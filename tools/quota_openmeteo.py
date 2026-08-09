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
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

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
    """
    if n_variables < 1 or n_modeles < 1:
        raise ValueError("poids : au moins une variable et un modèle")
    return n_variables * n_modeles / 10.0


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

    def _lire(self) -> list:
        """Événements du fichier, ou [] si l'état est neuf.

        ⚠️ Toute lecture qui échoue bascule en mode DÉGRADÉ plutôt que
        de lever : un garde-fou qui empêche de tourner est pire que le
        risque qu'il couvre. Fichier absent, JSON tronqué, version
        inconnue, droits refusés — même traitement.
        """
        try:
            brut = json.loads(self.chemin.read_text(encoding="utf-8"))
            evenements = brut["evenements"]
            if not isinstance(evenements, list):
                raise ValueError("evenements n'est pas une liste")
            return [(float(t), float(p), str(q)) for t, p, q in evenements]
        except FileNotFoundError:
            return []
        except Exception as exc:                      # noqa: BLE001
            self._passer_en_degrade(f"état illisible ({exc})")
            return []

    def _ecrire(self, evenements: list) -> None:
        """Réécriture atomique : fichier temporaire puis `rename`.

        ⚠️ Un `open(..., "w")` suivi d'un crash laisserait un JSON
        tronqué — et le lecteur suivant basculerait en dégradé pour
        rien. `rename` est atomique sur le même système de fichiers :
        l'état est soit l'ancien, soit le nouveau, jamais entre les deux.
        """
        contenu = json.dumps({"version": 1, "evenements": evenements},
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

    def _reserver(self, p: float) -> float:
        """Sous verrou : réserve `p` si possible, sinon dit quand.

        Renvoie 0.0 si le jeton est pris (et l'état déjà réécrit), sinon
        l'attente en secondes, ou `inf` si c'est sans espoir.
        """
        verrou = self._chemin_verrou()
        verrou.parent.mkdir(parents=True, exist_ok=True)
        with open(verrou, "a+") as vf:
            fcntl.flock(vf.fileno(), fcntl.LOCK_EX)
            try:
                evenements = self._lire()
                if self.degrade:
                    return 0.0            # traité par l'appelant
                maintenant = self._horloge()
                # Élagage : au-delà de 24 h, un événement ne pèse dans
                # aucune fenêtre. Sans lui le fichier grossirait sans fin.
                evenements = [e for e in evenements
                              if e[0] > maintenant - 86400.0]
                attente = self._quand_possible(evenements, p, maintenant)
                if attente > 0.0:
                    return attente
                evenements.append((maintenant, p, self.consommateur))
                self._ecrire(evenements)
                return 0.0
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
                attente = self._reserver(p)
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
        """
        evenements = self._lire()
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
        return vue

    def resume(self) -> str:
        """Une ligne lisible, pour la fin d'un run."""
        vue = self.etat()
        morceaux = []
        for nom, _duree, _brut in FENETRES:
            f = vue["fenetres"][nom]
            morceaux.append(f"{nom} {f['consomme']:.0f}/{f['plafond']}")
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
    if etat["degrade"]:
        print("⚠️  état illisible — les chiffres ci-dessus sont incomplets")
