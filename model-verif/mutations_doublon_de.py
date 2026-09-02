#!/usr/bin/env python3
"""Rejoue `test_score.py` contre des variantes CASSÉES de l'exclusion
des doublons d'inscription (lot L17, 27/08/2026).

⛔ Un banc vert ne prouve rien tant qu'on n'a pas vu ce qui le fait
rougir. Et la faute qu'on craint ici ne fait pas tomber la nuit : elle
laisse le double comptage EN PLACE — le classement continue de publier
des cases qui n'existent que grâce à une seconde inscription, et le
journal annonce sereinement « 0 balise-jour écarté ». C'est exactement
l'état d'AVANT le lot, avec en plus la conviction que le problème est
traité.

L'autre faute, symétrique : écarter le REPRÉSENTANT au lieu du doublon,
ou les deux — la case se tait alors au lieu de se dédoublonner, et le
produit perd des zones entières sans qu'aucune erreur ne remonte.

⚠️ JOUER PAR TRANCHES COURTES (`python3 mutations_doublon_de.py 1 5`) :
un processus TUÉ — y compris par le plafond de 45 s d'un appel
`device_bash` — ne passe pas par son `finally` et laisse `score.py`
MUTÉ sur le disque. Vécu quatre fois le 27/08 (L3, L6). Contrôle
d'intégrité après coup : chaque motif `avant` doit être retrouvé dans
son fichier.

    python3 mutations_doublon_de.py
"""
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent

# ⛔ (02/09/2026) copie d'origine sur le disque + sha256 + purge du
# bytecode, pour TOUS les harnais — voir `model-verif/harnais.py`.
sys.path.insert(0, str(ICI))
import harnais as HARNAIS  # noqa: E402
CIBLE = ICI / "score.py"
BANC = ICI / "test_score.py"

MUTATIONS = [
    # ── LA BRIQUE UNIQUE ────────────────────────────────────────────
    ("`est_doublon` rend toujours False : la colonne est lue, le test "
     "existe, le journal dit « 0 écarté » — et rien n'est écarté. "
     "C'est l'état d'avant le lot, avec la conviction en plus",
     "    return bool(zone and zone.get(COL_DOUBLON))",
     "    return False"),

    ("`est_doublon` rend toujours True : TOUTES les balises sortent du "
     "classement, y compris les représentants — le produit se tait",
     "    return bool(zone and zone.get(COL_DOUBLON))",
     "    return zone is not None"),

    ("la colonne change de nom d'UN SEUL côté : `score.py` lit "
     "`doublon` là où le SQL écrit `doublon_de`, et personne n'est "
     "jamais écarté",
     'COL_DOUBLON = "doublon_de"',
     'COL_DOUBLON = "doublon"'),

    # ── LE CLASSEMENT ───────────────────────────────────────────────
    ("le doublon n'est plus écarté du CLASSEMENT : le quorum "
     "`MIN_STATIONS_ZONE` recompte la seconde inscription comme une "
     "troisième station, et les 80 à 92 cases fantômes reviennent",
     "        if est_doublon(z):\n"
     "            # ⛔ LE GESTE DU LOT L17. Écarter la balise-jour ENTIÈRE,",
     "        if False:\n"
     "            # ⛔ LE GESTE DU LOT L17. Écarter la balise-jour ENTIÈRE,"),

    ("l'exclusion est INVERSÉE : on garde le doublon et on écarte tout "
     "le reste",
     "            n_doublons += 1\n            continue\n"
     "        if d.get(\"err_vec_med\") is None:",
     "            n_doublons += 1\n        else:\n            continue\n"
     "        if d.get(\"err_vec_med\") is None:"),

    ("seule la case FINE est dédoublonnée : les échelons agrégés "
     "(massif, forme, global) continuent de compter la seconde "
     "inscription — et ce sont eux que l'écran affiche quand la case "
     "fine se tait. Le compteur du journal, lui, annonce le bon "
     "chiffre : le rapport a l'air juste",
     '            n_doublons += 1\n            continue\n'
     '        if d.get("err_vec_med") is None:\n            continue\n'
     '        for zid, level in fallback_chain(z):\n',
     '            n_doublons += 1\n'
     '        if d.get("err_vec_med") is None:\n            continue\n'
     '        for zid, level in fallback_chain(z):\n'
     '            if est_doublon(z) and level == "basin_landform":\n'
     '                continue\n'),

    # ── LA MÉMOIRE LONGUE ───────────────────────────────────────────
    ("les accumulateurs ne sont plus dédoublonnés : `model_character` "
     "continue de compter deux fois pendant une demi-vie de 30 jours, "
     "APRÈS que le classement a cessé de le faire",
     "        if est_doublon(z):\n"
     "            # ⛔ LA MÉMOIRE LONGUE AUSSI, et ce n'est pas un doublon de",
     "        if False:\n"
     "            # ⛔ LA MÉMOIRE LONGUE AUSSI, et ce n'est pas un doublon de"),

    # ── LE COMPTAGE ─────────────────────────────────────────────────
    ("l'exclusion cesse de se compter : le journal n'annonce plus rien, "
     "et une purge silencieuse devient un fait acquis que personne ne "
     "peut plus contester",
     "            n_doublons += 1\n            continue",
     "            continue"),
]


def joue(debut: int = 1, fin: int = len(MUTATIONS)) -> int:
    rouges = 0
    origine = HARNAIS.garder(CIBLE)
    for i, (nom, avant, apres) in enumerate(MUTATIONS, 1):
        if not (debut <= i <= fin):
            continue
        if avant not in origine:
            print(f"  ⛔ {i:>2}. {nom}\n       MOTIF INTROUVABLE — la "
                  f"mutation n'a rien muté, donc elle n'a rien prouvé.")
            rouges += 1
            continue
        try:
            CIBLE.write_text(origine.replace(avant, apres, 1),
                             encoding="utf-8")
            r = subprocess.run([sys.executable, str(BANC)],
                               capture_output=True, text=True, cwd=ICI,
                               env=HARNAIS.env_banc(ICI))
            if r.returncode == 0:
                print(f"  ❌ {i:>2}. {nom}\n       LE BANC RESTE VERT — il "
                      f"ne tient pas cette propriété.")
                rouges += 1
            else:
                l = [x.strip() for x in r.stdout.splitlines()
                     if x.strip().startswith("❌")]
                if not l:
                    l = [x.strip() for x in r.stderr.splitlines()[-2:]]
                print(f"  ✅ {i:>2}. {nom}\n       {l[0] if l else 'banc rouge'}"
                      + (f" (+{len(l) - 1} autres)" if len(l) > 1 else ""))
        finally:
            HARNAIS.rendre(CIBLE, origine)
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations de l'exclusion des doublons (lot L17) — chaque "
          "ligne doit être VERTE,\n  c'est-à-dire : le banc a bien ROUGI "
          "sur la faute.\n")
    d = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    f = int(sys.argv[2]) if len(sys.argv) > 2 else len(MUTATIONS)
    n = joue(d, f)
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} non vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
