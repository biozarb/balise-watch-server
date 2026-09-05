#!/usr/bin/env python3
"""Rejoue les bancs contre des variantes CASSÉES du lot L20 — AGRUME à +24 h par
une ligne SŒUR lue dans arome_r2 (04/09/2026).

⛔ CE QU'ON CRAINT ICI : une ligne sœur qui garde le `fetched_at` d'AGRUME
(3 h de fraîcheur volée sous l'étiquette +24 h, 5 jours sur 13), une sœur
qui déborde sur les heures < 24 (la classe +6 h change sans le dire), ou
un mélange qui compte AGRUME deux fois (deux lignes, deux voix).

⚠️ Le motif à muter doit exister TEL QUEL dans le fichier : une
mutation dont le motif est introuvable n'a rien muté, donc rien prouvé,
et ce script le dit en rouge plutôt que de la compter verte.

    python3 mutations_l20.py            # tout
    python3 mutations_l20.py 1 5        # par tranches
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import harnais as HARNAIS  # noqa: E402

SCORE = ICI / "score.py"
MELANGE = ICI / "melange.py"
BIAIS = ICI / "biais_fin.py"
B_SCORE = ICI / "test_score.py"
B_MELANGE = ICI / "test_melange.py"
B_BIAIS = ICI / "test_biais_fin.py"

AGRUME = ICI / "agrume_fcst.py"
B_AGRUME = ICI / "test_agrume_fcst.py"

MUTATIONS = [
    ("⭐⭐ la sœur garde le fetched_at d'AGRUME : l'échéance ment quand "
     "arome_r2 est au 03 Z",
     AGRUME, B_AGRUME,
     '            "fetched_at": a["fetched_at"],\n            "t0": t0a, "step_s": pas,',
     '            "fetched_at": r["fetched_at"],\n            "t0": t0a, "step_s": pas,'),

    ("la sœur copie AUSSI les heures < 24 : la classe +6 h change",
     AGRUME, B_AGRUME,
     "H24_DEBUT = 24\n",
     "H24_DEBUT = 0\n"),

    # ⚠️ Lot L22a (05/09) : `prolonger_h24` est devenue un cas de
    # `prolonger(…, lead)`, paramétrée par `CLASSES_SOEURS`. Les deux
    # motifs ci-dessous ont été réécrits sur le corps généralisé — ils
    # mutent la MÊME propriété qu'au L20, à la même place.
    ("la sœur ne se déclare plus copie",
     AGRUME, B_AGRUME,
     '            f"{prefixe}_copie": True,\n',
     '            f"{prefixe}_copie": False,\n'),

    ("le journal dit « le même run » même quand il diffère",
     AGRUME, B_AGRUME,
     '            bilan["runs_identiques"] = (run_de(a) == r.get("agrume_run"))',
     '            bilan["runs_identiques"] = True'),

    ("⭐ le mélange compte AGRUME DEUX fois (plus de fusion)",
     MELANGE, B_MELANGE,
     """        par_modele[m] = (r if m not in par_modele
                         else fusionner(par_modele[m], r))
    return list(par_modele.values())""",
     """        par_modele[m] = r
    return list(par_modele.values())"""),

    ("la fusion laisse la SECONDE ligne écraser la première",
     MELANGE, B_MELANGE,
     "    for r, ts in ((b, tb), (a, ta)):          # b d'abord, a écrase",
     "    for r, ts in ((a, ta), (b, tb)):"),

    ("la fusion prend le fetched_at le plus FRAIS",
     MELANGE, B_MELANGE,
     '                "fetched_at": min(a["fetched_at"], b["fetched_at"])})',
     '                "fetched_at": max(a["fetched_at"], b["fetched_at"])})'),
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
    print("\n▶ mutations du lot L20 — AGRUME à +24 h. Chaque "
          "ligne doit être VERTE,\n  c'est-à-dire : le banc a bien ROUGI "
          "sur la faute.\n")
    debut = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    fin = int(sys.argv[2]) if len(sys.argv) > 2 else len(MUTATIONS)
    n = joue(debut, fin)
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
