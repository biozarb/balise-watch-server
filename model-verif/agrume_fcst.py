#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/agrume_fcst.py — AGRUME entre dans le scoring
#                                            (Lot I, 13/08/2026)
#
#  Un COLLECTEUR, pas un scoreur. Il lit le produit A d'AGRUME (les
#  colonnes verticales aux balises, archivées sur R2) et en écrit le
#  vent à 10 m dans une archive NDJSON gzip, au format EXACT que
#  `collect.py` produit pour les modèles Open-Meteo. `score.py` relit
#  ce flux à côté du sien et n'a rien à savoir d'AGRUME.
#
#  ⛔ POURQUOI CE FICHIER EST DANS `model-verif/` ET PAS DANS `agrume/`.
#  AGRUME est une ENTRÉE du module de scoring, pas un module qui se
#  score lui-même (`c16bb49` a déjà retiré de l'app les champs de score
#  qu'AGRUME déclarait sans les avoir). Et la frontière du §« Séparer
#  collecte et notation » tient : un bug de formule ne doit jamais
#  pouvoir corrompre une archive irremplaçable.
#
#  ⛔ CE QUE CE FLUX NE CONSOMME PAS : le quota Open-Meteo. Il lit R2.
#  C'est structurellement le seul modèle supplémentaire qui puisse
#  entrer sans qu'un autre sorte — la fenêtre horaire d'Open-Meteo est
#  prise à 93,3 % depuis le 09/08, et c'est elle qui a tué la nuit du
#  09/08. Un lecteur pressé refera le calcul du tableau du README et
#  conclura qu'il n'y a plus de place : il y en a, elle n'est pas là.
#
#  ═══ LES TROIS DÉCISIONS DE YANN, 13/08/2026 ═══
#
#  1. ⛔ **Lead +6 h SEUL.** `LEAD_BY_OFFSET = {0: 6, 1: 24, 2: 48}`
#     classe une ligne par l'écart en JOURS entre le fichier de
#     snapshot et la journée notée, et `MIN_HOURS_DAILY` vaut 6.
#     L'archive AGRUME s'arrête à +24 h : le run 00 Z de J ne touche la
#     journée J+1 que par l'heure 00 (1 paire appariable), le run 03 Z
#     par 4. Sous le plancher de 6, donc AUCUNE ligne. Le +24 h ne
#     manque pas par oubli : il s'auto-élimine, et le banc le prouve
#     (`test_lead_24_ne_sort_aucune_ligne`). On l'ÉCRIT plutôt que de
#     le laisser lire comme un trou de données.
#     ⚠️ La variante écartée : prendre pour chaque heure le run le plus
#     VIEUX qui l'atteint encore (leads 22-24 h, journée entière). Elle
#     marche, mais AGRUME serait alors ~10 h plus frais que les autres
#     sous le même intitulé « +24 h » — un avantage silencieux.
#
#  2. ⛔ **Maille 0,01°** (`c001`). C'est la maille la plus proche du
#     site (1,1 km contre 2,8) et l'analogue direct de
#     `meteofrance_arome_france_hd`. Le vent 10 m y vient des champs
#     DÉDIÉS `10u`/`10v` (paquet SP1), pas d'un niveau hauteur — u/v
#     n'existent qu'à partir de 20 m. `--maille 0025` reste possible
#     pour mesurer l'écart, il ne change pas le nom du modèle : à
#     n'utiliser qu'à la main, jamais dans le timer.
#
#  3. ⛔ **AGRUME seul.** AROME-PI est archivé à part
#     (`agrume/pi/colonnes/`, 24 runs/jour, 10 m servi et vérifié) et
#     pourra devenir une seconde entrée. Il n'est PAS dans ce flux.
#
#  ═══ CE QUE CE LOT MESURE VRAIMENT, ET CE QU'IL NE MESURE PAS ═══
#
#  ⚠️ Le vent 10 m du produit A, ce sont les champs `10u`/`10v`
#  d'AROME lus par NOTRE chaîne. `composite.py` exclut explicitement le
#  10 m du Δ AROME-PI (`NIVEAUX_DELTA` retire le niveau hors HP1 :
#  « rien ne dit que ce soit le même diagnostic — une question à
#  mesurer, pas à trancher »). Le score AGRUME sortira donc TRÈS PROCHE
#  de `meteofrance_arome_france_hd`, et c'est attendu : ce lot mesure
#  notre chaîne de lecture (GRIB, plus proche voisin, coordonnées de
#  balises) contre celle d'Open-Meteo, et pose les rails. Il ne dira
#  pas encore « AGRUME est meilleur ». Un écart LARGE entre les deux
#  serait un défaut de l'une des deux chaînes, pas une nouvelle.
#
#  ⚠️ `fetched_at` porte l'heure du RUN du modèle, pas l'heure d'un
#  appel d'API — AGRUME n'en fait pas. Conséquence sur la SEULE colonne
#  qui en dépend, `lead_exact_h` : celle d'AGRUME se compte depuis le
#  run, celle des modèles Open-Meteo depuis notre appel de 03:15. Pour
#  un même run 00 Z, AGRUME affichera ~2,6 h de PLUS. Les scores
#  eux-mêmes (`err_vec_*`, `mse_*`, `bias_*`) ne dépendent pas de
#  `fetched_at` : seule la colonne de diagnostic est asymétrique, et
#  elle est asymétrique DANS LE SENS DÉFAVORABLE à AGRUME.
#
#      python3 agrume_fcst.py                      # hier, run 00 Z
#      python3 agrume_fcst.py --day 2026-08-11
#      python3 agrume_fcst.py --day 2026-08-11 --dry-run
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone

# ⚠️ On APPEND `agrume/` au sys.path, on ne l'insère pas en tête : les
# deux paquets ont chacun un `sonde_r2.py`, et une insertion en tête
# ferait masquer celui de `model-verif/` dans tout processus qui
# importerait ce module. C'est aussi pourquoi on ne passe PAS par
# `agrume/sonder.py::depuis_r2`, qui fait `sys.path.insert(0, …)` à
# l'import : la clé et l'appel `Storage` tiennent en six lignes, le
# sys.path global est le vrai coût.
_ICI = pathlib.Path(__file__).resolve().parent
for _p in (_ICI.parent / "agrume", _ICI.parent / "tools"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

import numpy as np                                          # noqa: E402

from collect import temoin, upload_r2, write_ndjson_gz      # noqa: E402
from colonnes import Colonnes                               # noqa: E402
from profil import decorer_vent                             # noqa: E402
from score import fcst_agrume_key                           # noqa: E402

# ══════════════════════════════════════════════════════════════════
#  CONSTANTES
# ══════════════════════════════════════════════════════════════════

#: Le nom du modèle dans `model_verif_daily`. La colonne est du `text`
#: libre (seul CHECK : `not like '%\\_seamless'`), il n'y a ni enum ni
#: clé étrangère à migrer. Le libellé lisible vit dans
#: `src/lib/stationScore.ts::STATION_MODEL_LABELS`.
MODEL = "agrume"

#: ⛔ On ne note QUE les balises Pioupiou. Les 2 radiosondages de l'axe
#: (`RS-06610`, `RS-16064`) sont dans l'archive parce que le profil les
#: confronte au ballon — ils n'ont pas d'anémomètre au sol, et une
#: prévision de vent 10 m au-dessus d'une station de lâcher ne
#: s'apparie à rien.
SOURCE_NOTEE = "pioupiou"

#: Maille par défaut du vent 10 m (décision 2 ci-dessus).
MAILLE_DEFAUT = "001"

#: L'archive est horaire, et `t0`/`step_s` est le contrat de
#: `score.fcst_times_ms`.
STEP_S = 3600

#: ⛔ LES SEULS RUNS ADMIS COMME « SNAPSHOT DU JOUR », ET LA BORNE EST
#: LE POINT DE COMPARABILITÉ. Le run 00 Z couvre les 24 heures de la
#: journée à +0…+23 h (moyenne 11,5 h) ; le 03 Z en couvre 21 à
#: +0…+20 h. Un run de 15 Z couvrirait encore 9 heures — à +0…+8 h,
#: soit un avantage de fraîcheur de dix heures sur les autres modèles,
#: sous le même intitulé « +6 h ». On préfère une journée SANS ligne
#: AGRUME à une journée où AGRUME gagne par l'horaire.
RUNS_ADMIS = (0, 3)

#: Bucket R2 du produit A. ⚠️ CE N'EST PAS CELUI DU MODULE DE SCORING,
#: et ce n'est pas non plus « wind-grid » : `wind-grid` est le nom du
#: DOS SUPABASE (`bucket_env`), le bucket R2 réel s'appelle
#: `balise-watch-grids`. Le nom de variable et le défaut sont copiés
#: mot pour mot sur `agrume/run-ingest-pi.sh` (`AGRUME_R2_BUCKET`), qui
#: fait déjà exactement ce geste — deux noms pour une seule notion,
#: c'est ainsi qu'on écrit dans le mauvais bucket sans s'en apercevoir.
BUCKET_R2_ENV = "AGRUME_R2_BUCKET"
BUCKET_R2_DEFAUT = "balise-watch-grids"
BUCKET_SUPABASE_ENV = "AGRUME_BUCKET"
BUCKET_SUPABASE_DEFAUT = "wind-grid"
PREFIXE_COLONNES = "agrume/colonnes/"


class Abort(Exception):
    pass


# ══════════════════════════════════════════════════════════════════
#  LIRE LE PRODUIT A — et le piège des deux buckets
# ══════════════════════════════════════════════════════════════════

@contextlib.contextmanager
def bucket_r2(nom: str):
    """Force `R2_BUCKET` le temps de construire un `Storage`.

    ⛔ LE PIÈGE QUE CE BLOC EXISTE POUR ÉVITER, ET IL EST SILENCIEUX.
    `tools/storage.py` résout le bucket R2 par
    `os.environ.get("R2_BUCKET") or defaut` — `R2_BUCKET` PRIME sur le
    `bucket_env` passé en argument. Or `run.sh` exporte
    `R2_BUCKET=model-verif` pour les trois modes du module. Sans ce
    bloc, la lecture du produit A irait chercher
    `model-verif/agrume/colonnes/…` : une clé qui n'existe pas, donc un
    `None`, donc « run absent », donc zéro ligne AGRUME toutes les
    nuits — et rien ne s'allumerait, parce qu'un run absent est un cas
    NORMAL au démarrage.

    On restaure la valeur d'avant en sortant : l'envoi de l'archive,
    lui, doit repartir sur `model-verif`.
    """
    avant = os.environ.get("R2_BUCKET")
    os.environ["R2_BUCKET"] = nom
    try:
        yield nom
    finally:
        if avant is None:
            os.environ.pop("R2_BUCKET", None)
        else:
            os.environ["R2_BUCKET"] = avant


def lire_run(run: str, crier=print):
    """Rend `(Colonnes, manifeste)` d'un run du produit A, ou `None`.

    ⚠️ `None` veut dire « ce run n'a pas été publié », pas « erreur ».
    L'ingestion n'écrit un run que si les 8 paquets le couvrent : il
    manque des runs, c'est prévu, et un run manquant ne doit jamais se
    transformer en série de zéros.
    """
    from storage import Storage                              # noqa: PLC0415

    bucket = os.environ.get(BUCKET_R2_ENV) or BUCKET_R2_DEFAUT
    base = f"{PREFIXE_COLONNES}{run}"
    with bucket_r2(bucket):
        try:
            store = Storage("agrume-verif", BUCKET_SUPABASE_ENV,
                            BUCKET_SUPABASE_DEFAUT)
        except Exception as exc:                             # noqa: BLE001
            # ⚠️ Sans `STORAGE_BACKEND=r2`, `storage.py` retombe sur le
            # dos Supabase et lève sur des variables que ce job n'a
            # aucune raison d'avoir — le défaut du 03/08 sur le poller
            # Infoclimat, puis du 07/08 ici. `run.sh` impose la
            # variable ; à la main, on le DIT au lieu de rendre une
            # trace d'import.
            raise Abort(
                f"lecture du produit A impossible ({exc}) — ce job veut "
                f"STORAGE_BACKEND=r2 et les R2_* : passer par "
                f"`run.sh agrume`, ou sourcer ~/.balise-watch-r2.env") from exc
        crier(f"  lecture du produit A dans le bucket « {bucket} » : {base}")
        brut_man = store.get(f"{base}/manifest.json")
        if not brut_man:
            return None
        brut_npz = store.get(f"{base}/colonnes.npz")
        if not brut_npz:
            # Le manifeste sans les données : ce n'est pas « absent »,
            # c'est incohérent. On le DIT au lieu de le lire comme un
            # run manquant de plus.
            raise Abort(f"{base} : manifeste présent, colonnes.npz absent")
    man = json.loads(brut_man.decode("utf-8"))
    return Colonnes.lire_npz(io.BytesIO(brut_npz), man)


def runs_du_jour(day: datetime) -> list[str]:
    return [f"{day:%Y-%m-%d}T{h:02d}:00:00Z" for h in RUNS_ADMIS]


def choisir_run(day: datetime, crier=print):
    """Le premier run admis qui existe. Rend `(run, col, manifeste)`."""
    for run in runs_du_jour(day):
        lu = lire_run(run, crier=crier)
        if lu is not None:
            return run, lu[0], lu[1]
        crier(f"  run {run} : absent")
    return None, None, None


# ══════════════════════════════════════════════════════════════════
#  LE VENT 10 M → LES LIGNES D'ARCHIVE
# ══════════════════════════════════════════════════════════════════

def _u_v_10m(col, maille: str):
    """Les deux tableaux `(balise, échéance)` du vent 10 m, en float32.

    ⚠️ La conversion en float32 n'est pas cosmétique : les opérations
    numpy en float16 arrondissent là où on ne s'y attend pas, et
    `isfinite` sur un float16 se comporte bien mais tout ce qui suit,
    non. `profil.py` fait le même geste, pour la même raison.
    """
    if maille == "001":
        bloc, i_niv, i_par = col.c001, col.i_niveau_001, col.i_param_001
    elif maille == "0025":
        bloc, i_niv, i_par = col.c0025, col.i_niveau_0025, col.i_param_0025
    else:
        raise Abort(f"maille inconnue : {maille!r} (attendu 001 ou 0025)")
    j10 = i_niv[10]
    return (bloc[:, i_par["u"], j10, :].astype(np.float32),
            bloc[:, i_par["v"], j10, :].astype(np.float32))


def lignes(col, man: dict, maille: str = MAILLE_DEFAUT):
    """Une ligne d'archive par balise notable, au format de `collect.py`.

    ⛔ LES ÉCHÉANCES SE RANGENT PAR LEUR VALEUR, PAS PAR LEUR POSITION.
    `score.fcst_times_ms` reconstitue les heures par `t0 + i × step_s` :
    une série écrite dans l'ordre du tableau, sur un run dont les
    échéances ne seraient pas contiguës, décalerait TOUTES les heures
    d'après le trou — silencieusement, et du bon ordre de grandeur pour
    passer inaperçu. C'est exactement le défaut de dé-accumulation
    positionnelle trouvé à l'audit du 13/08. Ici : on alloue
    `max(échéances) + 1` cases et on pose chaque valeur à SON heure ;
    les trous restent `None`.
    """
    u10, v10 = _u_v_10m(col, maille)
    steps = [int(s) for s in col.steps]
    if not steps:
        return
    n = max(steps) + 1
    run_dt = datetime.strptime(man["run"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc)
    t0 = int(run_dt.timestamp())

    for k, b in enumerate(col.balises):
        if b.get("source") != SOURCE_NOTEE:
            continue
        speed: list[float | None] = [None] * n
        direction: list[float | None] = [None] * n
        for i, step in enumerate(steps):
            u, v = float(u10[k, i]), float(v10[k, i])
            if not (np.isfinite(u) and np.isfinite(v)):
                # ⛔ Une absence reste une absence. Un 0 serait une
                # valeur de vent parfaitement crédible, et le scoring
                # noterait « le modèle annonçait calme » sur une case
                # que le modèle n'a jamais remplie.
                continue
            p = decorer_vent({"u": u, "v": v})
            speed[step] = p["vitesseKmh"]
            direction[step] = p["directionDeg"]
        # Même règle que `collect.py` : une balise sans une seule valeur
        # ne rentre pas dans l'archive sous forme de nulls.
        if all(s is None for s in speed):
            continue
        yield {
            "station_id": str(b["id"]),
            "source": SOURCE_NOTEE,
            "lat": b.get("lat"), "lon": b.get("lon"),
            "model": MODEL,
            # L'heure du RUN, pas celle d'un appel d'API — cf. l'en-tête.
            "fetched_at": run_dt.isoformat(),
            "t0": t0, "step_s": STEP_S,
            "speed": speed, "dir": direction,
            # Deux champs de traçabilité que `score.py` ignore : sans
            # eux, l'archive ne dirait pas de quel run ni de quelle
            # maille elle sort, et le jour où l'on change l'un des deux
            # les séries d'avant et d'après seraient indistinguables.
            "agrume_run": man["run"],
            "agrume_maille": maille,
        }


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="/var/lib/bw-model-verif")
    ap.add_argument("--day", default=None,
                    help="journée à archiver (défaut : hier, comme score.py)")
    ap.add_argument("--maille", default=MAILLE_DEFAUT, choices=("001", "0025"),
                    help="⚠️ à la main seulement : le nom du modèle ne change "
                         "pas, deux mailles dans la même archive seraient "
                         "deux séries sous un seul nom")
    ap.add_argument("--run", default=None,
                    help="forcer un run précis (2026-08-13T00:00:00Z)")
    ap.add_argument("--dry-run", action="store_true",
                    help="tout lire, tout compter, n'écrire ni fichier ni R2")
    args = ap.parse_args()

    root = pathlib.Path(args.out)
    day = (datetime.strptime(args.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
           if args.day
           else datetime.now(timezone.utc) - timedelta(days=1)).replace(
               hour=0, minute=0, second=0, microsecond=0)
    print(f"▶ journée archivée : {day:%Y-%m-%d} — flux AGRUME, maille "
          f"0,{'01' if args.maille == '001' else '025'}°")

    try:
        if args.run:
            lu = lire_run(args.run)
            run, col, man = (args.run, lu[0], lu[1]) if lu else (None, None, None)
        else:
            run, col, man = choisir_run(day)
    except Abort as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if col is None:
        # ⚠️ Ce n'est pas une erreur : ni au démarrage, ni le jour où
        # l'ingestion a manqué ses 8 paquets. Mais ça se DIT, sinon une
        # journée sans AGRUME se lirait comme une journée où AGRUME
        # n'avait rien à dire.
        print(f"  aucun run admis pour {day:%Y-%m-%d} "
              f"({', '.join(runs_du_jour(day))}) — aucune ligne AGRUME "
              f"cette journée-là.")
        return 0

    rows = list(lignes(col, man, args.maille))
    n_pas = len(col.steps)
    horizon = max(int(s) for s in col.steps) if col.steps else 0
    n_axe = len(col.balises)
    print(f"  run retenu : {run} — {n_axe} points d'archive, "
          f"{n_pas} échéances (0 → {horizon} h)")
    print(f"  {len(rows)} balises {SOURCE_NOTEE} avec au moins une valeur "
          f"de vent 10 m")
    if not rows:
        print("❌ le run existe mais aucune balise n'a de vent 10 m — "
              "ce n'est pas un run vide, c'est un run cassé.", file=sys.stderr)
        return 1

    key = fcst_agrume_key(day)
    if args.dry_run:
        exemple = rows[0]
        n_val = sum(1 for s in exemple["speed"] if s is not None)
        print(f"  (dry-run) {key} — exemple : balise {exemple['station_id']}, "
              f"{n_val} heures servies sur {len(exemple['speed'])}")
        return 0

    path = root / key
    n = write_ndjson_gz(path, rows)
    ko = path.stat().st_size / 1024
    print(f"  écrit : {path} ({n} lignes, {ko:.1f} Ko)")

    if not upload_r2(path, key):
        # Même politique que `collect.py` : le local reste, le témoin
        # n'est pas posé, `rattraper()` réessaiera — et le run SORT EN
        # ERREUR plutôt que d'annoncer un succès sur une archive qui
        # n'existe que sur le disque d'une machine que personne ne
        # sauvegarde.
        print("❌ archive AGRUME non montée sur R2 (conservée localement)",
              file=sys.stderr)
        return 2
    print(f"  témoin posé : {temoin(path).name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
