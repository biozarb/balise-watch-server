#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  verif/colonnes.py — le CONTENEUR du produit A : un run, une archive
#                                       (extrait d'agrume/ le 13/08/2026)
#
#  ⛔ POURQUOI CE FICHIER A CHANGÉ DE PAQUET — Lot J, arbitrages A1/A3.
#  Tant que l'archive était DÉFINITIVE, elle pouvait passer pour un
#  livrable du modèle. Elle ne l'est plus : depuis le 13/08 elle ne
#  survit que 7 jours (`purge.py`), et elle n'existe donc plus QUE pour
#  nourrir la confrontation. Un produit qui n'existe que pour la
#  vérification appartient au module de vérification.
#
#  ⚠️ Ce qui est resté côté modèle, et ce n'est pas arbitraire :
#  `agrume/quantification.py` porte les PARAMS_*, les plafonds, la
#  sentinelle et `quantifier()` — parce que le produit B, AROME-PI et le
#  profil en dépendent tous, et qu'aucun d'eux ne doit dépendre d'ici.
#
#  ⓘ `agrume/ingest_colonnes.py` importe ce fichier, et c'est la SEULE
#  flèche `agrume/` → `verif/` du dépôt. Elle est assumée : l'ingestion
#  est une infrastructure partagée qui remplit les deux produits dans la
#  même passe. `verif/test_separation.py` la nomme et refuse toutes les
#  autres — un banc qui autoriserait « les exceptions » en général ne
#  protégerait plus rien.
#
#  ⚠️ La DISPOSITION des tableaux est le contrat de lecture, et elle est
#  publiée dans le manifeste : elle doit survivre à ce fichier, à ce
#  paquet, et à ce déplacement. Une archive écrite avant le 13/08 se
#  relit ici sans changer d'un octet — c'est vérifié par le banc, qui
#  rejoue un manifeste de l'ancien format.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "agrume"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

from domaine import (GRID_3D, GRID_FINE, NIVEAUX_H_001,  # noqa: E402
                     NIVEAUX_H_0025, NIVEAUX_P)
from quantification import (PARAMS_001, PARAMS_0025,  # noqa: E402
                           PARAMS_ISO)

# ══════════════════════════════════════════════════════════════════════
#  Le conteneur d'archive
# ══════════════════════════════════════════════════════════════════════
class Colonnes:
    """Un run, une archive.

    Disposition des tableaux, écrite ici et dans le manifeste — c'est le
    contrat de lecture, et il doit survivre à ce fichier :

        c0025 : (balise, paramètre, niveau, échéance)  float16
                paramètres = PARAMS_0025 dans l'ordre
                niveaux    = NIVEAUX_H_0025 (25, de 10 à 3000 m/sol)
        c001  : (balise, paramètre, niveau, échéance)  float16
                paramètres = PARAMS_001 (u, v)
                niveaux    = NIVEAUX_H_001 (4 : 10, 20, 50, 100 m/sol)
        ciso  : (balise, paramètre, niveau, échéance)  float16
                paramètres = PARAMS_ISO (u, v, t, r)
                niveaux    = NIVEAUX_P (14, de 1000 à 400 hPa)
        ziso  : (balise, niveau, échéance)             **float32**
                l'ALTITUDE-MER de chaque niveau isobare, en mètres

    ⚠️ Les niveaux hauteur sont AGL — au-dessus du sol DU MODÈLE. L'axe
    altitude-mer se reconstruit avec `z_001` / `z_0025`, qui sont dans le
    manifeste, balise par balise :
        altitude_ASL = z_<maille>[balise] + niveau
    Servir un niveau sans dire à quel sol il se rapporte serait faux de
    plusieurs centaines de mètres en montagne.

    ⚠️ Les niveaux ISOBARES, eux, sont déjà absolus — mais leur altitude
    est une VARIABLE, pas une constante : « 700 hPa » n'est pas à la même
    altitude d'un point à l'autre ni d'une heure à l'autre. D'où `ziso`,
    qui est le seul tableau en float32 de toute l'archive (cf.
    `DTYPE_ALTITUDE`).
    """

    def __init__(self, run, balises, steps):
        self.run = run
        self.balises = list(balises)
        self.steps = list(steps)
        nb, ns = len(self.balises), len(self.steps)
        self.c0025 = np.full((nb, len(PARAMS_0025), len(NIVEAUX_H_0025), ns),
                             np.nan, dtype=np.float16)
        self.c001 = np.full((nb, len(PARAMS_001), len(NIVEAUX_H_001), ns),
                            np.nan, dtype=np.float16)
        self.ciso = np.full((nb, len(PARAMS_ISO), len(NIVEAUX_P), ns),
                            np.nan, dtype=np.float16)
        self.ziso = np.full((nb, len(NIVEAUX_P), ns), np.nan, dtype=np.float32)
        self.i_niveau_0025 = {n: k for k, n in enumerate(NIVEAUX_H_0025)}
        self.i_niveau_001 = {n: k for k, n in enumerate(NIVEAUX_H_001)}
        self.i_niveau_p = {n: k for k, n in enumerate(NIVEAUX_P)}
        self.i_param_0025 = {p["nom"]: k for k, p in enumerate(PARAMS_0025)}
        self.i_param_001 = {p["nom"]: k for k, p in enumerate(PARAMS_001)}
        self.i_param_iso = {p["nom"]: k for k, p in enumerate(PARAMS_ISO)}
        self.i_step = {s: k for k, s in enumerate(self.steps)}

    def accepte_echeance(self, step):
        """⛔ L'ARCHIVE ET LA GRILLE N'ONT PLUS LE MÊME HORIZON (13/08).

        Le produit B va jusqu'à `MAX_HOURS_GRILLE` (51 h), l'archive reste
        à `MAX_HOURS` (24 h) parce qu'elle est DÉFINITIVE. L'ingestion
        décode donc des messages que ce conteneur-ci ne veut pas.

        ⚠️ CE TEST N'EST PAS UNE POLITESSE. Sans lui, `poser()` lèverait
        un `KeyError` sur `self.i_step[step]` — et `parcourir()` AVALE les
        exceptions du callback. La grille, qui se remplit dans le même
        `sur_champ` juste après, n'aurait jamais reçu ces échéances-là.
        On aurait donc perdu exactement ce que la rallonge vient chercher,
        en silence, sur un chemin où rien ne s'allume.
        """
        return step in self.i_step

    def poser(self, grille, param_nom, niveau, step, valeurs_balises):
        if grille == GRID_3D:
            self.c0025[:, self.i_param_0025[param_nom],
                       self.i_niveau_0025[niveau], self.i_step[step]] = valeurs_balises
        else:
            self.c001[:, self.i_param_001[param_nom],
                      self.i_niveau_001[niveau], self.i_step[step]] = valeurs_balises

    def poser_isobare(self, param_nom, niveau, step, valeurs_balises):
        """⚠️ `zp` va dans `ziso` (float32) et NULLE PART ailleurs : c'est
        l'axe vertical, il ne passe pas par le float16."""
        if param_nom == "zp":
            self.ziso[:, self.i_niveau_p[niveau], self.i_step[step]] = valeurs_balises
        else:
            self.ciso[:, self.i_param_iso[param_nom],
                      self.i_niveau_p[niveau], self.i_step[step]] = valeurs_balises

    # ── Complétude ────────────────────────────────────────────────────
    def remplissage(self):
        """Part de cases NON vides, par maille. Un run partiel n'est pas
        une erreur (Météo-France publie progressivement) mais il doit se
        VOIR : un tableau à moitié NaN qui passe pour complet, c'est un
        score faussé des semaines plus tard."""
        def part(a):
            return float(np.isfinite(a.astype(np.float32)).mean()) if a.size else 0.0
        return {GRID_3D: part(self.c0025), GRID_FINE: part(self.c001),
                "isobares": part(self.ciso), "altitude_iso": part(self.ziso)}

    def remplissage_par_parametre(self):
        """Le même compte, paramètre par paramètre — et c'est celui qui
        sert vraiment.

        ⚠️ Un remplissage global de 80 % ne dit pas si le run est
        incomplet ou si un champ manque par construction. Le 10/08, ces
        80 % venaient entièrement d'un fait mesuré et attendu : **la TKE
        n'existe pas à l'échéance 0**. Sans ce détail par paramètre, on
        cherche un bug d'ingestion là où il n'y en a pas — ou pire, on
        s'habitue à un chiffre qui masquerait un vrai trou le jour venu.
        """
        def part(a):
            return round(float(np.isfinite(a.astype(np.float32)).mean()), 4)
        out = {GRID_3D: {}, GRID_FINE: {}, "isobares": {}}
        for k, p in enumerate(PARAMS_0025):
            out[GRID_3D][p["nom"]] = part(self.c0025[:, k])
        for k, p in enumerate(PARAMS_001):
            out[GRID_FINE][p["nom"]] = part(self.c001[:, k])
        for k, p in enumerate(PARAMS_ISO):
            out["isobares"][p["nom"]] = part(self.ciso[:, k])
        out["isobares"]["altitude"] = part(self.ziso)
        return out

    # ── Sérialisation ─────────────────────────────────────────────────
    def manifeste(self, extra=None):
        m = dict(
            produit="AGRUME produit A — colonnes verticales aux balises",
            run=self.run,
            echeances=self.steps,
            niveaux={GRID_3D: list(NIVEAUX_H_0025),
                     GRID_FINE: list(NIVEAUX_H_001),
                     "isobares_hPa": list(NIVEAUX_P)},
            parametres={
                GRID_3D: [dict(nom=p["nom"], unite=p["unite"],
                               paquet=p["paquet"]) for p in PARAMS_0025],
                GRID_FINE: [dict(nom=p["nom"], unite=p["unite"],
                                 paquet=p["paquet"]) for p in PARAMS_001],
                "isobares": [dict(nom=p["nom"], unite=p["unite"],
                                  paquet=p["paquet"]) for p in PARAMS_ISO]},
            disposition=("(balise, parametre, niveau, echeance) en float16 ; "
                         "ziso = (balise, niveau, echeance) en float32"),
            reference_verticale=("niveaux hauteur AGL au-dessus du sol "
                                 "MODÈLE : altitude_ASL = z_<maille>[balise] "
                                 "+ niveau. Niveaux isobares déjà absolus, "
                                 "leur altitude est dans `ziso` (m, float32) "
                                 "et varie dans le temps et l'espace."),
            balises=self.balises,
            remplissage=self.remplissage(),
            remplissage_par_parametre=self.remplissage_par_parametre(),
            avertissement=(
                "Les deux mailles sont archivées SÉPARÉMENT, à leurs niveaux "
                "natifs. Le raccord 0,01°/0,025° à 100 m/sol est une décision "
                "de lecture : sa marche n'est pas encore mesurée (point 7 de "
                "la séquence du lot H). 35 m et 75 m n'existent PAS en "
                "maille fine. La TKE n'existe PAS à l'échéance 0 (mesuré) : "
                "un remplissage < 100 % sur elle seule est normal. Les "
                "niveaux isobares sous le sol du modèle sont ARCHIVÉS mais "
                "physiquement vides de sens : ils doivent être masqués à la "
                "lecture (altitude < z_<maille>[balise])."))
        if extra:
            m.update(extra)
        return m

    def ecrire_npz(self, chemin):
        np.savez_compressed(chemin, c0025=self.c0025, c001=self.c001,
                            ciso=self.ciso, ziso=self.ziso,
                            echeances=np.asarray(self.steps, dtype=np.int16))

    @staticmethod
    def lire_npz(chemin, manifeste):
        man = (json.loads(manifeste) if isinstance(manifeste, (str, bytes))
               else manifeste)
        with np.load(chemin) as z:
            c = Colonnes(man["run"], man["balises"], list(man["echeances"]))
            c.c0025 = z["c0025"]
            c.c001 = z["c001"]
            # ⚠️ Les archives écrites AVANT l'étape 5 n'ont pas d'isobares.
            # On les relit quand même, avec des tableaux vides plutôt
            # qu'une exception : une archive ancienne reste une archive
            # valide pour ce qu'elle contient, et le remplissage le dira.
            if "ciso" in z:
                c.ciso = z["ciso"]
                c.ziso = z["ziso"]
        return c, man
