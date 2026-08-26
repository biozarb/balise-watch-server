#!/usr/bin/env python3
"""Cadre 1, refait proprement : à l'échéance L, pour quelles heures
cibles AROME est-il publié AVANT l'heure cible ?

⛔ NE PAS appliquer la médiane globale : le §1.1 montre la population
BIMODALE (00/03 Z ~125 min contre 06→21 Z ~195-276 min). On compte donc
run par run, jamais par la médiane.
"""
import json
import sys
from collections import defaultdict
from dispo import PAQUETS_A


def main(chemin):
    J = [json.loads(l) for l in open(chemin) if l.strip()]
    par_run = defaultdict(dict)
    for e in J:
        if e.get("etat") == "publie" and e["source"] in PAQUETS_A:
            par_run[e["run"]][e["source"]] = e["latence_max_min"]
    complets = {r: max(d.values()) for r, d in par_run.items()
                if len(d) == len(PAQUETS_A)}
    print(f"runs avec les 8 paquets datés : {len(complets)}\n")

    print("  L   runs publiés avant l'heure cible   heures cibles/jour")
    for L in range(1, 8):
        seuil = L * 60
        ok = {r: v for r, v in complets.items() if v < seuil}
        # heures de run concernées
        par_h = defaultdict(lambda: [0, 0])
        for r, v in complets.items():
            h = int(r[11:13])
            par_h[h][1] += 1
            if v < seuil:
                par_h[h][0] += 1
        heures_utiles = [h for h, (a, b) in par_h.items() if a / b >= 0.5]
        print(f"  +{L} h  {len(ok):4d}/{len(complets)} "
              f"({100 * len(ok) / len(complets):4.0f} %)"
              f"          {len(heures_utiles)}  "
              f"(runs {sorted(heures_utiles)})")

    print("\n── détail par heure de run : part des runs sous le seuil ──")
    print("  run    <120  <180  <240  <300  <360   n")
    par_h = defaultdict(list)
    for r, v in complets.items():
        par_h[int(r[11:13])].append(v)
    for h in sorted(par_h):
        v = par_h[h]
        cs = [sum(1 for x in v if x < s) for s in (120, 180, 240, 300, 360)]
        print(f"  {h:02d} Z  " + "  ".join(f"{c:4d}" for c in cs)
              + f"  {len(v):4d}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "agrume_latence.ndjson")
