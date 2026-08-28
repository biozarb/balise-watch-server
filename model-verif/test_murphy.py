#!/usr/bin/env python3
"""test_murphy.py — banc d'essai de la décomposition de Murphy (lot L9b).

    Session 28/08/2026.

⚠️ UNE SEULE SIGNATURE DE `check`, ET ELLE EST ÉCRITE ICI :
`check(label, obtenu, attendu, tol)`. Le dossier en contient DEUX
autres (`test_score.py` la même, `test_inference.py` en
`(label, condition, detail)`), et six assertions de ce lot ont été
écrites au mauvais format le 28/08 : elles passaient VERTES sans rien
vérifier, parce que `180.0` est une condition vraie. *Un banc dont la
signature ressemble à celle du voisin doit la rappeler en tête.*

Ce que ce banc prouve, dans l'ordre d'importance :

  1. **L'identité est exacte.** `ss = r² − bc² − bs²` est revérifié par
     un chemin INDÉPENDANT — `1 − MSE/s_o²`, où le MSE est recalculé
     depuis les couples eux-mêmes, sans passer par `r`, `bc` ni `bs`.
     Un banc qui recalculerait l'identité avec les termes que le code
     vient de rendre comparerait la faute à elle-même (piège nº 1 de la
     phase B).

  2. **La lecture est la bonne.** Une erreur de pure AMPLITUDE doit
     laisser `r² = 1` et charger `bc`/`bs` ; une erreur de pur TIMING
     doit effondrer `r²` en laissant `bc`/`bs` près de zéro. C'est TOUT
     le produit du lot : si ces deux scènes ne se distinguaient pas, la
     décomposition ne dirait rien de ce qu'elle promet.

  3. **Les moments s'additionnent.** Le total de trente journées doit
     rendre exactement ce que rendraient les 720 couples d'un coup.

  4. **On ne poole pas entre balises.** Une scène où la médiane des
     décompositions et la décomposition des moments additionnés
     DIVERGENT franchement — sans quoi le §4 de l'en-tête de
     `murphy.py` serait une précaution invérifiable.

Usage :
    python3 test_murphy.py
"""
from __future__ import annotations

import math
import os
import sys

# ⚠️ LE DOSSIER DU FICHIER, PAS LE DOSSIER COURANT. `deploy-agrume-vps.sh`
# lance les bancs depuis la RACINE du dépôt (`$PY model-verif/test_x.py`) :
# un `sys.path.insert(0, ".")` y chercherait `murphy` à la racine et le
# banc tomberait à l'import — c'est-à-dire qu'il bloquerait un
# déploiement sans rien avoir mesuré.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import murphy as MU      # noqa: E402
import scoring as S      # noqa: E402

OK = 0
KO = 0


def check(label, obtenu, attendu, tol=1e-9):
    global OK, KO
    if isinstance(obtenu, bool) or isinstance(attendu, bool):
        bon = obtenu is attendu
    elif obtenu is None or attendu is None:
        bon = obtenu is None and attendu is None
    elif isinstance(obtenu, (int, float)) and isinstance(attendu, (int, float)):
        bon = abs(obtenu - attendu) <= tol
    else:
        bon = obtenu == attendu
    if bon:
        OK += 1
    else:
        KO += 1
        print(f"  ❌ {label}\n       obtenu  : {obtenu!r}"
              f"\n       attendu : {attendu!r}")


class LCG:
    """Congruentiel maison — reproductible, et qui ne sert QU'au banc.
    (Pas de `random` : un banc qui bouge d'une exécution à l'autre ne
    prouve rien ; pas de `hash` non plus, piège nº 4 de la phase B.)"""

    def __init__(self, seed=20260828):
        self.s = seed & 0xFFFFFFFF

    def u(self):
        self.s = (1103515245 * self.s + 12345) & 0x7FFFFFFF
        return self.s / 0x7FFFFFFF


def paires(f, o):
    return [S.VerifPair(t=i * 3_600_000, fcst_speed=a, fcst_dir=None,
                        obs_speed=b, obs_dir=None, n_obs=1)
            for i, (a, b) in enumerate(zip(f, o))]


def mse_direct(f, o):
    """Le MSE en DEUX PASSES, sans toucher aux six sommes."""
    return sum((a - b) ** 2 for a, b in zip(f, o)) / len(f)


def var_direct(x):
    m = sum(x) / len(x)
    return sum((v - m) ** 2 for v in x) / len(x)


# ══════════════════════════════════════════════════════════════════
print("── 1. L'IDENTITÉ, vérifiée par un chemin indépendant ──")
# ══════════════════════════════════════════════════════════════════
rng = LCG()
# Un cycle diurne + du bruit : irrégulier dans les deux dimensions que
# la décomposition sépare (forme ET échelle).
obs = [8 + 6 * math.sin(i * math.pi / 12) + 3 * (rng.u() - 0.5)
       for i in range(240)]
fcst = [1.25 * (8 + 6 * math.sin(i * math.pi / 12 - 0.4)) + 1.5 * (rng.u() - 0.5)
        for i in range(240)]
d = MU.decompose(MU.moments(paires(fcst, obs)))
ss_independant = 1.0 - mse_direct(fcst, obs) / var_direct(obs)
check("⭐ `ss` = 1 − MSE/s_o², le MSE recalculé en deux passes depuis "
      "les couples (jamais depuis r, bc ou bs)",
      d["ss"], round(ss_independant, 4), 1e-4)
check("… et l'identité r² − bc² − bs² rend le même nombre",
      round(d["r2"] - d["bc"] ** 2 - d["bs"] ** 2, 4), d["ss"], 1e-4)
check("`sd_o` est bien l'écart-type de POPULATION des observations "
      "(division par n, la convention du MSE)",
      d["sd_o"], round(math.sqrt(var_direct(obs)), 4), 1e-4)
check("`mean_o` est la moyenne des observations",
      d["mean_o"], round(sum(obs) / len(obs), 4), 1e-4)
check("`n` compte les couples", d["n"], 240)
check("le motif est `ok`", d["reason"], "ok")

# ══════════════════════════════════════════════════════════════════
print("\n── 2. AMPLITUDE contre TIMING — la lecture du lot ──")
# ══════════════════════════════════════════════════════════════════
base = [8 + 6 * math.sin(i * math.pi / 12) for i in range(240)]

# (a) Erreur de PURE AMPLITUDE : f = 1,4 × o. La forme est exacte.
amp = MU.decompose(MU.moments(paires([1.4 * v for v in base], base)))
check("⭐ amplitude pure : `r2` vaut 1 — la forme est parfaite",
      amp["r2"], 1.0, 1e-6)
check("⭐ … et le biais CONDITIONNEL vaut 1 − 1,4 = −0,4 (écrit en "
      "toutes lettres, pas dérivé du code)", amp["bc"], -0.4, 1e-3)
check("⭐ … le biais SYSTÉMATIQUE aussi est chargé : une pente "
      "multiplicative déplace la moyenne (0,4·ō/s_o)",
      amp["bs"], round(0.4 * (sum(base) / len(base))
                       / math.sqrt(var_direct(base)), 4), 1e-3)
# ⭐ LE CHIFFRE ÉCRIT EN TOUTES LETTRES, calculé à la main hors du code :
# ō = 8, s_o = 6/√2 = 4,24264 ; bc = 1 − 1,4 = −0,4 ; bs = 3,2/4,24264
# = 0,75425 ; ss = 1 − 0,16 − 0,56889 = 0,27111. Une erreur d'amplitude
# de +40 % mange donc 73 % du potentiel — et pas une once du potentiel
# lui-même, qui reste à 1.
check("⭐ … `ss` tombe à 0,2711 (valeur calculée à la main, pas relue "
      "du code) : l'amplitude mange 73 % du potentiel",
      amp["ss"], 0.2711, 1e-3)
check("⛔ … et TOUT ce qui manque est du réparable : ss < r², l'écart "
      "étant exactement bc² + bs²",
      round(amp["r2"] - amp["ss"], 4),
      round(amp["bc"] ** 2 + amp["bs"] ** 2, 4), 1e-3)

# ⭐ ET CE QUE LA PENTE DU LOT S2 RÉPARE, MESURÉ : appliquer la pente
# exacte annule bc ET bs, et `ss` remonte à `r²` — le plafond que la
# décomposition annonçait.
repare = MU.decompose(MU.moments(paires([v for v in base], base)))
check("⭐⭐ la pente exacte annule le biais conditionnel", repare["bc"],
      0.0, 1e-6)
check("⭐⭐ … et le systématique", repare["bs"], 0.0, 1e-6)
check("⭐⭐ … et `ss` remonte EXACTEMENT à `r²`, le plafond annoncé",
      repare["ss"], amp["r2"], 1e-6)

# (b) Erreur de PUR TIMING : même amplitude, décalée de 6 h (un quart
# de cycle) — la corrélation tombe à zéro, l'échelle reste juste.
tim = MU.decompose(MU.moments(
    paires([8 + 6 * math.sin((i - 6) * math.pi / 12) for i in range(240)],
           base)))
check("⭐ timing pur : `r2` s'effondre", tim["r2"] < 0.05, True)
check("⭐ … alors que le rapport des écarts-types reste à 1 (l'échelle "
      "est juste)", tim["sd_ratio"], 1.0, 1e-6)
check("⭐ … et le biais systématique reste nul", tim["bs"], 0.0, 1e-6)
check("⛔ … AUCUNE pente ne réparera ça : le plafond `r²` est déjà le "
      "plancher", tim["r2"] < 0.05 and tim["ss"] < 0.05, True)
check("⭐ les deux scènes se DISTINGUENT vraiment (le banc ne prouve "
      "rien si elles se ressemblent)", amp["r2"] - tim["r2"] > 0.9, True)

# ══════════════════════════════════════════════════════════════════
print("\n── 3. Les moments s'additionnent (30 journées = 720 couples) ──")
# ══════════════════════════════════════════════════════════════════
rng = LCG(7)
jours = []
tous_f, tous_o = [], []
for j in range(30):
    # ⚠️ Journées de LONGUEURS DIFFÉRENTES : un jeu régulier ne verrait
    # pas la différence entre « additionner les sommes » et
    # « moyenner les moyennes » (piège nº 2 de la phase B).
    n = 18 + (j % 7)
    fo = [(6 + 5 * math.sin(i * math.pi / 12) + 2 * rng.u(),
           5 + 5 * math.sin(i * math.pi / 12 - 0.3) + 2 * rng.u())
          for i in range(n)]
    f = [a for a, _ in fo]
    o = [b for _, b in fo]
    jours.append(MU.moments(paires(f, o)))
    tous_f += f
    tous_o += o
poolees = MU.pool(jours)
direct = MU.moments(paires(tous_f, tous_o))
check("le `n` total est la somme des n journaliers", poolees[0], direct[0])
for i, nom in enumerate(("Σf", "Σo", "Σf²", "Σo²", "Σfo"), 1):
    check(f"… {nom} additionné == {nom} direct", poolees[i], direct[i], 1e-3)
dp, dd = MU.decompose(poolees), MU.decompose(direct)
check("⭐ le r² des sommes additionnées == celui du calcul d'un bloc",
      dp["r2"], dd["r2"], 1e-4)
check("… idem `bc`", dp["bc"], dd["bc"], 1e-4)
check("… idem `bs`", dp["bs"], dd["bs"], 1e-4)
check("`pool` sur rien du tout rend None", MU.pool([]), None)
check("… et une journée à n=0 ne compte pas",
      MU.pool([[0, 0, 0, 0, 0, 0]]), None)

# ══════════════════════════════════════════════════════════════════
print("\n── 4. Les refus se NOMMENT, ils ne disparaissent pas ──")
# ══════════════════════════════════════════════════════════════════
plat = MU.decompose(MU.moments(paires([9.0] * 50, [7.0] * 50)))
check("observations sans variance → `flat_obs`", plat["reason"], "flat_obs")
check("… et aucun terme n'est inventé", plat["ss"], None)
check("… mais les moyennes, elles, sont publiées (elles ont un sens)",
      plat["mean_o"], 7.0, 1e-6)

const = MU.decompose(MU.moments(paires([9.0] * 240, base)))
check("prévision CONSTANTE : `r` posé à 0 (elle n'explique aucune "
      "variance) — pas `None`", const["r"], 0.0, 1e-9)
check("… `bc` nul, donc aucune pente n'y peut rien", const["bc"], 0.0, 1e-9)
check("… et `ss` vaut exactement −bs²",
      const["ss"], round(-const["bs"] ** 2, 4), 1e-4)
check("… le motif reste `ok` : la ligne est interprétable",
      const["reason"], "ok")

check("moments vides → `too_few_pairs`",
      MU.decompose(None)["reason"], "too_few_pairs")

# ══════════════════════════════════════════════════════════════════
print("\n── 5. Par balise : le plancher, et la ligne qui reste ──")
# ══════════════════════════════════════════════════════════════════
units = []
for j in range(30):
    d_str = f"2026-07-{j + 1:02d}"
    for u in ("pioupiou:1", "pioupiou:2"):
        n = 24
        dec = 0.0 if u == "pioupiou:1" else 6.0
        f = [8 + 6 * math.sin((i - dec) * math.pi / 12) for i in range(n)]
        o = [8 + 6 * math.sin(i * math.pi / 12) for i in range(n)]
        units.append({"unit": u, "day": d_str, "model": "icon_d2",
                      "lead_h": 6, MU.MURPHY_KEY: MU.moments(paires(f, o))})
# Une balise SOUS le plancher : trois journées seulement.
for j in range(3):
    units.append({"unit": "pioupiou:9", "day": f"2026-07-{j + 1:02d}",
                  "model": "icon_d2", "lead_h": 6,
                  MU.MURPHY_KEY: MU.moments(paires([9.0] * 24,
                                                   [8 + 6 * math.sin(i * math.pi / 12)
                                                    for i in range(24)]))})
lignes = MU.par_balise(units)
par_u = {l["unit"]: l for l in lignes}
check("trois balises, trois lignes", len(lignes), 3)
check("⭐ la balise sous le plancher a QUAND MÊME sa ligne (une ligne "
      "absente et une ligne à zéro se lisent pareil)",
      "pioupiou:9" in par_u, True)
check("… avec son motif", par_u["pioupiou:9"]["reason"], "too_few_pairs")
check("… et aucun terme inventé", par_u["pioupiou:9"]["r2"], None)
check("… mais son `n` et ses jours restent lisibles",
      (par_u["pioupiou:9"]["n"], par_u["pioupiou:9"]["n_days"]), (72, 3))
check("la balise calée est décomposée", par_u["pioupiou:1"]["reason"], "ok")
check("⭐ … et elle est PARFAITE (même série des deux côtés)",
      par_u["pioupiou:1"]["ss"], 1.0, 1e-6)
check("la balise décalée de 6 h a un r² effondré",
      par_u["pioupiou:2"]["r2"] < 0.05, True)
check("chaque ligne porte la référence de son `ss`, en toutes lettres",
      par_u["pioupiou:1"]["ss_reference"], MU.SS_REFERENCE)
check("… et la grandeur décomposée", par_u["pioupiou:1"]["value_key"],
      "speed_kmh")
check("une fenêtre sans aucune clé `_murphy` ne rend aucune ligne "
      "(et ne tombe pas)",
      MU.par_balise([{"unit": "x", "day": "2026-07-01", "model": "m",
                      "lead_h": 6}]), [])

# ══════════════════════════════════════════════════════════════════
print("\n── 6. ⛔ On ne poole PAS les moments entre balises ──")
# ══════════════════════════════════════════════════════════════════
# Deux sites au vent très différent (un fond de vallée à ~8 km/h, une
# crête à ~30), le modèle étant MÉDIOCRE sur chacun (décalé d'un quart
# de cycle). Additionner leurs moments fabrique une variance
# INTER-SITES que le modèle « explique » parfaitement — parce qu'il
# sait lequel des deux est le plus venté — et le r² poolé s'envole.
u2 = []
for j in range(30):
    d_str = f"2026-07-{j + 1:02d}"
    for u, niveau in (("pioupiou:A", 8.0), ("pioupiou:B", 30.0)):
        f = [niveau + 3 * math.sin((i - 6) * math.pi / 12) for i in range(24)]
        o = [niveau + 3 * math.sin(i * math.pi / 12) for i in range(24)]
        u2.append({"unit": u, "day": d_str, "model": "icon_d2", "lead_h": 6,
                   MU.MURPHY_KEY: MU.moments(paires(f, o))})
l2 = MU.par_balise(u2)
resume = MU.par_modele(l2)[0]
poolee_a_plat = MU.decompose(MU.pool([d[MU.MURPHY_KEY] for d in u2]))
check("⭐ chaque balise, prise seule, a un r² effondré (le modèle est "
      "décalé partout)", max(l["r2"] for l in l2) < 0.05, True)
check("⭐⭐ … et pourtant les moments ADDITIONNÉS entre sites rendent un "
      f"r² proche de 1 ({poolee_a_plat['r2']:.3f}) — la variance "
      "inter-sites, prise pour du talent",
      poolee_a_plat["r2"] > 0.90, True)
check("⭐⭐ le résumé publié suit la MÉDIANE des balises, pas le pool",
      resume["r2"] < 0.05, True)
check("… et il dit combien de balises il médiane", resume["n_balises"], 2)
check("⚠️ le résumé DÉCLARE que l'identité n'y tient plus (trois "
      "médianes ne sont pas la médiane d'une somme)",
      resume["identity_holds"], False)
check("… les lignes sous le plancher n'entrent pas dans le résumé",
      MU.par_modele([{"model": "m", "lead_h": 6, "reason": "too_few_pairs"}]),
      [])

# ══════════════════════════════════════════════════════════════════
print("\n── 7. L'arrondi des six sommes ne déplace pas le verdict ──")
# ══════════════════════════════════════════════════════════════════
# ⚠️ `moments` arrondit à 4 décimales pour tenir dans le cache de
# rejeu. Le banc mesure ce que cet arrondi coûte, au lieu de l'affirmer.
brut = paires(fcst, obs)
exact = [len(brut),
         sum(p.fcst_speed for p in brut), sum(p.obs_speed for p in brut),
         sum(p.fcst_speed ** 2 for p in brut),
         sum(p.obs_speed ** 2 for p in brut),
         sum(p.fcst_speed * p.obs_speed for p in brut)]
de, da = MU.decompose(exact), MU.decompose(MU.moments(brut))
check("⭐ r² arrondi == r² exact à 1e−6 près", da["r2"], de["r2"], 1e-6)
check("… bc aussi", da["bc"], de["bc"], 1e-6)
check("… bs aussi", da["bs"], de["bs"], 1e-6)
check("`r` est borné à [−1, 1] même quand le flottant déborde",
      abs(MU.decompose(MU.moments(paires(base, base)))["r"]) <= 1.0, True)

# ══════════════════════════════════════════════════════════════════
print(f"\n{'✅' if KO == 0 else '❌'} {OK} assertions vertes, {KO} rouges.\n")
sys.exit(1 if KO else 0)
