#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/grille.py — le produit B : la grille 3D du domaine Nord-Alpes
#                                                        (10/08/2026)
#
#  Étape 6 de la séquence du lot H. Là où le produit A extrait ~127
#  colonnes AUX BALISES et les archive pour toujours, le produit B garde
#  TOUT le domaine — 61 × 85 = 5 185 colonnes — et ne le garde QUE trois
#  runs. Deux produits, deux régimes, et c'est la seule raison pour
#  laquelle celui-ci est abordable.
#
#  ── CE QUI REND CETTE ÉTAPE PRESQUE GRATUITE, ET QUI N'ÉTAIT PAS PRÉVU ─
#  Le §4.2 du lot budgétait ~2,9 min d'ingestion pour le produit B, en
#  supposant une chaîne SÉPARÉE qui retéléchargerait les paquets. Elle
#  n'a plus lieu d'être : les cinq paquets dont ce produit a besoin sont
#  DÉJÀ sur le disque du runner, tirés par le produit A dans la même
#  passe. Et la découpe d'un sous-domaine est mesurée GRATUITE (7,6 s
#  contre 7,9 s pour décoder sans découper, sur un bundle de 818 Mo).
#  Le produit B ne coûte donc ni téléchargement ni minute de runner :
#  il coûte du stockage, et lui seul.
#
#  ⚠️ LE PRIX DE CE COUPLAGE EST RÉEL ET IL EST ÉCRIT DANS
#  `ingest_colonnes.py` : le produit A est une archive DÉFINITIVE, le
#  produit B est jetable. Le second ne doit jamais mettre le premier en
#  danger — il s'écrit APRÈS, et son échec ne fait échouer ni le run ni
#  le voyant.
#
#  ── LA FENÊTRE N'EST PAS RECALCULÉE, ELLE EST HÉRITÉE ────────────────
#  ⚠️ La grille est découpée sur la fenêtre de l'ARTEFACT D'OROGRAPHIE
#  0,025° — `(j0, i0)` et la forme `(61, 85)` viennent de lui, pas d'un
#  `fenetre()` rejoué ici. C'est délibéré : le sol qui porte la colonne
#  et la colonne elle-même doivent tomber sur les MÊMES points de grille
#  par construction, pas par coïncidence de deux calculs qui se
#  ressemblent. Le jour où l'un des deux dériverait, ils dériveraient
#  ensemble ou pas du tout.
#
#  ── LE FORMAT N'EST PAS UN ENGAGEMENT, ET C'EST LA DIFFÉRENCE ────────
#  Le format du produit A est une décision à long terme : ses archives
#  seront relues dans des années. Celui-ci ne survit pas à trois runs.
#  ⓘ Donc : UN objet par run, la grille entière. Le jour où le calque
#  altitude (étape 11) demandera de servir un niveau à la fois sans
#  tirer 32 Mo, on découpera — et on ne perdra rien, puisqu'il n'y aura
#  rien d'ancien à convertir. Décider aujourd'hui d'un découpage pour un
#  client qui n'existe pas encore serait payer une complexité maintenant
#  contre un besoin supposé.
#
#  ── DISPOSITION, ET POURQUOI CELLE-LÀ ────────────────────────────────
#      h0025 : (paramètre, niveau, échéance, lat, lon)   float16
#  Un niveau à une échéance est donc CONTIGU en mémoire : c'est
#  exactement la tranche que le calque altitude servira. L'ordre inverse
#  (lat, lon en tête) obligerait à lire tout le tableau pour en extraire
#  une carte.
#
#  ⚠️⚠️ LES AXES SONT PUBLIÉS, PAS DÉDUITS. `lats` DÉCROÎT (le premier
#  point est au NORD : `jScansPositively = 0` sur AROME) et `lons` croît.
#  Un consommateur qui supposerait des latitudes croissantes obtiendrait
#  une carte retournée — et une carte retournée sur un domaine presque
#  carré ne se voit PAS à l'œil : les Alpes ressembleraient toujours à
#  des Alpes. C'est le mode de panne silencieux de ce fichier, et c'est
#  pour ça que `lats` et `lons` sont dans l'archive plutôt que
#  reconstituables depuis un coin et un pas.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import json

import numpy as np

from colonnes import (PARAM_ALTITUDE, PARAM_PRESSION_SOL, PARAMS_0025,
                      PARAMS_ISO, PARAMS_SURFACE)
from domaine import (GRID_3D, NIVEAUX_H_0025, NIVEAUX_P,
                     RACCORD_BAS_M, RACCORD_HAUT_M)

# ⚠️ LE PRODUIT B N'A PAS SA PROPRE LISTE DE PARAMÈTRES, ET C'EST VOULU.
# Il sert les mêmes cinq champs que le produit A sur les mêmes 25
# niveaux, quantifiés de la même façon — kelvins → Celsius compris. Deux
# listes qui « doivent bouger ensemble » sont exactement ce que
# `domaine.py` existe pour empêcher : le projet a déjà payé ça avec
# `LEVELS`, dupliqué entre l'ingestion et le front.
PARAMS_GRILLE = PARAMS_0025

# Idem pour les isobares, qui arrivent avec l'étape 12 : mêmes cinq
# champs (u, v, t, r, **cc**) et même axe vertical `zp` que le produit A.
PARAMS_GRILLE_ISO = PARAMS_ISO

# ⛔ LA SURFACE, ELLE, N'EXISTE QUE DANS LE PRODUIT B — c'est la seule
# liste de ce fichier qui n'ait pas de jumelle dans le produit A, et
# c'est délibéré. Le produit A est une archive DÉFINITIVE dont le format
# engage pour des années ; le produit B ne survit pas à trois runs. Ces
# treize champs servent la ligne de surface d'UNE vue (`ProfileSurface`
# dans la coupe) : les graver dans l'archive perpétuelle pour ça serait
# payer un engagement contre un besoin d'écran.
PARAMS_GRILLE_SURF = PARAMS_SURFACE


# ══════════════════════════════════════════════════════════════════════
#  ⛔ LA DISPOSITION DU TAMPON D'ÉCHÉANCE — L'ARBITRAGE DE L'ÉTAPE 12
# ══════════════════════════════════════════════════════════════════════
#  L'ordre ci-dessous n'est pas esthétique : il DÉCIDE de ce que le
#  calque altitude paie à chaque requête. La disposition est
#  param-majeure, donc un paramètre est contigu ; un Range ne peut porter
#  que sur une plage CONTINUE. Tout ce dont le calque a besoin doit donc
#  se trouver EN TÊTE, d'un seul tenant.
#
#  Ce dont le calque a besoin, et rien d'autre :
#    · u et v sur les 25 niveaux hauteur   — la moitié basse du calque
#    · u et v sur les 14 niveaux isobares  — ce qui lève le plafond
#    · `ziso`, l'altitude de ces niveaux   — sans elle ils sont muets
#
#  Mesuré le 12/08 sur les 5 185 colonnes du domaine nord-alpes :
#
#      plafond du calque      aujourd'hui      avec les isobares
#      étendue                3 168 → 6 887 m  7 616 → 7 626 m
#      colonnes trouées à 4 000 m   36,3 %           0 %
#      colonnes trouées à 5 000 m   71,0 %           0 %
#      colonnes trouées à 7 000 m  100,0 %           0 %
#      Range du calque             506 Ko          1 073 Ko
#
#  ⚠️ Le Range du calque DOUBLE. C'est le prix mesuré du plafond
#  uniforme, il est écrit ici pour qu'il soit refusable plutôt que subi.
#
#  ⚠️⚠️ `ziso` EST EN float32 AU MILIEU D'UN TAMPON float16. Ce n'est pas
#  négociable (le float16 coûte 2 m sur cet axe, mesuré) et ça impose
#  deux choses : le manifeste publie le `dtype` de CHAQUE tranche, et le
#  décalage de la tranche float32 doit être multiple de 4 — sans quoi
#  `new Float32Array(buffer, offset, n)` lève côté navigateur.
#  `tranches()` le vérifie et refuse d'écrire sinon.
#
#  ⛔ RÉORDONNER CETTE LISTE FAIT SERVIR AUTRE CHOSE AU CLIENT SANS AUCUNE
#  ERREUR. C'est pour ça que `tranches()` est publié et que le banc
#  §8 côté web échoue si une liste est codée en dur.
#
#  Chaque entrée : (bloc, nom du paramètre).
#    "h"    → self.h0025, 25 niveaux hauteur, float16
#    "iso"  → self.iso,   14 niveaux isobares, float16
#    "ziso" → self.ziso,  14 niveaux isobares, float32
ORDRE_TAMPON = (
    ("h", "u"), ("h", "v"),              # ── le calque, moitié basse ──
    ("iso", "u"), ("iso", "v"),          # ── le calque, moitié haute ──
    ("ziso", "zp"),                      # ── l'axe de la moitié haute ──
    # ── à partir d'ici, ce que le calque ne lit JAMAIS ────────────────
    ("h", "t"), ("h", "r"), ("h", "tke"),
    ("iso", "t"), ("iso", "r"), ("iso", "cc"),
    # ── La surface (étape 12 bis) ─────────────────────────────────────
    # ⚠️ `psol` est le SECOND tableau float32 du produit, après `ziso`.
    # Il est ici en QUEUE et non collé à `ziso` : le calque ne lit ni
    # l'un ni l'autre de ces blocs, et les coller aurait allongé son
    # Range de 20,7 Ko pour rien. L'alignement sur 4 est vérifié par
    # `tranches()`, quelle que soit la position.
    ("psol", "psol"),
    ("surf", "t2m"), ("surf", "td2m"), ("surf", "rafale"),
    ("surf", "nuages_bas"), ("surf", "nuages_moyens"),
    ("surf", "nuages_hauts"), ("surf", "cape"), ("surf", "couche_limite"),
    ("surf", "rayonnement"), ("surf", "precipitation"),
    ("surf", "pression_mer"),
)

# Combien de runs restent en ligne. ⚠️ Ce n'est PAS un réglage de
# confort : à 32,4 Mo par run et 8 runs par jour, sans purge le palier
# gratuit de 10 Go serait mangé en ~39 jours. Trois runs, c'est ~97 Mo
# résidents — et de quoi comparer un run au précédent, ce qu'un seul ne
# permettrait pas.
RETENTION_RUNS = 3

# La clé FIXE de l'index. ⚠️ C'est la pièce maîtresse de la purge, et
# elle existe parce que `ListObjects` est hors de portée : `HeadObject`
# et `ListObjects` sont facturés Class A, et `storage.py::_R2.exists`
# lève plutôt que de les laisser passer. L'index tient donc lui-même la
# liste de ce qui est en ligne, en UN `GetObject` (Class B) par run —
# même principe que le manifeste servant d'état de reprise ailleurs
# dans le projet.
CLE_INDEX = "agrume/grille/index.json"


# ⚠️ 12/08 — LE DOMAINE ENTRE DANS LA CLÉ. Le produit B était strictement
# Nord-Alpes ; les Pyrénées y entrent avec l'étape 11. Deux domaines qui
# partageraient un préfixe se purgeraient mutuellement — la rétention est
# comptée PAR DOMAINE, donc le domaine doit être dans la clé.
def prefixe_run(run, domaine):
    return f"agrume/grille/{domaine}/{run}"


def cle_echeance(run, domaine, step):
    """⚠️ `{step:02d}` et pas `{step}` : l'index trie ses runs par ordre
    LEXICOGRAPHIQUE (voir `index_apres`). Une clé `e3` se rangerait entre
    `e29` et `e30`. Ici ça ne casse rien aujourd'hui — les clés ne sont
    pas triées — mais la même erreur a déjà coûté ailleurs, et deux
    chiffres ne coûtent rien."""
    return f"{prefixe_run(run, domaine)}/e{step:02d}.bin"


def cle_colonnes(run, domaine):
    """⛔ LE SECOND OBJET, ET LA DÉCISION DE L'ÉTAPE 12.

    Le tampon d'échéance est param-majeur : parfait pour une CARTE (un
    niveau, tous les points), inutilisable pour une COLONNE (un point,
    tous les niveaux, toutes les échéances) — qui y est stridée, donc
    hors de portée d'un Range.

    ⚠️ ET LE PROMPT DU LOT SE TROMPAIT D'UN FACTEUR 26 SUR CE POINT. Il
    chiffrait la coupe à « ~2,2 Mo par échéance ». Mais `VerticalProfile`
    (`web/src/types/openmeteo.ts`) n'est pas une échéance : c'est une
    SÉRIE sur `times`, chaque champ étant un tableau par heure. La coupe
    veut donc une colonne sur les 25 échéances. Mesuré le 12/08 sur le
    run en ligne, à travers le CDN :

        ce que la coupe doit lire     1 colonne × 25 échéances   10,9 Ko
        en param-majeur, elle tire    les 25 tampons entiers     57,8 Mo
                                      (93,7 Mo sur les Pyrénées)
        soit un facteur                                           5 185
        et, chronométré                32,4 Mo en 16,0 s à 2,0 Mo/s

    Trois voies ont été chiffrées et soumises à Yann le 12/08 ; il a
    retenu celle-ci :

        A  tampons entiers           57,8 Mo   25 req.    ~29 s
        B  UN objet « colonnes »     10,9 Ko    1 Range    0,25 s  ← ✅
           par RUN, disposé en colonnes
        C  un objet par échéance    446 o × 25  25 Ranges  1,4 s
        D  un Range par param×niveau  2 o × 70  1 750 req. refusé

    ⓘ Le prix de B, chiffré : il DUPLIQUE les 57,8 Mo du run (stationnaire
    455 → 910 Mo sur un palier de 10 Go, marge ×11) et ajoute UN objet par
    run et par domaine — 56 → 58, contre 106 pour la voie C.
    """
    return f"{prefixe_run(run, domaine)}/colonnes.bin"


def cles_du_run(run, domaine, steps):
    """Les clés d'un run : un tampon par échéance, plus le manifeste.

    ⛔ CE N'EST PLUS `grille.npz`, ET C'EST LA DÉCISION DE L'ÉTAPE 11.
    L'en-tête de ce fichier annonçait « le jour où le calque altitude
    demandera de servir un niveau à la fois sans tirer 32 Mo, on
    découpera ». Ce jour est venu, mais **pas sur l'axe prévu** : mesuré
    le 12/08, un calque à altitude-mer constante a besoin de 14 à 25 des
    25 niveaux (parce que `h = A − zsol` s'étale autant que `zsol`, soit
    3 720 m sur ce domaine). Découper par NIVEAU aurait fait 625 objets
    par run pour 14 à 25 requêtes par vue — plus cher ET plus lent.

    ✅ On découpe donc PAR ÉCHÉANCE : 25 objets, un objet = toute la pile
    verticale d'une échéance. Le client tire un objet et balaie ensuite
    TOUTE la plage d'altitudes sans une requête de plus.

    ⛔ ET LE FORMAT N'EST PLUS UN `.npz` : le navigateur ne sait pas le
    lire. C'est un tampon BRUT float16, disposition publiée dans le
    manifeste. Voir `tampon_echeance()` pour pourquoi il n'est pas
    compressé.

    ⛔ 12/08 — `colonnes.bin` ENTRE DANS CETTE LISTE, ET C'EST VITAL.
    C'est elle que `index_apres` recopie dans l'index, et l'index est la
    SEULE mémoire de ce qui est en ligne : `ListObjects` est hors de
    portée (Class A). Un objet écrit mais absent d'ici ne serait jamais
    purgé — définitivement payé, définitivement invisible. C'est
    l'inverse exact du défaut du 12/08 (« les clés de l'ancien format
    partent à la SUPPRESSION, pas à l'oubli ») et il coûte plus cher.
    """
    b = prefixe_run(run, domaine)
    return [cle_echeance(run, domaine, s) for s in steps] + [
        cle_colonnes(run, domaine), f"{b}/manifest.json"]


# ══════════════════════════════════════════════════════════════════════
#  Les axes — hérités de l'orographie, puis VÉRIFIÉS contre elle
# ══════════════════════════════════════════════════════════════════════
def axes_depuis_orographie(orog, domaine=None):
    """(lats, lons) de la fenêtre portée par l'artefact d'orographie.

    ⚠️⚠️ DEUX CONTRÔLES, ET UN SEUL DES DEUX PROUVE QUELQUE CHOSE.

    Le premier compare les axes recalculés ici à `orog.coords()` sur les
    quatre coins. ⓘ Il ne peut PAS détecter une fenêtre décalée : les
    deux formules partent des mêmes `(meta, j0, i0)`, donc elles se
    trompent ensemble ou pas du tout. Ce qu'il verrouille est plus
    étroit — que les deux conventions restent d'accord le jour où l'une
    des deux sera modifiée. C'est utile, et ce n'est pas ce qu'on croit
    en le lisant : d'où cette note. *(Constaté au banc, le 10/08 : écrit
    d'abord comme LE garde-fou, il laissait passer un décalage d'un
    point de grille sans broncher.)*

    Le second, lui, a une référence INDÉPENDANTE : les coins doivent
    tomber sur le `DOMAINE` déclaré, à un demi-pas près. Si `j0`/`i0`
    dérivaient, ou si Météo-France déplaçait le coin de grille, les
    latitudes cesseraient de coïncider avec 44,8–46,3 N — et c'est la
    seule chose ici qui ne vienne pas de l'artefact lui-même.

    ⚠️ Un point de grille vaut 2,8 km, et un décalage d'un point sur une
    orographie de montagne vaut des centaines de mètres d'altitude. Rien
    de tout cela ne se verrait sur une carte.
    """
    from domaine import DOMAINE
    dom = DOMAINE if domaine is None else domaine
    m = orog.meta
    nj, ni = orog.z.shape
    j = np.arange(nj, dtype=np.float64) + orog.j0
    i = np.arange(ni, dtype=np.float64) + orog.i0
    lats = (m["lat0"] + j * m["dj"] if m["jScan"] == 1
            else m["lat0"] - j * m["dj"])
    lons = m["lon0"] + i * m["di"]

    for (jj, ii) in ((0, 0), (0, ni - 1), (nj - 1, 0), (nj - 1, ni - 1)):
        lat_c, lon_c = orog.coords(jj, ii)
        if abs(lat_c - lats[jj]) > 1e-6 or abs(lon_c - lons[ii]) > 1e-6:
            raise ValueError(
                f"axes de la grille incohérents avec l'orographie au coin "
                f"({jj}, {ii}) : {lats[jj]:.4f}/{lons[ii]:.4f} contre "
                f"{lat_c:.4f}/{lon_c:.4f}. ⚠️ Ne PAS ignorer : la carte "
                f"serait décalée sans avoir l'air fausse.")

    # ── Le contrôle qui a une référence indépendante ──────────────────
    # `fenetre()` prend le point de grille le PLUS PROCHE de chaque
    # borne : l'écart admissible est donc un demi-pas. On serre à 0,6
    # pas — assez lâche pour le plus proche voisin, assez strict pour
    # qu'un décalage d'UN point (1,0 pas) soit refusé.
    #
    # ⚠️ On compare les EXTREMA, pas le premier et le dernier point : le
    # SENS de l'axe dépend de `jScansPositively`, son ÉTENDUE non. Écrire
    # « lats[0] doit valoir latmax » enfermerait ce contrôle dans une
    # convention de balayage — et le jour où elle changerait, le
    # garde-fou crierait au lieu de laisser passer, ce qui est le
    # mauvais sens de l'erreur.
    for valeur, attendu, pas, quoi in (
            (float(np.min(lats)), dom["latmin"], m["dj"], "latitude minimale"),
            (float(np.max(lats)), dom["latmax"], m["dj"], "latitude maximale"),
            (float(np.min(lons)), dom["lonmin"], m["di"], "longitude minimale"),
            (float(np.max(lons)), dom["lonmax"], m["di"], "longitude maximale")):
        if abs(float(valeur) - attendu) > 0.6 * pas:
            raise ValueError(
                f"la fenêtre de la grille ne tombe plus sur le domaine "
                f"déclaré : {quoi} = {float(valeur):.4f} au lieu de "
                f"{attendu} (écart {abs(float(valeur) - attendu) / pas:.2f} "
                f"point de grille). ⚠️ Un point vaut 2,8 km et des "
                f"centaines de mètres d'altitude en montagne — et rien "
                f"ne se verrait sur la carte. Régénérer l'artefact avec "
                f"`agrume/freeze_orographie.py`.")
    return lats.astype(np.float32), lons.astype(np.float32)


def decouper(values, meta, orog):
    """Champ France entière (plat) → fenêtre du domaine, en 2D (lat, lon).

    ⚠️ `values` arrive PLAT (`Ni × Nj` valeurs), pas en 2D : eccodes rend
    un tableau à une dimension. Le reshape se fait en (Nj, Ni) — dans cet
    ordre et pas l'autre — parce que le balayage du GRIB est par rangées
    de longitude. Inverser les deux donnerait un tableau de la bonne
    TAILLE et du mauvais contenu, ce qui ne lève aucune exception.
    """
    a = np.asarray(values)
    if a.size != meta["Ni"] * meta["Nj"]:
        raise ValueError(
            f"champ de {a.size} valeurs pour une grille "
            f"{meta['Ni']}×{meta['Nj']} = {meta['Ni'] * meta['Nj']}")
    nj, ni = orog.z.shape
    return a.reshape(meta["Nj"], meta["Ni"])[
        orog.j0:orog.j0 + nj, orog.i0:orog.i0 + ni]


# ══════════════════════════════════════════════════════════════════════
#  Le conteneur
# ══════════════════════════════════════════════════════════════════════
class Grille:
    """Un run, une grille 3D, trois runs de durée de vie.

        h0025 : (paramètre, niveau, échéance, lat, lon)  float16
                paramètres = PARAMS_GRILLE dans l'ordre
                niveaux    = NIVEAUX_H_0025 (25, de 10 à 3000 m/sol)
        zsol  : (lat, lon)                               float32
        lats  : (lat,)   float32, DÉCROISSANT (nord → sud)
        lons  : (lon,)   float32, croissant (ouest → est)

    ⚠️ Les niveaux sont AGL — au-dessus du sol DU MODÈLE, qui est `zsol`
    et qui varie d'un point à l'autre de plusieurs milliers de mètres sur
    ce domaine. `altitude_ASL = zsol[j, i] + niveau`. Une coupe
    horizontale « à 2 000 m » n'est donc PAS un niveau du tableau : c'est
    une interpolation entre deux niveaux, différente en chaque point.
    C'est le travail du calque altitude (étape 11), pas celui-ci.

    ⓘ `zsol` est embarqué (21 Ko) alors qu'il est déjà dans l'artefact
    commité. La redondance est assumée : sans lui, l'archive ne se
    suffit pas à elle-même, et un consommateur devrait aller chercher le
    bon artefact au bon sha pour savoir à quelle altitude sont ses
    valeurs. 21 Ko contre une ambiguïté verticale de 3 700 m.
    """

    def __init__(self, run, steps, lats, lons, zsol, domaine="nord-alpes"):
        self.run = run
        # ⚠️ Défaut `nord-alpes` : ce paramètre arrive le 12/08 avec le
        # second domaine, et quatre bancs plus trois CLI construisent
        # déjà des `Grille` sans lui. Un argument obligatoire les aurait
        # tous cassés d'un coup pour un renseignement que le manifeste
        # portait déjà implicitement.
        self.domaine = domaine
        self.steps = list(steps)
        self.lats = np.asarray(lats, dtype=np.float32)
        self.lons = np.asarray(lons, dtype=np.float32)
        self.zsol = np.asarray(zsol, dtype=np.float32)
        nj, ni = len(self.lats), len(self.lons)
        if self.zsol.shape != (nj, ni):
            raise ValueError(f"zsol {self.zsol.shape} ≠ axes ({nj}, {ni})")
        self.h0025 = np.full(
            (len(PARAMS_GRILLE), len(NIVEAUX_H_0025), len(self.steps), nj, ni),
            np.nan, dtype=np.float16)
        # ── Étape 12 : les isobares, sur leur propre verticale ─────────
        # ⚠️ UN SECOND TABLEAU, PAS 14 NIVEAUX DE PLUS DANS LE PREMIER.
        # Les deux verticales ne sont pas commensurables : « 500 m/sol »
        # est une constante au-dessus d'un sol qui varie de 3 720 m sur ce
        # domaine, « 500 hPa » est une surface dont l'altitude est une
        # VARIABLE. Les empiler dans un même axe donnerait un tableau que
        # personne ne pourrait indexer sans savoir de quelle moitié il
        # parle. C'est `ziso` qui les réconcilie, et lui seul.
        self.iso = np.full(
            (len(PARAMS_GRILLE_ISO), len(NIVEAUX_P), len(self.steps), nj, ni),
            np.nan, dtype=np.float16)
        # ⛔⛔ float32, ET JAMAIS float16. Mesuré (`test_colonnes.py`) :
        # entre 4 096 et 8 192 m le pas du float16 vaut 4 m, donc 2,00 m
        # d'erreur, contre 0,24 mm en float32 — un rapport de 8 192. Et
        # c'est l'axe SUR LEQUEL on raccorde deux sources. Ici le coût est
        # 284 Ko par échéance et par domaine, pas 175 Ko par run : c'est
        # le poste le plus cher du lot après les isobares elles-mêmes, et
        # il reste non négociable. `test_grille.py` échoue si ce dtype
        # change.
        self.ziso = np.full(
            (len(NIVEAUX_P), len(self.steps), nj, ni),
            np.nan, dtype=np.float32)
        # ── Étape 12 bis : la surface ─────────────────────────────────
        # ⚠️ Pas d'axe « niveau » : un champ de surface est un plan par
        # échéance. Le distinguer des trois autres blocs plutôt que de
        # lui inventer un niveau unique évite qu'un lecteur croie pouvoir
        # l'interpoler verticalement.
        self.surf = np.full(
            (len(PARAMS_GRILLE_SURF), len(self.steps), nj, ni),
            np.nan, dtype=np.float16)
        # ⛔ float32, comme `ziso`, et pour la même raison MESURÉE : c'est
        # l'ancre basse de la pression dérivée, et le float16 y coûterait
        # 0,125 à 0,25 hPa — soit 1 à 2 m — contre 0,016 hPa pour la
        # dérivation qu'elle ancre. Voir `PARAM_PRESSION_SOL`.
        self.psol = np.full(
            (len(self.steps), nj, ni), np.nan, dtype=np.float32)
        # ⛔ Garde-fou de la dé-accumulation : `tp` et `ssrd` arrivent
        # CUMULÉS depuis le début du run. Les différencier deux fois
        # donnerait des valeurs négatives un pas sur deux — pas une
        # erreur, un résultat.
        self._deaccumule = False
        self.i_param = {p["nom"]: k for k, p in enumerate(PARAMS_GRILLE)}
        self.i_niveau = {n: k for k, n in enumerate(NIVEAUX_H_0025)}
        self.i_param_iso = {p["nom"]: k
                            for k, p in enumerate(PARAMS_GRILLE_ISO)}
        self.i_param_surf = {p["nom"]: k
                             for k, p in enumerate(PARAMS_GRILLE_SURF)}
        self.i_niveau_p = {n: k for k, n in enumerate(NIVEAUX_P)}
        self.i_step = {s: k for k, s in enumerate(self.steps)}

    # ── La surface ────────────────────────────────────────────────────
    def accepte_surface(self, param_nom, step):
        return ((param_nom in self.i_param_surf
                 or param_nom == PARAM_PRESSION_SOL["nom"])
                and step in self.i_step)

    def poser_surface(self, param_nom, step, champ2d):
        """⚠️ `psol` va dans son propre tableau float32 — même règle que
        `zp` pour `ziso`, et pour la même raison mesurée."""
        if param_nom == PARAM_PRESSION_SOL["nom"]:
            self.psol[self.i_step[step]] = champ2d
        else:
            self.surf[self.i_param_surf[param_nom], self.i_step[step]] = champ2d

    def deaccumuler(self):
        """⛔⛔ CUMULS → VALEURS HORAIRES. À APPELER UNE FOIS, À LA FIN.

        `tp` (pluie) et `ssrd` (rayonnement) arrivent **cumulés depuis le
        début du run** — `stepRange` 0-1, 0-2, 0-3… et non 0-1, 1-2, 2-3.
        Mesuré le 13/08 sur le run 15 Z. Servis tels quels :

          · `tp` donnerait une pluie horaire QUI NE DÉCROÎT JAMAIS. Une
            courbe lisse, croissante, et fausse — le mode de panne que ce
            projet passe son temps à éviter.
          · `ssrd` donnerait 865 W/m² à 19 h TU un 12 août, après
            division par 3 600. Plausible à midi, absurde le soir, et
            rien pour le dire.

        ⚠️ POURQUOI ICI ET PAS AU FIL DES MESSAGES. Différencier pendant
        l'ingestion supposerait que l'échéance k−1 soit déjà arrivée
        quand k se pose. Elle l'est souvent — les bundles sont de 6 h et
        ordonnés — mais « souvent » n'est pas une garantie, et l'erreur
        serait silencieuse : une échéance différenciée contre un tableau
        encore NaN sortirait NaN, ce qui ressemble à un trou d'ingestion.

        ⚠️ L'ÉCHÉANCE 0 DEVIENT NaN, et c'est correct : un cumul sur zéro
        heure n'est pas une valeur horaire. Le modèle ne publie d'ailleurs
        pas ces champs à τ = 0 (mesuré) — la règle et la donnée sont
        d'accord.

        ⛔ Et elle refuse d'être rejouée : différencier deux fois donne
        des valeurs négatives un pas sur deux. Pas une erreur, un
        résultat — exactement comme diviser deux fois par `G`.
        """
        if self._deaccumule:
            raise RuntimeError(
                "`deaccumuler()` a déjà été appelé sur cette grille. ⛔ Le "
                "rejouer différencierait des différences : la pluie et le "
                "rayonnement sortiraient NÉGATIFS un pas sur deux, sans "
                "aucune exception pour le dire.")
        self._deaccumule = True
        for k, p in enumerate(PARAMS_GRILLE_SURF):
            if p.get("pas_de_temps") != "cumul":
                continue
            a = self.surf[k].astype(np.float32)
            # ⚠️ L'échéance 0 sort à NaN — pas à zéro. Un cumul sur zéro
            # heure n'est pas « il n'a pas plu », c'est « il n'y a pas
            # d'heure ». Le modèle ne publie d'ailleurs pas ces champs à
            # τ = 0 (mesuré) : la règle et la donnée sont d'accord.
            horaire = np.full_like(a, np.nan)
            horaire[1:] = a[1:] - a[:-1]
            # ⚠️⚠️ ET LA PREMIÈRE ÉCHÉANCE UTILE VAUT LE CUMUL LUI-MÊME,
            # PAS NaN. Le banc a démenti la première version, qui
            # différenciait bêtement : à τ = 1 elle faisait
            # `cumul(1) − cumul(0)`, or `cumul(0)` est NaN puisque le
            # modèle ne le publie pas — et la PREMIÈRE HEURE DE PLUIE DU
            # RUN disparaissait. Silencieusement, et seulement elle.
            # Le cumul à τ = 0 vaut ZÉRO par définition : zéro heure
            # écoulée. C'est la seule valeur qu'on ait le droit de
            # supposer ici, et encore : seulement si le run commence
            # bien à l'échéance 0.
            if self.steps and self.steps[0] == 0 and len(self.steps) > 1:
                horaire[1] = a[1]
            elif self.steps:
                # ⛔ Run partiel (première échéance > 0) : on ne sait pas
                # ce qui s'est accumulé avant, donc la première échéance
                # reste NaN. Y mettre le cumul afficherait plusieurs
                # heures de pluie comme UNE heure.
                horaire[0] = np.nan
            # ⚠️ Un cumul ne peut pas décroître. S'il décroît, c'est que
            # le run a été mélangé (deux runs dans le même tableau) ou
            # qu'une échéance manque : on rend NaN plutôt qu'une pluie
            # négative, qui s'afficherait comme un nombre.
            horaire = np.where(horaire < 0.0, np.nan, horaire)
            self.surf[k] = horaire.astype(np.float16)
        return self

    def accepte(self, param_nom, niveau, step):
        """Le champ a-t-il sa place ici ? Le produit A retient des
        niveaux et des paramètres que celui-ci ne porte pas (maille fine,
        isobares) : on filtre plutôt que de lever, sinon le branchement
        dans l'ingestion devrait connaître les deux périmètres."""
        return (param_nom in self.i_param and niveau in self.i_niveau
                and step in self.i_step)

    def accepte_isobare(self, param_nom, niveau, step):
        """Le pendant isobare d'`accepte()`.

        ⚠️ `niveau` est ici une PRESSION en hPa, pas une hauteur en
        mètres — et les deux jeux se recouvrent : 1000 est un niveau
        isobare valide ET une hauteur-sol valide, 750 et 500 aussi. Deux
        dictionnaires séparés (`i_niveau` et `i_niveau_p`) plutôt qu'un
        seul, sinon un champ isobare à 500 hPa irait se poser au niveau
        « 500 m/sol » sans que rien ne lève.

        ⚠️ `zp` doit être accepté ALORS QU'IL N'EST PAS DANS
        `PARAMS_GRILLE_ISO` : c'est un paramètre fictif, il ne vit pas
        dans `iso` mais dans `ziso`. L'oublier ici laisserait `ziso`
        entièrement NaN — donc des niveaux isobares sans altitude, donc
        muets, donc un plafond inchangé, et tout ça sans une erreur.
        """
        return ((param_nom in self.i_param_iso
                 or param_nom == PARAM_ALTITUDE["nom"])
                and niveau in self.i_niveau_p and step in self.i_step)

    def poser(self, param_nom, niveau, step, champ2d):
        self.h0025[self.i_param[param_nom], self.i_niveau[niveau],
                   self.i_step[step]] = champ2d

    def poser_isobare(self, param_nom, niveau, step, champ2d):
        """⚠️ `zp` va dans `ziso` (float32) et NULLE PART ailleurs — même
        règle que `Colonnes.poser_isobare`, pour la même raison."""
        if param_nom == PARAM_ALTITUDE["nom"]:
            self.ziso[self.i_niveau_p[niveau], self.i_step[step]] = champ2d
        else:
            self.iso[self.i_param_iso[param_nom], self.i_niveau_p[niveau],
                     self.i_step[step]] = champ2d

    # ── Complétude ────────────────────────────────────────────────────
    def remplissage_par_parametre(self):
        """⚠️ Par paramètre, comme le produit A, et pour la même raison
        mesurée : la TKE n'existe PAS à l'échéance 0. Un remplissage
        global de 96 % ne dit pas s'il manque un champ par construction
        ou si un run est tronqué."""
        def part(a):
            return round(float(np.isfinite(a.astype(np.float32)).mean()), 4)
        out = {p["nom"]: part(self.h0025[k])
               for k, p in enumerate(PARAMS_GRILLE)}
        # ⚠️ Préfixe `iso_` : `u` hauteur et `u` isobare sont deux champs
        # différents, et un dictionnaire à clé `u` en aurait écrasé un.
        for k, p in enumerate(PARAMS_GRILLE_ISO):
            out[f"iso_{p['nom']}"] = part(self.iso[k])
        out["ziso"] = part(self.ziso)
        for k, p in enumerate(PARAMS_GRILLE_SURF):
            out[p["nom"]] = part(self.surf[k])
        out["psol"] = part(self.psol)
        return out

    def remplissage(self):
        """Part de cases renseignées, TOUS blocs confondus et pondérée
        par leur taille — pas une moyenne des trois pourcentages, qui
        donnerait le même poids aux 3,2 M de cases hauteur et aux 1,8 M
        de cases isobares."""
        blocs = (self.h0025, self.iso, self.ziso, self.surf, self.psol)
        pleines = sum(int(np.isfinite(a.astype(np.float32)).sum())
                      for a in blocs)
        total = sum(a.size for a in blocs)
        return round(pleines / total, 4)

    def octets(self):
        return int(self.h0025.nbytes + self.iso.nbytes + self.ziso.nbytes
                   + self.surf.nbytes + self.psol.nbytes
                   + self.zsol.nbytes + self.lats.nbytes + self.lons.nbytes)

    # ── Sérialisation ─────────────────────────────────────────────────
    def manifeste(self, extra=None):
        from domaine import DOMAINES
        m = dict(
            produit=f"AGRUME produit B — grille 3D du domaine {self.domaine}",
            run=self.run,
            domaine=self.domaine,
            bornes=DOMAINES.get(self.domaine),
            echeances=self.steps,
            grille=GRID_3D,
            # ══ CE QUE LE CLIENT DOIT LIRE POUR SERVIR LE CALQUE ══════
            # ⚠️ Tout ce bloc existe pour qu'AUCUNE de ces valeurs ne
            # soit recopiée côté client. Le projet a déjà payé `LEVELS`
            # dupliqué entre `arome-wind/ingest.py` et
            # `web/src/lib/config.ts` : « les deux listes doivent bouger
            # ensemble, sinon le sélecteur d'altitude propose des paliers
            # dont les tuiles n'existent plus (404 silencieux, calque
            # vide) ». Un banc côté web échoue si une liste est en dur.
            service=dict(
                cle_echeance="agrume/grille/{domaine}/{run}/e{step:02d}.bin",
                cle_zsol="agrume/grille/{domaine}/{run}/zsol.bin",
                cle_colonnes="agrume/grille/{domaine}/{run}/colonnes.bin",
                disposition_tampon=("(tranche, niveau, lat, lon) "
                                    "little-endian, C-contigu, SANS en-tête ; "
                                    "le dtype est PROPRE À CHAQUE TRANCHE — "
                                    "float16 partout sauf `ziso`, en float32"),
                encodage="aucun — l'objet est BRUT pour rester Range-able",
                tranches=self.tranches(),
                octets_par_echeance=self.octets_par_echeance(),
                # ── L'AUTRE DISPOSITION, pour la vue de coupe ──────────
                # ⚠️ Publiée avec la même exigence que `tranches` : rien
                # ici ne doit être recalculé côté client. L'offset d'une
                # colonne (j, i) vaut `(j * nb_lon + i) * octets_par_colonne`,
                # et ce pas est ALIGNÉ SUR 4 par construction.
                colonnes=dict(
                    disposition=("un enregistrement par colonne, dans "
                                 "l'ordre (lat, lon) — donc du NORD au sud "
                                 "puis d'ouest en est, comme zsol"),
                    octets_par_colonne=self.octets_par_colonne(),
                    offset=("(j * nb_lon + i) * octets_par_colonne, où j "
                            "indexe `lats` (DÉCROISSANT) et i `lons`"),
                    tranches=self.tranches_colonne(),
                    note=("un Range de `octets_par_colonne` suffit à toute "
                          "la colonne, tous paramètres, tous niveaux, "
                          "TOUTES ÉCHÉANCES. Mesuré le 12/08 : 10,9 Ko et "
                          "0,25 s, contre 57,8 Mo et 16 s en lisant les 25 "
                          "tampons d'échéance.")),
                note=("`tranches` donne l'offset, la longueur ET LE DTYPE de "
                      "chaque tranche : un calque de vent ne demande que "
                      "`bytes=0-<fin de ziso>`, une coupe ne lit que "
                      "`colonnes.bin`. NE PAS recopier l'ordre des tranches "
                      "ni la liste des niveaux côté client — les lire ICI. "
                      "⚠️ `ziso` est en float32 : un client qui supposerait "
                      "float16 partout lirait l'axe vertical comme deux fois "
                      "plus de valeurs, toutes fausses et toutes finies.")),
            niveaux_m_sol=list(NIVEAUX_H_0025),
            niveaux_hpa=list(NIVEAUX_P),
            # ⛔ LE RACCORD EST PUBLIÉ (étape 13, 13/08), et ce n'est pas
            # de la documentation. Depuis que le calque MÉLANGE les deux
            # verticales entre `bas_m` et `haut_m` — comme `profil.py`,
            # décision de Yann — ces deux bornes décident d'une VALEUR
            # servie, pas d'un affichage. Les recopier côté client aurait
            # fait deux vérités pour un seul raccord ; le jour où l'une
            # bouge, la carte et la coupe divergeraient à nouveau, en
            # silence, ce que cette étape existe précisément pour éliminer.
            raccord=dict(
                bas_m=RACCORD_BAS_M, haut_m=RACCORD_HAUT_M,
                note=("poids de la source HAUTEUR : 1 sous `bas_m`, 0 "
                      "au-dessus de `haut_m`, rampe linéaire entre les "
                      "deux. valeur = w·hauteur + (1-w)·isobare, dans "
                      "CET ordre — l'ordre des termes n'est pas neutre en "
                      "virgule flottante et le banc de parité exige "
                      "l'écart NUL.")),
            parametres=[dict(nom=p["nom"], unite=p["unite"],
                             paquet=p["paquet"]) for p in PARAMS_GRILLE],
            parametres_isobares=[
                dict(nom=p["nom"], unite=p["unite"], paquet=p["paquet"],
                     absent_a_tau0=bool(p.get("absent_a_tau0")))
                for p in PARAMS_GRILLE_ISO],
            # ── La surface (étape 12 bis) ─────────────────────────────
            # ⚠️ `pas_de_temps` est PUBLIÉ, et ce n'est pas de la
            # documentation : `instant`, `max_horaire` et `cumul` ne se
            # lisent pas pareil, et `cumul` a déjà été ramené à l'heure
            # par `deaccumuler()` — un client qui redifférencierait
            # obtiendrait des valeurs négatives un pas sur deux.
            # ⛔ `decalage_precision` EST PUBLIÉ, et ce n'est pas de la
            # documentation non plus. `prmsl` est archivé en `hPa − 1000`
            # pour gagner de la précision float16 (0,125 au lieu de 0,25) ;
            # l'unité publiée, elle, reste « hPa ». Sans ce champ, un
            # client qui suit le manifeste affiche −13 hPa au lieu de 987.
            # `valeur_publiée = valeur_archivée − decalage_precision`.
            # ⚠️ À ne PAS confondre avec le décalage d'UNITÉ (K → °C),
            # qui est déjà fait et ne se défait pas : après lui l'archive
            # EST dans l'unité publiée.
            parametres_surface=[
                dict(nom=p["nom"], unite=p["unite"], paquet=p["paquet"],
                     pas_de_temps=p.get("pas_de_temps", "instant"),
                     absent_a_tau0=bool(p.get("absent_a_tau0")),
                     decalage_precision=float(p.get("decalage_precision", 0.0)))
                for p in PARAMS_GRILLE_SURF]
            + [dict(nom=PARAM_PRESSION_SOL["nom"],
                    unite=PARAM_PRESSION_SOL["unite"],
                    paquet=PARAM_PRESSION_SOL["paquet"],
                    pas_de_temps="instant", absent_a_tau0=False,
                    decalage_precision=float(
                        PARAM_PRESSION_SOL.get("decalage_precision", 0.0)),
                    note=("ancre BASSE de la pression dérivée des niveaux "
                          "hauteur ; en float32 pour la même raison que "
                          "`ziso`, et SANS décalage de précision — le "
                          "float32 n'en a pas besoin"))],
            disposition=("h0025 = (parametre, niveau, echeance, lat, lon) en "
                         "float16 ; iso = (parametre, niveau_hPa, echeance, "
                         "lat, lon) en float16 ; ziso = (niveau_hPa, echeance, "
                         "lat, lon) en float32 ; zsol = (lat, lon) en float32 ; "
                         "lats et lons sont dans l'archive"),
            axes=dict(
                nb_lat=len(self.lats), nb_lon=len(self.lons),
                lat_premier=round(float(self.lats[0]), 4),
                lat_dernier=round(float(self.lats[-1]), 4),
                lon_premier=round(float(self.lons[0]), 4),
                lon_dernier=round(float(self.lons[-1]), 4),
                # ⚠️ Écrit en toutes lettres : c'est LE piège de ce
                # produit. Une carte retournée nord-sud sur un domaine
                # presque carré ne se voit pas à l'œil.
                sens=("lats DÉCROISSANTES (premier point au NORD, "
                      "jScansPositively = 0 sur AROME) ; lons croissantes")),
            reference_verticale=(
                "DEUX verticales, et elles ne sont pas commensurables. "
                "(1) niveaux HAUTEUR, AGL au-dessus du sol MODÈLE : "
                "altitude_ASL = zsol[lat, lon] + niveau. (2) niveaux "
                "ISOBARES, absolus mais d'altitude VARIABLE : elle est "
                "dans `ziso` (m, float32), et change d'un point à l'autre "
                "comme d'une heure à l'autre. Une coupe horizontale à "
                "altitude-mer constante n'est PAS un niveau du tableau : "
                "elle s'interpole entre deux niveaux, différemment en "
                "chaque point."),
            # ── Ce que les isobares changent, MESURÉ sur ce domaine ────
            plafond=dict(
                note=("altitude la plus haute que porte chaque colonne. "
                      "Mesuré le 12/08 sur les 5 185 colonnes du domaine "
                      "nord-alpes, run 15 Z, échéance +3 h."),
                sans_isobares_m=[3168, 6887],
                avec_isobares_m=[7616, 7626],
                colonnes_trouees_pourcent={
                    "3500": [14.8, 0.0], "4000": [36.3, 0.0],
                    "5000": [71.0, 0.0], "7000": [100.0, 0.0]},
                coupure=("400 hPa, choisi le 10/08 : ce n'est PAS « le max », "
                         "c'est la coupure qui couvre z_sol + 3000 m pour "
                         "toutes les balises du domaine.")),
            retention_runs=RETENTION_RUNS,
            remplissage=self.remplissage(),
            remplissage_par_parametre=self.remplissage_par_parametre(),
            avertissement=(
                "Produit JETABLE : seuls les {n} derniers runs sont en "
                "ligne, l'index `{i}` fait foi. Ne rien bâtir dessus qui "
                "suppose un historique. La TKE n'existe PAS à l'échéance 0 "
                "(mesuré le 10/08) : un remplissage < 100 % sur elle seule "
                "est normal. ⛔ LA NÉBULOSITÉ `cc` N'EXISTE PAS NON PLUS À "
                "L'ÉCHÉANCE 0 (mesuré le 12/08 sur deux runs) : le modèle y "
                "publie un champ CONSTANT à zéro, ce qui n'est pas une "
                "absence mais un « ciel clair » faux. Elle est donc archivée "
                "à NaN à τ=0, et un consommateur DOIT distinguer « pas de "
                "nuages » de « pas de donnée » — les servir pareil est le "
                "défaut que ce produit existe pour éviter. ⛔ LES NIVEAUX "
                "ISOBARES SOUS LE SOL sont archivés et doivent être MASQUÉS "
                "À LA LECTURE (ziso < zsol) : le modèle y met des valeurs "
                "extrapolées parfaitement crédibles ; mesuré sur ce domaine, "
                "1 à 9 niveaux sur 14 par colonne, 4 en médiane. Les points "
                "dont zsol dépasse l'altitude demandée doivent être MASQUÉS à "
                "l'affichage — ce masque dessine le relief tel que le modèle "
                "le voit, c'est une information, pas un défaut.").format(
                    n=RETENTION_RUNS, i=CLE_INDEX))
        if extra:
            m.update(extra)
        return m

    def ecrire_npz(self, chemin):
        """L'archive LOCALE, inchangée depuis l'étape 6.

        ⓘ Elle n'est plus ce qui monte sur R2 (voir `tampon_echeance`),
        mais elle reste ce que `--sortie` dépose et ce que les CLI de
        lecture (`couper.py`, `composite.py`, `front_altitude.py`,
        `test_calque.py --archive`) savent relire. La supprimer aurait
        cassé quatre outils pour un gain nul : ce fichier ne coûte rien,
        il ne quitte pas le runner.
        """
        np.savez_compressed(chemin, h0025=self.h0025, iso=self.iso,
                            ziso=self.ziso, surf=self.surf, psol=self.psol,
                            zsol=self.zsol,
                            lats=self.lats, lons=self.lons,
                            echeances=np.asarray(self.steps, dtype=np.int16))

    # ── CE QUI MONTE SUR R2 : un tampon brut par échéance ─────────────
    def tampon_echeance(self, step):
        """Les octets servis pour une échéance : `(tranche, niveau, lat,
        lon)`, C-contigu, SANS en-tête, dans l'ordre d'`ORDRE_TAMPON`.

        ⛔ PAS DE `.npz` : le navigateur ne sait pas le lire. Pas de
        JSON non plus — 5 185 × 25 × 5 nombres en texte feraient plus de
        10 Mo là où le binaire en fait 1,3.

        ⚠️⚠️ ET IL N'EST PAS COMPRESSÉ, DÉLIBÉRÉMENT. Mesuré le 12/08,
        avant les isobares :

            objet gzippé, tiré en entier       1 045 Ko
            objet BRUT + Range sur u/v           518 Ko   ← retenu
            objet brut tiré en entier          1 296 Ko

        `Content-Encoding: gzip` et `Range` ne se combinent pas — un
        Range porte sur les octets ENCODÉS. En laissant l'objet brut, le
        calque ne demande que la TÊTE du tampon, où `ORDRE_TAMPON` a
        rangé tout ce qu'il lit et rien d'autre. ✅ Vérifié à travers le
        CDN : `HTTP 206`, `content-range` exact, `accept-ranges: bytes`.

        ⛔ LA COUPE ET LE PROFIL NE TIRENT PLUS TOUT — c'était vrai
        jusqu'au 11/08 et ça ne l'est plus : ils lisent `colonnes.bin`.
        Voir `cle_colonnes()` pour le chiffrage qui a démonté l'idée.

        ⚠️ CE QUE ÇA IMPOSE À QUI TOUCHERA `ORDRE_TAMPON` : réordonner
        les tranches, ou en insérer une avant `ziso`, ferait servir autre
        chose au client SANS AUCUNE ERREUR. Le manifeste publie donc
        l'offset, la longueur ET LE DTYPE de chaque tranche (`tranches`),
        et le client DOIT les lire. Un banc côté web échoue si une liste
        est codée en dur.

        ⓘ float16 conservé tel quel : requantifier en int16 aurait rendu
        le critère d'acceptation du lot (« le niveau BRUT à l'octet
        près ») invérifiable, puisqu'on aurait comparé à une valeur
        requantifiée. Le décodage float16 → float32 en JavaScript tient
        en dix lignes et il est exact.

        ⚠️⚠️ 12/08 — LE TAMPON N'EST PLUS HOMOGÈNE. Il concatène les
        tranches dans l'ordre d'`ORDRE_TAMPON`, dont l'une (`ziso`) est
        en float32. L'ordre place en tête, d'un seul tenant, tout ce que
        le calque lit : `u`, `v` hauteur puis `u`, `v` isobares puis
        `ziso`. Mesuré sur le domaine nord-alpes : le Range du calque
        passe de 506 Ko à 1 073 Ko, et son plafond de « 3 168 à 6 887 m
        selon le point » à « 7 616 à 7 626 m ».
        """
        k = self.i_step[step]
        plan, total = self._plan()
        tampon = bytearray(total)          # ⚠️ les octets de remplissage
        for _cle, _bloc, src, _nlev, dt, offset, octets in plan:
            tampon[offset:offset + octets] = np.ascontiguousarray(
                src[:, k], dtype=dt).tobytes()
        return bytes(tampon)

    # ── L'AUTRE DISPOSITION : un objet par run, en colonnes ────────────
    def _plan_colonne(self):
        """La disposition d'UN enregistrement de `colonnes.bin`.

        ⚠️ LES BLOCS float32 D'ABORD, PUIS LES float16. Ce n'est pas un
        goût de rangement : c'est ce qui rend l'alignement vrai par
        CONSTRUCTION plutôt que par arithmétique heureuse. Un
        enregistrement commence à un multiple de 4 (le pas l'est) ; si
        ses float32 sont en tête, leurs décalages le sont aussi, quel que
        soit le nombre de niveaux, d'échéances ou de colonnes.

        ⓘ La leçon vient du tampon d'échéance, où l'alignement dépendait
        du nombre de colonnes et tombait juste par hasard sur le domaine
        réel — jusqu'à ce qu'un banc en 5 × 7 le démente.
        """
        nech = len(self.steps)
        blocs = self._blocs()
        ordre = ([b for b in blocs if b[4] is np.float32]
                 + [b for b in blocs if b[4] is not np.float32])
        plan, offset = [], 0
        for bloc, nom, src, nlev, dt, _octets in ordre:
            octets = nlev * nech * np.dtype(dt).itemsize
            plan.append((self._cle_tranche(bloc, nom), bloc, src, nlev, dt,
                         offset, octets))
            offset += octets
        return plan, offset + (-offset % 4)

    def octets_par_colonne(self):
        """Taille d'un enregistrement de `tampon_colonnes()`, alignée sur 4.

        ⛔ L'ALIGNEMENT N'EST PAS COSMÉTIQUE. Sans remplissage, le pas
        peut tomber sur un multiple de 2 mais pas de 4 — et une colonne
        sur deux verrait alors son bloc float32 commencer à un décalage
        impair-en-mots. `new Float32Array(buffer, offset, n)` LÈVERAIT,
        pour la moitié des points de la carte, et seulement pour eux.
        Quelques octets de remplissage par colonne coûtent une dizaine de
        kilo-octets sur les 5 185 colonnes du domaine.
        """
        return self._plan_colonne()[1]

    def tampon_colonnes(self):
        """UN objet par run : la même donnée, disposée EN COLONNES.

        ⛔ C'est la voie B de l'arbitrage du 12/08 (voir `cle_colonnes`).
        Elle duplique 57,8 Mo par run et par domaine pour que la vue de
        coupe tire 10,9 Ko au lieu de 57,8 Mo. Ce n'est pas un cache :
        c'est la MÊME donnée sur l'axe orthogonal, parce qu'aucune
        disposition unique ne sert à la fois une carte et une colonne.

        Disposition, publiée dans le manifeste et à ne jamais déduire :

            pour chaque colonne, dans l'ordre (lat, lon) — donc du NORD
            au sud puis d'ouest en est, comme `zsol` :
              · `ziso`  : 14 niveaux × 25 échéances, float32   (EN TÊTE)
              · puis, dans l'ordre d'`ORDRE_TAMPON` privé de `ziso`,
                chaque tranche : niveaux × échéances, float16
              · puis 0 à 3 octets de remplissage

        ⚠️ `ziso` EST EN TÊTE DE L'ENREGISTREMENT, ET C'EST CE QUI REND
        L'ALIGNEMENT POSSIBLE. Placé après les float16, son décalage
        dépendrait du nombre de niveaux float16 qui le précèdent — donc
        d'`ORDRE_TAMPON`, donc d'une décision sans rapport. En tête, il
        commence au début de l'enregistrement, et il suffit que le PAS
        soit multiple de 4.

        ⚠️ Les échéances sont l'axe le PLUS INTERNE : la coupe lit une
        série temporelle par (paramètre, niveau), c'est la lecture qu'on
        veut contiguë. L'inverse obligerait à sauter 25 fois par courbe.
        """
        nech = len(self.steps)
        nj, ni = len(self.lats), len(self.lons)
        plan, pas = self._plan_colonne()
        tampon = np.zeros((nj * ni, pas), dtype=np.uint8)
        for _cle, _bloc, src, nlev, dt, offset, octets in plan:
            # (niveau, échéance, lat, lon) → (colonne, niveau × échéance)
            a = np.ascontiguousarray(
                np.moveaxis(src.reshape(nlev, nech, nj * ni), 2, 0), dtype=dt)
            tampon[:, offset:offset + octets] = a.reshape(nj * ni, -1).view(np.uint8)
        return tampon.tobytes()

    def tampon_zsol(self):
        """`zsol` en float32 brut, 21 Ko. Servi une fois par run.

        ⚠️ Sans lui, le client ne peut RIEN faire du tampon d'échéance :
        les niveaux sont AGL, donc `altitude = zsol + niveau`. C'est la
        même redondance assumée que dans le npz, et pour la même raison.
        """
        return np.ascontiguousarray(self.zsol, dtype=np.float32).tobytes()

    def octets_par_echeance(self):
        """Taille d'un tampon d'échéance, calculée et non mesurée sur les
        octets produits — `tampon_echeance()` les construit, et le
        chiffrage doit pouvoir tourner AVANT la première écriture sans
        payer 25 concaténations par domaine."""
        return self._plan()[1]

    def octets_publies(self):
        """Ce que ce domaine met VRAIMENT sur R2 pour un run.

        ⚠️ Ce n'est pas `octets()`. `octets()` compte les tableaux en
        mémoire ; ici on compte les OBJETS, et `colonnes.bin` republie
        les mêmes valeurs sur l'axe orthogonal. Le stockage réel fait donc
        environ le double de la grille — c'est le prix, chiffré, de la
        voie B du 12/08, et c'est ce nombre-là que
        `verifier_dimensionnement()` doit voir."""
        return int(self.octets_par_echeance() * len(self.steps)
                   + self.octets_par_colonne() * len(self.lats) * len(self.lons)
                   + self.zsol.nbytes)

    def tranches_colonne(self):
        """Le même contrat, mais À L'INTÉRIEUR D'UN ENREGISTREMENT de
        `colonnes.bin` : offset relatif au début de la colonne.

        ⚠️ Construite à partir du MÊME plan que `tampon_colonnes()`.
        Deux ordres qui divergeraient feraient lire au client des
        températures là où il attend du vent, sans une seule erreur.
        """
        nech = len(self.steps)
        nom_bloc = {"h": "hauteur", "iso": "isobare", "ziso": "isobare",
                    "surf": "surface", "psol": "surface"}
        out = {}
        for cle, bloc, _src, nlev, dt, offset, octets in self._plan_colonne()[0]:
            out[cle] = dict(offset=offset, octets=octets,
                            dtype=np.dtype(dt).name, niveaux=nlev,
                            echeances=nech,
                            disposition="(niveau, echeance)",
                            bloc=nom_bloc[bloc])
        return out

    # ── Ce que chaque bloc pèse, en un seul endroit ───────────────────
    def _blocs(self):
        """(bloc, nom) → (tableau source, nb de niveaux, dtype, octets).

        ⚠️ UNE SEULE TABLE POUR `tranches()` ET `tampon_echeance()`.
        Elles ont été écrites deux fois dans la première version de ce
        lot, et deux tables qui « doivent bouger ensemble » sont le
        défaut que ce fichier passe son temps à refuser : le manifeste
        aurait annoncé des offsets que le tampon ne respectait pas, et le
        client aurait décodé du bruit sans une seule erreur.
        """
        cols = len(self.lats) * len(self.lons)
        out = []
        for bloc, nom in ORDRE_TAMPON:
            if bloc == "h":
                src, nlev, dt = self.h0025[self.i_param[nom]], \
                    len(NIVEAUX_H_0025), np.float16
            elif bloc == "iso":
                src, nlev, dt = self.iso[self.i_param_iso[nom]], \
                    len(NIVEAUX_P), np.float16
            elif bloc == "ziso":
                src, nlev, dt = self.ziso, len(NIVEAUX_P), np.float32
            elif bloc == "surf":
                # ⚠️ `nlev = 1` : un champ de surface est un PLAN par
                # échéance. On lui donne un axe de longueur 1 plutôt
                # qu'un cas particulier partout — la disposition
                # `(niveau, lat, lon)` reste vraie, et le client n'a pas
                # deux façons de lire une tranche.
                # ⚠️ `[None, :]` et NON `[:, None]` : l'axe ajouté doit
                # être celui des NIVEAUX (le premier), pas celui des
                # échéances. Les deux donnent une forme à 4 axes et une
                # taille correcte ; un seul a le bon contenu, et
                # `tampon_echeance` indexe `src[:, k]` sur l'échéance.
                src, nlev, dt = (self.surf[self.i_param_surf[nom]][None, :],
                                 1, np.float16)
            else:
                src, nlev, dt = self.psol[None, :], 1, np.float32
            out.append((bloc, nom, src, nlev, dt,
                        nlev * cols * np.dtype(dt).itemsize))
        return out

    @staticmethod
    def _cle_tranche(bloc, nom):
        """Le nom PUBLIÉ d'une tranche.

        ⚠️ Il porte son bloc. `u` sur les niveaux hauteur et `u` sur les
        isobares sont DEUX champs différents ; un dictionnaire à clé `u`
        en aurait silencieusement perdu un. Les champs de surface, eux,
        ont déjà des noms propres (`t2m`, `rafale`, `psol`…) et n'ont
        besoin d'aucun préfixe.
        """
        if bloc in ("ziso", "psol"):
            return bloc
        if bloc == "iso":
            return f"iso_{nom}"
        return nom

    def _plan(self):
        """La disposition du tampon, remplissage compris — UNE fois.

        Rend [(clé, source, nlev, dtype, offset, octets)] et la taille
        totale. `tranches()` la publie, `tampon_echeance()` l'écrit :
        elles ne peuvent donc pas diverger.

        ⛔⛔ LE REMPLISSAGE N'EST PAS UNE PRÉCAUTION, C'EST UNE
        CORRECTION. La première version se contentait de REFUSER un
        décalage float32 non aligné, en laissant à `ORDRE_TAMPON` le soin
        de tomber juste. Elle tombait juste sur le domaine réel — par
        arithmétique heureuse : 25 × 5 185 est impair, mais les tranches
        float16 vont par paires avant `ziso`, et 2 × 25 × 5 185 × 2 est
        divisible par 4. Le banc l'a démentie dès qu'on lui a donné une
        grille 5 × 7 : `psol` tombait à l'offset 15 610.
        **Un alignement qui dépend du nombre de colonnes n'est pas un
        alignement, c'est une coïncidence** — et celle-ci se serait
        cassée au premier troisième domaine.

        Le remplissage est donc EXPLICITE et publié : le client lit des
        offsets, il n'a rien à recalculer, et la taille annoncée reste
        exactement celle de l'objet servi.
        """
        plan, offset = [], 0
        for bloc, nom, src, nlev, dt, octets in self._blocs():
            taille = np.dtype(dt).itemsize
            reste = offset % taille
            if reste:
                offset += taille - reste          # remplissage explicite
            plan.append((self._cle_tranche(bloc, nom), bloc, src, nlev, dt,
                         offset, octets))
            offset += octets
        return plan, offset

    def tranches(self):
        """Offset, longueur et **dtype** de chaque tranche du tampon.

        C'est ce que le client lit pour construire son `Range`. Publié
        plutôt que déductible : une liste de paramètres recopiée côté
        client est exactement le défaut que le projet a déjà payé avec
        `LEVELS` — « les deux listes doivent bouger ensemble, sinon le
        sélecteur d'altitude propose des paliers dont les tuiles
        n'existent plus ».

        ⚠️ 12/08 — LE `dtype` ENTRE DANS LA TRANCHE, parce que le tampon
        n'est plus homogène : `ziso` et `psol` y sont en float32 au
        milieu de float16. Un client qui supposerait float16 partout
        lirait l'axe vertical comme deux fois plus de valeurs, toutes
        fausses, et toutes finies. Aucun 404, aucune exception, une carte
        plausible.
        """
        nom_bloc = {"h": "hauteur", "iso": "isobare", "ziso": "isobare",
                    "surf": "surface", "psol": "surface"}
        out = {}
        for cle, bloc, _src, nlev, dt, offset, octets in self._plan()[0]:
            out[cle] = dict(offset=offset, octets=octets,
                            dtype=np.dtype(dt).name, niveaux=nlev,
                            bloc=nom_bloc[bloc])
        return out

    @staticmethod
    def lire_npz(chemin, manifeste):
        man = (json.loads(manifeste) if isinstance(manifeste, (str, bytes))
               else manifeste)
        with np.load(chemin) as z:
            g = Grille(man["run"], list(man["echeances"]),
                       z["lats"], z["lons"], z["zsol"],
                       domaine=man.get("domaine", "nord-alpes"))
            g.h0025 = z["h0025"]
            # ⚠️ Les archives locales écrites AVANT l'étape 12 n'ont pas
            # d'isobares. On les relit quand même, en laissant les
            # tableaux à NaN : `couper.py`, `composite.py`,
            # `front_altitude.py` et `test_calque.py --archive` savent
            # déjà lire un produit sans elles, et le remplissage le dira.
            if "iso" in z:
                g.iso = z["iso"]
                g.ziso = z["ziso"]
            if "surf" in z:
                g.surf = z["surf"]
                g.psol = z["psol"]
                # ⚠️ Une archive relue porte des cumuls DÉJÀ différenciés.
                # Sans ce drapeau, un appel à `deaccumuler()` les
                # différencierait une seconde fois — en silence.
                g._deaccumule = True
        return g, man


# ══════════════════════════════════════════════════════════════════════
#  L'INDEX ET LA PURGE — sans jamais lister le bucket
# ══════════════════════════════════════════════════════════════════════
#  ⚠️ TOUTE CETTE SECTION EXISTE PARCE QUE `ListObjects` EST HORS DE
#  PORTÉE. Ce n'est pas une contrainte technique de R2, c'est un choix
#  du projet, écrit dans `storage.py` : `HeadObject` et `ListObjects`
#  sont facturés Class A, et `exists()` LÈVE plutôt que de les laisser
#  passer. La purge doit donc savoir ce qui est en ligne sans le
#  demander au stockage — d'où un index à clé fixe, relu en un seul
#  `GetObject` (Class B) au début de chaque run.
#
#  ⚠️ L'ORDRE DES OPÉRATIONS N'EST PAS INTERCHANGEABLE :
#      1. lire l'index précédent                     (1 GetObject, Class B)
#      2. écrire les objets du nouveau run
#      3. écrire l'index, `restes` = ce qu'on VA supprimer
#      4. supprimer                                  (gratuit chez R2)
#      5. réécrire l'index, `restes` = ce qui a ÉCHOUÉ
#
#  Pourquoi l'index passe AVANT la suppression : sinon une panne entre
#  les deux laisserait des objets ORPHELINS — présents, plus référencés,
#  et invisibles. Sans `ListObjects`, plus rien ne saurait qu'ils
#  existent : ce serait une fuite définitive. Dans l'ordre retenu, une
#  panne laisse au pire un index qui désigne un objet déjà supprimé —
#  un 404 visible, que le run suivant corrige tout seul. Entre une fuite
#  invisible et permanente et une erreur visible et transitoire, le
#  choix se fait sans hésiter.
#
#  Pourquoi DEUX écritures d'index : la première ne peut pas connaître
#  le résultat de suppressions qui n'ont pas eu lieu, et la seconde ne
#  peut pas prévenir la fuite. Elles font deux choses différentes. Le
#  coût est d'une écriture Class A par run — 8 par jour, 0,02 % du
#  palier.
#
#  D'où `restes` : les clés dont la suppression a échoué restent dans
#  l'index, et le run suivant les réessaie. ⓘ Supprimer une clé déjà
#  absente est un succès chez R2 comme chez Supabase, donc un reste
#  périmé disparaît de lui-même au run suivant.
# ══════════════════════════════════════════════════════════════════════
INDEX_VIDE = dict(produit="AGRUME produit B — index des runs en ligne",
                  retention_runs=RETENTION_RUNS, runs=[], restes=[])


def index_apres(index, run, domaine, cles, retention=RETENTION_RUNS):
    """(index_nouveau, a_supprimer) après l'écriture de `run` sur `domaine`.

    ⚠️ Le tri est ANTICHRONOLOGIQUE sur la chaîne du run
    (`2026-08-10T09:00:00Z`), qui est un ISO 8601 en Z à longueur fixe :
    son ordre lexicographique EST son ordre chronologique. Ça vaut d'être
    écrit, parce que ça cesserait d'être vrai le jour où un run porterait
    un décalage horaire (`+02:00`) — et le tri se tromperait en silence.

    ⚠️⚠️ LA RÉTENTION SE COMPTE PAR DOMAINE, ET C'EST LE PIÈGE DE CETTE
    FONCTION DEPUIS LE 12/08. Avec deux domaines écrits dans le même run
    et une rétention globale de 3, les deux domaines du run le plus
    ancien seraient purgés au bout d'un run et demi — ou, si les deux
    domaines n'avancent pas au même rythme (une ingestion pyrénéenne qui
    échoue), le domaine lent disparaîtrait entièrement pendant que le
    rapide garde ses trois runs. On ne mélange pas les compteurs.

    ⛔ ET LA MIGRATION DES CLÉS DE L'ANCIEN FORMAT EST TRAITÉE ICI, PAS
    À LA MAIN. Les entrées écrites avant le 12/08 n'ont pas de `domaine`
    et pointent sur `agrume/grille/{run}/grille.npz`. Elles ne peuvent
    PAS être laissées à l'abandon : `ListObjects` est hors de portée dans
    ce projet, donc un objet qui sort de l'index devient **invisible et
    définitivement perdu** — une fuite, pas un déchet. Toute entrée sans
    `domaine` part donc directement à la suppression, au premier run qui
    suit le déploiement.
    """
    ancien = list((index or {}).get("runs") or [])
    a_supprimer = list((index or {}).get("restes") or [])

    # ── Les entrées de l'ANCIEN format, avant toute autre chose ───────
    legs = [e for e in ancien if not e.get("domaine")]
    for e in legs:
        a_supprimer.extend(e.get("cles") or [])
    ancien = [e for e in ancien if e.get("domaine")]

    garde = [e for e in ancien
             if not (e.get("run") == run and e.get("domaine") == domaine)]
    garde.insert(0, dict(run=run, domaine=domaine, cles=list(cles)))
    garde.sort(key=lambda e: (e["domaine"], e["run"]), reverse=True)

    vivants, sortis = [], []
    par_domaine = {}
    for e in garde:
        n = par_domaine.get(e["domaine"], 0)
        (vivants if n < retention else sortis).append(e)
        par_domaine[e["domaine"]] = n + 1
    vivants.sort(key=lambda e: (e["run"], e["domaine"]), reverse=True)

    for e in sortis:
        a_supprimer.extend(e.get("cles") or [])
    # Dédoublonnage en gardant l'ordre : un reste peut réapparaître si
    # deux runs successifs ont échoué à le supprimer.
    vus, propre = set(), []
    for c in a_supprimer:
        if c not in vus:
            vus.add(c)
            propre.append(c)
    # ⚠️ GARDE-FOU : on ne supprime JAMAIS une clé encore référencée.
    # Sans lui, un run rejoué avec une liste de clés différente pourrait
    # se faire effacer par sa propre purge.
    encore = {c for e in vivants for c in (e.get("cles") or [])}
    propre = [c for c in propre if c not in encore]

    # `restes` = ce qu'on s'apprête à supprimer. C'est l'index de
    # l'étape 3 : il est écrit AVANT la purge, donc il doit désigner les
    # orphelins pour qu'une panne au milieu ne les perde pas de vue.
    nouveau = dict(INDEX_VIDE, retention_runs=retention,
                   runs=vivants, restes=list(propre))
    return nouveau, propre


def index_apres_purge(index, echecs):
    """L'index de l'étape 5 : `restes` ne garde que ce qui a ÉCHOUÉ.

    Sans cette seconde écriture, `restes` ne se viderait jamais et la
    purge réessaierait indéfiniment des clés déjà supprimées — inoffensif
    mais bavard, et surtout impossible à distinguer d'un droit qui
    manque. Un compteur qui ne redescend jamais n'est pas un compteur.
    """
    return dict(index, restes=list(echecs))


def verifier_prefixe(cles, prefixe="agrume/grille/"):
    """⚠️ LE GARDE-FOU QUI EMPÊCHE UNE PURGE DE DÉBORDER.

    Le produit A vit dans le MÊME bucket, sous `agrume/colonnes/`, et il
    est DÉFINITIF : une purge qui s'y égarerait détruirait une archive
    irremplaçable, sans bruit et sans retour possible. Toute clé à
    supprimer est donc vérifiée contre le préfixe du produit B, et une
    seule intruse arrête la purge entière plutôt que de supprimer « ce
    qui est légitime » et de continuer.
    """
    intruses = [c for c in cles if not str(c).startswith(prefixe)]
    if intruses:
        raise ValueError(
            f"purge refusée : {len(intruses)} clé(s) hors du préfixe "
            f"{prefixe!r} — {intruses[:3]}. ⚠️ Le produit A (définitif) "
            f"vit dans le même bucket sous `agrume/colonnes/`.")
    return True
