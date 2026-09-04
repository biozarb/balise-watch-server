#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/test_agrume_fcst.py — le banc du producteur AGRUME
#                                            (Lot I, 13/08/2026)
#
#  Sans réseau, sans clé, sans base. Il ne vérifie pas que le
#  producteur « marche » : il vérifie les six façons qu'il aurait de
#  casser EN SILENCE.
#
#      python3 test_agrume_fcst.py
#
#  ⚠️ Il exige numpy (le produit A est un `.npz`). Pas de version « qui
#  saute si le module est absent » : un banc qui se désactive tout seul
#  est un banc qui ne dit plus rien, et c'est exactement ce que le lot P
#  interdit.
#
#  ═══ CHACUN DE CES BANCS A ÉTÉ REJOUÉ CONTRE UN CODE CASSÉ ═══
#  (la preuve qu'ils savent échouer — détail dans la note de session)
#
#  · direction        → `S.from_uv(u, v)` au lieu de `decorer_vent`  → 180° d'écart
#  · échéances        → `speed.append(...)` dans l'ordre du tableau   → 2 h de décalage
#  · absence          → `0.0` au lieu de `None` sur un NaN            → 24 h de calme inventé
#  · radiosondages    → pas de filtre sur `source`                    → 2 lignes qui ne s'apparient à rien
#  · bucket           → `Storage(...)` sans le garde                  → 0 ligne, toutes les nuits, sans bruit
#  · lead 24          → flux AGRUME lu au seul offset 0               → le banc ne prouve plus rien
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

import numpy as np                                          # noqa: E402

import agrume_fcst as A                                     # noqa: E402
import score as SC                                          # noqa: E402
import scoring as S                                         # noqa: E402
from colonnes import Colonnes                                # noqa: E402

ECHECS: list[str] = []


def verifie(condition, message):
    if condition:
        print(f"  ✅ {message}")
    else:
        print(f"  ❌ {message}")
        ECHECS.append(message)


# ══════════════════════════════════════════════════════════════════
#  FABRIQUE — une archive minuscule, mais de la vraie classe
# ══════════════════════════════════════════════════════════════════

RUN = "2026-08-12T00:00:00Z"

BALISES = [
    {"id": "70", "lat": 46.15, "lon": 6.19, "nom": "Salève",
     "source": "pioupiou", "position_suspecte": False},
    {"id": "1377", "lat": 45.60, "lon": 6.20, "nom": "Un déco",
     "source": "pioupiou", "position_suspecte": False},
    {"id": "RS-06610", "lat": 46.81, "lon": 6.94, "nom": "Payerne",
     "source": "radiosondage", "position_suspecte": False},
]


def archive(steps, remplir, balises=None):
    """Un `Colonnes` rempli par `remplir(k_balise, i_step) -> (u, v)`.

    `None` rendu par `remplir` laisse le NaN d'origine — c'est ainsi
    qu'on fabrique une absence, jamais avec un zéro.
    """
    bal = BALISES if balises is None else balises
    col = Colonnes(RUN, bal, list(steps))
    iu, iv = col.i_param_001["u"], col.i_param_001["v"]
    j10 = col.i_niveau_001[10]
    for k in range(len(bal)):
        for i in range(len(col.steps)):
            uv = remplir(k, i)
            if uv is None:
                continue
            col.c001[k, iu, j10, i] = np.float16(uv[0])
            col.c001[k, iv, j10, i] = np.float16(uv[1])
    man = {"run": RUN, "echeances": list(col.steps), "balises": bal}
    return col, man


#: Vent d'ouest à 5 m/s : u = +5 (il souffle VERS l'est), v = 0. Un
#: vent d'ouest vient de 270°.
OUEST = (5.0, 0.0)


# ══════════════════════════════════════════════════════════════════
#  1. LA CONVENTION DE DIRECTION, ET LE PIÈGE À 180°
# ══════════════════════════════════════════════════════════════════

def test_convention_de_direction():
    """⚠️ LE DÉFAUT LE PLUS COÛTEUX DU LOT, ET IL NE LÈVE RIEN.

    `agrume/profil.decorer_vent` et `model-verif/scoring.from_uv` ne
    parlent pas du même vecteur : le premier reçoit le u/v du GRIB
    (celui VERS où le vent souffle), le second le vecteur « d'où ça
    vient » que `to_uv` fabrique. Passer le u/v d'AROME à `from_uv` tel
    quel donne une direction juste à 180° près — et un score qui reste
    parfaitement crédible, parce que l'erreur vectorielle d'un vent
    inversé ressemble à celle d'un modèle médiocre.
    """
    print("\n▶ 1. convention de direction")
    col, man = archive([0], lambda k, i: OUEST)
    rows = list(A.lignes(col, man))
    r = rows[0]
    verifie(r["speed"][0] == 18.0, f"5 m/s → 18,0 km/h (lu {r['speed'][0]})")
    verifie(r["dir"][0] == 270,
            f"u=+5, v=0 → vent d'OUEST, direction 270° (lu {r['dir'][0]})")

    col, man = archive([0], lambda k, i: (0.0, -5.0))
    r = list(A.lignes(col, man))[0]
    verifie(r["dir"][0] == 0,
            f"u=0, v=−5 → vent de NORD, direction 0° (lu {r['dir'][0]})")

    # Le piège lui-même, tenu à l'endroit : si un jour quelqu'un
    # branche `from_uv` sur le u/v d'AROME, il obtiendra CE chiffre-là.
    piege = S.from_uv(*OUEST)
    verifie(abs(S.angular_diff(270.0, piege)) == 180.0,
            f"`scoring.from_uv(u, v)` sur le u/v d'AROME rend {piege:.0f}° "
            f"— 180° d'écart : c'est bien un piège, pas une équivalence")


# ══════════════════════════════════════════════════════════════════
#  2. LES ÉCHÉANCES SE RANGENT PAR VALEUR, PAS PAR POSITION
# ══════════════════════════════════════════════════════════════════

def test_echeances_non_contigues():
    """Le défaut de dé-accumulation POSITIONNELLE de l'audit du 13/08,
    transposé : un run tronqué ou troué décalerait toutes les heures
    d'après le trou, du bon ordre de grandeur pour passer inaperçu.
    """
    print("\n▶ 2. échéances non contiguës")
    steps = [0, 1, 2, 5]
    # Une valeur DIFFÉRENTE par échéance : un décalage se verrait.
    col, man = archive(steps, lambda k, i: (float(steps[i]) + 1.0, 0.0))
    r = list(A.lignes(col, man))[0]
    verifie(len(r["speed"]) == 6,
            f"la série va jusqu'à l'heure 5 incluse ({len(r['speed'])} cases)")
    attendu = [round((s + 1.0) * 3.6, 1) if s in steps else None
               for s in range(6)]
    verifie(r["speed"] == attendu,
            f"chaque valeur à SON heure, trous compris — {r['speed']}")

    # Et le contrat côté lecteur : `score.fcst_times_ms` doit retrouver
    # les mêmes heures que celles qu'on croit avoir écrites.
    times = SC.fcst_times_ms(r)
    t0 = datetime(2026, 8, 12, tzinfo=timezone.utc)
    heures = [datetime.fromtimestamp(t / 1000, timezone.utc).hour for t in times]
    verifie(heures == list(range(6)) and times[0] == int(t0.timestamp()) * 1000,
            "`score.fcst_times_ms` relit exactement les heures 0 à 5")


# ══════════════════════════════════════════════════════════════════
#  3. UNE ABSENCE RESTE UNE ABSENCE
# ══════════════════════════════════════════════════════════════════

def test_nan_reste_absence():
    print("\n▶ 3. NaN → None, jamais 0")
    col, man = archive([0, 1, 2], lambda k, i: None if i == 1 else OUEST)
    r = list(A.lignes(col, man))[0]
    verifie(r["speed"] == [18.0, None, 18.0] and r["dir"][1] is None,
            f"le trou reste vide, il ne devient pas du calme — {r['speed']}")
    verifie(0.0 not in [s for s in r["speed"] if s is not None],
            "aucun 0,0 n'apparaît (un 0 est un vent crédible, pas une absence)")


def test_balise_entierement_vide():
    print("\n▶ 4. une balise sans une seule valeur ne donne pas de ligne")
    col, man = archive([0, 1], lambda k, i: None if k == 0 else OUEST)
    ids = [r["station_id"] for r in A.lignes(col, man)]
    verifie("70" not in ids and "1377" in ids,
            f"la balise muette est absente de l'archive — {ids}")


# ══════════════════════════════════════════════════════════════════
#  5. QUI ENTRE DANS LE FLUX
# ══════════════════════════════════════════════════════════════════

def test_seules_les_balises_pioupiou():
    print("\n▶ 5. les radiosondages n'entrent pas")
    col, man = archive([0], lambda k, i: OUEST)
    rows = list(A.lignes(col, man))
    verifie(all(r["source"] == "pioupiou" for r in rows)
            and not any(r["station_id"].startswith("RS-") for r in rows),
            f"{len(rows)} lignes, aucune station de lâcher de ballon")
    verifie(all(r["model"] == "agrume" for r in rows)
            and rows[0]["agrume_run"] == RUN
            and rows[0]["agrume_maille"] == "001",
            "le modèle, le run et la maille sont écrits dans chaque ligne")
    verifie(rows[0]["fetched_at"].startswith("2026-08-12T00:00:00"),
            f"`fetched_at` porte l'heure du RUN — {rows[0]['fetched_at']}")


# ══════════════════════════════════════════════════════════════════
#  5bis. LOT L7 — PLUSIEURS SOURCES NOTÉES, ET LA BONNE SUR CHAQUE LIGNE
# ══════════════════════════════════════════════════════════════════

def test_plusieurs_sources_metar_exclu():
    """⛔ LE PIÈGE EXACT DU LOT L7 : `"source": SOURCE_NOTEE` au lieu de
    `"source": b.get("source")`. Tant que SOURCE_NOTEE était UNE chaîne
    ("pioupiou"), les deux écritures rendaient le même résultat — ce
    banc n'aurait donc RIEN vu avant que SOURCE_NOTEE devienne un
    ensemble. Avec une balise windsmobi et une balise metar dans le même
    axe, un code qui stamperait `SOURCE_NOTEE` (l'ensemble) au lieu de la
    source réelle planterait ici (un `frozenset` n'est pas sérialisable
    dans le sens attendu) ou, pire, écrirait une valeur incohérente selon
    l'ordre d'itération — silencieux, comme d'habitude.
    """
    print("\n▶ 5bis. plusieurs sources notées (lot L7), metar exclu")
    balises = BALISES + [
        {"id": "W-42", "lat": 45.90, "lon": 6.10, "nom": "Un capteur windsmobi",
         "source": "windsmobi", "position_suspecte": False},
        {"id": "LFLB", "lat": 45.64, "lon": 5.88, "nom": "Aérodrome",
         "source": "metar", "position_suspecte": False},
    ]
    col, man = archive([0], lambda k, i: OUEST, balises=balises)
    rows = list(A.lignes(col, man))
    par_id = {r["station_id"]: r for r in rows}

    verifie("W-42" in par_id, "la balise windsmobi entre dans le flux")
    verifie("LFLB" not in par_id,
            "la balise metar N'entre PAS — colonne dans l'axe, mais hors "
            "de SOURCE_NOTEE (audit PS3 : obsmetar sert le tau, pas ce flux)")
    verifie("RS-06610" not in par_id,
            "le radiosondage reste exclu, comme avant le lot L7")
    verifie(par_id.get("70", {}).get("source") == "pioupiou",
            f"la balise 70 est stampée `pioupiou`, sa vraie source — "
            f"{par_id.get('70', {}).get('source')!r}")
    verifie(par_id.get("W-42", {}).get("source") == "windsmobi",
            f"la balise W-42 est stampée `windsmobi`, SA vraie source, "
            f"pas une autre membre de SOURCE_NOTEE — "
            f"{par_id.get('W-42', {}).get('source')!r}")
    sources_ecrites = {r["source"] for r in rows}
    verifie(sources_ecrites <= set(A.SOURCE_NOTEE),
            f"aucune ligne ne porte une source hors de SOURCE_NOTEE — "
            f"{sources_ecrites}")
    verifie("metar" not in sources_ecrites,
            "metar n'apparaît sur AUCUNE ligne du flux noté")


# ══════════════════════════════════════════════════════════════════
#  6. LE GARDE DE BUCKET
# ══════════════════════════════════════════════════════════════════

def test_garde_de_bucket():
    """⛔ `run.sh` exporte `R2_BUCKET=model-verif`, et `storage.py` fait
    primer `R2_BUCKET` sur le `bucket_env` passé en argument. Sans le
    garde, la lecture du produit A irait chercher
    `model-verif/agrume/colonnes/…` : absent, donc « run absent », donc
    zéro ligne AGRUME toutes les nuits — sur un chemin où rien ne
    s'allume, parce qu'un run absent est un cas normal.
    """
    print("\n▶ 6. le garde de bucket")
    avant = os.environ.get("R2_BUCKET")
    os.environ["R2_BUCKET"] = "model-verif"
    try:
        with A.bucket_r2("wind-grid"):
            dedans = os.environ.get("R2_BUCKET")
        apres = os.environ.get("R2_BUCKET")
        verifie(dedans == "wind-grid",
                f"dans le bloc, R2_BUCKET vaut « {dedans} »")
        verifie(apres == "model-verif",
                f"en sortant, il est restauré à « {apres} » — l'envoi de "
                f"l'archive repart sur le bon bucket")
        # Et le cas où la variable n'existait pas : elle ne doit pas
        # être INVENTÉE en sortie, sinon le mode `score` hériterait d'un
        # bucket que personne ne lui a donné.
        del os.environ["R2_BUCKET"]
        with A.bucket_r2("wind-grid"):
            pass
        verifie("R2_BUCKET" not in os.environ,
                "une variable absente le reste après le bloc")
        # ⚠️ Et le bucket lui-même : `wind-grid` est le nom du dos
        # SUPABASE, pas celui du bucket R2. `agrume/run-ingest-pi.sh`
        # écrit `balise-watch-grids` depuis le 10/08 ; deux noms pour
        # une notion, c'est ainsi qu'on lit dans le vide sans le voir.
        verifie(A.BUCKET_R2_DEFAUT == "balise-watch-grids"
                and A.BUCKET_R2_ENV == "AGRUME_R2_BUCKET",
                f"le bucket R2 du produit A est « {A.BUCKET_R2_DEFAUT} », "
                f"pilotable par {A.BUCKET_R2_ENV} — comme run-ingest-pi.sh")

        # ⛔ ET LES IDENTIFIANTS. Le jeton ordinaire du VPS ÉCRIT sur
        # balise-watch-grids sans pouvoir le LIRE — 403 mesuré le 13/08
        # sur une clé PI écrite six minutes plus tôt. Sans ce
        # basculement, le producteur ne lirait jamais rien.
        os.environ["R2_ACCESS_KEY_ID"] = "jeton-ecriture"
        os.environ["R2_SECRET_ACCESS_KEY"] = "secret-ecriture"
        os.environ["BW_R2_AUDIT_ACCESS_KEY_ID"] = "jeton-lecture"
        os.environ["BW_R2_AUDIT_SECRET_ACCESS_KEY"] = "secret-lecture"
        try:
            verifie(A.prefixe_lecture() == "BW_R2_AUDIT_",
                    f"les identifiants de lecture retenus sont "
                    f"{A.prefixe_lecture()}* (le jeton d'audit, seul en "
                    f"lecture sur ce VPS)")
            with A.bucket_r2("balise-watch-grids", A.prefixe_lecture()):
                dedans = os.environ["R2_ACCESS_KEY_ID"]
            verifie(dedans == "jeton-lecture",
                    f"dans le bloc, c'est le jeton de LECTURE ({dedans})")
            verifie(os.environ["R2_ACCESS_KEY_ID"] == "jeton-ecriture",
                    "en sortant, le jeton d'écriture est restauré — sinon "
                    "l'archive partirait signée du mauvais jeton")
            # Et le repli : sans jeton d'audit, on retombe sur R2_* — un
            # repli qui ÉCHOUERA sur le VPS d'aujourd'hui, et c'est
            # `lire_run` qui doit le dire, pas ce banc.
            del os.environ["BW_R2_AUDIT_ACCESS_KEY_ID"]
            del os.environ["BW_R2_AUDIT_SECRET_ACCESS_KEY"]
            verifie(A.prefixe_lecture() == "R2_",
                    "sans jeton dédié ni jeton d'audit, on retombe sur R2_*")
        finally:
            for v in ("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY",
                      "BW_R2_AUDIT_ACCESS_KEY_ID",
                      "BW_R2_AUDIT_SECRET_ACCESS_KEY"):
                os.environ.pop(v, None)
    finally:
        if avant is None:
            os.environ.pop("R2_BUCKET", None)
        else:
            os.environ["R2_BUCKET"] = avant


# ══════════════════════════════════════════════════════════════════
#  7-8. LE LOT LUI-MÊME : +6 h SORT, +24 h NE SORT PAS
# ══════════════════════════════════════════════════════════════════

JOUR = datetime(2026, 8, 12, tzinfo=timezone.utc)


def _obs_constantes(speed_kmh, dir_deg, jour=JOUR, heures=range(24)):
    """Une balise qui relève toutes les 10 min, toute la journée."""
    t0 = int(jour.timestamp())
    t, sp, di = [], [], []
    for h in heures:
        for m in (0, 10, 20, 30, 40, 50):
            t.append(t0 + h * 3600 + m * 60)
            sp.append(speed_kmh)
            di.append(dir_deg)
    return {"source": "pioupiou", "station_id": "70",
            "t": t, "speed": sp, "dir": di}


def _serie_agrume(run_dt, n_heures=25, speed_kmh=25.0, dir_deg=270.0):
    """Une ligne AGRUME telle que `lignes()` l'écrit, mais posée à la
    main pour maîtriser force et direction (le banc de conversion, lui,
    a déjà vérifié le pont u/v → force/direction)."""
    return {"station_id": "70", "source": "pioupiou", "lat": 46.15, "lon": 6.19,
            "model": "agrume", "fetched_at": run_dt.isoformat(),
            "t0": int(run_dt.timestamp()), "step_s": 3600,
            "speed": [speed_kmh] * n_heures, "dir": [dir_deg] * n_heures,
            "agrume_run": run_dt.strftime("%Y-%m-%dT%H:00:00Z"),
            "agrume_maille": "001"}


def test_lead_6_sort_avec_un_score_connu():
    print("\n▶ 7. le +6 h sort, et son erreur est celle qu'on a posée")
    obs = _obs_constantes(20.0, 270.0)
    ligne = _serie_agrume(JOUR)          # run 00 Z de la journée notée
    rows, _ = SC.daily_rows(JOUR, {0: [ligne], 1: [], 2: []},
                            [obs], [], 7200)
    ag = [r for r in rows if r["model"] == "agrume"]
    verifie(len(ag) == 1, f"une ligne AGRUME et une seule ({len(ag)})")
    if not ag:
        return
    r = ag[0]
    verifie(r["lead_h"] == 6, f"classée +{r['lead_h']} h")
    verifie(r["n_hours"] == 24, f"24 heures appariées ({r['n_hours']})")
    # 25 km/h prévus contre 20 observés, même direction : l'erreur
    # vectorielle vaut exactement 5 km/h à toutes les heures.
    verifie(r["err_vec_med"] == 5.0,
            f"erreur vectorielle médiane = 5,0 km/h (lu {r['err_vec_med']})")
    verifie(r["vector_ratio"] == 1.0,
            "toutes les paires sont vectorielles (les deux côtés ont une "
            "direction et dépassent 5 km/h)")
    verifie(r["fcst_src"] == "own_archive",
            "`fcst_src` reste `own_archive` — aucune migration SQL, le nom "
            "du modèle suffit à distinguer la série")
    # ⚠️ La colonne de diagnostic, celle dont la convention diffère.
    verifie(11.0 < r["lead_exact_h"] < 12.0,
            f"`lead_exact_h` ≈ 11,5 h, compté depuis le RUN "
            f"(lu {r['lead_exact_h']})")


def _serie_arome(run_dt, n_heures=52, speed_kmh=30.0, dir_deg=270.0):
    """Une ligne `arome_r2` telle qu'`arome_fcst.py` l'écrit (0-51 h)."""
    return {"station_id": "70", "source": "pioupiou", "lat": 46.15, "lon": 6.19,
            "model": "arome_r2", "fetched_at": run_dt.isoformat(),
            "t0": int(run_dt.timestamp()), "step_s": 3600,
            "speed": [speed_kmh] * n_heures, "dir": [dir_deg] * n_heures,
            "arome_run": run_dt.strftime("%Y-%m-%dT%H:00:00Z")}


def test_lead_24_par_la_ligne_soeur():
    """⛔ LOT L20 (04/09/2026) — le +24 h SORT, par une ligne SŒUR lue dans
    `arome_r2`, et l'échéance qu'elle porte est celle du run d'`arome_r2`.
    Le banc d'avant (« le +24 h ne sort pas ») reste vrai pour la ligne
    d'ORIGINE : c'est la première moitié de celui-ci.
    """
    print("\n▶ 8. le +24 h sort par la ligne sœur, et pas autrement")
    obs = _obs_constantes(20.0, 270.0)
    veille = _serie_agrume(JOUR - timedelta(days=1))
    rows, _ = SC.daily_rows(JOUR, {0: [], 1: [veille], 2: []}, [obs], [], 7200)
    verifie(not [r for r in rows if r["model"] == "agrume"],
            "la ligne d'ORIGINE (0-24 h) ne donne toujours AUCUNE ligne +24 h "
            "(une seule heure appariable)")

    # ── la sœur, run identique (00 Z) ────────────────────────────────
    arome = _serie_arome(JOUR - timedelta(days=1))
    soeurs, bilan = A.prolonger_h24([veille], [arome])
    verifie(len(soeurs) == 1 and bilan["prolongees"] == 1,
            f"une ligne sœur par ligne AGRUME ({bilan})")
    so = soeurs[0]
    verifie(so["model"] == "agrume" and so["agrume_h24_copie"] is True
            and so["agrume_h24_source"] == "arome_r2",
            "la sœur porte le nom AGRUME et se DÉCLARE copie d'arome_r2")
    verifie(all(v is None for v in so["speed"][:24])
            and all(v == 30.0 for v in so["speed"][24:]),
            "ses heures < 24 sont None, ses heures ≥ 24 sont celles d'arome_r2")
    verifie(bilan["runs_identiques"] is True, "le bilan voit que les runs sont les mêmes")

    rows, _ = SC.daily_rows(JOUR, {0: [], 1: [veille, so], 2: []}, [obs], [], 7200)
    ag = [r for r in rows if r["model"] == "agrume"]
    verifie(len(ag) == 1 and ag[0]["lead_h"] == 24 and ag[0]["n_hours"] == 24,
            f"⭐ UNE ligne AGRUME en classe +24 h, 24 heures appariées "
            f"({[(r['lead_h'], r['n_hours']) for r in ag]})")
    verifie(ag and ag[0]["err_vec_med"] == 10.0,
            "… et son erreur est celle d'arome_r2 (30 prévu, 20 observé : 10 km/h)")
    # à l'offset 0, la sœur ne touche pas la journée du run
    rows0, _ = SC.daily_rows(JOUR - timedelta(days=1), {0: [veille, so], 1: [], 2: []},
                             [_obs_constantes(20.0, 270.0, JOUR - timedelta(days=1))],
                             [], 7200)
    ag0 = [r for r in rows0 if r["model"] == "agrume"]
    verifie(len(ag0) == 1 and ag0[0]["lead_h"] == 6 and ag0[0]["err_vec_med"] == 5.0,
            "⛔ à +6 h, la classe reste la ligne d'ORIGINE, bit à bit (25 → 5 km/h) "
            "— la sœur n'y entre pas")

    # ── runs DIFFÉRENTS (arome_r2 au 03 Z) : l'échéance dit la vérité ──
    arome03 = _serie_arome(JOUR - timedelta(days=1) + timedelta(hours=3))
    soeurs03, bilan03 = A.prolonger_h24([veille], [arome03])
    verifie(bilan03["runs_identiques"] is False and "≠ AGRUME" in A.dire_h24(bilan03, veille["agrume_run"]),
            "le journal DIT que le run d'arome_r2 n'est pas celui d'AGRUME")
    so03 = soeurs03[0]
    verifie(so03["fetched_at"] == arome03["fetched_at"] and so03["t0"] == arome03["t0"],
            "⛔ la sœur porte le run d'AROME_R2 (t0, fetched_at), pas celui d'AGRUME")
    rows03, _ = SC.daily_rows(JOUR, {0: [], 1: [veille, so03], 2: []}, [obs], [], 7200)
    ag03 = next(r for r in rows03 if r["model"] == "agrume")
    ar03 = next(r for r in SC.daily_rows(JOUR, {0: [], 1: [arome03], 2: []}, [obs], [], 7200)[0]
                if r["model"] == "arome_r2")
    verifie(abs(ag03["lead_exact_h"] - ar03["lead_exact_h"]) < 1e-9,
            f"⭐ `lead_exact_h` d'AGRUME +24 h == celui d'arome_r2 +24 h "
            f"({ag03['lead_exact_h']} vs {ar03['lead_exact_h']}) — aucune fraîcheur volée")
    verifie(ag03["lead_exact_h"] < 35.0,
            "… et il est bien plus court que celui d'un 00 Z (le 03 Z est plus frais)")

    # ── pas de ligne arome_r2 → pas de sœur, et c'est compté ──────────
    rien, b_rien = A.prolonger_h24([veille], [])
    verifie(rien == [] and b_rien["sans_arome"] == 1 and "AUCUNE" in A.dire_h24(b_rien, None),
            "sans ligne arome_r2, aucune sœur, et le journal le dit")
    # ── la série PI a sa sœur aussi, avec 0 heure PI ──────────────────
    pi = dict(veille, model="agrume_pi", agrume_pi_heures=6, agrume_pi_run="x")
    s_pi, _ = A.prolonger_h24([pi], [arome])
    verifie(s_pi and s_pi[0]["model"] == "agrume_pi" and s_pi[0]["agrume_pi_heures"] == 0,
            "la sœur d'agrume_pi porte `agrume_pi_heures = 0` (PI ne touche aucune de ces heures)")


def test_lead_24_ne_sort_aucune_ligne():
    """⛔ LA PROPRIÉTÉ QUI TIENT LA DÉCISION 1 DU LOT.

    Le run 00 Z de la veille ne touche la journée notée que par l'heure
    00 : une seule heure appariable, sous `MIN_HOURS_DAILY`. Si ce banc
    tombe un jour, c'est que l'horizon de l'ARCHIVE AGRUME a bougé.
    ⓘ Lot L20 (04/09/2026) : le +24 h existe désormais, mais par la ligne
    SŒUR (`test_lead_24_par_la_ligne_soeur`) — cette propriété-ci reste
    vraie pour la ligne d'origine, et c'est ce qui garantit que la
    classe +6 h n'a pas bougé.
    """
    print("\n▶ 8. le +24 h ne sort pas, et c'est mesuré")
    obs = _obs_constantes(20.0, 270.0)
    veille = _serie_agrume(JOUR - timedelta(days=1))
    rows, _ = SC.daily_rows(JOUR, {0: [], 1: [veille], 2: []},
                            [obs], [], 7200)
    ag = [r for r in rows if r["model"] == "agrume"]
    verifie(not ag, f"aucune ligne AGRUME en classe +24 h ({len(ag)})")

    # La raison, mesurée plutôt qu'affirmée : combien d'heures de la
    # journée notée un run 00 Z de la veille atteint-il vraiment ?
    jour_ms = int(JOUR.timestamp()) * 1000
    dedans = [t for t in SC.fcst_times_ms(veille)
              if jour_ms <= t < jour_ms + SC.DAY_MS]
    verifie(len(dedans) == 1 and len(dedans) < SC.MIN_HOURS_DAILY,
            f"{len(dedans)} heure atteinte sur les 24, plancher à "
            f"{SC.MIN_HOURS_DAILY} — l'horizon décide, pas une garde écrite "
            f"à la main")

    # Et l'inverse, pour que le banc ne puisse pas passer au vert parce
    # que `daily_rows` aurait cessé de voir le flux : le MÊME appareil,
    # avec le run du jour, donne bien une ligne.
    rows, _ = SC.daily_rows(JOUR, {0: [_serie_agrume(JOUR)], 1: [veille], 2: []},
                            [obs], [], 7200)
    verifie(len([r for r in rows if r["model"] == "agrume"]) == 1,
            "le même appareil rend bien une ligne quand le run est celui "
            "du jour — le banc ne passe pas au vert par aveuglement")


# ══════════════════════════════════════════════════════════════════
#  9. UN RUN ABSENT NE FABRIQUE PAS UN ZÉRO
# ══════════════════════════════════════════════════════════════════

def test_run_absent():
    print("\n▶ 9. un run absent ne fabrique rien")
    lu = []
    A_lire = A.lire_run
    try:
        A.lire_run = lambda run, crier=print: (lu.append(run), None)[1]
        run, col, man = A.choisir_run(JOUR, crier=lambda *_: None)
        verifie(run is None and col is None,
                "aucun run retenu, et rien d'inventé pour compenser")
        verifie(lu == [f"2026-08-12T{h:02d}:00:00Z" for h in A.RUNS_ADMIS],
                f"les runs admis ont été essayés dans l'ordre — {lu}")
        verifie(A.RUNS_ADMIS == (0, 3),
                "et ils sont bornés à 00 Z et 03 Z : un run de 15 Z "
                "donnerait à AGRUME dix heures de fraîcheur sur les autres "
                "modèles, sous le même intitulé « +6 h »")
    finally:
        A.lire_run = A_lire


# ══════════════════════════════════════════════════════════════════
#  10. LA CLÉ, ET LE BOUT-À-BOUT SUR DISQUE
# ══════════════════════════════════════════════════════════════════

def test_cle_et_bout_a_bout():
    print("\n▶ 10. la clé du flux, et le tour complet sur disque")
    k = SC.fcst_agrume_key(JOUR)
    verifie(k == "fcstagrume/2026/08/fcstagrume_2026-08-12.ndjson.gz",
            f"clé attendue — {k}")
    verifie(not k.startswith("fcst/"),
            "le flux AGRUME ne peut pas écraser l'archive Open-Meteo, qui "
            "est irremplaçable (0/384 sur `_previous_day1` côté MF)")

    col, man = archive([0, 1, 2], lambda k_, i: OUEST)
    rows = list(A.lignes(col, man))
    with tempfile.TemporaryDirectory() as d:
        path = pathlib.Path(d) / k
        from collect import write_ndjson_gz
        n = write_ndjson_gz(path, rows)
        relu = [json.loads(l) for l in
                gzip.decompress(path.read_bytes()).decode().splitlines()]
        verifie(n == len(rows) == len(relu),
                f"{n} lignes écrites, {len(relu)} relues")
        # `read_ndjson` est le lecteur réel de `score.py` : c'est LUI
        # qui doit savoir relire ce que le producteur écrit, pas un
        # parseur de banc.
        par_score = SC.read_ndjson(pathlib.Path(d), k)
        verifie(len(par_score) == len(rows)
                and par_score[0]["model"] == "agrume",
                "`score.read_ndjson` relit le flux sans rien savoir d'AGRUME")

        # ⛔ ET LES DEUX FLUX SE LISENT ENSEMBLE, POUR N'IMPORTE QUEL
        # JOUR. C'est la propriété qui tient la décision 1 côté lecteur :
        # si quelqu'un écrit un jour `if offset == 0` autour du flux
        # AGRUME, l'élimination du +24 h cessera d'être une MESURE pour
        # devenir une garde — juste jusqu'au jour où l'horizon bougera.
        write_ndjson_gz(pathlib.Path(d) / SC.fcst_key(JOUR),
                        [{"station_id": "70", "source": "pioupiou",
                          "model": "icon_d2", "fetched_at": JOUR.isoformat(),
                          "t0": int(JOUR.timestamp()), "step_s": 3600,
                          "speed": [12.0], "dir": [270.0]}])
        ensemble = SC.snapshot_rows(pathlib.Path(d), JOUR)
        modeles = sorted({r["model"] for r in ensemble})
        verifie(modeles == ["agrume", "icon_d2"],
                f"`snapshot_rows` rend les deux flux pour la même journée "
                f"— {modeles}")


def main() -> int:
    print("═" * 66)
    print("  BANC DU PRODUCTEUR AGRUME — lot I, 13/08/2026")
    print("═" * 66)
    test_convention_de_direction()
    test_echeances_non_contigues()
    test_nan_reste_absence()
    test_balise_entierement_vide()
    test_seules_les_balises_pioupiou()
    test_plusieurs_sources_metar_exclu()
    test_garde_de_bucket()
    test_lead_6_sort_avec_un_score_connu()
    test_lead_24_ne_sort_aucune_ligne()
    test_lead_24_par_la_ligne_soeur()
    test_run_absent()
    test_cle_et_bout_a_bout()
    print("\n" + "═" * 66)
    if ECHECS:
        print(f"❌ {len(ECHECS)} assertion(s) en échec :")
        for e in ECHECS:
            print(f"   · {e}")
        return 1
    print("✅ banc du producteur AGRUME : tout est vert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
