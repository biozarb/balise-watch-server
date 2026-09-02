#!/usr/bin/env python3
"""Casser `rafraichissement.py` de trois façons — les trois défauts que
le 26/08 a produits, et qu'aucune relecture n'avait vus.

⛔ Les deux premiers ont été trouvés EN LISANT L'ÉCRAN et EN LISANT
L'OBJET PUBLIÉ SUR R2, pas au banc. Ces mutations existent pour que la
prochaine fois, le banc suffise.

    python3 agrume/mutations_rafraichissement.py
"""
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent

# ⛔ (02/09/2026) copie d'origine sur le disque + sha256 + purge du
# bytecode, pour TOUS les harnais — voir `model-verif/harnais.py`.
sys.path.insert(0, str(ICI.parent / "model-verif"))
import harnais as HARNAIS  # noqa: E402
CIBLE = ICI / "rafraichissement.py"
BANC = ICI / "test_rafraichissement.py"

MUTATIONS = [
    ("le manifeste cesse de publier α — le champ existe dans le "
     "diagnostic mais n'arrive jamais au client",
     "            alpha_melange=self.diagnostic[\"alpha_melange\"],", "            "),
    ("le régime se relit sur le POIDS au lieu de la RAMPE — « ATTÉNUÉE » "
     "réapparaît à toutes les échéances, rampe pleine comprise",
     "            r = rampe_pi(minute)", "            r = w"),
    ("la condition de validité redevient « poids_pi = 1 », que le poids "
     "servi n'atteint plus jamais",
     "                \"⚠️ la table `niveaux` décrit le régime tant que PI est \"\n"
     "                \"PLEINEMENT DISPONIBLE, c'est-à-dire jusqu'à 4 h. Au-delà, \"",
     "                \"⚠️ la table `niveaux` décrit le régime à `poids_pi = 1`, \"\n"
     "                \"c'est-à-dire jusqu'à 4 h. Au-delà, \""),
    # ── L5 (27/08/2026) : le désaccord AROME/PI ──
    ("le manifeste cesse de publier le désaccord — le champ existe dans "
     "le diagnostic mais n'arrive jamais au client, exactement le "
     "défaut du 26/08 sur `alpha_melange`",
     "            desaccord=dict(self.diagnostic[\"desaccord\"]),", "            "),
    ("la provenance cesse d'attacher le désaccord aux blocs `arome+pi` "
     "— l'écran n'aurait plus rien à afficher à côté de `poids_pi`",
     "                    **champs_desaccord)\n            elif r > 0.0:",
     "                    )\n            elif r > 0.0:"),
]


def main():
    source = HARNAIS.garder(CIBLE)
    echecs = []
    try:
        for i, (nom, avant, apres) in enumerate(MUTATIONS, 1):
            if avant not in source:
                echecs.append(f"nº {i} : motif INTROUVABLE — {nom}")
                print(f"  ⛔ nº {i} : motif introuvable")
                continue
            CIBLE.write_text(source.replace(avant, apres, 1), encoding="utf-8")
            r = subprocess.run([sys.executable, str(BANC)],
                               capture_output=True, text=True, cwd=str(ICI),
                               env=HARNAIS.env_banc(ICI))
            if r.returncode == 0:
                echecs.append(f"nº {i} : le banc RESTE VERT — {nom}")
                print(f"  ⛔ nº {i} : BANC VERT SUR UN CODE CASSÉ — {nom}")
            else:
                print(f"  ✅ nº {i} : le banc tombe — {nom}")
    finally:
        HARNAIS.rendre(CIBLE, source)
        print(f"\n  ⓘ {CIBLE.name} restauré")

    r = subprocess.run([sys.executable, str(BANC)],
                       capture_output=True, text=True, cwd=str(ICI),
                       env=HARNAIS.env_banc(ICI))
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
