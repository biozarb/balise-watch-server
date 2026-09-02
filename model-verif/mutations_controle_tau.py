#!/usr/bin/env python3
"""Rejoue le banc contre des variantes CASSÉES du lot L8
(tau inter-populations, noyau commun, réserve `run_init`).

⛔ Un banc vert ne prouve rien tant qu'on n'a pas vu ce qui le fait
rougir (même discipline que `mutations_duel.py`, `mutations_fdr.py`,
`mutations_sonde_doublons.py`). Et la faute qu'on craint ici n'est pas
le plantage : c'est un tau qui SORT, plausible, et qui mesure autre
chose que ce que son nom dit — l'accord de deux calendriers, l'accord
d'un capteur avec lui-même, ou l'accord de deux fenêtres qu'on a
oublié d'apparier. Aucune de ces trois fautes ne rougit toute seule, et
les trois donnent un nombre entre −1 et +1 qui a l'air d'un tau.

Un seul banc concerné : `test_controle_tau.py`.

Restauration en `finally` : le fichier revient à son état d'origine
même si l'on interrompt. ⚠️ Un processus TUÉ (délai de l'outil, pont
Cowork qui tombe) ne passe PAS par son `finally` — jouer par tranches,
et contrôler l'intégrité après.

    python3 mutations_controle_tau.py [debut] [fin]
"""
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent

# ⛔ (02/09/2026) copie d'origine sur le disque + sha256 + purge du
# bytecode, pour TOUS les harnais — voir `model-verif/harnais.py`.
sys.path.insert(0, str(ICI))
import harnais as HARNAIS  # noqa: E402
CT = ICI / "controle_tau.py"
BANC = ICI / "test_controle_tau.py"

MUTATIONS = [
    # ── le noyau commun : le cœur du lot ────────────────────────────
    ("le noyau commun devient une UNION — chaque modèle repart avec ses "
     "propres journées et le tau redevient un tau de calendriers",
     CT, BANC,
     '        noyau = cles if noyau is None else (noyau & cles)',
     '        noyau = cles if noyau is None else (noyau | cles)'),

    ("le noyau n'est appliqué qu'à la POPULATION, pas à la référence — "
     "on apparie un côté et pas l'autre",
     CT, BANC,
     '    ref = {m: _restreindre(lignes_ref.get(m, ()), noyau_ref) for m in modeles} \\\n'
     '        if noyau_ref is not None else {m: list(lignes_ref.get(m, ())) for m in modeles}',
     '    ref = {m: list(lignes_ref.get(m, ())) for m in modeles}'),

    ("le noyau se calcule sur le PREMIER modèle seulement (la boucle "
     "s'arrête) — il devient la population de ce modèle",
     CT, BANC,
     '    for m in modeles:\n'
     '        cles = {(r["day"], r["unit"]) for r in lignes.get(m, ())}\n'
     '        noyau = cles if noyau is None else (noyau & cles)',
     '    for m in modeles[:1]:\n'
     '        cles = {(r["day"], r["unit"]) for r in lignes.get(m, ())}\n'
     '        noyau = cles if noyau is None else (noyau & cles)'),

    ("un modèle ABSENT n'annule plus le noyau, il est ignoré — le "
     "silence d'un modèle devient un accord",
     CT, BANC,
     '        cles = {(r["day"], r["unit"]) for r in lignes.get(m, ())}\n'
     '        noyau = cles if noyau is None else (noyau & cles)',
     '        cles = {(r["day"], r["unit"]) for r in lignes.get(m, ())}\n'
     '        if not cles:\n            continue\n'
     '        noyau = cles if noyau is None else (noyau & cles)'),

    ("⭐ l'alignement des calendriers saute : les deux reseaux sont "
     "classes sur des SEMAINES differentes, et un changement de temps "
     "se lit comme un desaccord de reseau",
     CT, BANC,
     '        noyau_pop = {c for c in noyau_pop if c[0] in jours_com}\n'
     '        noyau_ref = {c for c in noyau_ref if c[0] in jours_com}',
     '        pass'),

    ("l'alignement ne s'applique qu'a la population : la reference "
     "garde ses journees en trop",
     CT, BANC,
     '        noyau_ref = {c for c in noyau_ref if c[0] in jours_com}',
     '        noyau_ref = set(noyau_ref)'),

    ("les journees ecartees ne sont plus nommees : le prix de "
     "l'alignement devient invisible",
     CT, BANC,
     '        base["jours_ecartes_reference"] = sorted(jours_ref - jours_com)',
     '        base["jours_ecartes_reference"] = []'),

    # ── l'ordre ─────────────────────────────────────────────────────
    ("le classement s'ordonne à l'ENVERS (le pire premier)",
     CT, BANC,
     '    stats.sort(key=lambda s: (s["median"], s["model"]))',
     '    stats.sort(key=lambda s: (-s["median"], s["model"]))'),

    ("le classement s'ordonne sur le NOMBRE de balise-jours au lieu de "
     "l'erreur — le modèle le mieux couvert devient le meilleur",
     CT, BANC,
     '    stats.sort(key=lambda s: (s["median"], s["model"]))',
     '    stats.sort(key=lambda s: (-s["n"], s["model"]))'),

    ("les ex aequo ne se départagent plus par le nom : l'ordre dépend "
     "de l'ordre de lecture, donc de rien de reproductible",
     CT, BANC,
     '    stats.sort(key=lambda s: (s["median"], s["model"]))',
     '    stats.sort(key=lambda s: (s["median"], -ord(s["model"][0])))'),

    ("le quorum d'entrée saute — un modèle vu trois fois entre au "
     "classement et pèse sur le tau",
     CT, BANC,
     '        if len(rows) < min_occurrences or med is None:',
     '        if med is None:'),

    ("la marche du haut n'est plus calculée : l'ordre est publié sans "
     "rien qui dise ce qu'il vaut",
     CT, BANC,
     '    if len(stats) >= 2:',
     '    if False:'),

    # ── le tau lui-même ─────────────────────────────────────────────
    ("le tau se calcule sur l'UNION des modèles au lieu de leur "
     "intersection — un modèle absent d'un côté fait des paires",
     CT, BANC,
     '    communs = sorted(set(rangs_pop) & set(rangs_ref))',
     '    communs = sorted(set(rangs_pop) | set(rangs_ref))'),

    ("`TAU_MIN_MODELES` passe à 1 — un tau sort sur zéro paire, et il "
     "vaut ce que vaut une division par le hasard",
     CT, BANC,
     'TAU_MIN_MODELES = 2',
     'TAU_MIN_MODELES = 1'),

    ("le rerangement se fait par ORDRE ALPHABÉTIQUE au lieu de l'ordre "
     "des rangs — le tau compare deux listes de noms",
     CT, BANC,
     '    presents.sort(key=lambda m: rangs[m])',
     '    presents.sort()'),

    # ── les doublons ────────────────────────────────────────────────
    ("le doublon de CHAÎNE n'est plus écarté : la dernière ligne lue "
     "gagne, et le contrôle compare deux chaînes en croyant comparer "
     "deux réseaux",
     CT, BANC,
     '        if cle in par_modele[m]:\n'
     '            vus_deux_fois[m].add(cle)\n'
     '            continue',
     '        if cle in par_modele[m]:\n'
     '            pass'),

    ("le doublon de RÉSEAU n'est plus retiré (lot L16/L17) : le tau "
     "pioupiou↔windsmobi mesure en partie l'accord d'un capteur avec "
     "lui-même",
     CT, BANC,
     '        if u in doublons:\n'
     '            bilan["doublons_reseau"] += 1\n'
     '            continue',
     '        if u in doublons:\n'
     '            bilan["doublons_reseau"] += 1'),

    ("l'unité de balise perd son réseau (`station_id` seul) — deux "
     "balises étrangères qui portent le même id s'apparient",
     CT, BANC,
     '    return f"{row[\'source\']}:{row[\'station_id\']}"',
     '    return f"{row[\'station_id\']}"'),

    # ── la réserve run_init ─────────────────────────────────────────
    ("⭐ « un côté sans `run_init` » devient « runs identiques » — la "
     "faute exacte que la note S3 interdit : l'absence de preuve lue "
     "comme une preuve d'absence d'écart",
     CT, BANC,
     '        if not ref["runs"] or not cand["runs"]:\n'
     '            v = "non_verifiable"\n'
     '            inconnus.append(m)',
     '        if False:\n'
     '            v = "non_verifiable"\n'
     '            inconnus.append(m)'),

    ("la réserve est LEVÉE malgré les modèles non vérifiables",
     CT, BANC,
     '    levee = not differents and not inconnus',
     '    levee = not differents'),

    ("`arome_r2` perd son verdict d'archive unique et retombe dans le "
     "régime commun — la réserve devient impossible à lever, pour une "
     "différence de run qui n'existe pas",
     CT, BANC,
     '        if m == MODELE_ARCHIVE_UNIQUE:',
     '        if False:'),

    ("un objet ABSENT se lit comme un objet présent et muet",
     CT, BANC,
     '    return {"objet": key, "present": raw is not None, "n_lignes": n,',
     '    return {"objet": key, "present": True, "n_lignes": n,'),

    ("la réserve NON LUE se déclare levée — un tau non qualifié sort "
     "avec l'air d'un tau qualifié",
     CT, BANC,
     '    "levee": False,\n'
     '    "reserve": ("run_init NON LU',
     '    "levee": True,\n'
     '    "reserve": ("run_init NON LU'),

    ("la réserve ne descend plus sur les lignes de population : elle "
     "reste en tête du rapport, et chaque ligne se cite sans elle",
     CT, BANC,
     '            "reserve_run_init": reserve["reserve"],',
     '            "reserve_run_init": "",'),

    ("⭐ un seau qui refuse fait de nouveau TOMBER la verification : la "
     "reserve entiere est abandonnee pour une seule journee manquante",
     CT, BANC,
     '    try:\n'
     '        return storage.get(key), None\n'
     '    except Exception as exc:                              # noqa: BLE001\n'
     '        return None, f"{type(exc).__name__}: {exc}"',
     '    return storage.get(key), None'),

    ("un objet ILLISIBLE se lit comme un objet absent : la lecture "
     "manquee disparait du rapport",
     CT, BANC,
     '            "erreur": erreur,',
     '            "erreur": None,'),

    ("le rapport cesse d'etre ecrit par defaut : la sortie ne vit plus "
     "que dans le journal systemd, illisible d'une semaine a l'autre",
     CT, BANC,
     '    if args.rapport != "-":',
     '    if args.rapport == "@jamais":'),

    ("le compte des objets illisibles ne descend plus dans la phrase "
     "publiee",
     CT, BANC,
     "        reserve += f\" · {len(echecs)} objet(s) d'archive ILLISIBLE(S)\"",
     "        pass"),

    # ── la sélection ────────────────────────────────────────────────
    ("le filtre d'échéance saute — le classement mélange +6 h et +24 h",
     CT, BANC,
     '        if lead_h is not None and r.get("lead_h") != lead_h:',
     '        if False:'),

    ("les valeurs non finies entrent dans la médiane",
     CT, BANC,
     '        if not S._finite(r.get(value_key)):\n            continue',
     '        if False:\n            continue'),

    ("la lecture d'archive ne dégzippe plus comme `score.read_ndjson`",
     CT, BANC,
     '    try:\n'
     '        texte = gzip.decompress(raw).decode("utf-8")\n'
     '    except OSError:\n'
     '        texte = raw.decode("utf-8")',
     '    texte = raw.decode("utf-8", "ignore")'),
]


def joue(debut: int = 1, fin: int = len(MUTATIONS)) -> int:
    """⚠️ `debut`/`fin` NE SONT PAS UN CONFORT — cf. `mutations_fdr.py` :
    un processus tué laisse le fichier MUTÉ sur le disque. Jouer par
    tranches courtes, et vérifier l'intégrité après."""
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
    print("\n▶ mutations du lot L8 (tau inter-populations) — chaque ligne "
          "doit être VERTE,\n  c'est-à-dire : le banc a bien ROUGI sur la "
          "faute.\n")
    debut = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    fin = int(sys.argv[2]) if len(sys.argv) > 2 else len(MUTATIONS)
    n = joue(debut, fin)
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
