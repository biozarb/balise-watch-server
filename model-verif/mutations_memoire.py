#!/usr/bin/env python3
"""Rejoue les bancs contre des variantes CASSÉES du lot MÉMOIRE
(28/08/2026 — l'oubli des blocs morts, le jalon, le seuil).

⛔ Un banc vert ne prouve rien tant qu'on n'a pas vu ce qui le fait
rougir. Et la faute qu'on craint ici a un visage précis, parce qu'elle
s'est produite : elle ne plante pas, elle ne rougit pas, elle ne dit
rien. Un bloc de 497 Mo qu'on oublie d'oublier ne se voit sur AUCUN
banc et sur AUCUN écran — il se voit six jours plus tard dans
`journalctl -k`, une fois la nuit perdue. Les mutations ci-dessous sont
donc toutes de la même famille : « le code marche encore, il ment
seulement sur la mémoire ».

    python3 mutations_memoire.py            # tout
    python3 mutations_memoire.py 1 4        # par tranches (voir `joue`)
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
    #  L'OUBLI — la cause exacte de l'OOM du 28/08
    # ══════════════════════════════════════════════════════════════
    ("⭐ LA FAUTE DE LA NUIT DU 28/08, remise telle quelle : la fenêtre "
     "glissante (497 Mo sondés) survit au chemin régime",
     SCORE, B_SCORE,
     '        daily = None\n        gc.collect()\n'
     '        jalon_memoire("l\'oubli de la fenêtre glissante")',
     '        jalon_memoire("l\'oubli de la fenêtre glissante")'),

    ("⭐ le chemin J-0 (snapshots, observations, climatologie, agrégats) "
     "n'est plus relâché du tout",
     SCORE, B_SCORE,
     '        n_prior, n_clim = len(prior), len(clim)\n'
     '        snapshots = obs_day = obs_prev = clim = poids_comb = prior = None\n'
     '        rows = banded = temoin = zones_raw = None\n'
     '        pres_obs = p_rows = daily_duel = updates = ev_rows = None\n',
     '        n_prior, n_clim = len(prior), len(clim)\n'),

    ("les trois snapshots (une journée d'émission chacun) restent "
     "vivants : l'oubli a l'air complet, il ne l'est pas",
     SCORE, B_SCORE,
     '        snapshots = obs_day = obs_prev = clim = poids_comb = prior = None',
     '        obs_day = obs_prev = clim = poids_comb = prior = None'),

    ("le méta de publication relit `len(prior)` après l'oubli — en "
     "production, c'est `TypeError: object of type NoneType has no "
     "len()` À LA TOUTE FIN du run, après vingt minutes de calcul",
     SCORE, B_SCORE,
     '                               "pairs_with_prior": n_prior,',
     '                               "pairs_with_prior": len(prior),'),

    ("le ramasse-miettes n'est plus appelé après l'oubli du chemin "
     "J-0 : les cycles de références (une ligne qui pointe sa case, une "
     "case qui liste ses lignes) survivent au `= None`",
     SCORE, B_SCORE,
     '        pres_obs = p_rows = daily_duel = updates = ev_rows = None\n'
     '        gc.collect()\n',
     '        pres_obs = p_rows = daily_duel = updates = ev_rows = None\n'),

    # ══════════════════════════════════════════════════════════════
    #  L'INSTRUMENT — un jalon faux est pire qu'aucun jalon
    # ══════════════════════════════════════════════════════════════
    ("⭐ `_rss_mo` rend des KILO-octets et les appelle des Mo : le run "
     "annonce 2 883 584 « Mo », le seuil est franchi à chaque jalon, "
     "et l'alerte devient un bruit qu'on apprend à ignorer",
     SCORE, B_SCORE,
     '                    return int(ligne.split()[1]) / 1024.0',
     '                    return float(int(ligne.split()[1]))'),

    ("⭐ le jalon lit `VmPeak` au lieu de `VmRSS` : le pic ne redescend "
     "JAMAIS, donc un bloc relâché ne se voit plus entre deux jalons — "
     "et on conclurait que l'oubli ne sert à rien",
     SCORE, B_SCORE,
     '                if ligne.startswith("VmRSS:"):',
     '                if ligne.startswith("VmPeak:"):'),

    ("le cri du dépassement part sur `stdout` comme le reste : il ne "
     "remonte plus dans l'alerte, il se noie dans le journal",
     SCORE, B_SCORE,
     '    print(texte, file=sys.stderr if trop else sys.stdout)',
     '    print(texte, file=sys.stdout)'),

    ("le seuil devient un « supérieur ou égal » : un run qui vaut "
     "exactement le seuil crie, donc un seuil rond crie sur un run rond",
     SCORE, B_SCORE,
     '    trop = mo > seuil_mo',
     '    trop = mo >= seuil_mo'),

    ("le run cesse de jalonner le rejeu d'archive — c'est-à-dire "
     "précisément l'étape où il est mort le 28/08",
     SCORE, B_SCORE,
     '        jalon_memoire("le rejeu d\'archive")\n',
     ''),
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
                               capture_output=True, text=True, cwd=ICI)
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
            fichier.write_text(origine, encoding="utf-8")
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations du lot MÉMOIRE (28/08) — chaque ligne doit être "
          "VERTE,\n  c'est-à-dire : le banc a bien ROUGI sur la faute.\n")
    debut = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    fin = int(sys.argv[2]) if len(sys.argv) > 2 else len(MUTATIONS)
    n = joue(debut, fin)
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
