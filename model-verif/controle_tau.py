#!/usr/bin/env python3
"""controle_tau.py — le tau inter-POPULATIONS, contrôle n°3 du lot S3.

    Session 28/08/2026 (lot L8).
    cf. `amelioration scoring/agrume/LOTS_SCORING_AGRUME_27-08.md` §L8,
    `amelioration scoring/lot-s3-controles-veracite-23-08.md` §6 et §9,
    et l'audit `phase ABC/audit-scoring-integration-methode-26-08.md`
    PS3 (« Où en est le tau ? »).

═══ CE QUE CE FICHIER RÉPOND, ET CE QU'IL NE RÉPOND PAS ═══

La question est : **le classement des modèles dépend-il du RÉSEAU
d'observation qui le juge ?** Si les Pioupiou et les stations Infoclimat
rangent les mêmes modèles dans le même ordre, le classement publié parle
des modèles. S'ils les rangent autrement, il parle en partie du réseau —
et le produit publie alors une propriété de ses capteurs sous le nom
d'une propriété des prévisions.

⛔ CE N'EST PAS UN CLASSEMENT ET ÇA NE DOIT JAMAIS LE DEVENIR. Rien ici
n'écrit `rank`, `rank_reason`, ni une colonne de `model_score_zone`, ni
une ligne du fichier léger. C'est un contrôle de VÉRACITÉ : son livrable
est un rapport horodaté qu'un humain lit, et son seul pouvoir est de
faire douter d'un chiffre publié ailleurs.

⚠️ ET IL N'EST PAS NOCTURNE. La fenêtre doit s'ÉPAISSIR : un tau lu
chaque nuit sur une fenêtre qui bouge d'un jour se relit surtout
lui-même. Le rythme proposé est hebdomadaire (unités déposées sous
`systemd/`, ⬜ NON INSTALLÉES — cf. le prompt du lot).

═══ LES SIX CHOIX QUI FONT LA MESURE ═══

1. **Le tau se calcule sur les modèles PARTAGÉS, rerangés dans le
   sous-ensemble commun.** Un tau-b compte des paires concordantes :
   comparer « AROME d'un côté » aux « neuf de l'autre » mesurerait la
   différence entre MODÈLES, pas entre POPULATIONS — précisément la
   confusion que ce contrôle existe pour éviter (§6 de la note S3). Une
   population qui partage moins de `TAU_MIN_MODELES` modèles avec la
   référence n'a pas de tau, et le dit : `metar` en est là (k = 1,
   `arome_r2` seul), et ce n'est pas un défaut à réparer.

2. **On classe sur le NOYAU COMMUN de la population, pas sur les
   populations propres de chaque modèle.** C'est la leçon MESURÉE du lot
   L3 (audit §2.5.a), et ici elle mord plus fort qu'ailleurs : au
   27/08/2026, `arome_r2` couvre 5 jours sur les réseaux candidats
   (22→26/08) quand les cinq modèles du groupe réduit n'en couvrent que
   3 (24→26/08). Ranger `arome_r2` sur cinq journées contre `icon_eu`
   sur trois, c'est comparer des MÉTÉOS autant que des modèles — et
   c'est le premier suspect de la discordance que ce lot doit
   instruire. Le classement BRUT est calculé aussi, et publié à côté :
   la comparaison des deux EST la mesure.

3. **Le noyau commun se recalcule POUR CHAQUE POPULATION**, sur les k
   modèles qu'elle partage avec la référence — jamais une fois pour
   toutes sur les 12 modèles de Pioupiou. Sinon `agrume_pi` (né le
   25/08, 2 jours) réduirait à deux journées le noyau qui sert à juger
   `aemet`, qui ne connaît pas `agrume_pi`. ⚠️ Conséquence assumée : le
   classement de RÉFÉRENCE n'est pas le même d'une ligne à l'autre du
   rapport. Il est donc imprimé SUR CHAQUE LIGNE, jamais une fois en
   tête — un classement de référence qui voyage sans sa population se
   lit comme un absolu.

4. **On ORDONNE même quand la marche du haut n'est pas prouvée.** Le
   classement publié (`inference.rank_models`) refuse de classer tant
   que le premier ne bat pas le second par un test apparié : c'est la
   bonne règle pour un PRODUIT. Ici on veut mesurer l'accord de deux
   ORDRES, et refuser d'ordonner ne rendrait rien du tout. L'ordre
   utilisé est donc l'ordre brut des médianes — et le test apparié du
   1ᵉʳ contre le 2ᵉ est publié À CÔTÉ, sur chaque ligne, pour dire
   quelle part de cette marche est réelle. Les deux chiffres se lisent
   ensemble ou pas du tout.

5. **Les deux côtés sont ramenés aux MÊMES JOURNÉES.** Les deux
   populations ne partagent aucune balise — c'est leur définition — mais
   rien n'oblige leurs classements à porter sur la même période, et au
   27/08/2026 ils ne le faisaient pas : 2 journées côté `aemet` contre 5
   côté Pioupiou. Un désaccord entre deux semaines n'est pas un désaccord
   entre deux réseaux. Les journées écartées sont nommées dans le
   rapport.

6. **Les doublons d'inscription sont RETIRÉS avant de classer**, par la
   colonne `station_zone.doublon_de` du lot L17. Ce n'est pas une
   précaution de forme : le lot L16 a MESURÉ 346 paires sur 1 179 qui
   étaient le même capteur republié entre `pioupiou` et
   `windsmobi`/`ffvl`. Un tau `pioupiou ↔ windsmobi` calculé sur des
   populations qui partagent des capteurs PHYSIQUES mesurerait, pour
   partie, l'accord d'une balise avec elle-même — et il le ferait dans
   le sens qui rassure. Le nombre de balise-jours retirés est publié
   par population.

═══ LA RÉSERVE `run_init`, ET POURQUOI ELLE NE SE LÈVE PAS TOUTE SEULE ═══

La note S3 (§6, §9) l'exige en toutes lettres : *« Ne pas calculer le
tau sans regarder `run_init`. »* Les deux passes ne collectent pas à la
même heure — Pioupiou à 03:19 UTC (`collect.py`), les candidates à 05:00
(`collect_reduit.py`) — et il a été mesuré au S0.10 (n = 1 nuit) qu'
`icon_d2` sert aux candidates un run 3 h plus frais. Sur six modèles
comparés, un serait avantagé d'une échéance.

`verifier_run_init` va donc LIRE les archives de la fenêtre, flux par
flux, et rendre ce qu'elles portent — pas ce qu'on espère qu'elles
portent. Le résultat qualifie le tau : `reserve` voyage avec CHAQUE
ligne du rapport, et vaut `"non_verifiable"` quand l'archive ne permet
pas de trancher. ⛔ Un tau sans sa réserve ne doit pas pouvoir sortir
d'ici, c'est pour ça que le champ n'est pas optionnel.
"""
from __future__ import annotations

import os
import sys
from collections import defaultdict
from typing import Iterable, Mapping, Sequence

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inference as INF  # noqa: E402
import scoring as S  # noqa: E402


# ══════════════════════════════════════════════════════════════════
#  CE QU'ON CONTRÔLE
# ══════════════════════════════════════════════════════════════════

#: La population de RÉFÉRENCE. Toutes les autres sont comparées à
#: celle-ci, jamais entre elles : c'est le classement Pioupiou qui est
#: publié à l'écran, donc c'est lui dont on veut savoir s'il tient
#: ailleurs.
TAU_REFERENCE = "pioupiou"

#: L'échéance. `6` et pas `+6 h` : la valeur écrite en base par
#: `daily_rows` (`LEAD_BY_OFFSET`). Une seule, et c'est délibéré —
#: mélanger deux échéances dans un classement mélangerait deux
#: questions, et le tau ne saurait plus laquelle il mesure.
TAU_LEAD_H = 6

#: ⛔ LA COLONNE, ET C'EST CELLE DU CLASSEMENT PUBLIÉ. `typical_err_kmh`
#: (la colonne sur laquelle `rank_models` ordonne) EST la médiane par
#: blocs de jours d'`err_vec_med` — cf. `score.rolling_scores`,
#: `"typical_err_kmh": _r(ci.median)` sur `block_median_ci` des
#: `err_vec_med`. Classer ici sur `err_vec_med` reproduit donc l'ordre
#: du produit, ce qui est tout l'objet du contrôle.
#: ⚠️ Ce n'est PAS la colonne du duel (`err_vec_rms`, lot L1), et les
#: deux choix sont justes pour deux questions : le duel cherche un effet
#: de 0,03 km/h concentré sur six heures, ce contrôle cherche à savoir
#: si un CLASSEMENT tient — donc il doit porter sur la grandeur qui le
#: fabrique.
TAU_VALUE_KEY = "err_vec_med"

#: Profondeur lue par défaut, en jours. ⚠️ Plafonnée par la rétention de
#: `model_verif_daily` (`score.RETENTION_DAILY_D` = 30 jours), et bornée
#: bien avant par la naissance des flux : au 27/08/2026, les cinq
#: modèles du groupe réduit n'ont que 3 journées sur les candidates. Le
#: rapport publie la fenêtre RÉELLEMENT trouvée, jamais celle demandée.
TAU_DAYS = 14

#: Nombre minimal de modèles partagés pour qu'un tau existe. Deux, parce
#: qu'un tau-b compte des PAIRES : k = 1 donne zéro paire, k = 2 en donne
#: une. ⓘ Un tau sur une seule paire ne vaut que ±1 — il est rendu,
#: parce qu'un ±1 assorti de son k se lit correctement, alors qu'une
#: ligne absente ne se lit pas du tout.
TAU_MIN_MODELES = 2

#: Quorum d'entrée d'un modèle dans le classement d'une population :
#: LE MÊME que celui du classement publié (`scoring.REGIME_MIN_OCCURRENCES`
#: = 8 balise-jours), et importé plutôt que recopié. Le contrôle doit
#: comparer les ordres que le produit publierait ; s'en écarter ici
#: mesurerait l'accord de deux classements que personne ne verra jamais.
TAU_MIN_OCCURRENCES = S.REGIME_MIN_OCCURRENCES

#: Colonnes lues en base. Sélection étroite : la fenêtre entière à toutes
#: les colonnes, c'est ~300 000 lignes pour en lire six champs.
TAU_COLONNES = ("day", "source", "station_id", "model", "lead_h",
                "fcst_src", TAU_VALUE_KEY)


# ══════════════════════════════════════════════════════════════════
#  1. SÉLECTION — la même unité et le même refus que le duel
# ══════════════════════════════════════════════════════════════════

def _unit(row: Mapping) -> str:
    """L'identifiant de balise, MÊME FORME que `rolling_scores` et le duel.

    ⚠️ `source` ET `station_id`, jamais `station_id` seul : les
    identifiants ne sont uniques QUE par réseau, et le fichier le sait
    déjà — `arome_fcst.charger_balises` dédoublonne sur `source:id` en
    disant que `mf` et `infoclimat` portent DÉJÀ les mêmes id. Ici, où
    l'on manipule cinq réseaux à la fois, une collision apparierait deux
    balises étrangères sans qu'aucun compteur ne bouge.
    """
    return f"{row['source']}:{row['station_id']}"


def lignes_par_modele(daily: Iterable[Mapping], source: str,
                      lead_h: int | None = TAU_LEAD_H,
                      value_key: str = TAU_VALUE_KEY,
                      doublons: frozenset[str] = frozenset(),
                      ) -> tuple[dict[str, list[dict]], dict]:
    """Les balise-jours d'UNE population, rangés par modèle.

    Rend `(lignes_par_modele, bilan)`. `bilan` porte les trois
    dénombrements qui doivent voyager avec le chiffre : `doublons_ecartes`
    (deux `fcst_src` pour une même balise-jour-modèle), `doublons_reseau`
    (balise retirée par `station_zone.doublon_de`), `n_balises`.

    ⛔ LE DOUBLON DE CHAÎNE N'EST PAS TRANCHÉ, IL EST ÉCARTÉ — doctrine
    du lot L1, reprise à l'identique et pour la même raison. La clé
    d'upsert de `model_verif_daily` est `(day, source, station_id, model,
    lead_h, fcst_src)` : deux lignes peuvent légitimement coexister pour
    la même balise-jour si elles viennent de deux chaînes. Au 27/08/2026
    une seule valeur existe en base (`own_archive`), donc le cas ne se
    produit pas — et c'est précisément pour ça qu'il faut l'écrire
    maintenant, pendant qu'on peut vérifier que le compteur reste à zéro.

    ⛔ LE DOUBLON DE RÉSEAU, LUI, EST RETIRÉ — et c'est le §5 de
    l'en-tête. Il ne s'agit pas de la même faute : ici la balise existe
    bel et bien deux fois, sous deux réseaux, et les deux populations
    comparées la contiennent chacune une fois.
    """
    par_modele: dict[str, dict[tuple, dict]] = defaultdict(dict)
    vus_deux_fois: dict[str, set[tuple]] = defaultdict(set)
    bilan = {"doublons_ecartes": 0, "doublons_reseau": 0, "n_lignes": 0}
    balises: set[str] = set()
    for r in daily:
        if r.get("source") != source:
            continue
        if lead_h is not None and r.get("lead_h") != lead_h:
            continue
        u = _unit(r)
        if u in doublons:
            bilan["doublons_reseau"] += 1
            continue
        if not S._finite(r.get(value_key)):
            continue
        m = r.get("model")
        cle = (r["day"], u)
        if cle in par_modele[m]:
            vus_deux_fois[m].add(cle)
            continue
        par_modele[m][cle] = {"day": r["day"], "unit": u,
                              value_key: float(r[value_key])}
        balises.add(u)
    out: dict[str, list[dict]] = {}
    for m, d in par_modele.items():
        for cle in vus_deux_fois[m]:
            d.pop(cle, None)
        bilan["doublons_ecartes"] += len(vus_deux_fois[m])
        if d:
            out[m] = sorted(d.values(), key=lambda x: (x["day"], x["unit"]))
            bilan["n_lignes"] += len(d)
    bilan["n_balises"] = len(balises)
    return out, bilan


# ══════════════════════════════════════════════════════════════════
#  2. LE NOYAU COMMUN — la leçon du lot L3, appliquée aux populations
# ══════════════════════════════════════════════════════════════════

def noyau_commun(lignes: Mapping[str, Sequence[Mapping]],
                 modeles: Sequence[str]) -> set[tuple]:
    """Les balise-jours que TOUS les `modeles` notent ensemble.

    ⛔ POURQUOI CE N'EST PAS UN RAFFINEMENT. Mesuré en base le 28/08 :
    sur `infoclimat`, `arome_r2` porte 3 671 balise-jours étalés sur
    5 journées (22→26/08) et `icon_eu` 1 203 sur 3 (24→26/08). Comparer
    la médiane du premier à celle du second, c'est comparer une semaine
    à une autre : les 22 et 23 août ne sont pas dans les deux tableaux.
    L'écart obtenu contient de la MÉTÉO, et il en contient d'autant plus
    que la fenêtre est courte.

    ⚠️ Un modèle absent d'un seul jour vide le noyau de ce jour pour
    TOUT LE MONDE. C'est le prix de l'appariement, il est connu, et il
    est publié : `n_noyau` contre `n_brut` sur chaque ligne. Le jour où
    ce prix devient prohibitif, la réponse n'est pas d'abandonner le
    noyau — c'est de retirer du tableau le modèle qui le crève, et de
    le DIRE.
    """
    if not modeles:
        return set()
    noyau: set[tuple] | None = None
    for m in modeles:
        cles = {(r["day"], r["unit"]) for r in lignes.get(m, ())}
        noyau = cles if noyau is None else (noyau & cles)
        if not noyau:
            return set()
    return noyau or set()


def _restreindre(lignes: Sequence[Mapping], noyau: set[tuple]
                 ) -> list[dict]:
    return [dict(r) for r in lignes if (r["day"], r["unit"]) in noyau]


def classement(lignes: Mapping[str, Sequence[Mapping]],
               modeles: Sequence[str],
               value_key: str = TAU_VALUE_KEY,
               min_occurrences: int = TAU_MIN_OCCURRENCES,
               ) -> dict:
    """L'ordre d'une population sur un jeu de modèles donné.

    Rend un dict : `rangs` (modèle → 1..k), `lignes` (une par modèle,
    avec n et médiane), `exclus` (modèles sous quorum, avec leur n),
    `verdict_marche` (le test apparié du 1ᵉʳ contre le 2ᵉ).

    ⚠️ L'ORDRE EST CELUI DES MÉDIANES, PAS CELUI DE `rank_models` —
    §4 de l'en-tête. `rank_models` refuse d'ordonner quand la marche du
    haut n'est pas prouvée, ce qui est la bonne règle pour un produit et
    la mauvaise ici : un contrôle d'accord entre deux ordres a besoin de
    deux ordres. La preuve de la marche est publiée à côté, elle n'est
    pas escamotée.

    ⚠️ Départage DÉTERMINISTE des ex aequo par le nom du modèle. Deux
    médianes exactement égales sur des flottants ne s'observent pas, mais
    un ordre qui dépendrait de l'ordre de lecture d'un dictionnaire
    rendrait un tau différent d'une exécution à l'autre — et c'est le
    genre d'instabilité qu'on attribuerait à la météo.
    """
    stats, exclus = [], []
    for m in modeles:
        rows = lignes.get(m, ())
        med = S.median([r.get(value_key) for r in rows])
        if len(rows) < min_occurrences or med is None:
            exclus.append({"model": m, "n": len(rows),
                           "raison": "sous_quorum" if med is not None
                                     else "aucune_valeur"})
            continue
        stats.append({"model": m, "n": len(rows), "median": round(med, 4)})
    stats.sort(key=lambda s: (s["median"], s["model"]))
    rangs = {s["model"]: i for i, s in enumerate(stats, 1)}

    marche = None
    if len(stats) >= 2:
        a, b = stats[0]["model"], stats[1]["model"]
        v = INF.compare_pair(a, b, lignes.get(a, ()), lignes.get(b, ()),
                             value_key=value_key)
        marche = {
            "premier": a, "second": b,
            "reason": v.reason,
            "winner": v.winner,
            "n_comparable": v.n_comparable,
            "relative_gap": None if v.relative_gap is None
                            else round(v.relative_gap, 4),
            "ci_low": None if v.ci is None or v.ci.ci_low is None
                      else round(v.ci.ci_low, 4),
            "ci_high": None if v.ci is None or v.ci.ci_high is None
                       else round(v.ci.ci_high, 4),
            "n_days": None if v.ci is None else v.ci.n_days,
            # ⛔ Le signe voyage avec le chiffre, comme au lot L1.
            "sign": "err(premier) - err(second), km/h ; negatif = premier meilleur",
        }
    return {"rangs": rangs, "lignes": stats, "exclus": exclus,
            "marche": marche}


# ══════════════════════════════════════════════════════════════════
#  3. LE TAU — sur le sous-ensemble commun, rerangé
# ══════════════════════════════════════════════════════════════════

def reranger(rangs: Mapping[str, int], modeles: Sequence[str]
             ) -> dict[str, int]:
    """Les rangs d'un sous-ensemble, renumérotés 1..k dans leur ordre.

    ⓘ Le tau-b est invariant par transformation monotone des rangs : ne
    PAS reranger donnerait la même valeur. On rerange quand même, parce
    que le rapport IMPRIME ces rangs et qu'un « 1ᵉʳ, 4ᵉ, 7ᵉ » sur trois
    modèles se lit comme un classement à trous. Le banc tient les deux
    propriétés ensemble : la valeur ne bouge pas, l'affichage change.
    """
    presents = [m for m in modeles if m in rangs]
    presents.sort(key=lambda m: rangs[m])
    return {m: i for i, m in enumerate(presents, 1)}


def tau_population(rangs_pop: Mapping[str, int],
                   rangs_ref: Mapping[str, int]) -> tuple[float | None, int, str]:
    """`(tau_b, k, raison)` entre une population et la référence.

    `k` est le nombre de modèles classés DES DEUX CÔTÉS — pas le nombre
    de modèles partagés en base : un modèle partagé mais recalé sous
    quorum d'un côté ne fait pas de paire.
    """
    communs = sorted(set(rangs_pop) & set(rangs_ref))
    if len(communs) < TAU_MIN_MODELES:
        return None, len(communs), "trop_peu_de_modeles"
    t = INF.kendall_tau_b(reranger(rangs_pop, communs),
                          reranger(rangs_ref, communs))
    return (t, len(communs), "ok" if t is not None else "tau_indefini")


# ══════════════════════════════════════════════════════════════════
#  4. LA RÉSERVE `run_init` — lue dans les archives, pas déduite
# ══════════════════════════════════════════════════════════════════

#: Les trois flux d'archive qui alimentent les populations comparées, et
#: LE PRODUCTEUR de chacun. C'est ce tableau, et pas une phrase de doc,
#: qui dit d'où vient la prévision d'un modèle pour un réseau donné.
#:
#:   · `fcst/`        — `collect.py`, ~03:19 UTC, population `pioupiou`
#:                      (+ `metar` depuis le 23/08), 9 à 11 modèles
#:                      Open-Meteo.
#:   · `fcstreduit/`  — `collect_reduit.py`, 05:00 UTC, les cinq réseaux
#:                      candidats, 5 modèles Open-Meteo, ⭐ SEUL FLUX QUI
#:                      ÉCRIT `run_init`/`run_avail` (lot S0.11).
#:   · `fcstarome/`   — `arome_fcst.py`, tuiles R2 maison, ⭐ UN SEUL
#:                      OBJET POUR TOUS LES RÉSEAUX à la fois
#:                      (`charger_balises` lit les six référentiels et
#:                      dédoublonne sur `source:id`).
FLUX_ARCHIVE = ("fcst", "fcstreduit", "fcstarome")

#: ⭐ LE MODÈLE POUR LEQUEL LA RÉSERVE NE PEUT PAS EXISTER, et c'est
#: démontrable dans le code plutôt que mesurable dans les données :
#: `arome_r2` est servi aux SIX réseaux depuis le MÊME objet
#: `fcstarome_<jour>.ndjson.gz`, produit par un seul appel d'
#: `arome_fcst.py` sur les mêmes tuiles. Il n'y a pas deux runs à
#: comparer — il n'y en a qu'un, écrit une fois. Une réserve d'échéance
#: sur `arome_r2` serait donc une réserve sur une différence qui
#: n'existe pas, et l'écrire quand même rendrait le rapport plus prudent
#: en apparence et moins vrai en fait.
MODELE_ARCHIVE_UNIQUE = "arome_r2"


def _octets(root, key: str, storage=None) -> tuple[bytes | None, str | None]:
    """Les octets bruts d'un objet d'archive — local d'abord, R2 ensuite.

    ⚠️ MÊME RÈGLE QUE `score.read_ndjson`, ET C'EST VOULU : ce module ne
    lit pas les archives autrement que le job qui les écrit. Ce qui est
    différent, c'est ce qu'on en fait — `read_ndjson` construit la LISTE
    de toutes les lignes, et une journée de `fcst/` en porte plus d'un
    million (≈2 900 points × 9 modèles × 72 heures). Le contrôle n'a
    besoin que d'un ensemble de valeurs distinctes : il lit ligne à
    ligne et n'accumule rien. ⓘ Le banc
    `test_octets_lit_comme_read_ndjson` compare les deux chemins sur le
    même objet, pour que cette duplication ne puisse pas diverger.
    """
    import pathlib
    p = pathlib.Path(root) / key
    if p.exists():
        return p.read_bytes(), None
    if storage is None:
        return None, None
    # ⛔ UNE LECTURE QUI ÉCHOUE EST UN FAIT DU CONTRÔLE, PAS UNE PANNE
    # DU CONTRÔLE. Trouvé en jouant le lot sur le VPS le 28/08 : les
    # journées d'avant la naissance de `fcstreduit/` n'existent ni en
    # local ni sur R2, et le seau répondait `HTTP 400` au lieu d'un 404.
    # L'exception remontait jusqu'au `try` de `main`, qui abandonnait la
    # réserve ENTIÈRE — donc les quatre objets parfaitement lisibles des
    # nuits suivantes n'étaient jamais regardés, et le rapport disait
    # « archives non ouvertes » alors qu'elles étaient là.
    #
    # ⚠️ Et le repli n'est PAS « absent » : un objet qu'on n'a pas pu
    # lire n'est pas un objet qui n'existe pas. Le troisième état est
    # nommé, compté, et imprimé.
    try:
        return storage.get(key), None
    except Exception as exc:                              # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"


def _lignes(raw: bytes | None):
    """Itère les lignes d'un ndjson (gzippé ou non), sans tout garder."""
    import gzip
    import json
    if not raw:
        return
    try:
        texte = gzip.decompress(raw).decode("utf-8")
    except OSError:
        texte = raw.decode("utf-8")
    for ligne in texte.splitlines():
        if ligne.strip():
            try:
                yield json.loads(ligne)
            except ValueError:
                continue


def runs_du_flux(root, key: str, storage=None) -> dict:
    """Les `run_init` distincts par modèle dans UN objet d'archive.

    Rend `{"objet": key, "present": bool, "n_lignes": int,
           "par_modele": {modele: {"runs": [...], "sans_run": n}}}`.

    ⚠️ « objet absent » et « objet présent sans `run_init` » sont DEUX
    faits, et les confondre est exactement ce que ce contrôle ne doit pas
    faire : le premier dit « je n'ai pas regardé », le second dit « j'ai
    regardé et la donnée n'y est pas ». Le champ `present` les sépare.
    """
    raw, erreur = _octets(root, key, storage)
    par_modele: dict[str, dict] = {}
    n = 0
    for r in _lignes(raw):
        n += 1
        m = r.get("model")
        if m is None:
            continue
        d = par_modele.setdefault(m, {"runs": set(), "sans_run": 0})
        ri = r.get("run_init")
        if ri:
            d["runs"].add(ri)
        else:
            d["sans_run"] += 1
    return {"objet": key, "present": raw is not None, "n_lignes": n,
            "erreur": erreur,
            "par_modele": {m: {"runs": sorted(d["runs"]),
                               "sans_run": d["sans_run"]}
                           for m, d in sorted(par_modele.items())}}


def verifier_run_init(root, jours: Sequence[str], modeles: Sequence[str],
                      storage=None, lire=runs_du_flux) -> dict:
    """Le PRÉALABLE exigé par la note S3 §6 : les runs sont-ils comparables ?

    Lit `fcst/` (référence), `fcstreduit/` (candidates) et `fcstarome/`
    (les deux) sur les journées de la fenêtre, et rend, par modèle :
    les runs vus de chaque côté, et un verdict.

    Les quatre verdicts possibles par modèle, et il n'y en a pas de
    cinquième :

      · `archive_unique`   — un seul objet sert les deux populations
        (`arome_r2`) : il n'y a pas deux runs, donc pas d'écart possible.
        ⭐ C'est le verdict le plus fort, et il ne se mesure pas : il se
        DÉMONTRE, et le champ `preuve` dit où.
      · `runs_identiques`  — les deux côtés portent `run_init` et les
        mêmes valeurs.
      · `runs_differents`  — les deux côtés portent `run_init` et
        diffèrent : le modèle est avantagé d'une échéance quelque part,
        et le tau doit être lu en le sachant.
      · `non_verifiable`   — au moins un côté n'écrit pas `run_init`.
        ⛔ CE N'EST PAS « pas de problème ». C'est « la question n'a pas
        de réponse dans l'archive », et la différence tient tout le
        contrôle : `collect.py` (le flux `fcst/`, celui de la population
        de RÉFÉRENCE) n'a jamais écrit `run_init` — seul
        `collect_reduit.py` le fait, depuis le lot S0.11. La réserve du
        S3 ne peut donc pas être levée par la lecture des deux archives
        que la note demande de lire : il en manque une moitié.

    Rend aussi `reserve`, la phrase COURTE qui voyagera sur chaque ligne
    du rapport, et `levee` (bool) — vrai seulement si AUCUN modèle
    comparé n'est en `runs_differents` NI en `non_verifiable`.
    """
    par_flux: dict[str, list[dict]] = {f: [] for f in FLUX_ARCHIVE}
    import score as SC  # noqa: PLC0415  (cycle : score importe ce module)
    from datetime import datetime, timezone
    for j in jours:
        d = datetime.strptime(j, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        par_flux["fcst"].append(lire(root, SC.fcst_key(d), storage))
        par_flux["fcstreduit"].append(lire(root, SC.fcst_reduit_key(d), storage))
        par_flux["fcstarome"].append(lire(root, SC.fcst_arome_key(d), storage))

    def _agrege(flux: str, modele: str) -> dict:
        runs, sans, vus = set(), 0, 0
        for objet in par_flux[flux]:
            if not objet["present"]:
                continue
            vus += 1
            info = objet["par_modele"].get(modele)
            if info:
                runs.update(info["runs"])
                sans += info["sans_run"]
        return {"objets_lus": vus, "runs": sorted(runs), "sans_run": sans}

    detail, differents, inconnus = {}, [], []
    for m in sorted(set(modeles)):
        if m == MODELE_ARCHIVE_UNIQUE:
            detail[m] = {
                "verdict": "archive_unique",
                "preuve": ("arome_fcst.charger_balises lit les SIX "
                           "referentiels et ecrit UN objet fcstarome/ par "
                           "jour : la meme prevision sert pioupiou et les "
                           "candidates"),
                "reference": _agrege("fcstarome", m),
                "candidates": _agrege("fcstarome", m),
            }
            continue
        ref = _agrege("fcst", m)
        cand = _agrege("fcstreduit", m)
        if not ref["runs"] or not cand["runs"]:
            v = "non_verifiable"
            inconnus.append(m)
        elif set(ref["runs"]) == set(cand["runs"]):
            v = "runs_identiques"
        else:
            v = "runs_differents"
            differents.append(m)
        detail[m] = {"verdict": v, "reference": ref, "candidates": cand}

    echecs = sorted({o["objet"] for v in par_flux.values() for o in v
                     if o.get("erreur")})
    levee = not differents and not inconnus
    if levee:
        reserve = "run_init verifie : runs comparables sur tous les modeles compares"
    elif differents:
        reserve = ("run_init : ECART DE RUN sur " + ", ".join(differents)
                   + (" ; non verifiable sur " + ", ".join(inconnus)
                      if inconnus else ""))
    else:
        reserve = ("run_init NON VERIFIABLE sur " + ", ".join(inconnus)
                   + " — le flux fcst/ (population de reference) n'ecrit "
                     "pas run_init ; seul fcstreduit/ le fait (lot S0.11)")
    if echecs:
        # ⚠️ Recopié DANS la phrase qui voyage, pas rangé dans un champ à
        # part : une lecture manquée peut être ce qui empêche de voir un
        # écart de run, et le lecteur doit l'avoir sous les yeux avec le
        # tau, pas trois écrans plus loin.
        reserve += f" · {len(echecs)} objet(s) d'archive ILLISIBLE(S)"
    return {"levee": levee, "reserve": reserve, "par_modele": detail,
            "modeles_differents": differents, "modeles_inconnus": inconnus,
            "jours_lus": list(jours),
            "objets": {f: [{"objet": o["objet"], "present": o["present"],
                            "n_lignes": o["n_lignes"],
                            "erreur": o.get("erreur")} for o in v]
                       for f, v in par_flux.items()},
            "lectures_echouees": echecs}


#: Ce que rend `verifier_run_init` quand on refuse d'ouvrir les archives
#: (`--sans-archive`, ou une machine sans accès R2 : les identifiants du
#: bucket vivent sur le VPS, `~/.balise-watch-*.env`). ⛔ Ce n'est PAS un
#: défaut silencieux : la réserve le dit, et `levee` reste faux.
RESERVE_NON_LUE = {
    "levee": False,
    "reserve": ("run_init NON LU : archives non ouvertes (--sans-archive "
                "ou acces R2 absent) — le tau ci-dessous n'est pas qualifie"),
    "par_modele": {}, "modeles_differents": [], "modeles_inconnus": [],
    "jours_lus": [], "objets": {}, "lectures_echouees": [],
}


# ══════════════════════════════════════════════════════════════════
#  5. LE CONTRÔLE — assemblage
# ══════════════════════════════════════════════════════════════════

def _bloc_classement(lignes_pop, lignes_ref, modeles, noyau_pop, noyau_ref,
                     value_key, min_occurrences) -> dict:
    """Un couple (classement population, classement référence) + son tau."""
    pop = {m: _restreindre(lignes_pop.get(m, ()), noyau_pop) for m in modeles} \
        if noyau_pop is not None else {m: list(lignes_pop.get(m, ())) for m in modeles}
    ref = {m: _restreindre(lignes_ref.get(m, ()), noyau_ref) for m in modeles} \
        if noyau_ref is not None else {m: list(lignes_ref.get(m, ())) for m in modeles}
    c_pop = classement(pop, modeles, value_key, min_occurrences)
    c_ref = classement(ref, modeles, value_key, min_occurrences)
    tau, k, raison = tau_population(c_pop["rangs"], c_ref["rangs"])
    return {
        "tau_b": None if tau is None else round(tau, 4),
        "k": k, "raison": raison,
        # ⚠️ NOMMÉS `n_lignes_*` ET PAS `n_*` : c'est la SOMME sur les k
        # modèles, donc des balise-jour-MODÈLE, pas des balise-jours. Le
        # nombre de balise-jours du noyau, lui, est `n_noyau_*` sur la
        # ligne de population. Deux grandeurs voisines sous un nom
        # commun, c'est ainsi qu'on divise par le mauvais dénominateur.
        "n_lignes_population": sum(len(v) for v in pop.values()),
        "n_lignes_reference": sum(len(v) for v in ref.values()),
        "population": c_pop, "reference": c_ref,
    }


def controle_tau(daily: Iterable[Mapping],
                 doublons: frozenset[str] = frozenset(),
                 reference: str = TAU_REFERENCE,
                 lead_h: int | None = TAU_LEAD_H,
                 value_key: str = TAU_VALUE_KEY,
                 min_occurrences: int = TAU_MIN_OCCURRENCES,
                 run_init: Mapping | None = None) -> dict:
    """Le contrôle n°3 complet, prêt à imprimer ou à sérialiser.

    ⚠️ `run_init` N'EST PAS OPTIONNEL AU SENS OÙ ON POURRAIT L'OUBLIER :
    `None` est remplacé par `RESERVE_NON_LUE`, qui dit en toutes lettres
    que la réserve n'a pas été vérifiée et laisse `levee` à faux. Il n'y
    a aucun chemin qui produise un tau sans une phrase de réserve
    attachée — c'est la seule garantie qui empêche le chiffre de voyager
    seul (§ dernier de l'en-tête).
    """
    daily = list(daily)
    reserve = dict(run_init) if run_init else dict(RESERVE_NON_LUE)
    lignes_ref, bilan_ref = lignes_par_modele(
        daily, reference, lead_h, value_key, doublons)
    sources = sorted({r.get("source") for r in daily
                      if r.get("source") and r.get("source") != reference})
    jours = sorted({r["day"] for r in daily
                    if lead_h is None or r.get("lead_h") == lead_h})

    lignes_out = []
    for src in sources:
        lignes_pop, bilan = lignes_par_modele(
            daily, src, lead_h, value_key, doublons)
        partages = sorted(set(lignes_pop) & set(lignes_ref))
        base = {
            "source": src, "reference": reference,
            "modeles_partages": partages,
            "k_base": len(partages),
            "n_balises": bilan["n_balises"],
            "doublons_reseau_retires": bilan["doublons_reseau"],
            "doublons_chaine_ecartes": bilan["doublons_ecartes"],
            "jours_population": sorted({r["day"] for m in lignes_pop
                                        for r in lignes_pop[m]}),
            # ⛔ La réserve est recopiée sur CHAQUE ligne, pas posée une
            # fois en tête du rapport. Une ligne de tableau se cite seule,
            # se colle dans un message, se lit sans son en-tête.
            "reserve_run_init": reserve["reserve"],
            "reserve_levee": reserve["levee"],
        }
        if len(partages) < TAU_MIN_MODELES:
            base.update({"raison": "trop_peu_de_modeles_partages",
                         "noyau": None, "brut": None})
            lignes_out.append(base)
            continue
        noyau_pop = noyau_commun(lignes_pop, partages)
        noyau_ref = noyau_commun(lignes_ref, partages)

        # ⭐⭐ ET LES DEUX CÔTÉS SONT RAMENÉS AUX MÊMES JOURNÉES.
        #
        # Trouvé en mesurant, pas en relisant : au 27/08/2026, le noyau
        # d'`aemet` tient sur 2 journées (25→26/08, `icon_eu` n'entre que
        # le 25) tandis que celui de Pioupiou sur les mêmes 4 modèles en
        # porte 5 (22→26/08, borné par `arome_r2`). Sans cet alignement,
        # on comparerait le classement d'un réseau sur DEUX jours à celui
        # d'un autre sur CINQ — et un désaccord pourrait n'être qu'un
        # changement de temps entre les deux périodes.
        #
        # ⛔ C'est la MÊME faute que le lot L3 a corrigée à l'intérieur
        # d'une case (§2.5.a : deux médianes calculées chacune sur sa
        # population), remontée d'un cran : ici les deux populations ne
        # partagent aucune BALISE — elles sont disjointes par
        # construction, c'est tout l'objet du contrôle — mais elles
        # peuvent et doivent partager leurs JOURNÉES. On apparie ce qui
        # est appariable, et on le dit.
        #
        # ⚠️ Le prix est publié, pas caché : `jours_ecartes_*` nomme les
        # journées perdues de chaque côté. Le jour où ce prix vide le
        # noyau, la réponse n'est pas de retirer l'alignement — c'est de
        # dire que la fenêtre ne permet pas encore le contrôle.
        jours_pop = {d for d, _ in noyau_pop}
        jours_ref = {d for d, _ in noyau_ref}
        jours_com = jours_pop & jours_ref
        base["jours_ecartes_population"] = sorted(jours_pop - jours_com)
        base["jours_ecartes_reference"] = sorted(jours_ref - jours_com)
        noyau_pop = {c for c in noyau_pop if c[0] in jours_com}
        noyau_ref = {c for c in noyau_ref if c[0] in jours_com}

        base["n_noyau_population"] = len(noyau_pop)
        base["n_noyau_reference"] = len(noyau_ref)
        base["jours_noyau_population"] = sorted(jours_com)
        base["noyau"] = _bloc_classement(lignes_pop, lignes_ref, partages,
                                         noyau_pop, noyau_ref,
                                         value_key, min_occurrences)
        # Le même calcul SANS appariement — publié pour que l'écart entre
        # les deux soit lisible, jamais pour être cité seul (§2 en-tête).
        base["brut"] = _bloc_classement(lignes_pop, lignes_ref, partages,
                                        None, None,
                                        value_key, min_occurrences)
        base["raison"] = base["noyau"]["raison"]
        lignes_out.append(base)

    return {
        "reference": reference,
        "lead_h": lead_h,
        "value_key": value_key,
        "min_occurrences": min_occurrences,
        "jours": jours,
        "premier_jour": jours[0] if jours else None,
        "dernier_jour": jours[-1] if jours else None,
        "n_jours": len(jours),
        "reference_n_balises": bilan_ref["n_balises"],
        "reference_doublons_retires": bilan_ref["doublons_reseau"],
        "run_init": reserve,
        "populations": lignes_out,
    }


# ══════════════════════════════════════════════════════════════════
#  6. LE RAPPORT — ce qu'un humain lit
# ══════════════════════════════════════════════════════════════════

def _dire_marche(m: Mapping | None) -> str:
    """La preuve de la marche du haut, en une ligne, sous le classement.

    ⚠️ Elle s'imprime SOUS chaque classement et pas en annexe : l'ordre
    imprimé au-dessus est un ordre de médianes (§4 de l'en-tête), et
    cette ligne est la seule qui dise ce qu'il vaut. Séparées, la
    première se lit comme un podium.
    """
    if not m:
        return "        marche du haut : moins de deux modeles classes"
    ic = ("" if m["ci_low"] is None
          else f", IC95j [{m['ci_low']:+.4f} ; {m['ci_high']:+.4f}]")
    gap = ("" if m["relative_gap"] is None
           else f", ecart relatif {100 * m['relative_gap']:.1f} %")
    jours = "" if m["n_days"] is None else f", {m['n_days']} j"
    return (f"        marche du haut : {m['premier']} vs {m['second']} → "
            f"{m['reason']} (n apparie {m['n_comparable']}{jours}{ic}{gap})")


def _runs_lisibles(runs: Sequence) -> str:
    """Les `run_init` en clair, À CÔTÉ de leur valeur brute.

    ⚠️ Open-Meteo rend `last_run_initialisation_time` en SECONDES depuis
    l'époque, et `collect_reduit` l'archive tel quel — c'est la bonne
    décision (une archive ne doit pas transformer ce qu'elle garde).
    Mais « 1787529600 » ne se relit pas : un lecteur ne peut pas voir
    d'un coup d'œil que deux modèles sont à trois heures l'un de
    l'autre. La conversion vit DONC ici, dans l'affichage, et jamais
    dans la donnée.

    ⓘ Une valeur qui n'est pas un entier de secondes est rendue telle
    quelle plutôt que devinée : le jour où le fournisseur passe à une
    chaîne ISO, le rapport restera lisible et le dira.
    """
    from datetime import datetime, timezone
    if not runs:
        return "(aucun run_init ecrit)"
    out = []
    for r in runs:
        try:
            iso = datetime.fromtimestamp(int(r), timezone.utc).strftime(
                "%Y-%m-%dT%H:%MZ")
            out.append(f"{iso}")
        except (TypeError, ValueError, OSError, OverflowError):
            out.append(str(r))
    return ", ".join(out)


def rapport(res: Mapping, quand: str | None = None) -> str:
    """Le rapport horodaté, en texte. Aucune couleur, aucune surprise."""
    from datetime import datetime, timezone
    L: list[str] = []
    quand = quand or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    L.append("=" * 72)
    L.append(f"CONTROLE n°3 — TAU INTER-POPULATIONS (lot S3 / lot L8)")
    L.append(f"genere le {quand}")
    L.append("=" * 72)
    L.append("")
    L.append(f"reference        : {res['reference']} "
             f"({res['reference_n_balises']} balises)")
    L.append(f"echeance         : lead {res['lead_h']} h")
    L.append(f"grandeur classee : mediane de {res['value_key']} par balise-jour")
    L.append(f"quorum modele    : {res['min_occurrences']} balise-jours")
    L.append(f"fenetre TROUVEE  : {res['premier_jour']} → {res['dernier_jour']} "
             f"({res['n_jours']} jours)")
    if res["reference_doublons_retires"]:
        L.append(f"doublons reseau  : {res['reference_doublons_retires']} "
                 f"balise-jours retires de la reference (station_zone.doublon_de)")
    L.append("")
    L.append("-" * 72)
    L.append("PREALABLE — la reserve run_init de la note S3 §6")
    L.append("-" * 72)
    ri = res["run_init"]
    L.append(f"  levee : {'OUI' if ri['levee'] else 'NON'}")
    L.append(f"  {ri['reserve']}")
    for o in ri.get("lectures_echouees", ()):
        L.append(f"    ⚠️ ILLISIBLE : {o}")
    for m, d in sorted(ri.get("par_modele", {}).items()):
        L.append(f"    {m:32s} {d['verdict']}")
        if d["verdict"] == "archive_unique":
            L.append(f"        preuve : {d['preuve']}")
        else:
            r, c = d["reference"], d["candidates"]
            L.append(f"        reference  : {r['objets_lus']} objets lus, "
                     f"runs {_runs_lisibles(r['runs'])}, "
                     f"{r['sans_run']} lignes sans run_init")
            L.append(f"        candidates : {c['objets_lus']} objets lus, "
                     f"runs {_runs_lisibles(c['runs'])}, "
                     f"{c['sans_run']} lignes sans run_init")
    L.append("")
    for p in res["populations"]:
        L.append("-" * 72)
        L.append(f"POPULATION {p['source']}  —  {p['n_balises']} balises, "
                 f"{p['k_base']} modeles partages avec {p['reference']}")
        L.append("-" * 72)
        L.append(f"  jours de la population : "
                 f"{', '.join(p['jours_population']) or '(aucun)'}")
        if p["doublons_reseau_retires"]:
            L.append(f"  doublons reseau retires : "
                     f"{p['doublons_reseau_retires']} balise-jours")
        if p["doublons_chaine_ecartes"]:
            L.append(f"  ⚠️ doublons de chaine ecartes : "
                     f"{p['doublons_chaine_ecartes']} balise-jours (deux fcst_src)")
        if p.get("raison") == "trop_peu_de_modeles_partages":
            L.append(f"  ⛔ PAS DE TAU : {p['k_base']} modele(s) partage(s) — "
                     f"un tau-b compte des paires, il en faut au moins deux.")
            L.append(f"     modeles : {', '.join(p['modeles_partages'])}")
            L.append("")
            continue
        L.append(f"  modeles partages : {', '.join(p['modeles_partages'])}")
        L.append(f"  noyau commun     : {p['n_noyau_population']} balise-jours "
                 f"cote {p['source']} · {p['n_noyau_reference']} cote "
                 f"{p['reference']} · jours "
                 f"{', '.join(p['jours_noyau_population']) or '(aucun)'}")
        if p["jours_ecartes_population"] or p["jours_ecartes_reference"]:
            L.append(f"  jours ecartes    : "
                     f"{', '.join(p['jours_ecartes_population']) or '—'} cote "
                     f"{p['source']} · "
                     f"{', '.join(p['jours_ecartes_reference']) or '—'} cote "
                     f"{p['reference']}  (alignement des calendriers)")
        for nom, bloc in (("SUR LE NOYAU COMMUN", p["noyau"]),
                          ("classement BRUT (non apparie)", p["brut"])):
            L.append("")
            L.append(f"    {nom}")
            t = bloc["tau_b"]
            L.append(f"      tau-b vs {p['reference']} : "
                     f"{'—' if t is None else f'{t:+.3f}'} "
                     f"(k = {bloc['k']}, {bloc['raison']})")
            for cote, nom_cote in (("population", p["source"]),
                                   ("reference", p["reference"])):
                c = bloc[cote]
                L.append(f"      classement {nom_cote} :")
                for i, s in enumerate(c["lignes"], 1):
                    L.append(f"        {i}. {s['model']:32s} "
                             f"{s['median']:7.3f} km/h  (n={s['n']})")
                for e in c["exclus"]:
                    L.append(f"        —  {e['model']:32s} "
                             f"exclu ({e['raison']}, n={e['n']})")
                L.append(_dire_marche(c["marche"]))
        L.append("")
        L.append(f"  ⚠️ reserve : {p['reserve_run_init']}")
        L.append("")
    L.append("=" * 72)
    return "\n".join(L)


# ══════════════════════════════════════════════════════════════════
#  7. LA REQUÊTE — étroite, et filtrée serveur
# ══════════════════════════════════════════════════════════════════

def query_tau(since: str, lead_h: int | None = TAU_LEAD_H,
              colonnes: Sequence[str] = TAU_COLONNES) -> str:
    """La requête PostgREST du contrôle.

    ⛔ AUCUN FILTRE `model=in.(…)` ICI, contrairement au duel. Le duel
    suit trois paires NOMMÉES ; ce contrôle doit DÉCOUVRIR quels modèles
    chaque population partage avec la référence — écrire la liste en dur
    reviendrait à mesurer l'accord sur le tableau qu'on a imaginé, et le
    jour où un réseau perd un modèle, le contrôle continuerait de dire
    que tout va bien sur un `k` qu'il aurait lui-même fixé.

    ⓘ Le filtre `lead_h` reste, lui : l'échéance est une décision de
    méthode (une seule, §TAU_LEAD_H), pas une découverte.
    """
    q = f"?day=gte.{since}&select={','.join(colonnes)}"
    if lead_h is not None:
        q += f"&lead_h=eq.{lead_h}"
    return q


def doublons_connus(zones_raw: Iterable[Mapping]) -> frozenset[str]:
    """Les unités marquées `doublon_de` dans `station_zone` (lot L17).

    ⚠️ Passe par `score.est_doublon` — UN SEUL TEST POUR TOUS LES
    APPELANTS, c'est l'arbitrage écrit du L17. Un `z.get("doublon_de")`
    de plus ici serait le quatrième endroit où la colonne peut être
    renommée à moitié.
    """
    import score as SC  # noqa: PLC0415
    return frozenset(f"{z['source']}:{z['station_id']}" for z in zones_raw
                     if SC.est_doublon(z))


# ══════════════════════════════════════════════════════════════════
#  8. LANCEMENT — à la main, ou par le timer hebdo (NON INSTALLÉ)
# ══════════════════════════════════════════════════════════════════

def main() -> int:
    import argparse
    import json
    import pathlib
    from datetime import datetime, timedelta, timezone

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jours", type=int, default=TAU_DAYS)
    ap.add_argument("--day", default=None,
                    help="dernier jour de la fenetre (defaut : hier)")
    ap.add_argument("--root", default="/var/lib/bw-model-verif",
                    help="racine locale des archives (lecture de run_init)")
    ap.add_argument("--sans-archive", action="store_true",
                    help="ne pas ouvrir les archives : le tau sort NON "
                         "QUALIFIE et le rapport le dit sur chaque ligne")
    ap.add_argument("--sans-dedup", action="store_true",
                    help="ne pas lire station_zone.doublon_de. ⚠️ Le tau "
                         "pioupiou↔windsmobi devient alors partiellement "
                         "l'accord de capteurs avec eux-memes (lot L16)")
    ap.add_argument("--out", default=None,
                    help="ecrit le rapport horodate dans ce fichier "
                         "(defaut : stdout seul)")
    ap.add_argument("--json", action="store_true",
                    help="ajoute le resultat complet en JSON sur stdout")
    args = ap.parse_args()

    import score as SC  # noqa: PLC0415  (cycle potentiel : import tardif)

    day = (datetime.strptime(args.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
           if args.day
           else datetime.now(timezone.utc) - timedelta(days=1))
    since = (day - timedelta(days=args.jours - 1)).strftime("%Y-%m-%d")
    sb = SC.Supabase()

    daily = sb.select("model_verif_daily", query_tau(since),
                      order="day,source,station_id,model,lead_h,fcst_src")
    print(f"▶ controle tau : {len(daily)} lignes lues depuis le {since} "
          f"(lead {TAU_LEAD_H}, {TAU_VALUE_KEY})", flush=True)

    if args.sans_dedup:
        doublons = frozenset()
        print("  ⚠️ deduplication SAUTEE (--sans-dedup)")
    else:
        zones = sb.select("station_zone", order="source,station_id")
        doublons = doublons_connus(zones)
        print(f"  station_zone : {len(zones)} lignes, {len(doublons)} "
              f"doublon(s) d'inscription connu(s)")

    jours = sorted({r["day"] for r in daily})
    if args.sans_archive:
        ri = None
        print("  ⚠️ archives NON ouvertes (--sans-archive)")
    else:
        # ⚠️ Les modèles dont la réserve doit être instruite sont ceux
        # qui seront COMPARÉS, c'est-à-dire ceux qu'au moins une
        # population partage avec la référence — pas la liste des
        # modèles du groupe réduit, qui est une constante d'un autre
        # fichier et qui aurait raison jusqu'au jour où elle aurait tort.
        par_source: dict[str, set] = defaultdict(set)
        for r in daily:
            if r.get("lead_h") == TAU_LEAD_H:
                par_source[r["source"]].add(r["model"])
        ref_models = par_source.get(TAU_REFERENCE, set())
        compares = sorted({m for s, ms in par_source.items()
                           if s != TAU_REFERENCE for m in (ms & ref_models)})
        print(f"  archives : {len(jours)} jour(s) × 3 flux, "
              f"{len(compares)} modele(s) compare(s)")
        try:
            ri = verifier_run_init(pathlib.Path(args.root), jours, compares,
                                   storage=SC._storage())
        except Exception as exc:                      # noqa: BLE001
            # ⛔ On NE retombe PAS sur « pas de réserve ». Une archive
            # illisible est un fait du contrôle, pas un incident à
            # avaler : le tau sortira NON QUALIFIÉ et le dira.
            print(f"  ⚠️ archives illisibles : {type(exc).__name__} — {exc}",
                  file=sys.stderr)
            ri = None

    res = controle_tau(daily, doublons, run_init=ri)
    quand = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    texte = rapport(res, quand)
    print(texte)
    if args.json:
        print(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    if args.out:
        p = pathlib.Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(texte + "\n", encoding="utf-8")
        print(f"▶ rapport ecrit : {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
