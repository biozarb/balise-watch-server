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
# Grilles AROME différenciées (retour Yann 19/07, "épouser le relief") :
#  - sol : grille 001 = 0,01° (~1,1 km), la HAUTE RÉSOLUTION AROME. C'est
#          elle qui résout l'écoulement dans les vallées — le 0,025° lissait
#          justement ce qu'on veut voir.
#  - alt : grille 0025 uniquement — les niveaux de pression (paquets IP*)
#          n'existent QUE dans cette grille (vérifié : 001 n'expose que
#          SP*/HP*, aucun isobare).
GRID_SOL   = "001"
GRID_ALT   = "0025"
MAX_HOURS  = 48                     # horizon complet AROME (retour Yann 19/07)
BBOX       = dict(latmin=41.0, latmax=52.0, lonmin=-6.0, lonmax=11.0)  # France + voisins
# Pas d'échantillonnage, = maillage NATIF de chaque grille (aucune perte) :
#  - sol : 0,01°  (grille 001)  -> ~1,1 km, le relief est résolu.
#  - alt : 0,05°  (grille 0025, 1 point sur 2) -> les vents aux niveaux de
#          pression sont des champs lisses (synoptiques) : le terrain n'y
#          crée pas de structure fine, inutile de payer ×4 le stockage.
STEP_SOL   = 0.01
STEP_ALT   = 0.05
# Pas de temps (débogage 20/07/2026, retour Yann sur la Vue vent 3D —
# "le pas devient de plus en plus grand, on peut garder 1h par 1h sauf la
# nuit ?") : horaire toute la journée, 1 échéance sur COARSE_EVERY
# seulement pendant la fenêtre nuit (cf. NIGHT_UTC_START/END + keep_step
# plus bas). Remplace l'ancien profil à seuil fixe FINE_H=12 (coupait à
# 12h après le run peu importe l'heure réelle — donc parfois en pleine
# journée de vol). Coût : ~41 échéances au lieu de 25 sur 48h (deux nuits
# dans la fenêtre), donc plus de fichiers horaires SOL (grille 001,
# ~23 Mo/fichier) téléchargés — le volume ALT (IP1, bundles toujours
# téléchargés en entier) domine déjà le total (~4,4 Go/run, cf.
# .github/workflows/arome-wind.yml), l'impact reste de l'ordre de +8%,
# large marge sous le timeout de 60 min. FINE_H/COARSE_EVERY gardés
# comme filet de sécurité si _RUN_HOUR_UTC n'est pas encore connu (ne
# devrait pas arriver en usage normal, cf. keep_step).
FINE_H       = 12
COARSE_EVERY = 3
# Fenêtre UTC considérée "nuit" (coarse même si <= FINE_H) — généreuse
# pour ne jamais rogner une fenêtre de vol matinale/tardive :
#   été  (France UTC+2) : nuit locale ~22h-06h -> ~20h-04h UTC
#   hiver (France UTC+1) : nuit locale ~22h-06h -> ~21h-05h UTC
# Fenêtre retenue 22h-04h UTC (6h) : sous-ensemble commun aux deux
# saisons, quitte à garder l'horaire un peu tôt/tard aux extrêmes plutôt
# que de couper une fenêtre de vol. Traverse minuit (22 > 4).
NIGHT_UTC_START, NIGHT_UTC_END = 22, 4
TILE_DEG   = 2                      # cf. WIND_GRID_TILE_DEG
LEVELS     = [1000, 950, 925, 900, 850, 800, 700, 600, 500]  # cf. WIND_GRID_LEVELS
MODEL_KEY  = "meteofrance_seamless" # clé "model" écrite dans le JSON (AROME)

# Élévation du sol par nœud de la grille ALT (retour Yann 21/07/2026) —
# sert au masquage "façon météo-parapente" côté client (une flèche dont le
# niveau AMSL passe sous l'élévation à ce point est souterraine, non
# affichée, cf. web WindGridLayer.floorAltM / WindGridPoint.elev).
#
# 1re version : appel à l'API élévation Open-Meteo (build_alt_elevation.py,
# DEM Copernicus). ABANDONNÉE (retour Yann 21/07) — ce projet a DÉJÀ été
# cassé une fois par le quota Open-Meteo (429, cf. BUGS.md "calque champ de
# vent : aucune flèche, jamais"), c'est précisément pourquoi ce pipeline
# existe (téléchargement GRIB direct Météo-France plutôt que /v1/forecast
# par tuile/utilisateur). Ajouter un NOUVEL appel Open-Meteo — même
# pré-calculé une fois — allait à l'encontre de cette décision.
#
# 2e version (celle-ci) : le champ d'orographie AROME lui-même est déjà
# public dans le MÊME bucket S3 que le vent (paquet SP3, grille 001 —
# shortName `h`, "Geometrical height above ground", typeOfLevel "surface",
# STATIQUE d'une échéance à l'autre). Vérifié en direct (session 21/07,
# sondage eccodes) : Grenoble 219 m (réel ~215 m), mer 0 m, Mont Blanc
# 4142 m (lissé par la maille 1 km, cohérent), Bourg-St-Maurice 940 m
# (réel ~840 m). Gratuit, sans quota, ET plus juste sur le fond que
# n'importe quelle DEM externe : c'est le relief tel qu'AROME LE VOIT
# LUI-MÊME, exactement ce qui détermine si un niveau de vent AROME est
# "sous terre" selon AROME. Un seul petit fichier (~7 Mo, échéance 00H
# uniquement, le champ ne varie pas) téléchargé en plus par run.
def load_orography(ref):
    """Ne réutilise PAS `parse_grib` (déboguage 21/07, run GitHub cassé en
    prod) : celui-ci appelle `codes_get(gid, "typeOfLevel")` /
    `"level"` SANS filet pour CHAQUE message du fichier — or SP3 contient
    au moins un message dont ces clés n'existent pas (repéré au sondage
    manuel de session, ex. un champ de type probabilité/seuil sans niveau
    classique), ce qui levait `KeyValueNotFoundError` et faisait planter
    tout le script APRÈS le téléchargement SOL, donc SANS publier la
    moindre tuile ALT du run. `parse_grib` reste tel quel (utilisé par
    SOL/ALT eux-mêmes, jamais vu ce problème dessus) — on lit ce fichier
    précis à la main, message par message, en ignorant silencieusement
    tout message dont les clés attendues manquent."""
    keys = sorted(k for k in s3_keys(f"pnt/{ref}/{MODEL_DIR}/{GRID_SOL}/SP3/") if "__00H__" in k)
    if not keys:
        print("  ⚠️ orographie (SP3 00H) introuvable — points ALT sans `elev`")
        return None
    p = download_tmp(keys[0])
    meta, values = None, None
    try:
        with open(p, "rb") as f:
            while True:
                gid = codes_grib_new_from_file(f)
                if gid is None:
                    break
                try:
                    if (codes_get(gid, "shortName") == "h"
                            and codes_get(gid, "typeOfLevel") == "surface"):
                        meta = dict(
                            Ni=codes_get(gid, "Ni"), Nj=codes_get(gid, "Nj"),
                            lat0=codes_get(gid, "latitudeOfFirstGridPointInDegrees"),
                            lon0=_norm_lon(codes_get(gid, "longitudeOfFirstGridPointInDegrees")),
                            di=codes_get(gid, "iDirectionIncrementInDegrees"),
                            dj=codes_get(gid, "jDirectionIncrementInDegrees"),
                            jScan=codes_get(gid, "jScansPositively"))
                        values = codes_get_values(gid)
                        codes_release(gid)
                        break
                except Exception:
                    pass   # message sans les clés attendues — on l'ignore et on continue
                codes_release(gid)
    finally:
        os.unlink(p)
    if values is None:
        print("  ⚠️ champ 'h' (surface) absent du paquet SP3 — points ALT sans `elev`")
        return None
    return dict(values=values, meta=meta)

def elev_at(orog, lat, lon):
    """Élévation (m AMSL) au point (lat, lon) le plus proche dans la grille
    d'orographie native (0,01°) — même convention lat/lon/scan que
    `sample_indices` (meta['lon0'] déjà normalisé -180..180 par parse_grib,
    donc aucun rebouclage 348°→360°→16° à gérer ici)."""
    if orog is None:
        return None
    meta = orog["meta"]
    i = round((lon - meta["lon0"]) / meta["di"])
    j = round((meta["lat0"] - lat) / meta["dj"]) if meta["jScan"] != 1 else round((lat - meta["lat0"]) / meta["dj"])
    if i < 0 or i >= meta["Ni"] or j < 0 or j >= meta["Nj"]:
        return None
    v = orog["values"][j * meta["Ni"] + i]
    return None if v is None else round(float(v))

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
        if s3_keys(f"pnt/{ref}/{MODEL_DIR}/{GRID_SOL}/SP1/"):
            return ref, run
    raise SystemExit("Aucun run AROME SP1 publié sur les 24 dernières heures")

def files_for(ref, pkg, grid):
    """Fichiers du paquet couvrant les échéances retenues.

    Deux nommages coexistent : la grille 0025 groupe les échéances
    (`__00H06H__`), la grille 001 publie UN FICHIER PAR HEURE (`__06H__`).
    Pour cette dernière on ne télécharge que les échéances effectivement
    gardées (keep_step) — sinon on tirerait 49 fichiers de ~23 Mo pour n'en
    exploiter que 25, soit ~550 Mo de trafic pour rien."""
    out = []
    for k in s3_keys(f"pnt/{ref}/{MODEL_DIR}/{grid}/{pkg}/"):
        m = re.search(r"__(\d+)H(?:(\d+)H)?__", k)
        if not m:
            continue
        start, end = int(m.group(1)), m.group(2)
        if start > MAX_HOURS:
            continue
        if end is None and not keep_step(start):
            continue                       # fichier horaire non retenu
        out.append(k)
    return sorted(out)

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
                # Filtrer l'échéance AVANT codes_get_values : décoder puis
                # jeter coûterait ~2× la RAM (49 échéances gardées au lieu
                # de 25) et autant de temps CPU pour rien.
                step = codes_get(gid, "step")
                if step <= MAX_HOURS and keep_step(step):
                    if meta is None:
                        meta = dict(
                            Ni=codes_get(gid, "Ni"), Nj=codes_get(gid, "Nj"),
                            lat0=codes_get(gid, "latitudeOfFirstGridPointInDegrees"),
                            lon0=_norm_lon(codes_get(gid, "longitudeOfFirstGridPointInDegrees")),
                            di=codes_get(gid, "iDirectionIncrementInDegrees"),
                            dj=codes_get(gid, "jDirectionIncrementInDegrees"),
                            jScan=codes_get(gid, "jScansPositively"))
                    out.setdefault(key, {})[step] = codes_get_values(gid)
            codes_release(gid)
    return out, meta

# Défini dans main() dès que `run` (heure d'init réelle du run AROME) est
# connue — keep_step() en a besoin pour savoir quelle heure UTC réelle
# correspond à chaque échéance `h` (heures écoulées depuis le run).
_RUN_HOUR_UTC = None

def is_night_utc(hour_of_day):
    """hour_of_day : 0-23 UTC. Fenêtre [NIGHT_UTC_START, NIGHT_UTC_END[,
    traverse minuit (22 > 4)."""
    if NIGHT_UTC_START < NIGHT_UTC_END:
        return NIGHT_UTC_START <= hour_of_day < NIGHT_UTC_END
    return hour_of_day >= NIGHT_UTC_START or hour_of_day < NIGHT_UTC_END

def keep_step(h):
    """Profil d'échéances (débogage 20/07/2026, retour Yann) : horaire
    TOUTE la journée, 1 échéance sur COARSE_EVERY seulement pendant la
    fenêtre nuit (is_night_utc, sur l'heure UTC RÉELLE run+h — pas un
    seuil fixe d'heures écoulées comme l'ancien FINE_H, qui pouvait
    tomber en pleine journée de vol selon l'heure du run)."""
    if h == 0:
        return True  # état initial toujours gardé, même si le run tombe la nuit
    if _RUN_HOUR_UTC is None:
        return h <= FINE_H or h % COARSE_EVERY == 0  # filet de sécurité, ne devrait pas arriver
    if is_night_utc((_RUN_HOUR_UTC + h) % 24):
        return h % COARSE_EVERY == 0
    return True

def sample_indices(meta, step):
    """Indices (j, i) + (lat, lon) échantillonnés à `step` dans BBOX, depuis la
    grille native AROME (décimation entière step/di)."""
    dec = max(1, round(step / meta["di"]))
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
    """u,v (m/s) -> (vitesse km/h, direction météo = d'où vient le vent).

    Débogage 19/07/2026 — garde-fou ajouté : en échantillonnant au pas
    NATIF (0,025°) on touche des points que la décimation précédente
    sautait, dont d'éventuels points manquants du GRIB (NaN, ou la valeur
    sentinelle 9999 d'eccodes). Un NaN sérialisé par json.dumps donne le
    littéral `NaN` — du JSON INVALIDE, rejeté à l'écriture. On renvoie
    None (le client sait déjà ignorer un point null) plutôt que de
    produire un fichier corrompu."""
    if u is None or v is None:
        return None, None
    spd = math.hypot(u, v) * 3.6
    if not math.isfinite(spd) or spd > 500:      # 500 km/h : sentinelle/aberration
        return None, None
    drc = (270 - math.degrees(math.atan2(v, u))) % 360
    if not math.isfinite(drc):
        return None, None
    return round(spd, 1), round(drc)

def build_grids(uv_by_step, meta, steps, times, kind, level, step_deg, orog=None):
    """Construit les WindGrid par tuile 2° pour un (kind, level) donné.
    uv_by_step: {step: (U_values, V_values)}. Retourne {(tLat,tLon): dict WindGrid}.
    orog (grille ALT uniquement, cf. load_orography) : grille d'élévation AROME
    pour attacher `elev` à chaque point (masquage sous-relief côté client,
    retour Yann 21/07)."""
    pts = sample_indices(meta, step_deg)
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
        pt = dict(lat=lat, lon=lon, speed=speed, dir=dir_)
        if orog is not None:
            e = elev_at(orog, lat, lon)
            if e is not None:
                pt["elev"] = e
        g["points"].append(pt)
    return tiles

# ── Upload Supabase Storage ───────────────────────────────────────────
def sb_upload(path, body, tries=3, cache_control="no-cache, must-revalidate"):
    """Téléverse un objet. Débogage 19/07/2026 : la version précédente
    laissait remonter un `HTTPError: 400` NU, sans le corps de réponse —
    donc impossible de savoir ce que Supabase reprochait. On journalise
    désormais le message, et on réessaie (POST puis PUT : selon les
    versions de storage-api, un upsert refusé remonte un 400 plutôt qu'un
    409, et PUT passe alors sans ambiguïté).

    Débogage 24/07/2026 (retour Yann : calques vent sol/altitude figés sur
    certains ordis, données bloquées à échéance passée, hard-refresh sans
    effet — mobile OK). Root cause : ce bucket n'a QUE des objets réécrits
    EN PLACE à chaque run (tuiles sol/alt + manifest.json, même chemin) —
    aucun n'est "immuable" comme les geojson isobares par échéance.
    L'ancien `Cache-Control: max-age=10800` (calé sur la cadence 3h du
    run) reproduisait le bug déjà identifié sur le manifest isobares (cf.
    BUGS.md, session 23-24/07, "leçon générale à retenir" : un objet
    Storage réécrit doit avoir un cache court/no-cache, jamais un TTL
    long — un client ayant mis en cache juste avant un nouveau run reste
    bloqué sur l'ancien jusqu'à expiration du TTL LOCAL, et un edge CDN
    peut rester figé plus longtemps encore, indépendamment d'un
    hard-refresh côté client). `no-cache, must-revalidate` par défaut :
    revalidation systématique (conditionnelle via ETag, pas un aller-
    retour plein à chaque fois) plutôt qu'une fraîcheur supposée 3h."""
    if DRY_RUN:
        return 0
    url = f"{SB_URL}/storage/v1/object/{BUCKET}/{path}"
    last = None
    for attempt in range(tries):
        req = urllib.request.Request(
            url, data=body, method=("POST" if attempt == 0 else "PUT"), headers={
                "Authorization": f"Bearer {SB_KEY}", "apikey": SB_KEY,
                "Content-Type": "application/json", "x-upsert": "true",
                "Cache-Control": cache_control})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status
        except urllib.error.HTTPError as e:
            try:
                detail = e.read()[:300].decode("utf-8", "replace")
            except Exception:
                detail = ""
            last = f"HTTP {e.code} — {detail}"
        except Exception as e:                       # réseau, timeout…
            last = f"{type(e).__name__}: {e}"
        print(f"  ⚠️ upload {path} tentative {attempt + 1}/{tries} : {last}")
        time.sleep(1 + 2 * attempt)
    raise SystemExit(f"sb_upload {path} : échec après {tries} tentatives — {last}")

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
    steps = sorted(x for x in (common or set()) if x <= MAX_HOURS and keep_step(x))
    times = [(run + timedelta(hours=s)).strftime("%Y-%m-%dT%H:%M") for s in steps]
    return steps, times

def main():
    global _RUN_HOUR_UTC
    ref, run = latest_run()
    _RUN_HOUR_UTC = run.hour
    print(f"Run AROME : {ref}")
    manifest = dict(run=ref, generatedAt=datetime.now(timezone.utc)
                    .strftime("%Y-%m-%dT%H:%M:%SZ"), gridSol=GRID_SOL, gridAlt=GRID_ALT,
                    tileDeg=TILE_DEG, stepSol=STEP_SOL, stepAlt=STEP_ALT,
                    maxHours=MAX_HOURS, levels=[], uploaded=0)
    total = 0

    # ── SOL (10 m) : paquet SP1, variables 10u/10v ────────────────────
    print("SOL (SP1, 10 m) :")
    sol_want = lambda sn, tol, lvl: sn if (sn in ("10u", "10v")
                                           and tol == "heightAboveGround") else None
    data, meta = merge_parse(files_for(ref, "SP1", GRID_SOL), sol_want)
    data = {("u" if k == "10u" else "v"): v for k, v in data.items()}
    steps, times = steps_times(run, data)
    uv = {s: (data["u"][s], data["v"][s]) for s in steps}
    for (tLat, tLon), grid in build_grids(uv, meta, steps, times, "sol", None, STEP_SOL).items():
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
    print("Orographie (SP3, grille 001, champ 'h') :")
    orog = load_orography(ref)
    if orog is not None:
        print(f"  grille {orog['meta']['Ni']}×{orog['meta']['Nj']} chargée")
    LSET = set(LEVELS)
    alt_want = lambda sn, tol, l: ((sn, l) if (sn in ("u", "v")
                                   and tol == "isobaricInhPa" and l in LSET) else None)
    data, meta = merge_parse(files_for(ref, "IP1", GRID_ALT), alt_want)
    for lvl in LEVELS:
        if ("u", lvl) not in data or ("v", lvl) not in data:
            print(f"  niveau {lvl} hPa absent — ignoré"); continue
        du, dv = data[("u", lvl)], data[("v", lvl)]
        steps = sorted(s for s in (set(du) & set(dv)) if s <= MAX_HOURS and keep_step(s))
        times = [(run + timedelta(hours=s)).strftime("%Y-%m-%dT%H:%M") for s in steps]
        uv = {s: (du[s], dv[s]) for s in steps}
        for (tLat, tLon), grid in build_grids(uv, meta, steps, times, "alt", lvl, STEP_ALT, orog).items():
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
