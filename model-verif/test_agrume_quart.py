# ══════════════════════════════════════════════════════════════════════
#  model-verif/test_agrume_quart.py — le banc de la CLASSE AU QUART
#                                     D'HEURE      (Lot L11, 31/08/2026)
#
#  Sans réseau, sans clé, sans base.
#
#      python3 test_agrume_quart.py
#
#  ═══ CE QUE CHACUN TIENT, ET CE QUE ÇA COÛTERAIT DE NE PAS L'AVOIR ═══
#
#  · indépendance  → ±20 min gardée sur un    → ⛔⛔ chaque relevé compté
#                    pas de 15 min               dans TROIS points ; les
#                                                `n_obs` publiés sont faux
#                                                et rien n'a l'air anormal
#  · non-régression→ la demi-fenêtre de       → toutes les séries
#                    l'heure ronde bouge        existantes changent de
#                                               population en silence
#  · une seule     → un quart servi dans une  → la faute du L9(c) refaite :
#    population      série et pas dans une      trois erreurs comparées sur
#                    autre                      trois populations d'heures
#  · aucune ronde  → une heure ronde notée    → le même instant noté deux
#                    dans les deux classes      fois : `m` du BH-FDR et
#                                               `n` annoncés gonflés
#  · interpolation → interpolation sur        → 350° et 010° donnent 180°,
#                    l'angle plutôt qu'u/v      le vent à l'opposé
#  · cisaillement  → Δ(20 m) servi tel quel   → correction calibrée pour un
#                    au 10 m                    vent 30 % plus fort
#  · PI horaire    → les quarts fabriqués     → une classe « au quart
#                    des deux côtés             d'heure » sans un seul
#                                               chiffre natif dedans
#  · plancher      → 6 sur 15 comme sur 6     → une balise notée sur 6
#                                               points parmi 15 dans le
#                                               même tableau qu'une notée
#                                               sur 15
#  · étiquettes    → −1/−2 réutilisées        → deux PAS DE TEMPS sous une
#                                               seule étiquette
# ══════════════════════════════════════════════════════════════════════
from __future__ import annotations

import math
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np                                          # noqa: E402

import agrume_quart as Q                                    # noqa: E402
import score as J                                           # noqa: E402
import scoring as S                                         # noqa: E402
from agrume_fcst import decorer_vent                        # noqa: E402
from composite import facteur_cisaillement                  # noqa: E402
from test_agrume_pi_fcst import (BALISES, MINUTES,          # noqa: E402
                                 archive_a, archive_pi)

ECHECS: list[str] = []
UTC = timezone.utc
JOUR = datetime(2026, 8, 12, tzinfo=UTC)     # le RUN des fabriques est ce jour
T = JOUR.replace(hour=6, minute=50)


def verifie(condition, message):
    if condition:
        print(f"  ✅ {message}")
    else:
        print(f"  ❌ {message}")
        ECHECS.append(message)


def muet(*_a, **_k):
    pass


# ══════════════════════════════════════════════════════════════════
#  1. LE PÉRIMÈTRE — quinze quarts, et AUCUNE heure ronde
# ══════════════════════════════════════════════════════════════════

def test_quinze_quarts_aucune_ronde():
    for h, m in ((6, 50), (12, 50), (6, 0), (6, 30)):
        q = Q.quarts_cibles(JOUR.replace(hour=h, minute=m))
        verifie(len(q) == 15,
                f"T = {h:02d}:{m:02d} Z → {len(q)} quarts (attendu 15)")
        verifie(all(x.minute in (15, 30, 45) for x in q),
                "⛔ aucune heure ronde : elles appartiennent à la classe "
                "horaire, et un instant noté deux fois gonflerait le `m` "
                "du BH-FDR sur les mêmes observations")
    q = Q.quarts_cibles(T)
    verifie((q[0].hour, q[0].minute) == (7, 15)
            and (q[-1].hour, q[-1].minute) == (11, 45),
            f"la plage va de {q[0]:%H:%M} à {q[-1]:%H:%M} Z")
    # ⛔ Le périmètre est DÉRIVÉ de celui de la classe horaire : les deux
    # doivent bouger ensemble, ou l'une notera un intervalle que l'autre
    # ne note pas.
    from agrume_court import heures_cibles
    rondes = heures_cibles(T)
    verifie(rondes[0] < q[0] and q[-1] < rondes[-1],
            "les quarts sont STRICTEMENT à l'intérieur de la plage des "
            "heures rondes — la plage n'est pas écrite deux fois")


# ══════════════════════════════════════════════════════════════════
#  2. ⛔⛔ L'INDÉPENDANCE — l'invariant 2 × demi < pas
# ══════════════════════════════════════════════════════════════════

def test_invariant_d_independance():
    for pas_s, demi_ms in S.DEMI_FENETRE_MS.items():
        verifie(2 * demi_ms < pas_s * 1000,
                f"pas {pas_s // 60}′ / demi ±{demi_ms // 60000}′ : "
                f"2×demi < pas, fenêtres disjointes")
    verifie(S.demi_fenetre(3600) == S.OBS_HALF_WINDOW_MS,
            "⛔ NON-RÉGRESSION : l'heure ronde garde ±20 min au millième "
            "près — toute autre valeur changerait la population de TOUTES "
            "les séries existantes en silence")
    verifie(S.demi_fenetre(900) == 7 * 60 * 1000,
            "le pas de 15 min prend ±7 min (mesuré : 93,0 % des "
            "balise-jour-T à 14 quarts sur 15, contre 89,0 % à ±5 min)")
    # ⛔ LE BANC QUI ÉCHOUE SI ON MET ±20 MIN SUR LE QUART D'HEURE. Sans
    # lui, la faute est invisible : les erreurs ne bougent presque pas,
    # seuls les `n` gonflent — et personne ne relit un `n`.
    verifie(2 * S.demi_fenetre(900) < Q.PAS_QUART_S * 1000,
            "⛔⛔ ±20 min sur un pas de 15 min compterait chaque relevé "
            "dans TROIS points : le test apparié perdrait l'indépendance "
            "qui le rend licite")
    # Un pas inconnu est SERVI, mais jamais au-delà de l'invariant.
    for pas in (300, 1800, 7200):
        verifie(2 * S.demi_fenetre(pas) < pas * 1000,
                f"pas inconnu {pas} s : la demi-fenêtre rendue respecte "
                f"encore l'invariant")


def test_appariement_reel_a_15_min():
    """⭐ L'INDÉPENDANCE, VÉRIFIÉE SUR DES RELEVÉS, PAS SUR UNE INÉGALITÉ.

    Deux relevés espacés de 15 min, un par échéance : chacun doit
    compter pour UN point et un seul. Avec ±20 min, chacun compterait
    dans les deux — et `n_obs` vaudrait 2 partout.
    """
    t0 = int(datetime(2026, 8, 12, 7, 15, tzinfo=UTC).timestamp()) * 1000
    times = [t0, t0 + 900_000, t0 + 1_800_000]
    obs = [S.ObsSample(t=t, speed=10.0, dir=180.0) for t in times]
    paires = S.pair_series(times, [10.0, 10.0, 10.0], [180.0] * 3, obs,
                           S.demi_fenetre(900))
    verifie([p.n_obs for p in paires] == [1, 1, 1],
            f"±7 min : chaque relevé compte pour UN point "
            f"({[p.n_obs for p in paires]})")
    large = S.pair_series(times, [10.0, 10.0, 10.0], [180.0] * 3, obs,
                          S.OBS_HALF_WINDOW_MS)
    verifie([p.n_obs for p in large] != [1, 1, 1],
            "⛔ et le banc sait le voir : avec ±20 min les mêmes relevés "
            f"donnent {[p.n_obs for p in large]} — la faute que ce lot "
            f"existe pour ne pas commettre")


# ══════════════════════════════════════════════════════════════════
#  3. LE PLANCHER — 13 sur 15, et l'heure ronde ne bouge pas
# ══════════════════════════════════════════════════════════════════

def test_plancher_du_pas():
    verifie(J.plancher_du_pas(3600) == J.MIN_HOURS_DAILY,
            "⛔ NON-RÉGRESSION : l'heure ronde garde son plancher de 6")
    verifie(J.plancher_du_pas(900) == 13,
            "le quart d'heure exige 13 des 15 échéances (86,7 %, la "
            "transposition exacte du « 18 sur 21 » de Yann)")
    verifie(J.plancher_du_pas(1234) == J.MIN_HOURS_DAILY,
            "un pas inconnu retombe sur le plancher d'avant ce lot — "
            "laxiste et visible, plutôt que de coûter une nuit")
    verifie(J.plancher_du_pas(900) / 15 > 0.85
            and J.plancher_du_pas(3600) / 6 == 1.0,
            "⚠️ le quart d'heure reste légèrement moins exigeant que "
            "l'heure ronde (86,7 % contre 100 %) — c'est écrit, pas caché")


# ══════════════════════════════════════════════════════════════════
#  4. LA CONSTRUCTION — interpolation, cisaillement, direction
# ══════════════════════════════════════════════════════════════════

def _archives(pi_val=None, pi_minutes=None):
    """AROME LINÉAIRE en τ (donc l'interpolation y est EXACTE) et PI plat.

    ⭐ Le champ linéaire n'est pas un confort : il rend la valeur
    attendue calculable à la main à n'importe quel instant, donc le banc
    peut comparer à un NOMBRE plutôt qu'à la sortie d'une seconde
    implémentation — laquelle aurait pu se tromper de la même façon.
    """
    col, man = archive_a(base10=lambda k, s: (1.0 + 0.1 * s, 2.0 + 0.2 * s),
                         base20=lambda k, s: (3.0 + 0.3 * s, 4.0 + 0.4 * s))
    d, pim = archive_pi(pi_val or (lambda bid, m: (9.0, -9.0)),
                        minutes=pi_minutes)
    return col, man, d, pim


def test_interpolation_exacte_et_direction():
    """`w = 0` sur un champ linéaire = la valeur linéaire, au millième."""
    col, man, d, pim = _archives()
    r_a = JOUR.replace(hour=0)
    r_p = JOUR.replace(hour=6)
    rows = Q.series_du_t(col, man, d, pim, T, J.LEAD_QUART_MATIN,
                         r_a, r_p, crier=muet)
    w0 = [r for r in rows if r["model"] == J.AGRUME_QUART_W0]
    verifie(bool(w0), f"{len(w0)} lignes témoin `w = 0`")
    r = w0[0]
    # 07:15 Z sur un run de 00 Z : échéance 7,25 h.
    i = int((datetime(2026, 8, 12, 7, 15, tzinfo=UTC).timestamp()
             - r["t0"]) // Q.PAS_QUART_S)
    attendu = decorer_vent({"u": 1.0 + 0.1 * 7.25, "v": 2.0 + 0.2 * 7.25})
    verifie(abs(r["speed"][i] - attendu["vitesseKmh"]) < 1e-2,
            f"07:15 Z, w = 0 : {r['speed'][i]:.3f} km/h contre "
            f"{attendu['vitesseKmh']:.3f} attendus (interpolation exacte "
            f"sur un champ linéaire)")
    verifie(abs(r["dir"][i] - attendu["directionDeg"]) < 1e-2,
            "⛔ et la DIRECTION suit : l'interpolation se fait sur u et v, "
            "jamais sur l'angle — interpoler 350° et 010° donnerait 180°, "
            "le vent exactement à l'opposé, et rien ne lèverait")


def test_le_cisaillement_est_applique():
    """`w = 1` = base + kz·Δ, et kz vient de `composite`, pas d'ici."""
    col, man, d, pim = _archives()
    r_a, r_p = JOUR.replace(hour=0), JOUR.replace(hour=6)
    rows = Q.series_du_t(col, man, d, pim, T, J.LEAD_QUART_MATIN,
                         r_a, r_p, crier=muet)
    par = {r["model"]: r for r in rows if r["station_id"] == rows[0]["station_id"]}
    i = int((datetime(2026, 8, 12, 7, 15, tzinfo=UTC).timestamp()
             - par[J.AGRUME_QUART_W0]["t0"]) // Q.PAS_QUART_S)
    kz = facteur_cisaillement(10)
    u_b, v_b = 1.0 + 0.1 * 7.25, 2.0 + 0.2 * 7.25
    u20, v20 = 3.0 + 0.3 * 7.25, 4.0 + 0.4 * 7.25
    att = decorer_vent({"u": u_b + kz * (9.0 - u20),
                        "v": v_b + kz * (-9.0 - v20)})
    got = par[J.AGRUME_QUART_W1]["speed"][i]
    verifie(abs(got - att["vitesseKmh"]) < 5e-2,
            f"w = 1 : {got:.3f} km/h contre {att['vitesseKmh']:.3f} — "
            f"Δ(20 m) remis à l'échelle du 10 m par kz = {kz:.3f}")
    verifie(abs(kz - 1.0) > 0.05,
            "⛔ kz ≠ 1 : servir Δ(20 m) tel quel au 10 m appliquerait une "
            "correction calibrée pour un vent ~30 % plus fort")
    # ⭐ w = 0,5 est EXACTEMENT le milieu, en u/v — la seule vérification
    # qui distingue « moyenne des vents » de « moyenne des vitesses ».
    att05 = decorer_vent({"u": u_b + 0.5 * kz * (9.0 - u20),
                          "v": v_b + 0.5 * kz * (-9.0 - v20)})
    verifie(abs(par[J.AGRUME_QUART_W05]["speed"][i]
                - att05["vitesseKmh"]) < 5e-2,
            "w = 0,5 est le milieu en u/v, pas la moyenne des vitesses")


def test_w1_n_est_pas_du_pi_pur():
    """⚠️ LE BANC QUI GARDE UNE PHRASE HONNÊTE DANS L'EN-TÊTE.

    Il reste à `w = 1` le résidu `AROME₁₀ − kz·AROME₂₀`, interpolé lui
    aussi. Écrire « w = 1 = PI » serait un de ces énoncés plausibles,
    non mesurés et faux — et ce banc rougit si quelqu'un le rend vrai
    en changeant la construction sans le dire.
    """
    col, man, d, pim = _archives()
    rows = Q.series_du_t(col, man, d, pim, T, J.LEAD_QUART_MATIN,
                         JOUR.replace(hour=0), JOUR.replace(hour=6),
                         crier=muet)
    r = next(r for r in rows if r["model"] == J.AGRUME_QUART_W1)
    i = next(k for k, s in enumerate(r["speed"]) if s is not None)
    pi_seul = decorer_vent({"u": 9.0, "v": -9.0})["vitesseKmh"]
    verifie(abs(r["speed"][i] - pi_seul) > 1e-3,
            f"w = 1 ({r['speed'][i]:.3f}) n'est PAS PI seul "
            f"({pi_seul:.3f}) — le résidu interpolé existe, et l'en-tête "
            f"le dit")
    verifie(all(x["agrume_quart_base_interpolee"] is True for x in rows),
            "les TROIS sous-séries portent `base_interpolee = true` : à "
            "une échéance non ronde, aucune n'échappe à l'interpolation")


# ══════════════════════════════════════════════════════════════════
#  5. ⛔⛔ UNE SEULE POPULATION — la leçon du lot L9(c)
# ══════════════════════════════════════════════════════════════════

def test_une_seule_population():
    """Un quart sans PI est absent des TROIS séries, pas d'une seule."""
    trou = datetime(2026, 8, 12, 7, 30, tzinfo=UTC)
    m_trou = int((trou - JOUR.replace(hour=6)).total_seconds() // 60)

    def val(bid, m):
        return None if m == m_trou else (9.0, -9.0)

    col, man, d, pim = _archives(pi_val=val)
    rows = Q.series_du_t(col, man, d, pim, T, J.LEAD_QUART_MATIN,
                         JOUR.replace(hour=0), JOUR.replace(hour=6),
                         crier=muet)
    par_bal: dict[str, dict[str, dict]] = {}
    for r in rows:
        par_bal.setdefault(r["station_id"], {})[r["model"]] = r
    sid = next(iter(par_bal))
    i_trou = int((trou.timestamp() - par_bal[sid][J.AGRUME_QUART_W0]["t0"])
                 // Q.PAS_QUART_S)
    verifie(all(m["speed"][i_trou] is None for m in par_bal[sid].values()),
            "⛔ le quart sans PI est absent des TROIS sous-séries — pas "
            "servi dans le témoin et manquant dans les composites")
    comptes = {mo: sum(1 for s in r["speed"] if s is not None)
               for mo, r in par_bal[sid].items()}
    verifie(len(set(comptes.values())) == 1,
            f"⭐ les trois séries servent EXACTEMENT les mêmes points "
            f"({comptes}) — c'est ce qui rend la comparaison appariée, et "
            f"c'est la faute que le lot L9(c) a passé trois nuits à "
            f"instruire")
    verifie(all(r["agrume_quart_quarts"] == 14 for r in rows
                if r["station_id"] == sid),
            "le compte publié par la ligne dit 14 quarts sur 15, et il "
            "est le même pour les trois")


def test_pi_horaire_ne_sert_aucun_quart():
    """⛔ Si PI n'avait que des heures rondes, la classe se TAIRAIT.

    Elle ne fabriquerait pas les quarts des deux côtés : une classe « au
    quart d'heure » dont aucun chiffre n'est natif à 15 min ne mesurerait
    plus rien — elle comparerait deux interpolations du même champ.
    """
    col, man, d, pim = _archives(pi_minutes=list(range(0, 361, 60)))
    rows = Q.series_du_t(col, man, d, pim, T, J.LEAD_QUART_MATIN,
                         JOUR.replace(hour=0), JOUR.replace(hour=6),
                         crier=muet)
    verifie(rows == [],
            "PI horaire → aucune ligne, et le journal le dit "
            f"({len(rows)} lignes)")


def test_aucune_valeur_sur_une_heure_ronde():
    col, man, d, pim = _archives()
    rows = Q.series_du_t(col, man, d, pim, T, J.LEAD_QUART_MATIN,
                         JOUR.replace(hour=0), JOUR.replace(hour=6),
                         crier=muet)
    r = rows[0]
    rondes = [i for i in range(len(r["speed"]))
              if (r["t0"] + i * Q.PAS_QUART_S) % 3600 == 0]
    verifie(len(rondes) == 6,
            f"le tableau couvre 6 heures rondes ({len(rondes)}) …")
    verifie(all(r["speed"][i] is None for i in rondes),
            "… et AUCUNE ne porte de valeur : elles restent la propriété "
            "de la classe horaire")
    verifie(sum(1 for s in r["speed"] if s is not None) == 15,
            "quinze points servis, ni plus ni moins")


def test_la_ligne_declare_son_pas():
    """⛔ C'EST LA LIGNE QUI DÉCLARE SON PAS, OU PERSONNE.

    `score.daily_rows` ne connaît aucun modèle par son nom (règle du lot
    I, rappelée au L10) : il lit `step_s` pour choisir la demi-fenêtre
    ET le plancher. Une ligne qui déclarerait 3600 serait appariée à
    ±20 min sur un pas de 15 — chaque relevé compté dans trois points,
    sans qu'un seul chiffre n'ait l'air anormal.
    """
    col, man, d, pim = _archives()
    rows = Q.series_du_t(col, man, d, pim, T, J.LEAD_QUART_MATIN,
                         JOUR.replace(hour=0), JOUR.replace(hour=6),
                         crier=muet)
    verifie(all(r["step_s"] == 900 for r in rows),
            "toutes les lignes déclarent `step_s = 900`")
    verifie(S.demi_fenetre(rows[0]["step_s"]) == 7 * 60 * 1000,
            "… et ce pas mène bien à ±7 min, pas à ±20")
    verifie(J.plancher_du_pas(rows[0]["step_s"]) == 13,
            "… et au plancher de 13 sur 15, pas à celui de l'heure ronde")
    verifie(all(r["lead_h"] in J.LEADS_QUARTS for r in rows),
            "et son échéance, faute de quoi la classe entière "
            "disparaîtrait dans le « +6 h »")


# ══════════════════════════════════════════════════════════════════
#  6. LES ÉTIQUETTES ET LE CLASSEMENT
# ══════════════════════════════════════════════════════════════════

def test_etiquettes_distinctes():
    verifie(set(J.LEADS_QUARTS).isdisjoint(J.LEADS_COURTS),
            "⛔ les étiquettes du quart d'heure sont DISTINCTES de celles "
            "de la classe courte : deux pas de temps sous une seule "
            "étiquette, c'est la variante (b) refusée en Q2")
    verifie(set(J.LEADS_QUARTS).isdisjoint(set(J.LEAD_BY_OFFSET.values())),
            "… et des trois classes d'horizon")
    verifie(all(l < 0 for l in J.LEADS_QUARTS),
            "négatives : un entier positif s'alignerait à côté de 6, 24 "
            "et 48 comme s'il était de la même famille")
    verifie(set(J.LEADS_INSTANT_T) == set(J.LEADS_COURTS + J.LEADS_QUARTS),
            "et les trois lieux qui doivent les écarter lisent UNE seule "
            "liste")


def test_aucune_des_trois_ne_se_classe():
    rows = [{"model": m, "lead_h": J.LEAD_QUART_MATIN}
            for m in J.MODELES_QUARTS]
    exclus = J._exclus_du_rang(rows)
    for m in J.MODELES_QUARTS:
        verifie(exclus.get(m) == J.RANK_REASON_SERIE_EN_ESSAI,
                f"{m} : noté, jamais classé ({exclus.get(m)})")
    verifie(J.AGRUME_QUART_W0 in exclus,
            "⛔ le TÉMOIN surtout : classer de l'AROME fabriqué contre le "
            "produit qu'il sert à juger n'aurait aucun sens")


def test_le_caractere_ecarte_les_quarts():
    """Trois mois de mémoire pour une série en essai : non."""
    verifie(J.LEAD_QUART_MATIN in J.LEADS_INSTANT_T
            and J.LEAD_QUART_APREM in J.LEADS_INSTANT_T,
            "les deux étiquettes sont écartées de `model_character`")


def test_la_cle_d_archive_est_a_part():
    k = J.fcst_agrume_quart_key(JOUR)
    verifie("fcstagrumequart" in k and k != J.fcst_agrume_court_key(JOUR)
            and k != J.fcst_agrume_key(JOUR),
            f"quatrième préfixe, quatrième clé : {k}")



# ══════════════════════════════════════════════════════════════════
#  7. ⭐ L'INTÉGRATION — `daily_rows` lit-il vraiment le pas ?
#     (les cinq bancs que les mutations ont réclamés)
# ══════════════════════════════════════════════════════════════════

def _obs_line(sid, jour, vitesse_a, cadence_s=300):
    """Une ligne d'observation, cadence libre, sur toute la journée."""
    t0 = int(jour.timestamp()) - 3600
    n = (26 * 3600) // cadence_s
    t = [t0 + i * cadence_s for i in range(n)]
    return {"station_id": sid, "source": "pioupiou", "lat": 45.2,
            "lon": 6.6, "t": t,
            "speed": [vitesse_a(ts) for ts in t],
            "gust": [None] * n, "dir": [200.0] * n}


def _ligne_quart(sid, jour, valeur_a, n_servis=15):
    """Une ligne d'archive au pas de 15 min, telle que la produit
    `agrume_quart` : 21 cases, valeurs aux seuls quarts."""
    t0 = int(jour.replace(hour=7).timestamp())
    speed = [None] * 21
    servis = 0
    for i in range(21):
        t = t0 + i * 900
        if t % 3600 == 0 or servis >= n_servis:
            continue
        speed[i] = valeur_a(t)
        servis += 1
    return {"station_id": sid, "source": "pioupiou", "lat": 45.2, "lon": 6.6,
            "model": J.AGRUME_QUART_W1, "lead_h": J.LEAD_QUART_MATIN,
            "fetched_at": jour.replace(hour=6).isoformat(),
            "t0": t0, "step_s": 900,
            "speed": speed, "dir": [200.0] * 21, "gust": [None] * 21}


def test_daily_rows_utilise_la_demi_fenetre_du_pas():
    """⛔⛔ LE BANC QUE LA MUTATION Nº 1 A RÉCLAMÉ.

    Le compte de points appariés est le MÊME à ±7 et à ±20 min : une
    échéance a une paire dès qu'un seul relevé tombe dans sa fenêtre.
    Ce qui change, c'est la MOYENNE — à ±20 min on moyenne les relevés
    de trois échéances, et le vent servi est lissé. On met donc un vent
    à fort cycle horaire et une prévision ÉGALE à l'observation locale :
    à ±7 min l'erreur est presque nulle, à ±20 min le lissage la fait
    exploser. C'est la seule façon de rendre visible une faute qui ne
    change aucun compte.
    """
    jour = datetime(2026, 8, 12, tzinfo=UTC)

    def vent(ts):
        return 20.0 + 15.0 * math.sin(2 * math.pi * (ts % 3600) / 3600.0)

    snapshots = {0: [_ligne_quart("835", jour, vent)]}
    obs = [_obs_line("835", jour, vent)]
    rows, banded = J.daily_rows(jour, snapshots, obs, [], utc_offset_s=7200)
    r = next((x for x in rows if x["model"] == J.AGRUME_QUART_W1), None)
    verifie(r is not None, "la ligne au quart d'heure est notée")
    if r is None:
        return
    verifie(r["n_hours"] == 15,
            f"quinze échéances appariées ({r['n_hours']})")
    # ⭐ LES DEUX CHIFFRES CÔTE À CÔTE, plutôt qu'un seuil affirmé : on
    # recalcule la MÊME série avec la demi-fenêtre de l'heure ronde, et
    # on montre que les deux sont séparables. Un seuil seul se serait
    # périmé au premier changement de fixture ; celui-ci se lit.
    li = snapshots[0][0]
    times = J.fcst_times_ms(li)
    idx = [i for i, x in enumerate(li["speed"]) if x is not None]
    ech = S.ObsSample
    obs_s = [ech(t=int(t) * 1000, speed=v, dir=200.0)
             for t, v in zip(obs[0]["t"], obs[0]["speed"])]
    large = S.series_error(S.pair_series(
        [times[i] for i in idx], [li["speed"][i] for i in idx],
        [li["dir"][i] for i in idx], obs_s, S.OBS_HALF_WINDOW_MS)).med
    verifie(r["err_vec_med"] < 3.0 < large,
            f"⭐ ±7 min → {r['err_vec_med']:.2f} km/h · ±20 min → "
            f"{large:.2f} km/h sur LES MÊMES données. La faute nº 1 du "
            f"lot ne change aucun COMPTE (15 paires des deux côtés) : "
            f"elle moyenne le vent de trois échéances sous le nom d'une "
            f"seule, et c'est ce chiffre-ci, et lui seul, qui la voit")
    verifie(r["lead_h"] == J.LEAD_QUART_MATIN,
            "et la ligne garde l'échéance qu'elle déclare")
    # ⛔ La mutation nº 23 : la mémoire du caractère avale les quarts.
    verifie(banded == [],
            f"⛔ AUCUN détail par tranche : trois mois de moyenne "
            f"exponentielle pour un témoin fabriqué, non "
            f"({len(banded)} lignes)")


def test_daily_rows_applique_le_plancher_du_pas():
    """⛔ LE BANC QUE LA MUTATION Nº 5 A RÉCLAMÉ."""
    jour = datetime(2026, 8, 12, tzinfo=UTC)
    obs = [_obs_line("835", jour, lambda ts: 20.0)]
    for n, attendu in ((15, True), (13, True), (12, False), (6, False)):
        snap = {0: [_ligne_quart("835", jour, lambda ts: 20.0, n_servis=n)]}
        rows, _ = J.daily_rows(jour, snap, obs, [], utc_offset_s=7200)
        got = any(x["model"] == J.AGRUME_QUART_W1 for x in rows)
        verifie(got is attendu,
                f"{n} quarts servis → {'notée' if attendu else 'ÉCARTÉE'} "
                f"({'notée' if got else 'écartée'})")
    verifie(True, "⭐ 12 sur 15 est écarté, 13 passe : c'est le plancher "
                  "de CE pas, pas celui de l'heure ronde — sans quoi une "
                  "balise notée sur 6 points parmi 15 entrerait dans le "
                  "même tableau qu'une notée sur 15")


def test_l_heure_ronde_ne_change_pas_de_population():
    """⛔ NON-RÉGRESSION, mesurée et non affirmée."""
    jour = datetime(2026, 8, 12, tzinfo=UTC)
    t0 = int(jour.timestamp())
    ligne = {"station_id": "835", "source": "pioupiou", "lat": 45.2,
             "lon": 6.6, "model": "icon_d2",
             "fetched_at": jour.isoformat(), "t0": t0, "step_s": 3600,
             "speed": [20.0] * 24, "dir": [200.0] * 24,
             "gust": [None] * 24}
    obs = [_obs_line("835", jour, lambda ts: 20.0)]
    rows, _ = J.daily_rows(jour, {0: [ligne]}, obs, [], utc_offset_s=7200)
    r = next(x for x in rows if x["model"] == "icon_d2")
    verifie(r["n_hours"] == 24,
            f"une série horaire garde ses 24 heures ({r['n_hours']}) — "
            f"la demi-fenêtre et le plancher de l'heure ronde n'ont pas "
            f"bougé d'un millième")


def test_l_axe_pi_est_lu_par_identifiant():
    """⛔ LE BANC QUE LA MUTATION Nº 17 A RÉCLAMÉ.

    L'axe PI est RÉORDONNÉ : aucune valeur physique ne change, seule
    leur position. Lire par rang rendrait alors la correction d'une
    balise sur une autre — finie, plausible, et prise 40 km plus loin.
    """
    col, man = archive_a(base10=lambda k, s: (1.0, 2.0),
                         base20=lambda k, s: (3.0, 4.0))
    # Une valeur PI PROPRE À CHAQUE BALISE : sans ça, réordonner l'axe
    # ne changerait rien et le banc ne pourrait pas échouer.
    val = {"70": (20.0, 0.0), "1377": (-20.0, 0.0), "RS-06610": (0.0, 20.0)}
    d, pim = archive_pi(lambda bid, m: val[bid], ordre=[1, 0, 2])
    rows = Q.series_du_t(col, man, d, pim, T, J.LEAD_QUART_MATIN,
                         JOUR.replace(hour=0), JOUR.replace(hour=6),
                         crier=muet)
    kz = facteur_cisaillement(10)
    for sid in ("70", "1377"):
        r = next((x for x in rows if x["station_id"] == sid
                  and x["model"] == J.AGRUME_QUART_W1), None)
        if r is None:
            verifie(False, f"balise {sid} absente")
            continue
        i = next(k for k, x in enumerate(r["speed"]) if x is not None)
        att = decorer_vent({"u": 1.0 + kz * (val[sid][0] - 3.0),
                            "v": 2.0 + kz * (val[sid][1] - 4.0)})
        verifie(abs(r["speed"][i] - att["vitesseKmh"]) < 5e-2,
                f"balise {sid} : {r['speed'][i]:.2f} km/h, sa PROPRE "
                f"correction ({att['vitesseKmh']:.2f}) malgré un axe PI "
                f"réordonné")


def test_fetched_at_porte_le_run_pi():
    """⛔ LE BANC QUE LA MUTATION Nº 20 A RÉCLAMÉ — décision Q5.

    Le composite N'EXISTAIT PAS avant le run PI : c'est son heure qui
    date la ligne. Y mettre celle du run AROME créditerait la classe
    d'une fraîcheur de six heures qu'elle n'a pas, et `lead_exact_h`
    glisserait d'autant sans qu'une ligne ne le dise.
    """
    col, man, d, pim = _archives()
    r_a, r_p = JOUR.replace(hour=0), JOUR.replace(hour=6)
    rows = Q.series_du_t(col, man, d, pim, T, J.LEAD_QUART_MATIN,
                         r_a, r_p, crier=muet)
    attendu = r_p.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    verifie(all(r["fetched_at"] == attendu for r in rows),
            f"toutes les lignes portent l'heure du run PI ({attendu}) …")
    verifie(all(not r["fetched_at"].startswith(r_a.strftime("%Y-%m-%dT%H"))
                for r in rows),
            "… et JAMAIS celle du run AROME, qui vaut six heures de "
            "fraîcheur imméritée")


# ══════════════════════════════════════════════════════════════════

def main():
    for nom, fn in sorted(globals().items()):
        if nom.startswith("test_") and callable(fn):
            print(f"\n── {nom}")
            fn()
    print()
    if ECHECS:
        print(f"❌ {len(ECHECS)} banc(s) rouge(s) :")
        for e in ECHECS:
            print(f"   · {e}")
        return 1
    print("✅ tous les bancs de la classe au quart d'heure sont verts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
