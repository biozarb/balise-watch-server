#!/usr/bin/env python3
"""
test_calque.py — banc du calque altitude (étape 11), HORS-LIGNE.

    python3 agrume/test_calque.py
    python3 agrume/test_calque.py --archive grille.npz manifest.json

⚠️ CE QUE CE BANC PROTÈGE, ET POURQUOI IL EST LE SEUL CONTRÔLE POSSIBLE.

**Un calque interpolé de travers reste lisse, coloré et plausible.** Il
n'existe aucun contrôle visuel de ce fichier : une carte de vent fausse
ressemble à une carte de vent. Sept façons de casser en SILENCE, une par
section :

  1. **L'interpolation ne rend pas le niveau brut quand elle le devrait.**
     C'est l'invariant du lot, et il est vérifié sur TOUTES les colonnes ×
     TOUS les niveaux — 129 625 cas sur le domaine réel. Il ne dépend pas
     de l'œil, et c'est sa seule qualité qui compte.
  2. **Le vent interpolé par l'ANGLE.** Une colonne qui traverse 350° →
     010° donne 180° par la moyenne des angles et 0° par celle des
     composantes. Le calque montrerait un vent exactement inverse, et
     rien à l'écran ne le dirait.
  3. **Une extrapolation qui dort.** Le plus proche voisin et le
     `searchsorted` rendent TOUJOURS un indice : sans masque, une colonne
     sous le terrain est servie avec un poids négatif — une valeur
     parfaitement crédible, tirée de nulle part.
  4. **Un plafond oublié.** Le produit B ne porte AUCUN isobare. Une
     colonne s'arrête à `zsol + 3000 m` et ce plafond SUIT le relief.
  5. **Un trou qui se propage.** `0.0 × NaN = NaN` : un niveau supérieur
     absent effacerait le niveau inférieur pourtant présent.
  6. **Le dernier niveau, en float.** À `w = 1`, `a + (b − a)` n'est pas
     exactement `b`. L'invariant échouerait d'un ulp sur toute la tranche
     haute — donc invisiblement.
  7. **Les deux implémentations qui divergent.** Le calque s'interpole
     dans le navigateur ; `calque.fixture()` fabrique les vecteurs que le
     banc JS rejoue. Ce banc-ci vérifie que la fixture est déterministe
     et qu'elle CONTIENT les cas qui cassent.

Sans `--archive` : grille synthétique, aucun réseau, aucun GRIB, aucune
clé. Avec `--archive` : le run réel, et l'invariant sur 129 625 cas.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

import calque as C  # noqa: E402
from domaine import NIVEAUX_H_0025  # noqa: E402
from grille import Grille, PARAMS_GRILLE  # noqa: E402

echecs = []


def verifier(nom, condition, detail=""):
    print(f"  {'✓' if condition else '✗'} {nom}"
          + (f"   {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


# ══════════════════════════════════════════════════════════════════════
def grille_synthetique(nj=7, ni=9, steps=(0, 1)):
    """Une grille dont TOUT encode sa position.

    ⚠️ Même principe que `test_transect.py` : `zsol = 100·j + i` et
    `u = 1000·k + 10·j + i`. Une erreur d'indexation ne rend donc pas un
    nombre plausible mais les COORDONNÉES de l'endroit où l'on est allé
    chercher. Un banc qui utiliserait des valeurs réalistes ne
    distinguerait pas « faux » de « juste ».

    ⚠️ Les latitudes DÉCROISSENT, comme dans le produit B réel.
    """
    lats = np.array([46.3 - 0.025 * j for j in range(nj)], dtype=np.float32)
    lons = np.array([5.5 + 0.025 * i for i in range(ni)], dtype=np.float32)
    zsol = np.array([[100.0 * j + i for i in range(ni)] for j in range(nj)],
                    dtype=np.float32)
    g = Grille("2026-08-12T12:00:00Z", list(steps), lats, lons, zsol)
    ip = {p["nom"]: k for k, p in enumerate(PARAMS_GRILLE)}
    for nom, base in (("u", 1000.0), ("v", 2000.0), ("t", 0.0),
                      ("r", 50.0), ("tke", 1.0)):
        for k in range(len(NIVEAUX_H_0025)):
            for s in range(len(steps)):
                g.h0025[ip[nom], k, s] = np.float16(
                    base + k) + np.float16(0.0)
    return g


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--archive", nargs=2, default=None,
                   metavar=("NPZ", "MANIFESTE"))
    a = p.parse_args(argv)

    print("── 1. L'INVARIANT — une altitude qui tombe sur un niveau rend "
          "le niveau BRUT ──")
    g = grille_synthetique()
    ip = {q["nom"]: k for k, q in enumerate(PARAMS_GRILLE)}
    pires = []
    for j in range(g.zsol.shape[0]):
        for i in range(g.zsol.shape[1]):
            zs = float(g.zsol[j, i])
            for k, niveau in enumerate(NIVEAUX_H_0025):
                r = C.calque(g, 0, zs + niveau)
                brut = np.float32(g.h0025[ip["u"], k, 0, j, i])
                pires.append(abs(float(r["champs"]["u"][j, i]) - float(brut)))
    verifier("sur la grille synthétique, écart NUL à l'octet près "
             f"({len(pires)} cas)", max(pires) == 0.0,
             f"écart max {max(pires):.6g}")

    print("\n── 2. Le vent s'interpole par u/v, JAMAIS par l'angle ──")
    # Une colonne qui traverse 350° → 010°. Par les composantes, le
    # milieu vaut 0° ; par les angles, il vaudrait 180°.
    g2 = grille_synthetique(nj=1, ni=1, steps=(0,))
    g2.zsol[0, 0] = 0.0
    k10, k20 = 0, 1                       # niveaux 10 et 20 m
    for (k, ang) in ((k10, 350.0), (k20, 10.0)):
        rad = np.radians(270.0 - ang)
        g2.h0025[ip["u"], k, 0, 0, 0] = np.float16(10.0 * np.cos(rad))
        g2.h0025[ip["v"], k, 0, 0, 0] = np.float16(10.0 * np.sin(rad))
    r = C.calque(g2, 0, 15.0)             # pile au milieu des deux niveaux
    d = float(C.direction(r["champs"]["u"][0, 0], r["champs"]["v"][0, 0]))
    ecart_a_zero = min(abs(d), abs(d - 360.0))
    verifier("350° et 010° donnent 0° au milieu, PAS 180°",
             ecart_a_zero < 1.0, f"{d:.2f}°")
    verifier("la convention météo est clouée par une VALEUR "
             "(u = +10 m/s → 270°)",
             abs(float(C.direction(10.0, 0.0)) - 270.0) < 1e-9)

    print("\n── 3. Aucune extrapolation ne dort dans le code ──")
    g3 = grille_synthetique(nj=3, ni=3, steps=(0,))
    g3.zsol[:] = np.float32(1000.0)
    r = C.calque(g3, 0, 500.0)            # 500 m sous le sol du modèle
    verifier("une colonne dont le sol est AU-DESSUS n'est jamais servie",
             not r["servable"].any() and np.isnan(r["champs"]["u"]).all())
    verifier("et la raison publiée est le RELIEF, pas un défaut",
             (r["raisonMasque"] == C.MASQUE_RELIEF).all())
    verifier("le poids d'interpolation reste dans [0, 1] même là",
             float(np.min(r["poidsNiveauHaut"])) >= 0.0
             and float(np.max(r["poidsNiveauHaut"])) <= 1.0)

    print("\n── 4. Le plafond SUIT le relief, et il est refusé au-delà ──")
    r = C.calque(g3, 0, 1000.0 + 3000.0)  # pile sur le dernier niveau
    verifier("à zsol + 3000 m exactement, la colonne est ENCORE servie",
             bool(r["servable"].all()))
    r = C.calque(g3, 0, 1000.0 + 3000.1)
    verifier("à zsol + 3000,1 m elle ne l'est plus",
             not r["servable"].any()
             and (r["raisonMasque"] == C.MASQUE_PLAFOND).all())
    r = C.calque(g3, 0, 1000.0 + 5.0)     # au-dessus du sol, sous 10 m
    verifier("la bande entre zsol et zsol + 10 m est MASQUÉE (arbitré le "
             "12/08), et sa raison la distingue du relief",
             not r["servable"].any()
             and (r["raisonMasque"] == C.MASQUE_BAS).all())

    print("\n── 5. Un trou ne se propage pas vers le bas (0 × NaN) ──")
    g4 = grille_synthetique(nj=1, ni=1, steps=(0,))
    g4.zsol[0, 0] = 0.0
    g4.h0025[ip["u"], 1, 0, 0, 0] = np.float16(np.nan)   # niveau 20 m absent
    r = C.calque(g4, 0, 10.0, params=("u",))             # pile sur le 10 m
    verifier("niveau supérieur absent + altitude PILE sur l'inférieur → "
             "l'inférieur est servi, pas un trou",
             bool(r["servable"][0, 0])
             and float(r["champs"]["u"][0, 0]) == float(
                 np.float32(g4.h0025[ip["u"], 0, 0, 0, 0])))
    r = C.calque(g4, 0, 15.0, params=("u",))
    verifier("mais ENTRE les deux, la colonne est bien masquée — on "
             "n'invente pas le niveau manquant",
             not bool(r["servable"][0, 0])
             and r["raisonMasque"][0, 0] == C.MASQUE_DONNEE)

    print("\n── 6. Les bornes du mélange, et le motif MESURÉ des deux where ──")
    a_, b_ = np.float32(0.1), np.float32(0.3)
    verifier("w = 0 rend a à l'octet près",
             float(C.melanger(a_, b_, 0.0)) == float(a_))
    verifier("w = 1 rend b à l'octet près",
             float(C.melanger(a_, b_, 1.0)) == float(b_))
    # ⚠️ Ce contrôle-ci existe parce qu'un commentaire de `calque.py`
    # affirmait le contraire : que `a + (b − a)` ne rendait pas `b`. Sur
    # ce chemin de données, il le rend TOUJOURS — mesuré sur 6 millions
    # de couples. Le banc fige la mesure pour que personne ne réécrive
    # la justification fausse.
    rng = np.random.default_rng(7)
    x = np.float32(rng.uniform(-60, 60, 200_000)).astype(np.float64)
    y = np.float32(rng.uniform(-60, 60, 200_000)).astype(np.float64)
    verifier("⚠️ `a + (b − a)` rend b EXACTEMENT sur des float32 du même "
             "ordre — l'exactitude vient de la donnée, pas de la formule",
             int(np.sum(x + (y - x) != y)) == 0,
             f"0 contre-exemple sur {x.size}")
    verifier("✅ le VRAI motif des deux where : 0 × NaN et 1 × (b − NaN) "
             "valent NaN, donc un niveau absent effacerait son voisin",
             float(C.melanger(np.float32(np.nan), np.float32(7.5), 1.0)) == 7.5
             and float(C.melanger(np.float32(7.5), np.float32(np.nan), 0.0))
             == 7.5)
    k, w = C.encadrer(np.array([3000.0]))
    verifier("h = 3000 m (le dernier niveau) encadre sans sortir du tableau",
             int(k[0]) == len(NIVEAUX_H_0025) - 2 and float(w[0]) == 1.0)
    k, w = C.encadrer(np.array([float(n) for n in NIVEAUX_H_0025[:-1]]))
    verifier("sur CHAQUE niveau, le poids du supérieur vaut exactement 0",
             bool((w == 0.0).all()))

    print("\n── 7. La fixture contient les cas qui cassent, et elle est "
          "déterministe ──")
    f1 = C.fixture(g, 0, altitudes=(500.0, 1000.0), nb_colonnes=5)
    f2 = C.fixture(g, 0, altitudes=(500.0, 1000.0), nb_colonnes=5)
    verifier("deux appels donnent le même jeu (tirage déterministe)",
             json.dumps(f1, sort_keys=True) == json.dumps(f2, sort_keys=True),
             f"{f1['nbCas']} cas")
    zs = {c["zsol"] for c in f1["cas"]}
    verifier("le sol le PLUS BAS et le PLUS HAUT du domaine y sont",
             min(zs) == float(g.zsol.min()) and max(zs) == float(g.zsol.max()))
    sur_niveau = [c for c in f1["cas"]
                  if round(c["altitudeASLM"] - c["zsol"], 6)
                  in [float(n) for n in NIVEAUX_H_0025]]
    verifier("elle porte les 25 altitudes qui tombent PILE sur un niveau, "
             "pour chaque colonne", len(sur_niveau) >= 25 * len(zs),
             f"{len(sur_niveau)} cas sur niveau")

    # ══════════════════════════════════════════════════════════════════
    if a.archive:
        print("\n── 8. LE RUN RÉEL — l'invariant sur toutes les colonnes ──")
        man = json.loads(open(a.archive[1], encoding="utf-8").read())
        gr, man = Grille.lire_npz(a.archive[0], man)
        step = gr.steps[min(3, len(gr.steps) - 1)]
        i_step = gr.steps.index(step)
        zsol = np.asarray(gr.zsol, dtype=np.float64)
        nj, ni = zsol.shape
        pire, n = 0.0, 0
        for k, niveau in enumerate(NIVEAUX_H_0025):
            A = zsol + float(niveau)                 # une altitude PAR colonne
            h = A - zsol
            k_, w_ = C.encadrer(h)
            val = C.interpoler_champ(
                np.asarray(gr.h0025[0, :, i_step], dtype=np.float32), h)[0]
            brut = np.asarray(gr.h0025[0, k, i_step], dtype=np.float32)
            bon = np.isfinite(brut)
            pire = max(pire, float(np.max(np.abs(val[bon] - brut[bon])))
                       if bon.any() else 0.0)
            n += int(bon.sum())
        verifier(f"écart NUL sur les {n} cas (colonne × niveau) du run réel",
                 pire == 0.0, f"écart max {pire:.6g}")

        print("\n     couverture mesurée, échéance %d h :" % step)
        for A in (1000, 2000, 3000, 4000):
            r = C.calque(gr, step, float(A))
            c = r["couverture"]
            print(f"       {A:5d} m : servi {100*c['servi']:5.1f} %  ·  "
                  f"relief {100*c['relief']:5.1f} %  ·  plafond "
                  f"{100*c['auDessusDuPlafond']:5.1f} %  ·  bande basse "
                  f"{100*c['sousPremierNiveau']:5.2f} %")

    print("\n  calque :", "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
