#!/usr/bin/env python3
"""Casser l'extension multi-sources de `agrume_fcst.py` (lot L7), et
exiger que `test_agrume_fcst.py` le voie.

⛔ POURQUOI CE FICHIER EXISTE. Tant que `SOURCE_NOTEE` était UNE chaîne
("pioupiou"), écrire `"source": SOURCE_NOTEE` sur une ligne de l'archive
et écrire `"source": b.get("source")` rendaient EXACTEMENT le même
résultat — aucun banc écrit avant le lot L7 ne pouvait distinguer les
deux formes. Depuis que `SOURCE_NOTEE` est un ensemble de sources, la
première écrit un `frozenset` (ou un membre arbitraire de l'ensemble
selon l'implémentation) au lieu de la vraie source de la balise — un
mensonge crédible et silencieux sur CHAQUE ligne non-pioupiou.

    python3 model-verif/mutations_agrume_fcst_l7.py
"""
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
CIBLE = ICI / "agrume_fcst.py"
BANC = ICI / "test_agrume_fcst.py"
#: ⚠️ Mutation nº 2 (le filtre PI) n'est couverte par AUCUN banc de
#: `test_agrume_fcst.py`  — `delta_20m()` n'a de banc que dans
#: `test_agrume_pi_fcst.py` (test `test_source_elargie_sans_correction_pi`,
#: ajouté par ce même lot). Deux bancs, donc, pas un.
BANC_PI = ICI / "test_agrume_pi_fcst.py"

MUTATIONS = [
    ("chaque ligne écrit SOURCE_NOTEE (l'ensemble) au lieu de la vraie "
     "source de la balise — le bug exact que le lot L7 a trouvé et "
     "corrigé",
     "            # ⛔ `b.get(\"source\")`, JAMAIS `SOURCE_NOTEE` — cf. l'arbitrage\n"
     "            # sur SOURCE_NOTEE ci-dessus. Un ensemble n'est pas une valeur.\n"
     "            \"source\": b.get(\"source\"),",
     "            \"source\": SOURCE_NOTEE,"),
    ("le filtre PI redevient une égalité stricte — `not in` sur un "
     "ensemble d'un seul membre coïncide avec `!=`, mais dès que "
     "SOURCE_NOTEE porte plusieurs sources l'égalité stricte n'admet "
     "plus AUCUNE balise",
     "    for k, b in enumerate(col.balises):\n"
     "        if b.get(\"source\") not in SOURCE_NOTEE:\n"
     "            continue\n"
     "        kpi = ix_pi.get(str(b[\"id\"]))",
     "    for k, b in enumerate(col.balises):\n"
     "        if b.get(\"source\") != SOURCE_NOTEE:\n"
     "            continue\n"
     "        kpi = ix_pi.get(str(b[\"id\"]))"),
    ("le filtre de `lignes()` redevient une égalité stricte — même "
     "défaut, sur le flux qui alimente l'archive publiée",
     "    for k, b in enumerate(col.balises):\n"
     "        if b.get(\"source\") not in SOURCE_NOTEE:\n"
     "            continue\n"
     "        d_balise = None if delta is None else delta.get(k)",
     "    for k, b in enumerate(col.balises):\n"
     "        if b.get(\"source\") != SOURCE_NOTEE:\n"
     "            continue\n"
     "        d_balise = None if delta is None else delta.get(k)"),
    ("metar rentre dans SOURCE_NOTEE — l'audit PS3 est explicite : "
     "colonne utile (obsmetar/tau), mais aucun score AGRUME",
     "SOURCE_NOTEE = frozenset({\"pioupiou\", \"windsmobi\", \"infoclimat\", \"mf\",\n"
     "                          \"aemet\"})",
     "SOURCE_NOTEE = frozenset({\"pioupiou\", \"windsmobi\", \"infoclimat\", \"mf\",\n"
     "                          \"aemet\", \"metar\"})"),
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
            r_pi = subprocess.run([sys.executable, str(BANC_PI)],
                                  capture_output=True, text=True, cwd=str(ICI))
            if r.returncode == 0 and r_pi.returncode == 0:
                echecs.append(f"nº {i} : les DEUX bancs restent verts — {nom}")
                print(f"  ⛔ nº {i} : BANCS VERTS SUR UN CODE CASSÉ — {nom}")
            else:
                lequel = ('agrume_fcst' if r.returncode else '') +                          ('+agrume_pi_fcst' if r_pi.returncode else '')
                print(f"  ✅ nº {i} : le banc tombe ({lequel.strip('+')}) — {nom}")
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
