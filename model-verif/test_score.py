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

import math
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scoring as S      # noqa: E402
import score as J        # noqa: E402

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
    ]
    up = J.accumulator_updates(banded, zone_of, DAY, {})
    par_cle = {(u["zone_id"], u["metric"], u["band"]): u for u in up}

    fine = par_cle[("b1:valley", "errKmh", "strong")]
    check("la valeur intégrée est la MÉDIANE des balises de la zone (4 et 6 → 5)",
          fine["sum_wx"], 5.0)
    check("… avec un poids de 1 pour la première journée", fine["sum_w"], 1.0)

    check("un bassin indéterminé n'entre dans AUCUNE case",
          any(u["zone_id"].startswith("b2") for u in up), False)
    check("… et sa valeur aberrante ne contamine pas le réseau entier",
          par_cle[("*:*", "errKmh", "strong")]["sum_wx"], 5.0)

    check("les cinq échelons de repli sont alimentés d'un coup",
          sorted({u["zone_id"] for u in up}),
          ["*:*", "*:valley", "alpes-nord:*", "alpes-nord:valley", "b1:valley"])
    check("la case « toutes tranches » existe à côté des tranches",
          ("b1:valley", "errKmh", "all") in par_cle, True)
    check("… et la case « tous régimes » aussi",
          any(u["regime"] == "all" for u in up), True)

    # Idempotence : rejouer la même journée ne fait rien avancer.
    current = {}
    for u in up:
        current[(u["zone_id"], u["model"], u["lead_h"], u["regime"],
                 u["band"], u["metric"])] = S.Accumulator(
            sum_w=u["sum_w"], sum_wx=u["sum_wx"], sum_wx2=u["sum_wx2"],
            days=u["days"], last_day=DAY_MS)
    check("relancer le job sur la même journée n'avance aucun accumulateur",
          J.accumulator_updates(banded, zone_of, DAY, current), [])

    # Le lendemain, en revanche, avance bien.
    demain = DAY + timedelta(days=1)
    up2 = J.accumulator_updates(banded, zone_of, demain, current)
    f2 = {(u["zone_id"], u["metric"], u["band"]): u for u in up2}[
        ("b1:valley", "errKmh", "strong")]
    check("le lendemain, l'acquis décroît de 2^(-1/30) puis s'ajoute",
          round(f2["sum_w"], 6), round(2 ** (-1 / 30) + 1, 6))
    check("… et le compteur de journées avance de un", f2["days"], 2)


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


def test_score_par_regime():
    print("── score par régime, depuis la mémoire longue ──")
    accs = []
    for model, err, mse in (("icon_d2", 3.0, 9.0), ("gfs_global", 8.0, 64.0)):
        for metric, val in (("errKmh", err), ("mseModel", mse),
                            ("msePersist", 100.0)):
            accs.append({"zone_id": "b1:valley", "model": model, "lead_h": 24,
                         "regime": "fluxN", "band": "all", "metric": metric,
                         "sum_w": 20.0, "sum_wx": val * 20, "sum_wx2": 0.0,
                         "days": 20, "last_day": "2026-08-05"})
        # Une case par tranche existe aussi : elle ne doit PAS produire
        # de ligne de score, sinon la même zone serait publiée trois fois.
        accs.append({"zone_id": "b1:valley", "model": model, "lead_h": 24,
                     "regime": "fluxN", "band": "strong", "metric": "errKmh",
                     "sum_w": 20.0, "sum_wx": err * 20, "sum_wx2": 0.0,
                     "days": 20, "last_day": "2026-08-05"})
    # `model_zone` telle qu'elle est en base : c'est elle qui dit
    # l'échelon, et non la forme de l'identifiant.
    kind_of = {"b1:valley": "basin_landform",
               "alpes-nord:valley": "massif_landform",
               "alpes-nord:*": "massif", "*:valley": "landform",
               "*:*": "global"}
    rows = J.regime_scores(accs, DAY, kind_of)
    check("une ligne par modèle, pas une par tranche", len(rows), 2)
    check("l'échelon publié est celui de model_zone, pas un reniflage",
          {r["agg_level"] for r in rows}, {"basin_landform"})

    # ⚠️ LE CAS QUI MENTAIT. `alpes-nord:valley` ne commence pas par
    # `*:` et ne finit pas par `:*` : l'ancienne déduction le publiait
    # `basin_landform`, alors que sa ligne `model_zone` dit
    # `massif_landform` — et l'échelon 2 n'était donc JAMAIS atteignable
    # dans cette colonne.
    au_massif = [dict(a, zone_id="alpes-nord:valley") for a in accs]
    check("une zone de massif s'annonce massif_landform, pas basin_landform",
          {r["agg_level"] for r in J.regime_scores(au_massif, DAY, kind_of)},
          {"massif_landform"})
    # Une zone absente de model_zone est impossible (clé étrangère) ;
    # si elle survenait, on saute plutôt que d'inventer un échelon.
    check("zone inconnue de model_zone → aucune ligne publiée",
          J.regime_scores([dict(a, zone_id="b9:ridge") for a in accs],
                          DAY, kind_of), [])
    check("la fenêtre est bien celle du régime, pas les 15 jours",
          {r["window_kind"] for r in rows}, {"regime"})
    best = next(r for r in rows if r["model"] == "icon_d2")
    check("l'erreur typique du régime vient de l'accumulateur",
          best["typical_err_kmh"], 3.0)
    check("20 occurrences → le classement est permis", best["rank"], 1)
    check("… et « bat la persistance » se lit sur les deux MSE séparés",
          best["beats_persist"], True)

    # Trop peu d'occurrences : le classement se tait.
    rares = []
    for a in accs:
        b = dict(a)
        b["days"] = 3
        rares.append(b)
    rows2 = J.regime_scores(rares, DAY, kind_of)
    check("3 occurrences du régime → aucun rang, et la raison est dite",
          (all(r["rank"] is None for r in rows2), rows2[0]["rank_reason"]),
          (True, "insufficient"))


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


def main() -> int:
    for fn in (test_chaine_de_repli, test_lignes_de_zone,
               test_agregat_quotidien, test_accumulateurs,
               test_scores_de_zone, test_score_par_regime,
               test_familles_publiees, test_lecture_paginee):
        fn()
    print(f"\n{OK} assertions vertes, {KO} rouges.")
    return 1 if KO else 0


if __name__ == "__main__":
    sys.exit(main())
