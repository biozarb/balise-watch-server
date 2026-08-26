#!/usr/bin/env python3
"""« Que pouvais-tu savoir à l'instant T ? » — simulation de DISPONIBILITÉ,
à partir des latences MESURÉES par le poller (aucune heure codée en dur).

⚠️ On prend la borne HAUTE de la latence : c'est la seule affirmation
sûre (« à H+max il était là »). Utiliser la borne basse ferait croire à
une fraîcheur qu'on n'a pas vérifiée.
"""
import json
import sys
from collections import defaultdict

PAQUETS_A = ["arome:001/HP1", "arome:001/SP1", "arome:0025/HP1",
             "arome:0025/HP2", "arome:0025/IP1", "arome:0025/IP2",
             "arome:0025/SP1", "arome:0025/SP2"]
HORIZON_PI_H = 6            # agrume/pi : 0 → 6 h
PAS_PI_H = 1                # 24 runs/jour
PAS_AROME_H = 3             # 8 runs/jour


def q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))]


def latences(chemin):
    J = [json.loads(l) for l in open(chemin) if l.strip()]
    pub = [e for e in J if e.get("etat") == "publie"]
    pi = defaultdict(list)
    for e in pub:
        if e["source"] == "aromepi":
            pi[int(e["run"][11:13])].append(e["latence_max_min"])
    par_run = defaultdict(dict)
    for e in pub:
        if e["source"] in PAQUETS_A:
            par_run[e["run"]][e["source"]] = e["latence_max_min"]
    ar = defaultdict(list)
    for r, d in par_run.items():
        if len(d) == len(PAQUETS_A):
            ar[int(r[11:13])].append(max(d.values()))
    # médiane par heure de run — mesurée, pas supposée
    return ({h: q(v, .5) for h, v in pi.items()},
            {h: q(v, .5) for h, v in ar.items()})


def dernier_dispo(t_min, lat, pas_h, horizon_h=None):
    """Heure du run le plus frais publié à l'instant t (minutes depuis 00 Z),
    en remontant. Renvoie (heure_run_absolue, age_min) ou None."""
    for k in range(0, 48):
        h = ((int(t_min // 60) - k) // pas_h) * pas_h
        if h % pas_h:
            continue
        l = lat.get(h % 24)
        if l is None:
            continue
        if h * 60 + l <= t_min:
            return h, t_min - h * 60
    return None


def main(chemin):
    lat_pi, lat_ar = latences(chemin)
    print("── latences médianes retenues (borne haute, mesurées) ──")
    print("  PI    :", {h: round(v) for h, v in sorted(lat_pi.items())})
    print("  AROME :", {h: round(v) for h, v in sorted(lat_ar.items())})

    print("\n── ÂGE de l'information la plus fraîche disponible à l'instant T ──")
    print("  T(Z)   PI: run   âge      AROME: run   âge      écart")
    ages_pi, ages_ar = [], []
    for t_h in range(24):
        t = t_h * 60 + 30              # milieu d'heure
        p = dernier_dispo(t, lat_pi, PAS_PI_H)
        a = dernier_dispo(t, lat_ar, PAS_AROME_H)
        ages_pi.append(p[1])
        ages_ar.append(a[1])
        print(f"  {t_h:02d}:30   {p[0] % 24:02d}Z   {p[1]:4.0f} min      "
              f"{a[0] % 24:02d}Z   {a[1]:4.0f} min    "
              f"{a[1] - p[1]:5.0f} min")
    print(f"\n  âge PI    : médiane {q(ages_pi, .5):.0f} min, "
          f"min {min(ages_pi):.0f}, max {max(ages_pi):.0f}")
    print(f"  âge AROME : médiane {q(ages_ar, .5):.0f} min, "
          f"min {min(ages_ar):.0f}, max {max(ages_ar):.0f}")
    ec = [a - p for a, p in zip(ages_ar, ages_pi)]
    print(f"  écart     : médiane {q(ec, .5):.0f} min, "
          f"min {min(ec):.0f}, max {max(ec):.0f}")

    print("\n── À l'instant T, quelles heures cibles H les DEUX couvrent-ils ? ──")
    print("  (PI : run+0 → run+6 h · AROME : run+0 → run+24 h)")
    n_h = defaultdict(int)
    for t_h in range(24):
        t = t_h * 60 + 30
        p = dernier_dispo(t, lat_pi, PAS_PI_H)
        a = dernier_dispo(t, lat_ar, PAS_AROME_H)
        # heures cibles rondes strictement futures couvertes par PI
        cibles = [H for H in range(t_h + 1, p[0] + HORIZON_PI_H + 1)
                  if H >= t_h + 1]
        leads_pi = [H - p[0] for H in cibles]
        leads_ar = [H - a[0] for H in cibles]
        n_h[len(cibles)] += 1
        if t_h % 3 == 0:
            print(f"  T={t_h:02d}:30 → {len(cibles)} heures cibles "
                  f"({cibles[0] if cibles else '-'}→"
                  f"{cibles[-1] if cibles else '-'} Z) · "
                  f"lead PI {leads_pi} · lead AROME {leads_ar}")
    print("  répartition du nombre d'heures cibles par instant T :",
          dict(sorted(n_h.items())))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "agrume_latence.ndjson")
