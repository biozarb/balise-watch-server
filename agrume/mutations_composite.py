#!/usr/bin/env python3
"""Casser `composite.py` de sept façons, et exiger que le banc le voie.

⛔ POURQUOI CE FICHIER EXISTE. Le 26/08, 21 bancs de la phase B sont
passés du premier coup et QUATRE ne tenaient rien — seule la mutation
l'a dit. Les bancs de α et du cisaillement décident de ce que le produit
SERT : ils ne peuvent pas être crus sur parole.

Chaque mutation est une substitution de texte dans le source, suivie
d'un `test_composite.py`. Le banc DOIT tomber. Restauration en
`finally`, toujours — un fichier laissé muté serait pire que pas de
mutation du tout.

    python3 agrume/mutations_composite.py
"""
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
CIBLE = ICI / "composite.py"
BANC = ICI / "test_composite.py"

MUTATIONS = [
    ("α remis à 1 — le remplacement d'AROME par PI, l'erreur d'origine",
     "ALPHA_MELANGE = 0.5", "ALPHA_MELANGE = 1.0"),
    ("α mis à 0 — PI n'entre plus du tout",
     "ALPHA_MELANGE = 0.5", "ALPHA_MELANGE = 0.0"),
    ("cisaillement neutralisé — retour à l'extension constante",
     "CISAILLEMENT_10_20 = 0.766", "CISAILLEMENT_10_20 = 1.0"),
    ("cisaillement CONSTANT sous 20 m — la marche au ras du sol que la "
     "continuité doit refuser",
     "    if z >= haut:\n        return 1.0",
     "    if z >= haut:\n        return CISAILLEMENT_10_20"),
    ("`poids_pi` oublie α et rend la rampe nue",
     "    a = ALPHA_MELANGE if alpha is None else float(alpha)\n"
     "    return a * rampe_pi(minute)",
     "    return rampe_pi(minute)"),
    ("`poids_pi` ignore l'argument `alpha` des bancs — l'invariant à "
     "α = 1 ne serait plus vérifiable",
     "    a = ALPHA_MELANGE if alpha is None else float(alpha)",
     "    a = ALPHA_MELANGE"),
    # ⚠️ MUTATION REMPLACÉE. La première écrivait `z > haut` au lieu de
    # `z >= haut` — et le banc restait vert À RAISON : la formule
    # linéaire rend EXACTEMENT 1 à z = haut, donc les deux branches
    # coïncident. C'était une mutation NULLE, pas un banc faible.
    # *Une mutation qui ne change pas le comportement ne teste rien, et
    # elle se lit exactement comme un banc qui ne tient pas.*
    ("la rampe du cisaillement n'atteint plus 1 à 20 m — le niveau où Δ "
     "est MESURÉ serait rogné, et la continuité rompue",
     "    f = (z - bas) / (haut - bas)",
     "    f = (z - bas) / (haut - bas + 10.0)"),
    ("le diagnostic cesse de publier α",
     "        alpha_melange=ALPHA_MELANGE,", "        "),
]


def main():
    source = CIBLE.read_text(encoding="utf-8")
    echecs = []
    try:
        for i, (nom, avant, apres) in enumerate(MUTATIONS, 1):
            if avant not in source:
                echecs.append(f"nº {i} : motif INTROUVABLE — {nom}")
                print(f"  ⛔ nº {i} : motif introuvable, mutation impossible")
                continue
            CIBLE.write_text(source.replace(avant, apres, 1), encoding="utf-8")
            r = subprocess.run([sys.executable, str(BANC)],
                               capture_output=True, text=True, cwd=str(ICI))
            if r.returncode == 0:
                echecs.append(f"nº {i} : le banc RESTE VERT — {nom}")
                print(f"  ⛔ nº {i} : BANC VERT SUR UN CODE CASSÉ — {nom}")
            else:
                print(f"  ✅ nº {i} : le banc tombe — {nom}")
    finally:
        CIBLE.write_text(source, encoding="utf-8")
        print(f"\n  ⓘ {CIBLE.name} restauré")

    r = subprocess.run([sys.executable, str(BANC)],
                       capture_output=True, text=True, cwd=str(ICI))
    if r.returncode != 0:
        print("  ⛔⛔ le banc ne repasse PAS après restauration")
        return 2
    print("  ✅ et le banc repasse vert après restauration")

    if echecs:
        print(f"\n⛔ {len(echecs)} mutation(s) non détectée(s) :")
        for e in echecs:
            print(f"    · {e}")
        return 1
    print(f"\n✅ les {len(MUTATIONS)} mutations font toutes tomber le banc")
    return 0


if __name__ == "__main__":
    sys.exit(main())
