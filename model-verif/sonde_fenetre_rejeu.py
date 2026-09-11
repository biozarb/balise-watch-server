#!/usr/bin/env python3
"""Sonde de la fenêtre rejouée — où passent vraiment ses octets (11/09/2026).

⛔ POURQUOI CETTE SONDE EXISTE. Le 10/09, l'enquête a estimé qu'élaguer
`units` aux 22 clés lues rendrait **≈ −1 500 Mo** (enquête §2.3 : 2 570
o/ligne → 1 301). L'élagage a été déployé le 10/09 à 08:20. La nuit du
10→11 a rendu **−41 Mo au jalon**. Cette sonde mesure, sur la vraie
fenêtre et dans le vrai processus, ce que chaque variante coûte — et
elle dit pourquoi l'estimation était fausse :

  · le dict D'UNE LIGNE ne pèse que 832 o sur ~2 830 ; les 2 000 autres
    sont ses VALEURS. Retirer dix clés ne retire que dix pointeurs et
    les rares valeurs qu'eux seuls tenaient → **99 o/ligne**, pas 1 269.
  · et la table du dict ne rétrécit même pas : CPython 3.13 loge 21
    clés dans 464 o et double à 832 dès la 22e. `CLES_REJEU` en a
    exactement 22 — UNE de trop. L'élagage 32 → 22 change de nombre de
    clés sans changer de classe de taille.

Les deux leviers qui restent sont donc ailleurs, et ils se mesurent ici :
partager les chaînes (les mêmes ~10 reviennent sur 1,3 M de lignes) et
sortir du dict (la ligne en tuple, l'ordre des clés une seule fois).

⚠️ LECTURE SEULE. `budget_new_days=0` interdit tout recalcul, donc tout
réseau et toute écriture de cache : elle ne lit que des
`replay_*.json.gz` déjà là. Rejouable à n'importe quelle heure.

⚠️ UN PROCESSUS PAR VARIANTE, toujours. Le tas n'est pas rendu au noyau
(enquête §2.4) : deux variantes dans le même processus donneraient à la
seconde le trou laissé par la première, donc un chiffre faux.

⚠️ DEUX FAMILLES, qu'on ne mélange pas. `brut|deploye|k21` passent par
le VRAI `replay_window` ; `telquel|memo|tuple` rejouent sa boucle pour
pouvoir changer ce que `replay_window` ne sait pas faire. Chaque famille
se compare à elle-même — la sonde le dit dans sa sortie.

    python3 sonde_fenetre_rejeu.py deploye
    python3 sonde_fenetre_rejeu.py tuple --jours 3
"""
from __future__ import annotations

import argparse
import gc
import gzip
import json
import pathlib
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import score as J      # noqa: E402

VIA_PROD = ("brut", "deploye", "k21")
VIA_BOUCLE = ("telquel", "memo", "tuple")


def _rss_mo() -> float:
    """`VmRSS` en Mo. ⚠️ C'est un PLANCHER : il exclut les pages parties
    en échange (enquête §2.4). Sur une machine au repos, il suffit."""
    for ligne in pathlib.Path("/proc/self/status").read_text().splitlines():
        if ligne.startswith("VmRSS:"):
            return float(ligne.split()[1]) / 1024.0
    return 0.0


class _Tout(frozenset):
    """Un `CLES_REJEU` qui contient tout — l'élagage neutralisé, sans
    toucher au source : `replay_window` lit le global du module."""

    def __contains__(self, _x) -> bool:
        return True


def par_replay_window(variante: str, root: pathlib.Path,
                      jour: datetime, jours: int) -> list:
    if variante == "brut":
        J.CLES_REJEU = _Tout()
    elif variante == "k21":
        # Exactement ce que mesure une sonde qui filtre la ligne du
        # CACHE : `unit` n'y est pas, il est ajouté par `replay_window`.
        # C'est, à une clé près, la ligne « 22 clés » de l'enquête §2.3.
        J.CLES_REJEU = frozenset(k for k in J.CLES_REJEU if k != "unit")
    rows, _ = J.replay_window(root, jour, None, 7200,
                              n_days=jours, budget_new_days=0)
    return rows


def par_boucle(variante: str, root: pathlib.Path,
               jour: datetime, jours: int) -> list:
    """La boucle de `replay_window`, rejouée pour pouvoir la modifier."""
    rows: list = []
    ordre: tuple | None = None
    for k in range(jours):
        p = J.replay_path(root, jour - timedelta(days=k))
        if not p.exists():
            continue
        brut = json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))
        memo: dict = {}
        for r in brut.get("rows") or []:
            r = dict(r)
            r["unit"] = f"{r['source']}:{r['station_id']}"
            r.pop(J.MU.MURPHY_KEY, None)
            r.pop(J.BF.CLE, None)
            r = {c: v for c, v in r.items() if c in J.CLES_REJEU}
            if variante in ("memo", "tuple"):
                for c, v in r.items():
                    if type(v) is str:
                        r[c] = memo.setdefault(v, v)
            if variante == "tuple":
                if ordre is None:
                    ordre = tuple(sorted(r))
                r = tuple(r.get(c) for c in ordre)
            rows.append(r)
        del brut
        gc.collect()
    return rows


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("variante", choices=VIA_PROD + VIA_BOUCLE)
    p.add_argument("--out", default="/var/lib/bw-model-verif")
    p.add_argument("--jours", type=int, default=3)
    p.add_argument("--fenetre", type=int, default=1309861,
                   help="lignes de la fenêtre de production, pour "
                        "l'extrapolation (défaut : la nuit du 11/09)")
    a = p.parse_args(argv)

    root = pathlib.Path(a.out)
    jour = (datetime.now(timezone.utc) - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0)

    gc.collect()
    avant = _rss_mo()
    rows = (par_replay_window if a.variante in VIA_PROD
            else par_boucle)(a.variante, root, jour, a.jours)
    gc.collect()
    apres = _rss_mo()

    n = len(rows)
    if not n:
        print(f"⚠️ aucune ligne : pas de cache de rejeu sous {root}/replay "
              f"pour les {a.jours} journées avant {jour:%Y-%m-%d}",
              file=sys.stderr)
        return 2
    delta = apres - avant
    o = delta * 1024 * 1024 / n
    famille = "replay_window" if a.variante in VIA_PROD else "boucle rejouée"
    large = len(rows[0]) if isinstance(rows[0], dict) else len(rows[0])
    print(f"variante   : {a.variante}  (famille : {famille} — ne se compare "
          f"qu'aux variantes de sa famille)")
    print(f"lignes     : {n} sur {a.jours} journée(s)")
    print(f"par ligne  : {large} champs, sizeof = {sys.getsizeof(rows[0])} o")
    print(f"RSS        : {avant:.0f} → {apres:.0f} Mo   (Δ {delta:.0f} Mo)")
    print(f"o / ligne  : {o:.0f}")
    print(f"→ fenêtre de production ({a.fenetre} lignes) : "
          f"{o * a.fenetre / 1024 / 1024:.0f} Mo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
