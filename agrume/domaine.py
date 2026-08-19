#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/domaine.py — les constantes d'AGRUME, en UN SEUL endroit
#                                                        (10/08/2026)
#
#  AGRUME = AGRégation Unifiée Multi-Échelles. Nom de travail, assumé
#  comme provisoire. ⚠️ On n'utilise PAS « PIAF » : c'est la désignation
#  d'un produit opérationnel Météo-France (Prévision Immédiate Agrégée
#  Fusionnée), sur le même domaine métier et à partir des mêmes données ;
#  la Licence Ouverte 2.0 interdit explicitement d'induire un tiers en
#  erreur sur la source ou la nature de l'information réutilisée.
#
#  ⚠️ POURQUOI CE FICHIER EXISTE. Le projet a DÉJÀ été mordu par une
#  constante dupliquée : `LEVELS` vit à la fois dans
#  `arome-wind/ingest.py` et dans `web/src/lib/config.ts`
#  (`WIND_GRID_LEVELS`), sans code partagé — « les deux listes doivent
#  bouger ensemble, sinon le sélecteur d'altitude propose des paliers
#  dont les tuiles n'existent plus (404 silencieux, calque vide) ».
#  AGRUME touche DEUX grilles, DEUX paquets d'orographie et TROIS
#  produits : si ces valeurs se dispersent, la même erreur reviendra en
#  pire. Tout ce qui est commun est ici, et AGRUME publie sa liste de
#  niveaux DANS son manifeste — le client ne la recopie jamais.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

# ── Le miroir S3 public d'OVH ─────────────────────────────────────────
# ⚠️ Ce n'est NI le portail WCS de Météo-France, NI data.gouv.fr. C'est
# le miroir des paquets PNT, SANS CLÉ et sans quota, déjà utilisé par
# `arome-wind/ingest.py` depuis l'origine. Deux propriétés mesurées le
# 10/08 qui décident de l'architecture :
#   • débit 20,9 Mo/s sur un bundle de 818 Mo (n = 1). ⚠️ Le chiffre de
#     9,2 Mo/s publié le matin même portait sur un fichier de 75 Mo où
#     l'établissement de connexion dominait — un débit mesuré sur un
#     petit fichier n'est pas un débit ;
#   • rétention 118 runs en ligne, du 26/07 au 10/08, soit ~14,7 jours —
#     CINQ FOIS la rétention du portail (4,25 j mesurés). Le S3 est donc
#     aussi la route du rattrapage et du rejeu.
S3 = "https://meteofrance-pnt.s3.rbx.io.cloud.ovh.net"
MODEL_DIR = "arome"

# ── Les deux grilles, et ce que chacune porte VRAIMENT ────────────────
# ⛔ FAIT MESURÉ LE 10/08, ET IL COMMANDE TOUT LE LOT : la grille 0,01°
# n'expose que QUATRE niveaux hauteur (10, 20, 50, 100 m). Les 25 niveaux
# (10 → 3000 m) n'existent QU'EN 0,025°. Vérifié deux fois, par deux
# routes indépendantes qui concordent au niveau près :
#   • inventaire eccodes du GRIB réel `arome__001__HP1__00H__…` (75,1 Mo,
#     20 messages) : `u` `v` `ws` `wdir` sur 20/50/100 m seulement ;
#   • `DescribeCoverage` du WCS : `upperCorner … 100` en 001 contre
#     `upperCorner … 3000` en 0025.
# Le 0,025° n'est donc PAS un repli — c'est la seule option pour la 3D
# au-dessus de 100 m. La documentation Météo-France dit le contraire :
# ne pas la croire sur ce point.
GRID_FINE = "001"      # 0,01°  — 2801 × 1791
GRID_3D = "0025"       # 0,025° — 1121 × 717

# Niveaux hauteur au-dessus du sol MODÈLE, mesurés à l'inventaire eccodes
# le 10/08. ⚠️ La liste publiée dans une première version du lot portait
# un niveau `2 m` en tête : il N'EXISTE PAS. La plus basse est 10 m, et
# le vent y est servi à partir de 20 m — les 10 m viennent des champs
# dédiés `10u`/`10v`.
NIVEAUX_H_0025 = (10, 20, 35, 50, 75, 100, 150, 200, 250, 375, 500, 625,
                  750, 875, 1000, 1125, 1250, 1375, 1500, 1750, 2000,
                  2250, 2500, 2750, 3000)
NIVEAUX_H_001 = (10, 20, 50, 100)

# ✅ Le « cadeau caché », CONFIRMÉ PAR LA MESURE (DescribeCoverage sur le
# WCS AROME-PI 0025, 10/08) : les 6 niveaux d'AROME-PI sont EXACTEMENT
# 10, 20, 50, 100, 250, 500 — et tous les six sont dans les 25 d'AROME.
# La grille de PI est `1121 × 717 @ 0,025°`, STRICTEMENT identique à
# celle d'AROME 0025. Le composite du §4.3 ne demande donc NI
# interpolation verticale, NI rééchantillonnage horizontal.
NIVEAUX_H_AROMEPI = (10, 20, 50, 100, 250, 500)

# ── Les niveaux ISOBARES, et pourquoi on n'en garde que 14 sur 24 ─────
# Inventaire eccodes du 10/08 sur `0025/IP1` : 24 niveaux, de 1000 à
# 100 hPa. ⚠️ Ils n'existent QU'EN 0,025° — la grille fine n'expose aucun
# isobare (vérifié).
NIVEAUX_P_TOUS = (1000, 950, 925, 900, 850, 800, 750, 700, 650, 600, 550,
                  500, 450, 400, 350, 300, 275, 250, 225, 200, 175, 150,
                  125, 100)

# Ce qu'on archive : la bande 1000 → 400 hPa.
#
# ⚠️ LE HAUT EST FIXÉ PAR LE RACCORD, PAS PAR LE PLAFOND DU PILOTE. La
# tentation est de couper à 500 hPa (~5 600 m), « bien au-dessus du
# plafond parapente » — c'est le raisonnement qui a fait retirer 600 et
# 500 hPa du calque vent le 30/07. **Il serait faux ici.** Le raccord du
# §3.3 sert les isobares SEULES au-dessus de `z_s + 3000 m`, et la balise
# la plus haute du domaine a un sol modèle à ~3 200 m : sa bande
# « isobares seules » commence donc vers 6 200 m, soit ~440 hPa. Couper à
# 500 laisserait un TROU en haut des colonnes les plus hautes — et
# seulement sur celles-là, donc invisible sur un échantillon de plaine.
# 400 hPa (~7 200 m) couvre `z_s + 3000` pour toutes les balises du
# domaine, avec de la marge pour le mélange.
#
# Le bas descend à 1000 hPa alors que ces niveaux sont sous le terrain
# partout dans les Alpes : c'est volontaire. On ARCHIVE tout et on masque
# à la LECTURE — même principe que les deux mailles. Un niveau souterrain
# archivé permet de vérifier que le masquage fonctionne ; un niveau
# souterrain jeté à l'ingestion ne permet plus rien.
NIVEAUX_P = (1000, 950, 925, 900, 850, 800, 750, 700, 650, 600, 550,
             500, 450, 400)
assert set(NIVEAUX_P) <= set(NIVEAUX_P_TOUS)

# g normalisé (m/s²) — `z` est un GÉOPOTENTIEL en m²/s², pas une hauteur.
# altitude_ASL = z / G. Oublier la division donne des altitudes ~9,8 fois
# trop grandes, ce qui se voit ; l'inverse (diviser deux fois) donne des
# altitudes plausibles au premier coup d'œil, ce qui ne se voit pas.
G = 9.80665
assert set(NIVEAUX_H_AROMEPI) <= set(NIVEAUX_H_0025), (
    "les niveaux d'AROME-PI doivent être un sous-ensemble de ceux d'AROME "
    "— sinon la jonction PI ↔ AROME demande une interpolation verticale, "
    "et tout le §4.3 du lot H change")
assert set(NIVEAUX_H_001) <= set(NIVEAUX_H_0025), (
    "les 4 niveaux de la maille fine doivent être un sous-ensemble des 25 "
    "— c'est ce qui rend le raccord hybride du §4.1 bis possible")

# ── Où vit l'orographie du modèle : ⚠️ LE PAQUET CHANGE AVEC LA GRILLE ─
#
#   grille | paquet | fichier      | `h` présent
#   -------|--------|--------------|---------------------------------
#   001    | SP3    | __00H__      | ✅ (2 messages en tout)
#   0025   | SP2    | __00H06H__   | ✅ (1 seul message sur 79)
#   0025   | SP3    | __00H06H__   | ⛔ ABSENT (flux et rayonnement)
#
# ⚠️ C'EST LE PIÈGE LE PLUS COÛTEUX DU LOT, et il est SILENCIEUX. Le code
# existant (`arome-wind/ingest.py::load_orography`) cherche `SP3` + `h` ;
# porté tel quel en 0025, il ne trouverait rien — et `0025/SP3` existe
# bel et bien (67 messages, 55 Mo), il ne contient que des flux et du
# rayonnement plus 13 champs `unknown` qui se révèlent être de
# l'humidité. Donc pas d'erreur 404 pour alerter : juste une orographie
# absente, et `altitude_ASL = ALTITUDE + h_AGL` qui part sans plancher.
#
# Ce que ça coûte, mesuré aux 648 balises le 10/08 :
#   ECART z_0025 − z_001 (m) : d1 −102 · q1 −30 · MÉDIANE 0 · q3 +28 ·
#   d9 +88 ; |écart| médian 30 m ; 125 balises (19 %) au-delà de 100 m ;
#   28 au-delà de 200 m ; extrême +643 m (Signal de Soi).
# Pas de biais systématique, mais une dispersion considérable : sur UNE
# BALISE SUR CINQ, se tromper de grille décale la colonne entière de
# plus de 100 m, verticalement, sans qu'aucun test ne s'allume.
PAQUET_OROGRAPHIE = {
    GRID_FINE: ("SP3", "__00H__"),
    GRID_3D:   ("SP2", "__00H06H__"),
}

# ── Où vivent les isobares : TOUT est dans IP1 ────────────────────────
# Inventaire eccodes du 10/08 sur les cinq paquets IP :
#   IP1 (3,60 Go) : u v t r **z**      ← tout ce dont le raccord a besoin
#   IP2 (0,97 Go) : cc ciwc clwc crwc cswc
#   IP3 (5,72 Go) : dpt pv q w wdir ws wz
#   IP4 (0,44 Go) : tke (isobares !)
#   IP5 (1,15 Go) : absv papt vo — et `z` sur des niveaux de VORTICITÉ
#
# ⚠️ LE PIÈGE EST DANS IP5. Le géopotentiel `z` y existe aussi, mais sur
# `typeOfLevel = potentialVorticity` (niveaux 1500 et 2000), qui n'a
# strictement rien à voir. Un filtre sur le seul `shortName == "z"`
# ramasserait ces deux messages et fabriquerait des altitudes absurdes
# au milieu du profil. **Le `typeOfLevel` fait partie du filtre, pas de
# la décoration.**
PAQUET_ISOBARES = "IP1"

# ── 12/08 : `IP2` entre, pour la nébulosité et pour elle seule ────────
# ⚠️ C'EST LE SEUL TÉLÉCHARGEMENT NEUF DU LOT 12. `IP1` était déjà tiré
# par le produit A ; la découpe d'un domaine coûte une vue numpy (7,6 s
# contre 7,9 s sans, mesuré le 10/08). Mesuré le 12/08 sur le run 15 Z,
# bundles 00H06H → 19H24H : 122 + 110 + 112 + 106 = **450 Mo sur 0–24 h**,
# et le plus gros bundle fait 122 Mo, donc très en dessous du pic disque
# de 815 Mo déjà atteint par HP1 — le disque ne bouge pas.
#
# ⚠️ On ne retient que `cc` des cinq champs d'`IP2` (cc ciwc clwc crwc
# cswc). Les quatre autres décrivent les contenus en eau et en glace :
# utiles un jour pour un givrage, inutiles à la coupe, et ils
# doubleraient le tableau isobare pour rien.
PAQUET_NEBULOSITE = "IP2"

# Les paquets dont le filtre isobare s'occupe. ⚠️ C'est un ENSEMBLE et
# non plus une constante unique : `ingest_colonnes.py` décide de la
# branche de traitement (`poser_isobare`) sur l'appartenance à cet
# ensemble. Un `paquet == PAQUET_ISOBARES` laissé quelque part enverrait
# les messages d'`IP2` dans la branche des niveaux HAUTEUR, où
# `typeOfLevel = isobaricInhPa` ne correspond à rien : ils seraient
# silencieusement ignorés, et `cc` resterait NaN partout.
PAQUETS_ISOBARES = (PAQUET_ISOBARES, PAQUET_NEBULOSITE)

# ── 13/08 : les deux paquets de SURFACE ───────────────────────────────
# ⛔ ILS N'ARRIVENT PAS POUR « COMPLÉTER » LE PRODUIT. Ils arrivent parce
# que la ligne de surface de la vue de coupe (`ProfileSurface`, treize
# séries) n'avait AUCUNE source dans AGRUME, et parce que `sp` est
# l'ancre basse sans laquelle la pression des niveaux hauteur situés sous
# le premier isobare émergé — la tranche du décollage — serait
# extrapolée au lieu d'être encadrée.
#
# Inventaire eccodes du 13/08 sur le run 15 Z, bundles 00H06H :
#   SP1 (56 Mo) : 10u 10v 10si 10wdir · 2t 2r · max_i10fg (rafale)
#                 prmsl · ssrd (rayonnement) · tp (pluie) · tgrp tsnowp
#   SP2 (41 Mo) : 2d · **sp** · lcc mcc hcc · CAPE_INS · blh · h · t
#
# ⓘ `0025/SP2` était déjà connu du projet : c'est le paquet dont
# `freeze_orographie.py` tire le champ `h`. Il n'était simplement jamais
# téléchargé PAR RUN.
#
# ⚠️ ~388 Mo de plus sur 0–24 h (4 bundles × 97 Mo), après les 450 Mo
# d'`IP2`. Le pic disque ne bouge pas — 56 Mo au plus, contre les 815 Mo
# déjà atteints par `HP1`. Le chiffre à surveiller reste la DURÉE
# d'ingestion : 16,1 min avant ce lot, alerte à 30.
PAQUET_SURFACE_1 = "SP1"
PAQUET_SURFACE_2 = "SP2"
PAQUETS_SURFACE = (PAQUET_SURFACE_1, PAQUET_SURFACE_2)

# ── LES PAQUETS DE L'INGESTION, EN UN SEUL ENDROIT (audit du 13/08) ──
# ⛔ Cette liste existait DEUX fois : les huit paquets dans
# `ingest_colonnes.PAQUETS`, et seulement QUATRE dans
# `poller.PAQUETS_PRODUIT_A` — la liste d'avant les étapes 5, 12 et
# 12 bis, jamais rattrapée. Le poller déclenchait donc le workflow dès
# que les quatre anciens paquets étaient publiés ; si IP1/IP2/SP1/SP2
# 0,025° traînaient, `choisir_run()` retenait un run PLUS ANCIEN — perte
# de fraîcheur silencieuse, voyant au vert. Deux listes qui « doivent
# bouger ensemble » sont exactement ce que ce fichier existe pour
# empêcher (cf. `LEVELS`, payé une fois déjà).
# L'ordre et les couples (grille, paquet) sont ceux de l'ingestion ; le
# détail mesuré de chaque paquet (volumes, pièges eccodes) reste
# documenté sur place dans `ingest_colonnes.py`.
PAQUETS_INGESTION = (
    (GRID_3D, "HP1"),
    (GRID_3D, "HP2"),
    (GRID_FINE, "HP1"),
    (GRID_FINE, "SP1"),
    (GRID_3D, PAQUET_ISOBARES),
    (GRID_3D, PAQUET_NEBULOSITE),
    (GRID_3D, PAQUET_SURFACE_1),
    (GRID_3D, PAQUET_SURFACE_2),
)

# ── ⛔ LES PAQUETS DE LA RALLONGE — UN SOUS-ENSEMBLE (14/08) ──────────
# La rallonge du produit B (25 → MAX_HOURS_GRILLE) ne remplit QUE la
# grille 0,025° : `ingerer()` coupe la maille fine à l'horizon de
# l'ARCHIVE, c'est écrit noir sur blanc dans `ingest_colonnes.py`
# (« LA MAILLE FINE S'ARRÊTE À L'HORIZON DE L'ARCHIVE »).
#
# ⛔ La première version du 13/08 exigeait pourtant la couverture des
# HUIT paquets au-delà de +24 h, `001/HP1` et `001/SP1` compris. La
# rallonge était donc conditionnée à la publication de deux paquets dont
# elle ne lit pas un octet — elle attendait pour rien, et elle serait
# tombée à zéro le jour où Météo-France cesserait de publier la maille
# fine au-delà de l'horizon de l'archive, SANS QU'AUCUNE ERREUR NE SORTE
# (le message « aucune échéance au-delà de +24 h » est un ⓘ, pas un ⚠️).
#
# ⚠️ Elle reste dérivée de `PAQUETS_INGESTION`, jamais recopiée : un
# paquet 0,025° ajouté à l'ingestion entre ici tout seul.
PAQUETS_RALLONGE = tuple((g, p) for g, p in PAQUETS_INGESTION if g == GRID_3D)

# ── Le domaine ALPES (ex « Nord-Alpes ») ──────────────────────────────
# ⚠️ Ce n'est pas un choix de confort, c'est ce qui rend le produit B
# possible : la France entière en 0,025° fait 803 757 points par niveau,
# le domaine en fait 11 655. La formule (Nj × Ni sur le pas de 0,025°)
# est celle qui rendait exactement 5 185 sur l'ancienne boîte, 8 405 sur
# les Pyrénées et 2 856 sur Tarn/Aveyron/Hérault — vérifiée trois fois
# contre des découpes de GRIB réels.
#
# ⚠️ Les bornes sont INCLUSIVES et l'appartenance se teste sur les
# coordonnées, jamais sur des indices codés en dur — les indices se
# recalculent depuis les métadonnées du GRIB (cf. `fenetre()`), sinon un
# changement de domaine de Météo-France passerait inaperçu.
#
# ══════════════════════════════════════════════════════════════════════
#  ⛔⛔ 16/08/2026 — CE DOMAINE A ÉTÉ ÉLARGI, ET L'INTERDIT DE LE FAIRE
#  EST LEVÉ ICI, PAS EFFACÉ. Il vaut la peine d'être raconté en entier :
#  le commentaire de `DOMAINE_PYRENEES` (12/08) disait « ÉLARGIR `DOMAINE`
#  AURAIT CHANGÉ LE SHA256 DE L'OROGRAPHIE DE PRODUCTION — DONC ROMPU LA
#  COMPARABILITÉ DE TOUTES LES ARCHIVES DÉJÀ ÉCRITES ». C'était juste le
#  12/08. Deux faits l'ont périmé, et aucun des deux n'est un
#  assouplissement de la règle :
#
#    1. ⚠️ L'ARCHIVE N'EST PLUS PERMANENTE. Depuis le 13/08 le produit A
#       est en rétention glissante 7 jours. Ce que le sha256 protégeait —
#       la comparabilité d'archives éternelles — s'évapore de toute façon
#       en une semaine. Ce qui reste éternel, ce sont les SCORES, et les
#       scores portent sur des VALEURS, pas sur un nom de fichier.
#
#    2. ⛔ ET LES VALEURS NE BOUGENT PAS. Élargir la fenêtre ne déplace
#       AUCUN point de grille : `fenetre()` s'aligne sur la grille native
#       et `Orographie.z_at()` cherche le plus proche voisin. Le sol servi
#       à une balise donnée est le MÊME octet avant et après.
#       ⓘ Ce n'est pas un raisonnement, c'est une mesure : le banc
#       `--comparer-orographie` de `freeze_orographie.py` compare, balise
#       par balise, le sol rendu par l'ancien artefact et par le nouveau.
#       Écart max mesuré au regel du 16/08 : **0,000 m sur 123 balises**.
#
#  ⚠️ CE QUI REMPLACE L'INTERDIT N'EST DONC PAS « RIEN », C'EST UNE PREUVE
#  PLUS FORTE QUE CELLE QU'IL DONNAIT. Un sha256 inchangé prouve qu'on n'a
#  pas touché au fichier ; le banc prouve qu'on n'a pas touché aux
#  ALTITUDES, ce qui est la seule chose dont dépende un pilote. ⛔ La règle
#  qui reste, et qui n'a pas bougé : **on n'élargit pas un domaine sans
#  rejouer ce banc et publier son écart max.** Un élargissement silencieux
#  reste exactement aussi interdit qu'avant.
#
#  ⓘ Ce que ça change, mesuré sur le catalogue Pioupiou live du 16/08
#  (747 balises) : 123 → 205 balises servies par le produit B. Le
#  déclencheur est un pilote à Bernex (Haute-Savoie) dont la balise —
#  1479, Pointe de Pelluaz, 46,3385 N — tombait 4,3 km au NORD de l'ancien
#  `latmax`. ⛔ Et une zone d'intérêt n'y pouvait rien : elle ne donne
#  qu'un sol pour le produit A, alors que l'onglet AGRUME lit le produit B
#  (`localiserAgrume()` lève `hors-couverture` sur les bornes du
#  manifeste). Pour qu'AGRUME marche quelque part, il faut que la BOÎTE
#  contienne le point — il n'y a pas de demi-mesure possible.
#
#  Coût, chiffré depuis les mesures du 13/08 (254 Mo publiés pour 5 185
#  colonnes nord-alpes, 413 Mo pour 8 405 pyrénées → 49 ko/colonne/run,
#  les deux concordent à 0,2 % près) :
#      colonnes    5 185 → 11 655       (+6 470)
#      publié/run    254 Mo → 571 Mo    (+317 Mo)
#      résident R2, 3 runs × 3 domaines : 2,42 Go → 3,37 Go / palier 10 Go
#  ⚠️ LE POSTE À SURVEILLER RESTE LA DURÉE, PAS LE STOCKAGE — 20,97 min
#  mesurés le 13/08 (alerte à 30, timeout 60), et ce chiffre est d'AVANT
#  l'ajout de `tarn-aveyron-herault`. Le téléchargement (21 Go) ne bouge
#  pas d'un octet, c'est la publication qui grossit. Si un run passe
#  30 min, c'est ici qu'il faut revenir — et le §MAX_HOURS_GRILLE dit déjà
#  que la rallonge 51 h avait mangé la moitié de cette marge.
#
#  ⚠️ Le nom « nord-alpes » est CONSERVÉ partout — clé de `DOMAINES`,
#  préfixe R2 `agrume/grille/nord-alpes/`, `orographie-nord-alpes.npz`,
#  `DOMAINES_AGRUME` côté client. Il ment désormais un peu (la boîte
#  descend au Mercantour), et c'est le moindre mal : le renommer casserait
#  les clés R2 des runs en ligne, l'index publié et le client déployé, en
#  échange de zéro gain fonctionnel. Même arbitrage que
#  `balises-nord-alpes.json`, qui porte les Pyrénées depuis le 12/08.
# ══════════════════════════════════════════════════════════════════════
#
# Le choix des quatre bords, mesuré sur le catalogue live du 16/08 :
#   latmax 46,45 — le Chablais et la rive française du Léman (Pelluaz
#                  46,3385 · Windbird 2147 46,3799). Monter à 46,60
#                  ajouterait 17 balises, mais suisses (Fribourg, Vaud).
#   latmin 43,70 — le Verdon et l'arrière-pays niçois (Baouroux 43,7812 ·
#                  Gréolières 43,8004 · Coursegoules 43,8015).
#   lonmin 5,00  — le Ventoux et les Baronnies (Saint-Amand 5,0694 ·
#                  Le Graveyron 5,0760). ⛔ Ne pas descendre sous 3,96 :
#                  c'est `lonmax` de `DOMAINE_TAH`.
#   lonmax 7,60  — le Mercantour et la Roya (Col de Tende 7,5706 ·
#                  Cagnourine 7,5965).
DOMAINE = dict(latmin=43.70, latmax=46.45, lonmin=5.00, lonmax=7.60)

# ── Le SECOND domaine : les Pyrénées (12/08/2026) ─────────────────────
# ⚠️ CE N'EST PAS UN ÉLARGISSEMENT DU PREMIER, ET LA DIFFÉRENCE EST TOUT.
# Élargir `DOMAINE` aurait changé le sha256 de l'orographie de production
# — donc rompu la comparabilité de toutes les archives déjà écrites. Un
# SECOND domaine laisse le premier strictement intact : même bornes, même
# artefact, même sha, mêmes colonnes qu'hier.
# ⓘ 16/08 — ET C'EST TOUJOURS LE BON ARGUMENT POUR LES PYRÉNÉES, même si
# `DOMAINE` a bel et bien été élargi depuis (cf. son commentaire). Les
# deux cas ne se ressemblent pas : les Pyrénées sont à 400 km des Alpes,
# la boîte qui couvrirait les deux ferait 60 000 colonnes de vide entre
# elles. Ce qui a changé le 16/08 n'est pas « on peut élargir », c'est
# « on peut élargir EN PROUVANT que les altitudes servies ne bougent
# pas ». Fusionner deux massifs éloignés reste, lui, une mauvaise idée
# pour une raison qui n'a rien à voir avec le sha256 : le budget.
#
# ⛔ ET LES PYRÉNÉES N'ONT PAS LA FORME DES ALPES. Mesuré le 12/08 sur les
# 648 balises du catalogue : 76 balises dans la bande 42-44 N × −2,5-3,5 E,
# mais étalées sur 480 km d'est en ouest ET 200 km du nord au sud
# (piémont, Montagne Noire, arrière-pays basque). Toute boîte qui les
# couvre TOUTES fait 18 500 colonnes — 3,6 × les Alpes pour 40 % de
# balises en MOINS, soit 5 fois moins dense. Découper en deux ou trois
# boîtes ne rend que 22 %, pour deux ou trois orographies, index et purges.
#
# ✅ RETENU : une boîte sur la CHAÎNE elle-même. Le coût marginal par
# balise gagnée explose dès qu'on monte vers le nord — mesuré :
#     42,40-43,40 N →  8 405 col, 55 balises   (1,62 × les Alpes)
#     42,40-43,50 N →  9 225 col, 59 balises   (+820 col pour 4 balises)
#     42,30-43,80 N → 12 505 col, 65 balises   (+4 100 col pour 10)
#
# ⚠️ CE QUE LA BOÎTE LAISSE DEHORS : 21 balises de piémont, de Montagne
# Noire et d'arrière-pays basque. Leur colonne est extractible
# (l'indexation se fait sur la grille NATIVE, pas sur la fenêtre) — c'est
# leur SOL qui manquait. ✅ Traité le 12/08 par `ZONES_INTERET` plus bas :
# elles reçoivent une petite fenêtre de sol et entrent dans l'archive.
# ⛔⛔ 13/08 — ELLES N'Y SONT JAMAIS ENTRÉES EN FAIT :
# `balises_du_domaine()` ne recopie pas `hors_domaine`, donc `isolees`
# est toujours vide et l'archive porte 182 points, pas 227. Constaté à
# l'audit, consigné sur décision de Yann, PAS corrigé — les runs déjà
# archivés resteront à 182. ⛔ Elles n'entrent PAS dans le produit B : pas
# de calque, pas de coupe, hors grille 3D.
DOMAINE_PYRENEES = dict(latmin=42.40, latmax=43.40, lonmin=-1.80, lonmax=3.30)

# ── Le TROISIÈME domaine : Tarn / Aveyron / Hérault (15/08/2026) ──────
# Demande Yann. Étude complète dans le projet Claude (« balise watch » —
# `agrume-faisabilite-tarn-aveyron-herault-15-08.md` et
# `agrume-forme-boite-tarn-aveyron-herault-15-08.md`) : reverse-geocoding
# PRÉCIS (polygones INSEE réels via `geo.api.gouv.fr/communes`, jamais un
# simple test de boîte — l'API d'adresses `api-adresse.data.gouv.fr` rate
# systématiquement les sites de vol, trop loin de toute adresse) du
# catalogue Pioupiou live : **30 balises** dans les trois départements
# visés (Tarn 9 · Aveyron 5 · Hérault 16).
#
# ⛔ LA BOÎTE ÉVIDENTE (englobant les 30) CHEVAUCHE `DOMAINE_PYRENEES` —
# deux balises d'Hérault (Lespignan, Puisserguier) sont même DÉJÀ dans la
# boîte pyrénéenne. `verifier_domaines_disjoints()` l'aurait refusée.
#
# ✅ RETENU : coupe à `latmin=43.43`, une marge de 0,03° (~3,3 km)
# au-dessus de `DOMAINE_PYRENEES` — plus du double du rayon d'ambiguïté
# d'une demi-maille déjà mesuré dans ce fichier (1,4 km, cas de la balise
# 1661/LFMG). Résultat : **26 balises, 34 × 84 = 2 856 colonnes**
# (formule vérifiée : elle rend exactement 5 185 sur Nord-Alpes et 8 405
# sur les Pyrénées). Densité 110 col/balise — meilleure que les
# Pyrénées (153) pour un volume R2 plus petit encore (~0,35 Go estimé,
# contre ~1,0 Go/domaine mesuré le 13/08 sur les Pyrénées).
#
# ⚠️ CE QUE LA BOÎTE LAISSE DEHORS, ET POURQUOI :
#   · Lespignan et Puisserguier (Hérault sud) sont déjà dans la boîte
#     Pyrénées — rien à faire ici, à vérifier séparément qu'elles y
#     entrent bien à la prochaine régénération de l'axe.
#   · Agde et Bessan (Hérault côtier, lon 3,41–3,45) tombent dans le
#     « trou » entre les deux boîtes. Déjà couvertes par la zone
#     d'intérêt `pyrenees-large` (lat 42-44 × lon -2,5-3,5) : rien à
#     ajouter, elles entreront en balises isolées (sol seulement).
#   · Saujac (Aveyron, isolée à 44,49 N / 1,89 E, à côté du Lot) ferait
#     passer `latmax` à 44,49 pour la SEULE inclure : +756 colonnes pour
#     1 balise, densité 134 au lieu de 110 — le même verdict que « le
#     coût marginal explose » déjà mesuré sur les Pyrénées le 12/08.
#     Laissée hors de la boîte de production ; couverte en zone
#     d'intérêt dédiée (cf. `ZONES_INTERET["tah-nord-ouest-isolees"]`)
#     pour ne pas la perdre pour autant côté archive/score.
DOMAINE_TAH = dict(latmin=43.43, latmax=44.26, lonmin=1.88, lonmax=3.96)

# ⚠️ L'ORDRE COMPTE POUR `domaine_de()` — pas pour le résultat (les
# domaines sont disjoints, `verifier_domaines_disjoints()` l'exige), mais
# pour la lisibilité des journaux. Nord-Alpes d'abord : c'est le domaine
# historique, celui dont les archives remontent au 10/08.
DOMAINES = {"nord-alpes": DOMAINE, "pyrenees": DOMAINE_PYRENEES,
            "tarn-aveyron-herault": DOMAINE_TAH}

# ══════════════════════════════════════════════════════════════════════
#  ⛔ OÙ AROME-PI EXISTE VRAIMENT — arbitrage A9 de Yann, 17/08/2026
# ══════════════════════════════════════════════════════════════════════
#  ⚠️⚠️ CE N'EST PAS UN RÉGLAGE, C'EST UNE MESURE. `ingest_pi.py`
#  n'ingère que la boîte Nord-Alpes, et ça s'est vu dans la DONNÉE avant
#  de se voir dans le code : **207 balises servies sur les 288 de
#  l'archive** le 17/08, aucune Pyrénées, aucune Tarn/Aveyron/Hérault.
#
#  ⛔ Cette constante existe parce que la portée de PI était écrite NULLE
#  PART et déductible seulement d'un `from domaine import DOMAINE` au
#  milieu d'`ingest_pi.py`. Conséquence payée le 17/08 : le run venté a
#  soufflé sur le Roussillon, c'est-à-dire exactement là où PI n'existe
#  pas, et personne ne l'a su avant de chercher pourquoi le composite ne
#  se laissait pas juger.
#
#  ⛔ ELLE A TROIS LECTEURS, ET C'EST TOUT L'INTÉRÊT :
#    · `ingest_pi.py`   — ce qu'il va chercher au portail ;
#    · `grille.py`      — ce que le manifeste du produit B PUBLIE sur la
#                         disponibilité de PI, domaine par domaine ;
#    · `rafraichissement.py` — ce qu'il refuse de fabriquer ailleurs.
#  Recopier « nord-alpes » dans l'un des trois serait le défaut `LEVELS`
#  du projet, à l'identique : deux listes qui doivent bouger ensemble.
#
#  ⚠️ Étendre PI aux deux autres boîtes est un LOT À PART, à chiffrer en
#  quota : 300 requêtes par run et par boîte (2 paramètres × 6 niveaux ×
#  25 échéances), 24 runs par jour. Ce n'est pas un octet de stockage,
#  c'est un budget de portail.
#
# ══════════════════════════════════════════════════════════════════════
#  ⛔⛔ 19/08/2026 — LOT M : LE LOT À PART A EU LIEU, ET SON CHIFFRAGE A
#  DÉMENTI SA PROPRE PRÉMISSE. Arbitrage A13 de Yann.
# ══════════════════════════════════════════════════════════════════════
#  Le paragraphe ci-dessus posait la bonne question — « combien de
#  requêtes ? » — et la mauvaise réponse : « 300 PAR BOÎTE ». Les deux
#  options ont été MESURÉES le 19/08 sur le run PI 14 Z, depuis le VPS,
#  run complet, rien écrit :
#
#      3 boîtes séparées   926 requêtes réelles   9,40 min   11,0 Mo
#      1 boîte englobante  304 requêtes réelles   3,06 min   27,7 Mo
#
#  Et les DEUX rendent EXACTEMENT les mêmes fenêtres après découpe :
#  111×105 · 41×205 · 34×84, sur les trois orographies gelées, sur les
#  300 champs, sans un refus. **Les produits écrits sont donc octet pour
#  octet les mêmes ; seul le chemin d'approvisionnement change.**
#
#  ⛔ POURQUOI L'ARGUMENT DE `DOMAINE_PYRENEES` NE S'APPLIQUE PAS ICI,
#  ALORS QU'IL RESTE JUSTE POUR AROME. « La boîte qui couvrirait les
#  deux ferait 60 000 colonnes de vide entre elles » parle du produit
#  STOCKÉ, où la boîte EST le produit. Pour PI la boîte ne décide que du
#  TRANSPORT : on recoupe en trois fenêtres juste après le décodage
#  (0,5 s pour 300 champs, mesuré), et rien de mort n'est écrit nulle
#  part. La ressource rare de cette chaîne est le QUOTA, pas la bande
#  passante — c'est écrit depuis le 10/08 dans `ingest_pi.py` (« ce
#  n'est pas le volume qui gêne, c'est l'OCCUPATION PERMANENTE DU
#  QUOTA »). L'option qui gaspille 63 % des octets occupe le quota
#  3 minutes par heure au lieu de 9,4 : c'est elle qui préserve la
#  ressource rare.
#
#  ⓘ Effet de bord mesuré, et il a tranché le périmètre : la boîte
#  englobant Alpes + Pyrénées contient DÉJÀ tout Tarn/Aveyron/Hérault
#  (42,40–46,45 N × −1,80–7,60 E). Ajouter TAH coûte **zéro requête et
#  zéro octet** — d'où « les deux d'un coup », et non « Pyrénées
#  d'abord ».
#
#  ⚠️ CE QUE CETTE OPTION NE REND PAS GRATUIT, et qu'il faut surveiller :
#  le payload par requête grossit avec la SURFACE de la boîte englobante
#  (mesuré : 4 288 o pour TAH, 17 662 pour Nord-Alpes, 92 356 pour
#  l'englobante, 1 099 000 pour la France entière). Un quatrième domaine
#  très éloigné (Vosges, Corse) élargirait la boîte sans rien coûter en
#  requêtes mais multiplierait les octets. Le plafond dur est la France
#  entière : 330 Mo/run, 7,9 Go/jour — pas un mur, mais le jour où on
#  s'en approche, c'est ICI qu'il faut revenir.
DOMAINES_PI = ("nord-alpes", "pyrenees", "tarn-aveyron-herault")

# ⛔⛔ LA MARGE N'EST PAS UN CONFORT, ELLE CORRIGE UN REFUS MESURÉ.
#
# Le WCS rend les points STRICTEMENT DANS la boîte demandée ; `fenetre()`
# arrondit au point de grille le PLUS PROCHE, donc parfois vers
# l'EXTÉRIEUR. Tant que les quatre bornes d'un domaine tombent sur la
# grille 0,025° les deux coïncident — c'est le cas de `DOMAINE`
# (43,70 / 46,45 / 5,00 / 7,60) et de `DOMAINE_PYRENEES`
# (42,40 / 43,40 / −1,80 / 3,30), vérifié le 19/08 : 111×105 et 41×205
# rendus, attendus, alignés.
#
# ⛔ `DOMAINE_TAH` (43,43 / 44,26 / 1,88 / 3,96) n'a AUCUNE de ses quatre
# bornes sur la grille. Mesuré le 19/08 sans marge : le WCS rend
# **33 × 84 − 1 = 33 × 83** là où l'orographie gelée attend 34 × 84, et
# `aligner_sur_axes()` REFUSE, écart maximal 0,025001° — soit exactement
# un pas de grille, soit 2,78 km de décalage sur tout le domaine.
#
# ⚠️ LA RÉPONSE N'EST PAS D'ÉLARGIR LA TOLÉRANCE D'ALIGNEMENT. C'est
# écrit dans le message d'erreur de `pi.py` et ça reste vrai mot pour
# mot : un décalage d'un point rendrait un delta PI−AROME lisse,
# plausible et faux partout. La réponse est de DEMANDER PLUS LARGE et de
# laisser `aligner_sur_axes()` recouper — un pas de grille suffit, aucun
# point servi ne bouge, et ça coûte le liseré (4 288 → 4 823 o/champ sur
# TAH, mesuré).
#
# ⓘ Elle est appliquée MÊME quand les bornes tombent juste : une marge
# conditionnelle serait un garde-fou qui s'éteint tout seul le jour où
# quelqu'un déplace une borne de 0,01°.
MARGE_PI_DEG = 0.03


def boite_pi(noms=None, marge=MARGE_PI_DEG):
    """La boîte à DEMANDER au portail — ⛔ pas celle qu'on sert.

    L'englobante des domaines de `DOMAINES_PI`, élargie de `marge`. Elle
    est CALCULÉE et jamais écrite en dur : une englobante recopiée
    cesserait d'englober au premier domaine ajouté, et le symptôme
    serait un `aligner_sur_axes()` qui refuse — bruyamment, heureusement,
    mais un run perdu quand même.

    ⚠️ Ce que cette boîte contient EN PLUS des trois domaines n'est pas
    servi, pas écrit, pas stocké : c'est jeté à la découpe, dans la même
    seconde. 63 % de ses colonnes sont mortes, et c'est le prix assumé
    de l'arbitrage A13 (cf. `DOMAINES_PI`).
    """
    noms = list(DOMAINES_PI if noms is None else noms)
    if not noms:
        raise ValueError("aucun domaine PI — il n'y a pas de boîte à demander")
    boites = [DOMAINES[n] for n in noms]
    return dict(latmin=min(b["latmin"] for b in boites) - marge,
                latmax=max(b["latmax"] for b in boites) + marge,
                lonmin=min(b["lonmin"] for b in boites) - marge,
                lonmax=max(b["lonmax"] for b in boites) + marge)

#: Pourquoi PI n'est pas là, en une phrase SERVIE AU CLIENT. ⛔ Publiée
#: plutôt que déduite d'une absence : « pas de champ » et « champ absent
#: pour une raison connue » ne se lisent pas pareil, et l'écran doit
#: pouvoir DIRE la seconde. Même discipline que `resolutionTemporelleMin`.
#: ⚠️ 19/08 — LE TEXTE A CHANGÉ AVEC LA PORTÉE, ET C'EST LE POINT DE
#: CETTE CONSTANTE. Depuis le Lot M, `DOMAINES_PI` porte les trois
#: domaines de production : plus aucun domaine ne reçoit cette phrase
#: aujourd'hui. Elle reste, et elle reste JUSTE, parce que le jour où un
#: quatrième domaine entrera dans `DOMAINES` sans entrer dans
#: `DOMAINES_PI`, l'écran devra pouvoir dire pourquoi — et le dire avec
#: le bon chiffrage, pas avec celui d'avant-hier.
POURQUOI_PAS_DE_PI = (
    "AROME-PI est ingéré sur {couverts}. Le domaine {domaine} n'en "
    "reçoit aucun champ — ce n'est pas une panne ni un trou de données, "
    "c'est la portée actuelle de l'ingestion. L'étendre demande "
    "d'élargir la boîte demandée au portail : depuis le 19/08/2026 "
    "l'ingestion tire UNE boîte englobante et la recoupe par domaine, "
    "donc le coût est en octets par requête, plus en requêtes par "
    "boîte.")


def pi_couvre(domaine):
    """PI est-il ingéré sur ce domaine ? ⛔ La seule façon de le savoir."""
    return domaine in DOMAINES_PI

# ── LES ZONES D'INTÉRÊT — ⛔ CE NE SONT PAS DES DOMAINES ──────────────
# Une zone d'intérêt ne découpe AUCUNE grille, ne produit AUCUN artefact
# de production, et rien de ce qui est servi à un pilote n'en dépend
# géométriquement. Elle répond à une seule question : **quelles balises
# méritent qu'on aille leur chercher un sol alors qu'elles tombent hors
# de toutes les boîtes ?**
#
# ⚠️ POURQUOI CETTE NOTION EXISTE, ET POURQUOI ELLE EST DANGEREUSE SANS
# CE COMMENTAIRE. Les boîtes de production sont dimensionnées par le
# budget du produit B — la grille jetable. Le produit A, lui, est une
# archive PAR BALISE : `quantification.index_plats()` indexe la grille
# NATIVE France entière, donc extraire la colonne d'une balise hors
# boîte ne coûte rien de plus. Seul son SOL manque. Laisser 21 sites de
# vol pyrénéens hors de l'archive à cause du budget d'un produit
# jetable, ce serait laisser le jetable commander ce qui NOURRIT LES
# SCORES — exactement l'inverse de l'ordre voulu.
# ⚠️ 13/08 : l'archive n'est plus « permanente » (rétention glissante
# 7 j), mais l'argument ne bouge pas d'un pouce — ce sont les SCORES
# qu'elle nourrit qui sont éternels, et un site absent de l'archive est
# un site que rien ne notera jamais.
#
# ⛔ CE QUE CES BALISES N'ONT PAS, ET IL FAUT LE DIRE : elles auront un
# profil vertical (produit A), jamais de calque ni de coupe (produit B).
# Elles sont hors grille 3D, et le resteront tant que la boîte ne bouge
# pas.
ZONES_INTERET = {
    "pyrenees-large": dict(latmin=42.0, latmax=44.0, lonmin=-2.5, lonmax=3.5),
    # 15/08/2026 — la balise 2109 (Saujac, Aveyron) et sa voisine 1662
    # (Montblond, Lot) : coût marginal trop élevé pour la boîte de
    # production `tarn-aveyron-herault` (cf. le commentaire de
    # `DOMAINE_TAH`), mais elles ne perdent pas pour autant leur sol —
    # petite fenêtre dédiée, resserrée pour ne rien avaler d'autre.
    "tah-nord-ouest-isolees": dict(latmin=44.40, latmax=44.60,
                                   lonmin=1.75, lonmax=2.00),
    # 15/08/2026 — repérées en vérifiant le compte final de
    # `tarn-aveyron-herault` (23 balises mesurées contre 25-26 annoncées
    # dans l'étude de forme — l'étude vérifiait qu'aucune balise d'un
    # AUTRE département ne tombait dans la boîte, pas que toutes les
    # balises des 3 départements ciblés y tombaient). Deux balises
    # géométriquement hors de toute boîte et de toute zone existante :
    "tah-est-castries": dict(latmin=43.63, latmax=43.73,
                              lonmin=3.96, lonmax=4.06),
    # 549 · BAC Castries (Hérault, 43.682/4.010) — juste à l'est de
    # `lonmax` de `tarn-aveyron-herault`, trou comparable à Agde/Bessan.
    "tah-nord-kaymard": dict(latmin=44.49, latmax=44.60,
                              lonmin=2.43, lonmax=2.53),
    # 2177 · Puech de Kaymard (Aveyron, 44.546/2.480) — au nord de
    # `latmax` de `tarn-aveyron-herault`, à l'est de la zone
    # `tah-nord-ouest-isolees` (qui s'arrête à `lonmax=2.00`).
}

# Demi-fenêtre de sol autour d'une balise isolée. ⚠️ Ce n'est PAS le
# 0,25° des radiosondages : celui-là était dimensionné sur la dérive
# mesurée d'un ballon (7,8 km à 8 000 m). Une balise ne dérive pas. On
# veut la maille qui la contient et ses voisines — 0,05° ≈ 5,5 km, soit
# cinq mailles de 1,1 km, largement de quoi. Le coût suit : 146 points
# par balise au lieu de 3 042.
DEMI_FENETRE_BALISE_DEG = 0.05


def dans_zone_interet(lat, lon):
    """Le point est-il dans une zone d'intérêt ? (hors domaines)"""
    for d in ZONES_INTERET.values():
        if (d["latmin"] <= lat <= d["latmax"]
                and d["lonmin"] <= lon <= d["lonmax"]):
            return True
    return False

# Maille réelle au centre du domaine (45,5 °N), pour mémoire — c'est ce
# qui décide si deux balises d'une même grappe tombent dans la MÊME
# maille (§6 du lot, vérification par les grappes étagées) :
#   0,01°  → 1,11 × 0,78 km = 0,87 km²
#   0,025° → 2,78 × 1,95 km = 5,43 km²
MAILLE_KM2 = {GRID_FINE: 0.87, GRID_3D: 5.43}

# ── Les points de RADIOSONDAGE, et pourquoi ils ne sont pas dans le ───
#    domaine
#
# Le profil d'AGRUME n'était jusqu'ici vérifié que contre lui-même. Deux
# stations de radiosondage tombent à portée du domaine sans y être :
# Payerne (46,813 / 6,943 — 0,51° au nord de `latmax`) et Cameri
# (45,52 / 8,65 — 1,05° à l'est de `lonmax`). Elles donnent une vérité
# verticale RÉELLE, deux fois par jour. Cf. `agrume/radiosondage.py`.
#
# ⚠️ TROIS VOIES ÉTAIENT POSSIBLES, ET LE CHOIX SE PAIE PLUS TARD :
#
#   1. élargir `DOMAINE` → ~44,4–47,0 N × 5,4–8,8 E. Cohérent, mais
#      TRIPLE le produit B et fait entrer des balises suisses et
#      italiennes dans l'axe : rupture de l'axe des balises EN PLUS de
#      celle de l'orographie.
#   2. élargir la seule fenêtre d'orographie de production. Un seul
#      artefact, mais son sha256 change → toutes les archives d'avant ne
#      se rapportent plus au même fichier.
#   3. ✅ RETENU : un SECOND artefact d'orographie, minuscule, dédié à la
#      vérification, une petite fenêtre autour de chaque station.
#
# La 3 gagne parce qu'elle isole l'appareil de mesure du produit mesuré :
# la production ne bouge pas, son sha256 non plus, et la continuité des
# archives est intacte. Elle introduit bien deux notions de fenêtre —
# l'objection est réelle — mais la seconde n'est PAS un domaine de
# produit : aucune colonne servie à un pilote n'en dépend, et
# `freeze_orographie.py --radiosondages` l'écrit séparément.
# ⓘ Garde-fou : `--verifier-radiosondages` contrôle que les deux
# artefacts sont IDENTIQUES au point de grille près là où ils se
# recouvrent — sinon « deux fenêtres » deviendrait « deux orographies ».
#
# ⚠️ Rien de tout cela n'était nécessaire pour EXTRAIRE les colonnes :
# `quantification.index_plats()` indexe la grille NATIVE (France
# entière), pas la fenêtre. C'est l'ALTITUDE DU SOL qui manquait, et elle seule.
# Demi-fenêtre en degrés autour de chaque station. 0,25° ≈ 28 km, choisi
# sur une MESURE et pas sur une intuition : la dérive du ballon, intégrée
# sur les deux sondages réels de Payerne du 10/08, vaut 1,0 km à 2 000 m,
# 2,6 km à 4 000 et 7,8 km à 8 000 (ascension supposée 5 m/s). 28 km
# laisse donc de la marge même pour un jour de vent fort, tout en ne
# coûtant que ~24 Ko pour les deux stations et les deux mailles.
DEMI_FENETRE_VERIF_DEG = 0.25

# ⚠️ LE TÉMOIN — sans lui, le garde-fou des deux fenêtres ne prouve RIEN.
#
# L'idée du garde-fou est de vérifier que les deux artefacts donnent la
# MÊME altitude là où ils se recouvrent. Or Payerne et Cameri sont
# entièrement hors du domaine : le recouvrement est vide, et un contrôle
# sur zéro point rend un ✓ qui ne dit rien — exactement le genre de test
# qui rassure sans rien garantir.
#
# On découpe donc en plus une fenêtre CENTRÉE SUR LE DOMAINE, qui ne sert
# à aucune station et n'existe que pour être comparée à la production.
# Elle coûte quelques kilo-octets et transforme un contrôle vide en
# contrôle réel : même run, même champ, même indice, même octet.
TEMOIN_VERIF = dict(
    wmo="TEMOIN", nom="témoin (centre du domaine)", pays="FR",
    lat=round((DOMAINE["latmin"] + DOMAINE["latmax"]) / 2, 4),
    lon=round((DOMAINE["lonmin"] + DOMAINE["lonmax"]) / 2, 4),
    sol_station_m=None, active=True, resolution=None,
    mesure="Point de contrôle, pas une station. N'entre jamais dans "
           "l'axe des balises.")

# ── Horizon ───────────────────────────────────────────────────────────
# 0–24 h pour AGRUME, et c'est un choix de BUDGET, pas de physique.
# Mesuré : 0–51 h coûterait 5,98 Go (HP1) + 4,11 Go (HP2) par run contre
# 2,87 + 1,97 sur 0–24 h. Et l'archive du produit A à 0–51 h et 8 runs/j
# ferait 93 Go au bout d'un an, contre 23 Go à 0–24 h et 4 runs/j. Le
# surcoût R2 resterait dérisoire (~1,25 $/mois contre ~0,20), mais la
# consigne du projet est de rester SOUS le palier gratuit de 10 Go, pas
# de payer peu. ⚠️ AGRUME ne vaut de toute façon qu'à courte échéance :
# c'est précisément pourquoi son score demandera un lot dédié
# (`model_verif_daily` porte `check (lead_h in (6, 24, 48))`).
MAX_HOURS = 24

# ── ⛔ ET LA GRILLE VA PLUS LOIN QUE L'ARCHIVE (13/08/2026) ────────────
# Demande Yann : « je n'ai que la prévision d'une journée jusqu'à 20 h ».
# C'est exact, et c'est arithmétique — un run 18 Z + 24 h s'arrête au
# lendemain 18 Z, soit 20 h locales.
#
# ⛔ LES DEUX PRODUITS N'ONT PLUS LE MÊME HORIZON, ET C'EST LE POINT.
# Le paragraphe ci-dessus reste vrai POUR L'ARCHIVE : le produit A est
# DÉFINITIF, il croît pour toujours, et à 0–51 h il ferait 93 Go au bout
# d'un an contre 23. La consigne du projet est de rester SOUS le palier
# gratuit de 10 Go, pas de payer peu. Il reste donc à 24 h.
#
# Le produit B, lui, ne garde que TROIS runs. Doubler son horizon double
# un stationnaire, il ne grave rien. Chiffré depuis le run réel du 13/08
# (11,1 min, 9,96 Go, 320,8 Mo publiés, 962 Mo stationnaires) :
#
#     téléchargement    9,96 Go → ~21 Go      (les bundles vont par 6 h)
#     durée             11,1 min → ~23 min    ⚠️ alerte à 30, timeout 60
#     stationnaire      962 Mo → ~2 Go        (seuil d'arrêt 5 Go)
#     archive A         inchangée
#
# ⚠️ LA DURÉE EST LE CHIFFRE À SURVEILLER, et cette rallonge mange la
# moitié de la marge. Si un run passe 30 min, c'est ICI qu'il faut
# revenir — pas dans le nombre de domaines.
#
# ⛔ ET LA RALLONGE EST « AU MIEUX », PAS UN CONTRAT. Le choix du run
# reste décidé par la couverture de l'ARCHIVE (0 → MAX_HOURS) : sans ça,
# un run vieux de 3 h publiant 51 échéances battrait un run frais qui
# n'en publie encore que 25, et on perdrait de la fraîcheur pour gagner
# des heures lointaines dont personne ne fait rien. La rallonge est
# ajoutée APRÈS, et seulement tant qu'elle est CONTIGUË.
#
# ⛔⛔ ET « AU MIEUX » VOULAIT DIRE « JAMAIS » (mesuré le 13/08 au soir).
# La rallonge est cherchée à l'instant où le guet déclenche, c'est-à-dire
# dès que l'archive 0–24 h est complète. Or Météo-France publie les
# échéances lointaines APRÈS. Mesuré sur le run 15 Z du 13/08 :
#
#     0–24 h complet sur les 8 paquets   18:25:37 Z   (H+3 h 26)
#     rallonge cherchée par l'ingestion  18:29:12 Z   → VIDE
#     0–51 h complet                     18:53:29 Z   (H+3 h 53)
#
# Le seul run à sortir avec 52 échéances ce jour-là est celui qui avait
# été ingéré en RETARD. Sur douze réseaux mesurés (12 et 13/08), l'écart
# entre « archive prête » et « rallonge prête » va de 2 min à 3 h 33.
# ⚠️ Un cron ne peut donc pas le rattraper : c'est un second GUET qui
# déclenche une seconde passe (`poller.py --source arome-rallonge`).
MAX_HOURS_GRILLE = 51

# ── Le raccord vertical (§3.3 du lot) ─────────────────────────────────
# Sur l'axe altitude-mer, avec z_s = ALTITUDE(lat, lon) :
#   z_s → z_s + RACCORD_BAS      : niveaux HAUTEUR uniquement
#   z_s + RACCORD_BAS → z_s + RACCORD_HAUT : mélange à poids linéaire
#   au-dessus de z_s + RACCORD_HAUT        : ISOBARES uniquement
# ⚠️ Vérifier que les deux sources coïncident dans la zone de
# recouvrement est le meilleur test de non-régression du lot : si le
# mélange fait une marche, c'est qu'une conversion est fausse.
RACCORD_BAS_M = 1000
RACCORD_HAUT_M = 3000

# ── L'hybride du §4.1 bis — TRANCHÉ LE 10/08 : retenu dès la v0 ───────
# La tranche 10–100 m est disponible en maille fine (`001/HP1` porte
# u/v/ws/wdir à 20, 50 et 100 m ; `001/SP1` porte les 10 m), c'est-à-dire
# EXACTEMENT la tranche du décollage, du gonflage et de la première
# centaine de mètres de vol, là où le relief fin compte le plus.
#
# Ce que ça coûte, chiffré : +1,85 Go de téléchargement, +1,6 min,
# +12,7 Mo/run de stockage → produit B à ~42,6 Mo/run au lieu de 32
# (+33 %), budget d'ingestion à ~6,5 min au lieu de 2,9 — toujours six
# fois sous les 41,2 min de marge mesurée.
#
# ⚠️ CE QUE ÇA COÛTE AUSSI, et qui n'est PAS chiffré : un SECOND raccord.
# Le lot en a déjà un, délicat (hauteur ↔ isobares). L'hybride en ajoute
# un deuxième, entre deux MAILLES cette fois, à 100 m/sol — et les deux
# sources n'y diffèrent pas seulement par la verticale mais par la
# résolution horizontale. Une marche y est PROBABLE. Elle doit être
# MESURÉE et PUBLIÉE (critère d'acceptation du lot), pas supposée.
# C'est le point 7 de la séquence, et il reste ouvert.
HYBRIDE = True
RACCORD_HYBRIDE_M = 100   # au-dessus : 0,025° ; à 100 m et en dessous : 0,01°


def _j_de_lat(meta, lat):
    return (round((meta["lat0"] - lat) / meta["dj"]) if meta["jScan"] != 1
            else round((lat - meta["lat0"]) / meta["dj"]))


def fenetre_autour(meta, lat, lon, demi_deg=None):
    """Fenêtre (j0, j1, i0, i1) centrée sur un point, pour la vérification.

    ⚠️ Ce n'est PAS un domaine de produit. Sert uniquement à donner une
    altitude de sol aux points de radiosondage, qui sont hors du domaine
    Nord-Alpes (cf. la note plus haut). Aucune colonne servie à un pilote
    ne dépend de cette fenêtre.
    """
    d = DEMI_FENETRE_VERIF_DEG if demi_deg is None else demi_deg
    return fenetre(meta, domaine=dict(latmin=lat - d, latmax=lat + d,
                                      lonmin=lon - d, lonmax=lon + d))


def fenetre(meta, marge=0, domaine=None):
    """Indices (j0, j1, i0, i1) — bornes INCLUSIVES — du domaine dans la
    grille décrite par `meta` (mêmes clés que `parse_grib`).

    `domaine` vaut le domaine Nord-Alpes par défaut. Il n'est explicité
    que par la fenêtre de vérification des radiosondages : partout
    ailleurs, passer un autre domaine serait le début d'une seconde
    définition du produit.

    ⚠️ Les indices se DÉDUISENT des métadonnées du GRIB, ils ne sont
    jamais codés en dur : Météo-France peut déplacer le coin de grille
    sans prévenir, et un décalage d'un point sur une orographie de
    montagne vaut des centaines de mètres. Même convention de balayage
    que `arome-wind/ingest.py::elev_at` et
    `tools/orographie_balises.py::indices`.

    `marge` élargit la fenêtre de N points de grille de chaque côté —
    utile pour une interpolation bilinéaire ultérieure, qui a besoin des
    voisins des points de bord.
    """
    dom = DOMAINE if domaine is None else domaine
    j_a = _j_de_lat(meta, dom["latmax"])
    j_b = _j_de_lat(meta, dom["latmin"])
    j0, j1 = (j_a, j_b) if j_a <= j_b else (j_b, j_a)
    i0 = round((dom["lonmin"] - meta["lon0"]) / meta["di"])
    i1 = round((dom["lonmax"] - meta["lon0"]) / meta["di"])
    j0, i0 = max(0, j0 - marge), max(0, i0 - marge)
    j1 = min(meta["Nj"] - 1, j1 + marge)
    i1 = min(meta["Ni"] - 1, i1 + marge)
    if j0 > j1 or i0 > i1:
        raise ValueError(
            f"domaine {dom['latmin']}-{dom['latmax']} N × "
            f"{dom['lonmin']}-{dom['lonmax']} E hors de la grille reçue "
            f"({meta['Ni']}×{meta['Nj']}, origine "
            f"{meta['lat0']}/{meta['lon0']}, pas {meta['di']}/{meta['dj']})")
    return j0, j1, i0, i1


def dans_domaine(lat, lon, nom=None):
    """Le point est-il dans UN domaine de production ? (bornes inclusives)

    ⚠️ 12/08 — LE SENS DE CETTE FONCTION A CHANGÉ, et c'est le seul
    endroit où ça se voit. Elle testait le domaine Nord-Alpes ; elle teste
    maintenant l'appartenance à **n'importe lequel** des domaines de
    `DOMAINES`. Tous ses appelants voulaient déjà dire « ce point est-il
    servable ? » et non « est-il dans les Alpes ? » — `freeze_balises`
    filtre les candidates à l'axe, `quantification` écarte celles qui n'auront
    pas de sol. Passer `nom` restreint à un domaine précis, pour les rares
    cas qui veulent vraiment celui-là et pas un autre.

    ⚠️ MESURÉ LE 12/08 — CETTE FONCTION ET `z_at()` PEUVENT SE
    CONTREDIRE, D'UNE DEMI-MAILLE. Elle teste des BORNES ; la fenêtre
    réellement découpée par `fenetre()` s'aligne sur les POINTS DE GRILLE
    (elle arrondit), et `z_at()` cherche le plus proche voisin. Une balise
    posée à moins d'une demi-maille du bord — 0,0125° en 0,025°, soit
    1,4 km — est donc « hors bornes » ici et bel et bien DANS la fenêtre
    là-bas. Un cas réel sur 203 : la balise 1661 (LFMG), à 43,4069 N pour
    un `latmax` de 43,40.
    ⓘ Ce n'est pas un défaut à corriger, et surtout pas en rognant la
    fenêtre : les deux sources rendent le MÊME point de grille et le même
    sol (395,0 m des deux côtés, écart 0,000 m — vérifié). Ce qui compte
    est que le SOL soit unique, et il l'est. La règle du projet
    s'applique : c'est le fichier qui décide, pas la constante — d'où le
    fait que `ingest_colonnes` attribue les sols par `z_at`, jamais par
    `domaine_de`.
    """
    for cle, d in (DOMAINES.items() if nom is None else [(nom, DOMAINES[nom])]):
        if (d["latmin"] <= lat <= d["latmax"]
                and d["lonmin"] <= lon <= d["lonmax"]):
            return True
    return False


def domaine_de(lat, lon):
    """Le NOM du domaine qui contient ce point, ou None.

    ⚠️ Les domaines ne se recouvrent pas aujourd'hui, et rien ne l'impose.
    Le jour où deux se chevaucheraient, cette fonction rendrait le premier
    déclaré — silencieusement, et l'orographie servie changerait selon
    l'ordre d'un dictionnaire. `verifier_domaines_disjoints()` refuse ce
    cas plutôt que de le trancher au hasard.
    """
    for cle, d in DOMAINES.items():
        if (d["latmin"] <= lat <= d["latmax"]
                and d["lonmin"] <= lon <= d["lonmax"]):
            return cle
    return None


def verifier_domaines_disjoints():
    """Lève si deux domaines se recouvrent. Appelée par le banc.

    Deux domaines qui se chevauchent, c'est un point qui a DEUX sols
    figés — et donc une colonne dont l'altitude dépend de quel artefact a
    été consulté en premier. Le genre de faute qui ne lève jamais et
    décale toutes les altitudes servies sur la zone de recouvrement.
    """
    noms = list(DOMAINES)
    for a in range(len(noms)):
        for b in range(a + 1, len(noms)):
            x, y = DOMAINES[noms[a]], DOMAINES[noms[b]]
            if (x["latmin"] <= y["latmax"] and y["latmin"] <= x["latmax"]
                    and x["lonmin"] <= y["lonmax"] and y["lonmin"] <= x["lonmax"]):
                raise ValueError(
                    f"domaines {noms[a]} et {noms[b]} se recouvrent : un "
                    f"point du recouvrement aurait deux sols figés")
    return True
