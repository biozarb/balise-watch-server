#!/usr/bin/env python3
"""
day_features.py — features météo par site × date (v2, 30/07/2026)

Conception : ../../../Analyse de vol/CONCEPTION_MATCHING_METEO_30-07.md
Schéma d'origine : ETAPE2_SCHEMAS_FEATURES.md §3 (étendu, pas remplacé —
les 6 features figées à l'étape 2 gardent leurs noms, leurs échelles et
leurs poids ; 5 s'ajoutent, cf. §3 du doc de conception).

┌─ CE QUI CHANGE PAR RAPPORT À LA v1 (24/07), ET POURQUOI ────────────┐
│ 1. REQUÊTES PAR PLAGE. Une plage de 92 jours × 12 variables coûte   │
│    1,1 s / 139 Ko (mesuré 30/07). Un backfill complet d'un site     │
│    passe de ~2 130 requêtes à ~24. C'était déjà au TODO.            │
│ 2. TOUTES LES JOURNÉES, pas seulement les dates de vol. La v1 lisait│
│    les dates depuis les vols collectés : le corpus ne contenait donc│
│    aucune journée SANS vol, et « les jours comme aujourd'hui, on a  │
│    volé 11 fois sur 14 » était structurellement incalculable — le   │
│    dénominateur n'existait pas (§6 du doc). Décision Yann 30/07.    │
│ 3. DÉBUT D'ARCHIVE 2023-08-31, pas 2023-12-15. Mesuré : premier     │
│    `wind_speed_700hPa` non-null à 2023-08-30T18:00. +3,5 mois, dont │
│    une saison d'automne entière qui manquait (§0 et §9.1 du doc).   │
│ 4. COORDONNÉES RÉELLES depuis decos.json. Les anciennes étaient     │
│    fausses de 9,7 km pour Saint-Hilaire — sur une maille AROME de   │
│    2,5 km, c'est un autre endroit, pas une approximation (§9.3).    │
│ 5. 5 FEATURES DE PLUS : niveau libre 600 hPa (le RÉGIME, que le vent│
│    crête seul ne distingue pas quand le relief canalise), vent 10 m,│
│    écart T−Td (hauteur de base), ensoleillement, précipitations     │
│    (filtre, pas distance). Toutes sondées le 30/07 en archive ET en │
│    live — condition de comparabilité jour J ↔ historique.           │
└─────────────────────────────────────────────────────────────────────┘

⚠️ PIÈGE MESURÉ (30/07/2026) : Open-Meteo répond
   {"error": true, "reason": "Too many concurrent requests"} — en HTTP
   200, pas en erreur réseau — dès que deux requêtes partent en
   parallèle. C'est la CONCURRENCE qui casse, pas le volume. D'où
   `_get_json` qui teste `error` dans le corps et réessaie une fois, et
   d'où l'absence totale de parallélisme ici. Ne pas « optimiser » ce
   script avec un ThreadPool.

⚠️ Ce fichier reste la SEULE référence du calcul des features côté
   pipeline. Deux copies existent (`match_analogs.fetch_today_features`
   et `PWA/web/src/lib/analogLab.ts`, toutes deux marquées comme telles) :
   toute correction de la fenêtre horaire, du niveau de crête ou d'une
   moyenne vectorielle doit être reportée dans les trois.

Usage :
  python3 day_features.py                      # tous les sites, tout l'historique
  python3 day_features.py --site aussois_bellecote
  python3 day_features.py --start 2026-01-01   # incrément
"""

import argparse
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

UA = "BaliseWatch-traces/0.2 (+argonautes.sim@gmail.com)"
PAUSE_S = 0.4
CACHE_DIR = Path(__file__).parent / "traces_cache"

# Coordonnées RÉELLES, relevées dans PWA/web/public/data/decos.json le
# 30/07/2026 (§9.3 du doc de conception). Les valeurs « à la main » de la
# v1 sont conservées en commentaire : les tests du 24 et du 26/07 ont été
# faits avec elles, leurs chiffres ne sont donc PAS reproductibles ici —
# ils illustraient le mécanisme, pas un résultat.
#   saint_hilaire     : v1 45.22  / 5.885 / 950  → écart 9,7 km
#   montmin_forclaz   : v1 45.83  / 6.27  / 1150 → écart 2,4 km
#   aussois_bellecote : v1 45.22  / 6.75  / 2180 → écart 3,1 km
# ⚠️ À CONFIRMER AVEC YANN : le déco Syride s'appelle « Aussois Angle De
# Bellecote » ; decos.json ne connaît qu'« Aussois », à 3,1 km du point
# v1. À valider avant de figer quoi que ce soit sur ce site.
SITES = {
    "saint_hilaire":     {"lat": 45.3069, "lon": 5.8881, "alt_deco_m": 906,
                          "pge_name": "Saint Hilaire du Touvet"},
    "montmin_forclaz":   {"lat": 45.8142, "lon": 6.2470, "alt_deco_m": 1265,
                          "pge_name": "Montmin (Col de la Forclaz)"},
    "aussois_bellecote": {"lat": 45.2458, "lon": 6.7356, "alt_deco_m": 2102,
                          "pge_name": "Aussois"},
}

# Premier jour ENTIÈREMENT couvert par les niveaux de pression de
# l'archive meteofrance_seamless (mesuré le 30/07/2026 : premier
# wind_speed_700hPa non-null à 2023-08-30T18:00). Les variables de
# surface remontent plus loin — c'est le vent par niveau qui borne.
# Ne pas descendre cette date sans resonder.
ARCHIVE_START = "2023-08-31"
# Conservé pour mémoire : la borne qu'on croyait être la bonne au 24/07.
TIER_A_START_V1 = "2023-12-15"

HF_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
ERA5_URL = "https://archive-api.open-meteo.com/v1/archive"

# 92 j × 12 variables = 1,1 s / 139 Ko (mesuré). Au-delà, rien ne casse
# côté API, mais les réponses deviennent lourdes à garder en mémoire.
CHUNK_DAYS = 92

# Fenêtre 12h-18h locales ≈ 10h-16h UTC (H1, doc étape 2 — hypothèse
# toujours ouverte, manipulable dans le laboratoire admin).
WINDOW_UTC_HOURS = list(range(10, 17))

SURFACE_VARS = [
    "wind_speed_10m", "temperature_2m", "dew_point_2m", "cape",
    "cloud_cover_mid", "cloud_cover_high", "sunshine_duration", "precipitation",
]


def _pressure_level_for_alt(alt_m: float) -> int:
    """Niveau de pression standard le plus proche de alt_deco + 400 m
    (règle H2, doc étape 2), via l'atmosphère standard. Inchangé depuis
    la v1 — `crestLevelHpa` (analogLab.ts) en est le port exact."""
    target_m = alt_m + 400
    p = 1013.25 * (1 - 2.25577e-5 * target_m) ** 5.25588
    levels = [900, 850, 800, 700, 600, 500]
    return min(levels, key=lambda lv: abs(lv - p))


# ── budget Open-Meteo partagé (09/08/2026) ────────────────────────
# ⚠️ CE SCRIPT N'EST DANS AUCUN TIMER, ET C'EST EXACTEMENT POUR ÇA
# QU'IL EST CÂBLÉ ICI. Le plafond Open-Meteo est par ADRESSE IP, et tout
# le VPS en partage une : un lancement à la main pendant la collecte de
# 05:15 mangerait la fenêtre horaire de la nuit, et le journal de la
# collecte ne saurait pas dire d'où vient le trou — il dirait « quelque
# chose a dépassé ». Instrumenter la collecte seule aurait donné un faux
# sentiment de sécurité ; le prochain incident serait venu d'ici.
import os as _os                                          # noqa: E402
import sys as _sys                                        # noqa: E402

_TOOLS = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                       "..", "tools")
if _TOOLS not in _sys.path:
    _sys.path.insert(0, _TOOLS)
try:
    from quota_openmeteo import Budget as _Budget, poids_url as _poids_url
    BUDGET = _Budget("day_features")
except Exception as _exc:                                 # noqa: BLE001
    print(f"  ⓘ budget Open-Meteo indisponible ({_exc}) — sans comptage partagé")
    BUDGET = None


def _get_json(url: str, retry: bool = True):
    """GET + rattrapage du piège de concurrence (cf. en-tête) : l'erreur
    arrive dans le CORPS avec un HTTP 200, un test sur le code de statut
    ne la verrait pas."""
    # Le droit de parler avant de parler. Le poids est lu sur l'URL
    # elle-même : rien à recompter, donc rien à oublier.
    if BUDGET is not None:
        BUDGET.demander(_poids_url(url))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"    réseau : {e}")
        return None
    if data.get("error"):
        reason = str(data.get("reason", ""))
        if retry and "concurrent" in reason.lower():
            time.sleep(2.0)
            return _get_json(url, retry=False)
        print(f"    API : {reason}")
        return None
    return data


def _window_indices(times: list) -> list:
    return [i for i, t in enumerate(times) if int(t[11:13]) in WINDOW_UTC_HOURS]


def _chunks(start: str, end: str):
    a = date.fromisoformat(start)
    z = date.fromisoformat(end)
    while a <= z:
        b = min(a + timedelta(days=CHUNK_DAYS - 1), z)
        yield a.isoformat(), b.isoformat()
        a = b + timedelta(days=1)


def _vector_wind(speeds, dirs):
    """Moyenne VECTORIELLE u/v + rafale. Jamais une moyenne d'angles :
    le piège 359°→1° donnerait 180°, exactement à l'opposé. Même règle
    que WindGridLayer.tsx et que analogLab.ts."""
    pairs = [(s, d) for s, d in zip(speeds, dirs) if s is not None and d is not None]
    if not pairs:
        return None
    u = sum(-s * math.sin(math.radians(d)) for s, d in pairs) / len(pairs)
    v = sum(-s * math.cos(math.radians(d)) for s, d in pairs) / len(pairs)
    return {
        "dir": (math.degrees(math.atan2(-u, -v)) + 360) % 360,
        "force": math.hypot(u, v),
        "raf": max(s for s, _ in pairs),
    }


def _by_day(times, idx):
    out = {}
    for i in idx:
        out.setdefault(times[i][:10], []).append(i)
    return out


def fetch_range(site_slug: str, start: str, end: str) -> list:
    """Toutes les journées de [start, end] pour un site, en 2 requêtes
    (AROME + ERA5). Renvoie une liste de dicts au schéma v2."""
    cfg = SITES[site_slug]
    level = _pressure_level_for_alt(cfg["alt_deco_m"])
    hf_vars = ([f"wind_speed_{level}hPa", f"wind_direction_{level}hPa",
                "wind_speed_600hPa", "wind_direction_600hPa"] + SURFACE_VARS)
    q = urllib.parse.urlencode({
        "latitude": cfg["lat"], "longitude": cfg["lon"],
        "start_date": start, "end_date": end,
        "hourly": ",".join(hf_vars), "models": "meteofrance_seamless",
        "timezone": "UTC",
    })
    hf = _get_json(f"{HF_URL}?{q}")
    if not hf or "hourly" not in hf:
        return []
    hourly = hf["hourly"]
    times = hourly.get("time", [])
    idx = _window_indices(times)
    if not idx:
        return []

    # zᵢ : ERA5 est la SEULE archive qui l'expose (sonde du 24/07,
    # reconfirmée le 30/07). Elle accuse ~6 jours de retard — les
    # journées les plus récentes ressortent donc avec blh_max_m = null,
    # ce qui est un fait, pas une panne. La distance normalisée sait
    # ignorer une feature absente SANS avantager la journée (c'est
    # précisément le bug corrigé dans match_analogs.py le 30/07).
    time.sleep(PAUSE_S)
    q5 = urllib.parse.urlencode({
        "latitude": cfg["lat"], "longitude": cfg["lon"],
        "start_date": start, "end_date": end,
        "hourly": "boundary_layer_height", "models": "era5", "timezone": "UTC",
    })
    era5 = _get_json(f"{ERA5_URL}?{q5}")
    blh_by_day = {}
    if era5 and "hourly" in era5:
        bt = era5["hourly"].get("time", [])
        bv = era5["hourly"].get("boundary_layer_height", [])
        for i in _window_indices(bt):
            if i < len(bv) and bv[i] is not None:
                blh_by_day.setdefault(bt[i][:10], []).append(bv[i])

    def col(name):
        return hourly.get(name, [None] * len(times))

    out = []
    for day, day_idx in sorted(_by_day(times, idx).items()):
        crest = _vector_wind([col(f"wind_speed_{level}hPa")[i] for i in day_idx],
                             [col(f"wind_direction_{level}hPa")[i] for i in day_idx])
        if crest is None:
            # Pas de vent par niveau ce jour-là : la journée n'est pas
            # descriptible pour un matching de montagne. On la saute
            # plutôt que de l'écrire à moitié.
            continue
        free = _vector_wind([col("wind_speed_600hPa")[i] for i in day_idx],
                            [col("wind_direction_600hPa")[i] for i in day_idx])

        def vals(name):
            return [col(name)[i] for i in day_idx if col(name)[i] is not None]

        sol = vals("wind_speed_10m")
        capes = vals("cape")
        mid, high = vals("cloud_cover_mid"), vals("cloud_cover_high")
        sun = vals("sunshine_duration")
        precip = vals("precipitation")
        # Écart T−Td MAXIMAL de la fenêtre = la base la plus haute de la
        # journée (~125 m par °C). Pas la moyenne, qui mélangerait le
        # matin humide et l'après-midi sec.
        spread = None
        for i in day_idx:
            t, td = col("temperature_2m")[i], col("dew_point_2m")[i]
            if t is not None and td is not None:
                spread = (t - td) if spread is None else max(spread, t - td)
        blh = blh_by_day.get(day)

        out.append({
            "site_id": site_slug,
            "date": day,
            # ── les 6 features figées à l'étape 2, noms inchangés ──
            "vent_crete_dir_deg": round(crest["dir"]),
            "vent_crete_force_kmh": round(crest["force"], 1),
            "vent_crete_raf_kmh": round(crest["raf"], 1),
            "blh_max_m": round(max(blh)) if blh else None,
            "cape_max_jkg": round(max(capes)) if capes else None,
            "nuages_mh_pct": round((sum(mid) / len(mid) + sum(high) / len(high)) / 2) if mid and high else None,
            # ── v2 (30/07/2026) ──
            "vent_600_dir_deg": round(free["dir"]) if free else None,
            "vent_600_force_kmh": round(free["force"], 1) if free else None,
            "vent_sol_kmh": round(sum(sol) / len(sol), 1) if sol else None,
            "spread_td_c": round(spread, 1) if spread is not None else None,
            "soleil_pct": round(100 * sum(sun) / (len(day_idx) * 3600)) if sun else None,
            "precip_mm": round(sum(precip), 1) if precip else None,
            # ── traçabilité ──
            "niveau_crete_hpa": level,
            "meteo_tier": "A",
            "schema": 2,
        })
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", choices=list(SITES), default=None)
    ap.add_argument("--start", default=ARCHIVE_START)
    ap.add_argument("--end", default=(date.today() - timedelta(days=1)).isoformat())
    ap.add_argument("--out", default=None, help="défaut : traces_cache/day_features.jsonl")
    args = ap.parse_args()

    sites = [args.site] if args.site else list(SITES)
    out_path = Path(args.out) if args.out else CACHE_DIR / "day_features.jsonl"

    # Réécriture in extenso plutôt qu'un append : le schéma a changé, et
    # deux schémas dans le même fichier se paieraient plus tard.
    total = 0
    with open(out_path, "w") as f:
        for slug in sites:
            ranges = list(_chunks(args.start, args.end))
            print(f"== {slug} — {args.start} → {args.end} ({len(ranges)} plages) ==")
            n = 0
            for a, b in ranges:
                rows = fetch_range(slug, a, b)
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
                n += len(rows)
                print(f"   {a} → {b} : {len(rows)} journées")
                time.sleep(PAUSE_S)
            print(f"   → {n} journées pour {slug}")
            total += n
    print(f"Terminé : {total} journées → {out_path}")
