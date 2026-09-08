#!/usr/bin/env python3
"""Banc de mesure — SYNOPTIQUE MONDE (08/09/2026). Aucun téléversement.

Le lot « synoptique sur le monde » reposait sur UNE estimation (150-300 Ko
par échéance) et sur DEUX suppositions à vérifier dans le fichier lui-même
(ordre des longitudes, bornage en latitude). Ce banc remplace les trois par
des mesures, AVANT le premier run réel — c'est la règle du projet : tout
chiffre non mesuré est étiqueté estimation, et on ne pousse pas sur une
estimation quand la mesure coûte deux minutes.

    python3 banc_monde_08-09.py [ISO]                # mesures du lot
    python3 banc_monde_08-09.py [ISO] --orientation  # ⛔ le contrôle du miroir

⛔ Ce banc a trouvé, en passant, un bug de production vieux de six semaines :
le champ ARPEGE était lu de la mauvaise latitude (nord→sud alors que les
`.om` d'Open-Meteo sont rangés sud→nord), donc le calque isobares Europe
était RETOURNÉ depuis le 23/07 — c'est ce qui posait « un L à 975 hPa au
large du Maroc » (une dépression islandaise, à son point miroir). Le mode
`--orientation` est le contrôle qui manquait ; le lancer après toute
modification de `read_pressure`.

Il mesure, pour la même échéance :
  · Monde 0,25° synoptique : poids du geojson, tracés, centres, niveaux ;
  · le critère d'antiméridien (§4.3) : aucun tracé ne doit avoir deux
    points consécutifs à plus de 90° de longitude — un tracé qui
    traverserait l'écran d'un bord à l'autre se verrait là ;
  · Europe 0,1° détaillé : poids, et surtout l'ÉCART entre le H le plus
    fort d'Europe vu par les deux grilles (§4.2) — même modèle, donc un
    écart franc signerait un bug de grille, pas une divergence météo.
"""
import sys, json, urllib.request
from datetime import datetime, timezone

import numpy as np
import fsspec
from omfiles import OmFileReader

import ingest as ing


def read_pressure_https(model, dt, reference_time=None):
    """MÊME lecture que `ing.read_pressure`, mais en HTTPS au lieu de
    `s3://`. Raison, constatée le 08/09 sur ce poste : le couple
    botocore/aiobotocore installé y est incompatible (s3fs lève
    `compute_endpoint_resolver_builtin_defaults() missing 1 required
    positional argument`) — panne d'ENVIRONNEMENT LOCAL, sans rapport
    avec l'ingestion, qui tourne dans la GitHub Action avec ses propres
    versions. Le bucket Open-Meteo est public : la même donnée se lit
    aussi bien en HTTPS, et on ne touche pas au python de Yann pour un
    banc jetable. ⚠️ Ne pas recopier ceci dans `ingest.py` : là-bas
    `s3://` + anon est la lecture de référence, et elle marche."""
    run_dt = reference_time if reference_time is not None else dt
    uri = (f"https://{ing.OM_BUCKET}.s3.amazonaws.com/data_spatial/{model}/"
           f"{run_dt.strftime('%Y/%m/%d/%H00Z')}/{dt.strftime('%Y-%m-%dT%H%M')}.om")
    backend = fsspec.open("blockcache::" + uri, mode="rb",
                          https={"block_size": 65536},
                          blockcache={"cache_storage": "/tmp/om_cache_banc"})
    try:
        with OmFileReader(backend) as root:
            pressure = root.get_child_by_name("pressure_msl").read_array((...))
            bbox = ing._BBOX_RE.search(
                root.get_child_by_name("crs_wkt").read_scalar())
            south, west, north, east = (float(x) for x in bbox.groups())
    except Exception:
        return None
    nj, ni = pressure.shape
    # sud → nord, comme `ing.read_pressure` depuis le correctif du 08/09
    # (cf. `--orientation` : c'est ce banc qui a trouvé le miroir).
    lon2d, lat2d = np.meshgrid(np.linspace(west, east, ni),
                               np.linspace(south, north, nj))
    return lon2d, lat2d, pressure


API_POINTS = [(45.0, 6.0), (48.9, 2.3), (60.5, -6.5), (23.7, 9.4),
              (40.4, -3.7), (65.0, 25.0), (52.0, 13.4), (35.0, 33.0)]
API_MODELE = {"arpege_europe": "meteofrance_arpege_europe",
              "arpege_world": "meteofrance_arpege_world"}


def orientation(iso, dt):
    """⛔ LE CONTRÔLE QUI MANQUAIT (08/09/2026). Compare le champ lu dans
    le `.om` à l'API Open-Meteo — même fournisseur, même modèle, même
    échéance — en des points connus, dans les DEUX sens de latitude.

    C'est le seul contrôle capable d'attraper un champ retourné : une
    carte d'isobares miroir n'a ni valeur aberrante, ni trou, ni erreur
    de dimension. Elle est simplement fausse, et plausible. Elle l'a été
    six semaines (23/07 → 08/09), et ce qu'elle a produit de plus visible
    est une dépression islandaise dessinée au large du Maroc.

    Attendu : « sud→nord » à quelques centièmes de hPa, « nord→sud » à
    plus de 10 hPa. Si un jour c'est l'inverse, c'est le layout
    d'Open-Meteo qui a changé — et il faut alors changer `read_pressure`,
    pas ce banc."""
    lat = ",".join(str(a) for a, _ in API_POINTS)
    lon = ",".join(str(o) for _, o in API_POINTS)
    for key, cfg in ing.GRIDS.items():
        res = read_pressure_https(cfg["model"], dt)
        if res is None:
            print(f"  {key} : échéance absente")
            continue
        lon2d, lat2d, p = res
        # Bornes RÉELLES de la grille lue (crs_wkt), pas des constantes
        # recopiées : c'est justement une constante recopiée d'AROME qui
        # a causé le miroir.
        south, north = float(lat2d.min()), float(lat2d.max())
        west, east = float(lon2d.min()), float(lon2d.max())
        pas_lat = (north - south) / (p.shape[0] - 1)
        pas_lon = (east - west) / (p.shape[1] - 1)
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
               f"&hourly=pressure_msl&models={API_MODELE[key]}"
               f"&start_date={iso[:10]}&end_date={iso[:10]}&timezone=UTC")
        api = json.load(urllib.request.urlopen(url))
        ecarts = {"sud→nord": [], "nord→sud": []}
        for k, (la, lo) in enumerate(API_POINTS):
            h = api[k]["hourly"]
            if iso not in h["time"]:
                continue
            ref = h["pressure_msl"][h["time"].index(iso)]
            if ref is None or not south <= la <= north or not west <= lo <= east:
                continue
            i = int(round((lo - west) / pas_lon))
            for sens, j in (("sud→nord", int(round((la - south) / pas_lat))),
                            ("nord→sud", int(round((north - la) / pas_lat)))):
                if 0 <= j < p.shape[0] and 0 <= i < p.shape[1]:
                    ecarts[sens].append(abs(float(p[j, i]) - ref))
        for sens, e in ecarts.items():
            if e:
                verdict = "✔ c'est ce sens que lit ingest.py" if sens == "sud→nord" else ""
                print(f"  {key} lu {sens} : écart moyen à l'API "
                      f"{sum(e)/len(e):6.2f} hPa sur {len(e)} points {verdict}")


def mesure(key, iso, dt):
    cfg = ing.GRIDS[key]
    res = read_pressure_https(cfg["model"], dt)
    if res is None:
        print(f"  {key} : échéance absente chez Open-Meteo")
        return None
    lon2d, lat2d, p = res
    print(f"  {key} : grille brute {p.shape[1]}×{p.shape[0]} — "
          f"lat {lat2d[0,0]:+.2f}→{lat2d[-1,0]:+.2f}, "
          f"lon {lon2d[0,0]:+.2f}→{lon2d[0,-1]:+.2f}")
    lon2d, lat2d, p = ing.clip_latitude(lon2d, lat2d, p, cfg["lat_clip_deg"])
    if cfg["lat_clip_deg"]:
        print(f"           après coupe ±{cfg['lat_clip_deg']:g}° : "
              f"{p.shape[1]}×{p.shape[0]}")
    smooth = ing.smooth_pressure(p, cfg["smooth_sigma_cells"])
    centers = ing.find_centers(lon2d, lat2d, smooth,
                               max_per_kind=cfg["max_centers_per_kind"])
    out = {}
    if "synop" in cfg["variants"]:
        out["synop"] = ing.synop_geojson(lon2d, lat2d, smooth,
                                         cfg["synop_tol_deg"],
                                         cfg["synop_min_length_deg"])
    if "detail" in cfg["variants"]:
        out["detail"] = ing.isobars_geojson(lon2d, lat2d, p,
                                            step_hpa=ing.LEVEL_STEP_HPA)
    for variant, geo in out.items():
        geo["centers"] = centers
        poids = len(json.dumps(geo, separators=(",", ":")).encode())
        niveaux = sorted({f["properties"]["hpa"] for f in geo["features"]})
        pts = sum(len(f["geometry"]["coordinates"]) for f in geo["features"])
        print(f"  {key}/{variant} : {poids/1024:.0f} Ko — "
              f"{len(geo['features'])} tracés, {pts} points, "
              f"{len(niveaux)} niveaux {niveaux[0] if niveaux else '—'}"
              f"→{niveaux[-1] if niveaux else '—'}, {len(centers)} centres")
    return {"centers": centers, **out}


def saut_longitude_max(geo):
    """§4.3 — le plus grand écart de longitude entre deux points
    CONSÉCUTIFS d'un même tracé. La grille Monde est publiée en
    −180→180 (crs_wkt vérifié le 08/09) : marching squares ne referme
    donc rien par-dessus l'antiméridien, les tracés s'y arrêtent. Ce
    contrôle est là pour que la supposition soit VÉRIFIÉE et le reste."""
    pire, ou = 0.0, None
    for f in geo["features"]:
        c = f["geometry"]["coordinates"]
        for (x1, _), (x2, _) in zip(c, c[1:]):
            if abs(x2 - x1) > pire:
                pire, ou = abs(x2 - x1), (f["properties"]["hpa"], x1, x2)
    return pire, ou


def appariement(ref, autre, bbox):
    """§4.2 — pour chaque centre de la grille EUROPE dans la BBOX, son
    homologue de même type le plus proche dans la grille MONDE.

    Version corrigée du critère : comparer « le H le plus fort de chaque
    liste » ne marche pas, parce que deux hautes pressions à 1027,2 et
    1028,0 hPa sont à égalité de fait et à 16° l'une de l'autre — le test
    échouait sur un ex æquo, pas sur un désaccord. Ce qu'on veut vérifier
    est que les DEUX grilles voient les MÊMES systèmes au même endroit,
    ce qui est vrai ou faux centre par centre.

    Un centre Europe sans homologue n'est pas un échec en soi : le Monde
    plafonne son nombre de centres (`max_centers_per_kind`) et lisse plus
    fort, donc il peut ignorer un petit centre régional. On l'affiche."""
    lat0, lat1, lon0, lon1 = bbox
    lignes = []
    for c in sorted((c for c in ref if lat0 <= c["lat"] <= lat1
                     and lon0 <= c["lon"] <= lon1),
                    key=lambda c: -c.get("prominence", 0)):
        cands = [(max(abs(c["lat"] - o["lat"]), abs(c["lon"] - o["lon"])), o)
                 for o in autre if o["kind"] == c["kind"]]
        d, o = min(cands, default=(None, None), key=lambda x: x[0])
        lignes.append((c, d, o))
    return lignes


def main():
    meta = ing.latest_json(ing.GRIDS["arpege_world"]["model"])
    ref = datetime.strptime(meta["reference_time"],
                            "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    iso = args[0] if args else ref.strftime("%Y-%m-%dT%H:%M")
    dt = datetime.strptime(iso, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
    print(f"Run de référence {ref.isoformat()} — échéance mesurée {iso}\n")

    if "--orientation" in sys.argv:
        orientation(iso, dt)
        return

    monde = mesure("arpege_world", iso, dt)
    europe = mesure("arpege_europe", iso, dt)
    print()

    if monde:
        pire, ou = saut_longitude_max(monde["synop"])
        verdict = "OK" if pire <= 90 else "ÉCHEC"
        print(f"§4.3 antiméridien : saut de longitude max {pire:.2f}° "
              f"[{verdict}] {ou if pire > 90 else ''}")
        lats = [c["lat"] for c in monde["centers"]]
        if lats:
            print(f"     centres entre {min(lats):+.1f}° et {max(lats):+.1f}° "
                  f"de latitude (bornage ±80° : "
                  f"{'OK' if max(abs(l) for l in lats) <= 80 else 'ÉCHEC'})")

    if monde and europe:
        # BBOX Europe volontairement rétrécie de 4° : un centre pile au
        # bord de la grille Europe est exclu par `find_centers` (07/09),
        # le comparer à son homologue Monde n'aurait aucun sens.
        bbox = (24, 68, -28, 38)
        print("§4.2 chaque centre EUROPE et son homologue MONDE "
              "(< 1,5° et ≤ 2 hPa attendus) :")
        for c, d, o in appariement(europe["centers"], monde["centers"], bbox):
            if o is None:
                print(f"     {c['kind']} {c['hpa']:7.1f} @ {c['lat']:+5.1f},{c['lon']:+6.1f}"
                      f"  → aucun centre {c['kind']} côté Monde")
                continue
            dp = abs(c["hpa"] - o["hpa"])
            ok = "OK" if d < 1.5 and dp <= 2 else ("hors plafond Monde" if d > 5 else "ÉCART")
            print(f"     {c['kind']} {c['hpa']:7.1f} @ {c['lat']:+5.1f},{c['lon']:+6.1f}"
                  f"  → {o['hpa']:7.1f} @ {o['lat']:+5.1f},{o['lon']:+6.1f}"
                  f"   Δ {d:5.2f}° / {dp:4.1f} hPa  [{ok}]")


if __name__ == "__main__":
    main()
