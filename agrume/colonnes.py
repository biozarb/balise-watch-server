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

from domaine import (G, GRID_3D, GRID_FINE, NIVEAUX_P,  # noqa: F401
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
#
# ⚠️ 12/08 — `cc` ARRIVE ICI, ET C'EST LE SEUL CHAMP QUI VIENNE D'UN
# AUTRE PAQUET. Il est le prérequis de la vue de coupe : sans lui,
# `web/src/lib/profile.ts::cloudLayers` rend une liste vide, et son
# propre commentaire dit « liste vide = ciel clair sur la colonne ».
# La coupe n'afficherait donc pas un trou mais une AFFIRMATION fausse.
PARAMS_ISO = (
    dict(nom="u", court="u", court_10m=None, paquet="IP1", unite="m/s",
         decalage=0.0, tolerance=0.02),
    dict(nom="v", court="v", court_10m=None, paquet="IP1", unite="m/s",
         decalage=0.0, tolerance=0.02),
    dict(nom="t", court="t", court_10m=None, paquet="IP1", unite="°C",
         decalage=-273.15, tolerance=0.05),
    dict(nom="r", court="r", court_10m=None, paquet="IP1", unite="%",
         decalage=0.0, tolerance=0.05),
    # ⚠️⚠️ FRACTION → POURCENTAGE, ET LA CONVERSION EST ÉCRITE ICI.
    # Inventaire eccodes du 12/08 sur `0025/IP2` : `paramId = 248`,
    # `name = "Fraction of cloud cover"`, `units = "(0 - 1)"`. Le front,
    # lui, raisonne en pourcentage — `Sample.cloud` est commenté « % » et
    # `cloudLayers` a un seuil par défaut de 40. Servir la fraction telle
    # quelle donnerait un ciel clair permanent (0,85 < 40), sans erreur
    # ni trou : c'est exactement le mode de panne que ce lot combat.
    # Le facteur vit dans le descripteur, comme le décalage des kelvins,
    # pour que `quantifier()` reste le seul endroit qui convertisse.
    #
    # ⛔⛔ ET ELLE VAUT ZÉRO À L'ÉCHÉANCE 0 — MESURÉ, PAS SUPPOSÉ.
    # Sur les runs 2026-08-12T15Z et 12Z, `bitsPerValue = 0` sur les
    # 24 niveaux à τ = 0 : le champ est CONSTANT, et sa constante est 0.
    # Au même instant `clwc` (eau liquide nuageuse) n'est PAS nul — donc
    # ce n'est pas la météo, c'est l'analyse qui ne diagnostique pas la
    # nébulosité. Un zéro n'est pas une absence : servi tel quel il dit
    # « ciel clair » à l'échéance que le pilote regarde en PREMIER.
    # Même traitement que la TKE, mais ACTIF : il faut le mettre à NaN,
    # pas seulement constater qu'il manque.
    dict(nom="cc", court="cc", court_10m=None, paquet="IP2", unite="%",
         facteur=100.0, decalage=0.0, tolerance=0.5, absent_a_tau0=True),
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
                    "tke": 500.0, "cc": 100.0, "zp": 20000.0,
                    # ── Surface (étape 12 bis) ────────────────────────
                    # ⚠️ Les plafonds portent sur la valeur APRÈS facteur
                    # et décalage : `psol` est en hPa, `pression_mer` en
                    # hPa MOINS 1000, `rayonnement` déjà en W/m².
                    "t2m": 100.0, "td2m": 100.0, "rafale": 200.0,
                    "nuages_bas": 100.0, "nuages_moyens": 100.0,
                    "nuages_hauts": 100.0, "cape": 20000.0,
                    "couche_limite": 12000.0, "rayonnement": 1500.0,
                    # ⛔ `precipitation` et `rayonnement` sont CUMULÉS à
                    # l'ingestion : le plafond doit accepter le cumul du
                    # run entier, pas la valeur horaire. 51 h de pluie
                    # continue à 30 mm/h resterait sous 2 000 mm ; le
                    # rayonnement cumulé, lui, est ramené en W/m² par le
                    # facteur AVANT ce contrôle, donc 1 500 suffirait à
                    # peine — d'où 40 000, soit ~11 h de plein soleil
                    # cumulées avant division. `deaccumuler()` ramènera
                    # le tout dans les clous.
                    "precipitation": 2000.0,
                    "pression_mer": 200.0, "psol": 1200.0}

# ⚠️ Le plafond de `rayonnement` s'applique au CUMUL divisé par 3 600,
# pas à la valeur horaire. Écrit à part pour que la raison reste lisible.
PLAFOND_PHYSIQUE["rayonnement"] = 40000.0

# Paramètre fictif décrivant l'altitude géopotentielle, pour que
# `quantifier()` lui applique les mêmes garde-fous qu'aux autres (NaN,
# sentinelle, plafond physique) sans la faire passer par le float16.
#
# ⚠️⚠️ 12/08 — LA DIVISION PAR `G` EST DEVENUE UN `facteur`, ET C'EST UNE
# CORRECTION, PAS UN DÉPLACEMENT DE CONFORT.
#
# Elle vivait dans `ingest_colonnes.py`, APPLIQUÉE AVANT `quantifier()`.
# Deux conséquences, la seconde mesurée le 12/08 :
#
#  1. La sentinelle passait au travers. `IP1` porte un bitmap : 17,18 %
#     des points France entière valent 9 999 (les coins de la boîte
#     lat/lon, hors du domaine réel d'AROME — mesuré sur le run 15 Z).
#     Divisée par `G` avant le contrôle, la sentinelle vaut **1 019,6 m**
#     — sous le seuil 9 999 ET sous le plafond de 20 000. Un point
#     manquant devenait donc une ALTITUDE PLAUSIBLE, identique à tous les
#     niveaux, sans rien pour l'attraper. ⓘ Aucun des 227 points archivés
#     n'y tombe aujourd'hui (le plus proche est à 447 km), mais le
#     produit B découpe des DOMAINES, et les balises isolées comme les
#     radiosondages sont hors domaine par construction.
#  2. Le produit B aurait eu besoin de sa propre division — donc une
#     SECONDE écriture de la conversion, exactement ce que l'ancien
#     commentaire (« la conversion est écrite ici et nulle part
#     ailleurs ») cherchait à empêcher.
#
# ⛔ Corollaire à ne jamais perdre : `ingest_colonnes.py` NE DOIT PLUS
# diviser. Diviser deux fois donne 331 m à 700 hPa au lieu de 3 240 —
# plausible au premier coup d'œil. `test_colonnes.py` rejoue le chemin
# complet et exige ~3 240 m.
# ══════════════════════════════════════════════════════════════════════
#  LES CHAMPS DE SURFACE — étape 12 bis, 13/08/2026
# ══════════════════════════════════════════════════════════════════════
#  ⛔ POURQUOI ILS ARRIVENT, ET CE QU'ILS DÉBLOQUENT.
#  La vue de coupe n'affiche pas qu'une colonne d'air : sous la grille,
#  `ProfileSurface` porte treize séries — température et point de rosée à
#  2 m, vent et rafale à 10 m, nuages bas/moyens/hauts, CAPE, rayonnement,
#  pression sol et pression mer, précipitations. AGRUME n'en portait
#  AUCUNE. Le 6ᵉ onglet aurait eu une colonne d'air complète et une ligne
#  de surface vide.
#
#  ⚠️ Et l'une d'elles, `sp`, n'est pas décorative : c'est l'ANCRE BASSE
#  de la pression dérivée. Sans elle, la pression des niveaux hauteur
#  situés sous le premier isobare émergé — les ~230 premiers mètres sur
#  la colonne médiane du domaine, c'est-à-dire la tranche du décollage —
#  serait EXTRAPOLÉE. Avec elle, chaque niveau est encadré des deux côtés.
#
#  ── ⛔⛔ TROIS SÉMANTIQUES DE TEMPS DANS DEUX PAQUETS ─────────────────
#  Inventaire eccodes du 13/08 sur le run 15 Z. `stepType` et `stepRange`
#  ne sont PAS de la décoration : trois conventions cohabitent, et les
#  confondre donne des nombres parfaitement lisibles.
#
#    instant      2t 2d sp prmsl blh CAPE_INS lcc mcc hcc
#                 la valeur À l'échéance. rien à faire.
#    max          max_i10fg, `stepRange` 0-1, 1-2, 2-3…
#                 le MAXIMUM sur l'heure écoulée. déjà horaire.
#    accum        tp, ssrd, `stepRange` 0-1, 0-2, 0-3…
#                 ⛔ CUMULÉ DEPUIS LE DÉBUT DU RUN, pas sur l'heure.
#
#  ⚠️ Servir `tp` tel quel donnerait une pluie horaire QUI NE DÉCROÎT
#  JAMAIS — une courbe lisse, croissante, et fausse. Servir `ssrd` tel
#  quel donnerait 3 116 368 « W/m² » (mesuré à +6 h), absurde donc
#  attrapable ; mais divisé par 3 600 sans différence, il donnerait 865
#  W/m² à 19 h TU un 12 août, ce qui ne l'est pas.
#  La dé-accumulation est faite UNE FOIS, à la fin, sur le tableau
#  complet (`Grille.deaccumuler`) — jamais au fil des messages, où il
#  faudrait espérer que l'échéance précédente soit déjà arrivée.
#
#  ⚠️ `lcc`, `mcc`, `hcc`, `tp`, `ssrd` et `max_i10fg` sont ABSENTS à
#  l'échéance 0 (mesuré). Après la TKE et la nébulosité isobare, c'est la
#  troisième famille dans ce cas : à τ = 0 le modèle ne diagnostique ni
#  nuage, ni cumul, ni maximum.
#
#  ⚠️ `CAPE_INS` porte `typeOfLevel = "unknown"` — le filtre doit
#  l'accepter explicitement au lieu de tester un type de niveau.
#
#  ⓘ Le produit A n'est PAS touché : ces champs n'entrent que dans le
#  produit B. Le produit A est une archive DÉFINITIVE dont le format
#  engage pour des années ; le produit B ne survit pas à trois runs. On
#  ne modifie pas le premier pour un besoin du second.
PARAMS_SURFACE = (
    dict(nom="t2m", court="2t", paquet="SP1", unite="°C",
         decalage=-273.15, pas_de_temps="instant"),
    dict(nom="td2m", court="2d", paquet="SP2", unite="°C",
         decalage=-273.15, pas_de_temps="instant"),
    dict(nom="rafale", court="max_i10fg", paquet="SP1", unite="m/s",
         decalage=0.0, pas_de_temps="max_horaire", absent_a_tau0=True),
    dict(nom="nuages_bas", court="lcc", paquet="SP2", unite="%",
         decalage=0.0, pas_de_temps="instant", absent_a_tau0=True),
    dict(nom="nuages_moyens", court="mcc", paquet="SP2", unite="%",
         decalage=0.0, pas_de_temps="instant", absent_a_tau0=True),
    dict(nom="nuages_hauts", court="hcc", paquet="SP2", unite="%",
         decalage=0.0, pas_de_temps="instant", absent_a_tau0=True),
    dict(nom="cape", court="CAPE_INS", paquet="SP2", unite="J/kg",
         decalage=0.0, pas_de_temps="instant", sans_type_de_niveau=True),
    dict(nom="couche_limite", court="blh", paquet="SP2", unite="m",
         decalage=0.0, pas_de_temps="instant"),
    # ⚠️ J/m² cumulés → W/m² moyens sur l'heure : la DIFFÉRENCE puis
    # ÷ 3 600. Le facteur est ici, la différence dans `deaccumuler()`.
    dict(nom="rayonnement", court="ssrd", paquet="SP1", unite="W/m²",
         facteur=1.0 / 3600.0, decalage=0.0, pas_de_temps="cumul",
         absent_a_tau0=True),
    dict(nom="precipitation", court="tp", paquet="SP1", unite="mm",
         decalage=0.0, pas_de_temps="cumul", absent_a_tau0=True),
    # ⚠️ Pa → hPa, et décalage de 1000 : sans lui le float16 coûterait
    # 0,25 hPa (mesuré sur 200 000 tirages dans la plage réelle du
    # domaine, 630 → 996 hPa). Avec, 0,125. Les deux sont trop.
    # ⛔⛔ LES DEUX DÉCALAGES NE SONT PAS LE MÊME, ET LES CONFONDRE SE
    # PAIE DE 1 000 hPa (13/08).
    #
    #   `decalage`            — conversion d'UNITÉ. Après lui, l'archive
    #                           EST dans l'unité publiée. K → °C en est
    #                           l'exemple : `unite="°C"`, et la valeur
    #                           archivée est bien des °C.
    #   `decalage_precision`  — décalage de PRÉCISION, pris uniquement
    #                           pour gagner des bits de float16. Après
    #                           lui, l'archive N'EST PLUS dans l'unité
    #                           publiée, et LE CLIENT DOIT LE DÉFAIRE.
    #
    # Ils vivaient dans le même champ jusqu'au 13/08, et le manifeste ne
    # publiait que `unite`. Un client qui suivait le manifeste à la lettre
    # affichait donc −13 hPa au lieu de 987 — une valeur fausse, finie,
    # tracée sans une erreur. `decalage_precision` est publié ; celui qui
    # ne le lit pas doit REFUSER de servir la valeur.
    #
    # Le gain, mesuré sur 200 000 tirages dans la plage réelle du domaine :
    # 0,125 hPa d'erreur float16 avec le décalage, 0,250 sans.
    dict(nom="pression_mer", court="prmsl", paquet="SP1", unite="hPa",
         facteur=0.01, decalage=0.0, decalage_precision=-1000.0,
         pas_de_temps="instant"),
)

# ⛔⛔ LA PRESSION AU SOL EST EN float32, ET C'EST LE MÊME ARBITRAGE QUE
# `ziso`, POUR LA MÊME RAISON — mesuré, pas déduit.
#
# Elle n'est pas une valeur affichée parmi d'autres : c'est l'ANCRE d'un
# axe sur lequel on interpole. Sur la plage réelle du domaine
# (630 → 996 hPa, mesuré le 13/08), le float16 coûte :
#
#     sans décalage        0,2500 hPa  ≈ 2,10 m
#     décalage −1000 hPa   0,1250 hPa  ≈ 1,05 m
#     float32              0,00002 hPa
#
# À comparer à l'erreur de la pression DÉRIVÉE qu'elle sert à ancrer :
# 0,016 hPa sur un écart d'ancres de 230 m. Stocker l'ancre en float16
# coûterait donc huit à quinze fois plus que la dérivation elle-même —
# du bruit exactement là où on cherche du signal, comme pour `ziso`.
# Le prix : 20,7 Ko par échéance et par domaine.
PARAM_PRESSION_SOL = dict(nom="psol", court="sp", paquet="SP2", unite="hPa",
                          facteur=0.01, decalage=0.0,
                          pas_de_temps="instant")

PARAM_ALTITUDE = dict(nom="zp", court="z", court_10m=None, paquet="IP1",
                      unite="m", facteur=1.0 / G, decalage=0.0,
                      tolerance=0.5)


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
        # ⚠️ Les points de RADIOSONDAGE sont hors du domaine par
        # construction (cf. `domaine.py`) : ce sont les seuls points de
        # l'axe qui ne soient pas des balises, et c'est leur `source` qui
        # les fait entrer, pas leur position. Rien d'autre ne change pour
        # eux : `index_plats()` indexe la grille NATIVE, donc leur colonne
        # s'extrait exactement comme les autres.
        if (s.get("source") != "radiosondage"
                and not dans_domaine(s["lat"], s["lon"])):
            continue
        out.append(dict(id=str(s["id"]), lat=float(s["lat"]),
                        lon=float(s["lon"]), nom=s.get("name", ""),
                        source=s.get("source", ""),
                        position_suspecte=str(s["id"]) in sus))
    # ⚠️ C'EST CE TRI-CI QUI DÉFINIT L'AXE DE L'ARCHIVE — pas celui de
    # `freeze_balises.py`, qui ne range que le fichier figé pour qu'il se
    # relise. Les deux existent et n'ont PAS la même clé (chaîne ici,
    # numérique là-bas) : constaté le 10/08, laissé en l'état parce que
    # changer celui-ci changerait l'ordre des archives à venir sans
    # changer celui des archives déjà écrites.
    # ⓘ Effet de bord heureux : « RS-06610 » se range après tous les
    # identifiants numériques ('R' > '9' en ASCII), donc les points de
    # radiosondage arrivent EN FIN d'axe et ne décalent aucune balise
    # existante. C'est ce qu'on veut — mais c'est une propriété du tri
    # ASCII, pas une garantie écrite : `test_radiosondage.py` la vérifie.
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
    """float64 (unité GRIB) → float16 (unité d'archive).

        archive = brut × `facteur` + `decalage`

    Les points manquants (NaN, ou la sentinelle 9999 d'eccodes) et les
    valeurs physiquement absurdes deviennent NaN — jamais 0, qui serait
    une valeur de vent parfaitement crédible.

    ⚠️ Le garde-fou 19/07 de `arome-wind/ingest.py::_ms` s'applique ici
    aussi : en échantillonnant au pas natif on touche des points que la
    décimation sautait, dont d'éventuels points manquants.

    ⚠️⚠️ LA SENTINELLE SE TESTE SUR LA VALEUR BRUTE ET PAR ÉGALITÉ
    EXACTE. Deux choses ont changé le 12/08, et chacune corrige un tort :

    **Sur la valeur BRUTE**, parce que la conversion est maintenant ici :
    tester après aurait ramené 9 999 à 1 019,6 m pour le géopotentiel
    (÷ G) ou à 999 900 % pour la nébulosité (× 100), c'est-à-dire un
    nombre qui ne ressemble plus à une sentinelle.

    **PAR ÉGALITÉ EXACTE** — `== 9999.0` et non `>= 9999` — parce que le
    géopotentiel BRUT dépasse la sentinelle partout : `z` vaut ~29 400
    m²/s² à 700 hPa et ~74 700 à 400. Un `>=` sur le brut effacerait
    l'axe vertical en entier. Et l'égalité exacte est ce que la
    sentinelle EST : eccodes rend précisément `missingValue` (9 999,0 sur
    ces fichiers, vérifié) aux points couverts par le bitmap. Ce n'est
    pas un seuil d'invraisemblance — c'est un drapeau. L'invraisemblance,
    elle, est le rôle de `PLAFOND_PHYSIQUE`, qui s'applique APRÈS
    conversion et que chaque paramètre renseigne.

    ⓘ Mesuré le 12/08 sur `0025/IP1` et `0025/IP2` du run 15 Z : le
    bitmap couvre 17,18 % des points France entière — les coins de la
    boîte lat/lon, hors du domaine réel d'AROME — et **0 point** dans les
    fenêtres nord-alpes et pyrenees.
    """
    a = np.asarray(valeurs, dtype=np.float64)
    mauvais = ~np.isfinite(a) | (a == SENTINELLE)
    a = (a * param.get("facteur", 1.0) + param["decalage"]
         + param.get("decalage_precision", 0.0))
    plafond = PLAFOND_PHYSIQUE.get(param["nom"])
    if plafond is None:
        raise KeyError(
            f"`{param['nom']}` n'a pas de plafond physique. ⚠️ Ce n'est "
            f"pas un oubli anodin : depuis le 12/08 le plafond est le "
            f"SEUL garde-fou contre une valeur absurde, la sentinelle ne "
            f"vérifiant plus qu'une égalité exacte. Ajouter une entrée "
            f"dans `PLAFOND_PHYSIQUE`.")
    mauvais |= np.abs(a) > plafond
    a = np.where(mauvais, np.nan, a)
    return a.astype(dtype)


def erreur_quantification(valeurs, param, dtype=np.float16):
    """Erreur maximale introduite par la quantification, dans l'unité
    d'archive. Sert au banc : on MESURE la perte plutôt que de la
    supposer — c'est ainsi qu'on a vu qu'une température en kelvins perd
    un facteur 8, et qu'une altitude en float16 perd 8 mètres à 7 000."""
    a = (np.asarray(valeurs, dtype=np.float64) * param.get("facteur", 1.0)
         + param["decalage"] + param.get("decalage_precision", 0.0))
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
