#!/usr/bin/env python3
"""Dépouillement du journal de latence du poller — phase C.
Aucune production : lit agrume_latence.ndjson et imprime.
⚠️ `latence_max_min` = borne HAUTE (vu à). `latence_min_min` = dernier
instant où il était CONFIRMÉ ABSENT. La publication est entre les deux.
Pour « disponible à l'instant T », la borne HAUTE est la seule
affirmation sûre : à H+max, il était là."""
import json
import sys
from collections import defaultdict

PAQUETS_A = ["arome:001/HP1", "arome:001/SP1", "arome:0025/HP1",
             "arome:0025/HP2", "arome:0025/IP1", "arome:0025/IP2",
             "arome:0025/SP1", "arome:0025/SP2"]


def q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))]


def stats(v):
    return (f"n={len(v):4d}  min={min(v):6.0f}  med={q(v, .5):6.0f}  "
            f"d9={q(v, .9):6.0f}  d95={q(v, .95):6.0f}  max={max(v):6.0f}")


def main(chemin):
    J = [json.loads(l) for l in open(chemin) if l.strip()]
    pub = [e for e in J if e.get("etat") == "publie"]
    runs = sorted({e["run"] for e in J})
    print(f"── journal : {len(J)} entrées, {len(pub)} publications, "
          f"{runs[0]} → {runs[-1]}\n")

    print("── 1. AROME-PI (WCS, 24 runs/j) ──")
    pi = [e for e in pub if e["source"] == "aromepi"]
    print("  borne haute      :", stats([e["latence_max_min"] for e in pi]))
    enc = [e for e in pi if e.get("latence_min_min") is not None]
    print("  borne basse      :", stats([e["latence_min_min"] for e in enc]))
    print("  milieu encadr.   :", stats(
        [(e["latence_min_min"] + e["latence_max_min"]) / 2 for e in enc]))
    print(f"  encadrés         : {len(enc)}/{len(pi)}, incertitude médiane "
          f"{q([e['incertitude_min'] for e in enc], .5):.0f} min")

    print("\n── 2. Produit A : le run est ingérable quand le DERNIER des "
          "8 paquets est là ──")
    par_run = defaultdict(dict)
    for e in pub:
        if e["source"] in PAQUETS_A:
            par_run[e["run"]][e["source"]] = e["latence_max_min"]
    complets = {r: d for r, d in par_run.items() if len(d) == len(PAQUETS_A)}
    partiels = {r: d for r, d in par_run.items() if len(d) < len(PAQUETS_A)}
    dernier = [max(d.values()) for d in complets.values()]
    premier = [min(d.values()) for d in complets.values()]
    print(f"  runs avec les 8 paquets datés : {len(complets)} "
          f"(+{len(partiels)} incomplets, écartés)")
    print("  1er paquet       :", stats(premier))
    print("  DERNIER paquet   :", stats(dernier), " ⟵ la latence d'AGRUME")

    print("\n── 3. Par heure de run (dernier paquet, borne haute, min) ──")
    par_h = defaultdict(list)
    for r, d in complets.items():
        par_h[int(r[11:13])].append(max(d.values()))
    for h in sorted(par_h):
        v = par_h[h]
        print(f"  run {h:02d} Z : n={len(v):3d}  med={q(v, .5):5.0f}  "
              f"d9={q(v, .9):5.0f}  max={max(v):5.0f}")

    print("\n── 4. PI par heure de run (borne haute) ──")
    par_h = defaultdict(list)
    for e in pi:
        par_h[int(e["run"][11:13])].append(e["latence_max_min"])
    ligne = []
    for h in sorted(par_h):
        v = par_h[h]
        ligne.append(f"{h:02d}Z:{q(v, .5):.0f}/{len(v)}")
    print("  médiane/n : " + "  ".join(ligne))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "agrume_latence.ndjson")
