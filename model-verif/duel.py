#!/usr/bin/env python3
"""duel.py — la différence APPARIÉE, publiée hors classement (lot L1).

    Session 27/08/2026.
    cf. `amelioration scoring/agrume/LOTS_SCORING_AGRUME_27-08.md` §L1
    et l'audit `phase ABC/audit-scoring-integration-methode-26-08.md`
    §0.2, §2.3, §2.4.

═══ POURQUOI CE FICHIER EXISTE ═══

Le classement ne saura JAMAIS trancher `agrume` contre `agrume_pi`, et
ce n'est pas un défaut réparable : l'écart attendu (~0,03 km/h sur
~4,1 km/h, soit 0,7 %) est vingt fois sous `MIN_RELATIVE_GAP` (15 %).
`rank` rendra `tied` pour toujours, PAR CONSTRUCTION. Et `err_vec_med`
ne le verra pas non plus — médiane sur 24 h d'un effet qui touche 6 h
(mesuré le 26/08 : la médiane des diffs vaut 0,0000, la colonne ne
bouge que sur 66 % des balises).

La puissance existe ailleurs, et une seule vue la porte : la
différence APPARIÉE d'`err_vec_rms` par balise-jour, cumulée dans le
temps, avec un intervalle par blocs de jours. Reconstruit depuis l'IC
de la phase B (sd(jour) ≈ 0,06 km/h) : verdict attendu en 15 à 40
jours. C'est long, et c'est pour ça que le cumul commence AUJOURD'HUI.

⚠️ CE N'EST PAS UN CLASSEMENT ET ÇA NE DOIT JAMAIS LE DEVENIR. Rien
ici n'écrit `rank`, `rank_reason`, ni une colonne de
`model_score_zone`. Le duel répond à « cette modification du produit
a-t-elle changé quelque chose », pas à « qui est le meilleur modèle
ici ce soir ». Fondre les deux rendrait un écran où un modèle serait
2ᵉ ET gagnant d'un duel, sans qu'une ligne ne dise que les deux
phrases ne parlent pas de la même chose.

═══ LES TROIS CHOIX QUI FONT LA MESURE ═══

1. **`err_vec_rms`, pas `err_vec_med`.** Mesuré le 26/08 sur les 247
   balises notables : `err_vec_rms` bouge sur 100 % des balises entre
   `agrume` et `agrume_pi`, `err_vec_med` sur 66 % avec une médiane de
   diffs à 0,0000. Juger PI sur la médiane conduirait à conclure « il
   n'apporte rien » à partir d'une propriété arithmétique
   (`test_bout_a_bout_la_mediane_est_structurellement_aveugle`).

2. **Lead 6 h, source `pioupiou`.** Les trois paires suivies n'ont de
   population commune qu'à cette échéance et sur ce réseau : AGRUME ne
   produit rien d'appariable au-delà de +6 h (moins de
   `MIN_HOURS_DAILY` heures), et sa population est le millier de
   Pioupiou du produit A. Élargir la source est le lot L7, pas
   celui-ci ; le jour où il passe, `DUEL_SOURCE = None` suffit — et
   il faudra alors RENAÎTRE les séries sous un autre nom de paire,
   parce que changer la population en cours de cumul est exactement la
   rupture de définition que `agrume_pi` a été créé pour éviter.

3. **L'intervalle porte sur la MÉDIANE des différences, la moyenne est
   publiée À CÔTÉ, sans intervalle.** `block_bootstrap_ci` rééchantillonne
   la médiane — c'est le seul estimateur que le socle du lot G sait
   borner, et il n'est pas question d'en réécrire un second ici (une
   deuxième implémentation du même tirage serait la première chose à
   diverger, leçon du banc de parité de `scoring.py`). La moyenne, elle,
   est le chiffre que l'audit cite (−0,031 km/h le 25/08) et celui qui
   voit le mieux un effet concentré sur quelques heures : la taire
   serait pire que la publier sans borne. Elle voyage donc avec
   `mean_ci` à `None` et le champ `ci_on` qui NOMME ce que l'intervalle
   borne, pour qu'aucun lecteur ne prête à l'une l'intervalle de
   l'autre. ⓘ Arbitrage à rouvrir si un IC de la moyenne devient utile :
   ce serait un paramètre `stat` de `block_ci_by_day`, écrit et testé
   là-bas, jamais un second tirage ici.

═══ CE QUE LE SIGNE VEUT DIRE ═══

`diff = err(A) − err(B)`, en km/h. **Négatif = A meilleur.** C'est la
convention de `inference.paired_differences`, reprise telle quelle et
répétée dans CHAQUE ligne publiée (`sign`), parce qu'un signe qui ne
voyage pas avec son chiffre finit lu à l'envers.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from typing import Iterable, Mapping, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inference as INF  # noqa: E402
import scoring as S  # noqa: E402

# ══════════════════════════════════════════════════════════════════
#  CE QU'ON SUIT
# ══════════════════════════════════════════════════════════════════

#: Les paires suivies chaque nuit. L'ordre du couple FIXE le signe :
#: `diff = err(premier) − err(second)`, négatif = le premier est
#: meilleur.
#:
#: · (`agrume`, `agrume_pi`) — la question du lot : le composite
#:   AROME+PI apporte-t-il quelque chose de mesurable.
#: · (`agrume`, `meteofrance_arome_france_hd`) — le TÉMOIN de chaîne :
#:   deux lectures indépendantes du même modèle (GRIB maison contre API
#:   Open-Meteo). Référence mesurée le 26/08 : −0,006 km/h, IC95j
#:   [−0,047 ; +0,027] sur 13 jours. Ce duel-là doit rester collé à
#:   zéro ; s'il décolle, c'est une chaîne qui a bougé, pas un modèle
#:   qui s'améliore — et il le dira AVANT que le classement ne s'en
#:   aperçoive.
#: · (`arome_r2`, `meteofrance_arome_france_hd`) — le plancher de
#:   chaîne mesuré (+0,165 km/h médian, IC [+0,088 ; +0,283]) suivi en
#:   continu, en attendant que L4 le décompose.
PAIRES_SUIVIES: tuple[tuple[str, str], ...] = (
    ("agrume", "agrume_pi"),
    # Lot L19 (04/09/2026) : le produit servi contre le mélange
    # multi-modèle pondéré par nos scores. C'est LA question du lot —
    # « mélanger AGRUME avec les autres fait-il mieux qu'AGRUME seul ? »
    # — et elle se pose ici, pas au classement (bw_mix n'y concourt pas).
    ("agrume_pi", "bw_mix"),
    ("agrume", "meteofrance_arome_france_hd"),
    ("arome_r2", "meteofrance_arome_france_hd"),
)

#: ⛔ LA COLONNE, ET IL N'Y EN A QU'UNE. Voir le §1 de l'en-tête.
DUEL_VALUE_KEY = "err_vec_rms"

#: La classe d'échéance. `6` et pas `+6 h` : c'est la valeur écrite en
#: base par `daily_rows` (`LEAD_BY_OFFSET`).
DUEL_LEAD_H = 6

#: Le réseau. `None` = toutes les sources (voir §2 de l'en-tête — et la
#: réserve de rupture de définition qui va avec).
DUEL_SOURCE = "pioupiou"

#: Profondeur lue en base pour le cumul. ⚠️ PLAFONNÉE PAR LA RÉTENTION
#: DE `model_verif_daily` (`score.RETENTION_DAILY_D` = 30 jours) : le
#: « cumul depuis la naissance de la paire » est en vérité « cumul
#: depuis la naissance de la paire OU depuis 30 jours, le plus récent
#: des deux ». Ce n'est pas un détail de mise en œuvre : le verdict
#: attendu demande 15 à 40 jours, donc le cumul touchera son plafond
#: AVANT de conclure. Le champ `truncated_by_retention` le dit sur
#: chaque ligne, et le jour où il passe à `true` sans qu'on ait tranché,
#: la suite est un cumul persisté (un état sous `--out`, patron
#: `ROUNDS_STATE_FILE`) — pas un allongement de la rétention, qui
#: coûterait la table entière pour trois paires.
DUEL_DAYS = 30

#: Colonnes lues en base. Sélection EXPLICITE et étroite : la requête
#: nocturne du duel ne doit pas rapatrier les 300 000 lignes complètes
#: de la fenêtre pour en lire quatre champs.
DUEL_COLONNES = ("day", "source", "station_id", "model", "lead_h",
                 "fcst_src", DUEL_VALUE_KEY)


# ══════════════════════════════════════════════════════════════════
#  1. SÉLECTION — et le doublon qu'on refuse de trancher
# ══════════════════════════════════════════════════════════════════

def _unit(row: Mapping) -> str:
    """L'identifiant de balise, MÊME FORME que `rolling_scores`.

    ⚠️ `source` ET `station_id`, jamais `station_id` seul : les
    identifiants ne sont uniques QUE par réseau (`collect_reduit` porte
    exprès les mêmes noms de modèles que `collect`, et rien ne garantit
    que deux réseaux n'aient pas la balise « 42 »). Une collision ici
    apparierait deux balises différentes et le duel n'aurait aucun moyen
    de s'en apercevoir.
    """
    return f"{row['source']}:{row['station_id']}"


def lignes_du_modele(daily: Iterable[Mapping], model: str,
                     lead_h: int | None = DUEL_LEAD_H,
                     source: str | None = DUEL_SOURCE,
                     value_key: str = DUEL_VALUE_KEY,
                     ) -> tuple[list[dict], int]:
    """Les balise-jours d'UN modèle, filtrés, sans doublon (jour, balise).

    Rend `(lignes, n_doublons_ecartes)`.

    ⛔ LE DOUBLON N'EST PAS TRANCHÉ, IL EST ÉCARTÉ. La clé d'upsert de
    `model_verif_daily` est `(day, source, station_id, model, lead_h,
    fcst_src)` : deux lignes peuvent légitimement coexister pour la même
    balise-jour si elles viennent de DEUX CHAÎNES (`fcst_src`). Au
    27/08/2026, une seule valeur existe en base (`own_archive`) — donc
    ce cas ne se produit pas, et c'est précisément pour ça qu'il faut
    l'écrire maintenant : le jour où une seconde chaîne apparaît,
    `paired_differences` prendrait silencieusement la DERNIÈRE lue (son
    dictionnaire écrase), et le duel comparerait deux chaînes en croyant
    comparer deux modèles. On écarte la balise-jour entière et on la
    COMPTE — un chiffre dans le journal vaut mieux qu'un choix
    arbitraire caché.
    """
    par_cle: dict[tuple, dict] = {}
    doublons: set[tuple] = set()
    for r in daily:
        if r.get("model") != model:
            continue
        if lead_h is not None and r.get("lead_h") != lead_h:
            continue
        if source is not None and r.get("source") != source:
            continue
        if not S._finite(r.get(value_key)):
            continue
        cle = (r["day"], _unit(r))
        if cle in par_cle:
            doublons.add(cle)
            continue
        par_cle[cle] = {"day": r["day"], "unit": _unit(r),
                        value_key: float(r[value_key])}
    for cle in doublons:
        par_cle.pop(cle, None)
    lignes = sorted(par_cle.values(), key=lambda d: (d["day"], d["unit"]))
    return lignes, len(doublons)


# ══════════════════════════════════════════════════════════════════
#  2. LE DUEL D'UNE PAIRE
# ══════════════════════════════════════════════════════════════════

def _serie_journaliere(diffs: Sequence[INF.PairedDiff]) -> list[dict]:
    """Moyenne et médiane par jour, plus le CUMUL depuis le premier jour.

    ⚠️ `cum_mean` est la moyenne de TOUTES les différences depuis le
    début, pas la moyenne des moyennes journalières. Les deux ne
    coïncident que si tous les jours portent le même nombre de balises —
    ce qui n'arrive jamais (247 le 25/08, 251 la veille). La moyenne des
    moyennes donnerait le même poids à une journée de 12 balises qu'à
    une journée de 250 ; c'est un autre estimateur, défendable, mais
    ce n'est pas celui que l'audit cite et deux définitions sous un même
    nom sont le début d'un chiffre invérifiable.
    """
    par_jour: dict[str, list[float]] = defaultdict(list)
    for d in diffs:
        par_jour[d.day].append(d.diff)
    out: list[dict] = []
    somme = 0.0
    n_cum = 0
    for jour in sorted(par_jour):
        vals = par_jour[jour]
        somme += sum(vals)
        n_cum += len(vals)
        out.append({
            "day": jour,
            "n": len(vals),
            "mean": round(sum(vals) / len(vals), 4),
            "median": _arrondi(S.median(vals)),
            "cum_n": n_cum,
            "cum_mean": round(somme / n_cum, 4),
        })
    return out


def _arrondi(x, nd: int = 4):
    """Même arrondi que `score._r` — 4 décimales, `None` préservé.

    ⓘ Écrit ici plutôt qu'importé de `score.py` : ce module est appelé
    PAR `score.py`, l'importer en retour ferait un cycle. Trois lignes
    dupliquées valent mieux qu'un import circulaire, et le banc les
    compare (`test_duel.py`).
    """
    return None if x is None or not S._finite(x) else round(float(x), nd)


def duel_paire(daily: Iterable[Mapping], model_a: str, model_b: str,
               lead_h: int | None = DUEL_LEAD_H,
               source: str | None = DUEL_SOURCE,
               value_key: str = DUEL_VALUE_KEY,
               fenetre_jours: int | None = DUEL_DAYS) -> dict:
    """Une ligne de duel : n, moyenne, médiane, IC95 par blocs, cumul.

    ⚠️ RIEN N'EST RÉÉCRIT ICI. L'appariement est
    `inference.paired_differences`, l'intervalle est
    `inference.block_bootstrap_ci` — les deux fonctions que le lot G a
    écrites, testées et couvertes (couverture mesurée : 95 % par blocs,
    42 % en i.i.d.). Cette fonction filtre, appelle, et met en forme.
    """
    daily = list(daily)
    rows_a, dup_a = lignes_du_modele(daily, model_a, lead_h, source, value_key)
    rows_b, dup_b = lignes_du_modele(daily, model_b, lead_h, source, value_key)
    diffs = INF.paired_differences(rows_a, rows_b, value_key=value_key)
    ci = INF.block_bootstrap_ci(diffs)
    serie = _serie_journaliere(diffs)
    moyenne = (sum(d.diff for d in diffs) / len(diffs)) if diffs else None

    separe = ci.separates
    if separe is None:
        verdict = ci.reason              # 'window_too_short' | 'too_few_pairs'
    elif not separe:
        verdict = "not_separable"
    elif (ci.median or 0.0) < 0:
        verdict = "a_better"
    else:
        verdict = "b_better"

    return {
        "model_a": model_a,
        "model_b": model_b,
        # ⛔ Le signe voyage AVEC le chiffre, sur chaque ligne. Un lecteur
        # qui doit aller chercher la convention ailleurs la devinera.
        "sign": "err(a) - err(b), km/h ; negatif = a meilleur",
        "value_key": value_key,
        "lead_h": lead_h,
        "source": source,
        "n_pairs": ci.n_pairs,
        "n_days": ci.n_days,
        "first_day": serie[0]["day"] if serie else None,
        "last_day": serie[-1]["day"] if serie else None,
        "mean_diff": _arrondi(moyenne),
        "median_diff": _arrondi(ci.median),
        # ⛔ CE QUE L'INTERVALLE BORNE, NOMMÉ. Voir le §3 de l'en-tête :
        # l'IC est celui de la MÉDIANE ; la moyenne est publiée nue.
        "ci_on": "median",
        "ci_low": _arrondi(ci.ci_low),
        "ci_high": _arrondi(ci.ci_high),
        "block_days": ci.block_days,
        "ci_reason": ci.reason,
        "separates": separe,
        "verdict": verdict,
        "excluded_duplicates": dup_a + dup_b,
        # ⚠️ Vrai quand la fenêtre lue touche son plafond : le cumul est
        # alors tronqué par la rétention, pas par la naissance de la paire.
        "truncated_by_retention": bool(
            fenetre_jours is not None and ci.n_days >= fenetre_jours),
        "daily": serie,
    }


def duels(daily: Iterable[Mapping],
          paires: Sequence[tuple[str, str]] = PAIRES_SUIVIES,
          lead_h: int | None = DUEL_LEAD_H,
          source: str | None = DUEL_SOURCE,
          value_key: str = DUEL_VALUE_KEY,
          fenetre_jours: int | None = DUEL_DAYS) -> list[dict]:
    """Toutes les paires suivies, dans l'ordre de `PAIRES_SUIVIES`.

    ⚠️ UNE PAIRE SANS UNE SEULE BALISE-JOUR COMMUNE REND QUAND MÊME SA
    LIGNE (`n_pairs = 0`, `verdict = 'too_few_pairs'`). Une ligne absente
    et une ligne à zéro se lisent pareil dans un JSON — et c'est la
    première qu'on cherche le soir où une ingestion est morte.
    """
    daily = list(daily)
    return [duel_paire(daily, a, b, lead_h, source, value_key, fenetre_jours)
            for a, b in paires]


# ══════════════════════════════════════════════════════════════════
#  3. LA REQUÊTE — étroite, et c'est le point
# ══════════════════════════════════════════════════════════════════

def query_duel(since: str, paires: Sequence[tuple[str, str]] = PAIRES_SUIVIES,
               lead_h: int | None = DUEL_LEAD_H,
               source: str | None = DUEL_SOURCE,
               colonnes: Sequence[str] = DUEL_COLONNES) -> str:
    """La requête PostgREST du duel, filtrée SERVEUR.

    ⛔ POURQUOI PAS RÉUTILISER LE `daily` DÉJÀ LU PAR LE RUN. Celui-là
    couvre `ROLLING_DAYS` = 15 jours ; le duel en veut 30 (le verdict
    demande 15 à 40 jours et le cumul ne doit pas se rouvrir chaque
    nuit). Et une seconde lecture de la fenêtre ENTIÈRE coûterait cher :
    `arome_r2` seul écrit ~7 400 lignes par jour. Filtrée sur quatre
    modèles, un lead et un réseau, la même fenêtre tient dans quelques
    dizaines de milliers de lignes à quatre colonnes.
    """
    modeles = sorted({m for p in paires for m in p})
    q = (f"?day=gte.{since}"
         f"&model=in.({','.join(modeles)})"
         f"&select={','.join(colonnes)}")
    if lead_h is not None:
        q += f"&lead_h=eq.{lead_h}"
    if source is not None:
        q += f"&source=eq.{source}"
    return q


def dire(duel: Mapping) -> str:
    """Une ligne de journal, lisible sans le JSON."""
    if duel["n_pairs"] == 0:
        return (f"  · {duel['model_a']} ↔ {duel['model_b']} : "
                f"AUCUNE balise-jour commune")
    ic = ("" if duel["ci_low"] is None
          else f", IC95j médiane [{duel['ci_low']:+.3f} ; "
               f"{duel['ci_high']:+.3f}]")
    return (f"  · {duel['model_a']} ↔ {duel['model_b']} : "
            f"n = {duel['n_pairs']} balise-jours sur {duel['n_days']} j "
            f"({duel['first_day']}→{duel['last_day']}), "
            f"moyenne {duel['mean_diff']:+.3f}, "
            f"médiane {duel['median_diff']:+.3f}{ic} → {duel['verdict']}")


# ══════════════════════════════════════════════════════════════════
#  4. RAPPORT PONCTUEL (hors run) — `python3 duel.py --jours 30`
# ══════════════════════════════════════════════════════════════════

def main() -> int:
    import argparse
    import json
    from datetime import datetime, timedelta, timezone

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jours", type=int, default=DUEL_DAYS)
    ap.add_argument("--day", default=None,
                    help="dernier jour de la fenêtre (défaut : hier)")
    ap.add_argument("--json", action="store_true",
                    help="rend le bloc `duels` tel qu'il sera publié")
    args = ap.parse_args()

    # ⓘ Import TARDIF, et pas par élégance : `score.py` importe ce
    # module. L'importer en tête ferait un cycle à l'import.
    import score as SC  # noqa: PLC0415

    day = (datetime.strptime(args.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
           if args.day
           else datetime.now(timezone.utc) - timedelta(days=1))
    since = (day - timedelta(days=args.jours - 1)).strftime("%Y-%m-%d")
    sb = SC.Supabase()
    daily = sb.select("model_verif_daily", query_duel(since),
                      order="day,source,station_id,model,lead_h,fcst_src")
    print(f"▶ duel : {len(daily)} lignes lues depuis le {since} "
          f"(lead {DUEL_LEAD_H}, source {DUEL_SOURCE}, {DUEL_VALUE_KEY})")
    blocs = duels(daily, fenetre_jours=args.jours)
    if args.json:
        print(json.dumps(blocs, indent=1, ensure_ascii=False))
    else:
        for d in blocs:
            print(dire(d))
            for j in d["daily"]:
                print(f"        {j['day']}  n={j['n']:>4}  "
                      f"moy {j['mean']:+.4f}  méd {j['median']:+.4f}  "
                      f"cumul n={j['cum_n']:>5} moy {j['cum_mean']:+.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
