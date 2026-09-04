#!/usr/bin/env python3
"""test_biais_fin.py — banc du biais de site par secteur × tranche
(lot L19, 04/09/2026). Sans réseau, sans base, sans `score.py`.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import biais_fin as BF   # noqa: E402
import scoring as S      # noqa: E402

OK = KO = 0


def check(label: str, cond: bool, detail: str = ""):
    global OK, KO
    if cond:
        OK += 1
    else:
        KO += 1
        print(f"  ❌ {label}" + (f"\n       {detail}" if detail else ""))


T0 = 1_756_944_000_000        # 2026-09-04 00:00 UTC, ms
H = 3_600_000


def paire(h, fs, fd, os_, od=None):
    return S.VerifPair(t=T0 + h * H, fcst_speed=fs, fcst_dir=fd,
                       obs_speed=os_, obs_dir=od if od is not None else fd, n_obs=5)


# ══════════════════════════════════════════════════════════════════
print("── 1. LA CELLULE : connue AVANT l'observation ──")
# ══════════════════════════════════════════════════════════════════
check("06:00 UTC + 2 h = 08:00 local → matin", BF.tranche(T0 + 6 * H, 7200) == "matin")
check("12:00 UTC + 2 h = 14:00 → aprem", BF.tranche(T0 + 12 * H, 7200) == "aprem")
check("20:00 UTC + 2 h = 22:00 → nuit", BF.tranche(T0 + 20 * H, 7200) == "nuit")
check("… et sans décalage, 05:00 est encore la nuit", BF.tranche(T0 + 5 * H, 0) == "nuit")
check("cellule = quadrant du cap PRÉVU × tranche",
      BF.cellule(paire(8, 20.0, 350.0, 5.0, 170.0), 7200) == "N|matin")
check("⛔ le cap OBSERVÉ n'entre pas dans la cellule (170° observé, "
      "cellule N quand même)",
      BF.cellule(paire(8, 20.0, 350.0, 5.0, 170.0), 7200).startswith("N|"))
check("pas de cap prévu → pas de cellule",
      BF.cellule(paire(10, 20.0, None, 5.0), 7200) is None)
check("un cap prévu sous DIR_MIN_WIND_KMH est du bruit → pas de cellule",
      BF.cellule(paire(10, 3.0, 90.0, 5.0), 7200) is None)

# ══════════════════════════════════════════════════════════════════
print("── 2. LES SOMMES DU JOUR, ET LEUR MÉMOIRE ──")
# ══════════════════════════════════════════════════════════════════
pairs = [paire(8, 10.0, 0.0, 8.0), paire(9, 10.0, 0.0, 8.0),      # N|matin ×0,8
         paire(14, 10.0, 180.0, 15.0), paire(15, 10.0, 180.0, 15.0)]  # S|aprem ×1,5
s = BF.sommes_du_jour(pairs, 0)
check("une somme par cellule vue", set(s) == {"N|matin", "S|aprem"}, f"{s}")
check("Σof, Σff, n — la pente N|matin en sort à 0,8",
      abs(s["N|matin"][0] / s["N|matin"][1] - 0.8) < 1e-9 and s["N|matin"][2] == 2)

acc = BF.AccSommes()
for i in range(3):
    acc.push(i, [80.0, 100.0, 6])          # 6 h/jour à ×0,8
check("3 journées × 6 h = 18 h ≥ 12 et 3 j ≥ 3 → la pente parle (0,8)",
      acc.pente is not None and abs(acc.pente - 0.8) < 1e-9, f"{acc.pente}")
maigre = BF.AccSommes()
for i in range(3):
    maigre.push(i, [8.0, 10.0, 2])         # 2 h/jour : 6 h < 12
check("⛔ 3 journées mais 6 heures seulement → la cellule se TAIT",
      maigre.pente is None)
jeune = BF.AccSommes()
jeune.push(0, [800.0, 1000.0, 40])
jeune.push(1, [800.0, 1000.0, 40])
check("80 heures mais 2 journées → se tait aussi", jeune.pente is None)
fou = BF.AccSommes()
for i in range(3):
    fou.push(i, [30.0, 100.0, 6])          # ×0,3 : hors bornes
check("une pente hors [0,4 ; 2,5] ne corrige PAS (mât cassé, pas un site)",
      fou.pente is None)
check("une journée déjà intégrée est refusée",
      (acc.push(2, [1.0, 1.0, 6]), acc.days)[1] == 3)

# la décroissance : 10 j à ×2 puis 5 j à ×1 → la pente descend sous la
# moyenne plate
dec = BF.AccSommes()
for i in range(10):
    dec.push(i, [200.0, 100.0, 6])
for i in range(10, 15):
    dec.push(i, [100.0, 100.0, 6])
plate = (10 * 200 + 5 * 100) / (15 * 100)
check("la mémoire pèse les journées récentes (pente < moyenne plate)",
      dec.pente is not None and dec.pente < plate - 0.02, f"{dec.pente} vs {plate}")

# ══════════════════════════════════════════════════════════════════
print("── 3. LE REPLI : cellule → secteur → balise ──")
# ══════════════════════════════════════════════════════════════════
pr = BF.PriorFin()
for i in range(4):
    pr.push(i, {"N|matin": [80.0, 100.0, 4],       # ×0,8, 16 h
                "N|aprem": [10.0, 10.0, 1],         # ×1,0, 4 h — trop maigre
                "S|aprem": [150.0, 100.0, 5]})      # ×1,5, 20 h
p, niveau, nj = pr.pente_pour("N|matin")
check("N|matin a sa propre pente (0,8) au niveau secteur_heure",
      abs(p - 0.8) < 1e-9 and niveau == "secteur_heure" and nj == 4, f"{p, niveau, nj}")
p, niveau, nj = pr.pente_pour("N|aprem")
check("⭐ N|aprem, trop maigre, RETOMBE sur le secteur N (0,8 + 1,0 "
      "pondérés par leurs sommes)",
      niveau == "secteur" and abs(p - (90.0 / 110.0)) < 1e-9, f"{p, niveau}")
p, niveau, nj = pr.pente_pour("W|nuit")
check("un secteur jamais vu → rien, l'appelant retombe sur le S2",
      p is None and niveau is None)
check("pas de cellule → rien", pr.pente_pour(None) == (None, None, 0))
check("un prior qui a au moins une cellule parlante n'est pas vide",
      not pr.vide())
check("… et un prior nourri de sommes maigres l'est", BF.PriorFin().vide())

# appliquer
pairs_j = [paire(8, 10.0, 0.0, 8.0),      # N|matin → ×0,8 → 8,0 : erreur 0
           paire(14, 10.0, 0.0, 9.0),     # N|aprem → secteur N (0,818) → 8,18
           paire(15, 10.0, 270.0, 12.0)]  # W|aprem → S2 (1,2) → 12 : erreur 0
corr, compte, nj_med = BF.appliquer(pairs_j, pr, 1.2, None, 0)
check("chaque heure reçoit la pente la plus fine disponible",
      abs(corr[0].fcst_speed - 8.0) < 1e-9
      and abs(corr[1].fcst_speed - 10 * 90 / 110) < 1e-9
      and abs(corr[2].fcst_speed - 12.0) < 1e-9,
      f"{[c.fcst_speed for c in corr]}")
check("… et le compte dit qui a parlé",
      compte == {"secteur_heure": 1, "secteur": 1, "balise": 1}, f"{compte}")
check("le niveau dominant départage sur le nombre d'heures, puis du plus fin",
      BF.niveau_dominant(compte) == "secteur_heure")
check("… `balise` domine quand il corrige le plus d'heures",
      BF.niveau_dominant({"balise": 5, "secteur": 2}) == "balise")
check("… quel que soit l'ORDRE du dictionnaire",
      BF.niveau_dominant({"secteur": 2, "balise": 5}) == "balise"
      and BF.niveau_dominant({"balise": 1, "secteur_heure": 3}) == "secteur_heure")
check("… et aucune heure corrigée → None",
      BF.niveau_dominant({"aucun": 8}) is None)
corr2, compte2, _ = BF.appliquer(pairs_j, None, None, None, 0)
check("sans aucun prior, rien ne bouge et tout se compte `aucun`",
      [c.fcst_speed for c in corr2] == [10.0, 10.0, 10.0] and compte2 == {"aucun": 3})
corr3, _, _ = BF.appliquer(pairs_j, pr, 1.2, 30.0, 0)
check("le cap du S2 s'applique à toutes les heures, quel que soit le niveau",
      all(abs(c.fcst_dir - ((p_.fcst_dir + 30) % 360)) < 1e-9
          for c, p_ in zip(corr3, pairs_j)))
check("⛔ l'observation n'est JAMAIS touchée",
      all(c.obs_speed == p_.obs_speed for c, p_ in zip(corr3, pairs_j)))

# ══════════════════════════════════════════════════════════════════
print("── 4. LE PLACEBO : les mêmes mémoires, tournées ──")
# ══════════════════════════════════════════════════════════════════
perm = pr.permute()
check("la rotation déplace N|matin en E|aprem",
      "E|aprem" in perm.cellules and "N|matin" not in perm.cellules,
      f"{sorted(perm.cellules)}")
check("… et le secteur N en E", "E" in perm.secteurs and "N" not in perm.secteurs)
check("… en gardant les mêmes effectifs (même couverture)",
      len(perm.cellules) == len(pr.cellules) and len(perm.secteurs) == len(pr.secteurs))
check("… sans toucher l'original", "N|matin" in pr.cellules)

# ══════════════════════════════════════════════════════════════════
print("── 5. LE BILAN DU TÉMOIN ──")
# ══════════════════════════════════════════════════════════════════
tem = [(10.0, 8.0, 6.0, 7.5)] * 40          # brut, S2, fin, placebo
b = BF.bilan_temoin_fin(tem)
check("le bilan existe dès 30 échantillons complets", b is not None)
check("S2 gagne 20 % sur le brut", b and b["gain_s2_pct"] == 20.0, f"{b}")
check("le fin gagne 25 % de plus sur le S2 (8 → 6)", b and b["gain_fin_sur_s2_pct"] == 25.0)
check("le placebo en gagne 6,2 (8 → 7,5)", b and b["gain_placebo_sur_s2_pct"] == 6.2)
check("⛔ la part imputable au secteur × heure est la DIFFÉRENCE (18,8)",
      b and b["part_secteur_heure_pct"] == 18.8, f"{b}")
check("un échantillon incomplet (None) ne compte pas",
      BF.bilan_temoin_fin(tem[:29] + [(10.0, None, 6.0, 7.5)] * 5) is None)

# ══════════════════════════════════════════════════════════════════
print(f"\n{'✅' if KO == 0 else '❌'} {OK} assertions vertes, {KO} rouges.\n")
sys.exit(1 if KO else 0)
