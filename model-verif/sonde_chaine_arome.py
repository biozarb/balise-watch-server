#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/sonde_chaine_arome.py — D'OÙ VIENNENT LES +0,17 km/h
#  DE LA CHAÎNE `arome_r2` ?                        (Lot L4, 27/08/2026)
#
#  PONCTUELLE, LECTURE SEULE. Elle n'écrit rien en base, ne publie rien,
#  ne s'installe dans aucun timer. Elle lit les archives locales de
#  `/var/lib/bw-model-verif` et rend un rapport.
#
#  ═══ CE QU'ELLE MESURE, ET POURQUOI C'EST MESURABLE ═══
#
#  L'audit du 26/08 (§0.3, §2.2) a mesuré qu'`arome_r2` porte
#  +0,165 km/h d'erreur médiane contre `meteofrance_arome_france_hd`
#  (IC95j [+0,088 ; +0,283], n = 2 293) et +0,268 contre `agrume`.
#  Quatre causes étaient NOMMÉES, aucune PESÉE : l'arrondi entier des
#  tuiles, le plus proche voisin de tuile, la distance à la balise,
#  l'heure de lecture.
#
#  ⭐ Ce qui rend la décomposition possible, et ce qui fait tout
#  l'intérêt du lot : `agrume` et `arome_r2` lisent LE MÊME MODÈLE, LE
#  MÊME RUN, LES MÊMES CHAMPS. Vérifié sur les archives du 26/08 :
#  `agrume_run` = `arome_run` = 2026-08-26T00:00:00Z, maille 0,01° des
#  deux côtés, vent 10 m des champs dédiés 10u/10v du paquet SP1.
#  Il ne reste donc entre les deux séries QUE de la plomberie — et
#  toute la plomberie est énumérable :
#
#    (a) L'ARRONDI. `arome-wind/ingest.py::_ms()` rend `round(spd)`
#        (entier km/h) ; `agrume/profil.py::decorer_vent()` rend
#        `round(spd, 1)`. ⭐ La DIRECTION, elle, est arrondie à l'entier
#        DES DEUX CÔTÉS et avec la même convention (relu dans les deux
#        fichiers) : elle ne peut RIEN expliquer, et c'est la première
#        chose que cette sonde retire de la liste des suspects.
#
#    (b) LE NŒUD LU. `agrume/quantification.py::index_plats` prend le
#        plus proche nœud du treillis natif. `arome_fcst.Grille.voisin`
#        prend le plus proche nœud DE LA TUILE 2° de la balise — une
#        balise posée près d'un bord de tuile peut donc lire un nœud
#        qui n'est pas le sien. C'est mesurable balise par balise, sans
#        rien relire : `arome_dist_km` est ARCHIVÉ sur chaque ligne, et
#        la distance du VRAI plus proche nœud se calcule.
#
#    (c) LES HEURES. `arome-wind/ingest.py::keep_step()` ne garde
#        qu'une échéance sur trois dans la fenêtre 22-04 UTC : mesuré
#        sur les 4 302 lignes du 26/08, `arome_r2` n'a AUCUNE valeur
#        aux heures 01, 02, 22 et 23 UTC, quand `agrume` a ses 24. Or
#        `err_vec_med` est une MÉDIANE SUR LES HEURES DISPONIBLES : les
#        deux séries ne sont donc pas notées sur la même journée. Cette
#        cause-là n'était nommée nulle part — ni dans l'audit, ni dans
#        l'en-tête d'`arome_fcst.py`.
#
#    (d) LE RESTE. Tout ce que (a), (b) et (c) ne prennent pas.
#
#  ═══ L'IDENTITÉ, ET POURQUOI ELLE EST EXACTE ═══
#
#  Pour une balise-jour, en notant `err(série, heures)` l'erreur rendue
#  par `scoring.series_error` (l'arithmétique de production, importée,
#  jamais réécrite) :
#
#      gap        = err(R2, H_r2)      − err(AGRUME, H_ag)
#      p_heures   = err(AGRUME, H_∩)   − err(AGRUME, H_ag)
#      p_arrondi  = err(AGRUME↓, H_∩)  − err(AGRUME, H_∩)
#      p_reste    = err(R2, H_∩)       − err(AGRUME↓, H_∩)
#
#  avec H_∩ = les heures que LES DEUX portent, et AGRUME↓ = `agrume`
#  passé par l'arrondi de production d'`_ms`. Comme H_∩ = H_r2 (mesuré :
#  `agrume` porte toutes les heures que porte `arome_r2`), les trois
#  parts SOMMENT EXACTEMENT au gap — ce n'est pas une approximation, et
#  la sonde le VÉRIFIE sur chaque balise-jour au lieu de l'affirmer.
#
#  ⛔ L'ORDRE DES TERMES EST UN ARBITRAGE, PAS UNE VÉRITÉ. Une
#  décomposition séquentielle attribue les interactions au terme qui
#  passe en dernier. L'ordre retenu — heures, puis arrondi, puis reste —
#  met le RESTE en dernier, donc lui donne les interactions : le terme
#  qu'on comprend le moins est celui qu'on charge le plus. C'est le sens
#  prudent. L'ordre inverse est calculé aussi (`--ordre-inverse`), et
#  l'écart entre les deux lectures EST la taille des interactions ; il
#  est écrit dans le rapport plutôt que caché.
#
#  ═══ CE QUE CETTE SONDE NE PEUT PAS DIRE ═══
#
#  ⛔ Elle ne mesure PAS « la distance à la balise » comme cause à part
#  entière. `agrume` et `arome_r2` visent le MÊME nœud dans 99,5 % des
#  cas (mesuré ci-dessous) : la distance de 0,35 km médian est commune
#  aux deux chaînes, elle ne peut donc pas expliquer un ÉCART entre
#  elles. Elle expliquerait un écart avec une chaîne qui interpolerait —
#  aucune des deux ne le fait. Le suspect « distance » de l'audit est
#  donc requalifié en « nœud DIFFÉRENT », qui est la seule part de la
#  distance qui les sépare.
#
#  ⛔ Elle ne rejoue AUCUN GRIB. Les tuiles R2 sont réécrites en place
#  toutes les 3 h (`CACHE_REECRIT`) : les grilles des jours passés
#  n'existent plus, et aucune sonde ne les fera revenir. Ce qui reste
#  du passé, ce sont les deux archives NDJSON — et elles suffisent,
#  puisque chacune porte la valeur AU POINT DE LA BALISE.
#
#  ⚠️ L'arrondi simulé part d'une valeur DÉJÀ arrondie au dixième
#  (`agrume` archive `round(spd, 1)`). `round(round(x, 1))` et
#  `round(x)` diffèrent sur les valeurs à moins de 0,05 km/h d'un
#  demi-entier — un cas sur ~vingt en principe, et toujours d'un rang
#  d'arrondi. C'est un MAJORANT de fidélité, pas une source de biais de
#  signe : la sonde le dit, elle ne le corrige pas (le corriger
#  demanderait le u/v brut, qui n'est pas archivé).
#
#      python3 sonde_chaine_arome.py                       # 5 derniers jours
#      python3 sonde_chaine_arome.py --fin 2026-08-26 --jours 5
#      python3 sonde_chaine_arome.py --json                # objet brut
#      python3 sonde_chaine_arome.py --cout-tuile          # + le coût octets
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import inference as INF
import score as SC
import scoring as S
from arome_fcst import distance_km

# ══════════════════════════════════════════════════════════════════
#  CONSTANTES — chacune mesurée, aucune déduite d'une doc
# ══════════════════════════════════════════════════════════════════

MODEL_R2 = "arome_r2"
MODEL_AGRUME = "agrume"
MODEL_OM = "meteofrance_arome_france_hd"

#: Le pas du treillis natif d'AROME 0,01° (`arome-wind/ingest.py`
#: GRID_SOL="001", STEP_SOL=0.01 ; `agrume_fcst` maille `001`).
#: ⭐ MESURÉ, pas supposé : sur les 4 302 lignes du 26/08, la distance
#: `arome_dist_km` archivée coïncide à moins de 11 m avec la distance au
#: multiple de 0,01° le plus proche pour 4 280 lignes (99,5 %). Le
#: treillis est donc bien aligné sur les multiples de 0,01°, et les
#: 22 lignes restantes sont exactement les balises de bord de tuile —
#: c'est-à-dire la cause (b), pas un défaut de cette constante.
#: La sonde REFAIT ce contrôle à chaque exécution et le publie : si un
#: jour l'accord tombe, c'est le treillis qui a bougé, et le rapport le
#: dira avant qu'on lise ses chiffres de travers.
MAILLE_DEG = 0.01

#: Sous cette tolérance, les deux chaînes lisent LE MÊME nœud. 11 m :
#: la précision d'écriture de `arome_dist_km` est le centième de km.
TOL_NOEUD_KM = 0.011

#: La seule source que `agrume_fcst` note (`SOURCE_NOTEE`). La sonde
#: n'invente pas de population : elle prend l'intersection réelle.
SOURCE = "pioupiou"

#: Le lead de la classe notée par les deux flux (offset 0 de
#: `score.LEAD_BY_OFFSET`).
LEAD_H = 6

DAY_MS = 24 * 3600 * 1000


# ══════════════════════════════════════════════════════════════════
#  LE NOYAU — quatre fonctions pures, bançables sans une archive
# ══════════════════════════════════════════════════════════════════

def noeud_le_plus_proche(lat: float, lon: float,
                         maille: float = MAILLE_DEG) -> tuple[float, float]:
    """Le nœud du treillis natif le plus proche d'un point.

    ⚠️ On passe par les CENTIÈMES entiers plutôt que par
    `round(lat / maille) * maille` : le second rend 45.019999999999996
    pour 45,02 et deux nœuds identiques cesseraient de se comparer
    égaux. La comparaison de nœuds est exactement ce que fait cette
    sonde.
    """
    pas = round(1.0 / maille)
    return (round(lat * pas) / pas, round(lon * pas) / pas)


def arrondi_tuile(speed: float | None) -> float | None:
    """L'arrondi de publication des tuiles, tel qu'il est écrit dans
    `arome-wind/ingest.py::_ms()` : `round(spd)` — la vitesse en km/h à
    l'ENTIER, rien d'autre.

    ⛔ La direction N'EST PAS touchée ici, et ce n'est pas un oubli :
    `_ms` rend `round(drc)` et `decorer_vent` rend `round(...)`,
    c'est-à-dire le MÊME arrondi entier avec la MÊME convention (270 −
    atan2, « d'où vient le vent »). Arrondir la direction une seconde
    fois ferait apparaître un effet qui n'existe pas dans la chaîne.
    """
    if speed is None or not S._finite(speed):
        return None
    return float(round(speed))


def serie_du_jour(row: dict, day_start_ms: int):
    """`(heures_ms, vitesses, directions)` d'une ligne d'archive,
    restreints à la journée notée — la découpe EXACTE de
    `score.daily_rows` (mêmes bornes, même indexation par position).
    """
    times = SC.fcst_times_ms(row)
    speed = row.get("speed") or [None] * len(times)
    direction = row.get("dir") or [None] * len(times)
    idx = [i for i, t in enumerate(times)
           if day_start_ms <= t < day_start_ms + DAY_MS]
    return ([times[i] for i in idx],
            [speed[i] if i < len(speed) else None for i in idx],
            [direction[i] if i < len(direction) else None for i in idx])


def erreur(times, speed, direction, obs, min_heures: int):
    """L'erreur d'une série, par l'arithmétique de PRODUCTION.

    `S.pair_series` + `S.series_error`, importées telles quelles. Rien
    n'est réécrit ici : une seconde implémentation « équivalente » de
    l'appariement serait la première chose à diverger, et c'est la
    leçon que le banc de parité de `scoring.py` a déjà coûtée.
    """
    pairs = S.pair_series(times, speed, direction, obs)
    if len(pairs) < min_heures:
        return None
    return S.series_error(pairs)


# ══════════════════════════════════════════════════════════════════
#  LA DÉCOMPOSITION D'UNE BALISE-JOUR
# ══════════════════════════════════════════════════════════════════

def decomposer(row_ag: dict, row_r2: dict, obs, day_start_ms: int,
               min_heures: int = SC.MIN_HOURS_DAILY,
               ordre_inverse: bool = False) -> dict | None:
    """Le cœur du lot. Rend `None` quand la balise-jour n'est pas
    notable des DEUX côtés — jamais un demi-résultat.

    ⛔ Le filtre `min_heures` s'applique à CHAQUE variante et la
    balise-jour tombe ENTIÈREMENT si l'une manque. Garder les variantes
    qui passent ferait sommer des termes calculés sur des populations
    différentes, et l'identité ne serait plus vraie qu'en apparence.
    """
    t_ag, s_ag, d_ag = serie_du_jour(row_ag, day_start_ms)
    t_r2, s_r2, d_r2 = serie_du_jour(row_r2, day_start_ms)

    par_heure_r2 = {t: i for i, t in enumerate(t_r2)}
    # H_∩ : les heures que les DEUX portent, dans l'ordre du temps.
    inter = [(t, i, par_heure_r2[t]) for i, t in enumerate(t_ag)
             if t in par_heure_r2
             and s_ag[i] is not None and s_r2[par_heure_r2[t]] is not None]
    if not inter:
        return None
    t_i = [t for t, _, _ in inter]
    s_ag_i = [s_ag[i] for _, i, _ in inter]
    d_ag_i = [d_ag[i] for _, i, _ in inter]
    s_r2_i = [s_r2[j] for _, _, j in inter]
    d_r2_i = [d_r2[j] for _, _, j in inter]
    s_q_i = [arrondi_tuile(v) for v in s_ag_i]

    e_ag_tout = erreur(t_ag, s_ag, d_ag, obs, min_heures)
    e_ag_int = erreur(t_i, s_ag_i, d_ag_i, obs, min_heures)
    e_q_int = erreur(t_i, s_q_i, d_ag_i, obs, min_heures)
    e_r2_int = erreur(t_i, s_r2_i, d_r2_i, obs, min_heures)
    e_r2_tout = erreur(t_r2, s_r2, d_r2, obs, min_heures)
    if None in (e_ag_tout, e_ag_int, e_q_int, e_r2_int, e_r2_tout):
        return None

    out = {"n_heures_agrume": e_ag_tout.n, "n_heures_r2": e_r2_tout.n,
           "n_heures_inter": e_r2_int.n,
           "vector_ratio_agrume": e_ag_tout.vector_ratio,
           "vector_ratio_r2": e_r2_tout.vector_ratio}
    for cle in ("med", "rms"):
        a_tout = getattr(e_ag_tout, cle)
        a_int = getattr(e_ag_int, cle)
        q_int = getattr(e_q_int, cle)
        r_int = getattr(e_r2_int, cle)
        r_tout = getattr(e_r2_tout, cle)
        if None in (a_tout, a_int, q_int, r_int, r_tout):
            return None
        if ordre_inverse:
            # L'arrondi passe D'ABORD, les heures ensuite : les
            # interactions changent de terme, et c'est l'écart entre
            # les deux lectures qui les MESURE.
            e_q_tout = erreur(t_ag, [arrondi_tuile(v) for v in s_ag],
                              d_ag, obs, min_heures)
            if e_q_tout is None or getattr(e_q_tout, cle) is None:
                return None
            q_tout = getattr(e_q_tout, cle)
            p_arrondi = q_tout - a_tout
            p_heures = q_int - q_tout
        else:
            p_heures = a_int - a_tout
            p_arrondi = q_int - a_int
        p_reste = r_int - q_int
        out[cle] = {
            "err_agrume": a_tout, "err_r2": r_tout,
            "gap": r_tout - a_tout,
            "part_heures": p_heures,
            "part_arrondi": p_arrondi,
            "part_reste": p_reste,
            # ⭐ L'identité n'est pas affirmée, elle est REPORTÉE : si
            # H_∩ cessait d'être H_r2 (une heure qu'`arome_r2` porte et
            # qu'`agrume` n'a pas), ce résidu deviendrait non nul et le
            # rapport le montrerait au lieu de le taire.
            "residu_identite": (r_tout - a_tout)
            - (p_heures + p_arrondi + p_reste),
        }
    return out


# ══════════════════════════════════════════════════════════════════
#  LE NŒUD LU — la cause (b), mesurée sans relire une seule tuile
# ══════════════════════════════════════════════════════════════════

def ecart_de_noeud(row_r2: dict, maille: float = MAILLE_DEG):
    """`(force_par_la_tuile, ecart_km, d_archive, d_theorique)` pour une
    ligne `arome_r2`.

    `arome_dist_km` est la distance au nœud QU'ELLE A LU (posée par
    `arome_fcst.collecter`). `d_theorique` est la distance au plus
    proche nœud DE SA PROPRE COORDONNÉE. Quand les deux diffèrent, c'est
    la TUILE qui a imposé un autre nœud (bord de tuile) — la cause (b)
    de l'en-tête, sans rejouer un GRIB.

    ⛔ CE CONTRÔLE NE DIT RIEN DE `agrume`, et l'avoir cru un moment a
    failli coûter la conclusion du lot : il compare `arome_r2` à
    elle-même. Deux chaînes peuvent lire deux nœuds DIFFÉRENTS en étant
    chacune parfaitement cohérente — il suffit qu'elles ne partent pas
    de la même coordonnée de balise. C'est `noeuds_lus` qui tranche.
    """
    d_arch = row_r2.get("arome_dist_km")
    if d_arch is None:
        return None
    la, lo = noeud_le_plus_proche(row_r2["lat"], row_r2["lon"], maille)
    d_theo = distance_km(row_r2["lat"], row_r2["lon"], la, lo)
    ecart = float(d_arch) - d_theo
    return (ecart > TOL_NOEUD_KM, ecart, float(d_arch), d_theo)


def noeuds_lus(row_ag: dict, row_r2: dict, maille: float = MAILLE_DEG):
    """LES DEUX CHAÎNES LISENT-ELLES LE MÊME POINT DE GRILLE ?

    ⭐ C'est la question du lot, et elle a DEUX réponses possibles pour
    « non » — il fallait les séparer :

      • la TUILE a imposé son nœud (`arome_r2` près d'un bord) ;
      • les deux chaînes ne partent pas de la même COORDONNÉE de
        balise. `agrume_fcst` lit la liste GELÉE (`freeze_balises`),
        `arome_fcst` lit les six référentiels VIVANTS rafraîchis chaque
        nuit par `collect.py`. Une balise déplacée porte donc deux
        positions, et les deux chaînes notent deux endroits.
        ⛔ Mesuré le 27/08 : 160 balises sur 285, jusqu'à 147 km.

    Rend `(meme_noeud, ecart_coord_km, cause)` où `cause` vaut
    `"identique"`, `"coordonnee"` ou `"tuile"`.
    """
    d_coord = distance_km(row_ag["lat"], row_ag["lon"],
                          row_r2["lat"], row_r2["lon"])
    n_ag = noeud_le_plus_proche(row_ag["lat"], row_ag["lon"], maille)
    n_r2 = noeud_le_plus_proche(row_r2["lat"], row_r2["lon"], maille)
    tuile = ecart_de_noeud(row_r2, maille)
    if tuile is not None and tuile[0]:
        return (False, d_coord, "tuile")
    if n_ag != n_r2:
        return (False, d_coord, "coordonnee")
    return (True, d_coord, "identique")


def ecarts_de_chaine(row_ag: dict, row_r2: dict, day_start_ms: int):
    """Ce que les deux chaînes lisent, SANS AUCUNE OBSERVATION.

    ⭐ C'est la mesure la plus propre du lot : elle ne dépend d'aucun
    vent réel, d'aucun appariement, d'aucune médiane. Pour chaque
    balise-heure commune elle rend `‖v(r2) − v(agrume)‖` et la part que
    le seul arrondi explique — deux nombres qu'aucune convention de
    notation ne peut déformer.
    """
    t_ag, s_ag, d_ag = serie_du_jour(row_ag, day_start_ms)
    t_r2, s_r2, d_r2 = serie_du_jour(row_r2, day_start_ms)
    idx_r2 = {t: j for j, t in enumerate(t_r2)}
    tot, quant, reste = [], [], []
    for i, t in enumerate(t_ag):
        j = idx_r2.get(t)
        if j is None:
            continue
        sa, da, sr, dr = s_ag[i], d_ag[i], s_r2[j], d_r2[j]
        if None in (sa, da, sr, dr):
            continue
        ua, va = S.to_uv(sa, da)
        ur, vr = S.to_uv(sr, dr)
        uq, vq = S.to_uv(arrondi_tuile(sa), da)
        tot.append(math.hypot(ur - ua, vr - va))
        quant.append(math.hypot(uq - ua, vq - va))
        # ⭐ CE QUI RESTE APRÈS L'ARRONDI, balise-heure par balise-heure.
        # C'est la seule mesure du lot qui ne passe ni par une médiane,
        # ni par une observation : si elle est nulle, les deux chaînes
        # lisent LE MÊME NŒUD et il n'y a plus rien à expliquer.
        reste.append(math.hypot(ur - uq, vr - vq))
    return tot, quant, reste


# ══════════════════════════════════════════════════════════════════
#  LECTURE DES ARCHIVES
# ══════════════════════════════════════════════════════════════════

def lire_jour(root: pathlib.Path, jour: datetime, avec_om: bool):
    """Les trois (ou quatre) flux d'une journée, indexés par balise.

    Un flux absent rend `{}` — `read_ndjson` traite l'objet manquant
    comme « pas de donnée ce jour-là », et c'est le cas normal des
    premiers jours d'`arome_r2` (né le 22/08).
    """
    def par_balise(rows, modele):
        return {f"{r['source']}:{r['station_id']}": r for r in rows
                if r.get("model") == modele and r.get("source") == SOURCE}

    ag = par_balise(SC.read_ndjson(root, SC.fcst_agrume_key(jour)),
                    MODEL_AGRUME)
    r2 = par_balise(SC.read_ndjson(root, SC.fcst_arome_key(jour)), MODEL_R2)
    om = {}
    if avec_om:
        # ⚠️ `fcst_parties`, PAS `fcst_key` : depuis le lot S0.6 le flux
        # Open-Meteo peut être PARTITIONNÉ, et lire la seule partie 1
        # rendrait une population silencieusement amputée.
        om = par_balise(SC.fcst_parties(root, jour)[0], MODEL_OM)
    obs = {f"{r['source']}:{r['station_id']}": SC.to_obs_samples(r)
           for r in SC.all_obs_rows(root, jour) if r.get("source") == SOURCE}
    return ag, r2, om, obs


def _ci(valeurs_par_jour: dict) -> INF.DiffCI:
    """L'IC par blocs de jours, avec le socle du projet (`MIN_DAYS_BLOCK`
    = 8 jours) et SANS l'assouplir.

    ⚠️ Sur une fenêtre de 5 jours il rendra `window_too_short`, et c'est
    la bonne réponse : l'audit du 26/08 publiait un IC sur 4 jours
    d'`arome_r2` et le lot L1 a déjà tranché que c'est le socle qui a
    raison. Le rapport publie alors la SÉRIE JOURNALIÈRE — cinq nombres
    qu'on lit soi-même — plutôt qu'un intervalle qui n'a pas ses jours.
    """
    return INF.block_ci_by_day(valeurs_par_jour)


# ══════════════════════════════════════════════════════════════════
#  LA SONDE
# ══════════════════════════════════════════════════════════════════

def sonder(root: pathlib.Path, fin: datetime, jours: int,
           avec_om: bool = True, ordre_inverse: bool = False,
           crier=print) -> dict:
    lignes: list[dict] = []
    ecarts_tot: list[float] = []
    ecarts_quant: list[float] = []
    ecarts_reste: list[float] = []
    #: Les balise-heures où les deux chaînes divergent de plus d'un
    #: km/h APRÈS arrondi — c'est-à-dire ce que l'arrondi n'explique
    #: pas. Nommées, pas comptées : une poignée de balises qui portent
    #: tout l'écart résiduel ne se lit pas dans une moyenne.
    gros: dict[str, dict] = {}
    #: L'écart de coordonnée entre les deux référentiels, balise-jour
    #: par balise-jour. ⛔ Cause NON NOMMÉE par l'audit, et la plus
    #: grosse du « reste ».
    coords: list[float] = []
    treillis_ok = treillis_n = 0
    noeuds_differents: dict[str, float] = {}
    jours_lus: list[str] = []
    manquants: list[str] = []
    gaps_om: dict[str, list[float]] = {"r2_moins_om": [], "agrume_moins_om": []}
    om_par_jour: dict[str, list[float]] = {}
    om_par_bande: dict[str, dict[str, list[float]]] = {}

    for k in range(jours - 1, -1, -1):
        j = fin - timedelta(days=k)
        cle = f"{j:%Y-%m-%d}"
        ag, r2, om, obs = lire_jour(root, j, avec_om)
        if not ag or not r2:
            manquants.append(f"{cle} (agrume {len(ag)} · arome_r2 {len(r2)})")
            continue
        jours_lus.append(cle)
        day_start_ms = int(j.replace(tzinfo=timezone.utc).timestamp()) * 1000
        for unit, row_r2 in r2.items():
            row_ag = ag.get(unit)
            o = obs.get(unit)
            if row_ag is None or not o:
                continue
            # Le contrôle du treillis tourne sur TOUTES les balises
            # présentes, notables ou non : c'est un contrôle de
            # géométrie, il n'a rien à voir avec l'appariement.
            en = ecart_de_noeud(row_r2)
            if en is not None:
                treillis_n += 1
                if not en[0]:
                    treillis_ok += 1
                else:
                    noeuds_differents[unit] = max(
                        noeuds_differents.get(unit, 0.0), en[1])
            d = decomposer(row_ag, row_r2, o, day_start_ms,
                           ordre_inverse=ordre_inverse)
            if d is None:
                continue
            d["jour"], d["unit"] = cle, unit
            meme, d_coord, cause = noeuds_lus(row_ag, row_r2)
            d["meme_noeud"] = meme
            d["cause_noeud"] = cause
            d["ecart_coord_km"] = d_coord
            d["noeud_differe"] = bool(en and en[0])
            d["ecart_noeud_km"] = en[1] if en else None
            coords.append(d_coord)
            lignes.append(d)
            t, q, re = ecarts_de_chaine(row_ag, row_r2, day_start_ms)
            ecarts_tot += t
            ecarts_quant += q
            ecarts_reste += re
            for v in re:
                if v > 1.0:
                    g = gros.setdefault(unit, {"n": 0, "max": 0.0,
                                               "cause_noeud": cause,
                                               "ecart_coord_km": d_coord})
                    g["n"] += 1
                    g["max"] = max(g["max"], v)
            # ── le contrôle croisé avec la chaîne Open-Meteo ──
            row_om = om.get(unit)
            if row_om is not None:
                t_om, s_om, d_om = serie_du_jour(row_om, day_start_ms)
                e_om = erreur(t_om, s_om, d_om, o, SC.MIN_HOURS_DAILY)
                if e_om is not None and e_om.med is not None:
                    g = d["med"]["err_r2"] - e_om.med
                    gaps_om["r2_moins_om"].append(g)
                    ga = d["med"]["err_agrume"] - e_om.med
                    gaps_om["agrume_moins_om"].append(ga)
                    om_par_jour.setdefault(cle, []).append(g)
                    # ⭐⭐ LE TEST QUI TRANCHE LE RÉFÉRENTIEL. `agrume`
                    # lit la coordonnée GELÉE, Open-Meteo est interrogée
                    # à la coordonnée VIVANTE (`collect.py`), et les
                    # DEUX sont notées contre les MÊMES observations,
                    # celles de la balise réelle. Si l'écart
                    # `agrume − AROME HD` grandit avec la distance entre
                    # les deux coordonnées, c'est que la gelée est
                    # périmée — et le sens de l'effet le dit sans
                    # qu'on ait à interroger un référentiel.
                    bande = ("0 — identique" if d_coord <= 0.001
                             else "≤ 0,5 km" if d_coord <= 0.5
                             else "≤ 2 km" if d_coord <= 2.0
                             else "> 2 km")
                    om_par_bande.setdefault(bande, {}).setdefault(
                        cle, []).append(ga)

    def par_jour(champ: str, cle: str = "med", filtre=None):
        out: dict[str, list[float]] = {}
        for l in lignes:
            if filtre is not None and not filtre(l):
                continue
            out.setdefault(l["jour"], []).append(l[cle][champ])
        return out

    res = {
        "fenetre": {"fin": f"{fin:%Y-%m-%d}", "jours_demandes": jours,
                    "jours_lus": jours_lus, "jours_absents": manquants},
        "source": SOURCE, "lead_h": LEAD_H,
        "ordre": "inverse" if ordre_inverse else "heures→arrondi→reste",
        "n_balise_jours": len(lignes),
        "n_balises": len({l["unit"] for l in lignes}),
        "treillis": {
            "n": treillis_n, "accord": treillis_ok,
            "taux_accord": treillis_ok / treillis_n if treillis_n else None,
            "balises_noeud_different": len(noeuds_differents),
            "ecart_max_km": max(noeuds_differents.values())
            if noeuds_differents else 0.0,
        },
        "chaine": {
            "n_balise_heures": len(ecarts_tot),
            "ecart_total": _resume(ecarts_tot),
            "ecart_arrondi_seul": _resume(ecarts_quant),
            "ecart_apres_arrondi": _resume(ecarts_reste),
            "n_au_dessus_1kmh": sum(1 for v in ecarts_reste if v > 1.0),
            "n_au_dessus_5kmh": sum(1 for v in ecarts_reste if v > 5.0),
            "balises_qui_divergent": dict(sorted(
                gros.items(), key=lambda kv: -kv[1]["max"])[:10]),
            "n_balises_qui_divergent": len(gros),
        },
        "heures": {
            "agrume_median": _mediane([l["n_heures_agrume"] for l in lignes]),
            "r2_median": _mediane([l["n_heures_r2"] for l in lignes]),
            "inter_median": _mediane([l["n_heures_inter"] for l in lignes]),
        },
        "residu_identite_max": max(
            (abs(l["med"]["residu_identite"]) for l in lignes), default=0.0),
    }
    for cle in ("med", "rms"):
        res[cle] = {champ: _terme(par_jour(champ, cle))
                    for champ in ("gap", "part_heures", "part_arrondi",
                                  "part_reste")}
    # ⛔ TROIS GROUPES, PAS DEUX. Un nœud différent a deux causes très
    # différentes — la tuile (défaut de la chaîne `arome_r2`) et la
    # coordonnée (défaut de RÉFÉRENTIEL, qui n'appartient à aucune des
    # deux chaînes). Les confondre attribuerait à `arome_r2` un écart
    # dont elle n'est pas responsable.
    res["reste_par_noeud"] = {
        cause: _terme(par_jour("part_reste", "med",
                               lambda l, c=cause: l["cause_noeud"] == c))
        for cause in ("identique", "coordonnee", "tuile")
    }
    res["coordonnees"] = {
        "n": len(coords),
        "n_differentes": sum(1 for d in coords if d > 0.001),
        "resume": _resume([d for d in coords if d > 0.001]),
        "par_cause": {c: sum(1 for l in lignes if l["cause_noeud"] == c)
                      for c in ("identique", "coordonnee", "tuile")},
    }
    if gaps_om["r2_moins_om"]:
        res["controle_open_meteo"] = {
            "n": len(gaps_om["r2_moins_om"]),
            "r2_moins_om_median": S.median(gaps_om["r2_moins_om"]),
            "agrume_moins_om_median": S.median(gaps_om["agrume_moins_om"]),
            "r2_moins_om_ic": _terme(om_par_jour),
            "agrume_moins_om_par_ecart_de_coordonnee": {
                b: _terme(v) for b, v in sorted(om_par_bande.items())},
        }
    return res


def _mediane(xs):
    return S.median([float(x) for x in xs]) if xs else None


def _resume(xs: list[float]) -> dict:
    if not xs:
        return {"n": 0}
    o = sorted(xs)
    n = len(o)
    return {"n": n, "mediane": o[n // 2], "moyenne": sum(o) / n,
            "p90": o[min(n - 1, int(n * 0.9))], "max": o[-1]}


def _terme(par_jour: dict) -> dict:
    """Un terme de la décomposition : sa médiane, sa MOYENNE, son IC (ou
    la raison de son absence), et TOUJOURS sa série journalière.

    ⛔⛔ LA MOYENNE N'EST PAS UN DOUBLON DE LA MÉDIANE, ET C'EST LE PIÈGE
    CENTRAL DE CE LOT. L'identité `gap = heures + arrondi + reste` est
    vraie SUR CHAQUE BALISE-JOUR. Elle ne survit PAS à une médiane : la
    médiane d'une somme n'est pas la somme des médianes. Mesuré le
    27/08 sur la production — médianes +0,127 / +0,000 / +0,043 /
    +0,000 : les trois parts « expliquent » 34 % d'un total qu'elles
    somment pourtant exactement, balise-jour par balise-jour.
    ⇒ Les PARTS EN POURCENTAGE se lisent sur la MOYENNE, seule
    grandeur additive ; la médiane dit ce qu'une journée TYPIQUE voit.
    Publier l'une sans l'autre, c'est publier une part fausse.
    """
    ci = _ci(par_jour)
    vals = [x for v in par_jour.values() for x in v if S._finite(x)]
    return {
        "mediane": ci.median,
        "moyenne": (sum(vals) / len(vals)) if vals else None,
        "ci_low": ci.ci_low, "ci_high": ci.ci_high,
        "n_pairs": ci.n_pairs, "n_days": ci.n_days,
        "block_days": ci.block_days, "reason": ci.reason,
        "p_value": ci.p_value, "separates": ci.separates,
        "par_jour": {j: {"n": len(v), "mediane": S.median(v),
                         "moyenne": sum(v) / len(v) if v else None}
                     for j, v in sorted(par_jour.items())},
    }


# ══════════════════════════════════════════════════════════════════
#  LE COÛT D'UNE TUILE EN DÉCIMAL — mesuré sur une tuile RÉELLE
# ══════════════════════════════════════════════════════════════════

#: Un générateur congruentiel, uniquement pour FABRIQUER des décimales.
#: ⛔ Aucun chiffre fabriqué ne sort de cette fonction : seule la TAILLE
#: du fichier en sort. Une décimale cyclique (0,1,2,…) se comprimerait
#: bien mieux qu'une vraie, et le coût gzip annoncé serait faux dans le
#: sens qui arrange. Un tirage uniforme est le modèle honnête du dernier
#: chiffre d'une vitesse de vent.
def _chiffres(n: int, graine: int = 20260827):
    s = graine & 0xFFFFFFFF
    for _ in range(n):
        s = (1103515245 * s + 12345) & 0x7FFFFFFF
        yield (s >> 16) % 10


def cout_tuile_decimale(tuile: tuple[int, int] = (44, 4),
                        crier=print) -> dict:
    """Lit UNE tuile `arome/sol` réelle et pèse ce que coûterait le
    dixième de km/h. Lecture seule, une opération de classe B.

    ⚠️ Ce qui est mesuré est la TAILLE, jamais la valeur : les décimales
    sont fabriquées (voir `_chiffres`). Le rapport le dit là où il
    publie le chiffre.
    """
    import gzip as _gz                                       # noqa: PLC0415

    from arome_fcst import (BUCKET_SUPABASE_DEFAUT,           # noqa: PLC0415
                            BUCKET_SUPABASE_ENV, PREFIXE_SOL, _ouvrir_store)
    from r2_lecture import bucket_r2                          # noqa: PLC0415

    bucket, prefixe, Storage = _ouvrir_store()
    crier(f"  lecture d'UNE tuile réelle : bucket « {bucket} », "
          f"identifiants {prefixe}*")
    with bucket_r2(bucket, prefixe):
        store = Storage("sonde-l4", BUCKET_SUPABASE_ENV,
                        BUCKET_SUPABASE_DEFAUT)
        cle = f"{PREFIXE_SOL}{tuile[0]}_{tuile[1]}.json"
        brut = store.get(cle)
    if not brut:
        raise SystemExit(f"tuile {cle} absente — en choisir une autre "
                         f"(--tuile 46,6)")

    d = json.loads(brut)
    # ⚠️ La référence n'est PAS `len(brut)` : l'objet stocké peut porter
    # une mise en forme (espaces, ordre) qui n'a rien à voir avec la
    # précision. On re-sérialise les DEUX côtés avec les mêmes
    # séparateurs, sinon on mesurerait le style d'écriture.
    entier = json.dumps(d, separators=(",", ":")).encode("utf-8")
    n_pts = len(d["points"])
    n_pas = len(d.get("times") or [])
    gen = _chiffres(n_pts * max(1, n_pas))
    n_vals = 0
    for p in d["points"]:
        sp = p.get("speed") or []
        p["speed"] = [None if s is None else round(s + next(gen) / 10.0, 1)
                      for s in sp]
        n_vals += sum(1 for s in sp if s is not None)
    decimal = json.dumps(d, separators=(",", ":")).encode("utf-8")

    # ── LE SECOND COÛT, celui de la cause DOMINANTE ─────────────────
    # `keep_step()` ne garde qu'une échéance sur trois entre 22 et 04
    # UTC. C'est CE trou qui pèse le plus lourd dans le plancher (63 %
    # de la moyenne du gap, mesuré) — bien plus que l'arrondi (27 %).
    # Son coût se déduit de la tuile elle-même : le poids par échéance,
    # multiplié par les échéances absentes de l'horizon.
    heures = sorted({int(x[-5:-3]) for x in (d.get("times") or [])}
                    ) if d.get("times") else []
    n_manquantes = 0
    if n_pas >= 2:
        from datetime import datetime as _dt                  # noqa: PLC0415
        ts = [_dt.strptime(x, "%Y-%m-%dT%H:%M") for x in d["times"]]
        span = int((ts[-1] - ts[0]).total_seconds() // 3600) + 1
        n_manquantes = max(0, span - n_pas)

    #: Le vrai plafond du bucket, celui qui a motivé l'arrondi entier le
    #: 30/07 : `arome/sol` pèse 539 à 571 Mo par run selon qu'il vente
    #: ou pas (mesuré, cité par `_ms`), pour 63 tuiles `sol`.
    return {
        "echeances_manquantes": n_manquantes,
        "horizon_h": n_pas + n_manquantes,
        "tuile": f"{tuile[0]}_{tuile[1]}", "points": n_pts,
        "echeances": n_pas, "valeurs_vitesse": n_vals,
        "octets_stockes": len(brut),
        "entier_brut": len(entier), "entier_gz": len(_gz.compress(entier, 6)),
        "decimal_brut": len(decimal),
        "decimal_gz": len(_gz.compress(decimal, 6)),
    }


# ══════════════════════════════════════════════════════════════════
#  LE RAPPORT
# ══════════════════════════════════════════════════════════════════

def _f(x, n=4):
    return "—" if x is None else f"{x:+.{n}f}"


def _ligne_terme(nom: str, t: dict, total: float | None) -> str:
    """⛔ LA PART SE LIT SUR LA MOYENNE. Voir le pavé de `_terme` : la
    médiane d'une somme n'est pas la somme des médianes, et une part
    calculée sur des médianes ne fait pas 100 % — elle fait ce qu'elle
    veut, ce qui est pire, parce qu'elle reste lisible."""
    part = ("—" if not total or t.get("moyenne") is None
            else f"{100 * t['moyenne'] / total:5.1f} %")
    ic = ("—" if t["ci_low"] is None
          else f"[{_f(t['ci_low'])} ; {_f(t['ci_high'])}]")
    return (f"  {nom:<32s} {_f(t['mediane']):>9s} {_f(t.get('moyenne')):>9s}"
            f"  {ic:>22s} {part:>7s}  {t['reason']}")


def rapport(r: dict, cout: dict | None = None) -> str:
    L: list[str] = []
    a = L.append
    f = r["fenetre"]
    a("═" * 72)
    a("  SONDE DE CHAÎNE `arome_r2` — décomposition du plancher (lot L4)")
    a("═" * 72)
    a(f"  fenêtre      : {', '.join(f['jours_lus']) or '—'}"
      f"  ({len(f['jours_lus'])} jour(s))")
    if f["jours_absents"]:
        a(f"  jours écartés: {' · '.join(f['jours_absents'])}")
    a(f"  population   : {r['n_balise_jours']} balise-jours · "
      f"{r['n_balises']} balises · source {r['source']} · lead +{r['lead_h']} h")
    a(f"  ordre des termes : {r['ordre']}")
    a("")
    a("── 1. LE TREILLIS ET LES NŒUDS (géométrie, aucune observation) ──")
    t = r["treillis"]
    a(f"  lignes contrôlées                : {t['n']}")
    a(f"  distance archivée = distance au   "
      f"plus proche nœud 0,01° : {t['accord']} "
      f"({100 * (t['taux_accord'] or 0):.1f} %)")
    a(f"  balises dont la TUILE a imposé le nœud : "
      f"{t['balises_noeud_different']} "
      f"(écart max {t['ecart_max_km']:.3f} km)")
    co = r["coordonnees"]
    a("")
    a("  ⛔ LES DEUX CHAÎNES PARTENT-ELLES DE LA MÊME COORDONNÉE ?")
    a(f"     balise-jours dont les deux référentiels DIVERGENT : "
      f"{co['n_differentes']} / {co['n']}"
      + (f"  (méd {co['resume']['mediane']:.3f} · "
         f"p90 {co['resume']['p90']:.3f} · max {co['resume']['max']:.3f} km)"
         if co["resume"].get("n") else ""))
    a(f"     nœud finalement lu : identique {co['par_cause']['identique']} · "
      f"différent par la COORDONNÉE {co['par_cause']['coordonnee']} · "
      f"par la TUILE {co['par_cause']['tuile']}")
    a("     ⓘ `agrume_fcst` lit la liste GELÉE (`freeze_balises`),")
    a("       `arome_fcst` les six référentiels VIVANTS de `collect.py`.")
    a("  ⓘ un taux d'accord qui s'effondre ne dit pas « cause (b) » : il")
    a("    dit que le treillis a bougé. Le lire AVANT le reste.")
    a("")
    a("── 2. CE QUE LES DEUX CHAÎNES LISENT (aucune observation) ──")
    c = r["chaine"]
    for nom, cle in (("‖v(arome_r2) − v(agrume)‖", "ecart_total"),
                     ("dont l'arrondi entier seul", "ecart_arrondi_seul"),
                     ("CE QUI RESTE après arrondi", "ecart_apres_arrondi")):
        e = c[cle]
        if e.get("n"):
            a(f"  {nom:<28s} n={e['n']:<7d} méd {e['mediane']:.4f} · "
              f"moy {e['moyenne']:.4f} · p90 {e['p90']:.4f} · "
              f"max {e['max']:.4f} km/h")
    a(f"  balise-heures au-dessus de 1 km/h APRÈS arrondi : "
      f"{c['n_au_dessus_1kmh']} "
      f"({100 * c['n_au_dessus_1kmh'] / max(1, c['n_balise_heures']):.2f} %)"
      f" · au-dessus de 5 : {c['n_au_dessus_5kmh']}")
    a(f"  … portées par {c['n_balises_qui_divergent']} balises. Les pires :")
    for u, g in list(c["balises_qui_divergent"].items())[:5]:
        a(f"      {u:<22s} {g['n']:>3d} heures · max {g['max']:6.2f} km/h · "
          f"nœud {g['cause_noeud']:<11s} · "
          f"référentiels à {g['ecart_coord_km']:.3f} km")
    h = r["heures"]
    a(f"  heures notées / journée : agrume {h['agrume_median']:.0f} · "
      f"arome_r2 {h['r2_median']:.0f} · communes {h['inter_median']:.0f}")
    a("")
    a("── 3. L'ÉCART D'ERREUR ET SA DÉCOMPOSITION ──")
    for cle, titre in (("med", "err_vec_med (la colonne de l'audit)"),
                       ("rms", "err_vec_rms (la colonne du duel L1)")):
        d = r[cle]
        # ⛔ Le dénominateur est la MOYENNE du gap, pas sa médiane :
        # diviser une moyenne par une médiane ferait une part qui n'est
        # ni l'une ni l'autre, et qui resterait lisible.
        tot = d["gap"]["moyenne"]
        a(f"  ▸ {titre}")
        a(f"  {'terme':<32s} {'médiane':>9s} {'moyenne':>9s}"
          f"  {'IC95j (médiane)':>22s} {'part':>7s}  raison")
        a(_ligne_terme("GAP TOTAL  (r2 − agrume)", d["gap"], tot))
        a(_ligne_terme("(c) heures manquantes", d["part_heures"], tot))
        a(_ligne_terme("(a) arrondi entier des tuiles", d["part_arrondi"], tot))
        a(_ligne_terme("(d) reste", d["part_reste"], tot))
        a("")
    a("  ⚠️ la PART se lit sur la MOYENNE — seule grandeur additive. Les")
    a("     médianes ne somment PAS au gap, et ce n'est pas un défaut :")
    a("     c'est ce qu'est une médiane. Elles disent la journée typique.")
    a(f"  résidu d'identité maximal : {r['residu_identite_max']:.2e} km/h")
    a("    (les trois parts SOMMENT au gap ; ce résidu est le contrôle,")
    a("     pas une approximation — s'il grossit, H_∩ ≠ H_r2.)")
    a("")
    a("── 4. LE RESTE, PAR GROUPE DE NŒUD (la cause (b), isolée) ──")
    for nom, cle in (("MÊME nœud lu", "identique"),
                     ("nœud ≠ par la COORDONNÉE", "coordonnee"),
                     ("nœud ≠ par la TUILE", "tuile")):
        t = r["reste_par_noeud"][cle]
        a(f"  {nom:<26s} n={t['n_pairs']:<6d} méd {_f(t['mediane'])} · "
          f"moy {_f(t.get('moyenne'))} km/h  {t['reason']}")
    a("  ⛔ C'EST LA LIGNE QUI TRANCHE. Si le reste est NUL quand les deux")
    a("    chaînes lisent le même nœud, alors il n'y a rien d'autre à")
    a("    expliquer : tout le « reste » est du point lu, pas de la")
    a("    chaîne `arome_r2`.")
    if "controle_open_meteo" in r:
        o = r["controle_open_meteo"]
        a("")
        a("── 5. CONTRÔLE CROISÉ avec la chaîne Open-Meteo ──")
        a(f"  n = {o['n']} balise-jours · "
          f"arome_r2 − AROME HD : {_f(o['r2_moins_om_median'])} km/h · "
          f"agrume − AROME HD : {_f(o['agrume_moins_om_median'])} km/h")
        a("  ⓘ c'est le chiffre de l'audit §0.3 (+0,165) qu'on doit")
        a("    retrouver ici — s'il ne revient pas, c'est la sonde qui a tort.")
        bandes = o.get("agrume_moins_om_par_ecart_de_coordonnee") or {}
        if bandes:
            a("")
            a("  ⭐⭐ LAQUELLE DES DEUX COORDONNÉES EST LA BONNE ?")
            a("     `agrume` lit la GELÉE, Open-Meteo la VIVANTE, les deux")
            a("     contre les MÊMES observations. Si l'écart grandit avec la")
            a("     distance, c'est la gelée qui est périmée.")
            a(f"     {'écart de coordonnée':<20s} {'n':>5s} "
              f"{'méd(agrume − AROME HD)':>24s} {'moyenne':>10s}")
            for b, v in bandes.items():
                a(f"     {b:<20s} {v['n_pairs']:>5d} "
                  f"{_f(v['mediane']):>24s} {_f(v.get('moyenne')):>10s}")
    if cout:
        a("")
        a("── 6. LE COÛT D'UNE TUILE EN DÉCIMAL (tuile RÉELLE) ──")
        a(f"  tuile {cout['tuile']} · {cout['points']} points × "
          f"{cout['echeances']} échéances · "
          f"{cout['valeurs_vitesse']} vitesses")
        a(f"  entier  : {cout['entier_brut'] / 1e6:.2f} Mo brut · "
          f"{cout['entier_gz'] / 1e6:.2f} Mo gzip")
        a(f"  décimal : {cout['decimal_brut'] / 1e6:.2f} Mo brut · "
          f"{cout['decimal_gz'] / 1e6:.2f} Mo gzip")
        sb = 100 * (cout["decimal_brut"] / cout["entier_brut"] - 1)
        sg = 100 * (cout["decimal_gz"] / cout["entier_gz"] - 1)
        a(f"  surcoût : {sb:+.1f} % brut · {sg:+.1f} % gzip")
        if cout.get("echeances_manquantes"):
            par_ech = cout["entier_brut"] / max(1, cout["echeances"])
            a("")
            a(f"  ⭐ ET L'AUTRE COÛT, celui de la cause DOMINANTE : la tuile")
            a(f"     porte {cout['echeances']} échéances pour un horizon de "
              f"{cout['horizon_h']} h — {cout['echeances_manquantes']} "
              f"manquent (`keep_step`, 22-04 UTC).")
            a(f"     les rétablir coûterait ~"
              f"{cout['echeances_manquantes'] * par_ech / 1e6:.2f} Mo par "
              f"tuile, soit {100 * cout['echeances_manquantes'] / cout['echeances']:+.0f} %"
              f" — à comparer aux {sb:+.1f} % du décimal.")
        a("  ⚠️ les décimales sont FABRIQUÉES (tirage uniforme) : c'est la")
        a("     TAILLE qui est mesurée, jamais une valeur de vent.")
    a("═" * 72)
    return "\n".join(L)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default="/var/lib/bw-model-verif")
    p.add_argument("--fin", default=None,
                   help="dernier jour lu (défaut : hier)")
    p.add_argument("--jours", type=int, default=5)
    p.add_argument("--sans-om", action="store_true",
                   help="sauter le contrôle croisé Open-Meteo (flux lourd)")
    p.add_argument("--ordre-inverse", action="store_true",
                   help="arrondi d'abord, heures ensuite — mesure les "
                        "interactions")
    p.add_argument("--cout-tuile", action="store_true",
                   help="lire UNE tuile réelle et peser le décimal")
    p.add_argument("--tuile", default="44,4")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    fin = (datetime.strptime(a.fin, "%Y-%m-%d") if a.fin
           else datetime.now(timezone.utc).replace(tzinfo=None)
           - timedelta(days=1))
    fin = fin.replace(hour=0, minute=0, second=0, microsecond=0)

    r = sonder(pathlib.Path(a.root), fin, a.jours,
               avec_om=not a.sans_om, ordre_inverse=a.ordre_inverse,
               crier=(lambda *_a, **_k: None) if a.json else print)
    cout = None
    if a.cout_tuile:
        tl, tn = a.tuile.split(",")
        cout = cout_tuile_decimale((int(tl), int(tn)),
                                   crier=(lambda *_a, **_k: None)
                                   if a.json else print)
    if a.json:
        print(json.dumps({"sonde": r, "cout_tuile": cout},
                         ensure_ascii=False, indent=1))
    else:
        print(rapport(r, cout))
    return 0


if __name__ == "__main__":
    sys.exit(main())
