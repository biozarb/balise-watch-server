#!/usr/bin/env python3
"""test_score.py — banc d'essai du job de notation.

    Session 08/08/2026.

⚠️ CE BANC PARLE LA LANGUE DE `collect.py`, PAS CELLE DE `score.py`.
Les entrées sont des lignes NDJSON de la forme EXACTE que `collect.py`
écrit — `t0` + `step_s`, les séries par modèle, `aloft_speed` seulement
sur le modèle de référence. C'est la leçon du défaut `aliasOf` du
07/08 : un banc qui invente ses propres entrées teste la fonction, pas
l'intégration, et peut rester vert alors que le seul appelant réel
parle un autre vocabulaire.

Rien ici ne touche au réseau ni à Supabase : `score.py` sépare la
lecture d'archive du calcul précisément pour que ce soit possible.
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import os
import pathlib
import sys
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scoring as S      # noqa: E402
import score as J        # noqa: E402
import inference as I    # noqa: E402  (lot L3 : BOOTSTRAP_ITERATIONS)

OK = KO = 0
DAY = datetime(2026, 8, 5)
DAY_MS = int(DAY.replace(tzinfo=timezone.utc).timestamp()) * 1000


def check(label, got, want, tol=1e-6):
    global OK, KO
    same = _same(got, want, tol)
    if same:
        OK += 1
    else:
        KO += 1
        print(f"  ❌ {label}\n       obtenu  : {got!r}\n       attendu : {want!r}")


def _same(a, b, tol):
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if a is None or b is None:
        return a is None and b is None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= tol + tol * abs(b)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(_same(x, y, tol) for x, y in zip(a, b))
    return a == b


# ══════════════════════════════════════════════════════════════════
#  LE REPLI DES DEUX RAISONS DE RANG (28/08/2026)
# ══════════════════════════════════════════════════════════════════
#
# ⛔ LA NUIT DU 27/08, REJOUÉE LE 28, EST MORTE ICI — après l'OOM, et
# pour une tout autre cause. `_apply_rank_corr` pose `duplicate_chain`
# et `appliquer_fdr` pose `fdr` dans `rank_reason_corr`, dont le CHECK
# (`supabase_step52_rank_corr.sql`) ne connaît ni l'un ni l'autre. La
# base a répondu `23514` en nommant
# `model_score_zone_rank_reason_corr_check` ; le repli ne regardait que
# le CHECK de `rank_reason`, il a re-levé, et l'upsert ENTIER de
# `model_score_zone` est tombé — vingt-trois minutes de calcul pour
# rien, et L2/L3/L7 toujours sans un objet publié.


def _corps_postgrest(contrainte: str) -> bytes:
    """Le corps EXACT que PostgREST rend sur un CHECK violé.

    ⓘ La ligne de `details` est celle du 28/08, recopiée du journal :
    438 caractères pour une seule ligne de `model_score_zone`. C'est
    elle qui poussait `message` hors des 400 octets lus.
    """
    ligne = ("(2026-08-28, *:valley, arome_r2, 6, rolling15, all, "
             "landform, 324, 38444, 1935, 3.55, 8.3392, f, -0.3475, "
             "null, null, null, duplicate_chain, null, null, null, "
             "null, 6, null, window_too_short, null, 3.5976, 3.5636, "
             "0.005, -1.3479, f, 2.8772, f, -0.198, 820, 4, 78, null, "
             "duplicate_chain)")
    return json.dumps({
        "code": "23514",
        "details": f"Failing row contains {ligne}.",
        "hint": None,
        "message": (f'new row for relation "model_score_zone" violates '
                    f'check constraint "{contrainte}"'),
    }).encode("utf-8")


def test_detail_erreur_le_nom_de_la_contrainte_survit():
    print("── erreur PostgREST : le nom de la contrainte survit (28/08) ──")
    corps = _corps_postgrest("model_score_zone_rank_reason_corr_check")
    check("⛔ le corps réel dépasse les 400 octets que le code lisait",
          len(corps) > 400, True)
    check("⛔ … et le nom de la contrainte est APRÈS le 400ᵉ octet : "
          "c'est pour ça que le repli ne partait jamais",
          corps.decode().index("rank_reason_corr_check") > 400, True)

    check("⛔ … et le code lit assez d'octets pour que ce corps entre en "
          "ENTIER : une lecture courte re-couperait le message avant "
          "même la mise en forme",
          J.ERREUR_OCTETS > len(corps), True)

    lu = J._detail_erreur(corps)
    check("le nom de la contrainte survit à la mise en forme",
          "model_score_zone_rank_reason_corr_check" in lu, True)
    check("le code SQL aussi", "23514" in lu, True)
    check("la ligne fautive reste reconnaissable", "*:valley" in lu, True)
    check("… mais elle est tronquée, pas rendue entière",
          "(+" in lu and "car.)" in lu, True)
    check("le message reste court", len(lu) < 900, True)

    # ⛔ ET SURTOUT : `message` avant `details`. C'est l'ORDRE qui tient
    # la propriété, pas la longueur — un jour la ligne fera cinquante
    # colonnes.
    check("`message` est placé AVANT `details`",
          lu.index('"message"') < lu.index('"details"'), True)

    # Une ligne fautive démesurée ne doit rien pousser dehors.
    enorme = json.dumps({"code": "23514", "details": "x" * 50000,
                         "message": 'violates check constraint "zz_check"'})
    lu2 = J._detail_erreur(enorme.encode("utf-8"))
    check("une ligne de 50 000 caractères ne chasse pas le message",
          "zz_check" in lu2, True)
    check("… et le message reste borné", len(lu2) < 900, True)

    # Un corps qui n'est pas du JSON (passerelle, HTML) : on rend le
    # texte, on ne perd pas l'information et on ne lève pas.
    brut = b"<html><body>502 Bad Gateway</body></html>"
    check("un corps non-JSON est rendu tel quel",
          "502 Bad Gateway" in J._detail_erreur(brut), True)
    check("un corps vide ne lève pas", J._detail_erreur(b""), "")


class _SbRefuse:
    """Un Supabase qui refuse en NOMMANT sa contrainte, une fois chacune."""

    def __init__(self, contraintes):
        self.restantes = list(contraintes)
        self.appels = []

    def upsert(self, table, rows, cle):
        self.appels.append([dict(r) for r in rows])
        # ⛔ LE GARDE-FOU DU BANC LUI-MÊME. Une mutation qui retire le
        # « déjà désarmée » du repli fait boucler `_upsert_scores` POUR
        # TOUJOURS ; sans ce compteur, la mutation ne rougirait pas —
        # elle PENDRAIT, et un banc qui pend ne dit rien du tout.
        if len(self.appels) > 20:
            raise RuntimeError("le repli ne s'arrête pas : 20 upserts")
        if self.restantes:
            nom = self.restantes.pop(0)
            # ⛔⛔ ET LE MESSAGE PASSE PAR LE MÊME CHEMIN QUE LE VRAI —
            # `_detail_erreur` sur un corps PostgREST À LA BONNE FORME.
            # C'est là toute la leçon du 28/08 : le banc d'origine
            # fabriquait un message court où le nom de la contrainte
            # arrivait en deuxième position, donc TOUJOURS lisible. Le
            # vrai corps met `details` — la ligne entière, trente-huit
            # colonnes — AVANT `message`, et le code lisait 400 octets.
            # Le repli était vert au banc et mort en production.
            raise J.Abort(f"upsert {table} : HTTP 400 — "
                          + J._detail_erreur(_corps_postgrest(nom)))
        return len(rows)


def _lignes_de_rang():
    return [
        {"rank_reason": "duplicate_chain", "rank_reason_corr": "duplicate_chain"},
        {"rank_reason": "fdr", "rank_reason_corr": "fdr"},
        {"rank_reason": "ok", "rank_reason_corr": "mixed_population"},
        {"rank_reason": "single_model", "rank_reason_corr": "ok"},
        {"rank_reason": None, "rank_reason_corr": None},
    ]


def test_repli_rang_corr_la_seconde_contrainte_ne_tue_plus_la_nuit():
    print("── repli : les DEUX raisons de rang (28/08) ──")
    import contextlib, io

    # (1) SEULE la contrainte du CORRIGÉ refuse — le cas réel du 28/08.
    rows = _lignes_de_rang()
    sb = _SbRefuse(["model_score_zone_rank_reason_corr_check"])
    with contextlib.redirect_stderr(io.StringIO()) as err:
        n = J._upsert_scores(sb, rows)
    check("la nuit passe malgré le CHECK du corrigé", n, 5)
    check("`duplicate_chain` est tu dans la colonne CORRIGÉE",
          rows[0]["rank_reason_corr"], None)
    check("`fdr` aussi", rows[1]["rank_reason_corr"], None)
    check("⛔ mais la colonne BRUTE n'est PAS touchée : c'est un autre "
          "CHECK, et l'écraser perdrait une raison que la base accepte",
          rows[0]["rank_reason"], "duplicate_chain")
    check("`mixed_population` survit (le step52 l'admet)",
          rows[2]["rank_reason_corr"], "mixed_population")
    check("`ok` survit", rows[3]["rank_reason_corr"], "ok")
    check("le journal nomme le `.sql` à jouer",
          "supabase_step58_rank_reason_corr.sql" in err.getvalue(), True)
    check("… et nomme la colonne, pas seulement la valeur",
          "rank_reason_corr" in err.getvalue(), True)

    # (2) LES DEUX contraintes refusent, l'une APRÈS l'autre. C'est ce
    # qu'un `try` unique ne pouvait pas tenir.
    rows = _lignes_de_rang()
    sb = _SbRefuse(["model_score_zone_rank_reason_check",
                    "model_score_zone_rank_reason_corr_check"])
    with contextlib.redirect_stderr(io.StringIO()):
        n = J._upsert_scores(sb, rows)
    check("la nuit passe même avec DEUX refus successifs", n, 5)
    check("trois tentatives d'upsert, pas deux", len(sb.appels), 3)
    check("la raison brute neuve est tue", rows[0]["rank_reason"], None)
    check("la raison corrigée neuve aussi", rows[0]["rank_reason_corr"], None)
    check("`single_model` est tu côté BRUT (step42 pas joué)",
          rows[3]["rank_reason"], None)
    check("… mais reste admis côté CORRIGÉ (step52 le connaît)",
          rows[3]["rank_reason_corr"], "ok")

    # (3) UNE CONTRAINTE QU'ON NE SAIT PAS DÉSARMER PASSE À TRAVERS.
    # Un repli qui avale tout ferait disparaître les vraies pannes.
    rows = _lignes_de_rang()
    sb = _SbRefuse(["model_score_zone_pkey"])
    try:
        J._upsert_scores(sb, rows)
        check("une contrainte inconnue doit RE-LEVER", "passé", "Abort")
    except J.Abort as exc:
        check("une contrainte inconnue re-lève telle quelle",
              "model_score_zone_pkey" in str(exc), True)

    # (4) ⛔ ET LA MÊME CONTRAINTE QUI REFUSE DEUX FOIS NE BOUCLE PAS.
    # Sans le garde `déjà désarmée`, le run tournerait pour toujours —
    # et un run qui ne finit jamais est pire qu'un run qui échoue.
    rows = _lignes_de_rang()
    sb = _SbRefuse(["model_score_zone_rank_reason_corr_check"] * 6)
    try:
        J._upsert_scores(sb, rows)
        check("la même contrainte deux fois doit RE-LEVER", "passé", "Abort")
    except J.Abort:
        check("la même contrainte deux fois re-lève au lieu de boucler",
              len(sb.appels) <= len(J.REPLIS_RANG) + 1, True)



# ══════════════════════════════════════════════════════════════════
#  LOT L18 (30/08/2026) — UN SEUL AGRUME AU CLASSEMENT
# ══════════════════════════════════════════════════════════════════
#
# ⛔ CE QUE CES BANCS DOIVENT TENIR, ET POURQUOI CHACUN EXISTE.
# Mesuré en base le 30/08 (`as_of = 2026-08-30`) AVANT d'écrire une
# ligne : `agrume` (AROME 10 m brut) tenait 9 rangs dont UNE première
# place, `agrume_pi` (le composite servi à l'écran) 5 rangs et aucune.
# Le podium revenait donc au produit que personne ne reçoit. La
# décision de Yann du 30/08 le retire du RANG — jamais de la base, où
# le duel apparié du lot L1 a besoin des deux séries.

def _daily_agrume(zone_of, erreurs, jours=15):
    """Des balise-jours synthétiques, un modèle par entrée d'`erreurs`."""
    out = []
    for j in range(jours):
        d = (DAY - timedelta(days=j)).strftime("%Y-%m-%d")
        for i in range(830, 836):
            for model, err in erreurs:
                out.append({
                    "day": d, "source": "pioupiou", "station_id": str(i),
                    "model": model, "lead_h": 24, "regime": "fluxN",
                    "n_hours": 12, "err_vec_med": err,
                    "mse_model": err * err, "mse_persist": 100.0})
    return out


ZONE_L18 = {f"pioupiou:{i}": {"zone_id": "b1:valley", "landform": "valley",
                              "basin_id": "b1", "massif_id": "alpes-nord",
                              "basin_uncertain": False}
            for i in range(830, 836)}


def test_l18_un_seul_agrume_au_classement():
    """Lot L18 — `agrume` (AROME brut) n'a pas le droit de se classer
    contre `agrume_pi` (le composite), qui est le produit SERVI.
    """
    print("── lot L18 : un seul AGRUME au classement (`serie_temoin`) ──")
    # ⭐ LE CHIFFRE EST CHOISI POUR REPRODUIRE LE CAS RÉEL DU 30/08 :
    # `agrume` (3,0) bat NUMÉRIQUEMENT `agrume_pi` (4,0) et prendrait
    # la 1re place — c'est exactement ce qui se passait en production
    # sur b44.67_6.61:slope, où le témoin était PREMIER.
    daily = _daily_agrume(ZONE_L18, (("icon_d2", 5.0),
                                     (J.AGRUME_MODEL, 3.0),
                                     (J.AGRUME_PI_MODEL, 4.0)))
    rows = J.rolling_scores(daily, ZONE_L18, DAY)
    fine = [r for r in rows if r["zone_id"] == "b1:valley"]
    check("les trois modèles gardent chacun leur ligne (rien n'est "
          "supprimé de la base)", sorted(r["model"] for r in fine),
          sorted(["icon_d2", J.AGRUME_MODEL, J.AGRUME_PI_MODEL]))

    icon = next(r for r in fine if r["model"] == "icon_d2")
    ag = next(r for r in fine if r["model"] == J.AGRUME_MODEL)
    pi = next(r for r in fine if r["model"] == J.AGRUME_PI_MODEL)

    check("⭐⭐ le COMPOSITE est 1er (4,0 km/h), alors que le témoin "
          "(3,0) est numériquement MEILLEUR — il n'a jamais eu le "
          "droit de concourir", pi["rank"], 1)
    check("⭐ icon_d2 est 2e (5,0 km/h)", icon["rank"], 2)
    check("`agrume` n'a AUCUN rang, quel que soit son chiffre",
          ag["rank"], None)
    check("… et sa raison le nomme précisément — PAS `duplicate_chain`, "
          "les deux séries diffèrent par Δ et le duel du L1 le mesure",
          ag["rank_reason"], J.RANK_REASON_SERIE_TEMOIN)
    check("⛔ le témoin garde son erreur typique intacte (3,0 km/h) — "
          "seul le RANG lui est refusé", ag["typical_err_kmh"], 3.0)
    check("… et son `beats_persist` aussi, calculé contre la "
          "persistance, pas contre les autres modèles",
          ag["beats_persist"] is not None, True)
    check("le composite garde sa vraie raison de classement (« ok »)",
          pi["rank_reason"], "ok")


def test_l18_agrume_seul_concourt_normalement():
    """Lot L18 — la règle ne mord QUE si les deux séries sont dans la
    même case. Mesuré le 30/08 : 146 cases ne portent que le témoin (la
    population du composite est un sous-ensemble strict de la sienne).
    """
    print("── lot L18 : seul, `agrume` concourt normalement ──")
    daily = _daily_agrume(ZONE_L18, (("icon_d2", 5.0),
                                     (J.AGRUME_MODEL, 3.0)))
    rows = J.rolling_scores(daily, ZONE_L18, DAY)
    fine = [r for r in rows if r["zone_id"] == "b1:valley"]
    ag = next(r for r in fine if r["model"] == J.AGRUME_MODEL)
    check("⭐ composite absent de la case → `agrume` est 1er, "
          "normalement, comme `arome_r2` seul au lot L2",
          (ag["rank"], ag["rank_reason"]), (1, "ok"))


def test_l18_les_deux_exclusions_coexistent():
    """Lot L18 — une case peut porter les DEUX chaînes AROME *et* les
    DEUX AGRUME. C'est la raison d'être du dictionnaire rendu par
    `_exclus_du_rang` : n'écarter qu'un seul laisserait un billet de
    trop au podium, exactement le défaut que le L2 ferme.
    """
    print("── lot L18 : les deux règles d'exclusion dans la MÊME case ──")
    daily = _daily_agrume(ZONE_L18, (("icon_d2", 6.0),
                                     (J.AROME_HD_MODEL, 5.0),
                                     (J.AROME_R2_MODEL, 4.5),
                                     (J.AGRUME_MODEL, 3.0),
                                     (J.AGRUME_PI_MODEL, 4.0)))
    rows = J.rolling_scores(daily, ZONE_L18, DAY)
    fine = [r for r in rows if r["zone_id"] == "b1:valley"]
    par = {r["model"]: r for r in fine}
    check("les cinq lignes existent toujours", len(fine), 5)
    check("⭐⭐ le composite prend la 1re place (4,0) devant les deux "
          "écartés, qui sont pourtant meilleurs ou proches",
          par[J.AGRUME_PI_MODEL]["rank"], 1)
    check("⛔ `arome_r2` : écarté, motif `duplicate_chain`",
          (par[J.AROME_R2_MODEL]["rank"],
           par[J.AROME_R2_MODEL]["rank_reason"]),
          (None, J.RANK_REASON_DUPLICATE_CHAIN))
    check("⛔ `agrume` : écarté, motif `serie_temoin` — les deux motifs "
          "coexistent et ne se recouvrent JAMAIS",
          (par[J.AGRUME_MODEL]["rank"],
           par[J.AGRUME_MODEL]["rank_reason"]),
          (None, J.RANK_REASON_SERIE_TEMOIN))
    check("⭐ et les admis se classent entre eux sans trou : mfhd 2e, "
          "icon_d2 3e", (par[J.AROME_HD_MODEL]["rank"],
                         par["icon_d2"]["rank"]), (2, 3))
    check("`_exclus_du_rang` rend bien DEUX écartés pour cette case",
          J._exclus_du_rang([{"model": m} for m in par]),
          {J.AROME_R2_MODEL: J.RANK_REASON_DUPLICATE_CHAIN,
           J.AGRUME_MODEL: J.RANK_REASON_SERIE_TEMOIN})


def test_l18_le_temoin_voyage_jusquau_corrige():
    """Lot L18 — la même case n'a pas le droit de dire `serie_temoin`
    sur le brut et `mixed_population` (ou pire, un rang) sur le
    corrigé, pour le MÊME modèle. C'est la leçon du L2, reprise.
    """
    print("── lot L18 : le témoin voyage jusqu'à la colonne corrigée ──")
    jours = [f"2026-08-{d:02d}" for d in range(1, 16)]
    par_modele = {"icon_d2": [], J.AGRUME_MODEL: [], J.AGRUME_PI_MODEL: []}
    for j in jours:
        for u in range(6):
            for m, e, ec in (("icon_d2", 5.0, 5.0),
                             (J.AGRUME_MODEL, 3.0, 1.0),
                             (J.AGRUME_PI_MODEL, 4.0, 4.0)):
                par_modele[m].append({"day": j, "unit": f"p:{u}",
                                      "err_vec_med": e,
                                      "err_vec_med_corr": ec})
    rows = [{"model": "icon_d2", "typical_err_kmh": 5.0,
             "typical_err_kmh_corr": 5.0, "occurrences": 90, "n_corr": 90},
            {"model": J.AGRUME_MODEL, "typical_err_kmh": 3.0,
             "typical_err_kmh_corr": 1.0, "occurrences": 90, "n_corr": 90},
            {"model": J.AGRUME_PI_MODEL, "typical_err_kmh": 4.0,
             "typical_err_kmh_corr": 4.0, "occurrences": 90, "n_corr": 90}]
    exclus = J._exclus_du_rang(rows)
    check("l'écarté calculé est bien le témoin",
          exclus, {J.AGRUME_MODEL: J.RANK_REASON_SERIE_TEMOIN})
    J._apply_rank_corr(rows, par_modele, exclus)
    icon, ag, pi = rows
    check("⭐ le composite gagne le corrigé (4,0 contre 5,0) — le "
          "témoin (1,0, le plus bas des trois) n'a jamais concouru",
          (pi["rank_reason_corr"], pi["rank_corr"]), ("ok", 1))
    check("… icon_d2 2e", icon["rank_corr"], 2)
    check("⛔ le témoin : rang corrigé nul, `serie_temoin` — jamais "
          "`mixed_population`",
          (ag["rank_corr"], ag["rank_reason_corr"]),
          (None, J.RANK_REASON_SERIE_TEMOIN))


def test_l18_apply_rank_corr_accepte_encore_une_chaine():
    """Lot L18 — la compatibilité des bancs du L2 n'est pas un détail :
    `_apply_rank_corr` reçoit un DICTIONNAIRE depuis `_apply_rank`,
    mais les bancs du L2 lui passent un NOM DE MODÈLE. Les deux formes
    doivent produire le même objet, sinon on croit tenir le L2 alors
    qu'on ne tient plus rien.
    """
    print("── lot L18 : `_apply_rank_corr` tient les deux formes ──")
    def _rows():
        return [{"model": "icon_d2", "typical_err_kmh": 3.0,
                 "typical_err_kmh_corr": 3.0, "occurrences": 90, "n_corr": 90},
                {"model": J.AROME_HD_MODEL, "typical_err_kmh": 5.0,
                 "typical_err_kmh_corr": 5.0, "occurrences": 90, "n_corr": 90},
                {"model": J.AROME_R2_MODEL, "typical_err_kmh": 4.5,
                 "typical_err_kmh_corr": 1.0, "occurrences": 90, "n_corr": 90}]
    par_modele = {m: [{"day": f"2026-08-{d:02d}", "unit": f"p:{u}",
                       "err_vec_med": e, "err_vec_med_corr": ec}
                      for d in range(1, 16) for u in range(6)]
                  for m, e, ec in (("icon_d2", 3.0, 3.0),
                                   (J.AROME_HD_MODEL, 5.0, 5.0),
                                   (J.AROME_R2_MODEL, 4.5, 1.0))}
    par_chaine, par_dict = _rows(), _rows()
    J._apply_rank_corr(par_chaine, par_modele, J.AROME_R2_MODEL)
    J._apply_rank_corr(par_dict, par_modele,
                       {J.AROME_R2_MODEL: J.RANK_REASON_DUPLICATE_CHAIN})
    check("⭐ un nom de modèle et un dictionnaire rendent le MÊME objet",
          [(r["rank_corr"], r["rank_reason_corr"]) for r in par_chaine],
          [(r["rank_corr"], r["rank_reason_corr"]) for r in par_dict])
    check("… et c'est bien `duplicate_chain` qui sort de la forme courte",
          par_chaine[2]["rank_reason_corr"], "duplicate_chain")


def test_l18_le_rang_perime_du_temoin_est_efface():
    """Lot L18 — l'écarté ne se contente pas de « ne pas recevoir » de
    rang : le sien est EFFACÉ.

    ⛔ POURQUOI CE BANC EXISTE, ET IL A UNE HISTOIRE COURTE. La
    mutation nº 6 du 30/08 (retirer `r["rank"] = None` de la boucle
    d'exclusion) laissait le banc VERT : l'écarté n'étant jamais dans
    `admis`, aucun test ne lui posait de rang, et la ligne de garde ne
    gardait donc rien d'observable. Une ligne qu'aucune faute ne peut
    faire rougir est soit morte, soit non tenue — ici elle est vivante,
    et voici ce qu'elle tient : une ligne qui arrive AVEC un rang (un
    second passage sur les mêmes objets, un lot futur qui préremplit)
    doit repartir sans. Sans elle, la case dirait « écartée » et
    porterait quand même son numéro de podium.
    """
    print("── lot L18 : le rang périmé du témoin est bien effacé ──")
    key = ("b1:valley", 24, "basin_landform")
    rows = [
        {"model": "icon_d2", "typical_err_kmh": 5.0, "occurrences": 90,
         "typical_err_kmh_corr": 5.0, "n_corr": 90},
        {"model": J.AGRUME_PI_MODEL, "typical_err_kmh": 4.0, "occurrences": 90,
         "typical_err_kmh_corr": 4.0, "n_corr": 90},
        # ⭐ LE TÉMOIN ARRIVE AVEC UN RANG — celui qu'il tenait
        # légitimement avant que le composite n'entre dans la case.
        {"model": J.AGRUME_MODEL, "typical_err_kmh": 3.0, "occurrences": 90,
         "typical_err_kmh_corr": 1.0, "n_corr": 90,
         "rank": 1, "rank_corr": 1, "rank_reason": "ok",
         "rank_reason_corr": "ok"},
    ]
    jours = [f"2026-08-{d:02d}" for d in range(1, 16)]
    rbcm = {m: [{"day": j, "unit": f"p:{u}", "err_vec_med": e,
                 "err_vec_med_corr": ec}
                for j in jours for u in range(6)]
            for m, e, ec in (("icon_d2", 5.0, 5.0),
                             (J.AGRUME_PI_MODEL, 4.0, 4.0),
                             (J.AGRUME_MODEL, 3.0, 1.0))}
    J._apply_rank({key: rows}, {key: rbcm})
    temoin = rows[2]
    check("⭐⭐ le rang que le témoin portait EN ENTRANT est effacé, pas "
          "seulement « non attribué »", temoin["rank"], None)
    check("… et son rang corrigé aussi", temoin["rank_corr"], None)
    check("… et les deux motifs disent `serie_temoin`",
          (temoin["rank_reason"], temoin["rank_reason_corr"]),
          (J.RANK_REASON_SERIE_TEMOIN, J.RANK_REASON_SERIE_TEMOIN))
    check("le composite prend la 1re place", rows[1]["rank"], 1)


# ══════════════════════════════════════════════════════════════════
#  LOT L10 (30/08/2026) — LA CLASSE COURTE, CÔTÉ SCORING
# ══════════════════════════════════════════════════════════════════
#
# ⛔ Le collecteur a son propre banc (`test_agrume_court.py`). Ici on
# tient les TROIS choses que `score.py` doit faire de ses lignes :
#   · les noter sous LEUR échéance, pas sous celle du snapshot ;
#   · ne JAMAIS leur donner de rang, sans tomber pour autant ;
#   · les tenir hors des événements, qui se comptent sur une journée.

def _ligne_courte(station, model, lead, jour, fetched_h=6):
    """Une ligne de la classe courte : six heures, et rien d'autre."""
    row = fcst_line(station, model, jour, lambda i: brise(i % 24))
    for i in range(len(row["speed"])):
        # Les heures cibles de T = 06:50 Z : 07…12 Z, et elles seules.
        if not 7 <= i <= 12:
            row["speed"][i] = None
            row["dir"][i] = None
    row["lead_h"] = lead
    # Q5 — la fraîcheur du MODÈLE : l'heure du run PI (06 Z), donc une
    # échéance moyenne de 3,5 h sur les heures 07…12.
    row["fetched_at"] = jour.replace(hour=fetched_h, minute=0,
                                     tzinfo=timezone.utc).isoformat()
    return row


def test_l10_la_ligne_porte_son_echeance():
    """Lot L10 — une ligne qui déclare `lead_h` est notée SOUS CE
    `lead_h`, pas sous celui que l'écart de jours ferait deviner.
    """
    print("── lot L10 : l'échéance vient de la ligne, pas de l'offset ──")
    snapshots = {
        0: [fcst_line("835", "icon_d2", DAY, lambda i: brise(i % 24),
                      aloft=(40.0, 350.0)),
            _ligne_courte("835", J.AGRUME_COURT_W1, J.LEAD_COURT_MATIN, DAY),
            _ligne_courte("835", J.AGRUME_COURT_W05, J.LEAD_COURT_MATIN, DAY)],
    }
    obs_j = [obs_line("835", DAY, brise)]
    obs_v = [obs_line("835", DAY - timedelta(days=1), brise)]
    rows, _ = J.daily_rows(DAY, snapshots, obs_j, obs_v, utc_offset_s=7200)
    par = {r["model"]: r for r in rows}
    check("⭐ la sous-série w=1 est notée sous l'étiquette de la classe "
          "courte, PAS sous « +6 h »",
          par[J.AGRUME_COURT_W1]["lead_h"], J.LEAD_COURT_MATIN)
    check("… la sous-série w=0,5 aussi",
          par[J.AGRUME_COURT_W05]["lead_h"], J.LEAD_COURT_MATIN)
    check("⛔ et `icon_d2`, qui ne déclare rien, garde le +6 h de "
          "l'offset — le comportement d'avant le lot ne bouge pas",
          par["icon_d2"]["lead_h"], 6)
    check("la classe courte ne note que ses SIX heures",
          par[J.AGRUME_COURT_W1]["n_hours"], 6)
    check("⭐ son échéance réelle moyenne vaut 3,5 h — les heures 07…12 "
          "vues depuis le run PI de 06 Z (Q5 : fraîcheur du MODÈLE)",
          abs(par[J.AGRUME_COURT_W1]["lead_exact_h"] - 3.5) < 0.35,
          True)

    # ⛔ ET LA MÉMOIRE DU CARACTÈRE RESTE INTACTE. `banded` alimente
    # `model_character`, une moyenne exponentielle de trois mois : deux
    # sous-séries encore en essai n'y écrivent rien.
    _, banded = J.daily_rows(DAY, snapshots, obs_j, obs_v, utc_offset_s=7200)
    check("⛔ aucune ligne de la classe courte dans les accumulateurs de "
          "caractère", [b for b in banded if b["lead_h"] in J.LEADS_COURTS],
          [])
    check("⭐ … alors que `icon_d2`, lui, y est bien (le banc n'est pas "
          "vide)", any(b["model"] == "icon_d2" for b in banded), True)


def test_l10_notees_jamais_classees():
    """Lot L10 — les deux sous-séries sont NOTÉES et jamais CLASSÉES,
    et une case où plus personne n'est admis ne fait pas tomber la nuit.
    """
    print("── lot L10 : notées, jamais classées ──")
    zone_of = {f"pioupiou:{i}": {"zone_id": "b1:valley", "landform": "valley",
                                 "basin_id": "b1", "massif_id": "alpes-nord",
                                 "basin_uncertain": False}
               for i in range(830, 836)}
    daily = []
    for j in range(15):
        d = (DAY - timedelta(days=j)).strftime("%Y-%m-%d")
        for i in range(830, 836):
            for model, err in ((J.AGRUME_COURT_W1, 3.0),
                               (J.AGRUME_COURT_W05, 4.0)):
                daily.append({
                    "day": d, "source": "pioupiou", "station_id": str(i),
                    "model": model, "lead_h": J.LEAD_COURT_MATIN,
                    "regime": "fluxN", "n_hours": 6, "err_vec_med": err,
                    "mse_model": err * err, "mse_persist": 100.0})
    # ⛔ LE CAS QUI AURAIT FAIT TOMBER LA NUIT : les DEUX séries de la
    # case sont écartées, donc `admis` est vide. Sans le garde-fou, on
    # demanderait à `rank_models` de classer une liste vide.
    rows = J.rolling_scores(daily, zone_of, DAY)
    fine = [r for r in rows if r["zone_id"] == "b1:valley"
            and r["window_kind"] == "rolling15"]
    check("les deux sous-séries ont bien leur ligne (elles sont NOTÉES)",
          sorted(r["model"] for r in fine),
          sorted([J.AGRUME_COURT_W1, J.AGRUME_COURT_W05]))
    par = {r["model"]: r for r in fine}
    check("⭐ w=1 porte son erreur typique (3,0 km/h) — la feuille de "
          "fiabilité peut la lire",
          par[J.AGRUME_COURT_W1]["typical_err_kmh"], 3.0)
    check("… et w=0,5 la sienne (4,0)",
          par[J.AGRUME_COURT_W05]["typical_err_kmh"], 4.0)
    check("⛔ AUCUN rang, alors que w=1 bat w=0,5 de 25 %",
          [par[m]["rank"] for m in (J.AGRUME_COURT_W1, J.AGRUME_COURT_W05)],
          [None, None])
    check("… et le motif dit « en essai », pas « doublon » ni « témoin »",
          {par[m]["rank_reason"] for m in par}, {"serie_en_essai"})
    check("le classement CORRIGÉ dit la même chose sur la même case",
          {par[m]["rank_reason_corr"] for m in par}, {"serie_en_essai"})
    check("l'échéance publiée est celle de la classe courte",
          {r["lead_h"] for r in fine}, {J.LEAD_COURT_MATIN})


def test_l10_les_evenements_ignorent_la_classe_courte():
    """Lot L10 — six heures autour d'un instant de décision ne font pas
    une journée : la classe courte ne produit pas d'événements.
    """
    print("── lot L10 : la classe courte ne produit pas d'événements ──")
    zone_of = {f"pioupiou:{i}": {"zone_id": "b1:valley", "landform": "valley",
                                 "basin_id": "b1", "massif_id": "alpes-nord",
                                 "basin_uncertain": False}
               for i in ("835", "836")}

    def monte(h):
        return 2.0 if h < 10 else 25.0

    snapshots = {0: []}
    for st in ("835", "836"):
        snapshots[0].append(fcst_line(st, "icon_d2", DAY,
                                      lambda i: monte(i % 24)))
        court = fcst_line(st, J.AGRUME_COURT_W1, DAY, lambda i: monte(i % 24))
        court["lead_h"] = J.LEAD_COURT_MATIN
        snapshots[0].append(court)
    obs_j = [obs_line(st, DAY, monte) for st in ("835", "836")]

    rows, _ = J.event_rows(DAY, snapshots, obs_j, zone_of, 7200)
    modeles = {r["model"] for r in rows}
    check("⭐ le banc n'est pas vide : `icon_d2` produit bien des "
          "événements sur cette matière", "icon_d2" in modeles, True)
    check("⛔ et la classe courte, sur EXACTEMENT le même vent, n'en "
          "produit aucun", J.AGRUME_COURT_W1 in modeles, False)


def test_l10_on_ne_classe_pas_une_case_vide():
    """Lot L10 — une case dont TOUTES les séries sont écartées n'est
    jamais soumise au test apparié.

    ⛔ POURQUOI CE BANC EXISTE, ET IL A UNE HISTOIRE COURTE. La
    mutation nº 11 du 30/08 (retirer le garde-fou `if not admis`)
    laissait le banc VERT : `rank_models` accepte une liste vide sans
    broncher, et les motifs d'exclusion sont posés juste après de toute
    façon. La ligne ne gardait donc rien d'OBSERVABLE dans la sortie —
    or ce qu'elle garde n'est pas une valeur, c'est un GESTE : on ne
    pose pas une question à un test quand il n'y a personne à comparer.
    Un jour où `rank_models` lèvera sur une liste vide (ou rendra un
    verdict poli sur rien du tout), c'est la nuit entière qui tombera
    pour une case que personne ne publie. On tient donc l'appel.
    """
    print("── lot L10 : on ne soumet jamais une case vide au test ──")
    zone_of = {f"pioupiou:{i}": {"zone_id": "b1:valley", "landform": "valley",
                                 "basin_id": "b1", "massif_id": "alpes-nord",
                                 "basin_uncertain": False}
               for i in range(830, 836)}
    daily = []
    for j in range(15):
        d = (DAY - timedelta(days=j)).strftime("%Y-%m-%d")
        for i in range(830, 836):
            # La case COURTE : deux séries, toutes deux en essai.
            for model, err in ((J.AGRUME_COURT_W1, 3.0),
                               (J.AGRUME_COURT_W05, 4.0)):
                daily.append({
                    "day": d, "source": "pioupiou", "station_id": str(i),
                    "model": model, "lead_h": J.LEAD_COURT_MATIN,
                    "regime": "fluxN", "n_hours": 6, "err_vec_med": err,
                    "mse_model": err * err, "mse_persist": 100.0})
            # ⭐ Et une case ORDINAIRE à côté, pour que ce banc ne
            # puisse pas être vert en ne mesurant rien du tout.
            for model, err in (("icon_d2", 3.0),
                               ("meteofrance_arome_france_hd", 5.0)):
                daily.append({
                    "day": d, "source": "pioupiou", "station_id": str(i),
                    "model": model, "lead_h": 6, "regime": "fluxN",
                    "n_hours": 12, "err_vec_med": err,
                    "mse_model": err * err, "mse_persist": 100.0})

    appels = []
    vrai = J.INF.rank_models

    def espion(cases, *a, **kw):
        appels.append(list(cases))
        return vrai(cases, *a, **kw)

    J.INF.rank_models = espion
    try:
        J.rolling_scores(daily, zone_of, DAY)
    finally:
        J.INF.rank_models = vrai

    check("⭐ le banc n'est pas vide : des cases NON vides ont bien été "
          "soumises au test", any(appels), True)
    check("⛔ et AUCUNE case vide ne l'a été",
          [c for c in appels if not c], [])


def test_l10_le_lead_refuse_ecarte_les_lignes_pas_la_nuit():
    """Lot L10 — un `lead_h` que la base ne connaît pas encore écarte
    les lignes de la classe courte, jamais la nuit entière.

    ⛔ DEUX PRÉCÉDENTS EXACTS, ET ILS ONT COÛTÉ DEUX NUITS. Le lot G a
    ajouté trois `rank_reason` refusées ; le lot L2 en a ajouté une dans
    la colonne corrigée. Les deux fois, un HTTP 400 a emporté la nuit
    entière. Ici c'est pire sur le papier : `lead_h` est dans la CLÉ
    PRIMAIRE, donc on ne peut pas le taire — on écarte les lignes.
    ⚠️ Ce banc existe parce que le job `agrume_court` peut être lancé À
    LA MAIN avant que Yann n'ait joué `supabase_step62`. « Le timer
    n'est pas installé » n'est pas une protection.
    """
    print("── lot L10 : un lead refusé n'emporte pas la nuit ──")
    import contextlib, io as _io
    def _lignes():
        return [{"day": "2026-08-29", "source": "pioupiou",
                 "station_id": "835", "model": "icon_d2", "lead_h": 6,
                 "fcst_src": "own_archive"},
                {"day": "2026-08-29", "source": "pioupiou",
                 "station_id": "835", "model": "icon_d2", "lead_h": 24,
                 "fcst_src": "own_archive"},
                {"day": "2026-08-29", "source": "pioupiou",
                 "station_id": "835", "model": J.AGRUME_COURT_W1,
                 "lead_h": J.LEAD_COURT_MATIN, "fcst_src": "own_archive"},
                {"day": "2026-08-29", "source": "pioupiou",
                 "station_id": "835", "model": J.AGRUME_COURT_W05,
                 "lead_h": J.LEAD_COURT_APREM, "fcst_src": "own_archive"}]

    rows = _lignes()
    sb = _SbRefuse(["model_verif_daily_lead_h_check"])
    with contextlib.redirect_stderr(_io.StringIO()) as err:
        n = J._upsert_daily(sb, rows)
    check("⭐ la nuit passe : les deux classes d'horizon sont écrites",
          n, 2)
    envoyees = [r["lead_h"] for r in sb.appels[-1]]
    check("… et ce sont bien celles-là", sorted(envoyees), [6, 24])
    check("⛔ les lignes de la classe courte sont ÉCARTÉES, pas tues — "
          "`lead_h` est dans la clé primaire",
          [r for r in sb.appels[-1] if r["lead_h"] < 0], [])
    check("deux tentatives d'upsert, pas une", len(sb.appels), 2)
    check("le journal nomme le `.sql` à jouer",
          "supabase_step62_lot_l10_classe_courte.sql" in err.getvalue(), True)
    check("… et dit COMBIEN de lignes ont été écartées",
          "2 ligne(s) ÉCARTÉE(S)" in err.getvalue(), True)

    # ⛔ UNE CONTRAINTE QU'ON NE SAIT PAS DÉSARMER PASSE À TRAVERS —
    # un repli qui avale tout ferait disparaître les vraies pannes.
    try:
        J._upsert_daily(_SbRefuse(["model_verif_daily_pkey"]), _lignes())
        check("une contrainte inconnue doit RE-LEVER", "passé", "Abort")
    except J.Abort as exc:
        check("une contrainte inconnue re-lève telle quelle",
              "model_verif_daily_pkey" in str(exc), True)

    # ⛔ ET SI TOUT EST REFUSÉ, ON LÈVE. Un upsert vide « réussirait »
    # en écrivant zéro ligne, et la nuit se croirait passée.
    seules = [r for r in _lignes() if r["lead_h"] < 0]
    try:
        with contextlib.redirect_stderr(_io.StringIO()):
            J._upsert_daily(_SbRefuse(["model_verif_daily_lead_h_check"]),
                            seules)
        check("un lot ENTIÈREMENT refusé doit lever", "passé", "Abort")
    except J.Abort:
        check("⛔ un lot entièrement refusé lève — un upsert vide se "
              "lirait comme une nuit réussie", True, True)


def test_repli_rang_les_deux_ensembles_admis_disent_le_schema_reel():
    print("── repli : ce que chaque CHECK admet vraiment ──")
    # ⛔ CES DEUX ENSEMBLES SONT UNE LECTURE DU SCHÉMA, pas un choix de
    # code : les élargir « au cas où » ferait taire une raison que la
    # base accepte, ou laisser passer une raison qu'elle refuse — et
    # dans ce second cas la nuit retombe.
    check("le CHECK brut (step40) n'admet PAS `duplicate_chain`",
          "duplicate_chain" in J.RANK_REASONS_STEP40, False)
    check("le CHECK brut n'admet PAS `fdr`",
          "fdr" in J.RANK_REASONS_STEP40, False)
    check("le CHECK brut n'admet PAS `single_model` (step42 est un "
          "fichier à part)", "single_model" in J.RANK_REASONS_STEP40, False)
    check("le CHECK corrigé (step52) admet `mixed_population`",
          "mixed_population" in J.RANK_REASONS_CORR_STEP52, True)
    check("… et `single_model`",
          "single_model" in J.RANK_REASONS_CORR_STEP52, True)
    check("… mais PAS `duplicate_chain` : c'est toute l'affaire du 28/08",
          "duplicate_chain" in J.RANK_REASONS_CORR_STEP52, False)
    check("… ni `fdr`", "fdr" in J.RANK_REASONS_CORR_STEP52, False)
    # ⛔ LOT L18 — ET LA QUESTION S'EST VRAIMENT POSÉE LE 30/08, quand
    # Yann a joué `supabase_step61_lot_l18_agrume_unique.sql` : fallait-il
    # basculer ces deux lignes à True ? NON, et pour la raison écrite au
    # pavé de `RANK_REASONS_STEP40` : ce set n'est PAS « ce que la base
    # accepte aujourd'hui », c'est la BASELINE du step40. `single_model`
    # est joué depuis le step42 et n'y est pas davantage. Les élargir
    # rendrait le repli d'`_upsert_scores` inopérant le jour où une de
    # ces valeurs serait vraiment refusée — c'est-à-dire exactement
    # quand on en a besoin. Ils restent donc à False, et c'est un choix,
    # pas un retard.
    check("le CHECK de RÉFÉRENCE (step40) n'admet pas `serie_temoin` — "
          "le step61 est joué, mais ce set est la baseline, comme pour "
          "`single_model`", "serie_temoin" in J.RANK_REASONS_STEP40, False)
    check("… ni celui du corrigé (step52)",
          "serie_temoin" in J.RANK_REASONS_CORR_STEP52, False)
    check("les deux CHECK sont couverts par un repli",
          sorted(p[0] for p in J.REPLIS_RANG),
          ["model_score_zone_rank_reason_check",
           "model_score_zone_rank_reason_corr_check"])
    check("chaque repli vise sa PROPRE colonne",
          [p[1] for p in J.REPLIS_RANG],
          ["rank_reason", "rank_reason_corr"])



# ══════════════════════════════════════════════════════════════════
#  LA MÉMOIRE DU RUN (28/08/2026) — après l'OOM de la nuit du 28
# ══════════════════════════════════════════════════════════════════
#
# ⛔ CE QU'ON TIENT ICI ET CE QU'ON NE TIENT PAS. Un banc ne peut pas
# mesurer 497 Mo relâchés au milieu d'un `main()` de six cents lignes
# qui parle à Supabase et à R2 — et un banc qui prétendrait le faire
# mentirait sur un Mac, où `/proc` n'existe pas. On tient donc DEUX
# choses, séparément :
#   · que l'INSTRUMENT est juste (il lit des Mo, il crie au bon
#     moment, et il suit une allocation réelle là où `/proc` existe) ;
#   · que l'ORDRE est juste — chaque bloc mort est relâché AVANT la
#     phase qui l'écrasait. C'est une lecture de la SOURCE, assumée
#     comme telle : c'est l'ordre, et rien d'autre, qui a tué la nuit
#     du 28/08. Le chiffre, lui, se lit sur le VPS, dans les jalons
#     que ce même lot écrit dans le journal.


def test_memoire_le_jalon_dit_les_mo_et_crie_au_dessus_du_seuil():
    print("── mémoire : le jalon (28/08) ──")
    import io, contextlib
    sortie = io.StringIO()
    with contextlib.redirect_stdout(sortie):
        mo = J.jalon_memoire("un essai", seuil_mo=2800.0, rss=lambda: 1234.0)
    check("le jalon rend les Mo lus", mo, 1234.0)
    check("sous le seuil, la ligne est calme et va sur stdout",
          "ⓘ mémoire après un essai : 1234 Mo" in sortie.getvalue(), True)
    check("sous le seuil, aucun cri", "⛔" in sortie.getvalue(), False)

    err = io.StringIO()
    out = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
        J.jalon_memoire("le rejeu", seuil_mo=2800.0, rss=lambda: 2900.0)
    check("au-dessus du seuil, la ligne part sur STDERR (c'est ce qui "
          "la fait remonter dans l'alerte)", "⛔" in err.getvalue(), True)
    check("… et pas sur stdout", out.getvalue(), "")
    check("le cri nomme le seuil franchi",
          "2800 Mo" in err.getvalue(), True)

    # ⚠️ Le seuil est un « strictement au-dessus » : à la valeur exacte,
    # on ne crie pas. Sinon un seuil rond crierait sur un run rond.
    # ⚠️ LES DEUX TUYAUX, ET C'EST LA LEÇON DE LA MUTATION nº 9 : ne
    # regarder que `stdout` laissait passer un `>=`, puisque le cri
    # part justement sur `stderr`. Un banc qui ne lit qu'une moitié de
    # la sortie tient une moitié de propriété.
    calme_out, calme_err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(calme_out), \
            contextlib.redirect_stderr(calme_err):
        J.jalon_memoire("pile", seuil_mo=2800.0, rss=lambda: 2800.0)
    check("pile sur le seuil : pas de cri (le seuil est un "
          "« strictement au-dessus », sinon un seuil rond crie sur un "
          "run rond)",
          "⛔" in calme_out.getvalue() + calme_err.getvalue(), False)
    check("pile sur le seuil : la ligne calme est quand même dite",
          "ⓘ mémoire après pile" in calme_out.getvalue(), True)

    check("hors Linux, le jalon se tait et rend None",
          J.jalon_memoire("ailleurs", rss=lambda: None), None)


def test_memoire_rss_lit_bien_vmrss_et_le_rend_en_mo():
    print("── mémoire : `_rss_mo` lit VmRSS, en Mo ──")
    import tempfile
    # Un `/proc/self/status` de laboratoire, aux ordres de grandeur du
    # VPS la nuit de l'OOM : VmPeak et VmRSS DIFFÈRENT, exprès.
    faux = ("Name:\tpython3" + chr(10) +
            "VmPeak:\t 3999999 kB" + chr(10) +
            "VmSize:\t 2928108 kB" + chr(10) +
            "VmHWM:\t  2900000 kB" + chr(10) +
            "VmRSS:\t  2883584 kB" + chr(10) +
            "Threads:\t1" + chr(10))
    with tempfile.NamedTemporaryFile("w", suffix=".status",
                                     delete=False, encoding="ascii") as f:
        f.write(faux)
        chemin = f.name
    check("2 883 584 ko se lisent 2 816 Mo (division par 1024, pas par "
          "1000, et surtout pas rien)", J._rss_mo(chemin), 2816.0, tol=1e-9)
    check("c'est bien VmRSS qui est lu, pas VmPeak — sinon un bloc "
          "relâché ne se verrait JAMAIS entre deux jalons",
          J._rss_mo(chemin) < 3000.0, True)
    check("un fichier absent ne fait pas tomber le run",
          J._rss_mo(chemin + ".nexistepas"), None)
    os.unlink(chemin)


def test_memoire_rss_suit_une_allocation_reelle():
    print("── mémoire : `_rss_mo` suit une allocation réelle ──")
    avant = J._rss_mo()
    if avant is None:
        # ⓘ Pas un échec : `/proc/self/status` n'existe pas sur macOS,
        # et le banc doit rester jouable sur la machine de dev. Le dire
        # plutôt que de compter une assertion verte pour rien.
        print("     ⓘ /proc indisponible (macOS ?) — épreuve sautée, "
              "elle se joue sur le VPS.")
        return
    bloc = bytearray(120 * 1024 * 1024)     # 120 Mo, touchés page à page
    for i in range(0, len(bloc), 4096):
        bloc[i] = 1
    pendant = J._rss_mo()
    check("120 Mo alloués et touchés se voient (au moins 90 Mo de plus)",
          pendant - avant > 90.0, True)
    del bloc
    check("l'unité est bien le Mo, pas le ko (un run de notation ne "
          "tient pas dans 3 Mo et n'atteint pas 3 000 000)",
          1.0 < pendant < 100000.0, True)


def test_memoire_les_blocs_morts_sont_relaches_avant_le_chemin_regime():
    print("── mémoire : l'ordre des oublis dans `main` (28/08) ──")
    src = pathlib.Path(J.__file__).read_text(encoding="utf-8")
    src = src[src.index("def main() -> int:"):]

    def pos(motif, quoi):
        check(f"`{quoi}` est présent dans `main`", motif in src, True)
        return src.index(motif) if motif in src else 10 ** 9

    # ⛔ LA FENÊTRE GLISSANTE (497 Mo sondés le 28/08) doit mourir entre
    # son dernier lecteur et le rejeu d'archive. C'est LA ligne dont
    # l'absence a coûté la nuit du 28/08.
    p_roll = pos("scores = rolling_scores(daily, zone_of, as_of)", "rolling_scores")
    p_oubli = pos("        daily = None" + chr(10), "l'oubli de `daily`")
    p_replay = pos("units, bilan_replay = replay_window(", "replay_window")
    check("`daily` est relâché APRÈS son dernier lecteur", p_oubli > p_roll, True)
    check("… et AVANT le rejeu d'archive, qui est la phase qu'il "
          "écrasait", p_oubli < p_replay, True)

    # ⛔ LE CHEMIN J-0 (snapshots, observations, climatologie, agrégats)
    # doit mourir avant la fenêtre glissante ET avant le rejeu.
    p_j0 = pos("        n_prior, n_clim = len(prior), len(clim)" + chr(10),
               "l'oubli du chemin J-0")
    p_daily = pos('daily = sb.select("model_verif_daily"', "lecture de la fenêtre")
    check("le chemin J-0 est oublié avant la lecture de la fenêtre "
          "glissante", p_j0 < p_daily, True)
    for nom in ("snapshots", "obs_day", "obs_prev", "clim", "prior",
                "banded", "poids_comb"):
        check(f"`{nom}` est bien relâché", f"{nom} = " in
              src[p_j0:p_j0 + 400] or f"= {nom} =" in src[p_j0:p_j0 + 400]
              or f"{nom} =" in src[p_j0:p_j0 + 400], True)

    # ⛔ ET LES COMPTES SURVIVENT AUX TABLES : `_publish` lit `n_prior` /
    # `n_clim`, jamais `len(prior)` / `len(clim)` — qui lèveraient
    # `TypeError` sur `None` et feraient tomber la publication.
    check("le méta publie `n_prior` et non `len(prior)`",
          '"pairs_with_prior": n_prior,' in src, True)
    check("le méta publie `n_clim` et non `len(clim)`",
          '"climatology_stations": n_clim,' in src, True)
    check("plus aucun `len(prior)` après l'oubli",
          "len(prior)" in src[p_j0 + 200:], False)
    check("plus aucun `len(clim)` après l'oubli",
          "len(clim)" in src[p_j0 + 200:], False)

    # ⓘ Et le ramasse-miettes est appelé : sans lui, les cycles de
    # références (une ligne qui pointe sa case, une case qui liste ses
    # lignes) survivraient au `= None`.
    check("`gc.collect()` suit chaque oubli",
          src.count("gc.collect()") >= 3, True)

    # ⓘ Enfin, les jalons — NOMMÉS UN PAR UN, et c'est la leçon de la
    # mutation nº 10 : un simple compte laissait retirer celui du rejeu
    # d'archive, c'est-à-dire l'étape exacte où le run est mort. Ce sont
    # des étapes précises qu'on veut voir, pas un nombre.
    for etape in ("la relecture de l'archive",
                  "l'agrégat quotidien (chemin J-0)",
                  "l'oubli du chemin J-0",
                  "l'oubli de la fenêtre glissante",
                  "le rejeu d'archive",
                  "le score par régime",
                  "l'oubli de la fenêtre rejouée"):
        check(f"le run jalonne sa mémoire après « {etape} »",
              f'jalon_memoire("{etape}")' in src, True)



# ══════════════════════════════════════════════════════════════════
#  FABRIQUE D'ARCHIVE — la forme EXACTE que `collect.py` écrit
# ══════════════════════════════════════════════════════════════════

def fcst_line(station_id, model, emitted: datetime, speed_at,
              dir_deg=200.0, hours=72, aloft=None):
    """Une ligne de `fcst_YYYY-MM-DD.ndjson.gz`."""
    t0 = int(emitted.replace(hour=0, minute=0, second=0,
                             tzinfo=timezone.utc).timestamp())
    row = {
        "station_id": station_id, "source": "pioupiou",
        "lat": 45.22, "lon": 6.60, "model": model,
        "fetched_at": emitted.replace(tzinfo=timezone.utc).isoformat(),
        "t0": t0, "step_s": 3600,
        "speed": [speed_at(i) for i in range(hours)],
        "dir": [dir_deg] * hours,
        "gust": [None] * hours,
    }
    if aloft is not None:
        row["aloft_level"] = "850hPa"
        row["aloft_speed"] = [aloft[0]] * hours
        row["aloft_dir"] = [aloft[1]] * hours
    return row


def obs_line(station_id, day: datetime, speed_at, dir_deg=200.0, cadence_s=240):
    """Une ligne de `obs_YYYY-MM-DD.ndjson.gz`, cadence Pioupiou."""
    t0 = int(day.replace(tzinfo=timezone.utc).timestamp()) - 40 * 60
    n = (24 * 3600 + 80 * 60) // cadence_s
    t = [t0 + i * cadence_s for i in range(n)]
    return {"station_id": station_id, "source": "pioupiou",
            "lat": 45.22, "lon": 6.60, "t": t,
            "speed": [speed_at((ts - int(day.replace(tzinfo=timezone.utc)
                                         .timestamp())) / 3600) for ts in t],
            "gust": [None] * n,
            "dir": [dir_deg] * n}


def brise(h):
    """Cycle de brise : nul la nuit, maximum vers 15 h."""
    return round(34.0 * max(0.0, math.sin((h - 6) / 12 * math.pi)), 3)


# ══════════════════════════════════════════════════════════════════

def test_chaine_de_repli():
    print("── chaîne de repli (§16.3) ──")
    z = {"zone_id": "b45.28_6.51:valley", "landform": "valley",
         "basin_id": "b45.28_6.51", "massif_id": "alpes-nord"}
    check("cinq échelons, du bassin au réseau entier",
          J.fallback_chain(z),
          [("b45.28_6.51:valley", "basin_landform"),
           ("alpes-nord:valley", "massif_landform"),
           ("*:valley", "landform"),
           ("alpes-nord:*", "massif"),
           ("*:*", "global")])
    # La forme AVANT le massif : un fond de vallée est mal résolu par
    # une maille de 1,3 km dans les Pyrénées comme dans les Alpes.
    niveaux = [lvl for _, lvl in J.fallback_chain(z)]
    check("« cette forme partout » passe avant « ce massif »",
          niveaux.index("landform") < niveaux.index("massif"), True)

    sans_bassin = {"zone_id": "alpes-nord:valley", "landform": "valley",
                   "basin_id": None, "massif_id": "alpes-nord"}
    check("sans bassin, la case fine retombe sur massif:forme sans doublon",
          J.fallback_chain(sans_bassin),
          [("alpes-nord:valley", "massif_landform"),
           ("*:valley", "landform"),
           ("alpes-nord:*", "massif"),
           ("*:*", "global")])
    # ⚠️ Et elle s'ANNONCE massif_landform, pas basin_landform. Le
    # contraire (défaut corrigé le 08/08) faisait publier un score
    # `agg_level = 'basin_landform'` sur une zone dont `model_zone.kind`
    # dit `massif_landform` : le score mentait sur sa propre précision,
    # ce que la colonne `agg_level` existe pour empêcher.
    check("… et la case fine ne se fait pas passer pour un bassin",
          J.fallback_chain(sans_bassin)[0][1], "massif_landform")

    hors_massif = {"zone_id": "b48.1_2.3:plain", "landform": "plain",
                   "basin_id": "b48.1_2.3", "massif_id": None}
    check("hors de tout massif, trois échelons seulement",
          J.fallback_chain(hors_massif),
          [("b48.1_2.3:plain", "basin_landform"),
           ("*:plain", "landform"), ("*:*", "global")])

    # Ni bassin ni massif : `assignZone` rend `*:forme` depuis le 08/08
    # (il rendait `hors-zone:forme`, un identifiant que personne
    # n'insérait — donc une balise que la clé étrangère refusait).
    ni_l_un_ni_l_autre = {"zone_id": "*:slope", "landform": "slope",
                          "basin_id": None, "massif_id": None}
    check("ni bassin ni massif : la case fine EST « cette forme, partout »",
          J.fallback_chain(ni_l_un_ni_l_autre),
          [("*:slope", "landform"), ("*:*", "global")])


#: Les sept lignes que `supabase_step35_model_verification.sql` sème une
#: fois pour toutes. Recopiées ici parce que le banc ne touche pas la
#: base : si le SQL en ajoute une, cette liste doit suivre, et l'oubli
#: se voit tout de suite sur l'assertion d'inclusion ci-dessous.
SEMEES_PAR_LE_SQL = {"*:valley", "*:slope", "*:ridge", "*:plateau",
                     "*:plain", "*:coastal", "*:*"}

#: Les CHECK de step35, à la lettre (l. 169 et 177). Un `kind` inventé
#: passe le typage Python et échoue en base : c'est ici qu'il doit
#: mourir, pas à 05 h 58.
KINDS_SQL = {"basin_landform", "massif_landform", "landform", "massif",
             "global"}
LANDFORMS_SQL = {"valley", "slope", "ridge", "plateau", "plain", "coastal"}


class _SupabaseFactice:
    """Enregistre l'ordre des écritures. Ne parle à personne."""

    def __init__(self):
        self.appels: list[tuple] = []

    def upsert(self, table, rows, on_conflict, chunk=500):
        self.appels.append((table, on_conflict, len(rows)))
        return len(rows)


def test_lignes_de_zone():
    print("── qui crée les lignes model_zone (lot B) ──")
    # Les quatre cas possibles, pas les trois qu'on croit : le bassin et
    # le massif sont absents INDÉPENDAMMENT l'un de l'autre.
    cas = [
        {"source": "pioupiou", "station_id": "1", "zone_id": "b45.28_6.51:valley",
         "landform": "valley", "basin_id": "b45.28_6.51",
         "massif_id": "alpes-nord"},
        {"source": "pioupiou", "station_id": "2", "zone_id": "b48.1_2.3:plain",
         "landform": "plain", "basin_id": "b48.1_2.3", "massif_id": None},
        {"source": "pioupiou", "station_id": "3", "zone_id": "alpes-nord:valley",
         "landform": "valley", "basin_id": None, "massif_id": "alpes-nord"},
        {"source": "pioupiou", "station_id": "4", "zone_id": "*:slope",
         "landform": "slope", "basin_id": None, "massif_id": None},
    ]

    # ── l'identifiant que construit l'affectation est celui que la
    #    balise portera : sans ça, la clé étrangère refuserait la ligne.
    for z in cas:
        check(f"zone_id_for reconstruit {z['zone_id']}",
              J.zone_id_for(z), z["zone_id"])

    # ── échelon 1 : qui produit quoi ──
    check("bassin connu → une ligne basin_landform à créer",
          (J.zone_row_for(cas[0])["kind"], J.zone_row_for(cas[0])["basin_id"]),
          ("basin_landform", "b45.28_6.51"))
    check("bassin connu hors massif → basin_landform quand même",
          J.zone_row_for(cas[1])["kind"], "basin_landform")
    check("bassin nul, massif connu → massif_landform, pas basin_landform",
          J.zone_row_for(cas[2])["kind"], "massif_landform")
    # ⚠️ `None` n'est pas un échec : la ligne existe déjà, semée par le
    # SQL. Créer un doublon serait le vrai défaut.
    check("ni bassin ni massif → rien à créer, le SQL a déjà semé *:forme",
          J.zone_row_for(cas[3]), None)
    check("… et l'identifiant visé est bien l'un des sept semés",
          cas[3]["zone_id"] in SEMEES_PAR_LE_SQL, True)

    # ── `agg_level` et `kind` ne peuvent plus se contredire ──
    for z in cas:
        row = J.zone_row_for(z)
        kind = row["kind"] if row else "landform"
        check(f"agg_level == model_zone.kind pour {z['zone_id']}",
              J.fallback_chain(z)[0][1], kind)

    # ── L'ASSERTION QUI PROTÈGE VRAIMENT ──
    # Pas « zone_rows_needed rend deux lignes » : celle-là resterait
    # verte le jour où un sixième échelon apparaîtrait. L'ensemble des
    # zone_id de TOUTES les chaînes de repli doit être inclus dans
    # l'union des trois producteurs.
    produites = ({r["zone_id"] for r in J.zone_rows_for(cas)}
                 | {r["zone_id"] for r in J.zone_rows_needed(cas)}
                 | SEMEES_PAR_LE_SQL)
    attendues = {zid for z in cas for zid, _ in J.fallback_chain(z)}
    check("tout zone_id d'une chaîne de repli a un producteur",
          sorted(attendues - produites), [])
    # Et l'inverse est faux exprès : le SQL sème six formes dont on
    # n'utilise ici que trois. Un producteur peut créer plus que le
    # strict nécessaire, jamais moins.

    # ── les CHECK du SQL, honorés avant l'envoi ──
    for r in J.zone_rows_for(cas) + J.zone_rows_needed(cas):
        check(f"kind légal pour {r['zone_id']}", r["kind"] in KINDS_SQL, True)
        check(f"landform légale pour {r['zone_id']}",
              r.get("landform") is None or r["landform"] in LANDFORMS_SQL, True)
        check(f"libellé non vide pour {r['zone_id']}", bool(r["label"]), True)

    # ── ⚠️ LE JEU DE CLÉS, IDENTIQUE D'UNE LIGNE À L'AUTRE ──
    # Défaut trouvé le 08/08 sur le PREMIER run réel avec `station_zone`
    # peuplée : `massif:forme` portait `landform`, `massif:*` ne le
    # portait pas, et les 77 lignes partaient dans le même POST →
    # `PGRST102 — All object keys must match`, un 400 qui ne nomme ni la
    # clé ni la ligne. Le défaut existait depuis le lot B et ne pouvait
    # pas se déclencher tant que `station_zone` était vide : la liste
    # rendue était alors vide.
    #
    # On teste chaque producteur SÉPARÉMENT, parce que c'est par envoi
    # que PostgREST vérifie — et les deux ensemble, parce que la table
    # gagne à n'avoir qu'une seule forme de ligne.
    for nom, lot in (("zone_rows_for", J.zone_rows_for(cas)),
                     ("zone_rows_needed", J.zone_rows_needed(cas)),
                     ("les deux réunis",
                      J.zone_rows_for(cas) + J.zone_rows_needed(cas))):
        check(f"{nom} : un seul jeu de clés dans l'envoi",
              len({frozenset(r.keys()) for r in lot}), 1)
    check("et c'est bien le jeu de colonnes de model_zone",
          sorted(J.zone_rows_needed(cas)[0].keys()),
          ["basin_id", "kind", "label", "landform", "massif_id", "zone_id"])
    # ⚠️ Une clé à `None` DOIT être présente, pas omise : c'est
    # exactement ce que l'omission avait cassé.
    for r in J.zone_rows_needed(cas):
        check(f"{r['zone_id']} porte la clé landform même quand elle est nulle",
              "landform" in r, True)

    # ── … et le garde-fou qui le dit avant l'envoi ──
    # ⚠️ Le VRAI `Supabase`, pas la doublure : c'est son `upsert` qui
    # porte le garde-fou. `dry_run=True` lui évite d'exiger des secrets
    # et de parler au réseau, et le contrôle passe AVANT ce test-là.
    sb_garde = J.Supabase(dry_run=True)
    try:
        sb_garde.upsert("model_zone",
                        [{"zone_id": "a", "kind": "massif"},
                         {"zone_id": "b", "kind": "massif", "landform": "valley"}],
                        "zone_id")
        check("un envoi hétérogène est refusé AVANT le réseau", "accepté", "refusé")
    except J.Abort as exc:
        check("un envoi hétérogène est refusé AVANT le réseau", True, True)
        check("… et le message nomme la clé fautive", "landform" in str(exc), True)

    # ── dédoublonnage : deux balises d'une même vallée ──
    jumelle = dict(cas[0], station_id="5")
    rows = J.zone_rows_for(cas + [jumelle])
    check("deux balises du même bassin → une seule ligne model_zone",
          len(rows), len({r["zone_id"] for r in rows}))
    check("trois lignes d'échelon 1 pour quatre cas (la 4ᵉ est semée)",
          len(rows), 3)

    # ── L'ORDRE D'ÉCRITURE, qui n'est pas négociable ──
    sb = _SupabaseFactice()
    n_zone, n_stat = J.write_station_zones(sb, cas)
    check("model_zone est écrite AVANT station_zone",
          [t for t, _, _ in sb.appels], ["model_zone", "station_zone"])
    check("les deux écritures sont des upserts sur leur clé",
          [c for _, c, _ in sb.appels], ["zone_id", "source,station_id"])
    check("les quatre balises partent, y compris celle sans zone à créer",
          (n_zone, n_stat), (3, 4))

    # ── rejouable : un second passage écrit les mêmes lignes ──
    sb2 = _SupabaseFactice()
    check("relancer l'affectation ne change rien",
          J.write_station_zones(sb2, cas), (n_zone, n_stat))


def test_agregat_quotidien():
    print("── agrégat quotidien ──")
    # Trois snapshots : J (classe +6 h), J-1 (+24 h), J-2 (+48 h).
    # Le snapshot du jour J porte le vent d'altitude de référence.
    snapshots = {
        0: [fcst_line("835", "icon_d2", DAY, lambda i: brise(i % 24),
                      aloft=(40.0, 350.0)),
            fcst_line("835", "meteofrance_arome_france_hd", DAY,
                      lambda i: brise(i % 24) * 1.30)],
        1: [fcst_line("835", "icon_d2", DAY - timedelta(days=1),
                      lambda i: brise(i % 24))],
        2: [fcst_line("835", "icon_d2", DAY - timedelta(days=2),
                      lambda i: brise(i % 24))],
    }
    obs_j = [obs_line("835", DAY, brise)]
    obs_v = [obs_line("835", DAY - timedelta(days=1), lambda h: brise(h) * 0.5)]

    rows, banded = J.daily_rows(DAY, snapshots, obs_j, obs_v, utc_offset_s=7200)

    leads = sorted(r["lead_h"] for r in rows if r["model"] == "icon_d2")
    check("les trois classes d'échéance sont produites", leads, [6, 24, 48])

    r6 = next(r for r in rows if r["model"] == "icon_d2" and r["lead_h"] == 6)
    # Pas rigoureusement nulle, et c'est correct : l'observation est
    # une moyenne sur ±20 min d'un cycle courbe, la prévision une valeur
    # à l'heure pile. L'écart résiduel mesure la courbure, pas le modèle.
    check("un modèle qui rend l'observation a une erreur quasi nulle",
          r6["err_vec_med"] < 0.05, True)
    check("… et son échéance réelle moyenne est bien de l'ordre de 12 h",
          6 <= r6["lead_exact_h"] <= 18, True)

    r24 = next(r for r in rows if r["model"] == "icon_d2" and r["lead_h"] == 24)
    check("la classe +24 h a bien une échéance réelle d'environ 36 h",
          24 <= r24["lead_exact_h"] <= 48, True)
    r48 = next(r for r in rows if r["model"] == "icon_d2" and r["lead_h"] == 48)
    check("… et la classe +48 h, d'environ 60 h",
          48 <= r48["lead_exact_h"] <= 72, True)

    check("le régime vient du modèle de référence, pas du modèle noté "
          "(850 hPa 40 km/h de 350° → flux de nord)", r6["regime"], "fluxN")
    check("… et il est le MÊME pour tous les modèles de la journée",
          len({r["regime"] for r in rows}), 1)

    arome = next(r for r in rows
                 if r["model"] == "meteofrance_arome_france_hd")
    check("un modèle qui surestime de 30 % a un ratio observé/prévu de 0,77",
          round(arome["bias_ratio"], 2), 0.77)

    check("la veille était deux fois moins ventée → le modèle bat la "
          "persistance", r6["mse_model"] < r6["mse_persist"], True)

    # Le détail par tranche : c'est là que se joue « colle au vent
    # faible, écrête le vent fort » (§15.4).
    bandes = {b["band"] for b in banded if b["model"] == "icon_d2"}
    check("les tranches de vent sont bien séparées",
          bandes >= {"light", "moderate"}, True)
    check("chaque détail porte le régime de la journée",
          all(b["regime"] == "fluxN" for b in banded), True)

    # Une journée trop courte ne produit rien.
    court = {0: [fcst_line("835", "icon_d2", DAY,
                           lambda i: brise(i % 24) if i < 3 else None)]}
    rows2, _ = J.daily_rows(DAY, court, obs_j, obs_v, utc_offset_s=7200)
    check("3 heures appariées seulement → aucune ligne (bruit, pas donnée)",
          rows2, [])


def test_accumulateurs():
    print("── accumulateurs ──")
    # ⚠️ `basin_id` EST RENSEIGNÉ, comme dans une vraie ligne
    # `station_zone` : c'est lui qui dit à quel échelon appartient la
    # case fine. L'omettre ici ferait passer ces zones pour des zones de
    # massif — un banc qui invente ses entrées teste la fonction, pas
    # l'intégration.
    zone_of = {
        "pioupiou:835": {"zone_id": "b1:valley", "landform": "valley",
                         "basin_id": "b1", "massif_id": "alpes-nord",
                         "basin_uncertain": False},
        "pioupiou:836": {"zone_id": "b1:valley", "landform": "valley",
                         "basin_id": "b1", "massif_id": "alpes-nord",
                         "basin_uncertain": False},
        "pioupiou:999": {"zone_id": "b2:slope", "landform": "slope",
                         "basin_id": "b2", "massif_id": "alpes-nord",
                         "basin_uncertain": True},
        # Étape 42 (10/08) : coordonnées contredites par une source
        # indépendante — même exclusion que basin_uncertain, testée à
        # part pour ne pas dépendre du même chemin de code par hasard.
        "pioupiou:997": {"zone_id": "b3:ridge", "landform": "ridge",
                         "basin_id": "b3", "massif_id": "alpes-nord",
                         "basin_uncertain": False, "position_suspecte": True},
    }
    banded = [
        {"key": "pioupiou:835", "model": "icon_d2", "lead_h": 24,
         "regime": "fluxN", "band": "strong", "errKmh": 4.0,
         "speedRatio": 1.2, "dirOffset": 10.0,
         "mseModel": 20.0, "msePersist": 30.0},
        {"key": "pioupiou:836", "model": "icon_d2", "lead_h": 24,
         "regime": "fluxN", "band": "strong", "errKmh": 6.0,
         "speedRatio": 1.4, "dirOffset": 20.0,
         "mseModel": 24.0, "msePersist": 30.0},
        # Bassin indéterminé : cette balise ne doit peser nulle part.
        {"key": "pioupiou:999", "model": "icon_d2", "lead_h": 24,
         "regime": "fluxN", "band": "strong", "errKmh": 99.0,
         "speedRatio": 9.9, "dirOffset": 99.0,
         "mseModel": 99.0, "msePersist": 1.0},
        # Position suspecte : idem, ne doit peser nulle part.
        {"key": "pioupiou:997", "model": "icon_d2", "lead_h": 24,
         "regime": "fluxN", "band": "strong", "errKmh": 88.0,
         "speedRatio": 8.8, "dirOffset": 88.0,
         "mseModel": 88.0, "msePersist": 1.0},
        # ⛔ LOT S15 — UNE JOURNÉE DONT LE RÉGIME N'A PAS ÉTÉ CLASSÉ.
        # Posée sur un AUTRE modèle EXPRÈS : sur `icon_d2` elle
        # changerait les médianes des cas ci-dessus, et le banc
        # mesurerait deux choses à la fois sans le dire.
        {"key": "pioupiou:835", "model": "icon_eu", "lead_h": 24,
         "regime": "unknown", "band": "moderate", "errKmh": 7.0,
         "speedRatio": 1.1, "dirOffset": 5.0,
         "mseModel": 12.0, "msePersist": 15.0},
    ]
    up = J.accumulator_updates(banded, zone_of)
    par_cle = {(u["zone_id"], u["model"], u["regime"], u["band"], u["metric"]): u
               for u in up}

    fine = par_cle[("b1:valley", "icon_d2", "fluxN", "strong", "errKmh")]
    check("la valeur envoyée est la MÉDIANE des balises de la zone (4 et 6 → 5)",
          fine["x"], 5.0)
    # ⛔ LOT S15 — LA FORME DE LA LIGNE A CHANGÉ, et c'est le cœur du
    # lot : on n'envoie plus un ÉTAT (`sum_w`, `days`, `last_day`), on
    # envoie la valeur du jour. Si quelqu'un remet une de ces clés, la
    # RPC l'ignorera en silence et l'accumulateur repartira du mauvais
    # pied — d'où cette assertion sur ce qui NE DOIT PAS être là.
    check("… et rien d'autre : pas d'état absolu dans le corps envoyé",
          sorted(fine.keys()),
          ["band", "lead_h", "metric", "model", "regime", "x", "zone_id"])

    check("un bassin indéterminé n'entre dans AUCUNE case",
          any(u["zone_id"].startswith("b2") for u in up), False)
    check("une position suspecte n'entre dans AUCUNE case",
          any(u["zone_id"].startswith("b3") for u in up), False)
    check("… et sa valeur aberrante ne contamine pas le réseau entier",
          par_cle[("*:*", "icon_d2", "fluxN", "strong", "errKmh")]["x"], 5.0)

    check("les cinq échelons de repli sont alimentés d'un coup",
          sorted({u["zone_id"] for u in up}),
          ["*:*", "*:valley", "alpes-nord:*", "alpes-nord:valley", "b1:valley"])
    check("la case « toutes tranches » existe à côté des tranches",
          ("b1:valley", "icon_d2", "fluxN", "all", "errKmh") in par_cle, True)
    check("… et la case « tous régimes » aussi",
          any(u["regime"] == "all" for u in up), True)

    # ── LOT S15 : la coupe de `regime = 'unknown'` ─────────────────
    check("aucun accumulateur n'est plus écrit pour un régime inconnu",
          [u for u in up if u["regime"] == "unknown"], [])
    # ⛔ ET C'EST L'AUTRE MOITIÉ DE LA COUPE, celle qu'on rate en
    # sautant l'entrée `banded` entière : une journée qu'on n'a pas su
    # classer reste une journée de vent MESURÉE, et elle doit continuer
    # de peser dans la case générale. 10 647 journées par nuit
    # dépendent de cette ligne (mesuré le 25/08).
    # ⚠️ `.get(…, {})` PLUTÔT QU'UN ACCÈS DIRECT : si la case disparaît,
    # on veut un ROUGE qui nomme la case, pas un `KeyError` qui arrête
    # le banc et cache les assertions suivantes.
    check("… mais sa journée pèse quand même dans la case « tous régimes »",
          par_cle.get(("b1:valley", "icon_eu", "all", "all", "errKmh"),
                      {}).get("x"), 7.0)
    check("… à tous les échelons de repli, pas seulement la case fine",
          par_cle.get(("*:*", "icon_eu", "all", "all", "dirOffset"),
                      {}).get("x"), 5.0)

    # ── LOT S15 : l'ordre d'envoi ─────────────────────────────────
    cles = [(u["zone_id"], u["model"], u["lead_h"], u["regime"], u["band"],
             u["metric"]) for u in up]
    check("les lignes partent triées par la clé primaire (localité d'index)",
          cles, sorted(cles))

    # ⚠️ CE QUI N'EST PLUS TESTÉ ICI, ET OÙ ÇA L'EST : l'idempotence.
    # `accumulator_updates` ne connaît plus l'état, donc elle ne peut
    # plus écarter une journée déjà intégrée — c'est le
    # `where … p_day > mc.last_day` de `bw_character_avance` qui le
    # fait. Voir `test_s15_contrat_de_la_rpc` juste en dessous pour le
    # contrat, et la note `claude/lot-s15-rpc-caractere-etat-25-08.md`
    # pour le banc joué contre la VRAIE base (17 assertions vertes).
    check("la fonction est désormais SANS ÉTAT : deux appels identiques "
          "rendent la même chose",
          J.accumulator_updates(banded, zone_of), up)


def test_s15_contrat_de_la_rpc():
    """Le contrat que `bw_character_avance` doit tenir, modélisé ici.

    ⚠️ CE QUE CE BANC PROUVE, ET CE QU'IL NE PROUVE PAS. Il ne peut pas
    exécuter du SQL : il rejoue la sémantique de la RPC en Python et
    vérifie que, SOUS CE CONTRAT, la mémoire longue se comporte comme
    `scoring.accumulate`. Ce qui prouve que le SQL RÉEL tient ce
    contrat, c'est le banc joué contre la production le 25/08 (parité
    bit à bit sur 400 n-uplets tirés de la vraie table, double rejeu,
    doublons, NaN — 17 assertions vertes), consigné dans
    `claude/lot-s15-rpc-caractere-etat-25-08.md`.

    ⛔ Les deux sont nécessaires. Celui-ci rougit si quelqu'un change la
    forme du corps envoyé ou l'ordre des opérations côté Python ; celui
    de production rougit si quelqu'un touche au SQL. Aucun des deux ne
    couvre l'autre.
    """
    print("── S15 : le contrat de la RPC d'accumulation ──")

    def rpc(base, rows, jour_ms):
        """`bw_character_avance` en Python : le garde, et rien de plus."""
        applique = 0
        for r in rows:
            if not S._finite(r["x"]):
                continue                      # garde de finitude (SQL)
            cle = (r["zone_id"], r["model"], r["lead_h"], r["regime"],
                   r["band"], r["metric"])
            acc = base.get(cle, S.Accumulator())
            if acc.last_day is not None and jour_ms <= acc.last_day:
                continue                      # ⛔ LE GARDE D'IDEMPOTENCE
            base[cle] = S.accumulate(acc, r["x"], jour_ms)
            applique += 1
        return applique

    zone_of = {"pioupiou:835": {"zone_id": "b1:valley", "landform": "valley",
                               "basin_id": "b1", "massif_id": "alpes-nord",
                               "basin_uncertain": False}}
    banded = [{"key": "pioupiou:835", "model": "icon_d2", "lead_h": 24,
               "regime": "fluxN", "band": "strong", "errKmh": 4.0,
               "speedRatio": 1.2, "dirOffset": 10.0,
               "mseModel": 20.0, "msePersist": 30.0}]
    rows = J.accumulator_updates(banded, zone_of)
    cle = ("b1:valley", "icon_d2", 24, "fluxN", "strong", "errKmh")

    base = {}
    n1 = rpc(base, rows, DAY_MS)
    check("la première nuit applique toutes les lignes", n1, len(rows))
    check("… et pose un poids de 1", base[cle].sum_w, 1.0)
    check("… avec la médiane du jour", base[cle].sum_wx, 4.0)

    # ⛔ LE POINT : rejouer la MÊME journée n'applique RIEN.
    fige = dict(base)
    n2 = rpc(base, rows, DAY_MS)
    check("rejouer la même journée n'applique aucune ligne", n2, 0)
    check("… et ne bouge aucun accumulateur", base, fige)

    # Le lendemain, en revanche, avance — et exactement comme la
    # version Python d'avant le lot S15.
    n3 = rpc(base, rows, DAY_MS + 86_400_000)
    check("le lendemain, toutes les lignes s'appliquent", n3, len(rows))
    check("… l'acquis décroît de 2^(-1/30) puis s'ajoute",
          round(base[cle].sum_w, 12), round(2 ** (-1 / 30) + 1, 12))
    check("… et le compteur de journées avance de un", base[cle].days, 2)

    # ⛔ LE MUTANT, ÉCRIT DANS LE BANC : sans le garde, la nuit compte
    # deux fois. C'est ce que la RPC empêche, et c'est la seule chose
    # qui a vraiment changé de camp dans ce lot.
    sans_garde = {}
    for _ in range(2):
        for r in rows:
            c = (r["zone_id"], r["model"], r["lead_h"], r["regime"],
                 r["band"], r["metric"])
            sans_garde[c] = S.accumulate(
                S.Accumulator(sans_garde[c].sum_w, sans_garde[c].sum_wx,
                              sans_garde[c].sum_wx2, sans_garde[c].days, None)
                if c in sans_garde else S.Accumulator(), r["x"], DAY_MS)
    check("sans le garde, la même nuit compterait DEUX fois",
          sans_garde[cle].days, 2)


def test_s15_garde_du_lot_rpc():
    """`RPC_LOT` refuse de dépasser ce qui a été mesuré.

    ⛔ MÊME DÉFAUT QUE `PAGE` CONTRE `PLAFOND_SERVEUR`, MÊME GARDE. À
    20 000 lignes, la RPC rend `57014` EN PLEINE ÉCRITURE — et mesuré le
    25/08 sur la production, elle ne le fait qu'UNE FOIS SUR DEUX. Une
    taille qui échoue une fois sur deux passe en banc et tombe une nuit
    d'octobre : c'est pour ça que le garde refuse au lieu d'essayer.
    """
    print("── S15 : le garde de `RPC_LOT` ──")
    sb = _sb_de_banc()
    check("le plafond est celui mesuré le 25/08", J.Supabase.RPC_LOT, 5000)

    # ⛔ UN ESPION, PAS UN `try` NU. Sans lui, le banc ne distingue pas
    # « refusé AVANT de partir » de « parti, puis tombé sur le réseau » —
    # et c'est toute la différence : le second aurait déjà pu écrire.
    appels = []
    sb.rpc = lambda f, c: appels.append((f, len(c["p_rows"]))) or 0

    motif = None
    try:
        sb.avance_caractere([{"zone_id": "b1:valley", "model": "icon_d2",
                              "lead_h": 24, "regime": "fluxN",
                              "band": "strong", "metric": "errKmh", "x": 1.0}],
                            "2026-08-24", lot=20000)
    except J.Abort as exc:
        motif = str(exc)
    check("un lot au-dessus de RPC_LOT est refusé", motif is not None, True)
    check("… AVANT le moindre appel réseau", appels, [])
    check("… et le message dit pourquoi, pas seulement que",
          "57014" in (motif or ""), True)

    check("un envoi vide ne fait aucun appel",
          sb.avance_caractere([], "2026-08-24"), 0)
    check("… vraiment aucun", appels, [])


def test_s15_compte_ce_qui_est_applique():
    """⭐ `avance_caractere` rend l'APPLIQUÉ, pas l'ENVOYÉ.

    ⛔ C'EST UNE DIFFÉRENCE DE NATURE AVEC `upsert`, ET ELLE A UN COÛT
    HISTORIQUE. `sb.upsert` rend `len(rows)` : le journal a donc écrit
    « N accumulateurs avancés » pendant dix-huit nuits en comptant ce
    qu'il ENVOYAIT. Résultat, le 25/08 : impossible de réconcilier les
    3 615 845 « avancées » du journal avec les 3 270 977 `days` de la
    table sans relire les 739 916 lignes pour comprendre (c'était la
    purge du `step50`, mais rien ne le disait). Ce banc empêche que la
    régression revienne.
    """
    print("── S15 : le compte rendu est celui du serveur ──")
    sb = _sb_de_banc()
    envoyes = []

    def faux_rpc(fonction, corps):
        envoyes.append((fonction, len(corps["p_rows"]), corps["p_day"]))
        # Le serveur en applique moins que reçu : c'est le cas NORMAL
        # (valeurs non finies écartées, journées déjà intégrées).
        return len(corps["p_rows"]) - 1

    sb.rpc = faux_rpc
    rows = [{"zone_id": "b1:valley", "model": "icon_d2", "lead_h": 24,
             "regime": "fluxN", "band": "strong", "metric": "errKmh",
             "x": float(i)} for i in range(12_000)]
    n = sb.avance_caractere(rows, "2026-08-24")

    check("le découpage suit RPC_LOT", [e[1] for e in envoyes],
          [5000, 5000, 2000])
    check("toutes les journées envoyées sont la même",
          {e[2] for e in envoyes}, {"2026-08-24"})
    check("le compte rendu est celui du SERVEUR, pas la taille envoyée",
          n, 12_000 - 3)
    check("… et c'est lui qui alimente le compteur d'écritures",
          sb.ecritures, 12_000 - 3)


def test_scores_de_zone():
    print("── scores de zone ──")
    zone_of = {f"pioupiou:{i}": {"zone_id": "b1:valley", "landform": "valley",
                                 "basin_id": "b1", "massif_id": "alpes-nord",
                                 "basin_uncertain": False}
               for i in range(830, 836)}
    daily = []
    for j in range(15):
        d = (DAY - timedelta(days=j)).strftime("%Y-%m-%d")
        for i in range(830, 836):
            for model, err in (("icon_d2", 4.0), ("gfs_global", 9.0)):
                daily.append({
                    "day": d, "source": "pioupiou", "station_id": str(i),
                    "model": model, "lead_h": 24, "regime": "fluxN",
                    "n_hours": 12, "err_vec_med": err,
                    "mse_model": err * err, "mse_persist": 100.0})
    rows = J.rolling_scores(daily, zone_of, DAY)
    fine = [r for r in rows if r["zone_id"] == "b1:valley"]
    check("les deux modèles ont une ligne dans la case fine", len(fine), 2)
    gagnant = next(r for r in fine if r["model"] == "icon_d2")
    perdant = next(r for r in fine if r["model"] == "gfs_global")
    check("4 km/h contre 9 → le premier est classé 1er", gagnant["rank"], 1)
    check("… le second 2ᵉ", perdant["rank"], 2)
    check("… et la raison du classement est explicite",
          gagnant["rank_reason"], "ok")
    check("l'erreur typique est publiée en km/h, pas seulement le rang",
          gagnant["typical_err_kmh"], 4.0)
    check("battre la persistance est une réponse à part entière",
          gagnant["beats_persist"], True)
    check("… et un modèle à 81 de MSE contre 100 la bat aussi, tout en "
          "étant dernier", perdant["beats_persist"], True)
    check("le niveau d'agrégation est dit", gagnant["agg_level"], "basin_landform")
    check("les cinq échelons sont publiés",
          sorted({r["agg_level"] for r in rows}),
          ["basin_landform", "global", "landform", "massif", "massif_landform"])

    # Deux modèles trop proches : on refuse de trancher.
    serre = []
    for j in range(15):
        d = (DAY - timedelta(days=j)).strftime("%Y-%m-%d")
        for i in range(830, 836):
            for model, err in (("icon_d2", 5.0), ("gfs_global", 5.3)):
                serre.append({"day": d, "source": "pioupiou", "station_id": str(i),
                              "model": model, "lead_h": 24, "regime": "fluxN",
                              "n_hours": 12, "err_vec_med": err,
                              "mse_model": 25.0, "mse_persist": 100.0})
    rows2 = J.rolling_scores(serre, zone_of, DAY)
    fine2 = [r for r in rows2 if r["zone_id"] == "b1:valley"]
    check("5,0 contre 5,3 km/h → aucun rang attribué",
          all(r["rank"] is None for r in fine2), True)
    check("… et la raison le dit", fine2[0]["rank_reason"], "tied")

    # Sous le quorum de balises, aucune ligne.
    peu = [d for d in daily if d["station_id"] in ("830", "831")]
    rows3 = J.rolling_scores(peu, {k: v for k, v in zone_of.items()
                                   if k in ("pioupiou:830", "pioupiou:831")}, DAY)
    check("2 balises seulement → pas de score de zone publié", rows3, [])


def _unit(day, sid, model, err, regime="fluxN", lead=24, mse=None):
    return {"day": day, "unit": f"pioupiou:{sid}", "source": "pioupiou",
            "station_id": str(sid), "model": model, "lead_h": lead,
            "regime": regime, "n_hours": 12, "err_vec_med": err,
            "mse_model": mse if mse is not None else err * err,
            "mse_persist": 100.0}


def test_score_par_regime():
    """⚠️ CE BANC A CHANGÉ DE SOURCE AU LOT G, et c'est le cœur du lot.

    Il lisait des ACCUMULATEURS (`model_character`), qui portent trois
    sommes. Trois sommes savent faire une moyenne et une variance ;
    elles ne savent pas faire un décile. La conséquence se mesurait en
    base le 09/08 : `worst_decile_kmh`, `ci_low`, `ci_high` et `skill`
    nuls sur 10 250 lignes de régime sur 10 250 — pas un oubli, une
    impossibilité arithmétique.

    Il lit maintenant des BALISE-JOURS rejoués depuis l'archive. Les
    quatre colonnes ne sont plus vides, et c'est vérifiable ici.
    """
    print("── score par régime, depuis l'archive rejouée (lot G1) ──")
    zone_of = {f"pioupiou:{i}": {"zone_id": "b1:valley", "landform": "valley",
                                 "basin_id": "b1", "massif_id": "alpes-nord",
                                 "basin_uncertain": False}
               for i in range(830, 836)}
    kind_of = {"b1:valley": "basin_landform",
               "alpes-nord:valley": "massif_landform",
               "alpes-nord:*": "massif", "*:valley": "landform",
               "*:*": "global"}

    # 20 journées de flux de nord, dispersées : une distribution, pas
    # une constante — sinon le décile serait la moyenne et ne prouverait
    # rien.
    units = []
    for j in range(20):
        d = (DAY - timedelta(days=j)).strftime("%Y-%m-%d")
        for k, i in enumerate(range(830, 836)):
            for model, base in (("icon_d2", 3.0), ("gfs_global", 8.0)):
                units.append(_unit(d, i, model, base + (j % 5) + k * 0.5))
        # Une journée thermique intercalée : elle ne doit pas se
        # retrouver dans la case fluxN.
        for i in range(830, 836):
            units.append(_unit(d, i, "icon_d2", 99.0, regime="thermal"))
        # Et une journée non classée : elle ne va NULLE PART.
        units.append(_unit(d, 830, "icon_d2", 42.0, regime="unknown"))

    rows = J.regime_scores(units, DAY, zone_of, kind_of)
    fine = [r for r in rows if r["zone_id"] == "b1:valley"
            and r["regime"] == "fluxN"]
    check("une ligne par modèle dans la case fine", len(fine), 2)
    check("l'échelon publié est celui de model_zone, pas un reniflage",
          {r["agg_level"] for r in fine}, {"basin_landform"})
    check("la fenêtre est bien celle du régime, pas les 15 jours",
          {r["window_kind"] for r in rows}, {"regime"})

    best = next(r for r in fine if r["model"] == "icon_d2")
    pire = next(r for r in fine if r["model"] == "gfs_global")

    # ══ LE DÉFAUT CORRIGÉ ══
    check("LE PIRE DÉCILE EXISTE sur le chemin régime",
          best["worst_decile_kmh"] is not None, True)
    check("… et il est au-dessus de l'erreur typique, sinon ce n'est pas "
          "un décile supérieur",
          best["worst_decile_kmh"] > best["typical_err_kmh"], True)
    check("L'INTERVALLE EXISTE aussi", best["ci_low"] is not None, True)
    check("… et il encadre la médiane",
          best["ci_low"] <= best["typical_err_kmh"] <= best["ci_high"], True)
    check("… et il est annoncé comme un intervalle PAR BLOCS DE JOURS",
          best["ci_kind"], "block_day")
    check("… avec la longueur de bloc publiée",
          best["block_days"] >= 3, True)
    check("LE SKILL EXISTE", best["skill"] is not None, True)
    check("… et 'bat la persistance' aussi", best["beats_persist"], True)
    check("le nombre de JOURNÉES est publié, pas seulement d'occurrences",
          best["n_days"], 20)

    check("une journée non classée ne rejoint aucune case",
          any(r["regime"] == "unknown" for r in rows), False)
    check("le régime thermique a sa propre case",
          {r["regime"] for r in rows}, {"fluxN", "thermal"})
    check("… et la journée thermique n'a pas pollué fluxN",
          best["typical_err_kmh"] < 20, True)

    check("3 km/h contre 8 → le premier est classé 1er", best["rank"], 1)
    check("… le second 2ᵉ", pire["rank"], 2)
    check("… et la raison est explicite", best["rank_reason"], "ok")

    # Une zone absente de model_zone est impossible (clé étrangère) ;
    # si elle survenait, on saute plutôt que d'inventer un échelon.
    check("zone inconnue de model_zone → aucune ligne publiée",
          J.regime_scores(
              units, DAY,
              {k: dict(v, zone_id="b9:ridge") for k, v in zone_of.items()},
              {"alpes-nord:valley": "massif_landform", "alpes-nord:*": "massif",
               "*:valley": "landform", "*:*": "global"}),
          [r for r in J.regime_scores(
              units, DAY,
              {k: dict(v, zone_id="b9:ridge") for k, v in zone_of.items()},
              {"alpes-nord:valley": "massif_landform", "alpes-nord:*": "massif",
               "*:valley": "landform", "*:*": "global"})
           if r["zone_id"] != "b9:ridge"])

    # ══ LA FENÊTRE TROP COURTE — l'état réel de l'archive au 09/08 ══
    courts = [u for u in units
              if u["day"] >= (DAY - timedelta(days=1)).strftime("%Y-%m-%d")]
    rows_c = J.regime_scores(courts, DAY, zone_of, kind_of)
    fine_c = [r for r in rows_c if r["zone_id"] == "b1:valley"
              and r["regime"] == "fluxN"]
    check("deux jours → aucun intervalle publié",
          all(r["ci_low"] is None for r in fine_c), True)
    check("… et la raison est nommée, pas devinée",
          {r["ci_reason"] for r in fine_c}, {"window_too_short"})
    check("… le pire décile, lui, reste calculable : c'est une "
          "distribution, pas un test",
          all(r["worst_decile_kmh"] is not None for r in fine_c), True)
    check("… ET AUCUN RANG N'EST ATTRIBUÉ malgré un écart de 5 km/h : "
          "pas de repli sur l'écart relatif seul",
          all(r["rank"] is None for r in fine_c), True)
    check("… la raison du non-classement est la fenêtre, pas le quorum",
          fine_c[0]["rank_reason"], "window_too_short")

    # Trop peu d'occurrences : le classement se tait, quorum d'abord.
    rares = [u for u in units
             if u["day"] >= (DAY - timedelta(days=1)).strftime("%Y-%m-%d")
             and u["unit"] == "pioupiou:830"]
    rows2 = J.regime_scores(rares, DAY, zone_of, kind_of)
    fine2 = [r for r in rows2 if r["zone_id"] == "b1:valley"
             and r["regime"] == "fluxN"]
    check("sous le quorum d'occurrences → aucun rang, et la raison est dite",
          (all(r["rank"] is None for r in fine2), fine2[0]["rank_reason"]),
          (True, "insufficient"))


def test_rétrécissement_vers_le_parent():
    """Lot G3 — le pooling améliore l'estimation, le quorum garde la porte.

    ⚠️ LES DONNÉES DE CE BANC SONT DISPERSÉES, à dessein. Sur des
    erreurs quasi constantes, une case même maigre est parfaitement
    connue et n'a rien à emprunter : le banc passerait en ne prouvant
    rien. C'est la dispersion qui fait exister l'incertitude que le
    rétrécissement est censé arbitrer.
    """
    print("── rétrécissement vers le parent (lot G3) ──")

    def bruit(k):                       # suite déterministe, sans `random`
        return ((k * 7919) % 101) / 100.0 * 6.0 - 3.0

    zones, zone_of = [], {}
    #  b0 : 6 balises, 12 jours → 72 balise-jours, bien fournie
    #  b1 : 6 balises, 12 jours → 72, bien fournie aussi
    #  b2 : 1 balise, 2 jours   → 2, maigre
    plan = {"b0": (6, 12, 4.0), "b1": (6, 12, 6.0), "b2": (1, 2, 1.0)}
    for b, (n_st, _, _) in plan.items():
        for i in range(n_st):
            sid = f"{b}-{i:02d}"
            z = {"source": "pioupiou", "station_id": sid,
                 "zone_id": f"{b}:valley", "landform": "valley",
                 "basin_id": b, "massif_id": "alpes-nord",
                 "basin_uncertain": False}
            zone_of[f"pioupiou:{sid}"] = z
            zones.append(z)

    units, k = [], 0
    for key, z in zone_of.items():
        b = z["basin_id"]
        n_st, n_days, base = plan[b]
        for j in range(n_days):
            d = (DAY - timedelta(days=j)).strftime("%Y-%m-%d")
            k += 1
            units.append(_unit(d, z["station_id"], "icon_d2",
                               max(0.5, base + bruit(k))))

    kind_of = {"b0:valley": "basin_landform", "b1:valley": "basin_landform",
               "b2:valley": "basin_landform",
               "alpes-nord:valley": "massif_landform",
               "alpes-nord:*": "massif", "*:valley": "landform", "*:*": "global"}
    rows = J.regime_scores(units, DAY, zone_of, kind_of, min_stations=1)
    n = J.apply_pooling(rows, zones)
    check("des cases fines ont été rapprochées de leur parent", n > 0, True)

    maigre = next(r for r in rows if r["zone_id"] == "b2:valley")
    fourni = next(r for r in rows if r["zone_id"] == "b0:valley")
    parent = next(r for r in rows if r["zone_id"] == "alpes-nord:valley")

    check("la case à 2 balise-jours emprunte une part sensible",
          maigre["borrowed_weight"] > 0.25, True)
    check("… au moins dix fois plus que la case à 72 balise-jours",
          maigre["borrowed_weight"] > 10 * fourni["borrowed_weight"], True)
    # ⚠️ Elle n'emprunte PAS 90 % pour autant, et c'est juste : ici les
    # trois vallées sœurs sont vraiment différentes (4, 6 et 2 km/h),
    # donc τ² est grand et le parent est un mauvais substitut. Le
    # rétrécissement arbitre entre « cette case est mal connue » et
    # « les sœurs se ressemblent » ; il ne rabat pas tout par principe.
    check("… mais elle garde la majorité de son propre chiffre quand les "
          "vallées sœurs sont franchement différentes",
          maigre["borrowed_weight"] < 0.5, True)
    check("… et son estimation poolée est tirée vers le parent",
          abs(maigre["pooled_err_kmh"] - parent["typical_err_kmh"])
          < abs(maigre["typical_err_kmh"] - parent["typical_err_kmh"]), True)
    check("la case bien fournie garde presque tout son chiffre",
          abs(fourni["pooled_err_kmh"] - fourni["typical_err_kmh"]) < 1.0, True)
    check("L'ERREUR BRUTE N'EST PAS ÉCRASÉE — les deux sont publiées",
          maigre["typical_err_kmh"] < parent["typical_err_kmh"], True)
    check("le poids emprunté est publié À CÔTÉ de chaque chiffre poolé",
          all(r.get("borrowed_weight") is not None
              for r in rows if r.get("pooled_err_kmh") is not None), True)
    check("la dispersion de la case est publiée elle aussi",
          fourni["err_sd"] is not None, True)
    check("LE POOLING NE FAIT APPARAÎTRE AUCUNE LIGNE NOUVELLE : "
          "le quorum reste le seuil d'affichage",
          len(rows), len(J.regime_scores(units, DAY, zone_of, kind_of,
                                         min_stations=1)))

    # ── le cas symétrique : des sœurs qui se ressemblent ──
    # Quand τ² est petit, il n'y a rien à distinguer entre vallées et la
    # case maigre doit emprunter presque tout. C'est l'autre moitié de
    # la preuve : sans elle, on ne saurait pas si le curseur bouge.
    units2, k = [], 0
    for key, z in zone_of.items():
        b = z["basin_id"]
        _, n_days, _ = plan[b]
        for j in range(n_days):
            d = (DAY - timedelta(days=j)).strftime("%Y-%m-%d")
            k += 1
            units2.append(_unit(d, z["station_id"], "icon_d2",
                                max(0.5, 5.0 + bruit(k))))
    rows2 = J.regime_scores(units2, DAY, zone_of, kind_of, min_stations=1)
    J.apply_pooling(rows2, zones)
    maigre2 = next(r for r in rows2 if r["zone_id"] == "b2:valley")
    check("des vallées sœurs indiscernables → la case maigre emprunte "
          "presque tout",
          maigre2["borrowed_weight"] > 0.85, True)
    check("… et son estimation devient pratiquement celle du massif",
          abs(maigre2["pooled_err_kmh"]
              - next(r for r in rows2
                     if r["zone_id"] == "alpes-nord:valley")["typical_err_kmh"])
          < 0.5, True)


def test_rejeu_darchive():
    """Lot G1 — le rejeu, son cache, et son budget de nuit.

    ⚠️ CE BANC ÉCRIT SUR DISQUE, dans un répertoire temporaire. C'est
    voulu : le cache de rejeu est la seule raison pour laquelle rejouer
    30 journées chaque nuit ne multiplie pas la durée du run par 30, et
    un cache qu'on ne teste pas est un cache qui sert un jour des
    chiffres périmés.
    """
    print("── rejeu d'archive et cache (lot G1) ──")
    import gzip as _gz
    import json as _json
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        jours = [DAY - timedelta(days=k) for k in range(3)]
        for d in jours:
            fk = root / J.fcst_key(d)
            fk.parent.mkdir(parents=True, exist_ok=True)
            lignes = [fcst_line("830", "icon_d2", d, lambda i: brise(i % 24),
                                aloft=(30.0, 10.0)),
                      fcst_line("831", "icon_d2", d, lambda i: brise(i % 24),
                                aloft=(30.0, 10.0))]
            fk.write_bytes(_gz.compress(
                ("\n".join(_json.dumps(l) for l in lignes)).encode()))
            ok = root / J.obs_key(d)
            ok.parent.mkdir(parents=True, exist_ok=True)
            obs = [obs_line("830", d, brise), obs_line("831", d, brise)]
            ok.write_bytes(_gz.compress(
                ("\n".join(_json.dumps(l) for l in obs)).encode()))

        rows, bilan = J.replay_window(root, DAY, None, 7200, n_days=3)
        check("le rejeu retrouve des balise-jours dans l'archive",
              len(rows) > 0, True)
        check("chaque ligne porte sa clé d'appariement `unit`",
              all(r.get("unit", "").startswith("pioupiou:") for r in rows), True)
        check("le bilan dit combien de journées ont été rejouées",
              "rejouée(s) cette nuit" in bilan, True)

        # Le cache existe maintenant : deuxième passage, aucun rejeu.
        rows2, bilan2 = J.replay_window(root, DAY, None, 7200, n_days=3)
        check("le second passage rend exactement les mêmes lignes",
              len(rows2), len(rows))
        check("… sans rejouer quoi que ce soit (le cache a servi)",
              "0 rejouée(s)" in bilan2, True)

        # Un changement de formule invalide le cache : sinon on servirait
        # des chiffres calculés par du code qui n'existe plus.
        cache = J.replay_path(root, DAY)
        d = _json.loads(_gz.decompress(cache.read_bytes()).decode())
        d["formula"] = J.REPLAY_FORMULA + 1
        cache.write_bytes(_gz.compress(_json.dumps(d).encode()))
        check("un cache d'une AUTRE formule est ignoré, pas réparé",
              J.replay_read(root, DAY), None)

        # Budget : une nuit ne rattrape pas trente journées d'un coup.
        for d0 in jours:
            J.replay_path(root, d0).unlink(missing_ok=True)
        _, bilan3 = J.replay_window(root, DAY, None, 7200, n_days=3,
                                    budget_new_days=1)
        check("le budget borne le nombre de journées rejouées par nuit",
              "1 rejouée(s)" in bilan3, True)
        check("… ET LE DIT : une fenêtre tronquée en silence se lirait "
              "comme une fenêtre complète",
              "REPORTÉE(S)" in bilan3, True)


def test_fenetre_de_maintien_adaptative():
    """Arbitrage `hold_ms` du lot F, tranché le 09/08 : fenêtre adaptative.

    ⚠️ CE BANC PROTÈGE LES DEUX MOITIÉS DE L'ARBITRAGE. La première est
    facile à voir : une série horaire doit redevenir détectable. La
    seconde l'est moins et compte autant : une balise dense ne doit
    RIEN changer, parce que 45 min est le seul réglage sur lequel quoi
    que ce soit ait été calibré. Un banc qui ne vérifierait que la
    première laisserait passer une régression silencieuse sur les
    bonnes données — celles qui servent réellement.
    """
    print("── fenêtre de maintien adaptative (arbitrage hold_ms) ──")
    import events as E

    def serie(cadence_s, t0=0):
        """Une bascule franche : 90° pendant 3 h, puis 270° pendant 3 h."""
        n = 6 * 3600 // cadence_s
        return [S.ObsSample(t=t0 + i * cadence_s * 1000, speed=18.0,
                            dir=90.0 if i * cadence_s < 3 * 3600 else 270.0)
                for i in range(n + 1)]

    dense = serie(240)          # Pioupiou, ~4 min
    horaire = serie(3600)       # observation dégradée à l'heure

    check("le pas réel d'une série dense est retrouvé",
          J.median_step_ms(dense), 240_000)
    check("… celui d'une série horaire aussi",
          J.median_step_ms(horaire), 3_600_000)

    check("SUR UNE BALISE DENSE, LA FENÊTRE NE BOUGE PAS (45 min)",
          J.adaptive_hold_ms(dense), E.DEFAULT_DETECT.hold_ms)
    check("sur une série horaire, elle s'ouvre à 90 min",
          J.adaptive_hold_ms(horaire), 90 * 60 * 1000)
    check("… soit un pas entier de chaque côté, la condition minimale "
          "pour que les deux fenêtres comparées puissent différer",
          J.adaptive_hold_ms(horaire) >= 2 * J.median_step_ms(horaire) * 0.75,
          True)

    # ── l'effet mesuré sur la détection elle-même ──
    ev_dense_avant = [e for e in E.detect_all(dense, J.EVENT_ONSET_KMH)
                      if e.type == "reversal"]
    ev_dense_apres = [e for e in J.station_events(dense, None, 7200)
                      if e.type == "reversal"]
    check("la balise dense détecte la bascule avant comme après",
          (len(ev_dense_avant) > 0, len(ev_dense_apres)),
          (True, len(ev_dense_avant)))

    ev_h_avant = [e for e in E.detect_all(horaire, J.EVENT_ONSET_KMH)
                  if e.type == "reversal"]
    ev_h_apres = [e for e in J.station_events(horaire, None, 7200)
                  if e.type == "reversal"]
    check("À L'HEURE, LE RÉGLAGE FIXE DE 45 MIN NE VOYAIT RIEN",
          len(ev_h_avant), 0)
    check("… et la fenêtre adaptative voit la bascule",
          len(ev_h_apres) > 0, True)

    # Une série trop courte pour avoir un pas : on ne devine pas.
    check("moins de trois points → pas de pas mesurable",
          J.median_step_ms(dense[:2]), None)
    check("… et la fenêtre reste celle par défaut",
          J.adaptive_hold_ms(dense[:2]), E.DEFAULT_DETECT.hold_ms)

    # ⚠️ Et l'arbitrage ne s'étend PAS à la publication.
    check("`reversal` n'entre toujours pas dans le JSON publié : "
          "détecter n'est pas calibrer",
          "reversal" in J.EVENT_PUBLISHABLE_TYPES, False)



def test_stabilite_des_rangs():
    """Lot G5 — le critère de sortie, et le piège qu'il évite.

    ⚠️ CE BANC EXISTE SURTOUT POUR LE PIÈGE. Deux fenêtres glissantes de
    15 jours décalées d'un jour partagent 14 jours sur 15 : leur accord
    serait proche de 1 quoi qu'il arrive, et ce 1 dirait « les données
    sont les mêmes », pas « le classement est stable ». Le rapport doit
    donc porter le nombre de jours partagés, et il doit valoir ZÉRO.
    """
    print("── stabilité des rangs sur fenêtres disjointes (lot G5) ──")
    zone_of = {f"pioupiou:{i}": {"zone_id": "b1:valley", "landform": "valley",
                                 "basin_id": "b1", "massif_id": "alpes-nord",
                                 "basin_uncertain": False}
               for i in range(830, 836)}
    kind_of = {"b1:valley": "basin_landform",
               "alpes-nord:valley": "massif_landform",
               "alpes-nord:*": "massif", "*:valley": "landform", "*:*": "global"}

    def jeu(n_days, err_a, err_b, bascule=None):
        """`bascule` : à partir de ce jour, les deux modèles échangent."""
        out = []
        for j in range(n_days):
            d = (DAY - timedelta(days=j)).strftime("%Y-%m-%d")
            a, b = (err_a, err_b)
            if bascule is not None and j >= bascule:
                a, b = b, a
            for i in range(830, 836):
                out.append(_unit(d, i, "icon_d2", a + (j % 4) * 0.3))
                out.append(_unit(d, i, "gfs_global", b + (j % 4) * 0.3))
        return out

    stable = J.stability_report(jeu(30, 3.0, 9.0), zone_of, DAY, kind_of)
    check("deux moitiés disjointes ne partagent AUCUN jour",
          stable["shared_days"], 0)
    check("… et le rapport le dit, il ne le suppose pas",
          stable["reason"], "ok")
    check("un classement qui se reproduit donne tau = 1",
          stable["kendall_tau"], 1.0)
    check("… et l'accord sur le vainqueur vaut 1", stable["top1_agreement"], 1.0)
    check("le rapport dit ce que le chiffre recouvre",
          "disjointes" in stable["covers"], True)

    # Le classement s'inverse à mi-parcours : les deux moitiés se
    # contredisent, et le chiffre doit le montrer.
    instable = J.stability_report(jeu(30, 3.0, 9.0, bascule=15),
                                  zone_of, DAY, kind_of)
    check("un classement qui s'inverse d'une période à l'autre → tau = −1",
          instable["kendall_tau"], -1.0)
    check("… et aucun accord sur le vainqueur",
          instable["top1_agreement"], 0.0)

    # ── l'état réel de l'archive au 09/08 ──
    court = J.stability_report(jeu(3, 3.0, 9.0), zone_of, DAY, kind_of)
    check("moins de deux fenêtres pleines → aucun chiffre inventé",
          (court["reason"], court["kendall_tau"]), ("window_too_short", None))
    check("… et le rapport dit combien de journées il faudrait",
          "disjointes" in court["covers"], True)



def test_familles_publiees():
    """`reversal` va en base, jamais dans le JSON — tant que `hold_ms`
    n'est pas tranché.

    ⚠️ CE BANC PROTÈGE UNE DÉCISION, PAS UN CALCUL. Le jour où quelqu'un
    remettra `reversal` dans `EVENT_PUBLISHABLE_TYPES` sans avoir touché
    à `hold_ms`, ce banc rougira et rappellera pourquoi : le détecteur ne
    voit aucune bascule dans une série horaire, et publier POD = 0
    imputerait aux modèles une cécité qui est celle de l'outil.
    """
    print("── familles publiées ──")
    zone = {"source": "pioupiou", "station_id": "1", "zone_id": "b1:valley",
            "basin_id": "b1", "massif_id": "alpes-nord", "landform": "valley"}
    zone_of = {"pioupiou:1": zone}

    def ligne(etype, outcome, timing=None):
        return {"day": "2026-08-07", "zone_id": "b1:valley", "model": "icon_d2",
                "lead_h": 6, "event_type": etype, "threshold_kmh": None,
                "outcome": outcome, "timing_err_min": timing}

    # 12 bascules ratées : largement au-dessus du quorum de 8.
    bascules = [ligne("reversal", "miss") for _ in range(12)]
    # 12 établissements, dont 6 vus : publiables, eux.
    etablis = ([ligne("onset", "hit", -20) for _ in range(6)]
               + [ligne("onset", "miss") for _ in range(6)])

    rows, rejets, inconnues, retenues = J.event_scores(bascules, zone_of)
    check("12 bascules au-dessus du quorum ne produisent AUCUNE ligne publiée",
          [len(rows), retenues], [0, 12])

    rows2, _, _, retenues2 = J.event_scores(bascules + etablis, zone_of)
    check("les établissements passent, les bascules restent retenues",
          [sorted({r["event_type"] for r in rows2}), retenues2],
          [["onset"], 12])
    check("le POD publié porte bien sur les seuls établissements",
          [r["pod"] for r in rows2 if r["agg_level"] == "basin_landform"],
          [0.5])
    check("`reversal` est absent de la liste des familles publiables",
          "reversal" in J.EVENT_PUBLISHABLE_TYPES, False)


def test_lecture_paginee():
    """Le défaut du 08/08 : `select` rendait 1 000 lignes et se taisait.

    ⚠️ CE BANC EXISTE PARCE QUE LE DÉFAUT ÉTAIT INVISIBLE. Rien ne
    plantait, aucun banc ne rougissait, et `model_character` repartait
    de zéro chaque nuit — 81 960 accumulateurs dont la mémoire longue,
    seule raison d'être, n'a jamais rien mémorisé. On simule donc un
    serveur qui plafonne, et on exige que le client aille chercher la
    suite.
    """
    print("── lecture paginée (plafond PostgREST) ──")
    import io
    import json as JSON
    import urllib.request as U

    total = 2_346                       # ni un multiple de 1 000, ni rond
    vus: list[tuple[str, str]] = []     # (url, en-tête Range) par appel

    class _Rep(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def faux_urlopen(req, timeout=None):
        vus.append((req.full_url, req.get_header("Range")))
        deb, fin = (int(x) for x in req.get_header("Range").split("-"))
        page = [{"id": i} for i in range(deb, min(fin + 1, total))]
        return _Rep(JSON.dumps(page).encode())

    sb = J.Supabase.__new__(J.Supabase)
    sb.url, sb.key, sb.dry_run, sb.ecritures = "http://x", "k", False, 0
    vrai, U.urlopen = U.urlopen, faux_urlopen
    try:
        rows = sb.select("model_character", order="zone_id")
    finally:
        U.urlopen = vrai

    check("toutes les lignes sont lues, pas seulement la première page",
          len(rows), total)
    check("les identifiants ne sont ni dupliqués ni sautés",
          (rows[0]["id"], rows[-1]["id"], len({r["id"] for r in rows})),
          (0, total - 1, total))
    check("une page incomplète arrête la boucle (pas d'appel de trop)",
          [len(vus), [r for _, r in vus]],
          [3, ["0-999", "1000-1999", "2000-2999"]])
    # ⚠️ Sans `ORDER BY`, PostgreSQL peut rendre deux pages dans des
    # ordres incompatibles : une ligne deux fois, une autre jamais. Le
    # tri n'est donc pas un confort de lecture, c'est ce qui rend la
    # pagination correcte.
    check("l'ordre explicite part dans CHAQUE page, pas seulement la première",
          all("order=zone_id" in u for u, _ in vus), True)


# ══════════════════════════════════════════════════════════════════
#  LECTURE PAR CLÉ (25/08) — la panne du run de 05:57
# ══════════════════════════════════════════════════════════════════

def _faux_serveur_paginant(rows: list[dict], cle: str = "zone_id"):
    """Un PostgREST de papier : plafonne à la fenêtre demandée, honore
    `cle=gt.`, et note chaque appel reçu.

    ⚠️ Il TRIE sur la clé, comme le vrai `ORDER BY` : sans ça le banc
    validerait une pagination qui ne marche que par chance.
    """
    import io
    import json as JSON
    import re
    import urllib.parse as UP

    vus: list[tuple[str, str]] = []
    tout = sorted(rows, key=lambda r: (r[cle], r["i"]))

    class _Rep(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def faux(req, timeout=None):
        url = req.full_url
        vus.append((url, req.get_header("Range")))
        eq = re.search(rf"{cle}=eq\.([^&]*)", url)
        gt = re.search(rf"{cle}=gt\.([^&]*)", url)
        if eq:
            v = UP.unquote(eq.group(1))
            reste = [r for r in tout if r[cle] == v]
        elif gt:
            v = UP.unquote(gt.group(1))
            reste = [r for r in tout if r[cle] > v]
        else:
            reste = tout
        deb, fin = (int(x) for x in req.get_header("Range").split("-"))
        return _Rep(JSON.dumps(reste[deb:fin + 1]).encode())

    return faux, vus


def _sb_de_banc():
    sb = J.Supabase.__new__(J.Supabase)
    sb.url, sb.key, sb.dry_run, sb.ecritures = "http://x", "k", False, 0
    return sb


def test_lecture_par_cle_exacte():
    """⛔ LE BANC DE LA PANNE DU 25/08.

    Le run de 05:57 est mort sur `HTTP 500` en relisant `model_character`
    (739 916 lignes) : Supabase coupe à 8 s (`57014`), et une page de
    1 000 lignes à l'offset 600 000 dépasse ce délai — mesuré en direct
    aux offsets 600 000 / 660 000 / 700 000 / 730 000, tous rouges. Ce
    n'était donc pas un aléa : la lecture par OFFSET ne pouvait PLUS
    aller au bout, et ne le pourrait plus jamais.

    On exige ici trois choses de `select_par_cle` : qu'elle lise TOUT,
    qu'elle ne lise rien deux fois, et qu'elle ne demande JAMAIS un
    offset — le seul point qui rende la lecture immunisée à la taille
    de la table.
    """
    print("── lecture par clé (la panne du 25/08) ──")
    import urllib.request as U

    # Des zones de tailles inégales, dont une qui enjambe exactement la
    # frontière d'une page : c'est là que la queue partielle se joue.
    # `z003` compte 2 654 lignes : c'est la zone grasse du cas réel
    # (`alpes-nord:*`, mesurée le 25/08), celle qui déborde d'une page.
    rows, i = [], 0
    tailles = [700, 400, 1, 2654, 2, 350, 640, 1000]
    for z, n in enumerate(tailles):
        for _ in range(n):
            rows.append({"zone_id": f"z{z:03d}", "i": i, "v": i * 2})
            i += 1
    total = sum(tailles)

    faux, vus = _faux_serveur_paginant(rows)
    sb = _sb_de_banc()
    vrai, U.urlopen = U.urlopen, faux
    try:
        lues = sb.select_par_cle(
            "model_character", "zone_id",
            order="zone_id,model,lead_h,regime,band,metric,event_type")
    finally:
        U.urlopen = vrai

    check("toutes les lignes sont lues", len(lues), total)
    check("aucune ligne n'est lue deux fois, aucune n'est sautée",
          sorted(r["i"] for r in lues), list(range(total)))
    # ⛔ LE POINT DE TOUTE LA CORRECTION, et il ne dit PAS « zéro
    # offset » : il dit « aucun offset sur la table entière ». Les seuls
    # offsets tolérés sont ceux d'une valeur de clé isolée
    # (`zone_id=eq.`), bornés par la taille de cette valeur — 2 654
    # lignes au pire dans la vraie base, contre 739 916. Un offset sur
    # une requête NON filtrée, et la panne du 25/08 revient telle quelle
    # dans quelques semaines.
    balayages = [r for u, r in vus if "zone_id=eq." not in u]
    check("aucune page de balayage ne demande d'offset",
          sorted(set(balayages)), ["0-999"])
    check("les seuls offsets vont à une valeur de clé isolée",
          sorted({r for u, r in vus if "zone_id=eq." in u}),
          ["0-999", "1000-1999", "2000-2999"])
    check("l'ordre complet part dans chaque page",
          all("order=zone_id%2Cmodel" in u or "order=zone_id,model" in u
              for u, _ in vus), True)
    scans = [u for u, _ in vus if "zone_id=eq." not in u]
    check("la reprise se fait bien sur la clé, pas sur un rang",
          all("zone_id=gt." in u for u in scans[1:]), True)


def test_lecture_par_cle_valeur_plus_grosse_quune_page():
    """Une valeur de clé qui déborde d'une page — le cas RÉEL, pas d'école.

    ⛔ TROUVÉ EN LANÇANT LA SONDE SUR LA BASE DE PRODUCTION, pas en
    raisonnant : `zone_id=*:*` porte plus de 1 000 accumulateurs à elle
    seule, et la première version de `select_par_cle` s'arrêtait dessus.
    Les zones grasses sont les échelons de repli, ceux qui croisent tous
    les modèles × échéances × régimes × tranches × métriques —
    `*:valley` 2 301, `alpes-nord:*` 2 654, `alpes-nord:ridge` 2 320.

    Elles ne peuvent pas être jetées (la boucle resterait sur place) ni
    gardées à moitié (la fin de la valeur serait perdue) : on les lit
    entières, filtrées, et on reprend après.
    """
    print("── lecture par clé : une valeur plus grosse qu'une page ──")
    import urllib.request as U

    rows = ([{"zone_id": "a", "i": i} for i in range(3)]
            + [{"zone_id": "grosse", "i": 3 + i} for i in range(2654)]
            + [{"zone_id": "z", "i": 2657 + i} for i in range(5)])
    faux, vus = _faux_serveur_paginant(rows)
    sb = _sb_de_banc()
    vrai, U.urlopen = U.urlopen, faux
    try:
        lues = sb.select_par_cle("model_character", "zone_id", order="zone_id")
    finally:
        U.urlopen = vrai

    check("la valeur grasse est lue ENTIÈRE, et rien d'autre n'est perdu",
          [len(lues), sorted(r["i"] for r in lues)],
          [2662, list(range(2662))])
    check("aucun doublon malgré la page jetée puis relue",
          len({r["i"] for r in lues}), 2662)
    check("elle a bien été lue à part, filtrée sur sa seule valeur",
          any("zone_id=eq.grosse" in u for u, _ in vus), True)
    check("et la lecture reprend APRÈS elle, sans repasser dessus",
          any("zone_id=gt.grosse" in u for u, _ in vus), True)


def test_lecture_reprise_sur_5xx():
    """Une lecture ratée ne doit plus coûter le run entier.

    ⚠️ ET UN 4xx NE SE REPREND PAS : c'est une faute du client, elle se
    répéterait à l'identique. Le banc exige les deux comportements, pas
    seulement le premier — une reprise aveugle transformerait une erreur
    de requête en trois erreurs de requête, plus lentes.
    """
    print("── reprise de lecture sur 5xx ──")
    import io
    import json as JSON
    import urllib.error as E
    import urllib.request as U

    class _Rep(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    appels = {"n": 0}

    def faux_500_puis_ok(req, timeout=None):
        appels["n"] += 1
        if appels["n"] == 1:
            raise E.HTTPError(
                req.full_url, 500, "Internal Server Error", {},
                io.BytesIO(b'{"code":"57014","message":"statement timeout"}'))
        return _Rep(JSON.dumps([{"zone_id": "a", "i": 0}]).encode())

    def faux_400(req, timeout=None):
        appels["n"] += 1
        raise E.HTTPError(req.full_url, 400, "Bad Request", {},
                          io.BytesIO(b'{"code":"42703"}'))

    sb = _sb_de_banc()
    vraie_pause, J.time.sleep = J.time.sleep, lambda _s: None
    vrai, U.urlopen = U.urlopen, faux_500_puis_ok
    try:
        lues = sb.select_par_cle("model_character", "zone_id", order="zone_id")
    finally:
        U.urlopen = vrai
    check("un 500 est repris, et la lecture aboutit",
          [len(lues), appels["n"]], [1, 2])

    appels["n"] = 0
    U.urlopen = faux_400
    try:
        sb.select_par_cle("model_character", "zone_id", order="zone_id")
        recu = 400_000
    except E.HTTPError as exc:
        recu = exc.code
    finally:
        U.urlopen = vrai
        J.time.sleep = vraie_pause
    check("un 400 n'est PAS repris (une seule requête, erreur remontée)",
          [recu, appels["n"]], [400, 1])


def test_page_ne_depasse_pas_le_plafond_serveur():
    """⛔ LE PIÈGE DU 08/08, REFERMÉ POUR DE BON.

    `select` s'arrête sur `len(page) < PAGE`. Le serveur, lui, plafonne
    à 1 000 quoi qu'on demande — re-mesuré le 25/08 : `Range: 0-9999`
    sur `model_character` rend 1 000 lignes. Donc quiconque augmente
    `PAGE` pour « aller plus vite » obtient une première page qui a
    l'air incomplète, une lecture qui s'arrête là, et 739 000
    accumulateurs qui repartent de zéro — sans une seule erreur.

    On exige donc un refus BRUYANT, pas une lecture qui ment.
    """
    print("── PAGE contre le plafond serveur ──")
    import urllib.request as U

    rows = [{"zone_id": f"z{i:05d}", "i": i} for i in range(3000)]
    faux, vus = _faux_serveur_paginant(rows)
    sb = _sb_de_banc()
    sb.PAGE = 10_000                       # le geste tentant, et fatal
    vrai, U.urlopen = U.urlopen, faux
    try:
        sb.select_par_cle("model_character", "zone_id", order="zone_id")
        recu = "lecture silencieuse"
    except J.Abort as exc:
        recu = "abort" if "plafond serveur" in str(exc) else str(exc)
    finally:
        U.urlopen = vrai
    check("PAGE au-dessus du plafond serveur refuse de lire",
          recu, "abort")
    check("et rien n'est parti sur le réseau", len(vus), 0)

    # Le même garde protège l'ancien chemin par offset.
    sb2 = _sb_de_banc()
    sb2.PAGE = 10_000
    U.urlopen = faux
    try:
        sb2.select("model_character", order="zone_id")
        recu2 = "lecture silencieuse"
    except J.Abort:
        recu2 = "abort"
    finally:
        U.urlopen = vrai
    check("le garde couvre aussi `select` (pagination par offset)",
          recu2, "abort")


def test_plancher_de_skill():
    """⛔ LE BANC DE LA PANNE DES 12-14/08, ET IL SAIT ÉCHOUER.

    Trois nuits de scoring perdues sur `HTTP 400 — numeric field
    overflow` : `skill_clim` est un `numeric(8,4)` et valait −35 980,
    `skill` (un `real`, qui passait) −2 573 000. Cause unique :
    `1 − MSE_modèle / MSE_référence` avec une référence quasi nulle,
    c'est-à-dire une journée où le vent n'a pas bougé.

    Ce banc tient les deux moitiés de la réponse : sous le plancher on
    rend `None` — et `beats_persist` AUSSI, parce qu'un `false` se
    lirait « ce modèle a perdu » ; au-dessus, le skill est calculé comme
    avant, au chiffre près.
    """
    print("── plancher de skill (référence quasi nulle) ──")
    zone_of = {f"pioupiou:{i}": {"zone_id": "b9:plain", "landform": "plain",
                                 "basin_id": "b9", "massif_id": "alpes-nord",
                                 "basin_uncertain": False}
               for i in range(900, 904)}

    def daily(mse_ref, mse_clim=None):
        out = []
        for j in range(3):
            d = (DAY - timedelta(days=j)).strftime("%Y-%m-%d")
            for i in range(900, 904):
                r = {"day": d, "source": "pioupiou", "station_id": str(i),
                     "model": "icon_d2", "lead_h": 24, "regime": "calm",
                     "n_hours": 12, "err_vec_med": 5.0,
                     "mse_model": 25.0, "mse_persist": mse_ref}
                if mse_clim is not None:
                    r["mse_clim"] = mse_clim
                out.append(r)
        return out

    # Le cas réel : une persistance à 0,0001 (km/h)², soit 0,01 km/h de
    # RMS. Sans plancher, skill = 1 − 25/0,0001 = −249 999.
    fine = [r for r in J.rolling_scores(daily(0.0001, 0.0001), zone_of, DAY)
            if r["zone_id"] == "b9:plain"][0]
    check("référence à 0,01 km/h de RMS → skill nul", fine["skill"], None)
    check("… et `beats_persist` nul AUSSI, pas `false`",
          fine["beats_persist"], None)
    check("… idem pour la climatologie", fine["skill_clim"], None)
    check("… et pour `beats_clim`", fine["beats_clim"], None)
    check("l'erreur absolue, elle, est intacte",
          fine["typical_err_kmh"], 5.0)

    # Juste sous le plancher, et juste au-dessus : la bascule est nette.
    check("MSE de référence 0,99 → toujours nul",
          [r for r in J.rolling_scores(daily(0.99), zone_of, DAY)
           if r["zone_id"] == "b9:plain"][0]["skill"], None)
    au_dessus = [r for r in J.rolling_scores(daily(1.0), zone_of, DAY)
                 if r["zone_id"] == "b9:plain"][0]
    check("MSE de référence 1,0 → le skill est calculé",
          au_dessus["skill"], -24.0)
    check("… et il est bien négatif : le modèle perd contre une "
          "persistance très bonne", au_dessus["beats_persist"], False)

    # Et le cas ordinaire n'a pas bougé d'un chiffre.
    normal = [r for r in J.rolling_scores(daily(100.0, 100.0), zone_of, DAY)
              if r["zone_id"] == "b9:plain"][0]
    check("cas ordinaire (MSE 25 contre 100) : skill = 0,75",
          normal["skill"], 0.75)
    check("… et le modèle bat la persistance", normal["beats_persist"], True)

    # ⛔ Le contrat de la base : aucune valeur ne peut plus déborder le
    # numeric(8,4) de `model_score_zone`, quelle que soit la référence.
    pires = J.rolling_scores(daily(1e-9, 1e-9), zone_of, DAY)
    hors = [r for r in pires
            for c in ("skill", "skill_clim", "err_sd", "pooled_err_kmh")
            if isinstance(r.get(c), (int, float)) and abs(r[c]) >= 10000]
    check("aucune valeur ne dépasse le plafond 10⁴ du numeric(8,4)",
          hors, [])


# ══════════════════════════════════════════════════════════════════
#  PRESSION (E6) — lot S1, 21/08/2026
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ CE BLOC NE TOUCHE PAS `daily_rows`, ET C'EST LE POINT. La pression
# passe par `pressure_rows`, une fonction SŒUR ; les 168 assertions qui
# précèdent couvrent du code qui n'a pas bougé d'une ligne. La preuve de
# non-régression n'est pas « le banc est vert », c'est « le diff ne
# contient pas `daily_rows` » — mais le banc vert le confirme.

def _fcst_pres(station_id, model, emitted: datetime, lat, lon,
               pmsl_at, hours=72):
    """Une ligne de prévision QUI PORTE `pmsl`."""
    t0 = int(emitted.replace(hour=0, minute=0, second=0,
                             tzinfo=timezone.utc).timestamp())
    return {
        "station_id": station_id, "source": "pioupiou",
        "lat": lat, "lon": lon, "model": model,
        "fetched_at": emitted.replace(tzinfo=timezone.utc).isoformat(),
        "t0": t0, "step_s": 3600,
        "speed": [10.0] * hours, "dir": [200.0] * hours,
        "gust": [None] * hours,
        "pmsl": [pmsl_at(i) for i in range(hours)],
    }


def _obs_pres(station_id, source, day: datetime, lat, lon, elev,
              hpa_at, kind="qff", t2m=None):
    """Une ligne d'archive d'observation qui porte une pression."""
    t0 = int(day.replace(tzinfo=timezone.utc).timestamp())
    t = [t0 + h * 3600 for h in range(24)]
    row = {"station_id": station_id, "source": source,
           "lat": lat, "lon": lon, "elev": elev, "t": t,
           "speed": [8.0] * 24, "gust": [None] * 24, "dir": [200.0] * 24}
    if source == "metar":
        row["qnh"] = [hpa_at(h) for h in range(24)]
        row["t2m"] = [t2m if t2m is not None else 12.0] * 24
    else:
        row["pres_hpa"] = [hpa_at(h) for h in range(24)]
        row["pres_kind"] = kind
    return row


def test_pression_appariement():
    day = datetime(2026, 8, 20)
    emitted = day                      # offset 0 → +6 h
    # Le point de prévision, à 45,00 N / 6,00 E, 400 m (DEM).
    snaps = {0: [_fcst_pres("1", "ecmwf_ifs025", emitted, 45.0, 6.0,
                            lambda i: 1013.0 + 0.1 * (i % 24)),
                 _fcst_pres("1", "gfs_seamless_x", emitted, 45.0, 6.0,
                            lambda i: 1016.0 + 0.1 * (i % 24))],
             1: [], 2: []}
    zone_of = {"pioupiou:1": {"dem_alt_m": 400},
               "mf:AAA": {"dem_alt_m": 380},
               "mf:LOIN": {"dem_alt_m": 380},
               "mf:HAUT": {"dem_alt_m": 1900},
               "infoclimat:IC1": {"dem_alt_m": 390},
               "metar:LFXX": {"dem_alt_m": 380}}

    # AAA est à ~15 km à l'est ; LOIN à ~160 km ; HAUT est proche mais
    # 1 500 m plus haut ET au-dessus du plafond absolu.
    obs = [
        _obs_pres("AAA", "mf", day, 45.0, 6.19, 380,
                  lambda h: 1013.0 + 0.1 * h),
        _obs_pres("LOIN", "mf", day, 45.0, 8.03, 380,
                  lambda h: 1013.0 + 0.1 * h),
        _obs_pres("HAUT", "mf", day, 45.01, 6.01, 1900,
                  lambda h: 1013.0 + 0.1 * h),
        _obs_pres("IC1", "infoclimat", day, 45.02, 6.02, 390,
                  lambda h: 1015.6 + 0.1 * h),     # offset de calage +2,6
        _obs_pres("LFXX", "metar", day, 45.03, 6.03, 380,
                  lambda h: 1013.0 + 0.1 * h, kind="qnh", t2m=12.0),
    ]
    rows, bilan = J.pressure_rows(day, snaps, obs, zone_of)
    par = {(r["source"], r["station_id"], r["model"]): r for r in rows}

    check("la station proche est notée (2 modèles)",
          sorted(k[2] for k in par if k[1] == "AAA"),
          ["ecmwf_ifs025", "gfs_seamless_x"])
    check("… et la ligne est clé par la STATION, pas par le point Pioupiou",
          (par[("mf", "AAA", "ecmwf_ifs025")]["source"],
           par[("mf", "AAA", "ecmwf_ifs025")]["station_id"]), ("mf", "AAA"))
    check("… avec le point de prévision publié",
          (par[("mf", "AAA", "ecmwf_ifs025")]["pair_source"],
           par[("mf", "AAA", "ecmwf_ifs025")]["pair_station_id"]),
          ("pioupiou", "1"))
    check("… et la distance, arrondie mais pas cachée",
          14 < par[("mf", "AAA", "ecmwf_ifs025")]["pair_km"] < 16, True)
    check("… et le dénivelé", par[("mf", "AAA", "ecmwf_ifs025")]["pair_dz_m"],
          20.0)

    check("la station à 160 km n'est PAS notée — et pas notée à zéro",
          [k for k in par if k[1] == "LOIN"], [])
    check("la station à 1 900 m non plus (plafond absolu)",
          [k for k in par if k[1] == "HAUT"], [])

    # ECMWF colle à l'observation de AAA : erreur nulle des deux côtés.
    r_ok = par[("mf", "AAA", "ecmwf_ifs025")]
    check("modèle qui colle → erreur absolue nulle", r_ok["pres_err_med"], 0.0)
    check("… et tendance nulle", r_ok["ptend_err_med"], 0.0)
    r_bad = par[("mf", "AAA", "gfs_seamless_x")]
    check("modèle décalé de 3 hPa → l'erreur absolue le voit",
          r_bad["pres_err_med"], 3.0)
    check("… mais pas la tendance (le décalage est constant)",
          r_bad["ptend_err_med"], 0.0)

    # ⛔ Infoclimat : la ligne EXISTE (sa tendance vaut), mais son erreur
    # absolue est `None` — jamais 0, qui se lirait comme un sans-faute.
    r_ic = par[("infoclimat", "IC1", "ecmwf_ifs025")]
    check("Infoclimat : pas d'erreur absolue", r_ic["pres_err_med"], None)
    check("… mais une tendance, elle", r_ic["ptend_err_med"], 0.0)
    check("… et le drapeau qui le dit", r_ic["calibrated"], False)
    check("METAR est calibré, lui",
          par[("metar", "LFXX", "ecmwf_ifs025")]["calibrated"], True)
    check("… et sa convention est retenue comme QNH",
          par[("metar", "LFXX", "ecmwf_ifs025")]["pres_kind"], "qnh")

    check("le bilan dit combien de points portaient `pmsl`",
          "1 points de prévision portent `pmsl`" in bilan, True)
    check("… et compte les refusées", "hors rayon" in bilan, True)


def test_pression_refus():
    day = datetime(2026, 8, 20)
    snaps = {0: [_fcst_pres("1", "ecmwf_ifs025", day, 45.0, 6.0,
                            lambda i: 1013.0)], 1: [], 2: []}
    zone_of = {"pioupiou:1": {"dem_alt_m": 400}, "mf:X": {"dem_alt_m": 380}}

    # Un QNH sans température ne se rabat PAS sur le brut : la station
    # disparaît, elle ne produit pas une ligne fausse.
    sans_t = _obs_pres("X", "metar", day, 45.0, 6.05, 380, lambda h: 1013.0,
                       kind="qnh")
    sans_t["t2m"] = [None] * 24
    zone_of["metar:X"] = {"dem_alt_m": 380}
    rows, bilan = J.pressure_rows(day, snaps, [sans_t], zone_of)
    check("QNH sans température → aucune ligne", rows, [])
    check("… et le motif est compté", "no-temp" in bilan, True)

    # `pres_kind` absent : « on n'apparie pas, on compte » (spec S1).
    sans_kind = _obs_pres("X", "mf", day, 45.0, 6.05, 380, lambda h: 1013.0)
    del sans_kind["pres_kind"]
    rows, bilan = J.pressure_rows(day, snaps, [sans_kind], zone_of)
    check("`pres_kind` absent → aucune ligne", rows, [])
    check("… et le motif est compté", "unknown-kind" in bilan, True)

    # Aucun modèle ne porte `pmsl` : aucune ligne, et pas une erreur.
    sans_pmsl = {0: [fcst_line("1", "ecmwf_ifs025", day, lambda i: 10.0)],
                 1: [], 2: []}
    bonne = _obs_pres("X", "mf", day, 45.0, 6.05, 380, lambda h: 1013.0)
    rows, bilan = J.pressure_rows(day, sans_pmsl, [bonne], zone_of)
    check("aucune prévision de `pmsl` → aucune ligne", rows, [])
    check("… et le bilan le dit", "0 points de prévision" in bilan, True)

    # Moins de MIN_HOURS_DAILY heures appariables : rien.
    court = _obs_pres("X", "mf", day, 45.0, 6.05, 380, lambda h: 1013.0)
    for champ in ("t", "pres_hpa", "speed", "gust", "dir"):
        court[champ] = court[champ][:3]
    rows, _ = J.pressure_rows(day, snaps, [court], zone_of)
    check("moins de 6 heures appariées → aucune ligne", rows, [])


def test_pression_appariement_stable_entre_echeances():
    """⚠️ La même station doit être notée contre LE MÊME point à toutes
    les échéances — sinon +6 h et +48 h compareraient deux géométries."""
    day = datetime(2026, 8, 20)
    snaps = {}
    for offset in (0, 1, 2):
        emitted = day - timedelta(days=offset)
        # Deux points de prévision : le proche n'apparaît qu'à J-0, le
        # lointain aux trois. Un appariement calculé par échéance
        # basculerait de l'un à l'autre.
        lignes = [_fcst_pres("LOINTAIN", "ecmwf_ifs025", emitted, 45.0, 6.40,
                             lambda i: 1013.0, hours=72)]
        if offset == 0:
            lignes.append(_fcst_pres("PROCHE", "ecmwf_ifs025", emitted,
                                     45.0, 6.05, lambda i: 1013.0, hours=72))
        snaps[offset] = lignes
    zone_of = {"pioupiou:PROCHE": {"dem_alt_m": 400},
               "pioupiou:LOINTAIN": {"dem_alt_m": 400},
               "mf:X": {"dem_alt_m": 380}}
    obs = [_obs_pres("X", "mf", day, 45.0, 6.0, 380, lambda h: 1013.0)]
    rows, _ = J.pressure_rows(day, snaps, obs, zone_of)
    points = {r["pair_station_id"] for r in rows}
    check("un seul point de prévision pour toutes les échéances",
          points, {"PROCHE"})
    check("… et donc une seule échéance notée (le proche n'existe qu'à J-0)",
          sorted(r["lead_h"] for r in rows), [6])


# ══════════════════════════════════════════════════════════════════
#  LOT S0.6 — UNE PARTIE MANQUANTE EST VUE, COMPTÉE ET NOMMÉE
# ══════════════════════════════════════════════════════════════════
#
#  ⛔ C'EST LE PIÈGE CENTRAL DU LOT, ET CE BANC EST TOUT CE QUI SÉPARE
#  « la nuit a été notée sur deux modèles » de « la nuit a été notée sur
#  deux modèles ET PERSONNE NE L'A SU ».
#
#  ⚠️ CE BANC SAIT ÉCHOUER, et on peut le vérifier en une ligne :
#  remplacer dans `score.py::fcst_parties` le compte tiré du manifeste
#  par « les clés qui existent » — c'est-à-dire écrire le défaut — fait
#  tomber `parties_attendues == 2` et les deux assertions qui NOMMENT
#  les modèles. C'est la mutation M1 du §8 de la note.

def _ecrire_gz(racine, cle, lignes):
    import gzip as _gz
    import json as _js
    p = racine / cle
    p.parent.mkdir(parents=True, exist_ok=True)
    with _gz.open(p, "wt", encoding="utf-8") as fh:
        for r in lignes:
            fh.write(_js.dumps(r) + "\n")
    return p


def _ligne(model):
    return {"source": "pioupiou", "station_id": "1", "model": model,
            "t0": DAY_MS // 1000, "step_s": 3600, "speed": [10.0, 11.0]}


def _manifeste(jour, parties, version=1):
    detail = []
    for i, (cle, modeles) in enumerate(parties, 1):
        detail.append({"i": i, "cle": cle, "modeles": modeles,
                       "n_vars": 6, "poids_point": 0.6 * len(modeles)})
    return {"version": version, "flux": "fcst", "jour": f"{jour:%Y-%m-%d}",
            "parties": len(parties), "n_points": 3,
            "poids_point_total": 5.8, "detail": detail,
            "ecrit_par": "banc", "ecrit_a": "2026-08-23T03:15:04Z"}


def test_partition_parties_manquantes():
    import json as _js
    import pathlib
    import tempfile

    ALT = ["ecmwf_ifs025", "gfs_global"]
    SURF = ["meteofrance_arome_france_hd", "meteofrance_arpege_europe",
            "icon_eu", "dmi_harmonie", "chmi_aladin", "icon_d2",
            "meteoswiss_icon_ch2"]
    k1 = J.fcst_key(DAY)
    k2 = J.fcst_key(DAY, 2)

    check("la partie 1 garde la clé HISTORIQUE, au caractère près",
          k1, f"fcst/2026/08/fcst_2026-08-05.ndjson.gz")
    check("la partie 2 prend `_p2`",
          k2, "fcst/2026/08/fcst_2026-08-05_p2.ndjson.gz")
    check("le manifeste est LATÉRAL, jamais une ligne de l'archive",
          J.fcst_manifeste_key(DAY),
          "fcst/2026/08/fcst_2026-08-05.manifeste.json")

    # ── 1. Journée d'AVANT la partition : pas de manifeste, une clé ──
    #     ⚠️ Sans date de bascule dans le code : les 15 nuits déjà
    #     écrites doivent rester lisibles telles quelles.
    d = pathlib.Path(tempfile.mkdtemp(prefix="s06-avant-"))
    _ecrire_gz(d, k1, [_ligne(m) for m in ALT + SURF])
    rows, b = J.fcst_parties(d, DAY)
    check("avant la partition : les 9 modèles sont lus", len(rows), 9)
    check("avant la partition : l'état le DIT", b["etat"], "avant_partition")
    check("avant la partition : 1 partie attendue", b["parties_attendues"], 1)

    # ── 2. Deux parties déclarées, deux présentes ────────────────────
    d = pathlib.Path(tempfile.mkdtemp(prefix="s06-ok-"))
    (d / "fcst/2026/08").mkdir(parents=True)
    (d / J.fcst_manifeste_key(DAY)).write_text(
        _js.dumps(_manifeste(DAY, [(k1, ALT), (k2, SURF)])), encoding="utf-8")
    _ecrire_gz(d, k1, [_ligne(m) for m in ALT])
    _ecrire_gz(d, k2, [_ligne(m) for m in SURF])
    rows, b = J.fcst_parties(d, DAY)
    check("2 parties présentes : toutes les lignes sont là", len(rows), 9)
    check("2/2 parties lues", (b["parties_lues"], b["parties_attendues"]),
          (2, 2))
    check("rien à signaler", b["etat"], "ok")

    # ── 3. ⭐⭐ LA PARTIE 2 MANQUE — VUE, COMPTÉE, NOMMÉE ────────────
    d = pathlib.Path(tempfile.mkdtemp(prefix="s06-trou-"))
    (d / "fcst/2026/08").mkdir(parents=True)
    (d / J.fcst_manifeste_key(DAY)).write_text(
        _js.dumps(_manifeste(DAY, [(k1, ALT), (k2, SURF)])), encoding="utf-8")
    _ecrire_gz(d, k1, [_ligne(m) for m in ALT])
    # …et RIEN pour la partie 2. C'est la nuit où la passe de 04:35 a
    # échoué.
    rows, b = J.fcst_parties(d, DAY)
    check("⭐ VUE : l'état nomme le défaut", b["etat"], "partie_manquante")
    check("⭐ COMPTÉE : 1 partie lue sur 2 ATTENDUES — le 2 vient du "
          "manifeste, jamais des clés qui existent",
          (b["parties_lues"], b["parties_attendues"]), (1, 2))
    check("⭐ NOMMÉE : les sept modèles perdus sont listés",
          sorted(b["modeles_manquants"]), sorted(SURF))
    check("et la partie manquante porte son numéro et sa clé",
          (b["manquantes"][0]["i"], b["manquantes"][0]["cle"]), (2, k2))
    check("les lignes de la partie 1 ne sont PAS perdues au passage",
          len(rows), 2)
    ligne = J.dire_bilan_parties(b, 0)
    check("⭐ le journal COMPTE : « 1/2 parties »", "1/2 parties" in ligne, True)
    check("⭐ le journal NOMME : `icon_eu` est écrit en toutes lettres",
          "icon_eu" in ligne, True)
    check("⭐ et le journal nomme SON FLUX — sinon « 1 partie sur 2 » se "
          "lit « il manque un flux sur trois »", "`fcst/`" in ligne, True)

    # ── 4. ⛔ Manifeste perdu alors qu'une partie 2 existe ───────────
    #     Le cas que le S0.4 laissait ouvert. On garde les lignes, mais
    #     on REFUSE de dire combien de parties étaient attendues.
    d = pathlib.Path(tempfile.mkdtemp(prefix="s06-sansmanif-"))
    _ecrire_gz(d, k1, [_ligne(m) for m in ALT])
    _ecrire_gz(d, k2, [_ligne(m) for m in SURF])
    rows, b = J.fcst_parties(d, DAY)
    check("manifeste perdu + partie 2 présente = INCIDENT, pas "
          "« avant la partition »",
          b["etat"], "manifeste_absent_mais_partie_2_presente")
    check("⛔ et surtout : on REFUSE de deviner combien de parties",
          b["parties_attendues"], None)
    check("la donnée, elle, n'est pas jetée", len(rows), 9)

    # ── 5. ⛔ Ni manifeste ni donnée ─────────────────────────────────
    d = pathlib.Path(tempfile.mkdtemp(prefix="s06-rien-"))
    rows, b = J.fcst_parties(d, DAY)
    check("rien du tout = incident, pas « journée normale »",
          b["etat"], "rien_produit")
    check("et zéro ligne", len(rows), 0)

    # ── 6. Manifeste d'une version inconnue ─────────────────────────
    d = pathlib.Path(tempfile.mkdtemp(prefix="s06-v99-"))
    (d / "fcst/2026/08").mkdir(parents=True)
    (d / J.fcst_manifeste_key(DAY)).write_text(
        _js.dumps(_manifeste(DAY, [(k1, ALT), (k2, SURF)], version=99)),
        encoding="utf-8")
    _ecrire_gz(d, k1, [_ligne(m) for m in ALT])
    rows, b = J.fcst_parties(d, DAY)
    check("une version inconnue ARRÊTE la lecture au lieu de la deviner",
          b["etat"], "manifeste_version_inconnue")

    # ── 7. ⚠️ LES DEUX AUTRES FLUX NE SONT PAS DES PARTIES ──────────
    #     `snapshot_rows` en lit TROIS ; le manifeste ne parle que de
    #     `fcst/`. Un `fcstarome` présent ne doit pas faire croire à une
    #     partie de plus, ni son absence à une partie manquante.
    d = pathlib.Path(tempfile.mkdtemp(prefix="s06-flux-"))
    _ecrire_gz(d, k1, [_ligne(m) for m in ALT])
    _ecrire_gz(d, J.fcst_arome_key(DAY), [_ligne("arome_r2")])
    _ecrire_gz(d, J.fcst_agrume_key(DAY), [_ligne("agrume")])
    rows, b = J.snapshot_rows_et_bilan(d, DAY)
    check("les trois flux sont lus", len(rows), 4)
    check("mais le bilan ne compte que les parties de `fcst/`",
          (b["flux"], b["parties_lues"], b["parties_attendues"]),
          ("fcst", 1, 1))
    check("`snapshot_rows` rend toujours une simple liste (3 appelants)",
          len(J.snapshot_rows(d, DAY)), 4)


def test_flux_reduit_lu_et_pas_compte_comme_partie():
    """⭐ LE FLUX DU GROUPE RÉDUIT (lot S0.11, 23/08/2026).

    Deux propriétés, et elles ne disent pas la même chose :

      (a) ⭐ `snapshot_rows` LIT le flux `fcstreduit/` — sans cette
          ligne, la nuit est collectée, payée en quota, écrite sur R2…
          et jamais notée. Le run passerait au vert et les 2 942
          candidates resteraient en `regime = "unknown"` ;
      (b) ⛔ et il n'est PAS compté comme une partie de `fcst/`. La
          partition du S0.6 découpe UNE population par groupe de
          modèles ; ici c'est une AUTRE population. Les confondre ferait
          basculer la nuit Pioupiou en `partie_manquante` — l'incident
          que le S0.9 vient d'éteindre.
    """
    import pathlib
    import tempfile

    ALT = ["ecmwf_ifs025", "gfs_global"]
    k1 = J.fcst_key(DAY)

    check("la clé du flux réduit, au caractère près",
          J.fcst_reduit_key(DAY),
          "fcstreduit/2026/08/fcstreduit_2026-08-05.ndjson.gz")

    d = pathlib.Path(tempfile.mkdtemp(prefix="s11-lecture-"))
    _ecrire_gz(d, k1, [_ligne(m) for m in ALT])
    rows_avant, b_avant = J.snapshot_rows_et_bilan(d, DAY)

    # La même nuit, plus le flux réduit — sur une AUTRE population.
    reduit = []
    for m in ["ecmwf_ifs025", "gfs_global", "icon_d2",
              "meteoswiss_icon_ch2", "icon_eu"]:
        r = _ligne(m)
        r["source"], r["station_id"] = "windsmobi", "holfuy-918"
        reduit.append(r)
    _ecrire_gz(d, J.fcst_reduit_key(DAY), reduit)
    rows, b = J.snapshot_rows_et_bilan(d, DAY)

    check("⭐ (a) le flux réduit EST lu par `snapshot_rows`",
          len(rows) - len(rows_avant), 5)
    check("⭐ (a) et ses cinq modèles sont là, sous LEURS noms (pas de "
          "suffixe `_reduit` : c'est ce qui donne k = 6 au tau du S3)",
          sorted({r["model"] for r in rows if r["source"] == "windsmobi"}),
          ["ecmwf_ifs025", "gfs_global", "icon_d2", "icon_eu",
           "meteoswiss_icon_ch2"])
    check("⛔ (b) le bilan de `fcst/` est INCHANGÉ — le flux réduit n'est "
          "pas une partie",
          (b["flux"], b["parties_lues"], b["parties_attendues"], b["etat"]),
          (b_avant["flux"], b_avant["parties_lues"],
           b_avant["parties_attendues"], b_avant["etat"]))
    check("⛔ (b) … et il reste « avant_partition », pas "
          "« partie_manquante »", b["etat"], "avant_partition")

    # ⚠️ Et son ABSENCE ne fabrique pas non plus une partie manquante :
    # une nuit où le timer de 05:00 n'a pas tourné est une nuit sans ce
    # flux, pas une nuit trouée de `fcst/`.
    d2 = pathlib.Path(tempfile.mkdtemp(prefix="s11-absent-"))
    _ecrire_gz(d2, k1, [_ligne(m) for m in ALT])
    _, b2 = J.snapshot_rows_et_bilan(d2, DAY)
    check("⚠️ l'ABSENCE du flux réduit ne trouble pas le bilan de `fcst/`",
          b2["etat"], "avant_partition")


def test_metar_entre_dans_la_notation_du_vent():
    """⭐ ARBITRAGE N°8 DU S0.3, TRANCHÉ LE 23/08 : `obsmetar_key` entre
    dans `OBS_KEY_FUNCS`.

    ⛔ Et cette ligne ne coûte pas un pondéré : `arome_fcst.py` écrit
    déjà 278 lignes METAR par nuit, gratuitement, À LA COORDONNÉE de
    chaque aérodrome. La raison qui écartait METAR du vent — « aucun
    point de prévision à sa propre coordonnée » — est tombée le 22/08.
    """
    import pathlib
    import tempfile

    check("⭐ `obsmetar_key` est dans `OBS_KEY_FUNCS`",
          J.obsmetar_key in J.OBS_KEY_FUNCS, True)
    check("… et elle y est UNE fois", J.OBS_KEY_FUNCS.count(J.obsmetar_key), 1)
    check("les six archives d'observation de vent", len(J.OBS_KEY_FUNCS), 6)
    check("⛔ `PRES_OBS_KEY_FUNCS` est INCHANGÉE (4 flux de pression)",
          len(J.PRES_OBS_KEY_FUNCS), 4)

    d = pathlib.Path(tempfile.mkdtemp(prefix="s11-metar-"))
    _ecrire_gz(d, J.obsmetar_key(DAY),
               [{"source": "metar", "station_id": "LFLB",
                 "t": [DAY_MS // 1000], "speed": [20.4], "dir": [90.0]}])
    rows = J.all_obs_rows(d, DAY)
    check("⭐ et `all_obs_rows` les lit désormais",
          [(r["source"], r["station_id"]) for r in rows], [("metar", "LFLB")])


def test_rang_sur_journee_incomplete():
    """⛔ Un rang publié sur une journée incomplète doit le DIRE."""
    trou = {0: {"flux": "fcst", "etat": "partie_manquante",
                "parties_attendues": 2, "parties_lues": 1,
                "modeles_manquants": ["icon_eu"]},
            1: {"flux": "fcst", "etat": "ok"},
            2: {"flux": "fcst", "etat": "avant_partition"}}
    complet = {0: {"flux": "fcst", "etat": "ok"},
               1: {"flux": "fcst", "etat": "avant_partition"}}

    rows = [
        {"model": "a", "rank": 1, "rank_reason": "ok"},
        {"model": "b", "rank": 2, "rank_reason": "ok"},
        # ⚠️ Déjà non classée pour une raison STATISTIQUE : on n'y
        # touche pas. Il n'y a aucun rang trompeur à qualifier, et
        # écraser la raison détruirait un fait par case au profit d'un
        # fait par journée.
        {"model": "c", "rank": None, "rank_reason": "window_too_short"},
        {"model": "d", "rank": None, "rank_reason": "single_model"},
    ]
    n = J.marquer_parties_manquantes(rows, trou)
    check("seuls les rangs PUBLIÉS sont qualifiés", n, 2)
    check("le rang reste — un classement absent et un classement partiel "
          "se lisent pareil, et le second au moins se dit",
          [r["rank"] for r in rows], [1, 2, None, None])
    check("⭐ et il porte `partie_manquante`",
          [r["rank_reason"] for r in rows[:2]],
          ["partie_manquante", "partie_manquante"])
    check("⚠️ les raisons STATISTIQUES ne sont pas écrasées",
          [r["rank_reason"] for r in rows[2:]],
          ["window_too_short", "single_model"])

    rows2 = [{"model": "a", "rank": 1, "rank_reason": "ok"}]
    check("une journée complète ne qualifie rien",
          J.marquer_parties_manquantes(rows2, complet), 0)
    check("et `avant_partition` n'est PAS un incident",
          rows2[0]["rank_reason"], "ok")

    lignes = J.collect_part_rows(DAY, trou)
    check("une ligne de base par journée d'ÉMISSION, pas une par nuit "
          "notée — sinon deux incidents sur trois disparaissent",
          [r["day"] for r in lignes],
          ["2026-08-05", "2026-08-04", "2026-08-03"])
    check("et elle nomme son flux", {r["flux"] for r in lignes}, {"fcst"})
    check("⛔ `parties_attendues` est NUL quand on ne sait pas, jamais 0",
          J.collect_part_rows(
              DAY, {0: {"flux": "fcst", "parties_lues": 2,
                        "etat": "manifeste_absent_mais_partie_2_presente"}}
          )[0]["parties_attendues"], None)


def test_les_deux_cles_fcst_sont_la_meme_chaine():
    """`collect.py` et `score.py` écrivent la forme de clé DEUX FOIS.

    ⚠️ C'est délibéré — `score.py` ne doit dépendre ni de numpy ni du
    paquet `agrume/`, donc il n'importe pas `collect`. Mais deux
    définitions d'une même chaîne, c'est une divergence qui attend son
    heure : le jour où l'une prend un `_p0{i}` et l'autre un `_p{i}`,
    la notation lirait une clé que la collecte n'écrit jamais, et
    l'archive serait « complète » des deux côtés.
    """
    import collect as C
    for partie in (1, 2, 3):
        check(f"clé de la partie {partie} : collect == score",
              C.fcst_cle(DAY, partie), J.fcst_key(DAY, partie))
    check("manifeste : collect == score",
          C.manifeste_cle(DAY), J.fcst_manifeste_key(DAY))
    check("et le flux partitionné porte le même nom des deux côtés",
          C.FLUX_PARTITIONNE, "fcst")
    check("la version de manifeste écrite est celle qui est lue",
          C.MANIFESTE_VERSION, J.MANIFESTE_VERSION_LUE)
    # Le manifeste réellement construit par `collect.py` doit être lu par
    # `score.py` sans traduction — c'est le seul contrat entre les deux.
    m = C.construire_manifeste(DAY, 657)
    check("le manifeste construit déclare autant de parties que de groupes",
          m["parties"], len(C.groupes_requete()))
    check("il nomme son flux", m["flux"], "fcst")
    check("et son poids par point est celui de `poids_par_point()`, "
          "dérivé et jamais recopié",
          m["poids_point_total"], round(C.poids_par_point(), 4))



# ══════════════════════════════════════════════════════════════════
#  LOT S2 — L'ERREUR CORRIGÉE DU BIAIS DE SITE (22/08/2026)
# ══════════════════════════════════════════════════════════════════

def _archive_biaisee(root, jours, facteur, station="900", model="icon_d2",
                     bruit=None):
    """Écrit `n` journées où l'observation vaut `facteur ×` la prévision.

    Le modèle est donc PARFAIT à ce facteur près : c'est le cas d'école
    du §S2 — brut mauvais, corrigé quasi nul.

    ⚠️ UN SOCLE DE 12 km/h SOUS LA BRISE, et ce n'est pas cosmétique.
    `brise()` seule rend zéro douze heures sur vingt-quatre : la MÉDIANE
    de l'erreur d'une telle journée est alors dominée par des heures où
    prévu = observé = 0, et elle reste petite quel que soit le biais.
    Le premier jet de ce banc l'a payé — il affirmait « brut mauvais »
    sur une journée dont l'erreur médiane valait 1,8 km/h. Le socle met
    aussi les deux côtés au-dessus de `DIR_MIN_WIND_KMH` (5 km/h), donc
    l'erreur reste VECTORIELLE de bout en bout, comme en production.
    """
    import gzip as _gz
    import json as _json

    def prevu(i):
        return round(12.0 + brise(i % 24), 3)

    for d in jours:
        fk = root / J.fcst_key(d)
        fk.parent.mkdir(parents=True, exist_ok=True)
        fk.write_bytes(_gz.compress(_json.dumps(
            fcst_line(station, model, d, prevu,
                      aloft=(30.0, 10.0))).encode()))
        ok = root / J.obs_key(d)
        ok.parent.mkdir(parents=True, exist_ok=True)

        def vitesse(h, f=facteur):
            return round(f * (12.0 + brise(h % 24)), 3)

        ok.write_bytes(_gz.compress(_json.dumps(
            obs_line(station, d, vitesse)).encode()))


def test_s2_correction_du_biais_de_site():
    """Les trois bancs demandés par le §S2, plus celui qui doit échouer.

    ⚠️ Le troisième est le seul qui compte vraiment : « J ne se corrige
    jamais avec J ». Les deux premiers vérifient une arithmétique ; le
    troisième vérifie qu'on n'a pas triché.
    """
    print("── lot S2 : la colonne corrigée du biais de site ──")
    import tempfile
    from pathlib import Path

    # ── 1. une balise à ×0,6 constant sur 10 jours ────────────────
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        jours = [DAY - timedelta(days=k) for k in range(11)]
        _archive_biaisee(root, jours, 0.6)
        # On remplit le cache de rejeu du plus ancien au plus récent :
        # c'est ce que fait `replay_window` nuit après nuit.
        for d in reversed(jours[1:]):
            J.replay_day(root, d, None, 0)

        prior = J.prior_biais(root, DAY)
        cle = ("pioupiou:900", "icon_d2", 6)
        check("un antécédent existe pour la balise biaisée",
              cle in prior, True)
        pente, cap, n_j = prior[cle]
        check("… et sa pente retrouve le ×0,6 imposé", pente, 0.6, 0.02)
        check("… sur les 10 journées antérieures", n_j, 10)

        rows = J.replay_day(root, DAY, None, 0)
        ligne = next(r for r in rows if r["lead_h"] == 6)
        # 4,8 = 0,4 × 12 : l'erreur médiane est celle du socle, les
        # heures de brise étant minoritaires dans une journée.
        check("le BRUT porte l'entièreté du biais (0,4 × le socle)",
              ligne["err_vec_med"], 4.8, 0.01)
        check("le CORRIGÉ est quasi nul",
              ligne["err_vec_med_corr"] < 0.05, True)
        check("… et `bias_n_days` dit sur combien de jours il repose",
              ligne["bias_n_days"], 10)
        check("`mse_model_corr` s'effondre aussi",
              ligne["mse_model_corr"] < 0.2, True)

        # ⛔ LE BANC QUI DOIT SAVOIR ÉCHOUER. Sans antécédent, la colonne
        # se tait — elle ne retombe pas sur le biais du jour même.
        rows_nu, _ = J.daily_rows(
            DAY, {off: J.snapshot_rows(root, DAY - timedelta(days=off), None)
                  for off in J.LEAD_BY_OFFSET},
            J.all_obs_rows(root, DAY, None),
            J.all_obs_rows(root, DAY - timedelta(days=1), None), 0)
        nue = next(r for r in rows_nu if r["lead_h"] == 6)
        check("sans antécédent, `err_vec_med_corr` est NUL, pas égal au brut",
              nue["err_vec_med_corr"], None)
        check("… et le brut, lui, n'a pas bougé d'un cheveu",
              nue["err_vec_med"], ligne["err_vec_med"])

    # ── 2. une balise SANS biais : les deux colonnes se confondent ─
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        jours = [DAY - timedelta(days=k) for k in range(11)]
        _archive_biaisee(root, jours, 1.0)
        for d in reversed(jours[1:]):
            J.replay_day(root, d, None, 0)
        rows = J.replay_day(root, DAY, None, 0)
        ligne = next(r for r in rows if r["lead_h"] == 6)
        check("sans biais, la pente antérieure vaut 1",
              J.prior_biais(root, DAY)[("pioupiou:900", "icon_d2", 6)][0],
              1.0, 0.01)
        check("… et les deux colonnes sont identiques",
              ligne["err_vec_med_corr"], ligne["err_vec_med"], 0.05)

    # ── 3. J NE SE CORRIGE JAMAIS AVEC J ──────────────────────────
    # Dix journées à ×0,6, puis une onzième à ×1,4. Si la correction
    # avait vu le jour J, elle appliquerait ×1,4 et l'erreur tomberait à
    # zéro. Elle applique ×0,6 sur une journée qui va dans l'autre sens,
    # donc elle EMPIRE l'erreur — et c'est la preuve qu'elle n'a pas
    # triché. Un banc qui ne peut pas se retourner contre son auteur ne
    # prouve rien.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        anciens = [DAY - timedelta(days=k) for k in range(1, 11)]
        _archive_biaisee(root, anciens, 0.6)
        for d in reversed(anciens):
            J.replay_day(root, d, None, 0)
        _archive_biaisee(root, [DAY], 1.4)
        rows = J.replay_day(root, DAY, None, 0)
        ligne = next(r for r in rows if r["lead_h"] == 6)
        check("la pente appliquée est celle du PASSÉ (0,6), pas celle du jour",
              J.prior_biais(root, DAY)[("pioupiou:900", "icon_d2", 6)][0],
              0.6, 0.02)
        check("⛔ le corrigé est donc PIRE que le brut ce jour-là",
              ligne["err_vec_med_corr"] > ligne["err_vec_med"], True)
        check("… et `bias_slope` du jour, lui, vaut bien 1,4 "
              "(il nourrira DEMAIN, pas aujourd'hui)",
              ligne["bias_slope"], 1.4, 0.02)


def test_s2_estimateur_sans_selection():
    """⛔ Le banc qui démontre le défaut de `S.site_bias`.

    ⚠️ LE PREMIER JET DE CE BANC SIMULAIT LA CAUSALITÉ À L'ENVERS, et il
    est resté vert pour une mauvaise raison. Il posait `obs = prev +
    bruit` : dans ce monde-là, `E[obs | prev] = prev` exactement, donc
    conditionner sur `prev` ne biaise RIEN et `site_bias` rendait bien 1.
    C'est le contraire de la réalité — c'est la PRÉVISION qui se trompe,
    pas l'observation.

    Le bon montage est donc : une vérité, une observation qui la mesure,
    et une prévision qui vaut `vérité + erreur centrée`. Sélectionner
    les heures où la PRÉVISION est haute sélectionne alors les heures où
    son erreur est POSITIVE — et `obs/prev` y est mécaniquement < 1
    alors que le modèle ne surestime rien en cumul.

    C'est exactement ce qui a été mesuré en production le 22/08 :
    `site_bias` rendait 0,761 sur ECMWF quand Σobs/Σprev valait 1,112.

    ⓘ ET LA PENTE DES MOINDRES CARRÉS N'EST PAS 1 NON PLUS, ce qui est
    normal et voulu : elle vaut Var(vérité)/(Var(vérité)+Var(erreur)),
    l'atténuation classique. Ce n'est pas un défaut, c'est SA
    DÉFINITION — elle rend le facteur qui minimise l'erreur quadratique,
    pas le facteur qui « annule un biais ». Le banc vérifie donc la
    seule chose qui compte : appliquée, elle fait mieux que ne rien
    faire ET mieux que `site_bias`.

    ⚠️ ET LA LOI DU VENT COMPTE AUTANT QUE LA CAUSALITÉ. Le deuxième jet
    tirait la vérité UNIFORMÉMENT sur [4, 24] km/h : médiane 14, donc le
    seuil de 8 km/h ne coupait qu'une queue étroite et l'effet ne se
    voyait presque pas (0,956 au lieu de 1). Le vent réel est très
    dissymétrique — médiane mesurée le 22/08 sur 40 539 heures :
    **7,12 km/h**. Le seuil de 8 tombe donc en plein milieu de la
    distribution, et c'est LÀ qu'il mord. On tire ici une loi
    exponentielle de médiane ~5 km/h, et l'estimateur rend 0,78 : la
    même valeur que sur les vraies balises.

    Générateur affine à graine fixe : un banc qui bouge d'une exécution
    à l'autre n'est pas un banc.
    """
    print("── lot S2 : l'estimateur, avec et sans sélection ──")
    etat = [7]

    def alea():
        etat[0] = (1103515245 * etat[0] + 12345) % (1 << 31)
        return etat[0] / (1 << 31)                 # dans [0 ; 1[

    paires = []
    for i in range(6000):
        u = max(1e-6, alea())
        verite = min(45.0, -7.5 * math.log(u))     # loi du vent, dissymétrique
        obs = verite                               # la mesure EST la vérité
        prev = max(0.3, verite + 16.0 * (alea() - 0.5))   # erreur centrée
        paires.append(S.VerifPair(t=i * 3_600_000, fcst_speed=prev,
                                  fcst_dir=200.0, obs_speed=obs,
                                  obs_dir=200.0, n_obs=5))

    somme_o = sum(p.obs_speed for p in paires)
    somme_f = sum(p.fcst_speed for p in paires)
    #: La version d'AVANT le second commit du lot S2, reproduite ici
    #: pour que ce banc dise encore ce qu'il a coûté de la remplacer.
    #: ⚠️ Elle ne s'obtient plus par `S.site_bias` : celui-ci est réparé,
    #: et l'appeler ici ne comparerait plus que la pente à elle-même.
    ancien = S.median([p.obs_speed / p.fcst_speed for p in paires
                       if p.fcst_speed >= S.BIAS_MIN_WIND_KMH])
    pente = J.pente_du_jour(paires)

    check("le vent simulé a bien la médiane basse du vent réel (~5-7 km/h)",
          4.0 < S.median([p.obs_speed for p in paires]) < 8.0, True)
    check("en cumul, ce modèle ne surestime pour ainsi dire rien "
          "(Σobs/Σprev ≈ 1)", somme_o / somme_f, 1.0, 0.09)
    check("⛔ l'ANCIEN estimateur annonçait une surestimation de ~22 % "
          "(< 0,80)", ancien < 0.80, True)
    check("… et le miroir le prouve : en conditionnant sur l'OBSERVATION, "
          "le même calcul passe AU-DESSUS de 1",
          S.median([p.obs_speed / p.fcst_speed for p in paires
                    if p.obs_speed >= 8.0]) > 1.0, True)

    def mse(facteur):
        return sum((facteur * p.fcst_speed - p.obs_speed) ** 2
                   for p in paires) / len(paires)

    check("la pente des moindres carrés fait mieux que ne rien corriger",
          mse(pente) < mse(1.0), True)
    check("⛔ … et mieux que l'ancien, qui SUR-corrigeait",
          mse(pente) < mse(ancien), True)
    check("la pente est bien entre le rapport conditionné et 1",
          ancien < pente < 1.0, True)
    check("… et l'écart pente / ancien est bien celui du seuil",
          pente - ancien > 0.06, True)
    check("⛔ et depuis la réparation, `site_bias` REND la pente — "
          "une seule définition dans tout le projet",
          S.site_bias(paires, min_pairs=10).speed_ratio, pente)

    # ⓘ MESURÉ EN ÉCRIVANT CE BANC, ET C'EST UNE BONNE NOUVELLE :
    # retirer les heures sous 8 km/h ne déplace la pente que de 0,002
    # (0,8668 → 0,8649). Les moindres carrés pondèrent déjà par `prev²`,
    # donc les heures faibles ne pèsent presque rien : l'estimateur est
    # INSENSIBLE au seuil, là où la médiane de rapports en dépendait
    # entièrement. La première version de ce banc voulait prouver le
    # contraire et se trompait de propriété.
    #
    # ⛔ Là où le seuil faisait vraiment une différence, c'est le JOUR
    # CALME — celui où aucune heure n'atteint 8 km/h. L'ancien s'y
    # taisait, donc les sites abrités — ceux qui en ont le plus besoin —
    # n'avaient jamais de correction. C'est ce que ce banc tient, et
    # c'est lui qui tue le mutant « la pente reprend le seuil ».
    calme = [S.VerifPair(t=i * 3_600_000, fcst_speed=2.0 + (i % 5) * 0.5,
                         fcst_dir=200.0, obs_speed=1.4 + (i % 5) * 0.35,
                         obs_dir=200.0, n_obs=5) for i in range(12)]
    check("journée entièrement sous 8 km/h : l'ancien se taisait",
          S.median([p.obs_speed / p.fcst_speed for p in calme
                    if p.fcst_speed >= S.BIAS_MIN_WIND_KMH]), None)
    check("⛔ … la pente, elle, répond", J.pente_du_jour(calme), 0.70, 0.03)


def test_s2_memoire_du_biais():
    """`AccBiais` : le poids dépend du TEMPS ÉCOULÉ, pas du nombre d'appels.

    ⛔ Ce banc existe parce que le mutant « `decay = 1.0` » avait
    survécu au premier jeu : sur dix journées consécutives d'un biais
    CONSTANT, une moyenne pondérée et une moyenne plate rendent le même
    chiffre. Il faut un biais qui CHANGE pour que la demi-vie se voie —
    et c'est le cas qui compte, puisqu'un site dont le biais ne bouge
    jamais n'a pas besoin d'une mémoire à demi-vie.
    """
    print("── lot S2 : la mémoire du biais ──")
    # Vingt journées à ×1,3 puis cinq à ×0,7. La moyenne PLATE vaut
    # exp((20·ln1,3 + 5·ln0,7)/25) = 1,149. La moyenne pondérée doit
    # peser davantage les cinq récentes et descendre nettement dessous.
    acc = J.AccBiais()
    for i in range(20):
        acc.push(i, math.log(1.3))
    for i in range(20, 25):
        acc.push(i, math.log(0.7))
    plate = math.exp((20 * math.log(1.3) + 5 * math.log(0.7)) / 25)
    check("la moyenne plate vaudrait 1,149", plate, 1.149, 0.002)
    check("⛔ la mémoire pondérée descend sous la moyenne plate",
          math.exp(acc.mean) < plate - 0.02, True)
    check("… sans pour autant oublier les vingt anciennes",
          math.exp(acc.mean) > 1.05, True)
    check("elle compte bien 25 journées", acc.days, 25)

    # Une interruption de service ne doit pas faire peser la journée de
    # reprise comme une journée consécutive (même règle que
    # `S.accumulate`, et pour la même raison).
    trou = J.AccBiais()
    trou.push(0, math.log(2.0))
    trou.push(120, math.log(1.0))       # quatre demi-vies plus tard
    check("après quatre demi-vies, l'ancienne journée ne pèse presque plus",
          math.exp(trou.mean) < 1.05, True)

    # Une journée déjà intégrée ne se réintègre pas : le rejeu doit
    # pouvoir repasser deux fois sans épaissir la mémoire.
    deux = J.AccBiais()
    deux.push(5, math.log(0.5))
    deux.push(5, math.log(0.5))
    check("une journée déjà intégrée est refusée", deux.days, 1)
    check("… et une journée ANTÉRIEURE aussi (l'ordre est chronologique)",
          (deux.push(4, math.log(2.0)), deux.days)[1], 1)


def test_s2_gardes_fous_et_temoin():
    """Les refus, et le témoin qui dit ce que le gain n'est pas."""
    print("── lot S2 : garde-fous et témoin ──")
    import tempfile
    from pathlib import Path

    # Une pente aberrante ne se rabote pas : elle ne s'applique pas.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        jours = [DAY - timedelta(days=k) for k in range(1, 11)]
        _archive_biaisee(root, jours, 0.2)        # sous BIAIS_PENTE_MIN
        for d in reversed(jours):
            J.replay_day(root, d, None, 0)
        prior = J.prior_biais(root, DAY)
        cle = ("pioupiou:900", "icon_d2", 6)
        check("une pente sous le garde-fou N'EST PAS APPLIQUÉE",
              prior.get(cle, (None,))[0], None)
        # ⓘ La clé peut subsister pour son écart de CAP : une vitesse
        # aberrante ne dit rien de la girouette, et jeter l'un avec
        # l'autre serait perdre une information valide par association.
        check("… et la pente n'est pas non plus rabotée à 0,4",
              any(p is not None and p < J.BIAIS_PENTE_MIN
                  for p, _c, _n in prior.values()), False)

    # Sous BIAIS_MIN_JOURS, la correction se tait.
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        jours = [DAY - timedelta(days=k) for k in range(1, 3)]   # 2 jours
        _archive_biaisee(root, jours, 0.6)
        for d in reversed(jours):
            J.replay_day(root, d, None, 0)
        check(f"sous {J.BIAIS_MIN_JOURS} journées, pas d'antécédent",
              J.prior_biais(root, DAY), {})

    # Le témoin : il rend None sous l'échantillon minimal, et il calcule
    # bien trois médianes quand il en a assez.
    check("le témoin se tait sous 30 balise-jours échantillonnés",
          J.bilan_temoin([(5.0, 3.0, 4.0)] * 10), None)
    b = J.bilan_temoin([(5.0, 3.0, 4.0)] * 40)
    check("… et sinon il publie le gain du vrai antécédent", b["gain_pct"], 40.0)
    check("… celui d'une AUTRE balise", b["gain_placebo_pct"], 20.0)
    check("… et la différence, qui est la part imputable au site",
          b["part_site_pct"], 20.0)
    check("… en toutes lettres dans le journal du run",
          "rétrécissement de la prévision" in b["texte"], True)


def test_s2_colonnes_de_zone():
    """La case publie son corrigé À CÔTÉ du brut, avec sa population."""
    print("── lot S2 : les colonnes de zone ──")
    zones = {f"pioupiou:{i}": {"source": "pioupiou", "station_id": str(i),
                               "zone_id": "b45.22_6.60:valley",
                               "landform": "valley", "massif_id": "alpes-nord",
                               "basin_id": "b1"} for i in range(6)}
    units = []
    for i in range(6):
        for k in range(5):
            units.append({
                "unit": f"pioupiou:{i}", "day": f"2026-08-0{k + 1}",
                "model": "icon_d2", "lead_h": 6, "n_hours": 12,
                # Brut : le modèle PERD contre la climatologie (50 > 45).
                # Corrigé : il la bat largement (12 < 45). C'est
                # exactement la bascule que le §1.b du point d'étape
                # attend des Alpes.
                "err_vec_med": 6.0, "mse_model": 50.0, "mse_persist": 55.0,
                "mse_clim": 45.0,
                # Trois balises sur six ont un antécédent : le corrigé
                # existe donc sur une population PLUS PETITE.
                **({"err_vec_med_corr": 3.0, "mse_model_corr": 12.0,
                    "bias_n_days": 9} if i < 3 else {}),
            })
    rows = J._case_rows(units, zones, DAY, "rolling15", "all", 3,
                        with_ci=False)
    fine = next(r for r in rows if r["agg_level"] == "basin_landform")
    check("le brut reste le score de référence", fine["typical_err_kmh"], 6.0)
    check("le corrigé sort à côté", fine["typical_err_kmh_corr"], 3.0)
    check("`n_corr` dit sur combien de balise-jours il repose",
          fine["n_corr"], 15)
    check("… contre `occurrences` pour le brut", fine["occurrences"], 30)
    check("le modèle brut NE bat PAS la climatologie ici",
          fine["beats_clim"], False)
    check("… et corrigé, il la bat", fine["beats_clim_corr"], True)
    check("`skill_clim` reste négatif en brut", fine["skill_clim"] < 0, True)
    check("… et devient franchement positif corrigé",
          fine["skill_clim_corr"] > 0.5, True)
    check("`bias_n_days` voyage jusqu'à la case", fine["bias_n_days"], 9.0)


# ══════════════════════════════════════════════════════════════════
#  LOT S3 — LE CONTRÔLE N°1 : L'INJECTION (`score.py --self-test`)
# ══════════════════════════════════════════════════════════════════
#
#  ⛔ CE QUI EST TESTÉ ICI N'EST PAS « LE SELF-TEST PASSE ». C'est
#  « le self-test SAIT ÉCHOUER ». Un garde-fou dont on n'a jamais
#  fabriqué l'échec est une décoration : c'est la leçon du seuil
#  journalier inerte du S0.4, trouvé PAR MUTATION et pas en lisant le
#  code.

def test_s3_self_test_injection():
    print("\n── lot S3 : le self-test d'injection ──")
    ok, lignes, m = J.self_test_epreuves()
    check("le self-test est VERT sur sa propre fixture", ok, True)
    check("… et il a produit des balise-jours (sinon il ne teste rien)",
          m["n_lignes"], J.SELF_TEST_STATIONS * len(J.LEAD_BY_OFFSET))

    # ── (a) ──
    check("(a) prévision = observation ⇒ err_vec_med exactement 0",
          m["err_max_parfaite"], 0.0, tol=1e-12)
    check("(a) skill contre la persistance = 1", m["skill_parfait"], 1.0)
    check("(a) skill contre la climatologie = 1", m["skill_clim_parfait"], 1.0)

    # ── (b) ──
    check("(b) le rapport à la climatologie est dans la bande mesurée",
          J.SELF_TEST_PERM_RATIO_CLIM_MIN <= m["rapport_perm_clim"]
          <= J.SELF_TEST_PERM_RATIO_CLIM_MAX, True)
    check("(b) et sa valeur est CELLE-CI, déterministe (la fabrique ne "
          "tire rien au hasard) : 2,198", round(m["rapport_perm_clim"], 3),
          2.198)
    check("(b) une prévision permutée ne bat pas la persistance",
          m["skill_permute"] <= 0.0, True)

    # ── ⛔ MUTATION 1 — « l'injection rend toujours vert » ──
    # On passe une permutation qui n'en est pas une : l'IDENTITÉ. Le
    # scoring rendra alors err = 0 pour la « permutée » aussi, donc un
    # rapport de 0 à la climatologie et un skill de 1.
    ok_id, lignes_id, m_id = J.self_test_epreuves(permuter=lambda s, g: s)
    check("⛔ MUTATION 1 — une permutation IDENTITÉ rend le verdict ROUGE",
          ok_id, False)
    rouges = [l for l in lignes_id if "❌" in l]
    check("… et ce sont EXACTEMENT les deux assertions de (b) qui "
          "rougissent (2), pas celles de (a)",
          [l.split("(")[1][0] for l in rouges], ["b", "b"])
    check("… la première parce que le rapport tombe à 0",
          m_id["rapport_perm_clim"], 0.0)
    check("… la seconde parce que le skill « permuté » remonte à 1",
          m_id["skill_permute"], 1.0)

    # ── ⛔ MUTATION 10 — « la tolérance de (a) élargie » ──
    # Une prévision biaisée d'un demi-km/h doit faire rougir (a). Avec
    # `SELF_TEST_ZERO_KMH` porté à 1 km/h, elle passerait — et c'est
    # exactement ce que la campagne de mutations a trouvé le 23/08 :
    # sans cette injection-ci, élargir la tolérance de (a) ne changeait
    # RIEN au banc, puisque l'erreur parfaite vaut exactement 0.
    def biaiser(snaps):
        return {off: [dict(r, speed=[(v + 0.5) if v is not None else None
                                     for v in r["speed"]])
                      for r in lignes_]
                for off, lignes_ in snaps.items()}
    ok_b, lignes_b, m_b = J.self_test_epreuves(injecter=biaiser)
    check("⛔ MUTATION 10 — un biais de 0,5 km/h rend le verdict ROUGE",
          ok_b, False)
    check("… et c'est bien l'épreuve (a) qui rougit",
          all("(a)" in l for l in lignes_b if "❌" in l), True)
    check("… l'erreur parfaite y vaut 0,5 km/h", round(m_b["err_max_parfaite"], 6),
          0.5)
    check("… soit 500 000 fois la tolérance de (a) — mais elle passerait "
          "si on la portait à 1 km/h", m_b["err_max_parfaite"] <= 1.0, True)

    # ── ⛔ MUTATION 4 — « la tolérance élargie jusqu'à tout accepter » ──
    # Élargir la bande à [0, ∞[ ferait passer la permutation IDENTITÉ.
    # On le prouve ici sans toucher au module : on rejoue la comparaison
    # que fait l'épreuve (b) avec la borne mutée.
    check("⛔ MUTATION 4 — avec une borne basse à 0, la permutation "
          "IDENTITÉ passerait (la tolérance rendrait le contrôle muet)",
          0.0 <= m_id["rapport_perm_clim"] <= 1e9, True)
    check("… alors qu'avec la borne réelle elle ne passe pas",
          J.SELF_TEST_PERM_RATIO_CLIM_MIN <= m_id["rapport_perm_clim"], False)

    # ── la permutation elle-même : AUCUN point fixe (Sattolo) ──
    # ⚠️ SUR VINGT GRAINES, PAS UNE. Fisher-Yates laisse en moyenne UN
    # point fixe par tirage, mais il peut n'en laisser aucun sur une
    # graine donnée : une seule graine ferait un mutant « équivalent »
    # par chance, et on aurait mesuré la chance, pas la propriété.
    _, snaps, _, _, _ = J._self_test_fabrique(12)
    avant = {r["station_id"]: r["speed"] for r in snaps[0]}
    fixes = 0
    for graine in range(1, 21):
        permutes = J.self_test_permuter(snaps, graine)
        fixes += sum(1 for r in permutes[0]
                     if r["speed"] is avant[r["station_id"]])
    check("⭐ Sattolo : AUCUNE balise ne garde sa propre prévision, sur "
          "vingt graines (Fisher-Yates en laisserait ~20 en tout)",
          fixes, 0)
    check("… et la permutation ne perd aucune ligne",
          len(J.self_test_permuter(snaps)[0]), len(snaps[0]))

    # ── le contrat des codes de sortie ──
    check("`self_test()` rend 0 quand tout est vert", J.self_test(),
          J.SELF_TEST_OK)
    check("les trois codes sont distincts",
          len({J.SELF_TEST_OK, J.SELF_TEST_FAUX, J.SELF_TEST_INDISPONIBLE}), 3)
    check("⛔ « scoring faux » vaut 2", J.SELF_TEST_FAUX, 2)
    check("⛔ « contrôle indisponible » vaut 3, PAS 2 — un garde-fou qui "
          "tue la nuit pour sa propre panne finit désarmé",
          J.SELF_TEST_INDISPONIBLE, 3)

    # ── ⛔ une panne du contrôle rend 3, jamais 2 ──
    def permuter_qui_plante(s, g):
        raise RuntimeError("fixture cassée pour le banc")
    try:
        J.self_test_epreuves(permuter=permuter_qui_plante)
        check("une panne du contrôle lève bien", True, False)
    except RuntimeError:
        check("une panne du contrôle lève au lieu de rendre un verdict",
              True, True)
    # Et le mode complet la transforme en 3 (jamais en 2).
    #
    # ⚠️ ON REMPLACE `_self_test_fabrique`, PAS `self_test_permuter` — et
    # ce détail a été trouvé PAR LE BANC, au premier essai. `permuter`
    # est un ARGUMENT PAR DÉFAUT : Python le lie une fois pour toutes à
    # la définition de la fonction, donc réaffecter `J.self_test_permuter`
    # ne change rien à ce que `self_test()` appellera. La mutation ne
    # s'appliquait pas, le banc restait vert, et j'aurais cru avoir
    # mesuré « le code 3 marche » alors que je n'avais rien muté —
    # exactement la leçon (a) du S0.11.
    vraie_fabrique = J._self_test_fabrique
    try:
        def fabrique_cassee(n=0):
            raise RuntimeError("fixture cassée pour le banc")
        J._self_test_fabrique = fabrique_cassee
        check("⛔ `self_test()` rend 3 quand SA fixture casse — jamais 2",
              J.self_test(), J.SELF_TEST_INDISPONIBLE)
    finally:
        J._self_test_fabrique = vraie_fabrique
    check("… et il redevient vert une fois la fixture réparée",
          J.self_test(), J.SELF_TEST_OK)
    check("⭐ et le chemin de PRODUCTION n'est pas remplaçable : "
          "`permuter` est un argument PAR DÉFAUT, lié à la définition",
          J.self_test_epreuves.__defaults__[0] is J.self_test_permuter, True)

    # ── ⛔ LE SELF-TEST NE TOUCHE RIEN ──
    # Preuve statique : aucune des trois fonctions n'appelle quoi que ce
    # soit qui lise un fichier, la base ou R2.
    import ast as _ast
    import inspect as _inspect
    interdits = {"Supabase", "_storage", "read_ndjson", "read_json",
                 "replay_write", "replay_read", "upsert", "select",
                 "open", "urlopen"}
    for fn in (J._self_test_fabrique, J.self_test_permuter,
               J.self_test_epreuves, J.self_test):
        arbre = _ast.parse(_inspect.getsource(fn).lstrip())
        appels = set()
        for n in _ast.walk(arbre):
            if isinstance(n, _ast.Call):
                cible = n.func
                appels.add(getattr(cible, "id", None)
                           or getattr(cible, "attr", None))
        check(f"⛔ `{fn.__name__}` n'appelle rien qui lise ou écrive",
              sorted(appels & interdits), [])


# ══════════════════════════════════════════════════════════════════
#  LOT S13.0 — le fichier léger et le résumé des manches
# ══════════════════════════════════════════════════════════════════

def test_rank_corr_le_meme_test_sur_la_colonne_corrigee():
    """Le classement corrigé : même appareil, autre grandeur (25/08)."""
    print("── 25/08 : `rank_corr`, le test apparié sur l'erreur corrigée ──")

    # ⭐ LA FIXTURE EST CONSTRUITE POUR QUE LES DEUX COLONNES SE
    # CONTREDISENT — c'est le seul cas qui prouve quelque chose. `a` est
    # PIRE en brut (6 contre 5) et MEILLEUR en corrigé (3 contre 5) :
    # si le classement corrigé se contentait de recopier le brut, ou
    # s'il testait `err_vec_med` en ordonnant sur le corrigé, il
    # nommerait `b` ou ne nommerait personne.
    jours = [f"2026-08-{d:02d}" for d in range(1, 16)]
    par_modele = {"a": [], "b": []}
    for j in jours:
        for u in range(6):
            par_modele["a"].append({"day": j, "unit": f"p:{u}",
                                    "err_vec_med": 6.0, "err_vec_med_corr": 3.0})
            par_modele["b"].append({"day": j, "unit": f"p:{u}",
                                    "err_vec_med": 5.0, "err_vec_med_corr": 5.0})
    rows = [{"model": "a", "typical_err_kmh": 6.0, "typical_err_kmh_corr": 3.0,
             "occurrences": 90, "n_corr": 90},
            {"model": "b", "typical_err_kmh": 5.0, "typical_err_kmh_corr": 5.0,
             "occurrences": 90, "n_corr": 90}]
    J._apply_rank_corr(rows, par_modele)
    check("le corrigé tranche, et pour `a`", 
          (rows[0]["rank_reason_corr"], rows[0]["rank_corr"]), ("ok", 1))
    check("… `b` est second sur la colonne corrigée",
          rows[1]["rank_corr"], 2)

    # ⛔ Le test du brut, sur les MÊMES lignes, doit désigner `b` :
    # c'est la preuve que les deux verdicts sont bien indépendants.
    cases = [{"model": r["model"], "typical_err_kmh": r["typical_err_kmh"],
              "occurrences": r["occurrences"]} for r in rows]
    ranks_brut, raison_brut, _ = J.INF.rank_models(cases, par_modele)
    check("⭐ et le BRUT, lui, désigne `b` — deux colonnes, deux verdicts",
          (raison_brut, ranks_brut.get("b")), ("ok", 1))

    # ⛔ POPULATION MIXTE : une seule ligne sans corrigé et on refuse.
    mixte = [dict(rows[0]), dict(rows[1]),
             {"model": "c", "typical_err_kmh": 7.0, "typical_err_kmh_corr": None,
              "occurrences": 90, "n_corr": 0}]
    J._apply_rank_corr(mixte, par_modele)
    check("une case mixte ne se classe pas sur le corrigé",
          [r["rank_reason_corr"] for r in mixte],
          [J.RANK_REASON_POPULATION_MIXTE] * 3)
    check("… et aucun rang corrigé n'est publié",
          [r["rank_corr"] for r in mixte], [None] * 3)

    # ⚠️ Le quorum se compte en `n_corr` : à `n_corr` nul, la case
    # tombe sous le quorum même si `occurrences` est confortable.
    maigre = [{**dict(rows[0]), "n_corr": 0}, {**dict(rows[1]), "n_corr": 0}]
    J._apply_rank_corr(maigre, par_modele)
    check("⚠️ quorum compté en `n_corr`, pas en `occurrences`",
          maigre[0]["rank_reason_corr"], "insufficient")

    # ⛔ Et le motif de refus du mixte ne doit JAMAIS toucher
    # `rank_reason`, dont le CHECK SQL ne connaît pas cette valeur.
    check("`rank_reason` n'est pas touché par le passage corrigé",
          [r.get("rank_reason") for r in mixte], [None] * 3)


def test_l2_un_seul_arome_au_classement():
    """Lot L2 (27/08/2026) — `meteofrance_arome_france_hd` et `arome_r2`
    sont le MÊME modèle lu par deux chaînes : une case ne les admet
    JAMAIS tous les deux au classement (audit §2.2/PS2, décision de
    Yann du 27/08).
    """
    print("── lot L2 : un seul AROME au classement (`duplicate_chain`) ──")
    zone_of = {f"pioupiou:{i}": {"zone_id": "b1:valley", "landform": "valley",
                                 "basin_id": "b1", "massif_id": "alpes-nord",
                                 "basin_uncertain": False}
               for i in range(830, 836)}

    # ⭐ arome_r2 (4,5 km/h) bat NUMÉRIQUEMENT mfhd (5,0) — sans le lot
    # L2 il prendrait le 2ᵉ billet du podium devant mfhd. C'est
    # précisément ce que la décision de Yann interdit.
    daily = []
    for j in range(15):
        d = (DAY - timedelta(days=j)).strftime("%Y-%m-%d")
        for i in range(830, 836):
            for model, err in (("icon_d2", 3.0),
                               (J.AROME_HD_MODEL, 5.0),
                               (J.AROME_R2_MODEL, 4.5)):
                daily.append({
                    "day": d, "source": "pioupiou", "station_id": str(i),
                    "model": model, "lead_h": 24, "regime": "fluxN",
                    "n_hours": 12, "err_vec_med": err,
                    "mse_model": err * err, "mse_persist": 100.0})
    rows = J.rolling_scores(daily, zone_of, DAY)
    fine = [r for r in rows if r["zone_id"] == "b1:valley"]
    check("les trois modèles ont chacun leur ligne (rien n'est supprimé)",
          sorted(r["model"] for r in fine),
          sorted(["icon_d2", J.AROME_HD_MODEL, J.AROME_R2_MODEL]))

    icon = next(r for r in fine if r["model"] == "icon_d2")
    hd = next(r for r in fine if r["model"] == J.AROME_HD_MODEL)
    r2 = next(r for r in fine if r["model"] == J.AROME_R2_MODEL)

    check("⭐ icon_d2 reste 1er (3,0 km/h, imbattu)", icon["rank"], 1)
    check("⭐⭐ mfhd est 2ᵉ, alors que arome_r2 (4,5) bat mfhd (5,0) — "
          "arome_r2 n'a jamais eu le droit de concourir",
          hd["rank"], 2)
    check("`arome_r2` n'a AUCUN rang, quel que soit son chiffre",
          r2["rank"], None)
    check("… et sa raison le nomme précisément",
          r2["rank_reason"], "duplicate_chain")
    check("mfhd garde sa vraie raison de classement (« ok »), pas "
          "« duplicate_chain »", hd["rank_reason"], "ok")
    check("icon_d2 aussi", icon["rank_reason"], "ok")
    check("⛔ arome_r2 garde son erreur typique intacte (4,5 km/h) — "
          "seul le RANG lui est refusé", r2["typical_err_kmh"], 4.5)
    check("… et son `beats_persist` aussi, calculé contre la "
          "persistance/climatologie, pas contre les autres modèles",
          r2["beats_persist"] is not None, True)

    # ⛔ SEUL, arome_r2 concourt normalement — c'est le cas structurel
    # des balises hors Pioupiou (lot S0.5), où mfhd n'existe pas.
    seul = [d for d in daily if d["model"] != J.AROME_HD_MODEL]
    rows_seul = J.rolling_scores(seul, zone_of, DAY)
    fine_seul = [r for r in rows_seul if r["zone_id"] == "b1:valley"]
    r2_seul = next(r for r in fine_seul if r["model"] == J.AROME_R2_MODEL)
    check("seul (mfhd absent de la case), arome_r2 concourt normalement",
          (r2_seul["rank"], r2_seul["rank_reason"]), (2, "ok"))

    # ⛔ Et SEULS les deux AROME dans une case : personne à départager
    # pour mfhd (`single_model`) — une raison DIFFÉRENTE de celle
    # d'arome_r2, et les deux ne doivent jamais se confondre.
    duo = [d for d in daily if d["model"] != "icon_d2"]
    rows_duo = J.rolling_scores(duo, zone_of, DAY)
    fine_duo = [r for r in rows_duo if r["zone_id"] == "b1:valley"]
    hd_duo = next(r for r in fine_duo if r["model"] == J.AROME_HD_MODEL)
    r2_duo = next(r for r in fine_duo if r["model"] == J.AROME_R2_MODEL)
    check("⚠️ mfhd seul admis → `single_model`, PAS `ok` (rien à battre)",
          (hd_duo["rank"], hd_duo["rank_reason"]), (None, "single_model"))
    check("… et arome_r2 reste `duplicate_chain`, pas `single_model`",
          (r2_duo["rank"], r2_duo["rank_reason"]), (None, "duplicate_chain"))


def test_l2_duplicate_chain_sur_le_classement_corrige():
    """Lot L2 — même écarté, même raison, sur `rank_corr`/`rank_reason_corr`."""
    print("── lot L2 : `duplicate_chain` sur la colonne corrigée ──")
    jours = [f"2026-08-{d:02d}" for d in range(1, 16)]
    par_modele = {"icon_d2": [], J.AROME_HD_MODEL: [], J.AROME_R2_MODEL: []}
    for j in jours:
        for u in range(6):
            par_modele["icon_d2"].append(
                {"day": j, "unit": f"p:{u}",
                 "err_vec_med": 3.0, "err_vec_med_corr": 3.0})
            par_modele[J.AROME_HD_MODEL].append(
                {"day": j, "unit": f"p:{u}",
                 "err_vec_med": 5.0, "err_vec_med_corr": 5.0})
            par_modele[J.AROME_R2_MODEL].append(
                {"day": j, "unit": f"p:{u}",
                 "err_vec_med": 4.5, "err_vec_med_corr": 1.0})

    rows = [
        {"model": "icon_d2", "typical_err_kmh": 3.0, "typical_err_kmh_corr": 3.0,
         "occurrences": 90, "n_corr": 90},
        {"model": J.AROME_HD_MODEL, "typical_err_kmh": 5.0,
         "typical_err_kmh_corr": 5.0, "occurrences": 90, "n_corr": 90},
        {"model": J.AROME_R2_MODEL, "typical_err_kmh": 4.5,
         "typical_err_kmh_corr": 1.0, "occurrences": 90, "n_corr": 90},
    ]
    exclu = J._duplicate_chain_excluded(rows)
    check("l'écarté calculé par `_apply_rank` est bien `arome_r2`",
          exclu, J.AROME_R2_MODEL)
    J._apply_rank_corr(rows, par_modele, exclu)
    icon, hd, r2 = rows
    check("⭐ icon_d2 gagne le corrigé (3,0 contre 5,0) — arome_r2 "
          "(1,0, le plus bas des trois) n'a jamais concouru",
          (icon["rank_reason_corr"], icon["rank_corr"]), ("ok", 1))
    check("… mfhd 2ᵉ", hd["rank_corr"], 2)
    check("arome_r2 : rang nul, `duplicate_chain` — pas `mixed_population`",
          (r2["rank_corr"], r2["rank_reason_corr"]),
          (None, "duplicate_chain"))

    # ⛔ L'écarté ne doit pas faire tomber les autres dans le refus
    # « population mixte » quand IL est le seul sans corrigé. Sans le
    # filtrer AVANT ce test, `len(avec) != len(chiffrees)` verrait 3
    # lignes chiffrées et seulement 2 avec un corrigé, et refuserait
    # tout le monde.
    sans_corr = [dict(icon), dict(hd),
                 {**dict(r2), "typical_err_kmh_corr": None, "n_corr": 0}]
    J._apply_rank_corr(sans_corr, par_modele, J.AROME_R2_MODEL)
    check("⭐⭐ arome_r2 sans corrigé DU TOUT n'empêche pas icon_d2/mfhd "
          "de se classer sur le corrigé (l'écarté est retiré AVANT le "
          "test de population mixte)",
          (sans_corr[0]["rank_reason_corr"], sans_corr[0]["rank_corr"]),
          ("ok", 1))
    check("… et arome_r2 reste `duplicate_chain`, pas `mixed_population`",
          sans_corr[2]["rank_reason_corr"], "duplicate_chain")

    # ⛔ Sans exclusion (`exclu=None`), le comportement d'AVANT le lot
    # L2 doit être EXACTEMENT préservé — régression zéro pour toutes
    # les cases qui ne portent pas les deux AROME.
    sans_dup = [dict(icon), dict(hd)]
    par_modele_sans_r2 = {"icon_d2": par_modele["icon_d2"],
                          J.AROME_HD_MODEL: par_modele[J.AROME_HD_MODEL]}
    J._apply_rank_corr(sans_dup, par_modele_sans_r2)
    check("sans second AROME, `_apply_rank_corr` se comporte à l'identique "
          "d'avant le lot L2 (icon_d2 gagne)",
          (sans_dup[0]["rank_reason_corr"], sans_dup[0]["rank_corr"]),
          ("ok", 1))


def test_l2_apply_rank_transmet_lexclu_au_corrige():
    """Lot L2 — `_apply_rank` doit transmettre L'ÉCARTÉ à
    `_apply_rank_corr` : la même case n'a pas le droit de dire
    `duplicate_chain` sur le brut et `mixed_population` (ou pire, un
    rang) sur le corrigé, pour le MÊME modèle.
    """
    print("── lot L2 : l'écarté du brut voyage bien jusqu'au corrigé ──")
    key = ("b1:valley", 24, "basin_landform")
    rows = [
        {"model": "icon_d2", "typical_err_kmh": 3.0, "occurrences": 90,
         "typical_err_kmh_corr": 3.0, "n_corr": 90},
        {"model": J.AROME_HD_MODEL, "typical_err_kmh": 5.0, "occurrences": 90,
         "typical_err_kmh_corr": 5.0, "n_corr": 90},
        # ⭐ arome_r2 porte le MEILLEUR corrigé des trois (1,0) : s'il
        # n'est pas écarté ICI AUSSI, il gagne le classement corrigé.
        {"model": J.AROME_R2_MODEL, "typical_err_kmh": 4.5, "occurrences": 90,
         "typical_err_kmh_corr": 1.0, "n_corr": 90},
    ]
    jours = [f"2026-08-{d:02d}" for d in range(1, 16)]
    rbcm = {"icon_d2": [], J.AROME_HD_MODEL: [], J.AROME_R2_MODEL: []}
    for j in jours:
        for u in range(6):
            rbcm["icon_d2"].append({"day": j, "unit": f"p:{u}",
                                    "err_vec_med": 3.0, "err_vec_med_corr": 3.0})
            rbcm[J.AROME_HD_MODEL].append({"day": j, "unit": f"p:{u}",
                                           "err_vec_med": 5.0, "err_vec_med_corr": 5.0})
            rbcm[J.AROME_R2_MODEL].append({"day": j, "unit": f"p:{u}",
                                           "err_vec_med": 4.5, "err_vec_med_corr": 1.0})
    J._apply_rank({key: rows}, {key: rbcm})
    icon, hd, r2 = rows
    check("brut : icon_d2 1er", icon["rank"], 1)
    check("brut : mfhd 2ᵉ (arome_r2 écarté du calcul, pas juste du rang)",
          hd["rank"], 2)
    check("brut : arome_r2 `duplicate_chain`",
          r2["rank_reason"], "duplicate_chain")
    check("⭐⭐ corrigé : arome_r2 est AUSSI `duplicate_chain`, pas "
          "`mixed_population` ni un rang gagné sur son 1,0 — l'écarté du "
          "brut a bien voyagé jusqu'au corrigé",
          r2["rank_reason_corr"], "duplicate_chain")
    check("… et son rang corrigé est nul", r2["rank_corr"], None)
    check("corrigé : icon_d2 gagne quand même (3,0 contre 5,0 — arome_r2 "
          "toujours hors compétition malgré son 1,0)",
          (icon["rank_reason_corr"], icon["rank_corr"]), ("ok", 1))
    check("corrigé : mfhd 2ᵉ", hd["rank_corr"], 2)


def test_l3_gap_apparie_bout_en_bout():
    """Lot L3 (27/08/2026), objectif 2 — l'écart PRATIQUE se mesure sur
    les balise-jours COMMUNS aux deux modèles, plus jamais sur deux
    populations propres (défaut mesuré, audit §2.5).
    """
    print("── lot L3 : le gap pratique, sur la population appariée ──")
    zone_of = {f"pioupiou:{i}": {"zone_id": "b1:valley", "landform": "valley",
                                 "basin_id": "b1", "massif_id": "alpes-nord",
                                 "basin_uncertain": False}
               for i in range(900, 912)}

    # ⛔ LE PIÈGE, REPRODUIT EXPRÈS. `icon_d2` note DOUZE balises ; six
    # d'entre elles sont faciles (1,0 km/h) et six sont dures
    # (9,0 km/h). `mfhd` ne note QUE les six dures, et s'y trompe à
    # peine plus (9,4). Sur leurs populations propres, icon a l'air
    # DEUX FOIS meilleur ; sur les six balises qu'ils partagent, ils
    # sont à 4 % l'un de l'autre — bien sous les 15 % « utiles ».
    daily = []
    for j in range(15):
        d = (DAY - timedelta(days=j)).strftime("%Y-%m-%d")
        for i in range(900, 912):
            dure = i >= 906
            daily.append({
                "day": d, "source": "pioupiou", "station_id": str(i),
                "model": "icon_d2", "lead_h": 24, "regime": "fluxN",
                "n_hours": 12, "err_vec_med": 9.0 if dure else 1.0,
                "mse_model": 81.0 if dure else 1.0, "mse_persist": 200.0})
            if dure:
                daily.append({
                    "day": d, "source": "pioupiou", "station_id": str(i),
                    "model": J.AROME_HD_MODEL, "lead_h": 24, "regime": "fluxN",
                    "n_hours": 12, "err_vec_med": 9.4,
                    "mse_model": 88.36, "mse_persist": 200.0})

    rows = J.rolling_scores(daily, zone_of, DAY)
    fine = [r for r in rows if r["zone_id"] == "b1:valley"]
    icon = next(r for r in fine if r["model"] == "icon_d2")
    hd = next(r for r in fine if r["model"] == J.AROME_HD_MODEL)

    check("icon_d2 a bien l'air deux fois meilleur sur SA population "
          "(5,0 contre 9,4) — c'est le chiffre publié, et il est juste",
          (icon["typical_err_kmh"], hd["typical_err_kmh"]), (5.0, 9.4))
    check("⭐⭐ … et pourtant AUCUN rang n'est publié : sur les six "
          "balises qu'ils partagent, l'écart utile tombe à 4 %",
          (icon["rank"], hd["rank"]), (None, None))
    check("… la raison est `tied` (« écart réel mais trop faible »), pas "
          "`not_separable` : le test apparié sépare parfaitement, c'est "
          "la condition PRATIQUE qui refuse",
          icon["rank_reason"], "tied")

    # ⭐ `n_comparable` publie le dénominateur du raisonnement.
    check("⭐⭐ `n_comparable` : le noyau commun de la case vaut 90 "
          "balise-jours (6 balises × 15 jours) — icon_d2 publie donc un "
          "chiffre dont la MOITIÉ vient de balises que personne d'autre "
          "n'a vues, et sa ligne le dit",
          (icon["occurrences"], icon["n_comparable"]), (180, 90))
    check("… et mfhd, lui, est comparable sur la totalité des siens : "
          "`n_comparable == occurrences`",
          (hd["occurrences"], hd["n_comparable"]), (90, 90))

    # ⛔ ET LE GARDE-FOU QUI NE SE VOIT PAS AUTREMENT. `_jours_balises`
    # exige une `err_vec_med` FINIE, pas seulement une ligne présente —
    # la MÊME condition que `INF.paired_differences`. Sans elle,
    # `n_comparable` compterait des balise-jours vides et annoncerait
    # une population commune que le test, lui, n'a jamais eue. Le bout
    # en bout ne peut pas l'attraper (la collecte n'accumule que des
    # valeurs finies) : c'est donc ici, en direct, ou nulle part.
    lignes = [{"day": "2026-08-26", "unit": "pioupiou:1", "err_vec_med": 3.0},
              {"day": "2026-08-26", "unit": "pioupiou:2", "err_vec_med": None},
              {"day": "2026-08-26", "unit": "pioupiou:3",
               "err_vec_med": float("nan")},
              {"day": "2026-08-26", "unit": "pioupiou:4"}]
    check("⭐ `_jours_balises` ne retient que les balise-jours à erreur "
          "FINIE — ni `None`, ni `NaN`, ni champ absent",
          J._jours_balises(lignes), {("2026-08-26", "pioupiou:1")})
    check("… et une liste vide ou absente ne plante pas",
          (J._jours_balises([]), J._jours_balises(None)), (set(), set()))


def _ligne_fdr(zone, p, reason="ok", rank=1, model="icon_d2", p_corr=None):
    """Une ligne de score minimale, telle que `appliquer_fdr` la lit."""
    r = {"as_of": "2026-08-27", "zone_id": zone, "model": model, "lead_h": 24,
         "window_kind": "rolling15", "regime": "all", "agg_level": "basin",
         "rank": rank, "rank_reason": reason,
         "rank_corr": None, "rank_reason_corr": None}
    if p is not None:
        r[J.FDR_P_BRUT] = p
    if p_corr is not None:
        r[J.FDR_P_CORR] = p_corr
    return r


def test_l3_fdr_tue_la_limite_et_garde_la_franche():
    """Lot L3, objectif 1 — Benjamini-Hochberg sur le TABLEAU de la nuit.

    ⛔ Le jeu est construit pour que la réponse ne fasse aucun doute :
    dix cases FRANCHES (p au plancher du tirage), une case LIMITE
    (p = 0,02 — « significative » à 5 % prise toute seule), et 92 cases
    où un test a bien eu lieu sans rien conclure. BH doit garder les
    dix, tuer la limite, et compter les 92 dans `m` — c'est ce dernier
    point qui fait toute la sévérité de la correction.
    """
    print("── lot L3 : BH tue la case limite, garde les franches ──")
    PLANCHER = 2 / (I.BOOTSTRAP_ITERATIONS + 1)
    rows = []
    for i in range(10):
        rows.append(_ligne_fdr(f"franche:{i}", PLANCHER))
    rows.append(_ligne_fdr("limite", 0.02))
    for i in range(92):
        # Un test JOUÉ qui n'a rien conclu : pas de rang, mais une
        # p-valeur — donc dans la famille.
        rows.append(_ligne_fdr(f"muette:{i}", 0.30 + 0.005 * i,
                               reason="not_separable", rank=None))
    # Et deux cases où AUCUN test n'a eu lieu : hors famille.
    rows.append(_ligne_fdr("courte", None, reason="window_too_short",
                           rank=None))
    rows.append(_ligne_fdr("seule", None, reason="single_model", rank=None))

    # ⛔ ET UNE CASE JUMELLE, À TOUT SAUF LA FENÊTRE PRÈS. Le glissant
    # et le régime posent DEUX questions sur la même zone : les
    # confondre diviserait `m` par deux et rendrait la correction deux
    # fois trop indulgente, sans que rien ne le montre.
    jumelle = _ligne_fdr("limite", 0.02)
    jumelle["window_kind"], jumelle["regime"] = "regime", "fluxN"
    rows.append(jumelle)

    rapport = J.appliquer_fdr(rows)
    b = rapport["brut"]
    check("⭐ la famille compte les tests JOUÉS (104), pas les seuls "
          "rangs publiés (12) ni toutes les cases (106)", b["m"], 104)
    check("⭐⭐ … et la jumelle « régime » compte comme une case À PART "
          "de la jumelle « rolling15 » — même zone, même lead, deux "
          "questions", b["publies_avant"], 12)
    check("⭐⭐ les deux limites sont retirées, aucune autre",
          b["retrogrades"], 2)

    limite = next(r for r in rows if r["zone_id"] == "limite"
                  and r["window_kind"] == "rolling15")
    check("⭐⭐ la case limite perd son rang", limite["rank"], None)
    check("… et sa raison le NOMME (`fdr`), au lieu de la faire "
          "disparaître en silence", limite["rank_reason"], J.RANK_REASON_FDR)
    check("… la jumelle « régime » tombe elle aussi, séparément",
          jumelle["rank_reason"], J.RANK_REASON_FDR)
    check("les dix franches gardent leur rang",
          [r["rank"] for r in rows if r["zone_id"].startswith("franche")],
          [1] * 10)
    check("… et leur raison intacte",
          {r["rank_reason"] for r in rows
           if r["zone_id"].startswith("franche")}, {"ok"})
    check("⛔ les cases muettes ne sont PAS rétrogradées — elles "
          "n'avaient rien affirmé, `not_separable` reste `not_separable`",
          {r["rank_reason"] for r in rows if r["zone_id"].startswith("muette")},
          {"not_separable"})
    check("… et les cases sans test gardent la leur",
          [next(r["rank_reason"] for r in rows if r["zone_id"] == z)
           for z in ("courte", "seule")],
          ["window_too_short", "single_model"])

    check("⭐ les clés privées de transport sont RETIRÉES — le JSON "
          "publié porte tout le reste sans filtre",
          any(J.FDR_P_BRUT in r or J.FDR_P_CORR in r for r in rows), False)

    # ⛔ ET LE CONTRÔLE QUI COMPTE VRAIMENT : sans les 92 muettes dans la
    # famille, la limite SURVIVRAIT. C'est la preuve que `m` est le bon.
    rows2 = ([_ligne_fdr(f"franche:{i}", PLANCHER) for i in range(10)]
             + [_ligne_fdr("limite", 0.02)])
    J.appliquer_fdr(rows2)
    limite2 = next(r for r in rows2 if r["zone_id"] == "limite")
    check("⭐⭐ sur une famille de 11 seulement, la MÊME case limite "
          "survit — la sévérité vient bien du nombre de tests joués",
          limite2["rank_reason"], "ok")


def test_l3_fdr_ne_touche_pas_lecarte_ni_le_corrige():
    """Le motif `fdr` ne doit écraser NI `duplicate_chain` (lot L2), NI
    la colonne corrigée, qui est une famille à part.

    ⛔ C'est la leçon du lot L2 appliquée d'avance : depuis lui, une case
    n'est plus uniforme en `rank_reason`. Une rétrogradation qui
    balaierait toutes les lignes de la case effacerait le motif de
    l'écarté — et l'écran afficherait « retiré par la multiplicité » sur
    un modèle qui n'a jamais concouru.
    """
    print("── lot L3 : `fdr` n'écrase ni l'écarté, ni l'autre colonne ──")
    PLANCHER = 2 / (I.BOOTSTRAP_ITERATIONS + 1)
    rows = []
    # Une case publiée qui va tomber, avec son écarté L2 dedans.
    rows.append(_ligne_fdr("mixte", 0.02, model="icon_d2", rank=1))
    ecarte = _ligne_fdr("mixte", None, model=J.AROME_R2_MODEL, rank=None,
                        reason=J.RANK_REASON_DUPLICATE_CHAIN)
    rows.append(ecarte)
    for i in range(92):
        rows.append(_ligne_fdr(f"muette:{i}", 0.30 + 0.005 * i,
                               reason="not_separable", rank=None))
    J.appliquer_fdr(rows)
    gagnant = next(r for r in rows
                   if r["zone_id"] == "mixte" and r["model"] == "icon_d2")
    check("la case tombe bien", gagnant["rank_reason"], J.RANK_REASON_FDR)
    check("⭐⭐ … et l'écarté du lot L2 garde `duplicate_chain` — jamais "
          "`fdr`", ecarte["rank_reason"], J.RANK_REASON_DUPLICATE_CHAIN)
    check("… et son rang reste nul", ecarte["rank"], None)

    # ── deux familles séparées : le corrigé a son propre BH ──────────
    rows_c = []
    # ⓘ HUIT franches, pas trois : au plancher du tirage (p ≈ 0,003992)
    # et sur une famille de 101, il en faut au moins cinq pour que la
    # première franchisse son seuil BH (0,10/101 = 9,9e-4). C'est la
    # limite de résolution documentée dans `_p_bilaterale`, visible ici
    # à taille de banc — et une raison de plus de la connaître.
    for i in range(8):
        r = _ligne_fdr(f"c:{i}", PLANCHER, p_corr=PLANCHER)
        r["rank_corr"], r["rank_reason_corr"] = 1, "ok"
        rows_c.append(r)
    r_lim = _ligne_fdr("c:lim", PLANCHER, p_corr=0.02)
    r_lim["rank_corr"], r_lim["rank_reason_corr"] = 1, "ok"
    rows_c.append(r_lim)
    for i in range(92):
        m = _ligne_fdr(f"cm:{i}", 0.90, reason="not_separable", rank=None,
                       p_corr=0.30 + 0.005 * i)
        m["rank_reason_corr"] = "not_separable"
        rows_c.append(m)
    rap = J.appliquer_fdr(rows_c)
    check("le corrigé a sa propre famille, de la même taille ici",
          (rap["brut"]["m"], rap["corrige"]["m"]), (101, 101))
    check("⭐ le brut ne tombe pas (ses neuf p sont au plancher)",
          rap["brut"]["retrogrades"], 0)
    check("⭐⭐ … et le corrigé, lui, perd sa case limite — les deux "
          "colonnes sont jugées séparément",
          rap["corrige"]["retrogrades"], 1)
    check("… c'est bien `rank_reason_corr` qui porte le motif, jamais "
          "`rank_reason`",
          (r_lim["rank_reason_corr"], r_lim["rank_reason"]),
          (J.RANK_REASON_FDR, "ok"))


def test_l3_la_p_valeur_arrive_vraiment_du_classement():
    """⛔ LE BANC QUI EMPÊCHE LES TROIS AUTRES D'ÊTRE UNE MISE EN SCÈNE.

    Les bancs de `appliquer_fdr` posent les p-valeurs à la main. Celui-ci
    vérifie qu'un classement RÉEL en dépose une, non nulle, sur toutes
    les lignes admises et sur aucune autre — sans quoi la correction
    tournerait chaque nuit sur une famille vide, en silence.
    """
    print("── lot L3 : la p-valeur vient bien du test apparié réel ──")
    zone_of = {f"pioupiou:{i}": {"zone_id": "b1:valley", "landform": "valley",
                                 "basin_id": "b1", "massif_id": "alpes-nord",
                                 "basin_uncertain": False}
               for i in range(940, 946)}
    daily = []
    for j in range(15):
        d = (DAY - timedelta(days=j)).strftime("%Y-%m-%d")
        for i in range(940, 946):
            for model, err in (("icon_d2", 3.0),
                               (J.AROME_HD_MODEL, 9.0),
                               (J.AROME_R2_MODEL, 9.5)):
                daily.append({
                    "day": d, "source": "pioupiou", "station_id": str(i),
                    "model": model, "lead_h": 24, "regime": "fluxN",
                    "n_hours": 12, "err_vec_med": err,
                    "mse_model": err * err, "mse_persist": 200.0})
    rows = J.rolling_scores(daily, zone_of, DAY)
    fine = [r for r in rows if r["zone_id"] == "b1:valley"]
    icon = next(r for r in fine if r["model"] == "icon_d2")
    r2 = next(r for r in fine if r["model"] == J.AROME_R2_MODEL)
    check("le classement tranche (icon_d2 1er, écart franc)",
          (icon["rank"], icon["rank_reason"]), (1, "ok"))
    check("⭐⭐ une p-valeur RÉELLE a été déposée sur la ligne admise",
          isinstance(icon.get(J.FDR_P_BRUT), float), True)
    check("… au plancher du tirage, comme il se doit pour un écart franc",
          icon[J.FDR_P_BRUT], 2 / (I.BOOTSTRAP_ITERATIONS + 1))
    check("⛔ … et AUCUNE sur l'écarté du lot L2, qui n'a rien testé",
          r2.get(J.FDR_P_BRUT), None)
    rap = J.appliquer_fdr(rows)
    check("la famille n'est pas vide — la correction a de quoi mordre",
          rap["brut"]["m"] >= 1, True)


def _daily_l17(stations, n_jours=15, err_par_modele=(("icon_d2", 3.0),
                                                     ("icon_eu", 4.0))):
    """Des balise-jours réguliers pour `stations` — la scène du L17 ne
    teste pas le classement, elle teste QUI ENTRE dedans."""
    daily = []
    for j in range(n_jours):
        d = (DAY - timedelta(days=j)).strftime("%Y-%m-%d")
        for unite in stations:
            src, sid = unite.split(":", 1)
            for model, err in err_par_modele:
                daily.append({
                    "day": d, "source": src, "station_id": sid,
                    "model": model, "lead_h": 6, "n_hours": 24,
                    "err_vec_med": err, "err_vec_rms": err + 1.0,
                    "mse_model": None, "mse_persist": None,
                    "mse_clim": None, "err_vec_med_corr": None,
                    "mse_model_corr": None, "bias_n_days": None,
                })
    return daily


def _zones_l17(stations, zid="b1:valley", landform="valley"):
    return {u: {"zone_id": zid, "landform": landform, "basin_id": "b1",
                "massif_id": "alpes-nord", "basin_uncertain": False}
            for u in stations}


def test_l17_doublon_ecarte_du_classement():
    """Lot L17 (27/08/2026) — une SECONDE inscription du même capteur ne
    doit peser ni dans le `n` d'une case, ni dans son QUORUM.

    ⛔ Le quorum est le vrai sujet. `MIN_STATIONS_ZONE` vaut 3 : mesuré
    sur la production le 27/08, 80 à 92 cases publiées n'avaient leur
    troisième station que parce qu'elle était le doublon de la première.
    """
    print("── lot L17 : le doublon d'inscription sort du classement ──")
    trois = ["pioupiou:1", "pioupiou:2", "pioupiou:3"]
    zone_of = _zones_l17(trois)
    daily = _daily_l17(trois)
    base = J._case_rows([dict(d, unit=f"{d['source']}:{d['station_id']}")
                         for d in daily], zone_of, DAY, "rolling15", "all",
                        J.MIN_STATIONS_ZONE, with_ci=False)
    check("trois vraies balises : la case est publiée",
          len({J._cle_de_case(r) for r in base}) > 0, True)
    n_base = sum(int(r.get("occurrences") or 0) for r in base)

    # ── la MÊME case, mais la troisième est un doublon de la première ──
    zone_dbl = _zones_l17(trois)
    zone_dbl["pioupiou:3"]["doublon_de"] = "pioupiou:1"
    apres = J._case_rows([dict(d, unit=f"{d['source']}:{d['station_id']}")
                          for d in daily], zone_dbl, DAY, "rolling15", "all",
                         J.MIN_STATIONS_ZONE, with_ci=False)
    check("⭐ la case tombe sous le quorum et DISPARAÎT", len(apres), 0)

    # ── quatre vraies + un doublon : la case survit, le `n` est corrigé ──
    quatre = trois + ["pioupiou:4"]
    cinq = quatre + ["pioupiou:5"]
    z5 = _zones_l17(cinq)
    d5 = _daily_l17(cinq)
    units5 = [dict(d, unit=f"{d['source']}:{d['station_id']}") for d in d5]
    avec = J._case_rows(units5, z5, DAY, "rolling15", "all",
                        J.MIN_STATIONS_ZONE, with_ci=False)
    z5b = _zones_l17(cinq)
    z5b["pioupiou:5"]["doublon_de"] = "pioupiou:1"
    sans = J._case_rows(units5, z5b, DAY, "rolling15", "all",
                        J.MIN_STATIONS_ZONE, with_ci=False)
    n_avec = sum(int(r.get("occurrences") or 0) for r in avec
                 if r["agg_level"] == "basin_landform")
    n_sans = sum(int(r.get("occurrences") or 0) for r in sans
                 if r["agg_level"] == "basin_landform")
    check("la case à 4 vraies balises survit", len(sans) > 0, True)
    check("⭐ et son `n` perd exactement le cinquième", n_sans * 5, n_avec * 4)

    # ── ⭐ ÉCARTER LE DOUBLON REND EXACTEMENT LA MÊME NUIT QUE SI LA
    # SECONDE INSCRIPTION N'AVAIT JAMAIS EXISTÉ. C'est l'assertion qui
    # compte : elle dit que le geste RETIRE, il ne corrige pas.
    z4 = _zones_l17(quatre)
    units4 = [dict(d, unit=f"{d['source']}:{d['station_id']}")
              for d in _daily_l17(quatre)]
    jamais = J._case_rows(units4, z4, DAY, "rolling15", "all",
                          J.MIN_STATIONS_ZONE, with_ci=False)
    def _resume(rows):
        return sorted((r["zone_id"], r["model"], r["lead_h"], r["agg_level"],
                       r["occurrences"], r["rank"], r["rank_reason"])
                      for r in rows)
    check("⭐ la nuit dédoublonnée == la nuit où le doublon n'existait pas",
          _resume(sans), _resume(jamais))

    # ⛔ `doublon_de` vide ou absent n'écarte personne : une colonne
    # jamais posée (le SQL step55 pas encore joué) doit laisser la nuit
    # EXACTEMENT comme avant.
    for valeur in (None, "", 0):
        z = _zones_l17(trois)
        z["pioupiou:3"]["doublon_de"] = valeur
        r = J._case_rows([dict(d, unit=f"{d['source']}:{d['station_id']}")
                          for d in daily], z, DAY, "rolling15", "all",
                         J.MIN_STATIONS_ZONE, with_ci=False)
        check(f"`doublon_de = {valeur!r}` n'écarte personne",
              sum(int(x.get("occurrences") or 0) for x in r), n_base)

    # ⛔ PAS DE PURGE SILENCIEUSE — c'est une règle du chantier, donc
    # elle se teste. Une exclusion qui ne s'annonce pas devient un fait
    # acquis que personne ne peut plus contester six mois plus tard.
    import contextlib, io                                    # noqa: E401
    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon):
        J._case_rows([dict(d, unit=f"{d['source']}:{d['station_id']}")
                      for d in _daily_l17(cinq)], z5b, DAY, "rolling15",
                     "all", J.MIN_STATIONS_ZONE, with_ci=False)
    journal = tampon.getvalue()
    n_attendu = 15 * 2      # 15 jours × 2 modèles pour la balise écartée
    check("⭐ le journal ANNONCE combien il a écarté",
          [f"{n_attendu} balise-jour(s) écarté(s)" in journal,
           J.COL_DOUBLON in journal, "L17" in journal],
          [True, True, True])

    check("`est_doublon` dit la même chose que les trois appelants",
          [J.est_doublon(None), J.est_doublon({}),
           J.est_doublon({"doublon_de": None}),
           J.est_doublon({"doublon_de": "pioupiou:1"})],
          [False, False, False, True])


def test_l17_doublon_ecarte_des_accumulateurs():
    """⛔ LA MÉMOIRE LONGUE AUSSI. `model_character` accumule sur une
    demi-vie de 30 jours : un doublon non écarté là continuerait de
    peser un mois APRÈS que le classement a cessé de le compter."""
    print("── lot L17 : le doublon sort aussi des accumulateurs ──")
    stations = ["pioupiou:1", "pioupiou:2", "pioupiou:3"]
    banded = [{"key": u, "model": "icon_d2", "lead_h": 6, "regime": "fluxN",
               "band": "10-20", "errKmh": 3.0 + i}
              for i, u in enumerate(stations)]
    zone_of = _zones_l17(stations)
    avant = J.accumulator_updates(banded, zone_of)
    z2 = _zones_l17(stations)
    z2["pioupiou:3"]["doublon_de"] = "pioupiou:1"
    apres = J.accumulator_updates(banded, z2)
    med_avant = {(r["zone_id"], r["regime"], r["band"]): r["x"]
                 for r in avant if r["metric"] == "errKmh"}
    med_apres = {(r["zone_id"], r["regime"], r["band"]): r["x"]
                 for r in apres if r["metric"] == "errKmh"}
    check("⭐ la médiane accumulée change quand le doublon sort",
          med_avant != med_apres, True)
    cle = ("b1:valley", "fluxN", "10-20")
    check("trois balises (3, 4, 5) → médiane 4", med_avant.get(cle), 4.0)
    check("deux balises (3, 4) → médiane 3,5", med_apres.get(cle), 3.5)


def test_light_scores_sous_ensemble_exact():
    print("── S13.0 : le léger est un sous-ensemble exact du gros ──")
    plein = {
        "as_of": "2026-08-24", "zone_id": "b1:valley", "model": "icon_d2",
        "lead_h": 6, "window_kind": "rolling15", "regime": "all",
        "agg_level": "basin_landform", "n_stations": 4, "n_hours": 48,
        "occurrences": 40, "typical_err_kmh": 3.5, "worst_decile_kmh": 6.1,
        "beats_persist": True, "skill": 0.4, "beats_clim": True,
        "skill_clim": 0.3, "typical_err_kmh_corr": None,
        "beats_clim_corr": None, "skill_clim_corr": None, "n_corr": 0,
        "bias_n_days": None, "ci_low": 2.9, "ci_high": 4.1, "rank": 1,
        "rank_reason": "ok", "rank_corr": None,
        "rank_reason_corr": "mixed_population", "err_sd": 1.2, "n_days": 15,
        "n_comparable": 37,
        # ── lot L9a : le compagnon WMO entre dans le léger ──
        "bias_ratio": 1.084, "bias_dir_deg": -12.4, "n_bias_dir": 31,
        "ci_kind": "block_day", "ci_reason": "ok", "block_days": 15,
        "pooled_err_kmh": None, "borrowed_weight": 0.0, "variable": "wind",
    }
    regime = {**plein, "window_kind": "regime", "regime": "fluxN"}
    scores = [plein, regime]
    light = J.light_score_rows(scores)
    check("seule la ligne `rolling15` sort", len(light), 1)
    check("les champs sont EXACTEMENT ceux du prompt S13.0 (zone_id, "
          "agg_level, lead_h, model, typical_err_kmh ± IC, n_days, "
          "n_hours, rank, rank_reason, borrowed_weight)",
          sorted(light[0]), sorted(J.LIGHT_SCORE_FIELDS))
    for champ in J.LIGHT_SCORE_FIELDS:
        check(f"… `{champ}` recopié tel quel, jamais recalculé",
              light[0][champ], plein[champ])

    pres = {**plein, "variable": "pres"}
    check("⛔ une ligne `pres` ne doit JAMAIS entrer, même seule",
          J.light_score_rows([pres]), [])
    check("une ligne `window_kind='regime'` seule ne publie rien non plus",
          J.light_score_rows([regime]), [])


def test_light_scores_bout_en_bout_ne_recalcule_rien():
    print("── S13.0 : bout en bout, depuis `rolling_scores` réel ──")
    zone_of = {f"pioupiou:{i}": {"zone_id": "b1:valley", "landform": "valley",
                                 "basin_id": "b1", "massif_id": "alpes-nord",
                                 "basin_uncertain": False}
               for i in range(830, 836)}
    daily = []
    for j in range(15):
        d = (DAY - timedelta(days=j)).strftime("%Y-%m-%d")
        for i in range(830, 836):
            for model, err in (("icon_d2", 4.0), ("gfs_global", 9.0)):
                daily.append({
                    "day": d, "source": "pioupiou", "station_id": str(i),
                    "model": model, "lead_h": 24, "regime": "fluxN",
                    "n_hours": 12, "err_vec_med": err,
                    "mse_model": err * err, "mse_persist": 100.0})
    full = J.rolling_scores(daily, zone_of, DAY)
    for r in full:
        r.setdefault("variable", "wind")
    light = J.light_score_rows(full)
    check("aucune ligne perdue à fenêtre rolling15/wind égale",
          len(light), len(full))
    by_key = {(r["zone_id"], r["lead_h"], r["model"]): r for r in full}
    for lr in light:
        fr = by_key[(lr["zone_id"], lr["lead_h"], lr["model"])]
        for champ in J.LIGHT_SCORE_FIELDS:
            check(f"léger == gros sur `{champ}` "
                  f"({lr['zone_id']}/{lr['model']})", lr[champ], fr[champ])


def test_l9b_les_moments_de_murphy_voyagent_sans_toucher_la_base():
    print("── L9b : les six sommes de Murphy, clé privée du balise-jour ──")
    import murphy as MU_                                  # noqa: PLC0415
    snapshots = {
        0: [fcst_line("835", "icon_d2", DAY, lambda i: brise(i % 24) * 1.3)],
        1: [], 2: [],
    }
    obs_j = [obs_line("835", DAY, brise)]
    obs_v = [obs_line("835", DAY - timedelta(days=1), brise)]
    rows, _ = J.daily_rows(DAY, snapshots, obs_j, obs_v, utc_offset_s=7200)
    r = next(r for r in rows if r["lead_h"] == 6)

    check("chaque balise-jour porte la clé privée `_murphy`",
          MU_.MURPHY_KEY in r, True)
    check("… et elle commence bien par `_` (c'est ce qui la tient hors "
          "de la base)", MU_.MURPHY_KEY.startswith("_"), True)
    mom = r[MU_.MURPHY_KEY]
    check("… six sommes, pas les couples", len(mom), 6)
    check("… dont le n coïncide avec les heures notées de la ligne",
          mom[0], r["n_hours"])
    # ⛔ LA VALEUR, RECALCULÉE PAR UN AUTRE CHEMIN : le rapport Σfo/Σoo
    # d'un modèle qui vaut 1,30 × l'observation doit valoir ~1,30.
    check("⭐ Σfo/Σo² retrouve le facteur 1,30 du modèle d'essai "
          "(les sommes disent bien ce qu'elles prétendent)",
          mom[5] / mom[4], 1.30, 0.02)

    # ⛔ ET ELLE NE PART JAMAIS EN BASE — y compris quand le schéma est
    # ILLISIBLE. C'est le chemin qui compte : `_pour_la_base` renvoie les
    # lignes TELLES QUELLES quand `sb.columns()` rend `None`, et une clé
    # qui n'est jamais une colonne transformerait cette panne bénigne en
    # `PGRST204` certain, toutes les nuits.
    class _SbMuet:
        def columns(self, table):
            return None

    class _SbConnu:
        def columns(self, table):
            return set(rows[0]) - {MU_.MURPHY_KEY}

    for nom, sb in (("schéma ILLISIBLE", _SbMuet()),
                    ("schéma connu", _SbConnu())):
        sortie = J._pour_la_base(sb, "model_verif_daily", [dict(r)])
        check(f"⛔ `_murphy` ne part pas en base ({nom})",
              MU_.MURPHY_KEY in sortie[0], False)
        check(f"… et le reste de la ligne est intact ({nom})",
              sortie[0]["err_vec_med"], r["err_vec_med"])

    # … et le journal ne réclame AUCUN `.sql` pour une clé privée.
    import contextlib                                      # noqa: PLC0415
    import io                                              # noqa: PLC0415
    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon):
        J._pour_la_base(_SbConnu(), "model_verif_daily", [dict(r)])
    check("⛔ … et le journal ne nomme aucun `.sql` à jouer pour elle",
          "supabase_step" in tampon.getvalue(), False)

    # Le cache de rejeu, lui, DOIT la porter : c'est sa raison d'être.
    tmp = pathlib.Path(tempfile.mkdtemp())
    J.replay_write(tmp, DAY, rows)
    relu = J.replay_read(tmp, DAY)
    check("⭐ le cache de rejeu, lui, porte les six sommes",
          relu[0][MU_.MURPHY_KEY], rows[0][MU_.MURPHY_KEY])
    check("… et la formule du cache est bien la 5 (les moments + "
          "`mse_comb` l'ont fait passer de 4)", J.REPLAY_FORMULA, 5)

    # ── ⛔ ET LA MÉMOIRE, qui est la vraie contrainte (28/08) ─────────
    # La fenêtre rejouée porte 405 486 lignes en production. Y laisser
    # une liste de six flottants coûte ~107 Mo au pic, sur un VPS de
    # 3,8 Go SANS SWAP dont le run de cette nuit-là a été tué par l'OOM
    # killer. `replay_window` FOND donc les sommes au passage et RETIRE
    # la clé de la ligne.
    acc: dict = {}
    lus, _bilan = J.replay_window(tmp, DAY, None, 7200, n_days=1,
                                  murphy_acc=acc)
    check("⛔ aucune ligne rendue par `replay_window` ne porte encore "
          "`_murphy` — la mémoire de la fenêtre ne le paie pas",
          any(MU_.MURPHY_KEY in l for l in lus), False)
    check("⭐ … et pourtant l'accumulateur, lui, l'a bien reçu",
          len(acc) > 0, True)
    cle = (f"{rows[0]['source']}:{rows[0]['station_id']}",
           rows[0]["model"], rows[0]["lead_h"])
    check("… sous la clé (balise, modèle, échéance)", cle in acc, True)
    check("… avec les six sommes de la journée, plus le compteur de "
          "journées", (list(acc[cle][:6]), acc[cle][6]),
          (list(rows[0][MU_.MURPHY_KEY]), 1))
    # ⚠️ Sans accumulateur, la clé disparaît QUAND MÊME : personne
    # d'autre ne la lit, et la laisser traîner ferait payer la mémoire
    # à `regime_scores` et `stability_report`.
    lus2, _ = J.replay_window(tmp, DAY, None, 7200, n_days=1)
    check("⛔ … et sans accumulateur du tout, la clé disparaît aussi",
          any(MU_.MURPHY_KEY in l for l in lus2), False)

    # ⭐ LES DEUX CHEMINS RENDENT LE MÊME OBJET. `par_balise` (lignes,
    # pour le rapport ponctuel et le banc) et `par_balise_depuis_acc`
    # (l'accumulateur, pour le run) ne doivent pas diverger — c'est le
    # défaut classique des deux consommateurs (BUGS.md, 26/08).
    lignes_acc = MU_.par_balise_depuis_acc(acc, min_pairs=1, min_days=1)
    units_ref = [{**r, "unit": f"{r['source']}:{r['station_id']}"}
                 for r in rows]
    lignes_dir = MU_.par_balise(units_ref, min_pairs=1, min_days=1)
    check("⭐ l'accumulateur et le chemin par lignes rendent EXACTEMENT "
          "le même objet", lignes_acc, lignes_dir)


def test_l9c_reference_combinee_bout_en_bout():
    print("── L9c : la référence combinée, du balise-jour à la case ──")
    # ── 1. `daily_rows` : deux colonnes, et rien sans les deux entrées ─
    snapshots = {
        0: [fcst_line("835", "icon_d2", DAY, lambda i: brise(i % 24) * 1.2)],
        1: [], 2: [],
    }
    obs_j = [obs_line("835", DAY, brise)]
    obs_v = [obs_line("835", DAY - timedelta(days=1),
                      lambda h: brise(h) * 0.6)]
    clim = {"pioupiou:835": {h: (brise(h) * 0.8, None, 12) for h in range(24)}}

    sans, _ = J.daily_rows(DAY, snapshots, obs_j, obs_v, 7200, clim)
    r_sans = next(r for r in sans if r["lead_h"] == 6)
    check("⛔ sans `poids_comb`, `mse_comb` reste NUL — jamais un poids "
          "inventé", r_sans["mse_comb"], None)
    check("… et son témoin apparié aussi", r_sans["mse_model_comb"], None)

    avec, _ = J.daily_rows(DAY, snapshots, obs_j, obs_v, 7200, clim,
                           poids_comb={"pioupiou:835": 0.5})
    r = next(r for r in avec if r["lead_h"] == 6)
    check("avec les deux, `mse_comb` est chiffré",
          r["mse_comb"] is not None, True)
    check("⛔ … et `mse_model_comb` VOYAGE AVEC LUI (le témoin sur la "
          "même population d'heures)", r["mse_model_comb"] is not None, True)
    # ── la SECONDE définition, sur la même ligne (02/09/2026) ─────────
    # ⛔ SANS CETTE ASSERTION, LA COLONNE PEUT NE JAMAIS ÊTRE ÉCRITE.
    # Toutes les épreuves de case plus bas partent de dictionnaires
    # fabriqués à la main : elles vérifient ce que `_case_rows` FAIT de
    # la colonne, jamais que `daily_rows` la POSE. Une mutation qui
    # remplace `_r(mse_cbv)` par `None` les laisse toutes vertes — et la
    # colonne existerait en base, vide, pour toujours.
    check("⭐⭐ `mse_comb_vec` est POSÉ par `daily_rows`, sur la même "
          "ligne et sous les mêmes conditions", r["mse_comb_vec"] is not None,
          True)
    check("⛔ … et il reste NUL quand `mse_comb` l'est (mêmes entrées, "
          "mêmes silences)", r_sans["mse_comb_vec"], None)
    # ⭐ ET SUR CETTE LIGNE-CI ELLES COÏNCIDENT, POUR UNE RAISON QU'IL
    # FAUT DIRE : la climatologie de la fixture n'a pas de cap
    # (`(brise(h) * 0.8, None, 12)`). Sans cap des deux côtés il n'y a
    # aucun vecteur à mélanger, et les deux définitions DOIVENT rendre le
    # même nombre — c'est ce qui garantit que l'écart entre les deux
    # colonnes publiées ne vient jamais des girouettes manquantes.
    check("⭐ sans cap côté climatologie, les deux colonnes coïncident au "
          "bit près (bout en bout, pas seulement dans `inference`)",
          abs(r["mse_comb_vec"] - r["mse_comb"]) < 1e-12, True)
    # ⛔ ET AVEC UN CAP, ELLES DOIVENT DIVERGER — sinon la seconde
    # définition ne serait qu'un alias coûteux de la première, et rien
    # dans ce fichier ne le dirait.
    clim_cap = {"pioupiou:835": {h: (brise(h) * 0.8, (h * 37) % 360, 12)
                                 for h in range(24)}}
    avec_cap, _ = J.daily_rows(DAY, snapshots, obs_j, obs_v, 7200, clim_cap,
                               poids_comb={"pioupiou:835": 0.5})
    r_cap = next(x for x in avec_cap if x["lead_h"] == 6)
    check("⭐⭐ avec un cap climatologique, les deux définitions DIVERGENT "
          "bout en bout — l'espace du mélange décide vraiment",
          abs(r_cap["mse_comb_vec"] - r_cap["mse_comb"]) > 1e-6, True)
    check("le reste de la ligne n'a pas bougé d'un chiffre",
          (r["err_vec_med"], r["mse_model"], r["mse_persist"]),
          (r_sans["err_vec_med"], r_sans["mse_model"],
           r_sans["mse_persist"]))
    # ⭐ Les bornes, jusqu'au bout de la chaîne : k = 1 doit rendre le MSE
    # de la persistance, k = 0 celui de la climatologie.
    k1, _ = J.daily_rows(DAY, snapshots, obs_j, obs_v, 7200, clim,
                         poids_comb={"pioupiou:835": 1.0})
    k0, _ = J.daily_rows(DAY, snapshots, obs_j, obs_v, 7200, clim,
                         poids_comb={"pioupiou:835": 0.0})
    r1 = next(x for x in k1 if x["lead_h"] == 6)
    r0 = next(x for x in k0 if x["lead_h"] == 6)
    check("⭐ k = 1 → `mse_comb` == `mse_persist` de la même ligne",
          r1["mse_comb"], r1["mse_persist"], 5e-4)
    check("⭐ k = 0 → `mse_comb` == `mse_clim` de la même ligne",
          r0["mse_comb"], r0["mse_clim"], 5e-4)
    check("⭐⭐ … et le mélange à 0,5 fait MIEUX que les deux (Murphy "
          "1992, sur une vraie ligne de production)",
          r["mse_comb"] <= min(r1["mse_comb"], r0["mse_comb"]) + 1e-6, True)

    # ── 2. `_case_rows` : le skill de la case, sur le BON témoin ──────
    zone_of = {f"pioupiou:{i}": {"zone_id": "b1:valley", "landform": "valley",
                                 "basin_id": "b1", "massif_id": "alpes-nord",
                                 "basin_uncertain": False}
               for i in range(1, 5)}
    daily = []
    for j in range(6):
        d = (DAY - timedelta(days=j)).strftime("%Y-%m-%d")
        for i in range(1, 5):
            daily.append({
                "day": d, "source": "pioupiou", "station_id": str(i),
                "model": "icon_d2", "lead_h": 6, "regime": "fluxN",
                "n_hours": 20, "err_vec_med": 4.0,
                # ⛔ LA SCÈNE QUI SÉPARE LES DEUX TÉMOINS. `mse_model`
                # (population « persistance ») vaut 1,0 ; le modèle sur
                # les heures du MÉLANGE en vaut 4,0. Un code qui
                # reprendrait `mse_model` publierait skill_comb = 0,875
                # au lieu de 0,5.
                "mse_model": 1.0, "mse_persist": 100.0,
                "mse_model_comb": 4.0, "mse_comb": 8.0})
    fine = [r for r in J.rolling_scores(daily, zone_of, DAY)
            if r["zone_id"] == "b1:valley"][0]
    check("⭐ `skill_comb` = 1 − 4/8 = 0,5 (le témoin apparié)",
          fine["skill_comb"], 0.5, 1e-6)
    check("⛔ … et PAS 0,875, qu'aurait donné `mse_model` de la "
          "population « persistance »",
          abs(fine["skill_comb"] - 0.875) > 0.3, True)
    check("`beats_comb` est vrai quand le modèle fait mieux",
          fine["beats_comb"], True)
    check("⚠️ il reste À CÔTÉ : `skill` et `skill_clim` n'ont pas bougé",
          fine["skill"], 0.99, 1e-6)

    perd = [{**d, "mse_model_comb": 9.0} for d in daily]
    fine_p = [r for r in J.rolling_scores(perd, zone_of, DAY)
              if r["zone_id"] == "b1:valley"][0]
    check("un modèle battu par la référence la plus dure le dit",
          fine_p["beats_comb"], False)

    vieux = [{k: v for k, v in d.items()
              if k not in ("mse_comb", "mse_model_comb")} for d in daily]
    fine_v = [r for r in J.rolling_scores(vieux, zone_of, DAY)
              if r["zone_id"] == "b1:valley"][0]
    check("des balise-jours d'avant le lot laissent la case muette, pas "
          "cassée", (fine_v["skill_comb"], fine_v["beats_comb"]),
          (None, None))

    # ── 2 bis. LA SECONDE DÉFINITION, ET SON COMPTE (02/09/2026) ─────
    #
    # ⛔ LA SCÈNE EST CELLE QUI ARRIVE VRAIMENT LE 02/09 : la colonne
    # `mse_comb_vec` est neuve, donc la fenêtre `rolling15` mélange des
    # balise-jours qui la portent (les nuits d'après le déploiement) et
    # des balise-jours qui ne la portent pas (ceux déjà en base, qu'AUCUN
    # rejeu ne pourra combler — `replay_day` ne lit pas la climatologie).
    # Un banc qui donnerait la colonne à TOUS les balise-jours testerait
    # une situation qui n'existera pas avant quinze nuits.
    mixte = []
    for n_j, d in enumerate(daily):
        # Une journée sur trois porte la colonne neuve — et son
        # `mse_comb_vec` est DÉLIBÉRÉMENT différent de `mse_comb` (4,0
        # contre 8,0) : deux colonnes qui coïncideraient ne diraient rien
        # de l'endroit où le skill neuf va chercher son dénominateur.
        mixte.append({**d, "mse_comb_vec": 4.0} if n_j % 3 == 0 else dict(d))
    fine_m = [r for r in J.rolling_scores(mixte, zone_of, DAY)
              if r["zone_id"] == "b1:valley"][0]
    check("⭐ `n_comb` compte TOUS les balise-jours porteurs du mélange",
          fine_m["n_comb"], 24)
    check("⭐⭐ `n_comb_vec` ne compte QUE ceux qui portent la colonne "
          "neuve — c'est lui qui dit que la comparaison n'est pas encore "
          "posée", fine_m["n_comb_vec"], 8)
    check("⛔⛔ le skill neuf prend SON numérateur sur SA population : "
          "1 − 4/4 = 0, pas 1 − 4/4 lu sur une autre médiane",
          fine_m["skill_comb_vec"], 0.0, 1e-6)
    check("⚠️ … et l'ancien n'a PAS bougé (les deux colonnes cohabitent "
          "sans se toucher)", fine_m["skill_comb"], 0.5, 1e-6)
    check("`beats_comb_vec` est faux quand le modèle ne bat pas la "
          "référence vectorielle", fine_m["beats_comb_vec"], False)

    # ⭐ LE CAS OÙ LES DEUX COLONNES REPOSENT SUR LA MÊME MATIÈRE — celui
    # qu'on attend après quinze nuits, et le seul où les comparer a un
    # sens. `n_comb_vec == n_comb` est la façon de le LIRE.
    tout_vec = [{**d, "mse_comb_vec": 16.0} for d in daily]
    fine_t = [r for r in J.rolling_scores(tout_vec, zone_of, DAY)
              if r["zone_id"] == "b1:valley"][0]
    check("⭐ quand tous les balise-jours la portent, les deux comptes "
          "sont ÉGAUX — la comparaison est posée",
          (fine_t["n_comb"], fine_t["n_comb_vec"]), (24, 24))
    check("⭐⭐ et le skill neuf se calcule bien contre SA référence "
          "(1 − 4/16 = 0,75), pas contre celle de l'autre colonne",
          fine_t["skill_comb_vec"], 0.75, 1e-6)

    # ⛔⛔ LA SCÈNE QUI SÉPARE LE NUMÉRATEUR DU DÉNOMINATEUR, et sans
    # laquelle les deux précédentes ne prouvent rien. Ci-dessus,
    # `mse_model_comb` vaut 4,0 PARTOUT : prendre sa médiane sur tous les
    # balise-jours ou sur le sous-ensemble porteur donne le même nombre,
    # donc un code qui se tromperait de population resterait vert.
    # Ici les deux groupes ont des numérateurs DIFFÉRENTS — 2,0 pour ceux
    # qui portent la colonne neuve, 10,0 pour les autres — et la faute
    # devient visible : le bon skill vaut 1 − 2/4 = 0,5, celui qui
    # prendrait la médiane globale (10,0) rendrait −1,5.
    separe = []
    for n_j, d in enumerate(daily):
        if n_j % 3 == 0:
            separe.append({**d, "mse_model_comb": 2.0, "mse_comb_vec": 4.0})
        else:
            separe.append({**d, "mse_model_comb": 10.0})
    fine_s = [r for r in J.rolling_scores(separe, zone_of, DAY)
              if r["zone_id"] == "b1:valley"][0]
    check("⭐⭐ le skill vectoriel prend son NUMÉRATEUR et son "
          "DÉNOMINATEUR dans le même filtre (1 − 2/4 = 0,5)",
          fine_s["skill_comb_vec"], 0.5, 1e-6)
    check("⛔ … et surtout PAS −1,5, qu'aurait donné la médiane de "
          "`mse_model_comb` sur TOUS les balise-jours",
          abs(fine_s["skill_comb_vec"] + 1.5) > 0.5, True)

    # ⛔ Des balise-jours d'AVANT le lot : la colonne neuve se tait, et
    # son compte le DIT (0), au lieu de laisser croire à une case sans
    # matière. C'est la différence entre « pas encore » et « rien ».
    check("des balise-jours sans la colonne neuve laissent le skill "
          "vectoriel muet…", fine["skill_comb_vec"], None)
    check("⭐ … et `n_comb_vec` vaut 0 pendant que `n_comb` en compte 24 "
          "— « pas encore », pas « rien »",
          (fine["n_comb"], fine["n_comb_vec"]), (24, 0))

    # ── 3. le fichier léger ne s'alourdit PAS de ces deux champs ──────
    for champ in ("skill_comb", "beats_comb", "skill_comb_vec",
                  "beats_comb_vec", "n_comb", "n_comb_vec"):
        check(f"⛔ `{champ}` n'entre PAS dans le fichier léger (la "
              f"pastille n'affiche aucun skill)",
              champ in J.LIGHT_SCORE_FIELDS, False)

    # ── 4. le `.sql` est nommé, pour ces colonnes-ci aussi ────────────
    class _SbFactice:
        def columns(self, table):
            return {"day", "source", "station_id", "model", "lead_h",
                    "err_vec_med", "mse_model", "mse_persist", "mse_clim"}
    import contextlib                                      # noqa: PLC0415
    import io                                              # noqa: PLC0415
    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon):
        sortie = J._pour_la_base(_SbFactice(), "model_verif_daily", [dict(r)])
    dit = tampon.getvalue()
    check("⛔ `mse_comb` absente en base → step57 nommé, jamais step40",
          "supabase_step57_lot_l9_compagnons.sql" in dit
          and "step40" not in dit, True)
    check("… et la colonne ne part pas en base tant qu'elle n'existe pas",
          "mse_comb" in sortie[0], False)

    # ── 5. le cache de climatologie porte les DEUX, sous un nom NEUF ──
    # ⛔ POURQUOI CE BANC. Le cache d'avant ce lot ne porte pas `k`.
    # Relu sous son ancien nom, il aurait rendu une climatologie
    # complète et AUCUN poids : `mse_comb` serait resté vide toute la
    # journée du déploiement, et rien — ni log, ni colonne — ne l'aurait
    # distingué d'une archive trop courte.
    import gzip as _gz2                                    # noqa: PLC0415
    import json as _json2                                  # noqa: PLC0415
    tmp = pathlib.Path(tempfile.mkdtemp())
    (tmp / J.CLIM_SUBDIR).mkdir(parents=True, exist_ok=True)
    corps = {"clim": {"pioupiou:1": {"12": [11.0, 200.0, 9]}},
             "k": {"pioupiou:1": 0.42}}
    (tmp / J.CLIM_SUBDIR /
     f"clim_{DAY:%Y-%m-%d}_{J.CLIM_DAYS}_v2.json.gz").write_bytes(
        _gz2.compress(_json2.dumps(corps).encode()))
    # Le cache d'AVANT le lot, même journée, contenu DIFFÉRENT : il ne
    # doit jamais être lu.
    (tmp / J.CLIM_SUBDIR /
     f"clim_{DAY:%Y-%m-%d}_{J.CLIM_DAYS}.json.gz").write_bytes(
        _gz2.compress(_json2.dumps(
            {"clim": {"pioupiou:999": {"12": [99.0, 1.0, 9]}}}).encode()))
    c_lu, k_lu = J.climatology_by_station(tmp, DAY, None, 7200)
    check("⭐ le cache rend un COUPLE (climatologie, poids)",
          (sorted(c_lu), k_lu), (["pioupiou:1"], {"pioupiou:1": 0.42}))
    check("… avec l'heure relue en ENTIER, pas en chaîne",
          list(c_lu["pioupiou:1"]), [12])
    check("⛔ le cache d'avant le lot (sans `_v2`) n'est PAS lu — sinon "
          "tous les `k` sortiraient nuls sans que rien ne le dise",
          "pioupiou:999" in c_lu, False)

    # ── 6. ALLER-RETOUR COMPLET : calculé une fois, RELU ensuite ──────
    # ⛔ LE BANC DU DESSUS NE PROUVE QUE LA LECTURE. Un cache où l'on
    # oublierait d'ÉCRIRE `k` passerait la première nuit (le calcul a
    # lieu) et perdrait le poids toutes les suivantes — c'est-à-dire
    # que `mse_comb` marcherait le soir du déploiement et disparaîtrait
    # le lendemain. On fabrique donc une archive, on laisse la fonction
    # CALCULER, puis on la rappelle pour qu'elle RELISE.
    tmp2 = pathlib.Path(tempfile.mkdtemp())
    # Anomalie journalière PERSISTANTE (un décalage propre à chaque
    # journée, corrélé d'un jour sur l'autre) : sans elle, ρ n'existe
    # pas et le banc ne prouverait rien.
    def _obs_du_jour(root_, d_, storage_):
        j = (d_ - (DAY - timedelta(days=11))).days
        ecart = 3.0 * math.cos(j * 0.4)
        return [obs_line("1", d_, lambda h, e=ecart: brise(h) + e)]

    vrai_all_obs = J.all_obs_rows
    J.all_obs_rows = _obs_du_jour
    try:
        c_calc, k_calc = J.climatology_by_station(tmp2, DAY, None, 0)
        c_relu, k_relu = J.climatology_by_station(tmp2, DAY, None, 0)
    finally:
        J.all_obs_rows = vrai_all_obs
    check("l'archive fabriquée donne bien une climatologie",
          "pioupiou:1" in c_calc, True)
    check("⭐ … ET un poids `k`, calculé sur les mêmes journées",
          k_calc.get("pioupiou:1") is not None, True,)
    check("⭐⭐ le second appel RELIT le cache et retrouve le MÊME poids "
          "— sans quoi `mse_comb` marcherait le soir du déploiement et "
          "disparaîtrait le lendemain", k_relu, k_calc)
    check("… et la même climatologie", sorted(c_relu), sorted(c_calc))
    check("le fichier de cache porte bien le suffixe `_v2`",
          (tmp2 / J.CLIM_SUBDIR /
           f"clim_{DAY:%Y-%m-%d}_{J.CLIM_DAYS}_v2.json.gz").exists(), True)


def test_l9a_compagnon_wmo_biais_de_vitesse_et_de_cap():
    print("── L9a : le biais de vitesse et de cap, compagnons du score ──")
    # Cinq balises, cinq jours. Les `bias_ratio` sont choisis pour que la
    # MÉDIANE et la MOYENNE diffèrent franchement (une valeur très haute
    # tire la moyenne, pas la médiane) : sans ça, la mutation « moyenne
    # au lieu de médiane » resterait verte — piège nº 2 de la phase B,
    # « le jeu doit être irrégulier dans la dimension testée ».
    zone_of = {f"pioupiou:{i}": {"zone_id": "b1:valley", "landform": "valley",
                                 "basin_id": "b1", "massif_id": "alpes-nord",
                                 "basin_uncertain": False}
               for i in range(1, 6)}
    RATIOS = [0.90, 0.95, 1.00, 1.05, 4.00]       # médiane 1,00 · moyenne 1,58
    # Les écarts de CAP sont à cheval sur le demi-tour : leur moyenne
    # circulaire vaut 180°, leur moyenne (et leur médiane) arithmétique 0.
    CAPS = [179.0, -179.0, 178.0, -178.0, None]
    daily = []
    for j in range(5):
        d = (DAY - timedelta(days=j)).strftime("%Y-%m-%d")
        for i in range(1, 6):
            daily.append({
                "day": d, "source": "pioupiou", "station_id": str(i),
                "model": "icon_d2", "lead_h": 6, "regime": "fluxN",
                "n_hours": 20, "err_vec_med": 4.0,
                "mse_model": 16.0, "mse_persist": 100.0,
                "bias_ratio": RATIOS[i - 1],
                "bias_dir_deg": CAPS[i - 1]})
    rows = J.rolling_scores(daily, zone_of, DAY)
    fine = [r for r in rows if r["zone_id"] == "b1:valley"][0]

    check("`bias_ratio` de la case = MÉDIANE des balise-jours (1,00)",
          fine["bias_ratio"], 1.0)
    check("⛔ … et PAS leur moyenne (1,58), qu'une seule balise déréglée "
          "suffirait à imposer",
          abs(sum(RATIOS) / len(RATIOS) - 1.58) < 0.005, True)
    check("⭐ `bias_dir_deg` = moyenne CIRCULAIRE (180°), la seule qui "
          "voie le demi-tour", fine["bias_dir_deg"], 180.0)
    check("⛔ … là où la médiane arithmétique des mêmes écarts dirait "
          "« cap parfait »", S.median([c for c in CAPS if c is not None]),
          0.0)
    check("`n_bias_dir` compte les balise-jours qui PORTAIENT un cap "
          "(4 balises × 5 jours), pas les occurrences",
          fine["n_bias_dir"], 20)
    check("… et `occurrences` en compte 25 — le couple se lit ensemble",
          fine["occurrences"], 25)

    # ⛔ MÊME POPULATION QUE L'ERREUR, PROUVÉ PAR UNE EXCLUSION. Une
    # balise marquée `basin_uncertain` sort de la case : elle doit sortir
    # du compagnon AUSSI, sinon le biais publié porterait sur des
    # balise-jours que le score, lui, a refusés.
    zone_ko = {**zone_of}
    zone_ko["pioupiou:5"] = {**zone_of["pioupiou:5"], "basin_uncertain": True}
    fine_ko = [r for r in J.rolling_scores(daily, zone_ko, DAY)
               if r["zone_id"] == "b1:valley"][0]
    check("une balise exclue de la case sort aussi du compagnon "
          "(occurrences 25 → 20)", fine_ko["occurrences"], 20)
    check("… la balise à 4,00 étant sortie, la médiane du ratio descend "
          "à 0,975", fine_ko["bias_ratio"], 0.975)
    check("… `n_bias_dir` ne bouge pas : la balise sortie n'avait pas de "
          "cap", fine_ko["n_bias_dir"], 20)

    # Aucune direction du tout : le champ se tait, il n'invente pas 0°.
    daily_sans_cap = [{**d, "bias_dir_deg": None} for d in daily]
    fine_sc = [r for r in J.rolling_scores(daily_sans_cap, zone_of, DAY)
               if r["zone_id"] == "b1:valley"][0]
    check("⛔ aucun cap exploitable → `bias_dir_deg` nul, jamais 0°",
          fine_sc["bias_dir_deg"], None)
    check("… et `n_bias_dir` vaut 0, ce qui le DIT", fine_sc["n_bias_dir"], 0)

    # Un fichier d'avant ce lot ne porte pas les colonnes : la case doit
    # sortir muette, pas tomber.
    daily_vieux = [{k: v for k, v in d.items()
                    if k not in ("bias_ratio", "bias_dir_deg")} for d in daily]
    fine_v = [r for r in J.rolling_scores(daily_vieux, zone_of, DAY)
              if r["zone_id"] == "b1:valley"][0]
    check("des balise-jours d'avant le lot ne font pas tomber la case",
          (fine_v["bias_ratio"], fine_v["bias_dir_deg"], fine_v["n_bias_dir"]),
          (None, None, 0))

    # ⛔ LES TROIS CHAMPS SONT NOMMÉS EN TOUTES LETTRES, ET C'EST LE
    # POINT. `test_light_scores_sous_ensemble_exact` compare la sortie à
    # `J.LIGHT_SCORE_FIELDS` — donc au code testé lui-même : retirer un
    # champ du tuple retirerait les DEUX côtés de l'égalité et le banc
    # resterait vert (piège nº 1 de la phase B, 26/08). Ici la liste
    # attendue est écrite à la main : perdre `n_bias_dir` du léger
    # rougit.
    for champ in ("bias_ratio", "bias_dir_deg", "n_bias_dir"):
        check(f"⛔ `{champ}` est DANS le fichier léger (nommé à la main, "
              f"pas relu depuis la constante)",
              champ in J.LIGHT_SCORE_FIELDS, True)
    leger = J.light_score_rows([{**fine, "variable": "wind"}])
    check("… et il arrive bien jusqu'à la ligne publiée",
          (leger[0]["bias_ratio"], leger[0]["bias_dir_deg"],
           leger[0]["n_bias_dir"]), (1.0, 180.0, 20))

    # ⚠️ ET LE NOM DU `.sql`, parce que la fausse déduction « rejouer
    # step40 » a déjà coûté une session (audit §2.5, puis lot L3).
    #
    # ⚠️ LE SCHÉMA FACTICE A CHANGÉ AU LOT L13 (01/09), ET LE BANC DIT
    # MIEUX CE QU'IL VOULAIT DIRE. Il ne rendait que cinq colonnes :
    # celles du lot G, du S2 et du L3 manquaient elles aussi, et le
    # code d'alors ne nommait QUE le premier fichier de sa cascade.
    # Depuis le L13, tous les fichiers concernés sont nommés — donc
    # citer `step40` sur ce schéma-là serait devenu VRAI, et le banc
    # aurait rougi pour la bonne raison. On lui donne donc le schéma
    # qu'il décrivait : tout est en base SAUF les cinq colonnes du L9.
    class _SbFactice:
        def columns(self, table):
            return set(fine) - {"bias_ratio", "bias_dir_deg", "n_bias_dir",
                                "skill_comb", "beats_comb"}
    import io
    import contextlib
    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon):
        J._pour_la_base(_SbFactice(), "model_score_zone", [dict(fine)])
    dit = tampon.getvalue()
    check("⛔ colonnes du L9 absentes en base → le journal nomme "
          "step57, jamais step40",
          "supabase_step57_lot_l9_compagnons.sql" in dit
          and "step40" not in dit, True, )


def test_light_bascules_resume():
    print("── S13.0 : le résumé bascules fusionne montées et chutes ──")
    ev = [
        {"zone_id": "b1:valley", "agg_level": "basin_landform",
         "model": "icon_d2", "lead_h": 6, "event_type": "onset",
         "threshold_kmh": 12, "hits": 5, "misses": 2, "false_alarms": 1,
         "n": 7, "pod": 0.714, "far": 0.167, "csi": None,
         "frequency_bias": None, "timing_err_med_min": 12,
         "timing_iqr_min": 8},
        {"zone_id": "b1:valley", "agg_level": "basin_landform",
         "model": "icon_d2", "lead_h": 6, "event_type": "drop",
         "threshold_kmh": 12, "hits": 0, "misses": 4, "false_alarms": 0,
         "n": 4, "pod": 0.0, "far": None, "csi": None,
         "frequency_bias": None, "timing_err_med_min": None,
         "timing_iqr_min": None},
        # famille hors périmètre (même que `BasculeColumn.tsx` au S4) :
        # ne doit jamais entrer dans le résumé.
        {"zone_id": "b1:valley", "agg_level": "basin_landform",
         "model": "icon_d2", "lead_h": 6, "event_type": "ramp",
         "threshold_kmh": 20, "hits": 1, "misses": 0, "false_alarms": 0,
         "n": 1, "pod": 1.0, "far": None, "csi": None,
         "frequency_bias": None, "timing_err_med_min": None,
         "timing_iqr_min": None},
    ]
    rows = J.light_bascule_rows(ev)
    check("une seule ligne par zone×modèle×lead, montées ET chutes ensemble",
          len(rows), 1)
    r = rows[0]
    check("… POD montée", r["pod_onset"], 0.714)
    check("… POD chute", r["pod_drop"], 0.0)
    check("… far chute nul ⟺ 0 hit + 0 fausse alerte → « jamais annoncée »",
          r["far_drop_etat"], "jamais_annoncee")
    check("… far montée (0,167, une vraie question posée) n'est PAS "
          "« jamais annoncée »", r["far_onset_etat"], None)
    check("`ramp` n'entre pas dans le résumé", "pod_ramp" in r, False)


def test_manches_demarre_au_deploiement_et_est_idempotent():
    print("── S13.0 : le compteur de « manches » ──")
    tmp = pathlib.Path(tempfile.mkdtemp())
    j1 = [
        {"zone_id": "b1:valley", "lead_h": 6, "model": "icon_d2",
         "window_kind": "rolling15", "rank": 1, "rank_reason": "ok"},
        {"zone_id": "b1:valley", "lead_h": 6, "model": "gfs_global",
         "window_kind": "rolling15", "rank": 2, "rank_reason": "ok"},
        # une ligne régime au rang 1/ok : ne doit JAMAIS compter — seul
        # `rolling15` alimente le compteur (prompt S13.0).
        {"zone_id": "b1:valley", "lead_h": 6, "model": "icon_d2",
         "window_kind": "regime", "rank": 1, "rank_reason": "ok"},
    ]
    etat1 = J.update_rounds(tmp, DAY, j1)
    check("1ʳᵉ nuit : le compteur de nuits démarre à 1", etat1["nights"], 1)
    check("… `since` porte la date de CE premier run", etat1["since"],
          DAY.strftime("%Y-%m-%d"))
    check("… seul le rang 1/ok de `rolling15` gagne une manche",
          etat1["wins"], {"b1:valley\x1f6\x1ficon_d2": 1})

    # Idempotence : rejouer la même journée ne fait rien avancer — même
    # règle que le reste du job (cf. l'en-tête de `score.py`).
    etat1_bis = J.update_rounds(tmp, DAY, j1)
    check("rejouer la même journée n'avance ni les nuits ni les manches",
          (etat1_bis["nights"], etat1_bis["wins"]),
          (1, {"b1:valley\x1f6\x1ficon_d2": 1}))

    # `--dry-run` ne doit RIEN écrire sur le disque.
    etat_dry = J.update_rounds(tmp, DAY + timedelta(days=1), j1,
                               dry_run=True)
    check("`--dry-run` lit l'état mais ne l'avance pas", etat_dry["nights"], 1)
    etat_apres_dry = J.update_rounds(tmp, DAY, j1)
    check("… et n'a rien persisté : rejouer J1 reste à 1 nuit",
          etat_apres_dry["nights"], 1)

    # Le lendemain, un autre modèle gagne : les compteurs s'ADDITIONNENT,
    # ils ne se remplacent pas.
    j2 = [
        {"zone_id": "b1:valley", "lead_h": 6, "model": "icon_d2",
         "window_kind": "rolling15", "rank": 1, "rank_reason": "ok"},
        {"zone_id": "b1:valley", "lead_h": 6, "model": "gfs_global",
         "window_kind": "rolling15", "rank": None, "rank_reason": "tied"},
    ]
    etat2 = J.update_rounds(tmp, DAY + timedelta(days=1), j2)
    check("2ᵉ nuit : le compteur de nuits avance à 2", etat2["nights"], 2)
    check("… icon_d2 gagne une deuxième manche : le total est 2",
          etat2["wins"]["b1:valley\x1f6\x1ficon_d2"], 2)
    check("… gfs_global, `tied`, ne gagne toujours rien",
          "b1:valley\x1f6\x1fgfs_global" in etat2["wins"], False)

    check("`rounds_rows` rend zone_id/lead_h/model/wins",
          J.rounds_rows(etat2),
          [{"zone_id": "b1:valley", "lead_h": 6, "model": "icon_d2",
            "wins": 2}])


def test_manches_pas_de_rejeu_historique_sous_min_block_days():
    """Preuve, pas affirmation : sur UNE seule journée du passé, le test
    apparié ne peut jamais rendre `ok` — c'est ce qui a fait renoncer
    S13.0 au rejeu historique plutôt qu'à un compteur qui démarre au
    déploiement (cf. `update_rounds`, en-tête)."""
    print("── S13.0 : un seul jour ne peut jamais trancher — vérifié, "
          "pas supposé ──")
    check("`inference.MIN_BLOCK_DAYS` exige au moins 3 blocs de journées "
          "pour que le test apparié tranche", J.INF.MIN_BLOCK_DAYS >= 3, True)
    zone_of = {f"pioupiou:{i}": {"zone_id": "b1:valley", "landform": "valley",
                                 "basin_id": "b1", "massif_id": "alpes-nord",
                                 "basin_uncertain": False}
               for i in range(830, 836)}
    un_seul_jour = []
    d = DAY.strftime("%Y-%m-%d")
    for i in range(830, 836):
        for model, err in (("icon_d2", 4.0), ("gfs_global", 9.0)):
            un_seul_jour.append({
                "day": d, "source": "pioupiou", "station_id": str(i),
                "model": model, "lead_h": 24, "regime": "fluxN",
                "n_hours": 12, "err_vec_med": err,
                "mse_model": err * err, "mse_persist": 100.0})
    rows = J.rolling_scores(un_seul_jour, zone_of, DAY)
    fine = [r for r in rows if r["zone_id"] == "b1:valley"]
    check("un seul jour de données, même avec un écart net (4 contre "
          "9 km/h) → JAMAIS `ok`",
          all(r["rank_reason"] != "ok" for r in fine), True)


# ══════════════════════════════════════════════════════════════════
#  LOT LR (01/09/2026) — un rejeu de vieille journée ne republie pas
#  le classement du jour. Trouvé par l'oracle du lot L12.
# ══════════════════════════════════════════════════════════════════

def test_lr_le_rejeu_ancien_ne_republie_pas_le_classement():
    """`doit_republier` : hier oui, avant-hier non, et la frontière est
    CALENDAIRE."""
    U = timezone.utc
    nuit = datetime(2026, 9, 1, 3, 56, tzinfo=U)      # l'heure du timer
    hier = datetime(2026, 8, 31, tzinfo=U)
    check("LR  la nuit normale publie (J-1 note a 03:56)",
          J.doit_republier(hier, nuit), True)
    # ⭐ LA FRONTIÈRE EST CALENDAIRE, PAS À 24 h — et c'est le piège de
    # ce garde-fou. À 03:56, la journée notée a 27 h et 56 min : un test
    # écrit `as_of - day < timedelta(days=1)` refuserait de publier
    # CHAQUE NUIT, et personne ne verrait pourquoi le classement a cessé
    # de bouger.
    check("LR  ⭐ 27 h d'ecart a 03:56 : c'est la DATE qui compte",
          (nuit - hier) > timedelta(days=1)
          and J.doit_republier(hier, nuit), True)
    check("LR  ⭐ et a 23:59 le meme jour, toujours oui",
          J.doit_republier(hier, datetime(2026, 9, 1, 23, 59, tzinfo=U)),
          True)
    check("LR  la journee du jour meme publie aussi",
          J.doit_republier(datetime(2026, 9, 1, tzinfo=U), nuit), True)
    check("LR  ⛔ avant-hier ne publie PAS",
          J.doit_republier(datetime(2026, 8, 30, tzinfo=U), nuit), False)
    check("LR  ⛔ le trou du 13/08 rejoue le 01/09 ne publie PAS "
          "(25 j sous l'etiquette rolling15, 290 podiums qui changent)",
          J.doit_republier(datetime(2026, 8, 13, tzinfo=U), nuit), False)
    check("LR  `--publier-quand-meme` rouvre la porte, et lui seul",
          J.doit_republier(datetime(2026, 8, 13, tzinfo=U), nuit, True),
          True)
    # ⛔ Le drapeau doit EXISTER : un garde-fou sans porte de sortie se
    # contourne en éditant le code, ce qui ne laisse aucune trace.
    # ⚠️ ON CHERCHE LE JETON EXACT, PAS LA SOUS-CHAINE. Cherchez
    # `"--publier-quand-meme" in src` et un drapeau renomme
    # `--publier-quand-meme-x` passe le test : la sous-chaine y est
    # toujours. La mutation nº 6 a SURVECU a cette version-la, et c'est
    # elle qui a fait ecrire ces deux lignes.
    src = (pathlib.Path(os.path.dirname(os.path.abspath(__file__)))
           / "score.py").read_text(encoding="utf-8")
    check("LR  le drapeau de sortie est DECLARE tel quel",
          'ap.add_argument("--publier-quand-meme",' in src, True)
    check("LR  ⭐ et il est LU : un drapeau declare et jamais lu est un "
          "garde-fou sans porte, avec l'air d'en avoir une",
          "args.publier_quand_meme" in src, True)


def _rep_entetes(entetes: dict):
    """Une réponse HTTP factice qui ne porte QUE des en-têtes (comme un HEAD)."""
    import io

    class _Rep(io.BytesIO):
        headers = entetes

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    return _Rep(b"")


def test_l13_la_purge_dit_desormais_le_corps_de_son_erreur():
    """⛔ LA DETTE Nº 1 DU LOT L13, ET ELLE A COÛTÉ CINQ JOURS.

    `Supabase.delete` n'imprimait que « HTTP {code} ». La purge de
    `model_character` a rendu 500 les nuits des 26, 27 et 29/08 : le
    journal du VPS en garde trois lignes, aucune ne dit POURQUOI, et
    l'audit a dû écrire « `57014` — hypothèse forte » faute de pouvoir
    trancher. `_page` lit ce corps depuis le 25/08, `insert` depuis le
    28/08 : `delete` était le dernier endroit muet de la classe.

    ⚠️ Et elle doit CONTINUER : la purge est la toute dernière étape du
    run. La faire lever perdrait un run entièrement écrit, pour du
    ménage qui ne concerne aucune ligne.
    """
    print("── L13 : la purge dit le corps de son erreur (01/09) ──")
    import io
    import urllib.error as E
    import urllib.request as U

    corps = json.dumps({
        "code": "57014",
        "message": "canceling statement due to statement timeout",
        "hint": None,
        "details": "DELETE model_character",
    }).encode("utf-8")

    def faux_500(req, timeout=None):
        raise E.HTTPError(req.full_url, 500, "Internal Server Error", {},
                          io.BytesIO(corps))

    sb = _sb_de_banc()
    tampon = io.StringIO()
    vrai, U.urlopen = U.urlopen, faux_500
    try:
        with contextlib.redirect_stderr(tampon):
            rendu = sb.delete("model_character", "?last_day=lt.2026-03-05")
    finally:
        U.urlopen = vrai
    dit = tampon.getvalue()

    check("L13 le journal nomme toujours la table et le code HTTP",
          "model_character" in dit and "HTTP 500" in dit, True)
    check("L13 ⭐ … et il nomme MAINTENANT le code PostgREST — c'est ce "
          "qui manquait aux trois nuits de 500", "57014" in dit, True)
    check("L13 ⭐ … et le message, en clair",
          "statement timeout" in dit, True)
    check("L13 ⛔ et la purge NE LÈVE PAS : elle est la dernière étape "
          "du run, la faire échouer perdrait tout ce qui est écrit",
          rendu, None)


def test_l13_le_compte_dit_zero_ou_je_ne_sais_pas():
    """`Supabase.compte` : `*/0` c'est zéro, un refus c'est `None`.

    ⛔ LA CONFUSION QU'ON REFUSE. Rendre `0` quand le serveur n'a pas
    répondu ferait sauter la purge EN SILENCE — exactement le défaut
    qu'on répare. Les deux valeurs doivent être distinguables par
    l'appelant, donc distinguées ici.
    """
    print("── L13 : compter avant de supprimer ──")
    import io
    import urllib.error as E
    import urllib.request as U

    sb = _sb_de_banc()
    vrai = U.urlopen
    try:
        U.urlopen = lambda req, timeout=None: _rep_entetes(
            {"content-range": "*/0"})
        check("L13 `*/0` se lit ZÉRO (et pas `None`)",
              sb.compte("model_character", "?last_day=lt.2026-03-05"), 0)

        U.urlopen = lambda req, timeout=None: _rep_entetes(
            {"content-range": "0-0/1223107"})
        check("L13 un total se lit tel quel (1 223 107, mesuré le 01/09)",
              sb.compte("model_character"), 1223107)

        U.urlopen = lambda req, timeout=None: _rep_entetes(
            {"content-range": "*/*"})
        check("L13 ⛔ un total INCONNU (`*/*`) rend `None`, pas 0",
              sb.compte("model_character"), None)

        def refus(req, timeout=None):
            raise E.HTTPError(req.full_url, 500, "boom", {},
                              io.BytesIO(b'{"code":"57014"}'))

        U.urlopen = refus
        tampon = io.StringIO()
        with contextlib.redirect_stderr(tampon):
            rendu = sb.compte("model_character")
        check("L13 ⛔ un serveur qui refuse rend `None`, jamais 0", rendu,
              None)
        check("L13 … et il le DIT, corps compris",
              "57014" in tampon.getvalue(), True)
    finally:
        U.urlopen = vrai

    check("L13 en dry-run, `compte` dit « je ne sais pas »",
          J.Supabase(dry_run=True).compte("model_character"), None)


def test_l13_on_ne_lance_pas_un_delete_qui_ne_supprime_rien():
    """⭐ LE GESTE DU LOT : compter, puis ne supprimer que s'il y a de quoi.

    Mesuré le 01/09 : le filtre `last_day=lt.J-180` concerne ZÉRO ligne
    et le restera jusqu'en mars 2027 (25 jours de table pour 180 de
    rétention). Le DELETE partait quand même, toutes les nuits, contre
    1 223 107 lignes sans index utilisable — et rendait 500 trois nuits
    sur six.

    ⚠️ LES TROIS BRANCHES COMPTENT, pas seulement la première. « Je ne
    sais pas » (`None`) doit LANCER la purge : une purge sautée en
    silence serait un défaut pire que celui qu'on répare, et il ne se
    verrait qu'au bout de six mois de table qui gonfle.
    """
    print("── L13 : le DELETE ne part plus pour rien ──")
    U = timezone.utc
    today = datetime(2026, 9, 1, 3, 59, tzinfo=U)

    class _Sb:
        def __init__(self, n):
            self.n = n
            self.comptes, self.deletes = [], []

        def compte(self, table, query=""):
            self.comptes.append((table, query))
            return self.n

        def delete(self, table, query):
            self.deletes.append((table, query))

    vide = _Sb(0)
    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon):
        J._purge_caractere(vide, today)
    check("L13 ⭐ 0 ligne à jeter ⇒ AUCUN DELETE n'est lancé",
          vide.deletes, [])
    check("L13 … mais le compte, lui, a bien eu lieu (on MESURE, on ne "
          "suppose pas)", len(vide.comptes), 1)
    check("L13 … et le filtre compté est celui de la rétention, J-180",
          vide.comptes[0], ("model_character", "?last_day=lt.2026-03-05"))
    check("L13 … et le journal dit ce qui n'a pas été fait, et pourquoi",
          "DELETE non lancé" in tampon.getvalue(), True)

    plein = _Sb(1234)
    with contextlib.redirect_stdout(io.StringIO()):
        J._purge_caractere(plein, today)
    check("L13 ⭐ des lignes à jeter ⇒ le DELETE part, au même filtre",
          plein.deletes, [("model_character", "?last_day=lt.2026-03-05")])

    muet = _Sb(None)
    with contextlib.redirect_stdout(io.StringIO()):
        J._purge_caractere(muet, today)
    check("L13 ⛔ compte INDISPONIBLE ⇒ la purge part QUAND MÊME "
          "(« je ne sais pas » n'est pas « zéro »)",
          muet.deletes, [("model_character", "?last_day=lt.2026-03-05")])


def test_l13_rank_corr_davant_step52_dit_a_ecrire_jamais_step40():
    """⛔ LE BANC QUI DIT TOUT SEUL SI LA DETTE Nº 2 EST PAYÉE.

    L'audit §2.5 : `rank_corr` manquait en base, le code a imprimé
    « Lancer supabase_step40_lot_g.sql », et ce fichier était passé
    depuis le 07/08 — il ne pouvait rien ajouter. La bonne réponse
    était « aucun fichier ne porte cette colonne : migration À
    ÉCRIRE », et c'est ce qui a fini par s'écrire, en step52.

    Ce banc rejoue CET ÉTAT-LÀ du schéma (la table de correspondance
    sans le step52) et exige les deux moitiés de la phrase : « À
    ÉCRIRE » présent, `step40` ABSENT. La seconde est la plus
    importante : un message qui dit « à écrire » ET nomme un fichier
    envoie quand même Yann le rejouer.
    """
    print("── L13 : le .sql ne se déduit plus, il se lit ──")

    # L'état du 25/08 : le step52 n'existe pas encore.
    avant_52 = {
        "model_score_zone": {
            c: f for c, f in J._SQL_PAR_COLONNE["model_score_zone"].items()
            if "step52" not in f
        }
    }
    dit = J._sql_a_jouer("model_score_zone", ["rank_corr"], avant_52)
    check("L13 ⭐ `rank_corr` d'AVANT step52 : « migration À ÉCRIRE »",
          "À ÉCRIRE" in dit, True)
    check("L13 ⛔ … et le message ne nomme AUCUN step existant — c'est "
          "la faute exacte de l'audit §2.5",
          "step40" not in dit and "supabase_step" not in dit, True)

    dit_ok = J._sql_a_jouer("model_score_zone", ["rank_corr",
                                                "rank_reason_corr"])
    check("L13 aujourd'hui, la même colonne nomme le step52",
          "supabase_step52_rank_corr.sql" in dit_ok, True)
    check("L13 … et lui seul", "step40" not in dit_ok, True)

    # ⚠️ La cascade d'avant s'arrêtait au PREMIER set qui mordait : deux
    # migrations en attente, une seule nommée, et la nuit d'après
    # rejouait le même diagnostic incomplet.
    deux = J._sql_a_jouer("model_verif_daily", ["mse_clim", "mse_comb"])
    check("L13 ⭐ deux fichiers en attente ⇒ les DEUX sont nommés",
          "supabase_step40_lot_g.sql" in deux
          and "supabase_step57_lot_l9_compagnons.sql" in deux, True)
    check("L13 … et dans l'ordre des steps",
          deux.index("step40") < deux.index("step57"), True)

    melange = J._sql_a_jouer("model_score_zone", ["n_comparable",
                                                 "colonne_de_demain"])
    check("L13 ⭐ connue + inconnue : le step54 est nommé pour l'une, "
          "« À ÉCRIRE » pour l'autre",
          "supabase_step54_lot_l3_fdr.sql" in melange
          and "À ÉCRIRE" in melange, True)
    check("L13 ⛔ … et la colonne à écrire est NOMMÉE, pas noyée",
          "colonne_de_demain" in melange.split("À ÉCRIRE")[0][-120:]
          or "colonne_de_demain" in melange, True)

    # ── et le chemin réel, celui qui imprime ──────────────────────────
    class _SbSans52:
        def columns(self, table):
            return {"as_of", "zone_id", "model", "lead_h", "rank"}

    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon):
        sortie = J._pour_la_base(_SbSans52(), "model_score_zone",
                                 [{"as_of": "2026-09-01", "zone_id": "b1",
                                   "model": "arome", "lead_h": 6, "rank": 1,
                                   "n_comparable": 12}])
    journal = tampon.getvalue()
    check("L13 bout en bout : la colonne absente ne part pas en base",
          "n_comparable" in sortie[0], False)
    check("L13 bout en bout : le journal nomme le step54, pas le step40",
          "supabase_step54_lot_l3_fdr.sql" in journal
          and "step40" not in journal, True)


def test_l13_la_table_colonne_sql_colle_aux_fichiers_reels():
    """La table dit-elle la VÉRITÉ des `.sql` du dépôt ?

    ⚠️ CE CONTRÔLE NE TOURNE QUE LÀ OÙ LES `.sql` SONT — c'est-à-dire
    sur le Mac. Le VPS ne reçoit que `*.py` (`~/balise-watch/web/` n'a
    que `public/`), donc le banc distant l'annonce sauté au lieu de le
    croire vert : un contrôle qui ne trouve pas sa matière doit le
    DIRE, sinon il se compte comme une preuve (leçon du lot LD, où un
    vérificateur portait le même filtre que le geste qu'il vérifiait).
    """
    print("── L13 : la table colonne→.sql relue depuis les fichiers ──")
    import re                                              # noqa: PLC0415
    web = (pathlib.Path(os.path.dirname(os.path.abspath(__file__)))
           / ".." / ".." / "web").resolve()
    fichiers = sorted(web.glob("supabase_step*.sql")) if web.is_dir() else []
    if not fichiers:
        print(f"     ⓘ contrôle SAUTÉ : aucun .sql sous {web} "
              f"(machine de déploiement — les .sql restent au dépôt)")
        return

    reel: dict[str, dict[str, str]] = {}
    for f in fichiers:
        courante = None
        for ligne in f.read_text(encoding="utf-8").splitlines():
            ligne = ligne.split("--")[0]
            m = re.search(r"alter\s+table\s+(?:if\s+exists\s+)?"
                          r"(?:public\.)?(\w+)", ligne, re.I)
            if m:
                courante = m.group(1)
            for m2 in re.finditer(r"add\s+column\s+(?:if\s+not\s+exists\s+)?"
                                  r"(\w+)", ligne, re.I):
                if courante in J._SQL_PAR_COLONNE:
                    reel.setdefault(courante, {})[m2.group(1)] = f.name

    for table, colonnes in J._SQL_PAR_COLONNE.items():
        check(f"L13 {table} : la table du code == les `add column` réels",
              colonnes, reel.get(table, {}))
    check("L13 ⭐ et les trois tables que `_pour_la_base` sert y sont "
          "toutes — une table absente rendrait « À ÉCRIRE » pour TOUTES "
          "ses colonnes, ce qui est bruyant mais faux",
          sorted(J._SQL_PAR_COLONNE),
          ["model_score_zone", "model_verif_daily",
           "model_verif_daily_pres"])


def main() -> int:
    for fn in (test_chaine_de_repli, test_lignes_de_zone,
               test_agregat_quotidien, test_accumulateurs,
               # ── lot S15 : l'accumulation du caractère passe en SQL ──
               test_s15_contrat_de_la_rpc,
               test_s15_garde_du_lot_rpc,
               test_s15_compte_ce_qui_est_applique,
               test_scores_de_zone, test_score_par_regime,
               test_rétrécissement_vers_le_parent,
               test_rejeu_darchive,
               test_fenetre_de_maintien_adaptative,
               test_stabilite_des_rangs,
               test_familles_publiees, test_lecture_paginee,
               # ── 25/08 : la panne du run de 05:57 (délai 8 s, `57014`) ──
               test_lecture_par_cle_exacte,
               test_lecture_par_cle_valeur_plus_grosse_quune_page,
               test_lecture_reprise_sur_5xx,
               test_page_ne_depasse_pas_le_plafond_serveur,
               test_plancher_de_skill,
               test_pression_appariement, test_pression_refus,
               test_pression_appariement_stable_entre_echeances,
               # ── lot S0.6 ──
               test_partition_parties_manquantes,
               test_rang_sur_journee_incomplete,
               test_les_deux_cles_fcst_sont_la_meme_chaine,
               # ── lot S0.11 : le groupe réduit sur les candidates ──
               test_flux_reduit_lu_et_pas_compte_comme_partie,
               test_metar_entre_dans_la_notation_du_vent,
               # ── lot S2 ──
               test_s2_correction_du_biais_de_site,
               test_s2_estimateur_sans_selection,
               test_s2_memoire_du_biais,
               test_s2_gardes_fous_et_temoin,
               test_s2_colonnes_de_zone,
               # ── lot S3 : le scoring doit savoir échouer ──
               test_s3_self_test_injection,
               # ── 25/08 : le classement sur la colonne corrigée ──
               test_rank_corr_le_meme_test_sur_la_colonne_corrigee,
               # ── lot L2 (27/08) : un seul AROME au classement ──
               test_l2_un_seul_arome_au_classement,
               test_l2_duplicate_chain_sur_le_classement_corrige,
               test_l2_apply_rank_transmet_lexclu_au_corrige,
               # ── lot L18 (30/08) : un seul AGRUME au classement ──
               test_l18_un_seul_agrume_au_classement,
               test_l18_agrume_seul_concourt_normalement,
               test_l18_les_deux_exclusions_coexistent,
               test_l18_le_temoin_voyage_jusquau_corrige,
               test_l18_apply_rank_corr_accepte_encore_une_chaine,
               test_l18_le_rang_perime_du_temoin_est_efface,
               # ── lot L10 (30/08) : la classe courte ──
               test_l10_la_ligne_porte_son_echeance,
               test_l10_notees_jamais_classees,
               test_l10_les_evenements_ignorent_la_classe_courte,
               test_l10_on_ne_classe_pas_une_case_vide,
               test_l10_le_lead_refuse_ecarte_les_lignes_pas_la_nuit,
               # ── lot L17 (27/08) : les doublons d'inscription ──
               test_l17_doublon_ecarte_du_classement,
               test_l17_doublon_ecarte_des_accumulateurs,
               # ── lot L3 (27/08) : multiplicité + gap apparié ──
               test_l3_gap_apparie_bout_en_bout,
               test_l3_fdr_tue_la_limite_et_garde_la_franche,
               test_l3_fdr_ne_touche_pas_lecarte_ni_le_corrige,
               test_l3_la_p_valeur_arrive_vraiment_du_classement,
               # ── lot L9a (28/08) : le compagnon WMO du score ──
               test_l9a_compagnon_wmo_biais_de_vitesse_et_de_cap,
               # ── lot L9b (28/08) : les six sommes de Murphy ──
               test_l9b_les_moments_de_murphy_voyagent_sans_toucher_la_base,
               # ── lot L9c (28/08) : la référence combinée ──
               test_l9c_reference_combinee_bout_en_bout,
               # ── lot S13.0 : le fichier léger + le résumé des manches ──
               test_light_scores_sous_ensemble_exact,
               test_light_scores_bout_en_bout_ne_recalcule_rien,
               test_light_bascules_resume,
               test_manches_demarre_au_deploiement_et_est_idempotent,
               test_manches_pas_de_rejeu_historique_sous_min_block_days,
               # ── 28/08 : le corps d'erreur qui cachait la cause ──
               test_detail_erreur_le_nom_de_la_contrainte_survit,
               # ── 28/08 : les deux raisons de rang ──
               test_repli_rang_corr_la_seconde_contrainte_ne_tue_plus_la_nuit,
               test_repli_rang_les_deux_ensembles_admis_disent_le_schema_reel,
               # ── 28/08 : la mémoire du run, après l'OOM de la nuit ──
               test_memoire_le_jalon_dit_les_mo_et_crie_au_dessus_du_seuil,
               test_memoire_rss_lit_bien_vmrss_et_le_rend_en_mo,
               test_memoire_rss_suit_une_allocation_reelle,
               test_memoire_les_blocs_morts_sont_relaches_avant_le_chemin_regime,
               # ── lot LR (01/09) : le rejeu qui republiait le jour ──
               test_lr_le_rejeu_ancien_ne_republie_pas_le_classement,
               # ── lot L13 (01/09) : les deux dettes ops de l'audit ──
               test_l13_la_purge_dit_desormais_le_corps_de_son_erreur,
               test_l13_le_compte_dit_zero_ou_je_ne_sais_pas,
               test_l13_on_ne_lance_pas_un_delete_qui_ne_supprime_rien,
               test_l13_rank_corr_davant_step52_dit_a_ecrire_jamais_step40,
               test_l13_la_table_colonne_sql_colle_aux_fichiers_reels):
        fn()
    print(f"\n{OK} assertions vertes, {KO} rouges.")
    return 1 if KO else 0


if __name__ == "__main__":
    sys.exit(main())
