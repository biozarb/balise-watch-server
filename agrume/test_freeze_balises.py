#!/usr/bin/env python3
"""
test_freeze_balises.py — banc de l'axe des balises, HORS-LIGNE.

    python3 agrume/test_freeze_balises.py

⚠️⚠️ CE BANC EXISTE À CAUSE D'UNE PANNE DE PRODUCTION, LE 12/08/2026.

Le manifeste de l'axe est passé de `domaine` (un domaine) à `domaines`
(deux) avec l'entrée des Pyrénées. `charger_artefact()` a été rendu
tolérant aux deux formes — soigneusement, avec un commentaire de sept
lignes expliquant pourquoi. Et `main(--verifier)`, dix lignes plus bas,
est resté au singulier :

    KeyError: 'domaine'

sur un artefact parfaitement valide, dans une vérification qui ne
vérifiait plus rien puisqu'elle levait avant d'avoir vérifié quoi que ce
soit.

⛔ CE QUI L'A LAISSÉ PASSER N'EST PAS L'INATTENTION. `--verifier` ne
tourne que dans le workflow d'ingestion ; le workflow n'a pas été
relancé entre le renommage et le soir. Il n'existait AUCUN banc sur ce
fichier — ni sur le gel, ni sur la relecture, ni sur la vérification.
Le README dit « un banc qu'on ne lance jamais cesse de protéger » ;
celui-ci n'existait même pas.

Cinq façons de casser en silence, une par section :

  1. **Une clé de manifeste renommée à moitié.** Le défaut ci-dessus.
  2. **Un artefact d'une AUTRE époque refusé.** Entre le déploiement du
     code et le regel, l'ancienne forme circule : la refuser ferait
     échouer tous les runs de l'intervalle, y compris pour les domaines
     qui n'ont rien demandé.
  3. **Un axe figé sur des bornes qui ne sont plus celles du code.** Ça,
     il FAUT le refuser : l'archive est disposée par indice de balise.
  4. **Un total qui ne dit rien.** 203 balises ne dit pas si les
     Pyrénées sont dedans. Le compte par domaine, si.
  5. **Une balise perdue.** L'axe est en AJOUT SEUL : une balise hors
     ligne ne doit jamais disparaître, sinon l'archive se décale.

Aucun réseau, aucune clé — l'artefact commité suffit.
"""
from __future__ import annotations

import io
import json
import os
import sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

import freeze_balises as F  # noqa: E402
from domaine import DOMAINE, DOMAINES  # noqa: E402

echecs = []


def verifier(nom, condition, detail=""):
    print(f"  {'✓' if condition else '✗'} {nom}"
          + (f"   {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


def main(argv=None):
    print("── 1. `--verifier` sur l'artefact COMMITÉ ──")
    # ⛔ LE CHEMIN EXACT QUI A CASSÉ. On l'exécute, on capture sa sortie,
    # et on exige 0. Un `KeyError` ici referait tomber l'ingestion.
    sortie = io.StringIO()
    try:
        with redirect_stdout(sortie):
            code = F.main(["--verifier"])
        leve = None
    except Exception as e:                                   # noqa: BLE001
        code, leve = 1, f"{type(e).__name__}: {e}"
    txt = sortie.getvalue()
    verifier("il ne lève pas et rend 0", leve is None and code == 0,
             leve or "")
    verifier("il nomme TOUS les domaines figés, pas seulement le premier",
             all(d in txt for d in DOMAINES),
             " ".join(l.strip() for l in txt.splitlines()[:1]))
    verifier("il publie le compte PAR DOMAINE — un total de 203 ne dit pas "
             "si les Pyrénées sont dedans",
             any(f"{d} :" in txt for d in DOMAINES))

    print("\n── 2. Les DEUX formes de manifeste sont acceptées ──")
    balises, man = F.charger_artefact()
    verifier("l'artefact commité porte bien la forme au PLURIEL",
             "domaines" in man and isinstance(man["domaines"], dict),
             ", ".join(sorted(man.get("domaines") or {})))
    # L'ancienne forme, telle qu'un artefact figé avant le 12/08 la porte.
    ancien = {k: v for k, v in man.items() if k != "domaines"}
    ancien["domaine"] = DOMAINE
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "axe.json"
        p.write_text(json.dumps(ancien, ensure_ascii=False), encoding="utf-8")
        try:
            F.charger_artefact(p)
            passe = True
            err = ""
        except Exception as e:                               # noqa: BLE001
            passe, err = False, str(e)[:120]
    verifier("⚠️ un artefact à l'ANCIENNE forme est encore relu — sinon tout "
             "run lancé entre le déploiement et le regel échouerait, y "
             "compris pour les domaines qui n'ont rien demandé", passe, err)

    print("\n── 3. Mais un axe figé sur d'AUTRES bornes est refusé ──")
    faux = {k: v for k, v in man.items()}
    faux["domaines"] = {"nord-alpes": dict(DOMAINE, latmax=DOMAINE["latmax"] + 1)}
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "axe.json"
        p.write_text(json.dumps(faux, ensure_ascii=False), encoding="utf-8")
        try:
            F.charger_artefact(p)
            refuse = False
        except Exception:                                    # noqa: BLE001
            refuse = True
    verifier("⛔ un domaine élargi fait LEVER — l'archive est disposée par "
             "indice de balise, un axe qui bouge la décale en silence",
             refuse)

    print("\n── 4. L'axe est complet et cohérent ──")
    par = man.get("n_par_domaine") or {}
    verifier("le total annoncé est celui de la liste",
             man["n"] == len(balises), f"{man['n']} contre {len(balises)}")
    somme = sum(par.values())
    verifier("la somme des comptes par domaine retombe sur le total",
             somme == man["n"], f"{somme} contre {man['n']}")
    ids = [b.get("id") for b in balises]
    verifier("aucun identifiant en double — un doublon décalerait tout ce "
             "qui suit dans l'archive", len(ids) == len(set(ids)),
             f"{len(ids) - len(set(ids))} doublon(s)")
    # ⚠️ ON COMPARE À `_rang`, PAS À UN TRI QU'ON DEVINE. Ma première
    # version de ce contrôle exigeait `sorted(ids)` — et elle échouait,
    # à juste titre : `_rang` fait passer les points de RADIOSONDAGE
    # après toutes les balises, quel que soit leur identifiant. Un banc
    # qui réimplémente la règle qu'il vérifie ne vérifie que
    # lui-même — et ici il aurait fait rouge sur un axe parfaitement bon.
    verifier("l'axe est trié par `_rang` — radiosondages en dernier, puis "
             "par identifiant",
             [b.get("id") for b in sorted(balises, key=F._rang)] == ids)

    print("\n  freeze_balises :", "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
