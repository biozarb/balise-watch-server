#!/usr/bin/env python3
"""
Audit du Supabase Storage — taille réelle par bucket et par préfixe.

Contexte (30/07/2026) : mail Supabase « Fair Use Policy », Storage Size
mesuré à 3,23 Go pour 1 Go inclus dans le Free Plan, restrictions
annoncées au 29/08/2026. Ce script sert à SAVOIR où est le volume avant
de rogner quoi que ce soit — aucune des 4 chaînes d'ingestion
(arome-wind, arome-thermal, arpege-isobars, arpege-thermal) ne contient
un seul `delete`, donc l'hypothèse de travail est une accumulation
silencieuse d'objets orphelins.

⚠️ LECTURE SEULE — ce script ne supprime RIEN. La purge est dans
   `purge_isobars_orphans.py`, séparé volontairement.

Usage (depuis balise-watch-server/, .env chargé) :
    set -a && . ./.env && set +a && python3 tools/audit_storage.py

Variables d'environnement : SUPABASE_URL, SUPABASE_SERVICE_KEY
(la service_role est nécessaire : l'API de listing n'est pas publique,
même sur un bucket public).
"""
import os, json, urllib.request, urllib.error, sys
from collections import defaultdict

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
if not (SB_URL and SB_KEY):
    raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants — "
                     "lance avec : set -a && . ./.env && set +a && python3 tools/audit_storage.py")

HDRS = {"apikey": SB_KEY, "Authorization": f"Bearer {SB_KEY}",
        "Content-Type": "application/json"}
PAGE = 1000          # limite max de l'API storage list


def api(path, body=None, method=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(SB_URL + path, data=data, headers=HDRS,
                                 method=method or ("POST" if data else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        detail = e.read()[:300].decode("utf-8", "replace")
        raise SystemExit(f"HTTP {e.code} sur {path} — {detail}")


def human(n):
    for unit in ("o", "Ko", "Mo", "Go"):
        if n < 1024 or unit == "Go":
            return f"{n:,.1f} {unit}".replace(",", " ")
        n /= 1024


def walk(bucket, prefix=""):
    """Liste récursivement un bucket. L'API storage `list` est
    répertoire-par-répertoire : un objet sans `id` est un pseudo-dossier
    (préfixe), un objet avec `id` est un vrai fichier dont la taille est
    dans metadata.size. Pagination par `offset` (limite 1000)."""
    offset = 0
    while True:
        rows = api(f"/storage/v1/object/list/{bucket}", {
            "prefix": prefix, "limit": PAGE, "offset": offset,
            "sortBy": {"column": "name", "order": "asc"}})
        if not rows:
            return
        for row in rows:
            name = f"{prefix}{row['name']}"
            if row.get("id") is None:               # pseudo-dossier
                yield from walk(bucket, name + "/")
            else:
                size = (row.get("metadata") or {}).get("size") or 0
                yield name, int(size), row.get("updated_at") or ""
        if len(rows) < PAGE:
            return
        offset += PAGE


def prefix_key(name, depth=2):
    """Regroupe `arpege_europe/2026-07-30T06:00.json` -> `arpege_europe`,
    `arome/thermal/40_6.json` -> `arome/thermal`. Depth = nb de segments
    de chemin conservés (le dernier segment est le fichier)."""
    parts = name.split("/")
    return "/".join(parts[:-1][:depth]) or "(racine)"


def main():
    buckets = api("/storage/v1/bucket")
    print(f"\n{len(buckets)} bucket(s) : "
          + ", ".join(f"{b['name']}{' [public]' if b.get('public') else ''}"
                      for b in buckets))

    grand_total, grand_count = 0, 0
    per_bucket = {}

    for b in buckets:
        name = b["name"]
        print(f"\n{'=' * 66}\nBUCKET « {name} »\n{'=' * 66}")
        by_prefix = defaultdict(lambda: [0, 0])     # [octets, nb]
        objects = {}                                 # name -> size
        try:
            for obj, size, _ in walk(name):
                objects[obj] = size
                k = prefix_key(obj)
                by_prefix[k][0] += size
                by_prefix[k][1] += 1
        except SystemExit as e:
            print(f"  ⚠️ listing impossible : {e}")
            continue

        total = sum(objects.values())
        per_bucket[name] = (total, len(objects), objects)
        grand_total += total
        grand_count += len(objects)

        for k, (octets, n) in sorted(by_prefix.items(), key=lambda kv: -kv[1][0]):
            share = 100 * octets / total if total else 0
            print(f"  {human(octets):>12}  {share:5.1f}%  {n:>6} obj  {k}")
        print(f"  {'-' * 60}\n  {human(total):>12}   100%  {len(objects):>6} obj  TOTAL {name}")

    print(f"\n{'#' * 66}")
    print(f"TOTAL STORAGE : {human(grand_total)} en {grand_count} objets "
          f"(quota Free Plan : 1 Go)")
    print(f"{'#' * 66}")

    # ── Orphelins isobares : objets présents en storage mais ABSENTS du
    # manifest lu par le client. `arpege-isobars/ingest.py` nomme ses
    # geojson par échéance (`{grille}/{iso}.json`), les traite comme
    # immuables (skip-if-exists) et ne purge jamais — donc tout ce que le
    # manifest ne liste plus est du volume mort, jamais téléchargé par
    # l'app, mais facturé.
    if "isobars" in per_bucket:
        print("\n── Orphelins du bucket `isobars` "
              "(en storage mais absents du manifest) ──")
        _, _, objects = per_bucket["isobars"]
        for grid in ("arpege_europe", "arpege_world"):
            man_path = f"{grid}/manifest.json"
            if man_path not in objects:
                print(f"  {grid}: pas de manifest — grille jamais générée ?")
                continue
            try:
                url = f"{SB_URL}/storage/v1/object/public/isobars/{man_path}"
                with urllib.request.urlopen(url, timeout=30) as r:
                    manifest = json.loads(r.read())
            except Exception as e:
                print(f"  {grid}: manifest illisible ({e})")
                continue
            live = {f"{grid}/{t}.json" for t in manifest.get("times", [])}
            live.add(man_path)
            mine = {k for k in objects if k.startswith(grid + "/")}
            orphans = mine - live
            dead = sum(objects[o] for o in orphans)
            alive = sum(objects[o] for o in (mine & live))
            print(f"  {grid}: {len(mine)} objets, {human(alive)} utiles "
                  f"| {len(orphans)} ORPHELINS, {human(dead)} récupérables")
            if orphans:
                ex = sorted(orphans)[:3]
                print(f"     ex. {', '.join(ex)}"
                      + (" …" if len(orphans) > 3 else ""))
        print("\n  → purge : python3 tools/purge_isobars_orphans.py "
              "(DRY_RUN par défaut)")


if __name__ == "__main__":
    sys.exit(main())
