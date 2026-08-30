#!/usr/bin/env python3
"""Rejoue `test_score.py` contre des variantes CASSÉES du lot L18
(un seul AGRUME au classement — `_agrume_temoin_excluded` et
`_exclus_du_rang` dans `score.py`).

⛔ UN BANC VERT NE PROUVE RIEN TANT QU'ON N'A PAS VU CE QUI LE FAIT
ROUGIR. Et ici plus qu'ailleurs : toutes les fautes ci-dessous rendent
un tableau qui a l'air PARFAITEMENT normal — un podium complet, aucune
exception, aucune ligne manquante — avec simplement l'AROME brut qui
reprend en silence le rang qu'on vient de lui retirer. C'est
exactement l'état de la production le 30/08/2026, où le témoin tenait
9 rangs et une première place sans que rien ne le signale.

Restauration en `finally` : le fichier revient à son état d'origine
même si l'on interrompt.

    python3 mutations_agrume_unique.py
"""
import os
import pathlib
import shutil
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
SCORE = ICI / "score.py"

MUTATIONS = [
    # ── qui est écarté : la question centrale du lot ─────────────────
    ("⛔ la priorité s'inverse : on écarte le COMPOSITE au lieu du "
     "témoin — le classement retombe sur le produit que l'écran ne "
     "sert à personne, ce que le lot existe pour fermer",
     SCORE,
     '    if AGRUME_MODEL in present and AGRUME_PI_MODEL in present:\n'
     '        return AGRUME_MODEL',
     '    if AGRUME_MODEL in present and AGRUME_PI_MODEL in present:\n'
     '        return AGRUME_PI_MODEL'),

    ("l'exclusion se déclenche quand UN SEUL des deux AGRUME est "
     "présent (OR au lieu de AND) — le témoin perd son rang sur les "
     "146 cases où il est seul, et où il est légitime",
     SCORE,
     '    if AGRUME_MODEL in present and AGRUME_PI_MODEL in present:',
     '    if AGRUME_MODEL in present or AGRUME_PI_MODEL in present:'),

    ("`_agrume_temoin_excluded` n'écarte plus jamais personne — le lot "
     "est inerte et le tableau ne change pas d'un chiffre",
     SCORE,
     '    present = {r["model"] for r in rows}\n'
     '    if AGRUME_MODEL in present and AGRUME_PI_MODEL in present:\n'
     '        return AGRUME_MODEL\n'
     '    return None',
     '    return None'),

    # ── les DEUX règles doivent coexister ───────────────────────────
    ("⛔⛔ `_exclus_du_rang` oublie la règle du L18 : une case qui "
     "porte les deux chaînes AROME *et* les deux AGRUME n'écarte plus "
     "que la première — un billet de trop au podium, en silence",
     SCORE,
     '    temoin = _agrume_temoin_excluded(rows)\n'
     '    if temoin is not None:\n'
     '        exclus[temoin] = RANK_REASON_SERIE_TEMOIN',
     '    pass'),

    ("les deux motifs se confondent : le témoin sort avec "
     "`duplicate_chain`, ce qui dirait au lecteur que les deux séries "
     "sont redondantes — et effacerait la raison du duel du lot L1",
     SCORE,
     '        exclus[temoin] = RANK_REASON_SERIE_TEMOIN',
     '        exclus[temoin] = RANK_REASON_DUPLICATE_CHAIN'),

    # ── le rang, et le motif, jusqu'en base ─────────────────────────
    ("le motif est bien posé mais le RANG reste — la ligne dit "
     "« écartée » et porte quand même son numéro de podium",
     SCORE,
     '            if motif is not None:\n'
     '                r["rank_reason"] = motif\n'
     '                r["rank"] = None',
     '            if motif is not None:\n'
     '                r["rank_reason"] = motif'),

    ("le classement CORRIGÉ perd la forme dictionnaire (elle est lue "
     "comme « aucun écarté ») — la même case dirait `serie_temoin` sur "
     "une colonne et `mixed_population` sur l'autre",
     SCORE,
     '              if isinstance(exclu, str) else dict(exclu))',
     '              if isinstance(exclu, str) else {})'),

    # ── ce que la base accepte vraiment ─────────────────────────────
    ("⛔ le motif neuf est déclaré ADMIS par le CHECK de la base alors "
     "que `supabase_step61_lot_l18_agrume_unique.sql` n'est pas joué — "
     "le repli d'`_upsert_scores` ne se désarme plus et la nuit tombe "
     "le jour où la base refuse vraiment",
     SCORE,
     '                       "window_too_short", "too_few_pairs", None}',
     '                       "window_too_short", "too_few_pairs",\n'
     '                       "serie_temoin", None}'),
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
    print("\n▶ mutations du lot L18 (un seul AGRUME au classement) — chaque "
          "ligne doit être VERTE,\n  c'est-à-dire : le banc a bien ROUGI "
          "sur la faute.\n")
    n = joue()
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
