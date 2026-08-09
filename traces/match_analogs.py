#!/usr/bin/env python3
"""
match_analogs.py — Étape 3 v1 (matching k plus proches + aperçu)

Implémente le matching FIGÉ à l'étape 2 (ETAPE2_SCHEMAS_FEATURES.md §4) :
distance pondérée par échelles physiques fixes (pas de normalisation
statistique par corpus), seuil de vent faible qui désactive le poids
direction, k affiché = k réel.

C'est la "pré-étape 5 gratuite" du plan (session Cowork 24/07/2026) :
comparer la météo d'AUJOURD'HUI (forecast live) au corpus historique
déjà collecté (day_features.jsonl), et montrer à Yann les journées
trouvées — validation à l'œil AVANT même d'avoir une seule polyligne.

⚠️ Corpus encore minuscule (échantillon de session, pas un backfill —
cf. fetch_syride.py/fetch_dhvxc.py) : les résultats illustrent le
MÉCANISME, pas encore une vraie couverture. Le filtre ±60 jours
calendaires (H3) est appliqué mais élargi automatiquement si le corpus
filtré est vide (message explicite), pour rester utile même en été 1.

Usage : python3 match_analogs.py --site aussois_bellecote
        python3 match_analogs.py --site aussois_bellecote --date 2026-05-25
"""

import argparse
import json
import math
import urllib.parse
import urllib.request
from datetime import date as ddate
from pathlib import Path
from statistics import median

from day_features import SITES, _pressure_level_for_alt, _window_indices, UA

CACHE_DIR = Path(__file__).parent / "traces_cache"
LIVE_URL = "https://api.open-meteo.com/v1/forecast"

# Poids et échelles FIGÉS (ETAPE2_SCHEMAS_FEATURES.md §4).
FEATURES = [
    # (clé, échelle, poids, circulaire?)
    ("vent_crete_dir_deg", 30, 3.0, True),
    ("vent_crete_force_kmh", 8, 2.0, False),
    ("vent_crete_raf_kmh", 10, 1.0, False),
    ("blh_max_m", 500, 1.5, False),
    ("cape_max_jkg", 300, 1.0, False),
    ("nuages_mh_pct", 25, 1.0, False),
]
VENT_FAIBLE_KMH = 6
DIST_MAX_SIGMA = 3
# Seuil sur la distance NORMALISÉE (30/07/2026, cf. distance() ci-dessous
# et CONCEPTION_MATCHING_METEO_30-07.md §4.2). Ce n'est PAS un
# relâchement : l'ancien seuil 2,5 portait sur une somme non divisée, de
# poids total Σw = 9,5 ; 2,5/√9,5 = 0,81. Les résultats des tests du 24
# et du 26/07 restent donc valables tels quels.
D_SEUIL = 0.8
K_MAX = 10
# Couverture minimale : une journée dont les features présentes pèsent
# moins de 60 % de Σw est écartée, pas comparée sur des restes.
COUVERTURE_MIN = 0.6


import os as _os                                          # noqa: E402
import sys as _sys                                        # noqa: E402

_TOOLS = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                       "..", "tools")
if _TOOLS not in _sys.path:
    _sys.path.insert(0, _TOOLS)
try:
    from quota_openmeteo import Budget as _Budget, poids_url as _poids_url
    BUDGET = _Budget("match_analogs")
except Exception as _exc:                                 # noqa: BLE001
    print(f"  ⓘ budget Open-Meteo indisponible ({_exc}) — sans comptage partagé")
    BUDGET = None


def fetch_today_features(site_slug: str) -> dict:
    """Features du jour J depuis la prévision LIVE (pas l'archive —
    aujourd'hui n'y est pas encore). Même fenêtre/logique que
    day_features.fetch_day_features, dupliqué ici volontairement court
    (le vrai pipeline ferait un seul module partagé, cf. remarque §5
    du doc étape 2 sur la duplication assumée mais fragile)."""
    cfg = SITES[site_slug]
    level = _pressure_level_for_alt(cfg["alt_deco_m"])
    hf_vars = f"wind_speed_{level}hPa,wind_direction_{level}hPa,cape,cloud_cover_mid,cloud_cover_high,boundary_layer_height"
    params = urllib.parse.urlencode({
        "latitude": cfg["lat"], "longitude": cfg["lon"],
        "forecast_days": 1, "past_days": 0,
        "hourly": hf_vars, "models": "meteofrance_seamless", "timezone": "UTC",
    })
    # ── budget Open-Meteo partagé (09/08/2026) ────────────────────
    # ⚠️ CE SCRIPT N'EST DANS AUCUN TIMER : il se lance à la main, et
    # c'est précisément le scénario de la prochaine panne. Le plafond
    # est par ADRESSE IP ; lancé pendant la collecte de 05:15, il
    # mangerait la fenêtre horaire de la nuit sans laisser de trace
    # exploitable. Le compteur partagé, lui, le nomme.
    _url = f"{LIVE_URL}?{params}"
    if BUDGET is not None:
        BUDGET.demander(_poids_url(_url))
    req = urllib.request.Request(_url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode("utf-8"))
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    idx = _window_indices(times)
    speeds = [hourly[f"wind_speed_{level}hPa"][i] for i in idx if hourly.get(f"wind_speed_{level}hPa", [None]*len(times))[i] is not None]
    dirs = [hourly[f"wind_direction_{level}hPa"][i] for i in idx if hourly.get(f"wind_direction_{level}hPa", [None]*len(times))[i] is not None]
    capes = [hourly["cape"][i] for i in idx if hourly.get("cape", [None]*len(times))[i] is not None]
    mid = [hourly["cloud_cover_mid"][i] for i in idx if hourly.get("cloud_cover_mid", [None]*len(times))[i] is not None]
    high = [hourly["cloud_cover_high"][i] for i in idx if hourly.get("cloud_cover_high", [None]*len(times))[i] is not None]
    blh = [hourly["boundary_layer_height"][i] for i in idx if hourly.get("boundary_layer_height", [None]*len(times))[i] is not None]
    u = sum(-s * math.sin(math.radians(d)) for s, d in zip(speeds, dirs)) / len(speeds)
    v = sum(-s * math.cos(math.radians(d)) for s, d in zip(speeds, dirs)) / len(speeds)
    return {
        "vent_crete_dir_deg": (math.degrees(math.atan2(-u, -v)) + 360) % 360,
        "vent_crete_force_kmh": math.hypot(u, v),
        "vent_crete_raf_kmh": max(speeds) if speeds else None,
        "blh_max_m": max(blh) if blh else None,  # NB : AROME live, pas ERA5 ici (cf. H5, biais assumé)
        "cape_max_jkg": max(capes) if capes else None,
        "nuages_mh_pct": (sum(mid)/len(mid) + sum(high)/len(high)) / 2 if mid and high else None,
    }


def _ang_diff(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def distance(day_j: dict, day_i: dict):
    """Distance pondérée NORMALISÉE par le poids réellement utilisé.

    ⚠️ CORRIGÉ LE 30/07/2026 — l'ancienne version sommait sans diviser.
    Ignorer une feature absente (`continue`) est le bon comportement,
    mais sans renormalisation la somme d'une journée incomplète est
    mécaniquement plus faible : cette journée obtenait donc un MEILLEUR
    rang qu'une journée complète tout aussi ressemblante. Invisible
    jusqu'ici parce que blh manquait partout à la fois (jour J compris),
    mordant dès que blh marchera au jour J — les journées récentes que
    ERA5 n'a pas encore couvertes seraient devenues les « meilleurs
    analogues » du corpus. Consigné dans « Analyse de vol/DEBUG.md ».

    Renvoie (D, couverture) : D ∈ [0 ; DIST_MAX_SIGMA], couverture =
    part de Σw effectivement disponible sur cette journée.
    """
    weak_wind = (day_j.get("vent_crete_force_kmh") or 0) < VENT_FAIBLE_KMH and \
                (day_i.get("vent_crete_force_kmh") or 0) < VENT_FAIBLE_KMH
    total, used_w, all_w = 0.0, 0.0, 0.0
    for key, scale, weight, circular in FEATURES:
        if key == "vent_crete_dir_deg" and weak_wind:
            weight = 1.0
        all_w += weight
        vj, vi = day_j.get(key), day_i.get(key)
        if vj is None or vi is None:
            continue  # feature absente ce jour-là : ignorée, mais plus « gratuite »
        d = _ang_diff(vj, vi) if circular else abs(vj - vi)
        total += weight * min(d / scale, DIST_MAX_SIGMA) ** 2
        used_w += weight
    if used_w <= 0:
        return DIST_MAX_SIGMA, 0.0
    return math.sqrt(total / used_w), used_w / all_w


def match_pct(d: float) -> float:
    """% de match — noyau gaussien exp(−½ D²), cf. §4.3 du doc de
    conception. D = 0,80 (le seuil) ↔ 72 %."""
    return 100 * math.exp(-0.5 * d * d)


def load_corpus(site_slug: str) -> list:
    path = CACHE_DIR / "day_features.jsonl"
    out = []
    with open(path) as f:
        for line in f:
            row = json.loads(line)
            if row["site_id"] == site_slug:
                out.append(row)
    return out


def load_flight_stats(site_slug: str) -> dict:
    """date -> liste des vols ce jour-là (dist_km, duree_min), toutes
    sources confondues déjà collectées pour ce site."""
    stats = {}
    for path in CACHE_DIR.glob("*.jsonl"):
        if path.name == "day_features.jsonl":
            continue
        with open(path) as f:
            for line in f:
                row = json.loads(line)
                if row.get("site_id") == site_slug:
                    stats.setdefault(row["date"], []).append(row)
    return stats


def within_season_window(date_str: str, target: ddate, days: int = 60) -> bool:
    d = ddate.fromisoformat(date_str)
    # Distance calendaire ±60j (H3), en ignorant l'année.
    # `replace(year=...)` lève ValueError sur un 29 février reporté dans
    # une année non bissextile — une seule date du corpus suffisait à
    # faire planter tout le matching (jamais rencontré : le corpus n'a
    # pas encore de 29/02, ce qui changera avec le backfill complet).
    try:
        this_year = d.replace(year=target.year)
    except ValueError:
        this_year = d.replace(year=target.year, day=28)
    delta = abs((this_year - target).days)
    delta = min(delta, 365 - delta)
    return delta <= days


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", choices=list(SITES), required=True)
    ap.add_argument("--date", default=None, help="ISO, défaut = aujourd'hui")
    args = ap.parse_args()

    target_date = ddate.fromisoformat(args.date) if args.date else ddate.today()
    print(f"== Journées analogues — {args.site}, jour cible {target_date.isoformat()} ==\n")

    today_feat = fetch_today_features(args.site)
    print("Features du jour cible :")
    for k, *_ in FEATURES:
        v = today_feat.get(k)
        print(f"  {k:<24} {v if v is None else round(v, 1)}")
    print()

    corpus = load_corpus(args.site)
    seasonal = [d for d in corpus if within_season_window(d["date"], target_date)]
    pool, pool_label = (seasonal, "±60 j calendaires") if seasonal else (corpus, "TOUT le corpus (fenêtre saisonnière vide)")
    print(f"Corpus : {len(corpus)} journées connues, {len(pool)} dans la fenêtre {pool_label}\n")

    # Journées trop incomplètes écartées AVANT le tri : les comparer sur
    # des restes reviendrait à les faire concourir avec un handicap
    # positif (cf. distance(), correction du 30/07).
    scored = []
    ecartees = 0
    for d in pool:
        dist, cov = distance(today_feat, d)
        if cov < COUVERTURE_MIN:
            ecartees += 1
            continue
        scored.append((dist, cov, d))
    scored.sort(key=lambda x: x[0])
    if ecartees:
        print(f"({ecartees} journée(s) écartée(s) : couverture < {COUVERTURE_MIN:.0%})")

    matches = [(dist, cov, d) for dist, cov, d in scored if dist <= D_SEUIL][:K_MAX]
    if not matches:
        print(f"0 journée sous le seuil D ≤ {D_SEUIL} ({match_pct(D_SEUIL):.0f} %) — "
              "élargissement aux 3 plus proches (INDICATIF, ne pas afficher tel quel) :")
        matches = scored[:3]

    print(f"{len(matches)} journée(s) comparable(s) trouvée(s) :\n")
    flight_stats = load_flight_stats(args.site)
    all_dists, all_durs = [], []
    for dist, cov, d in matches:
        flights = flight_stats.get(d["date"], [])
        dists = [f["dist_km"] for f in flights if f.get("dist_km") is not None]
        durs = [f["duree_min"] for f in flights if f.get("duree_min") is not None]
        all_dists += dists
        all_durs += durs
        print(f"  {d['date']}  {match_pct(dist):>3.0f}% (D {dist:.2f}, couv. {cov:.0%})  "
              f"vent {d['vent_crete_dir_deg']:>3.0f}°/{d['vent_crete_force_kmh']:.0f}km/h  "
              f"cape {d['cape_max_jkg']}  blh {d['blh_max_m']}  nuages {d['nuages_mh_pct']}%  "
              f"-> {len(flights)} vol(s) connu(s)"
              + (f", dist {dists}" if dists else ""))

    print()
    if all_dists:
        print(f"Percentiles distance sur les journées analogues ({len(all_dists)} vols) : "
              f"médiane {median(all_dists):.0f} km")
    else:
        print("Aucun vol connu sur ces journées analogues dans le corpus déjà collecté "
              "(normal avec un échantillon de session, pas un backfill).")
