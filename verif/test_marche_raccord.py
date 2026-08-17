#!/usr/bin/env python3
"""
test_marche_raccord.py — banc de la stratification par vitesse et du
filtre `--domaine`, HORS-LIGNE.                          (16/08/2026)

    python3 verif/test_marche_raccord.py

⚠️ CE QUE CE BANC PROTÈGE.

`marche_raccord.py` publiait un seul écart agrégé par niveau. Mesuré du
10 au 16/08 sur huit runs réels : la médiane de vent à 10 m ne dépasse
JAMAIS 1,5 m/s — un chiffre agrégé sur un tel échantillon est TENU par
construction, qu'il y ait un problème de raccord par vent fort ou non.
Ce banc REJOUE ce défaut sur des données synthétiques et vérifie qu'il
existe bel et bien (la médiane agrégée masque un sous-groupe venté), puis
vérifie que les deux correctifs du 16/08 le corrigent :

  1. `par_bacs()` isole la tranche ≥ 8 m/s de la masse calme.
  2. `--domaine` isole un domaine minoritaire du domaine majoritaire.

Un banc qui ne démontrerait que « la fonction ne lève pas » ne prouverait
rien : celui-ci prouve que le chiffre AVANT ces bacs et ce filtre était
trompeur, sur un cas construit pour l'être.
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "agrume"))

import colonnes as C  # noqa: E402
import quantification as Q  # noqa: E402
import marche_raccord as M  # noqa: E402
from domaine import NIVEAUX_H_0025, NIVEAUX_H_001  # noqa: E402

echecs = []


def verifier(nom, condition, detail=""):
    print(f"  {'✓' if condition else '✗'} {nom}" + (f"   {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


def main():
    print("── `par_bacs` : stratification pure, valeurs à la main ────")
    # 0,5 et 2,0 m/s tombent dans le bac « < 3 m/s », mais seul 2,0 passe
    # le seuil relatif (1,0 m/s) : 0,5 doit être COMPTÉ EXCLU, pas jeté.
    v_ref = np.array([0.5, 2.0, 4.0, 6.0, 9.0, 10.0])
    ecart = np.array([0.1, 0.3, 0.5, 1.0, 2.0, 2.2])
    bacs = {b["bac"]: b for b in M.par_bacs(v_ref, ecart)}

    verifier("bac « < 3 m/s » : 2 points (0,5 et 2,0)",
             bacs["< 3 m/s"]["absolu"]["n"] == 2)
    verifier("⚠️ mais 1 seul entre dans le relatif (2,0 ≥ seuil, 0,5 non) "
             "— et l'exclu est COMPTÉ, pas silencieux",
             bacs["< 3 m/s"]["n_exclus_relatif"] == 1
             and bacs["< 3 m/s"]["relatif_pct"]["n"] == 1)
    verifier("le relatif du point restant vaut 0,3/2,0 = 15 %",
             abs(bacs["< 3 m/s"]["relatif_pct"]["mediane"] - 15.0) < 1e-9,
             f"{bacs['< 3 m/s']['relatif_pct']['mediane']}")
    verifier("bac « ≥ 8 m/s » : 9,0 et 10,0",
             bacs["≥ 8 m/s"]["absolu"]["n"] == 2)
    verifier("aucun exclu dans ce bac (les deux dépassent le seuil relatif)",
             bacs["≥ 8 m/s"]["n_exclus_relatif"] == 0)
    verifier("bac vide (aucune vitesse dans 5-8) → absolu None, pas une "
             "exception",
             bacs["5-8 m/s"]["absolu"]["n"] == 1)  # 6.0 tombe ici
    vide = M.par_bacs(np.array([50.0]), np.array([0.0]))
    verifier("aucune valeur dans un bac donné rend `absolu` à None",
             [b for b in vide if b["bac"] == "< 3 m/s"][0]["absolu"] is None)

    print("\n── `_indices_domaine` : la sélection, et son cas vide ─────")
    bal = [dict(domaine="a"), dict(domaine="b"), dict(domaine="a"), dict()]
    verifier("sans domaine demandé : tout le monde",
             M._indices_domaine(bal, None) == [0, 1, 2, 3])
    verifier("domaine 'a' : les deux bonnes balises, dans l'ordre",
             M._indices_domaine(bal, "a") == [0, 2])
    verifier("domaine absent de l'archive : liste VIDE, pas une exception",
             M._indices_domaine(bal, "c") == [])
    verifier("la balise sans clé `domaine` (`.get` renvoie None) ne "
             "matche jamais un nom",
             M._indices_domaine(bal, None)[3] == 3
             and 3 not in M._indices_domaine(bal, "a"))

    print("\n── ⛔ LE DÉFAUT REJOUÉ : la médiane agrégée masque un ────")
    print("   domaine minoritaire venté — puis les deux correctifs")
    # 30 balises « calmes » (référence 1 m/s, marche de raccord 0,05 m/s)
    # et 5 balises « ventées » (référence 9 m/s, marche 3,00 m/s) dans un
    # domaine à part. Sans stratification ni filtre, c'est EXACTEMENT le
    # profil mesuré en vrai le 16/08 (207 Alpes calmes contre 55 Pyrénées
    # ventées) — juste des proportions et des chiffres qui rendent le
    # verdict lisible à l'œil.
    n_calme, n_vent = 30, 5
    balises = ([dict(id=f"c{k}", lat=45.0, lon=6.0, domaine="calme_dom")
               for k in range(n_calme)]
              + [dict(id=f"v{k}", lat=42.9, lon=0.5, domaine="vent_dom")
                 for k in range(n_vent)])
    col = C.Colonnes("2026-08-16T00:00:00Z", balises, [0])
    j0 = NIVEAUX_H_0025.index(100)
    j1 = NIVEAUX_H_001.index(100)
    iu0 = {p["nom"]: k for k, p in enumerate(Q.PARAMS_0025)}["u"]
    iv0 = {p["nom"]: k for k, p in enumerate(Q.PARAMS_0025)}["v"]
    iu1 = {p["nom"]: k for k, p in enumerate(Q.PARAMS_001)}["u"]
    iv1 = {p["nom"]: k for k, p in enumerate(Q.PARAMS_001)}["v"]
    # Référence (0,025°) : 1 m/s plein est pour les calmes, 9 pour les
    # ventées. Maille fine (0,01°) : décalée de 0,05 m/s pour les calmes
    # (marche négligeable), de 3,00 m/s pour les ventées (marche réelle).
    col.c0025[:n_calme, iu0, j0, 0] = 1.0
    col.c0025[:n_calme, iv0, j0, 0] = 0.0
    col.c001[:n_calme, iu1, j1, 0] = 1.05
    col.c001[:n_calme, iv1, j1, 0] = 0.0
    col.c0025[n_calme:, iu0, j0, 0] = 9.0
    col.c0025[n_calme:, iv0, j0, 0] = 0.0
    col.c001[n_calme:, iu1, j1, 0] = 12.0
    col.c001[n_calme:, iv1, j1, 0] = 0.0

    silence = lambda *_a: None
    r_tout = M.mesurer(col, None, crier=silence)
    med_agrege = r_tout["par_niveau"][100]["vitesse"]["mediane"]
    verifier("⛔ LE DÉFAUT EXISTE : la médiane agrégée (35 balises, 30 "
             "calmes) reste sous le critère de 1 m/s alors que 5 balises "
             "ont une marche de 3,00 m/s — le vieux chiffre unique aurait "
             "dit « TENU » et se serait trompé",
             med_agrege < 1.0, f"médiane agrégée {med_agrege:.3f} m/s")

    bac_fort = {b["bac"]: b for b in
               r_tout["par_niveau"][100]["par_bac"]}["≥ 8 m/s"]
    verifier("✅ CORRECTIF 1 (bacs) : la tranche ≥ 8 m/s isole la vraie "
             "marche, 3,00 m/s, dans le MÊME appel — rien à retélécharger",
             abs(bac_fort["absolu"]["mediane"] - 3.0) < 1e-6,
             f"{bac_fort['absolu']['mediane']:.3f} m/s (n={bac_fort['absolu']['n']})")
    verifier("le bac ≥ 8 m/s ne contient QUE les 5 balises ventées",
             bac_fort["absolu"]["n"] == n_vent)

    r_dom = M.mesurer(col, None, crier=silence, domaine="vent_dom")
    verifier("✅ CORRECTIF 2 (--domaine) : filtré sur le domaine venté, "
             "la médiane DEVIENT 3,00 m/s — la dilution a disparu",
             abs(r_dom["par_niveau"][100]["vitesse"]["mediane"] - 3.0) < 1e-6,
             f"{r_dom['par_niveau'][100]['vitesse']['mediane']:.3f} m/s")
    verifier("et le compte de balises correspond au seul domaine demandé",
             r_dom["n_balises"] == n_vent)

    r_absent = M.mesurer(col, None, crier=silence, domaine="n-existe-pas")
    verifier("un domaine absent de l'archive rend 0 balise et un "
             "`par_niveau` VIDE, pas une exception",
             r_absent["n_balises"] == 0 and r_absent["par_niveau"] == {})

    print("\n── ⛔ LE DÉFAUT nº 2, REJOUÉ : l'ABSOLU CONDAMNE UN ─────")
    print("   raccord sain, et absout un raccord malade — le CRITÈRE")
    print("   RELATIF (17/08) tranche là où l'absolu se trompe")
    # Deux populations, toutes deux DANS le bac ≥ 8 m/s :
    #   · `fort_propre` : 20 m/s de référence, marche 1,5 m/s → 7,5 %.
    #     Le raccord est BON (les deux mailles s'accordent à 7,5 % du
    #     signal) et pourtant l'absolu (1,5 > 1) crie « DÉPASSÉ ».
    #     C'est le cas réel de nord-alpes le 17/08 — dépassement porté
    #     par l'orographie, pas par le raccord.
    #   · `fort_sale`   : 8 m/s de référence, marche 2,0 m/s → 25 %.
    #     Là, le raccord est VRAIMENT en défaut, et les deux critères
    #     doivent le dire.
    # Les quatre valeurs (20 · 21,5 · 8 · 10) sont exactement
    # représentables en float16 : le banc mesure le critère, pas
    # l'arrondi du conteneur.
    n_propre, n_sale = 10, 5
    bal2 = ([dict(id=f"p{k}", lat=45.0, lon=6.0, domaine="fort_propre")
             for k in range(n_propre)]
            + [dict(id=f"s{k}", lat=42.9, lon=0.5, domaine="fort_sale")
               for k in range(n_sale)])
    col2 = C.Colonnes("2026-08-17T03:00:00Z", bal2, [0])
    col2.c0025[:n_propre, iu0, j0, 0] = 20.0
    col2.c0025[:n_propre, iv0, j0, 0] = 0.0
    col2.c001[:n_propre, iu1, j1, 0] = 21.5
    col2.c001[:n_propre, iv1, j1, 0] = 0.0
    col2.c0025[n_propre:, iu0, j0, 0] = 8.0
    col2.c0025[n_propre:, iv0, j0, 0] = 0.0
    col2.c001[n_propre:, iu1, j1, 0] = 10.0
    col2.c001[n_propre:, iv1, j1, 0] = 0.0

    r2 = M.mesurer(col2, None, crier=silence)
    abs_med = r2["par_niveau"][100]["vitesse"]["mediane"]
    vr = r2["verdict_relatif"]
    verifier("⛔ LE DÉFAUT EXISTE : l'absolu dit « DÉPASSÉ » (médiane "
             "1,50 m/s > 1) sur un échantillon dont 10 couples sur 15 "
             "s'accordent à 7,5 % du vent",
             abs_med >= 1.0, f"médiane absolue {abs_med:.2f} m/s")
    verifier("✅ CORRECTIF : le verdict RELATIF existe, porte sur le bac "
             "≥ 8 m/s, et compte les 15 couples",
             vr is not None and vr["bac"] == "≥ 8 m/s" and vr["n"] == 15,
             f"{vr}")
    verifier("il vaut 7,5 % en médiane et il est TENU — le raccord est "
             "sain là où l'absolu le condamnait",
             abs(vr["mediane_pct"] - 7.5) < 1e-6 and vr["tenu"] is True,
             f"{vr['mediane_pct']:.2f} %")

    r2_sale = M.mesurer(col2, None, crier=silence, domaine="fort_sale")
    vs = r2_sale["verdict_relatif"]
    verifier("⚠️ ET IL SAIT ÉCHOUER : sur le seul domaine vraiment en "
             "défaut, le relatif monte à 25 % et le verdict passe à "
             "DÉPASSÉ — un critère qui ne dirait jamais non ne dirait rien",
             abs(vs["mediane_pct"] - 25.0) < 1e-6 and vs["tenu"] is False,
             f"{vs['mediane_pct']:.2f} %")
    verifier("le seuil publié est bien celui du module, pas une constante "
             "recopiée dans le verdict",
             vs["seuil_pct"] == M.SEUIL_RELATIF_VERDICT_PCT)

    r_calme = M.mesurer(col, None, crier=silence, domaine="calme_dom")
    verifier("un run sans AUCUN couple ≥ 8 m/s rend `verdict_relatif` à "
             "None — pas de verdict inventé, pas d'exception",
             r_calme["verdict_relatif"] is None)

    print("\n  marche_raccord :", "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
