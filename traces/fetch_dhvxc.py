#!/usr/bin/env python3
"""
fetch_dhvxc.py — Étape 3 v1 (échantillon DHV-XC, SANS collecte de masse)

⚠️ MÊME RÉSERVE QUE fetch_syride.py : le mail envoyé à DHV-XC
(MAIL_TRACES_SOURCES.md §3) demande la permission "before reading
anything in volume". ⇒ ce script est prêt et testé, mais tant que DHV
n'a pas répondu, on ne fait tourner que des ÉCHANTILLONS LÉGERS
(quelques centaines de vols, même ordre de grandeur que le sondage
étape 1 qui avait échantillonné 200 vols), jamais un backfill complet
saison par saison. `--max-pages` est donc systématiquement requis sauf
si tu sais ce que tu fais.

Endpoint (public, sans login — confirmé SONDAGE_TRACES_RESULTATS.md §3
et re-vérifié en session 24/07/2026) :

    GET https://dhv-xc.de/api/fli/flights
        ?s=<saison>&navpars={"start":N,"limit":L,
                              "sort":[{"field":"FlightDate","dir":-1}]}

⚠️ Le paramètre `navpars.filter` (Kendo-style) est IGNORÉ par le
serveur — re-testé en session avec un filtre `TakeoffCountry=FR`,
réponse strictement identique à la requête non filtrée. Aucun endpoint
`/api/fli/waypoints` trouvé pour résoudre un nom de site en ID. ⇒ pas de
filtrage serveur possible : on pagine et on filtre CÔTÉ CLIENT sur
`TakeoffWaypointName` (alias approximatifs ci-dessous) — imprécis par
construction (un même site peut avoir plusieurs graphies), documenté
comme tel, à affiner si DHV répond avec un vrai identifiant de site.

Champs déjà exploitables SANS IGC (le point clé du sondage) :
FKGliderClassification/GliderClassification (catégorie EN NATIVE),
UtcOffset (fuseau), TakeoffAltitude/MaxAltitude/MinAltitude,
ElevationGain, FlightDuration (secondes), FlightStartTime,
LinearDistance (m). L'IGC (`IgcFilename`) reste nécessaire seulement
pour la polyligne (v2).

Sortie : traces_cache/dhvxc_<site_slug>.jsonl, gitignoré.
"""

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

UA = "BaliseWatch-traces/0.1 (+argonautes.sim@gmail.com; usage non-commercial, echantillon leger)"
PAUSE_S = 1.2
PAGE_SIZE = 200  # taille de page raisonnable, pas testé au-delà en session

BASE_URL = "https://dhv-xc.de/api/fli/flights"

# Alias de recherche par site (TakeoffWaypointName observé chez DHV,
# imprécis — cf. en-tête). "Aussois" volontairement absent : couverture
# DHV quasi nulle en Maurienne (constaté sondage §3), pas la peine de
# paginer pour rien.
SITE_ALIASES = {
    "saint_hilaire": ["hilaire"],
    "montmin_forclaz": ["montmin", "forclaz", "bornand"],  # Grand Bornand est le site DHV le plus proche vu en session
}

CACHE_DIR = Path(__file__).parent / "traces_cache"
CACHE_DIR.mkdir(exist_ok=True)


def fetch_page(season: int, start: int, limit: int = PAGE_SIZE) -> dict:
    navpars = json.dumps({
        "start": start, "limit": limit,
        "sort": [{"field": "FlightDate", "dir": -1}],
    })
    url = BASE_URL + "?" + urllib.parse.urlencode({"s": season, "navpars": navpars})
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _matches_site(flight: dict, aliases: list) -> bool:
    name = (flight.get("TakeoffWaypointName") or "").lower()
    loc = (flight.get("TakeoffLocation") or "").lower()
    return any(a in name or a in loc for a in aliases)


def _normalize(flight: dict, site_slug: str) -> dict:
    """Champs du schéma vol (v1, sans polyline/bbox — cf.
    ETAPE2_SCHEMAS_FEATURES.md §2). Catégorie EN native, contrairement
    à Syride — un vrai plus de cette source malgré son faible volume FR."""
    return {
        "site_id": site_slug,
        "source": "dhvxc",
        "flight_id_source": flight.get("IDFlight"),
        "date": flight.get("FlightDate"),
        "heure_deco_locale": (flight.get("FlightStartTime") or " ").split(" ")[-1][:5],
        "utc_offset_h": flight.get("UtcOffset"),
        "duree_min": round((flight.get("FlightDuration") or 0) / 60),
        "dist_km": round((flight.get("LinearDistance") or 0) / 1000, 1),
        "alt_max_m": flight.get("MaxAltitude"),
        "gain_max_m": flight.get("ElevationGain"),
        "categorie_aile": flight.get("GliderClassification"),  # natif, ex. "EN B"
    }


def sample_site(site_slug: str, season: int, max_pages: int):
    """Échantillon LÉGER : pagine `max_pages` pages de la saison,
    garde les vols dont le site de déco matche un alias. Pas un
    backfill (cf. réserve en-tête) — pensé pour quelques centaines à
    quelques milliers de vols scannés, pas la saison entière."""
    aliases = SITE_ALIASES[site_slug]
    out_path = CACHE_DIR / f"dhvxc_{site_slug}.jsonl"
    kept = 0
    scanned = 0
    with open(out_path, "w") as f:
        for page in range(max_pages):
            start = page * PAGE_SIZE
            try:
                data = fetch_page(season, start)
            except urllib.error.URLError as e:
                print(f"[{site_slug}] page {page} : erreur réseau ({e}), arrêt")
                break
            flights = data.get("data", [])
            if not flights:
                print(f"[{site_slug}] plus de vols (page {page}), arrêt")
                break
            scanned += len(flights)
            for fl in flights:
                if _matches_site(fl, aliases):
                    f.write(json.dumps(_normalize(fl, site_slug), ensure_ascii=False) + "\n")
                    kept += 1
            if page < max_pages - 1:
                time.sleep(PAUSE_S)
        print(f"[{site_slug}] {scanned} vols scannés (saison {season}), {kept} retenus -> {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", choices=list(SITE_ALIASES), required=True)
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--max-pages", type=int, required=True,
                     help="OBLIGATOIRE — garde-fou échantillon léger, cf. réserve en-tête")
    args = ap.parse_args()
    sample_site(args.site, args.season, args.max_pages)
