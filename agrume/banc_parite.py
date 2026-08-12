#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/banc_parite.py — fabrique les entrées du banc de parité
#                                                        (12/08/2026)
#
#      python3 agrume/banc_parite.py --sortie /tmp/bw-parite
#      node --experimental-strip-types \
#           tools/altitude-layer-selftest.mjs \
#           --fixture /tmp/bw-parite/fixture.json \
#           --tampon /tmp/bw-parite/e01.bin \
#           --zsol /tmp/bw-parite/zsol.bin \
#           --manifeste /tmp/bw-parite/manifest.json
#
#  ⚠️ POURQUOI UNE GRILLE SYNTHÉTIQUE PLUTÔT QUE LE RUN EN LIGNE. Le banc
#  de parité doit tourner HORS LIGNE, à chaque fois, sans dépendre d'un
#  run que la rétention de trois runs aura effacé demain. Avec
#  `--archive`, il rejoue le vrai produit ; sans, il fabrique un domaine
#  dont chaque valeur est unique et dont l'axe isobare est délibérément
#  irrégulier — deux tranches interverties, un décalage d'un octet ou une
#  lecture float16 de `ziso` s'y voient, ce qui n'est pas garanti sur des
#  valeurs réalistes.
#
#  ⛔ CE FICHIER NE VÉRIFIE RIEN. Il PRODUIT ; c'est le `.mjs` qui juge.
#  Le séparer garantit que l'oracle et le juge ne partagent pas de code.
# ══════════════════════════════════════════════════════════════════════
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

from calque import fixture                                  # noqa: E402
from domaine import NIVEAUX_H_0025, NIVEAUX_P               # noqa: E402
from grille import PARAMS_GRILLE, PARAMS_GRILLE_ISO, Grille  # noqa: E402


def grille_de_banc(nj=23, ni=31, nech=3, graine=1208):
    rng = np.random.default_rng(graine)
    lats = np.linspace(46.3, 44.8, nj).astype(np.float32)   # DÉCROISSANT
    lons = np.linspace(5.5, 7.6, ni).astype(np.float32)
    # ⚠️ Un `zsol` ÉTALÉ, pas un plateau : c'est l'étendue de `zsol` qui
    # fait qu'une même altitude tombe dans les niveaux hauteur ici et
    # au-dessus du plafond là. Sur le domaine réel, 168 → 3 887 m.
    zsol = rng.uniform(170.0, 3880.0, (nj, ni)).astype(np.float32)
    g = Grille("2026-08-12T15:00:00Z", list(range(nech)), lats, lons, zsol,
               domaine="banc")

    for p in PARAMS_GRILLE:
        for niveau in NIVEAUX_H_0025:
            for s in range(nech):
                g.poser(p["nom"], niveau, s,
                        rng.uniform(-40, 40, (nj, ni)).astype(np.float16))
    for p in PARAMS_GRILLE_ISO:
        for hpa in NIVEAUX_P:
            for s in range(nech):
                if p.get("absent_a_tau0") and s == 0:
                    continue          # ⛔ la règle de l'ingestion, rejouée
                g.poser_isobare(p["nom"], hpa, s,
                                rng.uniform(-60, 60, (nj, ni)).astype(np.float16))
    # ── L'axe isobare : croissant, mais VARIABLE en chaque point ──────
    # ⚠️ Un axe constant ferait passer un banc qui lit `ziso` de travers :
    # avec la même valeur partout, un décalage de colonne ne se voit pas.
    for k, hpa in enumerate(NIVEAUX_P):
        base = 150.0 + 570.0 * k
        for s in range(nech):
            g.poser_isobare("zp", hpa, s,
                            (base + rng.uniform(0, 40, (nj, ni))
                             + 3.0 * s).astype(np.float32))
    return g


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sortie", default="/tmp/bw-parite")
    ap.add_argument("--step", type=int, default=1,
                    help="⚠️ 1 par défaut, pas 0 : à τ=0 `cc` est vide par "
                         "décision, et un banc qui ne verrait que ça ne "
                         "verrait jamais la nébulosité.")
    a = ap.parse_args(argv)

    d = Path(a.sortie)
    d.mkdir(parents=True, exist_ok=True)
    g = grille_de_banc()

    (d / "manifest.json").write_text(
        json.dumps(g.manifeste(), ensure_ascii=False), encoding="utf-8")
    (d / f"e{a.step:02d}.bin").write_bytes(g.tampon_echeance(a.step))
    (d / "zsol.bin").write_bytes(g.tampon_zsol())
    (d / "colonnes.bin").write_bytes(g.tampon_colonnes())

    # ⓘ Des altitudes qui traversent les TROIS régimes : sous le premier
    # niveau, dans les niveaux hauteur, au-dessus du plafond hauteur
    # (donc les isobares), et au-dessus du dernier isobare.
    alts = [300.0, 1000.0, 2000.0, 3000.0, 4000.0, 5000.0, 6000.0,
            7000.0, 7600.0, 9000.0]
    fx = fixture(g, a.step, alts, nb_colonnes=40)
    (d / "fixture.json").write_text(
        json.dumps(fx, ensure_ascii=False), encoding="utf-8")

    par_source = {}
    for c in fx["cas"]:
        cle = c["source"] if c["u"] is not None else "masqué"
        par_source[cle] = par_source.get(cle, 0) + 1
    print(f"écrit dans {d} :")
    print(f"  manifest.json · e{a.step:02d}.bin "
          f"({g.octets_par_echeance()} o) · zsol.bin · colonnes.bin "
          f"({g.octets_par_colonne() * len(g.lats) * len(g.lons)} o)")
    print(f"  fixture.json : {fx['nbCas']} cas — " +
          " · ".join(f"{k} {v}" for k, v in sorted(par_source.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
