#!/usr/bin/env python3
"""melange.py — le MÉLANGE MULTI-MODÈLE pondéré par nos propres scores
(lot L19, 04/09/2026), et la DISPERSION des membres qui va avec.

    Conception : `amelioration scoring/veille-spots-guru-algorithme-04-09.md`
    (§3.1 et §3.3) et `amelioration scoring/agrume/lot-l19-melange-biais-fin-04-09.md`.

═══ CE QUE C'EST ═══

Une PRÉVISION de plus, `bw_mix`, fabriquée chaque nuit à partir des
prévisions archivées des autres modèles : pour chaque balise et chaque
classe d'échéance, une moyenne pondérée en (u, v) des membres, le poids
d'un membre valant l'inverse de son erreur quadratique RÉCENTE sur cette
balise (EWMA de `err_vec_rms²`, demi-vie `MIX_DEMI_VIE_J`, lue dans le
cache de rejeu des jours STRICTEMENT antérieurs). C'est la brique
« Learning MultiModel » de meteoblue, réduite à ce que notre scoring
produit déjà : on mesure chaque nuit qui se trompe de combien, ici ; on
en tire qui croire, ici.

⛔ ELLE EST NOTÉE COMME UN MODÈLE, PAS SERVIE COMME UNE PRÉVISION. La
ligne synthétique entre dans les snapshots AVANT `daily_rows`, qui ne
sait toujours aucun nom de modèle : `bw_mix` est apparié, agrégé,
publié dans `model_verif_daily` et `model_score_zone` comme les autres —
et c'est sa vérification par construction. Il ne se CLASSE pas
(`RANK_REASON_SERIE_EN_ESSAI`, comme les sous-séries du L10) tant que
Yann n'a pas décidé, et aucun écran ne le sert.

═══ POURQUOI EN (u, v), ET PAS EN FORCE ═══

Leçon du L9(c), payée le 02/09 : un mélange fait dans un autre espace
que celui où `pair_error` mesure n'est pas convexe dans cet espace-là,
et peut sortir PIRE que chacun de ses membres (persistance 2 km/h à 0°
+ climatologie 20 km/h à 165° → force moyenne dans une direction
qu'aucune ne soutient). Ici les membres sont mélangés composante par
composante ; la force du mélange est la norme de la résultante, donc
deux membres opposés donnent un vent FAIBLE — ce qui est exactement ce
que « les modèles se contredisent » veut dire.

═══ LES DEUX TÉMOINS ═══

1. `bw_mix_u`, la MOYENNE UNIFORME des mêmes membres, écrite sur une
   balise sur `MIX_TEMOIN_PAS`. Si le mélange pondéré ne bat pas la
   moyenne bête, on ne sait pas pondérer — et c'est le placebo du S2
   transposé : ce qu'une moyenne gagne, elle le gagne sans rien
   savoir du site.
2. Le MEILLEUR MEMBRE A PRIORI (celui du plus gros poids), relu dans
   les lignes du jour : le mélange doit faire mieux que le modèle
   qu'on aurait choisi seul avec la même information. `bilan_melange`
   publie les deux, avec le n — jamais le gain seul.

⚠️ CE MODULE NE LIT NI L'ARCHIVE NI LE CACHE : il reçoit des lignes et
des poids, et rend des lignes. La lecture du cache vit dans `score.py`
(`prior_poids`), à côté de `prior_biais`, parce que c'est là que
`replay_read` et `_jour_index` habitent — et ce fichier doit rester
importable sans `score.py`, pour les bancs et pour le jour où
`score.py` est muté au point de ne plus s'importer.
"""
from __future__ import annotations

import math
import zlib
from typing import Sequence

import scoring as S

#: Le mélange pondéré par nos scores, et son témoin uniforme.
MODEL_MIX = "bw_mix"
MODEL_MIX_TEMOIN = "bw_mix_u"
MODELES_MELANGE = (MODEL_MIX, MODEL_MIX_TEMOIN)

#: Demi-vie de la mémoire d'erreur qui fait le poids, en jours. PLUS
#: COURTE que celle du biais de site (30 j) : un biais de site est un
#: caractère du relief, une supériorité de modèle est un état de la
#: saison — ECMWF peut mener en régime de nord et perdre en thermique.
MIX_DEMI_VIE_J = 15

#: Profondeur de cache lue pour bâtir les poids d'une journée.
MIX_PRIOR_JOURS = 30

#: Sous ce nombre de journées intégrées, un membre n'a PAS de poids et
#: n'entre pas dans le mélange. Un poids tiré de deux journées est un
#: poids de deux journées.
MIX_MIN_JOURS = 5

#: Membres minimaux pour qu'un mélange existe. Un mélange d'UN modèle
#: est ce modèle sous un autre nom — un avantage silencieux, refusé.
MIX_MIN_MEMBRES = 2

#: Une balise sur N reçoit AUSSI le témoin uniforme `bw_mix_u`.
MIX_TEMOIN_PAS = 7

#: Plancher de l'erreur quadratique qui entre au dénominateur du poids,
#: en (km/h)². Même rôle que `score.SKILL_MIN_REF_MSE` : une balise-jour
#: où un modèle a fait 0,05 km/h d'erreur RMS donnerait un poids 400
#: fois celui d'un modèle à 1 km/h — et ce 0,05 est du calme plat, pas
#: de la science.
MIX_MSE_MIN = 1.0

#: ⛔ UNE SEULE LECTURE PAR FAMILLE DE MODÈLE. `meteofrance_arome_france_hd`
#: (Open-Meteo), `arome_r2` (nos tuiles) et `agrume` (AROME brut du
#: produit A) sont TROIS lectures du même AROME : les mélanger toutes
#: donnerait à AROME trois voix sur six. Priorité dans l'ordre écrit —
#: la chaîne de référence d'abord (même règle que `_duplicate_chain_excluded`
#: au L2). `agrume_pi` n'est PAS de la famille : c'est AROME + PI, le
#: produit servi, et l'apport de PI est précisément ce que le duel
#: mesure ; il entre comme membre à part entière.
FAMILLES: dict[str, tuple[str, ...]] = {
    "arome": ("meteofrance_arome_france_hd", "arome_r2", "agrume"),
}

#: ⛔⛔ UNE LIGNE QUI SE DÉCLARE COPIE N'A PAS DE VOIX PROPRE (lot L22a,
#: 05/09/2026). `FAMILLES` refuse deux LECTURES d'un même modèle ; il ne
#: voit pas le cas où une série CHANGE de modèle avec l'échéance.
#:
#: C'est pourtant exactement ce que les lignes sœurs font : à +24 h,
#: `agrume`/`agrume_pi` portent de l'`arome_r2` recopié (L20) ; à +48 h,
#: de l'`ecmwf_ifs025` recopié (L22a). Sans cette règle, le mélange de
#: la classe +48 h recevait `ecmwf_ifs025` ET `agrume_pi` — deux membres
#: aux valeurs RIGOUREUSEMENT ÉGALES (c'est la même ligne copiée), donc
#: deux voix pour un seul modèle, et un poids doublé sans qu'une ligne
#: ne le dise. Même chose à +24 h pour AROME, depuis le L20.
#:
#: ⛔ LA RÈGLE EST PAR ÉCHÉANCE, ET ELLE DOIT L'ÊTRE. À +6 h, `agrume`
#: est de l'AGRUME calculé et garde sa voix ; c'est la MÊME ligne
#: fusionnée qui, à +48 h, n'est qu'une copie. Exclure le modèle partout
#: parce qu'une de ses lignes se déclare copie quelque part lui retirerait
#: la seule échéance où il a quelque chose à dire.
#:
#: ⚠️ MIROIR DE `agrume_fcst.CLASSES_SOEURS`, écrit deux fois À DESSEIN :
#: `melange.py` ne doit dépendre ni de numpy ni du paquet `agrume/`.
#: `test_agrume_fcst.py::test_les_declarations_de_copie_concordent`
#: compare les deux, champ par champ, plutôt que de faire confiance.
COPIES_PAR_LEAD: dict[int, tuple[str, str]] = {
    24: ("agrume_h24_copie", "agrume_h24_source"),
    48: ("agrume_h48_copie", "agrume_h48_source"),
}

#: Le pas des séries qu'on mélange. La classe au quart d'heure (900 s)
#: a ses propres sous-séries en essai ; on ne mélange pas deux pas.
MIX_STEP_S = 3600


class AccMse:
    """EWMA à poids temporel, en sommes — le patron de `score.AccBiais`,
    recopié (trois lignes) pour que ce module n'importe pas `score`."""
    __slots__ = ("sum_w", "sum_wx", "days", "last_day")

    def __init__(self):
        self.sum_w = 0.0
        self.sum_wx = 0.0
        self.days = 0
        self.last_day = None

    def push(self, day_i: int, x: float) -> None:
        if x is None or not S._finite(x):
            return
        if self.last_day is not None and day_i <= self.last_day:
            return
        decay = (1.0 if self.last_day is None
                 else 2 ** (-(day_i - self.last_day) / MIX_DEMI_VIE_J))
        self.sum_w = self.sum_w * decay + 1
        self.sum_wx = self.sum_wx * decay + x
        self.days += 1
        self.last_day = day_i

    @property
    def mean(self) -> float | None:
        return self.sum_wx / self.sum_w if self.sum_w > 0 else None


def poids_depuis_mse(accs: dict[str, AccMse],
                     min_jours: int = MIX_MIN_JOURS) -> dict[str, float] | None:
    """Les poids NORMALISÉS d'une balise × échéance : `1 / MSE` par membre.

    Un membre sous `min_jours` n'a pas de poids (il n'entre pas) ; sous
    `MIX_MIN_MEMBRES` membres, pas de mélange du tout (`None`).
    """
    bruts: dict[str, float] = {}
    for model, acc in accs.items():
        if acc.days < min_jours or acc.mean is None:
            continue
        bruts[model] = 1.0 / max(acc.mean, MIX_MSE_MIN)
    if len(bruts) < MIX_MIN_MEMBRES:
        return None
    total = sum(bruts.values())
    return {m: w / total for m, w in bruts.items()}


def unite(row: dict) -> str:
    return f"{row['source']}:{row['station_id']}"


def est_temoin(unit: str, pas: int = MIX_TEMOIN_PAS) -> bool:
    """Déterministe et indépendant de l'ordre des lignes : un crc, pas
    `hash()` (salé par processus depuis Python 3.3)."""
    return zlib.crc32(unit.encode("utf-8")) % pas == 0


def membres(rows_station: Sequence[dict], lead: int | None = None) -> list[dict]:
    """Les lignes d'UNE balise et d'UN offset qui ont le droit d'entrer.

    Écartées : les lignes qui déclarent leur échéance (`lead_h` — classe
    courte et quart, L10/L11), les lignes déjà synthétiques (`synthese`),
    les mélanges eux-mêmes, un autre pas que `MIX_STEP_S`, les doublons
    de famille (une lecture par famille, cf. `FAMILLES`) et — à
    l'échéance concernée — les séries qui s'y déclarent COPIE d'un modèle
    présent (cf. `COPIES_PAR_LEAD`).

    ⚠️ `lead` est la CLASSE (6, 24, 48), pas l'offset. Sans lui, la règle
    des copies ne s'applique pas : les appelants qui ne le passent pas
    (bancs d'avant le L22a) gardent le comportement d'avant.
    """
    out = []
    presents = {r.get("model") for r in rows_station}
    exclus_famille: set[str] = set()
    for _, lectures in FAMILLES.items():
        gardee = next((m for m in lectures if m in presents), None)
        exclus_famille |= {m for m in lectures if m != gardee}
    # ⛔ Les copies de CETTE échéance-ci, et d'aucune autre.
    champs = COPIES_PAR_LEAD.get(lead) if lead is not None else None
    if champs:
        champ_copie, champ_source = champs
        exclus_famille |= {r.get("model") for r in rows_station
                           if r.get(champ_copie)
                           and r.get(champ_source) in presents}
    # ⓘ Lot L20 (04/09) : un même modèle peut arriver en DEUX lignes —
    # AGRUME et sa ligne sœur +24 h (heures 24-47 lues dans arome_r2,
    # sous un autre run). Elles se FUSIONNENT par heure valide (la
    # première l'emporte là où les deux parlent) : deux lignes d'un même
    # modèle comptées comme deux membres lui donneraient deux voix.
    par_modele: dict[str, dict] = {}
    for r in rows_station:
        m = r.get("model")
        if (m is None or m in MODELES_MELANGE or m in exclus_famille
                or r.get("lead_h") is not None or r.get("synthese")
                or int(r.get("step_s") or 0) != MIX_STEP_S
                or not r.get("speed")):
            continue
        par_modele[m] = (r if m not in par_modele
                         else fusionner(par_modele[m], r))
    return list(par_modele.values())


def fusionner(a: dict, b: dict) -> dict:
    """Une ligne sur l'union des grilles de `a` et `b` (même pas), `a`
    prioritaire là où les deux ont une valeur. `fetched_at` = le plus
    ANCIEN des deux — même règle que `melanger` : pas de fraîcheur
    volée."""
    ta, tb = _times(a), _times(b)
    t0 = min(ta[0], tb[0])
    fin = max(ta[-1], tb[-1])
    n = (fin - t0) // MIX_STEP_S + 1
    speed: list = [None] * n
    direction: list = [None] * n
    for r, ts in ((b, tb), (a, ta)):          # b d'abord, a écrase
        sp, di = r.get("speed") or [], r.get("dir") or []
        for i, t in enumerate(ts):
            j = (t - t0) // MIX_STEP_S
            if i < len(sp) and S._finite(sp[i]):
                speed[j] = sp[i]
                direction[j] = di[i] if i < len(di) and S._finite(di[i]) else None
    out = dict(a)
    out.update({"t0": t0, "speed": speed, "dir": direction,
                "fetched_at": min(a["fetched_at"], b["fetched_at"])})
    return out


def _times(row: dict) -> list[int]:
    n = len(row.get("speed") or [])
    t0, step = int(row["t0"]), int(row["step_s"])
    return [t0 + i * step for i in range(n)]


def melanger(rows: Sequence[dict], poids: dict[str, float] | None,
             model: str = MODEL_MIX) -> dict | None:
    """UNE ligne synthétique au format EXACT de `collect.py`.

    `poids` = `{modèle: poids}` normalisés, ou `None` pour la moyenne
    uniforme (le témoin). Les membres absents de `poids` n'entrent pas.
    À chaque heure, les poids sont RENORMALISÉS sur les membres présents
    (une heure manquante chez un membre ne tire pas le mélange vers
    zéro). Un membre sans direction à une heure n'y entre pas — on ne
    peut pas vectoriser ce qui n'a pas de cap — sauf si AUCUN n'en a,
    auquel cas la force seule est moyennée et le cap reste nul.

    La ligne porte en plus : `spread` (par heure, la dispersion RMS des
    membres autour du mélange, km/h), `mix_n` (membres), `synthese`
    (le nom, pour que `event_rows` et `membres` la reconnaissent) et
    `hors_caractere` (elle ne nourrit pas `model_character`).
    """
    membs = [r for r in rows if poids is None or r["model"] in poids]
    if len(membs) < MIX_MIN_MEMBRES:
        return None
    w_of = ({r["model"]: 1.0 / len(membs) for r in membs} if poids is None
            else {r["model"]: poids[r["model"]] for r in membs})
    grilles = [_times(r) for r in membs]
    t0 = min(g[0] for g in grilles if g)
    t_fin = max(g[-1] for g in grilles if g)
    n = (t_fin - t0) // MIX_STEP_S + 1
    par_t = [dict(zip(g, range(len(g)))) for g in grilles]

    speed: list[float | None] = []
    direction: list[float | None] = []
    spread: list[float | None] = []
    for i in range(n):
        t = t0 + i * MIX_STEP_S
        vec: list[tuple[float, float, float]] = []   # (w, u, v)
        sca: list[tuple[float, float]] = []           # (w, force)
        for r, idx in zip(membs, par_t):
            j = idx.get(t)
            if j is None:
                continue
            sp = (r.get("speed") or [None] * (j + 1))[j]
            if not S._finite(sp):
                continue
            di = (r.get("dir") or [None] * (j + 1))[j]
            w = w_of[r["model"]]
            sca.append((w, float(sp)))
            if S._finite(di):
                vec.append((w, *S.to_uv(float(sp), float(di))))
        if vec:
            tw = sum(w for w, _, _ in vec)
            u = sum(w * uu for w, uu, _ in vec) / tw
            v = sum(w * vv for w, _, vv in vec) / tw
            f = math.hypot(u, v)
            speed.append(round(f, 3))
            direction.append(round(S.from_uv(u, v), 1) if f > 1e-9 else None)
            spread.append(round(math.sqrt(
                sum(w * ((uu - u) ** 2 + (vv - v) ** 2) for w, uu, vv in vec)
                / tw), 3))
        elif sca:
            tw = sum(w for w, _ in sca)
            f = sum(w * s for w, s in sca) / tw
            speed.append(round(f, 3))
            direction.append(None)
            spread.append(round(math.sqrt(
                sum(w * (s - f) ** 2 for w, s in sca) / tw), 3))
        else:
            speed.append(None)
            direction.append(None)
            spread.append(None)

    base = membs[0]
    return {
        "station_id": base["station_id"], "source": base["source"],
        "lat": base.get("lat"), "lon": base.get("lon"),
        "model": model,
        # ⚠️ LA PLUS ANCIENNE des émissions, pas la plus fraîche : le
        # mélange ne peut pas se prétendre plus frais que son membre le
        # plus vieux sans que `lead_exact_h` mente dans le sens flatteur.
        "fetched_at": min(r["fetched_at"] for r in membs),
        "t0": t0, "step_s": MIX_STEP_S,
        "speed": speed, "dir": direction, "gust": [None] * n,
        "spread": spread, "mix_n": len(membs),
        "mix_membres": sorted(w_of),
        "synthese": model, "hors_caractere": True,
    }


def ajouter_melange(snapshots: dict[int, list[dict]],
                    poids: dict[tuple, dict[str, float]],
                    lead_by_offset: dict[int, int]) -> tuple[dict[int, list[dict]], dict]:
    """Ajoute `bw_mix` (et `bw_mix_u` sur l'échantillon témoin) à chaque
    offset. Rend de NOUVELLES listes — les snapshots d'entrée ne sont
    pas modifiés — et un bilan `{offset: (n_mix, n_temoin, n_sans_poids)}`.

    `poids` est clé par `(unit, lead_h)` — le lead de la CLASSE, celui
    que `daily_rows` déduira de l'offset.
    """
    out: dict[int, list[dict]] = {}
    bilan: dict[int, tuple[int, int, int]] = {}
    for offset, rows in snapshots.items():
        lead = lead_by_offset.get(offset)
        par_unite: dict[str, list[dict]] = {}
        for r in rows:
            par_unite.setdefault(unite(r), []).append(r)
        ajouts: list[dict] = []
        n_mix = n_tem = n_sans = 0
        for unit, lignes in par_unite.items():
            membs = membres(lignes, lead)
            if len(membs) < MIX_MIN_MEMBRES:
                continue
            p = poids.get((unit, lead)) if lead is not None else None
            if p is None:
                n_sans += 1
            else:
                ligne = melanger(membs, p, MODEL_MIX)
                if ligne is not None:
                    ajouts.append(ligne)
                    n_mix += 1
            if est_temoin(unit):
                tem = melanger(membs, None, MODEL_MIX_TEMOIN)
                if tem is not None:
                    ajouts.append(tem)
                    n_tem += 1
        out[offset] = list(rows) + ajouts
        bilan[offset] = (n_mix, n_tem, n_sans)
    return out, bilan


def dire_bilan(bilan: dict, lead_by_offset: dict[int, int]) -> str:
    bouts = []
    for offset in sorted(bilan):
        n_mix, n_tem, n_sans = bilan[offset]
        bouts.append(f"+{lead_by_offset.get(offset, '?')} h : {n_mix} bw_mix, "
                     f"{n_tem} témoin(s) uniforme(s), {n_sans} balise(s) "
                     f"sans poids")
    return " · ".join(bouts) if bouts else "aucun snapshot"


# ══════════════════════════════════════════════════════════════════
#  LES TÉMOINS, relus dans les lignes du jour
# ══════════════════════════════════════════════════════════════════

def bilan_melange(rows: Sequence[dict], poids: dict[tuple, dict[str, float]],
                  cle: str = "err_vec_med") -> dict | None:
    """Ce que le mélange gagne sur (1) le meilleur membre A PRIORI et
    (2) la moyenne uniforme — par balise-jour × échéance, en médianes.

    ⛔ « Meilleur membre a priori » = celui du plus gros POIDS, donc
    choisi AVANT de voir la journée. Comparer au meilleur membre du
    jour (a posteriori) serait comparer à un oracle, et le mélange
    perdrait toujours — ce n'est pas la question posée.
    """
    par_cle: dict[tuple, dict[str, float]] = {}
    for r in rows:
        if r.get(cle) is None:
            continue
        k = (unite(r), r["lead_h"])
        par_cle.setdefault(k, {})[r["model"]] = r[cle]
    d_meilleur: list[tuple[float, float]] = []
    d_uniforme: list[tuple[float, float]] = []
    for k, errs in par_cle.items():
        mix = errs.get(MODEL_MIX)
        if mix is None:
            continue
        p = poids.get(k)
        if p:
            meilleur = max(p, key=lambda m: p[m])
            if errs.get(meilleur) is not None:
                d_meilleur.append((mix, errs[meilleur]))
        if errs.get(MODEL_MIX_TEMOIN) is not None:
            d_uniforme.append((mix, errs[MODEL_MIX_TEMOIN]))
    if len(d_meilleur) < 30:
        return None

    def _volet(paires):
        if not paires:
            return None
        a = S.median([x for x, _ in paires])
        b = S.median([y for _, y in paires])
        gagne = sum(1 for x, y in paires if x < y)
        return {"n": len(paires), "err_mix": _r(a), "err_reference": _r(b),
                "gain_pct": _r(100 * (b - a) / b, 1) if b else None,
                "mix_meilleur_pct": _r(100 * gagne / len(paires), 1)}

    vm = _volet(d_meilleur)
    vu = _volet(d_uniforme)
    texte = (f"sur {vm['n']} balise-jours×échéance, le mélange fait "
             f"{vm['err_mix']} km/h contre {vm['err_reference']} pour le "
             f"meilleur membre a priori (gain {vm['gain_pct']} %, mélange "
             f"devant dans {vm['mix_meilleur_pct']} % des cas)")
    if vu:
        texte += (f" ; contre la moyenne UNIFORME, sur {vu['n']} : "
                  f"{vu['err_mix']} vs {vu['err_reference']} "
                  f"(gain {vu['gain_pct']} %)")
    else:
        texte += " ; témoin uniforme sans matière cette nuit"
    return {"contre_meilleur_membre": vm, "contre_uniforme": vu,
            "colonne": cle, "texte": texte}


# ══════════════════════════════════════════════════════════════════
#  DISPERSION → CONFIANCE : la courbe dispersion-erreur (§3.3)
# ══════════════════════════════════════════════════════════════════

#: Balise-jours minimaux pour tracer la courbe. En dessous, on ne dit
#: rien — pas « exploitable », pas « non exploitable » : rien.
DISP_MIN_N = 100

#: Corrélation de rang minimale ET rapport dernier/premier décile
#: minimal pour que la dispersion ait le droit de se dire « confiance ».
DISP_RHO_MIN = 0.30
DISP_RAPPORT_MIN = 1.30


def _rangs(xs: Sequence[float]) -> list[float]:
    ordre = sorted(range(len(xs)), key=lambda i: xs[i])
    rangs = [0.0] * len(xs)
    i = 0
    while i < len(ordre):
        j = i
        while j + 1 < len(ordre) and xs[ordre[j + 1]] == xs[ordre[i]]:
            j += 1
        moy = (i + j) / 2 + 1
        for k in range(i, j + 1):
            rangs[ordre[k]] = moy
        i = j + 1
    return rangs


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    rx, ry = _rangs(xs), _rangs(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / math.sqrt(sxx * syy)


def bilan_dispersion(rows: Sequence[dict], cle_err: str = "err_vec_rms",
                     cle_disp: str = "spread_kmh", n_bins: int = 10) -> dict | None:
    """La relation dispersion → erreur, sur les balise-jours de `bw_mix`.

    ⛔ AVANT D'AFFICHER UNE PASTILLE « LES MODÈLES SONT D'ACCORD », il
    faut que l'erreur MONTE avec la dispersion — sinon la pastille dit
    quelque chose que la mesure contredit. Déciles de dispersion,
    erreur médiane par décile, rho de Spearman, et un verdict que
    l'écran a le droit de lire : `exploitable` / `non_exploitable`.
    """
    xs, ys = [], []
    for r in rows:
        if r.get("model") != MODEL_MIX:
            continue
        d, e = r.get(cle_disp), r.get(cle_err)
        if d is None or e is None or not S._finite(d) or not S._finite(e):
            continue
        xs.append(float(d))
        ys.append(float(e))
    if len(xs) < DISP_MIN_N:
        return None
    ordre = sorted(range(len(xs)), key=lambda i: xs[i])
    deciles = []
    for b in range(n_bins):
        lo = len(ordre) * b // n_bins
        hi = len(ordre) * (b + 1) // n_bins
        idx = ordre[lo:hi]
        if not idx:
            continue
        deciles.append({
            "spread_max": _r(max(xs[i] for i in idx)),
            "err_med": _r(S.median([ys[i] for i in idx])),
            "n": len(idx),
        })
    rho = spearman(xs, ys)
    premier, dernier = deciles[0]["err_med"], deciles[-1]["err_med"]
    rapport = (dernier / premier) if premier else None
    exploitable = (rho is not None and rho >= DISP_RHO_MIN
                   and rapport is not None and rapport >= DISP_RAPPORT_MIN)
    return {
        "n": len(xs), "rho_spearman": _r(rho, 3),
        "rapport_dernier_premier_decile": _r(rapport, 2),
        "deciles": deciles,
        "verdict": "exploitable" if exploitable else "non_exploitable",
        "seuils": {"rho_min": DISP_RHO_MIN, "rapport_min": DISP_RAPPORT_MIN,
                   "n_min": DISP_MIN_N},
        "texte": (f"sur {len(xs)} balise-jours de {MODEL_MIX}, rho = "
                  f"{_r(rho, 3)}, erreur médiane {premier} → {dernier} km/h "
                  f"du 1er au dernier décile de dispersion : "
                  + ("la dispersion PRÉDIT l'erreur, une pastille de "
                     "confiance est légitime"
                     if exploitable else
                     "la dispersion ne prédit pas assez l'erreur, AUCUNE "
                     "pastille de confiance ne doit s'afficher")),
    }


def _r(x, nd: int = 4):
    return None if x is None or not S._finite(x) else round(float(x), nd)
