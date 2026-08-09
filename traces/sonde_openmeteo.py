#!/usr/bin/env python3
"""
Sonde empirique de l'archive Open-Meteo — étape 2 du plan traces.

But : vérifier VARIABLE PAR VARIABLE ce que les deux APIs d'archive
exposent réellement (pas ce que la doc laisse croire), sur un point
Maurienne, avant de figer le schéma features de ETAPE2_SCHEMAS_FEATURES.md.

  - Historical Forecast API (archive des prévisions AROME/ARPEGE, >= déc 2023)
  - Historical Weather API (ERA5, 1940+, ~25 km — a priori SANS niveaux
    de pression d'après le README open-data ; confirmé en session)

Usage :  python3 sonde_openmeteo.py [lat lon]
         (défaut : 45.22 6.75, Maurienne)

Sortie : table lisible sur stdout + sonde_openmeteo_resultats.json
Coût quota : ~35 requêtes à 1 jour × 1 variable — négligeable
(pondération nb_points × jours/14 × variables/10, cf. OPEN_METEO_LIMITES_ANALYSE.md).

Aucune dépendance hors stdlib. Résultats déjà obtenus une fois en
session Cowork (24/07/2026) — cf. ETAPE2_SCHEMAS_FEATURES.md §1 pour le
verdict figé. Ce script sert à re-sonder un autre point ou une autre
variable plus tard, pas à ré-explorer ce qui est déjà tranché.
"""

import json
import sys
import time
import urllib.parse
import urllib.request

LAT, LON = 45.22, 6.75
if len(sys.argv) == 3:
    LAT, LON = float(sys.argv[1]), float(sys.argv[2])

HF = "https://historical-forecast-api.open-meteo.com/v1/forecast"
AR = "https://archive-api.open-meteo.com/v1/archive"
UA = "balise-watch-sonde/1.0 (contact: argonautes.sim@gmail.com)"
PAUSE = 0.4  # politesse réseau, habitude maison

# ---------------------------------------------------------------- candidats

HF_VARS = [
    "boundary_layer_height",
    "cape",
    "lifted_index",
    "convective_inhibition",
    "wind_speed_900hPa", "wind_direction_900hPa",
    "wind_speed_850hPa", "wind_direction_850hPa",
    "wind_speed_800hPa", "wind_direction_800hPa",
    "wind_speed_700hPa", "wind_direction_700hPa",
    "wind_speed_600hPa", "wind_direction_600hPa",
    "wind_speed_500hPa", "wind_direction_500hPa",
    "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high",
    "sunshine_duration",
    "shortwave_radiation",
    "temperature_2m",
    "temperature_850hPa",
    "freezing_level_height",
    "geopotential_height_850hPa",
]

AR_VARS = [
    "boundary_layer_height",
    "cape",
    "lifted_index",
    "wind_speed_10m", "wind_direction_10m",
    "wind_speed_100m", "wind_direction_100m",
    "wind_speed_850hPa",
    "cloud_cover_low", "cloud_cover_mid", "cloud_cover_high",
    "temperature_2m",
    "pressure_msl",
    "shortwave_radiation",
]

DEPTH_DATES = ["2021-06-15", "2022-06-15", "2023-06-15",
               "2023-12-16", "2024-01-15", "2024-06-15"]


import os as _os                                          # noqa: E402
import sys as _sys                                        # noqa: E402

_TOOLS = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                       "..", "tools")
if _TOOLS not in _sys.path:
    _sys.path.insert(0, _TOOLS)
try:
    from quota_openmeteo import Budget as _Budget, poids_url as _poids_url
    BUDGET = _Budget("sonde_openmeteo")
except Exception as _exc:                                 # noqa: BLE001
    print(f"  ⓘ budget Open-Meteo indisponible ({_exc}) — sans comptage partagé")
    BUDGET = None


def fetch(base, date, var, model=None):
    q = {
        "latitude": LAT, "longitude": LON,
        "start_date": date, "end_date": date,
        "hourly": var, "timezone": "UTC",
    }
    if model:
        q["models"] = model
    url = base + "?" + urllib.parse.urlencode(q)
    # ⚠️ MÊME UNE SONDE COMPTE. C'est le piège n°3 du lot : une sonde
    # lancée « juste pour voir » pendant la collecte tire sur la même
    # fenêtre horaire, depuis la même IP, et sa consommation doit
    # apparaître sous son nom plutôt que de disparaître dans un trou
    # que la collecte ne saura pas expliquer.
    if BUDGET is not None:
        BUDGET.demander(_poids_url(url))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            reason = json.loads(e.read().decode()).get("reason", "")[:80]
        except Exception:
            reason = str(e)
        return ("REFUSE", 0.0, reason)
    except Exception as e:
        return ("ERREUR", 0.0, str(e)[:80])
    vals = (data.get("hourly") or {}).get(var)
    if not vals:
        return ("ABSENT", 0.0, "clé absente de la réponse")
    non_null = [v for v in vals if v is not None]
    pct = 100.0 * len(non_null) / len(vals)
    sample = non_null[len(non_null) // 2] if non_null else None
    return ("OK" if pct > 0 else "VIDE", pct, sample)


def run(label, base, varlist, date, model=None):
    print(f"\n== {label} — point {LAT},{LON}, jour test {date} ==")
    print(f"{'variable':<32} {'statut':<8} {'%non-null':>9}  exemple/raison")
    out = {}
    for v in varlist:
        st, pct, sample = fetch(base, date, v, model)
        out[v] = {"statut": st, "pct_non_null": round(pct, 1), "exemple": sample}
        print(f"{v:<32} {st:<8} {pct:>8.0f}%  {sample}")
        time.sleep(PAUSE)
    return out


def run_depth():
    print("\n== Profondeur archive meteofrance_seamless (wind_speed_850hPa) ==")
    out = {}
    for d in DEPTH_DATES:
        st, pct, sample = fetch(HF, d, "wind_speed_850hPa", "meteofrance_seamless")
        out[d] = {"statut": st, "pct_non_null": round(pct, 1)}
        print(f"{d}  {st:<8} {pct:>4.0f}%  {sample}")
        time.sleep(PAUSE)
    return out


if __name__ == "__main__":
    results = {
        "point": [LAT, LON],
        "historical_forecast_meteofrance": run(
            "Historical Forecast API (meteofrance_seamless)",
            HF, HF_VARS, "2024-06-15", "meteofrance_seamless"),
        "historical_forecast_icon": run(
            "Historical Forecast API (icon_seamless — secours lifted_index)",
            HF, ["lifted_index", "convective_inhibition", "boundary_layer_height"],
            "2024-06-15", "icon_seamless"),
        "era5_archive": run(
            "Historical Weather API (ERA5)", AR, AR_VARS, "2015-06-15"),
        "profondeur_arome": run_depth(),
    }
    with open("sonde_openmeteo_resultats.json", "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print("\nRésultats écrits dans sonde_openmeteo_resultats.json")
