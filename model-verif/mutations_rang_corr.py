#!/usr/bin/env python3
"""Rejoue les bancs contre des variantes CASSÉES du repli des DEUX
raisons de rang (28/08/2026).

⛔ Ce lot est né d'une panne réelle, et la faute qu'il corrige avait
exactement la forme que ce fichier traque : un repli qui a l'air
complet, qui l'est pour UNE des deux colonnes, et qui laisse tomber la
nuit entière sur l'autre — à la dernière étape, après vingt-trois
minutes de calcul.

    python3 mutations_rang_corr.py
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
SCORE = ICI / "score.py"
B_SCORE = ICI / "test_score.py"

MUTATIONS = [
    # ══════════════════════════════════════════════════════════════
    #  LE CORPS D'ERREUR — ce qui rendait le repli INERTE
    # ══════════════════════════════════════════════════════════════
    ("⭐⭐ LA FAUTE DE FOND, REMISE TELLE QUELLE : le message d'erreur "
     "reprend l'ordre de PostgREST (`details` avant `message`) — la "
     "ligne fautive chasse le nom de la contrainte, et le repli, vert "
     "au banc, ne peut plus jamais partir en production",
     SCORE, B_SCORE,
     '    for cle in ("code", "message", "hint", "details"):',
     '    for cle in ("code", "details", "hint", "message"):'),

    ("la ligne fautive n'est plus tronquée : un `details` de 50 000 "
     "caractères part en entier dans le journal, et le message utile "
     "s'y noie",
     SCORE, B_SCORE,
     "        if cle == \"details\" and len(valeur) > car_details:\n"
     "            valeur = (valeur[:car_details]\n"
     "                      + f\"… (+{len(valeur) - car_details} car.)\")",
     "        if False:\n            pass"),

    ("on ne lit de nouveau que 400 octets du corps : la mise en forme "
     "est juste, mais elle travaille sur un JSON déjà coupé",
     SCORE, B_SCORE,
     'ERREUR_OCTETS = 65536',
     'ERREUR_OCTETS = 400'),

    ("un corps qui n'est pas du JSON (passerelle en panne, HTML "
     "d'erreur) devient une chaîne vide : la panne existe et plus rien "
     "ne la nomme",
     SCORE, B_SCORE,
     '    if not isinstance(objet, dict):\n        return texte[:2000]',
     '    if not isinstance(objet, dict):\n        return ""'),

    ("⭐ LA FAUTE DU 28/08, REMISE TELLE QUELLE : le repli ne connaît "
     "que le CHECK de `rank_reason` — celui du corrigé re-lève et "
     "emporte la nuit",
     SCORE, B_SCORE,
     '    ("model_score_zone_rank_reason_corr_check", "rank_reason_corr",\n'
     '     RANK_REASONS_CORR_STEP52,\n'
     '     "supabase_step58_rank_reason_corr.sql "\n'
     '     "(`duplicate_chain` et `fdr` sur la colonne CORRIGÉE)"),\n',
     ''),

    ("⭐ `RANK_REASONS_CORR_STEP52` s'élargit « au cas où » et admet "
     "`duplicate_chain` : le repli ne tait plus rien, et la base "
     "refuse toujours — le run retombe, mais en ayant l'air réparé",
     SCORE, B_SCORE,
     'RANK_REASONS_CORR_STEP52 = (RANK_REASONS_STEP40\n'
     '                            | {"single_model", "mixed_population"})',
     'RANK_REASONS_CORR_STEP52 = (RANK_REASONS_STEP40\n'
     '                            | {"single_model", "mixed_population",\n'
     '                               "duplicate_chain", "fdr"})'),

    ("le repli tait toujours `rank_reason`, quelle que soit la "
     "contrainte qui a refusé — il efface une raison que la base "
     "ACCEPTE et laisse en place celle qu'elle refuse",
     SCORE, B_SCORE,
     '            for r in rows:\n'
     '                if r.get(colonne) not in admises:\n'
     '                    r[colonne] = None',
     '            for r in rows:\n'
     '                if r.get("rank_reason") not in admises:\n'
     '                    r["rank_reason"] = None'),

    ("⭐ le garde « contrainte déjà désarmée » saute : une contrainte "
     "qui refuse encore fait BOUCLER le run pour toujours",
     SCORE, B_SCORE,
     '            repli = next((p for p in REPLIS_RANG\n'
     '                          if p[0] in str(exc) and p[0] not in desarmes),\n'
     '                         None)',
     '            repli = next((p for p in REPLIS_RANG\n'
     '                          if p[0] in str(exc)),\n'
     '                         None)'),

    ("le repli AVALE les contraintes qu'il ne sait pas désarmer : une "
     "vraie panne (clé primaire, type, NOT NULL) devient un run vert "
     "qui n'a rien écrit",
     SCORE, B_SCORE,
     '            if repli is None:\n                raise',
     '            if repli is None:\n                return 0'),

    ("le repli ne se donne qu'UN tour : il désarme la première "
     "contrainte, se fait refuser par la seconde, et rend `None` — "
     "c'est-à-dire zéro ligne écrite sans que personne ne le sache",
     SCORE, B_SCORE,
     '    desarmes: set[str] = set()\n    while True:',
     '    desarmes: set[str] = set()\n    for _ in range(2):'),
]


def joue(debut: int, fin: int) -> int:
    rouges = 0
    for i, (nom, fichier, banc, avant, apres) in enumerate(MUTATIONS, 1):
        if not (debut <= i <= fin):
            continue
        origine = fichier.read_text(encoding="utf-8")
        if avant not in origine:
            print(f"  ⛔ {i:>2}. {nom}\n       MOTIF INTROUVABLE dans "
                  f"{fichier.name} — la mutation n'a rien muté, donc elle "
                  f"n'a rien prouvé. (Le code a bougé : réécrire ce motif.)")
            rouges += 1
            continue
        try:
            fichier.write_text(origine.replace(avant, apres, 1),
                               encoding="utf-8")
            r = subprocess.run([sys.executable, str(banc)],
                               capture_output=True, text=True, cwd=ICI,
                               timeout=300)
            if r.returncode == 0:
                print(f"  ❌ {i:>2}. {nom}\n       LE BANC RESTE VERT "
                      f"({banc.name}) — il ne tient pas cette propriété.")
                rouges += 1
            else:
                lignes = [l.strip() for l in r.stdout.splitlines()
                          if l.strip().startswith("❌")]
                if not lignes:
                    lignes = [l.strip() for l in r.stderr.splitlines()[-3:]]
                print(f"  ✅ {i:>2}. {nom}\n       [{banc.name}] "
                      f"{lignes[0] if lignes else 'banc rouge'}"
                      + (f" (+{len(lignes) - 1} autres)"
                         if len(lignes) > 1 else ""))
        except subprocess.TimeoutExpired:
            print(f"  ✅ {i:>2}. {nom}\n       [{banc.name}] le banc ne "
                  f"finit plus (boucle) — vu, mais préférer un banc qui "
                  f"ROUGIT à un banc qui PEND.")
        finally:
            fichier.write_text(origine, encoding="utf-8")
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations du repli des DEUX raisons de rang (28/08) — "
          "chaque ligne doit être VERTE,\n  c'est-à-dire : le banc a bien "
          "ROUGI sur la faute.\n")
    debut = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    fin = int(sys.argv[2]) if len(sys.argv) > 2 else len(MUTATIONS)
    n = joue(debut, fin)
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
