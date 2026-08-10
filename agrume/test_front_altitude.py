#!/usr/bin/env python3
"""
test_front_altitude.py — banc de l'étape 10, HORS-LIGNE.

    python3 agrume/test_front_altitude.py

⚠️ CE QUE CE BANC PROTÈGE.

`front_altitude.py` ne calcule rien de physique : il RANGE des nombres
dans le tableau qu'attend un détecteur écrit dans un autre langage. Tous
ses modes de panne sont donc silencieux — le détecteur tournera, rendra
un R², et ce R² ne voudra rien dire. Cinq façons d'y arriver, une par
section :

  1. **Une direction retournée.** `atan2(v, u)` au lieu de `atan2(-u,-v)`
     donne des directions plausibles à 180° près, et une bascule de 40°
     reste une bascule de 40° : rien ne crie, et les deux niveaux sont
     faux de la même façon, donc la comparaison a l'air saine.
  2. **Un index plat à l'envers.** Le produit B range ses latitudes du
     NORD au SUD, la grille de production du SUD au NORD. Se tromper
     donne des vents justes attribués aux mauvaises latitudes : le plan
     spatio-temporel s'ajuste alors sur une géométrie inventée.
  3. **Une échéance de décalage.** La production ne publie pas
     l'échéance 0 ; la garder décale d'une heure la fenêtre de référence
     du détecteur, et les deux grilles ne sont plus jouables l'une contre
     l'autre.
  4. **Un trou comblé par un zéro.** Un vent manquant devenu 0 est un
     calme plat crédible — et il ABAISSE la médiane de référence, donc il
     FABRIQUE des sauts de vent.
  5. **Une rafale prise ailleurs.** Le plus proche voisin rend toujours
     un indice, même pour un point à 300 km de la grille de surface.
"""

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import front_altitude as F  # noqa: E402

echecs = []


def verifier(nom, condition, detail=""):
    print(f"  {'✓' if condition else '✗'} {nom}"
          + (f"   {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


# ── Un produit B synthétique dont la VITESSE encode sa position ───────
# `u = (1000 * j + i) / 3,6` avec `v = 0` : la vitesse publiée en km/h
# vaut donc EXACTEMENT `1000 * j + i`, où `j` est l'indice dans la source
# (du nord vers le sud). Une erreur d'indexation ne rend pas un vent
# plausible, elle rend les coordonnées de l'endroit où on est allé
# chercher — même principe que `test_transect.py`.
NJ, NI = 4, 3
RUN = "2026-08-10T12:00:00Z"
ECHEANCES = [0, 1, 2, 3, 4]
NIVEAUX = [10, 1000]


def produit_b(nan_en=None):
    lats = np.array([46.000, 45.975, 45.950, 45.925], dtype=np.float32)
    lons = np.array([5.500, 5.525, 5.550], dtype=np.float32)
    h = np.zeros((2, len(NIVEAUX), len(ECHEANCES), NJ, NI), dtype=np.float32)
    for j in range(NJ):
        for i in range(NI):
            h[0, :, :, j, i] = (1000 * j + i) / 3.6      # u
            h[1, :, :, j, i] = 0.0                        # v
    if nan_en is not None:
        s, j, i = nan_en
        h[0, :, s, j, i] = np.nan
    man = {
        "run": RUN,
        "niveaux_m_sol": list(NIVEAUX),
        "parametres": [{"nom": "u"}, {"nom": "v"}],
    }
    npz = {"h0025": h, "lats": lats, "lons": lons,
           "echeances": np.array(ECHEANCES, dtype=np.int16)}
    return man, npz


def surface(times=None, lats=None, lons=None):
    """Grille de surface minuscule, au format de `arome-gustfront`."""
    lats = [45.75, 46.00] if lats is None else lats
    lons = [5.50, 5.75] if lons is None else lons
    times = (["2026-08-10T14:00:00Z", "2026-08-10T15:00:00Z"]
             if times is None else times)
    n = len(lats) * len(lons)
    return {
        "run": RUN, "stepDeg": 0.25, "lats": lats, "lons": lons,
        "times": times,
        "vars": {nom: [[10 * (k + 1) + 100 * t for k in range(n)]
                       for t in range(len(times))]
                 for nom in F.CHAMPS_SURFACE},
    }


def main():
    print("\n── 1. La convention de vent, épinglée contre la production ──")
    for nom, u, v, attendu_dir in (
            ("vent d'OUEST (u > 0) → 270°", 10.0, 0.0, 270),
            ("vent d'EST (u < 0) → 90°", -10.0, 0.0, 90),
            ("vent du SUD (v > 0) → 180°", 0.0, 10.0, 180),
            ("vent du NORD (v < 0) → 0°", 0.0, -10.0, 0)):
        s, d = F.vent_kmh_dir(u, v)
        verifier(nom, d == attendu_dir, f"rendu {d}°")
    verifier("10 m/s → 36 km/h", F.vent_kmh_dir(10.0, 0.0)[0] == 36)
    # ⚠️ L'arrondi n'est pas cosmétique : le détecteur compare un saut à
    # 15 km/h. Arrondir d'un côté seulement fait basculer les points qui
    # sont au seuil, et l'écart passerait pour un effet du NIVEAU.
    verifier("arrondi identique à la production (3,6 m/s → 13 km/h)",
             F.vent_kmh_dir(3.6, 0.0)[0] == 13)
    verifier("u ou v manquant → (None, None)",
             F.vent_kmh_dir(None, 1.0) == (None, None))

    print("\n── 2. L'index plat et le sens des latitudes ──")
    man, npz = produit_b()
    g = F.construire(man, npz, surface(), 1000)
    verifier("les latitudes sont rendues CROISSANTES",
             g["lats"] == sorted(g["lats"]), str(g["lats"]))
    # La vitesse encode sa position : à l'indice plat k = j_asc * NI + i,
    # on doit retrouver 1000 * (NJ - 1 - j_asc) + i.
    faux = []
    for j_asc in range(NJ):
        for i in range(NI):
            k = j_asc * NI + i
            attendu = 1000 * (NJ - 1 - j_asc) + i
            if g["vars"]["spd"][0][k] != attendu:
                faux.append((k, g["vars"]["spd"][0][k], attendu))
    verifier("chaque vitesse décode EXACTEMENT sa position source",
             not faux, f"{len(faux)} écarts" if faux else f"{NJ * NI} points")
    # ⚠️ TROUVÉ PAR CE BANC, ET PAS PAR LA RELECTURE. Le point (0, 0) de
    # la grille synthétique porte u = v = 0. Il ne sort ni à 270° ni à
    # 0°, mais à **180°** : `atan2(-0.0, -0.0)` vaut −π, pas 0. Un point
    # parfaitement calme annonce donc un vent de SUD — dans ce fichier
    # comme dans `arome-gustfront/ingest.py`, qui porte la même formule
    # depuis le 31/07.
    #
    # Conséquence réelle, bornée : une maille qui passe au calme puis se
    # relève fait comparer la direction suivante à un 180° qui ne veut
    # rien dire, donc peut FABRIQUER une bascule de plus de 40°. Elle ne
    # suffit pas à faire un candidat (il faut en plus un saut de vent de
    # 15 km/h et une rafale de 45), et elle joue à l'identique aux deux
    # niveaux — l'étape 10 n'en est donc pas faussée. Épinglé ici pour
    # que ce ne soit pas redécouvert comme une nouveauté.
    dirs_venteux = {d for d, s in zip(g["vars"]["dir"][0], g["vars"]["spd"][0])
                    if s}
    verifier("u et v n'ont pas été échangés (270° partout où il y a du vent)",
             dirs_venteux == {270}, str(sorted(dirs_venteux)))
    verifier("vent nul → 180°, comme la production (un calme annonce un SUD)",
             F.vent_kmh_dir(0.0, 0.0) == (0, 180),
             str(F.vent_kmh_dir(0.0, 0.0)))
    verifier("nombre de points = nj × ni",
             len(g["vars"]["spd"][0]) == NJ * NI)

    print("\n── 3. Les échéances : la production ne publie pas le 0 ──")
    verifier("l'échéance 0 est écartée", len(g["times"]) == len(ECHEANCES) - 1,
             f"{len(g['times'])} échéances")
    verifier("la première échéance servie est run + 1 h",
             g["times"][0] == "2026-08-10T13:00:00Z", g["times"][0])
    verifier("la dernière est run + 4 h",
             g["times"][-1] == "2026-08-10T16:00:00Z", g["times"][-1])
    man0, npz0 = produit_b()
    npz0["echeances"] = np.array([0], dtype=np.int16)
    npz0["h0025"] = npz0["h0025"][:, :, :1]
    try:
        F.construire(man0, npz0, surface(), 1000)
        leve = False
    except SystemExit:
        leve = True
    verifier("un produit B réduit à l'échéance 0 est REFUSÉ", leve)

    print("\n── 4. Les trous restent des trous ──")
    man_n, npz_n = produit_b(nan_en=(2, 1, 1))   # échéance d'indice 2, point (1,1)
    gn = F.construire(man_n, npz_n, surface(), 10)
    k = (NJ - 1 - 1) * NI + 1
    verifier("un vent manquant devient None, JAMAIS 0",
             gn["vars"]["spd"][1][k] is None and gn["vars"]["dir"][1][k] is None)
    verifier("les trous sont comptés et publiés", gn["trous_vent"] == 1,
             f"trous_vent = {gn['trous_vent']}")

    print("\n── 5. Le raccord vers la grille de surface ──")
    # Les quatre latitudes du domaine synthétique tombent toutes à moins
    # d'un demi-pas de 46,00 ; les longitudes à moins d'un demi-pas de
    # 5,50. La rafale attendue est donc celle du point (46,00 / 5,50).
    s = surface()
    gs = F.construire(man, npz, s, 10)
    i_lat, i_lon = 1, 0                       # 46,00 et 5,50
    attendu = s["vars"]["gust"][0][i_lat * len(s["lons"]) + i_lon]
    verifier("la rafale vient du plus proche point de surface",
             gs["vars"]["gust"][1][0] == attendu,
             f"{gs['vars']['gust'][1][0]} attendu {attendu}")
    verifier("couverture de surface publiée", gs["surface"]["couverture"] == 1.0)
    # ⚠️ L'appariement se fait sur l'HEURE VALIDE. La surface synthétique
    # ne porte que 14 h et 15 h : les échéances 13 h et 16 h doivent
    # sortir VIDES, pas décalées d'une heure.
    verifier("une heure absente de la surface donne None, pas un décalage",
             all(x is None for x in gs["vars"]["gust"][0])
             and all(x is None for x in gs["vars"]["gust"][3]))
    verifier("les heures communes sont comptées",
             gs["surface"]["heures_communes"] == 2)

    # Domaine entièrement hors de l'emprise de la grille de surface.
    loin = surface(lats=[10.0, 10.25], lons=[10.0, 10.25])
    gl = F.construire(man, npz, loin, 10)
    verifier("hors emprise : la rafale est None, pas celle du BORD",
             all(x is None for ligne in gl["vars"]["gust"] for x in ligne))
    verifier("hors emprise : la couverture le dit (0 %)",
             gl["surface"]["couverture"] == 0.0)
    axe = np.array([0.0, 0.25, 0.50])
    verifier("_plus_proche refuse au-delà d'un demi-pas",
             F._plus_proche(axe, 0.30, 0.125) == 1
             and F._plus_proche(axe, 5.0, 0.125) is None)

    print("\n── 6. Les refus, qui disent ce qui existe ──")
    try:
        F.construire(man, npz, surface(), 375)
        leve = False
    except SystemExit as e:
        leve = "10" in str(e) and "1000" in str(e)
    verifier("un niveau absent est refusé EN DISANT lesquels existent", leve)
    man_sans_u = dict(man, parametres=[{"nom": "v"}])
    try:
        F.construire(man_sans_u, npz, surface(), 10)
        leve = False
    except SystemExit:
        leve = True
    verifier("un produit B sans « u » est refusé", leve)
    try:
        F.parite(g, surface())          # g est à 1000 m
        leve = False
    except SystemExit:
        leve = True
    verifier("la parité est refusée ailleurs qu'à 10 m", leve)

    print("\n── 7. Le format attendu par gfDetectModel ──")
    for cle in ("lats", "lons", "times", "vars"):
        verifier(f"clé « {cle} » présente", cle in g)
    manquants = [n for n in ("spd", "dir", "gust", "pres", "cape", "precip",
                             "temp") if n not in g["vars"]]
    verifier("les sept champs que le détecteur lit sont là", not manquants,
             str(manquants))
    verifier("chaque champ a une ligne par échéance",
             all(len(g["vars"][n]) == len(g["times"]) for n in g["vars"]))
    verifier("chaque ligne a nj × ni valeurs",
             all(len(ligne) == NJ * NI
                 for n in g["vars"] for ligne in g["vars"][n]))

    print("\n  front_altitude :", "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
