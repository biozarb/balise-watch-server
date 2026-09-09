#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/sonde_rafale_pi.py — ce que le portail dit VRAIMENT de la
#                              rafale AROME-PI 15 min      (09/09/2026)
#                              Lot « cellule qui approche », lot 2
#
#  ⛔ CE FICHIER N'ÉCRIT RIEN. Il lit le portail et il imprime. Il existe
#  parce que le lot 2 repose sur cinq faits que la note du 09/09 tient
#  d'UN SEUL run (le 09:00Z), et qu'un fait mesuré une fois est une
#  anecdote : la latence surtout, annoncée à H+2 h 40 le 08/09 et à
#  ≤ 47 min le 09/09. On ne cale pas une cadence d'ingestion sur deux
#  mesures qui se contredisent d'un facteur 3.
#
#  ── LES CINQ CHOSES QU'IL VÉRIFIE ────────────────────────────────────
#  1. La DISPONIBILITÉ run par run : combien d'échéances chaque run
#     annonce, et depuis combien de minutes il aurait dû être là.
#  2. ⛔ Le SUFFIXE D'AGRÉGATION. Sans `_PT15M`, DescribeCoverage rend
#     `NoSuchCoverage` — le MÊME code que « ce run n'existe pas ». La
#     sonde demande les deux formes exprès, pour que la trace montre
#     l'indiscernabilité plutôt que de la laisser croire.
#  3. ⛔ L'AXE VERTICAL. `Portail.axe_vertical()` appelle `describe()`
#     SANS transmettre l'agrégation : appelé sur ce champ-ci il part
#     donc sur un identifiant sans suffixe et récolte un 404. La sonde
#     essaie `niveau=10, axe="height"` ET `niveau=None` pour trancher
#     lequel des deux le serveur accepte.
#  4. Les CLÉS eccodes du champ reçu : `units`, `stepType`, `stepRange`,
#     géométrie. C'est ce que `verifier_geometrie` refusera plus tard.
#  5. Le COÛT d'une échéance sur la boîte PIAF entière : octets et
#     secondes. 24 échéances par run en dépendent.
#
#  Usage (SUR LE VPS, où vit la clé) :
#      python3 agrume/sonde_rafale_pi.py            # 6 runs, 1 tirage
#      python3 agrume/sonde_rafale_pi.py --runs 12  # remonter plus loin
#      python3 agrume/sonde_rafale_pi.py --cout     # + le tirage boîte entière
# ══════════════════════════════════════════════════════════════════════
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

from piaf import BOITE  # noqa: E402
from portail import (SERVICE_AROMEPI, CouvertureAbsente,  # noqa: E402
                     ErreurPortail, Portail)

CHAMP = "WIND_SPEED_GUST_15MIN__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND"
AGREGATION = "PT15M"
PAS_MIN = 15
NB_ECHEANCES = 24
#: Une boîte minuscule pour les sondes de forme : on veut les CLÉS du
#: GRIB, pas ses octets. 0,3° × 0,3° au-dessus de l'Aude du 24/08.
BOITE_TEMOIN = dict(latmin=42.80, latmax=43.10, lonmin=2.20, lonmax=2.50)


def crier(msg=""):
    print(msg, flush=True)


def runs_candidats(maintenant, combien):
    """Les runs horaires plausibles, du plus frais au plus ancien."""
    h = maintenant.replace(minute=0, second=0, microsecond=0)
    return [(h - dt.timedelta(hours=k)).strftime("%Y-%m-%dT%H:00:00Z")
            for k in range(combien)]


def coefficients_temps(arbre):
    """Les coefficients de l'axe `time`, et de LUI SEUL.

    ⛔⛔ LA RECETTE DE PIAF NE MARCHE PAS ICI, ET ELLE ÉCHOUE EN SILENCE.
    `ingest_piaf.nb_echeances_publiees` prend le PREMIER `coefficients`
    non vide de la réponse. Chez PIAF le champ est de surface : les axes
    `long` et `lat` sont réguliers (coefficients VIDES) et le premier
    non-vide est donc le temps. Ici le champ porte un axe `height`, dont
    le coefficient vaut `10` — un seul nombre. La recette de PIAF rend
    donc **1 échéance** sur un run qui en publie 24, et le poller conclut
    « passe partielle » sur tous les runs, pour toujours.

    ⚠️ Mesuré le 09/09 à 16:07Z : huit runs d'affilée annoncés
    « partiel (1) » alors que le 15:00Z était complet depuis une heure.

    On lit donc `gridAxesSpanned` et on ne garde que `time`.
    """
    for ax in arbre.iter():
        if not ax.tag.endswith("GeneralGridAxis"):
            continue
        spanned = coeffs = None
        for el in ax.iter():
            if el.tag.endswith("gridAxesSpanned"):
                spanned = (el.text or "").strip()
            elif el.tag.endswith("coefficients"):
                coeffs = (el.text or "").strip()
        if spanned == "time" and coeffs:
            return [int(x) for x in coeffs.split()]
    return []


def nb_echeances_publiees(arbre):
    return len(coefficients_temps(arbre))


# ══════════════════════════════════════════════════════════════════════
#  1 & 2. DISPONIBILITÉ, LATENCE, ET L'INDISCERNABILITÉ DU 404
# ══════════════════════════════════════════════════════════════════════
def sonder_runs(portail, maintenant, combien):
    crier("── 1. Disponibilité run par run "
          f"({CHAMP}_{AGREGATION})")
    crier("   run                    éch.  âge du run   verdict")
    trouves = []
    for run in runs_candidats(maintenant, combien):
        t = dt.datetime.strptime(run, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.timezone.utc)
        age = (maintenant - t).total_seconds() / 60.0
        try:
            arbre = portail.describe(CHAMP, run, agregation=AGREGATION)
        except CouvertureAbsente:
            crier(f"   {run}   —     {age:6.1f} min   absent")
            continue
        n = nb_echeances_publiees(arbre)
        etat = "COMPLET" if n == NB_ECHEANCES else f"partiel ({n})"
        crier(f"   {run}  {n:3d}    {age:6.1f} min   {etat}")
        if n == NB_ECHEANCES:
            trouves.append((run, round(age, 1)))
    if trouves:
        crier(f"   ⇒ le plus frais COMPLET : {trouves[0][0]}, "
              f"latence de publication ≤ {trouves[0][1]} min")
    else:
        crier("   ⛔ aucun run complet sur la profondeur demandée")
    return trouves


def sonder_suffixe(portail, run):
    """⛔ La démonstration que le 404 ne dit pas ce qu'on croit."""
    crier("\n── 2. Le suffixe d'agrégation, et le 404 qui ment")
    for etiquette, agreg in (("AVEC _PT15M", AGREGATION),
                             ("SANS suffixe", None)):
        cid = portail.id_couverture(CHAMP, run, agreg)
        try:
            arbre = portail.describe(CHAMP, run, agregation=agreg)
            crier(f"   {etiquette:14s} {nb_echeances_publiees(arbre):3d} "
                  f"échéances   ✅")
        except CouvertureAbsente as err:
            crier(f"   {etiquette:14s}  —              "
                  f"CouvertureAbsente — {err}")
        except ErreurPortail as err:
            crier(f"   {etiquette:14s}  —              ErreurPortail — {err}")
        crier(f"     id : {cid}")
    crier("   ⚠️ Les deux lignes ci-dessus sont la MÊME exception que "
          "« run absent ».\n"
          "      C'est pourquoi `valider_champ` doit recevoir "
          "`agregation=\"PT15M\"` :\n"
          "      sinon il conclut « le champ n'existe nulle part » sur un "
          "champ parfait.")


# ══════════════════════════════════════════════════════════════════════
#  3 & 4. L'AXE VERTICAL, PUIS LES CLÉS DU CHAMP REÇU
# ══════════════════════════════════════════════════════════════════════
def lire_cles(octets, quoi):
    """Les clés eccodes qui décident du format — et rien d'autre."""
    import eccodes as ec  # noqa: PLC0415
    h = ec.codes_new_from_message(octets)
    try:
        cles = {}
        for c in ("shortName", "units", "stepType", "stepRange",
                  "typeOfStatisticalProcessing", "Ni", "Nj",
                  "latitudeOfFirstGridPointInDegrees",
                  "longitudeOfFirstGridPointInDegrees",
                  "iDirectionIncrementInDegrees",
                  "jDirectionIncrementInDegrees", "jScansPositively",
                  "typeOfLevel", "level", "missingValue"):
            try:
                cles[c] = ec.codes_get(h, c)
            except Exception as err:                       # noqa: BLE001
                cles[c] = f"<{type(err).__name__}>"
        vals = ec.codes_get_values(h)
    finally:
        ec.codes_release(h)
    crier(f"   {quoi} — {len(octets)} octets")
    for c, v in cles.items():
        crier(f"     {c:38s} {v}")
    finis = vals[vals == vals]
    crier(f"     valeurs : {vals.size} points, "
          f"{finis.size} finies, min {finis.min():.2f}, "
          f"max {finis.max():.2f}")
    return cles


def sonder_forme(portail, run):
    crier("\n── 3 & 4. L'axe vertical, puis les clés du champ reçu")
    instant = (dt.datetime.strptime(run, "%Y-%m-%dT%H:%M:%SZ")
               + dt.timedelta(minutes=PAS_MIN)).strftime("%Y-%m-%dT%H:%M:%SZ")
    crier(f"   run {run}, échéance +{PAS_MIN} min → instant {instant}")
    crier("   ⚠️ instant nommé = FIN de tranche : c'est ce que `stepRange` "
          "doit confirmer.")
    gagnant = None
    for etiquette, niveau, axe in (
            ("niveau=10, axe=\"height\"", 10, "height"),
            ("niveau=None (surface)", None, None)):
        try:
            t0 = time.perf_counter()
            octets = portail.get_coverage(
                CHAMP, run, instant, niveau, BOITE_TEMOIN, axe=axe,
                agregation=AGREGATION)
            ms = (time.perf_counter() - t0) * 1000
            crier(f"\n   ✅ {etiquette} — {ms:.0f} ms")
            lire_cles(octets, etiquette)
            if gagnant is None:
                gagnant = (niveau, axe)
        except (ErreurPortail, CouvertureAbsente) as err:
            crier(f"\n   ⛔ {etiquette} — {type(err).__name__} : {err}")
    if gagnant is None:
        crier("   ⛔ AUCUNE des deux formes ne passe : le lot 2 ne peut "
              "pas tirer ce champ tel quel.")
    else:
        crier(f"\n   ⇒ forme retenue : niveau={gagnant[0]!r}, "
              f"axe={gagnant[1]!r}")
    return gagnant


# ══════════════════════════════════════════════════════════════════════
#  5. LE COÛT D'UNE ÉCHÉANCE SUR LA BOÎTE PIAF ENTIÈRE
# ══════════════════════════════════════════════════════════════════════
def sonder_cout(portail, run, forme):
    crier("\n── 5. Coût d'UNE échéance sur la boîte PIAF entière")
    crier(f"   boîte {BOITE['latmin']} → {BOITE['latmax']} N × "
          f"{BOITE['lonmin']} → {BOITE['lonmax']} E")
    niveau, axe = forme
    instant = (dt.datetime.strptime(run, "%Y-%m-%dT%H:%M:%SZ")
               + dt.timedelta(minutes=PAS_MIN)).strftime("%Y-%m-%dT%H:%M:%SZ")
    t0 = time.perf_counter()
    octets = portail.get_coverage(CHAMP, run, instant, niveau, BOITE,
                                  axe=axe, agregation=AGREGATION)
    s = time.perf_counter() - t0
    cles = lire_cles(octets, "boîte PIAF entière")
    crier(f"     {len(octets) / 1e6:.2f} Mo en {s:.1f} s")
    crier(f"   ⇒ un run de {NB_ECHEANCES} échéances : "
          f"~{NB_ECHEANCES * len(octets) / 1e6:.0f} Mo transférés, "
          f"~{NB_ECHEANCES * s:.0f} s")
    crier(f"   ⇒ le CALQUE publié, lui, est réduit 0,01° → 0,02° par "
          f"MAXIMUM :\n"
          f"      {cles['Nj']} × {cles['Ni']} → "
          f"{cles['Nj'] // 2} × {cles['Ni'] // 2} en float16 = "
          f"{cles['Nj'] // 2 * (cles['Ni'] // 2) * 2 / 1e6:.2f} Mo par "
          f"échéance,\n"
          f"      soit {NB_ECHEANCES * (cles['Nj'] // 2) * (cles['Ni'] // 2) * 2 / 1e6:.1f} Mo par run en ligne.")


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--runs", type=int, default=6,
                   help="profondeur de la sonde de disponibilité (heures)")
    a.add_argument("--grille", default="0025", choices=("001", "0025"),
                   help="la grille AROME-PI interrogée")
    a.add_argument("--cout", action="store_true",
                   help="tirer aussi UNE échéance sur la boîte PIAF entière")
    a = a.parse_args(argv)

    maintenant = dt.datetime.now(dt.timezone.utc)
    crier("══════════════════════════════════════════════════════════════")
    crier(f"  SONDE RAFALE AROME-PI — {maintenant:%Y-%m-%dT%H:%M:%SZ}, "
          f"grille {a.grille}")
    crier("══════════════════════════════════════════════════════════════\n")
    portail = Portail(SERVICE_AROMEPI, a.grille,
                      journal=lambda m: crier(f"   {m}"))

    trouves = sonder_runs(portail, maintenant, a.runs)
    if not trouves:
        crier("\n⛔ rien de complet à sonder plus loin.")
        return 1
    run = trouves[0][0]
    sonder_suffixe(portail, run)
    forme = sonder_forme(portail, run)
    if forme is None:
        return 1
    if a.cout:
        sonder_cout(portail, run, forme)
    crier(f"\n── portail : {portail.bilan()}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ErreurPortail as err:
        crier(f"⛔ {type(err).__name__} : {err}")
        sys.exit(1)
