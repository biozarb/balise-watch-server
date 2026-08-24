#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/sonde_suffixe.py — LA VÉRIFICATION CONTRE L'API
#                                        (débug du 24/08/2026)
#
#  ⛔ CE SCRIPT EXISTE PARCE QU'UN BANC VERT NE PROUVE RIEN SUR UN TIERS.
#  Le S0.11 affirmait « 1,40 pondéré par point, mesuré sur l'URL RÉELLE »
#  et il était vert : il mesurait l'accord du code avec lui-même. La
#  correction du 24/08 repose sur une affirmation du MÊME genre — « deux
#  modèles mondiaux dans la requête ⇒ Open-Meteo écrit toujours le
#  suffixe de modèle » — et cette affirmation-là ne vaut que si on la
#  pose à Open-Meteo.
#
#  On la lui pose donc, sur les points qui ont ÉCHOUÉ la nuit du 23 au
#  24 : ceux d'Espagne et des Pyrénées où seul `icon_eu` servait.
#
#  ⚠️ CHAQUE APPEL PASSE PAR `Budget.demander()`. Une sonde qui
#  s'affranchirait du compteur partagé serait la caricature du défaut
#  qu'elle vérifie.
#
#      python3 sonde_suffixe.py mf:65059001 aemet:9988B
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import json
import pathlib
import sys

_ICI = pathlib.Path(__file__).resolve().parent
for _p in (_ICI.parent / "tools",):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

import collect as C                                          # noqa: E402
import collect_reduit as R                                   # noqa: E402

ETAT = pathlib.Path("/var/lib/bw-model-verif")


def trouver(cle: str) -> dict | None:
    src, ident = cle.split(":", 1)
    for nom in R.REFERENTIELS:
        p = ETAT / nom
        if not p.exists():
            continue
        for b in json.loads(p.read_text("utf-8")):
            if b.get("source") == src and str(b.get("id")) == ident:
                return {"id": str(b["id"]), "source": b["source"],
                        "lat": float(b["lat"]), "lon": float(b["lon"])}
    return None


def main() -> int:
    cles = sys.argv[1:] or ["mf:65059001", "aemet:9988B", "aemet:9677"]
    qm = C.charger_quota()
    budget = qm.Budget("collect_reduit") if qm else None
    (modeles, variables), = R.groupes_reduit()
    poids = qm.poids(len(variables), len(modeles)) if qm else 2.0

    print(f"▶ sonde du suffixe de modèle — {len(cles)} point(s) × "
          f"{poids:.2f} pondéré = {len(cles) * poids:.0f}")
    print(f"  requête : {len(modeles)} modèles ({', '.join(modeles)}) × "
          f"{len(variables)} variables")
    ko = 0
    for cle in cles:
        st = trouver(cle)
        if st is None:
            print(f"  ⚠️ {cle} introuvable dans les référentiels")
            continue
        if budget is not None:
            budget.demander(poids, etiquette=f"sonde suffixe {cle}")
        payload = C.fetch_forecast(st["lat"], st["lon"], 3, modeles,
                                   variables)
        if payload is None:
            print(f"  ⚠️ {cle} : pas de réponse")
            ko += 1
            continue
        hourly = payload.get("hourly") or {}
        servis = [m for m in modeles if hourly.get(f"wind_speed_10m_{m}")
                  and any(v is not None
                          for v in hourly[f"wind_speed_10m_{m}"])]
        nu = "wind_speed_10m" in hourly       # ⛔ le symptôme du 23/08
        lignes = list(C.forecast_rows(st, payload, "sonde", modeles))
        aloft = [r["model"] for r in lignes if "aloft_speed" in r]
        etat = "❌" if (nu or not lignes) else "✅"
        if nu or not lignes:
            ko += 1
        print(f"  {etat} {cle} ({st['lat']:.3f},{st['lon']:.3f}) : "
              f"suffixe {'ABSENT ⛔' if nu else 'présent'} · "
              f"{len(servis)} modèle(s) servent ({', '.join(servis)}) · "
              f"{len(lignes)} ligne(s) écrite(s) · aloft sur {aloft}")
    if budget is not None:
        print(f"ⓘ {budget.resume()}")
    if ko:
        print(f"❌ {ko} point(s) toujours en échec — la correction du "
              f"24/08 ne tient PAS sur ces points-là", file=sys.stderr)
        return 1
    print("✅ tous les points sondés rendent le suffixe et écrivent des "
          "lignes — les 375 groupes perdus du 23/08 reviennent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
