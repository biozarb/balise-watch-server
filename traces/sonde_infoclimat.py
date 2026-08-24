#!/usr/bin/env python3
"""
sonde_infoclimat.py — vérifier une clé d'API Infoclimat AVANT de bâtir
quoi que ce soit dessus (02/08/2026).

┌─ POURQUOI CE SCRIPT EXISTE ─────────────────────────────────────────┐
│ Le module Infoclimat du serveur est écrit et complet depuis le      │
│ 17/07/2026 (`refreshInfoclimatObs` dans index.js). Il ne tourne pas │
│ pour UNE raison : `INFOCLIMAT_API_KEY` n'a jamais été créée. Les    │
│ deux calques ont été retirés du menu le 01/08 (commit 721f8ad).     │
│                                                                     │
│ Or la clé Infoclimat est liée à une ADRESSE IP DÉCLARÉE. Un appel   │
│ venu d'ailleurs reçoit `Wrong ip address`. C'est ce qui a fait      │
│ échouer la piste depuis Render, dont les IP sortantes sont          │
│ MULTIPLES : une clé ne peut pas en couvrir plusieurs, donc un poll  │
│ sur deux échouait.                                                  │
│                                                                     │
│ Ce script répond à trois questions, dans l'ordre, sans rien écrire  │
│ nulle part :                                                        │
│   1. Quelle est mon IP sortante RÉELLE ? (c'est celle-là qu'il      │
│      faut déclarer — pas celle du routeur, erreur n°1 sur leur      │
│      forum)                                                         │
│   2. La liste publique des stations répond-elle ? (aucune clé)      │
│   3. La clé fonctionne-t-elle, et que contiennent vraiment les      │
│      relevés ?                                                      │
└─────────────────────────────────────────────────────────────────────┘

⚠️ PIÈGE PRINCIPAL, identique à celui d'Open-Meteo : `Wrong ip address`
   arrive en **HTTP 200**, en texte brut, pas en erreur. Un `if not
   res.ok` ne le voit pas. (Le serveur, lui, le gère déjà correctement :
   `fetchInfoclimatBatch` lit en `text()` avant de parser.)

⚠️ IPv4 FORCÉE. Un utilisateur de leur forum s'est cassé les dents sur
   une IP v6 : on déclare une IPv4, l'appel part en IPv6, la clé est
   refusée sans que rien ne l'explique. Ce script force AF_INET pour que
   l'IP relevée soit exactement celle qui servira.

⚠️ USAGE NON COMMERCIAL. Infoclimat est une association bénévole, et
   sa page open data demande explicitement d'éviter les abus. Ce script
   interroge quelques stations, une fois. Ne pas en faire une boucle.

Usage :
  export INFOCLIMAT_API_KEY="..."        # clé générée sur infoclimat.fr/opendata
  python3 sonde_infoclimat.py            # sonde autour de Saint-Hilaire
  python3 sonde_infoclimat.py --lat 45.80 --lon 6.23 --n 5
  python3 sonde_infoclimat.py --ip-seule # juste l'IP à déclarer, rien d'autre
"""

import argparse
import json
import math
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request

UA = "BaliseWatch-sonde/1.0 (+argonautes.sim@gmail.com)"
IP_ECHO = "https://api.ipify.org"
STATIONS_GEOJSON = ("https://www.data.gouv.fr/api/1/datasets/r/"
                    "8a9e6a12-03f8-4056-861f-70b84136313e")
OPENDATA = "https://www.infoclimat.fr/opendata/"


def forcer_ipv4():
    """Force toutes les résolutions DNS en IPv4.
    Sans ça, l'IP relevée à l'étape 1 peut ne pas être celle qu'utilisera
    l'appel de l'étape 3 — et on déclarerait la mauvaise."""
    _orig = socket.getaddrinfo

    def v4(host, port, family=0, type=0, proto=0, flags=0):
        return _orig(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = v4


def get(url, timeout=20):
    """Renvoie (code_http, texte). Ne lève pas sur un code d'erreur :
    le corps porte souvent le vrai diagnostic."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:                       # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}"


def haversine_km(a_lat, a_lon, b_lat, b_lon):
    r = 6371.0
    dlat = math.radians(b_lat - a_lat)
    dlon = math.radians(b_lon - a_lon)
    h = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat))
         * math.sin(dlon / 2) ** 2)
    return 2 * r * math.asin(math.sqrt(h))


def etape_1_ip():
    print("── 1. IP sortante réelle (IPv4) ─────────────────────────────")
    code, txt = get(IP_ECHO)
    if code != 200 or not txt.strip():
        print(f"   ❌ impossible de relever l'IP (HTTP {code}) — {txt[:120]}")
        return None
    ip = txt.strip()
    print(f"   {ip}")
    print("   ⚠️ C'est CETTE adresse qu'il faut déclarer sur")
    print("      https://www.infoclimat.fr/opendata/ — pas celle affichée")
    print("      par ton routeur (erreur n°1 sur leur forum).")
    print("   ⚠️ Une IP domestique change au gré du FAI. Pour un service")
    print("      qui tourne, il faut une IP fixe (VPS) ou refaire la clé.")
    return ip


def etape_2_stations(lat, lon, n):
    print("\n── 2. Liste publique des stations (aucune clé requise) ──────")
    code, txt = get(STATIONS_GEOJSON, timeout=40)
    if code != 200:
        print(f"   ❌ HTTP {code} — {txt[:200]}")
        return []
    try:
        geo = json.loads(txt)
    except ValueError:
        print(f"   ❌ réponse non-JSON — {txt[:200]}")
        return []
    feats = geo.get("features") or []
    print(f"   ✅ {len(feats)} stations dans le GeoJSON data.gouv.fr")

    proches = []
    for f in feats:
        g = (f.get("geometry") or {}).get("coordinates") or []
        p = f.get("properties") or {}
        if len(g) < 2:
            continue
        try:
            slon, slat = float(g[0]), float(g[1])
        except (TypeError, ValueError):
            continue
        sid = p.get("id")
        if not sid:
            continue
        # ⚠️ `license` est un OBJET, pas une chaîne (relevé le 02/08 sur
        # le vrai fichier) : {code, license, url, source}. Et la licence
        # VARIE d'une station à l'autre — Etalab pour les stations
        # Météo-France reprises, CC BY / CC BY-NC pour les contributeurs
        # StatIC. C'est la raison d'être de ce champ ici : afficher une
        # station sans porter SA licence n'est pas une option.
        lic = p.get("license") or {}
        proches.append((haversine_km(lat, lon, slat, slon), str(sid),
                        p.get("name") or "?",
                        lic.get("license") or "?",
                        lic.get("source") or "?"))
    proches.sort()
    retenues = proches[:n]
    print(f"   {n} plus proches de {lat:.4f}, {lon:.4f} :")
    for d, sid, nom, lic, src in retenues:
        print(f"     {d:6.1f} km · {sid:<10} · {nom[:32]:<32} · {lic[:24]:<24} · {src}")
    return retenues


def etape_3_cle(stations, cle):
    print("\n── 3. Requête authentifiée ──────────────────────────────────")
    if not cle:
        print("   ⏭  INFOCLIMAT_API_KEY absente — étape sautée.")
        print("      Pour la créer : compte sur infoclimat.fr, puis")
        print("      https://www.infoclimat.fr/opendata/ → déclarer l'usage")
        print("      NON COMMERCIAL et générer une clé pour l'IP ci-dessus.")
        return False
    if not stations:
        print("   ⏭  aucune station à interroger (étape 2 en échec).")
        return False

    from datetime import date
    jour = date.today().isoformat()
    params = [("method", "get"), ("format", "json"),
              ("start", jour), ("end", jour), ("token", cle)]
    params += [("stations[]", s[1]) for s in stations]
    url = f"{OPENDATA}?{urllib.parse.urlencode(params)}"
    print(f"   {len(stations)} stations · journée {jour}")

    code, txt = get(url, timeout=60)
    # ⚠️ Le diagnostic est DANS le corps, pas dans le code HTTP.
    if txt.strip() == "Wrong ip address":
        print(f"   ❌ « Wrong ip address » (HTTP {code}) — la clé est liée")
        print("      à une autre IP que celle relevée à l'étape 1.")
        print("      Regénère une clé pour cette IP-là, ou corrige la")
        print("      déclaration. C'est le cas le plus fréquent.")
        return False
    try:
        data = json.loads(txt)
    except ValueError:
        print(f"   ❌ réponse non-JSON (HTTP {code}) — {txt[:200]}")
        return False
    if data.get("status") != "OK":
        print(f"   ❌ status={data.get('status')!r} — "
              f"{json.dumps(data.get('errors', data), ensure_ascii=False)[:300]}")
        return False

    hourly = data.get("hourly") or {}
    print(f"   ✅ status OK · {len(hourly)} stations dans la réponse")
    utiles = 0
    for d, sid, nom, _lic, _src in stations:
        pts = hourly.get(sid)
        if not isinstance(pts, list) or not pts:
            print(f"     {sid:<10} {nom[:28]:<28} — aucun relevé aujourd'hui")
            continue
        p = pts[-1]
        vent = p.get("vent_moyen")
        raf = p.get("vent_rafales")
        dirv = p.get("vent_direction")
        pres = p.get("pression")
        temp = p.get("temperature")
        if vent is not None:
            utiles += 1
        print(f"     {sid:<10} {nom[:28]:<28} {p.get('dh_utc','?')} · "
              f"vent {vent} raf {raf} dir {dirv} · {pres} hPa · {temp} °C "
              f"({len(pts)} relevés)")
    print(f"\n   {utiles}/{len(stations)} stations avec du VENT exploitable.")
    print("   ⚠️ `vent_rafales` souvent null : limitation de l'OPENDATA,")
    print("      pas de la station. Mesuré le 24/08 (sonde_rafale_infoclimat)")
    print("      sur 00003 : null sur 225 relevés, alors que sa page")
    print("      infoclimat.fr affiche les rafales et que ses métadonnées")
    print("      déclarent un Davis Vantage Pro 2. Rien à corriger ici.")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    # Saint-Hilaire du Touvet par défaut : dans le périmètre de bêta, et
    # l'un des deux seuls sites avec un corpus de vols.
    ap.add_argument("--lat", type=float, default=45.3030)
    ap.add_argument("--lon", type=float, default=5.8870)
    ap.add_argument("--n", type=int, default=8, help="stations à sonder")
    ap.add_argument("--ip-seule", action="store_true",
                    help="relever l'IP à déclarer, puis s'arrêter")
    args = ap.parse_args()

    forcer_ipv4()
    print("═══ sonde Infoclimat — aucune écriture, aucun effet de bord ═══\n")
    etape_1_ip()
    if args.ip_seule:
        return 0
    stations = etape_2_stations(args.lat, args.lon, args.n)
    ok = etape_3_cle(stations, os.environ.get("INFOCLIMAT_API_KEY"))

    print("\n── Suite ────────────────────────────────────────────────────")
    if ok:
        print("   La clé fonctionne depuis cette IP. Deux choses AVANT de")
        print("   rallumer les calques (commit 721f8ad à inverser) :")
        print("   · l'IP doit être FIXE — donc un VPS, pas ta box ni")
        print("     Render (IP sortantes multiples, cause du blocage) ;")
        print("   · ne pas poller les ~1200 stations toutes les 15 min.")
        print("     Association bénévole : se limiter aux stations utiles")
        print("     (proches décos/balises) et à la dernière heure.")
    else:
        print("   Rien n'est cassé — le module serveur dégrade en silence")
        print("   tant que la clé manque. Reprendre à l'étape en échec.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
