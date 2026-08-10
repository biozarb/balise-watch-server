#!/usr/bin/env python3
"""
test_profil.py — banc du raccord vertical.

    python3 agrume/test_profil.py
    python3 agrume/test_profil.py --archive <colonnes.npz> <manifeste.json>

⚠️ CE QUE CE BANC PROTÈGE.

Le profil vertical est le premier livrable d'AGRUME qu'un pilote lira
directement, et ses trois modes de panne sont muets :

  1. **Servir de l'air souterrain.** Dans les Alpes, 1000, 950 et 925 hPa
     sont sous le terrain à peu près partout. Le modèle y met des valeurs
     extrapolées, parfaitement crédibles à l'affichage et physiquement
     vides de sens.
  2. **Une marche au raccord.** Si les deux sources ne coïncident pas
     dans la zone de recouvrement, c'est qu'une conversion est fausse —
     géopotentiel non divisé par g, mauvaise orographie, niveau mal
     indexé. Une marche ne vient JAMAIS de la météo.
  3. **Mélanger par l'angle.** Un vent de 359° et un de 001° sont à 2°
     l'un de l'autre ; leur moyenne en degrés vaut 180°, soit exactement
     l'inverse.

Sans `--archive`, tout est synthétique et hors-ligne. Avec, on rejoue le
critère d'acceptation du lot sur **100 colonnes réelles**.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

import profil as P  # noqa: E402
from domaine import RACCORD_BAS_M, RACCORD_HAUT_M  # noqa: E402

echecs = []


def verifier(nom, condition, detail=""):
    print(f"  {'✓' if condition else '✗'} {nom}" + (f"   {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


def uv(deg_meteo, force):
    """(u, v) d'un vent venant de `deg_meteo`, convention météo."""
    a = math.radians(270.0 - deg_meteo)
    return force * math.cos(a), force * math.sin(a)


def pt(alt, deg, force, **kw):
    u, v = uv(deg, force)
    return dict(altitudeM=float(alt), u=u, v=v, source="hauteur",
                maille="0025", t=None, hr=None, tke=None, **kw)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--archive", nargs=2, metavar=("NPZ", "JSON"), default=None)
    a = p.parse_args(argv)

    print("── L'altitude lue dans le nom : un pis-aller, pas une source ──")
    verifier("« Déco Planpraz Chamonix 1958m » → 1958",
             P.altitude_du_nom("Déco Planpraz Chamonix 1958m") == 1958.0)
    verifier("« Signal de Soi 2050m » → 2050",
             P.altitude_du_nom("Signal de Soi 2050m") == 2050.0)
    verifier("⚠️ « Pioupiou 1006 » → None (c'est un IDENTIFIANT, pas une "
             "altitude)", P.altitude_du_nom("Pioupiou 1006") is None)
    verifier("⚠️ « Windbird 1377 » → None, même raison",
             P.altitude_du_nom("Windbird 1377") is None)
    verifier("⚠️ « Mât 10m » → None : 10 m n'est pas une altitude de site",
             P.altitude_du_nom("Mât 10m") is None)
    verifier("un nom sans altitude → None",
             P.altitude_du_nom("Nendaz Verrey") is None)
    verifier("nom vide ou absent → None",
             P.altitude_du_nom("") is None and P.altitude_du_nom(None) is None)
    z, src = P.reference_sol({"nom": "X"}, altitude_reelle=1234)
    verifier("une altitude fournie l'emporte sur le nom, et la source le dit",
             z == 1234.0 and src == "fournie")
    z, src = P.reference_sol({"nom": "Déco 1800m"})
    verifier("sinon on prend le nom, et on le DIT",
             z == 1800.0 and src == "nom de la balise")
    verifier("inconnue → (None, None), jamais une valeur inventée",
             P.reference_sol({"nom": "sans altitude"}) == (None, None))

    print("\n── Le poids du raccord ────────────────────────────────────")
    zs = 1000.0
    verifier("hauteur SEULE sous z_s + 1000",
             P.poids_hauteur(zs + 500, zs) == 1.0
             and P.poids_hauteur(zs, zs) == 1.0)
    verifier("isobares SEULES au-dessus de z_s + 3000",
             P.poids_hauteur(zs + 3000, zs) == 0.0
             and P.poids_hauteur(zs + 5000, zs) == 0.0)
    milieu = P.poids_hauteur(zs + 2000, zs)
    verifier("mélange à mi-course = 0,5", abs(milieu - 0.5) < 1e-9,
             f"{milieu:.3f}")
    verifier("le poids est continu aux deux bornes",
             abs(P.poids_hauteur(zs + RACCORD_BAS_M + 1, zs) - 1.0) < 0.002
             and abs(P.poids_hauteur(zs + RACCORD_HAUT_M - 1, zs)) < 0.002)
    verifier("le poids décroît strictement dans la rampe",
             all(P.poids_hauteur(zs + 1000 + k, zs)
                 > P.poids_hauteur(zs + 1000 + k + 100, zs)
                 for k in range(0, 1900, 100)))

    print("\n── Interpolation : par u/v, et JAMAIS d'extrapolation ─────")
    pts = [pt(1000, 350, 5.0), pt(2000, 10, 5.0)]
    u, v = P._interp_uv(pts, 1500)
    d = (270 - math.degrees(math.atan2(v, u))) % 360
    verifier("⚠️ 350° → 010° : la moyenne tombe au NORD, pas au sud",
             min(abs(d - 0), abs(d - 360)) < 1.0, f"{d:.1f}°")
    verifier("  (la moyenne naïve des angles aurait donné 180°)",
             abs((350 + 10) / 2 - 180) < 1e-9)
    verifier("la vitesse ne dépasse pas les deux bornes",
             math.hypot(u, v) <= 5.0 + 1e-9, f"{math.hypot(u, v):.3f} m/s")
    verifier("sous la borne basse → (None, None), pas d'extrapolation",
             P._interp_uv(pts, 500) == (None, None))
    verifier("au-dessus de la borne haute → (None, None)",
             P._interp_uv(pts, 5000) == (None, None))
    verifier("un seul point → (None, None)",
             P._interp_uv([pt(1000, 0, 5)], 1000) == (None, None))
    u2, v2 = P._interp_uv([pt(1000, 270, 4.0), pt(2000, 270, 8.0)], 1250)
    verifier("interpolation linéaire exacte au quart",
             abs(math.hypot(u2, v2) - 5.0) < 1e-6, f"{math.hypot(u2, v2):.3f}")

    print("\n── ⚠️ Aucun niveau isobare sous le sol du modèle ───────────")
    class ColFactice:
        pass
    c = ColFactice()
    c.ziso = np.array([[[500.0], [1500.0], [2500.0]]], dtype=np.float32)
    c.ciso = np.full((1, len(P.PARAMS_ISO), 3, 1), 3.0, dtype=np.float16)
    import domaine as D
    vrais = D.NIVEAUX_P
    D.NIVEAUX_P = (1000, 850, 700)
    P.NIVEAUX_P = D.NIVEAUX_P
    try:
        servis = P.niveaux_isobares(c, 0, 0, z_s=1200.0)
        verifier("le niveau à 500 m est SOUS le sol (1200 m) → jamais servi",
                 all(x["altitudeM"] >= 1200 for x in servis),
                 f"{[x['altitudeM'] for x in servis]}")
        verifier("les niveaux au-dessus sont servis", len(servis) == 2)
        tous = P.niveaux_isobares(c, 0, 0, z_s=None)
        verifier("sans sol connu, on ne masque rien (et on ne prétend pas)",
                 len(tous) == 3)
        verifier("un sol très haut masque tout",
                 P.niveaux_isobares(c, 0, 0, z_s=9000.0) == [])
    finally:
        D.NIVEAUX_P = vrais
        P.NIVEAUX_P = vrais

    print("\n── L'assemblage ───────────────────────────────────────────")
    zs = 1000.0
    hauteur = [pt(zs + h, 270, 5 + h / 500) for h in
               (10, 100, 500, 1000, 1500, 2000, 2500, 3000)]
    isobares = [dict(pt(zs + h, 280, 6 + h / 500), source="isobare",
                     niveauHPa=900 - k * 50)
                for k, h in enumerate((800, 1500, 2200, 2900, 3600, 4300))]
    points = P.assembler(hauteur, isobares, zs)
    alts = [x["altitudeM"] for x in points]
    verifier("le profil est strictement croissant en altitude",
             all(b > a for a, b in zip(alts, alts[1:])), f"{len(alts)} points")
    verifier("aucune altitude en double", len(alts) == len(set(alts)))
    verifier("le poids décroît le long de la colonne",
             all(b <= a + 1e-9 for a, b in
                 zip([x["poidsHauteur"] for x in points],
                     [x["poidsHauteur"] for x in points][1:])))
    verifier("des points sont bien mélangés",
             any(x["source"] == "melange" for x in points),
             f"{sum(1 for x in points if x['source'] == 'melange')} points")
    verifier("les isobares ne réapparaissent PAS sous le sommet des "
             "niveaux hauteur (sinon dents de scie)",
             all(x["altitudeM"] > zs + 3000 for x in points
                 if x["source"] == "isobare"))
    verifier("chaque point dit d'où il vient",
             all("source" in x and "poidsHauteur" in x for x in points))
    verifier("vent d'ouest pur → direction 270",
             P.assembler([pt(zs, 270, 5.0), pt(zs + 10, 270, 5.0)], [],
                         zs)[0]["directionDeg"] == 270)

    print("\n── ⚠️ L'écart au recouvrement, le vrai test du raccord ─────")
    ecarts = P.ecart_recouvrement(hauteur, isobares, zs)
    verifier("il ne porte QUE sur la zone de recouvrement",
             all(zs + RACCORD_BAS_M <= e["altitudeM"] <= zs + RACCORD_HAUT_M
                 for e in ecarts), f"{len(ecarts)} niveaux")
    # Deux sources identiques → écart nul. C'est le contrôle négatif.
    memes = [dict(pt(zs + h, 270, 5 + h / 500), source="isobare",
                  niveauHPa=900 - k * 50)
             for k, h in enumerate((1200, 1800, 2400))]
    e0 = P.ecart_recouvrement(hauteur, memes, zs)
    verifier("deux sources IDENTIQUES → écart nul (contrôle négatif)",
             e0 and max(x["ecartMs"] for x in e0) < 1e-4,
             f"max {max(x['ecartMs'] for x in e0):.2e} m/s")
    # Un géopotentiel non divisé par g décalerait tout : on le simule.
    decale = [dict(x, altitudeM=x["altitudeM"] * 1.5) for x in memes]
    e1 = P.ecart_recouvrement(hauteur, decale, zs)
    verifier("⚠️ une altitude isobare fausse fait APPARAÎTRE l'écart",
             (not e1) or max(x["ecartMs"] for x in e1) > 1e-3,
             "c'est exactement ce qu'on veut voir si g est oublié")

    print("\n── ⚠️ La marche hybride se mesure à HAUTEUR-SOL égale ──────")
    gros = [dict(pt(1642 + h, 180, 6.0), hauteurSolM=h) for h in (10, 50, 100)]
    fins = [dict(pt(1504 + h, 180, 6.0), hauteurSolM=h, maille="001")
            for h in (10, 50, 100)]
    m = P.marche_hybride(gros, fins)
    verifier("deux mailles d'accord → marche nulle, malgré 138 m d'écart "
             "d'altitude",
             len(m) == 3 and max(x["ecartMs"] for x in m) < 1e-3,
             f"écart d'altitude {m[0]['altitude0025M'] - m[0]['altitudeFineM']:.0f} m")
    verifier("la réponse porte les DEUX altitudes, pour qu'on ne confonde "
             "pas marche de vent et écart d'orographie",
             all("altitudeFineM" in x and "altitude0025M" in x for x in m))
    fins2 = [dict(pt(1504 + h, 200, 6.0), hauteurSolM=h, maille="001")
             for h in (10, 50, 100)]
    m2 = P.marche_hybride(gros, fins2)
    verifier("un désaccord de 20° se voit", min(x["ecartMs"] for x in m2) > 0.1,
             f"{m2[0]['ecartMs']:.2f} m/s")
    verifier("un niveau sans équivalent est ignoré, pas apparié au hasard",
             P.marche_hybride(gros, [dict(pt(1504, 180, 6.0),
                                          hauteurSolM=999)]) == [])

    # ══════════════════════════════════════════════════════════════════
    if a.archive:
        print("\n── ⚠️ CRITÈRE D'ACCEPTATION SUR 100 COLONNES RÉELLES ──────")
        from colonnes import Colonnes
        man = json.loads(open(a.archive[1], encoding="utf-8").read())
        col, _ = Colonnes.lire_npz(a.archive[0], man)
        rng = random.Random(42)
        paires = [(i, s) for i in range(len(col.balises)) for s in col.steps]
        rng.shuffle(paires)
        paires = paires[:100]

        tous_ecarts, sous_sol, sans_delta, non_croissants = [], 0, 0, 0
        marches = []
        for i, s in paires:
            r = P.sonder(col, man, i, s)
            zs = r["solModeleM"]["grille_0025"]
            for pt_ in r["profil"]:
                if pt_.get("niveauHPa") is not None and zs is not None \
                        and pt_["altitudeM"] < zs:
                    sous_sol += 1
            alts = [x["altitudeM"] for x in r["profil"]]
            if any(b <= x for x, b in zip(alts, alts[1:])):
                non_croissants += 1
            if "elevationDeltaM" not in r:
                sans_delta += 1
            e = r["raccord"]["ecartRecouvrementMs"]
            if e is not None:
                tous_ecarts.append(e)
            mh = r["marcheHybride"]["medianeMs"]
            if mh is not None:
                marches.append(mh)

        verifier("⚠️ AUCUN niveau isobare servi sous ALTITUDE(lat,lon)",
                 sous_sol == 0, f"{sous_sol} fautes sur 100 colonnes")
        verifier("tout profil est strictement croissant en altitude",
                 non_croissants == 0, f"{non_croissants} colonnes fautives")
        verifier("`elevationDeltaM` présent dans TOUTE réponse",
                 sans_delta == 0)
        if tous_ecarts:
            arr = np.sort(np.asarray(tous_ecarts))
            med = float(np.median(arr))
            d9 = float(arr[min(len(arr) - 1, int(0.9 * len(arr)))])
            verifier("⚠️ AUCUNE MARCHE au raccord hauteur/isobares "
                     "(< 1 m/s, critère du lot)",
                     med < 1.0,
                     f"médiane {med:.2f} m/s · d9 {d9:.2f} · max "
                     f"{float(arr[-1]):.2f} (n = {len(arr)} colonnes)")
            print(f"     ⓘ un écart médian très supérieur à 1 m/s voudrait "
                  f"dire qu'une conversion est fausse, pas qu'il vente.")
        else:
            verifier("des colonnes ont une zone de recouvrement exploitable",
                     False, "aucun écart calculable — archive sans isobares ?")
        if marches:
            arr = np.sort(np.asarray(marches))
            print(f"     ⓘ marche hybride 0,01°/0,025°, pour information : "
                  f"médiane {float(np.median(arr)):.2f} m/s · max "
                  f"{float(arr[-1]):.2f} (n = {len(arr)})")

    print("\n  profil :", "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
