#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/sonde_r2.py — de quels droits dispose VRAIMENT le jeton R2 ?
#                                                        (10/08/2026)
#
#  ⚠️ POURQUOI CE FICHIER EXISTE. Le produit B (étape 6 du lot H) est le
#  premier produit du projet à SUPPRIMER : il ne garde que les trois
#  derniers runs. Or le projet a déjà été mordu une fois par un droit R2
#  supposé — le piège nº 9 du lot : « le jeton R2 du VPS ne lit pas le
#  bucket wind-grid », découvert en lisant les logs d'un run, pas en
#  lisant une documentation.
#
#  Écrire une purge sur l'hypothèse que `DeleteObject` est accordé, c'est
#  se préparer à un produit qui grossit en silence pendant des semaines :
#  la purge journalise son échec et laisse le run VERT (c'est le
#  correctif du 30/07, et il est juste), donc personne ne verrait rien
#  avant la facture ou le palier. **On sonde d'abord.**
#
#  ── CE QUE LA SONDE VÉRIFIE, ET DANS CET ORDRE ───────────────────────
#    1. PutObject   — écrire une clé jetable sous un préfixe dédié
#    2. GetObject   — la relire, et vérifier que les OCTETS correspondent
#    3. DeleteObject — la supprimer
#    4. GetObject   — ⚠️ LE SEUL VRAI TEST : relire APRÈS suppression et
#                     exiger un 404. Un `delete_object` qui rend 204 sans
#                     rien supprimer est un succès apparent ; seule
#                     l'absence constatée prouve la suppression.
#
#  ── CE QU'ELLE NE VÉRIFIE PAS, ET C'EST VOULU ────────────────────────
#  ⛔ `ListObjects`. Non par oubli : la purge du produit B ne listera
#  JAMAIS le bucket. `HeadObject` et `ListObjects` sont facturés Class A
#  (`storage.py::_R2.exists` lève d'ailleurs plutôt que de les laisser
#  passer), et le projet a déjà sa réponse à ce besoin — relire un
#  manifeste à clé connue, 1 GetObject Class B. La purge tiendra donc un
#  index à clé fixe, et le droit de lister ne lui manquera pas.
#
#  Usage (dans l'Action, avec les secrets du dépôt) :
#      python3 agrume/sonde_r2.py
#      python3 agrume/sonde_r2.py --prefixe agrume/_sonde
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

from storage import CACHE_REECRIT, DRY_RUN, Abort, Storage  # noqa: E402

# ⚠️ Un préfixe qui ne ressemble à AUCUN produit. Si cette sonde laissait
# un jour un objet derrière elle (échec entre l'écriture et la
# suppression), il doit être identifiable d'un coup d'œil comme un
# déchet de diagnostic, et ne jamais tomber dans le champ d'une purge.
PREFIXE = "agrume/_sonde"


def sonder(prefixe=PREFIXE, log=print):
    """Renvoie (verdict_ok, details). Ne lève pas : le diagnostic doit
    aller au bout et dire TOUT ce qu'il a trouvé, pas s'arrêter au
    premier refus.

    ⚠️⚠️ SAUF SOUS `DRY_RUN`, ET C'EST LA PREMIÈRE CHOSE QUE CETTE SONDE
    A APPRISE — sur elle-même. Écrite sans ce garde-fou, lancée avec
    `DRY_RUN=1` pour un simple test d'import, elle a annoncé « la clé a
    DISPARU — la purge fonctionnera » : `Storage.put` ne monte rien,
    `Storage.get` rend `None` sans appeler personne, et l'absence
    fabriquée par le mode à blanc se lit exactement comme une
    suppression réussie.
    ⛔ Une sonde dont tout l'objet est d'OBSERVER LE RÉEL ne peut pas
    tourner à blanc. C'est le même faux vert que celui du 10/08 sur les
    deux fenêtres d'orographie : un contrôle sur zéro point rend un ✓
    qui ne dit rien.
    """
    if DRY_RUN:
        raise Abort(
            "DRY_RUN=1 — cette sonde ne mesure RIEN à blanc, et son "
            "résultat serait un faux vert (`get` rend None sans appeler "
            "R2, ce qui est indiscernable d'une suppression réussie). "
            "La lancer avec les vrais identifiants, ou pas du tout.")
    marque = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cle = f"{prefixe}/droits-{marque}.txt"
    # Un contenu non trivial : deux octets identiques passeraient un test
    # de relecture même si le stockage rendait autre chose.
    corps = (f"sonde de droits AGRUME · {marque} · "
             f"run {os.environ.get('GITHUB_RUN_ID', 'local')}\n").encode()

    d = dict(cle=cle, put=None, get=None, get_identique=None,
             delete=None, absent_apres_delete=None)
    store = Storage("agrume-sonde-r2", "AGRUME_BUCKET", "wind-grid",
                    plafond=4)

    # ── 1. écrire ─────────────────────────────────────────────────────
    try:
        store.put(cle, corps, cache_control=CACHE_REECRIT,
                  content_type="text/plain")
        d["put"] = True
        log(f"  ✅ PutObject   : {cle}")
    except Exception as e:                                  # noqa: BLE001
        d["put"] = False
        log(f"  ⛔ PutObject   : {type(e).__name__} — {e}")
        log("     → sans droit d'écriture, l'ingestion elle-même ne "
            "fonctionne pas : ce n'est pas un problème de purge.")
        return False, d

    # ── 2. relire ─────────────────────────────────────────────────────
    try:
        relu = store.get(cle)
        d["get"] = relu is not None
        d["get_identique"] = relu == corps
        if relu is None:
            log("  ⛔ GetObject   : la clé vient d'être écrite et revient "
                "VIDE — ce n'est pas un droit qui manque, c'est un bucket "
                "qui n'est pas celui qu'on croit.")
        elif not d["get_identique"]:
            log(f"  ⛔ GetObject   : {len(relu)} octets relus ≠ "
                f"{len(corps)} écrits")
        else:
            log(f"  ✅ GetObject   : {len(relu)} octets, identiques")
    except Exception as e:                                  # noqa: BLE001
        d["get"] = False
        log(f"  ⛔ GetObject   : {type(e).__name__} — {e}")

    # ── 3. supprimer ──────────────────────────────────────────────────
    # ⚠️ `Storage.delete` AVALE l'exception et rend False en journalisant
    # sur stderr (c'est son contrat : une purge ne doit jamais faire
    # échouer un run). On lit donc son booléen, et on ne s'en contente
    # pas — l'étape 4 est celle qui décide.
    d["delete"] = bool(store.delete(cle))
    log(f"  {'✅' if d['delete'] else '⛔'} DeleteObject : appel "
        f"{'accepté' if d['delete'] else 'REFUSÉ (détail sur stderr)'}")

    # ── 4. ⚠️ LE SEUL VRAI TEST ───────────────────────────────────────
    try:
        reste = store.get(cle)
        d["absent_apres_delete"] = reste is None
        if reste is None:
            log("  ✅ après suppression : la clé a DISPARU — "
                "la purge fonctionnera.")
        else:
            log(f"  ⛔ après suppression : la clé est TOUJOURS LÀ "
                f"({len(reste)} octets). Un appel accepté qui ne supprime "
                f"rien est le pire des deux mondes : la purge se croirait "
                f"faite et le produit grossirait sans fin.")
    except Exception as e:                                  # noqa: BLE001
        d["absent_apres_delete"] = False
        log(f"  ⛔ relecture après suppression : {type(e).__name__} — {e}")

    store.bilan(log)
    ok = bool(d["put"] and d["get_identique"] and d["delete"]
              and d["absent_apres_delete"])
    return ok, d


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--prefixe", default=PREFIXE)
    a = p.parse_args(argv)

    print("┌─ SONDE DES DROITS R2 ────────────────────────────────────")
    print(f"│ backend  : {os.environ.get('STORAGE_BACKEND') or '(défaut)'}")
    print(f"│ bucket   : {os.environ.get('R2_BUCKET') or '(défaut wind-grid)'}")
    print(f"│ préfixe  : {a.prefixe}")
    print("└──────────────────────────────────────────────────────────")
    try:
        ok, d = sonder(a.prefixe)
    except Abort as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2

    print()
    if ok:
        print("✅ VERDICT : PutObject, GetObject et DeleteObject sont tous "
              "accordés, et la suppression est RÉELLE (constatée par "
              "relecture). La purge à 3 runs du produit B peut être écrite.")
        return 0
    print("⛔ VERDICT : le jeton ne fait pas ce que la purge exige.",
          file=sys.stderr)
    print(f"   détail : {d}", file=sys.stderr)
    print("   ⚠️ NE PAS écrire de purge sur ce jeton : elle échouerait en "
          "silence (une purge ne fait jamais échouer un run, par "
          "conception) et le produit B grossirait sans que rien ne "
          "s'allume.", file=sys.stderr)
    return 3


if __name__ == "__main__":
    sys.exit(main())
