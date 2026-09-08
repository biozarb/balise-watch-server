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

⚠️ 08/09/2026 — LE SYNOPTIQUE PASSE AU MONDE (retour Yann : « on a moyen
d'avoir le synoptique sur le monde et pas que sur l'Europe ? »). La règle
« une source pour les deux versions » devient « UNE GRILLE PAR VERSION » :

  arpege_world  (meteofrance_arpege_world025, 0,25°, globe)
      → `<iso>.synop.json` SEUL, 4 hPa, latitudes bornées à ±80°
  arpege_europe (meteofrance_arpege_europe, 0,1°, Europe)
      → `<iso>.json` SEUL, détaillé 1 hPa, au-delà du zoom 7

Ce n'est PAS le retour de la bascule du 24/07 (deux grilles pour la même
information, deux runs, deux champs → incohérence à chaque zoom) : ici
chaque version n'a qu'une source possible, et c'est de toute façon le
MÊME modèle ARPEGE des deux côtés, à la même cadence de runs — les H/L
coïncident à la frontière Europe/Monde. Conséquences dans ce fichier :
  · `GRIDS` remplace `MODELS` : lissage, longueur minimale, tolérance
    RDP, nombre de centres et coupe en latitude sont PAR GRILLE (les
    mêmes 2,5 cellules ne font pas la même distance sur 0,1° et 0,25°) ;
  · le manifest ne porte QUE les pas des versions réellement produites
    (`manifest_profil`) — le web doit accepter un manifest sans détail ;
  · `retire_variant` supprime, une fois, les `.synop.json` Europe qui
    n'ont plus de producteur (`purge_stale` ne voit que les échéances
    sorties de la fenêtre, pas une version disparue) ;
  · `centers` porte désormais sa `prominence` (CENTERS_VERSION = 3) :
    pas encore lue par le web, mais le lot fronts en aura besoin et un
    changement de version coûte un recalcul complet du passé.

⚠️ 08/09/2026 (soir) — FRONTS sur le synoptique Monde (demande Yann : « un
rendu comme le Met Office », fronts compris). Détection OBJECTIVE (Hewson
1998) sur θe à 850 hPa lue dans le MÊME `.om` que la pression ; froid /
chaud / stationnaire par le vent normal au front, occlusions par la crête
de θe près d'un L. Écrits dans le `.synop.json` Monde (clé `fronts`), le
manifest porte `frontsVersion`. Étiquetés « détection automatique » côté
web — ce n'est PAS une analyse de prévisionniste. Détail : § Fronts.

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
# ⚠️ 08/09/2026 — LE SYNOPTIQUE PASSE AU MONDE (demande Yann : « on a moyen
# d'avoir le synoptique sur le monde et pas que sur l'Europe ? »). DEUX
# grilles à nouveau, mais — et c'est toute la différence avec le 24/07 —
# elles ne se disputent plus le même rôle : UNE VERSION PAR GRILLE.
#   arpege_world  0,25°, monde entier  → `<iso>.synop.json` SEUL (4 hPa)
#   arpege_europe 0,1°,  Europe        → `<iso>.json` SEUL (détaillé 1 hPa)
# Le front ne « bascule » donc plus d'une grille à l'autre pour la MÊME
# information : il change de VERSION (synoptique sous le zoom 7, détaillé
# au-delà), et chaque version n'a qu'une source possible. L'incohérence du
# 24/07 (deux grilles, deux runs, deux champs pour la même échéance) reste
# impossible pour une autre raison : c'est le MÊME modèle ARPEGE des deux
# côtés, même cadence de runs, donc les H/L coïncident à la frontière.
# ⛔ Et `arpege_world` sort de RETIRED_GRIDS : l'y laisser purgerait la
# grille à chaque run, juste après l'avoir écrite.
GRIDS = {
    "arpege_europe": dict(
        model="meteofrance_arpege_europe",
        variants=("detail",),
        # 0,1° ≈ 11 km : σ = 2,5 cellules ≈ 28 km (réglage du 07/09). Le
        # champ lissé ne sert plus ici qu'à la DÉTECTION DES CENTRES —
        # plus aucun `.synop.json` Europe n'est produit.
        smooth_sigma_cells=2.5,
        synop_min_length_deg=1.5,
        synop_tol_deg=0.02,
        max_centers_per_kind=6,
        lat_clip_deg=None,          # BBOX 20→72 N : rien à couper
    ),
    "arpege_world": dict(
        model="meteofrance_arpege_world025",
        variants=("synop",),
        # 0,25° ≈ 28 km : σ = 1,7 cellule ≈ 47 km. Le lissage est exprimé
        # en CELLULES par gaussian_filter, mais c'est bien une distance
        # qu'on vise — 2,5 cellules ici auraient fait 70 km, et 2,5 est
        # une valeur calée sur une maille 2,5× plus fine. Un lissage un
        # peu plus fort qu'en Europe est SOUHAITABLE : le monde se lit
        # aux zooms 1-4.
        smooth_sigma_cells=1.7,
        # Le vrai filtre des micro-boucles est côté web, en PIXELS
        # (`FEATURE_MIN_PX`, lot du 08/09). Celui-ci ne jette que les
        # moignons de marching squares : 2° sur 0,25° ≈ 8 cellules.
        # RDP : 0,05° ≈ 0,5 px au zoom 4 (0,02° en Europe, où le détaillé
        # se regarde au zoom 7).
        synop_min_length_deg=2.0,
        synop_tol_deg=0.05,
        # 6 était pensé pour l'Europe seule ; sur le globe, un H et un L
        # par système. MESURÉ le 08/09 (échéance 12:00, banc) : après le
        # filtre de séparation 6° et la prominence 2 hPa, le champ ne
        # fournit que 75 candidats par type — au-delà, le plafond ne
        # mord plus. 60 le laisse donc quasi inopérant en pratique tout
        # en gardant une borne. ⚠️ Et il faut être large : le tri est
        # « le plus extrême d'abord », donc un plafond de 20 sur le
        # GLOBE gardait les tempêtes australes et laissait l'Europe sans
        # aucun H (constaté au banc). Coût : 8 Ko de centres pour 261 Ko
        # de fichier. La fusion visuelle des centres trop proches à
        # l'écran est déjà côté web (90 px, 08/09).
        max_centers_per_kind=60,
        # Web Mercator s'arrête à 85° et les contours au-delà de 80° sont
        # des artefacts de projection (des cercles autour du pôle). On
        # coupe AVANT le contourage : ni tracés ni centres polaires.
        lat_clip_deg=80.0,
        # 08/09/2026 (lot fronts) : les fronts sont détectés sur CETTE
        # grille seulement (vue synoptique), dans le même fichier
        # `.synop.json` — même run, même échéance, jamais un second
        # fichier ni un second manifest (piège des deux runs du 24/07).
        fronts=True,
    ),
}
# Grilles qui ont existé et dont le bucket doit être vidé (manifest +
# échéances). Purge idempotente à chaque run (`retire_grid`) : sans
# manifest, rien à faire — donc gratuit une fois le ménage fait.
# ⛔ VIDE depuis le 08/09 : `arpege_world` est redevenue une grille VIVANTE.
RETIRED_GRIDS = ()
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
# ⚠️ 08/09/2026 — le lissage (σ), la longueur minimale d'un tracé, la
# tolérance RDP du synoptique et le nombre de centres sont désormais
# PAR GRILLE (cf. `GRIDS` plus haut) : les mêmes 2,5 cellules ne font pas
# la même distance sur une maille 0,1° et sur une maille 0,25°. Les
# valeurs Europe du 07/09 y sont reprises telles quelles.
# Simplification Douglas-Peucker des tracés, tolérance en degrés.
# Mesuré le 07/09 sur l'échéance Europe du 07/09 11:00 (1,0 Mo brut) :
# 0,004° → 802 Ko, 0,01° → 683 Ko, 0,02° → 545 Ko. Le gain est modeste
# parce que le poids du détaillé vient du NOMBRE de tracés (2 100 dont
# des centaines de petites boucles 1 hPa), pas de leurs points. 0,01°
# (~1 km, sous le pixel au zoom 7 où le détaillé apparaît) est retenu ;
# le synoptique, déjà lissé et affiché sous le zoom 7, tolère 0,02°.
SIMPLIFY_TOL_DEG_DETAIL = 0.01
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
                                # ⚠️ 08/09 : le NOMBRE max de centres est
                                # par grille (`GRIDS`) — 6 en Europe, 20
                                # sur le monde.
CENTER_MIN_PROMINENCE_HPA = 2.0 # 07/09 : amplitude minimale du champ dans la
                                 # fenêtre pour qu'un extremum soit un centre
# Version de l'algorithme des centres, écrite dans le manifest. Les centres
# vivent DANS les fichiers par échéance (immuables, skip-if-exists) : changer
# `find_centers` sans incrémenter ceci laisserait le passé avec les anciens
# centres jusqu'à sa sortie de fenêtre (72 h). Incrémenter force un recalcul
# du passé, une fois. 2 = exclusion du bord de grille (07/09, 2e run).
# 3 = `prominence` (hPa) écrite dans chaque centre + nombre de centres par
# grille (08/09). La prominence n'est pas encore lue par le web : elle est
# écrite MAINTENANT parce que le lot fronts en aura besoin et qu'un
# `CENTERS_VERSION` coûte un recalcul complet du passé — autant n'en payer
# qu'un.
CENTERS_VERSION = 3

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
    res = read_fields(model, dt_utc, ("pressure_msl",), reference_time)
    if res is None:
        return None
    lon2d, lat2d, fields = res
    return lon2d, lat2d, fields["pressure_msl"]

# 08/09/2026 (lot fronts) — les 4 champs 850 hPa du même fichier `.om`
# que la pression : zéro requête de plus, une lecture par variable.
# ⛔ Chaque nouvelle variable est un champ retourné en puissance (leçon du
# calque à l'envers) : `banc_fronts_08-09.py --orientation` a comparé ces
# quatre champs à l'API Open-Meteo sur 12 points (dont Le Cap, Wellington,
# New York, Tokyo) le 08/09 — écart 0,02 °C / 0,04 m/s lus sud→nord, 13 °C
# / 8 m/s lus à l'envers. Unités VÉRIFIÉES : T en °C, RH en %, u/v en m/s,
# u vers l'est, v vers le nord (confrontés à vitesse + direction de l'API).
FRONT_FIELDS = ("temperature_850hPa", "relative_humidity_850hPa",
                "wind_u_component_850hPa", "wind_v_component_850hPa")
# Taille de bloc de lecture par modèle (cf. `read_fields`) : 1 Mo là où
# l'on lit cinq variables par fichier, 64 Ko ailleurs.
OM_BLOCK_SIZE = {"meteofrance_arpege_world025": 1 << 20}

def read_fields(model, dt_utc, names, reference_time=None):
    """Lit plusieurs variables (grille complète) du même `.om`. Renvoie
    (lon2d, lat2d, {nom: tableau}) ou None si le fichier est absent.
    Même convention d'axes que `read_pressure` (sud → nord)."""
    run_dt = reference_time if reference_time is not None else dt_utc
    run_dir = run_dt.strftime("%Y/%m/%d/%H00Z")
    fname = dt_utc.strftime("%Y-%m-%dT%H%M")
    uri = f"s3://{OM_BUCKET}/data_spatial/{model}/{run_dir}/{fname}.om"
    # Taille de bloc : 64 Ko suffisaient pour UNE variable (~350 Ko lus
    # par fichier). MESURÉ le 08/09 (conteneur neuf, S3 anonyme, une
    # échéance Monde, 5 variables) : 9,7 s en blocs de 64 Ko, 4,1 s en
    # blocs de 1 Mo — la lecture domine le run (le calcul des fronts fait
    # 2,5 s), et 79 échéances × 20 s frôlaient le `timeout-minutes: 30`
    # du workflow.
    # ⛔ La taille de bloc est une propriété du MODÈLE, pas de l'appel :
    # le blockcache refuse de rouvrir un fichier avec une autre taille
    # (`BlocksizeMismatchError`), et `past_times` sonde chaque fichier
    # passé avec `read_pressure` (une variable) AVANT que `process_grid`
    # ne le relise avec les cinq. Une première version faisait dépendre
    # la taille du nombre de variables : le rejeu DRY_RUN du 08/09 est
    # mort dessus à la première échéance passée — en prod, ç'aurait été
    # le run.
    block = OM_BLOCK_SIZE.get(model, 65536)
    backend = fsspec.open(
        f"blockcache::{uri}", mode="rb",
        s3={"anon": True, "default_block_size": block},
        blockcache={"cache_storage": "/tmp/om_cache_isobars"},
    )
    fields = {}
    try:
        with OmFileReader(backend) as root:
            for n in names:
                fields[n] = root.get_child_by_name(n).read_array((...))
            bbox = _BBOX_RE.search(root.get_child_by_name("crs_wkt").read_scalar())
            south, west, north, east = (float(x) for x in bbox.groups())
    except FileNotFoundError:
        return None
    nj, ni = fields[names[0]].shape
    # ⛔ 08/09/2026 — CORRECTIF : LE CALQUE ÉTAIT RETOURNÉ NORD-SUD DEPUIS
    # LE 23/07. Cette ligne disait `linspace(north, south)` (« jScan
    # descendant »), convention GRIB2 d'AROME recopiée ici. Mais ces
    # fichiers ne sont PAS du GRIB2 : dans le layout `data_spatial`
    # d'Open-Meteo, la première ligne du tableau est la plus AU SUD. Tout
    # le champ était donc symétrisé autour du milieu de la BBOX (Europe :
    # lat′ = 92 − lat).
    #
    # Mesuré le 08/09 sur l'échéance 12:00, 8 points, contre l'API
    # Open-Meteo (même fournisseur, même modèle, `pressure_msl`) :
    #   lecture nord→sud : 13,35 hPa d'écart moyen
    #   lecture sud→nord :  0,04 hPa
    # Et l'anomalie notée le 07/09 — « un L à 975 hPa au large du Maroc
    # (31,4 N / −12,5 W), réel ou artefact de la source ? » — était ce
    # bug : à ce point la pression valait 1020,1 hPa, et 972,5 hPa à son
    # miroir 60,6 N. Une dépression islandaise dessinée sur le Maroc.
    #
    # ⚠️ Ce qui a rendu le bug invisible six semaines : une carte
    # d'isobares retournée reste une carte d'isobares plausible. Elle n'a
    # ni valeur aberrante, ni trou, ni erreur de dimension — seulement
    # des systèmes au mauvais endroit. Le seul contrôle qui l'attrape est
    # une comparaison à une source INDÉPENDANTE en un point connu, et
    # c'est ce que fait désormais `banc_monde_08-09.py --orientation`.
    lat = np.linspace(south, north, nj)
    lon = np.linspace(west, east, ni)
    lon2d, lat2d = np.meshgrid(lon, lat)
    return lon2d, lat2d, fields

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

def smooth_pressure(pressure, sigma_cells):
    """Champ lissé pour la version synoptique et la détection des centres.
    `sigma_cells` vient de `GRIDS` (08/09) : c'est une DISTANCE qu'on vise
    (~28 km en Europe, ~47 km sur le monde), exprimée dans l'unité que
    demande `gaussian_filter`. `mode='nearest'` : pas de repli vers zéro
    au bord de la grille, qui creuserait une fausse dépression sur tout le
    pourtour."""
    return gaussian_filter(pressure, sigma=sigma_cells, mode="nearest")

def synop_geojson(lon2d, lat2d, pressure_smooth, tol_deg, min_length_deg):
    """Version SIMPLIFIÉE (07/09/2026, modèle : cartes de pression de
    surface du Met Office) : contours tous les SYNOP_STEP_HPA sur le champ
    lissé, fragments courts jetés, tracés simplifiés plus fort."""
    return isobars_geojson(lon2d, lat2d, pressure_smooth, step_hpa=SYNOP_STEP_HPA,
                           tol_deg=tol_deg, min_length_deg=min_length_deg)

def clip_latitude(lon2d, lat2d, pressure, lat_clip_deg):
    """08/09/2026 — coupe la grille au-delà de ±`lat_clip_deg` (80° sur le
    monde). Deux raisons, et aucune n'est esthétique :
      · Web Mercator s'arrête à ~85° : au-delà, rien n'est affichable ;
      · entre 80 et 90°, un contourage en lon/lat produit des cercles
        concentriques autour du pôle qui sont un artefact de la
        PROJECTION de la grille, pas un système météo.
    Couper AVANT le contourage évite aussi de payer ces tracés dans le
    fichier. Sans effet si `lat_clip_deg` est None (grille Europe)."""
    if not lat_clip_deg:
        return lon2d, lat2d, pressure
    keep = np.abs(lat2d[:, 0]) <= lat_clip_deg
    return lon2d[keep, :], lat2d[keep, :], pressure[keep, :]

def find_centers(lon2d, lat2d, pressure, max_per_kind=6):
    """Repère les centres de basse/haute pression : un point est un centre
    s'il est le min/max strict de son voisinage (fenêtre CENTER_WINDOW_DEG).
    Filtre exhaustif (scipy.ndimage min/max_filter, vectorisé) — PAS un
    sous-échantillonnage : un test naïf par pas de grille a raté le vrai
    minimum d'une carte (932 hPa non détecté) en ne testant qu'un point sur
    N, cf. vérif locale 23/07/2026. Fusionne ensuite les détections proches
    et ne garde que les `max_per_kind` plus marqués par type (le plus
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
    # 07/09/2026, vu sur le premier run réel : trois « L » posés PILE sur
    # le bord de la grille (lat 20,0 ; lon 42,0 ; lon −24,6 à lat 20) —
    # avec `mode='nearest'`, un champ qui décroît jusqu'au bord y a
    # mécaniquement son minimum local. Un centre n'est crédible que si sa
    # fenêtre de recherche tient ENTIÈREMENT dans la grille.
    is_low[:hw_j, :] = is_low[-hw_j:, :] = False
    is_low[:, :hw_i] = is_low[:, -hw_i:] = False
    is_high[:hw_j, :] = is_high[-hw_j:, :] = False
    is_high[:, :hw_i] = is_high[:, -hw_i:] = False

    # 08/09/2026 : la `prominence` (amplitude du champ dans la fenêtre, en
    # hPa) est CONSERVÉE et écrite dans le fichier. Elle ne servait qu'à
    # filtrer ; le lot fronts en aura besoin pour hiérarchiser les centres,
    # et l'écrire maintenant évite un `CENTERS_VERSION` de plus (= un
    # recalcul complet du passé) plus tard.
    candidates = {
        "L": [(float(lat2d[j, i]), float(lon2d[j, i]), float(pressure[j, i]),
               float(prominence[j, i])) for j, i in zip(*np.where(is_low))],
        "H": [(float(lat2d[j, i]), float(lon2d[j, i]), float(pressure[j, i]),
               float(prominence[j, i])) for j, i in zip(*np.where(is_high))],
    }

    def dlon_wrap(a, b):
        """Écart de longitude en tenant compte de l'antiméridien : sur la
        grille Monde (−180→180), 179 et −179 sont voisins de 2°, pas de
        358°. Sans ça, deux détections du MÊME centre à cheval sur 180°
        seraient gardées toutes les deux."""
        d = abs(a - b) % 360.0
        return min(d, 360.0 - d)

    centers = []
    for kind, pts in candidates.items():
        pts.sort(key=lambda p: abs(p[2] - 1013.25), reverse=True)  # + extrême d'abord
        kept = []
        for lat, lon, hpa, prom in pts:
            if any(abs(lat - k[0]) < CENTER_MIN_SEPARATION_DEG and
                   dlon_wrap(lon, k[1]) < CENTER_MIN_SEPARATION_DEG for k in kept):
                continue  # trop proche d'un centre déjà retenu (plus marqué)
            kept.append((lat, lon, hpa, prom))
            if len(kept) >= max_per_kind:
                break
        centers += [{"kind": kind, "lat": round(lat, 2), "lon": round(lon, 2),
                     "hpa": round(hpa, 1), "prominence": round(prom, 1)}
                    for lat, lon, hpa, prom in kept]
    return centers

# ── Fronts (08/09/2026 — Hewson 1998, sur θe à 850 hPa) ───────────────
# Demande Yann (07-08/09) : « le but serait d'avoir un rendu comme le Met
# Office », fronts compris. Un front du Met Office est tracé À LA MAIN par
# un prévisionniste ; le nôtre est une ligne mathématique dans UN champ
# (θe à 850 hPa, ARPEGE 0,25°). Il est étiqueté « détection automatique »
# partout où il apparaît (dock, légende) — jamais présenté comme une
# analyse. Pas de données inventées : un front détecté n'est pas inventé,
# mais sa nature l'est, et elle doit être lisible.
#
# La méthode, en cinq champs 2-D sur la grille Monde, par échéance, en
# UNITÉS MÉTRIQUES (dx = R·cos φ·dλ, dy = R·dφ — ⛔ pas en degrés : une
# maille de 0,25° fait 28 km en longitude à l'équateur et 14 km à 60° N,
# un gradient en degrés rendrait les fronts nord-sud deux fois plus forts
# que les fronts est-ouest aux latitudes tempérées) :
#   1. τ = θe(T, RH, 850 hPa) par Bolton (1980). Hewson utilise θw ; θw
#      est une fonction MONOTONE de θe, donc les zéros de dérivées (où se
#      trouve le front) sont pratiquement les mêmes, seuls les SEUILS
#      changent d'échelle (θe varie ~1,5-2× plus que θw dans l'air chaud).
#   2. τ lissé (gaussien, σ = FRONTS['smooth_sigma_cells'], périodique en
#      longitude) : le locateur est une DÉRIVÉE TROISIÈME du champ — sans
#      lissage, c'est du bruit.
#   3. G = |∇τ| (intensité de la zone barocline), ŝ = ∇τ/G (vers l'air
#      CHAUD), TFP = −∇G · ŝ (paramètre frontal thermique, Renard &
#      Clarke 1965). En traversant une zone barocline du froid vers le
#      chaud, G monte puis redescend : TFP est < 0 sur le bord froid,
#      nul AU MILIEU de la zone, > 0 et MAXIMAL sur le bord chaud.
#   4. ⚠️ Le front synoptique est sur le BORD CHAUD de la zone barocline
#      (Hewson §2) — c'est-à-dire là où TFP est MAXIMAL le long de ŝ, PAS
#      là où TFP = 0 (ça, c'est le cœur de la zone). Le locateur est donc
#      L = ∇(TFP) · ŝ = 0, contouré au niveau 0 (marching squares, la même
#      routine que les isobares), puis MASQUÉ : on ne garde que les
#      portions où TFP ≥ K2 (un maximum, donc côté chaud — les minima de
#      TFP, côté froid, sont négatifs et tombent) ET où la zone barocline
#      adjacente est assez forte, max(G) sur ~140 km ≥ K1 (Hewson évalue
#      G un peu côté froid parce que sur le bord chaud G décroît déjà —
#      un max local fait le même office). ⛔ Sans ces deux masques, un
#      locateur trouve TOUJOURS des lignes : les zéros d'une dérivée sont
#      partout. Puis les morceaux < min_length_km sont jetés.
#   5. Classification par le VENT NORMAL AU FRONT : v_n = v₈₅₀ · ŝ (m/s,
#      positif quand le vent souffle de l'air froid vers l'air chaud).
#      v_n > seuil → l'air froid avance → FRONT FROID ; v_n < −seuil →
#      FRONT CHAUD ; entre les deux → STATIONNAIRE. ⚠️ Le prompt de reprise
#      écrivait « A = −v·∇τ > 0 → froid » : c'est le signe INVERSE
#      (−v·∇τ > 0 est une advection CHAUDE). Corrigé ici, et vérifié sur
#      le banc synthétique (`banc_fronts_08-09.py --synthetique`).
#   6. OCCLUSIONS (demande Yann 08/09 : « occlusions aussi en v1 »). Hewson
#      ne les localise pas directement. On prend la définition classique :
#      l'occlusion est la CRÊTE de θe (la « langue chaude » rejetée en
#      altitude) qui relie le L au point triple. Détectée comme ligne de
#      crête du champ τ (gradient parallèle à un vecteur propre du
#      hessien : Q = (τx²−τy²)τxy − τxτy(τxx−τyy) = 0, avec la courbure
#      TRANSVERSE au gradient nettement négative), gardée seulement à moins
#      de `occl_max_dist_km` d'un L de prominence suffisante et raccordée
#      à moins de `occl_join_km` d'un front froid/chaud. ⚠️ C'est la partie
#      la moins établie : `FRONTS['occlusions']` la coupe sans toucher au
#      reste.
# Géométrie de sortie : moyenne glissante (un front est une courbe douce)
# puis RDP (même tolérance que le synop). Chaque front : {kind, coords,
# side, strength}. `side` : côté des symboles PAR RAPPORT À L'ORDRE DES
# POINTS, +1 = à GAUCHE quand on parcourt le tracé (repère géographique,
# nord en haut). Froid / chaud / occlus : le côté vers lequel le front
# AVANCE (chaud pour un froid, froid pour un chaud, sens de v_n pour un
# occlus). Stationnaire : le côté de l'air CHAUD (le web y pose les
# triangles et les demi-cercles de l'autre côté). ⚠️ Marching squares ne
# garantit AUCUNE orientation des points : le côté est calculé depuis ŝ,
# jamais déduit de l'ordre.
# Latitudes : rien au-delà de ±FRONTS['lat_max'] (la zone barocline
# polaire est permanente et sans intérêt pour un pilote, et Mercator y
# ment).
# ⚠️ Limite connue (v1) : là où 850 hPa est SOUS le relief (Tibet,
# Groenland, Antarctique, Andes), T850 est une extrapolation et peut
# produire des fronts fantômes. Pas de `surface_pressure` dans le `.om`
# (vérifié le 08/09) pour les masquer proprement — à regarder sur les
# échéances réelles avant de décider d'un masque statique.
FRONTS_VERSION = 1
R_EARTH_M = 6_371_000.0
FRONTS = dict(
    # ⚠️ Tous ces seuils sont CALIBRÉS sur l'échéance réelle contre la
    # carte Met Office de la même heure (banc_fronts_08-09.py, note du
    # 08/09) — pas recopiés de Hewson, dont la maille (~100 km) et le
    # champ (θw) diffèrent. Les valeurs essayées et leur effet sont dans
    # la note projet.
    # MESURÉ le 08/09 (échéance 12:00, globe ±70°) : |∇θe| médian 1,6 K/
    # 100 km, p90 4,4, p99 8,8 ; TFP p90 2,0, p99 5,6 K/(100 km)². Les
    # seuils de départ (1,5 / 0,5, esprit Hewson) donnaient 885 fronts
    # sur le globe ; 4,5 / 2,5 → 228 ; 5,5 / 3,5 → 139 (13 dans la fenêtre
    # Met Office, dont le front froid Manche→Biscaye→Galice et le système
    # du L 993 atlantique au bon endroit) ; 5,5 / 3,5 avec σ = 4 → 53, en
    # perdant le L 993. Retenu : 5,5 / 3,5, σ = 3.
    smooth_sigma_cells=3.0,      # lissage de θe avant les dérivées (0,25° → ~85 km)
    grad_min_k_100km=5.5,        # K1 : max(|∇θe|) sur ~140 km ≥ K1 (K/100 km)
    tfp_min_k_100km2=3.5,        # K2 : TFP ≥ K2 sur le bord chaud (K/(100 km)²)
    min_length_km=500.0,         # morceaux plus courts jetés
    lat_max=70.0,                # rien au-delà (zone barocline polaire)
    # MESURÉ le 08/09 sur le globe : sans ce plancher, 35 « stationnaires »
    # sur 80 fronts, dont l'essentiel entre 10 et 25° N (Sahel, Arabie,
    # Inde) — des contrastes d'HUMIDITÉ de mousson, pas des fronts. Aucun
    # service ne trace de fronts sous 20-25° ; les cartes Met Office
    # s'arrêtent à 30° N.
    lat_min=20.0,
    # Boîtes (ouest, sud, est, nord) où 850 hPa est SOUS le sol : T850 y
    # est extrapolée et produisait un paquet de fronts sur le plateau
    # tibétain (vu le 08/09). Masque STATIQUE, faute de `surface_pressure`
    # dans le `.om`. Andes / Rocheuses : pas masquées (v1), à surveiller.
    mask_boxes=((73.0, 27.0, 105.0, 40.0),),   # plateau tibétain
    vn_stationary_ms=2.0,        # |v·ŝ| en deçà → stationnaire
    smooth_window_pts=5,         # moyenne glissante du tracé (points)
    # Occlusions — MESURÉ le 08/09 : courbure 1 / prominence 4 / 1 500 km
    # → 63 occlusions pour 18 fronts froids (impossible) ; 3 / 8 → 16 ;
    # 5 / 8 / 1 000 km → 4 sur le globe, 1 dans la fenêtre Met Office,
    # près du L 993 où le Met Office en trace une. Celle du L 989 (Écosse)
    # n'est PAS trouvée : la crête de θe y est trop faible. Sévère, donc.
    occlusions=True,             # interrupteur de la détection des occlusions
    occl_sigma_cells=4.0,        # lissage (plus fort) pour la crête de θe
    occl_curv_min=5.0,           # courbure transverse ≤ −K3 (K/(100 km)²)
    occl_max_dist_km=1000.0,     # à moins de … d'un L
    occl_low_prominence_hpa=8.0, # … de prominence ≥ …
    occl_join_km=400.0,          # raccordé à un front froid/chaud à moins de …
    occl_min_length_km=300.0,
)

def theta_e(t_c, rh_pct, p_hpa=850.0):
    """θe (K) — Bolton (1980), Mon. Wea. Rev. 108, 1046-1053 :
      es(T) = 6,112·exp(17,67·T/(T+243,5))        (éq. 10, T en °C, hPa)
      e = RH·es ; r = 0,622·e/(p−e)               (rapport de mélange, kg/kg)
      T_L = 1/(1/(T_K−55) − ln(RH)/2840) + 55     (éq. 22, niveau de condensation)
      θe = T_K·(1000/p)^(0,2854·(1−0,28·r))·exp[(3,376/T_L − 0,00254)·r·1000·(1+0,81·r)]
                                                  (éq. 38, r en kg/kg ici)
    Test (banc) : T = 10 °C, RH = 80 %, 850 hPa → 318,0 K, recalculé à la
    main le 08/09 (es = 12,27 hPa, r = 7,27 g/kg, T_L = 279,1 K)."""
    t_c = np.asarray(t_c, dtype=np.float64)
    rh = np.clip(np.asarray(rh_pct, dtype=np.float64), 1.0, 100.0) / 100.0
    t_k = t_c + 273.15
    es = 6.112 * np.exp(17.67 * t_c / (t_c + 243.5))
    e = rh * es
    r = 0.622 * e / (p_hpa - e)
    t_l = 1.0 / (1.0 / (t_k - 55.0) - np.log(rh) / 2840.0) + 55.0
    return (t_k * (1000.0 / p_hpa) ** (0.2854 * (1.0 - 0.28 * r))
            * np.exp((3.376 / t_l - 0.00254) * r * 1000.0 * (1.0 + 0.81 * r)))

def grad_m(f, lat1d, dlat_deg, dlon_deg, periodic_lon=True):
    """∂f/∂x, ∂f/∂y en unités de f PAR MÈTRE, différences centrées.
    x = est (R·cos φ·dλ), y = nord (R·dφ). Longitude PÉRIODIQUE sur la
    grille Monde (−180 → 179,75 : la colonne suivant 179,75 est −180)."""
    dy = R_EARTH_M * np.radians(dlat_deg)
    dx = R_EARTH_M * np.radians(dlon_deg) * np.cos(np.radians(lat1d))[:, None]
    dx = np.where(np.abs(dx) < 1.0, 1.0, dx)      # pôle : évite la division par ~0
    if periodic_lon:
        fx = (np.roll(f, -1, axis=1) - np.roll(f, 1, axis=1)) / (2.0 * dx)
    else:
        fx = np.gradient(f, axis=1) / dx
    fy = np.gradient(f, axis=0) / dy
    return fx, fy

def _smooth(f, sigma, periodic_lon=True):
    return gaussian_filter(f, sigma=sigma, mode=("nearest", "wrap" if periodic_lon else "nearest"))

def _grid_steps(lon2d, lat2d):
    lat1d, lon1d = lat2d[:, 0], lon2d[0, :]
    dlat = (lat1d[-1] - lat1d[0]) / max(len(lat1d) - 1, 1)
    dlon = (lon1d[-1] - lon1d[0]) / max(len(lon1d) - 1, 1)
    return lat1d, lon1d, float(dlat), float(dlon)

def front_fields(lon2d, lat2d, t850_c, rh850, u850, v850, cfg=FRONTS):
    """Les champs du §2 : τ lissé, G (K/m), ŝ, TFP (K/m²), le locateur
    L = ∇TFP·ŝ, v_n = v·ŝ (m/s) et, pour les occlusions, la crête de τ.
    Tout est renvoyé dans un dict ; les seuils ne sont PAS appliqués ici
    (c'est `front_locator` qui masque) — le banc peut ainsi mesurer les
    distributions avant de choisir K1/K2."""
    lat1d, lon1d, dlat, dlon = _grid_steps(lon2d, lat2d)
    periodic = abs((lon1d[-1] - lon1d[0]) + dlon - 360.0) < 1e-6
    tau = _smooth(theta_e(t850_c, rh850), cfg["smooth_sigma_cells"], periodic)
    tx, ty = grad_m(tau, lat1d, dlat, dlon, periodic)
    g = np.hypot(tx, ty)
    g_safe = np.where(g < 1e-12, 1e-12, g)
    sx, sy = tx / g_safe, ty / g_safe
    gx, gy = grad_m(g, lat1d, dlat, dlon, periodic)
    tfp = -(gx * sx + gy * sy)
    lx, ly = grad_m(tfp, lat1d, dlat, dlon, periodic)
    loc = lx * sx + ly * sy
    us = _smooth(np.asarray(u850, dtype=np.float64), cfg["smooth_sigma_cells"], periodic)
    vs = _smooth(np.asarray(v850, dtype=np.float64), cfg["smooth_sigma_cells"], periodic)
    vn = us * sx + vs * sy
    # ~140 km : 5 cellules sur 0,25°, indépendant de la latitude en lignes,
    # un peu plus large en km vers l'équateur — un majorant, c'est voulu.
    g_near = maximum_filter(g, size=5, mode=("nearest", "wrap" if periodic else "nearest"))
    out = dict(tau=tau, g=g, sx=sx, sy=sy, tfp=tfp, loc=loc, vn=vn, g_near=g_near,
               lat1d=lat1d, lon1d=lon1d, dlat=dlat, dlon=dlon, periodic=periodic)
    if cfg["occlusions"]:
        tau2 = _smooth(theta_e(t850_c, rh850), cfg["occl_sigma_cells"], periodic)
        ax, ay = grad_m(tau2, lat1d, dlat, dlon, periodic)
        axx, axy = grad_m(ax, lat1d, dlat, dlon, periodic)
        _, ayy = grad_m(ay, lat1d, dlat, dlon, periodic)
        # Q = 0 : gradient parallèle à un vecteur propre du hessien (crête
        # ou vallée) ; `curv_t` = dérivée seconde PERPENDICULAIRE au
        # gradient — nettement négative sur une crête.
        q = (ax * ax - ay * ay) * axy - ax * ay * (axx - ayy)
        n2 = ax * ax + ay * ay
        n2 = np.where(n2 < 1e-24, 1e-24, n2)
        curv_t = (ay * ay * axx - 2.0 * ax * ay * axy + ax * ax * ayy) / n2
        out.update(occl_q=q, occl_curv=curv_t, occl_g=np.sqrt(n2))
    return out

def _zero_contours(lon2d, lat2d, field):
    """Lignes de niveau 0 de `field` (marching squares matplotlib, comme
    les isobares). Renvoie une liste de tableaux (n, 2) lon/lat."""
    fig, ax = plt.subplots()
    cs = ax.contour(lon2d, lat2d, field, levels=[0.0])
    segs = [np.asarray(s, dtype=float) for s in cs.allsegs[0] if len(s) >= 2]
    plt.close(fig)
    return segs

def _sample(field, lon, lat, F):
    """Interpolation bilinéaire d'un champ aux points (lon, lat)."""
    from scipy.ndimage import map_coordinates
    j = (lat - F["lat1d"][0]) / F["dlat"]
    i = (lon - F["lon1d"][0]) / F["dlon"]
    return map_coordinates(field, [j, i], order=1, mode="nearest")

def _length_km(seg):
    """Longueur d'un tracé lon/lat en km (plan local, cos φ)."""
    if len(seg) < 2:
        return 0.0
    lat_m = np.radians((seg[1:, 1] + seg[:-1, 1]) / 2.0)
    dx = np.radians(np.diff(seg[:, 0])) * np.cos(lat_m)
    dy = np.radians(np.diff(seg[:, 1]))
    return float(np.hypot(dx, dy).sum() * R_EARTH_M / 1000.0)

def _runs(mask):
    """Plages consécutives de True → liste de (début, fin exclusive)."""
    out, start = [], None
    for k, m in enumerate(mask):
        if m and start is None:
            start = k
        elif not m and start is not None:
            out.append((start, k)); start = None
    if start is not None:
        out.append((start, len(mask)))
    return out

def _smooth_seg(seg, window):
    """Moyenne glissante sur le tracé, extrémités conservées."""
    if window < 3 or len(seg) < window:
        return seg
    k = np.ones(window) / window
    out = seg.copy()
    for c in (0, 1):
        out[:, c] = np.convolve(np.pad(seg[:, c], (window // 2, window // 2), mode="edge"), k, mode="valid")
    return out

def _left_is_warm(seg, sx, sy):
    """+1 si l'air chaud (ŝ) est à GAUCHE en parcourant le tracé dans
    l'ordre des points (repère géographique, nord en haut), −1 sinon.
    Moyenne sur le tracé : robuste aux points où la tangente vacille."""
    d = np.diff(seg, axis=0)
    cos = np.cos(np.radians((seg[1:, 1] + seg[:-1, 1]) / 2.0))
    dx, dy = d[:, 0] * cos, d[:, 1]
    # normale gauche de (dx, dy) = (−dy, dx)
    mid_sx, mid_sy = (sx[1:] + sx[:-1]) / 2.0, (sy[1:] + sy[:-1]) / 2.0
    return 1 if float(np.sum(-dy * mid_sx + dx * mid_sy)) >= 0 else -1

def _geo_mask(lon, lat, cfg):
    """Vrai là où un front a le DROIT d'exister : bande de latitude
    [lat_min, lat_max] (deux hémisphères) et hors des `mask_boxes`."""
    ok = (np.abs(lat) <= cfg["lat_max"]) & (np.abs(lat) >= cfg.get("lat_min", 0.0))
    for w, s, e, n in cfg.get("mask_boxes", ()):
        ok &= ~((lon >= w) & (lon <= e) & (lat >= s) & (lat <= n))
    return ok

def front_locator(lon2d, lat2d, F, cfg=FRONTS, tol_deg=0.05):
    """Fronts froids / chauds / stationnaires (§2.4-2.5). Renvoie une
    liste de dicts {kind, coords, side, strength, vn}."""
    k1 = cfg["grad_min_k_100km"] * 1e-5           # K/100 km → K/m
    k2 = cfg["tfp_min_k_100km2"] * 1e-10          # K/(100 km)² → K/m²
    fronts = []
    for seg in _zero_contours(lon2d, lat2d, F["loc"]):
        lon, lat = seg[:, 0], seg[:, 1]
        keep = ((_sample(F["tfp"], lon, lat, F) >= k2)
                & (_sample(F["g_near"], lon, lat, F) >= k1)
                & _geo_mask(lon, lat, cfg))
        for a, b in _runs(keep):
            part = seg[a:b]
            if len(part) < 3 or _length_km(part) < cfg["min_length_km"]:
                continue
            sx = _sample(F["sx"], part[:, 0], part[:, 1], F)
            sy = _sample(F["sy"], part[:, 0], part[:, 1], F)
            vn = float(np.mean(_sample(F["vn"], part[:, 0], part[:, 1], F)))
            strength = float(np.mean(_sample(F["g"], part[:, 0], part[:, 1], F))) * 1e5
            warm_left = _left_is_warm(part, sx, sy)
            if vn > cfg["vn_stationary_ms"]:
                kind, side = "cold", warm_left            # avance vers le chaud
            elif vn < -cfg["vn_stationary_ms"]:
                kind, side = "warm", -warm_left           # avance vers le froid
            else:
                kind, side = "stationary", warm_left      # côté de l'air chaud
            coords = simplify_rdp(_smooth_seg(part, cfg["smooth_window_pts"]), tol_deg)
            fronts.append(dict(kind=kind, side=side, strength=round(strength, 2),
                               vn=round(vn, 1), coords=coords))
    return fronts

def occlusion_locator(lon2d, lat2d, F, centers, fronts, cfg=FRONTS, tol_deg=0.05):
    """§6 — crêtes de θe près d'un L, raccordées à un front. Le côté des
    symboles est le sens d'avance (signe de v_n)."""
    if not cfg["occlusions"] or "occl_q" not in F:
        return []
    lows = [c for c in centers if c["kind"] == "L"
            and c.get("prominence", 0) >= cfg["occl_low_prominence_hpa"]]
    if not lows or not fronts:
        return []
    k3 = cfg["occl_curv_min"] * 1e-10
    ends = np.array([p for f in fronts for p in (f["coords"][0], f["coords"][-1])], dtype=float)

    def dist_km(lon, lat, lon0, lat0):
        return (np.hypot(np.radians(lon - lon0) * np.cos(np.radians((lat + lat0) / 2.0)),
                         np.radians(lat - lat0)) * R_EARTH_M / 1000.0)

    out = []
    for seg in _zero_contours(lon2d, lat2d, F["occl_q"]):
        lon, lat = seg[:, 0], seg[:, 1]
        near_low = np.zeros(len(seg), dtype=bool)
        for c in lows:
            near_low |= dist_km(lon, lat, c["lon"], c["lat"]) <= cfg["occl_max_dist_km"]
        keep = ((_sample(F["occl_curv"], lon, lat, F) <= -k3)
                & near_low & _geo_mask(lon, lat, cfg))
        for a, b in _runs(keep):
            part = seg[a:b]
            if len(part) < 3 or _length_km(part) < cfg["occl_min_length_km"]:
                continue
            # raccord : une extrémité de la crête à moins de occl_join_km
            # d'une extrémité d'un front froid/chaud (le point triple)
            joined = False
            for p in (part[0], part[-1]):
                if np.any(dist_km(ends[:, 0], ends[:, 1], p[0], p[1]) <= cfg["occl_join_km"]):
                    joined = True; break
            if not joined:
                continue
            vn = float(np.mean(_sample(F["vn"], part[:, 0], part[:, 1], F)))
            sx = _sample(F["sx"], part[:, 0], part[:, 1], F)
            sy = _sample(F["sy"], part[:, 0], part[:, 1], F)
            # sens d'avance = sens de v_n le long de ŝ
            side = _left_is_warm(part, sx, sy) * (1 if vn >= 0 else -1)
            strength = float(np.mean(_sample(F["g"], part[:, 0], part[:, 1], F))) * 1e5
            coords = simplify_rdp(_smooth_seg(part, cfg["smooth_window_pts"]), tol_deg)
            out.append(dict(kind="occluded", side=side, strength=round(strength, 2),
                            vn=round(vn, 1), coords=coords))
    return out

def fronts_features(lon2d, lat2d, t850_c, rh850, u850, v850, centers, cfg=FRONTS, tol_deg=0.05):
    """Chaîne complète → liste de fronts sérialisables (clé `fronts` du
    `.synop.json`, cf. `process_grid`)."""
    F = front_fields(lon2d, lat2d, t850_c, rh850, u850, v850, cfg)
    fronts = front_locator(lon2d, lat2d, F, cfg, tol_deg)
    fronts += occlusion_locator(lon2d, lat2d, F, centers, fronts, cfg, tol_deg)
    return [dict(kind=f["kind"], side=int(f["side"]), strength=f["strength"], vn=f["vn"],
                 coords=[[round(float(x), 3), round(float(y), 3)] for x, y in f["coords"]])
            for f in fronts]

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

def manifest_profil(cfg):
    """08/09/2026 — les champs du manifest qui décrivent CE QUI EST PRODUIT
    pour cette grille. Ils servent deux fois : écrits dans le manifest, et
    comparés à celui du run précédent pour décider d'un recalcul du passé.

    ⚠️ `levelStepHpa` est ABSENT du manifest Monde (aucun `<iso>.json`
    détaillé n'existe pour cette grille) et `synopStepHpa` absent de celui
    d'Europe. Le web doit accepter les deux formes — c'est exactement ce
    qui lui dit quelle version il peut demander à quelle grille."""
    p = {"centersVersion": CENTERS_VERSION}
    if "detail" in cfg["variants"]:
        p["levelStepHpa"] = LEVEL_STEP_HPA
    if "synop" in cfg["variants"]:
        p["synopStepHpa"] = SYNOP_STEP_HPA
    # 08/09/2026 : `frontsVersion` n'est écrit que pour la grille qui
    # produit des fronts. Absent du manifest précédent → le passé est
    # recalculé une fois (79 échéances, cf. `reprocess_past`).
    if cfg.get("fronts"):
        p["frontsVersion"] = FRONTS_VERSION
    return p

PROFIL_KEYS = ("levelStepHpa", "synopStepHpa", "centersVersion", "frontsVersion")

def echeances_publiees(key, attendu):
    """Les échéances DÉJÀ dans le bucket, lues dans le manifest du run
    précédent. Renvoie `(set d'ISO, manifest_lu, profil_ok, manifest_brut)`
    — le troisième dit si ces échéances ont été produites avec le PROFIL
    attendu par ce run (versions produites + `centersVersion`, cf.
    `manifest_profil`) ; sinon le passé est recalculé une fois.

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
        return set(), False, False, None
    times = {t for t in brut["times"] if isinstance(t, str)}
    # 07/09/2026 : le passé n'est « déjà là » que s'il porte les fichiers
    # que CE run produirait. Un manifest antérieur (sans `synopStepHpa`,
    # avec un autre pas, ou d'une époque où cette grille produisait les
    # DEUX versions) décrit un bucket dont le contenu ne correspond plus —
    # on recalcule alors tout le passé, une seule fois : le manifest écrit
    # par ce run portera le bon profil. Même mécanique que le rattrapage
    # `centers` du 23/07, mais automatique.
    # ⚠️ La comparaison porte sur les TROIS clés, absence comprise
    # (`.get()` vaut None des deux côtés) : c'est ce qui fait qu'une
    # grille qui PERD une version voit son passé recalculé, pas seulement
    # une grille qui en gagne une.
    profil_ok = all(brut.get(k) == attendu.get(k) for k in PROFIL_KEYS)
    print(f"  manifest précédent : {len(times)} échéance(s) déjà publiée(s)"
          + ("" if profil_ok else " — profil différent : passé recalculé"))
    return times, True, profil_ok, brut

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

def retire_variant(key, keep_isos, brut_prec, variants):
    """08/09/2026 — supprime les fichiers d'une VERSION qu'une grille ne
    produit plus. Cas réel du jour : l'Europe ne produit plus de
    `<iso>.synop.json` (le synoptique est passé au Monde), et
    `purge_stale` ne sait pas les voir — elle ne supprime que les
    ÉCHÉANCES sorties de la fenêtre, or celles-ci restent.

    Se déclenche sur le manifest PRÉCÉDENT : s'il annonçait la version et
    que le profil de ce run ne l'a plus. Donc une seule fois — le manifest
    que ce run vient d'écrire ne l'annonce plus. Non bloquant, et
    silencieux quand il n'y a rien à faire (aucun appel au stockage)."""
    if not isinstance(brut_prec, dict):
        return 0
    obsoletes = []
    if brut_prec.get("synopStepHpa") is not None and "synop" not in variants:
        obsoletes.append(".synop.json")
    if brut_prec.get("levelStepHpa") is not None and "detail" not in variants:
        obsoletes.append(".json")
    if not obsoletes:
        return 0
    if DRY_RUN:
        print(f"  (DRY_RUN — retrait de version sur '{key}' non exécuté : "
              f"{len(keep_isos)} × {', '.join(obsoletes)})")
        return 0
    removed = 0
    for iso in keep_isos:
        for suffixe in obsoletes:
            if STORE.delete(f"{key}/{iso}{suffixe}"):
                removed += 1
    print(f"  retrait de version sur '{key}' : {removed} fichier(s) "
          f"{', '.join(obsoletes)} supprimé(s)")
    return removed

def process_grid(key, cfg):
    model, variants = cfg["model"], cfg["variants"]
    print(f"— {key} ({model}) — version(s) : {', '.join(variants)} —")
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

    quoi = []
    if "detail" in variants:
        quoi.append(f"détaillé {LEVEL_STEP_HPA} hPa")
    if "synop" in variants:
        quoi.append(f"synoptique {SYNOP_STEP_HPA} hPa")
    if cfg.get("fronts"):
        quoi.append(f"fronts (Hewson, θe 850 hPa, v{FRONTS_VERSION})")
    print(f"  contourage : {' + '.join(quoi)} (lissage σ = "
          f"{cfg['smooth_sigma_cells']} cellules"
          + (f", latitudes bornées à ±{cfg['lat_clip_deg']:g}°" if cfg["lat_clip_deg"] else "")
          + ")")

    attendu = manifest_profil(cfg)
    # UNE lecture (Class B) qui remplace ~90 HeadObject + un ListObjects
    # (Class A) — cf. `echeances_publiees`. Elle sert trois fois : au
    # skip-if-exists ci-dessous, à la purge en fin de fonction, et au
    # ménage ponctuel des `.synop.json` Europe (`retire_variant`).
    publiees, manifest_lu, profil_ok, brut_prec = echeances_publiees(key, attendu)
    reprocess_past = FORCE_REPROCESS_PAST or not profil_ok

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
        # 08/09/2026 (fronts) : les 4 champs 850 hPa sont lus dans le MÊME
        # fichier que la pression, en une seule ouverture.
        names = ("pressure_msl",) + (FRONT_FIELDS if cfg.get("fronts") else ())
        result = read_fields(model, dt, names, reference_time=None if is_past else reference_time)
        if result is None:
            print(f"  ⚠️ {iso} absent (purgé ou pas encore publié) — ignoré")
            continue
        lon_full, lat_full, fields = result
        # 08/09/2026 : la coupe en latitude vient AVANT tout le reste —
        # lissage, centres et contourage travaillent sur la même grille,
        # sinon un centre pourrait être détecté là où aucune isobare n'est
        # tracée.
        lon2d, lat2d, pressure = clip_latitude(lon_full, lat_full, fields["pressure_msl"], cfg["lat_clip_deg"])
        # 07/09/2026 : les centres H/L sont détectés sur le champ LISSÉ —
        # sur le champ brut 0,1°, un creux thermique de vallée ou une
        # bulle côtière de 1 hPa suffisait à voler la place d'un vrai
        # centre. Quand une grille produit ses deux versions, elles
        # reçoivent les MÊMES centres : un pilote qui bascule de version
        # ne doit pas voir un H changer de place.
        smooth = smooth_pressure(pressure, cfg["smooth_sigma_cells"])
        centers = find_centers(lon2d, lat2d, smooth,
                               max_per_kind=cfg["max_centers_per_kind"])
        if "detail" in variants:
            geo = isobars_geojson(lon2d, lat2d, pressure, step_hpa=LEVEL_STEP_HPA)
            geo["centers"] = centers
            sb_upload(obj_path, json.dumps(geo, separators=(",", ":")).encode())
        if "synop" in variants:
            synop = synop_geojson(lon2d, lat2d, smooth, cfg["synop_tol_deg"],
                                  cfg["synop_min_length_deg"])
            synop["centers"] = centers
            if cfg.get("fronts"):
                # Même run, même échéance, même fichier : un pilote ne
                # verra jamais des fronts d'un run et des isobares d'un
                # autre. Les centres (avec `prominence`) servent aux
                # occlusions.
                f850 = [clip_latitude(lon_full, lat_full, fields[n], cfg["lat_clip_deg"])[2]
                        for n in FRONT_FIELDS]
                synop["fronts"] = fronts_features(lon2d, lat2d, *f850, centers,
                                                  tol_deg=cfg["synop_tol_deg"])
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
        # 08/09/2026 : `levelStepHpa` / `synopStepHpa` ne sont écrits que
        # pour les versions RÉELLEMENT produites par cette grille (cf.
        # `manifest_profil`). Le manifest décrit ce qui existe dans le
        # bucket, pas ce que le script sait faire.
        **attendu,
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
    # 08/09/2026 : et le ménage de la version que cette grille ne produit
    # PLUS (les `.synop.json` Europe). Après `purge_stale`, donc sur la
    # liste des échéances qui restent.
    retire_variant(key, manifest_times, brut_prec, variants)
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
    # 08/09/2026 : DEUX grilles, UN fichier par échéance chacune → même
    # ordre de grandeur (79 × 2 + 2 manifests = 160 à froid). Le poids
    # ajouté par le Monde est celui d'un synoptique 0,25° sur le globe —
    # mesuré au DRY_RUN avant le premier run réel, cf. la note du jour.
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
    for key, cfg in GRIDS.items():
        total += process_grid(key, cfg)
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
