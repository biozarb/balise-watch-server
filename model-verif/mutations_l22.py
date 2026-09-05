#!/usr/bin/env python3
"""Rejoue les bancs contre des variantes CASSÉES du lot L22a — AGRUME à +48 h
par une ligne SŒUR lue dans `ecmwf_ifs025` (05/09/2026).

⛔ CE QU'ON CRAINT ICI, ET CE N'EST PAS CE QU'ON CRAIGNAIT AU L20.
Le +24 h copiait un modèle de la MÊME famille sous une autre lecture ; le
+48 h copie un AUTRE MODÈLE, dans un flux partitionné, sous un run que
l'archive ne porte pas en clair. Les six façons de se tromper en silence :

  · voler de la fraîcheur (garder le `fetched_at` d'AGRUME) ;
  · déborder vers le bas (des heures < 48 h sous l'étiquette +48 h) ;
  · déborder vers le HAUT — c'est le défaut que ce lot a trouvé dans le
    L20 : sans borne, la sœur +24 h emporte les heures 48-51 d'`arome_r2`
    et fabrique une SECONDE ligne AGRUME à +48 h, faite d'AROME ;
  · stamper l'heure de NOTRE APPEL (03:19 Z) au lieu du run IFS (18 Z) ;
  · prendre pour source n'importe quelle ligne du fichier — `fcst/` en
    porte NEUF modèles, pas un ;
  · donner deux voix à l'IFS dans le mélange (la sœur EST la ligne
    `ecmwf_ifs025` recopiée : deux membres numériquement identiques).

⚠️ Le motif à muter doit exister TEL QUEL dans le fichier : une
mutation dont le motif est introuvable n'a rien muté, donc rien prouvé,
et ce script le dit en rouge plutôt que de la compter verte.

    python3 mutations_l22.py            # tout
    python3 mutations_l22.py 1 4        # par tranches
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import harnais as HARNAIS  # noqa: E402

AGRUME = ICI / "agrume_fcst.py"
MELANGE = ICI / "melange.py"
B_AGRUME = ICI / "test_agrume_fcst.py"
B_MELANGE = ICI / "test_melange.py"

MUTATIONS = [
    ("⭐⭐ la sœur +48 h garde le fetched_at d'AGRUME : l'échéance ment de "
     "3 h et se lit comme de l'AGRUME frais",
     AGRUME, B_AGRUME,
     '            "fetched_at": a["fetched_at"],\n            "t0": t0a, "step_s": pas,',
     '            "fetched_at": r["fetched_at"],\n            "t0": t0a, "step_s": pas,'),

    ("la sœur +48 h déborde vers le bas : elle emporte les heures < 48 h, "
     "et les classes +6 h et +24 h changent sans le dire",
     AGRUME, B_AGRUME,
     "H48_DEBUT = 48\n",
     "H48_DEBUT = 0\n"),

    ("⭐⭐ la sœur +24 h n'est plus bornée en haut : ses heures 48-51 "
     "fabriquent une SECONDE ligne AGRUME à +48 h, faite d'AROME",
     AGRUME, B_AGRUME,
     "H24_FIN = 48\n",
     "H24_FIN = 999\n"),

    ("⭐ `agrume_h48_run` porte l'heure de NOTRE APPEL (03:19 Z) au lieu du "
     "run IFS (18 Z) : l'archive annonce un run ECMWF qui n'existe pas",
     AGRUME, B_AGRUME,
     '    ri = a.get("run_init")\n',
     '    ri = a.get("run_init") and a["t0"] + 3 * 3600\n'),

    ("la sœur +48 h ne se déclare plus copie : plus rien ne dit que ces "
     "heures ne sont pas de l'AGRUME calculé",
     AGRUME, B_AGRUME,
     '            f"{prefixe}_copie": True,\n',
     '            f"{prefixe}_copie": False,\n'),

    ("⭐ n'importe quelle ligne du fichier sert de source : `fcst/` en porte "
     "NEUF modèles, et gfs_global passerait pour de l'IFS",
     AGRUME, B_AGRUME,
     '        if a.get("model") == source and a.get("speed"):',
     '        if a.get("speed"):'),

    ("une sœur peut se prolonger elle-même : une copie de copie, dont le "
     "run, l'échéance et la source se contredisent",
     AGRUME, B_AGRUME,
     "    declarations = tuple(f\"{c['prefixe']}_copie\" for c in CLASSES_SOEURS.values())",
     '    declarations = (f"{prefixe}_copie",)'),

    ("⭐⭐ le mélange donne DEUX voix à l'IFS à +48 h (la sœur EST la ligne "
     "ecmwf_ifs025 recopiée)",
     MELANGE, B_MELANGE,
     "COPIES_PAR_LEAD: dict[int, tuple[str, str]] = {\n"
     '    24: ("agrume_h24_copie", "agrume_h24_source"),\n'
     '    48: ("agrume_h48_copie", "agrume_h48_source"),\n'
     "}\n",
     "COPIES_PAR_LEAD: dict[int, tuple[str, str]] = {}\n"),

    ("la règle des copies s'applique à TOUTES les échéances : AGRUME perd "
     "aussi le +6 h, la seule où il est du calcul et pas une copie",
     MELANGE, B_MELANGE,
     "    champs = COPIES_PAR_LEAD.get(lead) if lead is not None else None",
     "    champs = COPIES_PAR_LEAD.get(lead or 48)"),

    ("le mélange exclut la copie même quand le modèle copié est ABSENT : "
     "la seule ligne qui porte ces heures perd sa voix pour rien",
     MELANGE, B_MELANGE,
     '                           and r.get(champ_source) in presents}',
     '                           }'),
]


def joue(debut: int = 1, fin: int | None = None) -> int:
    """⚠️ `debut`/`fin` NE SONT PAS UN CONFORT — voir `mutations_l9c_vec.py` :
    un harnais tué laisse le fichier muté, jouer par tranches courtes."""
    fin = len(MUTATIONS) if fin is None else fin
    rouges = 0
    for i, (nom, fichier, banc, avant, apres) in enumerate(MUTATIONS, 1):
        if not (debut <= i <= fin):
            continue
        origine = HARNAIS.garder(fichier)
        if avant not in origine:
            print(f"  ⛔ {i:>2}. {nom}\n       MOTIF INTROUVABLE dans "
                  f"{fichier.name} — la mutation n'a rien muté, donc elle "
                  f"n'a rien prouvé. (Le code a bougé : réécrire ce motif.)")
            rouges += 1
            HARNAIS.rendre(fichier, origine)
            continue
        try:
            fichier.write_text(origine.replace(avant, apres, 1),
                               encoding="utf-8")
            r = subprocess.run([sys.executable, str(banc)],
                               capture_output=True, text=True, cwd=ICI,
                               env=HARNAIS.env_banc(ICI))
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
            HARNAIS.rendre(fichier, origine)
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations du lot L22a — AGRUME à +48 h par l'IFS. Chaque "
          "ligne doit être VERTE,\n  c'est-à-dire : le banc a bien ROUGI "
          "sur la faute.\n")
    debut = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    fin = int(sys.argv[2]) if len(sys.argv) > 2 else len(MUTATIONS)
    n = joue(debut, fin)
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
