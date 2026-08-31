#!/usr/bin/env python3
"""Lot L11 — LE CONTRÔLE FINAL : l'objet qui SERAIT publié, relu.

⛔ POURQUOI CE FICHIER EXISTE. Les bancs prouvent que le producteur fait
ce qu'on lui demande sur des archives fabriquées ; le rejeu prouve qu'il
tourne sur les vraies. Ni l'un ni l'autre ne dit ce qui ARRIVERAIT DANS
LA BASE. Ce script fait passer les lignes réelles par `score.daily_rows`
— le même chemin que la nuit — et relit ce qui en sort.

⚠️ LECTURE SEULE. Rien n'est écrit, ni sur R2, ni en base.

    PYTHONPATH=… python3 controle_objet_l11.py --day 2026-08-30
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import gzip
import json
import pathlib
import statistics
import sys

RACINE = pathlib.Path("/var/lib/bw-model-verif")
FLUX = ("obs/{a}/{m}/obs_{j}.ndjson.gz",
        "obswindsmobi/{a}/{m}/obswindsmobi_{j}.ndjson.gz",
        "obsinfoclimat/{a}/{m}/obsinfoclimat_{j}.ndjson.gz",
        "obsmf/{a}/{m}/obsmf_{j}.ndjson.gz",
        "obsaemet/{a}/{m}/obsaemet_{j}.ndjson.gz",
        "obsmetar/{a}/{m}/obsmetar_{j}.ndjson.gz")


def obs_du_jour(jour: dt.date) -> list[dict]:
    out = []
    for f in FLUX:
        p = RACINE / f.format(a=f"{jour:%Y}", m=f"{jour:%m}", j=f"{jour:%Y-%m-%d}")
        if p.exists():
            out += [json.loads(l) for l in gzip.open(p, "rt") if l.strip()]
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", required=True)
    ap.add_argument("--rapport", default="/tmp/controle-objet-l11.txt")
    a = ap.parse_args()

    import agrume_quart as Q
    import score as J

    jour = dt.datetime.strptime(a.day, "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    sortie: list[str] = []

    def dire(s=""):
        print(s)
        sortie.append(s)

    dire(f"▶ CONTRÔLE FINAL L11 — journée {a.day}, LECTURE SEULE")
    dire()
    rows = Q.rows_du_jour(jour, crier=dire)
    dire()

    # ══ 1. L'ARCHIVE, telle qu'elle serait écrite ══════════════════════
    dire("=" * 68)
    dire(" 1. L'ARCHIVE — ce que le producteur poserait sur R2")
    dire("=" * 68)
    par = collections.Counter((r["lead_h"], r["model"]) for r in rows)
    for (lead, mo), n in sorted(par.items()):
        dire(f"   lead {lead:>3} · {mo:<20} {n:>6} lignes")
    pts = [sum(1 for s in r["speed"] if s is not None) for r in rows]
    dire(f"   points servis par ligne : min {min(pts)} · médiane "
         f"{statistics.median(pts):.0f} · max {max(pts)}")
    rondes_servies = sum(
        1 for r in rows for i, s in enumerate(r["speed"])
        if s is not None and (r["t0"] + i * r["step_s"]) % 3600 == 0)
    dire(f"   ⭐ valeurs posées sur une HEURE RONDE : {rondes_servies} "
         f"{'✅ (aucune : pas de double comptage avec la classe -1/-2)' if not rondes_servies else '⛔'}")
    dire(f"   pas déclaré : {sorted({r['step_s'] for r in rows})} · "
         f"fetched_at : {sorted({r['fetched_at'] for r in rows})}")

    # ⭐ LA PROPRIÉTÉ QUI TIENT LA COMPARAISON : une seule population.
    pop: dict[tuple, set] = collections.defaultdict(set)
    for r in rows:
        pop[(r["lead_h"], r["station_id"])].add(
            tuple(i for i, s in enumerate(r["speed"]) if s is not None))
    divergentes = sum(1 for v in pop.values() if len(v) > 1)
    dire(f"   ⭐⭐ balises dont les TROIS sous-séries ne servent PAS les "
         f"mêmes points : {divergentes} "
         f"{'✅' if not divergentes else '⛔ (la comparaison ne serait pas appariée — faute du L9(c))'}")
    dire()

    # ══ 2. CE QUI ARRIVERAIT EN BASE ══════════════════════════════════
    dire("=" * 68)
    dire(" 2. `model_verif_daily` — après `daily_rows`, le chemin de la nuit")
    dire("=" * 68)
    obs_j = obs_du_jour(jour.date())
    obs_v = obs_du_jour(jour.date() - dt.timedelta(days=1))
    dire(f"   observations relues : {len(obs_j)} balises (J), "
         f"{len(obs_v)} (J−1)")
    daily, banded = J.daily_rows(jour, {0: rows}, obs_j, obs_v,
                                 utc_offset_s=7200)
    quarts = [d for d in daily if d["lead_h"] in J.LEADS_QUARTS]
    dire(f"   lignes produites : {len(daily)} dont {len(quarts)} au quart "
         f"d'heure")
    dire(f"   ⭐ `banded` (mémoire du caractère) : {len(banded)} "
         f"{'✅ (les séries en essai n écrivent pas trois mois de mémoire)' if not banded else '⛔'}")
    dire()
    dire(f"   {'lead':>5} {'modèle':<22} {'lignes':>7} {'n_hours':>18} "
         f"{'lead_exact_h':>13} {'err_vec_med':>12}")
    for lead in sorted(J.LEADS_QUARTS, reverse=True):
        for mo in J.MODELES_QUARTS:
            v = [d for d in quarts if d["lead_h"] == lead and d["model"] == mo]
            if not v:
                continue
            nh = [d["n_hours"] for d in v]
            le = [d["lead_exact_h"] for d in v]
            er = sorted(d["err_vec_med"] for d in v
                        if d.get("err_vec_med") is not None)
            dire(f"   {lead:>5} {mo:<22} {len(v):>7} "
                 f"{f'{min(nh)}–{max(nh)} (méd {statistics.median(nh):.0f})':>18} "
                 f"{statistics.median(le):>13.2f} "
                 f"{(statistics.median(er) if er else float('nan')):>12.3f}")
    hors = [d["n_hours"] for d in quarts if not 13 <= d["n_hours"] <= 15]
    dire(f"   ⭐ lignes hors [13 ; 15] : {len(hors)} "
         f"{'✅ (plancher ET plafond tenus)' if not hors else '⛔ ' + str(sorted(set(hors)))}")

    # Le retrait par la RÈGLE : qui disparaît, et de quel réseau ?
    servies = {r["station_id"] for r in rows}
    notees = {d["station_id"] for d in quarts}
    src = {r["station_id"]: r["source"] for r in rows}
    perdues = collections.Counter(src[s] for s in servies - notees)
    gardees = collections.Counter(src[s] for s in notees)
    dire()
    dire("   ── LE RETRAIT PAR LA RÈGLE, réseau par réseau ──")
    dire(f"   {'réseau':<12} {'servies':>8} {'notées':>8} {'écartées':>9}")
    for r_ in sorted(set(src.values())):
        s_ = sum(1 for x in servies if src[x] == r_)
        dire(f"   {r_:<12} {s_:>8} {gardees.get(r_, 0):>8} "
             f"{perdues.get(r_, 0):>9}")
    dire("   ⓘ aemet reporte à l'heure ronde : la sonde mesurait 0,0 % de")
    dire("     fenêtres non vides aux quarts. S'il disparaît ici, c'est le")
    dire("     plancher qui l'a fait — aucun nom de réseau n'est écrit")
    dire("     dans le code.")
    dire()

    # ══ 3. LA QUESTION DU LOT — et AUCUN verdict ══════════════════════
    dire("=" * 68)
    dire(" 3. LA RÉSERVE DE LA PHASE B — les chiffres, et aucun verdict")
    dire("=" * 68)
    dire("⛔ UNE JOURNÉE NE TRANCHE RIEN, et c'est écrit avant les")
    dire("   chiffres. `n_days = 1`. Ce qui suit est un POINT DE DÉPART")
    dire("   DE SÉRIE, pas une réponse — la même discipline que la")
    dire("   décision Q7 du L10.")
    dire()
    for lead in sorted(J.LEADS_QUARTS, reverse=True):
        idx: dict[str, dict[str, float]] = collections.defaultdict(dict)
        for d in quarts:
            if d["lead_h"] == lead and d.get("err_vec_med") is not None:
                idx[d["station_id"]][d["model"]] = d["err_vec_med"]
        appariees = [v for v in idx.values() if len(v) == 3]
        if not appariees:
            continue
        dire(f"   lead {lead} — {len(appariees)} balises où les TROIS ont "
             f"une erreur (comparaison APPARIÉE) :")
        for mo in J.MODELES_QUARTS:
            v = sorted(x[mo] for x in appariees)
            dire(f"      {mo:<22} médiane {statistics.median(v):>7.3f} "
                 f"km/h · moyenne {sum(v) / len(v):>7.3f}")
        w0, w1, w05 = (J.AGRUME_QUART_W0, J.AGRUME_QUART_W1,
                       J.AGRUME_QUART_W05)
        for nom, b in ((f"{w1} − {w0}", w1), (f"{w05} − {w0}", w05)):
            ec = sorted(x[b] - x[w0] for x in appariees)
            mieux = sum(1 for e in ec if e < 0)
            dire(f"      Δ apparié {nom:<38} médiane "
                 f"{statistics.median(ec):+.4f} · meilleur que le témoin "
                 f"dans {mieux}/{len(ec)} cases "
                 f"({100.0 * mieux / len(ec):.1f} %)")
        dire()

    pathlib.Path(a.rapport).write_text("\n".join(sortie) + "\n",
                                       encoding="utf-8")
    print(f"▶ rapport écrit : {a.rapport}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
