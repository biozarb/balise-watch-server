#!/usr/bin/env python3
"""collect.py — la collecte nocturne : prévisions et observations.

    Session 08/08/2026.
    cf. PWA/web/CONCEPTION_SCORE_MODELES_06-08.md §15.6, §16, et le §0 bis
    de supabase_step35_model_verification.sql.

═══ CE QUE CE SCRIPT FAIT, ET CE QU'IL NE FAIT PAS ═══

Il collecte, il horodate, il range. **Il ne calcule aucun score.**
`score.py` viendra lire ces fichiers plus tard. Séparer les deux est
délibéré, et c'est la même raison que pour `archive_gust_forecast.py` :
un bug dans la formule de score ne doit jamais pouvoir corrompre la
collecte, qui est irremplaçable.

═══ POURQUOI ON ARCHIVE LES PRÉVISIONS AU LIEU DE LES RATTRAPER ═══

Le §9.1 pariait sur l'API Previous Runs pour reconstituer l'historique
des prévisions rétroactivement. Sondage du 08/08 : **aucun modèle
Météo-France n'y figure** — HTTP 200, le bon nombre d'heures, et rien
que des NULL, sur AROME comme sur ARPEGE, en août 2026 comme en mars.
AROME étant le modèle que lisent réellement les pilotes, le rattrapage
est impossible pour lui.

D'où le choix : on archive les prévisions de TOUS les modèles chaque
nuit, et on les compare plus tard aux mesures. C'est plus lent à
démarrer — quinze nuits avant le premier score à +24 h — mais c'est
symétrique. Rattraper quatre modèles sur huit produirait des chiffres
qu'on ne pourrait pas mettre côte à côte sans mentir.

Coût mesuré le 08/08 sur une requête réelle : 1,9 Ko gzippé par point,
soit **~0,5 Mo/nuit pour 250 points, ~176 Mo/an** sur un palier R2
gratuit de 10 Go. Il n'y a rien à purger.

═══ POURQUOI ON DEMANDE TOUS LES MODÈLES PARTOUT ═══

`src/lib/localModels.ts` sait déjà quel modèle fin couvre quel endroit.
Recopier ses boîtes de domaine ici en ferait une seconde vérité, à
maintenir en double — et le défaut `aliasOf` du 07/08 a montré ce que
coûte une table de domaines qui dérive.

À la place : on demande tous les modèles nommés pour chaque point, et
**on garde ceux qui répondent**. Coût : quelques variables de plus dans
une requête déjà largement sous le quota.

⚠️ CORRECTION DU 08/08 — « SA RÉPONSE EST L'AUTORITÉ SUR SA PROPRE
COUVERTURE » : C'EST FAUX, ET C'ÉTAIT ÉCRIT ICI. Cartographié sur une
grille de 805 points, `meteofrance_arome_france_hd` répond en plein
Atlantique au large du Portugal, `ukmo_uk_deterministic_2km` répond en
Maurienne, et `meteoswiss_icon_ch1` répond en Beauce, à 500 km des
Alpes. Open-Meteo sert la donnée bien au-delà de la zone où un modèle à
aire limitée vaut quelque chose.

Pour la COLLECTE, ça reste sans conséquence : archiver une prévision
médiocre ne coûte que quelques octets, et c'est justement au score de
dire ce qu'elle vaut. Mais pour l'AFFICHAGE, non — et c'est pour ça que
`src/lib/localModels.ts` garde des boîtes rognées à la main, calées
depuis le 08/08 sur les bords mesurés au lieu d'être devinées.

⚠️ Un modèle qui ne rend QUE des nulls ne donne pas de ligne. Écrire
une ligne de nulls ferait croire à une prévision reçue — et sur une
archive non rejouable, ce genre de mensonge est définitif.

═══ OÙ ÇA TOURNE ═══

VPS OVH (Debian 13), en timer systemd — pas en cron : c'est ce que le
VPS utilise déjà depuis le 03/08 (`balise-entretien.timer`), et
`Persistent=true` rattrape un run manqué au démarrage suivant, ce que
cron ne sait pas faire. Voir `model-verif/README.md`.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

# ── Modèles suivis ────────────────────────────────────────────────
# ⚠️ NOMMÉS, JAMAIS `*_seamless`. `meteofrance_seamless` bascule
# silencieusement sur ARPEGE au-delà de ~T+51 h (cf. MODEL_COVERAGE
# dans src/lib/config.ts) : archiver du « seamless » produirait un
# fichier où la colonne AROME contient de l'ARPEGE une partie du temps,
# sans qu'aucune trace ne permette de le savoir après coup.
#
# Horizons relevés le 08/08 sur une réponse réelle (Aussois, 72 h
# demandées) : AROME 52, ICON-D2 52, ICON-CH1 34, les autres 72. Ils
# concordent avec `horizonH` de localModels.ts — ICON-CH1 s'arrête bien
# vers +33 h et ne pourra jamais concourir à +48 h.
#
# ⚠️ `gfs_global` A UNE SECONDE RAISON D'ÊTRE ICI, technique celle-là :
# voir `forecast_rows`. Open-Meteo ne suffixe les clés par le nom du
# modèle que si PLUSIEURS modèles servent le point ; un modèle mondial
# garantit qu'il y en a toujours au moins deux, donc que les clés
# restent attribuables. Ne pas le retirer sans lire ce qui suit.
MODELS = [
    "meteofrance_arome_france_hd",
    "meteofrance_arpege_europe",
    "icon_d2",
    "icon_eu",
    "gfs_global",
    "ecmwf_ifs025",
    "meteoswiss_icon_ch1",
    "meteoswiss_icon_ch2",
    # Ajoutés le 08/08 après cartographie des domaines réels. DMI est
    # le seul modèle à 2 km qui couvre les Pyrénées, la Bretagne et le
    # Sud-Ouest — là où l'app n'avait, en dehors d'AROME, que du 11 à
    # 13 km. ALADIN CE est une famille de modèle de plus (ni ICON ni
    # HARMONIE) sur l'est du pays.
    "dmi_harmonie_arome_europe",
    "chmi_aladin_central_europe_2km",
]

#: Modèle de RÉFÉRENCE pour étiqueter le régime de la journée.
#: ⚠️ Un seul, et le même pour tout le monde : si chaque modèle
#: classait la journée avec son propre vent d'altitude, un modèle
#: pourrait « choisir » le régime dans lequel il est noté. Global et
#: grossier est ici une qualité — un régime est une situation
#: synoptique, pas un détail de vallée.
REGIME_REF_MODEL = "ecmwf_ifs025"

#: Niveau utilisé comme proxy du vent de crête.
#: ⚠️ CE N'EST PAS `crestWind.ts`, qui interpole à l'altitude du sommet
#: le plus proche. 850 hPa ≈ 1 500 m : au-dessus de la couche de brise
#: sur la plupart des massifs français, en dessous des crêtes alpines.
#: Les seuils de `regime.REGIME_THRESHOLDS` (25 / 12 km/h) ont été
#: raisonnés sur un vent de crête, PAS sur du 850 hPa. Ils ne sont
#: calibrés sur rien de toute façon (§16.5) — mais il ne faut pas
#: laisser croire que ce proxy les rend justes.
REGIME_LEVEL = "850hPa"

FORECAST_API = "https://api.open-meteo.com/v1/forecast"
PIOUPIOU_LIVE = "https://api.pioupiou.fr/v1/live-with-meta/all"
PIOUPIOU_ARCHIVE = "https://api.pioupiou.fr/v1/archive/{id}"

#: France + pays limitrophes. Règle par défaut du projet sur toute
#: fonctionnalité à portée géographique : ce n'est pas un outil pour la
#: Maurienne, même si c'est là qu'on a le plus de recul.
BBOX = (41.0, -6.0, 51.5, 11.0)      # latMin, lonMin, latMax, lonMax

BATCH_PAUSE_S = 0.25
MAX_RETRIES = 3
TIMEOUT_S = 45

#: Plafond gratuit Open-Meteo : 10 000 appels pondérés/jour, 600/min.
#: Pondération = nb_points × (jours/14) × (nb_variables/10).
QUOTA_JOUR = 10_000
QUOTA_MINUTE = 600


class Abort(Exception):
    """Arrêt net et volontaire — jamais rattrapé pour réessayer."""


# ══════════════════════════════════════════════════════════════════
#  HTTP
# ══════════════════════════════════════════════════════════════════

def _get_json(url: str, timeout: int = TIMEOUT_S):
    """GET + JSON, avec LE garde-fou Open-Meteo.

    ⚠️ Open-Meteo signale « Too many concurrent requests » avec un
    HTTP 200 et un corps `{"error": true}` — piège mesuré le 30/07
    (cf. lib/analogLab.ts). `r.status == 200` ne voit rien. Le traiter
    comme un succès écrirait des lignes vides dans une archive
    irremplaçable.
    """
    req = urllib.request.Request(url, headers={"User-Agent": "balise-watch/model-verif"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        payload = json.loads(r.read().decode("utf-8"))
    if isinstance(payload, dict) and payload.get("error"):
        raise RuntimeError(payload.get("reason", "erreur API non détaillée"))
    return payload


def _get_json_retry(url: str, label: str):
    for attempt in range(MAX_RETRIES):
        try:
            return _get_json(url)
        except (urllib.error.URLError, RuntimeError, json.JSONDecodeError,
                TimeoutError, OSError) as exc:
            if attempt == MAX_RETRIES - 1:
                print(f"  ⚠️  {label} abandonné : {exc}", file=sys.stderr)
                return None
            time.sleep(2 ** attempt)
    return None


# ══════════════════════════════════════════════════════════════════
#  RÉFÉRENTIEL DE STATIONS
# ══════════════════════════════════════════════════════════════════

def load_stations(path: pathlib.Path, max_age_days: int = 7) -> list[dict]:
    """Liste des points de vérification, rafraîchie depuis Pioupiou.

    ⚠️ Le fichier est mis à jour, jamais remplacé à l'aveugle : une
    balise qui disparaît du live (batterie à plat, maintenance) ne doit
    pas sortir du référentiel — sinon son historique deviendrait
    orphelin et son zone_id serait à recalculer à son retour. On ajoute,
    on marque `seen_at`, on ne retire jamais.
    """
    known: dict[str, dict] = {}
    if path.exists():
        for st in json.loads(path.read_text(encoding="utf-8")):
            known[f"{st['source']}:{st['id']}"] = st
        age_d = (time.time() - path.stat().st_mtime) / 86400
        if age_d < max_age_days:
            return list(known.values())

    print(f"▶ rafraîchissement du référentiel depuis {PIOUPIOU_LIVE}")
    payload = _get_json_retry(PIOUPIOU_LIVE, "catalogue Pioupiou")
    if payload is None:
        if known:
            print("  ⓘ catalogue injoignable — on garde le référentiel existant")
            return list(known.values())
        raise Abort("catalogue Pioupiou injoignable et aucun référentiel local")

    la_min, lo_min, la_max, lo_max = BBOX
    added = 0
    for d in payload.get("data", []):
        loc = d.get("location") or {}
        lat, lon = loc.get("latitude"), loc.get("longitude")
        if lat is None or lon is None:
            continue
        if not (la_min <= lat <= la_max and lo_min <= lon <= lo_max):
            continue
        key = f"pioupiou:{d['id']}"
        if key not in known:
            added += 1
        known[key] = {
            "id": str(d["id"]), "source": "pioupiou",
            "lat": round(float(lat), 4), "lon": round(float(lon), 4),
            "name": (d.get("meta") or {}).get("name") or "",
            "seen_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(known.values(), key=lambda s: s["id"]),
                               ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  {len(known)} points au référentiel ({added} nouveaux)")
    return list(known.values())


# ══════════════════════════════════════════════════════════════════
#  PRÉVISIONS
# ══════════════════════════════════════════════════════════════════

def _hourly_vars() -> list[str]:
    return ["wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
            f"wind_speed_{REGIME_LEVEL}", f"wind_direction_{REGIME_LEVEL}"]


def quota_projete(n_points: int, forecast_days: int) -> float:
    """Chiffre le run AVANT de le lancer, et refuse de démarrer s'il
    déborde.

    ⚠️ CE N'EST PAS UNE JOLIE TRACE. Le quota Open-Meteo a déjà cassé
    ce projet une fois (BUGS.md, 19/07) : sans cache, la veille se
    prenait des 429 **silencieusement**. La ligne journalisée à chaque
    run est ce qui rend une dérive visible avant la panne.
    """
    n_vars = len(_hourly_vars()) * len(MODELS)
    par_point = (forecast_days / 14) * (n_vars / 10)
    total = n_points * par_point
    print("┌─ QUOTA OPEN-METEO PROJETÉ ───────────────────────────────────")
    print(f"│ points                 : {n_points}")
    print(f"│ modèles × variables    : {len(MODELS)} × {len(_hourly_vars())} = {n_vars}")
    print(f"│ pondération / point    : {forecast_days}/14 × {n_vars}/10 = {par_point:.2f}")
    print(f"│ TOTAL du run           : {total:.0f} appels pondérés "
          f"({total / QUOTA_JOUR * 100:.1f} % du plafond journalier)")
    print(f"│ cadence                : 1 requête / {BATCH_PAUSE_S}s → "
          f"{60 / BATCH_PAUSE_S:.0f}/min (plafond {QUOTA_MINUTE}/min)")
    print("└──────────────────────────────────────────────────────────────")
    if total > QUOTA_JOUR * 0.5:
        raise Abort(f"{total:.0f} appels pondérés > 50 % du plafond journalier — "
                    f"comprendre AVANT de forcer (nb de points ? de modèles ?)")
    if 60 / BATCH_PAUSE_S > QUOTA_MINUTE:
        raise Abort("cadence au-dessus du plafond par minute")
    return total


def fetch_forecast(lat: float, lon: float, forecast_days: int):
    params = {
        "latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}",
        "hourly": ",".join(_hourly_vars()),
        "models": ",".join(MODELS),
        "forecast_days": str(forecast_days),
        "wind_speed_unit": "kmh", "timeformat": "unixtime",
    }
    return _get_json_retry(f"{FORECAST_API}?{urllib.parse.urlencode(params)}",
                           f"prévision {lat:.3f},{lon:.3f}")


def forecast_rows(station: dict, payload: dict, fetched_at: str):
    """Une ligne NDJSON par (station, modèle) réellement servi.

    ⚠️ LA SÉRIE DE TEMPS N'EST PAS RECOPIÉE, on écrit `t0` + `step_s`.
    Open-Meteo rend une grille horaire régulière, partagée par les huit
    modèles d'une même réponse : recopier les 72 horodatages sur chaque
    ligne triplait le fichier pour une information déductible. Mesuré
    avant/après sur 20 points réels — c'est le poste dominant, parce
    qu'un horodatage unix pèse autant qu'une vitesse mais qu'il y en a
    huit fois plus.

    Le format reste auto-descriptif : la longueur de `speed` donne le
    nombre d'échéances, `t0 + i × step_s` donne l'heure valide de
    chacune. Une archive qu'on relira dans trois ans ne doit dépendre
    d'aucune convention implicite.
    """
    hourly = payload.get("hourly") or {}
    times = hourly.get("time") or []
    if len(times) < 2:
        return
    step_s = int(times[1]) - int(times[0])

    # ⚠️ GARDE-FOU SUR LE SUFFIXE DE MODÈLE — mesuré le 08/08.
    # Open-Meteo suffixe les variables par `_<model>` SEULEMENT si
    # plusieurs modèles SERVENT le point. Ce n'est pas « plusieurs
    # demandés » :
    #   · 8 demandés, 2 servent  → `wind_speed_10m_icon_d2`, etc. ;
    #   · 2 demandés, 1 SEUL sert → `wind_speed_10m` tout court, et rien
    #     dans la réponse ne dit lequel a répondu.
    # Dans ce second cas, une boucle qui cherche `wind_speed_10m_<model>`
    # ne trouve rien : le point produirait ZÉRO ligne, en silence, avec
    # une réponse HTTP 200 parfaitement formée. C'est la panne qui a déjà
    # coûté un balayage complet à ce projet (ERA5, 06/08), et sur une
    # archive non rejouable elle serait définitive.
    #
    # `MODELS` contient des modèles mondiaux (GFS, ECMWF, ARPEGE), donc
    # au moins deux servent partout et le cas ne devrait pas arriver.
    # « Ne devrait pas » n'est pas « ne peut pas » : si ça arrive, on
    # ABANDONNE LE POINT BRUYAMMENT plutôt que d'attribuer la série au
    # hasard. Une archive préfère un trou signalé à une ligne fausse.
    if any(k == "wind_speed_10m" for k in hourly) and len(MODELS) > 1:
        print(f"  ⚠️  {station['source']}:{station['id']} : réponse sans suffixe de "
              f"modèle — un seul modèle sert ce point et l'API ne dit pas lequel. "
              f"Point abandonné (aucune ligne écrite).", file=sys.stderr)
        return

    for model in MODELS:
        speed = hourly.get(f"wind_speed_10m_{model}")
        # ⚠️ On teste le CONTENU, pas la présence de la clé. Open-Meteo
        # rend la clé même hors domaine, remplie de nulls — c'est le
        # piège ERA5 du 06/08, qui avait fait tourner un balayage
        # complet pour zéro résultat sans la moindre erreur.
        if not speed or all(v is None for v in speed):
            continue
        row = {
            "station_id": station["id"], "source": station["source"],
            "lat": station["lat"], "lon": station["lon"],
            "model": model, "fetched_at": fetched_at,
            "t0": int(times[0]), "step_s": step_s,
            "speed": speed,
            "dir": hourly.get(f"wind_direction_10m_{model}"),
            "gust": hourly.get(f"wind_gusts_10m_{model}"),
        }
        if model == REGIME_REF_MODEL:
            # Le vent d'altitude ne sert qu'à étiqueter le régime, et
            # un seul modèle le porte : le stocker pour les huit
            # multiplierait le fichier par deux pour rien.
            row["aloft_level"] = REGIME_LEVEL
            row["aloft_speed"] = hourly.get(f"wind_speed_{REGIME_LEVEL}_{model}")
            row["aloft_dir"] = hourly.get(f"wind_direction_{REGIME_LEVEL}_{model}")
        yield row


# ══════════════════════════════════════════════════════════════════
#  OBSERVATIONS
# ══════════════════════════════════════════════════════════════════

def fetch_archive(station: dict, day: str):
    """Une journée de relevés Pioupiou.

    Format rendu par l'API :
      [time, lat, lon, wind_min, wind_avg, wind_max, wind_heading, pressure]
    ~14 points/heure. On garde la moyenne (`wind_avg`), la rafale
    (`wind_max`) et le cap.

    ⚠️ La fenêtre déborde de 40 min de chaque côté : `pair_series`
    agrège les relevés dans ±20 min autour de chaque heure modèle, donc
    l'heure 00:00 a besoin de relevés de la veille 23:40. Sans ce
    débordement, les heures de bord auraient une demi-fenêtre et une
    moyenne systématiquement décalée.
    """
    start = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc) - timedelta(minutes=40)
    stop = start + timedelta(days=1, minutes=80)
    q = urllib.parse.urlencode({
        "start": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "stop": stop.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "format": "json",
    })
    url = f"{PIOUPIOU_ARCHIVE.format(id=station['id'])}?{q}"
    payload = _get_json_retry(url, f"archive {station['source']}:{station['id']}")
    if payload is None:
        return None
    data = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(data, list) or not data:
        return None
    t, speed, direction, gust = [], [], [], []
    for rec in data:
        if not isinstance(rec, list) or len(rec) < 7:
            continue
        try:
            ts = int(datetime.strptime(rec[0].replace("Z", "+0000"),
                                       "%Y-%m-%dT%H:%M:%S.%f%z").timestamp())
        except ValueError:
            try:
                ts = int(datetime.strptime(rec[0].replace("Z", "+0000"),
                                           "%Y-%m-%dT%H:%M:%S%z").timestamp())
            except ValueError:
                continue
        t.append(ts)
        speed.append(rec[4])
        gust.append(rec[5])
        direction.append(rec[6])
    if not t or all(v is None for v in speed):
        return None
    return {"station_id": station["id"], "source": station["source"],
            "lat": station["lat"], "lon": station["lon"],
            "t": t, "speed": speed, "gust": gust, "dir": direction}


# ══════════════════════════════════════════════════════════════════
#  ÉCRITURE
# ══════════════════════════════════════════════════════════════════

def write_ndjson_gz(path: pathlib.Path, rows_iter) -> int:
    """Écriture AU FIL DE L'EAU.

    Si le script est tué à mi-parcours, on garde ce qui a été collecté.
    Tout garder en mémoire pour n'écrire qu'à la fin, c'est risquer de
    tout perdre sur une coupure — et une nuit de collecte perdue ne se
    rattrape pas.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for row in rows_iter:
            fh.write(json.dumps(row, separators=(",", ":")) + "\n")
            n += 1
    return n


def upload_r2(path: pathlib.Path, key: str) -> bool:
    """Dépose sur R2 via `tools/storage.py` s'il est disponible.

    ⚠️ L'absence de R2 n'est PAS une erreur : le fichier local existe
    déjà à ce stade. Faire échouer le run parce que l'envoi distant a
    échoué reviendrait à préférer aucune archive à une archive locale —
    l'inverse de ce qu'on veut pour une donnée non rejouable.
    """
    tools = pathlib.Path(__file__).resolve().parent.parent / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    try:
        from storage import Storage, CACHE_IMMUABLE     # type: ignore
    except Exception as exc:                            # noqa: BLE001
        print(f"  ⓘ storage.py indisponible ({exc}) — archive locale seulement")
        return False
    try:
        st = Storage("model-verif", bucket_env="MODEL_VERIF_BUCKET",
                     defaut="model-verif", plafond=10)
        # Clé HORODATÉE et immuable : un objet par jour, jamais réécrit.
        # Cache long légitime — et pas de purge à prévoir, contrairement
        # aux isobares : ~176 Mo/an, l'archive est faite pour rester.
        st.put(key, path.read_bytes(), cache_control=CACHE_IMMUABLE,
               content_type="application/x-ndjson", content_encoding="gzip")
        st.bilan()
        return True
    except Exception as exc:                            # noqa: BLE001
        print(f"  ⚠️  envoi R2 échoué (archive locale conservée) : {exc}",
              file=sys.stderr)
        return False


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="/var/lib/bw-model-verif",
                    help="racine locale de l'archive")
    ap.add_argument("--stations", default=None,
                    help="référentiel JSON (défaut : <out>/stations.json)")
    ap.add_argument("--forecast-days", type=int, default=3)
    ap.add_argument("--obs-day", default=None,
                    help="journée d'observations à collecter (défaut : hier)")
    ap.add_argument("--skip-forecast", action="store_true")
    ap.add_argument("--skip-obs", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="0 = tout")
    ap.add_argument("--dry-run", action="store_true",
                    help="chiffre le run et sort, sans une seule requête météo")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    stations_path = pathlib.Path(args.stations) if args.stations else out / "stations.json"

    try:
        stations = load_stations(stations_path)
    except Abort as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    if args.limit:
        stations = stations[: args.limit]

    now = datetime.now(timezone.utc)
    fetched_at = now.isoformat()
    today = now.strftime("%Y-%m-%d")
    obs_day = args.obs_day or (now - timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        quota_projete(len(stations), args.forecast_days)
    except Abort as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if args.dry_run:
        print("  (dry-run : aucune requête météo, aucun fichier)")
        return 0

    rc = 0

    # ── 1. PRÉVISIONS ────────────────────────────────────────────
    # En premier, et c'est délibéré : c'est la partie non rattrapable.
    # Les observations Pioupiou, elles, restent lisibles des mois plus
    # tard dans l'archive publique.
    if not args.skip_forecast:
        key = f"fcst/{now:%Y/%m}/fcst_{today}.ndjson.gz"
        path = out / key
        print(f"▶ prévisions : {len(stations)} points × {len(MODELS)} modèles → {path}")
        failed = 0

        def _fcst_rows():
            nonlocal failed
            for i, st in enumerate(stations, 1):
                payload = fetch_forecast(st["lat"], st["lon"], args.forecast_days)
                if payload is None:
                    failed += 1
                else:
                    yield from forecast_rows(st, payload, fetched_at)
                if i % 50 == 0:
                    print(f"  … {i}/{len(stations)} ({failed} échecs)")
                time.sleep(BATCH_PAUSE_S)

        n = write_ndjson_gz(path, _fcst_rows())
        print(f"✅ {n} lignes, {failed} points en échec, "
              f"{path.stat().st_size / 1024:.0f} Ko")
        upload_r2(path, key)
        # ⚠️ Sortie en erreur si plus d'un point sur cinq a échoué : une
        # nuit à moitié collectée doit réveiller quelqu'un, pas passer
        # pour un succès dans les logs. Elle n'est pas rattrapable.
        if stations and failed > len(stations) * 0.2:
            print("❌ trop d'échecs — archive de prévisions incomplète "
                  "et non rattrapable", file=sys.stderr)
            rc = 1

    # ── 2. OBSERVATIONS ──────────────────────────────────────────
    if not args.skip_obs:
        d = datetime.strptime(obs_day, "%Y-%m-%d")
        key = f"obs/{d:%Y/%m}/obs_{obs_day}.ndjson.gz"
        path = out / key
        print(f"▶ observations du {obs_day} : {len(stations)} points → {path}")
        muettes = 0

        def _obs_rows():
            nonlocal muettes
            for i, st in enumerate(stations, 1):
                row = fetch_archive(st, obs_day)
                if row is None:
                    muettes += 1
                else:
                    yield row
                if i % 50 == 0:
                    print(f"  … {i}/{len(stations)} ({muettes} muettes)")
                time.sleep(BATCH_PAUSE_S)

        n = write_ndjson_gz(path, _obs_rows())
        print(f"✅ {n} lignes, {muettes} balises muettes, "
              f"{path.stat().st_size / 1024:.0f} Ko")
        upload_r2(path, key)
        # Seuil plus tolérant que pour les prévisions : une balise
        # éteinte est un fait normal du réseau, pas une panne de
        # collecte. Et l'archive Pioupiou reste relisible plus tard.
        if stations and muettes > len(stations) * 0.6:
            print("⚠️ plus de 60 % de balises muettes — vérifier l'API Pioupiou",
                  file=sys.stderr)

    return rc


if __name__ == "__main__":
    sys.exit(main())
