#!/usr/bin/env python3
"""
Ingestion ARPEGE -> grille zi ("épaisseur couche convective"), modèle ARPEGE.

Script SŒUR de `arome-thermal/ingest.py`, mais volontairement PLUS SIMPLE :
on ne calcule QUE zᵢ (blh, hauteur de couche limite), pas w* — la demande du
23/07/2026 portait sur le calque "Épaisseur couche convective" avec un
sélecteur de modèle AROME/ARPEGE, pas sur le calque "Estimation thermique"
(w*, RASP/BLIPMAP). Se limiter à blh évite toute désaccumulation de sshf
(non vérifiée pour ARPEGE à la bascule hourly -> 3h, cf. section dédiée dans
PROMPT_REPRISE_ARPEGE_CONVECTIF.md) : un champ instantané, pas de piège de
signe/dt possible. Si Yann veut un jour w* pour ARPEGE aussi, ce sera un
script séparé (comme arome-thermal l'est d'arome-wind), pas un ajout ici.

Différences avec arome-thermal/ingest.py :
  - UN SEUL paquet (SP2 : blh, sshf, t dans le même bundle chez ARPEGE,
    contre SP2+SP3 séparés chez AROME) — on ne lit que `blh` dedans.
  - Grille 01 (0,1°, ~11 km) au lieu de 0025 (2,5 km) : calque plus lisse.
  - MAX_HOURS = 102 (vs 51 pour AROME) — mais cadence NON uniforme :
    horaire de h1 à h48, puis seulement tous les 3h (51, 54, ... 102).
    Vérifié en direct le 23/07/2026 sur le run 2026-07-22T18:00:00Z + 6
    autres runs (cf. PROMPT_REPRISE_ARPEGE_CONVECTIF.md) : la bascule est
    nette à la frontière h48/h51, sans trou, stable sur tous les runs
    testés. `native_step()` encode cette règle : h<=48 -> tout est publié,
    h>48 -> seuls les multiples de 3 le sont (49 et 50 ne sont PAS publiés,
    la règle modulo-3 les exclut naturellement, pas besoin de cas
    particulier à la frontière).
  - ARPEGE ne tourne qu'à 00/06/12/18 UTC (4 runs/jour), PAS 8 comme AROME
    sur ce bucket (vérifié : les créneaux 03/09/15/21Z n'ont aucun dossier
    `arpege/`) -> `latest_run()` sonde par pas de 6h, pas 3h.
  - BBOX = Europe entière (choix Yann 23/07/2026, plutôt que se limiter à
    la BBOX France d'AROME) : ~962 tuiles 2°x2° générées par run contre
    ~54 pour le calque AROME (France uniquement) — 18x plus d'uploads
    Supabase Storage par run. À surveiller au premier run réel (temps
    d'exécution, quota API Storage) ; réduire la BBOX si ça pose problème
    est un simple changement de constante, pas une réécriture.
  - Tuiles publiées sous `wind-grid/arpege/thermal/` (PAS `arome/thermal/`)
    : calque distinct, ne remplace rien.

Variables d'environnement requises (secrets GitHub), identiques à
arome-thermal/ingest.py :
  SUPABASE_URL, SUPABASE_SERVICE_KEY   (WIND_GRID_BUCKET optionnel, défaut wind-grid)
  DRY_RUN=1 pour tester le calcul/tuilage sans téléverser.
"""
import os, re, json, math, time, tempfile, urllib.parse, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from eccodes import (codes_grib_new_from_file, codes_get, codes_get_values,
                     codes_release)

# ── Config (à garder synchronisé avec web/src/lib/config.ts) ──────────
S3        = "https://meteofrance-pnt.s3.rbx.io.cloud.ovh.net"
MODEL_DIR = "arpege"
GRID      = "01"
# 102h : plafond confirmé STABLE sur 7 runs différents le 23/07/2026 (pas
# juste un nom de fichier vu une fois, cf. piège découvert sur AROME
# 48 vs 51 vs 54). Cadence non uniforme au-delà de h48, cf. native_step().
MAX_HOURS = 102
# Europe entière (grille source native), choix Yann 23/07/2026 — cf.
# note ci-dessus sur le volume de tuiles. Bornes = extension réelle de la
# grille ARPEGE 01 (vérifiée en direct : Ni=741, Nj=521,
# lat0=72.0, lon0=-32.0(=328°), lat1=20.0, lon1=42.0).
BBOX      = dict(latmin=20.0, latmax=72.0, lonmin=-32.0, lonmax=42.0)
# Pas natif, aucune décimation (0,1° déjà 2x plus grossier que le 0,05°
# d'AROME thermal — la couche limite est un champ lisse, pas besoin de
# sous-échantillonner davantage).
STEP_DEG  = 0.1
TILE_DEG  = 2                       # = WIND_GRID_TILE_DEG côté client
MODEL_KEY = "arpege_seamless"        # cf. types/openmeteo.ts (OpenMeteoModelKey)

# Fenêtre UTC "jour" — IDENTIQUE à arome-thermal (choix explicite de Yann le
# 23/07/2026 : garder le même filtre jour-only sur ce calque pour ARPEGE,
# ne pas ouvrir la question de la nuit malgré la portée bien plus longue).
DAY_UTC_START, DAY_UTC_END = 4, 19

DRY_RUN = os.environ.get("DRY_RUN") == "1"
SB_URL  = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")
BUCKET  = os.environ.get("WIND_GRID_BUCKET", "wind-grid")
if not DRY_RUN and not (SB_URL and SB_KEY):
    raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants (ou DRY_RUN=1)")

_RUN_HOUR_UTC = None        # défini dans main(), cf. keep_step()


# ── HTTP / S3 helpers (identiques à arome-thermal/ingest.py) ──────────
def http_get(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "balise-watch-arpege/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def s3_keys(prefix):
    url = f"{S3}/?list-type=2&prefix={urllib.parse.quote(prefix)}&max-keys=1000"
    root = ET.fromstring(http_get(url, 60))
    return [e.text for e in root.iter() if e.tag.split('}')[-1] == "Key"]

def latest_run():
    """Dernier run ARPEGE dont le paquet SP2 (grille 01) est publié.

    ARPEGE ne tourne qu'à 00/06/12/18 UTC sur ce bucket (vérifié en direct
    le 23/07/2026 : les créneaux 03/09/15/21Z n'ont aucun dossier `arpege/`,
    contrairement à AROME qui y est répliqué 8x/jour) -> on sonde par pas
    de 6h, pas 3h comme arome-thermal, sinon on retesterait 2 fois sur 3 un
    créneau qui ne publiera jamais rien."""
    base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    base -= timedelta(hours=base.hour % 6)
    for back in range(8):                       # jusqu'à 48h en arrière
        run = base - timedelta(hours=6 * back)
        ref = run.strftime("%Y-%m-%dT%H:00:00Z")
        if s3_keys(f"pnt/{ref}/{MODEL_DIR}/{GRID}/SP2/"):
            return ref, run
    raise SystemExit("Aucun run ARPEGE SP2 publié sur les 48 dernières heures")

def is_day_utc(hour_of_day):
    """Fenêtre [DAY_UTC_START, DAY_UTC_END[ — ne traverse PAS minuit."""
    return DAY_UTC_START <= hour_of_day < DAY_UTC_END

def native_step(h):
    """Échéances RÉELLEMENT publiées par Météo-France pour ARPEGE/SP2/blh.

    Vérifié en direct le 23/07/2026 (décodage de bundles réels, pas
    déduit des noms de fichiers) : horaire de h1 à h48 inclus, puis
    UNIQUEMENT les multiples de 3 de h51 à h102 (51,54,...,99,102). h49 et
    h50 ne sont PAS publiés (bundle 049H060H ne contenait que 51/54/57/60,
    pas 12 échéances comme le nom le suggérerait) — la règle `h % 3 == 0`
    les exclut naturellement pour h>48, sans cas particulier à écrire :
    49 % 3 = 1, 50 % 3 = 2, ni l'un ni l'autre n'est retenu."""
    if h < 0 or h > MAX_HOURS:
        return False
    if h <= 48:
        return True
    return h % 3 == 0

def keep_step(h):
    """Échéances retenues pour la sortie : natives ET de jour."""
    if not native_step(h):
        return False
    if _RUN_HOUR_UTC is None:
        return True                              # filet, ne devrait pas arriver
    return is_day_utc((_RUN_HOUR_UTC + h) % 24)

def files_for(ref, pkg, steps_needed):
    """Bundles du paquet couvrant les échéances nécessaires.

    Même logique qu'arome-thermal (ne télécharge que les bundles utiles),
    mais bundles de largeur variable côté ARPEGE (12-13h en général, 5h
    pour le dernier `097H102H`) plutôt que 6h fixe chez AROME — le parsing
    du nom de fichier (regex) est identique, seule la largeur change."""
    want = set(steps_needed)
    out = []
    for k in s3_keys(f"pnt/{ref}/{MODEL_DIR}/{GRID}/{pkg}/"):
        m = re.search(r"__(\d+)H(?:(\d+)H)?__", k)
        if not m:
            continue
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else start
        if start > MAX_HOURS:
            continue
        if not any(start <= h <= end for h in want):
            continue
        out.append(k)
    return sorted(out)


# ── Grille / indexation (identique à arome-thermal) ───────────────────
def _norm_lon(x):
    """ARPEGE publie aussi en convention 0-360° (cf. piège _norm_lon dans
    arome-thermal/ingest.py, NOTES_TECHNIQUES_THERMIQUES_AROME.md)."""
    return x - 360 if x > 180 else x

def grid_meta(gid):
    return dict(
        Ni=codes_get(gid, "Ni"), Nj=codes_get(gid, "Nj"),
        lat0=codes_get(gid, "latitudeOfFirstGridPointInDegrees"),
        lon0=_norm_lon(codes_get(gid, "longitudeOfFirstGridPointInDegrees")),
        di=codes_get(gid, "iDirectionIncrementInDegrees"),
        dj=codes_get(gid, "jDirectionIncrementInDegrees"),
        jScan=codes_get(gid, "jScansPositively"))

def sample_points(meta):
    """[(index_plat, lat, lon)] échantillonnés à STEP_DEG dans la BBOX.

    STEP_DEG == di natif ici (0,1°) -> dec = 1, aucune décimation : on
    garde tous les points natifs de la BBOX (Europe entière -> ~380 000
    points bruts avant filtrage BBOX, cf. note volume en tête de fichier)."""
    dec = max(1, round(STEP_DEG / meta["di"]))
    pts = []
    for j in range(0, meta["Nj"], dec):
        lat = meta["lat0"] + (meta["dj"] * j if meta["jScan"] == 1 else -meta["dj"] * j)
        if not (BBOX["latmin"] <= lat <= BBOX["latmax"]):
            continue
        for i in range(0, meta["Ni"], dec):
            lon = meta["lon0"] + meta["di"] * i
            if BBOX["lonmin"] <= lon <= BBOX["lonmax"]:
                assert 0 <= i < meta["Ni"] and 0 <= j < meta["Nj"], (i, j)
                pts.append((j * meta["Ni"] + i, round(lat, 3), round(lon, 3)))
    return pts

# ── Parsing GRIB ──────────────────────────────────────────────────────
def parse_grib(path, steps_needed, state):
    """Décode un bundle et n'en garde QUE `blh`, aux points échantillonnés.

    Contrairement à arome-thermal, un seul champ à filtrer (`wanted` figé
    à {"blh"}) : pas de `sshf`/`t` à extraire pour ce calque zi-only."""
    want_steps = set(steps_needed)
    with open(path, "rb") as f:
        while True:
            gid = codes_grib_new_from_file(f)
            if gid is None:
                break
            try:
                sn = codes_get(gid, "shortName")
                st = codes_get(gid, "step")
                if sn != "blh" or st not in want_steps:
                    continue
                if state["meta"] is None:
                    state["meta"] = grid_meta(gid)
                    state["pts"] = sample_points(state["meta"])
                    print(f"  grille {state['meta']['Ni']}x{state['meta']['Nj']}, "
                          f"lon0={state['meta']['lon0']} -> {len(state['pts'])} points échantillonnés")
                vals = codes_get_values(gid)
                state["data"][st] = [vals[k] for k, _, _ in state["pts"]]
            finally:
                codes_release(gid)

def download_tmp(key):
    url = f"{S3}/{urllib.parse.quote(key)}"
    fd, path = tempfile.mkstemp(suffix=".grib2")
    os.close(fd)
    t0 = time.time()
    with urllib.request.urlopen(urllib.request.Request(
            url, headers={"User-Agent": "balise-watch-arpege/1"}), timeout=300) as r, \
            open(path, "wb") as out:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
    print(f"  ↓ {key.split('/')[-1]} ({os.path.getsize(path)//(1<<20)} Mo, {time.time()-t0:.1f}s)")
    return path

def fetch_parse(ref, pkg, steps_needed, state):
    for key in files_for(ref, pkg, steps_needed):
        p = download_tmp(key)
        try:
            parse_grib(p, steps_needed, state)
        finally:
            os.unlink(p)


# ── Tuilage ────────────────────────────────────────────────────────────
def build_tiles(state, kept, times):
    """{(tLat,tLon): dict tuile} — même structure que ThermalGrid côté
    client, mais `wstar` toujours `null` (pas calculé ici, cf. docstring
    de tête) : ConvectiveDepthLayer.tsx ne lit que `.zi`."""
    d = state["data"]
    tiles = {}
    for p, (_, lat, lon) in enumerate(state["pts"]):
        tLat = math.floor(lat / TILE_DEG) * TILE_DEG
        tLon = math.floor(lon / TILE_DEG) * TILE_DEG
        g = tiles.get((tLat, tLon))
        if g is None:
            g = tiles[(tLat, tLon)] = dict(
                model=MODEL_KEY, kind="thermal", tileLat=tLat, tileLon=tLon,
                times=times, points=[])
        zs = []
        for h in kept:
            vals = d.get(h)
            z = None
            if vals is not None:
                zi = vals[p]
                if math.isfinite(zi) and 0 <= zi <= 8000:
                    z = round(zi / 10) * 10
            zs.append(z)
        g["points"].append(dict(lat=lat, lon=lon, wstar=[None] * len(kept), zi=zs))
    return tiles

# ── Upload Supabase Storage (identique à arome-thermal/ingest.py) ─────
def sb_upload(path, body, tries=3, cache_control="no-cache, must-revalidate"):
    """Débogage 24/07/2026 : même bug que `arome-wind/ingest.py` (cf.
    BUGS.md session 24/07, calques vent figés sur certains ordis) — ce
    bucket n'a que des objets réécrits EN PLACE à chaque run (tuiles
    `thermal/{lat}_{lon}.json` + `thermal/manifest.json`, même chemin,
    aucun horodatage dans le nom), donc rien d'"immuable" ici. L'ancien
    `Cache-Control: max-age=10800` pouvait laisser un navigateur/CDN
    servir une tuile périmée bien après un nouveau run, sans que le
    hard-refresh corrige (comportement d'edge CDN, hors de portée du
    client). `no-cache, must-revalidate` par défaut : revalidation
    conditionnelle systématique plutôt qu'une fraîcheur supposée 3h."""
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
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
        print(f"  ⚠️ upload {path} tentative {attempt + 1}/{tries} : {last}")
        time.sleep(1 + 2 * attempt)
    raise SystemExit(f"sb_upload {path} : échec après {tries} tentatives — {last}")


# ── main ──────────────────────────────────────────────────────────────
def main():
    global _RUN_HOUR_UTC
    ref, run = latest_run()
    _RUN_HOUR_UTC = run.hour
    print(f"Run ARPEGE : {ref} (run à {_RUN_HOUR_UTC}h UTC)")

    kept = [h for h in range(0, MAX_HOURS + 1) if keep_step(h)]
    if not kept:
        print("Aucune échéance de jour dans l'horizon — rien à produire.")
        return
    times = [(run + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in kept]
    print(f"{len(kept)} échéances de jour retenues ({kept[0]}h→{kept[-1]}h) sur "
          f"un horizon de {MAX_HOURS}h")

    state = dict(meta=None, pts=None, data={})
    print("SP2 (blh) :")
    fetch_parse(ref, "SP2", kept, state)

    kept_avail = [h for h in kept if h in state["data"]]
    if not kept_avail:
        raise SystemExit("Aucune échéance exploitable après parsing (blh absent "
                         "partout) — run réellement cassé, on abandonne.")
    if len(kept_avail) < len(kept):
        holes = sorted(set(kept) - set(kept_avail))
        print(f"  ⚠️ {len(holes)} échéance(s) pas encore publiée(s) côté Météo-France, "
              f"écartée(s) : {holes[:10]}{' …' if len(holes) > 10 else ''} — "
              f"publication des {len(kept_avail)} échéances disponibles, le run "
              f"suivant complètera.")
    kept = kept_avail
    times = [(run + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in kept]

    total = 0
    for (tLat, tLon), grid in build_tiles(state, kept, times).items():
        grid["fetchedAt"] = int(time.time() * 1000)
        sb_upload(f"{MODEL_DIR}/thermal/{tLat}_{tLon}.json",
                  json.dumps(grid, separators=(",", ":")).encode())
        total += 1

    manifest = dict(run=ref, generatedAt=datetime.now(timezone.utc)
                    .strftime("%Y-%m-%dT%H:%M:%SZ"), grid=GRID, tileDeg=TILE_DEG,
                    step=STEP_DEG, maxHours=MAX_HOURS, times=times, uploaded=total,
                    dayUtc=[DAY_UTC_START, DAY_UTC_END])
    sb_upload(f"{MODEL_DIR}/thermal/manifest.json", json.dumps(manifest).encode())
    print(f"Terminé : {total} tuiles + manifest "
          f"{'(DRY_RUN, rien téléversé)' if DRY_RUN else f'téléversés dans {BUCKET}'}.")

if __name__ == "__main__":
    main()
