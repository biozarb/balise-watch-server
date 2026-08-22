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
        n_pairs=n_pairs, n_days=n_days, block_days=L, reason="ok")


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
    return DiffCI(S.median(vals),
                  meds[lo_i] if lo_i < len(meds) else None,
                  meds[hi_i] if hi_i < len(meds) else None,
                  len(vals), days, None, "ok")


# ══════════════════════════════════════════════════════════════════
#  3. LE VERDICT — un seul mécanisme, pas deux
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Verdict:
    winner: str | None
    reason: str
    ci: DiffCI | None = None
    relative_gap: float | None = None


def compare_pair(model_a: str, model_b: str,
                 rows_a: Sequence[Mapping], rows_b: Sequence[Mapping],
                 min_relative_gap: float = MIN_RELATIVE_GAP,
                 **kw) -> Verdict:
    """Départage DEUX modèles sur les mêmes balise-jours.

    Deux conditions, et il faut les deux :

    1. **Réel** — l'IC 95 % de la différence appariée, par blocs de
       jours, exclut zéro. C'est la question statistique.
    2. **Utile** — l'écart relatif sur l'erreur en km/h atteint 15 %.
       C'est la question pratique, et elle est distincte : avec assez
       de journées, un écart de 0,2 km/h finit par être « significatif »
       sans rien changer à une décision de vol. C'est le défaut n°3 du
       §16.4, « significatif ≠ applicable », déjà payé une fois.

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

    med_a = S.median([r.get("err_vec_med") for r in rows_a])
    med_b = S.median([r.get("err_vec_med") for r in rows_b])
    gap = None
    if med_a is not None and med_b is not None:
        worse = max(med_a, med_b)
        gap = None if worse == 0 else abs(med_a - med_b) / worse

    if ci.reason != "ok":
        return Verdict(None, ci.reason, ci, gap)
    if ci.separates is not True:
        return Verdict(None, "not_separable", ci, gap)
    if gap is None or gap < min_relative_gap:
        return Verdict(None, "tied", ci, gap)
    # `diff` = err(A) − err(B) : négatif veut dire que A se trompe moins.
    return Verdict(model_a if ci.median < 0 else model_b, "ok", ci, gap)


def rank_models(cases: Sequence[Mapping],
                rows_by_model: Mapping[str, Sequence[Mapping]],
                min_occurrences: int = S.REGIME_MIN_OCCURRENCES,
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
    usable = [c for c in cases
              if c.get("typical_err_kmh") is not None
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

    ordered = sorted(usable, key=lambda c: c["typical_err_kmh"])
    best, second = ordered[0]["model"], ordered[1]["model"]
    v = compare_pair(best, second,
                     rows_by_model.get(best, ()), rows_by_model.get(second, ()),
                     **kw)
    if v.winner != best:
        return {}, v.reason, v
    return {c["model"]: i for i, c in enumerate(ordered, 1)}, "ok", v


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
