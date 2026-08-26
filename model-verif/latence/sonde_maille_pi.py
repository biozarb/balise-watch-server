#!/usr/bin/env python3
"""AROME-PI est-il servi en 0,01° ? — re-sonde du 26/08/2026.

La note du 10/08 mesurait : le service `aromepi/001` EXISTE mais ne
publie que les RAFALES ; `u`/`v`/`WIND_SPEED` n'y sont pas. Seize jours
ont passé, et cette réponse décide de la conception de la phase C.
On re-demande plutôt que de citer une note.

⚠️ `DescribeCoverage` coûte ~600 o. Huit requêtes, quota 100/min.
À lancer SUR LE VPS (la clé Météo-France n'en sort pas).
"""
import sys
from datetime import datetime, timedelta, timezone

sys.path[:0] = ["tools", "agrume"]
from portail import Portail, SERVICE_AROMEPI  # noqa: E402

CHAMPS = [
    "U_COMPONENT_OF_WIND__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND",
    "V_COMPONENT_OF_WIND__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND",
    "WIND_SPEED__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND",
    "WIND_SPEED_GUST__SPECIFIC_HEIGHT_LEVEL_ABOVE_GROUND",
]


def main():
    t = (datetime.now(timezone.utc) - timedelta(hours=3)).replace(
        minute=0, second=0, microsecond=0)
    run = t.strftime("%Y-%m-%dT%H:00:00Z")
    print(f"run témoin : {run}\n")
    for grille in ("001", "0025"):
        print(f"── aromepi/{grille}")
        p = Portail(SERVICE_AROMEPI, grille, journal=lambda *a, **k: None)
        for c in CHAMPS:
            nom = c.split("__")[0]
            try:
                r = "PRÉSENT" if p.existe(c, run) else "absent"
            except Exception as exc:                         # noqa: BLE001
                r = f"erreur {type(exc).__name__}: {exc}"[:80]
            print(f"    {nom:<24} {r}")
        print()


if __name__ == "__main__":
    main()
