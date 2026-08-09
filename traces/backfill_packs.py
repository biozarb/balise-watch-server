#!/usr/bin/env python3
"""
backfill_packs.py — worker de backfill/entretien des packs météo par déco
(01/08/2026). Produit `packs/v1/<lat>_<lon>.json.gz` et les pousse sur
Cloudflare R2.

Conception : ../../../Analyse de vol/SCHEMA_REALISATION_ANALOGUES_26-07.md
§4.2/§4.3, et SOURCES_ARCHIVE_METEO_01-08.md (routes d'archive, mesures
du 01/08). Calcul des features : `day_features.py` v2, dont ce fichier
reprend la logique SANS la modifier (mêmes noms, mêmes échelles, même
fenêtre horaire, même moyenne vectorielle).

┌─ CE QUE CE WORKER EST, ET CE QU'IL N'EST PAS ───────────────────────┐
│ C'est un TRAVAIL DE FOND REPRENABLE, pas un script qui doit aller   │
│ au bout. La latence d'Open-Meteo varie d'un facteur 50 (mesuré le   │
│ 30/07, cf. DEBUG.md) : un run peut durer des heures ou des jours.   │
│ Il s'interrompt proprement, se relance, et ne refait jamais un déco │
│ déjà écrit. Toute la reprise tient dans UN fichier de checkpoint    │
│ LOCAL — jamais dans R2 (lister ou interroger R2 coûterait des       │
│ opérations facturables à chaque redémarrage).                       │
│                                                                     │
│ Ce n'est PAS un moteur de matching. Aucune décision du §3/§5 bis    │
│ n'est touchée ici. C'est de l'infrastructure.                       │
└─────────────────────────────────────────────────────────────────────┘

⚠️ GARDE-FOU N°1 — R2 N'A PAS DE PLAFOND : DÉPASSER = PAYER.
   Cloudflare ne propose aucun hard cap ; tout dépassement du palier
   gratuit est facturé automatiquement. D'où, dans ce fichier :
     · un plafond DUR d'écritures par run (MAX_CLASS_A_*), qui provoque
       un abort net et jamais une boucle de réessai — une boucle de
       retry est LE scénario qui crame 1 M d'opérations ;
     · un objet par déco, ÉCRASÉ EN PLACE, jamais de versionnage par
       date (c'est le versionnage qui ferait grossir le stockage sans
       borne) ;
     · un refus de démarrer si le dimensionnement projeté dépasse les
       seuils (voir `verifier_dimensionnement`) ;
     · aucun ListObjects, aucun HeadObject : le checkpoint local sait
       déjà ce qui a été écrit. Les deux sont des opérations facturées.
   Palier gratuit re-vérifié le 01/08/2026 sur la page pricing R2 :
   10 Go-mois · 1 M Class A/mois · 10 M Class B/mois · egress gratuit.
   DeleteObject et AbortMultipartUpload sont gratuites.

⚠️ UN PACK NE RÉTRÉCIT JAMAIS — garde-fou ajouté le 02/08/2026 après un
   bug destructif trouvé à la relecture, AVANT le premier run d'entretien
   (donc jamais déclenché, les 210 packs n'ont jamais été touchés).
   Le mode `entretien` reconstruisait le pack à partir des SEULES journées
   fetchées dans le run — une plage de 92 jours — et l'écrasait en place.
   Les 940 journées d'archive partaient, remplacées par 92, avec
   `complet: true` et `plages_perdues: 0` par-dessus : le pack aurait
   menti par omission, ce qu'il est précisément conçu pour ne jamais
   faire. Le checkpoint aurait enregistré `n: 92, complet: true`, donc
   `a_refaire()` aurait fait SAUTER la réparation par un `--mode
   backfill` — il aurait fallu supprimer le checkpoint et refaire deux
   jours de quota. Versionnage désactivé sur le bucket : aucun retour
   arrière.
   Trois choses en sortent, et elles sont dans le code, pas ici :
     · `R2.get()` — l'entretien LIT le pack existant (Class B, 10 M/mois)
       avant de le réécrire. C'est la seule façon pour ce worker de
       connaître le corpus : il ne garde rien en local hors checkpoint.
     · fenêtre par déco = lendemain de la dernière journée du pack → J-1.
       18 appels pondérés/jour pour 210 décos (0,18 % du quota), et un
       run raté hier se rattrape tout seul aujourd'hui.
     · `len(journees) < n_avant` → Abort. C'est la règle GÉNÉRALE, celle
       qui aurait arrêté ce bug sans qu'on ait à le comprendre.
   Famille : « un état partiel qui se croit final », déjà rencontrée
   trois fois le 01/08. C'est le motif à chercher en premier ici.

⚠️ JAMAIS DEPUIS L'IP DE RENDER. Ce worker tourne sur le poste de Yann
   ou un poste dédié. Le quota Open-Meteo se compte par IP, et l'IP de
   Render porte déjà la veille et le foehn en production.

⚠️ PAS DE PARALLÉLISME sur l'API publique. Open-Meteo répond
   {"error": true, "reason": "Too many concurrent requests"} en HTTP 200
   — pas en erreur réseau — dès que deux requêtes partent en parallèle
   (mesuré le 30/07). C'est la concurrence qui casse, pas le volume.
   Ne pas « optimiser » ce script avec un ThreadPool.

Usage :
  # 1. Toujours commencer par là : rien n'est écrit, tout est chiffré.
  python3 backfill_packs.py --mode backfill --dry-run

  # 2. Trois décos de test, écriture réelle, pour valider taille/format
  python3 backfill_packs.py --mode backfill --limit 3 --go

  # 3. Le vrai run (relançable autant de fois qu'on veut)
  python3 backfill_packs.py --mode backfill --go

  # 4. Entretien quotidien. Sous 500 décos, `rotation()` vaut 1 : tout le
  #    catalogue chaque jour (chiffré, cf. la docstring de rotation()).
  #    Lit chaque pack, y ajoute les journées manquantes jusqu'à J-1, et
  #    ne réécrit QUE ceux qui ont gagné au moins une journée.
  python3 backfill_packs.py --mode entretien --go

Variables d'environnement pour R2 (aucune valeur en dur dans ce fichier) :
  R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET
"""

import argparse
import contextlib
import gzip
import io
import json
import math
import os
import signal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════
#  SOURCE MÉTÉO — une seule constante à changer selon la route
# ══════════════════════════════════════════════════════════════════════
# Les trois routes chiffrées dans SOURCES_ARCHIVE_METEO_01-08.md §4 se
# distinguent UNIQUEMENT par ces deux URLs (et une clé, le cas échéant).
# Route 1 — API publique gratuite (défaut) :
HF_URL = os.environ.get(
    "OM_HF_URL", "https://historical-forecast-api.open-meteo.com/v1/forecast")
ERA5_URL = os.environ.get(
    "OM_ERA5_URL", "https://archive-api.open-meteo.com/v1/archive")
# Route 2 — endpoint client payant : OM_HF_URL=https://customer-historical-forecast-api.open-meteo.com/v1/forecast
#           + OM_API_KEY=...   (plan Professional : le plan Standard
#           N'OUVRE PAS ces endpoints, cf. §0 du doc du 01/08)
# Route 3 — API locale sur le dump AWS : OM_HF_URL=http://127.0.0.1:8080/v1/forecast
OM_API_KEY = os.environ.get("OM_API_KEY") or None

UA = "BaliseWatch-packs/1.0 (+argonautes.sim@gmail.com)"

# ══════════════════════════════════════════════════════════════════════
#  FENÊTRE TEMPORELLE
# ══════════════════════════════════════════════════════════════════════
# ⚠️ DÉBUT D'ARCHIVE — TRANCHÉ PAR YANN LE 01/08/2026 : 2024-01-02.
# Ce n'est ni le 15/12/2023 (borne supposée au 24/07) ni le 31/08/2023
# (mesuré le 30/07). Les DEUX étaient antérieures au début réel d'AROME.
# Mesuré le 01/08 à Aussois sur `wind_speed_700hPa` :
#     meteofrance_arome_france  au 01/10/2023 → 0/72 non-null, VIDE
#     meteofrance_arome_france  au 02/01/2024 → 72/72 non-null
#     meteofrance_arpege_europe au 01/10/2023 → 72/72, valeur 23,0
#     meteofrance_seamless      au 01/10/2023 → 72/72, valeur 23,0  ← ARPEGE
#     meteofrance_seamless      au 01/06/2025 → 48/48, valeur 14,0  ← AROME
# Autrement dit `seamless` sert de l'ARPEGE Europe à 11 km sous le même
# nom de variable, sans null et sans avertissement, jusqu'au 02/01/2024.
# Sur une maille de 2,5 km, 11 km n'est pas une approximation : c'est un
# autre relief. Décision : corpus homogène, AROME pur.
# ⚠️ Ne JAMAIS re-dater cette archive en sondant `meteofrance_seamless` :
# il répond toujours quelque chose. Sonder `meteofrance_arome_france`.
ARCHIVE_START = "2024-01-02"

# ⚠️ NE PAS ÉLARGIR « pour faire moins de requêtes ». Le coût serveur est
# très super-linéaire en longueur de plage : mesuré le 30/07 au soir,
# 366 j × 13 var = 331 s contre ~10 s pour 92 j — 33× le temps pour 4× la
# durée. Descendre à 30 j n'aide pas non plus (14-17 s). Ne pas rouvrir
# sans remesurer.
CHUNK_DAYS = 92

# Fenêtre 12h-18h locales ≈ 10h-16h UTC (H1, doc étape 2). Identique à
# day_features.py — toute correction ici doit être reportée là-bas, dans
# match_analogs.fetch_today_features et dans analogLab.ts (4 copies, cf.
# la dette consignée dans les en-têtes).
WINDOW_UTC_HOURS = list(range(10, 17))

SURFACE_VARS = [
    "wind_speed_10m", "temperature_2m", "dew_point_2m", "cape",
    "cloud_cover_mid", "cloud_cover_high", "sunshine_duration", "precipitation",
]

# ══════════════════════════════════════════════════════════════════════
#  REQUÊTES MULTI-POINTS  (mesuré le 01/08/2026)
# ══════════════════════════════════════════════════════════════════════
# L'API accepte des listes de coordonnées et renvoie un TABLEAU JSON, une
# entrée par point. Tentant. **Et contre-productif ici — mesuré.**
#
# Première mesure (01/08, sandbox, plages de 3 j × 2 variables) :
#     1 point ~1-4 s · 20 points 1,7 s · 100 points 2,8 s
# Conclusion tirée à ce moment-là : grouper supprime des allers-retours,
# donc groupons par 50. **FAUX**, parce que la sonde utilisait une charge
# minuscule. Sur la VRAIE charge (92 jours × 12 variables), remesuré le
# même jour sur le poste de Yann :
#     1 point  → 2,2 à 7,0 s par plage   → 1 déco complet en 1,1 min
#     3 points → 31 à 91 s par plage     → 3 décos en 11,5 min
# Soit 3,5× PLUS LENT que les mêmes 3 décos traités un par un (3,3 min),
# et surtout : les seules plages perdues du run (2 sur 11, timeout à 45 s)
# sont arrivées en mode groupé. Le coût serveur est super-linéaire en
# points comme il l'est en jours — c'est la même pathologie que
# CHUNK_DAYS, découverte deux fois.
#
# ⚠️ DONC : UN POINT PAR REQUÊTE. Ne pas remonter cette valeur « pour
# aller plus vite », c'est exactement ce qui ralentit. Extrapolation à
# 210 décos : ~4 h en séquentiel, ~13 h par lots de 3.
# Le groupage ne faisait de toute façon économiser AUCUN appel pondéré
# (le poids est nb_points × jours/14 × variables/10) : il ne visait que
# le temps d'horloge, et il le dégrade.
BATCH_POINTS = int(os.environ.get("OM_BATCH_POINTS", "1"))

PAUSE_S = 0.4
# ⚠️ MESURÉ LE 01/08/2026, ET C'EST UN PIÈGE : le paramètre `timeout` de
# `urlopen` borne l'attente ENTRE DEUX PAQUETS, pas la durée totale. Une
# réponse qui arrive au goutte-à-goutte ne le déclenche JAMAIS. Constaté
# en direct sur une plage de 92 j × 12 var restée pendante **plus de
# 7 minutes** avec TIMEOUT_S = 180, sans erreur ni abandon — pendant que
# les six plages précédentes du même déco coûtaient 2,2 à 9,0 s. C'est la
# latence erratique ×50 du 30/07, vue depuis le worker.
# D'où le garde-fou d'horloge ci-dessous : au-delà, on abandonne la plage
# et on continue. Une plage perdue est comptée et annoncée (elle sera
# reprise au prochain run), jamais avalée en silence.
# ⚠️ TROIS TOURS DU MÊME PIÈGE, LE 01/08 — À NE PAS REDÉCOUVRIR.
# 1. `timeout=` d'`urlopen` borne l'attente ENTRE DEUX PAQUETS, jamais la
#    durée totale. Plage restée pendante >7 min avec `timeout=180`.
# 2. Lire par blocs et surveiller l'horloge entre deux `read()` ne suffit
#    pas : un `read()` bloqué ne rend la main qu'au bout du timeout
#    socket. Dépassement maximal = DEADLINE_S + TIMEOUT_S.
# 3. Même en descendant le timeout socket à 45 s, une plage a tenu ~200 s
#    sans que RIEN ne morde — le serveur envoie manifestement de quoi
#    garder la socket « active » pendant qu'il calcule.
# Conclusion : aucun réglage de timeout urllib ne borne cette API. Seule
# une alarme au niveau du PROCESSUS y arrive (`signal.alarm`, qui
# interrompt l'appel système). D'où `_alarme` ci-dessous.
# ⚠️ Corollaire : ne JAMAIS mettre cette fonction dans un thread — SIGALRM
# n'est livré qu'au thread principal. C'est une raison de plus de ne pas
# « optimiser » ce worker avec un pool.
TIMEOUT_S = 45                   # inactivité socket (première ligne de défense)
DEADLINE_S = int(os.environ.get("OM_DEADLINE_S", "150"))   # alarme processus

# ══════════════════════════════════════════════════════════════════════
#  PLAFONDS DURS  —  ne pas relever sans refaire le calcul du §4.3
# ══════════════════════════════════════════════════════════════════════
# Atteindre un plafond = ABORT + log. Jamais de réessai en boucle.
MAX_CLASS_A_BACKFILL = 20_000     # écritures R2 par run de backfill
MAX_CLASS_A_ENTRETIEN = 4_000     # écritures R2 par run d'entretien
MAX_WEIGHTED_CALLS = int(os.environ.get("OM_MAX_WEIGHTED", "9000"))
# 9000 : marge sous le plafond gratuit de 10 000/jour. Sur route 2 ou 3,
# passer OM_MAX_WEIGHTED à une valeur haute (l'endpoint payant n'a pas de
# limite journalière, l'API locale n'a aucune limite).

# Seuils de refus de démarrage (marge ×2 sur tout, cf. garde-fou n°1)
SEUIL_STOCKAGE_GO = 5.0
SEUIL_ECRITURES_MOIS = 500_000
SEUIL_PACK_KO = 500              # un pack au-delà = on s'arrête et on comprend
# Nombre de passages avant d'accepter un pack auquel il manque des plages.
MAX_ESSAIS = 3

# ══════════════════════════════════════════════════════════════════════
#  PÉRIMÈTRE  —  décision Yann du 01/08/2026 : bêta sur 66 + 73
# ══════════════════════════════════════════════════════════════════════
# « Est-ce qu'on peut couvrir uniquement les Pyrénées-Orientales (66) et
# la Savoie (73) le temps de la bêta pour limiter les datas ? » Oui, et
# ça ne limite pas seulement les données : ça referme tout le débat sur
# la route d'archive (cf. SOURCES_ARCHIVE_METEO_01-08.md §4).
#
# Périmètre arrêté le 01/08 en deux temps : d'abord 66 + 73, puis
# **élargi à 38 (Isère) et 74 (Haute-Savoie)** — parce que les deux seuls
# sites où existe un corpus de vols (Saint-Hilaire en 38,
# Montmin/Forclaz en 74, 138 vols) en étaient exclus, ce qui interdisait
# de rejouer la validation du matching. Aussois (73) et Céret (66) sont
# dedans, mais Aussois n'a que 3 vols connus.
#
# Compté sur decos.json : 66 → 12 · 73 → 74 · 38 → 48 · 74 → 76, soit
# **210 décos sur 3313 (6,3 %)**. Le backfill complet passe de ~287 000
# appels pondérés (~29 jours de quota gratuit) à **~18 200, soit
# 1,8 jour** — deux journées de quota gratuit, sans abonnement d'aucune
# sorte.
#
# ⚠️ ÉTENDRE LE PÉRIMÈTRE = ajouter un code ici, rien d'autre. Le
# checkpoint est idempotent : les décos déjà faits ne sont pas refaits,
# seuls les nouveaux sont téléchargés. Les polygones de 04 et 05 sont
# déjà déposés dans `perimetre/` précisément pour ça.
# Ordres de grandeur mesurés le 01/08 (décos → jours de quota gratuit) :
# 66+73 = 86 → 0,7 j · **+38 et 74 = 210 → 1,8 j** · Alpes du Nord + PO
# = 262 → 2,3 j · arc alpin + Pyrénées = 347 → 3,0 j. Même dix
# départements de montagne tiennent en trois jours de quota gratuit.
# Le mur des 29 jours était un mur de CATALOGUE, pas un mur de météo.
PERIMETRE_DEPARTEMENTS = [
    d.strip() for d in os.environ.get("BW_DEPARTEMENTS", "66,73,38,74").split(",")
    if d.strip()
]

ROOT = Path(__file__).resolve().parent
PERIMETRE_DIR = ROOT / "perimetre"
DECOS_JSON = ROOT / "../../web/public/data/decos.json"
CHECKPOINT = ROOT / "traces_cache" / "packs_checkpoint.json"
PACKS_LOCAL = ROOT / "traces_cache" / "packs"
LOG_FILE = ROOT / "traces_cache" / "backfill_packs.log"

R2_PREFIX = "packs/v1/"
# Un pack est réécrit au plus une fois par semaine (rotation 1/7,
# décision Yann 01/08) : un cache d'une journée est franc, et
# stale-while-revalidate évite le trou de latence à l'expiration.
R2_CACHE_CONTROL = "public, max-age=86400, stale-while-revalidate=604800"


# ══════════════════════════════════════════════════════════════════════
#  COMPTEURS  —  tout ce qui coûte est compté et journalisé
# ══════════════════════════════════════════════════════════════════════
class Compteurs:
    def __init__(self):
        self.appels_http = 0
        self.appels_ponderes = 0.0
        self.class_a = 0            # écritures R2 (PutObject)
        self.class_b = 0            # lectures R2 (GetObject, entretien)
        self.octets_envoyes = 0
        self.decos_ok = 0
        self.decos_vides = 0
        self.plages_perdues = 0
        self.t0 = time.time()

    def ligne(self):
        dt = time.time() - self.t0
        return (f"[compteurs] {dt/60:.1f} min · HTTP {self.appels_http} · "
                f"pondéré {self.appels_ponderes:.0f} · R2 Class A {self.class_a} "
                f"Class B {self.class_b} · "
                f"envoyé {self.octets_envoyes/1e6:.1f} Mo · "
                f"décos ok {self.decos_ok} vides {self.decos_vides} · "
                f"plages perdues {self.plages_perdues}")


CPT = Compteurs()


def log(msg, echo=True):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ligne = f"{ts} {msg}"
    if echo:
        print(msg, flush=True)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as f:
            f.write(ligne + "\n")
    except OSError:
        pass


class Abort(Exception):
    """Plafond atteint ou invariant violé. On s'arrête NET : pas de
    réessai, pas de dégradation silencieuse. Le checkpoint est déjà
    sur disque, la reprise se fera au prochain lancement."""


# ══════════════════════════════════════════════════════════════════════
#  FEATURES  —  port fidèle de day_features.py v2
# ══════════════════════════════════════════════════════════════════════
def niveau_crete(alt_m):
    """Niveau de pression standard le plus proche de alt_deco + 400 m
    (règle H2, doc étape 2). Identique à `_pressure_level_for_alt` et à
    `crestLevelHpa` (analogLab.ts)."""
    target_m = alt_m + 400
    p = 1013.25 * (1 - 2.25577e-5 * target_m) ** 5.25588
    return min([900, 850, 800, 700, 600, 500], key=lambda lv: abs(lv - p))


def vent_vectoriel(speeds, dirs):
    """Moyenne VECTORIELLE u/v + rafale. Jamais une moyenne d'angles : le
    piège 359°→1° donnerait 180°, exactement à l'opposé."""
    pairs = [(s, d) for s, d in zip(speeds, dirs) if s is not None and d is not None]
    if not pairs:
        return None
    u = sum(-s * math.sin(math.radians(d)) for s, d in pairs) / len(pairs)
    v = sum(-s * math.cos(math.radians(d)) for s, d in pairs) / len(pairs)
    return {"dir": (math.degrees(math.atan2(-u, -v)) + 360) % 360,
            "force": math.hypot(u, v),
            "raf": max(s for s, _ in pairs)}


def _fenetre(times):
    return [i for i, t in enumerate(times) if int(t[11:13]) in WINDOW_UTC_HOURS]


def _par_jour(times, idx):
    out = {}
    for i in idx:
        out.setdefault(times[i][:10], []).append(i)
    return out


def _plages(start, end):
    a, z = date.fromisoformat(start), date.fromisoformat(end)
    while a <= z:
        b = min(a + timedelta(days=CHUNK_DAYS - 1), z)
        yield a.isoformat(), b.isoformat()
        a = b + timedelta(days=1)


def journees_depuis_hourly(hourly, level):
    """Transforme la réponse `hourly` d'UN point en lignes journalières.
    Même schéma de sortie que day_features.fetch_range (schema 2)."""
    times = hourly.get("time", [])
    idx = _fenetre(times)
    if not idx:
        return {}

    def col(name):
        return hourly.get(name, [None] * len(times))

    out = {}
    for day, day_idx in _par_jour(times, idx).items():
        crest = vent_vectoriel([col(f"wind_speed_{level}hPa")[i] for i in day_idx],
                               [col(f"wind_direction_{level}hPa")[i] for i in day_idx])
        if crest is None:
            # Pas de vent par niveau ce jour-là : la journée n'est pas
            # descriptible pour un matching de montagne. On la saute
            # plutôt que de l'écrire à moitié.
            continue
        free = vent_vectoriel([col("wind_speed_600hPa")[i] for i in day_idx],
                              [col("wind_direction_600hPa")[i] for i in day_idx])

        def vals(name):
            c = col(name)
            return [c[i] for i in day_idx if c[i] is not None]

        sol, capes = vals("wind_speed_10m"), vals("cape")
        mid, high = vals("cloud_cover_mid"), vals("cloud_cover_high")
        sun, precip = vals("sunshine_duration"), vals("precipitation")
        # Écart T−Td MAXIMAL de la fenêtre = la base la plus haute de la
        # journée (~125 m par °C). Pas la moyenne, qui mélangerait le
        # matin humide et l'après-midi sec.
        spread = None
        for i in day_idx:
            t, td = col("temperature_2m")[i], col("dew_point_2m")[i]
            if t is not None and td is not None:
                spread = (t - td) if spread is None else max(spread, t - td)

        out[day] = {
            "vent_crete_dir_deg": round(crest["dir"]),
            "vent_crete_force_kmh": round(crest["force"], 1),
            "vent_crete_raf_kmh": round(crest["raf"], 1),
            "cape_max_jkg": round(max(capes)) if capes else None,
            "nuages_mh_pct": (round((sum(mid) / len(mid) + sum(high) / len(high)) / 2)
                              if mid and high else None),
            "vent_600_dir_deg": round(free["dir"]) if free else None,
            "vent_600_force_kmh": round(free["force"], 1) if free else None,
            "vent_sol_kmh": round(sum(sol) / len(sol), 1) if sol else None,
            "spread_td_c": round(spread, 1) if spread is not None else None,
            "soleil_pct": round(100 * sum(sun) / (len(day_idx) * 3600)) if sun else None,
            "precip_mm": round(sum(precip), 1) if precip else None,
        }
    return out


FEATURES = ["vent_crete_dir_deg", "vent_crete_force_kmh", "vent_crete_raf_kmh",
            "cape_max_jkg", "nuages_mh_pct", "vent_600_dir_deg",
            "vent_600_force_kmh", "vent_sol_kmh", "spread_td_c",
            "soleil_pct", "precip_mm"]


# ══════════════════════════════════════════════════════════════════════
#  RÉSEAU
# ══════════════════════════════════════════════════════════════════════
@contextlib.contextmanager
def _alarme(secondes):
    """Borne DURE la durée d'un appel, au niveau du processus. C'est le
    seul mécanisme qui ait fonctionné (cf. les trois pièges ci-dessus) :
    SIGALRM interrompt l'appel système lui-même, là où tous les timeouts
    d'urllib se contentent d'espérer que la socket coopère.
    Repli silencieux (aucune borne) sur les plateformes sans SIGALRM —
    Windows. Le worker y resterait exposé au piège ; c'est assumé, il est
    prévu pour tourner sur le poste de Yann."""
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def _boum(_sig, _frm):
        raise TimeoutError(f"horloge dépassée ({secondes}s) — l'API n'a pas "
                           f"rendu la main")

    ancien = signal.signal(signal.SIGALRM, _boum)
    signal.alarm(secondes)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, ancien)


import os as _os                                          # noqa: E402
import sys as _sys                                        # noqa: E402

_TOOLS = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                       "..", "tools")
if _TOOLS not in _sys.path:
    _sys.path.insert(0, _TOOLS)
try:
    from quota_openmeteo import Budget as _Budget, poids_url as _poids_url
    BUDGET = _Budget("backfill_packs")
except Exception as _exc:                                 # noqa: BLE001
    print(f"  ⓘ budget Open-Meteo indisponible ({_exc}) — sans comptage partagé")
    BUDGET = None


def get_json(url, poids, essai_restant=1):
    """GET + rattrapage du piège de concurrence : l'erreur arrive dans le
    CORPS avec un HTTP 200, un test sur le code de statut ne la verrait
    pas. UN SEUL réessai, et seulement sur cette erreur-là."""
    if CPT.appels_ponderes + poids > MAX_WEIGHTED_CALLS:
        raise Abort(f"plafond d'appels pondérés atteint "
                    f"({CPT.appels_ponderes:.0f} + {poids:.0f} > {MAX_WEIGHTED_CALLS})")
    # ── budget Open-Meteo partagé (09/08/2026) ────────────────────
    # ⚠️ `CPT` NE VOIT QUE CE PROCESSUS-CI, ET C'EST LÀ SA LIMITE. Il
    # compte bien, il compte en poids, mais il compte SEUL : il ne sait
    # rien de la collecte de 05:15 ni des trois scripts lancés à la
    # main, alors que le plafond Open-Meteo est par ADRESSE IP et que
    # tout le VPS en partage une. Les deux comptes coexistent donc, et
    # ce n'est pas une redondance : `CPT` borne CE run (garde-fou de
    # l'appelant), le budget borne L'IP (garde-fou du voisinage).
    #
    # ⚠️ Le poids passé ici en argument est celui que l'appelant a
    # calculé ; celui du budget est relu sur l'URL — lots de points
    # compris. Si les deux divergent un jour, c'est l'URL qui dit vrai.
    if BUDGET is not None:
        BUDGET.demander(_poids_url(url))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    t0 = time.time()
    try:
        with _alarme(DEADLINE_S):
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                data = json.loads(r.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
        log(f"    réseau ({time.time()-t0:.0f}s) : {e} — plage abandonnée, "
            f"elle sera reprise au prochain run")
        return None
    finally:
        CPT.appels_http += 1
        CPT.appels_ponderes += poids
    err = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else data
    if isinstance(err, dict) and err.get("error"):
        raison = str(err.get("reason", ""))
        if essai_restant and "concurrent" in raison.lower():
            time.sleep(2.0)
            return get_json(url, poids, essai_restant - 1)
        log(f"    API : {raison}")
        return None
    return data


def poids_pondere(n_points, n_jours, n_vars):
    """Pondération officielle Open-Meteo : nb_points × (jours/14) × (var/10)."""
    return n_points * (n_jours / 14.0) * (n_vars / 10.0)


def fetch_lot(points, level, start, end):
    """Une plage pour un LOT de points partageant le même niveau de
    crête. Renvoie une liste (même ordre que `points`) de dicts
    {date: features}. Un point sans réponse renvoie {}."""
    hf_vars = ([f"wind_speed_{level}hPa", f"wind_direction_{level}hPa",
                "wind_speed_600hPa", "wind_direction_600hPa"] + SURFACE_VARS)
    n_jours = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    params = {
        "latitude": ",".join(f"{p['lat']:.4f}" for p in points),
        "longitude": ",".join(f"{p['lon']:.4f}" for p in points),
        "start_date": start, "end_date": end,
        "hourly": ",".join(hf_vars), "models": "meteofrance_arome_france",
        "timezone": "UTC",
    }
    if OM_API_KEY:
        params["apikey"] = OM_API_KEY
    data = get_json(f"{HF_URL}?{urllib.parse.urlencode(params)}",
                    poids_pondere(len(points), n_jours, len(hf_vars)))
    if data is None:
        CPT.plages_perdues += 1
        return [{} for _ in points]
    if isinstance(data, dict):          # réponse mono-point
        data = [data]
    if len(data) != len(points):
        # Un décalage silencieux apparierait les features au mauvais déco.
        # C'est le genre de bug qui ne se voit jamais à l'écran.
        raise Abort(f"réponse de {len(data)} entrées pour {len(points)} points "
                    f"— appariement impossible, on s'arrête")
    return [journees_depuis_hourly(e.get("hourly", {}), level) for e in data]


# ══════════════════════════════════════════════════════════════════════
#  PACK  —  format colonnaire (mesuré le 01/08)
# ══════════════════════════════════════════════════════════════════════
# Mesuré sur 1066 journées simulées, gzip -9 :
#     lignes JSON (schéma jsonl actuel) : 371 Ko brut → 38,1 Ko gzip
#     colonnaire                        :  54 Ko brut → 21,8 Ko gzip
#     colonnaire + entiers              :  41 Ko brut → 17,0 Ko gzip
# Le colonnaire écrit les clés une fois au lieu de 1066 fois. Les valeurs
# aléatoires du test compressent MOINS bien que des vraies séries météo
# (autocorrélées d'un jour à l'autre) : ces tailles sont des majorants.
def construire_pack(deco, level, journees, plages_perdues=0):
    dates = sorted(journees)
    return {
        # Un trou dans le corpus doit voyager AVEC le corpus. Un pack qui
        # ne dit pas qu'il lui manque trois mois est un pack qui ment au
        # client par omission — et le client, lui, comptera k sur ce qu'il
        # a reçu sans savoir ce qui manque.
        "plages_perdues": plages_perdues,
        "complet": plages_perdues == 0,
        "schema": 3,
        "format": "colonnaire",
        "lat": round(deco["lat"], 4), "lon": round(deco["lon"], 4),
        "nom": deco["nom"], "alt_deco_m": deco["alt"],
        "niveau_crete_hpa": level,
        "meteo_tier": "A",
        # Provenance explicite : tout ce pack vient d'AROME 2,5 km. Le
        # jour où on rouvrirait la fenêtre avant 2024-01-02, ce champ
        # devrait devenir une colonne, pas rester un scalaire (cf.
        # SOURCES_ARCHIVE_METEO_01-08.md §1).
        "modele": "meteofrance_arome_france",
        "resolution_km": 2.5,
        "archive_start": ARCHIVE_START,
        "fenetre_utc": [WINDOW_UTC_HOURS[0], WINDOW_UTC_HOURS[-1]],
        "genere_le": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "n": len(dates),
        "dates": dates,
        "cols": {k: [journees[d].get(k) for d in dates] for k in FEATURES},
    }


def pack_vers_journees(pack):
    """Inverse exact de l'encodage colonnaire de `construire_pack` :
    rend le `{date: {feature: valeur}}` d'origine. Sert à REPRENDRE un
    corpus existant avant de lui ajouter des journées (mode entretien).

    Tolérant à une colonne absente (un pack de schéma antérieur à qui
    manquerait une feature) : la valeur devient None, ce que le reste de
    la chaîne sait déjà traiter. Intolérant en revanche à une colonne
    plus courte que `dates` — ce serait un pack corrompu, et le silence
    y ferait perdre des journées sans que rien ne le dise."""
    dates = pack.get("dates") or []
    cols = pack.get("cols") or {}
    for k, v in cols.items():
        if len(v) != len(dates):
            raise Abort(f"pack corrompu : colonne '{k}' de {len(v)} valeurs "
                        f"pour {len(dates)} dates — ne pas réécrire par-dessus")
    return {d: {k: cols.get(k, [None] * len(dates))[i] for k in FEATURES}
            for i, d in enumerate(dates)}


def gzipper(obj):
    brut = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode()
    buf = io.BytesIO()
    # mtime=0 : deux runs produisant les mêmes données produisent le même
    # octet-à-octet. Sans ça, l'ETag change chaque jour même quand rien
    # n'a bougé, et le cache CDN est invalidé pour rien.
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=9, mtime=0) as f:
        f.write(brut)
    return buf.getvalue()


def cle_r2(deco):
    """Clé stable, dérivée des coordonnées — c'est ce qui détermine
    physiquement le contenu du pack. 4 décimales ≈ 11 m : deux décos
    distincts ne collident pas.
    ⚠️ Faiblesse assumée : corriger une coordonnée dans `decos.json`
    orpheline l'ancien pack. Les suppressions R2 étant GRATUITES, la
    purge se fera par comparaison checkpoint ↔ decos.json, jamais par un
    ListObjects (facturé)."""
    return f"{R2_PREFIX}{deco['lat']:.4f}_{deco['lon']:.4f}.json.gz"


# ══════════════════════════════════════════════════════════════════════
#  R2
# ══════════════════════════════════════════════════════════════════════
class R2:
    """`local=True` : on calcule et on écrit les packs sur disque, sans
    toucher à R2. C'est le mode de la validation des 3 packs de test
    (taille / format / relecture) exigée avant le run complet."""

    def __init__(self, dry_run, local=False):
        self.dry_run = dry_run or local
        self.local = local
        self.client = None
        self.bucket = os.environ.get("R2_BUCKET", "")
        if self.dry_run:
            return
        try:
            import boto3               # noqa: PLC0415
            from botocore.config import Config   # noqa: PLC0415
        except ImportError:
            raise Abort("boto3 absent — `pip3 install boto3` (ou lancer "
                        "en --dry-run)")
        for v in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID",
                  "R2_SECRET_ACCESS_KEY", "R2_BUCKET"):
            if not os.environ.get(v):
                raise Abort(f"variable d'environnement {v} manquante")
        self.client = boto3.client(
            "s3",
            endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
            # Aucun réessai automatique : un réessai en boucle est LE
            # scénario qui crame le quota d'opérations. On préfère un
            # échec visible, repris au prochain run.
            config=Config(retries={"max_attempts": 1, "mode": "standard"}),
        )

    def get(self, cle):
        """Lit un pack DÉJÀ ÉCRIT, par sa clé exacte. Renvoie le dict
        décodé, ou None si l'objet n'existe pas.

        ⚠️ CETTE MÉTHODE EXISTE À CAUSE D'UN BUG DESTRUCTIF (02/08/2026).
        Le mode `entretien` reconstruisait le pack à partir des SEULES
        journées fetchées dans le run (92 j) et l'écrasait en place :
        les 940 journées d'archive partaient, avec `complet: true` et
        `plages_perdues: 0` par-dessus. Le pack aurait menti par
        omission, le checkpoint aussi, et `a_refaire()` aurait fait
        sauter la réparation par un `--mode backfill`. Trouvé à la
        relecture, avant le premier run d'entretien — donc jamais
        déclenché. Le worker DOIT connaître le corpus existant avant de
        le réécrire ; il n'a aucun autre moyen de le connaître.

        ⚠️ Ne PAS confondre avec l'interdiction du garde-fou n°1. Ce qui
        est proscrit, c'est `ListObjects`/`HeadObject` pour reconstituer
        l'état de reprise — ça, c'est le rôle du checkpoint local, et
        c'est facturé en **Class A** (1 M/mois). Un `GetObject` sur une
        clé connue est facturé en **Class B** (10 M/mois) : 210/jour =
        6 300/mois = 0,06 % du palier. Le coût est réel mais négligeable,
        et il achète la seule chose qui empêche un entretien de détruire
        une archive de deux jours de quota."""
        if self.local:
            p = PACKS_LOCAL / cle.replace(R2_PREFIX, "")
            if not p.exists():
                return None
            return json.loads(gzip.decompress(p.read_bytes()))
        if self.dry_run:
            return None
        try:
            r = self.client.get_object(Bucket=self.bucket, Key=cle)
        except Exception as e:               # noqa: BLE001
            if "NoSuchKey" in type(e).__name__ or "NoSuchKey" in str(e):
                CPT.class_b += 1
                return None
            raise
        CPT.class_b += 1
        return json.loads(gzip.decompress(r["Body"].read()))

    def put(self, cle, corps, plafond):
        if CPT.class_a + 1 > plafond:
            raise Abort(f"plafond d'écritures R2 atteint ({plafond} Class A) "
                        f"— arrêt net, reprise au prochain run")
        if self.local:
            p = PACKS_LOCAL / cle.replace(R2_PREFIX, "")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(corps)
        if self.dry_run:
            CPT.class_a += 1
            CPT.octets_envoyes += len(corps)
            return
        self.client.put_object(
            Bucket=self.bucket, Key=cle, Body=corps,
            ContentType="application/json", ContentEncoding="gzip",
            CacheControl=R2_CACHE_CONTROL)
        CPT.class_a += 1
        CPT.octets_envoyes += len(corps)


# ══════════════════════════════════════════════════════════════════════
#  CHECKPOINT  —  local, jamais dans R2
# ══════════════════════════════════════════════════════════════════════
def charger_checkpoint():
    if CHECKPOINT.exists():
        try:
            return json.loads(CHECKPOINT.read_text())
        except (OSError, ValueError):
            log("⚠️ checkpoint illisible — on repart de zéro "
                "(les packs déjà en R2 seront simplement réécrits à l'identique)")
    return {"version": 1, "archive_start": ARCHIVE_START, "decos": {}}


def ecrire_checkpoint(ck):
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    tmp = CHECKPOINT.with_suffix(".tmp")
    tmp.write_text(json.dumps(ck, ensure_ascii=False))
    tmp.replace(CHECKPOINT)          # remplacement atomique : un Ctrl-C
                                     # pendant l'écriture ne corrompt rien


# ══════════════════════════════════════════════════════════════════════
#  DIMENSIONNEMENT  —  refuser de démarrer plutôt que de payer
# ══════════════════════════════════════════════════════════════════════
def verifier_dimensionnement(n_decos, mode):
    ko_par_pack = 22          # majorant mesuré le 01/08 (colonnaire gzip)
    stockage_go = n_decos * ko_par_pack / 1e6
    ecr_backfill = n_decos
    r = rotation(n_decos)
    ecr_jour = math.ceil(n_decos / r)
    ecr_entretien_mois = ecr_jour * 30
    n_jours = (date.today() - date.fromisoformat(ARCHIVE_START)).days
    n_plages = math.ceil(n_jours / CHUNK_DAYS)
    ponderes = poids_pondere(n_decos, min(CHUNK_DAYS, n_jours), 12) * n_plages

    log("┌─ DIMENSIONNEMENT PROJETÉ ────────────────────────────────────")
    log(f"│ périmètre                 : départements {','.join(PERIMETRE_DEPARTEMENTS) or '(aucun filtre)'}")
    log(f"│ décos                     : {n_decos}")
    log(f"│ archive                   : {ARCHIVE_START} → hier ({n_jours} j, {n_plages} plages)")
    log(f"│ stockage R2               : {stockage_go*1000:.1f} Mo  (seuil d'arrêt {SEUIL_STOCKAGE_GO*1000:.0f} Mo)")
    log(f"│   palier gratuit          : 10 Go-mois → marge ×{10/max(stockage_go,1e-9):.0f}")
    log(f"│ écritures backfill        : {ecr_backfill} Class A (plafond dur/run {MAX_CLASS_A_BACKFILL})")
    log(f"│ écritures entretien       : {ecr_jour}/jour "
        f"({'tout le catalogue chaque jour' if r == 1 else f'rotation 1/{r}'}) "
        f"→ {ecr_entretien_mois}/mois (seuil {SEUIL_ECRITURES_MOIS})")
    log(f"│   palier gratuit          : 1 M Class A/mois → marge ×{1e6/max(ecr_entretien_mois,1):.0f}")
    log(f"│ appels Open-Meteo pondérés: {ponderes:.0f} (backfill complet, une fois)")
    log(f"│   plafond gratuit         : 10 000/jour, 300 000/mois → "
        f"~{ponderes/10000:.1f} jour(s)")
    # Entretien : une seule journée (J-1) par déco, pas une plage de 92 j.
    # ⚠️ Le prompt de reprise du 02/08 annonçait « ~3 % du quota » : c'était
    # le chiffre d'une fenêtre de 92 jours (~15 %), pas celui-ci. Le vrai
    # coût quotidien est deux ordres de grandeur plus bas.
    pond_jour = poids_pondere(ecr_jour, 1, 12)
    log(f"│ entretien quotidien       : {pond_jour:.1f} pondéré/jour "
        f"({pond_jour/10000*100:.2f} % du quota) + {ecr_jour} Class B (lecture) "
        f"+ ≤{ecr_jour} Class A")
    log("└──────────────────────────────────────────────────────────────")

    if stockage_go > SEUIL_STOCKAGE_GO:
        raise Abort(f"stockage projeté {stockage_go:.1f} Go > seuil {SEUIL_STOCKAGE_GO} Go")
    if ecr_entretien_mois > SEUIL_ECRITURES_MOIS:
        raise Abort(f"écritures projetées {ecr_entretien_mois}/mois > seuil {SEUIL_ECRITURES_MOIS}")
    plafond = MAX_CLASS_A_BACKFILL if mode == "backfill" else MAX_CLASS_A_ENTRETIEN
    if n_decos > plafond:
        log(f"ℹ️  {n_decos} décos > plafond de {plafond} écritures : le run "
            f"s'arrêtera au plafond et reprendra là où il en est.")
    return plafond


# ══════════════════════════════════════════════════════════════════════
#  BOUCLE PRINCIPALE
# ══════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════
#  POINT DANS POLYGONE  —  filtre de périmètre
# ══════════════════════════════════════════════════════════════════════
# Les polygones viennent de `france-geojson` (contours officiels IGN,
# redistribués). Ils sont embarqués dans `perimetre/` plutôt que
# téléchargés à l'exécution : un worker qui tourne des heures ne doit
# dépendre d'aucun service tiers pour savoir CE QU'IL DOIT FAIRE.
# On refiltre à chaque run plutôt que de figer une liste de décos :
# `decos.json` est régénéré par `ingest_decos_pge.py`, une liste figée
# se périmerait en silence.
def _anneaux(geo):
    return [geo["coordinates"]] if geo["type"] == "Polygon" else geo["coordinates"]


def _dans_anneau(x, y, anneau):
    """Ray casting. Sur un point EXACTEMENT sur une arête le résultat est
    arbitraire — c'est sans conséquence ici (cf. l'avertissement sur les
    décos frontaliers dans `charger_decos`)."""
    dedans = False
    n = len(anneau)
    j = n - 1
    for i in range(n):
        xi, yi = anneau[i][0], anneau[i][1]
        xj, yj = anneau[j][0], anneau[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dedans = not dedans
        j = i
    return dedans


def _dans_polygone(x, y, geo):
    for poly in _anneaux(geo):
        # poly[0] = contour extérieur, poly[1:] = trous (enclaves)
        if _dans_anneau(x, y, poly[0]) and not any(
                _dans_anneau(x, y, t) for t in poly[1:]):
            return True
    return False


def charger_perimetre():
    """Renvoie {code_dept: géométrie}. Abort si un polygone manque : mieux
    vaut refuser de démarrer que traiter silencieusement un périmètre
    plus petit que celui demandé."""
    geos = {}
    for code in PERIMETRE_DEPARTEMENTS:
        f = PERIMETRE_DIR / f"departement-{code}.geojson"
        if not f.exists():
            raise Abort(f"polygone manquant pour le département {code} "
                        f"({f}). Le télécharger depuis france-geojson, ou "
                        f"retirer {code} de BW_DEPARTEMENTS.")
        d = json.loads(f.read_text())
        geos[code] = d["geometry"] if d.get("type") == "Feature" \
            else d["features"][0]["geometry"]
    return geos


def charger_decos():
    brut = json.loads(DECOS_JSON.read_text())
    geos = charger_perimetre() if PERIMETRE_DEPARTEMENTS else None
    out, hors, sans_alt = [], 0, 0
    par_dept = {}
    for lat, lon, nom, alt, *_ in brut:
        if alt is None:
            sans_alt += 1
            continue
        dept = None
        if geos is not None:
            for code, g in geos.items():
                if _dans_polygone(lon, lat, g):
                    dept = code
                    break
            if dept is None:
                hors += 1
                continue
        out.append({"lat": lat, "lon": lon, "nom": nom, "alt": alt,
                    "dept": dept, "level": niveau_crete(alt)})
        par_dept[dept] = par_dept.get(dept, 0) + 1
    if geos is not None:
        detail = " · ".join(f"{c}: {par_dept.get(c, 0)}" for c in PERIMETRE_DEPARTEMENTS)
        log(f"périmètre {','.join(PERIMETRE_DEPARTEMENTS)} → {len(out)} décos "
            f"({detail}) · {hors} hors périmètre · {sans_alt} sans altitude")
        # ⚠️ Les contours sont des polygones simplifiés : un déco à moins
        # de ~100 m d'une frontière départementale peut tomber du mauvais
        # côté. Mesuré le 01/08 : 16 décos à moins de 2 km d'une
        # frontière, dont « Roc de Frausa » à 10 m et « Puigmal » à 60 m.
        # Sans conséquence sur la météo (même maille AROME de 2,5 km de
        # part et d'autre), mais un site attendu et absent se cherche là.
        if not out:
            raise Abort("périmètre vide — vérifier BW_DEPARTEMENTS")
    return out


def selectionner(decos, ck, mode, limit, local=False):
    if mode == "backfill":
        # Idempotent : un déco déjà écrit pour cette archive n'est pas refait.
        # ⚠️ « Écrit » NE SUFFIT PAS — il faut « écrit COMPLET ». Bug trouvé
        # le 01/08 au premier run réel : deux plages sur onze avaient été
        # perdues (timeout), le pack avait quand même été écrit avec ~184
        # journées manquantes sur 942, et le checkpoint le marquait fait.
        # Le log promettait « elle sera reprise au prochain run » : c'était
        # faux. Un corpus amputé de 20 % qui se croit complet est pire
        # qu'une erreur, parce que rien ne le signale ensuite.
        def a_refaire(d):
            e = ck["decos"].get(cle_r2(d))
            if e is None or e.get("archive_start") != ARCHIVE_START:
                return True
            # ⚠️ « Complet » ne suffit pas non plus : complet OÙ ?
            # Troisième trou de reprise trouvé le 01/08. Les décos traités
            # en `--local` (validation des packs de test) étaient marqués
            # complets ; un `--go` ultérieur les aurait donc SAUTÉS, et ils
            # ne seraient jamais arrivés sur R2. On se serait retrouvé avec
            # 204 packs en ligne sur 210, sans que rien ne le signale.
            # La destination fait donc partie de l'état, pas du contexte.
            if not local and e.get("dest") != "r2":
                return True
            if e.get("complet"):
                return False
            # Incomplet : on retente, mais pas indéfiniment. Une plage
            # durablement indisponible côté API ne doit pas bloquer le
            # catalogue — au bout de MAX_ESSAIS on accepte le pack tel
            # quel, et le trou est écrit DANS le pack (`plages_perdues`).
            return e.get("essais", 0) < MAX_ESSAIS
        restants = [d for d in decos if a_refaire(d)]
    else:
        r = rotation(len(decos))
        if r == 1:
            restants = list(decos)
        else:
            jour = date.today().toordinal() % r
            restants = [d for i, d in enumerate(sorted(decos, key=cle_r2))
                        if i % r == jour]
    return restants[:limit] if limit else restants


def rotation(n_decos):
    """Combien de jours pour rafraîchir tout le catalogue.

    Décision Yann du 01/08 : rotation 1/7 — elle avait été chiffrée pour
    les 3313 décos, où réécrire tout chaque jour coûtait ~99 400 Class A
    par mois ET invalidait le cache CDN de chaque pack quotidiennement.

    Sur le périmètre de bêta (86 décos), cet arbitrage n'a plus d'objet :
    tout réécrire chaque jour coûte 86 écritures/jour, soit ~2 600 par
    mois — 0,26 % du palier gratuit. La fraîcheur à J-1 partout est alors
    gratuite, et il n'y a aucune raison de s'en priver.
    Le seuil bascule tout seul quand le périmètre grandit ; c'est
    volontaire, pour qu'une extension de périmètre ne fasse pas
    silencieusement exploser le compteur d'écritures."""
    return 1 if n_decos <= 500 else 7


def traiter(mode, dry_run, limit, fin, local=False):
    decos = charger_decos()
    log(f"decos.json : {len(decos)} décos avec altitude")
    ck = charger_checkpoint()
    if ck.get("archive_start") != ARCHIVE_START:
        log(f"ℹ️  checkpoint pour archive {ck.get('archive_start')} ≠ {ARCHIVE_START} "
            f"— tous les packs seront recalculés")
        ck = {"version": 1, "archive_start": ARCHIVE_START, "decos": {}}

    plafond = verifier_dimensionnement(len(decos), mode)
    if dry_run and not local:
        log("── DRY RUN : aucune écriture R2, aucun appel météo ──")
        return

    cibles = selectionner(decos, ck, mode, limit, local=local)
    # ⚠️ EN ENTRETIEN, LA FENÊTRE SE CALCULE PAR DÉCO, pas ici — elle
    # part de la dernière journée DÉJÀ dans le pack. Voir plus bas.
    debut = ARCHIVE_START if mode == "backfill" else None
    log(f"mode {mode} : {len(cibles)} décos à traiter, "
        f"{debut or 'dernière journée du pack'} → {fin}")
    if not cibles:
        log("rien à faire — tout est à jour.")
        return

    r2 = R2(dry_run, local=local)
    plages_backfill = list(_plages(debut, fin)) if debut else None

    # Les points d'un même lot doivent partager le niveau de crête : les
    # variables demandées en dépendent. D'où le groupement par niveau
    # AVANT le découpage en lots. Répartition des 3313 décos (mesurée) :
    # 900 hPa ×1570, 850 ×652, 800 ×748, 700 ×326, 600 ×16, 500 ×1.
    par_niveau = {}
    for d in cibles:
        par_niveau.setdefault(d["level"], []).append(d)

    for level, groupe in sorted(par_niveau.items(), reverse=True):
        log(f"\n══ niveau {level} hPa — {len(groupe)} décos ══")
        for i0 in range(0, len(groupe), BATCH_POINTS):
            lot = groupe[i0:i0 + BATCH_POINTS]

            # ── ENTRETIEN : on part du corpus DÉJÀ EN LIGNE ───────────
            # Un pack d'entretien n'est pas un pack neuf, c'est un pack
            # existant plus une journée. Le lire d'abord est la seule
            # chose qui empêche l'écrasement (cf. R2.get).
            if mode == "entretien":
                acc, base_n, plages = [], [], []
                depuis = fin
                for d in lot:
                    pack = r2.get(cle_r2(d))
                    if pack is None:
                        # Un déco absent de R2 relève du BACKFILL, pas de
                        # l'entretien. On ne le fabrique pas ici : un pack
                        # d'une seule journée serait pire que pas de pack.
                        log(f"  ⚠️ {d['nom']} : aucun pack en ligne — "
                            f"relève de --mode backfill, ignoré")
                        acc.append(None)
                        base_n.append(0)
                        continue
                    j0 = pack_vers_journees(pack)
                    if not j0:
                        # Pack en ligne mais vide : anomalie, pas un point
                        # de départ. On ne construit rien par-dessus.
                        log(f"  ⚠️ {d['nom']} : pack en ligne SANS aucune "
                            f"journée — anomalie, relève de --mode backfill")
                        acc.append(None)
                        base_n.append(0)
                        continue
                    acc.append(j0)
                    base_n.append(len(j0))
                    depuis = min(depuis, max(j0))
                vivants = [j for j in acc if j is not None]
                if not vivants:
                    continue
                # Fenêtre = lendemain de la dernière journée connue → J-1.
                # Un run raté hier se rattrape donc tout seul aujourd'hui,
                # sans qu'on ait à le détecter.
                a0 = (date.fromisoformat(depuis) + timedelta(days=1)).isoformat()
                if a0 > fin:
                    log(f"  ✓ {lot[0]['nom']}{'…' if len(lot) > 1 else ''} : "
                        f"déjà à jour au {fin} — aucun appel, aucune écriture")
                    continue
                plages = list(_plages(a0, fin))
            else:
                acc = [dict() for _ in lot]
                base_n = [0] * len(lot)
                plages = plages_backfill

            perdues_avant = CPT.plages_perdues
            for (a, b) in plages:
                t0 = time.time()
                res = fetch_lot([d for d, j in zip(lot, acc) if j is not None],
                                level, a, b)
                for j, r in zip([k for k, x in enumerate(acc) if x is not None], res):
                    acc[j].update(r)
                log(f"  {a}→{b} · {len(res)} pts · {time.time()-t0:5.1f}s · "
                    f"{sum(len(r) for r in res)} journées")
                time.sleep(PAUSE_S)
            perdues = CPT.plages_perdues - perdues_avant

            for d, journees, n_avant in zip(lot, acc, base_n):
                if journees is None:
                    continue
                if not journees:
                    CPT.decos_vides += 1
                    log(f"  ⚠️ {d['nom']} : aucune journée — non écrit")
                    continue
                # ⚠️ GARDE-FOU ANTI-RÉGRESSION (02/08/2026), symétrique de
                # SEUIL_PACK_KO qui garde déjà l'autre bout. Un pack ne
                # rétrécit JAMAIS : l'archive ne se raccourcit pas. Cette
                # règle, à elle seule, aurait arrêté le bug de l'entretien
                # avant la première écriture — c'est pour ça qu'elle est
                # ici et pas dans un commentaire.
                if len(journees) < n_avant:
                    raise Abort(
                        f"pack {d['nom']} : {len(journees)} journées contre "
                        f"{n_avant} déjà en ligne — un pack ne rétrécit pas. "
                        f"Rien n'est écrit, comprendre avant de relancer")
                if mode == "entretien" and len(journees) == n_avant:
                    # Aucune journée gagnée (plage perdue, ou archive pas
                    # encore publiée pour J-1). Réécrire à l'identique ne
                    # coûterait qu'une Class A et un ETag neuf pour rien —
                    # et invaliderait le cache navigateur de tous les
                    # pilotes. On ne touche pas au pack.
                    log(f"  ↻ {d['nom']} : aucune journée nouvelle "
                        f"({perdues} plage(s) perdue(s)) — pack laissé en place")
                    continue
                cle = cle_r2(d)
                essais = ck["decos"].get(cle, {}).get("essais", 0) + 1
                complet = perdues == 0
                if not complet and essais >= MAX_ESSAIS:
                    log(f"  ⚠️ {d['nom']} : {perdues} plage(s) toujours absente(s) "
                        f"après {essais} essais — pack accepté tel quel, trou "
                        f"consigné dans le pack")
                    complet = True          # on cesse de retenter, sans mentir
                corps = gzipper(construire_pack(d, level, journees, perdues))
                ko = len(corps) / 1024
                if ko > SEUIL_PACK_KO:
                    # Garde-fou n°1, règle 2 : un pack anormalement gros
                    # est un symptôme, pas un détail. On ne l'écrit pas.
                    raise Abort(f"pack {d['nom']} = {ko:.0f} Ko > {SEUIL_PACK_KO} Ko "
                                f"({len(journees)} journées) — comprendre avant d'écrire")
                r2.put(cle, corps, plafond)
                ck["decos"][cle] = {"archive_start": ARCHIVE_START,
                                    "n": len(journees), "ko": round(ko, 1),
                                    "complet": complet, "essais": essais,
                                    "plages_perdues": perdues,
                                    "dest": "local" if local else "r2",
                                    "le": date.today().isoformat()}
                if complet:
                    CPT.decos_ok += 1
                else:
                    log(f"  ↻ {d['nom']} : {len(journees)} journées, "
                        f"{perdues} plage(s) perdue(s) — À REPRENDRE au prochain run")
            ecrire_checkpoint(ck)      # après chaque lot, pas à la fin
            log("  " + CPT.ligne())


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--mode", choices=["backfill", "entretien"], default="backfill")
    ap.add_argument("--limit", type=int, default=0,
                    help="ne traiter que N décos (test)")
    ap.add_argument("--end", default=(date.today() - timedelta(days=1)).isoformat())
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True)
    g.add_argument("--go", dest="dry_run", action="store_false",
                   help="écrire pour de vrai (défaut : dry-run)")
    ap.add_argument("--local", action="store_true",
                    help="appels météo réels, packs écrits sur disque, "
                         "R2 non touché (validation des packs de test)")
    args = ap.parse_args()

    etat = ("LOCAL (R2 non touché)" if args.local
            else "DRY-RUN" if args.dry_run else "ÉCRITURE RÉELLE")
    log(f"\n═══ backfill_packs · mode={args.mode} · {etat} · source={HF_URL} ═══")
    code = 0
    try:
        traiter(args.mode, args.dry_run, args.limit, args.end, local=args.local)
    except Abort as e:
        log(f"\n⛔ ABORT : {e}")
        code = 2
    except KeyboardInterrupt:
        log("\n⏸  interrompu — le checkpoint est à jour, relancer pour reprendre")
        code = 130
    log(CPT.ligne())
    sys.exit(code)


if __name__ == "__main__":
    main()
