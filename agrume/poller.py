#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/poller.py — quand le run atterrit vraiment
#                                                        (10/08/2026)
#
#  ⚠️ AUCUNE HEURE DE MISE À DISPOSITION N'EST CODÉE EN DUR ICI, ET C'EST
#  LE POINT CENTRAL DU MODULE. La documentation Météo-France annonce
#  00→02 h 45, 03→05 h 45, 06→11 h 05, 09→12 h 30, 12→15 h 45,
#  15→18 h 10. Ces délais sont MUTUELLEMENT INCOHÉRENTS — 5 h 05 pour le
#  run de 06 h contre 3 h 30 pour celui de 09 h — et la doc ne dit même
#  pas si ces heures sont en UTC ou en heure légale. Un cron calé sur une
#  heure fixe fait donc forcément l'un des deux : il part trop tôt et
#  prend un 404, ou il part trop tard et perd de la fraîcheur.
#
#  Ce module fait l'inverse : il DEMANDE, il note l'heure réelle, et il
#  apprend. Au bout de quelques jours, la fenêtre de guet se resserre
#  toute seule autour de ce qui a été OBSERVÉ.
#
#  ── POURQUOI COMMENCER PAR AROME-PI ──────────────────────────────────
#  ✅ PI publie 24 runs par jour contre 8 pour AROME : c'est 24 mesures
#  de latence par jour au lieu de 8, sur le même code. Sa latence n'est
#  aujourd'hui bornée que par DEUX observations ponctuelles, ≤ 71 min et
#  ≤ 76 min — des BORNES, pas des mesures : on ne sait pas à quelle
#  minute ces runs sont apparus.
#
#  ── CE QUE COÛTE UNE INTERROGATION ───────────────────────────────────
#  ✅ Mesuré le 10/08, et l'écart décide de la méthode :
#     • `DescribeCoverage`  →  5 687 o en 0,12 s (run présent)
#                              593 o en 0,10 s (run absent)
#     • `GetCapabilities`   →  3,27 Mo, 10 288 identifiants, 105 runs
#  Un facteur ~575. Poller par GetCapabilities toutes les 2 minutes
#  coûterait 2,3 Go par jour pour une information de 600 octets. On
#  interroge donc UNE couverture précise, jamais le catalogue.
#  Côté S3 (AROME), `covered_steps()` fait déjà l'équivalent : un listing
#  de quelques kilo-octets, aucun téléchargement.
#
#  ── OÙ ÇA TOURNE ─────────────────────────────────────────────────────
#  Sur le VPS, et c'est son unique vraie propriété : IL EST ALLUMÉ EN
#  PERMANENCE. Une GitHub Action est un cron ; elle ne peut pas guetter.
#  Le bon partage est : VPS = détection et ordonnancement (quelques
#  requêtes de listing, coût nul) ; Actions = le gros du décodage
#  (éphémère, gratuit sur dépôt public). Le VPS ne touche jamais un GRIB.
#
#  Usage :
#      python3 agrume/poller.py --source aromepi --une-fois
#      python3 agrume/poller.py --source arome   --boucle
#      python3 agrume/poller.py --rapport
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

from domaine import (MAX_HOURS_GRILLE, PAQUETS_INGESTION,  # noqa: E402
                     PAQUETS_RALLONGE)
from mf_s3 import covered_steps  # noqa: E402
from portail import (SERVICE_AROME, SERVICE_AROMEPI, CouvertureAbsente,  # noqa: E402
                     ErreurPortail, Portail)

JOURNAL_DEFAUT = Path(os.environ.get("BW_MODEL_VERIF_ETAT",
                                     "/var/lib/bw-model-verif")) / "agrume_latence.ndjson"

# ── Cadence de guet ───────────────────────────────────────────────────
# ⚠️ Le back-off est là pour ne pas marteler quand un run est en retard
# ou absent, PAS pour économiser : une interrogation coûte 600 octets.
# Tant qu'on est dans la fenêtre plausible on reste FIN, parce que la
# précision de la mesure de latence vaut exactement la période de guet —
# un back-off qui démarre tout de suite transformerait « 41 min » en
# « quelque part entre 30 et 60 min ».
PERIODE_FINE_S = 120          # ±2 min sur la latence mesurée
PERIODE_MAX_S = 900           # plafond du back-off : 15 min
FACTEUR_BACKOFF = 1.6
FENETRE_FINE_MIN = 120        # au-delà, on lève le pied
ABANDON_MIN = 360             # 6 h après l'heure du run : on renonce et on l'écrit

# Marge appliquée sous la latence MINIMALE déjà observée pour décider
# quand commencer à guetter. Généreuse : rater le début d'une fenêtre
# coûte plus cher que quelques interrogations à 600 octets.
MARGE_APPRISE_MIN = 15
MIN_OBSERVATIONS = 5          # en-dessous, on ne fait confiance à rien


class Source:
    """Un flux de runs à guetter. Deux implémentations : le miroir S3 et
    le portail WCS. Elles ne partagent que cette interface, parce que
    tout le reste diffère — y compris ce que « publié » veut dire."""

    nom = "?"
    pas_h = 1

    def runs_recents(self, n=6, maintenant=None):
        """Les `n` derniers runs THÉORIQUES, du plus récent au plus ancien.
        Théoriques : c'est la grille des heures d'INITIALISATION, qui
        elle est régulière et documentée sans ambiguïté. Ce qui n'est pas
        connu, c'est quand ils sont MIS À DISPOSITION."""
        t = (maintenant or datetime.now(timezone.utc)).replace(
            minute=0, second=0, microsecond=0)
        t -= timedelta(hours=t.hour % self.pas_h)
        return [t - timedelta(hours=self.pas_h * k) for k in range(n)]

    def publie(self, run):
        raise NotImplementedError

    def preparer(self, runs_temoins):
        """Garde-fou à lancer AVANT de commencer à attendre."""


class SourceS3(Source):
    """AROME par le miroir OVH, sans clé.

    « Publié » signifie ici : le paquet couvre l'échéance 0. On ne
    demande PAS la couverture complète — c'est volontaire. La chaîne
    `arome-wind` a été mordue le 25/07 par l'inverse (un run pris dès
    qu'UN fichier existait, donc éternellement incomplet), mais ce
    module-ci ne publie rien : il DATE l'apparition. Confondre « le run
    commence à sortir » et « le run est complet » mélangerait deux
    latences très différentes, et c'est la première qu'on cherche.
    """

    pas_h = 3

    def __init__(self, paquet="HP1", grille="0025", echeance=0, modele="arome"):
        self.paquet, self.grille, self.echeance = paquet, grille, echeance
        self.modele = modele
        # ⚠️ Le nom porte le PAQUET, pas seulement le modèle. Sans ça, les
        # quatre paquets dont AGRUME a besoin se mélangeraient dans une
        # seule série de latences — et c'est justement leur ÉCART qu'on
        # cherche à mesurer.
        # ⚠️ ET L'ÉCHÉANCE, quand elle n'est pas 0 (14/08). « HP1 couvre
        # l'échéance 0 » et « HP1 couvre l'échéance 51 » sont deux
        # latences séparées de plusieurs heures ; sous un seul nom, le
        # journal les mélangerait, `debut_de_guet_min()` apprendrait une
        # fenêtre qui n'existe pas, et surtout `deja_vu()` prendrait
        # l'une pour l'autre — le second guet ne partirait jamais.
        # Le suffixe n'apparaît QUE pour une échéance non nulle : les
        # séries mesurées depuis le 10/08 gardent leur nom.
        self.nom = (f"{modele}:{grille}/{paquet}" if echeance == 0
                    else f"{modele}:{grille}/{paquet}@{echeance}")

    def publie(self, run):
        ref = run.strftime("%Y-%m-%dT%H:00:00Z")
        return bool(covered_steps(ref, self.paquet, self.grille,
                                  [self.echeance], model=self.modele))

    def __str__(self):
        return (f"S3 {self.modele}/{self.grille}/{self.paquet} "
                f"(échéance {self.echeance})")


# ⚠️ LES PAQUETS DONT L'INGESTION A BESOIN — et `choisir_run` exige leur
# couverture COMMUNE, donc l'ingestion avance au rythme du PLUS LENT.
# Lequel est-ce ? **Ce n'est pas mesuré**, et ça décide pourtant de la
# fraîcheur réelle d'AGRUME : si un seul paquet traîne d'une heure, il
# traîne toute la chaîne. Guetter chacun séparément ne coûte qu'un
# listing S3 par paquet et par cycle — quelques kilo-octets, aucun
# téléchargement.
# ⛔ LA LISTE VIENT DE `domaine.py`, PLUS D'ICI (audit du 13/08). Ce
# fichier en guettait QUATRE quand `ingest_colonnes.py` en exigeait
# HUIT — la liste d'avant les étapes 5, 12 et 12 bis, jamais rattrapée.
# Le dispatch partait donc dès les quatre anciens paquets : si
# IP1/IP2/SP1/SP2 0,025° n'étaient pas encore publiés, `choisir_run()`
# retenait un run PLUS ANCIEN. Perte de fraîcheur silencieuse — la
# seule chose qu'AGRUME apporte — et le voyant restait vert.
# `test_poller.py` verrouille la parité des deux listes.
PAQUETS_PRODUIT_A = PAQUETS_INGESTION

# ── ⛔ LE SECOND GUET : LA RALLONGE DU PRODUIT B (14/08/2026) ─────────
# Le guet ci-dessus déclenche dès que l'archive 0–24 h est complète, et
# c'est bien ce qu'on veut : la fraîcheur est la seule chose qu'AGRUME
# apporte. Mais `choisir_run()` cherche la rallonge (25 → 51 h) au même
# instant, et Météo-France ne l'a PAS ENCORE publiée — mesuré sur le run
# 15 Z du 13/08 : archive complète à 18:25:37 Z, rallonge complète à
# 18:53:29 Z. Le produit B sortait donc à +24 h à chaque run frais, et
# l'étape 14 n'avait jamais servi à personne.
#
# ⛔ CE N'EST PAS UN CRON. L'écart entre « archive prête » et « rallonge
# prête » va de 2 min à 3 h 33 sur les douze réseaux mesurés les 12 et
# 13/08 — une heure fixe raterait la moitié des runs, exactement la
# raison pour laquelle ce fichier existe (cf. l'en-tête de
# `bw-agrume-poller.service`).
#
# ⚠️ LES PAQUETS 0,025° SEULEMENT, et la parité avec `choisir_run()` est
# bancée : guetter la maille fine ferait attendre le second dispatch sur
# deux paquets que la rallonge ne lit pas.
PAQUETS_PRODUIT_B_RALLONGE = PAQUETS_RALLONGE
ECHEANCE_RALLONGE = MAX_HOURS_GRILLE


class SourcePortail(Source):
    """AROME-PI par le WCS. ⛔ Il n'y a pas d'autre route : le miroir S3
    publie `arome`, `arome-om`, `aromeifs`, `arpege`, `phealth` et
    `vague-surcote` — vérifié, AUCUN `aromepi` — et tous ses runs sont
    aux heures synoptiques, jamais horaires."""

    pas_h = 1

    # `u` n'a PAS de suffixe de cumul. ⚠️ Le GetCapabilities de PI décline
    # les champs cumulés et max en `_PT15M`, `_PT30M`, `_PT1H`, `_PT3H`,
    # `_PT6H` : `u`, `v` et `tke` n'en ont pas. Ne pas se laisser tromper
    # par le compte brut d'identifiants.
    CHAMP = "U_COMPONENT_OF_WIND__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND"

    def __init__(self, service=SERVICE_AROMEPI, grille="0025", champ=None,
                 pas_h=None, journal=print):
        self.service, self.grille = service, grille
        self.champ = champ or self.CHAMP
        self.nom = service
        if pas_h:
            self.pas_h = pas_h
        self.portail = Portail(service, grille, journal=journal)

    def preparer(self, runs_temoins):
        """⚠️ SANS CE GARDE-FOU, UNE FAUTE DE FRAPPE DEVIENT UNE ATTENTE
        INFINIE. Mesuré le 10/08 : un run futur et un nom de champ
        inventé rendent EXACTEMENT la même chose — HTTP 404,
        `exceptionCode="NoSuchCoverage"`. Rien dans la réponse ne
        distingue « pas encore publié » de « ça n'existe pas ». On vérifie
        donc d'abord que le champ répond sur un run forcément publié."""
        temoin = self.portail.valider_champ(
            self.champ, [r.strftime("%Y-%m-%dT%H:00:00Z") for r in runs_temoins])
        return temoin

    def publie(self, run):
        return self.portail.existe(self.champ,
                                   run.strftime("%Y-%m-%dT%H:00:00Z"))

    def __str__(self):
        return f"WCS {self.service}/{self.grille} · {self.champ}"


# ══════════════════════════════════════════════════════════════════════
#  Journal — la seule chose que ce module produit vraiment
# ══════════════════════════════════════════════════════════════════════
def lire_journal(chemin=JOURNAL_DEFAUT):
    p = Path(chemin)
    if not p.exists():
        return []
    out = []
    for ligne in p.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            out.append(json.loads(ligne))
        except json.JSONDecodeError:
            continue          # une ligne tronquée ne doit pas tout perdre
    return out


def ecrire_journal(entree, chemin=JOURNAL_DEFAUT):
    p = Path(chemin)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entree, ensure_ascii=False) + "\n")


def deja_vu(journal, source, run_iso):
    """Ce couple (source, run) est-il DÉCIDÉ — publié ou abandonné ?

    ⚠️ Il ne suffit PAS de compter les `publie`. Le 10/08, la version qui
    ne regardait que ceux-là a fait boucler le guet des paquets : un run
    abandonné n'étant jamais « déjà vu », le tour de rattrapage le
    reprenait à chaque cycle et réécrivait un abandon toutes les deux
    minutes. Le journal s'est rempli de doublons en quelques minutes, et
    la statistique qu'il porte s'en trouvait faussée d'autant.

    Un abandon est une décision, pas un échec à réessayer : le run est
    trop vieux pour être daté utilement, on l'a écrit, on passe.
    """
    return any(e.get("source") == source and e.get("run") == run_iso
               and e.get("etat") in ("publie", "abandon") for e in journal)


def latences_observees(journal, source):
    """Latences hautes (borne SUPÉRIEURE) déjà relevées, en minutes."""
    return sorted(e["latence_max_min"] for e in journal
                  if e.get("source") == source and e.get("etat") == "publie"
                  and isinstance(e.get("latence_max_min"), (int, float)))


def debut_de_guet_min(journal, source):
    """À combien de minutes après l'heure du run commencer à interroger.

    ⚠️ C'est APPRIS, jamais lu dans une doc. Tant qu'on a moins de
    `MIN_OBSERVATIONS` mesures, on guette dès l'heure du run — c'est un
    peu de gâchis (600 octets par interrogation) contre la certitude de
    ne pas rater le début de la fenêtre. Une fois qu'on sait, on démarre
    `MARGE_APPRISE_MIN` avant la latence la plus courte jamais vue.
    """
    obs = latences_observees(journal, source)
    if len(obs) < MIN_OBSERVATIONS:
        return 0
    return max(0, int(min(obs) - MARGE_APPRISE_MIN))


# ══════════════════════════════════════════════════════════════════════
def guetter(source, run, journal_entrees, chemin_journal=JOURNAL_DEFAUT,
            crier=print, dormir=time.sleep, maintenant=None,
            abandon_min=ABANDON_MIN):
    """Guette UN run jusqu'à ce qu'il apparaisse (ou qu'on renonce).

    Renvoie l'entrée de journal écrite.

    ⚠️ LA LATENCE EST UN INTERVALLE, PAS UN NOMBRE. On ne sait pas à
    quelle minute le run est apparu : on sait seulement qu'à `t_absent`
    il n'était pas là et qu'à `t_present` il y était. Écrire une valeur
    unique surestimerait la précision — c'est exactement l'erreur que la
    note de sondage reproche à l'observation « ≤ 71 min, n = 1 ». On
    journalise donc les DEUX bornes et leur écart.
    """
    now = maintenant or (lambda: datetime.now(timezone.utc))
    run_iso = run.strftime("%Y-%m-%dT%H:00:00Z")
    depart = debut_de_guet_min(journal_entrees, source.nom)
    periode = float(PERIODE_FINE_S)
    interrogations = 0
    t_absent = None

    t0 = now()
    ecoulees = (t0 - run).total_seconds() / 60.0
    if ecoulees < depart:
        attente = (depart - ecoulees) * 60
        crier(f"  ⏸ {source.nom} {run_iso} : rien avant H+{depart} min "
              f"(appris sur {len(latences_observees(journal_entrees, source.nom))} "
              f"observations) — sieste {attente / 60:.0f} min")
        dormir(attente)

    while True:
        t = now()
        ecoulees = (t - run).total_seconds() / 60.0

        # ⚠️ ON INTERROGE AVANT DE RENONCER, TOUJOURS. Le 10/08, une
        # première version testait la fenêtre d'abandon EN TÊTE de
        # boucle : au démarrage du service, un run vieux de 442 min a été
        # journalisé « toujours absent » — alors qu'il était publié
        # depuis des heures et qu'il venait de servir à une ingestion.
        # Le poller écrivait une affirmation qu'il n'avait jamais
        # vérifiée. Un run trop vieux ne donne qu'une borne très lâche,
        # mais une borne lâche reste vraie ; une absence inventée, non.
        interrogations += 1
        present = source.publie(run)

        if not present and ecoulees > abandon_min:
            entree = dict(
                source=source.nom, run=run_iso, etat="abandon",
                vu_a=t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                interrogations=interrogations,
                apres_min=round(ecoulees, 1),
                note=f"interrogé et ABSENT {abandon_min} min après l'heure "
                     f"du run")
            ecrire_journal(entree, chemin_journal)
            crier(f"  ⛔ {source.nom} {run_iso} : ABANDON après "
                  f"{ecoulees:.0f} min et {interrogations} interrogations")
            return entree

        if present:
            latence_max = ecoulees
            latence_min = ((t_absent - run).total_seconds() / 60.0
                           if t_absent else None)
            entree = dict(
                source=source.nom, run=run_iso, etat="publie",
                vu_a=t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                interrogations=interrogations,
                latence_max_min=round(latence_max, 1),
                latence_min_min=(round(latence_min, 1)
                                 if latence_min is not None else None),
                incertitude_min=(round(latence_max - latence_min, 1)
                                 if latence_min is not None else None),
                cible=str(source))
            ecrire_journal(entree, chemin_journal)
            if latence_min is None:
                crier(f"  ✅ {source.nom} {run_iso} : DÉJÀ là à la première "
                      f"interrogation — latence ≤ {latence_max:.0f} min "
                      f"(borne, pas mesure)")
            else:
                crier(f"  ✅ {source.nom} {run_iso} : apparu entre H+"
                      f"{latence_min:.0f} et H+{latence_max:.0f} min "
                      f"(±{(latence_max - latence_min) / 2:.0f} min, "
                      f"{interrogations} interrogations)")
            return entree

        t_absent = t
        if ecoulees > FENETRE_FINE_MIN:
            periode = min(periode * FACTEUR_BACKOFF, PERIODE_MAX_S)
        dormir(periode)


def guetter_plusieurs(sources, run, journal_entrees, chemin_journal=JOURNAL_DEFAUT,
                      crier=print, dormir=time.sleep, maintenant=None,
                      abandon_min=ABANDON_MIN):
    """Guette PLUSIEURS cibles sur le MÊME run, en une seule passe.

    ⚠️ POURQUOI PAS QUATRE POLLERS SÉPARÉS. Ce qu'on veut mesurer n'est
    pas la latence de chaque paquet dans l'absolu — c'est leur ÉCART. Or
    deux processus indépendants n'interrogent pas aux mêmes instants :
    une partie de l'écart mesuré viendrait alors de la désynchronisation
    des guets, pas de la publication. Ici les quatre sont interrogés dans
    le même cycle, donc l'écart mesuré est celui des paquets.

    ⚠️ Interrogation SÉQUENTIELLE dans le cycle, jamais en parallèle. Le
    portail coupe la connexion sous forte concurrence (mesuré : 102
    resets sur 200 requêtes à 40 fils), et rien ne dit que le miroir S3
    soit plus tolérant. Quatre listings de quelques kilo-octets ne
    justifient aucun parallélisme.

    Chaque cible garde son propre `t_absent` et son propre compteur, et
    sort de la ronde dès qu'elle est vue — les autres continuent.
    """
    now = maintenant or (lambda: datetime.now(timezone.utc))
    run_iso = run.strftime("%Y-%m-%dT%H:00:00Z")
    restantes = [s for s in sources if not deja_vu(journal_entrees, s.nom, run_iso)]
    if not restantes:
        return []
    etat = {s.nom: dict(t_absent=None, n=0) for s in restantes}
    periode = float(PERIODE_FINE_S)
    ecrites = []

    depart = min(debut_de_guet_min(journal_entrees, s.nom) for s in restantes)
    t0 = now()
    ecoulees = (t0 - run).total_seconds() / 60.0
    if ecoulees < depart:
        crier(f"  ⏸ {run_iso} : rien avant H+{depart} min sur aucune des "
              f"{len(restantes)} cibles — sieste "
              f"{(depart - ecoulees):.0f} min")
        dormir((depart - ecoulees) * 60)

    while restantes:
        t = now()
        ecoulees = (t - run).total_seconds() / 60.0
        trop_tard = ecoulees > abandon_min

        encore = []
        for s in restantes:
            etat[s.nom]["n"] += 1
            # ⚠️ Interroger AVANT de renoncer — cf. la note dans
            # `guetter()`. Écrire « absent » sans avoir demandé, c'est
            # inventer une mesure, et c'est arrivé.
            if not s.publie(run):
                etat[s.nom]["t_absent"] = t
                if trop_tard:
                    e = dict(source=s.nom, run=run_iso, etat="abandon",
                             vu_a=t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                             interrogations=etat[s.nom]["n"],
                             apres_min=round(ecoulees, 1),
                             note=f"interrogé et ABSENT {abandon_min} min "
                                  f"après l'heure du run")
                    ecrire_journal(e, chemin_journal)
                    ecrites.append(e)
                    crier(f"  ⛔ {s.nom} {run_iso} : ABANDON après "
                          f"{ecoulees:.0f} min")
                else:
                    encore.append(s)
                continue
            ta = etat[s.nom]["t_absent"]
            lat_min = (ta - run).total_seconds() / 60.0 if ta else None
            e = dict(source=s.nom, run=run_iso, etat="publie",
                     vu_a=t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                     interrogations=etat[s.nom]["n"],
                     latence_max_min=round(ecoulees, 1),
                     latence_min_min=(round(lat_min, 1)
                                      if lat_min is not None else None),
                     incertitude_min=(round(ecoulees - lat_min, 1)
                                      if lat_min is not None else None),
                     cible=str(s))
            ecrire_journal(e, chemin_journal)
            ecrites.append(e)
            if lat_min is None:
                crier(f"  ✅ {s.nom} {run_iso} : déjà là — ≤ {ecoulees:.0f} min "
                      f"(borne, pas mesure)")
            else:
                crier(f"  ✅ {s.nom} {run_iso} : entre H+{lat_min:.0f} et "
                      f"H+{ecoulees:.0f} min")
        restantes = encore
        if not restantes:
            break
        if ecoulees > FENETRE_FINE_MIN:
            periode = min(periode * FACTEUR_BACKOFF, PERIODE_MAX_S)
        dormir(periode)

    if len(ecrites) > 1:
        vus = [e for e in ecrites if e["etat"] == "publie"]
        if len(vus) > 1:
            hautes = [e["latence_max_min"] for e in vus]
            crier(f"  ⓘ écart entre le premier et le dernier paquet publié : "
                  f"{max(hautes) - min(hautes):.0f} min "
                  f"({min(vus, key=lambda e: e['latence_max_min'])['source']} "
                  f"→ {max(vus, key=lambda e: e['latence_max_min'])['source']})")
    return ecrites


def tour_paquets(sources, chemin_journal=JOURNAL_DEFAUT, crier=print,
                 dormir=time.sleep, profondeur=3):
    """Un tour sur le run le plus ancien encore incomplet."""
    entrees = lire_journal(chemin_journal)
    for run in reversed(sources[0].runs_recents(profondeur)):
        run_iso = run.strftime("%Y-%m-%dT%H:00:00Z")
        if all(deja_vu(entrees, s.nom, run_iso) for s in sources):
            continue
        return guetter_plusieurs(sources, run, entrees, chemin_journal,
                                 crier, dormir)
    crier("  · rien de nouveau à guetter")
    return []


def tour(source, chemin_journal=JOURNAL_DEFAUT, crier=print, dormir=time.sleep,
         profondeur=4):
    """Un tour : rattrape les runs récents non encore datés, puis guette
    le plus récent. Le rattrapage sert au redémarrage — un poller relancé
    ne doit pas laisser un trou dans la série."""
    entrees = lire_journal(chemin_journal)
    recents = source.runs_recents(profondeur)
    try:
        temoin = source.preparer(recents[1:])
        if temoin:
            crier(f"  ⓘ champ validé sur le run témoin {temoin}")
    except ErreurPortail as e:
        crier(f"  ❌ {e}")
        return None
    for run in reversed(recents):
        run_iso = run.strftime("%Y-%m-%dT%H:00:00Z")
        if deja_vu(entrees, source.nom, run_iso):
            continue
        return guetter(source, run, entrees, chemin_journal, crier, dormir)
    crier("  · rien de nouveau à guetter")
    return None


def rapport(chemin_journal=JOURNAL_DEFAUT, crier=print):
    entrees = lire_journal(chemin_journal)
    if not entrees:
        crier("Journal vide — aucune latence mesurée pour l'instant. "
              "C'est le résultat honnête tant que le poller n'a pas tourné.")
        return 0
    sources = sorted({e.get("source", "?") for e in entrees})
    crier(f"── LATENCE DE MISE À DISPOSITION, {len(entrees)} entrées ──")
    for s in sources:
        pub = [e for e in entrees if e.get("source") == s
               and e.get("etat") == "publie"]
        aband = [e for e in entrees if e.get("source") == s
                 and e.get("etat") == "abandon"]
        if not pub:
            crier(f"\n{s} : aucune publication datée "
                  f"({len(aband)} abandons)")
            continue
        hautes = sorted(e["latence_max_min"] for e in pub)
        bornees = [e for e in pub if e.get("latence_min_min") is not None]
        n = len(hautes)
        def q(p):
            return hautes[min(n - 1, int(p * n))]
        crier(f"\n{s} — n = {n} runs datés"
              + (f", dont {len(bornees)} ENCADRÉS" if bornees else ""))
        crier(f"  borne haute (min) : min {hautes[0]:.0f} · médiane "
              f"{q(0.5):.0f} · d9 {q(0.9):.0f} · max {hautes[-1]:.0f}")
        if bornees:
            inc = [e["incertitude_min"] for e in bornees]
            crier(f"  incertitude de l'encadrement : médiane "
                  f"{sorted(inc)[len(inc) // 2]:.0f} min")
        else:
            crier("  ⚠️ aucune mesure ENCADRÉE : toutes les valeurs sont des "
                  "bornes supérieures (le run était déjà là à la première "
                  "interrogation). Ce ne sont PAS des latences.")
        if aband:
            crier(f"  ⛔ {len(aband)} runs jamais apparus dans la fenêtre")
        crier(f"  → prochain guet à partir de H+"
              f"{debut_de_guet_min(entrees, s)} min")
    rapport_ecart_paquets(entrees, crier)
    return 0


def rapport_ecart_paquets(entrees, crier=print):
    """⚠️ LE CHIFFRE QUI DÉCIDE DE LA FRAÎCHEUR D'AGRUME.

    `ingest_colonnes.choisir_run()` exige la couverture COMMUNE aux
    quatre paquets : l'ingestion avance donc au rythme du PLUS LENT. Si
    un seul paquet traîne d'une heure, il traîne toute la chaîne — et on
    ne le verrait nulle part ailleurs, puisque le run finit par être
    complet et que tout a l'air normal.

    On ne compare QUE des cibles vues dans le même run et dans le même
    cycle de guet : comparer des paquets datés par des processus
    différents mélangerait l'écart de publication avec l'écart des guets.
    """
    par_run = {}
    for e in entrees:
        s = e.get("source", "")
        if e.get("etat") != "publie" or ":" not in s:
            continue
        par_run.setdefault(e["run"], {})[s] = e["latence_max_min"]
    complets = {r: d for r, d in par_run.items() if len(d) > 1}
    if not complets:
        return
    crier(f"\n── ÉCART DE PUBLICATION ENTRE PAQUETS ({len(complets)} runs) ──")
    noms = sorted({s for d in complets.values() for s in d})
    for nom in noms:
        vals = sorted(d[nom] for d in complets.values() if nom in d)
        crier(f"  {nom:<22} borne haute médiane {vals[len(vals) // 2]:6.0f} min "
              f"(n = {len(vals)})")
    ecarts = sorted(max(d.values()) - min(d.values()) for d in complets.values())
    med = ecarts[len(ecarts) // 2]
    crier(f"  → écart premier/dernier paquet : médiane {med:.0f} min · "
          f"max {ecarts[-1]:.0f} min")
    lents = {}
    for d in complets.values():
        lents[max(d, key=d.get)] = lents.get(max(d, key=d.get), 0) + 1
    crier("  → le plus lent est " + ", ".join(
        f"{k} ({v}×)" for k, v in sorted(lents.items(), key=lambda x: -x[1])))
    if all(e == 0 for e in ecarts):
        crier("  ⚠️ écart nul partout : soit les paquets sortent vraiment "
              "ensemble, soit la période de guet est trop grossière pour les "
              "séparer. Un zéro n'est pas une mesure de simultanéité.")


# ══════════════════════════════════════════════════════════════════════
def dispatch_github(depot, workflow, ref="main", entrees=None, crier=print):
    """Déclenche un `workflow_dispatch`. Optionnel, et volontairement
    minimal : le VPS décide QUAND, l'Action fait le travail.

    ⚠️ Le jeton se lit dans l'environnement et n'est jamais journalisé.
    Sans jeton, on ne déclenche rien et on le DIT — un dispatch qui échoue
    en silence donnerait un poller qui a l'air de marcher et une chaîne
    qui ne tourne jamais.
    """
    jeton = os.environ.get("GITHUB_DISPATCH_TOKEN")
    if not jeton:
        crier("  ⚠️ GITHUB_DISPATCH_TOKEN absent — aucun déclenchement "
              "(le run a bien été daté, mais rien n'a été lancé)")
        return False
    url = (f"https://api.github.com/repos/{depot}/actions/workflows/"
           f"{workflow}/dispatches")
    corps = json.dumps({"ref": ref, "inputs": entrees or {}}).encode()
    req = urllib.request.Request(url, data=corps, method="POST", headers={
        "Authorization": f"Bearer {jeton}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            crier(f"  ▶ workflow {workflow} déclenché (HTTP {r.status})")
            return True
    except urllib.error.HTTPError as e:
        crier(f"  ❌ dispatch refusé : HTTP {e.code} "
              f"{e.read()[:200].decode('utf-8', 'replace')}")
        return False


def fabriquer_source(nom, journal=print):
    if nom == "arome":
        return SourceS3()
    if nom == "arome-paquets":
        return [SourceS3(paquet=p, grille=g) for g, p in PAQUETS_PRODUIT_A]
    if nom == "arome-rallonge":
        # ⚠️ MÊME workflow déclenché que `arome-paquets`, et c'est voulu :
        # l'ingestion revérifie de toute façon la couverture réelle et
        # reprendra la rallonge d'elle-même. Un second point d'entrée
        # « qui ne ferait que la rallonge » aurait demandé un second
        # chemin d'écriture du produit B — deux façons d'écrire le même
        # objet, c'est-à-dire deux façons de se tromper.
        return [SourceS3(paquet=p, grille=g, echeance=ECHEANCE_RALLONGE)
                for g, p in PAQUETS_PRODUIT_B_RALLONGE]
    if nom == "aromepi":
        return SourcePortail(SERVICE_AROMEPI, "0025", journal=journal)
    if nom == "arome-wcs":
        # Utile pour comparer les DEUX routes sur le MÊME modèle : le
        # portail et le miroir ne publient pas forcément au même moment,
        # et personne ne l'a mesuré.
        return SourcePortail(SERVICE_AROME, "0025", pas_h=3, journal=journal)
    raise SystemExit(f"source inconnue : {nom}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", default="aromepi",
                   choices=("aromepi", "arome", "arome-wcs", "arome-paquets",
                            "arome-rallonge"))
    p.add_argument("--journal", default=str(JOURNAL_DEFAUT))
    p.add_argument("--une-fois", action="store_true",
                   help="guette un seul run puis sort (mode cron)")
    p.add_argument("--boucle", action="store_true",
                   help="tourne indéfiniment (mode service)")
    p.add_argument("--rapport", action="store_true",
                   help="n'interroge rien, affiche ce qui a été mesuré")
    p.add_argument("--dispatch", default=None,
                   help="dépôt/workflow à déclencher, ex. "
                        "biozarb/balise-watch-server:agrume.yml")
    a = p.parse_args(argv)

    if a.rapport:
        return rapport(a.journal)

    source = fabriquer_source(a.source)
    if isinstance(source, list):
        print("▶ guet simultané de " + ", ".join(s.nom for s in source))
        while True:
            ecrites = tour_paquets(source, a.journal)
            # ⚠️ Le dispatch n'a lieu que quand TOUS les paquets sont là :
            # `choisir_run()` exige leur couverture commune, déclencher
            # plus tôt donnerait un run que l'ingestion refuserait.
            if a.dispatch and ecrites and all(e.get("etat") == "publie"
                                              for e in ecrites):
                depot, _, wf = a.dispatch.partition(":")
                dispatch_github(depot, wf, entrees={"run": ecrites[0]["run"]})
            if a.une_fois or not a.boucle:
                return 0
            time.sleep(PERIODE_FINE_S)

    print(f"▶ guet : {source}")
    while True:
        entree = tour(source, a.journal)
        if entree and entree.get("etat") == "publie" and a.dispatch:
            depot, _, wf = a.dispatch.partition(":")
            dispatch_github(depot, wf, entrees={"run": entree["run"]})
        if a.une_fois or not a.boucle:
            return 0
        time.sleep(PERIODE_FINE_S)


if __name__ == "__main__":
    sys.exit(main())
