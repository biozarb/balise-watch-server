#!/usr/bin/env python3
"""test_duel.py — banc du DUEL APPARIÉ (lot L1, 27/08/2026).

Ce banc n'a pas pour but de vérifier que `duel.py` rend un objet de la
bonne forme : il vérifie qu'il MESURE ce que son nom promet, sur des
scènes dont on connaît la réponse parce qu'on les a fabriquées.

Les deux scènes exigées par le lot, et pourquoi :

  1. **EFFET NUL.** Deux modèles identiques au bruit près : l'intervalle
     doit CONTENIR zéro et le verdict être `not_separable`. Sans cette
     scène, un duel qui trouverait un gagnant partout passerait pour
     puissant.

  2. **EFFET 0,03 km/h** — l'ordre de grandeur réel de l'apport de PI
     (mesuré −0,031 le 25/08). L'intervalle doit EXCLURE zéro une fois
     la fenêtre assez longue, et le bon modèle doit être nommé.

⛔ ET LES DEUX SCÈNES SONT IRRÉGULIÈRES DANS LA DIMENSION TESTÉE
(piège nº 2 de la phase B, 26/08 : un jeu trop régulier rend la
mutation indétectable, trois fois de suite). Ici la dimension testée
est la balise-jour : le nombre de balises change chaque jour, les
balises présentes changent, certaines manquent d'un seul côté, et le
bruit n'est pas le même partout. Un jeu à 60 balises tous les jours
laisserait passer « la moyenne cumulée est la moyenne des moyennes
journalières », qui est FAUX et que la scène 6 attrape.

Aucun `random` : générateur congruentiel maison, graine explicite.

Usage :
    python3 test_duel.py
"""
from __future__ import annotations

import sys

import duel as D
import inference as INF
import scoring as S

OK = 0
KO = 0


def check(label: str, cond: bool, detail: str = ""):
    global OK, KO
    if cond:
        OK += 1
    else:
        KO += 1
        print(f"  ❌ {label}" + (f"\n       {detail}" if detail else ""))


class LCG:
    """Générateur congruentiel — reproductible, et qui ne sert QU'au banc."""

    def __init__(self, seed: int = 20260827):
        self.s = seed & 0xFFFFFFFF

    def u(self) -> float:
        self.s = (1103515245 * self.s + 12345) & 0x7FFFFFFF
        return self.s / 0x7FFFFFFF

    def normal(self) -> float:
        return sum(self.u() for _ in range(12)) - 6.0


def ligne(day: str, unit: str, model: str, val: float,
          lead_h: int = 6, source: str | None = None,
          fcst_src: str = "own_archive") -> dict:
    """Une ligne `model_verif_daily` comme la base en rend."""
    src, sid = unit.split(":", 1)
    return {"day": day, "source": source or src, "station_id": sid,
            "model": model, "lead_h": lead_h, "fcst_src": fcst_src,
            "err_vec_rms": val, "err_vec_med": val * 0.9}


def scene(n_days: int, effet_b: float, rnd: LCG,
          day_sd: float = 0.06, bruit_sd: float = 0.28,
          base: float = 4.1) -> list[dict]:
    """Deux modèles sur des balise-jours IRRÉGULIERS.

    `effet_b` est retranché à B : `effet_b > 0` ⟹ B meilleur ⟹
    `diff = err(A) − err(B)` POSITIF. C'est l'orientation qu'il faut
    lire dans les assertions, et elle est écrite ici plutôt que devinée
    là-bas.

    ⚠️ L'erreur de B n'est PAS recalculée depuis un intermédiaire produit
    par `duel.py` (piège nº 1 de la phase B) : les deux séries sont
    fabriquées ici, terme à terme, et la différence attendue est connue
    avant que le module ne soit appelé.
    """
    rows: list[dict] = []
    for i in range(n_days):
        jour = f"2026-07-{i + 1:02d}"
        # Irrégulier : entre 22 et 61 balises, jamais le même nombre.
        n_st = 22 + (i * 7) % 40
        effet_jour = rnd.normal() * day_sd * 3          # niveau commun du jour
        # ⛔ ET LA PART DU JOUR QUI VIT DANS LA DIFFÉRENCE. Sans elle,
        # `err_a` s'annule entièrement dans `diff` et les balise-jours
        # deviennent indépendants : le bootstrap par BLOCS n'aurait plus
        # rien à respecter, et une fenêtre de 9 jours trancherait ce
        # qu'il faut 15 à 40 jours pour trancher (mesuré en écrivant ce
        # banc). C'est la sd(jour) ≈ 0,06 km/h reconstruite en phase B.
        jour_diff = rnd.normal() * day_sd
        for k in range(n_st):
            # Les identifiants glissent d'un jour à l'autre : une balise
            # n'est pas présente tous les jours.
            unit = f"pioupiou:{100 + (k + i * 3) % 90}"
            err_a = base + rnd.normal() * bruit_sd + effet_jour
            err_b = err_a - effet_b - jour_diff + rnd.normal() * bruit_sd * 0.5
            rows.append(ligne(jour, unit, "A", round(err_a, 4)))
            rows.append(ligne(jour, unit, "B", round(err_b, 4)))
    return rows


PAIRE = (("A", "B"),)

# ══════════════════════════════════════════════════════════════════
print("\n── 1. EFFET NUL : l'intervalle doit contenir zéro ──")
# ══════════════════════════════════════════════════════════════════

rnd = LCG(11)
d0 = D.duel_paire(scene(20, 0.0, rnd), "A", "B")
check("effet nul → verdict `not_separable`",
      d0["verdict"] == "not_separable", f"{d0['verdict']} / {d0}")
check("… l'intervalle CONTIENT zéro",
      d0["ci_low"] is not None and d0["ci_low"] < 0 < d0["ci_high"],
      f"[{d0['ci_low']} ; {d0['ci_high']}]")
check("… et la moyenne est petite devant l'effet cherché (0,03)",
      abs(d0["mean_diff"]) < 0.03, f"{d0['mean_diff']}")
check("… `separates` est False, pas None",
      d0["separates"] is False)

# ══════════════════════════════════════════════════════════════════
print("── 2. EFFET 0,03 km/h : il doit être VU, et du bon côté ──")
# ══════════════════════════════════════════════════════════════════

rnd = LCG(23)
d1 = D.duel_paire(scene(40, 0.03, rnd), "A", "B")
check("effet 0,03 sur 40 jours → l'intervalle EXCLUT zéro",
      d1["separates"] is True,
      f"[{d1['ci_low']} ; {d1['ci_high']}] n={d1['n_pairs']}")
check("… et c'est B qui est nommé meilleur (B a 0,03 de moins)",
      d1["verdict"] == "b_better", d1["verdict"])
# ⚠️ TOLÉRANCE À ±0,02 ET PAS PLUS SERRÉE, POUR UNE RAISON CHIFFRÉE :
# avec sd(jour) = 0,06 km/h sur 40 jours, l'erreur-type de la moyenne
# vaut ~0,01 — un banc qui exigerait ±0,005 rougirait sur un tirage
# parfaitement légitime, et on l'aurait « réparé » en affaiblissant la
# scène.
check("… la moyenne retrouve l'effet posé à ±0,02 (≈ 2 erreurs-types)",
      d1["mean_diff"] is not None and abs(d1["mean_diff"] - 0.03) < 0.02,
      f"{d1['mean_diff']}")
check("… la médiane aussi",
      d1["median_diff"] is not None and abs(d1["median_diff"] - 0.03) < 0.02,
      f"{d1['median_diff']}")

# ⛔ ET LE CONTRÔLE QUI COMPTE VRAIMENT : LA PUISSANCE, PAS UN TIRAGE.
# La première version de ce banc affirmait « 9 jours ne tranchent pas »
# sur UNE graine — et c'était faux : avec la graine 23, neuf jours
# tranchent (moyenne 0,041, IC [+0,013 ; +0,062]), parce que le tirage
# des neuf jours penchait. Épingler cette graine aurait fabriqué un banc
# qui protège une CHANCE. On mesure donc la fréquence sur dix scènes
# indépendantes : c'est la propriété annoncée par l'audit §2.4
# (« verdict attendu en 15 à 40 jours »), et elle ne dépend d'aucune
# graine en particulier.
GRAINES = [101, 202, 303, 404, 505, 606, 707, 808, 909, 1010]
long_ = sum(D.duel_paire(scene(40, 0.03, LCG(g)), "A", "B")["separates"]
            is True for g in GRAINES)
court = sum(D.duel_paire(scene(9, 0.03, LCG(g)), "A", "B")["separates"]
            is True for g in GRAINES)
check("40 jours tranchent le plus souvent (≥ 6 scènes sur 10)",
      long_ >= 6, f"{long_}/10")
check("9 jours tranchent NETTEMENT moins souvent qu'une fenêtre longue",
      court < long_, f"court {court}/10 · long {long_}/10")

# ⛔ ET LA FABRIQUE DE FAUX GAGNANTS, MESURÉE : sur des scènes à effet
# NUL, un duel qui conclurait souvent serait pire qu'inutile. Nominal
# 5 % ; on refuse au-delà de 2 sur 10 (une seule scène de plus qu'un
# tirage 95 % ne surprend pas ; trois désigneraient un intervalle trop
# étroit, exactement le défaut i.i.d. que le lot G a corrigé).
faux = sum(D.duel_paire(scene(40, 0.0, LCG(g)), "A", "B")["separates"]
           is True for g in GRAINES)
check("effet NUL sur 40 jours → au plus 2 scènes sur 10 concluent",
      faux <= 2, f"{faux}/10 fausses conclusions")

# ⛔ ET LA SCÈNE QUI SÉPARE LA MOYENNE DE LA MÉDIANE. Elle a été
# ajoutée parce qu'une MUTATION est passée : « le verdict lit la
# moyenne » laissait le banc vert, toutes les scènes précédentes ayant
# une moyenne et une médiane du même signe. Ici la plupart des balises
# penchent d'un côté (+0,05) et deux journalières énormes (−5) tirent la
# moyenne de l'autre. Le verdict PUBLIÉ doit suivre ce que l'intervalle
# BORNE — la médiane — sinon la ligne affirme un gagnant que son propre
# intervalle ne soutient pas.
rows_asym = []
for i in range(12):
    j = f"2026-07-{i + 1:02d}"
    for k in range(18):
        rows_asym += [ligne(j, f"pioupiou:{k}", "A", 4.05),
                      ligne(j, f"pioupiou:{k}", "B", 4.00)]
    for k in (90, 91):
        rows_asym += [ligne(j, f"pioupiou:{k}", "A", 1.0),
                      ligne(j, f"pioupiou:{k}", "B", 6.0)]
d1d = D.duel_paire(rows_asym, "A", "B")
check("scène asymétrique : moyenne NÉGATIVE, médiane POSITIVE",
      d1d["mean_diff"] < 0 < d1d["median_diff"],
      f"moy {d1d['mean_diff']} / méd {d1d['median_diff']}")
check("… l'intervalle (de la médiane) exclut zéro par le haut",
      d1d["ci_low"] is not None and d1d["ci_low"] > 0,
      f"[{d1d['ci_low']} ; {d1d['ci_high']}]")
check("… et le verdict suit la MÉDIANE, ce que l'intervalle borne",
      d1d["verdict"] == "b_better", d1d["verdict"])

# ══════════════════════════════════════════════════════════════════
print("── 3. L'APPARIEMENT : ce qui n'a pas de jumeau est ÉCARTÉ ──")
# ══════════════════════════════════════════════════════════════════

rows = [
    ligne("2026-07-01", "pioupiou:2", "A", 5.0),      # sans jumeau B
    ligne("2026-07-02", "pioupiou:9", "B", 3.0),      # sans jumeau A
]
for j in ("2026-07-01", "2026-07-02"):
    for u in (1, 3, 5):
        rows += [ligne(j, f"pioupiou:{u}", "A", 4.0),
                 ligne(j, f"pioupiou:{u}", "B", 3.5)]
d2 = D.duel_paire(rows, "A", "B")
check("seules les balise-jours PORTANT LES DEUX entrent",
      d2["n_pairs"] == 6, f"{d2['n_pairs']}")
check("… et toutes les diffs valent +0,5 (A moins bon de 0,5)",
      d2["mean_diff"] == 0.5 and d2["median_diff"] == 0.5,
      f"{d2['mean_diff']} / {d2['median_diff']}")
check("… deux jours seulement → `window_too_short`, PAS un intervalle",
      d2["verdict"] == "window_too_short" and d2["ci_low"] is None,
      d2["verdict"])
check("… mais n, moyenne et médiane sont quand même publiés",
      d2["n_pairs"] == 6 and d2["mean_diff"] is not None)

# ⚠️ Sous le quorum de paires, le motif est AUTRE — et les deux motifs
# ne doivent pas se confondre : « pas assez de jours » se répare en
# attendant, « pas assez de balises » se répare en cherchant pourquoi.
d2q = D.duel_paire(rows[:2] + [ligne("2026-07-01", "pioupiou:1", "A", 4.0),
                               ligne("2026-07-01", "pioupiou:1", "B", 3.5)],
                   "A", "B")
check("moins de 4 paires → `too_few_pairs`, pas `window_too_short`",
      d2q["verdict"] == "too_few_pairs" and d2q["n_pairs"] == 1,
      f"{d2q['verdict']} / {d2q['n_pairs']}")

# La balise « 1 » du réseau A et la balise « 1 » d'un AUTRE réseau ne
# sont pas la même balise — et rien en base ne l'interdit.
rows_coll = [
    ligne("2026-07-01", "pioupiou:1", "A", 4.0, source="pioupiou"),
    ligne("2026-07-01", "windsmobi:1", "B", 3.5, source="windsmobi"),
]
d2b = D.duel_paire(rows_coll, "A", "B", source=None)
check("deux réseaux, même numéro de balise → AUCUN appariement",
      d2b["n_pairs"] == 0, f"{d2b['n_pairs']}")

# ══════════════════════════════════════════════════════════════════
print("── 4. LE DOUBLON DE CHAÎNE : écarté ET compté ──")
# ══════════════════════════════════════════════════════════════════

rows_dup = [
    ligne("2026-07-01", "pioupiou:1", "A", 4.0, fcst_src="own_archive"),
    ligne("2026-07-01", "pioupiou:1", "A", 9.9, fcst_src="autre_chaine"),
    ligne("2026-07-01", "pioupiou:1", "B", 3.5),
    ligne("2026-07-01", "pioupiou:2", "A", 4.0),
    ligne("2026-07-01", "pioupiou:2", "B", 3.5),
]
d3 = D.duel_paire(rows_dup, "A", "B")
check("une balise-jour à DEUX `fcst_src` est écartée entière",
      d3["n_pairs"] == 1, f"{d3['n_pairs']}")
check("… et le duel le COMPTE (pas de choix silencieux)",
      d3["excluded_duplicates"] == 1, f"{d3['excluded_duplicates']}")
check("… la valeur aberrante du doublon n'a PAS contaminé la moyenne",
      d3["mean_diff"] == 0.5, f"{d3['mean_diff']}")

# ══════════════════════════════════════════════════════════════════
print("── 5. LES FILTRES : lead et réseau, sinon on compare autre chose ──")
# ══════════════════════════════════════════════════════════════════

rows_mix = [
    ligne("2026-07-01", "pioupiou:1", "A", 4.0, lead_h=6),
    ligne("2026-07-01", "pioupiou:1", "B", 3.5, lead_h=6),
    ligne("2026-07-01", "pioupiou:1", "A", 8.0, lead_h=24),
    ligne("2026-07-01", "pioupiou:1", "B", 7.0, lead_h=24),
    ligne("2026-07-01", "windsmobi:9", "A", 4.0, source="windsmobi"),
    ligne("2026-07-01", "windsmobi:9", "B", 2.0, source="windsmobi"),
]
d4 = D.duel_paire(rows_mix, "A", "B")
check("lead 6 seul : une paire, pas trois",
      d4["n_pairs"] == 1, f"{d4['n_pairs']}")
check("… et la diff est celle du lead 6 (+0,5), pas celle du lead 24 (+1,0)",
      d4["mean_diff"] == 0.5, f"{d4['mean_diff']}")
d4b = D.duel_paire(rows_mix, "A", "B", lead_h=24)
check("lead 24 demandé explicitement → la paire du lead 24",
      d4b["n_pairs"] == 1 and d4b["mean_diff"] == 1.0,
      f"{d4b['n_pairs']} / {d4b['mean_diff']}")
d4c = D.duel_paire(rows_mix, "A", "B", source=None)
check("source=None → les deux réseaux entrent",
      d4c["n_pairs"] == 2, f"{d4c['n_pairs']}")

# ══════════════════════════════════════════════════════════════════
print("── 6. LA SÉRIE JOURNALIÈRE ET LE CUMUL ──")
# ══════════════════════════════════════════════════════════════════

# Jours de tailles TRÈS différentes : c'est là que « moyenne cumulée »
# et « moyenne des moyennes journalières » divergent.
rows_cum = []
for u in range(1, 11):                       # jour 1 : 10 balises, diff +1
    rows_cum += [ligne("2026-07-01", f"pioupiou:{u}", "A", 5.0),
                 ligne("2026-07-01", f"pioupiou:{u}", "B", 4.0)]
rows_cum += [ligne("2026-07-02", "pioupiou:1", "A", 5.0),   # jour 2 : 1, diff +11
             ligne("2026-07-02", "pioupiou:1", "B", -6.0)]
d5 = D.duel_paire(rows_cum, "A", "B")
serie = d5["daily"]
check("une entrée par jour, dans l'ordre",
      [j["day"] for j in serie] == ["2026-07-01", "2026-07-02"])
check("les n journaliers sont ceux posés (10 puis 1)",
      [j["n"] for j in serie] == [10, 1], f"{[j['n'] for j in serie]}")
check("moyenne du jour 2 = +11", serie[1]["mean"] == 11.0, f"{serie[1]['mean']}")
check("le CUMUL pondère par balise-jour : (10×1 + 11)/11 = 1,909…",
      abs(serie[1]["cum_mean"] - 21 / 11) < 1e-4, f"{serie[1]['cum_mean']}")
check("… et PAS la moyenne des moyennes journalières (6,0)",
      abs(serie[1]["cum_mean"] - 6.0) > 1e-3, f"{serie[1]['cum_mean']}")
check("le cumul de n suit", [j["cum_n"] for j in serie] == [10, 11])
check("la moyenne globale publiée est celle du cumul final",
      abs(d5["mean_diff"] - serie[-1]["cum_mean"]) < 1e-4,
      f"{d5['mean_diff']} / {serie[-1]['cum_mean']}")

# ══════════════════════════════════════════════════════════════════
print("── 7. CE QUE LA LIGNE PUBLIÉE DOIT PORTER (banc POSITIF) ──")
# ══════════════════════════════════════════════════════════════════

# ⛔ Piège nº 9 de BUGS.md : jamais « tel mot est absent ». On vérifie
# la PRÉSENCE et la VALEUR de ce qui doit voyager.
attendus = ("model_a", "model_b", "sign", "value_key", "lead_h", "source",
            "n_pairs", "n_days", "first_day", "last_day", "mean_diff",
            "median_diff", "ci_on", "ci_low", "ci_high", "block_days",
            "ci_reason", "separates", "verdict", "excluded_duplicates",
            "truncated_by_retention", "daily")
check("tous les champs attendus sont là",
      all(k in d1 for k in attendus),
      f"manquants : {[k for k in attendus if k not in d1]}")
check("le SIGNE voyage avec le chiffre, en toutes lettres",
      "negatif = a meilleur" in d1["sign"], d1["sign"])
check("`ci_on` NOMME ce que l'intervalle borne (la médiane)",
      d1["ci_on"] == "median", d1["ci_on"])
check("la colonne mesurée est nommée sur la ligne",
      d1["value_key"] == "err_vec_rms", d1["value_key"])
check("`value_key` par défaut du module = err_vec_rms (pas err_vec_med)",
      D.DUEL_VALUE_KEY == "err_vec_rms", D.DUEL_VALUE_KEY)
check("la fenêtre du duel ne dépasse pas la rétention de la table",
      D.DUEL_DAYS <= 30, f"{D.DUEL_DAYS}")

# ⚠️ Le drapeau de troncature n'est pas décoratif : c'est lui qui dira,
# le jour venu, que « cumul depuis la naissance de la paire » est devenu
# faux (cf. `duel.DUEL_DAYS`).
d6 = D.duel_paire(scene(12, 0.0, LCG(5)), "A", "B", fenetre_jours=12)
check("fenêtre pleine → `truncated_by_retention` VRAI",
      d6["truncated_by_retention"] is True, f"{d6['n_days']}")
d7 = D.duel_paire(scene(12, 0.0, LCG(5)), "A", "B", fenetre_jours=30)
check("fenêtre plus profonde que les données → drapeau FAUX",
      d7["truncated_by_retention"] is False, f"{d7['n_days']}")

# ⚠️ La ligne de journal doit se lire SANS le JSON (banc positif sur le
# texte, pas sur une absence).
txt = D.dire(d1)
check("le journal nomme les deux modèles, le n et le verdict",
      "A ↔ B" in txt and f"n = {d1['n_pairs']}" in txt
      and d1["verdict"] in txt, txt)

# ══════════════════════════════════════════════════════════════════
print("── 8. LES TROIS PAIRES SUIVIES, ET LA REQUÊTE ──")
# ══════════════════════════════════════════════════════════════════

check("trois paires suivies", len(D.PAIRES_SUIVIES) == 3)
check("… dont le duel de la question du lot",
      ("agrume", "agrume_pi") in D.PAIRES_SUIVIES)
check("… dont le TÉMOIN de chaîne agrume ↔ AROME HD",
      ("agrume", "meteofrance_arome_france_hd") in D.PAIRES_SUIVIES)
check("… dont arome_r2 ↔ AROME HD (le plancher de chaîne)",
      ("arome_r2", "meteofrance_arome_france_hd") in D.PAIRES_SUIVIES)

q = D.query_duel("2026-07-29")
for morceau in ("day=gte.2026-07-29", "lead_h=eq.6", "source=eq.pioupiou",
                "err_vec_rms", "agrume", "agrume_pi", "arome_r2",
                "meteofrance_arome_france_hd"):
    check(f"la requête porte `{morceau}`", morceau in q, q)
check("… et elle ne demande PAS toutes les colonnes",
      "select=*" not in q, q)

vide = D.duels([])
check("aucune donnée → trois lignes quand même, à zéro",
      len(vide) == 3 and all(v["n_pairs"] == 0 for v in vide))
check("… avec le motif dit, pas un silence",
      all(v["verdict"] == "too_few_pairs" for v in vide),
      f"{[v['verdict'] for v in vide]}")

# ══════════════════════════════════════════════════════════════════
print("── 9. LES EMPRUNTS : rien n'est réécrit ──")
# ══════════════════════════════════════════════════════════════════

# Le duel doit passer par les fonctions du lot G, pas par une copie.
rows_emprunt = scene(12, 0.05, LCG(7))
a = [r for r in rows_emprunt if r["model"] == "A"]
b = [r for r in rows_emprunt if r["model"] == "B"]
for r in a + b:
    r["unit"] = f"{r['source']}:{r['station_id']}"
attendu = INF.block_bootstrap_ci(
    INF.paired_differences(a, b, value_key="err_vec_rms"))
mesure = D.duel_paire(rows_emprunt, "A", "B")
check("l'IC du duel est BIT À BIT celui d'`inference.block_bootstrap_ci`",
      mesure["ci_low"] == D._arrondi(attendu.ci_low)
      and mesure["ci_high"] == D._arrondi(attendu.ci_high)
      and mesure["n_pairs"] == attendu.n_pairs,
      f"{mesure['ci_low']}/{attendu.ci_low}")
check("… et la médiane publiée est celle de l'IC, pas un second calcul",
      mesure["median_diff"] == D._arrondi(attendu.median))

# `_arrondi` est une copie de `score._r` (import circulaire interdit) :
# le banc compare les deux, pour que la copie ne dérive pas en silence.
import score as SC  # noqa: E402
for x in (None, float("nan"), 0.123456, -1.99995, 3.0):
    check(f"_arrondi({x!r}) == score._r({x!r})",
          repr(D._arrondi(x)) == repr(SC._r(x)),
          f"{D._arrondi(x)} / {SC._r(x)}")

# ══════════════════════════════════════════════════════════════════
print("── 10. L'OBJET PUBLIÉ, pas le producteur (piège nº 7) ──")
# ══════════════════════════════════════════════════════════════════

# ⛔ `_publish_light` recopie des champs NOMMÉS. Vérifier `duels()` ne
# prouve RIEN sur ce qui part vers R2 : c'est le corps réellement mis
# dans `st.put` qu'on lit ici. (Le contrôle final du lot va plus loin
# encore : lire l'objet servi par R2 après une vraie nuit.)
import json as _json  # noqa: E402
import pathlib as _pathlib  # noqa: E402
from datetime import datetime as _dt, timezone as _tz  # noqa: E402

sys.path.insert(0, str(_pathlib.Path(__file__).resolve().parent.parent / "tools"))


class FauxR2:
    """Un R2 qui garde ce qu'on lui donne — et rien de plus."""

    def __init__(self):
        self.objets: dict[str, bytes] = {}

    def put(self, cle, corps, cache_control=None):
        self.objets[cle] = corps

    def bilan(self):
        pass


faux = FauxR2()
SC._publish_light(faux, [], [], {"since": "2026-08-01", "nights": 3},
                  _dt(2026, 8, 27, tzinfo=_tz.utc), False, [d1, d0])
corps = _json.loads(faux.objets["model_scores_light.json"].decode("utf-8"))
check("`model_scores_light.json` porte un bloc `duels`",
      "duels" in corps, f"{sorted(corps)}")
check("… avec les deux duels donnés, dans l'ordre",
      len(corps["duels"]) == 2
      and corps["duels"][0]["model_a"] == "A", f"{corps.get('duels')}")
check("… le signe, la colonne et le n ont VOYAGÉ jusqu'au corps publié",
      corps["duels"][0]["value_key"] == "err_vec_rms"
      and "negatif = a meilleur" in corps["duels"][0]["sign"]
      and corps["duels"][0]["n_pairs"] == d1["n_pairs"])
check("… la série journalière aussi (le cumul est la moitié de l'intérêt)",
      len(corps["duels"][0]["daily"]) == len(d1["daily"]))
check("… et le duel n'a PAS contaminé `scores` (ce n'est pas un rang)",
      corps["scores"] == [])
check("… ni ajouté de `rank` où que ce soit dans le bloc duels",
      all("rank" not in k for d in corps["duels"] for k in d))

faux2 = FauxR2()
SC._publish_light(faux2, [], [], {}, _dt(2026, 8, 27, tzinfo=_tz.utc), False)
corps2 = _json.loads(faux2.objets["model_scores_light.json"].decode("utf-8"))
check("sans duels, la clé existe quand même (liste vide, pas d'absence)",
      corps2.get("duels") == [], f"{corps2.get('duels')}")

# ══════════════════════════════════════════════════════════════════
print(f"\n{'✅' if KO == 0 else '❌'} {OK} assertions vertes, {KO} rouges.\n")
sys.exit(1 if KO else 0)
