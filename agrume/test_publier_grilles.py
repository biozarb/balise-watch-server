#!/usr/bin/env python3
"""
test_publier_grilles.py — banc de `ingest_colonnes.publier_grilles`, HORS-LIGNE.

    python3 agrume/test_publier_grilles.py

⛔ CE QUE CE BANC PROTÈGE (10/10/2026).

Le garde-fou R2 est resté rouge trois nuits (08 → 10/10) sur DEUX
orphelins : `agrume/grille/nord-alpes/2026-10-07T06:00:00Z/e141.bin` et
`e144.bin`, écrits le 07/10 à 13:28 Z. Le reste du run a été purgé
normalement, pas eux. Signature d'une passe qui a ÉCRIT ses objets puis
est tombée avant l'étape 3 (l'index) : `main()` avale l'exception (voulu,
produit jetable) et les clés que seule cette passe avait publiées ne
sont plus écrites nulle part. Sans `ListObjects`, c'est une fuite.

Le correctif déclare les clés neuves sous `en_vol` AVANT la première
écriture ; la passe suivante les verse aux restes. Ce banc échoue sur le
code d'avant (§1) et verrouille les trois propriétés qui en dépendent :

  1. une passe tombée laisse ses clés neuves DANS l'index (`en_vol`) ;
  2. la passe suivante purge celles qu'elle ne republie pas, et
     n'efface RIEN de ce qu'elle publie — y compris un reste d'un domaine
     que le domaine suivant republie (garde-fou à l'index complet) ;
  3. une repasse identique ne coûte pas d'écriture d'index de plus.

Aucun réseau, aucun GRIB, aucune clé : `storage` est remplacé par un
magasin en mémoire, le temps de l'appel.
"""
from __future__ import annotations

import json
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

import ingest_colonnes as IC  # noqa: E402
import grille as GR  # noqa: E402

echecs = []


def verifier(nom, condition, detail=""):
    print(f"  {'✓' if condition else '✗'} {nom}"
          + (f"   {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


class Panne(Exception):
    pass


class Magasin:
    """Le bucket, en mémoire. `panne_sur` : préfixe de clé dont le
    premier `put` lève — la passe tombe au milieu, comme le 07/10."""

    def __init__(self, objets=None):
        self.objets = dict(objets or {})
        self.panne_sur = None
        self.puts_index = 0

    def module(self):
        m = types.ModuleType("storage")
        magasin = self

        class Storage:
            def __init__(self, *a, **k):
                pass

            def get_json(self, cle):
                b = magasin.objets.get(cle)
                return json.loads(b) if b is not None else None

            def put(self, cle, octets, **k):
                if magasin.panne_sur and cle.startswith(magasin.panne_sur):
                    raise Panne(f"put {cle}")
                if cle == GR.CLE_INDEX:
                    magasin.puts_index += 1
                magasin.objets[cle] = octets

            def delete(self, cle):
                magasin.objets.pop(cle, None)
                return True

            def bilan(self):
                pass

        m.Storage = Storage
        m.CACHE_IMMUABLE = "immuable"
        m.CACHE_REECRIT = "reecrit"
        m.verifier_dimensionnement = lambda *a, **k: 10_000
        return m

    def index(self):
        return json.loads(self.objets[GR.CLE_INDEX])

    def orphelins(self):
        idx = self.index()
        recl = {GR.CLE_INDEX}
        for e in idx.get("runs") or []:
            recl.update(e["cles"])
        recl |= set(idx.get("restes") or []) | set(idx.get("en_vol") or [])
        return sorted(c for c in self.objets if c not in recl)


class GrilleBidon:
    def __init__(self, steps):
        self.steps = list(steps)

    def tampon_echeance(self, step):
        return b"e"

    def tampon_zsol(self):
        return b"z"

    def tampon_colonnes(self):
        return b"c"

    def octets_publies(self):
        return 1e6

    def octets(self):
        return 1e6


def publier(magasin, run, pas_par_dom):
    vrai = sys.modules.get("storage")
    sys.modules["storage"] = magasin.module()
    try:
        paquets = [(d, GrilleBidon(s), {}) for d, s in pas_par_dom.items()]
        return IC.publier_grilles(paquets, run, crier=lambda *_: None)
    finally:
        if vrai is not None:
            sys.modules["storage"] = vrai
        else:
            sys.modules.pop("storage", None)


RUN = "2026-10-07T06:00:00Z"
COURT = list(range(0, 139, 3))          # e00 → e138
LONG = list(range(0, 145, 3))           # e00 → e144 (couture plus longue)
DOMS = ("nord-alpes", "pyrenees")


def main():
    print("\n── §1 · une passe qui tombe au milieu de la publication ──")
    m = Magasin()
    publier(m, RUN, {d: COURT for d in DOMS})
    verifier("état initial propre", not m.orphelins(), str(m.orphelins()))

    m.panne_sur = f"agrume/grille/pyrenees/{RUN}/"
    try:
        publier(m, RUN, {d: LONG for d in DOMS})
        verifier("la panne simulée a bien levé", False)
    except Panne:
        pass
    m.panne_sur = None
    neuves = [GR.cle_echeance(RUN, "nord-alpes", s) for s in (141, 144)]
    verifier("les tampons e141/e144 de nord-alpes sont bien en ligne",
             all(c in m.objets for c in neuves))
    verifier("⛔ et l'index s'en souvient (`en_vol`) — sinon fuite définitive",
             set(neuves) <= set(m.index().get("en_vol") or []),
             f"en_vol={m.index().get('en_vol')}")
    verifier("⛔ aucun orphelin après la panne", not m.orphelins(),
             str(m.orphelins()))

    print("\n── §2 · la passe suivante (plus courte) répare ───────────")
    publier(m, RUN, {d: COURT for d in DOMS})
    idx = m.index()
    verifier("⛔ e141/e144 purgés", not any(c in m.objets for c in neuves))
    verifier("`en_vol` vidé, `restes` vides",
             not idx.get("en_vol") and not idx.get("restes"),
             f"en_vol={idx.get('en_vol')} restes={idx.get('restes')}")
    verifier("⛔ toutes les clés réclamées sont présentes",
             all(c in m.objets for e in idx["runs"] for c in e["cles"]))
    verifier("aucun orphelin", not m.orphelins(), str(m.orphelins()))

    print("\n── §2-bis · une panne puis une repasse COMPLÈTE garde tout ──")
    m.panne_sur = f"agrume/grille/pyrenees/{RUN}/"
    try:
        publier(m, RUN, {d: LONG for d in DOMS})
    except Panne:
        pass
    m.panne_sur = None
    publier(m, RUN, {d: LONG for d in DOMS})
    idx = m.index()
    verifier("⛔ les clés « en vol » republiées ne sont PAS effacées",
             all(c in m.objets for c in neuves))
    verifier("⛔ toutes les clés réclamées sont présentes",
             all(c in m.objets for e in idx["runs"] for c in e["cles"]))
    verifier("aucun orphelin, rien en vol",
             not m.orphelins() and not idx.get("en_vol"))

    print("\n── §3 · un reste d'un domaine republié par le domaine suivant ──")
    m2 = Magasin()
    publier(m2, RUN, {"nord-alpes": COURT})
    cle_pyr = GR.cle_echeance(RUN, "pyrenees", 0)
    idx = m2.index()
    idx["restes"] = [cle_pyr]
    m2.objets[GR.CLE_INDEX] = json.dumps(idx).encode()
    m2.objets[cle_pyr] = b"vieux"
    publier(m2, RUN, {d: COURT for d in DOMS})
    verifier("⛔ la clé republiée par pyrénées n'est pas supprimée par la "
             "purge du domaine précédent", cle_pyr in m2.objets)
    verifier("…et elle n'est plus dans `restes`",
             cle_pyr not in (m2.index().get("restes") or []))

    print("\n── §4 · une repasse identique ne paie pas d'écriture de plus ──")
    avant = m.puts_index
    publier(m, RUN, {d: LONG for d in DOMS})
    verifier("une seule écriture d'index (étape 3)", m.puts_index - avant == 1,
             f"{m.puts_index - avant} écriture(s)")

    print()
    if echecs:
        print(f"✗ {len(echecs)} échec(s)")
        return 1
    print("✓ publier_grilles : tout est vert")
    return 0


if __name__ == "__main__":
    sys.exit(main())
