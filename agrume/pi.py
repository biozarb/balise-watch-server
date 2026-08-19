#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/pi.py — AROME-PI : les deux produits et leur alignement
#                                                        (10/08/2026)
#
#  Étape 8 bis. **Elle ne figurait pas dans la séquence du lot** : le §7
#  du prompt passe de « ingestion produit A/B » (AROME) à « composite
#  temporel PI » sans jamais poser l'ingestion de PI elle-même. La note
#  `claude/lot-h-etape-9-arbitrage-echeances-non-rondes-10-08.md` §6 le
#  constate — le poller DATE les runs PI depuis le 10/08, mais rien ne
#  les archive. Sans cette étape, l'étape 9 n'a pas de matière première.
#
#  ── CE QUI REND CE FICHIER DIFFÉRENT DE `grille.py` ──────────────────
#  ⛔ **PI n'est pas sur le miroir S3.** Vérifié : le miroir publie
#  `arome`, `arome-om`, `aromeifs`, `arpege`, `phealth`, `vague-surcote`,
#  et tous ses runs sont aux heures synoptiques. La route WCS avec clé
#  est donc OBLIGATOIRE, et elle a un grain imposé par le serveur :
#  **un paramètre × un niveau × une échéance × une boîte par requête.**
#
#  Conséquence directe et non négociable : **300 requêtes par run**
#  (2 paramètres × 6 niveaux × 25 échéances), ~2,4 Mo, ~3 min. À comparer
#  aux 7,4 Go et 2 requêtes du produit A. **Les deux chaînes n'ont donc
#  pas le même goulot** : AROME est limité par le réseau, PI par le
#  QUOTA. C'est pour ça que PI tourne sur le VPS, où vit la clé, et
#  AROME sur un runner GitHub, où vit la bande passante.
#
#  ── LE PIÈGE PRINCIPAL DE CE FICHIER : DEUX DÉCOUPES QUI SE
#     RESSEMBLENT ─────────────────────────────────────────────────────
#  ⚠️⚠️ Le produit AROME découpe son domaine avec `(j0, i0)` HÉRITÉS de
#  l'artefact d'orographie. Le WCS, lui, découpe le sien tout seul, à
#  partir de la boîte lat/lon qu'on lui donne. **Rien ne garantit que
#  les deux fenêtres coïncident** — et le 10/08 elles ne coïncidaient
#  déjà pas : la découpe WCS a rendu **61 × 85** là où ma découpe du
#  GRIB S3 en rendait **61 × 84**, une colonne d'écart née d'une égalité
#  en virgule flottante à la borne 7,6 °E.
#
#  Une colonne d'écart, c'est 1,95 km de décalage horizontal sur TOUT le
#  domaine. Le composite calculerait alors `Δ = PI − AROME` entre des
#  colonnes voisines mais différentes, et le résultat serait **une carte
#  de gradient horizontal déguisée en correction temporelle** — plausible
#  à l'œil, entièrement fausse, et impossible à voir sur un tracé.
#
#  D'où `aligner_sur_axes()` : on ne fait PAS confiance à la fenêtre que
#  le WCS a choisie. On lit la géométrie du GRIB reçu, on cherche où
#  l'axe de l'orographie tombe dedans, et on découpe nous-mêmes. Si le
#  WCS n'a pas couvert toute notre fenêtre, on REFUSE.
#
#  ── LES DEUX PRODUITS, MÊME PARTAGE QUE POUR AROME ───────────────────
#      colonnes PI (aux balises)  →  DÉFINITIF   ~76 ko/run, 670 Mo/an
#      grille PI   (le domaine)   →  3 RUNS      ~3,1 Mo/run, ~9 Mo résidents
#  ⓘ 24 runs par jour au lieu de 8 : c'est PI qui décide, pas nous.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import datetime as dt
import io
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from quantification import quantifier  # noqa: E402
from domaine import (DOMAINE, GRID_3D, NIVEAUX_H_0025,  # noqa: E402
                     NIVEAUX_H_AROMEPI)


class Abort(Exception):
    pass


# ══════════════════════════════════════════════════════════════════════
#  Ce que PI porte, et ce qu'il ne porte pas
# ══════════════════════════════════════════════════════════════════════
# ✅ Mesuré au `DescribeCoverage` du 10/08 : les 6 niveaux de PI sont
# exactement 10, 20, 50, 100, 250, 500 — et TOUS SIX sont dans les 25
# d'AROME, donc aucune interpolation verticale à la jonction. La grille
# est `1121 × 717 @ 0,025°`, strictement celle d'AROME 0025, donc aucun
# rééchantillonnage horizontal non plus.
NIVEAUX_PI = tuple(NIVEAUX_H_AROMEPI)
assert set(NIVEAUX_PI) <= set(NIVEAUX_H_0025), (
    "un niveau de PI qui n'existe pas dans AROME imposerait une "
    "interpolation verticale — vérifier domaine.py avant d'aller plus loin")

# ⚠️⚠️ LE 10 m N'EST PAS UN NIVEAU COMMUN, ET C'EST MESURÉ.
# Inventaire du bundle réel `0025/HP1__00H06H` du run 09 Z (10/08) :
# `u` et `v` y existent à **24 niveaux, de 20 m à 3 000 m**. Le 10 m
# vient des champs DÉDIÉS `10u`/`10v` (7 messages, un par échéance) —
# même paquet, autre famille de champ, autre `shortName`.
#
# Donc : côté AROME, « u à 10 m » n'existe pas sous ce nom. Le composite
# ne peut pas calculer Δ à 10 m sans aller chercher un champ d'une autre
# famille, et rien ne dit que le `10u` d'AROME et le « u à height=10 »
# de PI soient le même diagnostic.
#
# ⓘ CE QUE CE CODE FAIT : il DEMANDE le 10 m à PI, et il MESURE si le
# portail répond. Le résultat est écrit dans le manifeste
# (`niveau_10m_servi`). On transforme une inconnue en observation plutôt
# que de trancher par déduction — c'est la règle qui a déjà démenti cinq
# affirmations plausibles sur ce dossier en deux jours.
NIVEAU_HORS_HP1 = 10

# Les niveaux sur lesquels le composite peut calculer Δ SANS ambiguïté
# de champ. C'est cette liste-là qui compte pour l'étape 9.
NIVEAUX_DELTA = tuple(n for n in NIVEAUX_PI if n != NIVEAU_HORS_HP1)

# ── Les échéances : 25 pas de 15 min sur 0–6 h ────────────────────────
# ⚠️ EN MINUTES, et pas en heures. Le reste d'AGRUME compte les échéances
# en heures entières parce qu'AROME est horaire ; ici un `step` de 1 ne
# voudrait rien dire. Écrire les deux dans la même unité n'était pas une
# option : un mélange d'unités qui se ressemblent est exactement le genre
# de défaut qui ne lève jamais et qui décale tout d'un facteur 60.
PAS_MINUTES = 15
HORIZON_MINUTES = 360
ECHEANCES_MIN = tuple(range(0, HORIZON_MINUTES + 1, PAS_MINUTES))
assert len(ECHEANCES_MIN) == 25

# ── Les paramètres ────────────────────────────────────────────────────
# ⓘ `tolerance` et `decalage` suivent la convention de `quantification.py` —
# c'est `quantifier()` de ce module qui est réutilisé, pas une seconde
# copie. Le projet s'est déjà fait mordre par une constante dupliquée
# (`LEVELS` entre deux dépôts, cf. BUGS.md).
PARAMS_PI = (
    dict(nom="u", wcs="U_COMPONENT_OF_WIND__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND",
         unite="m/s", decalage=0.0, tolerance=0.02, optionnel=False),
    dict(nom="v", wcs="V_COMPONENT_OF_WIND__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND",
         unite="m/s", decalage=0.0, tolerance=0.02, optionnel=False),
    # ⓘ HORS v0, et c'est un arbitrage de QUOTA, pas de volume : la TKE
    # ferait passer le run de 300 à 450 requêtes (+50 %) pour un champ
    # dont l'étape 9 n'a aucun besoin. Elle sert au §5.2.c (rotor,
    # rabattant), qui est un autre lot. `--tke` la rallume.
    dict(nom="tke", wcs="TKE__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND",
         unite="m²/s²", decalage=0.0, tolerance=0.02, optionnel=True),
)

PARAMS_V0 = tuple(p for p in PARAMS_PI if not p["optionnel"])


def params_actifs(avec_tke=False):
    return PARAMS_PI if avec_tke else PARAMS_V0


# ══════════════════════════════════════════════════════════════════════
#  Où ça vit sur R2
# ══════════════════════════════════════════════════════════════════════
PREFIXE_COLONNES = "agrume/pi/colonnes/"
PREFIXE_GRILLE = "agrume/pi/grille/"
CLE_INDEX_GRILLE = "agrume/pi/grille/index.json"

# ══════════════════════════════════════════════════════════════════════
#  ⛔ LE RAFRAÎCHISSEMENT — arbitrage A10 de Yann, 17/08/2026 (Lot L)
# ══════════════════════════════════════════════════════════════════════
#  Le composite PI n'entre PAS dans les tampons du produit B, et c'est
#  un arbitrage, pas une commodité. Trois mesures l'ont dicté :
#
#  1. **La cadence.** Le produit B est publié 8 fois par jour (AROME),
#     PI 24. Fusionner à l'ingestion AROME aurait servi une couche PI
#     vieille de 3 h au pire — c'est-à-dire payer la fusion en perdant
#     exactement ce qui la justifie.
#  2. **Le cache.** Les `e{step}.bin` sont servis en `CACHE_IMMUABLE`
#     PARCE QUE « les mêmes octets sortiront toujours de cette clé »
#     (14/08). Les réécrire toutes les heures casse cette prémisse, et
#     l'appariement « vieux octets, manifeste frais » ne lève RIEN : le
#     Range tombe dans l'objet, rend 206, et la coupe trace une colonne
#     plausible et fausse. C'est la moitié silencieuse du bug du 13/08.
#  3. **Les octets.** Réécrire en place coûtait `colonnes.bin` ENTIER
#     (286 Mo sur nord-alpes) à chaque heure, parce que l'échéance y est
#     l'axe INTERNE d'un enregistrement de colonne. Un objet à part ne
#     porte que ce que PI corrige — `u`/`v` sur les 25 niveaux
#     hauteur — soit **29,14 Mo par disposition, 58,3 Mo par run PI**.
#
#  ⛔⛔ LES DEUX JUMEAUX S'ÉCRIVENT ENSEMBLE OU PAS DU TOUT. `carte.bin`
#  nourrit le calque, `colonnes.bin` nourrit la coupe. Publier l'un sans
#  l'autre ferait dire deux choses différentes au même vent au même
#  instant — c'est précisément la divergence que le produit B a été
#  redessiné pour éliminer le 12/08.
#
#  ⚠️ LE PRIX, PAYÉ SCIEMMENT : le client CHANGE de route de lecture
#  pour `u`/`v` hauteur sur 0–6 h. La clause « le client ne change pas
#  de route » de l'arbitrage A5 est donc TOMBÉE, et elle est tombée
#  devant le chiffrage, pas par inadvertance.
PREFIXE_RAFRAICHISSEMENT = "agrume/pi/rafraichissement/"
CLE_INDEX_RAFRAICHISSEMENT = "agrume/pi/rafraichissement/index.json"

# ⚠️ LE DOMAINE EST DANS LA CLÉ, comme pour le produit B depuis le
# 12/08. Aujourd'hui `DOMAINES_PI` n'en contient qu'un — mais une clé
# sans domaine devrait être migrée le jour où il y en a deux, et la
# rétention se compte PAR DOMAINE (`grille.index_apres`).
GABARIT_CLE_RAFRAICHISSEMENT = (
    "agrume/pi/rafraichissement/{domaine}/{run_pi}/{objet}")


def prefixe_rafraichissement(run_pi, domaine):
    return f"{PREFIXE_RAFRAICHISSEMENT}{domaine}/{run_pi}"


def cles_du_rafraichissement(run_pi, domaine):
    """Les trois clés d'un rafraîchissement. ⚠️ `manifest.json` en
    DERNIER dans cette liste et en dernier à l'écriture : il est ce qui
    rend l'objet lisible, il ne doit jamais décrire des octets absents."""
    b = prefixe_rafraichissement(run_pi, domaine)
    return [f"{b}/carte.bin", f"{b}/colonnes.bin", f"{b}/manifest.json"]

# ⚠️ 24 runs/jour, pas 8. À 3,1 Mo la grille, sans purge ce serait 27 Go
# par an — presque trois fois le palier gratuit, pour une donnée dont
# personne ne veut la version d'hier. Trois runs, comme le produit B, et
# pour la même raison : de quoi comparer un run au précédent.
RETENTION_RUNS = 3

#: ⛔ L'ANCIEN NOM DE DOMAINE DE L'INDEX DE LA GRILLE PI — À PURGER.
#: `grille.index_apres` compte la rétention PAR DOMAINE depuis le
#: 12/08 (deux domaines AROME dans un même run se purgeaient
#: mutuellement). Tant que PI n'avait qu'une boîte, il lui fallait
#: quand même un nom, et ce nom était `"pi"` : une entrée SANS
#: `domaine` est envoyée à la suppression par `index_apres`.
#: ⚠️ Cette constante est née d'une PANNE, pas d'une relecture :
#: `index_apres` a gagné un paramètre positionnel le 12/08 et deux
#: sites d'appel ne l'ont jamais reçu (`ingest_pi.purger` et
#: `sonde_r2`). Résultat : `TypeError` à CHAQUE run PI depuis, donc
#: index jamais mis à jour, donc grilles écrites hors index —
#: invisibles, puisque `ListObjects` est hors de portée du jeton
#: ordinaire. Exactement la fratrie de défauts décrite dans BUGS.md
#: le 13/08 : « le défaut voyage en fratrie ».
#:
#: ⛔⛔ 19/08 (Lot M) — ELLE N'EST PLUS UN NOM DE DOMAINE, ELLE EST UNE
#: CONSIGNE DE PURGE. PI écrit désormais UNE grille PAR DOMAINE, sous
#: son vrai nom (`nord-alpes`, `pyrenees`, …). Les entrées d'index
#: écrites avant ce lot portent toutes `domaine: "pi"` et pointent sur
#: `agrume/pi/grille/{run}/…`, un chemin que plus personne n'écrit.
#: Laissées telles quelles, elles ne seraient JAMAIS purgées : leur
#: compteur de rétention ne recevrait plus de nouvelle entrée, donc
#: elles resteraient éternellement sous le seuil de 3. Trois grilles
#: orphelines, ~9 Mo, invisibles — une fuite, pas un déchet, exactement
#: ce que le §« migration » de `index_apres` refuse pour les entrées
#: sans domaine. `ingest_pi.purger()` les envoie donc à la suppression
#: au premier run qui suit le déploiement, et cette constante est ce
#: qui les désigne.
DOMAINE_INDEX_LEGS = "pi"


def prefixe_run_grille(run, domaine):
    """⛔ LE DOMAINE EST DANS LA CLÉ DEPUIS LE LOT M (19/08).

    Sans lui, les trois domaines d'un même run PI écriraient sur la MÊME
    clé `agrume/pi/grille/{run}/grille.npz` : le dernier écrit gagnerait,
    et le calque des Alpes servirait la grille des Pyrénées sans qu'une
    seule requête n'échoue. C'est la faute que le produit B a déjà payée
    le 12/08, à l'identique, et que `GABARIT_CLE_RAFRAICHISSEMENT` avait
    déjà anticipée ici même (« une clé sans domaine devrait être migrée
    le jour où il y en a deux »). Ce jour est arrivé.
    """
    return f"{PREFIXE_GRILLE}{domaine}/{run}"


def cles_du_run_grille(run, domaine):
    b = prefixe_run_grille(run, domaine)
    return [f"{b}/grille.npz", f"{b}/manifest.json"]


def cles_du_run_colonnes(run):
    """⛔ ET CELLES-CI N'ONT PAS DE DOMAINE — CE N'EST PAS UN OUBLI.

    Les colonnes sont indexées sur **l'axe des balises**, celui de
    `quantification.balises_du_domaine()`, qui porte DÉJÀ les balises des
    trois domaines (c'est ce qui rendait « 207 servies sur 288 » avant le
    Lot M : l'axe était complet, seul le remplissage ne l'était pas).
    Un run PI produit donc UNE archive de colonnes, et une seule, qu'elle
    soit nourrie par une boîte ou par trois. Y mettre un domaine
    couperait en trois une archive dont l'axe est unique — et obligerait
    tout consommateur à recoller des morceaux dont il ne connaît pas le
    découpage.

    ⚠️ Rangées par JOUR : 24 runs/jour × 365 font 8 760 préfixes plats
    par an. Sans `ListObjects` (Class A, hors budget), un préfixe plat
    rend l'archive impossible à parcourir à la main le jour où on en
    aura besoin.
    """
    jour = run[:10]
    b = f"{PREFIXE_COLONNES}{jour}/{run}"
    return [f"{b}/colonnes.npz", f"{b}/manifest.json"]


def instants_du_run(run_iso):
    """Les 25 instants ISO d'un run PI. ⚠️ Le portail veut
    `2026-08-10T16:15:00Z` SANS guillemets (piège nº 3) — c'est
    `subset_temps()` qui s'en occupe, pas cette fonction."""
    t0 = dt.datetime.strptime(run_iso, "%Y-%m-%dT%H:00:00Z").replace(
        tzinfo=dt.timezone.utc)
    return [(t0 + dt.timedelta(minutes=m)).strftime("%Y-%m-%dT%H:%M:%SZ")
            for m in ECHEANCES_MIN]


# ══════════════════════════════════════════════════════════════════════
#  ⚠️⚠️ L'ALIGNEMENT — la seule fonction de ce fichier qui puisse
#     produire une erreur INVISIBLE
# ══════════════════════════════════════════════════════════════════════
def geometrie_grib(meta):
    """(lats, lons) de la fenêtre RENDUE par le WCS, en degrés signés.

    ⚠️ Le GRIB d'AROME publie les longitudes en **0–360** : le premier
    point de la grille France est à 348,0°, c'est-à-dire −12°. Sans
    normalisation, une fenêtre 5,5–7,6 °E ne rencontre AUCUN point, la
    découpe rend un tableau VIDE — et la médiane d'un tableau vide est
    **NaN, pas une exception**. *Constaté le 10/08 : le premier tableau
    de résultats de la session était une colonne de NaN parfaitement
    alignés, qui avait l'air d'un champ manquant.*
    """
    nj, ni = int(meta["Nj"]), int(meta["Ni"])
    lat0, lon0 = float(meta["lat0"]), float(meta["lon0"])
    dj, di = float(meta["dj"]), float(meta["di"])
    lats = (lat0 + np.arange(nj) * dj if meta.get("jScan") == 1
            else lat0 - np.arange(nj) * dj)
    lons = (lon0 + np.arange(ni) * di + 180.0) % 360.0 - 180.0
    return lats, lons


def aligner_sur_axes(champ2d, meta, lats_cible, lons_cible, tolerance=1e-4):
    """Découpe le champ rendu par le WCS sur les axes de l'OROGRAPHIE.

    ⚠️⚠️ POURQUOI CETTE FONCTION EXISTE. Le WCS choisit sa fenêtre tout
    seul à partir de la boîte lat/lon ; l'orographie a la sienne, héritée
    de `(j0, i0)`. Le 10/08, elles différaient **d'une colonne** — 61 × 85
    contre 61 × 84 — sur une égalité en virgule flottante à 7,6 °E.

    Une colonne d'écart vaut 1,95 km à 45,5 °N. Le composite calculerait
    `Δ = PI − AROME` entre colonnes VOISINES : le résultat serait une
    carte de gradient horizontal déguisée en correction temporelle. Elle
    serait lisse, plausible, et fausse partout.

    On ne corrige donc pas « au mieux » : on exige que chaque axe cible
    se retrouve dans l'axe reçu **au point de grille près**, et on refuse
    sinon. Une ingestion qui échoue coûte un run ; un décalage silencieux
    coûte la confiance dans tout ce qui en descend.
    """
    lats_recu, lons_recu = geometrie_grib(meta)
    a = np.asarray(champ2d)
    if a.shape != (len(lats_recu), len(lons_recu)):
        raise Abort(f"champ {a.shape} incohérent avec la géométrie annoncée "
                    f"({len(lats_recu)}, {len(lons_recu)})")

    def rang(axe_recu, axe_cible, quoi):
        # Chaque valeur cible doit exister dans l'axe reçu. On cherche le
        # plus proche puis on VÉRIFIE l'écart — `searchsorted` seul
        # rendrait toujours un indice, y compris le mauvais.
        idx = np.abs(axe_recu[None, :] - np.asarray(axe_cible)[:, None]).argmin(axis=1)
        ecart = np.abs(axe_recu[idx] - np.asarray(axe_cible))
        pire = float(ecart.max())
        if pire > tolerance:
            raise Abort(
                f"la fenêtre rendue par le WCS ne couvre pas l'axe "
                f"{quoi} de l'orographie : écart maximal {pire:.6f}° "
                f"(> {tolerance}). ⚠️ NE PAS ÉLARGIR LA TOLÉRANCE — un "
                f"point de grille vaut 1,95 km en longitude et 2,78 km "
                f"en latitude, et un décalage d'un point rendrait un "
                f"delta PI−AROME lisse, plausible et faux partout.")
        # Contiguïté : si les indices ne se suivent pas, les deux grilles
        # n'ont pas le même pas — la découpe serait un sous-échantillonnage
        # silencieux.
        if len(idx) > 1 and not np.array_equal(np.diff(idx), np.ones(len(idx) - 1, dtype=idx.dtype)):
            raise Abort(f"axe {quoi} non contigu dans la fenêtre reçue — "
                        f"les deux grilles n'ont pas le même pas")
        return idx

    jj = rang(lats_recu, lats_cible, "latitude")
    ii = rang(lons_recu, lons_cible, "longitude")
    return a[jj[0]:jj[-1] + 1, ii[0]:ii[-1] + 1]


# ══════════════════════════════════════════════════════════════════════
#  Les conteneurs
# ══════════════════════════════════════════════════════════════════════
class _Base:
    """Ce que les deux produits partagent : la pose d'un champ, le
    remplissage PAR PARAMÈTRE, et le refus de mentir sur les axes."""

    def __init__(self, run, params):
        self.run = run
        self.params = tuple(params)
        self.i_param = {p["nom"]: k for k, p in enumerate(self.params)}
        self.i_niveau = {n: k for k, n in enumerate(NIVEAUX_PI)}
        self.i_min = {m: k for k, m in enumerate(ECHEANCES_MIN)}
        self.manquants = []

    # ⚠️⚠️ LE REMPLISSAGE SE CALCULE SUR CE QUI POUVAIT ÊTRE REMPLI.
    # Premier run réel (16 Z, 10/08) : 300/300 champs obtenus, et un
    # remplissage annoncé de **98,43 %**. Ce n'était pas un trou — c'est
    # 125/127 = 0,98425. Deux des 127 « balises » sont des points de
    # RADIOSONDAGE, hors du domaine par construction (cf. `domaine.py`) :
    # elles ne peuvent PAS être servies, et jamais elles ne le seront.
    #
    # Un taux qui ne peut pas atteindre 100 % est un taux qu'on apprend à
    # ignorer — et le jour où il tomberait à 97 % pour une VRAIE raison,
    # personne ne verrait la différence. On divise donc par ce qui est
    # servable, et on publie le reste à part (`balises_hors_fenetre`).
    def _servable(self):
        return None

    def remplissage_par_parametre(self):
        """⚠️ PAR PARAMÈTRE, comme les produits A et B, et pour la même
        raison mesurée : un remplissage global de 96 % ne dit pas s'il
        manque un champ par construction ou si un run est tronqué."""
        return {p["nom"]: self._part(self.donnees[k])
                for k, p in enumerate(self.params)}

    def remplissage_par_niveau(self):
        """ⓘ Celui-ci sert à UNE chose précise : voir d'un coup d'œil si
        le 10 m est servi par PI ou non (cf. `NIVEAU_HORS_HP1`).
        ✅ Premier run réel : il l'est — 10 m rempli comme les cinq
        autres. L'inconnue laissée ouverte par la note d'étape 9 est
        levée, par mesure et non par déduction."""
        return {n: self._part(self.donnees[:, k])
                for k, n in enumerate(NIVEAUX_PI)}

    def _part(self, a):
        m = self._servable()
        b = a.astype(np.float32)
        if m is not None:
            b = b[..., m]
        if b.size == 0:
            return 0.0
        return round(float(np.isfinite(b).mean()), 4)

    def octets(self):
        return int(self.donnees.nbytes)


class GrillePI(_Base):
    """Le domaine entier, 3 runs de durée de vie.

        donnees : (paramètre, niveau, échéance, lat, lon)  float16
        zsol    : (lat, lon)                               float32
        lats    : DÉCROISSANT (nord → sud)   ·   lons : croissant

    ⚠️ La disposition met (niveau, échéance) devant (lat, lon) pour la
    même raison que le produit B : une carte à un niveau et une échéance
    est alors CONTIGUË en mémoire. C'est exactement la tranche que le
    calque altitude servira, et que le composite lira.

    ⚠️⚠️ `lats` DÉCROÎT. Un consommateur qui supposerait des latitudes
    croissantes obtiendrait une carte retournée — et une carte retournée
    sur un domaine presque carré ne se voit PAS à l'œil : les Alpes
    ressembleraient toujours à des Alpes. D'où les axes DANS l'archive.
    """

    def __init__(self, run, params, lats, lons, zsol, domaine=None):
        super().__init__(run, params)
        # ⚠️ Le domaine par défaut est le Nord-Alpes, et c'est le SEUL
        # défaut de ce fichier qui reste après le Lot M : il tient les
        # bancs écrits avant, pas la production, qui le passe toujours.
        self.domaine = domaine or "nord-alpes"
        self.lats = np.asarray(lats, dtype=np.float32)
        self.lons = np.asarray(lons, dtype=np.float32)
        self.zsol = np.asarray(zsol, dtype=np.float32)
        nj, ni = len(self.lats), len(self.lons)
        if self.zsol.shape != (nj, ni):
            raise Abort(f"zsol {self.zsol.shape} ≠ axes ({nj}, {ni})")
        self.donnees = np.full(
            (len(self.params), len(NIVEAUX_PI), len(ECHEANCES_MIN), nj, ni),
            np.nan, dtype=np.float16)

    def poser(self, param, niveau, minute, champ2d):
        self.donnees[self.i_param[param["nom"]], self.i_niveau[niveau],
                     self.i_min[minute]] = quantifier(champ2d, param)

    def manifeste(self, extra=None):
        m = dict(
            produit=(f"AGRUME PI — grille du domaine {self.domaine} "
                     f"(jetable)"),
            modele="AROME-PI", route="WCS portail (clé)", grille=GRID_3D,
            run=self.run, domaine=self.domaine,
            echeances_min=list(ECHEANCES_MIN),
            pas_min=PAS_MINUTES,
            niveaux_m_sol=list(NIVEAUX_PI),
            niveaux_delta=list(NIVEAUX_DELTA),
            parametres=[dict(nom=p["nom"], unite=p["unite"], wcs=p["wcs"])
                        for p in self.params],
            disposition=("donnees = (parametre, niveau, echeance, lat, lon) "
                         "en float16 ; zsol = (lat, lon) en float32 ; lats "
                         "et lons sont dans l'archive"),
            axes=dict(nb_lat=len(self.lats), nb_lon=len(self.lons),
                      lat_premier=round(float(self.lats[0]), 4),
                      lat_dernier=round(float(self.lats[-1]), 4),
                      lon_premier=round(float(self.lons[0]), 4),
                      lon_dernier=round(float(self.lons[-1]), 4),
                      sens=("lats DÉCROISSANTES (premier point au NORD, "
                            "jScansPositively = 0) ; lons croissantes")),
            reference_verticale=("niveaux AGL au-dessus du sol DU MODÈLE ; "
                                 "altitude_ASL = zsol[j, i] + niveau"),
            fenetre=("héritée de l'artefact d'orographie 0,025° de CE "
                     "domaine, PUIS découpée dans le GRIB reçu (cf. "
                     "aligner_sur_axes). ⛔ Depuis le Lot M (19/08) la "
                     "boîte DEMANDÉE au portail est l'englobante de tous "
                     "les domaines PI, élargie d'un pas de grille, et c'est "
                     "la découpe qui rend les trois fenêtres — le WCS "
                     "choisit sa propre fenêtre et elle a déjà différé "
                     "d'une colonne le 10/08 (Nord-Alpes) et d'une ligne "
                     "ET d'une colonne le 19/08 (Tarn/Aveyron/Hérault)"),
            remplissage=self.remplissage_par_parametre(),
            remplissage_par_niveau=self.remplissage_par_niveau(),
            octets=self.octets(),
            retention_runs=RETENTION_RUNS,
        )
        if extra:
            m.update(extra)
        return m

    def npz(self):
        tampon = io.BytesIO()
        np.savez_compressed(tampon, donnees=self.donnees, zsol=self.zsol,
                            lats=self.lats, lons=self.lons,
                            niveaux=np.asarray(NIVEAUX_PI),
                            echeances_min=np.asarray(ECHEANCES_MIN))
        return tampon.getvalue()


class ColonnesPI(_Base):
    """Les colonnes aux balises, **DÉFINITIVES**.

        donnees : (paramètre, niveau, échéance, balise)   float16

    ⓘ ~76 ko par run, 1,8 Mo par jour, 670 Mo par an — soit ~0,10 $/mois
    sur R2. C'est ce qui permettra un jour de confronter le composite aux
    mesures réelles des balises, et de calibrer les poids sur du passé.
    **La rétention du portail est de 4,25 jours : ce qui n'est pas
    archivé maintenant est perdu pour toujours.**

    ⚠️ L'axe des balises est celui de `quantification.balises_du_domaine()`, et
    il est embarqué dans le manifeste. Sans lui, l'archive ne se suffit
    pas : un consommateur devrait retrouver le bon artefact au bon sha
    pour savoir à quelle balise correspond la colonne 47.
    """

    def __init__(self, run, params, balises, ji, domaines=None):
        super().__init__(run, params)
        self.balises = list(balises)
        # (j, i) LOCAUX dans la fenêtre du domaine, None hors fenêtre.
        self.ji = list(ji)
        # ⛔ LE DOMAINE DE CHAQUE BALISE, DEPUIS LE LOT M (19/08).
        # `self.ji` seul ne suffit plus : un couple (j, i) n'a de sens
        # que RELATIVEMENT à une fenêtre, et il y en a désormais trois.
        # Poser un champ pyrénéen sur les indices d'une balise alpine
        # rendrait une valeur finie, plausible, et prise 400 km plus
        # loin — le genre de faute qui ne lève jamais.
        # ⚠️ `None` = « toutes les balises dans la même fenêtre », le
        # comportement d'avant le Lot M ; c'est ce que les bancs écrits
        # avant continuent d'exercer.
        self.domaines = (list(domaines) if domaines is not None
                         else [None] * len(self.balises))
        if len(self.domaines) != len(self.balises):
            raise Abort(f"{len(self.domaines)} domaines pour "
                        f"{len(self.balises)} balises")
        self.donnees = np.full(
            (len(self.params), len(NIVEAUX_PI), len(ECHEANCES_MIN),
             len(self.balises)), np.nan, dtype=np.float16)
        # Le masque des balises SERVABLES — celles qui tombent dans la
        # fenêtre. Voir la note sur `_servable` : sans lui, le taux
        # plafonne à 98,43 % pour une raison structurelle.
        self._masque = np.asarray([x is not None for x in self.ji], dtype=bool)

    def _servable(self):
        return self._masque

    def hors_fenetre(self):
        return [b["id"] for b, x in zip(self.balises, self.ji) if x is None]

    def poser_depuis_champ(self, param, niveau, minute, champ2d,
                           domaine=None):
        """Prélève les balises dans un champ DÉJÀ aligné.

        ⚠️ On prélève dans le champ aligné plutôt que de refaire une
        indexation depuis la grille native : les deux produits tombent
        alors sur les mêmes points PAR CONSTRUCTION, pas par coïncidence
        de deux calculs qui se ressemblent. C'est la leçon de
        `axes_depuis_orographie()`, dont le premier garde-fou ne prouvait
        rien parce qu'il comparait deux formules à la même source.

        ⛔⛔ `domaine` RESTREINT LA POSE AUX BALISES DE CETTE FENÊTRE, ET
        NE TOUCHE PAS AUX AUTRES. Depuis le Lot M cette méthode est
        appelée UNE FOIS PAR DOMAINE sur le même (paramètre, niveau,
        échéance) : trois appels remplissent une seule tranche, chacun sa
        part. D'où l'écriture par INDICES et non par tranche entière —
        une affectation globale effacerait ce que l'appel précédent vient
        de poser, et le symptôme serait une archive où seul le dernier
        domaine ingéré porte des valeurs. `domaine=None` garde le
        comportement d'avant : tout ce qui est dans la fenêtre.
        """
        a = np.asarray(champ2d)
        vals = np.full(len(self.balises), np.nan, dtype=np.float64)
        vises = []
        for k, ji in enumerate(self.ji):
            if ji is None:
                continue
            if domaine is not None and self.domaines[k] != domaine:
                continue
            vals[k] = a[ji[0], ji[1]]
            vises.append(k)
        if not vises:
            return 0
        q = quantifier(vals, param)
        self.donnees[self.i_param[param["nom"]], self.i_niveau[niveau],
                     self.i_min[minute], vises] = q[vises]
        return len(vises)

    def manifeste(self, extra=None):
        m = dict(
            produit="AGRUME PI — colonnes aux balises (définitif)",
            modele="AROME-PI", route="WCS portail (clé)", grille=GRID_3D,
            run=self.run,
            echeances_min=list(ECHEANCES_MIN),
            pas_min=PAS_MINUTES,
            niveaux_m_sol=list(NIVEAUX_PI),
            niveaux_delta=list(NIVEAUX_DELTA),
            parametres=[dict(nom=p["nom"], unite=p["unite"], wcs=p["wcs"])
                        for p in self.params],
            disposition=("donnees = (parametre, niveau, echeance, balise) "
                         "en float16"),
            balises=[dict(id=b["id"], lat=b["lat"], lon=b["lon"],
                          nom=b["nom"], source=b["source"],
                          position_suspecte=b["position_suspecte"],
                          # ⛔ Le domaine qui a NOURRI cette colonne, pas
                          # celui qui contient géométriquement la balise.
                          # Les deux coïncident aujourd'hui ; ils
                          # cesseraient de coïncider si un domaine était
                          # retiré de `DOMAINES_PI` sans l'être de
                          # `DOMAINES`, et c'est précisément ce cas-là
                          # que le consommateur doit pouvoir lire.
                          domaine_pi=self.domaines[k],
                          servie=self.ji[k] is not None)
                     for k, b in enumerate(self.balises)],
            reference_verticale=("niveaux AGL au-dessus du sol DU MODÈLE — "
                                 "l'altitude du sol vit dans l'artefact "
                                 "d'orographie 0,025°, pas ici"),
            # ⚠️ Calculé sur les balises SERVABLES. `balises_hors_fenetre`
            # dit ce qui a été exclu, et pourquoi : un taux qui ne peut
            # pas atteindre 100 % est un taux qu'on apprend à ignorer.
            remplissage=self.remplissage_par_parametre(),
            remplissage_par_niveau=self.remplissage_par_niveau(),
            remplissage_calcule_sur=("les balises tombant dans la fenêtre ; "
                                     "les points de radiosondage sont hors "
                                     "domaine par construction"),
            balises_hors_fenetre=self.hors_fenetre(),
            octets=self.octets(),
        )
        if extra:
            m.update(extra)
        return m

    def npz(self):
        tampon = io.BytesIO()
        np.savez_compressed(
            tampon, donnees=self.donnees,
            balises=np.asarray([b["id"] for b in self.balises]),
            niveaux=np.asarray(NIVEAUX_PI),
            echeances_min=np.asarray(ECHEANCES_MIN))
        return tampon.getvalue()


def json_octets(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1).encode("utf-8")
