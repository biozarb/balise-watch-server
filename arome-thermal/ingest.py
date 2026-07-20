#!/usr/bin/env python3
"""
Ingestion AROME -> grille THERMIQUE (calque "estimation thermique", vue 3D).

Script SŒUR de `arome-wind/ingest.py`, volontairement séparé : les paquets
SP2/SP3 en grille 0025 n'ont rien de commun avec SP1/IP1 (autres champs, autre
profil horaire, désaccumulation nécessaire). Les mélanger aurait alourdi un
fichier déjà dense sans rien mutualiser d'utile.

Calcule la VITESSE VERTICALE CONVECTIVE w* (formule RASP/BLIPMAP, Dr Jack
Glendening — reprise par Skysight, soaringmeteo, meteoblue) :

    w* = [ (g/T₀) · (H₀ / (ρ·cp)) · zᵢ ]^(1/3)

    zᵢ = blh   (hauteur de couche limite, m)          -> paquet SP2
    H₀ = sshf  (flux de chaleur sensible au sol, W/m²) -> paquet SP3, CUMULÉ
    T₀ = t     (température de surface, K)             -> paquet SP2

Publie des tuiles 2°×2° dans Supabase Storage (bucket `wind-grid`, sous-dossier
`arome/thermal/`), même tuilage et même BBOX que le calque vent.

⚠️ CE CHAMP EST UNE ESTIMATION, pas une observation. Il est présenté comme tel
   dans l'UI ("estimation thermique", jamais "thermiques"). Voir
   NOTES_TECHNIQUES_THERMIQUES_AROME.md pour la validation numérique.

Variables d'environnement requises (secrets GitHub) :
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
MODEL_DIR = "arome"
# Grille 0025 (2,5 km) UNIQUEMENT. `blh` et `sshf` n'existent PAS dans la
# grille 001 (vérifié empiriquement, cf. NOTES_TECHNIQUES) : le champ est
# donc plafonné à 2,5 km de toute façon, inutile de payer le poids de la
# grille fine pour les champs qui y sont (CAPE, t).
GRID      = "0025"
MAX_HOURS = 48
BBOX      = dict(latmin=41.0, latmax=52.0, lonmin=-6.0, lonmax=11.0)  # = arome-wind
# Pas d'échantillonnage : 0,05° comme le vent ALTITUDE (1 point sur 2 de la
# grille native 0,025°). w*/zᵢ sont des champs lisses à l'échelle de la
# couche limite — le pas natif n'apporterait pas d'information réelle, juste
# ×4 le poids des tuiles.
STEP_DEG  = 0.05
TILE_DEG  = 2                       # = WIND_GRID_TILE_DEG côté client
MODEL_KEY = "meteofrance_seamless"

# Fenêtre UTC "jour" — le calque n'a AUCUN sens la nuit (w* → 0 par
# construction : plus de flux de chaleur solaire, donc plus de thermique).
# Profil bien plus économe que le vent, qui garde du 3h nocturne : ici on
# ne produit RIEN hors de cette fenêtre.
#   été  (UTC+2) : 06h-21h locales -> 04h-19h UTC
#   hiver (UTC+1) : 07h-20h locales -> 06h-19h UTC
# Fenêtre retenue 04h-19h UTC : sur-couvre l'hiver plutôt que de risquer de
# couper une fin de journée d'été exploitable.
DAY_UTC_START, DAY_UTC_END = 4, 19

# Constantes physiques (formule w*)
G       = 9.81      # m/s²
RHO     = 1.2       # kg/m³  — masse volumique de l'air près du sol
CP      = 1005.0    # J/kg/K — capacité thermique massique de l'air sec
# Plancher de plausibilité : en dessous, on écrit 0 plutôt qu'un chiffre
# qui suggérerait un thermique exploitable. 0,5 m/s = seuil sous lequel
# aucun parapente ne monte réellement.
WSTAR_MIN = 0.5

DRY_RUN = os.environ.get("DRY_RUN") == "1"
SB_URL  = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY  = os.environ.get("SUPABASE_SERVICE_KEY", "")
BUCKET  = os.environ.get("WIND_GRID_BUCKET", "wind-grid")
if not DRY_RUN and not (SB_URL and SB_KEY):
    raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants (ou DRY_RUN=1)")

_RUN_HOUR_UTC = None        # défini dans main(), cf. keep_step()


# ── HTTP / S3 helpers (identiques à arome-wind/ingest.py) ─────────────
def http_get(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "balise-watch-arome/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def s3_keys(prefix):
    url = f"{S3}/?list-type=2&prefix={urllib.parse.quote(prefix)}&max-keys=1000"
    root = ET.fromstring(http_get(url, 60))
    return [e.text for e in root.iter() if e.tag.split('}')[-1] == "Key"]

def latest_run():
    """Dernier run AROME dont le paquet SP2 (0025) est publié.

    On teste SP2 et pas SP1 (contrairement à arome-wind) : les paquets ne
    sont pas publiés exactement en même temps, et c'est SP2/SP3 qu'il nous
    faut. Vérifier SP1 pourrait faire croire qu'un run est prêt alors que
    nos champs ne le sont pas encore."""
    base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    base -= timedelta(hours=base.hour % 3)
    for back in range(9):                       # jusqu'à 24 h en arrière
        run = base - timedelta(hours=3 * back)
        ref = run.strftime("%Y-%m-%dT%H:00:00Z")
        if s3_keys(f"pnt/{ref}/{MODEL_DIR}/{GRID}/SP2/"):
            return ref, run
    raise SystemExit("Aucun run AROME SP2 publié sur les 24 dernières heures")

def is_day_utc(hour_of_day):
    """Fenêtre [DAY_UTC_START, DAY_UTC_END[ — ne traverse PAS minuit."""
    return DAY_UTC_START <= hour_of_day < DAY_UTC_END

def keep_step(h):
    """Échéances RETENUES pour la sortie : heures de jour uniquement.

    h == 0 est exclu même en journée : `sshf` est un cumul depuis le début
    du run, donc valant 0 à h=0 — impossible d'en tirer un flux (il faut
    h et h−1). Cf. needed_steps() qui ajoute les prédécesseurs."""
    if h <= 0 or h > MAX_HOURS:
        return False
    if _RUN_HOUR_UTC is None:
        return True                              # filet, ne devrait pas arriver
    return is_day_utc((_RUN_HOUR_UTC + h) % 24)

def needed_steps():
    """Échéances à DÉCODER = celles retenues + leur prédécesseur h−1.

    Le prédécesseur n'est jamais publié en sortie : il ne sert qu'à
    désaccumuler `sshf`. Oublier cette étape est le piège n°1 de ce script
    (on obtiendrait un cumul depuis le début du run à la place d'un flux
    horaire, soit des valeurs qui grimpent absurdement au fil de la journée).

    h = 0 est exclu des échéances à décoder : les champs cumulés (`sshf`)
    ne sont PAS publiés à l'échéance 0 — leur cumul y vaut zéro par
    définition. Découvert par le test du 20/07/2026 sur le run de 03Z, où
    la première échéance de jour est h=1 et réclamait donc un h=0 qui
    n'existe pas. Le zéro est réinjecté implicitement par sshf_at()."""
    kept = [h for h in range(1, MAX_HOURS + 1) if keep_step(h)]
    need = {h for h in kept} | {h - 1 for h in kept}
    return sorted(h for h in need if h >= 1), kept

def sshf_at(data, h, p):
    """`sshf` au point p, échéance h — avec le zéro implicite à h = 0.

    Le cumul depuis le début du run vaut 0 à l'échéance 0, ce qui n'est pas
    écrit dans le GRIB. Renvoyer 0.0 plutôt que None permet de calculer un
    flux dès h = 1 (utile : au run de 03Z, h=1 est déjà en journée)."""
    if h == 0:
        return 0.0
    vals = data.get(("sshf", h))
    return None if vals is None else vals[p]

def files_for(ref, pkg, steps_needed):
    """Bundles du paquet couvrant les échéances nécessaires.

    La grille 0025 groupe les échéances par 6 h (`__00H06H__`). On ne
    télécharge que les bundles qui contiennent au moins une échéance utile —
    la nuit étant exclue, ça élimine réellement des fichiers (~40 % du
    volume selon l'heure du run)."""
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


# ── Grille / indexation ───────────────────────────────────────────────
def _norm_lon(x):
    """AROME publie longitudeOfFirstGridPointInDegrees en convention 0-360°
    (348.0 et non -12.0). SANS cette normalisation, l'indice i devient très
    négatif, k = j*Ni + i reste un index VALIDE du tableau, et on lit des
    valeurs réelles AU MAUVAIS ENDROIT — sans erreur ni avertissement.
    Piège rencontré pour de vrai le 20/07/2026, cf. NOTES_TECHNIQUES."""
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

    Décimation entière depuis la grille native (STEP_DEG / di), donc aucune
    interpolation : on prend des points réels du modèle."""
    dec = max(1, round(STEP_DEG / meta["di"]))
    pts = []
    for j in range(0, meta["Nj"], dec):
        lat = meta["lat0"] + (meta["dj"] * j if meta["jScan"] == 1 else -meta["dj"] * j)
        if not (BBOX["latmin"] <= lat <= BBOX["latmax"]):
            continue
        for i in range(0, meta["Ni"], dec):
            lon = meta["lon0"] + meta["di"] * i
            if BBOX["lonmin"] <= lon <= BBOX["lonmax"]:
                # Garde-fou : c'est CET assert qui aurait attrapé
                # immédiatement le bug de longitude 0-360° (cf. _norm_lon).
                assert 0 <= i < meta["Ni"] and 0 <= j < meta["Nj"], (i, j)
                pts.append((j * meta["Ni"] + i, round(lat, 3), round(lon, 3)))
    return pts

# ── Parsing GRIB ──────────────────────────────────────────────────────
def parse_grib(path, wanted, steps_needed, state):
    """Décode un bundle et n'en garde QUE les points échantillonnés.

    `state` porte {meta, pts, data}. Extraire les points de la BBOX dès le
    décodage (au lieu de stocker la grille complète) divise la mémoire par
    ~10 : la grille 0025 fait 1121×717 = 803 757 points, dont ~75 000 nous
    intéressent. Sur 30+ échéances × 4 champs, l'écart n'est pas anecdotique
    (~600 Mo contre ~60 Mo)."""
    want_steps = set(steps_needed)
    with open(path, "rb") as f:
        while True:
            gid = codes_grib_new_from_file(f)
            if gid is None:
                break
            try:
                sn = codes_get(gid, "shortName")
                st = codes_get(gid, "step")
                if sn not in wanted or st not in want_steps:
                    continue
                if state["meta"] is None:
                    state["meta"] = grid_meta(gid)
                    state["pts"] = sample_points(state["meta"])
                    print(f"  grille {state['meta']['Ni']}x{state['meta']['Nj']}, "
                          f"lon0={state['meta']['lon0']} -> {len(state['pts'])} points échantillonnés")
                vals = codes_get_values(gid)
                state["data"][(sn, st)] = [vals[k] for k, _, _ in state["pts"]]
            finally:
                codes_release(gid)

def download_tmp(key):
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

def fetch_parse(ref, pkg, wanted, steps_needed, state):
    for key in files_for(ref, pkg, steps_needed):
        p = download_tmp(key)
        try:
            parse_grib(p, wanted, steps_needed, state)
        finally:
            os.unlink(p)


# ── Calcul w* ─────────────────────────────────────────────────────────
def wstar(T0, zi, sshf_h, sshf_prev, dt_s):
    """w* pour UN point et UNE échéance. Retourne (w*, zᵢ) ou (None, None).

    `None` = donnée manquante ou aberrante — JAMAIS une valeur inventée pour
    "boucher le trou" (même logique que _ms() dans arome-wind/ingest.py :
    le client sait déjà ignorer un point null, un chiffre fabriqué serait
    indétectable).

    Désaccumulation + signe : `sshf` est un cumul depuis le début du run, en
    J/m², et la convention GRIB compte les flux VERS LE BAS positifs. La
    chaleur qui sort du sol — celle qui fait les thermiques — est donc
    NÉGATIVE dans le fichier, d'où le signe moins. Validation de ce signe :
    la Méditerranée doit ressortir à w* = 0 (cf. NOTES_TECHNIQUES). Si un
    jour la mer devient le meilleur spot de France, c'est ici qu'il faut
    regarder."""
    if T0 is None or zi is None or sshf_h is None or sshf_prev is None:
        return None, None
    if not (math.isfinite(T0) and math.isfinite(zi)
            and math.isfinite(sshf_h) and math.isfinite(sshf_prev)):
        return None, None
    if T0 < 150 or T0 > 350 or zi < 0 or zi > 8000:   # sentinelles / aberrations
        return None, None
    H0 = -(sshf_h - sshf_prev) / dt_s          # W/m², positif = sol qui chauffe l'air
    if H0 <= 0 or zi <= 0:
        return 0.0, round(zi / 10) * 10        # nuit, mer, couche stable : pas de thermique
    w = ((G / T0) * (H0 / (RHO * CP)) * zi) ** (1.0 / 3.0)
    if not math.isfinite(w) or w > 10:         # 10 m/s : au-delà, c'est une aberration
        return None, None
    if w < WSTAR_MIN:
        return 0.0, round(zi / 10) * 10
    # Arrondis : 0,01 m/s et 10 m. Au-delà c'est de la fausse précision —
    # et ça allège les tuiles d'environ 20 %.
    return round(w, 2), round(zi / 10) * 10

def build_tiles(state, kept, times, run):
    """{(tLat,tLon): dict tuile} — même structure que les tuiles vent."""
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
        ws, zs = [], []
        for h in kept:
            try:
                w, z = wstar(d[("t", h)][p], d[("blh", h)][p],
                             sshf_at(d, h, p), sshf_at(d, h - 1, p), 3600.0)
            except KeyError:
                w, z = None, None
            ws.append(w); zs.append(z)
        g["points"].append(dict(lat=lat, lon=lon, wstar=ws, zi=zs))
    return tiles

# ── Upload Supabase Storage (identique à arome-wind/ingest.py) ────────
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
                "Cache-Control": "max-age=10800"})
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


# ── Contrôle qualité (garde-fou anti-régression) ──────────────────────
# Points de contrôle vérifiés à la main le 20/07/2026 (cf. NOTES_TECHNIQUES).
# Le test de la MER est le plus important : il valide la convention de signe
# de la désaccumulation. Une inversion de signe ferait ressortir la
# Méditerranée comme la meilleure zone de France — une erreur silencieuse,
# invisible à la lecture du code, et dangereuse dans un outil de vol.
QC_SEA  = [(43.0, 4.0), (42.8, 4.5)]        # Golfe du Lion
QC_LAND = [(45.3, 5.875), (45.825, 6.25)]   # St-Hilaire, La Forclaz

def quality_check(state, kept):
    """Journalise w* sur des points connus, à l'échéance la plus proche de
    12h UTC. Ne bloque pas le run (un run AROME peut légitimement donner une
    journée pourrie partout), mais rend une régression VISIBLE dans les logs
    de l'Action au lieu de la laisser passer en silence."""
    if not kept or state["meta"] is None:
        return
    h = min(kept, key=lambda x: abs((_RUN_HOUR_UTC + x) % 24 - 12))
    idx_of = {(lat, lon): p for p, (_, lat, lon) in enumerate(state["pts"])}

    def nearest(lat, lon):
        best, bd = None, 1e9
        for (la, lo), p in idx_of.items():
            dd = (la - lat) ** 2 + (lo - lon) ** 2
            if dd < bd:
                best, bd = p, dd
        return best

    d = state["data"]
    print(f"  contrôle qualité (échéance +{h}h = {(_RUN_HOUR_UTC + h) % 24}h UTC) :")
    sea_max = 0.0
    for label, sites in (("MER ", QC_SEA), ("TERRE", QC_LAND)):
        for lat, lon in sites:
            p = nearest(lat, lon)
            w, z = wstar(d[("t", h)][p], d[("blh", h)][p],
                         sshf_at(d, h, p), sshf_at(d, h - 1, p), 3600.0)
            print(f"    {label} ({lat},{lon}) : w*={w} m/s, zi={z} m")
            if label == "MER " and w:
                sea_max = max(sea_max, w)
    if sea_max > 1.0:
        print(f"  ⚠️⚠️ ALERTE : w* = {sea_max} m/s sur la MER. Convention de signe "
              f"de la désaccumulation sshf probablement inversée — NE PAS "
              f"PUBLIER ce résultat tel quel, cf. NOTES_TECHNIQUES.")

# ── main ──────────────────────────────────────────────────────────────
def main():
    global _RUN_HOUR_UTC
    ref, run = latest_run()
    _RUN_HOUR_UTC = run.hour
    print(f"Run AROME : {ref} (run à {_RUN_HOUR_UTC}h UTC)")

    steps_needed, kept = needed_steps()
    if not kept:
        print("Aucune échéance de jour dans l'horizon — rien à produire.")
        return
    times = [(run + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M") for h in kept]
    print(f"{len(kept)} échéances de jour retenues ({kept[0]}h→{kept[-1]}h), "
          f"{len(steps_needed)} à décoder (prédécesseurs inclus pour la désaccumulation)")

    state = dict(meta=None, pts=None, data={})
    print("SP2 (blh, t) :")
    fetch_parse(ref, "SP2", {"blh", "t"}, steps_needed, state)
    print("SP3 (sshf) :")
    fetch_parse(ref, "SP3", {"sshf"}, steps_needed, state)

    missing = [(f, h) for f in ("blh", "t") for h in kept if (f, h) not in state["data"]]
    missing += [("sshf", h) for h in steps_needed
                if h >= 1 and ("sshf", h) not in state["data"]]
    if missing:
        raise SystemExit(f"Champs manquants après parsing : {missing[:10]} "
                         f"({len(missing)} au total) — run incomplet, on abandonne "
                         f"plutôt que de publier des tuiles trouées.")

    quality_check(state, kept)

    total = 0
    for (tLat, tLon), grid in build_tiles(state, kept, times, run).items():
        grid["fetchedAt"] = int(time.time() * 1000)
        sb_upload(f"{MODEL_DIR}/thermal/{tLat}_{tLon}.json",
                  json.dumps(grid, separators=(",", ":")).encode())
        total += 1

    manifest = dict(run=ref, generatedAt=datetime.now(timezone.utc)
                    .strftime("%Y-%m-%dT%H:%M:%SZ"), grid=GRID, tileDeg=TILE_DEG,
                    step=STEP_DEG, maxHours=MAX_HOURS, times=times, uploaded=total,
                    dayUtc=[DAY_UTC_START, DAY_UTC_END], wstarMin=WSTAR_MIN)
    sb_upload(f"{MODEL_DIR}/thermal/manifest.json", json.dumps(manifest).encode())
    print(f"Terminé : {total} tuiles + manifest "
          f"{'(DRY_RUN, rien téléversé)' if DRY_RUN else f'téléversés dans {BUCKET}'}.")

if __name__ == "__main__":
    main()
