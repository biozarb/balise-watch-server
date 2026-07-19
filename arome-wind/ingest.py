#!/usr/bin/env python3
"""
Ingestion AROME -> grille de vent (calque carte Balise Watch).

Télécharge les paquets GRIB AROME publics (OVH S3, sans clé API), extrait le
vent SOL (10 m, paquet SP1) et ALTITUDE (niveaux de pression, paquet IP1),
sous-échantillonne à 0,15° par tuiles 2°, et téléverse des fichiers WindGrid
JSON dans Supabase Storage (bucket `wind-grid`).

Tourne dans une GitHub Action toutes les 3 h — REMPLACE les appels Open-Meteo
par tuile / par utilisateur (qui saturaient le quota gratuit -> 429). Ici :
1 seule ingestion nationale par run, servie à tous depuis le CDN Supabase.

Sortie par (kind, level, tuile), format IDENTIQUE à l'ancienne route
/wind-grid (cf. web/src/types/openmeteo.ts, interface WindGrid) : côté client,
seule l'URL source change.

Variables d'environnement requises (secrets GitHub) :
  SUPABASE_URL, SUPABASE_SERVICE_KEY   (WIND_GRID_BUCKET optionnel, défaut wind-grid)
"""
import os, re, json, math, time, tempfile, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from eccodes import (codes_grib_new_from_file, codes_get, codes_get_values,
                     codes_release)

# ── Config (à garder synchronisé avec web/src/lib/config.ts) ──────────
S3         = "https://meteofrance-pnt.s3.rbx.io.cloud.ovh.net"
MODEL_DIR  = "arome"
GRID       = "0025"                 # 0,025° : largement suffisant pour un affichage 0,15°
MAX_HOURS  = 12                     # horizon court (décision Yann) — 1-2 groupes GRIB
BBOX       = dict(latmin=41.0, latmax=52.0, lonmin=-6.0, lonmax=11.0)  # France + voisins
STEP       = 0.15                   # pas d'affichage (cf. WIND_GRID_STEP_DEG)
TILE_DEG   = 2                      # cf. WIND_GRID_TILE_DEG
LEVELS     = [1000, 950, 925, 900, 850, 800, 700, 600, 500]  # cf. WIND_GRID_LEVELS
MODEL_KEY  = "meteofrance_seamless" # clé "model" écrite dans le JSON (AROME)

DRY_RUN = os.environ.get("DRY_RUN") == "1"     # tests : parse/tuilage sans upload
SB_URL  = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")
BUCKET  = os.environ.get("WIND_GRID_BUCKET", "wind-grid")
if not DRY_RUN and not (SB_URL and SB_KEY):
    raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants (ou DRY_RUN=1)")

# ── HTTP / S3 helpers ─────────────────────────────────────────────────
def http_get(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "balise-watch-arome/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def s3_keys(prefix):
    """Liste les clés d'objets sous un préfixe (S3 ListObjectsV2)."""
    url = f"{S3}/?list-type=2&prefix={urllib.parse.quote(prefix)}&max-keys=1000"
    root = ET.fromstring(http_get(url, 60))
    return [e.text for e in root.iter() if e.tag.split('}')[-1] == "Key"]

def latest_run():
    """Dernier run AROME (cadence 3 h) dont le paquet SP1 est déjà publié."""
    base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    base -= timedelta(hours=base.hour % 3)
    for back in range(9):                       # jusqu'à 24 h en arrière
        run = base - timedelta(hours=3 * back)
        ref = run.strftime("%Y-%m-%dT%H:00:00Z")
        if s3_keys(f"pnt/{ref}/{MODEL_DIR}/{GRID}/SP1/"):
            return ref, run
    raise SystemExit("Aucun run AROME SP1 publié sur les 24 dernières heures")

def _range_start(key):
    m = re.search(r"__(\d+)H(?:\d+H)?__", key)
    return int(m.group(1)) if m else 999

def files_for(ref, pkg):
    """Fichiers du paquet couvrant les échéances 0..MAX_HOURS."""
    keys = s3_keys(f"pnt/{ref}/{MODEL_DIR}/{GRID}/{pkg}/")
    return sorted(k for k in keys if _range_start(k) <= MAX_HOURS)

# ── Parsing GRIB (eccodes) ────────────────────────────────────────────
def _norm_lon(x):
    return x - 360 if x > 180 else x

def parse_grib(path, want):
    """want(shortName, typeOfLevel, level) -> clé de collecte (ou None pour ignorer).
    Retourne ({clé: {step: values}}, meta_grille). meta = grille commune AROME."""
    out, meta = {}, None
    with open(path, "rb") as f:
        while True:
            gid = codes_grib_new_from_file(f)
            if gid is None:
                break
            key = want(codes_get(gid, "shortName"),
                       codes_get(gid, "typeOfLevel"),
                       codes_get(gid, "level"))
            if key is not None:
                if meta is None:
                    meta = dict(
                        Ni=codes_get(gid, "Ni"), Nj=codes_get(gid, "Nj"),
                        lat0=codes_get(gid, "latitudeOfFirstGridPointInDegrees"),
                        lon0=_norm_lon(codes_get(gid, "longitudeOfFirstGridPointInDegrees")),
                        di=codes_get(gid, "iDirectionIncrementInDegrees"),
                        dj=codes_get(gid, "jDirectionIncrementInDegrees"),
                        jScan=codes_get(gid, "jScansPositively"))
                step = codes_get(gid, "step")
                out.setdefault(key, {})[step] = codes_get_values(gid)
            codes_release(gid)
    return out, meta

def sample_indices(meta):
    """Indices (j, i) + (lat, lon) échantillonnés à STEP dans BBOX, depuis la
    grille native AROME (décimation entière STEP/di)."""
    dec = max(1, round(STEP / meta["di"]))
    pts = []
    for j in range(0, meta["Nj"], dec):
        lat = meta["lat0"] + (meta["dj"] * j if meta["jScan"] == 1 else -meta["dj"] * j)
        if not (BBOX["latmin"] <= lat <= BBOX["latmax"]):
            continue
        for i in range(0, meta["Ni"], dec):
            lon = meta["lon0"] + meta["di"] * i
            if BBOX["lonmin"] <= lon <= BBOX["lonmax"]:
                pts.append((j * meta["Ni"] + i, round(lat, 3), round(lon, 3)))
    return pts

def _ms(u, v):
    """u,v (m/s) -> (vitesse km/h, direction météo = d'où vient le vent)."""
    if u is None or v is None:
        return None, None
    spd = math.hypot(u, v) * 3.6
    drc = (270 - math.degrees(math.atan2(v, u))) % 360
    return round(spd, 1), round(drc)

def build_grids(uv_by_step, meta, steps, times, kind, level):
    """Construit les WindGrid par tuile 2° pour un (kind, level) donné.
    uv_by_step: {step: (U_values, V_values)}. Retourne {(tLat,tLon): dict WindGrid}."""
    pts = sample_indices(meta)
    tiles = {}
    for idx, lat, lon in pts:
        tLat = math.floor(lat / TILE_DEG) * TILE_DEG
        tLon = math.floor(lon / TILE_DEG) * TILE_DEG
        g = tiles.get((tLat, tLon))
        if g is None:
            g = tiles[(tLat, tLon)] = dict(
                model=MODEL_KEY, kind=kind, level=level,
                tileLat=tLat, tileLon=tLon, times=times, points=[])
        speed, dir_ = [], []
        for s in steps:
            U, V = uv_by_step[s]
            sp, dr = _ms(U[idx], V[idx])
            speed.append(sp); dir_.append(dr)
        g["points"].append(dict(lat=lat, lon=lon, speed=speed, dir=dir_))
    return tiles

# ── Upload Supabase Storage ───────────────────────────────────────────
def sb_upload(path, body):
    if DRY_RUN:
        return 0
    url = f"{SB_URL}/storage/v1/object/{BUCKET}/{path}"
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Bearer {SB_KEY}", "apikey": SB_KEY,
        "Content-Type": "application/json", "x-upsert": "true",
        "Cache-Control": "max-age=300"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status

def download_tmp(key):
    """Télécharge un objet S3 (gros GRIB) vers un fichier temporaire."""
    url = f"{S3}/{urllib.parse.quote(key)}"
    fd, path = tempfile.mkstemp(suffix=".grib2")
    os.close(fd)
    t0 = time.time()
    with urllib.request.urlopen(urllib.request.Request(
            url, headers={"User-Agent": "balise-watch-arome/1"}), timeout=300) as r, \
            open(path, "wb") as out:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    print(f"  ↓ {key.split('/')[-1]} ({os.path.getsize(path)//(1<<20)} Mo, {time.time()-t0:.1f}s)")
    return path

def merge_parse(files, want):
    merged, meta = {}, None
    for key in files:
        p = download_tmp(key)
        try:
            part, m = parse_grib(p, want)
            meta = meta or m
            for k, byhstep in part.items():
                merged.setdefault(k, {}).update(byhstep)
        finally:
            os.unlink(p)
    return merged, meta

def steps_times(run, *dicts):
    """Échéances communes (≤ MAX_HOURS) + timestamps ISO alignés."""
    common = None
    for d in dicts:
        for byhstep in d.values():
            s = set(byhstep.keys())
            common = s if common is None else (common & s)
    steps = sorted(x for x in (common or set()) if x <= MAX_HOURS)
    times = [(run + timedelta(hours=s)).strftime("%Y-%m-%dT%H:%M") for s in steps]
    return steps, times

def main():
    ref, run = latest_run()
    print(f"Run AROME : {ref}")
    manifest = dict(run=ref, generatedAt=datetime.now(timezone.utc)
                    .strftime("%Y-%m-%dT%H:%M:%SZ"), grid=GRID,
                    tileDeg=TILE_DEG, step=STEP, levels=[], uploaded=0)
    total = 0

    # ── SOL (10 m) : paquet SP1, variables 10u/10v ────────────────────
    print("SOL (SP1, 10 m) :")
    sol_want = lambda sn, tol, lvl: sn if (sn in ("10u", "10v")
                                           and tol == "heightAboveGround") else None
    data, meta = merge_parse(files_for(ref, "SP1"), sol_want)
    data = {("u" if k == "10u" else "v"): v for k, v in data.items()}
    steps, times = steps_times(run, data)
    uv = {s: (data["u"][s], data["v"][s]) for s in steps}
    for (tLat, tLon), grid in build_grids(uv, meta, steps, times, "sol", None).items():
        grid["fetchedAt"] = int(time.time() * 1000)
        sb_upload(f"{MODEL_DIR}/sol/{tLat}_{tLon}.json",
                  json.dumps(grid, separators=(",", ":")).encode())
        total += 1
    manifest["solTimes"] = times
    print(f"  {len(times)} échéances, tuiles téléversées (cumul {total})")

    # ── ALTITUDE : paquet IP1, u/v par niveau de pression ─────────────
    # IP1 téléchargé/parsé UNE SEULE fois pour TOUS les niveaux (fichiers
    # ~500 Mo : surtout pas un re-téléchargement par niveau).
    print("ALTITUDE (IP1, niveaux de pression) :")
    LSET = set(LEVELS)
    alt_want = lambda sn, tol, l: ((sn, l) if (sn in ("u", "v")
                                   and tol == "isobaricInhPa" and l in LSET) else None)
    data, meta = merge_parse(files_for(ref, "IP1"), alt_want)
    for lvl in LEVELS:
        if ("u", lvl) not in data or ("v", lvl) not in data:
            print(f"  niveau {lvl} hPa absent — ignoré"); continue
        du, dv = data[("u", lvl)], data[("v", lvl)]
        steps = sorted(s for s in (set(du) & set(dv)) if s <= MAX_HOURS)
        times = [(run + timedelta(hours=s)).strftime("%Y-%m-%dT%H:%M") for s in steps]
        uv = {s: (du[s], dv[s]) for s in steps}
        for (tLat, tLon), grid in build_grids(uv, meta, steps, times, "alt", lvl).items():
            grid["fetchedAt"] = int(time.time() * 1000)
            sb_upload(f"{MODEL_DIR}/alt/{lvl}/{tLat}_{tLon}.json",
                      json.dumps(grid, separators=(",", ":")).encode())
            total += 1
        manifest["levels"].append(lvl)
        print(f"  {lvl} hPa : {len(times)} échéances OK (cumul {total})")

    manifest["uploaded"] = total
    sb_upload(f"{MODEL_DIR}/manifest.json", json.dumps(manifest).encode())
    print(f"Terminé : {total} tuiles + manifest téléversés dans '{BUCKET}'.")

if __name__ == "__main__":
    main()
