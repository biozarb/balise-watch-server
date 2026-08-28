#!/usr/bin/env python3
"""
test_filet_arome_wind.py — banc du filet AROME wind, HORS-LIGNE.

    python3 model-verif/test_filet_arome_wind.py

⛔ CE QUE CE BANC PROTÈGE, ET CE N'EST PAS DU CODE.
Le filet est trivial : il POSTe. Ce qui peut être faux, ce sont les
TROIS ACCORDS qu'il suppose, et aucun des trois ne se voit à la lecture
d'un seul fichier :

 1. l'heure du timer doit tomber dans la plage où `pick_run()` ne peut
    choisir qu'un run ADMIS. Déplacer le timer « pour laisser de la
    marge » sortirait de la plage sans que rien ne proteste : le job
    partirait, GitHub répondrait 204, `run.sh` écrirait « OK », et la
    journée serait perdue quand même ;
 2. `RUNS_ADMIS` est dupliqué dans le filet (il refuse de charger
    `arome_fcst`, donc `boto3`, pour rester increvable). Le jour où
    `arome_fcst.RUNS_ADMIS` bouge, la copie doit hurler ;
 3. l'unité systemd appelle `run.sh filet-arome`. Si ce mode n'est pas
    déclaré dans `run.sh`, le job sort en code 2 tous les matins.

Ce banc lit donc les VRAIS fichiers — `arome_fcst.py`, le `.timer`,
`run.sh` — plutôt que de recopier ce qu'ils sont censés dire.

Aucun réseau : le déclencheur est injecté.
"""
from __future__ import annotations

import ast
import os
import re
import sys
from datetime import datetime, timezone

_ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _ICI)

import filet_arome_wind as F  # noqa: E402

echecs = []


def verifier(nom, condition, detail=""):
    if condition:
        print(f"  ✓ {nom}" + (f"   {detail}" if detail else ""))
    else:
        print(f"  ✗ {nom}" + (f"   {detail}" if detail else ""))
        echecs.append(nom)


def constante_source(chemin, nom):
    """Lit une constante littérale dans un fichier SANS l'importer.

    ⓘ `ast` et non `import` : importer `arome_fcst` tirerait boto3,
    `collect` et `r2_lecture`. Un banc qui ne tourne que là où la
    production tourne ne sert plus à rien le jour où l'on veut vérifier
    un accord depuis un poste nu.
    """
    arbre = ast.parse(open(chemin, encoding="utf-8").read())
    for n in ast.walk(arbre):
        if isinstance(n, ast.Assign):
            for c in n.targets:
                if isinstance(c, ast.Name) and c.id == nom:
                    return ast.literal_eval(n.value)
    raise AssertionError(f"{nom} introuvable dans {chemin}")


def heure_timer(chemin):
    """L'heure d'`OnCalendar` du timer, en heures UTC entières."""
    txt = open(chemin, encoding="utf-8").read()
    # Seules les lignes de directive comptent : les pavés de commentaire
    # de ce projet CITENT des horaires, et un `grep` naïf les prendrait.
    for ligne in txt.splitlines():
        ligne = ligne.strip()
        if ligne.startswith("OnCalendar="):
            m = re.search(r"(\d{2}):(\d{2}):(\d{2})", ligne)
            assert m, f"OnCalendar illisible : {ligne}"
            assert "UTC" in ligne, f"OnCalendar sans UTC : {ligne}"
            return int(m.group(1)), int(m.group(2))
    raise AssertionError(f"aucun OnCalendar dans {chemin}")


def main():
    racine = os.path.join(_ICI, os.pardir)
    timer = os.path.join(_ICI, "systemd", "bw-filet-arome.timer")
    service = os.path.join(_ICI, "systemd", "bw-filet-arome.service")

    print("\n── ⛔ Accord nº 1 : RUNS_ADMIS n'a pas divergé ──────────")
    vrai = tuple(constante_source(os.path.join(_ICI, "arome_fcst.py"),
                                  "RUNS_ADMIS"))
    verifier("la copie du filet est ÉGALE à arome_fcst.RUNS_ADMIS — "
             "c'est la seule chose qui autorise à la dupliquer",
             tuple(F.RUNS_ADMIS) == vrai,
             f"filet {tuple(F.RUNS_ADMIS)} vs arome_fcst {vrai}")

    print("\n── Les candidats que pick_run() examinera ───────────────")
    def a(h, m=0):
        return datetime(2026, 8, 28, h, m, tzinfo=timezone.utc)

    for h, attendu in ((0, (0, 21)), (2, (0, 21)), (3, (3, 0)),
                       (5, (3, 0)), (6, (6, 3)), (8, (6, 3)),
                       (23, (21, 18))):
        verifier(f"à {h:02d} Z → {attendu[0]:02d} Z puis {attendu[1]:02d} Z",
                 F.runs_candidats(a(h)) == attendu,
                 str(F.runs_candidats(a(h))))
    verifier("⛔ le rebouclage de minuit ne fabrique pas d'heure négative",
             all(0 <= x < 24 for h in range(24)
                 for x in F.runs_candidats(a(h))))
    verifier("les minutes ne changent rien (pick_run arrondit à l'heure)",
             F.runs_candidats(a(5, 59)) == F.runs_candidats(a(5, 0)))

    print("\n── ⛔ Accord nº 2 : la plage sûre, et le timer dedans ───")
    sures = [h for h in range(24) if F.moment_sur(a(h))[0]]
    verifier("la plage sûre est exactement 03, 04, 05 Z",
             sures == [3, 4, 5], str(sures))
    th, tm = heure_timer(timer)
    verifier("⛔ l'heure du VRAI timer tombe dans la plage sûre",
             th in sures, f"OnCalendar {th:02d}:{tm:02d} UTC, sûres {sures}")
    # ⚠️ La borne haute n'est pas la fin de la plage : l'ingestion dure
    # 12-19 min et `bw-model-arome` lit à 06:00 Z. Un timer à 05:50
    # serait « sûr » au sens de pick_run() et arriverait quand même trop
    # tard. C'est un SECOND accord, et il se banche à part.
    fin = th * 60 + tm + F.INGESTION_MIN_MAX[1]
    verifier("⛔ …et l'ingestion la plus lente finit AVANT la lecture de "
             "bw-model-arome",
             fin < F.LECTURE_H * 60,
             f"fin au pire {fin // 60:02d}:{fin % 60:02d} Z, "
             f"lecture {F.LECTURE_H:02d}:00 Z")

    print("\n── ⛔ Accord nº 3 : run.sh connaît le mode de l'unité ───")
    ex = [l for l in open(service, encoding="utf-8").read().splitlines()
          if l.startswith("ExecStart=")]
    verifier("l'unité a un seul ExecStart", len(ex) == 1)
    mode = ex[0].split()[-1]
    verifier("il appelle run.sh avec un mode", "run.sh" in ex[0], mode)
    runsh = open(os.path.join(_ICI, "run.sh"), encoding="utf-8").read()
    # ⚠️ La ligne est « a|b|c) ;; » : on coupe d'ABORD sur la parenthèse.
    # Un `split("|")` naïf rendrait « filet-arome) ;; » comme dernier
    # mode et ne reconnaîtrait jamais le dernier de la liste — c'est-à-dire
    # précisément celui qu'on vient d'ajouter.
    ligne_case = [l for l in runsh.splitlines()
                  if l.strip().endswith(") ;;") and "collect|" in l]
    modes = (ligne_case[0].split(")")[0].strip().split("|")
             if ligne_case else [])
    verifier("⛔ ce mode est accepté par run.sh (sinon : code 2 chaque matin)",
             mode in modes, f"mode « {mode} » parmi {modes}")

    print("\n── Ce que le script fait, et ne fait pas ───────────────")
    envoyes = []

    def faux_dispatch(depot, workflow, **kw):
        envoyes.append((depot, workflow))
        return True

    reel = F.dispatch_github
    F.dispatch_github = faux_dispatch
    try:
        code = F.main(["--dry-run"])
        verifier("--dry-run rend 0…", code == 0, str(code))
        verifier("⛔ …et ne déclenche RIEN", not envoyes, str(envoyes))

        envoyes.clear()
        code = F.main([])
        verifier("un run normal rend 0", code == 0, str(code))
        verifier("…et déclenche la cible par défaut",
                 envoyes == [("biozarb/balise-watch-server",
                              "arome-wind.yml")], str(envoyes))

        envoyes.clear()
        code = F.main(["--cible", "a/b:autre.yml"])
        verifier("--cible est respectée",
                 envoyes == [("a/b", "autre.yml")], str(envoyes))

        envoyes.clear()
        code = F.main(["--cible", "cible-cassee"])
        verifier("⛔ une cible illisible rend 2 (≠ 1 : ce n'est pas un "
                 "refus de GitHub, c'est une faute de configuration)",
                 code == 2, str(code))
        verifier("⛔ …et n'ouvre aucune connexion", not envoyes)

        F.dispatch_github = lambda *a, **k: False
        code = F.main([])
        verifier("⛔ un dispatch refusé rend 1 — `run.sh` doit voir un "
                 "échec, pas un « OK » qui verdirait Healthchecks",
                 code == 1, str(code))

        # ⚠️ `--out` est imposé par run.sh à tous ses modes : s'il n'était
        # pas accepté, argparse sortirait en code 2 chaque matin.
        F.dispatch_github = faux_dispatch
        envoyes.clear()
        code = F.main(["--out", "/var/lib/bw-model-verif"])
        verifier("⛔ `--out` (imposé par run.sh) est accepté et ignoré",
                 code == 0 and len(envoyes) == 1, str(code))
    finally:
        F.dispatch_github = reel

    print("\n  filet AROME wind :",
          "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
