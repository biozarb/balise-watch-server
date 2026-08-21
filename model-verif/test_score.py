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
               test_pression_appariement_stable_entre_echeances):
        fn()
    print(f"\n{OK} assertions vertes, {KO} rouges.")
    return 1 if KO else 0


if __name__ == "__main__":
    sys.exit(main())
