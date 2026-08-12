#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/confronter_calque.py — le calque contre le produit A
#                                                        (12/08/2026)
#
#  Le banc de `test_calque.py` vérifie le calque CONTRE LUI-MÊME : que
#  l'interpolation rende le niveau brut quand elle le doit. C'est un
#  excellent détecteur d'erreur d'indexation. Ce n'est PAS une preuve que
#  le calque montre la même atmosphère que le reste du produit.
#
#  ⚠️ C'est exactement la distinction que le README fait déjà pour le
#  profil : `ecart_recouvrement()` mesurait 0,04 m/s, le ballon 1,73 —
#  « un facteur ~40 ». Un contrôle interne ne devient une mesure
#  d'exactitude que le jour où on le confronte à une source qui n'a rien
#  en commun avec lui.
#
#  Ici la source indépendante est le PRODUIT A : archive définitive,
#  extraite AUX BALISES par un indice plat calculé depuis les métadonnées
#  du GRIB — un chemin d'indexation qui n'a rien à voir avec le plus
#  proche voisin sur les axes publiés qu'utilise le produit B. C'est la
#  même confrontation que l'étape 8 a faite pour la coupe (875 colonnes,
#  identiques) ; on la refait ici POUR L'INTERPOLATION.
#
#  ⛔ LE POINT COMMUN N'EST PAS UNE ALTITUDE, C'EST UNE COLONNE. `zsol`
#  varie de 3 720 m sur le domaine : aucune altitude-mer ne tombe sur un
#  niveau partout. Pour chaque balise on demande donc au calque
#  l'altitude `A = zsol(balise) + niveau`, et on exige la valeur du
#  produit A à ce niveau — à l'arrondi de publication près, la même
#  précaution qui avait fait rendre 0/125 à la première comparaison du
#  10/08 (§4 de la note de l'étape 8).
#
#      python3 agrume/confronter_calque.py \
#              --grille grille.npz manifest.json \
#              --colonnes A-colonnes.npz A-manifest.json
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

import calque as C  # noqa: E402
from colonnes import Colonnes  # noqa: E402
from domaine import NIVEAUX_H_0025  # noqa: E402
from grille import Grille  # noqa: E402
from transect import index_plus_proche  # noqa: E402


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--grille", nargs=2, required=True,
                   metavar=("NPZ", "MANIFESTE"))
    p.add_argument("--colonnes", nargs=2, required=True,
                   metavar=("NPZ", "MANIFESTE"))
    p.add_argument("--echeances", type=int, default=7,
                   help="nombre d'échéances confrontées (par défaut 7)")
    a = p.parse_args(argv)

    man_g = json.loads(open(a.grille[1], encoding="utf-8").read())
    gr, man_g = Grille.lire_npz(a.grille[0], man_g)
    man_c = json.loads(open(a.colonnes[1], encoding="utf-8").read())
    col, man_c = Colonnes.lire_npz(a.colonnes[0], man_c)

    if man_g["run"] != man_c["run"]:
        raise SystemExit(
            f"⛔ deux runs différents : produit B {man_g['run']}, produit A "
            f"{man_c['run']}. La confrontation n'aurait aucun sens — et elle "
            f"rendrait un écart plausible.")

    balises = man_c["balises"]
    steps = [s for s in man_c["echeances"] if s in gr.steps][:a.echeances]
    # ⚠️ `parametres` du produit A est un dict PAR GRILLE (`0025`, `001`,
    # `isobares`), pas une liste : le produit A porte trois périmètres,
    # le produit B un seul. Prendre la liste au mauvais niveau donnerait
    # un `KeyError` — ou pire, un indice valide sur la mauvaise grille.
    ip_c = {q["nom"]: k
            for k, q in enumerate(man_c["parametres"][man_g["grille"]])}

    print(f"run {man_g['run']} · {len(balises)} balises à l'axe · "
          f"{len(steps)} échéances confrontées")

    n_cas = n_hors = n_sans_sol = 0
    ecarts = []
    pire = None
    for b in balises:
        try:
            j, i = index_plus_proche(gr.lats, gr.lons, b["lat"], b["lon"])
        except ValueError:
            n_hors += 1          # balise pyrénéenne ou isolée : hors produit B
            continue
        zs = float(gr.zsol[j, i])
        if not np.isfinite(zs):
            n_sans_sol += 1
            continue
        i_b = balises.index(b)
        for step in steps:
            i_s_c = man_c["echeances"].index(step)
            for k, niveau in enumerate(NIVEAUX_H_0025):
                # ⚠️ L'altitude est DIFFÉRENTE pour chaque balise : c'est
                # tout l'objet du lot. Une altitude commune ne tomberait
                # sur un niveau nulle part.
                A = zs + float(niveau)
                r = C.calque(gr, step, A)
                for nom in ("u", "v"):
                    # ⚠️ Le produit A est disposé (balise, paramètre,
                    # niveau, échéance) — la BALISE en tête. Le produit B
                    # est (paramètre, niveau, échéance, lat, lon). Les
                    # deux tableaux ont le même contenu et un ordre
                    # d'axes différent ; les confondre donnerait des
                    # indices valides et des valeurs absurdes.
                    ref = col.c0025[i_b, ip_c[nom], k, i_s_c]
                    got = r["champs"][nom][j, i]
                    if not np.isfinite(ref) or not np.isfinite(got):
                        continue
                    # Même arrondi de publication des deux côtés — la
                    # leçon du 10/08 : comparer deux FORMATS au lieu de
                    # deux valeurs donne un rouge parfaitement crédible.
                    e = abs(round(float(got), 2) - round(float(ref), 2))
                    ecarts.append(e)
                    n_cas += 1
                    if pire is None or e > pire[0]:
                        pire = (e, b.get("id", i_b), step, niveau, nom)

    if not ecarts:
        raise SystemExit("⛔ aucun point commun — la confrontation n'a rien "
                         "mesuré. Ne PAS lire ça comme un succès.")
    ecarts = np.asarray(ecarts)
    print(f"\n  points communs comparés : {n_cas}")
    print(f"  balises hors produit B  : {n_hors}  (Pyrénées + isolées)")
    if n_sans_sol:
        print(f"  balises sans sol        : {n_sans_sol}")
    print(f"  écart médian            : {np.median(ecarts):.6g} m/s")
    print(f"  écart maximal           : {ecarts.max():.6g} m/s")
    print(f"  identiques              : {int((ecarts == 0).sum())}/{n_cas}"
          f"  ({100 * (ecarts == 0).mean():.2f} %)")
    if pire and pire[0] > 0:
        print(f"  pire cas                : balise {pire[1]}, +{pire[2]} h, "
              f"{pire[3]} m/sol, {pire[4]} → {pire[0]:.4g} m/s")
    ok = ecarts.max() == 0.0
    print("\n  " + ("✅ ÉCART NUL aux points communs — critère du lot tenu."
                    if ok else
                    "⛔ ÉCART NON NUL : le calque et le produit A ne "
                    "montrent pas la même atmosphère."))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
