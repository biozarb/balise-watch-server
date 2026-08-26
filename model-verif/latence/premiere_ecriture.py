#!/usr/bin/env python3
"""Où passent les 3 h entre la publication d'AROME et `genere_le` ?

⚠️ RECONSTRUCTION, pas mesure directe. Hypothèse unique, écrite ici :
`ingest_colonnes.choisir_run()` retient le run le plus récent dont les
8 paquets sont couverts. Un workflow qui DÉMARRE dans la fenêtre
[P(R), P(R suivant)[ traite donc R, et sa fin est la première écriture
des colonnes de R.

Entrées : agrume_latence.ndjson  et  runs_actions.json, obtenu par
  curl -s "https://api.github.com/repos/biozarb/balise-watch-server/\
actions/workflows/331042625/runs?per_page=100&created=%3E2026-08-22"
(dépôt public, aucun jeton).
"""
import json
import sys
from collections import defaultdict
from datetime import datetime

from dispo import PAQUETS_A, q

# genere_le mesuré le 26/08 par sonde_genere_le.py (min après le run)
GENERE_LE = {
    "2026-08-22": [315, 479, 337, 419, 399, 481, 420, 336],
    "2026-08-23": [318, 483, 418, 392, 393, 478, 412, 329],
    "2026-08-24": [316, 321, 405, 391, 394, 481, 418, 331],
    "2026-08-25": [312, 316, 403, 402, 398, 496, 416, 324],
}
HEURES = (0, 3, 6, 9, 12, 15, 18, 21)


def iso(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() / 60


def main(journal="agrume_latence.ndjson", actions="runs_actions.json"):
    J = [json.loads(l) for l in open(journal) if l.strip()]
    par_run = defaultdict(dict)
    for e in J:
        if e.get("etat") == "publie" and e["source"] in PAQUETS_A:
            par_run[e["run"]][e["source"]] = e["latence_max_min"]
    P = {r: iso(r) + max(d.values())
         for r, d in par_run.items() if len(d) == len(PAQUETS_A)}

    wf = json.load(open(actions))["workflow_runs"]
    ok = sorted((iso(w.get("run_started_at") or w["created_at"]),
                 iso(w["updated_at"]), w["event"])
                for w in wf if w["conclusion"] == "success")

    runs = sorted(P)
    premiers, ecarts = [], []
    print(f"{'run':<22}{'P(R)':>7}{'1re ecr':>9}{'genere_le':>11}"
          f"{'ecart':>8}  event")
    for i, r in enumerate(runs):
        suivant = P[runs[i + 1]] if i + 1 < len(runs) else float("inf")
        cand = [(f, ev) for d, f, ev in ok if P[r] <= d < suivant]
        jour, h = r[:10], int(r[11:13])
        if jour not in GENERE_LE or not cand:
            continue
        g = GENERE_LE[jour][HEURES.index(h)]
        base = iso(r)
        prem = cand[0][0] - base
        premiers.append(prem)
        ecarts.append(g - prem)
        print(f"{r:<22}{P[r] - base:7.0f}{prem:9.0f}{g:11.0f}"
              f"{g - prem:8.0f}  {cand[0][1]}")

    if premiers:
        print(f"\n1re ecriture reconstruite : n={len(premiers)} "
              f"min={min(premiers):.0f} med={q(premiers, .5):.0f} "
              f"max={max(premiers):.0f} min apres le run")
        print(f"reecriture par le filet   : mediane "
              f"{q(ecarts, .5):.0f} min plus tard")


if __name__ == "__main__":
    main(*(sys.argv[1:] or []))
