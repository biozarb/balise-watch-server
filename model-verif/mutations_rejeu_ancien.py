#!/usr/bin/env python3
"""Rejoue le banc de `score.py` contre des variantes CASSEES du garde-fou
du lot LR — « un rejeu de vieille journee ne republie pas le classement
du jour ».

⛔ UN BANC VERT NE PROUVE RIEN TANT QU'ON N'A PAS VU CE QUI LE FAIT
ROUGIR, et ce garde-fou-ci a DEUX facons de casser, opposees et toutes
les deux silencieuses :

  · trop PERMISSIF (mutation nº 1) : on revient a l'etat d'avant, et un
    rejeu du 13/08 republie 25 jours sous l'etiquette `rolling15` —
    290 premieres places sur 1 984 changent de titulaire, mesure le
    01/09, et rien n'a l'air anormal ;
  · trop STRICT (mutations nº 2 et 3) : la nuit NORMALE cesse de
    publier. Le job rend 0, aucune alerte ne part, et le classement se
    fige — on ne s'en apercevrait qu'en remarquant que l'ecran ne bouge
    plus. C'est la pire des deux.

Restauration en `finally` : les fichiers reviennent a leur etat
d'origine meme si l'on interrompt.

    python3 model-verif/mutations_rejeu_ancien.py
"""
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent

# ⛔ (02/09/2026) copie d'origine sur le disque + sha256 + purge du
# bytecode, pour TOUS les harnais — voir `model-verif/harnais.py`.
sys.path.insert(0, str(ICI))
import harnais as HARNAIS  # noqa: E402
SCORE = ICI / "score.py"
BANC = "test_score.py"

MUTATIONS = [
    # ── ⛔⛔ TROP PERMISSIF : on revient a l'etat d'avant le lot ──────
    ("⛔⛔ le garde-fou rend TOUJOURS vrai — c'est l'etat d'avant le lot "
     "LR : un rejeu du 13/08 republie 25 jours sous l'etiquette "
     "`rolling15`, et 290 podiums sur 1 984 changent de titulaire",
     SCORE,
     '    if forcer:\n        return True\n    hier = (as_of - timedelta(days=1)).date()\n    return day.date() >= hier',
     '    return True'),

    # ── ⛔ TROP STRICT : la nuit normale cesse de publier ────────────
    ("⛔ la comparaison devient STRICTE (`>` au lieu de `>=`) : la nuit "
     "normale, qui note HIER, cesse de publier — le job rend 0, aucune "
     "alerte ne part, et le classement se fige en silence",
     SCORE,
     '    return day.date() >= hier',
     '    return day.date() > hier'),

    ("⛔ la frontiere devient un ECART DE 24 h au lieu d'une DATE : a "
     "03:56 la journee notee a 27 h 56, donc AUCUNE nuit ne publie plus",
     SCORE,
     '    hier = (as_of - timedelta(days=1)).date()\n    return day.date() >= hier',
     '    return (as_of - day) < timedelta(days=1)'),

    # ── les deux bords du raisonnement ──────────────────────────────
    ("la porte de sortie est condamnee : `--publier-quand-meme` "
     "n'ouvre plus rien, et le seul contournement possible redevient "
     "l'edition du code — qui ne laisse aucune trace",
     SCORE,
     '    if forcer:\n        return True',
     '    if False:\n        return True'),

    ("`hier` est calcule depuis la journee NOTEE et non depuis `as_of` : "
     "la comparaison se compare a elle-meme et rend toujours vrai",
     SCORE,
     '    hier = (as_of - timedelta(days=1)).date()',
     '    hier = (day - timedelta(days=1)).date()'),

    ("⭐ le drapeau est DECLARE mais plus JAMAIS LU : `--publier-quand-meme` "
     "existe dans l'aide, ne fait rien, et le garde-fou a l'air d'avoir "
     "une porte de sortie qu'il n'a pas",
     SCORE,
     '    republier = doit_republier(day, as_of, args.publier_quand_meme)',
     '    republier = doit_republier(day, as_of)'),

    ("le drapeau disparait de l'analyseur d'arguments : le garde-fou "
     "n'a plus de porte de sortie DOCUMENTEE",
     SCORE,
     '    ap.add_argument("--publier-quand-meme", action="store_true",',
     '    ap.add_argument("--publier-quand-meme-x", action="store_true",'),
]


def jouer(banc: str) -> bool:
    r = subprocess.run([sys.executable, str(ICI / banc)],
                       capture_output=True, text=True, cwd=str(ICI),
                       env=HARNAIS.env_banc(ICI))
    return r.returncode == 0


def main() -> int:
    if not jouer(BANC):
        print("⛔ le banc est DEJA rouge sans mutation : rien a prouver.")
        return 2
    print(f"✅ banc de reference vert ({BANC})\n")
    sauvegardes = {}
    survivantes = []
    try:
        for i, (titre, fichier, avant, apres) in enumerate(MUTATIONS, 1):
            if fichier not in sauvegardes:
                sauvegardes[fichier] = HARNAIS.garder(fichier)
            src = sauvegardes[fichier]
            if avant not in src:
                print(f"{i:2}. ⛔ MOTIF INTROUVABLE : {titre}")
                survivantes.append(titre)
                continue
            fichier.write_text(src.replace(avant, apres, 1), encoding="utf-8")
            try:
                passe = jouer(BANC)
            finally:
                fichier.write_text(src, encoding="utf-8")
            if passe:
                print(f"{i:2}. ❌ SURVIT : {titre}")
                survivantes.append(titre)
            else:
                print(f"{i:2}. ✅ tuee : {titre}")
    finally:
        for fichier, src in sauvegardes.items():
            HARNAIS.rendre(fichier, src)
    print("\n" + "═" * 66)
    print(f"  {len(MUTATIONS) - len(survivantes)}/{len(MUTATIONS)} mutations tuees")
    if survivantes:
        print("❌ mutations SURVIVANTES :")
        for s in survivantes:
            print(f"   · {s}")
        return 1
    print("✅ toutes les mutations sont tuees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
