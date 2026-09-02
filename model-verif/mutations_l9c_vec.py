#!/usr/bin/env python3
"""Rejoue les bancs contre des variantes CASSÉES de la REPRISE du volet
(c) du lot L9 — la référence combinée publiée sous DEUX définitions
(mélange scalaire et mélange vectoriel), arbitrage de Yann du
02/09/2026.

⛔ CE QU'ON CRAINT ICI N'EST PAS UN PLANTAGE, c'est une seconde colonne
PLAUSIBLE ET FAUSSE — un « mélange vectoriel » qui serait en réalité le
scalaire (donc deux colonnes identiques présentées comme un
départage), un skill neuf calculé sur une population qui n'est pas la
sienne, ou un compte de journées qui laisserait comparer une médiane
sur trois jours à une médiane sur quinze. Aucune de ces fautes ne
rougit toute seule, et toutes se publient — celle-ci sous l'étiquette
« on a mesuré les deux ».

⚠️ Le motif à muter doit exister TEL QUEL dans le fichier : une
mutation dont le motif est introuvable n'a rien muté, donc rien prouvé,
et ce script le dit en rouge plutôt que de la compter verte.

    python3 mutations_l9c_vec.py            # tout
    python3 mutations_l9c_vec.py 1 5        # par tranches
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
SCORE = ICI / "score.py"
INFER = ICI / "inference.py"
B_SCORE = ICI / "test_score.py"
B_INFER = ICI / "test_inference.py"

MUTATIONS = [
    # ══════════════════════════════════════════════════════════════
    #  A — LE MÉLANGE VECTORIEL EST-IL VRAIMENT VECTORIEL ?
    # ══════════════════════════════════════════════════════════════
    ("⭐⭐ le « mélange vectoriel » est en réalité le SCALAIRE — les deux "
     "colonnes deviennent identiques et le départage ne départage plus "
     "rien",
     INFER, B_INFER,
     """    up, vp = S.to_uv(sp, dp)
    uc, vc = S.to_uv(sc, dc)
    u = k * up + (1.0 - k) * uc
    v = k * vp + (1.0 - k) * vc
    f = math.hypot(u, v)""",
     """    up, vp = S.to_uv(1.0, dp)
    uc, vc = S.to_uv(1.0, dc)
    u = k * up + (1.0 - k) * uc
    v = k * vp + (1.0 - k) * vc
    f = k * sp + (1.0 - k) * sc"""),

    ("le mélange vectoriel pondère les DEUX composantes par k (au lieu "
     "de k et 1−k) : ce n'est plus un mélange convexe, donc la borne de "
     "Jensen n'a plus de raison de tenir",
     INFER, B_INFER,
     "    u = k * up + (1.0 - k) * uc\n    v = k * vp + (1.0 - k) * vc\n"
     "    f = math.hypot(u, v)",
     "    u = k * up + k * uc\n    v = k * vp + k * vc\n"
     "    f = math.hypot(u, v)"),

    ("⭐ k = 1 ne rend plus la persistance (les poids sont inversés) — "
     "un mélange qui ne retrouve pas ses bornes n'est pas un mélange",
     INFER, B_INFER,
     "    u = k * up + (1.0 - k) * uc\n    v = k * vp + (1.0 - k) * vc\n"
     "    f = math.hypot(u, v)",
     "    u = (1.0 - k) * up + k * uc\n    v = (1.0 - k) * vp + k * vc\n"
     "    f = math.hypot(u, v)"),

    ("la résultante nulle rend la force MOYENNE au lieu de zéro : deux "
     "vents opposés produisent un vent de 10 km/h",
     INFER, B_INFER,
     "    if f < 1e-12:\n        # Deux vents exactement opposés",
     "    if f < 1e-12 and False:\n        # Deux vents exactement opposés"),

    ("⛔ une balise SANS girouette n'est plus traitée pareil des deux "
     "côtés : l'écart entre les deux colonnes viendrait alors des "
     "girouettes manquantes, pas de l'espace du mélange",
     INFER, B_INFER,
     "    if dp is None or dc is None:\n        # Rien à mélanger",
     "    if dp is None and dc is None:\n        # Rien à mélanger"),

    # ══════════════════════════════════════════════════════════════
    #  B — LES DEUX MSE SONT-ILS SUR LA MÊME MATIÈRE ?
    # ══════════════════════════════════════════════════════════════
    ("⭐⭐ le MSE vectoriel est calculé dans une SECONDE boucle, sur sa "
     "propre population d'heures — le défaut §2.5.a reproduit par le "
     "lot qui existe pour le fermer",
     INFER, B_INFER,
     "        gs, gd = combined_reference_vec(k, pers, c)",
     "        gs, gd = combined_reference_vec(k, pers, (c[0] * 1.5, c[1]))"),

    ("le cinquième champ est renvoyé À LA PLACE du quatrième : les deux "
     "colonnes publiées portent le même nombre",
     INFER, B_INFER,
     "        (None if sq_c == 0 else 1 - sq_m / sq_c), n, mse_m, mse_c, mse_v)",
     "        (None if sq_c == 0 else 1 - sq_m / sq_c), n, mse_m, mse_v, mse_v)"),

    ("une série trop courte rend 0 au lieu de nul sur le champ neuf — "
     "« je ne sais pas » devient « référence parfaite »",
     INFER, B_INFER,
     "        return CombinedSkill(None, n, None, None, None)",
     "        return CombinedSkill(None, n, None, None, 0.0)"),

    # ══════════════════════════════════════════════════════════════
    #  C — LA CASE : MÉDIANES, COMPTES ET DÉNOMINATEURS
    # ══════════════════════════════════════════════════════════════
    ("⭐⭐ le skill vectoriel de la case prend le numérateur de TOUS les "
     "balise-jours et le dénominateur de ceux qui portent la colonne "
     "neuve — deux populations, exactement ce que `n_comb_vec` existe "
     "pour rendre visible",
     SCORE, B_SCORE,
     "        mse_cbm_vec = S.median([m for m, _ in trio_vec])",
     "        mse_cbm_vec = mse_cbm"),

    ("le compte de la colonne neuve recopie celui de l'ancienne : "
     "`n_comb_vec` == `n_comb` toujours, donc le lecteur croit les deux "
     "définitions sur la même matière dès la première nuit",
     SCORE, B_SCORE,
     '            "n_comb_vec": len(trio_vec),',
     '            "n_comb_vec": len(b["mse_cb"]),'),

    ("le triplet redevient un couple : `mse_comb_vec` n'entre plus dans "
     "l'accumulateur de case et la colonne neuve reste vide en silence",
     SCORE, B_SCORE,
     '                b["mse_cb"].append((d["mse_model_comb"], d["mse_comb"],\n'
     '                                    d.get("mse_comb_vec")))',
     '                b["mse_cb"].append((d["mse_model_comb"], d["mse_comb"],\n'
     '                                    None))'),

    ("la ligne de balise-jour n'emporte plus `mse_comb_vec` : la "
     "colonne existe en base et reste nulle pour toujours",
     SCORE, B_SCORE,
     '                "mse_comb_vec": _r(mse_cbv),',
     '                "mse_comb_vec": None,'),

    # ══════════════════════════════════════════════════════════════
    #  D — LA TABLE COLONNE→SQL, ET LA RÉSERVE
    # ══════════════════════════════════════════════════════════════
    ("⛔ la colonne neuve n'est pas déclarée dans la table colonne→.sql : "
     "le run ne saurait plus nommer le fichier à jouer (leçon du L13)",
     SCORE, B_SCORE,
     '        "mse_comb_vec": "supabase_step65_lot_l9c_melange_vectoriel.sql",',
     ""),

    ("la table colonne→.sql nomme un fichier qui n'existe pas — le "
     "contrôle du L13 doit le voir, sinon il ne contrôle rien",
     SCORE, B_SCORE,
     '        "n_comb_vec": "supabase_step65_lot_l9c_melange_vectoriel.sql",',
     '        "n_comb_vec": "supabase_step99_inexistant.sql",'),
]


def joue(debut: int = 1, fin: int | None = None) -> int:
    """⚠️ `debut`/`fin` NE SONT PAS UN CONFORT. Chaque mutation restaure
    son fichier en `finally` — mais un processus TUÉ (délai d'outil,
    pont Cowork qui tombe) ne passe jamais par son `finally` et laisse
    le fichier MUTÉ sur le disque (vécu deux fois le 27/08 au lot L3).
    Jouer par tranches courtes dans un shell qui a le temps de finir,
    puis contrôler que chaque motif `avant` est de retour.
    """
    fin = len(MUTATIONS) if fin is None else fin
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
    print("\n▶ mutations de la reprise L9(c) — mélange scalaire contre "
          "vectoriel. Chaque ligne "
          "doit être VERTE,\n  c'est-à-dire : le banc a bien ROUGI sur la "
          "faute.\n")
    debut = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    fin = int(sys.argv[2]) if len(sys.argv) > 2 else len(MUTATIONS)
    n = joue(debut, fin)
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
