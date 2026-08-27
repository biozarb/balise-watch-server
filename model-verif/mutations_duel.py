#!/usr/bin/env python3
"""Rejoue `test_duel.py` contre des variantes CASSÉES de `duel.py`.

⛔ Un banc vert ne prouve rien tant qu'on n'a pas vu ce qui le fait
rougir. Chaque mutation ci-dessous est une faute qu'on pourrait écrire
sans s'en apercevoir — et la plupart rendraient un duel qui a l'air
juste : des chiffres plausibles, un verdict crédible, aucune exception.
Celle qui laisserait le banc VERT désignerait un banc trop faible.

Restauration en `finally` : les fichiers reviennent à leur état
d'origine même si l'on interrompt.

    python3 mutations_duel.py
"""
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
DUEL = ICI / "duel.py"
SCORE = ICI / "score.py"

MUTATIONS = [
    # ── ce que le duel MESURE ───────────────────────────────────────
    ("la colonne mesurée redevient err_vec_med (sourde à PI)",
     DUEL,
     'DUEL_VALUE_KEY = "err_vec_rms"',
     'DUEL_VALUE_KEY = "err_vec_med"'),

    ("le signe est inversé (B − A au lieu de A − B)",
     DUEL,
     'diffs = INF.paired_differences(rows_a, rows_b, value_key=value_key)',
     'diffs = INF.paired_differences(rows_b, rows_a, value_key=value_key)'),

    ("le verdict lit la MOYENNE là où l'intervalle borne la médiane",
     DUEL,
     '    elif (ci.median or 0.0) < 0:',
     '    elif (moyenne or 0.0) < 0:'),

    ("un verdict est rendu même quand l'intervalle n'existe pas",
     DUEL,
     '    if separe is None:\n        verdict = ci.reason',
     '    if separe is None:\n        verdict = "not_separable"'),

    # ── l'appariement ───────────────────────────────────────────────
    ("la balise est identifiée par son NUMÉRO seul (collision de réseaux)",
     DUEL,
     '    return f"{row[\'source\']}:{row[\'station_id\']}"',
     '    return f"{row[\'station_id\']}"'),

    ("le doublon de chaîne est tranché en silence (on garde le premier)",
     DUEL,
     '    for cle in doublons:\n        par_cle.pop(cle, None)',
     '    pass'),

    ("le filtre de classe d'échéance est ignoré (on mélange +6 h et +24 h)",
     DUEL,
     '        if lead_h is not None and r.get("lead_h") != lead_h:\n'
     '            continue',
     '        pass'),

    ("le filtre de réseau est ignoré (populations mélangées)",
     DUEL,
     '        if source is not None and r.get("source") != source:\n'
     '            continue',
     '        pass'),

    # ── le cumul ────────────────────────────────────────────────────
    ("le cumul devient la moyenne des moyennes journalières",
     DUEL,
     '        somme += sum(vals)\n        n_cum += len(vals)',
     '        somme += sum(vals) / len(vals)\n        n_cum += 1'),

    ("le drapeau de troncature ment (toujours faux)",
     DUEL,
     '        "truncated_by_retention": bool(\n'
     '            fenetre_jours is not None and ci.n_days >= fenetre_jours),',
     '        "truncated_by_retention": False,'),

    # ── ce qui doit exister même vide ───────────────────────────────
    ("une paire sans donnée disparaît au lieu de rendre une ligne à zéro",
     DUEL,
     '    return [duel_paire(daily, a, b, lead_h, source, value_key, fenetre_jours)\n'
     '            for a, b in paires]',
     '    out = [duel_paire(daily, a, b, lead_h, source, value_key, fenetre_jours)\n'
     '           for a, b in paires]\n'
     '    return [d for d in out if d["n_pairs"]]'),

    ("la requête redemande toutes les colonnes",
     DUEL,
     "         f\"&select={','.join(colonnes)}\")",
     '         "&select=*")'),

    ("l'arrondi publié perd deux décimales (0,03 devient 0,0)",
     DUEL,
     '    return None if x is None or not S._finite(x) else round(float(x), nd)',
     '    return None if x is None or not S._finite(x) else round(float(x), 1)'),

    # ── le trajet jusqu'à l'objet publié (piège nº 7) ───────────────
    ("le bloc `duels` n'arrive jamais dans le fichier léger",
     SCORE,
     '        "duels": list(duels or []),',
     '        "duels": [],'),

    ("les duels sont versés dans `scores` (ils deviennent un classement)",
     SCORE,
     '        "scores": light_score_rows(scores),\n'
     '        "bascules": light_bascule_rows(ev_scores),',
     '        "scores": light_score_rows(scores) + list(duels or []),\n'
     '        "bascules": light_bascule_rows(ev_scores),'),
]


def joue() -> int:
    rouges = 0
    for i, (nom, fichier, avant, apres) in enumerate(MUTATIONS, 1):
        origine = fichier.read_text()
        if avant not in origine:
            print(f"  ⛔ {i:>2}. {nom}\n       MOTIF INTROUVABLE dans "
                  f"{fichier.name} — la mutation n'a rien muté, donc elle "
                  f"n'a rien prouvé. (Le code a bougé : réécrire ce motif.)")
            rouges += 1
            continue
        try:
            fichier.write_text(origine.replace(avant, apres, 1))
            r = subprocess.run([sys.executable, str(ICI / "test_duel.py")],
                               capture_output=True, text=True, cwd=ICI)
            if r.returncode == 0:
                print(f"  ❌ {i:>2}. {nom}\n       LE BANC RESTE VERT — "
                      f"il ne tient pas cette propriété.")
                rouges += 1
            else:
                lignes = [l.strip() for l in r.stdout.splitlines()
                          if l.strip().startswith("❌")]
                print(f"  ✅ {i:>2}. {nom}\n       "
                      f"{lignes[0] if lignes else 'banc rouge'}"
                      + (f" (+{len(lignes) - 1} autres)"
                         if len(lignes) > 1 else ""))
        finally:
            fichier.write_text(origine)
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations du DUEL APPARIÉ (lot L1) — chaque ligne doit être "
          "VERTE,\n  c'est-à-dire : le banc a bien ROUGI sur la faute.\n")
    n = joue()
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
