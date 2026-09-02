#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/harnais.py — ce que TOUS les harnais de mutations doivent
#  faire pareil, écrit une fois (02/09/2026, vérification de cohérence)
#
#  ⛔ DEUX PIÈGES VÉCUS, AUCUN N'ÉTAIT FERMÉ PARTOUT :
#
#  1. UN HARNAIS TUÉ LAISSE LE DÉPÔT MUTÉ. Chaque harnais restaure son
#     fichier en `finally` — mais un processus tué (délai d'outil, pont
#     Cowork qui tombe) ne passe jamais par son `finally`. Vécu deux
#     fois le 27/08 (`inference.py`), une fois le 31/08. Le seul garde
#     était `if avant not in origine`, qui ne voit qu'UNE mutation et
#     rend un message qui invite à réécrire le motif. Ici : le fichier
#     d'origine est COPIÉ SUR LE DISQUE (`<fichier>.harnais-origine`)
#     avant la première mutation ; au démarrage suivant, une copie qui
#     traîne est RESTAURÉE et nommée — et à la fin, on vérifie par
#     sha256 que ce qui est rendu est ce qui a été pris.
#
#  2. LE BYTECODE DE LA MUTATION PRÉCÉDENTE. Une mutation de même
#     longueur restaurée dans la même seconde laisse Python recharger
#     le `.pyc` MUTÉ (30/08, lot L10 : trois lignes vertes qui ne
#     prouvaient rien). Cinq harnais sur vingt-neuf purgeaient
#     `__pycache__` ; `env_banc()` le fait pour tous, et pose
#     `PYTHONDONTWRITEBYTECODE=1` pour que le banc n'en réécrive pas.
#
#  ⚠️ Ce module n'importe rien du projet : il doit pouvoir tourner
#  quand `score.py` est muté au point de ne plus s'importer.
# ══════════════════════════════════════════════════════════════════════
from __future__ import annotations

import hashlib
import os
import pathlib
import shutil

SUFFIXE_ORIGINE = ".harnais-origine"


def _sha(texte: str) -> str:
    return hashlib.sha256(texte.encode("utf-8")).hexdigest()


def copie_origine(fichier: pathlib.Path) -> pathlib.Path:
    return fichier.with_name(fichier.name + SUFFIXE_ORIGINE)


def garder(fichier: pathlib.Path) -> str:
    """Lit le fichier À MUTER et en garde une copie sur le disque.

    ⛔ Si une copie traîne d'un harnais TUÉ, c'est ELLE qui fait foi :
    le fichier courant est muté, on le restaure d'abord, et on le dit —
    sinon la première mutation partirait d'un code déjà faux, et le
    banc rougirait pour la faute d'hier.
    """
    fichier = pathlib.Path(fichier)
    copie = copie_origine(fichier)
    if copie.exists():
        origine = copie.read_text(encoding="utf-8")
        courant = fichier.read_text(encoding="utf-8")
        if courant != origine:
            fichier.write_text(origine, encoding="utf-8")
            print(f"  ⚠️ {fichier.name} était MUTÉ (harnais précédent tué) : "
                  f"restauré depuis {copie.name} avant de jouer.")
        return origine
    origine = fichier.read_text(encoding="utf-8")
    copie.write_text(origine, encoding="utf-8")
    return origine


def rendre(fichier: pathlib.Path, origine: str) -> None:
    """Restaure, VÉRIFIE par sha256, puis retire la copie.

    ⚠️ La copie n'est retirée QUE si la vérification passe : un dépôt
    qu'on n'a pas su rendre garde sa preuve sur le disque.
    """
    fichier = pathlib.Path(fichier)
    fichier.write_text(origine, encoding="utf-8")
    rendu = fichier.read_text(encoding="utf-8")
    if _sha(rendu) != _sha(origine):
        raise RuntimeError(f"{fichier.name} n'a pas été rendu à l'identique "
                           f"— la copie {copie_origine(fichier).name} est "
                           f"gardée, restaurer à la main.")
    copie = copie_origine(fichier)
    if copie.exists():
        copie.unlink()


def env_banc(racine: pathlib.Path) -> dict:
    """L'environnement d'un banc : sans bytecode, ni lu ni écrit."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for p in pathlib.Path(racine).rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)
    return env


def copies_qui_trainent(racine: pathlib.Path) -> list[pathlib.Path]:
    """Les `*.harnais-origine` laissés par des harnais tués — pour le
    déploiement, qui refuse de partir avec un dépôt peut-être muté."""
    return sorted(pathlib.Path(racine).rglob(f"*{SUFFIXE_ORIGINE}"))
