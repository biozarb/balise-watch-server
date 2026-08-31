#!/usr/bin/env python3
"""Critère d'acceptation du lot « rafale sur le calque vent sol » (31/08/2026).

⚠️ CE TEST NE DÉPEND PAS DE L'ŒIL. C'est l'équivalent, pour ce lot, de
l'invariant du composite : il rejoue le VRAI code d'ingestion
(`arome-wind/ingest.py`, importé tel quel — aucune copie de la formule
ici) sur un VRAI run, puis RECALCULE indépendamment `hypot(max_10efg,
max_10nfg)` en relisant le GRIB à la main, et compare.

Deux choses vérifiées, celles qui peuvent faire mentir une carte :

  1. ✅ la valeur écrite dans la tuile rafale = hypot(e, n) × 3,6 arrondi
     à l'entier, à un point pris AU HASARD dans la grille ;
  2. ⛔ la valeur à τ = 0 est `null`, PAS 0 et PAS le vent moyen — un
     `gust` qui vaudrait le `speed` serait une rafale FABRIQUÉE (faute du
     24/08), et un 0 se lirait comme « air calme prévu » alors que la
     donnée n'existe simplement pas à cette échéance.

Coût : DEUX fichiers GRIB (00H et 03H de SP1, ~23 Mo pièce), supprimés au
fil de l'eau. La BBOX est rétrécie à une fenêtre de 0,2° le temps du test
— on vérifie une FORMULE, pas une couverture géographique, et la France
entière prendrait dix minutes pour dire la même chose.

Usage :  python3 tools/rafale-tuile-selftest.py
"""
import os, sys, math, random
from datetime import datetime, timezone, timedelta

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, os.pardir, "arome-wind"))
sys.path.insert(0, ICI)

import ingest                                              # noqa: E402
from mf_s3 import s3_keys, download_tmp                    # noqa: E402
from eccodes import (codes_grib_new_from_file, codes_get,  # noqa: E402
                     codes_get_values, codes_release)

# Fenêtre minuscule : ~20 × 20 points au pas natif 0,01°, autour du
# Vercors (relief marqué, donc des valeurs qui ne se ressemblent pas).
ingest.BBOX = dict(latmin=44.9, latmax=45.1, lonmin=5.5, lonmax=5.7)

ECHEC = []


def verifier(ok, libelle, detail=""):
    print(("  ✅ " if ok else "  ⛔ ") + libelle + (f"  — {detail}" if detail else ""))
    if not ok:
        ECHEC.append(libelle)


def trouver_run():
    """Le run le plus récent dont SP1 publie AU MOINS 00H et 03H."""
    base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    base -= timedelta(hours=base.hour % 3)
    for back in range(5):
        run = base - timedelta(hours=3 * back)
        ref = run.strftime("%Y-%m-%dT%H:00:00Z")
        keys = list(s3_keys(f"pnt/{ref}/arome/001/SP1/"))
        k00 = [k for k in keys if "__00H__" in k]
        k03 = [k for k in keys if "__03H__" in k]
        if k00 and k03:
            return ref, run, sorted(k00)[0], sorted(k03)[0]
    raise SystemExit("Aucun run AROME SP1 avec 00H et 03H publiés.")


def lire_champ_a_la_main(path, shortname):
    """Relecture INDÉPENDANTE du GRIB — volontairement sans passer par
    `ingest.parse_grib` : si les deux lectures partageaient le code, le
    test comparerait la formule à elle-même."""
    with open(path, "rb") as f:
        while True:
            gid = codes_grib_new_from_file(f)
            if gid is None:
                return None, None
            try:
                if codes_get(gid, "shortName") == shortname:
                    meta = dict(Ni=codes_get(gid, "Ni"), Nj=codes_get(gid, "Nj"),
                                lat0=codes_get(gid, "latitudeOfFirstGridPointInDegrees"),
                                lon0=ingest._norm_lon(
                                    codes_get(gid, "longitudeOfFirstGridPointInDegrees")),
                                di=codes_get(gid, "iDirectionIncrementInDegrees"),
                                dj=codes_get(gid, "jDirectionIncrementInDegrees"),
                                jScan=codes_get(gid, "jScansPositively"),
                                stepType=codes_get(gid, "stepType"),
                                stepRange=str(codes_get(gid, "stepRange")))
                    vals = codes_get_values(gid)
                    codes_release(gid)
                    return vals, meta
            except Exception:
                pass
            codes_release(gid)


def main():
    ref, run, k00, k03 = trouver_run()
    print(f"Run AROME : {ref}")
    print(f"  00H : {k00.split('/')[-1]}")
    print(f"  03H : {k03.split('/')[-1]}")
    ingest._RUN_HOUR_UTC = run.hour

    # ── 1. Le vrai chemin d'ingestion, sur ces deux échéances ─────────
    p00, p03 = download_tmp(k00), download_tmp(k03)
    try:
        sol_want = lambda sn, tol, lvl: (sn if (tol == "heightAboveGround"      # noqa: E731
                                                and (sn in ("10u", "10v")
                                                     or sn in ingest.GUST_SN))
                                         else None)
        brut, meta = {}, None
        for p in (p00, p03):
            part, m = ingest.parse_grib(p, sol_want, "float32")
            meta = meta or m
            for k, byhstep in part.items():
                brut.setdefault(k, {}).update(byhstep)

        print(f"\nChamps vus dans SP1 : {sorted(brut)}")
        verifier(set(brut) >= {"10u", "10v"}, "le vent moyen est là (10u/10v)")
        verifier(set(brut) >= set(ingest.GUST_SN),
                 f"les composantes de rafale sont là {ingest.GUST_SN}")

        data = {("u" if k == "10u" else "v"): v for k, v in brut.items() if k in ("10u", "10v")}
        gust = {("e" if k == ingest.GUST_SN[0] else "n"): v
                for k, v in brut.items() if k in ingest.GUST_SN}

        verifier(0 in data["u"] and 0 not in gust.get("e", {}),
                 "τ = 0 : vent moyen présent, rafale ABSENTE du GRIB",
                 f"échéances moyen {sorted(data['u'])} / rafale {sorted(gust.get('e', {}))}")

        steps = sorted(set(data["u"]) & set(data["v"]))
        times = [(run + timedelta(hours=s)).strftime("%Y-%m-%dT%H:%M") for s in steps]
        gust_steps = [s for s in steps if s in gust.get("e", {}) and s in gust.get("n", {})]
        gust_times = [times[i] for i, s in enumerate(steps) if s in gust_steps]
        uvg = {s: (gust["e"][s], gust["n"][s]) for s in gust_steps}

        # La passe SOL d'abord : elle collecte les vitesses moyennes que la
        # passe RAFALE doit porter (`speedMean`), exactement comme main().
        uvm = {s: (data["u"][s], data["v"][s]) for s in steps}
        vitesses = []
        t_moy = ingest.build_grids(uvm, meta, steps, times, "sol", None,
                                   ingest.STEP_SOL, sortie_vitesses=vitesses)
        moy = next(iter(t_moy.values()))
        tuiles = ingest.build_grids(uvg, meta, steps, times, "rafale", None,
                                    ingest.STEP_SOL, entree_vitesses=vitesses)
        tuile = next(iter(tuiles.values()))
        tuile["gustTimes"] = gust_times
        print(f"\nTuile construite : {len(tuile['points'])} points, "
              f"times={tuile['times']}, gustTimes={tuile['gustTimes']}")

        # ── 2. τ = 0 : `null`, pas 0, pas le vent moyen ───────────────
        i0 = steps.index(0)
        nuls = all(p["speed"][i0] is None and p["dir"][i0] is None for p in tuile["points"])
        verifier(nuls, "τ = 0 : `null` partout dans la tuile rafale (ni 0, ni valeur empruntée)",
                 f"exemple : speed={tuile['points'][0]['speed'][i0]!r} "
                 f"dir={tuile['points'][0]['dir'][i0]!r}")
        verifier(times[i0] not in gust_times,
                 "τ = 0 n'est PAS annoncée dans `gustTimes`")
        verifier(len(gust_times) == len(times) - 1,
                 "`gustTimes` = toutes les échéances sauf τ = 0",
                 f"{len(gust_times)}/{len(times)}")

        # ── 3. hypot recalculé À LA MAIN sur un point au hasard ───────
        ge, meta_e = lire_champ_a_la_main(p03, ingest.GUST_SN[0])
        gn, _ = lire_champ_a_la_main(p03, ingest.GUST_SN[1])
        verifier(meta_e["stepType"] == "max",
                 "`stepType` = max — c'est bien un MAXIMUM, pas un instantané",
                 f"stepType={meta_e['stepType']} stepRange={meta_e['stepRange']}")
        verifier("-" in meta_e["stepRange"],
                 "`stepRange` est un intervalle — le max porte sur l'HEURE ÉCOULÉE",
                 f"stepRange={meta_e['stepRange']}")

        i3 = steps.index(3)
        pts = ingest.sample_indices(meta, ingest.STEP_SOL)
        random.seed()
        ecarts = []
        for _ in range(12):
            k = random.randrange(len(pts))
            idx, lat, lon = pts[k]
            pt = next(p for p in tuile["points"]
                      if abs(p["lat"] - lat) < 1e-9 and abs(p["lon"] - lon) < 1e-9)
            attendu = round(math.hypot(float(ge[idx]), float(gn[idx])) * 3.6)
            obtenu = pt["speed"][i3]
            ecarts.append((lat, lon, attendu, obtenu))
        pires = [e for e in ecarts if e[2] != e[3]]
        verifier(not pires,
                 "hypot(max_10efg, max_10nfg) × 3,6 recalculé = valeur écrite, à l'entier près",
                 f"12 points au hasard, ex. ({ecarts[0][0]}, {ecarts[0][1]}) → "
                 f"attendu {ecarts[0][2]} km/h, écrit {ecarts[0][3]} km/h"
                 + (f" | ÉCARTS : {pires}" if pires else ""))

        # La direction aussi : c'est elle que l'arbitrage A1 fait stocker.
        lat, lon = ecarts[0][0], ecarts[0][1]
        idx = next(i for i, la, lo in pts if abs(la - lat) < 1e-9 and abs(lo - lon) < 1e-9)
        pt = next(p for p in tuile["points"]
                  if abs(p["lat"] - lat) < 1e-9 and abs(p["lon"] - lon) < 1e-9)
        dir_attendu = round((270 - math.degrees(
            math.atan2(float(gn[idx]), float(ge[idx])))) % 360)
        verifier(pt["dir"][i3] == dir_attendu,
                 "direction de la rafale = convention météo (d'où vient le vent)",
                 f"attendu {dir_attendu}°, écrit {pt['dir'][i3]}°")

        # ── 4. `speedMean` : le vent moyen DU MÊME POINT ──────────────
        # C'est ce que lisent l'anneau et la flèche fantôme. Un decalage
        # d'un point ne se verrait PAS a l'ecran et serait faux partout.
        verifier(all("speedMean" in p for p in tuile["points"]),
                 "chaque point de la tuile rafale porte `speedMean`")
        desapparies = [(a["lat"], a["lon"]) for a, b in zip(tuile["points"], moy["points"])
                       if a["lat"] != b["lat"] or a["lon"] != b["lon"]
                       or a["speedMean"] is not b["speed"]]
        verifier(not desapparies,
                 "`speedMean` est le MÊME objet liste que le `speed` de la tuile sol, "
                 "au même (lat, lon)",
                 f"{len(tuile['points'])} points vérifiés"
                 + (f" | DÉSAPPARIÉS : {desapparies[:3]}" if desapparies else ""))
        verifier(all(p["speedMean"][i3] is not None and p["speed"][i3] is not None
                     and p["speedMean"][i3] <= p["speed"][i3] + 1
                     for p in tuile["points"]),
                 "la rafale est ≥ au vent moyen partout (tolérance 1 km/h d'arrondi)")

        # ── 5. La flèche fantôme s'appuie sur la direction de la RAFALE.
        # La tuile ne porte pas la direction du vent moyen (ce serait
        # +172 Mo). Est-ce défendable ? Mesuré plutôt que supposé :
        ecarts_dir = []
        for p, m in zip(tuile["points"], moy["points"]):
            a, b = p["dir"][i3], m["dir"][i3]
            if a is None or b is None:
                continue
            e = abs((a - b + 180) % 360 - 180)
            ecarts_dir.append(e)
        ecarts_dir.sort()
        med = ecarts_dir[len(ecarts_dir) // 2]
        p90 = ecarts_dir[int(len(ecarts_dir) * .9)]
        verifier(med <= 15,
                 "direction rafale ≈ direction du vent moyen — la flèche fantôme peut "
                 "porter les deux longueurs sur UN seul axe",
                 f"écart médian {med}° · p90 {p90}° (n = {len(ecarts_dir)})")

        # ── 6. Ce que le pilote lira : l'ordre de grandeur ────────────
        paires = [(m["speed"][i3], g["speed"][i3])
                  for m, g in zip(moy["points"], tuile["points"])
                  if m["speed"] and g["speed"][i3]]
        if paires:
            ratios = sorted(g / m for m, g in paires if m > 0)
            print(f"\nⓘ à τ = 3 h sur la fenêtre de test : moyen "
                  f"{sorted(m for m, _ in paires)[len(paires)//2]} km/h médian, "
                  f"rafale {sorted(g for _, g in paires)[len(paires)//2]} km/h médiane, "
                  f"ratio médian {ratios[len(ratios)//2]:.2f}")
    finally:
        for p in (p00, p03):
            try:
                os.unlink(p)
            except OSError:
                pass

    print("\n" + ("⛔ ÉCHEC : " + " | ".join(ECHEC) if ECHEC
                  else "✅ Critère d'acceptation SATISFAIT."))
    return 1 if ECHEC else 0


if __name__ == "__main__":
    sys.exit(main())
