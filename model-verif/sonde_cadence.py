#!/usr/bin/env python3
"""sonde_cadence.py — à quelle vitesse Open-Meteo dit-il non ? (07/08/2026)

⚠️ POURQUOI CETTE SONDE EXISTE. Le premier run complet sur le VPS a perdu
**24 points sur 648** en `HTTP 429 Too Many Requests`, alors que
`BATCH_PAUSE_S = 0.25` donne 240 requêtes/min et que `QUOTA_MINUTE` vaut
600 dans le code. Le plafond réel n'est donc pas celui qu'on croit — et
comme aucun modèle Météo-France n'a d'historique de runs passés, chacun
de ces 24 points est une nuit perdue pour cette balise, définitivement.

On mesure au lieu de raisonner : c'est la règle qui a déjà servi deux
fois contre la documentation d'Open-Meteo le 08/08.

Le protocole : N requêtes à la cadence C, on compte les 429 et on lit les
en-têtes de limitation s'il y en a. Une pause entre les séries, sinon la
seconde hérite de la fenêtre de la première.

    python3 sonde_cadence.py --n 30 --cadences 0.25,0.6

⚠️ Cette sonde CONSOMME du quota : ~1,07 appel pondéré par requête, comme
le vrai run. À 30 × 2 séries, c'est 64 appels sur 10 000.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import collect as C                                     # noqa: E402

# Des points réels du réseau, pas une grille inventée : on veut la même
# taille de réponse et les mêmes modèles servis que le vrai run.
POINTS = [(45.20, 6.70), (44.39, 0.82), (43.66, 3.95), (47.26, -0.11),
          (46.54, 7.11), (45.06, 5.10), (43.46, 0.85), (47.36, -2.49),
          (44.69, 5.35), (48.85, 2.35)]


def une_requete(lat: float, lon: float, jours: int = 3):
    """Même requête que `collect.fetch_forecast`, en rendant le statut."""
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": ",".join(C._hourly_vars()),
        "models": ",".join(C.MODELS),
        "forecast_days": jours, "timeformat": "unixtime",
        "wind_speed_unit": "kmh",
    }
    url = f"{C.FORECAST_API}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(url, timeout=45) as r:
            entetes = {k.lower(): v for k, v in r.headers.items()
                       if "rate" in k.lower() or "retry" in k.lower()}
            r.read()
            return 200, entetes
    except urllib.error.HTTPError as e:
        entetes = {k.lower(): v for k, v in e.headers.items()
                   if "rate" in k.lower() or "retry" in k.lower()} if e.headers else {}
        return e.code, entetes
    except Exception as exc:                            # noqa: BLE001
        return f"ERR {type(exc).__name__}", {}


def serie(n: int, cadence: float) -> None:
    print(f"\n── {n} requêtes à {cadence}s ({60 / cadence:.0f}/min)")
    codes = collections.Counter()
    entetes_vus: dict[str, str] = {}
    t0 = time.time()
    # ⚠️ On garde QUAND chaque refus tombe, pas seulement combien il y en
    # a. Une série de 30 requêtes n'a montré aucun 429 là où le run
    # complet en a eu 24 : c'est donc que le refus dépend d'un cumul ou
    # d'une fenêtre, et un total ne dirait rien de sa forme. Les échecs
    # du run arrivaient par paquets de six, régulièrement — c'est cette
    # forme-là qu'il faut voir.
    refus: list[tuple[int, float]] = []
    for i in range(n):
        code, ent = une_requete(*POINTS[i % len(POINTS)])
        codes[code] += 1
        entetes_vus.update(ent)
        if code != 200:
            refus.append((i + 1, time.time() - t0))
        time.sleep(cadence)
    duree = time.time() - t0
    print(f"   {dict(codes)}  en {duree:.0f}s "
          f"({n / duree * 60:.0f} requêtes/min réelles)")
    if refus:
        apercu = ", ".join(f"n°{i} à {t:.0f}s" for i, t in refus[:20])
        print(f"   {len(refus)} refus — {apercu}"
              + (" …" if len(refus) > 20 else ""))
    print(f"   en-têtes de limitation : {entetes_vus or 'AUCUN'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--cadences", default="0.25,0.6")
    ap.add_argument("--repos", type=float, default=70,
                    help="pause entre deux séries, en s (la fenêtre de "
                         "limitation doit se vider, sinon la 2e série "
                         "hérite de la 1re)")
    args = ap.parse_args()

    print(f"modèles demandés : {len(C.MODELS)} — variables : {len(C._hourly_vars())}")
    cadences = [float(x) for x in args.cadences.split(",")]
    for i, c in enumerate(cadences):
        if i:
            print(f"\n   … repos de {args.repos:.0f}s")
            time.sleep(args.repos)
        serie(args.n, c)
    return 0


if __name__ == "__main__":
    sys.exit(main())
