#!/usr/bin/env python3
"""Rejoue le banc contre des variantes CASSÉES de la sonde de doublons
(lot L16 : déduplication des réseaux d'observation).

⛔ Un banc vert ne prouve rien tant qu'on n'a pas vu ce qui le fait
rougir. Et ici la faute qu'on craint ne fait pas tomber la sonde : elle
retire des observations RÉELLES du classement (faux positif), ou laisse
le double comptage en place en annonçant l'avoir traité (faux négatif).
Dans les deux cas le rapport reste lisible, les chiffres restent
plausibles, et rien ne rougit.

⚠️ JOUER PAR TRANCHES COURTES (`python3 mutations_sonde_doublons.py 1 7`,
puis `8 14`…) : un processus TUÉ — y compris par le plafond de 45 s d'un
appel `device_bash` — ne passe pas par son `finally` et laisse le
fichier MUTÉ sur le disque. Vécu quatre fois les 27/08 (L3, L6).
Contrôle d'intégrité après coup : chaque motif `avant` de la liste
`MUTATIONS` doit être présent dans son fichier.

    python3 mutations_sonde_doublons.py
"""
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent

# ⛔ (02/09/2026) copie d'origine sur le disque + sha256 + purge du
# bytecode, pour TOUS les harnais — voir `model-verif/harnais.py`.
sys.path.insert(0, str(ICI))
import harnais as HARNAIS  # noqa: E402
SONDE = ICI / "sonde_doublons.py"
BANC = ICI / "test_sonde_doublons.py"

MUTATIONS = [
    # ── LES SEUILS : trop large = on jette du vrai ───────────────────
    ("le seuil de distance passe à 3 km : deux VRAIES balises voisines "
     "d'un même site de vol sont déclarées « la même balise », et leurs "
     "observations disparaissent du classement",
     "SEUIL_DIST_KM = 0.3",
     "SEUIL_DIST_KM = 3.0"),

    ("le seuil de distance tombe à un mètre : les republications à "
     "coordonnée décalée (les 15 `pioupiou` ↔ `windsmobi/ffvl` du L6) "
     "échappent, et le rapport annonce quand même « traité »",
     "SEUIL_DIST_KM = 0.3",
     "SEUIL_DIST_KM = 0.001"),

    ("le seuil d'accord passe à 10 km/h : tout ce qui est proche devient "
     "un doublon, y compris deux décollages opposés d'une même crête",
     "SEUIL_ECART_KMH = 1.0",
     "SEUIL_ECART_KMH = 10.0"),

    ("le seuil d'accord tombe à 0,05 km/h : seules les copies au bit "
     "près sont vues, et l'arrondi d'un des deux flux suffit à cacher "
     "un doublon",
     "SEUIL_ECART_KMH = 1.0",
     "SEUIL_ECART_KMH = 0.05"),

    ("l'incompatibilité disparaît : deux inscriptions au même point qui "
     "mesurent des vents à 11 km/h d'écart (le cas `STATIC0022` du L6) "
     "sont dédupliquées comme si c'était la même balise — on garderait "
     "l'une des deux AU HASARD, coordonnée fausse comprise",
     "SEUIL_INCOMPATIBLE_KMH = 4.0",
     "SEUIL_INCOMPATIBLE_KMH = 1000.0"),

    ("le minimum d'heures tombe à 1 : une paire vue trois heures rend un "
     "verdict aussi affirmatif qu'une paire vue trois cents",
     "MIN_HEURES_VERDICT = 120",
     "MIN_HEURES_VERDICT = 1"),

    ("« je ne sais pas » devient « voisin » : les paires trop courtes se "
     "rangent silencieusement du côté rassurant, et le rapport ne compte "
     "plus son incertitude",
     '    if ecart is None or n_heures < MIN_HEURES_VERDICT:\n'
     '        return "indecidable"',
     '    if ecart is None:\n        return "indecidable"'),

    ("les étiquettes du tableau croisé repassent par `bande()` appelée "
     "sur les BORNES : la première bande sort deux fois et la dernière "
     "bande finie ne sort pas du tout — le tableau qui JUSTIFIE les "
     "seuils devient faux, et il a l'air complet",
     "    return [f\"≤ {b:g}\" for b in bornes] + [f\"> {bornes[-1]:g}\"]",
     "    return [bande(x, bornes) for x in (0.0,) + tuple(bornes[:-1])] \\\n"
     "        + [f\"> {bornes[-1]:g}\"]"),

    ("« voisin » redevient possible AU MÊME POINT : les 47 paires "
     "`metar` ↔ `mf` (deux flux du même mât d'aérodrome, 2,1 km/h "
     "d'écart parce que le METAR est en nœuds entiers) repassent pour "
     "deux balises distinctes et restent comptées deux fois",
     '    return "doublon" if ecart <= SEUIL_ECART_KMH else "doublon_probable"',
     '    return "doublon" if ecart <= SEUIL_ECART_KMH else "voisin"'),

    ("la lecture LARGE devient la lecture étroite : l'encadrement se "
     "referme sur sa borne basse et le rapport publie un chiffre unique "
     "là où il n'en existe pas",
     'RETENUS_LARGE = ("doublon", "doublon_probable")',
     'RETENUS_LARGE = ("doublon",)'),

    ("la lecture ÉTROITE retire déjà les probables : la borne basse de "
     "l'encadrement n'est plus une borne basse",
     'RETENUS_ETROIT = ("doublon",)',
     'RETENUS_ETROIT = ("doublon", "doublon_probable")'),

    # ── LA TRANSITIVITÉ ─────────────────────────────────────────────
    ("l'union ne relie plus rien : A≡B et B≡C font deux paires et TROIS "
     "composantes d'un membre — on garderait les trois inscriptions en "
     "croyant avoir dédupliqué",
     "            self.parent[rb] = ra",
     "            _ = ra"),

    ("les composantes ne sortent plus TRIÉES : leurs membres suivent "
     "l'itération d'un `set` et les composantes celle d'un `dict` — le "
     "départage lexical de `choisir` cesse d'être déterministe, et deux "
     "exécutions peuvent désigner deux représentants différents",
     "        return [sorted(v) for _k, v in sorted(out.items())]",
     "        return [list(v) for _k, v in out.items()]"),

    # ── LA PREUVE NOMINALE, QUI N'EST PAS UN CRITÈRE ────────────────
    ("deux chiffres communs suffisent à crier au doublon : la "
     "corroboration nominale devient du bruit",
     "    return da[-n:] if n >= 3 else None",
     "    return da[-n:] if n >= 1 else None"),

    ("le suffixe d'identifiant devient un CRITÈRE : seuls les doublons "
     "qui ont la politesse de partager une convention de nommage sont "
     "vus, et le rapport ne peut plus dire combien il en rate",
     '            if p["verdict"] in verdicts_retenus:\n'
     '                comp.unir(p["a"], p["b"])',
     '            if p["verdict"] in verdicts_retenus and p["suffixe"]:\n'
     '                comp.unir(p["a"], p["b"])'),

    # ── LA RÈGLE ────────────────────────────────────────────────────
    ("`pioupiou` perd sa priorité : la balise notée par AGRUME est "
     "écartée au profit d'une inscription qui porte plus de modèles — "
     "et `agrume`/`agrume_pi` disparaissent de la case",
     "        return (0 if SR.reseau(u) == SOURCE_AGRUME else 1,",
     "        return (0,"),

    ("le critère « modèles » est inversé : on garde l'inscription du "
     "groupe RÉDUIT (5 modèles) et on jette celle du groupe complet (9)",
     '                -d["n_modeles"], -d["n_jours"], -d["heures"], u)',
     '                d["n_modeles"], -d["n_jours"], -d["heures"], u)'),

    ("le départage final n'est plus lexical : à égalité parfaite, c'est "
     "l'ordre d'arrivée qui décide, donc le classement peut changer "
     "d'une nuit à l'autre sans qu'aucune donnée n'ait bougé",
     '                -d["n_modeles"], -d["n_jours"], -d["heures"], u)',
     '                -d["n_modeles"], -d["n_jours"], -d["heures"], "")'),

    ("une inscription ABSENTE de la base passe pour la mieux couverte "
     "(défauts à l'infini au lieu de zéro) et rafle le billet",
     '        d = faits.get(u) or {"n_modeles": 0, "n_jours": 0, "heures": 0}',
     '        d = faits.get(u) or {"n_modeles": 99, "n_jours": 99,\n'
     '                             "heures": 99}'),

    ("la règle ne retire personne : chaque composante garde tous ses "
     "membres, et le rapport annonce quand même ses composantes traitées",
     '        perdus = [u for u in c["membres"] if u != g]',
     "        perdus = []"),

    # ── LES FAITS ───────────────────────────────────────────────────
    ("les faits comptent les LIGNES au lieu des modèles distincts : "
     "une balise notée par un seul modèle sur trente jours bat une "
     "balise notée par neuf modèles sur cinq",
     '        d["modeles"].add(r["model"])',
     '        d["modeles"].add(f"{r[\'model\']}/{r[\'day\']}")'),

    ("les heures ne s'additionnent plus, elles se remplacent",
     '            d["heures"] += int(r["n_hours"])',
     '            d["heures"] = int(r["n_hours"])'),

    ("le contrôle de câblage compare la nuit à ELLE-MÊME : les deux "
     "chemins s'accordent toujours, et un `est_doublon` mal câblé dans "
     "`score.py` ne serait plus vu par personne",
     "        ap2 = rejouer(units, zone_colonne, as_of, lambda *_a, **_k: None)",
     "        ap2 = rejouer(apres_units, zone_of, as_of, lambda *_a, **_k: None)"),

    ("la colonne injectée pour le contrôle n'est plus celle que "
     "`score.py` lit : le contrôle passe au vert en ne contrôlant rien",
     '            zone_colonne[u][SC.COL_DOUBLON] = "(peu importe qui)"',
     '            zone_colonne[u]["doublon"] = "(peu importe qui)"'),

    # ── LE `.sql` DE PEUPLEMENT ─────────────────────────────────────
    ("le `.sql` devient ADDITIF : il ne remet plus `doublon_de` à null "
     "avant de poser, donc les doublons d'une mesure précédente qui "
     "n'en sont plus survivent — et personne ne sait plus quel état la "
     "base porte",
     '    A("update public.station_zone set doublon_de = null")\n'
     '    A(" where doublon_de is not null;")',
     '    A("-- (remise à null retirée)")'),

    ("le `.sql` marque le REPRÉSENTANT au lieu de l'écarté : "
     "`_case_rows` écarte toute ligne dont `doublon_de` est posé, donc "
     "la case perd ses DEUX inscriptions et se tait — l'inverse exact "
     "du geste",
     '        A(f"update public.station_zone set doublon_de = {_lit(garde)}")\n'
     '        A(f" where source = {_lit(src)} and station_id = {_lit(sid)};")',
     '        gsrc, gsid = garde.split(":", 1)\n'
     '        A(f"update public.station_zone set doublon_de = {_lit(perdu)}")\n'
     '        A(f" where source = {_lit(gsrc)} and station_id = {_lit(gsid)};")'),

    ("les identifiants ne sont plus échappés : un `station_id` qui "
     "porte une apostrophe casse la requête — au mieux",
     '    return "\'" + str(s).replace("\'", "\'\'") + "\'"',
     '    return "\'" + str(s) + "\'"'),

    ("le contrôle « un représentant lui-même écarté » disparaît du "
     "`.sql` : la boucle A→B→A ne serait plus détectée à l'exécution",
     '    A("select count(*) as representants_eux_memes_ecartes")',
     '    A("select 0 as representants_eux_memes_ecartes")'),

    # ── LE DÉGÂT ────────────────────────────────────────────────────
    ("la seconde nuit est rejouée SANS retirer les doublons : le "
     "rapport compare la nuit à elle-même et conclut « aucun effet »",
     '    apres_units = [u for u in units if u["unit"] not in ecartes]',
     "    apres_units = list(units)"),

    ("le quorum de stations tombe à 1 : la case à deux vraies balises et "
     "un doublon survit à la déduplication, et le dommage le plus net du "
     "lot devient invisible",
     '    scores = SC._case_rows(units, zone_of, as_of, "rolling15", "all",\n'
     "                           SC.MIN_STATIONS_ZONE, with_ci=False)",
     '    scores = SC._case_rows(units, zone_of, as_of, "rolling15", "all",\n'
     "                           1, with_ci=False)"),

    ("le `n` d'une case compte ses LIGNES et non ses balise-jours : "
     "l'inflation mesurée tombe à zéro alors que la case compte cinq "
     "balises pour quatre",
     '        out[SC._cle_de_case(r)] += int(r.get("occurrences") or 0)',
     "        out[SC._cle_de_case(r)] += 1"),

    ("les cases perdues sont calculées à l'envers : la sonde annonce "
     "que la déduplication CRÉE des cases",
     '    perdues = av["cases"] - ap["cases"]',
     '    perdues = ap["cases"] - av["cases"]'),

    ("les heures d'une paire se comptent par JOUR et non par heure : "
     "toutes les paires passent sous le minimum et deviennent "
     "indécidables — un rapport qui ne conclut rien, poliment",
     "            heures[cle] += se.n",
     "            heures[cle] += 1"),
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
    print("\n▶ mutations de la sonde de doublons (lot L16) — chaque ligne "
          "doit être VERTE,\n  c'est-à-dire : le banc a bien ROUGI sur la "
          "faute.\n")
    d = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    f = int(sys.argv[2]) if len(sys.argv) > 2 else len(MUTATIONS)
    n = joue(d, f)
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} non vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
