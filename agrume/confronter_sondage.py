#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/confronter_sondage.py — le profil AGRUME contre un vrai ballon
#                                                        (10/08/2026)
#
#  Le visage de l'étape 5 bis, comme `sonder.py` l'est de l'étape 5.
#  Lit une archive du produit A, va chercher le radiosondage Wyoming du
#  même instant, et publie les écarts par tranche.
#
#      python3 agrume/confronter_sondage.py --run 2026-08-10T00:00:00Z \
#              --station 06610 --date 2026-08-10 --heure 12
#      python3 agrume/confronter_sondage.py --archive c.npz c.json \
#              --station 06610 --date 2026-08-10 --heure 00 --json
#
#  ⚠️ Sans `--run`, l'outil DIT quels runs conviennent et s'arrête. Il ne
#  choisit pas à la place de l'opérateur : l'échéance 0 est une ANALYSE
#  (elle a déjà vu des observations, peut-être ce ballon-ci), les
#  échéances lointaines sont une PRÉVISION. Confondre les deux, c'est
#  publier « AROME est excellent » en ayant mesuré l'assimilation.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

import profil as P  # noqa: E402
import radiosondage as RS  # noqa: E402
from colonnes import Abort, Colonnes  # noqa: E402
from sonder import depuis_r2, trouver_balise  # noqa: E402


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", nargs=2, metavar=("NPZ", "JSON"))
    p.add_argument("--run", help="run AROME à lire sur R2")
    p.add_argument("--station", required=True, help="indicatif OMM, ex. 06610")
    p.add_argument("--date", required=True, help="date du lâcher, AAAA-MM-JJ")
    p.add_argument("--heure", default="00", choices=("00", "12"))
    p.add_argument("--ascension", type=float, default=RS.ASCENSION_MS,
                   help="vitesse d'ascension SUPPOSÉE du ballon (m/s) — "
                        "n'entre que dans l'estimation de dérive")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    try:
        st = RS.station(a.station)
        if not st["active"]:
            raise RS.Abort(
                f"{st['nom']} ({st['wmo']}) est marquée INACTIVE : "
                f"{st['mesure']}")

        candidats = RS.runs_pour(a.date, a.heure)
        if not a.archive and not a.run:
            print(f"▶ runs dont une échéance tombe sur {a.date} {a.heure}Z :")
            for run, ech in candidats:
                note = ("  ⓘ ANALYSE : a déjà assimilé des observations"
                        if ech == 0 else "")
                print(f"    --run {run}   → échéance {ech:>2} h{note}")
            raise Abort("choisir un run ci-dessus, ou passer --archive")

        if a.archive:
            man = json.loads(Path(a.archive[1]).read_text(encoding="utf-8"))
            col, man = Colonnes.lire_npz(a.archive[0], man)
        else:
            col, man = depuis_r2(a.run)

        ech = dict(candidats).get(col.run)
        if ech is None:
            raise Abort(
                f"le run de cette archive ({col.run}) n'a AUCUNE échéance "
                f"qui tombe sur {a.date} {a.heure}Z. ⚠️ Ne pas comparer une "
                f"échéance voisine : une heure d'écart sur un profil de vent "
                f"passerait pour un défaut du modèle. Runs valides : "
                + ", ".join(r for r, _ in candidats))
        if ech not in col.steps:
            raise Abort(f"échéance {ech} h absente de l'archive — "
                        f"disponibles : {col.steps}")

        k = trouver_balise(col, f"RS-{st['wmo']}")
        reponse = P.sonder(col, man, k, ech,
                           altitude_reelle=st["sol_station_m"])
        niveaux = RS.parse_wyoming(
            RS.telecharger(st["wmo"], a.date, a.heure))
        c = RS.confronter(reponse, niveaux, a.ascension)
    except (Abort, RS.Abort) as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2

    if a.json:
        print(json.dumps(dict(c, station=st), ensure_ascii=False, indent=1,
                         default=str))
    else:
        RS.afficher(c, st, a.date, a.heure)
    return 0


if __name__ == "__main__":
    sys.exit(main())
