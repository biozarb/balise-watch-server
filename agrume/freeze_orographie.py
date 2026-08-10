#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/freeze_orographie.py — extraire une fois, figer, commiter
#                                                        (10/08/2026)
#
#  Le champ `h` (orographie du modèle) est STATIQUE : il ne bouge ni
#  d'une échéance à l'autre, ni d'un run à l'autre. Le retélécharger à
#  chaque run coûterait ~50 Mo pour rien ET mettrait une dépendance
#  réseau sous le SOCLE de toute la chaîne — celui dont dépend chaque
#  altitude servie à un pilote.
#
#  Ce script l'extrait donc UNE FOIS, pour les DEUX grilles, le découpe
#  au domaine Nord-Alpes et écrit un artefact versionné d'environ 150 Ko.
#  Il se relance à la main, jamais dans un run.
#
#      python3 agrume/freeze_orographie.py            # gèle
#      python3 agrume/freeze_orographie.py --verifier # relit, ne réécrit pas
#
#  ⚠️ NE PAS le câbler dans une GitHub Action. Un champ figé qui se
#  régénère tout seul n'est plus figé : il change le jour où
#  Météo-France change son maillage, silencieusement, et toutes les
#  altitudes archivées avant ce jour cessent d'être comparables à celles
#  d'après. Si le champ doit changer, ça se voit dans un diff et ça
#  s'assume dans un commit.
#
#  ⚠️ MÉNAGE. Les GRIB téléchargés (7,5 Mo en 001, 43,4 Mo en 0025) sont
#  supprimés dans un `finally`. La consigne du projet est ferme : on ne
#  laisse pas traîner de GRIB, ni sur le container, ni sur le VPS.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

from domaine import DOMAINE, GRID_3D, GRID_FINE, PAQUET_OROGRAPHIE  # noqa: E402
from mf_s3 import download_tmp, s3_keys, s3_objets  # noqa: E402
from orographie import (ARTEFACT_JSON, ARTEFACT_NPZ, Abort,  # noqa: E402
                        CLES_META, _sha256, charger_artefact, decouper,
                        ecart_grilles, ecrire_artefact, lire_champ_h)


def runs_candidats(n=8):
    """Les `n` derniers runs synoptiques, du plus récent au plus ancien.

    ⚠️ Aucune heure de mise à disposition n'est codée en dur — ni ici, ni
    ailleurs dans AGRUME. La documentation Météo-France est incohérente
    avec elle-même sur ce point (5 h 05 de délai annoncé pour le run 06
    contre 3 h 30 pour le run 09) et ne dit même pas si ces heures sont
    en UTC ou en heure légale. On remonte donc jusqu'à trouver un run
    publié, ce qui est vrai quoi qu'annonce la doc.
    """
    base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    base -= timedelta(hours=base.hour % 3)
    for back in range(n):
        yield (base - timedelta(hours=3 * back)).strftime("%Y-%m-%dT%H:00:00Z")


def trouver_run_complet():
    """Premier run qui publie l'orographie SUR LES DEUX GRILLES.

    ⚠️ Les deux ensemble, jamais l'une sans l'autre : l'hybride du
    §4.1 bis a besoin des deux, et surtout un artefact dont les deux
    moitiés viendraient de runs différents serait indétectable à la
    relecture. Les deux champs sont statiques, donc ce n'est en principe
    pas grave — mais « en principe » n'est pas une garantie qu'on peut
    écrire dans un manifeste.
    """
    for ref in runs_candidats():
        trouve = {}
        for grille in (GRID_FINE, GRID_3D):
            paquet, motif = PAQUET_OROGRAPHIE[grille]
            objets = [(k, t) for k, t in
                      s3_objets(f"pnt/{ref}/arome/{grille}/{paquet}/")
                      if motif in k]
            if objets:
                trouve[grille] = sorted(objets)[0]
        if len(trouve) == 2:
            return ref, trouve
        if trouve:
            print(f"  · {ref} : {sorted(trouve)} seulement — on remonte")
    raise Abort("aucun run ne publie l'orographie sur les deux grilles sur "
                "les 8 derniers réseaux — le miroir S3 est-il en panne ?")


def quantiles(v, qs=(0.1, 0.25, 0.5, 0.75, 0.9)):
    a = np.sort(np.asarray(v, dtype=float))
    return [float(a[min(len(a) - 1, int(q * len(a)))]) for q in qs] if len(a) else []


def geler():
    import eccodes

    ref, objets = trouver_run_complet()
    print(f"▶ run retenu : {ref} (champ statique, le run ne fait que dater "
          f"l'extraction)")

    paire, grilles_manifeste = {}, {}
    for grille in (GRID_FINE, GRID_3D):
        cle, taille = objets[grille]
        paquet, _ = PAQUET_OROGRAPHIE[grille]
        print(f"\n── grille {grille} · paquet {paquet} "
              f"({taille / 1e6:.1f} Mo) ──")
        chemin = download_tmp(cle)
        try:
            valeurs, meta = lire_champ_h(chemin)
        finally:
            os.unlink(chemin)          # ménage : jamais de GRIB qui traîne
        orog = decouper(valeurs, meta, grille)
        paire[grille] = orog
        j0, i0 = orog.j0, orog.i0
        nj, ni = orog.z.shape
        print(f"  grille native {meta['Ni']}×{meta['Nj']} @ {meta['di']}° · "
              f"origine {meta['lat0']}/{meta['lon0']}")
        print(f"  domaine       {nj}×{ni} = {nj * ni} points "
              f"(j {j0}..{j0 + nj - 1}, i {i0}..{i0 + ni - 1})")
        print(f"  altitude      min {orog.z.min():.0f} · médiane "
              f"{np.median(orog.z):.0f} · max {orog.z.max():.0f} m")
        grilles_manifeste[grille] = dict(
            paquet=paquet, cle_s3=cle, octets_source=taille,
            meta={k: (float(meta[k]) if isinstance(meta[k], float) else int(meta[k]))
                  for k in CLES_META},
            j0=j0, i0=i0, nj=nj, ni=ni,
            sha256=_sha256(orog.z),
            z_min=round(float(orog.z.min()), 1),
            z_med=round(float(np.median(orog.z)), 1),
            z_max=round(float(orog.z.max()), 1))

    # ── Ce que les deux grilles ne disent PAS pareil ──────────────────
    # Mesuré ici, sur les points de grille du domaine, et pas seulement
    # aux balises : c'est ce chiffre-là qui décide si l'artefact est
    # exploitable. S'il tombait à zéro, les deux moitiés seraient le même
    # champ — l'erreur exacte que tout ce module existe pour empêcher.
    fine = paire[GRID_FINE]
    pts = [fine.coords(j, i)
           for j in range(0, fine.z.shape[0], 3)
           for i in range(0, fine.z.shape[1], 3)]
    ecarts = ecart_grilles(paire, pts)
    absolus = [abs(e) for e in ecarts]
    q = quantiles(ecarts)
    print(f"\n── ÉCART z_0025 − z_001 sur {len(ecarts)} points du domaine ──")
    print(f"  d1 {q[0]:+.0f} · q1 {q[1]:+.0f} · MÉDIANE {q[2]:+.0f} · "
          f"q3 {q[3]:+.0f} · d9 {q[4]:+.0f} m")
    print(f"  |écart| médian {np.median(absolus):.0f} m · moyen "
          f"{np.mean(absolus):.0f} m · max {max(absolus):.0f} m")
    part100 = 100 * sum(1 for a in absolus if a > 100) / len(absolus)
    print(f"  {part100:.0f} % des points au-delà de 100 m")

    manifeste = dict(
        produit="AGRUME — orographie du modèle, figée",
        ecrit_le=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        run_source=ref,
        eccodes=eccodes.codes_get_api_version(),
        domaine=DOMAINE,
        grilles=grilles_manifeste,
        ecart_0025_moins_001=dict(
            n=len(ecarts),
            d1=round(q[0], 1), q1=round(q[1], 1), mediane=round(q[2], 1),
            q3=round(q[3], 1), d9=round(q[4], 1),
            abs_median=round(float(np.median(absolus)), 1),
            abs_max=round(float(max(absolus)), 1),
            part_au_dela_100m=round(part100, 1)),
        note=("Champ `h` (surface), STATIQUE. ⚠️ Le paquet CHANGE avec la "
              "grille : 001/SP3 mais 0025/SP2 — 0025/SP3 existe et ne "
              "contient aucune orographie. Régénérer avec "
              "`python3 agrume/freeze_orographie.py`."))

    o_npz, o_json = ecrire_artefact(paire, manifeste)
    print(f"\n▶ {ARTEFACT_NPZ.name} : {o_npz / 1024:.0f} Ko · "
          f"{ARTEFACT_JSON.name} : {o_json / 1024:.0f} Ko")
    return 0


def verifier():
    paire, man = charger_artefact()
    print(f"▶ artefact du {man['ecrit_le']}, run source {man['run_source']}, "
          f"eccodes {man['eccodes']}")
    for grille, o in sorted(paire.items()):
        print(f"  {o!r}  sha256 ✓")
    e = man["ecart_0025_moins_001"]
    print(f"  écart 0025−001 : médiane {e['mediane']:+.0f} m, "
          f"|écart| médian {e['abs_median']:.0f} m, "
          f"{e['part_au_dela_100m']:.0f} % au-delà de 100 m (n = {e['n']})")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verifier", action="store_true",
                   help="relit l'artefact existant sans rien retélécharger")
    a = p.parse_args(argv)
    try:
        return verifier() if a.verifier else geler()
    except Abort as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
