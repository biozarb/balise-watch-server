#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  tools/purge_pi_grille_orphans.py — ramasser les orphelins de
#            « agrume/pi/grille/ » que le garde-fou R2 a NOMMÉS
#                                                       (08/09/2026)
#
#  ⚠️ CE SCRIPT NE CHERCHE PAS LES ORPHELINS, IL LES REÇOIT. C'est
#  `tools/audit_r2.py` (la jauge, lecture seule, tournée chaque nuit)
#  qui fait le rapprochement bucket ↔ index et les imprime un par un.
#  Ici on ne relance donc AUCUN `ListObjects` : on prend les clés en
#  argument, et tout le travail est de refuser de supprimer autre chose.
#
#  ⛔ POURQUOI IL EXISTE. Deux fois déjà (12-13/08 : 18 orphelins,
#  24 Mo ; 07-08/09 : 3 orphelins, 10 Mo) il a fallu nettoyer à la main,
#  et la première fois le script préparé n'a jamais été posé dans le
#  dépôt — le pont était tombé en fin de session. Un nettoyage qui
#  n'existe qu'en mémoire d'une session est un nettoyage qu'il faudra
#  réinventer, sous pression, la fois suivante.
#
#  ⛔ CE QUI EST DÉFINITIF DANS LE MÊME BUCKET, ET SOUS LA MÊME RACINE :
#  `agrume/pi/colonnes/` — l'archive des colonnes PI, irremplaçable (la
#  rétention du portail est de 4,25 jours). Une purge qui s'y égarerait
#  ne se rattraperait pas. D'où le garde-fou de préfixe, et le refus
#  explicite, nommé, de cette racine-là.
#
#  ⚠️ `DeleteObject` RÉUSSIT SUR UNE CLÉ ABSENTE. Sans le `head` d'avant
#  ET d'après, « supprimé » et « n'a jamais existé » sont
#  indistinguables — c'est la leçon du 16/08, et c'est pour ça que ce
#  script fait deux fois le tour.
#
#  Usage (depuis balise-watch-server/, sur le VPS) :
#     set -a; . ~/.balise-watch-agrume-r2.env; set +a          # ← ÉCRIT
#     python3 tools/purge_pi_grille_orphans.py CLE [CLE …]     # à blanc
#     APPLY=1 python3 tools/purge_pi_grille_orphans.py CLE […]  # pour de vrai
#
#  ⛔ LE JETON. Mesuré le 13/08, opération par opération : le jeton
#  ORDINAIRE (`~/.balise-watch-r2.env`) rend 403 sur Get, List ET
#  Delete — il ne sait qu'écrire. Celui de `~/.balise-watch-agrume-r2.env`
#  (`balise-watch-agrume-pi-vps`) sait les quatre. C'est celui-là qu'il
#  faut sourcer, et le script le vérifie plutôt que de le supposer.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import datetime as dt

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
sys.path.insert(0, os.path.join(os.path.dirname(ICI), "agrume"))

APPLY = os.environ.get("APPLY") == "1"

#: Le seul préfixe où ce script a le droit de supprimer.
PREFIXE = "agrume/pi/grille/"
#: ⛔ Nommé pour être refusé, pas seulement « non autorisé ». Un refus
#: par omission ne se relit pas ; un refus par nom, si.
INTERDIT = "agrume/pi/colonnes/"
#: Frein de masse. Les deux incidents connus ont produit 18 et 3 clés.
#: Au-delà de 30, ce n'est plus un résidu : c'est autre chose, et il
#: faut comprendre avant de supprimer.
MAX_CLES = 30
#: ⚠️ FENÊTRE DE PUBLICATION EN VOL (motif du 17/08). Un run publie ses
#: OBJETS puis son INDEX ; entre les deux, ses objets ressemblent trait
#: pour trait à des orphelins. Un objet plus jeune que ça n'est donc
#: jamais un orphelin sûr — la reconstitution du 17/08 mesurait une
#: fenêtre d'UNE HEURE.
AGE_MINIMUM_H = 3


def _client(bucket):
    import boto3                                          # noqa: PLC0415
    from botocore.config import Config                    # noqa: PLC0415
    for v in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        if not os.environ.get(v):
            sys.exit(f"⛔ {v} manquante — sourcer "
                     f"~/.balise-watch-agrume-r2.env (le jeton ordinaire "
                     f"ne sait QU'ÉCRIRE : 403 sur get/list/delete).")
    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}"
                     f".r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(retries={"max_attempts": 1, "mode": "standard"}),
    ), bucket


def _head(cli, bucket, cle):
    """(existe, octets, date) — sans lever. ⚠️ C'est la SEULE façon de
    distinguer « supprimé » de « n'a jamais existé »."""
    try:
        r = cli.head_object(Bucket=bucket, Key=cle)
        return True, r.get("ContentLength", 0), r.get("LastModified")
    except Exception:                                      # noqa: BLE001
        return False, 0, None


def _reclamees(cli, bucket, cle_index):
    """Toutes les clés que l'index revendique — `runs[].cles` ET
    `restes`. ⚠️ Les `restes` comptent : une clé qui y figure est une
    suppression DÉJÀ programmée, que le prochain run fera. La reprendre
    ici doublerait le travail sans rien gagner."""
    import json                                            # noqa: PLC0415
    r = cli.get_object(Bucket=bucket, Key=cle_index)
    idx = json.loads(r["Body"].read())
    dedans = set(idx.get("restes") or [])
    for e in idx.get("runs") or []:
        dedans.update(e.get("cles") or [])
    return dedans, idx


def main(argv=None):
    cles = list(argv if argv is not None else sys.argv[1:])
    if not cles:
        sys.exit(__doc__ or "usage : purge_pi_grille_orphans.py CLE [CLE …]")

    from pi import CLE_INDEX_GRILLE                        # noqa: PLC0415

    # ── 1. Garde-fous de forme, AVANT tout appel réseau ───────────────
    if len(cles) > MAX_CLES:
        sys.exit(f"⛔ {len(cles)} clés demandées, frein de masse à "
                 f"{MAX_CLES}. Ce n'est plus un résidu : comprendre "
                 f"d'abord.")
    intruses = [c for c in cles if not c.startswith(PREFIXE)]
    if intruses:
        sys.exit(f"⛔ purge refusée : {len(intruses)} clé(s) hors de "
                 f"{PREFIXE!r} — {intruses[:3]}")
    egarees = [c for c in cles if c.startswith(INTERDIT)]
    if egarees:
        sys.exit(f"⛔⛔ purge refusée : {INTERDIT!r} est l'archive "
                 f"DÉFINITIVE des colonnes PI. {egarees[:3]}")
    if len(set(cles)) != len(cles):
        sys.exit("⛔ doublons dans la liste — la corriger plutôt que de "
                 "compter deux fois la même suppression.")

    bucket = os.environ.get("AGRUME_BUCKET") or os.environ.get(
        "R2_BUCKET") or "balise-watch-grids"
    cli, bucket = _client(bucket)
    print(f"bucket : {bucket} · {len(cles)} clé(s) candidate(s) · "
          + ("APPLY" if APPLY else "À BLANC (APPLY=1 pour supprimer)"))

    # ── 2. L'index AVANT : aucune de ces clés ne doit être réclamée ───
    reclamees, _ = _reclamees(cli, bucket, CLE_INDEX_GRILLE)
    servies = [c for c in cles if c in reclamees]
    if servies:
        sys.exit(f"⛔ purge refusée : {len(servies)} clé(s) sont RÉCLAMÉES "
                 f"par l'index — elles sont en service, ou déjà "
                 f"programmées à la purge du prochain run. {servies[:3]}")

    # ── 3. `head` d'avant : exister, et être assez vieux ──────────────
    maintenant = dt.datetime.now(dt.timezone.utc)
    a_supprimer, octets = [], 0
    for c in cles:
        existe, taille, date = _head(cli, bucket, c)
        if not existe:
            print(f"  ⓘ {c} — ABSENTE du bucket : rien à supprimer "
                  f"(⚠️ `DeleteObject` aurait quand même « réussi »)")
            continue
        age_h = (maintenant - date).total_seconds() / 3600 if date else 1e9
        if age_h < AGE_MINIMUM_H:
            print(f"  ⛔ {c} — {age_h:.1f} h seulement : un run publie ses "
                  f"OBJETS puis son INDEX, et entre les deux ses objets "
                  f"ressemblent à des orphelins (motif du 17/08). REFUSÉE.")
            continue
        a_supprimer.append(c)
        octets += taille
        print(f"  ✓ {c} — {taille / 1e6:.1f} Mo, {age_h:.0f} h")

    if not a_supprimer:
        print("rien à supprimer.")
        return 0
    print(f"→ {len(a_supprimer)} clé(s), {octets / 1e9:.3f} Go")

    if not APPLY:
        print("À BLANC — rien n'a été supprimé. Relancer avec APPLY=1.")
        return 0

    # ── 4. L'index UNE SECONDE FOIS, juste avant de supprimer ─────────
    # ⚠️ Un run publié PENDANT les `head` ci-dessus aurait réclamé ces
    # clés entre-temps. La fenêtre est de quelques secondes, mais elle
    # est exactement celle du faux positif du 17/08, en plus court.
    reclamees2, _ = _reclamees(cli, bucket, CLE_INDEX_GRILLE)
    revenues = [c for c in a_supprimer if c in reclamees2]
    if revenues:
        sys.exit(f"⛔ ARRÊT : {len(revenues)} clé(s) sont devenues "
                 f"réclamées pendant ce contrôle — un run a publié. "
                 f"{revenues[:3]}")

    # ── 5. Supprimer, puis VÉRIFIER ───────────────────────────────────
    restants = []
    for c in a_supprimer:
        cli.delete_object(Bucket=bucket, Key=c)
        existe, _, _ = _head(cli, bucket, c)
        print(("  ✅ supprimée : " if not existe
               else "  ⛔ TOUJOURS LÀ : ") + c)
        if existe:
            restants.append(c)
    print(f"\n{len(a_supprimer) - len(restants)}/{len(a_supprimer)} "
          f"supprimée(s), {octets / 1e9:.3f} Go rendus.")
    if restants:
        print("⛔ certaines clés sont toujours là — relancer, ou vérifier "
              "les droits du jeton (Object Read & Write requis).")
        return 1
    print("⇒ relancer `tools/audit_r2.py` pour confirmer « tout est "
          "réclamé » des deux côtés.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
