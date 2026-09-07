#!/usr/bin/env python3
"""
Ingestion ARPEGE -> calque isobares (Europe, passé -> prévision).

⚠️ 07/09/2026 — REFONTE « deux versions, une source » (retour Yann : « les
pilotes ne l'utilisent pas trop… on l'a remis en place mais mal »). Ce qui
était cassé : le front n'affiche que la grille MONDE depuis le 24/07 (fin
de l'incohérence Europe/Monde = deux runs), et le 30/07 cette grille a été
passée à 10 hPa pour le quota, sur la prémisse — déjà fausse depuis six
jours — qu'elle « n'est jamais affichée au-dessus du zoom 4 ». Mesuré le
07/09 à 12:00 : dans un anticyclone 1020-1032 hPa sur la France, la grille
Monde n'avait QUE 2 segments touchant la France (1000/1010), la grille
Europe 219 — et c'est la grille Europe qui n'était jamais lue.

Désormais :
  - UNE SEULE grille, `meteofrance_arpege_europe` (0,1°, BBOX Europe +
    Atlantique NE — la couverture des cartes de pression du Met Office,
    modèle de la version simplifiée). La grille Monde est RETIRÉE et son
    contenu purgé du bucket (`retire_grid`).
  - DEUX fichiers par échéance, calculés sur le MÊME champ du MÊME run
    (donc jamais d'incohérence entre les deux versions) :
      `<iso>.json`        détaillé : contours 1 hPa (inchangé), coordonnées
                          simplifiées (Douglas-Peucker) — ~1,5 Mo avant.
      `<iso>.synop.json`  simplifié « synoptique » : champ lissé, contours
                          tous les 4 hPa (convention Met Office), fragments
                          courts filtrés, coordonnées simplifiées plus fort.
    Les centres H/L sont détectés sur le champ LISSÉ et écrits dans les
    deux fichiers.
  - Le manifest porte `levelStepHpa` (détaillé) ET `synopStepHpa`
    (simplifié). Un manifest précédent SANS `synopStepHpa` déclenche le
    recalcul du passé (une seule fois) pour que chaque échéance ait ses
    deux fichiers.
Le front (IsobarsLayer.tsx) choisit la version selon le zoom, avec un
forçage manuel (Auto / Synoptique / Détaillé).

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

Isobares : contourage tous les 1 hPa (retour Yann 24/07 : « rajouter des
isobares quand on zoome pour avoir plus de détails »). Les multiples de 5
restent les lignes « maîtresses » (toujours affichées, bold tous les 20)
et les lignes intermédiaires 1 hPa ne sont révélées qu'au zoom côté
frontend (cf. ISOBAR_FINE_LINE_ZOOM, IsobarsLayer.tsx) — la convention 5
hPa d'origine reste donc la lecture par défaut, le pas fin n'ajoute du
détail que quand on zoome. Contourage via matplotlib (backend Agg, pas
d'affichage).

Impact du passage 5 -> 1 hPa : ~5x plus de segments par géojson (fichiers
plus lourds). Les échéances passées déjà en storage sont immuables
(skip-if-exists) : elles gardent leur pas de 5 hPa tant qu'on ne relance
pas un rattrapage `FORCE_REPROCESS_PAST=1 python ingest.py` — les nouveaux
runs, eux, sortent d'emblée en 1 hPa.

Sortie : GeoJSON (FeatureCollection de LineString, propriété `hpa`) par
échéance, + un manifest par grille listant les échéances disponibles (même
esprit que arome-wind/ingest.py) — Supabase Storage, bucket `isobars`.

Stockage (03/08/2026) : l'upload passe par `tools/storage.py`, un seul
module pour les 5 chaînes, avec deux implémentations derrière la même
signature. La destination se choisit par variable d'environnement :

  STORAGE_BACKEND   supabase (défaut) | r2 | both
  SUPABASE_URL, SUPABASE_SERVICE_KEY      — requis si backend supabase/both
  R2_ACCOUNT_ID, R2_ACCESS_KEY_ID,
  R2_SECRET_ACCESS_KEY, R2_BUCKET         — requis si backend r2/both
  ISOBARS_BUCKET optionnel, défaut isobars
  DRY_RUN=1 pour tester le calcul/tuilage sans rien téléverser.
"""
import os, sys, json, time, re, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import fsspec
from omfiles import OmFileReader
from scipy.ndimage import minimum_filter, maximum_filter, gaussian_filter

OM_BUCKET = "openmeteo"
# 07/09/2026 : une seule grille (cf. en-tête). `arpege_world` est retirée —
# elle n'a jamais été affichée au-dessus de 10 hPa de pas depuis le 30/07,
# et c'est justement ce pas qui la rendait vide sur la France.
MODELS = {
    "arpege_europe": "meteofrance_arpege_europe",
}
# Grilles qui ont existé et dont le bucket doit être vidé (manifest +
# échéances). Purge idempotente à chaque run (`retire_grid`) : sans
# manifest, rien à faire — donc gratuit une fois le ménage fait.
RETIRED_GRIDS = ("arpege_world",)
# Pas de contourage, PAR GRILLE (30/07/2026 — dépassement de quota Storage).
# Le pas fin 1 hPa a été introduit le 24/07 pour « avoir plus de détails quand
# on zoome » : côté frontend, les lignes non-multiples de 5 ne sont révélées
# qu'à partir de `ISOBAR_FINE_LINE_ZOOM` = 7 (IsobarsLayer.hpaVisibleAtZoom).
# Or la grille MONDE n'est jamais chargée au-dessus du zoom 4 (elle ne sert
# que sous `ISOBARS_EUROPE_MIN_ZOOM`, ou hors `ISOBARS_EUROPE_BBOX`) — ses
# lignes fines n'ont donc JAMAIS pu s'afficher, tout en pesant ~5x plus cher.
# Mesuré le 30/07 : arpege_world 840 Mo contre 128 Mo pour arpege_europe, à
# nombre d'échéances égal, alors que sa maille est 2,5x plus GROSSIÈRE — le
# surcoût venait entièrement du pas fin sur la surface du globe.
# Repasser la seule grille monde à 5 hPa est donc un gain sans aucune
# contrepartie visible. `hpaVisibleAtZoom` teste `hpa % 5`, pas
# `manifest.levelStepHpa` : un géojson tout-multiples-de-5 s'affiche
# intégralement à tous les zooms, aucun changement frontend nécessaire.
#
# ⛔ 07/09/2026 — la table par grille ci-dessus a été RETIRÉE avec la grille
# Monde. Ce raisonnement était juste le 30/07 et faux depuis le 24/07 :
# c'est la grille Monde que le front affichait, à tous les zooms. Leçon
# (BUGS.md) : un pas de contourage « sans contrepartie visible » se vérifie
# dans le code du front qui CHOISIT la grille, pas dans celui qui la
# dessine.
LEVEL_STEP_HPA = 1        # version DÉTAILLÉE (`<iso>.json`)
SYNOP_STEP_HPA = 4        # version SIMPLIFIÉE (`<iso>.synop.json`), Met Office
# Lissage du champ AVANT le contourage synoptique, en cellules de grille
# (0,1° → 2,5 cellules ≈ 25 km). Sans lui, le 0,1° dessine les creux de
# vallée et les bulles de chaleur de surface — du bruit à l'échelle
# synoptique, et des dizaines de petites boucles fermées de 1-2 hPa qui
# n'apparaissent sur aucune carte du Met Office. Assez faible pour ne
# déplacer aucun centre réel de plus d'une cellule ou deux.
SYNOP_SMOOTH_SIGMA_CELLS = 2.5
# Segments de contour synoptique plus courts que ça (longueur cumulée en
# degrés) : jetés. Ce sont les moignons de marching squares au bord de la
# grille et les dernières boucles résiduelles après lissage.
SYNOP_MIN_LENGTH_DEG = 1.5
# Simplification Douglas-Peucker des tracés, tolérance en degrés.
# Mesuré le 07/09 sur l'échéance Europe du 07/09 11:00 (1,0 Mo brut) :
# 0,004° → 802 Ko, 0,01° → 683 Ko, 0,02° → 545 Ko. Le gain est modeste
# parce que le poids du détaillé vient du NOMBRE de tracés (2 100 dont
# des centaines de petites boucles 1 hPa), pas de leurs points. 0,01°
# (~1 km, sous le pixel au zoom 7 où le détaillé apparaît) est retenu ;
# le synoptique, déjà lissé et affiché sous le zoom 7, tolère 0,02°.
SIMPLIFY_TOL_DEG_DETAIL = 0.01
SIMPLIFY_TOL_DEG_SYNOP = 0.02
FUTURE_HOURLY_UNTIL = 48      # horaire jusque-là, puis coarse
FUTURE_COARSE_EVERY = 3
PAST_STEP_HOURS = 6            # cadence des runs ARPEGE
PAST_MAX_RUNS = 60             # garde-fou dur (~15 jours) — la vraie limite
                                # est la 1ère lecture en échec (rétention réelle)
# 30/07/2026 — dépassement du quota Storage Supabase (mail Fair Use Policy,
# 3,23 Go pour 1 Go inclus, restrictions au 29/08). Le passé isobares était
# borné par la SEULE rétention Open-Meteo (~9 j), et rien n'était jamais
# supprimé du bucket : chaque échéance produite y restait à vie, orpheline
# dès qu'elle sortait de la fenêtre du manifest. Deux corrections :
#   1. cette borne temporelle explicite (72 h, décidé avec Yann — assez de
#      recul pour lire une évolution synoptique) ;
#   2. `purge_stale()`, appelée en fin de `process_grid()`, qui aligne
#      réellement le contenu du bucket sur le manifest.
# Un rattrapage de l'existant se fait avec tools/purge_isobars_orphans.py.
PAST_RETENTION_H = int(os.environ.get("PAST_RETENTION_H", "72"))

# Centres de pression (L/H), pour l'animation du sens de rotation du vent
# côté frontend (retour Yann 23/07). Fenêtre glissante simple (pas de scipy) :
# un point est un centre s'il est le min/max strict de son voisinage.
CENTER_WINDOW_DEG = 4.0         # rayon de la fenêtre de recherche (°) — assez
                                 # large pour ignorer le bruit de petite échelle
CENTER_MIN_SEPARATION_DEG = 6.0 # fusionne les centres détectés trop proches
MAX_CENTERS_PER_KIND = 6        # évite la surcharge visuelle
CENTER_MIN_PROMINENCE_HPA = 2.0 # 07/09 : amplitude minimale du champ dans la
                                 # fenêtre pour qu'un extremum soit un centre

DRY_RUN = os.environ.get("DRY_RUN") == "1"
BUCKET  = os.environ.get("ISOBARS_BUCKET", "isobars")
# 03/08/2026 — SB_URL/SB_KEY et le garde-fou de démarrage qui étaient ici
# ont disparu : plus une seule ligne de ce fichier ne parle à Supabase en
# direct, tout passe par `tools/storage.py`. La vérification des
# identifiants y a été déplacée (`_Supabase.__init__`), et elle y est
# devenue BACKEND-AWARE — ce qui était le vrai défaut de la version
# précédente : elle exigeait des identifiants Supabase même pour un run
# qui n'écrit QUE dans R2, donc elle aurait fait échouer toutes les
# chaînes le jour où on retire les secrets Supabase du dépôt.
# Elle se déclenche toujours AVANT la première écriture : `Storage()` est
# construit en tête de `main()`, juste après le dimensionnement.

# Débogage 23/07/2026 (bug identifié en session) : `find_centers` a été
# ajouté le même jour (commit 00434ba) mais le passé déjà téléversé est
# skippé via `sb_exists` avant même d'être relu -> les 33 échéances passées
# déjà en storage ne recevront JAMAIS `centers` en fonctionnement normal
# (le cron ne repasse jamais dessus, le passé est traité comme immuable).
# Flag explicite, DÉFAUT DÉSACTIVÉ : le cron planifié reste efficace et
# idempotent (skip-if-exists) ; on l'active manuellement pour CE run de
# rattrapage ponctuel (`FORCE_REPROCESS_PAST=1 python ingest.py`), puis on
# revient au comportement normal ensuite. Réutilisable si ce type de bug
# (nouveau champ dérivé ajouté après coup) se reproduit.
FORCE_REPROCESS_PAST = os.environ.get("FORCE_REPROCESS_PAST") == "1"

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

def read_pressure(model, dt_utc, reference_time=None):
    """Lit `pressure_msl` (grille complète, hPa) pour un modèle Open-Meteo.

    Débogage 23/07/2026 (bug confirmé en direct sur le bucket S3 réel) :
    les fichiers horaires d'un run vivent TOUS sous le dossier de CE run
    (son heure de référence), ex. `data_spatial/meteofrance_arpege_europe/
    2026/07/23/0000Z/` contient `2026-07-23T0000.om`, `...T1800.om`, etc.
    — un seul dossier `<run>Z/` par run, quel que soit le nombre
    d'échéances horaires qu'il contient. Le nom de FICHIER, lui, porte
    l'heure de VALIDITÉ (`valid_time`), pas l'heure de référence.

    - Passé (`reference_time=None`) : `dt_utc` EST à la fois le run et sa
      propre échéance 0 (cf. `past_times` — chaque run passé n'est lu qu'à
      SA propre heure de référence), donc `run_dir` dérivé de `dt_utc`
      fonctionne par coïncidence.
    - Prévision (`reference_time` fourni) : `dt_utc` est l'heure de
      VALIDITÉ (peut différer de plusieurs heures du run), donc `run_dir`
      DOIT être dérivé de `reference_time` (le run effectivement utilisé),
      et seul le nom de fichier varie avec `dt_utc`. Avant ce correctif,
      `run_dir` était dérivé de `dt_utc` dans les deux cas -> pour la
      prévision ça pointait vers un dossier `<heure de validité>Z/`
      inexistant (404 silencieux, prévision jamais ingérée).

    Retourne (lon2d, lat2d, pressure) ou None si absent (fichier purgé /
    pas encore publié — pas une erreur, cf. appelants)."""
    run_dt = reference_time if reference_time is not None else dt_utc
    run_dir = run_dt.strftime("%Y/%m/%d/%H00Z")
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
def simplify_rdp(seg, tol):
    """Douglas-Peucker itératif (pile, pas de récursion : un contour de
    grille Europe fait couramment 2 000 points). `seg` : tableau (n, 2)
    ; renvoie le sous-tableau des points conservés, extrémités comprises.
    07/09/2026 — première simplification des tracés : les fichiers
    pesaient 0,9 à 1,6 Mo par échéance, téléchargés à CHAQUE cran du
    curseur sur téléphone."""
    n = len(seg)
    if n < 3 or tol <= 0:
        return seg
    keep = np.zeros(n, dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        p, q = seg[a], seg[b]
        d = q - p
        norm = float(np.hypot(d[0], d[1]))
        pts = seg[a + 1:b]
        if norm < 1e-12:
            dist = np.hypot(pts[:, 0] - p[0], pts[:, 1] - p[1])
        else:
            dist = np.abs(d[0] * (p[1] - pts[:, 1]) - d[1] * (p[0] - pts[:, 0])) / norm
        i = int(np.argmax(dist))
        if dist[i] > tol:
            k = a + 1 + i
            keep[k] = True
            stack.append((a, k))
            stack.append((k, b))
    return seg[keep]

def seg_length_deg(seg):
    """Longueur cumulée d'un tracé en degrés (plan, sans cos(lat) — un
    seuil de filtrage, pas une mesure)."""
    d = np.diff(seg, axis=0)
    return float(np.hypot(d[:, 0], d[:, 1]).sum())

def isobars_geojson(lon2d, lat2d, pressure, step_hpa=LEVEL_STEP_HPA,
                    tol_deg=SIMPLIFY_TOL_DEG_DETAIL, min_length_deg=0.0):
    """Contourage tous les `step_hpa` hPa -> GeoJSON FeatureCollection
    de LineString (une feature par segment de contour, propriété `hpa`).
    matplotlib fait le travail numérique (marching squares) ; on ne fait
    que relire ses segments, rien n'est affiché (backend Agg).

    30/07/2026 : le pas est un PARAMÈTRE. 07/09/2026 : chaque tracé est
    simplifié (`simplify_rdp`, `tol_deg`) et, si `min_length_deg` > 0,
    les tracés trop courts sont jetés (version synoptique)."""
    pmin, pmax = float(np.nanmin(pressure)), float(np.nanmax(pressure))
    lo = np.floor(pmin / step_hpa) * step_hpa
    hi = np.ceil(pmax / step_hpa) * step_hpa + step_hpa
    levels = np.arange(lo, hi, step_hpa)

    fig, ax = plt.subplots()
    cs = ax.contour(lon2d, lat2d, pressure, levels=levels)
    features = []
    # matplotlib >=3.8 : cs.allsegs reste disponible (API contour "legacy"),
    # cf. cs.levels pour la valeur hPa de chaque jeu de segments.
    for level, segs in zip(cs.levels, cs.allsegs):
        for seg in segs:
            if len(seg) < 2:
                continue
            seg = np.asarray(seg, dtype=float)
            if min_length_deg > 0 and seg_length_deg(seg) < min_length_deg:
                continue
            seg = simplify_rdp(seg, tol_deg)
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

def smooth_pressure(pressure):
    """Champ lissé pour la version synoptique et la détection des centres
    (cf. SYNOP_SMOOTH_SIGMA_CELLS). `mode='nearest'` : pas de repli vers
    zéro au bord de la grille, qui creuserait une fausse dépression sur
    tout le pourtour."""
    return gaussian_filter(pressure, sigma=SYNOP_SMOOTH_SIGMA_CELLS, mode="nearest")

def synop_geojson(lon2d, lat2d, pressure_smooth):
    """Version SIMPLIFIÉE (07/09/2026, modèle : cartes de pression de
    surface du Met Office) : contours tous les SYNOP_STEP_HPA sur le champ
    lissé, fragments courts jetés, tracés simplifiés plus fort."""
    return isobars_geojson(lon2d, lat2d, pressure_smooth, step_hpa=SYNOP_STEP_HPA,
                           tol_deg=SIMPLIFY_TOL_DEG_SYNOP,
                           min_length_deg=SYNOP_MIN_LENGTH_DEG)

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
    # 07/09/2026 : un extremum local doit aussi DÉPASSER de la nappe.
    # Sans ce seuil, un champ plat rempli quand même ses 6 places par
    # type avec des ondulations de 0,2 hPa — et l'écran montrait des H
    # et des L au milieu de rien. Prominence = amplitude du champ dans
    # la fenêtre de recherche autour du point.
    prominence = local_max - local_min
    is_low = (pressure <= local_min) & (prominence >= CENTER_MIN_PROMINENCE_HPA)
    is_high = (pressure >= local_max) & (prominence >= CENTER_MIN_PROMINENCE_HPA)

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
# ── Upload : adaptateur vers le module partagé ────────────────────────
# 03/08/2026 — `sb_upload()` existait en CINQ exemplaires quasi
# identiques (une par chaîne d'ingestion), chacun avec sa propre copie de
# la leçon Cache-Control des 23-24/07 recopiée en docstring. Même motif
# de dette que les 4 copies du calcul de features. Le corps est désormais
# dans `tools/storage.py`, avec DEUX implémentations derrière la même
# signature (Supabase Storage / Cloudflare R2), choisies par la variable
# d'environnement `STORAGE_BACKEND` (`supabase` | `r2` | `both`).
#
# Ce qui reste ici est un adaptateur : aucun appelant ne change, et la
# bascule de CETTE chaîne se fait par une variable d'environnement — donc
# une chaîne à la fois, et un retour en arrière sans toucher au code.
#
# ⚠️ Cette chaîne est la SEULE à clés horodatées, donc la seule où le
# cache long se justifie — et donc la seule qui DOIT purger. Les deux
# moitiés de cet arbitrage sont indissociables : c'est l'absence de purge
# sur des clés immuables qui a fait grossir ce bucket jusqu'à 2,1 Go et
# déclenché le mail Fair Use du 30/07. `CACHE_IMMUABLE` pour les géojson
# par échéance, `CACHE_REECRIT` explicite pour le manifest (réécrit à
# chaque run, et il encode `nowIndex` — débogage du 23/07).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))
from storage import (Storage, verifier_dimensionnement, Abort,   # noqa: E402
                     CACHE_REECRIT, CACHE_IMMUABLE)

# Instancié dans main(), APRÈS verifier_dimensionnement() : on chiffre
# avant d'écrire, jamais l'inverse (garde-fou n°1).
STORE = None


def sb_upload(path, body, cache_control=CACHE_IMMUABLE):
    return STORE.put(path, body, cache_control=cache_control)

def echeances_publiees(key):
    """Les échéances DÉJÀ dans le bucket, lues dans le manifest du run
    précédent. Renvoie `(set d'ISO, manifest_lu, synop_ok)` — le troisième
    dit si ces échéances ont aussi leur version synoptique (07/09/2026).

    03/08/2026 — remplace `sb_exists()` (un `HEAD` par échéance) ET le
    `ListObjects` paginé de `purge_stale()`. Les deux étaient gratuits
    chez Supabase et sont facturés **Class A** chez R2 : ~90 HEAD + un
    listing par run et par grille, pour le plus souvent ne rien écrire.
    Ici : **un seul `GetObject` sur une clé connue**, facturé Class B
    (10 M/mois) — 8 par jour, soit 0,002 % du palier.

    ┌─ POURQUOI LE MANIFEST FAIT AUTORITÉ SUR LE CONTENU DU BUCKET ─────┐
    │ Depuis le correctif du 30/07, `purge_stale()` aligne le bucket    │
    │ sur le manifest à la fin de CHAQUE run. `times` est donc la liste │
    │ de ce qui existe. C'est aussi, et depuis toujours, la seule liste │
    │ que le frontend lit : un objet absent du manifest n'est plus      │
    │ jamais téléchargé, qu'il existe encore ou non.                    │
    └───────────────────────────────────────────────────────────────────┘

    ⚠️ ET SI LE MANIFEST MENT ? Les deux dérives possibles sont sans
    danger, et c'est ce qui rend le remplacement acceptable :
      · un objet écrit puis absent du manifest (run interrompu entre les
        deux) → on le réécrit au run suivant. Quelques Class A, aucune
        perte : l'écriture est idempotente, la clé est la même.
      · une échéance listée dont l'objet a échoué à être supprimé → on ne
        la recalcule pas et elle reste servie. Elle est dans le manifest,
        donc le frontend sait la lire. Pas de trou.
    Aucune des deux ne peut faire disparaître une donnée que l'app
    affiche — contrairement à un `ListObjects` qui échoue et qu'on
    interpréterait comme « le bucket est vide ».

    ⚠️ MANIFEST ILLISIBLE → ON NE SUPPRIME RIEN, et on recalcule tout.
    Même règle que `tools/purge_isobars_orphans.py` : sans état fiable,
    on ne détruit pas. Le `manifest_lu` renvoyé sert exactement à ça —
    `purge_stale()` refuse de tourner quand il vaut False. Le coût d'un
    manifest illisible est donc une fenêtre recalculée (borné par le
    plafond dur du run), jamais une suppression à l'aveugle.

    ⚠️ AU PREMIER RUN SUR UN BUCKET NEUF (bascule R2), il n'y a pas de
    manifest : on renvoie l'ensemble vide et tout est produit. C'est le
    comportement voulu — c'est même toute la raison du mode `both`, qui
    laisse le nouveau bucket se remplir pendant que l'ancien sert."""
    brut = STORE.get_json(f"{key}/manifest.json")
    if not isinstance(brut, dict) or not isinstance(brut.get("times"), list):
        print(f"  manifest '{key}' absent ou illisible — "
              f"aucune purge, tout sera recalculé")
        return set(), False, False
    times = {t for t in brut["times"] if isinstance(t, str)}
    # 07/09/2026 : le passé n'est « déjà là » que s'il a SES DEUX fichiers.
    # Un manifest antérieur à la refonte (sans `synopStepHpa`, ou avec un
    # autre pas) décrit un bucket où `<iso>.synop.json` n'existe pas —
    # on recalcule alors tout le passé, une seule fois : le manifest
    # écrit par ce run portera le bon pas. Même mécanique que le
    # rattrapage `centers` du 23/07, mais automatique.
    synop_ok = brut.get("synopStepHpa") == SYNOP_STEP_HPA \
        and brut.get("levelStepHpa") == LEVEL_STEP_HPA
    print(f"  manifest précédent : {len(times)} échéance(s) déjà publiée(s)"
          + ("" if synop_ok else " — SANS version synoptique : passé recalculé"))
    return times, True, synop_ok

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
    23/07/2026) — pas une valeur qu'on fige en dur, elle peut varier.

    30/07/2026 (dépassement de quota Storage Supabase) : la fenêtre est
    désormais bornée AUSSI par PAST_RETENTION_H (72 h, décidé avec Yann)
    — la rétention Open-Meteo (~9 j) plafonnait seule le passé, et comme
    rien n'était jamais supprimé du bucket, chaque échéance produite y
    restait à vie. Le garde-fou temporel remplace l'ancien PAST_MAX_RUNS
    dans la pratique (celui-ci reste comme filet de sécurité)."""
    out, dt = [], reference_time - timedelta(hours=PAST_STEP_HOURS)
    horizon = reference_time - timedelta(hours=PAST_RETENTION_H)
    for _ in range(PAST_MAX_RUNS):
        if dt < horizon:
            break
        if read_pressure(model, dt) is None:
            break
        out.append(dt)
        dt -= timedelta(hours=PAST_STEP_HOURS)
    out.reverse()
    return out

def purge_stale(key, publiees, keep_isos, manifest_lu):
    """Supprime les échéances qui étaient dans le manifest PRÉCÉDENT et
    ne sont plus dans celui de CE run. Aucun listing.

    30/07/2026 : c'est le correctif de fond du dépassement de quota. Avant,
    ce script ne faisait QUE écrire — les geojson nommés par échéance
    (`{key}/{iso}.json`) étaient traités comme immuables (skip-if-exists) et
    sortaient de la fenêtre du manifest sans jamais quitter le bucket : plus
    jamais téléchargés par l'app, toujours facturés.

    03/08/2026 : le `ListObjects` paginé qui établissait la liste des
    condamnés est remplacé par une **différence de deux manifests**
    (`publiees - keep_isos`). Motif repris du worker de packs : ne jamais
    demander au stockage ce qu'on peut savoir autrement. Chez R2 un
    listing est facturé **Class A** et c'est nommément ce que le garde-fou
    n°1 proscrit ; `DeleteObject`, elle, est **gratuite**, des deux côtés.
    Ce n'est donc pas le coût de la purge qu'on optimise — c'est celui de
    savoir quoi purger.

    ⚠️ `manifest_lu=False` (manifest absent ou illisible) → **on ne
    supprime RIEN**. Sans état fiable on ne détruit pas : même règle que
    `tools/purge_isobars_orphans.py`, qui saute toute grille dont le
    manifest est illisible. Ne PAS interpréter un manifest manquant comme
    « le bucket est vide ».

    ⚠️ Le manifest lui-même n'est jamais candidat : il n'apparaît pas dans
    `times`, donc jamais dans la différence.

    Idempotent, sans effet au premier run propre, et **non bloquant** : un
    échec de purge ne doit pas faire échouer un run qui a réussi à
    produire ses échéances (on journalise et on continue).

    ⚠️ Les orphelins ANTÉRIEURS au premier manifest ne sont pas vus par
    cette différence — par construction, ils n'ont jamais été listés. Le
    rattrapage de l'existant reste le rôle de
    `tools/purge_isobars_orphans.py`, et il a déjà été passé le 30/07
    (0 orphelin au relevé du 03/08)."""
    if not manifest_lu:
        print(f"  purge '{key}' : sautée (pas d'état fiable du run précédent)")
        return 0
    doomed = sorted(set(publiees) - set(keep_isos))
    if not doomed:
        print(f"  purge '{key}' : rien à supprimer")
        return 0
    if DRY_RUN:
        print(f"  (DRY_RUN — purge de '{key}' non exécutée : "
              f"{len(doomed)} échéance(s) auraient été supprimées)")
        return 0
    # 07/09/2026 : deux fichiers par échéance. Le `.synop.json` peut ne
    # pas exister (échéance antérieure à la refonte) — `delete` d'une clé
    # absente est sans effet, on ne compte que le fichier principal.
    removed = 0
    for iso in doomed:
        if STORE.delete(f"{key}/{iso}.json"):
            removed += 1
        STORE.delete(f"{key}/{iso}.synop.json")
    print(f"  purge '{key}' : {removed}/{len(doomed)} échéance(s) "
          f"obsolète(s) supprimée(s)")
    return removed

def retire_grid(key):
    """07/09/2026 — vide le bucket d'une grille RETIRÉE (cf. RETIRED_GRIDS) :
    ses échéances (les deux fichiers, par prudence) puis son manifest, en
    DERNIER — si le run s'interrompt avant, le manifest reste et le
    prochain run reprend le ménage là où il en était. Sans manifest :
    rien à faire, un seul `GetObject` (Class B) par run. Aucun listing,
    pour la même raison que `purge_stale` (Class A chez R2).
    ⚠️ Les orphelins que ce manifest ne liste pas ne sont pas vus — c'est
    le rôle de `tools/purge_isobars_orphans.py`, à repasser une fois."""
    brut = STORE.get_json(f"{key}/manifest.json")
    if not isinstance(brut, dict) or not isinstance(brut.get("times"), list):
        print(f"— {key} : grille retirée, plus de manifest, rien à purger —")
        return 0
    times = [t for t in brut["times"] if isinstance(t, str)]
    if DRY_RUN:
        print(f"— {key} : grille retirée (DRY_RUN — {len(times)} échéance(s) "
              f"+ manifest auraient été supprimés) —")
        return 0
    removed = 0
    for iso in times:
        if STORE.delete(f"{key}/{iso}.json"):
            removed += 1
        STORE.delete(f"{key}/{iso}.synop.json")
    STORE.delete(f"{key}/manifest.json")
    print(f"— {key} : grille retirée, {removed}/{len(times)} échéance(s) "
          f"et le manifest supprimés —")
    return removed

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

    if FORCE_REPROCESS_PAST:
        print("  ⚙️ FORCE_REPROCESS_PAST=1 — le passé déjà en storage sera relu/réécrit "
              "(rattrapage centers, cf. commit du 23/07)")

    print(f"  contourage : détaillé {LEVEL_STEP_HPA} hPa + synoptique "
          f"{SYNOP_STEP_HPA} hPa (lissage σ = {SYNOP_SMOOTH_SIGMA_CELLS} cellules)")

    # UNE lecture (Class B) qui remplace ~90 HeadObject + un ListObjects
    # (Class A) — cf. `echeances_publiees`. Elle sert deux fois : au
    # skip-if-exists ci-dessous, et à la purge en fin de fonction.
    publiees, manifest_lu, synop_ok = echeances_publiees(key)
    reprocess_past = FORCE_REPROCESS_PAST or not synop_ok

    manifest_times, done, future_done = [], 0, 0
    for dt in all_times:
        iso = dt.strftime("%Y-%m-%dT%H:%M")
        obj_path = f"{key}/{iso}.json"
        is_past = dt < reference_time
        # Débogage 23/07/2026 : `sb_exists` seul traitait TOUT passé déjà
        # téléversé comme définitivement à jour — or `find_centers` a été
        # ajouté le même jour (commit 00434ba), donc le passé déjà en
        # storage AVANT ce commit n'a jamais `centers`, et sans ce garde-
        # fou ne l'aura JAMAIS (le passé n'est normalement plus jamais
        # revisité). `FORCE_REPROCESS_PAST` (flag explicite, défaut off,
        # cf. plus haut) permet de forcer un rattrapage ponctuel sans
        # dégrader l'efficacité/idempotence du cron normal.
        if is_past and iso in publiees and not reprocess_past:
            manifest_times.append(iso)      # déjà là, immuable, on ne refait rien
            continue
        # Débogage 23/07/2026 (S3 réel, cf. read_pressure) : pour la
        # prévision, `run_dir` doit rester celui du run de référence — on
        # passe donc `reference_time` explicitement ici (seulement pour le
        # futur ; le passé garde `reference_time=None`, cf. docstring).
        result = read_pressure(model, dt, reference_time=None if is_past else reference_time)
        if result is None:
            print(f"  ⚠️ {iso} absent (purgé ou pas encore publié) — ignoré")
            continue
        lon2d, lat2d, pressure = result
        # 07/09/2026 : les centres H/L sont détectés sur le champ LISSÉ —
        # sur le champ brut 0,1°, un creux thermique de vallée ou une
        # bulle côtière de 1 hPa suffisait à voler la place d'un vrai
        # centre (MAX_CENTERS_PER_KIND = 6). Les deux fichiers reçoivent
        # les MÊMES centres : un pilote qui bascule de version ne doit pas
        # voir un H changer de place.
        smooth = smooth_pressure(pressure)
        centers = find_centers(lon2d, lat2d, smooth)
        geo = isobars_geojson(lon2d, lat2d, pressure, step_hpa=LEVEL_STEP_HPA)
        geo["centers"] = centers
        sb_upload(obj_path, json.dumps(geo, separators=(",", ":")).encode())
        synop = synop_geojson(lon2d, lat2d, smooth)
        synop["centers"] = centers
        sb_upload(f"{key}/{iso}.synop.json",
                  json.dumps(synop, separators=(",", ":")).encode())
        manifest_times.append(iso)
        done += 1
        if not is_past:
            future_done += 1
    print(f"  {done} échéance(s) (re)calculée(s), {len(manifest_times)} au total")

    manifest = dict(
        model=model, referenceTime=reference_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        generatedAt=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        levelStepHpa=LEVEL_STEP_HPA, synopStepHpa=SYNOP_STEP_HPA,
        times=manifest_times,
        # Débogage 23/07/2026 : basé AVANT sur `len(future)` (compte
        # DEMANDÉ, cf. `future_times`) plutôt que sur ce qui a RÉUSSI à
        # être téléversé (`future_done`, entrées passées + prévision
        # effectivement présentes dans `manifest_times`) — tout échec
        # partiel de la prévision (ex. bug de chemin S3 ci-dessus)
        # décalait silencieusement `nowIndex`, jusqu'à le faire sortir de
        # la plage valide (observé : -34 pour 33 échéances réelles).
        nowIndex=len(manifest_times) - future_done)  # frontend : jalon "maintenant"
    # cache court/no-cache : ce fichier est réécrit à chaque run (cf. note
    # dans sb_upload) — contrairement aux geojson par échéance ci-dessus.
    sb_upload(f"{key}/manifest.json", json.dumps(manifest).encode(),
              cache_control=CACHE_REECRIT)
    # 30/07/2026 : APRÈS l'écriture du manifest, jamais avant — si le run
    # échoue en cours de route, le manifest précédent reste servi et on ne
    # veut surtout pas avoir déjà supprimé les échéances qu'il liste.
    purge_stale(key, publiees, manifest_times, manifest_lu)
    return done

def main():
    global STORE

    # ── Chiffrer AVANT d'écrire (garde-fou n°1) ───────────────────────
    # Comptes RÉELS relevés le 03/08/2026 (`tools/audit_storage.py`) :
    # 80 objets par grille × 2 grilles = 160, pour 188 Mo. En régime
    # établi le skip-if-exists ne fait écrire que les nouvelles échéances
    # (~16/run) ; les 200 ci-dessous sont un MAJORANT de démarrage à
    # froid (bucket vide → toute la fenêtre est produite d'un coup), pas
    # une projection. C'est bien ce majorant qu'il faut donner au
    # plafond : il doit tenir le pire run, pas le run moyen.
    # 07/09/2026 : une grille, DEUX fichiers par échéance → même majorant
    # de 200 objets (79 × 2 + manifest = 159 à froid) ; le stockage
    # baisse (plus de grille Monde, tracés simplifiés) — 188 Mo reste un
    # majorant sûr tant que la mesure réelle n'a pas été relevée.
    plafond = verifier_dimensionnement("arpege-isobars", objets_par_run=200,
                                       runs_par_jour=4, mo_par_run=188)

    # 03/08/2026 — les deux dépendances Class A sont levées : le
    # skip-if-exists (avant : ~90 `HeadObject`) et purge_stale (avant :
    # un `ListObjects` paginé) lisent maintenant TOUS DEUX le manifest du
    # run précédent, soit **1 seul `GetObject` par grille**, facturé
    # Class B. Cette chaîne peut donc tourner en `r2`.
    #
    # ⚠️ MAIS PAS DIRECTEMENT. Les clés isobares sont HORODATÉES : au
    # moment de la bascule, le bucket R2 est vide et le manifest du run
    # précédent liste des échéances qui n'existent que dans l'ancien. Le
    # passage par `both` n'est pas une précaution de confort, c'est ce
    # qui rend la bascule sans coupure :
    #   · pendant `both`, l'autorité de lecture reste Supabase, donc le
    #     skip continue de porter sur l'état réel de ce que sert l'app ;
    #   · chaque échéance FUTURE est écrite des deux côtés ; en 72 h
    #     (= PAST_RETENTION_H, 12 runs ARPEGE) toute la fenêtre passée
    #     a été produite alors qu'elle était encore future, donc R2 la
    #     possède ;
    #   · les échéances passées héritées de l'ancien bucket sortent de la
    #     fenêtre dans le même délai et sont purgées des deux côtés.
    # Au bout de 72 h, R2 contient exactement la fenêtre — et c'est SEULEMENT
    # là qu'on bascule la lecture du client.
    # ⚠️ Pendant ces 72 h, le manifest écrit dans R2 liste des échéances
    # que R2 n'a pas encore. C'est sans conséquence tant que personne ne
    # lit R2 — mais c'est la raison pour laquelle on ne bascule pas le
    # client « pour voir ». Vérifier avant : toutes les échéances du
    # manifest R2 doivent répondre 200.
    #
    # Les buckets à clés STABLES (`wind-grid`) n'ont rien de tout ça :
    # 8 runs les repeuplent entièrement, soit une journée, et `both` y est
    # inutile.

    STORE = Storage("arpege-isobars", "ISOBARS_BUCKET", "isobars", plafond)

    total = 0
    for key, model in MODELS.items():
        total += process_grid(key, model)
    # Après la grille vivante, jamais avant : si le ménage échoue, le
    # calque a déjà ses nouvelles échéances.
    for key in RETIRED_GRIDS:
        try:
            retire_grid(key)
        except Exception as e:  # noqa: BLE001 — non bloquant, même règle que purge_stale
            print(f"— {key} : purge de la grille retirée en échec ({e}), on continue —")
    print(f"Terminé : {total} échéance(s) (re)calculée(s) au total dans '{BUCKET}'.")
    STORE.bilan()

if __name__ == "__main__":
    main()
