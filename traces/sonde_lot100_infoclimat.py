#!/usr/bin/env python3
"""
sonde_lot100_infoclimat.py — le coût RÉEL d'un cycle, au vrai lot de
100 stations, avec les en-têtes que Node envoie vraiment (03/08/2026).

┌─ POURQUOI CE TROISIÈME PASSAGE ─────────────────────────────────────┐
│ `sonde_poids_infoclimat.py` a montré 25× d'écart entre une réponse  │
│ nue et la même en gzip, et j'allais en conclure qu'il y avait là un │
│ levier gratuit. VÉRIFICATION FAITE : le `fetch` de Node envoie déjà │
│ `Accept-Encoding: br, gzip, deflate` par défaut. Render reçoit donc │
│ DÉJÀ du compressé — le levier était déjà tiré, à mon insu.          │
│                                                                     │
│ Ce script mesure ce qui compte vraiment :                           │
│   1. le poids sur le fil d'un lot de 100 (INFOCLIMAT_BATCH_SIZE),   │
│      avec les en-têtes exacts de Node → le coût réel d'un cycle ;   │
│   2. brotli vs gzip, puisque Node préfère br ;                      │
│   3. le nombre de LIGNES générées côté Infoclimat — la compression  │
│      soulage leur bande passante, PAS leur base de données. C'est   │
│      ce chiffre-là qui dit ce que coûte vraiment un poll à une      │
│      association bénévole.                                          │
└─────────────────────────────────────────────────────────────────────┘

⚠️ AF_INET forcé. ⚠️ TROIS appels, une fois. Pas de boucle.
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

UA = "BaliseWatch-sonde/1.3 (+argonautes.sim@gmail.com)"
STATIONS_GEOJSON = ("https://www.data.gouv.fr/api/1/datasets/r/"
                    "8a9e6a12-03f8-4056-861f-70b84136313e")
OPENDATA = "https://www.infoclimat.fr/opendata/"
LAT, LON = 45.3030, 5.8870


def forcer_ipv4():
    _orig = socket.getaddrinfo

    def v4(host, port, family=0, type=0, proto=0, flags=0):
        return _orig(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = v4


def get(url, accept_encoding=None, timeout=180):
    h = {"User-Agent": UA}
    if accept_encoding:
        h["Accept-Encoding"] = accept_encoding
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        brut = r.read()
        enc = (r.headers.get("Content-Encoding") or "(aucun)").lower()
        fil = len(brut)
        if "gzip" in enc:
            brut = gzip.GzipFile(fileobj=io.BytesIO(brut)).read()
        elif "br" in enc:
            try:
                import brotli
                brut = brotli.decompress(brut)
            except ImportError:
                return r.status, None, fil, enc + " (non décodé)"
        return r.status, brut.decode("utf-8", "replace"), fil, enc


def haversine_km(a_lat, a_lon, b_lat, b_lon):
    r = 6371.0
    dlat, dlon = math.radians(b_lat - a_lat), math.radians(b_lon - a_lon)
    h = (math.sin(dlat / 2) ** 2 + math.cos(math.radians(a_lat))
         * math.cos(math.radians(b_lat)) * math.sin(dlon / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def main():
    forcer_ipv4()
    cle = os.environ.get("INFOCLIMAT_API_KEY")
    if not cle:
        print("❌ INFOCLIMAT_API_KEY absente.")
        return 2

    _, txt, _, _ = get(STATIONS_GEOJSON, "gzip")
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
    ids = [s[1] for s in prox[:100]]
    jour = datetime.now(timezone.utc).date().isoformat()

    params = [("method", "get"), ("format", "json"),
              ("start", jour), ("end", jour), ("token", cle)]
    params += [("stations[]", i) for i in ids]
    url = f"{OPENDATA}?{urllib.parse.urlencode(params)}"

    print("═══ lot de 100 stations — le vrai cycle · 3 appels ═══\n")
    print(f"journée {jour} · URL de {len(url):,} caractères\n")
    print(f"{'Accept-Encoding envoyé':<34} {'sur le fil':>12} "
          f"{'décompressé':>13}  reçu en")
    print("─" * 82)

    ref_decomp, ref_lignes = None, None
    for ae, libelle in ((None, "(aucun — urllib par défaut)"),
                        ("gzip", "gzip"),
                        ("br, gzip, deflate", "br, gzip, deflate (Node)")):
        try:
            code, corps, fil, enc = get(url, ae)
        except Exception as e:                   # noqa: BLE001
            print(f"{libelle:<34} ❌ {type(e).__name__}: {e}")
            continue
        if corps is None:
            print(f"{libelle:<34} {fil:>12,} {'—':>13}  {enc}")
            continue
        if corps.strip() == "Wrong ip address":
            print(f"{libelle:<34} ❌ Wrong ip address")
            continue
        décomp = len(corps.encode())
        if ref_decomp is None:
            ref_decomp = décomp
            h = json.loads(corps).get("hourly") or {}
            ref_lignes = sum(len(v) for v in h.values()
                             if isinstance(v, list))
            ref_st = len(h)
        print(f"{libelle:<34} {fil:>12,} {décomp:>13,}  {enc}")

    if ref_decomp:
        print(f"\n   {ref_st} stations dans `hourly` · "
              f"{ref_lignes:,} relevés générés · "
              f"{ref_lignes / max(ref_st, 1):.0f} par station")
        print(f"   dont UTILISÉS par le module : {ref_st} "
              f"(le dernier de chaque station) — "
              f"{100 * ref_st / max(ref_lignes, 1):.1f} %")

        print("\n── Extrapolation au parc (~1200 stations) ───────────────")
        cycles = 96                       # 15 min
        lot = 100
        lots_par_cycle = math.ceil(1200 / lot)
        print(f"   {lots_par_cycle} lots/cycle · {cycles} cycles/jour = "
              f"{lots_par_cycle * cycles:,} requêtes/jour")
        lignes_j = ref_lignes * (1200 / ref_st) * cycles if ref_st else 0
        print(f"   LIGNES lues dans leur base : "
              f"{lignes_j / 1e6:,.1f} millions/jour")
        print(f"   dont réellement utilisées  : "
              f"{1200 * cycles / 1e6:,.3f} million/jour "
              f"({100 * 1200 * cycles / max(lignes_j, 1):.1f} %)")
        print("\n   ⚠️ La compression soulage LEUR BANDE PASSANTE, pas leur")
        print("      base. Le chiffre ci-dessus ne baisse qu'en pollant")
        print("      MOINS SOUVENT — c'est le §2, et c'est le seul levier")
        print("      qui reste une fois la fenêtre horaire écartée.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
