#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/ingest_pi.py — étape 8 bis : l'ingestion d'AROME-PI
#                                                        (10/08/2026)
#
#  L'étape qui manquait à la séquence. Le poller DATE les runs PI depuis
#  ce matin ; personne ne les ARCHIVE. Sans ce fichier, l'étape 9 —
#  le composite temporel — n'a pas de matière première.
#
#  ── CE QUI DISTINGUE CETTE CHAÎNE DE CELLE D'AROME, EN UNE LIGNE ─────
#  AROME est limité par le RÉSEAU (7,4 Go, 2 requêtes) ; PI est limité
#  par le QUOTA (2,4 Mo, 300 requêtes). Ce ne sont pas les mêmes
#  contraintes, donc ce ne sont pas les mêmes machines :
#
#      produit A/B (AROME) → runner GitHub : bande passante, 14 Go de
#                            disque, 4 vCores, et AUCUNE clé.
#      PI (ce fichier)     → LE VPS : c'est là que vit la clé
#                            Météo-France, et elle n'en sort pas.
#
#  ⚠️ Ce n'est pas une préférence, c'est écrit dans le message d'erreur
#  de `portail.py` lui-même : « lancer les requêtes portail DEPUIS le
#  VPS, jamais en rapatriant la clé ».
#
#  ── LE BUDGET, MESURÉ — ET REMESURÉ LE 19/08 ─────────────────────────
#      2 paramètres × 6 niveaux × 25 échéances = 300 requêtes
#      → ~3,2 min (le quota, pas le réseau, fixe la durée)
#      × 24 runs/jour = 7 200 requêtes par jour
#
#  ⚠️ **Ce n'est pas le volume qui gêne, c'est l'OCCUPATION PERMANENTE
#  DU QUOTA.** À 95 requêtes/min utilisables, un run de PI occupe la
#  fenêtre 3 minutes sur 60. Le reste du temps elle est libre — mais si
#  un jour une autre chaîne veut le portail, c'est ici qu'il faudra
#  regarder en premier.
#
#  ⛔⛔ 19/08 (LOT M) — ET C'EST CETTE PHRASE-LÀ QUI A DÉCIDÉ DE
#  L'ARCHITECTURE À TROIS DOMAINES. Puisque la ressource rare est le
#  quota et non les octets, on ne demande PAS trois boîtes : on demande
#  leur ENGLOBANTE et on la recoupe. Mesuré sur le run 14 Z, run complet,
#  rien écrit :
#
#      3 boîtes séparées   926 requêtes   9,40 min   11,0 Mo
#      1 boîte englobante  304 requêtes   3,06 min   27,7 Mo
#
#  Les deux rendent les mêmes fenêtres après découpe (111×105 · 41×205 ·
#  34×84, 300 champs, aucun refus). Trois domaines coûtent donc
#  aujourd'hui **exactement le même quota qu'un seul** — et le chiffre
#  du paragraphe ci-dessus, 3 minutes sur 60, n'a pas bougé.
#
#  ⓘ Le poids par champ n'est plus celui de 2026-08-10 : la boîte
#  Nord-Alpes a doublé le 16/08 (5 185 → 11 655 colonnes), donc 17 662
#  octets par champ et non 7 957. L'englobante en fait 92 356.
#
#  ── L'ORDRE D'ÉCRITURE EST UN CONTRAT ────────────────────────────────
#  Les colonnes sont DÉFINITIVES, la grille est jetable. Les colonnes
#  s'écrivent donc d'ABORD, et un échec de la grille ne fait PAS échouer
#  le run : faire tomber le voyant pour un produit régénéré au réseau
#  suivant apprendrait à l'ignorer. Même contrat que `ingest_colonnes.py`.
#
#  Usage :
#      python3 agrume/ingest_pi.py                     # dernier run publié
#      python3 agrume/ingest_pi.py --run 2026-08-10T16:00:00Z
#      python3 agrume/ingest_pi.py --sans-ecriture --limite-champs 12
#      python3 agrume/ingest_pi.py --tke               # +50 % de requêtes
#      python3 agrume/ingest_pi.py --domaines-pi pyrenees --sans-ecriture
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

from quantification import balises_du_domaine  # noqa: E402
from domaine import (DOMAINES, DOMAINES_PI, GRID_3D,  # noqa: E402
                     boite_pi, domaine_de)
from freeze_balises import charger_artefact as charger_balises  # noqa: E402
from grille import (INDEX_VIDE, axes_depuis_orographie,  # noqa: E402
                    index_apres, index_apres_purge, verifier_prefixe)
from orographie import charger_artefacts, norm_lon  # noqa: E402
from pi import (CLE_INDEX_GRILLE, DOMAINE_INDEX_LEGS,  # noqa: E402
                ECHEANCES_MIN, NIVEAUX_PI, PREFIXE_GRILLE, RETENTION_RUNS,
                Abort, ColonnesPI, GrillePI,
                aligner_sur_axes, cles_du_run_colonnes, cles_du_run_grille,
                instants_du_run, json_octets, params_actifs)
from portail import (SERVICE_AROMEPI, CouvertureAbsente,  # noqa: E402
                     ErreurPortail, Portail)

# ⚠️ Alerte de durée. Le budget mesuré est de ~3,2 min ; à 12 min, ce
# n'est pas « un peu long », c'est que le quota est partagé avec autre
# chose ou que le portail rame. Un budget qu'on ne mesure pas n'est pas
# un budget.
ALERTE_MINUTES = 12

# ── Les codes de sortie, et ce qu'ils veulent dire pour le VOYANT ─────
#   0  un run a été ingéré ET écrit          → ping de succès
#   3  rien de neuf à ingérer                → aucun ping (cas nominal)
#   1  erreur, ou run explicite incomplet    → ping d'échec
#   78 fichier d'environnement illisible     → ping d'échec (dans le .sh)
# ⚠️ La distinction 0/3 est TOUT l'intérêt : sans elle, le voyant
# surveillerait « le timer tourne » au lieu de « l'archive grossit ».
CODE_RIEN_A_FAIRE = 3


def crier(msg=""):
    print(msg, flush=True)


# ══════════════════════════════════════════════════════════════════════
#  Décodage — la seule dépendance eccodes de la chaîne PI
# ══════════════════════════════════════════════════════════════════════
def lire_grib_2d(octets):
    """Un GRIB2 d'UN message → (champ 2D, meta). Lève sinon.

    ⚠️ On exige UN message et un seul. Le WCS ne peut de toute façon
    rendre qu'une couverture 2D (« Slicing on height/time is
    mandatory »), donc deux messages signifieraient que le serveur a
    changé de comportement — et prendre le premier en silence
    laisserait passer ce changement pendant des semaines.
    """
    from eccodes import (codes_get, codes_get_values,
                         codes_grib_new_from_file, codes_release)
    with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as f:
        f.write(octets)
        chemin = f.name
    try:
        with open(chemin, "rb") as f:
            gid = codes_grib_new_from_file(f)
            if gid is None:
                raise Abort("GRIB sans message — le portail a répondu 200 "
                            "avec un corps qui n'est pas un GRIB")
            try:
                meta = dict(
                    Ni=codes_get(gid, "Ni"), Nj=codes_get(gid, "Nj"),
                    lat0=codes_get(gid, "latitudeOfFirstGridPointInDegrees"),
                    lon0=norm_lon(codes_get(
                        gid, "longitudeOfFirstGridPointInDegrees")),
                    di=codes_get(gid, "iDirectionIncrementInDegrees"),
                    dj=codes_get(gid, "jDirectionIncrementInDegrees"),
                    jScan=codes_get(gid, "jScansPositively"))
                vals = codes_get_values(gid).reshape(meta["Nj"], meta["Ni"])
            finally:
                codes_release(gid)
            if codes_grib_new_from_file(f) is not None:
                raise Abort("le GetCoverage a rendu PLUSIEURS messages — le "
                            "serveur a changé de comportement, ne pas "
                            "prendre le premier en silence")
        return vals.astype(np.float64), meta
    finally:
        os.unlink(chemin)


# ══════════════════════════════════════════════════════════════════════
#  Détection du run
# ══════════════════════════════════════════════════════════════════════
def run_complet(portail, champ, run, niveau_sonde=100):
    """⚠️⚠️ LE RUN EST-IL COMPLET, ET PAS SEULEMENT « PUBLIÉ » ?

    **MESURÉ LE 10/08, ET C'EST LE DÉFAUT QUI A FAILLI PASSER.** À
    17:23:51 UTC, le run `2026-08-10T17:00:00Z` répondait au
    `DescribeCoverage` — donc « publié » — et servait ses échéances 0 et
    90 min. **Les échéances 180, 270 et 360 min n'existaient pas.** Les
    runs 16 Z et 15 Z, eux, étaient complets sur les cinq sondes.

    Mieux : en ingérant ce run 17 Z, le compte de champs obtenus MONTAIT
    d'un niveau à l'autre — 6, 6, 6, 6, 8, 8, 8, 9. **PI publie ses
    échéances au fil de l'eau**, à peu près une toutes les 40 s, et
    l'ingestion courait après.

    Conséquences, dans l'ordre de gravité :
    ⛔ Les colonnes sont **DÉFINITIVES**. Archiver un run à 24 %, écrire
       son entrée dans l'index et passer au suivant, c'est perdre 76 %
       d'un run pour toujours — la rétention du portail est de 4,25 jours.
    ⛔ Et le produit serait **DENTELÉ, pas seulement tronqué** : les
       niveaux ingérés en premier auraient moins d'échéances que les
       derniers. Un trou franc se voit ; un trou en escalier ressemble à
       de la donnée.
    ⚠️ Accessoirement, chaque échéance absente coûte quand même une
       requête : 228 requêtes de quota brûlées pour rien.

    On sonde donc **la DERNIÈRE échéance**, celle qui arrive en dernier.
    Une requête de 8 ko décide de 300.

    ⓘ C'est mot pour mot ce que `covered_steps()` fait pour AROME sur le
    miroir S3, et ce que le poller applique déjà : « le dispatch n'a lieu
    que quand TOUS les paquets sont là ». Le portail n'a pas de listing,
    donc on sonde au lieu de lister.
    """
    dernier = instants_du_run(run)[-1]
    try:
        # ⚠️ On sonde LA BOÎTE QU'ON DEMANDERA, pas une plus petite. Une
        # sonde sur une boîte réduite rendrait « complet » un run que la
        # vraie requête refuserait — et depuis le Lot M la boîte demandée
        # n'est plus celle d'aucun domaine, c'est leur englobante.
        portail.get_coverage(champ, run, dernier, niveau_sonde, boite_pi())
        return True
    except (ErreurPortail, CouvertureAbsente):
        return False


def dernier_run_utile(portail, champ, deja=(), maintenant=None, recul_max=8,
                      journal=crier):
    """Le run le plus récent qui soit COMPLET et pas déjà archivé.

    Renvoie `(run, recul)`, ou `(None, None)` s'il n'y a rien à faire.

    ⚠️ PI tourne TOUTES LES HEURES (24 runs/jour contre 8 pour AROME) et
    aucune heure de mise à disposition n'est codée en dur — la doc se
    contredit elle-même et ne dit même pas si ses heures sont UTC ou
    légales. On redescend heure par heure.

    ⚠️ On s'arrête au premier run DÉJÀ ARCHIVÉ : tout ce qui est plus
    ancien l'est aussi, et continuer coûterait du quota pour rien.

    ⚠️ `valider_champ` est appelé AVANT par l'appelant : sans lui, un nom
    de champ faux rendrait exactement le même `NoSuchCoverage` qu'un run
    absent, et cette boucle conclurait « rien n'est publié » pour
    toujours.
    """
    t = (maintenant or dt.datetime.now(dt.timezone.utc)).replace(
        minute=0, second=0, microsecond=0)
    for recul in range(recul_max):
        run = (t - dt.timedelta(hours=recul)).strftime("%Y-%m-%dT%H:00:00Z")
        if run in deja:
            journal(f"  ⓘ {run} est déjà archivé — rien de plus récent à "
                    f"prendre.")
            return None, None
        if not portail.existe(champ, run):
            continue
        if not run_complet(portail, champ, run):
            # ⓘ Ce n'est PAS une anomalie : c'est le cas NORMAL dans la
            # première demi-heure d'un run. On le journalise quand même,
            # parce que c'est la mesure de la latence de complétion — et
            # que si ça durait une heure, il faudrait le savoir.
            journal(f"  ⏳ {run} est publié mais INCOMPLET (la dernière "
                    f"échéance manque) — on regarde le précédent.")
            continue
        return run, recul
    raise Abort(f"aucun run PI COMPLET dans les {recul_max} dernières heures. "
                f"⚠️ Si le champ vient d'être validé, ce n'est PAS un nom "
                f"faux : c'est le portail ou la chaîne PI qui est muette.")


# ══════════════════════════════════════════════════════════════════════
#  Le corps
# ══════════════════════════════════════════════════════════════════════
class Cadre:
    """Une fenêtre de domaine : ses axes, son sol, sa grille en cours.

    ⛔ Elle existe pour qu'un (j, i) ne circule JAMAIS sans le domaine
    auquel il se rapporte. Depuis le Lot M il y a trois fenêtres et un
    seul GRIB : un couple d'indices seul ne veut plus rien dire.
    """

    def __init__(self, nom, orog, run, params):
        self.nom = nom
        self.orog = orog
        self.lats, self.lons = axes_depuis_orographie(orog,
                                                      domaine=DOMAINES[nom])
        self.grille = GrillePI(run, params, self.lats, self.lons, orog.z,
                               domaine=nom)

    @property
    def points(self):
        return len(self.lats) * len(self.lons)


def cadres_des_domaines(run, params, noms=None, journal=crier):
    """Un `Cadre` par domaine PI dont l'orographie est GELÉE.

    ⚠️ Un domaine sans artefact est CRIÉ et SAUTÉ, jamais fatal — même
    règle que `charger_artefacts()`, et pour la même raison mesurée : le
    gel se lance à la main APRÈS le commit qui ajoute le domaine, et
    faire échouer tous les runs entre les deux punirait les domaines qui
    n'ont rien demandé. Le manifeste du run dit qui a réellement servi.
    ⛔ Nord-Alpes reste obligatoire : sans lui il n'y a pas de produit.
    """
    noms = list(DOMAINES_PI if noms is None else noms)
    arts, absents = charger_artefacts(noms, obligatoires=("nord-alpes",))
    if absents:
        journal(f"  ⚠️ orographie NON GELÉE pour {absents} — ces domaines "
                f"ne seront PAS ingérés ce run (lancer "
                f"`freeze_orographie.py` puis relancer)")
    cadres = {}
    for nom in noms:
        if nom not in arts:
            continue
        paire, man = arts[nom]
        cadres[nom] = Cadre(nom, paire[GRID_3D], run, params)
        journal(f"  {nom} : fenêtre {len(cadres[nom].lats)} × "
                f"{len(cadres[nom].lons)} = {cadres[nom].points} points "
                f"· orographie du run {man['run_source']}")
    if not cadres:
        raise Abort("aucun domaine PI n'a son orographie gelée")
    return cadres


def repartir_balises(balises, cadres, journal=crier):
    """(ji, domaines) — où chaque balise tombe, et DANS QUELLE fenêtre.

    ⛔⛔ LE DOMAINE SE DEMANDE À `domaine_de()`, PAS À LA PREMIÈRE
    FENÊTRE QUI RÉPOND. Les trois orographies sont découpées sur la
    grille NATIVE et `Orographie.indices()` rend un couple dès que le
    point tombe dans SA découpe — or `fenetre()` arrondit au point de
    grille, donc une balise posée à moins d'une demi-maille du bord d'un
    domaine peut tomber dans DEUX découpes (le cas mesuré le 12/08 :
    balise 1661/LFMG, 43,4069 N pour un `latmax` de 43,40). Prendre « la
    première qui répond » ferait dépendre le domaine servi de l'ordre
    d'un dictionnaire — exactement ce que
    `verifier_domaines_disjoints()` refuse de laisser au hasard.

    ⓘ Une balise dont le domaine n'est PAS ingéré (orographie non gelée,
    ou domaine hors `DOMAINES_PI`) sort avec `None` : sa colonne restera
    NaN et le manifeste le dira. C'est ce que « 207 servies sur 288 »
    voulait dire avant ce lot.
    """
    ji, doms = [], []
    par_domaine = {}
    for b in balises:
        nom = domaine_de(b["lat"], b["lon"])
        cadre = cadres.get(nom)
        x = cadre.orog.indices(b["lat"], b["lon"]) if cadre else None
        if x is None:
            ji.append(None)
            doms.append(None)
        else:
            ji.append(x)
            doms.append(nom)
            par_domaine[nom] = par_domaine.get(nom, 0) + 1
    hors = [b["id"] for b, x in zip(balises, ji) if x is None]
    journal(f"  balises servies : "
            + " · ".join(f"{n} {c}" for n, c in sorted(par_domaine.items()))
            + f" · hors fenêtre {len(hors)} (sur {len(balises)})")
    return ji, doms, hors, par_domaine


def ingerer(run, params, cadres, balises, portail, limite_champs=None,
            journal=crier):
    """Remplit les produits. Renvoie (colonnes, cadres, bilan).

    ⛔⛔ UNE REQUÊTE, TROIS DÉCOUPES — arbitrage A13 du 19/08, et il a
    été MESURÉ avant d'être écrit. Demander les trois boîtes séparément
    coûtait 926 requêtes et 9,40 min ; demander leur englobante en coûte
    304 et 3,06 min, et rend les MÊMES fenêtres après découpe (111×105,
    41×205, 34×84, sur les 300 champs, sans un refus). La ressource rare
    de cette chaîne est le quota, pas la bande passante : c'est écrit en
    tête de ce fichier depuis le 10/08.

    ⚠️ Ce qui est en trop dans l'englobante — 63 % de ses colonnes — est
    jeté à la découpe, dans la même seconde (0,5 s pour 300 champs). Rien
    de mort n'est écrit nulle part.
    """
    boite = boite_pi(list(cadres))
    ji, doms, hors, par_domaine = repartir_balises(balises, cadres,
                                                   journal=journal)
    colonnes = ColonnesPI(run, params, balises, ji, domaines=doms)

    journal(f"  boîte demandée au portail : lat {boite['latmin']:.2f}→"
            f"{boite['latmax']:.2f} · long {boite['lonmin']:.2f}→"
            f"{boite['lonmax']:.2f} (englobante de {len(cadres)} domaines, "
            f"élargie d'un pas de grille)")

    instants = instants_du_run(run)
    attendus = len(params) * len(NIVEAUX_PI) * len(ECHEANCES_MIN)
    journal(f"  {attendus} champs à demander "
            f"({len(params)} paramètres × {len(NIVEAUX_PI)} niveaux × "
            f"{len(ECHEANCES_MIN)} échéances) — pour {len(cadres)} domaines")

    def decouper_et_poser(param, niveau, minute, champ, meta):
        """⛔ TOUT OU RIEN. Si UNE découpe refuse, le champ entier est
        compté manquant et AUCUN domaine ne le reçoit.

        Un champ posé sur deux domaines et absent du troisième donnerait
        un produit DENTELÉ — et un trou en escalier ressemble à de la
        donnée, alors qu'un trou franc se voit. C'est mot pour mot la
        leçon du run 17 Z du 10/08.
        """
        alignes = {}
        for nom, cadre in cadres.items():
            alignes[nom] = aligner_sur_axes(champ, meta, cadre.lats,
                                            cadre.lons)
        for nom, cadre in cadres.items():
            cadre.grille.poser(param, niveau, minute, alignes[nom])
            colonnes.poser_depuis_champ(param, niveau, minute, alignes[nom],
                                        domaine=nom)

    faits = 0
    t0 = time.monotonic()
    for param in params:
        axe = portail.axe_vertical(param["wcs"], run)
        for niveau in NIVEAUX_PI:
            for minute, instant in zip(ECHEANCES_MIN, instants):
                if limite_champs is not None and faits >= limite_champs:
                    journal(f"  ⓘ arrêt sur --limite-champs={limite_champs}")
                    return colonnes, cadres, _bilan(t0, faits, attendus, hors,
                                                    cadres, par_domaine)
                try:
                    octets = portail.get_coverage(
                        param["wcs"], run, instant, niveau, boite, axe=axe)
                    champ, meta = lire_grib_2d(octets)
                    decouper_et_poser(param, niveau, minute, champ, meta)
                except (ErreurPortail, CouvertureAbsente, Abort) as e:
                    # ⚠️ UN CHAMP MANQUANT DOIT DISPARAÎTRE, PAS ÊTRE
                    # COMBLÉ. On le note et on continue : c'est exactement
                    # ce qui arrivera au 10 m si PI ne le sert pas, et le
                    # manifeste doit dire lequel manque plutôt que de
                    # publier une valeur inventée.
                    colonnes.manquants.append(
                        dict(param=param["nom"], niveau=niveau, minute=minute,
                             cause=f"{type(e).__name__}: {e}"[:200]))
                    continue
                faits += 1
            journal(f"    {param['nom']} · {niveau:>4} m : "
                    f"{faits}/{attendus} champs "
                    f"({time.monotonic() - t0:.0f} s)")
    # ── ⚠️⚠️ LA SECONDE PASSE — ET ELLE VIENT D'UN VRAI TROU ──────────
    # Le premier run écrit sur R2 a rendu **297 champs sur 300** : trois
    # `HTTP 502 Bad Gateway`, à trois niveaux et trois échéances sans
    # rapport (v/50 m/360 min, v/100 m/240 min, v/250 m/225 min). Les
    # quatre tentatives internes de `_http` ne s'appliquaient pas au 502,
    # traité comme définitif — c'est corrigé dans `portail.py`.
    #
    # ⛔ Mais un retry immédiat ne suffit pas à lui seul : les colonnes
    # sont DÉFINITIVES, et un trou y est permanent — la rétention du
    # portail est de 4,25 jours. On repasse donc sur les manquants À LA
    # FIN, c'est-à-dire une à trois minutes plus tard, ce qui laisse le
    # temps à un hoquet de passerelle de se dissiper.
    #
    # ⓘ Le coût est proportionnel aux trous, pas au run : trois requêtes
    # pour trois manquants. Sur un run parfait, cette passe ne coûte rien.
    # ⚠️ 19/08 — ET ELLE EN VAUT TROIS FOIS PLUS DEPUIS LE LOT M : un
    # champ récupéré ici l'est pour les TROIS domaines à la fois.
    #
    # ⚠️ ON ÉCRIT QUAND MÊME S'IL EN RESTE. Refuser d'écrire perdrait le
    # run ENTIER : `dernier_run_utile()` s'arrête au premier run archivé,
    # donc un run sauté ne serait jamais repris une fois le suivant écrit.
    # Entre 1 % de trous DÉCLARÉS dans le manifeste et 100 % de perte
    # silencieuse, le choix se fait sans hésiter.
    if colonnes.manquants:
        restants, reussis = [], 0
        journal(f"  ⟳ seconde passe sur {len(colonnes.manquants)} champs "
                f"manquants")
        for m in colonnes.manquants:
            param = next(p for p in params if p["nom"] == m["param"])
            k = ECHEANCES_MIN.index(m["minute"])
            try:
                octets = portail.get_coverage(
                    param["wcs"], run, instants[k], m["niveau"], boite)
                champ, meta = lire_grib_2d(octets)
                decouper_et_poser(param, m["niveau"], m["minute"], champ, meta)
            except (ErreurPortail, CouvertureAbsente, Abort) as e:
                m["cause_2"] = f"{type(e).__name__}: {e}"[:200]
                restants.append(m)
                continue
            faits += 1
            reussis += 1
        colonnes.manquants = restants
        journal(f"  ⟳ {reussis} récupérés, {len(restants)} définitivement "
                f"manquants")

    for cadre in cadres.values():
        cadre.grille.manquants = colonnes.manquants
    return colonnes, cadres, _bilan(t0, faits, attendus, hors, cadres,
                                    par_domaine)


def _bilan(t0, faits, attendus, hors, cadres, par_domaine):
    return dict(secondes=round(time.monotonic() - t0, 1), champs=faits,
                champs_attendus=attendus, balises_hors_fenetre=hors,
                # ⛔ QUI A RÉELLEMENT SERVI. Le manifeste doit le DIRE et
                # non le laisser déduire d'une absence : un domaine sauté
                # faute d'orographie gelée et un domaine vide faute de
                # données ne se réparent pas pareil.
                domaines_ingeres=sorted(cadres),
                balises_par_domaine=dict(sorted(par_domaine.items())),
                boite_demandee={k: round(v, 4)
                                for k, v in boite_pi(list(cadres)).items()})


# ══════════════════════════════════════════════════════════════════════
#  Écriture
# ══════════════════════════════════════════════════════════════════════
def ecrire(colonnes, cadres, bilan, journal=crier):
    """Colonnes d'abord (définitif), grilles ensuite (sous filet), purge.

    ⚠️ L'ordre EST le contrat. Une grille qui échoue laisse le run VERT ;
    des colonnes qui échouent le font tomber.

    ⛔ ET IL Y A UNE ARCHIVE DE COLONNES POUR N GRILLES. L'axe des
    balises est unique (les trois domaines y sont depuis toujours, cf.
    `cles_du_run_colonnes`) ; les fenêtres, elles, sont trois. Écrire
    trois archives de colonnes couperait en trois un axe qui n'a pas de
    couture.
    """
    from storage import Storage

    st = Storage("agrume-pi", "AGRUME_BUCKET", "wind-grid")

    # ── 1. Colonnes — DÉFINITIF ───────────────────────────────────────
    c_npz, c_man = cles_du_run_colonnes(colonnes.run)
    extra = dict(bilan=bilan, manquants=colonnes.manquants[:50],
                 nb_manquants=len(colonnes.manquants),
                 # ⓘ La réponse à la question laissée ouverte par la note
                 # d'étape 9 : PI sert-il u/v à 10 m ? Mesurée, pas
                 # supposée.
                 niveau_10m_servi=bool(
                     colonnes.remplissage_par_niveau().get(10, 0) > 0))
    st.put(c_npz, colonnes.npz(), cache_control="public, max-age=31536000",
           content_type="application/octet-stream")
    st.put(c_man, json_octets(colonnes.manifeste(extra)),
           cache_control="public, max-age=31536000",
           content_type="application/json")
    journal(f"  ✅ colonnes écrites : {c_npz} ({colonnes.octets() / 1024:.0f} ko)")

    # ── 2. Grilles — JETABLES, chacune sous son filet ─────────────────
    # ⚠️ UN `except` PAR DOMAINE, et non un pour les trois : une grille
    # pyrénéenne qui échoue ne doit pas empêcher la grille alpine d'être
    # écrite. Elles ne dépendent d'aucune façon les unes des autres — le
    # seul couplage entre domaines, c'est la requête, et elle a déjà
    # rendu ses octets à ce stade.
    ecrites = {}
    for nom, cadre in cadres.items():
        try:
            g_npz, g_man = cles_du_run_grille(cadre.grille.run, nom)
            st.put(g_npz, cadre.grille.npz(),
                   cache_control="public, max-age=3600",
                   content_type="application/octet-stream")
            st.put(g_man, json_octets(cadre.grille.manifeste(dict(bilan=bilan))),
                   cache_control="public, max-age=3600",
                   content_type="application/json")
            ecrites[nom] = [g_npz, g_man]
            journal(f"  ✅ grille écrite : {g_npz} "
                    f"({cadre.grille.octets() / 1e6:.1f} Mo en mémoire)")
        except Exception as e:                               # noqa: BLE001
            journal(f"  ⚠️ grille {nom} NON écrite ({type(e).__name__}: {e}) "
                    f"— le run reste VERT : elle est régénérée au réseau "
                    f"suivant, l'archive des colonnes ne l'est pas.")

    # ── 3. La purge, UNE FOIS pour tous les domaines ──────────────────
    if ecrites:
        try:
            purger(st, colonnes.run, ecrites, journal=journal)
        except Exception as e:                               # noqa: BLE001
            journal(f"  ⚠️ purge NON faite ({type(e).__name__}: {e}) — les "
                    f"grilles sont écrites et indexées au prochain run.")

    # ── 4. Rafraîchissement du produit B — JETABLE, sous filet ────────
    # ⛔ APRÈS les grilles, et sous `except`, exactement comme elles. À ce
    # point les grilles PI sont écrites et hors de danger ; un
    # rafraîchissement raté ne doit donc PAS faire tomber le voyant —
    # le prochain run PI repasse dans une heure et refera l'objet.
    #
    # ⚠️⚠️ MAIS IL DOIT CRIER, et fort. Ce que ce bloc publie n'est pas
    # un supplément : c'est la couche que le client PRÉFÉRERA au produit
    # B pour `u`/`v` sur 0–6 h. S'il cesse de s'écrire, l'écran ne
    # cassera pas — il redeviendra silencieusement horaire, ce que
    # personne ne remarquera. Un échec muet ici est exactement le « faux
    # vert » que ce projet a déjà eu deux fois.
    #
    # ⛔ UN PAR DOMAINE, ET CHACUN SON `except` — même raison que les
    # grilles. Un produit B pyrénéen absent (ingestion AROME en retard)
    # ferait tomber la composition pyrénéenne et ELLE SEULE ; les Alpes
    # n'ont pas à en pâtir.
    #
    # ⓘ Il ne touche NI au produit A, NI aux tampons du produit B : il
    # écrit sous `agrume/pi/rafraichissement/{domaine}/`, son propre index
    # et sa propre rétention. Rien de ce qui nourrit le scoring ne bouge.
    for nom, cadre in cadres.items():
        if nom not in ecrites:
            continue
        try:
            from rafraichissement import rafraichir            # noqa: PLC0415
            g = cadre.grille
            i_u, i_v = g.i_param["u"], g.i_param["v"]
            raf = rafraichir(g.donnees[[i_u, i_v]], g.lats, g.lons, g.run,
                             domaine=nom, st=st, extra=dict(bilan=bilan),
                             journal=journal)
            journal(f"  ✅ rafraîchissement {nom} : composite {raf.run_pi} × "
                    f"produit B {raf.run_b} (décalage "
                    f"{raf.decalage_min // 60} h, échéances AROME "
                    f"{raf.steps_b[0]}–{raf.steps_b[-1]})")
        except Exception as e:                                 # noqa: BLE001
            journal(f"  ⚠️⚠️ RAFRAÎCHISSEMENT {nom} NON ÉCRIT "
                    f"({type(e).__name__}: {e}) — le run reste VERT (la "
                    f"grille PI, elle, est écrite), mais le client servira "
                    f"de l'AROME HORAIRE sur 0–6 h pour {nom} jusqu'au "
                    f"prochain run PI. Si cette ligne revient d'heure en "
                    f"heure, ce n'est plus un incident.")

    st.bilan(log=journal)


def _migrer_index_legs(index, journal=crier):
    """⛔ LES ENTRÉES `domaine: "pi"` DE L'AVANT-LOT-M PARTENT À LA PURGE.

    Elles pointent sur `agrume/pi/grille/{run}/…`, un chemin que plus
    personne n'écrit depuis que le domaine est dans la clé. Laissées
    telles quelles, elles ne seraient JAMAIS purgées : leur compteur de
    rétention ne recevrait plus de nouvelle entrée, donc elles resteraient
    éternellement sous le seuil de 3, et les octets resteraient facturés
    et invisibles (`ListObjects` est hors de portée du jeton ordinaire).
    Même traitement que les entrées SANS domaine, pour la même raison,
    écrite dans `grille.index_apres` : « un objet qui sort de l'index
    devient invisible et définitivement perdu — une fuite, pas un
    déchet ».
    """
    entrees = list((index or {}).get("runs") or [])
    legs = [e for e in entrees if e.get("domaine") == DOMAINE_INDEX_LEGS]
    if not legs:
        return index
    restes = list((index or {}).get("restes") or [])
    for e in legs:
        restes.extend(e.get("cles") or [])
    journal(f"  ⟳ migration Lot M : {len(legs)} entrée(s) d'index au nom "
            f"{DOMAINE_INDEX_LEGS!r} (avant le domaine dans la clé) → purge")
    return dict(index, runs=[e for e in entrees
                             if e.get("domaine") != DOMAINE_INDEX_LEGS],
                restes=restes)


def purger(st, run, cles_par_domaine, journal=crier):
    """Index d'abord, suppression ensuite. ⚠️ L'ordre évite les orphelins
    invisibles — c'est la démonstration du §« purge » de `grille.py`, et
    elle s'applique mot pour mot ici.

    ⛔ UNE SEULE LECTURE ET UNE SEULE ÉCRITURE D'INDEX POUR N DOMAINES.
    `index_apres` se chaîne : son `restes` de sortie est le point de
    départ du `a_supprimer` de l'appel suivant. Écrire l'index entre
    chaque domaine coûterait des opérations Class A pour rien, et
    laisserait surtout des états intermédiaires où un domaine est indexé
    et pas les autres.
    """
    index = st.get_json(CLE_INDEX_GRILLE) or dict(
        INDEX_VIDE, produit="AGRUME PI — index des grilles en ligne",
        retention_runs=RETENTION_RUNS, runs=[], restes=[])
    index = _migrer_index_legs(index, journal=journal)
    a_supprimer = []
    for domaine, cles in sorted(cles_par_domaine.items()):
        # ⚠️ `domaine` n'est pas décoratif : sans lui, `cles` atterrit
        # dans le paramètre `domaine` et l'appel lève un `TypeError` — ce
        # qui s'est produit à chaque run du 12 au 13/08, en laissant des
        # grilles hors index.
        index, a_supprimer = index_apres(index, run, domaine, cles,
                                         retention=RETENTION_RUNS)
    # ⚠️ LE GARDE-FOU QUI EMPÊCHE LA PURGE DE DÉBORDER : les colonnes PI
    # sont DÉFINITIVES et vivent dans le même bucket, sous
    # `agrume/pi/colonnes/`. Une purge qui s'y égarerait détruirait une
    # archive irremplaçable — la rétention du portail est de 4,25 jours.
    verifier_prefixe(a_supprimer, prefixe=PREFIXE_GRILLE)
    st.put(CLE_INDEX_GRILLE, json_octets(index),
           cache_control="no-store", content_type="application/json")
    echecs = []
    for cle in a_supprimer:
        try:
            st.delete(cle)
        except Exception:                                    # noqa: BLE001
            echecs.append(cle)
    if a_supprimer:
        journal(f"  purge : {len(a_supprimer) - len(echecs)} clés supprimées"
                + (f", {len(echecs)} échecs (réessayés au run suivant)"
                   if echecs else ""))
        st.put(CLE_INDEX_GRILLE, json_octets(index_apres_purge(index, echecs)),
               cache_control="no-store", content_type="application/json")


def runs_archives():
    """Les runs déjà en ligne, lus dans l'INDEX.

    ⚠️ L'index ne connaît que les runs encore SOUS RÉTENTION (3). Un run
    de plus de 3 heures en est sorti — mais `dernier_run_utile()` ne
    remonte jamais assez loin pour le rencontrer, et le raccourci s'arrête
    au premier run archivé de toute façon. ⓘ Si la rétention descendait
    à 1, il faudrait un second index pour les colonnes définitives.
    """
    from storage import Storage
    st = Storage("agrume-pi", "AGRUME_BUCKET", "wind-grid")
    index = st.get_json(CLE_INDEX_GRILLE) or {}
    return {e.get("run") for e in (index.get("runs") or []) if e.get("run")}


# ══════════════════════════════════════════════════════════════════════
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", default=None,
                   help="run PI visé (ex. 2026-08-10T16:00:00Z) ; "
                        "par défaut le dernier publié")
    p.add_argument("--tke", action="store_true",
                   help="ajoute la TKE : +50 %% de requêtes, inutile à "
                        "l'étape 9, utile au §5.2.c (rotor, rabattant)")
    p.add_argument("--sans-ecriture", action="store_true",
                   help="tout faire sauf écrire sur R2")
    p.add_argument("--limite-champs", type=int, default=None,
                   help="s'arrêter après N champs (mise au point)")
    p.add_argument("--forcer", action="store_true",
                   help="réingérer même si le run est déjà dans l'index")
    p.add_argument("--stations", default=None,
                   help="chemin du stations.json (défaut : artefact figé)")
    p.add_argument("--domaines-pi", default=None,
                   type=lambda x: [n.strip() for n in x.split(",") if n.strip()],
                   help="restreindre les domaines ingérés (défaut : "
                        "DOMAINES_PI). ⚠️ Ne change PAS ce que le manifeste "
                        "du produit B annonce : c'est `DOMAINES_PI` qui "
                        "fait foi à l'écran, pas cette option de mise au "
                        "point.")
    p.add_argument("--suspectes", default=None,
                   help="JSON des identifiants à position suspecte — "
                        "⚠️ MARQUÉS dans l'archive, jamais retirés")
    a = p.parse_args(argv)

    debut = time.monotonic()
    params = params_actifs(a.tke)
    crier(f"AGRUME PI — étape 8 bis · {len(params)} paramètres "
          f"({', '.join(x['nom'] for x in params)})")

    # ── Ce qui est déjà archivé, lu UNE fois ──────────────────────────
    # ⚠️ Par l'INDEX, jamais par `exists` : `HeadObject` et `ListObjects`
    # sont facturés Class A chez R2, et `storage.py::_R2.exists` lève
    # plutôt que de les laisser passer. Le timer repasse toutes les 10
    # min ; sonder par `exists` coûterait 144 opérations Class A par jour
    # pour une réponse que l'index donne en une lecture Class B.
    deja = set() if (a.forcer or a.sans_ecriture) else runs_archives()

    portail = Portail(SERVICE_AROMEPI, "0025", journal=lambda m: crier(f"   {m}"))

    # ⚠️ VALIDER LE CHAMP AVANT DE CHERCHER LE RUN. Sans ça, un nom de
    # champ faux et un run non publié rendent EXACTEMENT la même chose —
    # HTTP 404, `NoSuchCoverage` — et la boucle de détection conclurait
    # « rien n'est publié » en attendant pour toujours.
    hier = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    temoins = [(hier + dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:00:00Z")
               for h in (0, 1, 2)]
    for param in params:
        portail.valider_champ(param["wcs"], temoins)
    crier(f"  ✅ {len(params)} champs validés sur un run témoin")

    if a.run:
        run, recul = a.run, None
        # ⚠️ Même forcé à la main, on vérifie la complétude : archiver un
        # run partiel dans une archive DÉFINITIVE est irréversible.
        if not a.forcer and not run_complet(portail, params[0]["wcs"], run):
            crier(f"  ⛔ {run} est publié mais INCOMPLET — refusé. "
                  f"`--forcer` passe outre, en connaissance de cause.")
            return 1
    else:
        run, recul = dernier_run_utile(portail, params[0]["wcs"], deja=deja)
        if run is None:
            crier(f"  {portail.bilan()}")
            # ⚠️ 3 et non 0 : « rien à faire » n'est PAS un succès à
            # signaler. Le timer repasse toutes les 10 min et PI ne sort
            # qu'une fois par heure — cinq passages sur six tombent ici.
            # Si le voyant pinguait au vert à chaque passage, il resterait
            # vert pendant que la chaîne aurait cessé d'écrire depuis des
            # jours. C'est le faux vert que ce projet a déjà eu deux fois.
            # `run-ingest-pi.sh` ne pingue donc RIEN sur ce code.
            return CODE_RIEN_A_FAIRE
    crier(f"  run retenu : {run}"
          + (f" (COMPLET, {recul} h de recul)" if recul is not None else ""))

    # ⚠️ `charger_artefacts()` rend la PAIRE d'orographies (0,01° et
    # 0,025°) PAR DOMAINE, pas une seule. PI vit en 0,025° et rien
    # d'autre : prendre la mauvaise décalerait toute la colonne
    # verticalement, en silence, de 30 m en médiane et jusqu'à 643 m
    # (19 % des balises au-delà de 100 m — mesuré le 10/08).
    crier(f"  domaines PI : {', '.join(DOMAINES_PI)}")
    cadres = cadres_des_domaines(run, params, noms=a.domaines_pi)

    suspectes = (json.loads(Path(a.suspectes).read_text(encoding="utf-8"))
                 if a.suspectes else [])
    if a.stations:
        stations = json.loads(Path(a.stations).read_text(encoding="utf-8"))
        balises = balises_du_domaine(stations, suspectes)
        origine = f"référentiel {Path(a.stations).name}"
    else:
        figees, man_bal = charger_balises()
        balises = balises_du_domaine(figees, suspectes)
        origine = f"axe figé du {man_bal['ecrit_le'][:10]}"
    if not balises:
        raise Abort("aucune balise ne tombe dans aucun domaine de "
                    "production — l'axe de l'archive serait vide")
    marquees = sum(1 for b in balises if b["position_suspecte"])
    crier(f"  {len(balises)} balises — {origine}"
          + (f", dont {marquees} à position suspecte (marquées, pas "
             f"retirées)" if marquees else ""))

    colonnes, cadres, bilan = ingerer(run, params, cadres, balises, portail,
                                      limite_champs=a.limite_champs)

    crier()
    crier(f"  champs obtenus : {bilan['champs']}/{bilan['champs_attendus']}")
    crier(f"  remplissage par paramètre : {colonnes.remplissage_par_parametre()}")
    crier(f"  remplissage par niveau    : {colonnes.remplissage_par_niveau()}")
    if colonnes.manquants:
        vus = sorted({(m["param"], m["niveau"]) for m in colonnes.manquants})
        crier(f"  ⚠️ {len(colonnes.manquants)} champs manquants, sur "
              f"{len(vus)} couples (paramètre, niveau) : {vus[:8]}")
    crier(f"  domaines ingérés : {bilan['domaines_ingeres']} · balises "
          f"servies par domaine : {bilan['balises_par_domaine']}")
    crier(f"  {portail.bilan()}")
    crier(f"  octets reçus : {portail.compteur['octets'] / 1e6:.2f} Mo")

    if a.sans_ecriture:
        crier("  ⓘ --sans-ecriture : rien n'a été écrit.")
    else:
        ecrire(colonnes, cadres, bilan)

    minutes = (time.monotonic() - debut) / 60
    crier(f"  durée totale : {minutes:.1f} min")
    if minutes > ALERTE_MINUTES:
        crier(f"  ⚠️ AU-DELÀ DE {ALERTE_MINUTES} min — le budget mesuré est "
              f"de 3,2 min. Ce n'est pas « un peu long », c'est que le "
              f"quota est partagé ou que le portail rame.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
