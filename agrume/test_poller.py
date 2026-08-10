#!/usr/bin/env python3
"""
test_poller.py — banc du poller et du client portail, HORS-LIGNE.

    python3 agrume/test_poller.py

⚠️ CE QUE CE BANC PROTÈGE. Le poller a un mode de panne qui ne s'annonce
pas : ATTENDRE POUR TOUJOURS. Le portail rend la même réponse — HTTP 404,
`exceptionCode="NoSuchCoverage"` — pour « ce run n'est pas encore
publié » et pour « ce champ n'existe pas » (mesuré le 10/08 : un run
futur et un nom inventé, réponses identiques au `locator` près). Un
poller sans garde-fou tournerait donc indéfiniment sur une faute de
frappe, en journalisant patiemment des absences.

Le second risque est plus insidieux : mesurer une latence qu'on n'a pas
mesurée. Si le run est déjà là à la PREMIÈRE interrogation, on ne connaît
qu'une BORNE SUPÉRIEURE — c'est exactement le défaut de l'observation
« ≤ 71 min, n = 1 » du sondage. Le banc vérifie que le journal distingue
les deux cas et ne fabrique jamais un encadrement qu'il n'a pas.

Aucun réseau, aucune clé : horloge et sommeil sont injectés.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

import poller as P  # noqa: E402
import portail as W  # noqa: E402

echecs = []


def verifier(nom, condition, detail=""):
    print(f"  {'✓' if condition else '✗'} {nom}" + (f"   {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


# Corps d'erreur RÉELS, copiés d'une réponse du portail le 10/08/2026.
CORPS_404_ABSENT = (
    '<?xml version="1.0" encoding="UTF-8"?><mw:fault '
    'xmlns:mw="http://metwork-framework.org/"><mw:code>868404</mw:code>'
    '<mw:message>Synopsis backend error</mw:message><mw:description>'
    '<ns0:ExceptionReport xmlns:ns0="http://www.opengis.net/ows/1.1" '
    'version="1.1.0">\n    <ns0:Exception exceptionCode="NoSuchCoverage" '
    'locator="U__HEIGHT___2026-08-10T10.00.00Z"><ns0:ExceptionText />'
    '</ns0:Exception>\n</ns0:ExceptionReport></mw:description></mw:fault>')
CORPS_404_PARAM = (
    '<ns0:ExceptionReport xmlns:ns0="http://www.opengis.net/ows/1.1">'
    '<ns0:Exception exceptionCode="emptyCoverageIdList" locator="coverageId">'
    '<ns0:ExceptionText>At least one coverage identifier is required'
    '</ns0:ExceptionText></ns0:Exception></ns0:ExceptionReport>')


class Horloge:
    """Horloge et sommeil simulés : le banc doit tourner en millisecondes,
    pas en heures."""

    def __init__(self, depart):
        self.t = depart
        self.dormi = []

    def maintenant(self):
        return self.t

    def dormir(self, s):
        self.dormi.append(s)
        self.t += timedelta(seconds=s)


class SourceFactice(P.Source):
    """Publie à `apparait_a`, pas avant."""

    pas_h = 1

    def __init__(self, horloge, apparait_a, nom="factice"):
        self.h, self.apparait_a, self.nom = horloge, apparait_a, nom
        self.interrogations = 0

    def publie(self, run):
        self.interrogations += 1
        return self.h.t >= self.apparait_a

    def __str__(self):
        return "source factice"


def main():
    print("── Lecture des corps d'erreur du portail ──────────────────")
    exc, msg = W._lire_exception_wcs(CORPS_404_ABSENT)
    verifier("un 404 « run absent » se lit NoSuchCoverage",
             exc == "NoSuchCoverage", f"{exc} · {msg}")
    exc2, msg2 = W._lire_exception_wcs(CORPS_404_PARAM)
    verifier("un 404 « paramètre manquant » N'EST PAS NoSuchCoverage",
             exc2 == "emptyCoverageIdList", f"{exc2} · {msg2}")
    verifier("le message OGC est extrait quand il existe",
             "coverage identifier" in msg2)
    verifier("un corps illisible ne fait pas lever",
             W._lire_exception_wcs("<<< tronqué") == (None, ""))

    print("\n── Les pièges du portail sont câblés, pas commentés ───────")
    verifier("piège 3 : subset temps SANS guillemets",
             '"' not in W.subset_temps("2026-08-10T12:00:00Z"),
             W.subset_temps("2026-08-10T12:00:00Z"))
    verifier("piège 4 : le format est wmo-grib, pas wmo-grib2",
             W.FORMAT_GRIB == "application/wmo-grib")
    verifier("piège 5 : le /1.0/ est dans le chemin", "/1.0/" in W.BASE)
    verifier("piège 6 : le service est `aromepi` en un mot",
             W.SERVICE_AROMEPI == "aromepi")
    verifier("l'identifiant de couverture porte des POINTS, pas des `:`",
             W.Portail.id_couverture("U", "2026-08-10T08:00:00Z")
             == "U___2026-08-10T08.00.00Z")
    verifier("le sous-domaine se demande en lat/long",
             W.subset_boite(44.8, 46.3, 5.5, 7.6)
             == "lat(44.8,46.3)&subset=long(5.5,7.6)")
    verifier("AROME-PI 0,01° n'est pas proposé comme source de vent "
             "(c'est un produit « danger », sans vent moyen)",
             (W.SERVICE_AROMEPI, "001") in W.COUVERTURES)
    verifier("quotas séparés par défaut (mesuré le 10/08 : AROME 429 "
             "pendant que PI répondait 200)", W.POOL_COMMUN is False)

    print("\n── Journal : écriture, relecture, robustesse ──────────────")
    with tempfile.TemporaryDirectory() as d:
        j = Path(d) / "lat.ndjson"
        P.ecrire_journal(dict(source="aromepi", run="R1", etat="publie",
                              latence_max_min=42.0), j)
        P.ecrire_journal(dict(source="aromepi", run="R2", etat="abandon"), j)
        with j.open("a", encoding="utf-8") as f:
            f.write('{"tronqué": \n')          # ligne abîmée volontairement
        P.ecrire_journal(dict(source="arome", run="R3", etat="publie",
                              latence_max_min=95.0), j)
        e = P.lire_journal(j)
        verifier("une ligne abîmée ne fait pas perdre les autres",
                 len(e) == 3, f"{len(e)} entrées relues")
        verifier("deja_vu ne confond pas publie et abandon",
                 P.deja_vu(e, "aromepi", "R1")
                 and not P.deja_vu(e, "aromepi", "R2"))
        verifier("les latences sont lues par source",
                 P.latences_observees(e, "aromepi") == [42.0])
        verifier("journal absent → liste vide, pas d'exception",
                 P.lire_journal(Path(d) / "rien.ndjson") == [])

    print("\n── Le début du guet est APPRIS, pas codé en dur ───────────")
    verifier("moins de 5 observations → on guette dès H+0",
             P.debut_de_guet_min([], "aromepi") == 0)
    peu = [dict(source="aromepi", etat="publie", latence_max_min=v)
           for v in (40, 44, 50)]
    verifier("3 observations, c'est encore trop peu",
             P.debut_de_guet_min(peu, "aromepi") == 0,
             f"{P.debut_de_guet_min(peu, 'aromepi')}")
    assez = [dict(source="aromepi", etat="publie", latence_max_min=v)
             for v in (40, 44, 50, 55, 61, 47)]
    verifier("6 observations → départ 15 min sous la plus courte",
             P.debut_de_guet_min(assez, "aromepi") == 25,
             f"min observé 40 → départ H+{P.debut_de_guet_min(assez, 'aromepi')}")
    tot = [dict(source="aromepi", etat="publie", latence_max_min=v)
           for v in (5, 6, 7, 8, 9, 10)]
    verifier("jamais de départ négatif",
             P.debut_de_guet_min(tot, "aromepi") == 0)

    print("\n── ⚠️ La latence est un INTERVALLE, jamais un nombre ──────")
    run = datetime(2026, 8, 10, 8, 0, tzinfo=timezone.utc)
    with tempfile.TemporaryDirectory() as d:
        j = Path(d) / "lat.ndjson"
        h = Horloge(run)                      # on guette dès l'heure du run
        src = SourceFactice(h, run + timedelta(minutes=41))
        e = P.guetter(src, run, [], j, crier=lambda *a: None,
                      dormir=h.dormir, maintenant=h.maintenant)
        verifier("run encadré : deux bornes ET une incertitude",
                 e["latence_min_min"] is not None
                 and e["latence_max_min"] is not None
                 and e["incertitude_min"] is not None,
                 f"entre H+{e['latence_min_min']:.0f} et "
                 f"H+{e['latence_max_min']:.0f} min")
        verifier("l'encadrement contient la vérité (41 min)",
                 e["latence_min_min"] <= 41 <= e["latence_max_min"])
        verifier("l'incertitude vaut la période de guet",
                 abs(e["incertitude_min"] - P.PERIODE_FINE_S / 60) < 0.2,
                 f"{e['incertitude_min']} min")
        verifier("le nombre d'interrogations est journalisé",
                 e["interrogations"] == src.interrogations)

        h2 = Horloge(run + timedelta(minutes=90))
        src2 = SourceFactice(h2, run, nom="deja")
        e2 = P.guetter(src2, run, [], j, crier=lambda *a: None,
                       dormir=h2.dormir, maintenant=h2.maintenant)
        verifier("run DÉJÀ là à la 1re interrogation → borne SEULE, "
                 "aucun encadrement inventé",
                 e2["latence_min_min"] is None
                 and e2["incertitude_min"] is None
                 and e2["latence_max_min"] == 90.0,
                 f"≤ {e2['latence_max_min']:.0f} min")

    print("\n── Back-off borné, et abandon écrit ──────────────────────")
    with tempfile.TemporaryDirectory() as d:
        j = Path(d) / "lat.ndjson"
        h = Horloge(run)
        src = SourceFactice(h, run + timedelta(days=9))   # n'arrive jamais
        e = P.guetter(src, run, [], j, crier=lambda *a: None,
                      dormir=h.dormir, maintenant=h.maintenant)
        verifier("un run qui n'arrive jamais finit en `abandon` écrit",
                 e["etat"] == "abandon", f"{e['apres_min']:.0f} min")
        verifier("⚠️ l'abandon dit qu'on a INTERROGÉ, pas qu'on a supposé",
                 "interrogé et ABSENT" in e["note"] and e["interrogations"] > 1,
                 f"{e['interrogations']} interrogations")
        verifier("l'abandon tombe bien à la limite annoncée",
                 P.ABANDON_MIN <= e["apres_min"] <= P.ABANDON_MIN + 20)
        verifier("le back-off est BORNÉ",
                 max(h.dormi) <= P.PERIODE_MAX_S, f"max {max(h.dormi):.0f} s")
        verifier("le guet reste FIN dans la fenêtre plausible",
                 all(s == P.PERIODE_FINE_S for s in h.dormi[:5]),
                 f"{h.dormi[:3]}")
        verifier("le back-off finit par lever le pied",
                 h.dormi[-1] > h.dormi[0])
        verifier("l'abandon est relu comme tel",
                 P.lire_journal(j)[0]["etat"] == "abandon")

    # ⚠️ LE CAS QUI A MORDU LE 10/08 : un poller démarré longtemps après
    # l'heure du run. Une première version testait la fenêtre d'abandon
    # EN TÊTE de boucle et journalisait « toujours absent » un run publié
    # depuis des heures — sans l'avoir interrogé une seule fois.
    with tempfile.TemporaryDirectory() as d:
        j = Path(d) / "l.ndjson"
        h = Horloge(run + timedelta(minutes=442))     # démarrage très tardif
        src = SourceFactice(h, run, nom="tardif")     # publié depuis longtemps
        e = P.guetter(src, run, [], j, crier=lambda *a: None,
                      dormir=h.dormir, maintenant=h.maintenant)
        verifier("⚠️ un run déjà publié n'est JAMAIS journalisé « abandon », "
                 "même découvert 442 min trop tard",
                 e["etat"] == "publie", e["etat"])
        verifier("il ne donne qu'une borne très lâche — mais une borne vraie",
                 e["latence_min_min"] is None and e["latence_max_min"] == 442.0,
                 f"≤ {e['latence_max_min']:.0f} min")

    with tempfile.TemporaryDirectory() as d:
        j = Path(d) / "l.ndjson"
        h = Horloge(run + timedelta(minutes=442))
        cibles = [SourceFactice(h, run, nom="a"),
                  SourceFactice(h, run + timedelta(days=9), nom="b")]
        ecrites = P.guetter_plusieurs(cibles, run, [], j,
                                      crier=lambda *a: None, dormir=h.dormir,
                                      maintenant=h.maintenant)
        etats = {e["source"]: e["etat"] for e in ecrites}
        verifier("en guet simultané aussi : le publié est publié, "
                 "l'absent est abandonné",
                 etats == {"a": "publie", "b": "abandon"}, str(etats))
        verifier("le run trop vieux ne fait pas boucler : une passe suffit",
                 len(ecrites) == 2 and all(x["interrogations"] == 1
                                           for x in ecrites),
                 str([x["interrogations"] for x in ecrites]))

    print("\n── La grille des runs théoriques ─────────────────────────")
    t = datetime(2026, 8, 10, 9, 47, tzinfo=timezone.utc)
    s3 = P.SourceS3()
    r = s3.runs_recents(3, maintenant=t)
    verifier("AROME : runs toutes les 3 h, alignés sur les synoptiques",
             [x.hour for x in r] == [9, 6, 3], str([x.hour for x in r]))
    verifier("le plus récent est en tête", r[0] > r[1] > r[2])

    class PIfactice(P.SourcePortail):
        def __init__(self):                    # sans clé, sans réseau
            self.service, self.grille = "aromepi", "0025"
            self.champ, self.nom = self.CHAMP, "aromepi"
    r = PIfactice().runs_recents(3, maintenant=t)
    verifier("AROME-PI : runs HORAIRES (24 mesures/jour au lieu de 8)",
             [x.hour for x in r] == [9, 8, 7], str([x.hour for x in r]))

    print("\n── ⚠️ Le garde-fou contre l'attente infinie ───────────────")
    class PortailMuet:
        service, grille = "aromepi", "0025"
        def __init__(self):
            self.vus = []
        def describe(self, champ, run):
            self.vus.append(run)
            raise W.CouvertureAbsente("NoSuchCoverage",
                                      exception_wcs="NoSuchCoverage")
        def valider_champ(self, champ, runs):
            return W.Portail.valider_champ(self, champ, runs)

    src = PIfactice()
    src.portail = PortailMuet()
    try:
        src.preparer([datetime(2026, 8, 10, h_, tzinfo=timezone.utc)
                      for h_ in (7, 6, 5)])
        verifier("un champ qui ne répond sur AUCUN run témoin fait LEVER",
                 False)
    except W.ErreurPortail as e:
        verifier("un champ qui ne répond sur AUCUN run témoin fait LEVER",
                 "NOM DE CHAMP FAUX" in str(e))
        verifier("tous les runs témoins ont bien été essayés",
                 len(src.portail.vus) == 3, f"{len(src.portail.vus)}")

    class PortailBavard(PortailMuet):
        def describe(self, champ, run):
            self.vus.append(run)
            if run.endswith("06:00:00Z"):
                return "ok"
            raise W.CouvertureAbsente("NoSuchCoverage")
    src2 = PIfactice()
    src2.portail = PortailBavard()
    temoin = src2.preparer([datetime(2026, 8, 10, h_, tzinfo=timezone.utc)
                            for h_ in (7, 6, 5)])
    verifier("un seul run témoin qui répond suffit à valider le champ",
             temoin.endswith("06:00:00Z"), temoin)

    print("\n── ⚠️ Guet SIMULTANÉ des quatre paquets du produit A ──────")
    # `choisir_run()` exige la couverture COMMUNE aux quatre : l'ingestion
    # avance au rythme du plus lent. C'est leur ÉCART qu'on mesure, donc
    # ils doivent être interrogés dans le MÊME cycle — sinon une part de
    # l'écart viendrait de la désynchronisation des guets.
    verifier("les quatre paquets du produit A sont déclarés",
             P.PAQUETS_PRODUIT_A == (("0025", "HP1"), ("0025", "HP2"),
                                     ("001", "HP1"), ("001", "SP1")))
    quatre = P.fabriquer_source("arome-paquets")
    verifier("`arome-paquets` fabrique bien quatre cibles distinctes",
             len({s.nom for s in quatre}) == 4,
             ", ".join(s.nom for s in quatre))
    verifier("le nom porte le paquet, pas seulement le modèle",
             quatre[0].nom == "arome:0025/HP1", quatre[0].nom)
    verifier("les quatre suivent la grille de runs à 3 h",
             all(s.pas_h == 3 for s in quatre))

    with tempfile.TemporaryDirectory() as d:
        j = Path(d) / "l.ndjson"
        h = Horloge(run)
        # HP1 sort à +30, SP1 à +34, HP2 à +52, 001/HP1 à +58.
        retards = {"arome:0025/HP1": 30, "arome:001/SP1": 34,
                   "arome:0025/HP2": 52, "arome:001/HP1": 58}
        cibles = [SourceFactice(h, run + timedelta(minutes=m), nom=n)
                  for n, m in retards.items()]
        ecrites = P.guetter_plusieurs(cibles, run, [], j,
                                      crier=lambda *a: None, dormir=h.dormir,
                                      maintenant=h.maintenant)
        verifier("les quatre sont datés en une seule ronde",
                 len(ecrites) == 4 and all(e["etat"] == "publie" for e in ecrites))
        par_nom = {e["source"]: e for e in ecrites}
        verifier("chacun est encadré autour de son vrai retard",
                 all(par_nom[n]["latence_min_min"] <= m <= par_nom[n]["latence_max_min"]
                     for n, m in retards.items()),
                 " · ".join(f"{n.split('/')[-1]} "
                            f"{par_nom[n]['latence_min_min']:.0f}-"
                            f"{par_nom[n]['latence_max_min']:.0f}"
                            for n in retards))
        verifier("⚠️ le plus lent est bien identifié (c'est lui qui bride "
                 "toute la chaîne)",
                 max(par_nom, key=lambda n: par_nom[n]["latence_max_min"])
                 == "arome:001/HP1")
        vus = sorted(e["latence_max_min"] for e in ecrites)
        verifier("l'écart premier/dernier est retrouvé (28 min attendus)",
                 abs((vus[-1] - vus[0]) - 28) <= P.PERIODE_FINE_S / 60,
                 f"{vus[-1] - vus[0]:.0f} min")
        verifier("une cible vue tôt cesse d'être interrogée",
                 par_nom["arome:0025/HP1"]["interrogations"]
                 < par_nom["arome:001/HP1"]["interrogations"],
                 f"{par_nom['arome:0025/HP1']['interrogations']} contre "
                 f"{par_nom['arome:001/HP1']['interrogations']}")
        # Un second passage ne doit rien redater.
        verifier("un tour de rattrapage ne redate pas ce qui est déjà daté",
                 P.guetter_plusieurs(cibles, run, P.lire_journal(j), j,
                                     crier=lambda *a: None, dormir=h.dormir,
                                     maintenant=h.maintenant) == [])

        lignes = []
        P.rapport_ecart_paquets(P.lire_journal(j), crier=lignes.append)
        texte = "\n".join(lignes)
        verifier("le rapport nomme le paquet le plus lent",
                 "le plus lent est arome:001/HP1" in texte)
        verifier("le rapport donne la médiane de l'écart",
                 "écart premier/dernier paquet" in texte)

    with tempfile.TemporaryDirectory() as d:
        j = Path(d) / "l.ndjson"
        h = Horloge(run)
        memes = [SourceFactice(h, run + timedelta(minutes=40), nom=f"arome:g/p{k}")
                 for k in range(3)]
        P.guetter_plusieurs(memes, run, [], j, crier=lambda *a: None,
                            dormir=h.dormir, maintenant=h.maintenant)
        lignes = []
        P.rapport_ecart_paquets(P.lire_journal(j), crier=lignes.append)
        verifier("⚠️ un écart nul est signalé comme AMBIGU, pas comme une "
                 "preuve de simultanéité",
                 any("n'est pas une mesure de simultanéité" in x for x in lignes))

    print("\n── Le rapport ne fabrique rien ───────────────────────────")
    lignes = []
    with tempfile.TemporaryDirectory() as d:
        P.rapport(Path(d) / "vide.ndjson", crier=lignes.append)
    verifier("journal vide → on le dit, on n'invente pas de statistique",
             any("Journal vide" in x for x in lignes))
    lignes = []
    with tempfile.TemporaryDirectory() as d:
        j = Path(d) / "l.ndjson"
        for v in (40, 44, 50):
            P.ecrire_journal(dict(source="aromepi", run=f"R{v}",
                                  etat="publie", latence_max_min=v), j)
        P.rapport(j, crier=lignes.append)
    verifier("sans encadrement, le rapport REFUSE d'appeler ça une latence",
             any("PAS des latences" in x for x in lignes))

    print("\n  poller :", "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
