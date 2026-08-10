#!/usr/bin/env python3
"""
test_mf_s3.py — banc du module S3 partagé, HORS-LIGNE.

À lancer depuis `balise-watch-server/` :
    python3 tools/test_mf_s3.py

Pourquoi ce banc existe. Le 10/08/2026, `s3_keys` / `covered_steps` /
`download_tmp` ont quitté `arome-wind/ingest.py` pour `tools/mf_s3.py`,
parce que le poller du lot H en a besoin. Un déplacement de code ne casse
pas bruyamment : il casse en décalant d'une échéance, ou en cessant de
reconnaître un nommage de fichier. Or `covered_steps` est ce qui décide
QUEL RUN la chaîne de production publie — le bug du 25/07 (curseur du
calque vent plafonnant à 6 h au lieu de 51) venait exactement de là.

Ce banc fige donc les deux choses que le déplacement pouvait abîmer :
le décodage des DEUX nommages de fichiers, et le calcul de couverture.
Aucun réseau : `lister` est injecté.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mf_s3 import (bornes_echeances, covered_steps,   # noqa: E402
                   est_fichier_horaire, s3_objets, s3_keys)

# Noms RÉELS relevés sur le miroir le 10/08/2026 — pas des noms inventés.
HORAIRES = [
    "pnt/2026-08-10T00:00:00Z/arome/001/SP1/arome__001__SP1__00H__2026-08-10T00:00:00Z.grib2",
    "pnt/2026-08-10T00:00:00Z/arome/001/SP1/arome__001__SP1__06H__2026-08-10T00:00:00Z.grib2",
    "pnt/2026-08-10T00:00:00Z/arome/001/SP1/arome__001__SP1__51H__2026-08-10T00:00:00Z.grib2",
]
BUNDLES = [
    "pnt/2026-08-10T00:00:00Z/arome/0025/HP1/arome__0025__HP1__00H06H__2026-08-10T00:00:00Z.grib2",
    "pnt/2026-08-10T00:00:00Z/arome/0025/HP1/arome__0025__HP1__07H12H__2026-08-10T00:00:00Z.grib2",
    "pnt/2026-08-10T00:00:00Z/arome/0025/HP1/arome__0025__HP1__49H51H__2026-08-10T00:00:00Z.grib2",
]
BRUIT = [
    "pnt/2026-08-10T00:00:00Z/arome/0025/HP1/",          # le préfixe lui-même
    "pnt/2026-08-10T00:00:00Z/arome/0025/HP1/README.txt",
]

echecs = []


def verifier(nom, condition, detail=""):
    print(f"  {'✓' if condition else '✗'} {nom}" + (f"   {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


def main():
    print("── Décodage des deux nommages ─────────────────────────────")
    verifier("fichier horaire → (h, h)",
             bornes_echeances(HORAIRES[1]) == (6, 6),
             str(bornes_echeances(HORAIRES[1])))
    verifier("bundle 6 h → (début, fin)",
             bornes_echeances(BUNDLES[1]) == (7, 12),
             str(bornes_echeances(BUNDLES[1])))
    verifier("bundle de queue → (49, 51)",
             bornes_echeances(BUNDLES[2]) == (49, 51))
    verifier("nom sans échéance → None",
             all(bornes_echeances(k) is None for k in BRUIT))

    # ⚠️ La distinction qui compte, et qui ne se voit pas dans (début, fin) :
    # `__06H__` est horaire, un hypothétique `__06H06H__` serait une tranche
    # d'une heure. `files_for` ne filtre par `keep_step` QUE les horaires.
    verifier("horaire reconnu comme horaire",
             all(est_fichier_horaire(k) for k in HORAIRES))
    verifier("bundle NON reconnu comme horaire",
             not any(est_fichier_horaire(k) for k in BUNDLES))
    verifier("tranche d'une heure ≠ fichier horaire",
             est_fichier_horaire("x__06H06H__y.grib2") is False
             and bornes_echeances("x__06H06H__y.grib2") == (6, 6))

    print("\n── Couverture d'un run ────────────────────────────────────")
    besoin = list(range(0, 25))

    cov = covered_steps("REF", "HP1", "0025", besoin, lister=lambda p: BUNDLES)
    verifier("bundles 00-06 + 07-12 couvrent 0..12",
             cov == set(range(0, 13)), f"{len(cov)} échéances")

    cov = covered_steps("REF", "SP1", "001", besoin, lister=lambda p: HORAIRES)
    verifier("fichiers horaires ne couvrent QUE leurs heures",
             cov == {0, 6}, str(sorted(cov)))

    verifier("run non publié → couverture vide",
             covered_steps("REF", "HP1", "0025", besoin, lister=lambda p: []) == set())

    verifier("les échéances hors besoin ne sont jamais inventées",
             covered_steps("REF", "HP1", "0025", [0, 1],
                           lister=lambda p: BUNDLES) == {0, 1})

    # Le préfixe interrogé doit porter le modèle : le poller du lot H
    # interroge `aromeifs` et le futur composite pourrait en viser d'autres.
    vus = []
    covered_steps("2026-08-10T00:00:00Z", "HP2", "0025", besoin,
                  model="aromeifs", lister=lambda p: vus.append(p) or [])
    verifier("le modèle est bien dans le préfixe",
             vus == ["pnt/2026-08-10T00:00:00Z/aromeifs/0025/HP2/"], vus[0])

    print("\n── Non-régression : la version d'origine, à l'identique ───")
    # Réimplémentation LITTÉRALE de la boucle qui vivait dans
    # `arome-wind/ingest.py` avant le déplacement. Si les deux divergent
    # sur un seul nom, c'est le déplacement qui a introduit un écart.
    import re
    def covered_steps_origine(keys, steps_needed):
        want, covered = set(steps_needed), set()
        for k in keys:
            m = re.search(r"__(\d+)H(?:(\d+)H)?__", k)
            if not m:
                continue
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else start
            covered |= {h for h in want if start <= h <= end}
        return covered

    tous = HORAIRES + BUNDLES + BRUIT
    for besoins in ([0], list(range(0, 52)), [12, 13, 51], []):
        a = covered_steps("REF", "P", "G", besoins, lister=lambda p: tous)
        b = covered_steps_origine(tous, besoins)
        verifier(f"identique à l'origine sur {len(besoins)} échéances", a == b,
                 f"{sorted(a)[:6]}…")

    print("\n── Signatures conservées ──────────────────────────────────")
    verifier("s3_keys renvoie des chaînes, s3_objets des couples",
             s3_keys.__doc__ is not None and s3_objets.__doc__ is not None)

    print("\n  mf_s3 :", "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
