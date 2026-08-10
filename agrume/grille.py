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

from colonnes import PARAMS_0025
from domaine import GRID_3D, NIVEAUX_H_0025

# ⚠️ LE PRODUIT B N'A PAS SA PROPRE LISTE DE PARAMÈTRES, ET C'EST VOULU.
# Il sert les mêmes cinq champs que le produit A sur les mêmes 25
# niveaux, quantifiés de la même façon — kelvins → Celsius compris. Deux
# listes qui « doivent bouger ensemble » sont exactement ce que
# `domaine.py` existe pour empêcher : le projet a déjà payé ça avec
# `LEVELS`, dupliqué entre l'ingestion et le front.
PARAMS_GRILLE = PARAMS_0025

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


def prefixe_run(run):
    return f"agrume/grille/{run}"


def cles_du_run(run):
    b = prefixe_run(run)
    return [f"{b}/grille.npz", f"{b}/manifest.json"]


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

    def __init__(self, run, steps, lats, lons, zsol):
        self.run = run
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
        self.i_param = {p["nom"]: k for k, p in enumerate(PARAMS_GRILLE)}
        self.i_niveau = {n: k for k, n in enumerate(NIVEAUX_H_0025)}
        self.i_step = {s: k for k, s in enumerate(self.steps)}

    def accepte(self, param_nom, niveau, step):
        """Le champ a-t-il sa place ici ? Le produit A retient des
        niveaux et des paramètres que celui-ci ne porte pas (maille fine,
        isobares) : on filtre plutôt que de lever, sinon le branchement
        dans l'ingestion devrait connaître les deux périmètres."""
        return (param_nom in self.i_param and niveau in self.i_niveau
                and step in self.i_step)

    def poser(self, param_nom, niveau, step, champ2d):
        self.h0025[self.i_param[param_nom], self.i_niveau[niveau],
                   self.i_step[step]] = champ2d

    # ── Complétude ────────────────────────────────────────────────────
    def remplissage_par_parametre(self):
        """⚠️ Par paramètre, comme le produit A, et pour la même raison
        mesurée : la TKE n'existe PAS à l'échéance 0. Un remplissage
        global de 96 % ne dit pas s'il manque un champ par construction
        ou si un run est tronqué."""
        def part(a):
            return round(float(np.isfinite(a.astype(np.float32)).mean()), 4)
        return {p["nom"]: part(self.h0025[k])
                for k, p in enumerate(PARAMS_GRILLE)}

    def remplissage(self):
        return round(float(np.isfinite(
            self.h0025.astype(np.float32)).mean()), 4)

    def octets(self):
        return int(self.h0025.nbytes + self.zsol.nbytes
                   + self.lats.nbytes + self.lons.nbytes)

    # ── Sérialisation ─────────────────────────────────────────────────
    def manifeste(self, extra=None):
        m = dict(
            produit="AGRUME produit B — grille 3D du domaine Nord-Alpes",
            run=self.run,
            echeances=self.steps,
            grille=GRID_3D,
            niveaux_m_sol=list(NIVEAUX_H_0025),
            parametres=[dict(nom=p["nom"], unite=p["unite"],
                             paquet=p["paquet"]) for p in PARAMS_GRILLE],
            disposition=("h0025 = (parametre, niveau, echeance, lat, lon) en "
                         "float16 ; zsol = (lat, lon) en float32 ; lats et "
                         "lons sont dans l'archive"),
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
                "niveaux AGL au-dessus du sol MODÈLE : "
                "altitude_ASL = zsol[lat, lon] + niveau. Une coupe "
                "horizontale à altitude-mer constante n'est PAS un niveau "
                "du tableau : elle s'interpole entre deux niveaux, "
                "différemment en chaque point."),
            retention_runs=RETENTION_RUNS,
            remplissage=self.remplissage(),
            remplissage_par_parametre=self.remplissage_par_parametre(),
            avertissement=(
                "Produit JETABLE : seuls les {n} derniers runs sont en "
                "ligne, l'index `{i}` fait foi. Ne rien bâtir dessus qui "
                "suppose un historique. La TKE n'existe PAS à l'échéance 0 "
                "(mesuré le 10/08) : un remplissage < 100 % sur elle seule "
                "est normal. Les points dont zsol dépasse l'altitude "
                "demandée doivent être MASQUÉS à l'affichage — ce masque "
                "dessine le relief tel que le modèle le voit, c'est une "
                "information, pas un défaut.").format(n=RETENTION_RUNS,
                                                      i=CLE_INDEX))
        if extra:
            m.update(extra)
        return m

    def ecrire_npz(self, chemin):
        np.savez_compressed(chemin, h0025=self.h0025, zsol=self.zsol,
                            lats=self.lats, lons=self.lons,
                            echeances=np.asarray(self.steps, dtype=np.int16))

    @staticmethod
    def lire_npz(chemin, manifeste):
        man = (json.loads(manifeste) if isinstance(manifeste, (str, bytes))
               else manifeste)
        with np.load(chemin) as z:
            g = Grille(man["run"], list(man["echeances"]),
                       z["lats"], z["lons"], z["zsol"])
            g.h0025 = z["h0025"]
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


def index_apres(index, run, cles, retention=RETENTION_RUNS):
    """(index_nouveau, a_supprimer) après l'écriture de `run`.

    ⚠️ Le tri est ANTICHRONOLOGIQUE sur la chaîne du run
    (`2026-08-10T09:00:00Z`), qui est un ISO 8601 en Z à longueur fixe :
    son ordre lexicographique EST son ordre chronologique. Ça vaut d'être
    écrit, parce que ça cesserait d'être vrai le jour où un run porterait
    un décalage horaire (`+02:00`) — et le tri se tromperait en silence.
    """
    ancien = list((index or {}).get("runs") or [])
    garde = [e for e in ancien if e.get("run") != run]
    garde.insert(0, dict(run=run, cles=list(cles)))
    garde.sort(key=lambda e: e["run"], reverse=True)

    vivants, sortis = garde[:retention], garde[retention:]
    a_supprimer = list((index or {}).get("restes") or [])
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
