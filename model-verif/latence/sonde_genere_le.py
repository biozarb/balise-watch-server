#!/usr/bin/env python3
"""Phase C — `genere_le` : l'instant où NOTRE archive est devenue lisible.

⛔ Ce n'est PAS la latence du poller. Le poller date la publication par
Météo-France ; `genere_le` date l'écriture de nos colonnes. C'est la
seconde qui décide de ce qu'un pilote pouvait voir dans l'app.

Ne lit QUE les `manifest.json` (Class B, quelques ko), jamais les .npz.
Réutilise le bucket, le préfixe d'identifiants et le contexte
d'`agrume_fcst` — on ne recopie pas le geste (cf. `_lire_paire_r2`).

    STORAGE_BACKEND=r2 python3 sonde_genere_le.py 2026-08-24 2026-08-25
"""
import json
import os
import sys
from datetime import datetime

sys.path[:0] = ["tools", "agrume", "verif", "model-verif"]
import agrume_fcst as A  # noqa: E402
from storage import Storage  # noqa: E402

RUNS_A = (0, 3, 6, 9, 12, 15, 18, 21)


def q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))]


def ecart(store, cle, run_iso):
    try:
        brut = store.get(cle)
    except Exception:
        return None
    if not brut:
        return None
    g = json.loads(brut.decode("utf-8")).get("genere_le")
    if not g:
        return "sans genere_le"
    gd = datetime.fromisoformat(g.replace("Z", "+00:00"))
    rd = datetime.fromisoformat(run_iso.replace("Z", "+00:00"))
    return (gd - rd).total_seconds() / 60.0


def main():
    jours = sys.argv[1:] or ["2026-08-24", "2026-08-25"]
    bucket = os.environ.get(A.BUCKET_R2_ENV) or A.BUCKET_R2_DEFAUT
    with A.bucket_r2(bucket, A.prefixe_lecture()):
        store = Storage("agrume-verif", A.BUCKET_SUPABASE_ENV,
                        A.BUCKET_SUPABASE_DEFAUT)

        print("── produit A (AROME) : genere_le − heure du run ──")
        va, manque = [], 0
        for j in jours:
            for h in RUNS_A:
                run = f"{j}T{h:02d}:00:00Z"
                d = ecart(store, f"agrume/colonnes/{run}/manifest.json", run)
                if isinstance(d, float):
                    va.append(d)
                    print(f"  {run} : H+{d:6.0f} min")
                else:
                    manque += 1
                    print(f"  {run} : {d or 'absent'}")
        if va:
            print(f"  → n={len(va)} (+{manque} absents)  min={min(va):.0f}  "
                  f"med={q(va, .5):.0f}  d9={q(va, .9):.0f}  "
                  f"max={max(va):.0f} min")

        print("\n── colonnes AROME-PI : genere_le − heure du run ──")
        vp, manque_pi = [], 0
        for j in jours:
            for h in range(24):
                run = f"{j}T{h:02d}:00:00Z"
                d = ecart(store,
                          f"agrume/pi/colonnes/{j}/{run}/manifest.json", run)
                if isinstance(d, float):
                    vp.append(d)
                else:
                    manque_pi += 1
        if vp:
            print(f"  → n={len(vp)} (+{manque_pi} absents/sans champ)  "
                  f"min={min(vp):.0f}  med={q(vp, .5):.0f}  "
                  f"d9={q(vp, .9):.0f}  max={max(vp):.0f} min")
        else:
            print(f"  aucun manifeste PI exploitable ({manque_pi} tentatives)")


if __name__ == "__main__":
    main()
