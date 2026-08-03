#!/usr/bin/env python3
"""
test_isobars_manifest.py — le skip-if-exists et la purge des isobares
lisent-ils bien le manifest, et se taisent-ils quand il ment ?

À lancer depuis `balise-watch-server/` :
    python3 tools/test_isobars_manifest.py

Pourquoi ce test existe. Le 03/08/2026, `sb_exists()` (un `HeadObject`
par échéance) et le `ListObjects` paginé de `purge_stale()` ont été
remplacés par une seule lecture du manifest du run précédent — pour
passer de ~90 opérations Class A par run à 1 opération Class B. Le gain
est réel, mais il déplace la question : **la purge ne sait plus ce que le
bucket contient, elle croit un fichier.**

Le scénario à ne jamais laisser passer est donc celui où ce fichier
manque ou est illisible. Interprété comme « le bucket est vide », il ne
supprimerait rien (inoffensif) ; interprété dans l'autre sens par une
future réécriture, il supprimerait tout. C'est exactement la famille de
bug rencontrée quatre fois les 01-02/08 — « un état partiel qui se croit
final » — et c'est ce que le cas 2 verrouille.

Aucun réseau, aucun Supabase, aucun R2.
"""
import importlib.util
import sys
import types


def charger():
    for nom in ("omfiles", "fsspec", "numpy", "matplotlib",
                "matplotlib.pyplot", "scipy", "scipy.ndimage"):
        if nom not in sys.modules:
            m = types.ModuleType(nom)
            m.__getattr__ = lambda k: (lambda *a, **kw: None)
            m.use = lambda *a, **kw: None
            sys.modules[nom] = m
    spec = importlib.util.spec_from_file_location("iso", "arpege-isobars/ingest.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["iso"] = mod
    spec.loader.exec_module(mod)
    mod.DRY_RUN = False          # on veut voir les suppressions réelles
    return mod


class StoreFactice:
    """Ne parle à personne. Retient ce qu'on lui supprime."""

    def __init__(self, manifest):
        self.manifest = manifest          # dict, ou None (absent)
        self.supprimes = []

    def get_json(self, path):
        return self.manifest

    def delete(self, path):
        self.supprimes.append(path)
        return True


def cas(nom, attendu, obtenu):
    ok = attendu == obtenu
    print(f"  {'✓' if ok else '✗'} {nom}")
    if not ok:
        print(f"      attendu {attendu!r}\n      obtenu  {obtenu!r}")
    return ok


def main():
    iso = charger()
    ok = True

    # ── 1. Régime normal ──────────────────────────────────────────────
    # Le manifest précédent liste 4 échéances ; le nouveau run n'en garde
    # que 3 (la plus ancienne est sortie de PAST_RETENTION_H).
    precedent = ["2026-08-01T00:00", "2026-08-01T06:00",
                 "2026-08-01T12:00", "2026-08-01T18:00"]
    nouveau = precedent[1:]
    iso.STORE = StoreFactice({"times": precedent})
    publiees, lu = iso.echeances_publiees("arpege_europe")
    ok &= cas("manifest lu", (set(precedent), True), (publiees, lu))
    iso.purge_stale("arpege_europe", publiees, nouveau, lu)
    ok &= cas("purge = différence des deux manifests",
              ["arpege_europe/2026-08-01T00:00.json"], iso.STORE.supprimes)

    # Le skip doit porter sur les échéances listées, et sur elles seules.
    ok &= cas("skip d'un passé listé", True, "2026-08-01T06:00" in publiees)
    ok &= cas("pas de skip d'un inconnu", False, "2026-08-02T00:00" in publiees)

    # ── 2. LE CAS QUI COMPTE — manifest absent ou illisible ───────────
    # Sans état fiable, on ne détruit RIEN. Le coût est une fenêtre
    # recalculée (bornée par le plafond dur du run) ; l'alternative
    # serait une suppression à l'aveugle, et elle est irrattrapable :
    # le versionnage est désactivé sur le bucket.
    for etiquette, faux_manifest in (("absent", None),
                                     ("illisible", {"pas_de_times": 1}),
                                     ("times non-liste", {"times": "oups"})):
        iso.STORE = StoreFactice(faux_manifest)
        publiees, lu = iso.echeances_publiees("arpege_europe")
        iso.purge_stale("arpege_europe", publiees, nouveau, lu)
        ok &= cas(f"manifest {etiquette} → 0 suppression, tout recalculé",
                  (set(), False, []),
                  (publiees, lu, iso.STORE.supprimes))

    # ── 3. Bucket neuf (bascule R2) ───────────────────────────────────
    # Pas de manifest : rien à purger, tout est produit. C'est le
    # comportement voulu — et toute la raison du mode `both`.
    iso.STORE = StoreFactice(None)
    publiees, lu = iso.echeances_publiees("arpege_world")
    iso.purge_stale("arpege_world", publiees, nouveau, lu)
    ok &= cas("bucket neuf → rien supprimé", [], iso.STORE.supprimes)

    # ── 4. Le manifest n'est jamais candidat à la suppression ─────────
    # Il n'apparaît pas dans `times`, donc jamais dans la différence.
    iso.STORE = StoreFactice({"times": precedent})
    publiees, lu = iso.echeances_publiees("arpege_europe")
    iso.purge_stale("arpege_europe", publiees, [], lu)
    ok &= cas("manifest.json jamais supprimé", False,
              any("manifest" in p for p in iso.STORE.supprimes))
    ok &= cas("purge d'une fenêtre vidée = les 4 échéances",
              4, len(iso.STORE.supprimes))

    # ── 5. Aucun appel facturé en Class A ─────────────────────────────
    # Le store factice n'expose ni `exists` ni de listing : si le code en
    # appelait un, ce test planterait sur un AttributeError. C'est le
    # garde-fou n°1 vérifié par construction plutôt que par relecture.
    ok &= cas("aucun exists()/listing dans le chemin",
              False, hasattr(iso.STORE, "exists"))

    print("\n  isobares (manifest) :", "OK" if ok else "ÉCHEC")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
