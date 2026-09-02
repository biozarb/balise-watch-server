#!/usr/bin/env python3
"""Rejoue le banc contre des variantes CASSÉES du lot L15
(`controle_position.py` — le garde-fou de position).

⛔ UN BANC VERT NE PROUVE RIEN TANT QU'ON N'A PAS VU CE QUI LE FAIT
ROUGIR. Les fautes de CE lot-ci sont toutes silencieuses : aucune ne
lève, aucune ne change la forme d'une sortie. Un `and` devenu `or`
suspend des balises que le produit sert au même endroit ; un `continue`
devenu `break` rend le seuil inatteignable pour les balises qu'on
débranche — c'est-à-dire précisément celles qui déménagent ; un seuil
descendu sous le cycle de rafraîchissement de `collect.py` transforme le
garde-fou en générateur de bruit. Rien de tout ça ne se voit dans un
journal.

⚠️ DEUX MUTATIONS SONT NÉES MUETTES (nº 4 et nº 12) et ont fait AJOUTER
deux assertions qui manquaient vraiment : le banc passait `seuil_jours`
explicitement (donc la CONSTANTE de production n'était tenue par rien),
et rien ne vérifiait que deux positions sous la même clé gardent la
PREMIÈRE. Une mutation qui ne rougit pas est un trou du banc, pas une
mutation ratée.

⚠️ Le harnais (restauration en `finally`, ménage du `__pycache__`,
`-B`) est celui du L10/L11, importé tel quel : le piège du bytecode
trouvé le 30/08 a déjà coûté trois lignes vertes qui ne prouvaient rien.

    python3 mutations_position_l15.py
"""
import os
import pathlib
import shutil
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
CP = ICI / "controle_position.py"
RUN = ICI / "run.sh"
BANC = "test_controle_position.py"
BANC_RUN = "test_run_selftest.py"

MUTATIONS = [
    # ── ⛔⛔ LA FAUTE CENTRALE : le critère cesse d'être une conjonction
    ("⛔⛔ le critère devient un OU — 333 m dans la MÊME maille "
     "suspendent une balise que le modèle sert au même endroit",
     '    return d, n001, n0025, bool(n001 and d > SEUIL_DEPLACEMENT_M)',
     '    return d, n001, n0025, bool(n001 or d > SEUIL_DEPLACEMENT_M)'),

    ("⛔⛔ le critère redevient « le nœud seul » (ce que le lot "
     "demandait) — 2 m sur un bord de maille suspendent une balise qui "
     "n'a pas bougé",
     '    return d, n001, n0025, bool(n001 and d > SEUIL_DEPLACEMENT_M)',
     '    return d, n001, n0025, bool(n001)'),

    ("⛔ le critère devient « la distance seule » — un déplacement qui "
     "ne change rien à ce qui est noté déclenche quand même",
     '    return d, n001, n0025, bool(n001 and d > SEUIL_DEPLACEMENT_M)',
     '    return d, n001, n0025, bool(d > SEUIL_DEPLACEMENT_M)'),

    # ── le seuil, et la constante recopiée ──────────────────────────
    ("⛔⛔ le seuil de persistance passe SOUS le cycle de "
     "rafraîchissement de collect.py (7 j) : le garde-fou ne filtre "
     "plus rien et crie sur des positions transitoires",
     'SEUIL_PERSISTANCE_J = 10',
     'SEUIL_PERSISTANCE_J = 5'),

    ("⛔ la constante recopiée de freeze_balises dérive (200 → 20 m) — "
     "le seul gardien de la copie est le banc",
     'SEUIL_DEPLACEMENT_M = 200.0',
     'SEUIL_DEPLACEMENT_M = 20.0'),

    # ── le nœud ─────────────────────────────────────────────────────
    ("⛔⛔ le nœud est calculé au plus proche voisin par TRONCATURE "
     "(int) au lieu de l'arrondi — la moitié des balises change de "
     "maille, et index_plats, lui, n'a pas bougé",
     '    i = round((lon - meta["lon0"]) / meta["di"])',
     '    i = int((lon - meta["lon0"]) / meta["di"])'),

    ("⛔ le sens de balayage de la latitude est inversé — les nœuds "
     "restent plausibles et désignent une autre ligne de grille",
     '    j = (round((meta["lat0"] - lat) / meta["dj"]) if meta.get("jScan") != 1',
     '    j = (round((lat - meta["lat0"]) / meta["dj"]) if meta.get("jScan") != 1'),

    ("⛔ deux artefacts d'orographie qui se contredisent : on prend le "
     "premier au lieu de LEVER — le nœud devient une opinion",
     '        raise ValueError(',
     '        return metas if False else metas  # noqa\n    if False:\n        raise ValueError('),

    # ── la persistance ──────────────────────────────────────────────
    ("⛔⛔ une nuit sans la balise REMET LE COMPTEUR À ZÉRO — et une "
     "balise déménagée est justement une balise qu'on débranche : le "
     "seuil devient inatteignable pour les cas visés",
     '            if p is None:\n                continue\n            if not diverge(b, p, metas)[3]:\n                break',
     '            if p is None:\n                break\n            if not diverge(b, p, metas)[3]:\n                break'),

    ("⛔ un retour à la bonne position n'interrompt plus le compte — "
     "une divergence ancienne et guérie reste confirmée pour toujours",
     '            if not diverge(b, p, metas)[3]:\n                break\n            n += 1',
     '            if not diverge(b, p, metas)[3]:\n                continue\n            n += 1'),

    ("le seuil de confirmation devient strict (> au lieu de ≥) — dix "
     "jours mesurés ne confirment plus un seuil de dix",
     '            noeud_0025=n0025, jours=n, confirmee=n >= seuil_jours,',
     '            noeud_0025=n0025, jours=n, confirmee=n > seuil_jours,'),

    ("⛔ deux positions sous la même clé le même jour : c'est la "
     "DERNIÈRE qui gagne, en silence",
     '        vues.setdefault(cle, (round(float(lat), 4), round(float(lon), 4)))',
     '        vues[cle] = (round(float(lat), 4), round(float(lon), 4))'),

    # ── le cri ──────────────────────────────────────────────────────
    ("⛔⛔ le jeton illisible fait TAIRE le cri au lieu de le faire "
     "partir — le dispositif d'alerte se tait parce que son propre "
     "état est cassé (la faute du lot LV, retournée)",
     '    except Exception:                                    # noqa: BLE001\n        connu = None\n    if connu is not None and connu == courant:',
     '    except Exception:                                    # noqa: BLE001\n        return None\n    if connu is not None and connu == courant:'),

    ("⛔ une balise qui SORT de l'ensemble ne fait plus rien dire — la "
     "guérison est aussi une nouvelle",
     '    sortantes = [x for x in (connu or []) if x not in courant]',
     '    sortantes = []'),

    ("⛔ un jeton inécrivable fait TOMBER le run de notation — un "
     "contrôle de diagnostic ne doit jamais coûter une nuit",
     '    except Exception:                                    # noqa: BLE001\n        pass                                             # échouer ouvert',
     '    except Exception:                                    # noqa: BLE001\n        raise'),

    # ── le .sql et le journal ───────────────────────────────────────
    ("⛔ le littéral SQL ne double plus les apostrophes — la première "
     "note française casse le fichier, ou pire, l'ouvre",
     '    return "\'" + str(s).replace("\'", "\'\'") + "\'"',
     '    return "\'" + str(s) + "\'"'),

    ("⛔ le .sql suspend TOUTES les divergences, confirmées ou non — "
     "le seuil mesuré ne sert plus à rien au moment de poser le drapeau",
     '    for i in sorted(r["confirmees"]):',
     '    for i in sorted(x["id"] for x in r["lignes"]):'),

    ("⛔ le journal se tait quand tout va bien — un contrôle qu'on ne "
     "voit que les jours de panne est indistinguable d'un contrôle qui "
     "ne tourne plus",
     '    if not r["lignes"]:\n        L.append("     (aucune : le gel et le référentiel tombent dans la "\n                 "même maille partout)")\n    return "\\n".join(L)',
     '    if not r["lignes"]:\n        return ""\n    return "\\n".join(L)'),
    # ── ⛔ LES SIX LIGNES DE `run.sh` QUI PORTENT LE CRI DEHORS ──────
    ("⛔⛔ le cri repart par `dire` au lieu d'`alerter` — il reste dans "
     "un journal que RIEN ne lit sur cette machine : la faute exacte du "
     "lot LV, qui a crié vingt jours dans le vide",
     RUN, BANC_RUN,
     '    alerter "$LIBELLE — position des balises" "$(cat "$CRI_POSITION")"',
     '    dire "position des balises : $(cat "$CRI_POSITION")"'),

    ("⛔ le fichier de cri n'est plus effacé — le même avertissement "
     "repart TOUTES les nuits, et on apprend à l'ignorer",
     RUN, BANC_RUN,
     '    rm -f "$CRI_POSITION" \\\n      || dire "⚠️ cri de position non effacé — il repartira demain"',
     '    :'),

    ("⛔ le cri n'est jamais envoyé (condition morte) — le garde-fou "
     "détecte et personne n'entend, l'état d'avant ce lot",
     RUN, BANC_RUN,
     '  if [[ "$MODE" == "score" && -s "$CRI_POSITION" ]]; then',
     '  if false; then'),
]


def _env_sans_pyc() -> dict:
    """L'environnement du banc, SANS écriture ni lecture de bytecode.
    ⛔⛔ Le piège du 30/08 (lot L10) : une mutation de même longueur
    restaurée dans la même seconde laisse Python recharger le `.pyc`
    MUTÉ, et les mutations suivantes rougissent pour la faute de la
    précédente."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for p in ICI.rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)
    return env


def joue() -> int:
    rouges = 0
    for i, mutation in enumerate(MUTATIONS, 1):
        # ⓘ Une entrée à trois champs vise `controle_position.py` et son
        # banc ; une entrée à cinq nomme son fichier et son banc. Les six
        # lignes de `run.sh` qui portent le cri DEHORS sont dans le second
        # cas — et elles n'étaient tenues par rien avant le 02/09.
        if len(mutation) == 3:
            nom, avant, apres = mutation
            fichier, banc = CP, BANC
        else:
            nom, fichier, banc, avant, apres = mutation
        origine = fichier.read_text(encoding="utf-8")
        if avant not in origine:
            print(f"  ⛔ {i:>2}. {nom}\n       MOTIF INTROUVABLE dans "
                  f"{fichier.name} — la mutation n'a rien muté, donc elle "
                  f"n'a rien prouvé. (Le code a bougé : réécrire ce motif.)")
            rouges += 1
            continue
        try:
            fichier.write_text(origine.replace(avant, apres, 1),
                               encoding="utf-8")
            r = subprocess.run([sys.executable, "-B", str(ICI / banc)],
                               capture_output=True, text=True, cwd=ICI,
                               env=_env_sans_pyc())
            if r.returncode == 0:
                print(f"  ❌ {i:>2}. {nom}\n       LE BANC RESTE VERT — il "
                      f"ne tient pas cette propriété ({banc}).")
                rouges += 1
            else:
                lignes = [l.strip() for l in r.stdout.splitlines()
                          if l.strip().startswith("❌")]
                if not lignes:
                    lignes = [l.strip() for l in r.stderr.splitlines()[-3:]]
                print(f"  ✅ {i:>2}. {nom}\n       {lignes[0] if lignes else 'banc rouge'}"
                      + (f" (+{len(lignes) - 1} autres)"
                         if len(lignes) > 1 else ""))
        finally:
            fichier.write_text(origine, encoding="utf-8")
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations du lot L15 (le garde-fou de position) — chaque ligne "
          "doit être VERTE,\n  c'est-à-dire : le banc a bien ROUGI sur la "
          "faute.\n")
    n = joue()
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
