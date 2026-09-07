#!/usr/bin/env python3
"""La SECONDE lecture de `model_verif_daily` — celle du duel — mesurée
plutôt que supposée (07/09/2026, incident `bw-model-score`).

⛔ POURQUOI ELLE EST SUSPECTE. Le commentaire de `main` la dit « petite »
(quatre modèles, un lead, un réseau, sept colonnes) et c'était vrai le
27/08. Elle lit toujours par DÉCALAGE, sur la table même dont la
première lecture vient d'expirer — et `select_par_cle` avertit déjà en
toutes lettres que filtrer ne sauve pas : « la tranche
`lead_h=6 & metric=errKmh` (70 798 lignes) expire aussi à son offset le
plus profond, le filtre n'étant pas indexé ».

⚠️ MAIS « SUSPECTE » N'EST PAS « FAUTIVE ». Le duel couvre 30 jours là
où la fenêtre en couvre 15 : deux fois plus de jours, sur une tranche
bien plus étroite. Le seul chiffre qui décide est celui de sa
PROFONDEUR RÉELLE, et il se lit, il ne se déduit pas. Cette sonde
n'écrit rien.

    python3 sonde_duel_offset.py
"""
from __future__ import annotations

import pathlib
import sys
import time
from datetime import date, timedelta

_ICI = pathlib.Path(__file__).resolve().parent
if str(_ICI) not in sys.path:
    sys.path.insert(0, str(_ICI))

import duel as DUEL                                         # noqa: E402
import score as SC                                          # noqa: E402


def main() -> int:
    jour = date.today() - timedelta(days=1)
    depuis = (jour - timedelta(days=DUEL.DUEL_DAYS - 1)).strftime("%Y-%m-%d")
    q = DUEL.query_duel(depuis)
    print(f"duel : {DUEL.DUEL_DAYS} jours, day >= {depuis}")
    print(f"requête : {q}\n")

    sb = SC.Supabase()
    t0 = time.monotonic()
    lignes = sb.select("model_verif_daily", q, order=SC.CLE_DAILY)
    dt = time.monotonic() - t0
    print(f"lecture par DÉCALAGE : {len(lignes):>7,} lignes en {dt:6.1f} s"
          .replace(",", " "))
    print(f"  profondeur atteinte : offset {max(0, len(lignes) - sb.PAGE)}")
    print(f"  pages : {-(-len(lignes) // sb.PAGE)}")
    if lignes:
        print(f"  colonnes : {', '.join(sorted(lignes[0]))}")

    # ⚠️ LA MARGE, PAS SEULEMENT LE TEMPS TOTAL. Ce qui tue, c'est la
    # DERNIÈRE page : c'est la seule qui court au fond de la table. On
    # la redemande seule, chronométrée, pour la comparer aux 8 s que
    # Supabase accorde.
    if len(lignes) > sb.PAGE:
        deb = len(lignes) - sb.PAGE
        racine = f"model_verif_daily{q}&order={SC.CLE_DAILY}"
        t1 = time.monotonic()
        derniere = sb._page(racine, deb, deb + sb.PAGE - 1)
        dt1 = time.monotonic() - t1
        print(f"\ndernière page seule  : offset {deb}, "
              f"{len(derniere)} lignes en {dt1:.2f} s "
              f"(la coupure serveur est à 8 s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
