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
import pathlib
import sys
import tempfile
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
    ]
    up = J.accumulator_updates(banded, zone_of, DAY, {})
    par_cle = {(u["zone_id"], u["metric"], u["band"]): u for u in up}

    fine = par_cle[("b1:valley", "errKmh", "strong")]
    check("la valeur intégrée est la MÉDIANE des balises de la zone (4 et 6 → 5)",
          fine["sum_wx"], 5.0)
    check("… avec un poids de 1 pour la première journée", fine["sum_w"], 1.0)

    check("un bassin indéterminé n'entre dans AUCUNE case",
          any(u["zone_id"].startswith("b2") for u in up), False)
    check("une position suspecte n'entre dans AUCUNE case",
          any(u["zone_id"].startswith("b3") for u in up), False)
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
        "rank_reason": "ok", "err_sd": 1.2, "n_days": 15,
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


def main() -> int:
    for fn in (test_chaine_de_repli, test_lignes_de_zone,
               test_agregat_quotidien, test_accumulateurs,
               test_scores_de_zone, test_score_par_regime,
               test_rétrécissement_vers_le_parent,
               test_rejeu_darchive,
               test_fenetre_de_maintien_adaptative,
               test_stabilite_des_rangs,
               test_familles_publiees, test_lecture_paginee,
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
               # ── lot S13.0 : le fichier léger + le résumé des manches ──
               test_light_scores_sous_ensemble_exact,
               test_light_scores_bout_en_bout_ne_recalcule_rien,
               test_light_bascules_resume,
               test_manches_demarre_au_deploiement_et_est_idempotent,
               test_manches_pas_de_rejeu_historique_sous_min_block_days):
        fn()
    print(f"\n{OK} assertions vertes, {KO} rouges.")
    return 1 if KO else 0


if __name__ == "__main__":
    sys.exit(main())
