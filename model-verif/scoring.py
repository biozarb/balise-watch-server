#!/usr/bin/env python3
"""scoring.py — le cœur arithmétique du score de fiabilité, côté VPS.

    Session 08/08/2026.
    cf. PWA/web/CONCEPTION_SCORE_MODELES_06-08.md §8, §15.2, §16.1.

═══ POURQUOI CE FICHIER EXISTE ALORS QUE LE CODE EXISTE DÉJÀ EN TS ═══

`src/lib/verifScore.ts`, `modelCharacter.ts` et `regime.ts` portent la
même arithmétique, avec 199 assertions vertes derrière. Les réécrire ici
est une duplication, et ce projet a une allergie documentée aux
duplications (les cinq copies de `sb_upload()` qui ont donné
`tools/storage.py`).

Le motif : le VPS fait tourner cinq chaînes Python et aucune chaîne
Node. Y installer une seconde plateforme d'exécution pour ce seul job —
avec sa version de Node, ses `node_modules`, sa compilation TS avant
chaque run — coûterait plus cher en entretien que ces 300 lignes.

⚠️ MAIS UNE DUPLICATION NON VÉRIFIÉE EST UNE BOMBE À RETARDEMENT. Les
trois défauts du §15.3 et du §16.4 (biais d'initialisation de l'EWMA,
skill indéfini quand la persistance est parfaite, « significatif ≠
applicable ») sont exactement le genre d'erreur qu'un portage à la main
réintroduit sans bruit. D'où `test_scoring.py`, qui ne se contente pas
de tester ce fichier : il rejoue les MÊMES entrées à travers le
TypeScript compilé et exige des sorties identiques au flottant près.
Tant que ce banc est vert, la duplication est vérifiée. Le jour où il
casse, c'est qu'une des deux moitiés a divergé — et on le saura.

═══ UNE DIVERGENCE VOULUE, ET UNE SEULE ═══

`dominantRegime` en TS lit `new Date(t).getHours()` : l'heure LOCALE DE
LA MACHINE. Dans un navigateur français ça donne bien « 10 h - 19 h
locales » ; sur un VPS réglé en UTC, ça donne 12 h - 21 h heure de
Paris en été, et la fenêtre glisse avec la saison. Ici, l'heure locale
est donc calculée explicitement à partir d'un décalage passé en
paramètre. Ce n'est pas une liberté prise avec le portage : c'est le
même comportement que le TS *dans le contexte pour lequel il a été
écrit*. Le banc d'essai de parité passe donc un décalage nul et compare
à un TS lancé en `TZ=UTC`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Iterable, Sequence

# ══════════════════════════════════════════════════════════════════
#  CONSTANTES — reprises À L'IDENTIQUE du TypeScript
# ══════════════════════════════════════════════════════════════════

#: Demi-fenêtre d'agrégation des relevés autour d'une heure modèle (ms).
#: Centrée et non rétrograde : Open-Meteo ne moyenne pas le vent sur
#: l'heure écoulée (contrairement aux précipitations). ±20 min plutôt
#: que ±30 pour que deux heures consécutives ne partagent aucun relevé
#: — condition d'indépendance du test apparié.
OBS_HALF_WINDOW_MS = 20 * 60 * 1000

#: Sous ce vent, la girouette raconte n'importe quoi (même seuil que
#: `HEADING_MIN_WIND_KMH` de lib/config.ts).
DIR_MIN_WIND_KMH = 5.0

WINNER_SIGMA = 1.5
WINNER_MIN_PAIRS = 4
BIAS_MIN_PAIRS = 48
BIAS_MIN_WIND_KMH = 8.0
HALF_LIFE_DAYS = 30
REGIME_MIN_OCCURRENCES = 8

REGIMES = ("fluxN", "fluxE", "fluxS", "fluxW", "thermal", "calm")

REGIME_THRESHOLDS = {
    "gradientCrestKmh": 25.0,
    "calmCrestKmh": 12.0,
    "calmSurfaceKmh": 10.0,
}


def _finite(x) -> bool:
    """Équivalent de `Number.isFinite` : None, bool et NaN sont faux."""
    return (
        x is not None
        and not isinstance(x, bool)
        and isinstance(x, (int, float))
        and math.isfinite(x)
    )


# ══════════════════════════════════════════════════════════════════
#  TRIGONOMÉTRIE DU VENT
# ══════════════════════════════════════════════════════════════════

def to_uv(speed: float, dir_deg: float) -> tuple[float, float]:
    """Composantes (u, v) d'un vent en (force, direction météo).

    Convention météo : `dir` est la direction D'OÙ VIENT le vent. On
    garde le vecteur « d'où ça vient » — peu importe le signe tant
    qu'il est le même des deux côtés de la soustraction.
    """
    r = math.radians(dir_deg)
    return speed * math.sin(r), speed * math.cos(r)


def from_uv(u: float, v: float) -> float:
    """Direction météo (0-360) depuis (u, v)."""
    return (math.degrees(math.atan2(u, v)) + 360) % 360


def angular_diff(a: float, b: float) -> float:
    """Écart angulaire SIGNÉ dans [-180, +180]. Positif = `b` horaire / `a`."""
    return (((b - a) % 360) + 540) % 360 - 180


def median(xs: Iterable[float]) -> float | None:
    """Médiane simple. None si aucune valeur finie."""
    v = sorted(x for x in xs if _finite(x))
    if not v:
        return None
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2


@dataclass(frozen=True)
class ObsSample:
    t: int              # ms
    speed: float | None
    dir: float | None


@dataclass(frozen=True)
class VerifPair:
    t: int
    fcst_speed: float
    fcst_dir: float | None
    obs_speed: float
    obs_dir: float | None
    n_obs: int


def mean_wind(samples: Sequence[ObsSample],
              min_wind_for_dir: float = DIR_MIN_WIND_KMH):
    """Moyenne VECTORIELLE d'une série de vents.

    ⚠️ Jamais la moyenne arithmétique des directions : la moyenne de
    350° et 10° vaut 180° en arithmétique (plein sud) alors que le vent
    est manifestement de nord.

    Les relevés sans direction contribuent quand même à la force, sinon
    une station sans girouette ne serait jamais notée.
    """
    su = sv = 0.0
    n_dir = 0
    s_speed = 0.0
    n_speed = 0
    for s in samples:
        if not _finite(s.speed):
            continue
        s_speed += s.speed
        n_speed += 1
        if not _finite(s.dir):
            continue
        # Sous le seuil, on garde la force et on jette la direction :
        # moyenner du bruit uniforme tire la moyenne vectorielle vers
        # zéro et fait croire à un vent nul là où il y a un vent faible.
        if s.speed < min_wind_for_dir:
            continue
        u, v = to_uv(s.speed, s.dir)
        su += u
        sv += v
        n_dir += 1
    if n_speed == 0:
        return None, None, 0
    return (s_speed / n_speed,
            from_uv(su / n_dir, sv / n_dir) if n_dir > 0 else None,
            n_speed)


# ══════════════════════════════════════════════════════════════════
#  APPARIEMENT PRÉVU / OBSERVÉ
# ══════════════════════════════════════════════════════════════════

def pair_series(times: Sequence[int],
                fcst_speed: Sequence[float | None],
                fcst_dir: Sequence[float | None] | None,
                obs: Sequence[ObsSample],
                half_window_ms: int = OBS_HALF_WINDOW_MS) -> list[VerifPair]:
    """Apparie une série de modèle aux relevés réels.

    Les heures sans aucun relevé dans la fenêtre sont ABSENTES du
    résultat — jamais comblées, jamais interpolées (règle maison : pas
    de donnée inventée, même pour un calcul intermédiaire).
    """
    if not times or not obs:
        return []
    ordered = sorted(obs, key=lambda o: o.t)
    pairs: list[VerifPair] = []
    lo = 0
    for i, t in enumerate(times):
        fs = fcst_speed[i] if i < len(fcst_speed) else None
        if not _finite(fs):
            continue
        while lo < len(ordered) and ordered[lo].t < t - half_window_ms:
            lo += 1
        win = []
        j = lo
        while j < len(ordered) and ordered[j].t <= t + half_window_ms:
            win.append(ordered[j])
            j += 1
        if not win:
            continue
        speed, direction, n = mean_wind(win)
        if speed is None:
            continue
        fd = fcst_dir[i] if fcst_dir is not None and i < len(fcst_dir) else None
        pairs.append(VerifPair(
            t=t, fcst_speed=fs, fcst_dir=fd if _finite(fd) else None,
            obs_speed=speed, obs_dir=direction, n_obs=n))
    return pairs


def pair_error(p: VerifPair) -> tuple[float, bool]:
    """Erreur d'UNE heure appariée (km/h), et si elle est vectorielle.

    Vectorielle dès que les deux côtés ont une direction exploitable :
    ‖V⃗_prévu − V⃗_observé‖. Sinon repli scalaire |Δforce| — un modèle
    n'est pas pénalisé parce que la station n'a pas de girouette, mais
    on garde trace du repli via `vector_ratio`.
    """
    if (p.fcst_dir is not None and p.obs_dir is not None
            and p.fcst_speed >= DIR_MIN_WIND_KMH
            and p.obs_speed >= DIR_MIN_WIND_KMH):
        au, av = to_uv(p.fcst_speed, p.fcst_dir)
        bu, bv = to_uv(p.obs_speed, p.obs_dir)
        return math.hypot(au - bu, av - bv), True
    return abs(p.fcst_speed - p.obs_speed), False


@dataclass(frozen=True)
class SeriesError:
    rms: float | None
    med: float | None
    n: int
    vector_ratio: float
    per_hour: list[float]


def series_error(pairs: Sequence[VerifPair]) -> SeriesError:
    per_hour: list[float] = []
    sum_sq = 0.0
    n_vec = 0
    for p in pairs:
        err, vector = pair_error(p)
        per_hour.append(err)
        sum_sq += err * err
        if vector:
            n_vec += 1
    n = len(per_hour)
    return SeriesError(
        rms=math.sqrt(sum_sq / n) if n >= 2 else None,
        med=median([abs(e) for e in per_hour]),
        n=n,
        vector_ratio=n_vec / n if n > 0 else 0.0,
        per_hour=per_hour,
    )


# ══════════════════════════════════════════════════════════════════
#  BIAIS DE SITE
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class SiteBias:
    speed_ratio: float | None
    dir_offset: float | None
    n: int


def site_bias(pairs: Sequence[VerifPair],
              min_pairs: int = BIAS_MIN_PAIRS) -> SiteBias:
    ratios: list[float] = []
    offsets: list[float] = []
    for p in pairs:
        if p.fcst_speed >= BIAS_MIN_WIND_KMH and p.obs_speed >= 0:
            ratios.append(p.obs_speed / p.fcst_speed)
        if (p.fcst_dir is not None and p.obs_dir is not None
                and p.fcst_speed >= BIAS_MIN_WIND_KMH
                and p.obs_speed >= BIAS_MIN_WIND_KMH):
            offsets.append(angular_diff(p.fcst_dir, p.obs_dir))
    enough = len(pairs) >= min_pairs
    return SiteBias(
        speed_ratio=median(ratios) if enough and len(ratios) >= min_pairs / 2 else None,
        dir_offset=median(offsets) if enough and len(offsets) >= min_pairs / 2 else None,
        n=len(pairs),
    )


def apply_bias(pairs: Sequence[VerifPair], bias: SiteBias) -> list[VerifPair]:
    """Corrige la série PRÉVUE, jamais l'observée.

    La mesure est la vérité terrain — c'est elle qu'on cherche à
    reproduire, ce n'est pas à elle de se justifier.
    """
    if bias.speed_ratio is None and bias.dir_offset is None:
        return list(pairs)
    out = []
    for p in pairs:
        out.append(replace(
            p,
            fcst_speed=p.fcst_speed * bias.speed_ratio
            if bias.speed_ratio is not None else p.fcst_speed,
            fcst_dir=(p.fcst_dir + bias.dir_offset + 360) % 360
            if bias.dir_offset is not None and p.fcst_dir is not None else p.fcst_dir,
        ))
    return out


# ══════════════════════════════════════════════════════════════════
#  SKILL CONTRE LA PERSISTANCE (§8.2)
# ══════════════════════════════════════════════════════════════════

def persistence_reference(obs: Sequence[ObsSample], t: int,
                          half_window_ms: int = OBS_HALF_WINDOW_MS):
    """L'observation de la MÊME HEURE LA VEILLE.

    ⚠️ Pas « la dernière valeur connue », qui est la persistance
    habituelle en météo synoptique. Sur un site de vol, le signal
    dominant est le cycle diurne de brise : « comme hier à la même
    heure » est une prévision naïve redoutable, et c'est ça qu'il faut
    battre.
    """
    target = t - 24 * 3600 * 1000
    win = [o for o in obs if abs(o.t - target) <= half_window_ms]
    if not win:
        return None, None
    speed, direction, _ = mean_wind(win)
    return speed, direction


def skill_vs_persistence(pairs: Sequence[VerifPair], obs: Sequence[ObsSample]):
    """Rend (skill, n, mse_model, mse_ref).

    ⚠️ LES DEUX MSE SONT RENDUS SÉPARÉMENT, ET LE RATIO N'EN EST PAS
    DÉRIVÉ. Défaut n°1 du §16.4 : le skill est indéfini quand la
    persistance est parfaite (dénominateur nul) — or c'est précisément
    le cas où l'on peut affirmer sans hésiter que le modèle perd.
    `beats_persistence` se calcule par comparaison directe.
    """
    sq_model = sq_ref = 0.0
    n = 0
    for p in pairs:
        ref_speed, ref_dir = persistence_reference(obs, p.t)
        if ref_speed is None:
            continue
        em, _ = pair_error(p)
        er, _ = pair_error(replace(p, fcst_speed=ref_speed, fcst_dir=ref_dir))
        sq_model += em * em
        sq_ref += er * er
        n += 1
    if n < 2:
        return None, n, None, None
    mse_model = sq_model / n
    mse_ref = sq_ref / n
    skill = None if sq_ref == 0 else 1 - sq_model / sq_ref
    return skill, n, mse_model, mse_ref


# ══════════════════════════════════════════════════════════════════
#  BOOTSTRAP (§8.4)
# ══════════════════════════════════════════════════════════════════

def _to_int32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - 0x100000000 if x & 0x80000000 else x


class _XorShift:
    """Reproduit BIT À BIT le générateur du TypeScript.

    Les opérateurs binaires de JavaScript travaillent sur des entiers
    32 bits signés, et `>>>` sur des non signés. Sans cette émulation,
    Python (entiers illimités) diverge dès le premier tour et les
    intervalles de confiance des deux implémentations ne seraient plus
    comparables — ce qui priverait le banc de parité de son objet.
    """

    def __init__(self, seed: int = 0x9E3779B9):
        self.s = _to_int32(seed)

    def next(self) -> float:
        s = self.s
        s = _to_int32(s ^ _to_int32((s & 0xFFFFFFFF) << 13))
        s = _to_int32(s ^ ((s & 0xFFFFFFFF) >> 17))
        s = _to_int32(s ^ _to_int32((s & 0xFFFFFFFF) << 5))
        self.s = s
        return ((s & 0xFFFFFFFF) % 0xFFFFFFFF) / 0xFFFFFFFF


def bootstrap_ci(values: Sequence[float], iterations: int = 500):
    """IC 95 % de la MÉDIANE, par rééchantillonnage avec remise.

    ⚠️ L'unité de rééchantillonnage doit être la BALISE-JOUR, pas
    l'heure : deux heures consécutives de la même balise le même jour
    ne sont pas indépendantes, et rééchantillonner à l'heure produirait
    un intervalle beaucoup trop étroit — donc des « gagnants » qui n'en
    sont pas. C'est à l'appelant de fournir un tableau déjà agrégé.

    Générateur déterministe : deux exécutions sur les mêmes données
    donnent le même intervalle. Un score qui bouge parce que le hasard
    a changé d'avis serait indéfendable devant un pilote.
    """
    v = [x for x in values if _finite(x)]
    if len(v) < 3:
        return median(v), None, None
    rnd = _XorShift()
    meds: list[float] = []
    for _ in range(iterations):
        draw = [v[int(rnd.next() * len(v))] for _ in range(len(v))]
        m = median(draw)
        if m is not None:
            meds.append(m)
    meds.sort()
    lo_i = math.floor(len(meds) * 0.025)
    hi_i = math.floor(len(meds) * 0.975)
    return (median(v),
            meds[lo_i] if lo_i < len(meds) else None,
            meds[hi_i] if hi_i < len(meds) else None)


# ══════════════════════════════════════════════════════════════════
#  SCORE ABSOLU (§16.1)
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class AbsoluteScore:
    """Ce qu'on peut dire d'un modèle SANS le comparer aux autres.

    `typical_err_kmh` est une MÉDIANE : l'erreur d'une journée
    ordinaire, pas celle que les trois pires journées font remonter.
    C'est le seul chiffre du dispositif qu'un pilote traduit
    directement en décision.
    """
    typical_err_kmh: float | None
    worst_decile_kmh: float | None
    skill: float | None
    beats_persistence: bool | None
    n: int


def absolute_score(pairs: Sequence[VerifPair],
                   obs: Sequence[ObsSample]) -> AbsoluteScore:
    e = series_error(pairs)
    ordered = sorted(e.per_hour)
    skill, n_skill, mse_model, mse_ref = skill_vs_persistence(pairs, obs)
    worst = (ordered[min(len(ordered) - 1, math.floor(len(ordered) * 0.9))]
             if len(ordered) >= 5 else None)
    beats = (None if n_skill < 4 or mse_model is None or mse_ref is None
             else mse_model < mse_ref)
    return AbsoluteScore(typical_err_kmh=e.med, worst_decile_kmh=worst,
                         skill=skill, beats_persistence=beats, n=e.n)


def rank_by_regime(scores: Sequence[dict], min_relative_gap: float = 0.15):
    """Classe des modèles pour un régime, en refusant de trancher quand
    rien ne se détache.

    Chaque entrée : {'model': str, 'typical_err_kmh': float|None,
                     'occurrences': int}.

    ⚠️ Le départage se fait sur l'erreur en km/h et non sur le skill :
    deux modèles peuvent avoir le même skill relatif à la persistance
    tout en se trompant de 4 et 9 km/h. C'est l'erreur en km/h qui
    décide d'un vol.

    ⚠️ Écart RELATIF : 1 km/h d'écart est décisif quand on est à 3 km/h,
    anecdotique quand on est à 15. Un seuil absolu privilégierait
    mécaniquement les zones calmes, où tout le monde est bon.
    """
    usable = [s for s in scores
              if s.get("typical_err_kmh") is not None
              and s.get("occurrences", 0) >= REGIME_MIN_OCCURRENCES]
    if not usable:
        return None, "insufficient"
    if len(usable) == 1:
        return usable[0]["model"], "ok"
    ordered = sorted(usable, key=lambda s: s["typical_err_kmh"])
    best = ordered[0]["typical_err_kmh"]
    second = ordered[1]["typical_err_kmh"]
    if second == 0:
        return None, "tied"
    return ((ordered[0]["model"], "ok")
            if (second - best) / second >= min_relative_gap
            else (None, "tied"))


# ══════════════════════════════════════════════════════════════════
#  RÉGIMES (§16.2) — six, dont quatre quadrants de flux
# ══════════════════════════════════════════════════════════════════

def quadrant(dir_deg: float) -> str:
    """Quadrant d'un cap, centré sur les points cardinaux : le secteur
    Nord va de 315° à 45°. Un flux de 350° est un flux de nord, pas un
    flux « nord-est déguisé »."""
    d = (dir_deg % 360 + 360) % 360
    if d >= 315 or d < 45:
        return "N"
    if d < 135:
        return "E"
    if d < 225:
        return "S"
    return "W"


def classify_regime(crest_speed_kmh: float | None,
                    crest_dir_deg: float | None,
                    surface_speed_kmh: float | None = None) -> str | None:
    """Classe une situation en régime. None = on ne devine pas.

    Une journée sans régime identifié ne participe à aucun
    accumulateur, plutôt que d'être versée au hasard dans « calme » —
    ce qui polluerait la case la plus peuplée avec des journées de flux.
    """
    if not _finite(crest_speed_kmh):
        return None
    if crest_speed_kmh >= REGIME_THRESHOLDS["gradientCrestKmh"]:
        # Un flux fort sans direction connue n'est pas classable : le
        # quadrant EST l'information ici.
        if not _finite(crest_dir_deg):
            return None
        return {"N": "fluxN", "E": "fluxE",
                "S": "fluxS", "W": "fluxW"}[quadrant(crest_dir_deg)]
    if crest_speed_kmh < REGIME_THRESHOLDS["calmCrestKmh"]:
        surf = surface_speed_kmh if _finite(surface_speed_kmh) else 0.0
        # Crête molle MAIS vent au sol réel = une brise s'est établie,
        # ce qui est un moteur thermique et pas du calme plat.
        if surf >= REGIME_THRESHOLDS["calmSurfaceKmh"]:
            return "thermal"
        return "calm"
    return "thermal"


def dominant_regime(hourly: Sequence[tuple[int, str | None]],
                    start_hour: int = 10,
                    end_hour: int = 19,
                    utc_offset_s: int = 0) -> str | None:
    """Régime DOMINANT d'une journée, sur les heures volables.

    ⚠️ Pas la moyenne des heures, mais le régime le plus REPRÉSENTÉ.
    Une journée qui commence calme et bascule en flux de nord à midi
    n'est pas une « journée moyennement ventée » : c'est une journée de
    flux de nord.

    ⚠️ `utc_offset_s` EST OBLIGATOIRE ICI ALORS QU'IL N'EXISTE PAS EN
    TS, et c'est la seule divergence assumée de ce portage. Le TS lit
    `new Date(t).getHours()`, donc l'heure locale DE LA MACHINE : juste
    dans un navigateur français, faux sur un VPS en UTC, où la fenêtre
    « 10 h - 19 h » devient 12 h - 21 h heure de Paris en été et glisse
    avec le changement d'heure. Passer le décalage explicitement rend
    la fenêtre indépendante du réglage du serveur.
    """
    counts: dict[str, int] = {}
    for t, regime in hourly:
        if regime is None:
            continue
        hod = ((t // 1000 + utc_offset_s) // 3600) % 24
        if hod < start_hour or hod > end_hour:
            continue
        counts[regime] = counts.get(regime, 0) + 1
    if not counts:
        return None
    # Ordre de REGIMES comme départage déterministe : deux régimes à
    # égalité doivent toujours donner le même verdict, sinon le même
    # jour rejoué produirait deux accumulateurs différents.
    best, best_n = None, 0
    for r in REGIMES:
        n = counts.get(r, 0)
        if n > best_n:
            best, best_n = r, n
    return best


# ══════════════════════════════════════════════════════════════════
#  ACCUMULATEURS — la mémoire longue (§15.2)
# ══════════════════════════════════════════════════════════════════

def wind_band(speed_kmh: float) -> str:
    """Tranche de vent. Bornes d'usage pilote, pas des quantiles."""
    if speed_kmh < 15:
        return "light"
    if speed_kmh < 30:
        return "moderate"
    return "strong"


@dataclass
class Accumulator:
    """État complet — c'est EXACTEMENT une ligne de `model_character`.

    ⚠️ ON STOCKE DES SOMMES, PAS UNE MOYENNE LISSÉE. La forme d'EWMA
    habituelle (`value += α(x − value)`) prend le premier jour tel quel
    et, avec une demi-vie de 30 jours, il faut des MOIS pour que cette
    valeur initiale s'efface. Mesuré sur `test-character.ts` : 40 jours
    d'un biais alternant 0,6 / 1,4 — de moyenne rigoureusement 1, donc
    aucun caractère à annoncer — laissaient l'accumulateur à 1,21, soit
    « ce modèle sous-estime le vent de 21 % ». Un constat faux, affiché
    avec aplomb, sur un modèle sans défaut.
    """
    sum_w: float = 0.0
    sum_wx: float = 0.0
    sum_wx2: float = 0.0
    days: int = 0
    last_day: int | None = None      # epoch ms à minuit UTC

    @property
    def mean(self) -> float:
        return self.sum_wx / self.sum_w if self.sum_w > 0 else 0.0

    @property
    def var(self) -> float:
        # Bornée à 0 : l'arithmétique flottante peut rendre −1e-17 sur
        # une série rigoureusement constante.
        if self.sum_w <= 0:
            return 0.0
        return max(0.0, self.sum_wx2 / self.sum_w - self.mean ** 2)

    @property
    def std(self) -> float:
        return math.sqrt(self.var)

    @property
    def weight(self) -> float:
        return self.sum_w


def accumulate(acc: Accumulator, daily_value: float, day_ms: int,
               half_life_days: int = HALF_LIFE_DAYS) -> Accumulator:
    """Intègre la valeur d'une journée.

    ⚠️ LE POIDS DÉPEND DU TEMPS ÉCOULÉ, pas du nombre d'appels. Si le
    job n'a pas tourné pendant dix jours, la journée de reprise ne doit
    pas peser comme une journée consécutive. Sans ce détail, une
    interruption de service réécrirait silencieusement l'historique.

    ⚠️ Une journée déjà intégrée ne se réintègre pas : le job nocturne
    doit pouvoir être relancé deux fois sans fausser la mémoire.

    ⚠️ La valeur attendue est déjà une MÉDIANE des balises de la zone.
    Une moyenne exponentielle de médianes reste robuste ; une moyenne
    exponentielle de valeurs brutes ne l'est pas.
    """
    if not _finite(daily_value):
        return acc
    if acc.last_day is not None and day_ms <= acc.last_day:
        return acc
    elapsed = 0.0 if acc.last_day is None else (day_ms - acc.last_day) / 86_400_000
    decay = 1.0 if acc.last_day is None else 2 ** (-elapsed / half_life_days)
    return Accumulator(
        sum_w=acc.sum_w * decay + 1,
        sum_wx=acc.sum_wx * decay + daily_value,
        sum_wx2=acc.sum_wx2 * decay + daily_value * daily_value,
        days=acc.days + 1,
        last_day=day_ms,
    )


def is_significant(acc: Accumulator, reference: float, sigmas: float = 2) -> bool:
    """L'écart est-il BIEN DÉTERMINÉ ? (question statistique)"""
    if acc.weight < 2:
        return False
    se = acc.std / math.sqrt(acc.weight)
    if se == 0:
        return acc.mean != reference
    return abs(acc.mean - reference) >= sigmas * se


def is_regular(acc: Accumulator, reference: float,
               max_rel_dispersion: float = 1) -> bool:
    """L'écart se REPRODUIT-IL d'un jour à l'autre ? (question pratique)

    ⚠️ CE TEST N'EST PAS LE PRÉCÉDENT, et c'est le garde-fou décisif.
    Un modèle qui alterne 0,9 et 1,9 a une moyenne de 1,4 parfaitement
    déterminée : `is_significant` la valide, et l'app annoncerait « ce
    modèle sous-estime le vent de 40 % ». C'est vrai en moyenne et
    inutilisable : le pilote appliquerait un ×1,4 de tête tous les
    jours et se tromperait lourdement un jour sur deux.
    """
    effect = abs(acc.mean - reference)
    if effect == 0:
        return False
    return acc.std <= effect * max_rel_dispersion


def is_announceable(acc: Accumulator, reference: float) -> bool:
    """Les deux conditions réunies — bien déterminé ET reproductible."""
    return is_significant(acc, reference) and is_regular(acc, reference)


# ══════════════════════════════════════════════════════════════════
#  PRESSION (E6) — lot S1, 21/08/2026
# ══════════════════════════════════════════════════════════════════
#
#  ⚠️ CE BLOC EST UN PORTAGE, PAS UNE TROISIÈME ÉCRITURE.
#
#  La physique QNH → QFF existe déjà, en TypeScript, dans
#  `web/src/lib/pressure.ts` (vérifiée par `scripts/verify-pressure.mjs`)
#  et générée en `balise-watch-server/lib/pressure.cjs` pour le serveur
#  (contrôle de dérive : `node tools/verify-pressure-sync.mjs`). Ce qui
#  suit en est le JUMEAU PYTHON, et il est tenu par le banc de parité
#  (`test_scoring.py` + `web/scripts/parity-scoring.ts`), exactement
#  comme `verifScore.ts` l'est déjà. Toute correction ici doit partir
#  du TS, pas y arriver.
#
#  ⛔ POURQUOI ICI ET PAS DANS `score.py`. La spec du S1 laissait le
#  choix « portage avec banc de parité » ou « conversion locale dans
#  score.py, rien côté TS ». Le portage l'emporte parce que la
#  conversion ne sert pas qu'à la notation : le S2 en aura besoin pour
#  l'offset de station, et une conversion écrite dans `score.py` serait
#  la QUATRIÈME copie le jour où quelqu'un d'autre en a besoin.
#
#  ⚠️ ET LA CONSTANTE D'ALTITUDE N'EST PAS UN GARDE-FOU DE CONFORT.
#  `PRESSURE_MAX_ALT = 1000` vient de `pressure.ts` (03/08) : Samedan
#  (LSZS, 1 708 m) annonçait Q1025 quand toute la Suisse était entre
#  Q1013 et Q1018, et restait 2 à 3 hPa au-dessus de ses voisins MÊME
#  APRÈS conversion en QFF. Une réduction au niveau de la mer depuis
#  1 700 m est une fiction, pas une mesure imprécise.

#: Atmosphère standard ISA — valeurs reprises À L'IDENTIQUE de
#: `pressure.ts`. Les changer d'un côté sans l'autre casse la parité,
#: ce qui est exactement le but du banc.
ISA_T0 = 288.15          # K
ISA_LAPSE = 0.0065       # K/m
ISA_EXP = 5.25588        # = g / (R_d · lapse)
G_ACC = 9.80665          # m/s²
R_D = 287.05             # J/(kg·K)

#: cf. `pressure.ts` — mêmes noms, mêmes valeurs, même raison.
PRESSURE_MAX_ALT = 1000.0
QFF_CONVERSION_UNCERTAINTY_HPA = 0.3
QFF_NATIVE_UNCERTAINTY_HPA = 0.05

#: Les conventions de réduction qu'on sait traiter. `unknown` n'en est
#: PAS une : une pression dont on ignore la convention ne s'apparie pas,
#: elle se COMPTE (cf. `to_qff`, qui rend un motif).
PRES_KINDS = ("qff", "qnh", "station")

#: L'écart de tendance se mesure sur 3 h — c'est l'échelle à laquelle un
#: front se voit passer, et celle que le S0.1 a mesurée (|Δ3h| médian
#: observé : 0,668 hPa chez MF, 0,867 chez Infoclimat, le 21/08).
PTEND_HOURS = 3


def qnh_to_station(qnh: float, elev: float) -> float:
    """QNH → pression station, en remontant l'atmosphère standard.

    C'est l'inverse exact de la définition du QNH : le calage
    altimétrique qui, en atmosphère standard, ferait afficher l'altitude
    du terrain.
    """
    return qnh * (1.0 - (ISA_LAPSE * elev) / ISA_T0) ** ISA_EXP


def station_to_qff(p_sta: float, elev: float, temp_c: float) -> float:
    """Pression station → QFF, colonne d'air à la température RÉELLE.

    Toute la différence avec le QNH est là : la colonne fictive sous une
    station est plus légère quand il fait chaud, donc la réduction est
    plus faible. `T_moy` approxime la température moyenne de la colonne
    par celle de la station corrigée d'un demi-gradient standard.
    """
    t_mean = temp_c + 273.15 + (ISA_LAPSE * elev) / 2.0
    return p_sta * math.exp((G_ACC * elev) / (R_D * t_mean))


def qnh_to_qff(qnh: float, elev: float, temp_c: float) -> float:
    """QNH → QFF en une passe."""
    return station_to_qff(qnh_to_station(qnh, elev), elev, temp_c)


def to_qff(raw: float | None, kind: str, elev: float | None,
           temp_c: float | None = None,
           max_alt: float = PRESSURE_MAX_ALT) -> tuple[float | None, str | None]:
    """Ramène n'importe quel relevé en QFF. Rend `(qff, motif_de_refus)`.

    ⛔ TROIS REFUS EXPLICITES, tous volontaires — mieux vaut pas de
    chiffre qu'un chiffre faux, et le motif remonte pour être COMPTÉ :

      · `too-high`  — station au-dessus de `max_alt` (le cas Samedan) ;
      · `no-temp`   — un QNH sans température. On ne se rabat SURTOUT
        PAS sur le QNH brut « faute de mieux » : ce serait exactement le
        mélange de conventions que tout ce bloc existe pour empêcher
        (2,4 hPa d'écart entre deux stations de même altitude séparées
        par 15 K, chiffré côté serveur) ;
      · `unknown-kind` — `pres_kind` absent ou inconnu. La spec du S1 le
        dit : « si `pres_kind` est inconnu, on n'apparie pas, on
        compte ».

    ⚠️ `elev` EST L'ALTITUDE DÉCLARÉE PAR LA SOURCE, pas `dem_alt_m`.
    Se tromper de 28 m décalait Lugano de 3,3 hPa (03/08). `dem_alt_m`
    sert aux SEUILS d'appariement (`geopair`), jamais à la conversion.
    """
    if raw is None or not _finite(raw):
        return None, "no-value"
    if kind not in PRES_KINDS:
        return None, "unknown-kind"
    if elev is None or not _finite(elev):
        return None, "no-elev"
    if elev > max_alt:
        return None, "too-high"
    if kind == "qff":
        return float(raw), None
    if temp_c is None or not _finite(temp_c):
        return None, "no-temp"
    if kind == "qnh":
        return qnh_to_qff(float(raw), float(elev), float(temp_c)), None
    return station_to_qff(float(raw), float(elev), float(temp_c)), None


@dataclass(frozen=True)
class PresSample:
    """Un relevé de pression DÉJÀ ramené en QFF (hPa)."""
    t: int              # ms
    qff: float


@dataclass(frozen=True)
class PresPair:
    """Une heure appariée : le modèle et l'observation, tous deux en QFF."""
    t: int
    fcst_hpa: float
    obs_hpa: float
    n_obs: int


def mean_pressure(samples: Sequence[PresSample]) -> tuple[float | None, int]:
    """Moyenne arithmétique — et là, contrairement au vent, c'est juste.

    Une pression n'est pas une grandeur circulaire ; le piège du
    `mean_wind` (350° + 10° = 180°) n'existe pas ici. On garde quand
    même une fonction nommée pour que l'appariement se lise pareil des
    deux côtés.
    """
    vals = [s.qff for s in samples if _finite(s.qff)]
    if not vals:
        return None, 0
    return sum(vals) / len(vals), len(vals)


def pair_pressure(times: Sequence[int],
                  fcst_hpa: Sequence[float | None],
                  obs: Sequence[PresSample],
                  half_window_ms: int = OBS_HALF_WINDOW_MS) -> list[PresPair]:
    """Même fenêtre que le vent (±20 min), et c'est délibéré.

    Non pas parce que la pression aurait besoin de la même tolérance —
    elle varie bien plus lentement — mais parce que deux fenêtres
    différentes rendraient `n_hours` incomparable d'une variable à
    l'autre sur la même balise-jour, et personne ne le verrait.

    Les heures sans relevé sont ABSENTES, jamais interpolées.
    """
    if not times or not obs:
        return []
    ordered = sorted(obs, key=lambda o: o.t)
    out: list[PresPair] = []
    lo = 0
    for i, t in enumerate(times):
        f = fcst_hpa[i] if i < len(fcst_hpa) else None
        if not _finite(f):
            continue
        while lo < len(ordered) and ordered[lo].t < t - half_window_ms:
            lo += 1
        win = []
        j = lo
        while j < len(ordered) and ordered[j].t <= t + half_window_ms:
            win.append(ordered[j])
            j += 1
        if not win:
            continue
        m, n = mean_pressure(win)
        if m is None:
            continue
        out.append(PresPair(t=t, fcst_hpa=float(f), obs_hpa=m, n_obs=n))
    return out


def pressure_error(pairs: Sequence[PresPair]) -> float | None:
    """`pres_err_med` — erreur absolue médiane en hPa.

    ⛔ NE SE CALCULE QUE SUR DES BAROMÈTRES CALIBRÉS (METAR, MF, AEMET,
    SMN). Mesuré le 21/08 sur 764 stations Infoclimat : l'écart médian
    entre deux baromètres amateurs distants de MOINS DE 5 KM est de
    **1,18 hPa**, et il n'atteint 1,82 qu'à 200 km. La dispersion de
    calage écrase complètement le signal spatial ; une erreur absolue
    calculée là-dessus mesurerait nos capteurs, pas les modèles.
    C'est `score.py` qui applique cette règle (il connaît les sources),
    pas cette fonction (qui n'en connaît aucune).
    """
    errs = [abs(p.fcst_hpa - p.obs_hpa) for p in pairs]
    return median(errs)


def tendency_error(pairs: Sequence[PresPair],
                   hours: int = PTEND_HOURS) -> float | None:
    """`ptend_err_med` — erreur médiane sur la VARIATION à 3 h.

    Différence des variations : |(F(t) − F(t−3h)) − (O(t) − O(t−3h))|.
    Un décalage CONSTANT par station s'y annule, ce qui la rend valable
    même sur des baromètres mal calés — mesuré le 21/08 : la fonction de
    structure de la tendance d'Infoclimat (amateur) colle à celle de
    Météo-France (calibrée) à moins de 0,04 hPa sur toute la gamme
    0-200 km. C'est ce qui autorise Infoclimat sur CETTE métrique et le
    lui interdit sur l'autre.

    ⚠️ La paire à t−3h doit EXISTER : on ne va pas chercher la plus
    proche, on exige l'heure exacte. Une tendance calculée sur 2 h 40
    en croyant qu'elle en fait 3 est une erreur silencieuse.
    """
    par_t = {p.t: p for p in pairs}
    dt = hours * 3_600_000
    errs = []
    for p in pairs:
        avant = par_t.get(p.t - dt)
        if avant is None:
            continue
        errs.append(abs((p.fcst_hpa - avant.fcst_hpa)
                        - (p.obs_hpa - avant.obs_hpa)))
    return median(errs)
