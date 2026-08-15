#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/orographie.py — le sol du modèle, figé une fois pour toutes
#                                                        (10/08/2026)
#
#  ⚠️ TOUT LE LOT H DÉPEND DE CE FICHIER. Les niveaux « hauteur » d'AROME
#  sont AGL — au-dessus du sol DU MODÈLE, pas du sol réel. La conversion
#  vers l'axe que lit un pilote est donc :
#
#      altitude_ASL = ALTITUDE(lat, lon) + h_AGL
#
#  Se tromper d'`ALTITUDE`, c'est décaler la colonne entière
#  verticalement, silencieusement, sans qu'aucune valeur n'ait l'air
#  fausse. C'est le mode de panne le plus dangereux du lot.
#
#  ── LES DEUX PIÈGES, MESURÉS LE 10/08 ────────────────────────────────
#
#  1. ⚠️ LE PAQUET CHANGE AVEC LA GRILLE : `001/SP3` mais `0025/SP2`.
#     `0025/SP3` existe (67 messages, 55 Mo) et ne contient AUCUNE
#     orographie — que des flux et du rayonnement. Un portage naïf du
#     code existant ne lèverait donc pas d'erreur : il ne trouverait
#     simplement rien. La table est dans `domaine.PAQUET_OROGRAPHIE`, et
#     ce module REFUSE de deviner : une grille absente de la table lève.
#
#  2. ⚠️ LES DEUX GRILLES NE DISENT PAS LA MÊME CHOSE. Aux 648 balises :
#     |écart| médian 30 m, mais 125 balises (19 %) au-delà de 100 m et
#     un extrême à +643 m (Signal de Soi : 1 665 m en 001, 2 308 m en
#     0025). La médiane de l'écart signé est exactement 0 — donc pas de
#     biais, mais une dispersion telle qu'on ne peut PAS servir une
#     tranche 0,01° avec l'orographie 0,025°, ni l'inverse. L'hybride du
#     §4.1 bis étant retenu, on charge LES DEUX, et chacune ne sert que
#     sa tranche.
#
#  ── CE QUE LE MODÈLE FAIT DU RELIEF, ET DANS QUEL SENS ───────────────
#  ⚠️ Le modèle place les balises ~150 m TROP BAS, pas trop haut. C'est
#  l'INVERSE de ce qu'une première version du lot annonçait, et ça a été
#  corrigé DEUX FOIS avant d'être juste :
#
#      ÉCART AU NOM DÉCLARÉ (m), n = 109
#        z_001  − z_nom : d1 −383 · q1 −273 · MÉD −174 · q3 −83 · d9 +18
#        z_0025 − z_nom : d1 −424 · q1 −279 · MÉD −135 · q3 −46 · d9 +55
#
#  Les balises de vol libre sont sur des décollages et des crêtes, et la
#  maille rabote les sommets. ⛔ Et la déduction « ce sera pire en
#  0,025°, la maille est 2,5 fois plus grossière » est FAUSSE : la
#  médiane s'AMÉLIORE (−174 → −135 m), c'est la DISPERSION qui augmente.
#  Ce n'est pas un écrêtage supplémentaire, c'est du bruit
#  d'échantillonnage en plus. *(Mécanisme = hypothèse ; seul l'effet est
#  mesuré.)*
#
#  Décision : ancrer au sol du modèle, AFFICHER LES DEUX ALTITUDES, et
#  écrire l'écart (`elevationDeltaM`). « Le modèle place le sol à
#  1 665 m ; le décollage est à 1 800 m. » Décrire, ne pas maquiller.
#
#  ── POURQUOI C'EST FIGÉ ET VERSIONNÉ ─────────────────────────────────
#  Le champ est STATIQUE d'une échéance à l'autre et d'un run à l'autre.
#  Le retélécharger à chaque run, ce serait 50 Mo par run pour une valeur
#  qui ne bouge pas, ET une dépendance réseau sur le socle de toute la
#  chaîne. Il est donc extrait UNE FOIS, découpé au domaine Nord-Alpes
#  (37 046 points au total pour les deux grilles, ~150 Ko), et commité.
#  `freeze_orographie.py` le régénère ; le manifeste dit de quel run il
#  vient et ce qu'il vaut.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np

from domaine import (GRID_3D, GRID_FINE, MODEL_DIR, PAQUET_OROGRAPHIE,
                     RACCORD_HYBRIDE_M, fenetre)

ARTEFACT_NPZ = Path(__file__).resolve().parent / "data" / "orographie-nord-alpes.npz"
ARTEFACT_JSON = Path(__file__).resolve().parent / "data" / "orographie-nord-alpes.json"

# ── UN ARTEFACT PAR DOMAINE DE PRODUCTION (12/08/2026) ────────────────
# ⚠️ `ARTEFACT_NPZ`/`ARTEFACT_JSON` restent le Nord-Alpes, aux mêmes
# chemins et au même sha256 qu'au 10/08. C'est délibéré et ce n'est pas
# de la compatibilité de façade : toutes les archives du produit A déjà
# écrites déclarent CE sha. Le renommer en `orographie-domaines.npz`, si
# propre que ça paraisse, ferait que plus aucune archive existante ne se
# rapporte à un fichier qui existe.
def _art(nom):
    d = Path(__file__).resolve().parent / "data"
    return d / f"orographie-{nom}.npz", d / f"orographie-{nom}.json"


ARTEFACTS = {"nord-alpes": (ARTEFACT_NPZ, ARTEFACT_JSON),
             "pyrenees": _art("pyrenees"),
             "tarn-aveyron-herault": _art("tarn-aveyron-herault")}

# Clés de métadonnées de grille conservées dans l'artefact. Ce sont
# exactement celles que `arome-wind/ingest.py::parse_grib` fabrique — on
# reste compatible avec `elev_at()` et `orographie_balises.py::indices`,
# volontairement : trois conventions de balayage dans un projet, c'est
# deux de trop.
CLES_META = ("Ni", "Nj", "lat0", "lon0", "di", "dj", "jScan")


class Abort(Exception):
    """Erreur fatale et explicite. ⚠️ Ce module ne renvoie JAMAIS None en
    silence sur une orographie manquante — contrairement à
    `arome-wind/ingest.py::load_orography`, qui imprime un avertissement
    et continue sans `elev`. Là-bas c'est acceptable : le pire est un
    calque de vent sans masquage sous-relief. Ici, une orographie
    manquante ou fausse déplace TOUTES les altitudes servies au pilote.
    On préfère un run échoué à une colonne fausse."""


def norm_lon(x):
    return x - 360 if x > 180 else x


# ══════════════════════════════════════════════════════════════════════
#  PARTIE PURE — testable sans réseau ni GRIB
# ══════════════════════════════════════════════════════════════════════
class Orographie:
    """Le sol du modèle sur le domaine Nord-Alpes, pour UNE grille.

    `z` est un tableau 2D (j, i) en mètres, découpé au domaine ; `meta`
    décrit la grille NATIVE complète et `j0`/`i0` disent où le découpage
    commence. On garde la grille native dans `meta` plutôt que de
    fabriquer une pseudo-grille locale : c'est ce qui permet de comparer
    un indice AGRUME à un indice de la chaîne existante sans conversion.
    """

    __slots__ = ("grille", "z", "meta", "j0", "i0")

    def __init__(self, grille, z, meta, j0, i0):
        self.grille = grille
        self.z = np.asarray(z, dtype=np.float32)
        self.meta = dict(meta)
        self.j0, self.i0 = int(j0), int(i0)

    # ── Indexation ────────────────────────────────────────────────────
    def indices(self, lat, lon):
        """(j, i) LOCAUX du point de grille le plus proche, ou None si le
        point tombe hors du domaine découpé.

        ⚠️ Plus proche voisin, AUCUNE interpolation — volontairement, et
        c'est la même convention que `tools/orographie_balises.py`. Une
        orographie interpolée serait plus lisse que celle qu'AROME
        utilise vraiment, et c'est justement celle qu'AROME utilise qui
        détermine à quelle altitude vit un niveau « hauteur ». On veut le
        relief tel que le modèle le voit, pas un relief plus joli.
        """
        m = self.meta
        i = round((lon - m["lon0"]) / m["di"]) - self.i0
        j = (round((m["lat0"] - lat) / m["dj"]) if m["jScan"] != 1
             else round((lat - m["lat0"]) / m["dj"])) - self.j0
        if j < 0 or j >= self.z.shape[0] or i < 0 or i >= self.z.shape[1]:
            return None
        return j, i

    def z_at(self, lat, lon):
        """Altitude du sol MODÈLE (m), ou None hors domaine."""
        ji = self.indices(lat, lon)
        if ji is None:
            return None
        v = float(self.z[ji])
        return None if not np.isfinite(v) else v

    def coords(self, j, i):
        """(lat, lon) du point local (j, i) — utile pour publier une
        colonne en disant OÙ le modèle l'a vraiment prise."""
        m = self.meta
        jj, ii = j + self.j0, i + self.i0
        lat = (m["lat0"] + m["dj"] * jj if m["jScan"] == 1
               else m["lat0"] - m["dj"] * jj)
        return round(lat, 6), round(m["lon0"] + m["di"] * ii, 6)

    def __repr__(self):
        return (f"<Orographie {self.grille} {self.z.shape[0]}×{self.z.shape[1]} "
                f"z∈[{self.z.min():.0f}, {self.z.max():.0f}] m>")


def altitude_asl(orog, lat, lon, h_agl):
    """`altitude_ASL = ALTITUDE(lat, lon) + h_AGL` — la conversion du
    §3.1 du lot, écrite une seule fois pour que personne ne la retape.

    Renvoie None hors domaine plutôt que d'inventer un plancher : une
    colonne sans sol connu n'est pas une colonne au niveau de la mer.
    """
    z_s = orog.z_at(lat, lon)
    return None if z_s is None else z_s + h_agl


def orographie_pour(paire, h_agl):
    """Laquelle des deux orographies sert la tranche `h_agl` ?

    ⚠️ C'est ICI que vit l'arbitrage de l'hybride (§4.1 bis), et nulle
    part ailleurs : à 100 m/sol et en dessous la donnée existe en maille
    fine, donc on la sert en 0,01° AVEC l'orographie 0,01° ; au-dessus,
    la donnée n'existe qu'en 0,025°, donc orographie 0,025°. Mélanger les
    deux topographies dans une même colonne produirait une marche
    d'origine purement comptable — jusqu'à 643 m sur la balise la pire.

    ⚠️ La marche PHYSIQUE au raccord, elle, n'est pas encore mesurée.
    C'est le point 7 de la séquence du lot, et le critère d'acceptation
    exige qu'elle soit publiée avant de considérer l'hybride comme acquis.
    """
    return paire[GRID_FINE] if h_agl <= RACCORD_HYBRIDE_M else paire[GRID_3D]


def ecart_grilles(paire, points):
    """|z_0025 − z_001| aux `points` [(lat, lon), …]. Renvoie la liste des
    écarts signés (0025 − 001), en ignorant les points hors domaine.

    Sert au critère d'acceptation du lot : un test qui ÉCHOUE si l'écart
    médian des |différences| est nul. Un zéro voudrait dire que les deux
    orographies sont en fait la même — donc qu'on a chargé deux fois le
    même paquet, l'erreur exacte que ce module existe pour empêcher.
    """
    out = []
    for lat, lon in points:
        a = paire[GRID_FINE].z_at(lat, lon)
        b = paire[GRID_3D].z_at(lat, lon)
        if a is not None and b is not None:
            out.append(b - a)
    return out


# ══════════════════════════════════════════════════════════════════════
#  ARTEFACT FIGÉ — lecture / écriture
# ══════════════════════════════════════════════════════════════════════
def _sha256(a: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(a, dtype=np.float32).tobytes()).hexdigest()


def charger_artefact(npz=ARTEFACT_NPZ, js=ARTEFACT_JSON):
    """Charge les deux orographies figées. Renvoie (paire, manifeste) où
    `paire` est {grille: Orographie}.

    ⚠️ Le sha256 de chaque tableau est REVÉRIFIÉ à la lecture. Ce n'est
    pas de la paranoïa gratuite : cet artefact est un binaire commité,
    donc invisible à la relecture d'un diff, et il fixe le plancher de
    toutes les altitudes servies. Une corruption silencieuse (transfert,
    fusion, filtre git mal réglé) ne se verrait autrement qu'à
    l'affichage, chez un pilote.
    """
    npz, js = Path(npz), Path(js)
    if not npz.exists() or not js.exists():
        raise Abort(f"artefact d'orographie absent ({npz.name} / {js.name}) — "
                    f"le régénérer avec `python3 agrume/freeze_orographie.py`")
    man = json.loads(js.read_text(encoding="utf-8"))
    with np.load(npz) as z:
        paire = {}
        for grille, entree in man["grilles"].items():
            arr = z[f"z_{grille}"]
            attendu = entree["sha256"]
            obtenu = _sha256(arr)
            if obtenu != attendu:
                raise Abort(
                    f"orographie {grille} CORROMPUE : sha256 {obtenu[:12]}… "
                    f"au lieu de {attendu[:12]}… — ne pas s'en servir, "
                    f"régénérer l'artefact")
            paire[grille] = Orographie(
                grille, arr, {k: entree["meta"][k] for k in CLES_META},
                entree["j0"], entree["i0"])
    manquantes = {GRID_FINE, GRID_3D} - set(paire)
    if manquantes:
        raise Abort(f"artefact incomplet : grilles manquantes {sorted(manquantes)}")
    return paire, man


def charger_artefacts(noms=None, obligatoires=("nord-alpes",)):
    """Charge l'orographie de CHAQUE domaine de production.

    Renvoie {nom: (paire, manifeste)}. Un domaine dont l'artefact n'est
    pas encore gelé est **absent du résultat**, pas une exception — sauf
    s'il est dans `obligatoires`.

    ⚠️ C'EST LE POINT DE CONCEPTION DE CETTE FONCTION, et il n'est pas
    cosmétique. Le jour où un domaine est ajouté à `DOMAINES`, son
    artefact n'existe pas encore : le gel se lance À LA MAIN, après le
    commit du code. Si l'absence levait, ce commit-là ferait échouer
    TOUS les runs de production entre les deux — pour les Alpes aussi,
    qui n'ont rien demandé. On crie, on continue, et le manifeste du run
    dit quels domaines ont réellement servi.
    ⛔ Le Nord-Alpes reste obligatoire : sans lui il n'y a pas de produit.
    """
    from domaine import DOMAINES
    noms = list(DOMAINES) if noms is None else list(noms)
    out, absents = {}, []
    for nom in noms:
        npz, js = ARTEFACTS[nom]
        try:
            out[nom] = charger_artefact(npz, js)
        except Abort:
            if nom in obligatoires:
                raise
            absents.append(nom)
    return out, absents


def ecrire_artefact(paire, manifeste, npz=ARTEFACT_NPZ, js=ARTEFACT_JSON):
    npz, js = Path(npz), Path(js)
    npz.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(npz, **{f"z_{g}": o.z for g, o in paire.items()})
    js.write_text(json.dumps(manifeste, indent=2, ensure_ascii=False) + "\n",
                  encoding="utf-8")
    return npz.stat().st_size, js.stat().st_size


# ══════════════════════════════════════════════════════════════════════
#  EXTRACTION DEPUIS UN GRIB — a besoin d'eccodes
# ══════════════════════════════════════════════════════════════════════
def cle_s3_orographie(ref, grille, lister):
    """Clé S3 du fichier portant l'orographie pour ce run et cette grille.

    `lister(prefixe) -> [clés]` est injecté pour que ce module reste
    testable sans réseau.

    ⚠️ Le paquet ET le motif de nom de fichier changent tous les deux
    avec la grille (`SP3`/`__00H__` contre `SP2`/`__00H06H__`) : les
    deux viennent de `domaine.PAQUET_OROGRAPHIE`, jamais d'une
    construction à la main.
    """
    if grille not in PAQUET_OROGRAPHIE:
        raise Abort(f"grille {grille!r} inconnue — le paquet portant "
                    f"l'orographie a été MESURÉ pour "
                    f"{sorted(PAQUET_OROGRAPHIE)} et pour elles seules ; "
                    f"il ne se devine pas (0025/SP3 existe et ne contient "
                    f"aucune orographie)")
    paquet, motif = PAQUET_OROGRAPHIE[grille]
    cles = sorted(k for k in lister(f"pnt/{ref}/{MODEL_DIR}/{grille}/{paquet}/")
                  if motif in k)
    if not cles:
        raise Abort(f"orographie introuvable : aucun fichier {motif} dans "
                    f"{grille}/{paquet} pour le run {ref}")
    return cles[0], paquet


def lire_champ_h(chemin):
    """Extrait le champ `h` (surface) d'un GRIB. Renvoie (values, meta).

    ⚠️ On lit message par message EN IGNORANT ceux dont les clés
    attendues manquent — leçon du 21/07/2026, où un run GitHub a été
    cassé en production : `SP3` contient au moins un message sans
    `typeOfLevel`/`level`, et un `codes_get` sans filet levait
    `KeyValueNotFoundError` APRÈS le téléchargement, donc sans publier
    la moindre tuile du run. Le même piège existe en `0025/SP2`, qui a
    79 messages dont UN SEUL est l'orographie.

    ⚠️ En revanche, `h` ABSENT lève : cf. la docstring d'`Abort`.
    """
    from eccodes import (codes_get, codes_get_values,
                         codes_grib_new_from_file, codes_release)
    meta = values = None
    lus = 0
    with open(chemin, "rb") as f:
        while True:
            gid = codes_grib_new_from_file(f)
            if gid is None:
                break
            lus += 1
            try:
                if (codes_get(gid, "shortName") == "h"
                        and codes_get(gid, "typeOfLevel") == "surface"):
                    meta = dict(
                        Ni=codes_get(gid, "Ni"), Nj=codes_get(gid, "Nj"),
                        lat0=codes_get(gid, "latitudeOfFirstGridPointInDegrees"),
                        lon0=norm_lon(codes_get(
                            gid, "longitudeOfFirstGridPointInDegrees")),
                        di=codes_get(gid, "iDirectionIncrementInDegrees"),
                        dj=codes_get(gid, "jDirectionIncrementInDegrees"),
                        jScan=codes_get(gid, "jScansPositively"))
                    values = codes_get_values(gid)
                    codes_release(gid)
                    break
            except Exception:      # noqa: BLE001 — message sans ces clés
                pass
            codes_release(gid)
    if values is None:
        raise Abort(f"champ 'h' (surface) ABSENT de {os.path.basename(chemin)} "
                    f"({lus} messages lus) — ⚠️ vérifier le paquet : "
                    f"`0025/SP3` en contient 67 et AUCUNE orographie, "
                    f"c'est `0025/SP2` qu'il faut")
    return values, meta


def decouper(values, meta, grille, bornes=None):
    """Découpe le champ France entière au domaine Nord-Alpes.

    ✅ Mesuré le 10/08 : la découpe est GRATUITE (7,6 s contre 7,9 s sans
    découpe, à la marge du bruit). Le coût est dans `codes_get_values()` ;
    le `reshape` + slice numpy derrière ne se voit pas. On décode donc la
    France entière et on découpe, sans chercher à être malin.

    `bornes` permet de découper AILLEURS que sur le domaine par défaut :
    la fenêtre de vérification des radiosondages (`fenetre_autour`), et —
    depuis le 12/08 — le **second domaine de production**, les Pyrénées.

    ⚠️ 12/08 : CE COMMENTAIRE DISAIT L'INVERSE, et il faut dire pourquoi
    il a changé plutôt que de l'effacer. Il interdisait de s'en servir
    « pour fabriquer un second domaine de produit ». L'interdit visait
    l'ÉLARGISSEMENT du domaine existant — qui aurait changé le sha256 de
    l'artefact de production et rompu la comparabilité des archives. Un
    second domaine, avec son propre artefact et son propre sha, ne
    touche pas au premier : c'est exactement la voie nº 3 déjà retenue
    pour les radiosondages, appliquée à un vrai domaine cette fois.
    ⛔ L'interdit d'origine, lui, tient toujours : ne pas élargir
    `DOMAINE`.
    """
    j0, j1, i0, i1 = fenetre(meta) if bornes is None else bornes
    grille2d = np.asarray(values, dtype=np.float32).reshape(meta["Nj"], meta["Ni"])
    z = np.ascontiguousarray(grille2d[j0:j1 + 1, i0:i1 + 1])
    return Orographie(grille, z, meta, j0, i0)


# ══════════════════════════════════════════════════════════════════════
#  ARTEFACT DE VÉRIFICATION — le sol sous les points de radiosondage
#
#  ⚠️ SECOND artefact, volontairement séparé du premier. Les stations de
#  radiosondage sont HORS du domaine Nord-Alpes ; leur donner une
#  altitude de sol demandait soit d'élargir la production — donc de
#  changer son sha256 et de rompre la continuité de toutes les archives
#  déjà écrites — soit d'écrire à côté. On écrit à côté.
#
#  ⚠️ Ce fichier ne sert QU'À la vérification. Aucune colonne servie à un
#  pilote n'en dépend, et `ingest_colonnes.py` ne le charge que pour les
#  points marqués `source = "radiosondage"`. Le jour où quelqu'un voudra
#  en faire un domaine de produit, il faudra le décider, pas le laisser
#  arriver.
# ══════════════════════════════════════════════════════════════════════
ARTEFACT_VERIF_NPZ = (Path(__file__).resolve().parent / "data"
                      / "orographie-radiosondages.npz")
ARTEFACT_VERIF_JSON = (Path(__file__).resolve().parent / "data"
                       / "orographie-radiosondages.json")

# ── Le TROISIÈME artefact : les balises isolées (12/08/2026) ──────────
# ⚠️ Même mécanisme que ci-dessus, autre usage, donc autre fichier. Ici
# les points ne sont PAS des appareils de mesure : ce sont des balises de
# pilotes, hors de toute boîte de production, à qui on doit un sol pour
# que leur colonne du produit A ait un plancher. Mélanger les deux dans
# un seul fichier aurait fait qu'un artefact « de vérification » devient
# indispensable à la production — et le §589 d'`ingest_colonnes` explique
# justement pourquoi son absence ne doit PAS arrêter un run.
ARTEFACT_ISOLEES_NPZ = (Path(__file__).resolve().parent / "data"
                        / "orographie-balises-isolees.npz")
ARTEFACT_ISOLEES_JSON = (Path(__file__).resolve().parent / "data"
                         / "orographie-balises-isolees.json")


def charger_artefact_isolees(npz=ARTEFACT_ISOLEES_NPZ,
                             js=ARTEFACT_ISOLEES_JSON):
    """{id_balise: {grille: Orographie}} — le sol des balises hors boîte."""
    return charger_artefact_verif(npz, js, cle="balises",
                                  quoi="des balises isolées",
                                  commande="--balises-isolees")


def charger_artefact_verif(npz=ARTEFACT_VERIF_NPZ, js=ARTEFACT_VERIF_JSON,
                           cle="stations", quoi="de vérification",
                           commande="--radiosondages"):
    """{identifiant: {grille: Orographie}}, sha256 revérifié comme pour la
    production — même raison : c'est un binaire commité, invisible au
    diff.

    ⚠️ 12/08 — `cle` existe parce que le MÊME lecteur sert deux artefacts
    de fenêtres : celui des radiosondages (clé `stations`) et celui des
    balises isolées (clé `balises`). Recopier ce lecteur pour changer un
    nom de clé aurait fait deux vérifications de sha256 à maintenir — et
    le projet a déjà payé deux fois la recopie d'une logique au lieu de
    son appel, le 10/08.
    """
    npz, js = Path(npz), Path(js)
    if not npz.exists() or not js.exists():
        raise Abort(f"artefact {quoi} absent ({npz.name}) — le "
                    f"générer avec `python3 agrume/freeze_orographie.py "
                    f"{commande}`")
    man = json.loads(js.read_text(encoding="utf-8"))
    out = {}
    with np.load(npz) as z:
        for wmo, entrees in man[cle].items():
            out[wmo] = {}
            for grille, e in entrees["grilles"].items():
                arr = z[f"z_{wmo}_{grille}"]
                obtenu = _sha256(arr)
                if obtenu != e["sha256"]:
                    raise Abort(
                        f"orographie de vérification {wmo}/{grille} CORROMPUE "
                        f"(sha256 {obtenu[:12]}… au lieu de {e['sha256'][:12]}…)")
                out[wmo][grille] = Orographie(
                    grille, arr, {k: e["meta"][k] for k in CLES_META},
                    e["j0"], e["i0"])
    return out, man


def ecrire_artefact_verif(par_station, manifeste,
                          npz=ARTEFACT_VERIF_NPZ, js=ARTEFACT_VERIF_JSON):
    npz, js = Path(npz), Path(js)
    npz.parent.mkdir(parents=True, exist_ok=True)
    tableaux = {f"z_{wmo}_{g}": o.z
                for wmo, paire in par_station.items()
                for g, o in paire.items()}
    np.savez_compressed(npz, **tableaux)
    js.write_text(json.dumps(manifeste, indent=2, ensure_ascii=False) + "\n",
                  encoding="utf-8")
    return npz.stat().st_size, js.stat().st_size


def accord_avec_production(par_station, paire_prod, pas=1):
    """⚠️ LE GARDE-FOU DES DEUX FENÊTRES.

    Deux fenêtres découpées dans le même champ statique doivent donner
    EXACTEMENT la même altitude là où elles se recouvrent. Si ce n'est
    pas le cas, « deux fenêtres » est devenu « deux orographies » — et
    une colonne de vérification ne reposerait plus sur le même sol que la
    production qu'elle prétend vérifier.

    Renvoie (n_communs, ecart_max_m). ⚠️ `ecart_max_m` doit valoir
    exactement 0,0 : ce n'est pas une tolérance, c'est le même octet lu
    deux fois. Une valeur non nulle veut dire que les deux artefacts
    viennent de runs différents, ou qu'un indice est décalé.
    """
    n, pire = 0, 0.0
    for paire in par_station.values():
        for grille, o in paire.items():
            prod = paire_prod.get(grille)
            if prod is None:
                continue
            for j in range(0, o.z.shape[0], pas):
                for i in range(0, o.z.shape[1], pas):
                    lat, lon = o.coords(j, i)
                    a = prod.z_at(lat, lon)
                    if a is None:
                        continue
                    n += 1
                    pire = max(pire, abs(a - float(o.z[j, i])))
    return n, pire
