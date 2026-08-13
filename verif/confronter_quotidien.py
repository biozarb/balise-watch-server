#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  verif/confronter_quotidien.py — rejouer confronter_sondage tout seul,
#                                   chaque jour, pour faire grandir n
#                                                        (13/08/2026)
#
#  Lot M. Jusqu'ici `confronter_sondage.py` s'appelle À LA MAIN, une
#  fois, pour UN couple station/date/heure — ce qui est exactement ce
#  qu'il fallait pour établir la méthode (§ README, n = 9 à Payerne).
#  Mais le README le dit lui-même : « n restera petit », et une mesure
#  qui ne grandit pas ne devient jamais un chiffre qu'on peut citer.
#
#  Ce script ne réinvente RIEN : il appelle exactement les mêmes
#  fonctions que `confronter_sondage.py` (`radiosondage.py`,
#  `sonder.depuis_r2`, `profil.sonder`), pour CHAQUE station ACTIVE de
#  `STATIONS`, sur le lâcher de la VEILLE (00Z et 12Z), et journalise le
#  résultat en NDJSON — un succès ou un abandon, jamais un silence.
#
#  ⚠️ POURQUOI LA VEILLE, PAS AUJOURD'HUI. La rétention du produit A est
#  glissante (7 jours, Lot J) : la veille est TOUJOURS dans l'archive, et
#  son ballon a eu le temps d'être publié par Wyoming (jamais instantané).
#  Confronter le jour même risquerait de manquer l'un des deux, pour
#  rien — le lendemain suffit et ne coûte rien de plus.
#
#  ⚠️ POURQUOI L'ÉCHÉANCE +6 h, ET PAS 0 NI LA PLUS RÉCENTE DISPONIBLE.
#  `radiosondage.runs_pour()` le dit déjà : l'échéance 0 est une ANALYSE
#  (elle a assimilé des observations, peut-être CE ballon), donc la
#  confronter mesurerait l'assimilation, pas la prévision. +6 h est le
#  lead que le Lot I a déjà retenu pour noter AGRUME dans le scoring
#  (`claude/lot-i-agrume-scoring-13-08.md`) — un choix déjà arbitré,
#  documenté, et cohérent d'un lot à l'autre plutôt qu'un second chiffre
#  concurrent.
#
#  ⛔ CE QUI N'EST PAS ICI. Une station qui rend HTTP 400 à une heure
#  donnée (cf. Innsbruck à 12Z, mesuré le 13/08 : 0/6, systématique) N'EST
#  PAS retirée de la boucle. Le script continue d'essayer, honnêtement,
#  et journalise l'abandon avec sa raison — c'est LUI qui doit finir par
#  dire « cette station ne publie qu'à 00Z », pas un commentaire figé
#  qu'on pourrait un jour laisser mentir.
#
#      python3 verif/confronter_quotidien.py                 # la veille
#      python3 verif/confronter_quotidien.py --date 2026-08-10
#      python3 verif/confronter_quotidien.py --rapport        # relit le journal
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "agrume"))

import profil as P                                            # noqa: E402
import radiosondage as RS                                     # noqa: E402
from quantification import Abort                              # noqa: E402
from sonder import depuis_r2, trouver_balise                  # noqa: E402

ECHEANCE_H = 6            # cf. l'en-tête : cohérent avec le scoring AGRUME
JOURNAL_DEFAUT = Path(os.environ.get(
    "BW_CONFRONTATION_JOURNAL",
    "/var/lib/bw-model-verif/agrume_confrontation.ndjson"))


def run_iso(date, heure):
    """Le run AROME dont l'échéance ECHEANCE_H tombe exactement sur le
    lâcher (date, heure) — pas une échéance voisine, cf. l'avertissement
    de `radiosondage.runs_pour` : un décalage d'une heure sur un profil
    de vent passerait pour un défaut du modèle."""
    t = RS.instant_ballon(date, heure)
    run = t - timedelta(hours=ECHEANCE_H)
    return run.strftime("%Y-%m-%dT%H:00:00Z")


def lire_journal(chemin=JOURNAL_DEFAUT):
    if not chemin.exists():
        return []
    out = []
    for ligne in chemin.read_text(encoding="utf-8").splitlines():
        ligne = ligne.strip()
        if ligne:
            out.append(json.loads(ligne))
    return out


def ecrire_ligne(entree, chemin=JOURNAL_DEFAUT):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "a", encoding="utf-8") as f:
        f.write(json.dumps(entree, ensure_ascii=False, default=str) + "\n")


def deja_fait(entrees, wmo, date, heure):
    """⚠️ Idempotence : un timer relancé à la main après un incident ne
    doit pas dupliquer une ligne déjà journalisée pour ce couple — un
    doublon fausserait n sans qu'aucun écran ne le dise."""
    return any(e["wmo"] == wmo and e["date"] == date and e["heure"] == heure
               for e in entrees)


def confronter_un(station, date, heure, crier=print):
    """Une confrontation, du couple (station, date, heure) à la ligne de
    journal. Ne lève JAMAIS : chaque échec a une CAUSE nommée, et la
    boucle appelante continue avec les autres — trois causes, trois
    messages, jamais un silence."""
    run = run_iso(date, heure)
    base = dict(wmo=station["wmo"], nom=station["nom"], date=date,
                heure=heure, run=run, echeanceH=ECHEANCE_H)
    if not station["active"]:
        return dict(base, etat="ignore", cause="station inactive")
    try:
        col, man = depuis_r2(run)
    except Exception as e:                                     # noqa: BLE001
        return dict(base, etat="abandon",
                    cause=f"run absent de l'archive glissante : {e}")
    if ECHEANCE_H not in col.steps:
        return dict(base, etat="abandon",
                    cause=f"échéance {ECHEANCE_H} h absente ({col.steps})")
    try:
        k = trouver_balise(col, f"RS-{station['wmo']}")
    except Abort as e:
        return dict(base, etat="abandon",
                    cause=f"balise absente de cet axe archivé : {e}")
    try:
        reponse = P.sonder(col, man, k, ECHEANCE_H,
                           altitude_reelle=station["sol_station_m"])
        niveaux = RS.parse_wyoming(RS.telecharger(station["wmo"], date, heure))
        c = RS.confronter(reponse, niveaux)
    except RS.Abort as e:
        return dict(base, etat="abandon", cause=str(e))
    except Exception as e:                                     # noqa: BLE001
        return dict(base, etat="abandon", cause=f"{type(e).__name__}: {e}")

    g = c["global_"]
    crier(f"  ✓ {station['nom']} {date} {heure}Z (+{ECHEANCE_H} h) : "
          f"n={g['n']} écart médian {g['ecartVentMs']['mediane']} m/s")
    return dict(base, etat="confronte", nPoints=g["n"],
                ecartVentMedianMs=g["ecartVentMs"]["mediane"],
                ecartVentD9Ms=g["ecartVentMs"]["d9"],
                biaisVitesseMs=g["biaisVitesseMs"],
                parSource=[dict(libelle=b["libelle"], n=b["n"],
                                ecartMedianMs=b["ecartVentMs"]["mediane"])
                          for b in c["parSource"]])


def quotidien(date=None, crier=print):
    if date is None:
        date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    entrees = lire_journal()
    ecrites = []
    for station in RS.STATIONS:
        for heure in ("00", "12"):
            if deja_fait(entrees, station["wmo"], date, heure):
                continue
            e = confronter_un(station, date, heure, crier)
            ecrire_ligne(e)
            ecrites.append(e)
            if e["etat"] == "abandon":
                crier(f"  · {station['nom']} {date} {heure}Z : {e['cause']}")
    n_ok = sum(1 for e in ecrites if e["etat"] == "confronte")
    crier(f"▶ {date} : {n_ok}/{len(ecrites)} confrontations écrites "
          f"({len(entrees) + len(ecrites)} au total dans le journal)")
    return 0


def rapport(crier=print):
    entrees = [e for e in lire_journal() if e["etat"] == "confronte"]
    if not entrees:
        crier("Journal vide — aucune confrontation pour l'instant.")
        return 0
    par_station = {}
    for e in entrees:
        par_station.setdefault(e["nom"], []).append(e)
    crier(f"── CONFRONTATION AU BALLON, {len(entrees)} confrontations ──")
    for nom, es in sorted(par_station.items()):
        ecarts = sorted(e["ecartVentMedianMs"] for e in es)
        n = len(ecarts)
        crier(f"\n{nom} — n = {n} confrontations "
              f"({es[0]['date']} → {es[-1]['date']})")
        crier(f"  écart vent médian : min {ecarts[0]:.2f} · "
              f"médiane {ecarts[n // 2]:.2f} · max {ecarts[-1]:.2f} m/s")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", default=None,
                   help="AAAA-MM-JJ à confronter — défaut : la veille (UTC)")
    p.add_argument("--rapport", action="store_true",
                   help="n'interroge rien, relit et résume le journal")
    a = p.parse_args(argv)
    if a.rapport:
        return rapport()
    return quotidien(a.date)


if __name__ == "__main__":
    sys.exit(main())
