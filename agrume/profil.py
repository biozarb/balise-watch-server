#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/profil.py — la colonne telle qu'un pilote la lit
#                                                        (10/08/2026)
#
#  Étape 5 du lot H. C'est ici que les trois sources deviennent UNE
#  colonne sur un seul axe : l'altitude-mer.
#
#  ── LE VRAI PROBLÈME DU LOT, EN UN PARAGRAPHE ───────────────────────
#  AROME publie deux verticales incompatibles. Les niveaux HAUTEUR sont
#  au-dessus du sol **du modèle** — un « 500 m » est à 500 m au-dessus
#  d'une orographie lissée, pas au-dessus du sol réel. Les niveaux
#  ISOBARES sont absolus, mais ceux dont l'altitude tombe **sous** le sol
#  du modèle sont extrapolés SOUS TERRE : les valeurs existent, elles
#  sont physiquement vides de sens, et rien dans le fichier ne le dit.
#
#  Un pilote, lui, raisonne exclusivement en altitude-mer. Toute la
#  valeur de ce fichier est là : convertir sans mentir.
#
#  ── LES TROIS RÈGLES, ET POURQUOI ────────────────────────────────────
#
#  1. **MASQUER SOUS LE SOL.** Aucun niveau isobare dont l'altitude est
#     inférieure à `z_s` n'est servi. Ce n'est pas de la prudence : dans
#     les Alpes, 1000, 950 et 925 hPa sont sous le terrain à peu près
#     partout, et les servir donnerait un vent « au sol » inventé par
#     l'extrapolation du modèle.
#
#  2. **RACCORDER PAR MÉLANGE, PAS PAR BASCULE.** De `z_s` à
#     `z_s + 1000 m`, hauteur seule. De `z_s + 1000` à `z_s + 3000`,
#     mélange à poids linéaire. Au-dessus, isobares seules. Une bascule
#     franche ferait une marche à un endroit arbitraire ; le mélange
#     répartit le désaccord — et surtout **il le rend mesurable**.
#
#  3. **MÉLANGER PAR COMPOSANTES u/v, JAMAIS PAR L'ANGLE.** Un vent de
#     359° et un de 001° sont à 2° l'un de l'autre ; leur moyenne
#     arithmétique en degrés vaut 180°, soit exactement l'inverse. Le
#     banc le vérifie sur une colonne traversant 350° → 010°.
#
#  ⚠️ **LE MÉLANGE EST UN TEST, PAS SEULEMENT UN CALCUL.** Si les deux
#  sources ne coïncident pas dans la zone de recouvrement, le profil fait
#  une marche — et une marche ne vient jamais de la météo, elle vient
#  d'une conversion fausse. `ecart_recouvrement()` mesure ce désaccord
#  AVANT tout mélange, et c'est le meilleur test de non-régression du lot.
#
#  ── CE QUE `elevationDeltaM` DIT, ET CE QU'IL NE PEUT PAS DIRE ───────
#  Le modèle place les balises **~150 m TROP BAS** — médiane −174 m en
#  0,01°, −135 m en 0,025° (n = 109). Les balises de vol libre sont sur
#  des décollages et des crêtes, et la maille rabote les sommets.
#
#  ⚠️ **Mais l'altitude RÉELLE des 648 balises n'existe nulle part dans
#  ce projet** : le référentiel Pioupiou donne latitude et longitude, et
#  rien d'autre. Le seul repère disponible est l'altitude parfois écrite
#  DANS LE NOM (« Signal de Soi 2050m ») — 109 balises sur 648. Donc
#  `elevationDeltaM` vaut `None` pour la plupart, et la réponse dit
#  toujours D'OÙ vient l'altitude de référence. Un delta sans source
#  serait pire qu'un delta absent.
#  ⚠️ Et il ne faut PAS aller chercher cette altitude chez Open-Meteo :
#  décision du 21/07, le projet a déjà été cassé une fois par ce quota.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import math
import re

import numpy as np

from colonnes import PARAMS_001, PARAMS_0025, PARAMS_ISO
from domaine import (GRID_3D, GRID_FINE, NIVEAUX_H_001, NIVEAUX_H_0025,
                     NIVEAUX_P, RACCORD_BAS_M, RACCORD_HAUT_M,
                     RACCORD_HYBRIDE_M)


# ══════════════════════════════════════════════════════════════════════
#  Altitude de référence — celle du sol RÉEL, quand on la connaît
# ══════════════════════════════════════════════════════════════════════
_RE_ALT_NOM = re.compile(r"(?<!\d)(\d{3,4})\s*m(?![a-zA-Z])", re.IGNORECASE)


def altitude_du_nom(nom):
    """Altitude lue dans le nom de la balise, ou None.

    ⚠️ C'est un pis-aller ASSUMÉ, pas une source de vérité. Les noms sont
    saisis à la main par les propriétaires de balises : « Déco Planpraz
    Chamonix 1958m » donne 1958, mais rien ne garantit ni l'exactitude ni
    l'unité. On borne donc à des valeurs plausibles pour un site de vol
    libre, et la réponse dit toujours que la source est le NOM.
    """
    if not nom:
        return None
    candidats = [int(m) for m in _RE_ALT_NOM.findall(nom)]
    plausibles = [c for c in candidats if 100 <= c <= 4900]
    return float(max(plausibles)) if plausibles else None


def reference_sol(balise, altitude_reelle=None):
    """(altitude de référence, source) — ou (None, None) si inconnue."""
    if altitude_reelle is not None:
        return float(altitude_reelle), "fournie"
    z = altitude_du_nom(balise.get("nom") or balise.get("name") or "")
    return (z, "nom de la balise") if z is not None else (None, None)


# ══════════════════════════════════════════════════════════════════════
#  Extraction d'une colonne brute
# ══════════════════════════════════════════════════════════════════════
def _f32(a):
    return np.asarray(a, dtype=np.float32)


def niveaux_hauteur(col, i_balise, i_step, z_0025):
    """Les 25 niveaux HAUTEUR du 0,025°, ramenés en altitude-mer.

    ⚠️⚠️ ON N'INSÈRE **PAS** LA MAILLE FINE DANS CETTE COLONNE, ET C'EST
    UNE DÉCISION, PAS UN OUBLI.

    La tentation est évidente : l'hybride du §4.1 bis dit que la tranche
    ≤ 100 m/sol existe en 0,01°, donc autant la servir là. Essayé, et le
    résultat est indéfendable — mesuré sur une vraie colonne le 10/08 :

        100 m/sol en maille fine  → 604 m ASL   (sol 0,01° = 504 m)
         35 m/sol en maille 0025  → 677 m ASL   (sol 0,025° = 642 m)

    **« 35 m au-dessus du sol » se retrouve PLUS HAUT que « 100 m
    au-dessus du sol ».** Ce n'est pas une erreur de calcul : les deux
    hauteurs se rapportent à deux sols différents, distants de 138 m ici,
    de 75 m en médiane et de 643 m au pire sur le domaine. Et 35 m et
    75 m n'existent pas en maille fine, donc la tranche basse serait de
    toute façon obligée d'alterner entre les deux topographies.

    Une colonne unique doit reposer sur **UN seul sol**. Celui-ci est le
    0,025°, parce que c'est la seule maille qui porte la colonne entière.
    La maille fine est servie **à part** (`niveaux_fins`), avec SON sol
    annoncé — et l'écart entre les deux est mesuré et publié plutôt que
    dissous dans un tri par altitude.
    """
    gros_u = {p["nom"]: k for k, p in enumerate(PARAMS_0025)}
    c0 = _f32(col.c0025[i_balise])
    sortie = []
    if z_0025 is None:
        return sortie
    for niveau in NIVEAUX_H_0025:
        j = NIVEAUX_H_0025.index(niveau)
        u, v = c0[gros_u["u"], j, i_step], c0[gros_u["v"], j, i_step]
        if not np.isfinite(u) or not np.isfinite(v):
            continue
        t = c0[gros_u["t"], j, i_step]
        r = c0[gros_u["r"], j, i_step]
        tke = c0[gros_u["tke"], j, i_step]
        sortie.append(dict(altitudeM=round(z_0025 + niveau, 1),
                           hauteurSolM=niveau, source="hauteur",
                           maille=GRID_3D, u=float(u), v=float(v),
                           t=None if not np.isfinite(t) else float(t),
                           hr=None if not np.isfinite(r) else float(r),
                           tke=None if not np.isfinite(tke) else float(tke)))
    return sorted(sortie, key=lambda p: p["altitudeM"])


def niveaux_fins(col, i_balise, i_step, z_001):
    """Les 4 niveaux de la maille 0,01°, sur LEUR sol.

    C'est la tranche du décollage, du gonflage et de la première centaine
    de mètres de vol, à 1,1 km de maille au lieu de 2,8. Elle est servie
    **à côté** de la colonne principale, pas dedans.

    ⚠️ Elle ne porte QUE le vent : `001/HP1` n'expose ni température, ni
    humidité, ni TKE. Un affichage qui les attendrait ici trouverait des
    trous — ce n'est pas un défaut d'ingestion, c'est ce que Météo-France
    publie en maille fine.
    """
    if z_001 is None:
        return []
    fine_u = {p["nom"]: k for k, p in enumerate(PARAMS_001)}
    c1 = _f32(col.c001[i_balise])
    sortie = []
    for j, niveau in enumerate(NIVEAUX_H_001):
        u, v = c1[fine_u["u"], j, i_step], c1[fine_u["v"], j, i_step]
        if not np.isfinite(u) or not np.isfinite(v):
            continue
        sortie.append(dict(altitudeM=round(z_001 + niveau, 1),
                           hauteurSolM=niveau, source="hauteur",
                           maille=GRID_FINE, u=float(u), v=float(v),
                           t=None, hr=None, tke=None))
    return sorted(sortie, key=lambda p: p["altitudeM"])


def marche_hybride(hauteur, fins):
    """|Δ(u,v)| entre les deux mailles, **à hauteur-sol égale**.

    ⚠️ À hauteur-sol égale et non à altitude égale : c'est la seule
    comparaison qui ait un sens physique, parce que le profil de couche
    de surface se rapporte au sol LOCAL. Comparer à altitude-mer égale
    mélangerait l'écart de maille avec l'écart d'orographie, et c'est ce
    dernier qui domine (75 m médians, 643 m au pire).

    C'est le critère d'acceptation de l'hybride, calculé ici colonne par
    colonne pour qu'il soit visible dans la réponse et pas seulement dans
    un banc.
    """
    par_h = {p["hauteurSolM"]: p for p in hauteur}
    out = []
    for f in fins:
        g = par_h.get(f["hauteurSolM"])
        if g is None:
            continue
        out.append(dict(hauteurSolM=f["hauteurSolM"],
                        ecartMs=round(float(math.hypot(f["u"] - g["u"],
                                                       f["v"] - g["v"])), 3),
                        altitudeFineM=f["altitudeM"],
                        altitude0025M=g["altitudeM"]))
    return out


def niveaux_isobares(col, i_balise, i_step, z_s):
    """Les niveaux ISOBARES, **masqués sous le sol du modèle**.

    ⚠️ Le masque n'est pas cosmétique : dans les Alpes, 1000, 950 et
    925 hPa sont sous le terrain presque partout. Les servir donnerait un
    « vent au sol » entièrement fabriqué par l'extrapolation sous-terraine
    du modèle, et parfaitement crédible à l'affichage.
    """
    if col.ziso is None or not col.ziso.size:
        return []
    iso_u = {p["nom"]: k for k, p in enumerate(PARAMS_ISO)}
    ci = _f32(col.ciso[i_balise])
    zi = _f32(col.ziso[i_balise])
    sortie = []
    for j, hpa in enumerate(NIVEAUX_P):
        alt = zi[j, i_step]
        u, v = ci[iso_u["u"], j, i_step], ci[iso_u["v"], j, i_step]
        if not np.isfinite(alt) or not np.isfinite(u) or not np.isfinite(v):
            continue
        if z_s is not None and alt < z_s:
            continue                       # ⚠️ sous terre : jamais servi
        t = ci[iso_u["t"], j, i_step]
        r = ci[iso_u["r"], j, i_step]
        sortie.append(dict(altitudeM=round(float(alt), 1), niveauHPa=hpa,
                           source="isobare", maille=GRID_3D,
                           u=float(u), v=float(v),
                           t=None if not np.isfinite(t) else float(t),
                           hr=None if not np.isfinite(r) else float(r),
                           tke=None))
    return sorted(sortie, key=lambda p: p["altitudeM"])


# ══════════════════════════════════════════════════════════════════════
#  Le raccord
# ══════════════════════════════════════════════════════════════════════
def poids_hauteur(altitude, z_s):
    """Poids de la source HAUTEUR à cette altitude-mer, dans [0, 1].

    1 sous `z_s + RACCORD_BAS_M`, 0 au-dessus de `z_s + RACCORD_HAUT_M`,
    rampe linéaire entre les deux.
    """
    bas, haut = z_s + RACCORD_BAS_M, z_s + RACCORD_HAUT_M
    if altitude <= bas:
        return 1.0
    if altitude >= haut:
        return 0.0
    return float((haut - altitude) / (haut - bas))


def _interp_uv(points, altitude):
    """u, v interpolés LINÉAIREMENT en altitude sur une liste triée.

    ⚠️ Par composantes, jamais par l'angle. Renvoie (None, None) hors
    des bornes plutôt que d'extrapoler : au-delà du dernier niveau, on ne
    sait pas, et prolonger une tendance donnerait un vent inventé.
    """
    if len(points) < 2:
        return (None, None)
    if altitude <= points[0]["altitudeM"] or altitude >= points[-1]["altitudeM"]:
        return (None, None)
    k = 0
    while k + 1 < len(points) and points[k + 1]["altitudeM"] < altitude:
        k += 1
    a, b = points[k], points[k + 1]
    span = b["altitudeM"] - a["altitudeM"]
    if span <= 0:
        return (a["u"], a["v"])
    f = (altitude - a["altitudeM"]) / span
    return (a["u"] + f * (b["u"] - a["u"]), a["v"] + f * (b["v"] - a["v"]))


def ecart_recouvrement(hauteur, isobares, z_s):
    """⚠️ LE TEST DE NON-RÉGRESSION DU LOT.

    Aux altitudes des niveaux isobares situés DANS la zone de
    recouvrement (`z_s + 1000` → `z_s + 3000`), compare le vent isobare au
    vent hauteur interpolé à la même altitude. Renvoie la liste des
    écarts `|Δ(u,v)|` en m/s.

    Si les deux sources décrivent le même air, ces écarts sont petits. Une
    marche ne vient jamais de la météo — elle vient d'une conversion
    fausse : géopotentiel non divisé par g, mauvaise orographie, niveau
    mal indexé. C'est le seul endroit du lot où une erreur de conversion
    devient VISIBLE au lieu de rester plausible.
    """
    bas, haut = z_s + RACCORD_BAS_M, z_s + RACCORD_HAUT_M
    ecarts = []
    for p in isobares:
        if not (bas <= p["altitudeM"] <= haut):
            continue
        u, v = _interp_uv(hauteur, p["altitudeM"])
        if u is None:
            continue
        ecarts.append(dict(altitudeM=p["altitudeM"], niveauHPa=p["niveauHPa"],
                           ecartMs=float(math.hypot(p["u"] - u, p["v"] - v))))
    return ecarts


def assembler(hauteur, isobares, z_s):
    """La colonne unique, sur l'axe altitude-mer.

    Chaque point garde **la trace de ce qui l'a produit** (`source`,
    `poidsHauteur`) : servir un profil mélangé sans dire où le mélange
    opère empêcherait quiconque de diagnostiquer une marche plus tard.
    """
    points = []
    for p in hauteur:
        w = poids_hauteur(p["altitudeM"], z_s)
        if w <= 0.0:
            continue                       # au-dessus du raccord : isobares
        q = dict(p)
        if w < 1.0:
            ui, vi = _interp_uv(isobares, p["altitudeM"])
            if ui is not None:
                q["u"] = w * p["u"] + (1 - w) * ui
                q["v"] = w * p["v"] + (1 - w) * vi
                q["source"] = "melange"
        q["poidsHauteur"] = round(w, 3)
        points.append(q)

    haut_max = max((p["altitudeM"] for p in hauteur), default=z_s)
    for p in isobares:
        w = poids_hauteur(p["altitudeM"], z_s)
        # ⚠️ On ne rajoute un niveau isobare que là où la source hauteur
        # ne parle plus. Sous le sommet des niveaux hauteur, il a déjà
        # servi via le mélange : le remettre doublerait les points et
        # ferait des dents de scie.
        if w >= 1.0 or p["altitudeM"] <= haut_max:
            continue
        q = dict(p, poidsHauteur=0.0)
        points.append(q)

    points.sort(key=lambda p: p["altitudeM"])
    for p in points:
        spd = math.hypot(p["u"], p["v"])
        p["vitesseKmh"] = round(spd * 3.6, 1)
        # Convention météo : la direction D'OÙ VIENT le vent.
        p["directionDeg"] = round((270 - math.degrees(
            math.atan2(p["v"], p["u"]))) % 360) % 360
        p["u"], p["v"] = round(p["u"], 2), round(p["v"], 2)
    return points


# ══════════════════════════════════════════════════════════════════════
#  La réponse v0
# ══════════════════════════════════════════════════════════════════════
def sonder(col, manifeste, i_balise, step, altitude_reelle=None):
    """Le sondage vertical en un point, prêt à être servi.

    ⚠️ `elevationDeltaM` est présent DANS TOUTE RÉPONSE — c'est un critère
    d'acceptation du lot — mais il vaut `None` quand l'altitude réelle est
    inconnue, et la réponse dit alors pourquoi. Le champ
    `solReferenceSource` n'est pas décoratif : un écart de 150 m annoncé
    sans dire à quoi il se compare n'est pas une information.
    """
    balise = col.balises[i_balise]
    i_step = col.i_step[step] if step in col.i_step else col.steps.index(step)
    z_001, z_0025 = balise.get("z_001"), balise.get("z_0025")

    # ⚠️ UN SEUL SOL POUR LA COLONNE, et c'est le 0,025° : c'est la seule
    # maille qui la porte entière. Le 0,01° a son propre sol et sa propre
    # tranche, servie à part.
    z_s = z_0025
    hauteur = niveaux_hauteur(col, i_balise, i_step, z_0025)
    fins = niveaux_fins(col, i_balise, i_step, z_001)
    isobares = niveaux_isobares(col, i_balise, i_step, z_s)
    points = assembler(hauteur, isobares, z_s) if z_s is not None else []
    ecarts = ecart_recouvrement(hauteur, isobares, z_s) if z_s is not None else []
    marche = marche_hybride(hauteur, fins)

    z_reel, source_reel = reference_sol(balise, altitude_reelle)
    delta = None if (z_reel is None or z_s is None) else round(z_s - z_reel, 1)

    return dict(
        run=col.run,
        echeanceH=step,
        balise=dict(id=balise["id"], nom=balise.get("nom", ""),
                    lat=balise["lat"], lon=balise["lon"],
                    positionSuspecte=bool(balise.get("position_suspecte"))),
        solModeleM=dict(grille_0025=z_0025, grille_001=z_001),
        solReferenceM=z_reel,
        solReferenceSource=source_reel,
        # ⚠️ NÉGATIF = le modèle place le sol SOUS le sol réel, et c'est le
        # cas général : médiane −135 m en 0,025° (n = 109). C'est
        # l'inverse de ce qu'une première version du lot annonçait.
        elevationDeltaM=delta,
        elevationDeltaNote=(
            "sol du modèle moins sol de référence ; négatif = le modèle "
            "place le sol EN DESSOUS. Médiane mesurée −135 m en 0,025° "
            "(n = 109)." if delta is not None else
            "altitude réelle inconnue : le référentiel Pioupiou ne donne "
            "que lat/lon, et le nom de cette balise n'en porte pas."),
        raccord=dict(
            hauteurSeuleJusquM=None if z_s is None else round(z_s + RACCORD_BAS_M, 1),
            isobaresSeulesDesM=None if z_s is None else round(z_s + RACCORD_HAUT_M, 1),
            nMelange=sum(1 for p in points if p.get("source") == "melange"),
            ecartRecouvrementMs=(
                round(float(np.median([e["ecartMs"] for e in ecarts])), 3)
                if ecarts else None),
            nEcarts=len(ecarts)),
        profil=points,
        # ── La tranche du décollage, en maille fine, sur SON sol ──────
        # ⚠️ Elle n'est PAS insérée dans `profil` : les deux mailles
        # placent le sol à des altitudes différentes (75 m d'écart médian,
        # 643 m au pire), donc les fusionner ferait apparaître « 35 m
        # au-dessus du sol » plus haut que « 100 m au-dessus du sol ».
        # Elle ne porte que le vent — la maille fine n'expose ni T, ni HR,
        # ni TKE.
        profilMailleFine=dict(
            solM=z_001,
            note=("maille 0,01° (~1,1 km) sur SON sol, qui n'est pas celui "
                  "de la colonne principale. Vent seul : la maille fine "
                  "n'expose ni température, ni humidité, ni TKE."),
            points=[dict(p, vitesseKmh=round(math.hypot(p["u"], p["v"]) * 3.6, 1),
                         directionDeg=round((270 - math.degrees(
                             math.atan2(p["v"], p["u"]))) % 360) % 360,
                         u=round(p["u"], 2), v=round(p["v"], 2))
                    for p in fins]),
        # ⚠️ La marche entre les deux mailles, À HAUTEUR-SOL ÉGALE.
        # Publiée dans la réponse et pas seulement dans un banc : c'est
        # le critère d'acceptation de l'hybride, et il n'est pas tenu
        # tant qu'il n'a pas été vu par vent fort.
        marcheHybride=dict(
            parNiveau=marche,
            medianeMs=(round(float(np.median([m["ecartMs"] for m in marche])), 3)
                       if marche else None)))
