#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/pi_rafale.py — LE FORMAT de la rafale à venir     (09/09/2026)
#                        Lot « cellule qui approche », lot 2
#
#  ⛔ DE QUOI CE FICHIER PARLE, ET COMMENT ON LE NOMME.
#  Il ingère et CITE une source : AROME-PI, le modèle de prévision
#  immédiate de Météo-France, publié sous Licence Ouverte 2.0. Le nom
#  `pi` désigne ici LA SOURCE — jamais un produit de ce projet. La même
#  licence exige l'attribution (le manifeste la porte) et interdit de
#  laisser croire qu'AROME-PI est de nous. Les deux à la fois, comme
#  pour `piaf.py`.
#
#  ── CE QUE CE MODULE N'EST PAS ───────────────────────────────────────
#  ⚠️⚠️ IL N'EST PAS `gust-front.js`. Ce projet a DÉJÀ une chaîne « front
#  de rafales » : elle vit dans `gust-front.js`, elle CONSTATE un front
#  sur le réseau d'observation RADOME (paquet infrahoraire 6 min), et
#  elle porte le signal `gust_front`. Ce module-ci PRÉVOIT, sur un modèle,
#  et porte le signal `gust_pi`. Les deux peuvent parler du même orage
#  sans se contredire : l'un dit « c'est passé sur Narbonne il y a
#  12 min », l'autre « ça arrive sur Bugarach dans 40 ». ⛔ Ils ne
#  partagent NI table, NI scope, NI seuil — la clé de dédup est
#  `(user_id, scope, signal)` et les confondre effacerait une alerte sur
#  deux.
#
#  ── LES SIX FAITS MESURÉS LE 09/09 À 16:08 Z ─────────────────────────
#  1. ⛔ **Le champ porte un SUFFIXE D'AGRÉGATION**, comme PIAF :
#     `…_ABOVE_GROUND_PT15M` (et `_PT30M`, `_PT1H`, `_PT3H`, `_PT6H`).
#     Sans suffixe, DescribeCoverage rend `NoSuchCoverage` — mesuré,
#     `locator=FF_RAF_15MN__HEIGHT___2026-09-09T15.00.00Z`. ⚠️ C'est le
#     MÊME code d'erreur que « ce run n'est pas encore publié » : un
#     poller qui le lit comme « pas encore là » attend pour toujours.
#  2. ⛔⛔ **L'AXE VERTICAL EST OBLIGATOIRE, ET `axe_vertical()` NE SAIT
#     PAS LE TROUVER SEUL.** `niveau=None` rend `HTTP 404 ·
#     InvalidSubsetting · Slicing on height is mandatory`. Et
#     `Portail.axe_vertical()` appelle `describe()` SANS transmettre
#     l'agrégation : lancé sur ce champ, il part sur un identifiant sans
#     `_PT15M` et récolte le 404 du fait nº 1. ⇒ **on passe `niveau=10`
#     ET `axe="height"` en dur, à chaque requête.**
#  3. ⛔⛔ **LE COMPTEUR D'ÉCHÉANCES DE PIAF NE MARCHE PAS ICI.**
#     `ingest_piaf.nb_echeances_publiees` prend le PREMIER `coefficients`
#     non vide du DescribeCoverage. Chez PIAF le champ est de surface :
#     les axes `long`/`lat` sont réguliers, coefficients vides, et le
#     premier non-vide EST le temps. Ici l'axe `height` porte le
#     coefficient `10` — un seul nombre. La recette de PIAF rend donc
#     **1 échéance** sur un run qui en publie 24. Mesuré le 09/09 à
#     16:07 Z : huit runs d'affilée annoncés « partiel (1) » alors que
#     le 15:00 Z était complet depuis une heure. ⇒ on lit
#     `gridAxesSpanned` et on ne garde que `time` (`coefficients_temps`).
#  4. **24 échéances, coefficients 900 … 21 600 s**, soit +15 → +360 min.
#     `stepType = max`, `stepRange = 0m-15m` à +15, `units = m s**-1`,
#     `shortName = max_i10fg`, `typeOfLevel = heightAboveGround`,
#     `level = 10`. ⇒ **l'instant nommé est la FIN de la tranche**, comme
#     chez PIAF, et pour la même raison de ne pas décaler le ruban.
#  5. ⛔ **LA GRILLE EST `001`, PAS `0025`.** Les deux servent le champ.
#     `0025` rend du 0,025° (1 121 × 717 sur −12 → 16 E) : 0,02° n'en
#     dérive pas par un facteur entier — le piège exact d'A19 bis pour
#     PIAF. `001` rend du **0,01°**, et sur la boîte PIAF il rend
#     **912 × 1 472, coin 51,11 N / −5,21 E** — c'est-à-dire EXACTEMENT
#     les axes de `piaf.py`, à la maille près. Les deux calques sont donc
#     superposables point pour point, et le composite du lot 3 n'aura
#     rien à reprojeter. C'est la raison pour laquelle ce module IMPORTE
#     la géométrie de `piaf` au lieu de la recopier (cf. plus bas).
#  6. **Latence de publication : mesurée entre 47 et 68 min**, et elle
#     n'est PAS une constante — le 08/09 la note parlait de H+2 h 40, le
#     09/09 au matin de ≤ 47 min, le 09/09 à 16:08 Z le run 15:00 Z était
#     complet depuis au plus 68 min. ⚠️ Aucune décision de ce module ne
#     repose sur ce chiffre : `derniers_runs` interroge et la première
#     réponse complète gagne. La latence RÉELLE de chaque run est
#     MESURÉE à l'ingestion et publiée dans le manifeste, pour qu'on
#     puisse la relire dans six mois au lieu de la recroire.
#
#  ── COÛT MESURÉ, ET L'ARBITRAGE DE YANN ──────────────────────────────
#      une échéance, boîte entière, 0,01°   2,01 Mo   5,9 s
#      un run de 24 échéances               ~48 Mo    ~141 s
#      le CALQUE publié (0,02°, float16)    0,67 Mo par échéance
#                                           16,1 Mo par run EN LIGNE
#  Arbitrage Yann du 09/09 : **0,02° par MAXIMUM** — la règle PIAF, et
#  pour une raison encore plus forte ici. La rafale d'une ligne de grains
#  est un fil de quelques kilomètres de large ; décimer le ferait
#  disparaître entre deux points gardés, moyenner l'aplatirait de 20 à
#  30 %. Le maximum ne perd jamais la rafale : il l'élargit d'au plus
#  1 km. ⛔ L'erreur va donc TOUJOURS dans le sens prudent, et le
#  manifeste le DIT — un calque qui surestime l'étendue sans le dire
#  serait un mensonge crédible.
#
#  ── UN SEUL JEU D'OBJETS, ET POURQUOI ────────────────────────────────
#      carte.bin      calque   0,02°   456 × 736   float16   16,1 Mo/run
#  ⚠️ PAS de `colonnes-{domaine}.bin`. PIAF en publie parce que la COUPE
#  verticale lit une colonne au pas natif. Rien ne dessine de coupe de
#  rafale aujourd'hui : publier 33 Mo de plus par run servirait un
#  consommateur qui n'existe pas. Le jour où la coupe en voudra, la
#  brique est dans `piaf.Passe.colonnes_bin` et se transpose en dix
#  lignes — mais elle ne s'écrit pas « au cas où ».
#
#  ⛔⛔ LES OBJETS S'ÉCRIVENT ENSEMBLE OU PAS DU TOUT, et
#  `index["dernier"]` n'avance qu'après TOUTES les écritures. La leçon du
#  Lot L2, mot pour mot, et elle vaut ici aussi.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import datetime as dt
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

from grille import (index_apres, index_apres_purge,  # noqa: E402
                    verifier_prefixe)
from quantification import PARAM_RAFALE_PI_15MIN, quantifier  # noqa: E402

# ⛔⛔ LA GÉOMÉTRIE EST CELLE DE PIAF, IMPORTÉE, PAS RECOPIÉE.
#
# Le fait nº 5 le rend possible : sur la grille `001`, la boîte PIAF rend
# la MÊME fenêtre 912 × 1 472 au même coin. Deux copies de ces nombres
# divergeraient le jour où l'une des deux boîtes bouge — et le lot 3
# calculerait alors un composite entre deux nappes décalées d'une
# colonne, c'est-à-dire une carte de gradient horizontal déguisée en
# signal convectif. Exactement le défaut que `pi.aligner_sur_axes()`
# existe pour attraper, en pire : ici il n'y aurait aucune requête pour
# le révéler.
#
# ⚠️ Le prix de ce choix : `pi_rafale` ne peut pas changer d'emprise sans
# `piaf`. C'est VOULU. Si un jour il le faut, ce sera un arbitrage
# explicite, pas un effet de bord — et `verifier_alignement()` plus bas
# refusera tant qu'il n'aura pas été pris.
from piaf import (BOITE, FACTEUR_CALQUE, PAS_CALQUE_DEG,  # noqa: E402
                  PAS_DEG, Abort, axes_boite, horodatage, json_octets,
                  reduire_max, verifier_parite)


# ══════════════════════════════════════════════════════════════════════
#  CE QUE LE PORTAIL SERT
# ══════════════════════════════════════════════════════════════════════
#: ⚠️ Le nom EXACT, relevé le 09/09. Il dit « 15MIN » et c'est vrai :
#: `stepRange = 0m-15m`. Contrairement à PIAF, l'étiquette ne ment pas.
CHAMP_WCS = "WIND_SPEED_GUST_15MIN__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND"

#: Les cinq agrégations publiées pour chaque run (530 identifiants =
#: 106 runs × 5, sur AROME-PI `001` ET `0025`).
AGREGATIONS = ("PT15M", "PT30M", "PT1H", "PT3H", "PT6H")

#: ⛔ ON N'INGÈRE QUE `PT15M`. Les autres sont des maxima sur des
#: fenêtres plus longues : ils LISSENT exactement ce qu'on cherche. Une
#: rafale de 90 km/h qui dure trois minutes reste 90 km/h dans le
#: `PT15M` ; dans le `PT1H` elle reste 90 aussi (c'est un maximum), mais
#: on ne sait plus À QUEL MOMENT de l'heure — et l'ETA du push, qui est
#: tout l'objet de ce lot, s'évapore.
AGREGATION = "PT15M"

#: ⛔⛔ NON NÉGOCIABLES, faits nº 1 et 2. `niveau=None` rend
#: « Slicing on height is mandatory », et laisser `axe=None` déclenche un
#: `axe_vertical()` qui perd le suffixe.
NIVEAU_M = 10
AXE_VERTICAL = "height"

#: ⛔ `001` et pas `0025` — fait nº 5. La grille 0,025° ne se réduit pas
#: en 0,02° par un facteur entier.
GRILLE = "001"

PAS_MIN = 15
NB_ECHEANCES = 24
HORIZON_MIN = PAS_MIN * NB_ECHEANCES           # 360
#: Cadence du PRODUCTEUR : un run par heure ronde (coefficients 900 …
#: 21 600 s, envelope 15:15 → 21:00 pour le run 15:00 Z).
CADENCE_RUNS_MIN = 60
#: Cadence d'ingestion — LA NÔTRE. 10 min comme PIAF, non parce qu'il
#: sort quelque chose toutes les 10 min (il en sort un par heure), mais
#: parce que la latence varie de 47 à 68 min (fait nº 6) : un rendez-vous
#: fixe raterait la moitié des runs d'une demi-heure. ⚠️ Cinq passages
#: sur six ne font donc RIEN et sortent en code 3 — c'est le cas
#: nominal, et le lanceur ne doit pas le pinguer comme un échec.
CADENCE_MIN = 10

#: ⚠️ float16, comme partout. Mesuré : à 23,5 m/s (le maximum réel du
#: 09/09 sur la boîte entière) le pas du float16 vaut 0,016 m/s, soit
#: 0,06 km/h. Trois ordres de grandeur sous l'incertitude du modèle.
DTYPE = np.dtype("<f2")

#: Le seuil de l'arbitrage Yann du 09/09 : **40 km/h**, « ça devient
#: sérieux » pour du parapente. Écrit ici en m/s parce que c'est l'unité
#: PUBLIÉE — convertir dans le manifeste obligerait le lecteur à deviner
#: laquelle des deux il lit.
#:
#: ⚠️ CE NOMBRE N'EST PAS UN SEUIL DE PUSH ICI. Ce module ne pousse rien
#: et ne décide rien : il ne s'en sert que pour la mesure
#: `part_ventee` du manifeste, qui répond à « ce run a-t-il de quoi
#: déclencher quelque chose ? ». Le vrai seuil du push vit dans
#: `lib/rafale-pi.js` (`DEFAUTS.seuilKmh`), surchargeable sans
#: réingérer une seule passe. ⛔ Les deux doivent rester d'accord : le
#: banc `test_pi_rafale.py` le vérifie contre la valeur du module JS.
SEUIL_PUSH_KMH = 40.0
SEUIL_PUSH_MS = round(SEUIL_PUSH_KMH / 3.6, 4)     # 11,1111 m/s

# ══════════════════════════════════════════════════════════════════════
#  LES CLÉS
# ══════════════════════════════════════════════════════════════════════
PREFIXE = "agrume/pi-rafale/"
CLE_INDEX = "agrume/pi-rafale/index.json"
GABARIT_CLE = "agrume/pi-rafale/{run}/{objet}"

#: ⛔ DEUX runs en ligne. Le second existe pour qu'un client qui lisait
#: le précédent ne prenne pas un 404 pendant la publication du suivant.
#: À 24 runs/jour et 16,1 Mo pièce, chaque run gardé coûte 16 Mo.
RETENTION_RUNS = 2

#: ⛔ LE PLAFOND DUR. 2 objets + 2 écritures d'index = 4 par run. Posé à
#: 8 : de quoi absorber une republication d'index après purge partielle,
#: pas de quoi laisser une boucle écrire mille objets.
PLAFOND_ECRITURES = 8

#: Le flux unique de ce produit, au sens de `grille.index_apres` (qui
#: compte la rétention PAR domaine). Les deux objets d'un run forment un
#: tout indissociable : un seul flux.
FLUX = "run"

INDEX_VIDE = dict(
    produit="AGRUME — index des runs de rafale à venir en ligne",
    retention_runs=RETENTION_RUNS, runs=[], restes=[], dernier={})


def cles_du_run(run):
    """Les deux clés d'un run, dans l'ORDRE D'ÉCRITURE.

    ⛔ LE MANIFESTE EN DERNIER, toujours. Il est ce qui rend les octets
    lisibles : publié avant eux, il décrirait un `carte.bin` absent, et
    un client qui l'a lu demanderait une clé qui rend 404.
    """
    return [GABARIT_CLE.format(run=run, objet="carte.bin"),
            GABARIT_CLE.format(run=run, objet="manifest.json")]


# ══════════════════════════════════════════════════════════════════════
#  PARTIE PURE — géométrie et temps, testables sans réseau ni clé
# ══════════════════════════════════════════════════════════════════════
def verifier_alignement():
    """⛔⛔ LE GARDE-FOU QUI PROTÈGE LE COMPOSITE DU LOT 3.

    Il ne vérifie qu'une chose, et c'est la seule qui compte : que le
    calque de rafale et le calque de pluie décrivent la MÊME grille. Tant
    que c'est vrai, le lot 3 peut lire les deux nappes maille par maille
    sans une ligne d'interpolation ; le jour où ce n'est plus vrai, il
    calculerait un composite entre deux cartes décalées — plausible à
    l'œil, faux partout, et invisible sur un tracé.

    ⚠️ Il n'y a rien à « comparer » puisque la géométrie est IMPORTÉE de
    `piaf` : c'est exactement le point. Ce contrôle existe pour attraper
    le jour où quelqu'un, croyant bien faire, recopiera les nombres ici.
    """
    verifier_parite()
    lats, lons = axes_boite()
    if PAS_DEG != 0.01 or FACTEUR_CALQUE != 2:
        raise Abort(
            f"la maille de `piaf` vaut {PAS_DEG}° réduite par "
            f"{FACTEUR_CALQUE} — la rafale d'AROME-PI n'est servie qu'au "
            f"0,01° (grille `001`), et 0,02° en dérive par un facteur "
            f"ENTIER. ⛔ Changer l'un des deux sans l'autre publierait "
            f"deux calques qui ne se superposent plus, et le composite du "
            f"lot 3 les mélangerait sans rien signaler.")
    return len(lats), len(lons)


def _instant(run):
    return dt.datetime.strptime(run, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=dt.timezone.utc)


def echeances(run):
    """Les 24 tranches d'un run, chacune avec ses DEUX bornes.

    ⛔⛔ L'INSTANT NOMMÉ EST LA FIN DE LA TRANCHE. Mesuré le 09/09 :
    l'échéance demandée à `run + 15 min` porte `stepRange = 0m-15m`. La
    tranche couvre donc `]debut, fin]`, et un client qui prendrait `fin`
    pour le début décalerait tout le ruban d'un quart d'heure — sans
    qu'une seule requête n'échoue.

    ⚠️ Et la conséquence est plus forte ici que pour la pluie. Une averse
    décalée de 5 min reste une averse ; une rafale annoncée 15 min trop
    tôt, c'est un pilote qui plie pour rien, puis qui n'y croit plus.
    """
    t0 = _instant(run)
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


def runs_candidats(maintenant=None, recul_min=40, profondeur_min=240):
    """Les runs horaires plausibles, du plus FRAIS au plus ancien.

    ⚠️ `recul_min = 40` parce que la latence mesurée va de 47 à 68 min
    (fait nº 6) : demander le run de l'heure qui vient de sonner coûte un
    `NoSuchCoverage` à chaque fois. Ce chiffre n'ordonne QUE la liste ;
    la première candidate qui répond complète gagne. Trop court, il coûte
    une requête ; trop long, il fait rater un run frais pendant une
    heure — d'où la prudence dans ce sens-là.

    ⚠️ `profondeur_min = 240` : quatre heures. Au-delà, un run n'a plus
    grand-chose à dire d'une cellule qui approche, et le portail garde de
    toute façon 4,25 jours qu'on ne veut pas parcourir.
    """
    t = maintenant or dt.datetime.now(dt.timezone.utc)
    depart = (t - dt.timedelta(minutes=recul_min)).replace(
        minute=0, second=0, microsecond=0)
    return [horodatage(depart - dt.timedelta(hours=n))
            for n in range(profondeur_min // 60 + 1)]


# ══════════════════════════════════════════════════════════════════════
#  LE CONTENEUR — un run, prêt à être servi
# ══════════════════════════════════════════════════════════════════════
class Run:
    """Le ruban 0 → 360 min d'un run, au format du calque.

        natif : (24, nj, ni) — la boîte ingérée AU PAS NATIF 0,01°, en
                m/s, unités du GRIB (la sentinelle 9999 est encore
                dedans : c'est `quantifier` qui la traite, par égalité
                exacte).

    ⚠️ Le tableau est gardé UNE FOIS, au pas natif, et le calque en
    dérive. Deux constructions indépendantes des mêmes octets, c'est la
    divergence assurée le jour où l'une bouge.
    """

    def __init__(self, run, natif, lats, lons, latence_min=None):
        self.run = run
        self.boite = dict(BOITE)
        self.latence_min = latence_min
        self.lats = np.asarray(lats, dtype=np.float32)
        self.lons = np.asarray(lons, dtype=np.float32)
        a = np.asarray(natif)
        attendu = (NB_ECHEANCES, len(self.lats), len(self.lons))
        if a.shape != attendu:
            raise Abort(f"ruban {a.shape} au lieu de {attendu}")
        # ⚠️ Quantifié TRANCHE PAR TRANCHE : `quantifier` promeut en
        # float64, et le faire d'un coup sur les 24 échéances coûterait
        # 258 Mo de copie temporaire sur un VPS qui fait tourner trois
        # autres chaînes. Même arbitrage que `piaf.Passe`.
        self.rafale = np.stack(
            [quantifier(a[k], PARAM_RAFALE_PI_15MIN)
             for k in range(NB_ECHEANCES)]).astype(np.float16)
        self.echeances = echeances(run)

    # ── Le jeu du CALQUE ──────────────────────────────────────────────
    def carte(self):
        """`(échéance, lat, lon)` au pas du calque — maximum du bloc 2×2.

        ⛔ MAXIMUM, et c'est l'arbitrage de Yann du 09/09. La rafale
        d'une ligne de grains est un fil de quelques kilomètres :
        décimer le ferait disparaître entre deux points gardés, moyenner
        l'aplatirait de 20 à 30 %. Le maximum ne la perd jamais ; il
        l'élargit d'au plus 1 km.
        """
        return reduire_max(self.rafale.astype(np.float32)).astype(np.float16)

    def axes_calque(self):
        """⚠️ La coordonnée d'une maille du calque est celle de son
        premier point natif (le coin NORD-OUEST du bloc), pas son centre
        — nommer un centre demanderait d'inventer une demi-maille."""
        return (self.lats[::FACTEUR_CALQUE], self.lons[::FACTEUR_CALQUE])

    def octets_par_echeance(self):
        lat_c, lon_c = self.axes_calque()
        return len(lat_c) * len(lon_c) * DTYPE.itemsize

    def carte_bin(self):
        """⛔ L'ÉCHÉANCE EST L'AXE EXTERNE. Le lecteur sert UN instant à
        la fois et balaie la carte entière ; avec l'échéance dehors il
        tire un seul Range de `octets_par_echeance` (671 232 octets) et a
        toute la France. Avec la latitude dehors, il en tirerait 456."""
        return np.ascontiguousarray(self.carte(), dtype=DTYPE).tobytes()

    def remplissage_par_echeance(self):
        """⚠️ PAR ÉCHÉANCE, jamais un chiffre global. Une échéance
        entièrement absente au milieu du ruban se lirait « 95,8 % » dans
        un remplissage global — et ferait un trou d'un quart d'heure à
        l'endroit exact où le pilote regarde."""
        return [round(float(np.isfinite(
                    self.rafale[k].astype(np.float32)).mean()), 4)
                for k in range(NB_ECHEANCES)]

    def mesures(self):
        """Ce que le run contient VRAIMENT — pour qu'un champ mort ne
        ressemble pas à une journée sans vent.

        ⚠️ `part_ventee` est calculée au SEUIL DU PUSH (11,11 m/s =
        40 km/h, l'arbitrage de Yann du 09/09) et pas à un seuil rond de
        confort : c'est le seul chiffre qui répond à « ce run a-t-il de
        quoi déclencher quelque chose ? ». Un run tout vert à 0,04 m/s et
        un run mort donnent tous deux 0 — mais le premier aura
        `renseignees = 1,0` et le second beaucoup moins.
        """
        a = self.rafale.astype(np.float32)
        fini = np.isfinite(a)
        n = int(fini.sum())
        return dict(
            mailles=int(a.size),
            renseignees=round(n / a.size, 4) if a.size else 0.0,
            seuil_part_ventee_ms=SEUIL_PUSH_MS,
            part_ventee=(round(float(np.count_nonzero(
                np.where(fini, a, 0.0) >= SEUIL_PUSH_MS)) / n, 4)
                if n else 0.0),
            max_ms=(round(float(np.nanmax(a)), 2) if n else None),
            max_kmh=(round(float(np.nanmax(a)) * 3.6, 1) if n else None),
            mediane_ms=(round(float(np.nanmedian(a)), 2) if n else None))

    def octets_publies(self):
        return self.octets_par_echeance() * NB_ECHEANCES

    # ── LE MANIFESTE ──────────────────────────────────────────────────
    def manifeste(self, extra=None):
        lat_c, lon_c = self.axes_calque()
        return dict(
            produit=("AGRUME — rafale à venir, ruban 15 min (jetable). "
                     "Un seul jeu : calque 0,02° réduit par MAXIMUM."),
            run=self.run,
            # ⛔ L'ÂGE N'EST PAS PUBLIÉ, ET C'EST DÉLIBÉRÉ — même règle
            # que `piaf.py`. Un âge écrit ici périmerait à la lecture :
            # servi depuis un cache, il dirait « 3 min » sur un run qui
            # en a 90. On publie de quoi le CALCULER : `run` et
            # `ecrit_le` de l'index.
            age=("NON PUBLIÉ. Se calcule à l'écran : maintenant − `run`. "
                 "⚠️ Et il vieillit VITE : le producteur ne sort qu'un "
                 "run par heure, avec 47 à 68 min de latence — un run "
                 "frais a déjà une heure. C'est normal, et c'est "
                 "précisément pourquoi l'âge doit être DIT plutôt que "
                 "tu."),
            source=dict(
                producteur="Météo-France",
                produit="AROME-PI (prévision immédiate), rafale à 10 m",
                licence="Licence Ouverte 2.0 (Etalab)",
                attribution=("Source : Météo-France — AROME-PI, "
                             "Licence Ouverte 2.0"),
                note=("⛔ Cette mention est une OBLIGATION de la licence, "
                      "pas une politesse. ⚠️ Et la même licence interdit "
                      "d'appeler « AROME-PI » ce que ce projet fabrique : "
                      "on cite la source, on ne s'en réclame pas."),
                couverture_wcs=CHAMP_WCS,
                agregation=AGREGATION,
                agregations_publiees=list(AGREGATIONS),
                grille=GRILLE,
                niveau_m=NIVEAU_M,
                axe_vertical=AXE_VERTICAL,
                latence_publication_min=self.latence_min,
                cadence_producteur_min=CADENCE_RUNS_MIN,
                cadence_ingestion_min=CADENCE_MIN,
                piege_suffixe=(
                    "⛔ L'identifiant de couverture porte le suffixe "
                    "`_PT15M`. Sans lui, DescribeCoverage rend "
                    "`NoSuchCoverage` — le MÊME code que « run absent ». "
                    "Un poller qui le lit comme « pas encore publié » "
                    "attend pour toujours."),
                piege_axe=(
                    "⛔ `subset=height(10)` est OBLIGATOIRE : sans lui le "
                    "portail rend « Slicing on height is mandatory ». Et "
                    "`Portail.axe_vertical()` ne transmet pas "
                    "l'agrégation — l'appeler ici récolterait le 404 "
                    "ci-dessus. On passe `axe=\"height\"` en dur.")),
            echeances=self.echeances,
            pas_min=PAS_MIN,
            horizon_min=HORIZON_MIN,
            convention_temps=(
                "⛔ L'INSTANT NOMMÉ EST LA FIN DE LA TRANCHE. Mesuré : "
                "l'échéance +15 min porte `stepRange = 0m-15m`. Chaque "
                "valeur est le MAXIMUM de rafale sur `]fin − 15 min, "
                "fin]`. ⚠️ Prendre `fin` pour le début décalerait tout le "
                "ruban d'un quart d'heure sans qu'une requête n'échoue."),
            parametre=dict(
                nom=PARAM_RAFALE_PI_15MIN["nom"],
                unite=PARAM_RAFALE_PI_15MIN["unite"],
                grandeur=("`max_i10fg` — la rafale maximale à 10 m. LE "
                          "MÊME paramètre que la ligne « Rafale » de la "
                          "coupe (`quantification.PARAMS_SURFACE`), à la "
                          "FENÊTRE PRÈS."),
                avertissement_unite=(
                    "⚠️ Les octets sont en MÈTRES PAR SECONDE, pas en "
                    "km/h. `units = m s**-1`, vérifié à chaque échéance à "
                    "l'ingestion. Multiplier par 3,6 pour afficher — une "
                    "fois, chez le lecteur."),
                avertissement_fenetre=(
                    "⛔ NE PAS COMPARER À `rafale` D'AROME. Les deux sont "
                    "`stepType = max` sur `max_i10fg`, mais la fenêtre "
                    "d'AROME est l'HEURE et celle-ci le QUART D'HEURE. Un "
                    "maximum horaire est toujours ≥ un maximum de quart "
                    "d'heure, et l'écart grandit avec la convection — "
                    "c'est-à-dire exactement quand ce produit parle. "
                    "Mélangés dans une même série, ils dessineraient une "
                    "rafale qui « retombe » de 20 % au changement de "
                    "source, sans une seule valeur fausse.")),
            # ── La géométrie ────────────────────────────────────────
            boite=dict(self.boite),
            axes=dict(
                nb_lat=len(self.lats), nb_lon=len(self.lons),
                pas_deg=PAS_DEG,
                lat_premier=round(float(self.lats[0]), 4),
                lat_dernier=round(float(self.lats[-1]), 4),
                lon_premier=round(float(self.lons[0]), 4),
                lon_dernier=round(float(self.lons[-1]), 4),
                sens=("lats DÉCROISSANTES (premier point au NORD) ; "
                      "lons croissantes")),
            # ══ CE QUE LE CLIENT DOIT LIRE POUR SERVIR ═══════════════
            service=dict(
                cle_index=CLE_INDEX,
                encodage="aucun — les objets sont BRUTS, Range-ables",
                dtype=DTYPE.name,
                calque=dict(
                    cle=GABARIT_CLE.format(run=self.run, objet="carte.bin"),
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
                        "centre."),
                    pourquoi_maximum=(
                        "⚠️ La rafale d'une ligne de grains est un fil de "
                        "quelques kilomètres. Décimer le ferait "
                        "DISPARAÎTRE entre deux points gardés ; moyenner "
                        "l'aplatirait de 20 à 30 %. Le maximum ne le perd "
                        "jamais : il l'élargit d'au plus 1 km. Ce calque "
                        "SURESTIME donc l'étendue de la rafale d'au plus "
                        "une maille, et ne sous-estime jamais son "
                        "intensité."),
                    pourquoi_pas_0025=(
                        "La grille AROME-PI `0025` sert du 0,025°, et "
                        "0,025 / 0,02 n'est pas entier : en dériver 0,02° "
                        "demanderait d'interpoler. On tire donc la grille "
                        "`001` (0,01°), dont 0,02° est le double exact."),
                    alignement_piaf=(
                        "⛔ CE CALQUE EST SUPERPOSABLE MAILLE POUR MAILLE "
                        "AU CALQUE DE PLUIE de `agrume/piaf/` : même "
                        "boîte, même pas, même coin, même sens d'axes — "
                        "la géométrie est IMPORTÉE de `piaf.py`, pas "
                        "recopiée. C'est ce qui permettra au composite du "
                        "lot 3 de lire les deux nappes sans une ligne "
                        "d'interpolation."))),
            # ══ LES REFUS NOMMÉS ═════════════════════════════════════
            refus=[
                dict(quoi="hors emprise",
                     regle=f"hors de `boite` ({BOITE['latmin']} → "
                           f"{BOITE['latmax']} N × {BOITE['lonmin']} → "
                           f"{BOITE['lonmax']} E)",
                     dire="« hors de l'emprise AROME-PI » — jamais un "
                          "silence, jamais un zéro."),
                dict(quoi="run trop vieux",
                     regle="âge du run au-delà du seuil du lecteur",
                     dire="« run ancien (N min) » puis, plus loin, refus "
                          "nommé. ⛔ L'âge est TOUJOURS dit, même quand "
                          "le run est frais."),
                dict(quoi="échéance dépassée",
                     regle=f"au-delà de {HORIZON_MIN} min après le run",
                     dire="« au-delà de l'horizon du modèle » — ne pas "
                          "extrapoler la dernière tranche."),
                dict(quoi="maille non renseignée",
                     regle="NaN (sentinelle 9999 du GRIB, hors domaine)",
                     dire="« pas de donnée ici » — ⛔ jamais 0, qui est "
                          "une rafale parfaitement crédible.")],
            remplissage_par_echeance=self.remplissage_par_echeance(),
            mesures=self.mesures(),
            retention_runs=RETENTION_RUNS,
            octets_publies=self.octets_publies(),
            avertissement=(
                "Produit JETABLE : seuls les {n} derniers runs sont en "
                "ligne, et c'est `dernier` dans l'index `{i}` qui désigne "
                "le run LISIBLE — les {k} objets s'écrivent ensemble ou "
                "pas du tout, et `dernier` n'avance qu'après la dernière "
                "écriture."
            ).format(n=RETENTION_RUNS, i=CLE_INDEX,
                     k=len(cles_du_run(self.run))),
            **(extra or {}))


# ══════════════════════════════════════════════════════════════════════
#  L'ÉCRITURE, L'INDEX ET LA PURGE
#
#  ⛔⛔ TROIS RÈGLES, RECOPIÉES DE `piaf.py` PARCE QU'ELLES ONT DÉJÀ
#  COÛTÉ (leçons du Lot L2 et du L3b) :
#   1. TOUT est sérialisé AVANT la première écriture — sérialiser pendant
#      l'envoi laisserait une fenêtre où une erreur de forme arriverait
#      APRÈS que `carte.bin` soit en ligne.
#   2. L'index s'écrit AVANT la purge. Une purge qui échoue laisse des
#      clés en ligne ; l'index les connaît et les reprendra. L'inverse
#      laisse des objets payés que plus rien ne nomme.
#   3. `st.delete` NE LÈVE PAS : il rend `False`. On lit sa valeur.
# ══════════════════════════════════════════════════════════════════════
def _ecrire_index(st, run, cles, avancer, journal=print, maintenant=None):
    ecrit_le = maintenant or horodatage()
    index = st.get_json(CLE_INDEX) or dict(INDEX_VIDE)
    dernier = dict(index.get("dernier") or {})
    nouveau, a_supprimer = index_apres(index, run, FLUX, cles,
                                       retention=RETENTION_RUNS)
    nouveau["produit"] = INDEX_VIDE["produit"]
    verifier_prefixe(a_supprimer, prefixe=PREFIXE)
    if avancer:
        dernier[FLUX] = run
    nouveau["dernier"] = dernier
    nouveau["ecrit_le"] = ecrit_le
    nouveau["note"] = (
        "⛔ `dernier.run` est LE run à lire : il n'avance qu'après "
        "l'écriture de TOUS les objets. `runs` liste ce qui est en ligne "
        "pour la purge et peut contenir un run incomplet — ne pas le lire "
        "pour choisir quoi servir. ⛔ `ecrit_le` est le JETON DE CACHE. "
        "⚠️ L'ÂGE se calcule depuis `dernier.run`, il n'est jamais "
        "publié : publié, il périmerait à la lecture.")
    st.put(CLE_INDEX, json_octets(nouveau), cache_control="no-store",
           content_type="application/json")

    if not a_supprimer:
        return nouveau
    echecs = [c for c in a_supprimer if not st.delete(c)]
    journal(f"     purge : {len(a_supprimer) - len(echecs)} clés supprimées"
            + (f", {len(echecs)} échecs (réessayés au run suivant)"
               if echecs else ""))
    # ⚠️ Même `ecrit_le` que l'écriture ci-dessus : le jeton de cache ne
    # doit pas bouger pour une purge, sinon tous les clients
    # retéléchargent 16 Mo d'octets rigoureusement identiques.
    apres = index_apres_purge(nouveau, echecs)
    apres["ecrit_le"] = ecrit_le
    st.put(CLE_INDEX, json_octets(apres), cache_control="no-store",
           content_type="application/json")
    return apres


def ecrire(st, r, extra=None, journal=print, maintenant=None):
    """Les deux objets, puis l'index. Dans cet ordre, manifeste en
    dernier."""
    from storage import CACHE_REECRIT                     # noqa: PLC0415
    cles = cles_du_run(r.run)
    corps = [(cles[0], r.carte_bin(), "application/octet-stream"),
             (cles[1], json_octets(r.manifeste(extra)), "application/json")]
    if len(corps) != len(cles):
        raise Abort(
            f"{len(cles)} clés pour {len(corps)} corps. ⛔ Les deux listes "
            f"ne se correspondent plus — écrire quand même ferait partir "
            f"des octets sous le nom d'un autre objet.")

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
                    f"un run dépareillé.")
            try:
                _ecrire_index(st, r.run, ecrites, avancer=False,
                              journal=journal, maintenant=maintenant)
            except Exception as e:                         # noqa: BLE001
                journal(f"  ⛔ …et l'index n'a pas pu être mis à jour "
                        f"({type(e).__name__}: {e}) : {len(ecrites)} objet(s) "
                        f"HORS INDEX, donc invisibles. À supprimer à la main.")
        raise
    journal(f"  ✅ run écrit : {PREFIXE}{r.run}/ "
            f"({r.octets_publies() / 1e6:.1f} Mo, {len(corps)} objets)")
    _ecrire_index(st, r.run, [c for c, _, _ in corps], avancer=True,
                  journal=journal, maintenant=maintenant)
    return cles


def run_en_ligne(st):
    """Le run LISIBLE, par `dernier.run` — et JAMAIS par `runs`.

    ⛔ `runs` peut contenir un run à moitié publié (c'est même sa raison
    d'être : la purge doit le connaître). Le lire pour choisir quoi
    servir donnerait un `carte.bin` sans manifeste, une fois sur mille,
    et seulement les jours où l'écriture a échoué au milieu.
    """
    index = st.get_json(CLE_INDEX) or {}
    return (index.get("dernier") or {}).get(FLUX)
