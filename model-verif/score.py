#!/usr/bin/env python3
"""score.py — apparier, agréger, accumuler, publier.

    Session 08/08/2026.
    cf. PWA/web/CONCEPTION_SCORE_MODELES_06-08.md §8, §15.2, §16.1, §16.3
    et PWA/web/supabase_step35_model_verification.sql.

═══ CE QUE FAIT UN RUN ═══

Pour UNE journée D (hier par défaut) :

  1. relit l'archive de `collect.py` — les prévisions émises les jours
     D, D-1 et D-2, et les observations des jours D et D-1 ;
  2. apparie prévu/observé heure par heure, par (station, modèle,
     classe d'échéance) ;
  3. écrit un agrégat quotidien par ligne dans `model_verif_daily` ;
  4. fait avancer les accumulateurs à mémoire longue de
     `model_character`, par zone × régime × tranche de vent ;
  5. recalcule `model_score_zone` et publie `model_scores.json` sur R2 ;
  6. purge ce qui a dépassé sa rétention.

⚠️ LE JOB EST IDEMPOTENT. Le relancer sur la même journée écrit les
mêmes lignes (upsert) et ne fait PAS avancer les accumulateurs deux
fois (`accumulate` refuse une journée déjà intégrée). C'est la même
exigence que partout ailleurs dans ce projet, et elle est ici
particulièrement importante : un accumulateur compté deux fois ne se
répare pas, il faudrait rejouer toute l'histoire.

═══ LA CLASSE D'ÉCHÉANCE, ET POURQUOI CE N'EST PAS UNE ÉCHÉANCE ═══

Le snapshot du jour X, pris vers 03 h UTC, couvre X à X+2. Pour noter
la journée D :

  · le snapshot de D   → échéances 3 à 21 h   → classe « +6 h »
  · le snapshot de D-1 → échéances 24 à 45 h  → classe « +24 h »
  · le snapshot de D-2 → échéances 48 à 69 h  → classe « +48 h »

`lead_exact_h` porte l'échéance réelle moyenne de la journée, parce que
la classe seule ferait croire à une précision qu'elle n'a pas. Le §8.3
parle de « +6 h / +24 h / +48 h » comme si c'étaient des échéances
exactes ; ce sont des bandes, et c'est vrai aussi de l'API Previous
Runs, dont `previous_dayN` désigne un RUN et pas une échéance.

═══ CE QUI DÉGRADE PROPREMENT ═══

`station_zone` est probablement vide au premier run : l'affectation
d'une balise à son bassin-versant demande le relief, et n'est pas faite
par ce lot. Conséquence assumée : les étapes 1 à 3 tournent quand même
(elles ne connaissent aucune zone), et les étapes 4 et 5 sautent en le
DISANT. Une balise sans zone n'est pas rangée dans une case au hasard.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import events as EV  # noqa: E402
import inference as INF  # noqa: E402
import scoring as S  # noqa: E402

DAY_MS = 86_400_000

#: Classe d'échéance ← nombre de jours entre le snapshot et la journée notée.
LEAD_BY_OFFSET = {0: 6, 1: 24, 2: 48}

#: Le modèle maison, lu dans un flux à part (lot I, 13/08/2026). Il ne
#: sert ICI qu'à compter des lignes dans le journal : `daily_rows` ne
#: connaît toujours aucun modèle par son nom, et c'est ce qui a rendu
#: ce lot court.
AGRUME_MODEL = "agrume"

#: Heures minimales appariées pour qu'une journée-balise-modèle compte.
#: En dessous, l'agrégat est du bruit : une balise qui n'a émis que
#: trois heures ne dit rien de la qualité d'un modèle sur la journée.
MIN_HOURS_DAILY = 6

#: Balises minimales dans une case avant de publier un score de zone.
MIN_STATIONS_ZONE = 3

#: ⛔ PLANCHER DE LA RÉFÉRENCE D'UN SKILL, EN (km/h)² — 1,0, soit une
#: erreur RMS de 1 km/h. En dessous, `skill`, `skill_clim`,
#: `beats_persist` et `beats_clim` sortent à **null** : jamais à
#: `false`, jamais à un nombre.
#:
#: ⚠️ SON ABSENCE A COÛTÉ TROIS NUITS DE SCORING (12, 13 et 14/08).
#: `1 − MSE_modèle / MSE_référence` divise par presque rien dès qu'une
#: journée sans vent rend la persistance quasi parfaite. Mesuré le
#: 13/08 en rejouant la journée du 11/08 : `skill` descendait à
#: **−2 573 000**, `skill_clim` à **−35 980**. Le second est un
#: `numeric(8,4)` en base (plafond 10⁴) : l'upsert ENTIER repartait en
#: `HTTP 400 — numeric field overflow`, donc aucun score de zone n'était
#: écrit et `model_scores.json` gelait — pour onze lignes sur 27 812.
#:
#: Le seuil n'est pas choisi au jugé. Dénombré le 13/08 sur les 72 751
#: balise-jours de `model_verif_daily` depuis le 30/07 : 2 719 (3,74 %)
#: ont une persistance dont l'erreur RMS est sous 1 km/h, et 1 855
#: (2,55 %) sous 0,1 km/h — du vent qui n'a pas bougé de la journée.
#: « Ce modèle bat la persistance » n'y a pas de contenu, et un chiffre
#: qui écrase toutes les échelles où il entre est pire qu'une absence.
#:
#: ⓘ Les scores ABSOLUS (`typical_err_kmh`, `worst_decile_kmh`,
#: `err_sd`, `pooled_err_kmh`) ne bougent pas d'un chiffre : ce plancher
#: ne touche QUE le rapport à une référence.
SKILL_MIN_REF_MSE = 1.0

#: Fenêtre du score glissant (§8.4).
ROLLING_DAYS = 15

RETENTION_DAILY_D = 30
RETENTION_EVENT_D = 90
RETENTION_SCORE_D = 7

# ══════════════════════════════════════════════════════════════════
#  LOT G — LES TROIS ARBITRAGES, TRANCHÉS LE 09/08/2026
# ══════════════════════════════════════════════════════════════════
#
# 1. PROFONDEUR D'ARCHIVE. L'archive R2 commence le 07/08/2026 : deux
#    jours au moment où ce code est écrit. Un bootstrap par blocs de
#    jours sur deux jours n'a aucun sens, et le partial pooling non
#    plus. Décision : ÉCRIRE LE CODE MAINTENANT et le laisser rendre
#    `None` avec une raison explicite (`window_too_short`) tant que la
#    fenêtre est trop courte. Le code est prêt le jour où les données
#    arrivent, et l'archive permet de tout REJOUER — c'est
#    précisément ce pour quoi elle ne se purge jamais.
#    Le contraire (attendre deux semaines) aurait fait écrire le même
#    code plus tard, sans banc, sur des données qu'on n'aurait pas pu
#    rejouer avant.
#
# 2. `hold_ms` — cf. `events.py`, en-tête de `HOLD_MS`. Fenêtre
#    ADAPTATIVE au pas réel de la série, plutôt qu'un seuil fixe.
#
# 3. PARTIAL POOLING ET QUORUM. Le §16.3 dit « en remplacement
#    progressif du quorum sec ». Décision : le pooling AMÉLIORE
#    l'estimation, le quorum reste le seuil d'AFFICHAGE, et le poids
#    emprunté est publié à côté de chaque chiffre. Un remplacement
#    franc ferait apparaître des chiffres partout, y compris là où
#    presque tout est emprunté au parent — c'est-à-dire ouvrirait la
#    vanne au moment précis où on affirme la refermer.

#: Fenêtre du chemin RÉGIME, en jours d'archive rejoués. Le chemin
#: régime ne lit plus les accumulateurs pour son erreur typique : trois
#: sommes (`sum_w`, `sum_wx`, `sum_wx2`) savent faire une moyenne et une
#: variance, jamais un décile. Elles restent la mémoire longue du
#: CARACTÈRE (§15.4) ; la DISTRIBUTION se rejoue depuis les paires
#: brutes.
REGIME_REPLAY_DAYS = 30

#: Où le rejeu range ses journées déjà recalculées, sous `--out`. Une
#: journée rejouée ne change plus jamais : l'archive est immuable et la
#: formule est versionnée par `REPLAY_FORMULA`. Sans ce cache, rejouer
#: 30 jours chaque nuit multiplierait la durée du run par 30.
REPLAY_SUBDIR = "replay"

#: ⚠️ À INCRÉMENTER À CHAQUE FOIS QUE `daily_rows` CHANGE DE RÉSULTAT.
#: Un cache qui survit à un changement de formule sert des chiffres
#: calculés par du code qui n'existe plus, sans que rien ne le signale —
#: le même piège que le `dist_old_*` servi par localhost le 08/08.
#: 2 — lot G4 : `daily_rows` porte désormais `mse_clim` à côté de
#:     `mse_persist`. Les caches de la formule 1 sont donc ignorés.
#: 3 — lot I (13/08) : le flux AGRUME entre dans les snapshots. La
#:     formule n'a pas bougé d'une virgule — c'est l'ENSEMBLE D'ENTRÉE
#:     qui a changé, et ça suffit. Un cache d'avant ne porte aucune
#:     ligne AGRUME ; réutilisé, il donnerait une fenêtre de régime où
#:     AGRUME existe pour les journées récentes et pas pour les
#:     anciennes, sans que rien ne le dise. ⚠️ Le prix est connu et
#:     borné : `--replay-budget` (3 par défaut) rattrape trois journées
#:     par nuit et `replay_window` COMPTE celles qu'il reporte. Pour
#:     rattraper d'un coup : `--replay-budget 30`.
#: 4 — lot S2 (22/08) : `daily_rows` porte la COLONNE CORRIGÉE du biais
#:     de site (`err_vec_med_corr`, `mse_model_corr`, `bias_n_days`) et
#:     la pente du jour (`bias_slope`) dont l'antécédent des journées
#:     suivantes est fait. Un cache de la formule 3 ne porte NI l'une NI
#:     l'autre : réutilisé, il donnerait une fenêtre où le corrigé
#:     existe pour les journées récentes et manque pour les anciennes —
#:     exactement le mélange que la formule 3 refusait déjà pour AGRUME.
#:     ⚠️ Prix connu : au premier run, les 30 caches sont invalides et
#:     l'antécédent repart à zéro. `--replay-budget 30` une fois (mesuré
#:     ~35 s par journée sur le VPS, soit ~18 min) plutôt que dix nuits
#:     à en rattraper trois.
REPLAY_FORMULA = 4


class Abort(Exception):
    """Arrêt net et volontaire."""


# ══════════════════════════════════════════════════════════════════
#  SUPABASE (PostgREST, clé service_role — contourne RLS)
# ══════════════════════════════════════════════════════════════════

class Supabase:
    """Le strict nécessaire : lire une table, en écrire une par upsert.

    Même modèle d'accès que `mf_station_history` (step13) : la clé
    `service_role` contourne RLS, aucune policy d'écriture n'existe et
    n'a à exister.
    """

    def __init__(self, dry_run: bool = False):
        self.url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
        self.key = os.environ.get("SUPABASE_SERVICE_KEY") or ""
        self.dry_run = dry_run
        if not dry_run and not (self.url and self.key):
            raise Abort("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants")
        self.ecritures = 0

    def _req(self, path: str, method: str, data: bytes | None = None,
             extra: dict | None = None):
        return urllib.request.Request(
            f"{self.url}/rest/v1/{path}", data=data, method=method,
            headers={"apikey": self.key, "Authorization": f"Bearer {self.key}",
                     "Content-Type": "application/json", **(extra or {})})

    #: Nombre de lignes qu'un seul appel PostgREST peut rendre. Mesuré en
    #: direct le 08/08 : `Range: 0-4999` sur une table de 1 946 lignes en
    #: rend 1 000, pas 1 946. C'est `db-max-rows` côté serveur, pas une
    #: limite du client — demander plus n'y change rien.
    PAGE = 1000

    def select(self, table: str, query: str = "", order: str | None = None,
               ) -> list[dict]:
        """Lit une table ENTIÈRE, page par page.

        ⚠️ DÉFAUT TROUVÉ LE 08/08 EN VÉRIFIANT LES CHIFFRES DU LOT F, ET
        IL NE DATAIT PAS DU LOT F. La version précédente faisait UN appel
        et rendait ce qui venait. PostgREST plafonne à 1 000 lignes et le
        dit dans un en-tête que personne ne lisait : la fonction rendait
        donc une TRONCATURE SILENCIEUSE, jamais une erreur.
        Conséquences mesurées sur la base réelle :
          · `model_verif_daily` sur 15 jours = 5 407 lignes → 1 000 lues,
            soit un score glissant calculé sur 18 % de sa fenêtre ;
          · `model_character` = 81 960 accumulateurs → 1 000 lus, donc
            80 960 accumulateurs repartaient de ZÉRO chaque nuit. La
            mémoire longue du §15.4, dont c'est toute la raison d'être,
            n'a jamais mémorisé quoi que ce soit.
        Rien ne plantait, rien n'était rouge, et les chiffres avaient
        l'air normaux. C'est le motif exact contre lequel ce chantier se
        bat : une table raisonnée n'est pas une table vérifiée.

        ⚠️ `order` N'EST PAS DÉCORATIF. Sans `ORDER BY`, PostgreSQL n'a
        aucune obligation de rendre deux pages dans un ordre cohérent :
        une ligne peut apparaître deux fois et une autre jamais. On
        ordonne donc sur la clé primaire de la table, et l'appelant la
        passe explicitement — la deviner ici serait la même faute de
        reniflage que celle corrigée dans `zone_kind_for`.
        """
        if self.dry_run:
            return []
        sep = "&" if "?" in query else "?"
        base = (f"{table}{query}{sep}select=*" if "select=" not in query
                else f"{table}{query}")
        if order:
            base += f"{'&' if '?' in base else '?'}order={order}"
        out: list[dict] = []
        offset = 0
        while True:
            req = self._req(base, "GET", None,
                            {"Range-Unit": "items",
                             "Range": f"{offset}-{offset + self.PAGE - 1}"})
            with urllib.request.urlopen(req, timeout=120) as r:
                page = json.loads(r.read().decode("utf-8"))
            out.extend(page)
            # Une page incomplète est la fin : c'est le seul signal fiable
            # sans demander un `count=exact`, qui coûte un balayage complet
            # de la table à chaque appel.
            if len(page) < self.PAGE:
                return out
            offset += self.PAGE

    _schema: dict | None = None

    def columns(self, table: str) -> set[str] | None:
        """Les colonnes RÉELLES d'une table, lues une fois par run.

        ⚠️ Ce n'est pas de la curiosité : le lot G ajoute des colonnes à
        `model_score_zone` (`pooled_err_kmh`, `borrowed_weight`, …) et le
        SQL ne s'exécute JAMAIS depuis ici — c'est Yann qui le lance,
        quand il le lance. Entre le déploiement du code et l'exécution du
        SQL, un run qui enverrait les nouvelles colonnes recevrait un
        `PGRST204 — column … does not exist` et la nuit serait perdue.

        On lit donc le schéma que PostgREST publie à sa racine et on
        n'envoie que ce que la table sait recevoir. Le jour où le SQL est
        passé, les colonnes apparaissent d'elles-mêmes : aucun drapeau à
        basculer, donc aucun drapeau à oublier.

        Rend `None` si le schéma n'est pas lisible — l'appelant se
        rabat alors sur le jeu de colonnes historique.
        """
        if self.dry_run:
            return None
        if Supabase._schema is None:
            try:
                req = self._req("", "GET", None, {"Accept": "application/openapi+json"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    Supabase._schema = json.loads(r.read().decode("utf-8"))
            except Exception as exc:                      # noqa: BLE001
                print(f"  ⚠️ schéma PostgREST illisible ({exc}) : on s'en tient "
                      f"aux colonnes historiques.", file=sys.stderr)
                Supabase._schema = {}
        defs = (Supabase._schema or {}).get("definitions", {})
        d = defs.get(table)
        if not d:
            return None
        return set((d.get("properties") or {}).keys())

    def upsert(self, table: str, rows: list[dict], on_conflict: str,
               chunk: int = 500) -> int:
        """Upsert par paquets.

        ⚠️ `resolution=merge-duplicates` et PAS un delete-puis-insert :
        une réécriture en deux temps laisse la table vide entre les
        deux, et l'atelier admin lirait un trou. Sur une table réécrite
        chaque nuit, ce trou dure le temps du run.
        """
        if not rows:
            return 0
        # ⚠️ GARDE-FOU AJOUTÉ LE 08/08, APRÈS AVOIR PAYÉ LE MESSAGE.
        # PostgREST refuse un envoi groupé dont les objets n'ont pas tous
        # le même jeu de clés, et il le dit ainsi :
        #
        #     HTTP 400 — {"code":"PGRST102", … "All object keys must match"}
        #
        # Ni la clé fautive, ni la ligne, ni la table. Le run nocturne
        # tombe alors sur une pile d'appels `urllib` qui parle de tout
        # sauf du problème. On vérifie donc AVANT d'envoyer, et on nomme
        # la clé — le coût est une union d'ensembles sur quelques
        # milliers de lignes, invisible devant l'aller-retour réseau.
        formes = {frozenset(r.keys()) for r in rows}
        if len(formes) > 1:
            communes = frozenset.intersection(*formes)
            variables = sorted(set().union(*formes) - communes)
            raise Abort(
                f"upsert {table} : {len(formes)} jeux de clés différents dans le "
                f"même envoi — PostgREST le refusera (PGRST102). Clés présentes "
                f"dans certaines lignes seulement : {variables}. Les ajouter à "
                f"`None` partout plutôt que de les omettre.")
        if self.dry_run:
            print(f"  (dry-run) {len(rows)} lignes vers {table}")
            return len(rows)
        n = 0
        for i in range(0, len(rows), chunk):
            body = json.dumps(rows[i:i + chunk]).encode("utf-8")
            req = self._req(f"{table}?on_conflict={on_conflict}", "POST", body,
                            {"Prefer": "resolution=merge-duplicates,return=minimal"})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    r.read()
            except urllib.error.HTTPError as e:
                detail = e.read()[:400].decode("utf-8", "replace")
                raise Abort(f"upsert {table} : HTTP {e.code} — {detail}") from e
            n += len(rows[i:i + chunk])
        self.ecritures += n
        return n

    def insert(self, table: str, rows: list[dict], chunk: int = 500) -> int:
        """Insertion simple, pour les tables SANS clé d'unicité.

        ⚠️ `model_verif_event` n'a PAS de contrainte d'unicité, et ce
        n'est pas un oubli : elle porte UNE LIGNE PAR ÉVÉNEMENT
        INDIVIDUEL (chaque succès, chaque raté, chaque fausse alarme),
        pas un agrégat par nuit. Deux bascules ratées le même jour par le
        même modèle sur la même zone sont deux lignes légitimes, qu'un
        `on_conflict` fusionnerait en une.

        L'idempotence se joue donc ailleurs : l'appelant PURGE la journée
        avant de réinsérer (`?day=eq.…`). Contrairement au cas de
        `upsert`, le trou de lecture ne coûte rien ici — la purge ne
        touche qu'un jour sur une fenêtre de 90, et personne ne lit cette
        table en direct : le JSON publié est reconstruit après.
        """
        if not rows:
            return 0
        formes = {frozenset(r.keys()) for r in rows}
        if len(formes) > 1:
            communes = frozenset.intersection(*formes)
            variables = sorted(set().union(*formes) - communes)
            raise Abort(
                f"insert {table} : {len(formes)} jeux de clés différents dans le "
                f"même envoi — PostgREST le refusera (PGRST102). Clés présentes "
                f"dans certaines lignes seulement : {variables}.")
        if self.dry_run:
            print(f"  (dry-run) {len(rows)} lignes vers {table}")
            return len(rows)
        n = 0
        for i in range(0, len(rows), chunk):
            body = json.dumps(rows[i:i + chunk]).encode("utf-8")
            req = self._req(table, "POST", body,
                            {"Prefer": "return=minimal"})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    r.read()
            except urllib.error.HTTPError as e:
                detail = e.read()[:400].decode("utf-8", "replace")
                raise Abort(f"insert {table} : HTTP {e.code} — {detail}") from e
            n += len(rows[i:i + chunk])
        self.ecritures += n
        return n

    def delete(self, table: str, query: str) -> None:
        if self.dry_run:
            print(f"  (dry-run) delete {table}{query}")
            return
        req = self._req(f"{table}{query}", "DELETE", None, {"Prefer": "return=minimal"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                r.read()
        except urllib.error.HTTPError as e:
            print(f"  ⚠️ purge {table} : HTTP {e.code}", file=sys.stderr)


# ══════════════════════════════════════════════════════════════════
#  ARCHIVE
# ══════════════════════════════════════════════════════════════════

def _storage():
    tools = pathlib.Path(__file__).resolve().parent.parent / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    try:
        from storage import Storage             # type: ignore
        return Storage("model-verif", bucket_env="MODEL_VERIF_BUCKET",
                       defaut="model-verif", plafond=10)
    except Exception:                           # noqa: BLE001
        return None


def read_ndjson(root: pathlib.Path, key: str, storage=None):
    """Lit un objet d'archive, localement d'abord, sur R2 ensuite.

    ⚠️ Un objet ABSENT rend une liste vide, et l'appelant doit le
    traiter comme « pas de donnée ce jour-là », pas comme une erreur :
    au démarrage, D-1 et D-2 n'existent pas encore, et c'est normal.
    Confondre les deux ferait échouer les quinze premiers runs.
    """
    path = root / key
    raw = None
    if path.exists():
        raw = path.read_bytes()
    elif storage is not None:
        raw = storage.get(key)
    if not raw:
        return []
    try:
        text = gzip.decompress(raw).decode("utf-8")
    except OSError:
        text = raw.decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def read_json(root: pathlib.Path, key: str, storage=None):
    """Lit UN objet JSON d'archive, localement d'abord, sur R2 ensuite.

    Même contrat que `read_ndjson` : un objet absent rend `None`, et
    l'appelant doit en faire un fait, pas une erreur.

    ⓘ LE LOCAL D'ABORD, ET ÇA COMPTE POUR LE MANIFESTE. `score.py`
    tourne sur la même machine que `collect.py` : si l'envoi R2 du
    manifeste a échoué, le fichier est quand même là, et la notation de
    la nuit le trouve. R2 n'est le recours que pour un rejeu fait
    ailleurs.
    """
    path = root / key
    raw = None
    if path.exists():
        raw = path.read_bytes()
    elif storage is not None:
        raw = storage.get(key)
    if not raw:
        return None
    try:
        return json.loads(gzip.decompress(raw).decode("utf-8"))
    except OSError:
        pass
    except ValueError:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:
        return None


def fcst_key(day: datetime, partie: int = 1) -> str:
    """La clé d'UNE partie du flux `fcst/` — la 1 est la clé historique.

    ⛔ AUCUNE DATE DE BASCULE, ET C'EST LA PROPRIÉTÉ QUI COMPTE.
    `fcst_key(day)` rend exactement ce qu'elle rendait avant le lot S0.6,
    donc les 15 nuits déjà écrites (au 22/08/2026) restent lisibles sans
    condition. Une journée d'avant la partition n'a pas de manifeste,
    n'a qu'une clé, et son union est complète.

    ⓘ Le miroir de `collect.fcst_cle`. Les deux fichiers ne s'importent
    pas l'un l'autre (`score.py` ne doit dépendre ni de numpy ni du
    paquet `agrume/`), donc la forme est écrite deux fois — et le banc
    `test_score.py::test_les_deux_cles_fcst_sont_la_meme_chaine` la
    compare caractère pour caractère plutôt que de faire confiance.
    """
    if partie < 1:
        raise ValueError(f"partie {partie} : elles se comptent à partir de 1")
    suffixe = "" if partie == 1 else f"_p{partie}"
    return f"fcst/{day:%Y/%m}/fcst_{day:%Y-%m-%d}{suffixe}.ndjson.gz"


def fcst_manifeste_key(day: datetime) -> str:
    """Le manifeste de partition du flux `fcst/` — objet LATÉRAL.

    ⚠️ `tools/storage.py` N'A PAS DE `list`, et c'est pour ça que cette
    clé est calculable : on la lit par `get_json`, jamais par listing.
    C'est aussi ce qui condamnait la variante « le nom de la clé porte
    le total » (`_p2sur2`) — il aurait fallu sonder n × n clés pour
    trouver celle qui parle.
    """
    return f"fcst/{day:%Y/%m}/fcst_{day:%Y-%m-%d}.manifeste.json"


def obs_key(day: datetime) -> str:
    return f"obs/{day:%Y/%m}/obs_{day:%Y-%m-%d}.ndjson.gz"


def obswindsmobi_key(day: datetime) -> str:
    """Le flux windsmobi (S0.2, 21/08) — clé à part, jamais dans `obs/`.

    Décision 1 du cadrage : `obs/` reste Pioupiou seul, lu depuis treize
    nuits par `score.py` (ce fichier). windsmobi a sa cadence, ses
    variables (pas de pression, jamais) et sa géographie propres — les
    mélanger dans un fichier déjà relu, c'était risquer de casser une
    notation qui marche pour une donnée que personne ne note encore.
    """
    return f"obswindsmobi/{day:%Y/%m}/obswindsmobi_{day:%Y-%m-%d}.ndjson.gz"


def obsinfoclimat_key(day: datetime) -> str:
    """Le flux infoclimat (S0.2, 21/08, session 2) — clé à part, comme
    windsmobi. Porte aussi `pres_hpa`/`pres_kind`/`licence_code` que le
    S1 lira plus tard ; `score.py` ne les regarde pas encore (cf.
    `to_obs_samples`, qui ne lit que `t`/`speed`/`dir`).
    """
    return f"obsinfoclimat/{day:%Y/%m}/obsinfoclimat_{day:%Y-%m-%d}.ndjson.gz"


def obsmf_key(day: datetime) -> str:
    """Le flux mf (S0.2, 21/08, session 3) — clé à part, comme windsmobi
    et infoclimat. Porte aussi `pres_hpa`/`pres_kind` que le S1 lira
    plus tard ; `score.py` ne les regarde pas encore (cf.
    `to_obs_samples`, qui ne lit que `t`/`speed`/`dir`).
    """
    return f"obsmf/{day:%Y/%m}/obsmf_{day:%Y-%m-%d}.ndjson.gz"


def obsaemet_key(day: datetime) -> str:
    """Le flux aemet (S0.2, 21/08, session 4 — le dernier du sous-lot) —
    clé à part, comme windsmobi/infoclimat/mf. Porte aussi
    `pres_hpa`/`pres_kind` que le S1 lira plus tard ; `score.py` ne les
    regarde pas encore (cf. `to_obs_samples`, qui ne lit que
    `t`/`speed`/`dir`).
    """
    return f"obsaemet/{day:%Y/%m}/obsaemet_{day:%Y-%m-%d}.ndjson.gz"


#: Toutes les clés d'observations de VENT à fusionner pour noter une
#: journée. `obs_key` (Pioupiou) est la seule d'origine ; chaque session
#: du S0.2 y ajoute la sienne au fil de l'eau — windsmobi, infoclimat,
#: mf et aemet faits : S0.2 est clos. ⚠️ `score.py` NE CONNAÎT AUCUN
#: RÉSEAU PAR SON NOM au-delà de cette liste : `daily_rows`,
#: `climatology_by_station` et le reste de la notation lisent des lignes
#: génériques (`source`, `station_id`, `t`, `speed`…) sans jamais tester
#: `row["source"] == "windsmobi"`. Ajouter un réseau, c'est ajouter sa
#: fonction de clé ici — rien d'autre à toucher dans ce fichier pour
#: qu'il entre dans le score.
OBS_KEY_FUNCS = [obs_key, obswindsmobi_key, obsinfoclimat_key, obsmf_key, obsaemet_key]


def all_obs_rows(root: pathlib.Path, day: datetime, storage=None) -> list[dict]:
    """Les observations de vent de TOUTES les sources, pour une journée.

    Même principe que `snapshot_rows` pour les prévisions (fcst + fcst
    AGRUME) : une fonction qui fusionne, jamais un `if` par réseau semé
    dans le reste du fichier. Un objet absent rend `[]` (`read_ndjson`),
    donc une source qui n'existe pas encore pour cette journée ne casse
    rien — c'est le cas normal des quinze premières nuits de chaque
    nouveau réseau.
    """
    rows: list[dict] = []
    for key_fn in OBS_KEY_FUNCS:
        rows += read_ndjson(root, key_fn(day), storage)
    return rows


def fcst_agrume_key(day: datetime) -> str:
    """Le flux AGRUME — un préfixe à part, et c'est délibéré (lot I).

    ⚠️ POURQUOI PAS DANS `fcst/`. Les deux flux n'ont ni le même
    producteur, ni la même heure, ni la même façon d'échouer :
    `collect.py` interroge Open-Meteo sous quota et son archive est
    IRREMPLAÇABLE (aucun modèle Météo-France n'a d'historique de runs
    passés — mesuré le 08/08 : 0/384 sur `_previous_day1`) ;
    `agrume_fcst.py` relit un produit A qui, lui, est encore là. Les
    mélanger dans une clé réécrite par deux jobs, c'est se donner un
    moyen de perdre l'irremplaçable en réécrivant le rejouable.

    ⓘ Ce préfixe est le seul endroit du dépôt où il est écrit. C'est
    `agrume_fcst.py` qui l'importe d'ici, pas l'inverse — `score.py` ne
    doit dépendre ni de numpy ni du paquet `agrume/`.
    """
    return f"fcstagrume/{day:%Y/%m}/fcstagrume_{day:%Y-%m-%d}.ndjson.gz"


def fcst_arome_key(day: datetime) -> str:
    """Le flux AROME lu sur R2 (lot S0.5, 22/08) — un préfixe à part,
    exactement pour les mêmes raisons que `fcstagrume`.

    ⚠️ POURQUOI PAS DANS `fcst/`. Les deux flux n'ont ni le même
    producteur, ni la même heure, ni la même façon d'échouer :
    `collect.py` interroge Open-Meteo sous quota à 03:19 et son archive
    est IRREMPLAÇABLE ; `arome_fcst.py` relit à 06:00 des tuiles que
    l'Action `arome-wind` réécrit toutes les 3 h. Les mélanger dans une
    clé écrite par deux jobs, c'est se donner un moyen de perdre
    l'irremplaçable en réécrivant l'autre.

    ⚠️ ET L'ARCHIVE PORTE LE JOUR DE SON PROPRE RUN, pas la veille.
    `agrume_fcst.py` archive HIER (le produit A est encore sur R2) ;
    ici les tuiles n'ont AUCUN historique, donc le job lit le jour même
    et `fcstarome_{J}` contient bien « les prévisions émises le jour J »
    — la même chose que `fcst_{J}`, écrit le matin de J lui aussi.

    ⓘ Ce préfixe est le seul endroit du dépôt où il est écrit. C'est
    `arome_fcst.py` qui l'importe d'ici, pas l'inverse.
    """
    return f"fcstarome/{day:%Y/%m}/fcstarome_{day:%Y-%m-%d}.ndjson.gz"


def snapshot_rows(root: pathlib.Path, day: datetime, storage=None) -> list[dict]:
    """Toutes les prévisions émises un jour donné, tous flux confondus.

    ⛔ LES FLUX R2 SONT LUS AUX TROIS OFFSETS, EXACTEMENT COMME LES
    AUTRES, et ce n'est pas une négligence. L'horizon d'AGRUME (24 h)
    fait qu'aux offsets 1 et 2 il ne reste que 1 à 4 heures appariables
    dans la journée notée ; celui d'AROME/R2 (51 h) ne laisse que
    2 heures à l'offset 2 — le run 00 Z de J−2 ne touche la journée J
    que par 00:00 et 03:00, `arome-wind/ingest.py::keep_step()` ayant
    déjà retiré 01 h et 02 h de la nuit. Dans les deux cas c'est sous
    `MIN_HOURS_DAILY`, donc `daily_rows` et `event_rows` les écartent
    tous les deux d'eux-mêmes. Écrire ici un `if offset == 0`
    produirait le même résultat en le faisant dépendre d'une constante
    lue à un autre endroit : le jour où l'horizon d'AGRUME passerait à
    48 h (ARPEGE), ou celui où `MAX_HOURS` d'`arome-wind` remonterait,
    il faudrait penser à retirer la garde. Ici, il n'y a rien à
    penser : la donnée décide. Les bancs
    `test_agrume_fcst.py::test_lead_24_ne_sort_aucune_ligne` et
    `test_arome_fcst.py::test_lead_48_ne_sort_aucune_ligne` tiennent
    la propriété.
    """
    return snapshot_rows_et_bilan(root, day, storage)[0]


#: Version de manifeste que ce fichier sait lire. Un numéro inconnu doit
#: ARRÊTER la lecture, pas être ignoré : un manifeste v2 pourrait très
#: bien déclarer ses parties autrement, et les compter comme des v1
#: donnerait un chiffre faux avec l'air d'être juste.
MANIFESTE_VERSION_LUE = 1


def fcst_parties(root: pathlib.Path, day: datetime,
                 storage=None) -> tuple[list[dict], dict]:
    """Les lignes du flux `fcst/` ET le bilan de ses parties.

    ⛔⛔ ON NE DEVINE JAMAIS COMBIEN DE PARTIES LA NUIT ATTENDAIT. C'est
    le piège central du lot S0.6, et il n'a qu'une forme : si la
    partie 2 échoue et que la notation lit « les clés qui existent », la
    journée est notée sur sept modèles en moins SANS QUE RIEN NE LE
    DISE. Le compte vient du MANIFESTE, écrit avant la première ligne de
    données ; il ne vient de nulle part ailleurs.

    Rend `(lignes, bilan)`, où le bilan est :

        {"flux": "fcst", "parties_attendues": 2, "parties_lues": 1,
         "manquantes": [{"i": 2, "cle": …, "modeles": [...]}],
         "modeles_manquants": [...], "etat": "…"}

    ⚠️ `flux` N'EST PAS DÉCORATIF. `snapshot_rows` lit TROIS flux depuis
    le lot S0.5 (`fcst`, `fcstagrume`, `fcstarome`) et UN SEUL est
    partitionné. Sans le nommer, « 1 partie sur 2 » se lit « il manque
    un flux sur deux », qui est une tout autre nuit.

    ⚠️ LES QUATRE ÉTATS, ET AUCUN N'A BESOIN D'UNE DATE DE BASCULE :

    | manifeste | clé historique | `_p2` | lecture                       |
    |-----------|----------------|-------|-------------------------------|
    | présent   | —              | —     | il fait autorité, point       |
    | absent    | présente       | vide  | journée d'AVANT la partition  |
    | absent    | présente       | pleine| ⛔ INCIDENT : manifeste perdu  |
    | absent    | absente        | vide  | ⛔ INCIDENT : nuit sans rien   |

    ⓘ LE SONDAGE DE `_p2` NE SERT PAS À COMPTER. Il ne sert qu'à savoir
    si l'ABSENCE du manifeste est excusable. Une nuit à trois parties qui
    aurait perdu son manifeste tombe donc aussi en incident — ce qui est
    la bonne réponse, puisqu'on ne saura de toute façon plus ce qu'elle
    attendait. Un `get` R2 de plus par journée d'émission, soit trois par
    nuit : Class B, 0,0001 % du palier.
    """
    manifeste = read_json(root, fcst_manifeste_key(day), storage)
    bilan = {"flux": "fcst", "parties_attendues": None, "parties_lues": 0,
             "manquantes": [], "modeles_manquants": [], "etat": "ok"}

    if isinstance(manifeste, dict) and \
            manifeste.get("version") == MANIFESTE_VERSION_LUE:
        detail = manifeste.get("detail") or []
        bilan["parties_attendues"] = int(manifeste.get("parties") or len(detail))
        rows: list[dict] = []
        for d in detail:
            cle = d.get("cle") or fcst_key(day, int(d.get("i", 1)))
            part = read_ndjson(root, cle, storage)
            if part:
                bilan["parties_lues"] += 1
                rows += part
            else:
                bilan["manquantes"].append(
                    {"i": d.get("i"), "cle": cle,
                     "modeles": list(d.get("modeles") or [])})
                bilan["modeles_manquants"] += list(d.get("modeles") or [])
        if bilan["manquantes"]:
            bilan["etat"] = "partie_manquante"
        return rows, bilan

    if isinstance(manifeste, dict):
        # Un manifeste illisible ou d'une version inconnue. ⛔ On ne
        # l'interprète PAS : on lit la clé historique, et on le dit.
        bilan["etat"] = "manifeste_version_inconnue"
        p1 = read_ndjson(root, fcst_key(day), storage)
        bilan["parties_lues"] = 1 if p1 else 0
        return p1, bilan

    # ── Pas de manifeste ────────────────────────────────────────────
    p1 = read_ndjson(root, fcst_key(day), storage)
    p2 = read_ndjson(root, fcst_key(day, 2), storage)
    if p2:
        # ⛔ Une partie 2 sans manifeste : la déclaration a été perdue.
        # On garde les lignes — la donnée est la donnée — mais on
        # REFUSE de dire combien de parties étaient attendues.
        bilan["etat"] = "manifeste_absent_mais_partie_2_presente"
        bilan["parties_lues"] = (1 if p1 else 0) + 1
        return p1 + p2, bilan
    if p1:
        bilan["parties_attendues"] = 1
        bilan["parties_lues"] = 1
        bilan["etat"] = "avant_partition"
        return p1, bilan
    bilan["etat"] = "rien_produit"
    return [], bilan


def snapshot_rows_et_bilan(root: pathlib.Path, day: datetime,
                           storage=None) -> tuple[list[dict], dict]:
    """`snapshot_rows`, plus le bilan des parties du flux `fcst/`.

    ⓘ POURQUOI DEUX FONCTIONS. `snapshot_rows` est appelée par les bancs
    d'`agrume_fcst` et d'`arome_fcst`, qui n'ont que faire du bilan ;
    lui faire rendre un couple aurait cassé trois appelants pour une
    information dont ils ne se servent pas. Et lire le bilan
    séparément aurait relu les archives une seconde fois — 6 Mo par
    offset, trois fois par nuit, pour rien.
    """
    rows, bilan = fcst_parties(root, day, storage)
    return (rows
            + read_ndjson(root, fcst_agrume_key(day), storage)
            + read_ndjson(root, fcst_arome_key(day), storage)), bilan


def dire_bilan_parties(bilan: dict, offset: int) -> str:
    """Une ligne de journal qui COMPTE et qui NOMME.

    ⛔ « prévisions émises J-0 : 5 595 lignes » ne suffit plus. Un compte
    de lignes ne distingue pas une nuit complète d'une nuit à laquelle
    il manque sept modèles — les deux sont « beaucoup de lignes ». Il
    faut dire combien de parties, sur combien, et LESQUELS des modèles
    manquent.
    """
    f = bilan.get("flux", "?")
    att, lues = bilan.get("parties_attendues"), bilan.get("parties_lues", 0)
    etat = bilan.get("etat")
    if etat == "avant_partition":
        return f"`{f}/` : 1 partie (journée d'avant la partition)"
    if etat == "rien_produit":
        return (f"⛔ `{f}/` : AUCUNE donnée et AUCUN manifeste pour J-{offset} "
                f"— la nuit d'émission n'a rien produit du tout")
    if etat == "manifeste_absent_mais_partie_2_presente":
        return (f"⛔ `{f}/` : {lues} partie(s) lue(s) mais AUCUN MANIFESTE, "
                f"alors qu'une partie 2 existe — la déclaration a été perdue "
                f"et plus rien ne dit combien de parties cette nuit attendait")
    if etat == "manifeste_version_inconnue":
        return (f"⛔ `{f}/` : manifeste d'une version que ce code ne sait pas "
                f"lire — seule la clé historique a été lue")
    if etat == "partie_manquante":
        noms = ", ".join(bilan.get("modeles_manquants") or []) or "?"
        quelles = ", ".join(str(m.get("i")) for m in bilan.get("manquantes", []))
        return (f"⛔ `{f}/` : {lues}/{att} parties — partie(s) {quelles} "
                f"MANQUANTE(S) : {noms}")
    return f"`{f}/` : {lues}/{att} parties"


def to_obs_samples(row: dict) -> list[S.ObsSample]:
    t = row.get("t") or []
    sp = row.get("speed") or []
    di = row.get("dir") or []
    out = []
    for i, ts in enumerate(t):
        out.append(S.ObsSample(
            t=int(ts) * 1000,
            speed=sp[i] if i < len(sp) else None,
            dir=di[i] if i < len(di) else None))
    return out


def fcst_times_ms(row: dict) -> list[int]:
    """Reconstitue les heures valides depuis `t0` + `step_s`."""
    n = len(row.get("speed") or [])
    t0, step = int(row["t0"]), int(row["step_s"])
    return [(t0 + i * step) * 1000 for i in range(n)]


# ══════════════════════════════════════════════════════════════════
#  RÉGIME DE LA JOURNÉE
# ══════════════════════════════════════════════════════════════════

def day_regime(fcst_ref: dict | None, obs: list[S.ObsSample],
               day_start_ms: int, utc_offset_s: int) -> str:
    """Étiquette la journée d'une balise.

    ⚠️ LE VENT D'ALTITUDE VIENT D'UN SEUL MODÈLE DE RÉFÉRENCE, le même
    pour tout le monde (`collect.REGIME_REF_MODEL`). Si chaque modèle
    classait la journée avec son propre vent d'altitude, il pourrait
    « choisir » le régime dans lequel il est noté — un modèle qui voit
    du flux là où les autres voient du thermique se ferait juger sur
    une autre population de journées.

    ⚠️ ET CE N'EST PAS `crestWind.ts`. C'est du 850 hPa, un proxy. Les
    seuils de `REGIME_THRESHOLDS` ont été raisonnés sur un vent de
    crête. Ils ne sont calibrés sur rien (§16.5), mais il ne faut pas
    laisser croire que ce proxy les rend justes : le jour où on
    calibrera, c'est ce couple seuil/niveau qu'il faudra reprendre
    ensemble, pas le seuil seul.
    """
    if fcst_ref is None:
        return "unknown"
    times = fcst_times_ms(fcst_ref)
    aloft_s = fcst_ref.get("aloft_speed") or []
    aloft_d = fcst_ref.get("aloft_dir") or []
    hourly: list[tuple[int, str | None]] = []
    for i, t in enumerate(times):
        if not (day_start_ms <= t < day_start_ms + DAY_MS):
            continue
        cs = aloft_s[i] if i < len(aloft_s) else None
        cd = aloft_d[i] if i < len(aloft_d) else None
        win = [o for o in obs if abs(o.t - t) <= S.OBS_HALF_WINDOW_MS]
        surf, _, _ = S.mean_wind(win) if win else (None, None, 0)
        hourly.append((t, S.classify_regime(cs, cd, surf)))
    return S.dominant_regime(hourly, utc_offset_s=utc_offset_s) or "unknown"


# ══════════════════════════════════════════════════════════════════
#  AGRÉGAT QUOTIDIEN
# ══════════════════════════════════════════════════════════════════

def daily_rows(day: datetime, snapshots: dict[int, list[dict]],
               obs_day: list[dict], obs_prev: list[dict],
               utc_offset_s: int, clim: dict | None = None,
               bias_prior: dict | None = None, temoin: list | None = None):
    """Rend (lignes model_verif_daily, détail par tranche de vent).

    Le détail par tranche ne va PAS en base : il alimente les
    accumulateurs le soir même. §15.4 — « ce modèle sous-estime le
    vent » est presque toujours faux en moyenne et vrai dans une
    tranche, un modèle collant au vent faible et écrêtant le vent fort.
    Une seule colonne `bias_ratio` par journée ne peut pas porter ça ;
    la stocker par tranche triplerait la table pour une donnée qui ne
    sert qu'une fois.

    `bias_prior` (lot S2) : `{(unit, model, lead): (pente, cap, n_jours)}`
    bâti par `prior_biais` sur les jours STRICTEMENT antérieurs. Absent
    ou vide, les colonnes `*_corr` sortent à `None` et le reste de la
    fonction est bit à bit ce qu'il était — c'est ce qui permet aux
    168 assertions de `test_score.py` de rester vraies sans changer.

    `temoin` : liste que la fonction remplit de couples
    `(err_brut, err_placebo)` pour une balise-jour sur `BIAIS_TEMOIN_PAS`,
    la correction d'une AUTRE balise étant appliquée à celle-ci. ⛔ Ce
    n'est pas une coquetterie : mesuré le 22/08, un antécédent tiré au
    sort rend DÉJÀ 13 % des 29 % de gain. Publier « corrigé −29 % » sans
    ce chiffre laisserait croire que 29 points viennent du site.
    """
    day_start_ms = int(day.replace(tzinfo=timezone.utc).timestamp()) * 1000
    obs_by_st = {f"{r['source']}:{r['station_id']}": to_obs_samples(r) for r in obs_day}
    prev_by_st = {f"{r['source']}:{r['station_id']}": to_obs_samples(r) for r in obs_prev}

    # Le régime s'établit une fois par balise, sur le snapshot le plus
    # frais : c'est celui qui décrit le mieux la journée qui a eu lieu.
    ref_by_st: dict[str, dict] = {}
    for row in snapshots.get(0, []):
        if "aloft_speed" in row:
            ref_by_st[f"{row['source']}:{row['station_id']}"] = row

    regimes: dict[str, str] = {}
    for key, obs in obs_by_st.items():
        regimes[key] = day_regime(ref_by_st.get(key), obs, day_start_ms, utc_offset_s)

    rows: list[dict] = []
    banded: list[dict] = []
    #: (modèle, échéance) → (pente, cap, balise) du dernier échantillon,
    #: la matière du témoin ci-dessous.
    dernier_prior: dict[tuple, tuple] = {}
    for offset, lead_h in LEAD_BY_OFFSET.items():
        for row in snapshots.get(offset, []):
            key = f"{row['source']}:{row['station_id']}"
            obs = obs_by_st.get(key)
            if not obs:
                continue
            times = fcst_times_ms(row)
            idx = [i for i, t in enumerate(times)
                   if day_start_ms <= t < day_start_ms + DAY_MS]
            if not idx:
                continue
            sub_t = [times[i] for i in idx]
            sub_s = [(row.get("speed") or [None] * len(times))[i] for i in idx]
            sub_d = [(row.get("dir") or [None] * len(times))[i] for i in idx]
            pairs = S.pair_series(sub_t, sub_s, sub_d, obs)
            if len(pairs) < MIN_HOURS_DAILY:
                continue

            # La persistance a besoin de la VEILLE : sans elle, le skill
            # n'est pas calculable et il vaut mieux le dire que de le
            # remplacer par autre chose.
            obs_for_skill = (prev_by_st.get(key) or []) + obs
            err = S.series_error(pairs)
            skill, n_skill, mse_m, mse_r = S.skill_vs_persistence(pairs, obs_for_skill)
            bias = S.site_bias(pairs, min_pairs=MIN_HOURS_DAILY)
            ordered = sorted(err.per_hour)
            p90 = (ordered[min(len(ordered) - 1, math.floor(len(ordered) * 0.9))]
                   if len(ordered) >= 5 else None)
            # ⚠️ `.timestamp()` sur un datetime NAÏF lit l'heure locale de
            # la machine, pas UTC. collect.py écrit bien un offset
            # (`datetime.now(timezone.utc).isoformat()`), mais une archive
            # écrite autrement — ou relue sur une machine en CEST — verrait
            # `lead_exact_h` glisser de deux heures sans que rien ne le
            # signale. On tranche ici plutôt que de faire confiance.
            emitted_dt = datetime.fromisoformat(row["fetched_at"])
            if emitted_dt.tzinfo is None:
                emitted_dt = emitted_dt.replace(tzinfo=timezone.utc)
            emitted = int(emitted_dt.timestamp()) * 1000
            lead_exact = sum(t - emitted for t in (p.t for p in pairs)) / len(pairs) / 3_600_000

            # ── seconde référence : la climatologie horaire (lot G4) ──
            # ⚠️ `mse_clim` sort À CÔTÉ de `mse_persist`, jamais à sa
            # place. Les deux répondent à des questions différentes, et
            # remplacer l'une par l'autre reviendrait à changer la
            # question sans changer le nom de la réponse.
            mse_c = None
            if clim:
                c = clim.get(key)
                if c:
                    _, _, _, mse_c = INF.skill_vs_climatology(pairs, c, utc_offset_s)

            # ── la colonne corrigée du biais de site (lot S2) ─────────
            # ⛔ L'ANTÉCÉDENT NE CONTIENT JAMAIS LE JOUR J. Il est bâti
            # par `prior_biais` sur [J−30, J−1] et passé tout fait : il
            # n'y a, dans cette fonction, aucun chemin par lequel la
            # journée qu'on note pourrait entrer dans sa propre
            # correction. C'est le seul garde-fou qui compte ici, et
            # `test_score.py` le vérifie en lui donnant un antécédent
            # que J contredit.
            err_corr = mse_corr = n_bias = None
            pente_j = pente_du_jour(pairs)
            if bias_prior:
                prior = bias_prior.get((key, row["model"], lead_h))
                if prior:
                    pente, cap, n_bias = prior
                    cp = S.apply_bias(pairs, S.SiteBias(pente, cap, len(pairs)))
                    err_corr = S.series_error(cp).med
                    _, _, mse_corr, _ = S.skill_vs_persistence(cp, obs_for_skill)
                    # ── le témoin ────────────────────────────────────
                    # On applique à CETTE balise l'antécédent d'une
                    # AUTRE : la précédente balise échantillonnée du
                    # même modèle et de la même échéance. Si l'erreur
                    # tombe quand même, ce qui tombe n'est pas du site.
                    # Une balise-jour sur `BIAIS_TEMOIN_PAS`, pour que
                    # le coût reste une fraction du run.
                    if temoin is not None and len(rows) % BIAIS_TEMOIN_PAS == 0:
                        autre = dernier_prior.get((row["model"], lead_h))
                        if autre is not None and autre[2] != key:
                            pp = S.apply_bias(
                                pairs, S.SiteBias(autre[0], autre[1], len(pairs)))
                            temoin.append((err.med, err_corr,
                                           S.series_error(pp).med))
                        dernier_prior[(row["model"], lead_h)] = (pente, cap, key)

            rows.append({
                "day": day.strftime("%Y-%m-%d"),
                "source": row["source"], "station_id": row["station_id"],
                "model": row["model"], "lead_h": lead_h,
                "fcst_src": "own_archive",
                "lead_exact_h": round(lead_exact, 2),
                "regime": regimes.get(key, "unknown"),
                "n_hours": err.n,
                "err_vec_rms": _r(err.rms), "err_vec_med": _r(err.med),
                "err_vec_p90": _r(p90),
                "mse_model": _r(mse_m), "mse_persist": _r(mse_r),
                "mse_clim": _r(mse_c),
                "bias_ratio": _r(bias.speed_ratio),
                "bias_dir_deg": _r(bias.dir_offset),
                "vector_ratio": _r(err.vector_ratio),
                # ── lot S2 ────────────────────────────────────────────
                # `bias_slope` est la pente du jour J : elle ne sert PAS
                # à corriger J (ce serait la fuite), elle nourrit
                # l'antécédent de J+1. C'est pour elle que le cache de
                # rejeu change de formule.
                "bias_slope": _r(pente_j),
                "err_vec_med_corr": _r(err_corr),
                "mse_model_corr": _r(mse_corr),
                "bias_n_days": n_bias,
            })

            # ── détail par tranche de vent OBSERVÉE ──
            by_band: dict[str, list[S.VerifPair]] = defaultdict(list)
            for p in pairs:
                by_band[S.wind_band(p.obs_speed)].append(p)
            for band, bp in by_band.items():
                if len(bp) < 3:
                    continue
                be = S.series_error(bp)
                ratios = [p.obs_speed / p.fcst_speed for p in bp
                          if p.fcst_speed >= S.BIAS_MIN_WIND_KMH]
                offs = [S.angular_diff(p.fcst_dir, p.obs_dir) for p in bp
                        if p.fcst_dir is not None and p.obs_dir is not None
                        and p.fcst_speed >= S.BIAS_MIN_WIND_KMH
                        and p.obs_speed >= S.BIAS_MIN_WIND_KMH]
                bskill, _, bmm, bmr = S.skill_vs_persistence(bp, obs_for_skill)
                banded.append({
                    "key": key, "model": row["model"], "lead_h": lead_h,
                    "regime": regimes.get(key, "unknown"), "band": band,
                    "errKmh": be.med,
                    "speedRatio": S.median(ratios),
                    "dirOffset": S.median(offs),
                    "mseModel": bmm, "msePersist": bmr,
                })
    return rows, banded


def _r(x, nd: int = 4):
    return None if x is None or not S._finite(x) else round(float(x), nd)


# ══════════════════════════════════════════════════════════════════
#  LE BIAIS DE SITE APPLIQUÉ — la colonne corrigée (lot S2, 22/08/2026)
# ══════════════════════════════════════════════════════════════════
#
#  Conception et mesures : `claude/lot-s2-erreur-corrigee-22-08.md`.
#  ⛔ LA DÉCISION D N'EST PAS ROUVERTE. Le score de référence reste le
#  BRUT — c'est lui que le pilote voit. Ce qui suit publie une SECONDE
#  colonne, nommée comme telle, qui dit ce qu'un MOS donnerait.
#
#  ═══ POURQUOI UN ESTIMATEUR NEUF ET PAS `S.site_bias` ═══
#
#  `S.site_bias` rend la MÉDIANE de `obs/prev` sur les seules heures où
#  `fcst_speed >= BIAS_MIN_WIND_KMH` (8 km/h). Conditionner sur la
#  PRÉVISION sélectionne les heures où le modèle est haut : si l'erreur
#  est bruitée, `obs/prev` y est mécaniquement inférieur à 1 même quand
#  le modèle ne surestime rien. C'est un retour vers la moyenne, pas un
#  biais de site.
#
#  ⛔ MESURÉ, PAS SUPPOSÉ — 40 539 heures appariées, 19→21/08/2026,
#  ECMWF IFS 0,25° :
#
#      med(obs/prev | prev ≥ 8)  = 0,761      ← ce que `site_bias` rend
#      med(obs/prev | prev ≥ 1)  = 1,003
#      Σobs / Σprev              = 1,112
#      Σ(obs·prev) / Σ(prev²)    = 0,894      ← la pente ci-dessous
#      med(obs/prev | obs ≥ 8)   = 1,514      ← le miroir, qui prouve
#                                               que c'est la sélection
#
#  Un estimateur qui rend 0,76 et 1,51 selon le côté sur lequel on
#  conditionne ne mesure pas le vent, il mesure son propre seuil.
#
#  ⇒ On prend la PENTE DES MOINDRES CARRÉS `Σ(obs·prev) / Σ(prev²)`,
#  sur TOUTES les heures appariées, sans seuil. C'est l'estimateur qui
#  minimise l'erreur quadratique — c'est-à-dire exactement la quantité
#  que `mse_model_corr` publie — et il est insensible à la sélection
#  parce qu'il ne trie aucune heure.
#
#  ⚠️ IL VIT ICI ET PAS DANS `scoring.py`, DÉLIBÉRÉMENT. `scoring.py`
#  est tenu au flottant près par son jumeau `verifScore.ts` et par
#  `parity-scoring.ts` ; y poser une fonction neuve obligerait à écrire
#  le jumeau TS le même jour pour une arithmétique que le navigateur
#  n'appelle jamais. `S.apply_bias`, lui, est bien réutilisé tel quel :
#  la CORRECTION est commune, seule son ESTIMATION est locale.
#
#  ═══ ET POURQUOI L'ANTÉCÉDENT VIENT DES JOURS < J ═══
#
#  Corriger le jour J avec le biais mesuré le jour J, c'est noter une
#  prévision qui a vu sa propre réponse : l'erreur tomberait de moitié
#  sans qu'aucun modèle n'ait rien appris. L'antécédent est donc une
#  EWMA (demi-vie 30 j, même arithmétique en sommes que
#  `S.accumulate` — cf. son avertissement sur le biais d'initialisation)
#  arrêtée la VEILLE, reconstruite depuis le cache de rejeu.
#
#  ⚠️ PAR BALISE, PAS PAR `model_character`. L'accumulateur de
#  `model_character` ne garde AUCUN état historique : il n'a que sa
#  valeur d'aujourd'hui, laquelle a déjà intégré le jour J. L'utiliser
#  pour corriger une journée rejouée serait précisément la fuite
#  ci-dessus. La mesure dit en plus que le niveau ne change presque
#  rien : 29,4 % de gain par balise contre 28,9 % par case fine.

#: Demi-vie de l'antécédent, en jours. Identique à `S.HALF_LIFE_DAYS` —
#: écrite ici parce qu'elle décrit CETTE mémoire-ci, et qu'aligner les
#: deux par hasard n'est pas les aligner.
BIAIS_DEMI_VIE_J = 30

#: Profondeur de cache lue pour bâtir l'antécédent d'une journée.
BIAIS_PRIOR_JOURS = 30

#: Sous ce nombre de journées intégrées, la correction ne sort pas :
#: `err_vec_med_corr` et consorts restent à `None`. Une pente tirée de
#: deux journées est une pente de deux journées, pas un caractère.
BIAIS_MIN_JOURS = 3

#: Heures appariées minimales pour que la pente d'UNE journée soit
#: calculée. Même seuil que `MIN_HOURS_DAILY` : une journée qui mérite
#: une ligne mérite une pente.
BIAIS_MIN_HEURES = MIN_HOURS_DAILY

#: Garde-fous de sanité sur la pente appliquée. ⛔ Hors de ces bornes on
#: ne corrige PAS — on ne rabote pas la valeur. Une pente de 0,2 ou de 4
#: ne dit pas « ce site est très abrité », elle dit « quelque chose ne
#: va pas » (mât cassé, coordonnées fausses, unité mélangée), et publier
#: une correction dessus donnerait un chiffre lisse et faux.
BIAIS_PENTE_MIN = 0.4
BIAIS_PENTE_MAX = 2.5

#: Écart de cap maximal appliqué, en degrés. Au-delà, la girouette est
#: probablement mal orientée sur son mât — c'est une réparation de
#: terrain, pas une correction de modèle.
BIAIS_CAP_MAX_DEG = 90.0

#: Une balise-jour sur N reçoit AUSSI la correction d'une AUTRE balise,
#: pour mesurer la part du gain qui n'est pas du site (§ témoin).
BIAIS_TEMOIN_PAS = 7


def pente_du_jour(pairs) -> float | None:
    """Pente des moindres carrés `Σ(obs·prev) / Σ(prev²)` d'une journée.

    ⚠️ SANS ORDONNÉE À L'ORIGINE, et c'est voulu : une correction
    multiplicative se compose (deux jours à ×0,8 font ×0,64) et
    s'accumule donc en log, ce qu'une affine ne sait pas faire. C'est
    aussi la forme que `S.apply_bias` sait appliquer, et le lot S2 ne
    change pas la correction, seulement son estimation.

    ⚠️ Sur la FORCE seule. Le cap a son propre estimateur (l'écart
    circulaire médian de `S.site_bias`), qui, lui, conditionne des DEUX
    côtés (`fcst_speed >= 8` ET `obs_speed >= 8`) — une condition
    symétrique ne fabrique pas le biais qu'elle mesure, et une girouette
    sous 8 km/h raconte vraiment n'importe quoi.

    ⚠️ L'ARITHMÉTIQUE VIT DANS `scoring.py`, PAS ICI — et c'est le second
    commit du lot S2 qui l'y a mise, en réparant `S.site_bias` du même
    coup. Cette fonction n'est plus qu'un GARDE : le seuil d'heures
    propre au rejeu quotidien. Deux copies de `Σof/Σff` dans le projet
    auraient été exactement la duplication non vérifiée contre laquelle
    l'en-tête de `scoring.py` met en garde.
    """
    if len(pairs) < BIAIS_MIN_HEURES:
        return None
    return S.pente_moindres_carres(pairs)


class AccBiais:
    """EWMA à poids temporel, en SOMMES — le patron de `S.Accumulator`.

    On refait ici les trois lignes plutôt que d'importer l'accumulateur
    de `scoring.py` parce que celui-ci porte `sum_wx2` (la variance) et
    une identité de ligne `model_character` dont on n'a que faire, et
    parce qu'il est tenu par la parité TS. Deux sommes suffisent.
    """
    __slots__ = ("sum_w", "sum_wx", "days", "last_day")

    def __init__(self):
        self.sum_w = 0.0
        self.sum_wx = 0.0
        self.days = 0
        self.last_day = None

    def push(self, day_i: int, x: float) -> None:
        if x is None or not S._finite(x):
            return
        # Une journée déjà intégrée ne se réintègre pas : le rejeu doit
        # pouvoir repasser deux fois sans épaissir la mémoire.
        if self.last_day is not None and day_i <= self.last_day:
            return
        decay = (1.0 if self.last_day is None
                 else 2 ** (-(day_i - self.last_day) / BIAIS_DEMI_VIE_J))
        self.sum_w = self.sum_w * decay + 1
        self.sum_wx = self.sum_wx * decay + x
        self.days += 1
        self.last_day = day_i

    @property
    def mean(self) -> float | None:
        return self.sum_wx / self.sum_w if self.sum_w > 0 else None


def _jour_index(day: datetime) -> int:
    return (day.replace(tzinfo=timezone.utc) - datetime(2026, 1, 1,
                                                        tzinfo=timezone.utc)).days


def prior_biais(root: pathlib.Path, day: datetime,
                n_jours: int = BIAIS_PRIOR_JOURS) -> dict:
    """L'antécédent du jour `day`, bâti sur les jours STRICTEMENT avant.

    Rend `{(unit, model, lead): (pente, ecart_cap_deg, n_jours)}`.

    ⚠️ NE LIT QUE LE CACHE DE REJEU, jamais l'archive. Recalculer trente
    journées pour corriger une journée coûterait trente fois le run, et
    le cache EST la projection rejouable de l'archive — c'est même son
    unique raison d'être. Conséquence assumée et publiée : tant que le
    cache est creux, `bias_n_days` est petit et la correction se tait
    d'elle-même sous `BIAIS_MIN_JOURS`. Elle s'approfondit à mesure que
    `--replay-budget` comble le passé, et `bias_n_days` voyage à côté de
    chaque chiffre pour que personne n'ait à le deviner.

    ⛔ Et le cache d'une AUTRE formule est déjà refusé par
    `replay_read` : un antécédent ne peut donc pas mélanger deux
    définitions de la pente.
    """
    acc_pente: dict[tuple, AccBiais] = {}
    acc_cap: dict[tuple, AccBiais] = {}
    for k in range(n_jours, 0, -1):          # du plus ancien au plus récent
        d = day - timedelta(days=k)
        rows = replay_read(root, d)
        if not rows:
            continue
        di = _jour_index(d)
        for r in rows:
            pente = r.get("bias_slope")
            cap = r.get("bias_dir_deg")
            if pente is None and cap is None:
                continue
            key = (f"{r['source']}:{r['station_id']}", r["model"], r["lead_h"])
            if pente is not None and pente > 0:
                acc_pente.setdefault(key, AccBiais()).push(di, math.log(pente))
            if cap is not None:
                acc_cap.setdefault(key, AccBiais()).push(di, cap)
    out: dict[tuple, tuple] = {}
    for key in set(acc_pente) | set(acc_cap):
        ap = acc_pente.get(key)
        ac = acc_cap.get(key)
        n = ap.days if ap else 0
        if n < BIAIS_MIN_JOURS:
            continue
        pente = math.exp(ap.mean) if ap and ap.mean is not None else None
        if pente is not None and not (BIAIS_PENTE_MIN <= pente <= BIAIS_PENTE_MAX):
            pente = None
        cap = ac.mean if ac and ac.mean is not None else None
        if cap is not None and abs(cap) > BIAIS_CAP_MAX_DEG:
            cap = None
        if pente is None and cap is None:
            continue
        out[key] = (pente, cap, n)
    return out


def bilan_temoin(temoin: list) -> dict | None:
    """Ce que la correction gagne, et ce qu'un HASARD gagnerait.

    ⛔ CE CHIFFRE EST LA MOITIÉ DU LIVRABLE DU LOT S2. Mesuré le 22/08
    sur 30 268 balise-jours : le vrai antécédent fait tomber l'erreur
    médiane de 29,4 %, et celui d'une balise tirée au sort la fait
    tomber de 13,0 %. Autrement dit, **44 % du gain affiché n'est pas du
    biais de site** — c'est un rétrécissement de la prévision, qui
    réduit une erreur quadratique dès lors que la prévision est bruitée,
    quelle que soit la balise dont vient le facteur.

    Publier « corrigé −29 % » sans ce témoin serait exact et trompeur à
    la fois. Il sort donc dans le journal du run ET dans le `meta` du
    JSON publié, à côté du chiffre qu'il tempère.
    """
    if len(temoin) < 30:
        return None
    brut = S.median([t[0] for t in temoin])
    corr = S.median([t[1] for t in temoin])
    plac = S.median([t[2] for t in temoin])
    if not brut:
        return None
    g_corr = 100 * (brut - corr) / brut
    g_plac = 100 * (brut - plac) / brut
    return {
        "n": len(temoin),
        "err_brut": _r(brut, 3), "err_corr": _r(corr, 3),
        "err_placebo": _r(plac, 3),
        "gain_pct": _r(g_corr, 1), "gain_placebo_pct": _r(g_plac, 1),
        "part_site_pct": _r(g_corr - g_plac, 1),
        "texte": (f"sur {len(temoin)} balise-jours échantillonnés, le vrai "
                  f"antécédent gagne {g_corr:.1f} % et celui d'une AUTRE "
                  f"balise {g_plac:.1f} % — la part imputable au site est "
                  f"{g_corr - g_plac:.1f} point(s), le reste est un "
                  f"rétrécissement de la prévision"),
    }


# ══════════════════════════════════════════════════════════════════
#  PRESSION (E6) — lot S1, 21/08/2026
# ══════════════════════════════════════════════════════════════════
#
#  Conception complète : `claude/lot-s1-conception-appariement-21-08.md`.
#
#  ⛔ POURQUOI UNE FONCTION SŒUR DE `daily_rows` ET PAS UNE BRANCHE DEDANS
#
#  `daily_rows` boucle sur les PRÉVISIONS et rend une ligne par (point de
#  prévision × modèle × échéance), avec `source:station_id` = le point de
#  prévision, parce que pour le vent les deux bouts SONT le même point.
#
#  Ici, non. `pmsl` n'est archivé qu'aux ~648 coordonnées Pioupiou, qui
#  ne mesurent jamais de pression ; les réseaux qui en mesurent sont
#  ailleurs. Les lignes de pression sont donc clé par la station
#  D'OBSERVATION, sur une autre population, avec d'autres colonnes et
#  d'autres refus. Les faire cohabiter dans une seule boucle demanderait
#  un `if` à chaque étape — c'est-à-dire le pansement que le lot S1
#  refusait explicitement.
#
#  ⇒ `daily_rows` N'EST PAS MODIFIÉE. Les 168 assertions de
#  `test_score.py` ne peuvent pas bouger : le code qu'elles couvrent
#  n'est pas touché. La preuve n'est pas « le banc est vert », c'est
#  « le diff ne contient pas `daily_rows` ».

#: ⛔ QUELLES VARIABLES ONT LE DROIT D'ÊTRE APPARIÉES GÉOGRAPHIQUEMENT.
#: `geopair` ne connaît aucune variable — c'est ICI, et seulement ici,
#: que l'autorisation se donne, avec sa raison écrite.
#:
#: ⛔ `wind` N'Y EST PAS, ET CE N'EST PAS UN OUBLI. Le vent à 10 m d'une
#: balise de décollage n'est pas un champ synoptique décalé de quelques
#: kilomètres : c'est le vent DE CE SITE-LÀ, et le lot S2 existe tout
#: entier parce que ce biais de site est énorme. Apparier un METAR
#: d'aérodrome au Pioupiou d'une crête à 30 km produirait des lignes, un
#: `n` et un classement — tous faux, et indistinguables d'un vrai une
#: fois publiés.
GEOPAIR_VARIABLES = {
    "pres": {
        # Budget de bruit : le déplacement ne doit pas ajouter plus de
        # ~0,25 hPa d'erreur MÉDIANE, soit moins que les 0,3 hPa que le
        # projet accepte déjà sur toute conversion QNH → QFF
        # (`QFF_CONVERSION_UNCERTAINTY_HPA`, pressure.ts).
        # Conséquence MESURÉE le 21/08 sur 168 stations Météo-France
        # calibrées (48 h) : 50 km rend 0,243 hPa, 100 km en rendrait
        # 0,386. Ce n'est PAS `PRESSURE_MAX_KM` (25 km), qui répond à
        # une autre question — cf. §2 de la note de conception.
        "max_km": 50.0,
        # 300 m est le coude mesuré : à moins de 30 km, 300-600 m de
        # dénivelé coûtent 0,286 hPa, soit autant que 60-100 km à
        # altitude égale. Sans cette borne, un Pioupiou de crête se
        # ferait apparier à une station de plaine et le désaccord des
        # deux réductions serait compté comme une erreur de modèle.
        "max_dz_m": 300.0,
        # = `PRESSURE_MAX_ALT` de pressure.ts (03/08, Samedan LSZS :
        # Q1025 quand toute la Suisse était à Q1013-1018, et 2 à 3 hPa
        # de trop MÊME après conversion en QFF). S'applique aux DEUX
        # bouts : le `pressure_msl` d'un point à 2 000 m est la même
        # fiction, réduite depuis l'orographie du modèle.
        "max_alt_m": S.PRESSURE_MAX_ALT,
    },
}

#: Le champ où vit la pression, par source, et la convention à lui
#: appliquer. Le défaut (`pres_hpa` + `pres_kind` de la ligne) est celui
#: du schéma du S0.2 ; METAR est archivé depuis le 08/08 avec un schéma
#: antérieur, d'où l'entrée explicite. Deux entrées, pas quatre `if`.
PRES_FIELDS = {
    "metar": {"value": "qnh", "kind": "qnh", "temp": "t2m"},
}

#: ⛔ LES SEULS RÉSEAUX SUR LESQUELS `pres_err_med` A UN SENS.
#: Mesuré le 21/08 sur 764 stations Infoclimat : l'écart médian entre
#: deux baromètres amateurs distants de MOINS DE 5 KM est de 1,18 hPa,
#: et il n'atteint 1,82 qu'à 200 km — la dispersion de calage écrase
#: complètement le signal spatial. Sur les mêmes stations, la fonction
#: de structure de la TENDANCE colle à celle de Météo-France à moins de
#: 0,04 hPa : les décalages constants s'y annulent. D'où la règle, qui
#: n'est plus une intuition : `pres_err_med` sur les calibrés,
#: `ptend_err_med` sur tout le monde.
PRES_CALIBRATED = frozenset({"metar", "mf", "aemet", "smn"})


def obsmetar_key(day: datetime) -> str:
    """L'archive METAR (225 aérodromes Iowa State, depuis le 08/08).

    ⛔ ELLE N'EST PAS DANS `OBS_KEY_FUNCS`, ET ELLE N'Y ENTRE PAS ICI.
    `OBS_KEY_FUNCS` alimente la notation du VENT, et le vent d'un
    aérodrome n'a aucun point de prévision à sa propre coordonnée :
    l'y ajouter produirait zéro ligne aujourd'hui, et la première
    personne à voir ce zéro serait tentée de « le réparer » avec
    `geopair`. Le S1 lit `obsmetar/` pour la PRESSION seulement.
    """
    return f"obsmetar/{day:%Y/%m}/obsmetar_{day:%Y-%m-%d}.ndjson.gz"


#: Toutes les clés d'archive susceptibles de porter une PRESSION.
#: METAR d'abord (le seul rempli à 100 %), puis les trois flux du S0.2.
PRES_OBS_KEY_FUNCS = [obsmetar_key, obsinfoclimat_key, obsmf_key, obsaemet_key]


def pres_obs_rows(root: pathlib.Path, day: datetime, storage=None) -> list[dict]:
    """Les observations de PRESSION de toutes les sources, une journée.

    Même principe que `all_obs_rows` : une fonction qui fusionne, jamais
    un `if` par réseau semé ailleurs. Un objet absent rend `[]`, donc une
    source qui n'existe pas encore ne casse rien — c'est le cas normal
    des premières nuits de chaque flux (les collecteurs du S0.2 ont été
    déployés le 21/08 : la première journée archivée est le 22/08).
    """
    rows: list[dict] = []
    for key_fn in PRES_OBS_KEY_FUNCS:
        rows += read_ndjson(root, key_fn(day), storage)
    return rows


def pres_samples(row: dict, refus: dict | None = None) -> list[S.PresSample]:
    """Une ligne d'archive → des relevés RAMENÉS EN QFF, ou rien.

    ⚠️ La réduction se fait ICI, une seule fois, avec l'altitude
    DÉCLARÉE PAR LA SOURCE (`elev`) — jamais `dem_alt_m`, qui ne sert
    qu'aux seuils d'appariement : 28 m d'erreur décalaient Lugano de
    3,3 hPa (mesuré le 03/08).

    Chaque refus est COMPTÉ dans `refus` plutôt que silencieux : une
    population qui rétrécit sans dire pourquoi se relit six mois plus
    tard comme « le modèle s'est amélioré ».
    """
    src = row.get("source") or ""
    spec = PRES_FIELDS.get(src)
    if spec:
        vals = row.get(spec["value"]) or []
        kind = spec["kind"]
        temps = row.get(spec["temp"]) or [] if spec.get("temp") else []
    else:
        vals = row.get("pres_hpa") or []
        # `pres_kind` est CONSTANT par ligne dans le schéma du S0.2.
        # Absent → `to_qff` refusera avec `unknown-kind`, et le comptera.
        kind = row.get("pres_kind") or ""
        temps = []
    if not vals:
        return []
    ts = row.get("t") or []
    elev = row.get("elev")
    out: list[S.PresSample] = []
    for i, t in enumerate(ts):
        if i >= len(vals):
            break
        temp = temps[i] if i < len(temps) else None
        qff, motif = S.to_qff(vals[i], kind, elev, temp)
        if qff is None:
            if refus is not None and motif:
                refus[motif] = refus.get(motif, 0) + 1
            continue
        out.append(S.PresSample(t=int(t) * 1000, qff=qff))
    return out


def pressure_rows(day: datetime, snapshots: dict[int, list[dict]],
                  pres_obs: list[dict], zone_of: dict | None = None):
    """Les agrégats quotidiens de PRESSION. Rend (lignes, bilan lisible).

    Une ligne par (station d'observation × modèle × échéance), clé par la
    station QUI MESURE — jamais par le point Pioupiou dont vient la
    prévision. Publier `pioupiou:123` sur une erreur mesurée à Ambérieu
    serait un mensonge dans la clé primaire, et plus personne ne pourrait
    s'en apercevoir. Le point utilisé voyage dans `pair_source` /
    `pair_station_id`, avec `pair_km` et `pair_dz_m`.

    ⚠️ L'APPARIEMENT EST CALCULÉ UNE SEULE FOIS, PAS UNE PAR ÉCHÉANCE.
    Sinon une même station pourrait être notée contre un point à +6 h et
    contre un AUTRE point à +48 h, et la comparaison entre échéances —
    qui est exactement ce que l'écran affiche — mélangerait deux
    géométries. L'appariement est une propriété des positions, pas de
    l'échéance.
    """
    import geopair as GP                      # noqa: PLC0415

    conf = GEOPAIR_VARIABLES["pres"]
    day_start_ms = int(day.replace(tzinfo=timezone.utc).timestamp()) * 1000
    zone_of = zone_of or {}

    def dem(cle: str):
        z = zone_of.get(cle)
        return z.get("dem_alt_m") if z else None

    # ── les candidats : les points de prévision qui portent `pmsl` ──
    # Un champ ABSENT veut dire « ce modèle ne sert pas cette variable
    # ici » (cf. `collect.py`, extension du format du 08/08) — ce n'est
    # pas une absence de valeur, c'est une absence de série.
    points: dict[str, dict] = {}
    par_point: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for offset in LEAD_BY_OFFSET:
        for row in snapshots.get(offset, []):
            if not row.get("pmsl"):
                continue
            cle = f"{row['source']}:{row['station_id']}"
            points.setdefault(cle, {"cle": cle, "lat": row["lat"],
                                    "lon": row["lon"], "dem_alt_m": dem(cle)})
            par_point[cle].append((offset, row))

    # ── les cibles : les stations qui mesurent une pression ce jour-là ──
    refus: dict[str, int] = {}
    cibles, obs_par_cle = [], {}
    for row in pres_obs:
        cle = f"{row['source']}:{row['station_id']}"
        ech = pres_samples(row, refus)
        if not ech:
            continue
        cibles.append({"cle": cle, "lat": row["lat"], "lon": row["lon"],
                       "dem_alt_m": dem(cle), "elev": row.get("elev")})
        obs_par_cle[cle] = (row, ech)

    appariement, bilan = GP.apparier(
        cibles, list(points.values()),
        max_km=conf["max_km"], max_dz_m=conf["max_dz_m"],
        max_alt_m=conf["max_alt_m"])

    rows: list[dict] = []
    for cle, (obs_row, ech) in obs_par_cle.items():
        ap = appariement.get(cle)
        if ap is None:
            continue                # « pas de modèle assez proche », jamais un 0
        calibre = obs_row["source"] in PRES_CALIBRATED
        for offset, frow in par_point.get(ap.cle, []):
            times = fcst_times_ms(frow)
            pmsl = frow.get("pmsl") or []
            idx = [i for i, t in enumerate(times)
                   if day_start_ms <= t < day_start_ms + DAY_MS]
            if not idx:
                continue
            pairs = S.pair_pressure([times[i] for i in idx],
                                    [pmsl[i] if i < len(pmsl) else None
                                     for i in idx], ech)
            if len(pairs) < MIN_HOURS_DAILY:
                continue
            emitted_dt = datetime.fromisoformat(frow["fetched_at"])
            if emitted_dt.tzinfo is None:
                emitted_dt = emitted_dt.replace(tzinfo=timezone.utc)
            emitted = int(emitted_dt.timestamp()) * 1000
            lead_exact = sum(p.t - emitted for p in pairs) / len(pairs) / 3_600_000
            rows.append({
                "day": day.strftime("%Y-%m-%d"),
                "source": obs_row["source"], "station_id": obs_row["station_id"],
                "model": frow["model"], "lead_h": LEAD_BY_OFFSET[offset],
                "fcst_src": "own_archive",
                "lead_exact_h": round(lead_exact, 2),
                "n_hours": len(pairs),
                # ⛔ `None`, pas 0, sur les baromètres non calibrés — la
                # ligne existe (sa tendance est valable), mais son erreur
                # absolue n'a pas de sens et un 0 se lirait comme un
                # modèle parfait.
                "pres_err_med": _r(S.pressure_error(pairs), 3) if calibre else None,
                "ptend_err_med": _r(S.tendency_error(pairs), 3),
                "pres_kind": (PRES_FIELDS.get(obs_row["source"], {}).get("kind")
                              or obs_row.get("pres_kind")),
                "calibrated": calibre,
                "pair_source": ap.cle.split(":", 1)[0],
                "pair_station_id": ap.cle.split(":", 1)[1],
                "pair_km": _r(ap.km, 2),
                "pair_dz_m": _r(ap.dz_m, 1),
            })

    detail = ", ".join(f"{k} {v}" for k, v in sorted(refus.items()))
    resume = (f"{len(rows)} lignes ; {len(points)} points de prévision portent "
              f"`pmsl` ; {bilan.resume()}"
              + (f" ; relevés refusés : {detail}" if detail else ""))
    return rows, resume


# ══════════════════════════════════════════════════════════════════
#  REJEU DE L'ARCHIVE (lot G1)
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ POURQUOI REJOUER PLUTÔT QUE LIRE LES AGRÉGATS.
#
# Le chemin régime posait `worst_decile_kmh = None`, `ci_low = None`,
# `ci_high = None`, `skill = None` — quatre colonnes vides sur
# précisément les lignes qui intéressent un pilote. La cause était
# structurelle : l'accumulateur de `model_character` porte TROIS SOMMES
# (`sum_w`, `sum_wx`, `sum_wx2`). Trois sommes savent faire une moyenne
# et une variance. Elles ne savent pas faire un décile, et aucune
# torsion ne leur en fera produire un — on obtiendrait un nombre qui
# ressemble à un décile sans en être un, ce qui est pire que rien.
#
# Un quantile demande la DISTRIBUTION. Elle existe : dans l'archive R2,
# qui garde les paires brutes et ne se purge jamais. On la rejoue.
#
# ⚠️ ET POURQUOI PAS `model_verif_daily`. Elle porte bien les mêmes
# balise-jours, mais avec 30 jours de rétention et sans garantie
# d'exister pour les journées antérieures au dernier correctif. Le
# rejeu depuis l'archive est la seule source qui remonte aussi loin que
# l'archive elle-même, et la seule qui reste juste quand la formule
# change (il suffit d'incrémenter `REPLAY_FORMULA`).

def replay_path(root: pathlib.Path, day: datetime) -> pathlib.Path:
    return root / REPLAY_SUBDIR / f"replay_{day:%Y-%m-%d}.json.gz"


def replay_write(root: pathlib.Path, day: datetime, rows: list[dict]) -> None:
    """Range une journée déjà calculée à côté de l'archive.

    Appelé avec le résultat de `daily_rows` du run courant : la journée
    notée ce soir est donc mise en cache SANS aucun calcul
    supplémentaire. Le rejeu n'a plus qu'à combler les trous du passé,
    ce qu'il ne fait qu'une fois par journée manquante.
    """
    try:
        p = replay_path(root, day)
        p.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps({"formula": REPLAY_FORMULA,
                           "day": day.strftime("%Y-%m-%d"),
                           "rows": rows}, separators=(",", ":")).encode("utf-8")
        p.write_bytes(gzip.compress(body))
    except OSError as exc:
        print(f"  ⚠️ cache de rejeu non écrit pour {day:%Y-%m-%d} : {exc}",
              file=sys.stderr)


def replay_read(root: pathlib.Path, day: datetime) -> list[dict] | None:
    p = replay_path(root, day)
    if not p.exists():
        return None
    try:
        d = json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))
    except (OSError, ValueError):
        return None
    # Un cache produit par une autre formule est IGNORÉ, pas réparé :
    # mélanger deux formules dans une même fenêtre donnerait une
    # distribution qui n'est celle d'aucune des deux.
    if d.get("formula") != REPLAY_FORMULA:
        return None
    return d.get("rows") or []


def replay_day(root: pathlib.Path, day: datetime, storage,
               utc_offset_s: int) -> list[dict]:
    """Les balise-jours d'UNE journée : du cache, ou recalculés."""
    cached = replay_read(root, day)
    if cached is not None:
        return cached
    snapshots = {off: snapshot_rows(root, day - timedelta(days=off), storage)
                 for off in LEAD_BY_OFFSET}
    # ⚠️ TOUTES LES SOURCES DE VENT, PAS SEULEMENT PIOUPIOU — S0.2, 21/08.
    # `all_obs_rows` fusionne `obs_key` (Pioupiou) et chaque flux ajouté
    # depuis (windsmobi, puis infoclimat/mf/aemet) ; le reste de cette
    # fonction ne change pas, il reçoit juste plus de lignes.
    obs_day = all_obs_rows(root, day, storage)
    if not obs_day:
        replay_write(root, day, [])
        return []
    obs_prev = all_obs_rows(root, day - timedelta(days=1), storage)
    # ⚠️ L'ANTÉCÉDENT DE CETTE JOURNÉE-CI, pas celui d'aujourd'hui. Une
    # journée rejouée doit être corrigée par ce qu'on savait AVANT elle,
    # sinon un rejeu de juillet appliquerait le biais d'août et le
    # « corrigé » serait meilleur que la réalité sur toute la
    # profondeur de l'archive — le genre d'erreur qui ne se voit jamais
    # parce qu'elle va dans le sens qu'on espère.
    rows, _ = daily_rows(day, snapshots, obs_day, obs_prev, utc_offset_s,
                         bias_prior=prior_biais(root, day))
    replay_write(root, day, rows)
    return rows


def replay_window(root: pathlib.Path, day: datetime, storage,
                  utc_offset_s: int, n_days: int = REGIME_REPLAY_DAYS,
                  budget_new_days: int | None = None):
    """La fenêtre rejouée, la plus récente d'abord.

    Rend `(lignes, bilan)`. Chaque ligne porte en plus `unit`
    (« source:station_id »), la clé d'appariement du test du G2.

    ⚠️ `budget_new_days` BORNE LE TRAVAIL D'UNE NUIT. Rejouer trente
    journées jamais vues d'un coup peut multiplier la durée du run par
    trente, et un run qui déborde son timer est un run qui ne finit
    pas. On en rattrape donc quelques-unes par nuit, et — piège n°7 du
    lot G — LE BILAN LE DIT : une fenêtre tronquée en silence se lirait
    comme une fenêtre complète.
    """
    rows: list[dict] = []
    vus, rejoues, manquants, ignores = 0, 0, 0, 0
    for k in range(n_days):
        d = day - timedelta(days=k)
        cached = replay_read(root, d)
        if cached is None:
            if budget_new_days is not None and rejoues >= budget_new_days:
                ignores += 1
                continue
            cached = replay_day(root, d, storage, utc_offset_s)
            rejoues += 1
        if not cached:
            manquants += 1
            continue
        vus += 1
        for r in cached:
            r = dict(r)
            r["unit"] = f"{r['source']}:{r['station_id']}"
            rows.append(r)
    bilan = (f"{len(rows)} balise-jours sur {vus} journées "
             f"({rejoues} rejouée(s) cette nuit, {manquants} vide(s)"
             + (f", {ignores} REPORTÉE(S) faute de budget" if ignores else "")
             + ")")
    return rows, bilan


# ══════════════════════════════════════════════════════════════════
#  CLIMATOLOGIE HORAIRE (lot G4) — la seconde référence
# ══════════════════════════════════════════════════════════════════

CLIM_SUBDIR = "clim"

#: Jours d'observations lus pour établir « le vent habituel ici à cette
#: heure-ci ». Plus long que la fenêtre de score : une climatologie qui
#: bouge chaque nuit n'est pas une climatologie.
CLIM_DAYS = 30

#: Journées distinctes minimales pour qu'une heure soit climatologisée.
CLIM_MIN_DAYS = 5


def climatology_by_station(root: pathlib.Path, day: datetime, storage,
                           utc_offset_s: int, n_days: int = CLIM_DAYS):
    """Le vent HABITUEL de chaque balise, heure locale par heure locale.

    ⚠️ POURQUOI UNE SECONDE RÉFÉRENCE. Le skill se mesure aujourd'hui
    contre la persistance — « l'observation de la même heure la veille ».
    C'est une prévision naïve redoutable sur un site de vol, et c'est la
    bonne référence pour la question « le modèle apporte-t-il quelque
    chose par rapport à hier ». Mais ce n'est pas la question que se pose
    un pilote qui consulte trois jours à l'avance : la sienne est « le
    modèle sait-il quelque chose que je ne sais pas déjà ». Battre la
    climatologie et battre la persistance sont deux exploits différents,
    et un modèle peut réussir l'un en échouant l'autre — typiquement
    quand la veille était atypique.

    ⚠️ Rend `{}` plutôt qu'une climatologie fabriquée quand l'archive est
    trop courte : au 09/08 elle porte deux jours, et « le vent habituel »
    tiré de deux journées serait le vent de ces deux journées-là.
    """
    cache = root / CLIM_SUBDIR / f"clim_{day:%Y-%m-%d}_{n_days}.json.gz"
    if cache.exists():
        try:
            d = json.loads(gzip.decompress(cache.read_bytes()).decode("utf-8"))
            return {u: {int(h): tuple(v) for h, v in hs.items()}
                    for u, hs in d.get("clim", {}).items()}
        except (OSError, ValueError):
            pass

    obs_by_unit_day: dict[str, dict[str, list]] = defaultdict(dict)
    for k in range(n_days):
        d = day - timedelta(days=k)
        for row in all_obs_rows(root, d, storage):
            unit = f"{row['source']}:{row['station_id']}"
            obs_by_unit_day[unit][d.strftime("%Y-%m-%d")] = to_obs_samples(row)

    out: dict[str, dict[int, tuple]] = {}
    for unit, by_day in obs_by_unit_day.items():
        clim = INF.hourly_climatology(by_day, utc_offset_s, CLIM_MIN_DAYS)
        if clim:
            out[unit] = clim
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(gzip.compress(json.dumps(
            {"clim": {u: {str(h): list(v) for h, v in hs.items()}
                      for u, hs in out.items()}},
            separators=(",", ":")).encode("utf-8")))
    except OSError:
        pass
    return out


# ══════════════════════════════════════════════════════════════════
#  ZONES ET REPLI
# ══════════════════════════════════════════════════════════════════
#
# ═══ QUI CRÉE LES LIGNES `model_zone` — décision du 08/08 (lot B) ═══
#
# Trois producteurs se partagent cette table, et la frontière entre eux
# n'est PAS une affaire de goût : elle se lit dans le schéma.
#
#   échelon 1  `b45.28_6.51:valley`   → LE SCRIPT D'AFFECTATION
#   échelon 2  `alpes-nord:valley`    → `zone_rows_needed`, ici
#   échelon 3  `*:valley`             → le SQL (step35), une fois
#   échelon 4  `alpes-nord:*`         → `zone_rows_needed`, ici
#   échelon 5  `*:*`                  → le SQL (step35), une fois
#
# LA RAISON, et pas seulement le comportement : `station_zone.zone_id`
# porte LUI-MÊME une clé étrangère vers `model_zone` (step35 l. 199).
# L'échelon 1 doit donc exister AVANT que la balise ne soit rattachée —
# donc avant que ce job ne voie quoi que ce soit. Aucun autre producteur
# n'est possible, et c'est ce qui tranche la question.
#
# ⚠️ COROLLAIRE, ET IL COMPTE : ce job n'a PAS à rattraper un échelon 1
# manquant, et un tel « filet » serait du code mort par construction. La
# clé étrangère garantit déjà que toute ligne `station_zone` lue ici a sa
# ligne `model_zone`. Écrire ce filet donnerait l'illusion d'une défense
# là où il n'y a rien à défendre — et masquerait que la vraie défense est
# la contrainte, qui échoue tôt, en pleine session, avec un message clair.
#
# Les échelons 2 et 4, eux, ne sont référencés que par `model_score_zone`
# et `model_character`, écrits des heures plus tard : rien ne force leur
# existence, et ce job est le seul à pouvoir les reconstruire depuis les
# lignes `station_zone` qu'il vient de lire. D'où `zone_rows_needed`.

#: Formes de terrain en français, pour les libellés lus dans l'atelier
#: admin. Les mêmes mots que les libellés semés par le SQL (« Fonds de
#: vallée, tous massifs »), pour qu'une liste triée se lise d'un bloc.
LANDFORM_FR = {
    "valley": "Fonds de vallée", "slope": "Versants", "ridge": "Crêtes",
    "plateau": "Plateaux", "plain": "Plaines", "coastal": "Littoral",
}

#: Massifs en français — MIROIR de `MASSIFS` dans `src/lib/zoneClass.ts`,
#: qui reste la source de vérité. Un identifiant absent d'ici retombe sur
#: lui-même : un libellé moins joli, jamais une ligne manquante.
MASSIF_FR = {
    "alpes-nord": "Alpes du Nord", "alpes-sud": "Alpes du Sud",
    "alpes-suisses": "Alpes suisses", "jura": "Jura", "vosges": "Vosges",
    "pyrenees-ouest": "Pyrénées occidentales",
    "pyrenees-est": "Pyrénées orientales",
    "massif-central": "Massif central", "corse": "Corse",
    "mediterranee": "Pourtour méditerranéen",
    "atlantique": "Façade atlantique", "france-nord": "Moitié nord",
    "france-sud": "Moitié sud", "espagne": "Espagne",
}


def zone_id_for(zone: dict) -> str:
    """L'identifiant de la case fine d'une balise — l'échelon 1.

    Reproduit `zoneClass.assignZone` : le bassin s'il est connu, sinon
    le massif, sinon `*`. Le dernier cas n'est pas un aveu d'échec mais
    la réponse honnête : un point sans bassin ET sans massif n'a pas de
    case à lui, et « cette forme de terrain, partout » est ce qu'on sait
    de plus fin à son sujet.
    """
    head = zone.get("basin_id") or zone.get("massif_id") or "*"
    return f"{head}:{zone['landform']}"


def zone_kind_for(zone: dict) -> str:
    """L'échelon auquel appartient RÉELLEMENT le `zone_id` d'une balise.

    ⚠️ SE DÉDUIT DES COLONNES, JAMAIS DE LA FORME DE LA CHAÎNE. Un
    `LIKE '%*%'` sur l'identifiant est exactement la dépendance au format
    contre laquelle le SQL de step35 met en garde : `kind` y est
    volontairement redondant avec `zone_id` pour qu'on n'ait jamais à
    renifler l'un pour retrouver l'autre.

    ⚠️ ET C'EST AUSSI UN CORRECTIF. Avant le 08/08, `fallback_chain`
    étiquetait le premier échelon `basin_landform` quoi qu'il arrive.
    Une balise sans bassin publiait donc un score `agg_level =
    'basin_landform'` sur une zone dont `model_zone.kind` disait
    `massif_landform` : deux colonnes du même schéma se contredisaient
    sur la même zone, et le score mentait sur sa propre précision — ce
    que la colonne `agg_level` existe précisément pour empêcher.
    """
    if zone.get("basin_id"):
        return "basin_landform"
    if zone.get("massif_id"):
        return "massif_landform"
    return "landform"


def zone_row_for(zone: dict) -> dict | None:
    """La ligne `model_zone` qu'une balise EXIGE pour pouvoir être
    rattachée, ou `None` quand cette ligne est déjà semée par le SQL.

    À appeler par le script d'affectation, AVANT d'écrire `station_zone`
    (cf. la décision ci-dessus). `None` n'est pas un cas dégradé : c'est
    le cas d'une balise dont la case fine est `*:forme`, l'un des sept
    échelons constants posés une fois pour toutes par step35.
    """
    kind = zone_kind_for(zone)
    if kind == "landform":
        return None
    landform = zone["landform"]
    lf = LANDFORM_FR.get(landform, landform)
    massif = zone.get("massif_id")
    basin = zone.get("basin_id")
    if kind == "basin_landform":
        label = f"{lf} du bassin {basin}"
        if massif:
            label += f" ({MASSIF_FR.get(massif, massif)})"
    else:
        label = f"{lf}, {MASSIF_FR.get(massif, massif)}"
    return {"zone_id": zone.get("zone_id") or zone_id_for(zone), "kind": kind,
            "basin_id": basin, "massif_id": massif, "landform": landform,
            "label": label}


def zone_rows_for(zones: list[dict]) -> list[dict]:
    """Les lignes `model_zone` d'échelon 1 d'un lot de balises, dédoublonnées.

    Deux balises de la même vallée partagent leur case fine : sans ce
    dédoublonnage, le même `zone_id` partirait deux fois dans le même
    envoi, ce que PostgREST refuse (« ON CONFLICT ne peut affecter la
    ligne une seconde fois ») — un échec qui n'a rien à voir avec les
    données et tout à voir avec la façon de les envoyer.
    """
    out: dict[str, dict] = {}
    for z in zones:
        row = zone_row_for(z)
        if row:
            out[row["zone_id"]] = row
    return list(out.values())


def write_station_zones(sb, zones: list[dict]) -> tuple[int, int]:
    """Écrit `model_zone` PUIS `station_zone`, dans cet ordre, en upsert.

    ⚠️ L'ORDRE N'EST PAS NÉGOCIABLE et c'est tout l'intérêt de cette
    fonction : un script qui construit les deux jeux en mémoire puis les
    « envoie ensemble » échoue en 23503. Le point d'entrée est ici pour
    que la question ne se repose pas à chaque script d'affectation.

    ⚠️ REJOUABLE. Les deux écritures sont des upserts sur leur clé, donc
    relancer l'affectation sur les mêmes balises réécrit les mêmes
    lignes. `assigned_at` garde la trace du dernier passage.

    Rend (lignes `model_zone` créées ou réécrites, lignes `station_zone`).
    """
    rows = zone_rows_for(zones)
    n_zone = sb.upsert("model_zone", rows, "zone_id") if rows else 0
    n_stat = sb.upsert("station_zone", zones, "source,station_id")
    return n_zone, n_stat


def fallback_chain(zone: dict) -> list[tuple[str, str]]:
    """Les cinq échelons du §16.3, dans l'ordre, avec leur `agg_level`.

    ⚠️ LA FORME PASSE AVANT LE MASSIF (échelon 3 avant échelon 4). Un
    fond de vallée encaissé est mal résolu par une maille de 1,3 km
    dans les Pyrénées comme dans les Alpes, alors qu'une crête et un
    fond de vallée du même massif n'ont pas les mêmes modes d'erreur.

    Reproduit `zoneClass.zoneFallbackChain`, y compris son
    dédoublonnage : quand le bassin manque, la case fine retombe sur
    `massif:forme`, qui serait sinon dupliquée à l'échelon 2.

    ⚠️ LE PREMIER ÉCHELON N'EST PAS TOUJOURS `basin_landform`, et le
    croire était un défaut (corrigé le 08/08) : la case fine d'une
    balise sans bassin EST `massif:forme`, celle d'une balise sans
    bassin ni massif EST `*:forme`. L'étiquette vient donc de
    `zone_kind_for`, la même dérivation que celle qui a servi à écrire
    `model_zone.kind` — de sorte que `agg_level` et `kind` ne peuvent
    plus se contredire sur une même zone.
    """
    landform = zone["landform"]
    massif = zone.get("massif_id")
    chain = [(zone["zone_id"], zone_kind_for(zone))]
    if massif:
        chain.append((f"{massif}:{landform}", "massif_landform"))
    chain.append((f"*:{landform}", "landform"))
    if massif:
        chain.append((f"{massif}:*", "massif"))
    chain.append(("*:*", "global"))
    seen, out = set(), []
    for zid, level in chain:
        if zid in seen:
            continue
        seen.add(zid)
        out.append((zid, level))
    return out


def zone_rows_needed(zones: list[dict]) -> list[dict]:
    """Les lignes `model_zone` que CE JOB doit créer avant d'écrire des
    scores : les échelons `massif:forme` et `massif:*` rencontrés, et
    eux seuls.

    Périmètre exact, décidé le 08/08 (cf. le pavé en tête de section) :

    · `*:forme` et `*:*` sont posés une fois par le fichier SQL —
      inutile de les réécrire chaque nuit ;
    · `bassin:forme` appartient au script d'affectation, parce que la
      clé étrangère de `station_zone.zone_id` l'exige AVANT que la
      balise n'existe. Cette fonction ne le rattrape pas, et ce n'est
      pas un oubli : toute ligne `station_zone` lue par ce job a déjà,
      par contrainte, sa ligne `model_zone`. Un rattrapage ici ne
      pourrait jamais s'exécuter ;
    · restent les échelons 2 et 4, que rien ne force à préexister
      puisqu'ils ne sont référencés que par `model_score_zone` et
      `model_character`, écrits plus loin dans ce même run.
    """
    out: dict[str, dict] = {}
    for z in zones:
        massif = z.get("massif_id")
        if not massif:
            continue
        landform = z["landform"]
        nom = MASSIF_FR.get(massif, massif)
        lf = LANDFORM_FR.get(landform, landform)
        # ⚠️ LES DEUX LIGNES PORTENT EXACTEMENT LES MÊMES CLÉS, y compris
        # celles qui valent `None`. Ce n'est pas de la cosmétique :
        # PostgREST REFUSE un envoi groupé dont les objets n'ont pas le
        # même jeu de clés, avec un `PGRST102 — All object keys must
        # match` qui ne dit ni quelle clé ni quelle ligne.
        #
        # Défaut trouvé le 08/08 sur le PREMIER run réel avec
        # `station_zone` peuplée : `massif:forme` portait `landform`,
        # `massif:*` ne le portait pas, et les 77 lignes partaient dans
        # le même POST. Le défaut était là depuis le lot B, mais il ne
        # pouvait pas se déclencher tant que `station_zone` était vide —
        # `zone_rows_needed` rendait alors une liste vide.
        #
        # La même forme à six clés que `zone_row_for` (l'échelon 1), pour
        # que TOUTE ligne `model_zone` du projet ait la même, quel que
        # soit son producteur.
        out[f"{massif}:{landform}"] = {
            "zone_id": f"{massif}:{landform}", "kind": "massif_landform",
            "basin_id": None, "massif_id": massif, "landform": landform,
            "label": f"{lf}, {nom}"}
        out[f"{massif}:*"] = {
            "zone_id": f"{massif}:*", "kind": "massif",
            "basin_id": None, "massif_id": massif, "landform": None,
            "label": f"{nom}, toutes formes"}
    return list(out.values())


# ══════════════════════════════════════════════════════════════════
#  ACCUMULATEURS
# ══════════════════════════════════════════════════════════════════

#: Ce qu'un accumulateur mesure, et la référence par rapport à laquelle
#: un écart devient un « caractère ».
#: ⚠️ `errKmh`, `mseModel` et `msePersist` N'EXISTENT PAS dans le
#: `TraitMetric` de modelCharacter.ts, et il faudra les y ajouter. Sans
#: eux, le score par régime du §16.1 n'a nulle part où vivre : les
#: quatre métriques d'origine décrivent un BIAIS (« sous-estime le vent
#: fort »), aucune ne porte l'ERREUR TYPIQUE, qui est justement le
#: premier des deux nombres que Yann demande.
#: (définition juste avant `accumulator_updates`, plus bas — la section
#: ÉVÉNEMENTS s'intercale ici parce qu'elle n'a besoin que des zones.)

# ══════════════════════════════════════════════════════════════════
#  ÉVÉNEMENTS — `model_verif_event` (lot F, 08/08)
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ CETTE SECTION ROMPT LE COMMENTAIRE DE `supabase_step35…sql`, ET
# C'EST VOULU. Ce commentaire disait « AUCUN JOB N'ÉCRIT ENCORE ICI, et
# c'est délibéré […] les seuils ne sont calibrés sur rien ». Yann a
# tranché le 08/08 au soir, en connaissance de cause : on écrit et on
# publie, AVEC un drapeau `calibrated: false` qui voyage avec les
# données jusqu'à l'affichage. Le raisonnement complet est en tête
# d'`events.py` — il n'est pas recopié ici pour qu'il n'y ait qu'un seul
# endroit à corriger le jour où les seuils seront mesurés.
#
# ⚠️ CE QUE LE DRAPEAU N'AUTORISE PAS : présenter ces chiffres comme
# calibrés, ici ou dans la PWA.

#: Quorum de balises DISTINCTES pour qu'un événement compte (§3.4).
#: Une girouette qui tourne peut être une bascule, une rafale, un arbre
#: qui a poussé ou un roulement mort ; deux balises de la même case fine
#: qui tournent dans la demi-heure, non.
EVENT_MIN_STATIONS = 2

#: Quorum d'AFFICHAGE : sous ce nombre d'événements réels (succès +
#: ratés), un POD vaut 0, 0,5 ou 1 et ne veut rien dire. Même valeur et
#: même rôle que `S.REGIME_MIN_OCCURRENCES`.
EVENT_MIN_OCCURRENCES = 8

#: Seuil d'établissement/chute. Constante en attendant `ZONE_THRESHOLDS`,
#: dont le recalibrage est hors périmètre de ce lot.
EVENT_ONSET_KMH = 12

#: Les familles qu'on PUBLIE. `reversal` est détecté, apparié et écrit en
#: base comme les autres — mais pas publié, et voici pourquoi.
#:
#: ⚠️ MESURÉ LE 08/08, PAS SUPPOSÉ. Au premier run réel, `reversal`
#: sortait 40 ratés, 0 succès, 0 fausse alarme : aucun des dix modèles
#: n'avait prévu une seule bascule. Avant de publier « POD = 0 » pour
#: tout le monde, on a cherché si c'était de la météo ou un artefact, en
#: dégradant les VRAIES balises à une mesure par heure, comme un modèle :
#:
#:     balises réelles à ~4 min .................. 34 bascules
#:     les mêmes, dégradées à 1 h ................  0 bascule
#:
#: Ce n'est pas de la météo. `hold_ms` vaut 45 min, soit MOINS que le pas
#: horaire d'un modèle : les fenêtres « avant » et « après » ne peuvent
#: jamais contenir deux valeurs horaires distinctes, et la rotation
#: mesurée vaut exactement 0°. Le balayage confirme le seuil net —
#: 45 min : 0 · 60 min : 31 · 75 min : 51 · 90 min : 22 (obs dégradées),
#: contre 34 · 37 · 42 · 42 à pleine cadence.
#:
#: Le défaut est dans `windEvents.ts` autant qu'ici : le portage est
#: fidèle, et le banc de parité le prouve. Publier ce POD dirait « aucun
#: modèle ne prévoit jamais de bascule » alors que la vérité est « notre
#: détecteur ne sait pas voir une bascule dans une série horaire » — une
#: cécité de l'outil attribuée aux modèles. C'est exactement le genre de
#: chiffre que ce chantier refuse d'afficher.
#:
#: ⚠️ ON NE CORRIGE PAS `hold_ms` ICI, ET C'EST DÉLIBÉRÉ. C'est un seuil
#: de détection, donc une décision de calibration : la changer en douce
#: pour faire apparaître des chiffres serait précisément la faute contre
#: laquelle tout le reste de ce fichier met en garde. Arbitrage laissé à
#: Yann, avec les mesures ci-dessus. Les lignes continuent d'être
#: écrites en base pendant ce temps : l'archive R2 permet de tout
#: rejouer le jour où le seuil sera tranché.
EVENT_PUBLISHABLE_TYPES = ("onset", "drop", "ramp", "breeze_yield")

#: ⚠️ VOYAGE JUSQU'AU JSON PUBLIÉ. Passera à `True` le jour où la boucle
#: de calibration (`find-episodes.ts` → `episodeReview.ts`) aura tourné
#: sur quelques dizaines de journées étiquetées en aveugle — pas avant,
#: et surtout pas parce que les chiffres « ont l'air bons ».
EVENTS_CALIBRATED = False


def _series_of(row: dict, day_start_ms: int, aloft: bool = False):
    """Une série de prévision, restreinte à la journée notée.

    ⚠️ ON DÉCOUPE LES DEUX CÔTÉS DE LA MÊME FAÇON, et c'est la raison
    d'être de cette fonction. L'archive d'observations couvre exactement
    la journée UTC ; une prévision, elle, déborde des deux côtés. Si on
    laissait la prévision déborder, le modèle pourrait « voir » une
    bascule à 23 h 50 que l'observation, tronquée, ne peut plus détecter
    faute de fenêtre — et récolterait une fausse alarme pour une
    prévision peut-être juste. Le découpage symétrique fait perdre les
    événements des ~45 premières et dernières minutes de la journée UTC
    des DEUX côtés, ce qui, pour des sites français, tombe au milieu de
    la nuit : aucune brise n'y bascule.

    `aloft=True` rend la série de crête, qui n'est PAS découpée : elle
    n'est jamais détectée, seulement interrogée par `crest_at` avec sa
    propre tolérance de ±90 min, qui a besoin des voisins.
    """
    times = fcst_times_ms(row)
    sp = row.get("aloft_speed" if aloft else "speed") or []
    di = row.get("aloft_dir" if aloft else "dir") or []
    out = []
    for i, t in enumerate(times):
        if not aloft and not (day_start_ms <= t < day_start_ms + DAY_MS):
            continue
        s = sp[i] if i < len(sp) else None
        d = di[i] if i < len(di) else None
        out.append(EV.CrestSample(t=t, speed_kmh=s, dir_deg=d) if aloft
                   else S.ObsSample(t=t, speed=s, dir=d))
    return out


def median_step_ms(series) -> int | None:
    """Le pas RÉEL d'une série, en millisecondes. Médiane des écarts.

    Médiane et pas moyenne : un trou de trois heures au milieu d'une
    journée à 4 min de cadence tirerait la moyenne à 10 min et ferait
    croire à une série grossière là où il n'y a qu'une coupure.
    """
    ts = sorted({s.t for s in series})
    if len(ts) < 3:
        return None
    return int(S.median([ts[i + 1] - ts[i] for i in range(len(ts) - 1)]) or 0) or None


def adaptive_hold_ms(series, base: int = EV.DEFAULT_DETECT.hold_ms) -> int:
    """La fenêtre de maintien, ajustée au pas réel de la série.

    ═══ L'ARBITRAGE, TRANCHÉ LE 09/08/2026 ═══

    Le lot F avait laissé `hold_ms` ouvert et le problème est
    structurel : la détection de bascule compare la fenêtre `hold_ms`
    AVANT à la fenêtre `hold_ms` APRÈS. À 45 min sur une série HORAIRE,
    les deux fenêtres ne peuvent pas contenir deux valeurs distinctes —
    le détecteur est aveugle par construction, pas par réglage.

    Mesuré sur les mêmes balises réelles (pleine cadence ~4 min /
    observations dégradées à 1 h) :

        45 min → 34 / 0      ← l'état actuel : aveugle à l'heure
        60 min → 37 / 31     ← le minimum qui marche
        75 min → 42 / 51     ← la série DÉGRADÉE en trouve plus que la
                               pleine cadence : sur-détection
        90 min → 42 / 22
       120 min → 41 / 16

    Trois voies étaient possibles. 75 min donne le plus de détections
    mais la série dégradée y trouve PLUS d'événements que la série
    complète, ce qui ne peut pas être vrai : c'est la signature d'une
    fenêtre si large qu'elle fabrique des bascules à partir du bruit de
    rééchantillonnage. 60 min fixe marche partout, mais change le
    comportement des balises denses, qui sont les seules sur lesquelles
    quoi que ce soit ait été calibré — on paierait un recul certain sur
    les bonnes données pour un gain incertain sur les mauvaises.

    D'où la fenêtre ADAPTATIVE : `max(45 min, 1,5 × pas réel)`.

      · Sur une balise à 4 min de cadence : 1,5 × 4 min = 6 min < 45 min
        → 45 min, soit EXACTEMENT le comportement d'aujourd'hui. Aucun
        recul là où il y avait de la calibration.
      · Sur une série horaire : 1,5 × 60 = 90 min → deux pas de part et
        d'autre, donc une comparaison qui a un sens.

    Le facteur 1,5 est le plus petit qui garantisse au moins un pas
    entier de chaque côté après arrondi. Ce n'est pas un réglage de
    confort : c'est la condition minimale pour que les deux fenêtres
    comparées puissent contenir des valeurs différentes.

    ⚠️ CE CHOIX VIT ICI, PAS DANS `events.py`. `events.py` est le
    portage de `windEvents.ts` et un banc de parité les compare terme à
    terme ; y ajouter une règle sans jumeau TS casserait la garantie que
    ce banc existe pour tenir. Le choix du paramètre appartient à
    l'appelant, qui est le seul à connaître la cadence de la série.

    ⚠️ ET `reversal` N'EST TOUJOURS PAS PUBLIÉ. Cette fenêtre rend la
    détection possible sur les séries horaires ; elle ne prouve pas que
    ce qu'on détecte est juste. La calibration (`EVENTS_CALIBRATED`)
    reste à faire, et `EVENT_PUBLISHABLE_TYPES` reste inchangé.
    """
    step = median_step_ms(series)
    if step is None:
        return base
    return max(base, int(round(1.5 * step)))


def station_events(series, crest, utc_offset_s: int) -> list[EV.WindEvent]:
    """Tous les événements d'UNE série : E1-E3, plus `breeze_yield`.

    ⚠️ LA MÊME DÉTECTION DES DEUX CÔTÉS, observations comme prévisions.
    Détecter les bascules réelles avec un algorithme et les bascules
    prévues avec un autre mesurerait l'écart entre deux algorithmes, pas
    la qualité du modèle.

    ⚠️ `breeze_yield` reste un mécanisme SÉPARÉ (`detect_conflicts`), pas
    une famille de plus dans `detect_all` : il exige une entrée que
    `windEvents` n'a pas (le vent de crête) et un critère que les autres
    n'ont pas (la stabilité du flux). La conversion en `WindEvent` qui
    suit est une mise en forme pour passer par le même appariement, pas
    une fusion des deux détecteurs.
    """
    # ⚠️ LA MÊME FENÊTRE DES DEUX CÔTÉS. `adaptive_hold_ms` est appelé
    # sur la série qu'on détecte, observations comme prévisions — et les
    # deux n'ont PAS la même cadence (4 min contre 60). C'est voulu : ce
    # qu'on ajuste, c'est la résolution de l'instrument à la finesse de
    # sa matière, pas un seuil de sévérité. Imposer la fenêtre de
    # l'observation à la prévision rendrait le modèle aveugle ; imposer
    # celle de la prévision à l'observation lui ferait rater ce qu'elle
    # a vraiment vu.
    p = replace(EV.DEFAULT_DETECT, hold_ms=adaptive_hold_ms(series))
    out = EV.detect_all(series, EVENT_ONSET_KMH, p)
    if crest:
        out = out + EV.conflicts_as_events(
            EV.detect_conflicts(series, crest,
                                EV.conflict_params(utc_offset_s)))
    out.sort(key=lambda e: e.t)
    return out


def event_rows(day: datetime, snapshots: dict[int, list[dict]],
               obs_day: list[dict], zone_of: dict[str, dict],
               utc_offset_s: int):
    """Rend (lignes `model_verif_event`, bilan lisible du tri).

    ⚠️ TOUT SE JOUE À L'ÉCHELON DE LA CASE FINE (`zone_id`), et les
    événements y sont CONSOLIDÉS PAR LE RÉSEAU avant d'être appariés. On
    ne remonte JAMAIS la chaîne de repli pour consolider : fusionner les
    détections de deux vallées distantes de 200 km fabriquerait des
    « événements » qui n'ont eu lieu nulle part. Les échelons supérieurs
    se construisent plus tard, en SOMMANT DES COMPTEURS (ce qui est
    licite : les cases sont disjointes), jamais en fusionnant des
    détections.

    ⚠️ LE VENT DE CRÊTE VIENT D'UN SEUL MODÈLE DE RÉFÉRENCE, le même
    pour tout le monde — même raison que `day_regime` : si chaque modèle
    apportait son propre décor, il pourrait choisir les journées où on
    le juge sur `breeze_yield`.
    """
    day_start_ms = int(day.replace(tzinfo=timezone.utc).timestamp()) * 1000
    obs_by_st: dict[str, list[S.ObsSample]] = {}
    for r in obs_day:
        key = f"{r['source']}:{r['station_id']}"
        if key not in zone_of:
            continue
        obs_by_st[key] = [o for o in to_obs_samples(r)
                          if day_start_ms <= o.t < day_start_ms + DAY_MS]

    crest_by_st: dict[str, list[EV.CrestSample]] = {}
    for row in snapshots.get(0, []):
        if "aloft_speed" not in row:
            continue
        key = f"{row['source']}:{row['station_id']}"
        if key in obs_by_st and key not in crest_by_st:
            crest_by_st[key] = _series_of(row, day_start_ms, aloft=True)

    # ── 1. observé, consolidé par case fine ──
    obs_by_zone: dict[str, list[tuple[str, list[EV.WindEvent]]]] = defaultdict(list)
    for key, samples in obs_by_st.items():
        obs_by_zone[zone_of[key]["zone_id"]].append(
            (key, station_events(samples, crest_by_st.get(key), utc_offset_s)))
    observed = {zid: EV.consolidate_network(items, EVENT_MIN_STATIONS)
                for zid, items in obs_by_zone.items()}

    # ── 2. prévu, consolidé de la même façon, par modèle et échéance ──
    fcst: dict[tuple, list[tuple[str, list[EV.WindEvent]]]] = defaultdict(list)
    for offset, lead_h in LEAD_BY_OFFSET.items():
        for row in snapshots.get(offset, []):
            key = f"{row['source']}:{row['station_id']}"
            if key not in obs_by_st:
                continue
            series = _series_of(row, day_start_ms)
            if len(series) < MIN_HOURS_DAILY:
                continue
            fcst[(zone_of[key]["zone_id"], row["model"], lead_h)].append(
                (key, station_events(series, crest_by_st.get(key), utc_offset_s)))

    # ── 3. apparier et écrire une ligne PAR ÉVÉNEMENT ──
    rows: list[dict] = []
    for (zid, model, lead_h), items in sorted(fcst.items()):
        ob = observed.get(zid, [])
        fc = EV.consolidate_network(items, EVENT_MIN_STATIONS)
        if not ob and not fc:
            continue
        for m in EV.match_events(ob, fc):
            rows.append({
                "day": day.strftime("%Y-%m-%d"),
                "zone_id": zid, "model": model, "lead_h": lead_h,
                "event_type": m.type,
                "threshold_kmh": (None if m.threshold is None
                                  else int(round(m.threshold))),
                "outcome": m.outcome,
                "timing_err_min": m.timing_err_min,
                "obs_t": _iso(m.obs_t), "fcst_t": _iso(m.fcst_t),
            })

    solo = sum(1 for zid, items in obs_by_zone.items() if len(items) < EVENT_MIN_STATIONS)
    bilan = (f"{len(obs_by_st)} balises zonées, {len(obs_by_zone)} cases fines, "
             f"dont {solo} à moins de {EVENT_MIN_STATIONS} balises (aucun "
             f"événement retenu, faute de confirmation réseau)")
    return rows, bilan


def event_scores(events: list[dict], zone_of: dict[str, dict]):
    """Agrège `model_verif_event` en POD / FAR / décalage médian.

    ⚠️ ON SOMME DES COMPTEURS POUR REMONTER LA CHAÎNE DE REPLI, on ne
    refait aucune détection. Les cases fines sont disjointes, donc les
    hits, ratés et fausses alarmes de deux vallées d'un même massif
    s'additionnent sans double compte. C'est la seule opération licite
    pour changer d'échelon ici — refaire une consolidation réseau à
    l'échelle du massif fusionnerait des bascules qui n'ont rien à voir.

    ⚠️ POURQUOI PAS UN ACCUMULATEUR `model_character`. Les trois sommes
    de `S.Accumulator` décrivent une grandeur CONTINUE (une erreur, un
    ratio) : elles ne savent pas compter des succès et des ratés. Le
    schéma l'a d'ailleurs déjà prévu, en réservant `metric in
    ('timing','frequency')` avec un `event_type` — ce sont les deux
    seules grandeurs d'événement qui soient continues, et donc les deux
    seules qui aient leur place dans un accumulateur. Les compteurs de
    contingence, eux, se recomptent chaque nuit depuis les lignes
    brutes, exactement comme `rolling_scores` recompte depuis
    `model_verif_daily`. Le brancher sur les accumulateurs est un lot à
    part, pas un raccourci à prendre ici.

    ⚠️ QUORUM RESPECTÉ, ET LES REJETS SONT COMPTÉS. Une troncature
    silencieuse se lit comme « on a tout couvert » ; le nombre de
    combinaisons écartées faute d'événements part dans le JSON.
    """
    zone_by_id: dict[str, dict] = {}
    for z in zone_of.values():
        zone_by_id.setdefault(z["zone_id"], z)

    buckets: dict[tuple, list[EV.EventMatch]] = defaultdict(list)
    inconnues = 0
    non_publiables = 0
    for e in events:
        if e["event_type"] not in EVENT_PUBLISHABLE_TYPES:
            # Écrit en base, pas publié — cf. EVENT_PUBLISHABLE_TYPES.
            # Compté, jamais tu : une troncature silencieuse se lit comme
            # « on a tout couvert ».
            non_publiables += 1
            continue
        zone = zone_by_id.get(e["zone_id"])
        if zone is None:
            # Une zone présente en base mais plus rattachée à aucune
            # balise : ses lignes restent lisibles, on ne les invente pas
            # une chaîne de repli.
            inconnues += 1
            chain = [(e["zone_id"], "unknown")]
        else:
            chain = fallback_chain(zone)
        m = EV.EventMatch(type=e["event_type"], outcome=e["outcome"],
                          timing_err_min=e.get("timing_err_min"),
                          obs_t=None, fcst_t=None,
                          threshold=e.get("threshold_kmh"))
        for zid, level in chain:
            buckets[(zid, level, e["model"], e["lead_h"], e["event_type"],
                     e.get("threshold_kmh"))].append(m)

    out: list[dict] = []
    rejets = 0
    for (zid, level, model, lead_h, etype, thr), matches in sorted(
            buckets.items(), key=lambda kv: [str(x) for x in kv[0]]):
        sc = EV.score_events(matches)
        if sc.hits + sc.misses < EVENT_MIN_OCCURRENCES:
            rejets += 1
            continue
        out.append({
            "zone_id": zid, "agg_level": level, "model": model,
            "lead_h": lead_h, "event_type": etype, "threshold_kmh": thr,
            "hits": sc.hits, "misses": sc.misses, "false_alarms": sc.false_alarms,
            # `n` est le nombre d'événements RÉELS, seul dénominateur qui
            # ait un sens pour un POD. Il est publié à côté de chaque
            # chiffre, jamais sous-entendu.
            "n": sc.hits + sc.misses,
            "pod": _r(sc.pod), "far": _r(sc.far), "csi": _r(sc.csi),
            "frequency_bias": _r(sc.frequency_bias),
            "timing_err_med_min": sc.timing_err_med_min,
            "timing_iqr_min": sc.timing_iqr_min,
        })
    return out, rejets, inconnues, non_publiables


def _publish_events(st, rows: list[dict], as_of: datetime, rejets: int,
                    non_publiables: int, dry_run: bool):
    """Publie `model_events.json` — le JSON que lira la PWA.

    ⚠️ LE DRAPEAU `calibrated` EST DANS LE FICHIER, pas dans une note de
    session. Il voyage avec les données jusqu'à l'affichage, parce que
    c'est le seul endroit où il ne peut pas se perdre.

    Mêmes règles d'affichage que tout le chantier : pas de feu
    tricolore, pas de recommandation, chaque chiffre avec son n et son
    échelon d'agrégation.
    """
    body = {
        "as_of": as_of.strftime("%Y-%m-%d"),
        "window_days": ROLLING_DAYS,
        "min_occurrences": EVENT_MIN_OCCURRENCES,
        "min_stations": EVENT_MIN_STATIONS,
        "dropped_below_quorum": rejets,
        "published_types": list(EVENT_PUBLISHABLE_TYPES),
        "withheld_rows": non_publiables,
        # ⚠️ Un fichier doit dire ce qu'il NE contient PAS. Sans cette
        # ligne, un lecteur conclurait que les bascules n'ont jamais eu
        # lieu, alors qu'elles sont en base et que c'est le détecteur qui
        # ne sait pas les voir dans une série horaire.
        "withheld_note": (
            "`reversal` est détecté, apparié et stocké dans "
            "model_verif_event, mais PAS publié ici : le détecteur est "
            "structurellement aveugle aux bascules sur une série horaire "
            "(hold_ms = 45 min < pas horaire de 60 min). Mesuré le 08/08 : "
            "les mêmes balises réelles donnent 34 bascules à ~4 min de "
            "cadence et 0 dégradées à l'heure. Publier ce POD imputerait "
            "aux modèles une cécité qui est celle de l'outil. "
            "Voir EVENT_PUBLISHABLE_TYPES dans score.py."),
        "calibrated": EVENTS_CALIBRATED,
        "calibration_note": (
            "Seuils de détection RAISONNÉS, jamais mesurés : aucune journée "
            "étiquetée n'a encore servi à les régler. Les décalages de timing "
            "sont donc lisibles comme des ordres de grandeur, pas comme des "
            "valeurs calibrées. Décision assumée du 08/08 — voir events.py."),
        "events": rows,
    }
    if st is None or dry_run:
        print("  ⓘ publication R2 sautée (pas de storage, ou dry-run)")
        return
    from storage import CACHE_REECRIT             # type: ignore
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    st.put("model_events.json", raw, cache_control=CACHE_REECRIT)
    print(f"  → model_events.json publié ({len(raw) / 1024:.0f} Ko)")


def _iso(ms) -> str | None:
    """Un instant en ms vers un `timestamptz`, ou None.

    La consolidation réseau prend la MÉDIANE des instants d'une grappe,
    qui peut tomber sur une demi-milliseconde quand la grappe est paire.
    On tronque : une demi-milliseconde sur une bascule de brise n'a
    aucun sens physique, et la garder ferait échouer le format ISO.
    """
    if ms is None:
        return None
    return datetime.fromtimestamp(int(ms) // 1000, timezone.utc).isoformat()


METRICS = ("errKmh", "speedRatio", "dirOffset", "mseModel", "msePersist")


def accumulator_updates(banded: list[dict], zone_of: dict[str, dict],
                        day: datetime, current: dict[tuple, S.Accumulator]):
    """Fait avancer les accumulateurs d'une journée.

    ⚠️ LA VALEUR INTÉGRÉE EST UNE MÉDIANE SUR LES BALISES DE LA ZONE,
    pas une valeur de balise. Une moyenne exponentielle de médianes
    reste robuste ; une moyenne exponentielle de valeurs brutes ne l'est
    pas, et une seule balise déréglée suffirait à écrire un caractère
    faux dans une mémoire de trois mois.
    """
    day_ms = int(day.replace(tzinfo=timezone.utc).timestamp()) * 1000
    # (zone_id, model, lead, regime, band, metric) → valeurs des balises
    buckets: dict[tuple, list[float]] = defaultdict(list)
    for b in banded:
        z = zone_of.get(b["key"])
        if z is None or z.get("basin_uncertain"):
            # Une balise dont le bassin est indéterminé (§16.4, défaut
            # n°2) est EXCLUE, pas rangée de travers.
            continue
        if z.get("position_suspecte"):
            # Coordonnées contredites par une source indépendante du
            # lieu nommé (étape 42, 10/08 — inspection des 18 balises à
            # >300 m d'écart z_modele/z_nom). Même traitement que
            # `basin_uncertain` : EXCLUE, pas rangée de travers. Posé
            # UNIQUEMENT quand une source tierce situe le lieu ailleurs,
            # jamais sur le seul écart modèle/nom (14 des 18 grands
            # écarts inspectés étaient de vrais sommets rabotés par la
            # maille — cf. claude/inspection-18-balises-ecart-resultats-10-08.md).
            continue
        for zid, _level in fallback_chain(z):
            for metric in METRICS:
                v = b.get(metric)
                if v is None or not S._finite(v):
                    continue
                buckets[(zid, b["model"], b["lead_h"], b["regime"],
                         b["band"], metric)].append(float(v))
                # La case « toutes tranches » vit à côté des tranches,
                # pas à leur place : c'est elle qui porte le score
                # général, elles qui portent le caractère.
                buckets[(zid, b["model"], b["lead_h"], b["regime"],
                         "all", metric)].append(float(v))
                buckets[(zid, b["model"], b["lead_h"], "all",
                         "all", metric)].append(float(v))

    out: list[dict] = []
    for key, values in buckets.items():
        if len(values) < 1:
            continue
        med = S.median(values)
        if med is None:
            continue
        acc = current.get(key, S.Accumulator())
        acc2 = S.accumulate(acc, med, day_ms)
        if acc2 is acc or acc2.last_day != day_ms:
            continue                        # journée déjà intégrée
        zid, model, lead, regime, band, metric = key
        out.append({
            "zone_id": zid, "model": model, "lead_h": lead,
            "regime": regime, "band": band, "metric": metric,
            "event_type": "none",
            "sum_w": acc2.sum_w, "sum_wx": acc2.sum_wx, "sum_wx2": acc2.sum_wx2,
            "days": acc2.days, "last_day": day.strftime("%Y-%m-%d"),
        })
    return out


# ══════════════════════════════════════════════════════════════════
#  SCORES DE ZONE
# ══════════════════════════════════════════════════════════════════

def skill_contre(mse_modele, mse_reference):
    """`(skill, bat_la_référence)`, ou `(None, None)` sous le plancher.

    ⛔ LE `None` EST LA RÉPONSE, PAS UN ÉCHEC. Une référence dont
    l'erreur RMS tient sous 1 km/h n'est pas une référence : c'est une
    journée où le vent n'a pas bougé. Le rapport y devient énorme et
    arbitraire (−2 573 000 mesuré le 11/08), et il écrase toute médiane
    et toute échelle où il entre. On rend donc `None` pour les DEUX
    réponses — y compris `bat_la_référence`, parce qu'un `false` se
    lirait comme « ce modèle a perdu » alors que la question n'a pas eu
    lieu. Détail chiffré : `SKILL_MIN_REF_MSE`.
    """
    if mse_modele is None or mse_reference is None:
        return None, None
    if mse_reference < SKILL_MIN_REF_MSE:
        return None, None
    return _r(1 - mse_modele / mse_reference), mse_modele < mse_reference


def _case_rows(units: list[dict], zone_of: dict[str, dict], as_of: datetime,
               window_kind: str, regime: str, min_stations: int,
               level_of: dict[str, str] | None = None,
               with_ci: bool = True):
    """Le corps commun des deux chemins de score.

    ⚠️ UN SEUL CORPS POUR `rolling15` ET POUR `regime`, et c'est la
    correction de fond du lot G. Les deux chemins étaient deux codes
    différents : l'un lisait des balise-jours et savait donc calculer un
    décile et un intervalle, l'autre lisait des accumulateurs et ne le
    pouvait pas. D'où quatre colonnes nulles sur 10 250 lignes — pas un
    oubli d'écriture, une impossibilité arithmétique.

    Maintenant les deux lisent la même matière : des BALISE-JOURS. Le
    chemin régime ne diffère plus que par son filtre (les journées de CE
    régime, quelle que soit leur ancienneté) et par sa fenêtre.

    `units` : lignes de balise-jour portant `unit`, `day`, `model`,
    `lead_h`, `err_vec_med`, et facultativement `mse_model`/`mse_persist`.
    """
    acc: dict[tuple, dict] = defaultdict(
        lambda: {"by_day": defaultdict(list), "st": set(), "rows": [],
                 "mse_m": [], "mse_r": [], "mse_c": [], "n_hours": 0,
                 # ── lot S2 : la colonne corrigée, À CÔTÉ ─────────────
                 "err_corr": [], "mse_cc": [], "nd": []})
    for d in units:
        z = zone_of.get(d["unit"])
        if z is None or z.get("basin_uncertain"):
            continue
        if z.get("position_suspecte"):
            # Même exclusion qu'accumulator_updates — voir le
            # commentaire là-bas (étape 42, 10/08).
            continue
        if d.get("err_vec_med") is None:
            continue
        for zid, level in fallback_chain(z):
            b = acc[(zid, d["model"], d["lead_h"], level)]
            b["by_day"][d["day"]].append(d["err_vec_med"])
            b["rows"].append(d)
            if d.get("mse_model") is not None and d.get("mse_persist") is not None:
                b["mse_m"].append(d["mse_model"])
                b["mse_r"].append(d["mse_persist"])
            if d.get("mse_model") is not None and d.get("mse_clim") is not None:
                b["mse_c"].append((d["mse_model"], d["mse_clim"]))
            # ── lot S2 ────────────────────────────────────────────────
            # ⚠️ LA CLIMATOLOGIE N'EST PAS CORRIGÉE, ET C'EST LA QUESTION.
            # Elle est bâtie sur des OBSERVATIONS : elle porte déjà le
            # site en elle, c'est même pour ça qu'elle gagne dans les
            # Alpes. `skill_clim_corr` demande donc « une fois le site
            # retiré du MODÈLE, bat-il une référence qui, elle, l'a
            # gardé ». C'est l'exploit qui compte, et le corriger des
            # deux côtés reviendrait à comparer deux fois la même
            # soustraction.
            if d.get("err_vec_med_corr") is not None:
                b["err_corr"].append(d["err_vec_med_corr"])
                if d.get("bias_n_days") is not None:
                    b["nd"].append(d["bias_n_days"])
            if (d.get("mse_model_corr") is not None
                    and d.get("mse_clim") is not None):
                b["mse_cc"].append((d["mse_model_corr"], d["mse_clim"]))
            b["st"].add(d["unit"])
            b["n_hours"] += d.get("n_hours") or 0

    rows: list[dict] = []
    #: [persistance, climatologie] — cases dont la référence est sous le
    #: plancher. Compté et DIT : une correction qui fait taire des
    #: colonnes doit annoncer combien, sinon c'est une purge silencieuse.
    sous_plancher = [0, 0]
    # Le classement se décide zone par zone et échéance par échéance :
    # comparer deux modèles sur des zones différentes n'a aucun sens.
    by_case: dict[tuple, list[dict]] = defaultdict(list)
    rows_by_case_model: dict[tuple, dict[str, list[dict]]] = defaultdict(dict)
    for (zid, model, lead, level), b in acc.items():
        if len(b["st"]) < min_stations:
            continue
        # ⚠️ `level_of` (= `model_zone.kind`, lu en base) prime sur
        # l'échelon déduit de la chaîne quand il est fourni : c'est la
        # leçon du reniflage de `zone_id` corrigé le 08/08. Une zone
        # absente de `model_zone` est sautée plutôt que publiée sous un
        # échelon inventé — un score anonyme sur sa précision ment.
        if level_of is not None:
            level = level_of.get(zid)
            if level is None:
                print(f"  ⚠️ zone inconnue de model_zone, score sauté : {zid}",
                      file=sys.stderr)
                continue
        values = [v for vs in b["by_day"].values() for v in vs]
        # ⚠️ `with_ci=False` SAUTE LE BOOTSTRAP UNAIRE, et seulement lui.
        # Mesuré le 09/08 à la taille réelle (647 balises × 10 modèles ×
        # 30 jours = 194 100 balise-jours) : le chemin régime complet
        # coûte 85,6 s, dont l'essentiel part dans ce rééchantillonnage —
        # 500 tirages par ligne, sur 5 360 lignes. Le rapport de
        # stabilité (G5) n'a besoin QUE des rangs, et les rangs viennent
        # du test APPARIÉ, pas de cet intervalle-là. Le calculer deux
        # fois de plus pour le jeter serait doubler la durée du run pour
        # rien.
        ci = (INF.block_median_ci(b["by_day"]) if with_ci
              else INF.DiffCI(S.median(values), None, None, len(values),
                              len(b["by_day"]), None, "not_computed"))
        mse_m = S.median(b["mse_m"])
        mse_r = S.median(b["mse_r"])
        # ⚠️ La climatologie s'apparie AVANT de se médianiser : comparer
        # la médiane des MSE du modèle à celle d'une climatologie
        # calculée sur une population de balise-jours différente
        # comparerait deux échantillons, pas deux prévisions.
        mse_cm = S.median([m for m, _ in b["mse_c"]])
        mse_cc = S.median([c for _, c in b["mse_c"]])
        skill, bat_persist = skill_contre(mse_m, mse_r)
        skill_clim, bat_clim = skill_contre(mse_cm, mse_cc)
        # ── lot S2 : la même arithmétique, sur le modèle corrigé ──────
        # ⚠️ Le quorum est CELUI DE LA CASE, pas un second : une case
        # publie son corrigé si et seulement si elle publie son brut.
        # Deux populations différentes sous deux colonnes voisines
        # inviteraient à les soustraire, et la différence ne voudrait
        # rien dire.
        corr_med = S.median(b["err_corr"]) if b["err_corr"] else None
        mse_ccm = S.median([m for m, _ in b["mse_cc"]])
        mse_ccc = S.median([c for _, c in b["mse_cc"]])
        skill_clim_corr, bat_clim_corr = skill_contre(mse_ccm, mse_ccc)
        # Le dénombrement se fait ICI, sur la référence, pas sur le
        # résultat : un skill nul parce que la référence manque et un
        # skill nul parce qu'elle est trop bonne sont deux choses, et
        # c'est la seconde qu'on veut voir grossir ou pas.
        if mse_r is not None and mse_r < SKILL_MIN_REF_MSE:
            sous_plancher[0] += 1
        if mse_cc is not None and mse_cc < SKILL_MIN_REF_MSE:
            sous_plancher[1] += 1
        ordered = sorted(values)
        row = {
            "as_of": as_of.strftime("%Y-%m-%d"), "zone_id": zid, "model": model,
            "lead_h": lead, "window_kind": window_kind, "regime": regime,
            "agg_level": level, "n_stations": len(b["st"]),
            "n_hours": b["n_hours"], "occurrences": len(values),
            "typical_err_kmh": _r(ci.median),
            "worst_decile_kmh": _r(ordered[min(len(ordered) - 1,
                                               math.floor(len(ordered) * 0.9))])
            if len(ordered) >= 5 else None,
            "beats_persist": bat_persist,
            "skill": skill,
            "beats_clim": bat_clim,
            "skill_clim": skill_clim,
            # ── lot S2 : le corrigé, À CÔTÉ du brut, jamais à sa place ─
            # ⛔ Décision D intacte : `typical_err_kmh` reste LE score.
            # `n_corr` voyage avec, parce qu'une case peut publier son
            # brut sur 40 balise-jours et son corrigé sur 12 (les
            # balises dont l'antécédent n'a pas encore
            # `BIAIS_MIN_JOURS` journées), et comparer les deux
            # médianes sans le savoir serait comparer deux populations.
            "typical_err_kmh_corr": _r(corr_med),
            "beats_clim_corr": bat_clim_corr,
            "skill_clim_corr": skill_clim_corr,
            "n_corr": len(b["err_corr"]),
            "bias_n_days": _r(S.median(b["nd"]), 1) if b["nd"] else None,
            "ci_low": _r(ci.ci_low), "ci_high": _r(ci.ci_high),
            "rank": None, "rank_reason": None,
            # ── colonnes du lot G ──
            # `err_sd` : dispersion des balise-jours de la case. Publiée
            # parce qu'elle est lisible en soi (« ce modèle est régulier
            # ici »), et parce que le rétrécissement du G3 en a besoin —
            # la déduire de la demi-largeur de l'IC marcherait quand
            # l'IC existe et donnerait `None` quand il manque,
            # c'est-à-dire précisément sur les cases maigres, celles qui
            # doivent emprunter le plus. Un estimateur qui se tait là où
            # il est le plus utile n'est pas un estimateur.
            "err_sd": _r(math.sqrt(INF.sample_variance(values))
                         if INF.sample_variance(values) is not None else None),
            "n_days": ci.n_days,
            "ci_kind": "block_day" if ci.reason == "ok" else None,
            "ci_reason": ci.reason,
            "block_days": ci.block_days,
            "pooled_err_kmh": None, "borrowed_weight": None,
        }
        rows.append(row)
        by_case[(zid, lead, level)].append(row)
        rows_by_case_model[(zid, lead, level)][model] = b["rows"]

    _apply_rank(by_case, rows_by_case_model)
    if sous_plancher[0] or sous_plancher[1]:
        print(f"  ⓘ skill nul sur {sous_plancher[0]} case(s) "
              f"(persistance) et {sous_plancher[1]} (climatologie) : "
              f"référence sous {SKILL_MIN_REF_MSE} (km/h)², soit une "
              f"erreur RMS < {math.sqrt(SKILL_MIN_REF_MSE):.0f} km/h — "
              f"le vent n'a pas bougé, la question n'a pas eu lieu "
              f"[{window_kind}/{regime}]")
    return rows


def rolling_scores(daily: list[dict], zone_of: dict[str, dict], as_of: datetime):
    """Le score « 15 jours glissants » du §8, depuis `model_verif_daily`.

    ⚠️ Le rééchantillonnage se fait par BLOCS DE JOURS CONSÉCUTIFS
    (lot G), et plus par balise-jour indépendante. La note précédente
    disait déjà qu'il ne fallait pas rééchantillonner à l'heure parce
    que deux heures consécutives ne sont pas indépendantes. C'était vrai
    et insuffisant : deux JOURNÉES consécutives ne le sont pas non plus,
    une situation synoptique durant environ trois jours. Un tirage
    i.i.d. sur les balise-jours fabriquait donc des intervalles trop
    étroits — mesuré sur données simulées à corrélation connue : 42 % de
    couverture réelle pour un intervalle annoncé à 95 % (cf.
    `test_inference.py`, section 4). C'est une fabrique de faux
    gagnants, pas une imprécision.
    """
    units = []
    for d in daily:
        r = dict(d)
        r["unit"] = f"{d['source']}:{d['station_id']}"
        units.append(r)
    return _case_rows(units, zone_of, as_of, "rolling15", "all",
                      MIN_STATIONS_ZONE)


def regime_scores(units: list[dict], as_of: datetime,
                  zone_of: dict[str, dict], kind_of: dict[str, str],
                  min_stations: int = 1):
    """Le score par régime du §16.1 — désormais depuis les BALISE-JOURS
    rejoués, et non plus depuis les accumulateurs.

    ⚠️ CE N'EST TOUJOURS PAS UNE FENÊTRE GLISSANTE, et c'est tout
    l'intérêt. « Les 15 derniers jours » mélange un flux de nord, deux
    jours de marin et trois jours de brise — la moyenne qui en sort
    n'est vraie aucun de ces jours. Ici on lit « les N dernières fois
    qu'on a eu CE régime ici », quelle que soit leur ancienneté ; la
    seule limite est la profondeur de l'archive rejouée.

    ⚠️ CE QUI A CHANGÉ AU LOT G, ET POURQUOI. Cette fonction lisait
    `model_character`, dont l'accumulateur ne porte que trois sommes.
    Elle publiait donc `worst_decile_kmh = None`, `ci_low = None`,
    `ci_high = None` et `skill = None` sur TOUTES ses lignes : 10 250
    sur 10 250, mesuré le 09/08. Ce n'était pas réparable dans
    l'accumulateur — un quantile demande la distribution, trois sommes
    ne la portent pas.

    Les accumulateurs ne disparaissent pas pour autant : ils restent la
    mémoire longue du CARACTÈRE (§15.4, « ce modèle sous-estime le vent
    fort dans cette vallée »), qui est une moyenne pondérée et qui, elle,
    tient parfaitement dans trois sommes. Ce sont deux questions
    différentes, et c'est de les avoir confondues que venait le trou.

    ⚠️ `min_stations` VAUT 1 ICI, à dessein. Le quorum du chemin régime
    est un nombre d'OCCURRENCES (`REGIME_MIN_OCCURRENCES`), appliqué au
    classement, pas un nombre de balises : une case fine peut n'avoir
    qu'une balise et beaucoup de journées de ce régime.
    """
    rows: list[dict] = []
    by_regime: dict[str, list[dict]] = defaultdict(list)
    for u in units:
        reg = u.get("regime")
        # « unknown » n'est pas un régime : une journée qu'on n'a pas su
        # classer ne doit pas être versée dans une case, surtout pas dans
        # la plus peuplée.
        if reg and reg != "unknown" and reg in S.REGIMES:
            by_regime[reg].append(u)
    for reg, us in sorted(by_regime.items()):
        rows += _case_rows(us, zone_of, as_of, "regime", reg,
                           min_stations, level_of=kind_of)
    return rows


def _apply_rank(by_case: dict[tuple, list[dict]],
                rows_by_case_model: dict[tuple, dict[str, list[dict]]]):
    """Classe, ou refuse de classer — par TEST APPARIÉ (lot G2).

    ⚠️ `rank` NUL SUR TOUTES LES LIGNES est un résultat de première
    classe, et ce sera le cas le plus fréquent. Une colonne qui force un
    classement fabriquerait un gagnant là où il n'y en a pas — c'est le
    reproche fait au 🏆 du score actuel.

    ⚠️ UN SEUL MÉCANISME, PAS DEUX. Le verdict venait auparavant d'un
    écart relatif de 15 % sur l'erreur médiane, avec deux intervalles
    unaires publiés à côté — et un lecteur qui compare deux intervalles
    unaires croit faire un test sans en faire un. Le verdict vient
    maintenant de l'intervalle de la DIFFÉRENCE APPARIÉE, et l'écart
    relatif reste ce qu'il aurait toujours dû être : la question
    PRATIQUE (« est-ce que ça change une décision de vol »), distincte
    de la question statistique (« est-ce réel »). Il faut les deux.

    ⚠️ ET PAS DE REPLI. Quand la fenêtre est trop courte pour le test,
    on ne retombe pas sur l'écart relatif seul : ce serait remettre en
    service le mécanisme qu'on remplace, et publier sous le même nom
    deux verdicts de nature différente. `rank_reason` vaut alors
    `window_too_short`, et c'est la réponse honnête tant que l'archive
    ne porte que deux jours.
    """
    for key, rows in by_case.items():
        cases = [{"model": r["model"], "typical_err_kmh": r["typical_err_kmh"],
                  "occurrences": r["occurrences"]} for r in rows]
        ranks, reason, verdict = INF.rank_models(
            cases, rows_by_case_model.get(key, {}))
        for r in rows:
            r["rank_reason"] = reason
            r["rank"] = ranks.get(r["model"])


#: La valeur que porte un rang publié sur une journée à laquelle il
#: manque une partie de collecte.
RANK_REASON_PARTIE_MANQUANTE = "partie_manquante"


def marquer_parties_manquantes(rows: list[dict], bilans: dict) -> int:
    """Qualifie les rangs PUBLIÉS quand une partie de collecte manque.

    ⛔ LA QUESTION QUE LE LOT S0.4 LAISSAIT OUVERTE, TRANCHÉE ICI.
    `_apply_rank` classe les modèles PRÉSENTS. Si la passe de surface a
    échoué, il en reste deux sur neuf, et il publie « 1ᵉʳ sur 2 » sans
    que rien ne dise que sept manquaient. Les deux issues instruites
    étaient : refuser de classer la journée, ou publier en le disant.

    ⇒ **On publie en le disant**, et la raison est celle du S0.4 : *un
    classement absent et un classement partiel se lisent pareil dans un
    écran, et le second au moins se dit.* Refuser de classer ferait
    disparaître la ligne — donc rendrait la nuit incomplète
    INDISTINGUABLE d'une nuit sous quorum, qui est le cas le plus
    fréquent et parfaitement normal.

    ⚠️ MAIS ON N'ÉCRASE QUE LES `ok`, ET C'EST LA MOITIÉ QUI COMPTE.
    `rank_reason` porte un verdict STATISTIQUE par case
    (`insufficient`, `window_too_short`, `not_separable`, `tied`,
    `too_few_pairs`, `single_model`). Le remplacer partout détruirait
    une information par case pour y mettre un fait par JOURNÉE — et sur
    ces cases-là il n'y a de toute façon aucun rang trompeur à
    qualifier, puisqu'il n'y a pas de rang du tout. On ne qualifie donc
    que ce qui, sans ça, mentirait : les rangs effectivement publiés.

    ⓘ LE FAIT PAR JOURNÉE, LUI, VA EN BASE, dans
    `model_verif_collect_part` — une table par (jour, flux), lisible
    telle quelle, qui porte le compte des parties et les modèles
    nommés. Les deux écritures sont complémentaires : celle-ci empêche
    un rang de mentir, celle-là permet au tableau de bord de dire
    pourquoi.

    Rend le nombre de lignes qualifiées.
    """
    incomplets = sorted(
        off for off, b in bilans.items()
        if b.get("etat") not in ("ok", "avant_partition"))
    if not incomplets:
        return 0
    n = 0
    for r in rows:
        if r.get("rank") is not None and r.get("rank_reason") == "ok":
            r["rank_reason"] = RANK_REASON_PARTIE_MANQUANTE
            n += 1
    return n


def collect_part_rows(day: datetime, bilans: dict) -> list[dict]:
    """Les lignes de `model_verif_collect_part` pour une journée notée.

    ⚠️ UNE LIGNE PAR (JOUR D'ÉMISSION, FLUX), pas par journée notée. Une
    nuit de notation lit TROIS journées d'émission (les trois offsets de
    `LEAD_BY_OFFSET`) : c'est chacune d'elles qui a pu perdre une
    partie, et les confondre ferait disparaître deux incidents sur
    trois. La clé primaire est donc `(day, flux)` où `day` est le jour
    D'ÉMISSION — le même que celui de la clé R2.
    """
    out = []
    for off, b in sorted(bilans.items()):
        emis = day - timedelta(days=off)
        out.append({
            "day": f"{emis:%Y-%m-%d}",
            "flux": b.get("flux", "fcst"),
            "parties_attendues": b.get("parties_attendues"),
            "parties_lues": b.get("parties_lues", 0),
            "modeles_manquants": list(b.get("modeles_manquants") or []),
            "etat": b.get("etat", "ok"),
        })
    return out


# ══════════════════════════════════════════════════════════════════
#  RÉTRÉCISSEMENT VERS LE PARENT (lot G3)
# ══════════════════════════════════════════════════════════════════

def apply_pooling(rows: list[dict], zones: list[dict]) -> int:
    """Rétrécit chaque case fine vers son parent, et publie l'emprunt.

    Le parent d'une zone est l'échelon SUIVANT de sa chaîne de repli —
    la même chaîne que celle qui sert déjà à agréger, donc aucune
    hiérarchie nouvelle à maintenir.

    ⚠️ LE QUORUM RESTE LE SEUIL D'AFFICHAGE (arbitrage du 09/08). Le
    pooling améliore l'ESTIMATION ; il ne fait apparaître aucune ligne
    qui n'existait pas. Le §16.3 parlait d'un « remplacement progressif
    du quorum sec » : un remplacement franc ferait apparaître des
    chiffres partout, y compris là où presque tout est emprunté au
    massif, c'est-à-dire ouvrirait la vanne au moment précis où l'on
    affirme la refermer.

    ⚠️ `borrowed_weight` EST PUBLIÉ À CÔTÉ DE CHAQUE CHIFFRE, et
    `typical_err_kmh` n'est PAS écrasé. Un score à 80 % emprunté au
    massif n'est pas un score de vallée : le remplacer en silence serait
    la même faute que le débiaisage silencieux du lot D. Le lecteur voit
    les deux et sait lequel il regarde.
    """
    parent_of: dict[str, str] = {}
    for z in zones:
        chain = fallback_chain(z)
        for i in range(len(chain) - 1):
            parent_of.setdefault(chain[i][0], chain[i + 1][0])

    par_famille: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        par_famille[(r["model"], r["lead_h"], r["window_kind"],
                     r["regime"])][r["zone_id"]] = r

    n = 0
    for famille in par_famille.values():
        # Fratries : les zones qui partagent le même parent.
        fratries: dict[str, list[dict]] = defaultdict(list)
        for zid, r in famille.items():
            p = parent_of.get(zid)
            if p and p in famille:
                fratries[p].append(r)
        for pid, enfants in fratries.items():
            parent = famille[pid]
            spread = [(e["typical_err_kmh"], e["occurrences"],
                       _within_var(e)) for e in enfants]
            tau2, sigma2 = INF.pooling_variances(
                [(v, k, s) for v, k, s in spread if v is not None and s is not None])
            for e in enfants:
                p = INF.pool_toward_parent(
                    e["typical_err_kmh"], e["occurrences"],
                    parent["typical_err_kmh"], tau2, sigma2)
                e["pooled_err_kmh"] = _r(p.value)
                e["borrowed_weight"] = _r(p.borrowed, 3)
                n += 1
    return n


# ══════════════════════════════════════════════════════════════════
#  CRITÈRE DE SORTIE (lot G5) — mesuré, pas décrété
# ══════════════════════════════════════════════════════════════════

def stability_report(units: list[dict], zone_of: dict[str, dict],
                     as_of: datetime, kind_of: dict[str, str],
                     half_days: int = ROLLING_DAYS) -> dict:
    """Les rangs tiennent-ils d'une période à la suivante ?

    C'est le chiffre qui devra décider, un jour, de sortir de l'atelier.
    Il n'est pas décrété : il se mesure, et il se mesure d'une façon
    précise.

    ⚠️ SUR DES FENÊTRES DISJOINTES, ET C'EST TOUT LE PIÈGE. La mesure
    naturelle — comparer la fenêtre glissante de 15 jours d'hier à celle
    d'aujourd'hui — est trompeuse : deux fenêtres glissantes décalées
    d'un jour partagent 14 jours sur 15. Leur accord serait proche de 1
    quoi qu'il arrive, et ce 1 dirait « les données sont les mêmes », pas
    « le classement est stable ». On coupe donc la fenêtre rejouée en
    deux moitiés SANS AUCUN JOUR COMMUN, et le rapport porte le nombre de
    jours partagés (0) pour que personne n'ait à le croire sur parole.

    ⚠️ Un `tau` élevé ne suffira pas à sortir de l'atelier : il dit que
    le classement se reproduit, pas qu'il est juste. Un détecteur
    systématiquement biaisé est parfaitement stable.
    """
    jours = sorted({u["day"] for u in units}, reverse=True)
    recents = set(jours[:half_days])
    anciens = set(jours[half_days:half_days * 2])
    if not anciens:
        return {"reason": "window_too_short", "shared_days": 0,
                "n_cases": 0, "n_comparable": 0,
                "kendall_tau": None, "top1_agreement": None,
                "covers": (f"{len(jours)} journées rejouées : il en faut "
                           f"{half_days * 2} pour comparer deux fenêtres "
                           f"disjointes de {half_days} jours")}

    def rangs(jeu: set[str]) -> dict[tuple, dict[str, int]]:
        rows = _case_rows([u for u in units if u["day"] in jeu],
                          zone_of, as_of, "rolling15", "all",
                          MIN_STATIONS_ZONE, level_of=kind_of, with_ci=False)
        out: dict[tuple, dict[str, int]] = defaultdict(dict)
        for r in rows:
            if r["rank"] is not None:
                out[(r["zone_id"], r["lead_h"])][r["model"]] = r["rank"]
        return out

    st = INF.rank_stability(rangs(recents), rangs(anciens), recents, anciens)
    return {"reason": st.reason, "shared_days": st.shared_days,
            "n_cases": st.n_cases, "n_comparable": st.n_comparable,
            "kendall_tau": _r(st.kendall_tau, 3),
            "top1_agreement": _r(st.top1_agreement, 3),
            "window_days": half_days, "covers": st.covers}


def _within_var(row: dict) -> float | None:
    """Variance interne d'une case — la dispersion de ses balise-jours.

    Lue directement dans `err_sd`, et non reconstituée depuis la
    demi-largeur de l'intervalle : l'intervalle manque exactement sur
    les cases maigres, qui sont celles qui doivent emprunter le plus.
    """
    sd = row.get("err_sd")
    return None if sd is None else float(sd) * float(sd)

# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def _pour_la_base(sb, table: str, rows: list[dict]) -> list[dict]:
    """N'envoie que les colonnes que la table sait recevoir.

    ⚠️ LE SQL NE S'EXÉCUTE JAMAIS DEPUIS ICI — c'est Yann qui le lance,
    quand il le lance. Entre le déploiement de ce code et l'exécution de
    `supabase_step40_lot_g.sql`, un run qui enverrait `pooled_err_kmh` ou
    `mse_clim` recevrait un `PGRST204 — column … does not exist` et la
    nuit serait perdue pour une colonne d'agrément.

    Le jour où le SQL est passé, les colonnes apparaissent d'elles-mêmes.
    Aucun drapeau à basculer, donc aucun drapeau à oublier — et c'est le
    point : un `SCHEMA_LOT_G = True` à changer à la main aurait été une
    seconde chose à ne pas oublier, le lendemain d'une nuit blanche.
    """
    if not rows:
        return rows
    cols = sb.columns(table)
    if not cols:
        return rows
    absentes = sorted(set(rows[0]) - cols)
    if not absentes:
        return rows
    # ⚠️ Le nom du SQL est DÉDUIT des colonnes qui manquent, pas écrit en
    # dur. La version précédente nommait toujours `step40_lot_g` : au lot
    # S2, elle aurait envoyé Yann rejouer un fichier déjà passé pendant
    # que les vraies colonnes manquantes attendaient ailleurs.
    _S2 = {"bias_slope", "err_vec_med_corr", "mse_model_corr", "bias_n_days",
           "typical_err_kmh_corr", "beats_clim_corr", "skill_clim_corr",
           "n_corr"}
    fichier = ("supabase_step49_lot_s2_biais_corrige.sql"
               if set(absentes) & _S2 else "supabase_step40_lot_g.sql")
    print(f"  ⓘ {table} : colonnes pas encore en base, non envoyées — "
          f"{', '.join(absentes)}. Lancer {fichier} pour les activer.")
    out = [{k: v for k, v in r.items() if k in cols} for r in rows]

    # ⚠️ ET LE CAS QUI NE SE VOIT PAS. `model_score_zone.rank_reason`
    # porte un CHECK écrit dans step35 :
    #
    #     check (rank_reason in ('ok','insufficient','tied'))
    #
    # Le lot G en ajoute trois (`window_too_short`, `not_separable`,
    # `too_few_pairs`) et la contrainte les REFUSE — ce n'est plus une
    # colonne manquante qu'on peut omettre, c'est tout l'envoi qui part
    # en HTTP 400. Tant que le SQL du lot G n'est pas passé, on écrit
    # donc `null` en base plutôt que de perdre la nuit ; le JSON publié,
    # lui, garde la vraie raison, et c'est lui que lit l'écran.
    if table == "model_score_zone" and "ci_reason" in absentes:
        historiques = {"ok", "insufficient", "tied", None}
        nouvelles = {r.get("rank_reason") for r in out} - historiques
        if nouvelles:
            print(f"     ⚠️ rank_reason : {', '.join(sorted(nouvelles))} "
                  f"refusé(s) par le CHECK de step35 → écrit `null` en base "
                  f"cette nuit. Le JSON publié garde la raison exacte.")
            for r in out:
                if r.get("rank_reason") not in historiques:
                    r["rank_reason"] = None
    return out


#: Les `rank_reason` que le CHECK de `supabase_step40_lot_g.sql` admet.
#: `single_model` (lot S0.5) n'y est PAS : il vient avec
#: `supabase_step42_lot_s05.sql`.
RANK_REASONS_STEP40 = {"ok", "insufficient", "tied", "not_separable",
                       "window_too_short", "too_few_pairs", None}


def _upsert_scores(sb, rows: list[dict]) -> int:
    """`model_score_zone`, avec un repli sur le CHECK de `rank_reason`.

    ⛔ POURQUOI CE REPLI EXISTE, ET IL A UN PRÉCÉDENT EXACT. Le lot G a
    ajouté trois valeurs à `rank_reason` ; le CHECK de step35 les
    refusait, et un HTTP 400 sur `model_score_zone` fait perdre LA NUIT
    ENTIÈRE — pas la colonne, la nuit. Le contournement d'alors
    (`_pour_la_base`, ci-dessus) devinait l'état du schéma par une
    colonne absente : un proxy, qui ne marche que pour ce lot-là.

    Le lot S0.5 ajoute `single_model` et n'ajoute AUCUNE colonne : il
    n'y a plus de proxy à lire. On fait donc la seule chose qui ne
    suppose rien — on envoie, et si la base refuse EN NOMMANT sa
    contrainte, on renvoie une fois avec la raison neuve mise à `null`.
    Le JSON publié, lui, garde la vraie raison, et c'est lui que lit
    l'écran (même règle qu'au lot G).

    ⇒ La nuit passe même si `supabase_step42_lot_s05.sql` n'a pas
    encore été joué, et ce repli devient inerte le jour où il l'est —
    sans qu'il faille penser à retirer quoi que ce soit.
    """
    cle = "as_of,zone_id,model,lead_h,window_kind,regime"
    try:
        return sb.upsert("model_score_zone", rows, cle)
    except Abort as exc:
        if "model_score_zone_rank_reason_check" not in str(exc):
            raise
        neuves = sorted({r.get("rank_reason") for r in rows}
                        - RANK_REASONS_STEP40)
        print(f"  ⚠️ rank_reason : {', '.join(neuves)} refusé(s) par le "
              f"CHECK en base → écrit `null` cette nuit. Jouer "
              f"`supabase_step42_lot_s05.sql` (`single_model`) et/ou "
              f"`supabase_step48_lot_s06_collect_part.sql` "
              f"(`partie_manquante`). Le JSON publié garde la raison "
              f"exacte.", file=sys.stderr)
        for r in rows:
            if r.get("rank_reason") not in RANK_REASONS_STEP40:
                r["rank_reason"] = None
        return sb.upsert("model_score_zone", rows, cle)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="/var/lib/bw-model-verif")
    ap.add_argument("--day", default=None, help="journée à noter (défaut : hier)")
    ap.add_argument("--utc-offset-h", type=float, default=2.0,
                    help="décalage local des sites, pour la fenêtre volable "
                         "(défaut : 2 = heure d'été française)")
    ap.add_argument("--no-purge", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--regime-days", type=int, default=REGIME_REPLAY_DAYS,
                    help="profondeur du rejeu d'archive pour le chemin régime")
    ap.add_argument("--replay-budget", type=int, default=3,
                    help="journées JAMAIS rejouées qu'une nuit peut rattraper. "
                         "Borne la durée du run : rejouer trente journées d'un "
                         "coup peut la multiplier par trente.")
    args = ap.parse_args()

    root = pathlib.Path(args.out)
    # ⚠️ AUCUN DATETIME NAÏF NE SORT D'ICI, et c'est délibéré. Ce qui
    # tenait debout jusqu'ici ne tenait que par accident : `utcnow()`
    # rend l'heure UTC mais SANS le dire, et `day.replace(tzinfo=utc)`
    # plus bas ne fait que rattraper cette omission. Les deux lignes ne
    # sont d'accord que tant que personne ne remplace `utcnow()` par
    # `now()` — auquel cas `.timestamp()` lirait 22 h la veille comme
    # minuit UTC, et TOUS les appariements glisseraient de deux heures
    # sans qu'aucun test ne tombe. Un décalage silencieux, pas un plantage.
    #
    # `utcnow()` est par ailleurs déprécié depuis Python 3.12 et le VPS
    # tourne en 3.13 : on l'entend déjà, on ne l'a pas encore payé.
    day = (datetime.strptime(args.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
           if args.day
           else datetime.now(timezone.utc) - timedelta(days=1)).replace(
               hour=0, minute=0, second=0, microsecond=0)
    as_of = datetime.now(timezone.utc)
    utc_offset_s = int(args.utc_offset_h * 3600)

    try:
        sb = Supabase(dry_run=args.dry_run)
    except Abort as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    st = _storage()

    print(f"▶ journée notée : {day:%Y-%m-%d}")

    # ── 1. relire l'archive ───────────────────────────────────────
    snapshots = {}
    # ⛔ LE BILAN DES PARTIES, PAR JOURNÉE D'ÉMISSION (lot S0.6). Il se
    # rend et se journalise TROIS FOIS par nuit — une par offset — parce
    # que ce sont trois nuits de collecte différentes, dont chacune a pu
    # perdre une partie. Un bilan unique en aurait caché deux sur trois.
    bilans_parties = {}
    for offset in LEAD_BY_OFFSET:
        emis = day - timedelta(days=offset)
        rows, bilan = snapshot_rows_et_bilan(root, emis, st)
        snapshots[offset] = rows
        bilans_parties[offset] = bilan
        n_ag = sum(1 for r in rows if r.get("model") == AGRUME_MODEL)
        # ⚠️ Le compte AGRUME se dit à chaque offset, y compris quand il
        # est destiné à ne rien produire. Une ligne « 0 » qui n'apparaît
        # jamais et une ligne qui manque se lisent pareil dans un
        # journal, et c'est la seconde qu'on cherche.
        print(f"  prévisions émises J-{offset} : {len(rows)} lignes "
              f"(classe +{LEAD_BY_OFFSET[offset]} h)"
              + (f" — dont {n_ag} AGRUME" if n_ag else "")
              + (f", qui ne donneront AUCUNE ligne : horizon 24 h, moins de "
                 f"{MIN_HOURS_DAILY} heures appariables à cet offset"
                 if n_ag and offset else ""))
        # ⚠️ ET LA LIGNE QUI NOMME LE FLUX. « 1 partie sur 2 » sans son
        # flux se lit « il manque un flux sur trois » : `snapshot_rows`
        # en lit trois (`fcst`, `fcstagrume`, `fcstarome`) et seul
        # `fcst/` est partitionné.
        ligne = dire_bilan_parties(bilan, offset)
        print(f"     {ligne}",
              file=sys.stderr if ligne.startswith("⛔") else sys.stdout)

    # ── 1 bis. le bilan des parties EN BASE (lot S0.6) ────────────
    #
    # ⚠️ TOUT CE BLOC EST SOUS `try`, POUR LA MÊME RAISON QUE CELUI DE LA
    # PRESSION (S1) : la table est neuve, son SQL est exécuté par Yann et
    # pas par ce script, et une notation qui tomberait ENTIÈRE parce
    # qu'une ligne de DIAGNOSTIC n'a pas pu s'écrire serait le remède
    # pire que le mal. Le journal, lui, a déjà dit la même chose
    # ci-dessus : la base ajoute la lisibilité pour le tableau de bord,
    # elle n'est pas le seul endroit où le fait existe.
    #
    # ⓘ ORDRE DE DÉPLOIEMENT RECOMMANDÉ : la table AVANT le code. Mais
    # grâce à ce `try`, ce n'est plus une CONDITION — c'est un confort.
    # Un ordre de déploiement qu'il faut se rappeler est un ordre qu'on
    # oubliera un soir de fatigue.
    try:
        cp_rows = collect_part_rows(day, bilans_parties)
        n = sb.upsert("model_verif_collect_part", cp_rows, "day,flux")
        incidents = [r for r in cp_rows
                     if r["etat"] not in ("ok", "avant_partition")]
        print(f"  → model_verif_collect_part : {n} ligne(s)"
              + (f", dont {len(incidents)} INCIDENT(S)" if incidents else ""))
    except Exception as exc:                           # noqa: BLE001
        print(f"  ⚠️ model_verif_collect_part : {type(exc).__name__} — {exc}. "
              f"Le bilan des parties reste dans le journal ci-dessus ; la "
              f"notation n'est pas affectée. (Jouer "
              f"`supabase_step48_lot_s06_collect_part.sql`.)",
              file=sys.stderr)

    # ⚠️ TOUTES LES SOURCES DE VENT — cf. `all_obs_rows`, S0.2 (21/08).
    obs_day = all_obs_rows(root, day, st)
    obs_prev = all_obs_rows(root, day - timedelta(days=1), st)
    print(f"  observations du jour : {len(obs_day)} balises, "
          f"veille : {len(obs_prev)}")
    if not obs_day:
        print("❌ aucune observation pour cette journée — rien à noter.",
              file=sys.stderr)
        return 1
    if not obs_prev:
        # Ce n'est pas fatal, mais il faut le DIRE : sans la veille, la
        # persistance est incalculable et `beats_persist` restera nul.
        print("  ⚠️ pas d'observations de la veille : le skill contre la "
              "persistance ne sera pas calculable pour cette journée.")

    # ── 2-3. apparier et écrire l'agrégat quotidien ──────────────
    t_clim = time.monotonic()
    clim = climatology_by_station(root, day, st, utc_offset_s)
    print(f"  climatologie horaire : {len(clim)} balises "
          f"({time.monotonic() - t_clim:.1f} s)"
          + ("" if clim else " — archive trop courte, seconde référence "
                             "indisponible, `beats_clim` restera nul"))
    # ── l'antécédent du biais de site (lot S2) ───────────────────
    t_prior = time.monotonic()
    prior = prior_biais(root, day)
    print(f"  antécédent du biais : {len(prior)} couples balise×modèle×échéance "
          f"sur {BIAIS_PRIOR_JOURS} j de cache ({time.monotonic() - t_prior:.1f} s)"
          + ("" if prior else
             f" — ⓘ vide : le cache de rejeu est creux ou vient de changer de "
             f"formule ({REPLAY_FORMULA}). Les colonnes corrigées resteront "
             f"nulles cette nuit ; `--replay-budget 30` comble d'un coup."))
    temoin: list = []
    rows, banded = daily_rows(day, snapshots, obs_day, obs_prev, utc_offset_s,
                              clim, bias_prior=prior, temoin=temoin)
    print(f"  {len(rows)} agrégats quotidiens, {len(banded)} détails par tranche")
    part_temoin = bilan_temoin(temoin)
    if part_temoin:
        print(f"  ⛔ témoin du corrigé : {part_temoin['texte']}")
    if rows:
        n = sb.upsert("model_verif_daily", _pour_la_base(sb, "model_verif_daily", rows),
                      "day,source,station_id,model,lead_h,fcst_src")
        print(f"  → model_verif_daily : {n} lignes")
    # ⚠️ Le cache de rejeu est alimenté PAR CE CALCUL-CI, pas par un
    # second. La journée notée ce soir entre donc dans la fenêtre du
    # chemin régime sans coûter une seule seconde de plus. C'est ce qui
    # rend le rejeu tenable en régime de croisière : le run ne rattrape
    # que le passé, et le passé se remplit une fois.
    replay_write(root, day, rows)

    # ── 4-5. zones, accumulateurs, scores ────────────────────────
    # ⚠️ Chaque `select` passe la clé primaire de sa table en `order` :
    # c'est ce qui rend la pagination cohérente (cf. `Supabase.select`).
    # `station_zone` tenait sous les 1 000 lignes (647 le 08/08) et
    # n'était donc pas tronquée — mais rien ne garantit qu'elle y reste,
    # et un plafond qu'on ne franchit pas encore reste un plafond.
    zones_raw = sb.select("station_zone", order="source,station_id")
    zone_of = {f"{z['source']}:{z['station_id']}": z for z in zones_raw}

    # ── 3 bis. la pression (E6, lot S1) ───────────────────────────
    #
    # ⚠️ TOUT CE BLOC EST SOUS `try`, ET C'EST DÉLIBÉRÉ. La notation du
    # vent tourne depuis quatorze nuits ; la pression est neuve, sa
    # table peut ne pas encore exister (le SQL est exécuté par Yann,
    # pas par ce script), et ses archives commencent le 22/08. Une
    # exception ici ne doit JAMAIS emporter le run de vent avec elle —
    # ce serait échanger un chantier qui marche contre un chantier qui
    # démarre. Elle est journalisée en toutes lettres, pas avalée.
    #
    # ⓘ Placé APRÈS `station_zone` parce que l'appariement a besoin de
    # `dem_alt_m` — la seule altitude que les points Pioupiou possèdent,
    # et la seule qui soit sur la même échelle que celle des stations.
    try:
        pres_obs = pres_obs_rows(root, day, st)
        if not pres_obs:
            print("  ⓘ pression : aucune archive d'observation pour cette "
                  "journée — normal avant le 22/08 (flux S0.2 déployés le "
                  "21/08). Rien noté, rien écrit.")
        else:
            p_rows, p_bilan = pressure_rows(day, snapshots, pres_obs, zone_of)
            print(f"  pression : {p_bilan}")
            if p_rows:
                n = sb.upsert("model_verif_daily_pres",
                              _pour_la_base(sb, "model_verif_daily_pres", p_rows),
                              "day,source,station_id,model,lead_h,fcst_src")
                print(f"  → model_verif_daily_pres : {n} lignes")
    except Exception as exc:                       # noqa: BLE001
        print(f"  ⚠️ pression (S1) : {type(exc).__name__} — {exc}. "
              f"La notation du VENT n'est pas affectée.", file=sys.stderr)

    if not zone_of:
        print("  ⓘ `station_zone` est vide : aucune balise n'est encore")
        print("     rattachée à son bassin-versant. Les accumulateurs et les")
        print("     scores de zone sont SAUTÉS — pas calculés au hasard.")
        print("     (l'affectation demande le relief ; elle n'est pas dans ce lot)")
    else:
        needed = zone_rows_needed(list(zone_of.values()))
        if needed:
            sb.upsert("model_zone", needed, "zone_id")

        current_raw = sb.select(
            "model_character",
            order="zone_id,model,lead_h,regime,band,metric,event_type")
        current = {}
        for a in current_raw:
            last = a.get("last_day")
            current[(a["zone_id"], a["model"], a["lead_h"], a["regime"],
                     a["band"], a["metric"])] = S.Accumulator(
                sum_w=a["sum_w"], sum_wx=a["sum_wx"], sum_wx2=a["sum_wx2"],
                days=a["days"],
                last_day=int(datetime.strptime(last, "%Y-%m-%d")
                             .replace(tzinfo=timezone.utc).timestamp()) * 1000
                if last else None)
        updates = accumulator_updates(banded, zone_of, day, current)
        if updates:
            n = sb.upsert("model_character", updates,
                          "zone_id,model,lead_h,regime,band,metric,event_type")
            print(f"  → model_character : {n} accumulateurs avancés")

        # ── 4 bis. événements (lot F) ────────────────────────────
        # ⚠️ Après les zones, jamais avant : `model_verif_event.zone_id`
        # porte une clé étrangère, et un événement sans case fine n'a de
        # toute façon aucun sens — la confirmation réseau se fait entre
        # balises d'une MÊME case.
        ev_rows, bilan = event_rows(day, snapshots, obs_day, zone_of, utc_offset_s)
        print(f"  événements : {bilan}")
        # Purge d'abord : la table n'a pas de clé d'unicité (une ligne par
        # événement individuel), donc seule la réécriture complète de la
        # journée rend le run rejouable sans doubler les lignes.
        sb.delete("model_verif_event", f"?day=eq.{day:%Y-%m-%d}")
        if ev_rows:
            n = sb.insert("model_verif_event", ev_rows)
            par_type = defaultdict(int)
            for r in ev_rows:
                par_type[r["event_type"]] += 1
            detail = ", ".join(f"{k} {v}" for k, v in sorted(par_type.items()))
            print(f"  → model_verif_event : {n} lignes ({detail})")
        else:
            print("  → model_verif_event : aucune ligne (aucun événement "
                  "confirmé par le réseau cette journée)")

        since_ev = (day - timedelta(days=ROLLING_DAYS - 1)).strftime("%Y-%m-%d")
        ev_all = sb.select("model_verif_event", f"?day=gte.{since_ev}",
                           order="id")
        ev_scores, rejets, inconnues, retenues = event_scores(ev_all, zone_of)
        if inconnues:
            print(f"  ⚠️ {inconnues} lignes d'événement sur une zone qui n'a "
                  f"plus aucune balise rattachée : publiées telles quelles, "
                  f"sans chaîne de repli.")
        if retenues:
            print(f"  ⓘ {retenues} lignes NON publiées (familles hors "
                  f"{', '.join(EVENT_PUBLISHABLE_TYPES)}) : elles restent en "
                  f"base et le JSON dit pourquoi.")
        print(f"  événements notés : {len(ev_scores)} combinaisons publiables, "
              f"{rejets} écartées sous le quorum de {EVENT_MIN_OCCURRENCES}")
        _publish_events(st, ev_scores, as_of, rejets, retenues, args.dry_run)

        since = (day - timedelta(days=ROLLING_DAYS - 1)).strftime("%Y-%m-%d")
        daily = sb.select("model_verif_daily", f"?day=gte.{since}",
                          order="day,source,station_id,model,lead_h,fcst_src")
        t_roll = time.monotonic()
        scores = rolling_scores(daily, zone_of, as_of)
        print(f"  score glissant : {len(scores)} lignes "
              f"({time.monotonic() - t_roll:.1f} s)")
        # `model_zone` est relue APRÈS l'upsert des échelons 2 et 4, pour
        # que `agg_level` soit littéralement le `kind` de la zone et non
        # une déduction faite sur la forme de son identifiant. Une table
        # de quelques centaines de lignes, une fois par nuit.
        kind_of = {r["zone_id"]: r["kind"]
                   for r in sb.select("model_zone", order="zone_id")}

        # ── chemin régime : archive rejouée, plus accumulateurs ───
        t_replay = time.monotonic()
        units, bilan_replay = replay_window(
            root, day, st, utc_offset_s, args.regime_days, args.replay_budget)
        print(f"  rejeu d'archive : {bilan_replay} en "
              f"{time.monotonic() - t_replay:.1f} s")
        t_reg = time.monotonic()
        reg_rows = regime_scores(units, as_of, zone_of, kind_of)
        scores += reg_rows
        # ⚠️ CHIFFRE À SURVEILLER. Mesuré le 09/08 sur un jeu synthétique
        # à la taille réelle (194 100 balise-jours, 30 jours) : 85,6 s.
        # C'est le poste le plus cher du lot G, et il grandit avec la
        # profondeur d'archive. Le jour où il déborde, la manette est
        # `--regime-days`, pas le timer.
        print(f"  score par régime : {len(reg_rows)} lignes "
              f"({time.monotonic() - t_reg:.1f} s)")

        # ⛔ UN RANG PUBLIÉ SUR UNE JOURNÉE INCOMPLÈTE DOIT LE DIRE
        # (lot S0.6). `_apply_rank` classe les modèles PRÉSENTS : si la
        # passe de surface a échoué, il publie « 1ᵉʳ sur 2 » sans que
        # rien ne dise que sept manquaient. On garde le classement — un
        # classement absent et un classement partiel se lisent pareil à
        # l'écran, et le second au moins se dit — mais on le QUALIFIE.
        n_marques = marquer_parties_manquantes(scores, bilans_parties)
        if n_marques:
            print(f"  ⛔ {n_marques} rang(s) publié(s) sur une journée "
                  f"d'émission INCOMPLÈTE → `rank_reason = "
                  f"{RANK_REASON_PARTIE_MANQUANTE}`", file=sys.stderr)
        n_pool = apply_pooling(scores, list(zone_of.values()))
        print(f"  rétrécissement vers le parent : {n_pool} cases fines "
              f"rapprochées de leur échelon supérieur (poids emprunté publié)")

        t_stab = time.monotonic()
        stabilite = stability_report(units, zone_of, as_of, kind_of)
        print(f"  ({time.monotonic() - t_stab:.1f} s)", end=" ")
        print(f"  stabilité des rangs : {stabilite['reason']}"
              + (f" · tau = {stabilite['kendall_tau']} sur "
                 f"{stabilite['n_comparable']} cases, "
                 f"{stabilite['shared_days']} jour(s) partagé(s)"
                 if stabilite["kendall_tau"] is not None else ""))
        print(f"     ⓘ {stabilite['covers']}")

        if scores:
            n = _upsert_scores(sb, _pour_la_base(sb, "model_score_zone",
                                                 scores))
            print(f"  → model_score_zone : {n} lignes")
            # Le JSON publié, lui, porte TOUT : il n'a pas de schéma à
            # respecter, et c'est lui que lira l'écran des bêta-testeurs.
            # ⚠️ `variable` EST ÉCRIT EXPLICITEMENT SUR CHAQUE LIGNE,
            # jamais déduit d'une absence (lot S1). L'écran ne doit
            # jamais additionner des hPa et des km/h ; « pas de champ »
            # se lit un jour comme « pas de valeur », et c'est la
            # deuxième moitié de ce garde-fou qui vit côté web (une
            # ligne sans `variable` y est traitée comme `wind`, pour
            # qu'un JSON servi par le CDN pendant l'heure de cache ne
            # fasse pas disparaître le tableau).
            for _s in scores:
                _s.setdefault("variable", "wind")
            _publish(st, scores, as_of, args.dry_run,
                     meta={"stability": stabilite,
                           "replay": bilan_replay,
                           "regime_days": args.regime_days,
                           # ⛔ Le témoin voyage AVEC le corrigé, dans le
                           # même objet, pour qu'on ne puisse pas lire
                           # l'un sans l'autre (lot S2).
                           "bias_correction": {
                               "prior_days": BIAIS_PRIOR_JOURS,
                               "half_life_days": BIAIS_DEMI_VIE_J,
                               "min_days": BIAIS_MIN_JOURS,
                               "estimator": "ls_slope_sum_of_over_sum_ff",
                               "pairs_with_prior": len(prior),
                               "witness": part_temoin,
                           },
                           "climatology_stations": len(clim),
                           "events_calibrated": EVENTS_CALIBRATED,
                           "audience": "beta"})

    # ── 6. purge ─────────────────────────────────────────────────
    if not args.no_purge:
        today = datetime.now(timezone.utc)
        sb.delete("model_verif_daily",
                  f"?day=lt.{(today - timedelta(days=RETENTION_DAILY_D)):%Y-%m-%d}")
        # Même rétention que sa sœur : la pression se rejoue depuis
        # l'archive R2 comme le vent, donc garder 30 jours en base
        # n'apporte rien de plus qu'à `model_verif_daily`.
        # ⓘ `Supabase.delete` journalise et continue sur un HTTP d'erreur
        # (cf. sa définition) : tant que le SQL du S1 n'est pas passé,
        # cette ligne écrit un ⚠️ dans le journal et ne casse rien.
        sb.delete("model_verif_daily_pres",
                  f"?day=lt.{(today - timedelta(days=RETENTION_DAILY_D)):%Y-%m-%d}")
        sb.delete("model_verif_event",
                  f"?day=lt.{(today - timedelta(days=RETENTION_EVENT_D)):%Y-%m-%d}")
        sb.delete("model_score_zone",
                  f"?as_of=lt.{(today - timedelta(days=RETENTION_SCORE_D)):%Y-%m-%d}")
        # ⚠️ `model_character` ne se purge JAMAIS : c'est son intérêt.
        # L'archive R2 non plus — ~544 Mo/an mesurés, et c'est ce qui
        # rend chaque amélioration de la formule rejouable.

    print(f"✅ terminé ({sb.ecritures} lignes écrites en base)")
    return 0


def _publish(st, scores: list[dict], as_of: datetime, dry_run: bool,
             meta: dict | None = None):
    """Publie le JSON que lira la PWA.

    Même patron que les packs de site : R2 sert le fichier, Supabase
    n'est pas sur le chemin de lecture. Zéro requête SQL par ouverture
    de fiche, zéro requête Open-Meteo côté pilote.
    """
    if st is None or dry_run:
        print("  ⓘ publication R2 sautée (pas de storage, ou dry-run)")
        return
    from storage import CACHE_REECRIT             # type: ignore
    # ⚠️ `audience: "beta"` VOYAGE AVEC LES CHIFFRES. Le garde de
    # l'écran est côté PWA (`isAdmin || isBetaTester`), et c'est lui qui
    # décide ; ce champ ne protège rien. Il sert à ce qu'un fichier
    # retrouvé seul, ou lu par un outil qu'on n'a pas encore écrit, dise
    # de lui-même qu'il n'est pas destiné aux pilotes. Un JSON qui ne
    # porte pas sa propre destination finit toujours par être servi à
    # quelqu'un d'autre.
    body = json.dumps({"as_of": as_of.strftime("%Y-%m-%d"),
                       **(meta or {}), "scores": scores},
                      separators=(",", ":")).encode("utf-8")
    # Clé STABLE, réécrite chaque nuit → cache court obligatoire. Un TTL
    # long laisserait un edge CDN servir un classement périmé bien après
    # le run, et le hard-refresh n'y pourrait rien (leçon des 23-24/07).
    st.put("model_scores.json", body, cache_control=CACHE_REECRIT)
    st.bilan()
    print(f"  → model_scores.json publié ({len(body) / 1024:.0f} Ko)")


if __name__ == "__main__":
    sys.exit(main())
