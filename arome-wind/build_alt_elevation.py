#!/usr/bin/env python3
"""Pré-calcul (UNE SEULE FOIS) de l'élévation du sol par nœud de la grille
ALT du calque vent — retour Yann 21/07/2026.

Pourquoi : les niveaux du vent d'altitude sont en altitude NIVEAU MER
(conversion ISA d'un niveau de pression, cf. web windGridLevelAltM). En
montagne, les niveaux bas passent SOUS le relief : la carte affiche des
flèches souterraines, sans le dire. Le client sait désormais masquer une
flèche dont le niveau (m AMSL) passe sous le sol À CE POINT
(WindGridLayer.floorAltM), mais il lui faut une élévation PAR POINT — que
le flux GRIB AROME (u/v seulement) ne fournit pas.

Ce script échantillonne l'API élévation Open-Meteo (DEM Copernicus ~90 m,
la même que le client utilise déjà pour situer une balise) sur le maillage
0,05° de la grille ALT, et écrit `alt_elevation.json` (clés "lat,lon"
snappées au 0,05°, valeurs en m AMSL). `ingest.py` le lit ensuite et
attache `elev` à chaque point ALT — donnée STATIQUE, ce calcul ne se
refait pas à chaque run.

Usage (à lancer une fois, là où il y a du réseau) :
    python3 build_alt_elevation.py            # BBOX + pas par défaut
    python3 build_alt_elevation.py --out alt_elevation.json

Puis committer `alt_elevation.json` à côté de ce script : le prochain run
d'ingest attachera l'élévation, et le masquage "façon météo-parapente"
s'activera côté carte.

⚠️ ~75 000 points sur France + voisins → ~750 requêtes. Throttle inclus
(≈ quelques minutes). Reprend là où il s'est arrêté si `--out` existe
déjà (utile si la connexion coupe)."""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request

# Mêmes constantes qu'ingest.py — à garder synchronisées (pas de code
# partagé : ce script est autonome et ne dépend pas d'eccodes).
BBOX = dict(latmin=41.0, latmax=52.0, lonmin=-6.0, lonmax=11.0)
STEP_ALT = 0.05
OM_ELEVATION = "https://api.open-meteo.com/v1/elevation"
BATCH = 100          # coordonnées par requête (limite Open-Meteo)
THROTTLE_S = 0.25    # pause entre requêtes, poli avec l'API


def snap_key(lat: float, lon: float) -> str:
    """Clé de nœud snappée au pas ALT — IDENTIQUE côté ingest.py, pour que
    la recherche d'élévation d'un point de grille tombe sur la bonne case."""
    la = round(round(lat / STEP_ALT) * STEP_ALT, 2)
    lo = round(round(lon / STEP_ALT) * STEP_ALT, 2)
    return f"{la:.2f},{lo:.2f}"


def frange(lo: float, hi: float, step: float):
    n = int(round((hi - lo) / step)) + 1
    return [round(lo + i * step, 2) for i in range(n)]


def fetch_batch(coords, tries=4):
    lats = ",".join(f"{la:.2f}" for la, _ in coords)
    lons = ",".join(f"{lo:.2f}" for _, lo in coords)
    url = f"{OM_ELEVATION}?latitude={urllib.parse.quote(lats)}&longitude={urllib.parse.quote(lons)}"
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "balise-watch-elev/1"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
            elev = data.get("elevation")
            if isinstance(elev, list) and len(elev) == len(coords):
                return elev
            raise ValueError(f"réponse inattendue: {str(data)[:200]}")
        except Exception as e:      # noqa: BLE001 — one-shot, on réessaie simplement
            wait = 2 * (k + 1)
            print(f"    ! échec ({e}); nouvel essai dans {wait}s", file=sys.stderr)
            time.sleep(wait)
    raise SystemExit("Trop d'échecs consécutifs — relancer plus tard (le fichier partiel est conservé).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "alt_elevation.json"))
    args = ap.parse_args()

    lats = frange(BBOX["latmin"], BBOX["latmax"], STEP_ALT)
    lons = frange(BBOX["lonmin"], BBOX["lonmax"], STEP_ALT)
    all_pts = [(la, lo) for la in lats for lo in lons]

    table = {}
    if os.path.exists(args.out):                 # reprise si interruption
        try:
            table = json.load(open(args.out)).get("elev", {})
            print(f"Reprise : {len(table)} nœuds déjà connus.")
        except Exception:
            table = {}

    todo = [(la, lo) for la, lo in all_pts if snap_key(la, lo) not in table]
    print(f"{len(all_pts)} nœuds ({len(lats)}×{len(lons)}), {len(todo)} à calculer.")

    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        elev = fetch_batch(batch)
        for (la, lo), e in zip(batch, elev):
            if isinstance(e, (int, float)):
                table[snap_key(la, lo)] = round(e)
        done = min(i + BATCH, len(todo))
        if done % (BATCH * 20) == 0 or done == len(todo):
            json.dump({"step": STEP_ALT, "bbox": BBOX, "elev": table},
                      open(args.out, "w"), separators=(",", ":"))
            print(f"  {done}/{len(todo)} — sauvegarde intermédiaire ({len(table)} nœuds)")
        time.sleep(THROTTLE_S)

    json.dump({"step": STEP_ALT, "bbox": BBOX, "elev": table},
              open(args.out, "w"), separators=(",", ":"))
    print(f"Terminé : {len(table)} nœuds écrits dans {args.out}")


if __name__ == "__main__":
    main()
