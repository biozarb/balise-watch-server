#!/usr/bin/env python3
"""sonde_r2.py — regarder ce qu'il y a VRAIMENT dans le bucket.

    Écrit le 07/08/2026, au déploiement.

⚠️ POURQUOI CE N'EST PAS DU CONFORT. « Le service est `active` » ne dit
rien de l'archive : le 07/08, un run a annoncé « OK en 2s » alors que
`PutObject` rendait `AccessDenied` et que l'archive n'existait que sur le
disque du VPS. Et le 08/08, `localModels.ts` a passé 38 assertions au
vert avec une maille fausse et deux modèles manquants — parce que le
banc photographiait la table au lieu de la confronter au monde.

Cet outil ouvre l'objet, le décompresse et compte ce qu'il y a dedans.
La présence d'une clé ne prouve rien : un run interrompu laisse un
fichier gzip parfaitement valide, plus court.

    python3 sonde_r2.py                    # inventaire des deux buckets
    python3 sonde_r2.py --jour 2026-08-08  # + contenu de la journée dite

À lancer avec l'environnement chargé :
    set -a; . ~/.balise-watch-r2.env; set +a
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import os
import sys
from datetime import datetime, timedelta, timezone

BUCKET = os.environ.get("BW_MODEL_VERIF_BUCKET", "model-verif")
# Le bucket partagé des autres chaînes. On le regarde pour vérifier
# qu'on n'y a RIEN déversé : `collect.py` écrit des clés non préfixées
# (`fcst/`, `obs/`), et si l'écrasement de `R2_BUCKET` sautait un jour,
# c'est là qu'elles atterriraient.
BUCKET_VOISIN = os.environ.get("R2_BUCKET_VOISIN", "balise-watch-packs")


def client():
    try:
        import boto3
    except ImportError:
        sys.exit("boto3 absent — lancer avec /home/debian/venv-balise/bin/python3")
    for v in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        if not os.environ.get(v):
            sys.exit(f"{v} absente — `set -a; . ~/.balise-watch-r2.env; set +a`")
    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto")


def inventaire(c, bucket: str, prefixe: str = "", maxi: int = 40) -> int:
    from botocore.exceptions import ClientError
    try:
        r = c.list_objects_v2(Bucket=bucket, Prefix=prefixe, MaxKeys=maxi)
    except ClientError as e:
        print(f"── {bucket} : {e.response['Error']['Code']}")
        return -1
    n = r.get("KeyCount", 0)
    tronque = r.get("IsTruncated", False)
    print(f"── {bucket} : {n} objet(s){' (tronqué)' if tronque else ''}")
    total = 0
    for o in r.get("Contents", []):
        total += o["Size"]
        print(f"   {o['Size']:>10}  {o['LastModified']:%Y-%m-%d %H:%M}  {o['Key']}")
    if n:
        print(f"   → {total / 1024 / 1024:.2f} Mo")
    return n


def contenu(c, bucket: str, cle: str) -> None:
    """Ouvre l'objet et décrit ce qu'il porte."""
    from botocore.exceptions import ClientError
    print(f"\n── contenu de {cle}")
    try:
        o = c.get_object(Bucket=bucket, Key=cle)
    except ClientError as e:
        print(f"   ABSENT ({e.response['Error']['Code']})")
        return
    brut = gzip.decompress(o["Body"].read()).decode("utf-8").splitlines()
    print(f"   {len(brut)} lignes")
    if not brut:
        print("   ⚠️ objet VIDE — un gzip valide et sans contenu")
        return
    lignes = [json.loads(l) for l in brut]
    par_modele = collections.Counter(d.get("model") for d in lignes)
    # ⚠️ La clé est `station_id`, pas `station` : première version de
    # cette sonde comptait « 1 station » sur trois points, parce qu'elle
    # lisait un champ qui n'existe pas et que `None` se dédoublonne en un
    # seul élément. Une sonde qui se trompe de nom de champ ne se plaint
    # pas — elle rend un chiffre faux et rassurant.
    stations = {(d.get("source"), d.get("station_id")) for d in lignes}
    print(f"   {len(stations)} station(s), {len(par_modele)} modèle(s)")
    for m, k in sorted(par_modele.items(), key=lambda kv: (-kv[1], str(kv[0]))):
        print(f"     {k:>5}  {m}")
    print("   première ligne :")
    print("    ", json.dumps(lignes[0], ensure_ascii=False)[:500])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jour", default=None,
                    help="journée à ouvrir (AAAA-MM-JJ, défaut : aujourd'hui UTC)")
    ap.add_argument("--obs", action="store_true",
                    help="ouvrir l'archive d'observations au lieu des prévisions")
    args = ap.parse_args()

    c = client()
    inventaire(c, BUCKET)
    print()
    # ⚠️ On vérifie l'ABSENCE ici, pas la présence : aucune clé `fcst/`
    # ni `obs/` ne doit exister dans le bucket des packs.
    n_voisin = inventaire(c, BUCKET_VOISIN, prefixe="fcst/")
    if n_voisin > 0:
        print(f"   ❌ des clés `fcst/` traînent dans {BUCKET_VOISIN} — "
              f"l'écrasement de R2_BUCKET n'a pas eu lieu ce jour-là")
    elif n_voisin == 0:
        print(f"── {BUCKET_VOISIN} : aucune clé `fcst/` — rien n'a débordé")

    jour = args.jour or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    d = datetime.strptime(jour, "%Y-%m-%d")
    if args.obs:
        contenu(c, BUCKET, f"obs/{d:%Y/%m}/obs_{jour}.ndjson.gz")
    else:
        contenu(c, BUCKET, f"fcst/{d:%Y/%m}/fcst_{jour}.ndjson.gz")
    return 0


if __name__ == "__main__":
    sys.exit(main())
