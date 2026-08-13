#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  verif/sonder.py — lire un profil vertical, en tableau ou en JSON
#                                                        (10/08/2026)
#
#  Le visage de l'étape 5. Lit une archive du produit A — locale ou sur
#  R2 — et rend le sondage vertical en un point.
#
#  ⚠️ CE N'EST PAS UNE ROUTE HTTP, et c'est volontaire. La forme de la
#  réponse (`profil.sonder`) est arrêtée et testée ; où on la sert est
#  une autre décision, qui dépend de l'API Node existante et n'a pas à
#  être prise en même temps. Câbler une route maintenant, ce serait
#  figer deux choses d'un coup.
#
#      python3 verif/sonder.py --archive c.npz c.json --balise 1377
#      python3 verif/sonder.py --run 2026-08-10T06:00:00Z --balise 1377
#      python3 verif/sonder.py --archive … --balise 1377 --json
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
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "agrume"))

import profil as P  # noqa: E402
from colonnes import Colonnes  # noqa: E402
from quantification import Abort  # noqa: E402


def depuis_r2(run, crier=print):
    """Récupère l'archive d'un run depuis R2.

    ⚠️ Lecture seule, et via le module partagé — pas de client S3 écrit
    à la main ici : `tools/storage.py` porte déjà les identifiants, la
    politique de cache et le compteur d'opérations."""
    from storage import Storage
    store = Storage("agrume-sonder", "AGRUME_BUCKET", "wind-grid")
    base = f"agrume/colonnes/{run}"
    man = json.loads(store.get(f"{base}/manifest.json").decode("utf-8"))
    brut = store.get(f"{base}/colonnes.npz")
    tmp = Path(os.environ.get("TMPDIR", "/tmp")) / f"agrume-{run.replace(':', '')}.npz"
    tmp.write_bytes(brut)
    try:
        return Colonnes.lire_npz(tmp, man)
    finally:
        tmp.unlink(missing_ok=True)      # ménage : rien ne traîne


def trouver_balise(col, ident):
    """Index de la balise par identifiant, ou par position dans l'axe."""
    for k, b in enumerate(col.balises):
        if str(b["id"]) == str(ident):
            return k
    if str(ident).lstrip("-").isdigit() and int(ident) < len(col.balises):
        return int(ident)
    raise Abort(f"balise {ident!r} absente de cette archive "
                f"({len(col.balises)} balises du domaine Nord-Alpes)")


def afficher(r, crier=print):
    b = r["balise"]
    crier(f"\n{b['nom'] or b['id']}  ({b['lat']}, {b['lon']})"
          + ("   ⚠️ position suspecte" if b["positionSuspecte"] else ""))
    crier(f"run {r['run']} + {r['echeanceH']} h")
    sm = r["solModeleM"]
    crier(f"  sol du modèle : {sm['grille_0025']} m en 0,025° · "
          f"{sm['grille_001']} m en 0,01°")
    if r["elevationDeltaM"] is None:
        crier(f"  sol réel : inconnu — {r['elevationDeltaNote']}")
    else:
        crier(f"  sol réel {r['solReferenceM']:.0f} m ({r['solReferenceSource']}) "
              f"→ écart {r['elevationDeltaM']:+.0f} m "
              f"({'le modèle place le sol EN DESSOUS' if r['elevationDeltaM'] < 0 else 'au-dessus'})")
    rc = r["raccord"]
    crier(f"  raccord : hauteur seule ≤ {rc['hauteurSeuleJusquM']:.0f} m · "
          f"isobares seules ≥ {rc['isobaresSeulesDesM']:.0f} m · "
          f"{rc['nMelange']} points mélangés")
    if rc["ecartRecouvrementMs"] is not None:
        crier(f"  ⚠️ écart des deux sources au recouvrement : "
              f"{rc['ecartRecouvrementMs']:.2f} m/s sur {rc['nEcarts']} niveaux "
              f"(> 1 m/s = une conversion est fausse, pas qu'il vente)")

    crier(f"\n  {'alt ASL':>8} {'source':>8} {'poids':>6} {'km/h':>6} "
          f"{'dir':>4} {'T °C':>6} {'HR %':>5} {'TKE':>5}  niveau")
    for p in r["profil"]:
        niv = (f"{p['hauteurSolM']:>4} m/sol" if p.get("hauteurSolM") is not None
               else f"{p['niveauHPa']:>4} hPa")
        f = lambda v, n=1: "     —" if v is None else f"{v:6.{n}f}"  # noqa: E731
        crier(f"  {p['altitudeM']:>8.0f} {p['source']:>8} "
              f"{p['poidsHauteur']:>6.2f} {p['vitesseKmh']:>6.1f} "
              f"{p['directionDeg']:>4} {f(p['t'])} {f(p['hr'], 0)[1:]} "
              f"{f(p['tke'], 2)[1:]}  {niv}")

    mf = r["profilMailleFine"]
    if mf["points"]:
        crier(f"\n  ── maille fine 0,01°, sur SON sol ({mf['solM']:.0f} m) ──")
        for p in mf["points"]:
            crier(f"  {p['altitudeM']:>8.0f} {'':>8} {'':>6} "
                  f"{p['vitesseKmh']:>6.1f} {p['directionDeg']:>4}"
                  f"{'':>19}  {p['hauteurSolM']:>4} m/sol")
        mh = r["marcheHybride"]
        if mh["medianeMs"] is not None:
            crier(f"  ⚠️ marche entre les deux mailles, à hauteur-sol égale : "
                  f"{mh['medianeMs']:.2f} m/s en médiane")
            crier("     (l'écart d'ALTITUDE entre les deux sols, lui, vaut "
                  f"{mf['solM'] - sm['grille_0025']:+.0f} m — ne pas confondre)")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", nargs=2, metavar=("NPZ", "JSON"))
    p.add_argument("--run", help="run à lire sur R2, ex. 2026-08-10T06:00:00Z")
    p.add_argument("--balise", required=True)
    p.add_argument("--echeance", type=int, default=0)
    p.add_argument("--altitude-reelle", type=float, default=None,
                   help="altitude du sol réel, si tu la connais — sinon on "
                        "prend celle du nom quand il en porte une")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    try:
        if a.archive:
            man = json.loads(Path(a.archive[1]).read_text(encoding="utf-8"))
            col, man = Colonnes.lire_npz(a.archive[0], man)
        elif a.run:
            col, man = depuis_r2(a.run)
        else:
            raise Abort("préciser --archive <npz> <json> ou --run <run>")
        k = trouver_balise(col, a.balise)
        if a.echeance not in col.steps:
            raise Abort(f"échéance {a.echeance} h absente — disponibles : "
                        f"{col.steps}")
        r = P.sonder(col, man, k, a.echeance, a.altitude_reelle)
    except Abort as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2

    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        afficher(r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
