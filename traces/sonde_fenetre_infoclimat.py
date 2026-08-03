#!/usr/bin/env python3
"""
sonde_fenetre_infoclimat.py — mesurer ce que rend, et ce que coûte, une
fenêtre ÉTROITE sur l'API opendata Infoclimat (03/08/2026).

┌─ POURQUOI CE SCRIPT EXISTE ─────────────────────────────────────────┐
│ `refreshInfoclimatObs` (index.js ~2368) demande la JOURNÉE ENTIÈRE  │
│ à chaque cycle : `fetchInfoclimatBatch(ids, today, today)`. La      │
│ sonde du 03/08 a mesuré 53 à 93 relevés par station et par appel,   │
│ dont UN SEUL est utilisé (le dernier).                              │
│                                                                     │
│ Le §1 du chantier veut passer à une fenêtre d'une heure. Ça ne      │
│ tient QUE si `start`/`end` acceptent un composant horaire. La doc   │
│ ne le dit pas. Ce script le MESURE avant qu'une ligne de code en    │
│ dépende — si l'heure est ignorée, la réponse pèsera exactement le   │
│ même poids que la journée, et le §1 est à réécrire autrement.       │
│                                                                     │
│ Quatre questions, dans l'ordre :                                    │
│   1. L'heure est-elle PRISE EN COMPTE, ou silencieusement ignorée ? │
│   2. Quel format passe : « J HH:MM:SS », « JTHH:MM:SS », sans sec ? │
│   3. Que renvoie une fenêtre qui DÉBORDE sur la veille ?            │
│   4. Que renvoie une fenêtre VIDE — une erreur, ou une station      │
│      simplement absente de `hourly` ?                               │
└─────────────────────────────────────────────────────────────────────┘

⚠️ `Wrong ip address` arrive en HTTP 200, en TEXTE BRUT. On lit le
   corps avant de parser — cf. l'en-tête de `sonde_infoclimat.py`.
⚠️ AF_INET FORCÉ. Le VPS sort en IPv6 par défaut (constaté le 03/08 :
   ping Healthchecks reçu depuis 2001:41d0:404:200::60e8), et
   `precedence ::ffff:0:0/96` dans gai.conf ne couvre pas tout.
⚠️ USAGE NON COMMERCIAL. Association bénévole : ce script fait SEPT
   appels authentifiés au total, une seule fois. Ne pas en faire une
   boucle, ne pas le mettre dans un timer.

Usage :
  export INFOCLIMAT_API_KEY="..."
  python3 sonde_fenetre_infoclimat.py
"""

import json
import math
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

UA = "BaliseWatch-sonde/1.1 (+argonautes.sim@gmail.com)"
STATIONS_GEOJSON = ("https://www.data.gouv.fr/api/1/datasets/r/"
                    "8a9e6a12-03f8-4056-861f-70b84136313e")
OPENDATA = "https://www.infoclimat.fr/opendata/"

# Saint-Hilaire du Touvet — même point de référence que sonde_infoclimat.py
LAT, LON, NB = 45.3030, 5.8870, 4


def forcer_ipv4():
    _orig = socket.getaddrinfo

    def v4(host, port, family=0, type=0, proto=0, flags=0):
        return _orig(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = v4


def get(url, timeout=60):
    """Renvoie (code, texte, octets). Le corps porte le vrai diagnostic."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            brut = r.read()
            return r.status, brut.decode("utf-8", "replace"), len(brut)
    except urllib.error.HTTPError as e:
        brut = e.read()
        return e.code, brut.decode("utf-8", "replace"), len(brut)
    except Exception as e:                       # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}", 0


def haversine_km(a_lat, a_lon, b_lat, b_lon):
    r = 6371.0
    dlat = math.radians(b_lat - a_lat)
    dlon = math.radians(b_lon - a_lon)
    h = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat))
         * math.sin(dlon / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def stations_proches(n):
    code, txt, _ = get(STATIONS_GEOJSON, timeout=60)
    if code != 200:
        print(f"❌ GeoJSON HTTP {code}")
        return []
    feats = (json.loads(txt).get("features") or [])
    prox = []
    for f in feats:
        g = (f.get("geometry") or {}).get("coordinates") or []
        p = f.get("properties") or {}
        if len(g) < 2 or not p.get("id"):
            continue
        if (p.get("license") or {}).get("source") != "infoclimat.fr":
            continue
        prox.append((haversine_km(LAT, LON, float(g[1]), float(g[0])),
                     str(p["id"]), p.get("name") or "?"))
    prox.sort()
    return prox[:n]


def appel(cle, ids, start, end):
    """Un appel. Renvoie (ok, hourly, octets, diagnostic)."""
    params = [("method", "get"), ("format", "json"),
              ("start", start), ("end", end), ("token", cle)]
    params += [("stations[]", i) for i in ids]
    url = f"{OPENDATA}?{urllib.parse.urlencode(params)}"
    code, txt, octets = get(url)
    if txt.strip() == "Wrong ip address":
        return False, {}, octets, "Wrong ip address (HTTP %d)" % code
    try:
        data = json.loads(txt)
    except ValueError:
        return False, {}, octets, f"non-JSON (HTTP {code}) — {txt[:120]}"
    if data.get("status") != "OK":
        err = json.dumps(data.get("errors", data), ensure_ascii=False)
        return False, {}, octets, f"status={data.get('status')!r} — {err[:160]}"
    return True, (data.get("hourly") or {}), octets, "OK"


def compte(hourly, ids):
    """(total de relevés, détail par station, dernier dh_utc vu)."""
    total, detail, dernier = 0, [], None
    for i in ids:
        pts = hourly.get(i)
        n = len(pts) if isinstance(pts, list) else 0
        total += n
        detail.append(f"{i}:{n}")
        if n:
            dh = pts[-1].get("dh_utc")
            if dh and (dernier is None or dh > dernier):
                dernier = dh
    return total, " ".join(detail), dernier


def main():
    forcer_ipv4()
    cle = os.environ.get("INFOCLIMAT_API_KEY")
    if not cle:
        print("❌ INFOCLIMAT_API_KEY absente.")
        return 2

    st = stations_proches(NB)
    if not st:
        return 2
    ids = [s[1] for s in st]
    print("═══ sonde fenêtre Infoclimat — lecture seule, 7 appels ═══\n")
    print(f"{len(ids)} stations autour de Saint-Hilaire :")
    for d, sid, nom in st:
        print(f"   {d:5.1f} km · {sid:<10} · {nom[:38]}")

    now = datetime.now(timezone.utc)
    jour = now.date().isoformat()
    veille = (now.date() - timedelta(days=1)).isoformat()
    demain = (now.date() + timedelta(days=1)).isoformat()
    h0 = (now - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    h1 = now.strftime("%Y-%m-%d %H:%M:%S")

    essais = [
        ("A · journée entière (code actuel)", jour, jour),
        ("B · 1 h, espace + secondes", h0, h1),
        ("C · 1 h, séparateur T", h0.replace(" ", "T"), h1.replace(" ", "T")),
        ("D · 1 h, sans les secondes", h0[:16], h1[:16]),
        ("E · déborde sur la veille", f"{veille} 23:30:00", f"{jour} 00:30:00"),
        ("F · fenêtre vide (demain)", f"{demain} 03:00:00", f"{demain} 04:00:00"),
        ("G · deux dates pleines (veille→jour)", veille, jour),
    ]

    base_octets = None
    print(f"\n{'essai':<38} {'octets':>8} {'relevés':>8}  détail / diagnostic")
    print("─" * 100)
    for libelle, s, e in essais:
        ok, hourly, octets, diag = appel(cle, ids, s, e)
        if not ok:
            print(f"{libelle:<38} {octets:>8} {'—':>8}  ❌ {diag}")
            continue
        total, detail, dernier = compte(hourly, ids)
        if libelle.startswith("A"):
            base_octets = octets
        ratio = f" ({base_octets / octets:.0f}×)" if base_octets and octets else ""
        print(f"{libelle:<38} {octets:>8}{ratio:<7} {total:>8}  "
              f"{len(hourly)} st · {detail} · dernier {dernier}")

    print("\n── Lecture ──────────────────────────────────────────────────")
    print("   Si B/C/D pèsent AUTANT que A : l'heure est IGNORÉE, et le §1")
    print("   tel qu'écrit ne tient pas. Si elles pèsent nettement moins :")
    print("   le gain est réel et se lit dans la colonne octets.")
    print("   E dit si une fenêtre à cheval sur minuit rend la veille.")
    print("   F dit ce que rend une fenêtre vide : station absente de")
    print("   `hourly`, ou erreur — le module doit garder sa dernière")
    print("   valeur connue dans les deux cas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
