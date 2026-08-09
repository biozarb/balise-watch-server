"""events.py — les ÉVÉNEMENTS de vent, côté job nocturne (lot F).

    Session 08/08/2026.
    cf. PWA/web/CONCEPTION_SCORE_MODELES_06-08.md §4 et §17.
    Portage de `src/lib/windEvents.ts` et `src/lib/breezeConflict.ts`.

═══ POURQUOI CE FICHIER, ET POURQUOI MAINTENANT ═══

Un RMSE de 4,2 km/h ne parle à personne. « AROME bascule la brise 40 min
trop tôt dans cette vallée, 9 fois sur 10 » est exploitable, mémorisable
et corrigeable de tête. C'est le §4, « le point le plus important du
document ».

Et il y a mieux que le confort de lecture (§4.3) : L'HEURE D'UNE BASCULE
NE DÉPEND PAS DE L'EXPOSITION DU MÂT. Une balise abritée lit une force
fausse et bascule quand même à la bonne heure. Les scores d'événements
sont donc structurellement immunisés contre le biais de site qui plombe
le score en force — ils n'ont pas besoin de la correction de biais de
`verifScore.ts` pour être justes. C'est ce qui justifie de les livrer
avant le socle statistique, et pas après.

═══ LA DÉCISION DU 08/08 QUI DÉBLOQUE CE FICHIER ═══

⚠️ À LIRE AVANT DE S'ÉTONNER QUE `model_verif_event` SE REMPLISSE.

Le commentaire de `supabase_step35_model_verification.sql` disait, et
disait à raison : « AUCUN JOB N'ÉCRIT ENCORE ICI, et c'est délibéré […]
les seuils de `windEvents.ts` et de `breezeConflict.ts` ne sont calibrés
sur rien, donc les événements qu'ils détectent ne valent pas encore
d'être notés. »

Yann a tranché le 08/08 au soir, en connaissance de cause : ON ÉCRIT ET
ON PUBLIE, avec les seuils par défaut, ET AVEC UN DRAPEAU EXPLICITE
`calibrated: false` dans le JSON publié. Trois raisons, dans l'ordre où
elles ont pesé :

 1. chaque nuit non notée est une nuit dont les événements ne seront
    jamais comptés — l'archive R2 permet de REJOUER la détection avec
    d'autres seuils, mais seulement si on a l'archive ; on l'a. Ce qui
    est perdu sans écrire, c'est seulement le temps ;
 2. le drapeau dit la vérité, ce qui est la règle de tout ce chantier :
    le lot D publie « n = 4, intervalle large » plutôt que de cacher un
    petit échantillon. Un POD annoncé « seuils raisonnés, non mesurés »
    est plus honnête qu'un POD absent et non expliqué ;
 3. la boucle de calibration décrite par `find-episodes.ts` n'est PAS
    branchée (vérifié le 08/08 : `grep -ic label src/lib/autotune.ts`
    rend 0). Attendre qu'elle se ferme, c'est attendre un chantier dont
    personne n'a la date.

Ce que cette décision N'AUTORISE PAS : présenter ces chiffres comme
calibrés, ici ou dans la PWA. Le drapeau voyage avec les données jusqu'à
l'affichage. Le jour où les seuils seront mesurés, il passe à `true` et
la détection se rejoue sur toute l'archive.

═══ AUCUN APPEL RÉSEAU, AUCUNE HORLOGE MACHINE ═══

Fonctions pures, comme `scoring.py` et pour la même raison : le même
comportement doit tenir côté client (TS) et côté VPS (Python), et
`test_events.py` le prouve en rejouant les mêmes entrées des deux côtés.

⚠️ Aucune fonction d'ici ne lit l'heure locale de la machine.
`windEvents.ts` n'a pas de logique horaire du tout ; `breezeConflict.ts`
en a une (la plage 9 h - 20 h) et reçoit son décalage en paramètre
explicite — `utc_offset_s`, même correctif que `regime.dominant_regime`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Callable, Iterable, Sequence

import scoring as S


def _js_round(x: float) -> int:
    """`Math.round` de JavaScript — qui n'est PAS `round()` de Python.

    ⚠️ Différence réelle et pas théorique, sur une valeur SIGNÉE qui est
    le cœur de ce lot. `round()` en Python arrondit au pair le plus
    proche (« banquier ») : `round(0.5)` rend 0, `round(1.5)` rend 2.
    `Math.round` arrondit toujours vers +∞ à mi-chemin : 1 et 2. Sur un
    décalage de timing d'une demi-minute, les deux portages sortiraient
    des minutes différentes une fois sur deux, et le banc de parité
    tomberait sur une différence qui n'est pas un défaut de logique.
    """
    return math.floor(x + 0.5)


# ══════════════════════════════════════════════════════════════════
#  TYPES ET PARAMÈTRES — repris À L'IDENTIQUE du TypeScript
# ══════════════════════════════════════════════════════════════════

#: Les quatre familles portées ici (E1 à E3 du catalogue §4.2).
#: `breeze_yield` est la cinquième valeur du `check` SQL et vient de
#: `detect_conflicts`, plus bas — mécanisme séparé, jamais fusionné.
WIND_EVENT_TYPES = ("reversal", "onset", "drop", "ramp")


@dataclass(frozen=True)
class DetectParams:
    step_ms: int
    smooth_ms: int
    min_turn_deg: float
    min_wind_kmh: float
    hold_ms: int
    ramp_thresholds: tuple[int, ...]


#: Réglages par défaut. ⚠️ AUCUN N'EST CALIBRÉ SUR DES DONNÉES RÉELLES —
#: ils sont raisonnés, pas mesurés (cf. le pavé d'en-tête). Leur
#: justification détaillée est dans `windEvents.ts`, elle n'est pas
#: recopiée ici pour qu'il n'y ait qu'un seul endroit à corriger le jour
#: où la calibration aura eu lieu.
DEFAULT_DETECT = DetectParams(
    step_ms=10 * 60 * 1000,
    smooth_ms=15 * 60 * 1000,
    min_turn_deg=100.0,
    min_wind_kmh=5.0,
    hold_ms=45 * 60 * 1000,
    ramp_thresholds=(20, 25, 30),
)


@dataclass(frozen=True)
class WindEvent:
    type: str
    t: int
    turn: float | None = None
    dir_before: float | None = None
    dir_after: float | None = None
    speed_before: float | None = None
    speed_after: float | None = None
    threshold: int | None = None


@dataclass(frozen=True)
class SmoothPoint:
    t: int
    speed: float
    dir: float | None


# ══════════════════════════════════════════════════════════════════
#  RÉÉCHANTILLONNAGE
# ══════════════════════════════════════════════════════════════════

def resample(obs: Sequence[S.ObsSample],
             p: DetectParams = DEFAULT_DETECT) -> list[SmoothPoint]:
    """Rééchantillonne et lisse une série à pas régulier, par moyenne
    VECTORIELLE glissante (jamais la moyenne arithmétique des caps).

    ⚠️ C'est ce rééchantillonnage qui rend la détection comparable entre
    réseaux. Un Pioupiou émet toutes les ~4 min, Météo-France toutes les
    5-6, SwissMetNet toutes les 10, un modèle toutes les 60. Sans pas
    commun, la même journée donnerait des heures de bascule différentes
    selon le réseau — et le score comparerait des réseaux plutôt que des
    modèles.

    ⚠️ Les pas sans aucun relevé dans la fenêtre sont ABSENTS du
    résultat, pas interpolés : un trou de données ne doit jamais se
    transformer en bascule fantôme au redémarrage de la série.
    """
    pts = sorted((o for o in obs if S._finite(o.speed)), key=lambda o: o.t)
    if not pts:
        return []
    step = p.step_ms
    # Ceil entier plutôt que `math.ceil(t / step)` : sur des
    # timestamps en millisecondes (1,7 × 10¹²), la division flottante
    # est encore exacte, mais l'entier ne dépend pas de cette chance.
    t0 = -((-pts[0].t) // step) * step
    t_n = pts[-1].t
    out: list[SmoothPoint] = []
    lo = 0
    t = t0
    while t <= t_n:
        while lo < len(pts) and pts[lo].t < t - p.smooth_ms:
            lo += 1
        win: list[S.ObsSample] = []
        j = lo
        while j < len(pts) and pts[j].t <= t + p.smooth_ms:
            win.append(pts[j])
            j += 1
        if win:
            speed, direction, _ = S.mean_wind(win, p.min_wind_kmh)
            if speed is not None:
                out.append(SmoothPoint(t=t, speed=speed, dir=direction))
        t += step
    return out


def _as_obs(points: Iterable[SmoothPoint]) -> list[S.ObsSample]:
    return [S.ObsSample(t=s.t, speed=s.speed, dir=s.dir) for s in points]


def _need(p: DetectParams, span_ms: int) -> int:
    """Nombre minimal de points exploitables dans une fenêtre.

    Reproduit `Math.max(2, Math.floor(span / step / 2))` du TS, y compris
    l'ordre des deux divisions : les faire en une seule (`span / (step *
    2)`) donnerait la même valeur ici mais pas forcément partout, et ce
    fichier n'a pas le droit d'être « équivalent », il doit être
    identique.
    """
    return max(2, math.floor(span_ms / p.step_ms / 2))


def _dedupe(events: Sequence[WindEvent], window_ms: int,
            score: Callable[[WindEvent], float]) -> list[WindEvent]:
    """Ne garde qu'un événement par grappe temporelle (le mieux noté).

    ⚠️ GRAPPES PAR CHAÎNAGE, pas par tranches de temps fixes. C'est la
    correction du 07/08 : avec des frontières fixes, trois détections à
    t, t+12 et t+20 min tombaient dans deux seaux différents et une
    seule bascule comptait pour deux dans la table de contingence
    (mesuré par `test-autotune-local.ts`). Ne pas réintroduire ce motif.

    ⚠️ En cas d'égalité de score, on garde le PREMIER — comme le
    `reduce` du TS, qui ne remplace que sur un `>` strict.
    """
    out: list[WindEvent] = []
    cluster: list[WindEvent] = []

    def flush() -> None:
        if not cluster:
            return
        best = cluster[0]
        for c in cluster[1:]:
            if score(c) > score(best):
                best = c
        out.append(best)

    for e in sorted(events, key=lambda x: x.t):
        if cluster and e.t - cluster[-1].t > window_ms:
            flush()
            cluster = []
        cluster.append(e)
    flush()
    return out


# ══════════════════════════════════════════════════════════════════
#  DÉTECTION — E1 (bascule), E2 (établissement/chute), E3 (renforcement)
# ══════════════════════════════════════════════════════════════════

def detect_reversals(series: Sequence[SmoothPoint],
                     p: DetectParams = DEFAULT_DETECT) -> list[WindEvent]:
    """Bascules de cap : E1.

    Pour chaque instant candidat, on compare le vent moyen de la fenêtre
    `hold_ms` AVANT à celui de la fenêtre `hold_ms` APRÈS.

    ⚠️ Comparer deux fenêtres LARGES plutôt que deux points consécutifs
    est ce qui rend la détection insensible aux sautes de girouette : un
    pic isolé ne déplace pas une moyenne de 45 min, une vraie bascule
    oui. Ça donne gratuitement le critère de maintien.
    """
    need = _need(p, p.hold_ms)
    cand: list[WindEvent] = []
    for i in range(len(series)):
        t = series[i].t
        before = [s for s in series
                  if s.t >= t - p.hold_ms and s.t < t
                  and s.dir is not None and s.speed >= p.min_wind_kmh]
        after = [s for s in series
                 if s.t > t and s.t <= t + p.hold_ms
                 and s.dir is not None and s.speed >= p.min_wind_kmh]
        # Au moins la moitié de chaque fenêtre doit être exploitable,
        # sinon on « détecte » surtout la fin d'un trou de données.
        if len(before) < need or len(after) < need:
            continue
        sb, db, _ = S.mean_wind(_as_obs(before), p.min_wind_kmh)
        sa, da, _ = S.mean_wind(_as_obs(after), p.min_wind_kmh)
        if db is None or da is None or sb is None or sa is None:
            continue
        if sb < p.min_wind_kmh or sa < p.min_wind_kmh:
            continue
        turn = abs(S.angular_diff(db, da))
        if turn < p.min_turn_deg:
            continue
        cand.append(WindEvent(type="reversal", t=t, turn=turn,
                              dir_before=db, dir_after=da,
                              speed_before=sb, speed_after=sa))
    return _dedupe(cand, p.hold_ms, lambda e: e.turn or 0.0)


def detect_ramps(series: Sequence[SmoothPoint],
                 p: DetectParams = DEFAULT_DETECT) -> list[WindEvent]:
    """Franchissements de seuil de force, à la hausse : E3.

    ⚠️ Un franchissement ne compte que s'il est MAINTENU — la MÉDIANE de
    la fenêtre suivante doit rester au-dessus du seuil. Exiger que TOUS
    les points y restent serait cassé par un seul creux de 10 min ;
    n'exiger rien reprocherait au modèle une rafale de 10 min, échelle
    de temps qu'un modèle horaire ne résout de toute façon pas.
    """
    need = _need(p, p.hold_ms)
    out: list[WindEvent] = []
    for threshold in p.ramp_thresholds:
        cand: list[WindEvent] = []
        for i in range(1, len(series)):
            prev, cur = series[i - 1], series[i]
            if not (prev.speed < threshold and cur.speed >= threshold):
                continue
            after = [s for s in series
                     if s.t >= cur.t and s.t <= cur.t + p.hold_ms]
            if len(after) < need:
                continue
            med = S.median(s.speed for s in after)
            if med is None or med < threshold:
                continue
            cand.append(WindEvent(type="ramp", t=cur.t, threshold=threshold,
                                  speed_before=prev.speed, speed_after=med))
        out.extend(_dedupe(cand, p.hold_ms, lambda e: e.speed_after or 0.0))
    out.sort(key=lambda e: e.t)
    return out


def detect_onset_drop(series: Sequence[SmoothPoint], threshold_kmh: float,
                      p: DetectParams = DEFAULT_DETECT) -> list[WindEvent]:
    """Établissement et chute du vent autour d'un seuil : E2.

    ⚠️ Volontairement séparé de `detect_ramps` bien que la mécanique se
    ressemble. L'établissement du matin et la chute du soir sont les
    deux TRANSITIONS QUOTIDIENNES d'un site de vol : ce sont elles dont
    l'erreur de timing intéresse le pilote qui prépare sa journée. Les
    confondre avec un renforcement de milieu d'après-midi mélangerait
    deux phénomènes qui n'ont ni la même physique ni le même usage.
    """
    need = _need(p, p.hold_ms)
    onset: list[WindEvent] = []
    drop: list[WindEvent] = []
    for i in range(1, len(series)):
        prev, cur = series[i - 1], series[i]
        after = [s for s in series if s.t >= cur.t and s.t <= cur.t + p.hold_ms]
        if len(after) < need:
            continue
        med = S.median(s.speed for s in after)
        if med is None:
            continue
        if prev.speed < threshold_kmh and cur.speed >= threshold_kmh and med >= threshold_kmh:
            onset.append(WindEvent(type="onset", t=cur.t, threshold=threshold_kmh,
                                   speed_before=prev.speed, speed_after=med))
        if prev.speed >= threshold_kmh and cur.speed < threshold_kmh and med < threshold_kmh:
            drop.append(WindEvent(type="drop", t=cur.t, threshold=threshold_kmh,
                                  speed_before=prev.speed, speed_after=med))
    merged = (_dedupe(onset, p.hold_ms, lambda e: -e.t)
              + _dedupe(drop, p.hold_ms, lambda e: -e.t))
    merged.sort(key=lambda e: e.t)
    return merged


#: Seuil d'établissement/chute par défaut. ⚠️ Même statut que les autres :
#: raisonné (12 km/h, l'ordre de grandeur où un site « marche »), pas
#: mesuré. Il est passé explicitement partout pour qu'un futur seuil par
#: zone (`ZONE_THRESHOLDS`) n'ait qu'un point d'entrée à changer.
DEFAULT_ONSET_KMH = 12


def detect_all(obs: Sequence[S.ObsSample],
               onset_threshold_kmh: float = DEFAULT_ONSET_KMH,
               p: DetectParams = DEFAULT_DETECT) -> list[WindEvent]:
    """Détection complète sur une série de relevés bruts."""
    s = resample(obs, p)
    merged = (detect_reversals(s, p)
              + detect_ramps(s, p)
              + detect_onset_drop(s, onset_threshold_kmh, p))
    merged.sort(key=lambda e: e.t)
    return merged


# ══════════════════════════════════════════════════════════════════
#  VÉRIFICATION PAR ÉVÉNEMENT — appariement flou et contingence (§4.1)
# ══════════════════════════════════════════════════════════════════

#: Tolérance d'appariement, par type.
#:
#: ⚠️ APPARIEMENT FLOU, ET C'EST UN CHOIX MÉTHODOLOGIQUE, PAS UNE
#: FACILITÉ. Un modèle qui annonce la bascule à 13 h quand elle a lieu à
#: 13 h 40 n'a PAS raté l'événement : il l'a vu, avec 40 min d'avance. Le
#: compter comme un raté ET comme une fausse alarme (ce que fait un
#: appariement strict) le pénalise deux fois pour une erreur qu'il n'a
#: commise qu'une fois, et jette au passage l'information la plus utile —
#: le décalage systématique, qui est corrigeable de tête par le pilote.
#:
#: Tolérances DIFFÉRENCIÉES, actées et testées le 06-07/08 : une bascule
#: se date à ±1 h 30 (elle s'installe progressivement), un franchissement
#: de seuil à ±1 h (plus net), une transition quotidienne à ±2 h
#: (l'établissement du matin est étalé, et c'est justement son décalage
#: qui intéresse).
MATCH_TOLERANCE_MS = {
    "reversal": 90 * 60 * 1000,
    "ramp": 60 * 60 * 1000,
    "onset": 120 * 60 * 1000,
    "drop": 120 * 60 * 1000,
    # ⚠️ SEULE ENTRÉE QUI N'EXISTE PAS DANS LE TS, et c'est assumé :
    # `windEvents.MATCH_TOLERANCE_MS` ne connaît que les quatre familles
    # de son propre fichier, `breeze_yield` venant de `breezeConflict.ts`
    # qui n'a jamais eu d'appariement. Le banc de parité ne soumet donc
    # que les quatre types communs — ajouter une cinquième clé côté TS
    # pour « symétriser » ferait porter à `windEvents.ts` un type qu'il
    # ne produit pas. ±90 min : un « la brise cède » se date comme une
    # bascule, c'en est une, avec un mécanisme de plus.
    "breeze_yield": 90 * 60 * 1000,
}


@dataclass(frozen=True)
class EventMatch:
    type: str
    outcome: str                       # 'hit' | 'miss' | 'false_alarm'
    timing_err_min: int | None         # prévu − observé, SIGNÉ. < 0 = en avance.
    obs_t: int | None
    fcst_t: int | None
    threshold: int | None = None


def match_events(observed: Sequence[WindEvent], forecast: Sequence[WindEvent],
                 tolerance: dict[str, int] | None = None) -> list[EventMatch]:
    """Apparie les événements prévus à ceux observés, avec tolérance.

    ⚠️ APPARIEMENT GLOUTON PAR PROXIMITÉ CROISSANTE, et pas dans l'ordre
    chronologique : on traite d'abord les couples les plus proches dans
    le temps, chacun consommant définitivement ses deux événements.
    L'appariement chronologique naïf produit des aberrations quand deux
    événements sont proches (le premier prévu se colle au premier
    observé même si le second lui correspondait beaucoup mieux).

    ⚠️ LES `ramp` NE S'APPARIENT QU'À SEUIL ÉGAL : un modèle qui annonce
    le franchissement des 20 km/h n'a pas prévu celui des 30. Sans cette
    règle, le POD des franchissements de seuil gonflerait tout seul.
    """
    tol_over = tolerance or {}

    def tol(ty: str) -> int:
        v = tol_over.get(ty)
        return v if v is not None else MATCH_TOLERANCE_MS[ty]

    pairs: list[tuple[int, int, float]] = []
    for oi, o in enumerate(observed):
        for fi, f in enumerate(forecast):
            if o.type != f.type:
                continue
            if o.type == "ramp" and o.threshold != f.threshold:
                continue
            d = abs(f.t - o.t)
            if d <= tol(o.type):
                pairs.append((oi, fi, d))
    # Tri STABLE sur la seule distance : à distance égale, l'ordre de
    # construction (observé croissant, puis prévu croissant) tranche —
    # exactement comme `Array.prototype.sort` côté TS, qui est stable.
    pairs.sort(key=lambda p: p[2])

    used_obs: set[int] = set()
    used_fcst: set[int] = set()
    out: list[EventMatch] = []
    for oi, fi, _d in pairs:
        if oi in used_obs or fi in used_fcst:
            continue
        used_obs.add(oi)
        used_fcst.add(fi)
        o, f = observed[oi], forecast[fi]
        out.append(EventMatch(type=o.type, outcome="hit",
                              timing_err_min=_js_round((f.t - o.t) / 60000),
                              obs_t=o.t, fcst_t=f.t, threshold=o.threshold))
    for oi, o in enumerate(observed):
        if oi in used_obs:
            continue
        out.append(EventMatch(type=o.type, outcome="miss", timing_err_min=None,
                              obs_t=o.t, fcst_t=None, threshold=o.threshold))
    for fi, f in enumerate(forecast):
        if fi in used_fcst:
            continue
        out.append(EventMatch(type=f.type, outcome="false_alarm",
                              timing_err_min=None, obs_t=None, fcst_t=f.t,
                              threshold=f.threshold))
    out.sort(key=lambda m: m.obs_t if m.obs_t is not None
             else (m.fcst_t if m.fcst_t is not None else 0))
    return out


@dataclass(frozen=True)
class ContingencyScore:
    hits: int
    false_alarms: int
    misses: int
    pod: float | None
    far: float | None
    csi: float | None
    frequency_bias: float | None
    timing_err_med_min: float | None
    timing_iqr_min: float | None


def score_events(matches: Sequence[EventMatch]) -> ContingencyScore:
    """Agrège des appariements en scores de contingence.

    ⚠️ CETTE FONCTION NE FILTRE RIEN. Sur 2 bascules dans la fenêtre, un
    POD vaut 0, 0,5 ou 1 et ne veut rien dire. C'est à l'APPELANT de
    vérifier `hits + misses` avant d'afficher quoi que ce soit — même
    règle que `rank_by_regime` et que le v0 par balise du lot D. Le
    quorum est `EVENT_MIN_OCCURRENCES`, appliqué dans `score.py`.

    ⚠️ Pour un événement RARE (orage, foehn — E6/E7), le CSI se dégrade
    mal et la littérature recommande SEDI. Non implémenté, et volontaire :
    les quatre familles portées ici sont quotidiennes ou quasi
    quotidiennes sur un site de vol, le CSI y est bien posé.
    """
    hits = sum(1 for m in matches if m.outcome == "hit")
    false_alarms = sum(1 for m in matches if m.outcome == "false_alarm")
    misses = sum(1 for m in matches if m.outcome == "miss")
    timings = sorted(m.timing_err_min for m in matches
                     if m.outcome == "hit" and m.timing_err_min is not None)

    def q(frac: float):
        if not timings:
            return None
        return timings[min(len(timings) - 1, math.floor(len(timings) * frac))]

    q1, q3 = q(0.25), q(0.75)
    return ContingencyScore(
        hits=hits, false_alarms=false_alarms, misses=misses,
        pod=hits / (hits + misses) if hits + misses > 0 else None,
        far=false_alarms / (hits + false_alarms) if hits + false_alarms > 0 else None,
        csi=(hits / (hits + false_alarms + misses)
             if hits + false_alarms + misses > 0 else None),
        frequency_bias=((hits + false_alarms) / (hits + misses)
                        if hits + misses > 0 else None),
        timing_err_med_min=S.median(timings),
        # Un décalage médian de 40 min ne vaut d'être annoncé que s'il
        # est RÉGULIER : l'IQR est ce qui permet de le dire.
        timing_iqr_min=(q3 - q1) if q1 is not None and q3 is not None else None,
    )


# ══════════════════════════════════════════════════════════════════
#  CONFIRMATION PAR LE RÉSEAU (§3.4)
# ══════════════════════════════════════════════════════════════════

def consolidate_network(
    per_station: Sequence[tuple[str, Sequence[WindEvent]]],
    min_stations: int = 2,
    cluster_ms: int = 30 * 60 * 1000,
) -> list[WindEvent]:
    """Ne retient que les événements CONFIRMÉS par plusieurs balises.

    ⚠️ C'EST ICI QUE LE RÉSEAU CHANGE LA NATURE DU RÉSULTAT, et pas
    seulement sa robustesse. Une balise isolée est incapable de
    distinguer un phénomène d'un artefact : une seule girouette qui
    tourne peut être une bascule, une rafale catabatique, un arbre qui a
    poussé, un roulement défaillant. Cinq balises d'une même vallée qui
    tournent dans les 30 minutes, ça ne peut être qu'une bascule.

    ⚠️ GRAPPES PAR CHAÎNAGE TEMPOREL, jamais par tranches fixes — même
    correction du 07/08 que `_dedupe`, et le piège n°2 explicitement
    listé par le prompt du lot F. Trois balises à t, t+12 et t+20 min
    forment UNE grappe, quelle que soit la position des frontières.

    ⚠️ L'instant retenu est la MÉDIANE de la grappe, plus robuste que la
    moyenne à une balise qui bascule très en avance parce qu'elle est en
    bout de vallée. Les caps et forces retenus sont ceux de l'événement
    médian, jamais une moyenne : moyenner les caps de balises situées
    dans des orientations de vallée différentes produirait un cap qui
    n'existe nulle part.
    """
    flat: list[tuple[str, WindEvent]] = []
    for station_id, evts in per_station:
        for e in evts:
            flat.append((station_id, e))
    flat.sort(key=lambda it: it[1].t)

    out: list[WindEvent] = []
    cluster: list[tuple[str, WindEvent]] = []

    def flush() -> None:
        if not cluster:
            return
        ids = {c[0] for c in cluster}
        if len(ids) >= min_stations:
            ts = sorted(c[1].t for c in cluster)
            t = S.median(ts)
            ref = cluster[len(cluster) // 2][1]
            if t is not None:
                out.append(replace(ref, t=t))

    for item in flat:
        if cluster:
            same_type = (cluster[0][1].type == item[1].type
                         and cluster[0][1].threshold == item[1].threshold)
            if not same_type or item[1].t - cluster[-1][1].t > cluster_ms:
                flush()
                cluster = []
        cluster.append(item)
    flush()
    out.sort(key=lambda e: e.t)
    return out


# ══════════════════════════════════════════════════════════════════
#  LA BRISE QUI TIENT TÊTE AU FLUX, PUIS QUI CÈDE — `breeze_yield` (§17)
# ══════════════════════════════════════════════════════════════════
#
# Portage de `src/lib/breezeConflict.ts`. MÉCANISME SÉPARÉ de tout ce
# qui précède, et il le reste : les deux écrivent dans la même table SQL
# mais ne partagent ni leur entrée (celui-ci exige un vent de crête) ni
# leur critère (celui-ci exige la STABILITÉ du flux d'altitude). Les
# fusionner « pour simplifier » ferait disparaître le seul discriminant
# qui sépare une brise qui cède d'une bascule ordinaire.
#
# ⚠️ CE DISCRIMINANT, EN UNE PHRASE. Une bascule de brise ordinaire
# (`detect_reversals`) tourne vers le secteur catabatique du soir, à
# l'opposé de l'anabatique. Une brise qui CÈDE tourne vers le cap du
# flux de crête, quel qu'il soit. Sans comparer au vent de crête, les
# deux sont indiscernables.

@dataclass(frozen=True)
class CrestSample:
    t: int
    speed_kmh: float | None
    dir_deg: float | None


@dataclass(frozen=True)
class ConflictParams:
    min_crest_kmh: float
    min_oppose_deg: float
    min_breeze_kmh: float
    min_hold_ms: int
    max_align_deg: float
    min_after_ms: int
    max_crest_drift_deg: float
    hours: tuple[int, int]
    utc_offset_s: int


#: ⚠️ AUCUN SEUIL CALIBRÉ. Ils encodent le récit de Yann sur la lombarde
#: de Maurienne (07/08), ce qui est déjà beaucoup plus qu'une intuition,
#: mais ce n'est pas une mesure. Justifications détaillées dans
#: `breezeConflict.ts` — un seul endroit à corriger.
DEFAULT_CONFLICT = ConflictParams(
    min_crest_kmh=20.0,
    min_oppose_deg=70.0,
    min_breeze_kmh=8.0,
    min_hold_ms=90 * 60 * 1000,
    max_align_deg=50.0,
    min_after_ms=60 * 60 * 1000,
    max_crest_drift_deg=45.0,
    # Plage horaire LOCALE ajoutée après le premier balayage réel du
    # 07/08 : 6 des 13 épisodes trouvés tombaient à 21 h 15, 23 h 45,
    # 6 h 10 — heures où il n'y a plus de brise anabatique du tout.
    hours=(9, 20),
    utc_offset_s=0,
)


def conflict_params(utc_offset_s: int,
                    base: "ConflictParams | None" = None) -> "ConflictParams":
    """Les paramètres de conflit pour un site donné.

    ⚠️ Point d'entrée unique du décalage horaire, pour que le jour où un
    décalage PAR SITE remplacera l'unique `--utc-offset-h` du job, il n'y
    ait qu'un appel à changer. Le piège corrigé au lot E (`regime.ts` et
    `breezeConflict.ts` lisant l'heure de la machine) ne se répare pas
    une fois : il se rend impossible à refaire.
    """
    return replace(base or DEFAULT_CONFLICT, utc_offset_s=utc_offset_s)


@dataclass(frozen=True)
class ConflictEpisode:
    hold_start: int
    yield_at: int
    crest_dir: float
    crest_speed: float
    breeze_dir: float
    breeze_speed: float
    after_dir: float
    hold_minutes: int
    stations: int | None = None


def crest_at(crest: Sequence[CrestSample], t: int,
             tolerance_ms: int = 90 * 60 * 1000) -> CrestSample | None:
    """Le relevé de crête le plus proche d'un instant, sans inventer
    hors plage : au-delà de la tolérance, on rend None plutôt que
    d'extrapoler un décor qu'on n'a pas observé."""
    best: CrestSample | None = None
    best_d = math.inf
    for c in crest:
        if c.speed_kmh is None or c.dir_deg is None:
            continue
        d = abs(c.t - t)
        if d < best_d:
            best_d = d
            best = c
    return best if best is not None and best_d <= tolerance_ms else None


def detect_conflicts(obs: Sequence[S.ObsSample], crest: Sequence[CrestSample],
                     p: ConflictParams = DEFAULT_CONFLICT,
                     dp: DetectParams = DEFAULT_DETECT) -> list[ConflictEpisode]:
    """Cherche les épisodes « la brise tient, puis cède au flux ».

    ⚠️ ON COLLECTE TOUS LES CANDIDATS AVANT DE TRANCHER, on ne prend pas
    le premier qui passe. Le premier jet gardait le premier instant
    satisfaisant les critères et datait la bascule 30 MINUTES TROP TÔT
    (mesuré par `test-autotune-local.ts`) : la fenêtre « après » se
    remplit progressivement du nouveau vent, et comme celui-ci est plus
    fort que la brise, il domine la moyenne vectorielle bien avant
    d'avoir réellement pris le dessus. Trente minutes d'erreur
    systématique seraient rédhibitoires — c'est l'ordre de grandeur de
    ce qu'on cherche justement à mesurer chez les modèles.
    """
    series = resample(obs, dp)
    if not series:
        return []

    need_before = _need(dp, p.min_hold_ms)
    need_after = _need(dp, p.min_after_ms)
    candidates: list[tuple[ConflictEpisode, float]] = []

    for i in range(len(series)):
        t = series[i].t
        # ⚠️ Décalage EXPLICITE du site, jamais l'horloge de la machine —
        # même formule que `regime.dominant_regime`, et même défaut
        # corrigé au lot E dans le TS.
        total_s = math.floor(t / 1000) + p.utc_offset_s
        hod = ((math.floor(total_s / 3600) % 24) + 24) % 24
        if hod < p.hours[0] or hod > p.hours[1]:
            continue

        before = [s for s in series
                  if s.t >= t - p.min_hold_ms and s.t < t and s.dir is not None]
        after = [s for s in series
                 if s.t > t and s.t <= t + p.min_after_ms and s.dir is not None]
        if len(before) < need_before or len(after) < need_after:
            continue

        sb, db, _ = S.mean_wind(_as_obs(before))
        sa, da, _ = S.mean_wind(_as_obs(after))
        if db is None or da is None or sb is None or sa is None:
            continue
        # Un vent nul ne tient tête à rien : « elle tenait » n'aurait
        # aucun sens.
        if sb < p.min_breeze_kmh:
            continue

        # Le flux de crête doit exister ET être stable sur tout
        # l'épisode. ⚠️ Sans la stabilité, on capterait un simple
        # changement de temps (le flux tourne, le sol suit) — banal et
        # sans intérêt ici. Tout l'objet de ce détecteur est le cas où
        # LE DÉCOR NE BOUGE PAS et où c'est l'équilibre local qui lâche.
        crest_pts = [c for c in (crest_at(crest, s.t) for s in before + after)
                     if c is not None]
        if len(crest_pts) < 3:
            continue
        cs, cd, _ = S.mean_wind([S.ObsSample(t=c.t, speed=c.speed_kmh, dir=c.dir_deg)
                                 for c in crest_pts])
        if cd is None or cs is None:
            continue
        if cs < p.min_crest_kmh:
            continue
        drift = max(abs(S.angular_diff(cd, c.dir_deg)) for c in crest_pts)
        if drift > p.max_crest_drift_deg:
            continue

        oppose_before = abs(S.angular_diff(cd, db))
        align_after = abs(S.angular_diff(cd, da))
        if oppose_before < p.min_oppose_deg:
            continue
        if align_after > p.max_align_deg:
            continue

        # ⚠️ DURÉE DE RÉSISTANCE MESURÉE, PAS RECOPIÉE. Le premier jet
        # écrivait `hold_minutes = min_hold_ms`, donc le rapport
        # affichait « Résistance : 90 min » sur les 13 épisodes trouvés
        # — un paramètre présenté comme un résultat.
        hold_start = t
        for k in range(i - 1, -1, -1):
            s = series[k]
            if s.dir is None or s.speed < p.min_breeze_kmh:
                break
            if abs(S.angular_diff(cd, s.dir)) < p.min_oppose_deg:
                break
            hold_start = s.t

        # ⚠️ ET LA DURÉE MESURÉE DOIT TENIR SES PROMESSES. Le balayage du
        # 07/08 a sorti un épisode à « 0 min de résistance » : la MOYENNE
        # de la fenêtre avant s'opposait au flux, mais aucun point
        # individuel juste avant la bascule ne le faisait. On ne peut pas
        # dire qu'une brise a tenu tête pendant zéro minute.
        if t - hold_start < p.min_hold_ms:
            continue

        candidates.append((
            ConflictEpisode(
                hold_start=hold_start, yield_at=t,
                crest_dir=cd, crest_speed=cs,
                breeze_dir=db, breeze_speed=sb, after_dir=da,
                hold_minutes=_js_round((t - hold_start) / 60000)),
            # Contraste maximal quand « avant » est purement brise
            # (opposition totale) et « après » purement flux (alignement
            # total). Même principe que `_dedupe`, score adapté.
            oppose_before - align_after,
        ))

    out: list[ConflictEpisode] = []
    cluster: list[tuple[ConflictEpisode, float]] = []

    def flush() -> None:
        if not cluster:
            return
        best = cluster[0]
        for c in cluster[1:]:
            if c[1] > best[1]:
                best = c
        out.append(best[0])

    for cand in candidates:
        if cluster and cand[0].yield_at - cluster[-1][0].yield_at > p.min_hold_ms:
            flush()
            cluster = []
        cluster.append(cand)
    flush()
    return out


def consolidate_conflicts(
    per_station: Sequence[tuple[str, Sequence[ConflictEpisode]]],
    min_stations: int = 2,
    cluster_ms: int = 45 * 60 * 1000,
) -> list[ConflictEpisode]:
    """Un épisode vu par PLUSIEURS balises de la même vallée.

    ⚠️ Même raison qu'ailleurs, encore plus forte ici : une brise qui
    cède sur UNE balise peut être un nuage qui passe et coupe le moteur
    thermique cinq minutes. Trois balises de la même vallée qui cèdent
    dans la même demi-heure, c'est le flux qui a gagné. C'est la
    différence entre un incident local et un basculement de régime — et
    seul le second mérite de noter un modèle.
    """
    flat: list[tuple[str, ConflictEpisode]] = []
    for station_id, eps in per_station:
        for e in eps:
            flat.append((station_id, e))
    flat.sort(key=lambda it: it[1].yield_at)

    out: list[ConflictEpisode] = []
    cluster: list[tuple[str, ConflictEpisode]] = []

    def flush() -> None:
        if not cluster:
            return
        ids = {c[0] for c in cluster}
        if len(ids) >= min_stations:
            t = S.median(c[1].yield_at for c in cluster)
            ref = cluster[len(cluster) // 2][1]
            if t is not None:
                out.append(replace(ref, yield_at=t, stations=len(ids)))

    for item in flat:
        if cluster and item[1].yield_at - cluster[-1][1].yield_at > cluster_ms:
            flush()
            cluster = []
        cluster.append(item)
    flush()
    return out


def conflicts_as_events(episodes: Sequence[ConflictEpisode]) -> list[WindEvent]:
    """Convertit des épisodes en `WindEvent` de type `breeze_yield`, pour
    les faire passer par le MÊME appariement que les autres familles.

    ⚠️ C'est une conversion de FORME, pas une fusion des détecteurs.
    L'instant retenu est `yield_at` — le moment où la brise cède, la
    seule valeur que le modèle doit prévoir. Le reste de l'épisode
    (durée de résistance, cap du flux) décrit la journée, pas la
    prévision, et n'a rien à faire dans une table de contingence.
    """
    return [WindEvent(type="breeze_yield", t=e.yield_at,
                      dir_before=e.breeze_dir, dir_after=e.after_dir,
                      speed_before=e.breeze_speed, speed_after=e.crest_speed)
            for e in episodes]


def rank_for_review(episodes: Sequence[ConflictEpisode]) -> list[tuple[ConflictEpisode, float]]:
    """Trie des épisodes par netteté, POUR LA BOUCLE DE CALIBRATION et
    pas pour le produit : un épisode ambigu validé de travers ferait plus
    de mal qu'un épisode non soumis, puisque c'est l'étiquette qui sert
    de vérité ensuite."""
    scored = [
        (e, (e.crest_speed / 20)
            * (abs(S.angular_diff(e.crest_dir, e.breeze_dir)) / 90)
            * max(1, e.stations or 1)
            * (e.breeze_speed / 10))
        for e in episodes
    ]
    scored.sort(key=lambda it: -it[1])
    return scored
