#!/usr/bin/env python3
"""test_fraicheur.py — banc de la SONDE DE FRAÎCHEUR DE RUN
                       (lot L8, 28/08/2026).

Ce que ce banc tient, et pourquoi chaque propriété vaut son assertion :

  1. ⭐ **La carte couvre `collect.MODELS` EXACTEMENT.** C'est
     l'invariant qui décide de tout : un modèle collecté et absent de la
     carte partirait sans `run_init` en silence, et le contrôle n°3
     dirait `non_verifiable` trois semaines plus tard sans que personne
     ne sache pourquoi. Un modèle en trop ferait payer un appel pour
     rien.
  2. **Un modèle inconnu LÈVE, il ne se saute pas.** L'échec au
     déploiement est le seul moyen que l'oubli se sache le jour même.
  3. **Un témoin n'atterrit JAMAIS sur une ligne.** Sonder un domaine
     qu'on ne collecte pas est légitime ; coller son run sur les lignes
     d'un modèle qu'on sert le serait beaucoup moins.
  4. **Un échec ne tue pas la passe** — ni un refus de budget, ni un
     `meta.json` illisible, ni une exception. Une colonne d'information
     ne doit jamais coûter une nuit d'archive, et celle-ci ne se
     rattrape pas (Open-Meteo ne garde aucun historique de runs).
  5. **Un champ ABSENT, jamais un `null`.** « la sonde n'a pas eu ce
     domaine » est une information ; `null` se confondrait avec une
     valeur.
  6. **Le déménagement est invisible depuis `collect_reduit`** : même
     signature, même forme de journal, même carte restreinte aux cinq.

Aucun réseau : `get_json` est injecté, le budget est un double.

Usage :
    python3 test_fraicheur.py
"""
from __future__ import annotations

import pathlib
import sys

import collect as C
import collect_reduit as CR
import fraicheur as FR

OK = 0
KO = 0


def check(label: str, cond: bool, detail: str = ""):
    global OK, KO
    if cond:
        OK += 1
    else:
        KO += 1
        print(f"  ❌ {label}" + (f"\n       {detail}" if detail else ""))


class BudgetRefuse(Exception):
    pass


class FauxBudget:
    """Un seau de banc. `refuse` : les étiquettes à rejeter."""

    def __init__(self, refuse=()):
        self.demandes = []
        self.refuse = tuple(refuse)

    def demander(self, poids, etiquette=""):
        self.demandes.append((poids, etiquette))
        if any(r in etiquette for r in self.refuse):
            raise BudgetRefuse(f"refusé : {etiquette}")


def faux_meta(par_domaine, echouent=(), leve=(), muets=()):
    """Un `_get_json_retry` de banc, sans une seule requête.

    ⚠️ TROIS FAÇONS D'ÉCHOUER, PAS UNE — et la troisième a été ajoutée
    après coup, parce qu'une mutation restait VERTE sans elle :
      · `leve`     : le réseau tombe (exception) ;
      · `echouent` : la réponse n'est pas un objet (`None`) ;
      · `muets`    : la réponse EST un objet, bien formé, mais sans
        `last_run_initialisation_time`.
    Le banc ne connaissait que les deux premières, donc « accepter un
    `meta.json` muet » ne changeait rien : les deux scènes existantes
    échouaient déjà sur le `isinstance`. C'est le piège nº 2 de la
    phase B (26/08) — le jeu d'essai doit être irrégulier DANS LA
    DIMENSION testée, et cette dimension-ci est la FORME de la réponse.
    """
    vus = []

    def get_json(url, label, **kw):
        vus.append(url)
        dom = url.split("/data/")[1].split("/")[0]
        if dom in leve:
            raise RuntimeError(f"réseau mort sur {dom}")
        if dom in muets:
            return {"temporal_resolution_seconds": 3600}
        if dom in echouent:
            return None
        return {"last_run_initialisation_time": par_domaine[dom][0],
                "last_run_availability_time": par_domaine[dom][1]}
    get_json.vus = vus
    return get_json


META = {d: (1787529600, 1787533200) for d in FR.DOMAINE_PAR_MODELE.values()}
META["dwd_icon_d2"] = (1787540400, 1787544000)      # le run 03 Z du S0.10


print("\n── 1. ⭐ la carte couvre collect.MODELS, exactement ───────────")

check("aucun modèle collecté n'est absent de la carte",
      set(C.MODELS) - set(FR.DOMAINE_PAR_MODELE) == set(),
      f"{set(C.MODELS) - set(FR.DOMAINE_PAR_MODELE)}")
check("aucun domaine de la carte n'est payé pour rien",
      set(FR.DOMAINE_PAR_MODELE) - set(C.MODELS) == set(),
      f"{set(FR.DOMAINE_PAR_MODELE) - set(C.MODELS)}")
check("les cinq du groupe réduit sont DANS la carte canonique",
      set(CR.MODELS_REDUIT) <= set(FR.DOMAINE_PAR_MODELE))
check("la vue de collect_reduit est exactement ses cinq modèles",
      set(CR.DOMAINE_PAR_MODELE) == set(CR.MODELS_REDUIT),
      f"{sorted(CR.DOMAINE_PAR_MODELE)}")
check("… et elle est DÉRIVÉE : mêmes domaines que la carte canonique",
      all(CR.DOMAINE_PAR_MODELE[m] == FR.DOMAINE_PAR_MODELE[m]
          for m in CR.MODELS_REDUIT))
check("⭐ `gfs_global` n'est PAS servi par un domaine du même nom "
      "(la faute qui écrirait le run d'un autre modèle)",
      FR.DOMAINE_PAR_MODELE["gfs_global"] == "ncep_gfs013",
      FR.DOMAINE_PAR_MODELE["gfs_global"])
check("les témoins de collect_reduit sont les modèles que SEULE la "
      "passe Pioupiou collecte",
      set(CR.DOMAINES_TEMOINS) == set(C.MODELS) - set(CR.MODELS_REDUIT),
      f"{set(CR.DOMAINES_TEMOINS) ^ (set(C.MODELS) - set(CR.MODELS_REDUIT))}")

print("\n── 2. un modèle inconnu LÈVE, il ne se saute pas ──────────────")

try:
    FR.domaine_de("modele_qui_nexiste_pas")
    check("un modèle inconnu lève", False, "rien n'a été levé")
except FR.ModeleInconnu as exc:
    check("un modèle inconnu lève `ModeleInconnu`", True)
    check("… et le message dit OÙ l'ajouter",
          "DOMAINE_PAR_MODELE" in str(exc), str(exc))
try:
    FR.sonde_fraicheur(None, ["inconnu"], get_json=faux_meta(META))
    check("la sonde refuse un modèle inconnu AVANT le premier appel",
          False, "elle a continué")
except FR.ModeleInconnu:
    check("la sonde refuse un modèle inconnu AVANT le premier appel", True)

print("\n── 3. le relevé nominal ───────────────────────────────────────")

b = FauxBudget()
g = faux_meta(META)
par_modele, jrn = FR.sonde_fraicheur(b, C.MODELS, get_json=g)
check("les neuf modèles sont rendus",
      set(par_modele) == set(C.MODELS), f"{sorted(par_modele)}")
check("neuf appels, neuf réservations",
      jrn["appels"] == 9 and len(b.demandes) == 9, f"{jrn}")
check("le poids réservé est celui qui est déclaré",
      jrn["poids_reserve"] == 9 * FR.POIDS_SONDE, f"{jrn['poids_reserve']}")
check("chaque réservation porte le POIDS de la sonde, pas un autre",
      all(p == FR.POIDS_SONDE for p, _ in b.demandes), f"{b.demandes}")
check("l'URL interrogée est bien celle du domaine, pas du modèle",
      any("ncep_gfs013" in u for u in g.vus)
      and not any("/gfs_global/" in u for u in g.vus), f"{g.vus}")
check("⭐ l'écart mesuré au S0.10 se lit dans le relevé "
      "(icon_d2 3 h plus frais)",
      par_modele["icon_d2"]["init"] - par_modele["icon_eu"]["init"] == 10800,
      f"{par_modele['icon_d2']} vs {par_modele['icon_eu']}")
check("le domaine voyage avec le run (on peut refaire l'appel)",
      par_modele["gfs_global"]["domaine"] == "ncep_gfs013")

print("\n── 4. les témoins ne touchent JAMAIS une ligne ────────────────")

par_modele, jrn = FR.sonde_fraicheur(
    None, CR.MODELS_REDUIT, get_json=faux_meta(META),
    temoins=CR.DOMAINES_TEMOINS)
check("les cinq modèles sont dans `par_modele`",
      set(par_modele) == set(CR.MODELS_REDUIT), f"{sorted(par_modele)}")
check("⭐ les quatre témoins n'y sont PAS",
      not (set(par_modele) & set(CR.DOMAINES_TEMOINS)), f"{sorted(par_modele)}")
check("… ils sont dans le journal, à part",
      set(jrn["temoins"]) == set(CR.DOMAINES_TEMOINS), f"{sorted(jrn['temoins'])}")
check("sans témoins, on ne paie que les modèles servis",
      FR.sonde_fraicheur(None, CR.MODELS_REDUIT,
                         get_json=faux_meta(META))[1]["appels"] == 5)

print("\n── 5. un échec ne tue pas la passe ────────────────────────────")

b = FauxBudget(refuse=("dwd_icon_d2",))
par_modele, jrn = FR.sonde_fraicheur(
    b, C.MODELS, get_json=faux_meta(META), crier=lambda *a, **k: None)
check("un refus de budget écarte CE domaine et pas les autres",
      "icon_d2" not in par_modele and len(par_modele) == 8, f"{sorted(par_modele)}")
check("… le refus est COMPTÉ, pas silencieux",
      len(jrn["refuses"]) == 1 and "dwd_icon_d2" in jrn["refuses"][0], f"{jrn}")
check("… et son poids n'est pas compté comme réservé",
      jrn["poids_reserve"] == 8 * FR.POIDS_SONDE, f"{jrn['poids_reserve']}")

par_modele, jrn = FR.sonde_fraicheur(
    None, C.MODELS, get_json=faux_meta(META, echouent=("ecmwf_ifs025",)),
    crier=lambda *a, **k: None)
check("un `meta.json` illisible écarte ce modèle et pas les autres",
      "ecmwf_ifs025" not in par_modele and len(par_modele) == 8)
check("… l'échec est nommé dans le journal",
      jrn["echecs"] == ["ecmwf_ifs025"], f"{jrn['echecs']}")
check("… et `appels` compte l'appel FAIT, `ok` le seul rendu",
      jrn["appels"] == 9 and jrn["ok"] == 8, f"{jrn}")

par_modele, jrn = FR.sonde_fraicheur(
    None, C.MODELS, get_json=faux_meta(META, muets=("dwd_icon_d2",)),
    crier=lambda *a, **k: None)
check("⭐ un `meta.json` BIEN FORMÉ mais sans run est un ÉCHEC, pas une "
      "valeur : sans ça l'archive recevrait `run_init = None`",
      "icon_d2" not in par_modele and jrn["echecs"] == ["dwd_icon_d2"],
      f"{par_modele.get('icon_d2')} · {jrn['echecs']}")
check("… et les huit autres passent quand même",
      len(par_modele) == 8, f"{sorted(par_modele)}")

leve = faux_meta(META, leve=("dwd_icon_eu",))
try:
    FR.sonde_fraicheur(None, C.MODELS, get_json=leve,
                       crier=lambda *a, **k: None)
    check("une exception réseau remonte à l'appelant (qui la journalise "
          "et continue — cf. le `try` de collect.py)", False, "rien levé")
except RuntimeError:
    check("une exception réseau remonte à l'appelant (qui la journalise "
          "et continue — cf. le `try` de collect.py)", True)

vu = []
FR.sonde_fraicheur(None, C.MODELS,
                   get_json=faux_meta(META, echouent=("dwd_icon_eu",)),
                   crier=lambda m: vu.append(m))
check("la sonde incomplète CRIE (sinon personne ne le saura le soir même)",
      any("INCOMPLÈTE" in m for m in vu), f"{vu}")

print("\n── 6. ce qui est posé sur la ligne, et ce qui ne l'est pas ────")

fr = {"icon_d2": {"init": 111, "avail": 222, "domaine": "dwd_icon_d2"}}
r = FR.poser({"model": "icon_d2", "speed": [1, 2]}, fr)
check("un modèle sondé reçoit ses deux champs",
      r["run_init"] == 111 and r["run_avail"] == 222, f"{r}")
r2 = FR.poser({"model": "icon_eu", "speed": [1, 2]}, fr)
check("⭐ un modèle NON sondé n'a PAS de clé `run_init` — pas un `null`",
      "run_init" not in r2 and "run_avail" not in r2, f"{r2}")
r3 = FR.poser({"model": "icon_d2"}, {})
check("un relevé vide ne pose rien du tout (sonde sautée ou en échec)",
      "run_init" not in r3, f"{r3}")
check("`poser` rend la ligne, pour pouvoir s'écrire dans un `yield`",
      FR.poser({"model": "x"}, {})["model"] == "x")

print("\n── 7. le pavé de journal NOMME les manquants ──────────────────")

lignes = []
FR.dire_sonde({"appels": 9, "ok": 8, "poids_reserve": 9.0, "temoins": {}},
              {m: {"init": 1, "avail": 2} for m in C.MODELS[:-1]},
              C.MODELS, crier=lambda m: lignes.append(m))
texte = "\n".join(lignes)
check("⭐ le modèle non rendu est NOMMÉ, avec sa conséquence",
      C.MODELS[-1] in texte and "non rendu" in texte, texte)
check("… et ceux qui sont rendus portent leur run",
      texte.count("run 1 · publié 2") == len(C.MODELS) - 1, texte)

print("\n── 8. le déménagement est invisible depuis collect_reduit ─────")

import unittest.mock as _mock  # noqa: E402

with _mock.patch.object(CR, "_get_json_retry", faux_meta(META)):
    pm, jr = CR.sonde_fraicheur(None)
check("l'enveloppe rend la même forme qu'avant (par_modele, journal)",
      set(pm) == set(CR.MODELS_REDUIT)
      and set(jr) >= {"appels", "ok", "echecs", "refuses", "temoins",
                      "poids_reserve"}, f"{sorted(jr)}")
check("… avec les témoins par défaut, comme avant",
      set(jr["temoins"]) == set(CR.DOMAINES_TEMOINS), f"{sorted(jr['temoins'])}")
with _mock.patch.object(CR, "_get_json_retry", faux_meta(META)):
    _, jr2 = CR.sonde_fraicheur(None, avec_temoins=False)
check("`avec_temoins=False` retire les quatre appels, comme avant",
      jr2["appels"] == len(CR.MODELS_REDUIT) and not jr2["temoins"],
      f"{jr2}")
check("le budget réservé par ce flux n'a pas changé (5 + 4 = 9)",
      len(CR.DOMAINE_PAR_MODELE) + len(CR.DOMAINES_TEMOINS) == 9)

print("\n── 9. collect.py est CÂBLÉ (pas seulement importable) ─────────")

# ⛔ LE CHEMIN EST RÉSOLU DEPUIS CE FICHIER, PAS DEPUIS LE `cwd`
# (31/08/2026). Les IMPORTS de ce banc marchent partout — Python met le
# dossier du script en tête de `sys.path` — mais cette LECTURE-ci
# dépendait du répertoire courant, et personne ne s'en apercevait tant
# que le banc n'était lancé que depuis `model-verif/`.
# ⚠️ Trouvé le 31/08 en l'ajoutant à la liste du déploiement, qui lance
# les bancs depuis la RACINE du dépôt sur le VPS : vert sur le Mac,
# `FileNotFoundError: collect.py` sur le VPS. Le déploiement s'est
# arrêté et n'a rien redémarré — le garde-fou a fait exactement son
# travail, et il a révélé un banc qui n'était pas portable.
src = (pathlib.Path(__file__).resolve().parent / "collect.py").read_text(
    encoding="utf-8")
check("collect appelle bien la sonde partagée",
      "FR.sonde_fraicheur(" in src)
check("⭐ il la sonde sur `modeles_passe`, pas sur MODELS "
      "(une passe partitionnée ne paie pas les modèles qu'elle ne sert pas)",
      "FR.sonde_fraicheur(\n                    budget, modeles_passe" in src
      or "budget, modeles_passe" in src, "signature attendue absente")
check("il pose les champs sur CHAQUE ligne écrite",
      "yield FR.poser(_row, fraicheur)" in src)
check("il a un `--sans-sonde`, comme collect_reduit",
      '"--sans-sonde"' in src)
check("⛔ il n'a PAS recopié la carte des domaines",
      "ncep_gfs013" not in src, "un domaine en dur dans collect.py")
check("⛔ ni le point d'entrée meta.json",
      "static/meta.json" not in src)

print("\n── 10. ⭐ LA BOUCLE EST FERMÉE : le contrôle n°3 change d'avis ─")

# ⚠️ C'est la seule assertion qui vérifie que ce lot SERT À QUELQUE
# CHOSE. Les neuf sections précédentes prouvent que la sonde relève et
# que collect.py écrit ; celle-ci prouve que le verdict du contrôle n°3
# BASCULE — de « je ne peux pas savoir » à « je sais, et voici quoi ».
# Sans elle, on aurait une colonne de plus et aucune raison de croire
# qu'elle répond à la question qui l'a fait naître.
import gzip as _gz, json as _js, pathlib as _pl, tempfile as _tf  # noqa: E402

import controle_tau as CT  # noqa: E402
import score as SC  # noqa: E402
from datetime import datetime as _dt  # noqa: E402

JOUR = "2026-08-25"
_d = _dt(2026, 8, 25)


def _ecrire(racine, cle, lignes):
    f = _pl.Path(racine) / cle
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(_gz.compress(
        "\n".join(_js.dumps(x) for x in lignes).encode("utf-8")))


with _tf.TemporaryDirectory() as _tmp:
    # côté candidates : run 03 Z (ce que `fcstreduit/` écrit déjà)
    _ecrire(_tmp, SC.fcst_reduit_key(_d),
            [{"model": "icon_d2", "run_init": 1787540400}])
    # côté référence, AVANT ce lot : des lignes, et pas de run_init
    _ecrire(_tmp, SC.fcst_key(_d), [{"model": "icon_d2"}])
    avant = CT.verifier_run_init(_pl.Path(_tmp), [JOUR], ["icon_d2"])
    check("AVANT le lot : le contrôle n°3 rend `non_verifiable`",
          avant["par_modele"]["icon_d2"]["verdict"] == "non_verifiable"
          and avant["levee"] is False, f"{avant['par_modele']}")

with _tf.TemporaryDirectory() as _tmp:
    _ecrire(_tmp, SC.fcst_reduit_key(_d),
            [{"model": "icon_d2", "run_init": 1787540400}])
    # côté référence, APRÈS : la ligne telle que `FR.poser` la produit
    _ecrire(_tmp, SC.fcst_key(_d),
            [FR.poser({"model": "icon_d2"},
                      {"icon_d2": {"init": 1787529600, "avail": 1787533200}})])
    apres = CT.verifier_run_init(_pl.Path(_tmp), [JOUR], ["icon_d2"])
    check("⭐ APRÈS : le contrôle CONSTATE l'écart de run "
          "(`runs_differents`, pas `non_verifiable`)",
          apres["par_modele"]["icon_d2"]["verdict"] == "runs_differents",
          f"{apres['par_modele']}")
    check("… et la réserve NOMME le modèle avantagé d'une échéance",
          "icon_d2" in apres["reserve"] and "ECART DE RUN" in apres["reserve"],
          apres["reserve"])

with _tf.TemporaryDirectory() as _tmp:
    # et le cas où il n'y a rien à signaler : les deux passes au même run
    _ecrire(_tmp, SC.fcst_reduit_key(_d),
            [{"model": "icon_eu", "run_init": 1787529600}])
    _ecrire(_tmp, SC.fcst_key(_d),
            [FR.poser({"model": "icon_eu"},
                      {"icon_eu": {"init": 1787529600, "avail": 1787533200}})])
    egal = CT.verifier_run_init(_pl.Path(_tmp), [JOUR], ["icon_eu"])
    check("⭐ … et quand les deux passes voient le MÊME run, la réserve "
          "du S3 est enfin LEVÉE",
          egal["levee"] is True
          and egal["par_modele"]["icon_eu"]["verdict"] == "runs_identiques",
          f"{egal}")

# ══════════════════════════════════════════════════════════════════
print(f"\n{'✅' if KO == 0 else '❌'} {OK} assertions vertes, {KO} rouges.\n")
sys.exit(1 if KO else 0)
