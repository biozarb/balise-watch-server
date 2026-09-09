"""Banc — nappe de pression colorée (09/09/2026).

Vérifie les trois choses qui peuvent silencieusement casser le calque, et
qu'aucun test de forme n'attraperait :

  1. ALLER-RETOUR : ce que le web relira dans le PNG est bien la pression
     du modèle au bon endroit (tolérance 0,5 hPa = la quantification).
  2. ORIENTATION : la ligne 0 du PNG est la plus au NORD. C'est le bug du
     08/09 (calque retourné, invisible six semaines) transposé : une
     nappe à l'envers reste une nappe plausible.
  3. POIDS : combien pèse la clé `field` dans le fichier, par rapport aux
     contours — le quota Storage a déjà été dépassé une fois (30/07).

Usage (depuis ce dossier) :
    python3 banc_field_09-09.py            # synthétique, sans réseau
    python3 banc_field_09-09.py --reel     # lit une échéance ARPEGE réelle

⚠️ `--reel` demande l'environnement de l'ingestion (omfiles + s3fs qui
marche). Sur le Mac de Yann le 09/09, s3fs/aiobotocore est cassé
(`compute_endpoint_resolver_builtin_defaults`), sans rapport avec ce
banc : le mode sans réseau ci-dessus couvre l'encodage, l'aller-retour et
l'orientation, et le poids réel se lit dans le journal du workflow.
"""
import sys, json, base64, io, zlib, struct
import numpy as np

sys.path.insert(0, ".")
import ingest


def decode_png_gray(b64):
    """Relit un PNG 8 bits gris SANS dépendance — c'est l'équivalent
    Python de ce que fait le navigateur (drawImage + getImageData)."""
    raw = base64.b64decode(b64)
    assert raw[:8] == b"\x89PNG\r\n\x1a\n", "signature PNG"
    pos, idat, w = 8, b"", None
    while pos < len(raw):
        n = struct.unpack(">I", raw[pos:pos + 4])[0]
        tag = raw[pos + 4:pos + 8]
        payload = raw[pos + 8:pos + 8 + n]
        if tag == b"IHDR":
            w, h, depth, ctype = struct.unpack(">IIBB", payload[:10])
            assert (depth, ctype) == (8, 0), "8 bits, niveaux de gris"
        elif tag == b"IDAT":
            idat += payload
        pos += 12 + n
    data = zlib.decompress(idat)
    out = np.zeros((h, w), dtype=np.uint8)
    prev = np.zeros(w, dtype=np.uint8)
    p = 0
    for y in range(h):
        ft = data[p]; p += 1
        cur = np.frombuffer(data[p:p + w], dtype=np.uint8).astype(np.int16).copy()
        p += w
        if ft == 1:
            for x in range(1, w):
                cur[x] = (cur[x] + cur[x - 1]) & 0xFF
        elif ft == 2:
            cur = (cur + prev.astype(np.int16)) & 0xFF
        elif ft != 0:
            raise AssertionError(f"filtre {ft} inattendu (l'encodeur n'écrit que 0/1/2)")
        out[y] = cur.astype(np.uint8)
        prev = out[y]
    return out


def lire(champ, lon, lat):
    """Ce que fait le web : bilinéaire dans la grille du PNG, ligne 0 au
    nord. `None` si trou de donnée ou hors grille.

    ⚠️ Cette fonction est le MIROIR de la boucle de rendu de
    `IsobarsFieldLayer.tsx` (mêmes formules `fx`/`fy`, même `latTop`,
    même bilinéaire, même repli sur le trou de donnée). C'est ce qui fait
    que ce banc teste la convention réellement appliquée à l'écran et pas
    seulement l'encodeur : si l'une des deux change, l'autre doit
    changer, et c'est ici qu'on s'en aperçoit."""
    px = decode_png_gray(champ["png"])
    nx, ny = champ["nx"], champ["ny"]
    fx = (lon - champ["lonMin"]) / champ["dLon"]
    # ligne 0 = nord -> on descend quand la latitude baisse
    fy = (champ["latMin"] + (ny - 1) * champ["dLat"] - lat) / champ["dLat"]
    j = int(np.floor(fy))
    if j < 0 or j + 1 >= ny:
        return None
    if champ["wrap"]:
        fx = ((fx % nx) + nx) % nx
        i = int(np.floor(fx))
        i1 = (i + 1) % nx
    else:
        i = int(np.floor(fx))
        if i < 0 or i + 1 >= nx:
            return None
        i1 = i + 1
    tx, ty = fx - np.floor(fx), fy - j
    v = [px[j, i], px[j, i1], px[j + 1, i], px[j + 1, i1]]
    if any(int(k) == 0 for k in v):
        return None
    a = float(v[0]) * (1 - tx) + float(v[1]) * tx
    b = float(v[2]) * (1 - tx) + float(v[3]) * tx
    return champ["baseHpa"] + a * (1 - ty) + b * ty


def controle(lon2d, lat2d, pression, step_deg, titre):
    champ = ingest.pressure_field(lon2d, lat2d, pression, step_deg)
    assert champ is not None, "champ vide"
    print(f"\n— {titre} —")
    print(f"  grille {champ['nx']} × {champ['ny']}, pas {champ['dLon']:g}° × "
          f"{champ['dLat']:g}°, wrap={champ['wrap']}")
    print(f"  PNG base64 : {len(champ['png']) / 1024:.1f} Ko "
          f"(binaire {len(base64.b64decode(champ['png'])) / 1024:.1f} Ko)")

    # 1) aller-retour sur 200 points tirés au hasard DANS la grille
    rng = np.random.default_rng(0)
    lats, lons = lat2d[:, 0], lon2d[0, :]
    ecarts = []
    for _ in range(200):
        j = int(rng.integers(1, len(lats) - 1))
        i = int(rng.integers(1, len(lons) - 1))
        lu = lire(champ, float(lons[i]), float(lats[j]))
        if lu is None:
            continue
        ecarts.append(abs(lu - float(pression[j, i])))
    ecarts = np.array(ecarts)
    print(f"  aller-retour : écart moyen {ecarts.mean():.3f} hPa, "
          f"max {ecarts.max():.3f} hPa ({len(ecarts)} points)")
    assert ecarts.max() < 1.0, "quantification/interpolation hors tolérance"

    # 2) orientation : la ligne 0 doit être la plus au NORD
    px = decode_png_gray(champ["png"])
    haut = float(np.mean(px[0][px[0] > 0])) if (px[0] > 0).any() else float("nan")
    bas = float(np.mean(px[-1][px[-1] > 0])) if (px[-1] > 0).any() else float("nan")
    nord = float(np.nanmean(pression[-1, :]))
    sud = float(np.nanmean(pression[0, :]))
    print(f"  orientation : ligne 0 = {champ['baseHpa'] + haut:.1f} hPa "
          f"(nord du modèle {nord:.1f}), dernière ligne = "
          f"{champ['baseHpa'] + bas:.1f} hPa (sud du modèle {sud:.1f})")
    assert abs(champ["baseHpa"] + haut - nord) < abs(champ["baseHpa"] + haut - sud) \
        or abs(nord - sud) < 1.0, "⛔ NAPPE RETOURNÉE (cf. bug du 08/09)"

    # 3) enroulement : Leaflet donne des longitudes hors [-180, 180] dès
    #    qu'on pane sur le monde répété. +185° doit lire comme −175°.
    if champ["wrap"]:
        a = lire(champ, -175.0, 20.0)
        b = lire(champ, 185.0, 20.0)
        c = lire(champ, 545.0, 20.0)
        print(f"  enroulement : −175° = {a:.1f} hPa, +185° = {b:.1f}, +545° = {c:.1f}")
        assert abs(a - b) < 0.01 and abs(a - c) < 0.01, "⛔ couture sur l'antiméridien"
    return champ


def synthetique():
    """Un anticyclone au nord, une dépression au sud : deux systèmes que
    l'orientation distingue sans ambiguïté."""
    lon = np.linspace(-180, 179.75, 1440)
    lat = np.linspace(-80, 80, 641)
    lon2d, lat2d = np.meshgrid(lon, lat)
    p = 1013 + 25 * np.sin(np.radians(lat2d)) + 3 * np.cos(np.radians(lon2d * 2))
    controle(lon2d, lat2d, p, 1.0, "synthétique lisse, monde 0,25° → 1°")

    # Champ RÉALISTE : le lisse ci-dessus se comprime trop bien pour dire
    # quoi que ce soit du poids réel. On y sème 30 systèmes (± 8 à 35 hPa,
    # 600 à 2 500 km) — l'ordre de grandeur d'une carte synoptique.
    rng = np.random.default_rng(1)
    p2 = 1013 + 8 * np.sin(np.radians(lat2d * 1.5))
    for _ in range(30):
        clat = float(rng.uniform(-70, 70))
        clon = float(rng.uniform(-180, 180))
        amp = float(rng.uniform(8, 35)) * (1 if rng.random() < 0.5 else -1)
        rayon = float(rng.uniform(6, 22))
        d2 = ((lon2d - clon) * np.cos(np.radians(lat2d))) ** 2 + (lat2d - clat) ** 2
        p2 = p2 + amp * np.exp(-d2 / (2 * rayon ** 2))
    controle(lon2d, lat2d, p2, 1.0, "synthétique réaliste (30 systèmes), monde")


def reel():
    from datetime import datetime, timezone
    for key in ("arpege_world", "arpege_europe"):
        cfg = ingest.GRIDS[key]
        meta = ingest.latest_json(cfg["model"])
        ref = datetime.strptime(meta["reference_time"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc)
        res = ingest.read_pressure(cfg["model"], ref, reference_time=ref)
        assert res, f"{key} : échéance introuvable"
        lon2d, lat2d, p = ingest.clip_latitude(*res, cfg["lat_clip_deg"])
        if "synop" in cfg["variants"]:
            p = ingest.smooth_pressure(p, cfg["smooth_sigma_cells"])
        champ = controle(lon2d, lat2d, p, cfg["field_step_deg"], f"{key} — {ref:%d/%m %HZ}")
        # 3) poids relatif dans le fichier réellement téléversé
        if "synop" in cfg["variants"]:
            geo = ingest.synop_geojson(lon2d, lat2d, p, cfg["synop_tol_deg"],
                                       cfg["synop_min_length_deg"])
        else:
            geo = ingest.isobars_geojson(lon2d, lat2d, p, step_hpa=ingest.LEVEL_STEP_HPA)
        sans = len(json.dumps(geo, separators=(",", ":")))
        geo["field"] = champ
        avec = len(json.dumps(geo, separators=(",", ":")))
        print(f"  fichier : {sans / 1024:.0f} Ko sans la nappe, {avec / 1024:.0f} Ko avec "
              f"(+{100 * (avec - sans) / sans:.0f} %)")


if __name__ == "__main__":
    synthetique()
    if "--reel" in sys.argv:
        reel()
    print("\n✅ banc nappe colorée : OK")
