#!/usr/bin/env python3
"""
test_transect.py — banc de la coupe verticale (étape 8), HORS-LIGNE.

    python3 agrume/test_transect.py

⚠️ CE QUE CE BANC PROTÈGE.

Une coupe verticale est un dessin. C'est ce qui la rend dangereuse : elle
a l'air juste tant qu'elle a l'air d'une coupe. Six façons de casser en
SILENCE, une par section :

  1. **Une coupe retournée.** Les latitudes du produit B DÉCROISSENT. Une
     indexation par formule à partir d'un coin donne un indice négatif —
     que numpy accepte sans broncher. La coupe montre alors une autre
     vallée, et elle ressemble toujours à une vallée.
  2. **Une finesse fabriquée.** Le plus proche voisin fait que 200 points
     d'échantillonnage peuvent ne reposer que sur 20 colonnes. La courbe
     est lisse, le modèle ne l'est pas.
  3. **Un segment qui sort du domaine.** Le plus proche voisin existe
     TOUJOURS : sans contrôle, les points hors domaine se recollent sur
     le bord et produisent une coupe plate parfaitement crédible.
  4. **Deux formats pour une même donnée.** Le sondage et la coupe
     servent les mêmes niveaux ; s'ils les nomment différemment, le front
     écrit deux lecteurs et l'un des deux périme.
  5. **Un plafond invisible.** Le produit B n'a AUCUN isobare : la coupe
     s'arrête à `zsol + 3000 m`, et ce plafond suit le relief. Une coupe
     qui prétend monter plus haut ment.
  6. **Un trou comblé.** Un niveau manquant doit être ABSENT, pas
     interpolé depuis ses voisins.

Aucun réseau, aucun GRIB, aucune clé.
"""
from __future__ import annotations

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "verif"))

import transect as T  # noqa: E402
from colonnes import Colonnes  # noqa: E402
from quantification import PARAMS_0025  # noqa: E402
from domaine import DOMAINE, NIVEAUX_H_0025  # noqa: E402
from grille import Grille, PARAMS_GRILLE  # noqa: E402
from profil import niveaux_hauteur  # noqa: E402

echecs = []


def verifier(nom, condition, detail=""):
    print(f"  {'✓' if condition else '✗'} {nom}"
          + (f"   {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


# ── Une grille synthétique dont TOUT encode sa position ───────────────
# `zsol = 100 * j + i` et `u = 1000 * j + i` : une erreur d'indexation ne
# donne pas un nombre plausible, elle donne les coordonnées de l'endroit
# où on est allé chercher.
NJ, NI, NSTEP = 61, 85, 3
PAS = 0.025


def grille_bidon():
    lats = np.array([DOMAINE["latmax"] - k * PAS for k in range(NJ)],
                    dtype=np.float32)          # ⚠️ DÉCROISSANTES
    lons = np.array([DOMAINE["lonmin"] + k * PAS for k in range(NI)],
                    dtype=np.float32)
    zsol = (np.arange(NJ)[:, None] * 100.0
            + np.arange(NI)[None, :]).astype(np.float32)
    g = Grille("2026-08-10T09:00:00Z", [0, 1, 2], lats, lons, zsol)
    ip = {p["nom"]: k for k, p in enumerate(PARAMS_GRILLE)}
    for k in range(len(NIVEAUX_H_0025)):
        for s in range(NSTEP):
            g.h0025[ip["u"], k, s] = (np.arange(NJ)[:, None] * 1000.0
                                      + np.arange(NI)[None, :])
            g.h0025[ip["v"], k, s] = 0.0
            g.h0025[ip["t"], k, s] = 10.0 - k
            g.h0025[ip["r"], k, s] = 50.0
            g.h0025[ip["tke"], k, s] = 0.5
    return g


def main():
    g = grille_bidon()

    print("\n── 1. ⚠️ Les latitudes DÉCROISSENT — l'indexation ne le "
          "suppose pas, elle le lit ──")
    # Un point clairement dans le sud-est du domaine.
    lat_cible, lon_cible = 45.0, 7.0
    j, i = T.index_plus_proche(g.lats, g.lons, lat_cible, lon_cible)
    verifier("le plus proche voisin tombe à moins d'un demi-pas",
             abs(float(g.lats[j]) - lat_cible) <= 0.5 * PAS + 1e-6
             and abs(float(g.lons[i]) - lon_cible) <= 0.5 * PAS + 1e-6,
             f"j={j}, i={i} → {float(g.lats[j]):.4f}/{float(g.lons[i]):.4f}")
    # ⚠️ La formule « à partir du coin », celle qu'on écrit d'instinct.
    j_formule = int(round((lat_cible - float(g.lats[0])) / PAS))
    verifier("⚠️ la formule (lat − lat[0]) / pas donne un indice NÉGATIF, "
             "que numpy indexe sans lever",
             j_formule < 0 and g.zsol[j_formule, i] != g.zsol[j, i],
             f"{j_formule} au lieu de {j} → zsol {float(g.zsol[j_formule, i]):.0f} "
             f"au lieu de {float(g.zsol[j, i]):.0f}")
    verifier("la valeur servie encode bien la position demandée "
             "(zsol = 100·j + i)",
             abs(float(g.zsol[j, i]) - (100 * j + i)) < 1e-6)

    print("\n── 2. ⚠️ La finesse affichée n'est pas la finesse du modèle ──")
    a, b = (45.60, 5.90), (45.45, 6.60)      # Chambéry → Tarentaise, ~55 km
    fin = T.couper(g, None, a, b, 1, n=200)
    verifier("200 points demandés → 200 points servis",
             fin["resolution"]["nbPoints"] == 200)
    verifier("⚠️ mais BEAUCOUP moins de colonnes distinctes derrière",
             fin["resolution"]["nbMaillesDistinctes"] < 60,
             f"{fin['resolution']['nbMaillesDistinctes']} mailles pour "
             f"200 points")
    verifier("le drapeau `escalier` est levé, il n'est pas à deviner",
             fin["resolution"]["escalier"] is True)
    verifier("la réponse porte le point DEMANDÉ et le point SERVI",
             all("lat" in p and "latMaille" in p for p in fin["points"]))
    ecart_max = max(T.haversine_km(p["lat"], p["lon"],
                                   p["latMaille"], p["lonMaille"])
                    for p in fin["points"])
    verifier("l'écart demandé ↔ servi reste sous la demi-diagonale de maille",
             ecart_max < 1.8, f"max {ecart_max*1000:.0f} m")

    defaut = T.couper(g, None, a, b, 1)
    verifier("le pas par défaut est la plus PETITE dimension de maille "
             "(est-ouest), pas la plus grande",
             abs(defaut["segment"]["pasKm"] - 1.95) < 0.05,
             f"{defaut['segment']['pasKm']} km "
             f"(maille {defaut['resolution']['mailleKm']})")
    verifier("⚠️ et il produit encore des doublons, ce qui est assumé et dit",
             defaut["resolution"]["nbMaillesDistinctes"]
             <= defaut["resolution"]["nbPoints"])

    print("\n── 3. ⚠️ Un segment hors domaine est REFUSÉ, pas recollé ──")
    try:
        T.couper(g, None, (45.6, 5.9), (45.6, 9.5), 1, n=10)
        leve, msg = False, ""
    except ValueError as e:
        leve, msg = True, str(e)
    verifier("il lève au lieu de servir une coupe plate", leve)
    verifier("le message dit POURQUOI c'est dangereux (recollage sur le bord)",
             "RECOLLANT" in msg or "recollant" in msg)
    # Et le contraire : un segment entièrement dedans passe.
    try:
        T.couper(g, None, (45.0, 6.0), (45.5, 6.5), 1, n=5)
        dedans = True
    except ValueError:
        dedans = False
    verifier("un segment entièrement dans le domaine passe", dedans)

    print("\n── 4. ⚠️ Le sondage et la coupe nomment la donnée PAREIL ──")
    col = Colonnes("2026-08-10T09:00:00Z",
                   [dict(id="X", lat=45.5, lon=6.5, nom="", source="",
                         position_suspecte=False)], [0])
    ic = {p["nom"]: k for k, p in enumerate(PARAMS_0025)}
    for k in range(len(NIVEAUX_H_0025)):
        col.c0025[0, ic["u"], k, 0] = 3.0
        col.c0025[0, ic["v"], k, 0] = 4.0
        col.c0025[0, ic["t"], k, 0] = 5.0
        col.c0025[0, ic["r"], k, 0] = 60.0
        col.c0025[0, ic["tke"], k, 0] = 0.2
    cles_profil = set(niveaux_hauteur(col, 0, 0, 1000.0)[0])
    _z, niv = T.colonne(g, 10, 10, 0)
    cles_coupe = set(niv[0])
    verifier("les clés de la coupe = celles du sondage + la décoration vent",
             cles_coupe == cles_profil | {"vitesseKmh", "directionDeg"},
             f"en trop : {sorted(cles_coupe - cles_profil)} ; "
             f"manquantes : {sorted(cles_profil - cles_coupe)}")
    # La convention de direction, clouée par une valeur et pas par un texte.
    v_est = T.decorer_vent(dict(u=10.0, v=0.0))
    verifier("⚠️ un vent qui SOUFFLE vers l'est est annoncé venant de 270°",
             v_est["directionDeg"] == 270, "convention météo")

    print("\n── 5. ⚠️ Le plafond suit le relief, et il n'y a pas d'isobare ──")
    c = T.couper(g, None, (45.0, 6.0), (45.5, 6.5), 1, n=5)
    ok_plafond = True
    for p in c["points"]:
        haut = max(n["altitudeM"] for n in p["niveaux"])
        if abs(haut - (p["solModeleM"] + max(NIVEAUX_H_0025))) > 0.51:
            ok_plafond = False
        if abs(p["plafondM"] - haut) > 0.51:
            ok_plafond = False
    verifier("le sommet de chaque colonne vaut solModèle + 3000 m, "
             "colonne par colonne", ok_plafond)
    verifier("aucun niveau n'est marqué `isobare` — le produit B n'en a pas",
             all(n["source"] == "hauteur"
                 for p in c["points"] for n in p["niveaux"]))
    verifier("la réponse ANNONCE ce plafond au lieu de le laisser deviner",
             "isobare" in c["plafond"]["note"]
             and c["plafond"]["hauteurSolMaxM"] == 3000)
    sols = [p["solModeleM"] for p in c["points"]]
    verifier("le relief du modèle est publié pour être tracé sous la coupe",
             c["relief"]["solMinM"] == min(sols)
             and c["relief"]["solMaxM"] == max(sols))

    print("\n── 6. ⚠️ Un niveau manquant est ABSENT, jamais comblé ──")
    g2 = grille_bidon()
    ip = {p["nom"]: k for k, p in enumerate(PARAMS_GRILLE)}
    k_trou = NIVEAUX_H_0025.index(500)
    g2.h0025[ip["u"], k_trou, :, :, :] = np.nan
    _z2, niv2 = T.colonne(g2, 10, 10, 0)
    hauteurs = [n["hauteurSolM"] for n in niv2]
    verifier("le niveau 500 m/sol a disparu de la colonne",
             500 not in hauteurs and len(hauteurs) == len(NIVEAUX_H_0025) - 1)
    verifier("ses voisins 375 et 625 sont intacts et non déplacés",
             375 in hauteurs and 625 in hauteurs)
    # La TKE manque à l'échéance 0 en production : ce n'est pas un bug.
    g3 = grille_bidon()
    g3.h0025[ip["tke"], :, 0, :, :] = np.nan
    _z3, niv3 = T.colonne(g3, 10, 10, 0)
    verifier("une TKE absente ne fait PAS disparaître le niveau "
             "(mesuré : elle manque à l'échéance 0)",
             len(niv3) == len(NIVEAUX_H_0025)
             and all(n["tke"] is None for n in niv3))

    print("\n── 7. ⚠️ L'orthodromie contre la droite en lat/lon : MESURÉ, "
          "et ce n'est PAS négligeable ──")
    # ⚠️ Cette section a démenti un commentaire écrit une heure plus tôt
    # dans `transect.py`, qui annonçait « quelques dizaines de mètres ».
    diagonale = T.ecart_droite_m((DOMAINE["latmin"], DOMAINE["lonmin"]),
                                 (DOMAINE["latmax"], DOMAINE["lonmax"]))
    verifier("⚠️ sur la diagonale du domaine (233 km), l'écart atteint "
             "0,6 MAILLE — assez pour changer de colonne",
             1000.0 < diagonale < 1400.0,
             f"{diagonale:.0f} m contre 1950 m de maille")
    court = T.ecart_droite_m(a, b)
    verifier("sur un segment de 55 km il retombe sous 100 m, et là il est "
             "vraiment négligeable", court < 100.0, f"{court:.0f} m")
    verifier("l'écart croît comme le CARRÉ de la longueur (ce qui explique "
             "les deux chiffres)",
             abs(diagonale / max(court, 1e-9)
                 - (233.0 / 55.0) ** 2) < 0.35 * (233.0 / 55.0) ** 2,
             f"rapport mesuré {diagonale/max(court,1e-9):.1f}, "
             f"attendu ~{(233.0/55.0)**2:.1f}")
    verifier("la réponse PUBLIE cet écart pour le segment demandé",
             abs(fin["segment"]["ecartDroiteLatLonM"] - court) < 5.0,
             f"{fin['segment']['ecartDroiteLatLonM']} m")
    verifier("les deux extrémités du segment sont servies exactement",
             abs(T.point_intermediaire(a, b, 0.0)[0] - a[0]) < 1e-9
             and abs(T.point_intermediaire(a, b, 1.0)[1] - b[1]) < 1e-9)

    print("\n── 8. Les refus qui évitent une réponse absurde ──")
    for quoi, appel in (
            ("un segment de longueur nulle renvoie vers le sondage",
             lambda: T.couper(g, None, (45.5, 6.5), (45.5, 6.5), 1, n=5)),
            ("une échéance absente du run est refusée, en disant lesquelles "
             "existent",
             lambda: T.couper(g, None, (45.0, 6.0), (45.5, 6.5), 9, n=5))):
        try:
            appel()
            leve = False
        except ValueError:
            leve = True
        verifier(quoi, leve)

    print("\n  transect :", "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
