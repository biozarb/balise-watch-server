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
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import events as EV  # noqa: E402
import scoring as S  # noqa: E402

DAY_MS = 86_400_000

#: Classe d'échéance ← nombre de jours entre le snapshot et la journée notée.
LEAD_BY_OFFSET = {0: 6, 1: 24, 2: 48}

#: Heures minimales appariées pour qu'une journée-balise-modèle compte.
#: En dessous, l'agrégat est du bruit : une balise qui n'a émis que
#: trois heures ne dit rien de la qualité d'un modèle sur la journée.
MIN_HOURS_DAILY = 6

#: Balises minimales dans une case avant de publier un score de zone.
MIN_STATIONS_ZONE = 3

#: Fenêtre du score glissant (§8.4).
ROLLING_DAYS = 15

RETENTION_DAILY_D = 30
RETENTION_EVENT_D = 90
RETENTION_SCORE_D = 7


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


def fcst_key(day: datetime) -> str:
    return f"fcst/{day:%Y/%m}/fcst_{day:%Y-%m-%d}.ndjson.gz"


def obs_key(day: datetime) -> str:
    return f"obs/{day:%Y/%m}/obs_{day:%Y-%m-%d}.ndjson.gz"


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
               utc_offset_s: int):
    """Rend (lignes model_verif_daily, détail par tranche de vent).

    Le détail par tranche ne va PAS en base : il alimente les
    accumulateurs le soir même. §15.4 — « ce modèle sous-estime le
    vent » est presque toujours faux en moyenne et vrai dans une
    tranche, un modèle collant au vent faible et écrêtant le vent fort.
    Une seule colonne `bias_ratio` par journée ne peut pas porter ça ;
    la stocker par tranche triplerait la table pour une donnée qui ne
    sert qu'une fois.
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
                "bias_ratio": _r(bias.speed_ratio),
                "bias_dir_deg": _r(bias.dir_offset),
                "vector_ratio": _r(err.vector_ratio),
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
    out = EV.detect_all(series, EVENT_ONSET_KMH)
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

def rolling_scores(daily: list[dict], zone_of: dict[str, dict], as_of: datetime):
    """Le score « 15 jours glissants » du §8, depuis `model_verif_daily`.

    ⚠️ Le bootstrap rééchantillonne des BALISES-JOURS, pas des heures :
    deux heures consécutives de la même balise ne sont pas
    indépendantes, et rééchantillonner à l'heure produirait un
    intervalle beaucoup trop étroit — donc des gagnants qui n'en sont
    pas (§8.4).
    """
    # (zone, model, lead) → {err: [...], mse_m: [...], mse_r: [...], st: set}
    acc: dict[tuple, dict] = defaultdict(
        lambda: {"err": [], "mse_m": [], "mse_r": [], "st": set(), "n_hours": 0})
    for d in daily:
        z = zone_of.get(f"{d['source']}:{d['station_id']}")
        if z is None or z.get("basin_uncertain"):
            continue
        if d.get("err_vec_med") is None:
            continue
        for zid, level in fallback_chain(z):
            b = acc[(zid, d["model"], d["lead_h"], level)]
            b["err"].append(d["err_vec_med"])
            if d.get("mse_model") is not None and d.get("mse_persist") is not None:
                b["mse_m"].append(d["mse_model"])
                b["mse_r"].append(d["mse_persist"])
            b["st"].add(f"{d['source']}:{d['station_id']}")
            b["n_hours"] += d.get("n_hours") or 0

    rows: list[dict] = []
    # Le classement se décide zone par zone et échéance par échéance :
    # comparer deux modèles sur des zones différentes n'a aucun sens.
    by_case: dict[tuple, list[dict]] = defaultdict(list)
    for (zid, model, lead, level), b in acc.items():
        if len(b["st"]) < MIN_STATIONS_ZONE:
            continue
        med, lo, hi = S.bootstrap_ci(b["err"])
        mse_m = S.median(b["mse_m"])
        mse_r = S.median(b["mse_r"])
        ordered = sorted(b["err"])
        row = {
            "as_of": as_of.strftime("%Y-%m-%d"), "zone_id": zid, "model": model,
            "lead_h": lead, "window_kind": "rolling15", "regime": "all",
            "agg_level": level, "n_stations": len(b["st"]),
            "n_hours": b["n_hours"], "occurrences": len(b["err"]),
            "typical_err_kmh": _r(med),
            "worst_decile_kmh": _r(ordered[min(len(ordered) - 1,
                                               math.floor(len(ordered) * 0.9))])
            if len(ordered) >= 5 else None,
            "beats_persist": None if mse_m is None or mse_r is None else mse_m < mse_r,
            "skill": None if not mse_r else _r(1 - mse_m / mse_r),
            "ci_low": _r(lo), "ci_high": _r(hi),
            "rank": None, "rank_reason": None,
        }
        rows.append(row)
        by_case[(zid, lead, level)].append(row)

    _apply_rank(by_case)
    return rows


def regime_scores(accs: list[dict], as_of: datetime, kind_of: dict[str, str]):
    """Le score par régime du §16.1, depuis les accumulateurs.

    ⚠️ CE N'EST PAS UNE FENÊTRE GLISSANTE, et c'est tout l'intérêt.
    « Les 15 derniers jours » mélange un flux de nord, deux jours de
    marin et trois jours de brise — la moyenne qui en sort n'est vraie
    aucun de ces jours. Ici on lit « les N dernières fois qu'on a eu CE
    régime ici », quelle que soit leur ancienneté.

    ⚠️ `kind_of` EST OBLIGATOIRE — c'est `model_zone` elle-même,
    lue en base, et non une déduction. Cette fonction devinait
    auparavant l'échelon en RENIFLANT la forme du `zone_id` (`*:` au
    début, `:*` à la fin, sinon « bassin »). Deux conséquences, toutes
    deux fausses : `alpes-nord:valley` était publié
    `agg_level = 'basin_landform'` alors que sa ligne `model_zone` dit
    `massif_landform`, et l'échelon 2 était donc INATTEIGNABLE dans
    cette colonne. Le SQL de step35 prévient explicitement contre cette
    dépendance au format de chaîne : `kind` y est redondant avec
    `zone_id` pour qu'on n'ait jamais à renifler l'un pour retrouver
    l'autre. Passer la table rend l'égalité `agg_level == kind` vraie
    par construction plutôt que par coïncidence.
    """
    by_key: dict[tuple, dict] = defaultdict(dict)
    for a in accs:
        if a["band"] != "all" or a["regime"] == "all":
            continue
        by_key[(a["zone_id"], a["model"], a["lead_h"], a["regime"])][a["metric"]] = a

    rows: list[dict] = []
    by_case: dict[tuple, list[dict]] = defaultdict(list)
    for (zid, model, lead, regime), metrics in by_key.items():
        err = metrics.get("errKmh")
        if err is None or err["sum_w"] <= 0:
            continue
        mm, mr = metrics.get("mseModel"), metrics.get("msePersist")
        beats = None
        if mm and mr and mm["sum_w"] > 0 and mr["sum_w"] > 0:
            beats = (mm["sum_wx"] / mm["sum_w"]) < (mr["sum_wx"] / mr["sum_w"])
        # ⚠️ Un `zone_id` absent de `model_zone` est IMPOSSIBLE :
        # `model_character.zone_id` porte la clé étrangère. Si ça
        # arrivait quand même, mieux vaut sauter la ligne que publier un
        # échelon inventé — un score anonyme sur sa précision ment.
        level = kind_of.get(zid)
        if level is None:
            print(f"  ⚠️ zone inconnue de model_zone, score sauté : {zid}",
                  file=sys.stderr)
            continue
        row = {
            "as_of": as_of.strftime("%Y-%m-%d"), "zone_id": zid, "model": model,
            "lead_h": lead, "window_kind": "regime", "regime": regime,
            "agg_level": level, "n_stations": 0, "n_hours": 0,
            "occurrences": err["days"],
            "typical_err_kmh": _r(err["sum_wx"] / err["sum_w"]),
            "worst_decile_kmh": None, "beats_persist": beats,
            "skill": None, "ci_low": None, "ci_high": None,
            "rank": None, "rank_reason": None,
        }
        rows.append(row)
        by_case[(zid, lead, regime)].append(row)

    _apply_rank(by_case)
    return rows


def _apply_rank(by_case: dict[tuple, list[dict]]):
    """Classe, ou refuse de classer.

    ⚠️ `rank` NUL SUR TOUTES LES LIGNES est un résultat de première
    classe, et ce sera le cas le plus fréquent. Une colonne qui force un
    classement fabriquerait un gagnant là où il n'y en a pas — c'est le
    reproche fait au 🏆 du score actuel.
    """
    for rows in by_case.values():
        key, reason = S.rank_by_regime(
            [{"model": r["model"], "typical_err_kmh": r["typical_err_kmh"],
              "occurrences": r["occurrences"]} for r in rows])
        for r in rows:
            r["rank_reason"] = reason
        if key is None:
            continue
        ordered = sorted((r for r in rows if r["typical_err_kmh"] is not None),
                         key=lambda r: r["typical_err_kmh"])
        for i, r in enumerate(ordered, 1):
            r["rank"] = i


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="/var/lib/bw-model-verif")
    ap.add_argument("--day", default=None, help="journée à noter (défaut : hier)")
    ap.add_argument("--utc-offset-h", type=float, default=2.0,
                    help="décalage local des sites, pour la fenêtre volable "
                         "(défaut : 2 = heure d'été française)")
    ap.add_argument("--no-purge", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
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
    for offset in LEAD_BY_OFFSET:
        rows = read_ndjson(root, fcst_key(day - timedelta(days=offset)), st)
        snapshots[offset] = rows
        print(f"  prévisions émises J-{offset} : {len(rows)} lignes "
              f"(classe +{LEAD_BY_OFFSET[offset]} h)")
    obs_day = read_ndjson(root, obs_key(day), st)
    obs_prev = read_ndjson(root, obs_key(day - timedelta(days=1)), st)
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
    rows, banded = daily_rows(day, snapshots, obs_day, obs_prev, utc_offset_s)
    print(f"  {len(rows)} agrégats quotidiens, {len(banded)} détails par tranche")
    if rows:
        n = sb.upsert("model_verif_daily", rows,
                      "day,source,station_id,model,lead_h,fcst_src")
        print(f"  → model_verif_daily : {n} lignes")

    # ── 4-5. zones, accumulateurs, scores ────────────────────────
    # ⚠️ Chaque `select` passe la clé primaire de sa table en `order` :
    # c'est ce qui rend la pagination cohérente (cf. `Supabase.select`).
    # `station_zone` tenait sous les 1 000 lignes (647 le 08/08) et
    # n'était donc pas tronquée — mais rien ne garantit qu'elle y reste,
    # et un plafond qu'on ne franchit pas encore reste un plafond.
    zones_raw = sb.select("station_zone", order="source,station_id")
    zone_of = {f"{z['source']}:{z['station_id']}": z for z in zones_raw}
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
        scores = rolling_scores(daily, zone_of, as_of)
        accs = sb.select("model_character",
                         order="zone_id,model,lead_h,regime,band,metric,event_type")
        # `model_zone` est relue APRÈS l'upsert des échelons 2 et 4, pour
        # que `agg_level` soit littéralement le `kind` de la zone et non
        # une déduction faite sur la forme de son identifiant. Une table
        # de quelques centaines de lignes, une fois par nuit.
        kind_of = {r["zone_id"]: r["kind"]
                   for r in sb.select("model_zone", order="zone_id")}
        scores += regime_scores(accs, as_of, kind_of)
        if scores:
            n = sb.upsert("model_score_zone", scores,
                          "as_of,zone_id,model,lead_h,window_kind,regime")
            print(f"  → model_score_zone : {n} lignes")
            _publish(st, scores, as_of, args.dry_run)

    # ── 6. purge ─────────────────────────────────────────────────
    if not args.no_purge:
        today = datetime.now(timezone.utc)
        sb.delete("model_verif_daily",
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


def _publish(st, scores: list[dict], as_of: datetime, dry_run: bool):
    """Publie le JSON que lira la PWA.

    Même patron que les packs de site : R2 sert le fichier, Supabase
    n'est pas sur le chemin de lecture. Zéro requête SQL par ouverture
    de fiche, zéro requête Open-Meteo côté pilote.
    """
    if st is None or dry_run:
        print("  ⓘ publication R2 sautée (pas de storage, ou dry-run)")
        return
    from storage import CACHE_REECRIT             # type: ignore
    body = json.dumps({"as_of": as_of.strftime("%Y-%m-%d"), "scores": scores},
                      separators=(",", ":")).encode("utf-8")
    # Clé STABLE, réécrite chaque nuit → cache court obligatoire. Un TTL
    # long laisserait un edge CDN servir un classement périmé bien après
    # le run, et le hard-refresh n'y pourrait rien (leçon des 23-24/07).
    st.put("model_scores.json", body, cache_control=CACHE_REECRIT)
    st.bilan()
    print(f"  → model_scores.json publié ({len(body) / 1024:.0f} Ko)")


if __name__ == "__main__":
    sys.exit(main())
