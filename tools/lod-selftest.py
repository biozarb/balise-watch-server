#!/usr/bin/env python3
"""Critère d'acceptation de la PYRAMIDE DE NIVEAUX `arome/lod/` (08/09/2026).

⚠️ CE TEST NE DÉPEND PAS DE L'ŒIL. Sur le modèle de
`rafale-tuile-selftest.py` : il rejoue le VRAI code d'ingestion
(`arome-wind/ingest.py`, importé tel quel — `publier_lod`,
`publier_lod_elev`, avec un STORE factice qui capture les octets), sur un
VRAI run, puis RECALCULE À LA MAIN depuis le GRIB relu indépendamment,
avec un DÉCODEUR binaire écrit ici (pas celui d'ingest) :

  ✅ speed = ‖Σu/n, Σv/n‖ × 3,6 à l'entier près, 12 blocs au hasard par niveau
  ✅ dir2  = atan2 du vecteur moyen, convention météo, en pas de 2°
  ✅ max   = max(hypot(u, v)) × 3,6 du bloc, à l'entier près
  ✅ max ≥ speed partout (tolérance 1 km/h d'arrondi)
  ✅ orientation : le bloc (0,0) du niveau 0,2° couvre bien le coin
     SUD-OUEST de la BBOX (et diffère du coin nord-est, sinon le test ne
     prouverait rien)
  ✅ times[] de l'index = times[] des tuiles, même run
  ✅ rafale à τ = 0 : PAS de fichier, PAS d'échéance listée — jamais 0
  ✅ alt au niveau natif (bloc 1) : max = speed, et `elev` = `elev_at`
     point par point ; au bloc 4, `elev` = moyenne arrondie du bloc
  ✅ en-têtes : run, géométrie, `Content-Encoding: gzip`, CACHE_REECRIT

⭐ Et UNE MESURE qui servira au client (§3.4 du prompt de reprise) : sur
la BBOX entière à l'échéance 03H, la distribution de `max − speed` au
niveau 0,2°, globalement et sur les Alpes du Nord (tuile 44_6). Yann a
choisi le max pour la couleur de fond ; si la carte des Alpes doit
devenir uniformément rouge en dézoom, c'est ce chiffre qui le dit avant
l'écran — à lui montrer, pas à corriger en douce.

Coût : SP1 001 00H + 03H (~23 Mo pièce), SP1 0025 00H06H (~56 Mo, pour la
géométrie de la grille ALT — l'IP1 réel fait ~500 Mo, on teste le CHEMIN
DE CODE alt sur 10u/10v de la même grille, pas la donnée IP1), SP3 001
00H (~7 Mo, orographie). Supprimés au fil de l'eau.

Usage :  python3 tools/lod-selftest.py
"""
import os, sys, math, json, gzip, struct, random
from datetime import datetime, timezone, timedelta
import numpy as np

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ICI, os.pardir, "arome-wind"))
sys.path.insert(0, ICI)

import ingest                                              # noqa: E402
from storage import CACHE_REECRIT                          # noqa: E402
from mf_s3 import s3_keys, download_tmp                    # noqa: E402
from eccodes import (codes_grib_new_from_file, codes_get,  # noqa: E402
                     codes_get_values, codes_release)

# Fenêtre de test : 0,4° × 0,4° autour du Vercors — 41 × 41 points à
# 0,01° → 8 × 8 blocs au 0,05°, 2 × 2 au 0,2° (donc un coin sud-ouest ET
# un coin nord-est à distinguer). Sur la grille 0025 décimée à 0,05° :
# 9 × 9 → 2 × 2 au 0,2°, avec troncature d'une ligne et d'une colonne.
BBOX_TEST = dict(latmin=44.8, latmax=45.2, lonmin=5.4, lonmax=5.8)
BBOX_PROD = dict(ingest.BBOX)

ECHEC = []


def verifier(ok, libelle, detail=""):
    print(("  ✅ " if ok else "  ⛔ ") + libelle + (f"  — {detail}" if detail else ""))
    if not ok:
        ECHEC.append(libelle)


class StoreFactice:
    """Capture ce que `sb_upload` écrirait : (octets, en-têtes HTTP)."""
    def __init__(self):
        self.objets = {}

    def put(self, path, body, *, cache_control, content_type="application/json",
            content_encoding=None):
        self.objets[path] = dict(body=body, cache_control=cache_control,
                                 content_type=content_type,
                                 content_encoding=content_encoding)
        return 200


def decoder(octets):
    """Décodeur INDÉPENDANT de `lod_encoder` — c'est ce que le client (lot
    2) devra écrire : gunzip · magic · uint32 LE · JSON · plans."""
    brut = gzip.decompress(octets)
    assert brut[:4] == b"BWL1", f"magic {brut[:4]!r}"
    n = struct.unpack("<I", brut[4:8])[0]
    h = json.loads(brut[8:8 + n].decode("utf-8"))
    corps = brut[8 + n:]
    R, C = h["rows"], h["cols"]
    dt = {"uint8": np.uint8, "int16": "<i2"}[h["dtype"]]
    taille = R * C * np.dtype(dt).itemsize
    nt = len(h["times"]) if h.get("layout") == "allTimes" else 1
    plans = {}
    off = 0
    for t in range(nt):
        for nom in h["planes"]:
            a = np.frombuffer(corps[off:off + taille], dtype=dt).reshape(R, C)
            plans.setdefault(nom, []).append(a)
            off += taille
    assert off == len(corps), f"{len(corps) - off} octets en trop"
    return h, {k: (v[0] if nt == 1 else v) for k, v in plans.items()}


def trouver_run():
    base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    base -= timedelta(hours=base.hour % 3)
    for back in range(5):
        run = base - timedelta(hours=3 * back)
        ref = run.strftime("%Y-%m-%dT%H:00:00Z")
        k001 = list(s3_keys(f"pnt/{ref}/arome/001/SP1/"))
        k00 = [k for k in k001 if "__00H__" in k]
        k03 = [k for k in k001 if "__03H__" in k]
        k0025 = [k for k in s3_keys(f"pnt/{ref}/arome/0025/SP1/") if "__00H06H__" in k]
        if k00 and k03 and k0025:
            return ref, run, sorted(k00)[0], sorted(k03)[0], sorted(k0025)[0]
    raise SystemExit("Aucun run AROME avec SP1 001 00H/03H et SP1 0025 00H06H publiés.")


def lire_champ_a_la_main(path, shortname, step=None):
    """Relecture INDÉPENDANTE du GRIB — sans `ingest.parse_grib`."""
    with open(path, "rb") as f:
        while True:
            gid = codes_grib_new_from_file(f)
            if gid is None:
                return None, None
            try:
                if (codes_get(gid, "shortName") == shortname
                        and (step is None or codes_get(gid, "step") == step)):
                    meta = dict(Ni=codes_get(gid, "Ni"), Nj=codes_get(gid, "Nj"),
                                lat0=codes_get(gid, "latitudeOfFirstGridPointInDegrees"),
                                lon0=ingest._norm_lon(
                                    codes_get(gid, "longitudeOfFirstGridPointInDegrees")),
                                di=codes_get(gid, "iDirectionIncrementInDegrees"),
                                dj=codes_get(gid, "jDirectionIncrementInDegrees"),
                                jScan=codes_get(gid, "jScansPositively"))
                    vals = codes_get_values(gid)
                    codes_release(gid)
                    return vals, meta
            except Exception:
                pass
            codes_release(gid)


def bloc_a_la_main(vals_u, vals_v, m, lat_min, lat_max, lon_min, lon_max, pas=None):
    """Moyenne u/v et max de vitesse des points natifs dont le centre est
    dans [lat_min, lat_max[ × [lon_min, lon_max[ — calcul par (lat, lon)
    RECONSTRUITS depuis la meta du GRIB, sans aucun indice d'ingest.
    `pas` : ne garder que les nœuds multiples de `pas` (la grille ALT est
    décimée à 0,05° sur du 0,025° — les tuiles ET la pyramide ne voient
    qu'un point sur deux, le recalcul doit faire pareil)."""
    su = sv = ss = 0.0
    n = 0
    mx = -1.0
    sur_pas = lambda x: pas is None or abs(x / pas - round(x / pas)) < 1e-6   # noqa: E731
    for j in range(m["Nj"]):
        lat = m["lat0"] + (m["dj"] * j if m["jScan"] == 1 else -m["dj"] * j)
        if not (lat_min - 1e-6 <= lat < lat_max - 1e-6) or not sur_pas(lat):
            continue
        for i in range(m["Ni"]):
            lon = m["lon0"] + m["di"] * i
            if not (lon_min - 1e-6 <= lon < lon_max - 1e-6) or not sur_pas(lon):
                continue
            u, v = float(vals_u[j * m["Ni"] + i]), float(vals_v[j * m["Ni"] + i])
            su += u; sv += v; n += 1
            sp = math.hypot(u, v)
            ss += sp
            mx = max(mx, sp)
    if n == 0:
        return None
    um, vm = su / n, sv / n
    return dict(n=n, speed=round(math.hypot(um, vm) * 3.6),
                dir2=round(((270 - math.degrees(math.atan2(vm, um))) % 360) / 2) % 180,
                max=round(mx * 3.6),
                mean=round(ss / n * 3.6))        # moyenne SCALAIRE (plan `mean`, 09/09)


def bornes_bloc(h, r, c):
    """Emprise [lat_min, lat_max[ × [lon_min, lon_max[ du bloc (r, c) d'après
    l'EN-TÊTE : `lat0`/`lon0` sont des centres de cellule."""
    f, s = h["block"], h["nativeStep"]
    lat_min = h["lat0"] - s * (f - 1) / 2 + r * h["dLat"]
    lon_min = h["lon0"] - s * (f - 1) / 2 + c * h["dLon"]
    return lat_min, lat_min + f * s, lon_min, lon_min + f * s


def controler_niveau(libelle, h, plans, vals_u, vals_v, m, i_t=None, n_blocs=12):
    """12 blocs au hasard : speed / dir2 / max recalculés à la main."""
    R, C = h["rows"], h["cols"]
    pick = lambda nom: (plans[nom][i_t] if i_t is not None else plans[nom])   # noqa: E731
    S, D, M, SM = pick("speed"), pick("dir2"), pick("max"), pick("mean")
    random.seed()
    ecarts = dict(speed=[], dir2=[], max=[], mean=[])
    exemples = []
    for _ in range(n_blocs):
        r, c = random.randrange(R), random.randrange(C)
        att = bloc_a_la_main(vals_u, vals_v, m, *bornes_bloc(h, r, c), pas=h["nativeStep"])
        if att is None:
            ECHEC.append(f"{libelle} : bloc ({r},{c}) sans point natif")
            continue
        if att["n"] != h["block"] ** 2:
            ECHEC.append(f"{libelle} : bloc ({r},{c}) compte {att['n']} points, attendu {h['block']**2}")
        ecarts["speed"].append(abs(int(S[r, c]) - att["speed"]))
        ecarts["dir2"].append(min((int(D[r, c]) - att["dir2"]) % 180, (att["dir2"] - int(D[r, c])) % 180))
        ecarts["max"].append(abs(int(M[r, c]) - att["max"]))
        ecarts["mean"].append(abs(int(SM[r, c]) - att["mean"]))
        if len(exemples) < 2:
            exemples.append(f"({r},{c}) speed {int(S[r,c])}/{att['speed']} dir2 {int(D[r,c])}/{att['dir2']} "
                            f"max {int(M[r,c])}/{att['max']}")
    # « à l'entier près » : 0 attendu ; 1 toléré pour un demi exact (arrondi
    # au pair côté numpy contre round() côté Python sur des flottants qui
    # diffèrent au dernier bit) — et la médiane doit être 0.
    for nom, tol in (("speed", 1), ("dir2", 1), ("max", 1), ("mean", 1)):
        e = ecarts[nom]
        verifier(e and max(e) <= tol and sorted(e)[len(e) // 2] == 0,
                 f"{libelle} : `{nom}` recalculé à la main = valeur écrite ({len(e)} blocs, "
                 f"écart max {max(e) if e else '?'})",
                 "écrit/attendu : " + " · ".join(exemples))
    verifier(bool(np.all((M.astype(int) - S.astype(int)) >= -1)),
             f"{libelle} : max ≥ speed partout (tolérance 1 km/h)",
             f"min(max − speed) = {int((M.astype(int) - S.astype(int)).min())}")
    # Inégalité triangulaire : ‖vecteur moyen‖ ≤ moyenne des normes ≤ max.
    verifier(bool(np.all((SM.astype(int) - S.astype(int)) >= -1)) and bool(np.all((M.astype(int) - SM.astype(int)) >= -1)),
             f"{libelle} : speed ≤ mean ≤ max partout (tolérance 1 km/h)",
             f"min(mean − speed) = {int((SM.astype(int) - S.astype(int)).min())}, "
             f"min(max − mean) = {int((M.astype(int) - SM.astype(int)).min())}")
    verifier(bool(np.all(D < 180)), f"{libelle} : dir2 ∈ [0, 179]")


def main():
    ref, run, k00, k03, k0025 = trouver_run()
    print(f"Run AROME : {ref}")
    ingest._RUN_HOUR_UTC = run.hour
    ingest.BBOX = dict(BBOX_TEST)
    store = StoreFactice()
    ingest.STORE = store

    p00, p03, p25 = download_tmp(k00), download_tmp(k03), download_tmp(k0025)
    try:
        # ── 1. Le vrai chemin : SOL + RAFALE sur 00H + 03H (grille 001) ──
        sol_want = lambda sn, tol, lvl: (sn if (tol == "heightAboveGround"      # noqa: E731
                                                and (sn in ("10u", "10v")
                                                     or sn in ingest.GUST_SN)) else None)
        brut, meta = {}, None
        for p in (p00, p03):
            part, mm = ingest.parse_grib(p, sol_want, "float32")
            meta = meta or mm
            for k, byhstep in part.items():
                brut.setdefault(k, {}).update(byhstep)
        data = {("u" if k == "10u" else "v"): v for k, v in brut.items() if k in ("10u", "10v")}
        gust = {("e" if k == ingest.GUST_SN[0] else "n"): v
                for k, v in brut.items() if k in ingest.GUST_SN}
        steps = sorted(set(data["u"]) & set(data["v"]))
        times = [(run + timedelta(hours=s)).strftime("%Y-%m-%dT%H:%M") for s in steps]
        uv = {s: (data["u"][s], data["v"][s]) for s in steps}
        gust_steps = [s for s in steps if s in gust.get("e", {}) and s in gust.get("n", {})]
        uvg = {s: (gust["e"][s], gust["n"][s]) for s in gust_steps}
        print(f"  échéances vent moyen {steps}, rafale {gust_steps}")

        index = dict(run=ref, entries=[], elev=[])
        n_sol = ingest.publier_lod(uv, meta, steps, times, "sol", None, ingest.STEP_SOL, ref, index, "sol")
        n_raf = ingest.publier_lod(uvg, meta, steps, times, "rafale", None, ingest.STEP_SOL, ref, index, "rafale")
        print(f"  publier_lod : sol {n_sol} objets, rafale {n_raf} objets → {sorted(store.objets)}")

        # ── 2. En-têtes HTTP et binaires ──────────────────────────────
        bins = {k: v for k, v in store.objets.items() if k.endswith(".bin")}
        verifier(all(o["content_encoding"] == "gzip" and o["content_type"] == "application/octet-stream"
                     and o["cache_control"] == CACHE_REECRIT for o in bins.values()),
                 "chaque .bin part en `application/octet-stream`, `Content-Encoding: gzip`, CACHE_REECRIT")
        decodes = {k: decoder(o["body"]) for k, o in bins.items()}
        verifier(all(h["run"] == ref for h, _ in decodes.values()),
                 "chaque .bin porte le `run` dans son en-tête", f"{len(decodes)} objets")

        e_sol05 = next(e for e in index["entries"] if e["kind"] == "sol" and e["lod"] == 0.05)
        e_sol20 = next(e for e in index["entries"] if e["kind"] == "sol" and e["lod"] == 0.2)
        e_raf05 = next(e for e in index["entries"] if e["kind"] == "rafale" and e["lod"] == 0.05)
        verifier((e_sol05["rows"], e_sol05["cols"]) == (8, 8) and (e_sol20["rows"], e_sol20["cols"]) == (2, 2),
                 "géométrie sol : 41×41 natifs → 8×8 au 0,05° (1 tronqué), 2×2 au 0,2°",
                 f"0,05° {e_sol05['rows']}×{e_sol05['cols']} tronqué {e_sol05['truncated']} · "
                 f"0,2° {e_sol20['rows']}×{e_sol20['cols']} tronqué {e_sol20['truncated']}")
        verifier(abs(e_sol20["lat0"] - (44.8 + 0.095)) < 1e-6 and abs(e_sol20["lon0"] - (5.4 + 0.095)) < 1e-6,
                 "centre de la cellule (0,0) au 0,2° = coin sud-ouest + 0,095°",
                 f"lat0 {e_sol20['lat0']} lon0 {e_sol20['lon0']}")

        # ── 3. times[] et τ = 0 de la rafale ──────────────────────────
        verifier(e_sol05["times"] == times and e_sol20["times"] == times,
                 "times[] des entrées sol = times[] des tuiles, même run")
        verifier(e_raf05["times"] == [times[i] for i, s in enumerate(steps) if s in gust_steps]
                 and times[steps.index(0)] not in e_raf05["times"],
                 "rafale : τ = 0 n'est PAS listée dans l'index", f"times rafale {e_raf05['times']}")
        verifier("arome/lod/0.05/rafale/t00.bin" not in bins and "arome/lod/0.05/sol/t00.bin" in bins,
                 "rafale : PAS de fichier t00 (sol en a un) — ni 0, ni sentinelle, absent")
        verifier(len(e_raf05["paths"]) == len(e_raf05["times"]),
                 "rafale : un chemin par échéance listée")
        h_raf, pl_raf = decodes[e_raf05["paths"][0]]
        verifier(h_raf["time"] == e_raf05["times"][0] and h_raf["kind"] == "rafale",
                 "l'en-tête du premier .bin rafale porte la bonne échéance", h_raf["time"])

        # ── 4. Recalcul à la main depuis le GRIB relu indépendamment ──
        i3 = steps.index(3)
        vu, m_u = lire_champ_a_la_main(p03, "10u")
        vv, _ = lire_champ_a_la_main(p03, "10v")
        h05, pl05 = decodes[e_sol05["paths"][i3]]
        controler_niveau("sol 0,05° (bloc 5)", h05, pl05, vu, vv, m_u)
        h20, pl20 = decodes[e_sol20["path"]]
        verifier(h20["layout"] == "allTimes" and h20["times"] == times
                 and len(pl20["speed"]) == len(times),
                 "0,2° : toutes les échéances dans UN fichier, dans l'ordre de `times`")
        controler_niveau("sol 0,2° (bloc 20)", h20, pl20, vu, vv, m_u, i_t=i3, n_blocs=4)
        ge, _ = lire_champ_a_la_main(p03, ingest.GUST_SN[0])
        gn, _ = lire_champ_a_la_main(p03, ingest.GUST_SN[1])
        controler_niveau("rafale 0,05° (bloc 5)", *decodes[e_raf05["paths"][e_raf05["times"].index(times[i3])]],
                         ge, gn, m_u)

        # ── 5. Orientation : (0,0) = SUD-OUEST, et ≠ nord-est ─────────
        so = bloc_a_la_main(vu, vv, m_u, 44.8, 45.0, 5.4, 5.6)
        ne = bloc_a_la_main(vu, vv, m_u, 45.0, 45.2, 5.6, 5.8)
        S20 = pl20["speed"][i3]
        verifier(int(S20[0, 0]) == so["speed"] and int(S20[1, 1]) == ne["speed"],
                 "orientation : bloc (0,0) du 0,2° = coin SUD-OUEST (44,8-45,0 N / 5,4-5,6 E), "
                 "bloc (1,1) = nord-est",
                 f"écrit (0,0)={int(S20[0,0])} (1,1)={int(S20[1,1])} · à la main SO={so['speed']} NE={ne['speed']}")
        verifier(so["speed"] != ne["speed"] or so["dir2"] != ne["dir2"],
                 "…et les deux coins DIFFÈRENT (sinon le contrôle d'orientation ne prouverait rien)",
                 f"SO {so['speed']} km/h {so['dir2']*2}° · NE {ne['speed']} km/h {ne['dir2']*2}°")
        del uv, uvg, data, gust, brut

        # ── 6. Chemin ALT (grille 0025, bloc 1 et 4) + orographie ─────
        # ⓘ Sur 10u/10v de SP1 0025, PAS sur l'IP1 (500 Mo) : on vérifie le
        # CHEMIN DE CODE alt (décimation 2, bloc 1 = natif, bloc 4), pas la
        # donnée d'altitude elle-même.
        want25 = lambda sn, tol, lvl: (sn if (tol == "heightAboveGround" and sn in ("10u", "10v")) else None)  # noqa: E731
        part25, meta25 = ingest.parse_grib(p25, want25)
        steps25 = sorted(set(part25["10u"]) & set(part25["10v"]))
        times25 = [(run + timedelta(hours=s)).strftime("%Y-%m-%dT%H:%M") for s in steps25]
        uv25 = {s: (part25["10u"][s], part25["10v"][s]) for s in steps25}
        store.objets.clear()
        n_alt = ingest.publier_lod(uv25, meta25, steps25, times25, "alt", 850, ingest.STEP_ALT, ref, index, "alt/850")
        e_a05 = next(e for e in index["entries"] if e["kind"] == "alt" and e["lod"] == 0.05)
        e_a20 = next(e for e in index["entries"] if e["kind"] == "alt" and e["lod"] == 0.2)
        verifier(n_alt == len(steps25) + 1 and e_a05["block"] == 1 and e_a20["block"] == 4,
                 "alt : bloc 1 au 0,05° (= natif décimé), bloc 4 au 0,2°",
                 f"{n_alt} objets, géométrie 0,05° {e_a05['rows']}×{e_a05['cols']} · "
                 f"0,2° {e_a20['rows']}×{e_a20['cols']} tronqué {e_a20['truncated']}")
        ha, pa = decoder(store.objets[e_a05["paths"][0]]["body"])
        verifier(bool(np.array_equal(pa["speed"], pa["max"])) and bool(np.array_equal(pa["speed"], pa["mean"])),
                 "alt 0,05° (bloc 1) : max = mean = speed partout — rien n'est moyenné au niveau natif")
        s25 = steps25[-1]
        vu25, m25 = lire_champ_a_la_main(p25, "10u", step=s25)
        vv25, _ = lire_champ_a_la_main(p25, "10v", step=s25)
        ha20, pa20 = decoder(store.objets[e_a20["path"]]["body"])
        controler_niveau("alt 0,2° (bloc 4 sur 0,05°)", ha20, pa20, vu25, vv25, m25,
                         i_t=steps25.index(s25), n_blocs=4)
        # Orographie : `elev` du 0,05° = `elev_at` point par point.
        orog = ingest.load_orography(ref)
        if orog is None:
            verifier(False, "orographie SP3 chargée")
        else:
            store.objets.clear()
            ingest.publier_lod_elev(orog, meta25, ingest.STEP_ALT, index)
            he, pe = decoder(store.objets["arome/lod/elev/0.05.bin"]["body"])
            E = pe["elev"]
            pts = ingest.sample_indices(meta25, ingest.STEP_ALT)
            attendu = {(lat, lon): ingest.elev_at(orog, lat, lon) for _, lat, lon in pts}
            f, s = he["block"], he["nativeStep"]
            desacc = []
            for r in range(he["rows"]):
                for c in range(he["cols"]):
                    lat, lon = round(he["lat0"] + r * he["dLat"], 3), round(he["lon0"] + c * he["dLon"], 3)
                    if attendu.get((lat, lon)) != int(E[r, c]):
                        desacc.append((lat, lon, attendu.get((lat, lon)), int(E[r, c])))
            verifier(not desacc, "elev 0,05° = `elev_at` des tuiles alt, point par point",
                     f"{he['rows']*he['cols']} points, ex. {int(E[0,0])} m en ({he['lat0']}, {he['lon0']})"
                     + (f" | DÉSACCORDS {desacc[:3]}" if desacc else ""))
            he20, pe20 = decoder(store.objets["arome/lod/elev/0.2.bin"]["body"])
            R, C = he20["rows"], he20["cols"]
            moy = E[:R * 4, :C * 4].reshape(R, 4, C, 4).astype(float).mean(axis=(1, 3))
            verifier(bool(np.all(np.abs(pe20["elev"].astype(float) - np.rint(moy)) <= 1)),
                     "elev 0,2° = moyenne arrondie du bloc 4×4 du 0,05°",
                     f"ex. {int(pe20['elev'][0,0])} m contre {moy[0,0]:.0f}")
    finally:
        for p in (p00, p03, p25):
            try:
                os.unlink(p)
            except OSError:
                pass

    # ── 7. ⭐ La mesure pour Yann : max − speed sur la BBOX entière ────
    print("\nⓘ Mesure `max − speed` (BBOX de production, échéance 03H) :")
    ingest.BBOX = dict(BBOX_PROD)
    p03 = download_tmp(k03)
    try:
        part, meta = ingest.parse_grib(p03, lambda sn, tol, l: sn if (tol == "heightAboveGround" and sn in ("10u", "10v")) else None, "float32")
        U, V = part["10u"][3], part["10v"][3]
        fen = ingest.fenetre_bbox(meta, ingest.STEP_SOL)
        heure = (run + timedelta(hours=3)).strftime("%d/%m %H:%M UTC")
        paliers = np.array([8, 16, 24, 32, 40])
        for lod in ingest.LOD_LEVELS:
            f = round(lod / 0.01)
            geo = ingest.lod_geometrie(meta, fen, f)
            S, D, M, SM = ingest.lod_bloc(U, V, meta, fen, f)
            S, M = S.astype(int), M.astype(int)
            lat = geo["lat0"] + np.arange(geo["rows"]) * geo["dLat"]
            lon = geo["lon0"] + np.arange(geo["cols"]) * geo["dLon"]
            zones = {"BBOX entière": np.ones(S.shape, bool),
                     "Alpes du Nord (tuile 44_6 : 44-46 N / 6-8 E)":
                         (lat[:, None] >= 44) & (lat[:, None] < 46) & (lon[None, :] >= 6) & (lon[None, :] < 8)}
            for nom, z in zones.items():
                d = (M - S)[z]
                bS, bM = np.searchsorted(paliers, S[z], "right"), np.searchsorted(paliers, M[z], "right")
                print(f"  {lod:g}° · {nom} · {heure} · n={d.size} : max−speed médiane {np.median(d):.0f} "
                      f"p90 {np.percentile(d, 90):.0f} max {d.max()} km/h ; le max change de PALIER de "
                      f"couleur (8/16/24/32/40) sur {100*np.mean(bM > bS):.0f} % des cellules ; "
                      f"max ≥ 40 km/h : {100*np.mean(M[z] >= 40):.0f} % (speed ≥ 40 : {100*np.mean(S[z] >= 40):.0f} %)")
    finally:
        os.unlink(p03)

    print("\n" + ("⛔ ÉCHEC : " + " | ".join(ECHEC) if ECHEC
                  else "✅ Critère d'acceptation SATISFAIT."))
    return 1 if ECHEC else 0


if __name__ == "__main__":
    sys.exit(main())
