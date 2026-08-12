#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/calque.py — le calque vent à ALTITUDE-MER CONSTANTE
#                                                        (12/08/2026)
#
#  Étape 11 du lot H. Le transect (étape 8) a explicitement renvoyé ici
#  le rééchantillonnage vertical : « l'interpolation à altitude-mer
#  constante est le travail du calque altitude, qui devra la faire une
#  fois, bien, et pour tout le domaine ». C'est ce fichier.
#
#  ── CE QUE « 2 000 m » VEUT DIRE, ET CE QU'IL NE VEUT PAS DIRE ───────
#  Les 25 niveaux du produit B sont AGL — au-dessus du sol DU MODÈLE. Sur
#  le domaine Nord-Alpes, `zsol` va de 168 à 3 887 m : MESURÉ sur le run
#  2026-08-12T12:00:00Z, étendue 3 720 m. Une coupe horizontale à
#  altitude-mer constante n'est donc PAS un niveau du tableau : c'est une
#  interpolation entre deux niveaux, DIFFÉRENTE EN CHAQUE POINT.
#
#  ⚠️⚠️ ET C'EST LE MODE DE PANNE DE CE FICHIER : UN CALQUE INTERPOLÉ DE
#  TRAVERS RESTE LISSE, COLORÉ ET PLAUSIBLE. Aucun contrôle visuel ne le
#  démasque. D'où l'invariant du §« Ce qui prouve », plus bas, qui ne
#  dépend pas de l'œil.
#
#  ── LA MESURE QUI A DÉCIDÉ DU DÉCOUPAGE (12/08) ──────────────────────
#  Le prompt du lot proposait de découper le produit B « par niveau ×
#  échéance » (625 objets/run) pour servir un niveau à la fois. Mesuré
#  sur le run réel, cette découpe n'économise RIEN pour ce consommateur :
#
#      A (m)   masqué relief   au-dessus plafond   niveaux utiles
#       1000       63,7 %            0,0 %            14 / 25
#       2000       29,0 %            0,0 %            21 / 25
#       3000        2,3 %            0,0 %            25 / 25
#       4000        0,0 %           36,3 %            20 / 25
#
#  Un calque à altitude-mer constante a besoin de 14 à 25 des 25 niveaux,
#  parce que `h_demandé = A − zsol` s'étale autant que `zsol`. Servir
#  « un niveau à la fois » ferait donc 14 à 25 requêtes par vue, pour
#  625 objets/run — 5 000 écritures Class A par jour, soit le DOUBLE du
#  budget actuel du projet (168 000/mois, 17 % du palier).
#
#  ✅ RETENU (arbitré avec Yann le 12/08) : découpage PAR ÉCHÉANCE.
#  25 objets par run et par domaine, un objet = toute la pile verticale
#  d'une échéance. Le client tire UN objet et peut ensuite balayer TOUTE
#  la plage d'altitudes sans une requête de plus — c'est le curseur
#  d'altitude qui devient gratuit, ce qu'aucune découpe par niveau ne
#  permet.
#
#  ⓘ Et c'est la route de lecture que TROIS autres lecteurs attendaient
#  depuis l'étape 9 (composite, profil, coupe). Elle est prise une fois,
#  pour les quatre.
#
#  ── POURQUOI UN TAMPON BRUT ET PAS UN .npz ───────────────────────────
#  ⛔ Le navigateur ne lit pas de `.npz`. L'objet servi est donc un
#  TAMPON BRUT float16, de disposition publiée dans le manifeste :
#
#      (paramètre, niveau, lat, lon)   float16, C-contigu
#
#  ⚠️ ET LE CHOIX DE NE PAS LE COMPRESSER EST DÉLIBÉRÉ, MESURÉ, ET C'EST
#  L'ARBITRAGE LE MOINS ÉVIDENT DE CE FICHIER :
#
#      objet gzippé, tiré en entier       1 045 Ko
#      objet BRUT + Range sur u/v           518 Ko   ← retenu
#      objet brut tiré en entier          1 296 Ko
#
#  `Content-Encoding: gzip` et `Range` ne se combinent pas — un Range
#  porte sur les octets ENCODÉS. En laissant l'objet brut, le calque ne
#  demande que `bytes=0-518499` : u et v sont les DEUX PREMIERS
#  paramètres et la disposition est param-majeure, donc ils sont
#  contigus en tête. La coupe et le profil, eux, tirent tout.
#  ✅ Vérifié le 12/08 à travers le CDN : `HTTP 206`, `content-range`
#  exact, `accept-ranges: bytes`, `cf-cache-status: DYNAMIC`.
#
#  ⚠️ CE QUE ÇA IMPOSE À QUI TOUCHERA `PARAMS_GRILLE` : le jour où l'on
#  réordonne les paramètres, ou qu'on en insère un avant `v`, le Range du
#  client sert autre chose SANS ERREUR. Le manifeste publie donc
#  `octets_par_parametre` et l'offset de chaque paramètre, et le client
#  DOIT les lire — un banc échoue si une liste est codée en dur côté
#  client.
#
#  ── CE QUE CE FICHIER N'EST PAS ──────────────────────────────────────
#  ⛔ Ce n'est PAS l'implémentation qui tourne devant le pilote. Le
#  calque s'interpole DANS LE NAVIGATEUR (c'est ce qui rend le curseur
#  d'altitude gratuit). Deux implémentations d'une même interpolation
#  divergeraient — c'est le défaut payé deux fois le 10/08 avec
#  `gfDetectModel`, et la leçon est écrite dans le README.
#
#  Ce fichier est donc l'ORACLE : il calcule la référence et fabrique un
#  jeu de vecteurs (`fixture()`) que le banc JS rejoue. La divergence
#  n'est pas évitée par la discipline, elle est MESURÉE à chaque banc.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import numpy as np

from domaine import GRID_3D, NIVEAUX_H_0025, NIVEAUX_P

# ⚠️ Les niveaux en float64 UNE FOIS, ici. Comparer un `h` float64 à un
# niveau entier promu à la volée marche ; le faire dans une boucle
# vectorisée sur 5 185 colonnes × 25 niveaux ne marche que si la
# promotion est la même partout. On la fige.
NIVEAUX = np.asarray(NIVEAUX_H_0025, dtype=np.float64)

# Les raisons pour lesquelles une colonne n'est PAS servie. Publiées
# telles quelles : à l'écran, chacune veut dire une chose différente et
# une seule est un « trou ».
MASQUE_RELIEF = "relief"      # zsol > altitude demandée
MASQUE_BAS = "sous_premier_niveau"
MASQUE_PLAFOND = "au_dessus_du_plafond"
MASQUE_DONNEE = "niveau_absent"


# ══════════════════════════════════════════════════════════════════════
#  L'INTERPOLATION — et les quatre façons dont elle casserait en silence
# ══════════════════════════════════════════════════════════════════════
def encadrer(h):
    """(k, w) : indice du niveau INFÉRIEUR et poids du supérieur.

    `h` est la hauteur-sol demandée, en mètres, éventuellement un
    tableau. Renvoie `k` tel que `NIVEAUX[k] <= h <= NIVEAUX[k+1]` et
    `w = (h - NIVEAUX[k]) / (NIVEAUX[k+1] - NIVEAUX[k])`, dans [0, 1].

    ⚠️ `side="right"` PUIS `-1`, ET PAS `side="left"`. Sur `h` tombant
    EXACTEMENT sur un niveau, « left » rendrait l'indice de ce niveau
    comme borne SUPÉRIEURE, donc `w = 1` et un encadrement décalé d'un
    cran vers le bas. Le résultat serait juste (on retomberait sur la
    même valeur), mais le poids publié mentirait — et le banc qui vérifie
    « w vaut 0 sur un niveau » attraperait la différence. On préfère que
    l'invariant soit vrai par CONSTRUCTION.

    ⚠️ Le `clip` à `len-2` n'est pas un garde-fou décoratif : sans lui,
    `h == 3000` (le dernier niveau, atteint exactement dès que
    `A = zsol + 3000`) indexerait `NIVEAUX[25]`, hors du tableau. numpy
    lèverait ici — mais la même formule écrite en TypeScript rendrait
    `undefined`, puis `NaN`, puis un trou dans le calque. La borne est
    donc explicite des deux côtés.
    """
    h = np.asarray(h, dtype=np.float64)
    k = np.searchsorted(NIVEAUX, h, side="right") - 1
    k = np.clip(k, 0, len(NIVEAUX) - 2)
    bas = NIVEAUX[k]
    haut = NIVEAUX[k + 1]
    w = (h - bas) / (haut - bas)
    return k, w


def melanger(a, b, w):
    """Mélange linéaire de `a` et `b` au poids `w`, aux bornes EXACT.

    ⚠️⚠️ CE COMMENTAIRE A DIT AUTRE CHOSE PENDANT DIX MINUTES, ET LE BANC
    L'A DÉMENTI. Il justifiait le second `where` par l'EXACTITUDE : « à
    `w = 1`, `a + (b − a)` n'est pas exactement `b` en virgule flottante ».
    **C'est faux sur ce chemin de données.** Mesuré sur 6 000 000 de
    couples float16→float64 :

        u/v réalistes (± 60 m/s)          0 contre-exemple sur 2 000 000
        altitudes (± 3 000 m)             0 contre-exemple sur 2 000 000
        ± 1e30 (hors domaine physique)    0 contre-exemple sur 2 000 000

    Quand `a` et `b` viennent de float32/float16 et sont du même ordre de
    grandeur, `b − a` est EXACT en float64 (il tient dans les 53 bits de
    mantisse), donc `a + (b − a)` vaut exactement `b`. L'exactitude aux
    bornes est une propriété de la DONNÉE, pas de la formule.

    ⓘ *Un « ce n'est pas exact » écrit sans mesure est une déduction,
    exactement comme le « négligeable » que `point_intermediaire` a dû
    retirer le 10/08. La règle vaut aussi pour ses propres corrections.*

    ✅ LE VRAI MOTIF DES DEUX `where`, LUI, EST MESURÉ ET IL EST UNIQUE :
    LA CONTAMINATION PAR NaN. `0.0 × NaN = NaN`, et `1.0 × (b − NaN)`
    aussi.

        a = NaN, b = 7,5, w = 1  →  a + w(b − a) = nan   au lieu de 7,5
        a = 7,5, b = NaN, w = 0  →  a + w(b − a) = nan   au lieu de 7,5

    Une colonne dont UN des deux niveaux encadrants est absent, mais dont
    l'altitude demandée tombe PILE sur l'autre, doit rendre cet autre —
    pas un trou. Sans les deux `where`, le manque se propagerait au
    niveau voisin, et le calque montrerait un trou là où la donnée
    existe. Les deux branches répondent donc au MÊME défaut, en haut et
    en bas.

    ⓘ La TKE n'existe pas à l'échéance 0 (mesuré le 10/08) : ce cas n'est
    pas théorique, il se produit à chaque run.
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    w = np.asarray(w, dtype=np.float64)
    droit = a + w * (b - a)
    return np.where(w == 0.0, a, np.where(w == 1.0, b, droit))


def interpoler_champ(pile, h, niveaux=NIVEAUX):
    """Interpole une pile `(niveau, ...)` à la hauteur-sol `h`.

    `pile` et `h` sont diffusés l'un sur l'autre : `pile` de forme
    `(25, nj, ni)` et `h` de forme `(nj, ni)` donnent `(nj, ni)`.

    ⚠️ LA PILE EST CONVERTIE EN float32 AVANT TOUT CALCUL. L'archive est
    en float16 : le pas relatif y vaut 2⁻¹⁰, et une soustraction de deux
    float16 proches perd des chiffres significatifs. Le README le
    documente déjà pour l'axe d'altitude (2 m d'erreur mesurés) ; ici
    c'est `b - a` qui est en jeu.
    """
    pile = np.asarray(pile, dtype=np.float32)
    k, w = encadrer(h)
    jj, ii = np.indices(np.shape(h))
    a = pile[k, jj, ii]
    b = pile[k + 1, jj, ii]
    return melanger(a, b, w), k, w


# ══════════════════════════════════════════════════════════════════════
#  ÉTAPE 12 — LE RELAIS ISOBARE, QUI LÈVE LE PLAFOND
# ══════════════════════════════════════════════════════════════════════
#  ⚠️⚠️ L'AXE N'EST PLUS UNE CONSTANTE, ET TOUT EST LÀ. Les 25 niveaux
#  hauteur sont les mêmes partout : `encadrer(h)` peut donc travailler
#  sur un vecteur de 25 nombres. Les 14 niveaux isobares, eux, ont une
#  altitude qui CHANGE en chaque point et à chaque échéance — c'est
#  `ziso`, un tableau `(14, nj, ni)`. L'encadrement doit donc être fait
#  colonne par colonne, et c'est la seule différence de fond entre les
#  deux moitiés du calque.
#
#  ⓘ Mesuré sur le run 15 Z, échéance +3 h, 5 185 colonnes : `ziso` varie
#  peu horizontalement (400 hPa entre 7 616 et 7 626 m, soit 11 m
#  d'étendue) — mais « peu » n'est pas « pas », et un axe supposé
#  constant se tromperait de dizaines de mètres à 850 hPa (1 591 → 1 646,
#  55 m d'étendue) là où l'orographie du modèle en discute autant.
def _encadrer_isobares(ziso, altitude_asl):
    """(disponible, k, w) pour l'altitude-mer `altitude_asl`.

    `ziso` est la pile `(niveau, ...)` des altitudes isobares D'UNE
    échéance. ⚠️ On prend le TABLEAU et non la grille : la fixture doit
    pouvoir appeler cette fonction sur UNE colonne, et un banc qui ne
    peut s'exécuter que sur un domaine entier n'est pas un banc.

    `ziso` CROÎT avec l'indice — `NIVEAUX_P` va de 1000 à 400 hPa, donc
    du bas vers le haut. On compte les niveaux passés plutôt que
    d'appeler `searchsorted` colonne par colonne : 5 185 appels
    coûteraient plus que 14 comparaisons vectorielles.
    """
    ziso = np.asarray(ziso, dtype=np.float64)                # (14, nj, ni)
    nlev = ziso.shape[0]
    if nlev < 2:
        faux = np.zeros(ziso.shape[1:], dtype=bool)
        return faux, np.zeros_like(faux, dtype=int), np.zeros_like(faux,
                                                                   dtype=float)
    # ⚠️ Les NaN ne doivent pas compter comme « passé » : une colonne dont
    # l'axe est troué n'est pas servable, et un `<=` sur NaN rend False,
    # ce qui la ferait passer pour « sous le premier niveau ».
    sous = np.where(np.isfinite(ziso), ziso <= altitude_asl, False)
    k = np.clip(sous.sum(axis=0) - 1, 0, nlev - 2)
    jj, ii = np.indices(k.shape)
    bas, haut = ziso[k, jj, ii], ziso[k + 1, jj, ii]
    dispo = (np.isfinite(bas) & np.isfinite(haut)
             & (bas <= altitude_asl) & (altitude_asl <= haut))
    span = haut - bas
    # ⚠️ Même garde-fou que `melanger` : un `span` nul ou négatif ne doit
    # pas produire un poids infini. Il ne devrait pas arriver — l'axe est
    # monotone — mais « ne devrait pas » n'est pas un contrôle.
    w = np.where(span > 0, (altitude_asl - bas) / np.where(span > 0, span, 1.0),
                 0.0)
    return dispo, k, np.clip(w, 0.0, 1.0)


def _interpoler_isobares(pile, k, w):
    """Interpole une pile isobare `(niveau, nj, ni)` à l'encadrement
    donné. Même conversion float16 → float32 avant calcul, et pour la
    même raison, que `interpoler_champ`."""
    pile = np.asarray(pile, dtype=np.float32)
    jj, ii = np.indices(k.shape)
    return melanger(pile[k, jj, ii], pile[k + 1, jj, ii], w)


# ══════════════════════════════════════════════════════════════════════
#  LE CALQUE
# ══════════════════════════════════════════════════════════════════════
def calque(gr, step, altitude_asl, params=("u", "v")):
    """Le calque à `altitude_asl` mètres au-dessus du niveau de la mer.

    Renvoie un dict : les champs interpolés (float32, `NaN` là où c'est
    masqué), le masque et sa RAISON, et de quoi écrire l'écran.

    ⛔ LE VENT S'INTERPOLE PAR u ET v SÉPARÉMENT, JAMAIS PAR L'ANGLE.
    C'est la première ligne des pièges déjà payés du lot, et
    `test_colonnes.py` porte déjà le cas qui l'exige (une colonne qui
    traverse 350° → 010° : la moyenne des angles donne 180°, celle des
    composantes donne 0°). Ici la règle est tenue par CONSTRUCTION —
    aucune direction n'est calculée avant l'interpolation, et
    `direction()` ne s'applique qu'au résultat.
    """
    if step not in gr.steps:
        raise ValueError(
            f"l'échéance {step} h n'est pas dans ce run : le produit B ne "
            f"porte que {gr.steps}. ⚠️ Trois runs de rétention, aucun "
            f"historique — une échéance absente ne se rattrape pas en "
            f"relisant.")
    i_step = gr.steps.index(step)
    A = float(altitude_asl)

    i_param = {p: k for k, p in enumerate(_noms_params(gr))}
    manquants = [p for p in params if p not in i_param]
    if manquants:
        raise ValueError(f"paramètre(s) absent(s) du produit B : {manquants} "
                         f"— il porte {sorted(i_param)}")

    zsol = np.asarray(gr.zsol, dtype=np.float64)
    h = A - zsol

    # ── Les trois masques, et ils ne disent PAS la même chose ──────────
    # ⚠️ Un seul des trois est un « trou ». Les deux autres sont des
    # informations, et l'écran doit les dire différemment.
    m_relief = h < 0.0                              # le sol est au-dessus
    m_bas = (h >= 0.0) & (h < NIVEAUX[0])           # sous le premier niveau
    m_haut = h > NIVEAUX[-1]                        # au-dessus de zsol+3000
    m_zsol = ~np.isfinite(zsol)

    # ── Étape 12 : au-dessus de zsol+3000, les ISOBARES prennent le relais
    # ⚠️ CE N'EST PAS UN MÉLANGE, ET C'EST DÉLIBÉRÉ. `profil.py` mélange
    # les deux sources entre zsol+1000 et zsol+3000, puis sert les
    # isobares SEULES au-dessus — son poids hauteur vaut déjà 0 à
    # zsol+3000. Le calque, lui, ne mélange nulle part : il rend le
    # niveau BRUT du produit, et son invariant (« à A = zsol + niveau_k,
    # le calque rend exactement le niveau k », 129 625 cas vérifiés) ne
    # survivrait pas à un mélange.
    #
    # ⛔ CONSÉQUENCE À NE PAS TAIRE : entre zsol+1000 et zsol+3000, le
    # calque et le profil vertical ne rendent donc PAS la même valeur au
    # même point. `confronter_calque.py --recouvrement` mesure cet écart
    # sur le domaine et le publie ; il n'est pas arbitré ici.
    haut_dispo, k_iso, w_iso = _encadrer_isobares(gr.ziso[:, i_step], A)
    servi_par_iso = m_haut & haut_dispo & ~m_zsol
    m_plafond = m_haut & ~servi_par_iso             # ce qui reste troué

    servable = ~(m_relief | m_bas | m_plafond | m_zsol)

    # ⚠️ `h` est écrêté AVANT `encadrer` pour que les colonnes masquées
    # n'aillent pas indexer hors du tableau. Leur résultat est écrasé par
    # `NaN` juste après — mais un `searchsorted` sur un `h` négatif
    # rendrait un indice valide et un poids négatif, donc une valeur
    # EXTRAPOLÉE parfaitement crédible si quelqu'un retirait le masque un
    # jour. On ne laisse pas d'extrapolation dormir dans le code.
    h_sur = np.clip(h, NIVEAUX[0], NIVEAUX[-1])

    champs, k_pub, w_pub = {}, None, None
    m_donnee = np.zeros_like(servable)
    i_param_iso = {p: k for k, p in enumerate(_noms_params_iso(gr))}
    for nom in params:
        pile = gr.h0025[i_param[nom], :, i_step]        # (niveau, nj, ni)
        val, k, w = interpoler_champ(pile, h_sur)
        if k_pub is None:
            k_pub, w_pub = k, w
        # ── là où le relais isobare joue, il REMPLACE la valeur ────────
        # ⚠️ `interpoler_champ` a été appelé sur un `h` écrêté, donc il a
        # rendu le niveau 3000 m pour ces colonnes — une valeur finie,
        # plausible, et fausse de plusieurs milliers de mètres. C'est
        # exactement le genre de résultat qui ne se voit pas : on
        # l'écrase, on ne le complète pas.
        if servi_par_iso.any():
            if nom in i_param_iso:
                pile_iso = gr.iso[i_param_iso[nom], :, i_step]
                haut = _interpoler_isobares(pile_iso, k_iso, w_iso)
                val = np.where(servi_par_iso, haut, val)
            else:
                # ⓘ `tke` n'existe pas sur les isobares (elle vit dans
                # IP4, non ingéré). Au-dessus du plafond hauteur elle est
                # donc absente — un trou, pas un zéro.
                val = np.where(servi_par_iso, np.nan, val)
        m_donnee |= ~np.isfinite(val)
        champs[nom] = val

    servable &= ~m_donnee
    for nom in params:
        champs[nom] = np.where(servable, champs[nom], np.nan).astype(np.float32)

    raison = np.full(zsol.shape, "", dtype=object)
    raison[m_relief] = MASQUE_RELIEF
    raison[m_bas] = MASQUE_BAS
    raison[m_plafond] = MASQUE_PLAFOND
    raison[m_donnee & ~(m_relief | m_bas | m_plafond)] = MASQUE_DONNEE

    n = zsol.size
    return dict(
        produit="AGRUME étape 11 — calque vent à altitude-mer constante",
        run=gr.run, echeanceH=step, grille=GRID_3D,
        altitudeASLM=A,
        champs=champs,
        servable=servable,
        raisonMasque=raison,
        indiceNiveauBas=k_pub, poidsNiveauHaut=w_pub,
        couverture=dict(
            servi=round(float(servable.mean()), 4),
            relief=round(float(m_relief.mean()), 4),
            sousPremierNiveau=round(float(m_bas.mean()), 4),
            auDessusDuPlafond=round(float(m_plafond.mean()), 4),
            niveauAbsent=round(float((m_donnee & ~(
                m_relief | m_bas | m_plafond)).mean()), 4),
            # ⚠️ Publié parce que l'écran DOIT pouvoir le dire : sur une
            # même carte, les colonnes basses viennent des niveaux
            # hauteur et les hautes des isobares, et la tranche isobare
            # est la PIRE des trois contre le ballon (2,34 et 4,09 m/s
            # d'écart médian, contre 1,70 et 1,84 — n = 2 profils, vent
            # faible). Une carte qui mélange deux sources sans dire où
            # empêche de diagnostiquer une marche.
            parIsobares=round(float(servi_par_iso.mean()), 4),
            nbColonnes=int(n)),
        # ── Ce que l'écran DOIT dire, et que personne n'a envie d'écrire
        # (§4 du lot). Publié ici pour que le front n'ait pas à le
        # réinventer, et surtout pour qu'il ne puisse pas l'oublier.
        aEcrire=dict(
            maille=("maille 0,025° — le calque vent au SOL est en 0,01°. "
                    "Ce calque est visiblement plus grossier : c'est la "
                    "seule résolution où les 25 niveaux existent."),
            masqueRelief=("les zones vides sont le RELIEF TEL QUE LE MODÈLE "
                          "LE VOIT, pas une panne de donnée. L'orographie du "
                          "modèle place les sommets ~135 m plus bas que le "
                          "sol réel en médiane (n = 109)."),
            plafond=("depuis l'étape 12, les niveaux ISOBARES prennent le "
                     "relais au-dessus de zsol + 3000 m : le plafond ne suit "
                     "plus le relief, il est uniforme à ~7 620 m (400 hPa). "
                     "Mesuré le 12/08 sur les 5 185 colonnes du domaine "
                     "nord-alpes : de « 3 168 à 6 887 m selon le point » à "
                     "« 7 616 à 7 626 m », et 0 % de colonnes trouées à "
                     "5 000 m contre 71 % avant. ⚠️ 7 620 m n'est pas « le "
                     "max » du modèle : c'est 400 hPa, coupure choisie le "
                     "10/08 pour couvrir zsol + 3000 m partout."),
            sourceParAltitude=(
                "⚠️ SUR UNE MÊME CARTE, DEUX SOURCES. Sous zsol + 3000 m les "
                "valeurs viennent des niveaux HAUTEUR, au-dessus des niveaux "
                "ISOBARES — et la tranche isobare est la moins sûre des "
                "deux : 2,34 et 4,09 m/s d'écart médian contre le ballon, "
                "contre 1,70 et 1,84 pour la hauteur seule (n = 2 profils, "
                "vent faible, aucune des trois causes isolée). Le haut du "
                "calque vaut moins que le bas, et l'écran doit le dire — "
                "`couverture.parIsobares` donne la part concernée."),
            tkeEnHaut=("la TKE n'existe PAS sur les isobares (elle vit dans "
                       "IP4, non ingéré) : au-dessus de zsol + 3000 m elle "
                       "est absente, et c'est un TROU, pas un zéro."),
            retention=("3 runs en ligne, aucun historique.")),
        reference_verticale=(
            "altitude-mer constante, obtenue par interpolation LINÉAIRE sur "
            "u et v SÉPARÉMENT, et sur DEUX axes selon l'altitude : en "
            "HAUTEUR-SOL entre les niveaux encadrant "
            "h = altitudeASLM − zsol[lat, lon] jusqu'à zsol + 3000 m, puis "
            "en ALTITUDE-MER entre les niveaux isobares encadrants, dont "
            "l'altitude `ziso` varie en chaque point et à chaque échéance. "
            "Aucune interpolation d'angle, aucune extrapolation, aucun "
            "mélange des deux sources — la bascule est franche à "
            "zsol + 3000 m, là où `profil.py` a déjà ramené le poids de la "
            "source hauteur à zéro."))


def _noms_params(gr):
    from grille import PARAMS_GRILLE
    return [p["nom"] for p in PARAMS_GRILLE]


def _noms_params_iso(gr):
    from grille import PARAMS_GRILLE_ISO
    return [p["nom"] for p in PARAMS_GRILLE_ISO]


def direction(u, v):
    """Convention météo : l'angle d'où VIENT le vent.

    ⚠️ Appelée APRÈS l'interpolation, jamais avant. La convention est
    déjà réunie dans `profil.decorer_vent()` pour le sondage, la coupe et
    le radiosondage ; ici on ne travaille que sur des tableaux, donc on
    ne peut pas réutiliser la fonction qui décore un dict. La VALEUR de
    référence est la même et le banc la cloue comme les autres :
    u = +10 m/s → 270°.
    """
    return (270.0 - np.degrees(np.arctan2(np.asarray(v, dtype=np.float64),
                                          np.asarray(u, dtype=np.float64)))
            ) % 360.0


# ══════════════════════════════════════════════════════════════════════
#  L'ORACLE — les vecteurs que le banc JS rejoue
# ══════════════════════════════════════════════════════════════════════
def fixture(gr, step, altitudes, nb_colonnes=64, graine=11):
    """Un jeu de cas de référence, calculé ICI, rejoué par le TypeScript.

    ⚠️⚠️ C'EST LE SEUL DISPOSITIF QUI EMPÊCHE LES DEUX IMPLÉMENTATIONS DE
    DIVERGER. Le calque s'interpole dans le navigateur — c'est ce qui
    rend le curseur d'altitude gratuit — donc il EXISTE forcément deux
    implémentations. Le README dit ce que ça coûte quand on les laisse
    vivre séparément (`gfDetectModel`, défaut payé deux fois le 10/08).
    Ici la divergence n'est pas évitée par la discipline : elle est
    mesurée à chaque banc.

    Les colonnes sont tirées au sort MAIS le tirage est déterministe, et
    on force les cas qui cassent : le sol le plus bas, le plus haut, et
    des altitudes qui tombent EXACTEMENT sur un niveau.
    """
    i_step = gr.steps.index(step)
    from grille import PARAMS_GRILLE
    i_param = {p["nom"]: k for k, p in enumerate(PARAMS_GRILLE)}
    zsol = np.asarray(gr.zsol, dtype=np.float64)
    nj, ni = zsol.shape

    rng = np.random.default_rng(graine)
    plat = np.argsort(zsol, axis=None)
    choix = [int(plat[0]), int(plat[-1]), int(plat[len(plat) // 2])]
    choix += [int(x) for x in rng.choice(zsol.size, nb_colonnes, replace=False)]
    vus, colonnes = set(), []
    for p in choix:
        if p in vus:
            continue
        vus.add(p)
        colonnes.append((int(p // ni), int(p % ni)))

    cas = []
    for (j, i) in colonnes:
        zs = float(zsol[j, i])
        alts = list(altitudes)
        # ⛔ LES ALTITUDES QUI TOMBENT PILE SUR UN NIVEAU. C'est le
        # critère d'acceptation du lot, et il n'a de sens que colonne par
        # colonne : `zsol` étant continu, aucune altitude GLOBALE ne
        # tombe sur un niveau partout à la fois.
        alts += [zs + float(n) for n in NIVEAUX_H_0025]
        # ⛔ ÉTAPE 12 — LES ALTITUDES QUI TOMBENT PILE SUR UN NIVEAU
        # ISOBARE, et celles qui tombent entre deux. Sans elles, le banc
        # de parité ne vérifierait la moitié HAUTE du calque nulle part —
        # or c'est celle dont l'axe VARIE en chaque point, donc celle où
        # une divergence Python/TypeScript est la plus facile.
        zcol = np.asarray(gr.ziso[:, i_step, j, i], dtype=np.float64)
        for k_iso, zz in enumerate(zcol):
            if not np.isfinite(zz):
                continue
            alts.append(float(zz))
            if k_iso + 1 < len(zcol) and np.isfinite(zcol[k_iso + 1]):
                alts.append(float(zz + zcol[k_iso + 1]) / 2.0)
        for A in alts:
            h = A - zs
            attendu = {}
            # ── Au-dessus du dernier niveau hauteur, le relais isobare ──
            # ⚠️ On appelle les MÊMES fonctions que `calque()`, pas une
            # réécriture : un banc qui réimplémente la règle qu'il vérifie
            # ne vérifie rien (c'est déjà arrivé le 12/08 sur
            # `test_freeze_balises.py`).
            par_iso = False
            if np.isfinite(zs) and h > NIVEAUX[-1]:
                dispo, ki, wi = _encadrer_isobares(
                    gr.ziso[:, i_step, j:j + 1, i:i + 1], A)
                par_iso = bool(dispo[0, 0])
            for nom in ("u", "v"):
                if par_iso:
                    pile = gr.iso[gr.i_param_iso[nom], :, i_step, j:j + 1,
                                  i:i + 1]
                    val = _interpoler_isobares(pile, ki, wi)
                    attendu[nom] = (None if not np.isfinite(val[0, 0])
                                    else float(val[0, 0]))
                    continue
                pile = np.asarray(gr.h0025[i_param[nom], :, i_step, j, i],
                                  dtype=np.float32)
                if h < NIVEAUX[0] or h > NIVEAUX[-1] or not np.isfinite(zs):
                    attendu[nom] = None
                else:
                    val, _, _ = interpoler_champ(pile[:, None, None],
                                                 np.array([[h]]))
                    attendu[nom] = (None if not np.isfinite(val[0, 0])
                                    else float(val[0, 0]))
            # ⛔ `A` EST PUBLIÉ SANS ARRONDI, ET C'EST LE BANC JS QUI L'A
            # EXIGÉ. La première version écrivait `round(A, 6)` — par
            # habitude de publication. Le consommateur recalcule
            # `h = A − zsol` : avec un `A` arrondi et un `zsol` qui ne
            # l'est pas, `h` ne retombe plus sur `niveau`, et 51 cas sur
            # 1 632 basculaient d'un côté ou de l'autre d'une borne de
            # masque. **Mesuré, pas redouté.** Un arrondi de publication
            # dans un jeu de vecteurs de référence n'est pas une
            # présentation : c'est une donnée fausse.
            #
            # ⓘ `h`, `k` et `w` sont publiés EN PLUS de `u`/`v` : sans
            # eux, un banc qui échoue ne dit pas OÙ les deux
            # implémentations ont divergé — à l'encadrement, au poids ou
            # au mélange.
            h = A - zs
            if par_iso:
                # ⓘ `k` et `w` portent alors l'encadrement ISOBARE, et
                # `source` dit lequel des deux. Sans ce champ, un banc qui
                # échoue ne saurait pas si le TypeScript s'est trompé de
                # valeur ou simplement d'axe.
                k_pub, w_pub = int(ki[0, 0]), float(wi[0, 0])
            elif NIVEAUX[0] <= h <= NIVEAUX[-1]:
                kk, ww = encadrer(np.array([h]))
                k_pub, w_pub = int(kk[0]), float(ww[0])
            else:
                k_pub, w_pub = None, None
            cas.append(dict(j=j, i=i, zsol=zs, altitudeASLM=A, h=h,
                            source="isobare" if par_iso else "hauteur",
                            k=k_pub, w=w_pub,
                            u=attendu["u"], v=attendu["v"]))
    return dict(
        produit="AGRUME étape 12 — vecteurs de référence du calque altitude",
        run=gr.run, echeanceH=step, grille=GRID_3D,
        niveaux_m_sol=list(NIVEAUX_H_0025),
        # ⚠️ L'axe isobare n'est PAS publié ici, et c'est volontaire : le
        # banc JS lit `ziso` DANS LE TAMPON, comme le fera le navigateur.
        # Le lui donner tout mâché vérifierait l'interpolation mais pas le
        # décodage — or c'est le décodage qui porte le piège du float32 au
        # milieu des float16.
        niveaux_hpa=list(NIVEAUX_P),
        note=("Calculé par agrume/calque.py. Le banc JS DOIT retrouver "
              "ces valeurs à l'identique en float32. Une divergence ici "
              "veut dire que les deux implémentations du calque ont "
              "commencé à s'écarter — c'est exactement ce que ce fichier "
              "existe pour attraper."),
        nbCas=len(cas), cas=cas)
