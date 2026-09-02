#!/usr/bin/env python3
"""Rejoue le banc contre des variantes CASSÉES de la sonde de fraîcheur
(lot L8, 28/08/2026 — le geste qui rend le contrôle n°3 possible).

⛔ Un banc vert ne prouve rien tant qu'on n'a pas vu ce qui le fait
rougir. Et la faute qu'on craint ici est particulière : elle ne casse
RIEN. Une sonde qui écrit le run d'`ncep_gfs025` sous le nom de
`gfs_global`, ou qui saute un modèle absent de sa carte, produit une
archive parfaitement lisible, parfaitement plausible, et fausse — dans
une archive irremplaçable qu'on relira dans trois ans.

    python3 mutations_fraicheur.py [debut] [fin]
"""
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent

# ⛔ (02/09/2026) copie d'origine sur le disque + sha256 + purge du
# bytecode, pour TOUS les harnais — voir `model-verif/harnais.py`.
sys.path.insert(0, str(ICI))
import harnais as HARNAIS  # noqa: E402
FR = ICI / "fraicheur.py"
COL = ICI / "collect.py"
CR = ICI / "collect_reduit.py"
BANC = ICI / "test_fraicheur.py"
B_RED = ICI / "test_collect_reduit.py"

MUTATIONS = [
    # ── la carte des domaines : la faute qui ne casse rien ──────────
    ("⭐ `gfs_global` est sondé sur un domaine du même nom — l'archive "
     "recevrait le run d'un AUTRE modèle, sans qu'une ligne ne rougisse",
     FR, BANC,
     '    "gfs_global": "ncep_gfs013",',
     '    "gfs_global": "gfs_global",'),

    ("un modèle collecté disparaît de la carte — il partirait sans "
     "`run_init`, en silence, pour toujours",
     FR, BANC,
     '    "chmi_aladin_central_europe_2km": "chmi_aladin_central_europe_2km",',
     ''),

    ("un modèle inconnu est SAUTÉ au lieu de lever — l'oubli ne se "
     "saurait qu'au contrôle n°3, trois semaines plus tard",
     FR, BANC,
     '''    if modele not in DOMAINE_PAR_MODELE:
        raise ModeleInconnu(''',
     '''    if modele not in DOMAINE_PAR_MODELE:
        return "inconnu"
    if False:
        raise ModeleInconnu('''),

    # ── les témoins ─────────────────────────────────────────────────
    ("⭐ un témoin atterrit sur les LIGNES : le run d'un modèle qu'on "
     "ne sert pas est collé sur celles d'un modèle qu'on sert",
     FR, BANC,
     '''        if modele:
            par_modele[modele] = info
        else:
            jrn["temoins"][domaine] = info''',
     '''        par_modele[modele or domaine] = info
        if not modele:
            jrn["temoins"][domaine] = info'''),

    # ── le budget ───────────────────────────────────────────────────
    ("la sonde ne demande plus au budget : neuf appels partent hors "
     "compteur, et le seau ment sur la minute",
     FR, BANC,
     '''                budget.demander(POIDS_SONDE,
                                etiquette=f"sonde meta.json {domaine}")
                jrn["poids_reserve"] += POIDS_SONDE''',
     '''                jrn["poids_reserve"] += POIDS_SONDE'''),

    ("un refus de budget compte quand même son poids comme réservé",
     FR, BANC,
     '''            except Exception as exc:                         # noqa: BLE001
                # ⚠️ `BudgetRefuse` est un refus ARGUMENTÉ, pas une
                # panne — et il ne doit pas emporter la collecte.
                jrn["refuses"].append(f"{domaine} ({exc})")
                continue''',
     '''            except Exception as exc:                         # noqa: BLE001
                jrn["refuses"].append(f"{domaine} ({exc})")
                jrn["poids_reserve"] += POIDS_SONDE
                continue'''),

    ("⛔ un refus de budget EMPORTE la passe (au lieu d'écarter un "
     "domaine) : une colonne d'information coûte une nuit d'archive",
     FR, BANC,
     '''                jrn["refuses"].append(f"{domaine} ({exc})")
                continue''',
     '''                raise'''),

    # ── ce qui est écrit sur la ligne ───────────────────────────────
    ("⭐ un modèle non sondé reçoit `run_init = null` au lieu de RIEN — "
     "« pas de relevé » devient indiscernable d'une valeur",
     FR, BANC,
     '''    info = fraicheur.get(row.get("model"))
    if info:
        row["run_init"] = info["init"]
        row["run_avail"] = info["avail"]''',
     '''    info = fraicheur.get(row.get("model")) or {}
    row["run_init"] = info.get("init")
    row["run_avail"] = info.get("avail")'''),

    ("`poser` écrit le run de PUBLICATION dans `run_init` — les deux "
     "colonnes disent la même chose, et l'écart d'échéance disparaît",
     FR, BANC,
     '        row["run_init"] = info["init"]',
     '        row["run_init"] = info["avail"]'),

    # ── le journal ──────────────────────────────────────────────────
    ("le pavé de journal ne nomme plus les modèles non rendus",
     FR, BANC,
     '''        else:
            crier(f"│   {m:28s} ⚠️ non rendu — lignes sans `run_init`")''',
     '''        else:
            pass'''),

    ("une sonde incomplète ne crie plus : personne ne l'apprend le "
     "soir même",
     FR, BANC,
     '    if jrn["echecs"] or jrn["refuses"]:',
     '    if False:'),

    ("un `meta.json` sans `last_run_initialisation_time` est accepté — "
     "l'archive reçoit un `run_init` absent sous forme de valeur",
     FR, BANC,
     '        if not isinstance(d, dict) or not d.get("last_run_initialisation_time"):',
     '        if not isinstance(d, dict):'),

    # ── le câblage de collect.py ────────────────────────────────────
    ("collect.py ne pose plus les champs sur les lignes écrites : la "
     "sonde tourne, coûte ses neuf pondérés, et n'écrit rien",
     COL, BANC,
     '                            yield FR.poser(_row, fraicheur)',
     '                            yield _row'),

    ("collect.py sonde les NEUF modèles même en passe partitionnée — "
     "il paie pour des lignes qu'il n'écrit pas",
     COL, BANC,
     '                    budget, modeles_passe, get_json=_get_json_retry)',
     '                    budget, MODELS, get_json=_get_json_retry)'),

    ("collect.py recopie la carte des domaines au lieu de l'importer",
     COL, BANC,
     'import fraicheur as FR  # noqa: E402',
     'import fraicheur as FR  # noqa: E402\n_DOM = {"gfs_global": "ncep_gfs013"}'),

    # ── le déménagement, vu de collect_reduit ───────────────────────
    ("la vue restreinte de collect_reduit cesse d'être dérivée et "
     "reprend la carte ENTIÈRE — son budget passe de 9 à 13 appels",
     CR, BANC,
     '    DOMAINE_PAR_MODELE = {m: FR.DOMAINE_PAR_MODELE[m] for m in MODELS_REDUIT}'
     if False else
     'DOMAINE_PAR_MODELE = {m: FR.DOMAINE_PAR_MODELE[m] for m in MODELS_REDUIT}',
     'DOMAINE_PAR_MODELE = dict(FR.DOMAINE_PAR_MODELE)'),

    ("l'enveloppe de collect_reduit perd ses témoins : le flux cesse "
     "de sonder les quatre domaines qu'il ne collecte pas",
     CR, BANC,
     '        temoins=DOMAINES_TEMOINS if avec_temoins else (), crier=crier)',
     '        temoins=(), crier=crier)'),

    ("l'enveloppe sonde les modèles de la PASSE PIOUPIOU au lieu des "
     "cinq du groupe réduit",
     CR, B_RED,
     '        budget, MODELS_REDUIT, get_json=_get_json_retry,',
     '        budget, list(FR.DOMAINE_PAR_MODELE), get_json=_get_json_retry,'),
]


def joue(debut: int = 1, fin: int = len(MUTATIONS)) -> int:
    """⚠️ Jouer par tranches courtes : un processus TUÉ ne passe pas par
    son `finally` et laisse le fichier MUTÉ (vécu le 27/08). Contrôler
    l'intégrité après — chaque motif `avant` doit être retrouvable."""
    rouges = 0
    for i, (nom, fichier, banc, avant, apres) in enumerate(MUTATIONS, 1):
        if not (debut <= i <= fin):
            continue
        origine = HARNAIS.garder(fichier)
        if avant not in origine:
            print(f"  ⛔ {i:>2}. {nom}\n       MOTIF INTROUVABLE dans "
                  f"{fichier.name} — la mutation n'a rien muté, donc elle "
                  f"n'a rien prouvé.")
            rouges += 1
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
    print("\n▶ mutations de la sonde de fraîcheur — chaque ligne doit être "
          "VERTE,\n  c'est-à-dire : le banc a bien ROUGI sur la faute.\n")
    debut = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    fin = int(sys.argv[2]) if len(sys.argv) > 2 else len(MUTATIONS)
    n = joue(debut, fin)
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
