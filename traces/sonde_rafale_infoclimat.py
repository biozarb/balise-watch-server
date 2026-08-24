#!/usr/bin/env python3
"""
sonde_rafale_infoclimat.py — LECTURE SEULE, un seul appel opendata.

Question posée (24/08/2026, retour Yann) : le site d'Infoclimat affiche
une rafale pour la station 00003 (Besse sur Issole) — 30,6 km/h à 15h30
le 24/08 — alors que notre `latest.json` porte `raf: null` au MÊME
horodatage, avec la même moyenne. Sur 875 stations d'historique, 27
seulement ont une série `raf`.

`parse_point()` du poller ne lit qu'une clé, `vent_rafales`, et personne
n'a jamais regardé la liste des clés RÉELLEMENT renvoyées par l'API. Ce
script les imprime, station par station, sans rien écrire nulle part.

  ssh balise
  set -a; source ~/.balise-watch-r2.env; set +a
  python3 sonde_rafale_infoclimat.py
"""
import json
import os
import socket
import sys
import urllib.parse
import urllib.request
import gzip
import io
from datetime import datetime, timedelta, timezone

OPENDATA = "https://www.infoclimat.fr/opendata/"
UA = "BaliseWatch/1.0 (+argonautes.sim@gmail.com; https://balise-watch.app)"

# 00003 : le site montre une rafale, notre pipeline non → le cas du bug.
# 00047 : une des 27 stations dont la rafale ARRIVE bien → le témoin.
STATIONS = ["00003", "00047"]


def forcer_ipv4():
    _orig = socket.getaddrinfo

    def v4(host, port, family=0, type=0, proto=0, flags=0):
        return _orig(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = v4


def get(url, timeout=120):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        brut = r.read()
        if "gzip" in (r.headers.get("Content-Encoding") or "").lower():
            brut = gzip.GzipFile(fileobj=io.BytesIO(brut)).read()
        return r.status, brut.decode("utf-8", "replace")


def main():
    cle = os.environ.get("INFOCLIMAT_API_KEY")
    if not cle:
        print("INFOCLIMAT_API_KEY absente — "
              "set -a; source ~/.balise-watch-r2.env; set +a")
        return 2
    forcer_ipv4()
    jour = datetime.now(timezone.utc).date()
    veille = jour - timedelta(days=1)
    params = [("method", "get"), ("format", "json"),
              ("start", veille.isoformat()), ("end", jour.isoformat()),
              ("token", cle)]
    params += [("stations[]", s) for s in STATIONS]
    code, txt = get(f"{OPENDATA}?{urllib.parse.urlencode(params)}")
    if txt.strip() == "Wrong ip address":
        print(f"❌ Wrong ip address (HTTP {code})")
        return 1
    data = json.loads(txt)
    print(f"status={data.get('status')!r} · clés racine={sorted(data.keys())}")
    hourly = data.get("hourly") or {}
    print(f"stations dans la réponse : {sorted(hourly.keys())}")
    # ⚠️ Ces deux blocs sont la moitié de la réponse : ils disent quels
    # champs l'API PRÉTEND servir. Tant que personne ne les avait
    # ouverts, « la rafale est absente » et « la rafale est prévue mais
    # arrive vide » se ressemblaient — ce sont deux diagnostics opposés.
    print(f"champs annoncés (hourly._params) : {hourly.get('_params')}")
    meta = data.get("metadata") or {}
    print("métadonnées vent : "
          + json.dumps({k: v for k, v in meta.items() if "vent" in k},
                       ensure_ascii=False) + "\n")

    for sid in STATIONS:
        pts = hourly.get(sid)
        if not isinstance(pts, list) or not pts:
            print(f"── {sid} : aucun relevé\n")
            continue
        print(f"── {sid} · {len(pts)} relevés")
        print(f"   clés d'un relevé : {sorted(pts[-1].keys())}")
        for p in pts[-3:]:
            print(f"   {p.get('dh_utc')} → "
                  + json.dumps(p, ensure_ascii=False)[:400])
        # Toute clé qui ressemble à une rafale, quel que soit son nom.
        suspectes = sorted({k for p in pts for k in p
                            if any(m in k.lower()
                                   for m in ("raf", "gust", "max", "vent"))})
        print(f"   clés « vent/rafale/max » vues : {suspectes}")
        for k in suspectes:
            vals = [p.get(k) for p in pts if p.get(k) not in (None, "")]
            print(f"     {k:<22} {len(vals)}/{len(pts)} non nuls"
                  + (f" · ex. {vals[-3:]}" if vals else ""))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
