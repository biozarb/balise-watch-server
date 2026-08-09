#!/usr/bin/env python3
"""test_events.py — banc d'essai d'`events.py`, et banc de PARITÉ.

    Session 08/08/2026 (lot F).

═══ CE QUE CE BANC EXISTE POUR ATTRAPER ═══

`scripts/parity-scoring.ts` ne couvre que `verifScore`, `modelCharacter`
et `regime`. `windEvents.ts` n'y a JAMAIS figuré — vérifié le 08/08.
Jusqu'à ce fichier, un portage Python incorrect de la détection
d'événements passait TOUS les bancs existants sans qu'aucun ne rougisse :
`test-verif.ts` teste le TypeScript, `test_scoring.py` teste une autre
partie du Python, et personne ne les confrontait.

═══ ET SURTOUT : LA PARITÉ SUR DONNÉES RÉELLES ═══

⚠️ Une parité sur séries synthétiques ne prouve pas grand-chose. Les
séries que je fabrique sont propres : pas de trou de plusieurs heures,
pas de balise qui émet deux fois la même seconde, pas de vent qui
oscille exactement autour d'un seuil. Ce sont précisément ces cas-là qui
font diverger deux portages.

Ce banc lit donc, quand elle est disponible, une VRAIE journée
d'archive R2 (`--archive DIR --day YYYY-MM-DD`) et soumet aux deux
langages les séries brutes de plusieurs dizaines de balises réelles,
observations ET prévisions. La comparaison porte alors sur les
événements un par un : type, instant, seuil.

Sans archive, le banc tourne quand même sur ses fixtures synthétiques et
le DIT — un banc qui se saute en silence ment sur sa couverture.

Usage :
    # 1. banc local seul
    python3 test_events.py

    # 2. émettre les fixtures (avec archive réelle si on l'a)
    python3 test_events.py --emit-fixtures /tmp/bw-events/fixtures.json \\
        --archive /tmp/bw-arch --day 2026-08-07

    # 3. produire les sorties TS (depuis PWA/web/, cf. parity-events.ts)
    node /tmp/bwe/scripts/parity-events.js \\
        /tmp/bw-events/fixtures.json /tmp/bw-events/ts_results.json

    # 4. comparer
    python3 test_events.py --ts-results /tmp/bw-events/ts_results.json
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import pathlib
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import events as E  # noqa: E402
import scoring as S  # noqa: E402

DAY_MS = 86_400_000
OK = 0
KO = 0


def check(label: str, got, want, tol: float = 1e-9):
    global OK, KO
    if _same(got, want, tol):
        OK += 1
        return True
    KO += 1
    print(f"  ❌ {label}\n       obtenu  : {got!r}\n       attendu : {want!r}")
    return False


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
#  SÉRIES DE RÉFÉRENCE
# ══════════════════════════════════════════════════════════════════

def breeze_day(day_index: int = 0, turn_at_h: float = 14.0,
               dir_before: float = 200.0, dir_after: float = 20.0,
               speed: float = 14.0, cadence_s: int = 240) -> list[S.ObsSample]:
    """Une journée de balise Pioupiou : un relevé toutes les ~4 min, une
    bascule franche à l'heure dite. Le vent reste au-dessus de
    `min_wind_kmh` des deux côtés, sinon il n'y a rien à détecter."""
    t0 = day_index * DAY_MS
    out = []
    k = 0
    while k * cadence_s < 86_400:
        t = t0 + k * cadence_s * 1000
        h = (k * cadence_s) / 3600
        out.append(S.ObsSample(t=t, speed=speed,
                               dir=dir_before if h < turn_at_h else dir_after))
        k += 1
    return out


def ramping_day(day_index: int = 0, cadence_s: int = 240) -> list[S.ObsSample]:
    """Vent qui monte en marches : 8 km/h le matin, 22 à midi, 32 le
    soir. Franchit 20, 25 et 30 — les trois seuils de `ramp` — et
    franchit aussi le seuil d'établissement de 12."""
    t0 = day_index * DAY_MS
    out = []
    k = 0
    while k * cadence_s < 86_400:
        h = (k * cadence_s) / 3600
        sp = 8.0 if h < 8 else (22.0 if h < 13 else 32.0)
        out.append(S.ObsSample(t=t0 + k * cadence_s * 1000, speed=sp, dir=180.0))
        k += 1
    return out


def yielding_day(day_index: int = 0, yield_at_h: float = 15.0,
                 cadence_s: int = 240) -> list[S.ObsSample]:
    """La brise d'aval tient, puis cède au flux de nord. Le sol passe de
    190° (brise, opposée au flux) à 010° (aligné sur le flux)."""
    t0 = day_index * DAY_MS
    out = []
    k = 0
    while k * cadence_s < 86_400:
        h = (k * cadence_s) / 3600
        if h < 9:
            sp, d = 4.0, 190.0            # trop faible : pas de brise établie
        elif h < yield_at_h:
            sp, d = 15.0, 190.0           # la brise tient tête
        else:
            sp, d = 26.0, 10.0            # le flux a gagné
        out.append(S.ObsSample(t=t0 + k * cadence_s * 1000, speed=sp, dir=d))
        k += 1
    return out


def steady_crest(day_index: int = 0, dir_deg: float = 5.0,
                 speed: float = 34.0) -> list[E.CrestSample]:
    """Un flux d'altitude ÉTABLI et STABLE : le décor qui ne bouge pas.
    Cadence horaire, comme un modèle."""
    t0 = day_index * DAY_MS
    return [E.CrestSample(t=t0 + h * 3_600_000, speed_kmh=speed, dir_deg=dir_deg)
            for h in range(25)]


# ══════════════════════════════════════════════════════════════════
#  1. ASSERTIONS DANS LA LANGUE DE L'APPELANT
# ══════════════════════════════════════════════════════════════════

def bench_local():
    print("── 1. détection ──")
    s = E.resample(breeze_day())
    check("le rééchantillonnage rend un point tous les 10 min",
          [s[1].t - s[0].t, s[2].t - s[1].t], [600_000, 600_000])

    rev = E.detect_reversals(s)
    check("une bascule franche donne UN événement, pas cinq", len(rev), 1)
    check("la rotation mesurée est bien de 180°", round(rev[0].turn), 180)

    trous = [o for o in breeze_day() if not (10 * 3600 <= (o.t % DAY_MS) / 1000 < 13 * 3600)]
    st = E.resample(trous)
    # ⚠️ La borne testée n'est pas celle du trou mais celle du trou MOINS
    # la demi-fenêtre de lissage (±15 min) : les 15 premières minutes du
    # trou voient encore des relevés d'avant, et c'est le comportement
    # voulu — un lissage glissant déborde, par construction. Ce qui ne
    # doit jamais arriver, c'est un point AU MILIEU du trou, là où plus
    # aucun relevé n'est en vue.
    check("un trou de 3 h ne fabrique aucun point interpolé en son milieu",
          any(10.5 * 3600 <= (p.t % DAY_MS) / 1000 < 12.5 * 3600 for p in st),
          False)

    rr = E.detect_ramps(E.resample(ramping_day()))
    check("les trois seuils de renforcement sont franchis",
          sorted({e.threshold for e in rr}), [20, 25, 30])

    od = E.detect_onset_drop(E.resample(ramping_day()), 12)
    check("un établissement, aucune chute (le vent ne retombe pas)",
          [sum(1 for e in od if e.type == "onset"),
           sum(1 for e in od if e.type == "drop")], [1, 0])

    calme = [S.ObsSample(t=k * 240_000, speed=2.0, dir=float((k * 37) % 360))
             for k in range(360)]
    check("sous 5 km/h, la girouette n'invente aucune bascule",
          len(E.detect_all(calme)), 0)

    print("── 2. appariement et contingence ──")
    obs = [E.WindEvent("reversal", 12 * 3_600_000),
           E.WindEvent("ramp", 15 * 3_600_000, threshold=20)]
    fcst = [E.WindEvent("reversal", 12 * 3_600_000 - 40 * 60_000),
            E.WindEvent("ramp", 15 * 3_600_000, threshold=30)]
    m = E.match_events(obs, fcst)
    check("1 succès, 1 raté, 1 fausse alarme",
          [sum(1 for x in m if x.outcome == o)
           for o in ("hit", "miss", "false_alarm")], [1, 1, 1])
    hit = next(x for x in m if x.outcome == "hit")
    check("le décalage est SIGNÉ et négatif quand le modèle est en avance",
          hit.timing_err_min, -40)
    check("un ramp de seuil différent ne s'apparie pas",
          [x.outcome for x in m if x.type == "ramp"], ["miss", "false_alarm"])

    loin = E.match_events([E.WindEvent("reversal", 0)],
                          [E.WindEvent("reversal", 100 * 60_000)])
    check("au-delà de la tolérance : raté + fausse alarme, jamais un succès",
          sorted(x.outcome for x in loin), ["false_alarm", "miss"])

    sc = E.score_events(m)
    check("POD = 0,5", sc.pod, 0.5)
    check("FAR = 0,5", sc.far, 0.5)
    check("biais de fréquence = 1 (autant annoncé que survenu)",
          sc.frequency_bias, 1.0)
    check("scoreEvents ne filtre rien : il rend un POD même sur 2 cas",
          sc.hits + sc.misses, 2)

    proches = E.match_events(
        [E.WindEvent("onset", 0), E.WindEvent("onset", 30 * 60_000)],
        [E.WindEvent("onset", 35 * 60_000), E.WindEvent("onset", 5 * 60_000)])
    check("les couples les plus proches sont appariés en premier",
          sorted(x.timing_err_min for x in proches if x.outcome == "hit"),
          [5, 5])


    print("── 3. confirmation par le réseau ──")
    grappe = [("A", [E.WindEvent("reversal", 0)]),
              ("B", [E.WindEvent("reversal", 12 * 60_000)]),
              ("C", [E.WindEvent("reversal", 20 * 60_000)]),
              ("Z", [E.WindEvent("reversal", 9 * 3_600_000)])]
    cons = E.consolidate_network(grappe)
    check("la grappe à 3 balises est retenue, la balise seule est écartée",
          len(cons), 1)
    check("l'instant retenu est la MÉDIANE de la grappe",
          cons[0].t, 12 * 60_000)
    check("une même balise deux fois ne fait pas quorum",
          len(E.consolidate_network([("A", [E.WindEvent("onset", 0),
                                            E.WindEvent("onset", 60_000)])])), 0)

    # ⚠️ LE PIÈGE DU 07/08, EN UNE ASSERTION. Trois balises à t, t+12 et
    # t+20 min forment UNE grappe par chaînage. Avec des tranches fixes
    # de 30 min ancrées sur zéro, celle de t+20 basculerait dans le seau
    # suivant si la première tombait à t=25 min — et la même bascule
    # compterait deux fois.
    decale = [("A", [E.WindEvent("reversal", 25 * 60_000)]),
              ("B", [E.WindEvent("reversal", 37 * 60_000)]),
              ("C", [E.WindEvent("reversal", 45 * 60_000)])]
    check("chaînage temporel : une seule grappe même à cheval sur 30 min",
          len(E.consolidate_network(decale)), 1)

    check("deux types différents ne se mélangent jamais dans une grappe",
          len(E.consolidate_network([("A", [E.WindEvent("onset", 0)]),
                                     ("B", [E.WindEvent("drop", 60_000)])])), 0)
    check("deux seuils de ramp différents ne se mélangent pas non plus",
          len(E.consolidate_network([("A", [E.WindEvent("ramp", 0, threshold=20)]),
                                     ("B", [E.WindEvent("ramp", 60_000, threshold=30)])])), 0)

    print("── 4. la brise qui cède (breeze_yield) ──")
    ep = E.detect_conflicts(yielding_day(), steady_crest())
    check("un épisode détecté sur la journée type", len(ep), 1)
    if ep:
        check("la résistance est MESURÉE, pas recopiée du paramètre",
              ep[0].hold_minutes != E.DEFAULT_CONFLICT.min_hold_ms // 60_000
              or ep[0].hold_minutes >= 90, True)
        check("l'instant retenu tombe dans la plage locale 9 h - 20 h",
              9 <= (ep[0].yield_at % DAY_MS) / 3_600_000 <= 20, True)

    # ⚠️ Le décor doit être STABLE. Un flux de crête qui tourne de 90°
    # pendant l'épisode, c'est un changement de temps — banal, et pas ce
    # qu'on cherche.
    tournant = [E.CrestSample(t=h * 3_600_000, speed_kmh=34.0,
                              dir_deg=float((h * 8) % 360)) for h in range(25)]
    check("un flux d'altitude qui tourne n'est pas un conflit brise/flux",
          len(E.detect_conflicts(yielding_day(), tournant)), 0)

    faible = [E.CrestSample(t=h * 3_600_000, speed_kmh=8.0, dir_deg=5.0)
              for h in range(25)]
    check("sans flux de crête, il n'y a rien à contrer",
          len(E.detect_conflicts(yielding_day(), faible)), 0)

    # ⚠️ L'heure est celle du SITE, jamais celle de la machine. Décalé de
    # −10 h, l'épisode de 15 h locales tombe à 5 h : hors plage.
    p_dec = E.ConflictParams(**{**E.DEFAULT_CONFLICT.__dict__,
                                "utc_offset_s": -10 * 3600})
    check("utc_offset_s décale réellement la plage horaire retenue",
          len(E.detect_conflicts(yielding_day(), steady_crest(), p_dec)), 0)

    if ep:
        deux = E.consolidate_conflicts([("A", ep), ("B", ep)])
        check("un épisode vu par deux balises passe le quorum réseau",
              [len(deux), deux[0].stations if deux else None], [1, 2])
        check("le même épisode vu par une seule balise est écarté",
              len(E.consolidate_conflicts([("A", ep)])), 0)
        ev = E.conflicts_as_events(ep)
        check("la conversion en WindEvent garde l'instant de la bascule",
              [ev[0].type, ev[0].t], ["breeze_yield", ep[0].yield_at])

    print("── 5. l'arrondi de JavaScript, pas celui de Python ──")
    # `round(0.5)` rend 0 en Python (arrondi au pair) et 1 en JS.
    check("un décalage de +30 s s'arrondit à +1 min, comme Math.round",
          E._js_round(0.5), 1)
    check("un décalage de −30 s s'arrondit à 0, comme Math.round",
          E._js_round(-0.5), 0)
    check("et +90 s à +2 min (et non +1 comme l'arrondi au pair)",
          E._js_round(1.5), 2)


# ══════════════════════════════════════════════════════════════════
#  2. FIXTURES DE PARITÉ
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ LES ENTRÉES VIENNENT D'UN SEUL CÔTÉ, exprès. Deux générateurs
# « équivalents » écrits dans deux langages seraient la première chose à
# diverger, et la divergence se lirait comme un défaut de portage.

def _obs_json(samples):
    return [{"t": o.t, "speed": o.speed, "dir": o.dir} for o in samples]


def _crest_json(samples):
    return [{"t": c.t, "speedKmh": c.speed_kmh, "dirDeg": c.dir_deg}
            for c in samples]


def _ev_json(e: E.WindEvent):
    return {"type": e.type, "t": e.t, "turn": e.turn,
            "dirBefore": e.dir_before, "dirAfter": e.dir_after,
            "speedBefore": e.speed_before, "speedAfter": e.speed_after,
            "threshold": e.threshold}


def _match_json(m: E.EventMatch):
    return {"type": m.type, "outcome": m.outcome,
            "timingErrMin": m.timing_err_min, "obsT": m.obs_t,
            "fcstT": m.fcst_t, "threshold": m.threshold}


def _ep_json(e: E.ConflictEpisode):
    return {"holdStart": e.hold_start, "yieldAt": e.yield_at,
            "crestDir": e.crest_dir, "crestSpeed": e.crest_speed,
            "breezeDir": e.breeze_dir, "breezeSpeed": e.breeze_speed,
            "afterDir": e.after_dir, "holdMinutes": e.hold_minutes,
            "stations": e.stations}


def _p_json(p: E.DetectParams):
    return {"stepMs": p.step_ms, "smoothMs": p.smooth_ms,
            "minTurnDeg": p.min_turn_deg, "minWindKmh": p.min_wind_kmh,
            "holdMs": p.hold_ms, "rampThresholds": list(p.ramp_thresholds)}


def _cp_json(p: E.ConflictParams):
    return {"minCrestKmh": p.min_crest_kmh, "minOpposeDeg": p.min_oppose_deg,
            "minBreezeKmh": p.min_breeze_kmh, "minHoldMs": p.min_hold_ms,
            "maxAlignDeg": p.max_align_deg, "minAfterMs": p.min_after_ms,
            "maxCrestDriftDeg": p.max_crest_drift_deg,
            "hours": list(p.hours), "utcOffsetS": p.utc_offset_s}


# ── lecture d'une vraie journée d'archive ─────────────────────────

def _read_ndjson(path: pathlib.Path):
    if not path.exists():
        return []
    raw = path.read_bytes()
    try:
        text = gzip.decompress(raw).decode("utf-8")
    except OSError:
        text = raw.decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _obs_of(row: dict) -> list[S.ObsSample]:
    t = row.get("t") or []
    sp = row.get("speed") or []
    di = row.get("dir") or []
    return [S.ObsSample(t=int(ts) * 1000,
                        speed=sp[i] if i < len(sp) else None,
                        dir=di[i] if i < len(di) else None)
            for i, ts in enumerate(t)]


def _fcst_of(row: dict) -> list[S.ObsSample]:
    """Une prévision horaire, présentée comme une série de relevés.

    ⚠️ C'est légitime et c'est même le point : la détection doit être la
    MÊME des deux côtés de la comparaison. Si on détectait les bascules
    observées avec un algorithme et les bascules prévues avec un autre,
    on mesurerait l'écart entre deux algorithmes, pas la qualité du
    modèle.
    """
    n = len(row.get("speed") or [])
    t0, step = int(row["t0"]), int(row["step_s"])
    sp = row.get("speed") or []
    di = row.get("dir") or []
    return [S.ObsSample(t=(t0 + i * step) * 1000,
                        speed=sp[i] if i < len(sp) else None,
                        dir=di[i] if i < len(di) else None)
            for i in range(n)]


def _crest_of(row: dict) -> list[E.CrestSample]:
    n = len(row.get("aloft_speed") or [])
    t0, step = int(row["t0"]), int(row["step_s"])
    sp = row.get("aloft_speed") or []
    di = row.get("aloft_dir") or []
    return [E.CrestSample(t=(t0 + i * step) * 1000,
                          speed_kmh=sp[i] if i < len(sp) else None,
                          dir_deg=di[i] if i < len(di) else None)
            for i in range(n)]


def load_archive(archive: str, day: str, max_stations: int = 24):
    """Rend (obs par balise, prévisions par balise, crête par balise).

    ⚠️ On prend les balises les mieux fournies, pas les premières venues :
    une balise à trois relevés ne produit aucun événement et ne prouve
    donc rien sur le portage. Le tri est déterministe (nombre de relevés
    décroissant, puis identifiant) pour que deux exécutions du banc
    soumettent exactement les mêmes séries.
    """
    root = pathlib.Path(archive)
    obs_rows = _read_ndjson(root / "obs" / f"obs_{day}.ndjson.gz")
    fcst_rows = _read_ndjson(root / "fcst" / f"fcst_{day}.ndjson.gz")
    if not obs_rows:
        return {}, {}, {}
    obs = {f"{r['source']}:{r['station_id']}": _obs_of(r) for r in obs_rows}
    keys = sorted(obs, key=lambda k: (-len(obs[k]), k))[:max_stations]
    obs = {k: obs[k] for k in keys}

    fcst: dict[tuple[str, str], list[S.ObsSample]] = {}
    crest: dict[str, list[E.CrestSample]] = {}
    for r in fcst_rows:
        key = f"{r['source']}:{r['station_id']}"
        if key not in obs:
            continue
        fcst[(key, r["model"])] = _fcst_of(r)
        if "aloft_speed" in r and key not in crest:
            crest[key] = _crest_of(r)
    return obs, fcst, crest


def build_fixtures(archive: str | None = None, day: str | None = None):
    p = _p_json(E.DEFAULT_DETECT)
    serre = _p_json(E.DetectParams(step_ms=5 * 60 * 1000,
                                   smooth_ms=10 * 60 * 1000,
                                   min_turn_deg=60.0, min_wind_kmh=3.0,
                                   hold_ms=30 * 60 * 1000,
                                   ramp_thresholds=(15, 25)))

    jour_brise = _obs_json(breeze_day())
    jour_rampe = _obs_json(ramping_day())
    jour_cede = _obs_json(yielding_day())
    trouee = _obs_json([o for o in breeze_day()
                        if not (10 * 3600 <= (o.t % DAY_MS) / 1000 < 13 * 3600)])
    # Vent qui oscille EXACTEMENT autour du seuil : le cas où un `<`
    # devenu `<=` d'un côté se voit, et nulle part ailleurs.
    frontiere = _obs_json([
        S.ObsSample(t=k * 240_000, speed=20.0 if k % 7 else 19.999999,
                    dir=180.0) for k in range(360)])

    fx: dict[str, list] = {
        "resample": [{"obs": jour_brise, "p": p},
                     {"obs": trouee, "p": p},
                     {"obs": jour_rampe, "p": serre},
                     {"obs": [], "p": p}],
        "detectReversals": [{"obs": jour_brise, "p": p},
                            {"obs": trouee, "p": p},
                            {"obs": jour_brise, "p": serre}],
        "detectRamps": [{"obs": jour_rampe, "p": p},
                        {"obs": frontiere, "p": p},
                        {"obs": jour_rampe, "p": serre}],
        "detectOnsetDrop": [{"obs": jour_rampe, "threshold": 12, "p": p},
                            {"obs": jour_cede, "threshold": 12, "p": p},
                            {"obs": frontiere, "threshold": 20, "p": p}],
        "detectAll": [{"obs": jour_brise, "onset": 12, "p": p},
                      {"obs": jour_rampe, "onset": 12, "p": p},
                      {"obs": jour_cede, "onset": 12, "p": serre}],
        "matchEvents": [],
        "scoreEvents": [],
        "consolidateNetwork": [],
        "detectConflicts": [
            {"obs": jour_cede, "crest": _crest_json(steady_crest()),
             "p": _cp_json(E.DEFAULT_CONFLICT), "dp": p},
            {"obs": jour_cede,
             "crest": _crest_json([E.CrestSample(t=h * 3_600_000, speed_kmh=34.0,
                                                 dir_deg=float((h * 8) % 360))
                                   for h in range(25)]),
             "p": _cp_json(E.DEFAULT_CONFLICT), "dp": p},
            {"obs": jour_brise, "crest": _crest_json(steady_crest()),
             "p": _cp_json(E.DEFAULT_CONFLICT), "dp": p},
        ],
        "consolidateConflicts": [],
        "rankForReview": [],
    }

    # ── appariement : synthétique, tous les cas limites ──
    obs_ev = [E.WindEvent("reversal", 12 * 3_600_000),
              E.WindEvent("ramp", 15 * 3_600_000, threshold=20),
              E.WindEvent("onset", 9 * 3_600_000, threshold=12),
              E.WindEvent("drop", 20 * 3_600_000, threshold=12)]
    fc_ev = [E.WindEvent("reversal", 12 * 3_600_000 - 40 * 60_000),
             E.WindEvent("ramp", 15 * 3_600_000, threshold=30),
             E.WindEvent("ramp", 15 * 3_600_000 + 30 * 60_000, threshold=20),
             E.WindEvent("onset", 9 * 3_600_000 + 90 * 60_000, threshold=12)]
    fx["matchEvents"] += [
        {"observed": [_ev_json(e) for e in obs_ev],
         "forecast": [_ev_json(e) for e in fc_ev]},
        {"observed": [], "forecast": [_ev_json(e) for e in fc_ev]},
        {"observed": [_ev_json(e) for e in obs_ev], "forecast": []},
        # Deux événements proches : le piège de l'appariement chronologique.
        {"observed": [_ev_json(E.WindEvent("onset", 0)),
                      _ev_json(E.WindEvent("onset", 30 * 60_000))],
         "forecast": [_ev_json(E.WindEvent("onset", 35 * 60_000)),
                      _ev_json(E.WindEvent("onset", 5 * 60_000))]},
        # Décalages exactement à la demi-minute : l'arrondi de JS.
        {"observed": [_ev_json(E.WindEvent("reversal", 0)),
                      _ev_json(E.WindEvent("drop", 6 * 3_600_000))],
         "forecast": [_ev_json(E.WindEvent("reversal", 30_000)),
                      _ev_json(E.WindEvent("drop", 6 * 3_600_000 - 30_000))]},
    ]
    for case in list(fx["matchEvents"]):
        ms = E.match_events([E.WindEvent(**{
            "type": e["type"], "t": e["t"], "turn": e["turn"],
            "dir_before": e["dirBefore"], "dir_after": e["dirAfter"],
            "speed_before": e["speedBefore"], "speed_after": e["speedAfter"],
            "threshold": e["threshold"]}) for e in case["observed"]],
            [E.WindEvent(**{
                "type": e["type"], "t": e["t"], "turn": e["turn"],
                "dir_before": e["dirBefore"], "dir_after": e["dirAfter"],
                "speed_before": e["speedBefore"], "speed_after": e["speedAfter"],
                "threshold": e["threshold"]}) for e in case["forecast"]])
        fx["scoreEvents"].append({"matches": [_match_json(m) for m in ms]})
    fx["scoreEvents"].append({"matches": []})

    # ── réseau : la grappe à cheval sur une frontière de 30 min ──
    fx["consolidateNetwork"] += [
        {"perStation": [{"stationId": "A", "events": [_ev_json(E.WindEvent("reversal", 25 * 60_000))]},
                        {"stationId": "B", "events": [_ev_json(E.WindEvent("reversal", 37 * 60_000))]},
                        {"stationId": "C", "events": [_ev_json(E.WindEvent("reversal", 45 * 60_000))]}],
         "minStations": 2, "clusterMs": 30 * 60 * 1000},
        {"perStation": [{"stationId": "A", "events": [_ev_json(E.WindEvent("ramp", 0, threshold=20))]},
                        {"stationId": "B", "events": [_ev_json(E.WindEvent("ramp", 60_000, threshold=30))]}],
         "minStations": 2, "clusterMs": 30 * 60 * 1000},
        {"perStation": [{"stationId": "A", "events": [_ev_json(E.WindEvent("onset", 0)),
                                                      _ev_json(E.WindEvent("onset", 60_000))]}],
         "minStations": 2, "clusterMs": 30 * 60 * 1000},
        {"perStation": [], "minStations": 2, "clusterMs": 30 * 60 * 1000},
    ]

    eps = E.detect_conflicts(yielding_day(), steady_crest())
    fx["consolidateConflicts"] += [
        {"perStation": [{"stationId": "A", "episodes": [_ep_json(e) for e in eps]},
                        {"stationId": "B", "episodes": [_ep_json(e) for e in eps]}],
         "minStations": 2, "clusterMs": 45 * 60 * 1000},
        {"perStation": [{"stationId": "A", "episodes": [_ep_json(e) for e in eps]}],
         "minStations": 2, "clusterMs": 45 * 60 * 1000},
    ]
    fx["rankForReview"] = [{"episodes": [_ep_json(e) for e in eps]}]

    # ══════════════════════════════════════════════════════════════
    #  DONNÉES RÉELLES — la partie qui prouve vraiment quelque chose
    # ══════════════════════════════════════════════════════════════
    fx["_real"] = []
    if archive and day:
        obs, fcst, crest = load_archive(archive, day)
        if not obs:
            print(f"  ⚠️ archive vide ou absente pour {day} dans {archive} — "
                  f"le banc de parité restera SYNTHÉTIQUE, et c'est une "
                  f"couverture plus faible.")
        else:
            fx["_real"] = [f"{day}: {len(obs)} balises, {len(fcst)} séries "
                           f"prévues, {len(crest)} séries de crête"]
            for key, samples in obs.items():
                fx["detectAll"].append({"obs": _obs_json(samples),
                                        "onset": 12, "p": p})
            # Les prévisions passent par la MÊME détection : c'est le
            # principe de la vérification par événement.
            for (key, model), samples in sorted(fcst.items())[:40]:
                fx["detectAll"].append({"obs": _obs_json(samples),
                                        "onset": 12, "p": p})
            # Appariement réel : les événements observés d'une balise
            # contre ceux prévus par chaque modèle pour la même balise.
            for (key, model), samples in sorted(fcst.items())[:40]:
                o_ev = E.detect_all(obs[key])
                f_ev = E.detect_all(samples)
                if not o_ev and not f_ev:
                    continue
                fx["matchEvents"].append({
                    "observed": [_ev_json(e) for e in o_ev],
                    "forecast": [_ev_json(e) for e in f_ev]})
                fx["scoreEvents"].append({
                    "matches": [_match_json(m)
                                for m in E.match_events(o_ev, f_ev)]})
            # Réseau : toutes les balises réelles d'un coup. Aucune n'est
            # dans la même vallée ici — le quorum écartera presque tout,
            # et c'est justement ce que les deux portages doivent faire
            # de la même façon.
            fx["consolidateNetwork"].append({
                "perStation": [{"stationId": k,
                                "events": [_ev_json(e) for e in E.detect_all(v)]}
                               for k, v in obs.items()],
                "minStations": 2, "clusterMs": 30 * 60 * 1000})
            for key, c in sorted(crest.items())[:12]:
                fx["detectConflicts"].append({
                    "obs": _obs_json(obs[key]), "crest": _crest_json(c),
                    "p": _cp_json(E.DEFAULT_CONFLICT), "dp": p})
    return fx


# ══════════════════════════════════════════════════════════════════
#  3. COMPARAISON PYTHON ↔ TYPESCRIPT
# ══════════════════════════════════════════════════════════════════

def _r(x, nd: int = 9):
    """Même arrondi que le TS (`toFixed(9)`), et pour la même raison."""
    if x is None or not S._finite(x):
        return None
    return round(float(x), nd)


def _ev_out(e: E.WindEvent):
    return [e.type, _r(e.t), e.threshold, _r(e.turn), _r(e.dir_before),
            _r(e.dir_after), _r(e.speed_before), _r(e.speed_after)]


def _match_out(m: E.EventMatch):
    return [m.type, m.outcome, m.timing_err_min, m.obs_t, m.fcst_t, m.threshold]


def _ep_out(e: E.ConflictEpisode):
    return [e.hold_start, e.yield_at, _r(e.crest_dir), _r(e.crest_speed),
            _r(e.breeze_dir), _r(e.breeze_speed), _r(e.after_dir),
            e.hold_minutes, e.stations]


def _obs_from(a):
    return [S.ObsSample(t=o["t"], speed=o["speed"], dir=o["dir"]) for o in a]


def _crest_from(a):
    return [E.CrestSample(t=c["t"], speed_kmh=c["speedKmh"], dir_deg=c["dirDeg"])
            for c in a]


def _ev_from(e):
    return E.WindEvent(type=e["type"], t=e["t"], turn=e["turn"],
                       dir_before=e["dirBefore"], dir_after=e["dirAfter"],
                       speed_before=e["speedBefore"],
                       speed_after=e["speedAfter"], threshold=e["threshold"])


def _match_from(m):
    return E.EventMatch(type=m["type"], outcome=m["outcome"],
                        timing_err_min=m["timingErrMin"], obs_t=m["obsT"],
                        fcst_t=m["fcstT"], threshold=m["threshold"])


def _ep_from(e):
    return E.ConflictEpisode(
        hold_start=e["holdStart"], yield_at=e["yieldAt"],
        crest_dir=e["crestDir"], crest_speed=e["crestSpeed"],
        breeze_dir=e["breezeDir"], breeze_speed=e["breezeSpeed"],
        after_dir=e["afterDir"], hold_minutes=e["holdMinutes"],
        stations=e.get("stations"))


def _p_from(p):
    return E.DetectParams(step_ms=p["stepMs"], smooth_ms=p["smoothMs"],
                          min_turn_deg=p["minTurnDeg"],
                          min_wind_kmh=p["minWindKmh"], hold_ms=p["holdMs"],
                          ramp_thresholds=tuple(p["rampThresholds"]))


def _cp_from(p):
    return E.ConflictParams(
        min_crest_kmh=p["minCrestKmh"], min_oppose_deg=p["minOpposeDeg"],
        min_breeze_kmh=p["minBreezeKmh"], min_hold_ms=p["minHoldMs"],
        max_align_deg=p["maxAlignDeg"], min_after_ms=p["minAfterMs"],
        max_crest_drift_deg=p["maxCrestDriftDeg"],
        hours=(p["hours"][0], p["hours"][1]), utc_offset_s=p["utcOffsetS"])


def parity(ts_path: str, fx_path: str):
    print("── 6. parité Python ↔ TypeScript ──")
    with open(fx_path, encoding="utf-8") as f:
        fx = json.load(f)
    with open(ts_path, encoding="utf-8") as f:
        ts = json.load(f)

    for note in fx.get("_real", []):
        print(f"  ⓘ données réelles dans le jeu : {note}")
    if not fx.get("_real"):
        print("  ⚠️ AUCUNE donnée réelle dans ce jeu de fixtures — la parité "
              "n'est prouvée que sur des séries fabriquées.")

    mine: dict[str, list] = {}
    mine["resample"] = [[[s.t, _r(s.speed), _r(s.dir)]
                         for s in E.resample(_obs_from(c["obs"]), _p_from(c["p"]))]
                        for c in fx["resample"]]
    mine["detectReversals"] = [
        [_ev_out(e) for e in E.detect_reversals(
            E.resample(_obs_from(c["obs"]), _p_from(c["p"])), _p_from(c["p"]))]
        for c in fx["detectReversals"]]
    mine["detectRamps"] = [
        [_ev_out(e) for e in E.detect_ramps(
            E.resample(_obs_from(c["obs"]), _p_from(c["p"])), _p_from(c["p"]))]
        for c in fx["detectRamps"]]
    mine["detectOnsetDrop"] = [
        [_ev_out(e) for e in E.detect_onset_drop(
            E.resample(_obs_from(c["obs"]), _p_from(c["p"])), c["threshold"],
            _p_from(c["p"]))]
        for c in fx["detectOnsetDrop"]]
    mine["detectAll"] = [
        [_ev_out(e) for e in E.detect_all(_obs_from(c["obs"]), c["onset"],
                                          _p_from(c["p"]))]
        for c in fx["detectAll"]]
    mine["matchEvents"] = [
        [_match_out(m) for m in E.match_events([_ev_from(e) for e in c["observed"]],
                                               [_ev_from(e) for e in c["forecast"]])]
        for c in fx["matchEvents"]]
    mine["scoreEvents"] = []
    for c in fx["scoreEvents"]:
        s = E.score_events([_match_from(m) for m in c["matches"]])
        mine["scoreEvents"].append(
            [s.hits, s.false_alarms, s.misses, _r(s.pod), _r(s.far), _r(s.csi),
             _r(s.frequency_bias), _r(s.timing_err_med_min), _r(s.timing_iqr_min)])
    mine["consolidateNetwork"] = [
        [_ev_out(e) for e in E.consolidate_network(
            [(s["stationId"], [_ev_from(x) for x in s["events"]])
             for s in c["perStation"]], c["minStations"], c["clusterMs"])]
        for c in fx["consolidateNetwork"]]
    mine["detectConflicts"] = [
        [_ep_out(e) for e in E.detect_conflicts(
            _obs_from(c["obs"]), _crest_from(c["crest"]),
            _cp_from(c["p"]), _p_from(c["dp"]))]
        for c in fx["detectConflicts"]]
    mine["consolidateConflicts"] = [
        [_ep_out(e) for e in E.consolidate_conflicts(
            [(s["stationId"], [_ep_from(x) for x in s["episodes"]])
             for s in c["perStation"]], c["minStations"], c["clusterMs"])]
        for c in fx["consolidateConflicts"]]
    mine["rankForReview"] = [
        [[e.yield_at, _r(sh)]
         for e, sh in E.rank_for_review([_ep_from(x) for x in c["episodes"]])]
        for c in fx["rankForReview"]]

    for family, got in mine.items():
        want = ts.get(family)
        if want is None:
            check(f"{family} : famille absente du résultat TS", False, True)
            continue
        if len(got) != len(want):
            check(f"{family} : {len(got)} cas Python vs {len(want)} cas TS",
                  len(got), len(want))
            continue
        # ⚠️ ON COMPARE CAS PAR CAS, JAMAIS FAMILLE PAR FAMILLE. Un seul
        # `check` sur toute la liste dirait « ça ne colle pas » sans dire
        # OÙ — et sur 100 journées réelles, la différence serait
        # illisible.
        for i, (g, w) in enumerate(zip(got, want)):
            check(f"{family}[{i}] ({len(g)} sorties)", g, w)
    print(f"  ⓘ {sum(len(v) for v in mine.values())} cas comparés, "
          f"{sum(len(x) for v in mine.values() for x in v)} sorties élémentaires")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--emit-fixtures", default=None)
    ap.add_argument("--ts-results", default=None)
    ap.add_argument("--fixtures", default=None,
                    help="jeu d'entrées à relire pour la comparaison "
                         "(défaut : à côté de --ts-results)")
    ap.add_argument("--archive", default=None,
                    help="racine d'archive locale (obs/ et fcst/)")
    ap.add_argument("--day", default=None, help="journée réelle, YYYY-MM-DD")
    args = ap.parse_args()

    if args.emit_fixtures:
        fx = build_fixtures(args.archive, args.day)
        path = pathlib.Path(args.emit_fixtures)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fx), encoding="utf-8")
        n = sum(len(v) for k, v in fx.items() if not k.startswith("_"))
        print(f"✅ {n} cas écrits dans {path} "
              f"({path.stat().st_size / 1024:.0f} Ko)")
        return 0

    bench_local()
    if args.ts_results:
        fx_path = args.fixtures or str(
            pathlib.Path(args.ts_results).with_name("fixtures.json"))
        if not pathlib.Path(fx_path).exists():
            print(f"  ❌ jeu d'entrées introuvable : {fx_path}")
            return 1
        parity(args.ts_results, fx_path)
    else:
        print("── 6. parité Python ↔ TypeScript ──")
        print("  ⓘ SAUTÉE (pas de --ts-results). Un banc de parité sauté "
              "n'est pas un banc vert : la duplication reste non vérifiée.")

    print(f"\n{'✅' if KO == 0 else '❌'} {OK} réussis, {KO} échoués")
    return 0 if KO == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
