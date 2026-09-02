#!/usr/bin/env python3
"""Sonde L9(c) — pourquoi `mse_comb` dépasse SES DEUX composantes.

⛔ LECTURE SEULE. Elle n'écrit rien, ne pousse rien, ne touche pas à la
base : elle relit l'archive locale d'une journée déjà notée et refait,
à la main, les trois MSE de la ligne `model_verif_daily`.

Ce qu'elle départage (lot L9(c), reprise du 31/08/2026) :

 (1) LES TROIS MSE SONT-ILS SUR LA MÊME POPULATION D'HEURES ?
     `mse_persist` vient de `skill_vs_persistence` (heures où la veille
     existe), `mse_clim` de `skill_vs_climatology` (heures où la
     climatologie existe), `mse_comb` de `skill_vs_combined` (les deux à
     la fois). La sonde recalcule les trois sur l'INTERSECTION et
     recompte les violations.

 (2) LE `k` RÉELLEMENT APPLIQUÉ. Lu dans le cache `clim_*_v2.json.gz`,
     c'est-à-dire le nombre qui est ENTRÉ dans le mélange cette nuit-là,
     pas le ρ du journal.

 (3) L'ESPACE DU MÉLANGE. `combined_reference` mélange la FORCE en
     scalaire et le CAP en vecteurs unitaires ; `pair_error` mesure une
     erreur VECTORIELLE. La sonde recalcule un `mse_comb` mélangé DANS
     L'ESPACE DE L'ERREUR (u, v) et recompte les violations.
     ⚠️ Ce n'est PAS une proposition de correctif : c'est la mesure qui
     dit si la borne de Jensen s'applique là où on la teste.
"""
from __future__ import annotations

import argparse
import math
import pathlib
import sys
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import score as J          # noqa: E402
import scoring as S        # noqa: E402
import inference as INF    # noqa: E402


def melange_uv(k: float, persist, clim_h):
    """Le mélange convexe fait DANS L'ESPACE (u, v) — celui où
    `pair_error` mesure. Rendu `(force, cap)` pour rester comparable.

    ⓘ Sa force est SYSTÉMATIQUEMENT ≤ celle du mélange publié (inégalité
    triangulaire) : c'est exactement l'objection écrite dans la
    docstring de `combined_reference`, et c'est pour ça que le choix
    d'aujourd'hui n'est pas un bug — c'est un arbitrage.
    """
    sp, dp = persist
    sc, dc = clim_h[0], clim_h[1]
    if dp is None or dc is None:
        return k * sp + (1.0 - k) * sc, (dp if dc is None else dc)
    up, vp = S.to_uv(sp, dp)
    uc, vc = S.to_uv(sc, dc)
    u = k * up + (1.0 - k) * uc
    v = k * vp + (1.0 - k) * vc
    f = math.hypot(u, v)
    if f < 1e-12:
        return 0.0, None
    return f, S.from_uv(u, v)


def analyse_serie(pairs, obs_for_skill, clim_u, k, utc_offset_s, detail=False):
    """Rend un dict de MSE, chacun sur la population annoncée."""
    lignes = []
    for p in pairs:
        ps, pd = S.persistence_reference(obs_for_skill, p.t)
        hod = ((p.t // 1000 + utc_offset_s) // 3600) % 24
        c = clim_u.get(hod) if clim_u else None
        if c is not None and not S._finite(c[0]):
            c = None
        e_m, _ = S.pair_error(p)
        e_p = e_c = e_cb = e_uv = None
        if ps is not None:
            e_p, _ = S.pair_error(replace(p, fcst_speed=ps, fcst_dir=pd))
        if c is not None:
            e_c, _ = S.pair_error(replace(p, fcst_speed=c[0], fcst_dir=c[1]))
        if ps is not None and c is not None and k is not None:
            fs, fd = INF.combined_reference(k, (ps, pd), c)
            e_cb, _ = S.pair_error(replace(p, fcst_speed=fs, fcst_dir=fd))
            gs, gd = melange_uv(k, (ps, pd), c)
            e_uv, _ = S.pair_error(replace(p, fcst_speed=gs, fcst_dir=gd))
        lignes.append({"t": p.t, "obs": (p.obs_speed, p.obs_dir),
                       "fcst": (p.fcst_speed, p.fcst_dir),
                       "persist": (ps, pd), "clim": c,
                       "comb": (INF.combined_reference(k, (ps, pd), c)
                                if (ps is not None and c is not None
                                    and k is not None) else None),
                       "e_m": e_m, "e_p": e_p, "e_c": e_c,
                       "e_cb": e_cb, "e_uv": e_uv})

    def mse(champ, sous=None):
        v = [L[champ] for L in lignes
             if L[champ] is not None and (sous is None or sous(L))]
        return (sum(x * x for x in v) / len(v), len(v)) if len(v) >= 2 else (None, len(v))

    inter = lambda L: L["e_cb"] is not None          # noqa: E731
    out = {
        "n_pairs": len(lignes),
        "mse_persist": mse("e_p"), "mse_clim": mse("e_c"),
        "mse_comb": mse("e_cb"), "mse_uv": mse("e_uv"),
        "mse_persist_inter": mse("e_p", inter),
        "mse_clim_inter": mse("e_c", inter),
        "lignes": lignes if detail else None,
    }
    return out


def day_start_ms_de(day):
    return int(day.timestamp()) * 1000


def mesure_poids(root, day, clim, poids, obs_by, prev_by, day_start_ms,
                 utc_offset_s):
    """⭐ ÉTAPE (4) — `k = ρ` est-il le poids qui MINIMISE le MSE ?

    ⛔ SUR LES COUPLES RÉELS, PAS SUR DES MÉDIANES. La déduction du
    29/08 (`k* ≈ −0,01`) était de l\'arithmétique sur trois médianes ;
    elle ne peut pas être vraie ligne à ligne, et elle est écrite comme
    telle dans le suivi. Ici on balaie `k` de 0 à 1 par pas de 0,01 sur
    la grille horaire de CHAQUE balise, et on prend l\'argmin.

    ⓘ Sans aucun modèle : les trois références ne dépendent que de
    l\'observation, et c\'est ce qui rend cette mesure comparable d\'une
    balise à l\'autre.
    """
    import statistics as st
    grille = [i / 100 for i in range(101)]
    lignes = []
    for unit, k in poids.items():
        obs = obs_by.get(unit)
        clim_u = clim.get(unit)
        if not obs or not clim_u:
            continue
        obs_for_skill = (prev_by.get(unit) or []) + obs
        times = [day_start_ms + h * 3_600_000 for h in range(24)]
        pairs = S.pair_series(times, [1.0] * 24, None, obs)
        trip = []
        for p in pairs:
            ps, pd = S.persistence_reference(obs_for_skill, p.t)
            hod = ((p.t // 1000 + utc_offset_s) // 3600) % 24
            c = clim_u.get(hod)
            if ps is None or c is None or not S._finite(c[0]):
                continue
            trip.append((p, (ps, pd), c))
        if len(trip) < 6:
            continue
        def mse_k(kk, uv=False):
            s2 = 0.0
            for p, pers, c in trip:
                f, d = (melange_uv(kk, pers, c) if uv
                        else INF.combined_reference(kk, pers, c))
                e, _ = S.pair_error(replace(p, fcst_speed=f, fcst_dir=d))
                s2 += e * e
            return s2 / len(trip)
        vals = [mse_k(x) for x in grille]
        k_opt = grille[min(range(len(vals)), key=lambda i: vals[i])]
        vals_uv = [mse_k(x, uv=True) for x in grille]
        k_opt_uv = grille[min(range(len(vals_uv)), key=lambda i: vals_uv[i])]
        lignes.append({"unit": unit, "k": k, "n": len(trip),
                       "k_opt": k_opt, "k_opt_uv": k_opt_uv,
                       "mse_k": mse_k(k), "mse_opt": vals[grille.index(k_opt)],
                       "mse_clim": vals[0], "mse_persist": vals[100],
                       "mse_uv_k": mse_k(k, uv=True)})
    if not lignes:
        print("aucune balise mesurable")
        return 0
    n = len(lignes)
    print(f"\n══ ÉTAPE (4) — le poids, mesuré sur les couples de {n} balises ══")
    print(f"  k appliqué (ρ borné) : médiane {st.median([L['k'] for L in lignes]):.4f}")
    print(f"  k* qui minimise le MSE (mélange publié) : médiane "
          f"{st.median([L['k_opt'] for L in lignes]):.4f}")
    print(f"  k* qui minimise le MSE (mélange (u,v))  : médiane "
          f"{st.median([L['k_opt_uv'] for L in lignes]):.4f}")
    print(f"  balises où k* = 0 (climatologie PURE optimale) : "
          f"{sum(1 for L in lignes if L['k_opt'] == 0)} / {n}")
    print(f"  balises où k* >= k appliqué : "
          f"{sum(1 for L in lignes if L['k_opt'] >= L['k'])} / {n}")
    print(f"  MSE médian : à k appliqué {st.median([L['mse_k'] for L in lignes]):.3f} · "
          f"à k* {st.median([L['mse_opt'] for L in lignes]):.3f} · "
          f"clim pure {st.median([L['mse_clim'] for L in lignes]):.3f} · "
          f"persist pure {st.median([L['mse_persist'] for L in lignes]):.3f} · "
          f"mélange (u,v) à k appliqué {st.median([L['mse_uv_k'] for L in lignes]):.3f}")
    pire = [L for L in lignes if L["mse_k"] > min(L["mse_clim"], L["mse_persist"])]
    print(f"  balises où le mélange PUBLIÉ fait pire que la meilleure de ses "
          f"deux composantes : {len(pire)} / {n}")
    pire_uv = [L for L in lignes if L["mse_uv_k"] > min(L["mse_clim"], L["mse_persist"])]
    print(f"  idem pour le mélange (u,v) : {len(pire_uv)} / {n}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True)
    ap.add_argument("--out", default="/var/lib/bw-model-verif")
    ap.add_argument("--utc-offset-h", type=float, default=2.0)
    ap.add_argument("--unit", help="source:station_id — détail heure par heure")
    ap.add_argument("--model", default=None)
    ap.add_argument("--lead", type=int, default=None)
    ap.add_argument("--units", help="fichier de balises 'source:id' à balayer")
    ap.add_argument("--dump", help="CSV de controle : une ligne par "
                    "(balise, modele, echeance), pour recoupement avec la base")
    ap.add_argument("--poids", action="store_true",
                    help="mesure le k qui minimise le MSE sur les couples "
                         "reels (etape 4 du lot) - independant de tout modele")
    args = ap.parse_args()

    root = pathlib.Path(args.out)
    day = datetime.strptime(args.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    utc_offset_s = int(args.utc_offset_h * 3600)

    clim, poids = J.climatology_by_station(root, day, None, utc_offset_s)
    print(f"clim : {len(clim)} balises · k : {len(poids)} balises")
    ks = sorted(poids.values())
    if ks:
        print(f"  k médian {ks[len(ks)//2]:.4f} · k = 0 exact : "
              f"{sum(1 for v in ks if v == 0.0)} · k = 1 exact : "
              f"{sum(1 for v in ks if v == 1.0)} · k hors [0,1] : "
              f"{sum(1 for v in ks if v < 0.0 or v > 1.0)}")

    obs_day = J.all_obs_rows(root, day, None)
    obs_prev = J.all_obs_rows(root, day - timedelta(days=1), None)
    obs_by = {f"{r['source']}:{r['station_id']}": J.to_obs_samples(r) for r in obs_day}
    prev_by = {f"{r['source']}:{r['station_id']}": J.to_obs_samples(r) for r in obs_prev}
    print(f"obs : {len(obs_by)} balises · veille : {len(prev_by)}")

    if args.poids:
        return mesure_poids(root, day, clim, poids, obs_by, prev_by,
                            day_start_ms_de(day), utc_offset_s)

    cibles = None
    if args.units:
        cibles = {l.strip() for l in open(args.units) if l.strip()}
    if args.unit:
        cibles = {args.unit}

    dump = open(args.dump, "w") if args.dump else None
    if dump:
        dump.write("unit,model,lead_h,n_pairs,n_p,n_c,n_cb,"
                   "mse_persist,mse_clim,mse_comb,mse_uv,"
                   "mse_persist_inter,mse_clim_inter\n")
    day_start_ms = int(day.timestamp()) * 1000
    total = defaultdict(int)
    meds = defaultdict(list)
    exces_uv = []
    par_balise = defaultdict(lambda: defaultdict(int))
    for offset, lead_defaut in J.LEAD_BY_OFFSET.items():
        emis = day - timedelta(days=offset)
        for row in J.snapshot_rows(root, emis, None):
            key = f"{row['source']}:{row['station_id']}"
            if cibles is not None and key not in cibles:
                continue
            lead_h = row.get("lead_h", lead_defaut)
            if args.lead is not None and lead_h != args.lead:
                continue
            if args.model and row["model"] != args.model:
                continue
            obs = obs_by.get(key)
            if not obs:
                continue
            times = J.fcst_times_ms(row)
            idx = [i for i, t in enumerate(times)
                   if day_start_ms <= t < day_start_ms + J.DAY_MS]
            if not idx:
                continue
            sub_t = [times[i] for i in idx]
            sub_s = [(row.get("speed") or [None] * len(times))[i] for i in idx]
            sub_d = [(row.get("dir") or [None] * len(times))[i] for i in idx]
            pairs = S.pair_series(sub_t, sub_s, sub_d, obs)
            if len(pairs) < J.MIN_HOURS_DAILY:
                continue
            obs_for_skill = (prev_by.get(key) or []) + obs
            k = poids.get(key)
            r = analyse_serie(pairs, obs_for_skill, clim.get(key), k,
                              utc_offset_s, detail=bool(args.unit))
            mp, mc, mcb = r["mse_persist"][0], r["mse_clim"][0], r["mse_comb"][0]
            if None in (mp, mc, mcb):
                continue
            if dump:
                dump.write("%s,%s,%s,%d,%d,%d,%d,%s,%s,%s,%s,%s,%s\n" % (
                    key, row["model"], lead_h, r["n_pairs"],
                    r["mse_persist"][1], r["mse_clim"][1], r["mse_comb"][1],
                    mp, mc, mcb, r["mse_uv"][0],
                    r["mse_persist_inter"][0], r["mse_clim_inter"][0]))
            total["lignes"] += 1
            viol = mcb > max(mp, mc)
            total["viol_publie"] += int(viol)
            mpi, mci = r["mse_persist_inter"][0], r["mse_clim_inter"][0]
            viol_inter = (mpi is not None and mci is not None
                          and mcb > max(mpi, mci))
            total["viol_pop_commune"] += int(viol_inter)
            total["pop_identique"] += int(
                r["mse_persist"][1] == r["mse_clim"][1] == r["mse_comb"][1])
            muv = r["mse_uv"][0]
            if muv is not None and mpi is not None and mci is not None:
                meds["persist"].append(mpi); meds["clim"].append(mci)
                meds["comb"].append(mcb); meds["uv"].append(muv)
                if muv > max(mpi, mci):
                    total["viol_uv"] += 1
                    exces_uv.append(100 * (muv - max(mpi, mci)) / max(mpi, mci))
            if viol:
                par_balise[key]["viol"] += 1
                par_balise[key]["k"] = k
                par_balise[key]["viol_inter"] = par_balise[key].get("viol_inter", 0) + int(viol_inter)
                par_balise[key]["viol_uv"] = par_balise[key].get("viol_uv", 0) + int(
                    muv is not None and muv > max(mpi or mp, mci or mc))

            if args.unit:
                print(f"\n── {key} · {row['model']} · +{lead_h} h · k = {k}")
                print(f"   MSE publiés  : persist {mp:9.3f} (n={r['mse_persist'][1]}) · "
                      f"clim {mc:9.3f} (n={r['mse_clim'][1]}) · comb {mcb:9.3f} (n={r['mse_comb'][1]})")
                print(f"   MÊME POPULATION (celle du mélange) : persist "
                      f"{mpi if mpi is None else round(mpi,3)} · clim "
                      f"{mci if mci is None else round(mci,3)} · comb {mcb:.3f}"
                      f"   → violation : {viol_inter}")
                print(f"   mélange DANS L'ESPACE DE L'ERREUR (u,v) : "
                      f"{muv if muv is None else round(muv,3)}")
                if r["lignes"]:
                    print("   heure UTC | obs (f,cap) | persist | clim | comb publié | comb (u,v) |"
                          " err persist / clim / comb / (u,v)")
                    for L in r["lignes"]:
                        h = datetime.fromtimestamp(L["t"] / 1000, timezone.utc).strftime("%H:%M")
                        f = lambda x: ("—" if x is None else            # noqa: E731
                                       f"{x[0]:5.1f}@{'—' if x[1] is None else format(x[1],'5.0f')}")
                        g = lambda x: "—" if x is None else f"{x:6.2f}"  # noqa: E731
                        print(f"   {h} | {f(L['obs'])} | {f(L['persist'])} | {f(L['clim'])} | "
                              f"{f(L['comb'])} | {f(melange_uv(k, L['persist'], L['clim'])) if (L['persist'][0] is not None and L['clim'] is not None and k is not None) else '—'} | "
                              f"{g(L['e_p'])} {g(L['e_c'])} {g(L['e_cb'])} {g(L['e_uv'])}")

    print("\n══════ BILAN ══════")
    if meds["comb"]:
        import statistics as _st
        n = len(meds["comb"])
        print(f"  médianes sur les {n} lignes portant les quatre références, "
              f"TOUTES sur la population du mélange :")
        for nom in ("persist", "clim", "comb", "uv"):
            print(f"     {nom:8s} {_st.median(meds[nom]):9.3f}")
        print(f"     comb publié <= min(persist, clim) : "
              f"{sum(1 for i in range(n) if meds['comb'][i] <= min(meds['persist'][i], meds['clim'][i]))}")
        print(f"     comb (u,v)  <= min(persist, clim) : "
              f"{sum(1 for i in range(n) if meds['uv'][i] <= min(meds['persist'][i], meds['clim'][i]))}")
    if exces_uv:
        import statistics as _st
        print(f"  violations SURVIVANTES en espace (u,v) : dépassement relatif "
              f"médian {_st.median(exces_uv):.3f} % · max {max(exces_uv):.3f} %")
    for k2 in ("lignes", "viol_publie", "viol_pop_commune", "viol_uv", "pop_identique"):
        print(f"  {k2:20s} : {total[k2]}")
    if par_balise:
        print("  balises en violation (publié) :", len(par_balise))
        for u, d in sorted(par_balise.items()):
            print(f"    {u:20s} k={d['k']!r:8} viol={d['viol']:3d} "
                  f"· pop commune={d['viol_inter']:3d} · espace (u,v)={d['viol_uv']:3d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
