#!/usr/bin/env python3
"""
Purge des objets orphelins du bucket Supabase Storage `wind-grid`.

CONTEXTE (30/07/2026) : pendant du script `purge_isobars_orphans.py`, pour
l'autre bucket. Contrairement à `isobars`, `wind-grid` est clé par TUILE
(`arome/sol/{lat}_{lon}.json`, `arpege/thermal/{lat}_{lon}.json`, …) donc
réécrit en place à chaque run : il est normalement stationnaire, et
abaisser `MAX_HOURS` ne crée AUCUN orphelin (mêmes chemins, fichiers
simplement plus légers).

En revanche, **réduire une BBOX en crée** : les tuiles qui sortent de la
nouvelle zone ne sont plus jamais réécrites et restent à vie. C'est le cas
après la réduction d'`arpege-thermal` du 30/07 (Europe entière 1026 tuiles
-> Ouest européen + arc alpin 228 tuiles), soit ~798 tuiles mortes.

Ce script supprime :
  1. les tuiles `arpege/thermal/` hors de la BBOX courante lue directement
     dans `arpege-thermal/ingest.py` (pas de constante dupliquée ici — si
     la BBOX rebouge, ce script suit tout seul) ;
  2. le préfixe `test/`, résidu de mise au point repéré à l'audit.

`manifest.json` n'est jamais candidat à la suppression, à aucun niveau.

⚠️ DRY_RUN PAR DÉFAUT — rien n'est supprimé sans APPLY=1.

Usage (depuis balise-watch-server/) :
    set -a && . ./.env && set +a && python3 tools/purge_windgrid_orphans.py
    set -a && . ./.env && set +a && APPLY=1 python3 tools/purge_windgrid_orphans.py
"""
import os, re, json, math, urllib.request, urllib.error, sys
from pathlib import Path

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
APPLY = os.environ.get("APPLY") == "1"
BUCKET = os.environ.get("WIND_GRID_BUCKET", "wind-grid")
PAGE, BATCH = 1000, 200

if not (SB_URL and SB_KEY):
    raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants — "
                     "lance avec : set -a && . ./.env && set +a && python3 tools/purge_windgrid_orphans.py")

HDRS = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json"}


def api(path, body=None, method=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(SB_URL + path, data=data, headers=HDRS,
                                 method=method or ("POST" if data else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        detail = e.read()[:300].decode("utf-8", "replace")
        raise SystemExit(f"HTTP {e.code} sur {path} — {detail}")


def human(n):
    for unit in ("o", "Ko", "Mo", "Go"):
        if n < 1024 or unit == "Go":
            return f"{n:,.1f} {unit}".replace(",", " ")
        n /= 1024


def read_bbox_from_ingest():
    """Lit la BBOX effective dans arpege-thermal/ingest.py plutôt que de la
    redéclarer ici — une constante dupliquée finit toujours par diverger, et
    dans ce script-ci une divergence se traduirait par des suppressions
    fausses."""
    src = (Path(__file__).resolve().parent.parent
           / "arpege-thermal" / "ingest.py").read_text(encoding="utf-8")
    m = re.search(r"^BBOX\s*=\s*dict\((.*?)\)\s*$", src, re.M)
    if not m:
        raise SystemExit("BBOX introuvable dans arpege-thermal/ingest.py — "
                         "purge annulée (mieux vaut ne rien supprimer).")
    vals = dict(re.findall(r"(lat|lon)(min|max)\s*=\s*(-?[\d.]+)",
                           m.group(1)) and
                [(a + b, float(c)) for a, b, c in
                 re.findall(r"(lat|lon)(min|max)\s*=\s*(-?[\d.]+)", m.group(1))])
    if set(vals) != {"latmin", "latmax", "lonmin", "lonmax"}:
        raise SystemExit(f"BBOX incomplète lue dans ingest.py : {vals} — purge annulée.")
    return vals


def walk(prefix):
    """{nom: taille} récursif sous un préfixe."""
    out, offset = {}, 0
    while True:
        rows = api(f"/storage/v1/object/list/{BUCKET}", {
            "prefix": prefix, "limit": PAGE, "offset": offset,
            "sortBy": {"column": "name", "order": "asc"}})
        if not rows:
            return out
        for row in rows:
            name = f"{prefix}{row['name']}"
            if row.get("id") is None:
                out.update(walk(name + "/"))
            else:
                out[name] = int((row.get("metadata") or {}).get("size") or 0)
        if len(rows) < PAGE:
            return out
        offset += PAGE


TILE_DEG = 2
_TILE_RE = re.compile(r"/(-?\d+)_(-?\d+)\.json$")


def main():
    print(f"\nPurge orphelins `{BUCKET}` — mode : "
          f"{'APPLIQUE (suppression réelle)' if APPLY else 'DRY_RUN (rien ne sera supprimé)'}")

    bbox = read_bbox_from_ingest()
    print(f"BBOX arpege-thermal lue dans ingest.py : "
          f"lat {bbox['latmin']}..{bbox['latmax']}, lon {bbox['lonmin']}..{bbox['lonmax']}")

    doomed = {}

    # ── 1. tuiles arpege/thermal hors BBOX ────────────────────────────
    thermal = walk("arpege/thermal/")
    lat_lo = math.floor(bbox["latmin"] / TILE_DEG) * TILE_DEG
    lat_hi = math.floor(bbox["latmax"] / TILE_DEG) * TILE_DEG
    lon_lo = math.floor(bbox["lonmin"] / TILE_DEG) * TILE_DEG
    lon_hi = math.floor(bbox["lonmax"] / TILE_DEG) * TILE_DEG
    inside = 0
    for name, size in thermal.items():
        if name.endswith("/manifest.json"):
            continue
        m = _TILE_RE.search(name)
        if not m:
            continue                      # forme inattendue : on ne touche pas
        tlat, tlon = int(m.group(1)), int(m.group(2))
        if lat_lo <= tlat <= lat_hi and lon_lo <= tlon <= lon_hi:
            inside += 1
        else:
            doomed[name] = size
    print(f"\n— arpege/thermal : {len(thermal)} objets, "
          f"{inside} tuiles dans la BBOX, {len(doomed)} hors BBOX")

    # ── 2. préfixe test/ ──────────────────────────────────────────────
    test = walk("test/")
    if test:
        print(f"— test/ : {len(test)} objet(s) résiduel(s) "
              f"({human(sum(test.values()))}) — mise au point, à supprimer")
        doomed.update(test)

    total = sum(doomed.values())
    print(f"\n  à supprimer : {len(doomed)} objets  {human(total)}")
    for name in sorted(doomed)[:8]:
        print(f"    - {name}  ({human(doomed[name])})")
    if len(doomed) > 8:
        print(f"    … et {len(doomed) - 8} autres")

    if doomed and APPLY:
        names = sorted(doomed)
        for i in range(0, len(names), BATCH):
            lot = names[i:i + BATCH]
            api(f"/storage/v1/object/{BUCKET}", {"prefixes": lot}, method="DELETE")
            print(f"    supprimé {min(i + BATCH, len(names))}/{len(names)}")

    print(f"\n{'=' * 60}")
    print(f"{'SUPPRIMÉ' if APPLY else 'RÉCUPÉRABLE'} : {human(total)} "
          f"en {len(doomed)} objets")
    if not APPLY and doomed:
        print("Relance avec APPLY=1 pour appliquer.")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    sys.exit(main())
