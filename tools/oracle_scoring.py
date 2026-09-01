#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  tools/oracle_scoring.py — L'ORACLE BATCH MENSUEL (lot L12, 01/09/2026)
#
#  Conception et mesures : `amelioration scoring/agrume/
#  LOTS_SCORING_AGRUME_27-08.md`, lot L12 · audit §4.7.
#
#  ═══ CE QU'IL RÉPOND, ET POURQUOI PERSONNE D'AUTRE NE LE RÉPOND ═══
#
#  Le contrôle n°2 (`verif/recalcul_balise_jour.py`, lot S3) vérifie
#  UNE journée : il rejoue 20 balise-jours tirés au sort de la nuit qui
#  vient de tourner et compare. Il ne peut rien dire de la FENÊTRE — des accumulateurs, des moyennes exponentielles,
#  des quinze jours glissants. Or c'est là que les dérives sont
#  silencieuses : un accumulateur qui repart de zéro, une demi-vie
#  appliquée deux fois, une case qui garde un balise-jour hors fenêtre
#  ne PLANTENT pas. Ils publient un nombre plausible et faux.
#
#  Cet oracle relit les ARCHIVES LOCALES sur une fenêtre longue et
#  recalcule, PAR UN CHEMIN QUI N'EST PAS CELUI DE LA PRODUCTION :
#
#    · `err_vec_med` / `err_vec_rms` par balise-jour → `model_verif_daily`
#    · la médiane des cases `rolling15` de zones tirées au sort
#      → `model_score_zone.typical_err_kmh`
#
#  Tout écart supérieur à `SEUIL_ECART_KMH` est NOMMÉ, balise par
#  balise. Le rapport est horodaté ; son seul pouvoir est d'être lu.
#
#  ⓘ ET C'EST UN TROISIÈME CHEMIN, pas une réutilisation du second.
#  `recalcul_balise_jour.py` est lui aussi indépendant de `scoring.py` ;
#  l'importer ici ferait des deux contrôles UNE seule implémentation, et
#  le jour où elle se tromperait, les deux se tairaient ensemble. Deux
#  recalculs écrits séparément peuvent se tromper pareil — c'est un
#  accident, et on peut au moins le rendre improbable.
#
#  ═══ ⛔ POURQUOI IL N'IMPORTE NI `scoring.py` NI `score.py` ═══
#
#  C'est le piège nº 1 de la phase B, et c'est TOUT le lot. La pente
#  naturelle est d'importer le code testé — il est là, il est bancé, il
#  est juste. Un oracle qui importe le code testé compare la faute à
#  elle-même : il rendra toujours ✅, y compris la nuit où l'EWMA se
#  remet à zéro. Ce fichier ne partage donc AUCUNE ligne de calcul avec
#  la chaîne : ni `S.pair_series`, ni `S.series_error`, ni
#  `S.median`, ni `INF.block_median_ci`, ni la classe `Supabase`. Il
#  n'importe rien du dépôt, et une assertion à l'import le vérifie.
#
#  ⚠️ CE QU'IL NE PEUT PAS VOIR, ET IL FAUT LE DIRE. Les constantes de
#  la méthode (demi-fenêtre, seuil de girouette, plancher d'heures,
#  quorum de case, chaîne de repli) sont TRANSCRITES À LA MAIN ici,
#  depuis la conception — pas importées. Conséquences, dans les deux
#  sens :
#    · si quelqu'un change une de ces valeurs dans `scoring.py`, cet
#      oracle CRIE. C'est voulu : un changement de définition doit se
#      voir, et c'est ici qu'il se voit.
#    · si la DÉFINITION elle-même est fausse (les deux côtés d'accord,
#      et tous deux dans l'erreur), il ne voit rien. Aucun oracle ne le
#      peut ; c'est le travail de l'audit, pas du sien.
#  Il ne vérifie pas non plus les colonnes de skill, de MSE ni de biais
#  — seulement l'erreur et sa médiane de case. Et il ne sait rien de ce
#  qui n'est pas dans l'archive : une archive fausse rend une chaîne
#  fausse ET un oracle faux, à l'identique.
#
#      python3 tools/oracle_scoring.py --jours 30
#      python3 tools/oracle_scoring.py --jours 7 --sans-base   # hors ligne
#
#  Code de sortie : 0 si aucun écart, 1 sinon (c'est ce qui réveille le
#  canal d'alerte quand il est lancé par le mode `oracle` de `run.sh`).
# ══════════════════════════════════════════════════════════════════════
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import pathlib
import random
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import numpy as np

# ══════════════════════════════════════════════════════════════════
#  L'INDÉPENDANCE, VÉRIFIÉE À L'IMPORT
# ══════════════════════════════════════════════════════════════════
#
# ⛔ Une règle écrite en commentaire est une règle qu'on enfreint sans
# le savoir. Celle-ci se vérifie : si un jour quelqu'un ajoute
# `import scoring` en tête pour « réutiliser la médiane », ce fichier
# refuse de démarrer plutôt que de rendre un ✅ qui ne prouve rien.
_INTERDITS = ("scoring", "score", "inference", "murphy", "duel", "collect")


def _verifier_independance(modules=None) -> None:
    charges = sys.modules if modules is None else modules
    fautifs = sorted(m for m in _INTERDITS if m in charges)
    if fautifs:
        raise SystemExit(
            f"⛔ oracle_scoring : {', '.join(fautifs)} est importé. Un "
            f"oracle qui importe le code testé compare la faute à "
            f"elle-même — c'est le piège nº 1 de la phase B, et c'est "
            f"la seule raison d'être de ce fichier.")


# ══════════════════════════════════════════════════════════════════
#  LA SPÉCIFICATION, TRANSCRITE À LA MAIN
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ CHAQUE VALEUR CI-DESSOUS EST UNE COPIE MANUELLE de la conception,
# jamais un import. C'est ce qui fait qu'un changement de définition
# dans `scoring.py` rend cet oracle BAVARD au lieu de le rendre
# complice. Le prix est qu'il faut les tenir à jour à la main — et le
# rapport le dit à chaque passage.

#: Au-delà de quoi un écart est NOMMÉ. 0,01 km/h : deux ordres de
#: grandeur sous le plancher de représentativité le plus bas mesuré au
#: lot L6 (vallée, 1,76 km/h), donc bien en dessous de tout ce qui a un
#: sens physique — ce qui reste est de l'arithmétique, et l'arithmétique
#: ne dérive pas toute seule.
SEUIL_ECART_KMH = 0.01

JOUR_MS = 86_400_000

#: Sous ce vent la girouette raconte n'importe quoi : la direction est
#: jetée (des deux côtés) et l'erreur retombe sur |Δforce|.
VENT_MIN_DIR_KMH = 5.0

#: Demi-fenêtre d'agrégation des relevés autour d'une échéance, PAR PAS
#: DE LA SÉRIE. L'invariant qui la gouverne est arithmétique : deux
#: échéances consécutives ne partagent aucun relevé si et seulement si
#: 2 × demi < pas.
DEMI_FENETRE_MS = {3600: 20 * 60 * 1000, 900: 7 * 60 * 1000}
DEMI_FENETRE_PLAFOND_MS = 20 * 60 * 1000

for _pas_s, _demi_ms in DEMI_FENETRE_MS.items():
    assert 2 * _demi_ms < _pas_s * 1000, (
        f"demi-fenetre {_demi_ms} ms sur un pas de {_pas_s} s : "
        f"2xdemi >= pas, l'appariement perdrait son independance")
del _pas_s, _demi_ms

#: Nombre minimal d'heures appariées pour qu'une balise-jour existe.
PLANCHER_PAR_PAS = {3600: 6, 900: 13}
PLANCHER_DEFAUT = 6

#: Classe d'échéance ← nombre de jours entre l'archive d'émission et la
#: journée notée. Une ligne qui déclare son propre `lead_h` (classes
#: courte et au quart d'heure, étiquettes négatives) l'emporte.
LEAD_PAR_OFFSET = {0: 6, 1: 24, 2: 48}
OFFSETS = (0, 1, 2)

#: La fenêtre du score glissant, et le quorum de balises d'une case.
FENETRE_GLISSANTE_J = 15
MIN_BALISES_CASE = 3

#: Racine de l'état et des archives — même sens que le `--out` de tous
#: les autres jobs du dossier.
RACINE_DEFAUT = "/var/lib/bw-model-verif"


def demi_fenetre_ms(pas_s: int) -> int:
    """La demi-fenêtre d'agrégation d'une série de pas `pas_s`.

    Un pas inconnu n'est pas une erreur : il est servi, mais jamais
    au-delà de ce que l'invariant autorise.
    """
    connu = DEMI_FENETRE_MS.get(int(pas_s))
    if connu is not None:
        return connu
    return max(0, min(DEMI_FENETRE_PLAFOND_MS, (int(pas_s) * 1000) // 2 - 60_000))


def plancher_du_pas(pas_s: int) -> int:
    return PLANCHER_PAR_PAS.get(int(pas_s), PLANCHER_DEFAUT)


def nombre(x) -> float:
    """Le flottant d'une valeur d'archive, ou NaN.

    ⚠️ `True` n'est PAS 1.0 ici. `bool` est une sous-classe de `int` en
    Python, et un booléen glissé dans un tableau de vitesses vaudrait
    « 1 km/h » sans que rien ne le dise. Même refus que le `_finite` de
    la chaîne — transcrit, pas importé.
    """
    if x is None or isinstance(x, bool) or not isinstance(x, (int, float)):
        return math.nan
    v = float(x)
    return v if math.isfinite(v) else math.nan


def lignes_ndjson(chemin: pathlib.Path):
    """Les objets d'une archive, un par un. Jamais la liste entière :
    un flux `fcst/` fait 5 600 lignes de 72 échéances, et l'oracle en
    ouvre trois par journée notée."""
    with gzip.open(chemin, "rt", encoding="utf-8") as f:
        for ligne in f:
            ligne = ligne.strip()
            if ligne:
                yield json.loads(ligne)


def archives_du_jour(racine: pathlib.Path, jour: datetime,
                     famille: str) -> list[pathlib.Path]:
    """Les archives d'une famille (`obs` ou `fcst`) pour une journée,
    PAR ÉNUMÉRATION DU DISQUE.

    ⛔ ET C'EST UN CHOIX D'ORACLE, PAS UNE PARESSE. La chaîne construit
    ses clés par une fonction par flux (`obs_key`, `fcst_agrume_key`,
    `fcst_arome_key`…) : les recopier ici ferait dépendre l'oracle de la
    même liste, et un flux oublié des deux côtés resterait invisible.
    On énumère donc ce qui EST sur le disque. Un flux neuf entre tout
    seul ; un flux que la chaîne a cessé de lire se voit, parce que
    l'oracle sortira des balise-jours que la base n'a pas.
    """
    out: list[pathlib.Path] = []
    if not racine.is_dir():
        return out
    for d in sorted(p for p in racine.iterdir() if p.is_dir()):
        nom = d.name
        if famille == "obs" and not nom.startswith("obs"):
            continue
        if famille == "fcst" and not nom.startswith("fcst"):
            continue
        out.extend(sorted(d.glob(
            f"{jour:%Y/%m}/{nom}_{jour:%Y-%m-%d}*.ndjson.gz")))
    return out


def observations_du_jour(racine: pathlib.Path, jour: datetime) -> dict:
    """Tous les relevés d'une journée, par balise, TRIÉS dans le temps.

    Rend `{ "source:station_id": (t_ms, vitesses, directions) }`, trois
    tableaux numpy alignés. Les valeurs manquantes sont des NaN — pas
    des trous : le tri doit rester aligné.
    """
    brut: dict[str, tuple[list, list, list]] = defaultdict(
        lambda: ([], [], []))
    for chemin in archives_du_jour(racine, jour, "obs"):
        for r in lignes_ndjson(chemin):
            t = r.get("t") or []
            sp = r.get("speed") or []
            di = r.get("dir") or []
            a, b, c = brut[f"{r['source']}:{r['station_id']}"]
            for i, ts in enumerate(t):
                a.append(int(ts) * 1000)
                b.append(nombre(sp[i]) if i < len(sp) else math.nan)
                c.append(nombre(di[i]) if i < len(di) else math.nan)
    out = {}
    for cle, (t, sp, di) in brut.items():
        if not t:
            continue
        ta = np.asarray(t, dtype=np.int64)
        ordre = np.argsort(ta, kind="stable")
        out[cle] = (ta[ordre],
                    np.asarray(sp, dtype=float)[ordre],
                    np.asarray(di, dtype=float)[ordre])
    return out


# ══════════════════════════════════════════════════════════════════
#  L'ERREUR D'UNE BALISE-JOUR — le cœur, et le seul endroit qui compte
# ══════════════════════════════════════════════════════════════════

def erreurs_horaires(ligne: dict, obs: tuple, debut_ms: int,
                     demi_ms: int) -> list[float]:
    """Les erreurs horaires (km/h) d'UNE ligne de prévision sur la
    journée qui commence à `debut_ms`.

    Les échéances sans relevé dans la fenêtre sont ABSENTES — jamais
    comblées, jamais interpolées. Les échéances hors journée aussi.

    ⚠️ LA FORCE OBSERVÉE EST UNE MOYENNE ARITHMÉTIQUE, LA DIRECTION UNE
    MOYENNE VECTORIELLE, et les deux ne portent pas sur la même
    population : un relevé sous `VENT_MIN_DIR_KMH` compte dans la force
    et pas dans la direction (sa girouette est du bruit, et moyenner du
    bruit uniforme tire le vecteur vers zéro, donc fait croire à un vent
    nul là où il y a un vent faible). Un relevé sans vitesse ne compte
    nulle part.
    """
    sp = ligne.get("speed") or []
    di = ligne.get("dir") or []
    t0 = int(ligne["t0"])
    pas = int(ligne["step_s"])
    t_obs, s_obs, d_obs = obs
    fin_ms = debut_ms + JOUR_MS
    errs: list[float] = []
    for i in range(len(sp)):
        t = (t0 + i * pas) * 1000
        if t < debut_ms or t >= fin_ms:
            continue
        fs = nombre(sp[i])
        if math.isnan(fs):
            continue
        g = int(np.searchsorted(t_obs, t - demi_ms, side="left"))
        d = int(np.searchsorted(t_obs, t + demi_ms, side="right"))
        if d <= g:
            continue
        sw = s_obs[g:d]
        avec_vitesse = ~np.isnan(sw)
        if not avec_vitesse.any():
            continue
        obs_speed = float(sw[avec_vitesse].mean())
        dw = d_obs[g:d]
        avec_dir = avec_vitesse & ~np.isnan(dw) & (sw >= VENT_MIN_DIR_KMH)
        obs_dir = None
        if avec_dir.any():
            r = np.radians(dw[avec_dir])
            u = float((sw[avec_dir] * np.sin(r)).mean())
            v = float((sw[avec_dir] * np.cos(r)).mean())
            obs_dir = (math.degrees(math.atan2(u, v)) + 360.0) % 360.0
        fd = nombre(di[i]) if i < len(di) else math.nan
        if (obs_dir is not None and not math.isnan(fd)
                and fs >= VENT_MIN_DIR_KMH and obs_speed >= VENT_MIN_DIR_KMH):
            ra = math.radians(fd)
            rb = math.radians(obs_dir)
            errs.append(math.hypot(fs * math.sin(ra) - obs_speed * math.sin(rb),
                                   fs * math.cos(ra) - obs_speed * math.cos(rb)))
        else:
            errs.append(abs(fs - obs_speed))
    return errs


def balise_jours(racine: pathlib.Path, jour: datetime) -> tuple[dict, dict]:
    """Toutes les balise-jours d'une journée, recalculées depuis
    l'archive. Clé : `(source, station_id, model, lead_h)`.

    ⚠️ TROIS ARCHIVES D'ÉMISSION, PAS UNE. La journée J est notée avec
    ce qui a été émis le jour J (échéance 6 h par défaut), le jour J−1
    (24 h) et le jour J−2 (48 h). Une ligne qui porte son propre
    `lead_h` (classes courte et au quart d'heure) garde le sien.
    """
    debut_ms = int(jour.replace(tzinfo=timezone.utc).timestamp()) * 1000
    obs = observations_du_jour(racine, jour)
    res: dict[tuple, dict] = {}
    bilan = {"lignes_fcst": 0, "sans_obs": 0, "sous_plancher": 0,
             "cles_en_double": 0, "archives": [], "balises_obs": len(obs)}
    if not obs:
        return res, bilan
    for offset in OFFSETS:
        jour_emis = jour - timedelta(days=offset)
        for chemin in archives_du_jour(racine, jour_emis, "fcst"):
            bilan["archives"].append(f"J-{offset}:{chemin.name}")
            for ligne in lignes_ndjson(chemin):
                bilan["lignes_fcst"] += 1
                o = obs.get(f"{ligne['source']}:{ligne['station_id']}")
                if o is None:
                    bilan["sans_obs"] += 1
                    continue
                pas = int(ligne.get("step_s") or 3600)
                errs = erreurs_horaires(ligne, o, debut_ms,
                                        demi_fenetre_ms(pas))
                if len(errs) < plancher_du_pas(pas):
                    bilan["sous_plancher"] += 1
                    continue
                lead = ligne.get("lead_h")
                lead = LEAD_PAR_OFFSET[offset] if lead is None else int(lead)
                cle = (ligne["source"], str(ligne["station_id"]),
                       ligne["model"], lead)
                if cle in res:
                    # ⚠️ La chaîne écrirait DEUX lignes de même clé
                    # primaire et l'upsert garderait la dernière : on
                    # fait pareil, et on le COMPTE. Un doublon de clé
                    # entre deux flux ne se verrait nulle part ailleurs.
                    bilan["cles_en_double"] += 1
                a = np.asarray(errs, dtype=float)
                res[cle] = {
                    "med": float(np.median(a)),
                    "rms": (math.sqrt(float((a * a).mean()))
                            if len(a) >= 2 else None),
                    "n": len(a),
                }
    return res, bilan


# ══════════════════════════════════════════════════════════════════
#  LES CASES DU SCORE GLISSANT — la fenêtre, pas la journée
# ══════════════════════════════════════════════════════════════════

def echelon_de(zone: dict) -> str:
    """L'échelon auquel appartient RÉELLEMENT le `zone_id` d'une balise.
    Se déduit des colonnes, jamais de la forme de la chaîne."""
    if zone.get("basin_id"):
        return "basin_landform"
    if zone.get("massif_id"):
        return "massif_landform"
    return "landform"


def chaine_de_repli(zone: dict) -> list[tuple[str, str]]:
    """Les cinq échelons, dans l'ordre, avec leur `agg_level`.

    ⚠️ LA FORME PASSE AVANT LE MASSIF, et le dédoublonnage est le même :
    quand le bassin manque, la case fine EST `massif:forme` et ne doit
    pas être comptée deux fois.
    """
    forme = zone.get("landform")
    massif = zone.get("massif_id")
    chaine = [(zone["zone_id"], echelon_de(zone))]
    if massif:
        chaine.append((f"{massif}:{forme}", "massif_landform"))
    chaine.append((f"*:{forme}", "landform"))
    if massif:
        chaine.append((f"{massif}:*", "massif"))
    chaine.append(("*:*", "global"))
    vus, out = set(), []
    for zid, niveau in chaine:
        if zid in vus:
            continue
        vus.add(zid)
        out.append((zid, niveau))
    return out


class AccumulateurCases:
    """Les cases `rolling15`, remplies JOUR PAR JOUR.

    ⛔ POURQUOI UN ACCUMULATEUR ET PAS UNE FONCTION QUI PREND TOUT. La
    leçon du lot LM, appliquée avant d'en avoir besoin : garder les
    25 journées de balise-jours en mémoire pour les traiter à la fin
    coûterait le double de ce que coûte la nuit elle-même, sur une
    machine qui est déjà morte d'un OOM le 28/08. Chaque journée est
    versée ici puis RELÂCHÉE ; ne survivent que des flottants et des
    ensembles de clés de balise.

    ⚠️ LES QUATRE EXCLUSIONS SONT CELLES DE LA CHAÎNE, dans le même
    ordre : zone inconnue, `basin_uncertain`, `position_suspecte`,
    `doublon_de` (lot L17). Chacune écarte la BALISE-JOUR entière, pas
    seulement son rang — c'est le quorum de case qui fabriquait les
    cases n'existant que grâce à une seconde inscription.
    """

    def __init__(self, zones: dict):
        self.zones = zones
        self.acc: dict[tuple, dict] = defaultdict(
            lambda: {"v": [], "st": set()})
        self.bilan = {"zone_inconnue": 0, "bassin_incertain": 0,
                      "position_suspecte": 0, "doublon": 0, "retenus": 0}

    def verser(self, balise_jours_du_jour: dict) -> None:
        for (source, sid, model, lead), v in balise_jours_du_jour.items():
            z = self.zones.get(f"{source}:{sid}")
            if z is None:
                self.bilan["zone_inconnue"] += 1
                continue
            if z.get("basin_uncertain"):
                self.bilan["bassin_incertain"] += 1
                continue
            if z.get("position_suspecte"):
                self.bilan["position_suspecte"] += 1
                continue
            if z.get("doublon_de"):
                self.bilan["doublon"] += 1
                continue
            self.bilan["retenus"] += 1
            for zid, niveau in chaine_de_repli(z):
                b = self.acc[(zid, model, lead, niveau)]
                b["v"].append(v["med"])
                b["st"].add(f"{source}:{sid}")

    def cases(self) -> dict:
        out = {}
        for cle, b in self.acc.items():
            if len(b["st"]) < MIN_BALISES_CASE:
                continue
            out[cle] = {
                "med": float(np.median(np.asarray(b["v"], dtype=float))),
                "n_stations": len(b["st"]), "occurrences": len(b["v"])}
        return out


def cases_glissantes(par_jour: dict, zones: dict,
                     jours: list[str]) -> tuple[dict, dict]:
    """`AccumulateurCases` en une passe — la forme que le banc éprouve."""
    a = AccumulateurCases(zones)
    for j in jours:
        a.verser(par_jour.get(j, {}))
    return a.cases(), a.bilan


# ══════════════════════════════════════════════════════════════════
#  LA BASE — lue, jamais écrite
# ══════════════════════════════════════════════════════════════════

class Base:
    """Le strict minimum pour LIRE PostgREST. Écrit ici plutôt
    qu'importé de `score.py` : l'oracle ne partage aucune ligne avec la
    chaîne, pagination comprise.

    ⛔ `PAGE` NE MONTE PAS. Le serveur plafonne à 1 000 lignes par appel
    (`db-max-rows`, remesuré le 25/08 sur la production). La boucle
    s'arrête sur `len(page) < PAGE` : demander 10 000 ferait prendre la
    première page plafonnée pour la fin de la table, et tronquerait en
    silence.
    """

    PAGE = 1000
    PLAFOND_SERVEUR = 1000
    RELECTURES = 2

    def __init__(self, url: str | None = None, cle: str | None = None):
        self.url = (url or os.environ.get("SUPABASE_URL") or "").rstrip("/")
        self.cle = cle or os.environ.get("SUPABASE_SERVICE_KEY") or ""
        if not (self.url and self.cle):
            raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants")
        self.appels = 0

    def _page(self, chemin: str, deb: int, fin: int) -> list[dict]:
        assert self.PAGE <= self.PLAFOND_SERVEUR
        derniere: Exception | None = None
        for essai in range(self.RELECTURES + 1):
            try:
                r = urllib.request.Request(f"{self.url}/rest/v1/{chemin}")
                r.add_header("apikey", self.cle)
                r.add_header("Authorization", f"Bearer {self.cle}")
                r.add_header("Range-Unit", "items")
                r.add_header("Range", f"{deb}-{fin}")
                self.appels += 1
                with urllib.request.urlopen(r, timeout=120) as f:
                    return json.loads(f.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                if e.code < 500:
                    raise
                derniere = e
            except (urllib.error.URLError, TimeoutError) as e:
                derniere = e
            time.sleep(2.0 * (essai + 1))
        raise SystemExit(f"lecture impossible de {chemin} : {derniere}")

    def lire(self, table: str, requete: str, ordre: str) -> list[dict]:
        sep = "&" if requete else ""
        chemin = f"{table}?{requete}{sep}order={ordre}"
        out: list[dict] = []
        deb = 0
        while True:
            page = self._page(chemin, deb, deb + self.PAGE - 1)
            out.extend(page)
            if len(page) < self.PAGE:
                return out
            deb += self.PAGE


# ══════════════════════════════════════════════════════════════════
#  LA CONFRONTATION
# ══════════════════════════════════════════════════════════════════

def ecart(a, b) -> float | None:
    """L'écart absolu entre deux nombres, ou `None` si l'un manque."""
    if a is None or b is None:
        return None
    return abs(float(a) - float(b))


def confronter_balise_jours(oracle: dict, base: dict, seuil: float,
                            res: dict | None = None) -> dict:
    """Compare deux dictionnaires de balise-jours clés à l'identique.

    `base` porte des TUPLES `(err_vec_med, err_vec_rms, n_hours)` et non
    les lignes entières : la fenêtre en compte plus de six cent mille, et
    garder les dictionnaires JSON coûterait un demi-gigaoctet pour trois
    nombres par ligne.

    `res` permet de FUSIONNER journée après journée — c'est ce qui rend
    la lecture jour par jour possible, donc ce qui tient la mémoire.

    ⚠️ DEUX SENS, PAS UN. « la base dit un autre chiffre » et « la base
    ne dit rien du tout » sont deux pannes différentes, et la seconde
    est la plus silencieuse des deux : une nuit qui n'a rien écrit ne
    produit aucun chiffre faux, donc aucune alerte de valeur.
    """
    if res is None:
        res = {"communs": 0, "ecarts_med": [], "ecarts_rms": [],
               "oracle_seul": [], "base_seule": [],
               "med_max": 0.0, "rms_max": 0.0}
    for cle, o in oracle.items():
        b = base.get(cle)
        if b is None:
            res["oracle_seul"].append((cle, o))
            continue
        res["communs"] += 1
        e = ecart(o["med"], b[0])
        if e is not None:
            res["med_max"] = max(res["med_max"], e)
            if e > seuil:
                res["ecarts_med"].append(
                    (cle, o["med"], b[0], e, o["n"], b[2]))
        er = ecart(o["rms"], b[1])
        if er is not None:
            res["rms_max"] = max(res["rms_max"], er)
            if er > seuil:
                res["ecarts_rms"].append(
                    (cle, o["rms"], b[1], er, o["n"], b[2]))
    for cle, b in base.items():
        if cle not in oracle:
            res["base_seule"].append((cle, b))
    return res


def confronter_cases(oracle: dict, base: dict, seuil: float) -> dict:
    res = {"communs": 0, "ecarts": [], "oracle_seul": [], "base_seule": [],
           "max": 0.0}
    for cle, o in oracle.items():
        b = base.get(cle)
        if b is None:
            res["oracle_seul"].append((cle, o))
            continue
        res["communs"] += 1
        e = ecart(o["med"], b.get("typical_err_kmh"))
        if e is not None:
            res["max"] = max(res["max"], e)
            if e > seuil:
                res["ecarts"].append((cle, o, b, e))
    for cle, b in base.items():
        if cle not in oracle:
            res["base_seule"].append((cle, b))
    return res


def resume_absences(liste: list) -> list[tuple[tuple, int]]:
    """Les absences REGROUPÉES par journée, modèle et échéance.

    ⛔ NOMMER N'EST PAS SUFFISANT QUAND IL Y EN A NEUF MILLE. Le lot
    exige que tout ÉCART DE VALEUR soit nommé balise par balise, et il
    l'est. Une ABSENCE, elle, se lit autrement : « 9 441 balise-jours
    que la base n'a pas » ne devient une question qu'une fois écrit
    « 2026-08-13 · agrume · lead 6 : 9 441 » — une seule journée, un
    seul modèle, et la question qui suit est évidente. Quarante noms
    tirés d'une liste triée ne l'auraient jamais dit.
    """
    par_cas: dict[tuple, int] = defaultdict(int)
    for cle, _v in liste:
        jour, _source, _sid, model, lead = cle
        par_cas[(jour, model, lead)] += 1
    return sorted(par_cas.items(), key=lambda x: (-x[1], x[0]))


def nommer_balise(cle: tuple) -> str:
    """Une balise-jour, nommee comme un humain la cherchera en base :
    la journee d'abord, puis la cle primaire de `model_verif_daily`."""
    jour, source, sid, model, lead = cle
    return f"{jour} · {source}:{sid} · {model} · lead {lead}"


# ══════════════════════════════════════════════════════════════════
#  LE RAPPORT
# ══════════════════════════════════════════════════════════════════

def rapport(res: dict, quand: str | None = None) -> str:
    """Le rapport horodaté, en texte. Aucune couleur, aucune surprise."""
    q = quand or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    L = []
    A = L.append
    A("=" * 70)
    A(f"  ORACLE BATCH DU SCORING (lot L12) — {q}")
    A("=" * 70)
    A("")
    A(f"  seuil d'ecart nomme : {res['seuil']} km/h")
    A(f"  racine des archives : {res['racine']}")
    A(f"  fenetre demandee    : {res['jours_demandes']} jour(s)")
    A(f"  fenetre trouvee     : {len(res['jours'])} jour(s) "
      f"({res['jours'][0] if res['jours'] else '-'} -> "
      f"{res['jours'][-1] if res['jours'] else '-'})")
    if res.get("jours_manquants"):
        A(f"  /!\\ {len(res['jours_manquants'])} jour(s) demande(s) SANS "
          f"archive : {', '.join(res['jours_manquants'])}")
    A("")
    A("-" * 70)
    A("  1. BALISE-JOURS  (err_vec_med / err_vec_rms vs model_verif_daily)")
    A("-" * 70)
    bj = res["balise_jours"]
    A(f"  oracle : {res['n_oracle']} balise-jour(s) recalcule(s) depuis "
      f"l'archive")
    A(f"  base   : {res['n_base']} ligne(s) lue(s) (fcst_src=own_archive)")
    A(f"  communs : {bj['communs']}")
    A(f"  ecart max sur la mediane : {bj['med_max']:.6f} km/h")
    A(f"  ecart max sur le RMS     : {bj['rms_max']:.6f} km/h")
    A(f"  ecarts > seuil : {len(bj['ecarts_med'])} sur la mediane, "
      f"{len(bj['ecarts_rms'])} sur le RMS")
    A(f"  presents chez l'oracle et ABSENTS de la base : "
      f"{len(bj['oracle_seul'])}")
    A(f"  presents en base et ABSENTS chez l'oracle    : "
      f"{len(bj['base_seule'])}")
    for titre, liste in (("MEDIANE", bj["ecarts_med"]),
                         ("RMS", bj["ecarts_rms"])):
        if not liste:
            continue
        A("")
        A(f"  --- ecarts de {titre}, balise par balise ---")
        for cle, vo, vb, e, no, nb in sorted(liste, key=lambda x: -x[3]):
            A(f"    {e:9.4f}  {nommer_balise(cle)}  "
              f"oracle={vo!r} base={vb!r} n_oracle={no} n_base={nb}")
    for titre, liste in (("l'oracle sait calculer, la base ne dit rien",
                          bj["oracle_seul"]),
                         ("la base publie, l'oracle ne retrouve pas",
                          bj["base_seule"])):
        if not liste:
            continue
        A("")
        A(f"  --- {titre} : PAR JOURNEE, MODELE ET ECHEANCE ---")
        resume = resume_absences(liste)
        for (j, model, lead), n in resume[:res["max_nommes"]]:
            A(f"    {n:7}  {j} · {model} · lead {lead}")
        if len(resume) > res["max_nommes"]:
            A(f"    ... et {len(resume) - res['max_nommes']} autre(s) "
              f"combinaison(s)")
    if bj["oracle_seul"]:
        A("")
        A("  --- l'oracle sait calculer, la base ne dit rien ---")
        for cle, o in sorted(bj["oracle_seul"])[:res["max_nommes"]]:
            A(f"    {nommer_balise(cle)}  med={o['med']:.4f} n={o['n']}")
        if len(bj["oracle_seul"]) > res["max_nommes"]:
            A(f"    ... et {len(bj['oracle_seul']) - res['max_nommes']} "
              f"autre(s)")
    if bj["base_seule"]:
        A("")
        A("  --- la base publie, l'oracle ne retrouve pas ---")
        for cle, b in sorted(bj["base_seule"])[:res["max_nommes"]]:
            A(f"    {nommer_balise(cle)}  base_med={b[0]!r} "
              f"n_base={b[2]}")
        if len(bj["base_seule"]) > res["max_nommes"]:
            A(f"    ... et {len(bj['base_seule']) - res['max_nommes']} "
              f"autre(s)")
    A("")
    A("-" * 70)
    A("  2. CASES rolling15  (typical_err_kmh vs model_score_zone)")
    A("-" * 70)
    cs = res.get("cases")
    if cs is None:
        A(f"  NON VERIFIABLE : {res.get('cases_raison')}")
    else:
        A(f"  as_of   : {res['as_of']}   journee notee : {res['jour_note']}")
        A(f"  fenetre : {res['fenetre_debut']} -> {res['jour_note']} "
          f"({FENETRE_GLISSANTE_J} jours)")
        A(f"  zones tirees au sort (graine {res['graine']}) : "
          f"{', '.join(res['zones_tirees'])}")
        A(f"  balise-jours retenus dans la fenetre : "
          f"{res['bilan_cases']['retenus']} "
          f"(ecartes : zone inconnue {res['bilan_cases']['zone_inconnue']}, "
          f"bassin incertain {res['bilan_cases']['bassin_incertain']}, "
          f"position suspecte {res['bilan_cases']['position_suspecte']}, "
          f"doublon {res['bilan_cases']['doublon']})")
        A(f"  cases comparees : {cs['communs']}")
        A(f"  ecart max : {cs['max']:.6f} km/h")
        A(f"  ecarts > seuil : {len(cs['ecarts'])}")
        A(f"  cases de l'oracle absentes de la base : "
          f"{len(cs['oracle_seul'])}")
        A(f"  cases de la base absentes de l'oracle : "
          f"{len(cs['base_seule'])}")
        for cle, o, b, e in sorted(cs["ecarts"], key=lambda x: -x[3]):
            zid, model, lead, niveau = cle
            A(f"    {e:9.4f}  {zid} · {model} · lead {lead} · {niveau}  "
              f"oracle={o['med']:.4f} base={b.get('typical_err_kmh')!r}  "
              f"n_st oracle={o['n_stations']} base={b.get('n_stations')}  "
              f"occ oracle={o['occurrences']} base={b.get('occurrences')}")
        for titre, liste in (("oracle seul", cs["oracle_seul"]),
                             ("base seule", cs["base_seule"])):
            if not liste:
                continue
            A(f"    --- cases {titre} ---")
            for cle, v in sorted(liste)[:res["max_nommes"]]:
                A(f"      {cle}")
            if len(liste) > res["max_nommes"]:
                A(f"      ... et {len(liste) - res['max_nommes']} autre(s)")
    A("")
    A("-" * 70)
    A("  3. CE QUE CE RAPPORT NE PROUVE PAS")
    A("-" * 70)
    A("  · les constantes de methode sont TRANSCRITES a la main dans")
    A("    l'oracle (demi-fenetre, seuil de girouette, plancher, quorum,")
    A("    chaine de repli). Un changement de definition fait CRIER cet")
    A("    oracle ; une definition fausse des deux cotes reste invisible.")
    A("  · seules l'erreur vectorielle et sa mediane de case sont")
    A("    verifiees. Skill, MSE, biais, rangs, FDR : hors perimetre.")
    A("  · une archive fausse rend une chaine fausse ET un oracle faux,")
    A("    a l'identique.")
    A("  · ⛔ ET SURTOUT : cet oracle fait tourner LE CODE D'AUJOURD'HUI")
    A("    sur LES ARCHIVES D'HIER. « l'oracle sait calculer, la base ne")
    A("    dit rien » a donc TROIS lectures, et une seule est une faute :")
    A("      1. une CLASSE NEE APRES ce jour-la (son archive existe, la")
    A("         nuit qui l'aurait notee est anterieure au job) ;")
    A("      2. un PERIMETRE QUI A CHANGE depuis (un reseau entre dans")
    A("         la liste des observations, et l'oracle apparie ce que la")
    A("         nuit de l'epoque ne voyait pas) ;")
    A("      3. ⛔ une NUIT QUI A ECHOUE et une archive reparee APRES")
    A("         coup, jamais rejouee. Celle-la seule est un trou.")
    A("    Les trois se departagent en regardant la date de naissance du")
    A("    job et le journal de la nuit — le resume par journee/modele")
    A("    ci-dessus est fait pour ca, et c'est pour ca qu'il existe.")
    A("")
    A(f"  verdict : {res['verdict']}")
    A("=" * 70)
    return "\n".join(L)


def rss_mo() -> float | None:
    """La memoire residente de CE processus, en Mo. `None` hors Linux."""
    try:
        with open("/proc/self/status", encoding="utf-8") as f:
            for ligne in f:
                if ligne.startswith("VmRSS:"):
                    return int(ligne.split()[1]) / 1024.0
    except OSError:
        return None
    return None


def main() -> int:
    _verifier_independance()
    ap = argparse.ArgumentParser(
        description="Oracle batch mensuel du scoring (lot L12).")
    # ⛔ `--out` VEUT DIRE LA MEME CHOSE QUE PARTOUT AILLEURS DANS CE
    # DEPOT : la racine de l'etat et des archives, celle que `run.sh`
    # passe a TOUS ses jobs. Lui donner ici un sens different (un chemin
    # de rapport, par exemple) obligerait l'enveloppe a connaitre une
    # exception, c'est-a-dire a porter un second chemin — l'arbitrage
    # deja pris pour `controle_tau.py` au lot L8. Le rapport, lui, a son
    # propre drapeau.
    ap.add_argument("--out", default=RACINE_DEFAUT,
                    help="racine de l'etat et des archives, et ou le "
                         "rapport est depose")
    ap.add_argument("--jours", type=int, default=30,
                    help="profondeur demandee. Le rapport publie la "
                         "fenetre REELLEMENT trouvee, jamais celle demandee")
    ap.add_argument("--day", default=None,
                    help="derniere journee notee (AAAA-MM-JJ). "
                         "Defaut : hier UTC")
    ap.add_argument("--as-of", default=None,
                    help="as_of de model_score_zone a confronter. "
                         "Defaut : le plus recent en base")
    ap.add_argument("--zones", type=int, default=3,
                    help="nombre de zones tirees au sort (0 = toutes)")
    ap.add_argument("--graine", type=int, default=12,
                    help="graine du tirage des zones. Elle est IMPRIMEE "
                         "dans le rapport : un tirage qu'on ne peut pas "
                         "rejouer n'est pas une mesure")
    ap.add_argument("--seuil", type=float, default=SEUIL_ECART_KMH,
                    help="au-dela de quoi un ecart est nomme (km/h)")
    ap.add_argument("--max-nommes", type=int, default=40,
                    help="combien d'ABSENCES nommer au maximum. Les "
                         "ecarts de VALEUR, eux, sont tous nommes")
    ap.add_argument("--rapport", default=None,
                    help="chemin du rapport. Defaut : "
                         "<racine>/oracle-scoring-<jour>.txt ; `-` pour "
                         "ne rien ecrire et rester sur stdout")
    ap.add_argument("--sans-base", action="store_true",
                    help="recalcule seulement, ne lit ni ne confronte la "
                         "base (mise au point, hors ligne)")
    ap.add_argument("--json", action="store_true",
                    help="ajoute le resume en JSON sur stdout")
    args = ap.parse_args()

    racine = pathlib.Path(args.out)
    jour_note = (datetime.strptime(args.day, "%Y-%m-%d")
                 if args.day else datetime.now(timezone.utc) - timedelta(days=1))
    jour_note = jour_note.replace(hour=0, minute=0, second=0, microsecond=0,
                                  tzinfo=timezone.utc)

    demandes = [(jour_note - timedelta(days=i)) for i in range(args.jours)][::-1]
    jours: list[datetime] = []
    manquants: list[str] = []
    for j in demandes:
        if (archives_du_jour(racine, j, "obs")
                and archives_du_jour(racine, j, "fcst")):
            jours.append(j)
        else:
            manquants.append(j.strftime("%Y-%m-%d"))
    if not jours:
        print("⛔ aucune journee d'archive dans la fenetre demandee",
              file=sys.stderr)
        return 2

    print(f"▶ oracle L12 : {len(jours)} journee(s) d'archive "
          f"({jours[0]:%Y-%m-%d} -> {jours[-1]:%Y-%m-%d}), "
          f"{len(manquants)} demandee(s) sans archive", flush=True)

    # ── ce que la fenetre glissante exige, decide AVANT la boucle ───
    voulus = []
    absents = []
    if len(jours) >= 1:
        debut_fenetre = jour_note - timedelta(days=FENETRE_GLISSANTE_J - 1)
        voulus = [(debut_fenetre + timedelta(days=i)).strftime("%Y-%m-%d")
                  for i in range(FENETRE_GLISSANTE_J)]
        presents = {j.strftime("%Y-%m-%d") for j in jours}
        demandes_s = {j.strftime("%Y-%m-%d") for j in demandes}
        absents = [d for d in voulus if d not in presents]
        # ⛔ DEUX RAISONS DIFFÉRENTES DE NE PAS POUVOIR CONCLURE, ET LES
        # CONFONDRE SERAIT MENTIR SUR SA PROPRE CÉCITÉ. « l'archive ne
        # remonte pas jusque-là » est un fait du disque ; « --jours est
        # trop court » est un choix de l'appelant. Le premier se répare
        # en attendant, le second en retapant la commande — et un
        # contrôle qui nomme mal ce qui l'empêche de conclure envoie
        # chercher au mauvais endroit (leçon du §2 du lot LD : un
        # vérificateur qui décrit mal son angle mort ne peut pas le
        # voir).
        hors_fenetre = [d for d in absents if d not in demandes_s]
        sans_archive = [d for d in absents if d in demandes_s]

    res = {
        "seuil": args.seuil, "racine": str(racine),
        "jours_demandes": args.jours,
        "jours": [j.strftime("%Y-%m-%d") for j in jours],
        "jours_manquants": manquants,
        "n_oracle": 0, "n_base": 0, "cles_en_double": 0,
        "max_nommes": args.max_nommes,
        "jour_note": jour_note.strftime("%Y-%m-%d"),
        "fenetre_debut": voulus[0] if voulus else None,
        "cases": None, "cases_raison": "--sans-base",
        "graine": args.graine, "zones_tirees": [],
        "bilan_cases": None, "rss_mo": None,
        "balise_jours": None,
    }

    sb = None
    accumulateur = None
    as_of = None
    tirees_s: set = set()
    base_cases: dict = {}
    if not args.sans_base:
        sb = Base()
        as_of = args.as_of
        if as_of is None:
            derniere = sb._page(
                "model_score_zone?select=as_of&order=as_of.desc", 0, 0)
            as_of = derniere[0]["as_of"] if derniere else None
        res["as_of"] = as_of
        if as_of is None:
            res["cases_raison"] = "aucun as_of en base"
        elif absents:
            # ⚠️ UNE CASE INCOMPLETE N'EST PAS UNE CASE FAUSSE, et
            # publier l'ecart comme s'il en etait un accuserait la
            # chaine d'une faute qui est celle de l'archive. On se tait,
            # et on dit POURQUOI — meme geste que le `non_verifiable`
            # du lot L8.
            motifs = []
            if hors_fenetre:
                motifs.append(
                    f"{len(hors_fenetre)} jour(s) HORS DE LA PROFONDEUR "
                    f"DEMANDEE (--jours {args.jours} : "
                    f"{', '.join(hors_fenetre)})")
            if sans_archive:
                motifs.append(
                    f"{len(sans_archive)} jour(s) SANS ARCHIVE sur le "
                    f"disque ({', '.join(sans_archive)})")
            res["cases_raison"] = (
                f"la fenetre glissante {voulus[0]}->{voulus[-1]} n'est "
                f"pas couverte : " + " ; ".join(motifs))
        else:
            zrows = sb.lire("station_zone", "select=*", "source,station_id")
            zones = {f"{z['source']}:{z['station_id']}": z for z in zrows}
            print(f"  station_zone : {len(zones)} balise(s)", flush=True)
            srows = sb.lire(
                "model_score_zone",
                f"select=zone_id,model,lead_h,agg_level,typical_err_kmh,"
                f"n_stations,occurrences&as_of=eq.{as_of}"
                f"&window_kind=eq.rolling15&regime=eq.all",
                "zone_id,model,lead_h,agg_level")
            toutes = sorted({r["zone_id"] for r in srows})
            if args.zones and args.zones < len(toutes):
                tirees = sorted(random.Random(args.graine).sample(
                    toutes, args.zones))
            else:
                tirees = toutes
            res["zones_tirees"] = tirees
            tirees_s = set(tirees)
            base_cases = {(r["zone_id"], r["model"], int(r["lead_h"]),
                           r["agg_level"]): r
                          for r in srows if r["zone_id"] in tirees_s}
            print(f"  model_score_zone : {len(srows)} ligne(s) rolling15 "
                  f"as_of={as_of}, {len(base_cases)} sur les zones "
                  f"tirees", flush=True)
            accumulateur = AccumulateurCases(zones)

    colonnes = ("day,source,station_id,model,lead_h,fcst_src,"
                "err_vec_med,err_vec_rms,n_hours")
    cumul = None
    t0 = time.monotonic()
    for j in jours:
        d = j.strftime("%Y-%m-%d")
        bj, bilan = balise_jours(racine, j)
        res["n_oracle"] += len(bj)
        res["cles_en_double"] += bilan["cles_en_double"]
        if sb is not None:
            brut = sb.lire("model_verif_daily",
                           f"select={colonnes}&day=eq.{d}"
                           f"&fcst_src=eq.own_archive",
                           "source,station_id,model,lead_h,fcst_src")
            base_j = {(d, r["source"], str(r["station_id"]), r["model"],
                       int(r["lead_h"])):
                      (r["err_vec_med"], r["err_vec_rms"], r["n_hours"])
                      for r in brut}
            res["n_base"] += len(base_j)
            cumul = confronter_balise_jours(
                {(d,) + cle: v for cle, v in bj.items()},
                base_j, args.seuil, cumul)
            brut = base_j = None
        if accumulateur is not None and d in voulus:
            accumulateur.verser(bj)
        # ⛔ LA JOURNEE EST RELACHEE ICI, et c'est ce qui tient la
        # memoire : ne survivent que le cumul des ecarts et les
        # flottants de l'accumulateur de cases.
        bj = None
        print(f"  {d} : {res['n_oracle']} balise-jour(s) cumules "
              f"({bilan['lignes_fcst']} lignes de prevision, "
              f"{bilan['sous_plancher']} sous plancher, "
              f"{bilan['sans_obs']} sans releve) "
              f"[{time.monotonic() - t0:.0f} s, RSS {rss_mo():.0f} Mo]",
              flush=True)

    res["rss_mo"] = rss_mo()
    if cumul is None:
        cumul = {"communs": 0, "ecarts_med": [], "ecarts_rms": [],
                 "oracle_seul": [], "base_seule": [],
                 "med_max": 0.0, "rms_max": 0.0}
    res["balise_jours"] = cumul

    if args.sans_base:
        res["verdict"] = "NON CONFRONTE (--sans-base)"
        print(rapport(res))
        return 0

    if accumulateur is not None:
        cases_o = {k: v for k, v in accumulateur.cases().items()
                   if k[0] in tirees_s}
        res["bilan_cases"] = accumulateur.bilan
        res["cases"] = confronter_cases(cases_o, base_cases, args.seuil)

    n_ecarts = len(cumul["ecarts_med"]) + len(cumul["ecarts_rms"])
    if res["cases"]:
        n_ecarts += len(res["cases"]["ecarts"])
    res["n_ecarts"] = n_ecarts
    res["verdict"] = ("VERT — aucun ecart au-dela du seuil"
                      if n_ecarts == 0
                      else f"ROUGE — {n_ecarts} ecart(s) nomme(s)")

    texte = rapport(res)
    print(texte)
    if args.rapport != "-":
        chemin = pathlib.Path(
            args.rapport or (racine / f"oracle-scoring-"
                                      f"{jour_note:%Y-%m-%d}.txt"))
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(texte + "\n", encoding="utf-8")
        print(f"\n  rapport depose : {chemin}")
    if args.json:
        print(json.dumps({k: v for k, v in res.items()
                          if k not in ("balise_jours", "cases")},
                         ensure_ascii=False, default=str))
    return 0 if n_ecarts == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
