#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/piaf.py — LE FORMAT de la pluie à venir           (20/08/2026)
#                   Lot Q2, arbitrages A15 à A20
#
#  ⛔ DE QUOI CE FICHIER PARLE, ET COMMENT ON LE NOMME.
#  Il ingère et CITE une source : le produit de prévision immédiate
#  agrégée de Météo-France (PIAF), publié sous Licence Ouverte 2.0. Le
#  nom `piaf` désigne ici LA SOURCE — jamais un produit de ce projet.
#  ⚠️ La Licence Ouverte 2.0 interdit d'induire un tiers en erreur sur la
#  source ou la nature de l'information réutilisée : elle EXIGE donc
#  l'attribution (que le manifeste porte), et elle interdit d'appeler
#  « PIAF » ce que nous fabriquons. Les deux à la fois.
#
#  ── SIX FAITS MESURÉS LE 20/08, DONT QUATRE DÉMENTENT LA DOC ─────────
#  1. ⛔ Grille **lat/lon 0,01°**, `srsName=2DLongLat` — PAS du Lambert.
#     Aucune reprojection. C'est la maille du calque vent SOL.
#  2. ⛔ **39 échéances**, coefficients 300 … 11 700 s, soit 5 → 195 min.
#     La description du portail dit 180 ; **sa propre donnée dit 195.**
#  3. ⛔ `typeOfStatisticalProcessing = 1`, `stepType = accum`,
#     `units = kg m**-2` ⇒ un **CUMUL en mm**, malgré le mot « RATE »
#     dans le nom de la couverture. Ne rien diviser.
#  4. ⛔ **L'instant nommé est la FIN de la tranche.** L'échéance +5 min
#     porte `stepRange = 0m-5m`. Décaler le ruban de 5 min est l'erreur
#     naturelle, et elle ne lève jamais.
#  5. ⛔ **Une passe toutes les 5 MINUTES**, pas dix : 1 223 écarts de
#     5 min sur 1 226, rétention 4,32 jours (1 227 passes en ligne).
#     A18 avait tranché « 10 min » en croyant que c'était la cadence du
#     producteur — c'est la nôtre, et c'est un choix, pas un constat.
#  6. ⛔ **Aucun drapeau de qualité radar n'est publié.** 256 clés
#     eccodes lues sur un champ réel : rien. Le descriptif annonce que
#     sous 74 % de qualité radar le produit vaut AROME-PI seul ; nous ne
#     pouvons pas le savoir, et le manifeste doit le DIRE plutôt que de
#     laisser croire que le silence vaut « qualité bonne ».
#
#  ── LES DEUX JEUX, ET POURQUOI ILS N'ONT PAS LA MÊME MAILLE ──────────
#      carte.bin              calque   0,02°   401 × 568   17,8 Mo
#      colonnes-{domaine}.bin coupe    0,01°   natif       11,0 Mo (×3)
#
#  ⛔⛔ ILS S'ÉCRIVENT ENSEMBLE OU PAS DU TOUT — la leçon du Lot L2, mot
#  pour mot. `index["dernier"]` n'avance qu'après TOUTES les écritures.
#
#  ⚠️ **0,025° ÉTAIT IMPOSSIBLE**, et A19 bis l'annonçait. 0,025 / 0,01
#  = 2,5 : dériver cette maille de la grille servie demanderait
#  d'interpoler, c'est-à-dire d'inventer des points entre ceux que le
#  producteur publie. 0,02° est un facteur ENTIER.
#
#  ⛔⛔ ET LA RÉDUCTION EST UN **MAXIMUM**, PAS UNE DÉCIMATION NI UNE
#  MOYENNE. Pour le vent, décimer est à peu près neutre : le champ est
#  lisse. Pour la pluie, non — une cellule d'averse d'un kilomètre
#  tombée entre deux points gardés **disparaît de l'écran alors qu'elle
#  mouille**. Le maximum ne perd jamais une cellule ; il l'élargit d'au
#  plus 1 km. La coupe, elle, lit le 0,01° natif : la valeur AU POINT
#  reste exacte. C'est la seule dissymétrie du lot, et elle est dans ce
#  sens-là exprès.
#
#  ── L'EMPRISE, ET UN DÉFAUT DU CADRAGE ───────────────────────────────
#  ⚠️ A19 écrivait « ~−1 → 9,5 E · 42 → 50 N ». Cette boîte **ne
#  contient pas le domaine Pyrénées**, qui descend à `lonmin = −1,80`.
#  Elle est donc élargie à −1,85 (un pas de grille de marge), et `latmax`
#  passe à 50,01 pour que les DEUX comptes de mailles soient PAIRS —
#  sans quoi le dernier bloc du calque serait incomplet et sa maille
#  couvrirait deux fois moins de terrain que les autres, en silence.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import datetime as dt
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

from domaine import DOMAINES  # noqa: E402
from grille import (index_apres, index_apres_purge,  # noqa: E402
                    verifier_prefixe)
from quantification import PARAM_PLUIE_IMMEDIATE, quantifier  # noqa: E402


class Abort(Exception):
    """Erreur d'exécution — le run s'arrête, rien n'est publié à moitié."""


# ══════════════════════════════════════════════════════════════════════
#  CE QUE LE PORTAIL SERT
# ══════════════════════════════════════════════════════════════════════
#: ⚠️ Le nom EXACT, relevé dans le GetCapabilities du 20/08. Il porte
#: « RATE » alors que la donnée est un cumul (fait nº 3) — on ne le
#: « corrige » pas : c'est l'identifiant du producteur.
CHAMP_WCS = "TOTAL_PRECIPITATION_RATE__GROUND_OR_WATER_SURFACE"

#: Les cinq agrégations publiées pour chaque passe.
AGREGATIONS = ("PT5M", "PT15M", "PT30M", "PT1H", "PT3H")

#: ⛔ ON N'INGÈRE QUE `PT5M`, ET `PT1H` EST UN PIÈGE. Mesuré le 20/08 :
#: le `PT1H` est calé sur LA PASSE, pas sur l'heure ronde
#: (`lengthOfTimeRange = 60`, `stepRange = 0-1`, `dataTime = 0550` ⇒ la
#: tranche nommée 06:50 couvre 05:50 → 06:50). Elle ne tombe donc JAMAIS
#: dans une colonne de la coupe. L'agrégat horaire du Lot Q4 est une
#: SOMME de 12 tranches `PT5M` — légitime et exacte, puisque ce sont des
#: cumuls disjoints de la même grandeur.
AGREGATION = "PT5M"

PAS_MIN = 5
NB_ECHEANCES = 39
HORIZON_MIN = PAS_MIN * NB_ECHEANCES          # 195
#: Cadence d'ingestion — LA NÔTRE (A18), pas celle du producteur, qui
#: publie toutes les 5 min (fait nº 5).
CADENCE_MIN = 10

PAS_DEG = 0.01                                 # la maille servie
FACTEUR_CALQUE = 2                             # 0,01° → 0,02°
PAS_CALQUE_DEG = PAS_DEG * FACTEUR_CALQUE

#: L'emprise ingérée (A19, corrigée — cf. l'en-tête).
BOITE = dict(latmin=42.00, latmax=50.01, lonmin=-1.85, lonmax=9.50)

#: ⛔ Les domaines où la COUPE existe, et rien d'autre. Vérifié dans le
#: client le 20/08 : `chargerProfilAgrume` lit UNE colonne d'un
#: `colonnes.bin` publié PAR DOMAINE — la coupe n'est donc dessinable
#: nulle part ailleurs. Publier le 0,01° sur toute la boîte servirait un
#: consommateur qui n'existe pas, pour 65,7 Mo par passe au lieu de 11.
#: ⚠️ Les noms ne sont pas recopiés : ils viennent de `domaine.DOMAINES`.
DOMAINES_COUPE = ("nord-alpes", "pyrenees", "tarn-aveyron-herault")

#: ⚠️ float16 comme partout ailleurs dans ce projet. Mesuré : à 11 mm
#: (le maximum réel du 20/08) le pas du float16 vaut 0,008 mm, à 1 mm il
#: vaut 0,001 mm. La quantification est très en dessous de l'incertitude
#: du produit ; c'est le seul endroit du lot où l'on peut se le
#: permettre sans le mesurer davantage.
DTYPE = np.dtype("<f2")

# ══════════════════════════════════════════════════════════════════════
#  LES CLÉS
# ══════════════════════════════════════════════════════════════════════
PREFIXE = "agrume/piaf/"
CLE_INDEX = "agrume/piaf/index.json"
GABARIT_CLE = "agrume/piaf/{passe}/{objet}"

#: ⛔ DEUX passes en ligne, pas trois. La secours existe pour qu'un
#: client qui lisait la passe précédente ne prenne pas un 404 pendant la
#: publication de la suivante ; au-delà elle ne sert plus personne, et à
#: 144 passes par jour chaque passe gardée coûte 28,8 Mo.
RETENTION_PASSES = 2

#: ⛔ LE PLAFOND DUR (garde-fou nº 3 du §8 bis du cadrage). 5 objets +
#: 2 écritures d'index par passe = 7. Le plafond est posé à 12 : de quoi
#: absorber une republication d'index après purge partielle, et pas de
#: quoi laisser une boucle écrire 2 000 objets. ⚠️ Sans lui, une purge
#: qui cesserait de mordre ajouterait 4,1 Go par jour et saturerait la
#: jauge R2 en un peu plus de vingt-quatre heures — une alerte du
#: lendemain matin arriverait trop tard.
PLAFOND_ECRITURES = 12

#: Le flux unique de ce produit, au sens de `grille.index_apres` (qui
#: compte la rétention PAR domaine). Ici les cinq objets d'une passe
#: forment UN tout indissociable : un seul flux, donc.
FLUX = "passe"


def cles_de_la_passe(passe, domaines=DOMAINES_COUPE):
    """Les cinq clés d'une passe, dans l'ORDRE D'ÉCRITURE.

    ⛔ Le manifeste est le DERNIER : il est ce qui rend les octets
    lisibles, il ne doit jamais décrire des objets absents. Même contrat
    que `rafraichissement.ecrire`.

    ⛔⛔ `domaines` EST UN PARAMÈTRE, ET C'EST UN CORRECTIF (trouvé par le
    banc, 20/08). La première version lisait `DOMAINES_COUPE` en dur.
    Appelée avec une passe construite sur un autre jeu de domaines — ce
    que fait le banc, et ce que ferait `--domaines` demain — elle rendait
    une liste de clés d'une AUTRE longueur que la liste des corps, et le
    `zip()` de `ecrire()` tronquait la différence **sans un mot** : les
    octets des Pyrénées seraient partis sous le nom `colonnes-nord-alpes`,
    et la coupe alpine aurait affiché de la pluie pyrénéenne. Aucune
    erreur, aucune trace, une carte parfaitement crédible.
    """
    cles = [GABARIT_CLE.format(passe=passe, objet="carte.bin")]
    cles += [GABARIT_CLE.format(passe=passe, objet=f"colonnes-{d}.bin")
             for d in domaines]
    cles.append(GABARIT_CLE.format(passe=passe, objet="manifest.json"))
    return cles


def json_octets(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1).encode("utf-8")


def horodatage(maintenant=None):
    t = maintenant or dt.datetime.now(dt.timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


# ══════════════════════════════════════════════════════════════════════
#  PARTIE PURE — géométrie et temps, testables sans réseau ni clé
# ══════════════════════════════════════════════════════════════════════
def axes_boite(boite=None):
    """Les axes de la boîte ingérée, DÉDUITS DES BORNES.

    ⚠️ Ce ne sont PAS les axes servis : ce sont ceux qu'on ATTEND. Ils
    servent à confronter ce que le portail rend (`verifier_geometrie`),
    et le refus est net. Le piège est déjà payé côté PI le 10/08 : le WCS
    avait rendu 61 × 85 là où la découpe attendait 61 × 84 — une colonne
    d'écart, soit ~1,9 km, et toute la fenêtre décalée sans une seule
    erreur.

    lats DÉCROISSANTES (premier point au NORD), lons croissantes — la
    convention du produit B, et celle du GRIB reçu.
    """
    b = boite or BOITE
    nj = round((b["latmax"] - b["latmin"]) / PAS_DEG) + 1
    ni = round((b["lonmax"] - b["lonmin"]) / PAS_DEG) + 1
    lats = np.round(b["latmax"] - PAS_DEG * np.arange(nj), 4)
    lons = np.round(b["lonmin"] + PAS_DEG * np.arange(ni), 4)
    return lats.astype(np.float32), lons.astype(np.float32)


def verifier_parite(boite=None):
    """⛔ LES DEUX COMPTES DOIVENT ÊTRE PAIRS, et c'est un contrôle, pas
    une convention de confort.

    Le calque réduit par blocs de 2 × 2. Avec un compte impair, le
    dernier bloc n'aurait qu'une ligne (ou qu'une colonne) : sa maille
    couvrirait **deux fois moins de terrain** que ses voisines, à
    l'écran, sans que rien ne le signale. C'est la borne de la boîte
    qu'on ajuste, pas la règle de réduction.
    """
    lats, lons = axes_boite(boite)
    mauvais = [n for n, v in (("latitudes", len(lats)), ("longitudes",
                                                         len(lons)))
               if v % FACTEUR_CALQUE]
    if mauvais:
        raise Abort(
            f"la boîte rend un nombre IMPAIR de {' et de '.join(mauvais)} "
            f"({len(lats)} × {len(lons)}) — le dernier bloc du calque "
            f"serait incomplet et sa maille couvrirait deux fois moins de "
            f"terrain que les autres, en silence. ⚠️ Ajuster une BORNE de "
            f"`BOITE`, jamais la règle de réduction.")
    return True


def fenetre_domaine(nom, boite=None):
    """`(j0, j1, i0, i1)` inclusifs — la découpe d'un domaine AGRUME dans
    la boîte ingérée.

    ⛔ Lève si le domaine DÉBORDE. C'est le contrôle qui a manqué au
    cadrage : A19 écrivait `lonmin = −1,0` alors que le domaine Pyrénées
    descend à −1,80. La coupe pyrénéenne aurait été publiée sur une
    fenêtre tronquée de 80 colonnes — c'est-à-dire une carte juste, plus
    petite, et rien pour le dire.
    """
    b = boite or BOITE
    d = DOMAINES.get(nom)
    if d is None:
        raise Abort(f"domaine inconnu : {nom!r} — connus : "
                    f"{sorted(DOMAINES)}")
    dehors = []
    if d["latmin"] < b["latmin"] - 1e-9: dehors.append("latmin")
    if d["latmax"] > b["latmax"] + 1e-9: dehors.append("latmax")
    if d["lonmin"] < b["lonmin"] - 1e-9: dehors.append("lonmin")
    if d["lonmax"] > b["lonmax"] + 1e-9: dehors.append("lonmax")
    if dehors:
        raise Abort(
            f"le domaine {nom!r} déborde la boîte ingérée par "
            f"{', '.join(dehors)} : domaine {d['latmin']}–{d['latmax']} N × "
            f"{d['lonmin']}–{d['lonmax']} E, boîte {b['latmin']}–"
            f"{b['latmax']} N × {b['lonmin']}–{b['lonmax']} E. ⛔ Publier "
            f"la fenêtre tronquée rendrait une coupe juste sur une emprise "
            f"muette — l'erreur la moins visible de toutes.")
    j0 = round((b["latmax"] - d["latmax"]) / PAS_DEG)
    j1 = round((b["latmax"] - d["latmin"]) / PAS_DEG)
    i0 = round((d["lonmin"] - b["lonmin"]) / PAS_DEG)
    i1 = round((d["lonmax"] - b["lonmin"]) / PAS_DEG)
    return j0, j1, i0, i1


def reduire_max(grille, facteur=FACTEUR_CALQUE):
    """`(…, nj, ni)` → `(…, nj//f, ni//f)` par MAXIMUM du bloc f × f.

    ⛔⛔ MAXIMUM, ET C'EST L'ARBITRAGE DU 20/08. Trois règles étaient
    possibles et elles ne disent pas la même chose au pilote :

      décimation  une averse de 1 km tombée entre deux points gardés
                  DISPARAÎT. C'est ce qu'on fait pour le vent, où le
                  champ est lisse ; pour la pluie c'est un mensonge.
      moyenne     la même averse perd 75 % de son intensité affichée —
                  elle devient invisible alors qu'elle mouille.
      MAXIMUM     ne perd jamais une cellule ; il l'élargit d'au plus
                  1 km. L'erreur va dans le sens prudent, et la coupe
                  (0,01° natif) donne la valeur exacte au point.

    ⚠️ `np.nanmax` sur un bloc entièrement NaN rend NaN **et un
    RuntimeWarning**. On passe donc par `fmax`, qui ignore le NaN quand
    l'autre opérande est fini et rend NaN quand les deux le sont — même
    résultat, sans avertissement et sans masque temporaire.
    """
    a = np.asarray(grille)
    nj, ni = a.shape[-2], a.shape[-1]
    if nj % facteur or ni % facteur:
        raise Abort(
            f"réduction impossible : {nj} × {ni} n'est pas divisible par "
            f"{facteur}. ⚠️ Voir `verifier_parite` — c'est la BORNE de la "
            f"boîte qui s'ajuste.")
    bloc = a.reshape(*a.shape[:-2], nj // facteur, facteur,
                     ni // facteur, facteur)
    return np.fmax.reduce(np.fmax.reduce(bloc, axis=-1), axis=-2)


def echeances(passe):
    """Les 39 tranches d'une passe, chacune avec ses DEUX bornes.

    ⛔⛔ L'INSTANT NOMMÉ EST LA FIN DE LA TRANCHE. Mesuré : l'échéance
    demandée à `passe + 5 min` porte `stepRange = 0m-5m`. La tranche
    couvre donc `]debut, fin]`, et un client qui prendrait `fin` pour le
    début décalerait tout le ruban de 5 minutes — sans qu'une seule
    requête n'échoue.
    """
    t0 = _instant(passe)
    out = []
    for k in range(1, NB_ECHEANCES + 1):
        fin = t0 + dt.timedelta(minutes=PAS_MIN * k)
        out.append(dict(
            rang=k - 1,
            debut_min=PAS_MIN * (k - 1), fin_min=PAS_MIN * k,
            debut=horodatage(fin - dt.timedelta(minutes=PAS_MIN)),
            fin=horodatage(fin),
            instant_demande=horodatage(fin)))
    return out


def heures_entieres(passe):
    """Les heures rondes ENTIÈREMENT couvertes par le ruban de la passe.

    ⛔ REFUS NOMMÉ Nº 3 DU CADRAGE. Sur une fenêtre 05:55 → 09:05, seules
    06→07, 07→08 et 08→09 sont entières. Afficher 40 minutes de pluie
    dans une colonne intitulée « heure » serait exactement le mensonge
    crédible que ce projet pourchasse : la valeur serait juste, l'unité
    fausse, et rien ne le dirait.

    Renvoie une liste de `{heure, rangs}` où `rangs` est la liste des 12
    indices d'échéance à SOMMER. Le calcul se fait ici, une fois, et le
    manifeste le publie — le client n'a pas à refaire l'arithmétique, et
    surtout pas à la refaire différemment.
    """
    t0 = _instant(passe)
    fin_ruban = t0 + dt.timedelta(minutes=HORIZON_MIN)
    premiere = t0.replace(minute=0, second=0, microsecond=0)
    if premiere < t0:
        premiere += dt.timedelta(hours=1)
    out, h = [], premiere
    while h + dt.timedelta(hours=1) <= fin_ruban:
        debut_min = int((h - t0).total_seconds() // 60)
        rangs = [debut_min // PAS_MIN + n for n in range(60 // PAS_MIN)]
        out.append(dict(heure=horodatage(h), rangs=rangs,
                        debut_min=debut_min, fin_min=debut_min + 60))
        h += dt.timedelta(hours=1)
    return out


def _instant(passe):
    return dt.datetime.strptime(passe, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=dt.timezone.utc)


def passes_candidates(maintenant=None, recul_min=10, profondeur_min=30):
    """Les passes plausibles, de la plus FRAÎCHE à la plus ancienne.

    ⚠️ On part de `maintenant − recul_min` parce que la latence de
    publication mesurée le 20/08 vaut **12,6 min** (et 11 à 12,3 min lors
    des sondages précédents). Demander la passe de l'instant même
    coûterait un `NoSuchCoverage` à chaque fois — c'est-à-dire une
    requête perdue, et un message d'erreur qui accuse la publication
    plutôt que l'horloge.

    ⚠️ **Ce chiffre VIEILLIRA.** Il ne décide rien d'irréversible ici :
    il ne fait qu'ordonner les candidates, et la première qui répond
    gagne. Un `recul_min` trop court coûte une requête de plus, jamais un
    trou.
    """
    t = maintenant or dt.datetime.now(dt.timezone.utc)
    t = t.replace(second=0, microsecond=0)
    t -= dt.timedelta(minutes=t.minute % PAS_MIN)
    depart = t - dt.timedelta(minutes=recul_min - recul_min % PAS_MIN)
    return [horodatage(depart - dt.timedelta(minutes=PAS_MIN * n))
            for n in range(profondeur_min // PAS_MIN + 1)]


# ══════════════════════════════════════════════════════════════════════
#  LE CONTENEUR — une passe, prête à être servie
# ══════════════════════════════════════════════════════════════════════
class Passe:
    """Le ruban 0 → 195 min d'une passe, dans les deux jeux d'objets.

        natif : (39, nj, ni) — la boîte ingérée AU PAS SERVI, en mm,
                unités du GRIB (la sentinelle 9999 est encore dedans :
                c'est `quantifier` qui la traite, et par égalité exacte).

    ⚠️ Le tableau est gardé UNE FOIS, au pas natif, et les deux jeux en
    dérivent. Deux constructions indépendantes des mêmes octets, c'est la
    divergence assurée le jour où l'une bouge — le défaut que
    `grille._blocs()` existe pour éviter.
    """

    def __init__(self, passe, natif, lats, lons, boite=None,
                 domaines=DOMAINES_COUPE, latence_min=None):
        self.passe = passe
        self.boite = dict(boite or BOITE)
        self.domaines = tuple(domaines)
        self.latence_min = latence_min
        self.lats = np.asarray(lats, dtype=np.float32)
        self.lons = np.asarray(lons, dtype=np.float32)
        a = np.asarray(natif)
        attendu = (NB_ECHEANCES, len(self.lats), len(self.lons))
        if a.shape != attendu:
            raise Abort(f"ruban {a.shape} au lieu de {attendu}")
        # ⚠️ Quantifié TRANCHE PAR TRANCHE : `quantifier` promeut en
        # float64, et le faire d'un coup sur les 39 échéances coûterait
        # 284 Mo de copie temporaire sur un VPS qui en a 3 300 de libres
        # et qui fait tourner trois autres chaînes.
        self.pluie = np.stack(
            [quantifier(a[k], PARAM_PLUIE_IMMEDIATE)
             for k in range(NB_ECHEANCES)]).astype(np.float16)
        self.echeances = echeances(passe)
        self.heures = heures_entieres(passe)

    # ── Le jeu du CALQUE ──────────────────────────────────────────────
    def carte(self):
        """`(échéance, lat, lon)` au pas du calque — maximum du bloc 2×2."""
        return reduire_max(self.pluie.astype(np.float32)).astype(np.float16)

    def axes_calque(self):
        """⚠️ La coordonnée d'une maille du calque est celle de son
        premier point natif (le coin NORD-OUEST du bloc), pas son centre.
        Publier un centre demanderait d'inventer une demi-maille ; publier
        le coin permet au client de nommer EXACTEMENT les quatre points
        natifs résumés. C'est ce que dit `service.calque.regle`."""
        return (self.lats[::FACTEUR_CALQUE], self.lons[::FACTEUR_CALQUE])

    def octets_par_echeance(self):
        lat_c, lon_c = self.axes_calque()
        return len(lat_c) * len(lon_c) * DTYPE.itemsize

    def carte_bin(self):
        """⛔ L'ÉCHÉANCE EST L'AXE EXTERNE. Le calque sert UN instant à la
        fois et balaie la carte entière ; avec l'échéance dehors il tire
        un seul Range de `octets_par_echeance` (422 ko) et a toute la
        France. Avec la latitude dehors, il en tirerait 401."""
        return np.ascontiguousarray(self.carte(), dtype=DTYPE).tobytes()

    # ── Le jeu de la COUPE ────────────────────────────────────────────
    def octets_par_colonne(self):
        """39 × 2 = 78 octets — toute la colonne temporelle d'un point.

        ⚠️ 78 n'est PAS un multiple de 4, et c'est sans conséquence ici :
        l'objet ne porte aucune tranche float32, donc aucun alignement
        n'est requis. Le dire explicitement évite qu'on « corrige » un
        jour un remplissage qui n'a pas lieu d'être — et qui décalerait
        toutes les colonnes sauf la première."""
        return NB_ECHEANCES * DTYPE.itemsize

    def colonnes_bin(self, nom):
        """Un enregistrement par colonne du domaine, ordre (lat, lon).

        ⚠️ Les échéances sont l'axe le PLUS INTERNE, comme dans le
        `colonnes.bin` du produit B : la coupe lit une série temporelle
        en un point, c'est cette lecture-là qu'on veut contiguë. Un Range
        de 78 octets suffit au ruban entier."""
        j0, j1, i0, i1 = fenetre_domaine(nom, self.boite)
        bloc = self.pluie[:, j0:j1 + 1, i0:i1 + 1]
        nj, ni = bloc.shape[1], bloc.shape[2]
        return np.ascontiguousarray(
            np.moveaxis(bloc.reshape(NB_ECHEANCES, nj * ni), 1, 0),
            dtype=DTYPE).tobytes()

    def axes_domaine(self, nom):
        j0, j1, i0, i1 = fenetre_domaine(nom, self.boite)
        return self.lats[j0:j1 + 1], self.lons[i0:i1 + 1]

    # ── Ce qu'on peut affirmer, et ce qu'on ne peut pas ───────────────
    def remplissage_par_echeance(self):
        """⚠️ PAR ÉCHÉANCE, jamais un chiffre global. Une échéance
        entièrement absente au milieu du ruban se lirait « 97,4 % » dans
        un remplissage global — et ferait un trou de 5 minutes dans une
        animation, à l'endroit exact où le pilote regarde."""
        return [round(float(np.isfinite(
                    self.pluie[k].astype(np.float32)).mean()), 4)
                for k in range(NB_ECHEANCES)]

    def mesures(self):
        """Ce que la passe contient VRAIMENT — pour qu'un champ mort ne
        ressemble pas à une journée sans pluie."""
        a = self.pluie.astype(np.float32)
        fini = np.isfinite(a)
        n = int(fini.sum())
        return dict(
            mailles=int(a.size),
            renseignees=round(n / a.size, 4) if a.size else 0.0,
            part_pluvieuse=(round(float(np.count_nonzero(
                np.where(fini, a, 0.0) > 0.001)) / n, 4) if n else 0.0),
            max_mm_5min=(round(float(np.nanmax(a)), 3) if n else None),
            cumul_max_mm_195min=(round(float(np.nanmax(
                np.where(fini, a, 0.0).sum(axis=0))), 3) if n else None))

    def octets_publies(self):
        total = self.octets_par_echeance() * NB_ECHEANCES
        for nom in self.domaines:
            lat_d, lon_d = self.axes_domaine(nom)
            total += len(lat_d) * len(lon_d) * self.octets_par_colonne()
        return total

    # ── LE MANIFESTE ──────────────────────────────────────────────────
    def manifeste(self, extra=None):
        lat_c, lon_c = self.axes_calque()
        return dict(
            produit=("AGRUME — pluie à venir, ruban 5 min (jetable). "
                     "Deux jeux : calque 0,02° et coupe 0,01° natif."),
            passe=self.passe,
            # ⛔ L'ÂGE N'EST PAS PUBLIÉ, ET C'EST DÉLIBÉRÉ (garde-fou nº 1
            # du §8 bis). Un âge écrit ici périmerait à la lecture : servi
            # depuis un cache, il dirait « 3 min » sur une passe qui en a
            # 40. On publie de quoi le CALCULER — `passe` et `ecrit_le` de
            # l'index — et `ageTexte()` existe déjà côté client.
            age=("NON PUBLIÉ. Se calcule à l'écran : maintenant − `passe`. "
                 "⚠️ Une passe de 13 min et une passe de 40 min ne doivent "
                 "pas se ressembler à l'affichage."),
            source=dict(
                producteur="Météo-France",
                produit="prévision immédiate agrégée (PIAF)",
                licence="Licence Ouverte 2.0 (Etalab)",
                attribution=("Source : Météo-France — prévision immédiate "
                             "agrégée, Licence Ouverte 2.0"),
                note=("⛔ Cette mention est une OBLIGATION de la licence, "
                      "pas une politesse. ⚠️ Et la même licence interdit "
                      "d'appeler « PIAF » ce que ce projet fabrique : on "
                      "cite la source, on ne s'en réclame pas."),
                couverture_wcs=CHAMP_WCS,
                agregation=AGREGATION,
                agregations_publiees=list(AGREGATIONS),
                latence_publication_min=self.latence_min,
                cadence_producteur_min=PAS_MIN,
                cadence_ingestion_min=CADENCE_MIN),
            # ── Le temps ────────────────────────────────────────────
            echeances=self.echeances,
            pas_min=PAS_MIN, horizon_min=HORIZON_MIN,
            convention_temps=(
                "⛔ L'INSTANT NOMMÉ EST LA FIN DE LA TRANCHE. Chaque "
                "valeur est un CUMUL en mm sur `]debut, fin]`, soit 5 "
                "minutes. Mesuré : l'échéance demandée à passe + 5 min "
                "porte `stepRange = 0m-5m`. Prendre `fin` pour le début "
                "décalerait tout le ruban de 5 minutes, sans qu'une seule "
                "requête n'échoue."),
            heures_entieres=self.heures,
            agregat_horaire=(
                "⛔ SOMME des 12 tranches désignées par `rangs`, et de "
                "celles-là seulement. Ce sont des cumuls DISJOINTS de la "
                "même grandeur (`tp`, mm) : la somme est exacte, sans "
                "conversion ni division. ⚠️ Les heures rondes qui ne sont "
                "pas dans cette liste ne sont PAS entièrement couvertes "
                "par le ruban — afficher 40 minutes de pluie dans une "
                "colonne intitulée « heure » serait une valeur juste sous "
                "une unité fausse. ⛔ Et on n'INTERPOLE rien : "
                "`rafraichissement.ts` exclut nommément `precipitation` de "
                "l'interpolation, et cet agrégat ne rouvre pas ce choix — "
                "il SOMME une donnée qui existe."),
            parametre=dict(
                nom=PARAM_PLUIE_IMMEDIATE["nom"],
                unite=PARAM_PLUIE_IMMEDIATE["unite"],
                grandeur=("`tp` — discipline 0, catégorie 1, numéro 52 : "
                          "LE MÊME paramètre que la ligne « Précipitation » "
                          "de la coupe (`quantification.PARAMS_SURFACE`). "
                          "C'est ce qui rend l'agrégat horaire légitime."),
                avertissement_unite=(
                    "⚠️ Le nom de la couverture dit « RATE » et la "
                    "description du portail dit « rainrate ». LA DONNÉE DIT "
                    "AUTRE CHOSE : `typeOfStatisticalProcessing = 1`, "
                    "`stepType = accum`, `units = kg m**-2`. C'est un CUMUL "
                    "en mm. Ne rien diviser par la durée.")),
            # ── La géométrie ────────────────────────────────────────
            boite=dict(self.boite),
            axes=dict(
                nb_lat=len(self.lats), nb_lon=len(self.lons),
                pas_deg=PAS_DEG,
                lat_premier=round(float(self.lats[0]), 4),
                lat_dernier=round(float(self.lats[-1]), 4),
                lon_premier=round(float(self.lons[0]), 4),
                lon_dernier=round(float(self.lons[-1]), 4),
                sens="lats DÉCROISSANTES (premier point au NORD) ; lons croissantes"),
            # ══ CE QUE LE CLIENT DOIT LIRE POUR SERVIR ═══════════════
            service=dict(
                cle_index=CLE_INDEX,
                encodage="aucun — les objets sont BRUTS, Range-ables",
                dtype=DTYPE.name,
                calque=dict(
                    cle=GABARIT_CLE.format(passe=self.passe,
                                           objet="carte.bin"),
                    disposition=("(echeance, lat, lon) little-endian, "
                                 "C-contigu, SANS en-tête"),
                    octets_par_echeance=self.octets_par_echeance(),
                    offset="rang de l'échéance × `octets_par_echeance`",
                    pas_deg=PAS_CALQUE_DEG,
                    nb_lat=len(lat_c), nb_lon=len(lon_c),
                    lat_premier=round(float(lat_c[0]), 4),
                    lat_dernier=round(float(lat_c[-1]), 4),
                    lon_premier=round(float(lon_c[0]), 4),
                    lon_dernier=round(float(lon_c[-1]), 4),
                    regle=(
                        "⛔ MAXIMUM des 4 points natifs (lat, lon), "
                        "(lat, lon+0,01), (lat−0,01, lon), "
                        "(lat−0,01, lon+0,01). La coordonnée publiée est "
                        "celle du coin NORD-OUEST du bloc, jamais un "
                        "centre — nommer un centre demanderait d'inventer "
                        "une demi-maille."),
                    pourquoi_maximum=(
                        "⚠️ Décimer ou moyenner FERAIT DISPARAÎTRE une "
                        "cellule d'averse d'un kilomètre. Le maximum ne "
                        "perd jamais une cellule : il l'élargit d'au plus "
                        "1 km. Le calque SURESTIME donc l'étendue de la "
                        "pluie d'au plus une maille, et ne sous-estime "
                        "jamais son intensité. La valeur exacte AU POINT "
                        "est dans le jeu de la coupe."),
                    pourquoi_pas_0025=(
                        "0,025 / 0,01 = 2,5 : cette maille demanderait "
                        "d'interpoler entre des points publiés. 0,02° est "
                        "un facteur entier.")),
                coupe=dict(
                    gabarit_cle=GABARIT_CLE.format(
                        passe=self.passe, objet="colonnes-{domaine}.bin"),
                    disposition=("un enregistrement par colonne, ordre "
                                 "(lat, lon) — du NORD au sud puis d'ouest "
                                 "en est, comme `zsol` du produit B"),
                    octets_par_colonne=self.octets_par_colonne(),
                    offset="(j × nb_lon + i) × `octets_par_colonne`",
                    pas_deg=PAS_DEG,
                    disposition_interne="(echeance,) — 39 float16 contigus",
                    domaines={
                        nom: dict(
                            nb_lat=len(self.axes_domaine(nom)[0]),
                            nb_lon=len(self.axes_domaine(nom)[1]),
                            lat_premier=round(float(self.axes_domaine(nom)[0][0]), 4),
                            lat_dernier=round(float(self.axes_domaine(nom)[0][-1]), 4),
                            lon_premier=round(float(self.axes_domaine(nom)[1][0]), 4),
                            lon_dernier=round(float(self.axes_domaine(nom)[1][-1]), 4))
                        for nom in self.domaines},
                    note=("⛔ Ces domaines sont EXACTEMENT ceux du produit "
                          "B : la coupe n'est dessinable nulle part "
                          "ailleurs, donc le 0,01° n'est publié nulle part "
                          "ailleurs. Le refus « hors emprise » est donc le "
                          "MÊME que celui du produit B — même géographie, "
                          "même message, rien de neuf à expliquer."))),
            # ══ LA PRÉSÉANCE — publiée, jamais devinée (A17) ═════════
            preseance=(
                "DANS `boite` ET JUSQU'À `horizon_min` : cet objet "
                "REMPLACE la translation du radar par le vent 700 hPa "
                "(`WindShiftedRadarLayer`). Hors de `boite` ou au-delà de "
                "l'horizon, la translation subsiste et DOIT porter son "
                "badge « extrapolé ». ⛔ Le contour de `boite` se dessine : "
                "une couture invisible est une couture qu'on croit "
                "inexistante. ⚠️ Et RainViewer reste, partout : il est le "
                "CONSTAT, cet objet est une PRÉVISION — les deux ne disent "
                "pas la même chose et ne se remplacent pas."),
            # ══ LES REFUS NOMMÉS (§7 du cadrage) ═════════════════════
            refus=[
                dict(quoi="hors emprise",
                     regle="lat/lon hors de `boite` (calque) ou hors des "
                           "domaines de `service.coupe.domaines` (coupe)",
                     dire="l'absence, verbatim — comme `domaine-sans-pi`"),
                dict(quoi="au-delà de l'horizon",
                     regle=f"instant > passe + {HORIZON_MIN} min",
                     dire="la couture doit être VUE, jamais lissée"),
                dict(quoi="heure ronde incomplète",
                     regle="heure absente de `heures_entieres`",
                     dire="pas d'agrégat horaire pour cette colonne"),
                dict(quoi="passe trop vieille",
                     regle="maintenant − `passe` au-delà de ce que le "
                           "produit promet",
                     dire="l'âge, à l'écran — ne jamais servir une "
                          "prévision d'il y a une heure comme si elle "
                          "datait de maintenant"),
                dict(quoi="qualité radar",
                     regle="INCONNUE — le producteur ne la publie pas",
                     dire=("⛔ 256 clés eccodes lues sur un champ réel le "
                           "20/08 : AUCUNE ne porte un indicateur de "
                           "qualité, de confiance ou de couverture radar "
                           "(`is_probability_fcst = 0`, "
                           "`typeOfGeneratingProcess = 2`, "
                           "`productDefinitionTemplateNumber = 8`). Le "
                           "descriptif du produit annonce qu'en dessous de "
                           "74 % de qualité radar la fusion vaut AROME-PI "
                           "seul. **Nous ne pouvons pas savoir quand c'est "
                           "le cas**, et le silence ne vaut pas « qualité "
                           "bonne ». À dire tel quel dans l'aide."))],
            # ══ CE QUE LA BOÎTE CONTIENT VRAIMENT ════════════════════
            couverture=(
                "⚠️ La boîte déborde largement les radars français, et "
                "TOUTES ses mailles sont renseignées — mesuré le 20/08 : "
                "100,00 %, `bitmapPresent = 0`, aucune valeur manquante. "
                "⛔ « Renseigné » ne veut donc PAS dire « vu par un "
                "radar » : hors couverture radar la fusion se réduit au "
                "modèle. Il n'y a aucun moyen publié de savoir où passe "
                "cette frontière, et resserrer la boîte « là où la donnée "
                "est réelle » était impossible pour cette raison — la "
                "question 9.3 du cadrage est close par un NON mesuré."),
            remplissage_par_echeance=self.remplissage_par_echeance(),
            mesures=self.mesures(),
            retention_passes=RETENTION_PASSES,
            octets_publies=self.octets_publies(),
            avertissement=(
                "Produit JETABLE : seules les {n} dernières passes sont en "
                "ligne, et c'est `dernier` dans l'index `{i}` qui désigne "
                "la passe LISIBLE — les {k} objets s'écrivent ensemble ou "
                "pas du tout, et `dernier` n'avance qu'après la dernière "
                "écriture."
            ).format(n=RETENTION_PASSES, i=CLE_INDEX,
                     k=len(cles_de_la_passe(self.passe, self.domaines))),
            **(extra or {}))


# ══════════════════════════════════════════════════════════════════════
#  L'ÉCRITURE, L'INDEX ET LA PURGE
#
#  ⛔ Tout ce bloc reprend `rafraichissement.py` (Lot L2/L3b) SANS le
#  réinventer, parce que ses trois leçons ont été payées :
#    1. l'INDEX s'écrit AVANT la purge — l'inverse laisse, en cas de
#       panne, des objets que rien ne sait plus nommer (`ListObjects`
#       n'est pas une route de ce projet : hors index = invisible et
#       définitivement payé) ;
#    2. `Storage.delete` NE LÈVE JAMAIS, il rend `False` — un
#       `try/except` autour n'attrape rien, et c'est ce qui a fabriqué
#       18 orphelins les 12-13/08 ;
#    3. une écriture PARTIELLE inscrit quand même ses clés dans l'index
#       pour qu'elles soient purgées, et `dernier` NE BOUGE PAS.
# ══════════════════════════════════════════════════════════════════════
INDEX_VIDE = dict(
    produit="AGRUME — index des passes de pluie à venir en ligne",
    retention_runs=RETENTION_PASSES, runs=[], restes=[], dernier={})


def _ecrire_index(st, passe, cles, avancer, journal=print, maintenant=None):
    ecrit_le = maintenant or horodatage()
    index = st.get_json(CLE_INDEX) or dict(INDEX_VIDE)
    dernier = dict(index.get("dernier") or {})
    nouveau, a_supprimer = index_apres(index, passe, FLUX, cles,
                                       retention=RETENTION_PASSES)
    # ⚠️ `grille.index_apres` reconstruit l'index à partir de SON
    # `INDEX_VIDE` — celui du produit B. Sans cette ligne, l'index de ce
    # produit s'intitulerait « AGRUME produit B — index des runs en
    # ligne » : un index qui ment sur ce qu'il indexe. ⓘ C'est déjà le
    # cas des deux index frères (`agrume/pi/grille`,
    # `agrume/pi/rafraichissement`), à corriger là-bas séparément — pas
    # dans ce commit, qui ne doit pas réécrire deux index en production
    # pour une étiquette.
    nouveau["produit"] = INDEX_VIDE["produit"]
    # ⛔ LE GARDE-FOU QUI EMPÊCHE LA PURGE DE DÉBORDER. Le produit A
    # (`agrume/colonnes/`) et les colonnes PI (`agrume/pi/colonnes/`)
    # sont DÉFINITIFS et vivent dans le même bucket. Une seule clé hors
    # du préfixe arrête la purge entière — on ne supprime pas « ce qui
    # est légitime » en continuant.
    verifier_prefixe(a_supprimer, prefixe=PREFIXE)
    if avancer:
        dernier[FLUX] = passe
    nouveau["dernier"] = dernier
    # Le jeton de cache du client : il change à CHAQUE publication, y
    # compris un rejeu sous la même passe — ce que la passe seule ne sait
    # pas dire, puisque les deux générations ont la même longueur.
    nouveau["ecrit_le"] = ecrit_le
    nouveau["note"] = (
        "⛔ `dernier.passe` est LA passe à lire : elle n'avance qu'après "
        "l'écriture de TOUS les objets. `runs` liste ce qui est en ligne "
        "pour la purge et peut contenir une passe incomplète — ne pas le "
        "lire pour choisir quoi servir. ⛔ `ecrit_le` est le JETON DE "
        "CACHE. ⚠️ L'ÂGE se calcule depuis `dernier.passe`, il n'est "
        "jamais publié : publié, il périmerait à la lecture.")
    # ⚠️ `no-store`, comme les index frères. Un index mis en cache ferait
    # lire une passe purgée dix minutes plus tôt : 404 sur les cinq
    # objets, et le client ne saurait pas que c'est le cache et non la
    # rétention.
    st.put(CLE_INDEX, json_octets(nouveau), cache_control="no-store",
           content_type="application/json")
    echecs = []
    for cle in a_supprimer:
        # ⛔ ON LIT LA VALEUR DE RETOUR. `Storage.delete` attrape tout et
        # rend `False` : un `try/except` seul n'attraperait RIEN, `restes`
        # ne se remplirait jamais, et la clé sortirait de l'index à la
        # rotation — un objet EN LIGNE et HORS INDEX. C'est le motif exact
        # des 18 orphelins des 12-13/08.
        try:
            if not st.delete(cle):
                echecs.append(cle)
        except Exception:                                  # noqa: BLE001
            echecs.append(cle)
    if a_supprimer:
        journal(f"     purge : {len(a_supprimer) - len(echecs)} clés "
                f"supprimées"
                + (f", {len(echecs)} échecs (réessayés à la passe suivante)"
                   if echecs else ""))
        # ⚠️ MÊME horodatage que la première écriture : deux jetons
        # différents feraient retélécharger 28,8 Mo pour des octets
        # identiques. Un jeton n'a pas à être frais, il a à être JUSTE.
        st.put(CLE_INDEX, json_octets(index_apres_purge(nouveau, echecs)),
               cache_control="no-store", content_type="application/json")
    return nouveau


def ecrire(st, p, extra=None, journal=print, maintenant=None):
    """Les cinq objets, puis l'index. Dans cet ordre, manifeste en dernier.

    ⛔ TOUT EST SÉRIALISÉ AVANT LA PREMIÈRE ÉCRITURE. Sérialiser pendant
    l'envoi laisserait une fenêtre où une erreur de forme arriverait
    APRÈS que `carte.bin` soit déjà en ligne.
    """
    from storage import CACHE_REECRIT                     # noqa: PLC0415
    # ⛔ `CACHE_REECRIT`, pas `CACHE_IMMUABLE` : la clé porte la passe,
    # mais un rejeu sous la même passe réécrit les mêmes clés. Et
    # `CACHE_IMMUABLE` vaut SIX HEURES pour un objet dont la rétention
    # est de vingt minutes — un cache qui survit à l'objet qu'il décrit
    # est précisément la forme du défaut du 13/08.
    cles = cles_de_la_passe(p.passe, p.domaines)
    # ⛔ PAS DE `zip` NU ICI. `zip` s'arrête à la plus courte des deux
    # listes, sans un mot : c'est comme ça que le défaut ci-dessus
    # (`cles_de_la_passe` en dur) écrivait les octets d'un domaine sous
    # le nom d'un autre. Le contrôle explicite coûte une ligne.
    if len(cles) != len(p.domaines) + 2:
        raise Abort(
            f"{len(cles)} clés pour {len(p.domaines)} domaines + carte + "
            f"manifeste. ⛔ Les deux listes ne se correspondent plus — "
            f"écrire quand même ferait partir les octets d'un domaine sous "
            f"le nom d'un autre.")
    corps = [(cles[0], p.carte_bin(), "application/octet-stream")]
    # ⓘ Pas de `strict=True` : il n'existe qu'à partir de Python 3.10 et
    # ce banc tourne aussi sur le Python du Mac. Le contrôle explicite
    # ci-dessus fait le même travail et dit POURQUOI.
    for nom, cle in zip(p.domaines, cles[1:-1]):
        corps.append((cle, p.colonnes_bin(nom), "application/octet-stream"))
    corps.append((cles[-1], json_octets(p.manifeste(extra)),
                  "application/json"))

    ecrites = []
    try:
        for cle, octets, mime in corps:
            st.put(cle, octets, cache_control=CACHE_REECRIT,
                   content_type=mime)
            ecrites.append(cle)
    except Exception:
        if ecrites:
            journal(f"  ⚠️ écriture PARTIELLE ({len(ecrites)}/{len(corps)}) — "
                    f"les clés écrites entrent dans l'index pour être "
                    f"PURGÉES, et `dernier` ne bouge pas : personne ne lira "
                    f"une passe dépareillée.")
            try:
                _ecrire_index(st, p.passe, ecrites, avancer=False,
                              journal=journal, maintenant=maintenant)
            except Exception as e:                         # noqa: BLE001
                journal(f"  ⛔ …et l'index n'a pas pu être mis à jour "
                        f"({type(e).__name__}: {e}) : {len(ecrites)} objet(s) "
                        f"HORS INDEX, donc invisibles. À supprimer à la main.")
        raise
    journal(f"  ✅ passe écrite : {PREFIXE}{p.passe}/ "
            f"({p.octets_publies() / 1e6:.1f} Mo, {len(corps)} objets)")
    _ecrire_index(st, p.passe, [c for c, _, _ in corps], avancer=True,
                  journal=journal, maintenant=maintenant)
    return cles


def passe_en_ligne(st):
    """La passe LISIBLE, ou None. ⛔ Par `dernier`, jamais par `runs` :
    `runs` peut contenir une passe incomplète."""
    index = st.get_json(CLE_INDEX) or {}
    return (index.get("dernier") or {}).get(FLUX)
