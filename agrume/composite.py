#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/composite.py — étape 9 : le composite temporel AROME + PI
#                                                        (10/08/2026)
#
#  Sur 0–6 h, AROME-PI apporte 4× la résolution temporelle d'AROME, mais
#  seulement 6 de ses 25 niveaux. Ce module fabrique un profil qui a les
#  DEUX : les 25 niveaux d'AROME, au pas de 15 min de PI.
#
#  ── LE §4.3 DEMANDAIT COMMENT INVENTER UNE VALEUR QU'ON POSSÉDAIT ────
#  Le prompt de lot posait la question : « aux échéances non rondes,
#  garder le dernier Δ connu, ou l'interpoler en τ ? » — au motif que le
#  delta ne serait calculable qu'aux heures rondes.
#
#  **C'est faux.** Aux niveaux communs, PI est publié aux 25 échéances,
#  `:15` et `:45` compris. Le trou n'est pas sur Δ, il est sur AROME.
#  Δ est donc CALCULÉ partout, jamais propagé en τ, et la question se
#  dissout. Démonstration complète dans
#  `claude/lot-h-etape-9-arbitrage-echeances-non-rondes-10-08.md`.
#
#  ── LES DEUX CHIFFRES QUI JUSTIFIENT CE FICHIER, MESURÉS ─────────────
#      Δ = PI − AROME ......................... 0,76 m/s (méd), q90 1,78
#      erreur d'interpolation d'AROME en τ .... 0,31 m/s (méd), q90 1,08
#
#  **Δ vaut 2,5 fois le bruit qu'on introduit en fabriquant la
#  référence.** C'est la seule chose qui rende ce composite légitime : si
#  le rapport avait été inverse, on aurait servi de l'artefact avec la
#  tête d'une correction. Et Δ vaut 24 à 33 % du vent d'AROME lui-même —
#  PI ne retouche pas à la marge.
#
#  ⚠️ LE CHIFFRE QUI DÉMENT L'INTUITION : l'erreur d'interpolation ne
#  décroît PAS comme le carré du pas. Rapport mesuré err(4 h)/err(2 h) =
#  1,43 à 1,84, jamais 4 — le champ AROME n'est pas lisse en τ à
#  l'échelle de l'heure. La loi en H² aurait sous-estimé l'erreur d'un
#  facteur 2,2 à 3,0.
#
#  ── CE QUE CE MODULE NE FAIT PAS ─────────────────────────────────────
#  ⛔ Il n'invente RIEN au-dessus de 1 000 m/sol. Δ y est éteint, donc le
#  composite y vaut AROME interpolé — et la réponse le DIT, par niveau
#  (`resolutionTemporelleMin`). *On ne refuse pas de servir un point à
#  15 min à 3 000 m ; on refuse de laisser croire qu'il a été calculé à
#  15 min.* Même discipline que le drapeau `escalier` du transect.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from domaine import NIVEAUX_H_0025  # noqa: E402
from pi import ECHEANCES_MIN, NIVEAUX_DELTA, NIVEAUX_PI  # noqa: E402


class Abort(Exception):
    pass


# ── La pondération en échéance ────────────────────────────────────────
# ⛔ CORRECTION DU §4.3 : il écrivait « `w_PI` = 1 jusqu'à 4 h, rampe
# vers 0 entre 4 et 7 h ». **Mais PI s'arrête à 6 h** (§2 du lot). Entre
# 6 et 7 h la formule réclamait un PI qui n'existe pas — la rampe aurait
# pondéré du vide. Elle finit donc à 6 h.
TAU_PLEIN_MIN = 240        # 4 h : PI seul maître
TAU_FIN_MIN = 360          # 6 h : horizon de PI, w = 0

# ── L'extinction verticale de Δ ───────────────────────────────────────
# Δ n'est mesuré qu'aux niveaux de PI, dont le plus haut est 500 m. Au
# dessus, on ne sait rien : l'extinction linéaire 500 → 1 000 m est une
# CONVENTION, pas une mesure, et elle est écrite ici pour qu'on sache
# où la contester.
# ⚠️ Conséquence à publier, pas à taire : au-dessus de 1 000 m/sol le
# composite n'a AUCUNE information à 15 min.
Z_EXTINCTION_DEBUT = 500
Z_EXTINCTION_FIN = 1000

# ⚠️ Erreur d'interpolation d'AROME entre deux heures, MESURÉE (médiane,
# m/s) — sert à publier l'incertitude là où Δ ne corrige plus rien.
# Extrapolée depuis AROME par la loi empirique en H^α (α mesuré 0,5–0,9),
# validée contre PI à ±14 % là où PI existe.
ERREUR_INTERP_PAR_NIVEAU = {
    20: 0.27, 50: 0.31, 100: 0.31, 250: 0.31, 500: 0.34,
    1000: 0.34, 1500: 0.38, 2000: 0.43, 3000: 0.59,
}


def poids_pi(minute):
    """`w_PI(τ)` — 1 jusqu'à 4 h, rampe linéaire vers 0 à 6 h.

    ⚠️ C⁰ et non C¹ : il y a un coude à 4 h et un à 6 h. C'est assumé —
    un lissage C¹ demanderait de choisir une forme, et rien ne la
    mesure. Un coude visible vaut mieux qu'une courbe inventée.
    """
    if minute <= TAU_PLEIN_MIN:
        return 1.0
    if minute >= TAU_FIN_MIN:
        return 0.0
    return (TAU_FIN_MIN - minute) / (TAU_FIN_MIN - TAU_PLEIN_MIN)


def arome_interpole(serie_horaire, steps_h, minute):
    """AROME à une échéance NON RONDE, par interpolation linéaire en τ.

    `serie_horaire` : tableau (…, nb_steps) ; `steps_h` : les échéances
    horaires correspondantes ; `minute` : l'instant voulu, en minutes
    depuis le début du run PI, DÉJÀ converti en échéance AROME par
    l'appelant.

    ⚠️⚠️ SUR u ET v, JAMAIS SUR L'ANGLE. Interpoler une direction qui
    passe de 350° à 010° donnerait 180° — le vent exactement à l'opposé,
    et rien ne lèverait. C'est la règle du lot, et elle vaut ici comme
    partout ailleurs.

    ⚠️ Cette valeur est FABRIQUÉE. Elle coûte 0,31 m/s en médiane et
    1,08 au q90 (mesuré sur PI, qui est au pas de 15 min). Aux niveaux
    où Δ existe, ce coût s'annule EXACTEMENT — le composite y reproduit
    PI. Au-dessus de 1 000 m il ne s'annule pas du tout.
    """
    h = minute / 60.0
    steps = np.asarray(steps_h, dtype=np.float64)
    if h < steps[0] or h > steps[-1]:
        raise Abort(f"échéance {h:.2f} h hors de la couverture AROME "
                    f"({steps[0]:.0f}–{steps[-1]:.0f} h) — on ne "
                    f"l'extrapole PAS")
    k = int(np.searchsorted(steps, h, side="right")) - 1
    if k >= len(steps) - 1:
        return np.asarray(serie_horaire[..., -1], dtype=np.float64)
    t0, t1 = steps[k], steps[k + 1]
    f = 0.0 if t1 == t0 else (h - t0) / (t1 - t0)
    a = np.asarray(serie_horaire[..., k], dtype=np.float64)
    b = np.asarray(serie_horaire[..., k + 1], dtype=np.float64)
    return (1.0 - f) * a + f * b


def etendre_delta(delta_aux_niveaux_pi, niveaux_cibles=NIVEAUX_H_0025,
                  niveaux_source=NIVEAUX_DELTA):
    """Δ mesuré sur 5 niveaux → Δ sur les 25 niveaux d'AROME.

    Trois régimes, et un seul est une mesure :

      z < 20 m           Δ(20) CONSTANT — extension, pas mesure.
                         ⚠️ Le 10 m est le seul niveau concerné. Mettre
                         0 y créerait une marche au RAS DU SOL, c'est-à-
                         dire exactement là où vit le pilote. ⓘ Δ y est
                         calculable en principe (PI sert le 10 m,
                         mesuré) mais côté AROME `u`/`v` n'existent qu'à
                         partir de 20 m : le 10 m viendrait des champs
                         dédiés `10u`/`10v`, une AUTRE famille de champ.
                         Rien ne dit que ce soit le même diagnostic —
                         c'est une question à mesurer, pas à trancher.
      20 → 500 m         interpolation linéaire entre niveaux PI. Mesure.
      500 → 1000 m       extinction linéaire vers 0. CONVENTION.
      > 1000 m           Δ = 0. Le composite y vaut AROME interpolé.

    `delta_aux_niveaux_pi` : (…, nb_niveaux_source), aligné sur
    `niveaux_source`. Renvoie (…, nb_niveaux_cibles).
    """
    src = np.asarray(niveaux_source, dtype=np.float64)
    d = np.asarray(delta_aux_niveaux_pi, dtype=np.float64)
    if d.shape[-1] != len(src):
        raise Abort(f"Δ a {d.shape[-1]} niveaux pour {len(src)} attendus")
    sortie = np.zeros(d.shape[:-1] + (len(niveaux_cibles),), dtype=np.float64)
    haut = float(src[-1])
    for k, z in enumerate(niveaux_cibles):
        if z <= src[0]:
            v = d[..., 0]                                  # extension basse
        elif z <= haut:
            v = _interp_lineaire(d, src, float(z))         # mesure
        elif z < Z_EXTINCTION_FIN:
            # Extinction depuis la valeur du niveau le plus haut de PI.
            reste = (Z_EXTINCTION_FIN - float(z)) / (
                Z_EXTINCTION_FIN - Z_EXTINCTION_DEBUT)
            v = d[..., -1] * max(0.0, min(1.0, reste))
        else:
            v = np.zeros_like(d[..., -1])
        sortie[..., k] = v
    return sortie


def _interp_lineaire(d, src, z):
    j = int(np.searchsorted(src, z, side="right")) - 1
    j = max(0, min(j, len(src) - 2))
    z0, z1 = src[j], src[j + 1]
    f = 0.0 if z1 == z0 else (z - z0) / (z1 - z0)
    return (1.0 - f) * d[..., j] + f * d[..., j + 1]


def resolution_temporelle(z):
    """La résolution temporelle RÉELLE à ce niveau, en minutes, et
    l'incertitude qui va avec.

    ⚠️ C'EST LE CHAMP LE PLUS IMPORTANT DE LA RÉPONSE. Le composite sert
    25 échéances à TOUS les niveaux, mais seule la tranche basse a été
    OBSERVÉE à 15 min. Au-dessus de 1 000 m/sol, les points à `:15`,
    `:30`, `:45` sont de l'AROME horaire interpolé — et l'erreur y vaut
    0,34 m/s en médiane, 0,59 à 3 000 m.

    *On ne refuse pas de servir. On refuse de laisser croire.*
    """
    if z <= Z_EXTINCTION_DEBUT:
        regime, res = "observée (PI)", 15
    elif z < Z_EXTINCTION_FIN:
        regime, res = "dégradée (Δ s'éteint)", 15
    else:
        regime, res = "interpolée (AROME horaire)", 60
    # Erreur d'interpolation : nulle là où Δ la compense exactement.
    niveaux = sorted(ERREUR_INTERP_PAR_NIVEAU)
    proche = min(niveaux, key=lambda n: abs(n - z))
    err = 0.0 if z <= Z_EXTINCTION_DEBUT else ERREUR_INTERP_PAR_NIVEAU[proche]
    return dict(resolutionTemporelleMin=res, regime=regime,
                erreurInterpolationMs=round(err, 2))


def composer(pi_uv, arome_uv, steps_arome_h, decalage_min=0,
             niveaux_cibles=NIVEAUX_H_0025):
    """Le composite, sur les 25 échéances de PI et les 25 niveaux d'AROME.

        pi_uv        : (2, nb_niveaux_pi, 25, …)   u/v de PI
        arome_uv     : (2, nb_niveaux_arome, nb_steps, …)  u/v d'AROME
        steps_arome_h: les échéances horaires d'AROME
        decalage_min : minutes entre le début du run AROME et celui de PI

    Renvoie (composite, diagnostic) où `composite` a la forme
    (2, len(niveaux_cibles), 25, …).

    ── L'INVARIANT, ET C'EST LE CRITÈRE D'ACCEPTATION DE L'ÉTAPE ───────
    ✅ Aux niveaux communs et tant que `w_PI = 1` (τ ≤ 4 h) :
           composite(t, z) == PI(t, z)   aux 25 échéances
    parce que les deux termes se compensent exactement :
           AROME_interp + (PI − AROME_interp) = PI
    ⚠️ Appliquer le MÊME arrondi de publication des deux côtés pour le
    vérifier — c'est le piège qui a rendu un 0/125 parfaitement crédible
    à l'étape 8.
    """
    pi_uv = np.asarray(pi_uv, dtype=np.float64)
    arome_uv = np.asarray(arome_uv, dtype=np.float64)
    if pi_uv.shape[0] != 2 or arome_uv.shape[0] != 2:
        raise Abort("u et v attendus en première dimension, dans cet ordre")

    i_delta = [NIVEAUX_PI.index(z) for z in NIVEAUX_DELTA]
    i_arome_delta = [list(niveaux_cibles).index(z) for z in NIVEAUX_DELTA]
    forme = (2, len(niveaux_cibles), len(ECHEANCES_MIN)) + pi_uv.shape[3:]
    sortie = np.full(forme, np.nan, dtype=np.float64)
    poids = []

    # ⚠️ `arome_interpole` travaille sur la DERNIÈRE dimension. Ici l'axe
    # des échéances est en position 2, suivi des points. Sans ce
    # `moveaxis`, numpy diffuserait « niveaux × points » contre
    # « niveaux × échéances » — et sur un jeu où les deux comptes se
    # trouveraient égaux, ça passerait SANS LEVER en rendant n'importe
    # quoi. *Constaté au banc, le 10/08.*
    arome_par_step = np.moveaxis(arome_uv, 2, -1)

    for it, minute in enumerate(ECHEANCES_MIN):
        # AROME interpolé à CETTE minute, sur TOUS les niveaux.
        ar = np.stack([arome_interpole(arome_par_step[c], steps_arome_h,
                                       minute + decalage_min)
                       for c in (0, 1)])
        # Δ aux 5 niveaux communs — CALCULÉ, jamais propagé en τ.
        delta = np.stack([pi_uv[c][i_delta, it] - ar[c][i_arome_delta]
                          for c in (0, 1)])
        # (2, 5, …) → (2, …, 5) pour `etendre_delta`, puis retour.
        delta = np.moveaxis(delta, 1, -1)
        etendu = np.moveaxis(etendre_delta(delta, niveaux_cibles), -1, 1)
        w = poids_pi(minute)
        poids.append(w)
        sortie[:, :, it] = ar + w * etendu

    diagnostic = dict(
        echeances_min=list(ECHEANCES_MIN),
        poids_pi=[round(w, 4) for w in poids],
        niveaux_delta_mesure=list(NIVEAUX_DELTA),
        niveaux=[dict(niveauMSol=int(z), **resolution_temporelle(z))
                 for z in niveaux_cibles],
        conventions=dict(
            interpolation="linéaire en τ sur u et v, JAMAIS sur l'angle",
            delta="calculé aux 25 échéances, jamais propagé en τ",
            extinction=(f"linéaire de {Z_EXTINCTION_DEBUT} à "
                        f"{Z_EXTINCTION_FIN} m/sol — CONVENTION, pas mesure"),
            sous_20m="Δ(20 m) étendu constant — extension, pas mesure",
            rampe=(f"w_PI = 1 jusqu'à {TAU_PLEIN_MIN // 60} h, 0 à "
                   f"{TAU_FIN_MIN // 60} h (l'horizon de PI, pas 7 h)"),
        ),
        mesures=dict(
            delta_pi_arome_median_ms=0.76,
            delta_pi_arome_q90_ms=1.78,
            erreur_interpolation_median_ms=0.31,
            rapport="Δ vaut 2,5 fois l'erreur d'interpolation",
        ),
    )
    return sortie, diagnostic
