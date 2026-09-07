#!/usr/bin/env python3
"""Ce qui MANQUE vraiment en base après l'incident `bw-model-score`
(07/09/2026) — mesuré avant de rejouer quoi que ce soit.

⛔ POURQUOI NE PAS REJOUER D'EMBLÉE. Le run est mort DANS la lecture de
la fenêtre glissante, c'est-à-dire APRÈS l'agrégat quotidien et son
upsert. Il est donc parfaitement possible que `model_verif_daily` soit
intact pour ces journées et que seul `model_score_zone` ait un trou. Ce
n'est pas la même réparation : rejouer une journée dont la matière est
déjà là coûte le même temps, mais rejouer en croyant qu'elle manque
alors qu'elle est là, c'est ne pas savoir ce qu'on a réparé.

⚠️ CETTE SONDE N'ÉCRIT RIEN. Deux lectures bornées par jour.

    python3 sonde_trou_0709.py
    python3 sonde_trou_0709.py --jours 8
"""
from __future__ import annotations

import argparse
import pathlib
import sys
from datetime import date, timedelta

_ICI = pathlib.Path(__file__).resolve().parent
if str(_ICI) not in sys.path:
    sys.path.insert(0, str(_ICI))

import score as SC                                          # noqa: E402


def combien(sb, table: str, colonne: str, jour: str) -> int:
    """Le nombre de lignes d'un jour, SANS tout rapatrier.

    ⚠️ On demande une seule page bornée et on lit l'en-tête `Content-
    Range` que PostgREST rend avec `Prefer: count=exact` — c'est le seul
    moyen d'avoir le compte sans payer la lecture. Sur une table à
    784 372 lignes, la différence n'est pas cosmétique.
    """
    import json
    import urllib.error
    import urllib.request
    base = f"{table}?{colonne}=eq.{jour}&select={colonne}"
    req = sb._req(base, "GET", None,
                  {"Range-Unit": "items", "Range": "0-0",
                   "Prefer": "count=exact"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            entete = r.headers.get("Content-Range", "")
            json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return -1
    # « 0-0/12345 » ou « */0 »
    return int(entete.rsplit("/", 1)[-1]) if "/" in entete else -1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jours", type=int, default=8)
    a = ap.parse_args()

    sb = SC.Supabase()
    aujourdhui = date.today()
    print(f"{'jour':<12} {'model_verif_daily':>18} {'model_score_zone':>18}")
    print("-" * 52)
    for i in range(a.jours, -1, -1):
        j = (aujourdhui - timedelta(days=i)).isoformat()
        n_daily = combien(sb, "model_verif_daily", "day", j)
        n_score = combien(sb, "model_score_zone", "as_of", j)
        marque = ""
        if n_daily > 0 and n_score == 0:
            marque = "  ⛔ matière présente, AUCUN score"
        elif n_daily == 0 and n_score == 0:
            marque = "  ⚠️ rien du tout"
        print(f"{j:<12} {n_daily:>18,} {n_score:>18,}{marque}"
              .replace(",", " "))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
