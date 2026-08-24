#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  quota_openmeteo.py — le droit de parler à Open-Meteo, partagé (09/08/2026)
#
#  ═══ CE QUE CE FICHIER RÉPARE, ET COMMENT ON LE SAIT ═══
#
#  Nuit du 09/08 : `bw-model-collect` tué par son chien de garde après
#  2 400 s. Le journal dit deux pannes, pas une, et les deux sont
#  mesurées — pas déduites.
#
#  1. LA MINUTE ÉTAIT FRANCHIE EN CONTINU. Entre deux marqueurs de 50
#     points, le run met 38 s : 0,76 s par point. La pause vaut 0,70 s,
#     donc la latence RÉELLE valait 0,06 s — et non les 0,22 s inscrites
#     dans `collect.py`. Cadence réelle 79 req/min × poids 8 = 631
#     pondérés/min, au-dessus des 600. D'où un 429 isolé toutes les
#     deux ou trois minutes, chacun rattrapé par la pause de 65 s.
#
#     ⚠️ C'est le défaut de fond : la cadence était réglée en BOUCLE
#     OUVERTE. On choisissait un délai en espérant une cadence, et
#     personne ne mesurait la cadence obtenue. Un réseau PLUS RAPIDE
#     faisait donc DÉPASSER le plafond. Ce n'était pas une hypothèse le
#     08/08 : c'est ce qui s'est produit le 09.
#
#  2. PUIS LE MUR, À 05:33:28. Plus un seul point ne passe : un 429
#     toutes les 68 s pendant 26 minutes, jusqu'au chien de garde. La
#     pause de 65 s ne rattrape plus rien, parce que ce n'est plus la
#     fenêtre de la minute qui bloque.
#
#     Le run a fini à « 5808 lignes, 23 points en échec ». 648 − 23 =
#     625 points collectés. 625 × 8 = **5 000 appels pondérés, à
#     l'unité près**. Le palier gratuit Open-Meteo compte 600/min,
#     **5 000/heure** et 10 000/jour — et `collect.py` ne modélisait que
#     la minute et le jour. L'heure n'existait nulle part dans le code.
#
#  Le 08/08 passait parce qu'il était encore à 5 variables : 3 240
#  pondérés, sous les 5 000. Le commit du 08/08 qui porte les variables
#  de 5 à 8 a franchi un plafond que rien ne surveillait, et l'a franchi
#  en silence.
#
#  ═══ LES TROIS ARBITRAGES, TRANCHÉS ICI ET PAS DANS UNE NOTE ═══
#
#  1. OÙ VIT LE BUDGET → un fichier JSON sous `/var/lib/bw-quota/`, pas
#     SQLite. La contention est faible (une seule machine, deux chaînes
#     programmées, trois scripts à la main), et un fichier se lit à
#     l'œil quand ça va mal. À 6 h du matin, `cat` vaut mieux qu'un
#     client SQL. `flock` suffit pour la concurrence.
#
#  2. QUE FAIT UN SCRIPT QUI N'A PAS SES JETONS → il attend, mais de
#     façon BORNÉE. Le chien de garde de la collecte vaut 40 min :
#     attendre sans limite la ferait mourir de la même mort qu'au 09/08,
#     en plus lent. Passé la borne, on abandonne le point et on DIT
#     combien de points n'ont pas été collectés. Un trou nommé vaut
#     mieux qu'un run tué.
#
#  3. LE BUDGET EST-IL PAR API OU GLOBAL → GLOBAL, un seul compteur pour
#     tous les hôtes `*.open-meteo.com`. Le plafond est par ADRESSE IP,
#     et tout le VPS en partage une. Séparer prévisions et archive
#     rendrait le compteur faux du côté qui ne protège pas.
#     ⚠️ Ce point reste le moins établi des trois : personne n'a mesuré
#     que les deux endpoints partagent bien le compteur. On prend
#     l'hypothèse la plus DÉFAVORABLE, comme `quota_projete` le fait
#     déjà depuis le 07/08 — un garde-fou qui se trompe doit se tromper
#     du côté qui protège.
#
#  ═══ CE QUE CE FICHIER NE PEUT PAS FAIRE ═══
#
#  ⚠️ AUCUNE CADENCE NE FAIT TENIR 5 184 PONDÉRÉS SOUS 5 000/HEURE.
#     À 8 variables × 10 modèles, le poids d'un point vaut 8, donc
#     l'heure autorise 625 points — et le référentiel en compte 648.
#     Le seau rend ce manque VISIBLE et NOMMÉ ; il ne le supprime pas.
#     Le supprimer est une décision de produit, pas de code : moins de
#     variables, moins de modèles, une passe étalée sur deux heures, ou
#     une clé payante. `quota_projete()` doit refuser de démarrer et
#     poser l'arithmétique, plutôt que de partir en espérant.
#
#  ═══ S0.7 (22/08/2026) — LE QUATRIÈME PLAFOND, 300 000/MOIS ═══
#
#  Le palier gratuit Open-Meteo compte une QUATRIÈME fenêtre, mensuelle,
#  confirmée verbatim sur sa page de tarification le 22/08 : « 600 calls
#  / min, 5.000 calls / hour, 10.000 calls / day, 300.000 calls / month ».
#
#  ⛔ « L'AJOUTER À FENETRES EST UNE LIGNE » EST FAUX, ET L'ÉCRIRE DEUX
#  FOIS (S0.3) NE L'A PAS REND VRAI. Deux raisons, toutes deux mesurées :
#
#  1. `_reserver` élague à 86 400 s EN DUR (plus bas — CETTE LIGNE NE
#     BOUGE PAS dans ce lot). Ajouter ("mois", 2_592_000, 300_000) à
#     FENETRES SANS y toucher donnerait une fenêtre mensuelle qui ne
#     verrait JAMAIS plus de 24 h d'événements : elle compterait ~4 000
#     pondérés au lieu de ~122 000, et ne se déclencherait donc JAMAIS.
#     `TestVersionNaiveEstRouge` (banc) reproduit ce calcul et le prouve :
#     c'est la forme EXACTE du défaut du 09/08 — un garde-fou présent
#     qui ne garde rien, pire que son absence puisqu'on croirait le
#     plafond couvert.
#
#  2. Élargir l'élagage à 30 jours pour de vrai NE PASSE PAS À L'ÉCHELLE.
#     Mesuré sur le VPS le 22/08 à 12 h UTC : le fichier d'état pèse
#     40 367 octets pour 1 077 événements (37,5 octets/événement), relu
#     ET réécrit à CHAQUE `demander()` — 1 524 fois par nuit depuis le
#     S0.4 (2 requêtes × 657 points, plus `backfill_packs`). Élargir
#     l'élagage à 30 jours ferait grossir ce fichier à ~45 700
#     événements (~1,7 Mo), soit ~1,7 Mo lus + 1,7 Mo écrits × 1 524 —
#     environ 5 Go d'E/S par nuit, et un tri de 45 000 éléments × 4
#     fenêtres × 1 524 fois. Personne n'a demandé ce coût.
#
#  ═══ LA FORME RETENUE : UN COMPTEUR AGRÉGÉ EN SEAUX JOURNALIERS ═══
#
#  PAS un quatrième élément de FENETRES — une structure À PART, "jours",
#  dans le même fichier JSON, à côté de "evenements" :
#
#      {"version": 2,
#       "evenements": [[t, poids, "collect"], …],   ← inchangé, 24 h
#       "jours": {"2026-08-21": 4982.4, "2026-08-22": 3810.6, …}}
#
#  · SEAUX JOURNALIERS, pas un agrégat par MOIS CALENDAIRE (la forme
#    esquissée dans le prompt, "2026-08": 121878.0) — cf. question 1
#    du prompt : le mois d'Open-Meteo n'est PAS mesuré, et un agrégat
#    par mois calendaire suppose implicitement qu'il l'est. Les seaux
#    journaliers répondent aux DEUX hypothèses (calendaire OU glissant)
#    sans trancher ce qu'on ne peut pas trancher : sommés sur les 30
#    derniers jours (`_poids_mois`), ils incluent le jour calendaire
#    ENTIER qui contient la borne basse de la fenêtre, donc surestiment
#    légèrement plutôt que l'inverse — même arbitrage que le périmètre
#    global/par-API en tête de fichier : un garde-fou qui se trompe doit
#    se tromper du côté qui protège.
#
#  · INCRÉMENTÉS AU MÊME ENDROIT que l'événement (`_reserver`, sous le
#    même `flock`, dans la même réécriture atomique `_ecrire`) — sinon
#    les deux compteurs peuvent diverger après un crash entre les deux.
#
#  · ÉLAGUÉS À 31 JOURS (`JOURS_CONSERVES`) : 30 jours de fenêtre + 1 de
#    marge pour que le jour EN COURS, toujours partiel, ne fasse jamais
#    manquer un jour complet côté bas de la fenêtre.
#
#  · MARGE 5 % (`MARGE_LONGUE`), la même que l'heure et le jour : c'est
#    une ACCUMULATION, pas une fenêtre où la dispersion réseau mord.
#
#  · UN MOIS PLEIN REFUSE IMMÉDIATEMENT, SANS ATTENDRE (question 2) :
#    attendre n'a aucun sens, la fenêtre met des JOURS à se vider — très
#    au-delà d'`ATTENTE_MAX_S` (300 s). `_reserver` court-circuite donc
#    `_quand_possible` pour le mensuel et rend directement `float("inf")`
#    avec le motif `"mois"`, que `demander()` traduit en `BudgetRefuse`
#    dont le message contient explicitement le mot « mois » — vérifié
#    par le banc, pas supposé.
#
#  · L'ANNONCE AVANT LA MORSURE (question 3) vit dans `etat()` et
#    `resume()` — PAS dans `model-verif/collect.py::quota_projete()`,
#    qui reste INTOUCHÉ : les cinq appelants impriment déjà
#    `budget.resume()` et itèrent déjà `budget.etat()["fenetres"]` en
#    fin de run. Étendre ces deux méthodes suffit à faire apparaître la
#    ligne mensuelle — « mois 121878/300000 (40,6 %), au rythme actuel
#    plein le AAAA-MM-JJ » — SANS toucher un seul appelant.
#
#  · COÛT EN E/S MESURÉ (question 4), pas estimé : `TestCoutEntreesSorties`
#    du banc sérialise un état réaliste (1 077 événements + 31 jours) et
#    mesure la taille en octets. Les 31 seaux journaliers ajoutent moins
#    de 1 000 octets — sans commune mesure avec le ~1,7 Mo qu'aurait
#    coûté l'option naïve.
#
#  ⚠️ CE QUE CE CHOIX NE TRANCHE PAS : si Open-Meteo compte réellement en
#  mois CALENDAIRE (non mesuré), ce seau se déclenchera parfois un peu
#  AVANT que le fournisseur ne coupe vraiment — jamais après. C'est le
#  sens dans lequel un garde-fou a le droit de se tromper.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import datetime
import fcntl
import json
import os
import sys
import tempfile
import time
from pathlib import Path

#: Emplacement de l'état partagé. Surchargeable par l'environnement pour
#: les bancs et pour un essai à blanc — jamais en production.
CHEMIN_BUDGET = Path(os.environ.get("BW_QUOTA_FICHIER",
                                    "/var/lib/bw-quota/openmeteo.json"))

#: Plafonds du palier gratuit Open-Meteo, en appels PONDÉRÉS.
#: ⚠️ `PLAFOND_HEURE` est celui qui manquait, et c'est le seul qui ait
#: été FATAL le 09/08 : la minute se rattrape en attendant 65 s, l'heure
#: non. Un dépassement horaire ferme la porte pour le reste de l'heure.
PLAFOND_MINUTE = 600
PLAFOND_HEURE = 5_000
PLAFOND_JOUR = 10_000

#: Fenêtres GLISSANTES, pas des heures d'horloge.
#: ⚠️ Le journal du 09/08 ne tranche pas entre les deux : le blocage a
#: duré de 05:33 à 05:59, et le run a été tué avant qu'on puisse voir
#: si 06:00 rouvrait la porte. On prend donc la glissante, qui est
#: l'hypothèse la plus stricte : si le serveur compte par heure
#: d'horloge, le seau sera simplement un peu trop prudent. L'inverse
#: aurait rejoué la panne.
FENETRES = (
    ("minute", 60.0, PLAFOND_MINUTE),
    ("heure", 3600.0, PLAFOND_HEURE),
    ("jour", 86400.0, PLAFOND_JOUR),
)

#: ⭐ LOT S0.7 (22/08) — le QUATRIÈME plafond, mensuel. ⛔ VOLONTAIREMENT
#: PAS dans FENETRES : cf. le pavé « S0.7 » en tête de fichier — y
#: ajouter une ligne ("mois", 2_592_000, PLAFOND_MOIS) réutiliserait
#: l'élagage à 86 400 s de `_reserver` et ne se déclencherait JAMAIS.
#: Le mensuel est compté à part, en seaux journaliers (`_poids_mois`,
#: `_jours_elagues`), sur une fenêtre glissante de 30 jours.
PLAFOND_MOIS = 300_000

#: Fenêtre glissante, PAS calendaire — cf. le pavé S0.7 : le mois
#: d'Open-Meteo n'est pas mesuré, et les seaux journaliers répondent aux
#: deux hypothèses sans avoir à trancher entre elles.
DUREE_MOIS_S = 30 * 86400.0

#: 30 jours de fenêtre + 1 de marge pour le jour en cours, toujours
#: partiel (cf. `_jours_elagues`).
JOURS_CONSERVES = 31

#: Marges. Elles ne sont PAS uniformes, et la différence est raisonnée.
#:
#: ⚠️ LA MINUTE GARDE 10 % — c'est la fenêtre où la dispersion mord.
#: Le seau ne connaît que l'instant où il AUTORISE une requête, pas
#: celui où le serveur la COMPTE : entre les deux il y a un aller-retour
#: réseau qui varie. Le 08/08 a tourné à 600 pondérés/min pile sans un
#: seul 429 ; le 09/08 à 631 en a pris toutes les deux minutes. La ligne
#: est donc réelle et proche : on ne la frôle pas.
#:
#: ⚠️ L'HEURE ET LE JOUR GARDENT 5 % — ce sont des ACCUMULATIONS, que le
#: seau compte exactement. Il n'y a pas de dispersion à absorber sur une
#: fenêtre de 3 600 s. Y mettre 10 % coûterait 500 pondérés par heure,
#: soit 62 points de collecte, pour se protéger d'un bruit qui n'existe
#: pas à cette échelle.
MARGE_MINUTE = 0.90
MARGE_LONGUE = 0.95

#: Attente maximale par défaut avant d'abandonner un point (cf.
#: arbitrage 2). 300 s tient dans le chien de garde de 40 min même si
#: plusieurs points de suite doivent patienter.
ATTENTE_MAX_S = 300.0

#: Cadence de repli quand l'état est illisible (cf. plus bas).
#: ⚠️ C'est la cadence conservatrice d'AVANT ce lot, pas une cadence
#: inventée : 0,70 s de pause a tenu le 08/08. Dégradé, pas arrêté.
PAUSE_REPLI_S = 0.70


class BudgetRefuse(Exception):
    """Les jetons n'arrivent pas dans la borne d'attente.

    ⚠️ N'EST PAS UNE ERREUR TECHNIQUE. C'est un refus argumenté : le
    plafond est atteint et il ne se libérera pas assez vite. L'appelant
    doit en faire un TROU DÉCLARÉ, jamais une valeur inventée.
    """


def poids(n_variables: int, n_modeles: int = 1) -> float:
    """Poids d'une requête, DÉRIVÉ de la requête et non recopié.

    ⚠️ LE PLAFOND OPEN-METEO COMPTE DES VARIABLES, PAS DES APPELS.
    Passer de 5 à 8 variables par modèle a fait passer le poids d'un
    point de 5,0 à 8,0 — et c'est ce facteur qui a franchi l'heure le
    09/08. Compter en requêtes reproduirait le défaut sous un autre nom,
    et l'instrumentation donnerait l'illusion d'une surveillance.

    ⚠️ ET SURTOUT : NE PAS FIGER LE RÉSULTAT DANS UNE CONSTANTE. Le `8`
    d'aujourd'hui est le nombre de variables du moment. Le jour où
    quelqu'un ajoute une variable ou un modèle, un `8` en dur devient
    faux en silence — exactement la panne du 09/08, rejouée. On passe
    donc `len(_hourly_vars())` et `len(MODELS)`, jamais leur produit
    mémorisé.

    La division par 10 vient d'Open-Meteo : une requête « coûte » le
    nombre de variables rapporté à 10. La remise `jours/14` a été
    retirée le 07/08 et ne revient pas — cf. le pavé de `quota_projete`.

    ⛔⛔ **LE PLANCHER À 1,0 — ET IL A COÛTÉ UNE NUIT D'ARCHIVE
    (débug du 24/08/2026).** Un appel HTTP ne coûte JAMAIS moins d'un
    appel. Open-Meteo facture **au minimum une requête**, si petite
    soit-elle ; la formule variables × modèles / 10 ne décrit le
    serveur QU'AU-DESSUS de 1.

    Mesuré, pas déduit : `collect_reduit` envoyait deux requêtes par
    point, de 0,8 (2 modèles × 4 vars) et 0,6 (3 × 2) pondérés. Le
    compteur les additionnait à **1,40** ; le serveur les comptait
    **2,00**. À 2 518 points, cela fait 5 037 requêtes contre un
    plafond HORAIRE de 5 000 : le run a heurté le mur au point ~2 500,
    **à l'unité près**, alors que son propre budget lui annonçait
    1 000 pondérés de marge. Facteur d'erreur : 1,43.

    ⚠️ **ET LE DÉFAUT NE POUVAIT SE VOIR QUE LÀ.** Il ne mord QUE sur
    une requête dont le poids est sous 1. Mesuré le 24/08 : la passe
    Pioupiou pèse 1,6 (2 modèles × 8 vars) et 4,2 (7 × 6) — les deux
    au-dessus, donc le plancher ne la change pas d'un pondéré et n'a
    jamais eu l'occasion de se manifester. Il fallait une passe dont
    **les DEUX** requêtes soient sous 1 : c'était celle du 23/08, à sa
    première nuit.

    ⚠️ **ET AUCUN BANC NE POUVAIT L'ATTRAPER.** Le banc du S0.11
    affirmait « 1,40 pondéré par point, mesuré sur l'URL RÉELLE », et
    il était VERT : il mesurait l'accord du code avec lui-même, jamais
    avec l'API. Un `--dry-run` bâti sur la même formule disait la même
    chose fausse avec la même assurance. Le plancher est la seule
    partie de cette fonction qui vienne d'une mesure faite CONTRE le
    serveur, et non contre nous-mêmes.

    ⓘ Le plancher s'applique PAR REQUÊTE. Les appelants qui somment
    plusieurs groupes doivent donc appeler `poids()` une fois PAR
    GROUPE et additionner ensuite — jamais sommer les produits puis
    diviser, ce qui ferait disparaître le plancher exactement là où il
    mord (`collect.poids_par_point`, `collect_reduit`).
    """
    if n_variables < 1 or n_modeles < 1:
        raise ValueError("poids : au moins une variable et un modèle")
    return max(1.0, n_variables * n_modeles / 10.0)


def poids_url(url: str) -> float:
    """Poids d'une requête, lu sur L'URL RÉELLEMENT CONSTRUITE.

    ⚠️ C'EST LA FORME QUI NE PEUT PAS DÉRIVER. `poids(n, m)` oblige
    l'appelant à recompter ses variables à la main, et un appelant qui
    recompte à la main finit par oublier — c'est littéralement la panne
    du 09/08, où un `5` est devenu `8` sans que le garde-fou bouge. Ici,
    ajouter une variable à la requête change le poids sans que personne
    n'ait à y penser.

    Trois multiplicateurs, et le troisième est celui qu'on oublie :
      · le nombre de variables (`hourly`, `minutely_15`, `daily`) ;
      · le nombre de MODÈLES demandés ;
      · le nombre de LIEUX — Open-Meteo accepte `latitude=a,b,c` et
        compte chaque point. `backfill_packs.py` envoie des lots ; sans
        ce facteur son poids serait sous-estimé d'un ordre de grandeur.
    """
    from urllib.parse import parse_qs, urlparse

    q = parse_qs(urlparse(url).query)

    def _liste(cle: str) -> list:
        return [v for bloc in q.get(cle, []) for v in bloc.split(",") if v]

    n_vars = len(_liste("hourly") + _liste("minutely_15") + _liste("daily"))
    n_modeles = max(len(_liste("models")), 1)
    n_lieux = max(len(_liste("latitude")), 1)
    return poids(max(n_vars, 1), n_modeles * n_lieux)


def plafond_effectif(fenetre: str) -> float:
    """Plafond réduit de la marge propre à la fenêtre."""
    for nom, _duree, brut in FENETRES:
        if nom == fenetre:
            marge = MARGE_MINUTE if nom == "minute" else MARGE_LONGUE
            return brut * marge
    raise KeyError(fenetre)


def plafond_mois_effectif() -> float:
    """Plafond MENSUEL réduit de MARGE_LONGUE.

    ⚠️ Une ACCUMULATION, comme l'heure et le jour, cf. le pavé de marges
    plus haut — 30 jours glissants n'ont pas la dispersion réseau que la
    minute doit absorber.
    """
    return PLAFOND_MOIS * MARGE_LONGUE


def _cle_jour(instant: float) -> str:
    """Date UTC d'un instant — la clé d'un seau journalier ('AAAA-MM-JJ').

    ⚠️ UTC, jamais l'heure locale du VPS : `time.time()` (et l'horloge
    injectée dans les bancs) est déjà en secondes UTC depuis l'epoch.
    Mélanger un fuseau ici rendrait la frontière du jour incohérente
    avec les fenêtres minute/heure/jour, qui elles ignorent totalement
    les fuseaux — et ferait un compteur mensuel qui compte parfois 23 h,
    parfois 25 h de « jour ».
    """
    return datetime.datetime.fromtimestamp(
        instant, tz=datetime.timezone.utc).strftime("%Y-%m-%d")


def _poids_mois(jours: dict, maintenant: float) -> float:
    """Pondéré cumulé sur les 30 jours glissants, lu sur les seaux.

    ⚠️ SURESTIME LÉGÈREMENT, JAMAIS NE SOUS-ESTIME : la fenêtre inclut
    le jour calendaire ENTIER qui contient sa borne basse, même si une
    partie de ce jour-là tombe en réalité hors fenêtre — la seule
    imprécision qu'un seau à granularité JOURNALIÈRE peut faire, et on
    la fait du côté qui protège (même arbitrage que le périmètre
    global/par-API en tête de fichier).
    """
    depuis = _cle_jour(maintenant - DUREE_MOIS_S)
    return sum(w for jour, w in jours.items() if jour >= depuis)


def _jours_elagues(jours: dict, maintenant: float) -> dict:
    """Seaux journaliers élagués à `JOURS_CONSERVES` jours.

    ⚠️ Sans cet élagage le fichier grossirait sans fin, comme le pavé
    S0.7 le note pour la forme naïve — sauf qu'ici il grossit d'UNE
    entrée par jour, jamais d'une par événement.
    """
    limite = _cle_jour(maintenant - JOURS_CONSERVES * 86400.0)
    return {jour: p for jour, p in jours.items() if jour >= limite}


def _projection_mois(jours: dict, maintenant: float) -> str | None:
    """AAAA-MM-JJ où le seau mensuel serait plein « au rythme actuel ».

    Rend `None` si la donnée est insuffisante (aucun jour mesuré dans la
    fenêtre) ou si le rythme est nul — pas de projection à faire.

    ⚠️ LE RYTHME EST LA MOYENNE DES JOURS RÉELLEMENT MESURÉS dans la
    fenêtre, pas `consomme / 30`. Au lendemain d'une migration ou d'un
    redémarrage il n'y a que quelques jours de mesure ; diviser par 30
    sous-estimerait le rythme — donc la projection — du côté qui NE
    protège PAS.
    """
    depuis = _cle_jour(maintenant - DUREE_MOIS_S)
    pertinents = {jour: p for jour, p in jours.items() if jour >= depuis}
    if not pertinents:
        return None
    consomme = sum(pertinents.values())
    rythme = consomme / len(pertinents)
    if rythme <= 0:
        return None
    plafond = plafond_mois_effectif()
    if consomme >= plafond:
        return _cle_jour(maintenant)
    jours_restants = (plafond - consomme) / rythme
    return _cle_jour(maintenant + jours_restants * 86400.0)


class Budget:
    """Le droit de parler à Open-Meteo, compté hors processus.

    Usage, côté appelant :

        budget = Budget("collect")
        p = poids(len(_hourly_vars()), len(MODELS))
        for st in stations:
            try:
                budget.demander(p)          # bloque le temps qu'il faut
            except BudgetRefuse:
                trous += 1                  # trou DÉCLARÉ, jamais comblé
                continue
            ...requête...

    ⚠️ `demander()` crédite le budget AVANT la requête, pas après. Deux
    raisons : le serveur compte la requête dès qu'il la reçoit, même
    s'il répond 429 ; et un processus tué entre la requête et le crédit
    laisserait le compteur MENTEUR à la baisse — c'est-à-dire du côté
    qui ne protège pas.
    """

    def __init__(self, consommateur: str, chemin: Path | None = None,
                 attente_max_s: float = ATTENTE_MAX_S,
                 horloge=time.time, dormir=time.sleep,
                 journal=sys.stderr) -> None:
        if not consommateur:
            raise ValueError("un budget sans consommateur nommé ne sert à rien")
        self.consommateur = consommateur
        self.chemin = Path(chemin) if chemin else CHEMIN_BUDGET
        self.attente_max_s = attente_max_s
        self._horloge = horloge
        self._dormir = dormir
        self._journal = journal
        self.degrade = False
        self._degrade_dit = False
        self._migration_dite = False
        self.attendu_s = 0.0
        self.consomme = 0.0
        self.refuses = 0

    # ── état sur disque ──────────────────────────────────────────
    #
    # ⚠️ LE VERROU EST SUR UN FICHIER À PART, ET C'EST DÉLIBÉRÉ.
    # L'état est réécrit par `rename` atomique : le rename remplace
    # l'inode, donc un `flock` posé sur l'état lui-même protégerait un
    # inode que le prochain écrivain vient de jeter. Deux processus
    # croiraient tenir le verrou en même temps — précisément le défaut
    # qu'un budget partagé existe pour éliminer.

    def _chemin_verrou(self) -> Path:
        return self.chemin.with_name(self.chemin.name + ".lock")

    def _lire(self) -> tuple[list, dict]:
        """(événements, seaux journaliers) du fichier, ou ([], {}) si neuf.

        ⚠️ Toute lecture qui échoue bascule en mode DÉGRADÉ plutôt que
        de lever : un garde-fou qui empêche de tourner est pire que le
        risque qu'il couvre. Fichier absent, JSON tronqué, version
        inconnue, droits refusés — même traitement.

        ⚠️ MIGRATION DEPUIS LA VERSION 1 (avant le S0.7, sans compteur
        mensuel) : l'ABSENCE de la clé "jours" — pas le numéro de
        version, plus robuste à un fichier écrit à la main — déclenche
        `_signaler_migration()`. Il n'y a rien à récupérer (la version 1
        ne conservait aucun agrégat journalier), donc les seaux
        démarrent à {} ; ce qui compte est que ce ne soit jamais fait EN
        SILENCE.
        """
        try:
            brut = json.loads(self.chemin.read_text(encoding="utf-8"))
            evenements = brut["evenements"]
            if not isinstance(evenements, list):
                raise ValueError("evenements n'est pas une liste")
            evenements = [(float(t), float(p), str(q)) for t, p, q in evenements]
            if "jours" in brut:
                jours = brut["jours"]
                if not isinstance(jours, dict):
                    raise ValueError("jours n'est pas un objet")
                jours = {str(j): float(w) for j, w in jours.items()}
            else:
                jours = {}
                self._signaler_migration()
            return evenements, jours
        except FileNotFoundError:
            return [], {}
        except Exception as exc:                      # noqa: BLE001
            self._passer_en_degrade(f"état illisible ({exc})")
            return [], {}

    def _signaler_migration(self) -> None:
        """Dit UNE FOIS qu'un fichier sans compteur mensuel a été lu.

        ⚠️ NE REPART JAMAIS « DE ZÉRO EN SILENCE » (Livrable attendu du
        S0.7) : il n'y a rien à récupérer — la version 1 ne conservait
        pas d'agrégat journalier — donc démarrer à 0 est la seule
        option honnête. Cette méthode garantit qu'on le SAIT, pas qu'on
        invente un historique.
        """
        if not self._migration_dite:
            self._migration_dite = True
            print(f"  ⓘ budget Open-Meteo : {self.chemin} sans compteur "
                  f"mensuel (version 1) — migration vers la version 2, "
                  f"compteur MENSUEL démarré à 0 (rien à récupérer : la "
                  f"version 1 ne conservait pas d'agrégat journalier)",
                  file=self._journal)

    def _ecrire(self, evenements: list, jours: dict) -> None:
        """Réécriture atomique : fichier temporaire puis `rename`.

        ⚠️ Un `open(..., "w")` suivi d'un crash laisserait un JSON
        tronqué — et le lecteur suivant basculerait en dégradé pour
        rien. `rename` est atomique sur le même système de fichiers :
        l'état est soit l'ancien, soit le nouveau, jamais entre les deux.

        ⭐ VERSION 2 (S0.7) : `evenements` ET `jours` sont réécrits
        ENSEMBLE, dans le MÊME `rename` atomique — c'est ce qui garantit
        qu'ils ne peuvent pas diverger après un crash entre les deux.
        """
        contenu = json.dumps({"version": 2, "evenements": evenements,
                              "jours": jours},
                             separators=(",", ":"))
        fd, tmp = tempfile.mkstemp(dir=str(self.chemin.parent),
                                   prefix=".quota-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(contenu)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.chemin)
        except Exception:                              # noqa: BLE001
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _passer_en_degrade(self, raison: str) -> None:
        """Bascule en cadence de repli, et le DIT — une seule fois."""
        self.degrade = True
        if not self._degrade_dit:
            self._degrade_dit = True
            print(f"  ⓘ budget Open-Meteo indisponible ({raison}) — repli sur "
                  f"la cadence conservatrice de {PAUSE_REPLI_S:.2f}s, sans "
                  f"comptage partagé", file=self._journal)

    # ── arithmétique des fenêtres ────────────────────────────────

    @staticmethod
    def _quand_possible(evenements: list, p: float, maintenant: float) -> float:
        """0.0 si le jeton est disponible, sinon l'attente en secondes.

        Renvoie `inf` si la requête ne peut JAMAIS passer — cas d'une
        requête dont le poids dépasse à lui seul un plafond.

        ⚠️ On ne compte pas des seaux qui se vident à taux constant mais
        des ÉVÉNEMENTS DATÉS dans une fenêtre glissante. La différence
        compte : un seau à fuite autorise une rafale en début de fenêtre
        que le serveur, lui, comptera d'un bloc. Ici l'attente est
        l'instant EXACT où assez de poids sort de la fenêtre.
        """
        attente = 0.0
        for nom, duree, _brut in FENETRES:
            limite = plafond_effectif(nom)
            dedans = sorted((t, w) for t, w, _q in evenements
                            if t > maintenant - duree)
            somme = sum(w for _t, w in dedans)
            if somme + p <= limite:
                continue
            besoin = somme + p - limite
            cumul = 0.0
            liberation = None
            for t, w in dedans:
                cumul += w
                if cumul >= besoin:
                    liberation = t + duree
                    break
            if liberation is None:
                return float("inf")
            attente = max(attente, liberation - maintenant)
        return attente

    def attente_fenetre(self, poids_total: float,
                        fenetre: str = "heure") -> float:
        """Quand UNE fenêtre nommée aura la place pour `poids_total`.

        Rend 0.0 si la place est déjà là, sinon l'attente en secondes,
        sinon `inf` si `poids_total` dépasse à lui seul le plafond
        effectif de cette fenêtre — auquel cas aucune attente ne sert et
        c'est `quota_projete` qui doit refuser, pas ce compteur.

        ⚠️ CE N'EST PAS `_quand_possible`, ET LA DIFFÉRENCE EST LE SUJET
        DU LOT S0.6. `_quand_possible` répond pour UNE requête et sur
        TOUTES les fenêtres — la minute comprise, qui ne peut jamais
        contenir le poids d'une passe entière et rendrait donc `inf`
        pour une question qui a une réponse. Ici on demande à UNE seule
        fenêtre, celle qui ferme la porte pour une heure entière.

        ⛔ POURQUOI CETTE MÉTHODE EXISTE. Une passe de collecte lancée
        à l'heure où la précédente déborde encore se ferait refuser
        POINT PAR POINT jusqu'à `ATTENTE_MAX_S`, en fabriquant des
        centaines de trous DÉCLARÉS là où attendre douze minutes une
        seule fois aurait tout sauvé. Un trou déclaré vaut mieux qu'un
        run tué (arbitrage 2 de l'en-tête) — mais il ne vaut rien du
        tout face à une attente qui, elle, ramène la donnée. La passe
        doit donc pouvoir DEMANDER l'instant où la place se libère au
        lieu de le supposer.

        ⚠️ LECTURE SANS VERROU ET SANS RÉSERVATION, et c'est voulu :
        c'est un CONSEIL, pas un droit. La réservation reste celle de
        `demander()`, point par point, sous `flock`. Deux passes qui
        liraient ce conseil en même temps se réserveraient quand même
        correctement — au pire elles se marcheraient dessus au niveau
        des points, ce que le seau sait déjà arbitrer.

        ⓘ Le mode dégradé rend 0.0 : sans état lisible, on ne sait rien,
        et faire attendre sur une ignorance serait pire que partir à la
        cadence de repli.
        """
        for nom, duree, _brut in FENETRES:
            if nom != fenetre:
                continue
            limite = plafond_effectif(nom)
            if poids_total > limite:
                return float("inf")
            evenements, _jours = self._lire()
            if self.degrade:
                return 0.0
            maintenant = self._horloge()
            dedans = sorted((t, w) for t, w, _q in evenements
                            if t > maintenant - duree)
            somme = sum(w for _t, w in dedans)
            if somme + poids_total <= limite:
                return 0.0
            besoin = somme + poids_total - limite
            cumul = 0.0
            for t, w in dedans:
                cumul += w
                if cumul >= besoin:
                    return max(0.0, t + duree - maintenant)
            # Inatteignable : `besoin` ne peut pas dépasser `somme`.
            return float("inf")
        raise KeyError(fenetre)

    def _reserver(self, p: float) -> tuple[float, str]:
        """Sous verrou : réserve `p` si possible, sinon dit quand.

        Renvoie `(0.0, "")` si le jeton est pris (état déjà réécrit),
        sinon `(attente_s, motif)` — `motif` vaut `"mois"` quand c'est
        le plafond MENSUEL qui refuse (`demander()` en a besoin pour
        nommer la bonne fenêtre dans le message de `BudgetRefuse`), et
        `""` pour les trois fenêtres glissantes classiques, dont le
        message ne nomme aucune fenêtre depuis le 09/08 (inchangé ici).
        """
        verrou = self._chemin_verrou()
        verrou.parent.mkdir(parents=True, exist_ok=True)
        with open(verrou, "a+") as vf:
            fcntl.flock(vf.fileno(), fcntl.LOCK_EX)
            try:
                evenements, jours = self._lire()
                if self.degrade:
                    return 0.0, ""        # traité par l'appelant
                maintenant = self._horloge()
                # Élagage : au-delà de 24 h, un événement ne pèse dans
                # aucune fenêtre. Sans lui le fichier grossirait sans fin.
                # ⛔ CETTE LIGNE NE BOUGE PAS (cf. le pavé S0.7 en tête de
                # fichier) : le mensuel est compté à part, sur `jours`,
                # justement pour ne PAS en dépendre.
                evenements = [e for e in evenements
                              if e[0] > maintenant - 86400.0]
                jours = _jours_elagues(jours, maintenant)

                # ⛔ LE MENSUEL D'ABORD, ET SANS PASSER PAR
                # `_quand_possible` : question 2 du prompt S0.7 —
                # attendre n'a aucun sens, la fenêtre met des JOURS à se
                # vider, très au-delà d'`ATTENTE_MAX_S`. Un refus
                # immédiat dit la vérité ; un temps d'attente calculé sur
                # un seau à granularité JOURNALIÈRE ne saurait de toute
                # façon pas dire l'instant exact.
                consomme_mois = _poids_mois(jours, maintenant)
                if consomme_mois + p > plafond_mois_effectif():
                    return float("inf"), "mois"

                attente = self._quand_possible(evenements, p, maintenant)
                if attente > 0.0:
                    return attente, ""
                evenements.append((maintenant, p, self.consommateur))
                # ⭐ Incrémenté ICI, sous le MÊME verrou, réécrit dans la
                # MÊME `rename` atomique que `evenements` — sinon les
                # deux compteurs peuvent diverger après un crash entre
                # deux écritures séparées.
                cle = _cle_jour(maintenant)
                jours[cle] = jours.get(cle, 0.0) + p
                self._ecrire(evenements, jours)
                return 0.0, ""
            finally:
                fcntl.flock(vf.fileno(), fcntl.LOCK_UN)

    # ── l'appel que font les cinq scripts ────────────────────────

    def demander(self, p: float, etiquette: str = "") -> float:
        """Bloque jusqu'à disposer de `p` pondérés. Renvoie l'attente.

        ⚠️ NE MENT JAMAIS PAR OMISSION. Toute attente d'une seconde ou
        plus est journalisée avec le nom du consommateur. C'est ce qui
        permettra de lire « `day_features` a pris 4 000 unités entre
        05:12 et 05:31 » plutôt que « quelque chose a dépassé ».
        """
        if p <= 0:
            raise ValueError("un poids nul ou négatif ne se réserve pas")

        if self.degrade:
            self._dormir(PAUSE_REPLI_S)
            self.consomme += p
            return PAUSE_REPLI_S

        debut = self._horloge()
        attendu = 0.0
        while True:
            try:
                attente, motif = self._reserver(p)
            except OSError as exc:
                # Disque plein, droits refusés, /var/lib absent : on
                # dégrade, on ne s'arrête pas.
                self._passer_en_degrade(f"écriture impossible ({exc})")
                self._dormir(PAUSE_REPLI_S)
                self.consomme += p
                return PAUSE_REPLI_S

            if self.degrade:
                self._dormir(PAUSE_REPLI_S)
                self.consomme += p
                return PAUSE_REPLI_S

            if attente <= 0.0:
                self.consomme += p
                self.attendu_s += attendu
                return attendu

            if attente == float("inf"):
                self.refuses += 1
                if motif == "mois":
                    # ⭐ Question 2 du prompt S0.7, vérifiée : le mois
                    # plein refuse IMMÉDIATEMENT, jamais après une
                    # attente — et le message dit « mois », pas autre
                    # chose (Livrable attendu du lot).
                    raise BudgetRefuse(
                        f"{self.consommateur}: le plafond MENSUEL Open-Meteo "
                        f"est atteint ({plafond_mois_effectif():.0f} "
                        f"pondérés effectifs sur {PLAFOND_MOIS} bruts, 30 "
                        f"jours glissants) pour {p:.1f} pondérés — attendre "
                        f"n'a aucun sens, la fenêtre met des jours à se "
                        f"vider. Point non collecté — trou déclaré pour le "
                        f"mois.")
                raise BudgetRefuse(
                    f"{self.consommateur}: une requête de {p:.1f} pondérés "
                    f"dépasse à elle seule un plafond — revoir le nombre de "
                    f"variables ou de modèles, pas la cadence")

            restant = self.attente_max_s - (self._horloge() - debut)
            if attente > restant:
                self.refuses += 1
                raise BudgetRefuse(
                    f"{self.consommateur}: {attente:.0f}s d'attente pour "
                    f"{p:.1f} pondérés{(' — ' + etiquette) if etiquette else ''}, "
                    f"au-delà de la borne de {self.attente_max_s:.0f}s. "
                    f"Point non collecté — trou déclaré.")

            if attente >= 1.0:
                print(f"  ⏳ {self.consommateur} attend {attente:.0f}s de quota "
                      f"Open-Meteo{(' — ' + etiquette) if etiquette else ''}",
                      file=self._journal)
            self._dormir(attente)
            attendu += attente

    # ── lecture d'état, pour les journaux et les sondes ──────────

    def etat(self) -> dict:
        """Consommation par fenêtre et par consommateur, à l'instant t.

        ⚠️ Sert à la ligne de journal de fin de run. Un budget partagé
        qui ne nomme pas ses consommateurs déplace le problème au lieu
        de le résoudre.

        ⭐ `vue["mois"]` (S0.7) — À PART de `vue["fenetres"]`, PAS un
        quatrième élément dedans : sa forme diffère (pas de
        `par_consommateur` — les seaux journaliers ne gardent pas cette
        granularité, c'est tout le point de l'agrégat) et le mêler à
        `fenetres` risquerait de le faire un jour finir DANS FENETRES
        par un « nettoyage » bien intentionné — exactement l'erreur que
        ce lot existe pour empêcher.
        """
        evenements, jours = self._lire()
        maintenant = self._horloge()
        vue: dict = {"degrade": self.degrade, "fenetres": {}}
        for nom, duree, brut in FENETRES:
            dedans = [e for e in evenements if e[0] > maintenant - duree]
            par_qui: dict = {}
            for _t, w, qui in dedans:
                par_qui[qui] = par_qui.get(qui, 0.0) + w
            vue["fenetres"][nom] = {
                "consomme": round(sum(w for _t, w, _q in dedans), 1),
                "plafond": brut,
                "plafond_effectif": round(plafond_effectif(nom), 1),
                "par_consommateur": {k: round(v, 1) for k, v in
                                     sorted(par_qui.items(),
                                            key=lambda kv: -kv[1])},
            }
        consomme_mois = _poids_mois(jours, maintenant)
        vue["mois"] = {
            "consomme": round(consomme_mois, 1),
            "plafond": PLAFOND_MOIS,
            "plafond_effectif": round(plafond_mois_effectif(), 1),
            "projection": _projection_mois(jours, maintenant),
        }
        return vue

    def resume(self) -> str:
        """Une ligne lisible, pour la fin d'un run.

        ⭐ QUESTION 3 DU PROMPT S0.7 : « faut-il l'annoncer avant de
        mordre ? » — le S0.4 l'a fait pour l'heure dans
        `quota_projete()` (`model-verif/collect.py`) ; ici, ajouter la
        ligne DANS `resume()` fait apparaître l'annonce mensuelle chez
        les CINQ appelants qui impriment déjà cette ligne en fin de run,
        SANS toucher un seul d'entre eux — cf. le pavé S0.7 en tête de
        fichier.
        """
        vue = self.etat()
        morceaux = []
        for nom, _duree, _brut in FENETRES:
            f = vue["fenetres"][nom]
            morceaux.append(f"{nom} {f['consomme']:.0f}/{f['plafond']}")
        m = vue["mois"]
        pct_mois = (m["consomme"] / m["plafond"] * 100) if m["plafond"] else 0.0
        ligne_mois = f"mois {m['consomme']:.0f}/{m['plafond']} ({pct_mois:.1f} %)"
        if m["projection"]:
            ligne_mois += f", au rythme actuel plein le {m['projection']}"
        morceaux.append(ligne_mois)
        suffixe = " (DÉGRADÉ)" if self.degrade else ""
        return (f"quota Open-Meteo — {', '.join(morceaux)} ; "
                f"{self.consommateur} a consommé {self.consomme:.0f}, "
                f"attendu {self.attendu_s:.0f}s, "
                f"{self.refuses} refus{suffixe}")


# ══════════════════════════════════════════════════════════════════════
#  Lecture à l'œil : `python3 quota_openmeteo.py` affiche l'état.
#  ⚠️ Volontairement sans argument et sans effet de bord — c'est la
#  commande qu'on tape à 6 h du matin quand la collecte a échoué.
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    b = Budget("sonde")
    etat = b.etat()
    print(f"budget : {b.chemin}")
    for nom_f, info in etat["fenetres"].items():
        print(f"┌─ {nom_f} : {info['consomme']:.0f} / {info['plafond']} "
              f"(seuil interne {info['plafond_effectif']:.0f})")
        for qui, combien in info["par_consommateur"].items():
            print(f"│   {qui:<24} {combien:>8.1f}")
    m = etat["mois"]
    print(f"┌─ mois : {m['consomme']:.0f} / {m['plafond']} "
          f"(seuil interne {m['plafond_effectif']:.0f})"
          + (f" — au rythme actuel plein le {m['projection']}"
             if m["projection"] else ""))
    if etat["degrade"]:
        print("⚠️  état illisible — les chiffres ci-dessus sont incomplets")
