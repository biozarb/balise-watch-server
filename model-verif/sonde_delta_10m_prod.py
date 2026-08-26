#!/usr/bin/env python3
"""Contrôle croisé de la sonde phase B contre l'archive de PRODUCTION.

⛔ Le banc prouve que la sonde fait ce que son auteur croit. Il ne prouve
pas qu'elle mesure la MÊME chose que le job qui tourne toutes les nuits.
Ici on confronte T0 et T1 aux lignes `agrume` / `agrume_pi` réellement
écrites par `agrume_fcst.py` sur le VPS pour le run 00 Z du 25/08.

    ~/venv-balise/bin/python model-verif/_verif_b.py
"""
import gzip, json, pathlib, sys
import numpy as np

ICI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import sonde_delta_10m as B                                  # noqa: E402

NPZ = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/deltab.npz")
ARCH = pathlib.Path("/var/lib/bw-model-verif/fcstagrume/2026/08/"
                    "fcstagrume_2026-08-25.ndjson.gz")

z = np.load(NPZ, allow_pickle=False)
tab, ch = z["table"], [str(x) for x in z["champs"]]
bal = [str(x) for x in z["balise"]]
c = {n: k for k, n in enumerate(ch)}
sers, _ = B.series(tab, ch)

m = (tab[:, c["jour"]] == 20260825) & (tab[:, c["run_h"]] == 0)
print(f"couples du run 2026-08-25T00Z : {int(m.sum())}")

prod = {}
with gzip.open(ARCH, "rt", encoding="utf-8") as f:
    for ligne in f:
        r = json.loads(ligne)
        if r.get("agrume_run") != "2026-08-25T00:00:00Z":
            continue
        prod[(r["model"], str(r["station_id"]))] = r
print(f"lignes de production relues : {len(prod)} "
      f"({len({k[0] for k in prod})} séries)")


idx = np.flatnonzero(m)
ecarts = {"agrume": [], "agrume_pi": []}
manquants = 0
for i in idx:
    sid, h = bal[i], int(tab[i, c["h"]])
    for modele, serie in (("agrume", "T0"), ("agrume_pi", "T1")):
        r = prod.get((modele, sid))
        if r is None:
            manquants += 1
            continue
        v = r["speed"][h] if h < len(r["speed"]) else None
        if v is None:
            continue
        ecarts[modele].append(abs(v - sers[serie][0][i]))

for modele, e in ecarts.items():
    if not e:
        print(f"  {modele} : aucun couple confronté")
        continue
    e = np.asarray(e)
    print(f"  {modele:<10} {len(e):5d} valeurs confrontées — "
          f"écart max {e.max():.4f} km/h, médian {np.median(e):.4f}, "
          f"> 0,05 : {(e > 0.05).sum()}")
print(f"  lignes de production absentes : {manquants}")

# ⛔ Le seuil est 0,05 km/h : `decorer_vent` arrondit au dixième de km/h,
# donc deux chaînes identiques peuvent différer d'un demi-pas d'arrondi
# si elles n'arrondissent pas au même endroit. Au-delà, ce n'est plus de
# l'arrondi.
ok = all((np.asarray(e) <= 0.051).all() for e in ecarts.values() if e)
print("\n" + ("✅ la sonde reproduit EXACTEMENT les deux séries de "
               "production" if ok else
               "❌ ÉCART RÉEL avec la production — le rapport ne mesure "
               "pas ce que le job écrit"))
sys.exit(0 if ok else 1)
