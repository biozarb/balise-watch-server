#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/ingest_colonnes.py — produit A : ingestion des colonnes
#                                                        (10/08/2026)
#
#  Étape 4 de la séquence du lot H. Le socle : c'est ce fichier qui
#  transforme 7 Go de GRIB France entière en ~1 Mo de colonnes
#  verticales aux balises des Alpes du Nord, archivées indéfiniment.
#
#  ── LA CONTRAINTE MATÉRIELLE, ET C'EST LA SEULE ──────────────────────
#  ⚠️ **Le disque du runner GitHub fait 14 Go.** Un run AGRUME complet
#  tire 4,84 Go de GRIB en 0,025° (HP1 + HP2 sur 0–24 h) plus 2,4 Go en
#  0,01° pour l'hybride, et la chaîne `arome-wind` en tire déjà 4,4 —
#  **ça ne tient pas ensemble.** D'où la règle absolue de ce fichier :
#  **UN SEUL FICHIER SUR LE DISQUE À LA FOIS**, téléchargé, lu, supprimé.
#  Le pic d'occupation est journalisé à chaque run, et un critère
#  d'acceptation du lot exige qu'il reste sous 10 Go.
#
#  ✅ **La mémoire, elle, n'est pas un sujet** : pic RSS mesuré à
#  **88,0 Mo** pour digérer un fichier de 818 Mo, sur des runners qui ont
#  16 Go. On est à 0,5 %. Le pic est dominé par le décodage d'UN message
#  isolé, pas par l'accumulation — et ici on n'accumule que ~125 balises.
#
#  ── LA STRATÉGIE DE LECTURE, MESURÉE ET NON DEVINÉE ──────────────────
#  Sur un bundle réel de 818 Mo (1 225 messages), en 2 vCPU :
#      balayer les en-têtes seuls .............  1,3 s  (1 ms/message)
#      décoder u/v (336 messages) .............  7,9 s  (~21 ms/message)
#      décoder u/v PUIS découper le domaine ...  7,6 s  (la découpe est
#                                                 GRATUITE)
#      tout décoder (1 225 messages) .......... 25,0 s
#  Trois conséquences, appliquées telles quelles ici :
#    • on FILTRE sur l'en-tête (`shortName`/`level`/`step`) avant de
#      décoder — c'est quasi gratuit et ça divise le coût par 3 ;
#    • on décode France entière et on prélève ensuite : chercher à être
#      malin ne rapporterait rien de mesurable ;
#    • **le goulot est le RÉSEAU, jamais le CPU.**
#
#  ── BUDGET ───────────────────────────────────────────────────────────
#  Téléchargement à 20,9 Mo/s mesuré. Marge sous le timeout de 60 min :
#  41,2 min (run `arome-wind` : médiane 12,4, max 18,8, n = 37).
#  Le run le plus lourd prévu ici tient six fois dans cette marge — mais
#  la durée RÉELLE est mesurée et journalisée à chaque passage, avec
#  alerte au-delà de 30 min. Un budget qu'on ne mesure pas n'est pas un
#  budget.
#
#  Usage :
#      python3 agrume/ingest_colonnes.py --stations /var/lib/…/stations.json
#      python3 agrume/ingest_colonnes.py --max-heures 0 --sans-ecriture
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

from colonnes import (PARAM_ALTITUDE, PARAM_PRESSION_SOL,  # noqa: E402
                      PARAMS_001, PARAMS_0025, PARAMS_ISO, PARAMS_SURFACE,
                      Abort, Colonnes, balises_du_domaine, index_plats,
                      quantifier, verifier_grille)
from domaine import (GRID_3D, GRID_FINE, MAX_HOURS,  # noqa: E402
                     MODEL_DIR, NIVEAUX_P, PAQUET_ISOBARES,
                     PAQUET_NEBULOSITE, PAQUETS_ISOBARES, PAQUETS_SURFACE)
from grille import Grille, axes_depuis_orographie, decouper  # noqa: E402
from freeze_balises import charger_artefact as charger_balises  # noqa: E402
from mf_s3 import (bornes_echeances, covered_steps, download_tmp,  # noqa: E402
                   est_fichier_horaire, s3_objets)
from orographie import (charger_artefact, charger_artefacts,  # noqa: E402
                        charger_artefact_isolees, charger_artefact_verif)

# ⚠️ Alerte de durée : la MOITIÉ du timeout de 60 min, et six fois le
# budget mesuré. Si on l'atteint, ce n'est pas « c'était un peu long »,
# c'est que quelque chose a changé.
ALERTE_DUREE_MIN = 30
PLAFOND_DISQUE_GO = 10.0


def journal_horodate(msg):
    print(f"[{datetime.now(timezone.utc):%H:%M:%S}] {msg}", flush=True)


# ══════════════════════════════════════════════════════════════════════
#  Choix du run
# ══════════════════════════════════════════════════════════════════════
# Les quatre paquets dont le produit A a besoin. ⚠️ DEUX paquets en
# 0,025°, pas un : HP1 pour le vent et la thermo, HP2 pour la TKE (qui
# vit avec le géopotentiel). Ils pèsent presque autant l'un que l'autre.
PAQUETS = (
    (GRID_3D, "HP1"),
    (GRID_3D, "HP2"),
    (GRID_FINE, "HP1"),      # hybride : u/v à 20, 50, 100 m
    (GRID_FINE, "SP1"),      # hybride : 10u/10v à 10 m
    # Étape 5 : le haut du profil. ⚠️ `IP1` porte u, v, t, r ET le
    # géopotentiel `z` — les cinq dans le même paquet, mesuré le 10/08.
    # Les quatre autres paquets IP* ne contiennent rien dont le raccord
    # ait besoin. +1,73 Go sur 0–24 h, bundles de 496 Mo au plus (donc
    # sous le pic de 815 Mo déjà atteint par HP1 : le disque ne bouge pas).
    (GRID_3D, PAQUET_ISOBARES),
    # Étape 12 : la nébulosité par niveau. ⚠️ SEUL TÉLÉCHARGEMENT NEUF DU
    # LOT, +450 Mo sur 0–24 h (mesuré le 12/08, run 15 Z). Il n'est pas
    # là pour enrichir le produit : il est là parce que sans `cc` la vue
    # de coupe affirme « ciel clair » sur toutes les colonnes.
    (GRID_3D, PAQUET_NEBULOSITE),
    # Étape 12 bis : la ligne de SURFACE de la vue de coupe, et l'ancre
    # basse de la pression dérivée. ⚠️ +388 Mo sur 0–24 h, bundles de
    # 56 Mo au plus — le pic disque ne bouge pas, la durée si.
    (GRID_3D, "SP1"),
    (GRID_3D, "SP2"),
)


def choisir_run(max_heures, profondeur=5, crier=journal_horodate):
    """Run maximisant la couverture COMMUNE aux quatre paquets.

    Même esprit que `arome-wind/ingest.py::pick_run`, et pour la même
    raison, apprise à la dure le 25/07 : prendre le run le plus récent
    dès qu'UN fichier existe donne un run éternellement incomplet, réécrit
    au run suivant, dont les échéances lointaines ne sont JAMAIS publiées.
    Ici le risque est pire, parce que l'archive est définitive : une
    colonne tronquée écrite aujourd'hui le reste pour toujours.
    """
    base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    base -= timedelta(hours=base.hour % 3)
    voulues = list(range(0, max_heures + 1))
    meilleur = None
    for k in range(profondeur):
        run = base - timedelta(hours=3 * k)
        ref = run.strftime("%Y-%m-%dT%H:00:00Z")
        commun = set(voulues)
        detail = []
        for grille, paquet in PAQUETS:
            c = covered_steps(ref, paquet, grille, voulues, model=MODEL_DIR)
            detail.append(f"{grille}/{paquet} {len(c)}")
            commun &= c
        crier(f"  run {ref} : {len(commun)}/{len(voulues)} échéances communes "
              f"({', '.join(detail)})")
        if meilleur is None or len(commun) > len(meilleur[2]):
            meilleur = (ref, run, commun)
        if len(commun) == len(voulues):
            break
    if meilleur is None or not meilleur[2]:
        raise Abort("aucun run ne publie les quatre paquets sur les 5 derniers "
                    "réseaux — rien à archiver.")
    ref, run, commun = meilleur
    crier(f"→ run retenu : {ref} ({len(commun)}/{len(voulues)} échéances)")
    return ref, run, sorted(commun)


def fichiers_du_paquet(ref, grille, paquet, steps, lister=s3_objets):
    """Fichiers à tirer, et RIEN de plus.

    ⚠️ En 0,01° les fichiers sont HORAIRES : ne tirer que les échéances
    retenues évite ~550 Mo de trafic pour rien. En 0,025° ils sont
    groupés par 6 h : on prend le bundle dès qu'il intersecte le besoin.
    """
    besoin = set(steps)
    out = []
    for cle, taille in lister(f"pnt/{ref}/{MODEL_DIR}/{grille}/{paquet}/"):
        b = bornes_echeances(cle)
        if b is None:
            continue
        debut, fin = b
        if est_fichier_horaire(cle):
            if debut in besoin:
                out.append((cle, taille))
        elif any(debut <= h <= fin for h in besoin):
            out.append((cle, taille))
    return sorted(out)


# ══════════════════════════════════════════════════════════════════════
#  Lecture d'un GRIB, message par message
# ══════════════════════════════════════════════════════════════════════
def parcourir(chemin, veut, sur_champ, steps_voulus):
    """Balaie un GRIB, ne décode QUE ce que `veut` retient.

    `veut(shortName, typeOfLevel, level) -> clé | None`
    `sur_champ(cle, step, values, meta)`

    ⚠️ L'ordre des `codes_get` compte : `step` est lu AVANT
    `codes_get_values`, parce que décoder puis jeter coûterait le double
    de temps CPU pour rien (leçon écrite dans `arome-wind/ingest.py`).

    ⚠️ Les messages dont les clés attendues manquent sont IGNORÉS, pas
    fatals — `SP3` en contient au moins un, et ça a cassé un run de
    production le 21/07.

    ⚠️⚠️ MAIS CE `except` NE COUVRAIT PAS QUE LA LECTURE DES CLÉS : il
    engloutissait aussi TOUTE exception levée par `sur_champ`, c'est-à-dire
    par le traitement lui-même. Une erreur de forme, un indice hors
    bornes, une conversion ratée — rien ne s'allumait, et le compteur
    `decodes` se contentait de ne pas monter. Constaté le 10/08 en
    branchant le produit B : une fenêtre de la mauvaise maille posée dans
    la grille aurait échoué **sans un mot**.

    On ne rend pas ça fatal — l'archive du produit A est définitive et
    l'interrompre coûterait un run entier pour un message. Mais on
    COMPTE, et on renvoie le premier incident : un run qui perd des
    champs doit se voir dans le bilan, pas se deviner dans un
    remplissage. *Un `pass` qui protège d'un cas connu finit toujours
    par en cacher un inconnu.*
    """
    from eccodes import (codes_get, codes_get_values,
                         codes_grib_new_from_file, codes_release)
    lus = decodes = 0
    incidents = []
    with open(chemin, "rb") as f:
        while True:
            gid = codes_grib_new_from_file(f)
            if gid is None:
                break
            lus += 1
            try:
                cle = veut(codes_get(gid, "shortName"),
                           codes_get(gid, "typeOfLevel"),
                           codes_get(gid, "level"))
                if cle is not None:
                    step = codes_get(gid, "step")
                    if step in steps_voulus:
                        meta = dict(
                            Ni=codes_get(gid, "Ni"), Nj=codes_get(gid, "Nj"),
                            lat0=codes_get(gid, "latitudeOfFirstGridPointInDegrees"),
                            lon0=codes_get(gid, "longitudeOfFirstGridPointInDegrees"),
                            di=codes_get(gid, "iDirectionIncrementInDegrees"),
                            dj=codes_get(gid, "jDirectionIncrementInDegrees"),
                            jScan=codes_get(gid, "jScansPositively"))
                        if meta["lon0"] > 180:
                            meta["lon0"] -= 360
                        sur_champ(cle, step, codes_get_values(gid), meta)
                        decodes += 1
            except Exception as e:      # noqa: BLE001
                if isinstance(e, Abort):
                    codes_release(gid)
                    raise
                # ⚠️ Toujours non fatal — mais plus muet. Un message sans
                # les clés attendues est attendu (`SP3`) ; une erreur de
                # traitement ne l'est pas, et rien ici ne peut faire la
                # différence. On garde donc les DEUX, et le bilan les
                # montre : c'est au lecteur de trancher, pas au `pass`.
                if len(incidents) < 5:
                    incidents.append(f"{type(e).__name__}: {e}")
            codes_release(gid)
    return lus, decodes, incidents


def filtre_0025(paquet):
    """Ce qu'on retient dans un bundle 0,025°.

    ⚠️ Le vent n'existe qu'À PARTIR DE 20 m sur les niveaux hauteur : le
    10 m vient des champs dédiés `10u`/`10v`, `typeOfLevel`
    `heightAboveGround`, niveau 10. Sans ce cas particulier, la colonne
    aurait un trou EXACTEMENT à l'altitude où la balise mesure.
    """
    voulus = {p["court"]: p for p in PARAMS_0025 if p["paquet"] == paquet}
    dix = {p["court_10m"]: p for p in PARAMS_0025
           if p["paquet"] == paquet and p["court_10m"]}

    def veut(sn, tol, lvl):
        if sn in dix and lvl == 10:
            return (dix[sn]["nom"], 10)
        p = voulus.get(sn)
        if p is None or tol != "heightAboveGround":
            return None
        from domaine import NIVEAUX_H_0025
        return (p["nom"], lvl) if lvl in NIVEAUX_H_0025 else None
    return veut


def filtre_iso(paquet=PAQUET_ISOBARES):
    """Ce qu'on retient dans un bundle isobare — `IP1` ou `IP2`.

    ⚠️ LE `typeOfLevel` FAIT PARTIE DU FILTRE, PAS DE LA DÉCORATION. Le
    géopotentiel `z` existe aussi dans `IP5`, mais sur des niveaux de
    **vorticité potentielle** (1500 et 2000) — mesuré le 10/08. Un filtre
    sur le seul `shortName` ramasserait ces messages-là et fabriquerait
    des altitudes absurdes au milieu du profil, sans rien casser de
    visible. On ne lit `IP5` nulle part, mais la règle vaut d'être écrite :
    ce jour où quelqu'un ajoutera un paquet, elle sera déjà là.

    ⚠️⚠️ ET LE PAQUET AUSSI FAIT PARTIE DU FILTRE, DEPUIS LE 12/08. Les
    descripteurs portent leur `paquet` ; on ne retient dans un bundle que
    les champs qui s'en réclament. Sans ce tri, un `shortName` partagé
    par deux bundles serait posé DEUX FOIS — la seconde écrasant la
    première — et rien ne le dirait. Ce n'est pas hypothétique :
    l'inventaire eccodes du 12/08 sur `0025/IP2` liste 1 008 messages
    dont 168 de `shortName` **`unknown`**, et un `unknown` de plus dans
    un futur paquet est exactement le genre de collision qui se
    produirait sans que rien ne s'allume.
    """
    voulus = {p["court"]: p["nom"] for p in PARAMS_ISO
              if p["paquet"] == paquet}
    veut_altitude = PARAM_ALTITUDE["paquet"] == paquet
    niveaux = set(NIVEAUX_P)

    def veut(sn, tol, lvl):
        if tol != "isobaricInhPa" or lvl not in niveaux:
            return None
        if sn == PARAM_ALTITUDE["court"]:
            return (PARAM_ALTITUDE["nom"], lvl) if veut_altitude else None
        nom = voulus.get(sn)
        return (nom, lvl) if nom else None
    return veut


def filtre_surface(paquet):
    """Ce qu'on retient dans `0025/SP1` et `0025/SP2`.

    ⚠️⚠️ TROIS PIÈGES, TOUS MESURÉS LE 13/08, ET AUCUN NE LÈVE.

    1. **`typeOfLevel` ne suffit plus.** Les champs de surface vivent sur
       `surface`, `heightAboveGround` (2 m pour `2t`/`2d`, 10 m pour la
       rafale) — et `CAPE_INS` sur **`unknown`**. Un filtre qui exigerait
       `surface` en perdrait la moitié, en silence.
    2. **Le paquet fait partie du filtre**, comme pour les isobares :
       `2t` existe dans SP1, `t` dans SP2, et SP2 porte aussi le `h` de
       l'orographie qu'on ne veut surtout pas réingérer par run.
    3. **`10u`/`10v` sont dans SP1 aussi**, et on ne les prend PAS ici :
       le 0,025° les tient déjà de `HP1` (niveau 10 des niveaux hauteur).
       Les reprendre écraserait la même valeur par elle-même au mieux, et
       par une autre convention au pire.
    """
    voulus = {p["court"]: p for p in PARAMS_SURFACE if p["paquet"] == paquet}
    if PARAM_PRESSION_SOL["paquet"] == paquet:
        voulus[PARAM_PRESSION_SOL["court"]] = PARAM_PRESSION_SOL

    def veut(sn, tol, lvl):
        p = voulus.get(sn)
        if p is None:
            return None
        # ⚠️ Le niveau publié est FIXÉ À 0 pour tous : un champ de surface
        # n'a pas de niveau, et laisser passer celui du GRIB ferait entrer
        # `2t` au « niveau 2 » et la rafale au « niveau 10 » — deux
        # valeurs qui EXISTENT dans les 25 niveaux hauteur du produit.
        return (p["nom"], 0)
    return veut


def filtre_001(paquet):
    """Ce qu'on retient en maille fine — 4 niveaux, pas un de plus.
    ⛔ Rien n'existe au-dessus de 100 m dans cette grille."""
    from domaine import NIVEAUX_H_001
    voulus = {p["court"]: p for p in PARAMS_001}
    dix = {p["court_10m"]: p for p in PARAMS_001}

    def veut(sn, tol, lvl):
        if paquet == "SP1":
            return (dix[sn]["nom"], 10) if sn in dix and lvl == 10 else None
        p = voulus.get(sn)
        if p is None or tol != "heightAboveGround":
            return None
        return (p["nom"], lvl) if lvl in NIVEAUX_H_001 and lvl != 10 else None
    return veut


# ══════════════════════════════════════════════════════════════════════
def ingerer(ref, run, steps, balises, paire_orog, crier=journal_horodate,
            limite_fichiers=None, avec_grille=True, orogs_grille=None):
    """`orogs_grille` : {domaine: orographie 0,025°} — les domaines du
    produit B.

    ⚠️ 12/08 — CE PARAMÈTRE EST LA SEULE CHOSE QUI SÉPARE « un produit B »
    DE « autant de produits B que de domaines », et il est distinct de
    `paire_orog` À DESSEIN. `paire_orog` porte les DEUX MAILLES d'UN
    domaine (0,01° et 0,025°) et sert le produit A ; `orogs_grille` porte
    UNE maille (0,025°, la seule où les 25 niveaux existent) pour
    PLUSIEURS domaines et sert le produit B. Les confondre — ce que le
    nom `paire` invite à faire — reviendrait à découper la grille 3D sur
    la maille fine, c'est-à-dire à poser une fenêtre de 151×211 dans un
    tableau de 61×85. Le commentaire de `_g == GRID_3D`, plus bas, décrit
    déjà ce que ça donne : rien ne s'allume.
    """
    col = Colonnes(ref, balises, steps)

    # ── Le produit B, dans la MÊME passe ──────────────────────────────
    # ⚠️ C'est ici que l'étape 6 devient presque gratuite : les messages
    # sont déjà téléchargés et déjà décodés pour le produit A. Découper
    # en plus la fenêtre du domaine coûte une vue numpy — la mesure du
    # 10/08 donne 7,6 s avec découpe contre 7,9 s sans, sur un bundle de
    # 818 Mo. Le budget de 2,9 min du §4.2 supposait une chaîne séparée
    # qui retéléchargerait tout ; elle n'a plus lieu d'être.
    #
    # ⚠️ La fenêtre vient de l'orographie 0,025°, pas d'un `fenetre()`
    # rejoué : le sol et la colonne doivent tomber sur les mêmes points
    # par construction (cf. l'en-tête de `grille.py`).
    # ── Le produit B : UNE grille PAR DOMAINE, dans la même passe ─────
    # ⚠️ 12/08 — les Pyrénées entrent ici. Le surcoût est une DÉCOUPE de
    # plus par champ décodé : le téléchargement, le décodage eccodes et
    # le pic disque sont strictement inchangés, puisque les paquets sont
    # les mêmes et déjà sur le disque. Ce qui change vraiment est la
    # MÉMOIRE — chaque domaine porte son tableau float16 — et le
    # stockage R2, chiffré par `verifier_dimensionnement`.
    grilles = {}
    if avec_grille:
        if orogs_grille is None:
            orogs_grille = {"nord-alpes": paire_orog[GRID_3D]}
        from domaine import DOMAINES  # noqa: PLC0415
        for nom_dom, o3d in sorted(orogs_grille.items()):
            lats, lons = axes_depuis_orographie(o3d, DOMAINES.get(nom_dom))
            g = Grille(ref, steps, lats, lons, o3d.z, domaine=nom_dom)
            grilles[nom_dom] = (g, o3d)
            crier(f"▶ produit B [{nom_dom}] : grille {len(lats)}×{len(lons)} × "
                  f"{g.h0025.shape[0]} paramètres × {g.h0025.shape[1]} niveaux "
                  f"× {len(steps)} échéances = {g.octets() / 1e6:.1f} Mo en "
                  f"mémoire (float16)")
    par_nom_0025 = {p["nom"]: p for p in PARAMS_0025}
    par_nom_001 = {p["nom"]: p for p in PARAMS_001}
    par_nom_iso = {p["nom"]: p for p in PARAMS_ISO}
    par_nom_iso[PARAM_ALTITUDE["nom"]] = PARAM_ALTITUDE
    par_nom_surf = {p["nom"]: p for p in PARAMS_SURFACE}
    par_nom_surf[PARAM_PRESSION_SOL["nom"]] = PARAM_PRESSION_SOL
    steps_set = set(steps)

    idx = {}
    for grille, orog in paire_orog.items():
        indices, hors = index_plats(orog.meta, balises)
        if hors:
            crier(f"  ⚠️ {len(hors)} balises hors grille {grille} : "
                  f"{hors[:5]}{'…' if len(hors) > 5 else ''}")
        idx[grille] = indices

    octets = pic_disque = 0
    compte = dict(fichiers=0, messages=0, decodes=0, incidents=0,
                  incidents_vus=[])
    t_dl = t_parse = 0.0

    for grille, paquet in PAQUETS:
        fichiers = fichiers_du_paquet(ref, grille, paquet, steps)
        if limite_fichiers:
            fichiers = fichiers[:limite_fichiers]
        total_mo = sum(t for _, t in fichiers) / 1e6
        crier(f"── {grille}/{paquet} : {len(fichiers)} fichiers, "
              f"{total_mo:.0f} Mo")
        # ⚠️ APPARTENANCE, pas égalité : `IP2` rejoint `IP1` le 12/08 et
        # les deux passent par la branche isobare. Un `== PAQUET_ISOBARES`
        # oublié ici enverrait `cc` dans la branche des niveaux HAUTEUR,
        # où son `typeOfLevel = isobaricInhPa` ne correspondrait à rien :
        # les messages seraient ignorés en silence et `cc` resterait NaN.
        isobare = paquet in PAQUETS_ISOBARES
        surface = paquet in PAQUETS_SURFACE and grille == GRID_3D
        veut = (filtre_iso(paquet) if isobare
                else filtre_surface(paquet) if surface
                else filtre_0025(paquet) if grille == GRID_3D
                else filtre_001(paquet))
        table = (par_nom_iso if isobare
                 else par_nom_surf if surface
                 else par_nom_0025 if grille == GRID_3D else par_nom_001)
        orog = paire_orog[grille]
        indices = idx[grille]
        valides = indices >= 0

        for cle, taille in fichiers:
            t0 = time.time()
            chemin = download_tmp(cle, journal=None)
            t_dl += time.time() - t0
            pic_disque = max(pic_disque, os.path.getsize(chemin))
            octets += os.path.getsize(chemin)
            try:
                def sur_champ(k, step, values, meta, _g=grille, _o=orog,
                              _i=indices, _v=valides, _t=table, _iso=isobare,
                              _surf=surface):
                    verifier_grille(_o.meta, meta, f"{_g}/{paquet}")
                    nom, niveau = k
                    # ⛔⛔ UN ZÉRO PUBLIÉ N'EST PAS UNE DONNÉE.
                    # `cc` EXISTE à l'échéance 0 — le message est là, il
                    # se décode, et il vaut exactement 0 sur les 24
                    # niveaux (`bitsPerValue = 0`, champ constant, mesuré
                    # sur les runs 15 Z et 12 Z du 12/08). Au même instant
                    # `clwc` n'est pas nul : ce n'est donc pas la météo,
                    # c'est l'analyse qui ne diagnostique pas la
                    # nébulosité. L'archiver tel quel ferait dire au
                    # produit « ciel clair partout » à l'échéance que le
                    # pilote regarde EN PREMIER — précisément le mensonge
                    # que ce lot existe pour empêcher.
                    # On ne pose rien : le tableau garde son NaN, et
                    # `remplissage_par_parametre` le montrera, comme il
                    # montre déjà le trou de la TKE.
                    # ⓘ Pour la TKE la règle est un no-op — ses messages
                    # n'existent pas du tout à τ = 0 — mais elle est
                    # écrite une fois pour les deux, parce que la
                    # prochaine fois on ne saura pas d'avance de quelle
                    # façon le champ manque.
                    if step == 0 and _t[nom].get("absent_a_tau0"):
                        return
                    # ── La surface : produit B UNIQUEMENT ─────────────
                    # ⛔ Le produit A n'en veut pas, et ce n'est pas un
                    # oubli : c'est une archive DÉFINITIVE dont le format
                    # engage pour des années, alors que ces champs
                    # servent la ligne de surface d'une seule vue. On ne
                    # grave pas un besoin d'écran dans le perpétuel.
                    if _surf:
                        dt_s = (np.float32
                                if nom == PARAM_PRESSION_SOL["nom"]
                                else np.float16)
                        for _g_dom, _o_dom in grilles.values():
                            if _g_dom.accepte_surface(nom, step):
                                _g_dom.poser_surface(
                                    nom, step,
                                    quantifier(decouper(values, meta, _o_dom),
                                               _t[nom], dtype=dt_s))
                        return
                    brut = np.full(len(_i), np.nan)
                    brut[_v] = np.asarray(values)[_i[_v]]
                    if not _iso:
                        col.poser(_g, nom, niveau, step,
                                  quantifier(brut, _t[nom]))
                        # ── produit B, sur le MÊME message décodé ─────
                        # ⚠️⚠️ `_g == GRID_3D` N'EST PAS REDONDANT AVEC
                        # `accepte()`, ET L'OUBLIER CASSE EN SILENCE. La
                        # maille fine porte elle aussi des champs nommés
                        # `u` et `v`, aux niveaux 10, 20, 50 et 100 m —
                        # QUATRE NIVEAUX QUI SONT TOUS DANS LES 25 DU
                        # 0,025°. `accepte()` les accepterait donc, et on
                        # poserait une fenêtre 0,01° de 151×211 dans un
                        # tableau de 61×85. Pire : `parcourir` avale les
                        # exceptions de ce callback, donc rien ne
                        # s'allumerait — la grille se remplirait de
                        # travers ou pas du tout, sans un mot.
                        if _g == GRID_3D:
                            # ⚠️ La découpe est refaite POUR CHAQUE
                            # DOMAINE, depuis le champ France entière —
                            # jamais depuis la fenêtre d'un autre
                            # domaine. Les deux boîtes ne se recouvrent
                            # pas, mais surtout `decouper` s'appuie sur
                            # `orog.j0/i0`, qui est propre à l'artefact :
                            # réutiliser la découpe alpine pour les
                            # Pyrénées donnerait un tableau de la bonne
                            # FORME et du mauvais contenu.
                            for _g_dom, _o_dom in grilles.values():
                                if _g_dom.accepte(nom, niveau, step):
                                    _g_dom.poser(
                                        nom, niveau, step,
                                        quantifier(
                                            decouper(values, meta, _o_dom),
                                            _t[nom]))
                        return
                    # ⚠️⚠️ PLUS AUCUNE DIVISION PAR `G` ICI, ET C'EST
                    # DÉLIBÉRÉ. `z` reste un GÉOPOTENTIEL en m²/s² — mais
                    # la conversion vit désormais dans le `facteur` de
                    # `PARAM_ALTITUDE`, donc dans `quantifier()`, donc au
                    # même endroit pour le produit A et le produit B.
                    # Deux raisons, la première mesurée le 12/08 :
                    #  · divisée AVANT le contrôle, la sentinelle 9 999
                    #    devenait 1 019,6 m et passait pour une altitude ;
                    #  · le produit B aurait eu besoin de sa PROPRE
                    #    division, soit une seconde écriture de la même
                    #    conversion — exactement ce qu'on voulait éviter.
                    # ⛔ Remettre un `/ G` ici diviserait DEUX FOIS : 331 m
                    # à 700 hPa au lieu de 3 240, plausible au premier
                    # coup d'œil. `test_colonnes.py` rejoue ce chemin.
                    dtype = np.float32 if nom == PARAM_ALTITUDE["nom"] else np.float16
                    col.poser_isobare(nom, niveau, step,
                                      quantifier(brut, _t[nom], dtype=dtype))

                    # ── produit B, sur le MÊME message décodé ──────────
                    # Même geste que pour les niveaux hauteur vingt
                    # lignes plus haut, et même piège évité : la découpe
                    # est refaite POUR CHAQUE DOMAINE depuis le champ
                    # France entière, jamais depuis la fenêtre d'un
                    # autre. ⓘ Les isobares n'existent qu'en 0,025°, donc
                    # pas de garde `_g == GRID_3D` à ajouter — mais
                    # `accepte_isobare()` filtre quand même le niveau,
                    # parce que `NIVEAUX_P` pourrait un jour ne pas être
                    # le même des deux côtés.
                    for _g_dom, _o_dom in grilles.values():
                        if _g_dom.accepte_isobare(nom, niveau, step):
                            _g_dom.poser_isobare(
                                nom, niveau, step,
                                quantifier(decouper(values, meta, _o_dom),
                                           _t[nom], dtype=dtype))

                t1 = time.time()
                lus, dec, incidents = parcourir(chemin, veut, sur_champ,
                                                steps_set)
                t_parse += time.time() - t1
                compte["messages"] += lus
                compte["decodes"] += dec
                compte["fichiers"] += 1
                compte["incidents"] += len(incidents)
                for m in incidents:
                    if m not in compte["incidents_vus"]:
                        compte["incidents_vus"].append(m)
            finally:
                # ⚠️ UN SEUL FICHIER SUR LE DISQUE À LA FOIS. Le `finally`
                # n'est pas une politesse : une exception qui laisserait
                # traîner un bundle de 818 Mo remplirait le runner en
                # quelques échéances.
                os.unlink(chemin)
            crier(f"    {cle.split('/')[-1][-28:]} · {taille / 1e6:.0f} Mo · "
                  f"{dec} champs retenus sur {lus}")

    # ⛔⛔ LA DÉ-ACCUMULATION, UNE FOIS, ICI — ET PAS AILLEURS.
    # `tp` et `ssrd` arrivent CUMULÉS depuis le début du run (stepRange
    # 0-1, 0-2, 0-3…, mesuré le 13/08). Les servir tels quels donnerait
    # une pluie horaire qui ne décroît jamais : une courbe lisse,
    # croissante, et fausse. La différence se fait sur le tableau
    # COMPLET, quand toutes les échéances sont arrivées — au fil des
    # messages, il faudrait espérer que l'échéance précédente soit déjà
    # là, et l'espoir n'est pas un contrôle.
    for _g_dom, _o_dom in grilles.values():
        _g_dom.deaccumuler()

    return (col, {d: g for d, (g, _) in grilles.items()},
            dict(octets=octets, pic_disque=pic_disque, t_dl=t_dl,
                 t_parse=t_parse, **compte))


# ══════════════════════════════════════════════════════════════════════
#  Publication du produit B — APRÈS le produit A, et sans jamais
#  mettre le produit A en danger
# ══════════════════════════════════════════════════════════════════════
def publier_grilles(paquets, ref, crier=journal_horodate):
    """Monte les grilles sur R2, met l'index à jour, purge les runs sortis.

    `paquets` : [(domaine, Grille, manifeste)] — un par domaine de
    production.

    ⚠️⚠️ CETTE FONCTION NE DOIT JAMAIS FAIRE ÉCHOUER LE RUN, ET C'EST LA
    RAISON D'ÊTRE DE L'`except` LARGE QUI L'ENVELOPPE. Le produit A est
    une archive DÉFINITIVE, déjà écrite quand on arrive ici ; le produit B
    est jetable et sera régénéré au run suivant, une heure ou trois plus
    tard. Faire tomber le run — donc le voyant healthchecks, donc
    l'alerte — pour un produit qui se répare tout seul serait apprendre
    à ignorer le voyant. C'est le même arbitrage que la purge du 30/07.

    ⓘ En contrepartie, l'échec est CRIÉ et compté : un produit B qui ne
    monte plus doit se lire dans les logs, même si le run est vert.

    ── CE QUI A CHANGÉ LE 12/08, ET DANS QUEL ORDRE ──────────────────
    ⛔ L'INDEX EST LU UNE FOIS ET ÉCRIT UNE FOIS POUR TOUS LES DOMAINES.
    Le boucler par domaine coûterait un `GetObject` et deux `PutObject`
    de plus par domaine — mais surtout, deux passes sur le même index à
    clé fixe ouvriraient une fenêtre où l'index publié ne décrit qu'une
    partie de ce qui est en ligne. Sans `ListObjects`, cette fenêtre-là
    est exactement celle où un objet devient invisible.

    ⚠️ Les objets d'un domaine sont écrits AVANT que l'index ne le
    référence, et l'index précède la purge : l'ordre en cinq temps de
    `grille.py` est conservé mot pour mot, seul son périmètre s'élargit.
    """
    from grille import (CLE_INDEX, INDEX_VIDE, RETENTION_RUNS,  # noqa: PLC0415
                        cle_colonnes, cle_echeance, cles_du_run, index_apres,
                        index_apres_purge, prefixe_run, verifier_prefixe)
    from storage import (CACHE_IMMUABLE, CACHE_REECRIT,  # noqa: PLC0415
                         Storage, verifier_dimensionnement)

    if not paquets:
        return False

    # ── Le chiffrage, AVANT la première écriture ──────────────────────
    # ⚠️ Un objet par échéance et par domaine, plus le manifeste, plus
    # `zsol`, plus — depuis le 12/08 — `colonnes.bin`. C'est le poste qui
    # a été TRANCHÉ deux fois (voir `grille.cles_du_run` puis
    # `grille.cle_colonnes`) et c'est celui qu'il faut voir bouger si
    # quelqu'un remonte `MAX_HOURS` ou ajoute un domaine : à 25 échéances
    # et 2 domaines on est à 58 objets par run ; à 4 domaines et 48
    # échéances on serait à 204, et la ligne journalisée le dirait AVANT
    # la facture.
    #
    # ⚠️⚠️ `octets()` NE SUFFIT PLUS À CHIFFRER LE STOCKAGE. Il compte les
    # tableaux EN MÉMOIRE ; or `colonnes.bin` republie exactement les
    # mêmes valeurs sur l'axe orthogonal. Ce qui monte sur R2 fait donc
    # ~2× ce que la grille pèse, plus l'alignement — mesuré, pas
    # supposé : on somme les tailles RÉELLES des objets qu'on s'apprête à
    # écrire. Sous-estimer ici ferait passer le garde-fou pour vert la
    # veille du jour où il devait crier.
    objets = sum(len(cles_du_run(ref, d, g.steps)) + 1 for d, g, _ in paquets)
    mo = sum(g.octets_publies() / 1e6 for _, g, _ in paquets)
    plafond = verifier_dimensionnement(
        "agrume-grille", objets_par_run=objets + 2, runs_par_jour=8,
        mo_par_run=round(mo * RETENTION_RUNS, 2))
    store = Storage("agrume-grille", "AGRUME_BUCKET", "wind-grid", plafond)

    # ── 1. l'index précédent — 1 GetObject, Class B ───────────────────
    index = store.get_json(CLE_INDEX) or dict(INDEX_VIDE)
    legs = [e for e in (index.get("runs") or []) if not e.get("domaine")]
    crier(f"▶ index : {len(index.get('runs') or [])} entrée(s) en ligne"
          + (f", dont {len(legs)} à l'ANCIEN format (sans domaine) — elles "
             f"partent à la purge, pas à l'oubli" if legs else "")
          + (f", {len(index.get('restes') or [])} reste(s) à supprimer"
             if index.get("restes") else ""))

    # ── 2. les objets de chaque domaine ───────────────────────────────
    a_supprimer, nouveau = [], index
    for dom, gr, manifeste in paquets:
        base = prefixe_run(ref, dom)
        for step in gr.steps:
            store.put(cle_echeance(ref, dom, step), gr.tampon_echeance(step),
                      cache_control=CACHE_IMMUABLE,
                      content_type="application/octet-stream")
        # ⚠️ `zsol` N'EST PAS DANS LES TAMPONS D'ÉCHÉANCE, et ce n'est pas
        # un oubli : il ne dépend pas de l'échéance. Le répéter 25 fois
        # coûterait 525 Ko par run et par domaine pour 21 Ko d'information.
        # Sans lui en revanche le client ne peut RIEN faire des tampons —
        # les niveaux sont AGL.
        store.put(f"{base}/zsol.bin", gr.tampon_zsol(),
                  cache_control=CACHE_IMMUABLE,
                  content_type="application/octet-stream")
        # ── L'objet « colonnes », pour la vue de coupe ─────────────────
        # ⚠️ ÉCRIT AVANT LE MANIFESTE, comme les tampons d'échéance : le
        # manifeste est ce qui rend un run lisible, il ne doit jamais
        # décrire un objet qui n'est pas encore là. ⓘ C'est le plus gros
        # objet du produit (57,8 Mo sur les Alpes, 93,7 sur les
        # Pyrénées) : s'il doit échouer, autant que ce soit avant.
        store.put(cle_colonnes(ref, dom), gr.tampon_colonnes(),
                  cache_control=CACHE_IMMUABLE,
                  content_type="application/octet-stream")
        store.put(f"{base}/manifest.json",
                  json.dumps(manifeste, ensure_ascii=False).encode(),
                  cache_control=CACHE_IMMUABLE)
        cles = cles_du_run(ref, dom, gr.steps) + [f"{base}/zsol.bin"]
        nouveau, sup = index_apres(nouveau, ref, dom, cles)
        a_supprimer += [c for c in sup if c not in a_supprimer]
        crier(f"▶ produit B [{dom}] : {len(gr.steps)} tampon(s) + colonnes + "
              f"zsol + manifeste, {gr.octets_publies() / 1e6:.1f} Mo publiés "
              f"({gr.octets() / 1e6:.1f} Mo en mémoire)")

    # ── 3. l'index NOUVEAU, avant toute suppression ───────────────────
    nouveau = dict(nouveau, restes=list(a_supprimer))
    nouveau["ecrit_le"] = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    store.put(CLE_INDEX, json.dumps(nouveau, ensure_ascii=False).encode(),
              cache_control=CACHE_REECRIT)

    # ── 4. la purge ───────────────────────────────────────────────────
    echecs = []
    if a_supprimer:
        # ⚠️ Le garde-fou de préfixe LÈVE plutôt que de purger « ce qui
        # est légitime » : le produit A vit dans le même bucket, sous
        # `agrume/colonnes/`, et il est irremplaçable.
        verifier_prefixe(a_supprimer)
        for c in a_supprimer:
            if not store.delete(c):
                echecs.append(c)
        crier(f"▶ purge : {len(a_supprimer) - len(echecs)}/"
              f"{len(a_supprimer)} objet(s) supprimé(s)"
              + (f" — ⚠️ {len(echecs)} échec(s), réessayés au run suivant"
                 if echecs else ""))
    else:
        crier("▶ purge : rien à supprimer "
              f"(moins de {RETENTION_RUNS} runs en ligne par domaine)")

    # ── 5. l'index FINAL : `restes` = ce qui a échoué ─────────────────
    if nouveau.get("restes") != echecs:
        store.put(CLE_INDEX,
                  json.dumps(index_apres_purge(nouveau, echecs),
                             ensure_ascii=False).encode(),
                  cache_control=CACHE_REECRIT)
    store.bilan()
    return True


# ══════════════════════════════════════════════════════════════════════
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    # ⚠️ PAR DÉFAUT, L'AXE DES BALISES VIENT DE L'ARTEFACT COMMITÉ, pas
    # d'un fichier du VPS ni d'un appel réseau. Deux raisons :
    #   • l'archive est disposée en (balise, …) : l'axe doit être STABLE
    #     d'un run à l'autre, sinon empiler deux runs demande de remapper
    #     des indices — et ça ne se verrait qu'après des semaines ;
    #   • l'ingestion tourne sur GitHub Actions, qui n'a accès ni au VPS
    #     ni à /var/lib/bw-model-verif. Un artefact commité rend le run
    #     autonome ET reproductible : rejouer un run d'il y a un mois
    #     donne le même axe qu'à l'époque.
    # `--stations` reste là pour un rejeu ponctuel sur une autre liste.
    p.add_argument("--stations", default=None,
                   help="référentiel alternatif (défaut : l'axe figé de "
                        "agrume/data/balises-nord-alpes.json)")
    p.add_argument("--suspectes", default=None,
                   help="fichier JSON [ids] des balises position_suspecte "
                        "(elles sont MARQUÉES, pas retirées)")
    p.add_argument("--max-heures", type=int, default=MAX_HOURS)
    p.add_argument("--limite-fichiers", type=int, default=None,
                   help="banc d'essai : n premiers fichiers par paquet")
    p.add_argument("--sans-ecriture", action="store_true",
                   help="ingère et chiffre, n'écrit rien sur R2")
    # ⚠️ Le produit B se DÉSACTIVE, il ne se réactive pas : il est là par
    # défaut parce qu'il ne coûte ni téléchargement ni minute de runner.
    # Un drapeau `--avec-grille` aurait fait de la gratuité une option
    # qu'on oublie d'activer.
    p.add_argument("--sans-grille", action="store_true",
                   help="n'ingère PAS le produit B (grille 3D du domaine)")
    p.add_argument("--sortie", default=None,
                   help="dossier local où déposer npz + manifeste")
    a = p.parse_args(argv)

    t_debut = time.time()
    try:
        # ⚠️ 12/08 — DEUX DOMAINES DE PRODUCTION, ET UN SEUL PRODUIT B.
        # `paire` reste STRICTEMENT le Nord-Alpes : c'est elle qui est
        # passée à `ingerer()`, donc c'est elle qui décide de la fenêtre
        # du produit B et des axes de la grille 3D. Le second domaine
        # n'entre que dans le SOL des balises, plus bas. Confondre les
        # deux ferait grossir le produit B sans que personne l'ait décidé
        # — et le produit B est le seul objet du lot dont le budget R2 se
        # discute.
        artefacts, sans_artefact = charger_artefacts()
        paire, man_orog = artefacts["nord-alpes"]
        journal_horodate(f"▶ orographie figée du run {man_orog['run_source']} "
                         f"({', '.join(sorted(paire))}) — domaines : "
                         f"{', '.join(sorted(artefacts))}")
        if sans_artefact:
            journal_horodate(
                f"  ⚠️ domaine(s) SANS orographie figée : "
                f"{', '.join(sans_artefact)} — leurs balises seront "
                f"archivées SANS SOL. Lancer "
                f"`python3 agrume/freeze_orographie.py --domaine <nom>`.")

        suspectes = (json.loads(Path(a.suspectes).read_text(encoding="utf-8"))
                     if a.suspectes else [])
        if a.stations:
            stations = json.loads(Path(a.stations).read_text(encoding="utf-8"))
            balises = balises_du_domaine(stations, suspectes)
            origine = f"référentiel {Path(a.stations).name} " \
                      f"({len(stations)} balises)"
        else:
            figees, man_bal = charger_balises()
            balises = balises_du_domaine(figees, suspectes)
            origine = f"axe figé du {man_bal['ecrit_le'][:10]}"
        if not balises:
            raise Abort("aucune balise ne tombe dans un domaine de production")
        marquees = sum(1 for b in balises if b["position_suspecte"])
        journal_horodate(f"▶ {len(balises)} balises — {origine}"
                         + (f", dont {marquees} à position suspecte (marquées, "
                            f"pas retirées)" if marquees else ""))

        # Le sol du modèle sous chaque balise, écrit une fois pour toutes
        # dans le manifeste : sans lui, un niveau « 500 m » ne veut rien
        # dire, et l'écart au sol réel ne peut pas être affiché.
        # ⚠️ On balaie TOUS les domaines, et `z_at` rend None hors de sa
        # fenêtre : une balise reçoit donc le sol de l'artefact qui la
        # contient, sans qu'on ait à savoir lequel. `domaine_de()` dirait
        # la même chose ; le faire par `z_at` évite qu'un désaccord entre
        # les bornes déclarées et la fenêtre réellement découpée passe
        # inaperçu — ici c'est le fichier qui décide, pas la constante.
        par_domaine = {}
        for b in balises:
            trouve = None
            for nom, (p_dom, _) in artefacts.items():
                for g, o in p_dom.items():
                    z = o.z_at(b["lat"], b["lon"])
                    if z is not None:
                        b[f"z_{g}"] = round(z, 1)
                        trouve = nom
                    else:
                        b.setdefault(f"z_{g}", None)
            b["domaine"] = trouve
            par_domaine[trouve] = par_domaine.get(trouve, 0) + 1
        journal_horodate("▶ sol par domaine : " + ", ".join(
            f"{n or 'AUCUN'} {c}" for n, c in sorted(
                par_domaine.items(), key=lambda kv: (kv[0] is None, kv[0]))))

        # ── Le sol des balises HORS de toute boîte ────────────────────
        # ⚠️ Même arbitrage que pour les radiosondages juste en dessous :
        # l'absence de cet artefact NE DOIT PAS arrêter l'ingestion. Ces
        # balises perdent leur plancher, les 180 autres colonnes n'ont
        # rien à voir là-dedans. On crie, on continue, et le manifeste
        # dira lesquelles sont sans sol.
        isolees = [b for b in balises if b.get("hors_domaine")]
        isolees_manifeste = None
        if isolees:
            try:
                par_bal, man_iso = charger_artefact_isolees()
                isolees_manifeste = dict(
                    run_source=man_iso["run_source"],
                    demi_fenetre_deg=man_iso["demi_fenetre_deg"],
                    n=man_iso["n"])
                pose = 0
                for b in isolees:
                    for g, o in par_bal.get(str(b["id"]), {}).items():
                        z = o.z_at(b["lat"], b["lon"])
                        if z is not None:
                            b[f"z_{g}"] = round(z, 1)
                            pose += 1
                journal_horodate(
                    f"▶ {len(isolees)} balise(s) hors boîte — sol lu dans "
                    f"l'artefact des balises isolées du run "
                    f"{man_iso['run_source']} ({pose} valeurs posées)")
            except Abort as e:
                journal_horodate(f"  ⚠️ balises hors boîte SANS SOL : {e}")

        # ── Le sol des points de RADIOSONDAGE ─────────────────────────
        # ⚠️ Ils sont hors du domaine, donc hors de l'orographie de
        # PRODUCTION : `z_at` y renvoie None et leur colonne serait
        # extraite sans plancher, donc inexploitable. Leur sol vient du
        # second artefact, celui de vérification — et de lui seul.
        #
        # ⚠️ Son absence n'ARRÊTE PAS l'ingestion. C'est un appareil de
        # mesure, pas le produit : casser la production de 125 colonnes
        # parce qu'un artefact de vérification manque serait le mauvais
        # arbitrage. On crie, on continue, et le manifeste dira que ces
        # points n'ont pas de sol.
        rs = [b for b in balises if b.get("source") == "radiosondage"]
        verif_manifeste = None
        if rs:
            try:
                par_station, man_verif = charger_artefact_verif()
                verif_manifeste = dict(
                    run_source=man_verif["run_source"],
                    demi_fenetre_deg=man_verif["demi_fenetre_deg"])
                for b in rs:
                    wmo = str(b["id"]).replace("RS-", "")
                    for g, o in par_station.get(wmo, {}).items():
                        z = o.z_at(b["lat"], b["lon"])
                        b[f"z_{g}"] = None if z is None else round(z, 1)
                journal_horodate(
                    f"▶ {len(rs)} point(s) de radiosondage — sol lu dans "
                    f"l'artefact de vérification du run "
                    f"{man_verif['run_source']}")
            except Abort as e:
                journal_horodate(f"  ⚠️ points de radiosondage SANS SOL : {e}")

        ref, run, steps = choisir_run(a.max_heures)
        # ⚠️ 12/08 — LE PRODUIT B COUVRE MAINTENANT TOUS LES DOMAINES QUI
        # ONT UNE OROGRAPHIE FIGÉE, pas seulement `nord-alpes`. Le
        # commentaire qui précède `charger_artefacts()` disait « DEUX
        # DOMAINES DE PRODUCTION, ET UN SEUL PRODUIT B » et redoutait de
        # « faire grossir le produit B sans que personne l'ait décidé ».
        # C'est décidé, chiffré et arbitré le 12/08 : ~254 Mo résidents
        # pour les deux domaines sur un palier de 10 Go, et le
        # dimensionnement est journalisé à chaque run.
        # ⛔ `paire` reste STRICTEMENT le Nord-Alpes : c'est le produit A
        # qu'elle sert, et lui n'a pas changé.
        orogs_b = {d: pr[GRID_3D] for d, (pr, _m) in artefacts.items()
                   if GRID_3D in pr}
        col, grilles, mesures = ingerer(ref, run, steps, balises, paire,
                                        limite_fichiers=a.limite_fichiers,
                                        avec_grille=not a.sans_grille,
                                        orogs_grille=orogs_b)
    except Abort as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2

    duree_min = (time.time() - t_debut) / 60
    remp = col.remplissage()
    manifeste = col.manifeste(dict(
        genere_le=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        orographie=dict(run_source=man_orog["run_source"],
                        sha256={g: man_orog["grilles"][g]["sha256"][:16]
                                for g in man_orog["grilles"]}),
        # ⚠️ Publié pour qu'on sache, en relisant une archive, si les
        # points de radiosondage avaient un sol ce jour-là — et lequel.
        orographie_radiosondages=verif_manifeste,
        orographie_balises_isolees=isolees_manifeste,
        mesures=dict(
            duree_min=round(duree_min, 2),
            octets_telecharges=mesures["octets"],
            pic_disque_mo=round(mesures["pic_disque"] / 1e6, 1),
            fichiers=mesures["fichiers"],
            messages_balayes=mesures["messages"],
            messages_decodes=mesures["decodes"],
            secondes_reseau=round(mesures["t_dl"], 1),
            secondes_parsing=round(mesures["t_parse"], 1),
            # ⚠️ Publié dans le manifeste, pas seulement journalisé : un
            # log de runner disparaît au bout de 90 jours, une archive
            # définitive se relit dans cinq ans. Si un run a perdu des
            # champs en silence, il faut que l'archive elle-même le dise.
            incidents=mesures["incidents"],
            debit_mo_s=round(mesures["octets"] / 1e6 / max(mesures["t_dl"], 1e-6), 1))))

    print()
    journal_horodate("┌─ BILAN DU RUN ───────────────────────────────────")
    journal_horodate(f"│ run                 : {ref}, {len(steps)} échéances")
    journal_horodate(f"│ colonnes            : {len(balises)} balises × "
                     f"{col.c0025.shape[1]}×{col.c0025.shape[2]} (0025) + "
                     f"{col.c001.shape[1]}×{col.c001.shape[2]} (001)")
    journal_horodate(f"│ remplissage         : 0025 {remp[GRID_3D] * 100:.1f} % · "
                     f"001 {remp[GRID_FINE] * 100:.1f} % · "
                     f"isobares {remp['isobares'] * 100:.1f} % · "
                     f"altitude iso {remp['altitude_iso'] * 100:.1f} %")
    detail = col.remplissage_par_parametre()
    journal_horodate("│   par paramètre     : "
                     + " · ".join(f"{n} {v * 100:.0f}%"
                                  for n, v in detail[GRID_3D].items())
                     + "  |  fine " + " · ".join(
                         f"{n} {v * 100:.0f}%" for n, v in detail[GRID_FINE].items()))
    journal_horodate("│   isobares          : "
                     + " · ".join(f"{n} {v * 100:.0f}%"
                                  for n, v in detail["isobares"].items()))
    if detail[GRID_3D].get("tke", 1.0) < 1.0 and steps and steps[0] == 0:
        journal_horodate("│   ⓘ la TKE manque à l'échéance 0 — MESURÉ le "
                         "10/08, ce n'est pas un défaut d'ingestion")
    journal_horodate(f"│ téléchargé          : {mesures['octets'] / 1e9:.2f} Go "
                     f"en {mesures['t_dl'] / 60:.1f} min "
                     f"({mesures['octets'] / 1e6 / max(mesures['t_dl'], 1e-6):.1f} Mo/s)")
    journal_horodate(f"│ parsing             : {mesures['t_parse']:.0f} s pour "
                     f"{mesures['decodes']} champs décodés sur "
                     f"{mesures['messages']} balayés")
    journal_horodate(f"│ ⚠️ pic disque        : "
                     f"{mesures['pic_disque'] / 1e6:.0f} Mo "
                     f"(un fichier à la fois ; plafond du lot "
                     f"{PLAFOND_DISQUE_GO:.0f} Go)")
    for dom in sorted(grilles):
        gr = grilles[dom]
        journal_horodate(f"│ produit B [{dom}] : "
                         f"{gr.h0025.shape[3]}×{gr.h0025.shape[4]} points × "
                         f"{gr.h0025.shape[1]} niveaux × {len(steps)} "
                         f"échéances · remplissage "
                         f"{gr.remplissage() * 100:.1f} %")
        journal_horodate("│   par paramètre     : "
                         + " · ".join(f"{n} {v * 100:.0f}%" for n, v
                                      in gr.remplissage_par_parametre().items()))
    journal_horodate(f"│ durée totale        : {duree_min:.1f} min "
                     f"(alerte au-delà de {ALERTE_DUREE_MIN})")
    # ⚠️ Un incident n'est pas fatal, mais il ne doit pas être muet — cf.
    # `parcourir`. Zéro incident est le cas normal ; toute autre valeur
    # veut dire que des champs ont été perdus sans qu'on sache lesquels.
    if mesures["incidents"]:
        journal_horodate(f"│ ⚠️ INCIDENTS         : {mesures['incidents']} "
                         f"message(s) ont levé pendant le traitement")
        for m in mesures["incidents_vus"][:3]:
            journal_horodate(f"│     {m[:90]}")
    journal_horodate("└──────────────────────────────────────────────────")
    if duree_min > ALERTE_DUREE_MIN:
        print(f"⚠️ ALERTE DURÉE : {duree_min:.1f} min > {ALERTE_DUREE_MIN} min "
              f"— la moitié du timeout GitHub. Quelque chose a changé.",
              file=sys.stderr)
    if mesures["pic_disque"] / 1e9 > PLAFOND_DISQUE_GO:
        print(f"⚠️ ALERTE DISQUE : pic à "
              f"{mesures['pic_disque'] / 1e9:.1f} Go", file=sys.stderr)

    dossier = Path(a.sortie) if a.sortie else Path(".")
    dossier.mkdir(parents=True, exist_ok=True)
    p_npz = dossier / f"agrume-colonnes-{ref.replace(':', '')}.npz"
    p_man = dossier / f"agrume-colonnes-{ref.replace(':', '')}.json"
    col.ecrire_npz(p_npz)
    p_man.write_text(json.dumps(manifeste, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")
    journal_horodate(f"▶ {p_npz.name} : {p_npz.stat().st_size / 1024:.0f} Ko · "
                     f"{p_man.name} : {p_man.stat().st_size / 1024:.0f} Ko")

    # ── Le produit B, écrit localement lui aussi ──────────────────────
    # ⚠️ Écrit AVANT le test `--sans-ecriture` : c'est ce qui permet de
    # MESURER la taille réelle de la grille sans rien monter sur R2. Le
    # §4.1 annonce 32 Mo/run ; ce chiffre venait d'une extrapolation, et
    # il n'a de valeur que confronté au fichier produit.
    paquets = []
    for dom in sorted(grilles):
        g = grilles[dom]
        # ⚠️ Le sha de l'orographie publié est celui du domaine CONCERNÉ.
        # Publier celui des Alpes dans le manifeste pyrénéen ferait
        # croire à un consommateur que sa grille repose sur un sol
        # qu'elle n'a jamais vu — et le manifeste est justement ce qui
        # permet de rejouer un run à l'identique.
        man_dom = (artefacts.get(dom) or (None, man_orog))[1]
        man_grille = g.manifeste(dict(
            genere_le=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            orographie=dict(run_source=man_dom["run_source"],
                            sha256=man_dom["grilles"][GRID_3D]["sha256"][:16]),
            mesures=dict(duree_min=round(duree_min, 2),
                         incidents=mesures["incidents"])))
        g_npz = dossier / f"agrume-grille-{dom}-{ref.replace(':', '')}.npz"
        g_man = dossier / f"agrume-grille-{dom}-{ref.replace(':', '')}.json"
        g.ecrire_npz(g_npz)
        g_man.write_text(
            json.dumps(man_grille, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8")
        journal_horodate(
            f"▶ {g_npz.name} : {g_npz.stat().st_size / 1e6:.1f} Mo "
            f"(brut float16 : {g.octets() / 1e6:.1f} Mo · servi en "
            f"{len(g.steps)} tampons de "
            f"{len(g.tampon_echeance(g.steps[0])) / 1e6:.2f} Mo) · "
            f"{g_man.name} : {g_man.stat().st_size / 1024:.0f} Ko")
        paquets.append((dom, g, man_grille))

    if a.sans_ecriture:
        journal_horodate("▶ --sans-ecriture : rien n'est monté sur R2")
        return 0

    from storage import CACHE_IMMUABLE, Storage, verifier_dimensionnement
    # ⚠️ Deux objets par run, 8 runs/jour au pire : 480 écritures par
    # mois, soit 0,05 % du palier Class A. Le vrai poste de coût d'AGRUME
    # n'est pas l'écriture, c'est l'archive qui CROÎT — chiffrée dans le
    # manifeste à chaque run pour qu'une dérive se voie au run près.
    plafond = verifier_dimensionnement(
        "agrume-colonnes", objets_par_run=2, runs_par_jour=8,
        mo_par_run=round((p_npz.stat().st_size + p_man.stat().st_size) / 1e6, 2))
    store = Storage("agrume-colonnes", "AGRUME_BUCKET", "wind-grid", plafond)
    base = f"agrume/colonnes/{ref}"
    # ⚠️ CACHE_IMMUABLE : la clé porte le run, donc l'objet n'est JAMAIS
    # réécrit en place — contrairement aux tuiles de vent. C'est le cas
    # où un TTL long est correct (et la leçon des 23-24/07 ne s'applique
    # pas ici, elle vise les clés réécrites).
    store.put(f"{base}/colonnes.npz", p_npz.read_bytes(),
              cache_control=CACHE_IMMUABLE,
              content_type="application/octet-stream")
    store.put(f"{base}/manifest.json",
              json.dumps(manifeste, ensure_ascii=False).encode(),
              cache_control=CACHE_IMMUABLE)
    store.bilan()

    # ══════════════════════════════════════════════════════════════════
    #  LE PRODUIT B — APRÈS, ET SOUS FILET
    #
    #  ⚠️ L'ordre n'est pas un détail de mise en page : à ce point,
    #  l'archive DÉFINITIVE du produit A est écrite et hors de danger.
    #  Tout ce qui suit concerne un produit qui ne survit pas à trois
    #  runs et que le prochain réseau régénérera.
    #
    #  ⛔ D'où l'`except Exception` — le seul du fichier, et il est
    #  volontaire. Le run reste VERT si la grille échoue : faire tomber
    #  le voyant healthchecks pour un produit jetable apprendrait à
    #  l'ignorer, et le projet a déjà eu deux faux verts. L'échec est
    #  crié, il se lit dans les logs, et il ne coûte rien de plus qu'un
    #  cycle d'attente.
    # ══════════════════════════════════════════════════════════════════
    if paquets:
        try:
            publier_grilles(paquets, ref)
        except Exception as e:                              # noqa: BLE001
            print(f"⚠️ PRODUIT B NON PUBLIÉ : {type(e).__name__} — {e}\n"
                  f"   Le produit A est écrit et intact ; le run reste "
                  f"vert. La grille sera régénérée au prochain réseau. "
                  f"⚠️ Si ça se répète, ce n'est plus un incident : "
                  f"regarder les droits R2 avec "
                  f"`agrume-sonde-r2.yml`.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
