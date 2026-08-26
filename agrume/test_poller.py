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


# ══════════════════════════════════════════════════════════════════════
#  ⛔ LA RALLONGE DU PRODUIT B — LE SECOND GUET ET SON JUMEAU
# ══════════════════════════════════════════════════════════════════════
def banc_rallonge():
    """Ce que ce banc protège, et pourquoi il n'existait pas avant.

    L'étape 14 a écrit la rallonge 25 → 51 h, l'a documentée sur trois
    pages, et elle n'a JAMAIS servi : elle est cherchée à l'instant du
    dispatch, c'est-à-dire avant que Météo-France ait publié les
    échéances lointaines. Rien ne le disait — le message est un ⓘ, le
    run est vert, la coupe s'arrête simplement un jour plus tôt.

    ⛔ ET LE SEUL SYMPTÔME VISIBLE ÉTAIT À L'ÉCRAN. C'est exactement le
    jumeau du 6ᵉ argument du 13/08 : un chemin construit, mesuré,
    documenté, et jamais emprunté, parce que rien ne lève quand il ne
    l'est pas. Les trois contrôles ci-dessous sont donc écrits pour
    ÉCHOUER sur le code d'avant.
    """
    from ingest_colonnes import choisir_run  # noqa: PLC0415
    import domaine as D  # noqa: PLC0415

    print("\n── ⛔ La rallonge du produit B (25 → 51 h) ────────────────")

    verifier("⛔ la rallonge n'exige QUE des paquets 0,025° — la maille "
             "fine s'arrête à l'horizon de l'archive",
             all(g == D.GRID_3D for g, _ in D.PAQUETS_RALLONGE)
             and len(D.PAQUETS_RALLONGE) < len(D.PAQUETS_INGESTION),
             f"{len(D.PAQUETS_RALLONGE)} sur {len(D.PAQUETS_INGESTION)}")
    verifier("…et elle est DÉRIVÉE de la liste d'ingestion, pas recopiée "
             "(un paquet 0,025° ajouté entre tout seul)",
             set(D.PAQUETS_RALLONGE)
             == {(g, p) for g, p in D.PAQUETS_INGESTION if g == D.GRID_3D})

    # ── Un S3 factice : chaque (grille, paquet) publie jusqu'à N h ────
    maintenant = datetime(2026, 8, 13, 18, 29, tzinfo=timezone.utc)
    frais = "2026-08-13T15:00:00Z"

    def couverture_a(horizons, partout=False):
        """`horizons[(grille, paquet)] = dernière échéance publiée`.

        ⚠️ Le réseau de 18 Z existe DÉJÀ dans la grille théorique à
        18:29 Z, et Météo-France n'en a pas encore publié un octet —
        c'est la situation réelle, et l'oublier ferait bancer un run qui
        n'existe pas. Plus récent que `frais` → ABSENT ; plus ancien →
        complet ; `frais` → ce que dit `horizons`.

        `partout=True` applique `horizons` à tous les runs publiés :
        indispensable quand le run frais est INCOMPLET, sinon
        `choisir_run()` se rabat sur un run plus ancien réputé parfait
        et on bance autre chose que ce qu'on croit."""
        vus = []

        def couvre(ref, paquet, grille, steps, model=None):
            vus.append((ref, grille, paquet, max(steps)))
            if ref > frais:
                return set()               # réseau pas encore publié
            if ref < frais and not partout:
                return set(steps)          # les vieux runs sont complets
            h = horizons.get((grille, paquet), 24)
            return {s for s in steps if s <= h}
        return couvre, vus

    # 1. LE CAS RÉEL DU 13/08 : archive complète, rallonge pas encore là.
    couvre, vus = couverture_a({})
    ref, _run, steps = choisir_run(24, crier=lambda *a: None,
                                   max_heures_grille=51, couverture=couvre,
                                   maintenant=maintenant)
    verifier("run frais retenu même sans rallonge (la fraîcheur d'abord)",
             ref == frais, ref)
    verifier("…et la coupe s'arrête à +24 h — le défaut MESURÉ le 13/08 "
             "à 18:29:12 Z",
             steps == list(range(25)), f"{len(steps)} échéances")
    verifier("⛔ aucun run PLUS ANCIEN n'est même interrogé dès qu'un run "
             "complet est trouvé — la rallonge ne peut donc PAS voler le "
             "choix du run à la fraîcheur",
             min(r for r, _, _, _ in vus) == frais,
             ", ".join(sorted({r for r, _, _, _ in vus})))

    # 2. LA SECONDE PASSE : Météo-France a fini de publier.
    couvre, vus = couverture_a({(g, p): 51 for g, p in D.PAQUETS_RALLONGE})
    ref, _run, steps = choisir_run(24, crier=lambda *a: None,
                                   max_heures_grille=51, couverture=couvre,
                                   maintenant=maintenant)
    verifier("⛔ la seconde passe monte à +51 h ALORS QUE la maille fine "
             "reste à +24 h — c'est tout l'objet du fix",
             steps == list(range(52)), f"{len(steps)} échéances")
    verifier("⛔ …et la maille fine n'a JAMAIS été interrogée au-delà de "
             "+24 h : c'était ça, le paquet de trop",
             all(h <= 24 for _r, g, _p, h in vus if g == D.GRID_FINE),
             f"max +{max([h for _r, g, _p, h in vus if g == D.GRID_FINE])} h "
             f"sur la maille fine, +{max(h for *_x, h in vus)} h en 0,025°")

    # 3. UN TROU DANS LA RALLONGE : on s'arrête au bord, pas au trou.
    #    SP2 traîne (c'est le paquet le plus lent, mesuré le 13/08) :
    #    30 h chez lui, 51 h chez les autres.
    horizons = {(D.GRID_3D, p): 51 for _g, p in D.PAQUETS_RALLONGE}
    horizons[(D.GRID_3D, D.PAQUET_SURFACE_2)] = 30
    couvre, _vus = couverture_a(horizons)
    _ref, _run, steps = choisir_run(24, crier=lambda *a: None,
                                    max_heures_grille=51, couverture=couvre,
                                    maintenant=maintenant)
    verifier("⚠️ un paquet en retard borne la coupe à SON horizon — pas "
             "de trou au milieu",
             steps == list(range(31)), f"{len(steps)} échéances")

    # 4. ARCHIVE INCOMPLÈTE, RALLONGE DISPONIBLE — le cas que la
    #    séparation des deux listes rend POSSIBLE, et qu'il faut donc
    #    bancer : les six paquets 0,025° montent à 51 h pendant que la
    #    maille fine, elle, traîne à 19 h. La rallonge est là, l'archive
    #    ne l'est pas, et une coupe 0–19 h + 25–51 h serait illisible.
    horizons = {(g, p): 51 for g, p in D.PAQUETS_INGESTION}
    horizons[(D.GRID_FINE, "HP1")] = 19
    couvre, _vus = couverture_a(horizons, partout=True)
    messages = []
    _ref, _run, steps = choisir_run(24, crier=messages.append,
                                    max_heures_grille=51, couverture=couvre,
                                    maintenant=maintenant)
    verifier("⚠️ archive incomplète → rallonge ABANDONNÉE (une coupe "
             "courte vaut mieux qu'une coupe trouée)",
             steps == list(range(20)), f"jusqu'à +{max(steps)} h")
    verifier("…et l'abandon est CRIÉ, pas silencieux",
             any("ABANDONNÉE" in m for m in messages))

    # ── Le guet, côté poller ─────────────────────────────────────────
    print("\n── ⛔ Le second guet `arome-rallonge` ─────────────────────")
    cibles = P.fabriquer_source("arome-rallonge")
    verifier("⛔ il guette EXACTEMENT les paquets que la rallonge exige "
             "— deux listes qui divergent = un dispatch qui n'arrive pas",
             tuple((s.grille, s.paquet) for s in cibles)
             == tuple(D.PAQUETS_RALLONGE),
             ", ".join(f"{s.grille}/{s.paquet}" for s in cibles))
    verifier("il guette l'échéance la PLUS LOINTAINE (celle qui arrive "
             "en dernier), pas l'échéance 0",
             all(s.echeance == D.MAX_HOURS_GRILLE for s in cibles),
             str({s.echeance for s in cibles}))
    verifier("⛔ ses séries portent un nom DISTINCT du premier guet — "
             "sinon `deja_vu()` les confond et le second guet ne part "
             "jamais",
             not ({s.nom for s in cibles}
                  & {s.nom for s in P.fabriquer_source("arome-paquets")}),
             ", ".join(sorted(s.nom for s in cibles)[:2]) + " …")
    verifier("…et le premier guet garde le nom qu'il a depuis le 10/08 "
             "(la série mesurée ne se casse pas)",
             P.fabriquer_source("arome-paquets")[0].nom == "arome:0025/HP1")


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
        verifier("deja_vu = DÉCIDÉ : publié ou abandonné, pas seulement publié",
                 P.deja_vu(e, "aromepi", "R1") and P.deja_vu(e, "aromepi", "R2"),
                 "un abandon non compté ferait re-guetter le run à chaque "
                 "cycle — c'est arrivé le 10/08")
        verifier("un run jamais rencontré n'est pas « déjà vu »",
                 not P.deja_vu(e, "aromepi", "R-inconnu"))
        verifier("les sources ne se contaminent pas",
                 not P.deja_vu(e, "arome:0025/HP1", "R1"))
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

    print("\n── ⛔ …et la FIN de la fenêtre fine aussi (26/08/2026) ─────")
    # ⛔ CE QUI MANQUAIT : le début du guet était appris depuis le 10/08,
    # la fin non — elle restait à `FENETRE_FINE_MIN`, écrite avant la
    # moindre mesure. Six réseaux AROME sur huit publient au-delà, donc
    # au moment précis de leur publication ils étaient guettés à 15 min
    # de période au lieu de 2.
    verifier("sans observations, on garde le défaut de 120 min",
             P.fin_de_guet_fin_min([], "arome:0025/HP1") == 120,
             f"{P.fin_de_guet_fin_min([], 'arome:0025/HP1')}")
    verifier("3 observations, c'est encore trop peu — défaut",
             P.fin_de_guet_fin_min(peu, "aromepi") == 120)
    # d9 de dix valeurs 200…290 : l'indice int(0,9 × 9) = 8 → 280.
    tardif = [dict(source="arome:0025/HP1", etat="publie",
                   latence_max_min=v)
              for v in (200, 210, 220, 230, 240, 250, 260, 270, 280, 290)]
    verifier("⛔ un réseau qui publie APRÈS H+2 h étire la fenêtre fine "
             "jusqu'au d9 + marge — sinon on lève le pied à la minute "
             "où il paraît",
             P.fin_de_guet_fin_min(tardif, "arome:0025/HP1") == 295,
             f"d9 = 280 → fin H+"
             f"{P.fin_de_guet_fin_min(tardif, 'arome:0025/HP1')}")
    # ⛔ 295 EN DUR, pas `280 + P.MARGE_APPRISE_MIN` : lire la marge
    # depuis le module ferait bouger les deux côtés de l'égalité et une
    # mutation de la marge resterait invisible. Le piège nº 1 de la
    # phase B, qui s'est reproduit deux fois le 26/08.
    verifier("⚠️ un réseau RAPIDE ne raccourcit PAS la fenêtre sous le "
             "défaut — le back-off ne doit pas démarrer avant l'heure "
             "sous prétexte qu'on a eu de la chance",
             P.fin_de_guet_fin_min(tot, "aromepi") == 120,
             f"latences 5–10 min → fin H+"
             f"{P.fin_de_guet_fin_min(tot, 'aromepi')}")
    # ⚠️ UN SEUL run pathologique ne doit pas tirer la fenêtre : PI a un
    # max à 207 min pour une médiane de 19. Le d9 suit la population.
    pi_reel = [dict(source="aromepi", etat="publie", latence_max_min=v)
               for v in (16, 17, 18, 19, 19, 20, 21, 22, 23, 207)]
    verifier("⛔ le d9 protège d'un run pathologique isolé — un max à "
             "207 min ne doit pas faire guetter finement pendant 3 h",
             P.fin_de_guet_fin_min(pi_reel, "aromepi") == 120,
             f"max 207 mais d9 = 207 ? → fin H+"
             f"{P.fin_de_guet_fin_min(pi_reel, 'aromepi')}")
    verifier("ⓘ la fenêtre apprise commence toujours APRÈS son début — "
             "une fenêtre inversée ne guetterait jamais finement",
             all(P.fin_de_guet_fin_min(j, s) > P.debut_de_guet_min(j, s)
                 for j, s in ((tardif, "arome:0025/HP1"), (tot, "aromepi"),
                              (assez, "aromepi"), ([], "aromepi"))))
    lignes = []
    with tempfile.TemporaryDirectory() as d:
        j = Path(d) / "l.ndjson"
        for e in tardif:
            P.ecrire_journal(dict(e, run=f"R{e['latence_max_min']}"), j)
        P.rapport(j, crier=lignes.append)
    verifier("et le rapport PUBLIE la fenêtre apprise — une fenêtre qui "
             "ne se voit pas ne se conteste pas",
             any("fenêtre de guet FINE apprise" in x and "H+295" in x
                 for x in lignes),
             next((x.strip() for x in lignes if "FINE apprise" in x), "—"))

    # ⛔⛔ ET LE GUET MULTIPLE PREND LE MAX, PAS LE MIN. Sans ce banc, la
    # mutation « min au lieu de max » restait invisible — trouvée par
    # `mutations_poller.py`, pas par une relecture. `choisir_run()` exige
    # la couverture COMMUNE : c'est le paquet le PLUS LENT qui décide de
    # la fraîcheur de toute la chaîne. Lever le pied sur lui, c'est
    # perdre exactement ce qu'on cherche à gagner.
    with tempfile.TemporaryDirectory() as d:
        j = Path(d) / "l.ndjson"
        run2 = datetime(2026, 8, 10, 0, 0, tzinfo=timezone.utc)
        # « rapide » a appris une fenêtre courte (défaut 120), « lent »
        # une fenêtre longue (d9 280 + 15 = 295).
        hist = ([dict(source="rapide", etat="publie", latence_max_min=v)
                 for v in (10, 11, 12, 13, 14, 15)]
                + [dict(source="lent", etat="publie", latence_max_min=v)
                   for v in (200, 210, 220, 230, 240, 250, 260, 270, 280, 290)])
        h = Horloge(run2)
        cibles = [SourceFactice(h, run2 + timedelta(minutes=250),
                                nom="rapide"),
                  SourceFactice(h, run2 + timedelta(minutes=250),
                                nom="lent")]
        P.guetter_plusieurs(cibles, run2, hist, j, crier=lambda *a: None,
                            dormir=h.dormir, maintenant=h.maintenant)
        # À période fine (120 s) sur 250 min, il faut ~125 interrogations.
        # Avec le back-off démarré à H+120, il en faut nettement moins.
        n = cibles[1].interrogations
        verifier("⛔ le guet multiple reste FIN tant que la cible la plus "
                 "LENTE est dans sa fenêtre — prendre le min lèverait le "
                 "pied sur le paquet qui commande la chaîne",
                 n > 100, f"{n} interrogations jusqu'à H+250 "
                          f"(au back-off dès H+120 il y en aurait ~40)")

    print("\n── ⛔ Le rapport ne mélange plus deux populations ──────────")
    # ⛔ Le filtre était `":" in source` : il ramassait la rallonge `@51`
    # avec les paquets 0–24 h et annonçait 60 min d'écart là où il y en a
    # 14. *Un test sur le NOM d'une source ne définit pas une population.*
    lignes = []
    with tempfile.TemporaryDirectory() as d:
        j = Path(d) / "l.ndjson"
        for src, lat in (("arome:0025/HP1", 100), ("arome:0025/SP1", 110),
                         ("arome:0025/HP1@51", 400),
                         ("arome:0025/SP1@51", 402)):
            P.ecrire_journal(dict(source=src, run="R1", etat="publie",
                                  latence_max_min=lat), j)
        P.rapport(j, crier=lignes.append)
    plat = "\n".join(lignes)
    verifier("⛔ les paquets 0–24 h et la rallonge @51 sont rapportés "
             "SÉPARÉMENT",
             "produit A, échéances 0–24 h" in plat
             and "rallonge du produit B" in plat)
    verifier("⛔ et l'écart du produit A vaut 10 min (110 − 100), pas 302 "
             "— le mélange donnait le second",
             "médiane 10 min" in plat and "médiane 302 min" not in plat,
             next((x.strip() for x in lignes
                   if "écart premier/dernier" in x), "—"))

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
        # ⚠️ LE SECOND DÉFAUT DU 10/08 : un abandon n'était pas compté
        # comme « déjà vu », donc le tour de rattrapage reprenait le run à
        # chaque cycle et réécrivait un abandon toutes les deux minutes.
        # Le journal s'est rempli de doublons en quelques minutes.
        for _ in range(3):
            P.guetter_plusieurs(cibles, run, P.lire_journal(j), j,
                                crier=lambda *a: None, dormir=h.dormir,
                                maintenant=h.maintenant)
        verifier("⚠️ un ABANDON ne se réécrit pas au cycle suivant",
                 len(P.lire_journal(j)) == 2,
                 f"{len(P.lire_journal(j))} entrées après 3 tours de plus")

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
        # ⚠️ `**kw` DEPUIS LE 20/08, et ce n'est pas de la complaisance.
        # `portail.describe` a gagné un paramètre `agregation` (la
        # prévision immédiate suffixe ses identifiants de couverture), et
        # cette doublure l'a fait tomber : `TypeError: describe() got an
        # unexpected keyword argument`. Une doublure qui reproduit une
        # signature à l'exact transforme tout élargissement en panne de
        # banc — alors que ce qu'elle simule ici, c'est un portail MUET,
        # ce qui n'a rien à voir avec ses arguments.
        def describe(self, champ, run, **kw):
            self.vus.append(run)
            raise W.CouvertureAbsente("NoSuchCoverage",
                                      exception_wcs="NoSuchCoverage")
        def valider_champ(self, champ, runs, **kw):
            return W.Portail.valider_champ(self, champ, runs, **kw)

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
        def describe(self, champ, run, **kw):      # cf. `PortailMuet`
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

    print("\n── ⚠️ Guet SIMULTANÉ des paquets de l'ingestion ───────────")
    # `choisir_run()` exige la couverture COMMUNE à tous : l'ingestion
    # avance au rythme du plus lent. C'est leur ÉCART qu'on mesure, donc
    # ils doivent être interrogés dans le MÊME cycle — sinon une part de
    # l'écart viendrait de la désynchronisation des guets.
    # ⛔ LA PARITÉ AVEC L'INGESTION EST LE CONTRÔLE QUI COMPTE (audit du
    # 13/08) : ce fichier a guetté QUATRE paquets pendant que
    # `ingest_colonnes.py` en exigeait HUIT — trois étapes de retard,
    # dispatch prématuré, run plus ancien retenu, voyant vert. Le banc
    # compare donc les deux listes L'UNE À L'AUTRE, pas à une copie
    # locale qui prendrait le même retard.
    from ingest_colonnes import PAQUETS as PAQUETS_INGERES  # noqa: PLC0415
    verifier("⛔ le poller guette EXACTEMENT les paquets de l'ingestion "
             "— deux listes qui divergent = dispatch prématuré",
             tuple(P.PAQUETS_PRODUIT_A) == tuple(PAQUETS_INGERES),
             f"{len(P.PAQUETS_PRODUIT_A)} guettés / "
             f"{len(PAQUETS_INGERES)} exigés")
    verifier("…et il y en a plus que les quatre d'origine (étapes 5, "
             "12, 12 bis)",
             len(P.PAQUETS_PRODUIT_A) >= 8,
             str(len(P.PAQUETS_PRODUIT_A)))
    cibles = P.fabriquer_source("arome-paquets")
    verifier("`arome-paquets` fabrique une cible distincte par paquet",
             len({s.nom for s in cibles}) == len(P.PAQUETS_PRODUIT_A),
             ", ".join(s.nom for s in cibles))
    verifier("le nom porte le paquet, pas seulement le modèle",
             cibles[0].nom == "arome:0025/HP1", cibles[0].nom)
    verifier("toutes les cibles suivent la grille de runs à 3 h",
             all(s.pas_h == 3 for s in cibles))

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

    banc_rallonge()

    print("\n  poller :", "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
