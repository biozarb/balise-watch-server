#!/usr/bin/env python3
"""
Ingestion ARPEGE -> calque isobares (Europe + monde, passé -> prévision).

Source : Open-Meteo AWS Open Data (`s3://openmeteo`, gratuit, sans clé,
licence CC-BY-4.0), layout `data_spatial/` — PAS le bucket meteofrance-pnt
(OVH) utilisé pour AROME : celui-ci ne contient QUE de l'AROME, vérifié en
direct le 23/07/2026 (cf. NOTES_TECHNIQUES_THERMIQUES_AROME.md, addendum).

Format des fichiers source : `.om` (PAS du GRIB2), lu via le package `omfiles`
+ `fsspec` (lecture par blocs — un fichier ~19 Mo, on n'en télécharge que la
variable voulue, ~350 Ko mesuré). Variable `pressure_msl`, déjà en hPa.

Deux grilles traitées indépendamment (retour Yann 23/07 : ARPEGE partout,
pas besoin d'AROME localement pour un phénomène synoptique) :
  - meteofrance_arpege_europe   0,1°  (~11 km), BBOX Europe
  - meteofrance_arpege_world025 0,25° (~25 km), BBOX monde

Deux portions temporelles, séries INDÉPENDANTES du module de temps
vent/thermique existant (retour Yann 23/07 : « on ne touche pas au reste ») :
  - PASSÉ : un point toutes les 6 h (cadence des runs ARPEGE), en remontant
    tant que le fichier existe encore chez Open-Meteo (~9 jours observés le
    23/07 — « le max de ce que nous permet Open-Meteo », retour Yann).
    Chaque run passé n'est lu qu'à son échéance 0 (ce que CE run a produit
    pour SA propre heure de référence = le plus proche d'un état observé
    qu'on puisse obtenir sans réanalyse dédiée).
  - PRÉVISION : échéances de `valid_times` du run le plus récent
    (`latest.json`), horaire jusqu'à +48 h puis toutes les 3 h au-delà
    (même esprit de dégressivité que arome-wind/ingest.py, sur un horizon
    ARPEGE ~4 jours).

Isobares : contourage tous les 5 hPa (convention météo classique, retour
Yann 23/07) via matplotlib (backend Agg, pas d'affichage).

Sortie : GeoJSON (FeatureCollection de LineString, propriété `hpa`) par
échéance, + un manifest par grille listant les échéances disponibles (même
esprit que arome-wind/ingest.py) — Supabase Storage, bucket `isobars`.

Variables d'environnement requises (secrets GitHub) :
  SUPABASE_URL, SUPABASE_SERVICE_KEY   (ISOBARS_BUCKET optionnel, défaut isobars)
"""
import os, json, time, re, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import fsspec
from omfiles import OmFileReader
from scipy.ndimage import minimum_filter, maximum_filter

OM_BUCKET = "openmeteo"
MODELS = {
    "arpege_europe": "meteofrance_arpege_europe",
    "arpege_world":  "meteofrance_arpege_world025",
}
LEVEL_STEP_HPA = 5
FUTURE_HOURLY_UNTIL = 48      # horaire jusque-là, puis coarse
FUTURE_COARSE_EVERY = 3
PAST_STEP_HOURS = 6            # cadence des runs ARPEGE
PAST_MAX_RUNS = 60             # garde-fou dur (~15 jours) — la vraie limite
                                # est la 1ère lecture en échec (rétention réelle)

# Centres de pression (L/H), pour l'animation du sens de rotation du vent
# côté frontend (retour Yann 23/07). Fenêtre glissante simple (pas de scipy) :
# un point est un centre s'il est le min/max strict de son voisinage.
CENTER_WINDOW_DEG = 4.0         # rayon de la fenêtre de recherche (°) — assez
                                 # large pour ignorer le bruit de petite échelle
CENTER_MIN_SEPARATION_DEG = 6.0 # fusionne les centres détectés trop proches
MAX_CENTERS_PER_KIND = 6        # évite la surcharge visuelle (surtout grille monde)

DRY_RUN = os.environ.get("DRY_RUN") == "1"
SB_URL  = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")
BUCKET  = os.environ.get("ISOBARS_BUCKET", "isobars")
if not DRY_RUN and not (SB_URL and SB_KEY):
    raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants (ou DRY_RUN=1)")

# ── Lecture Open-Meteo (.om) ───────────────────────────────────────────
def http_get_json(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "balise-watch-isobars/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())

def latest_json(model):
    """`data_spatial/<model>/latest.json` — run le plus récent COMPLET,
    avec la liste des échéances de prévision déjà publiées (`valid_times`)."""
    return http_get_json(f"https://{OM_BUCKET}.s3.amazonaws.com/data_spatial/{model}/latest.json")

_BBOX_RE = re.compile(r"BBOX\[([-\d.]+),([-\d.]+),([-\d.]+),([-\d.]+)\]")

def read_pressure(model, dt_utc):
    """Lit `pressure_msl` (grille complète, hPa) pour un modèle Open-Meteo
    à un instant (run initial OU échéance de prévision — même fichier
    `data_spatial/<model>/<run>/<timestamp>.om`, le nommage ne distingue
    pas les deux). Retourne (lon2d, lat2d, pressure) ou None si absent
    (fichier purgé / pas encore publié — pas une erreur, cf. appelants)."""
    run_dir = dt_utc.strftime("%Y/%m/%d/%H00Z")
    fname = dt_utc.strftime("%Y-%m-%dT%H%M")
    uri = f"s3://{OM_BUCKET}/data_spatial/{model}/{run_dir}/{fname}.om"
    backend = fsspec.open(
        f"blockcache::{uri}", mode="rb",
        s3={"anon": True, "default_block_size": 65536},
        blockcache={"cache_storage": "/tmp/om_cache_isobars"},
    )
    try:
        with OmFileReader(backend) as root:
            p = root.get_child_by_name("pressure_msl")
            pressure = p.read_array((...))
            bbox = _BBOX_RE.search(root.get_child_by_name("crs_wkt").read_scalar())
            south, west, north, east = (float(x) for x in bbox.groups())
    except FileNotFoundError:
        return None
    nj, ni = pressure.shape
    lat = np.linspace(north, south, nj)     # jScan descendant, cf. NOTES_TECHNIQUES
    lon = np.linspace(west, east, ni)
    lon2d, lat2d = np.meshgrid(lon, lat)
    return lon2d, lat2d, pressure

# ── Contourage ─────────────────────────────────────────────────────────
def isobars_geojson(lon2d, lat2d, pressure):
    """Contourage tous les LEVEL_STEP_HPA hPa -> GeoJSON FeatureCollection
    de LineString (une feature par segment de contour, propriété `hpa`).
    matplotlib fait le travail numérique (marching squares) ; on ne fait
    que relire ses segments, rien n'est affiché (backend Agg)."""
    pmin, pmax = float(np.nanmin(pressure)), float(np.nanmax(pressure))
    lo = np.floor(pmin / LEVEL_STEP_HPA) * LEVEL_STEP_HPA
    hi = np.ceil(pmax / LEVEL_STEP_HPA) * LEVEL_STEP_HPA + LEVEL_STEP_HPA
    levels = np.arange(lo, hi, LEVEL_STEP_HPA)

    fig, ax = plt.subplots()
    cs = ax.contour(lon2d, lat2d, pressure, levels=levels)
    features = []
    # matplotlib >=3.8 : cs.allsegs reste disponible (API contour "legacy"),
    # cf. cs.levels pour la valeur hPa de chaque jeu de segments.
    for level, segs in zip(cs.levels, cs.allsegs):
        for seg in segs:
            if len(seg) < 2:
                continue
            features.append({
                "type": "Feature",
                "properties": {"hpa": round(float(level))},
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[round(float(x), 3), round(float(y), 3)] for x, y in seg],
                },
            })
    plt.close(fig)
    return {"type": "FeatureCollection", "features": features}

def find_centers(lon2d, lat2d, pressure):
    """Repère les centres de basse/haute pression : un point est un centre
    s'il est le min/max strict de son voisinage (fenêtre CENTER_WINDOW_DEG).
    Filtre exhaustif (scipy.ndimage min/max_filter, vectorisé) — PAS un
    sous-échantillonnage : un test naïf par pas de grille a raté le vrai
    minimum d'une carte (932 hPa non détecté) en ne testant qu'un point sur
    N, cf. vérif locale 23/07/2026. Fusionne ensuite les détections proches
    et ne garde que les MAX_CENTERS_PER_KIND plus marqués par type (le plus
    loin de 1013,25 hPa d'abord). Le sens de rotation du vent (cyclonique/
    anticyclonique) n'est PAS calculé ici : il ne dépend que du type (L/H)
    et de l'hémisphère (signe de `lat`), donc c'est le frontend qui
    l'applique au moment du rendu."""
    lat1d, lon1d = lat2d[:, 0], lon2d[0, :]
    nj, ni = pressure.shape
    dlat = abs(lat1d[0] - lat1d[-1]) / max(nj - 1, 1)
    dlon = abs(lon1d[0] - lon1d[-1]) / max(ni - 1, 1)
    hw_j = max(1, round(CENTER_WINDOW_DEG / dlat)) if dlat else 1
    hw_i = max(1, round(CENTER_WINDOW_DEG / dlon)) if dlon else 1
    size = (2 * hw_j + 1, 2 * hw_i + 1)

    local_min = minimum_filter(pressure, size=size, mode="nearest")
    local_max = maximum_filter(pressure, size=size, mode="nearest")
    is_low = pressure <= local_min
    is_high = pressure >= local_max

    candidates = {
        "L": [(float(lat2d[j, i]), float(lon2d[j, i]), float(pressure[j, i]))
              for j, i in zip(*np.where(is_low))],
        "H": [(float(lat2d[j, i]), float(lon2d[j, i]), float(pressure[j, i]))
              for j, i in zip(*np.where(is_high))],
    }

    centers = []
    for kind, pts in candidates.items():
        pts.sort(key=lambda p: abs(p[2] - 1013.25), reverse=True)  # + extrême d'abord
        kept = []
        for lat, lon, hpa in pts:
            if any(abs(lat - k[0]) < CENTER_MIN_SEPARATION_DEG and
                   abs(lon - k[1]) < CENTER_MIN_SEPARATION_DEG for k in kept):
                continue  # trop proche d'un centre déjà retenu (plus marqué)
            kept.append((lat, lon, hpa))
            if len(kept) >= MAX_CENTERS_PER_KIND:
                break
        centers += [{"kind": kind, "lat": round(lat, 2), "lon": round(lon, 2),
                     "hpa": round(hpa, 1)} for lat, lon, hpa in kept]
    return centers

# ── Upload Supabase Storage (mêmes conventions que arome-wind/ingest.py) ─
def sb_upload(path, body, tries=3):
    if DRY_RUN:
        return 0
    url = f"{SB_URL}/storage/v1/object/{BUCKET}/{path}"
    last = None
    for attempt in range(tries):
        req = urllib.request.Request(
            url, data=body, method=("POST" if attempt == 0 else "PUT"), headers={
                "Authorization": f"Bearer {SB_KEY}", "apikey": SB_KEY,
                "Content-Type": "application/json", "x-upsert": "true",
                # passé = immuable (un run ne change jamais rétroactivement),
                # cache long ; le futur sera de toute façon réécrit au run
                # suivant (6h) donc ce cache n'a pas besoin d'être plus court.
                "Cache-Control": "max-age=21600"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.status
        except urllib.error.HTTPError as e:
            try:
                detail = e.read()[:300].decode("utf-8", "replace")
            except Exception:
                detail = ""
            last = f"HTTP {e.code} — {detail}"
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        print(f"  ⚠️ upload {path} tentative {attempt + 1}/{tries} : {last}")
        time.sleep(1 + 2 * attempt)
    raise SystemExit(f"sb_upload {path} : échec après {tries} tentatives — {last}")

def sb_exists(path):
    """Évite de recontourer un passé déjà téléversé (immuable) — un simple
    HEAD, pas de retry : une erreur réseau ici doit juste faire retenter
    l'upload, pas planter le run."""
    if DRY_RUN:
        return False
    req = urllib.request.Request(
        f"{SB_URL}/storage/v1/object/info/{BUCKET}/{path}",
        headers={"Authorization": f"Bearer {SB_KEY}", "apikey": SB_KEY})
    try:
        urllib.request.urlopen(req, timeout=15)
        return True
    except Exception:
        return False

# ── Construction de la série temporelle (passé + prévision) ────────────
def future_times(reference_time, valid_times):
    """Coarsening dégressif (même esprit que arome-wind : horaire proche,
    plus espacé loin) — sur les `valid_times` déjà publiées par le run,
    pas besoin de deviner l'horizon max, `latest.json` le donne tel quel."""
    out = []
    for iso in valid_times:
        dt = datetime.strptime(iso, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
        h = round((dt - reference_time).total_seconds() / 3600)
        if h <= FUTURE_HOURLY_UNTIL or h % FUTURE_COARSE_EVERY == 0:
            out.append(dt)
    return out

def past_times(reference_time, model):
    """Remonte de PAST_STEP_HOURS en PAST_STEP_HOURS depuis le run courant,
    tant que le fichier existe encore côté Open-Meteo. Le premier échec de
    lecture EST la limite de rétention réelle (~9 jours observés le
    23/07/2026) — pas une valeur qu'on fige en dur, elle peut varier."""
    out, dt = [], reference_time - timedelta(hours=PAST_STEP_HOURS)
    for _ in range(PAST_MAX_RUNS):
        if read_pressure(model, dt) is None:
            break
        out.append(dt)
        dt -= timedelta(hours=PAST_STEP_HOURS)
    out.reverse()
    return out

def process_grid(key, model):
    print(f"— {key} ({model}) —")
    meta = latest_json(model)
    reference_time = datetime.strptime(
        meta["reference_time"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

    past = past_times(reference_time, model)
    future = future_times(reference_time, meta["valid_times"])
    all_times = past + future
    print(f"  run de référence {reference_time.isoformat()} — "
          f"{len(past)} pt passé / {len(future)} pt prévision")

    manifest_times, done = [], 0
    for dt in all_times:
        iso = dt.strftime("%Y-%m-%dT%H:%M")
        obj_path = f"{key}/{iso}.json"
        is_past = dt < reference_time
        if is_past and sb_exists(obj_path):
            manifest_times.append(iso)      # déjà là, immuable, on ne refait rien
            continue
        result = read_pressure(model, dt)
        if result is None:
            print(f"  ⚠️ {iso} absent (purgé ou pas encore publié) — ignoré")
            continue
        geo = isobars_geojson(*result)
        geo["centers"] = find_centers(*result)
        sb_upload(obj_path, json.dumps(geo, separators=(",", ":")).encode())
        manifest_times.append(iso)
        done += 1
    print(f"  {done} échéance(s) (re)calculée(s), {len(manifest_times)} au total")

    manifest = dict(
        model=model, referenceTime=reference_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        generatedAt=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        levelStepHpa=LEVEL_STEP_HPA, times=manifest_times,
        nowIndex=len(manifest_times) - len(future))  # frontend : jalon "maintenant"
    sb_upload(f"{key}/manifest.json", json.dumps(manifest).encode())
    return done

def main():
    total = 0
    for key, model in MODELS.items():
        total += process_grid(key, model)
    print(f"Terminé : {total} échéance(s) (re)calculée(s) au total dans '{BUCKET}'.")

if __name__ == "__main__":
    main()
