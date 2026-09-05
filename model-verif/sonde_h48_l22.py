#!/usr/bin/env python3
"""Sonde du lot L22a — ce que la classe +48 h d'AGRUME donnerait VRAIMENT,
sur une journée d'archive RÉELLE, sans rien écrire (05/09/2026).

⛔ POURQUOI UNE SONDE ET PAS UN `--dry-run`. `agrume_fcst.py --dry-run`
lit le produit A sur R2 (jeton du VPS) avant d'arriver aux lignes sœurs :
il ne peut pas tourner ailleurs que sur le VPS, et il ne dit rien du
RÉSULTAT de la couture (couverture, run servi, écart de chaîne). Cette
sonde-ci part de l'archive `fcstagrume_{J}` DÉJÀ ÉCRITE — les lignes
d'origine, telles qu'elles sont sur le disque — et rejoue `prolonger_h48`
dessus. Elle est donc rejouable sur n'importe quelle machine qui a les
quatre fichiers, y compris après coup.

⚠️ ELLE NE PROUVE PAS que le job écrira ces lignes : elle prouve ce que
`prolonger_h48` fait de l'archive du jour. La seule chose qu'elle mesure
en plus du banc, c'est la RÉALITÉ des données — couverture des balises,
run IFS réellement servi, longueur des séries.

    python3 sonde_h48_l22.py --day 2026-09-03
    python3 sonde_h48_l22.py --day 2026-09-03 --out /var/lib/bw-model-verif
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import sys
from datetime import datetime, timedelta, timezone

_ICI = pathlib.Path(__file__).resolve().parent
for _p in (_ICI.parent / "agrume", _ICI.parent / "verif", _ICI.parent / "tools"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

import agrume_fcst as A                                     # noqa: E402
import score as SC                                          # noqa: E402


def _unite(r):
    return f"{r.get('source')}:{r.get('station_id')}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="/var/lib/bw-model-verif")
    ap.add_argument("--day", required=True)
    args = ap.parse_args()
    root = pathlib.Path(args.out)
    day = datetime.strptime(args.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    ag = SC.read_ndjson(root, SC.fcst_agrume_key(day))
    if not ag:
        print(f"❌ `{SC.fcst_agrume_key(day)}` absent sous {root}",
              file=sys.stderr)
        return 1
    # ⛔ LES ORIGINES SEULES. Une archive écrite après le L20 contient
    # déjà des sœurs +24 h : les prolonger fabriquerait des copies de
    # copies, et le compte serait faux du double.
    origines = [r for r in ag if not r.get("agrume_h24_copie")
                and not r.get("agrume_h48_copie")]
    soeurs24 = [r for r in ag if r.get("agrume_h24_copie")]
    print(f"▶ {args.day} — `{SC.fcst_agrume_key(day)}` : {len(ag)} lignes, "
          f"dont {len(origines)} d'origine et {len(soeurs24)} sœur(s) +24 h")

    fcst, bilan_parties = SC.fcst_parties(root, day)
    reduit = SC.read_ndjson(root, SC.fcst_reduit_key(day))
    src = [r for r in fcst + reduit if r.get("model") == A.H48_SOURCE]
    n_fcst = sum(1 for r in fcst if r.get("model") == A.H48_SOURCE)
    print(f"  source {A.H48_SOURCE} : {len(src)} ligne(s) — {n_fcst} dans "
          f"`fcst/` ({bilan_parties.get('parties_lues')} partie(s)), "
          f"{len(src) - n_fcst} dans `fcstreduit/`")
    par_src = collections.Counter(r.get("source") for r in src)
    print(f"    par réseau : {dict(par_src)}")
    if src:
        L = collections.Counter(len(r.get("speed") or []) for r in src)
        pas = collections.Counter(r.get("step_s") for r in src)
        runs = collections.Counter(A._run_ifs(r) for r in src)
        print(f"    longueurs {dict(L)} · pas {dict(pas)} · "
              f"run(s) IFS {dict(runs)}")

    soeurs, bilan = A.prolonger_h48(origines, src)
    print(f"  {A.dire_h48(bilan, (origines[0].get('agrume_run') if origines else None))}")

    par_modele = collections.Counter(r["model"] for r in soeurs)
    par_reseau = collections.Counter(r["source"] for r in soeurs)
    heures = [sum(1 for v in r["speed"] if v is not None) for r in soeurs]
    print(f"  sœurs +48 h : {dict(par_modele)} · par réseau "
          f"{dict(par_reseau)}")
    if heures:
        heures.sort()
        print(f"    heures servies par sœur : min {heures[0]}, médiane "
              f"{heures[len(heures) // 2]}, max {heures[-1]}")

    # Les balises d'AGRUME que la source ne couvre PAS, par réseau —
    # c'est le chiffre qui dit ce que la classe +48 h ne notera jamais.
    couvertes = {_unite(r) for r in src}
    manquantes = collections.Counter(
        r["source"] for r in origines if _unite(r) not in couvertes)
    print(f"    balises AGRUME sans ligne {A.H48_SOURCE} : "
          f"{dict(manquantes)} ({sum(manquantes.values())} lignes)")

    # ⛔ L'ÉCART DE CHAÎNE, MESURÉ ET NON SUPPOSÉ. À L22a la sœur EST la
    # ligne source recopiée : l'écart DOIT être exactement nul, sur
    # chaque case. S'il ne l'est pas, c'est une fenêtre mal découpée.
    par_unite = {_unite(r): r for r in src}
    ecarts, cases = [], 0
    for s in soeurs:
        a = par_unite[_unite(s)]
        for i, v in enumerate(s["speed"]):
            if v is None:
                continue
            cases += 1
            ecarts.append(abs(v - a["speed"][i]))
    print(f"  écart de chaîne AGRUME +48 h ↔ {A.H48_SOURCE} : "
          f"max {max(ecarts) if ecarts else 0:.6f} km/h sur {cases} cases "
          f"— {'EXACTEMENT NUL, comme attendu (c est la même ligne)' if ecarts and max(ecarts) == 0 else 'NON NUL : la fenêtre est mal découpée'}")

    # Ce que la journée notée à +48 h verra : la journée J+2.
    jour_note = day + timedelta(days=2)
    ms0 = int(jour_note.timestamp()) * 1000
    dedans = []
    for s in soeurs:
        t = SC.fcst_times_ms(s)
        n = sum(1 for i, v in enumerate(s["speed"])
                if v is not None and ms0 <= t[i] < ms0 + SC.DAY_MS)
        dedans.append(n)
    ok = sum(1 for n in dedans if n >= SC.MIN_HOURS_DAILY)
    print(f"  journée notée à +48 h : {jour_note:%Y-%m-%d} — {ok} sœur(s) sur "
          f"{len(soeurs)} atteignent le plancher de {SC.MIN_HOURS_DAILY} h "
          f"(médiane {sorted(dedans)[len(dedans) // 2] if dedans else 0} h)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
