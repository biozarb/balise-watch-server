#!/usr/bin/env python3
"""Rejoue le banc contre des variantes CASSÉES du contrôle de pente et du
registre (10/09/2026 — lot REGISTRE ET PENTE).

⛔ Un banc vert ne prouve rien tant qu'on n'a pas vu ce qui le fait
rougir. Et les fautes qu'on craint ici ont toutes le même visage : le
contrôle continue de tourner à 07:30, rend 0, et SE TAIT — la nuit
précisément où il devrait parler. Les cinq premières sont celles que le
prompt du lot exigeait de voir ; les suivantes sont celles que
l'écriture a fait apparaître.

    python3 mutations_controle_quotidien.py          # tout
    python3 mutations_controle_quotidien.py 1 5      # par tranches
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import harnais as HARNAIS  # noqa: E402

CTRL = ICI / "controle_quotidien.py"
REG = ICI / "registre_nuit.py"
BANC = ICI / "test_controle_quotidien.py"

MUTATIONS = [
    # ══ les cinq du prompt ═══════════════════════════════════════════
    ("⭐ une pente calculée sur des relevés NON comparables : le rejeu "
     "diurne (cache chaud, machine vide) entre dans la série",
     CTRL, BANC,
     '    return (r.get("lancement") == "timer"\n            and r.get("result") == "success"',
     '    return (r.get("result") == "success"'),

    ("⭐ un jalon ABSENT est lu comme un ZÉRO : une nuit tuée avant le "
     "régime fabrique une chute de 2 000 Mo, la pente s'effondre, silence",
     CTRL, BANC,
     '        if not comparable(r) or r.get(cle) is None:\n            continue\n'
     '        out.append((date.fromisoformat(r["jour"]), float(r[cle])))',
     '        if not comparable(r):\n            continue\n'
     '        out.append((date.fromisoformat(r["jour"]), float(r.get(cle) or 0)))'),

    ("⭐ un run en ÉCHEC compte comme une nuit normale : la nuit morte à "
     "2 400 s (code 124) devient un plateau à 2 400 dans une série qui monte",
     CTRL, BANC,
     '            and r.get("result") == "success"\n'
     '            and r.get("exec_status") == 0\n',
     ''),

    ("⭐ le seuil est lu EN DUR (2 800) au lieu de `MAX_RSS_MO` : le jour "
     "où score.py change de seuil, le contrôle vise l'ancien",
     CTRL, BANC,
     '             seuil_mo: float = MAX_RSS_MO) -> list[dict]:',
     '             seuil_mo: float = 2800) -> list[dict]:'),

    ("⭐ le contrôle CRIE sur une pente négative : un run qui se range "
     "après un correctif ferait un ticket tous les matins",
     CTRL, BANC,
     '    if pente is None or pente <= 0:\n        return None\n    if dernier >= cible:',
     '    if pente is None or pente == 0:\n        return None\n    if dernier >= cible:'),

    # ══ celles que l'écriture a fait apparaître ══════════════════════
    ("la pente redevient une MOYENNE des différences : une marche (un lot "
     "qui ajoute une série) refabrique la fausse échéance de la jauge R2",
     CTRL, BANC,
     '    return _quantile(vitesses, q)',
     '    return sum(vitesses) / len(vitesses)'),

    ("la pente est « dernier moins premier » : une oscillation sans "
     "tendance rend une pente, une fuite lente en rend une fausse",
     CTRL, BANC,
     '    vitesses = [(v1 - v0) / max(1, (d1 - d0).days)\n'
     '                for (d0, v0), (d1, v1) in zip(pts, pts[1:])]\n'
     '    return _quantile(vitesses, q)',
     '    return (pts[-1][1] - pts[0][1]) / max(1, (pts[-1][0] - pts[0][0]).days)'),

    ("l'horizon n'est plus regardé : +5 s/nuit vers un garde à six mois "
     "fait un constat chaque matin — le contrôle bavard du ⚠️ 3 du 09/09",
     CTRL, BANC,
     '    if f_tard is None or (f_tard - jour).days > horizon_j:\n        return None',
     '    if f_tard is None:\n        return None'),

    ("le garde visé est celui de la PREMIÈRE nuit, pas de la dernière : "
     "remonté hier, on annoncerait encore le franchissement d'hier",
     CTRL, BANC,
     '    dernier = comparables[-1]',
     '    dernier = comparables[0]'),

    ("moins de cinq relevés suffisent : trois points ne séparent pas une "
     "marche d'une croissance, et le contrôle tranche quand même",
     CTRL, BANC,
     'MINI_RELEVES = int(os.environ.get("BW_CONTROLE_MINI_RELEVES", "5"))',
     'MINI_RELEVES = int(os.environ.get("BW_CONTROLE_MINI_RELEVES", "3"))'),

    ("deux relevés le même jour comptent deux fois : un rejeu + le timer "
     "font une différence à zéro jour, divisée par 1, et la série ment",
     CTRL, BANC,
     '    vus: dict = {}\n    for d, v in pts:\n        vus[d] = v\n    pts = sorted(vus.items())',
     '    pts = sorted(pts, key=lambda p: p[0])'),

    # ══ le registre ══════════════════════════════════════════════════
    ("⭐ le registre n'écrit plus le pic de SWAP — la colonne qui explique "
     "pourquoi la durée monte alors que la mémoire ne monte plus",
     REG, BANC,
     '            sp = _mo_systemd(m.group(3))\n            if sp is not None:\n'
     '                r["swap_peak_mo"] = sp',
     '            pass'),

    ("les unités de systemd sont lues en décimal : 2G = 2 000 Mo, 2,4 % "
     "d'erreur au moment précis où l'on frôle la RAM",
     REG, BANC,
     '"G": 1024,',
     '"G": 1000,'),

    ("une nuit OOM est écrite avec `exec_status: 0` : elle devient une "
     "nuit comparable, courte, et la pente redescend",
     REG, BANC,
     '    if code is not None:\n        r["exec_status"] = code',
     '    r["exec_status"] = code or 0'),

    ("le chien de garde rétro est celui du JOUR du déploiement : la nuit "
     "du 03/09, morte sous 40 min, se lit comme morte sous 65",
     REG, BANC,
     '        if jour > depuis:\n            g = s',
     '        if jour >= depuis:\n            g = s'),

    ("un rejeu de l'après-midi est marqué `timer` : il entre dans la pente",
     REG, BANC,
     '    r["lancement"] = "timer" if TIMER_UTC_DE <= hm <= TIMER_UTC_A else "manuel"',
     '    r["lancement"] = "timer"'),

    ("le rétro-remplissage écrit deux fois le même run quand on le rejoue",
     REG, BANC,
     '    neuves = [r for r in lignes if r.get("debut_utc") not in deja]',
     '    neuves = list(lignes)'),
]


def joue(debut: int, fin: int) -> int:
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
                lignes = [l.strip() for l in r.stderr.splitlines()
                          if l.startswith("FAIL:") or l.startswith("ERROR:")]
                print(f"  ✅ {i:>2}. {nom}\n       [{banc.name}] "
                      f"{lignes[0] if lignes else 'banc rouge'}"
                      + (f" (+{len(lignes) - 1} autres)" if len(lignes) > 1 else ""))
        finally:
            HARNAIS.rendre(fichier, origine)
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations du lot REGISTRE ET PENTE (10/09) — chaque ligne doit "
          "être VERTE,\n  c'est-à-dire : le banc a bien ROUGI sur la faute.\n")
    debut = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    fin = int(sys.argv[2]) if len(sys.argv) > 2 else len(MUTATIONS)
    n = joue(debut, fin)
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
