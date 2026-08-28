#!/usr/bin/env python3
"""fraicheur.py — QUEL RUN Open-Meteo sert cette nuit, par modèle.

    Session 28/08/2026 (suite du lot L8).
    cf. `amelioration scoring/agrume/LOTS_SCORING_AGRUME_27-08.md` §L8,
    `amelioration scoring/lot-s3-controles-veracite-23-08.md` §6 et §9.

═══ POURQUOI CE FICHIER EXISTE, ET POURQUOI IL EST NEUF ═══

La sonde vivait dans `collect_reduit.py` depuis le lot S0.11 : elle
interroge le `meta.json` d'Open-Meteo et écrit `run_init` / `run_avail`
dans CHAQUE LIGNE de l'archive `fcstreduit/`. Elle n'a jamais existé du
côté de `collect.py` — donc du côté de la population de RÉFÉRENCE.

⛔ CE QUE ÇA COÛTAIT, MESURÉ LE 28/08 SUR LES ARCHIVES RÉELLES.
`controle_tau.verifier_run_init` a lu 14 objets `fcst/` : **zéro
`run_init`, 7 271 à 9 138 lignes muettes par modèle**. Le préalable que
la note S3 exige en toutes lettres — *« le tau doit être lu en regardant
`run_init` des archives `fcst/` ET `fcstreduit/` »* — était donc à
moitié IMPOSSIBLE : il manquait le côté contre lequel on compare. Le
contrôle n°3 rendait `non_verifiable` sur cinq modèles sur six, et
c'était sa réponse honnête, pas un défaut réparable dans le contrôle.
Ce fichier est le geste qui le rend réparable.

⛔ ET POURQUOI PAS UNE RECOPIE DANS `collect.py`. Deux relevés du même
`meta.json`, écrits deux fois, sont la première chose qui divergera —
c'est le piège nº 1 de BUGS.md du 26/08 (« quand un produit a deux
consommateurs, vérifier qu'ils lisent la MÊME fonction, pas deux chemins
qui se ressemblent »), et il a déjà coûté une journée sur le composite
AGRUME. La sonde déménage donc ICI, et les deux collecteurs l'appellent.

⛔ ET POURQUOI PAS DANS `collect.py`, PUISQUE `collect_reduit` L'IMPORTE
DÉJÀ. Parce que `collect.py` « porte la seule chaîne irremplaçable du
chantier » (son propre en-tête, et l'en-tête de `collect_reduit`), qu'il
a été déployé, retiré et redéployé trois fois en un matin le 22/08, et
qu'on ne le fait pas grossir de 90 lignes quand un module de 90 lignes
fait l'affaire. Ici la sonde a ses bancs à elle, et elle se relit sans
ouvrir un fichier de 4 000 lignes.

═══ LE CYCLE, ET COMMENT IL EST ÉVITÉ ═══

`_get_json_retry` vit dans `collect.py`, qui va importer ce module :
l'importer en retour ferait un cycle. Il est donc INJECTÉ
(`get_json=`) — l'appelant passe la fonction qu'il utilise déjà pour
tout le reste de sa nuit. ⚠️ Ce n'est pas une élégance : c'est ce qui
garantit qu'un 429 sur le `meta.json` est traité par le MÊME code que
celui qui traite un 429 sur une prévision, avec la même pause franche
(cf. le pavé de `_get_json_retry`, et les 24 balises que le 07/08 a
coûtées).
"""
from __future__ import annotations

from typing import Callable, Iterable, Mapping, Sequence

#: Le point d'entrée de métadonnées d'Open-Meteo, mesuré au S0.10 :
#: HTTP 200 sur les dix domaines interrogés, et il rend
#: `last_run_initialisation_time` / `last_run_availability_time`.
#: ⛔ CE N'EST PAS LE MIROIR AWS. Le même fichier existe sur
#: `openmeteo.s3.amazonaws.com` SANS QUOTA — et il est PÉRIMÉ : mesuré
#: le 23/08, `dwd_icon_d2` y portait encore le run du 15/08, huit jours
#: de retard. Le miroir ne reflète pas ce que l'API sert, et pas de la
#: même façon selon le modèle. La route gratuite n'existe pas.
META_API = "https://api.open-meteo.com/data/{domaine}/static/meta.json"

#: ⛔ POIDS RÉSERVÉ PAR APPEL DE SONDE — LE MINIMUM FACTURABLE.
#: `quota_openmeteo.poids_url()` calcule le poids depuis les paramètres
#: de l'URL ; celle-ci n'en a AUCUN, donc elle rend son plancher — qui
#: vaut **1,0 depuis le débug du 24/08**, et non plus 0,1. Ce que cet
#: endpoint facture réellement N'EST PAS ÉTABLI, mais un appel HTTP ne
#: coûte jamais moins d'un appel.
#: ⓘ Cette constante et `poids_url` disent la même chose. On la garde :
#: elle DÉCLARE le choix, là où l'égalité n'est qu'une coïncidence
#: d'aujourd'hui.
POIDS_SONDE = 1.0

#: ⭐ LA CARTE CANONIQUE modèle → domaine Open-Meteo, ET IL N'Y EN A
#: QU'UNE. Elle couvre les NEUF modèles Open-Meteo du chantier : les
#: cinq du groupe réduit (`collect_reduit.MODELS_REDUIT`) et les quatre
#: que seule la passe Pioupiou collecte.
#:
#: ⚠️ CE SONT DES NOMS DE DOMAINE, PAS DES NOMS DE MODÈLE. `gfs_global`
#: est servi par `ncep_gfs013` (mesuré au S0.10 — `ncep_gfs025`, lui,
#: publie 43 min plus tard). Une correspondance fausse ici écrirait dans
#: l'archive le run d'un AUTRE modèle, ce qui est pire que pas de
#: colonne du tout : un chiffre faux se cite, une colonne absente non.
#: Les quatre derniers portent le même nom des deux côtés — c'est un
#: fait d'Open-Meteo, pas une règle, et c'est pour ça qu'ils sont écrits
#: en toutes lettres plutôt que déduits.
#:
#: ⛔ ELLE DOIT COUVRIR `collect.MODELS` EXACTEMENT. Un modèle collecté
#: et absent d'ici partirait sans `run_init` sans que rien ne rougisse ;
#: un modèle ici et non collecté ferait payer un appel pour rien. Le
#: banc `test_fraicheur.py` tient l'égalité des deux ensembles, et
#: `sonde_fraicheur` refuse un modèle inconnu au lieu de le sauter.
DOMAINE_PAR_MODELE: dict[str, str] = {
    # les cinq du groupe réduit
    "icon_d2": "dwd_icon_d2",
    "icon_eu": "dwd_icon_eu",
    "meteoswiss_icon_ch2": "meteoswiss_icon_ch2",
    "ecmwf_ifs025": "ecmwf_ifs025",
    "gfs_global": "ncep_gfs013",
    # les quatre que seule la passe Pioupiou collecte
    "meteofrance_arome_france_hd": "meteofrance_arome_france_hd",
    "meteofrance_arpege_europe": "meteofrance_arpege_europe",
    "dmi_harmonie_arome_europe": "dmi_harmonie_arome_europe",
    "chmi_aladin_central_europe_2km": "chmi_aladin_central_europe_2km",
}


class ModeleInconnu(KeyError):
    """Un modèle sans domaine connu. ⛔ On ne le SAUTE pas.

    Sauter rendrait des lignes sans `run_init` pour ce modèle-là
    seulement, silencieusement — et la nuit suivante, le contrôle n°3
    dirait `non_verifiable` sans que personne ne sache pourquoi. Un
    modèle ajouté à `collect.MODELS` doit être ajouté ICI, et l'échec
    est le seul moyen que ça se sache le jour même.
    """


def domaine_de(modele: str) -> str:
    if modele not in DOMAINE_PAR_MODELE:
        raise ModeleInconnu(
            f"{modele} n'a pas de domaine Open-Meteo dans "
            f"fraicheur.DOMAINE_PAR_MODELE — l'ajouter là, une seule fois, "
            f"plutôt que de le laisser partir sans run_init")
    return DOMAINE_PAR_MODELE[modele]


def sonde_fraicheur(budget, modeles: Sequence[str],
                    get_json: Callable,
                    temoins: Iterable[str] = (),
                    crier=print) -> tuple[dict, dict]:
    """Quel run sert CE SOIR, par modèle. Rend `(par_modele, journal)`.

    ⭐ C'EST LA COLONNE QUI TRANSFORME UNE HYPOTHÈSE EN DONNÉE. Le S0.10
    avait mesuré, sur UNE nuit, qu'`icon_d2` sert un run 03 Z aux
    candidates (05:00) et un run 00 Z à Pioupiou (03:19) : trois heures
    d'écart, sur un modèle sur six. Tant que ce n'est pas ÉCRIT DANS
    L'ARCHIVE **DES DEUX CÔTÉS**, le tau du §S3 ne peut pas le
    neutraliser — il ne peut même pas le CONSTATER (mesuré le 28/08 :
    `non_verifiable` sur cinq modèles sur six).

    ⛔ **CHAQUE APPEL PASSE PAR `Budget.demander()`, ET RÉSERVE LE PIRE
    CAS** (`POIDS_SONDE`). Le quota Open-Meteo se compte par adresse IP,
    et c'est celle du VPS qui collecte.

    ⚠️ **UN ÉCHEC NE TUE PAS LA PASSE.** On écrit ce qu'on a, on dit ce
    qui manque, et la collecte part quand même : une colonne
    d'information ne doit jamais coûter une nuit d'archive — celle-là
    ne se rattrape pas, Open-Meteo ne gardant aucun historique de runs.

    ⚠️ Les `temoins` sont sondés pour le JOURNAL, pas pour les lignes :
    ce sont des domaines que l'appelant ne collecte pas. Ils entrent dans
    `jrn["temoins"]` et JAMAIS dans `par_modele`, pour qu'aucun appelant
    ne puisse coller par mégarde le run d'un modèle qu'il ne sert pas.
    """
    par_modele: dict[str, dict] = {}
    jrn: dict = {"appels": 0, "ok": 0, "echecs": [], "refuses": [],
                 "temoins": {}, "poids_reserve": 0.0}

    cibles: list[tuple[str | None, str]] = [
        (m, domaine_de(m)) for m in modeles]
    cibles += [(None, d) for d in temoins]

    for modele, domaine in cibles:
        if budget is not None:
            try:
                budget.demander(POIDS_SONDE,
                                etiquette=f"sonde meta.json {domaine}")
                jrn["poids_reserve"] += POIDS_SONDE
            except Exception as exc:                         # noqa: BLE001
                # ⚠️ `BudgetRefuse` est un refus ARGUMENTÉ, pas une
                # panne — et il ne doit pas emporter la collecte.
                jrn["refuses"].append(f"{domaine} ({exc})")
                continue
        jrn["appels"] += 1
        d = get_json(META_API.format(domaine=domaine),
                     f"meta.json {domaine}")
        if not isinstance(d, dict) or not d.get("last_run_initialisation_time"):
            jrn["echecs"].append(domaine)
            continue
        jrn["ok"] += 1
        info = {
            "domaine": domaine,
            "init": d.get("last_run_initialisation_time"),
            "avail": d.get("last_run_availability_time"),
        }
        if modele:
            par_modele[modele] = info
        else:
            jrn["temoins"][domaine] = info

    if jrn["echecs"] or jrn["refuses"]:
        crier(f"  ⚠️ sonde de fraîcheur INCOMPLÈTE : {jrn['ok']}/"
              f"{len(cibles)} domaines rendus"
              + (f" · échecs : {', '.join(jrn['echecs'])}"
                 if jrn["echecs"] else "")
              + (f" · refusés par le budget : {', '.join(jrn['refuses'])}"
                 if jrn["refuses"] else "")
              + " — la collecte part quand même, les lignes des modèles "
                "manquants n'auront pas `run_init`.")
    return par_modele, jrn


def poser(row: dict, fraicheur: Mapping[str, Mapping]) -> dict:
    """Colle `run_init`/`run_avail` sur une ligne d'archive, ou rien.

    ⚠️ UN CHAMP ABSENT SIGNIFIE « la sonde n'a pas eu ce domaine cette
    nuit-là », ce qui est une INFORMATION ; un `null` ne dirait rien et
    se confondrait avec une valeur. C'est la même règle que
    `collect_reduit` appliquait déjà, écrite une seule fois pour les
    deux flux — et c'est elle qui donne son sens au verdict
    `non_verifiable` du contrôle n°3.
    """
    info = fraicheur.get(row.get("model"))
    if info:
        row["run_init"] = info["init"]
        row["run_avail"] = info["avail"]
    return row


def dire_sonde(jrn_sonde: dict, fraicheur: dict, modeles: Sequence[str],
               crier=print) -> None:
    """Le pavé de journal. ⚠️ Il NOMME les modèles non rendus.

    Un modèle absent du relevé partira sans `run_init` : c'est la seule
    ligne qui le dira le soir même, avant que le contrôle n°3 ne le
    découvre une semaine plus tard.
    """
    crier("┌─ SONDE DE FRAÎCHEUR DE RUN ──────────────────────────────────")
    crier(f"│ appels : {jrn_sonde['appels']} · rendus {jrn_sonde['ok']} · "
          f"{jrn_sonde['poids_reserve']:.0f} pondérés RÉSERVÉS "
          f"(pire cas {POIDS_SONDE:.0f}/appel — le poids réel de cet "
          f"endpoint n'est pas établi)")
    for m in modeles:
        info = fraicheur.get(m)
        if info:
            crier(f"│   {m:28s} run {info['init']} · publié {info['avail']}")
        else:
            crier(f"│   {m:28s} ⚠️ non rendu — lignes sans `run_init`")
    for d, info in sorted(jrn_sonde["temoins"].items()):
        crier(f"│   (témoin) {d:20s} run {info['init']} · publié "
              f"{info['avail']}")
    crier("└──────────────────────────────────────────────────────────────")
