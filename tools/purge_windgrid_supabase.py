#!/usr/bin/env python3
"""
Purge INTÉGRALE du bucket Supabase Storage `wind-grid`, après la bascule
des 4 chaînes de grilles vers Cloudflare R2 (03/08/2026).

À ne pas confondre avec `purge_windgrid_orphans.py`, qui retire les tuiles
devenues mortes d'un bucket ENCORE EN SERVICE (BBOX réduite, niveau retiré).
Ici le bucket entier n'est plus lu par personne : `arome-wind`,
`arome-thermal`, `arpege-thermal` et `arome-gustfront` écrivent sur
`balise-watch-grids`, et le frontend lit `VITE_WIND_GRID_BASE_URL`.

⚠️ NE TOUCHE JAMAIS `isobars`. Ce bucket sert encore les pilotes : sa
bascule demande 72 h de double écriture (cf. TODO, chantier R2). Le nom du
bucket est en dur, et un garde-fou refuse tout autre nom.

GARDE-FOU PRINCIPAL — la fraîcheur. Le script relève `updated_at` sur tous
les objets et REFUSE de supprimer si l'un d'eux est postérieur à
`CUTOFF_UTC`. Un objet frais signifierait qu'une chaîne écrit encore ici,
donc que la bascule n'est pas ce qu'on croit — et supprimer sous une
chaîne vivante ferait disparaître un calque en production. Relevé du
05/08 : la dernière écriture Supabase date du 03/08 12:44 UTC.

Pourquoi vider et non supprimer le bucket : un bucket vide ne coûte rien et
garde sa politique publique et son CORS. Recréer un bucket, c'est risquer
de rater un réglage — et c'est exactement ce qui avait vidé tous les
calques en HTTP 200 le 03/08 (cf. BUGS.md).

⚠️ APRÈS CETTE PURGE, LE RETOUR ARRIÈRE VERS SUPABASE N'EXISTE PLUS.
Il faudrait rebasculer `STORAGE_BACKEND_*=supabase` et attendre 8 runs.

⚠️ DRY_RUN PAR DÉFAUT — rien n'est supprimé sans APPLY=1.

Usage (depuis balise-watch-server/) :
    set -a && . ./.env && set +a && python3 tools/purge_windgrid_supabase.py
    set -a && . ./.env && set +a && APPLY=1 python3 tools/purge_windgrid_supabase.py
"""
import os, json, sys, urllib.request, urllib.error
from datetime import datetime, timezone
from collections import defaultdict

SB_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
APPLY = os.environ.get("APPLY") == "1"
BUCKET = "wind-grid"          # EN DUR, volontairement. Cf. garde-fou ci-dessous.
CUTOFF_UTC = datetime(2026, 8, 3, 14, 0, tzinfo=timezone.utc)
PAGE, BATCH = 1000, 200

if not (SB_URL and SB_KEY):
    raise SystemExit("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants — lance avec : "
                     "set -a && . ./.env && set +a && python3 tools/purge_windgrid_supabase.py")

if BUCKET != "wind-grid":
    raise SystemExit("Ce script ne purge QUE `wind-grid`. `isobars` sert encore "
                     "les pilotes, `balise-watch-packs` est sur R2.")

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


def parse_ts(s):
    """`updated_at` Supabase : ISO 8601 en Z. Illisible -> None, et un None
    fait échouer le garde-fou de fraîcheur plutôt que de le contourner."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def walk(prefix=""):
    """{nom: (taille, updated_at)} récursif sous un préfixe."""
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
                size = int((row.get("metadata") or {}).get("size") or 0)
                out[name] = (size, parse_ts(row.get("updated_at")))
        if len(rows) < PAGE:
            return out
        offset += PAGE


def main():
    print(f"\nPurge INTÉGRALE de `{BUCKET}` (Supabase) — mode : "
          f"{'APPLIQUÉ (suppression réelle)' if APPLY else 'DRY_RUN (rien ne sera supprimé)'}")

    objets = walk()
    if not objets:
        print("\nBucket déjà vide — rien à faire.\n")
        return 0

    total = sum(s for s, _ in objets.values())

    # ── Répartition, pour comparer au relevé d'audit ──────────────────
    par_prefixe = defaultdict(lambda: [0, 0])
    for name, (size, _) in objets.items():
        pref = "/".join(name.split("/")[:-1]) or "(racine)"
        par_prefixe[pref][0] += size
        par_prefixe[pref][1] += 1
    print()
    for pref, (size, n) in sorted(par_prefixe.items(), key=lambda kv: -kv[1][0]):
        print(f"  {human(size):>12}   {n:>4} obj  {pref}")
    print(f"  {'-' * 46}\n  {human(total):>12}   {len(objets):>4} obj  TOTAL")

    # ── GARDE-FOU : aucune écriture postérieure à la bascule ──────────
    illisibles = [n for n, (_, ts) in objets.items() if ts is None]
    frais = sorted(((ts, n) for n, (_, ts) in objets.items()
                    if ts is not None and ts > CUTOFF_UTC), reverse=True)
    dernier = max((ts for _, ts in objets.values() if ts is not None), default=None)

    print(f"\nDernière écriture Supabase : "
          f"{dernier.isoformat() if dernier else 'inconnue'}")
    print(f"Seuil de fraîcheur (bascule R2) : {CUTOFF_UTC.isoformat()}")

    if illisibles:
        raise SystemExit(
            f"\n⛔ PURGE ANNULÉE — {len(illisibles)} objet(s) sans `updated_at` "
            f"lisible (ex. {illisibles[0]}).\nLa fraîcheur ne peut pas être "
            f"prouvée : mieux vaut ne rien supprimer.")

    if frais:
        apercu = "\n".join(f"    {ts.isoformat()}  {n}" for ts, n in frais[:5])
        raise SystemExit(
            f"\n⛔ PURGE ANNULÉE — {len(frais)} objet(s) écrit(s) APRÈS la "
            f"bascule :\n{apercu}\n"
            f"Une chaîne écrit encore sur Supabase (STORAGE_BACKEND resté à "
            f"`supabase` ou `both` ?).\nSupprimer sous une chaîne vivante "
            f"éteindrait un calque en production. Vérifier les variables de "
            f"dépôt avant de réessayer.")

    print("✓ Aucun objet postérieur à la bascule — le bucket est bien figé.")

    if not APPLY:
        print(f"\n{'=' * 62}\nRÉCUPÉRABLE : {human(total)} en {len(objets)} objets"
              f"\nRelance avec APPLY=1 pour appliquer.\n{'=' * 62}\n")
        return 0

    names = sorted(objets)
    for i in range(0, len(names), BATCH):
        lot = names[i:i + BATCH]
        api(f"/storage/v1/object/{BUCKET}", {"prefixes": lot}, method="DELETE")
        print(f"    supprimé {min(i + BATCH, len(names))}/{len(names)}")

    reste = walk()
    print(f"\n{'=' * 62}")
    print(f"SUPPRIMÉ : {human(total)} en {len(objets)} objets")
    print(f"Reste dans `{BUCKET}` : {len(reste)} objet(s)"
          f"{' — ' + human(sum(s for s, _ in reste.values())) if reste else ''}")
    print("Le bucket est conservé (vide) : politique publique et CORS intacts.")
    print(f"{'=' * 62}\n")
    return 0 if not reste else 1


if __name__ == "__main__":
    sys.exit(main())
