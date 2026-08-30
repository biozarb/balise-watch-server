#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/agrume_court.py — LA CLASSE COURTE (cadre 2)
#                                            (Lot L10, 30/08/2026)
#
#  ⛔ CE QU'ELLE NOTE, EN UNE PHRASE : « ce que tu pouvais savoir à
#  l'instant T ». Deux instants de décision par jour, six heures rondes
#  après chacun, et le meilleur produit RÉELLEMENT disponible à T —
#  c'est-à-dire un AROME de la nuit rafraîchi par un AROME-PI de l'heure
#  d'avant. C'est le seul cadre où PI peut gagner : à échéance égale sa
#  qualité est mesurée nulle (+0,08 km/h, phase B), et tout son apport
#  est de la FRAÎCHEUR.
#
#  ═══ LES SEPT RÉPONSES DE YANN, 30/08/2026 — elles sont le lot ═══
#
#  Q1 · CADRE 2. Le cadre 1 est vide sous +4 h et sans intérêt au-dessus.
#  Q2 · Une NOUVELLE valeur de `lead_h` (`score.LEAD_COURT_*`), pas un
#       nouveau nom de modèle sous `lead_h = 6` — « un avantage
#       silencieux sous le même intitulé », refusé le 13/08.
#  Q3 · UN SEUL AGRUME publié : le composite (lot L18).
#  Q4 · DEUX instants T. ⛔ **Et pas ceux de la conception** — voir
#       ci-dessous, c'est la mesure qui les a déplacés.
#  Q5 · Fraîcheur du MODÈLE, pas de la chaîne. `fetched_at` porte donc
#       l'heure du RUN PI, jamais l'heure où nos octets ont été posés.
#  Q6 · Heures rondes en v1 ; le pas de 15 min est le lot L11.
#  Q7 · DEUX sous-séries, w = 1 et w = 0,5, toutes deux NOTÉES et
#       AUCUNE RANGÉE (`score.RANK_REASON_SERIE_EN_ESSAI`).
#
#  ═══ ⛔⛔ POURQUOI 06:50 ET 12:50, ET PAS 06:30 ET 12:30 ═══
#
#  La conception écrivait « p. ex. 06:30 et 12:30 Z ». C'était un
#  exemple ; la sonde du 30/08 (`sonde_instants_t_l10.py`, rapport dans
#  `amelioration scoring/agrume/`) l'a mesuré, et l'exemple ne tenait
#  pas :
#
#      T = 06:30 / 12:30  →  0 journée sur 6 atteint le plancher
#      T = 06:40 / 12:40  →  2 sur 6, puis 0 sur 6
#      T = 06:50 / 12:50  →  6 sur 6, matin ET après-midi
#
#  La cause est arithmétique et n'a rien d'un réglage : NOTRE archive
#  PI pose un run 0,7 h après son heure (médiane sur 20 jours ; max
#  1,5 h). À :30, le run PI le plus frais est donc celui de H−1, et sa
#  portée de six heures s'arrête UNE HEURE trop tôt pour couvrir les six
#  heures rondes qui suivent T. À :50, le run de l'heure H est posé
#  (≈ 42 min) et la fenêtre colle exactement.
#  ⓘ AROME, lui, couvre 6/6 dans tous les cas : ce n'est pas lui qui
#  décide, c'est PI — donc la classe elle-même.
#  ⚠️ Le jour où le retard PI dépasse 50 min (une fois sur vingt),
#  cette classe ne publie RIEN pour ce T. C'est le comportement voulu :
#  sous le plancher, on se tait.
#
#  ═══ ⛔ LE PIÈGE QUE CE FICHIER EXISTE POUR NE PAS COMMETTRE ═══
#
#  Choisir « le run le plus frais » SANS vérifier qu'il était publié à T
#  serait se noter avec de l'information du FUTUR. C'est la seule faute
#  qui rendrait tout le lot faux sans qu'aucun chiffre n'ait l'air
#  anormal : les erreurs baisseraient, la classe brillerait, et la
#  cause serait invisible. D'où `run_disponible()`, qui ne regarde pas
#  l'heure du run mais l'instant où NOS OCTETS ont été posés
#  (`LastModified` sur R2) — et le banc
#  `test_le_run_du_futur_est_refuse` qui échoue si on l'oublie.
#
#  Usage :
#      set -a; . ~/.balise-watch-r2.env; . ~/.balise-watch-agrume-r2.env; set +a
#      python3 model-verif/agrume_court.py [--day 2026-08-29] [--dry-run]
# ══════════════════════════════════════════════════════════════════════
from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys
from datetime import datetime, time, timedelta, timezone

_ICI = pathlib.Path(__file__).resolve().parent
for _p in (_ICI.parent / "agrume", _ICI.parent / "verif", _ICI.parent / "tools"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

from agrume_fcst import (BUCKET_R2_DEFAUT, BUCKET_R2_ENV,   # noqa: E402
                         MAILLE_DEFAUT, PREFIXE_COLONNES,
                         delta_20m, lignes, lire_run, lire_run_pi,
                         NIVEAU_DELTA_APPLIQUE, NIVEAU_DELTA_MESURE,
                         MAILLE_DELTA)
from collect import temoin, upload_r2, write_ndjson_gz      # noqa: E402
from r2_lecture import bucket_r2, prefixe_lecture           # noqa: E402
from score import (AGRUME_COURT_W05, AGRUME_COURT_W1,       # noqa: E402
                   LEAD_COURT_APREM, LEAD_COURT_MATIN,
                   fcst_agrume_court_key)
from storage import Abort                                   # noqa: E402

#: Le préfixe des colonnes PI. ⓘ `agrume_fcst` passe par
#: `pi.cles_du_run_colonnes` pour LIRE un run précis ; ici on doit
#: ÉNUMÉRER, ce que cette fonction ne fait pas. Le préfixe est donc
#: écrit une seconde fois — et le banc `test_prefixe_pi_coherent` le
#: confronte à ce que `cles_du_run_colonnes` produit, pour que les deux
#: ne puissent pas diverger en silence.
PREFIXE_PI = "agrume/pi/colonnes/"

#: ⛔ LES DEUX INSTANTS DE DÉCISION — mesurés, pas choisis. Voir l'en-tête.
T_MATIN = time(6, 50)
T_APREM = time(12, 50)
INSTANTS = ((T_MATIN, LEAD_COURT_MATIN), (T_APREM, LEAD_COURT_APREM))

#: Six heures rondes par instant T. ⛔ Ce n'est pas un réglage : PI ne
#: porte que six échéances. Au-delà, on servirait de l'AROME pur sous
#: une étiquette PI.
HEURES_CIBLES = 6

#: Les deux poids de Δ (décision Q7). Le nom de la série PORTE son
#: poids : une série dont le poids ne serait que dans un manifeste
#: deviendrait illisible le jour où l'on change d'avis.
POIDS = {AGRUME_COURT_W1: 1.0, AGRUME_COURT_W05: 0.5}

_RUN_RE = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}):00:00Z/manifest\.json$")


def heures_cibles(T: datetime) -> list[datetime]:
    """Les `HEURES_CIBLES` heures rondes STRICTEMENT APRÈS T.

    ⛔ « STRICTEMENT », ET C'EST TOUT LE CADRE 2. Une heure déjà
    commencée à T n'est pas une prévision, c'est un constat. L'inclure
    donnerait au dispositif un point qu'il n'a pas eu à prévoir, et le
    verdict du lot entier s'en trouverait flatté sans que rien ne le
    dise. Le cas limite compte : à T = 06:00 pile, l'heure 06 Z est
    ÉCARTÉE, pas gardée.
    """
    h0 = T.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    return [h0 + timedelta(hours=k) for k in range(HEURES_CIBLES)]


def _client_r2():
    """Un client S3 pour ÉNUMÉRER — `tools/storage.Storage` ne sait que
    `get`/`put`/`exists`, jamais lister.

    ⚠️ Mêmes identifiants et même endpoint que `storage._R2`, à
    l'intérieur du même `bucket_r2(...)` : le jeton ordinaire du VPS
    ÉCRIT sur `balise-watch-grids` sans pouvoir le LIRE (403 mesuré le
    13/08). Se tromper de jeu de variables ici rendrait « aucun run
    disponible », c'est-à-dire une classe silencieusement vide.
    """
    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise Abort("boto3 absent — `pip3 install boto3`") from exc
    for v in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
        if not os.environ.get(v):
            raise Abort(f"variable d'environnement {v} manquante")
    return boto3.client(
        "s3",
        endpoint_url="https://%s.r2.cloudflarestorage.com"
                     % os.environ["R2_ACCOUNT_ID"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=Config(retries={"max_attempts": 1, "mode": "standard"}))


def runs_poses(prefixe: str, depuis: datetime,
               client=None) -> dict[datetime, datetime]:
    """`{heure du run → instant où NOS octets ont été posés}`.

    ⭐ C'EST `LastModified`, ET C'EST TOUT LE LOT. `genere_le` date la
    dernière PASSE d'écriture — le filet de sécurité réécrit un
    manifeste à l'identique quelques heures plus tard, et il
    surestimait la latence de 2 h (§1.2 de la conception). Le
    `LastModified` de l'objet, lui, dit quand nos octets ont été posés,
    c'est-à-dire l'instant exact à partir duquel un lecteur aurait pu
    s'en servir. C'est la seule horloge qui réponde à la question du
    cadre 2.

    ⚠️ ON INDEXE `manifest.json`, PAS `colonnes.npz`. Le manifeste est
    écrit EN DERNIER (vérifié dans les deux préfixes : quelques
    centaines de millisecondes après le `.npz`), donc lui seul date le
    moment où la PAIRE devient lisible. Dater sur le `.npz` daterait un
    état incomplet — le piège que `_lire_paire_r2` nomme déjà côté
    lecture.
    """
    s3 = client or _client_r2()
    bucket = os.environ.get(BUCKET_R2_ENV) or BUCKET_R2_DEFAUT
    out: dict[datetime, datetime] = {}
    jeton = None
    while True:
        kw = {"Bucket": bucket, "Prefix": prefixe, "MaxKeys": 1000}
        if jeton:
            kw["ContinuationToken"] = jeton
        r = s3.list_objects_v2(**kw)
        for o in r.get("Contents", ()):
            m = _RUN_RE.search(o["Key"])
            if not m:
                continue
            run = datetime.strptime(m.group(1), "%Y-%m-%dT%H").replace(
                tzinfo=timezone.utc)
            if run >= depuis:
                out[run] = o["LastModified"]
        if not r.get("IsTruncated"):
            return out
        jeton = r.get("NextContinuationToken")


def run_disponible(runs: dict[datetime, datetime], T: datetime):
    """Le run le plus récent dont les octets étaient POSÉS à T.

    ⛔⛔ LA CONDITION EST SUR L'INSTANT DE POSE, JAMAIS SUR L'HEURE DU
    RUN. `run <= T` serait la formule naturelle, et elle est fausse :
    le run de 06 Z existe à 06:00 chez Météo-France, mais nos colonnes
    ne sont posées qu'à 06:42. Le retenir à 06:30 reviendrait à se
    noter avec un objet qu'on n'avait pas — de l'information du futur,
    invisible dans les chiffres, et qui ferait briller la classe.
    """
    dispo = [(run, pose) for run, pose in runs.items() if pose <= T]
    return max(dispo, key=lambda p: p[0]) if dispo else (None, None)


def restreindre(row: dict, steps: set[int]) -> int:
    """Ne garde que les `steps` visés ; rend le nombre d'heures servies.

    ⛔ POURQUOI ON DÉCOUPE ICI PLUTÔT QUE DANS `lignes()`. `lignes()`
    est le corps de boucle COMMUN aux trois séries (`agrume`,
    `agrume_pi`, et les deux d'ici) — c'est lui qui tient la convention
    de direction, celle qui a coûté 180° au lot I. On ne le paramètre
    pas une troisième fois : on lui laisse produire la journée entière,
    et on éteint ensuite ce qui n'appartient pas à la classe.
    ⚠️ « Éteindre » = poser `None`, jamais 0. Un 0 est une valeur de
    vent parfaitement crédible, et le scoring lirait « le modèle
    annonçait calme » sur une heure qu'il n'a jamais servie.
    """
    n = 0
    for i in range(len(row["speed"])):
        if i in steps and row["speed"][i] is not None:
            n += 1
        else:
            row["speed"][i] = None
            row["dir"][i] = None
    return n


def rows_du_jour(day: datetime, crier=print, client=None) -> list[dict]:
    """Les lignes d'archive de la classe courte pour la journée `day`."""
    with bucket_r2(os.environ.get(BUCKET_R2_ENV) or BUCKET_R2_DEFAUT,
                   prefixe_lecture()):
        s3 = client or _client_r2()
        depuis = day - timedelta(days=2)
        arome = runs_poses(PREFIXE_COLONNES, depuis, s3)
        pi = runs_poses(PREFIXE_PI, depuis, s3)
    crier(f"  runs connus sur R2 : {len(arome)} AROME, {len(pi)} PI "
          f"(depuis {depuis:%Y-%m-%d})")

    out: list[dict] = []
    for heure_t, lead in INSTANTS:
        T = datetime.combine(day.date(), heure_t, tzinfo=timezone.utc)
        r_a, pose_a = run_disponible(arome, T)
        r_p, pose_p = run_disponible(pi, T)
        if r_a is None or r_p is None:
            # ⚠️ PAS une erreur : l'archive R2 est purgée au bout d'une
            # semaine, et un rejeu plus ancien ne PEUT pas savoir ce qui
            # était disponible. Le dire, et ne rien écrire, est la seule
            # réponse honnête — inventer un run par une règle fixe
            # publierait une disponibilité qu'on n'a pas vérifiée.
            crier(f"  T={heure_t:%H:%M} Z — aucun run "
                  f"{'AROME' if r_a is None else 'PI'} posé à cet instant "
                  f"(archive purgée ou journée trop ancienne) : "
                  f"aucune ligne pour ce T.")
            continue
        decalage = int((r_p - r_a).total_seconds() // 3600)
        cibles = heures_cibles(T)
        steps = {int((h - r_a).total_seconds() // 3600) for h in cibles}
        crier(f"  T={heure_t:%H:%M} Z — AROME {r_a:%m-%d %HZ} (posé "
              f"{(pose_a - r_a).total_seconds() / 3600:.1f} h après) · "
              f"PI {r_p:%m-%d %HZ} (posé "
              f"{(pose_p - r_p).total_seconds() / 3600:.1f} h après) · "
              f"décalage {decalage:+d} h · cibles "
              f"{cibles[0]:%H}–{cibles[-1]:%H} Z")
        lu = lire_run(r_a.strftime("%Y-%m-%dT%H:%M:%SZ"), crier=crier)
        if lu is None:
            crier("    colonnes AROME illisibles — ce T est sauté.")
            continue
        col, man = lu
        lu_pi = lire_run_pi(r_p.strftime("%Y-%m-%dT%H:%M:%SZ"), crier=crier)
        if lu_pi is None:
            crier("    colonnes PI illisibles — ce T est sauté (une "
                  "classe courte sans PI serait de l'AROME sous un autre "
                  "nom).")
            continue
        pi_donnees, pi_man = lu_pi
        for model, w in POIDS.items():
            d = delta_20m(col, pi_donnees, pi_man, crier=lambda *a: None,
                          decalage_h=decalage, poids=w)
            n_lignes = n_heures = 0
            for row in lignes(col, man, MAILLE_DEFAUT, model=model, delta=d,
                              extra={"agrume_pi_run": pi_man["run"],
                                     "agrume_delta_mesure_m": NIVEAU_DELTA_MESURE,
                                     "agrume_delta_applique_m": NIVEAU_DELTA_APPLIQUE,
                                     "agrume_delta_maille": MAILLE_DELTA,
                                     "agrume_court_poids": w,
                                     "agrume_court_t": T.isoformat(),
                                     "agrume_court_decalage_h": decalage}):
                n = restreindre(row, steps)
                if n == 0:
                    continue
                # ⛔ L'ÉCHÉANCE EST PORTÉE PAR LA LIGNE (`score.daily_rows`
                # la lit). Sans elle, ces lignes seraient notées comme du
                # « +6 h » — la classe entière disparaîtrait dans une
                # autre, et personne ne verrait la différence.
                row["lead_h"] = lead
                # ⛔ Q5 — FRAÎCHEUR DU MODÈLE, PAS DE LA CHAÎNE.
                # `lignes()` pose l'heure du run AROME ; la classe courte
                # la remplace par celle du run PI, parce que le composite
                # N'EXISTAIT PAS avant ce run-là. `lead_exact_h` en
                # découle (~3,5 h) et décrit alors la fraîcheur du
                # MODÈLE. L'heure où NOS octets ont été posés — une heure
                # de plus, du temps de détection — n'entre nulle part :
                # c'est la nôtre, elle ne se crédite pas à PI.
                row["fetched_at"] = r_p.strftime("%Y-%m-%dT%H:%M:%S+00:00")
                # Le compte des heures corrigées, recompté APRÈS
                # découpe : celui de `lignes()` porte la journée entière.
                row["agrume_pi_heures"] = sum(
                    1 for s in steps if (d.get(_k_balise(col, row)) or {}).get(s))
                n_lignes += 1
                n_heures += n
                out.append(row)
            crier(f"    {model} : {n_lignes} balises, {n_heures} heures "
                  f"servies ({n_heures / max(1, n_lignes):.1f} par balise "
                  f"sur {HEURES_CIBLES})")
    return out


def _k_balise(col, row) -> int | None:
    """L'index de la balise de `row` dans l'axe du produit A.

    ⚠️ Par IDENTIFIANT, jamais par rang : `lignes()` saute les balises
    hors `SOURCE_NOTEE` et celles sans Δ, donc le rang d'une ligne dans
    la sortie n'est PAS son rang dans `col.balises`. S'y fier
    compterait les heures corrigées d'une autre balise.
    """
    for k, b in enumerate(col.balises):
        if str(b["id"]) == row["station_id"]:
            return k
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="/var/lib/bw-model-verif")
    ap.add_argument("--day", default=None,
                    help="journée notée (défaut : hier, comme score.py)")
    ap.add_argument("--dry-run", action="store_true",
                    help="tout lire, tout compter, n'écrire ni fichier ni R2")
    args = ap.parse_args()

    day = (datetime.strptime(args.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
           if args.day
           else datetime.now(timezone.utc) - timedelta(days=1)).replace(
               hour=0, minute=0, second=0, microsecond=0)
    print(f"▶ classe courte (cadre 2) — journée {day:%Y-%m-%d}, "
          f"T = {T_MATIN:%H:%M} et {T_APREM:%H:%M} Z")
    try:
        rows = rows_du_jour(day)
    except Abort as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if not rows:
        # ⚠️ Ce n'est pas une erreur : c'est ce qui arrive quand aucun
        # run n'était posé à T (retard PI au-delà de 50 min, une fois
        # sur vingt) ou quand la journée est plus vieille que la
        # rétention R2. Une classe qui se tait vaut mieux qu'une classe
        # qui devine.
        print("  aucune ligne pour cette journée — voir les motifs "
              "ci-dessus. Rien n'est écrit.")
        return 0

    key = fcst_agrume_court_key(day)
    if args.dry_run:
        print(f"  (dry-run) {key} — {len(rows)} lignes, non écrites")
        return 0
    path = pathlib.Path(args.out) / key
    n = write_ndjson_gz(path, rows)
    print(f"  écrit : {path} ({n} lignes, "
          f"{path.stat().st_size / 1024:.1f} Ko)")
    if not upload_r2(path, key):
        print("❌ archive de la classe courte non montée sur R2 "
              "(conservée localement)", file=sys.stderr)
        return 2
    print(f"  témoin posé : {temoin(path).name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
