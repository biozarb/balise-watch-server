#!/usr/bin/env python3
"""inference.py — ce qui décide si un écart entre deux modèles est réel.

    Lot G, session 09/08/2026.
    cf. PWA/web/CONCEPTION_SCORE_MODELES_06-08.md §8.4, §16.1, §16.3.

═══ POURQUOI CE FICHIER N'A PAS DE JUMEAU TYPESCRIPT ═══

`scoring.py` est un PORTAGE : chacune de ses fonctions existe aussi
dans `src/lib/verifScore.ts`, et `test_scoring.py` compare les deux
terme à terme parce qu'une duplication non vérifiée diverge toujours.

Ce fichier-ci n'est pas une duplication. Rien de ce qu'il contient
n'existe côté TS, et rien ne doit y être porté : la PWA ne calcule
pas d'intervalle de confiance, elle lit un JSON déjà noté. Y ajouter
un jumeau créerait exactement le problème que le banc de parité
existe pour surveiller.

⚠️ COROLLAIRE : ne JAMAIS déplacer une fonction d'ici vers
`scoring.py` sans lui écrire son pendant TS le même jour. Le banc de
parité ne se plaindrait pas — il ne compare que ce qu'on lui donne —
et la garantie « tout ce qui est dans scoring.py est vérifié des deux
côtés » deviendrait fausse en silence.

═══ LES TROIS DÉFAUTS QUE CE FICHIER CORRIGE ═══

1. `bootstrap_ci` est UNAIRE. Il rend l'IC de la médiane d'UN modèle.
   Comparer deux intervalles unaires n'est pas un test : deux IC qui
   se recouvrent ne prouvent pas l'égalité (ils peuvent se recouvrir
   alors que la différence appariée est nettement non nulle), et deux
   IC disjoints exagèrent la différence. Le bon objet est l'IC de la
   DIFFÉRENCE APPARIÉE — A moins B sur les mêmes balises et les mêmes
   jours, ce qui élimine d'un coup l'effet « site » et l'effet
   « journée », qui sont tous deux énormes devant l'effet « modèle ».

2. Le rééchantillonnage est i.i.d. L'en-tête de `bootstrap_ci` dit
   déjà que l'unité doit être la balise-jour et pas l'heure. C'est
   vrai et insuffisant : deux journées consécutives ne sont pas
   indépendantes non plus — une situation synoptique dure trois
   jours. Tirer des balise-jours indépendamment fabrique donc des
   intervalles trop étroits, donc de faux gagnants. D'où le
   rééchantillonnage par BLOCS DE JOURS CONSÉCUTIFS.

3. Le quorum sec (`REGIME_MIN_OCCURRENCES = 8`) traite une case à 8
   observations comme une case à 800, et une case à 7 comme
   inexistante. Le rétrécissement vers le parent (partial pooling)
   remplace cette falaise par une pente — à condition de PUBLIER LE
   POIDS EMPRUNTÉ : un chiffre à 80 % emprunté au massif n'est pas un
   chiffre de vallée, et l'afficher sans le dire serait la même faute
   que le débiaisage silencieux du lot D.

═══ DÉTERMINISME ═══

Tous les tirages passent par `scoring._XorShift`, le générateur déjà
utilisé par `bootstrap_ci` — la même graine donne la même sortie, sur
n'importe quelle machine. Un score qui bouge parce que le hasard a
changé d'avis serait indéfendable devant un pilote. Ce fichier
n'importe PAS `random`, et ce n'est pas un oubli.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

import scoring as S

# ══════════════════════════════════════════════════════════════════
#  SEUILS
# ══════════════════════════════════════════════════════════════════

#: Nombre de jours DISTINCTS sous lequel un bootstrap par blocs n'a
#: aucun sens. Avec des blocs de 3 jours, il faut au moins quelques
#: blocs indépendants pour que la distribution rééchantillonnée dise
#: quelque chose ; en dessous, l'intervalle décrit surtout le tirage.
#:
#: ⚠️ Au 09/08/2026, l'archive R2 commence le 07/08 : DEUX jours. Tout
#: ce fichier rend donc `None` avec la raison `window_too_short` en
#: production, et c'est le comportement voulu (arbitrage du 09/08 :
#: écrire le code maintenant, le laisser refuser tant que les données
#: manquent, et rejouer depuis l'archive quand elle sera profonde).
MIN_DAYS_BLOCK = 8

#: Longueur de bloc plancher, en jours. Une situation synoptique dure
#: typiquement trois jours : deux journées consécutives se ressemblent
#: parce qu'elles partagent la même situation, pas parce que le modèle
#: est stable. Un bloc plus court que la mémoire du phénomène ramène le
#: bootstrap au cas i.i.d. sans le dire.
MIN_BLOCK_DAYS = 3

#: Nombre de paires (balise-jour) sous lequel on ne compare rien, même
#: avec assez de jours. Reprend `WINNER_MIN_PAIRS` de `scoring.py`.
MIN_PAIRS_DIFF = S.WINNER_MIN_PAIRS

#: Itérations du bootstrap. Même valeur que `bootstrap_ci` — les deux
#: doivent rester comparables en coût comme en résolution (1/500 =
#: 0,2 %, largement sous les 2,5 % des bornes lues).
BOOTSTRAP_ITERATIONS = 500

#: Écart RELATIF minimal pour qu'une différence mérite d'être annoncée.
#: Repris de `rank_by_regime` : 1 km/h est décisif à 3 km/h et
#: anecdotique à 15.
MIN_RELATIVE_GAP = 0.15


#: Le taux de fausses découvertes visé sur le TABLEAU d'une nuit
#: (lot L3, 27/08/2026). ⛔ Ce n'est PAS un α de test : 0,10 ne veut pas
#: dire « 10 % de chances de se tromper sur cette case », il veut dire
#: « parmi les rangs publiés cette nuit, au plus 10 % en moyenne sont du
#: bruit ». La valeur vient de Wilks 2016 (BAMS 97:2263) : pour des
#: tests CORRÉLÉS — et les nôtres le sont massivement, une même journée
#: de flux traversant toutes les zones à la fois — la recommandation est
#: α_FDR ≈ 2α, soit 0,10 pour un α usuel de 0,05. Prendre 0,05 ici
#: serait plus sévère que la littérature ne le demande ET reposerait sur
#: une indépendance qu'on sait fausse.
ALPHA_FDR = 0.10


# ══════════════════════════════════════════════════════════════════
#  1. DIFFÉRENCES APPARIÉES
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class PairedDiff:
    """Une différence appariée : même balise, même jour, deux modèles."""
    day: str
    unit: str            # identifiant de balise ("pioupiou:1209")
    diff: float          # err(A) − err(B), en km/h. Négatif = A meilleur.


def paired_differences(rows_a: Sequence[Mapping],
                       rows_b: Sequence[Mapping],
                       value_key: str = "err_vec_med",
                       unit_key: str = "unit",
                       day_key: str = "day") -> list[PairedDiff]:
    """Apparie deux séries de balise-jours sur (jour, balise).

    ⚠️ L'APPARIEMENT EST LE CŒUR DU TEST, pas une commodité. Deux
    modèles notés sur des populations différentes de balise-jours ne
    sont pas comparables : l'un peut avoir été noté surtout les jours
    de brise (faciles) et l'autre surtout les jours de flux. La
    différence appariée annule l'effet du site ET celui de la journée,
    qui sont l'un et l'autre bien plus grands que l'effet du modèle.

    Les balise-jours présents d'un seul côté sont ÉCARTÉS, jamais
    comblés — un modèle absent n'a pas d'erreur « moyenne » à lui
    prêter.
    """
    by_key_b: dict[tuple, float] = {}
    for r in rows_b:
        v = r.get(value_key)
        if S._finite(v):
            by_key_b[(r[day_key], r[unit_key])] = float(v)
    out: list[PairedDiff] = []
    for r in rows_a:
        va = r.get(value_key)
        if not S._finite(va):
            continue
        k = (r[day_key], r[unit_key])
        vb = by_key_b.get(k)
        if vb is None:
            continue
        out.append(PairedDiff(day=k[0], unit=k[1], diff=float(va) - vb))
    out.sort(key=lambda d: (d.day, d.unit))
    return out


# ══════════════════════════════════════════════════════════════════
#  2. BOOTSTRAP PAR BLOCS DE JOURS
# ══════════════════════════════════════════════════════════════════

def block_length(n_days: int) -> int:
    """Longueur de bloc, en jours.

    Règle usuelle du bootstrap par blocs : ℓ ≈ n^(1/3), plancher à
    `MIN_BLOCK_DAYS` parce que la corrélation qu'on cherche à respecter
    est celle d'une situation synoptique, pas celle des données.
    Plafonnée à n/2 pour qu'il reste au moins deux blocs à tirer.
    """
    if n_days <= 0:
        return 1
    return max(1, min(n_days // 2, max(MIN_BLOCK_DAYS, round(n_days ** (1 / 3)))))


@dataclass(frozen=True)
class DiffCI:
    """IC d'une différence appariée. `reason` dit pourquoi c'est nul."""
    median: float | None
    ci_low: float | None
    ci_high: float | None
    n_pairs: int
    n_days: int
    block_days: int | None
    reason: str          # 'ok' | 'window_too_short' | 'too_few_pairs'
    #: p-valeur bilatérale de « la médiane des différences vaut zéro »,
    #: dérivée de la DISTRIBUTION bootstrap — voir `_p_bilaterale`.
    #: `None` quand aucun rééchantillonnage n'a eu lieu (`reason` != 'ok').
    #: ⛔ Ajouté EN DERNIER, avec un défaut : les six constructions
    #: positionnelles existantes (ici et dans `score.py`) restent justes
    #: au bit près. Un champ inséré au milieu les aurait toutes décalées
    #: en silence — le genre de faute qui ne rougit à aucun banc.
    p_value: float | None = None

    @property
    def separates(self) -> bool | None:
        """L'intervalle exclut-il zéro ? None si l'IC n'existe pas.

        ⚠️ C'est la SEULE lecture légitime d'un intervalle pour trancher
        entre deux modèles. Regarder si deux IC unaires se recouvrent
        n'est pas un test et ne le devient pas en le répétant.
        """
        if self.ci_low is None or self.ci_high is None:
            return None
        return self.ci_low > 0 or self.ci_high < 0


def block_bootstrap_ci(diffs: Sequence[PairedDiff],
                       iterations: int = BOOTSTRAP_ITERATIONS,
                       seed: int = 0x9E3779B9,
                       min_days: int = MIN_DAYS_BLOCK) -> DiffCI:
    """IC 95 % de la médiane des différences, par blocs de jours.

    Bootstrap par blocs CIRCULAIRE : les blocs sont pris sur la liste
    des jours refermée sur elle-même. Sans la fermeture, les premiers
    et les derniers jours de la fenêtre seraient tirés moins souvent
    que ceux du milieu (ils appartiennent à moins de blocs), ce qui
    biaiserait l'estimation vers le centre de la période — un défaut
    connu du bootstrap par blocs mobiles, et invisible sans le chercher.

    L'unité tirée est le JOUR : quand un jour est tiré, TOUTES ses
    balise-jours entrent dans le tirage ensemble. C'est ce qui fait la
    différence avec un tirage i.i.d. : la corrélation à l'intérieur
    d'une journée (même situation, même erreur de modèle partout) est
    préservée au lieu d'être moyennée.

    ⚠️ Rend `None` avec `reason` plutôt qu'un intervalle fabriqué. Au
    09/08/2026 l'archive porte deux jours : la réponse honnête est
    `window_too_short`, et un intervalle calculé quand même serait
    faux avec l'aplomb d'un chiffre.
    """
    by_day: dict[str, list[float]] = defaultdict(list)
    for d in diffs:
        if S._finite(d.diff):
            by_day[d.day].append(d.diff)
    return block_ci_by_day(by_day, iterations, seed, min_days)


def block_median_ci(values_by_day: Mapping[str, Sequence[float]],
                    iterations: int = BOOTSTRAP_ITERATIONS,
                    seed: int = 0x9E3779B9,
                    min_days: int = MIN_DAYS_BLOCK) -> DiffCI:
    """IC de la MÉDIANE d'une seule série, par blocs de jours.

    ⚠️ UN INTERVALLE UNAIRE N'EST PAS UN TEST, et celui-ci ne sert
    jamais à départager deux modèles — c'est `compare_pair` qui le
    fait, sur la différence appariée. Celui-ci répond à une autre
    question, parfaitement légitime : « à quel point connaît-on CE
    chiffre-là ». Il remplace l'appel i.i.d. de `bootstrap_ci` sur le
    chemin glissant, pour la même raison que le reste du fichier :
    deux journées consécutives ne sont pas indépendantes.
    """
    by_day = {d: [x for x in v if S._finite(x)] for d, v in values_by_day.items()}
    return block_ci_by_day({d: v for d, v in by_day.items() if v},
                           iterations, seed, min_days)


def _median_sorted(v: list[float]) -> float | None:
    """Médiane d'une liste DÉJÀ filtrée de ses valeurs non finies.

    ⚠️ Elle existe pour une raison mesurée, pas par goût. `S.median`
    rappelle `_finite` sur CHAQUE élément, et le bootstrap l'appelle
    500 fois par ligne : à la taille réelle (194 100 balise-jours,
    5 360 lignes de régime), cela faisait 485 millions d'appels de
    fonction Python, soit l'essentiel des 85 s mesurées le 09/08 pour
    le chemin régime. Les valeurs sont filtrées UNE FOIS à l'entrée du
    rééchantillonnage ; les refiltrer à chaque tirage ne peut rien
    trouver de nouveau.

    ⚠️ Elle n'est appelée QUE depuis la boucle de tirage, sur des
    listes construites à partir de `by_day` déjà nettoyé. Partout
    ailleurs, `S.median` — celle du portage, celle que le banc de
    parité compare au TypeScript.
    """
    if not v:
        return None
    v.sort()
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2


def _p_bilaterale(meds: Sequence[float]) -> float | None:
    """p-valeur bilatérale de « la médiane des différences vaut zéro »,
    lue dans la distribution bootstrap DÉJÀ tirée.

    ⭐ POURQUOI IL EN FAUT UNE (lot L3, 27/08/2026). Benjamini-Hochberg
    ordonne des p-valeurs ; le dispositif ne produisait qu'un
    INTERVALLE, c'est-à-dire une réponse binaire à 95 % (« zéro dedans /
    zéro dehors »). Deux cases également « séparées » ne sont pas
    également improbables, et un tableau de 1 121 cases se trie sur
    cette différence-là, pas sur le binaire.

    **La formule.** `p = 2 · (1 + #{tirages du mauvais côté}) / (B + 1)`,
    plafonnée à 1. C'est la p-valeur de rééchantillonnage usuelle
    (Davison & Hinkley 1997 §4.2 ; Phipson & Smyth 2010, qui montrent que
    le `+1` n'est pas une commodité : sans lui, `p = 0` est possible et
    fait passer une case pour infiniment improbable alors qu'on a
    seulement épuisé la résolution du tirage). Les tirages EXACTEMENT
    nuls sont comptés des DEUX côtés — le choix conservateur : ils
    grossissent p, donc retiennent une affirmation plutôt que d'en
    fabriquer une.

    ⚠️ SA LIMITE, ET ELLE DÉCIDE. La résolution est `2/(B+1)` : avec
    `BOOTSTRAP_ITERATIONS = 500`, AUCUNE case ne peut descendre sous
    `p ≈ 0,003992`, même si sa vraie p-valeur vaut 1e-9. Le seuil BH du
    premier rang, lui, vaut `α/m ≈ 0,10/1 121 ≈ 8,9e-5` — DIX FOIS PLUS
    BAS que ce plancher. Conséquence à connaître avant de lire un
    résultat : BH ne peut rejeter QUE par le nombre, jamais par
    l'extrémité d'une seule case — il faut qu'environ `m·p_min/α ≈ 45`
    cases atteignent ensemble le plancher pour que la première franchisse
    son seuil. C'est une propriété du tirage, pas du phénomène ; la seule
    façon de la lever est d'augmenter `BOOTSTRAP_ITERATIONS` (coût
    linéaire sur le poste le plus cher du run, 85 s mesurées le 09/08).
    ⇒ Arbitrage du 27/08 : on garde 500 et on VIT avec le plancher,
    parce qu'un p plancher est un MAJORANT de la vraie p-valeur, donc
    une erreur du côté qui publie MOINS de rangs. Publier moins est le
    sens du lot ; publier plus serait la faute.
    """
    if not meds:
        return None
    B = len(meds)
    n_neg = sum(1 for m in meds if m <= 0)
    n_pos = sum(1 for m in meds if m >= 0)
    return min(1.0, 2.0 * (1 + min(n_neg, n_pos)) / (B + 1))


def block_ci_by_day(by_day: Mapping[str, Sequence[float]],
                    iterations: int = BOOTSTRAP_ITERATIONS,
                    seed: int = 0x9E3779B9,
                    min_days: int = MIN_DAYS_BLOCK) -> DiffCI:
    """Le rééchantillonnage lui-même — un seul, pour les deux usages.

    Écrit une fois et appelé des deux côtés exprès : deux
    implémentations « équivalentes » du même tirage seraient la
    première chose à diverger, et c'est la leçon que le banc de parité
    de `scoring.py` a déjà coûtée.
    """
    # Filtrage UNE FOIS, ici, pour que la boucle de tirage n'ait plus
    # rien à valider (cf. `_median_sorted`).
    by_day = {d: [x for x in v if S._finite(x)] for d, v in by_day.items()}
    by_day = {d: v for d, v in by_day.items() if v}
    vals = [x for v in by_day.values() for x in v]
    days = sorted(by_day)
    n_days, n_pairs = len(days), len(vals)

    if n_pairs < MIN_PAIRS_DIFF:
        return DiffCI(S.median(vals), None, None,
                      n_pairs, n_days, None, "too_few_pairs")
    if n_days < min_days:
        return DiffCI(S.median(vals), None, None,
                      n_pairs, n_days, None, "window_too_short")

    L = block_length(n_days)
    n_blocks = math.ceil(n_days / L)
    rnd = S._XorShift(seed)
    meds: list[float] = []
    for _ in range(iterations):
        draw: list[float] = []
        taken = 0
        for _b in range(n_blocks):
            start = int(rnd.next() * n_days)
            for k in range(L):
                if taken >= n_days:
                    break
                draw.extend(by_day[days[(start + k) % n_days]])
                taken += 1
        m = _median_sorted(draw)
        if m is not None:
            meds.append(m)
    meds.sort()
    lo_i = math.floor(len(meds) * 0.025)
    hi_i = math.floor(len(meds) * 0.975)
    return DiffCI(
        median=S.median(vals),
        ci_low=meds[lo_i] if lo_i < len(meds) else None,
        ci_high=meds[hi_i] if hi_i < len(meds) else None,
        n_pairs=n_pairs, n_days=n_days, block_days=L, reason="ok",
        # ⚠️ LA MÊME LISTE `meds` QUE L'INTERVALLE, pas un second tirage.
        # Deux rééchantillonnages du même jeu donneraient un IC et une
        # p-valeur légèrement discordants — un jour, une case dont l'IC
        # exclut zéro et dont le p dit le contraire, et personne pour
        # savoir lequel croire.
        p_value=_p_bilaterale(meds))


def iid_bootstrap_ci(diffs: Sequence[PairedDiff],
                     iterations: int = BOOTSTRAP_ITERATIONS,
                     seed: int = 0x9E3779B9) -> DiffCI:
    """La MÊME chose en tirant les balise-jours indépendamment.

    ⚠️ CETTE FONCTION N'EST PAS APPELÉE EN PRODUCTION. Elle n'existe
    que pour le banc : sans un i.i.d. à côté, on ne saurait pas dire
    si le bootstrap par blocs a été implémenté ou seulement nommé. Sur
    des données à corrélation connue, l'IC par blocs DOIT être plus
    large — c'est la seule preuve que les blocs servent à quelque chose.
    """
    vals = [d.diff for d in diffs if S._finite(d.diff)]
    days = len({d.day for d in diffs})
    if len(vals) < MIN_PAIRS_DIFF:
        return DiffCI(S.median(vals), None, None, len(vals), days, None,
                      "too_few_pairs")
    rnd = S._XorShift(seed)
    meds: list[float] = []
    for _ in range(iterations):
        draw = [vals[int(rnd.next() * len(vals))] for _ in range(len(vals))]
        m = _median_sorted(draw)
        if m is not None:
            meds.append(m)
    meds.sort()
    lo_i = math.floor(len(meds) * 0.025)
    hi_i = math.floor(len(meds) * 0.975)
    # ⓘ La p-valeur aussi, pour la MÊME raison que l'IC : sans un i.i.d.
    # à côté, on ne saurait pas dire si le p par blocs a été implémenté
    # ou seulement nommé. Sur des données corrélées, le p par blocs DOIT
    # être le plus GRAND des deux (l'IC par blocs est le plus large).
    return DiffCI(S.median(vals),
                  meds[lo_i] if lo_i < len(meds) else None,
                  meds[hi_i] if hi_i < len(meds) else None,
                  len(vals), days, None, "ok", _p_bilaterale(meds))


# ══════════════════════════════════════════════════════════════════
#  3. LE VERDICT — un seul mécanisme, pas deux
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Verdict:
    winner: str | None
    reason: str
    ci: DiffCI | None = None
    relative_gap: float | None = None
    #: Le nombre de balise-jours sur lesquels `relative_gap` a été
    #: calculé — c'est-à-dire les balise-jours COMMUNS aux deux modèles
    #: (lot L3). Il vaut `ci.n_pairs` quand l'appariement a eu lieu ; il
    #: est publié parce qu'un écart de 15 % sur 6 balise-jours communs
    #: et le même écart sur 400 ne se lisent pas pareil.
    n_comparable: int = 0


def compare_pair(model_a: str, model_b: str,
                 rows_a: Sequence[Mapping], rows_b: Sequence[Mapping],
                 min_relative_gap: float = MIN_RELATIVE_GAP,
                 **kw) -> Verdict:
    """Départage DEUX modèles sur les mêmes balise-jours.

    Deux conditions, et il faut les deux :

    1. **Réel** — l'IC 95 % de la différence appariée, par blocs de
       jours, exclut zéro. C'est la question statistique.
    2. **Utile** — l'écart relatif sur l'erreur en km/h atteint 15 %,
       ⛔ mesuré sur les MÊMES balise-jours que le test (lot L3,
       27/08/2026 — voir le pavé dans le corps). C'est la question
       pratique, et elle est distincte : avec assez de journées, un
       écart de 0,2 km/h finit par être « significatif » sans rien
       changer à une décision de vol. C'est le défaut n°3 du §16.4,
       « significatif ≠ applicable », déjà payé une fois.

    ⚠️ Quand la fenêtre est trop courte pour le test, on ne RETOMBE PAS
    sur l'écart relatif seul. Ce serait remettre en service le
    mécanisme qu'on remplace, et publier deux verdicts de nature
    différente sous le même nom. On refuse de trancher et on le dit.
    """
    diffs = paired_differences(rows_a, rows_b, **{
        k: v for k, v in kw.items()
        if k in ("value_key", "unit_key", "day_key")})
    ci = block_bootstrap_ci(diffs, **{
        k: v for k, v in kw.items()
        if k in ("iterations", "seed", "min_days")})

    # ⚠️ LA MÊME CLÉ QUE LE TEST, PAS `err_vec_med` EN DUR (25/08/2026).
    # L'écart relatif et l'intervalle de la différence appariée doivent
    # porter sur la MÊME grandeur : mesurer l'IC sur l'erreur corrigée
    # puis l'écart pratique sur l'erreur brute donnerait un verdict
    # composite — réel sur une colonne, utile sur l'autre — dont
    # personne ne pourrait dire ce qu'il compare. Le défaut par défaut
    # reste `err_vec_med`, donc tous les appels existants sont
    # inchangés au bit près.
    value_key = kw.get("value_key", "err_vec_med")

    # ⛔ LOT L3 (27/08/2026) — `med_a` ET `med_b` SUR LES BALISE-JOURS
    # COMMUNS, plus jamais sur `rows_a`/`rows_b` entiers. C'est le défaut
    # MESURÉ de l'audit §2.5 : la « marche du haut » était protégée par
    # l'appariement, mais l'écart « utile » qui la valide juste après
    # comparait deux médianes calculées CHACUNE SUR SA POPULATION. Sur
    # les 58 cases mesurées le 25/08, `agrume` et `arome_r2` cohabitent
    # partout sans noter les mêmes balises : un modèle noté surtout les
    # jours de brise et l'autre surtout les jours de flux se voyaient
    # attribuer un écart pratique qui était, pour partie, un écart de
    # MÉTÉO. Les deux conditions du verdict portent maintenant sur la
    # même population, la même que l'intervalle — et c'est la seule
    # façon que « réel » et « utile » parlent du même écart.
    #
    # ⚠️ Conséquence assumée : quand l'appariement ne rend rien, le gap
    # vaut `None` au lieu d'un chiffre issu de deux populations
    # étrangères. Un `None` refuse de trancher (branche `tied`) — c'est
    # le bon sens de l'erreur, et c'était déjà le comportement quand
    # l'une des deux médianes manquait.
    communs = {(d.day, d.unit) for d in diffs}
    unit_key = kw.get("unit_key", "unit")
    day_key = kw.get("day_key", "day")

    def _med_appariee(rows):
        return S.median([r.get(value_key) for r in rows
                         if (r.get(day_key), r.get(unit_key)) in communs])

    med_a = _med_appariee(rows_a)
    med_b = _med_appariee(rows_b)
    gap = None
    if med_a is not None and med_b is not None:
        worse = max(med_a, med_b)
        gap = None if worse == 0 else abs(med_a - med_b) / worse
    n_comparable = len(communs)

    if ci.reason != "ok":
        return Verdict(None, ci.reason, ci, gap, n_comparable)
    if ci.separates is not True:
        return Verdict(None, "not_separable", ci, gap, n_comparable)
    if gap is None or gap < min_relative_gap:
        return Verdict(None, "tied", ci, gap, n_comparable)
    # `diff` = err(A) − err(B) : négatif veut dire que A se trompe moins.
    return Verdict(model_a if ci.median < 0 else model_b, "ok", ci, gap,
                   n_comparable)


def rank_models(cases: Sequence[Mapping],
                rows_by_model: Mapping[str, Sequence[Mapping]],
                min_occurrences: int = S.REGIME_MIN_OCCURRENCES,
                err_key: str = "typical_err_kmh",
                **kw):
    """Classe les modèles d'une case, ou refuse — par tests appariés.

    Rend `(rank_by_model, reason, detail)`. `rank_by_model` est vide
    quand on refuse de classer, ce qui reste le cas le plus fréquent et
    un résultat de première classe.

    Le classement n'est produit que si le meilleur modèle bat le
    deuxième par un test apparié. Autrement dit : on ne publie un ordre
    que quand la MARCHE DU HAUT est prouvée. Ordonner les autres entre
    eux « pour faire joli » donnerait un rang à des écarts qu'on vient
    de déclarer indiscernables.
    """
    # ⚠️ `err_key` — la colonne sur laquelle on ORDONNE (25/08/2026).
    # `typical_err_kmh` par défaut, `typical_err_kmh_corr` pour le
    # classement corrigé du biais de site. ⛔ Il doit désigner la MÊME
    # grandeur que le `value_key` passé plus bas à `compare_pair` :
    # ordonner sur une colonne et tester sur l'autre départagerait le
    # premier et le deuxième d'un classement qui n'est pas celui qu'on
    # publie. C'est l'appelant qui tient les deux ensemble.
    usable = [c for c in cases
              if c.get(err_key) is not None
              and c.get("occurrences", 0) >= min_occurrences]
    if not usable:
        return {}, "insufficient", None
    if len(usable) == 1:
        # ⛔ « 1ᵉʳ SUR 1 » N'EST PAS UN CLASSEMENT — changé le 22/08/2026
        # (lot S0.5). Cette branche rendait `{modèle: 1}, "ok"`, et à
        # l'écran un rang 1 assorti de « un vainqueur, prouvé et utile »
        # se lit « ce modèle est le meilleur ici ». Sur une case où il
        # est le SEUL, la phrase est fausse : il n'a battu personne.
        #
        # ⚠️ CE N'ÉTAIT PAS GRAVE JUSQU'ICI, ET ÇA LE DEVIENT. Mesuré le
        # 22/08 sur `model_score_zone` : DEUX lignes publiées sur 276 035
        # passaient par ici — les cases portent neuf à dix modèles, il
        # fallait que huit tombent sous le quorum. Le flux AROME/R2
        # (`arome_fcst.py`) rend le cas STRUCTUREL : 2 938 balises n'ont
        # qu'un seul modèle, par construction, et une case fine peuplée
        # de trois d'entre elles atteint le quorum POUR LUI SEUL.
        #
        # La règle du fichier ne change pas d'un pouce, elle s'applique :
        # « on ne publie un ordre que quand la MARCHE DU HAUT est
        # prouvée ». Sans second modèle, il n'y a pas de marche.
        # ⓘ `typical_err_kmh`, `skill`, `beats_persist` et `beats_clim`
        # restent publiés : ils ne comparent pas les modèles entre eux,
        # ils comparent CE modèle à la persistance et à la climatologie,
        # qui se calculent depuis les observations. C'est exactement ce
        # que ces lignes-là ont le droit de dire.
        return {}, "single_model", None

    ordered = sorted(usable, key=lambda c: c[err_key])
    best, second = ordered[0]["model"], ordered[1]["model"]
    v = compare_pair(best, second,
                     rows_by_model.get(best, ()), rows_by_model.get(second, ()),
                     **kw)
    if v.winner != best:
        return {}, v.reason, v
    return {c["model"]: i for i, c in enumerate(ordered, 1)}, "ok", v


# ══════════════════════════════════════════════════════════════════
#  3 bis. LA MULTIPLICITÉ — Benjamini-Hochberg (lot L3, 27/08/2026)
# ══════════════════════════════════════════════════════════════════

def benjamini_hochberg(p_values: Sequence[float | None],
                       alpha: float = ALPHA_FDR) -> tuple[list[bool], float | None, int]:
    """Quelles p-valeurs survivent au contrôle du taux de fausses
    découvertes, à `alpha`, sur la famille ENTIÈRE qu'on lui donne.

    Rend `(survivants, seuil, k)` — un booléen par p-valeur DANS L'ORDRE
    REÇU, la p-valeur seuil retenue (`None` si aucune ne survit), et le
    nombre de survivantes.

    ⭐ POURQUOI (audit §4.2, Wilks 2016). Le dispositif teste ~1 121
    cases (zone × lead × régime) CHAQUE NUIT et publie celles qui
    passent. Sans contrôle de la répétition, en régime permanent, environ
    5 % des « gagnants » publiés seraient du bruit — et ils seraient
    publiés avec exactement la même phrase que les vrais. La procédure de
    Benjamini & Hochberg (1995) ordonne les p-valeurs et retient les
    `k` plus petites telles que `p_(k) ≤ k·α/m`.

    ⛔ LA FAMILLE, C'EST TOUS LES TESTS JOUÉS, PAS LES SEULS PUBLIÉS.
    `m` doit compter les cases où un test a EU LIEU et n'a rien conclu
    (`not_separable`, `tied`) autant que celles qui ont conclu. Ne
    passer que les gagnantes ferait `m` = le nombre de succès et
    rendrait la correction quasi inopérante — l'erreur classique, et
    celle qui donne l'illusion d'avoir corrigé. En revanche les cases
    où AUCUN test n'a été joué (`insufficient`, `window_too_short`,
    `too_few_pairs`, `single_model`) n'en sont pas : il n'y a pas
    d'hypothèse testée à corriger, et les compter gonflerait `m` d'un
    tiers pour rien.

    ⚠️ BH SUPPOSE L'INDÉPENDANCE (ou la PRDS) ; nos tests sont corrélés.
    Le remède retenu est celui de Wilks — `alpha` doublé
    (`ALPHA_FDR`) — et non Benjamini-Yekutieli, dont le facteur
    `Σ 1/i ≈ 7,6` à m = 1 121 est bien trop sévère pour des tests
    positivement corrélés. Arbitrage écrit, pas mesuré : à réviser si
    un jour on sait estimer la corrélation effective du tableau.

    ⓘ Les `None` (pas de p-valeur) ne sont PAS dans la famille et
    rendent `False` — l'appelant décide ce qu'il en fait ; ici il ne les
    rétrograde pas, puisqu'elles n'ont rien affirmé.
    """
    indices = [i for i, p in enumerate(p_values) if p is not None]
    m = len(indices)
    survivants = [False] * len(p_values)
    if m == 0:
        return survivants, None, 0
    ordre = sorted(indices, key=lambda i: p_values[i])
    # Le plus GRAND k qui satisfait p_(k) ≤ k·α/m — pas le premier qui
    # échoue. La différence n'est pas cosmétique : les p-valeurs de
    # rang inférieur à k sont rejetées MÊME si elles échouent
    # individuellement au seuil, et c'est exactement ce qui fait de BH
    # une procédure « step-up » plutôt qu'une suite de tests.
    k = 0
    for rang, i in enumerate(ordre, 1):
        if p_values[i] <= rang * alpha / m:
            k = rang
    if k == 0:
        return survivants, None, 0
    for i in ordre[:k]:
        survivants[i] = True
    return survivants, p_values[ordre[k - 1]], k


# ══════════════════════════════════════════════════════════════════
#  4. RÉTRÉCISSEMENT VERS LE PARENT (partial pooling)
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Pooled:
    value: float | None
    borrowed: float | None   # part empruntée au parent, dans [0, 1]
    reason: str              # 'ok' | 'no_parent' | 'no_data' | 'single_child'


def pool_toward_parent(child_value: float | None, child_n: int,
                       parent_value: float | None,
                       tau2: float | None, sigma2: float | None) -> Pooled:
    """Rétrécit l'estimation d'une case fine vers celle de son parent.

    Forme classique de l'empirique bayésien :

        w = τ² / (τ² + σ²/n)        estimation = w·enfant + (1−w)·parent

    — où τ² est la variance ENTRE cases sœurs (ce qui distingue
    vraiment une vallée d'une autre) et σ²/n l'incertitude sur la case
    elle-même. Quand la case est peu fournie, σ²/n domine, w tend vers
    0 et l'estimation devient celle du parent. Quand elle est bien
    fournie, w tend vers 1 et le parent ne pèse plus rien.

    ⚠️ `borrowed` (= 1 − w) EST UN LIVRABLE, pas un diagnostic. Un
    score à 80 % emprunté au massif n'est pas un score de vallée. Le
    publier à côté du chiffre est la condition posée au §16.3 pour que
    le pooling améliore l'estimation sans ouvrir la vanne — le quorum
    reste, lui, le seuil d'AFFICHAGE (arbitrage du 09/08).

    ⚠️ Si τ² vaut 0 — les cases sœurs sont indiscernables — tout est
    emprunté, et c'est le bon comportement : dire « cette vallée-ci est
    différente » quand rien ne l'établit serait inventer une nuance.
    """
    if child_value is None or not S._finite(child_value):
        return Pooled(parent_value, 1.0 if parent_value is not None else None,
                      "no_data")
    if parent_value is None or not S._finite(parent_value):
        return Pooled(child_value, 0.0, "no_parent")
    if child_n <= 0 or tau2 is None or sigma2 is None:
        return Pooled(child_value, 0.0, "single_child")
    denom = tau2 + sigma2 / child_n
    w = 0.0 if denom <= 0 else tau2 / denom
    w = min(1.0, max(0.0, w))
    return Pooled(w * child_value + (1 - w) * parent_value, 1 - w, "ok")


def pooling_variances(children: Sequence[tuple[float, int, float]]):
    """Estime (τ², σ²) sur une fratrie.

    Chaque enfant : (valeur, n, variance interne). Rend :

    · σ² — variance interne typique (médiane des variances internes),
      robuste : une case aberrante ne doit pas fixer l'échelle de
      toutes les autres ;
    · τ² — variance ENTRE cases, obtenue en retranchant de la
      dispersion observée la part qui n'est due qu'au bruit
      d'échantillonnage. Bornée à 0 : quand la dispersion observée est
      entièrement explicable par le bruit, il n'y a rien à distinguer.

    Rend (None, None) sous deux enfants : une fratrie d'un seul enfant
    ne dit rien sur ce qui sépare les enfants.
    """
    usable = [(v, n, s2) for v, n, s2 in children
              if S._finite(v) and n and n > 0 and S._finite(s2)]
    if len(usable) < 2:
        return None, None
    vals = [v for v, _, _ in usable]
    mean = sum(vals) / len(vals)
    observed = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
    noise = sum(s2 / n for _, n, s2 in usable) / len(usable)
    sigma2 = S.median([s2 for _, _, s2 in usable])
    return max(0.0, observed - noise), sigma2


def sample_variance(values: Sequence[float]) -> float | None:
    v = [x for x in values if S._finite(x)]
    if len(v) < 2:
        return None
    m = sum(v) / len(v)
    return sum((x - m) ** 2 for x in v) / (len(v) - 1)


# ══════════════════════════════════════════════════════════════════
#  5. CLIMATOLOGIE HORAIRE — la seconde référence
# ══════════════════════════════════════════════════════════════════

def hourly_climatology(obs_by_day: Mapping[str, Sequence[S.ObsSample]],
                       utc_offset_s: int = 0,
                       min_days: int = 5):
    """Le vent HABITUEL de cette balise, heure locale par heure locale.

    ⚠️ Ce n'est pas la même question que la persistance. « Le modèle
    bat-il la valeur d'il y a 24 h » interroge la mémoire courte ; « le
    modèle bat-il ce qu'on savait déjà sans lui » interroge le cycle de
    brise, qui est le signal dominant sur un site de vol. Un modèle
    peut battre la persistance (parce qu'hier était atypique) tout en
    n'apprenant rien à personne sur une journée ordinaire.

    Moyenne VECTORIELLE par heure locale, jamais arithmétique sur les
    directions — même raison que `mean_wind`. Rend
    `{heure_locale: (force, direction, n_jours)}`, et seulement pour
    les heures vues au moins `min_days` jours DISTINCTS : une heure
    connue par une seule journée n'est pas une climatologie.
    """
    by_hour: dict[int, list[S.ObsSample]] = defaultdict(list)
    days_by_hour: dict[int, set] = defaultdict(set)
    for day, samples in obs_by_day.items():
        for s in samples:
            if not S._finite(s.speed):
                continue
            hod = ((s.t // 1000 + utc_offset_s) // 3600) % 24
            by_hour[hod].append(s)
            days_by_hour[hod].add(day)
    out: dict[int, tuple[float, float | None, int]] = {}
    for hod, samples in by_hour.items():
        n_days = len(days_by_hour[hod])
        if n_days < min_days:
            continue
        speed, direction, _ = S.mean_wind(samples)
        if speed is None:
            continue
        out[hod] = (speed, direction, n_days)
    return out


def skill_vs_climatology(pairs: Sequence[S.VerifPair],
                         clim: Mapping[int, tuple],
                         utc_offset_s: int = 0):
    """Rend (skill, n, mse_model, mse_clim), même forme que le skill
    contre la persistance — et pour la même raison les deux MSE sortent
    séparément : le skill est indéfini quand la référence est parfaite,
    or c'est précisément le cas où le modèle perd sans discussion.
    """
    from dataclasses import replace
    sq_m = sq_c = 0.0
    n = 0
    for p in pairs:
        hod = ((p.t // 1000 + utc_offset_s) // 3600) % 24
        ref = clim.get(hod)
        if ref is None:
            continue
        em, _ = S.pair_error(p)
        ec, _ = S.pair_error(replace(p, fcst_speed=ref[0], fcst_dir=ref[1]))
        sq_m += em * em
        sq_c += ec * ec
        n += 1
    if n < 2:
        return None, n, None, None
    mse_m, mse_c = sq_m / n, sq_c / n
    return (None if sq_c == 0 else 1 - sq_m / sq_c), n, mse_m, mse_c


# ══════════════════════════════════════════════════════════════════
#  5 ter. LA RÉFÉRENCE COMBINÉE (lot L9c, 28/08/2026)
#  Murphy 1992, Wea. Forecasting 7:692 — « Climatology, persistence,
#  and their linear combination as standards of reference »
# ══════════════════════════════════════════════════════════════════
#
# ⭐ POURQUOI UNE TROISIÈME RÉFÉRENCE, ALORS QU'IL Y EN A DÉJÀ DEUX.
# Le dispositif mesure aujourd'hui deux exploits séparés : battre la
# persistance (« hier à la même heure ») et battre la climatologie
# horaire (« le vent habituel ici à cette heure »). Un modèle peut
# gagner l'un en perdant l'autre, et c'est même l'intérêt de les avoir
# tous les deux.
#
# Mais aucun des deux n'est la référence la PLUS DURE. Murphy (1992)
# montre que leur combinaison linéaire optimale les DOMINE toutes les
# deux — elle a, par construction, un MSE inférieur ou égal à chacune —
# et que le poids optimal sur la persistance est ρ, l'autocorrélation
# de l'anomalie à l'échéance considérée (24 h ici) :
#
#     ref(t) = clim(h) + ρ · [obs(t − 24 h) − clim(h)]
#            = ρ · persistance + (1 − ρ) · climatologie
#
# Autrement dit : « comme hier, mais ramené vers l'habituel d'autant
# plus fort que hier prédit mal aujourd'hui ». ⛔ Tant qu'on ne la
# publie pas, l'objection « votre skill bat une référence faible » n'a
# aucune réponse chiffrée (audit §4.4, P7).
#
# ⚠️ À CÔTÉ, JAMAIS À LA PLACE. `mse_persist` et `mse_clim` répondent à
# deux questions de pilote (« mieux qu'hier ? », « mieux que
# d'habitude ? ») ; `mse_comb` répond à une question de méthode
# (« mieux que ce qu'on peut faire sans modèle ? »). Remplacer l'une
# par l'autre changerait la question sans changer le nom de la réponse.

#: ⛔⛔ LE PLANCHER SE COMPTE EN JOURNÉES, PAS EN HEURES — ET CE N'EST
#: PAS UN CHOIX DE PRUDENCE, C'EST UNE MESURE.
#:
#: La première version de ce lot exigeait 120 couples d'anomalies et
#: 5 journées. 120 couples ressemble à un gros échantillon ; il n'en est
#: pas un. Les 24 heures d'une même journée portent PRESQUE LA MÊME
#: anomalie (c'est la définition d'une anomalie journalière) : la taille
#: d'échantillon EFFECTIVE est le nombre de JOURNÉES, pas d'heures. Et
#: le retrait des moyennes, sur N points, biaise l'autocorrélation de
#: rang 1 d'environ **−1/N** — soit −0,20 pour cinq journées.
#:
#: ⭐ MESURÉ SUR LA PRODUCTION LE 28/08/2026 (3 725 balises, archive
#: réelle lue sur R2), ρ horaire médian par profondeur d'archive :
#:
#:     0–7 journées   2 928 balises   ρ méd **−0,194**   85 % négatifs
#:     8–14 journées      20 balises   ρ méd  +0,034     41 % négatifs
#:     15–21 journées    777 balises   ρ méd  **+0,082**  25 % négatifs
#:
#: −0,194 pour ~5 journées, c'est le biais de −1/5 au centième près : ce
#: que mesurait la première version, sur 85 % des balises, c'était son
#: propre biais d'estimation. Et le sens de l'erreur est le pire
#: possible : un ρ trop bas rend la référence combinée plus proche de la
#: climatologie seule, donc PLUS FACILE À BATTRE, donc un skill publié
#: FLATTEUR.
#:
#: ⇒ 15 journées. À 15 journées le biais résiduel vaut ≈ −1/14 ≈ −0,07,
#: il est NOMMÉ ici et non corrigé : une correction de biais tirée d'un
#: manuel (Marriott-Pope) suppose un AR(1) que rien n'a vérifié sur ces
#: séries, et un ρ « corrigé » sur une hypothèse fausse serait
#: exactement le nombre plausible et faux que tout ce chantier cherche à
#: ne pas publier.
#: ⚠️ CONSÉQUENCE ASSUMÉE : au 28/08, seuls `pioupiou` (21 j d'archive
#: médiane) et `metar` (19 j) franchissent ce plancher. Les quatre
#: réseaux nés le 21/08 (windsmobi, infoclimat, mf, aemet — 6 j) n'ont
#: PAS de `k` et n'auront donc pas de `mse_comb` avant que leur archive
#: n'atteigne 15 journées, soit vers le 05/09. C'est le comportement
#: ATTENDU, pas une panne : `mse_comb` vide sur ces réseaux-là ne se
#: diagnostique pas, il se lit dans ce pavé.
#: ⓘ À ROUVRIR quand tous les réseaux auront 30 journées (mi-septembre) :
#: remesurer la même table, et décider À CE MOMENT-LÀ si une correction
#: de biais se justifie — validée par simulation, pas par citation.
AUTOCORR_MIN_DAYS = 15

#: Garde-fou secondaire, en couples d'heures. Non contraignant à
#: 15 journées (≈ 360 couples) : il n'attrape que les balises dont la
#: série est trouée à l'intérieur des journées.
AUTOCORR_MIN_PAIRS = 120


def autocorr_lag24(obs_by_day: Mapping[str, Sequence[S.ObsSample]],
                   clim: Mapping[int, tuple],
                   utc_offset_s: int = 0) -> float | None:
    """ρ, l'autocorrélation à 24 h de l'ANOMALIE de force, sur une balise.

    Rend `None` (jamais 0, jamais 1) quand l'archive est trop courte —
    une référence combinée bâtie sur un poids inventé serait pire que
    pas de référence combinée du tout.

    ⚠️ SUR LA FORCE, PAS SUR LE VECTEUR, et c'est le même arbitrage que
    le mélange qu'elle pondère (`combined_reference` ci-dessous) : la
    force se mélange linéairement — c'est là que le théorème de Murphy
    s'applique — le cap se mélange circulairement, et une
    « autocorrélation vectorielle » demanderait une définition qu'aucune
    des deux moitiés ne réclame.

    ⚠️ ANOMALIE, PAS VALEUR BRUTE. L'autocorrélation à 24 h de la force
    BRUTE d'un site de brise est énorme (~0,7) et ne dit rien : elle
    mesure le cycle diurne, que la climatologie connaît déjà. Ce qui
    pondère la persistance, c'est ce qu'elle apporte EN PLUS de
    l'habituel — donc la persistance de l'ÉCART à l'habituel. Pondérer
    avec l'autocorrélation brute donnerait un poids proche de 1 partout,
    c'est-à-dire referait de la persistance seule sous un autre nom (la
    faute du 26/08 sur `poids_pi`, dans une autre matière).

    ⚠️ Corrélation de PEARSON sur les couples appariés (les deux
    moyennes retirées séparément) : les anomalies ne sont pas de moyenne
    exactement nulle sur une fenêtre finie, et poser qu'elles le sont
    fabriquerait un ρ biaisé — vers le haut, donc vers « la persistance
    suffit ».
    """
    # ── force horaire moyenne, par (journée, heure locale) ──
    par_jour: dict[str, dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(list))
    for day, samples in obs_by_day.items():
        for s in samples:
            if not S._finite(s.speed):
                continue
            hod = ((s.t // 1000 + utc_offset_s) // 3600) % 24
            par_jour[day][hod].append(s.speed)
    # ⛔ L'ANOMALIE SE MESURE CONTRE LA MÊME CLIMATOLOGIE QUE CELLE QUI
    # ENTRERA DANS LE MÉLANGE. Se servir d'une autre (la moyenne de la
    # journée, par exemple) donnerait un ρ qui ne pondère pas la
    # quantité qu'il est censé pondérer.
    anomalies: dict[tuple[str, int], float] = {}
    for day, heures in par_jour.items():
        for hod, vals in heures.items():
            ref = clim.get(hod)
            if ref is None or not S._finite(ref[0]):
                continue
            anomalies[(day, hod)] = sum(vals) / len(vals) - ref[0]
    # ── appariement à 24 h : même heure locale, journée précédente ──
    jours = sorted({d for d, _ in anomalies})
    index = {d: i for i, d in enumerate(jours)}
    a, b = [], []
    jours_vus = set()
    for (day, hod), x in anomalies.items():
        i = index[day]
        if i == 0:
            continue
        veille = jours[i - 1]
        # ⚠️ Les journées doivent être CONSÉCUTIVES : un trou d'archive
        # ferait apparier lundi avec vendredi sous le nom de « 24 h ».
        # Le test se fait sur les CHAÎNES de date, format `%Y-%m-%d`,
        # via un delta d'un jour calculé ici plutôt que supposé.
        if not _jours_consecutifs(veille, day):
            continue
        y = anomalies.get((veille, hod))
        if y is None:
            continue
        a.append(x)
        b.append(y)
        jours_vus.add(day)
    if len(a) < AUTOCORR_MIN_PAIRS or len(jours_vus) < AUTOCORR_MIN_DAYS:
        return None
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    if da <= 0.0 or db <= 0.0:
        return None
    return num / (da * db)


def _jours_consecutifs(veille: str, jour: str) -> bool:
    """`veille` est-elle la journée qui précède `jour` ? (`%Y-%m-%d`)"""
    from datetime import date, timedelta
    try:
        d1 = date.fromisoformat(veille)
        d2 = date.fromisoformat(jour)
    except ValueError:
        return False
    return d2 - d1 == timedelta(days=1)


def poids_combine(rho: float | None) -> tuple[float | None, bool]:
    """Le poids de la persistance dans le mélange, borné à [0, 1].

    Rend `(k, borne)` — `borne` vaut `True` quand ρ sortait de [0, 1] et
    a été ramené.

    ⚠️ POURQUOI ON BORNE, ET C'EST UN ARBITRAGE. Le poids optimal au
    sens du MSE est ρ, y compris NÉGATIF : sur un site où l'écart à
    l'habituel s'inverse d'un jour sur l'autre, la meilleure référence
    « sans modèle » serait l'anti-persistance. C'est mathématiquement
    juste et opérationnellement absurde — une référence que personne ne
    saurait formuler comme conseil (« demain, l'inverse d'aujourd'hui »)
    n'est pas une référence à battre, c'est une curiosité. On borne
    donc, et le run COMPTE les balises bornées : le jour où elles sont
    nombreuses, c'est le mélange qu'il faut rouvrir, pas la borne.
    """
    if rho is None or not S._finite(rho):
        return None, False
    if rho < 0.0:
        return 0.0, True
    if rho > 1.0:
        return 1.0, True
    return rho, False


def combined_reference(k: float, persist: tuple, clim_h: tuple) -> tuple:
    """`(force, cap)` du mélange `k·persistance + (1−k)·climatologie`.

    `persist` et `clim_h` sont des couples `(force, cap)` ; `cap` peut
    être `None` (station sans girouette, ou vent trop faible pour qu'elle
    dise quelque chose).

    ⚠️ FORCE EN SCALAIRE, CAP EN CIRCULAIRE — exactement le partage que
    `scoring.mean_wind` fait déjà, et pour la même raison. Mélanger les
    deux références en composantes (u, v) puis reprendre la norme
    rendrait une force SYSTÉMATIQUEMENT plus petite que celle des deux
    références mélangées (dès que leurs caps diffèrent), c'est-à-dire
    une référence artificiellement faible — donc un skill artificiellement
    bon. C'est la faute que ce lot existe pour ne PAS commettre.

    ⓘ `k = 1` rend la persistance au bit près, `k = 0` la climatologie :
    le banc le vérifie, parce qu'un mélange qui ne retrouve pas ses
    bornes n'est pas un mélange.
    """
    sp, dp = persist
    sc, dc = clim_h[0], clim_h[1]
    force = k * sp + (1.0 - k) * sc
    if dp is None and dc is None:
        return force, None
    if dp is None:
        return force, dc
    if dc is None:
        return force, dp
    # Vecteurs UNITAIRES : le cap se mélange indépendamment des forces,
    # sinon la référence la plus forte imposerait aussi sa direction.
    up, vp = S.to_uv(1.0, dp)
    uc, vc = S.to_uv(1.0, dc)
    u = k * up + (1.0 - k) * uc
    v = k * vp + (1.0 - k) * vc
    if math.hypot(u, v) < 1e-12:
        # Deux caps diamétralement opposés à poids égal : aucune
        # direction ne représente le mélange. On préfère se taire —
        # `pair_error` retombera alors sur l'écart de force, et le
        # `vector_ratio` de la série en gardera trace.
        return force, None
    return force, S.from_uv(u, v)


def skill_vs_combined(pairs: Sequence[S.VerifPair],
                      clim: Mapping[int, tuple],
                      k: float,
                      obs: Sequence[S.ObsSample],
                      utc_offset_s: int = 0):
    """Rend `(skill, n, mse_model, mse_comb)` — même forme que les deux
    autres références, et les deux MSE sortent séparément pour la même
    raison (le skill est indéfini quand la référence est parfaite).

    ⛔ LE MSE DU MODÈLE EST RECALCULÉ SUR **CETTE** POPULATION D'HEURES,
    et c'est la différence de fond avec `skill_vs_climatology`. Le
    mélange n'existe qu'aux heures où la persistance ET la climatologie
    existent toutes les deux — soit une population strictement plus
    petite que celle de chacune. Comparer le `mse_model` de la
    persistance à ce `mse_comb`-ci comparerait deux échantillons, pas
    deux prévisions : c'est le défaut §2.5.a de l'audit, celui que le
    lot L3 a fermé dans `compare_pair` et que le lot L8 a retrouvé
    ailleurs. `daily_rows` publie donc `mse_model_comb` À CÔTÉ de
    `mse_comb`, et les deux voyagent en couple.

    ⓘ La même réserve VAUT pour `mse_clim`, qui compare depuis le lot G4
    un `mse_model` de population « persistance » à un `mse_clim` de
    population « climatologie ». Non corrigé ICI, et volontairement :
    ce serait changer la DÉFINITION d'une colonne publiée au milieu
    d'une fenêtre glissante de 15 et 30 jours — exactement l'interdit du
    26/08 (« un changement de définition se publie sous un NOUVEAU nom,
    jamais en place »). À traiter comme un lot, avec une colonne neuve.
    """
    from dataclasses import replace
    sq_m = sq_c = 0.0
    n = 0
    for p in pairs:
        ref_s, ref_d = S.persistence_reference(obs, p.t)
        if ref_s is None:
            continue
        hod = ((p.t // 1000 + utc_offset_s) // 3600) % 24
        c = clim.get(hod)
        if c is None or not S._finite(c[0]):
            continue
        fs, fd = combined_reference(k, (ref_s, ref_d), c)
        em, _ = S.pair_error(p)
        ec, _ = S.pair_error(replace(p, fcst_speed=fs, fcst_dir=fd))
        sq_m += em * em
        sq_c += ec * ec
        n += 1
    if n < 2:
        return None, n, None, None
    mse_m, mse_c = sq_m / n, sq_c / n
    return (None if sq_c == 0 else 1 - sq_m / sq_c), n, mse_m, mse_c


# ══════════════════════════════════════════════════════════════════
#  5 bis. AGRÉGER UN ANGLE (lot L9a, 28/08/2026)
# ══════════════════════════════════════════════════════════════════

def circular_mean_deg(angles: Sequence[float]) -> float | None:
    """La moyenne CIRCULAIRE d'écarts de cap, en degrés dans (−180, 180].

    ⛔ POURQUOI ELLE EXISTE, ET CE QU'ELLE ÉVITE. `bias_dir_deg` est un
    écart signé rendu par `scoring.angular_diff` : il vit dans
    (−180, 180], et deux balise-jours à +179° et −179° décrivent le MÊME
    écart (le modèle est à un demi-tour près) à deux degrés près. Leur
    moyenne — ou leur médiane — arithmétique vaut 0°, c'est-à-dire
    « modèle parfaitement calé », l'exact contraire de ce que la donnée
    dit. La moyenne circulaire, elle, rend +180°.
    Ce n'est pas un cas d'école : un modèle en désaccord franc de cap
    sur un site de brise (donc oscillant autour du demi-tour) produit
    précisément cette population-là, et c'est le cas où l'indicateur
    doit crier.

    ⚠️ MOYENNE, PAS MÉDIANE, ET C'EST UN ARBITRAGE. Tout le reste du
    dispositif publie des médianes (`typical_err_kmh`, `bias_ratio`),
    par robustesse. La médiane circulaire n'a pas de définition unique
    bon marché — il faut minimiser une somme de distances angulaires sur
    un cercle, donc balayer les candidats en O(n²) — quand la moyenne
    circulaire, elle, est spécifiée en une ligne et se recalcule à la
    main. On publie donc une MOYENNE, et le pavé de `_case_rows` le dit
    en toutes lettres à côté du champ, pour que personne ne la lise
    comme une médiane. ⓘ À rouvrir le jour où une case est assez petite
    pour qu'une valeur aberrante déplace l'aiguille : ce serait une
    médiane circulaire écrite et testée ICI, jamais un tri ailleurs.

    Rend `None` si la liste est vide ou si la résultante est nulle — deux
    écarts diamétralement opposés n'ont pas de moyenne, et inventer 0°
    serait exactement la faute que cette fonction corrige.
    """
    sx = sy = 0.0
    n = 0
    for a in angles:
        if a is None or not S._finite(a):
            continue
        r = math.radians(a)
        sx += math.cos(r)
        sy += math.sin(r)
        n += 1
    if n == 0:
        return None
    # Résultante nulle : la population n'a pas de direction moyenne.
    # Le seuil est relatif à `n` — deux angles opposés donnent
    # exactement 0, mais l'arithmétique flottante laisse des miettes.
    if math.hypot(sx, sy) < 1e-12 * n:
        return None
    ang = math.degrees(math.atan2(sy, sx))
    # Ramené dans (−180, 180] : `atan2` rend déjà [−180, 180], on ne
    # corrige que le −180 exact pour qu'un demi-tour ait UN seul nom.
    return 180.0 if ang <= -180.0 else ang


# ══════════════════════════════════════════════════════════════════
#  6. STABILITÉ DES RANGS — le critère de sortie, mesuré
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Stability:
    kendall_tau: float | None
    top1_agreement: float | None
    n_cases: int
    n_comparable: int
    shared_days: int
    reason: str
    covers: str


def kendall_tau_b(a: Mapping[str, int], b: Mapping[str, int]) -> float | None:
    """Tau-b de Kendall sur les modèles classés des DEUX côtés."""
    keys = sorted(set(a) & set(b))
    if len(keys) < 2:
        return None
    conc = disc = ta = tb = 0
    for i in range(len(keys)):
        for j in range(i + 1, len(keys)):
            da = a[keys[i]] - a[keys[j]]
            db = b[keys[i]] - b[keys[j]]
            if da == 0 and db == 0:
                ta += 1
                tb += 1
            elif da == 0:
                ta += 1
            elif db == 0:
                tb += 1
            elif da * db > 0:
                conc += 1
            else:
                disc += 1
    n0 = conc + disc + ta
    n1 = conc + disc + tb
    if n0 <= 0 or n1 <= 0:
        return None
    return (conc - disc) / math.sqrt(n0 * n1)


def rank_stability(window_a: Mapping[tuple, Mapping[str, int]],
                   window_b: Mapping[tuple, Mapping[str, int]],
                   days_a: Iterable[str] = (),
                   days_b: Iterable[str] = ()) -> Stability:
    """Mesure l'accord des classements de deux fenêtres.

    ⚠️ LES DEUX FENÊTRES DOIVENT ÊTRE DISJOINTES. Deux fenêtres
    glissantes de 15 jours décalées d'un jour partagent 14 jours sur
    15 : mesurer leur accord mesure surtout ce recouvrement, et le
    chiffre obtenu — proche de 1 — dirait « les rangs sont stables »
    alors qu'il dit « les données sont les mêmes ». Le nombre de jours
    partagés est donc CALCULÉ, rendu, et `covers` écrit en toutes
    lettres ce que le chiffre recouvre, pour qu'il ne puisse pas être
    republié sans sa réserve.
    """
    shared = len(set(days_a) & set(days_b))
    cases = sorted(set(window_a) & set(window_b))
    taus, top1 = [], []
    for c in cases:
        t = kendall_tau_b(window_a[c], window_b[c])
        if t is not None:
            taus.append(t)
        fa = [m for m, r in window_a[c].items() if r == 1]
        fb = [m for m, r in window_b[c].items() if r == 1]
        if fa and fb:
            top1.append(1.0 if fa[0] == fb[0] else 0.0)
    if shared > 0:
        covers = (f"fenêtres NON disjointes ({shared} jours partagés) : ce "
                  f"chiffre mesure surtout le recouvrement, pas la stabilité")
        reason = "windows_overlap"
    elif not taus:
        covers = "aucune case classée des deux côtés — rien à comparer"
        reason = "no_common_case"
    else:
        covers = (f"{len(taus)} cases classées dans deux fenêtres disjointes ; "
                  f"tau-b moyen sur les modèles présents des deux côtés")
        reason = "ok"
    return Stability(
        kendall_tau=(sum(taus) / len(taus)) if taus else None,
        top1_agreement=(sum(top1) / len(top1)) if top1 else None,
        n_cases=len(cases), n_comparable=len(taus),
        shared_days=shared, reason=reason, covers=covers)
