#!/usr/bin/env python3
"""test_controle_tau.py — banc du TAU INTER-POPULATIONS (lot L8, 28/08/2026).

Ce banc ne vérifie pas que `controle_tau.py` rend un objet de la bonne
forme : il vérifie qu'il MESURE l'accord de deux classements, sur des
populations SYNTHÉTIQUES dont l'accord est connu parce qu'on l'a
fabriqué — c'est l'exigence explicite du prompt du lot.

Les scènes, et pourquoi chacune existe :

  1. **ACCORD PARFAIT** — la population range les modèles dans l'ordre
     de la référence : tau = +1. Sans elle, un tau qui rendrait toujours
     0 passerait pour prudent.
  2. **DÉSACCORD PARFAIT** — ordre exactement inverse : tau = −1.
  3. **ACCORD PARTIEL calculé à la main** — une seule paire inversée sur
     trois modèles : tau-b = 1/3, vérifié par l'arithmétique
     (conc = 2, disc = 1, aucun ex aequo) et pas par ce que rend le code.
  4. **k = 1** — un seul modèle partagé : pas de tau, et une raison qui
     le dit. C'est le cas `metar` en production, et il ne doit pas se
     lire comme une panne.
  5. ⭐ **LA SCÈNE DU LOT** — le noyau commun et le brut se CONTREDISENT.
     Un modèle est noté sur deux journées supplémentaires, faciles ;
     classé sur ses propres jours il gagne, classé sur le noyau il perd.
     C'est la forme exacte de la discordance `arome_r2`/`infoclimat`
     que le lot doit instruire, et un contrôle qui ne saurait pas la
     distinguer d'un vrai désaccord de réseau ne servirait à rien.
  6. **DOUBLONS DE RÉSEAU** — une balise republiée d'un réseau à l'autre
     est retirée, et le retrait est COMPTÉ.
  7. **RÉSERVE `run_init`** — les quatre verdicts, dont la distinction
     « objet absent » / « objet présent sans `run_init` ».

⛔ ET LE JEU EST IRRÉGULIER DANS LA DIMENSION TESTÉE (piège nº 2 de la
phase B, 26/08). La dimension testée ici est le couple (jour, balise) :
le nombre de balises change d'un jour à l'autre, certaines manquent pour
un seul modèle, les erreurs ne sont pas les mêmes d'un jour à l'autre.
Un jeu où tous les modèles voient toutes les balises tous les jours
rendrait le noyau commun égal au brut — et la scène 5, la seule qui
compte vraiment, ne pourrait pas exister.

Aucun `random` : générateur congruentiel maison, graine explicite
(piège nº 4 du 26/08 phase B : `hash()` n'est pas rejouable).

Usage :
    python3 test_controle_tau.py
"""
from __future__ import annotations

import gzip
import json
import pathlib
import sys
import tempfile

import controle_tau as CT
import inference as INF
import score as SC
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

    def __init__(self, seed: int = 20260828):
        self.s = seed & 0xFFFFFFFF

    def u(self) -> float:
        self.s = (1103515245 * self.s + 12345) & 0x7FFFFFFF
        return self.s / 0x7FFFFFFF


def ligne(day, source, sid, model, err, lead=6, src="own_archive"):
    return {"day": day, "source": source, "station_id": str(sid),
            "model": model, "lead_h": lead, "fcst_src": src,
            "err_vec_med": err}


JOURS = ["2026-08-22", "2026-08-23", "2026-08-24", "2026-08-25", "2026-08-26"]


def population(source, err_par_modele, jours=JOURS, n_balises=12,
               seed=1, absents=()):
    """Fabrique une population : erreur MOYENNE imposée par modèle.

    `absents` : couples (modele, jour) que ce modèle ne note pas — c'est
    ce qui rend le jeu irrégulier et le noyau commun plus petit que le
    brut.
    """
    g = LCG(seed)
    out = []
    for j, jour in enumerate(jours):
        # ⚠️ le nombre de balises CHANGE d'un jour à l'autre : sinon
        # « moyenne des moyennes » et « moyenne globale » coïncident et
        # aucune mutation ne les sépare.
        combien = n_balises - (j % 3)
        for b in range(combien):
            for m, base in err_par_modele.items():
                if (m, jour) in absents:
                    continue
                out.append(ligne(jour, source, f"{source[:2]}{b}", m,
                                 round(base + 0.4 * (g.u() - 0.5), 4)))
    return out


print("\n── 1-2. accord parfait, désaccord parfait ─────────────────────")

REF = {"alpha": 3.0, "beta": 4.0, "gamma": 5.0}
ref_rows = population("pioupiou", REF, seed=7)
accord = population("windsmobi", {"alpha": 3.1, "beta": 4.1, "gamma": 5.1},
                    seed=11)
inverse = population("infoclimat", {"alpha": 5.2, "beta": 4.2, "gamma": 3.2},
                     seed=13)

res = CT.controle_tau(ref_rows + accord + inverse)
par_src = {p["source"]: p for p in res["populations"]}
check("l'accord parfait rend tau = +1",
      par_src["windsmobi"]["noyau"]["tau_b"] == 1.0,
      f"{par_src['windsmobi']['noyau']['tau_b']}")
check("le désaccord parfait rend tau = −1",
      par_src["infoclimat"]["noyau"]["tau_b"] == -1.0,
      f"{par_src['infoclimat']['noyau']['tau_b']}")
check("la référence n'est pas comparée à elle-même",
      "pioupiou" not in par_src, f"{sorted(par_src)}")
check("les trois modèles sont bien reconnus partagés",
      par_src["windsmobi"]["modeles_partages"] == ["alpha", "beta", "gamma"])
check("le classement de la référence est celui qu'on a fabriqué",
      [s["model"] for s in par_src["windsmobi"]["noyau"]["reference"]["lignes"]]
      == ["alpha", "beta", "gamma"])
check("… et celui de la population inversée aussi",
      [s["model"] for s in par_src["infoclimat"]["noyau"]["population"]["lignes"]]
      == ["gamma", "beta", "alpha"])

print("\n── 3. accord partiel, tau calculé À LA MAIN ───────────────────")

# trois modèles, une seule paire inversée (beta et gamma échangés) :
#   paires (a,b) (a,g) (b,g) → concordantes 2, discordante 1, ex aequo 0
#   tau-b = (2 − 1) / sqrt(3 × 3) = 1/3
partiel = CT.tau_population({"alpha": 1, "gamma": 2, "beta": 3},
                            {"alpha": 1, "beta": 2, "gamma": 3})
check("une paire inversée sur trois modèles rend tau-b = 1/3",
      partiel[0] is not None and abs(partiel[0] - 1 / 3) < 1e-12,
      f"{partiel}")
check("… et k vaut 3, pas le nombre de paires",
      partiel[1] == 3, f"{partiel}")
check("l'accord total vaut exactement +1",
      CT.tau_population({"a": 1, "b": 2}, {"a": 1, "b": 2})[0] == 1.0)
check("l'inversion totale vaut exactement −1",
      CT.tau_population({"a": 1, "b": 2}, {"a": 2, "b": 1})[0] == -1.0)

print("\n── 4. k = 1 : pas de tau, et une raison qui le dit ────────────")

seul = CT.tau_population({"arome_r2": 1}, {"arome_r2": 1, "autre": 2})
check("un seul modèle partagé ne rend PAS de tau",
      seul[0] is None, f"{seul}")
check("… avec la raison nommée, pas un None muet",
      seul[2] == "trop_peu_de_modeles", f"{seul}")

metar = population("metar", {"alpha": 3.3}, seed=17)
res_m = CT.controle_tau(ref_rows + metar)
p_metar = [p for p in res_m["populations"] if p["source"] == "metar"][0]
check("une population à k=1 a une LIGNE dans le rapport (pas d'absence)",
      p_metar["raison"] == "trop_peu_de_modeles_partages", f"{p_metar}")
check("… et sa ligne porte quand même le nombre de balises",
      p_metar["n_balises"] > 0)

print("\n── 5. ⭐ LA SCÈNE DU LOT : le noyau et le brut se contredisent ─")

# La forme exacte de la discordance à instruire : `alpha` (le rôle
# d'`arome_r2`) est noté sur DEUX JOURNÉES DE PLUS que `beta`, et ces
# journées-là sont mauvaises pour tout le monde. Classé sur SES jours il
# perd ; classé sur les jours COMMUNS il gagne, comme chez la référence.
def scene_discordante():
    g = LCG(4242)
    rows = []
    # les jours 22-24 : alpha SEUL, et le temps y est difficile
    for j, jour in enumerate(["2026-08-22", "2026-08-23", "2026-08-24"]):
        for b in range(12 - j):
            rows.append(ligne(jour, "infoclimat", f"ic{b}", "alpha",
                              round(9.0 + 0.4 * (g.u() - 0.5), 4)))
    # les jours 25-26 : les deux modèles, et alpha y est MEILLEUR
    for j, jour in enumerate(["2026-08-25", "2026-08-26"]):
        for b in range(11 - j):
            rows.append(ligne(jour, "infoclimat", f"ic{b}", "alpha",
                              round(3.0 + 0.4 * (g.u() - 0.5), 4)))
            rows.append(ligne(jour, "infoclimat", f"ic{b}", "beta",
                              round(4.0 + 0.4 * (g.u() - 0.5), 4)))
    return rows


disc = scene_discordante()
res5 = CT.controle_tau(ref_rows + disc)
p5 = [p for p in res5["populations"] if p["source"] == "infoclimat"][0]
check("le classement BRUT range alpha DERNIER (il traîne ses mauvais jours)",
      [s["model"] for s in p5["brut"]["population"]["lignes"]]
      == ["beta", "alpha"],
      f"{p5['brut']['population']['lignes']}")
check("… donc le tau BRUT annonce un DÉSACCORD de réseau",
      p5["brut"]["tau_b"] == -1.0, f"{p5['brut']['tau_b']}")
check("le classement SUR LE NOYAU range alpha PREMIER",
      [s["model"] for s in p5["noyau"]["population"]["lignes"]]
      == ["alpha", "beta"],
      f"{p5['noyau']['population']['lignes']}")
check("… et le tau sur le noyau dit ACCORD : le désaccord était un "
      "artefact de calendrier",
      p5["noyau"]["tau_b"] == 1.0, f"{p5['noyau']['tau_b']}")
check("le noyau est STRICTEMENT plus petit que le brut (sinon la scène "
      "ne teste rien)",
      p5["noyau"]["n_lignes_population"] < p5["brut"]["n_lignes_population"],
      f"{p5['noyau']['n_lignes_population']} vs {p5['brut']['n_lignes_population']}")
check("le noyau ne retient que les journées communes",
      p5["jours_noyau_population"] == ["2026-08-25", "2026-08-26"],
      f"{p5['jours_noyau_population']}")
check("les jours de la population entière, eux, sont les cinq",
      len(p5["jours_population"]) == 5, f"{p5['jours_population']}")

print("\n── 5 ter. ⭐ le noyau s'applique AUX DEUX CÔTÉS ────────────────")

# ⚠️ Scène écrite APRÈS coup, parce qu'une mutation est restée VERTE :
# « le noyau n'est appliqué qu'à la population, pas à la référence ».
# Toutes les scènes précédentes avaient une RÉFÉRENCE régulière (tous
# les modèles sur tous les jours) — l'y apparier ou non donnait le même
# ordre, et la mutation était donc indétectable. C'est le piège nº 2 de
# la phase B (26/08) dans sa forme exacte : le jeu d'essai doit être
# irrégulier DANS LA DIMENSION où vit la propriété testée, et cette
# dimension-ci est le calendrier DE LA RÉFÉRENCE.
def scene_reference_irreguliere():
    g = LCG(909)
    rows = []
    for j, jour in enumerate(["2026-08-22", "2026-08-23", "2026-08-24"]):
        for b in range(12 - j):
            rows.append(ligne(jour, "pioupiou", f"pp{b}", "alpha",
                              round(9.0 + 0.4 * (g.u() - 0.5), 4)))
    for j, jour in enumerate(["2026-08-25", "2026-08-26"]):
        for b in range(11 - j):
            rows.append(ligne(jour, "pioupiou", f"pp{b}", "alpha",
                              round(3.0 + 0.4 * (g.u() - 0.5), 4)))
            rows.append(ligne(jour, "pioupiou", f"pp{b}", "beta",
                              round(4.0 + 0.4 * (g.u() - 0.5), 4)))
    # la population, elle, est RÉGULIÈRE et d'accord avec la référence
    # une fois celle-ci appariée
    for j, jour in enumerate(["2026-08-25", "2026-08-26"]):
        for b in range(11 - j):
            rows.append(ligne(jour, "mf", f"mf{b}", "alpha",
                              round(3.0 + 0.4 * (g.u() - 0.5), 4)))
            rows.append(ligne(jour, "mf", f"mf{b}", "beta",
                              round(4.0 + 0.4 * (g.u() - 0.5), 4)))
    return rows


res5t = CT.controle_tau(scene_reference_irreguliere())
p5t = [p for p in res5t["populations"] if p["source"] == "mf"][0]
check("la RÉFÉRENCE aussi est ramenée à son noyau : alpha y repasse 1ᵉʳ",
      [s["model"] for s in p5t["noyau"]["reference"]["lignes"]]
      == ["alpha", "beta"],
      f"{p5t['noyau']['reference']['lignes']}")
check("… donc le tau sur le noyau dit ACCORD",
      p5t["noyau"]["tau_b"] == 1.0, f"{p5t['noyau']['tau_b']}")
check("non appariée, la référence rangerait alpha DERNIER (la scène "
      "teste bien quelque chose)",
      [s["model"] for s in p5t["brut"]["reference"]["lignes"]]
      == ["beta", "alpha"],
      f"{p5t['brut']['reference']['lignes']}")
check("… et le tau BRUT annoncerait alors un désaccord",
      p5t["brut"]["tau_b"] == -1.0, f"{p5t['brut']['tau_b']}")
check("le noyau de la référence est plus petit que sa population entière",
      p5t["noyau"]["n_lignes_reference"] < p5t["brut"]["n_lignes_reference"],
      f"{p5t['noyau']['n_lignes_reference']} vs {p5t['brut']['n_lignes_reference']}")


print("\n── 5 quater. ⭐ les deux côtés sur les MÊMES JOURNÉES ──────────")

# ⚠️ Scène née d'une mesure, pas d'une relecture : au 27/08 le noyau
# d'`aemet` tient sur 2 journées et celui de Pioupiou sur les mêmes
# modèles sur 5. Ici la référence voit une période où `alpha` domine
# (22-24) et une où `beta` domine (25-26) ; la population, elle, ne
# connaît que la seconde. Sans alignement des calendriers, le contrôle
# annoncerait un désaccord de RÉSEAU là où il n'y a qu'un changement
# de TEMPS.
def scene_calendriers():
    g = LCG(31337)
    rows = []
    for j, jour in enumerate(["2026-08-22", "2026-08-23", "2026-08-24"]):
        for b in range(12 - j):
            rows.append(ligne(jour, "pioupiou", f"pq{b}", "alpha",
                              round(1.0 + 0.3 * (g.u() - 0.5), 4)))
            rows.append(ligne(jour, "pioupiou", f"pq{b}", "beta",
                              round(8.0 + 0.3 * (g.u() - 0.5), 4)))
    for j, jour in enumerate(["2026-08-25", "2026-08-26"]):
        for b in range(11 - j):
            rows.append(ligne(jour, "pioupiou", f"pq{b}", "alpha",
                              round(5.0 + 0.3 * (g.u() - 0.5), 4)))
            rows.append(ligne(jour, "pioupiou", f"pq{b}", "beta",
                              round(4.0 + 0.3 * (g.u() - 0.5), 4)))
            rows.append(ligne(jour, "aemet", f"ae{b}", "alpha",
                              round(5.1 + 0.3 * (g.u() - 0.5), 4)))
            rows.append(ligne(jour, "aemet", f"ae{b}", "beta",
                              round(4.1 + 0.3 * (g.u() - 0.5), 4)))
    return rows


res5q = CT.controle_tau(scene_calendriers())
p5q = [p for p in res5q["populations"] if p["source"] == "aemet"][0]
check("les journees que la population n'a pas sont ECARTEES de la reference",
      p5q["jours_ecartes_reference"]
      == ["2026-08-22", "2026-08-23", "2026-08-24"],
      f"{p5q['jours_ecartes_reference']}")
check("… et la population, elle, ne perd rien (elle est le calendrier court)",
      p5q["jours_ecartes_population"] == [], f"{p5q['jours_ecartes_population']}")
check("le noyau retenu est exactement l'intersection des calendriers",
      p5q["jours_noyau_population"] == ["2026-08-25", "2026-08-26"],
      f"{p5q['jours_noyau_population']}")
check("⭐ aligne, le classement de reference dit beta 1ᵉʳ, comme la population",
      [s["model"] for s in p5q["noyau"]["reference"]["lignes"]]
      == ["beta", "alpha"], f"{p5q['noyau']['reference']['lignes']}")
check("… donc le tau dit ACCORD",
      p5q["noyau"]["tau_b"] == 1.0, f"{p5q['noyau']['tau_b']}")
check("non aligne, la reference dirait alpha 1ᵉʳ (la scene teste bien "
      "quelque chose)",
      [s["model"] for s in p5q["brut"]["reference"]["lignes"]]
      == ["alpha", "beta"], f"{p5q['brut']['reference']['lignes']}")
check("… et le tau brut annoncerait un desaccord de reseau qui n'existe pas",
      p5q["brut"]["tau_b"] == -1.0, f"{p5q['brut']['tau_b']}")
check("le rapport NOMME les journees ecartees (le prix est publie)",
      "alignement des calendriers" in CT.rapport(res5q, "x"))


print("\n── 5 bis. le noyau commun, seul ───────────────────────────────")

lignes_test = {
    "a": [{"day": "j1", "unit": "u1"}, {"day": "j1", "unit": "u2"},
          {"day": "j2", "unit": "u1"}],
    "b": [{"day": "j1", "unit": "u1"}, {"day": "j2", "unit": "u1"}],
    "c": [{"day": "j1", "unit": "u1"}],
}
check("le noyau de deux modèles est leur intersection",
      CT.noyau_commun(lignes_test, ["a", "b"])
      == {("j1", "u1"), ("j2", "u1")})
check("un troisième modèle plus pauvre RÉTRÉCIT le noyau pour tous",
      CT.noyau_commun(lignes_test, ["a", "b", "c"]) == {("j1", "u1")})
check("un modèle absent vide le noyau, il ne l'ignore pas",
      CT.noyau_commun(lignes_test, ["a", "inconnu"]) == set())
check("un noyau sans modèle est vide, pas 'tout'",
      CT.noyau_commun(lignes_test, []) == set())

print("\n── 6. doublons : de chaîne (écartés) et de réseau (retirés) ───")

dup_chaine = [
    ligne("2026-08-25", "mf", "s1", "alpha", 3.0, src="own_archive"),
    ligne("2026-08-25", "mf", "s1", "alpha", 9.9, src="autre_chaine"),
    ligne("2026-08-25", "mf", "s2", "alpha", 3.5),
]
lm, bilan = CT.lignes_par_modele(dup_chaine, "mf")
check("deux `fcst_src` pour une balise-jour : la balise-jour ENTIÈRE sort",
      [r["unit"] for r in lm["alpha"]] == ["mf:s2"], f"{lm}")
check("… et le retrait est COMPTÉ, pas silencieux",
      bilan["doublons_ecartes"] == 1, f"{bilan}")

dup_reseau = [
    ligne("2026-08-25", "windsmobi", "w1", "alpha", 3.0),
    ligne("2026-08-25", "windsmobi", "w2", "alpha", 3.5),
]
lm2, bilan2 = CT.lignes_par_modele(dup_reseau, "windsmobi",
                                   doublons=frozenset({"windsmobi:w1"}))
check("une balise marquée `doublon_de` est RETIRÉE de la population",
      [r["unit"] for r in lm2["alpha"]] == ["windsmobi:w2"], f"{lm2}")
check("… et comptée à part du doublon de chaîne (deux fautes, deux compteurs)",
      bilan2["doublons_reseau"] == 1 and bilan2["doublons_ecartes"] == 0,
      f"{bilan2}")

res6 = CT.controle_tau(ref_rows + accord,
                       doublons=frozenset({f"windsmobi:wi{b}" for b in range(4)}))
p6 = [p for p in res6["populations"] if p["source"] == "windsmobi"][0]
check("la déduplication descend jusqu'au rapport de population",
      p6["doublons_reseau_retires"] > 0, f"{p6['doublons_reseau_retires']}")
check("… et retire des BALISES, pas seulement des lignes",
      p6["n_balises"] < par_src["windsmobi"]["n_balises"],
      f"{p6['n_balises']} vs {par_src['windsmobi']['n_balises']}")

print("\n── 6 bis. quorum, ordre déterministe, filtre d'échéance ───────")

petit = {"a": [{"day": "j", "unit": f"u{i}", "err_vec_med": 1.0}
               for i in range(CT.TAU_MIN_OCCURRENCES - 1)],
         "b": [{"day": "j", "unit": f"u{i}", "err_vec_med": 2.0}
               for i in range(CT.TAU_MIN_OCCURRENCES)]}
c = CT.classement(petit, ["a", "b"])
check("un modèle sous quorum est EXCLU du classement",
      list(c["rangs"]) == ["b"], f"{c['rangs']}")
check("… et il est nommé dans `exclus` avec son n et sa raison",
      c["exclus"] == [{"model": "a", "n": CT.TAU_MIN_OCCURRENCES - 1,
                       "raison": "sous_quorum"}], f"{c['exclus']}")
check("le quorum est CELUI du classement publié, pas un second",
      CT.TAU_MIN_OCCURRENCES == S.REGIME_MIN_OCCURRENCES)

exaequo = {m: [{"day": "j", "unit": f"u{i}", "err_vec_med": 3.0}
               for i in range(10)] for m in ("zeta", "alpha", "mu")}
check("deux médianes égales se départagent par le NOM (ordre reproductible)",
      CT.classement(exaequo, ["zeta", "alpha", "mu"])["rangs"]
      == {"alpha": 1, "mu": 2, "zeta": 3})

autre_lead = [ligne("2026-08-25", "mf", f"s{i}", "alpha", 3.0, lead=24)
              for i in range(10)]
lm3, _ = CT.lignes_par_modele(autre_lead, "mf")
check("une autre échéance ne rentre pas dans le contrôle",
      lm3 == {}, f"{lm3}")
non_finie = [ligne("2026-08-25", "mf", f"s{i}", "alpha", None)
             for i in range(10)]
lm4, _ = CT.lignes_par_modele(non_finie, "mf")
check("une valeur non finie ne rentre pas non plus",
      lm4 == {}, f"{lm4}")

print("\n── 6 ter. reranger : la valeur ne bouge pas, l'affichage oui ──")

rangs = {"a": 1, "b": 4, "c": 7, "d": 9}
sous = ["a", "c", "d"]
check("le rerangement renumérote 1..k en gardant l'ordre",
      CT.reranger(rangs, sous) == {"a": 1, "c": 2, "d": 3})
check("… et il ne CHANGE PAS le tau (invariance monotone), c'est le point",
      INF.kendall_tau_b(CT.reranger(rangs, sous),
                        CT.reranger({"a": 2, "c": 1, "d": 3}, sous))
      == INF.kendall_tau_b({k: rangs[k] for k in sous},
                           {"a": 2, "c": 1, "d": 3}))
check("un modèle absent des rangs ne se voit pas inventer une place",
      CT.reranger(rangs, ["a", "inconnu"]) == {"a": 1})

print("\n── 7. la réserve `run_init` — les quatre verdicts ─────────────")


def faux_lire(objets):
    """Un lecteur d'archive de banc : `objets` est {clé: [lignes]}.

    ⚠️ Une clé ABSENTE du dictionnaire rend `present=False` — c'est ce
    qui permet de tester la distinction « objet absent » / « objet
    présent sans run_init », que le contrôle ne doit pas confondre.
    """
    def lire(root, key, storage=None):
        if key not in objets:
            return {"objet": key, "present": False, "n_lignes": 0,
                    "par_modele": {}}
        par = {}
        n = 0
        for r in objets[key]:
            n += 1
            d = par.setdefault(r["model"], {"runs": set(), "sans_run": 0})
            if r.get("run_init"):
                d["runs"].add(r["run_init"])
            else:
                d["sans_run"] += 1
        return {"objet": key, "present": True, "n_lignes": n,
                "par_modele": {m: {"runs": sorted(v["runs"]),
                                   "sans_run": v["sans_run"]}
                               for m, v in par.items()}}
    return lire


J = ["2026-08-25"]
K_FCST = SC.fcst_key(__import__("datetime").datetime(2026, 8, 25))
K_RED = SC.fcst_reduit_key(__import__("datetime").datetime(2026, 8, 25))
K_ARO = SC.fcst_arome_key(__import__("datetime").datetime(2026, 8, 25))

# (a) les deux côtés portent le MÊME run
memes = faux_lire({
    K_FCST: [{"model": "icon_eu", "run_init": "2026-08-25T00:00"}],
    K_RED: [{"model": "icon_eu", "run_init": "2026-08-25T00:00"}]})
v = CT.verifier_run_init(pathlib.Path("."), J, ["icon_eu"], lire=memes)
check("mêmes runs des deux côtés → `runs_identiques`",
      v["par_modele"]["icon_eu"]["verdict"] == "runs_identiques", f"{v}")
check("… et la réserve est LEVÉE",
      v["levee"] is True and "verifie" in v["reserve"], f"{v['reserve']}")

# (b) les deux côtés portent des runs DIFFÉRENTS (le cas icon_d2 du S0.10)
autres = faux_lire({
    K_FCST: [{"model": "icon_d2", "run_init": "2026-08-25T00:00"}],
    K_RED: [{"model": "icon_d2", "run_init": "2026-08-25T03:00"}]})
v = CT.verifier_run_init(pathlib.Path("."), J, ["icon_d2"], lire=autres)
check("runs différents → `runs_differents`",
      v["par_modele"]["icon_d2"]["verdict"] == "runs_differents", f"{v}")
check("… la réserve n'est PAS levée",
      v["levee"] is False)
check("… et elle NOMME le modèle en cause dans la phrase publiée",
      "icon_d2" in v["reserve"], f"{v['reserve']}")

# (c) un côté n'écrit pas run_init — LE CAS RÉEL de `collect.py`
muet = faux_lire({
    K_FCST: [{"model": "icon_eu"}, {"model": "icon_eu"}],
    K_RED: [{"model": "icon_eu", "run_init": "2026-08-25T03:00"}]})
v = CT.verifier_run_init(pathlib.Path("."), J, ["icon_eu"], lire=muet)
check("un côté sans `run_init` → `non_verifiable`, PAS `runs_identiques`",
      v["par_modele"]["icon_eu"]["verdict"] == "non_verifiable", f"{v}")
check("… la réserve n'est pas levée",
      v["levee"] is False)
check("… et le compteur `sans_run` dit COMBIEN de lignes se taisent",
      v["par_modele"]["icon_eu"]["reference"]["sans_run"] == 2, f"{v}")
check("… l'objet est bien noté PRÉSENT (on a regardé, la donnée n'y est pas)",
      v["objets"]["fcst"][0]["present"] is True, f"{v['objets']}")

# (d) objet ABSENT — distinct du précédent
rien = faux_lire({K_RED: [{"model": "icon_eu", "run_init": "x"}]})
v = CT.verifier_run_init(pathlib.Path("."), J, ["icon_eu"], lire=rien)
check("objet absent : `present` faux (≠ présent et muet)",
      v["objets"]["fcst"][0]["present"] is False, f"{v['objets']}")
check("… et le verdict reste `non_verifiable`, sans invention",
      v["par_modele"]["icon_eu"]["verdict"] == "non_verifiable")

# (e) ⭐ arome_r2 : une seule archive pour les deux populations
v = CT.verifier_run_init(pathlib.Path("."), J, ["arome_r2"],
                         lire=faux_lire({K_ARO: [{"model": "arome_r2"}]}))
check("`arome_r2` → `archive_unique` : il n'y a pas deux runs à comparer",
      v["par_modele"]["arome_r2"]["verdict"] == "archive_unique", f"{v}")
check("… la réserve est levée SANS qu'aucun `run_init` ait été écrit",
      v["levee"] is True, f"{v}")
check("… et le verdict porte sa PREUVE, pas seulement son nom",
      "referentiels" in v["par_modele"]["arome_r2"]["preuve"],
      f"{v['par_modele']['arome_r2']}")

# (f) un mélange : le pire l'emporte, et les deux sont nommés
v = CT.verifier_run_init(pathlib.Path("."), J,
                         ["arome_r2", "icon_d2", "icon_eu"],
                         lire=faux_lire({
                             K_ARO: [{"model": "arome_r2"}],
                             K_FCST: [{"model": "icon_d2",
                                       "run_init": "2026-08-25T00:00"},
                                      {"model": "icon_eu"}],
                             K_RED: [{"model": "icon_d2",
                                      "run_init": "2026-08-25T03:00"},
                                     {"model": "icon_eu",
                                      "run_init": "2026-08-25T03:00"}]}))
check("un mélange laisse la réserve NON levée",
      v["levee"] is False)
check("… l'écart de run l'emporte dans la phrase",
      "ECART DE RUN" in v["reserve"], f"{v['reserve']}")
check("… mais le non-vérifiable y figure aussi",
      "icon_eu" in v["reserve"], f"{v['reserve']}")
check("… et `arome_r2` n'apparaît dans NI l'une NI l'autre liste",
      "arome_r2" not in v["modeles_differents"]
      and "arome_r2" not in v["modeles_inconnus"], f"{v}")

print("\n── 7 bis. aucun tau ne sort sans sa réserve ───────────────────")

res7 = CT.controle_tau(ref_rows + accord)          # run_init non fourni
check("sans réserve fournie, le contrôle en pose une NON levée",
      res7["run_init"]["levee"] is False
      and "NON LU" in res7["run_init"]["reserve"],
      f"{res7['run_init']}")
check("… et elle est recopiée sur CHAQUE ligne de population",
      all(p["reserve_run_init"] and p["reserve_levee"] is False
          for p in res7["populations"]))
res7b = CT.controle_tau(ref_rows + accord,
                        run_init={"levee": True, "reserve": "ok mesuré",
                                  "par_modele": {}, "modeles_differents": [],
                                  "modeles_inconnus": []})
check("une réserve levée voyage elle aussi jusqu'aux lignes",
      all(p["reserve_levee"] is True and p["reserve_run_init"] == "ok mesuré"
          for p in res7b["populations"]))

print("\n── 8. la lecture d'archive lit comme `score.read_ndjson` ──────")

with tempfile.TemporaryDirectory() as tmp:
    root = pathlib.Path(tmp)
    cle = "fcstreduit/2026/08/fcstreduit_2026-08-25.ndjson.gz"
    (root / cle).parent.mkdir(parents=True, exist_ok=True)
    lignes_src = [{"model": "icon_d2", "run_init": "2026-08-25T03:00"},
                  {"model": "icon_d2", "run_init": "2026-08-25T03:00"},
                  {"model": "icon_eu"}]
    corps = "\n".join(json.dumps(x) for x in lignes_src).encode("utf-8")
    (root / cle).write_bytes(gzip.compress(corps))
    par_score = SC.read_ndjson(root, cle)
    octets, erreur = CT._octets(root, cle)
    par_ici = list(CT._lignes(octets))
    check("test_octets_lit_comme_read_ndjson : mêmes lignes, même ordre",
          par_ici == par_score, f"{par_ici} vs {par_score}")
    check("… et une lecture locale réussie ne porte aucune erreur",
          erreur is None, f"{erreur}")

    class R2QuiTombe:
        """Un seau qui refuse — le cas VÉCU le 28/08 sur le VPS
        (`HTTP 400` sur les journées d'avant la naissance du flux)."""

        def get(self, key):
            raise RuntimeError("HTTP Error 400: Bad Request")

    manquant = "fcstreduit/2026/08/fcstreduit_2026-08-13.ndjson.gz"
    o2, err2 = CT._octets(root, manquant, R2QuiTombe())
    check("⭐ un seau qui refuse ne fait PAS tomber la lecture",
          o2 is None and err2 is not None and "400" in err2, f"{err2}")
    info_ko = CT.runs_du_flux(root, manquant, R2QuiTombe())
    check("… l'objet est marqué illisible, distinct d'absent et de muet",
          info_ko["present"] is False and info_ko["erreur"] is not None,
          f"{info_ko}")
    v_ko = CT.verifier_run_init(
        root, ["2026-08-13", "2026-08-25"], ["icon_eu"],
        storage=R2QuiTombe())
    check("… la vérification CONTINUE et rend une réserve",
          v_ko["levee"] is False and v_ko["lectures_echouees"], f"{v_ko}")
    check("… et la phrase publiée compte les objets illisibles",
          "ILLISIBLE" in v_ko["reserve"], f"{v_ko['reserve']}")
    info = CT.runs_du_flux(root, cle)
    check("les runs distincts sont dédoublonnés",
          info["par_modele"]["icon_d2"]["runs"] == ["2026-08-25T03:00"],
          f"{info}")
    check("… les lignes muettes sont comptées à part",
          info["par_modele"]["icon_eu"]["sans_run"] == 1, f"{info}")
    check("… et le nombre de lignes lues est rendu",
          info["n_lignes"] == 3 and info["present"] is True, f"{info}")
    absent = CT.runs_du_flux(root, "fcst/2026/08/fcst_2026-08-25.ndjson.gz")
    check("un objet absent rend `present` faux et zéro ligne",
          absent["present"] is False and absent["n_lignes"] == 0)

print("\n── 8 bis. la MARCHE DU HAUT : le test apparié, vraiment joué ──")

# ⚠️ Scène écrite APRÈS coup : la mutation « la marche du haut n'est
# plus calculée » restait VERTE, parce que le banc ne comptait que des
# occurrences du MOT dans le rapport — et `_dire_marche(None)` imprime
# ce mot lui aussi. Un banc qui compte un vocabulaire qu'on contrôle ne
# teste rien (piège nº 9 du 26/08, clôture). Il fallait vérifier le
# CONTENU du verdict, et sur une fenêtre assez longue pour que
# `block_bootstrap_ci` accepte de la borner (MIN_DAYS_BLOCK = 8 jours).
def scene_longue(ecart, jours=12, seed=555):
    g = LCG(seed)
    rows = []
    for j in range(jours):
        jour = f"2026-08-{j + 1:02d}"
        for b in range(14 - (j % 4)):
            base = 4.0 + 0.6 * (g.u() - 0.5)
            rows.append({"day": jour, "unit": f"u{b}",
                         "err_vec_med": round(base - ecart, 4),
                         "model": "bon"})
            rows.append({"day": jour, "unit": f"u{b}",
                         "err_vec_med": round(base, 4), "model": "moins_bon"})
    par = {"bon": [r for r in rows if r["model"] == "bon"],
           "moins_bon": [r for r in rows if r["model"] == "moins_bon"]}
    return par


c_franc = CT.classement(scene_longue(1.2), ["bon", "moins_bon"])
m = c_franc["marche"]
check("la marche nomme le 1ᵉʳ et le 2ᵉ du classement, pas deux modèles au hasard",
      m["premier"] == "bon" and m["second"] == "moins_bon", f"{m}")
check("sur 12 jours et un écart franc, le test apparié CONCLUT",
      m["reason"] == "ok" and m["winner"] == "bon", f"{m}")
check("… l'IC exclut zéro et il est du bon côté (le 1ᵉʳ se trompe moins)",
      m["ci_high"] is not None and m["ci_high"] < 0, f"{m}")
check("… le n apparié est celui des balise-jours communs, pas la somme",
      m["n_comparable"] == len(scene_longue(1.2)["bon"]), f"{m}")
check("… et l'écart relatif est publié à côté de l'intervalle",
      m["relative_gap"] is not None and m["relative_gap"] > 0.15, f"{m}")
check("… le signe de la marche voyage avec elle",
      "negatif = premier meilleur" in m["sign"], f"{m['sign']}")

c_nul = CT.classement(scene_longue(0.0, seed=777), ["bon", "moins_bon"])
check("⭐ à effet NUL, la marche NE conclut pas (sinon le contrôle "
      "trouverait un gagnant partout)",
      c_nul["marche"]["winner"] is None
      and c_nul["marche"]["reason"] in ("not_separable", "tied"),
      f"{c_nul['marche']}")

c_court = CT.classement(scene_longue(1.2, jours=3), ["bon", "moins_bon"])
check("sur trois journées, la marche refuse de trancher et le DIT",
      c_court["marche"]["reason"] == "window_too_short"
      and c_court["marche"]["ci_low"] is None, f"{c_court['marche']}")
check("… c'est le cas RÉEL des réseaux candidats au 27/08 (3 jours)",
      INF.MIN_DAYS_BLOCK == 8)

autre_col = {m_: [{"day": f"j{i}", "unit": "u", "autre_col": v}
                  for i in range(10)]
             for m_, v in (("x", 5.0), ("y", 2.0))}
check("la grandeur classée est un PARAMÈTRE, pas une colonne en dur",
      list(CT.classement(autre_col, ["x", "y"],
                         value_key="autre_col")["rangs"]) == ["y", "x"])

print("\n── 8 ter. les run_init, lisibles sans calculette ──────────────")

check("un run_init epoch se rend en UTC lisible",
      CT._runs_lisibles([1787529600]) == "2026-08-24T00:00Z",
      CT._runs_lisibles([1787529600]))
check("… et l'ecart de 3 h d'icon_d2 se VOIT",
      CT._runs_lisibles([1787540400]) == "2026-08-24T03:00Z",
      CT._runs_lisibles([1787540400]))
check("une liste vide dit qu'aucun run_init n'est ecrit",
      CT._runs_lisibles([]) == "(aucun run_init ecrit)")
check("une valeur qui n'est pas un epoch est rendue telle quelle, "
      "pas devinee",
      CT._runs_lisibles(["2026-08-24T00:00Z"]) == "2026-08-24T00:00Z")


print("\n── 9. le rapport : ce qu'un humain lit ────────────────────────")

texte = CT.rapport(res5, "2026-08-28 06:00:00Z")
check("le rapport porte la date de génération",
      "2026-08-28 06:00:00Z" in texte)
check("le rapport porte la fenêtre RÉELLEMENT trouvée",
      "2026-08-22 → 2026-08-26" in texte, texte[:400])
check("le rapport porte les DEUX classements (noyau ET brut)",
      "SUR LE NOYAU COMMUN" in texte and "BRUT" in texte)
check("⭐ la réserve est écrite sous CHAQUE population, pas une fois en tête",
      texte.count("reserve :") == len(res5["populations"]),
      f"{texte.count('reserve :')} vs {len(res5['populations'])}")
check("la marche du haut est imprimée sous chaque classement",
      texte.count("marche du haut") >= 4)
check("le rapport nomme la grandeur classée (sinon le lecteur devine)",
      "err_vec_med" in texte)
check("le rapport dit si la réserve est levée, en toutes lettres",
      "levee : NON" in texte, texte[:600])

print("\n── 10. `main()` : l'objet ÉCRIT, pas seulement calculé ───────")

# ⚠️ Aucune des 105 assertions précédentes ne touche `main()`, et c'est
# exactement là que vivent les fautes qu'un banc ne voit pas : le sens
# de `--out`, l'écriture du rapport, le chemin par défaut. « Vérifier le
# producteur ne vérifie pas le publié » (BUGS.md 26/08, piège nº 7) —
# ici le publié est un FICHIER, et le seul contrôle qui vaille est de le
# relire.
#
# ⓘ `--out` a d'ailleurs changé de sens en écrivant le mode `run.sh
# tau` : il désignait un fichier de rapport, il désigne maintenant la
# racine de l'état, comme pour TOUS les autres jobs du dépôt. Sans quoi
# l'orchestrateur aurait eu besoin d'une exception pour ce mode-là.

import unittest.mock as _mock  # noqa: E402


class _FausseBase:
    def select(self, table, query="", order=None):
        if table == "station_zone":
            return [{"source": "windsmobi", "station_id": "wi0",
                     "doublon_de": "pioupiou:pp0"}]
        return ref_rows + accord


with tempfile.TemporaryDirectory() as tmp, \
        _mock.patch.object(SC, "Supabase", lambda *a, **k: _FausseBase()), \
        _mock.patch.object(sys, "argv",
                           ["controle_tau.py", "--out", tmp,
                            "--day", "2026-08-26", "--sans-archive"]):
    rc = CT.main()
    ecrits = sorted(pathlib.Path(tmp).glob("controle-tau-*.txt"))
    check("main() sort en 0", rc == 0, f"{rc}")
    check("⭐ le rapport est écrit PAR DÉFAUT, sans drapeau",
          len(ecrits) == 1, f"{[p.name for p in ecrits]}")
    check("… sous le jour demandé, pas sous la date du jour",
          ecrits and ecrits[0].name == "controle-tau-2026-08-26.txt",
          f"{[p.name for p in ecrits]}")
    corps = ecrits[0].read_text(encoding="utf-8") if ecrits else ""
    check("… et il porte bien un tau, pas un fichier vide",
          "tau-b vs pioupiou" in corps, corps[:200])
    check("… avec sa réserve, comme toute ligne publiée",
          "reserve" in corps)
    check("⭐ `--out` est bien la RACINE (le dossier existe, il n'a pas "
          "été écrasé par un fichier)",
          pathlib.Path(tmp).is_dir())

with tempfile.TemporaryDirectory() as tmp, \
        _mock.patch.object(SC, "Supabase", lambda *a, **k: _FausseBase()), \
        _mock.patch.object(sys, "argv",
                           ["controle_tau.py", "--out", tmp,
                            "--day", "2026-08-26", "--sans-archive",
                            "--rapport", "-"]):
    CT.main()
    check("`--rapport -` n'écrit rien (sonde ponctuelle, stdout seul)",
          not list(pathlib.Path(tmp).glob("*.txt")))

# ══════════════════════════════════════════════════════════════════
print(f"\n{'✅' if KO == 0 else '❌'} {OK} assertions vertes, {KO} rouges.\n")
sys.exit(1 if KO else 0)
