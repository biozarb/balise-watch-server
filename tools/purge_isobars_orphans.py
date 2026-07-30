#!/usr/bin/env python3
"""
Purge des objets orphelins du bucket Supabase Storage `isobars`.

POURQUOI (30/07/2026, dépassement de quota Storage) :
`arpege-isobars/ingest.py` nomme chaque geojson par échéance
(`{grille}/{iso}.json`), traite le passé comme IMMUABLE (skip-if-exists)
et ne supprime jamais rien. Le manifest ne liste que la fenêtre courante
(passé disponible chez Open-Meteo + prévision du run de référence), mais
tous les objets sortis de cette fenêtre restent dans le bucket : plus
jamais téléchargés par l'app, toujours facturés. Combiné au passage
LEVEL_STEP_HPA 5 -> 1 hPa du 24/07 (~5x plus lourd par fichier), c'est
la cause la plus probable de la croissance du Storage Size.

CE QUE FAIT CE SCRIPT : supprime, grille par grille, tout objet
`{grille}/*.json` dont l'échéance n'est PAS dans `{grille}/manifest.json`.
Le manifest lui-même est toujours préservé. Aucun objet listé par le
manifest n'est touché — donc zéro perte fonctionnelle côté app.

⚠️ DRY_RUN PAR DÉFAUT. Le script n'écrit rien tant que tu ne passes pas
   APPLY=1 explicitement. Lis la liste, puis relance avec APPLY=1.

Usage (depuis balise-watch-server/) :
    # 1) voir ce qui serait supprimé, sans rien toucher
    set -a && . ./.env && set +a && python3 tools/purge_isobars_orphans.py
    # 2) appliquer
    set -a && . ./.env && set +a && APPLY=1 python3 tools/purge_isobars_orphans.py

Option : MAX_AGE_H=72 pour purger EN PLUS les échéances passées plus
vieilles que 72 h même si elles sont encore dans le manifest (aligne le
storage sur la rétention 72 h décidée le 30/07 ; le prochain run
régénérera un manifest cohérent).
"""
import os, json, urllib.request, urllib.error, sys
from datetime import datetime, timezone, timedelta

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
APPLY = os.environ.get("APPLY") == "1"
MAX_AGE_H = int(os.environ.get("MAX_AGE_H", "0") or 0)
BUCKET = os.environ.get("ISOBARS_BUCKET", "isobars")
GRIDS = ("arpege_europe", "arpege_world")
PAGE = 1000
BATCH = 200          # taille des lots de suppression

if not (SB_URL and SB_KEY):
    raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants — "
                     "lance avec : set -a && . ./.env && set +a && python3 tools/purge_isobars_orphans.py")

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


def list_grid(grid):
    """{nom_objet: taille} pour un préfixe de grille (pas de sous-dossier
    dans ce bucket — les geojson sont directement sous `{grille}/`)."""
    out, offset = {}, 0
    while True:
        rows = api(f"/storage/v1/object/list/{BUCKET}", {
            "prefix": f"{grid}/", "limit": PAGE, "offset": offset,
            "sortBy": {"column": "name", "order": "asc"}})
        if not rows:
            return out
        for row in rows:
            if row.get("id") is None:      # pseudo-dossier, ignoré
                continue
            size = (row.get("metadata") or {}).get("size") or 0
            out[f"{grid}/{row['name']}"] = int(size)
        if len(rows) < PAGE:
            return out
        offset += PAGE


def read_manifest(grid):
    url = f"{SB_URL}/storage/v1/object/public/{BUCKET}/{grid}/manifest.json"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read())


def iso_of(obj, grid):
    """`arpege_europe/2026-07-30T06:00.json` -> datetime UTC, ou None."""
    stem = obj[len(grid) + 1:-5] if obj.endswith(".json") else None
    if not stem or stem == "manifest":
        return None
    try:
        return datetime.strptime(stem, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def main():
    mode = "APPLIQUE (suppression réelle)" if APPLY else "DRY_RUN (rien ne sera supprimé)"
    print(f"\nPurge orphelins `{BUCKET}` — mode : {mode}")
    if MAX_AGE_H:
        print(f"MAX_AGE_H={MAX_AGE_H} : les échéances passées plus vieilles "
              f"que {MAX_AGE_H} h seront purgées AUSSI, même si le manifest "
              f"les liste encore.")
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_H)) if MAX_AGE_H else None

    grand_dead, grand_n = 0, 0
    for grid in GRIDS:
        objects = list_grid(grid)
        if not objects:
            print(f"\n— {grid} : aucun objet, rien à faire.")
            continue
        man_path = f"{grid}/manifest.json"
        try:
            manifest = read_manifest(grid)
        except Exception as e:
            print(f"\n— {grid} : ⚠️ manifest illisible ({e}) — grille IGNORÉE "
                  f"(sans manifest fiable, on ne supprime rien).")
            continue

        live = {f"{grid}/{t}.json" for t in manifest.get("times", [])}
        live.add(man_path)

        doomed = []
        for obj in objects:
            if obj == man_path:
                continue                      # jamais le manifest
            if obj not in live:
                doomed.append((obj, "orphelin"))
                continue
            if cutoff:
                dt = iso_of(obj, grid)
                if dt and dt < cutoff:
                    doomed.append((obj, f"> {MAX_AGE_H}h"))

        dead = sum(objects[o] for o, _ in doomed)
        kept = sum(objects[o] for o in objects) - dead
        print(f"\n— {grid} : {len(objects)} objets ({human(sum(objects.values()))})")
        print(f"    à garder   : {len(objects) - len(doomed):>5} obj  {human(kept)}")
        print(f"    à supprimer: {len(doomed):>5} obj  {human(dead)}")
        for obj, why in sorted(doomed)[:8]:
            print(f"      - {obj}  ({why}, {human(objects[obj])})")
        if len(doomed) > 8:
            print(f"      … et {len(doomed) - 8} autres")

        grand_dead += dead
        grand_n += len(doomed)

        if doomed and APPLY:
            names = [o for o, _ in doomed]
            for i in range(0, len(names), BATCH):
                lot = names[i:i + BATCH]
                api(f"/storage/v1/object/{BUCKET}", {"prefixes": lot},
                    method="DELETE")
                print(f"    supprimé {min(i + BATCH, len(names))}/{len(names)}")

    print(f"\n{'=' * 60}")
    print(f"{'SUPPRIMÉ' if APPLY else 'RÉCUPÉRABLE'} : {human(grand_dead)} "
          f"en {grand_n} objets")
    if not APPLY and grand_n:
        print("Relance avec APPLY=1 pour appliquer.")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    sys.exit(main())
