#!/usr/bin/env python3
"""collect.py — la collecte nocturne : prévisions et observations.

    Session 07/08/2026.
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
    # ⚠️ `meteoswiss_icon_ch1` RETIRÉ LE 09/08 — et ce n'est pas un
    # arbitrage de goût, c'est de l'arithmétique de quota.
    #
    # À 8 variables, 10 modèles pèsent 8,0 par point : 648 × 8 = 5 184
    # appels pondérés, au-dessus du plafond HORAIRE de 5 000 que le code
    # ne modélisait pas. La nuit du 09/08 s'est arrêtée à 625 points
    # collectés — 5 000 pondérés à l'unité près — puis n'a plus rien
    # obtenu pendant 26 min, jusqu'au chien de garde. À 9 modèles le
    # poids tombe à 7,2 et le run redescend à 4 666 : il rentre.
    #
    # ⚠️ POURQUOI CELUI-LÀ ET PAS UN AUTRE — mesuré sur l'archive
    # complète du 08/08 (648 balises), pas raisonné :
    #   · retirer AROME HD ou DMI HARMONIE coûterait à 53 balises leur
    #     DEUXIÈME avis à maille fine (et AROME en laisserait 2 sans
    #     aucun) — exclus ;
    #   · CH1 couvre EXACTEMENT les mêmes 515 balises que CH2 (ensembles
    #     identiques, vérifié) : même fournisseur, même domaine, 1 km
    #     contre 2 km. C'est le seul vrai doublon de la liste ;
    #   · son horizon médian mesuré vaut 34 h, donc il ne concourait
    #     déjà pas au +48 h.
    # Retirer CH1 ne fait tomber AUCUNE balise sous son nombre d'avis
    # fins actuel. C'est le seul des dix dont on puisse dire ça.
    #
    # ⚠️ CE QUE ÇA COÛTE, ET QUI DOIT LE DIRE. L'app continue de
    # PROPOSER ICON-CH1 aux pilotes (`localModels.ts` — il y est le plus
    # fin en Maurienne) alors qu'il ne sera plus NOTÉ. Il rejoint les
    # quatre modèles déjà dans ce cas (ICON-2I, UKMO 2 km, AROME
    # Autriche, KNMI Harmonie) : l'écran qui juxtapose « modèles de la
    # coupe » et « modèles notés » doit l'écrire, sinon il se lira
    # comme un trou de données.
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

#: ⚠️ MESURÉ LE 07/08, PAS RAISONNÉ. La valeur précédente — 0,25 s — a
#: coûté **24 points sur 648** en `HTTP 429` au premier run complet.
#: Trois séries depuis le VPS, sur des points réels (`sonde_cadence.py`) :
#:
#:   | cadence réelle | résultat                          |
#:   |----------------|-----------------------------------|
#:   |  30 req à 186/min | 30/30 — trop court pour remplir la fenêtre |
#:   | 320 req à 131/min | 31 × 429, blocage FRANC à partir de la 275ᵉ |
#:   | 300 req à  89/min | 0 × 429 (un seul échec réseau)    |
#:
#: Open-Meteo ne renvoie AUCUN en-tête de limitation : il n'y a rien à
#: lire pour s'adapter, il faut rester sous la ligne par construction.
BATCH_PAUSE_S = 0.45

#: ⚠️ `FCST_PAUSE_S` ET LA CONSTANTE DE LATENCE ONT DISPARU LE 09/08.
#: Elles réglaient la passe prévisions en BOUCLE OUVERTE : on choisissait
#: un délai en espérant une cadence, et personne ne mesurait la cadence
#: obtenue. Le 09/08 l'a payé — la latence réelle valait 0,06 s et non
#: les 0,22 s inscrites ici, donc 79 req/min × 8 = 631 pondérés/min, au
#: -dessus des 600. Un réseau PLUS RAPIDE faisait DÉPASSER le plafond.
#:
#: La passe prévisions demande désormais son droit de parler à
#: `tools/quota_openmeteo.py`, qui compte en POIDS sur trois fenêtres
#: glissantes (minute, HEURE, jour) et partage ce compte avec les quatre
#: autres scripts qui appellent Open-Meteo depuis cette IP. On ne décide
#: plus combien de temps dormir : on décide quand on a le droit de
#: partir, et le sommeil en découle. La latence est alors absorbée, plus
#: estimée — c'est tout l'objet du lot.
#:
#: `BATCH_PAUSE_S` reste, et reste une pause fixe : la passe
#: observations interroge Pioupiou, qui n'a ni le même plafond ni la
#: même pondération. La ralentir « par sympathie » aurait coûté 4 min de
#: run pour rien.

MAX_RETRIES = 3
TIMEOUT_S = 45

#: Après un 429, la fenêtre de limitation doit se VIDER. Les 1-2-4 s de
#: `MAX_RETRIES` ne suffisent pas : un point refusé mourait en ~7 s alors
#: que la porte reste fermée une minute. Une pause franche, une seule
#: fois par point — après elle, la fenêtre est repartie et les points
#: suivants passent.
PAUSE_429_S = 65

#: ⚠️ PLAFONDS OPEN-METEO — TROIS, PAS DEUX. C'est le défaut qui a coûté
#: la nuit du 09/08 : le code ne connaissait que le jour et la minute,
#: et le palier gratuit compte AUSSI 5 000 appels pondérés par HEURE.
#: 648 points × 8 tenaient sous les 10 000 du jour et sous les 600 de la
#: minute — et franchissaient l'heure au 626ᵉ point. Le run s'est arrêté
#: à 625 points collectés, soit 5 000 pondérés à l'unité près, puis n'a
#: plus rien obtenu pendant 26 min : contrairement à la minute, une
#: fenêtre horaire pleine ne se vide pas en attendant 65 s.
#:
#: Les valeurs vivent maintenant dans `tools/quota_openmeteo.py`, avec
#: le compteur qui les fait respecter. Les alias ci-dessous ne sont là
#: que pour les messages de `quota_projete`.
QUOTA_JOUR = 10_000
QUOTA_MINUTE = 600
QUOTA_HEURE = 5_000


def charger_quota():
    """Le module de budget partagé, ou `None` s'il n'est pas déployé.

    ⚠️ IMPORT PARESSEUX ET RATTRAPÉ, comme `storage.py` plus bas. Un
    garde-fou qui empêche de tourner est pire que le risque qu'il
    couvre : si `tools/quota_openmeteo.py` manque sur le VPS — un rsync
    qui n'a copié que `model-verif/`, par exemple —, la collecte doit
    repartir en cadence conservatrice, pas s'arrêter.
    """
    tools = pathlib.Path(__file__).resolve().parent.parent / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    try:
        import quota_openmeteo                        # type: ignore
        return quota_openmeteo
    except Exception as exc:                          # noqa: BLE001
        print(f"  ⓘ budget partagé indisponible ({exc}) — cadence "
              f"conservatrice, sans comptage partagé", file=sys.stderr)
        return None


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
    """GET avec réessais, et un traitement À PART du 429.

    ⚠️ POURQUOI LE 429 N'EST PAS UNE ERREUR COMME LES AUTRES. Les autres
    échecs sont des accidents : on retente vite, ça repasse. Un 429 est
    une décision — la porte est fermée, et elle le reste le temps que la
    fenêtre se vide. Retenter au bout d'une, deux puis quatre secondes,
    c'est frapper trois fois à une porte qu'on sait fermée, puis
    abandonner le point. C'est exactement ce qui a coûté 24 balises au
    premier run complet du 07/08.

    Une seule pause franche par point, donc, et pas trois : après elle la
    fenêtre est repartie, et ce sont les points SUIVANTS qui en
    profitent. Le point qui a payé l'attente est celui qui la rend aux
    autres.
    """
    pause_429_deja_prise = False
    for attempt in range(MAX_RETRIES):
        try:
            return _get_json(url)
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and not pause_429_deja_prise:
                pause_429_deja_prise = True
                # `Retry-After` s'il existe — Open-Meteo n'en envoie pas
                # (mesuré le 07/08), d'où la valeur de repli.
                # ⚠️ `exc.headers` peut valoir None : une HTTPError peut
                # être levée sans en-têtes du tout. Le banc l'a attrapé
                # avant la production — sans ce `getattr`, la lecture du
                # Retry-After plantait sur AttributeError, et le point
                # mourait d'une exception au lieu d'attendre.
                entetes = getattr(exc, "headers", None)
                brut = entetes.get("Retry-After") if entetes else None
                try:
                    attente = float(brut or 0)
                except (TypeError, ValueError):
                    attente = 0.0
                attente = attente or PAUSE_429_S
                print(f"  ⏸ 429 sur {label} — pause de {attente:.0f}s, "
                      f"le temps que la fenêtre se vide", file=sys.stderr)
                time.sleep(attente)
                continue
            if attempt == MAX_RETRIES - 1:
                print(f"  ⚠️  {label} abandonné : {exc}", file=sys.stderr)
                return None
            time.sleep(2 ** attempt)
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

#: Variables ajoutées le 08/08 pour E4 (précipitations) et E6 (pression,
#: température). Elles ne servent à AUCUN score aujourd'hui — elles sont
#: archivées parce que c'est la seule pièce du dispositif qui ne se
#: rattrape pas : une nuit non collectée n'existera jamais, alors que
#: tout le calcul se rejoue depuis R2 quand on veut.
#:
#: ⚠️ SONDÉ EN DIRECT LE 08/08 SUR 4 POINTS RÉELS (Maurienne, Pyrénées,
#: Bretagne, plaine du Sud-Ouest), pas lu dans la doc :
#:
#:   · `meteofrance_arome_france_hd` NE SERT NI `pressure_msl` NI
#:     `surface_pressure`. La clé est PRÉSENTE et intégralement `null`,
#:     sur les quatre points. E6 n'aura donc jamais AROME — c'est un
#:     fait de l'API, pas un trou de collecte, et il ne faut pas le
#:     relire dans six mois comme une panne.
#:   · Les autres modèles hors domaine, eux, n'ont PAS de clé du tout.
#:     Deux comportements différents dans la même réponse : d'où le
#:     `_serie()` de `forecast_rows`, qui teste le CONTENU et pas la
#:     présence. C'est le piège ERA5 du 06/08, en plus sournois.
#:   · `surface_pressure` a été écartée : partout où elle existe,
#:     `pressure_msl` existe aussi, et c'est le gradient au niveau de la
#:     mer qui porte E6. Deux variables auraient coûté 648 appels
#:     pondérés de plus par nuit pour une information redondante.
#:   · AROME s'arrête à 55 pas sur 72 pour `precipitation` et
#:     `temperature_2m`, ICON-CH1 à 40 : c'est leur horizon, pas un
#:     défaut. Les listes sont donc plus courtes que `speed` sur
#:     certains modèles — le format le supporte, `t0 + i × step_s`
#:     reste la seule convention.
NEW_SURFACE_VARS = ["precipitation", "pressure_msl", "temperature_2m"]


def _hourly_vars() -> list[str]:
    return ["wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
            *NEW_SURFACE_VARS,
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
    # ⚠️ LA REMISE `jours/14` A ÉTÉ RETIRÉE LE 07/08, ET C'EST LE CŒUR DU
    # DÉFAUT. Avec elle, une requête pesait 3/14 × 50/10 = 1,07, et cet
    # encadré annonçait fièrement « 6,9 % du plafond ». À 240 requêtes
    # théoriques par minute, cela donnait 257 pondérés/min, très en
    # dessous des 600 : le garde-fou ne pouvait pas se déclencher.
    #
    # Le premier run réel a perdu 24 points en 429. Sans la remise, une
    # requête pèse 5, la cadence réelle du run (131/min) valait 655
    # pondérés/min — au-dessus de la ligne, ce que les mesures montrent.
    # On garde donc l'hypothèse la plus DÉFAVORABLE : un garde-fou qui se
    # trompe doit se tromper du côté qui protège.
    par_point = n_vars / 10
    total = n_points * par_point
    # ⚠️ CE QUI EST PROJETÉ ICI N'EST PLUS UNE CADENCE, C'EST UN VOLUME.
    # L'ancienne ligne comparait `60/(pause + latence)` au plafond de la
    # minute — une cadence ESPÉRÉE, jamais mesurée, et fausse le 09/08.
    # La cadence est maintenant tenue par le seau à jetons, qui la
    # mesure au lieu de l'estimer. Ce qu'aucun seau ne peut corriger, en
    # revanche, c'est un run qui ne TIENT PAS dans une fenêtre : d'où le
    # plafond horaire ci-dessous, qui est le seul garde-fou qui restait
    # à écrire.
    points_par_heure = QUOTA_HEURE / par_point
    print("┌─ QUOTA OPEN-METEO PROJETÉ ───────────────────────────────────")
    print(f"│ points                 : {n_points}")
    print(f"│ modèles × variables    : {len(MODELS)} × {len(_hourly_vars())} = {n_vars}")
    print(f"│ pondération / requête  : {n_vars}/10 = {par_point:.2f} "
          f"(sans remise sur {forecast_days} jours — cf. 07/08)")
    print(f"│ TOTAL du run           : {total:.0f} appels pondérés "
          f"({total / QUOTA_JOUR * 100:.1f} % du plafond journalier)")
    print(f"│ fenêtre HORAIRE        : {total:.0f} / {QUOTA_HEURE} "
          f"({total / QUOTA_HEURE * 100:.1f} %) — l'heure autorise "
          f"{points_par_heure:.0f} points à ce poids")
    print(f"│ cadence                : tenue par le seau à jetons "
          f"(tools/quota_openmeteo.py), plafonds {QUOTA_MINUTE}/min · "
          f"{QUOTA_HEURE}/h · {QUOTA_JOUR}/j")
    print("└──────────────────────────────────────────────────────────────")
    # ⚠️ SEUIL RELEVÉ DE 50 % À 60 % LE 08/08 — décision assumée, pas
    # contournement. Les trois variables d'E4/E6 portent le run mesuré de
    # 3 240 à 5 184 appels pondérés, soit 51,8 % : à 50 %, le garde-fou
    # aurait refusé de démarrer et la nuit aurait été perdue en silence.
    # Ce que ce seuil protège n'a pas changé — il attrape « quelqu'un a
    # ajouté dix modèles sans regarder », pas « on a délibérément ajouté
    # trois variables et on a recompté ». 60 % laisse 4 000 appels
    # pondérés de marge sur la journée.
    #
    # ⚠️ CE QUE CETTE MARGE DOIT COUVRIR — vérifié sur le VPS le 08/08,
    # pas supposé. Ce job est le seul consommateur Open-Meteo PLANIFIÉ
    # depuis cette IP (`systemctl list-timers` : les autres timers sont
    # `balise-infoclimat`, qui interroge Infoclimat, et l'entretien ;
    # aucun timer ni cron n'appelle `traces/backfill_packs.py`,
    # `match_analogs.py`, `day_features.py` ni `sonde_openmeteo.py`).
    # Mais ces quatre-là appellent bien Open-Meteo quand quelqu'un les
    # lance À LA MAIN, depuis la même IP et donc sur le même plafond
    # journalier. La marge de 4 000 est là pour ça : un backfill lancé
    # dans la journée ne doit pas faire tomber la collecte de la nuit.
    # L'app, elle, n'y touche pas — elle interroge Open-Meteo depuis le
    # navigateur des pilotes, jamais depuis ce serveur.
    if total > QUOTA_JOUR * 0.6:
        raise Abort(f"{total:.0f} appels pondérés > 60 % du plafond journalier — "
                    f"comprendre AVANT de forcer (nb de points ? de modèles ?)")
    # ⚠️ LE GARDE-FOU QUI MANQUAIT, ET QUI AURAIT SAUVÉ LA NUIT DU 09/08.
    # L'ancien comparait une cadence espérée au plafond de la minute ;
    # celui-ci compare le VOLUME du run au plafond de l'HEURE, qui est
    # celui qui a mordu. Il n'y a rien à régler pour le contourner :
    # aucune cadence ne fait tenir plus de 5 000 pondérés dans une heure.
    # Les trois issues sont un choix de produit — moins de variables,
    # moins de modèles, ou une passe étalée sur deux heures — et le
    # message doit les poser plutôt que de laisser chercher.
    #
    # 95 % et pas 100 : le compteur du serveur et le nôtre ne datent pas
    # une requête à la même milliseconde, et les scripts lancés à la
    # main partagent la même IP.
    if total > QUOTA_HEURE * 0.95:
        raise Abort(
            f"{total:.0f} appels pondérés pour {n_points} points, alors que "
            f"l'heure n'en autorise que {QUOTA_HEURE} — soit "
            f"{points_par_heure:.0f} points à {par_point:.1f} de poids. "
            f"C'est exactement ce qui a tué la nuit du 09/08. Aucune "
            f"cadence ne corrige un volume : retirer une variable ou un "
            f"modèle, ou étaler la passe sur deux heures (et relever "
            f"alors MAX_MINUTES, qui vaut 40).")
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

    def _serie(nom: str, model: str):
        """Une série, ou `None` si le modèle ne la sert pas.

        ⚠️ NE PAS SIMPLIFIER EN `hourly.get(...)`. Sondé le 08/08 sur
        quatre points réels : Open-Meteo a DEUX façons de dire « je ne
        sers pas cette variable », et une seule est visible d'un `get` :

          · hors domaine géographique → la clé est ABSENTE ;
          · AROME sur `pressure_msl`  → la clé est PRÉSENTE et remplie
            de 72 `null`.

        Sans ce filtre, l'archive gagnerait, pour chaque balise et
        chaque nuit, une liste de 72 nulls qui se relirait dans un an
        comme « AROME prévoyait quelque chose et on l'a mal lu ». Un
        champ absent dit la vérité ; une liste de nulls ment.
        """
        s = hourly.get(f"{nom}_{model}")
        if not s or all(v is None for v in s):
            return None
        return s

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
        # ⚠️ EXTENSION DU FORMAT, PAS RENOMMAGE (08/08). Les lignes
        # gagnent trois champs facultatifs ; aucun nom existant ne
        # bouge, aucun champ ne disparaît. Les archives des 07 et 08/08,
        # écrites sans eux, restent lisibles par ce même code — et
        # `score.py` lit déjà tout en `row.get(...)`, donc une archive
        # mixte ne lui pose aucune question. Un champ ABSENT signifie
        # « ce modèle ne sert pas cette variable ici », et c'est une
        # information ; un champ à `null` ne signifierait rien.
        for nom, court in (("precipitation", "precip"),
                           ("pressure_msl", "pmsl"),
                           ("temperature_2m", "t2m")):
            serie = _serie(nom, model)
            if serie is not None:
                row[court] = serie
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
#  OBSERVATIONS METAR (aérodromes) — ajouté le 08/08
# ══════════════════════════════════════════════════════════════════
#
#  POURQUOI CE FLUX EXISTE, ET POURQUOI IL EST À PART
#
#  Pioupiou observe des décollages : du relief, de la brise, et un biais
#  de site énorme. E4 (précipitations) et E6 (pression) ne s'y vérifient
#  pas — une balise Pioupiou ne mesure ni la pluie ni la pression de
#  référence. Les aérodromes, si : ils rendent QNH, température,
#  précipitation horaire et vent, en plaine, au même pas horaire que les
#  modèles. C'est la vérité terrain qui manquait aux trois variables
#  ajoutées le même jour.
#
#  ⚠️ CE FLUX N'EST PAS URGENT, ET IL FAUT LE SAVOIR. Contrairement aux
#  prévisions, l'archive METAR d'Iowa State est RÉTROACTIVE : on peut
#  redemander le 7 août dans deux ans. Il est collecté quand même pour
#  deux raisons honnêtes — ne pas dépendre d'un tiers qui pourrait
#  fermer, et rendre la donnée rejouable localement comme le reste.
#  Mais s'il tombe, il ne fait perdre RIEN d'irrattrapable : d'où le
#  `try/except` qui l'enveloppe dans `main()`, et sa place en dernier.
#
#  ⚠️ IL S'ÉCRIT DANS SA PROPRE CLÉ (`obsmetar/`), PAS DANS `obs/`.
#  Mélanger deux réseaux qui n'ont ni la même cadence, ni les mêmes
#  variables, ni la même géographie dans un fichier que `score.py` lit
#  déjà, c'était risquer de casser une notation qui marche pour une
#  donnée que personne ne note encore. Le jour où on notera la plaine,
#  on lira `obsmetar/` explicitement.

#: Les réseaux ASOS/METAR qui touchent France + limitrophes. Comptés le
#: 08/08 sur les geojson réels : FR 127, DE 92, GB 112, IT 108, ES 67,
#: NL 32, CH 20, BE 12, LU 1 — dont **278 dans la `BBOX`**, et **225
#: qui ont effectivement rendu des relevés** pour le 07/08.
#: `AD__ASOS` existe mais est VIDE (0 station) : gardé dans la liste
#: pour que personne ne le « redécouvre » et ne le rajoute en croyant
#: combler un trou.
METAR_NETWORKS = ["FR__ASOS", "CH__ASOS", "BE__ASOS", "LU__ASOS", "DE__ASOS",
                  "IT__ASOS", "ES__ASOS", "AD__ASOS", "GB__ASOS", "NL__ASOS"]
METAR_GEOJSON = "https://mesonet.agron.iastate.edu/geojson/network/{net}.geojson"
METAR_ASOS = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"

#: ⚠️ `alti` ET PAS `mslp` — SONDÉ LE 08/08, LA DOC AURAIT MENTI.
#: Sur 5 090 relevés réels du 07/08 : `mslp` rempli à **2 %**, `alti`
#: rempli à **100 %**. Les METAR européens diffusent le QNH (calage
#: altimétrique), pas la pression réduite au niveau de la mer au sens
#: SYNOP. Bâtir E6 sur `mslp` aurait donné une archive vide à 98 %.
#: Le QNH n'est pas exactement `pressure_msl` — il réduit en atmosphère
#: standard, pas avec la température du jour. L'écart est de l'ordre du
#: dixième d'hPa en plaine et grandit avec l'altitude du terrain : c'est
#: pour ça qu'on archive aussi `elev`, pour pouvoir corriger plus tard.
#: On archive la mesure, pas une correction — la correction se rejoue.
#:
#: Remplissage mesuré des autres champs, même jour : `tmpf` 100 %,
#: `sknt` 99 %, `drct` 83 %, `gust` **0,4 %** (une rafale n'est diffusée
#: que si elle existe — un champ vide veut dire « pas de rafale
#: signalée », pas « pas de mesure »).
#:
#: ⚠️⚠️ `p01i` — LA PRÉCIPITATION — A ÉTÉ RETIRÉE, ET C'EST LE RÉSULTAT
#: LE PLUS IMPORTANT DE LA SONDE DU 08/08. Le champ est SERVI À 100 %
#: pour les stations européennes… et vaut **0.00 partout, toujours**.
#: Mesuré, pas supposé :
#:
#:   | jeu                                  | valeurs | non nulles |
#:   |--------------------------------------|---------|------------|
#:   | janvier 2026, 4 stations FR          |   2 976 |     **0**  |
#:   | novembre 2025, 4 stations FR         |   2 880 |     **0**  |
#:   | novembre 2025, DEN + SEA (États-Unis)|   1 438 |     251    |
#:
#: Le groupe de précipitation horaire est une particularité ASOS
#: américaine ; le METAR européen ne le diffuse pas. Le champ « marche »
#: donc parfaitement — il rend un zéro sincère du point de vue du
#: format, et un mensonge du point de vue du sens.
#:
#: L'archiver aurait été le pire des cas : pas un trou visible, mais une
#: colonne pleine de `0.0` qu'on aurait relue dans six mois comme « il
#: n'a pas plu », et contre laquelle on aurait noté E4. Un modèle qui
#: prévoit 20 mm aurait été déclaré faux par une donnée qui n'existe pas.
#:
#: CONSÉQUENCE À RETENIR : **la vérité terrain d'E4 n'est PAS dans le
#: METAR.** Elle demande Météo-France (RADOME / pluviomètres), donc une
#: clé sur `portail-api.meteofrance.fr` — sondée le 08/08, elle répond
#: HTTP 401 sans clé, et l'ancien portail libre
#: `donneespubliques.meteofrance.fr` ne sert plus que du HTML.
#: Tant que la clé n'existe pas, on archive la PRÉVISION de
#: précipitation (elle, irréversible) sans sa vérification. C'est
#: cohérent : l'archive se rejoue, la vérité terrain se rebranche.
METAR_CHAMPS = ["drct", "sknt", "gust", "alti", "tmpf"]


def _get_text(url: str, timeout: int = 120) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": "balise-watch/model-verif"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def metar_stations(cache: pathlib.Path) -> list[dict]:
    """Le référentiel des aérodromes, avec cache sur disque.

    ⚠️ LE CACHE N'EST PAS UNE OPTIMISATION, C'EST LE FILET. Neuf appels
    à un service tiers en tête d'un flux facultatif : si Iowa State est
    en maintenance cette nuit-là, on collecte quand même avec le
    référentiel d'hier plutôt que de sauter la nuit. Un aérodrome n'ouvre
    pas tous les mois ; une liste vieille d'une semaine est juste.
    """
    stations, echecs = {}, []
    for net in METAR_NETWORKS:
        try:
            payload = json.loads(_get_text(METAR_GEOJSON.format(net=net), timeout=45))
        except Exception as exc:                       # noqa: BLE001
            echecs.append(f"{net} ({exc})")
            continue
        for s in payload.get("features") or []:
            coords = (s.get("geometry") or {}).get("coordinates") or []
            if len(coords) < 2:
                continue
            lon, lat = float(coords[0]), float(coords[1])
            if not (BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3]):
                continue
            props = s.get("properties") or {}
            stations[s["id"]] = {
                "id": s["id"], "source": "metar", "network": net,
                "lat": round(lat, 4), "lon": round(lon, 4),
                "elev": props.get("elevation"),
                "name": (props.get("sname") or "")[:60],
            }
    if echecs:
        print(f"  ⚠️  référentiel METAR incomplet — {', '.join(echecs)}",
              file=sys.stderr)
    if stations:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(sorted(stations.values(), key=lambda s: s["id"]),
                                    ensure_ascii=False, indent=1), encoding="utf-8")
        return list(stations.values())
    if cache.exists():
        anciennes = json.loads(cache.read_text(encoding="utf-8"))
        print(f"  ⚠️  aucun réseau joignable — on repart du cache "
              f"({len(anciennes)} aérodromes)", file=sys.stderr)
        return anciennes
    return []


def _f(v: str):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def metar_rows(stations: list[dict], day: str):
    """Une journée de METAR pour TOUS les aérodromes, en UNE requête.

    ⚠️ UNE SEULE REQUÊTE, ET C'EST MESURÉ : 278 stations, un jour
    complet, **2,1 s et 342 Ko** le 08/08. Le service accepte autant de
    paramètres `station=` qu'on veut (URL de 3 870 caractères, servie
    sans broncher). Boucler station par station aurait coûté 278
    requêtes pour la même donnée — c'est le genre de boucle qu'on écrit
    par réflexe et qui fait qu'un tiers gratuit finit par fermer la
    porte.

    Le débordement de 40 min appliqué à Pioupiou n'a pas lieu d'être
    ici : les METAR sont à l'heure ronde, il n'y a pas de fenêtre à
    moyenner. On prend la journée civile UTC, franche.

    Unités : le service rend des nœuds, des pouces de mercure, des
    degrés Fahrenheit et des pouces de pluie. On convertit À
    L'ÉCRITURE — une archive doit se relire sans table de conversion,
    et les modèles sont déjà demandés en km/h et °C.
    """
    if not stations:
        return
    par_id = {s["id"]: s for s in stations}
    debut = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    fin = debut + timedelta(days=1)
    q = [("year1", str(debut.year)), ("month1", str(debut.month)), ("day1", str(debut.day)),
         ("year2", str(fin.year)), ("month2", str(fin.month)), ("day2", str(fin.day)),
         ("tz", "UTC"), ("format", "onlycomma"), ("latlon", "yes"),
         ("missing", "empty"), ("trace", "0.0001"), ("report_type", "3")]
    q += [("data", c) for c in METAR_CHAMPS]
    q += [("station", sid) for sid in sorted(par_id)]
    txt = _get_text(f"{METAR_ASOS}?{urllib.parse.urlencode(q)}")

    lignes = txt.splitlines()
    if not lignes:
        return
    entete = lignes[0].split(",")
    try:
        col = {c: entete.index(c) for c in
               ("station", "valid", *METAR_CHAMPS)}
    except ValueError:
        # ⚠️ L'en-tête a changé de forme → on ABANDONNE au lieu de
        # deviner des positions de colonnes. Une archive vide est un
        # problème visible ; une archive décalée d'une colonne ne se
        # voit qu'au moment où on s'en sert.
        print(f"  ⚠️  en-tête METAR inattendu : {lignes[0][:120]} — "
              f"aucune ligne écrite", file=sys.stderr)
        return

    par_station: dict[str, dict] = {}
    for l in lignes[1:]:
        p = l.split(",")
        if len(p) != len(entete):
            continue
        sid = p[col["station"]]
        st = par_id.get(sid)
        if st is None:
            continue
        try:
            ts = int(datetime.strptime(p[col["valid"]], "%Y-%m-%d %H:%M")
                     .replace(tzinfo=timezone.utc).timestamp())
        except ValueError:
            continue
        r = par_station.setdefault(sid, {
            "station_id": sid, "source": "metar", "network": st["network"],
            "lat": st["lat"], "lon": st["lon"], "elev": st["elev"],
            "t": [], "speed": [], "gust": [], "dir": [],
            "qnh": [], "t2m": [],
        })
        kt, gkt = _f(p[col["sknt"]]), _f(p[col["gust"]])
        alti, tf = _f(p[col["alti"]]), _f(p[col["tmpf"]])
        r["t"].append(ts)
        r["speed"].append(round(kt * 1.852, 1) if kt is not None else None)
        r["gust"].append(round(gkt * 1.852, 1) if gkt is not None else None)
        r["dir"].append(_f(p[col["drct"]]))
        # 1 inHg = 33,8639 hPa ; °C = (°F − 32) × 5/9.
        r["qnh"].append(round(alti * 33.8639, 2) if alti is not None else None)
        r["t2m"].append(round((tf - 32.0) * 5.0 / 9.0, 1) if tf is not None else None)

    for r in par_station.values():
        # Même règle que pour les prévisions : une station qui n'a rien
        # mesuré ne rentre pas dans l'archive sous forme de nulls.
        if all(v is None for v in r["speed"]) and all(v is None for v in r["qnh"]):
            continue
        yield r


# ══════════════════════════════════════════════════════════════════
#  OBSERVATIONS WINDSMOBI (vent, seize réseaux agrégés) — S0.2, 21/08
# ══════════════════════════════════════════════════════════════════
#
#  Ce flux vient du cadrage `claude/lot-s0-cadrage-reseaux-21-08.md` :
#  848 balises neuves, dont 572 dans les Alpes et 337 au-dessus de
#  1 500 m — la seule population qui puisse dire si « aucun modèle ne
#  bat la climatologie » (0/27 lignes massif Alpes du Nord) parle des
#  modèles ou des balises.
#
#  ⛔ CADENCE : NOCTURNE, ET C'EST UN ARBITRAGE ROUVERT LE 21/08.
#  La note de cadrage recommandait UNE PASSE PAR SEMAINE (848
#  appels/semaine, −86 % contre un rythme nocturne) précisément pour
#  ménager winds.mobi : CGU « Do not overload… », blacklistage SANS
#  PRÉAVIS, monétisation interdite. Yann a rouvert cet arbitrage le
#  21/08 et choisi la cadence nocturne — ~5 936 appels/semaine (×7) —
#  en connaissance du risque. Ce choix est ASSUMÉ, pas un oubli.
#
#  ⛔ CONTRAINTES NON NÉGOCIABLES (CGU sondées le 07/08, RESEAU_WINDSMOBI.md) :
#    - user-agent identifiant OBLIGATOIRE sur CHAQUE appel (WINDSMOBI_UA) ;
#    - AUCUNE RAFALE : les appels par balise sont séquentiels, avec
#      une pause (BATCH_PAUSE_S) — jamais de parallélisme ;
#    - IL N'EXISTE PAS D'APPEL GROUPÉ POUR L'HISTORIQUE — mesuré au
#      cadrage. Un appel par balise est la seule voie.
#
#  ⚠️ AUCUNE PRESSION, JAMAIS. Mesuré au cadrage : les 16 réseaux
#  sources ne disent pas leur convention de réduction. Les champs
#  `pres_hpa`/`pres_kind` du schéma de décision 1 sont donc OMIS des
#  lignes windsmobi plutôt que remplis de `None` en boucle — un champ
#  absent dit « sans objet », une colonne de `None` se relirait un jour
#  comme une collecte manquée.
#
#  ⚠️ AUCUN DÉDOUBLONNAGE À L'ARCHIVAGE (décision 2 du cadrage). Les
#  ~305 doublons FFVL/Pioupiou à moins de 180 m sont écartés côté ÉCRAN
#  (`windsmobiIsDuplicate` dans index.js) parce qu'un marqueur en double
#  y est une régression. Côté archive, deux capteurs à 50 m qui mesurent
#  différemment sont une information : c'est la matière du S3.

WINDSMOBI_API = "https://winds.mobi/api/2"
WINDSMOBI_UA = "balise-watch.app (biozarb@gmail.com)"
#: Mêmes seize réseaux que `refreshWindsmobiProviders` (index.js) —
#: copie assumée, comme `tools/sonde_windsmobi.mjs` le fait déjà : si
#: quelqu'un change cette liste côté serveur sans toucher collect.py,
#: l'archive divergera silencieusement de ce que l'app affiche. À
#: vérifier à l'œil si les deux s'écartent d'un coup.
WINDSMOBI_PROVIDERS_FAST = ["holfuy", "ffvl"]
WINDSMOBI_PROVIDERS_SLOW = [
    "slf", "meteoswiss", "windspots", "aletsch", "windball", "windline",
    "iweathar", "pgsonda", "gxaircom", "pdcs", "yvbeach", "thunerwetter",
    "kachelmannwetter", "wunderground",
]
WINDSMOBI_PROVIDERS = WINDSMOBI_PROVIDERS_FAST + WINDSMOBI_PROVIDERS_SLOW

#: Durée d'historique redemandée à CHAQUE appel nocturne, en secondes.
#: ⚠️ CHOIX D'IMPLÉMENTATION, PAS UN ARBITRAGE DE YANN — lui a tranché
#: nocturne vs hebdomadaire (cadence), pas la durée par appel (payload).
#: 48 h et pas les 604 800 s (7 j) de la version hebdomadaire d'origine :
#: la cadence nocturne n'a plus qu'à couvrir la nuit ratée d'avant, pas
#: une semaine entière — demander 7 j chaque nuit multiplierait le
#: payload par ~28 sans changer le nombre d'appels, ce que rien dans
#: l'arbitrage du 21/08 ne demandait. 48 h reprend l'ordre de grandeur
#: déjà choisi pour la marge MF/AEMET (§1.4 du cadrage). À raccourcir si
#: la charge s'avère un problème mesuré, à rallonger si des nuits
#: manquées se révèlent fréquentes — mais alors le dire à Yann, ce n'est
#: plus un détail d'implémentation.
WINDSMOBI_HISTORY_DURATION_S = 48 * 3600

#: Profondeur maximale que winds.mobi accepte de rendre par balise
#: (`?duration=…`), mesurée le 07/08 sur `ffvl-2820` : 937 points sur
#: 168,0 h pile. Même constante que `WINDSMOBI_HISTORY_MAX_H` d'index.js
#: — sert ICI de garde-fraîcheur du référentiel (§ ci-dessous dans
#: `windsmobi_stations`) : au-delà, l'historique d'une station ne
#: rentrerait de toute façon dans aucune fenêtre de 48 h demandée.
WINDSMOBI_HISTORY_MAX_H = 168


def _get_json_windsmobi(path: str, timeout: int = 60):
    """GET sur l'API windsmobi, AVEC le user-agent obligatoire.

    ⚠️ Pas `_get_json` : ce garde-fou-là est pour Open-Meteo (piège du
    `{"error": true}` en HTTP 200). windsmobi a son propre risque — le
    blacklistage sans préavis d'une IP qui ne s'identifie pas — d'où un
    header dédié plutôt qu'un paramètre optionnel sur la fonction
    générique, pour qu'un appel windsmobi sans user-agent soit
    impossible à écrire par erreur.
    """
    req = urllib.request.Request(f"{WINDSMOBI_API}{path}",
                                 headers={"user-agent": WINDSMOBI_UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def windsmobi_stations(cache: pathlib.Path) -> list[dict]:
    """Le référentiel des balises windsmobi, avec cache sur disque.

    SEIZE appels (`/stations/?provider=<p>&limit=0`), un par réseau —
    pas 848 : celui-ci ne demande que position et dernier relevé, pas
    l'historique. Même filet que `metar_stations` : un réseau injoignable
    ne fait pas tomber le run, et le cache d'hier prend le relais si
    aucun des seize ne répond.

    Filtré sur la MÊME `BBOX` que le reste de collect.py — PAS
    `WINDSMOBI_BOX` d'index.js, plus large, qui sert l'écran et pas
    l'archive. C'est la `BBOX` de collect.py que le cadrage du 21/08 a
    mesurée (901 balises en boîte, 848 neuves).

    Les stations `red`/`hidden` ou n'ayant jamais mesuré de vent
    (`last['w-avg']` absent) sont écartées : pas un dédoublonnage, un
    filtre de vivacité — leur historique ne rendrait que des lignes
    vides, comme `refreshWindsmobiProviders` le fait déjà côté serveur.

    ⛔ **Garde-fraîcheur ajoutée le 21/08 (suite session, cf. §9 du
    cadrage) — écarte les stations mortes DEPUIS LONGTEMPS.** Mesuré ce
    jour-là : le référentiel brut (identique au filtre ci-dessus, SANS
    cette garde) rend 1283 stations contre 901 au cadrage S0.1, quelques
    heures plus tôt. Investigué et **pour l'essentiel PAS expliqué par
    la fraîcheur** : seules 50 stations sur 1283 ont un dernier relevé
    de plus de 60 min (le seuil `WINDSMOBI_OBS_MAX_AGE_MS` de l'app), et
    37 de plus de 24 h — l'écart réel (~382) tient surtout à la
    RESPIRATION du réseau au fil de la journée (mesure 12h40 vs
    fin d'après-midi), la même que celle déjà documentée pour Infoclimat
    (§1.2 du cadrage : 548 puis 572 en dix minutes). Ce n'est donc PAS
    une correction du chiffre, juste l'écartement des entrées VRAIMENT
    abandonnées : au-delà de `WINDSMOBI_HISTORY_MAX_H` (168 h, 7 jours —
    la même constante qu'index.js pour la profondeur d'historique
    winds.mobi), leur historique ne rentrerait de toute façon dans
    aucune fenêtre de 48 h qu'on leur redemande. Mesuré : 15 stations
    sur 1283 dans ce cas le 21/08.
    """
    stations, echecs = {}, []
    now = time.time()
    for provider in WINDSMOBI_PROVIDERS:
        try:
            rows = _get_json_windsmobi(f"/stations/?provider={provider}&limit=0")
        except Exception as exc:                       # noqa: BLE001
            echecs.append(f"{provider} ({exc})")
            continue
        if not isinstance(rows, list):
            echecs.append(f"{provider} (réponse inattendue)")
            continue
        for s in rows:
            coords = ((s.get("loc") or {}).get("coordinates")) or []
            if len(coords) < 2:
                continue
            lon, lat = float(coords[0]), float(coords[1])
            if not (BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3]):
                continue
            if s.get("status") in ("red", "hidden"):
                continue
            last = s.get("last") or {}
            if last.get("w-avg") is None:
                continue
            derniere_ts = last.get("_id")
            if isinstance(derniere_ts, (int, float)) and (now - derniere_ts) > WINDSMOBI_HISTORY_MAX_H * 3600:
                continue
            sid = s.get("_id")
            if sid is None:
                continue
            stations[sid] = {
                "id": str(sid), "source": "windsmobi", "network": provider,
                "lat": round(lat, 4), "lon": round(lon, 4),
                "elev": s.get("alt"),
                "name": (s.get("name") or s.get("short") or str(sid))[:60],
            }
    if echecs:
        print(f"  ⚠️  référentiel windsmobi incomplet — {', '.join(echecs)}",
              file=sys.stderr)
    if stations:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(sorted(stations.values(), key=lambda s: s["id"]),
                                    ensure_ascii=False, indent=1), encoding="utf-8")
        return list(stations.values())
    if cache.exists():
        anciennes = json.loads(cache.read_text(encoding="utf-8"))
        print(f"  ⚠️  aucun réseau windsmobi joignable — on repart du cache "
              f"({len(anciennes)} balises)", file=sys.stderr)
        return anciennes
    return []


def windsmobi_historic(station_id: str) -> list | None:
    """Un appel : l'historique d'UNE balise, `WINDSMOBI_HISTORY_DURATION_S`
    de recul depuis maintenant. Pas d'appel groupé possible — mesuré au
    cadrage du 21/08.
    """
    path = f"/stations/{urllib.parse.quote(station_id, safe='')}/historic/?duration={WINDSMOBI_HISTORY_DURATION_S}"
    try:
        rows = _get_json_windsmobi(path, timeout=30)
    except Exception as exc:                           # noqa: BLE001
        print(f"  ⚠️ windsmobi historic {station_id} : {exc}", file=sys.stderr)
        return None
    return rows if isinstance(rows, list) else None


def windsmobi_rows(stations: list[dict], day: str):
    """Une journée de windsmobi, un appel PAR BALISE, séquentiel.

    ⚠️ AUCUNE RAFALE : `BATCH_PAUSE_S` entre deux appels, la même pause
    que pour Pioupiou — winds.mobi n'a pas de quota chiffré au-delà de
    « ne pas surcharger », donc on reprend la prudence déjà choisie pour
    un autre tiers gratuit plutôt que d'inventer un chiffre.

    winds.mobi rend l'historique le plus RÉCENT en premier et horodate
    en SECONDES (`_id`) — on retrie par `t` croissant, et on ne garde
    que les points tombant dans la journée civile UTC demandée : l'appel
    ramène `WINDSMOBI_HISTORY_DURATION_S` de recul depuis MAINTENANT,
    pas une fenêtre calée sur `day`.

    Vitesse et rafale sont DÉJÀ en km/h — vérifié par
    `tools/sonde_windsmobi.mjs` (comparaison à 39 balises Pioupiou vues
    des deux côtés, à l'horodatage identique) : aucune conversion.

    ⛔ Aucun champ `pres_hpa`/`pres_kind` — cf. l'en-tête de section.
    """
    if not stations:
        return
    debut = int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    fin = debut + 86400
    for i, st in enumerate(stations, 1):
        rows = windsmobi_historic(st["id"])
        time.sleep(BATCH_PAUSE_S)
        if not rows:
            continue
        t, speed, gust, direction = [], [], [], []
        for p in rows:
            ts = p.get("_id") if isinstance(p, dict) else None
            if not isinstance(ts, (int, float)):
                continue
            ts = int(ts)
            if ts < debut or ts >= fin:
                continue
            t.append(ts)
            speed.append(p.get("w-avg"))
            gust.append(p.get("w-max"))
            direction.append(p.get("w-dir"))
        if not t or all(v is None for v in speed):
            continue
        order = sorted(range(len(t)), key=lambda k: t[k])
        yield {
            "station_id": st["id"], "source": "windsmobi", "network": st["network"],
            "lat": st["lat"], "lon": st["lon"], "elev": st["elev"],
            "t": [t[k] for k in order],
            "speed": [speed[k] for k in order],
            "gust": [gust[k] for k in order],
            "dir": [direction[k] for k in order],
        }
        if i % 50 == 0:
            print(f"  … {i}/{len(stations)}")


# ══════════════════════════════════════════════════════════════════
#  OBSERVATIONS INFOCLIMAT (vent + pression) — S0.2, 21/08, session 2
# ══════════════════════════════════════════════════════════════════
#
#  Ce flux vient du cadrage `claude/lot-s0-cadrage-reseaux-21-08.md` :
#  539 pressions à 10 min — le seul réseau non archivé qui en serve —
#  et 550 balises de plaine (la population « sans relief » du S3).
#
#  ⛔ ZÉRO APPEL CHEZ L'ASSOCIATION. Ce flux lit DEUX choses, ni l'une
#  ni l'autre n'est un appel à `infoclimat.fr` :
#    1. Le référentiel des stations — le MÊME GeoJSON public que lit
#       déjà `traces/infoclimat/poller_infoclimat.py::charger_stations`
#       (data.gouv.fr, aucune clé requise) ;
#    2. `infoclimat/history.json` — NOTRE PROPRE objet R2, écrit par le
#       poller toutes les `HISTORY_INTERVAL_MIN` (30 min). Le poller a
#       déjà fait le travail chez l'association ; on ne fait que relire
#       ce qu'il a écrit.
#
#  ⚠️ URL PUBLIQUE, PAS `tools/storage.py`. Les deux objets Infoclimat
#  sont servis en lecture publique par le domaine r2.dev — EXACTEMENT
#  l'URL qu'`index.js` lit déjà côté serveur (`INFOCLIMAT_HISTORY_URL`).
#  Passer par `Storage`/boto3 aurait fallu contourner `run.sh`, qui
#  FORCE `R2_BUCKET=model-verif` pour ce job — et l'objet Infoclimat vit
#  dans le bucket `balise-watch-packs` (cf. le piège déjà documenté et
#  déjoué dans `agrume_fcst.bucket_r2`). La route publique n'a pas ce
#  problème, et ne consomme aucun identifiant.
#
#  ⚠️ FENÊTRE DE 30 H, PAS 48 H COMME windsmobi — MESURÉ, PAS SUPPOSÉ.
#  `poller_infoclimat.py` accumule un historique GLISSANT de
#  `HISTORY_HEURES = 30` dans son propre état, réécrit sur R2 toutes
#  les 30 min. Un run de collecte qui tombe dans les six premières
#  heures UTC du jour suivant (03 h 15, notre cas) couvre la totalité
#  de la veille avec ~3 h de marge ; au-delà, une partie de la journée
#  manquerait EN SILENCE. C'est le sens du §1.4 du cadrage : « chaque
#  nuit ou pas du tout ».
#
#  ⚠️ `raf` (rafale) N'EXISTE QUE SUR ~4 % DES STATIONS — mesuré en
#  direct le 21/08 sur l'objet réel : 31 stations sur 872. Le champ est
#  quand même TOUJOURS écrit (comme pour METAR), avec `None` là où il
#  n'y a pas de mesure — jamais reconstruit depuis la moyenne.
#
#  ⚠️ `pres_kind = "qff"`, CONSTANT — mesuré au cadrage (§1.5) : la
#  pression Infoclimat est déjà réduite au niveau de la mer et colle en
#  médiane au QFF Météo-France (−0,10 hPa sous 500 m, +0,20 entre 500 et
#  1 500 m), mais avec un écart-type de 2,60 hPa — la dispersion de
#  calage des baromètres amateurs. C'est ce qui, au S1, écartera
#  Infoclimat de `pres_err_med` et ne gardera que `ptend_err_med`. Ici
#  on archive la MESURE BRUTE, jamais une décision de notation.
#
#  ⚠️ `licence_code` VOYAGE PAR STATION (décision 1 du cadrage) : 1
#  (`CC BY`) ou 2 (`NON-COMMERCIAL ONLY: CC BY NC`), à peu près
#  moitié-moitié sur le parc. On archive tout ; le tri par licence, s'il
#  doit exister, se fera à la lecture — jamais à l'archivage.

INFOCLIMAT_STATIONS_GEOJSON = ("https://www.data.gouv.fr/api/1/datasets/r/"
                               "8a9e6a12-03f8-4056-861f-70b84136313e")
#: ⚠️ MÊME URL PUBLIQUE QU'`index.js` (`INFOCLIMAT_R2_BASE`, l. ~2644) —
#: recopiée à dessein plutôt que lue depuis un fichier partagé : les
#: deux runtimes (Render en JS, ce script en Python sur le VPS) n'ont
#: aucun module commun. Si Yann change le domaine personnalisé un jour,
#: les deux constantes divergeront en silence — à vérifier à l'œil si
#: le flux s'arrête sans raison apparente.
INFOCLIMAT_R2_BASE = (os.environ.get("INFOCLIMAT_R2_BASE")
                      or "https://pub-14b7b6ffdba34729b51280359c8f2c01.r2.dev")
INFOCLIMAT_HISTORY_URL = f"{INFOCLIMAT_R2_BASE}/infoclimat/history.json"
#: Mesuré au cadrage (§1.5) — cf. l'en-tête de section.
INFOCLIMAT_PRES_KIND = "qff"


def _get_json_infoclimat(url: str, timeout: int = 60):
    req = urllib.request.Request(url, headers={"User-Agent": "balise-watch/model-verif"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def infoclimat_stations(cache: pathlib.Path) -> list[dict]:
    """Le référentiel des stations Infoclimat StatIC, avec cache disque.

    UN appel — le GeoJSON public de data.gouv.fr, PAS l'API Infoclimat.
    Même filet que `metar_stations`/`windsmobi_stations` : une panne de
    data.gouv.fr cette nuit-là ne fait pas sauter la nuit, le cache
    d'hier prend le relais (une station Infoclimat n'ouvre pas tous les
    mois).

    Filtré sur la MÊME `BBOX` que le reste de collect.py — mesuré le
    21/08 : 1 145 stations Infoclimat dans la `BBOX` sur les 1 212 que
    sert le GeoJSON complet (StatIC seul — les entrées `METEO-FRANCE`
    du même fichier sont déjà couvertes par `mf`, jamais dédoublées ici
    non plus qu'ailleurs dans ce script).
    """
    try:
        geo = _get_json_infoclimat(INFOCLIMAT_STATIONS_GEOJSON, timeout=60)
    except Exception as exc:                           # noqa: BLE001
        geo = None
        print(f"  ⚠️  référentiel infoclimat (data.gouv.fr) injoignable : {exc}",
              file=sys.stderr)

    stations = {}
    if isinstance(geo, dict):
        for feat in geo.get("features") or []:
            props = feat.get("properties") or {}
            coords = (feat.get("geometry") or {}).get("coordinates") or []
            if len(coords) < 2 or not props.get("id"):
                continue
            lic = props.get("license") or {}
            # Ne garder que le réseau Infoclimat (StatIC) : les entrées
            # `METEO-FRANCE` du même GeoJSON sont déjà notre `mf`.
            if lic.get("source") != "infoclimat.fr":
                continue
            lon, lat = float(coords[0]), float(coords[1])
            if not (BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lon <= BBOX[3]):
                continue
            sid = str(props["id"])
            stations[sid] = {
                "id": sid, "source": "infoclimat",
                "lat": round(lat, 4), "lon": round(lon, 4),
                "elev": props.get("elevation"),
                "licence_code": lic.get("code"),
            }
    if stations:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(sorted(stations.values(), key=lambda s: s["id"]),
                                    ensure_ascii=False, indent=1), encoding="utf-8")
        return list(stations.values())
    if cache.exists():
        anciennes = json.loads(cache.read_text(encoding="utf-8"))
        print(f"  ⚠️  référentiel infoclimat injoignable — on repart du cache "
              f"({len(anciennes)} stations)", file=sys.stderr)
        return anciennes
    return []


def infoclimat_rows(stations: list[dict], day: str):
    """Une journée d'Infoclimat, LUE UNE SEULE FOIS depuis NOTRE objet R2
    `infoclimat/history.json` — cf. l'en-tête de section pour pourquoi
    ce n'est ni un appel chez l'association ni un passage par `Storage`.

    Format colonnaire de la source (`corps_history` dans
    `poller_infoclimat.py`) : chaque station porte des tableaux ALIGNÉS
    sur `t`, une série entièrement nulle est absente du dict plutôt que
    remplie de `null`. On reproduit la même discipline à l'écriture :
    `gust`/`pres_hpa` sont TOUJOURS présents sur la ligne archivée
    (comme pour METAR), avec `None` aux positions où la série source
    est absente — jamais un champ qui disparaît selon la station.
    """
    if not stations:
        return
    par_id = {s["id"]: s for s in stations}
    try:
        doc = _get_json_infoclimat(INFOCLIMAT_HISTORY_URL, timeout=60)
    except Exception as exc:                           # noqa: BLE001
        print(f"  ⚠️ infoclimat history.json injoignable : {exc}", file=sys.stderr)
        return
    if not isinstance(doc, dict):
        return
    hist = doc.get("historique")
    if not isinstance(hist, dict):
        return

    debut = int(datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())
    fin = debut + 86400

    for sid, serie in hist.items():
        st = par_id.get(sid)
        if st is None:
            continue                      # hors BBOX, ou hors référentiel
        t_all = serie.get("t") if isinstance(serie, dict) else None
        if not isinstance(t_all, list):
            continue
        idx = [i for i, ts in enumerate(t_all)
              if isinstance(ts, (int, float)) and debut <= ts < fin]
        if not idx:
            continue

        def colonne(champ, _serie=serie, _idx=idx):
            vals = _serie.get(champ)
            if not isinstance(vals, list):
                return [None] * len(_idx)
            return [vals[i] if i < len(vals) else None for i in _idx]

        speed = colonne("moy")
        if all(v is None for v in speed):
            continue
        yield {
            "station_id": sid, "source": "infoclimat",
            "lat": st["lat"], "lon": st["lon"], "elev": st["elev"],
            "t": [t_all[i] for i in idx],
            "speed": speed,
            "gust": colonne("raf"),
            "dir": colonne("dir"),
            "pres_hpa": colonne("pres"),
            "pres_kind": INFOCLIMAT_PRES_KIND,
            "licence_code": st["licence_code"],
        }


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


R2OK_SUFFIXE = ".r2ok"


def temoin(path: pathlib.Path) -> pathlib.Path:
    """Le témoin d'envoi, posé à côté de l'objet qu'il décrit.

    Un fichier plutôt qu'un index : il ne peut pas se désynchroniser de
    l'objet, il survit à un arrêt brutal au milieu du run, et il se
    répare d'un `rm` le jour où l'on doute de lui.
    """
    return pathlib.Path(str(path) + R2OK_SUFFIXE)


def upload_r2(path: pathlib.Path, key: str) -> bool:
    """Dépose sur R2 via `tools/storage.py`, et pose son témoin.

    ⚠️ CE QUI A CHANGÉ LE 07/08/2026, ET POURQUOI. Cette fonction rendait
    déjà ce booléen, et les deux appelants le JETAIENT — au motif, écrit
    ici, que « faire échouer le run parce que l'envoi distant a échoué
    reviendrait à préférer aucune archive à une archive locale ».

    L'argument est juste pour ce qu'il défend : on ne jette pas le
    fichier local, et on ne le jette toujours pas. Mais il ne justifiait
    pas d'ANNONCER UN SUCCÈS. Constaté au premier essai réel sur le VPS :
    le jeton R2 n'avait pas droit au bucket `model-verif`, `PutObject`
    rendait `AccessDenied`, et le run sortait en 0. Healthchecks serait
    passé au vert sur une nuit dont l'archive irremplaçable n'existait
    que sur le disque d'une machine que personne ne sauvegarde — le
    « garde-fou qui vérifie la forme et pas le contenu » du §11, à
    l'intérieur même du dispositif censé garder.

    Désormais : le local reste, le témoin n'est pas posé, `main` le voit
    et sort en erreur, et `rattraper()` réessaiera la nuit suivante.
    """
    # ⚠️ LE TÉMOIN D'UN ENVOI PRÉCÉDENT MEURT AVANT QU'ON RETENTE, et
    # c'est la première chose que fait cette fonction. L'objet local a
    # pu être RÉÉCRIT depuis (le run complet remplace l'essai à cinq
    # points) : un témoin périmé affirmerait que la nouvelle version est
    # montée alors qu'elle ne l'est pas, et `en_retard()` la laisserait
    # passer. Vu le 07/08 en comparant les horodatages — témoin de
    # 09:36, archive de 09:42. Le témoin dit « ce contenu-ci est parti »,
    # pas « ce chemin a servi un jour ».
    temoin(path).unlink(missing_ok=True)

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
        temoin(path).write_text(
            datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + "\n",
            encoding="utf-8")
        return True
    except Exception as exc:                            # noqa: BLE001
        print(f"  ⚠️  envoi R2 échoué (archive locale conservée, "
              f"rattrapage au prochain run) : {exc}", file=sys.stderr)
        return False


def en_retard(out: pathlib.Path) -> list[pathlib.Path]:
    """Les archives locales qui ne sont jamais montées sur R2."""
    return sorted(p for p in out.rglob("*.ndjson.gz") if not temoin(p).exists())


def rattraper(out: pathlib.Path, plafond: int = 30) -> None:
    """Réessaie l'envoi des archives restées au sol.

    ⚠️ Sans cette reprise, corriger la cause d'un échec ne ramènerait PAS
    les nuits déjà collectées : un run n'écrit que la journée du jour, et
    personne ne repasse derrière. Le fichier serait « conservé
    localement » à perpétuité, ce qui est une autre façon de le perdre —
    un disque de VPS n'est pas une archive.

    Tourne AVANT la collecte du jour, pour que l'objet du jour soit
    ensuite réécrit par le run complet et non par un reliquat partiel.
    """
    retard = en_retard(out)
    if not retard:
        return
    print(f"▶ rattrapage : {len(retard)} archive(s) locale(s) jamais montée(s)")
    # Un plafond, parce qu'un an de panne ferait mille envois d'un coup —
    # mais un plafond qui se TAIT ferait croire à une reprise complète.
    lot, reste = retard[:plafond], retard[plafond:]
    envoyes = sum(1 for p in lot if upload_r2(p, p.relative_to(out).as_posix()))
    print(f"  {envoyes}/{len(lot)} rattrapée(s)")
    if reste:
        print(f"  ⓘ {len(reste)} laissée(s) pour le prochain run (plafond {plafond})")


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
    ap.add_argument("--skip-metar", action="store_true",
                    help="saute les observations d'aérodrome (flux rattrapable)")
    ap.add_argument("--skip-windsmobi", action="store_true",
                    help="saute les observations windsmobi (rétroactif 48h chez la source)")
    ap.add_argument("--skip-infoclimat", action="store_true",
                    help="saute les observations infoclimat (rétroactif 30h chez NOUS, pas la source)")
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

    # ── 0. RATTRAPAGE ────────────────────────────────────────────
    # Avant tout le reste : si une nuit précédente n'a pas pu monter son
    # archive, c'est maintenant qu'on la pousse, pendant qu'on a encore
    # le fichier.
    rattraper(out)

    # ── 1. PRÉVISIONS ────────────────────────────────────────────
    # En premier, et c'est délibéré : c'est la partie non rattrapable.
    # Les observations Pioupiou, elles, restent lisibles des mois plus
    # tard dans l'archive publique.
    if not args.skip_forecast:
        key = f"fcst/{now:%Y/%m}/fcst_{today}.ndjson.gz"
        path = out / key
        print(f"▶ prévisions : {len(stations)} points × {len(MODELS)} modèles → {path}")
        failed = 0

        # ⚠️ LE SEAU EST CONSTRUIT ICI, PAS DANS LA BOUCLE : c'est lui
        # qui porte le compte, et un seau reconstruit à chaque point
        # relirait l'état 648 fois pour rien.
        qm = charger_quota()
        budget = qm.Budget("collect") if qm else None
        # ⚠️ POIDS DÉRIVÉ, JAMAIS RECOPIÉ. Si quelqu'un ajoute demain une
        # variable ou un modèle, ce calcul suit ; un `8` en dur, non.
        poids_point = (qm.poids(len(_hourly_vars()), len(MODELS))
                       if qm else None)
        refuses = 0

        def _fcst_rows():
            nonlocal failed, refuses
            for i, st in enumerate(stations, 1):
                # Le droit de parler AVANT de parler. En dégradé comme
                # en nominal, `demander` rend la main quand c'est l'heure.
                if budget is not None:
                    try:
                        budget.demander(
                            poids_point,
                            etiquette=f"{st['lat']:.3f},{st['lon']:.3f}")
                    except qm.BudgetRefuse as exc:
                        # ⚠️ TROU DÉCLARÉ, JAMAIS COMBLÉ. Un point non
                        # collecté se dit ; il ne s'interpole pas, et il
                        # ne fait pas non plus tuer le run par le chien
                        # de garde — c'était la mort du 09/08.
                        print(f"  ⛔ {exc}", file=sys.stderr)
                        refuses += 1
                        failed += 1
                        continue
                else:
                    # Module absent : cadence conservatrice d'avant le
                    # lot, celle qui a tenu le 08/08.
                    time.sleep(0.70)

                payload = fetch_forecast(st["lat"], st["lon"], args.forecast_days)
                if payload is None:
                    failed += 1
                else:
                    yield from forecast_rows(st, payload, fetched_at)
                if i % 50 == 0:
                    print(f"  … {i}/{len(stations)} ({failed} échecs)")

        n = write_ndjson_gz(path, _fcst_rows())
        print(f"✅ {n} lignes, {failed} points en échec "
              f"(dont {refuses} refusés par le quota), "
              f"{path.stat().st_size / 1024:.0f} Ko")
        # ⚠️ LA LIGNE QUI NOMME LES CONSOMMATEURS. Un budget partagé qui
        # ne dit pas QUI a consommé QUOI déplace le problème au lieu de
        # le résoudre : quand la collecte échouera, on doit pouvoir lire
        # « day_features a pris 4 000 unités entre 05:12 et 05:31 » et
        # non « quelque chose a dépassé ».
        if budget is not None:
            print(f"ⓘ {budget.resume()}")
            for nom_f, info in budget.etat()["fenetres"].items():
                if info["par_consommateur"]:
                    detail = ", ".join(f"{q} {v:.0f}" for q, v
                                       in info["par_consommateur"].items())
                    print(f"   {nom_f:<7} {info['consomme']:>6.0f}/"
                          f"{info['plafond']:<6} — {detail}")
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

    # ── 2 bis. OBSERVATIONS METAR (aérodromes) ───────────────────
    # ⚠️ EN DERNIER, ET SOUS FILET. Ce flux est le seul du script dont
    # la perte se rattrape (l'archive d'Iowa State est rétroactive). Il
    # ne doit donc JAMAIS pouvoir faire tomber ce qui le précède : une
    # exception ici se journalise et ne change pas le code de sortie.
    # L'inverse — mettre en péril une nuit de prévisions pour une
    # donnée qu'on peut redemander dans deux ans — serait absurde.
    if not args.skip_metar:
        try:
            d = datetime.strptime(obs_day, "%Y-%m-%d")
            key = f"obsmetar/{d:%Y/%m}/obsmetar_{obs_day}.ndjson.gz"
            path = out / key
            aeros = metar_stations(out / "metar_stations.json")
            print(f"▶ METAR du {obs_day} : {len(aeros)} aérodromes → {path}")
            n = write_ndjson_gz(path, metar_rows(aeros, obs_day))
            print(f"✅ {n} aérodromes servis sur {len(aeros)}, "
                  f"{path.stat().st_size / 1024:.0f} Ko")
            upload_r2(path, key)
        except Exception as exc:                       # noqa: BLE001
            print(f"⚠️ passe METAR abandonnée ({exc!r}) — flux rattrapable, "
                  f"le reste du run n'est pas affecté", file=sys.stderr)

    # ── 2 ter. OBSERVATIONS WINDSMOBI ─────────────────────────────
    # ⚠️ NOCTURNE depuis le 21/08 (arbitrage rouvert par Yann) — voir
    # l'en-tête de section pour ce que ça coûte et pourquoi c'est assumé.
    # Comme METAR : un échec ici ne doit jamais faire tomber le run,
    # c'est un ajout et non une brique dont dépend le score actuel.
    if not args.skip_windsmobi:
        try:
            d = datetime.strptime(obs_day, "%Y-%m-%d")
            key = f"obswindsmobi/{d:%Y/%m}/obswindsmobi_{obs_day}.ndjson.gz"
            path = out / key
            balises = windsmobi_stations(out / "windsmobi_stations.json")
            if args.limit:
                balises = balises[: args.limit]
            print(f"▶ windsmobi du {obs_day} : {len(balises)} balises → {path}")
            n = write_ndjson_gz(path, windsmobi_rows(balises, obs_day))
            print(f"✅ {n} balises servies sur {len(balises)}, "
                  f"{path.stat().st_size / 1024:.0f} Ko")
            upload_r2(path, key)
        except Exception as exc:                       # noqa: BLE001
            print(f"⚠️ passe windsmobi abandonnée ({exc!r}) — flux rattrapable "
                  f"48h, le reste du run n'est pas affecté", file=sys.stderr)

    # ── 2 quater. OBSERVATIONS INFOCLIMAT (vent + pression) ───────
    # ⚠️ Comme METAR et windsmobi : un échec ici ne fait jamais tomber
    # le run. Contrairement à windsmobi (48h chez la SOURCE), la fenêtre
    # infoclimat n'est que de 30h et chez NOUS (notre propre historique
    # R2) — cf. l'en-tête de section : une nuit manquée n'est
    # rattrapable que de justesse, jamais au-delà.
    if not args.skip_infoclimat:
        try:
            d = datetime.strptime(obs_day, "%Y-%m-%d")
            key = f"obsinfoclimat/{d:%Y/%m}/obsinfoclimat_{obs_day}.ndjson.gz"
            path = out / key
            stations_ic = infoclimat_stations(out / "infoclimat_stations.json")
            if args.limit:
                stations_ic = stations_ic[: args.limit]
            print(f"▶ infoclimat du {obs_day} : {len(stations_ic)} stations → {path}")
            n = write_ndjson_gz(path, infoclimat_rows(stations_ic, obs_day))
            print(f"✅ {n} stations servies sur {len(stations_ic)}, "
                  f"{path.stat().st_size / 1024:.0f} Ko")
            upload_r2(path, key)
        except Exception as exc:                       # noqa: BLE001
            print(f"⚠️ passe infoclimat abandonnée ({exc!r}) — flux rattrapable "
                  f"30h (chez nous), le reste du run n'est pas affecté",
                  file=sys.stderr)

    # ── 3. L'ARCHIVE EST-ELLE VRAIMENT À L'ABRI ? ─────────────────
    # Une seule règle, en fin de run, plutôt qu'un test à chaque envoi :
    # elle couvre du même geste l'objet du jour et le retard accumulé, et
    # elle ne peut pas se désynchroniser des appelants.
    #
    # ⚠️ C'EST CE CONTRÔLE QUI MANQUAIT. Sans lui, un run pouvait sortir
    # en 0 avec une archive qui n'existait que sur ce disque.
    reste = en_retard(out)
    if reste:
        apercu = ", ".join(p.relative_to(out).as_posix() for p in reste[:5])
        print(f"❌ {len(reste)} archive(s) ne sont PAS sur R2 — elles n'existent "
              f"que sur ce disque : {apercu}"
              + (" …" if len(reste) > 5 else ""), file=sys.stderr)
        rc = rc or 2

    return rc


if __name__ == "__main__":
    sys.exit(main())
