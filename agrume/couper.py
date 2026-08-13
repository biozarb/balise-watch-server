#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/couper.py — lire une coupe verticale, en dessin ou en JSON
#                                                        (10/08/2026)
#
#  Le visage de l'étape 8, comme `sonder.py` est celui de l'étape 5. Lit
#  une grille du produit B — locale ou sur R2 — et rend la coupe le long
#  d'un segment.
#
#  ⚠️ CE N'EST PAS UNE ROUTE HTTP, même raison qu'à l'étape 5 : la forme
#  de la réponse est arrêtée et testée, où on la sert est une autre
#  décision.
#
#  ⚠️⚠️ LE DESSIN ASCII N'INTERPOLE RIEN, ET C'EST TOUT L'INTÉRÊT. Chaque
#  caractère est UN niveau du modèle, posé sur la ligne d'altitude où il
#  tombe. Les lignes où aucun niveau ne tombe restent VIDES. Un dessin
#  qui remplirait les trous serait plus joli et montrerait de la donnée
#  qui n'existe pas — or le seul but de cette vue est de voir, à l'œil,
#  ce que la coupe contient réellement.
#
#      python3 agrume/couper.py --archive g.npz g.json \
#              --de 45.60,5.90 --a 45.45,6.60 --echeance 3
#      python3 agrume/couper.py --run 2026-08-10T09:00:00Z \
#              --de 45.60,5.90 --a 45.45,6.60 --echeance 3 --json
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

import transect as T  # noqa: E402
from grille import Grille  # noqa: E402

# Échelle de vitesse. ⚠️ Les seuils sont ceux qui parlent à un pilote de
# vol libre, pas des quantiles jolis : ~15 km/h est la limite du confort
# au décollage, 25 celle où beaucoup renoncent, 45 celle où le vol est
# hors de question. Un dessin dont l'échelle ne veut rien dire ne sert
# qu'à faire joli.
ECHELLE = ((5, "."), (10, ":"), (15, "-"), (25, "="), (35, "+"),
           (45, "*"), (60, "#"), (10 ** 9, "@"))
SOL = "▒"


def symbole(kmh):
    for seuil, c in ECHELLE:
        if kmh < seuil:
            return c
    return "@"


def depuis_r2(run, domaine="nord-alpes", echeances=None, crier=print):
    """Récupère la grille d'un run depuis R2.

    ⚠️ Lecture seule et via le module partagé, comme `sonder.py` :
    `tools/storage.py` porte déjà les identifiants et le compteur
    d'opérations. ⚠️ Le produit B ne garde que 3 runs : un run absent
    n'est pas une panne, c'est une purge qui a fait son travail.

    ⛔ RÉÉCRIT LE 13/08 (audit) : ce lecteur demandait encore
    `agrume/grille/{run}/grille.npz` — une clé de l'AVANT-étape 11, sans
    domaine, dans un format qui n'est plus jamais écrit sur R2 (et que
    `index_apres` a envoyée à la suppression). 404 à chaque appel,
    pendant deux lots, sans qu'aucun banc ne le voie. La route est
    désormais celle des objets PUBLIÉS — manifeste + tampons d'échéance
    + zsol — via `Grille.depuis_tampons()`, bancée par `test_grille` §11.

    `echeances=None` tire tout le run (52 tampons × ~1,3 Mo au pire) ;
    en passer une liste ne tire que celles-là — c'est ce que fait le
    `main` avec `--echeance`.
    """
    from storage import Storage
    store = Storage("agrume-couper", "AGRUME_BUCKET", "wind-grid")
    base = f"agrume/grille/{domaine}/{run}"
    man = json.loads(store.get(f"{base}/manifest.json").decode("utf-8"))
    voulues = man["echeances"] if echeances is None else [
        s for s in man["echeances"] if s in set(echeances)]
    if echeances is not None and not voulues:
        raise SystemExit(f"aucune des échéances {sorted(echeances)} n'est "
                         f"dans le run {run} ({man['echeances']})")
    tampons = {s: store.get(man["service"]["cle_echeance"]
                            .format(domaine=domaine, run=run, step=s))
               for s in voulues}
    zsol = store.get(man["service"]["cle_zsol"]
                     .format(domaine=domaine, run=run))
    return Grille.depuis_tampons(man, tampons, zsol), man


def couple(texte):
    lat, lon = texte.split(",")
    return (float(lat), float(lon))


def dessiner(rep, largeur=78, lignes=34, crier=print):
    """La coupe, à l'œil. Ordonnée = altitude-mer, abscisse = distance."""
    pts = rep["points"]
    if not pts:
        crier("  (aucun point)")
        return
    # ⚠️ On sous-échantillonne les COLONNES pour tenir dans le terminal,
    # et on le DIT — sinon la largeur du terminal deviendrait un choix
    # scientifique.
    if len(pts) > largeur:
        pas = len(pts) / largeur
        montres = [pts[min(len(pts) - 1, int(k * pas))] for k in range(largeur)]
        note_largeur = (f"  ⓘ {len(pts)} points ramenés à {largeur} colonnes "
                        f"pour l'affichage (la donnée, elle, en a "
                        f"{rep['resolution']['nbMaillesDistinctes']} "
                        f"distinctes)")
    else:
        montres, note_largeur = pts, ""

    sols = [p["solModeleM"] for p in montres if p["solModeleM"] is not None]
    hauts = [max((n["altitudeM"] for n in p["niveaux"]), default=0)
             for p in montres]
    if not sols:
        crier("  (aucun sol de modèle : grille vide ?)")
        return
    z_bas = min(sols)
    z_haut = max(hauts)
    pas_z = max(50.0, (z_haut - z_bas) / (lignes - 1))
    nb = int((z_haut - z_bas) / pas_z) + 1

    toile = [[" "] * len(montres) for _ in range(nb)]
    for x, p in enumerate(montres):
        for n in p["niveaux"]:
            y = int(round((n["altitudeM"] - z_bas) / pas_z))
            if 0 <= y < nb:
                toile[y][x] = symbole(n["vitesseKmh"])
        if p["solModeleM"] is not None:
            # ⚠️ `ceil`, pas `int`. Avec la troncature, la ligne qui
            # CONTIENT le sol restait blanche quand aucun niveau n'y
            # tombait — et une ligne blanche au milieu du terrain se lit
            # comme un trou de donnée, c'est-à-dire comme un défaut
            # d'ingestion. Constaté à la première exécution réelle.
            y_sol = math.ceil((p["solModeleM"] - z_bas) / pas_z)
            for y in range(0, min(max(y_sol, 0), nb)):
                if toile[y][x] == " ":
                    toile[y][x] = SOL

    crier("")
    for y in range(nb - 1, -1, -1):
        crier(f"  {z_bas + y * pas_z:6.0f} m │{''.join(toile[y])}")
    crier(f"         └{'─' * len(montres)}")
    crier(f"          0 km{' ' * max(0, len(montres) - 14)}"
          f"{rep['segment']['longueurKm']:.0f} km")
    crier(f"\n  échelle km/h : {'  '.join(f'{c} <{s}' for s, c in ECHELLE[:-1])}"
          f"   {SOL} sous le sol du modèle")
    crier("  ⚠️ chaque caractère est UN niveau du modèle — aucune "
          "interpolation, les lignes vides sont vides")
    if note_largeur:
        crier(note_largeur)


def rendre(rep, crier=print):
    s, r = rep["segment"], rep["resolution"]
    crier(f"\n{rep['produit']}")
    crier(f"  run {rep['run']} + {rep['echeanceH']} h · maille {rep['grille']}")
    crier(f"  {s['depart']['lat']}, {s['depart']['lon']}  →  "
          f"{s['arrivee']['lat']}, {s['arrivee']['lon']}   "
          f"{s['longueurKm']} km, pas {s['pasKm']} km ({s['geodesique']})")
    crier(f"  relief du modèle : {rep['relief']['solMinM']} → "
          f"{rep['relief']['solMaxM']} m · plafond = sol + "
          f"{rep['plafond']['hauteurSolMaxM']} m")
    # ⚠️ Les deux nombres qui empêchent de croire à une finesse inventée.
    ligne = (f"  {r['nbPoints']} points d'échantillonnage pour "
             f"{r['nbMaillesDistinctes']} colonnes DISTINCTES")
    crier(ligne + ("   ⚠️ escalier : la finesse en plus vient de "
                   "l'affichage" if r["escalier"] else ""))
    if s["ecartDroiteLatLonM"] > 0.5 * 1000 * min(
            r["mailleKm"]["hauteur"], r["mailleKm"]["largeur"]):
        crier(f"  ⚠️ la coupe suit l'orthodromie, qui s'écarte de "
              f"{s['ecartDroiteLatLonM']:.0f} m de la droite lat/lon — "
              f"plus d'une demi-maille : le tracé dessiné sur une carte "
              f"ne passe pas par les mêmes colonnes.")
    dessiner(rep, crier=crier)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", nargs=2, metavar=("NPZ", "JSON"))
    p.add_argument("--run", help="run à lire sur R2 (produit B, 3 derniers)")
    p.add_argument("--de", required=True, type=couple, metavar="LAT,LON")
    p.add_argument("--a", required=True, type=couple, metavar="LAT,LON")
    p.add_argument("--echeance", type=int, default=0)
    p.add_argument("--pas", type=float, default=None,
                   help="pas d'échantillonnage en km (défaut : la maille)")
    p.add_argument("--points", type=int, default=None,
                   help="nombre de points imposé — ⚠️ au-delà du nombre de "
                        "mailles, la finesse est fabriquée")
    p.add_argument("--json", action="store_true")
    p.add_argument("--domaine", default="nord-alpes",
                   help="domaine du produit B (défaut : nord-alpes) — "
                        "le domaine fait partie de la clé R2 depuis "
                        "l'étape 11")
    a = p.parse_args(argv)

    if a.archive:
        gr, man = Grille.lire_npz(
            a.archive[0], json.loads(Path(a.archive[1]).read_text("utf-8")))
    elif a.run:
        # ⚠️ On ne tire QUE l'échéance demandée : une coupe = un tampon
        # (~1,3 Mo), pas les 52 du run.
        gr, man = depuis_r2(a.run, domaine=a.domaine,
                            echeances=[a.echeance])
    else:
        p.error("il faut --archive ou --run")

    rep = T.couper(gr, man, a.de, a.a, a.echeance,
                   pas_km=a.pas, n=a.points)
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1))
    else:
        rendre(rep)
    return 0


if __name__ == "__main__":
    sys.exit(main())
