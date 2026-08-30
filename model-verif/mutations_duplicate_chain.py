#!/usr/bin/env python3
"""Rejoue `test_score.py` contre des variantes CASSÉES du lot L2
(un seul AROME au classement, `_duplicate_chain_excluded` dans
`score.py`).

⛔ Un banc vert ne prouve rien tant qu'on n'a pas vu ce qui le fait
rougir (même discipline que `mutations_duel.py`, lot L1). La plupart de
ces fautes rendraient un classement qui a l'air juste : un podium
complet, aucune exception — et arome_r2 reprenant en silence le billet
qu'on vient de lui retirer.

⚠️ RÉÉCRIT LE 30/08/2026 (lot L18). `_apply_rank` n'appelle plus
`_duplicate_chain_excluded` en direct : il passe par `_exclus_du_rang`,
qui rend un DICTIONNAIRE modèle → motif parce qu'il y a désormais DEUX
règles d'exclusion. Les motifs de mutation ci-dessous ont suivi le
code ligne pour ligne — un motif introuvable ne mute rien et ne prouve
donc rien, ce que le script dit lui-même en rouge.

Restauration en `finally` : le fichier revient à son état d'origine
même si l'on interrompt.

    python3 mutations_duplicate_chain.py
"""
import os
import pathlib
import shutil
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
SCORE = ICI / "score.py"

MUTATIONS = [
    # ── la priorité entre les deux chaînes ──────────────────────────
    ("la priorité s'inverse : on écarte mfhd au lieu d'arome_r2",
     SCORE,
     '    if AROME_HD_MODEL in present and AROME_R2_MODEL in present:\n'
     '        return AROME_R2_MODEL',
     '    if AROME_HD_MODEL in present and AROME_R2_MODEL in present:\n'
     '        return AROME_HD_MODEL'),

    ("l'exclusion se déclenche même quand un seul des deux AROME est "
     "présent (OR au lieu de AND)",
     SCORE,
     '    if AROME_HD_MODEL in present and AROME_R2_MODEL in present:',
     '    if AROME_HD_MODEL in present or AROME_R2_MODEL in present:'),

    # ── le brut (_apply_rank) ────────────────────────────────────────
    ("l'écarté reste dans le POOL de classement (cases non filtrées) — "
     "il peut redevenir « second » en silence",
     SCORE,
     '        cases = [{"model": r["model"], "typical_err_kmh": r["typical_err_kmh"],\n'
     '                  "occurrences": r["occurrences"]} for r in admis]',
     '        cases = [{"model": r["model"], "typical_err_kmh": r["typical_err_kmh"],\n'
     '                  "occurrences": r["occurrences"]} for r in rows]'),

    ("le rang forcé de l'écarté disparaît — il garde son rang d'avant "
     "au lieu de `None`/`duplicate_chain`",
     SCORE,
     '        for r in rows:\n'
     '            motif = exclus.get(r["model"])\n'
     '            if motif is not None:\n'
     '                r["rank_reason"] = motif\n'
     '                r["rank"] = None\n'
     '        _apply_rank_corr(rows, rbcm, exclus)',
     '        _apply_rank_corr(rows, rbcm, exclus)'),

    ("le classement corrigé ne reçoit jamais l'écarté du brut (repli "
     "sur l'ancien appel à deux arguments)",
     SCORE,
     '        _apply_rank_corr(rows, rbcm, exclus)',
     '        _apply_rank_corr(rows, rbcm)'),

    # ── le corrigé (_apply_rank_corr) ───────────────────────────────
    ("l'écarté reste dans le POOL du classement corrigé (`chiffrees` "
     "non filtré par `admis`)",
     SCORE,
     '    admis = [r for r in rows if r["model"] not in exclus]\n'
     '    chiffrees = [r for r in admis if r.get("typical_err_kmh") is not None]',
     '    admis = [r for r in rows if r["model"] not in exclus]\n'
     '    chiffrees = [r for r in rows if r.get("typical_err_kmh") is not None]'),

    ("le compte « avec corrigé » redevient global — l'écarté peut "
     "faire tomber les AUTRES en « population mixte » à sa place",
     SCORE,
     '    avec = [r for r in chiffrees if r.get("typical_err_kmh_corr") is not None]',
     '    avec = [r for r in rows if r.get("typical_err_kmh_corr") is not None]'),

    ("le rang corrigé forcé de l'écarté disparaît — il garde ce que la "
     "boucle `admis` (ou le refus mixte) lui a laissé",
     SCORE,
     '    for r in rows:\n'
     '        motif = exclus.get(r["model"])\n'
     '        if motif is not None:\n'
     '            r["rank_corr"] = None\n'
     '            r["rank_reason_corr"] = motif',
     '    if False:\n'
     '        pass'),
]


def _env_sans_pyc() -> dict:
    """L'environnement du banc, SANS écriture ni lecture de bytecode.

    ⛔⛔ LE PIÈGE, TROUVÉ LE 30/08/2026 SUR LE LOT L10, ET IL REND UNE
    MUTATION MENTEUSE. `HEURES_CIBLES = 6` muté en `= 7` fait EXACTEMENT
    la même longueur de fichier ; si la restauration retombe dans la même
    SECONDE, l'horodatage ne bouge pas non plus. Python juge son cache
    `__pycache__` sur (mtime, taille) : il a donc rechargé le bytecode
    MUTÉ pour les trois mutations suivantes, qui ont rougi — mais pour la
    faute de la précédente. Trois lignes vertes qui ne prouvaient rien.
    ⇒ `-B` (ne pas écrire) et `PYTHONDONTWRITEBYTECODE` (pour les
    sous-processus), plus le ménage ci-dessous. Une mutation qui ne peut
    pas prouver ce qu'elle affirme est pire qu'une mutation absente.
    """
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for p in ICI.rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)
    return env


def joue() -> int:
    rouges = 0
    for i, (nom, fichier, avant, apres) in enumerate(MUTATIONS, 1):
        origine = fichier.read_text(encoding="utf-8")
        if avant not in origine:
            print(f"  ⛔ {i:>2}. {nom}\n       MOTIF INTROUVABLE dans "
                  f"{fichier.name} — la mutation n'a rien muté, donc elle "
                  f"n'a rien prouvé. (Le code a bougé : réécrire ce motif.)")
            rouges += 1
            continue
        try:
            fichier.write_text(origine.replace(avant, apres, 1), encoding="utf-8")
            r = subprocess.run([sys.executable, "-B", str(ICI / "test_score.py")],
                               capture_output=True, text=True, cwd=ICI,
                               env=_env_sans_pyc())
            if r.returncode == 0:
                print(f"  ❌ {i:>2}. {nom}\n       LE BANC RESTE VERT — "
                      f"il ne tient pas cette propriété.")
                rouges += 1
            else:
                lignes = [l.strip() for l in r.stdout.splitlines()
                          if l.strip().startswith("❌")]
                if not lignes:
                    lignes = [l.strip() for l in r.stderr.splitlines()[-3:]]
                print(f"  ✅ {i:>2}. {nom}\n       "
                      f"{lignes[0] if lignes else 'banc rouge'}"
                      + (f" (+{len(lignes) - 1} autres)"
                         if len(lignes) > 1 else ""))
        finally:
            fichier.write_text(origine, encoding="utf-8")
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations du lot L2 (un seul AROME au classement) — chaque "
          "ligne doit être VERTE,\n  c'est-à-dire : le banc a bien ROUGI "
          "sur la faute.\n")
    n = joue()
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
