#!/usr/bin/env python3
"""Grille fine : l'âge réel de chaque source à l'instant T (pas 5 min),
et le décompte des couples (T, H) qu'un cadre 2 aurait à noter."""
import sys
from collections import defaultdict, Counter
from dispo import latences, dernier_dispo, q, PAS_PI_H, PAS_AROME_H, HORIZON_PI_H


def main(chemin):
    lat_pi, lat_ar = latences(chemin)
    ages_pi, ages_ar, ecarts = [], [], []
    for t in range(0, 24 * 60, 5):
        p = dernier_dispo(t, lat_pi, PAS_PI_H)
        a = dernier_dispo(t, lat_ar, PAS_AROME_H)
        ages_pi.append(p[1])
        ages_ar.append(a[1])
        ecarts.append(a[1] - p[1])
    print("── âge de l'information la plus fraîche, pas de 5 min sur 24 h ──")
    for nom, v in (("PI   ", ages_pi), ("AROME", ages_ar),
                   ("écart", ecarts)):
        print(f"  {nom} : min {min(v):4.0f}  d1 {q(v, .1):4.0f}  "
              f"med {q(v, .5):4.0f}  d9 {q(v, .9):4.0f}  max {max(v):4.0f} min")

    print("\n── couples (instant de décision T, heure cible H) notables ──")
    print("  hypothèse : T aux heures rondes + 30 min, H heures rondes,")
    print("  H strictement futur, H couvert par le run PI disponible.")
    leads = Counter()
    n_couples = 0
    for t_h in range(24):
        t = t_h * 60 + 30
        p = dernier_dispo(t, lat_pi, PAS_PI_H)
        a = dernier_dispo(t, lat_ar, PAS_AROME_H)
        for H in range(t_h + 1, p[0] + HORIZON_PI_H + 1):
            n_couples += 1
            leads[(H - p[0], H - a[0])] += 1
    print(f"  → {n_couples} couples par jour et par balise")
    print("  répartition (lead PI, lead AROME) :")
    for (lp, la), n in sorted(leads.items()):
        print(f"    PI +{lp} h  vs  AROME +{la:2d} h   ×{n}")

    print("\n── si l'on ne garde QU'UN instant de décision par jour ──")
    for t_h in (6, 9, 12):
        t = t_h * 60 + 30
        p = dernier_dispo(t, lat_pi, PAS_PI_H)
        a = dernier_dispo(t, lat_ar, PAS_AROME_H)
        cibles = list(range(t_h + 1, p[0] + HORIZON_PI_H + 1))
        print(f"  T={t_h:02d}:30 Z → {len(cibles)} heures cibles/jour "
              f"({cibles[0]}→{cibles[-1]} Z), PI run {p[0] % 24:02d}Z "
              f"(âge {p[1]:.0f} min), AROME run {a[0] % 24:02d}Z "
              f"(âge {a[1]:.0f} min)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "agrume_latence.ndjson")
