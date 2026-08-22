#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/test_arome_fcst.py — le banc du producteur AROME/R2
#                                          (Lot S0.5, 22/08/2026)
#
#  Sans réseau, sans clé, sans base, sans numpy. Il ne vérifie pas que
#  le producteur « marche » : il vérifie les huit façons qu'il aurait
#  de casser EN SILENCE.
#
#      python3 test_arome_fcst.py
#
#  ═══ CHACUN DE CES BANCS A ÉTÉ REJOUÉ CONTRE UN CODE CASSÉ ═══
#  (la preuve qu'ils savent échouer — détail dans la note de session)
#
#  · échéances     → `speed[i]` au lieu de `speed[heure]`      → 2 h de décalage
#  · régime        → `aloft_speed` au lieu d'`arome_aloft_*`   → le régime des 570 change
#  · hors maille   → pas de `DIST_MAX_KM`                      → `geopair` sur du vent
#  · absence       → `0` au lieu de `None`                     → du calme inventé
#  · deux runs     → pas de contrôle de cohérence              → 3 h d'écart, la moitié des lignes
#  · run non admis → `RUNS_ADMIS` ignoré                       → AROME gagne par l'horaire
#  · lead 48       → flux lu au seul offset 0                  → le banc ne prouve plus rien
#  · classement    → `{modèle: 1}, "ok"` sur une case à un seul → « AROME est le meilleur ici »
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

import arome_fcst as A                                      # noqa: E402
import inference as I                                       # noqa: E402
import score as SC                                          # noqa: E402

ECHECS: list[str] = []


def verifie(condition, message):
    if condition:
        print(f"  ✅ {message}")
    else:
        print(f"  ❌ {message}")
        ECHECS.append(message)


# ══════════════════════════════════════════════════════════════════
#  FABRIQUE — une tuile minuscule, mais de la vraie classe
# ══════════════════════════════════════════════════════════════════

JOUR = datetime(2026, 8, 22, tzinfo=timezone.utc)

#: ⛔ LE PROFIL D'ÉCHÉANCES RÉEL DU RUN 00 Z, RELEVÉ LE 22/08 SUR R2.
#: `arome-wind/ingest.py::keep_step()` garde l'heure pleine le jour et
#: UNE SUR TROIS la nuit (fenêtre 22-04 UTC) : 42 échéances pour 52
#: heures d'horizon. Les heures 1, 2, 22, 23, 25, 26, 46, 47, 49, 50
#: MANQUENT. C'est ce profil-là que le banc rejoue, pas un pas horaire
#: régulier qui ne prouverait rien.
HEURES_00Z = ([0] + list(range(3, 22)) + [24] + list(range(27, 46))
              + [48, 51])

#: Deux balises dans la tuile 46_6, une pile sur un point de grille et
#: une entre quatre points ; plus une hors de toute tuile lue.
BALISES = [
    {"station_id": "70", "source": "pioupiou", "lat": 46.15, "lon": 6.19},
    {"station_id": "holfuy-918", "source": "windsmobi",
     "lat": 46.153, "lon": 6.194},
]


def _times(run: datetime, heures) -> list[str]:
    return [(run + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M")
            for h in heures]


def tuile(run: datetime, heures=None, kind="sol", tuile_xy=(46, 6),
          pas=0.01, n=40, speed=lambda h: 20, direction=lambda h: 270,
          trous=()):
    """Une tuile WindGrid au format exact d'`arome-wind/ingest.py`.

    `speed(h)`/`direction(h)` reçoivent l'ÉCHÉANCE, pas l'indice —
    c'est ainsi qu'on fabrique une série dont la valeur trahit sa
    position si le producteur range par indice.
    `trous` : les échéances où la tuile porte `null` (le NaN du GRIB).
    """
    heures = list(HEURES_00Z if heures is None else heures)
    tl, tn = tuile_xy
    pts = []
    for j in range(n):
        for i in range(n):
            lat = round(tl + j * pas, 3)
            lon = round(tn + i * pas, 3)
            pts.append({
                "lat": lat, "lon": lon,
                "speed": [None if h in trous else speed(h) for h in heures],
                "dir": [None if h in trous else direction(h) for h in heures]})
    return json.dumps({
        "model": "meteofrance_seamless", "kind": kind,
        "level": None if kind == "sol" else A.ALOFT_HPA,
        "tileLat": tl, "tileLon": tn, "times": _times(run, heures),
        "points": pts, "fetchedAt": 1787376859374}).encode()


class Store:
    """Le `Storage` minimal que `collecter()` consomme : un `.get(clé)`.

    ⚠️ Il RETIENT les clés demandées. Une lecture de trop, c'est une
    opération classe B de trop toutes les nuits — et le banc est le seul
    endroit où ça se voit avant la facture.
    """

    def __init__(self, objets: dict):
        self.objets = objets
        self.demandes: list[str] = []

    def get(self, cle):
        self.demandes.append(cle)
        return self.objets.get(cle)


def store_simple(run=JOUR, alt=True, alt_speed=2, **kw):
    """Le magasin d'une nuit ordinaire : la tuile `sol` 46_6 et, si
    `alt`, sa jumelle `alt/850` au pas de 0,05° (la maille réelle des
    niveaux de pression — `arome-wind/ingest.py::STEP_ALT`)."""
    objets = {f"{A.PREFIXE_SOL}46_6.json": tuile(run, **kw)}
    if alt:
        cle = A.PREFIXE_ALT.format(niveau=A.ALOFT_HPA) + "46_6.json"
        objets[cle] = tuile(run, kind="alt", pas=0.05, n=40,
                            speed=lambda h: alt_speed,
                            direction=lambda h: 270,
                            heures=kw.get("heures"))
    return Store(objets)


# ══════════════════════════════════════════════════════════════════
#  1. LES ÉCHÉANCES SE RANGENT PAR LEUR VALEUR, PAS PAR LEUR POSITION
# ══════════════════════════════════════════════════════════════════

def test_echeances_non_contigues():
    """⛔ LE DÉFAUT LE PLUS COÛTEUX DU LOT, ET IL NE LÈVE RIEN.

    Le profil `keep_step()` retire dix heures sur cinquante-deux. Une
    série écrite dans l'ORDRE DU TABLEAU décale TOUTES les heures
    d'après le premier trou — silencieusement, et du bon ordre de
    grandeur pour passer inaperçu (`score.fcst_times_ms` reconstitue par
    `t0 + i × step_s`). C'est le défaut de dé-accumulation positionnelle
    de l'audit du 13/08, sous un autre déguisement.
    """
    print("\n▶ 1. les échéances non contiguës, et le décalage silencieux")
    # La vitesse EST l'échéance : une valeur mal placée se dénonce.
    st = store_simple(speed=lambda h: h, direction=lambda h: 270)
    lignes, jrn = A.collecter(st, BALISES, JOUR, avec_aloft=False,
                              crier=lambda *_: None)
    verifie(len(lignes) == 2, f"deux lignes ({len(lignes)})")
    if not lignes:
        return
    sp = lignes[0]["speed"]
    verifie(len(sp) == 52,
            f"52 cases allouées (0 → 51 h), pas 42 ({len(sp)})")
    verifie(all(sp[h] == h for h in HEURES_00Z),
            "chaque valeur est à SON heure, pas à sa position dans le "
            "tableau de la tuile")
    manquantes = [h for h in range(52) if h not in HEURES_00Z]
    verifie(manquantes == [1, 2, 22, 23, 25, 26, 46, 47, 49, 50],
            f"le profil de nuit retire bien dix heures — {manquantes}")
    verifie(all(sp[h] is None for h in manquantes),
            "les trous restent `None` : une absence reste une absence")

    # Et la preuve que le banc sait échouer : rangées par indice, les
    # heures 3 et 4 porteraient 3 et 4 au lieu de 3 et 4… non : la
    # valeur de l'indice 1 (échéance 3) atterrirait en case 1.
    verifie(sp[1] is None and sp[3] == 3,
            "un rangement positionnel aurait mis l'échéance 3 en case 1 — "
            "elle est bien en case 3, et la case 1 est vide")


# ══════════════════════════════════════════════════════════════════
#  2. ⭐ LE RÉGIME DES 570 BALISES DÉJÀ NOTÉES NE BOUGE PAS
# ══════════════════════════════════════════════════════════════════

def _obs(speed_kmh=20.0, dir_deg=270.0, jour=JOUR):
    t, sp, di = [], [], []
    for h in range(24):
        for m in (0,):
            t.append(int((jour + timedelta(hours=h, minutes=m)).timestamp()))
            sp.append(speed_kmh)
            di.append(dir_deg)
    return {"source": "pioupiou", "station_id": "70",
            "t": t, "speed": sp, "dir": di}


def _ligne_ecmwf(jour=JOUR, aloft=45.0, aloft_dir=270.0):
    """La ligne de référence du régime, telle que `collect.py` l'écrit :
    `aloft_*` n'est posé QUE sur `REGIME_REF_MODEL`."""
    return {"station_id": "70", "source": "pioupiou", "lat": 46.15,
            "lon": 6.19, "model": "ecmwf_ifs025",
            "fetched_at": jour.isoformat(),
            "t0": int(jour.timestamp()), "step_s": 3600,
            "speed": [20.0] * 24, "dir": [270.0] * 24,
            "aloft_level": "850hPa",
            "aloft_speed": [aloft] * 24, "aloft_dir": [aloft_dir] * 24}


def test_aloft_ne_vole_pas_le_regime():
    """⛔ LA PROPRIÉTÉ QUI TIENT LA DÉCISION 2 DU LOT, ET ELLE EST
    INVISIBLE À LA LECTURE.

    `daily_rows` choisit la référence d'altitude ainsi :

        for row in snapshots.get(0, []):
            if "aloft_speed" in row:
                ref_by_st[clé] = row

    — LE DERNIER GAGNE, et `snapshot_rows` lit `fcst` d'abord, le flux
    AROME/R2 en dernier. Sous le nom `aloft_speed`, nos lignes
    voleraient donc le régime des 570 balises Pioupiou à
    `ecmwf_ifs025` (`collect.REGIME_REF_MODEL`), en silence, sur 13 795
    lignes par nuit — alors que `day_regime` dit en toutes lettres
    « un seul modèle de référence, le même pour tout le monde ».

    ⭐ Le banc n'affirme pas « le champ s'appelle autrement » : il
    mesure que L'AJOUT DU FLUX NE CHANGE PAS LE RÉGIME. C'est la seule
    formulation qui reste vraie si quelqu'un renomme quelque chose.
    """
    print("\n▶ 2. ajouter le flux AROME/R2 ne change PAS le régime des "
          "balises déjà notées")
    st = store_simple()
    lignes, _ = A.collecter(st, BALISES, JOUR, avec_aloft=True,
                            crier=lambda *_: None)
    arome = [r for r in lignes if r["station_id"] == "70"]
    verifie(len(arome) == 1, "une ligne AROME/R2 pour la balise 70")
    if not arome:
        return

    verifie(not any(k.startswith("aloft_") for k in arome[0]),
            f"aucune clé `aloft_*` sur la ligne AROME/R2 — "
            f"{[k for k in arome[0] if 'aloft' in k]}")

    obs = _obs()
    ecmwf = _ligne_ecmwf(aloft=45.0)      # du flux net à 850 hPa
    avant, _ = SC.daily_rows(JOUR, {0: [ecmwf], 1: [], 2: []},
                             [obs], [], 7200)
    apres, _ = SC.daily_rows(JOUR, {0: [ecmwf] + arome, 1: [], 2: []},
                             [obs], [], 7200)
    r_avant = {r["model"]: r["regime"] for r in avant}
    r_apres = {r["model"]: r["regime"] for r in apres}
    verifie(r_avant.get("ecmwf_ifs025") == r_apres.get("ecmwf_ifs025"),
            f"le régime d'`ecmwf_ifs025` est le même avant et après "
            f"({r_avant.get('ecmwf_ifs025')} → {r_apres.get('ecmwf_ifs025')})")
    verifie(r_apres.get(A.MODEL) == r_apres.get("ecmwf_ifs025"),
            f"… et la ligne AROME/R2 hérite du MÊME régime, pas du sien "
            f"({r_apres.get(A.MODEL)})")

    # ⚠️ Et la preuve que le banc sait échouer : si le champ s'appelait
    # `aloft_speed`, le régime viendrait d'un vent d'altitude DIFFÉRENT.
    triche = dict(arome[0])
    triche["aloft_speed"] = [2.0] * 52      # calme à 850 hPa
    triche["aloft_dir"] = [270.0] * 52
    triche["aloft_level"] = "850hPa"
    triché, _ = SC.daily_rows(JOUR, {0: [ecmwf, triche], 1: [], 2: []},
                              [obs], [], 7200)
    r_triche = {r["model"]: r["regime"] for r in triché}
    verifie(r_triche.get("ecmwf_ifs025") != r_apres.get("ecmwf_ifs025"),
            f"sous le nom `aloft_speed`, le régime d'`ecmwf_ifs025` "
            f"CHANGERAIT ({r_apres.get('ecmwf_ifs025')} → "
            f"{r_triche.get('ecmwf_ifs025')}) — c'est bien ce nom-là qui "
            f"tient la propriété, pas un hasard de fabrique")

    # La donnée est là, sous son nom à elle : arbitrage n°6 remis à plus
    # tard SANS avoir à rejouer une archive qui n'est pas rejouable.
    verifie(arome[0].get("arome_aloft_level") == A.ALOFT_LEVEL
            and len(arome[0].get("arome_aloft_speed") or []) == 52,
            "`arome_aloft_*` est écrit dès la première nuit, sur le même "
            "axe horaire que `speed` — les tuiles étant réécrites toutes "
            "les 3 h, ne pas l'écrire serait irrattrapable")


# ══════════════════════════════════════════════════════════════════
#  3. HORS DE SA MAILLE, UNE BALISE SORT — ON NE RATTRAPE RIEN
# ══════════════════════════════════════════════════════════════════

def test_hors_maille_sort_et_se_compte():
    """⛔ LA BORNE DU §3.2 DU LOT S1, TENUE PAR UN NOMBRE.

    Tout ce lot repose sur « on lit le modèle À LA COORDONNÉE DE LA
    BALISE ». Si une balise sans point de grille proche recevait quand
    même le vent du point le moins loin, ce serait `geopair` sur du
    vent — l'appariement que le S1 interdit, et pour une bonne raison :
    le désaccord des deux SITES entrerait dans l'erreur du modèle.
    """
    print("\n▶ 3. hors de sa maille, une balise sort (et se compte)")
    loin = [{"station_id": "loin", "source": "windsmobi",
             "lat": 46.15, "lon": 6.19},
            # Dans la tuile 46_6, mais la fabrique ne couvre que
            # 46,00-46,39 / 6,00-6,39 : celle-ci est à ~60 km du bord.
            {"station_id": "tres-loin", "source": "windsmobi",
             "lat": 46.15, "lon": 7.00}]
    st = store_simple()
    lignes, jrn = A.collecter(st, loin, JOUR, avec_aloft=False,
                              crier=lambda *_: None)
    ids = sorted(r["station_id"] for r in lignes)
    verifie(ids == ["loin"],
            f"seule la balise dans la maille sort — {ids}")
    verifie(jrn["hors_grille"] == 1,
            f"et l'autre est COMPTÉE, pas oubliée ({jrn['hors_grille']})")
    verifie(max(jrn["distances"]) <= A.DIST_MAX_KM,
            f"toutes les distances retenues sont sous "
            f"{A.DIST_MAX_KM} km (max {max(jrn['distances']):.2f})")
    verifie(lignes[0]["arome_dist_km"] < 0.7,
            f"la distance est PUBLIÉE sur la ligne "
            f"({lignes[0]['arome_dist_km']} km) — la preuve, nuit après "
            f"nuit, qu'on lit la maille de la balise")

    # Une tuile qui n'existe pas emporte ses balises, et le dit.
    ailleurs = [{"station_id": "x", "source": "mf", "lat": 42.5, "lon": 0.5}]
    st2 = store_simple()
    l2, j2 = A.collecter(st2, ailleurs, JOUR, avec_aloft=False,
                         crier=lambda *_: None)
    verifie(not l2 and j2["tuiles_absentes"] == ["42_0"]
            and j2["hors_grille"] == 1,
            f"une tuile absente est NOMMÉE et ses balises comptées — "
            f"{j2['tuiles_absentes']}, {j2['hors_grille']} hors grille")


# ══════════════════════════════════════════════════════════════════
#  4. UNE ABSENCE RESTE UNE ABSENCE
# ══════════════════════════════════════════════════════════════════

def test_absence_reste_absence():
    print("\n▶ 4. un `null` de tuile ne devient pas un calme plat")
    st = store_simple(trous=tuple(range(3, 22)))   # tout le jour manque
    lignes, jrn = A.collecter(st, BALISES, JOUR, avec_aloft=False,
                              crier=lambda *_: None)
    verifie(len(lignes) == 2, "les lignes existent encore (nuit servie)")
    if lignes:
        sp = lignes[0]["speed"]
        verifie(all(sp[h] is None for h in range(3, 22)),
                "les heures creuses sont `None`, pas 0 — un 0 serait un "
                "vent calme parfaitement crédible, et le scoring noterait "
                "« le modèle annonçait calme »")
        verifie(sp[0] == 20 and sp[24] == 20,
                "et les heures servies le sont toujours")

    # Une balise dont AUCUNE heure n'est servie ne rentre pas du tout.
    st2 = store_simple(trous=tuple(HEURES_00Z))
    l2, j2 = A.collecter(st2, BALISES, JOUR, avec_aloft=False,
                         crier=lambda *_: None)
    verifie(not l2 and j2["sans_valeur"] == 2,
            f"une balise sans une seule valeur ne rentre pas sous forme "
            f"de nulls, et se compte ({j2['sans_valeur']})")


# ══════════════════════════════════════════════════════════════════
#  5. DEUX RUNS DANS LA MÊME ARCHIVE : JAMAIS
# ══════════════════════════════════════════════════════════════════

def test_tuiles_de_deux_runs():
    """⛔ LA FENÊTRE DE TÉLÉVERSEMENT, MESURÉE LE 22/08 : 8 MINUTES.

    `arome-wind/ingest.py` écrit les 63 tuiles `sol` (05:34:38 Z), puis
    les 441 tuiles `alt` (~8 min), puis le manifeste. Un job qui
    tomberait au milieu lirait des tuiles de DEUX runs — et daterait la
    moitié de ses lignes de trois heures trop tôt, sans une erreur.
    """
    print("\n▶ 5. deux runs dans la même archive : on s'arrête")
    # ⚠️ LES DEUX RUNS SONT ADMIS (03 Z pour la première tuile lue, 00 Z
    # pour la seconde) — exprès. Avec un run non admis, c'est le contrôle
    # `RUNS_ADMIS` qui lèverait, et ce banc-ci ne prouverait plus rien :
    # il resterait vert alors même que le contrôle de cohérence aurait
    # disparu. Mesuré : la mutation « elif False » passait inaperçue.
    st = Store({f"{A.PREFIXE_SOL}46_6.json": tuile(JOUR),
                f"{A.PREFIXE_SOL}44_6.json":
                    tuile(JOUR + timedelta(hours=3), tuile_xy=(44, 6))})
    bal = BALISES + [{"station_id": "sud", "source": "mf",
                      "lat": 44.15, "lon": 6.19}]
    try:
        A.collecter(st, bal, JOUR, avec_aloft=False, crier=lambda *_: None)
        verifie(False, "un mélange de deux runs doit lever `Abort`")
    except A.Abort as exc:
        verifie("mélangeant" in str(exc),
                f"`Abort` levé par le contrôle de COHÉRENCE (pas par "
                f"`RUNS_ADMIS`) — {str(exc)[:60]}…")

    # ⚠️ Le cas SOL neuve / ALT ancienne, lui, ne tue pas le run : on
    # écrit le vent sans l'altitude plutôt que de perdre la journée.
    st2 = Store({f"{A.PREFIXE_SOL}46_6.json": tuile(JOUR),
                 A.PREFIXE_ALT.format(niveau=A.ALOFT_HPA) + "46_6.json":
                     tuile(JOUR - timedelta(hours=3), kind="alt",
                           pas=0.05, n=40)})
    l2, j2 = A.collecter(st2, BALISES, JOUR, avec_aloft=True,
                         crier=lambda *_: None)
    verifie(len(l2) == 2 and j2["aloft_ecrit"] == 0,
            f"une tuile `alt` d'un autre run : le vent passe, "
            f"`arome_aloft_*` non ({len(l2)} lignes, "
            f"{j2['aloft_ecrit']} aloft)")


# ══════════════════════════════════════════════════════════════════
#  6. LES RUNS ADMIS — LA COMPARABILITÉ, PAS L'HORAIRE
# ══════════════════════════════════════════════════════════════════

def test_run_non_admis():
    print("\n▶ 6. un run de 15 Z n'entre pas, et la journée est DITE perdue")
    verifie(A.RUNS_ADMIS == (0, 3),
            "les runs admis sont bornés à 00 Z et 03 Z : un run de 15 Z "
            "couvrirait encore 9 heures de la journée à +0…+8 h, soit dix "
            "heures de fraîcheur d'avance sur les autres modèles sous le "
            "même intitulé « +6 h »")
    st = store_simple(run=JOUR + timedelta(hours=15))
    try:
        A.collecter(st, BALISES, JOUR, avec_aloft=False,
                    crier=lambda *_: None)
        verifie(False, "un run non admis doit lever `Abort`")
    except A.Abort as exc:
        verifie("perdue" in str(exc).lower(),
                "… et l'`Abort` dit que la journée est PERDUE, pas "
                "« réessayez » : les tuiles sont réécrites toutes les 3 h, "
                "il n'existe aucune archive des runs passés")

    # Le run 03 Z, lui, passe.
    st3 = store_simple(run=JOUR + timedelta(hours=3))
    l3, j3 = A.collecter(st3, BALISES, JOUR, avec_aloft=False,
                         crier=lambda *_: None)
    verifie(len(l3) == 2 and j3["run"].endswith("T03:00:00Z"),
            f"le run 03 Z est admis — {j3['run']}")


# ══════════════════════════════════════════════════════════════════
#  7. LE +48 H S'AUTO-ÉLIMINE — LA DONNÉE DÉCIDE, PAS UN `if`
# ══════════════════════════════════════════════════════════════════

def test_lead_48_ne_sort_aucune_ligne():
    """⛔ LA PROPRIÉTÉ QUI INTERDIT D'ÉCRIRE UN `if offset == 0`.

    Le run 00 Z de J−2 ne touche la journée notée que par 00:00 et
    03:00 — `keep_step()` ayant déjà retiré 01 h et 02 h de la nuit.
    DEUX paires, sous `MIN_HOURS_DAILY = 6`. Le +48 h ne manque pas par
    oubli : il s'auto-élimine, exactement comme le +24 h d'AGRUME. Le
    coder en dur ferait dépendre le comportement d'une constante lue
    ailleurs (`arome-wind::MAX_HOURS`) — et le jour où l'horizon
    bougerait, il faudrait penser à retirer la garde.
    """
    print("\n▶ 7. le +48 h ne sort pas, et c'est MESURÉ")
    obs = _obs(20.0, 270.0)

    # Les trois snapshots : le run du jour, celui de J−1, celui de J−2.
    def _run(delta_j):
        s = store_simple(run=JOUR - timedelta(days=delta_j))
        li, _ = A.collecter(s, [BALISES[0]], JOUR - timedelta(days=delta_j),
                            avec_aloft=False, crier=lambda *_: None)
        return li

    j0, j1, j2 = _run(0), _run(1), _run(2)
    rows, _ = SC.daily_rows(JOUR, {0: j0, 1: j1, 2: j2}, [obs], [], 7200)
    leads = sorted({r["lead_h"] for r in rows if r["model"] == A.MODEL})
    verifie(leads == [6, 24],
            f"AROME/R2 sort à +6 h et +24 h, jamais à +48 h — {leads}")

    # La raison, mesurée plutôt qu'affirmée.
    #
    # ⚠️ ET LA MESURE JUSTE N'EST PAS LE NOMBRE D'INSTANTS. `fcst_times_ms`
    # rend TOUT l'axe (`t0 + i × step_s`, 52 cases), trous compris : depuis
    # J−2, quatre instants tombent dans la journée notée — 48, 49, 50, 51 h.
    # Mais 49 h et 50 h sont des trous du profil de nuit (`keep_step`), donc
    # `pair_series` n'en fait rien. Ce qui compte, ce sont les heures
    # SERVIES, et il y en a deux : 00:00 et 03:00.
    jour_ms = int(JOUR.timestamp()) * 1000

    def _servies(ligne):
        t = SC.fcst_times_ms(ligne)
        sp = ligne["speed"]
        dedans = [i for i, x in enumerate(t)
                  if jour_ms <= x < jour_ms + SC.DAY_MS]
        return len(dedans), sum(1 for i in dedans if sp[i] is not None)

    n_inst, n_serv = _servies(j2[0])
    verifie(n_inst == 4 and n_serv == 2 and n_serv < SC.MIN_HOURS_DAILY,
            f"depuis J−2 : {n_inst} instants dans la journée, dont "
            f"{n_serv} SERVIS (00:00 et 03:00 — le profil de nuit a retiré "
            f"01 h et 02 h), plancher à {SC.MIN_HOURS_DAILY}. L'horizon "
            f"décide, pas une garde écrite à la main")
    n_inst1, n_serv1 = _servies(j1[0])
    verifie(n_serv1 >= SC.MIN_HOURS_DAILY,
            f"… et depuis J−1 il en reste {n_serv1} sur {n_inst1}, largement "
            f"au-dessus — le banc ne passe pas au vert par aveuglement")


# ══════════════════════════════════════════════════════════════════
#  8. ⭐ UN SEUL MODÈLE DANS UNE CASE N'EST PAS « 1ᵉʳ »
# ══════════════════════════════════════════════════════════════════

def test_classement_un_seul_modele():
    """⛔ LE GARDE-FOU QUE CE LOT DOIT POSER, ET IL N'EXISTAIT PAS.

    `MIN_STATIONS_ZONE = 3` se compte PAR MODÈLE. Une case fine avec
    2 Pioupiou (neuf modèles) et 3 windsmobi (AROME/R2 seul) devient
    publiable POUR AROME et reste sous quorum pour les huit autres.
    `inference.rank_models` rendait alors `{modèle: 1}, "ok"` — et
    `rankReasonFr("ok")` s'affiche « un modèle se détache ». Un « 1ᵉʳ
    sur 1 » se lirait « AROME est le meilleur ici ».

    Mesuré le 22/08 : DEUX lignes sur 276 035 passaient par là
    aujourd'hui. Le flux AROME/R2 rend le cas structurel.
    """
    print("\n▶ 8. une case à un seul modèle n'est pas classée")
    lignes = [{"typical_err_kmh": 5.0, "occurrences": 20, "model": A.MODEL,
               "unit": f"u{i}"} for i in range(12)]
    rk, raison, _ = I.rank_models(
        [{"model": A.MODEL, "typical_err_kmh": 5.0, "occurrences": 20}],
        {A.MODEL: lignes})
    verifie(rk == {}, f"aucun rang attribué — {rk}")
    verifie(raison == "single_model",
            f"et la raison le DIT, elle n'est pas nulle — {raison}")

    # Deux modèles nettement séparés : le mécanisme marche toujours.
    a = [{"typical_err_kmh": 4.0, "occurrences": 20, "unit": f"u{i}",
          "lead_h": 6} for i in range(12)]
    b = [{"typical_err_kmh": 9.0, "occurrences": 20, "unit": f"u{i}",
          "lead_h": 6} for i in range(12)]
    rk2, raison2, _ = I.rank_models(
        [{"model": "A", "typical_err_kmh": 4.0, "occurrences": 20},
         {"model": "B", "typical_err_kmh": 9.0, "occurrences": 20}],
        {"A": a, "B": b})
    verifie(raison2 != "single_model",
            f"deux modèles : on retombe sur le test apparié — {raison2}")

    # ⚠️ ET L'ÉCRAN DOIT SAVOIR TRADUIRE LE MOTIF, sans quoi il
    # s'afficherait en anglais brut sous le tableau.
    # ⓘ `web/` n'est PAS déployé sur le VPS (rsync de `model-verif/` et
    # `tools/` seulement) : là-bas, cette vérification ne peut pas avoir
    # lieu. On le DIT plutôt que de la sauter en silence — un banc qui se
    # désactive tout seul est un banc qui ne dit plus rien.
    ts = pathlib.Path(__file__).resolve().parent.parent.parent \
        / "web" / "src" / "lib" / "modelScores.ts"
    if ts.exists():
        verifie("single_model" in ts.read_text("utf-8"),
                "l'écran sait traduire `single_model` (RANK_REASON_FR)")
    else:
        print(f"  ⓘ {ts.name} absent de cette machine (VPS : `web/` n'y est "
              f"pas déployé) — la traduction de `single_model` reste à "
              f"vérifier sur le poste de développement, où ce banc la teste.")


# ══════════════════════════════════════════════════════════════════
#  9. LA CLÉ, LE COÛT, ET LE BOUT-À-BOUT SUR DISQUE
# ══════════════════════════════════════════════════════════════════

def test_cle_cout_et_bout_a_bout():
    print("\n▶ 9. la clé du flux, le coût des lectures, le tour complet")
    k = SC.fcst_arome_key(JOUR)
    verifie(k == "fcstarome/2026/08/fcstarome_2026-08-22.ndjson.gz",
            f"clé attendue — {k}")
    verifie(not k.startswith("fcst/") and not k.startswith("fcstagrume/"),
            "le flux AROME/R2 ne peut écraser ni l'archive Open-Meteo "
            "(irremplaçable) ni celle d'AGRUME")

    st = store_simple()
    lignes, jrn = A.collecter(st, BALISES, JOUR, crier=lambda *_: None)
    verifie(jrn["lectures"] == 2 and len(st.demandes) == 2,
            f"UNE tuile utile → deux lectures (sol + alt), pas une de plus "
            f"— {st.demandes}")
    verifie(jrn["tuiles_utiles"] == 1,
            "deux balises de la même tuile ne coûtent qu'une lecture — "
            "c'est pourquoi ajouter les 570 Pioupiou et les 278 aérodromes "
            "au flux ne coûte AUCUNE opération classe B de plus")

    with tempfile.TemporaryDirectory() as d:
        from collect import write_ndjson_gz                 # noqa: PLC0415
        path = pathlib.Path(d) / k
        n = write_ndjson_gz(path, lignes)
        relu = [json.loads(l) for l in
                gzip.decompress(path.read_bytes()).decode().splitlines()]
        verifie(n == len(lignes) == len(relu),
                f"{n} lignes écrites, {len(relu)} relues")
        par_score = SC.read_ndjson(pathlib.Path(d), k)
        verifie(len(par_score) == len(lignes)
                and par_score[0]["model"] == A.MODEL,
                "`score.read_ndjson` relit le flux sans rien savoir "
                "d'AROME/R2")

        # ⛔ LES TROIS FLUX SE LISENT ENSEMBLE. Si quelqu'un écrit un jour
        # `if offset == 0` autour de l'un d'eux, l'élimination du lead
        # cesse d'être une MESURE pour devenir une garde.
        write_ndjson_gz(pathlib.Path(d) / SC.fcst_key(JOUR),
                        [{"station_id": "70", "source": "pioupiou",
                          "model": "icon_d2", "fetched_at": JOUR.isoformat(),
                          "t0": int(JOUR.timestamp()), "step_s": 3600,
                          "speed": [12.0], "dir": [270.0]}])
        write_ndjson_gz(pathlib.Path(d) / SC.fcst_agrume_key(JOUR),
                        [{"station_id": "70", "source": "pioupiou",
                          "model": "agrume", "fetched_at": JOUR.isoformat(),
                          "t0": int(JOUR.timestamp()), "step_s": 3600,
                          "speed": [12.0], "dir": [270.0]}])
        modeles = sorted({r["model"]
                          for r in SC.snapshot_rows(pathlib.Path(d), JOUR)})
        verifie(modeles == sorted([A.MODEL, "agrume", "icon_d2"]),
                f"`snapshot_rows` rend les TROIS flux — {modeles}")

    verifie(not A.MODEL.endswith("_seamless"),
            "le nom du modèle ne finit pas par `_seamless` : le CHECK de "
            "`model_verif_daily.model` refuserait l'upsert ENTIER, et la "
            "tuile porte pourtant ce libellé (vestige, cf. BUGS.md)")
    verifie(A.MODEL != "meteofrance_arome_france_hd",
            "… et il est DISTINCT du modèle Open-Meteo : deux chaînes de "
            "lecture sous un seul nom feraient un modèle dont les lignes "
            "ne veulent pas dire la même chose selon la balise")


def main() -> int:
    print("═" * 66)
    print("  BANC DU PRODUCTEUR AROME/R2 — lot S0.5, 22/08/2026")
    print("═" * 66)
    test_echeances_non_contigues()
    test_aloft_ne_vole_pas_le_regime()
    test_hors_maille_sort_et_se_compte()
    test_absence_reste_absence()
    test_tuiles_de_deux_runs()
    test_run_non_admis()
    test_lead_48_ne_sort_aucune_ligne()
    test_classement_un_seul_modele()
    test_cle_cout_et_bout_a_bout()
    print("\n" + "═" * 66)
    if ECHECS:
        print(f"❌ {len(ECHECS)} assertion(s) en échec :")
        for e in ECHECS:
            print(f"   · {e}")
        return 1
    print("✅ banc du producteur AROME/R2 : tout est vert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
