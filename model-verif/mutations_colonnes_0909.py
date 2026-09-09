#!/usr/bin/env python3
"""Rejoue les bancs contre des variantes CASSÉES de la restriction des
colonnes lues par la fenêtre glissante (09/09/2026).

⛔ LA FAUTE QUE CE LOT PEUT INTRODUIRE NE PLANTE PAS : une colonne lue
par `_case_rows` et oubliée dans `COLONNES_FENETRE` fait rendre `None`
à `d.get()`, la métrique s'éteint (skill, biais, corrigé…) et le run
finit VERT. C'est la raison même pour laquelle l'incident du 07/09
avait remis ce correctif. Chaque mutation ci-dessous est de cette
famille : le code marche encore, il ment seulement.

    python3 mutations_colonnes_0909.py            # tout
    python3 mutations_colonnes_0909.py 1 3        # par tranches
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import harnais as HARNAIS  # noqa: E402

SCORE = ICI / "score.py"
B_SCORE = ICI / "test_score.py"

MUTATIONS = [
    ("⭐⭐ `main` relit `select=*` : le correctif existe, personne ne "
     "s'en sert, et 13 colonnes sur 31 repartent en mémoire",
     SCORE, B_SCORE,
     '            query=f"?day=gte.{since}&select={COLONNES_FENETRE}")',
     '            query=f"?day=gte.{since}")'),
    ("⭐⭐ `mse_clim` sort de la liste : `skill_clim` et `beats_clim` "
     "s'éteignent sur toutes les cases, sans une ligne rouge",
     SCORE, B_SCORE,
     '    "mse_model", "mse_persist", "mse_clim",\n',
     '    "mse_model", "mse_persist",\n'),
    ("`err_vec_med_corr` sort : le classement corrigé (rank_corr) n'a "
     "plus de matière — 468 rangs publiés le 09/09 deviennent 0",
     SCORE, B_SCORE,
     '    "err_vec_med", "err_vec_med_corr",\n',
     '    "err_vec_med",\n'),
    ("`n_hours` sort : le rapport h/j (L14) et le quorum d'heures "
     "comptent zéro partout",
     SCORE, B_SCORE,
     '    "n_hours",\n',
     ''),
    ("⭐ `day` sort : `select_par_cle` n'a plus de borne — KeyError en "
     "production, mais le banc doit le dire AVANT",
     SCORE, B_SCORE,
     '    "day", "source", "station_id", "model", "lead_h",\n',
     '    "source", "station_id", "model", "lead_h",\n'),
    ("`station_id` sort : `unit` ne peut plus se fabriquer",
     SCORE, B_SCORE,
     '    "day", "source", "station_id", "model", "lead_h",\n',
     '    "day", "source", "model", "lead_h",\n'),
    ("⭐ `_case_rows` se met à lire une colonne NEUVE (`bias_slope`) "
     "sans l'ajouter à la liste : c'est le geste de demain, et il "
     "doit rougir aujourd'hui",
     SCORE, B_SCORE,
     '            b["n_hours"] += d.get("n_hours") or 0',
     '            b["n_hours"] += d.get("n_hours") or 0\n'
     '            b["_pente"] = d.get("bias_slope")'),
    ("la liste prend un doublon et un espace (`select=` PostgREST "
     "rendrait 400 sur la ligne — mais seulement en production)",
     SCORE, B_SCORE,
     '    "n_hours",\n',
     '    "n_hours", " n_hours",\n'),
    ("le banc cesse d'extraire les clés du source et ne compare plus "
     "que deux chaînes : la mutation nº 7 redevient invisible",
     B_SCORE, B_SCORE,
     '    lues |= set(re.findall(r\'\\bd\\.get\\(\\"(\\w+)\\"\', corps))',
     '    lues |= set()'),
]


def joue(debut: int, fin: int) -> int:
    rouges = 0
    for i, (nom, fichier, banc, avant, apres) in enumerate(MUTATIONS, 1):
        if not (debut <= i <= fin):
            continue
        origine = HARNAIS.garder(fichier)
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
                               env=HARNAIS.env_banc(ICI))
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
        finally:
            HARNAIS.rendre(fichier, origine)
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations « colonnes de la fenêtre » (09/09) — chaque ligne "
          "doit être VERTE,\n  c'est-à-dire : le banc a bien ROUGI sur la "
          "faute.\n")
    debut = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    fin = int(sys.argv[2]) if len(sys.argv) > 2 else len(MUTATIONS)
    n = joue(debut, fin)
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
