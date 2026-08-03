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
from scipy.ndimage import minimum_filter, maximum_filter

OM_BUCKET = "openmeteo"
MODELS = {
    "arpege_europe": "meteofrance_arpege_europe",
    "arpege_world":  "meteofrance_arpege_world025",
}
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
LEVEL_STEP_HPA_BY_GRID = {
    "arpege_europe": 1,     # zoom régional atteignable -> le détail sert
    "arpege_world": 10,     # jamais affichée au-delà du zoom 4 — cf. ci-dessous
}
# 30/07/2026, 2e passe (le compte était encore à ~1,13 Go après la 1re) :
# grille monde poussée de 5 à 10 hPa, mesurée à 236 Mo en 5 hPa -> ~118 Mo.
# Toujours sans perte visible, pour la même raison qu'au-dessus :
# `hpaVisibleAtZoom` (IsobarsLayer.tsx) teste `hpa % 5 === 0`, donc des
# lignes tous les 10 hPa sont TOUTES multiples de 5 et TOUTES affichées —
# aucun changement frontend, aucune ligne masquée. Et 10 hPa est la
# convention des cartes synoptiques de grande échelle : sur une carte du
# monde sous le zoom 4, c'est au moins aussi lisible que le 5 hPa.
# La grille Europe reste à 1 hPa (c'est elle qu'on zoome).
LEVEL_STEP_HPA = 1   # défaut de repli si une grille n'est pas dans la table
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
MAX_CENTERS_PER_KIND = 6        # évite la surcharge visuelle (surtout grille monde)

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
def isobars_geojson(lon2d, lat2d, pressure, step_hpa=LEVEL_STEP_HPA):
    """Contourage tous les `step_hpa` hPa -> GeoJSON FeatureCollection
    de LineString (une feature par segment de contour, propriété `hpa`).
    matplotlib fait le travail numérique (marching squares) ; on ne fait
    que relire ses segments, rien n'est affiché (backend Agg).

    30/07/2026 : le pas est désormais un PARAMÈTRE (cf.
    LEVEL_STEP_HPA_BY_GRID) et non plus une constante globale — la grille
    monde n'a pas besoin du pas fin."""
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
    précédent. Renvoie `(set d'ISO, manifest_lu)`.

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
        return set(), False
    times = {t for t in brut["times"] if isinstance(t, str)}
    print(f"  manifest précédent : {len(times)} échéance(s) déjà publiée(s)")
    return times, True

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
    removed = sum(1 for iso in doomed if STORE.delete(f"{key}/{iso}.json"))
    print(f"  purge '{key}' : {removed}/{len(doomed)} échéance(s) "
          f"obsolète(s) supprimée(s)")
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

    step_hpa = LEVEL_STEP_HPA_BY_GRID.get(key, LEVEL_STEP_HPA)
    print(f"  contourage : {step_hpa} hPa")

    # UNE lecture (Class B) qui remplace ~90 HeadObject + un ListObjects
    # (Class A) — cf. `echeances_publiees`. Elle sert deux fois : au
    # skip-if-exists ci-dessous, et à la purge en fin de fonction.
    publiees, manifest_lu = echeances_publiees(key)

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
        if is_past and iso in publiees and not FORCE_REPROCESS_PAST:
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
        geo = isobars_geojson(*result, step_hpa=step_hpa)
        geo["centers"] = find_centers(*result)
        sb_upload(obj_path, json.dumps(geo, separators=(",", ":")).encode())
        manifest_times.append(iso)
        done += 1
        if not is_past:
            future_done += 1
    print(f"  {done} échéance(s) (re)calculée(s), {len(manifest_times)} au total")

    manifest = dict(
        model=model, referenceTime=reference_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        generatedAt=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        levelStepHpa=step_hpa, times=manifest_times,
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
    print(f"Terminé : {total} échéance(s) (re)calculée(s) au total dans '{BUCKET}'.")
    STORE.bilan()

if __name__ == "__main__":
    main()
