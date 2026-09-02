#!/usr/bin/env python3
"""Rejoue le banc contre des variantes CASSÉES de la sonde de plancher
(lot L6 : demi-variance des paires de balises proches).

⛔ Un banc vert ne prouve rien tant qu'on n'a pas vu ce qui le fait
rougir. Et la faute qu'on craint ici n'est pas le plantage : c'est un
plancher parfaitement lisible, en km/h, faux d'un facteur √2 — ou
gonflé par une inscription en double, ou tiré d'un pavage qui rate les
paires du nord sans jamais le dire. Aucune des mutations ci-dessous ne
fait tomber la sonde ; toutes rendent un rapport crédible et faux.

⚠️ JOUER PAR TRANCHES COURTES (`python3 mutations_sonde_representativite.py
1 8`, puis `9 16`…) : un processus TUÉ ne passe pas par son `finally` et
laisse le fichier MUTÉ sur le disque. Vécu deux fois le 27/08 au lot L3.
Contrôle d'intégrité après coup : chaque motif `avant` de la liste
`MUTATIONS` doit être présent dans son fichier.

    python3 mutations_sonde_representativite.py
"""
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent

# ⛔ (02/09/2026) copie d'origine sur le disque + sha256 + purge du
# bytecode, pour TOUS les harnais — voir `model-verif/harnais.py`.
sys.path.insert(0, str(ICI))
import harnais as HARNAIS  # noqa: E402
SONDE = ICI / "sonde_representativite.py"
BANC = ICI / "test_sonde_representativite.py"

MUTATIONS = [
    # ── LE FACTEUR ½ : tout le lot tient dans cette division ─────────
    ("le √2 devient 2 — le plancher perd 30 % sans rien changer "
     "d'autre au rapport",
     "RACINE_2 = math.sqrt(2.0)",
     "RACINE_2 = 2.0"),

    ("le ½ disparaît : la sonde publie l'écart ENTRE DEUX BALISES en "
     "l'appelant le plancher d'UNE — la faute exacte que le lot existe "
     "pour éviter",
     "    return x / RACINE_2",
     "    return x"),

    ("le √2 passe au numérateur — le plancher est multiplié par deux "
     "et reste un nombre en km/h parfaitement plausible",
     "    return x / RACINE_2",
     "    return x * RACINE_2"),

    # ── LE PAVAGE : rater des paires ne se voit sur aucun chiffre ────
    ("le pas de longitude devient FIXE (comme la latitude) : les cases "
     "rétrécissent en kilomètres vers le nord et le voisinage 3×3 se "
     "met à rater des paires — en silence, avec moins de paires et un "
     "plancher toujours lisible",
     "    pas_lon = rayon_km / (111.32 * cos_min)",
     "    pas_lon = rayon_km / 111.32"),

    ("le cosinus est pris à l'équateur (1,0) au lieu de la latitude la "
     "plus haute du jeu — même effet, plus subtil",
     "    cos_min = max(math.cos(math.radians(min(lat_max, 85.0))), 0.05)",
     "    cos_min = 1.0"),

    ("le voisinage tombe à la seule case du point : toutes les paires "
     "à cheval sur une frontière de case disparaissent",
     "        for di in (-1, 0, 1):",
     "        for di in (0,):"),

    ("une balise s'apparie avec ELLE-MÊME : une paire de distance nulle "
     "et d'écart nul par balise, qui tire le plancher vers zéro",
     "                if a == b:\n                    continue",
     "                if a is None:\n                    continue"),

    # ── LE DOUBLON : deux identifiants pour un seul capteur ──────────
    ("le doublon n'est plus détecté du tout — la balise inscrite deux "
     "fois entre dans le calcul avec un écart nul",
     "    nuls = sum(1 for e in per_hour if e == 0.0)\n"
     "    return nuls >= CLONE_PART_NULLE * len(per_hour)",
     "    return False"),

    ("le doublon se juge sur la DISTANCE SEULE : un vrai voisinage à "
     "20 m — l'observation la plus informative du jeu — est jeté avec "
     "les inscriptions en double",
     "    nuls = sum(1 for e in per_hour if e == 0.0)\n"
     "    return nuls >= CLONE_PART_NULLE * len(per_hour)",
     "    return True"),

    ("une paire dont un bout DÉMÉNAGE reste dans le calcul : sa "
     "distance n'existe plus, mais sa bande, si (lot L15)",
     "DERIVE_MAX_KM = 0.1",
     "DERIVE_MAX_KM = 10.0"),

    # ── LA POPULATION : ce qui entre et ce qui n'entre pas ───────────
    ("une paire-jour de UNE heure vaut une paire-jour de vingt : la "
     "médiane d'une journée se calcule sur un seul point",
     "MIN_HEURES_PAIRE_JOUR = 6",
     "MIN_HEURES_PAIRE_JOUR = 1"),

    ("le seuil d'heures glisse d'un cran (`<` devient `<=` de fait) — "
     "des journées valides tombent, et personne ne les compte",
     "            if se.n < MIN_HEURES_PAIRE_JOUR:",
     "            if se.n < MIN_HEURES_PAIRE_JOUR + 1:"),

    ("une balise arrivée en DEUX lignes d'archive le même jour (deux "
     "passes de collecte, lot S0.6) est ÉCRASÉE au lieu d'être "
     "recollée : une demi-journée disparaît sans rien faire rougir",
     '            echantillons.setdefault(u, []).extend(ech)',
     '            echantillons[u] = ech'),

    # ── LE PARTAGE PERSISTANT / FLUCTUANT ───────────────────────────
    ("la moyenne du vecteur d'écart oublie sa seconde division : le "
     "persistant est multiplié par n et mange tout le fluctuant",
     "    pers = (acc.su / acc.n) ** 2 + (acc.sv / acc.n) ** 2",
     "    pers = (acc.su ** 2 + acc.sv ** 2) / acc.n"),

    ("le fluctuant devient le TOTAL : l'identité de König-Huygens ne "
     "tient plus, et le rapport annonce qu'aucune correction de site "
     "ne peut rien reprendre",
     "    return ms, pers, max(0.0, ms - pers)",
     "    return ms, pers, ms"),

    ("la mise en commun du persistant n'est plus pondérée par les "
     "heures — les paires courtes pèsent autant que les longues et "
     "l'identité se met à saigner",
     "        tot_pers += pers * acc.n",
     "        tot_pers += pers"),

    ("les heures NON vectorielles entrent dans le partage : un "
     "|Δforce| scalaire y est compté comme un vecteur",
     "                if not vectorielle:\n                    continue",
     "                if vectorielle is None:\n                    continue"),

    # ── L'AGRÉGATION ET SON INTERVALLE ──────────────────────────────
    ("la colonne « médiane » est remplie avec la rms : deux colonnes "
     "identiques, dont l'une porte le mauvais nom, face à deux "
     "métriques publiées différentes",
     '            med_par_jour[e["jour"]].append(e["med"])',
     '            med_par_jour[e["jour"]].append(e["rms"])'),

    ("l'intervalle se laisse tirer sur moins de 8 jours : une fenêtre "
     "trop courte rend un IC qui a l'air d'un verdict",
     "    med_ci = INF.block_ci_by_day(med_par_jour, min_days=min_jours)",
     "    med_ci = INF.block_ci_by_day(med_par_jour, min_days=1)"),

    ("l'intervalle est tiré sur les PAIRES et non par blocs de jours — "
     "les heures d'un même jour comptent comme indépendantes et l'IC "
     "rétrécit d'un facteur qu'on ne saurait même pas nommer",
     "    med_ci = INF.block_ci_by_day(med_par_jour, min_days=min_jours)",
     "    med_ci = INF.block_ci_by_day(\n"
     "        {'tout': [x for v in med_par_jour.values() for x in v]},\n"
     "        min_days=min_jours)"),

    ("la part vectorielle est affirmée à 1 au lieu d'être comptée : le "
     "rapport ne dit plus quand il a mesuré des |Δforce| scalaires",
     '        "part_vectorielle": (n_vect / n_heures) if n_heures else 0.0,',
     '        "part_vectorielle": 1.0,'),

    # ── LES AXES ────────────────────────────────────────────────────
    ("une paire crête/vallée est rangée dans « crête » au lieu de "
     "« mixte » : le plancher d'une classe est calculé sur des paires "
     "qui n'en sont pas",
     '    return la if la == lb else "mixte"',
     "    return la"),

    ("la classe de la paire se lit DEUX FOIS sur la même balise : "
     "aucune paire n'est plus mixte, et toutes sont pures",
     '        e["terrain"] = classe_terrain(_z(a, "landform"), _z(b, "landform"))',
     '        e["terrain"] = classe_terrain(_z(a, "landform"), _z(a, "landform"))'),

    ("intra-réseau et inter-réseaux sont ÉCHANGÉS : le minorant est "
     "publié comme majorant, et l'encadrement du plancher est retourné",
     '        e["intra"] = fa == fb',
     '        e["intra"] = fa != fb'),

    ("le fournisseur retombe sur la SOURCE : deux capteurs de deux "
     "constructeurs derrière `windsmobi` repassent pour « le même "
     "réseau », et le minorant est calculé sur des paires qui n'en "
     "sont pas",
     '    return f"{s}/{n}" if n and n != s else s',
     "    return s"),

    ("les paires CO-IMPLANTÉES (d ≈ 0) rentrent dans le plancher "
     "spatial : 503 paires sur 1 170 mesuraient la chaîne au lieu de "
     "la distance, et tiraient le chiffre publié à 0,63 km/h",
     "DIST_MIN_KM = 0.1",
     "DIST_MIN_KM = 0.0"),

    ("les REPUBLICATIONS à coordonnée décalée ne sont plus détectées : "
     "`pioupiou:1494` et `windsmobi:ffvl-3494`, à 111 m et 0,30 km/h "
     "d'accord, comptent comme un voisinage",
     "SEUIL_QUASI_KMH = 1.0",
     "SEUIL_QUASI_KMH = 0.0"),

    ("le plancher « hors quasi-identiques » est calculé SUR les "
     "quasi-identiques — le rapport publie donc, sous le nom de la "
     "lecture propre, exactement la population contaminée",
     '        if (e["a"], e["b"]) not in quasi and e["dist"] <= RAYONS_KM[1]],',
     '        if (e["a"], e["b"]) in quasi and e["dist"] <= RAYONS_KM[1]],'),

    ("la partition est inversée : le plancher spatial est calculé sur "
     "les seules paires co-implantées",
     '    co_implantees = [e for e in retenus if e["dist"] < DIST_MIN_KM]\n'
     '    gardes = [e for e in retenus if e["dist"] >= DIST_MIN_KM]',
     '    co_implantees = [e for e in retenus if e["dist"] >= DIST_MIN_KM]\n'
     '    gardes = [e for e in retenus if e["dist"] < DIST_MIN_KM]'),

    ("les étiquettes du profil repassent par `bande_distance` appelée "
     "sur les BORNES : la première bande sort deux fois et la "
     "dernière (2,2–3,0 km, la plus peuplée) ne sort pas du tout — "
     "et le profil a l'air complet",
     "    for b in _etiquettes_bandes():",
     "    for b in [bande_distance(x) for x in (0.0,) + BANDES_KM[:-1]]:"),

    ("le dénivelé change de signe avant d'être rangé en bandes : deux "
     "balises à 300 m d'écart vertical passent pour deux balises du "
     "même étage",
     "    dz = abs(dz)",
     "    dz = -abs(dz)"),

    # ── L'APPARIEMENT LUI-MÊME ──────────────────────────────────────
    ("la demi-fenêtre du côté A tombe à 5 min pendant que "
     "`pair_series` garde ses 20 : les deux bouts ne sont plus moyennés "
     "de la même façon, et l'écart cesse d'être symétrique",
     "                  demi_fenetre_ms: int = S.OBS_HALF_WINDOW_MS):",
     "                  demi_fenetre_ms: int = 5 * 60 * 1000):"),

    ("le côté A prend le PREMIER relevé de la fenêtre au lieu de la "
     "moyenne vectorielle — l'autre côté, lui, moyenne toujours",
     "        sp, di, _n = S.mean_wind(win) if win else (None, None, 0)",
     "        sp, di, _n = ((win[0].speed, win[0].dir, 1) if win\n"
     "                      else (None, None, 0))"),
]


def joue(debut: int = 1, fin: int = len(MUTATIONS)) -> int:
    rouges = 0
    origine = HARNAIS.garder(SONDE)
    for i, (nom, avant, apres) in enumerate(MUTATIONS, 1):
        if not (debut <= i <= fin):
            continue
        if avant not in origine:
            print(f"  ⛔ {i:>2}. {nom}\n       MOTIF INTROUVABLE — la "
                  f"mutation n'a rien muté, donc elle n'a rien prouvé.")
            rouges += 1
            continue
        try:
            SONDE.write_text(origine.replace(avant, apres, 1),
                             encoding="utf-8")
            r = subprocess.run([sys.executable, str(BANC)],
                               capture_output=True, text=True, cwd=ICI,
                               env=HARNAIS.env_banc(ICI))
            if r.returncode == 0:
                print(f"  ❌ {i:>2}. {nom}\n       LE BANC RESTE VERT — il "
                      f"ne tient pas cette propriété.")
                rouges += 1
            else:
                l = [x.strip() for x in r.stdout.splitlines()
                     if x.strip().startswith("❌")]
                if not l:
                    l = [x.strip() for x in r.stderr.splitlines()[-2:]]
                print(f"  ✅ {i:>2}. {nom}\n       {l[0] if l else 'banc rouge'}"
                      + (f" (+{len(l) - 1} autres)" if len(l) > 1 else ""))
        finally:
            HARNAIS.rendre(SONDE, origine)
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations de la sonde de plancher (lot L6) — chaque ligne "
          "doit être VERTE,\n  c'est-à-dire : le banc a bien ROUGI sur la "
          "faute.\n")
    d = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    f = int(sys.argv[2]) if len(sys.argv) > 2 else len(MUTATIONS)
    n = joue(d, f)
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} non vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
