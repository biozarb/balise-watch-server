#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  tools/r2_lecture.py — LIRE un autre bucket R2 que celui du job
#                                        (lot S0.5, 22/08/2026)
#
#  Deux fonctions, sorties À L'IDENTIQUE de `model-verif/agrume_fcst.py`
#  (lot I, 13/08/2026) parce qu'un SECOND collecteur en a besoin :
#  `model-verif/arome_fcst.py`, qui lit `arome/sol/` dans le même bucket
#  `balise-watch-grids`, avec le même jeton, contre le même piège.
#
#  Même motif que `tools/mf_s3.py` le 10/08 (les quatre fonctions S3
#  sorties d'`arome-wind/ingest.py` pour le poller d'AGRUME) et que
#  `tools/storage.py` le 03/08 (cinq copies de `sb_upload` réunies) :
#  la consigne du chantier est « étendre, ne pas réécrire ». Le corps
#  et les commentaires ci-dessous n'ont pas bougé d'une virgule ; seul
#  l'endroit où ils vivent a changé.
#
#  ⚠️ `agrume_fcst.prefixe_lecture` et `agrume_fcst.bucket_r2` existent
#  toujours sous ces noms — ce sont maintenant des import. Le banc
#  `test_agrume_fcst.py` les appelle par `A.bucket_r2(...)` et continue
#  de passer sans une ligne de changement : un attribut de module reste
#  un attribut de module.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import contextlib
import os

#: ⛔ LE JETON R2 ORDINAIRE DU VPS ÉCRIT SUR `balise-watch-grids` MAIS NE
#: LE LIT PAS. Mesuré le 13/08 : `HeadObject` sur une clé PI écrite six
#: minutes plus tôt rend **403**, et `ListObjectsV2` aussi. C'est le même
#: jeton qui a fait écrire à `~/.balise-watch-r2.env` que « le jeton de
#: ce VPS n'a pas ListBuckets ». Le producteur lit donc avec le jeton
#: LECTURE SEULE de l'audit, qui, lui, liste et lit (22 runs du produit A
#: retrouvés avec lui le 13/08 ; 570 objets `arome/` le 22/08).
#: L'écriture de l'archive, elle, repart sur le jeton ordinaire et sur
#: `model-verif`.
#:
#: Ordre d'essai, du plus spécifique au plus général. ⚠️ Le dernier
#: échelon (`R2_*`) est un repli qui ÉCHOUERA sur le VPS d'aujourd'hui,
#: et c'est voulu : il fait marcher le job partout où le jeton principal
#: a le droit de lire (les Actions, une machine de dev), sans faire
#: croire qu'un jeton dédié n'est pas souhaitable.
#: ⓘ Reliquat assumé : un jeton `AGRUME_R2_READ_*` propre, scopé au seul
#: bucket des grilles, vaudrait mieux que d'emprunter celui de l'audit —
#: le jour où Yann le crée, il suffit de le poser dans le .env.
PREFIXES_LECTURE = ("AGRUME_R2_READ_", "BW_R2_AUDIT_", "R2_")


def prefixe_lecture() -> str:
    """Le premier jeu d'identifiants R2 disponible pour la LECTURE.

    Rend le préfixe de variables retenu (`"BW_R2_AUDIT_"`, …). Le
    dernier échelon (`"R2_"`) est toujours rendu par défaut, même
    incomplet : c'est l'appelant qui dira ce qui a été refusé, avec le
    nom de la variable à poser.
    """
    for p in PREFIXES_LECTURE:
        if os.environ.get(p + "ACCESS_KEY_ID") and \
                os.environ.get(p + "SECRET_ACCESS_KEY"):
            return p
    return PREFIXES_LECTURE[-1]


@contextlib.contextmanager
def bucket_r2(nom: str, prefixe: str | None = None):
    """Force `R2_BUCKET` (et les identifiants) le temps d'un `Storage`.

    ⛔ LE PIÈGE QUE CE BLOC EXISTE POUR ÉVITER, ET IL EST SILENCIEUX.
    `tools/storage.py` résout le bucket R2 par
    `os.environ.get("R2_BUCKET") or defaut` — `R2_BUCKET` PRIME sur le
    `bucket_env` passé en argument. Or `run.sh` exporte
    `R2_BUCKET=model-verif` pour tous les modes du module. Sans ce
    bloc, la lecture irait chercher `model-verif/arome/sol/…` : une clé
    qui n'existe pas, donc un `None`, donc « tuile absente », donc zéro
    ligne toutes les nuits — et rien ne s'allumerait, parce qu'une
    tuile absente est un cas NORMAL au démarrage.

    ⛔ ET LES IDENTIFIANTS AVEC, pour la même raison en pire : le jeton
    ordinaire du VPS ÉCRIT sur `balise-watch-grids` sans pouvoir le LIRE
    (403 mesuré le 13/08 sur une clé existante). `prefixe` désigne le jeu
    de variables à utiliser ; `None` laisse celles en place.

    On restaure tout en sortant : l'envoi de l'archive, lui, doit
    repartir sur `model-verif` avec le jeton ordinaire.
    """
    cles = ["R2_BUCKET"]
    if prefixe and prefixe != "R2_":
        cles += ["R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"]
    avant = {k: os.environ.get(k) for k in cles}
    os.environ["R2_BUCKET"] = nom
    if prefixe and prefixe != "R2_":
        for suffixe in ("ACCESS_KEY_ID", "SECRET_ACCESS_KEY"):
            v = os.environ.get(prefixe + suffixe)
            if v:
                os.environ["R2_" + suffixe] = v
    try:
        yield nom
    finally:
        for k, v in avant.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
