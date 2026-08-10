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

# ── Le domaine Nord-Alpes ─────────────────────────────────────────────
# ⚠️ Ce n'est pas un choix de confort, c'est ce qui rend le produit B
# possible : la France entière en 0,025° fait 803 757 points par niveau,
# le domaine en fait 5 185. Taille MESURÉE le 10/08 en découpant un GRIB
# réel : 61 × 85 = 5 185 points, exactement la valeur annoncée au §4.1
# du lot. Ce n'était qu'un calcul ; c'est maintenant une mesure.
#
# ⚠️ Les bornes sont INCLUSIVES et l'appartenance se teste sur les
# coordonnées, jamais sur des indices codés en dur — les indices se
# recalculent depuis les métadonnées du GRIB (cf. `fenetre()`), sinon un
# changement de domaine de Météo-France passerait inaperçu.
DOMAINE = dict(latmin=44.8, latmax=46.3, lonmin=5.5, lonmax=7.6)

# Maille réelle au centre du domaine (45,5 °N), pour mémoire — c'est ce
# qui décide si deux balises d'une même grappe tombent dans la MÊME
# maille (§6 du lot, vérification par les grappes étagées) :
#   0,01°  → 1,11 × 0,78 km = 0,87 km²
#   0,025° → 2,78 × 1,95 km = 5,43 km²
MAILLE_KM2 = {GRID_FINE: 0.87, GRID_3D: 5.43}

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


def fenetre(meta, marge=0):
    """Indices (j0, j1, i0, i1) — bornes INCLUSIVES — du domaine dans la
    grille décrite par `meta` (mêmes clés que `parse_grib`).

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
    def _j(lat):
        return (round((meta["lat0"] - lat) / meta["dj"]) if meta["jScan"] != 1
                else round((lat - meta["lat0"]) / meta["dj"]))

    j_a, j_b = _j(DOMAINE["latmax"]), _j(DOMAINE["latmin"])
    j0, j1 = (j_a, j_b) if j_a <= j_b else (j_b, j_a)
    i0 = round((DOMAINE["lonmin"] - meta["lon0"]) / meta["di"])
    i1 = round((DOMAINE["lonmax"] - meta["lon0"]) / meta["di"])
    j0, i0 = max(0, j0 - marge), max(0, i0 - marge)
    j1 = min(meta["Nj"] - 1, j1 + marge)
    i1 = min(meta["Ni"] - 1, i1 + marge)
    if j0 > j1 or i0 > i1:
        raise ValueError(
            f"domaine Nord-Alpes hors de la grille reçue "
            f"({meta['Ni']}×{meta['Nj']}, origine "
            f"{meta['lat0']}/{meta['lon0']}, pas {meta['di']}/{meta['dj']})")
    return j0, j1, i0, i1


def dans_domaine(lat, lon):
    """Le point est-il dans le domaine Nord-Alpes ? (bornes inclusives)"""
    return (DOMAINE["latmin"] <= lat <= DOMAINE["latmax"]
            and DOMAINE["lonmin"] <= lon <= DOMAINE["lonmax"])
