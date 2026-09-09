#!/usr/bin/env python3
"""Rejoue les bancs contre des variantes CASSÉES du correctif de
l'incident `bw-model-score` des 05 et 06/09/2026 — la fenêtre glissante
lue par DÉCALAGE, et la copie par ligne de `rolling_scores`.

⛔ LES DEUX FAUTES DE CET INCIDENT SE RESSEMBLENT, et c'est pour ça
qu'elles vont ensemble ici : aucune des deux ne plante à l'écriture,
aucune des deux ne rougit au banc, et toutes les deux attendent que la
table grossisse assez. La première a attendu neuf jours (332 307 lignes
le 28/08, 784 372 le 07/09) avant de rendre `57014 canceling statement
due to statement timeout` à l'offset 650 000 — deux nuits de notation
perdues. La seconde attend toujours : 687 Mo de copie mesurés le 07/09
sur un VPS de 3 825 Mo, sur un run qui a déjà culminé à 3,2 Go.

⚠️ ET C'EST BIEN LA MÊME CLASSE DE DÉFAUT QUE LE 25/08 et le 02/09.
`model_character` puis `model_verif_event` étaient déjà passées de
l'offset à la clé. `model_verif_daily` est la TROISIÈME. Un banc qui
regarde le source plutôt qu'un comportement est laid ; c'est aussi la
seule chose qui ait arrêté la répétition, parce qu'un `select(` par
décalage est syntaxiquement parfait et ne se voit qu'en production.

    python3 mutations_incident_0709.py            # tout
    python3 mutations_incident_0709.py 1 3        # par tranches
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent

# ⛔ (02/09/2026) copie d'origine sur le disque + sha256 + purge du
# bytecode, pour TOUS les harnais — voir `model-verif/harnais.py`.
sys.path.insert(0, str(ICI))
import harnais as HARNAIS  # noqa: E402
SCORE = ICI / "score.py"
B_SCORE = ICI / "test_score.py"

# ⓘ 09/09/2026 : la requête de la fenêtre porte désormais
#   `&select={COLONNES_FENETRE}` (restriction des colonnes lues) ; les
#   quatre motifs qui la citent ont suivi. Voir mutations_colonnes_0909.py.
MUTATIONS = [
    # ══════════════════════════════════════════════════════════════
    #  LA PAGINATION — la faute exacte des nuits des 05 et 06/09
    # ══════════════════════════════════════════════════════════════
    ("⭐⭐ LA FAUTE DES NUITS DES 05 ET 06/09, remise telle quelle : la "
     "fenêtre glissante repasse au DÉCALAGE. En production c'est trois "
     "`57014` à l'offset 650 000 et le run meurt AVANT d'avoir rien "
     "écrit — mesuré : 0,19 s à l'offset 0, 16,12 s à 500 000, expiré "
     "à 650 000",
     SCORE, B_SCORE,
     '        daily = sb.select_par_cle(\n'
     '            "model_verif_daily", "day",\n'
     '            order=CLE_DAILY,\n'
     '            query=f"?day=gte.{since}&select={COLONNES_FENETRE}")',
     '        daily = sb.select(\n'
     '            "model_verif_daily",\n'
     '            order=CLE_DAILY,\n'
     '            query=f"?day=gte.{since}&select={COLONNES_FENETRE}")'),

    ("la lecture reste par clé mais borne sur `station_id` au lieu de "
     "`day` : la clé n'est plus la PREMIÈRE colonne de l'ordre, donc "
     "deux pages peuvent se recouvrir ou se sauter — une fenêtre "
     "glissante fausse, jamais vide, jamais rouge",
     SCORE, B_SCORE,
     '            "model_verif_daily", "day",\n            order=CLE_DAILY,',
     '            "model_verif_daily", "station_id",\n'
     '            order=CLE_DAILY,'),

    ("⭐ l'ordre perd sa queue (`fcst_src`) : il n'est plus la clé "
     "primaire complète, et deux lignes qui ne diffèrent que par la "
     "chaîne de prévision deviennent interchangeables entre deux pages. "
     "C'est la mutation qui a SURVÉCU au premier jet du 07/09 — le banc "
     "ne regardait que le nom de la table",
     SCORE, B_SCORE,
     'CLE_DAILY = "day,source,station_id,model,lead_h,fcst_src"',
     'CLE_DAILY = "day,source,station_id,model,lead_h"'),

    ("l'ordre de la fenêtre redevient une chaîne recopiée : identique "
     "aujourd'hui, libre de diverger demain de la clé d'upsert — les "
     "quatre copies d'avant le 07/09, remises une par une",
     SCORE, B_SCORE,
     '            order=CLE_DAILY,\n'
     '            query=f"?day=gte.{since}&select={COLONNES_FENETRE}")',
     '            order="day,source,station_id,model,lead_h,fcst_src",\n'
     '            query=f"?day=gte.{since}&select={COLONNES_FENETRE}")'),

    ("`day` n'est plus la tête de l'ordre : `select_par_cle` borne "
     "toujours sur `day`, mais l'index attaqué n'est plus le sien — la "
     "condition même que sa docstring pose en avertissement",
     SCORE, B_SCORE,
     'CLE_DAILY = "day,source,station_id,model,lead_h,fcst_src"',
     'CLE_DAILY = "source,day,station_id,model,lead_h,fcst_src"'),

    ("la profondeur MESURÉE du duel disparaît du commentaire : « elle "
     "est petite » redevient une supposition, exactement comme du "
     "27/08 au 07/09 — et la prochaine fois personne ne saura si elle "
     "l'est encore",
     SCORE, B_SCORE,
     '    #     37 528 lignes, 38 pages, offset le plus profond 36 528\n',
     '    #     (quelques dizaines de milliers de lignes)\n'),

    # ══════════════════════════════════════════════════════════════
    #  LA COPIE PAR LIGNE — 687 Mo, et la mutation qu'elle autorise
    # ══════════════════════════════════════════════════════════════
    ("⭐ `main` cesse de demander la mutation et reprend la copie : le "
     "run redevient correct et repasse à +687 Mo, sur une machine où "
     "il ne reste que 990 Mo une fois la fenêtre lue. Rien ne rougit, "
     "rien ne plante — jusqu'à l'OOM, qui ne laisse qu'un code 137",
     SCORE, B_SCORE,
     'rolling_scores(daily, zone_of, as_of, sur_place=True)',
     'rolling_scores(daily, zone_of, as_of)'),

    ("⭐⭐ LA MUTATION DEVIENT SILENCIEUSE : `sur_place` passe à `True` "
     "par défaut. Tout appelant qui relit son `daily` après coup — "
     "trente bancs, et demain un `main` qui ne l'oublierait plus — "
     "trouve des lignes qu'il n'a pas écrites",
     SCORE, B_SCORE,
     '                   as_of: datetime, sur_place: bool = False):',
     '                   as_of: datetime, sur_place: bool = True):'),

    ("la voie `sur_place` oublie d'écrire `unit` et rend les lignes "
     "telles quelles : `_case_rows` ne trouve plus la zone d'aucune "
     "balise-jour, et le score glissant sort VIDE plutôt que faux",
     SCORE, B_SCORE,
     '        for d in daily:\n'
     '            d["unit"] = f"{d[\'source\']}:{d[\'station_id\']}"\n'
     '        units = daily',
     '        units = daily'),

    ("la voie `sur_place` compose `unit` à l'envers "
     "(`station_id:source`) : les clés ne tombent plus dans `zone_of`, "
     "et c'est la même panne silencieuse vue d'un autre angle",
     SCORE, B_SCORE,
     '            d["unit"] = f"{d[\'source\']}:{d[\'station_id\']}"',
     '            d["unit"] = f"{d[\'station_id\']}:{d[\'source\']}"'),

    ("la voie par défaut cesse de copier et mute elle aussi : le "
     "drapeau existe encore, il ne protège plus rien",
     SCORE, B_SCORE,
     '        units = []\n'
     '        for d in daily:\n'
     '            r = dict(d)\n'
     '            r["unit"] = f"{d[\'source\']}:{d[\'station_id\']}"\n'
     '            units.append(r)',
     '        for d in daily:\n'
     '            d["unit"] = f"{d[\'source\']}:{d[\'station_id\']}"\n'
     '        units = daily'),

    # ══════════════════════════════════════════════════════════════
    #  L'OUBLI QUI REND LA MUTATION LÉGALE
    # ══════════════════════════════════════════════════════════════
    ("⭐ l'oubli de la fenêtre disparaît alors que `sur_place=True` "
     "reste : 1 266 Mo de lignes MUTÉES survivent au chemin régime. "
     "C'est la faute du 28/08 aggravée — le bloc a doublé depuis, et "
     "il est maintenant partagé avec `units`",
     SCORE, B_SCORE,
     '        daily = None\n        gc.collect()\n'
     '        jalon_memoire("l\'oubli de la fenêtre glissante")',
     '        jalon_memoire("l\'oubli de la fenêtre glissante")'),

    # ══════════════════════════════════════════════════════════════
    #  LA LECTURE TARDIVE — le run mort la base déjà écrite
    # ══════════════════════════════════════════════════════════════
    ("⭐⭐ LA FAUTE DU 07/09 À 09:24, remise telle quelle : la dispersion "
     "se relit sur `units` DANS le méta, c'est-à-dire après l'oubli de "
     "la fenêtre rejouée. `TypeError: 'NoneType' object is not "
     "iterable` — après 3 089 s de run et APRÈS les 116 425 lignes de "
     "`model_score_zone` : la base à moitié à jour et le journal rouge",
     SCORE, B_SCORE,
     '        bilan_disp = MX.bilan_dispersion(units)\n',
     ''),

    ("le méta republie la TABLE et non le résultat : identique tant que "
     "`units` vit, mortel dès qu'on l'oublie — et c'est exactement "
     "l'ordre du fichier",
     SCORE, B_SCORE,
     '                           "dispersion": bilan_disp,',
     '                           "dispersion": MX.bilan_dispersion(units),'),

    ("la dispersion est calculée APRÈS l'oubli au lieu d'avant : la "
     "variable existe, le nom est le bon, et elle vaut `None`",
     SCORE, B_SCORE,
     '        bilan_disp = MX.bilan_dispersion(units)\n'
     '        # ⓘ Dernier lecteur de la fenêtre rejouée',
     '        # ⓘ Dernier lecteur de la fenêtre rejouée'),

    # ══════════════════════════════════════════════════════════════
    #  ET LE BANC LUI-MÊME — un garde aveugle est pire qu'aucun garde
    # ══════════════════════════════════════════════════════════════
    ("⭐ `sans_commentaires` cesse d'effacer et rend le texte brut : les "
     "gardes « plus aucune lecture après l'oubli » redeviennent "
     "sensibles aux COMMENTAIRES, donc rouges dès qu'on explique le "
     "défaut qu'ils gardent — le banc qu'on finit par contourner",
     B_SCORE, B_SCORE,
     '        lignes[l1 - 1] = s[:c1] + " " * (c2 - c1) + s[c2:]',
     '        lignes[l1 - 1] = s'),
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
    print("\n▶ mutations de l'incident du 05-06/09 — chaque ligne doit être "
          "VERTE,\n  c'est-à-dire : le banc a bien ROUGI sur la faute.\n")
    debut = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    fin = int(sys.argv[2]) if len(sys.argv) > 2 else len(MUTATIONS)
    n = joue(debut, fin)
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
