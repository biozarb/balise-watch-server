#!/usr/bin/env python3
"""test_melange.py — banc du mélange multi-modèle et de la dispersion
(lot L19, 04/09/2026). Sans réseau, sans base, sans `score.py`.

⚠️ Les entrées parlent la langue de `collect.py` (`t0` + `step_s`,
`speed`/`dir` par ligne) — même règle que `test_score.py`.
"""
from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import melange as MX     # noqa: E402
import scoring as S      # noqa: E402

OK = KO = 0


def check(label: str, cond: bool, detail: str = ""):
    global OK, KO
    if cond:
        OK += 1
    else:
        KO += 1
        print(f"  ❌ {label}" + (f"\n       {detail}" if detail else ""))


T0 = 1_756_944_000          # 2026-09-04 00:00 UTC


def ligne(model, speed, direction, station="900", t0=T0, step=3600,
          fetched="2026-09-04T03:10:00+00:00", **extra):
    n = len(speed)
    row = {"station_id": station, "source": "pioupiou", "lat": 45.0,
           "lon": 6.0, "model": model, "fetched_at": fetched,
           "t0": t0, "step_s": step, "speed": list(speed),
           "dir": list(direction) if direction is not None else [None] * n,
           "gust": [None] * n}
    row.update(extra)
    return row


# ══════════════════════════════════════════════════════════════════
print("── 1. LA MÉMOIRE D'ERREUR ET LES POIDS ──")
# ══════════════════════════════════════════════════════════════════
a, b = MX.AccMse(), MX.AccMse()
for i in range(10):
    a.push(i, 4.0)        # RMS 2 km/h
    b.push(i, 16.0)       # RMS 4 km/h
p = MX.poids_depuis_mse({"bon": a, "moins": b})
check("deux membres → deux poids qui somment à 1",
      p is not None and abs(sum(p.values()) - 1) < 1e-9, f"{p}")
check("⭐ le poids est l'INVERSE de la MSE : 4 fois moins d'erreur "
      "quadratique → 4 fois plus de poids",
      p is not None and abs(p["bon"] / p["moins"] - 4.0) < 1e-9, f"{p}")

c = MX.AccMse()
for i in range(MX.MIX_MIN_JOURS - 1):
    c.push(i, 1.0)
check("un membre sous MIX_MIN_JOURS n'a pas de poids",
      "jeune" not in (MX.poids_depuis_mse({"bon": a, "moins": b, "jeune": c}) or {}))
check("un seul membre avec assez de jours → PAS de mélange (None)",
      MX.poids_depuis_mse({"bon": a, "jeune": c}) is None)

d = MX.AccMse()
for i in range(10):
    d.push(i, 0.0001)     # calme plat : RMS 0,01
p2 = MX.poids_depuis_mse({"bon": a, "plat": d})
check("⛔ la MSE est plafonnée par le bas (MIX_MSE_MIN) : un calme plat "
      "ne vaut pas un poids infini",
      p2 is not None and p2["plat"] / p2["bon"] <= 4.0 + 1e-9, f"{p2}")

# la demi-vie : dix jours à 16 puis cinq à 1 → la mémoire descend
# nettement sous la moyenne plate (11)
e = MX.AccMse()
for i in range(10):
    e.push(i, 16.0)
for i in range(10, 15):
    e.push(i, 1.0)
check("la mémoire pèse davantage les journées récentes",
      e.mean is not None and e.mean < 11.0 - 1.0, f"{e.mean}")
check("… et une journée déjà intégrée est refusée",
      (e.push(14, 100.0), e.days)[1] == 15)

# ══════════════════════════════════════════════════════════════════
print("── 2. LES MEMBRES : qui a le droit d'entrer ──")
# ══════════════════════════════════════════════════════════════════
rows = [
    ligne("ecmwf_ifs025", [10] * 3, [0] * 3),
    ligne("meteofrance_arome_france_hd", [10] * 3, [0] * 3),
    ligne("arome_r2", [10] * 3, [0] * 3),
    ligne("agrume", [10] * 3, [0] * 3),
    ligne("agrume_pi", [10] * 3, [0] * 3),
    ligne("agrume_court_w1", [10] * 3, [0] * 3, lead_h=-1),
    ligne("agrume_quart_w1", [10] * 3, [0] * 3, step=900, lead_h=-3),
    ligne("bw_mix", [10] * 3, [0] * 3, synthese="bw_mix"),
]
m = {r["model"] for r in MX.membres(rows)}
check("⛔ une seule lecture de la famille AROME : la chaîne de référence",
      "meteofrance_arome_france_hd" in m and "arome_r2" not in m
      and "agrume" not in m, f"{m}")
check("agrume_pi (AROME + PI, le produit servi) est un membre à part entière",
      "agrume_pi" in m, f"{m}")
check("les lignes qui déclarent une échéance (classe courte / quart) "
      "n'entrent pas", "agrume_court_w1" not in m and "agrume_quart_w1" not in m)
check("un mélange n'entre pas dans un mélange", "bw_mix" not in m)
check("ECMWF entre", "ecmwf_ifs025" in m)

sans_hd = [r for r in rows if r["model"] != "meteofrance_arome_france_hd"]
m2 = {r["model"] for r in MX.membres(sans_hd)}
check("sans la chaîne de référence, c'est `arome_r2` qui parle pour AROME",
      "arome_r2" in m2 and "agrume" not in m2, f"{m2}")

# ══════════════════════════════════════════════════════════════════
print("── 3. LE MÉLANGE EN (u, v) ──")
# ══════════════════════════════════════════════════════════════════
nord = ligne("a", [10.0, 10.0, 10.0], [0.0, 0.0, 0.0])
sud = ligne("b", [10.0, 10.0, 10.0], [180.0, 180.0, 180.0])
mix = MX.melanger([nord, sud], {"a": 0.5, "b": 0.5})
check("⭐ deux vents OPPOSÉS de même force se mélangent en vent NUL "
      "(espace vectoriel, leçon du L9c) — pas en 10 km/h",
      mix is not None and all(abs(s) < 1e-6 for s in mix["speed"]),
      f"{mix and mix['speed']}")
check("… dont le cap est nul (indéfini), pas 0°",
      mix is not None and all(d is None for d in mix["dir"]))
check("… et la dispersion vaut la force des membres (10 km/h)",
      mix is not None and all(abs(sp - 10.0) < 1e-6 for sp in mix["spread"]),
      f"{mix and mix['spread']}")

est = ligne("a", [10.0, 20.0], [90.0, 90.0])
est2 = ligne("b", [20.0, 10.0], [90.0, 90.0])
mix2 = MX.melanger([est, est2], {"a": 0.75, "b": 0.25})
check("même cap → la force est la moyenne PONDÉRÉE (0,75·10 + 0,25·20)",
      mix2 is not None and abs(mix2["speed"][0] - 12.5) < 1e-6
      and abs(mix2["speed"][1] - 17.5) < 1e-6, f"{mix2 and mix2['speed']}")
check("… et le cap est celui des membres", mix2["dir"] == [90.0, 90.0])

mix3 = MX.melanger([est, est2], None)
check("poids None = moyenne uniforme (15 partout)",
      mix3 is not None and all(abs(s - 15.0) < 1e-6 for s in mix3["speed"]))
check("… publiée sous le nom du témoin quand on le demande",
      MX.melanger([est, est2], None, MX.MODEL_MIX_TEMOIN)["model"] == "bw_mix_u")

# une heure manquante chez un membre : les poids se renormalisent
troue = ligne("a", [10.0, None], [90.0, 90.0])
mix4 = MX.melanger([troue, est2], {"a": 0.75, "b": 0.25})
check("une heure manquante chez un membre ne tire pas le mélange vers "
      "zéro : l'autre membre parle seul (10 km/h)",
      mix4 is not None and abs(mix4["speed"][1] - 10.0) < 1e-6,
      f"{mix4 and mix4['speed']}")
check("… et la dispersion y est nulle (un seul membre présent)",
      abs(mix4["spread"][1]) < 1e-9)

# des grilles décalées : le mélange couvre l'union, aligné sur les heures
tard = ligne("b", [20.0, 10.0], [90.0, 90.0], t0=T0 + 3600)
mix5 = MX.melanger([est, tard], {"a": 0.5, "b": 0.5})
check("des grilles décalées d'une heure s'alignent sur l'HEURE VALIDE, "
      "pas sur la position dans le tableau",
      mix5 is not None and mix5["t0"] == T0 and len(mix5["speed"]) == 3
      and abs(mix5["speed"][1] - 20.0) < 1e-6,     # 0,5·20 + 0,5·20
      f"{mix5 and (mix5['t0'], mix5['speed'])}")

# un membre sans girouette : il n'entre pas dans le vecteur
sans_cap = ligne("b", [30.0, 30.0], None)
mix6 = MX.melanger([est, sans_cap], {"a": 0.5, "b": 0.5})
check("un membre sans cap n'entre pas dans le vecteur quand un autre en a",
      mix6 is not None and abs(mix6["speed"][0] - 10.0) < 1e-6)
mix7 = MX.melanger([ligne("a", [10.0], None), ligne("b", [30.0], None)],
                   {"a": 0.5, "b": 0.5})
check("… mais quand AUCUN n'en a, la force seule est moyennée (20)",
      mix7 is not None and abs(mix7["speed"][0] - 20.0) < 1e-6
      and mix7["dir"] == [None])

check("la ligne se déclare : synthese, hors_caractere, mix_n, step 3600",
      mix2["synthese"] == "bw_mix" and mix2["hors_caractere"] is True
      and mix2["mix_n"] == 2 and mix2["step_s"] == 3600)
vieux = ligne("a", [10.0], [90.0], fetched="2026-09-04T01:00:00+00:00")
frais = ligne("b", [10.0], [90.0], fetched="2026-09-04T03:00:00+00:00")
check("⚠️ fetched_at = le membre le plus ANCIEN (pas de fraîcheur volée)",
      MX.melanger([vieux, frais], {"a": 0.5, "b": 0.5})["fetched_at"]
      == "2026-09-04T01:00:00+00:00")
check("un seul membre → pas de mélange", MX.melanger([est], {"a": 1.0}) is None)
check("un membre absent des poids n'entre pas — et s'il ne reste qu'un "
      "membre, pas de mélange", MX.melanger([est, est2], {"a": 1.0}) is None)

# ══════════════════════════════════════════════════════════════════
print("── 4. AJOUTER AUX SNAPSHOTS ──")
# ══════════════════════════════════════════════════════════════════
snaps = {0: [ligne("ecmwf_ifs025", [10] * 4, [0] * 4),
             ligne("icon_d2", [12] * 4, [0] * 4),
             ligne("ecmwf_ifs025", [10] * 4, [0] * 4, station="901"),
             ligne("icon_d2", [12] * 4, [0] * 4, station="901")],
         1: [ligne("ecmwf_ifs025", [10] * 4, [0] * 4),
             ligne("icon_d2", [12] * 4, [0] * 4)]}
poids = {("pioupiou:900", 6): {"ecmwf_ifs025": 0.5, "icon_d2": 0.5},
         ("pioupiou:901", 6): {"ecmwf_ifs025": 0.5, "icon_d2": 0.5}}
out, bilan = MX.ajouter_melange(snaps, poids, {0: 6, 1: 24})
check("les snapshots d'entrée ne sont PAS modifiés",
      len(snaps[0]) == 4 and len(snaps[1]) == 2)
n_mix0 = sum(1 for r in out[0] if r["model"] == "bw_mix")
check("offset 0 : un bw_mix par balise qui a des poids",
      n_mix0 == 2, f"{bilan}")
check("offset 1 : aucun poids pour la classe +24 h → aucun bw_mix, et "
      "le bilan compte la balise SANS poids",
      sum(1 for r in out[1] if r["model"] == "bw_mix") == 0
      and bilan[1][2] == 1, f"{bilan}")
temoins = sum(1 for off in out for r in out[off] if r["model"] == "bw_mix_u")
check("le témoin uniforme n'est écrit que sur l'échantillon (crc % pas)",
      temoins == (int(MX.est_temoin("pioupiou:900")) * 2
                  + int(MX.est_temoin("pioupiou:901"))), f"{temoins}")
check("est_temoin est déterministe", MX.est_temoin("pioupiou:900")
      == MX.est_temoin("pioupiou:900"))
check("le bilan se dit", "bw_mix" in MX.dire_bilan(bilan, {0: 6, 1: 24}))

# ══════════════════════════════════════════════════════════════════
print("── 5. LE TÉMOIN : meilleur membre A PRIORI et moyenne uniforme ──")
# ══════════════════════════════════════════════════════════════════
def _row(unit, model, err, lead=6):
    src, sid = unit.split(":")
    return {"source": src, "station_id": sid, "model": model,
            "lead_h": lead, "err_vec_med": err}

rows_j, poids_j = [], {}
for i in range(40):
    u = f"pioupiou:{i}"
    poids_j[(u, 6)] = {"a": 0.7, "b": 0.3}
    rows_j += [_row(u, "a", 3.0), _row(u, "b", 2.0),       # b meilleur ce jour
               _row(u, "bw_mix", 2.5), _row(u, "bw_mix_u", 2.6)]
bm = MX.bilan_melange(rows_j, poids_j)
check("le bilan existe dès 30 couples", bm is not None)
check("⛔ la référence est le membre du plus gros POIDS (a, 3,0) — pas le "
      "meilleur du jour (b, 2,0) : on ne compare pas à un oracle",
      bm and bm["contre_meilleur_membre"]["err_reference"] == 3.0, f"{bm}")
check("… le mélange (2,5) fait donc mieux, dans 100 % des cas",
      bm and bm["contre_meilleur_membre"]["mix_meilleur_pct"] == 100.0)
check("… et contre l'uniforme (2,6), il gagne un peu",
      bm and bm["contre_uniforme"]["err_reference"] == 2.6
      and bm["contre_uniforme"]["gain_pct"] > 0)
check("sous 30 couples → None", MX.bilan_melange(rows_j[:100], poids_j) is None)

# ══════════════════════════════════════════════════════════════════
print("── 6. LA DISPERSION PRÉDIT-ELLE L'ERREUR ? ──")
# ══════════════════════════════════════════════════════════════════
def _disp_rows(pente):
    out = []
    for i in range(200):
        sp = 0.5 + i * 0.05
        out.append({"model": "bw_mix", "spread_kmh": sp,
                    "err_vec_rms": 2.0 + pente * sp + (0.3 if i % 3 else -0.3)})
    return out

bd = MX.bilan_dispersion(_disp_rows(1.0))
check("une erreur qui monte avec la dispersion → `exploitable`",
      bd is not None and bd["verdict"] == "exploitable", f"{bd and bd['texte']}")
check("… dix déciles, avec leur n", bd and len(bd["deciles"]) == 10
      and sum(d["n"] for d in bd["deciles"]) == 200)
check("… et rho proche de 1", bd and bd["rho_spearman"] > 0.9)

bd0 = MX.bilan_dispersion(_disp_rows(0.0))
check("⛔ une erreur INDÉPENDANTE de la dispersion → `non_exploitable` : "
      "aucune pastille de confiance", bd0 is not None
      and bd0["verdict"] == "non_exploitable", f"{bd0 and bd0['texte']}")
check("sous DISP_MIN_N balise-jours → rien (None), ni oui ni non",
      MX.bilan_dispersion(_disp_rows(1.0)[:50]) is None)
check("les lignes des AUTRES modèles n'entrent pas dans la courbe",
      MX.bilan_dispersion([dict(r, model="icon_d2") for r in _disp_rows(1.0)])
      is None)
check("Spearman : monotone croissant → 1", abs(MX.spearman([1, 2, 3, 4],
                                                            [10, 20, 30, 40]) - 1) < 1e-9)
check("Spearman : décroissant → −1", abs(MX.spearman([1, 2, 3],
                                                      [3, 2, 1]) + 1) < 1e-9)
check("Spearman : les ex æquo reçoivent le rang moyen",
      MX._rangs([5, 5, 1]) == [2.5, 2.5, 1.0])

# ══════════════════════════════════════════════════════════════════
print(f"\n{'✅' if KO == 0 else '❌'} {OK} assertions vertes, {KO} rouges.\n")
sys.exit(1 if KO else 0)
