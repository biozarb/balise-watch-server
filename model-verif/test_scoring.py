#!/usr/bin/env python3
"""test_scoring.py — banc d'essai de `scoring.py`, et banc de PARITÉ.

    Session 08/08/2026.

Deux choses en une, et la seconde est la plus importante :

  1. Des assertions sur `scoring.py` seul, écrites dans la langue de
     son APPELANT (des séries horaires de balise, des journées, des
     modèles), pas dans celle de ses fonctions. C'est la leçon du
     défaut `aliasOf` du 07/08 : un banc qui interroge une fonction
     avec un vocabulaire que son seul appelant n'emploie jamais peut
     rester vert sur un code cassé.

  2. Une comparaison TERME À TERME avec le TypeScript. Le job du VPS
     est en Python, l'arithmétique de référence est en TS avec 199
     assertions derrière : sans cette comparaison, le portage serait
     une seconde vérité non vérifiée.

⚠️ L'ABSENCE DU FICHIER DE RÉSULTATS TS EST UN ÉCHEC, pas un saut.
Un banc de parité qui se saute tout seul quand l'autre moitié manque
finirait par être vert en permanence sans jamais rien comparer — le
même piège qu'un garde-fou qui vérifie la forme d'une réponse et pas
son contenu. Il faut `--unit-only` pour l'ignorer, et c'est explicite.

Usage :
    # 1. produire les entrées et les sorties Python
    python3 test_scoring.py --emit-fixtures /tmp/bw-parity/fixtures.json

    # 2. produire les sorties TS (depuis PWA/web/, cf. parity-scoring.ts)
    TZ=UTC node /tmp/bwp/scripts/parity-scoring.js \\
        /tmp/bw-parity/fixtures.json /tmp/bw-parity/ts_results.json

    # 3. comparer
    python3 test_scoring.py --ts-results /tmp/bw-parity/ts_results.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scoring as S  # noqa: E402

DAY_MS = 86_400_000
OK = 0
KO = 0


def check(label: str, got, want, tol: float = 1e-9):
    global OK, KO
    same = _same(got, want, tol)
    if same:
        OK += 1
    else:
        KO += 1
        print(f"  ❌ {label}\n       obtenu  : {got!r}\n       attendu : {want!r}")
    return same


def _same(a, b, tol: float) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= tol + tol * abs(b)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y, tol) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k], tol) for k in a)
    return a == b


# ══════════════════════════════════════════════════════════════════
#  1. ASSERTIONS DANS LA LANGUE DE L'APPELANT
# ══════════════════════════════════════════════════════════════════

def _beacon_day(day_index: int, base_speed=12.0, base_dir=190.0,
                cadence_s=240, jitter=True):
    """Une journée de balise Pioupiou : un relevé toutes les ~4 min.

    C'est EXACTEMENT la forme que rend `api.pioupiou.fr/v1/archive` une
    fois projetée sur `ObsSample`. Le banc parle donc la langue du seul
    appelant réel de `pair_series`, pas une langue à lui.
    """
    t0 = day_index * DAY_MS
    out = []
    n = 24 * 3600 // cadence_s
    for i in range(n):
        t = t0 + i * cadence_s * 1000
        hod = (t % DAY_MS) / 3_600_000
        # Cycle de brise : nul la nuit, maximum vers 15 h.
        cycle = max(0.0, math.sin((hod - 6) / 12 * math.pi))
        sp = base_speed * cycle + (0.7 if jitter and i % 3 == 0 else 0.0)
        di = (base_dir + (5 if jitter and i % 5 == 0 else 0)) % 360
        out.append(S.ObsSample(t=t, speed=round(sp, 3), dir=di))
    return out


def _hourly(day_index: int, n=24):
    return [day_index * DAY_MS + h * 3_600_000 for h in range(n)]


def unit_tests():
    print("── 1. scoring.py, dans la langue de son appelant ──")

    # ── appariement : une journée de balise contre une série horaire ──
    obs = _beacon_day(0)
    times = _hourly(0)
    fcst = [12.0 * max(0.0, math.sin((h - 6) / 12 * math.pi)) for h in range(24)]
    pairs = S.pair_series(times, fcst, [190.0] * 24, obs)
    check("24 heures modèle → 24 paires (la balise couvre la journée)",
          len(pairs), 24)
    # Les heures de bord n'ont qu'une demi-fenêtre : on regarde
    # l'intérieur de la journée, là où la fenêtre est complète.
    check("chaque heure agrège ~10 relevés (±20 min à 4 min de cadence)",
          all(10 <= p.n_obs <= 11 for p in pairs[1:-1]), True)

    # Un trou de mesure ne se comble pas : les heures concernées
    # disparaissent, elles ne sont pas interpolées. Trois heures de
    # silence n'en font perdre que deux — les heures 10 et 13 attrapent
    # encore des relevés dans leur demi-fenêtre, et c'est correct : la
    # fenêtre est centrée, pas rétrograde.
    troue = [o for o in obs if not (10 * 3_600_000 <= o.t < 13 * 3_600_000)]
    p2 = S.pair_series(times, fcst, [190.0] * 24, troue)
    check("3 h de balise muette → 2 heures perdues, jamais interpolées",
          len(p2), 22)

    # ── erreur vectorielle : le bon module du mauvais côté est puni ──
    p_oppose = [S.VerifPair(t=0, fcst_speed=20.0, fcst_dir=0.0,
                            obs_speed=20.0, obs_dir=180.0, n_obs=10)]
    err, vec = S.pair_error(p_oppose[0])
    check("20 km/h plein nord vs 20 km/h plein sud → 40 km/h d'erreur",
          err, 40.0)
    check("… et c'est bien une erreur vectorielle", vec, True)

    p_sans_girouette = S.VerifPair(t=0, fcst_speed=20.0, fcst_dir=0.0,
                                   obs_speed=17.0, obs_dir=None, n_obs=10)
    err2, vec2 = S.pair_error(p_sans_girouette)
    check("station sans girouette → repli scalaire, pas de pénalité", err2, 3.0)
    check("… et le repli est signalé", vec2, False)

    p_faible = S.VerifPair(t=0, fcst_speed=3.0, fcst_dir=0.0,
                           obs_speed=2.0, obs_dir=180.0, n_obs=10)
    check("sous 5 km/h la direction ne compte pas (girouette non fiable)",
          S.pair_error(p_faible), (1.0, False))

    # ── persistance : la veille ne ressemble pas à aujourd'hui ──
    # Deux journées DIFFÉRENTES, sinon la persistance est parfaite et
    # le test ne mesure plus rien (c'est justement le cas limite testé
    # juste en dessous).
    obs2 = _beacon_day(0, base_speed=8.0) + _beacon_day(1, base_speed=20.0)
    times_j2 = _hourly(1)
    fcst_parfait, dir_parfait = [], []
    for h in range(24):
        w = [o for o in obs2
             if abs(o.t - (DAY_MS + h * 3_600_000)) <= S.OBS_HALF_WINDOW_MS]
        sp, di, _ = S.mean_wind(w)
        fcst_parfait.append(sp)
        dir_parfait.append(di)
    pp = S.pair_series(times_j2, fcst_parfait, dir_parfait, obs2)
    skill, n, mse_m, mse_r = S.skill_vs_persistence(pp, obs2)
    check("un modèle qui rend exactement l'observation a une MSE nulle",
          round(mse_m, 9), 0.0)
    check("… et il bat « comme hier » quand hier était différent",
          mse_m < mse_r, True)
    check("… ce qui donne un skill de 1", round(skill, 9), 1.0)

    # Le cas qui a révélé le défaut n°1 du §16.4 : persistance PARFAITE.
    plat = [S.ObsSample(t=d * DAY_MS + h * 3_600_000, speed=10.0, dir=180.0)
            for d in (0, 1) for h in range(24)]
    pairs_plat = S.pair_series(_hourly(1), [14.0] * 24, [180.0] * 24, plat)
    skill_p, n_p, mm, mr = S.skill_vs_persistence(pairs_plat, plat)
    check("persistance parfaite → le skill est indéfini (ratio 0/0)", skill_p, None)
    check("… mais la comparaison directe, elle, tranche", mm > mr, True)
    absolu = S.absolute_score(pairs_plat, plat)
    check("… et `beats_persistence` répond NON, pas « je ne sais pas »",
          absolu.beats_persistence, False)

    # ── score absolu : deux nombres qu'un pilote lit ──
    check("erreur typique = médiane, pas moyenne quadratique",
          round(absolu.typical_err_kmh, 6), 4.0)

    # ── régimes : les six du §16.2 ──
    check("crête 40 km/h de 350° → flux de nord (pas « nord-est »)",
          S.classify_regime(40, 350), "fluxN")
    check("crête 40 km/h de 120° → flux d'est", S.classify_regime(40, 120), "fluxE")
    check("crête forte sans direction → non classable, pas « calme »",
          S.classify_regime(40, None), None)
    check("crête molle + brise au sol → thermique",
          S.classify_regime(6, 200, 14), "thermal")
    check("crête molle + rien au sol → calme", S.classify_regime(6, 200, 3), "calm")
    check("crête inconnue → None (on ne devine pas)",
          S.classify_regime(None, 200, 14), None)

    # Journée qui commence calme et bascule en flux de nord à midi :
    # c'est une journée de flux de nord, pas une journée moyenne.
    jour = [(h * 3_600_000, "calm" if h < 12 else "fluxN") for h in range(24)]
    check("journée qui bascule à midi → étiquetée flux de nord",
          S.dominant_regime(jour), "fluxN")
    nuit = [(h * 3_600_000, "calm" if h < 10 or h > 19 else None) for h in range(24)]
    check("un régime purement nocturne ne compte pas",
          S.dominant_regime(nuit), None)

    # ── accumulateurs : les deux défauts du §15.3 ──
    acc = S.Accumulator()
    for d in range(40):
        acc = S.accumulate(acc, 0.6 if d % 2 else 1.4, d * DAY_MS)
    check("40 jours alternant 0,6/1,4 → moyenne ≈ 1, PAS 1,21 "
          "(biais d'initialisation de l'EWMA)", abs(acc.mean - 1.0) < 0.02, True)

    acc2 = S.Accumulator()
    for d in range(60):
        acc2 = S.accumulate(acc2, 0.9 if d % 2 else 1.9, d * DAY_MS)
    check("un modèle qui alterne 0,9/1,9 a une moyenne bien déterminée",
          S.is_significant(acc2, 1.0), True)
    check("… mais elle n'est PAS applicable : rien à annoncer",
          S.is_announceable(acc2, 1.0), False)

    acc3 = S.Accumulator()
    for d in range(60):
        acc3 = S.accumulate(acc3, 1.30 + (0.02 if d % 2 else -0.02), d * DAY_MS)
    check("un biais régulier de +30 % à ±2 %, lui, s'annonce",
          S.is_announceable(acc3, 1.0), True)

    # Idempotence : le job doit pouvoir être relancé deux fois.
    a = S.Accumulator()
    a = S.accumulate(a, 1.2, 5 * DAY_MS)
    b = S.accumulate(a, 1.2, 5 * DAY_MS)
    check("relancer le job sur la même journée ne change rien", a, b)

    # Un trou de service ne doit pas peser comme un jour consécutif.
    conse = S.Accumulator()
    for d in range(2):
        conse = S.accumulate(conse, 1.0, d * DAY_MS)
    troue_acc = S.accumulate(S.accumulate(S.Accumulator(), 1.0, 0), 1.0, 30 * DAY_MS)
    check("après 30 jours d'arrêt, l'acquis ne pèse plus que moitié",
          round(troue_acc.sum_w, 6), round(1 + 0.5, 6))
    check("… alors que deux jours consécutifs pèsent presque deux",
          conse.sum_w > 1.97, True)

    # ── classement : refuser de trancher est un résultat ──
    serre = [{"model": "a", "typical_err_kmh": 5.0, "occurrences": 20},
             {"model": "b", "typical_err_kmh": 5.3, "occurrences": 20}]
    check("5,0 contre 5,3 km/h → aucun ne se détache",
          S.rank_by_regime(serre), (None, "tied"))
    net = [{"model": "a", "typical_err_kmh": 4.0, "occurrences": 20},
           {"model": "b", "typical_err_kmh": 9.0, "occurrences": 20}]
    check("4 contre 9 km/h → a gagne", S.rank_by_regime(net), ("a", "ok"))
    rare = [{"model": "a", "typical_err_kmh": 4.0, "occurrences": 3},
            {"model": "b", "typical_err_kmh": 9.0, "occurrences": 3}]
    check("3 occurrences du régime → pas assez, même si l'écart est net",
          S.rank_by_regime(rare), (None, "insufficient"))

    # ── bootstrap : déterminisme ──
    vals = [3.0, 4.1, 5.2, 4.8, 6.0, 3.3, 7.1, 4.4, 5.5, 4.9]
    check("deux exécutions du bootstrap donnent le même intervalle",
          S.bootstrap_ci(vals), S.bootstrap_ci(vals))
    med, lo, hi = S.bootstrap_ci(vals)
    check("… et l'intervalle encadre bien la médiane", lo <= med <= hi, True)


# ══════════════════════════════════════════════════════════════════
#  2. FIXTURES DE PARITÉ
# ══════════════════════════════════════════════════════════════════

def _obs_json(samples):
    return [{"t": o.t, "speed": o.speed, "dir": o.dir} for o in samples]


def _pair_json(p: S.VerifPair):
    return {"t": p.t, "fcstSpeed": p.fcst_speed, "fcstDir": p.fcst_dir,
            "obsSpeed": p.obs_speed, "obsDir": p.obs_dir, "nObs": p.n_obs}


def build_fixtures():
    """Un seul générateur, côté Python. Deux générateurs « équivalents »
    seraient la première chose à diverger."""
    obs_j0 = _beacon_day(0)
    obs_j01 = _beacon_day(0) + _beacon_day(1)
    obs_calme = [S.ObsSample(t=d * DAY_MS + h * 3_600_000, speed=10.0, dir=180.0)
                 for d in (0, 1) for h in range(24)]
    obs_sans_dir = [S.ObsSample(t=o.t, speed=o.speed, dir=None) for o in obs_j0]

    times = _hourly(0)
    fcst = [12.0 * max(0.0, math.sin((h - 6) / 12 * math.pi)) for h in range(24)]

    pairs_a = S.pair_series(times, fcst, [190.0] * 24, obs_j0)
    pairs_b = S.pair_series(_hourly(1), [14.0] * 24, [180.0] * 24, obs_calme)
    pairs_long = []
    for d in range(4):
        pairs_long += S.pair_series(_hourly(d), [11.0] * 24, [200.0] * 24,
                                    _beacon_day(d))

    return {
        "toUV": [[12, 190], [0, 0], [5, 359.5], [30, 45], [7.5, 271.3]],
        "fromUV": [[1, 1], [-1, 2], [0, -3], [0, 0], [-4.2, -0.1]],
        "angularDiff": [[10, 350], [350, 10], [0, 180], [0, 181], [359, 1]],
        "median": [[3, 1, 2], [4, 1, 2, 3], [], [5], [1, 1, 1, 9]],
        "quadrant": [350, 100, 200, 300, 45, 44.9, 315, 314.9, 0, 360, -10],
        "windBand": [0, 14.9, 15, 29.9, 30, 80],
        "meanWind": [
            {"samples": _obs_json(obs_j0[:20]), "minWindForDir": 5},
            # 350° et 10° : la moyenne arithmétique dirait 180° (plein sud).
            {"samples": [{"t": 0, "speed": 12, "dir": 350},
                         {"t": 1, "speed": 12, "dir": 10}], "minWindForDir": 5},
            {"samples": [{"t": 0, "speed": 2, "dir": 90},
                         {"t": 1, "speed": 3, "dir": 270}], "minWindForDir": 5},
            {"samples": [{"t": 0, "speed": None, "dir": 90}], "minWindForDir": 5},
            {"samples": _obs_json(obs_sans_dir[:30]), "minWindForDir": 5},
        ],
        "pairSeries": [
            {"times": times, "fcstSpeed": fcst, "fcstDir": [190.0] * 24,
             "obs": _obs_json(obs_j0)},
            {"times": times, "fcstSpeed": fcst, "fcstDir": None,
             "obs": _obs_json(obs_j0)},
            {"times": times, "fcstSpeed": [None] * 24, "fcstDir": [190.0] * 24,
             "obs": _obs_json(obs_j0)},
            {"times": times, "fcstSpeed": fcst, "fcstDir": [190.0] * 24,
             "obs": []},
        ],
        "pairError": [
            {"t": 0, "fcstSpeed": 20, "fcstDir": 0, "obsSpeed": 20,
             "obsDir": 180, "nObs": 10},
            {"t": 0, "fcstSpeed": 20, "fcstDir": 0, "obsSpeed": 17,
             "obsDir": None, "nObs": 10},
            {"t": 0, "fcstSpeed": 3, "fcstDir": 0, "obsSpeed": 2,
             "obsDir": 180, "nObs": 10},
            {"t": 0, "fcstSpeed": 12, "fcstDir": 190, "obsSpeed": 9,
             "obsDir": 240, "nObs": 8},
        ],
        "seriesError": [{"pairs": [_pair_json(p) for p in pairs_a]},
                        {"pairs": [_pair_json(p) for p in pairs_b]},
                        {"pairs": []}],
        "siteBias": [{"pairs": [_pair_json(p) for p in pairs_long], "minPairs": 48},
                     {"pairs": [_pair_json(p) for p in pairs_a], "minPairs": 48},
                     {"pairs": [_pair_json(p) for p in pairs_a], "minPairs": 10}],
        "persistenceReference": [
            {"obs": _obs_json(obs_j01), "t": DAY_MS + 14 * 3_600_000},
            {"obs": _obs_json(obs_j01), "t": 14 * 3_600_000},
        ],
        "skillVsPersistence": [
            {"pairs": [_pair_json(p) for p in pairs_b], "obs": _obs_json(obs_calme)},
            {"pairs": [_pair_json(p) for p in pairs_a], "obs": _obs_json(obs_j0)},
        ],
        "bootstrapCI": [
            {"values": [3.0, 4.1, 5.2, 4.8, 6.0, 3.3, 7.1, 4.4, 5.5, 4.9],
             "iterations": 500},
            {"values": [1.0, 2.0], "iterations": 500},
            {"values": [round(1 + (i * 37 % 23) / 10, 3) for i in range(60)],
             "iterations": 200},
        ],
        "absoluteScore": [
            {"pairs": [_pair_json(p) for p in pairs_b], "obs": _obs_json(obs_calme)},
            {"pairs": [_pair_json(p) for p in pairs_a], "obs": _obs_json(obs_j0)},
        ],
        "rankByRegime": [
            {"scores": [{"model": "a", "typicalErrKmh": 5.0, "occurrences": 20},
                        {"model": "b", "typicalErrKmh": 5.3, "occurrences": 20}],
             "minRelativeGap": 0.15},
            {"scores": [{"model": "a", "typicalErrKmh": 4.0, "occurrences": 20},
                        {"model": "b", "typicalErrKmh": 9.0, "occurrences": 20}],
             "minRelativeGap": 0.15},
            {"scores": [{"model": "a", "typicalErrKmh": 4.0, "occurrences": 3}],
             "minRelativeGap": 0.15},
            {"scores": [{"model": "a", "typicalErrKmh": 0.0, "occurrences": 20},
                        {"model": "b", "typicalErrKmh": 0.0, "occurrences": 20}],
             "minRelativeGap": 0.15},
        ],
        "classifyRegime": [[40, 350, None], [40, 120, None], [40, None, None],
                           [6, 200, 14], [6, 200, 3], [None, 200, 14],
                           [18, 90, 5], [25, 200, 0], [11.9, 10, 10]],
        "dominantRegime": [
            {"hourly": [[h * 3_600_000, "calm" if h < 12 else "fluxN"]
                        for h in range(24)], "startHour": 10, "endHour": 19},
            {"hourly": [[h * 3_600_000, None] for h in range(24)],
             "startHour": 10, "endHour": 19},
            {"hourly": [[h * 3_600_000, "calm" if h < 10 or h > 19 else None]
                        for h in range(24)], "startHour": 10, "endHour": 19},
            # Égalité stricte : le départage doit être déterministe.
            {"hourly": [[h * 3_600_000, "fluxS" if h % 2 else "fluxN"]
                        for h in range(10, 20)], "startHour": 10, "endHour": 19},
        ],
        "accumulate": [
            {"steps": [[0.6 if d % 2 else 1.4, d * DAY_MS] for d in range(40)],
             "halfLifeDays": 30, "reference": 1.0},
            {"steps": [[0.9 if d % 2 else 1.9, d * DAY_MS] for d in range(60)],
             "halfLifeDays": 30, "reference": 1.0},
            {"steps": [[1.30 + (0.02 if d % 2 else -0.02), d * DAY_MS]
                       for d in range(60)], "halfLifeDays": 30, "reference": 1.0},
            # Trou de service : la reprise ne doit pas peser comme un
            # jour consécutif.
            {"steps": [[1.0, 0], [1.0, 30 * DAY_MS], [1.0, 31 * DAY_MS]],
             "halfLifeDays": 30, "reference": 1.0},
            # Jour rejoué : idempotence.
            {"steps": [[1.2, 5 * DAY_MS], [1.2, 5 * DAY_MS], [1.3, 4 * DAY_MS]],
             "halfLifeDays": 30, "reference": 1.0},
        ],
    }


def python_results(fx):
    r = lambda x: None if x is None or not S._finite(x) else round(float(x), 9)  # noqa: E731
    to_obs = lambda a: [S.ObsSample(t=o["t"], speed=o["speed"], dir=o["dir"]) for o in a]  # noqa: E731
    to_pairs = lambda a: [S.VerifPair(t=p["t"], fcst_speed=p["fcstSpeed"],  # noqa: E731
                                      fcst_dir=p["fcstDir"], obs_speed=p["obsSpeed"],
                                      obs_dir=p["obsDir"], n_obs=p["nObs"]) for p in a]
    out = {}
    out["toUV"] = [[r(u), r(v)] for u, v in (S.to_uv(s, d) for s, d in fx["toUV"])]
    out["fromUV"] = [r(S.from_uv(u, v)) for u, v in fx["fromUV"]]
    out["angularDiff"] = [r(S.angular_diff(a, b)) for a, b in fx["angularDiff"]]
    out["median"] = [r(S.median(xs)) for xs in fx["median"]]
    out["quadrant"] = [S.quadrant(d) for d in fx["quadrant"]]
    out["windBand"] = [S.wind_band(s) for s in fx["windBand"]]
    out["meanWind"] = []
    for c in fx["meanWind"]:
        sp, di, n = S.mean_wind(to_obs(c["samples"]), c["minWindForDir"])
        out["meanWind"].append([r(sp), r(di), n])
    out["pairSeries"] = [
        [[p.t, r(p.fcst_speed), r(p.fcst_dir), r(p.obs_speed), r(p.obs_dir), p.n_obs]
         for p in S.pair_series(c["times"], c["fcstSpeed"], c["fcstDir"],
                                to_obs(c["obs"]))]
        for c in fx["pairSeries"]]
    out["pairError"] = []
    for p in fx["pairError"]:
        err, vec = S.pair_error(to_pairs([p])[0])
        out["pairError"].append([r(err), vec])
    out["seriesError"] = []
    for c in fx["seriesError"]:
        e = S.series_error(to_pairs(c["pairs"]))
        out["seriesError"].append([r(e.rms), r(e.med), e.n, r(e.vector_ratio),
                                   [r(x) for x in e.per_hour]])
    out["siteBias"] = []
    for c in fx["siteBias"]:
        b = S.site_bias(to_pairs(c["pairs"]), c["minPairs"])
        out["siteBias"].append([r(b.speed_ratio), r(b.dir_offset), b.n])
    out["persistenceReference"] = []
    for c in fx["persistenceReference"]:
        sp, di = S.persistence_reference(to_obs(c["obs"]), c["t"])
        out["persistenceReference"].append([r(sp), r(di)])
    out["skillVsPersistence"] = []
    for c in fx["skillVsPersistence"]:
        sk, n, mm, mr = S.skill_vs_persistence(to_pairs(c["pairs"]), to_obs(c["obs"]))
        out["skillVsPersistence"].append([r(sk), n, r(mm), r(mr)])
    out["bootstrapCI"] = []
    for c in fx["bootstrapCI"]:
        m, lo, hi = S.bootstrap_ci(c["values"], c["iterations"])
        out["bootstrapCI"].append([r(m), r(lo), r(hi)])
    out["absoluteScore"] = []
    for c in fx["absoluteScore"]:
        a = S.absolute_score(to_pairs(c["pairs"]), to_obs(c["obs"]))
        out["absoluteScore"].append([r(a.typical_err_kmh), r(a.worst_decile_kmh),
                                     r(a.skill), a.beats_persistence, a.n])
    out["rankByRegime"] = []
    for c in fx["rankByRegime"]:
        key, reason = S.rank_by_regime(
            [{"model": s["model"], "typical_err_kmh": s["typicalErrKmh"],
              "occurrences": s["occurrences"]} for s in c["scores"]],
            c["minRelativeGap"])
        out["rankByRegime"].append([key, reason])
    out["classifyRegime"] = [S.classify_regime(c, d, s)
                             for c, d, s in fx["classifyRegime"]]
    out["dominantRegime"] = [
        S.dominant_regime([(h[0], h[1]) for h in c["hourly"]],
                          c["startHour"], c["endHour"], utc_offset_s=0)
        for c in fx["dominantRegime"]]
    out["accumulate"] = []
    for c in fx["accumulate"]:
        acc = S.Accumulator()
        trace = []
        for value, day_ms in c["steps"]:
            acc = S.accumulate(acc, value, day_ms, c["halfLifeDays"])
            trace.append([r(acc.sum_w), r(acc.sum_wx), r(acc.sum_wx2), acc.days,
                          acc.last_day, r(acc.mean), r(acc.var), r(acc.std)])
        out["accumulate"].append({
            "trace": trace,
            "significant": S.is_significant(acc, c["reference"]),
            "regular": S.is_regular(acc, c["reference"]),
            "announceable": S.is_announceable(acc, c["reference"]),
        })
    return out


def parity(ts_path: str):
    print("── 2. parité Python ↔ TypeScript ──")
    fx = build_fixtures()
    py = python_results(fx)
    with open(ts_path, encoding="utf-8") as fh:
        ts = json.load(fh)
    manquantes = sorted(set(py) - set(ts))
    if manquantes:
        print(f"  ❌ sections absentes du fichier TS : {manquantes}")
        globals()["KO"] += len(manquantes)
    for section in sorted(set(py) & set(ts)):
        check(f"parité · {section}", py[section], ts[section])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--emit-fixtures", metavar="PATH",
                    help="écrit le jeu d'entrées pour le banc TS, puis sort")
    ap.add_argument("--ts-results", metavar="PATH",
                    help="sorties du banc TS, à comparer")
    ap.add_argument("--unit-only", action="store_true",
                    help="ignorer la parité — À N'UTILISER QUE SCIEMMENT")
    args = ap.parse_args()

    if args.emit_fixtures:
        os.makedirs(os.path.dirname(os.path.abspath(args.emit_fixtures)), exist_ok=True)
        with open(args.emit_fixtures, "w", encoding="utf-8") as fh:
            json.dump(build_fixtures(), fh)
        print(f"entrées écrites → {args.emit_fixtures}")
        return 0

    unit_tests()

    if args.ts_results:
        if not os.path.exists(args.ts_results):
            print(f"\n❌ {args.ts_results} est absent : le banc TS n'a pas tourné.")
            print("   La parité N'A PAS été vérifiée — ce n'est pas un succès.")
            return 1
        parity(args.ts_results)
    elif not args.unit_only:
        print("\n❌ Aucun --ts-results : la parité avec le TypeScript n'a pas été")
        print("   vérifiée. `scoring.py` duplique `src/lib/verifScore.ts` et")
        print("   consorts ; sans cette comparaison, la duplication n'est pas")
        print("   contrôlée. Utiliser --unit-only pour l'ignorer sciemment.")
        return 1

    print(f"\n{OK} assertions vertes, {KO} rouges.")
    return 1 if KO else 0


if __name__ == "__main__":
    sys.exit(main())
