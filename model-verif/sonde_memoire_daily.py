#!/usr/bin/env python3
"""Sonde de l'incident `bw-model-score` — ce que la lecture par clé de
`model_verif_daily` COÛTE vraiment, en temps et en mémoire (07/09/2026).

⛔ POURQUOI CETTE SONDE EXISTE. Le correctif de pagination (offset →
clé) rend la lecture POSSIBLE : les mesures du 07/09 montrent l'offset
650 000 qui expire en `57014` alors que, borné sur `day`, il reste plat
à 0,11-0,24 s. Mais « possible » n'est pas « tenable » : la lecture qui
échouait ramenait 650 000 lignes et mourait AVANT de les rendre ; celle
qui réussit en rend 784 372, et le service a déjà culminé à 3,2 Go avec
896 Mo d'échange sur un VPS de 3,4 Go de RAM. Le correctif peut donc
transformer une lecture qui expire en un run tué par l'OOM — ce qui
serait strictement pire, parce qu'un `57014` se lit dans le journal
alors qu'un OOM ne laisse qu'un code 137.

⚠️ CETTE SONDE N'ÉCRIT RIEN. Une lecture, deux comptages, aucun
`upsert`, aucun `delete`. Elle est rejouable à n'importe quelle heure,
y compris pendant que le service tourne — c'est d'ailleurs le seul
moment où le chiffre de RSS disponible qu'elle imprime a un sens.

    python3 sonde_memoire_daily.py
    python3 sonde_memoire_daily.py --jours 15 --copie

`--copie` refait EN PLUS la copie par ligne de `rolling_scores`
(`r = dict(d)`), pour mesurer le SURCOÛT de cette copie plutôt que de
le supposer. C'est la décision que cette sonde doit permettre de
prendre : garder la copie, ou écrire `unit` dans la ligne lue.
"""
from __future__ import annotations

import argparse
import gc
import pathlib
import resource
import sys
import time
from datetime import datetime, timedelta, timezone

_ICI = pathlib.Path(__file__).resolve().parent
if str(_ICI) not in sys.path:
    sys.path.insert(0, str(_ICI))

import score as SC                                          # noqa: E402


def rss_mo() -> float:
    """Le pic de RSS du processus, en Mo.

    ⚠️ `ru_maxrss` est en Ko sur Linux et en OCTETS sur macOS. Cette
    sonde tourne sur le VPS (Linux) ; la division est donc par 1024. Le
    dire ici plutôt que de laisser un chiffre 1 000 fois faux passer
    pour une bonne nouvelle si quelqu'un la lance sur le Mac.
    """
    ko = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return ko / 1024.0 if sys.platform.startswith("linux") else ko / 1048576.0


def dispo_mo() -> float:
    """La mémoire DISPONIBLE de la machine, pas la libre.

    `MemFree` ment : il ignore le cache réclamable. `MemAvailable` est
    l'estimation du noyau de ce qu'une allocation peut réellement
    obtenir sans échanger — c'est le chiffre qui décide si le run passe.
    """
    try:
        for ligne in pathlib.Path("/proc/meminfo").read_text().splitlines():
            if ligne.startswith("MemAvailable:"):
                return int(ligne.split()[1]) / 1024.0
    except Exception:                                       # noqa: BLE001
        pass
    return float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jours", type=int, default=None,
                    help="fenêtre en jours (défaut : ROLLING_DAYS du run)")
    ap.add_argument("--copie", action="store_true",
                    help="mesurer aussi la copie par ligne de rolling_scores")
    ap.add_argument("--sur-place", action="store_true", dest="sur_place",
                    help="mesurer l'écriture SUR PLACE (le correctif) "
                         "au lieu de la copie")
    a = ap.parse_args()

    jours = a.jours if a.jours is not None else SC.ROLLING_DAYS
    as_of = datetime.now(timezone.utc)
    since = (as_of - timedelta(days=jours)).date().isoformat()

    sb = SC.Supabase()
    print(f"fenêtre : {jours} jours, day >= {since}")
    print(f"RSS au départ    : {rss_mo():8.1f} Mo   "
          f"(disponible {dispo_mo():.0f} Mo)")

    t0 = time.monotonic()
    daily = sb.select_par_cle(
        "model_verif_daily", "day",
        order="day,source,station_id,model,lead_h,fcst_src",
        query=f"?day=gte.{since}")
    dt = time.monotonic() - t0
    apres_lecture = rss_mo()
    print(f"lecture par clé  : {len(daily):>8,} lignes en {dt:6.1f} s"
          .replace(",", " "))
    print(f"RSS après lecture: {apres_lecture:8.1f} Mo   "
          f"(disponible {dispo_mo():.0f} Mo)")
    if daily:
        print(f"  soit {apres_lecture * 1048576 / len(daily):.0f} octets "
              f"par ligne, colonnes : {len(daily[0])}")
        print(f"  colonnes lues : {', '.join(sorted(daily[0]))}")

    if a.copie:
        t1 = time.monotonic()
        units = []
        for d in daily:
            r = dict(d)
            r["unit"] = f"{d['source']}:{d['station_id']}"
            units.append(r)
        dtc = time.monotonic() - t1
        apres_copie = rss_mo()
        print(f"copie par ligne  : {len(units):>8,} unités en {dtc:6.1f} s"
              .replace(",", " "))
        print(f"RSS après copie  : {apres_copie:8.1f} Mo   "
              f"(+{apres_copie - apres_lecture:.0f} Mo, "
              f"disponible {dispo_mo():.0f} Mo)")
        del units

    if a.sur_place:
        # ⭐ LE CORRECTIF, MESURÉ SUR LE MÊME JEU. Même champ écrit, même
        # résultat pour l'appelant ; la seule différence est qu'aucun
        # second dictionnaire n'est fabriqué. C'est ce delta-là qui
        # décide, et non l'intuition qu'« une copie, ça ne coûte rien ».
        t1 = time.monotonic()
        for d in daily:
            d["unit"] = f"{d['source']}:{d['station_id']}"
        dtp = time.monotonic() - t1
        apres_place = rss_mo()
        print(f"écriture SUR PLACE: {len(daily):>8,} lignes en {dtp:6.1f} s"
              .replace(",", " "))
        print(f"RSS après sur-place:{apres_place:8.1f} Mo   "
              f"(+{apres_place - apres_lecture:.0f} Mo, "
              f"disponible {dispo_mo():.0f} Mo)")

    del daily
    gc.collect()
    print(f"RSS après oubli  : {rss_mo():8.1f} Mo   "
          f"(le pic ne redescend pas : `ru_maxrss` EST le pic)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
