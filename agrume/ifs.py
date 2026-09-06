#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/ifs.py — LE FORMAT ET LE CLIENT DE LA RALLONGE IFS
#                                         (Lot L22b, 06/09/2026)
#
#  La coupe AGRUME s'arrête à +51 h parce qu'AROME s'arrête là. Ce
#  module va chercher, chez ECMWF (open data, 0,25°, sans clé), les
#  échéances dont l'heure valide tombe entre 54 et 72 h après le run
#  AGRUME, et les met AU FORMAT DU PRODUIT B — mêmes blocs, mêmes
#  niveaux, mêmes dtypes.
#
#  ⛔ IL NE DÉCIDE RIEN ET N'ÉCRIT RIEN. Comme `piaf.py` pour la pluie et
#  `quantification.py` pour le produit A, ce fichier porte le FORMAT et
#  les conversions ; l'ingestion (`ingest_ifs.py`) fait le travail, et
#  c'est l'Action qui l'appelle. Le VPS ne touche aucun GRIB IFS.
#
#  ═══ LES SEPT FAITS MESURÉS LE 06/09, ET TROIS DÉMENTENT LE CADRAGE ═══
#
#  1. ✅ **Un run non publié rend 404, pas une réponse ambiguë.** Mesuré
#     sur `20260906/18z` et `20260907/00z` : `404`, corps de 79 octets.
#     C'est l'inverse du portail Météo-France, qui rend le même
#     `NoSuchCoverage` pour « pas encore là » et pour « ça n'existe
#     pas » (fait nº 3 du README AGRUME) — ici, le choix du run le plus
#     récent est DÉCIDABLE, et `run_disponible()` le décide.
#
#  2. ✅ **Les sept pas d'un run sont publiés AU MÊME INSTANT.** Mesuré
#     sur le run 00 Z du 06/09 : `Last-Modified` identique à la seconde
#     pour +54, +57, +60, +63, +66, +69 et +72 h. ⛔ C'est ce qui rend
#     ce lot possible SANS second guet : la rallonge AROME du 13/08 a
#     coûté un service systemd entier parce que Météo-France publie les
#     échéances lointaines entre 2 min et 3 h 33 APRÈS les proches.
#     Ici, une seule sonde sur le dernier pas suffit.
#
#  3. ✅ **La latence de publication est STABLE À LA MINUTE**, mesurée
#     sur 8 runs réels (04 et 05/09, quatre réseaux chacun) :
#         00 Z → 07:34 Z   (H+7 h 34)      12 Z → 19:34 Z   (H+7 h 34)
#         06 Z → 12:27 Z   (H+6 h 27)      18 Z → 00:27 Z   (H+6 h 27)
#     ⚠️ C'est une RÉGULARITÉ OBSERVÉE SUR DEUX JOURS, pas un contrat.
#     `LATENCE_MESUREE_S` sert à choisir quel run essayer EN PREMIER —
#     jamais à conclure qu'un run est là sans l'avoir demandé.
#
#  4. ⛔ **La sélection utile fait 29,3 Mo par pas, pas 50,4.** Le
#     cadrage du 04/09 comptait `u v t gh q r` sur les 14 niveaux
#     isobares d'IFS (89 messages). Nous n'avons besoin que des SEPT qui
#     sont aussi dans `NIVEAUX_P` : au-dessus de 400 hPa, le produit B
#     n'a aucun niveau à remplir. Mesuré sur le pas +54 h du 06/09 :
#     **47 messages, 29,26 Mo** sur 184 et 143,1 Mo, en **31 plages
#     d'octets contiguës**. ⇒ ~205 Mo par run, et non ~350.
#
#  5. ⛔⛔ **L'AXE DES LONGITUDES COMMENCE À 180°, ET CELUI DES LATITUDES
#     DESCEND DEPUIS 90 N.** Mesuré : `regular_ll`, 1440 × 721, premier
#     point (90,0 N ; 180,0 E), dernier (−90,0 ; 179,75), pas 0,25°,
#     `jScansPositively = 0`. D'où `i = ((lon − 180) mod 360)/0,25` et
#     `j = (90 − lat)/0,25`.
#
#     ⚠️ **ET LE PIÈGE N'EST PAS CELUI QUE CE COMMENTAIRE ANNONÇAIT —
#     le banc l'a démenti au premier essai.** `i = (lon + 180)/0,25`
#     donne EXACTEMENT le même indice sur tout [−180, 180[, parce que
#     `(lon − 180) mod 360 = lon + 180` là. Les deux écritures sont
#     interchangeables sur nos trois domaines.
#
#     ⛔ Le vrai piège est de supposer la grille calée sur **Greenwich**
#     (`i = lon/0,25`), qui est la convention la plus répandue : 720
#     points d'écart, soit **180°** — le domaine Nord-Alpes est lu au
#     milieu du Pacifique. Et son jumeau, supposer
#     `jScansPositively = 1`, bascule le domaine dans l'hémisphère sud.
#     Dans les deux cas le champ reste lisse, donc crédible. Le banc
#     mesure les deux en régrillant les champs « latitude » et
#     « longitude » eux-mêmes.
#
#  6. ⛔ **`gh` est en gpm, et c'est `gh` qu'on lit — jamais `z`.** Les
#     deux existent dans le fichier. `z` est un géopotentiel en m²/s² et
#     demande la division par g ; l'oublier donne des altitudes ~9,8
#     fois trop grandes (ce qui se voit), diviser deux fois en donne de
#     plausibles (ce qui ne se voit pas — README AGRUME, `G`). `gh` est
#     déjà une hauteur : il n'y a rien à diviser, donc rien à oublier.
#
#  7. ⛔⛔ **1000 ET 925 hPa SONT SOUS LE TERRAIN DANS LES ALPES, ET LE
#     FICHIER LE DIT.** Mesuré sur le pas +54 h : `gh` à 1000 hPa
#     descend à **−461 gpm**. Le bloc `h0025` (10 → 3 000 m/sol) doit
#     donc être DÉRIVÉ d'une colonne dont les deux niveaux du bas sont,
#     en montagne, de l'air fictif. `deriver_hauteurs()` les ÉCARTE
#     point par point et ancre la colonne sur le 10 m réel
#     (`10u`/`10v`/`2t`) — voir sa docstring, c'est le cœur du lot.
#
#  8. ⛔⛔ **LE BLOC HAUTEUR TIENT POUR LE VENT ET PAS POUR LA
#     TEMPÉRATURE, ET LA CAUSE EST MESURÉE.** Contrôle d'acceptation
#     joué le 06/09 sur la fenêtre de recouvrement (AROME et IFS ont
#     tous deux +48 et +51 h), MÊME run 12 Z, MÊMES heures valides,
#     11 655 colonnes × 25 niveaux × 2 échéances :
#
#         écart médian AROME ↔ IFS dérivé   bas (≤500 m)  haut (≥2000 m)
#           u                                 1,73 m/s      1,84 m/s   ×0,94
#           v                                 2,17 m/s      1,59 m/s   ×1,36
#           t                                 1,82 °C       0,71 °C    ×2,57
#
#     ⭐ **Le vent se comporte pareil en bas et en haut** — l'écart est
#     celui de deux modèles, pas celui de la dérivation. **La
#     température, non** : 2,6 fois pire en bas.
#
#     ⛔ Et ce n'est PAS la météo. L'orographie d'IFS (0,25°, dérivée de
#     `sp` et `gh`) diffère de celle d'AROME (0,025°, notre `zsol`) de
#     **198 m en médiane absolue, 590 m au d9, 1 866 m au pire**. Or
#     l'ancre `2t` est le 2 m d'IFS AU-DESSUS DU SOL D'IFS, et on la
#     pose sur le sol d'AROME. Mesuré : corrélation **r = 0,81** entre
#     |Δsol| et |Δt| à 10 m/sol, **pente 7,5 °C/km** — le gradient
#     atmosphérique vaut ~6,5 °C/km. L'écart de température en bas de
#     colonne EST l'écart d'orographie, à la précision de la mesure.
#
#     ⚠️ Trois réponses possibles, et ce module ne tranche pas : publier
#     tel quel en le MARQUANT (choix de Yann du 05/09, c'est ce qui est
#     fait) ; ne pas ancrer `t` du tout (bloc vide en bas dans les
#     Alpes) ; ou corriger `2t` du gradient sur Δsol — une réduction
#     standard, mais qui fabrique une valeur. Le manifeste porte
#     l'avertissement pour que l'écran puisse le dire.
#     ⓘ Le vent est peu sensible à l'altitude, la température l'est
#     directement : c'est pourquoi la même ancre tient pour l'un et pas
#     pour l'autre.
#
#  ⚠️ CE QUE CE MODULE NE PEUT PAS FABRIQUER, et qui reste `NaN` :
#  `tke` (bloc hauteur) et `cc` (bloc isobare) n'existent pas dans l'open
#  data IFS ; neuf des onze champs de surface non plus. Une valeur non
#  finie veut dire « rien à en dire », jamais zéro — et le manifeste
#  publie la liste plutôt que de laisser le silence passer pour une
#  absence de nuages.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import concurrent.futures
import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

import numpy as np

from domaine import NIVEAUX_H_0025, NIVEAUX_P
from quantification import Abort

# ══════════════════════════════════════════════════════════════════
#  CE QU'ON DEMANDE, ET OÙ
# ══════════════════════════════════════════════════════════════════

#: ⛔ Open data, SANS CLÉ — et c'est la moitié de la raison qui a fait
#: choisir IFS. L'autre moitié est dans les scores du 04/09 : IFS est
#: premier dans TOUS les massifs alpins à +48 h (Alpes du Nord 3,6 km/h
#: contre 4,5 pour ICON-EU et 4,9 pour ARPEGE).
BASE_URL = "https://data.ecmwf.int/forecasts"

#: Le gabarit, SANS l'extension : `.index` et `.grib2` partagent tout le
#: reste, et les séparer serait se donner deux chaînes à garder d'accord.
GABARIT = "{base}/{jour}/{heure:02d}z/ifs/0p25/oper/{jour}{heure:02d}0000-{step}h-oper-fc"

#: Les quatre réseaux, et le pas natif.
RUNS_IFS = (0, 6, 12, 18)
PAS_IFS_H = 3

#: Latence de publication MESURÉE (fait nº 3). Sert à ordonner les
#: essais, jamais à conclure.
LATENCE_MESUREE_S = {0: 7 * 3600 + 34 * 60, 6: 6 * 3600 + 27 * 60,
                     12: 7 * 3600 + 34 * 60, 18: 6 * 3600 + 27 * 60}

#: La fenêtre cousue, en heures APRÈS LE RUN AGRUME. 54 et non 52 :
#: AROME s'arrête à 51 h (`MAX_HOURS_GRILLE`) et le pas natif IFS est de
#: 3 h — 54 est la première heure valide disponible au-delà.
#: ⚠️ Le trou 51 → 54 h est ASSUMÉ ET VISIBLE (décision du 05/09) :
#: interpoler entre une échéance AROME et une échéance IFS mélangerait
#: deux modèles dans une même courbe sans le dire.
DEBUT_H = 54
FIN_H = 72

#: Les 14 niveaux isobares publiés (mesuré sur l'index, pas déduit).
NIVEAUX_IFS = (1000, 925, 850, 700, 600, 500, 400, 300, 250, 200, 150,
               100, 50, 10)

#: ⛔ LES SEPT QUE NOUS PARTAGEONS, ET LES SEPT QUE NOUS FABRIQUONS.
#: `NIVEAUX_COMMUNS` est ce qu'on télécharge ; `NIVEAUX_DERIVES` est ce
#: que `interpoler_log_p` fabrique — et que le manifeste doit nommer, un
#: par un, pour que `provenance()` puisse dire « interpolé
#: verticalement » sur ceux-là et seulement ceux-là.
NIVEAUX_COMMUNS = tuple(n for n in NIVEAUX_P if n in NIVEAUX_IFS)
NIVEAUX_DERIVES = tuple(n for n in NIVEAUX_P if n not in NIVEAUX_IFS)
assert len(NIVEAUX_COMMUNS) == 7 and len(NIVEAUX_DERIVES) == 7, (
    "l'inventaire du 06/09 donne 7 niveaux communs sur nos 14 — si ce "
    "compte change, c'est l'open data qui a bougé, et le budget du lot "
    "avec lui")

#: Ce qu'on tire sur les niveaux isobares, et à la surface.
#: ⚠️ `gh` et non `z` (fait nº 6). `q` est tiré sans être publié : il
#: n'a pas de case dans le produit B — il est là parce qu'il coûte
#: 5,25 Mo et qu'il est le seul chemin vers une humidité spécifique si
#: le raccord en demande une un jour. ⓘ À retirer si le budget serre.
PARAMS_PL = ("u", "v", "t", "gh", "q", "r")
PARAMS_SFC = ("10u", "10v", "2t", "msl", "sp")

#: ⛔ CE QUI N'EXISTE PAS, ÉCRIT PLUTÔT QUE TU. Le produit B a des cases
#: pour ces champs ; l'open data IFS ne les porte pas à ces échéances.
#: Elles restent `NaN`, et le manifeste publie CETTE liste.
#: ⓘ Quatre d'entre eux sont à portée pour ~4 Mo de plus par pas
#: (`2d` → td2m, `10fg` → rafale, `mucape` → cape, `ssrd` →
#: rayonnement, `tp` → precipitation) et ne coûteraient RIEN en
#: stockage : les cases sont déjà allouées. Non branché — hors du
#: cadrage du 04/09, à trancher par Yann.
ABSENTS = {
    "hauteur": ("tke",),
    "isobare": ("cc",),
    "surface": ("td2m", "rafale", "nuages_bas", "nuages_moyens",
                "nuages_hauts", "cape", "couche_limite", "rayonnement",
                "precipitation"),
}

#: La géométrie de la grille source, MESURÉE (fait nº 5).
SRC_LAT0, SRC_LON0, SRC_PAS = 90.0, 180.0, 0.25
SRC_NI, SRC_NJ = 1440, 721

#: Combien de plages d'octets on tire en parallèle. Mesuré depuis un
#: conteneur cloud : 31 plages en série = 40 s (0,7 Mo/s), dont
#: l'essentiel est de la latence par requête, pas du débit.
PARALLELE = 6


class AbsentIFS(Exception):
    """Le run (ou le pas) n'est pas publié. ⚠️ CE N'EST PAS UNE ERREUR —
    c'est la réponse « pas encore », et `run_disponible` s'en sert pour
    reculer d'un réseau. Confondre les deux ferait tomber l'Action à
    chaque fois qu'elle part trop tôt."""


# ══════════════════════════════════════════════════════════════════
#  QUEL RUN IFS, ET QUELLES ÉCHÉANCES
# ══════════════════════════════════════════════════════════════════

def echeances_cousues(run_agrume: datetime, run_ifs: datetime,
                      debut_h: int = DEBUT_H, fin_h: int = FIN_H) -> list[int]:
    """Les pas du run IFS dont l'HEURE VALIDE tombe dans la fenêtre.

    ⛔ LE CHOIX SE FAIT PAR HEURE VALIDE, JAMAIS PAR NUMÉRO DE PAS. Le
    run IFS n'est presque jamais celui d'AGRUME (mesuré : 18 Z de la
    veille chez Open-Meteo, 00 Z chez nous), donc « le pas +54 » d'IFS
    et « +54 h après AGRUME » désignent deux instants différents. Prendre
    le numéro donnerait une coupe décalée de plusieurs heures, lisse et
    crédible.

    ⚠️ Rend une liste VIDE plutôt que d'arrondir : si le décalage entre
    les deux runs n'est pas un multiple de 3 h, aucun pas IFS ne tombe
    sur nos heures, et il faut le dire — pas fabriquer l'échéance la
    plus proche.
    """
    ecart_h = (run_agrume - run_ifs).total_seconds() / 3600.0
    if ecart_h != int(ecart_h):
        return []
    ecart_h = int(ecart_h)
    return [h + ecart_h for h in range(debut_h, fin_h + 1)
            if (h + ecart_h) % PAS_IFS_H == 0 and h + ecart_h >= 0]


def heures_agrume(steps_ifs, run_agrume: datetime, run_ifs: datetime):
    """Les pas IFS traduits en HEURES APRÈS LE RUN AGRUME.

    ⛔⛔ LE SIGNE, ET RIEN D'AUTRE. `heure_agrume = pas_ifs − (run_agrume
    − run_ifs)`. L'inverser donne, pour un run IFS de 12 Z et un AGRUME
    de 00 Z, des échéances 30 → 48 au lieu de 54 → 72 : la coupe est
    décalée de VINGT-QUATRE heures, elle écrase des échéances AROME
    existantes, et rien ne s'allume — le contenu reste lisse et les
    tableaux ont la bonne forme.

    ⓘ Écrite ICI et appelée deux fois plutôt que recopiée : la première
    version de `ingest_ifs` la refaisait à la main, avec le signe à
    l'envers, et `echeances_cousues` (qui l'a juste) ne pouvait pas le
    voir.
    """
    ecart_h = int((run_agrume - run_ifs).total_seconds() // 3600)
    return [int(s) - ecart_h for s in steps_ifs]


def url_pas(run_ifs: datetime, step: int) -> str:
    return GABARIT.format(base=BASE_URL, jour=f"{run_ifs:%Y%m%d}",
                          heure=run_ifs.hour, step=step)


def _tete(url: str, timeout: int = 30):
    """`Last-Modified` d'un objet, ou `None` s'il n'est pas publié.

    ⛔ Le 404 est une RÉPONSE, pas une panne (fait nº 1) : il se traduit
    en `None`. Toute autre erreur remonte — un 500 chez ECMWF ne doit
    pas se lire « le run n'est pas là » et faire reculer la chaîne d'un
    réseau en silence.
    """
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.headers.get("Last-Modified")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def run_disponible(run_agrume: datetime, maintenant: datetime | None = None,
                   reculs: int = 4, tete=_tete, crier=print):
    """Le run IFS le plus RÉCENT dont tous les pas de la fenêtre sont
    publiés, ou `None`.

    ⛔ ON SONDE LE DERNIER PAS, ET LUI SEUL. Les sept pas d'un run sont
    publiés au même instant (fait nº 2, mesuré) : sonder les sept
    coûterait sept requêtes pour la même information. ⚠️ Ce raccourci
    REPOSE sur une mesure de deux jours — si un jour la coupe sort
    trouée en haut de fenêtre, c'est ICI qu'il faut revenir, et le
    manifeste porte `sonde` pour qu'on sache ce qui a été demandé.

    ⚠️ On recule par réseaux de 6 h, jamais par jours : un run vieux de
    24 h couvrirait encore la fenêtre, et serait accepté en silence. Le
    plafond `reculs` (4 réseaux = 24 h) est ce qui l'empêche.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    # Le réseau le plus récent qui soit théoriquement passé, puis on
    # recule. `LATENCE_MESUREE_S` ne décide pas : elle ordonne.
    base = maintenant.replace(minute=0, second=0, microsecond=0)
    base = base.replace(hour=(base.hour // 6) * 6)
    for k in range(reculs + 1):
        cand = base - timedelta(hours=6 * k)
        steps = echeances_cousues(run_agrume, cand)
        if not steps:
            continue
        lm = tete(url_pas(cand, max(steps)) + ".index")
        if lm is None:
            crier(f"    IFS {cand:%Y-%m-%dT%HZ} +{max(steps)}h : pas encore publié")
            continue
        return cand, steps, lm
    return None


# ══════════════════════════════════════════════════════════════════
#  L'INDEX, LA SÉLECTION, LES PLAGES
# ══════════════════════════════════════════════════════════════════

def lire_index(url_base: str, timeout: int = 60) -> list[dict]:
    """Les messages du `.index` — un JSON par ligne, `_offset`/`_length`."""
    try:
        with urllib.request.urlopen(url_base + ".index", timeout=timeout) as r:
            texte = r.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise AbsentIFS(f"{url_base}.index : 404") from exc
        raise
    return [json.loads(l) for l in texte.splitlines() if l.strip()]


def selection(msgs: list[dict], niveaux=NIVEAUX_COMMUNS,
              params_pl=PARAMS_PL, params_sfc=PARAMS_SFC) -> list[dict]:
    """Les messages qu'on tire, et pas un de plus.

    ⚠️ `int(levelist)` : le champ est une CHAÎNE dans l'index. Comparer
    `"850" in (850, ...)` est faux et silencieux — la sélection sortirait
    vide, le tirage réussirait, et la grille serait toute en `NaN`.
    """
    niveaux = set(niveaux)
    return [m for m in msgs
            if (m.get("levtype") == "pl" and m.get("param") in params_pl
                and int(m.get("levelist", -1)) in niveaux)
            or (m.get("levtype") == "sfc" and m.get("param") in params_sfc)]


def plages(sel: list[dict]) -> list[tuple[int, int]]:
    """Les plages d'octets CONTIGUËS à demander, fusionnées.

    Mesuré sur le pas +54 h : 47 messages → 31 plages. La fusion n'est
    pas une optimisation de confort — c'est 16 requêtes de moins par
    pas, soit 112 par run, sur une liaison où la latence domine le débit.
    """
    ordre = sorted(sel, key=lambda m: m["_offset"])
    out: list[list[int]] = []
    for m in ordre:
        a, b = m["_offset"], m["_offset"] + m["_length"]
        if out and a == out[-1][1]:
            out[-1][1] = b
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def tirer(url_base: str, bornes, parallele: int = PARALLELE,
          timeout: int = 180) -> bytes:
    """Les octets des plages demandées, concaténés DANS L'ORDRE.

    ⛔ L'ORDRE EST CELUI DES PLAGES, PAS CELUI DES RÉPONSES. Le tirage
    est parallèle ; recoller les morceaux dans l'ordre d'arrivée
    donnerait un fichier GRIB syntaxiquement valide dont les messages
    seraient mélangés — eccodes le lirait sans broncher, et chaque champ
    porterait les valeurs d'un autre.
    """
    def _un(k_ab):
        k, (a, b) = k_ab
        req = urllib.request.Request(
            url_base + ".grib2", headers={"Range": f"bytes={a}-{b - 1}"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return k, r.read()

    bornes = list(bornes)
    morceaux: dict[int, bytes] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallele) as ex:
        for k, d in ex.map(_un, list(enumerate(bornes))):
            morceaux[k] = d
    return b"".join(morceaux[k] for k in range(len(bornes)))


def decoder(octets: bytes) -> dict:
    """`{(shortName, level): tableau (721, 1440) float32}`.

    ⚠️ eccodes s'importe ICI et pas en tête de module : `test_ifs.py`
    doit tourner sans lui (les bancs du projet tournent sans réseau ET
    sans dépendance lourde), et `domaine.py` est importé par le VPS, qui
    n'a pas eccodes installé pour ce chemin-là.
    """
    import tempfile

    import eccodes as ec

    out = {}
    with tempfile.NamedTemporaryFile(suffix=".grib2") as f:
        f.write(octets)
        f.flush()
        with open(f.name, "rb") as g:
            while True:
                h = ec.codes_grib_new_from_file(g)
                if h is None:
                    break
                try:
                    nom = ec.codes_get(h, "shortName")
                    niv = int(ec.codes_get(h, "level"))
                    ni = int(ec.codes_get(h, "Ni"))
                    nj = int(ec.codes_get(h, "Nj"))
                    if (ni, nj) != (SRC_NI, SRC_NJ):
                        raise Abort(
                            f"géométrie IFS inattendue : {ni}×{nj} au lieu "
                            f"de {SRC_NI}×{SRC_NJ} — le régrillage repose "
                            f"sur cette grille, il ne la déduit pas")
                    val = ec.codes_get_values(h).astype(np.float32)
                    out[(nom, niv)] = val.reshape(nj, ni)
                finally:
                    ec.codes_release(h)
    return out


# ══════════════════════════════════════════════════════════════════
#  LE RÉGRILLAGE 0,25° → 0,025°
# ══════════════════════════════════════════════════════════════════

class Regrilleur:
    """Les poids bilinéaires de la grille IFS vers UNE grille de domaine.

    ⛔ LES POIDS SE CALCULENT UNE FOIS, PAS UNE FOIS PAR CHAMP. Un run
    régrille 47 champs × 7 échéances = 329 fois la même géométrie ;
    recalculer les indices à chaque coup, c'est 329 fois le même travail
    et 329 occasions d'écrire la formule de travers.

    ⛔⛔ ET LA GÉOMÉTRIE SOURCE NE SE DEVINE PAS (fait nº 5). L'axe des
    longitudes commence à 180° et celui des latitudes DESCEND depuis
    90 N. Supposer Greenwich (`i = lon/0,25`) décale de 720 points —
    180° — et lit le domaine au milieu du Pacifique ; supposer
    `jScansPositively = 1` le bascule dans l'hémisphère sud. Dans les
    deux cas le champ reste lisse, donc crédible à l'écran.
    ⓘ `(lon + 180)/0,25` est, elle, ÉQUIVALENTE sur [−180, 180[ : ce
    module l'a d'abord annoncée fautive, et le banc l'a démentie.

    ⚠️ On n'interpole PAS le relief, et ce n'est pas un raccourci : le
    champ IFS est lisse à 0,25°, le poser sur notre maille 0,025° ne
    fabrique aucune information. Ce qui porte le relief, c'est `zsol` —
    l'orographie AROME figée — et c'est elle qui décide, dans
    `deriver_hauteurs`, où commence la colonne.
    """

    def __init__(self, lats, lons):
        lats = np.asarray(lats, dtype=np.float64)
        lons = np.asarray(lons, dtype=np.float64)
        # ── latitudes : l'axe source DESCEND depuis 90 (jScans = 0) ──
        y = (SRC_LAT0 - lats) / SRC_PAS
        self.j0 = np.clip(np.floor(y).astype(np.int32), 0, SRC_NJ - 2)
        self.fy = (y - self.j0).astype(np.float32)
        # ── longitudes : origine 180°, et l'axe BOUCLE ───────────────
        x = ((lons - SRC_LON0) % 360.0) / SRC_PAS
        self.i0 = np.floor(x).astype(np.int32) % SRC_NI
        self.fx = (x - np.floor(x)).astype(np.float32)
        self.i1 = (self.i0 + 1) % SRC_NI
        self.forme = (len(lats), len(lons))

    def __call__(self, champ) -> np.ndarray:
        """Le champ source posé sur la grille du domaine (float32)."""
        j0, j1 = self.j0[:, None], (self.j0 + 1)[:, None]
        i0, i1 = self.i0[None, :], self.i1[None, :]
        fy, fx = self.fy[:, None], self.fx[None, :]
        v00 = champ[j0, i0]
        v01 = champ[j0, i1]
        v10 = champ[j1, i0]
        v11 = champ[j1, i1]
        haut = v00 * (1 - fx) + v01 * fx
        bas = v10 * (1 - fx) + v11 * fx
        return (haut * (1 - fy) + bas * fy).astype(np.float32)


# ══════════════════════════════════════════════════════════════════
#  L'INTERPOLATION VERTICALE — bloc `iso`
# ══════════════════════════════════════════════════════════════════

def poids_log_p(natifs=NIVEAUX_COMMUNS, cibles=NIVEAUX_P):
    """`[(k_bas, k_haut, w)]` par niveau cible, en `log p`.

    ⛔ EN `log p`, PAS EN `p`. Entre 1000 et 925 hPa l'écart d'altitude
    est d'environ 650 m ; entre 500 et 400, d'environ 1 500 m pour le
    même écart de 100 hPa. Interpoler linéairement en pression place
    950 hPa ~15 m trop haut et 450 hPa ~40 m trop bas — un biais qui ne
    saute jamais aux yeux et qui décale toute la moitié haute de la
    coupe.

    ⓘ Un niveau NATIF rend `(k, k, 0.0)` : il se recopie, il ne
    s'interpole pas. C'est ce qui garantit que les 7 niveaux communs
    sortent bit à bit ce que le GRIB portait.
    """
    lp = np.log(np.asarray(natifs, dtype=np.float64))
    out = []
    for p in cibles:
        x = np.log(float(p))
        if p in natifs:
            k = natifs.index(p)
            out.append((k, k, 0.0))
            continue
        # natifs DÉCROISSANTS en pression ⇒ `lp` décroissant
        k = None
        for i in range(len(natifs) - 1):
            if lp[i] >= x >= lp[i + 1]:
                k = i
                break
        if k is None:
            raise Abort(
                f"niveau {p} hPa hors de la bande native IFS "
                f"[{natifs[0]}, {natifs[-1]}] : ce module n'extrapole pas")
        w = (lp[k] - x) / (lp[k] - lp[k + 1])
        out.append((k, k + 1, float(w)))
    return out


def interpoler_log_p(pile, poids=None):
    """`(7, nj, ni)` natif → `(14, nj, ni)` sur `NIVEAUX_P`."""
    poids = poids if poids is not None else poids_log_p()
    pile = np.asarray(pile)
    out = np.empty((len(poids),) + pile.shape[1:], dtype=np.float32)
    for k, (a, b, w) in enumerate(poids):
        out[k] = pile[a] if a == b else pile[a] * (1 - w) + pile[b] * w
    return out


# ══════════════════════════════════════════════════════════════════
#  LA DÉRIVATION DU BLOC `h0025` — le cœur du lot, et son inconfort
# ══════════════════════════════════════════════════════════════════

def deriver_hauteurs(vals_iso, gh, zsol, ancre=None,
                     niveaux=NIVEAUX_H_0025):
    """Les 25 niveaux AGL, dérivés d'une colonne isobare + une ancre 10 m.

    `vals_iso` : `(n_natifs, nj, ni)` — le champ sur les niveaux IFS.
    `gh`       : `(n_natifs, nj, ni)` — l'altitude ASL de ces niveaux (gpm).
    `zsol`     : `(nj, ni)` — l'orographie AROME figée (m).
    `ancre`    : `(nj, ni)` ou `None` — la valeur à `zsol + 10 m`.

    ⛔⛔ CE QUE CETTE FONCTION FAIT DE PLUS QU'UNE INTERPOLATION, ET
    POURQUOI ELLE EXISTE.

    Dans les Alpes, 1000 et 925 hPa sont SOUS LE TERRAIN presque partout
    (`gh` mesuré à −461 gpm au minimum sur le pas +54 h du 06/09), et le
    modèle y met des valeurs extrapolées parfaitement crédibles — c'est
    le cinquième « ce qui casse en silence » du README AGRUME. Une
    interpolation naïve entre les sept niveaux irait donc chercher, pour
    « 100 m au-dessus du sol », un mélange d'air souterrain.

    Trois gestes, dans cet ordre :

    1. **Tout niveau dont `gh <= zsol + 10` est ÉCARTÉ, point par
       point.** Pas par domaine, pas par une règle « on jette 1000 et
       925 » : le même niveau est souterrain dans une vallée et libre
       au-dessus du lac d'à côté, et une règle globale se tromperait des
       deux façons.
    2. **La colonne est ANCRÉE sur le 10 m réel** (`10u`/`10v`/`2t`,
       champs dédiés), à l'altitude `zsol + 10`. Sans ancre, la tranche
       du décollage — 10 à 500 m/sol, celle que le parapentiste
       regarde — serait extrapolée sous le premier niveau libre, qui est
       souvent à plus de 1 000 m au-dessus du sol en montagne.
       ⚠️ `r` n'a PAS d'ancre (l'open data ne porte pas d'humidité
       relative à 2 m) : sous le premier niveau libre, il reste `NaN`.
       Une absence, jamais un zéro.
    3. **Aucune extrapolation, dans aucun sens.** Au-dessus du plus haut
       niveau libre comme sous l'ancre, la valeur reste `NaN`.

    ⚠️⚠️ CE QUE ÇA NE RÉPARE PAS, ET QU'IL FAUT MESURER : entre l'ancre
    (10 m) et le premier niveau libre, il n'y a RIEN. En montagne, cette
    tranche vide peut couvrir 1 000 m, et la colonne y est une simple
    droite entre le vent 10 m et le vent du premier isobare. Ce n'est
    pas un profil de couche limite — c'est une ligne. Le contrôle
    d'acceptation du lot (l'écart AROME ↔ IFS dérivé sur la fenêtre
    commune 48-51 h, `controle_h0025.py`) mesure exactement ce que cette
    ligne coûte, et c'est LUI qui dit si ce bloc mérite d'être servi.
    """
    vals_iso = np.asarray(vals_iso, dtype=np.float32)
    gh = np.asarray(gh, dtype=np.float32)
    zsol = np.asarray(zsol, dtype=np.float32)
    nj, ni = zsol.shape
    z_ancre = zsol + float(niveaux[0])

    # ── la pile : l'ancre en bas, puis les niveaux LIBRES ────────────
    #
    # ⛔⛔ LES NIVEAUX SOUTERRAINS SONT ÉCRASÉS SUR L'ANCRE, PAS MIS À
    # `NaN` — et la différence vaut 90 % du bloc. Mesuré sur le run
    # 12 Z du 06/09, domaine nord-alpes : 1000 hPa est sous le terrain
    # sur **98,9 %** des mailles, 925 sur **58,6 %**, 850 sur **29,2 %**.
    # Une première version les mettait à `NaN` : la boucle ci-dessous ne
    # regarde que des paires de niveaux ADJACENTS, donc le couple
    # (ancre, 1000 hPa) était mort, puis (1000, 925) aussi, et rien ne
    # se remplissait tant que DEUX niveaux consécutifs n'étaient pas
    # libres. Résultat mesuré : 1,1 % du niveau 10 m/sol renseigné,
    # 8,3 % à 100 m — un bloc vide qui n'aurait fait tomber aucun banc,
    # puisque `NaN` est une valeur légitime partout ailleurs.
    #
    # En les écrasant sur l'ancre, les intervalles souterrains
    # deviennent de largeur NULLE : `dz > 0` les saute, et le premier
    # intervalle réel part exactement de l'ancre. C'est la propriété
    # qu'on veut — sous le premier niveau libre, la colonne est la
    # droite entre le vent 10 m et lui, et rien d'autre.
    #
    # ⚠️ SANS ANCRE (`r`, qui n'a pas d'équivalent à 2 m dans l'open
    # data), on ne peut pas faire ça : écraser sur l'ancre reviendrait à
    # recopier une valeur qu'on n'a pas. Les niveaux souterrains partent
    # alors à `−inf` avec une valeur `NaN`, ce qui ne remplit rien sous
    # le premier niveau libre. Une absence, jamais une extrapolation.
    libre = gh > z_ancre[None, :, :]
    if ancre is not None:
        anc = np.asarray(ancre, dtype=np.float32)
        z = np.where(libre, gh, z_ancre[None, :, :])
        v = np.where(libre, vals_iso, anc[None, :, :])
        z = np.concatenate([z_ancre[None], z], axis=0)
        v = np.concatenate([anc[None], v], axis=0)
    else:
        z = np.where(libre, gh, -np.inf)
        v = np.where(libre, vals_iso, np.nan)

    out = np.full((len(niveaux), nj, ni), np.nan, dtype=np.float32)
    # ⚠️ `−inf − (−inf)` est un `nan` LÉGITIME ici (deux niveaux
    # souterrains consécutifs, sans ancre) : il est filtré par `dz > 0`
    # deux lignes plus bas. On tait cet avertissement-là, et lui seul,
    # plutôt que de le laisser polluer le journal d'un run.
    with np.errstate(invalid="ignore"):
        for k, h in enumerate(niveaux):
            cible = zsol + float(h)
            for a in range(z.shape[0] - 1):
                za, zb = z[a], z[a + 1]
                dedans = (np.isfinite(za) & np.isfinite(zb)
                          & (za <= cible) & (cible <= zb))
                if not dedans.any():
                    continue
                dz = zb - za
                # ⚠️ `dz > 0` : un intervalle de largeur nulle (niveau
                # souterrain écrasé sur l'ancre, ou colonne dégénérée)
                # donnerait une division par zéro et un `inf` qui se
                # quantifierait en une valeur parfaitement crédible.
                ok = dedans & (dz > 0)
                if not ok.any():
                    continue
                w = np.zeros_like(dz)
                np.divide(cible - za, dz, out=w, where=ok)
                val = v[a] + w * (v[a + 1] - v[a])
                # ⛔ On ne remplit QUE ce qui est encore vide : les
                # intervalles se touchent aux bornes (`za <= cible <=
                # zb`), et sans cette garde le suivant réécrirait le
                # précédent. Même résultat aujourd'hui — mais la
                # propriété « le premier intervalle qui contient la
                # cible gagne » cesserait d'être vraie le jour où la
                # pile ne serait plus monotone.
                prendre = ok & ~np.isfinite(out[k]) & np.isfinite(val)
                out[k][prendre] = val[prendre]
    return out


# ══════════════════════════════════════════════════════════════════
#  CE QUE LE MANIFESTE DOIT PORTER
# ══════════════════════════════════════════════════════════════════

def bloc_manifeste(run_ifs: datetime, steps_ifs, last_modified=None,
                   sonde=None) -> dict:
    """La déclaration IFS à coller dans le manifeste du produit B.

    ⛔ LES NIVEAUX NATIFS SONT PUBLIÉS, PAS DÉDUITS. `provenance()` doit
    pouvoir dire « IFS » sur une heure et « interpolé verticalement » sur
    un niveau — et l'écran ne peut pas le savoir en recoupant deux
    listes qu'il n'a pas. C'est la même discipline que
    `resolutionTemporelleMin` au Lot L2 : ce que l'objet ne porte pas,
    personne ne le devine.
    """
    return dict(
        modele="ecmwf_ifs025",
        nom="ECMWF IFS 0,25° (open data)",
        run_ifs=f"{run_ifs:%Y-%m-%dT%H:%M:%SZ}",
        publie_le=last_modified,
        pas_natif_h=PAS_IFS_H,
        echeances_ifs=list(steps_ifs),
        fenetre_h=[DEBUT_H, FIN_H],
        niveaux_natifs=list(NIVEAUX_COMMUNS),
        niveaux_interpoles=list(NIVEAUX_DERIVES),
        interpolation_verticale="linéaire en log p entre les niveaux natifs",
        regrillage="bilinéaire 0,25° → 0,025°, sans relief ajouté",
        bloc_hauteur_derive=(
            "les 25 niveaux AGL sont DÉRIVÉS des niveaux isobares "
            "(gh − zsol), ancrés sur le 10 m (10u/10v/2t) ; les niveaux "
            "sous le terrain sont écartés point par point"),
        # ⛔ CE QUE LE CONTRÔLE D'ACCEPTATION A MESURÉ, PUBLIÉ PLUTÔT QUE
        # TU. Un écran qui sert `t` sur ces échéances doit pouvoir dire
        # d'où vient son incertitude ; sans ce champ, il ne peut que se
        # taire — et un silence se lit « aussi bon que le reste ».
        avertissement_temperature=dict(
            portee="bloc hauteur, paramètre t, sous ~500 m/sol",
            mesure=(
                "contrôle du 06/09 (run 12 Z, échéances 48 et 51 h, "
                "11 655 colonnes) : écart médian AROME ↔ IFS dérivé de "
                "1,82 °C sous 500 m contre 0,71 °C au-dessus de 2000 m"),
            cause=(
                "l'ancre 2 m d'IFS est prise au-dessus de l'orographie "
                "d'IFS (0,25°) et posée sur celle d'AROME (0,025°), qui "
                "en diffère de 198 m en médiane absolue (d9 590 m, max "
                "1866 m) — corrélation r = 0,81 entre |Δsol| et |Δt|, "
                "pente 7,5 °C/km contre un gradient atmosphérique de "
                "~6,5 °C/km"),
            vent=(
                "u et v ne sont PAS concernés au même degré : rapport "
                "bas/haut ×0,94 et ×1,36, contre ×2,57 pour t"),
            non_corrige=(
                "aucune réduction n'est appliquée : corriger 2t du "
                "gradient sur Δsol fabriquerait une valeur, et ce lot "
                "publie ce qu'il a en le nommant")),
        absents=dict(ABSENTS),
        sonde=sonde,
        pourquoi_pas_arome=(
            "AROME s'arrête à 51 h (MAX_HOURS_GRILLE) ; le trou 51 → 54 h "
            "est laissé VISIBLE plutôt que comblé, parce qu'interpoler "
            "entre deux modèles dans une même courbe ne se voit pas"))
