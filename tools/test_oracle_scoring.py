# ══════════════════════════════════════════════════════════════════════
#  tools/test_oracle_scoring.py — le banc de L'ORACLE BATCH
#                                              (Lot L12, 01/09/2026)
#
#  Sans reseau, sans cle, sans base : tout se joue sur une archive
#  FORGEE dans un dossier temporaire.
#
#      python3 tools/test_oracle_scoring.py
#
#  ═══ CE QUE CHACUN TIENT, ET CE QUE ÇA COÛTERAIT DE NE PAS L'AVOIR ═══
#
#  · independance   → l'oracle importe la chaine → il compare la faute a
#                                                  elle-meme et rend ✅
#                                                  la nuit ou l'EWMA
#                                                  repart de zero
#  · PARITE         → la transcription des       → l'oracle crie tous les
#                     constantes derive             mois pour rien, et on
#                                                   finit par ne plus le lire
#  · fenetre        → ±20 min devient ±30        → deux echeances partagent
#                                                  des releves
#  · plancher       → une balise-jour de 2 h     → une mediane sur deux
#                     est publiee                  points, publiee comme un
#                                                  score
#  · journee        → une echeance de J+1 compte → la journee note ce qu'elle
#                                                  n'a pas vecu
#  · direction      → moyenne ARITHMETIQUE des   → 350° et 10° donnent plein
#                     caps                         sud : l'erreur double
#  · girouette      → les releves sous 5 km/h    → du bruit uniforme tire le
#                     entrent dans le vecteur      vecteur vers zero
#  · lead declare   → l'offset l'emporte sur le  → les classes courte et au
#                     `lead_h` de la ligne         quart d'heure atterrissent
#                                                  sous `lead_h = 6`
#  · exclusions     → un doublon L17 entre dans  → des cases qui n'existent
#                     la case                      que grace a une seconde
#                                                  inscription
#  · quorum         → une case a 2 balises       → un score de zone qui est
#                                                  celui d'une balise
#  · mediane groupee→ moyenne des medianes du    → un chiffre plausible et
#                     jour                         faux, exactement le
#                                                  danger que l'oracle existe
#                                                  pour voir
#  · deux sens      → seul l'ecart de VALEUR est → une nuit qui n'ecrit rien
#                     compte                       ne produit aucun ecart,
#                                                  donc aucune alerte
# ══════════════════════════════════════════════════════════════════════
from __future__ import annotations

import gzip
import json
import math
import os
import pathlib
import random
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone

ICI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))

import oracle_scoring as O                                  # noqa: E402

ECHECS: list[str] = []
UTC = timezone.utc


def verifie(condition, message):
    if condition:
        print(f"  ✅ {message}")
    else:
        print(f"  ❌ {message}")
        ECHECS.append(message)


def jour(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=UTC)


def ms(j: datetime) -> int:
    return int(j.timestamp()) * 1000


def ecrire(racine: pathlib.Path, dossier: str, j: datetime, lignes: list[dict],
           suffixe: str = "") -> pathlib.Path:
    """Ecrit une archive ndjson.gz a l'endroit exact ou la chaine la met."""
    d = racine / dossier / f"{j:%Y/%m}"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{dossier}_{j:%Y-%m-%d}{suffixe}.ndjson.gz"
    with gzip.open(p, "wt", encoding="utf-8") as f:
        for ligne in lignes:
            f.write(json.dumps(ligne) + "\n")
    # Le jumeau `.r2ok` que la chaine depose a cote : il ne doit JAMAIS
    # etre lu comme une archive.
    (d / (p.name + ".r2ok")).write_text("ok\n", encoding="utf-8")
    return p


def obs_ligne(station: str, j: datetime, source: str = "pioupiou",
              pas_s: int = 300, n: int = 288,
              vitesse=10.0, direction=180.0) -> dict:
    t0 = int(j.timestamp())
    return {
        "station_id": station, "source": source, "lat": 45.0, "lon": 6.0,
        "t": [t0 + i * pas_s for i in range(n)],
        "speed": [vitesse(i) if callable(vitesse) else vitesse
                  for i in range(n)],
        "dir": [direction(i) if callable(direction) else direction
                for i in range(n)],
    }


def fcst_ligne(station: str, j: datetime, model: str = "m1",
               source: str = "pioupiou", pas_s: int = 3600, n: int = 24,
               vitesse=10.0, direction=180.0, **extra) -> dict:
    t0 = int(j.timestamp())
    r = {
        "station_id": station, "source": source, "lat": 45.0, "lon": 6.0,
        "model": model, "fetched_at": j.isoformat(),
        "t0": t0, "step_s": pas_s,
        "speed": [vitesse(i) if callable(vitesse) else vitesse
                  for i in range(n)],
        "dir": [direction(i) if callable(direction) else direction
                for i in range(n)],
    }
    r.update(extra)
    return r


def test_erreur_connue():
    """L'erreur d'une balise-jour, calculee a la main."""
    J = jour("2026-08-20")
    with tempfile.TemporaryDirectory() as tmp:
        r = pathlib.Path(tmp)
        ecrire(r, "obs", J, [obs_ligne("A", J, vitesse=10.0, direction=180.0)])
        ecrire(r, "fcst", J, [
            fcst_ligne("A", J, model="parfait", vitesse=10.0, direction=180.0),
            fcst_ligne("A", J, model="cap+10", vitesse=10.0, direction=190.0),
            fcst_ligne("A", J, model="force+5", vitesse=15.0, direction=180.0),
            # Une heure sur deux parfaite, l'autre a +10 km/h : la
            # mediane dit 5, le RMS dit sqrt(50). Un RMS remplace par
            # une moyenne dirait 5 lui aussi — et la sensibilite aux
            # queues, qui est TOUT l'interet du RMS ici, disparaitrait
            # sans qu'un seul chiffre n'ait l'air anormal.
            fcst_ligne("A", J, model="queue",
                       vitesse=lambda i: 10.0 if i % 2 == 0 else 20.0,
                       direction=180.0),
        ])
        bj, bilan = O.balise_jours(r, J)
    parfait = bj[("pioupiou", "A", "parfait", 6)]
    cap = bj[("pioupiou", "A", "cap+10", 6)]
    force = bj[("pioupiou", "A", "force+5", 6)]
    verifie(parfait["n"] == 24 and parfait["med"] == 0.0
            and parfait["rms"] == 0.0,
            "prevision = observation → erreur nulle sur 24 heures")
    attendu = 2 * 10.0 * math.sin(math.radians(5.0))
    verifie(abs(cap["med"] - attendu) < 1e-9,
            f"10° de cap sur 10 km/h → 2·s·sin(θ/2) = {attendu:.6f} km/h "
            f"(erreur VECTORIELLE, pas |Δforce| = 0)")
    verifie(abs(force["med"] - 5.0) < 1e-9,
            "+5 km/h dans le bon cap → 5,000 km/h")
    queue = bj[("pioupiou", "A", "queue", 6)]
    verifie(abs(queue["med"] - 5.0) < 1e-9
            and abs(queue["rms"] - math.sqrt(50.0)) < 1e-9,
            f"une heure sur deux a +10 km/h → mediane 5,000 et RMS "
            f"{math.sqrt(50.0):.4f} : le RMS est bien une racine de "
            f"moyenne de CARRES, pas une moyenne d'erreurs")
    verifie(bilan["balises_obs"] == 1 and bilan["lignes_fcst"] == 4,
            "le bilan compte ce qu'il a lu, pas ce qu'il esperait")


def test_repli_scalaire_sous_le_seuil():
    """Sous 5 km/h la girouette est jetee : l'erreur redevient |Δforce|."""
    J = jour("2026-08-20")
    with tempfile.TemporaryDirectory() as tmp:
        r = pathlib.Path(tmp)
        ecrire(r, "obs", J, [obs_ligne("A", J, vitesse=3.0, direction=0.0)])
        ecrire(r, "fcst", J, [fcst_ligne("A", J, vitesse=4.0, direction=180.0)])
        bj, _ = O.balise_jours(r, J)
    v = bj[("pioupiou", "A", "m1", 6)]
    verifie(abs(v["med"] - 1.0) < 1e-9,
            "obs 3 km/h (sous le seuil) contre 4 km/h a 180° d'ecart → "
            "1,000 km/h et non 7,000 : le cap n'est pas note quand la "
            "girouette est du bruit")


def obs_par_heure(station: str, j: datetime, echantillons,
                  source: str = "pioupiou") -> dict:
    """Une archive d'observation batie HEURE PAR HEURE.

    `echantillons` : liste de `(decalage_s, vitesse, direction)` posee
    autour de CHAQUE heure ronde. Elle rend chaque fenetre d'agregation
    exactement identique — sans quoi l'heure 0, qui n'a pas de releve
    avant elle, fausserait la mediane et le banc mesurerait un effet de
    bord au lieu de la regle qu'il croit tenir.
    """
    t0 = int(j.timestamp())
    t, sp, di = [], [], []
    for h in range(24):
        for dec, v, d in echantillons:
            t.append(t0 + h * 3600 + dec)
            sp.append(v)
            di.append(d)
    return {"station_id": station, "source": source, "lat": 45.0, "lon": 6.0,
            "t": t, "speed": sp, "dir": di}


def test_direction_vectorielle():
    """350° et 10° font du NORD, jamais du sud."""
    J = jour("2026-08-20")
    with tempfile.TemporaryDirectory() as tmp:
        r = pathlib.Path(tmp)
        ecrire(r, "obs", J, [obs_par_heure("A", J, [
            (-600, 10.0, 350.0), (+600, 10.0, 10.0)])])
        ecrire(r, "fcst", J, [fcst_ligne("A", J, vitesse=10.0,
                                         direction=0.0)])
        bj, _ = O.balise_jours(r, J)
    v = bj[("pioupiou", "A", "m1", 6)]
    verifie(v["n"] == 24 and v["med"] < 1e-9,
            "cap observe = 0° (moyenne VECTORIELLE de 350° et 10°) → "
            "erreur nulle ; la moyenne arithmetique aurait dit 180°, "
            "donc 20 km/h d'erreur sur les 24 heures")


def test_le_faible_vent_porte_la_force_pas_le_cap():
    """Un releve sous 5 km/h compte dans la force, pas dans le vecteur."""
    J = jour("2026-08-20")
    with tempfile.TemporaryDirectory() as tmp:
        r = pathlib.Path(tmp)
        # Par heure : deux releves a 10 km/h plein nord, un a 1 km/h
        # plein sud. Force moyenne (10+10+1)/3 = 7 ; cap moyen 0°.
        ecrire(r, "obs", J, [obs_par_heure("A", J, [
            (-600, 10.0, 0.0), (0, 1.0, 180.0), (+600, 10.0, 0.0)])])
        ecrire(r, "fcst", J, [fcst_ligne("A", J, vitesse=7.0,
                                         direction=0.0)])
        bj, _ = O.balise_jours(r, J)
    v = bj[("pioupiou", "A", "m1", 6)]
    verifie(v["n"] == 24 and v["med"] < 1e-9,
            "force = moyenne de TOUS les releves (7,0), cap = moyenne "
            "vectorielle des seuls releves au-dessus de 5 km/h (0°) : "
            "un releve calme ne doit pas tirer le vecteur vers zero")


def test_fenetre_plancher_et_journee():
    """La fenetre d'agregation, le plancher d'heures, et la journee."""
    J = jour("2026-08-20")
    verifie(O.demi_fenetre_ms(3600) == 20 * 60 * 1000
            and O.demi_fenetre_ms(900) == 7 * 60 * 1000,
            "±20 min a l'heure ronde, ±7 min au quart d'heure "
            "(valeurs MESUREES au lot L11, pas une formule)")
    verifie(O.demi_fenetre_ms(1800) == 14 * 60 * 1000,
            "un pas inconnu est SERVI, plafonne par l'invariant "
            "2×demi < pas — jamais une exception qui ferait tomber la nuit")
    verifie(O.plancher_du_pas(3600) == 6 and O.plancher_du_pas(900) == 13
            and O.plancher_du_pas(1800) == 6,
            "plancher 6 a l'heure, 13 au quart d'heure, 6 par defaut")

    with tempfile.TemporaryDirectory() as tmp:
        r = pathlib.Path(tmp)
        # Des releves sur les 5 premieres heures seulement : SOUS le
        # plancher, donc pas de balise-jour du tout.
        t0 = int(J.timestamp())
        ecrire(r, "obs", J, [{
            "station_id": "A", "source": "pioupiou", "lat": 45.0, "lon": 6.0,
            "t": [t0 + h * 3600 for h in range(5)],
            "speed": [10.0] * 5, "dir": [180.0] * 5}])
        ecrire(r, "fcst", J, [fcst_ligne("A", J)])
        bj, bilan = O.balise_jours(r, J)
        verifie(not bj and bilan["sous_plancher"] == 1,
                "5 heures appariees sur 24 → AUCUNE balise-jour, et le "
                "bilan dit pourquoi")

    with tempfile.TemporaryDirectory() as tmp:
        r = pathlib.Path(tmp)
        ecrire(r, "obs", J, [obs_ligne("A", J)])
        # 72 echeances a partir de J−1 00:00 : la serie deborde des
        # DEUX cotes de la journee notee, et seules les 24 heures de J
        # doivent compter. Une borne droite oubliee en ferait 48.
        ecrire(r, "fcst", J - timedelta(days=1), [fcst_ligne(
            "A", J, n=72, t0=int((J - timedelta(days=1)).timestamp()))])
        bj, _ = O.balise_jours(r, J)
        v = bj[("pioupiou", "A", "m1", 24)]
        verifie(v["n"] == 24,
                "une serie a cheval sur deux journees n'apporte que les "
                "echeances de la journee notee")
        verifie(("pioupiou", "A", "m1", 6) not in bj,
                "l'archive de J−1 porte l'echeance 24, pas 6 : l'oracle "
                "ne melange pas deux classes sous une seule cle")


def test_le_lead_declare_par_la_ligne_gagne():
    """Classes courte et au quart d'heure : la LIGNE declare son lead."""
    J = jour("2026-08-20")
    with tempfile.TemporaryDirectory() as tmp:
        r = pathlib.Path(tmp)
        ecrire(r, "obs", J, [obs_ligne("A", J)])
        ecrire(r, "fcstagrumecourt", J, [
            fcst_ligne("A", J, model="agrume_court_w1", lead_h=-1)])
        # Au quart d'heure : pas de 900 s, plancher 13, demi-fenetre ±7 min.
        ecrire(r, "fcstagrumequart", J, [
            fcst_ligne("A", J, model="agrume_quart_w1", pas_s=900, n=96,
                       lead_h=-3)])
        bj, _ = O.balise_jours(r, J)
    verifie(("pioupiou", "A", "agrume_court_w1", -1) in bj,
            "la classe courte garde son etiquette −1 et n'atterrit pas "
            "sous `lead_h = 6`")
    q = bj.get(("pioupiou", "A", "agrume_quart_w1", -3))
    verifie(q is not None and q["n"] == 96,
            "la classe au quart d'heure garde −3, et ses 96 echeances "
            "sont appariees avec la demi-fenetre de SON pas")


def test_deux_flux_qui_se_marchent_dessus_sont_comptes():
    """Deux archives qui rendent la meme cle primaire : c'est COMPTE."""
    J = jour("2026-08-20")
    with tempfile.TemporaryDirectory() as tmp:
        r = pathlib.Path(tmp)
        ecrire(r, "obs", J, [obs_ligne("A", J)])
        ecrire(r, "fcst", J, [fcst_ligne("A", J, model="m1")])
        ecrire(r, "fcstreduit", J, [fcst_ligne("A", J, model="m1",
                                               vitesse=20.0)])
        bj, bilan = O.balise_jours(r, J)
    verifie(bilan["cles_en_double"] == 1 and len(bj) == 1,
            "la chaine ecrirait deux lignes de meme cle primaire et "
            "l'upsert garderait la derniere : l'oracle fait pareil, et "
            "il le COMPTE — sinon le doublon ne se verrait nulle part")


# ══════════════════════════════════════════════════════════════════
#  ⭐ LE BANC DE PARITÉ — le seul qui prouve la TRANSCRIPTION
# ══════════════════════════════════════════════════════════════════
#
# ⛔ ET IL NE CONTREDIT PAS L'INDEPENDANCE, il la rend utilisable.
# L'independance qui compte est celle du CODE QUI TOURNE LA NUIT :
# `oracle_scoring.py` n'importe rien de la chaine, et son garde-fou le
# verifie. Ici, dans un BANC, on fait tourner les deux cotes sur les
# memes donnees forgees et on exige le meme nombre. Sans ce banc,
# l'oracle serait independant ET peut-etre faux — il crierait tous les
# mois pour une virgule mal recopiee, et on finirait par ne plus le
# lire, ce qui est la seule facon de perdre un oracle.

def _obs_deux_formes(echantillons):
    """Les memes releves, dans la forme de la chaine et dans celle de
    l'oracle."""
    ordonnes = sorted(echantillons, key=lambda e: e[0])
    import numpy as np
    t = np.asarray([e[0] * 1000 for e in ordonnes], dtype="int64")
    sp = np.asarray([O.nombre(e[1]) for e in ordonnes], dtype=float)
    di = np.asarray([O.nombre(e[2]) for e in ordonnes], dtype=float)
    return ordonnes, (t, sp, di)


def test_parite_avec_la_chaine():
    """L'oracle et `scoring.py` rendent le MEME nombre sur 200 tirages."""
    sys.path.insert(0, str(ICI.parent / "model-verif"))
    import scoring as S                                     # noqa: PLC0415

    J = jour("2026-08-20")
    t_jour = int(J.timestamp())
    debut_ms = t_jour * 1000
    rnd = random.Random(1789)
    ecarts_med, ecarts_rms, ecarts_n = 0, 0, 0
    compares = 0
    for _ in range(200):
        pas = rnd.choice([3600, 900, 1800])
        n_ech = 24 if pas == 3600 else (96 if pas == 900 else 48)
        # ── les releves : cadence irreguliere, trous, vents calmes ──
        ech = []
        t = t_jour - 1800
        while t < t_jour + 86400 + 1800:
            t += rnd.randint(120, 900)
            v = rnd.choice([None, 0.0, 1.5, 3.0, 4.9, 5.0, 7.0, 12.0, 30.0,
                            rnd.uniform(0, 40)])
            d = rnd.choice([None, 0.0, 10.0, 175.0, 350.0,
                            rnd.uniform(0, 360)])
            ech.append((t, v, d))
        ordonnes, obs_np = _obs_deux_formes(ech)
        obs_chaine = [S.ObsSample(t=e[0] * 1000, speed=e[1], dir=e[2])
                      for e in ordonnes]
        # ── la prevision ────────────────────────────────────────────
        sp = [rnd.choice([None, rnd.uniform(0, 45)]) for _ in range(n_ech)]
        di = [rnd.choice([None, rnd.uniform(0, 360)]) for _ in range(n_ech)]
        ligne = {"station_id": "A", "source": "pioupiou", "model": "m",
                 "t0": t_jour, "step_s": pas, "speed": sp, "dir": di,
                 "fetched_at": J.isoformat()}
        # ── cote chaine : exactement ce que fait `daily_rows` ────────
        times = [(t_jour + i * pas) * 1000 for i in range(len(sp))]
        idx = [i for i, tt in enumerate(times)
               if debut_ms <= tt < debut_ms + O.JOUR_MS]
        pairs = S.pair_series([times[i] for i in idx],
                              [sp[i] for i in idx],
                              [di[i] for i in idx],
                              obs_chaine, S.demi_fenetre(pas))
        err = S.series_error(pairs)
        # ── cote oracle ─────────────────────────────────────────────
        errs = O.erreurs_horaires(ligne, obs_np, debut_ms,
                                  O.demi_fenetre_ms(pas))
        compares += 1
        if len(errs) != err.n:
            ecarts_n += 1
            continue
        if not errs:
            continue
        import numpy as np
        med_o = float(np.median(np.asarray(errs)))
        rms_o = (math.sqrt(float((np.asarray(errs) ** 2).mean()))
                 if len(errs) >= 2 else None)
        if abs(med_o - err.med) > 1e-9:
            ecarts_med += 1
        if err.rms is not None and abs(rms_o - err.rms) > 1e-9:
            ecarts_rms += 1
    verifie(compares == 200 and ecarts_n == 0 and ecarts_med == 0
            and ecarts_rms == 0,
            f"⭐ PARITE sur {compares} series tirees au sort (3 pas, "
            f"releves irreguliers, trous, vents sous le seuil) : "
            f"{ecarts_n} desaccord(s) de population, {ecarts_med} de "
            f"mediane, {ecarts_rms} de RMS")


def test_parite_de_la_chaine_de_repli():
    """La chaine de repli de l'oracle est celle de `score.py`."""
    sys.path.insert(0, str(ICI.parent / "model-verif"))
    import score as SC                                      # noqa: PLC0415

    zones = [
        {"zone_id": "b1:vallee", "landform": "vallee", "basin_id": "b1",
         "massif_id": "m1"},
        {"zone_id": "m1:crete", "landform": "crete", "basin_id": None,
         "massif_id": "m1"},
        {"zone_id": "*:littoral", "landform": "littoral", "basin_id": None,
         "massif_id": None},
    ]
    desaccords = [z["zone_id"] for z in zones
                  if O.chaine_de_repli(z) != SC.fallback_chain(z)]
    verifie(not desaccords,
            f"⭐ PARITE de la chaine de repli sur trois formes de zone "
            f"(bassin, massif seul, ni l'un ni l'autre) — "
            f"desaccords : {desaccords or 'aucun'}")
    verifie(O.MIN_BALISES_CASE == SC.MIN_STATIONS_ZONE
            and O.FENETRE_GLISSANTE_J == SC.ROLLING_DAYS
            and O.VENT_MIN_DIR_KMH == SC.S.DIR_MIN_WIND_KMH
            and O.LEAD_PAR_OFFSET == SC.LEAD_BY_OFFSET,
            "⭐ PARITE des constantes transcrites (quorum, fenetre, "
            "seuil de girouette, classes d'echeance) : le jour ou l'une "
            "bouge dans la chaine, ce banc rougit AVANT que l'oracle ne "
            "crie en production")


# ══════════════════════════════════════════════════════════════════
#  LES CASES DU SCORE GLISSANT
# ══════════════════════════════════════════════════════════════════

def _zone(zid, forme="vallee", bassin="b1", massif="m1", **kw):
    z = {"zone_id": zid, "landform": forme, "basin_id": bassin,
         "massif_id": massif, "basin_uncertain": False,
         "position_suspecte": False, "doublon_de": None}
    z.update(kw)
    return z


def test_cases_quorum_et_exclusions():
    """Quorum de 3 balises, et les quatre exclusions de la chaine."""
    zones = {f"pioupiou:{i}": _zone("b1:vallee") for i in range(1, 5)}
    zones["pioupiou:2"]["doublon_de"] = "pioupiou:1"
    zones["pioupiou:3"]["basin_uncertain"] = True
    zones["pioupiou:4"]["position_suspecte"] = True
    par_jour = {"2026-08-20": {
        ("pioupiou", str(i), "m", 6): {"med": 1.0, "rms": 1.0, "n": 24}
        for i in range(1, 5)}}
    par_jour["2026-08-20"][("pioupiou", "9", "m", 6)] = {
        "med": 1.0, "rms": 1.0, "n": 24}          # zone inconnue
    cases, bilan = O.cases_glissantes(par_jour, zones,
                                      ["2026-08-20"])
    verifie(bilan == {"zone_inconnue": 1, "bassin_incertain": 1,
                      "position_suspecte": 1, "doublon": 1, "retenus": 1},
            "les quatre exclusions comptent CHACUNE ce qu'elle ecarte : "
            "zone inconnue, bassin incertain, position suspecte, doublon "
            "d'inscription (lot L17)")
    verifie(not cases,
            "une seule balise survit : sous le quorum de 3, la case "
            "n'existe pas — c'est ce quorum que les doublons "
            "fabriquaient")

    zones = {f"pioupiou:{i}": _zone("b1:vallee") for i in range(1, 4)}
    par_jour = {"2026-08-20": {
        ("pioupiou", str(i), "m", 6): {"med": float(i), "rms": 1.0, "n": 24}
        for i in range(1, 4)}}
    cases, _ = O.cases_glissantes(par_jour, zones, ["2026-08-20"])
    verifie(cases[("b1:vallee", "m", 6, "basin_landform")]["med"] == 2.0
            and cases[("*:*", "m", 6, "global")]["med"] == 2.0,
            "trois balises → la case existe a tous les echelons de la "
            "chaine de repli, et sa mediane est celle des balise-jours")


def test_mediane_groupee_et_non_moyenne_des_jours():
    """La mediane porte sur TOUS les balise-jours, pas jour par jour."""
    zones = {f"pioupiou:{i}": _zone("b1:vallee") for i in range(1, 4)}
    par_jour = {
        # Jour 1 : trois balise-jours a 1. Jour 2 : trois a 100.
        "2026-08-20": {("pioupiou", str(i), "m", 6):
                       {"med": 1.0, "rms": 1.0, "n": 24} for i in range(1, 4)},
        "2026-08-21": {("pioupiou", str(i), "m", 6):
                       {"med": 100.0, "rms": 1.0, "n": 24}
                       for i in range(1, 4)},
    }
    cases, _ = O.cases_glissantes(par_jour, zones,
                                  ["2026-08-20", "2026-08-21"])
    v = cases[("b1:vallee", "m", 6, "basin_landform")]
    verifie(v["med"] == 50.5 and v["occurrences"] == 6,
            "6 valeurs groupees → mediane 50,5 ; une moyenne des "
            "medianes du jour aurait dit 50,5 aussi, mais une mediane "
            "des medianes aurait dit 1 ou 100 selon le tri — c'est "
            "exactement le genre de faute qui ne rougit nulle part")

    # Le cas qui separe VRAIMENT les deux : 2 jours desequilibres.
    par_jour["2026-08-21"] = {
        ("pioupiou", str(i), "m", 6): {"med": 100.0, "rms": 1.0, "n": 24}
        for i in range(1, 4)}
    par_jour["2026-08-20"] = {
        ("pioupiou", str(i), "m", 6): {"med": 1.0, "rms": 1.0, "n": 24}
        for i in range(1, 3)}
    cases, _ = O.cases_glissantes(par_jour, zones,
                                  ["2026-08-20", "2026-08-21"])
    v = cases[("b1:vallee", "m", 6, "basin_landform")]
    verifie(v["occurrences"] == 5 and v["med"] == 100.0,
            "2 valeurs a 1 et 3 a 100 → mediane 100 : le jour le plus "
            "fourni PESE plus, et c'est la definition publiee")


# ══════════════════════════════════════════════════════════════════
#  LA CONFRONTATION
# ══════════════════════════════════════════════════════════════════

def test_confrontation_dans_les_deux_sens():
    """Un ecart est nomme ; une absence aussi, et dans le bon sens."""
    o = {
        ("2026-08-20", "pioupiou", "1", "m", 6): {"med": 5.0, "rms": 6.0,
                                                  "n": 24},
        ("2026-08-20", "pioupiou", "2", "m", 6): {"med": 5.0, "rms": 6.0,
                                                  "n": 24},
        ("2026-08-20", "pioupiou", "3", "m", 6): {"med": 5.0, "rms": 6.0,
                                                  "n": 24},
    }
    # La base arrive en TUPLES `(err_vec_med, err_vec_rms, n_hours)` :
    # la fenetre en compte plus de six cent mille, et garder les
    # dictionnaires JSON couterait un demi-gigaoctet pour trois nombres.
    b = {
        ("2026-08-20", "pioupiou", "1", "m", 6): (5.005, 6.0, 24),
        ("2026-08-20", "pioupiou", "2", "m", 6): (5.02, 6.5, 24),
        ("2026-08-20", "pioupiou", "9", "m", 6): (1.0, 1.0, 24),
    }
    r = O.confronter_balise_jours(o, b, 0.01)
    verifie(r["communs"] == 2 and len(r["ecarts_med"]) == 1
            and len(r["ecarts_rms"]) == 1,
            "0,005 km/h passe sous le seuil, 0,02 est nomme — et le RMS "
            "est confronte SEPAREMENT de la mediane")
    verifie([c[0][2] for c in r["oracle_seul"]] == ["3"]
            and [c[0][2] for c in r["base_seule"]] == ["9"],
            "⛔ les deux sens : « la base ne dit rien » et « la base "
            "publie ce que l'oracle ne retrouve pas » sont deux pannes "
            "differentes, et la premiere est la plus silencieuse")
    gros = {("2026-08-13", "pioupiou", str(i), "agrume", 6):
            {"med": 1.0, "rms": 1.0, "n": 24} for i in range(500)}
    gros[("2026-08-14", "pioupiou", "1", "arome_r2", 24)] = {
        "med": 1.0, "rms": 1.0, "n": 24}
    r2 = O.confronter_balise_jours(gros, {}, 0.01)
    verifie(O.resume_absences(r2["oracle_seul"])
            == [(("2026-08-13", "agrume", 6), 500),
                (("2026-08-14", "arome_r2", 24), 1)],
            "⛔ 501 absences se resument en DEUX lignes (journee, modele, "
            "echeance), triees par nombre : « 9 441 balise-jours "
            "manquants » n'est pas une question, « 2026-08-13 · agrume · "
            "lead 6 : 9 441 » en est une")
    verifie(O.confronter_balise_jours({}, {}, 0.01, r) is r
            and r["communs"] == 2,
            "la confrontation se FUSIONNE journee apres journee : c'est "
            "ce qui permet de relacher chaque journee au lieu de garder "
            "les 25 en memoire (lecon du lot LM)")
    verifie(abs(r["med_max"] - 0.02) < 1e-12,
            "l'ecart MAXIMAL est publie meme quand il passe sous le "
            "seuil : un rapport qui ne dit que « rien a signaler » ne "
            "permet pas de voir une derive s'installer")


# ══════════════════════════════════════════════════════════════════
#  LES GARDE-FOUS
# ══════════════════════════════════════════════════════════════════

def test_le_garde_fou_d_independance_mord():
    """Importer la chaine dans l'oracle doit l'EMPECHER de tourner."""
    O._verifier_independance({"json": None, "numpy": None})
    for interdit in ("scoring", "score", "inference", "murphy", "duel",
                     "collect"):
        try:
            O._verifier_independance({interdit: None})
        except SystemExit as e:
            verifie(interdit in str(e),
                    f"`import {interdit}` dans l'oracle → refus de "
                    f"demarrer, en nommant le module fautif")
        else:
            verifie(False, f"`import {interdit}` n'a PAS ete refuse — "
                           f"l'oracle comparerait la faute a elle-meme")


def test_l_invariant_de_la_demi_fenetre():
    """2×demi < pas, verifie a l'import et pas au premier appel."""
    for pas, demi in O.DEMI_FENETRE_MS.items():
        verifie(2 * demi < pas * 1000,
                f"pas {pas} s, demi-fenetre ±{demi // 60000} min : "
                f"deux echeances consecutives ne partagent aucun releve")
    verifie(O.SEUIL_ECART_KMH == 0.01,
            "le seuil de nommage vaut 0,01 km/h — deux ordres de "
            "grandeur sous le plancher de representativite le plus bas "
            "mesure au lot L6 (vallee, 1,76 km/h). Le relever ferait "
            "taire l'oracle sans que personne ne s'en apercoive")


def test_la_pagination_ne_peut_pas_tronquer_en_silence():
    """PAGE > plafond serveur = troncature invisible (defaut du 08/08)."""
    verifie(O.Base.PAGE <= O.Base.PLAFOND_SERVEUR,
            "PAGE (1 000) ne depasse pas le plafond serveur mesure : "
            "sinon la premiere page plafonnee passerait pour la fin de "
            "la table, et l'oracle confronterait une base tronquee sans "
            "que rien ne soit rouge")


def test_les_jumeaux_r2ok_ne_sont_pas_des_archives():
    """`.r2ok` et `.manifeste.json` ne doivent jamais etre ouverts."""
    J = jour("2026-08-20")
    with tempfile.TemporaryDirectory() as tmp:
        r = pathlib.Path(tmp)
        ecrire(r, "obs", J, [obs_ligne("A", J)])
        p = ecrire(r, "fcst", J, [fcst_ligne("A", J)])
        (p.parent / f"fcst_{J:%Y-%m-%d}.manifeste.json").write_text(
            '{"parties": 2}', encoding="utf-8")
        trouves = O.archives_du_jour(r, J, "fcst")
        verifie([x.name for x in trouves] == [p.name],
                "l'enumeration du disque ne garde que les `.ndjson.gz` : "
                "ni le jumeau `.r2ok`, ni le manifeste")
        verifie([x.name for x in O.archives_du_jour(r, J, "obs")]
                == [f"obs_{J:%Y-%m-%d}.ndjson.gz"],
                "les familles `obs` et `fcst` ne se melangent pas")


def test_une_partie_p2_est_lue():
    """Le flux `fcst/` est partitionne : la partie 2 compte."""
    J = jour("2026-08-20")
    with tempfile.TemporaryDirectory() as tmp:
        r = pathlib.Path(tmp)
        ecrire(r, "obs", J, [obs_ligne("A", J), obs_ligne("B", J)])
        ecrire(r, "fcst", J, [fcst_ligne("A", J, model="m1")])
        ecrire(r, "fcst", J, [fcst_ligne("B", J, model="m2")],
               suffixe="_p2")
        bj, bilan = O.balise_jours(r, J)
    verifie(("pioupiou", "B", "m2", 6) in bj and len(bilan["archives"]) == 2,
            "⛔ la partie 2 de `fcst/` est lue : l'ignorer noterait la "
            "journee sur sept modeles en moins SANS QUE RIEN NE LE DISE "
            "(le piege central du lot S0.6)")


def main() -> int:
    n = 0
    for nom, fn in list(globals().items()):
        if nom.startswith("test_") and callable(fn):
            titre = fn.__doc__.splitlines()[0] if fn.__doc__ else nom
            print(f"\n▶ {titre}")
            fn()
            n += 1
    print("\n" + "═" * 66)
    print(f"  {n} bancs executes")
    if ECHECS:
        print(f"❌ banc de l'oracle L12 : {len(ECHECS)} echec(s)")
        for e in ECHECS:
            print(f"   · {e}")
        return 1
    print("✅ banc de l'oracle L12 : tout est vert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
