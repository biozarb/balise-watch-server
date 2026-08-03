#!/usr/bin/env python3
"""
cadence_infoclimat.py — classer chaque station Infoclimat par DENSITÉ de
décollages, et chiffrer ce que la cadence fait vraiment baisser
(03/08/2026).

┌─ CE QUE CE SCRIPT SERT À DÉCIDER ───────────────────────────────────┐
│ La fenêtre d'une heure n'existe pas (mesuré, cf.                    │
│ `traces/sonde_fenetre_infoclimat.py`). La compression était déjà en │
│ place. **Il ne reste que la cadence.** Ce script chiffre le seul    │
│ levier restant, sur les vraies données, avant qu'on écrive le       │
│ poller.                                                             │
│                                                                     │
│ Paliers arbitrés par Yann le 02/08 — par DENSITÉ de décos, pas par  │
│ département : une frontière administrative n'a pas de sens météo, et │
│ un déco de bordure lit forcément des stations de l'autre côté.      │
└─────────────────────────────────────────────────────────────────────┘

⚠️ AUCUN APPEL AUTHENTIFIÉ. Ce script ne touche PAS l'API opendata : il
   lit `decos.json` en local et le GeoJSON PUBLIC des stations. Il est
   donc rejouable autant qu'on veut, depuis n'importe quelle IP.

⚠️ Le classement n'est PAS destiné à être figé dans un fichier de
   données : le poller doit le RECALCULER au démarrage, à partir du
   GeoJSON qu'il télécharge déjà chaque jour. Un fichier figé se
   désynchroniserait en silence à chaque station nouvelle. Ce script est
   l'outil de MESURE et de revue, pas la source de vérité.

Usage :  python3 tools/cadence_infoclimat.py
"""

import json
import math
import os
import sys
import urllib.request

ICI = os.path.dirname(os.path.abspath(__file__))
DECOS = os.path.join(ICI, '..', '..', 'web', 'public', 'data', 'decos.json')
STATIONS_GEOJSON = ("https://www.data.gouv.fr/api/1/datasets/r/"
                    "8a9e6a12-03f8-4056-861f-70b84136313e")
UA = "BaliseWatch-outil/1.0 (+argonautes.sim@gmail.com)"

RAYON_KM = 25.0
# (décos dans le rayon minimum, libellé, minutes)
PALIERS = [(20, "20 et +", 10), (5, "5 à 19", 20), (1, "1 à 4", 40),
           (0, "0", 60)]

# Cadence native mesurée le 02/08 : 10,0 à 14,7 min selon la station.
# Descendre sous 10 min ne rend PAS une valeur plus fraîche.
PLANCHER_MIN = 10
# Relevés qu'une station produit sur une journée PLEINE, déduit de la
# mesure du 03/08 : 85 relevés à 16h40 UTC → 85 / (16,67/24) ≈ 122.
RELEVES_JOUR_PLEIN = 122
LOT = 100


def haversine_km(a_lat, a_lon, b_lat, b_lon):
    r = 6371.0
    dlat, dlon = math.radians(b_lat - a_lat), math.radians(b_lon - a_lon)
    h = (math.sin(dlat / 2) ** 2 + math.cos(math.radians(a_lat))
         * math.cos(math.radians(b_lat)) * math.sin(dlon / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def charger_decos():
    with open(DECOS, encoding='utf-8') as f:
        return [(d[0], d[1]) for d in json.load(f)
                if isinstance(d, list) and len(d) >= 2]


def charger_stations():
    req = urllib.request.Request(STATIONS_GEOJSON, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        geo = json.loads(r.read().decode('utf-8', 'replace'))
    out = []
    for f in (geo.get('features') or []):
        g = (f.get('geometry') or {}).get('coordinates') or []
        p = f.get('properties') or {}
        if len(g) < 2 or not p.get('id'):
            continue
        if (p.get('license') or {}).get('source') != 'infoclimat.fr':
            continue
        out.append((str(p['id']), float(g[1]), float(g[0]),
                    p.get('name') or '?',
                    (p.get('license') or {}).get('license') or '?'))
    return out


def compter_par_bins(stations, decos, rayon):
    """Index spatial grossier : un bin de 0,25° (~28 km en lat). On ne
    compare une station qu'aux décos des bins voisins. 3 313 × 1 206 en
    force brute passerait aussi, mais l'index rend le script rejouable
    instantanément quand on voudra tester d'autres rayons."""
    pas = 0.25
    bins = {}
    for lat, lon in decos:
        bins.setdefault((int(lat / pas), int(lon / pas)), []).append((lat, lon))
    # marge : combien de bins couvrir de part et d'autre
    portee = int(rayon / (111.0 * pas)) + 1
    res = {}
    for sid, lat, lon, _nom, _lic in stations:
        bi, bj = int(lat / pas), int(lon / pas)
        n = 0
        for di in range(-portee, portee + 1):
            for dj in range(-portee, portee + 1):
                for dlat, dlon in bins.get((bi + di, bj + dj), ()):
                    if haversine_km(lat, lon, dlat, dlon) <= rayon:
                        n += 1
        res[sid] = n
    return res


def palier_de(n):
    for seuil, libelle, minutes in PALIERS:
        if n >= seuil:
            return libelle, minutes
    return PALIERS[-1][1], PALIERS[-1][2]


def main():
    decos = charger_decos()
    stations = charger_stations()
    print("═══ cadence par densité de décos — aucun appel authentifié ═══\n")
    print(f"{len(decos):,} décollages · {len(stations):,} stations "
          f"Infoclimat · rayon {RAYON_KM:.0f} km\n")

    compte = compter_par_bins(stations, decos, RAYON_KM)

    groupes = {}
    for sid, _lat, _lon, _nom, _lic in stations:
        lib, mn = palier_de(compte[sid])
        groupes.setdefault((lib, mn), []).append(sid)

    # ── Le classement ────────────────────────────────────────────────
    attendu = {"20 et +": 58, "5 à 19": 400, "1 à 4": 426, "0": 322}
    print(f"{'décos dans 25 km':<18} {'stations':>9} {'attendu 02/08':>14} "
          f"{'cadence':>9} {'cycles/j':>9}")
    print("─" * 66)
    total = 0
    for seuil, lib, mn in PALIERS:
        ids = groupes.get((lib, mn), [])
        total += len(ids)
        ecart = "" if attendu.get(lib) == len(ids) else "  ⚠️ écart"
        print(f"{lib:<18} {len(ids):>9,} {attendu.get(lib, '—'):>14} "
              f"{mn:>7} min {1440 // mn:>9,}{ecart}")
    print("─" * 66)
    print(f"{'TOTAL':<18} {total:>9,} {sum(attendu.values()):>14}")

    # ── Ce que ça coûte, avant et après ──────────────────────────────
    # Convention : le nombre de relevés RENVOYÉS croît au fil de la
    # journée (la requête porte sur la journée écoulée). Sur un cycle
    # tiré au hasard dans la journée, l'espérance vaut la MOITIÉ d'une
    # journée pleine. C'est cette moyenne qu'on utilise ici — et c'est
    # une correction de la note du 03/08 (nuit), qui extrapolait le
    # débit de 16h40 à toutes les heures et surestimait donc d'environ
    # 1,7×.
    moy_releves = RELEVES_JOUR_PLEIN / 2

    def cout(repartition):
        req = lignes = 0
        for (lib, mn), ids in repartition.items():
            cycles = 1440 // max(mn, PLANCHER_MIN)
            req += math.ceil(len(ids) / LOT) * cycles
            lignes += len(ids) * cycles * moy_releves
        return req, lignes

    avant = {("tout le parc", 15): [s[0] for s in stations]}
    req_av, lig_av = cout(avant)
    req_ap, lig_ap = cout(groupes)

    print("\n── Charge chez Infoclimat ───────────────────────────────")
    print(f"{'':<26} {'requêtes/jour':>14} {'lignes lues/jour':>18}")
    print("─" * 62)
    print(f"{'aujourd’hui (15 min)':<26} {req_av:>14,} {lig_av:>18,.0f}")
    print(f"{'paliers par densité':<26} {req_ap:>14,} {lig_ap:>18,.0f}")
    print(f"{'facteur':<26} {req_av / max(req_ap, 1):>13.2f}× "
          f"{lig_av / max(lig_ap, 1):>17.2f}×")
    print(f"\n   Réellement utilisées : {total * 1440 // 10:,} au grand "
          f"maximum (une valeur par station et par cycle).")

    # ── Le détail qui surprend ───────────────────────────────────────
    print("\n── Ce que le classement révèle ──────────────────────────")
    sans = len(groupes.get(("0", 60), []))
    print(f"   {total - sans:,} stations sur {total:,} "
          f"({100 * (total - sans) / total:.0f} %) ont au moins un déco "
          f"dans 25 km.")
    print("   « Se limiter aux zones de vol » ne filtre donc presque rien —")
    print("   c'est bien la CADENCE le levier, pas la sélection géographique.")

    rapide = groupes.get(("20 et +", 10), [])
    if rapide:
        part = 100 * len(rapide) / total
        cycles_rapide = len(rapide) * (1440 // 10)
        cycles_tot = sum(len(v) * (1440 // mn)
                         for (lib, mn), v in groupes.items())
        print(f"\n   Le palier 10 min ne pèse que {part:.1f} % des stations "
              f"mais {100 * cycles_rapide / cycles_tot:.0f} % des relevés.")
        print("   ⚠️ C'est là que se joue le plafond quotidien d'appels :")
        print("      un palier rapide qui déborde coûte plus que tous les")
        print("      autres réunis.")

    # ── Variantes : le facteur ~2× suffit-il ? ───────────────────────
    # Les paliers du 02/08 avaient été arbitrés en supposant qu'ils
    # s'ajoutaient à un gain de 60× sur la fenêtre. Ce gain n'existe pas.
    # Seuls, ils rendent moins de 2× — d'où ce comparatif, qui simule la
    # journée MINUTE PAR MINUTE et regroupe en lots les stations dues au
    # même instant (toutes cadences confondues). C'est la seule façon
    # honnête de compter les requêtes : par palier, on paie des lots
    # incomplets (394 stations = 4 lots dont un à 94 % de vide).
    def simuler(paliers_min, exclure_sans_vent=0.0):
        """Renvoie (requêtes/jour, lignes lues/jour)."""
        cadence = {}
        for sid, *_ in stations:
            lib, _mn = palier_de(compte[sid])
            cadence[sid] = max(paliers_min[lib], PLANCHER_MIN)
        # Rétrogradation des stations sans anémomètre : on ne sait pas
        # LESQUELLES avant de les avoir pollées, mais on en connaît la
        # PART (26 % sans aucun relevé le 03/08). Modélisé en passant
        # cette fraction des paliers rapides au palier le plus lent.
        if exclure_sans_vent:
            rapides = sorted([s for s in cadence if cadence[s] < 60],
                             key=lambda s: (cadence[s], s))
            for s in rapides[:int(len(rapides) * exclure_sans_vent)]:
                cadence[s] = max(paliers_min.values())
        req = 0
        stations_cycles = 0
        for minute in range(1440):
            dues = [s for s, mn in cadence.items() if minute % mn == 0]
            if not dues:
                continue
            req += math.ceil(len(dues) / LOT)
            stations_cycles += len(dues)
        return req, stations_cycles * moy_releves

    print("\n── Et si ~2× ne suffit pas ? ────────────────────────────")
    print("   (journée simulée minute par minute, lots mutualisés entre")
    print("    paliers — c'est ainsi que le poller devra grouper)")
    variantes = [
        ("aujourd'hui — 15 min partout",
         {"20 et +": 15, "5 à 19": 15, "1 à 4": 15, "0": 15}, 0.0),
        ("paliers 02/08 — 10/20/40/60",
         {"20 et +": 10, "5 à 19": 20, "1 à 4": 40, "0": 60}, 0.0),
        ("écartés — 10/30/60/180",
         {"20 et +": 10, "5 à 19": 30, "1 à 4": 60, "0": 180}, 0.0),
        ("écartés + sans-vent rétrogradées",
         {"20 et +": 10, "5 à 19": 30, "1 à 4": 60, "0": 180}, 0.26),
        ("sobres — 15/45/90/240",
         {"20 et +": 15, "5 à 19": 45, "1 à 4": 90, "0": 240}, 0.26),
    ]
    base = None
    print(f"\n{'variante':<36} {'req/jour':>9} {'lignes/jour':>13} "
          f"{'gain':>7}")
    print("─" * 70)
    for libelle, paliers, frac in variantes:
        r, l = simuler(paliers, frac)
        if base is None:
            base = l
        print(f"{libelle:<36} {r:>9,} {l:>13,.0f} {base / max(l, 1):>6.1f}×")
    print("\n   ⚠️ Le palier des 323 stations SANS déco proche pèse lourd")
    print("      pour un service qui n'est ni du vent local ni du direct :")
    print("      elles servent à voir venir fronts et foehn, un signal")
    print("      synoptique qui ne bouge pas en 60 min. Les passer à 180")
    print("      ou 240 min ne dégrade rien de perceptible.")

    # ── Sortie machine, pour revue seulement ─────────────────────────
    dest = os.path.join(ICI, 'cadence_infoclimat.json')
    with open(dest, 'w', encoding='utf-8') as f:
        json.dump({
            "genere_le": "2026-08-03",
            "rayon_km": RAYON_KM,
            "avertissement": ("Fichier de REVUE, pas source de vérité. Le "
                              "poller recalcule au démarrage depuis le "
                              "GeoJSON du jour."),
            "paliers_min": {lib: mn for _s, lib, mn in PALIERS},
            "stations": {sid: {"decos_25km": compte[sid],
                               "cadence_min": palier_de(compte[sid])[1]}
                         for sid, *_ in stations},
        }, f, ensure_ascii=False, indent=1)
    print(f"\n   Détail par station écrit dans {os.path.relpath(dest)}")
    print("   (revue uniquement — le poller RECALCULE, cf. l'en-tête).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
