#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  verif/test_confronter_quotidien.py — banc hors-ligne, sans réseau ni R2
#                                                        (13/08/2026)
#
#  ⚠️ Ce banc ne rejoue PAS la confrontation elle-même (ça, c'est
#  `test_radiosondage.py::confronter`, déjà couvert). Il protège les
#  TROIS choses que ce module ajoute par-dessus : le calcul du run
#  depuis l'échéance fixe, l'idempotence du journal, et le fait qu'une
#  station inactive ne consomme jamais un appel réseau.
#
#      python3 verif/test_confronter_quotidien.py
# ══════════════════════════════════════════════════════════════════════
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "agrume"))

import confronter_quotidien as CQ  # noqa: E402

echecs = 0


def verifier(nom, ok, detail=""):
    global echecs
    print(f"  {'✓' if ok else '✗'} {nom}" + (f"   {detail}" if detail else ""))
    if not ok:
        echecs += 1


print("── 1. LE RUN DEPUIS L'ÉCHÉANCE FIXE ──")
verifier("le lâcher de 12Z tombe sur le run de 06Z (12 − ECHEANCE_H)",
         CQ.run_iso("2026-08-10", "12") == "2026-08-10T06:00:00Z")
verifier("le lâcher de 00Z traverse minuit vers la veille",
         CQ.run_iso("2026-08-10", "00") == "2026-08-09T18:00:00Z")

print("\n── 2. L'IDEMPOTENCE DU JOURNAL ──")
entrees = [dict(wmo="06610", date="2026-08-10", heure="00", etat="confronte")]
verifier("un couple déjà journalisé n'est pas refait",
         CQ.deja_fait(entrees, "06610", "2026-08-10", "00"))
verifier("une autre heure, même station, n'est PAS marquée faite",
         not CQ.deja_fait(entrees, "06610", "2026-08-10", "12"))
verifier("une autre station, même date/heure, n'est PAS marquée faite",
         not CQ.deja_fait(entrees, "16064", "2026-08-10", "00"))

print("\n── 3. UNE STATION INACTIVE NE CONSOMME AUCUN APPEL RÉSEAU ──")
cuneo = next(s for s in CQ.RS.STATIONS if s["wmo"] == "16117")
verifier("Cuneo est bien la station inactive de ce fixture",
         not cuneo["active"])
e = CQ.confronter_un(cuneo, "2026-08-10", "00", crier=lambda *a: None)
verifier("⛔ court-circuitée AVANT tout accès réseau ou R2",
         e["etat"] == "ignore" and "inactive" in e["cause"])

print(f"\n{'✅' if echecs == 0 else '❌'} confronter_quotidien : "
      f"{'OK' if echecs == 0 else f'{echecs} échec(s)'}")
sys.exit(1 if echecs else 0)
