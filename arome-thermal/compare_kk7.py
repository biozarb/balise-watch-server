#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════
#  compare_kk7.py — VALIDATION HORS-LIGNE de notre calque « estimation
#  thermique » contre la climatologie thermal.kk7.ch.
#
#  ⚠️ OUTIL DE DIAGNOSTIC. N'est jamais importé par l'ingestion, jamais
#  appelé par un workflow, jamais déployé côté client. Rien de ce qu'il
#  télécharge n'est republié ni stocké dans notre bucket : les tuiles kk7
#  restent dans un cache local temporaire, le temps de calculer des
#  statistiques. C'est ce qui permet de l'utiliser AVANT d'avoir l'accord
#  de M. von Känel (cf. PROMPT_DECISION_DONNEES_TRACES.md).
#
#  Données kk7 : © M. von Känel — thermal.kk7.ch, CC-BY-NC-SA 4.0.
#  https://creativecommons.org/licenses/by-nc-sa/4.0/
#
#  ── LA QUESTION POSÉE ────────────────────────────────────────────
#  NOTES_TECHNIQUES dit, depuis le début, que le calque n'a « aucune
#  validation contre des vols réels » et que GATE_LO/GATE_HI sont posés
#  par raisonnement physique. kk7 agrège 3,8 M de vols réels. Ce script
#  répond donc à deux questions distinctes, à ne pas confondre :
#
#   Q1. Notre localisation par le relief vaut-elle mieux que le hasard ?
#       Mesuré par le LIFT à couverture égale (cf. §MÉTRIQUES). Si le
#       lift de `w* × relief` ne dépasse pas celui de `w*` seul, alors
#       tout terrain.ts ne sert à rien et il faut le savoir.
#
#   Q2. Quels GATE_LO/GATE_HI maximisent l'accord avec kk7 ?
#       Balayage systématique, sortie triée par F1.
#
#  ── CE QUE CE SCRIPT NE PROUVE PAS ───────────────────────────────
#  kk7 n'est PAS la vérité terrain. C'est une climatologie de traces,
#  avec ses propres biais, documentés par son auteur :
#    - surreprésentation des abords de décollage (« thermals next to
#      popular launch pads are mostly overrated ») ;
#    - rien en dessous de ~20 vols/100 m², donc du vide qui ne veut pas
#      dire « pas de thermique » mais « personne n'a volé ici » ;
#    - agrégat toutes conditions confondues, alors que nous calculons
#      une heure précise d'un jour précis.
#  Un désaccord peut donc venir de NOUS comme de LUI. Ce script mesure
#  un accord, pas une justesse.
# ══════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import io
import math
import os
import sys
import time
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

try:
    import numpy as np
    from PIL import Image
except ImportError as e:  # pragma: no cover
    sys.exit(f"Dépendance manquante ({e}). Installer : pip3 install --user numpy pillow")


# ── Constantes MIROIR du client ───────────────────────────────────
# Toute divergence ici invaliderait la comparaison. Si l'une de ces
# valeurs change dans PWA/web/src/, la changer ICI aussi.
#   lib/terrain.ts       -> DERIV_M, SOLAR_CAP, seuils de pente, CONVEX_*
#   lib/config.ts        -> THERMAL_MIN_WSTAR
#   ThermalGridLayer.tsx -> CONTRAST_M, GATE_LO, GATE_HI
DERIV_M = 120.0
SOLAR_CAP = 1.8
CONVEX_SCALE = 4000.0
CONVEX_AMP = 0.25
ENERGY_REF_DEG = 35.0
CONTRAST_M = 2000.0
GATE_LO_DEFAULT = 1.04
GATE_HI_DEFAULT = 1.20
THERMAL_MIN_WSTAR = 1.0

# ── Sources ───────────────────────────────────────────────────────
# WMTS kk7 : orientation XYZ standard (TopLeftCorner en haut à gauche
# dans WMTSCapabilities). ⚠️ NE PAS confondre avec l'endpoint /tiles/,
# qui lui est en TMS (y inversé) — se tromper produit une comparaison
# silencieusement fausse, avec des chiffres parfaitement plausibles.
KK7_URL = "https://thermal.kk7.ch/tiles/wmts/{style}/{z}/{x}/{y}.png?src={src}"
KK7_MAX_Z = 12          # zoom natif max de la couche thermals
DEM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
SB_URL = "https://dfufrvpoezglxxtunjni.supabase.co"
THERMAL_TILE_URL = SB_URL + "/storage/v1/object/public/wind-grid/arome/thermal/{lat}_{lon}.json"
TILE_DEG = 2            # WIND_GRID_TILE_DEG côté client
TILE_PX = 256

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache_kk7")
UA = "balise-watch/compare_kk7 (offline validation; contact via thermal.kk7.ch)"
MAX_TILES = 400         # garde-fou : au-delà on martèle un serveur perso


def fetch(url: str, cache_key: str | None = None, pause: float = 0.15) -> bytes | None:
    """GET avec cache disque. `None` si 404/erreur — jamais d'exception
    silencieuse ni de contenu inventé : l'appelant compte les trous."""
    if cache_key:
        path = os.path.join(CACHE, cache_key)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read() or None
        os.makedirs(os.path.dirname(path), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        data = b"" if e.code == 404 else None
        if data is None:
            print(f"  ! HTTP {e.code} sur {url}", file=sys.stderr)
    except Exception as e:
        print(f"  ! {type(e).__name__} sur {url}: {e}", file=sys.stderr)
        data = None
    # Politesse : thermal.kk7 est hébergé et payé par une seule personne.
    time.sleep(pause)
    if data is not None and cache_key:
        with open(os.path.join(CACHE, cache_key), "wb") as f:
            f.write(data)
    return data or None


# ── Slippy map ────────────────────────────────────────────────────
def lon_to_tx(lon: float, z: float) -> float:
    return (lon + 180.0) / 360.0 * (2 ** z)


def lat_to_ty(lat: float, z: float) -> float:
    r = math.radians(lat)
    return (1 - math.log(math.tan(r) + 1 / math.cos(r)) / math.pi) / 2 * (2 ** z)


def ty_to_lat(ty: float, z: float) -> float:
    n = math.pi * (1 - 2 * ty / (2 ** z))
    return math.degrees(math.atan(math.sinh(n)))


def tx_to_lon(tx: float, z: float) -> float:
    return tx / (2 ** z) * 360.0 - 180.0


def mosaic(url_tpl: str, z: int, x0: int, x1: int, y0: int, y1: int,
           tag: str, **fmt) -> tuple[np.ndarray, int]:
    """Assemble les tuiles [x0..x1]×[y0..y1] en un seul raster RGBA.
    Retourne (raster, nb_tuiles_manquantes). Une tuile absente reste à
    zéro ET est comptée — on ne bouche pas les trous."""
    w, h = (x1 - x0 + 1) * TILE_PX, (y1 - y0 + 1) * TILE_PX
    out = np.zeros((h, w, 4), dtype=np.uint8)
    missing = 0
    total = (x1 - x0 + 1) * (y1 - y0 + 1)
    done = 0
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            done += 1
            url = url_tpl.format(z=z, x=x, y=y, **fmt)
            key = f"{tag}/{z}_{x}_{y}.png"
            raw = fetch(url, key)
            if raw is None:
                missing += 1
                continue
            try:
                img = Image.open(io.BytesIO(raw)).convert("RGBA")
            except Exception:
                missing += 1
                continue
            px = (x - x0) * TILE_PX, (y - y0) * TILE_PX
            out[px[1]:px[1] + TILE_PX, px[0]:px[0] + TILE_PX] = np.asarray(img)
            if done % 25 == 0:
                print(f"    {tag}: {done}/{total}", file=sys.stderr)
    return out, missing


def sun_position(dt: datetime, lat: float, lon: float) -> tuple[float, float]:
    """Miroir EXACT de lib/sun.ts (azimut compas, élévation en degrés)."""
    rad = math.pi / 180.0
    d = dt.timestamp() / 86400.0 - 0.5 + 2440588 - 2451545
    M = rad * (357.5291 + 0.98560028 * d)
    C = rad * (1.9148 * math.sin(M) + 0.02 * math.sin(2 * M) + 0.0003 * math.sin(3 * M))
    P = rad * 102.9372
    L = M + C + P + math.pi
    e = rad * 23.4397
    dec = math.asin(math.sin(e) * math.sin(L))
    ra = math.atan2(math.sin(L) * math.cos(e), math.cos(L))
    lw, phi = rad * -lon, rad * lat
    theta = rad * (280.16 + 360.9856235 * d) - lw
    H = theta - ra
    az = math.atan2(math.sin(H), math.cos(H) * math.sin(phi) - math.tan(dec) * math.cos(phi))
    el = math.asin(math.sin(phi) * math.sin(dec) + math.cos(phi) * math.cos(dec) * math.cos(H))
    return ((az / rad) + 180 + 360) % 360, el / rad


def terrain_factor(elev: np.ndarray, mppx: np.ndarray,
                   sun_az: float, sun_el: float) -> np.ndarray:
    """Miroir vectorisé de terrainFactorAt(). `elev` en m, `mppx` = taille
    d'un pixel au sol par LIGNE (Mercator : varie avec la latitude).
    Retourne NaN là où les dérivées ne sont pas calculables (bords)."""
    h, w = elev.shape
    if sun_el <= 0:
        return np.full((h, w), np.nan, dtype=np.float64)

    # Décalage entier de pixels le plus proche de DERIV_M. Différence
    # assumée avec le client, qui échantillonne exactement à ±120 m par
    # interpolation bilinéaire : ici on est à ±un demi-pixel (~13 m à z12).
    step = max(1, int(round(DERIV_M / float(np.median(mppx)))))
    d = (mppx * step)[:, None]                   # distance réelle, par ligne

    e0 = elev
    eE = np.roll(elev, -step, axis=1)
    eW = np.roll(elev, step, axis=1)
    eN = np.roll(elev, step, axis=0)             # nord = y décroissant
    eS = np.roll(elev, -step, axis=0)

    dzdx = (eE - eW) / (2 * d)
    dzdy = (eN - eS) / (2 * d)
    slope = np.arctan(np.hypot(dzdx, dzdy))
    aspect = (np.degrees(np.arctan2(-dzdx, -dzdy)) + 360.0) % 360.0

    el = math.radians(sun_el)
    rel = np.radians(sun_az - aspect)
    cos_slope = np.cos(slope) * math.sin(el) + np.sin(slope) * math.cos(el) * np.cos(rel)
    solar = np.where(cos_slope <= 0, 0.0,
                     np.minimum(SOLAR_CAP, cos_slope / math.sin(el)))

    sd = np.degrees(slope)
    slope_w = np.where(sd < 3, 0.25,
               np.where(sd < 12, 0.25 + 0.75 * (sd - 3) / 9,
                np.where(sd <= 40, 1.0, np.maximum(0.35, 1 - (sd - 40) / 40))))

    lap = (eE + eW + eN + eS - 4 * e0) / (d * d)
    convex = np.clip(-lap * CONVEX_SCALE, -1, 1)
    convex_w = 1 + CONVEX_AMP * convex

    energy = min(1.0, math.sin(el) / math.sin(math.radians(ENERGY_REF_DEG)))
    fac = solar * slope_w * convex_w * energy

    # Les `roll` recyclent les bords : on les invalide plutôt que de les
    # laisser produire une pente absurde entre nord et sud du raster.
    fac[:step, :] = np.nan
    fac[-step:, :] = np.nan
    fac[:, :step] = np.nan
    fac[:, -step:] = np.nan
    return fac


def box_mean_nan(a: np.ndarray, r: int) -> np.ndarray:
    """Moyenne glissante carrée ignorant les NaN — miroir de
    boxBlurIgnoringNaN(). Sommes cumulées : O(n), indépendant de r."""
    v = np.nan_to_num(a, nan=0.0)
    m = (~np.isnan(a)).astype(np.float64)

    def integ(x):
        c = np.cumsum(np.cumsum(x, axis=0), axis=1)
        return np.pad(c, ((1, 0), (1, 0)), mode="constant")

    Iv, Im = integ(v), integ(m)
    h, w = a.shape
    ys, xs = np.arange(h), np.arange(w)
    y0 = np.clip(ys - r, 0, h)[:, None]
    y1 = np.clip(ys + r + 1, 0, h)[:, None]
    x0 = np.clip(xs - r, 0, w)[None, :]
    x1 = np.clip(xs + r + 1, 0, w)[None, :]

    def win(I):
        return I[y1, x1] - I[y0, x1] - I[y1, x0] + I[y0, x0]

    s, c = win(Iv), win(Im)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(c > 0, s / c, np.nan)


def load_wstar(south, north, west, east, time_iso):
    """Charge nos tuiles thermiques Supabase et renvoie
    (grille 2D w*, lat0, lon0, pas, horodatage retenu).
    Sort en erreur explicite si l'Action n'a jamais tourné — mieux qu'une
    comparaison contre du vide qu'on prendrait pour un désaccord."""
    tiles = []
    for tlat in range(int(math.floor(south / TILE_DEG) * TILE_DEG),
                      int(math.floor(north / TILE_DEG) * TILE_DEG) + 1, TILE_DEG):
        for tlon in range(int(math.floor(west / TILE_DEG) * TILE_DEG),
                          int(math.floor(east / TILE_DEG) * TILE_DEG) + 1, TILE_DEG):
            raw = fetch(THERMAL_TILE_URL.format(lat=tlat, lon=tlon),
                        f"thermal/{tlat}_{tlon}.json", pause=0.0)
            if raw:
                tiles.append(json.loads(raw))
    if not tiles:
        sys.exit("Aucune tuile thermique Supabase. L'Action arome-thermal "
                 "a-t-elle tourné ? (cf. PROMPT_REPRISE §5.1)")

    times = tiles[0]["times"]
    if time_iso in times:
        idx = times.index(time_iso)
    else:
        # Échéance la plus proche, mais on le DIT — un décalage d'heure
        # sur l'exposition des pentes changerait tout le résultat.
        want = datetime.fromisoformat(time_iso).replace(tzinfo=timezone.utc)
        idx = min(range(len(times)), key=lambda i: abs(
            datetime.fromisoformat(times[i]).replace(tzinfo=timezone.utc) - want))
        print(f"  ! échéance {time_iso} absente, repli sur {times[idx]}", file=sys.stderr)

    pts = [p for t in tiles for p in t["points"]]
    lats = sorted({p["lat"] for p in pts})
    lons = sorted({p["lon"] for p in pts})
    step = min(min(b - a for a, b in zip(lats, lats[1:])),
               min(b - a for a, b in zip(lons, lons[1:])))
    n_lat = int(round((lats[-1] - lats[0]) / step)) + 1
    n_lon = int(round((lons[-1] - lons[0]) / step)) + 1
    g = np.full((n_lat, n_lon), np.nan)
    for p in pts:
        v = p["wstar"][idx]
        if v is None:
            continue                              # trou : on n'invente pas
        g[int(round((p["lat"] - lats[0]) / step)),
          int(round((p["lon"] - lons[0]) / step))] = v
    return g, lats[0], lons[0], step, times[idx]


def sample_bilinear(g, lat0, lon0, step, lat, lon):
    """Interpolation bilinéaire, NaN si un des 4 voisins manque —
    exactement le parti-pris du client (rien plutôt qu'une extrapolation)."""
    fy = (lat - lat0) / step
    fx = (lon - lon0) / step
    j, i = np.floor(fy).astype(int), np.floor(fx).astype(int)
    ok = (j >= 0) & (j + 1 < g.shape[0]) & (i >= 0) & (i + 1 < g.shape[1])
    j, i = np.clip(j, 0, g.shape[0] - 2), np.clip(i, 0, g.shape[1] - 2)
    ty, tx = fy - j, fx - i
    v = ((g[j, i] * (1 - tx) + g[j, i + 1] * tx) * (1 - ty) +
         (g[j + 1, i] * (1 - tx) + g[j + 1, i + 1] * tx) * ty)
    return np.where(ok, v, np.nan)


def kk7_intensity(rgba: np.ndarray) -> np.ndarray:
    """Reconstruit l'intensité 0-1 de la rampe kk7 depuis les pixels.

    ⚠️ NE PAS revenir à « intensité = alpha/255 ». Encodage MESURÉ sur les
    tuiles réelles (Maurienne, thermals_jul_07, 12 tuiles, 107 276 px
    visibles), pas supposé :

      - alpha < 255 : bleu pur (R=G=0), et B = alpha/2 exactement
        (corrélation B/alpha = 1,000 sur 44 391 px). L'alpha EST le signal.
      - alpha = 255 : l'alpha sature et c'est la COULEUR qui prend le
        relais — bleu (0,0,255) -> cyan (0,255,255) -> jaune, avec G qui
        monte d'abord, puis R+B ≈ 247 constant pendant que R monte et B
        descend (vérifié sur 263 couleurs uniques).

    Lire l'alpha seul écrase donc toute la moitié haute de l'échelle dans
    une seule valeur — c'est-à-dire précisément les zones où kk7 est le
    plus sûr de lui, les seules qui nous intéressent pour un recalage.
    """
    r = rgba[:, :, 0].astype(np.float64)
    g = rgba[:, :, 1].astype(np.float64)
    b = rgba[:, :, 2].astype(np.float64)
    a = rgba[:, :, 3].astype(np.float64)
    # Régime transparent : linéaire en alpha, occupe la moitié basse.
    low = 0.5 * (a / 255.0)
    # Régime saturé : bleu->cyan (G monte), puis cyan->jaune (R monte).
    t = np.where(g < 255, 0.5 * (g / 255.0), 0.5 + 0.5 * np.clip(r / 247.0, 0, 1))
    high = 0.5 + 0.5 * t
    return np.where(a >= 255, high, low)


# ── MÉTRIQUES ─────────────────────────────────────────────────────
# LIFT À COUVERTURE ÉGALE — la seule métrique honnête ici.
#
# Comparer bêtement « % de pixels allumés chez nous » à « % chez kk7 »
# ne dit rien : un calque qui allume tout obtient un rappel parfait. On
# force donc chaque score à allumer EXACTEMENT le même nombre de pixels
# que kk7, puis on regarde la proportion de bons.
#
#   lift = précision(score) / taux de base(kk7)
#
#   lift = 1  -> le score ne vaut pas mieux qu'un tirage au hasard
#   lift = 2  -> deux fois plus de chances de tomber sur une zone kk7
#                qu'en pointant au hasard dans le même massif
#
# C'est cette valeur, pour `w*` seul contre `w* × relief`, qui dit si
# terrain.ts apporte quoi que ce soit. Sans ce contrôle, n'importe quel
# score produit des pourcentages d'accord flatteurs.

def lift(score, kk7_pos, valid, coverage):
    m = valid & ~np.isnan(score)
    n = int(m.sum() * coverage)
    if n < 100:
        return None, None
    thr = np.partition(score[m], -n)[-n]
    sel = m & (score >= thr)
    base = kk7_pos[m].mean()
    if base <= 0:
        return None, None
    prec = kk7_pos[sel].mean()
    return prec / base, prec


def report_mask(name, sel, kk7_pos, valid):
    """Précision/rappel/F1 d'un masque tel qu'il serait RÉELLEMENT rendu
    à l'écran (avec sa couverture propre, pas normalisée)."""
    sel = sel & valid
    if sel.sum() == 0:
        print(f"  {name:<34} — rien d'allumé")
        return None
    inter = (sel & kk7_pos).sum()
    prec = inter / sel.sum()
    rec = inter / max(1, kk7_pos.sum())
    f1 = 2 * prec * rec / (prec + rec) if prec + rec > 0 else 0.0
    base = kk7_pos[valid].mean()
    print(f"  {name:<34} couv {sel.sum()/valid.sum():6.1%}  "
          f"préc {prec:6.1%}  rapp {rec:6.1%}  F1 {f1:5.3f}  lift {prec/base:4.2f}")
    return f1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bbox", default="45.10,6.20,45.55,6.85",
                    help="south,west,north,east (défaut : Maurienne)")
    ap.add_argument("--layer", default="thermals_jul_07",
                    help="style kk7 : thermals_{all,jan,apr,jul,oct}_{all,04,07,10} "
                         "(mois ±1,5 M ; heures APRÈS LE LEVER, pas heure locale)")
    ap.add_argument("--time", default=None,
                    help="échéance UTC ISO, ex. 2026-07-20T12:00 (défaut : midi UTC du jour)")
    ap.add_argument("--zoom", type=int, default=12)
    ap.add_argument("--gate-lo", type=float, default=GATE_LO_DEFAULT)
    ap.add_argument("--gate-hi", type=float, default=GATE_HI_DEFAULT)
    ap.add_argument("--kk7-thr", type=float, default=0.25,
                    help="seuil d'alpha kk7 (0-1) au-dessus duquel on considère "
                         "que kk7 signale quelque chose")
    ap.add_argument("--src", default="balise-watch-offline-validation",
                    help="paramètre src= exigé par kk7 pour son suivi de charge")
    ap.add_argument("--sweep", action="store_true", help="balayage GATE_LO/GATE_HI")
    a = ap.parse_args()

    south, west, north, east = (float(v) for v in a.bbox.split(","))
    z = min(a.zoom, KK7_MAX_Z)
    if z != a.zoom:
        print(f"! zoom ramené à {z} (zoom natif max de la couche kk7)", file=sys.stderr)
    time_iso = a.time or f"{datetime.now(timezone.utc):%Y-%m-%d}T12:00"

    x0, x1 = int(lon_to_tx(west, z)), int(lon_to_tx(east, z))
    y0, y1 = int(lat_to_ty(north, z)), int(lat_to_ty(south, z))
    n_tiles = (x1 - x0 + 1) * (y1 - y0 + 1)
    if n_tiles > MAX_TILES:
        sys.exit(f"{n_tiles} tuiles demandées (max {MAX_TILES}). Réduire --bbox ou --zoom.")

    print(f"\n══ compare_kk7 — {a.layer} @ z{z} — {time_iso}Z")
    print(f"   bbox {south},{west},{north},{east} — {n_tiles} tuiles × 2 sources")
    print(f"   données kk7 © M. von Känel, CC-BY-NC-SA 4.0 (usage hors-ligne, non redistribué)\n")

    kk7, miss_k = mosaic(KK7_URL, z, x0, x1, y0, y1, "kk7",
                         style=a.layer, src=a.src)
    dem, miss_d = mosaic(DEM_URL, z, x0, x1, y0, y1, "dem")
    print(f"   tuiles manquantes : kk7 {miss_k}, dem {miss_d}")
    if miss_d:
        print("   ! trous DEM -> pixels exclus du calcul, pas comblés")

    elev = (dem[:, :, 0].astype(np.float64) * 256
            + dem[:, :, 1] + dem[:, :, 2] / 256.0) - 32768.0
    dem_ok = dem[:, :, 3] > 0
    elev[~dem_ok] = np.nan

    h, w = elev.shape
    lat_px = np.array([ty_to_lat(y0 + (r + 0.5) / TILE_PX, z) for r in range(h)])
    lon_px = np.array([tx_to_lon(x0 + (c + 0.5) / TILE_PX, z) for c in range(w)])
    mppx = 156543.03392 * np.cos(np.radians(lat_px)) / (2 ** z)
    LAT = np.repeat(lat_px[:, None], w, axis=1)
    LON = np.repeat(lon_px[None, :], h, axis=0)

    # Soleil : UNE position au centre, comme le client (l'écart d'azimut
    # sur quelques dizaines de km est négligeable devant l'incertitude
    # du reste du modèle).
    cy, cx = (south + north) / 2, (west + east) / 2
    sun_az, sun_el = sun_position(
        datetime.fromisoformat(time_iso).replace(tzinfo=timezone.utc), cy, cx)
    print(f"   soleil : az {sun_az:.1f}° el {sun_el:.1f}°")
    if sun_el <= 0:
        sys.exit("Soleil sous l'horizon à cette heure : le calque est vide par construction.")

    g, lat0, lon0, step, used = load_wstar(south, north, west, east, time_iso)
    print(f"   w* AROME : échéance {used}, grille {g.shape}, "
          f"médiane {np.nanmedian(g):.2f} m/s")

    wmeteo = sample_bilinear(g, lat0, lon0, step, LAT, LON)
    fac = terrain_factor(elev, mppx, sun_az, sun_el)
    blur_r = max(2, int(round(CONTRAST_M / float(np.median(mppx)))))
    mean = box_mean_nan(fac, blur_r)
    with np.errstate(invalid="ignore", divide="ignore"):
        anomaly = np.where(mean > 0, fac / mean, np.nan)

    kk7_int = kk7_intensity(kk7)
    kk7_pos = kk7_int >= a.kk7_thr

    # ── CONTRÔLE D'ALIGNEMENT (à ne jamais retirer) ──────────────
    # L'endpoint /tiles/ de kk7 est en TMS, l'endpoint /tiles/wmts/ en
    # XYZ. Se tromper retourne le raster verticalement et produit une
    # comparaison parfaitement plausible ET fausse. Test : les zones
    # thermiques de kk7 doivent tomber sur des PENTES, pas sur des fonds
    # de vallée. Si la version retournée sépare mieux, l'orientation est
    # inversée quelque part.
    slope_deg = np.degrees(np.arctan(np.hypot(
        (np.roll(elev, -1, 1) - np.roll(elev, 1, 1)) / (2 * mppx[:, None]),
        (np.roll(elev, 1, 0) - np.roll(elev, -1, 0)) / (2 * mppx[:, None]))))
    flip = kk7_intensity(kk7[::-1, :, :]) >= a.kk7_thr
    s_norm = np.nanmean(slope_deg[kk7_pos]) - np.nanmean(slope_deg)
    s_flip = np.nanmean(slope_deg[flip]) - np.nanmean(slope_deg)
    print(f"   alignement : pente moyenne kk7+ vs fond {s_norm:+.2f}° "
          f"(retourné : {s_flip:+.2f}°)")
    if s_flip > s_norm:
        sys.exit("ORIENTATION SUSPECTE : la version retournée colle mieux au "
                 "relief. Vérifier XYZ vs TMS avant d'interpréter quoi que ce soit.")

    # Domaine de comparaison : uniquement les pixels où TOUT est connu.
    # Sinon on compterait comme « désaccord » des endroits où l'un des
    # deux n'a simplement pas d'information.
    valid = ~(np.isnan(wmeteo) | np.isnan(fac) | np.isnan(anomaly)) & dem_ok
    print(f"   domaine valide : {valid.sum():,} px / {valid.size:,} "
          f"({valid.sum()/valid.size:.1%}) — kk7 positif sur "
          f"{kk7_pos[valid].mean():.1%} d'entre eux\n")
    if valid.sum() < 10000:
        sys.exit("Domaine valide trop petit pour conclure quoi que ce soit.")

    def gate(lo, hi):
        return np.clip((anomaly - lo) / max(1e-9, hi - lo), 0, 1)

    ww = wmeteo * fac
    g_cur = gate(a.gate_lo, a.gate_hi)

    print("── Ce qui est RÉELLEMENT affiché aujourd'hui ──────────────")
    report_mask(f"rendu actuel (gates {a.gate_lo}/{a.gate_hi})",
                (ww >= THERMAL_MIN_WSTAR) & (g_cur > 0), kk7_pos, valid)
    report_mask("sans porte de contraste", ww >= THERMAL_MIN_WSTAR, kk7_pos, valid)
    report_mask("w* brut, sans relief du tout", wmeteo >= THERMAL_MIN_WSTAR, kk7_pos, valid)

    print("\n── Contrôle : chaque score à COUVERTURE ÉGALE ─────────────")
    print("   (lift 1,00 = ne vaut pas mieux que pointer au hasard)")
    for cov in (0.05, 0.10, 0.20):
        row = [f"   couv {cov:.0%} :"]
        for name, sc in (("w* seul", wmeteo),
                         ("w*×relief", ww),
                         ("w*×relief×contraste", ww * g_cur),
                         ("contraste seul", anomaly)):
            lf, _ = lift(sc, kk7_pos, valid, cov)
            row.append(f"{name} {lf:4.2f}" if lf else f"{name}   n/a")
        print("  ".join(row))

    if a.sweep:
        # On rapporte le LIFT, pas le F1. Le F1 récompense l'étalement :
        # mesuré sur la Maurienne, il plafonne à 0,075 pour TOUT réglage
        # couvrant ~38 % de la carte, donc il ne départage rien et pousse
        # dans le mauvais sens. Pour un outil consulté avant de voler, la
        # question n'est pas « attrape-t-on tout kk7 » mais « quand on
        # allume, a-t-on raison ».
        #
        # ⚠️ ON NE BALAYE QUE GATE_LO, ET C'EST UN RÉSULTAT, PAS UN RACCOURCI.
        # Dans ThermalGridLayer, un pixel est peint dès que `g > 0`, donc dès
        # que `anomaly > GATE_LO`. GATE_HI ne fait que régler la VITESSE du
        # dégradé d'opacité entre les deux seuils : il ne change ni la
        # surface allumée, ni le nombre de pixels d'accord avec kk7. Un
        # balayage 2D produit donc des lignes rigoureusement identiques par
        # valeur de LO — ce qui donne l'illusion d'explorer deux réglages
        # alors qu'un seul décide de quoi que ce soit.
        #
        # Conséquence pratique : si le rendu est « trop plein », c'est
        # GATE_LO qu'il faut monter. Toucher GATE_HI ne fera que pâlir ce
        # qui est déjà affiché.
        print("\n── Balayage GATE_LO (seul seuil qui décide de la couverture) ─")
        base = kk7_pos[valid].mean()
        print(f"   taux de base kk7 sur le domaine : {base:.2%}")
        for lo in (1.00, 1.02, 1.04, 1.06, 1.08, 1.10, 1.15,
                   1.20, 1.25, 1.30, 1.40, 1.50, 1.65):
            sel = (ww >= THERMAL_MIN_WSTAR) & (anomaly > lo) & valid
            if sel.sum() < 100:
                print(f"   LO {lo:.2f}   — moins de 100 px allumés, non conclusif")
                continue
            inter = (sel & kk7_pos).sum()
            prec, rec = inter / sel.sum(), inter / max(1, kk7_pos.sum())
            cov = sel.sum() / valid.sum()
            flag = "  <- actuel" if abs(lo - a.gate_lo) < 1e-9 else ""
            print(f"   LO {lo:.2f}  lift {prec/base:4.2f}  préc {prec:6.1%}  "
                  f"rapp {rec:6.1%}  couv {cov:6.1%}{flag}")
        print("\n   ⚠️ Ne PAS recopier mécaniquement la meilleure ligne. Un lift élevé")
        print("   sur une couverture de 2 % peut ne concerner qu'une poignée de")
        print("   crêtes, et kk7 lui-même surreprésente les abords de décollage.")
        print("   Ce tableau sert à cadrer un arbitrage, pas à le trancher seul.")

    print("\n── Rappel de ce que ces chiffres ne disent pas ────────────")
    print("   kk7 = climatologie de vols réels, pas vérité terrain. Ses biais")
    print("   connus (abords de déco surreprésentés, vide = personne n'a volé,")
    print("   toutes conditions confondues) sont dans l'écart mesuré ci-dessus.")
    print(f"   Cache local : {CACHE} (supprimable, rien n'est redistribué)\n")


if __name__ == "__main__":
    main()
