#!/usr/bin/env python3
"""Rejoue les bancs contre des variantes CASSÉES du lot L10
(la classe courte : `agrume_court.py`, `delta_20m`, et le côté
`score.py`).

⛔ UN BANC VERT NE PROUVE RIEN TANT QU'ON N'A PAS VU CE QUI LE FAIT
ROUGIR — et ici moins qu'ailleurs. La faute centrale de ce lot (choisir
un run sur son HEURE plutôt que sur l'instant où NOS OCTETS ont été
posés) ne casse rien : elle FAIT BAISSER LES ERREURS. La classe
brillerait, le verdict serait flatteur, et rien n'aurait l'air anormal.
C'est la mutation nº 1, et c'est pour elle que ce fichier existe.

Restauration en `finally` : les fichiers reviennent à leur état
d'origine même si l'on interrompt.

    python3 mutations_classe_courte.py
"""
import os
import pathlib
import shutil
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
SCORE = ICI / "score.py"
COURT = ICI / "agrume_court.py"
FCST = ICI / "agrume_fcst.py"

#: Quel banc chaque mutation doit faire rougir. Les faire tourner TOUS
#: à chaque mutation coûterait quatre minutes par ligne ; on nomme donc
#: le banc concerné, et on le dit dans la sortie.
BANC_COURT = "test_agrume_court.py"
BANC_SCORE = "test_score.py"

MUTATIONS = [
    # ── ⛔⛔ LA FAUTE CENTRALE ────────────────────────────────────────
    ("⛔⛔ le run est choisi sur son HEURE et non sur l'instant où NOS "
     "OCTETS ont été posés — information du futur, erreurs en baisse, "
     "rien d'anormal à l'œil",
     COURT, BANC_COURT,
     '    dispo = [(run, pose) for run, pose in runs.items() if pose <= T]',
     '    dispo = [(run, pose) for run, pose in runs.items() if run <= T]'),

    # ── les heures cibles ───────────────────────────────────────────
    ("l'heure de T elle-même compte comme cible — on note un CONSTAT "
     "sous le nom de prévision",
     COURT, BANC_COURT,
     '    h0 = T.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)',
     '    h0 = T.replace(minute=0, second=0, microsecond=0)'),

    ("la classe vise sept heures au lieu de six — la septième est "
     "au-delà de la portée de PI, donc de l'AROME pur",
     COURT, BANC_COURT,
     'HEURES_CIBLES = 6',
     'HEURES_CIBLES = 7'),

    # ── ⛔ L'ALIGNEMENT ─────────────────────────────────────────────
    ("⛔ Δ est posé échéance à échéance sur deux runs décalés — la "
     "correction de 10 h Z sur la prévision de 04 h Z",
     FCST, BANC_COURT,
     '            h_pi = h - decalage_h',
     '            h_pi = h'),

    ("la liste des heures ignore le décalage — la classe courte perd "
     "ses six heures sans que rien ne le dise",
     FCST, BANC_COURT,
     '    heures = sorted({m // 60 + decalage_h for m in pi_min if m % 60 == 0})',
     '    heures = sorted({m // 60 for m in pi_min if m % 60 == 0})'),

    ("le poids constant est ignoré : la rampe revient, et à ces "
     "échéances elle sert de l'AROME pur sous une étiquette PI",
     FCST, BANC_COURT,
     '            w = poids_pi(h_pi * 60) if poids is None else poids',
     '            w = poids_pi(h_pi * 60)'),

    # ── la découpe ──────────────────────────────────────────────────
    ("les heures hors classe sont éteintes avec 0 au lieu de `None` — "
     "« le modèle annonçait calme » sur une heure jamais servie",
     COURT, BANC_COURT,
     '            row["speed"][i] = None\n'
     '            row["dir"][i] = None\n'
     '    return n',
     '            row["speed"][i] = 0\n'
     '            row["dir"][i] = 0\n'
     '    return n'),

    # ── côté score.py ───────────────────────────────────────────────
    ("l'échéance déclarée par la ligne est ignorée — toute la classe "
     "courte disparaît dans le « +6 h »",
     SCORE, BANC_SCORE,
     '            lead_h = row.get("lead_h", lead_defaut)',
     '            lead_h = lead_defaut'),

    ("les sous-séries en essai reprennent un rang — le tableau tranche "
     "le poids tout seul, sur quelques journées",
     SCORE, BANC_SCORE,
     '    for r in rows:\n'
     '        if r["model"] in MODELES_COURTS:\n'
     '            exclus[r["model"]] = RANK_REASON_SERIE_EN_ESSAI',
     '    pass'),

    ("le motif « en essai » se confond avec « témoin » — trois "
     "situations différentes sous deux mots",
     SCORE, BANC_SCORE,
     '            exclus[r["model"]] = RANK_REASON_SERIE_EN_ESSAI',
     '            exclus[r["model"]] = RANK_REASON_SERIE_TEMOIN'),

    ("le garde-fou « aucune série admise » disparaît — on demande à "
     "`rank_models` de classer une liste vide",
     SCORE, BANC_SCORE,
     '        if not admis:',
     '        if False:'),

    ("⛔ le repli du `lead_h` refusé disparaît — un HTTP 400 sur "
     "`model_verif_daily` emporte LA NUIT ENTIÈRE, comme au lot G et "
     "au lot L2",
     SCORE, BANC_SCORE,
     '        if nom not in str(exc):\n'
     '            raise\n'
     '        admises = set(LEAD_BY_OFFSET.values())',
     '        raise\n'
     '        admises = set(LEAD_BY_OFFSET.values())'),

    ("le repli garde TOUTES les lignes au lieu d'écarter celles que la "
     "base refuse — le second upsert se fait refuser à son tour",
     SCORE, BANC_SCORE,
     '        gardees = [r for r in rows if r.get(colonne) in admises]',
     '        gardees = list(rows)'),

    ("un lot ENTIÈREMENT refusé passe pour une nuit réussie (upsert "
     "vide) au lieu de lever",
     SCORE, BANC_SCORE,
     '        if not gardees:\n'
     '            raise\n'
     '        return sb.upsert("model_verif_daily", gardees, cle)',
     '        return sb.upsert("model_verif_daily", gardees, cle)'),

    ("la classe courte nourrit la MÉMOIRE DU CARACTÈRE — une moyenne "
     "exponentielle de trois mois écrite pour des séries encore en essai",
     SCORE, BANC_SCORE,
     '    banded = [b for b in banded if b["lead_h"] not in LEADS_COURTS]',
     '    banded = list(banded)'),

    ("la classe courte entre dans les ÉVÉNEMENTS — un taux de fausse "
     "alerte calculé sur un sixième de la matière, sous le même nom",
     SCORE, BANC_SCORE,
     '            if row.get("lead_h") is not None:\n'
     '                continue\n'
     '            key = f"{row[\'source\']}:{row[\'station_id\']}"\n'
     '            if key not in obs_by_st:',
     '            key = f"{row[\'source\']}:{row[\'station_id\']}"\n'
     '            if key not in obs_by_st:'),
]


def _env_sans_pyc() -> dict:
    """L'environnement du banc, SANS écriture ni lecture de bytecode.

    ⛔⛔ LE PIÈGE, TROUVÉ LE 30/08/2026 SUR LE LOT L10, ET IL REND UNE
    MUTATION MENTEUSE. `HEURES_CIBLES = 6` muté en `= 7` fait EXACTEMENT
    la même longueur de fichier ; si la restauration retombe dans la même
    SECONDE, l'horodatage ne bouge pas non plus. Python juge son cache
    `__pycache__` sur (mtime, taille) : il a donc rechargé le bytecode
    MUTÉ pour les trois mutations suivantes, qui ont rougi — mais pour la
    faute de la précédente. Trois lignes vertes qui ne prouvaient rien.
    ⇒ `-B` (ne pas écrire) et `PYTHONDONTWRITEBYTECODE` (pour les
    sous-processus), plus le ménage ci-dessous. Une mutation qui ne peut
    pas prouver ce qu'elle affirme est pire qu'une mutation absente.
    """
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for p in ICI.rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)
    return env


def joue() -> int:
    rouges = 0
    for i, (nom, fichier, banc, avant, apres) in enumerate(MUTATIONS, 1):
        origine = fichier.read_text(encoding="utf-8")
        if avant not in origine:
            print(f"  ⛔ {i:>2}. {nom}\n       MOTIF INTROUVABLE dans "
                  f"{fichier.name} — la mutation n'a rien muté, donc elle "
                  f"n'a rien prouvé. (Le code a bougé : réécrire ce motif.)")
            rouges += 1
            continue
        try:
            fichier.write_text(origine.replace(avant, apres, 1), encoding="utf-8")
            r = subprocess.run([sys.executable, "-B", str(ICI / banc)],
                               capture_output=True, text=True, cwd=ICI,
                               env=_env_sans_pyc())
            if r.returncode == 0:
                print(f"  ❌ {i:>2}. {nom}\n       LE BANC {banc} RESTE "
                      f"VERT — il ne tient pas cette propriété.")
                rouges += 1
            else:
                lignes = [l.strip() for l in r.stdout.splitlines()
                          if l.strip().startswith("❌")]
                if not lignes:
                    lignes = [l.strip() for l in r.stderr.splitlines()[-3:]]
                print(f"  ✅ {i:>2}. {nom}\n       [{banc}] "
                      f"{lignes[0] if lignes else 'banc rouge'}"
                      + (f" (+{len(lignes) - 1} autres)"
                         if len(lignes) > 1 else ""))
        finally:
            fichier.write_text(origine, encoding="utf-8")
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations du lot L10 (la classe courte) — chaque ligne doit "
          "être VERTE,\n  c'est-à-dire : le banc a bien ROUGI sur la faute.\n")
    n = joue()
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
