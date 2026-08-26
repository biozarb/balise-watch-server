#!/usr/bin/env python3
"""Deux écarts de fraîcheur, et il ne faut pas les confondre :
  · celui du MODÈLE   — publication Météo-France (poller)
  · celui de LA CHAÎNE — écriture de nos colonnes (journal / genere_le)
Plus : l'écart réel entre les 8 paquets du produit A (sans la rallonge).
"""
import json
import sys
from collections import defaultdict
from dispo import latences, dernier_dispo, q, PAS_PI_H, PAS_AROME_H, PAQUETS_A

# mesurés ailleurs, réinjectés ici (cf. la note de phase C)
LAT_ARCHIVE_PI = 40           # médiane, journal du VPS, n = 168
LAT_ARCHIVE_A = 271           # 1re ecriture reconstruite, n = 25


def main(chemin):
    lat_pi, lat_ar = latences(chemin)

    print("── écart entre les 8 paquets du produit A, run par run ──")
    print("  (⚠️ le rapport du poller mélange la rallonge @51 dans ce"
          " chiffre)")
    J = [json.loads(l) for l in open(chemin) if l.strip()]
    par_run = defaultdict(dict)
    for e in J:
        if e.get("etat") == "publie" and e["source"] in PAQUETS_A:
            par_run[e["run"]][e["source"]] = e["latence_max_min"]
    ec = [max(d.values()) - min(d.values())
          for d in par_run.values() if len(d) == len(PAQUETS_A)]
    print(f"  n={len(ec)}  min={min(ec):.0f}  med={q(ec, .5):.0f}  "
          f"d9={q(ec, .9):.0f}  max={max(ec):.0f} min")

    for titre, lp, la in (
            ("MODÈLE — publication Météo-France", lat_pi, lat_ar),
            ("CHAÎNE — écriture de nos colonnes",
             {h: LAT_ARCHIVE_PI for h in range(24)},
             {h: LAT_ARCHIVE_A for h in lat_ar})):
        ages_pi, ages_ar, ecarts = [], [], []
        for t in range(0, 24 * 60, 5):
            p = dernier_dispo(t, lp, PAS_PI_H)
            a = dernier_dispo(t, la, PAS_AROME_H)
            ages_pi.append(p[1])
            ages_ar.append(a[1])
            ecarts.append(a[1] - p[1])
        print(f"\n── âge du plus frais disponible à l'instant T — {titre} ──")
        for nom, v in (("PI   ", ages_pi), ("AROME", ages_ar),
                       ("écart", ecarts)):
            print(f"  {nom} : min {min(v):4.0f}  med {q(v, .5):4.0f}  "
                  f"max {max(v):4.0f} min  "
                  f"({min(v) / 60:.1f} → {max(v) / 60:.1f} h)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "agrume_latence.ndjson")
