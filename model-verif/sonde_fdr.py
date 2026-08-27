#!/usr/bin/env python3
"""sonde_fdr.py — ce que Benjamini-Hochberg fait VRAIMENT au tableau.

    Lot L3, 27/08/2026.

⛔ POURQUOI CETTE SONDE EXISTE. Le lot L3 retire des rangs publiés.
Combien ? Le prompt du lot demande le chiffre, et l'audit en fait la
métrique de la proposition P5 (« le nombre de rangs publiés baisse,
compté »). Un contrôle de multiplicité qui n'en retirerait AUCUN
plusieurs nuits de suite ne serait pas une bonne nouvelle : ce serait
le signe que la famille est vide ou que la p-valeur n'arrive pas. Et
un qui les retirerait TOUS détruirait le produit. La seule façon de
savoir est de le jouer sur les données réelles.

⚠️ ELLE NE PASSE PAS PAR L'ARCHIVE R2 (lecture en HTTP 400 depuis le
pont Cowork, mesurée au lot L2) : elle relit `model_verif_daily` par
REST — ce chemin-là fonctionne — et rejoue `rolling_scores`. Elle ne
couvre donc PAS le chemin régime, qui a besoin du rejeu d'archive. Le
`m` réel d'une nuit complète est plus grand que celui qu'elle mesure,
et BH y est donc PLUS sévère, pas moins.

⚠️ LECTURE SEULE. Aucune écriture, aucun SQL, aucune purge.

    cd PWA/balise-watch-server && set -a && . ./.env && set +a
    python3 model-verif/sonde_fdr.py
"""
from __future__ import annotations

import os
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score as J          # noqa: E402
import inference as INF    # noqa: E402


#: Les SEULES colonnes que `_case_rows` lit. ⚠️ Un `select=*` sur
#: 298 122 lignes coûte des minutes de REST pour rien ; cette liste est
#: à tenir à jour avec `_case_rows`, et le banc qui la protège est la
#: sonde elle-même (une colonne oubliée fait tomber un chiffre à zéro,
#: pas planter le script — donc à relire, pas à croire).
COLONNES = ("day,source,station_id,model,lead_h,n_hours,err_vec_med,"
            "mse_model,mse_persist,mse_clim,err_vec_med_corr,"
            "mse_model_corr,bias_n_days")

#: Le cache disque de la sonde. ⛔ HORS des dossiers de Yann — c'est du
#: brouillon, pas un livrable, et il pèse des dizaines de Mo.
CACHE = os.path.join(os.path.expanduser("~"), ".sonde_fdr_daily.ndjson")
CACHE_ZONES = os.path.join(os.path.expanduser("~"), ".sonde_fdr_zones.json")

#: ⛔ FAIT D'ENVIRONNEMENT MESURÉ LE 27/08, ET IL COMMANDE TOUT CE QUI
#: SUIT : dans une session Cowork, un processus DÉTACHÉ (`setsid nohup
#: … & disown`) NE SURVIT PAS à la fin de l'appel `device_bash`
#: (vérifié : un `sleep 25` détaché n'écrit jamais son fichier). Tout
#: doit donc tenir dans les ~45 s d'un appel — d'où le cache disque et
#: le budget ci-dessous, et d'où le fait que cette sonde se rejoue
#: jusqu'à ce qu'elle finisse au lieu de tourner en arrière-plan.
BUDGET_S = float(os.environ.get("SONDE_BUDGET_S", "32"))


def _cache_json(chemin: str, produire):
    """Lit `chemin` s'il existe, sinon appelle `produire` et l'écrit."""
    import json
    if os.path.exists(chemin):
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    v = produire()
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(v, f)
    return v


def _lire_daily(sb, since: str) -> list[dict]:
    """`model_verif_daily` sur la fenêtre, avec un cache disque.

    ⚠️ REPRENABLE, et c'est nécessaire : ~300 pages de 1 000 lignes, que
    le shell du pont Cowork (45 s par appel) ne peut pas avaler d'un
    coup. Chaque page lue est écrite tout de suite ; un appel tué
    reprend où il s'est arrêté au lieu de tout refaire.
    """
    import json
    t0 = time.monotonic()
    lignes: list[dict] = []
    if os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            lignes = [json.loads(l) for l in f if l.strip()]
        print(f"  ⓘ cache : {len(lignes)} ligne(s) déjà lues "
              f"({CACHE})")
    page = 1000
    with open(CACHE, "a", encoding="utf-8") as f:
        while True:
            deb = len(lignes)
            lot = sb._page(f"model_verif_daily?select={COLONNES}"
                           f"&day=gte.{since}"
                           f"&order=day,source,station_id,model,lead_h,fcst_src",
                           deb, deb + page - 1)
            if not lot:
                break
            for r in lot:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            lignes.extend(lot)
            if len(lot) < page:
                break
            if time.monotonic() - t0 > BUDGET_S:
                print(f"    ⏸ {len(lignes)} lignes lues, budget "
                      f"({BUDGET_S:.0f} s) épuisé — RELANCER la sonde, "
                      f"elle reprendra ici.", flush=True)
                raise SystemExit(2)
    return lignes


def main() -> int:
    # ⓘ `Supabase()` lit `SUPABASE_URL`/`SUPABASE_SERVICE_KEY` dans
    # l'environnement lui-même — sourcer `.env` avant, jamais afficher.
    sb = J.Supabase()
    as_of = datetime.now(timezone.utc)
    day = as_of - timedelta(days=1)
    since = (day - timedelta(days=J.ROLLING_DAYS - 1)).strftime("%Y-%m-%d")

    print(f"▶ sonde FDR — fenêtre glissante depuis {since}")
    zones_raw = _cache_json(CACHE_ZONES,
                            lambda: sb.select("station_zone",
                                              order="source,station_id"))
    zone_of = {f"{z['source']}:{z['station_id']}": z for z in zones_raw}
    print(f"  balises rattachées à une zone : {len(zone_of)}")

    daily = _lire_daily(sb, since)
    print(f"  balise-jours lus : {len(daily)}")
    if not daily:
        print("  ⛔ rien à noter — sonde sans objet.")
        return 1

    # ⚠️ `with_ci=False` — le MÊME raccourci que `stability_report`, et
    # pour la même raison : il saute le bootstrap UNAIRE (500 tirages
    # par LIGNE, le poste le plus cher du run) et ne touche pas au
    # bootstrap APPARIÉ, d'où sortent les p-valeurs et les rangs. La
    # sonde mesure donc exactement les mêmes verdicts que la nuit, sans
    # payer les intervalles qu'elle n'affiche pas.
    units = []
    for d in daily:
        r = dict(d)
        r["unit"] = f"{d['source']}:{d['station_id']}"
        units.append(r)
    t0 = time.monotonic()
    scores = J._case_rows(units, zone_of, as_of, "rolling15", "all",
                          J.MIN_STATIONS_ZONE, with_ci=False)
    print(f"  lignes de score (rolling15) : {len(scores)} "
          f"({time.monotonic() - t0:.0f} s)")

    # ── AVANT le contrôle ───────────────────────────────────────────
    par_case: dict[tuple, list[dict]] = {}
    for r in scores:
        par_case.setdefault(J._cle_de_case(r), []).append(r)
    avant = Counter(r["rank_reason"] for r in scores)
    cases_ok_avant = sum(1 for l in par_case.values()
                         if any(x.get("rank_reason") == "ok" for x in l))
    ps = [p for l in par_case.values()
          for p in [next((x.get(J.FDR_P_BRUT) for x in l
                          if x.get(J.FDR_P_BRUT) is not None), None)]
          if p is not None]
    plancher = 2 / (INF.BOOTSTRAP_ITERATIONS + 1)

    print(f"\n  ── LA FAMILLE ──")
    print(f"  cases (zone × lead × échelon)          : {len(par_case)}")
    print(f"  cases où un test a été JOUÉ (m)        : {len(ps)}")
    print(f"  cases avec un rang publié              : {cases_ok_avant}")
    if ps:
        ps_tri = sorted(ps)
        n_planch = sum(1 for p in ps if p <= plancher + 1e-12)
        print(f"  p-valeurs : min {ps_tri[0]:.5f} · médiane "
              f"{ps_tri[len(ps_tri) // 2]:.5f} · max {ps_tri[-1]:.5f}")
        print(f"  ⚠️ au PLANCHER du tirage ({plancher:.5f}) : {n_planch} "
              f"case(s) — le bootstrap ne sait pas descendre plus bas")
        seuil1 = INF.ALPHA_FDR / len(ps)
        print(f"  seuil BH du 1er rang (α/m)             : {seuil1:.7f}")
        print(f"  ⓘ il faut donc au moins "
              f"{int(plancher / seuil1) + 1} case(s) au plancher pour "
              f"qu'UNE seule franchisse — propriété du tirage, pas du "
              f"phénomène")

    # ── APRÈS ───────────────────────────────────────────────────────
    rapport = J.appliquer_fdr(scores)
    apres = Counter(r["rank_reason"] for r in scores)
    b = rapport["brut"]
    print(f"\n  ── LE VERDICT (α_FDR = {INF.ALPHA_FDR}) ──")
    print(f"  survivants BH (k)                      : {b['k']} / {b['m']}")
    print(f"  seuil retenu                           : {b['seuil']}")
    print(f"  cases publiées AVANT                   : {b['publies_avant']}")
    print(f"  cases RETIRÉES par le FDR              : {b['retrogrades']}")
    print(f"  corrigé : m={rapport['corrige']['m']} · "
          f"retirées={rapport['corrige']['retrogrades']}")

    print(f"\n  ── rank_reason, avant → après ──")
    for k in sorted(set(avant) | set(apres), key=lambda x: str(x)):
        if avant.get(k, 0) != apres.get(k, 0) or k in ("ok", "fdr"):
            print(f"    {str(k):>18} : {avant.get(k, 0):>6} → {apres.get(k, 0):>6}")

    # ── n_comparable ────────────────────────────────────────────────
    chiffrees = [r for r in scores if r.get("n_comparable") is not None]
    melangees = sum(1 for r in chiffrees
                    if r["n_comparable"] < r.get("occurrences", 0))
    zero = sum(1 for r in chiffrees if r["n_comparable"] == 0)
    print(f"\n  ── n_comparable (noyau commun de la case) ──")
    print(f"  lignes avec la colonne                 : {len(chiffrees)}")
    print(f"  dont `n_comparable < occurrences`      : {melangees} "
          f"({100 * melangees / max(1, len(chiffrees)):.1f} %)")
    print(f"  dont noyau VIDE (`n_comparable = 0`)   : {zero} "
          f"({100 * zero / max(1, len(chiffrees)):.1f} %)")
    rangs = [r for r in scores if r.get("rank") is not None]
    mel_rangs = sum(1 for r in rangs
                    if (r.get("n_comparable") or 0) < r.get("occurrences", 0))
    print(f"  parmi les RANGS PUBLIÉS ({len(rangs)}) : {mel_rangs} "
          f"reposent sur une population partielle")
    return 0


if __name__ == "__main__":
    sys.exit(main())
