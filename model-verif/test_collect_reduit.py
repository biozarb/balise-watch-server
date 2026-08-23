#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/test_collect_reduit.py — le banc du groupe réduit
#                                          (Lot S0.11, 23/08/2026)
#
#  Sans réseau, sans clé, sans base, sans un seul appel Open-Meteo. Il
#  ne vérifie pas que le collecteur « marche » : il vérifie les onze
#  façons qu'il aurait de casser EN SILENCE.
#
#      python3 test_collect_reduit.py
#
#  ═══ LES ONZE MUTATIONS, ET L'ASSERTION QUI DOIT ROUGIR ═══
#  (chacune rejouée contre un code muté — détail dans la note de
#   session ; l'outil est `/tmp/s11_mutations.py`, JETABLE : il se
#   réécrit, il ne se cite pas, et il VÉRIFIE que sa mutation s'applique
#   avant de conclure quoi que ce soit — un `str.replace` qui ne trouve
#   pas sa cible rend la chaîne inchangée, le banc reste vert, et on
#   croit avoir mesuré « le banc ne sait pas échouer » alors qu'on a
#   mesuré « je n'ai pas muté le code ». C'est arrivé au premier essai
#   du S0.6.)
#
#   1 filtre `pioupiou` retiré      → ⭐ l'assertion de RÉGIME (pas celle
#                                      qui compte les sources)
#   2 garde-fou du suffixe retiré   → ⭐ l'assertion « l'abandon est
#                                      ANNONCÉ » — PAS celle qui compte
#                                      les lignes : sans le garde-fou,
#                                      le point rend zéro ligne AUSSI,
#                                      mais en silence
#   3 cap lu sur `9 500 × 0,6`      → le cap ≤ 2 905 avec 3 810,6 au seau
#   4 cap sans exclure son étiquette→ ⭐ le cap INCHANGÉ quand sa propre
#                                      consommation de la veille est là
#   5 le flux écrit dans `fcst_*`   → les clés, caractère pour caractère
#   6 le manifeste déclare 2 parties→ `parties == len(cles_ecrites)`
#   7 l'éviction ne compte ni ne nomme → le journal (patron `--limit`)
#   8 modèles suffixés `_reduit`    → `k ≥ 6` modèles partagés
#   9 `snapshot_rows` ne lit pas    → (dans `test_score.py`)
#  10 un trou écrit `0` au lieu de `None` → les trous restent absents
#  11 `en_retard` oublie le préfixe → le rattrapage voit le manifeste
#
#  ⚠️ UN BANC QUI TESTE DEUX GARDES À LA FOIS N'EN TESTE QU'UNE
#  (mutation n°5 du S0.5). Chaque test ci-dessous nomme l'assertion qui
#  porte SA propriété, et la note de session dit laquelle a rougi.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import gzip
import json
import os
import pathlib
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             os.pardir, "tools"))

import collect as C                                          # noqa: E402
import collect_reduit as R                                   # noqa: E402
import quota_openmeteo as Q                                  # noqa: E402
import score as SC                                           # noqa: E402

ECHECS: list[str] = []


def verifie(condition, message):
    if condition:
        print(f"  ✅ {message}")
    else:
        print(f"  ❌ {message}")
        ECHECS.append(message)


# ══════════════════════════════════════════════════════════════════
#  FABRIQUE — de vrais fichiers, de la vraie classe, en miniature
# ══════════════════════════════════════════════════════════════════

JOUR = datetime(2026, 8, 23, 5, 0, tzinfo=timezone.utc)
VEILLE = datetime(2026, 8, 22, tzinfo=timezone.utc)

#: Le référentiel de démonstration. ⚠️ Il CONTIENT une balise Pioupiou
#: — c'est tout l'objet du test n°1 : la population se construit en
#: RETIRANT `source == "pioupiou"` des référentiels, pas en partant
#: d'une liste où elle n'est pas.
REFS_DEMO = {
    "stations.json": [
        {"id": "70", "source": "pioupiou", "lat": 46.15, "lon": 6.19},
        {"id": "71", "source": "pioupiou", "lat": 45.90, "lon": 6.10},
    ],
    "windsmobi_stations.json": [
        {"id": "holfuy-918", "source": "windsmobi", "lat": 46.153,
         "lon": 6.194, "elev": 2100.0},
        {"id": "ffvl-12", "source": "windsmobi", "lat": 45.20, "lon": 5.70,
         "elev": 300.0},
    ],
    "infoclimat_stations.json": [
        {"id": "STA1", "source": "infoclimat", "lat": 44.10, "lon": 5.10,
         "elev": 1500.0},
        # ⛔ Celle-ci n'a AUCUNE observation la veille : c'est une
        # « muette », et elle sort au rang 0 — une exclusion gratuite,
        # pas une éviction.
        {"id": "MUETTE", "source": "infoclimat", "lat": 44.20, "lon": 5.20,
         "elev": 1800.0},
    ],
    "mf_stations.json": [
        {"id": "07577", "source": "mf", "lat": 43.60, "lon": 3.90,
         "elev": 50.0},
    ],
    "aemet_stations.json": [
        # Sans `elev` : elle doit sortir EN PREMIER au rang 1.
        {"id": "9999X", "source": "aemet", "lat": 42.50, "lon": -1.00},
    ],
    "metar_stations.json": [
        {"id": "LFLB", "source": "metar", "lat": 45.63, "lon": 5.88,
         "elev": 235.0},
    ],
}

#: Qui a été observé la veille. ⚠️ `infoclimat:MUETTE` n'y est pas.
OBSERVEES = [
    ("obs", [("pioupiou", "70"), ("pioupiou", "71")]),
    ("obswindsmobi", [("windsmobi", "holfuy-918"), ("windsmobi", "ffvl-12")]),
    ("obsinfoclimat", [("infoclimat", "STA1")]),
    ("obsmf", [("mf", "07577")]),
    ("obsaemet", [("aemet", "9999X")]),
    ("obsmetar", [("metar", "LFLB")]),
]


def racine_demo(avec_obs: bool = True) -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp(prefix="s11-"))
    for nom, liste in REFS_DEMO.items():
        (root / nom).write_text(json.dumps(liste), encoding="utf-8")
    if avec_obs:
        for prefixe, couples in OBSERVEES:
            d = root / prefixe / "2026" / "08"
            d.mkdir(parents=True, exist_ok=True)
            f = d / f"{prefixe}_2026-08-22.ndjson.gz"
            with gzip.open(f, "wt", encoding="utf-8") as fh:
                for src, sid in couples:
                    fh.write(json.dumps({
                        "source": src, "station_id": sid,
                        "t": [int((VEILLE + timedelta(hours=h)).timestamp())
                              for h in range(24)],
                        "speed": [20.0] * 24, "dir": [270.0] * 24}) + "\n")
    return root


def _payload(modeles: list[str], variables: list[str], n=24, trou_a=None,
             suffixe=True) -> dict:
    """Une réponse Open-Meteo, SUFFIXÉE comme l'API le fait dès que
    plusieurs modèles servent le point.

    ⚠️ `suffixe=False` reproduit le piège du 08/08 : un seul modèle sert
    le point, l'API rend `wind_speed_10m` TOUT COURT, et rien ne dit
    lequel a répondu.
    """
    t0 = int(JOUR.replace(hour=0).timestamp())
    hourly: dict = {"time": [t0 + 3600 * i for i in range(n)]}
    for m in modeles:
        for v in variables:
            serie: list = [12.0 if "speed" in v else 270.0] * n
            if trou_a is not None:
                serie[trou_a] = None
            hourly[f"{v}_{m}" if suffixe else v] = serie
    return {"hourly": hourly}


def _lignes_reduit(balises: list[dict], aloft=2.0, trou_a=None) -> list[dict]:
    """Ce que `collecter()` écrirait, sans un appel réseau : on passe
    par les VRAIES fonctions (`groupes_reduit`, `collect.forecast_rows`)
    et une réponse fabriquée."""
    lignes = []
    for st in balises:
        for modeles, variables in R.groupes_reduit():
            p = _payload(modeles, variables, trou_a=trou_a)
            # Le vent d'altitude du flux réduit, différent de celui de
            # `fcst/` — c'est ce qui rend le vol de régime visible.
            for v in C.ALOFT_VARS:
                for m in modeles:
                    if f"{v}_{m}" in p["hourly"]:
                        p["hourly"][f"{v}_{m}"] = [
                            aloft if "speed" in v else 270.0] * 24
            lignes += list(C.forecast_rows(st, p, JOUR.isoformat(), modeles))
    return lignes


#: ⚠️ LA JOURNÉE NOTÉE EST CELLE QUE LES SÉRIES COUVRENT. `_payload`
#: pose `t0` au minuit de `JOUR` : l'observation et la ligne de
#: référence doivent être sur LE MÊME jour, sinon `day_regime` rend
#: `unknown` pour une raison d'horaire et le banc croirait avoir mesuré
#: un vol de régime alors qu'il aurait mesuré un décalage de fabrique.
JOUR0 = JOUR.replace(hour=0, minute=0)


def _obs_pioupiou(jour=JOUR0) -> dict:
    return {"source": "pioupiou", "station_id": "70",
            "t": [int((jour + timedelta(hours=h)).timestamp())
                  for h in range(24)],
            "speed": [20.0] * 24, "dir": [270.0] * 24}


def _ligne_ecmwf_pioupiou(jour, aloft=45.0) -> dict:
    """La ligne de référence du régime, telle que `collect.py` l'écrit
    dans `fcst/` : `aloft_*` n'est posé QUE sur `REGIME_REF_MODEL`."""
    return {"station_id": "70", "source": "pioupiou", "lat": 46.15,
            "lon": 6.19, "model": C.REGIME_REF_MODEL,
            "fetched_at": jour.isoformat(),
            "t0": int(jour.timestamp()), "step_s": 3600,
            "speed": [20.0] * 24, "dir": [270.0] * 24,
            "aloft_level": C.REGIME_LEVEL,
            "aloft_speed": [aloft] * 24, "aloft_dir": [270.0] * 24}


def seau(chemin: pathlib.Path, evenements: list[tuple]) -> None:
    """Écrit un fichier de budget à la main.

    ⚠️ On ne peut PAS seeder ce seau par `demander()` : 3 810,6 pondérés
    d'un coup dépassent à eux seuls le plafond de la minute, et
    `Budget` refuserait — à juste titre. On écrit donc les événements
    au format du module (`_ecrire`, version 2), qui est le format réel.
    """
    chemin.write_text(json.dumps({
        "version": 2,
        "evenements": [[t, p, q] for t, p, q in evenements],
        "jours": {}}), encoding="utf-8")


# ══════════════════════════════════════════════════════════════════
#  1. ⛔⛔ LE FLUX NE VOLE PAS LE RÉGIME DES BALISES PIOUPIOU
# ══════════════════════════════════════════════════════════════════

def test_regime_pioupiou_inchange():
    """⛔ LA PROPRIÉTÉ CENTRALE DU LOT, ET ELLE EST INVISIBLE À LA
    LECTURE.

    `score.daily_rows` établit la référence d'altitude ainsi :

        for row in snapshots.get(0, []):
            if "aloft_speed" in row:
                ref_by_st[clé] = row

    — LE DERNIER GAGNE, et le test porte sur la PRÉSENCE de la clé, pas
    sur sa valeur. Ce flux-ci porte un VRAI `aloft_speed` (ECMWF à
    850 hPa, écrit par `collect.forecast_rows` parce que
    `REGIME_REF_MODEL` est dans son groupe d'altitude) ET il est lu EN
    DERNIER par `snapshot_rows_et_bilan`.

    ⇒ Si une balise Pioupiou entrait dans la population, SON RÉGIME
    SERAIT VOLÉ — mesuré au S0.5 : `fluxW` devient `thermal`, sur
    13 795 lignes par nuit, sans un message et sans un banc rouge.

    ⭐ **L'ASSERTION QUI PORTE LA PROPRIÉTÉ EST CELLE DU RÉGIME**, pas
    celle qui compte les sources. Celle-ci resterait verte le jour où
    quelqu'un renommerait quelque chose ; celle-là mesure ce qui compte
    vraiment : l'ajout du flux ne change pas le régime.
    """
    print("\n▶ 1. ajouter le flux réduit ne change PAS le régime des "
          "balises Pioupiou déjà notées")
    root = racine_demo()
    population, jrn = R.charger_population(root, VEILLE,
                                           crier=lambda *_: None)

    # ── assertion « comptable » (utile, mais PAS celle qui porte la
    #    propriété) ────────────────────────────────────────────────
    verifie(not any(b["source"] == "pioupiou" for b in population),
            "aucune balise `pioupiou` dans la population "
            f"({sorted({b['source'] for b in population})})")

    # ── ⭐ L'ASSERTION DE RÉGIME ─────────────────────────────────────
    jour0 = JOUR0
    ecmwf = _ligne_ecmwf_pioupiou(jour0, aloft=45.0)     # flux net → fluxW
    obs = _obs_pioupiou()
    lignes = _lignes_reduit(population, aloft=2.0)       # calme à 850 hPa
    avant, _ = SC.daily_rows(jour0, {0: [ecmwf], 1: [], 2: []},
                             [obs], [], 7200)
    apres, _ = SC.daily_rows(jour0, {0: [ecmwf] + lignes, 1: [], 2: []},
                             [obs], [], 7200)
    r_avant = {r["model"]: r["regime"] for r in avant
               if r["source"] == "pioupiou"}
    r_apres = {r["model"]: r["regime"] for r in apres
               if r["source"] == "pioupiou"}
    verifie(r_avant and r_avant == r_apres,
            f"⭐ le RÉGIME des balises Pioupiou est identique avant et "
            f"après l'ajout du flux réduit ({r_avant} → {r_apres})")

    # ⚠️ Et la preuve que ce banc SAIT échouer : si le filtre tombait,
    # la balise Pioupiou entrerait dans la population et son propre
    # `aloft_speed` (2 km/h) écraserait celui de `fcst/` (45 km/h).
    triche = _lignes_reduit(
        [{"id": "70", "source": "pioupiou", "lat": 46.15, "lon": 6.19,
          "elev": 1000.0}], aloft=2.0)
    triché, _ = SC.daily_rows(jour0, {0: [ecmwf] + triche, 1: [], 2: []},
                              [obs], [], 7200)
    r_triche = {r["model"]: r["regime"] for r in triché
                if r["source"] == "pioupiou"}
    verifie(r_triche.get(C.REGIME_REF_MODEL) != r_avant.get(C.REGIME_REF_MODEL),
            f"… et SANS le filtre, ce même régime CHANGERAIT "
            f"({r_avant.get(C.REGIME_REF_MODEL)} → "
            f"{r_triche.get(C.REGIME_REF_MODEL)}) — la propriété tient "
            f"bien au filtre, pas à un hasard de fabrique")

    verifie(jrn["exclues_source"].get("pioupiou") == 2
            and jrn["exclues_source"].get("metar") == 1,
            f"le journal COMPTE les exclusions par source "
            f"({jrn['exclues_source']})")


# ══════════════════════════════════════════════════════════════════
#  2. LA RÈGLE DU SUFFIXE DE MODÈLE
# ══════════════════════════════════════════════════════════════════

def test_suffixe_de_modele():
    """⛔ UN GROUPE À UN SEUL MODÈLE PRODUIRAIT ZÉRO LIGNE, EN SILENCE.

    Open-Meteo ne suffixe les clés par le nom du modèle que si
    PLUSIEURS modèles SERVENT le point (mesuré le 08/08) :

      · 8 demandés, 2 servent  → `wind_speed_10m_icon_d2`, etc. ;
      · 2 demandés, 1 SEUL sert → `wind_speed_10m` tout court, et rien
        dans la réponse ne dit lequel a répondu.

    Dans ce second cas, `collect.forecast_rows` ABANDONNE le point
    bruyamment plutôt que d'attribuer la série au hasard — une archive
    préfère un trou signalé à une ligne fausse. Deux gardes, deux
    assertions, et elles ne disent pas la même chose :

      (a) `groupes_reduit()` REFUSE de construire un groupe à un modèle ;
      (b) ⭐ et si un tel groupe partait quand même, l'abandon serait
          ANNONCÉ. C'est cette seconde assertion qui porte la propriété,
          et il a fallu muter pour s'en apercevoir : sans le garde-fou,
          la boucle ne trouve pas ses clés suffixées et rend zéro ligne
          ELLE AUSSI — le compte ne distingue pas les deux, seul le
          message le fait.
    """
    print("\n▶ 2. la règle du suffixe de modèle")
    st = {"id": "STA1", "source": "infoclimat", "lat": 44.1, "lon": 5.1}

    # (b) ⭐ le garde-fou du suffixe, testé sur les VRAIES fonctions.
    #
    # ⚠️ **ZÉRO LIGNE NE SUFFIT PAS COMME ASSERTION, ET C'EST TOUT LE
    # PIÈGE.** Sans le garde-fou, la boucle chercherait
    # `wind_speed_10m_icon_d2`, ne le trouverait pas, et rendrait AUSSI
    # zéro ligne — mais EN SILENCE. Les deux comportements sont
    # indistinguables par le nombre de lignes. Ce que le garde-fou
    # apporte, et la seule chose qu'il apporte, c'est que
    # L'ABANDON EST ANNONCÉ. C'est donc ÇA qu'on mesure.
    # (Trouvé en mutant : `if False:` à la place du garde-fou laissait
    #  le banc parfaitement vert tant qu'il ne testait que le compte.)
    import io                                                # noqa: PLC0415
    import contextlib                                        # noqa: PLC0415
    p_nu = _payload(["icon_d2"], R.VENT, suffixe=False)
    tampon = io.StringIO()
    with contextlib.redirect_stderr(tampon):
        lignes = list(C.forecast_rows(st, p_nu, JOUR.isoformat(),
                                      ["icon_d2", "icon_eu"]))
    dit = tampon.getvalue()
    verifie(lignes == [],
            "une réponse SANS suffixe de modèle ne produit AUCUNE ligne "
            f"— le point est abandonné, pas attribué au hasard "
            f"({len(lignes)} ligne(s))")
    verifie("sans suffixe de modèle" in dit and "infoclimat:STA1" in dit,
            f"⭐ … et l'abandon est ANNONCÉ, avec le nom du point — sans "
            f"ce message, zéro ligne et un HTTP 200 se lisent comme une "
            f"nuit normale ({dit.strip()[:70] or 'RIEN DIT'})")

    # … et avec le suffixe, les mêmes données passent : la propriété
    # tient au suffixe, pas à la fabrique.
    p_ok = _payload(["icon_d2", "icon_eu"], R.VENT, suffixe=True)
    lignes_ok = list(C.forecast_rows(st, p_ok, JOUR.isoformat(),
                                     ["icon_d2", "icon_eu"]))
    verifie(len(lignes_ok) == 2,
            f"… et avec le suffixe, les deux modèles produisent leurs "
            f"lignes ({len(lignes_ok)})")

    # (a) le garde-fou en amont : aucun groupe à moins de deux modèles
    for modeles, _v in R.groupes_reduit():
        verifie(len(modeles) >= 2,
                f"le groupe [{', '.join(modeles)}] porte au moins deux "
                f"modèles")
    verifie(C.COMPAGNON_ALTITUDE in R.MODELS_REDUIT_ALTITUDE,
            f"le compagnon MONDIAL du groupe d'altitude est bien "
            f"`{C.COMPAGNON_ALTITUDE}`, dérivé de `collect.py` et non "
            f"recopié")


# ══════════════════════════════════════════════════════════════════
#  3 & 4. LE CAP VIENT DU BUDGET MESURÉ, ET IL S'EXCLUT LUI-MÊME
# ══════════════════════════════════════════════════════════════════

def test_cap_lit_le_budget_mesure():
    """⛔ 2 905 POINTS, PAS 4 071 — ET LA DIFFÉRENCE EST LA NUIT
    PIOUPIOU.

    Le seuil de 60 % de `collect.quota_projete` (6 000 pondérés) est
    AVEUGLE à cette passe : il juge `n_points × par_point_jour` de SA
    population. Une passe candidates à 2 942 points × 1,40 projette
    4 119 pondérés — 69 % de 6 000 — et passerait sans avoir jamais vu
    les 3 810,6 de Pioupiou.

    ⇒ Le cap se calcule sur le budget MESURÉ. Avec 3 810,6 (`collect`)
    + 252,0 (`backfill_packs`) dans la fenêtre du jour, et la réserve
    nommée de 1 370, il ne reste que 4 067,4 pondérés, soit **2 905
    points**.
    """
    print("\n▶ 3. le cap vient du budget MESURÉ, pas de 60 % d'un plafond")
    root = pathlib.Path(tempfile.mkdtemp(prefix="s11-quota-"))
    chemin = root / "openmeteo.json"
    t = 1_787_000_000.0
    seau(chemin, [(t - 3600, 3810.6, "collect"),
                  (t - 1800, 252.0, "backfill_packs")])
    b = Q.Budget(R.ETIQUETTE_BUDGET, chemin=chemin, horloge=lambda: t)
    cap, jrn = R.cap_budgetaire(Q, b, R.poids_par_point_reduit())

    verifie(abs(jrn["autres"] - 4062.6) < 0.05,
            f"la consommation des AUTRES est lue, pas supposée "
            f"({jrn['autres']:.1f} pondérés)")
    verifie(cap == 2905,
            f"⭐ le cap vaut 2 905 points ({cap}) — soit "
            f"⌊(9 500 − 4 062,6 − 1 370) / 1,40⌋")
    verifie(cap <= 2905,
            f"⭐ … et il est ≤ 2 905 : un cap calculé sur « 9 500 × 0,6 » "
            f"en rendrait {int((9500 * 0.6 - 4062.6 - 1370) // 1.4)} ou "
            f"{int(9500 * 0.6 // 1.4)} selon la faute, jamais 2 905")
    verifie(jrn["source"] == "budget-mesure",
            f"le journal DIT d'où vient le budget ({jrn['source']})")


def test_cap_ignore_sa_propre_consommation_de_la_veille():
    """⛔⛔ LE PIÈGE LE PLUS VICIEUX DU LOT, ET IL EST INVISIBLE.

    `Budget.etat()["fenetres"]["jour"]` est une fenêtre GLISSANTE de
    24 h, pas une journée d'horloge. Une nuit où cette passe part deux
    minutes plus tôt que la veille verrait donc SA PROPRE CONSOMMATION
    DE LA VEILLE (4 067 pondérés) encore dedans — et calculerait un cap
    de ~0 point.

    ⛔ **La nuit serait perdue EN SILENCE, une fois sur deux**, sans
    qu'aucun garde-fou ne crie : le run écrirait une archive vide et
    sortirait en 0.

    ⭐ L'assertion qui porte la propriété est celle du cap INCHANGÉ.
    """
    print("\n▶ 4. le cap exclut SA PROPRE étiquette de la fenêtre glissante")
    root = pathlib.Path(tempfile.mkdtemp(prefix="s11-quota2-"))
    chemin = root / "openmeteo.json"
    t = 1_787_000_000.0
    base = [(t - 3600, 3810.6, "collect"), (t - 1800, 252.0, "backfill_packs")]
    seau(chemin, base)
    cap_sans, _ = R.cap_budgetaire(
        Q, Q.Budget(R.ETIQUETTE_BUDGET, chemin=chemin, horloge=lambda: t),
        R.poids_par_point_reduit())

    # La veille, à 22 h 19 d'ici, cette même passe a pris 4 067 pondérés.
    seau(chemin, base + [(t - 80_340, 4067.0, R.ETIQUETTE_BUDGET)])
    cap_avec, jrn = R.cap_budgetaire(
        Q, Q.Budget(R.ETIQUETTE_BUDGET, chemin=chemin, horloge=lambda: t),
        R.poids_par_point_reduit())

    verifie(R.ETIQUETTE_BUDGET in jrn["par_consommateur"],
            "sa propre consommation de la veille EST bien dans la "
            "fenêtre glissante (sinon le test ne testerait rien)")
    verifie(cap_avec == cap_sans == 2905,
            f"⭐ le cap est INCHANGÉ ({cap_sans} → {cap_avec}) : sa propre "
            f"étiquette est exclue. Sans l'exclusion, il tomberait à "
            f"{max(0, int((9500 - 4062.6 - 4067.0 - 1370) // 1.4))} point(s) "
            f"— et la nuit serait perdue en silence")


def test_cap_repli_derive():
    """⚠️ Le repli quand le budget partagé est illisible : DÉRIVÉ, pas
    inventé, et l'hypothèse la plus défavorable. Un garde-fou qui se
    trompe doit se tromper du côté qui protège."""
    print("\n▶ 4 bis. le repli sans budget partagé")
    repli = 657 * C.poids_par_point() + R.BACKFILL_PACKS_MESURE
    cap, jrn = R.cap_budgetaire(None, None, R.poids_par_point_reduit(),
                                conso_repli=repli)
    verifie(jrn["source"] == "repli-derive",
            f"le journal DIT que le budget est un repli ({jrn['source']})")
    verifie(cap == 2905,
            f"le repli dérivé du référentiel réel rend le même cap "
            f"({cap}) — 657 × {C.poids_par_point():.2f} + 252,0 = "
            f"{repli:.1f}")
    try:
        R.cap_budgetaire(None, None, R.poids_par_point_reduit())
    except R.Abort as exc:
        verifie("devine pas un budget" in str(exc),
                "sans budget ET sans repli, on s'ARRÊTE plutôt que de "
                "deviner")
    else:
        verifie(False, "sans budget ET sans repli, on s'ARRÊTE plutôt que "
                       "de deviner")


# ══════════════════════════════════════════════════════════════════
#  5. LES CLÉS, CARACTÈRE POUR CARACTÈRE
# ══════════════════════════════════════════════════════════════════

def test_cles_caractere_pour_caractere():
    """⛔ UNE CLÉ R2 S'ÉCRIT UNE FOIS, ET CE FLUX NE TOUCHE JAMAIS
    `fcst_*`.

    Écrire dans `fcst/` ferait compter cette passe comme une partie de
    la nuit Pioupiou — donc, le matin suivant, un `partie_manquante`
    sur une nuit qui n'a rien perdu. C'est l'incident que le S0.9 vient
    d'éteindre, et il ne doit pas se rallumer sur un flux neuf.
    """
    print("\n▶ 5. les clés, caractère pour caractère")
    verifie(R.fcstreduit_cle(JOUR)
            == "fcstreduit/2026/08/fcstreduit_2026-08-23.ndjson.gz",
            f"clé des données : {R.fcstreduit_cle(JOUR)}")
    verifie(R.manifeste_cle(JOUR)
            == "fcstreduit/2026/08/fcstreduit_2026-08-23.manifeste.json",
            f"clé du manifeste : {R.manifeste_cle(JOUR)}")
    verifie(R.fcstreduit_cle(JOUR) == SC.fcst_reduit_key(JOUR),
            "⭐ le producteur et le lecteur écrivent LA MÊME chaîne — "
            "deux noms pour une seule notion, c'est ainsi qu'on écrit "
            "dans le mauvais préfixe sans s'en apercevoir")
    verifie(not R.fcstreduit_cle(JOUR).startswith("fcst/")
            and not R.manifeste_cle(JOUR).startswith("fcst/"),
            "⭐ aucune des deux clés ne commence par `fcst/`")
    verifie(R.fcstreduit_cle(JOUR) != C.fcst_cle(JOUR)
            and R.manifeste_cle(JOUR) != C.manifeste_cle(JOUR),
            "… et aucune ne coïncide avec celles de la nuit Pioupiou "
            f"({C.fcst_cle(JOUR)})")
    verifie(C.FLUX_PARTITIONNE == "fcst",
            f"`collect.FLUX_PARTITIONNE` reste `fcst` ({C.FLUX_PARTITIONNE}) "
            f"— la partition du S0.6 découpe UNE population par groupe de "
            f"modèles ; ici c'est une AUTRE population")


# ══════════════════════════════════════════════════════════════════
#  6. LE MANIFESTE DÉCLARE CE QUE CE RUN ÉCRIT
# ══════════════════════════════════════════════════════════════════

def test_manifeste_declare_ce_que_le_run_ecrit():
    """⛔ LE DÉFAUT DU S0.9, CORRIGÉ LA VEILLE, À NE PAS REFABRIQUER.

    `collect.construire_manifeste` déclarait deux parties parce que
    `groupes_requete()` en rend toujours deux, alors que le run
    `--passe 0` écrivait TOUT dans une seule clé : 513 cases ont failli
    basculer en `partie_manquante` sur une nuit complète.

    ⇒ Ici le discriminant est STRUCTUREL : `parties` est la LONGUEUR DE
    LA LISTE DES CLÉS que l'appelant va écrire. Il ne peut pas mentir
    sans que l'appelant mente d'abord.
    """
    print("\n▶ 6. le manifeste déclare ce que CE RUN écrit")
    cles = [R.fcstreduit_cle(JOUR)]
    m = R.construire_manifeste(JOUR, 2942, cles)
    verifie(m["parties"] == 1,
            f"⭐ UNE partie déclarée ({m['parties']}) — ce run n'écrit "
            f"qu'une clé, quel que soit le nombre de groupes de requête "
            f"({len(R.groupes_reduit())})")
    verifie(len(m["detail"]) == 1 and m["detail"][0]["cle"] == cles[0],
            f"… et la partie déclarée porte LA clé écrite "
            f"({m['detail'][0]['cle']})")
    verifie(m["detail"][0]["modeles"] == R.MODELS_REDUIT,
            f"⭐ elle porte les CINQ modèles, dérivés et non recopiés "
            f"({m['detail'][0]['modeles']})")
    verifie(m["flux"] == R.FLUX,
            f"le bilan NOMME son flux ({m['flux']}) — sans ça, "
            f"« 1 partie » se lirait « il manque des flux »")
    verifie(abs(m["poids_point_total"] - 1.4) < 1e-9,
            f"le poids par point est celui de la clé réelle "
            f"({m['poids_point_total']})")
    # La preuve que le discriminant n'est pas `len(groupes)` : deux clés
    # déclarées ⇒ deux parties, même groupes.
    m2 = R.construire_manifeste(JOUR, 2942, cles + ["x/y.ndjson.gz"])
    verifie(m2["parties"] == 2,
            f"⭐ … et deux clés écrites feraient DEUX parties ({m2['parties']}) "
            f"— le discriminant est bien la liste des clés, pas "
            f"`len(groupes)`")
    verifie(m["version"] == SC.MANIFESTE_VERSION_LUE,
            f"la version du manifeste est celle que `score.py` sait lire "
            f"({m['version']})")


# ══════════════════════════════════════════════════════════════════
#  7. UNE ÉVICTION SE COMPTE ET SE NOMME
# ══════════════════════════════════════════════════════════════════

def test_eviction_compte_et_nomme():
    """⛔ PATRON DE `--limit`, CORRIGÉ AU S0.4.

    Avant, la coupe se faisait EN SILENCE, et comme la liste était
    triée par `id` et non par ancienneté, ce sont des balises
    arbitraires qui disparaissaient d'une archive irremplaçable. Un
    trou nommé vaut mieux qu'un run tué ; un trou ANONYME ne vaut rien
    du tout, parce qu'on ne saura jamais qu'il est là.
    """
    print("\n▶ 7. l'éviction COMPTE et NOMME")
    root = racine_demo()
    population, _ = R.charger_population(root, VEILLE, crier=lambda *_: None)
    dit: list[str] = []
    gardees, evincees = R.trier_et_evincer(population, 2, crier=dit.append)
    verifie(len(gardees) == 2 and len(evincees) == len(population) - 2,
            f"{len(evincees)} balise(s) évincée(s) sur {len(population)}")
    texte = " ".join(dit)
    verifie(str(len(evincees)) in texte,
            f"⭐ le journal COMPTE les évincées ({texte[:80]}…)")
    for b in evincees[:5]:
        verifie(f"{b['source']}:{b['id']}" in texte,
                f"⭐ le journal NOMME {b['source']}:{b['id']}")

    # ── rang 1 : altitude DÉCROISSANTE, sans-altitude EN PREMIER ────
    alts = [b["elev"] for b in gardees]
    verifie(all(a is not None for a in alts) and alts == sorted(alts,
                                                                reverse=True),
            f"⭐ les gardées sont les PLUS HAUTES, en ordre décroissant "
            f"({alts})")
    verifie(any(b["elev"] is None for b in evincees),
            "⭐ une balise SANS altitude sort EN PREMIER — on préfère "
            "perdre celle dont on ne sait rien")

    # ── rang 2 : déterminisme ──────────────────────────────────────
    g2, e2 = R.trier_et_evincer(list(reversed(population)), 2,
                               crier=lambda *_: None)
    verifie([b["id"] for b in g2] == [b["id"] for b in gardees],
            "⭐ l'ordre est DÉTERMINISTE : la même population présentée "
            "à l'envers évince exactement les mêmes balises")

    # Sous le cap, rien n'est évincé et rien n'est dit.
    dit2: list[str] = []
    g3, e3 = R.trier_et_evincer(population, 999, crier=dit2.append)
    verifie(not e3 and not dit2,
            "sous le cap, aucune éviction et aucun bruit")


# ══════════════════════════════════════════════════════════════════
#  8. LES MODÈLES PARTAGÉS — LA RAISON D'ÊTRE DU LOT
# ══════════════════════════════════════════════════════════════════

def test_modeles_partages_avec_la_population_pioupiou():
    """⭐ `k ≥ 6`, ET C'EST TOUT L'OBJET DU LOT.

    Un tau de Kendall compare deux classements DES MÊMES MODÈLES. Au
    23/08, les deux populations n'en partagent qu'UN (`arome_r2`) :
    zéro paire, donc pas de tau, donc le contrôle n°3 du S3 est hors
    périmètre. Avec ce flux, `k = 6` ⇒ 15 paires.

    ⛔ Un `icon_d2_reduit` rendrait `k = 1` — l'état d'aujourd'hui, pour
    le prix d'une nuit de quota.
    """
    print("\n▶ 8. les modèles partagés entre les deux populations")
    partages = [m for m in R.MODELS_REDUIT if m in C.MODELS]
    verifie(len(partages) == len(R.MODELS_REDUIT) == 5,
            f"⭐ les {len(R.MODELS_REDUIT)} modèles du flux réduit sont TOUS "
            f"dans `collect.MODELS` ({partages})")
    # `arome_r2` est le sixième : il est écrit par `arome_fcst.py` sur
    # les DEUX populations depuis le 22/08, gratuitement.
    k = len(partages) + 1
    verifie(k >= 6,
            f"⭐ k = {k} modèles partagés (les {len(partages)} d'ici + "
            f"`arome_r2`) ⇒ {k * (k - 1) // 2} paires — le contrôle n°3 du "
            f"S3 redevient calculable")
    verifie(all("_reduit" not in m and "_candidat" not in m
                for m in R.MODELS_REDUIT),
            "⭐ aucun nom de modèle n'est suffixé — un suffixe rendrait "
            "k = 1, donc zéro paire, donc rien")
    verifie(R.MODELS_REDUIT_ALTITUDE == [C.REGIME_REF_MODEL,
                                         C.COMPAGNON_ALTITUDE],
            f"le groupe d'altitude est DÉRIVÉ de `collect.py` "
            f"({R.MODELS_REDUIT_ALTITUDE}) — un `ecmwf_ifs025` recopié se "
            f"défait le jour où `REGIME_REF_MODEL` change")


def test_noms_de_modeles_identiques_a_collect():
    """Les trois modèles de surface sont des chaînes littérales : ce
    banc est la seule chose qui empêche une faute de frappe de créer un
    sixième modèle fantôme dans `model_verif_daily`."""
    print("\n▶ 8 bis. les noms de modèles de surface")
    for m in R.MODELS_REDUIT_SURFACE:
        verifie(m in C.MODELS,
                f"`{m}` existe dans `collect.MODELS`")
    verifie(len(set(R.MODELS_REDUIT)) == len(R.MODELS_REDUIT),
            "aucun doublon dans la composition")


def test_referentiels_identiques_a_arome_fcst():
    """⚠️ UNE DUPLICATION DÉCLARÉE ET BANCÉE, jamais une duplication
    muette. `REFERENTIELS` est écrit ici ET dans `arome_fcst.py` :
    l'égalité se vérifie, elle ne s'espère pas."""
    print("\n▶ 8 ter. le référentiel des référentiels")
    import arome_fcst as A                                   # noqa: PLC0415
    verifie(tuple(R.REFERENTIELS) == tuple(A.REFERENTIELS),
            f"les six référentiels sont les mêmes que ceux d'`arome_fcst` "
            f"({len(R.REFERENTIELS)})")


# ══════════════════════════════════════════════════════════════════
#  10. UN TROU RESTE UN TROU
# ══════════════════════════════════════════════════════════════════

def test_trou_reste_absence():
    """⛔ UN `0` SERAIT UN VENT CALME PARFAITEMENT CRÉDIBLE, QUE LE
    SCORING NOTERAIT COMME UNE PRÉVISION.

    Deux propriétés, toutes deux tenues par `collect.forecast_rows`, que
    ce flux importe sans les modifier :

      (a) une série ENTIÈREMENT nulle ne produit pas de ligne — un champ
          absent dit la vérité, une liste de nulls ment ;
      (b) ⭐ un trou PONCTUEL reste `None` à sa place, jamais 0.
    """
    print("\n▶ 10. un trou reste un trou")
    st = {"id": "STA1", "source": "infoclimat", "lat": 44.1, "lon": 5.1}
    lignes = _lignes_reduit([st], trou_a=5)
    verifie(lignes, "des lignes sont produites malgré le trou")
    r = lignes[0]
    verifie(r["speed"][5] is None,
            f"⭐ le trou de l'heure 5 reste `None` sur `{r['model']}` "
            f"({r['speed'][5]!r}) — un 0 serait du calme inventé, et le "
            f"scoring le noterait comme une prévision")
    verifie(r["speed"][4] == 12.0 and r["speed"][6] == 12.0,
            f"… et les heures voisines gardent leur valeur "
            f"({r['speed'][4]}, {r['speed'][6]})")
    verifie(all(any(v is None for v in x["speed"]) for x in lignes),
            f"le trou est à SA place sur les {len(lignes)} lignes, pas "
            f"comblé par un décalage")

    # (a) une série entièrement nulle ne fait pas de ligne
    p = _payload(["icon_d2", "icon_eu"], R.VENT)
    p["hourly"]["wind_speed_10m_icon_d2"] = [None] * 24
    lignes_nulles = list(C.forecast_rows(st, p, JOUR.isoformat(),
                                         ["icon_d2", "icon_eu"]))
    verifie([r["model"] for r in lignes_nulles] == ["icon_eu"],
            f"⭐ un modèle servi TOUT EN NULS ne produit aucune ligne "
            f"({[r['model'] for r in lignes_nulles]})")


# ══════════════════════════════════════════════════════════════════
#  11. LE RATTRAPAGE VOIT LE PRÉFIXE NEUF
# ══════════════════════════════════════════════════════════════════

def test_en_retard_voit_le_manifeste_du_flux_neuf():
    """⛔ 300 OCTETS PERDUS FONT NOTER UNE NUIT SUR UNE PARTIE SUR DEUX,
    EN SILENCE.

    `collect.en_retard()` ne cherchait que `*.ndjson.gz` ; le S0.6 l'a
    élargi aux `*.manifeste.json`. Il fait un `rglob` sur TOUTE la
    racine, donc le préfixe neuf est couvert sans une ligne de plus —
    mais ça se VÉRIFIE, ça ne se suppose pas.
    """
    print("\n▶ 11. le rattrapage voit le manifeste du flux neuf")
    root = pathlib.Path(tempfile.mkdtemp(prefix="s11-retard-"))
    d = root / R.FLUX / "2026" / "08"
    d.mkdir(parents=True)
    m = root / R.manifeste_cle(JOUR)
    a = root / R.fcstreduit_cle(JOUR)
    m.write_text("{}", encoding="utf-8")
    with gzip.open(a, "wt", encoding="utf-8") as fh:
        fh.write("{}\n")
    retard = {p.relative_to(root).as_posix() for p in C.en_retard(root)}
    verifie(R.manifeste_cle(JOUR) in retard,
            f"⭐ le MANIFESTE du flux neuf est vu par `en_retard` "
            f"({sorted(retard)})")
    verifie(R.fcstreduit_cle(JOUR) in retard,
            "… et l'archive aussi")
    # Un témoin posé le retire — le contrat du `.r2ok`.
    C.temoin(m).write_text("2026-08-23T05:00:00Z\n", encoding="utf-8")
    retard2 = {p.relative_to(root).as_posix() for p in C.en_retard(root)}
    verifie(R.manifeste_cle(JOUR) not in retard2,
            "… et un témoin posé le retire du rattrapage")


# ══════════════════════════════════════════════════════════════════
#  12. LA POPULATION, SA RÈGLE ET SON REPLI
# ══════════════════════════════════════════════════════════════════

def test_population_regle_et_repli():
    """⚠️ LE REPLI EST ÉCRIT, PAS SUBI — et le journal DIT lequel des
    deux chemins a été pris. Jamais un plantage, jamais un silence."""
    print("\n▶ 12. la règle de population, et son repli")
    root = racine_demo()
    pop, jrn = R.charger_population(root, VEILLE, crier=lambda *_: None)
    ids = {f"{b['source']}:{b['id']}" for b in pop}
    verifie("infoclimat:MUETTE" not in ids,
            "une balise sans AUCUNE observation la veille est exclue "
            "(rang 0)")
    verifie(jrn["muettes"] == 1
            and jrn["muettes_par_source"] == {"infoclimat": 1},
            f"le journal COMPTE les muettes et dit de quel réseau "
            f"({jrn['muettes_par_source']})")
    verifie(not jrn["repli_sans_obs"],
            "le journal dit que la règle a bien été appliquée")
    verifie(ids == {"windsmobi:holfuy-918", "windsmobi:ffvl-12",
                    "infoclimat:STA1", "mf:07577", "aemet:9999X"},
            f"la population est exactement la règle ({sorted(ids)})")

    # ── LE REPLI : aucune archive d'observations ────────────────────
    root2 = racine_demo(avec_obs=False)
    dit: list[str] = []
    pop2, jrn2 = R.charger_population(root2, VEILLE, crier=dit.append)
    verifie(jrn2["repli_sans_obs"] is True,
            "⭐ sans archive d'observations, le journal DIT que le repli "
            "a été pris")
    verifie(len(pop2) == 6,
            f"⭐ … et la population n'est PAS vide : on garde les "
            f"{len(pop2)} points hors pioupiou/metar, et c'est le cap "
            f"budgétaire qui tranche")
    verifie(any("REPLI" in m for m in dit),
            f"… et le mot est écrit noir sur blanc ({dit[:1]})")
    verifie(len(jrn2["obs_absentes"]) == len(SC.OBS_KEY_FUNCS),
            f"les {len(jrn2['obs_absentes'])} archives cherchées sont "
            f"NOMMÉES")

    # ── un référentiel absent n'est pas une erreur ──────────────────
    root3 = racine_demo()
    (root3 / "aemet_stations.json").unlink()
    dit3: list[str] = []
    pop3, jrn3 = R.charger_population(root3, VEILLE, crier=dit3.append)
    verifie(jrn3["referentiels"]["aemet_stations.json"] is None
            and len(pop3) == 4,
            "un référentiel ABSENT est dit et ignoré, pas fatal")


def test_regle_derive_des_obs_de_la_notation():
    """⭐ « Les archives `obs*` de la veille » doit vouloir dire LES
    MÊMES que celles que la notation lit. Dérivé de
    `score.OBS_KEY_FUNCS`, jamais recopié."""
    print("\n▶ 12 bis. la règle lit les mêmes archives que la notation")
    verifie(R.OBS_KEY_FUNCS is SC.OBS_KEY_FUNCS,
            f"`collect_reduit` lit LA liste de `score.py` "
            f"({len(SC.OBS_KEY_FUNCS)} archives), pas une copie")
    verifie(SC.obsmetar_key in SC.OBS_KEY_FUNCS,
            "⭐ `obsmetar_key` est entrée dans `OBS_KEY_FUNCS` "
            "(arbitrage n°5, tranché le 23/08) — 278 aérodromes ouverts "
            "à la NOTATION, zéro pondéré")
    verifie(SC.obsmetar_key(VEILLE)
            == "obsmetar/2026/08/obsmetar_2026-08-22.ndjson.gz",
            f"… et sa clé est inchangée ({SC.obsmetar_key(VEILLE)})")


# ══════════════════════════════════════════════════════════════════
#  13. LA SONDE DE FRAÎCHEUR
# ══════════════════════════════════════════════════════════════════

def test_sonde_echec_ne_tue_pas_la_passe():
    """⚠️ UNE COLONNE D'INFORMATION NE DOIT JAMAIS COÛTER UNE NUIT
    D'ARCHIVE."""
    print("\n▶ 13. la sonde de fraîcheur")
    vus: list[str] = []

    def faux_get(url, label):
        vus.append(url)
        if "dwd_icon_d2" in url:
            return None                      # ⛔ un domaine qui tombe
        return {"last_run_initialisation_time": "2026-08-23T03:00",
                "last_run_availability_time": "2026-08-23T04:26"}

    reel = R._get_json_retry
    R._get_json_retry = faux_get
    try:
        fraicheur, jrn = R.sonde_fraicheur(None, crier=lambda *_: None)
    finally:
        R._get_json_retry = reel

    verifie(len(vus) == len(R.DOMAINE_PAR_MODELE) + len(R.DOMAINES_TEMOINS)
            == 9,
            f"⭐ NEUF appels, le chiffre budgété ({len(vus)})")
    verifie("icon_d2" not in fraicheur and jrn["echecs"] == ["dwd_icon_d2"],
            f"⭐ un domaine qui tombe est COMPTÉ et NOMMÉ, et la passe "
            f"continue ({jrn['echecs']})")
    verifie(all(m in fraicheur for m in R.MODELS_REDUIT if m != "icon_d2"),
            f"les quatre autres modèles ont leur run "
            f"({sorted(fraicheur)})")
    verifie(len(jrn["temoins"]) == 4,
            f"les quatre témoins sont relevés pour le journal et le "
            f"manifeste ({len(jrn['temoins'])})")
    verifie(R.DOMAINE_PAR_MODELE["gfs_global"] == "ncep_gfs013",
            "⭐ `gfs_global` est servi par `ncep_gfs013` — une "
            "correspondance fausse écrirait le run d'un autre modèle")

    # ── les lignes portent le run, et SEULEMENT si la sonde l'a eu ──
    # ⚠️ On ne fait PAS tourner `collecter()` ici : elle appellerait
    # `fetch_forecast`, donc le réseau, et un banc qui sort de la
    # machine n'est plus un banc. On rejoue le greffage sur des lignes
    # produites par le VRAI chemin (`collect.forecast_rows`).
    st = {"id": "STA1", "source": "infoclimat", "lat": 44.1, "lon": 5.1}
    brutes = _lignes_reduit([st])
    greffees = []
    for r in brutes:
        info = fraicheur.get(r["model"])
        if info:
            r["run_init"], r["run_avail"] = info["init"], info["avail"]
        greffees.append(r)
    avec = [r for r in greffees if "run_init" in r]
    sans = [r for r in greffees if "run_init" not in r]
    verifie(avec and all(r["run_init"] == "2026-08-23T03:00" for r in avec),
            f"⭐ `run_init` est écrit DANS CHAQUE LIGNE ({len(avec)} lignes)")
    verifie(all(r["model"] == "icon_d2" for r in sans),
            f"⚠️ un champ ABSENT dit « la sonde n'a pas eu ce domaine » — "
            f"un `null` ne dirait rien ({[r['model'] for r in sans]})")


# ══════════════════════════════════════════════════════════════════
#  14. LE COÛT, CHIFFRÉ SUR DES URL CONSTRUITES ET NON ENVOYÉES
# ══════════════════════════════════════════════════════════════════

def test_cout_par_point():
    """⛔ TOUT CHIFFRAGE PASSE PAR `poids_url()` SUR DES URL CONSTRUITES
    ET JAMAIS ENVOYÉES. La première dépense Open-Meteo du groupe réduit
    est la première nuit après activation — pas avant, pas « pour
    voir »."""
    print("\n▶ 14. le coût par point")
    total = 0.0
    for modeles, variables in R.groupes_reduit():
        params = {"latitude": "45.9000", "longitude": "6.1000",
                  "hourly": ",".join(variables), "models": ",".join(modeles),
                  "forecast_days": "3", "wind_speed_unit": "kmh",
                  "timeformat": "unixtime"}
        import urllib.parse                                  # noqa: PLC0415
        url = f"{C.FORECAST_API}?{urllib.parse.urlencode(params)}"
        total += Q.poids_url(url)
    verifie(abs(total - 1.40) < 1e-9,
            f"⭐ 1,40 pondéré par point, mesuré sur l'URL RÉELLE ({total})")
    verifie(abs(R.poids_par_point_reduit() - total) < 1e-9,
            f"… et `poids_par_point_reduit()` rend le même chiffre "
            f"({R.poids_par_point_reduit()}) — dérivé, jamais recopié")
    verifie(abs(C.poids_par_point() - 5.80) < 1e-9,
            f"⚠️ et la passe Pioupiou est INCHANGÉE à "
            f"{C.poids_par_point():.2f} pondéré/point — ce lot ne la "
            f"touche pas")


def main() -> int:
    print("═" * 68)
    print("  BANC DU GROUPE RÉDUIT SUR LES CANDIDATES — lot S0.11, 23/08/2026")
    print("═" * 68)
    test_regime_pioupiou_inchange()
    test_suffixe_de_modele()
    test_cap_lit_le_budget_mesure()
    test_cap_ignore_sa_propre_consommation_de_la_veille()
    test_cap_repli_derive()
    test_cles_caractere_pour_caractere()
    test_manifeste_declare_ce_que_le_run_ecrit()
    test_eviction_compte_et_nomme()
    test_modeles_partages_avec_la_population_pioupiou()
    test_noms_de_modeles_identiques_a_collect()
    test_referentiels_identiques_a_arome_fcst()
    test_trou_reste_absence()
    test_en_retard_voit_le_manifeste_du_flux_neuf()
    test_population_regle_et_repli()
    test_regle_derive_des_obs_de_la_notation()
    test_sonde_echec_ne_tue_pas_la_passe()
    test_cout_par_point()
    print("\n" + "═" * 68)
    if ECHECS:
        print(f"❌ {len(ECHECS)} assertion(s) en échec :")
        for e in ECHECS:
            print(f"   · {e}")
        return 1
    print("✅ banc du groupe réduit : tout est vert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
