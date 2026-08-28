#!/usr/bin/env python3
"""test_inference.py — banc d'essai du socle statistique du lot G.

    Session 09/08/2026.

Ce banc a une particularité : il ne se contente pas de vérifier que
les fonctions rendent quelque chose de la bonne forme. Il vérifie
qu'elles font ce que leur NOM promet, sur des données dont on connaît
la réponse parce qu'on les a fabriquées.

Trois preuves, dans l'ordre d'importance :

  1. **Le bloc est un bloc.** Sur des données à corrélation
     journalière CONNUE, l'IC par blocs doit être NETTEMENT plus large
     que l'IC i.i.d. Sans ce contrôle, on ne saurait pas dire si le
     bootstrap par blocs a été implémenté ou seulement nommé — et un
     bootstrap par blocs qui tire en réalité i.i.d. rendrait des
     intervalles trop étroits, donc de faux gagnants, exactement le
     défaut qu'il est censé corriger.

  2. **Le bloc couvre.** Sur 60 jeux tirés du même modèle, la
     proportion de fois où l'intervalle contient la vraie valeur doit
     s'approcher de 95 % pour les blocs, et rester nettement en
     dessous pour l'i.i.d. C'est la propriété qui compte vraiment :
     « plus large » ne vaut que si c'est plus large du bon montant.

  3. **Le poids emprunté dit la vérité.** Une case à une seule
     balise-jour doit rendre une estimation proche du parent et un
     poids emprunté proche de 1 ; une case bien fournie l'inverse.

Aucun `random` : un générateur congruentiel maison, graine explicite.
Un banc qui bouge d'une exécution à l'autre ne prouve rien.

Usage :
    python3 test_inference.py
"""
from __future__ import annotations

import math
import sys

import inference as I
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

    def __init__(self, seed: int = 12345):
        self.s = seed & 0xFFFFFFFF

    def u(self) -> float:
        self.s = (1103515245 * self.s + 12345) & 0x7FFFFFFF
        return self.s / 0x7FFFFFFF

    def normal(self) -> float:
        # Somme de 12 uniformes − 6 : approximation d'une normale
        # centrée réduite, suffisante et sans dépendance externe.
        return sum(self.u() for _ in range(12)) - 6.0


def make_diffs(rnd: LCG, n_days: int, n_stations: int,
               day_sd: float, noise_sd: float, mean: float = 0.0):
    """Fabrique des différences appariées à corrélation journalière connue.

    `day_sd` est l'écart-type de l'effet JOURNÉE — la situation
    synoptique, partagée par toutes les balises du jour. `noise_sd`
    est le bruit propre à chaque balise-jour. Quand `day_sd` domine,
    les 30 balises d'un même jour n'apportent pas 30 informations mais
    à peu près une seule : c'est exactement ce qu'un bootstrap i.i.d.
    ignore.
    """
    out = []
    for d in range(n_days):
        eff = rnd.normal() * day_sd
        day = f"2026-07-{d + 1:02d}"
        for st in range(n_stations):
            out.append(I.PairedDiff(day=day, unit=f"p:{st}",
                                    diff=mean + eff + rnd.normal() * noise_sd))
    return out


# ══════════════════════════════════════════════════════════════════
print("\n── 1. appariement ──")

rows_a = [{"day": "2026-08-01", "unit": "p:1", "err_vec_med": 5.0},
          {"day": "2026-08-01", "unit": "p:2", "err_vec_med": 7.0},
          {"day": "2026-08-02", "unit": "p:1", "err_vec_med": 6.0},
          {"day": "2026-08-03", "unit": "p:9", "err_vec_med": 4.0}]
rows_b = [{"day": "2026-08-01", "unit": "p:1", "err_vec_med": 4.0},
          {"day": "2026-08-01", "unit": "p:2", "err_vec_med": 9.0},
          {"day": "2026-08-02", "unit": "p:1", "err_vec_med": 6.5},
          {"day": "2026-08-02", "unit": "p:7", "err_vec_med": 3.0}]
d = I.paired_differences(rows_a, rows_b)
check("seules les balise-jours présentes des DEUX côtés sont appariées",
      len(d) == 3, f"n={len(d)}")
check("aucune balise-jour orpheline n'est comblée",
      all((x.day, x.unit) != ("2026-08-03", "p:9") for x in d))
check("le signe est err(A) − err(B)",
      [round(x.diff, 6) for x in d] == [1.0, -2.0, -0.5],
      str([x.diff for x in d]))
check("une valeur non finie d'un côté écarte la paire",
      len(I.paired_differences(
          [{"day": "d", "unit": "u", "err_vec_med": None}],
          [{"day": "d", "unit": "u", "err_vec_med": 3.0}])) == 0)

# ══════════════════════════════════════════════════════════════════
print("── 2. refus explicites plutôt qu'intervalles fabriqués ──")

short = make_diffs(LCG(1), n_days=2, n_stations=40, day_sd=2.0, noise_sd=1.0)
ci = I.block_bootstrap_ci(short)
check("deux jours → window_too_short (l'état réel de l'archive au 09/08)",
      ci.reason == "window_too_short", ci.reason)
check("… et aucun intervalle n'est publié malgré 80 paires",
      ci.ci_low is None and ci.ci_high is None)
check("… mais la médiane brute reste disponible", ci.median is not None)
check("… et separates rend None, pas False",
      ci.separates is None)

tiny = make_diffs(LCG(2), n_days=20, n_stations=1, day_sd=1.0, noise_sd=1.0)[:3]
check("moins de 4 paires → too_few_pairs",
      I.block_bootstrap_ci(tiny).reason == "too_few_pairs")

# ══════════════════════════════════════════════════════════════════
print("── 3. LE BLOC EST UN BLOC (corrélation journalière connue) ──")

corr = make_diffs(LCG(7), n_days=20, n_stations=30, day_sd=3.0, noise_sd=1.0)
blk = I.block_bootstrap_ci(corr)
iid = I.iid_bootstrap_ci(corr)
w_blk = blk.ci_high - blk.ci_low
w_iid = iid.ci_high - iid.ci_low
check("l'IC par blocs se calcule (20 jours, 600 paires)", blk.reason == "ok")
check("la longueur de bloc respecte le plancher synoptique de 3 jours",
      blk.block_days is not None and blk.block_days >= I.MIN_BLOCK_DAYS,
      f"L={blk.block_days}")
check("l'IC par blocs est PLUS LARGE que l'i.i.d. sur données corrélées",
      w_blk > w_iid, f"blocs={w_blk:.3f} vs iid={w_iid:.3f}")
check("… et nettement : au moins 2× (l'effet journée domine)",
      w_blk > 2 * w_iid, f"rapport={w_blk / w_iid:.2f}")
print(f"     ⓘ largeur blocs {w_blk:.3f} km/h · i.i.d. {w_iid:.3f} km/h "
      f"· rapport {w_blk / w_iid:.2f}")

# ⚠️ Moyenné sur six jeux, et pas mesuré sur un seul. Le rapport des
# largeurs d'un unique tirage varie de ±40 % d'une graine à l'autre :
# une assertion posée sur un seul jeu passerait ou tomberait selon la
# graine, ce qui ferait d'elle un thermomètre du hasard et non du code.
ratios = []
for s in range(6):
    flat = make_diffs(LCG(80 + s), n_days=20, n_stations=30,
                      day_sd=0.0, noise_sd=3.0)
    wb = I.block_bootstrap_ci(flat)
    wi = I.iid_bootstrap_ci(flat)
    ratios.append((wb.ci_high - wb.ci_low) / (wi.ci_high - wi.ci_low))
ratio = sum(ratios) / len(ratios)
check("sans effet journée, les deux intervalles se rejoignent",
      0.7 < ratio < 1.5, f"rapport moyen={ratio:.2f} sur {ratios}")
print(f"     ⓘ sans corrélation, rapport moyen blocs/i.i.d. = {ratio:.2f}")

check("le bootstrap par blocs est DÉTERMINISTE",
      I.block_bootstrap_ci(corr).ci_low == blk.ci_low
      and I.block_bootstrap_ci(corr).ci_high == blk.ci_high)
check("… et change si la graine change",
      I.block_bootstrap_ci(corr, seed=1234).ci_low != blk.ci_low)

# ══════════════════════════════════════════════════════════════════
print("── 4. LE BLOC COUVRE (60 réplications) ──")

n_rep, cov_blk, cov_iid = 60, 0, 0
for r in range(n_rep):
    sample = make_diffs(LCG(1000 + r), n_days=16, n_stations=25,
                        day_sd=3.0, noise_sd=1.0, mean=0.0)
    b = I.block_bootstrap_ci(sample, iterations=200)
    i2 = I.iid_bootstrap_ci(sample, iterations=200)
    if b.ci_low is not None and b.ci_low <= 0 <= b.ci_high:
        cov_blk += 1
    if i2.ci_low is not None and i2.ci_low <= 0 <= i2.ci_high:
        cov_iid += 1
p_blk, p_iid = cov_blk / n_rep, cov_iid / n_rep
print(f"     ⓘ couverture réelle d'un IC 95 % : blocs {p_blk:.0%} · "
      f"i.i.d. {p_iid:.0%} (vraie différence = 0)")
check("l'IC par blocs couvre la vraie valeur au moins 80 % du temps",
      p_blk >= 0.80, f"{p_blk:.0%}")
check("l'IC i.i.d. SOUS-COUVRE nettement — c'est la fabrique de faux gagnants",
      p_iid < p_blk - 0.15, f"blocs {p_blk:.0%} vs iid {p_iid:.0%}")

# ══════════════════════════════════════════════════════════════════
print("── 5. le verdict : réel ET utile, jamais l'un des deux ──")

def rows(n_days, n_st, base, rnd, day_sd=0.5, noise=0.4):
    out = []
    for dd in range(n_days):
        eff = rnd.normal() * day_sd
        for st in range(n_st):
            out.append({"day": f"2026-07-{dd + 1:02d}", "unit": f"p:{st}",
                        "err_vec_med": base + eff + rnd.normal() * noise})
    return out

r0 = LCG(21)
a = rows(16, 20, 4.0, r0)
b = rows(16, 20, 8.0, r0)
v = I.compare_pair("A", "B", a, b)
check("un écart large et net donne un gagnant", v.winner == "A",
      f"{v.winner} / {v.reason}")
check("… avec un IC qui exclut zéro", v.ci.separates is True)

r1 = LCG(22)
a2 = rows(16, 20, 6.00, r1)
b2 = rows(16, 20, 6.05, r1)
v2 = I.compare_pair("A", "B", a2, b2)
check("un écart minuscule ne donne pas de gagnant", v2.winner is None, v2.reason)
check("… et la raison n'est pas 'insufficient' mais un vrai motif",
      v2.reason in ("tied", "not_separable"), v2.reason)

# Significatif mais inutile : 8 % d'écart, très bien mesuré.
r2 = LCG(23)
a3 = rows(24, 40, 6.00, r2, day_sd=0.15, noise=0.2)
b3 = rows(24, 40, 6.50, r2, day_sd=0.15, noise=0.2)
v3 = I.compare_pair("A", "B", a3, b3)
check("un écart bien mesuré mais sous 15 % reste 'tied' (significatif ≠ applicable)",
      v3.winner is None and v3.reason == "tied",
      f"{v3.reason} gap={v3.relative_gap:.3f}" if v3.relative_gap else v3.reason)
check("… et l'IC, lui, excluait bien zéro", v3.ci.separates is True)

r3 = LCG(24)
a4 = rows(3, 40, 4.0, r3)
b4 = rows(3, 40, 9.0, r3)
v4 = I.compare_pair("A", "B", a4, b4)
check("écart énorme mais fenêtre courte → PAS de repli sur l'écart relatif",
      v4.winner is None and v4.reason == "window_too_short", v4.reason)

# ══════════════════════════════════════════════════════════════════
print("── 6. classement : la marche du haut, ou rien ──")

cases = [{"model": "A", "typical_err_kmh": 4.0, "occurrences": 20},
         {"model": "B", "typical_err_kmh": 8.0, "occurrences": 20},
         {"model": "C", "typical_err_kmh": 9.0, "occurrences": 20}]
rk, reason, _ = I.rank_models(cases, {"A": a, "B": b, "C": b})
check("le vainqueur net est classé 1", rk.get("A") == 1, str(rk))
check("… et les suivants suivent l'erreur en km/h", rk.get("B") == 2 and rk.get("C") == 3)

rk2, reason2, _ = I.rank_models(
    [{"model": "A", "typical_err_kmh": 6.00, "occurrences": 20},
     {"model": "B", "typical_err_kmh": 6.05, "occurrences": 20}],
    {"A": a2, "B": b2})
check("deux modèles indiscernables → aucun rang", rk2 == {}, str(rk2))
check("… et la raison est publiée", reason2 in ("tied", "not_separable"), reason2)

rk3, reason3, _ = I.rank_models(
    [{"model": "A", "typical_err_kmh": 4.0, "occurrences": 3}], {"A": a})
check("sous le quorum → 'insufficient', aucun rang",
      rk3 == {} and reason3 == "insufficient")

rk4, reason4, _ = I.rank_models(
    [{"model": "A", "typical_err_kmh": 4.0, "occurrences": 20}], {"A": a})
# ⛔ CHANGÉ LE 22/08/2026 (lot S0.5). Cette assertion demandait
# `rk4 == {"A": 1}` et `reason4 == "ok"` : un « 1ᵉʳ sur 1 » publié avec
# la mention « un vainqueur, prouvé et utile ». Tant que chaque case
# portait neuf modèles, le cas était marginal (2 lignes sur 276 035,
# mesuré le 22/08). Le flux AROME/R2 le rend STRUCTUREL — 2 938 balises
# n'ont qu'un seul modèle. Un modèle seul n'a battu personne.
check("un seul modèle au-dessus du quorum n'est PAS classé",
      rk4 == {} and reason4 == "single_model", f"{rk4} / {reason4}")

# ══════════════════════════════════════════════════════════════════
print("── 7. rétrécissement vers le parent, et poids emprunté ──")

# Fratrie : 5 vallées bien fournies, dispersées autour de 6 km/h.
fratrie = [(5.0, 40, 4.0), (6.0, 40, 4.0), (7.0, 40, 4.0),
           (5.5, 40, 4.0), (6.5, 40, 4.0)]
tau2, sigma2 = I.pooling_variances(fratrie)
check("τ² est strictement positif quand les sœurs diffèrent vraiment",
      tau2 is not None and tau2 > 0, f"tau2={tau2}")

maigre = I.pool_toward_parent(2.0, 1, 6.0, tau2, sigma2)
check("une case à UNE balise-jour emprunte presque tout",
      maigre.borrowed is not None and maigre.borrowed > 0.85,
      f"borrowed={maigre.borrowed:.3f}")
check("… et son estimation est tirée vers le parent",
      abs(maigre.value - 6.0) < abs(2.0 - 6.0) / 3,
      f"value={maigre.value:.3f}")

fournie = I.pool_toward_parent(2.0, 400, 6.0, tau2, sigma2)
check("une case bien fournie n'emprunte presque rien",
      fournie.borrowed is not None and fournie.borrowed < 0.15,
      f"borrowed={fournie.borrowed:.3f}")
check("… et son estimation reste la sienne",
      abs(fournie.value - 2.0) < 0.6, f"value={fournie.value:.3f}")

check("le poids emprunté est monotone en n",
      I.pool_toward_parent(2.0, 1, 6.0, tau2, sigma2).borrowed
      > I.pool_toward_parent(2.0, 10, 6.0, tau2, sigma2).borrowed
      > I.pool_toward_parent(2.0, 100, 6.0, tau2, sigma2).borrowed)

plates = [(6.0, 40, 4.0), (6.0, 40, 4.0), (6.0, 40, 4.0)]
tau0, sig0 = I.pooling_variances(plates)
check("des sœurs indiscernables donnent τ² = 0", tau0 == 0.0, f"tau2={tau0}")
p0 = I.pool_toward_parent(2.0, 40, 6.0, tau0, sig0)
check("… et alors tout est emprunté, ce qui est le bon aveu",
      p0.borrowed == 1.0 and p0.value == 6.0)

check("sans parent, rien n'est emprunté et on le dit",
      I.pool_toward_parent(3.0, 10, None, tau2, sigma2).reason == "no_parent")
check("sans enfant, l'estimation EST le parent, emprunt = 1",
      I.pool_toward_parent(None, 0, 6.0, tau2, sigma2).borrowed == 1.0)
check("une fratrie d'un seul enfant ne dit rien sur τ²",
      I.pooling_variances([(5.0, 10, 2.0)]) == (None, None))

# ══════════════════════════════════════════════════════════════════
print("── 8. climatologie horaire ──")

H = 3600_000
obs_by_day = {}
for dd in range(10):
    base = 1_754_000_000_000 + dd * 86_400_000
    obs_by_day[f"j{dd}"] = [
        S.ObsSample(t=base + h * H,
                    speed=(20.0 if 10 <= h <= 16 else 4.0),
                    dir=270.0 if 10 <= h <= 16 else 90.0)
        for h in range(24)]
clim = I.hourly_climatology(obs_by_day)
check("la climatologie couvre les 24 heures vues 10 jours", len(clim) == 24)
check("… et retrouve le cycle de brise", clim[13][0] == 20.0 and clim[3][0] == 4.0)
check("… avec la direction, vectoriellement", round(clim[13][1]) == 270)

rare = {"j0": [S.ObsSample(t=1_754_000_000_000, speed=9.0, dir=180.0)]}
check("une heure vue un seul jour n'est pas une climatologie",
      I.hourly_climatology(rare) == {})

pairs = [S.VerifPair(t=1_754_000_000_000 + 13 * H, fcst_speed=20.0,
                     fcst_dir=270.0, obs_speed=20.0, obs_dir=270.0, n_obs=3),
         S.VerifPair(t=1_754_000_000_000 + 14 * H, fcst_speed=20.0,
                     fcst_dir=270.0, obs_speed=20.0, obs_dir=270.0, n_obs=3)]
sk, n, mm, mc = I.skill_vs_climatology(pairs, clim)
check("un modèle parfait face à une climatologie parfaite : MSE nuls",
      mm == 0.0 and mc == 0.0 and n == 2)
check("… et le skill est None, jamais une division par zéro", sk is None)

pairs_bad = [S.VerifPair(t=1_754_000_000_000 + 13 * H, fcst_speed=2.0,
                         fcst_dir=90.0, obs_speed=20.0, obs_dir=270.0, n_obs=3)
             for _ in range(3)]
sk2, n2, mm2, mc2 = I.skill_vs_climatology(pairs_bad, clim)
check("un modèle mauvais face à une climatologie juste : MSE modèle > 0",
      mm2 is not None and mm2 > 0 and mc2 == 0.0)

# ══════════════════════════════════════════════════════════════════
print("── 9. stabilité des rangs — et ce que le chiffre recouvre ──")

wa = {("z1", 6, "all"): {"A": 1, "B": 2, "C": 3},
      ("z2", 6, "all"): {"A": 1, "B": 2}}
wb_same = {("z1", 6, "all"): {"A": 1, "B": 2, "C": 3},
           ("z2", 6, "all"): {"A": 1, "B": 2}}
days_a = [f"2026-07-{d:02d}" for d in range(1, 16)]
days_b = [f"2026-07-{d:02d}" for d in range(16, 31)]
st = I.rank_stability(wa, wb_same, days_a, days_b)
check("classements identiques sur fenêtres disjointes → tau = 1",
      st.kendall_tau == 1.0 and st.reason == "ok")
check("… et l'accord sur le vainqueur vaut 1", st.top1_agreement == 1.0)
check("… et zéro jour partagé est constaté, pas supposé", st.shared_days == 0)

wb_rev = {("z1", 6, "all"): {"A": 3, "B": 2, "C": 1},
          ("z2", 6, "all"): {"A": 2, "B": 1}}
st2 = I.rank_stability(wa, wb_rev, days_a, days_b)
check("classements inversés → tau = −1", st2.kendall_tau == -1.0)
check("… et aucun accord sur le vainqueur", st2.top1_agreement == 0.0)

chevauche = [f"2026-07-{d:02d}" for d in range(2, 17)]
st3 = I.rank_stability(wa, wb_same, days_a, chevauche)
check("DEUX FENÊTRES QUI SE RECOUVRENT SONT SIGNALÉES",
      st3.reason == "windows_overlap" and st3.shared_days == 14,
      f"{st3.reason} / {st3.shared_days}")
check("… et `covers` le dit en toutes lettres, pour que le chiffre "
      "ne circule pas sans sa réserve",
      "recouvrement" in st3.covers)

st4 = I.rank_stability({("z9", 6, "all"): {"A": 1}}, wa, days_a, days_b)
check("aucune case commune classable → no_common_case",
      st4.reason == "no_common_case" and st4.kendall_tau is None)

# ══════════════════════════════════════════════════════════════════
#  10. LOT L3 (27/08/2026) — la p-valeur bootstrap, Benjamini-Hochberg,
#      et l'écart pratique enfin mesuré sur la population appariée.
# ══════════════════════════════════════════════════════════════════
print("── 10. lot L3 : p-valeur, multiplicité, gap apparié ──")

PLANCHER_P = 2 / (I.BOOTSTRAP_ITERATIONS + 1)

# ── 10.a. la p-valeur se lit dans la distribution, pas dans l'IC ─────
# Un décalage FRANC : toutes les journées penchent du même côté.
franc = {f"2026-07-{d:02d}": [-2.0, -2.1, -1.9, -2.2] for d in range(1, 16)}
ci_franc = I.block_ci_by_day(franc)
check("cas franc : l'IC exclut zéro", ci_franc.separates is True)
check("… et la p-valeur existe", ci_franc.p_value is not None)
check("⭐ … et elle est AU PLANCHER du tirage (aucun des 500 tirages du "
      "mauvais côté) — jamais zéro, ce qui serait affirmer l'infini",
      ci_franc.p_value == PLANCHER_P,
      f"p = {ci_franc.p_value} attendu {PLANCHER_P}")

# Un jeu SANS écart : la moitié des tirages de chaque côté.
nul = {f"2026-07-{d:02d}": [-1.0, 1.0, -1.0, 1.0] for d in range(1, 16)}
ci_nul = I.block_ci_by_day(nul)
check("cas nul : l'IC n'exclut pas zéro", ci_nul.separates is False)
check("… et la p-valeur est GRANDE (proche de 1), pas seulement « pas "
      "significative »", ci_nul.p_value is not None and ci_nul.p_value > 0.5,
      f"p = {ci_nul.p_value}")

# ⛔ LA PROPRIÉTÉ QUI COMPTE POUR BH : p et IC ne peuvent pas se
# contredire, puisqu'ils sortent du MÊME tirage.
check("⭐⭐ p ≤ 0,05 si et seulement si l'IC 95 % exclut zéro — un seul "
      "rééchantillonnage, donc jamais deux verdicts contraires",
      all((c.p_value <= 0.05) == (c.separates is True)
          for c in (ci_franc, ci_nul)))

check("aucune p-valeur quand aucun tirage n'a eu lieu (fenêtre trop "
      "courte)",
      I.block_ci_by_day({f"2026-07-0{d}": [1.0] * 4
                         for d in range(1, 5)}).p_value is None)

check("⚠️ le PLANCHER est une propriété du tirage, pas du phénomène : "
      "aucune p-valeur ne peut descendre sous 2/(B+1)",
      min(c.p_value for c in (ci_franc, ci_nul)) >= PLANCHER_P)

# ── 10.b. Benjamini-Hochberg : step-up, pas une suite de tests ───────
# Famille construite à la main : 10 cases franches au plancher, une à
# 0,0055 (qui ÉCHOUE à son propre rang), une à 0,009, une « limite » à
# 0,02, et 90 cases sans conclusion. m = 103, α = 0,10.
ps = ([PLANCHER_P] * 10 + [0.0110, 0.0115, 0.02]
      + [0.30 + 0.005 * i for i in range(90)])
surv, seuil, k = I.benjamini_hochberg(ps, 0.10)
m = len(ps)
check("BH : la famille est bien de 103 tests", m == 103)
check("⭐ la case LIMITE (p = 0,02) ne survit pas — seule, elle aurait "
      "été « significative » à 5 %", surv[12] is False)
check("⭐ les cases FRANCHES survivent", all(surv[i] for i in range(10)))
check("⭐⭐ STEP-UP : p = 0,0110 échoue à SON rang (11ᵉ seuil = "
      f"{11 * 0.10 / m:.5f}) mais survit parce qu'un k plus grand passe — "
      "c'est ce qui distingue BH d'une suite de tests indépendants",
      0.0110 > 11 * 0.10 / m and surv[10] is True,
      f"seuil rang 11 = {11 * 0.10 / m:.6f}, k = {k}")
check("… et p = 0,0115 survit aussi (c'est lui qui fixe k)",
      surv[11] is True and k == 12, f"k = {k}, seuil = {seuil}")
check("… aucune des 90 cases sans conclusion ne survit",
      not any(surv[13:]))

check("BH sur une famille vide ne rejette rien et ne plante pas",
      I.benjamini_hochberg([], 0.10) == ([], None, 0))
check("BH ignore les `None` (aucun test joué) et les rend non-survivants",
      I.benjamini_hochberg([None, None], 0.10) == ([False, False], None, 0))
sv2, _, k2 = I.benjamini_hochberg([None, PLANCHER_P], 0.10)
check("… et un `None` ne compte PAS dans m : une seule vraie p-valeur, "
      "seuil = α", sv2 == [False, True] and k2 == 1)
check("⛔ toutes grandes → k = 0, personne ne publie",
      I.benjamini_hochberg([0.4, 0.5, 0.9], 0.10)[2] == 0)
check("⚠️ α plus sévère tue plus : la même famille à 0,01 garde moins",
      I.benjamini_hochberg(ps, 0.01)[2] <= k)

# ── 10.c. le gap PRATIQUE sur les balise-jours appariés ──────────────
# ⛔ LE DÉFAUT MESURÉ DE L'AUDIT §2.5, reproduit exprès : A n'est noté
# que les jours faciles ET les jours difficiles ; B seulement les jours
# difficiles. Sur leurs populations propres, B a l'air BIEN pire. Sur
# les balise-jours COMMUNS, les deux sont à égalité stricte.
# ⚠️ LES DEUX CÔTÉS ONT DES BALISE-JOURS HORS DU NOYAU, et c'est
# nécessaire : un jeu où seul A déborde laisserait passer la faute
# « un seul des deux côtés est apparié », qui ne se voit pas à la
# lecture (mutation nº 16 du lot).
jours = [f"2026-07-{d:02d}" for d in range(1, 16)]
rows_a, rows_b = [], []
for j in jours:
    for u in ("u1", "u2", "u3", "u4", "u5", "u6"):
        rows_a.append({"day": j, "unit": u, "err_vec_med": 9.0})   # commun
        rows_b.append({"day": j, "unit": u, "err_vec_med": 9.4})   # commun
    for u in ("f1", "f2", "f3", "f4", "f5", "f6"):
        rows_a.append({"day": j, "unit": u, "err_vec_med": 1.0})   # A seul
    for u in ("g1", "g2", "g3", "g4", "g5", "g6", "g7", "g8"):
        rows_b.append({"day": j, "unit": u, "err_vec_med": 30.0})  # B seul
v = I.compare_pair("A", "B", rows_a, rows_b)
check("⭐⭐ gap APPARIÉ : sur les balise-jours communs, l'écart réel est "
      "de 0,4 km/h sur 9,4 — soit 4 %, très en dessous des 15 % utiles",
      v.relative_gap is not None and abs(v.relative_gap - 0.4 / 9.4) < 1e-9,
      f"gap = {v.relative_gap}")
check("⛔ … le test apparié SÉPARE pourtant (l'écart est parfaitement "
      "réel) : c'est bien la condition PRATIQUE qui refuse, et elle ne "
      "peut le faire que si elle porte sur la même population",
      v.ci is not None and v.ci.separates is True)
check("… verdict `tied`, au lieu d'un vainqueur fabriqué par deux "
      "populations", v.winner is None and v.reason == "tied",
      f"{v.winner}/{v.reason}")
check("⭐ `n_comparable` dit sur combien de balise-jours l'écart repose "
      "(90 communs, ni les 180 lignes de A ni les 210 de B)",
      v.n_comparable == 90, f"n_comparable = {v.n_comparable}")

# Le gap NON apparié, celui d'avant le lot, sur les MÊMES données :
med_a_tout = S.median([r["err_vec_med"] for r in rows_a])
med_b_tout = S.median([r["err_vec_med"] for r in rows_b])
gap_avant = abs(med_a_tout - med_b_tout) / max(med_a_tout, med_b_tout)
check("⛔ … alors que l'ancien calcul (médianes de populations propres) "
      "annonçait un écart énorme sur les mêmes données — c'est LE défaut "
      "que ce lot ferme",
      gap_avant >= I.MIN_RELATIVE_GAP, f"gap non apparié = {gap_avant:.3f}")
check("⚠️ les deux gaps DIVERGENT vraiment (le banc ne serait pas une "
      "preuve s'ils coïncidaient)", abs(gap_avant - v.relative_gap) > 0.5)

# ⛔ ET L'ASYMÉTRIE, la plus discrète des trois fautes : UN SEUL des
# deux côtés apparié. Le gap qui en sort n'est ni l'un ni l'autre, et
# rien dans le code ne le signale.
med_a_app = S.median([r["err_vec_med"] for r in rows_a
                      if r["unit"].startswith("u")])
gap_mixte = abs(med_a_app - med_b_tout) / max(med_a_app, med_b_tout)
check("⛔ apparier UN SEUL côté donnerait encore un écart « utile » "
      f"({gap_mixte:.2f}), donc un vainqueur — les DEUX médianes "
      "doivent porter sur le noyau", gap_mixte >= I.MIN_RELATIVE_GAP)

# Et le cas où l'appariement ne rend rien : pas de gap inventé.
v0 = I.compare_pair("A", "B", rows_a,
                    [{"day": "2026-09-01", "unit": "z", "err_vec_med": 1.0}])
check("aucun balise-jour commun → gap `None`, jamais un chiffre tiré de "
      "deux populations étrangères",
      v0.relative_gap is None and v0.n_comparable == 0)

# ══════════════════════════════════════════════════════════════════
#  9. LOT L9a — agréger un ANGLE sans le mettre à plat
# ══════════════════════════════════════════════════════════════════
print("\n── 9. lot L9a : la moyenne circulaire des écarts de cap ──")

# ⛔ LA SCÈNE QUI FAIT TOUT LE LOT. Deux balise-jours à +179° et −179°
# décrivent le MÊME désaccord (le modèle est à un demi-tour). La
# moyenne — et la médiane — arithmétiques valent 0°, c'est-à-dire
# « modèle parfaitement calé ». La valeur attendue est écrite en
# TOUTES LETTRES (180), jamais dérivée du code testé : piège nº 3 du
# 26/08 (clôture).
check("⭐ +179° et −179° → 180°, pas 0° (la faute que ce lot évite)",
      round(I.circular_mean_deg([179.0, -179.0]), 6) == 180.0,
      f"rendu : {I.circular_mean_deg([179.0, -179.0])}")
check("⛔ … alors que la moyenne arithmétique dirait « parfait »",
      (179.0 + -179.0) / 2 == 0.0)
check("⛔ … et la médiane arithmétique aussi",
      S.median([179.0, -179.0]) == 0.0)

# Le cas ordinaire : loin du saut, la circulaire redonne l'arithmétique.
check("loin du saut, elle coïncide avec la moyenne ordinaire",
      round(I.circular_mean_deg([10.0, 20.0, 30.0]), 6) == 20.0,
      f"rendu : {I.circular_mean_deg([10.0, 20.0, 30.0])}")
check("… y compris à cheval sur 0° (−10 et +10 → 0)",
      abs(I.circular_mean_deg([-10.0, 10.0])) < 1e-9,
      f"rendu : {I.circular_mean_deg([-10.0, 10.0])}")
check("un seul angle se rend lui-même",
      round(I.circular_mean_deg([-42.5]), 6) == -42.5)

# Résultante nulle : deux caps diamétralement opposés n'ont PAS de
# moyenne. Inventer 0° serait exactement la faute du haut, à l'envers.
check("⛔ 0° et 180° → None, jamais un 90° inventé",
      I.circular_mean_deg([0.0, 180.0]) is None,
      f"rendu : {I.circular_mean_deg([0.0, 180.0])}")
check("liste vide → None", I.circular_mean_deg([]) is None)
check("None et NaN sont ignorés, pas comptés",
      round(I.circular_mean_deg([None, float("nan"), 30.0, 30.0]), 6) == 30.0,
      f"rendu : {I.circular_mean_deg([None, float('nan'), 30.0, 30.0])}")
check("… et une liste qui n'a QUE des non-finis rend None",
      I.circular_mean_deg([None, float("inf")]) is None)

# La sortie vit dans (−180, 180] : un demi-tour a UN seul nom.
check("le demi-tour sort à +180, jamais à −180",
      I.circular_mean_deg([180.0]) == 180.0)
# ⚠️ LE CAS QUI PROUVE LA NORMALISATION, et il fallait le chercher :
# `atan2` ne rend −180 que si le sinus est NÉGATIF, ce qui n'arrive
# qu'en partant d'un angle déjà écrit −180 (sin(−π) = −1,2e−16).
# Écrire seulement `[180.0]` laissait la mutation « la normalisation
# saute » passer VERTE — la branche n'était pas atteinte.
check("⭐ … y compris quand l'entrée elle-même est écrite −180 "
      "(le seul chemin par lequel `atan2` rend −π)",
      I.circular_mean_deg([-180.0]) == 180.0,
      f"rendu : {I.circular_mean_deg([-180.0])}")
check("… et sur une population entière à −180",
      I.circular_mean_deg([-180.0, -180.0]) == 180.0)
for a in (-179.0, -90.0, 0.0, 90.0, 179.9, 180.0):
    m = I.circular_mean_deg([a])
    check(f"… {a}° reste dans (−180, 180] ({m})", -180.0 < m <= 180.0)

# ⚠️ LE JEU EST IRRÉGULIER DANS LA DIMENSION TESTÉE (piège nº 2 de la
# phase B) : une population ASYMÉTRIQUE autour du saut. Trois angles
# près de +180 et un près de −180 : la réponse doit pencher du côté des
# trois, ce qu'aucune moyenne arithmétique ne saurait faire.
m = I.circular_mean_deg([170.0, 175.0, 178.0, -175.0])
check("⭐ population asymétrique autour du demi-tour : la moyenne "
      f"circulaire penche du bon côté ({m:.2f}°)", 165.0 < m < 180.0)
check("⛔ … là où l'arithmétique aurait rendu un cap Sud-Est",
      round((170.0 + 175.0 + 178.0 - 175.0) / 4, 2) == 87.0)


# ══════════════════════════════════════════════════════════════════
#  10. LOT L9c — la référence COMBINÉE (Murphy 1992)
# ══════════════════════════════════════════════════════════════════
print("\n── 10. lot L9c : k·persistance + (1−k)·climatologie ──")

# ── (i) les deux BORNES du mélange, exactes ──────────────────────
persist = (20.0, 90.0)
climh = (8.0, 0.0, 12)
check("⭐ k = 1 rend la PERSISTANCE au bit près",
      I.combined_reference(1.0, persist, climh) == (20.0, 90.0),
      f"{I.combined_reference(1.0, persist, climh)}")
check("⭐ k = 0 rend la CLIMATOLOGIE au bit près",
      I.combined_reference(0.0, persist, climh) == (8.0, 0.0),
      f"{I.combined_reference(0.0, persist, climh)}")

# ── (ii) un k INTERMÉDIAIRE, calculé à la main hors du code ──────
# force : 0,25 × 20 + 0,75 × 8 = 5 + 6 = 11
# cap   : vecteurs UNITAIRES, u = 0,25·sin90 + 0,75·sin0 = 0,25
#                             v = 0,25·cos90 + 0,75·cos0 = 0,75
#         atan2(0,25 ; 0,75) = 18,4349°
f_i, d_i = I.combined_reference(0.25, persist, climh)
check("⭐ k = 0,25 : la FORCE vaut 11 km/h (5 + 6, calculé à la main)",
      abs(f_i - 11.0) < 1e-9, f"force = {f_i}")
check("⭐ k = 0,25 : le CAP vaut 18,4349° (atan2(0,25 ; 0,75), calculé "
      "à la main)", abs(d_i - 18.4349) < 1e-3, f"cap = {d_i}")
check("⛔ … et PAS la moyenne arithmétique des caps (22,5°) : le "
      "mélange est circulaire", abs(d_i - 22.5) > 3.0)
# ⚠️ La force ne passe PAS par (u, v). Le vérifier explicitement : la
# norme du mélange vectoriel VRAI vaudrait ici bien moins que 11.
_u = 0.25 * 20 * math.sin(math.radians(90)) + 0.75 * 8 * math.sin(0.0)
_v = 0.25 * 20 * math.cos(math.radians(90)) + 0.75 * 8 * math.cos(0.0)
check("⛔⛔ mélanger en (u, v) puis reprendre la norme rendrait une "
      f"référence artificiellement FAIBLE ({math.hypot(_u, _v):.2f} au "
      "lieu de 11) — donc un skill artificiellement bon",
      math.hypot(_u, _v) < 9.0)

check("un cap manquant d'un côté laisse passer celui de l'autre",
      I.combined_reference(0.5, (10.0, None), (6.0, 40.0, 9))[1] == 40.0)
check("deux caps manquants → aucun cap inventé",
      I.combined_reference(0.5, (10.0, None), (6.0, None, 9))[1] is None)
check("⛔ deux caps diamétralement opposés à poids égal → aucun cap "
      "(la moyenne n'existe pas)",
      I.combined_reference(0.5, (10.0, 0.0), (6.0, 180.0, 9))[1] is None)

# ── (iii) la borne du poids, et ce qu'elle DIT ───────────────────
check("ρ dans [0, 1] passe tel quel", I.poids_combine(0.42) == (0.42, False))
check("ρ négatif est ramené à 0 ET SIGNALÉ",
      I.poids_combine(-0.3) == (0.0, True))
check("ρ > 1 est ramené à 1 ET SIGNALÉ", I.poids_combine(1.4) == (1.0, True))
check("ρ absent reste absent — jamais un poids inventé",
      I.poids_combine(None) == (None, False))

# ── (iv) ⭐ L'ESTIMATEUR RETROUVE UN ρ CONNU ─────────────────────
# Série fabriquée : cycle diurne + anomalie journalière AR(1) de
# coefficient 0,6 CONNU. `autocorr_lag24` doit le retrouver — c'est la
# seule façon de savoir qu'il mesure ce que son nom dit.
# ⚠️ Le cycle diurne est ÉNORME devant l'anomalie (±5 contre ±2) :
# c'est exprès. Un estimateur qui oublierait de retirer la climatologie
# rendrait un ρ dominé par le cycle, donc proche de 1 — la faute que le
# pavé de la fonction nomme.
rng = LCG(4242)
JOURS = 40
clim_h = {h: (10.0 + 5.0 * math.sin(2 * math.pi * h / 24), None, JOURS)
          for h in range(24)}
A, obs_by_day = 0.0, {}
anomalies_vraies = []
for j in range(JOURS):
    A = 0.6 * A + 2.0 * (rng.u() - 0.5)
    anomalies_vraies.append(A)
    jour = f"2026-06-{j + 1:02d}"
    # ⚠️ ORIGINE ALIGNÉE SUR MINUIT UTC (1 779 926 400 = 20 601 × 86 400),
    # et ce n'est PAS un détail de fixture. `hourly_climatology` et
    # `autocorr_lag24` calculent l'heure locale sur le timestamp ABSOLU
    # (`(t//1000 + offset)//3600 % 24`). Une origine non alignée décale
    # la climatologie d'un cran par rapport aux observations, ce qui
    # fabrique une anomalie DIURNE identique chaque jour — mesuré en
    # écrivant ce banc : ρ sortait à 0,981 au lieu de 0,60. Le banc
    # aurait « prouvé » que l'estimateur marche… en mesurant une faute
    # de fixture.
    t0 = (1779926400 + j * 86400) * 1000
    obs_by_day[jour] = [
        S.ObsSample(t=t0 + h * 3_600_000,
                    speed=clim_h[h][0] + A + 0.3 * (rng.u() - 0.5),
                    dir=None)
        for h in range(24)]
rho = I.autocorr_lag24(obs_by_day, clim_h, 0)
check("⭐⭐ `autocorr_lag24` retrouve le ρ de 0,6 qu'on a injecté "
      f"({rho:.3f})", rho is not None and 0.45 < rho < 0.75,
      f"rho = {rho}")

# ⛔ ET LE CONTRE-CAS : la même série SANS retirer la climatologie.
clim_plate = {h: (10.0, None, JOURS) for h in range(24)}
rho_brut = I.autocorr_lag24(obs_by_day, clim_plate, 0)
check("⛔⛔ … là où la même série, l'anomalie mesurée contre une "
      f"climatologie PLATE, rend {rho_brut:.3f} — le cycle diurne pris "
      "pour de la persistance",
      rho_brut is not None and rho_brut > 0.85, f"rho brut = {rho_brut}")

# ⛔ LE PLANCHER, ET IL SE COMPTE EN JOURNÉES. 14 journées font ~336
# couples d'heures — largement au-dessus de `AUTOCORR_MIN_PAIRS` — et
# doivent pourtant être REFUSÉES : la taille d'échantillon effective est
# le nombre de JOURNÉES, et à 14 le biais de retrait de moyenne
# (≈ −1/N) reste ce que l'estimateur mesure le mieux. Mesuré sur la
# production le 28/08 : ρ médian −0,194 sous 8 journées, +0,082 entre
# 15 et 21.
check("le plancher est en JOURNÉES : 15 exigées",
      I.AUTOCORR_MIN_DAYS == 15, f"{I.AUTOCORR_MIN_DAYS}")
sous = {k: v for k, v in list(obs_by_day.items())[:14]}
n_couples_sous = sum(len(v) for v in sous.values())
check("⭐ 14 journées sont REFUSÉES bien qu'elles portent "
      f"{n_couples_sous} relevés — largement plus que le garde-fou en "
      f"couples ({I.AUTOCORR_MIN_PAIRS})",
      I.autocorr_lag24(sous, clim_h, 0) is None
      and n_couples_sous > I.AUTOCORR_MIN_PAIRS,
      f"rho = {I.autocorr_lag24(sous, clim_h, 0)}")
check("… et trois journées aussi, évidemment",
      I.autocorr_lag24({k: v for k, v in list(obs_by_day.items())[:4]},
                       clim_h, 0) is None)
check("16 journées, elles, passent",
      I.autocorr_lag24({k: v for k, v in list(obs_by_day.items())[:16]},
                       clim_h, 0) is not None)
troue = {k: v for k, v in obs_by_day.items() if int(k[-2:]) % 2 == 1}
check("⛔ des journées NON consécutives ne s'apparient pas à « 24 h » "
      "(lundi contre vendredi ne serait pas de la persistance)",
      I.autocorr_lag24(troue, clim_h, 0) is None)

# ── (v) ⭐⭐ LA PROPRIÉTÉ DE MURPHY : la combinaison DOMINE ────────
# Sur la dernière journée de la série fabriquée, les trois références
# sont mises côte à côte sur les MÊMES heures.
# ⛔ SUR TOUTE LA SÉRIE, PAS SUR UNE JOURNÉE. La domination de Murphy
# est une propriété EN ESPÉRANCE, pas une garantie par réalisation :
# une journée où l'anomalie est proche de zéro donne raison à la
# climatologie seule, et un banc écrit sur cette journée-là « prouverait »
# le contraire du théorème. Mesuré en écrivant ce banc — la version à
# une journée rendait clim 0,026 contre combinaison 0,460.
def _mse_des_trois(jours_utiles):
    sp = sc = sb_ = 0.0
    np_ = 0
    for j in jours_utiles:
        d0 = f"2026-06-{j + 1:02d}"
        d1 = f"2026-06-{j:02d}"
        t_j = (1779926400 + j * 86400) * 1000
        serie = obs_by_day[d0] + obs_by_day[d1]
        pr = [S.VerifPair(t=t_j + h * 3_600_000,
                          fcst_speed=clim_h[h][0] + 0.7 * anomalies_vraies[j],
                          fcst_dir=None,
                          obs_speed=obs_by_day[d0][h].speed,
                          obs_dir=None, n_obs=1)
              for h in range(24)]
        _, na, _, mp = S.skill_vs_persistence(pr, serie)
        _, nb, _, mc = I.skill_vs_climatology(pr, clim_h, 0)
        _, nc, _, mb = I.skill_vs_combined(pr, clim_h, rho, serie, 0)
        if not (na == nb == nc == 24):
            continue
        sp += mp * na
        sc += mc * nb
        sb_ += mb * nc
        np_ += na
    return sp / np_, sc / np_, sb_ / np_, np_


mse_p_tot, mse_c_tot, mse_b_tot, n_tot = _mse_des_trois(range(1, 29))
check("les trois références sont mesurées sur les mêmes heures, sur "
      f"28 journées ({n_tot} heures)", n_tot == 28 * 24, f"n = {n_tot}")
check("⭐⭐ le MSE de la COMBINAISON est inférieur ou égal à celui de la "
      f"persistance ({mse_b_tot:.3f} ≤ {mse_p_tot:.3f}) — la propriété "
      "de Murphy 1992, mesurée", mse_b_tot <= mse_p_tot + 1e-9)
check("⭐⭐ … ET à celui de la climatologie "
      f"({mse_b_tot:.3f} ≤ {mse_c_tot:.3f})", mse_b_tot <= mse_c_tot + 1e-9)
check("⚠️ les trois DIFFÈRENT vraiment (le banc ne prouverait rien si "
      "elles coïncidaient)",
      abs(mse_p_tot - mse_c_tot) > 0.05
      and abs(mse_b_tot - min(mse_p_tot, mse_c_tot)) > 1e-6,
      f"persist {mse_p_tot:.3f} · clim {mse_c_tot:.3f} · "
      f"comb {mse_b_tot:.3f}")

# ── (vi) les bornes, bout en bout, sur une journée quelconque ────
obs_serie = obs_by_day["2026-06-29"] + obs_by_day["2026-06-28"]
prevs = [S.VerifPair(t=(1779926400 + 28 * 86400) * 1000 + h * 3_600_000,
                     fcst_speed=clim_h[h][0] + 0.7 * anomalies_vraies[28],
                     fcst_dir=None,
                     obs_speed=obs_by_day["2026-06-29"][h].speed,
                     obs_dir=None, n_obs=1)
         for h in range(24)]
_, _, _, mse_p1 = S.skill_vs_persistence(prevs, obs_serie)
_, _, _, mse_c1 = I.skill_vs_climatology(prevs, clim_h, 0)
_, n_b1, mm_b1, _ = I.skill_vs_combined(prevs, clim_h, rho, obs_serie, 0)
_, _, _, mse_k1 = I.skill_vs_combined(prevs, clim_h, 1.0, obs_serie, 0)
_, _, _, mse_k0 = I.skill_vs_combined(prevs, clim_h, 0.0, obs_serie, 0)
check("⭐ bout en bout : k = 1 rend EXACTEMENT le MSE de la persistance",
      abs(mse_k1 - mse_p1) < 1e-9, f"{mse_k1} vs {mse_p1}")
check("⭐ bout en bout : k = 0 rend EXACTEMENT le MSE de la climatologie",
      abs(mse_k0 - mse_c1) < 1e-9, f"{mse_k0} vs {mse_c1}")
check("⛔ `skill_vs_combined` rend SON PROPRE mse_model, pas celui de la "
      "persistance (deux populations d'heures, deux témoins)",
      mm_b1 is not None and n_b1 == 24)

# Une heure sans climatologie sort du calcul plutôt que d'être comblée.
clim_trouee = {h: v for h, v in clim_h.items() if h != 12}
_, n_t, _, _ = I.skill_vs_combined(prevs, clim_trouee, rho, obs_serie, 0)
check("une heure sans climatologie n'entre pas dans le mélange "
      "(23 heures, pas 24 comblées)", n_t == 23, f"n = {n_t}")

# ⛔ ET LE TÉMOIN QUI COMPTE : sur la MÊME population d'heures, le MSE
# du modèle rendu par `skill_vs_combined` doit être celui du modèle —
# pas une valeur recopiée d'ailleurs. On le confronte au calcul direct.
mse_mod_direct = sum(
    S.pair_error(p)[0] ** 2 for p in prevs) / len(prevs)
check("⭐ … et ce mse_model coïncide avec le calcul direct sur les "
      "mêmes 24 heures", abs(mm_b1 - mse_mod_direct) < 1e-9,
      f"{mm_b1} vs {mse_mod_direct}")


# ══════════════════════════════════════════════════════════════════
print(f"\n{'✅' if KO == 0 else '❌'} {OK} assertions vertes, {KO} rouges.\n")
sys.exit(1 if KO else 0)
