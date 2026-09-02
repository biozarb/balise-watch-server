#!/usr/bin/env python3
"""murphy.py — TIMING ou AMPLITUDE : de quoi ce modèle souffre-t-il ici ?
(lot L9b)

    Session 28/08/2026.
    cf. `amelioration scoring/agrume/LOTS_SCORING_AGRUME_27-08.md` §L9
    et l'audit `phase ABC/audit-scoring-integration-methode-26-08.md`
    §4.3-4.5 (point 5 du « ce qui manque »).

═══ POURQUOI CE FICHIER EXISTE ═══

Le score publié dit COMBIEN un modèle se trompe ici (`typical_err_kmh`),
et depuis le lot L9a il dit aussi s'il souffle trop fort ou pas assez
(`bias_ratio`). Il ne dit toujours pas la seule chose qui décide de ce
qu'on peut y FAIRE : est-ce que ce modèle rate la FORME de la journée
(le thermique monte trop tard, la brise tombe trop tôt) ou son
AMPLITUDE (la forme est juste, l'échelle est fausse) ?

La distinction n'est pas académique — c'est la frontière EXACTE de ce
que la correction de biais de site du lot S2 peut réparer :

  · une erreur d'AMPLITUDE se corrige par une pente. C'est précisément
    ce que `scoring.pente_moindres_carres` estime et que
    `apply_bias` applique.
  · une erreur de TIMING ne se corrige par AUCUNE pente. Multiplier
    une courbe décalée de deux heures par un facteur ne la recale pas.

La décomposition de Murphy (1988, MWR 116:2417) sépare les deux en
trois nombres, sur le score de compétence MSE contre la CLIMATOLOGIE
D'ÉCHANTILLON (la moyenne des observations de la fenêtre) :

    SS = r²  −  (r − s_f/s_o)²  −  ((f̄ − ō)/s_o)²
         └┬┘     └──────┬─────┘     └──────┬──────┘
      potentiel      biais           biais
      (le TIMING)  conditionnel   systématique
                   (l'AMPLITUDE)   (le décalage)

L'identité est EXACTE (elle se démontre en développant
MSE = s_f² + s_o² − 2·r·s_f·s_o + (f̄ − ō)²), et le banc la vérifie
terme à terme plutôt que de la croire.

Lecture :
  · `r2` haut, `bc`/`bs` proches de 0 → le modèle a la bonne forme et
    la bonne échelle. Rien à corriger.
  · `r2` haut, `bc` gros → la forme est bonne, l'échelle est fausse.
    ⭐ C'EST LE CAS QUE LE LOT S2 RÉPARE, et `r2` est le plafond qu'il
    peut atteindre.
  · `r2` bas → le modèle rate la journée elle-même. AUCUNE pente ne le
    sauvera ; c'est un problème de modèle, pas de site.

═══ LES QUATRE CHOIX QUI FONT LA MESURE ═══

1. **Sur la VITESSE, pas sur l'erreur vectorielle.** La décomposition
   est définie pour un scalaire. Et le scalaire qui compte ici est
   celui que la correction S2 manipule : la FORCE. Décomposer une norme
   vectorielle mélangerait à nouveau force et cap, c'est-à-dire
   refabriquerait exactement la confusion que le lot L9a vient de
   défaire. ⓘ Le cap a déjà son compagnon (`bias_dir_deg`).

2. **Sur la prévision BRUTE, jamais corrigée.** Murphy répond « que
   POURRAIT réparer une pente » : la mesurer sur une série déjà
   corrigée répondrait « que reste-t-il après », qui est une autre
   question et qui rendrait `bc` mécaniquement petit.

3. **La référence est la MOYENNE DES OBSERVATIONS de la fenêtre, et ce
   n'est PAS `mse_clim`.** L'identité de Murphy ne tient que contre la
   climatologie d'ÉCHANTILLON (une constante, ō). La colonne
   `mse_clim` du dispositif, elle, est bâtie sur une climatologie
   HORAIRE (`inference.hourly_climatology`), qui connaît le cycle
   diurne — une référence bien plus dure. ⛔ `ss` ne se compare donc
   PAS à `skill_clim`, et les deux ne doivent jamais être mis dans la
   même colonne. Le champ `ss_reference` le NOMME sur chaque ligne.

4. **On ne POOLE PAS les moments entre balises.** Le résumé par modèle
   est la MÉDIANE des décompositions par balise, pas une décomposition
   des moments additionnés. Additionner les moments de deux sites dont
   l'un souffle en moyenne 8 km/h et l'autre 25 gonfle `s_o` de la
   variance INTER-SITES : le `r²` qui en sort mesurerait surtout la
   capacité du modèle à savoir lequel des deux sites est le plus venté,
   ce qu'on ne lui demande pas. Les moments s'additionnent en revanche
   librement entre JOURNÉES d'une même balise — c'est ce que fait
   `pool`, et c'est exact.

═══ D'OÙ VIENNENT LES CHIFFRES ═══

`score.daily_rows` dépose sur chaque balise-jour une clé PRIVÉE
`_murphy` : les six sommes suffisantes `[n, Σf, Σo, Σf², Σo², Σfo]` des
heures appariées de la journée. Six nombres, pas 24 couples — et ils
s'additionnent, ce qui est toute la raison de les stocker ainsi.

⚠️ Ces six sommes voyagent dans le CACHE DE REJEU
(`score.REPLAY_SUBDIR`), pas en base : c'est pour elles (et pour
`mse_comb` du volet c) que `REPLAY_FORMULA` passe de 4 à 5. La clé
commence par `_` pour que `_pour_la_base` ne la prenne jamais pour une
colonne manquante.
"""
from __future__ import annotations

import math
import os
import sys
from collections import defaultdict
from typing import Iterable, Mapping, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scoring as S  # noqa: E402

#: La clé privée déposée par `score.daily_rows` sur chaque balise-jour.
#: ⚠️ COMMENCE PAR `_` — c'est ce qui la tient hors de `_pour_la_base`
#: (elle n'est pas une colonne de `model_verif_daily` et n'a pas à le
#: devenir : six sommes par balise-jour multiplieraient la table par
#: rien du tout de lisible).
MURPHY_KEY = "_murphy"

#: Sous quel plancher on refuse de décomposer. 120 heures appariées,
#: c'est cinq journées pleines : en dessous, `r` est une estimation sur
#: une poignée de points et son carré se lit comme un verdict.
#: ⚠️ DEUX PLANCHERS, PAS UN. 120 heures d'UNE SEULE journée
#: décriraient le cycle diurne d'un jour, pas le comportement du
#: modèle ; et un `r²` tiré d'une seule situation synoptique est
#: exactement le faux verdict que ce lot existe pour ne pas publier.
MURPHY_MIN_PAIRS = 120
MURPHY_MIN_DAYS = 5

#: Ce que le score de compétence de Murphy prend pour référence, écrit
#: sur CHAQUE ligne publiée. Voir le §3 de l'en-tête : ce n'est pas
#: `mse_clim`, et un lecteur qui les comparerait se tromperait.
SS_REFERENCE = ("moyenne des observations de la fenetre (climatologie "
                "d'echantillon, Murphy 1988) — PAS la climatologie "
                "horaire de `skill_clim`")


# ══════════════════════════════════════════════════════════════════
#  1. LES SOMMES SUFFISANTES
# ══════════════════════════════════════════════════════════════════

def moments(pairs: Sequence[S.VerifPair]) -> list[float]:
    """`[n, Σf, Σo, Σf², Σo², Σfo]` sur la VITESSE des heures appariées.

    ⚠️ Arrondi à 4 décimales : ces six nombres sont écrits dans le cache
    de rejeu, et un `Σf²` en 17 chiffres significatifs par balise-jour
    coûterait plus cher que tout le reste de la ligne. La résolution
    relative reste de l'ordre de 1e−11 sur des sommes en milliers —
    dix ordres de grandeur sous ce qu'un `r²` publié à trois décimales
    demande.
    """
    n = 0
    sf = so = sff = soo = sfo = 0.0
    for p in pairs:
        f, o = p.fcst_speed, p.obs_speed
        if not (S._finite(f) and S._finite(o)):
            continue
        n += 1
        sf += f
        so += o
        sff += f * f
        soo += o * o
        sfo += f * o
    return [n, round(sf, 4), round(so, 4),
            round(sff, 4), round(soo, 4), round(sfo, 4)]


def pool(liste: Iterable[Sequence[float]]) -> list[float] | None:
    """Additionne des sommes suffisantes. Rend `None` si rien à sommer.

    ⛔ N'ADDITIONNER QUE DES JOURNÉES D'UNE MÊME BALISE — voir le §4 de
    l'en-tête. Rien ici ne peut le vérifier ; c'est l'appelant qui
    groupe, et `par_balise` est le seul appelant du run.
    """
    tot = [0, 0.0, 0.0, 0.0, 0.0, 0.0]
    vu = False
    for m in liste:
        if not m or len(m) != 6 or not m[0]:
            continue
        vu = True
        tot[0] += int(m[0])
        for i in range(1, 6):
            tot[i] += float(m[i])
    return tot if vu else None


# ══════════════════════════════════════════════════════════════════
#  2. LA DÉCOMPOSITION
# ══════════════════════════════════════════════════════════════════

def decompose(m: Sequence[float] | None) -> dict:
    """`{r2, bc, bs, ss, r, sd_ratio, mean_f, mean_o, sd_o, n, reason}`.

    Les moments sont ceux de la POPULATION (division par n, pas n−1) —
    c'est la convention sous laquelle l'identité de Murphy est exacte,
    parce que le MSE se divise lui aussi par n.

    ⛔ TROIS CAS OÙ L'ON REFUSE DE RÉPONDRE, ET ILS SE NOMMENT :
    · `too_few_pairs` — sous `MURPHY_MIN_PAIRS`, l'appelant le pose.
    · `flat_obs` — les observations n'ont PAS varié (`s_o = 0`). Il n'y
      a alors rien à expliquer : la climatologie d'échantillon est
      parfaite et tout score de compétence est indéfini (division par
      zéro). Ce n'est pas un défaut du modèle, c'est une journée sans
      vent, et le dire vaut mieux qu'un `ss = -inf`.
    · rien — `ok`.

    ⚠️ ET LE CAS QUI N'EN EST PAS UN : `s_f = 0` (le modèle prévoit une
    constante). `r` est alors indéfini au sens strict (0/0), mais la
    décomposition, elle, ne l'est pas : `r² − (r − 0)²` vaut 0 quelle
    que soit la valeur qu'on donne à `r`. On pose donc `r = 0` — une
    prévision constante n'explique aucune variance — et il reste
    `ss = −bs²`, ce qui est exactement juste. Poser `None` ici ferait
    disparaître une ligne parfaitement interprétable.
    """
    vide = {"n": 0, "r": None, "r2": None, "bc": None, "bs": None,
            "ss": None, "sd_ratio": None, "mean_f": None, "mean_o": None,
            "sd_o": None, "reason": "too_few_pairs"}
    if not m or not m[0]:
        return vide
    n, sf, so, sff, soo, sfo = m[0], m[1], m[2], m[3], m[4], m[5]
    n = int(n)
    mf, mo = sf / n, so / n
    var_f = max(sff / n - mf * mf, 0.0)
    var_o = max(soo / n - mo * mo, 0.0)
    cov = sfo / n - mf * mo
    sdf, sdo = math.sqrt(var_f), math.sqrt(var_o)
    if sdo <= 0.0:
        return {**vide, "n": n, "mean_f": round(mf, 4),
                "mean_o": round(mo, 4), "sd_o": 0.0, "reason": "flat_obs"}
    r = 0.0 if sdf <= 0.0 else cov / (sdf * sdo)
    # ⚠️ Bornage à [−1, 1] : l'arithmétique flottante sur des sommes de
    # carrés peut rendre 1,0000000002, et un `r² > 1` publié se lirait
    # comme un défaut de la mesure — ce qu'il serait.
    r = max(-1.0, min(1.0, r))
    bc = r - (sdf / sdo)
    bs = (mf - mo) / sdo
    return {
        "n": n,
        "r": round(r, 4),
        "r2": round(r * r, 4),
        "bc": round(bc, 4),
        "bs": round(bs, 4),
        "ss": round(r * r - bc * bc - bs * bs, 4),
        "sd_ratio": round(sdf / sdo, 4),
        "mean_f": round(mf, 4),
        "mean_o": round(mo, 4),
        "sd_o": round(sdo, 4),
        "reason": "ok",
    }


def mse_depuis_moments(m: Sequence[float]) -> float:
    """Le MSE de la VITESSE, recalculé des mêmes six sommes.

    N'entre pas dans la publication : c'est le témoin du banc, qui
    vérifie l'identité `SS = 1 − MSE/s_o²` par un chemin qui ne
    réutilise ni `r`, ni `bc`, ni `bs`.
    """
    n, sf, so, sff, soo, sfo = m[0], m[1], m[2], m[3], m[4], m[5]
    return (sff - 2.0 * sfo + soo) / int(n)


# ══════════════════════════════════════════════════════════════════
#  3. PAR BALISE, PUIS LE RÉSUMÉ PAR MODÈLE
# ══════════════════════════════════════════════════════════════════

def accumule(acc: dict, cle: tuple, moments: Sequence[float] | None) -> None:
    """Ajoute les six sommes d'UN balise-jour dans l'accumulateur.

    ⛔⛔ POURQUOI UN ACCUMULATEUR ET PAS UNE LISTE DE LIGNES — ET C'EST
    UNE MESURE, PAS UN GOÛT. La première version de ce module lisait
    `units`, c'est-à-dire les 405 486 lignes de la fenêtre rejouée, avec
    leur clé `_murphy` attachée. Chaque clé coûte une liste Python et
    six flottants, soit ~260 octets : **~107 Mo de plus au pic**, sur un
    VPS de 3,8 Go SANS SWAP dont le run de la nuit du 28/08 venait
    précisément d'être tué par l'OOM killer (`Result: oom-kill`,
    06:20:40 CEST).
    Ici, l'état total tient dans un tableau de sept nombres par
    (balise, modèle, échéance) : ~37 000 clés, **~5 Mo**. Les six sommes
    sont ADDITIVES — c'est toute la raison de les avoir choisies — donc
    rien ne se perd à les fondre au fil de l'eau.

    `acc[cle] = [n, Σf, Σo, Σf², Σo², Σfo, n_journées]`.

    ⚠️ `n_journées` est un COMPTEUR, pas un ensemble de dates : un
    `set` de 30 chaînes par clé pèserait ~66 Mo à lui seul, ce qui
    aurait rendu l'optimisation vaine. Il est exact parce que
    l'appelant balaie la fenêtre JOUR PAR JOUR et qu'une clé ne reçoit
    au plus qu'une ligne par journée (la clé d'upsert de
    `model_verif_daily` le garantit, `fcst_src` mis à part — et un
    doublon de chaîne y ajouterait une journée en trop, ce qui gonfle
    le dénominateur du plancher, jamais le r² publié).
    """
    if not moments or not moments[0]:
        return
    b = acc.get(cle)
    if b is None:
        acc[cle] = [int(moments[0]), float(moments[1]), float(moments[2]),
                    float(moments[3]), float(moments[4]), float(moments[5]), 1]
        return
    b[0] += int(moments[0])
    for i in range(1, 6):
        b[i] += float(moments[i])
    b[6] += 1


def par_balise_depuis_acc(acc: Mapping[tuple, Sequence[float]],
                          min_pairs: int = MURPHY_MIN_PAIRS,
                          min_days: int = MURPHY_MIN_DAYS) -> list[dict]:
    """Les lignes publiables, depuis l'accumulateur de `accumule`."""
    out: list[dict] = []
    for (unit, model, lead), b in sorted(acc.items(),
                                         key=lambda kv: (kv[0][1], kv[0][2],
                                                         kv[0][0])):
        tot = list(b[:6])
        n_jours = int(b[6])
        dec = decompose(tot)
        if dec["reason"] == "ok" and (dec["n"] < min_pairs
                                      or n_jours < min_days):
            dec = {**dec, "r": None, "r2": None, "bc": None, "bs": None,
                   "ss": None, "sd_ratio": None, "reason": "too_few_pairs"}
        out.append({"unit": unit, "model": model, "lead_h": lead,
                    "n_days": n_jours, "value_key": "speed_kmh",
                    "ss_reference": SS_REFERENCE, **dec})
    return out


def par_balise(units: Iterable[Mapping],
               min_pairs: int = MURPHY_MIN_PAIRS,
               min_days: int = MURPHY_MIN_DAYS) -> list[dict]:
    """Une ligne par (balise, modèle, échéance) depuis des LIGNES.

    ⚠️ CE CHEMIN N'EST PLUS CELUI DU RUN NOCTURNE — il tiendrait les
    405 000 lignes de la fenêtre en mémoire, ce que le pavé de
    `accumule` explique. Il reste pour le rapport ponctuel
    (`python3 murphy.py`) et pour le banc, qui doit pouvoir partir de
    lignes lisibles. Le run, lui, remplit l'accumulateur au fil de la
    lecture (`score.replay_window`).

    ⚠️ UNE LIGNE SOUS LE PLANCHER EST PUBLIÉE QUAND MÊME, avec son
    `reason` et ses termes nuls. Une ligne absente et une ligne à zéro
    se lisent pareil dans un JSON, et c'est la première qu'on cherche
    le soir où une ingestion est morte (leçon du lot L1).
    """
    acc: dict[tuple, list] = {}
    for d in units:
        accumule(acc, (d["unit"], d["model"], d["lead_h"]), d.get(MURPHY_KEY))
    return par_balise_depuis_acc(acc, min_pairs, min_days)


def par_modele(lignes: Sequence[Mapping]) -> list[dict]:
    """Le résumé : MÉDIANE des décompositions par balise, modèle par
    modèle et échéance par échéance.

    ⛔ MÉDIANE DES DÉCOMPOSITIONS, PAS DÉCOMPOSITION DES MOMENTS
    ADDITIONNÉS — §4 de l'en-tête. Le second mesurerait la variance
    entre sites, pas la qualité du modèle sur un site.

    ⚠️ Et la médiane des trois termes NE RESPECTE PLUS l'identité
    `ss = r² − bc² − bs²` : trois médianes ne sont pas la médiane d'une
    somme. `ss` est donc médiané LUI AUSSI, séparément, et le champ
    `identity_holds` vaut `false` sur ces lignes pour que personne ne
    tente de la revérifier ici. Sur les lignes PAR BALISE, il vaut
    `true` — c'est là qu'elle est exacte.
    """
    par: dict[tuple, list[Mapping]] = defaultdict(list)
    for l in lignes:
        if l.get("reason") != "ok":
            continue
        par[(l["model"], l["lead_h"])].append(l)
    out = []
    for (model, lead), ls in sorted(par.items()):
        out.append({
            "model": model, "lead_h": lead,
            "n_balises": len(ls),
            # ⛔ `reason` EXPLICITE, ET C'EST UNE CICATRICE (02/09/2026).
            # Sans cette clé, `dire()` lisait `l.get("reason") != "ok"`
            # — vrai pour `None` — puis `l['reason']` : `KeyError`. La
            # boucle `for l in mur_modeles: print(MU.dire(l))` de
            # `score.py` tombait sur la PREMIÈRE ligne, et
            # `_publish_murphy` n'était jamais atteint. Le 29/08 le cache
            # de rejeu était creux (`n_ok = 0`, liste vide, boucle
            # muette) ; le 31/08 il s'est rempli (44 194 décomposées) et
            # `model_murphy.json` a cessé d'être republié — trois nuits
            # d'affilée, sous un `except` qui disait « la notation
            # continue ». Une ligne par modèle est TOUJOURS `ok` par
            # construction (le filtre l. 363 ne garde que celles-là).
            "reason": "ok",
            "r2": _med([l["r2"] for l in ls]),
            "bc": _med([l["bc"] for l in ls]),
            "bs": _med([l["bs"] for l in ls]),
            "ss": _med([l["ss"] for l in ls]),
            "sd_ratio": _med([l["sd_ratio"] for l in ls]),
            "identity_holds": False,
            "value_key": "speed_kmh",
            "ss_reference": SS_REFERENCE,
        })
    return out


def _med(xs):
    m = S.median(xs)
    return None if m is None else round(m, 4)


def dire(l: Mapping) -> str:
    """Une ligne de journal, lisible sans le JSON.

    ⚠️ Une ligne SANS clé `reason` est lue comme `ok` — jamais comme
    un motif à imprimer. C'est la seconde moitié du correctif du
    02/09 : `par_modele` pose la clé, et `dire` ne peut plus lever un
    `KeyError` sur une ligne qui ne l'aurait pas.
    """
    if l.get("reason", "ok") != "ok":
        return (f"  · {l['model']} +{l['lead_h']}h : {l['reason']} "
                f"({l.get('n_balises', l.get('n', 0))})")
    # La phrase qui compte : ce que la pente PEUT réparer, et le reste.
    quoi = ("AMPLITUDE (une pente peut aider)" if abs(l["bc"]) > 0.15
            else "rien de franc")
    if l["r2"] < 0.30:
        quoi = "TIMING (aucune pente n'y peut rien)"
    return (f"  · {l['model']} +{l['lead_h']}h : r² {l['r2']:+.3f} · "
            f"biais cond. {l['bc']:+.3f} · biais syst. {l['bs']:+.3f} "
            f"→ SS {l['ss']:+.3f} · {quoi}")


# ══════════════════════════════════════════════════════════════════
#  4. RAPPORT PONCTUEL (hors run)
# ══════════════════════════════════════════════════════════════════

def main() -> int:
    import argparse
    import json
    from datetime import datetime, timedelta, timezone

    ap = argparse.ArgumentParser(description="Décomposition de Murphy")
    ap.add_argument("--out", default=os.environ.get("MODEL_VERIF_OUT", "."),
                    help="racine de l'état et des archives (comme run.sh)")
    ap.add_argument("--jours", type=int, default=30)
    ap.add_argument("--day", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    # ⓘ Import TARDIF : `score.py` importe ce module.
    import pathlib
    import score as SC  # noqa: PLC0415

    day = (datetime.strptime(args.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
           if args.day
           else datetime.now(timezone.utc) - timedelta(days=1))
    root = pathlib.Path(args.out)
    units, bilan = SC.replay_window(root, day, SC._storage(), 0,
                                    n_days=args.jours, budget_new_days=0)
    print(f"▶ Murphy : {bilan}")
    lignes = par_balise(units)
    resume = par_modele(lignes)
    if args.json:
        print(json.dumps({"par_modele": resume, "par_balise": lignes},
                         indent=1, ensure_ascii=False))
    else:
        for r in resume:
            print(dire(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
