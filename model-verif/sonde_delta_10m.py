#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/sonde_delta_10m.py — PHASE B : Δ(10 m) vrai contre
#                     Δ(20 m) étendu, MESURE et rien d'autre (26/08/2026)
#
#  ⛔⛔ CE FICHIER NE CHANGE RIEN AU PRODUIT. Il ne touche ni
#  `composite.py`, ni `agrume_fcst.py`, ni une archive. Il LIT R2 et les
#  observations, et il écrit un tableau de chiffres. Le câblage éventuel
#  de Δ(10 m) est un autre lot, dans une autre session, APRÈS le verdict.
#
#  ═══ LA QUESTION, EXACTEMENT ═══
#  `composite.etendre_delta` étend Δ(20 m) CONSTANT sous 20 m, avec
#  cette raison écrite : côté AROME `u`/`v` n'existent qu'à partir de
#  20 m dans `HP1` ; le 10 m viendrait des champs dédiés `10u`/`10v`,
#  une AUTRE famille de champ — « rien ne dit que ce soit le même
#  diagnostic ». PI, lui, sert bien un `u`/`v` à height = 10 m
#  (`niveau_10m_servi: true`, vérifié dans le manifeste).
#
#  Deux questions, dans cet ordre :
#    1. PI₁₀ et AROME(10u/10v) sont-ils COMMENSURABLES ? (le cisaillement
#       10↔20 m de chacun des deux modèles est la signature : deux
#       familles de champ différentes se verraient comme un décalage
#       systématique que Δ(20 m) n'a pas)
#    2. Δ(10 m) vrai rapproche-t-il des OBSERVATIONS plus que Δ(20 m)
#       étendu ? C'est celle qui décide.
#
#  ═══ LES CINQ SÉRIES APPARIÉES ═══
#      T0   AROME₁₀ brut (maille 0,01°, la base du score)
#      T1   T0 + w·Δ(20 m)  — CE QU'ON SERT AUJOURD'HUI
#      T2   T0 + w·Δ(10 m)  — le candidat
#      T1p  T0 + w·Δ(20 m) D'UNE AUTRE BALISE   ⟵ témoin placebo
#      T2p  T0 + w·Δ(10 m) D'UNE AUTRE BALISE   ⟵ témoin placebo
#
#  ⛔ LE TÉMOIN PLACEBO EST OBLIGATOIRE (règle du 25/08, BUGS.md), ET IL
#  Y EN A DEUX. Le prompt de reprise n'en réclamait qu'un, sur T2. Mais
#  T1 est lui aussi un candidat : si l'on ne mesure le placebo que d'un
#  côté, on compare un gain net à un gain brut. Sans témoin, un simple
#  rétrécissement de variance se lit comme un gain d'information — c'est
#  exactement le piège qui avait fait annoncer 29,4 % de gain dont
#  13,0 % étaient du placebo.
#
#  ⛔ LES RÈGLES DE Δ SONT CELLES DE `agrume_fcst.delta_20m`, PAS DES
#  VARIANTES : même run des deux côtés, Δ en 0,025° contre 0,025°,
#  heures rondes cherchées PAR VALEUR (donc aucune interpolation),
#  balises appariées PAR IDENTIFIANT, NaN d'un côté = pas de Δ. La
#  rampe `poids_pi` s'IMPORTE du composite, elle ne se recopie pas.
#
#  ⚠️ CE QUE CETTE SONDE ÉLARGIT PAR RAPPORT AU SCORE, ET POURQUOI. Le
#  score ne retient que les runs 00 Z et 03 Z (`RUNS_ADMIS`, décision 1
#  du lot I) parce qu'un run plus frais donnerait à AGRUME un avantage
#  d'horaire sur les autres modèles. Ici il n'y a PAS d'autre modèle :
#  les cinq séries partagent le même run, la même balise, la même heure.
#  Prendre les 8 runs/jour multiplie par 4 le nombre de couples sans
#  rien déséquilibrer. Le tableau restreint à {00, 03} Z est sorti aussi,
#  parce que c'est LUI qui dit ce que le score verrait changer.
#
#      python3 sonde_delta_10m.py --extraire --sortie /tmp/deltab.npz
#      python3 sonde_delta_10m.py --agreger  --sortie /tmp/deltab.npz
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import gzip
import io
import json
import math
import os
import pathlib
import sys
import zlib
from datetime import datetime, timedelta, timezone

_ICI = pathlib.Path(__file__).resolve().parent
for _p in (_ICI.parent / "agrume", _ICI.parent / "verif", _ICI.parent / "tools"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

import numpy as np                                          # noqa: E402

import agrume_fcst as A                                     # noqa: E402
import score as SC                                          # noqa: E402
import scoring as S                                         # noqa: E402
from composite import poids_pi                              # noqa: E402
from profil import decorer_vent                             # noqa: E402

# ── Ce qui vient d'ailleurs et ne se recopie pas ──────────────────────
# ⛔ Chacune de ces constantes a un propriétaire, et ce fichier n'en est
# jamais le propriétaire. Une copie ici serait un endroit où la
# correction suivante n'irait pas — le défaut que `poids_pi` a déjà
# coûté une fois (rampe finissant à 7 h pour un PI qui s'arrête à 6 h).
MAILLE_BASE = A.MAILLE_DEFAUT          # "001" — la base du score
MAILLE_DELTA = A.MAILLE_DELTA          # "0025" — Δ se mesure là
NIV_HAUT = A.NIVEAU_DELTA_MESURE       # 20 m — Δ mesuré aujourd'hui
NIV_BAS = A.NIVEAU_DELTA_APPLIQUE      # 10 m — Δ appliqué aujourd'hui
SOURCE = A.SOURCE_NOTEE                # "pioupiou"
HEURES_PI = tuple(h for h in range(0, 7) if poids_pi(h * 60) > 0.0)

#: Les deux graines du placebo. ⚠️ DEUX, pas une : une permutation
#: unique peut être malchanceuse (un appariement fortuit de balises
#: voisines rendrait le placebo trop bon et le gain trop petit). Deux
#: graines indépendantes disent si le témoin est stable ; si elles
#: divergent, c'est le témoin qu'il faut lire, pas le verdict.
GRAINES_PLACEBO = (1, 2)


class Abort(Exception):
    pass


# ══════════════════════════════════════════════════════════════════
#  LE PLACEBO — une permutation SANS POINT FIXE, déterministe
# ══════════════════════════════════════════════════════════════════

def derangement(n: int, graine: int) -> np.ndarray:
    """Une permutation de `n` éléments sans aucun point fixe.

    ⛔ SANS POINT FIXE, ET C'EST TOUT L'INTÉRÊT. Une permutation
    ordinaire laisse en moyenne UN élément à sa place, quelle que soit
    la taille de `n` (l'espérance du nombre de points fixes vaut 1). Sur
    285 balises c'est négligeable en moyenne — mais c'est une balise qui
    reçoit son PROPRE Δ sous l'étiquette « placebo », et le témoin est
    précisément ce qui doit être irréprochable.

    ⚠️ La graine dépend du RUN chez l'appelant : une permutation figée
    pour toute la campagne ferait porter le verdict par un seul tirage.
    """
    if n < 2:
        return np.zeros(0, dtype=np.int64)
    rng = np.random.default_rng(graine)
    p = rng.permutation(n)
    # ⚠️ On RE-TESTE après chaque échange plutôt que de balayer une liste
    # de points fixes figée : sur `n = 2` avec `p = [0, 1]`, un balayage
    # figé échange deux fois et rend exactement ce qu'il devait corriger.
    for i in range(n):
        if p[i] != i:
            continue
        j = (i + 1) % n
        p[i], p[j] = p[j], p[i]
    if np.any(p == np.arange(n)):
        raise Abort(f"dérangement raté (n={n}, graine={graine}) — "
                    f"un témoin qui se donne son propre Δ n'est pas un témoin")
    return p


# ══════════════════════════════════════════════════════════════════
#  LES OBSERVATIONS — celles de `score.py`, lues comme `score.py`
# ══════════════════════════════════════════════════════════════════

def charger_obs(racine: pathlib.Path, jours):
    """`{station_id: [ObsSample…] trié}` sur plusieurs journées.

    ⛔ ON PASSE PAR `score.read_ndjson` / `score.to_obs_samples`, PAS PAR
    UNE RELECTURE MAISON. Le format d'`obs/` a déjà changé une fois, et
    une seconde lecture du même fichier est un endroit où la prochaine
    correction n'ira pas. ⚠️ `obs/` est Pioupiou SEUL (décision 1 du
    cadrage S0.2) — c'est exactement la population que `SOURCE_NOTEE`
    retient du côté du produit A.
    """
    par_station: dict[str, list] = {}
    for j in jours:
        for row in SC.read_ndjson(racine, SC.obs_key(j)):
            sid = str(row.get("station_id"))
            par_station.setdefault(sid, []).extend(SC.to_obs_samples(row))
    # ⓘ On rend `(temps, échantillons)` et pas seulement la liste : le
    # tableau des instants est reconstruit une fois par station au lieu
    # d'une fois par appariement (≈ 95 000 appels sur la campagne).
    out = {}
    for sid, ech in par_station.items():
        ech.sort(key=lambda o: o.t)
        out[sid] = (np.fromiter((o.t for o in ech), dtype=np.int64,
                                count=len(ech)), ech)
    return out


def obs_a(paire, t_ms: int):
    """La moyenne VECTORIELLE des relevés dans ±20 min, ou `None`.

    C'est le geste de `scoring.pair_series` isolé pour un seul instant :
    même demi-fenêtre, même `mean_wind`, même refus de combler une heure
    sans relevé. On ne le réécrit pas, on l'appelle.
    """
    if paire is None:
        return None
    temps, samples = paire
    if not len(temps):
        return None
    lo = t_ms - S.OBS_HALF_WINDOW_MS
    hi = t_ms + S.OBS_HALF_WINDOW_MS
    i = int(np.searchsorted(temps, lo, side="left"))
    win = []
    while i < len(samples) and samples[i].t <= hi:
        win.append(samples[i])
        i += 1
    if not win:
        return None
    speed, direction, n = S.mean_wind(win)
    if speed is None:
        return None
    return speed, direction, n


# ══════════════════════════════════════════════════════════════════
#  UN RUN → LES COUPLES
# ══════════════════════════════════════════════════════════════════

#: Les champs stockés par couple. ⛔ ON STOCKE LES u/v BRUTS, PAS LES
#: CINQ SÉRIES DÉJÀ COMPOSÉES. L'extraction lit R2 (≈ 2 Mo par run) et
#: coûte des minutes ; l'agrégation, elle, doit pouvoir être rejouée
#: autant de fois qu'il le faut sans re-télécharger — et surtout, une
#: définition de série gardée DANS l'agrégation est une définition qu'on
#: peut contester après coup sans refaire la campagne.
CHAMPS = (
    "jour", "run_h", "h", "w", "i_balise",
    "u_ar10", "v_ar10",            # base du score, maille 0,01°
    "u_ar10q", "v_ar10q",          # AROME 10 m en 0,025° (pour Δ10)
    "u_ar20q", "v_ar20q",          # AROME 20 m en 0,025° (pour Δ20)
    "u_pi10", "v_pi10",            # PI 10 m
    "u_pi20", "v_pi20",            # PI 20 m
    "obs_speed", "obs_dir", "n_obs",
)
#: Les Δ des DONNEURS du placebo, une paire de graines. Séparés de
#: `CHAMPS` parce qu'ils ne décrivent pas la balise de la ligne.
CHAMPS_PLACEBO = tuple(
    f"{q}_don{g}" for g in GRAINES_PLACEBO
    for q in ("d10u", "d10v", "d20u", "d20v"))


def _finite(*xs) -> bool:
    return all(np.isfinite(x) for x in xs)


def graine_run(run: str, g: int) -> int:
    """Une graine STABLE d'un run à l'autre et d'un processus à l'autre.

    ⛔ Pas `hash()` : le hachage des chaînes de Python est randomisé par
    processus. Une campagne dont le témoin change à chaque exécution
    n'est pas une campagne, c'est un tirage.
    """
    return zlib.crc32(f"{run}#{g}".encode("utf-8"))


def couples_du_run(run: str, obs_par_station, crier=print):
    """Toutes les lignes de couples d'UN run, ou `[]`.

    ── LES RÈGLES, COPIÉES DE `agrume_fcst.delta_20m` PAR IMPORT ─────────
    1. Même run des deux côtés (le PI du run AROME, jamais le PI le plus
       frais) — ici c'est encore plus contraignant qu'au score : les cinq
       séries doivent différer par Δ et par RIEN d'autre.
    2. Δ en 0,025° contre 0,025°, appliqué à la base 0,01°.
    3. Heures rondes cherchées PAR VALEUR dans `echeances_min`, donc
       aucune interpolation — `composite.arome_interpole` n'est pas
       appelé et ne peut rien fabriquer.
    4. Balises appariées par IDENTIFIANT, jamais par rang.
    5. Un NaN d'un côté quelconque ⇒ pas de couple. ⚠️ Ici on est plus
       strict qu'au score : le score replie l'heure sur AROME seul, ce
       qui est le bon geste pour SERVIR. Pour MESURER, une heure où Δ10
       existe et Δ20 pas (ou l'inverse) casserait l'appariement des cinq
       séries — c'est une comparaison entre populations déguisée.
    """
    lu_ar = A.lire_run(run, crier=lambda *_: None)
    if lu_ar is None:
        crier(f"  {run} : produit A absent")
        return []
    col, man = lu_ar
    lu_pi = A.lire_run_pi(run, crier=lambda *_: None)
    if lu_pi is None:
        crier(f"  {run} : colonnes PI absentes")
        return []
    pi_donnees, pi_man = lu_pi

    # ── Les index, lus dans le MANIFESTE côté PI ──────────────────────
    # (même raison qu'à `delta_20m` : le manifeste décrit l'archive qu'on
    #  a en main, les constantes celle qu'on écrirait aujourd'hui)
    pi_par = {p["nom"]: k for k, p in enumerate(pi_man["parametres"])}
    pi_niv = list(pi_man["niveaux_m_sol"])
    pi_min = list(pi_man["echeances_min"])
    try:
        j_pi_haut, j_pi_bas = pi_niv.index(NIV_HAUT), pi_niv.index(NIV_BAS)
        iu_pi, iv_pi = pi_par["u"], pi_par["v"]
    except (KeyError, ValueError) as exc:
        raise Abort(f"{run} : le manifeste PI ne décrit pas {NIV_HAUT} m ou "
                    f"{NIV_BAS} m ou u/v ({exc})") from exc
    # ⛔⛔ LA FORME DU TABLEAU PI EST VÉRIFIÉE CONTRE SON MANIFESTE.
    # L'axe PI est (paramètre, niveau, échéance, balise) ; celui du
    # produit A est (balise, paramètre, niveau, échéance). Les deux
    # archives viennent de deux chantiers différents et rien ne les a
    # jamais obligées à coïncider (`lire_run_pi` le dit). Une
    # transposition rendrait des valeurs finies, plausibles, prises sur
    # la mauvaise balise — et elle ne lève une IndexError que par chance,
    # quand les tailles ne coïncident pas. Ici on ne compte pas sur la
    # chance : on compare la forme aux quatre listes du manifeste.
    attendue = (len(pi_man["parametres"]), len(pi_niv), len(pi_min),
                len(pi_man.get("balises", [])))
    if tuple(pi_donnees.shape) != attendue:
        raise Abort(
            f"{run} : les colonnes PI ont la forme {pi_donnees.shape} là où "
            f"le manifeste décrit {attendue} (paramètre, niveau, échéance, "
            f"balise) — refus de lire, chaque Δ partirait sur la mauvaise "
            f"balise en rendant des valeurs crédibles")
    if not pi_man.get("niveau_10m_servi", False):
        # ⛔ Ce n'est pas un détail de journal. Toute la phase B repose
        # sur l'existence d'un VRAI 10 m côté PI ; un run où le portail
        # ne l'a pas servi rendrait un Δ(10 m) fabriqué, pas mesuré.
        crier(f"  {run} : PI n'a pas servi le 10 m — run écarté")
        return []

    # ── Les index et LE TABLEAU côté AROME, pris ENSEMBLE ─────────────
    # ⛔ `_bloc_maille` rend les trois d'un coup : prendre l'index d'une
    # maille et les valeurs de l'autre ne lèverait RIEN aujourd'hui
    # (i_niveau_001[20] == i_niveau_0025[20] == 1) et décalerait tout le
    # jour où l'une des listes gagne un niveau. Piège nº 3 du 26/08.
    bloc_q, i_niv_q, i_par_q = A._bloc_maille(col, MAILLE_DELTA)
    bloc_b, i_niv_b, i_par_b = A._bloc_maille(col, MAILLE_BASE)
    try:
        jq_haut, jq_bas = i_niv_q[NIV_HAUT], i_niv_q[NIV_BAS]
        jb_bas = i_niv_b[NIV_BAS]
        iu_q, iv_q = i_par_q["u"], i_par_q["v"]
        iu_b, iv_b = i_par_b["u"], i_par_b["v"]
    except KeyError as exc:
        raise Abort(f"{run} : le produit A n'a pas {NIV_HAUT} m / {NIV_BAS} m "
                    f"dans les deux mailles ({exc})") from exc

    ix_pi = {str(b["id"]): k for k, b in enumerate(pi_man.get("balises", []))
             if b.get("servie", True)}
    #: Le domaine PI de chaque balise, lu dans le manifeste — il sert à
    #: sortir le verdict PAR DOMAINE, parce qu'un gain qui n'existerait
    #: que dans les Pyrénées n'est pas le même résultat qu'un gain
    #: partout.
    dom_de = {str(b["id"]): str(b.get("domaine_pi", "?"))
              for b in pi_man.get("balises", [])}
    run_dt = datetime.strptime(man["run"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc)

    # ── Les balises appariables, dans un ORDRE STABLE ─────────────────
    # Le placebo permute CETTE liste. Elle doit donc être la même pour
    # les cinq séries, et ne contenir que des balises dont les quatre
    # champs existent — sinon le donneur d'une ligne pourrait être une
    # balise absente du tableau, et le témoin serait plus creux que le
    # candidat.
    appariables = [(k, str(b["id"])) for k, b in enumerate(col.balises)
                   if b.get("source") == SOURCE and str(b["id"]) in ix_pi]
    if len(appariables) < 2:
        crier(f"  {run} : {len(appariables)} balise(s) appariable(s) — écarté")
        return []
    # ⛔ `hash()` EST INTERDIT ICI. Le hachage des chaînes de Python est
    # randomisé à chaque processus (PYTHONHASHSEED) : la campagne ne
    # serait pas rejouable, et deux exécutions rendraient deux témoins
    # différents sans qu'une ligne ne le dise. `crc32` est stable.
    perms = {g: derangement(len(appariables), graine_run(run, g))
             for g in GRAINES_PLACEBO}

    # ── Les quatre vents de chaque balise appariable, par heure ───────
    # ⓘ On les calcule TOUS d'abord, puis on apparie : le placebo a
    # besoin du Δ du donneur, donc de la table complète de l'heure.
    jour_i = int(f"{run_dt:%Y%m%d}")
    lignes_run = []
    for h in HEURES_PI:
        w = poids_pi(h * 60)
        i_step = col.i_step.get(h)
        if i_step is None:
            continue                      # AROME n'a pas cette échéance
        if h * 60 not in pi_min:
            continue                      # PI n'a pas cette heure ronde
        i_min = pi_min.index(h * 60)      # PAR VALEUR, jamais par position

        # Table de l'heure : un enregistrement par balise appariable,
        # `None` si un seul des huit champs manque.
        table = []
        for (k, sid) in appariables:
            u_b = float(bloc_b[k, iu_b, jb_bas, i_step])
            v_b = float(bloc_b[k, iv_b, jb_bas, i_step])
            u_q10 = float(bloc_q[k, iu_q, jq_bas, i_step])
            v_q10 = float(bloc_q[k, iv_q, jq_bas, i_step])
            u_q20 = float(bloc_q[k, iu_q, jq_haut, i_step])
            v_q20 = float(bloc_q[k, iv_q, jq_haut, i_step])
            kpi = ix_pi[sid]
            # ⚠️⚠️ L'AXE PI EST (paramètre, niveau, échéance, balise) ;
            # celui du produit A est (balise, paramètre, niveau,
            # échéance). Les confondre ne lèverait pas — numpy rendrait
            # des valeurs finies, plausibles, et prises sur la mauvaise
            # balise (avertissement de `lire_run_pi`, respecté ici).
            u_p10 = float(pi_donnees[iu_pi, j_pi_bas, i_min, kpi])
            v_p10 = float(pi_donnees[iv_pi, j_pi_bas, i_min, kpi])
            u_p20 = float(pi_donnees[iu_pi, j_pi_haut, i_min, kpi])
            v_p20 = float(pi_donnees[iv_pi, j_pi_haut, i_min, kpi])
            if not _finite(u_b, v_b, u_q10, v_q10, u_q20, v_q20,
                           u_p10, v_p10, u_p20, v_p20):
                table.append(None)
                continue
            table.append((u_b, v_b, u_q10, v_q10, u_q20, v_q20,
                          u_p10, v_p10, u_p20, v_p20))

        t_ms = int((run_dt + timedelta(hours=h)).timestamp()) * 1000
        for n, (k, sid) in enumerate(appariables):
            rec = table[n]
            if rec is None:
                continue
            # ⛔ LE DONNEUR DOIT EXISTER, SINON LA LIGNE SORT. Un couple
            # gardé sans placebo mettrait le témoin sur une population
            # plus étroite que le candidat — et c'est exactement le genre
            # de dissymétrie qui rend un témoin rassurant à tort.
            dons = {}
            for g, perm in perms.items():
                rec_don = table[int(perm[n])]
                if rec_don is None:
                    dons = None
                    break
                dons[g] = (rec_don[6] - rec_don[2], rec_don[7] - rec_don[3],
                           rec_don[8] - rec_don[4], rec_don[9] - rec_don[5])
            if dons is None:
                continue
            o = obs_a(obs_par_station.get(sid), t_ms)
            if o is None:
                continue
            obs_speed, obs_dir, n_obs = o
            ligne = [jour_i, run_dt.hour, h, w, 0.0, *rec,
                     obs_speed,
                     obs_dir if obs_dir is not None else np.nan,
                     n_obs]
            for g in GRAINES_PLACEBO:
                ligne.extend(dons[g])
            # ⚠️ On rend l'IDENTIFIANT, pas le rang `k` du produit A.
            # Le rang est propre à un run ; le jour où l'axe des balises
            # gagne ou perd un point, une campagne indexée par le rang
            # mélangerait deux balises sous un seul numéro — la faute
            # que `delta_20m` refuse déjà côté appariement.
            lignes_run.append((sid, dom_de.get(sid, "?"), ligne))
    return lignes_run


# ══════════════════════════════════════════════════════════════════
#  LA CAMPAGNE — quels runs, et jusqu'où l'archive remonte
# ══════════════════════════════════════════════════════════════════

def runs_disponibles(crier=print):
    """La liste des runs du produit A réellement présents sur R2.

    ⚠️ ON LISTE, ON NE DEVINE PAS. Deviner « 8 runs par jour depuis
    N jours » produirait une campagne dont les trous seraient invisibles
    (chaque run absent se lirait comme un run vide), et surtout ça
    supposerait une profondeur d'archive qui n'existe pas : le produit A
    est purgé à 7 jours (`verif/purge.py::RETENTION_JOURS`).
    """
    import boto3                                             # noqa: PLC0415
    p = A.prefixe_lecture()
    if p == "R2_":
        crier("  ⚠️ aucun jeton de lecture dédié — on tente avec R2_*")
    s3 = boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}"
                     f".r2.cloudflarestorage.com",
        aws_access_key_id=os.environ[p + "ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ[p + "SECRET_ACCESS_KEY"],
        region_name="auto")
    bucket = os.environ.get(A.BUCKET_R2_ENV) or A.BUCKET_R2_DEFAUT
    runs, tok = [], None
    while True:
        kw = dict(Bucket=bucket, Prefix=A.PREFIXE_COLONNES, Delimiter="/",
                  MaxKeys=1000)
        if tok:
            kw["ContinuationToken"] = tok
        r = s3.list_objects_v2(**kw)
        runs += [c["Prefix"].rsplit("/", 2)[-2]
                 for c in r.get("CommonPrefixes", [])]
        if not r.get("IsTruncated"):
            break
        tok = r["NextContinuationToken"]
    return sorted(runs)


def extraire(sortie: pathlib.Path, racine: pathlib.Path,
             runs_admis=None, crier=print):
    runs = runs_disponibles(crier=crier)
    if runs_admis is not None:
        runs = [r for r in runs if int(r[11:13]) in runs_admis]
    crier(f"{len(runs)} runs du produit A sur R2 : {runs[0]} → {runs[-1]}")

    # Les journées d'observations à charger : celles que les runs
    # touchent, PLUS le lendemain du dernier (un run de 21 Z porte
    # jusqu'à 03 Z le lendemain).
    jours = sorted({datetime.strptime(r[:10], "%Y-%m-%d").replace(
        tzinfo=timezone.utc) for r in runs})
    jours = jours + [jours[-1] + timedelta(days=1)]
    obs = charger_obs(racine, jours)
    crier(f"observations : {len(obs)} stations sur {len(jours)} journées "
          f"({jours[0]:%Y-%m-%d} → {jours[-1]:%Y-%m-%d})")

    toutes, ids, domaines, ecartes = [], [], [], []
    for run in runs:
        try:
            lot = couples_du_run(run, obs, crier=crier)
        except A.Abort as exc:
            crier(f"  {run} : ÉCARTÉ — {exc}")
            ecartes.append(run)
            continue
        if not lot:
            ecartes.append(run)
            continue
        for sid, dom, ligne in lot:
            ids.append(sid)
            domaines.append(dom)
            toutes.append(ligne)
        crier(f"  {run} : {len(lot)} couples")

    if not toutes:
        raise Abort("aucun couple — rien à agréger, et un fichier vide "
                    "se lirait comme un résultat")
    tab = np.asarray(toutes, dtype=np.float64)
    np.savez_compressed(
        sortie, table=tab,
        champs=np.array(CHAMPS + CHAMPS_PLACEBO),
        balise=np.array(ids), domaine=np.array(domaines),
        runs=np.array(runs), runs_ecartes=np.array(ecartes or [""]),
        heures_pi=np.array(HEURES_PI),
        graines=np.array(GRAINES_PLACEBO))
    crier(f"\n✅ {len(toutes)} couples écrits dans {sortie} "
          f"({sortie.stat().st_size / 1e6:.1f} Mo)")
    crier(f"   {len(runs) - len(ecartes)}/{len(runs)} runs exploités ; "
          f"{len(set(ids))} balises distinctes")
    if ecartes:
        crier(f"   ⚠️ runs sans aucun couple : {len(ecartes)} — {ecartes[:6]}"
              f"{'…' if len(ecartes) > 6 else ''}")


# ══════════════════════════════════════════════════════════════════
#  L'AGRÉGATION — les cinq séries, et l'erreur telle que le score la
#  calcule
# ══════════════════════════════════════════════════════════════════

def _kmh_dir(u, v):
    """(vitesse km/h arrondie, direction ° arrondie) — via `decorer_vent`.

    ⛔ ON PASSE PAR LA FONCTION DU PROJET, ARRONDIS COMPRIS. `lignes()`
    écrit dans l'archive exactement ce que `decorer_vent` rend (0,1 km/h
    et 1°) ; mesurer sur des flottants non arrondis mesurerait une série
    que le score ne verra jamais. L'écart est minuscule — c'est
    justement pour ça qu'il faut le mettre du bon côté.
    """
    n = len(u)
    sp = np.empty(n)
    di = np.empty(n)
    for i in range(n):
        p = decorer_vent({"u": float(u[i]), "v": float(v[i])})
        sp[i], di[i] = p["vitesseKmh"], p["directionDeg"]
    return sp, di


def series(tab, champs):
    """Les cinq séries `(vitesse km/h, direction °)`, appariées.

    T0 = AROME₁₀ brut ; T1 = +w·Δ(20 m) ; T2 = +w·Δ(10 m) ;
    T1p / T2p = les mêmes avec le Δ d'une AUTRE balise.

    ⛔ Δ S'AJOUTE SUR u ET v, JAMAIS SUR LA VITESSE NI SUR L'ANGLE, et
    AVANT `decorer_vent` — la règle du composite, valable ici mot pour
    mot : ajouter un Δ à une vitesse scalaire perdrait la direction, et
    l'ajouter à un angle donnerait 180° au passage de 350° à 010°.
    """
    c = {nom: k for k, nom in enumerate(champs)}
    w = tab[:, c["w"]]
    u0, v0 = tab[:, c["u_ar10"]], tab[:, c["v_ar10"]]
    d20u = tab[:, c["u_pi20"]] - tab[:, c["u_ar20q"]]
    d20v = tab[:, c["v_pi20"]] - tab[:, c["v_ar20q"]]
    d10u = tab[:, c["u_pi10"]] - tab[:, c["u_ar10q"]]
    d10v = tab[:, c["v_pi10"]] - tab[:, c["v_ar10q"]]
    out = {
        "T0": _kmh_dir(u0, v0),
        "T1": _kmh_dir(u0 + w * d20u, v0 + w * d20v),
        "T2": _kmh_dir(u0 + w * d10u, v0 + w * d10v),
    }
    for g in GRAINES_PLACEBO:
        out[f"T1p{g}"] = _kmh_dir(u0 + w * tab[:, c[f"d20u_don{g}"]],
                                  v0 + w * tab[:, c[f"d20v_don{g}"]])
        out[f"T2p{g}"] = _kmh_dir(u0 + w * tab[:, c[f"d10u_don{g}"]],
                                  v0 + w * tab[:, c[f"d10v_don{g}"]])
    return out, dict(w=w, d20u=d20u, d20v=d20v, d10u=d10u, d10v=d10v)


def erreurs(sp, di, obs_sp, obs_di, mode_vectoriel):
    """L'erreur d'appariement, EXACTEMENT celle de `scoring.pair_error`.

    `mode_vectoriel` est imposé de l'extérieur et vaut pour les CINQ
    séries à la fois.

    ⛔⛔ ET C'EST LE POINT SUBTIL DE TOUTE LA MESURE. `pair_error`
    choisit vectoriel ou scalaire selon que la vitesse PRÉVUE dépasse
    5 km/h. Or la vitesse prévue n'est pas la même dans T0, T1 et T2 :
    laissé libre, le critère changerait de définition d'erreur entre les
    séries qu'on compare, sur les mêmes couples. On obtiendrait alors un
    « gain » qui serait en partie un changement de règle de calcul —
    exactement la classe de faux résultat que cette phase existe pour
    éviter. Le mode est donc décidé une fois par couple, sur un critère
    que les cinq séries partagent (cf. `mode_commun`).
    """
    e = np.empty(len(sp))
    vec = mode_vectoriel
    # Vectoriel : ‖V⃗prévu − V⃗observé‖. ⚠️ Convention de `scoring.to_uv`
    # RECOPIÉE À L'IDENTIQUE (`speed·sin`, `speed·cos`, sans signe moins)
    # — pas parce que le signe changerait la norme, mais parce qu'une
    # convention qui diverge de deux degrés entre deux fichiers est ce
    # que ce projet a déjà payé une fois à 180° près.
    au = np.sin(np.radians(di)) * sp
    av = np.cos(np.radians(di)) * sp
    bu = np.sin(np.radians(obs_di)) * obs_sp
    bv = np.cos(np.radians(obs_di)) * obs_sp
    e_vec = np.hypot(au - bu, av - bv)
    e_sca = np.abs(sp - obs_sp)
    e[:] = np.where(vec, e_vec, e_sca)
    return e


def mode_commun(sers, obs_sp, obs_di):
    """`True` là où les CINQ séries satisfont le critère vectoriel.

    ⚠️ Un couple où l'une des séries passe sous 5 km/h et pas les autres
    est un couple où la comparaison n'est plus appariée. On le traite en
    SCALAIRE pour tout le monde plutôt que de le jeter : le jeter
    éliminerait préférentiellement les cas de vent faible, c'est-à-dire
    exactement ceux où Δ pèse le plus lourd en proportion.
    """
    ok = np.isfinite(obs_di) & (obs_sp >= S.DIR_MIN_WIND_KMH)
    for sp, di in sers.values():
        ok &= np.isfinite(di) & (sp >= S.DIR_MIN_WIND_KMH)
    return ok


def rms(e):
    return float(np.sqrt(np.mean(e * e))) if len(e) else float("nan")


def bootstrap_jours(err_par_serie, jours, ref="T1", cand="T2",
                    tirages=2000, graine=7):
    """IC 95 % de `rms(ref) − rms(cand)`, rééchantillonné PAR JOURNÉE.

    ⛔⛔ PAR JOURNÉE, PAS PAR COUPLE, ET C'EST LA CORRECTION LA PLUS
    IMPORTANTE DE CETTE AGRÉGATION. Les ~95 000 couples ne sont pas
    95 000 tirages indépendants : une même situation météo lie toutes
    les balises d'un domaine pendant des heures. Un bootstrap sur les
    couples rendrait un intervalle dix fois trop étroit et ferait passer
    pour « significatif » ce qui n'est qu'une poignée de journées. On
    rééchantillonne donc les JOURNÉES, qui sont l'unité à peu près
    indépendante dont on dispose — et il n'y en a que sept.
    """
    rng = np.random.default_rng(graine)
    uniques = np.unique(jours)
    par_jour = {j: np.flatnonzero(jours == j) for j in uniques}
    ecarts = []
    for _ in range(tirages):
        pris = rng.choice(uniques, size=len(uniques), replace=True)
        idx = np.concatenate([par_jour[j] for j in pris])
        ecarts.append(rms(err_par_serie[ref][idx])
                      - rms(err_par_serie[cand][idx]))
    e = np.sort(np.asarray(ecarts))
    return float(np.percentile(e, 2.5)), float(np.percentile(e, 97.5))


def question_1(tab, champs, crier=print):
    """Commensurabilité : PI₁₀ et AROME(10u/10v) sont-ils le même
    diagnostic ?

    ── LA SIGNATURE QU'ON CHERCHE ────────────────────────────────────
    Si les deux familles de champ portaient le même diagnostic, Δ(10 m)
    et Δ(20 m) auraient des distributions de MÊME NATURE : centrées au
    même endroit, de largeur voisine. Un décalage systématique présent
    à 10 m et absent à 20 m dirait le contraire — et il se lit encore
    mieux sur le CISAILLEMENT interne à chaque modèle : le rapport
    `‖V(10)‖ / ‖V(20)‖` ne dépend que du modèle, pas de l'autre. S'ils
    diffèrent nettement, c'est que l'un des deux applique au 10 m une
    réduction de couche de surface que l'autre n'applique pas.
    """
    c = {n: k for k, n in enumerate(champs)}
    d10u = tab[:, c["u_pi10"]] - tab[:, c["u_ar10q"]]
    d10v = tab[:, c["v_pi10"]] - tab[:, c["v_ar10q"]]
    d20u = tab[:, c["u_pi20"]] - tab[:, c["u_ar20q"]]
    d20v = tab[:, c["v_pi20"]] - tab[:, c["v_ar20q"]]
    n10 = np.hypot(d10u, d10v)
    n20 = np.hypot(d20u, d20v)
    v_ar10 = np.hypot(tab[:, c["u_ar10q"]], tab[:, c["v_ar10q"]])
    v_ar20 = np.hypot(tab[:, c["u_ar20q"]], tab[:, c["v_ar20q"]])
    v_pi10 = np.hypot(tab[:, c["u_pi10"]], tab[:, c["v_pi10"]])
    v_pi20 = np.hypot(tab[:, c["u_pi20"]], tab[:, c["v_pi20"]])

    crier("\n══ QUESTION 1 — PI₁₀ et AROME(10u/10v) sont-ils "
          "commensurables ? ══")
    crier(f"   (0,025° contre 0,025°, {len(tab)} couples, m/s)\n")
    crier("  ‖Δ‖            médiane    moyenne    q90     "
          "|  Δu moyen  Δv moyen")
    for nom, nn, du, dv in (("Δ(20 m)", n20, d20u, d20v),
                            ("Δ(10 m)", n10, d10u, d10v)):
        crier(f"  {nom:<12} {np.median(nn):7.3f}   {nn.mean():7.3f}  "
              f"{np.percentile(nn, 90):7.3f}   |  {du.mean():+7.3f}  "
              f"{dv.mean():+7.3f}")
    r = np.corrcoef(np.concatenate([d10u, d10v]),
                    np.concatenate([d20u, d20v]))[0, 1]
    crier(f"\n  corrélation Δ(10 m) ↔ Δ(20 m), composantes empilées : "
          f"r = {r:.3f}")

    # ── Le cisaillement 10↔20 m, modèle par modèle ────────────────────
    ok = (v_ar20 > 1.0) & (v_pi20 > 1.0)      # au-dessus du bruit
    r_ar = v_ar10[ok] / v_ar20[ok]
    r_pi = v_pi10[ok] / v_pi20[ok]
    crier(f"\n  ‖V(10 m)‖ / ‖V(20 m)‖   (sur {ok.sum()} couples où "
          f"‖V(20 m)‖ > 1 m/s)")
    crier(f"    AROME (10u/10v ÷ HP1 20 m) : médiane {np.median(r_ar):.3f}  "
          f"moyenne {r_ar.mean():.3f}")
    crier(f"    AROME-PI (height=10 ÷ 20)  : médiane {np.median(r_pi):.3f}  "
          f"moyenne {r_pi.mean():.3f}")
    ecart = float(np.median(r_pi) - np.median(r_ar))
    crier(f"    écart des médianes : {ecart:+.3f}")

    # ── LE MÉCANISME, EN UNE LIGNE ────────────────────────────────────
    # ⛔ C'est la ligne qui explique tout le reste du rapport. Δ est une
    # différence entre deux vents ; son amplitude suit celle du vent. Le
    # vent à 10 m vaut ~0,77 fois celui à 20 m, donc Δ(20 m) est ~1/0,77
    # fois plus grand que Δ(10 m). ÉTENDRE Δ(20 m) CONSTANT SOUS 20 M
    # N'EST DONC PAS NEUTRE : c'est appliquer au 10 m une correction
    # calibrée pour un vent 30 % plus fort. `etendre_delta` appelle ça
    # « une extension, pas une mesure » — voici de combien.
    rapport = float(np.median(n20) / np.median(n10))
    kappa = float(np.median(r_ar))
    crier(f"\n  ⛔ rapport d'amplitude ‖Δ(20 m)‖ / ‖Δ(10 m)‖ (médianes) : "
          f"{rapport:.3f}")
    crier(f"     à comparer à 1 / {kappa:.3f} = {1 / kappa:.3f}, "
          f"l'inverse du cisaillement 10↔20 m.")
    crier("     Les deux coïncident : Δ suit l'amplitude du vent, et "
          "étendre Δ(20 m)\n     CONSTANT sous 20 m applique donc au "
          "10 m une correction calibrée\n     pour un vent ~30 % plus "
          "fort. Ce n'est pas neutre, et c'est mesurable.")

    # ── Δ(10 m) EST-IL AUTRE CHOSE QU'UN Δ(20 m) REMIS À L'ÉCHELLE ? ──
    # ⛔ CETTE LIGNE-LÀ CHANGE LA RECOMMANDATION, PAS SEULEMENT LE
    # VERDICT. Si Δ(10 m) ≈ κ·Δ(20 m) au bruit près, alors le vrai
    # Δ(10 m) n'apporte pas une information NOUVELLE : il apporte la
    # même à la bonne échelle — et corriger le facteur d'`etendre_delta`
    # suffirait, sans aller chercher une seconde famille de champ. S'il
    # en reste une part irréductible, c'est l'inverse, et le 10 m mérite
    # d'entrer dans `NIVEAUX_DELTA`.
    res_u, res_v = d10u - kappa * d20u, d10v - kappa * d20v
    residu = np.hypot(res_u, res_v)
    part = float(np.median(residu) / np.median(n10))
    crier(f"\n  Δ(10 m) − {kappa:.3f}·Δ(20 m) — le « reste » du vrai 10 m "
          f"une fois l'échelle ôtée")
    crier(f"    ‖résidu‖ médian {np.median(residu):.3f} m/s, soit "
          f"{100 * part:.0f} % de ‖Δ(10 m)‖ (médiane {np.median(n10):.3f})")
    return dict(residu_med=float(np.median(residu)), residu_part=part,
                kappa=kappa, rapport_amplitude=rapport,
                n=len(tab), med_d10=float(np.median(n10)),
                med_d20=float(np.median(n20)),
                moy_d10u=float(d10u.mean()), moy_d10v=float(d10v.mean()),
                moy_d20u=float(d20u.mean()), moy_d20v=float(d20v.mean()),
                r_delta=float(r), cis_arome=float(np.median(r_ar)),
                cis_pi=float(np.median(r_pi)), cis_ecart=ecart)


def _cisaillement(tab, champs) -> float:
    """κ = médiane de ‖V(10 m)‖ / ‖V(20 m)‖ côté AROME, en 0,025°.

    ⚠️ MESURÉ SUR LE TABLEAU, jamais écrit en dur. Une constante recopiée
    ici et une mesure là-bas, c'est deux nombres qui divergent le jour où
    l'archive change de saison — et le cisaillement de couche de surface
    n'a aucune raison d'être le même en août et en janvier.
    """
    c = {n: k for k, n in enumerate(champs)}
    v10 = np.hypot(tab[:, c["u_ar10q"]], tab[:, c["v_ar10q"]])
    v20 = np.hypot(tab[:, c["u_ar20q"]], tab[:, c["v_ar20q"]])
    ok = v20 > 1.0
    return float(np.median(v10[ok] / v20[ok])) if ok.any() else 1.0


def balayage_amplitude(tab, champs, obs_sp, obs_di, jours, vec, crier=print):
    """À quelle FRACTION de Δ l'erreur est-elle minimale ?

    ⛔⛔ CE N'EST PAS UN CANDIDAT, C'EST UN DIAGNOSTIC — ET IL EST
    ÉTIQUETÉ COMME UN RÉGLAGE APPRIS. `α` est ajusté sur les données
    qu'on mesure : le α optimal « dans l'échantillon » est
    structurellement flatteur, et le publier tel quel serait annoncer un
    gain qui ne se reproduira pas. On le sort donc DEUX FOIS : appris
    sur la première moitié des journées et évalué sur la seconde, puis
    l'inverse. C'est la seule des deux colonnes qui a le droit d'être
    citée.

    ⓘ Ce que α répond, et que le trio T0/T1/T2 ne répond pas : si Δ
    dégrade, est-ce parce qu'il porte la mauvaise information, ou parce
    qu'il en porte trop ? α* ≈ 0 dit la première ; α* nettement entre 0
    et 1 dit la seconde, et désigne la rampe comme le vrai réglage.
    """
    c = {n: k for k, n in enumerate(champs)}
    w = tab[:, c["w"]]
    u0, v0 = tab[:, c["u_ar10"]], tab[:, c["v_ar10"]]
    d20 = (tab[:, c["u_pi20"]] - tab[:, c["u_ar20q"]],
           tab[:, c["v_pi20"]] - tab[:, c["v_ar20q"]])
    d10 = (tab[:, c["u_pi10"]] - tab[:, c["u_ar10q"]],
           tab[:, c["v_pi10"]] - tab[:, c["v_ar10q"]])
    # ⛔ LA TROISIÈME COURBE EST CELLE QUI DÉSIGNE LE CORRECTIF LE MOINS
    # CHER. Si « Δ(20 m) × cisaillement » suit « Δ(10 m) vrai » de près,
    # alors le vrai 10 m n'apporte pas d'information nouvelle et
    # `etendre_delta` n'a besoin QUE d'un facteur — pas d'une seconde
    # famille de champ dans `NIVEAUX_DELTA`. Si elle reste en retrait, le
    # 10 m mesuré vaut son câblage. La question n'était pas au programme
    # de la phase B ; sans elle le rapport aurait recommandé le gros
    # changement sans avoir regardé le petit.
    kappa = _cisaillement(tab, champs)
    d = {"Δ(20 m) étendu          ": d20,
         "Δ(10 m) vrai            ": d10,
         f"Δ(20 m) × {kappa:.3f} (échelle)": (kappa * d20[0], kappa * d20[1])}
    alphas = np.round(np.arange(0.0, 1.05, 0.1), 2)

    # ⚠️ LE MODE VECTORIEL EST CELUI DU RAPPORT, FIGÉ POUR TOUS LES α.
    # Le laisser suivre α ferait varier la RÈGLE DE CALCUL le long de la
    # courbe : une partie du creux serait alors un changement de
    # définition, pas une amélioration.
    def err_de(du, dv, a, m):
        sp, di = _kmh_dir(u0[m] + a * w[m] * du[m], v0[m] + a * w[m] * dv[m])
        return rms(erreurs(sp, di, obs_sp[m], obs_di[m], vec[m]))

    uniques = np.unique(jours)
    moitie = len(uniques) // 2
    a_moitie = np.isin(jours, uniques[:moitie])
    b_moitie = ~a_moitie
    tous = np.ones(len(tab), dtype=bool)

    crier("\n══ DIAGNOSTIC — À QUELLE FRACTION α DE Δ L'ERREUR EST-ELLE "
          "MINIMALE ? ══")
    crier(f"   ⚠️ α est un réglage APPRIS. La colonne « dans "
          f"l'échantillon » est flatteuse\n      par construction ; seule "
          f"la colonne « hors échantillon » a le droit d'être citée.\n")
    out = {}
    for nom, (du, dv) in d.items():
        courbe = [err_de(du, dv, a, tous) for a in alphas]
        a_dans = float(alphas[int(np.argmin(courbe))])
        # Apprentissage croisé sur les deux moitiés de la campagne.
        hors = []
        for appr, eval_ in ((a_moitie, b_moitie), (b_moitie, a_moitie)):
            ca = [err_de(du, dv, a, appr) for a in alphas]
            a_star = float(alphas[int(np.argmin(ca))])
            hors.append((a_star, err_de(du, dv, a_star, eval_),
                         err_de(du, dv, 0.0, eval_),
                         err_de(du, dv, 1.0, eval_)))
        crier(f"   {nom}")
        crier("     α        " + "  ".join(f"{a:5.1f}" for a in alphas))
        crier("     rms      " + "  ".join(f"{v:5.2f}" for v in courbe))
        crier(f"     α* dans l'échantillon : {a_dans:.1f}")
        for i, (a_star, e_ev, e_0, e_1) in enumerate(hors, 1):
            crier(f"     moitié {i} → α* = {a_star:.1f} ; HORS "
                  f"ÉCHANTILLON rms(α*) = {e_ev:.4f}  "
                  f"contre rms(α=0) = {e_0:.4f} et rms(α=1) = {e_1:.4f}  "
                  f"→ gain {e_0 - e_ev:+.4f}")
        out[nom.strip()] = dict(alphas=alphas.tolist(), courbe=courbe,
                                alpha_dans=a_dans,
                                hors=[list(map(float, x)) for x in hors])
    # ── CE QUE α EST VRAIMENT, ET CE N'EST PAS UN COEFFICIENT ─────────
    # ⛔ L'algèbre est exacte, pas une interprétation :
    #     T0 + α·Δ = T0 + α·(PI − AROME) = (1−α)·AROME + α·PI   (+ le
    #     terme de maille, que T0 garde intact des deux côtés).
    # Donc α n'est pas « une correction atténuée » : c'est le POIDS DE
    # PI DANS UN MÉLANGE. α = 1 — ce que le composite fait aujourd'hui —
    # ne corrige pas AROME avec PI, il REMPLACE AROME par PI. Et α ≈ 0,5
    # est la moyenne des deux. Un lecteur qui n'a pas cette ligne lira le
    # creux de la courbe comme un réglage empirique ; c'est le résultat
    # le plus classique de la prévision d'ensemble.
    crier("\n   ⛔ α N'EST PAS UN COEFFICIENT D'ATTÉNUATION, C'EST UN "
          "POIDS DE MÉLANGE.")
    crier("      T0 + α·Δ = T0 + α·(PI − AROME) = (1−α)·AROME + α·PI, "
          "à l'identique.")
    crier("      α = 1 (ce que le composite sert aujourd'hui) ne corrige "
          "donc pas AROME\n      avec PI : il REMPLACE AROME par PI. "
          "α ≈ 0,5 est leur moyenne.")
    return out


#: Les cinq séries BRUTES de la question 0 : chaque modèle tout seul.
BRUTES = {
    "AROME₁₀ 0,01° (T0)": ("u_ar10", "v_ar10"),
    "AROME₁₀ 0,025°    ": ("u_ar10q", "v_ar10q"),
    "AROME-PI₁₀        ": ("u_pi10", "v_pi10"),
    "AROME₂₀ 0,025°    ": ("u_ar20q", "v_ar20q"),
    "AROME-PI₂₀        ": ("u_pi20", "v_pi20"),
}


def series_brutes(tab, champs):
    c = {n: k for k, n in enumerate(champs)}
    return {nom: _kmh_dir(tab[:, c[u]], tab[:, c[v]])
            for nom, (u, v) in BRUTES.items()}


def question_0(tab, champs, obs_sp, obs_di, vec=None, crier=print):
    """LES MODÈLES BRUTS, CHACUN CONTRE LES OBSERVATIONS.

    ⛔⛔ CE TABLEAU N'ÉTAIT PAS AU PROGRAMME DE LA PHASE B, ET IL EST CE
    QUI REND SON RÉSULTAT INTERPRÉTABLE. Le protocole ne comparait que
    des CORRECTIONS (T0, T1, T2). Si une correction dégrade, deux
    explications restent ouvertes et le protocole ne les sépare pas :
    « Δ est mal appliqué » ou « PI est simplement plus loin des balises
    qu'AROME à 10 m ». La seconde se lit ici, et nulle part ailleurs :
    on note PI₁₀ TOUT SEUL contre les mêmes observations.

    ⚠️ `AROME₁₀ 0,025°` est là comme témoin de MAILLE : sans lui, l'écart
    entre `AROME₁₀ 0,01°` et `PI₁₀` mélangerait un écart de modèle et un
    écart de résolution (1,1 km contre 2,8), et on attribuerait à PI une
    différence d'orographie.

    ⛔ `vec` VIENT DE L'APPELANT, ET C'EST UNE CORRECTION DU 26/08 AU
    SOIR. Ce tableau calculait d'abord SON PROPRE mode vectoriel, sur
    ses cinq séries : le T0 de la question 0 sortait alors à 8,2277 et
    celui de la question 2 à 8,1476 — deux nombres différents pour la
    MÊME série, dans le MÊME rapport, à deux pages d'écart. Aucun des
    deux n'était faux ; c'est la comparaison entre les deux tableaux qui
    l'aurait été, et c'est exactement le genre d'écart qu'un lecteur
    attribue à un effet physique.
    """
    sers = series_brutes(tab, champs)
    vec = mode_commun(sers, obs_sp, obs_di) if vec is None else vec
    crier("\n══ QUESTION 0 — LES MODÈLES BRUTS, CHACUN CONTRE LES BALISES ══")
    crier(f"   ({len(tab)} couples, {int(vec.sum())} vectoriels, "
          f"erreur MOYENNÉE en km/h)\n")
    out = {}
    ref = None
    for nom, (sp, di) in sers.items():
        v = rms(erreurs(sp, di, obs_sp, obs_di, vec))
        out[nom.strip()] = v
        if ref is None:
            ref = v
        crier(f"   {nom}   rms {v:8.4f}   ({v - ref:+.4f} / T0)")
    return out


ORDRE = ("T0", "T1", "T2", "T1p1", "T2p1", "T1p2", "T2p2")


def tableau(err, masque, titre, crier=print, jours=None):
    """Une ligne par série : n, erreur MOYENNÉE (rms), et gain sur T0.

    ⛔ MOYENNÉE, JAMAIS MÉDIANE. Un banc du 26/08 démontre que la
    médiane sur 24 heures ne peut pas bouger quand PI n'en corrige que
    6 ; ici on ne mesure que les heures corrigées, donc la médiane
    bougerait — mais c'est `err_vec_rms` et `mse_model` qui décident du
    classement, et c'est donc elles qu'il faut lire pour prédire ce que
    le score fera.
    """
    n = int(masque.sum())
    if n < 2:
        crier(f"\n── {titre} : {n} couple(s), rien à dire")
        return None
    crier(f"\n── {titre} — {n} couples "
          f"({len(np.unique(jours[masque])) if jours is not None else '?'} "
          f"journées)")
    crier("   série   rms (km/h)   gain / T0     gain / T1")
    base = rms(err["T0"][masque])
    ref = rms(err["T1"][masque])
    out = {}
    for s in ORDRE:
        v = rms(err[s][masque])
        out[s] = v
        crier(f"   {s:<6}  {v:9.4f}   {base - v:+9.4f}   {ref - v:+9.4f}")
    return out


def agreger(source: pathlib.Path, crier=print):
    z = np.load(source, allow_pickle=False)
    tab, champs = z["table"], [str(x) for x in z["champs"]]
    balise, domaine = z["balise"], z["domaine"]
    runs = [str(r) for r in z["runs"]]
    c = {n: k for k, n in enumerate(champs)}
    jours = tab[:, c["jour"]].astype(np.int64)
    run_h = tab[:, c["run_h"]].astype(np.int64)
    h = tab[:, c["h"]].astype(np.int64)

    crier("══════════════════════════════════════════════════════════")
    crier("  PHASE B — Δ(10 m) VRAI CONTRE Δ(20 m) ÉTENDU")
    crier("══════════════════════════════════════════════════════════")
    crier(f"  couples          : {len(tab)}")
    crier(f"  runs exploités   : {len(set(zip(jours.tolist(), run_h.tolist())))}"
          f" (archive listée : {len(runs)} runs, {runs[0]} → {runs[-1]})")
    crier(f"  journées         : {len(np.unique(jours))} — "
          f"{np.unique(jours)[0]} → {np.unique(jours)[-1]}")
    crier(f"  balises          : {len(set(balise.tolist()))}")
    crier(f"  échéances PI     : {sorted(set(h.tolist()))} h "
          f"(rampe : w = {sorted(set(tab[:, c['w']].tolist()))})")

    obs_sp, obs_di = tab[:, c["obs_speed"]], tab[:, c["obs_dir"]]
    q1 = question_1(tab, champs, crier=crier)

    # ⛔⛔ UN SEUL MASQUE POUR TOUT LE RAPPORT, CALCULÉ SUR LES DIX
    # SÉRIES À LA FOIS. Chaque tableau calculait d'abord le sien : le T0
    # de la question 0 sortait alors à 8,2277 et celui de la question 2
    # à 8,1476 — même série, même rapport, deux nombres. Un lecteur y
    # lirait un effet physique. C'est le mode d'erreur qui doit être
    # constant, pas les chiffres qui doivent s'expliquer.
    sers, bruts = series(tab, champs)
    vec = mode_commun({**sers, **series_brutes(tab, champs)}, obs_sp, obs_di)
    q0 = question_0(tab, champs, obs_sp, obs_di, vec=vec, crier=crier)
    crier(f"\n  mode d'erreur : {int(vec.sum())} couples VECTORIELS "
          f"({100 * vec.mean():.1f} %), le reste en scalaire "
          f"(seuil {S.DIR_MIN_WIND_KMH} km/h — UN SEUL masque pour les "
          f"dix séries de ce rapport)")
    err = {s: erreurs(sp, di, obs_sp, obs_di, vec)
           for s, (sp, di) in sers.items()}

    crier("\n══ QUESTION 2 — Δ(10 m) rapproche-t-il des observations ? ══")
    tout = np.ones(len(tab), dtype=bool)
    res = {"ensemble": tableau(err, tout, "ENSEMBLE (8 runs/jour)",
                               crier=crier, jours=jours)}

    # ── Le sous-ensemble que le SCORE verrait bouger ──────────────────
    # ⛔ Les runs 00 Z et 03 Z seuls (`RUNS_ADMIS`, décision 1 du lot I).
    # C'est le seul tableau qui prédit un changement de classement ;
    # l'ensemble, lui, répond à la question physique.
    m_score = np.isin(run_h, np.asarray(A.RUNS_ADMIS))
    res["runs_notes"] = tableau(err, m_score, "RUNS NOTÉS seulement "
                                "(00 Z / 03 Z, ce que le score verrait)",
                                crier=crier, jours=jours)

    crier("\n── par échéance ─────────────────────────────────────────")
    res["par_h"] = {}
    for hh in sorted(set(h.tolist())):
        res["par_h"][int(hh)] = tableau(err, h == hh, f"+{hh} h",
                                        crier=crier, jours=jours)

    crier("\n── par domaine ──────────────────────────────────────────")
    res["par_domaine"] = {}
    for d in sorted(set(domaine.tolist())):
        res["par_domaine"][str(d)] = tableau(err, domaine == d, str(d),
                                             crier=crier, jours=jours)

    crier("\n── par journée (stabilité du verdict) ───────────────────")
    crier("   jour        n     rms T0    rms T1    rms T2   T1−T2")
    res["par_jour"] = {}
    for j in np.unique(jours):
        m = jours == j
        v = {s: rms(err[s][m]) for s in ("T0", "T1", "T2")}
        res["par_jour"][int(j)] = v
        crier(f"   {int(j)}  {int(m.sum()):5d}  {v['T0']:8.4f}  "
              f"{v['T1']:8.4f}  {v['T2']:8.4f}  {v['T1'] - v['T2']:+7.4f}")


    crier("\n── intervalles de confiance (bootstrap PAR JOURNÉE, 2000 "
          "tirages) ──")
    crier("   ⚠️ l'unité rééchantillonnée est la JOURNÉE, pas le couple : "
          "les couples\n      d'une même journée ne sont pas indépendants, "
          "et il n'y a que "
          f"{len(np.unique(jours))} journées.")
    res["ic"] = {}
    for ref, cand in (("T0", "T1"), ("T0", "T2"), ("T1", "T2"),
                      ("T0", "T1p1"), ("T0", "T2p1"),
                      ("T0", "T1p2"), ("T0", "T2p2")):
        lo, hi = bootstrap_jours(err, jours, ref, cand)
        d = rms(err[ref]) - rms(err[cand])
        res["ic"][f"{ref}→{cand}"] = (d, lo, hi)
        signe = "  ⟵ 0 dans l'IC" if lo <= 0 <= hi else ""
        crier(f"   rms({ref}) − rms({cand}) = {d:+.4f} km/h   "
              f"IC95 [{lo:+.4f}, {hi:+.4f}]{signe}")

    crier("\n══ CE QUE CES CHIFFRES DISENT, ET CE QU'ILS NE DISENT PAS ══")
    g1 = rms(err["T0"]) - rms(err["T1"])
    g2 = rms(err["T0"]) - rms(err["T2"])
    p1 = np.mean([rms(err["T0"]) - rms(err[f"T1p{g}"])
                  for g in GRAINES_PLACEBO])
    p2 = np.mean([rms(err["T0"]) - rms(err[f"T2p{g}"])
                  for g in GRAINES_PLACEBO])
    crier(f"   gain BRUT  de T1 sur T0 : {g1:+.4f} km/h   "
          f"| placebo T1 : {p1:+.4f}  → gain NET {g1 - p1:+.4f}")
    crier(f"   gain BRUT  de T2 sur T0 : {g2:+.4f} km/h   "
          f"| placebo T2 : {p2:+.4f}  → gain NET {g2 - p2:+.4f}")
    res["net"] = dict(T1_brut=g1, T1_placebo=float(p1), T1_net=g1 - float(p1),
                      T2_brut=g2, T2_placebo=float(p2), T2_net=g2 - float(p2))
    crier("   ⚠️ « gain NET » = gain sur T0 moins celui d'un Δ étranger. "
          "Il dit que Δ porte\n      une information propre à SA balise — "
          "il ne dit PAS que la série corrigée\n      bat la série non "
          "corrigée. Les deux lignes du dessus le disent, elles.")
    res["q0"], res["q1"] = q0, q1
    res["alpha"] = balayage_amplitude(tab, champs, obs_sp, obs_di, jours,
                                      vec, crier=crier)
    return res


# ══════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--extraire", action="store_true",
                    help="lit R2 + les observations et écrit les couples")
    ap.add_argument("--agreger", action="store_true",
                    help="relit les couples et sort les tableaux")
    ap.add_argument("--sortie", default="/tmp/deltab.npz")
    ap.add_argument("--racine", default="/var/lib/bw-model-verif",
                    help="racine locale des archives du scoring")
    ap.add_argument("--runs-notes-seulement", action="store_true",
                    help="n'extraire que les runs 00 Z / 03 Z")
    ap.add_argument("--json", default=None,
                    help="écrit aussi le résumé agrégé en JSON")
    a = ap.parse_args(argv)
    if not (a.extraire or a.agreger):
        ap.error("choisir --extraire et/ou --agreger")
    sortie = pathlib.Path(a.sortie)
    if a.extraire:
        extraire(sortie, pathlib.Path(a.racine),
                 runs_admis=set(A.RUNS_ADMIS) if a.runs_notes_seulement
                 else None)
    if a.agreger:
        res = agreger(sortie)
        if a.json:
            pathlib.Path(a.json).write_text(
                json.dumps(res, indent=2, ensure_ascii=False,
                           default=float), encoding="utf-8")
            print(f"\nrésumé JSON : {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
