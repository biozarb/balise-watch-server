#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/colonnes.py — le produit A : une colonne verticale par balise
#                                                        (10/08/2026)
#
#  C'est LE SOCLE du lot H. Tout le reste s'y appuie : le sondage
#  vertical en un point, la confrontation aux mesures des balises, et
#  plus tard l'alimentation du score. Il est archivé indéfiniment, ce qui
#  fait de son format une décision à long terme.
#
#  ── LA DÉCISION DE FORMAT QUI COMPTE : ON N'ASSEMBLE PAS À L'INGESTION ─
#
#  L'hybride du §4.1 bis dit : sous 100 m/sol la donnée existe en maille
#  fine (0,01°), au-dessus elle n'existe qu'en 0,025°. La tentation est
#  d'assembler la colonne au moment de l'ingestion — une seule colonne,
#  propre, avec la maille fine en bas. ⚠️ **On ne le fait pas**, pour une
#  raison qui n'est pas esthétique :
#
#      La marche au raccord 0,01° / 0,025° à 100 m/sol N'A PAS ÉTÉ
#      MESURÉE. C'est le point 7 de la séquence du lot et un critère
#      d'acceptation non tenu. Assembler à l'ingestion DÉTRUIRAIT la
#      donnée qui permet de la mesurer — on ne pourrait plus comparer les
#      deux mailles au même niveau, puisqu'un seul survivrait.
#
#  L'archive garde donc LES DEUX MAILLES CÔTE À CÔTE, chacune à ses
#  niveaux natifs. Le raccord est une décision de SERVICE, prise à la
#  lecture (§3.3 et §4.1 bis), pas une décision d'écriture. Le coût est
#  dérisoire : la tranche fine, c'est 2 paramètres × 4 niveaux contre
#  5 × 25 pour le reste.
#
#  ⚠️ Et les niveaux ne se recouvrent pas exactement : la maille fine
#  porte 10, 20, 50, 100 m, la maille 0,025° porte 10, 20, 35, 50, 75,
#  100 m sous la barre des 100. **35 m et 75 m n'existent PAS en maille
#  fine.** Une colonne « tout fine sous 100 m » serait donc soit trouée,
#  soit alternée d'une maille à l'autre à l'intérieur même de la tranche
#  — ce qui serait pire qu'un seul raccord franc. Une raison de plus de
#  garder les deux et de trancher à la lecture.
#
#  ── L'AUTRE DÉCISION : float16, MAIS PAS SUR N'IMPORTE QUOI ──────────
#  Le float16 divise l'archive par deux, et sur du vent en m/s sa
#  précision est très au-delà de celle du modèle. ⚠️ MAIS il n'a que
#  ~11 bits de mantisse, donc un pas RELATIF de ~0,05 % : à 300 kelvins,
#  ça fait un pas de **0,25 K**, ce qui est grossier pour une
#  température. La parade est de stocker la température en DEGRÉS
#  CELSIUS (±60 → pas de 0,03 °C) plutôt qu'en kelvins. Ce n'est pas un
#  détail cosmétique : c'est un facteur 8 sur l'erreur de quantification,
#  gratuit, et invisible si on n'y pense pas. `test_colonnes.py` mesure
#  l'erreur réelle par paramètre et échoue si elle dépasse le seuil
#  annoncé ici.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import json

import numpy as np

from domaine import (GRID_3D, GRID_FINE, NIVEAUX_P,  # noqa: F401
                     NIVEAUX_H_001, NIVEAUX_H_0025,
                     dans_domaine)


class Abort(Exception):
    pass


# ── Les paramètres archivés ───────────────────────────────────────────
# Chaque entrée : (nom AGRUME, shortName eccodes aux niveaux hauteur,
#                  shortName du champ 10 m dédié ou None, paquet, unité,
#                  décalage appliqué avant quantification)
#
# ⚠️ `u`, `v`, `ws`, `wdir` ne sont servis qu'À PARTIR DE 20 m dans
# `0025/HP1` : le niveau 10 m vient des champs DÉDIÉS `10u`/`10v`.
# `t`, `r`, `pres` sont bien sur les 25 niveaux, 10 m compris. Un code
# qui chercherait `u` à 10 m ne trouverait rien et laisserait un trou en
# bas de colonne — c'est-à-dire exactement à l'altitude de la balise.
PARAMS_0025 = (
    dict(nom="u", court="u", court_10m="10u", paquet="HP1", unite="m/s",
         decalage=0.0, tolerance=0.02),
    dict(nom="v", court="v", court_10m="10v", paquet="HP1", unite="m/s",
         decalage=0.0, tolerance=0.02),
    # ⚠️ Kelvins → Celsius AVANT float16, cf. l'en-tête. Sans ce décalage
    # le pas de quantification serait de 0,25 K.
    dict(nom="t", court="t", court_10m=None, paquet="HP1", unite="°C",
         decalage=-273.15, tolerance=0.05),
    dict(nom="r", court="r", court_10m=None, paquet="HP1", unite="%",
         decalage=0.0, tolerance=0.05),
    # TKE = énergie cinétique turbulente, le proxy de turbulence du
    # §5.2.c (rotor, rabattant). ⚠️ Elle vit dans HP2, PAS dans HP1 —
    # avec le géopotentiel. Les deux paquets pèsent presque autant l'un
    # que l'autre (5,98 et 4,11 Go par run complet).
    #
    # ⚠️⚠️ ET ELLE N'EXISTE PAS À L'ÉCHÉANCE 0. MESURÉ le 10/08 sur le
    # bundle `0025/HP2/__00H06H__` du run 03 Z : 200 messages à l'échéance
    # 0 contre 225 aux échéances 1 à 6 — exactement 25 de moins, soit un
    # paramètre × 25 niveaux, et le filtre ne retient que 150 messages de
    # TKE (6 échéances × 25 niveaux) là où il en attendait 175.
    # C'est cohérent avec la nature du champ (l'analyse ne porte pas de
    # TKE), mais ce n'est écrit nulle part dans la documentation.
    # **Conséquence : un trou permanent à τ = 0 sur la TKE, et sur elle
    # seule.** Ce n'est pas une erreur d'ingestion — le remplissage est
    # donc publié PAR PARAMÈTRE, pour qu'on voie de quoi il s'agit au
    # lieu de chercher un bug qui n'existe pas.
    dict(nom="tke", court="tke", court_10m=None, paquet="HP2", unite="m²/s²",
         decalage=0.0, tolerance=0.02, absent_a_tau0=True),
)

# La tranche fine : ce qu'on peut avoir en 0,01°, et rien de plus.
# `001/HP1` porte u/v/ws/wdir à 20, 50 et 100 m ; `001/SP1` porte les
# 10 m (`10u`/`10v`). ⛔ Aucun niveau au-dessus de 100 m n'existe dans
# cette grille : ce n'est pas un choix, c'est la donnée.
PARAMS_001 = (
    dict(nom="u", court="u", court_10m="10u", paquet="HP1", paquet_10m="SP1",
         unite="m/s", decalage=0.0, tolerance=0.02),
    dict(nom="v", court="v", court_10m="10v", paquet="HP1", paquet_10m="SP1",
         unite="m/s", decalage=0.0, tolerance=0.02),
)

# ── Les paramètres isobares ───────────────────────────────────────────
# Mêmes cinq champs que sur les niveaux hauteur, plus l'altitude — qui
# est ici une VARIABLE et non une constante : un niveau « 700 hPa » n'est
# pas à la même altitude d'un point à l'autre ni d'une heure à l'autre.
# C'est `z` qui porte l'axe vertical de toute la moitié haute du profil.
PARAMS_ISO = (
    dict(nom="u", court="u", court_10m=None, paquet="IP1", unite="m/s",
         decalage=0.0, tolerance=0.02),
    dict(nom="v", court="v", court_10m=None, paquet="IP1", unite="m/s",
         decalage=0.0, tolerance=0.02),
    dict(nom="t", court="t", court_10m=None, paquet="IP1", unite="°C",
         decalage=-273.15, tolerance=0.05),
    dict(nom="r", court="r", court_10m=None, paquet="IP1", unite="%",
         decalage=0.0, tolerance=0.05),
)

# ⚠️⚠️ L'ALTITUDE DES NIVEAUX ISOBARES EST STOCKÉE EN float32, PAS EN
# float16, ET C'EST LE MÊME PIÈGE QUE LES KELVINS EN PIRE.
#
# Le float16 a 10 bits de mantisse, donc un pas RELATIF de ~0,1 %. Entre
# 4 096 et 8 192 m, le pas vaut **4 mètres**, soit une erreur d'arrondi
# pouvant atteindre **2 m** — mesuré, pas déduit : `test_colonnes.py`
# donne 2,00 m d'erreur maximale sur 20 000 tirages entre 0 et 7 500 m,
# contre 0,24 millimètre en float32.
#
# ⚠️ Deux mètres, ce n'est pas énorme dans l'absolu — mais cet axe est
# celui sur lequel on RACCORDE deux sources et sur lequel on discute
# d'écarts d'orographie de quelques dizaines de mètres. Y mettre du bruit
# de quantification, c'est en mettre exactement là où on cherche du
# signal. Et contrairement à la température, aucun décalage ne sauve :
# une altitude va de 0 à 7 500 m, on ne peut pas la recentrer.
#
# Le coût de la précision est dérisoire : 14 niveaux × 125 balises ×
# 25 échéances × 4 o = **175 Ko par run**. `test_colonnes.py` mesure
# l'erreur des deux dtypes et échoue si float32 ne fait pas au moins
# vingt fois mieux (mesuré : ×8 192).
DTYPE_ALTITUDE = "float32"

SENTINELLE = 9999.0     # eccodes marque ainsi les points manquants
PLAFOND_PHYSIQUE = {"u": 200.0, "v": 200.0, "t": 100.0, "r": 110.0,
                    "tke": 500.0, "zp": 20000.0}

# Paramètre fictif décrivant l'altitude géopotentielle, pour que
# `quantifier()` lui applique les mêmes garde-fous qu'aux autres (NaN,
# sentinelle, plafond physique) sans la faire passer par le float16.
PARAM_ALTITUDE = dict(nom="zp", court="z", court_10m=None, paquet="IP1",
                      unite="m", decalage=0.0, tolerance=0.5)


# ══════════════════════════════════════════════════════════════════════
#  Sélection des balises
# ══════════════════════════════════════════════════════════════════════
def balises_du_domaine(stations, suspectes=()):
    """Balises tombant dans le domaine Nord-Alpes, triées par identifiant.

    ⚠️ Les balises `position_suspecte` sont MARQUÉES, pas retirées.
    L'étape 42 du 10/08 en a exclu trois des scores (Hautacam 1410, CVL
    Jabalcon West 1334, Déco de Puivert 939) et en a signalé une sans
    l'exclure (Piccolo Matro 2175) — mais ces décisions portent sur le
    SCORE, pas sur l'archive. Jeter une colonne à l'ingestion est
    irréversible ; la marquer laisse le consommateur décider, et laisse
    surtout la possibilité de constater plus tard qu'une position a été
    corrigée. `score.py` a déjà sa propre exclusion, en base, où elle
    doit être.
    """
    sus = set(str(x) for x in suspectes)
    out = []
    for s in stations:
        if not dans_domaine(s["lat"], s["lon"]):
            continue
        out.append(dict(id=str(s["id"]), lat=float(s["lat"]),
                        lon=float(s["lon"]), nom=s.get("name", ""),
                        source=s.get("source", ""),
                        position_suspecte=str(s["id"]) in sus))
    return sorted(out, key=lambda b: b["id"])


def index_plats(meta, balises):
    """Indice plat (j * Ni + i) de chaque balise dans la grille NATIVE.

    Renvoie (indices, hors_domaine) — `indices` est un tableau d'entiers
    aligné sur `balises`, et vaut -1 pour les balises hors grille.

    ⚠️ Plus proche voisin, aucune interpolation — même convention que
    l'orographie, et pour la même raison : on veut la colonne que le
    modèle calcule réellement à ce point de grille, pas une moyenne de
    colonnes voisines qui n'existe nulle part dans le modèle.
    """
    idx = np.full(len(balises), -1, dtype=np.int64)
    hors = []
    for k, b in enumerate(balises):
        i = round((b["lon"] - meta["lon0"]) / meta["di"])
        j = (round((meta["lat0"] - b["lat"]) / meta["dj"]) if meta["jScan"] != 1
             else round((b["lat"] - meta["lat0"]) / meta["dj"]))
        if 0 <= i < meta["Ni"] and 0 <= j < meta["Nj"]:
            idx[k] = j * meta["Ni"] + i
        else:
            hors.append(b["id"])
    return idx, hors


def verifier_grille(meta_attendue, meta_recue, quoi):
    """⚠️ LE GARDE-FOU CONTRE LE DÉCALAGE SILENCIEUX.

    Les indices plats sont calculés une fois depuis l'orographie figée.
    Si Météo-France déplaçait le coin de grille ou changeait le pas, ces
    indices désigneraient d'autres points — et rien ne le signalerait :
    les valeurs resteraient plausibles, simplement prises ailleurs. On
    compare donc la géométrie de CHAQUE message à celle de l'artefact.
    """
    for cle in ("Ni", "Nj", "di", "dj", "jScan"):
        if meta_attendue[cle] != meta_recue[cle]:
            raise Abort(
                f"{quoi} : la grille reçue ne correspond plus à l'orographie "
                f"figée ({cle} = {meta_recue[cle]} au lieu de "
                f"{meta_attendue[cle]}). ⚠️ Ne PAS ignorer : les indices des "
                f"balises seraient faux et les colonnes seraient prises "
                f"ailleurs, sans que rien n'ait l'air anormal. Régénérer "
                f"l'artefact avec `agrume/freeze_orographie.py`.")
    for cle in ("lat0", "lon0"):
        if abs(float(meta_attendue[cle]) - float(meta_recue[cle])) > 1e-6:
            raise Abort(
                f"{quoi} : origine de grille déplacée ({cle} = "
                f"{meta_recue[cle]} au lieu de {meta_attendue[cle]})")


# ══════════════════════════════════════════════════════════════════════
#  Quantification
# ══════════════════════════════════════════════════════════════════════
def quantifier(valeurs, param, dtype=np.float16):
    """float64 (unité GRIB) → float16 (unité d'archive), avec décalage.

    Les points manquants (NaN, ou la sentinelle 9999 d'eccodes) et les
    valeurs physiquement absurdes deviennent NaN — jamais 0, qui serait
    une valeur de vent parfaitement crédible.

    ⚠️ Le garde-fou 19/07 de `arome-wind/ingest.py::_ms` s'applique ici
    aussi : en échantillonnant au pas natif on touche des points que la
    décimation sautait, dont d'éventuels points manquants.
    """
    a = np.asarray(valeurs, dtype=np.float64)
    mauvais = ~np.isfinite(a) | (np.abs(a) >= SENTINELLE)
    a = a + param["decalage"]
    plafond = PLAFOND_PHYSIQUE.get(param["nom"])
    if plafond is not None:
        mauvais |= np.abs(a) > plafond
    a = np.where(mauvais, np.nan, a)
    return a.astype(dtype)


def erreur_quantification(valeurs, param, dtype=np.float16):
    """Erreur maximale introduite par la quantification, dans l'unité
    d'archive. Sert au banc : on MESURE la perte plutôt que de la
    supposer — c'est ainsi qu'on a vu qu'une température en kelvins perd
    un facteur 8, et qu'une altitude en float16 perd 8 mètres à 7 000."""
    a = np.asarray(valeurs, dtype=np.float64) + param["decalage"]
    return float(np.nanmax(np.abs(a - a.astype(dtype).astype(np.float64))))


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
