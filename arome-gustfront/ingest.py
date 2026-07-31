"""Grille AROME dédiée à la VEILLE MODÈLE « front de rafales » (Lot A).

Produit UN fichier JSON par run, consommé par le serveur de push (jamais
par le navigateur) : une grille régulière sur la France portant, par
échéance horaire, les champs dont le détecteur §4.1 a besoin.

── Pourquoi pas Open-Meteo, comme le prévoyait la spec ───────────────
La spec passait par l'API Open-Meteo Météo-France. Sondage du bucket
public AROME (tools/probe_arome_packages.py, 31/07/2026) : TOUT y est,
en grille 001 (1,1 km au lieu de 2,5), horaire de 0 à 51 h, sans clé API
ni quota. On évite d'un coup le quota pondéré Open-Meteo (qui a déjà
cassé ce projet une fois, cf. BUGS.md 19/07), le piège documenté « les
variables 15 min n'incluent ni rafales ni pression », et une dépendance
réseau de plus au moment du poll.

⚠️ La clé METEOFRANCE_API_KEY ne sert PAS ici : elle couvre les
observations (DPPaquetObs) et la vigilance, pas les paquets modèle. Le
bucket S3 est en accès libre.

── Deux pièges vérifiés en direct sur le GRIB ────────────────────────
1. `max_10efg` / `max_10nfg` ne sont PAS deux variantes de rafale. Ce
   sont les composantes EST et NORD du maximum de rafale sur
   l'intervalle ("Time-maximum 10 metre eastward/northward wind gust").
   La rafale scalaire est leur norme. Prendre l'un des deux pour « la
   rafale » sous-estimerait d'environ 30 %, silencieusement.
2. Les valeurs manquantes sont encodées **9999**, pas NaN (même
   sentinelle que celle déjà documentée dans arome-wind/ingest.py).
   Sans masquage : des rafales à 36 000 km/h, ou pire, des moyennes
   plausibles mais fausses.

    SUPABASE_URL, SUPABASE_SERVICE_KEY   (WIND_GRID_BUCKET optionnel)
    DRY_RUN=1 pour tourner sans téléverser
"""

import json
import math
import os
import re
import sys
import tempfile
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

from eccodes import (codes_grib_new_from_file, codes_get, codes_get_values,
                     codes_release)

# ── Config ────────────────────────────────────────────────────────────
S3 = "https://meteofrance-pnt.s3.rbx.io.cloud.ovh.net"
MODEL_DIR = "arome"
GRID = "001"          # 0,01° natif — sous-échantillonné juste après
STEP_DEG = 0.25       # ~28 km : un front fait des centaines de km de long,
                      # inutile de le chercher à la maille kilométrique.
                      # Correspond au « maillage amont ~20 km » du §4.1.
MAX_HOURS = 24        # préavis visé 3 h à 24 h (§0). Au-delà, l'incertitude
                      # sur le déclenchement convectif rend l'ETA inutilisable.

# Emprise France métropolitaine + marge, identique à FW_LIGHTNING_BBOX.
LAT_MIN, LAT_MAX = 41.0, 51.6
LON_MIN, LON_MAX = -5.5, 10.0

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
BUCKET = os.environ.get("WIND_GRID_BUCKET", "wind-grid")
OUT_KEY = f"{MODEL_DIR}/gustfront/grid.json"
DRY_RUN = os.environ.get("DRY_RUN") == "1"
if not DRY_RUN and not (SB_URL and SB_KEY):
    raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants (ou DRY_RUN=1)")

MISSING_SENTINEL = 9999.0   # valeur manquante encodée par eccodes (pas NaN)


def http_get(url, timeout=300):
    req = urllib.request.Request(url, headers={"User-Agent": "balise-watch-gustfront/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def s3_keys(prefix):
    url = f"{S3}/?list-type=2&prefix={urllib.parse.quote(prefix)}&max-keys=1000"
    root = ET.fromstring(http_get(url, 60))
    return [e.text for e in root.iter() if e.tag.split('}')[-1] == "Key"]


def step_of(key):
    m = re.search(r"__(\d+)H__", key)
    return int(m.group(1)) if m else None


def pick_run():
    """Run offrant le plus d'échéances RÉELLEMENT publiées sur SP1 ET SP2.

    Même précaution que arome-wind/ingest.py::pick_run (cf. le débogage
    du 25/07/2026) : prendre le run le plus récent dès qu'un seul fichier
    existe donnait une grille tronquée à quelques heures, donc un
    détecteur aveugle au-delà — et silencieusement.
    """
    now = datetime.now(timezone.utc)
    h = (now.hour // 3) * 3
    base = now.replace(hour=h, minute=0, second=0, microsecond=0)
    best, best_n = None, -1
    for i in range(5):
        ref = (base - timedelta(hours=3 * i)).strftime("%Y-%m-%dT%H:00:00Z")
        try:
            sp1 = {step_of(k) for k in s3_keys(f"pnt/{ref}/{MODEL_DIR}/{GRID}/SP1/")}
            sp2 = {step_of(k) for k in s3_keys(f"pnt/{ref}/{MODEL_DIR}/{GRID}/SP2/")}
        except Exception:
            continue
        common = {s for s in (sp1 & sp2) if s is not None and 0 < s <= MAX_HOURS}
        if len(common) > best_n:
            best, best_n = ref, len(common)
        if len(common) >= MAX_HOURS:
            return ref, sorted(common)
    if not best or best_n <= 0:
        raise SystemExit("Aucun run AROME exploitable")
    ref = best
    sp1 = {step_of(k) for k in s3_keys(f"pnt/{ref}/{MODEL_DIR}/{GRID}/SP1/")}
    sp2 = {step_of(k) for k in s3_keys(f"pnt/{ref}/{MODEL_DIR}/{GRID}/SP2/")}
    return ref, sorted(s for s in (sp1 & sp2) if s is not None and 0 < s <= MAX_HOURS)


# ── Lecture GRIB ──────────────────────────────────────────────────────
WANT_SP1 = {"10u", "10v", "2t", "max_10efg", "max_10nfg"}
WANT_SP2 = {"sp", "CAPE_INS", "tirf"}


def download_tmp(key, suffix):
    """eccodes exige un VRAI descripteur de fichier (il appelle fileno()),
    un io.BytesIO ne passe pas — même contrainte que arome-wind/ingest.py.
    """
    path = os.path.join(tempfile.gettempdir(), f"bw_gf_{suffix}.grib2")
    with open(path, "wb") as fh:
        fh.write(http_get(f"{S3}/{urllib.parse.quote(key)}"))
    return path


def read_fields(path, want):
    """shortName -> valeurs, plus la géométrie de grille (une seule fois)."""
    out, meta = {}, None
    fh = open(path, "rb")
    while True:
        gid = codes_grib_new_from_file(fh)
        if gid is None:
            break
        sn = codes_get(gid, "shortName")
        if sn in want and sn not in out:
            out[sn] = codes_get_values(gid)
            if meta is None:
                meta = {
                    "ni": codes_get(gid, "Ni"),
                    "nj": codes_get(gid, "Nj"),
                    "lat0": codes_get(gid, "latitudeOfFirstGridPointInDegrees"),
                    "lon0": codes_get(gid, "longitudeOfFirstGridPointInDegrees"),
                    "dlat": codes_get(gid, "jDirectionIncrementInDegrees"),
                    "dlon": codes_get(gid, "iDirectionIncrementInDegrees"),
                    "scan_neg_j": codes_get(gid, "jScansPositively") == 0,
                }
        codes_release(gid)
    fh.close()
    return out, meta


def norm_lon(x):
    return x - 360 if x > 180 else x


def sample_indices(meta):
    """Indices plats du GRIB correspondant à notre grille de sortie."""
    ni, nj = meta["ni"], meta["nj"]
    lat0, lon0 = meta["lat0"], norm_lon(meta["lon0"])
    dlat, dlon = meta["dlat"], meta["dlon"]

    n_lat = int((LAT_MAX - LAT_MIN) / STEP_DEG) + 1
    n_lon = int((LON_MAX - LON_MIN) / STEP_DEG) + 1
    lats = [round(LAT_MIN + j * STEP_DEG, 4) for j in range(n_lat)]
    lons = [round(LON_MIN + i * STEP_DEG, 4) for i in range(n_lon)]

    idx = []
    for lat in lats:
        for lon in lons:
            # jScansPositively=0 => la première ligne du GRIB est la plus
            # AU NORD (cas AROME). Se tromper de sens retournerait la
            # France du nord au sud sans rien casser visiblement.
            jj = (lat0 - lat) / dlat if meta["scan_neg_j"] else (lat - lat0) / dlat
            ii = (lon - lon0) / dlon
            jj, ii = int(round(jj)), int(round(ii))
            idx.append(jj * ni + ii if (0 <= jj < nj and 0 <= ii < ni) else -1)
    return lats, lons, idx


# Bornes de PLAUSIBILITÉ en unités BRUTES du GRIB (SI), par champ.
#
# ⚠️ Débogage 31/07/2026, trouvé en vérifiant les valeurs produites : la
# première version appliquait un seuil unique `abs(v) >= 9998` pour
# détecter la sentinelle de valeur manquante. La pression de surface est
# en PASCALS (~101 325) — elle dépassait donc le seuil et TOUTE la
# colonne `pres` sortait vide, silencieusement. Le détecteur aurait
# tourné sans jamais voir un seul saut de pression, c'est-à-dire sans son
# signal principal, sans la moindre erreur visible.
#
# D'où des bornes explicites par champ plutôt qu'un seuil universel. La
# sentinelle 9999 est en plus testée séparément : pour le CAPE, 9999 est
# une valeur physiquement possible, une borne haute ne suffirait pas.
RAW_BOUNDS = {
    "10u": (-150.0, 150.0),          # m/s
    "10v": (-150.0, 150.0),
    "max_10efg": (-200.0, 200.0),
    "max_10nfg": (-200.0, 200.0),
    "2t": (150.0, 350.0),            # K
    "sp": (50000.0, 110000.0),       # Pa
    "CAPE_INS": (0.0, 20000.0),      # J/kg
    "tirf": (0.0, 500.0),            # mm
}


def pick(values, k, field):
    if k < 0 or values is None or k >= len(values):
        return None
    v = float(values[k])
    if not math.isfinite(v):
        return None
    if abs(v - MISSING_SENTINEL) < 0.01:
        return None
    lo, hi = RAW_BOUNDS.get(field, (-1e12, 1e12))
    if v < lo or v > hi:
        return None
    return v


def sb_upload(path, body, tries=3):
    """Même politique de cache que arome-wind : `no-cache, must-revalidate`.

    Cet objet est RÉÉCRIT EN PLACE à chaque run. Un TTL long y
    reproduirait le bug documenté dans BUGS.md (23-24/07) : un client
    ayant mis l'objet en cache juste avant un nouveau run reste bloqué
    sur l'ancien, hard-refresh sans effet.
    """
    url = f"{SB_URL}/storage/v1/object/{BUCKET}/{path}"
    headers = {
        "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json",
        "Cache-Control": "no-cache, must-revalidate",
        "x-upsert": "true",
    }
    last = None
    for attempt in range(tries):
        for method in ("POST", "PUT"):
            req = urllib.request.Request(url, data=body, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=300) as r:
                    return r.status
            except Exception as e:
                last = e
                detail = ""
                if hasattr(e, "read"):
                    try:
                        detail = e.read().decode()[:300]
                    except Exception:
                        pass
                print(f"  upload {method} échec ({e}) {detail}", file=sys.stderr)
        time.sleep(2 * (attempt + 1))
    raise SystemExit(f"Téléversement impossible : {last}")


def main():
    ref, steps = pick_run()
    if not steps:
        raise SystemExit("Run trouvé mais aucune échéance exploitable")
    print(f"Run {ref} — {len(steps)} échéances (1..{max(steps)} h)")

    run_dt = datetime.strptime(ref, "%Y-%m-%dT%H:00:00Z").replace(tzinfo=timezone.utc)
    sp1_keys = {step_of(k): k for k in s3_keys(f"pnt/{ref}/{MODEL_DIR}/{GRID}/SP1/")}
    sp2_keys = {step_of(k): k for k in s3_keys(f"pnt/{ref}/{MODEL_DIR}/{GRID}/SP2/")}

    lats = lons = idx = None
    times = []
    out = {k: [] for k in ("gust", "spd", "dir", "pres", "cape", "precip", "temp")}

    for h in steps:
        k1, k2 = sp1_keys.get(h), sp2_keys.get(h)
        if not k1 or not k2:
            continue
        t0 = time.time()
        f1, meta = read_fields(download_tmp(k1, "sp1"), WANT_SP1)
        f2, _ = read_fields(download_tmp(k2, "sp2"), WANT_SP2)
        if meta is None:
            continue
        if idx is None:
            lats, lons, idx = sample_indices(meta)
            print(f"  grille de sortie {len(lats)}×{len(lons)} = {len(idx)} points")

        gust, spd, drc, pres, cape, precip, temp = [], [], [], [], [], [], []
        for k in idx:
            u = pick(f1.get("10u"), k, "10u")
            v = pick(f1.get("10v"), k, "10v")
            ge = pick(f1.get("max_10efg"), k, "max_10efg")
            gn = pick(f1.get("max_10nfg"), k, "max_10nfg")
            t2 = pick(f1.get("2t"), k, "2t")
            sp = pick(f2.get("sp"), k, "sp")
            cp = pick(f2.get("CAPE_INS"), k, "CAPE_INS")
            rr = pick(f2.get("tirf"), k, "tirf")

            gust.append(round(math.hypot(ge, gn) * 3.6) if (ge is not None and gn is not None) else None)
            if u is not None and v is not None:
                spd.append(round(math.hypot(u, v) * 3.6))
                # Direction D'OÙ VIENT le vent (convention météo), la même
                # que Pioupiou et Météo-France — sinon la bascule de
                # direction comparerait des choux et des carottes.
                drc.append(round((math.degrees(math.atan2(-u, -v)) + 360) % 360))
            else:
                spd.append(None)
                drc.append(None)
            pres.append(round(sp / 100, 1) if sp is not None else None)
            cape.append(round(cp) if cp is not None else None)
            precip.append(round(rr, 1) if rr is not None else None)
            temp.append(round(t2 - 273.15, 1) if t2 is not None else None)

        times.append((run_dt + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M:%SZ"))
        out["gust"].append(gust)
        out["spd"].append(spd)
        out["dir"].append(drc)
        out["pres"].append(pres)
        out["cape"].append(cape)
        out["precip"].append(precip)
        out["temp"].append(temp)
        print(f"  +{h:02d} h  ({time.time() - t0:.1f} s)")

    if not times:
        raise SystemExit("Aucune échéance lue")

    payload = {
        "run": ref,
        "fetchedAt": int(time.time() * 1000),
        "stepDeg": STEP_DEG,
        "lats": lats,
        "lons": lons,
        "times": times,
        # Tableaux à plat, index = iLat * len(lons) + iLon, un par échéance.
        "vars": out,
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    print(f"\n{len(times)} échéances, {len(idx)} points, {len(body) / 1024 / 1024:.1f} Mo")

    if DRY_RUN:
        print("DRY_RUN — pas de téléversement")
        return 0
    sb_upload(OUT_KEY, body)
    print(f"Téléversé → {BUCKET}/{OUT_KEY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
