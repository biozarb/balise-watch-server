#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  verif/test_separation.py — la coupe `agrume/` ⟂ `verif/` tient-elle ?
#                                                        (13/08/2026)
#
#  ⛔ CE BANC EXISTE PARCE QU'UNE SÉPARATION NE SE MAINTIENT PAS TOUTE
#  SEULE. Elle a coûté un refactor (Lot J, arbitrage A3) ; six mois plus
#  tard, un `from colonnes import …` ajouté dans `agrume/` la défera sans
#  qu'aucun test ne tombe, sans qu'aucun écran ne change, et sans que
#  personne s'en aperçoive — jusqu'au jour où le modèle ne se déploiera
#  plus sans le module de scoring.
#
#  LA RÈGLE, dans les deux sens :
#    ✅ `verif/` PEUT importer `agrume/` — la vérification lit le modèle.
#    ⛔ `agrume/` n'importe JAMAIS `verif/`, à DEUX exceptions près,
#       nommées une par une ci-dessous. Une liste nominative, pas une
#       catégorie : « les bancs ont le droit » se serait élargi tout
#       seul.
#
#  ⚠️ Il est STATIQUE (`ast`) et non dynamique : il voit un import même
#  dans une branche qui ne s'exécute jamais, et il n'a besoin ni de
#  numpy, ni de réseau, ni d'exécuter le module. C'est le même principe
#  que le banc d'arité ajouté le 13/08 après la panne de `index_apres`.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import ast
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parent
AGRUME, VERIF = RACINE / "agrume", RACINE / "verif"

# ⛔ LES EXCEPTIONS, NOMMÉES. Chacune coûte une ligne ici, et c'est le
# but : ajouter la troisième oblige à écrire pourquoi.
EXCEPTIONS = {
    # L'ingestion remplit les DEUX produits dans le MÊME `sur_champ`,
    # depuis les mêmes messages (7,6 s contre 7,9 mesurés le 10/08). On
    # sépare les MODULES, jamais la passe. L'alternative — déplacer
    # l'ingestion dans `verif/` — ferait dépendre le produit B du module
    # de scoring, ce qui est pire dans les deux sens.
    "ingest_colonnes.py",
    # Ces deux bancs comparent le produit A au produit B : leur travail
    # EST de tenir les deux côtés à la fois. Ce ne sont pas des modules,
    # rien ne les importe, et ils ne partent pas en production.
    "test_transect.py",
    "test_profil.py",
}

echecs = []


def verifier(nom, condition, detail=""):
    print(f"  {'✓' if condition else '✗'} {nom}" + (f"   {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


def modules_de(dossier):
    return {p.stem for p in dossier.glob("*.py")}


def imports_de(fichier):
    """Les noms de modules importés, y compris dans les imports LOCAUX
    (à l'intérieur d'une fonction) — c'est justement là qu'on triche."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"), filename=str(fichier))
    noms = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            noms.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module and n.level == 0:
            noms.add(n.module.split(".")[0])
    return noms


def main():
    mods_agrume, mods_verif = modules_de(AGRUME), modules_de(VERIF)
    propres_a_verif = mods_verif - mods_agrume

    print("\n── 1. la topologie ──")
    verifier("`agrume/quantification.py` existe (la moitié modèle)",
             "quantification" in mods_agrume)
    verifier("`verif/colonnes.py` existe (le conteneur produit A)",
             "colonnes" in mods_verif)
    verifier("⛔ `colonnes` n'est plus dans `agrume/` — pas de doublon, "
             "pas de shim : un shim aurait laissé les vieux imports "
             "marcher et la coupe n'aurait rien coupé",
             "colonnes" not in mods_agrume)
    verifier("`quantification` n'est PAS dans `verif/` (une seule "
             "définition des unités dans tout le dépôt)",
             "quantification" not in mods_verif)
    verifier("`verif/purge.py` existe", "purge" in mods_verif)

    print("\n── 2. ⛔ aucune flèche `agrume/` → `verif/`, sauf les nommées ──")
    fautes = []
    for f in sorted(AGRUME.glob("*.py")):
        interdits = imports_de(f) & propres_a_verif
        if not interdits:
            continue
        if f.name in EXCEPTIONS:
            print(f"    ⓘ exception assumée : {f.name} → "
                  f"{', '.join(sorted(interdits))}")
            continue
        fautes.append((f.name, sorted(interdits)))
    verifier("aucun module d'`agrume/` n'importe `verif/` hors "
             "exceptions", not fautes, f"{fautes}" if fautes else "")

    inutiles = {e for e in EXCEPTIONS
                if not (imports_de(AGRUME / e) & propres_a_verif)}
    verifier("⚠️ aucune exception PÉRIMÉE — une exception qui ne sert "
             "plus est une permission qui traîne",
             not inutiles, f"{sorted(inutiles)}" if inutiles else "")

    print("\n── 3. le sens autorisé fonctionne ──")
    lit_agrume = {f.name for f in VERIF.glob("*.py")
                  if imports_de(f) & (mods_agrume - mods_verif)}
    verifier("`verif/` importe bien `agrume/` (sinon la coupe aurait "
             "dupliqué du code au lieu de le partager)",
             len(lit_agrume) >= 3, f"{len(lit_agrume)} fichiers")

    print("\n── 4. le banc sait-il échouer ? ──")
    # On fabrique la faute en mémoire et on vérifie que la règle la voit.
    faux = ast.parse("from purge import cles_du_run\n")
    noms = {n.module for n in ast.walk(faux) if isinstance(n, ast.ImportFrom)}
    verifier("un `from purge import …` posé dans `agrume/` serait bien "
             "détecté comme une flèche interdite",
             bool(noms & propres_a_verif), f"{sorted(noms)}")

    print("\n  séparation :", "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
