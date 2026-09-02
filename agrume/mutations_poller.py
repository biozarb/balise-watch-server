#!/usr/bin/env python3
"""Casser `poller.py` de six façons, et exiger que le banc le voie.

⛔ La fenêtre de guet décide de la FRAÎCHEUR d'AGRUME, c'est-à-dire de
la seule chose que le produit apporte. Un banc qui ne tiendrait rien
laisserait passer une demi-heure de retard sans qu'aucune ligne ne
bouge — et personne ne le verrait, puisque le run finit toujours par
être daté.

    python3 agrume/mutations_poller.py
"""
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent

# ⛔ (02/09/2026) copie d'origine sur le disque + sha256 + purge du
# bytecode, pour TOUS les harnais — voir `model-verif/harnais.py`.
sys.path.insert(0, str(ICI.parent / "model-verif"))
import harnais as HARNAIS  # noqa: E402
CIBLE = ICI / "poller.py"
BANC = ICI / "test_poller.py"

MUTATIONS = [
    ("la fenêtre fine redevient la constante d'avant — six réseaux sur "
     "huit repassent au back-off au moment de leur publication",
     "    d9 = obs[int(0.9 * (len(obs) - 1))]\n"
     "    return max(FENETRE_FINE_MIN, int(d9 + MARGE_APPRISE_MIN))",
     "    return FENETRE_FINE_MIN"),
    ("le quantile redevient `int(0,9 × n)` — c'est-à-dire le MAX tant "
     "que n ≤ 10, donc un run pathologique commande la fenêtre",
     "    d9 = obs[int(0.9 * (len(obs) - 1))]",
     "    d9 = obs[min(len(obs) - 1, int(0.9 * len(obs)))]"),
    ("le plancher saute : un réseau rapide raccourcirait la fenêtre "
     "sous le défaut",
     "    return max(FENETRE_FINE_MIN, int(d9 + MARGE_APPRISE_MIN))",
     "    return int(d9 + MARGE_APPRISE_MIN)"),
    ("le guet multiple prend le MIN au lieu du MAX — on lève le pied "
     "sur le paquet le plus lent, celui qui commande la chaîne",
     "    fin_fine = max(fin_de_guet_fin_min(journal_entrees, s.nom)\n"
     "                   for s in restantes)",
     "    fin_fine = min(fin_de_guet_fin_min(journal_entrees, s.nom)\n"
     "                   for s in restantes)"),
    ("le rapport remélange la rallonge @51 avec les paquets 0–24 h",
     '            ("produit A, échéances 0–24 h",\n'
     '             lambda s: ":" in s and "@" not in s),\n'
     '            ("rallonge du produit B, échéance 51 h",\n'
     '             lambda s: ":" in s and "@" in s)):',
     '            ("tout mélangé", lambda s: ":" in s),):'),
    ("le rapport cesse de publier la fenêtre apprise — elle existerait "
     "sans que personne ne puisse la contester",
     '        crier(f"  → fenêtre de guet FINE apprise : H+"',
     '        crier(f"  → (rien) H+"'),
]


def main():
    source = HARNAIS.garder(CIBLE)
    echecs = []
    try:
        for i, (nom, avant, apres) in enumerate(MUTATIONS, 1):
            if avant not in source:
                echecs.append(f"nº {i} : motif INTROUVABLE — {nom}")
                print(f"  ⛔ nº {i} : motif introuvable, mutation impossible")
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
