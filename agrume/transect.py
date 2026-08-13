#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/transect.py — la coupe verticale le long d'un segment
#                                                        (10/08/2026)
#
#  Étape 8 du lot H. Le sondage de l'étape 5 répond « que fait l'air
#  AU-DESSUS DE CE POINT ? ». Celui-ci répond « que fait l'air LE LONG DE
#  CETTE VALLÉE ? » — et c'est la question qu'un pilote se pose avant un
#  cross, pas l'autre.
#
#  ⚠️ IL N'EXISTE AUCUN CATALOGUE DE TRANSECTS, ET IL N'EN EXISTERA PAS.
#  Le §4.1 du lot l'a chiffré : 40 transects de 200 points font 8 000
#  colonnes, contre 5 185 pour la grille ENTIÈRE du domaine. Le catalogue
#  serait plus lourd que la donnée dont il est extrait. Une coupe se
#  découpe donc à la demande dans le produit B, en mémoire, et ne
#  s'écrit nulle part.
#
#  ── CE QUE CE FICHIER NE SERT PAS, ET IL FAUT LE LIRE D'ABORD ────────
#  ⚠️ MIS À JOUR LE 13/08 (audit). Depuis l'étape 12, le produit B PORTE
#  les 14 niveaux isobares (`iso`, `ziso`) et la ligne de surface — ce
#  fichier disait encore le contraire, dans sa RÉPONSE publiée, pas
#  seulement dans un commentaire. ⛔ Mais CETTE coupe-ci ne lit toujours
#  que `gr.h0025` : elle s'arrête à `zsol + 3000 m`, et c'est écrit dans
#  la réponse plutôt que laissé à deviner. Le lecteur qui sert TOUTE la
#  colonne (isobares + surface, mélange compris) est le 6ᵉ onglet de la
#  vue de coupe, via `colonnes.bin` (`web/src/lib/agrumeProfile.ts`).
#  Étendre cette coupe Python aux isobares est un choix de produit — à
#  arbitrer, pas à glisser dans un correctif ; en attendant, la réponse
#  dit exactement ce qu'elle sert.
#
#  ── LA DÉCISION DE L'ÉTAPE : ON NE COUD PAS L'AXE VERTICAL ───────────
#  Chaque colonne repose sur SON sol. Deux colonnes voisines peuvent
#  avoir 800 m d'écart d'orographie, donc leurs niveaux « 500 m/sol » ne
#  sont pas à la même altitude-mer. Deux façons de rendre ça :
#
#    (a) TERRAIN-FOLLOWING — on sert les niveaux tels quels, chacun avec
#        son altitude-mer, et on publie `solModeleM` pour que le
#        consommateur dessine le relief sous la coupe ;
#    (b) RÉÉCHANTILLONNÉ — on interpole verticalement sur une grille
#        d'altitudes régulière, et la coupe devient un rectangle.
#
#  ⚠️ (b) est retenu NULLE PART ici, et ce n'est pas de la paresse. Sous
#  le sol du modèle, (b) devrait inventer des valeurs ou poser des trous ;
#  au-dessus de `zsol + 3000`, pareil. Et surtout : l'interpolation
#  verticale à altitude-mer constante est EXACTEMENT le travail du calque
#  altitude (étape 11), qui devra la faire une fois, bien, et pour tout le
#  domaine. La faire ici en plus, c'est deux implémentations d'une même
#  décision qui divergeront. Le manifeste du produit B le dit déjà :
#  « une coupe horizontale à altitude-mer constante n'est PAS un niveau du
#  tableau ».
#
#  ── PLUS PROCHE VOISIN, ET RIEN D'AUTRE ──────────────────────────────
#  ⚠️ Aucune interpolation HORIZONTALE non plus — même convention que
#  l'orographie et que les colonnes du produit A, et pour la même raison :
#  on veut la colonne que le modèle CALCULE réellement, pas une moyenne
#  de colonnes voisines qui n'existe dans aucun modèle. Conséquence
#  directe et assumée : deux points d'échantillonnage voisins tombent
#  souvent dans la MÊME maille, et la coupe est un escalier.
#
#  ⚠️⚠️ ET C'EST LE MODE DE PANNE SILENCIEUX DE CE FICHIER. Demander
#  200 points sur un segment de 50 km affiche une coupe lisse et détaillée
#  qui ne repose que sur ~25 colonnes distinctes : la finesse est
#  entièrement fabriquée par l'affichage. La réponse porte donc TOUJOURS
#  `nbPoints` ET `nbMaillesDistinctes`, et le drapeau `escalier` quand
#  les deux diffèrent. On ne refuse pas — un axe régulier est utile pour
#  tracer — on refuse seulement de laisser croire.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import math

import numpy as np

from domaine import DOMAINE, GRID_3D, NIVEAUX_H_0025
from grille import PARAMS_GRILLE
from profil import decorer_vent

# Rayon terrestre moyen, comme partout ailleurs dans le projet.
R_TERRE_KM = 6371.0

# ⚠️ Tolérance d'appariement d'un point à une maille, en pas de grille.
# Même valeur et même raison que dans `grille.axes_depuis_orographie` :
# 0,6 pas accepte le plus proche voisin (qui ne peut être qu'à un demi-pas)
# et refuse un décalage d'un point entier.
TOL_MAILLE = 0.6


# ══════════════════════════════════════════════════════════════════════
#  Géométrie
# ══════════════════════════════════════════════════════════════════════
def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * R_TERRE_KM * math.asin(min(1.0, math.sqrt(a)))


def _vecteur(lat, lon):
    p, l = math.radians(lat), math.radians(lon)
    return np.array([math.cos(p) * math.cos(l),
                     math.cos(p) * math.sin(l),
                     math.sin(p)])


def _degres(v):
    return (math.degrees(math.asin(v[2] / np.linalg.norm(v))),
            math.degrees(math.atan2(v[1], v[0])))


def point_intermediaire(depart, arrivee, f):
    """Point à la fraction `f` du segment, SUR L'ORTHODROMIE.

    ⚠️⚠️ CE COMMENTAIRE A DIT LE CONTRAIRE PENDANT UNE HEURE. Il
    affirmait que l'orthodromie et l'interpolation linéaire de lat/lon
    « ne diffèrent que de quelques dizaines de mètres, très en dessous de
    la maille ». **Le banc l'a démenti** : sur la diagonale du domaine
    (233 km), l'écart maximal vaut **1 215 m**, soit 0,62 maille — assez
    pour ranger des points d'échantillonnage dans une AUTRE colonne, au
    milieu du segment, là où personne ne va vérifier.

    L'écart croît comme le carré de la longueur (≈ L²·sin φ / 8R) : il
    tombe à ~70 m sur un segment de 55 km, et c'est là qu'il est
    effectivement négligeable. `ecart_droite_m()` le mesure POUR CHAQUE
    REQUÊTE et la réponse le publie, plutôt que de laisser un
    consommateur découvrir que la coupe ne suit pas exactement le trait
    qu'il a dessiné sur sa carte.

    ⓘ *Un « négligeable » écrit sans nombre est une déduction, et ce
    projet en a déjà démenti trois en une journée.*
    """
    a, b = _vecteur(*depart), _vecteur(*arrivee)
    omega = math.acos(max(-1.0, min(1.0, float(np.dot(a, b)))))
    if omega < 1e-12:
        return depart
    s = math.sin(omega)
    return _degres((math.sin((1 - f) * omega) / s) * a
                   + (math.sin(f * omega) / s) * b)


def ecart_droite_m(depart, arrivee, n=64):
    """Écart MAXIMAL, en mètres, entre l'orthodromie servie et la droite
    lat/lon qu'un consommateur croit avoir demandée.

    ⚠️ Ce n'est pas une curiosité mathématique : un front qui dessine une
    polyligne entre deux points sur une carte web, puis affiche cette
    coupe dessous, montre deux tracés différents. Tant que l'écart reste
    petit devant la maille, ça n'a aucune conséquence ; à 1,2 km il en a
    une. On le mesure au lieu d'en décider une fois pour toutes.
    """
    pire = 0.0
    for k in range(1, n):
        f = k / n
        lat_o, lon_o = point_intermediaire(depart, arrivee, f)
        lat_d = depart[0] + f * (arrivee[0] - depart[0])
        lon_d = depart[1] + f * (arrivee[1] - depart[1])
        pire = max(pire, haversine_km(lat_o, lon_o, lat_d, lon_d))
    return pire * 1000.0


def maille_km(lats, lons):
    """(hauteur, largeur) d'une maille en km, au CENTRE du domaine.

    ⚠️ Une maille n'est PAS carrée, et laquelle des deux dimensions est
    la plus petite n'est pas celle qu'on croit : 0,025° de latitude font
    2,78 km partout, tandis que 0,025° de longitude n'en font que 1,95 à
    45,5 °N (× cos φ). C'est la dimension EST-OUEST qui est la plus fine.
    Ce calcul est ici, et pas en dur, précisément pour que personne n'ait
    à se rappeler dans quel sens va le cosinus. (Cohérent avec
    `domaine.MAILLE_KM2`, qui annonce 2,78 × 1,95 km.)
    """
    dlat = abs(float(lats[1] - lats[0])) if len(lats) > 1 else 0.0
    dlon = abs(float(lons[1] - lons[0])) if len(lons) > 1 else 0.0
    phi = math.radians(float(np.mean(lats)))
    return (dlat * math.pi / 180 * R_TERRE_KM,
            dlon * math.pi / 180 * R_TERRE_KM * math.cos(phi))


def pas_par_defaut(lats, lons):
    """Le pas d'échantillonnage par défaut : la PLUS PETITE dimension de
    maille.

    ⚠️ Le plus petit, pas le plus grand, et pas la moyenne. Avec le plus
    grand, un segment orienté selon la dimension fine sauterait des
    mailles — et une maille sautée dans une coupe de montagne, c'est un
    col ou une crête qui n'apparaît pas. Avec le plus petit, on
    sur-échantillonne dans l'autre direction, ce qui produit des doublons
    — visibles, comptés, publiés. *Entre rater une maille et en répéter
    une, on répète.*

    ⓘ Ça ne GARANTIT pas que toute maille traversée soit visitée sur une
    diagonale ; ça garantit qu'aucun pas ne franchit plus d'une maille
    dans la direction la plus fine.
    """
    h, l = maille_km(lats, lons)
    return min(x for x in (h, l) if x > 0)


def echantillonner(depart, arrivee, pas_km, n=None):
    """[(fraction, lat, lon, distanceKm)] le long du segment.

    `n` impose un nombre de points ; sinon le pas décide. Les deux
    extrémités sont toujours servies.
    """
    total = haversine_km(depart[0], depart[1], arrivee[0], arrivee[1])
    if total <= 0:
        raise ValueError("le départ et l'arrivée sont le même point : "
                         "un transect de longueur nulle n'est pas une coupe, "
                         "c'est un sondage (voir `verif/sonder.py`).")
    if n is None:
        n = max(2, int(round(total / pas_km)) + 1)
    if n < 2:
        raise ValueError("un transect demande au moins 2 points")
    out = []
    for k in range(n):
        f = k / (n - 1)
        lat, lon = point_intermediaire(depart, arrivee, f)
        out.append((f, lat, lon, round(f * total, 3)))
    return out


# ══════════════════════════════════════════════════════════════════════
#  Indexation dans la grille
# ══════════════════════════════════════════════════════════════════════
def index_plus_proche(lats, lons, lat, lon, tol=TOL_MAILLE):
    """(j, i) de la maille la plus proche, ou lève.

    ⚠️⚠️ `argmin` SUR L'ÉCART ABSOLU, JAMAIS UNE FORMULE À PARTIR D'UN
    COIN ET D'UN PAS. Les latitudes du produit B DÉCROISSENT (le premier
    point est au nord, `jScansPositively = 0` sur AROME) et le manifeste
    le dit en toutes lettres. Une formule `(lat - lats[0]) / dlat`
    donnerait un indice négatif — et `argmin` d'un tableau reste valide,
    donc l'erreur se lirait comme une coupe qui montre les Alpes à
    l'envers. Sur un domaine presque carré, une coupe retournée ressemble
    toujours à une coupe. On lit donc les axes PUBLIÉS, sans supposer
    leur sens.
    """
    lats = np.asarray(lats, dtype=np.float64)
    lons = np.asarray(lons, dtype=np.float64)
    j = int(np.abs(lats - lat).argmin())
    i = int(np.abs(lons - lon).argmin())
    dlat = abs(float(lats[1] - lats[0])) if len(lats) > 1 else 1.0
    dlon = abs(float(lons[1] - lons[0])) if len(lons) > 1 else 1.0
    if (abs(float(lats[j]) - lat) > tol * dlat
            or abs(float(lons[i]) - lon) > tol * dlon):
        raise ValueError(
            f"le point ({lat:.4f}, {lon:.4f}) tombe hors de la grille du "
            f"domaine Nord-Alpes ({DOMAINE['latmin']}–{DOMAINE['latmax']} N, "
            f"{DOMAINE['lonmin']}–{DOMAINE['lonmax']} E). ⚠️ Le plus proche "
            f"voisin existe toujours : sans ce contrôle, un segment qui sort "
            f"du domaine serait servi en RECOLLANT tous ses points sur le "
            f"bord, ce qui donne une coupe plate parfaitement crédible.")
    return j, i


def colonne(gr, j, i, i_step):
    """La colonne (j, i) à l'échéance `i_step`, au FORMAT DE `profil.py`.

    ⚠️ Les clés sont exactement celles de `profil.niveaux_hauteur` — un
    banc de parité le vérifie. Le sondage en un point et la coupe servent
    la même donnée sous deux découpes ; qu'ils la nomment différemment
    obligerait le front à écrire deux lecteurs, et l'un des deux
    finirait périmé.
    """
    ip = {p["nom"]: k for k, p in enumerate(PARAMS_GRILLE)}
    z_s = float(gr.zsol[j, i])
    if not np.isfinite(z_s):
        return z_s, []
    out = []
    for k, niveau in enumerate(NIVEAUX_H_0025):
        u = float(gr.h0025[ip["u"], k, i_step, j, i])
        v = float(gr.h0025[ip["v"], k, i_step, j, i])
        if not (np.isfinite(u) and np.isfinite(v)):
            continue
        t = float(gr.h0025[ip["t"], k, i_step, j, i])
        r = float(gr.h0025[ip["r"], k, i_step, j, i])
        tke = float(gr.h0025[ip["tke"], k, i_step, j, i])
        out.append(decorer_vent(dict(
            altitudeM=round(z_s + niveau, 1), hauteurSolM=niveau,
            source="hauteur", maille=GRID_3D, u=u, v=v,
            t=None if not np.isfinite(t) else round(t, 2),
            hr=None if not np.isfinite(r) else round(r, 1),
            tke=None if not np.isfinite(tke) else round(tke, 3))))
    out.sort(key=lambda p: p["altitudeM"])
    return z_s, out


# ══════════════════════════════════════════════════════════════════════
#  La réponse v0
# ══════════════════════════════════════════════════════════════════════
def couper(gr, manifeste, depart, arrivee, step, pas_km=None, n=None):
    """La coupe verticale le long de [depart → arrivee], prête à servir.

    `depart` et `arrivee` sont des couples (lat, lon) ; `step` est une
    échéance en heures, telle qu'elle figure dans le manifeste.
    """
    if step not in gr.steps:
        raise ValueError(
            f"l'échéance {step} h n'est pas dans ce run : le produit B ne "
            f"porte que {gr.steps}. ⚠️ Il ne survit pas à trois runs — "
            f"demander une échéance absente n'est pas rattrapable en "
            f"relisant, il faut un autre run.")
    i_step = gr.steps.index(step)

    h_km, l_km = maille_km(gr.lats, gr.lons)
    pas = pas_par_defaut(gr.lats, gr.lons) if pas_km is None else float(pas_km)
    echantillons = echantillonner(depart, arrivee, pas, n)

    points, vues = [], []
    for _f, lat, lon, d_km in echantillons:
        j, i = index_plus_proche(gr.lats, gr.lons, lat, lon)
        vues.append((j, i))
        z_s, niveaux = colonne(gr, j, i, i_step)
        points.append(dict(
            distanceKm=d_km,
            lat=round(lat, 5), lon=round(lon, 5),
            # ⚠️ Le point DEMANDÉ et le point SERVI ne sont pas le même,
            # et l'écart peut atteindre 1,4 km. Publier les deux est la
            # seule façon pour un consommateur de savoir qu'il regarde un
            # escalier et non une courbe.
            latMaille=round(float(gr.lats[j]), 4),
            lonMaille=round(float(gr.lons[i]), 4),
            jMaille=j, iMaille=i,
            solModeleM=None if not np.isfinite(z_s) else round(z_s, 1),
            plafondM=None if not np.isfinite(z_s) else round(
                z_s + max(NIVEAUX_H_0025), 1),
            niveaux=niveaux))

    distinctes = len(set(vues))
    sols = [p["solModeleM"] for p in points if p["solModeleM"] is not None]

    return dict(
        produit="AGRUME étape 8 — coupe verticale le long d'un segment",
        run=gr.run,
        echeanceH=step,
        grille=GRID_3D,
        segment=dict(
            depart=dict(lat=round(depart[0], 5), lon=round(depart[1], 5)),
            arrivee=dict(lat=round(arrivee[0], 5), lon=round(arrivee[1], 5)),
            longueurKm=round(haversine_km(depart[0], depart[1],
                                          arrivee[0], arrivee[1]), 2),
            pasKm=round(pas, 3),
            geodesique="orthodromie",
            # ⚠️ Mesuré pour CE segment, pas décrété une fois pour
            # toutes : 1 215 m sur la diagonale du domaine, ~70 m sur
            # 55 km. Au-delà d'une demi-maille, la coupe ne passe plus
            # par les mêmes colonnes que le trait dessiné sur la carte.
            ecartDroiteLatLonM=round(ecart_droite_m(depart, arrivee), 1)),
        # ── Ce bloc est la raison d'être de la réponse ────────────────
        # Sans lui, une coupe à 200 points sur 20 colonnes distinctes se
        # lit comme une coupe à 200 colonnes.
        resolution=dict(
            nbPoints=len(points),
            nbMaillesDistinctes=distinctes,
            escalier=bool(distinctes < len(points)),
            mailleKm=dict(hauteur=round(h_km, 3), largeur=round(l_km, 3)),
            note=("plus proche voisin, AUCUNE interpolation horizontale : "
                  "plusieurs points d'échantillonnage peuvent tomber dans la "
                  "même maille. `nbMaillesDistinctes` est le nombre de "
                  "colonnes RÉELLEMENT différentes derrière la coupe ; "
                  "au-delà, la finesse vient de l'affichage, pas du modèle.")),
        relief=dict(
            solMinM=round(min(sols), 1) if sols else None,
            solMaxM=round(max(sols), 1) if sols else None,
            note=("`solModeleM` est l'orographie DU MODÈLE, lissée : elle "
                  "place les sommets ~135 m plus bas que le sol réel en "
                  "médiane (n = 109). Le tracer sous la coupe est une "
                  "information, pas un décor.")),
        reference_verticale=(
            "niveaux AGL au-dessus du sol du modèle, servis TELS QUELS : "
            "altitudeM = solModeleM + hauteurSolM, colonne par colonne. "
            "Aucun rééchantillonnage sur un axe d'altitude commun — c'est "
            "le travail du calque altitude (étape 11)."),
        plafond=dict(
            hauteurSolMaxM=max(NIVEAUX_H_0025),
            note=("⛔ CETTE coupe ne sert que les niveaux HAUTEUR : elle "
                  "s'arrête à solModeleM + 3000 m, et cette limite suit le "
                  "relief. ⚠️ Le produit B porte AUSSI les isobares et la "
                  "surface depuis l'étape 12 (13/08) — ils sont servis par "
                  "`colonnes.bin` (6ᵉ onglet de la vue de coupe), pas par "
                  "cette route-ci.")),
        manifesteSource=dict(
            run=(manifeste or {}).get("run"),
            remplissage=(manifeste or {}).get("remplissage")),
        points=points)
