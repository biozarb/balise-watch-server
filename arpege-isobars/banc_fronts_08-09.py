#!/usr/bin/env python3
"""Banc hors ligne — FRONTS FROID / CHAUD sur le synoptique Monde (08/09/2026).
Aucun téléversement.

    python3 banc_fronts_08-09.py --orientation [ISO]   # ⛔ §4.1 : les 4 champs 850 hPa contre l'API
    python3 banc_fronts_08-09.py --synthetique         # §3 lot 1 : zone barocline tanh, 4 orientations
    python3 banc_fronts_08-09.py [ISO] [--svg out.svg] # échéance réelle : fronts + isobares, mesures

⛔ Leçon du 08/09 (calque retourné six semaines) : CHAQUE nouvelle variable
lue est un champ retourné en puissance. `--orientation` compare
`temperature_850hPa`, `relative_humidity_850hPa`, `wind_u/v_850hPa` lus
dans le `.om` à l'API Open-Meteo (même fournisseur, même modèle, même
échéance) en des points connus, dans les DEUX sens de latitude, et
vérifie les unités (°C ? K ? m/s ? km/h ?) et le sens de u/v — un vent
tourné de 90° classerait tous les fronts à l'envers sans aucun symptôme.
"""
import sys, json, math, urllib.request
from datetime import datetime, timezone

import numpy as np
import fsspec
from omfiles import OmFileReader

import ingest as ing

FIELDS_850 = ("temperature_850hPa", "relative_humidity_850hPa",
              "wind_u_component_850hPa", "wind_v_component_850hPa")


def read_fields_https(model, dt, names, reference_time=None):
    """Même lecture que `ing.read_pressure`, en HTTPS (le couple botocore/
    aiobotocore de ce poste est incompatible avec s3fs — panne locale,
    cf. banc_monde_08-09.py ; ⚠️ ne pas recopier dans ingest.py).
    Renvoie (lon2d, lat2d, {name: array}) — sud→nord, comme ingest.py."""
    run_dt = reference_time if reference_time is not None else dt
    uri = (f"https://{ing.OM_BUCKET}.s3.amazonaws.com/data_spatial/{model}/"
           f"{run_dt.strftime('%Y/%m/%d/%H00Z')}/{dt.strftime('%Y-%m-%dT%H%M')}.om")
    backend = fsspec.open("blockcache::" + uri, mode="rb",
                          https={"block_size": 65536},
                          blockcache={"cache_storage": "/tmp/om_cache_banc"})
    out = {}
    with OmFileReader(backend) as root:
        for n in names:
            out[n] = root.get_child_by_name(n).read_array((...))
        bbox = ing._BBOX_RE.search(root.get_child_by_name("crs_wkt").read_scalar())
        south, west, north, east = (float(x) for x in bbox.groups())
    nj, ni = next(iter(out.values())).shape
    lon2d, lat2d = np.meshgrid(np.linspace(west, east, ni), np.linspace(south, north, nj))
    return lon2d, lat2d, out


API_POINTS = [(45.0, 6.0), (48.9, 2.3), (60.5, -6.5), (23.7, 9.4),
              (40.4, -3.7), (65.0, 25.0), (52.0, 13.4), (35.0, 33.0),
              (-33.9, 18.4), (-41.3, 174.8), (40.7, -74.0), (35.7, 139.7)]


def orientation(iso, dt):
    """⛔ §4.1 — les 4 champs 850 hPa contre l'API, dans les deux sens."""
    model = ing.GRIDS["arpege_world"]["model"]
    lon2d, lat2d, f = read_fields_https(model, dt, FIELDS_850 + ("pressure_msl",))
    south, north = float(lat2d.min()), float(lat2d.max())
    west, east = float(lon2d.min()), float(lon2d.max())
    nj, ni = lon2d.shape
    pas_lat, pas_lon = (north - south) / (nj - 1), (east - west) / (ni - 1)
    for n, a in f.items():
        print(f"  {n:28s} min {np.nanmin(a):9.2f}  max {np.nanmax(a):9.2f}  "
              f"dtype {a.dtype}  nan {int(np.isnan(a).sum())}")
    lat = ",".join(str(a) for a, _ in API_POINTS)
    lon = ",".join(str(o) for _, o in API_POINTS)
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
           f"&hourly=pressure_msl,temperature_850hPa,relative_humidity_850hPa,"
           f"wind_speed_850hPa,wind_direction_850hPa&models=meteofrance_arpege_world"
           f"&wind_speed_unit=ms&start_date={iso[:10]}&end_date={iso[:10]}&timezone=UTC")
    api = json.load(urllib.request.urlopen(url))
    # écarts[sens][champ] = liste des |om - api|
    ecarts = {"sud→nord": {}, "nord→sud": {}}
    for k, (la, lo) in enumerate(API_POINTS):
        h = api[k]["hourly"]
        if iso not in h["time"]:
            continue
        t = h["time"].index(iso)
        ref = {"pressure_msl": h["pressure_msl"][t],
               "temperature_850hPa": h["temperature_850hPa"][t],
               "relative_humidity_850hPa": h["relative_humidity_850hPa"][t]}
        spd, dirn = h["wind_speed_850hPa"][t], h["wind_direction_850hPa"][t]
        if None in ref.values() or spd is None or dirn is None:
            continue
        # Convention météo : la direction est celle d'OÙ vient le vent.
        # u (vers l'est) = −V·sin(dir), v (vers le nord) = −V·cos(dir).
        ref["wind_u_component_850hPa"] = -spd * math.sin(math.radians(dirn))
        ref["wind_v_component_850hPa"] = -spd * math.cos(math.radians(dirn))
        i = int(round((lo - west) / pas_lon))
        for sens, j in (("sud→nord", int(round((la - south) / pas_lat))),
                        ("nord→sud", int(round((north - la) / pas_lat)))):
            if not (0 <= j < nj and 0 <= i < ni):
                continue
            for n, r in ref.items():
                ecarts[sens].setdefault(n, []).append((float(f[n][j, i]), r))
    for sens, d in ecarts.items():
        print(f"\n  lu {sens} :")
        for n, pairs in d.items():
            e = [abs(a - b) for a, b in pairs]
            print(f"    {n:28s} écart moyen {sum(e)/len(e):7.2f} sur {len(e)} pts"
                  f"   ex. om={pairs[0][0]:8.2f} api={pairs[0][1]:8.2f}")


def synthetique():
    """§3 lot 1 — une zone barocline RECTILIGNE inclinée d'un angle α,
    τ = τ0 + A·tanh(x⊥/L) (x⊥ = distance signée au cœur de la zone, en km,
    positive côté CHAUD), vent uniforme. Attendu : UNE ligne droite, du
    côté chaud du cœur (pour tanh, le maximum de TFP est à x⊥ ≈ 0,66 L),
    froide si le vent va du froid vers le chaud, chaude dans l'autre sens,
    stationnaire à vent nul ou parallèle — et la même chose aux quatre
    orientations (les dérivées en x et en y ne doivent pas se comporter
    différemment : c'est le piège du gradient en degrés, §4.4)."""
    # θe : valeur de contrôle recalculée à la main (docstring de theta_e)
    te = float(ing.theta_e(10.0, 80.0))
    print(f"θe(10 °C, 80 %, 850 hPa) = {te:.1f} K (attendu 318,0 ± 1)  "
          f"[{'OK' if abs(te - 318.0) < 1.0 else 'ÉCHEC'}]")
    # θe croît avec T et avec RH (monotonie, sanity)
    ok = (ing.theta_e(15.0, 80.0) > te) and (ing.theta_e(10.0, 95.0) > te)
    print(f"θe monotone en T et RH : [{'OK' if ok else 'ÉCHEC'}]")

    lat1d = np.arange(20.0, 70.01, 0.25)
    lon1d = np.arange(-40.0, 40.01, 0.25)
    lon2d, lat2d = np.meshgrid(lon1d, lat1d)
    lat0, lon0 = 45.0, 0.0
    # A = 14 K sur 2 L = 300 km : un front marqué (≈ 9 K/100 km au cœur,
    # au-dessus de K1 = 5,5 — le banc teste la GÉOMÉTRIE et le SIGNE, pas
    # les seuils, calibrés sur le réel).
    L_km, A = 150.0, 14.0
    # coordonnées locales en km (x est, y nord), plan tangent en (lat0, lon0)
    xk = (lon2d - lon0) * 111.2 * np.cos(np.radians(lat2d))
    yk = (lat2d - lat0) * 111.2
    cfg = dict(ing.FRONTS, occlusions=False)
    echecs = 0
    for alpha in (0.0, 45.0, 90.0, 135.0):
        a = np.radians(alpha)
        # ligne du front dirigée selon (cos α, sin α) ; normale « chaude »
        # n = (−sin α, cos α) ; x⊥ = distance signée à la ligne
        nx, ny = -np.sin(a), np.cos(a)
        xperp = xk * nx + yk * ny
        # τ en K, avec une RH constante : on passe par T pour utiliser la
        # vraie chaîne (θe) — T tel que θe ≈ τ0 + A·tanh
        tau_target = 300.0 + A * np.tanh(xperp / L_km)
        # inversion grossière : θe ≈ T_K·1.047 + terme humide ~ 6 K à RH 50 %
        t_c = (tau_target / 1.047) - 273.15 - 6.0
        rh = np.full_like(t_c, 50.0)
        for regime, (u, v) in {"froid→chaud (+6 m/s)": (6 * nx, 6 * ny),
                               "chaud→froid (−6 m/s)": (-6 * nx, -6 * ny),
                               "parallèle (0 m/s ⊥)": (6 * np.cos(a), 6 * np.sin(a))}.items():
            F = ing.front_fields(lon2d, lat2d, t_c, rh,
                                 np.full_like(t_c, u), np.full_like(t_c, v), cfg)
            fronts = ing.front_locator(lon2d, lat2d, F, cfg)
            attendu = ("cold" if "froid→chaud" in regime
                       else "warm" if "chaud→froid" in regime else "stationary")
            kinds = [f["kind"] for f in fronts]
            # position : distance signée moyenne du tracé au cœur, en km
            pos = []
            for f in fronts:
                c = np.asarray(f["coords"])
                cx = (c[:, 0] - lon0) * 111.2 * np.cos(np.radians(c[:, 1]))
                cy = (c[:, 1] - lat0) * 111.2
                pos.append(float(np.mean(cx * nx + cy * ny)))
            # côté attendu des symboles : froid → côté chaud (+n), chaud →
            # côté froid (−n), stationnaire → côté chaud (+n). `side` est
            # relatif à l'ordre des points : on le convertit en signe le
            # long de n via la normale gauche du tracé.
            sides_ok = True
            for f in fronts:
                c = np.asarray(f["coords"])
                d = c[-1] - c[0]
                dx, dy = d[0] * np.cos(np.radians(lat0)), d[1]
                left = np.array([-dy, dx]) / max(np.hypot(dx, dy), 1e-9)
                sym = f["side"] * (left[0] * nx + left[1] * ny)   # +1 = côté chaud
                want = -1 if attendu == "warm" else 1
                if np.sign(sym) != want:
                    sides_ok = False
            un_seul = len(fronts) == 1
            bonne_pos = all(0.0 < p < 1.5 * L_km for p in pos)
            bon_type = kinds == [attendu]
            ok = un_seul and bonne_pos and bon_type and sides_ok
            echecs += 0 if ok else 1
            print(f"  α={alpha:5.1f}° {regime:22s} → {len(fronts)} front(s) {kinds} "
                  f"x⊥={[round(p) for p in pos]} km  côté {'OK' if sides_ok else 'ÉCHEC'}  "
                  f"[{'OK' if ok else 'ÉCHEC'}]")
    print(f"\nSynthétique : {'TOUT OK' if echecs == 0 else f'{echecs} ÉCHEC(S)'}")
    return echecs == 0


KIND_COLOR = {"cold": "#1d4ed8", "warm": "#dc2626", "stationary": "#7c3aed", "occluded": "#a21caf"}


def svg_fronts(path, synop, fronts, bbox=(-55.0, 30.0, 35.0, 70.0), width=1200):
    """SVG Mercator : isobares synop (gris) + fronts (couleur par type) +
    petites dents du côté `side` (pour VOIR l'orientation, pas le rendu
    final). `bbox` = (ouest, sud, est, nord)."""
    w0, s0, e0, n0 = bbox
    merc = lambda lat: math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
    sx = width / (e0 - w0)
    height = int((merc(n0) - merc(s0)) * sx * 180 / math.pi)
    sy = height / (merc(n0) - merc(s0))
    X = lambda lon: (lon - w0) * sx
    Y = lambda lat: (merc(n0) - merc(lat)) * sy
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
           f'viewBox="0 0 {width} {height}" style="background:#fff;font:12px sans-serif">']
    # graticule
    for lo in range(int(w0), int(e0) + 1, 10):
        out.append(f'<line x1="{X(lo):.0f}" y1="0" x2="{X(lo):.0f}" y2="{height}" stroke="#eee"/>')
    for la in range(int(s0), int(n0) + 1, 10):
        out.append(f'<line x1="0" y1="{Y(la):.0f}" x2="{width}" y2="{Y(la):.0f}" stroke="#eee"/>')
    for f in synop["features"]:
        pts = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in f["geometry"]["coordinates"]
                       if w0 <= x <= e0 and s0 <= y <= n0)
        if pts:
            out.append(f'<polyline points="{pts}" fill="none" stroke="#999" stroke-width="1"/>')
    for c in synop.get("centers", []):
        if w0 <= c["lon"] <= e0 and s0 <= c["lat"] <= n0:
            out.append(f'<text x="{X(c["lon"]):.0f}" y="{Y(c["lat"]):.0f}" font-size="18" '
                       f'font-weight="bold" fill="{"#1d4ed8" if c["kind"] == "H" else "#dc2626"}">'
                       f'{c["kind"]}<tspan font-size="10">{c["hpa"]:.0f}</tspan></text>')
    for fr in fronts:
        c = fr["coords"]
        pts = " ".join(f"{X(x):.1f},{Y(y):.1f}" for x, y in c)
        col = KIND_COLOR[fr["kind"]]
        out.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2.5"/>')
        # dents : tous les ~30 px, du côté `side` (+1 = gauche géographique
        # = (dy_px, −dx_px) en pixels, y vers le bas)
        acc, nxt = 0.0, 15.0
        for (x0, y0), (x1, y1) in zip(c, c[1:]):
            px0, py0, px1, py1 = X(x0), Y(y0), X(x1), Y(y1)
            dl = math.hypot(px1 - px0, py1 - py0)
            while acc + dl >= nxt and dl > 0:
                t = (nxt - acc) / dl
                mx, my = px0 + t * (px1 - px0), py0 + t * (py1 - py0)
                nx_, ny_ = (py1 - py0) / dl * fr["side"], -(px1 - px0) / dl * fr["side"]
                out.append(f'<line x1="{mx:.1f}" y1="{my:.1f}" x2="{mx + 7 * nx_:.1f}" '
                           f'y2="{my + 7 * ny_:.1f}" stroke="{col}" stroke-width="2.5"/>')
                nxt += 30.0
            acc += dl
        x, y = c[len(c) // 2]
        out.append(f'<text x="{X(x) + 4:.0f}" y="{Y(y) - 4:.0f}" fill="{col}">'
                   f'{fr["kind"][:2]} {fr["strength"]:.1f} K/100km v_n {fr["vn"]:+.0f}</text>')
    out.append("</svg>")
    with open(path, "w") as fh:
        fh.write("\n".join(out))
    return path


def png_fronts(path, synop, fronts, bbox=(-55.0, 30.0, 35.0, 70.0), title=""):
    """Même chose en PNG (matplotlib, Mercator) — qlmanage rogne les SVG
    non carrés, et c'est le PNG qu'on met côte à côte avec le Met Office."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    w0, s0, e0, n0 = bbox
    merc = lambda lat: np.degrees(np.log(np.tan(np.pi / 4 + np.radians(lat) / 2)))
    fig, ax = plt.subplots(figsize=(12, 12 * (merc(n0) - merc(s0)) / (e0 - w0)))
    for f in synop["features"]:
        c = np.asarray(f["geometry"]["coordinates"])
        ax.plot(c[:, 0], merc(c[:, 1]), color="#999", lw=0.7)
        m = c[len(c) // 2]
        if w0 < m[0] < e0 and s0 < m[1] < n0:
            ax.text(m[0], merc(m[1]), str(f["properties"]["hpa"]), fontsize=6, color="#666",
                    ha="center", va="center", bbox=dict(fc="white", ec="none", pad=0.5))
    for c in synop.get("centers", []):
        ax.text(c["lon"], merc(c["lat"]), f'{c["kind"]}\n{c["hpa"]:.0f}', fontsize=11, weight="bold",
                ha="center", va="center", color="#1d4ed8" if c["kind"] == "H" else "#dc2626")
    for fr in fronts:
        c = np.asarray(fr["coords"])
        col = KIND_COLOR[fr["kind"]]
        x, y = c[:, 0], merc(c[:, 1])
        ax.plot(x, y, color=col, lw=2.2)
        # dents côté `side` (+1 = gauche géographique) tous les 3 points
        for k in range(1, len(c) - 1, 3):
            dx, dy = x[k + 1] - x[k - 1], y[k + 1] - y[k - 1]
            nrm = math.hypot(dx, dy) or 1e-9
            nx_, ny_ = -dy / nrm * fr["side"], dx / nrm * fr["side"]
            ax.plot([x[k], x[k] + 0.7 * nx_], [y[k], y[k] + 0.7 * ny_], color=col, lw=2.2)
        ax.text(x[len(x) // 2], y[len(y) // 2], f'{fr["kind"][:2]} {fr["strength"]:.0f} vn{fr["vn"]:+.0f}',
                fontsize=7, color=col)
    ax.set_xlim(w0, e0); ax.set_ylim(merc(s0), merc(n0))
    ax.set_yticks([merc(v) for v in range(int(s0), int(n0) + 1, 10)])
    ax.set_yticklabels([str(v) for v in range(int(s0), int(n0) + 1, 10)])
    ax.set_xticks(range(int(w0), int(e0) + 1, 10)); ax.grid(color="#eee")
    ax.set_title(title, fontsize=9)
    fig.tight_layout(); fig.savefig(path, dpi=100); plt.close(fig)
    return path


def reel(iso, dt, svg_path=None, cfg=None):
    """Échéance réelle : isobares synop + fronts, mesures, SVG."""
    cfg = cfg or ing.FRONTS
    key, gcfg = "arpege_world", ing.GRIDS["arpege_world"]
    lon2d, lat2d, f = read_fields_https(gcfg["model"], dt, FIELDS_850 + ("pressure_msl",))
    t, rh, u, v = (ing.clip_latitude(lon2d, lat2d, f[n], gcfg["lat_clip_deg"])[2] for n in FIELDS_850)
    lon2d, lat2d, p = ing.clip_latitude(lon2d, lat2d, f["pressure_msl"], gcfg["lat_clip_deg"])
    smooth = ing.smooth_pressure(p, gcfg["smooth_sigma_cells"])
    centers = ing.find_centers(lon2d, lat2d, smooth, max_per_kind=gcfg["max_centers_per_kind"])
    synop = ing.synop_geojson(lon2d, lat2d, smooth, gcfg["synop_tol_deg"], gcfg["synop_min_length_deg"])
    synop["centers"] = centers
    import time
    t0 = time.time()
    F = ing.front_fields(lon2d, lat2d, t, rh, u, v, cfg)
    fronts = ing.front_locator(lon2d, lat2d, F, cfg, gcfg["synop_tol_deg"])
    occl = ing.occlusion_locator(lon2d, lat2d, F, centers, fronts, cfg, gcfg["synop_tol_deg"])
    dt_s = time.time() - t0
    allf = fronts + occl
    # distributions des champs de masque (pour caler K1/K2)
    band = np.abs(lat2d[:, 0]) <= cfg["lat_max"]
    g = F["g"][band] * 1e5
    tfp = F["tfp"][band] * 1e10
    print(f"  |∇θe| (K/100 km) percentiles 50/90/99 : "
          f"{np.percentile(g, 50):.2f} / {np.percentile(g, 90):.2f} / {np.percentile(g, 99):.2f}")
    print(f"  TFP (K/(100 km)²) percentiles 90/99 : "
          f"{np.percentile(tfp, 90):.2f} / {np.percentile(tfp, 99):.2f}")
    par_type = {}
    for fr in allf:
        k = fr["kind"]
        par_type.setdefault(k, [0, 0.0])
        par_type[k][0] += 1
        par_type[k][1] += ing._length_km(np.asarray(fr["coords"]))
    ser = ing.fronts_features(lon2d, lat2d, t, rh, u, v, centers, cfg, gcfg["synop_tol_deg"])
    poids = len(json.dumps(ser, separators=(",", ":")).encode())
    print(f"  fronts : {len(allf)} au total en {dt_s:.1f} s, {poids/1024:.1f} Ko — "
          + ", ".join(f"{k} {n} ({L:.0f} km)" for k, (n, L) in sorted(par_type.items())))
    # zone Atlantique/Europe (la fenêtre Met Office)
    eu = [fr for fr in allf if any(-40 <= x <= 30 and 35 <= y <= 70 for x, y in fr["coords"])]
    print(f"  dans la fenêtre Met Office (−40→30, 35→70) : {len(eu)} front(s) : "
          + ", ".join(f"{fr['kind']} {ing._length_km(np.asarray(fr['coords'])):.0f} km "
                      f"@({fr['coords'][len(fr['coords'])//2][0]:.0f},{fr['coords'][len(fr['coords'])//2][1]:.0f}) "
                      f"v_n {fr['vn']:+.0f}" for fr in eu))
    if "--dump" in sys.argv:
        # le `.synop.json` tel que l'ingestion l'écrirait (fronts compris),
        # pour le banc web `banc_isobars_fronts.mts`
        dump = sys.argv[sys.argv.index("--dump") + 1]
        synop["fronts"] = ser
        with open(dump, "w") as fh:
            json.dump(synop, fh, separators=(",", ":"))
        print(f"  dump : {dump} ({len(json.dumps(synop, separators=(',', ':')).encode())/1024:.0f} Ko)")
    if svg_path:
        if "--monde" in sys.argv:
            png_fronts(svg_path, synop, allf, bbox=(-180.0, -70.0, 180.0, 70.0), title=f"{iso} — monde")
        elif svg_path.endswith(".png"):
            png_fronts(svg_path, synop, allf, title=f"{iso} — {len(allf)} fronts — "
                       + ", ".join(f"{k}={v}" for k, v in cfg.items() if v != ing.FRONTS[k]))
        else:
            svg_fronts(svg_path, synop, allf)
        print(f"  image : {svg_path}")
    return allf, synop


def main():
    if "--synthetique" in sys.argv:
        sys.exit(0 if synthetique() else 1)
    meta = ing.latest_json(ing.GRIDS["arpege_world"]["model"])
    ref = datetime.strptime(meta["reference_time"],
                            "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    iso = args[0] if args else ref.strftime("%Y-%m-%dT%H:%M")
    dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
    print(f"Run de référence {ref.isoformat()} — échéance {iso}\n")
    if "--orientation" in sys.argv:
        orientation(iso, dt)
        return
    svg = None
    if "--svg" in sys.argv:
        svg = sys.argv[sys.argv.index("--svg") + 1]
    # --set cle=valeur[,cle=valeur…] : surcharge de FRONTS pour le balayage
    cfg = dict(ing.FRONTS)
    if "--set" in sys.argv:
        for kv in sys.argv[sys.argv.index("--set") + 1].split(","):
            k, v = kv.split("=")
            cfg[k] = (v.lower() == "true") if v.lower() in ("true", "false") else float(v)
        print("  réglages :", {k: v for k, v in cfg.items() if v != ing.FRONTS[k]})
    reel(iso, dt, svg, cfg)


if __name__ == "__main__":
    main()
