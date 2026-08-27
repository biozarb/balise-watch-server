#!/usr/bin/env python3
"""Casser l'identité multi-sources de `freeze_balises.py` (lot L7), et
exiger que `test_freeze_balises.py` le voie.

⛔ POURQUOI CE FICHIER EXISTE. Avant le lot L7, `fusionner()` indexait
`connues` par `id` seul — vrai sans risque tant que l'axe ne portait
QUE des identifiants Pioupiou (une seule autorité de numérotation).
Depuis que l'axe accueille windsmobi/infoclimat/mf/aemet/metar, revenir
à un index par `id` seul ferait fusionner en silence deux balises de
réseaux différents partageant le même id brut — une balise disparaîtrait
de l'axe SANS AUCUNE ERREUR, exactement le défaut que la discipline
d'ajout seul existe pour empêcher.

    python3 agrume/mutations_freeze_balises_l7.py
"""
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
CIBLE = ICI / "freeze_balises.py"
BANC = ICI / "test_freeze_balises.py"

MUTATIONS = [
    ("`connues` revient à un index par `id` seul — deux réseaux "
     "différents partageant le même id brut fusionneraient en silence",
     "connues = {_identite(b): dict(b) for b in existantes}",
     "connues = {b[\"id\"]: dict(b) for b in existantes}"),
    ("la recherche de l'ancienne balise revient à `id` seul — même défaut, "
     "côté lecture cette fois",
     "        cle = _identite(c)\n        ancienne = connues.get(cle)",
     "        cle = c[\"id\"]\n        ancienne = connues.get(cle)"),
    ("le nouveau candidat est ENREGISTRÉ sous `id` seul — la moitié du "
     "défaut suffit à perdre une balise dès le premier gel",
     "            connues[cle] = dict(c, position_suspecte=False,",
     "            connues[c[\"id\"]] = dict(c, position_suspecte=False,"),
    ("`_identite` ignore la source et ne renvoie que l'id — la fonction "
     "existe mais ne fait plus rien",
     "    return (b.get(\"source\") or \"pioupiou\", str(b[\"id\"]))",
     "    return str(b[\"id\"])"),
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
        print(r.stdout[-2000:])
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
