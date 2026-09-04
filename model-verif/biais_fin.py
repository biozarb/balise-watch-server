#!/usr/bin/env python3
"""biais_fin.py — le biais de site PAR SECTEUR DE VENT ET PAR TRANCHE
HORAIRE, avec repli hiérarchique (lot L19, 04/09/2026, §3.2 de la veille).

═══ POURQUOI UNE PENTE PAR CELLULE ═══

Le S2 corrige UNE amplitude par balise × modèle × échéance : une pente
`Σ(o·f)/Σ(f²)` apprise sur trente jours. En montagne, le biais n'est pas
un : une balise de crête est sous-estimée par vent de nord et
surestimée par brise de sud ; une balise de vallée voit le modèle
avancer ou retarder la brise, donc se tromper le matin et pas l'après-
midi. C'est le cycle diurne que Schulz & Lerch (2021) trouvent décisif
sur 175 stations DWD — « la transition du soir de la couche limite ».

═══ LA CELLULE, ET POURQUOI ELLE EST CONNUE À L'AVANCE ═══

`quadrant(direction PRÉVUE)` × tranche de l'heure LOCALE. ⛔ La
direction est celle de la PRÉVISION, pas de l'observation : au moment
d'appliquer la correction à une prévision, on ne connaît qu'elle.
Conditionner sur l'observé serait choisir la correction après avoir vu
la réponse — le défaut exact que `pente_moindres_carres` a réparé au S2
pour la force, transposé au cap.

═══ LE REPLI ═══

    (balise, modèle, échéance, secteur, tranche)   « secteur_heure »
      ↳ (balise, modèle, échéance, secteur)          « secteur »
          ↳ (balise, modèle, échéance)                « balise »  = S2

Chaque niveau se tait sous `FIN_MIN_JOURS` journées ou `FIN_MIN_HEURES`
heures pondérées, et laisse la main au niveau au-dessus. Le niveau
« balise » est la pente du S2, passée telle quelle : ce module ne la
recalcule pas. Une prévision reçoit donc la correction la plus fine que
la matière autorise, jamais une correction tirée de deux heures.

═══ LES SOMMES VOYAGENT, PAS LES PENTES ═══

Chaque journée écrit `{cellule: [Σof, Σff, n]}` (clé privée
`_biais_fin`, cache de rejeu, jamais en base — même patron que
`_murphy`). Des sommes s'ADDITIONNENT avec décroissance ; des pentes ne
s'additionnent pas. Et le niveau « secteur » s'obtient en sommant les
tranches d'un même quadrant : pas de seconde comptabilité.

⚠️ CE MODULE NE LIT NI L'ARCHIVE NI LE CACHE — voir `melange.py`, même
raison. Il reçoit des paires et des sommes, rend des paires corrigées.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Sequence

import scoring as S

#: Les tranches de l'heure LOCALE. Trois, pas vingt-quatre : la brise
#: se lève le matin, culmine l'après-midi, tombe la nuit — c'est la
#: forme du cycle, et douze cellules par balise (4 quadrants × 3) se
#: remplissent en trente jours là où soixante-douze resteraient vides.
TRANCHES = ("nuit", "matin", "aprem")
HEURE_MATIN = 6      # [6, 12) → matin
HEURE_APREM = 12     # [12, 20) → aprem, le reste → nuit
HEURE_NUIT = 20

#: La clé PRIVÉE sous laquelle les sommes du jour voyagent dans le
#: cache de rejeu. Le `_` la tient hors de `_pour_la_base` (base) et
#: `replay_window` la retire de la fenêtre (mémoire) — `_murphy`, même
#: patron.
CLE = "_biais_fin"

NIVEAU_SECTEUR_HEURE = "secteur_heure"
NIVEAU_SECTEUR = "secteur"
NIVEAU_BALISE = "balise"
NIVEAUX = (NIVEAU_SECTEUR_HEURE, NIVEAU_SECTEUR, NIVEAU_BALISE)

#: Demi-vie, en jours. Celle du S2 : c'est le même caractère de site,
#: vu plus finement.
FIN_DEMI_VIE_J = 30

#: Journées intégrées minimales pour qu'une cellule (ou un secteur)
#: parle. Celle du S2 (`BIAIS_MIN_JOURS`).
FIN_MIN_JOURS = 3

#: Heures PONDÉRÉES minimales dans la cellule. Trois jours à une heure
#: par jour font trois heures : une pente de trois heures n'est pas un
#: caractère. Douze heures, c'est trois journées où la cellule a été
#: vue quatre heures — ou six journées à deux.
FIN_MIN_HEURES = 12.0

#: Mêmes garde-fous que le S2 : hors bornes on ne corrige PAS.
FIN_PENTE_MIN = 0.4
FIN_PENTE_MAX = 2.5


def tranche(t_ms: int, utc_offset_s: int) -> str:
    h = ((t_ms // 1000 + utc_offset_s) % 86_400) // 3600
    if HEURE_MATIN <= h < HEURE_APREM:
        return "matin"
    if HEURE_APREM <= h < HEURE_NUIT:
        return "aprem"
    return "nuit"


def cellule(p: S.VerifPair, utc_offset_s: int) -> str | None:
    """`"N|matin"`, ou `None` quand la prévision n'a pas de cap
    exploitable (sous `DIR_MIN_WIND_KMH`, un cap prévu est du bruit)."""
    if p.fcst_dir is None or p.fcst_speed < S.DIR_MIN_WIND_KMH:
        return None
    return f"{S.quadrant(p.fcst_dir)}|{tranche(p.t, utc_offset_s)}"


def secteur_de(cell: str) -> str:
    return cell.split("|", 1)[0]


def sommes_du_jour(pairs: Sequence[S.VerifPair],
                   utc_offset_s: int) -> dict[str, list[float]]:
    """`{cellule: [Σ(o·f), Σ(f²), n]}` d'une journée — la matière du
    cache. Les paires sans cellule n'y sont pas."""
    out: dict[str, list[float]] = {}
    for p in pairs:
        c = cellule(p, utc_offset_s)
        if c is None:
            continue
        s = out.setdefault(c, [0.0, 0.0, 0])
        s[0] += p.obs_speed * p.fcst_speed
        s[1] += p.fcst_speed * p.fcst_speed
        s[2] += 1
    return {c: [round(s[0], 4), round(s[1], 4), s[2]] for c, s in out.items()}


class AccSommes:
    """Sommes à décroissance temporelle — `AccBiais`, avec trois sommes."""
    __slots__ = ("sum_of", "sum_ff", "sum_n", "days", "last_day")

    def __init__(self):
        self.sum_of = 0.0
        self.sum_ff = 0.0
        self.sum_n = 0.0
        self.days = 0
        self.last_day = None

    def push(self, day_i: int, sommes: Sequence[float]) -> None:
        if not sommes or len(sommes) < 3 or not sommes[2]:
            return
        if self.last_day is not None and day_i <= self.last_day:
            return
        decay = (1.0 if self.last_day is None
                 else 2 ** (-(day_i - self.last_day) / FIN_DEMI_VIE_J))
        self.sum_of = self.sum_of * decay + float(sommes[0])
        self.sum_ff = self.sum_ff * decay + float(sommes[1])
        self.sum_n = self.sum_n * decay + float(sommes[2])
        self.days += 1
        self.last_day = day_i

    @property
    def pente(self) -> float | None:
        if (self.days < FIN_MIN_JOURS or self.sum_n < FIN_MIN_HEURES
                or self.sum_ff <= 0):
            return None
        p = self.sum_of / self.sum_ff
        if not (FIN_PENTE_MIN <= p <= FIN_PENTE_MAX):
            return None
        return p


class PriorFin:
    """L'antécédent fin d'UNE clé (balise, modèle, échéance) : une
    mémoire par cellule ET une par secteur, nourries ensemble."""
    __slots__ = ("cellules", "secteurs")

    def __init__(self):
        self.cellules: dict[str, AccSommes] = {}
        self.secteurs: dict[str, AccSommes] = {}

    def push(self, day_i: int, sommes_par_cellule: dict) -> None:
        # ⚠️ Le secteur additionne ses tranches AVANT de pousser : deux
        # `push` d'une même journée seraient refusés par le second.
        par_secteur: dict[str, list[float]] = {}
        for c, s in (sommes_par_cellule or {}).items():
            self.cellules.setdefault(c, AccSommes()).push(day_i, s)
            q = par_secteur.setdefault(secteur_de(c), [0.0, 0.0, 0])
            q[0] += float(s[0])
            q[1] += float(s[1])
            q[2] += s[2]
        for q, s in par_secteur.items():
            self.secteurs.setdefault(q, AccSommes()).push(day_i, s)

    def pente_pour(self, cell: str | None) -> tuple[float | None, str | None, int]:
        """`(pente, niveau, n_jours)` — le niveau le plus fin qui parle,
        `(None, None, 0)` si aucun : l'appelant retombe sur le S2."""
        if cell is None:
            return None, None, 0
        acc = self.cellules.get(cell)
        if acc is not None and acc.pente is not None:
            return acc.pente, NIVEAU_SECTEUR_HEURE, acc.days
        acc = self.secteurs.get(secteur_de(cell))
        if acc is not None and acc.pente is not None:
            return acc.pente, NIVEAU_SECTEUR, acc.days
        return None, None, 0

    def permute(self) -> "PriorFin":
        """Le PLACEBO : les mêmes mémoires, avec les étiquettes tournées
        (N→E→S→W→N, nuit→matin→aprem→nuit). Même couverture, mêmes
        effectifs, mêmes pentes — posées sur les MAUVAISES cellules. Ce
        que ce prior-là gagne encore n'est pas du secteur ni de l'heure :
        c'est du rétrécissement, et il se soustrait."""
        rot_q = {"N": "E", "E": "S", "S": "W", "W": "N"}
        rot_t = {"nuit": "matin", "matin": "aprem", "aprem": "nuit"}
        out = PriorFin()
        for c, acc in self.cellules.items():
            q, t = c.split("|", 1)
            out.cellules[f"{rot_q.get(q, q)}|{rot_t.get(t, t)}"] = acc
        for q, acc in self.secteurs.items():
            out.secteurs[rot_q.get(q, q)] = acc
        return out

    def vide(self) -> bool:
        return not any(a.pente is not None for a in self.cellules.values()) \
            and not any(a.pente is not None for a in self.secteurs.values())


def appliquer(pairs: Sequence[S.VerifPair], prior: PriorFin | None,
              pente_balise: float | None, cap: float | None,
              utc_offset_s: int) -> tuple[list[S.VerifPair], dict[str, int], int]:
    """Corrige chaque paire par la pente la plus fine disponible, le cap
    du S2 s'appliquant à toutes. Rend `(paires corrigées, compte par
    niveau, n_jours médian des cellules utilisées)`.

    ⚠️ Une paire pour laquelle AUCUN niveau ne parle — ni cellule, ni
    secteur, ni S2 — reste telle quelle et se compte sous `aucun`.
    """
    out: list[S.VerifPair] = []
    compte: dict[str, int] = {}
    jours: list[int] = []
    for p in pairs:
        pente, niveau, nj = (prior.pente_pour(cellule(p, utc_offset_s))
                             if prior is not None else (None, None, 0))
        if pente is None and pente_balise is not None:
            pente, niveau = pente_balise, NIVEAU_BALISE
        if pente is None:
            compte["aucun"] = compte.get("aucun", 0) + 1
            fs = p.fcst_speed
        else:
            compte[niveau] = compte.get(niveau, 0) + 1
            if nj:
                jours.append(nj)
            fs = p.fcst_speed * pente
        fd = p.fcst_dir
        if cap is not None and fd is not None:
            fd = (fd + cap + 360) % 360
        out.append(replace(p, fcst_speed=fs, fcst_dir=fd))
    nj_med = int(S.median(jours)) if jours else 0
    return out, compte, nj_med


def niveau_dominant(compte: dict[str, int]) -> str | None:
    """Le niveau qui a corrigé le plus d'heures — `None` si aucune."""
    utiles = {k: v for k, v in compte.items() if k in NIVEAUX and v}
    if not utiles:
        return None
    return max(utiles, key=lambda k: (utiles[k], -NIVEAUX.index(k)))


def bilan_temoin_fin(temoin: Sequence[tuple]) -> dict | None:
    """`(brut, corr_S2, corr_fin, placebo_fin)` par balise-jour
    échantillonné → ce que le FIN gagne sur le S2, et ce qu'un placebo
    (le MÊME antécédent, cellules tournées — `PriorFin.permute`)
    gagnerait.

    ⛔ Deux témoins, pas un. Le gain du fin sur le brut inclut celui du
    S2 ; ce qui compte ici est l'INCRÉMENT (`gain_fin_sur_s2_pct`), et
    l'incrément doit dépasser son placebo — sinon on s'arrête au S2.
    """
    utiles = [t for t in temoin if all(x is not None for x in t)]
    if len(utiles) < 30:
        return None
    brut = S.median([t[0] for t in utiles])
    s2 = S.median([t[1] for t in utiles])
    fin = S.median([t[2] for t in utiles])
    plac = S.median([t[3] for t in utiles])
    if not brut or not s2:
        return None
    g_s2 = 100 * (brut - s2) / brut
    g_fin = 100 * (brut - fin) / brut
    g_fin_s2 = 100 * (s2 - fin) / s2
    g_plac_s2 = 100 * (s2 - plac) / s2
    return {
        "n": len(utiles),
        "err_brut": _r(brut, 3), "err_corr_s2": _r(s2, 3),
        "err_corr_fin": _r(fin, 3), "err_placebo_fin": _r(plac, 3),
        "gain_s2_pct": _r(g_s2, 1), "gain_fin_pct": _r(g_fin, 1),
        "gain_fin_sur_s2_pct": _r(g_fin_s2, 1),
        "gain_placebo_sur_s2_pct": _r(g_plac_s2, 1),
        "part_secteur_heure_pct": _r(g_fin_s2 - g_plac_s2, 1),
        "texte": (f"sur {len(utiles)} balise-jours échantillonnés, le S2 "
                  f"gagne {g_s2:.1f} % sur le brut ; le fin gagne "
                  f"{g_fin_s2:.1f} point(s) de plus sur le S2, contre "
                  f"{g_plac_s2:.1f} pour le même antécédent aux cellules "
                  f"TOURNÉES — la part imputable au secteur et à l'heure "
                  f"est "
                  f"{g_fin_s2 - g_plac_s2:.1f} point(s)"),
    }


def _r(x, nd: int = 4):
    return None if x is None or not S._finite(x) else round(float(x), nd)
