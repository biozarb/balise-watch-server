#!/usr/bin/env python3
"""Banc hors ligne (07/09/2026) — refonte deux versions du calque isobares.
Sans réseau ni Storage : `omfiles`/`fsspec`/`storage` sont remplacés par
des stubs, `ingest.py` est importé tel quel, et on vérifie sur un champ
synthétique (dépression + anticyclone + bruit 0,1°) que :
  1. simplify_rdp conserve les extrémités et respecte la tolérance ;
  2. la version synoptique ne sort QUE des multiples de 4 hPa, sans
     fragment court, et pèse nettement moins que la détaillée ;
  3. les centres H/L retrouvent les deux vrais centres injectés.
Usage : python3 banc_synop_07-09.py (depuis ce dossier)."""
import sys, types, json, os
import numpy as np

# ── stubs des dépendances réseau/stockage ──────────────────────────────
for name in ("omfiles", "fsspec"):
    sys.modules[name] = types.ModuleType(name)
sys.modules["omfiles"].OmFileReader = object
stor = types.ModuleType("storage")
stor.Storage = object; stor.verifier_dimensionnement = lambda *a, **k: 0
stor.Abort = Exception; stor.CACHE_REECRIT = "x"; stor.CACHE_IMMUABLE = "y"
sys.modules["storage"] = stor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ingest  # noqa: E402

# ── champ synthétique : grille Europe 0,1° ─────────────────────────────
lat = np.linspace(72, 20, 521); lon = np.linspace(-32, 42, 741)
lon2d, lat2d = np.meshgrid(lon, lat)
rng = np.random.default_rng(7)
def bump(clon, clat, amp, sig):
    return amp * np.exp(-(((lon2d - clon) ** 2) + ((lat2d - clat) ** 2)) / (2 * sig ** 2))
p = 1013 - bump(-15, 55, 28, 7) + bump(10, 45, 18, 9) + rng.normal(0, 0.6, lon2d.shape)

# 1. RDP
seg = np.array([[0, 0], [1, 0.001], [2, 0], [3, 1], [4, 1.001], [5, 1]], float)
out = ingest.simplify_rdp(seg, 0.01)
assert (out[0] == seg[0]).all() and (out[-1] == seg[-1]).all(), "extrémités perdues"
assert out.tolist() == [[0, 0], [2, 0], [3, 1], [5, 1]], out.tolist()  # le Z, sans les 2 quasi-colinéaires
print("1. simplify_rdp ✔", out.tolist())

# 2. les deux versions
smooth = ingest.smooth_pressure(p)
detail = ingest.isobars_geojson(lon2d, lat2d, p)
synop = ingest.synop_geojson(lon2d, lat2d, smooth)
hpas = sorted({f["properties"]["hpa"] for f in synop["features"]})
assert all(h % ingest.SYNOP_STEP_HPA == 0 for h in hpas), hpas
for f in synop["features"]:
    assert ingest.seg_length_deg(np.array(f["geometry"]["coordinates"])) >= ingest.SYNOP_MIN_LENGTH_DEG - 0.05
sz = lambda g: len(json.dumps(g, separators=(",", ":")))
nd, ns = sz(detail), sz(synop)
print(f"2. détaillé {len(detail['features'])} lignes / {nd/1e3:.0f} Ko ; "
      f"synoptique {len(synop['features'])} lignes / {ns/1e3:.0f} Ko ; niveaux {hpas} ✔")
assert ns < nd / 3, "la version synoptique devrait peser bien moins"

# 3. centres
centers = ingest.find_centers(lon2d, lat2d, smooth)
L = [c for c in centers if c["kind"] == "L"]; H = [c for c in centers if c["kind"] == "H"]
assert L and abs(L[0]["lat"] - 55) < 1 and abs(L[0]["lon"] + 15) < 1, L
assert H and abs(H[0]["lat"] - 45) < 1 and abs(H[0]["lon"] - 10) < 1, H
print(f"3. centres ✔ L={L[0]} H={H[0]} (total {len(centers)})")
print("BANC OK")
