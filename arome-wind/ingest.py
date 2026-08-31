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

31/08/2026 — TROISIÈME préfixe : `arome/rafale/{tLat}_{tLon}.json`, la
rafale 10 m (max sur l'heure écoulée), en tuiles SÉPARÉES du vent sol.
Même forme, même tuilage, mêmes `times[]` ; un champ de plus,
`gustTimes`, qui dit à quelles échéances la rafale existe (elle est
absente à τ = 0). Cf. GUST_SN plus bas.

Stockage (03/08/2026) : l'upload passe par `tools/storage.py`, un seul
module pour les 5 chaînes, avec deux implémentations derrière la même
signature. La destination se choisit par variable d'environnement :

  STORAGE_BACKEND   supabase (défaut) | r2 | both
  SUPABASE_URL, SUPABASE_SERVICE_KEY      — requis si backend supabase/both
  R2_ACCOUNT_ID, R2_ACCESS_KEY_ID,
  R2_SECRET_ACCESS_KEY, R2_BUCKET         — requis si backend r2/both
  WIND_GRID_BUCKET optionnel, défaut wind-grid
  DRY_RUN=1 pour tester le calcul/tuilage sans rien téléverser.
"""
import os, sys, json, math, time
from datetime import datetime, timezone, timedelta
from eccodes import (codes_grib_new_from_file, codes_get, codes_get_values,
                     codes_release)

# 10/08/2026 (lot H) — `http_get`, `s3_keys`, `covered_steps` et
# `download_tmp` vivaient ICI. Elles sont maintenant dans
# `tools/mf_s3.py`, À L'IDENTIQUE, parce que le poller de run d'AGRUME en
# a besoin et que la consigne du lot est « étendre, ne pas réécrire ».
# Même motif que `tools/storage.py` le 03/08 (cinq copies de sb_upload
# réunies en un module). Aucun appelant de ce fichier ne change.
# ⚠️ `S3` reste importé sous son nom historique : plusieurs commentaires
# et le message de log y font référence.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))
from mf_s3 import (S3, bornes_echeances, covered_steps,   # noqa: E402,F401
                   download_tmp, est_fichier_horaire, http_get, s3_keys)

# ── Config (à garder synchronisé avec web/src/lib/config.ts) ──────────
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
MAX_HOURS  = 51                     # 05/08/2026 : REMONTÉ de 36 à 51 h — l'horizon
                                     # réel d'AROME-HD (relevé de 48 à 51 le
                                     # 25/07/2026 après mesure, cf.
                                     # NOTES_TECHNIQUES_THERMIQUES_AROME.md).
                                     # Historique : abaissé de 51 à 36 h le 30/07/2026
                                     # pour le quota Storage Supabase (cf. BUGS.md,
                                     # dépassement du 30/07 — arome/sol + arome/alt
                                     # pesaient 1,02 Go des 2,1 Go du compte). Cette
                                     # contrainte n'existe plus : la chaîne écrit sur
                                     # R2 depuis le 03/08 et `wind-grid` côté Supabase
                                     # a été purgé le 05/08.
                                     # Coût chiffré le 03/08 sur `keep_step()` évalué
                                     # aux 8 heures de run : 31,0 échéances à 36 h
                                     # contre 43,5 à 51 h, soit ×1,40 → arome/sol +
                                     # arome/alt passent de 588 à ~825 Mo (11 % du
                                     # palier R2 de 10 Go). ⚠️ Les ÉCRITURES ne
                                     # bougent pas d'un objet : les échéances vivent
                                     # DANS les fichiers, pas dans les clés — 505
                                     # tuiles par run dans les deux cas.
                                     # Rien à changer côté frontend : le client lit
                                     # `times` du manifest, aucune constante d'horizon
                                     # n'est codée en dur dans web/src (vérifié).
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
# 30/07/2026 (quota Storage, 2e passe) : 600 et 500 hPa RETIRÉS — soit
# ~4 200 et ~5 600 m AMSL, bien au-dessus du plafond parapente (et
# au-dessus du plafond réglementaire sans oxygène). 9 -> 7 niveaux =
# −22 % sur arome/alt, mesuré à 209 Mo -> ~163 Mo.
# ⚠️ Cette liste est DUPLIQUÉE dans web/src/lib/config.ts
# (`WIND_GRID_LEVELS`), sans code partagé entre les deux repos, et le
# client ne la lit PAS depuis le manifest : les deux listes doivent bouger
# ensemble, sinon le sélecteur d'altitude propose des paliers dont les
# tuiles n'existent plus (404 silencieux, calque vide en haut de gamme).
LEVELS     = [1000, 950, 925, 900, 850, 800, 700]  # cf. WIND_GRID_LEVELS
MODEL_KEY  = "meteofrance_seamless" # clé "model" écrite dans le JSON (AROME)

# ── RAFALE 10 m (31/08/2026) ──────────────────────────────────────────
# Les DEUX COMPOSANTES du vecteur rafale, dans le MÊME paquet SP1 que
# 10u/10v : déjà téléchargées à chaque run, jusqu'ici vues par
# `parse_grib` puis jetées par `sol_want`. Zéro téléchargement, zéro
# requête, zéro quota en plus (mesuré le 31/08, cf. la note de
# faisabilité `rafale-sur-le-calque-vent-sol-faisabilite-31-08.md`).
#
# ⚠️ Ce n'est PAS `max_i10fg` (le scalaire de la grille 0025 que lit
# AGRUME) : la grille 001 publie les composantes. Vérifié avant d'écrire
# une ligne de code — `hypot(max_10efg, max_10nfg)` contre `max_i10fg`
# du 0025, n = 18 981 points : médiane d'écart 0,00 km/h, ratio médian
# 1,000. Ce sont bien les composantes du VECTEUR, donc `_ms()` s'applique
# tel quel et la DIRECTION de la rafale est disponible (le 0025 ne la
# donne pas).
#
# ⛔ DEUX LIMITES QUI DOIVENT ÊTRE ÉCRITES DANS L'UI, PAS DÉCOUVERTES À
#    L'ÉCRAN (cf. `gustTimes` plus bas et les locales du client) :
#    1. `stepType = max`, `stepRange = 2-3` → c'est le MAXIMUM SUR
#       L'HEURE ÉCOULÉE, pas la valeur à l'instant. Le pilote qui lit
#       14:00 lit le max de 13:00 à 14:00.
#    2. ABSENTE à τ = 0 : le fichier 00H ne porte que `2t 2r 10u 10v`.
#       La première échéance n'a donc PAS de rafale — on écrit `null`,
#       JAMAIS un repli sur le vent moyen (règle du 28/08 : un `gust`
#       qui vaudrait le `speed` serait une rafale FABRIQUÉE).
GUST_SN    = ("max_10efg", "max_10nfg")   # composantes est / nord

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
BUCKET  = os.environ.get("WIND_GRID_BUCKET", "wind-grid")
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

# ── HTTP / S3 helpers ─────────────────────────────────────────────────
# (déplacés dans `tools/mf_s3.py`, cf. l'import en tête de fichier)

def pick_run():
    """Run AROME offrant le PLUS d'échéances réellement publiées, à la fois
    sur SOL (SP1, grille 001) ET ALTITUDE (IP1, grille 0025).

    ⚠️ Débogage 25/07/2026 (retour Yann : le curseur temporel du calque
    vent plafonnait à ~6 h après le run — « sam. 23:00 / Run sam. 17:00 »
    — au lieu des ~48-51 h attendues). Sondage en direct du manifest de
    prod à ce moment-là : run 15h UTC, SEULEMENT 7 fichiers SP1 publiés
    (échéances 0-6h) et AUCUN IP1 (`"levels": []`). MÊME cause racine que
    le bug corrigé le jour même sur arome-thermal/ingest.py (cf. commit
    `dd666a7`, `pick_run()`) : l'ancienne `latest_run()` prenait le run le
    plus RÉCENT dès qu'UN SEUL fichier SP1 existait, sans vérifier que les
    échéances lointaines (et IP1) étaient publiées. Le cron tourne 2 h
    après le run (`arome-wind.yml`), largement avant que Météo-France ait
    fini de publier les ~51 fichiers horaires SP1 et les bundles IP1
    (encore plus lents à démarrer, observé à 0 à 2h). 3 h plus tard, le
    script suivant saute sur un run encore plus frais, tout aussi
    incomplet, et RÉÉCRIT la tuile en place (bucket entièrement mutable,
    cf. sb_upload) — les échéances lointaines n'étaient donc JAMAIS
    publiées, à aucun run, indéfiniment.

    Nouveau critère, identique dans l'esprit à arome-thermal : parmi les
    runs candidats (du plus récent au plus ancien, jusqu'à 12 h en
    arrière), on retient celui qui maximise la couverture SP1 ∩ IP1 sur
    les échéances utiles (`0..MAX_HOURS`, filtrées par `keep_step`).
    Sortie immédiate dès qu'un run est complet. SOL et ALT restent ISSUS
    DU MÊME run (comme avant ce fix) — cohérent avec le reste du script,
    qui n'a jamais traité les deux indépendamment."""
    base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    base -= timedelta(hours=base.hour % 3)
    best = None                                  # (n_usable, ref, run, steps_needed)
    for back in range(5):                        # 0, 3, 6, 9, 12 h en arrière
        run = base - timedelta(hours=3 * back)
        ref = run.strftime("%Y-%m-%dT%H:00:00Z")
        steps_needed = [h for h in range(0, MAX_HOURS + 1) if keep_step(h, run.hour)]
        if not steps_needed:
            continue
        sp1 = covered_steps(ref, "SP1", GRID_SOL, steps_needed)
        if not sp1:
            continue                             # run pas (encore) publié du tout
        ip1 = covered_steps(ref, "IP1", GRID_ALT, steps_needed)
        cov = sp1 & ip1
        usable = [h for h in steps_needed if h in cov]
        print(f"  run {ref} : {len(usable)}/{len(steps_needed)} échéances exploitables "
              f"({len(sp1)} SP1, {len(ip1)} IP1)")
        if best is None or len(usable) > best[0]:
            best = (len(usable), ref, run, steps_needed)
        if len(usable) == len(steps_needed):
            break                                # complet : inutile de remonter
    if best is None or best[0] == 0:
        raise SystemExit("Aucun run AROME SP1/IP1 exploitable sur les 12 dernières "
                         "heures — rien à publier.")
    n, ref, run, steps_needed = best
    print(f"→ run retenu : {ref} ({n}/{len(steps_needed)} échéances)")
    return ref, run

def files_for(ref, pkg, grid):
    """Fichiers du paquet couvrant les échéances retenues.

    Deux nommages coexistent : la grille 0025 groupe les échéances
    (`__00H06H__`), la grille 001 publie UN FICHIER PAR HEURE (`__06H__`).
    Pour cette dernière on ne télécharge que les échéances effectivement
    gardées (keep_step) — sinon on tirerait 49 fichiers de ~23 Mo pour n'en
    exploiter que 25, soit ~550 Mo de trafic pour rien.

    10/08/2026 : le décodage du nom de fichier passe par
    `mf_s3.bornes_echeances()` — une seule expression régulière pour tout
    le projet, au lieu d'une par appelant."""
    out = []
    for k in s3_keys(f"pnt/{ref}/{MODEL_DIR}/{grid}/{pkg}/"):
        b = bornes_echeances(k)
        if b is None:
            continue
        start, end = b
        if start > MAX_HOURS:
            continue
        if est_fichier_horaire(k) and not keep_step(start):
            continue                       # fichier horaire non retenu
        out.append(k)
    return sorted(out)

# ── Parsing GRIB (eccodes) ────────────────────────────────────────────
def _norm_lon(x):
    return x - 360 if x > 180 else x

def parse_grib(path, want, dtype=None):
    """want(shortName, typeOfLevel, level) -> clé de collecte (ou None pour ignorer).
    Retourne ({clé: {step: values}}, meta_grille). meta = grille commune AROME.

    `dtype` (31/08/2026, lot rafale) — type de stockage des valeurs
    décodées. `None` = comportement d'origine, eccodes rend du float64 :
    c'est ce que reçoivent la grille ALT et l'orographie, INCHANGÉES.

    ⚠️ Ce paramètre existe pour la MÉMOIRE, pas pour la précision. Mesuré
    le 31/08 sur la grille réelle : AROME 001 fait Ni=2801 × Nj=1791 =
    5 016 591 points, soit **40,1 Mo par champ décodé en float64** et
    20,1 Mo en float32. La branche SOL en garde 44 échéances × 2
    composantes (u/v) ; la rafale en ajoute 2 de plus (est/nord). En
    float64 les quatre champs pèseraient ~7,1 Go de pic contre ~3,5 Go
    aujourd'hui — sur un runner GitHub, c'est le genre de marge qu'on ne
    prend pas au hasard. En float32 les QUATRE tiennent dans les ~3,5 Go
    d'aujourd'hui : le lot rafale n'augmente donc pas le pic mémoire du
    run, et il n'a pas fallu re-télécharger SP1 une seconde fois pour ça.
    ⓘ Perte de précision : ~1e-5 m/s sur une composante de vent, alors
    que `_ms()` arrondit à l'ENTIER de km/h juste après. NaN et la
    sentinelle 9999 traversent float32 à l'identique — le garde-fou de
    `_ms()` fonctionne pareil."""
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
                    vals = codes_get_values(gid)
                    # Cast IMMÉDIAT, message par message : convertir après
                    # coup ferait cohabiter les deux copies et annulerait
                    # tout le bénéfice.
                    out.setdefault(key, {})[step] = (
                        vals if dtype is None else vals.astype(dtype, copy=False))
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

def keep_step(h, run_hour=None):
    """Profil d'échéances (débogage 20/07/2026, retour Yann) : horaire
    TOUTE la journée, 1 échéance sur COARSE_EVERY seulement pendant la
    fenêtre nuit (is_night_utc, sur l'heure UTC RÉELLE run+h — pas un
    seuil fixe d'heures écoulées comme l'ancien FINE_H, qui pouvait
    tomber en pleine journée de vol selon l'heure du run).

    `run_hour` explicite (25/07/2026, ajouté pour pick_run()) : pick_run()
    doit évaluer la couverture de PLUSIEURS runs candidats avant d'en
    choisir un, donc avant que `_RUN_HOUR_UTC` (global, fixé dans main())
    ne soit connu. Défaut inchangé pour tous les appels d'origine."""
    if h == 0:
        return True  # état initial toujours gardé, même si le run tombe la nuit
    rh = _RUN_HOUR_UTC if run_hour is None else run_hour
    if rh is None:
        return h <= FINE_H or h % COARSE_EVERY == 0  # filet de sécurité, ne devrait pas arriver
    if is_night_utc((rh + h) % 24):
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
    # 30/07/2026 (quota Storage, 3e passe) : vitesse arrondie à l'ENTIER,
    # plus à la décimale. Ce n'est pas un réglage de précision physique mais
    # de TAILLE DE FICHIER : chaque valeur passe de 4-5 caractères ("12.3")
    # à 2-3 ("12"), sur des tableaux de ~31 échéances par point et ~600 000
    # points par run. Mesuré nécessaire parce qu'`arome/sol` fluctue de
    # ±30 Mo d'un run à l'autre selon qu'il vente ou pas (539 -> 571 Mo
    # observé sans aucun changement de code) : il fallait une marge sous le
    # Go, pas s'asseoir pile sur la ligne.
    # Erreur maximale introduite : 0,5 km/h sur une flèche de carte, alors
    # que l'échelle de couleurs a ses paliers à 8/16/24/32/40 km/h et que
    # l'affichage arrondit déjà. `dir` était de toute façon déjà entier.
    # Seul consommateur client : WindGridLayer.fill(), qui reconvertit
    # immédiatement en u/v flottants pour l'interpolation — l'entier en
    # entrée ne change rien à la douceur du champ interpolé.
    return round(spd), round(drc)

def build_grids(uv_by_step, meta, steps, times, kind, level, step_deg, orog=None,
                sortie_vitesses=None, entree_vitesses=None):
    """Construit les WindGrid par tuile 2° pour un (kind, level) donné.
    uv_by_step: {step: (U_values, V_values)}. Retourne {(tLat,tLon): dict WindGrid}.
    orog (grille ALT uniquement, cf. load_orography) : grille d'élévation AROME
    pour attacher `elev` à chaque point (masquage sous-relief côté client,
    retour Yann 21/07).

    ⛔ 31/08/2026 (lot rafale) — `uv_by_step` peut désormais NE PAS avoir
    une échéance de `steps` : la rafale AROME est absente à τ = 0 (mesuré,
    le fichier 00H ne porte que `2t 2r 10u 10v`). On écrit alors `null` /
    `null` à cet index, JAMAIS une valeur empruntée. C'est la règle
    arbitrée le 28/08 pour la coupe, reprise telle quelle : le pilote lit
    un blanc, pas un chiffre pris ailleurs. Un repli sur le vent moyen
    fabriquerait une rafale — la faute du 24/08.
    ⓘ `steps` reste la série SOL COMPLÈTE, y compris pour la rafale :
    c'est ce qui garde `times[]` aligné entre les deux tuiles et laisse
    le curseur horaire fonctionner sans décalage d'index. La liste des
    échéances où la rafale existe VRAIMENT est écrite à part
    (`gustTimes`), pour que le client le DISE plutôt que le devine.

    ── `sortie_vitesses` / `entree_vitesses` (31/08/2026, lot « écart ») ──
    La tuile RAFALE porte aussi le vent MOYEN (`speedMean`), pour que le
    client puisse montrer l'écart moyen/rafale — l'anneau ou la flèche
    fantôme — SANS charger la tuile sol. Charger les deux rouvrirait
    exactement ce que l'arbitrage A1 avait fermé : deux fichiers, donc
    deux runs possibles (piège du manifeste du 22/08).

    ⭐ Et il n'est PAS recalculé : la passe SOL vient de le calculer pour
    chaque point. `sortie_vitesses` collecte, dans l'ordre des points, le
    triplet (lat, lon, liste speed) ; `entree_vitesses` le relit dans le
    MÊME ordre. Les deux passes appellent `sample_indices(meta, STEP_SOL)`
    avec la même meta et la même BBOX : l'ordre est déterministe. Les
    listes sont PARTAGÉES, pas copiées — la tuile rafale référence l'objet
    de la tuile sol, donc ~15 Mo de pointeurs et pas 800 Mo de doublons.
    C'est ce qui permet de libérer `u`/`v` avant la passe rafale et de
    tenir le pic mémoire d'aujourd'hui.
    ⚠️ L'appariement se VÉRIFIE point par point sur (lat, lon), et lève
    plutôt que d'écrire un `speedMean` décalé d'un point : un vent moyen
    pris chez le voisin serait invisible à l'écran et faux partout."""
    pts = sample_indices(meta, step_deg)
    if entree_vitesses is not None and len(entree_vitesses) != len(pts):
        raise SystemExit(f"speedMean : {len(entree_vitesses)} points collectés à la "
                         f"passe SOL contre {len(pts)} ici — les deux passes ne "
                         f"parcourent pas la même grille, on n'écrit rien.")
    tiles = {}
    for n, (idx, lat, lon) in enumerate(pts):
        tLat = math.floor(lat / TILE_DEG) * TILE_DEG
        tLon = math.floor(lon / TILE_DEG) * TILE_DEG
        g = tiles.get((tLat, tLon))
        if g is None:
            g = tiles[(tLat, tLon)] = dict(
                model=MODEL_KEY, kind=kind, level=level,
                tileLat=tLat, tileLon=tLon, times=times, points=[])
        speed, dir_ = [], []
        for s in steps:
            pair = uv_by_step.get(s)
            if pair is None:
                speed.append(None); dir_.append(None); continue   # cf. τ=0 ci-dessus
            U, V = pair
            sp, dr = _ms(U[idx], V[idx])
            speed.append(sp); dir_.append(dr)
        pt = dict(lat=lat, lon=lon, speed=speed, dir=dir_)
        if sortie_vitesses is not None:
            sortie_vitesses.append((lat, lon, speed))
        if entree_vitesses is not None:
            mlat, mlon, mspeed = entree_vitesses[n]
            if mlat != lat or mlon != lon:
                raise SystemExit(f"speedMean : point {n} desapparie "
                                 f"({mlat},{mlon}) contre ({lat},{lon}) — on n'ecrit "
                                 f"pas un vent moyen pris chez le voisin.")
            pt["speedMean"] = mspeed        # MEME objet liste que la tuile sol
        if orog is not None:
            e = elev_at(orog, lat, lon)
            if e is not None:
                pt["elev"] = e
        g["points"].append(pt)
    return tiles

# ── Upload Supabase Storage ───────────────────────────────────────────
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
# ⚠️ Le défaut `CACHE_REECRIT` (= `no-cache, must-revalidate`) reprend à
# l'identique la politique posée le 24/07/2026, et NE DOIT PAS BOUGER :
# ce bucket n'a QUE des objets réécrits EN PLACE à chaque run (tuiles +
# manifest, même chemin, aucun horodatage dans la clé). Un TTL long y
# laisserait un navigateur — ou un edge CDN, hors de portée du client —
# servir une grille périmée bien après un nouveau run, hard-refresh sans
# effet (cf. BUGS.md, session 23-24/07).
from storage import (Storage, verifier_dimensionnement, Abort,   # noqa: E402
                     CACHE_REECRIT, CACHE_IMMUABLE)

# Instancié dans main(), APRÈS verifier_dimensionnement() : on chiffre
# avant d'écrire, jamais l'inverse (garde-fou n°1).
STORE = None


def sb_upload(path, body, cache_control=CACHE_REECRIT):
    return STORE.put(path, body, cache_control=cache_control)

def merge_parse(files, want, dtype=None):
    merged, meta = {}, None
    for key in files:
        p = download_tmp(key)
        try:
            part, m = parse_grib(p, want, dtype)
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
    global _RUN_HOUR_UTC, STORE
    ref, run = pick_run()
    _RUN_HOUR_UTC = run.hour
    print(f"Run AROME : {ref}")

    # ── Chiffrer AVANT d'écrire (garde-fou n°1) ───────────────────────
    # Comptes RÉELS du bucket relevés le 03/08/2026 par
    # `tools/audit_storage.py` : 63 tuiles sol + 441 tuiles altitude
    # (63 × 7 niveaux) + 1 manifest = 505/run, 8 runs/jour.
    # Ces nombres sont le SEUL garde-fou contre une dérive silencieuse :
    # relever MAX_HOURS, ajouter un niveau ou élargir la BBOX les fait
    # bouger, et la ligne journalisée à chaque run le montre au run près
    # plutôt qu'au relevé mensuel — R2 n'a pas de plafond de dépense.
    # ⚠️ 825 Mo et non 588 depuis le 05/08 : MAX_HOURS est remonté à 51 h
    # (×1,40 sur les échéances). Le nombre d'OBJETS est inchangé — c'est
    # justement pourquoi une dérive d'horizon ne se verrait PAS dans le
    # compteur d'écritures, et pourquoi `mo_par_run` doit suivre à la main.
    # ⚠️ 31/08/2026 (lot rafale) : 505 -> 568 objets et 825 -> 1 680 Mo.
    # Le préfixe `arome/rafale/` ajoute 63 tuiles par run (même tuilage
    # 2°, même BBOX que le sol) et ~853 Mo stationnaires.
    # Le chiffre de stockage vient du modèle de taille VALIDÉ le 31/08 à
    # 0,1 % près sur les tuiles de production :
    #     1 872 801 points × (30 + 44 × 2,98 o/gust + 44 × 3,91 o/dir
    #                            + 44 × 2,78 o/speedMean)
    #   = 853 Mo   (le même modèle prédit 607 Mo pour `arome/sol`, mesuré
    #               606,3 Mo — c'est ce qui autorise à s'en servir ici
    #               plutôt que d'écrire d'abord et de regarder ensuite).
    # ⓘ `speedMean` (+229 Mo) : le vent MOYEN dans la tuile rafale, pour
    # que le client montre l'écart moyen/rafale en ne chargeant QU'UN
    # fichier. Charger les deux aurait rouvert le piège des deux runs que
    # l'arbitrage A1 venait de fermer — et coûté 18 Mo au pilote au lieu
    # de 5,6. Aucun téléchargement ni décodage en plus : la valeur est
    # déjà calculée par la passe SOL, et la LISTE est partagée, pas
    # recopiée.
    # ⓘ La direction EST stockée dans la tuile rafale (arbitrage A1 de
    # Yann, 31/08) : ~320 Mo de plus que de l'emprunter à la tuile sol,
    # mais la tuile rafale se suffit alors à elle-même — un seul fichier
    # chargé par mode, et le risque de mélanger deux runs (piège du
    # manifeste du 22/08) DISPARAÎT au lieu d'être à gérer côté client.
    # Facture : 0 $ (palier gratuit 10 Go) ; hors palier, 0,010 $/mois.
    # ⓘ Écritures : +63/run = +504/jour, ~15 k/mois de plus sur un palier
    # de 1 M — sans effet, mais la ligne journalisée ci-dessous le montre
    # au run près plutôt que de le laisser deviner.
    plafond = verifier_dimensionnement("arome-wind", objets_par_run=568,
                                       runs_par_jour=8, mo_par_run=1680)
    STORE = Storage("arome-wind", "WIND_GRID_BUCKET", "wind-grid", plafond)

    manifest = dict(run=ref, generatedAt=datetime.now(timezone.utc)
                    .strftime("%Y-%m-%dT%H:%M:%SZ"), gridSol=GRID_SOL, gridAlt=GRID_ALT,
                    tileDeg=TILE_DEG, stepSol=STEP_SOL, stepAlt=STEP_ALT,
                    maxHours=MAX_HOURS, levels=[], uploaded=0)
    total = 0

    # ── SOL (10 m) : paquet SP1, variables 10u/10v ────────────────────
    print("SOL (SP1, 10 m) :")
    # 31/08/2026 — le MÊME `want` ramène désormais aussi les deux
    # composantes de la rafale (cf. GUST_SN en tête de fichier). Elles
    # traversaient déjà `parse_grib` : la seule chose qui change est
    # qu'on cesse de les jeter. Un SEUL téléchargement de SP1, comme
    # avant. `float32` : cf. la docstring de `parse_grib` — c'est ce qui
    # permet de tenir les QUATRE champs dans le pic mémoire des deux
    # d'aujourd'hui.
    sol_want = lambda sn, tol, lvl: (sn if (tol == "heightAboveGround"
                                            and (sn in ("10u", "10v") or sn in GUST_SN))
                                     else None)
    brut, meta = merge_parse(files_for(ref, "SP1", GRID_SOL), sol_want, "float32")
    data = {("u" if k == "10u" else "v"): v for k, v in brut.items() if k in ("10u", "10v")}
    gust = {("e" if k == GUST_SN[0] else "n"): v for k, v in brut.items() if k in GUST_SN}
    del brut
    # ⛔ `steps_times` sur `data` SEUL, et surtout PAS sur la rafale : il
    # prend l'INTERSECTION des échéances de tout ce qu'on lui passe. La
    # rafale n'existant pas à τ = 0, lui passer `gust` ferait disparaître
    # la première échéance du calque VENT MOYEN — un calque amputé par
    # l'ajout d'un autre. Le piège est silencieux : la grille resterait
    # parfaitement valide, juste plus courte d'une heure.
    steps, times = steps_times(run, data)
    uv = {s: (data["u"][s], data["v"][s]) for s in steps}
    # `vitesses_moyennes` : les listes `speed` de la passe SOL, collectées
    # dans l'ordre des points, pour que la tuile RAFALE porte le vent moyen
    # sans le recalculer et sans le dupliquer (cf. build_grids).
    vitesses_moyennes = []
    for (tLat, tLon), grid in build_grids(uv, meta, steps, times, "sol", None, STEP_SOL,
                                          sortie_vitesses=vitesses_moyennes).items():
        grid["fetchedAt"] = int(time.time() * 1000)
        sb_upload(f"{MODEL_DIR}/sol/{tLat}_{tLon}.json",
                  json.dumps(grid, separators=(",", ":")).encode())
        total += 1
    manifest["solTimes"] = times
    print(f"  {len(times)} échéances, tuiles téléversées (cumul {total})")
    del data, uv        # ⭐ libéré AVANT de construire les tuiles rafale :
                        # les composantes u/v (~1,8 Go) partent, seules les
                        # listes de vitesses déjà calculées restent (~0,8 Go,
                        # et ce sont les MÊMES objets que ceux qu'on vient
                        # d'écrire). Les deux jeux de tuiles ne coexistent
                        # jamais.

    # ── RAFALE 10 m (SP1, max_10efg/max_10nfg) — 31/08/2026 ───────────
    # Tuiles SÉPARÉES (`arome/rafale/`), arbitrage de Yann du 31/08 : la
    # tuile vent sol ne grossit pas d'un octet, et seul le pilote qui
    # bascule le switch paie le téléchargement. Mêmes `times[]`, même
    # tuilage 2°, même BBOX, même arrondi entier que `_ms()` — donc le
    # client n'a rien de nouveau à savoir lire.
    print("RAFALE (SP1, 10 m, max sur l'heure écoulée) :")
    if "e" in gust and "n" in gust:
        ge, gn = gust["e"], gust["n"]
        # Échéances où la rafale existe VRAIMENT (τ = 0 en est absente).
        # Sous-ensemble de `steps` : on n'invente pas une échéance que le
        # calque moyen n'a pas non plus.
        gust_steps = [s for s in steps if s in ge and s in gn]
        gust_times = [times[i] for i, s in enumerate(steps) if s in gust_steps]
        manquantes = [s for s in steps if s not in gust_steps]
        if manquantes:
            print(f"  ⓘ pas de rafale aux échéances {manquantes} → `null` "
                  f"écrit à ces index (jamais un repli sur le vent moyen)")
        uvg = {s: (ge[s], gn[s]) for s in gust_steps}
        for (tLat, tLon), grid in build_grids(uvg, meta, steps, times,
                                              "rafale", None, STEP_SOL,
                                              entree_vitesses=vitesses_moyennes).items():
            # `gustTimes` : la liste des échéances RENSEIGNÉES, portée par
            # la tuile elle-même. C'est ce qui permet au client de DIRE
            # « pas de rafale à cette échéance » au lieu de laisser une
            # carte vide que le pilote lirait comme une panne — et de le
            # dire sans relire le manifeste, donc sans jamais pouvoir
            # apparier deux runs différents.
            grid["gustTimes"] = gust_times
            # ⓘ Chaque point porte aussi `speedMean` (cf. build_grids) :
            # c'est ce qui permet au client de montrer l'ÉCART moyen /
            # rafale — l'anneau ou la flèche fantôme — en ne chargeant
            # QU'UN fichier. Deux fichiers auraient rouvert le risque
            # d'apparier deux runs.
            grid["fetchedAt"] = int(time.time() * 1000)
            sb_upload(f"{MODEL_DIR}/rafale/{tLat}_{tLon}.json",
                      json.dumps(grid, separators=(",", ":")).encode())
            total += 1
        # Annoncé AUSSI dans le manifeste : le client lit `gustTimes` dans
        # la tuile (ci-dessus), mais l'exploitant, `audit_r2.py` et le
        # prochain qui ouvre ce fichier doivent voir le préfixe exister
        # sans avoir à deviner son nom.
        manifest["gustPrefix"] = f"{MODEL_DIR}/rafale"
        manifest["gustTimes"] = gust_times
        print(f"  {len(gust_times)}/{len(times)} échéances renseignées, "
              f"tuiles téléversées (cumul {total})")
    else:
        # Pas de repli, pas de tuile écrite : mieux vaut un calque qui
        # n'apparaît pas qu'un calque qui montre autre chose que la
        # rafale. Les tuiles du run précédent restent en place.
        print(f"  ⚠️ composantes {GUST_SN} absentes de SP1 — aucune tuile "
              f"rafale écrite pour ce run")
    del gust

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
    STORE.bilan()

if __name__ == "__main__":
    main()
