#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/front_altitude.py — étape 10 du lot H : donner au détecteur de
#  front la MÊME entrée à deux niveaux différents      (10/08/2026)
#
#  ⛔ CE FICHIER NE DÉTECTE RIEN. Le détecteur est `gust-front.js`
#  (`gfDetectModel`), et il n'est PAS réécrit : toute l'étape 10 consiste
#  à lui donner la même grille à 10 m puis à 1 000 m/sol et à comparer ce
#  qu'il en fait. Réimplémenter le fit ici donnerait deux détecteurs qui
#  divergeraient — c'est le défaut déjà payé DEUX FOIS le 10/08 (la sonde
#  de purge, puis la sonde de vent, l'une et l'autre ayant recopié une
#  logique au lieu de l'appeler).
#
#  ── CE QUE CETTE ÉTAPE PEUT MESURER, ET CE QU'ELLE NE PEUT PAS ───────
#  ⚠️ Le détecteur de production tourne sur la FRANCE ENTIÈRE à 0,25°
#  (2 709 points, 24 échéances). Le produit B ne couvre que le domaine
#  Nord-Alpes — 165 × 165 km à 0,025°, 5 185 colonnes. Un R² mesuré ici
#  n'est donc PAS comparable au R² ≈ 0,17-0,19 du 09/08 : ni la même
#  emprise, ni la même variance en temps (un front traverse ce domaine en
#  ~3 h, soit 3 échéances horaires, contre ~8 h sur la France).
#  **Ce qui est comparable, et c'est le seul objet du fichier, c'est
#  10 m CONTRE 1 000 m sur les mêmes points, le même run, les mêmes
#  échéances et le même détecteur.**
#
#  ⛔ LA RAFALE N'EXISTE QU'À 10 m, partout — mesuré, et c'est ce qui
#  rend « rejouer le détecteur sans y toucher » impossible au sens
#  strict : `gfDetectModel` écarte tout point dont la rafale prévue est
#  sous 45 km/h. On branche donc le verrou sur la rafale de SURFACE (la
#  signature du front au sol reste la même quel que soit le niveau où on
#  regarde le vent), et le rejeu publie les DEUX variantes, avec et sans
#  verrou : un résultat qui dépendrait du verrou ne dirait rien du niveau.
#  ⚠️ Cette rafale vient de la grille de production à 0,25° : UNE valeur
#  de rafale pour ~121 colonnes du produit B. C'est écrit dans la sortie
#  (`surface.note`), pas caché.
#
#  ── DEUX GARDE-FOUS PLUTÔT QUE DE LA VIGILANCE ───────────────────────
#  Les formules vitesse/direction sont recopiées de
#  `arome-gustfront/ingest.py` (qui importe eccodes au chargement, donc
#  n'est pas importable sans GRIB). Une recopie est une dette : elle est
#  tenue par `test_front_altitude.py`, qui fige la convention, et par
#  `--parite`, qui confronte la grille 10 m fabriquée ici à celle que la
#  production a écrite pour le MÊME run — mêmes octets sources, donc tout
#  écart y est une faute de conversion ou d'indice, pas une donnée.
#
#  Usage :
#      python3 agrume/front_altitude.py --niveaux 10 1000 --sortie /tmp/lot10
#      python3 agrume/front_altitude.py --niveaux 10 --parite
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

import numpy as np

# Le bucket public des grilles — le même que celui du calque vent et de
# la chaîne `arome-gustfront`. ⓘ Aucun secret ici : le produit B est
# lisible sans jeton, c'est ce qui rend ce rejeu reproductible depuis
# n'importe quelle machine.
BASE_PUBLIQUE = "https://pub-7a401bae4fe54a6c8dbdd6b5a33a7bec.r2.dev"
CLE_INDEX = "agrume/grille/index.json"
CLE_SURFACE = "arome/gustfront/grid.json"

# Les champs que `gfDetectModel` lit dans `vars`. `spd` et `dir` sont
# BLOQUANTS (ils décident du passage) ; `gust` est bloquant aussi, mais
# c'est un seuil ; `pres`, `temp`, `cape` et `precip` ne le sont pas —
# ils renseignent la confiance et le typage outflow/synoptique.
CHAMPS_SURFACE = ("gust", "pres", "cape", "precip", "temp")


# ══════════════════════════════════════════════════════════════════════
#  Lecture des deux sources
# ══════════════════════════════════════════════════════════════════════
def _lire(url, timeout=180):
    req = urllib.request.Request(
        url, headers={"User-Agent": "balise-watch-agrume-front-altitude/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _lire_json_local_ou_http(base, cle):
    if base.startswith("http://") or base.startswith("https://"):
        return json.loads(_lire(f"{base}/{cle}"))
    with open(os.path.join(base, cle), "rb") as f:
        return json.loads(f.read())


def _lire_octets(base, cle):
    if base.startswith("http://") or base.startswith("https://"):
        return _lire(f"{base}/{cle}")
    with open(os.path.join(base, cle), "rb") as f:
        return f.read()


def dernier_run(base, domaine="nord-alpes"):
    """Le run le plus récent DÉCLARÉ PAR L'INDEX, jamais deviné.

    ⚠️ Le produit B ne garde que trois runs et n'autorise pas
    `ListObjects` (Class A, refusé par `storage.py`). L'index à clé fixe
    est donc la seule source de vérité sur ce qui est en ligne : demander
    un run absent rendrait un 404, mais demander « le dernier » en le
    calculant depuis l'heure courante rendrait un 404 SILENCIEUX un jour
    où un run aurait sauté.

    ⚠️ 13/08 (audit) : l'index porte DEUX domaines depuis l'étape 11 —
    prendre `runs[0]` sans filtrer pouvait rendre un run des Pyrénées à
    un rejeu qui croyait lire les Alpes.
    """
    idx = _lire_json_local_ou_http(base, CLE_INDEX)
    runs = [e for e in (idx.get("runs") or [])
            if e.get("domaine", "nord-alpes") == domaine]
    if not runs:
        raise SystemExit(f"index du produit B : aucun run en ligne pour le "
                         f"domaine {domaine}")
    return runs[0]["run"], idx


def charger_produit_b(base, run, domaine="nord-alpes"):
    """⛔ RÉÉCRIT LE 13/08 (audit) : ce lecteur demandait encore
    `agrume/grille/{run}/grille.npz` — clé de l'avant-étape 11, sans
    domaine, format qui n'est plus jamais écrit sur R2. 404 à chaque
    rejeu, pendant deux lots, et la CI ne couvrait que `construire()`.

    La route est désormais celle des objets PUBLIÉS (manifeste + tampons
    d'échéance + zsol), reconstruits par `Grille.depuis_tampons()` —
    bancée par `test_grille.py` §11. Rend `(man, npz_like)` où
    `npz_like` porte les quatre clés que `construire()` lit :
    `h0025`, `lats`, `lons`, `echeances`.

    ⓘ Coût : un GET par échéance (~1,3 Mo pièce, jusqu'à 52) là où le
    npz d'avant tirait ~32 Mo d'un coup — même ordre de grandeur, et
    c'est un outil de rejeu, pas un chemin chaud.
    """
    from grille import Grille                              # noqa: PLC0415
    man = _lire_json_local_ou_http(
        base, f"agrume/grille/{domaine}/{run}/manifest.json")
    svc = man["service"]
    tampons = {s: _lire_octets(base, svc["cle_echeance"].format(
        domaine=domaine, run=run, step=s)) for s in man["echeances"]}
    zsol = _lire_octets(base, svc["cle_zsol"].format(
        domaine=domaine, run=run))
    g = Grille.depuis_tampons(man, tampons, zsol)
    return man, {"h0025": g.h0025, "lats": g.lats, "lons": g.lons,
                 "echeances": g.steps}


def charger_surface(base):
    return _lire_json_local_ou_http(base, CLE_SURFACE)


# ══════════════════════════════════════════════════════════════════════
#  La convention de vent — recopiée, donc épinglée
# ══════════════════════════════════════════════════════════════════════
def vent_kmh_dir(u, v):
    """(u, v) en m/s → (vitesse km/h entière, direction D'OÙ VIENT le vent).

    ⚠️ Formules identiques à `arome-gustfront/ingest.py`, arrondis
    compris. L'arrondi n'est pas cosmétique : le détecteur compare un
    saut de vent à un seuil de 15 km/h et une bascule à 40°. Arrondir
    d'un côté et pas de l'autre suffirait à faire basculer des points
    juste au seuil, et l'écart passerait pour un effet du niveau.

    ⓘ `atan2(-u, -v)` et non `atan2(v, u)` : convention MÉTÉO (direction
    d'où vient le vent), la même que Pioupiou et Météo-France. Prendre
    l'autre donnerait des directions plausibles à 180° près — et une
    bascule de 40° resterait une bascule de 40°, donc rien ne crierait.
    """
    if u is None or v is None:
        return None, None
    return (round(math.hypot(u, v) * 3.6),
            round((math.degrees(math.atan2(-u, -v)) + 360) % 360))


def _plus_proche(axe, valeur, demi_pas):
    """Indice du point le plus proche, ou None s'il est trop loin.

    ⚠️ Sans la borne, `argmin` rendrait TOUJOURS un indice — celui du
    bord de la grille pour un point situé à 300 km au large. Le détecteur
    lirait alors une rafale prise ailleurs, sans qu'aucune exception ne
    se lève : exactement le mode de panne silencieuse que ce projet
    cherche partout.
    """
    k = int(np.abs(axe - valeur).argmin())
    return k if abs(float(axe[k]) - valeur) <= demi_pas else None


# ══════════════════════════════════════════════════════════════════════
#  La grille, au format exact que le détecteur attend
# ══════════════════════════════════════════════════════════════════════
def construire(man, npz, surface, niveau):
    """Produit B + grille de surface → une grille au format `gfDetectModel`.

    Format attendu par le détecteur (cf. `gust-front.js`) :
        { lats, lons, times, vars: { spd, dir, gust, pres, cape, precip, temp } }
    chaque `vars.X[echeance][k]` avec `k = iLat * len(lons) + iLon`.
    """
    run = man["run"]
    niveaux = list(man["niveaux_m_sol"])
    if niveau not in niveaux:
        raise SystemExit(
            f"niveau {niveau} m/sol absent du produit B. Disponibles : {niveaux}")
    noms = [p["nom"] for p in man["parametres"]]
    for quoi in ("u", "v"):
        if quoi not in noms:
            raise SystemExit(f"le produit B ne porte pas « {quoi} » : {noms}")
    iu, iv, kniv = noms.index("u"), noms.index("v"), niveaux.index(niveau)

    h = npz["h0025"]
    lats = np.asarray(npz["lats"], dtype=np.float64)
    lons = np.asarray(npz["lons"], dtype=np.float64)
    ech = [int(e) for e in npz["echeances"]]

    # ⚠️ L'ÉCHÉANCE 0 EST ÉCARTÉE, et ce n'est pas une question de forme.
    # La chaîne de production ne la publie pas (`0 < s <= MAX_HOURS` dans
    # `arome-gustfront/ingest.py`), et `gfDetectModel` démarre son
    # balayage à l'indice 3 en regardant les TROIS précédents. La garder
    # décalerait d'une heure toute la fenêtre de référence par rapport à
    # la production : la grille d'altitude ne serait plus jouable contre
    # la grille de surface, sans que rien ne le signale.
    garder = [i for i, e in enumerate(ech) if e >= 1]
    if not garder:
        raise SystemExit("aucune échéance ≥ 1 h dans le produit B")

    # Le produit B range ses latitudes du NORD au SUD (`jScansPositively
    # = 0` sur AROME) ; la grille de production les range du sud au nord.
    # On trie plutôt que de retourner : un `[::-1]` suppose le sens, un
    # `argsort` le constate. L'index plat a alors le même sens des deux
    # côtés — sinon le détecteur lirait des latitudes justes sur des vents
    # pris ailleurs, et aucune exception ne se lèverait.
    ordre = np.argsort(lats)
    lats_c = lats[ordre]
    u = np.asarray(h[iu, kniv], dtype=np.float32)[garder][:, ordre, :]
    v = np.asarray(h[iv, kniv], dtype=np.float32)[garder][:, ordre, :]
    nj, ni = len(lats_c), len(lons)

    t0 = datetime.strptime(run, "%Y-%m-%dT%H:00:00Z").replace(tzinfo=timezone.utc)
    times = [(t0 + timedelta(hours=ech[i])).strftime("%Y-%m-%dT%H:%M:%SZ")
             for i in garder]

    # ── Le raccord vers la grille de surface ──────────────────────────
    # ⓘ L'alignement se fait sur l'HEURE VALIDE, pas sur l'indice
    # d'échéance : les deux chaînes ne choisissent pas forcément le même
    # run (chacune prend celui dont la couverture est la plus complète).
    # Aligner par indice collerait un +3 h sur un +6 h le jour où elles
    # divergeraient, silencieusement.
    s_lats = np.asarray(surface["lats"], dtype=np.float64)
    s_lons = np.asarray(surface["lons"], dtype=np.float64)
    s_nlon = len(s_lons)
    s_pas = float(surface.get("stepDeg") or 0.25)
    s_index_temps = {t: k for k, t in enumerate(surface["times"])}
    jj = [_plus_proche(s_lats, float(la), s_pas / 2 + 1e-6) for la in lats_c]
    ii = [_plus_proche(s_lons, float(lo), s_pas / 2 + 1e-6) for lo in lons]
    plat_surface = [None if (jj[j] is None or ii[i] is None)
                    else jj[j] * s_nlon + ii[i]
                    for j in range(nj) for i in range(ni)]

    vars_ = {n: [] for n in ("spd", "dir") + CHAMPS_SURFACE}
    nan_vus = 0
    for si, t in enumerate(times):
        spd_l, dir_l = [], []
        for j in range(nj):
            for i in range(ni):
                uu, vv = float(u[si, j, i]), float(v[si, j, i])
                if math.isnan(uu) or math.isnan(vv):
                    # ⚠️ `None`, jamais 0 : un trou vaut « je ne sais pas »
                    # et le détecteur l'écarte. Un 0 serait un calme plat
                    # parfaitement crédible, et il abaisserait la médiane
                    # de la fenêtre de référence — donc il FABRIQUERAIT
                    # des sauts de vent.
                    spd_l.append(None)
                    dir_l.append(None)
                    nan_vus += 1
                else:
                    s, d = vent_kmh_dir(uu, vv)
                    spd_l.append(s)
                    dir_l.append(d)
        vars_["spd"].append(spd_l)
        vars_["dir"].append(dir_l)

        ks = s_index_temps.get(t)
        for nom in CHAMPS_SURFACE:
            col = surface["vars"][nom][ks] if ks is not None else None
            vars_[nom].append([None if (col is None or p is None) else col[p]
                               for p in plat_surface])

    couverture = sum(1 for p in plat_surface if p is not None) / max(1, len(plat_surface))
    heures_communes = sum(1 for t in times if t in s_index_temps)
    return {
        "produit": "AGRUME étape 10 — grille au format du détecteur de front",
        "run": run,
        "niveau_m_sol": niveau,
        "stepDeg": 0.025,
        "lats": [round(float(x), 4) for x in lats_c],
        "lons": [round(float(x), 4) for x in lons],
        "times": times,
        "vars": vars_,
        "surface": {
            "run": surface.get("run"),
            "cle": CLE_SURFACE,
            "stepDeg": s_pas,
            "couverture": round(couverture, 4),
            "heures_communes": heures_communes,
            "note": (
                "rafale, pression, température, CAPE et pluie viennent de la "
                "grille de SURFACE à 0,25° : une valeur pour ~121 colonnes du "
                "produit B. La rafale n'existe qu'à 10 m (mesuré), elle ne "
                "peut donc pas venir du niveau demandé. Seuls `spd` et `dir` "
                "sont au niveau."),
        },
        "trous_vent": nan_vus,
        "avertissement": (
            "Domaine Nord-Alpes seulement (165 × 165 km) : un R² mesuré ici "
            "n'est PAS comparable au R² du détecteur de production, qui "
            "travaille sur la France entière. Seule la comparaison entre deux "
            "niveaux du MÊME fichier a un sens."),
    }


# ══════════════════════════════════════════════════════════════════════
#  La parité — le seul contrôle qui ne repose pas sur ma propre logique
# ══════════════════════════════════════════════════════════════════════
def parite(grille, surface):
    """Confronte la grille 10 m fabriquée ici à celle de la PRODUCTION.

    Aux points où la maille 0,25° de la production tombe exactement sur
    une colonne du produit B, et à échéance égale, les deux grilles
    décrivent le MÊME point du MÊME run : à 10 m, l'une et l'autre
    remontent `10u`/`10v` de la grille 0,01°. Un écart n'y est donc pas
    une différence de donnée, c'est une faute de conversion ou d'indice.

    ⚠️ Un écart de ±1 km/h reste attendu et n'est pas une faute : le
    produit B stocke en float16 et arrondit à l'entier, la production
    arrondit depuis du float64. Ce qui doit être nul, c'est le nombre de
    points en désaccord GROSSIER.
    """
    if int(grille["niveau_m_sol"]) != 10:
        raise SystemExit(
            "la parité ne vaut qu'à 10 m : au-dessus, la production ne porte "
            "rien à comparer (elle est entièrement en champs de surface)")
    if grille["run"] != surface.get("run"):
        print(f"⚠️  runs différents : produit B {grille['run']} contre "
              f"surface {surface.get('run')} — la parité perd son sens, "
              f"les deux grilles ne décrivent plus la même prévision")

    s_lats = list(surface["lats"])
    s_lons = list(surface["lons"])
    s_nlon = len(s_lons)
    s_t = {t: k for k, t in enumerate(surface["times"])}
    paires = []
    for j, la in enumerate(grille["lats"]):
        for i, lo in enumerate(grille["lons"]):
            for sj, sla in enumerate(s_lats):
                if abs(sla - la) > 1e-6:
                    continue
                for si_, slo in enumerate(s_lons):
                    if abs(slo - lo) > 1e-6:
                        continue
                    paires.append((j * len(grille["lons"]) + i,
                                   sj * s_nlon + si_))
    n, dmax_v, dmax_d, gros = 0, 0.0, 0.0, 0
    for k_t, t in enumerate(grille["times"]):
        ks = s_t.get(t)
        if ks is None:
            continue
        for k_a, k_s in paires:
            a_v, a_d = grille["vars"]["spd"][k_t][k_a], grille["vars"]["dir"][k_t][k_a]
            b_v, b_d = surface["vars"]["spd"][ks][k_s], surface["vars"]["dir"][ks][k_s]
            if a_v is None or b_v is None or a_d is None or b_d is None:
                continue
            n += 1
            dv = abs(a_v - b_v)
            dd = abs(((a_d - b_d + 540) % 360) - 180)
            dmax_v, dmax_d = max(dmax_v, dv), max(dmax_d, dd)
            if dv > 2 or dd > 10:
                gros += 1
    return {"points_coincidents": len(paires), "comparaisons": n,
            "ecart_max_kmh": dmax_v, "ecart_max_deg": dmax_d,
            "desaccords_grossiers": gros}


# ══════════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════════
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", default=BASE_PUBLIQUE,
                   help="base publique des grilles, ou un répertoire local")
    p.add_argument("--run", default=None,
                   help="run du produit B (défaut : le plus récent de l'index)")
    p.add_argument("--niveaux", type=int, nargs="+", default=[10, 1000],
                   help="niveaux AGL à sortir, en mètres")
    p.add_argument("--sortie", default=".",
                   help="répertoire où écrire grid-<niveau>m.json")
    p.add_argument("--parite", action="store_true",
                   help="confronte la grille 10 m à celle de la production")
    p.add_argument("--domaine", default="nord-alpes",
                   help="domaine du produit B (défaut : nord-alpes) — le "
                        "domaine fait partie de la clé R2 depuis l'étape 11, "
                        "et l'index porte les deux")
    a = p.parse_args(argv)

    run = a.run
    if run is None:
        run, idx = dernier_run(a.base, domaine=a.domaine)
        print(f"run du produit B : {run}  "
              f"({len(idx.get('runs') or [])} en ligne sur "
              f"{idx.get('retention_runs')} gardés)")
    man, npz = charger_produit_b(a.base, run, domaine=a.domaine)
    surface = charger_surface(a.base)
    print(f"grille de surface : run {surface.get('run')}, "
          f"{len(surface['times'])} échéances, pas {surface.get('stepDeg')}°")

    os.makedirs(a.sortie, exist_ok=True)
    ecrits = []
    for niveau in a.niveaux:
        g = construire(man, npz, surface, niveau)
        chemin = os.path.join(a.sortie, f"grid-{niveau}m.json")
        with open(chemin, "w") as f:
            json.dump(g, f, separators=(",", ":"))
        octets = os.path.getsize(chemin)
        print(f"  {niveau:>5} m/sol → {chemin}  "
              f"({len(g['lats'])}×{len(g['lons'])} points, "
              f"{len(g['times'])} échéances, {octets / 1e6:.1f} Mo, "
              f"{g['trous_vent']} trous de vent, "
              f"rafale sur {g['surface']['couverture'] * 100:.0f} % des points, "
              f"{g['surface']['heures_communes']} heures communes)")
        ecrits.append((niveau, g))

    if a.parite:
        for niveau, g in ecrits:
            if int(niveau) != 10:
                continue
            r = parite(g, surface)
            print(f"\nPARITÉ 10 m contre la grille de production")
            print(f"  points coïncidents      : {r['points_coincidents']}")
            print(f"  comparaisons            : {r['comparaisons']}")
            print(f"  écart max               : {r['ecart_max_kmh']:.0f} km/h, "
                  f"{r['ecart_max_deg']:.0f}°")
            print(f"  désaccords grossiers    : {r['desaccords_grossiers']} "
                  f"(> 2 km/h ou > 10°)")
            if r["comparaisons"] == 0:
                print("  ⛔ AUCUNE comparaison : un contrôle sur zéro point "
                      "rend un ✓ qui ne dit rien")
                return 1
            if r["desaccords_grossiers"]:
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
