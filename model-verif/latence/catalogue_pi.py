#!/usr/bin/env python3
"""ÉNUMÉRER le catalogue, au lieu de deviner des noms de champs.

⛔ POURQUOI CE FICHIER EXISTE. Le 26/08, une sonde a conclu « le vent
moyen n'existe pas en 0,01° sur AROME-PI » en interrogeant QUATRE
identifiants écrits à la main, tous sur `SPECIFIC_HEIGHT_LEVEL_ABOVE_
GROUND`. Or le portail rend le MÊME `NoSuchCoverage` pour un champ
absent et pour un nom mal écrit (`Portail.existe` le dit lui-même). Une
absence ne se prouve pas en demandant les noms qu'on a imaginés : il
faut lire le catalogue.

`GetCapabilities` coûte quelques Mo — c'est cher pour du polling, pas
pour une question qu'on pose une fois.

    METEOFRANCE_API_KEY=... python3 catalogue_pi.py           # aromepi
    METEOFRANCE_API_KEY=... python3 catalogue_pi.py arome     # comparaison
"""
import re
import sys

sys.path[:0] = ["tools", "agrume", "."]
from portail import Portail, SERVICE_AROME, SERVICE_AROMEPI  # noqa: E402


def familles(service, grille):
    """Les noms de champs distincts, run et agrégation retirés."""
    p = Portail(service, grille, journal=None)
    # ⚠️ L'URL des capabilities OMET le `/1.0/` du chemin réel (piège
    # relevé le 10/08, cf. `prompt-demarrage-lot-h-10-08.md`).
    base = p.base.replace("/1.0/", "/")
    url = f"{base}/GetCapabilities?service=WCS&version=2.0.1&language=eng"
    xml = p._http(url, timeout=180)
    if isinstance(xml, bytes):
        xml = xml.decode("utf-8", "replace")
    ids = re.findall(r"<wcs:CoverageId>([^<]+)</wcs:CoverageId>", xml)
    if not ids:
        ids = re.findall(r"<CoverageId>([^<]+)</CoverageId>", xml)
    fam = {}
    for cid in ids:
        f = cid.split("___")[0]
        fam[f] = fam.get(f, 0) + 1
    return len(xml), len(ids), fam


def main():
    service = sys.argv[1] if len(sys.argv) > 1 else SERVICE_AROMEPI
    service = {"arome": SERVICE_AROME, "aromepi": SERVICE_AROMEPI}[service]
    for grille in ("001", "0025"):
        octets, n, fam = familles(service, grille)
        print(f"\n{'=' * 62}\n{service}/{grille} — {octets / 1e6:.2f} Mo, "
              f"{n} couvertures, {len(fam)} familles distinctes\n{'=' * 62}")
        vent = sorted(f for f in fam if "WIND" in f or "GUST" in f)
        print(f"  familles contenant WIND ou GUST : {len(vent)}")
        for f in vent:
            print(f"    {f}   (×{fam[f]})")
        autres = sorted(f for f in fam if f not in set(vent))
        print(f"  --- les {len(autres)} autres familles ---")
        for f in autres:
            print(f"    {f}")


if __name__ == "__main__":
    main()
