#!/usr/bin/env python3
"""
sonde_poids_infoclimat.py — puisque la FENÊTRE ne se resserre pas,
mesurer ce qui reste : le POIDS (03/08/2026).

┌─ CE QUE LA SONDE PRÉCÉDENTE A ÉTABLI ───────────────────────────────┐
│ `sonde_fenetre_infoclimat.py`, 7 appels depuis le VPS :             │
│   · start/end = DATES. Tout composant horaire (« J HH:MM:SS »,      │
│     « JTHH:MM:SS », sans secondes) renvoie `status OK` avec ZÉRO    │
│     relevé et une réponse de 3283 octets — un ÉCHEC SILENCIEUX de   │
│     plus, comme `Wrong ip address` en HTTP 200.                     │
│   · La page opendata le confirme : la période s'y choisit au JOUR   │
│     (« 7 jours consécutifs maximum »).                              │
│ Conclusion : la fenêtre d'une heure du §1 N'EXISTE PAS côté API.    │
│ Le minimum indivisible est la journée.                              │
└─────────────────────────────────────────────────────────────────────┘

┌─ CE QUE CE SCRIPT MESURE ───────────────────────────────────────────┐
│ Si on ne peut pas demander MOINS de lignes, on peut demander les    │
│ mêmes lignes MOINS CHER. Trois leviers, mesurés et non supposés :   │
│   1. gzip — `urllib` et le `fetch` de Node n'envoient PAS           │
│      `Accept-Encoding` par défaut. Du JSON très répétitif se        │
│      compresse énormément. C'est gratuit et invisible pour eux.     │
│   2. `format=csv` — la page opendata le propose. Le CSV ne répète   │
│      pas les noms de champs à chaque ligne.                         │
│   3. le coût FIXE d'un appel (métadonnées de stations) — il dit à   │
│      partir de quelle taille de lot on paie surtout de l'en-tête.   │
│                                                                     │
│ Et il capture le corps de la réponse VIDE, dont `refreshInfoclimat  │
│ Obs` devra se défendre.                                             │
└─────────────────────────────────────────────────────────────────────┘

⚠️ AF_INET forcé (le VPS sort en IPv6 par défaut, constaté le 03/08).
⚠️ Association bénévole : SIX appels au total, une fois. Pas de boucle.
"""

import gzip
import io
import json
import math
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

UA = "BaliseWatch-sonde/1.2 (+argonautes.sim@gmail.com)"
STATIONS_GEOJSON = ("https://www.data.gouv.fr/api/1/datasets/r/"
                    "8a9e6a12-03f8-4056-861f-70b84136313e")
OPENDATA = "https://www.infoclimat.fr/opendata/"
LAT, LON = 45.3030, 5.8870


def forcer_ipv4():
    _orig = socket.getaddrinfo

    def v4(host, port, family=0, type=0, proto=0, flags=0):
        return _orig(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = v4


def get(url, timeout=90, gz=False):
    """Renvoie (code, texte, octets_sur_le_fil, encodage_annonce)."""
    h = {"User-Agent": UA}
    if gz:
        h["Accept-Encoding"] = "gzip"
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            brut = r.read()
            enc = r.headers.get("Content-Encoding", "") or "(aucun)"
            fil = len(brut)
            if "gzip" in enc:
                brut = gzip.GzipFile(fileobj=io.BytesIO(brut)).read()
            return r.status, brut.decode("utf-8", "replace"), fil, enc
    except urllib.error.HTTPError as e:
        b = e.read()
        return e.code, b.decode("utf-8", "replace"), len(b), "(erreur)"
    except Exception as e:                       # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}", 0, "(erreur)"


def haversine_km(a_lat, a_lon, b_lat, b_lon):
    r = 6371.0
    dlat, dlon = math.radians(b_lat - a_lat), math.radians(b_lon - a_lon)
    h = (math.sin(dlat / 2) ** 2 + math.cos(math.radians(a_lat))
         * math.cos(math.radians(b_lat)) * math.sin(dlon / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def stations_proches(n):
    code, txt, _, _ = get(STATIONS_GEOJSON, timeout=90, gz=True)
    if code != 200:
        print(f"❌ GeoJSON HTTP {code}")
        return []
    prox = []
    for f in (json.loads(txt).get("features") or []):
        g = (f.get("geometry") or {}).get("coordinates") or []
        p = f.get("properties") or {}
        if len(g) < 2 or not p.get("id"):
            continue
        if (p.get("license") or {}).get("source") != "infoclimat.fr":
            continue
        prox.append((haversine_km(LAT, LON, float(g[1]), float(g[0])),
                     str(p["id"])))
    prox.sort()
    return [s[1] for s in prox[:n]]


def url_pour(cle, ids, jour, fmt="json"):
    params = [("method", "get"), ("format", fmt),
              ("start", jour), ("end", jour), ("token", cle)]
    params += [("stations[]", i) for i in ids]
    return f"{OPENDATA}?{urllib.parse.urlencode(params)}"


def nb_releves(txt):
    try:
        h = json.loads(txt).get("hourly") or {}
    except ValueError:
        return None
    return sum(len(v) for v in h.values() if isinstance(v, list))


def main():
    forcer_ipv4()
    cle = os.environ.get("INFOCLIMAT_API_KEY")
    if not cle:
        print("❌ INFOCLIMAT_API_KEY absente.")
        return 2

    jour = datetime.now(timezone.utc).date().isoformat()
    ids20 = stations_proches(20)
    if not ids20:
        return 2
    ids4 = ids20[:4]
    ids1 = ids20[:1]

    print("═══ sonde poids Infoclimat — lecture seule, 6 appels ═══\n")
    print(f"journée {jour} · lots de 1, 4 et 20 stations\n")
    print(f"{'essai':<40} {'sur le fil':>11} {'décompressé':>12} "
          f"{'relevés':>8}  encodage")
    print("─" * 92)

    mesures = {}
    essais = [
        ("1 station · json", ids1, "json", False),
        ("4 stations · json (référence)", ids4, "json", False),
        ("4 stations · json + gzip", ids4, "json", True),
        ("4 stations · csv", ids4, "csv", False),
        ("4 stations · csv + gzip", ids4, "csv", True),
        ("20 stations · json + gzip", ids20, "json", True),
    ]
    for libelle, ids, fmt, gz in essais:
        code, txt, fil, enc = get(url_pour(cle, ids, jour, fmt), gz=gz)
        if txt.strip() == "Wrong ip address":
            print(f"{libelle:<40} ❌ Wrong ip address (HTTP {code})")
            continue
        n = nb_releves(txt) if fmt == "json" else txt.count("\n")
        mesures[libelle] = (fil, len(txt.encode()), n)
        print(f"{libelle:<40} {fil:>11,} {len(txt.encode()):>12,} "
              f"{n if n is not None else '—':>8}  {enc}")

    ref = mesures.get("4 stations · json (référence)")
    if ref:
        print("\n── Ce que ça change ─────────────────────────────────────")
        par_station = ref[0] / 4
        print(f"   Référence : {par_station:,.0f} octets par station et par "
              f"appel, non compressé.")
        for lib in ("4 stations · json + gzip", "4 stations · csv",
                    "4 stations · csv + gzip"):
            if lib in mesures:
                print(f"   {lib:<32} → {ref[0] / mesures[lib][0]:5.1f}× "
                      f"moins d'octets sur le fil")
        print("\n   Extrapolation au parc réel (~1200 stations, 96 cycles/j "
              "à 15 min) :")
        for lib, (fil, _, _) in mesures.items():
            if not lib.startswith("4 stations"):
                continue
            octets_cycle = (fil / 4) * 1200
            print(f"     {lib:<32} {octets_cycle / 1e6:8.1f} Mo/cycle · "
                  f"{octets_cycle * 96 / 1e9:6.2f} Go/JOUR")

    print("\n── Corps d'une réponse vide (fenêtre horaire refusée) ────")
    code, txt, fil, _ = get(url_pour(cle, ids4, f"{jour} 12:00:00"))
    print(f"   HTTP {code} · {fil} octets")
    print("   " + txt[:600].replace("\n", "\n   "))
    return 0


if __name__ == "__main__":
    sys.exit(main())
