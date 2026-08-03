#!/usr/bin/env python3
"""
poller_infoclimat.py — le poller Infoclimat, sur le VPS, qui écrit dans
R2 (03/08/2026).

┌─ POURQUOI CE FICHIER EXISTE, ET PAS DANS index.js ──────────────────┐
│ La clé Infoclimat est liée à UNE adresse IP : 51.91.102.146, celle  │
│ du VPS. Les IP sortantes de Render sont MULTIPLES. Tant que le poll │
│ partait de Render, il recevait `Wrong ip address` — en HTTP 200,    │
│ donc sans erreur visible — et les calques s'affichaient vides.      │
│                                                                     │
│ Le VPS poll et écrit un JSON dans R2 ; Render le lit. Retenu plutôt │
│ qu'une API exposée par le VPS : aucun port entrant, aucun           │
│ certificat, aucune disponibilité à garantir sur une machine à 4 €.  │
└─────────────────────────────────────────────────────────────────────┘

┌─ LE PRINCIPE QUI COMMANDE TOUT CE FICHIER ──────────────────────────┐
│ Infoclimat est une association loi 1901 à but non lucratif, tenue   │
│ par des bénévoles, dont la page open data demande explicitement     │
│ d'« éviter les abus sur notre plateforme maintenue bénévolement ».  │
│ Les stations sont hébergées par des PARTICULIERS qui ont accepté de │
│ partager leurs mesures.                                             │
│                                                                     │
│ Réduire la charge n'est pas une optimisation technique ici, c'est   │
│ LA CONDITION D'USAGE. Chaque constante de ce fichier qu'on remonte  │
│ se paie chez eux.                                                   │
└─────────────────────────────────────────────────────────────────────┘

━━━ CE QUI A ÉTÉ MESURÉ, ET QU'IL NE FAUT PAS REDÉCOUVRIR ━━━━━━━━━━━

⚠️ LA FENÊTRE D'UNE HEURE N'EXISTE PAS. `start`/`end` sont des DATES.
   Tout composant horaire renvoie `status:"OK"`, `errors:[]`, `data:[]`
   et AUCUNE clé `hourly` — un échec silencieux de plus. Mesuré le
   03/08 par `traces/sonde_fenetre_infoclimat.py`, 7 appels.
   Le minimum indivisible est la JOURNÉE. NE PAS RETENTER.

⚠️ `Wrong ip address` ARRIVE EN HTTP 200, en texte brut. Un contrôle de
   code de statut ne le voit pas. On lit le corps avant de parser.

⚠️ IPv4 FORCÉE. Le VPS sort en IPv6 par défaut : le 03/08, le ping
   Healthchecks est arrivé depuis `2001:41d0:404:200::60e8`.
   `precedence ::ffff:0:0/96 100` a été posé dans `/etc/gai.conf` mais
   c'est un filet, pas une garantie (curl fait du Happy Eyeballs et
   court-circuite l'ordre de la glibc). On force `AF_INET` ICI.

⚠️ GZIP EXPLICITE. Le `fetch` de Node envoie `Accept-Encoding` tout
   seul ; `urllib` n'envoie RIEN. Sans l'en-tête posé dans `get()`, un
   lot de 100 pèse 2,90 Mo au lieu de 82 Ko — 35× pire que Render
   aujourd'hui. C'est la seule ligne de ce fichier dont l'oubli ne
   casse rien de visible tout en multipliant la charge par 35.

⚠️ `vent_rafales` est null partout — limitation connue d'Infoclimat,
   signalée par d'autres réutilisateurs. Pas un bug d'ici.

⚠️ LA LICENCE VARIE D'UNE STATION À L'AUTRE, dans un rayon de 20 km :
   `CC BY`, `NON-COMMERCIAL ONLY: CC BY NC`, `Etalab`. Elle voyage donc
   PAR STATION dans le JSON écrit ici — toute UI doit porter la licence
   DE LA STATION AFFICHÉE, jamais une mention globale.

━━━ CADENCE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Arbitrée par Yann le 03/08 sur simulation (`tools/cadence_infoclimat.py`)
— par DENSITÉ DE DÉCOS, pas par département : une frontière
administrative n'a pas de sens météo, et un déco de bordure lit
forcément des stations de l'autre côté.

    décos dans 25 km   stations   cadence
    20 et +                  57   10 min      ← là où on vole vraiment
    5 à 19                  394   30 min
    1 à 4                   431   60 min
    0                       323   180 min     ← fronts et foehn, synoptique

Charge chez Infoclimat : 1,82 M de lignes lues/jour contre 7,06 M
aujourd'hui, soit 3,9× moins. (Et non 190× : ce chiffre du prompt de
reprise multipliait la cadence par un gain de 60× sur la fenêtre, qui
n'existe pas.)

⚠️ PLANCHER À 10 MIN, jamais moins. Les stations MESURENT toutes les
   10 à 14,7 min (mesuré station par station le 02/08). Poller plus
   vite ne rend pas une valeur plus fraîche, il rend la MÊME valeur une
   deuxième fois.

⚠️ L'intervalle effectif est `max(palier, cadence native observée)`.
   La cadence native s'apprend GRATUITEMENT : l'écart entre deux
   horodatages successifs est dans les réponses qu'on reçoit déjà.
   Poller Saint-Pancrasse (14,7 min) toutes les 10 min gaspillerait un
   appel sur trois pour la même valeur.

⚠️ RÉTROGRADATION DES STATIONS SANS ANÉMOMÈTRE. Une station qui n'a
   rendu aucun vent depuis SANS_VENT_JOURS passe au palier le plus
   lent. Ce n'est pas théorique : 26 des 100 stations sondées le 03/08
   n'avaient AUCUN relevé du jour, et 3 sur 8 aucun vent. Même logique
   que la rétention différenciée déjà en place pour les stations MF
   pression-seule.

━━━ ESCALADE SUR ÉVÉNEMENT (§3) — MÉCANISME POSÉ, DÉCLENCHEUR ABSENT ━

Les 323 stations sans déco proche servent à voir venir fronts et foehn.
Au repos elles pollent à 180 min ; en événement elles doivent accélérer.

⚠️ LE DÉCLENCHEUR VIT SUR RENDER, PAS ICI. Les signaux flightwatch
   (`sig_pressure_drop`, `sig_vigilance`, `sig_wind_surge`) et les axes
   de foehn sont calculés par `index.js`. Le VPS ne les voit pas, et on
   ne lui ouvre aucun port entrant. Le canal retenu est donc le MÊME
   que dans l'autre sens : Render écrit `infoclimat/escalade.json` dans
   R2, ce poller le lit. Tant que Render ne l'écrit pas, le mécanisme
   ci-dessous reste inerte — c'est voulu, et c'est sans risque.

Les TROIS garde-fous, non négociables (sans eux, c'est le mécanisme
d'escalade lui-même qui coûterait cher) :
  1. PLAFOND DUR : jamais sous PLANCHER_MIN, quoi que dise le fichier.
  2. DÉSESCALADE GARANTIE PAR EXPIRATION, jamais par « l'événement est
     fini ». Un état bloqué en alerte pollerait au maximum
     indéfiniment. L'escalade porte une date de péremption ; passée
     celle-ci elle tombe, même si personne ne l'a levée.
  3. PLAFOND QUOTIDIEN d'appels, abort net et journalisé — même
     philosophie que `MAX_WEIGHTED_CALLS` du worker de packs.

━━━ ÉCRITURES R2 ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Deux objets, et c'est délibéré (arbitré le 03/08) :
  · `infoclimat/latest.json`  — dernière valeur des ~1200 stations.
    Petit, réécrit à chaque run où quelque chose a bougé. C'est ce que
    Render lit pour la carte.
  · `infoclimat/history.json` — HISTORY_HEURES glissantes. Gros,
    réécrit toutes les HISTORY_INTERVAL_MIN. Render ne le lit QUE
    quand un pilote ouvre une fiche station.

Un seul objet aurait été plus simple, mais Render relirait 24 h × 1200
stations à chaque cycle pour n'afficher qu'une valeur : on déplacerait
le gaspillage d'Infoclimat vers R2. Même principe que tout le chantier.

⚠️ L'HISTORIQUE NE VA PAS DANS SUPABASE, contrairement aux stations MF.
   MF n'a AUCUN historique natif (snapshot instantané), d'où
   `mf_station_history` qui s'accumule point par point. Infoclimat
   renvoie la journée entière à chaque appel — 122 relevés par station
   et par jour. L'historique, on l'a déjà : c'est exactement ce qu'on
   jetait. Rien à stocker ailleurs, et le Storage Supabase est sous
   restriction au 29/08.

⚠️ Discipline R2 reprise du worker de packs : plafond dur d'écritures
   par run, JAMAIS de boucle de réessai, aucun `ListObjects`, aucun
   `HeadObject`. Cf. le garde-fou n°1 dans l'en-tête de `storage.py`.

━━━ USAGE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  python3 poller_infoclimat.py --dry-run            # ni appel ni écriture
  python3 poller_infoclimat.py --dry-run --reseau   # appelle, n'écrit pas
  python3 poller_infoclimat.py --go                 # pour de vrai
  python3 poller_infoclimat.py --go --limit 100     # borne le parc

Lancé par `balise-infoclimat.timer`, jamais à la main en production.
Ne PAS le greffer sur `entretien.sh` : sa cadence (quotidienne) n'a
rien à voir avec celle-ci.
"""

import argparse
import gzip
import io
import json
import math
import os
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, '..', '..', 'tools'))

UA = "BaliseWatch/1.0 (+argonautes.sim@gmail.com; https://balise-watch.app)"
OPENDATA = "https://www.infoclimat.fr/opendata/"
STATIONS_GEOJSON = ("https://www.data.gouv.fr/api/1/datasets/r/"
                    "8a9e6a12-03f8-4056-861f-70b84136313e")
DECOS_JSON = os.path.join(ICI, '..', '..', '..', 'web', 'public', 'data',
                          'decos.json')

# ── Cadence ───────────────────────────────────────────────────────────
RAYON_KM = 25.0
PALIERS = [(20, 10), (5, 30), (1, 60), (0, 180)]   # (décos mini, minutes)
PLANCHER_MIN = 10          # cadence native mesurée : 10 à 14,7 min
PALIER_LENT_MIN = 180
SANS_VENT_JOURS = 3        # au-delà, rétrogradation au palier lent
LOT = 100                  # URL de 2 409 caractères — loin de toute limite

# ── Plafonds ──────────────────────────────────────────────────────────
# Cible mesurée du schéma retenu : 328 requêtes/jour. Le plafond est posé
# à ~1,5× pour laisser vivre l'escalade sans jamais laisser une dérive
# s'installer. Dépassement = arrêt net, jamais de réessai.
MAX_APPELS_JOUR = 500
MAX_APPELS_RUN = 20        # 1205 / 100 = 13 lots au grand maximum
HISTORY_INTERVAL_MIN = 30
# 30 h et pas 24 : le client demande `max(7, heure_locale + 2)` heures
# pour le graphe de comparaison (ChartModal), soit jusqu'à 25 h en fin de
# soirée. À 24 h, ce graphe serait tronqué une partie de la journée.
#
# ⚠️ Ça ne coûte AUCUN appel de plus. La rétention est un élagage de
# l'ÉTAT, pas une fenêtre demandée à l'API : les points déjà vus sont
# conservés d'un run à l'autre. L'API n'en rend que ~24 h au minimum
# (veille→jour au petit matin), le reste s'accumule tout seul.
HISTORY_HEURES = 30
TOLERANCE_S = 90           # jitter du timer : ne pas rater un créneau

ETAT_DIR = os.environ.get("BW_INFOCLIMAT_ETAT",
                          os.path.expanduser("~/.balise-watch-infoclimat"))
ETAT_FICHIER = os.path.join(ETAT_DIR, "etat.json")
GEOJSON_CACHE = os.path.join(ETAT_DIR, "stations.geojson")


class Abort(Exception):
    """Arrêt net et volontaire. Jamais rattrapée pour réessayer — le run
    s'arrête, le précédent reste servi, on reprend au run suivant."""


# ══════════════════════════════════════════════════════════════════════
#  RÉSEAU
# ══════════════════════════════════════════════════════════════════════
def forcer_ipv4():
    """⚠️ Sans ça l'appel part en IPv6 et la clé — liée à une IPv4 — est
    refusée par un `Wrong ip address` qui arrive en HTTP 200."""
    _orig = socket.getaddrinfo

    def v4(host, port, family=0, type=0, proto=0, flags=0):
        return _orig(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = v4


def get(url, timeout=120):
    """Renvoie (code, texte, octets_sur_le_fil).

    ⚠️ `Accept-Encoding: gzip` est OBLIGATOIRE ici : `urllib` ne l'envoie
    pas de lui-même, et son absence multiplie par 35 ce qu'on télécharge
    chez eux sans rien casser de visible."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            brut = r.read()
            fil = len(brut)
            if "gzip" in (r.headers.get("Content-Encoding") or "").lower():
                brut = gzip.GzipFile(fileobj=io.BytesIO(brut)).read()
            return r.status, brut.decode("utf-8", "replace"), fil
    except urllib.error.HTTPError as e:
        b = e.read()
        return e.code, b.decode("utf-8", "replace"), len(b)
    except Exception as e:                       # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}", 0


def haversine_km(a_lat, a_lon, b_lat, b_lon):
    r = 6371.0
    dlat, dlon = math.radians(b_lat - a_lat), math.radians(b_lon - a_lon)
    h = (math.sin(dlat / 2) ** 2 + math.cos(math.radians(a_lat))
         * math.cos(math.radians(b_lat)) * math.sin(dlon / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


# ══════════════════════════════════════════════════════════════════════
#  PARC ET CADENCES
# ══════════════════════════════════════════════════════════════════════
def charger_stations(reseau=True):
    """Liste publique des stations StatIC. Aucune clé requise pour
    celle-ci, contrairement au reste de l'API.

    Le GeoJSON est mis en cache sur disque et rafraîchi une fois par
    jour : le télécharger à chaque run (toutes les 5 min) serait
    exactement le genre de charge inutile que ce fichier combat."""
    frais = False
    if os.path.exists(GEOJSON_CACHE):
        age_h = (time.time() - os.path.getmtime(GEOJSON_CACHE)) / 3600
        frais = age_h < 24
    if not frais and reseau:
        code, txt, _ = get(STATIONS_GEOJSON, timeout=120)
        if code == 200 and txt.lstrip().startswith("{"):
            os.makedirs(ETAT_DIR, exist_ok=True)
            with open(GEOJSON_CACHE, "w", encoding="utf-8") as f:
                f.write(txt)
    if not os.path.exists(GEOJSON_CACHE):
        raise Abort("aucune liste de stations (ni cache, ni réseau) — "
                    "rien à poller, on s'arrête proprement")
    with open(GEOJSON_CACHE, encoding="utf-8") as f:
        geo = json.load(f)

    out = []
    for feat in (geo.get("features") or []):
        g = (feat.get("geometry") or {}).get("coordinates") or []
        p = feat.get("properties") or {}
        if len(g) < 2 or not p.get("id"):
            continue
        # Ne garder que le réseau Infoclimat (StatIC) : les quelques
        # entrées 'METEO-FRANCE' de ce même fichier sont déjà couvertes
        # par /meteofrance-stations. Jamais doubler un point physique.
        lic = p.get("license") or {}
        if lic.get("source") != "infoclimat.fr":
            continue
        out.append({
            "id": str(p["id"]),
            "nom": p.get("name") or str(p["id"]),
            "lat": float(g[1]), "lon": float(g[0]),
            "alt": p.get("elevation"),
            # ⚠️ La licence voyage PAR STATION — elle varie dans un rayon
            # de 20 km. Sur les 854 stations servies le 03/08 : 442 en
            # `NON-COMMERCIAL ONLY: CC BY NC`, 412 en `CC BY`. Une
            # mention globale serait fausse pour une station sur deux.
            # Les trois champs sont transportés parce que le client les
            # attendait déjà tous les trois (licenseCode/Label/Url).
            "licence_code": lic.get("code"),
            "licence": lic.get("license"),
            "licence_url": lic.get("url"),
        })
    return out


def cadences_par_densite(stations):
    """Palier de chaque station selon le nombre de décos dans 25 km.

    ⚠️ RECALCULÉ À CHAQUE DÉMARRAGE, jamais lu dans un fichier figé :
    `tools/cadence_infoclimat.json` est un artefact de REVUE. Une
    station nouvelle apparaîtrait sinon avec une cadence héritée de
    rien, et personne ne le verrait."""
    with open(DECOS_JSON, encoding="utf-8") as f:
        decos = [(d[0], d[1]) for d in json.load(f)
                 if isinstance(d, list) and len(d) >= 2]
    pas = 0.25
    bins = {}
    for lat, lon in decos:
        bins.setdefault((int(lat / pas), int(lon / pas)), []).append((lat, lon))
    portee = int(RAYON_KM / (111.0 * pas)) + 1

    out = {}
    for s in stations:
        bi, bj = int(s["lat"] / pas), int(s["lon"] / pas)
        n = 0
        for di in range(-portee, portee + 1):
            for dj in range(-portee, portee + 1):
                for dlat, dlon in bins.get((bi + di, bj + dj), ()):
                    if haversine_km(s["lat"], s["lon"], dlat, dlon) <= RAYON_KM:
                        n += 1
        minutes = PALIERS[-1][1]
        for seuil, mn in PALIERS:
            if n >= seuil:
                minutes = mn
                break
        out[s["id"]] = {"decos": n, "palier_min": minutes}
    return out


def intervalle_effectif(sid, base, etat, escalade, maintenant):
    """L'intervalle réellement appliqué, et pourquoi.

    Quatre règles, dans cet ordre — chacune ne peut que RALENTIR, sauf
    l'escalade, qui est la seule à accélérer et qui est bornée par le
    plancher dur."""
    st = etat.get("stations", {}).get(sid, {})
    minutes = base
    motif = "palier"

    # 1. La cadence NATIVE de la station. Apprise gratuitement : poller
    #    plus vite qu'elle ne mesure rend la même valeur deux fois.
    native = st.get("cadence_native_min")
    if native and native > minutes:
        minutes, motif = native, "cadence native"

    # 2. Rétrogradation des stations sans anémomètre. Une station qui n'a
    #    rendu aucun vent depuis SANS_VENT_JOURS n'a rien à faire au
    #    palier rapide — 26 % du parc était dans ce cas le 03/08.
    vu = st.get("dernier_vent_ts")
    if vu and (maintenant - vu) > SANS_VENT_JOURS * 86400:
        if PALIER_LENT_MIN > minutes:
            minutes, motif = PALIER_LENT_MIN, "sans vent"
    elif vu is None and st.get("premier_poll_ts") and \
            (maintenant - st["premier_poll_ts"]) > SANS_VENT_JOURS * 86400:
        if PALIER_LENT_MIN > minutes:
            minutes, motif = PALIER_LENT_MIN, "jamais de vent"

    # 3. Escalade sur événement — la SEULE règle qui accélère.
    if sid in escalade:
        minutes, motif = min(minutes, escalade[sid]), "escalade"

    # 4. PLAFOND DUR. Quoi qu'il arrive, jamais sous le plancher : les
    #    stations ne mesurent pas plus vite que ça.
    if minutes < PLANCHER_MIN:
        minutes, motif = PLANCHER_MIN, motif + " (borné au plancher)"
    return minutes, motif


def lire_escalade(storage, etat, maintenant, log):
    """Stations en cadence accélérée, lues depuis `infoclimat/escalade.json`
    que RENDER écrit (les signaux flightwatch vivent là-bas, pas ici).

    ⚠️ GARDE-FOU N°2 — DÉSESCALADE GARANTIE PAR EXPIRATION. Chaque entrée
    porte un `expire_ts`. Passé celui-ci, elle tombe, que l'événement
    soit fini ou non, que Render ait été mis à jour ou non. On ne
    désescalade JAMAIS sur « l'événement est terminé » : un état bloqué
    en alerte pollerait au maximum indéfiniment, et c'est précisément le
    mécanisme d'escalade qui coûterait alors le plus cher.

    Absence de fichier = aucune escalade. C'est l'état normal tant que
    Render ne l'écrit pas."""
    if storage is None:
        return {}
    doc = storage.get_json("infoclimat/escalade.json")
    if not isinstance(doc, dict):
        return {}
    out, expirees = {}, 0
    for sid, spec in (doc.get("stations") or {}).items():
        try:
            expire = float(spec.get("expire_ts", 0))
            minutes = int(spec.get("cadence_min", PLANCHER_MIN))
        except (TypeError, ValueError):
            continue
        if expire <= maintenant:
            expirees += 1
            continue
        out[sid] = max(minutes, PLANCHER_MIN)
    if out or expirees:
        log(f"escalade : {len(out)} station(s) accélérée(s), "
            f"{expirees} entrée(s) expirée(s) et ignorée(s)")
    return out


# ══════════════════════════════════════════════════════════════════════
#  APPEL À L'API
# ══════════════════════════════════════════════════════════════════════
def fetch_lot(cle, ids, jour_debut, jour_fin):
    """Un lot. Renvoie (hourly | None, octets, diagnostic).

    ⚠️ Trois échecs de cette API arrivent en HTTP 200 et se ressemblent
    tous à un succès. Ils sont traités ici, dans l'ordre où on les a
    découverts :
      · `Wrong ip address` — texte brut, clé liée à une autre IP ;
      · réponse non-JSON — même famille ;
      · `status:"OK"` SANS clé `hourly` — requête refusée en silence
        (typiquement un start/end portant une heure). Rendre `{}` ici
        serait indistinguable d'un « aucune station n'a de relevé »
        légitime, et le poller se tairait en écrivant du vide."""
    params = [("method", "get"), ("format", "json"),
              ("start", jour_debut), ("end", jour_fin), ("token", cle)]
    params += [("stations[]", i) for i in ids]
    url = f"{OPENDATA}?{urllib.parse.urlencode(params)}"
    code, txt, octets = get(url)

    if txt.strip() == "Wrong ip address":
        return None, octets, (f"Wrong ip address (HTTP {code}) — la clé "
                              f"n'est pas valide depuis cette IP")
    try:
        data = json.loads(txt)
    except ValueError:
        return None, octets, f"réponse non-JSON (HTTP {code}) — {txt[:160]}"
    if data.get("status") != "OK":
        err = json.dumps(data.get("errors", data), ensure_ascii=False)
        return None, octets, f"status={data.get('status')!r} — {err[:160]}"
    hourly = data.get("hourly")
    if not isinstance(hourly, dict):
        return None, octets, ("status OK mais pas de clé `hourly` — requête "
                              f"refusée en silence ; clés : "
                              f"{sorted(data.keys())}")
    return hourly, octets, "OK"


def parse_point(raw):
    """Un relevé. `t` non fini → l'appelant l'ignore.

    ⚠️ `dh_utc` peut manquer sur un relevé malformé (constaté le
    19/07) : sans ce garde-fou, un seul point pourri faisait tomber le
    rafraîchissement de TOUTES les stations."""
    def num(v):
        try:
            return float(v) if v not in (None, "") else None
        except (TypeError, ValueError):
            return None

    dh = raw.get("dh_utc") if isinstance(raw, dict) else None
    if not isinstance(dh, str):
        return None
    try:
        t = datetime.strptime(dh, "%Y-%m-%d %H:%M:%S").replace(
            tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None
    def arrondi(v, d):
        # Arrondi À L'ENTRÉE, pas à l'affichage : un `180.0` sérialisé
        # coûte deux caractères de plus qu'un `180`, et il y en a
        # ~735 000 dans l'historique complet. La précision retirée ici
        # n'existait pas dans la mesure : aucun anémomètre amateur ne
        # rend le dixième de degré.
        return None if v is None else (round(v, d) if d else int(round(v)))

    return {
        "t": int(t),
        "moy": arrondi(num(raw.get("vent_moyen")), 1),
        "raf": arrondi(num(raw.get("vent_rafales")), 1),  # null partout
        "dir": arrondi(num(raw.get("vent_direction")), 0),
        "pres": arrondi(num(raw.get("pression")), 1),
        "temp": arrondi(num(raw.get("temperature")), 1),
    }


def cadence_native_min(points):
    """Écart MÉDIAN entre relevés successifs, en minutes.

    Gratuit : c'est déjà dans la réponse. La médiane et non la moyenne,
    parce qu'un trou d'une heure dans la journée (station qui redémarre)
    fausserait la moyenne et ferait croire la station plus lente qu'elle
    n'est — donc la ferait poller moins souvent qu'il ne faut."""
    ts = sorted(p["t"] for p in points)
    if len(ts) < 4:
        return None
    ecarts = sorted((b - a) / 60.0 for a, b in zip(ts, ts[1:]) if b > a)
    if not ecarts:
        return None
    med = ecarts[len(ecarts) // 2]
    # Bornes de sûreté : une valeur aberrante ne doit pas pouvoir
    # accélérer le poller (borne basse) ni l'endormir (borne haute).
    return max(PLANCHER_MIN, min(round(med), PALIER_LENT_MIN))


# ══════════════════════════════════════════════════════════════════════
#  ÉTAT
# ══════════════════════════════════════════════════════════════════════
def charger_etat():
    """L'état survit entre les runs : le service est `oneshot` et meurt
    à chaque cycle. Sans lui, aucune cadence apprise, aucune
    rétrogradation, aucun plafond quotidien."""
    if not os.path.exists(ETAT_FICHIER):
        return {"stations": {}, "appels_jour": {}, "history_ecrit_ts": 0}
    try:
        with open(ETAT_FICHIER, encoding="utf-8") as f:
            e = json.load(f)
    except (OSError, ValueError):
        # Un état corrompu ne doit pas empêcher de tourner : on repart
        # d'une page blanche, les cadences se réapprennent en un jour.
        return {"stations": {}, "appels_jour": {}, "history_ecrit_ts": 0}
    e.setdefault("stations", {})
    e.setdefault("appels_jour", {})
    e.setdefault("history_ecrit_ts", 0)
    return e


def ecrire_etat(etat):
    """Écriture ATOMIQUE. Un run tué au mauvais moment (chien de garde,
    reboot) laisserait sinon un JSON tronqué, et le run suivant repartirait
    sans cadences apprises — en pollant tout au palier de base."""
    os.makedirs(ETAT_DIR, exist_ok=True)
    tmp = ETAT_FICHIER + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(etat, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, ETAT_FICHIER)


def appels_du_jour(etat, jour):
    """⚠️ GARDE-FOU N°3 — PLAFOND QUOTIDIEN. Le compteur est purgé des
    jours passés à chaque lecture : sans ça le fichier d'état grossirait
    sans fin, ce qui est exactement le défaut relevé sur `essais` en
    mode entretien le 02/08."""
    etat["appels_jour"] = {j: n for j, n in etat["appels_jour"].items()
                           if j >= jour}
    return etat["appels_jour"].get(jour, 0)


# ══════════════════════════════════════════════════════════════════════
#  SORTIE R2
# ══════════════════════════════════════════════════════════════════════
def corps_latest(stations_meta, etat, maintenant):
    """`infoclimat/latest.json` — ce que Render lit pour la carte.

    On n'écrit QUE les stations dont le dernier relevé est frais. Une
    valeur de six heures affichée comme courante ferait mentir le calque,
    et un calque météo qui ment est pire qu'un calque absent."""
    limite = maintenant - 90 * 60
    obs = {}
    for sid, st in etat["stations"].items():
        d = st.get("dernier")
        if not d or d.get("t", 0) < limite:
            continue
        obs[sid] = d
    doc = {
        "genere_le": datetime.fromtimestamp(maintenant, timezone.utc)
                             .isoformat(timespec="seconds"),
        "source": "Infoclimat — réseau StatIC",
        # ⚠️ Les métadonnées portent la LICENCE DE CHAQUE STATION. Elle
        # varie d'une station à l'autre dans le même rayon : toute UI
        # doit afficher celle de la station montrée, pas une globale.
        "stations": {s["id"]: {k: s[k] for k in
                               ("nom", "lat", "lon", "alt", "licence_code",
                                "licence", "licence_url")}
                     for s in stations_meta if s["id"] in obs},
        "obs": obs,
    }
    return json.dumps(doc, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def corps_history(etat, maintenant):
    """`infoclimat/history.json` — HISTORY_HEURES glissantes.

    Objet SÉPARÉ de `latest.json` : Render le relit sur SA propre
    cadence et le garde en RAM (même philosophie que `mfObsCache`), puis
    sert une station à la fois. Le faire voyager à chaque cycle de carte
    reviendrait à déplacer le gaspillage d'Infoclimat vers R2.

    ⚠️ FORMAT COLONNAIRE, et c'est la raison d'être de cette fonction.
    En liste d'objets, chaque point réécrit ses six noms de champ :
    122 points × 6 clés × 1205 stations, c'est ~4,4 Mo de clés répétées
    sur 8 Mo de fichier. Mesuré : 8 017 Ko / 831 Ko compressés en liste
    d'objets. En colonnes, les clés sont écrites UNE FOIS par station.
    Une série entièrement nulle (`raf` l'est partout, limitation connue
    d'Infoclimat) n'est pas écrite du tout.

    Les tableaux sont ALIGNÉS sur `t` — un trou est un `null` à sa
    position, jamais un point manquant : décaler les séries les unes par
    rapport aux autres afficherait un vent à la mauvaise heure."""
    limite = maintenant - HISTORY_HEURES * 3600
    hist = {}
    for sid, st in etat["stations"].items():
        pts = [p for p in st.get("historique", []) if p.get("t", 0) >= limite]
        if not pts:
            continue
        serie = {"t": [p["t"] for p in pts]}
        for champ in ("moy", "raf", "dir", "pres", "temp"):
            col = [p.get(champ) for p in pts]
            if any(v is not None for v in col):
                serie[champ] = col
        hist[sid] = serie
    doc = {
        "genere_le": datetime.fromtimestamp(maintenant, timezone.utc)
                             .isoformat(timespec="seconds"),
        "heures": HISTORY_HEURES,
        "source": "Infoclimat — réseau StatIC",
        "format": ("colonnaire : chaque station porte des tableaux "
                   "ALIGNÉS sur `t`. Une série absente = entièrement "
                   "nulle. Un trou = null à sa position."),
        "historique": hist,
    }
    return json.dumps(doc, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


# ══════════════════════════════════════════════════════════════════════
#  RUN
# ══════════════════════════════════════════════════════════════════════
def run(args, log):
    maintenant = int(datetime.now(timezone.utc).timestamp())
    jour = datetime.now(timezone.utc).date().isoformat()
    veille = (datetime.now(timezone.utc).date()
              - timedelta(days=1)).isoformat()

    cle = os.environ.get("INFOCLIMAT_API_KEY")
    if not cle and args.reseau:
        raise Abort("INFOCLIMAT_API_KEY absente — le poller n'a rien à "
                    "faire sans elle (dégradation silencieuse volontaire, "
                    "comme le module serveur)")

    etat = charger_etat()
    stations = charger_stations(reseau=args.reseau)
    if args.limit:
        stations = stations[:args.limit]
    cadences = cadences_par_densite(stations)
    log(f"parc : {len(stations)} stations · "
        + " · ".join(f"{mn} min: "
                     f"{sum(1 for c in cadences.values() if c['palier_min'] == mn)}"
                     for _s, mn in PALIERS))

    # ── Storage ───────────────────────────────────────────────────────
    storage = None
    if args.go:
        # ⚠️ R2 IMPOSÉ, et pas seulement par défaut. `storage.py` retombe
        # sur Supabase quand STORAGE_BACKEND est vide — or le Storage
        # Supabase est sous restriction Fair Use jusqu'au 29/08, et cette
        # chaîne-ci n'a jamais eu vocation à y écrire. On force plutôt
        # que de dépendre d'une variable d'environnement qu'un oubli
        # laisserait vide, ce qui écrirait silencieusement au mauvais
        # endroit.
        if (os.environ.get("STORAGE_BACKEND") or "r2").lower() != "r2":
            raise Abort(f"STORAGE_BACKEND="
                        f"{os.environ.get('STORAGE_BACKEND')!r} — ce poller "
                        f"écrit dans R2 et nulle part ailleurs")
        os.environ["STORAGE_BACKEND"] = "r2"
        from storage import Storage, CACHE_REECRIT      # noqa: F401
        # Le bucket est `R2_BUCKET` (= balise-watch-packs), réutilisé
        # sciemment : c'est celui qui a été validé le 03/08, et les clés
        # sont préfixées `infoclimat/`. Un bucket de plus n'apporterait
        # qu'un secret de plus à tenir.
        # Plafond volontairement bas : ce poller n'écrit QUE deux objets.
        # Si ce compteur devait monter, c'est qu'une boucle s'est
        # installée — l'abort net est alors le bon comportement.
        storage = Storage("infoclimat", "INFOCLIMAT_BUCKET", "infoclimat",
                          plafond=4)

    escalade = lire_escalade(storage, etat, maintenant, log)

    # ── Qui est dû ? ──────────────────────────────────────────────────
    dues, motifs = [], {}
    for s in stations:
        sid = s["id"]
        base = cadences[sid]["palier_min"]
        minutes, motif = intervalle_effectif(sid, base, etat, escalade,
                                             maintenant)
        st = etat["stations"].get(sid, {})
        dernier_poll = st.get("dernier_poll_ts", 0)
        if maintenant - dernier_poll >= minutes * 60 - TOLERANCE_S:
            dues.append(sid)
            motifs[sid] = motif
    if not dues:
        log("rien à poller à ce cycle — sortie sans un appel")
        ecrire_etat(etat)
        return 0

    # ── GARDE-FOU N°3 : plafond quotidien ─────────────────────────────
    deja = appels_du_jour(etat, jour)
    lots = [dues[i:i + LOT] for i in range(0, len(dues), LOT)]
    if len(lots) > MAX_APPELS_RUN:
        # Ne jamais tronquer en silence : on borne ET on le dit.
        log(f"⚠️ {len(lots)} lots demandés > MAX_APPELS_RUN "
            f"({MAX_APPELS_RUN}) — borné. Les stations non traitées "
            f"seront dues au run suivant.")
        lots = lots[:MAX_APPELS_RUN]
    if deja + len(lots) > MAX_APPELS_JOUR:
        raise Abort(
            f"plafond quotidien atteint : {deja} appels déjà faits "
            f"aujourd'hui, {len(lots)} de plus dépasseraient "
            f"{MAX_APPELS_JOUR}. Arrêt net, aucun réessai — le dernier "
            f"latest.json reste servi. Comprendre la dérive AVANT de "
            f"relever la constante (escalade bloquée ? cadence apprise "
            f"à zéro ? timer qui se déclenche trop souvent ?)")

    log(f"{len(dues)} stations dues → {len(lots)} lot(s) · "
        f"{deja} appel(s) déjà faits aujourd'hui / {MAX_APPELS_JOUR}")
    if not args.reseau:
        log("--dry-run sans --reseau : on s'arrête avant le premier appel")
        return 0

    # ── Les appels ────────────────────────────────────────────────────
    # ⚠️ La JOURNÉE, et pas une fenêtre plus courte : elle n'existe pas
    #    (mesuré). On demande veille→jour pour que l'historique reste
    #    complet à cheval sur minuit, où la journée du jour est vide.
    octets_total, neufs, echecs = 0, 0, 0
    for lot in lots:
        hourly, octets, diag = fetch_lot(cle, lot, veille, jour)
        etat["appels_jour"][jour] = etat["appels_jour"].get(jour, 0) + 1
        octets_total += octets
        if hourly is None:
            echecs += 1
            log(f"❌ lot de {len(lot)} : {diag}")
            # Pas de réessai, jamais. Le lot repassera au run suivant.
            continue
        for sid in lot:
            st = etat["stations"].setdefault(sid, {})
            st["dernier_poll_ts"] = maintenant
            st.setdefault("premier_poll_ts", maintenant)
            bruts = hourly.get(sid)
            if not isinstance(bruts, list) or not bruts:
                continue
            pts = [p for p in (parse_point(b) for b in bruts) if p]
            if not pts:
                continue
            pts.sort(key=lambda p: p["t"])
            # Cadence native : apprise sur la journée qu'on vient de
            # recevoir, gratuitement.
            nat = cadence_native_min(pts)
            if nat:
                st["cadence_native_min"] = nat
            recent = pts[-1]
            # ⚠️ Ne jamais RECULER : un lot en retard ne doit pas
            #    remplacer un relevé plus récent déjà connu.
            ancien = st.get("dernier") or {}
            if recent["t"] > ancien.get("t", 0):
                st["dernier"] = recent
                neufs += 1
            if recent.get("moy") is not None:
                st["dernier_vent_ts"] = recent["t"]
            # Historique : fusionné puis borné. On garde ce qu'on a déjà
            # vu même si l'API ne le renvoie plus.
            limite = maintenant - HISTORY_HEURES * 3600
            connus = {p["t"]: p for p in st.get("historique", [])}
            connus.update({p["t"]: p for p in pts})
            st["historique"] = [connus[t] for t in sorted(connus)
                                if t >= limite]

    log(f"{octets_total / 1024:.0f} Ko sur le fil · {neufs} relevés neufs · "
        f"{echecs} lot(s) en échec")

    # ── Écritures R2 ──────────────────────────────────────────────────
    if not args.go:
        log("--dry-run : rien n'est écrit dans R2")
        ecrire_etat(etat)
        return 0
    if echecs == len(lots):
        # Tous les lots en échec : ne PAS écrire un latest.json appauvri
        # par-dessus un bon. Le précédent reste servi.
        log("tous les lots en échec — aucune écriture, le précédent "
            "latest.json reste servi")
        ecrire_etat(etat)
        return 1

    from storage import CACHE_REECRIT

    def gz(brut):
        """Compressé À L'ÉCRITURE, avec `Content-Encoding: gzip`.

        R2 ne compresse pas à la volée. Sans ça, `history.json` partirait
        et se relirait en clair à chaque ouverture de fiche station — le
        même gaspillage qu'on vient de retirer côté Infoclimat, déplacé
        d'un cran. `mtime=0` pour que deux corps identiques donnent deux
        octets identiques (sinon l'horodatage gzip les rendrait
        différents et masquerait toute comparaison)."""
        tampon = io.BytesIO()
        with gzip.GzipFile(fileobj=tampon, mode="wb", mtime=0) as f:
            f.write(brut)
        return tampon.getvalue()

    body = corps_latest(stations, etat, maintenant)
    comp = gz(body)
    storage.put("infoclimat/latest.json", comp, cache_control=CACHE_REECRIT,
                content_encoding="gzip")
    log(f"latest.json écrit — {len(body) / 1024:.0f} Ko "
        f"→ {len(comp) / 1024:.0f} Ko compressé")

    if maintenant - etat.get("history_ecrit_ts", 0) >= HISTORY_INTERVAL_MIN * 60:
        body_h = corps_history(etat, maintenant)
        comp_h = gz(body_h)
        storage.put("infoclimat/history.json", comp_h,
                    cache_control=CACHE_REECRIT, content_encoding="gzip")
        etat["history_ecrit_ts"] = maintenant
        log(f"history.json écrit — {len(body_h) / 1024:.0f} Ko "
            f"→ {len(comp_h) / 1024:.0f} Ko compressé")

    log(f"R2 : {storage.ecritures} Class A · {storage.lectures} Class B")
    ecrire_etat(etat)
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--go", action="store_true",
                    help="écrire pour de vrai dans R2")
    ap.add_argument("--dry-run", action="store_true",
                    help="ne rien écrire (défaut si --go est absent)")
    ap.add_argument("--reseau", action="store_true",
                    help="autoriser les appels réseau en dry-run")
    ap.add_argument("--limit", type=int, default=0,
                    help="borner le parc, pour les essais")
    args = ap.parse_args()
    if args.go:
        args.reseau = True

    def log(msg):
        print(f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%M:%SZ} {msg}",
              flush=True)

    forcer_ipv4()
    try:
        return run(args, log)
    except Abort as e:
        log(f"ABORT — {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
