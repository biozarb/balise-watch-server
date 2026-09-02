#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/controle_position.py — LE GARDE-FOU DE POSITION
#                                              (Lot L15, 02/09/2026)
#
#  ⛔⛔ POURQUOI CE FICHIER EXISTE. Rien, jusqu'ici, ne comparait la
#  position GELÉE d'une balise (celle où AGRUME lit sa colonne) à la
#  position VIVANTE (celle où l'observation est relevée, et où tous les
#  modèles Open-Meteo vont chercher leur prévision) en dehors d'un
#  `freeze_balises.py` lancé À LA MAIN. C'est ce silence qui a laissé
#  passer onze jours de dérive sans que personne ne le sache, et
#  `pioupiou:1333` être notée **147 km** à côté de ses observations,
#  chaque nuit, depuis le 16/08.
#
#  ⚠️ CE CONTRÔLE NE CORRIGE RIEN, ET C'EST DÉLIBÉRÉ — c'est la règle
#  que `freeze_balises.geler()` écrit déjà : « On SIGNALE, on ne corrige
#  pas tout seul. Déplacer une balise dans l'artefact changerait la
#  colonne archivée sous le même identifiant, donc casserait la
#  comparabilité de son historique sans que rien ne le dise. » Il nomme,
#  et il propose une suspension de NOTATION (`position_suspecte`) que
#  Yann pose par `.sql`.
#
#  ═══ CE QU'IL COMPARE, ET POURQUOI CE COUPLE-LÀ ═══
#
#  Ce qui abîme un score n'est pas qu'une balise ait déménagé : c'est
#  que la PRÉVISION et l'OBSERVATION d'une même ligne ne parlent plus du
#  même endroit. AGRUME lit sa colonne à la position GELÉE ; l'observation
#  arrive à la position du RÉFÉRENTIEL, recopiée dans chaque ligne
#  d'archive obs par `collect.py`. L'écart entre ces deux positions-là
#  EST le défaut, **quelle que soit celle qui a raison** — et mesuré le
#  02/09, ce n'est pas toujours le gel : sur 25 divergences tranchées
#  par le catalogue live, **12 sont des déménagements (gel périmé) mais
#  9 sont un RÉFÉRENTIEL FAUX** (`pioupiou:1730` : gel à 0 m du
#  catalogue, référentiel à 2 292 m, depuis 12 jours). Dans les deux cas
#  le classement compare des modèles à qui on n'a pas posé la même
#  question, et c'est ça qu'on suspend.
#
#  ═══ LE CRITÈRE : LE NŒUD **ET** LA DISTANCE ═══
#
#  ⭐ Le nœud seul ne suffit pas : `pioupiou:1588` change de nœud pour
#  **14 m**, parce que sa position tombe sur un bord de maille. Le vent
#  servi change bel et bien de colonne, mais la balise n'a pas bougé et
#  la suspendre coûterait une balise-jour pour rien.
#  ⭐ La distance seule ne suffit pas non plus : 500 m dans la même
#  maille ne changent pas d'un chiffre ce qui est noté (3 des
#  11 déplacements confirmés du 27/08 étaient dans ce cas).
#  ⇒ On exige les DEUX. Le nœud est calculé avec l'arithmétique de
#  `quantification.index_plats` sur le meta RELU dans les artefacts
#  d'orographie (jamais écrit en dur : le jour où Météo-France déplace
#  le coin de grille, un nombre en dur mentirait sans le dire).
#
#  ═══ N = 10 JOURS, ET POURQUOI CE N'EST PAS UN CHIFFRE ROND ═══
#
#  ⛔⛔ LA PERSISTANCE « EN JOURS » A FAILLI NE RIEN MESURER.
#  `collect.py::load_stations` ne rafraîchit `stations.json` que si le
#  fichier a plus de `max_age_days = 7` jours. Mesuré sur 27 jours
#  d'archives (sonde du 02/09) : les positions n'ont changé que
#  **4 jours sur 27** — 14/08 (364 balises), 21/08 (362), 25/08 (1),
#  28/08 (382). Entre deux rafraîchissements, une position NE PEUT PAS
#  bouger : « N jours d'affilée » avec N < 7 ne mesure que le calendrier
#  du rafraîchissement, pas la stabilité de la position.
#
#  ⭐ D'où N = 10, mesuré et non choisi : les épisodes de divergence qui
#  se sont REFERMÉS (la balise est revenue) durent min 4 j, médiane 7 j,
#  **max 8 j** — exactement un cycle. À N = 8 il reste 1 fausse alarme
#  sur l'historique ; **à N = 10 il n'en reste aucune**, et 9 balises
#  sont retenues. Le prix est écrit : un vrai déménagement attend dix
#  jours avant d'être nommé. C'est le prix d'un chien qui n'aboie pas
#  pour rien — le lot LV a mesuré ce que coûte l'autre choix (315 cris,
#  vingt jours d'affilée, personne n'écoute).
#
#  ═══ POURQUOI AUCUN FICHIER D'ÉTAT POUR LA PERSISTANCE ═══
#
#  La persistance se RECALCULE chaque nuit depuis les archives obs des
#  dix derniers jours, au lieu d'être accumulée dans un compteur. Un
#  compteur se perd (machine réinstallée, dossier d'état nettoyé) et
#  rend alors le garde-fou muet dix nuits sans que rien ne le dise —
#  exactement le défaut du poller Infoclimat du lot LD, muet 28 jours.
#  Le recalcul, lui, est vrai au premier run et se répare tout seul.
#  Son coût est mesuré et jalonné (`jalon_memoire`), pas supposé.
#
#  ⚠️ Le SEUL fichier d'état est le jeton d'anti-répétition du cri, et
#  il échoue OUVERT : illisible ou inécrivable, on crie quand même.
#
#  ═══ USAGE ═══
#
#      # dans le run nocturne : appelé par score.py, rien à lancer
#      # à la main, pour voir :
#      ~/venv-balise/bin/python3 controle_position.py --out /var/lib/bw-model-verif
#      ~/venv-balise/bin/python3 controle_position.py --sql   # le .sql proposé
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from geopair import distance_km                              # noqa: E402

#: ⚠️ RECOPIÉ de `agrume/freeze_balises.SEUIL_DEPLACEMENT_M`, PAS importé.
#: `score.py` — qui appelle ce module — ne doit dépendre ni de numpy ni
#: du paquet `agrume/` (règle écrite dans `score.fcst_agrume_key`), et
#: `freeze_balises` importe `domaine`, qui tire tout le paquet. Le banc
#: `test_controle_position.py` IMPORTE les deux et assure qu'elles sont
#: égales : une constante recopiée sans gardien dérive, celle-ci ne peut
#: pas.
SEUIL_DEPLACEMENT_M = 200.0

#: Idem pour la distance : `freeze_balises.distance_m` est une
#: équirectangulaire, `geopair.distance_km` une haversine. Le banc
#: vérifie qu'elles s'accordent à mieux que 1 % sur des cas réels de la
#: BBOX — au-delà, ce module devrait cesser de prétendre mesurer la
#: même chose.

#: Mesuré, cf. le pavé. ⛔ NE PAS descendre sous 8 sans remesurer les
#: épisodes refermés : c'est le cycle de rafraîchissement de
#: `collect.py` (7 jours) qui fixe ce plancher, pas une prudence.
SEUIL_PERSISTANCE_J = 10

#: Le gel, relu là où `agrume/` l'écrit. ⓘ Chemin, pas import.
GEL = (pathlib.Path(__file__).resolve().parent.parent
       / "agrume" / "data" / "balises-nord-alpes.json")
DATA_OROG = pathlib.Path(__file__).resolve().parent.parent / "agrume" / "data"

#: Le fichier d'état du cri (anti-répétition). Dans le dossier d'état du
#: job, comme `echecs_consecutifs.*` — donc dans un chemin que l'unité
#: systemd déclare déjà en `ReadWritePaths` (leçon du lot LV : le jeton
#: posé dans `$HOME` d'une unité durcie ne s'écrit jamais).
NOM_JETON = "position_confirmees.json"


# ══════════════════════════════════════════════════════════════════
#  LE NŒUD
# ══════════════════════════════════════════════════════════════════

def metas_grilles(data=DATA_OROG):
    """Le meta de chaque maille, RELU dans les artefacts d'orographie.

    ⛔ Ne PAS écrire 55,4 / −12,0 / 0,01 en dur. Ces trois nombres
    viennent du GRIB de Météo-France ; `quantification.verifier_grille`
    surveille déjà leur changement côté production, et un nombre en dur
    ici mentirait en silence le jour où ils bougent. Si les domaines ne
    s'accordent pas, le nœud n'est pas définissable et on le DIT plutôt
    que d'en choisir un.
    """
    metas: dict[str, dict] = {}
    vus: dict[str, set] = {}
    for f in sorted(pathlib.Path(data).glob("orographie-*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for grille, v in (d.get("grilles") or {}).items():
            m = v.get("meta") or {}
            cle = (m.get("lat0"), m.get("lon0"), m.get("di"), m.get("dj"),
                   m.get("jScan"))
            vus.setdefault(grille, set()).add(cle)
            metas.setdefault(grille, m)
    desaccords = {g: c for g, c in vus.items() if len(c) > 1}
    if desaccords:
        raise ValueError(
            f"les artefacts d'orographie ne s'accordent pas sur le meta "
            f"des grilles {sorted(desaccords)} — le nœud n'est pas "
            f"définissable")
    return metas


def noeud(meta, lat, lon):
    """(i, j) du plus proche voisin — LA MÊME arithmétique que
    `quantification.index_plats`, sans numpy et sans le paquet
    `agrume/`. Le banc la confronte à `index_plats` sur les balises
    réelles du gel : la copie ne peut pas dériver en silence."""
    i = round((lon - meta["lon0"]) / meta["di"])
    j = (round((meta["lat0"] - lat) / meta["dj"]) if meta.get("jScan") != 1
         else round((lat - meta["lat0"]) / meta["dj"]))
    return (i, j)


# ══════════════════════════════════════════════════════════════════
#  LES DEUX POSITIONS
# ══════════════════════════════════════════════════════════════════

def charger_gel(chemin=GEL):
    """{(source, id): balise} — l'axe figé, lu comme un fichier.

    ⓘ `(source, id)` et non `id` : c'est la clé d'identité posée par le
    lot L7 (`freeze_balises._identite`), depuis que l'axe porte six
    réseaux qui numérotent chacun de leur côté.
    """
    d = json.loads(pathlib.Path(chemin).read_text(encoding="utf-8"))
    return {(b.get("source") or "pioupiou", str(b["id"])): b
            for b in d.get("balises", [])}, d.get("ecrit_le")


def positions_des_obs(rows):
    """{(source, id): (lat, lon)} — la position que la chaîne a
    RÉELLEMENT utilisée, relue dans les lignes d'archive obs.

    ⚠️ On garde la PREMIÈRE vue. Une balise republiée par deux réseaux
    (lot L16) apparaît deux fois sous deux clés différentes : ce n'est
    donc pas le cas visé ici, et deux positions sous la MÊME clé le même
    jour seraient un défaut d'un autre genre — moyenner les cacherait.
    """
    vues = {}
    for r in rows:
        lat, lon = r.get("lat"), r.get("lon")
        if lat is None or lon is None:
            continue
        cle = (r.get("source") or "pioupiou", str(r.get("station_id")))
        vues.setdefault(cle, (round(float(lat), 4), round(float(lon), 4)))
    return vues


def diverge(balise_gelee, position, metas):
    """(distance_m, nœud_0,01 change, nœud_0,025 change, déclenche)."""
    d = distance_km(balise_gelee["lat"], balise_gelee["lon"],
                    position[0], position[1]) * 1000.0
    n001 = (noeud(metas["001"], *position)
            != noeud(metas["001"], balise_gelee["lat"], balise_gelee["lon"]))
    n0025 = (noeud(metas["0025"], *position)
             != noeud(metas["0025"], balise_gelee["lat"],
                      balise_gelee["lon"]))
    return d, n001, n0025, bool(n001 and d > SEUIL_DEPLACEMENT_M)


def persistances(gel, positions_par_jour, metas, jours_tries):
    """{cle: nombre de jours VUS et divergents d'affilée jusqu'au dernier
    jour}, pour les seules balises qui divergent le dernier jour.

    ⚠️ Un jour où la balise n'est pas vue N'INTERROMPT PAS le compte : il
    ne dit rien. Le traiter comme « pas de divergence » remettrait le
    compteur à zéro chaque fois qu'une balise passe une nuit hors ligne
    — et une balise déménagée est justement une balise qu'on débranche.
    """
    out = {}
    for cle, b in gel.items():
        n = 0
        for j in reversed(jours_tries):
            p = positions_par_jour.get(j, {}).get(cle)
            if p is None:
                continue
            if not diverge(b, p, metas)[3]:
                break
            n += 1
        if n:
            out[cle] = n
    return out


# ══════════════════════════════════════════════════════════════════
#  LE CONTRÔLE
# ══════════════════════════════════════════════════════════════════

def verifier(root, day, par_jour, gel_chemin=GEL, metas=None,
             seuil_jours=SEUIL_PERSISTANCE_J):
    """Le cœur, PUR : il ne lit aucun fichier d'archive lui-même.

    `par_jour` : {"YYYY-MM-DD": {(source, id): (lat, lon)}} — des
    positions DÉJÀ RÉDUITES par `positions_des_obs`, pas des lignes
    d'archive.

    ⛔⛔ ET C'EST UNE QUESTION DE MÉMOIRE, PAS DE GOÛT. La première
    version prenait les lignes brutes et les réduisait ici : dix
    journées d'archive tenaient alors ensemble en mémoire, et la mesure
    sur le VPS (02/09) a dit **906 Mo**. Le run de notation culmine déjà
    à 1 474 Mo pour un plafond de 2 800, et la nuit du 28/08 est morte à
    2 820 (lot LM). L'appelant réduit donc CHAQUE journée dès qu'il l'a
    lue et lâche les lignes : le pic retombe à une seule journée.
    """
    metas = metas or metas_grilles()
    gel, ecrit_le = charger_gel(gel_chemin)
    jours_tries = sorted(par_jour)
    jour_j = day.strftime("%Y-%m-%d") if hasattr(day, "strftime") else str(day)

    pers = persistances(gel, par_jour, metas, jours_tries)
    lignes = []
    for cle, n in pers.items():
        b = gel[cle]
        p = par_jour.get(jour_j, {}).get(cle)
        if p is None:                      # pas vue la nuit notée
            for j in reversed(jours_tries):
                p = par_jour[j].get(cle)
                if p is not None:
                    break
        if p is None:
            continue
        d, n001, n0025, _ = diverge(b, p, metas)
        lignes.append(dict(
            id=f"{cle[0]}:{cle[1]}", source=cle[0], station_id=cle[1],
            nom=b.get("name") or "", metres=round(d), noeud_001=n001,
            noeud_0025=n0025, jours=n, confirmee=n >= seuil_jours,
            gel=(b["lat"], b["lon"]), vivante=p, gelee_le=b.get("vue_le")))
    lignes.sort(key=lambda x: (-x["jours"], -x["metres"]))
    return dict(jour=jour_j, gel_ecrit_le=ecrit_le, seuil_jours=seuil_jours,
                jours_lus=len(jours_tries), lignes=lignes,
                confirmees=[x["id"] for x in lignes if x["confirmee"]])


def texte_journal(r):
    """Ce que le run écrit chaque nuit, cri ou pas. ⚠️ Il écrit AUSSI
    quand tout va bien : un contrôle dont on ne voit la ligne que les
    jours de panne est indistinguable d'un contrôle qui ne tourne plus
    (règle du lot LD, § « un garde-fou oublié en position ouverte »)."""
    n_c = len(r["confirmees"])
    L = [f"  {'⛔' if n_c else 'ⓘ'} position : {len(r['lignes'])} balise(s) "
         f"divergent du gel ({r['jours_lus']} j lus), dont {n_c} "
         f"CONFIRMÉE(S) (≥ {r['seuil_jours']} j)"]
    for x in r["lignes"]:
        L.append(f"     {'⛔' if x['confirmee'] else '·'} {x['id']:<22} "
                 f"{x['metres']:>7} m · {x['jours']:>2} j · "
                 f"nœud 0,01 {'CHANGE' if x['noeud_001'] else 'même'}"
                 f"{' · profil 0,025 CHANGE' if x['noeud_0025'] else ''}"
                 f" · {x['nom'][:30]}")
    if not r["lignes"]:
        L.append("     (aucune : le gel et le référentiel tombent dans la "
                 "même maille partout)")
    return "\n".join(L)


def jeton(etat_dir):
    return pathlib.Path(etat_dir) / NOM_JETON


def jeton_en_attente(etat_dir):
    """Le jeton tel que `score.py` le DÉPOSE : il n'est pas encore posé.

    ⛔ (02/09/2026) C'est `run.sh` qui le renomme en `jeton()` — et
    SEULEMENT après qu'un e-mail est sorti (`ALERTE_LIVREE`). Tant qu'il
    porte ce suffixe, `cri()` ne le lit pas : l'ensemble n'est pas
    « connu », on recriera demain.
    """
    return pathlib.Path(etat_dir) / (NOM_JETON + ".attente")


def cri(r, etat_dir):
    """Le texte à envoyer DEHORS, ou None s'il n'y a rien de neuf.

    ⚠️ ON NE CRIE QUE SUR UN CHANGEMENT D'ENSEMBLE, pas toutes les nuits.
    Neuf balises confirmées le resteront des semaines : un cri par nuit
    ferait 9 lignes × 30 jours d'un avertissement qu'on apprend à
    ignorer — la faute exacte que le lot LV a mesurée (315 cris, dont un
    vingt jours d'affilée dans le vide).
    ⛔ MAIS IL ÉCHOUE OUVERT : jeton illisible ou inécrivable ⇒ on crie.
    Un dispositif d'alerte ne doit pas se taire parce que son propre
    état est cassé.
    """
    courant = sorted(r["confirmees"])
    connu = None
    try:
        connu = sorted(json.loads(jeton(etat_dir).read_text(
            encoding="utf-8")).get("balises", []))
    except Exception:                                    # noqa: BLE001
        connu = None
    if connu is not None and connu == courant:
        return None
    entrantes = [x for x in courant if connu is None or x not in connu]
    sortantes = [x for x in (connu or []) if x not in courant]
    if not entrantes and not sortantes:
        return None
    par_id = {x["id"]: x for x in r["lignes"]}
    L = [f"Le gel des balises et le referentiel vivant ne tombent plus dans "
         f"la meme maille AROME pour {len(courant)} balise(s), depuis au "
         f"moins {r['seuil_jours']} jours.",
         "",
         "Consequence : AGRUME lit sa colonne a la position GELEE pendant que "
         "l'observation arrive a la position du REFERENTIEL. Les modeles ne "
         "sont pas notes au meme endroit, et le classement de ces balises "
         "compare des reponses a deux questions differentes.", ""]
    for i in entrantes:
        x = par_id.get(i)
        L.append(f"  + {i} : {x['metres']} m, {x['jours']} j — {x['nom']}"
                 if x else f"  + {i}")
    for i in sortantes:
        L.append(f"  - {i} : rentree dans l'ordre (le referentiel et le gel "
                 f"se sont rejoints, ou la balise n'est plus vue)")
    L += ["",
          "Ce controle NE CORRIGE RIEN (regle de freeze_balises.geler : on "
          "signale, on ne deplace pas une balise dans un artefact archive).",
          "Geste : trancher chaque cas — correction de coordonnees ou AUTRE "
          "balise ? — puis poser position_suspecte + position_note sur "
          "station_zone par .sql.",
          "Le detail chiffre est dans le journal du run, ligne « position : »."]
    return "\n".join(L)


def poser_jeton(r, etat_dir, en_attente: bool = False):
    """⚠️ Écrit APRÈS l'envoi, jamais avant : si le canal tombe, on
    recriera demain. Bruyant, jamais muet.

    ⛔ ET LA PROMESSE N'ÉTAIT PAS TENUE (vérification du 02/09/2026) :
    `score.py` l'appelait dans la foulée du dépôt du cri, et l'envoi
    avait lieu plus tard, dans `run.sh`, dont `alerter` rend 0 même
    quand msmtp échoue. `en_attente=True` — le seul usage de `score.py`
    désormais — écrit `jeton_en_attente()`, que `run.sh` promeut en
    jeton une fois l'e-mail parti. L'appel sans `en_attente` reste
    pour les bancs et pour un opérateur qui veut poser le jeton à la
    main.
    """
    try:
        p = jeton_en_attente(etat_dir) if en_attente else jeton(etat_dir)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(
            {"annonce_le": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
             "jour_note": r["jour"], "balises": sorted(r["confirmees"])},
            ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:                                    # noqa: BLE001
        pass                                             # échouer ouvert


# ══════════════════════════════════════════════════════════════════
#  LE .SQL PROPOSÉ — préparé, JAMAIS exécuté d'ici
# ══════════════════════════════════════════════════════════════════

def sql_suspension(r, catalogue=None):
    """Le `.sql` que Yann exécute. Une ligne par balise confirmée.

    ⚠️ LA NOTE EST LE LIVRABLE, pas le drapeau. Sans elle, personne ne
    saura dans six mois pourquoi la balise est sortie du classement —
    c'est le format des 3 notes déjà en base (`pioupiou:1410` :
    « Hautacam 1670m (nom) : le vrai Hautacam est à ~55 km de ces
    coordonnées… »). On écrit donc les DEUX positions, l'écart, la durée,
    et, quand le catalogue live a été interrogé, LEQUEL des deux a tort.
    """
    par_id = {x["id"]: x for x in r["lignes"]}
    L = ["-- ══════════════════════════════════════════════════════════",
         "--  Lot L15 — suspension de NOTATION des balises dont le gel et",
         "--  le référentiel ne tombent plus dans la même maille AROME.",
         f"--  Généré le {datetime.now(timezone.utc):%Y-%m-%d %H:%M} Z par "
         "controle_position.py",
         "--",
         "--  ⚠️ SUSPEND LA NOTATION, PAS L'ARCHIVAGE. `score.py` honore",
         "--  `position_suspecte` en deux endroits : la balise sort de",
         "--  l'agrégation de zone (donc du classement) et GARDE sa ligne",
         "--  `model_verif_daily` et sa colonne d'archive.",
         "--  ⓘ L'artefact gelé n'est PAS marqué (arbitrage du 02/09) :",
         "--  le produit A garde sa colonne, l'archive reste rejouable.",
         "-- ══════════════════════════════════════════════════════════",
         ""]
    for i in sorted(r["confirmees"]):
        x = par_id[i]
        verdict = (catalogue or {}).get(i, {}).get("verdict")
        note = (f"Lot L15 ({datetime.now(timezone.utc):%d/%m/%Y}) : position "
                f"gelée ({x['gel'][0]:.4f}, {x['gel'][1]:.4f}) et position "
                f"du référentiel ({x['vivante'][0]:.4f}, "
                f"{x['vivante'][1]:.4f}) séparées de {x['metres']} m, "
                f"depuis {x['jours']} jours consécutifs, et pas dans le même "
                f"nœud AROME 0,01°. AGRUME note donc à un autre endroit que "
                f"celui d'où viennent les observations.")
        if verdict:
            note += f" Troisième avis (catalogue live) : {verdict}."
        note += (" Suspendue de la NOTATION, pas de l'archivage. À trancher : "
                 "correction de coordonnées (l'historique d'avant n'est plus "
                 "comparable) ou autre balise (elle doit cesser d'être notée "
                 "sous cet identifiant) ?")
        L.append(
            f"update station_zone set position_suspecte = true, "
            f"position_note = {_lit(note)} "
            f"where source = {_lit(x['source'])} "
            f"and station_id = {_lit(x['station_id'])};")
    L += ["",
          "-- contrôle après exécution :",
          "-- select source, station_id, position_suspecte, position_note",
          "--   from station_zone where position_suspecte;"]
    return "\n".join(L)


def _lit(s):
    """Littéral SQL. ⓘ Les notes portent des apostrophes françaises et
    des accents ; on double la quote et on ne se fie à rien d'autre."""
    return "'" + str(s).replace("'", "''") + "'"


# ══════════════════════════════════════════════════════════════════
#  CLI — pour rejouer à la main, jamais dans un timer
# ══════════════════════════════════════════════════════════════════

def main(argv=None):
    import score as SC                                   # noqa: PLC0415

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="/var/lib/bw-model-verif")
    p.add_argument("--day", default=None)
    p.add_argument("--jours", type=int, default=SEUIL_PERSISTANCE_J)
    p.add_argument("--sql", action="store_true",
                   help="écrire le .sql de suspension sur la sortie")
    p.add_argument("--verdicts", default=None, metavar="JSON",
                   help="sortie --json de sonde_position_l15.py : ses "
                        "verdicts du catalogue live entrent alors dans les "
                        "`position_note`. ⓘ Ce module n'interroge AUCUN "
                        "réseau lui-même — le run nocturne n'a pas à "
                        "dépendre de la disponibilité de Pioupiou.")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    root = pathlib.Path(a.out)
    day = (datetime.strptime(a.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
           if a.day else datetime.now(timezone.utc) - timedelta(days=1))
    day = day.replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        import storage as ST                             # noqa: PLC0415
        st = ST.make_storage()
    except Exception:                                    # noqa: BLE001
        st = None
    # ⚠️ Une journée à la fois, réduite tout de suite : cf. le pavé de
    # `verifier`. Tenir les dix ensemble coûtait 906 Mo.
    pos = {}
    for k in range(a.jours):
        _d = day - timedelta(days=k)
        pos[_d.strftime("%Y-%m-%d")] = positions_des_obs(
            SC.all_obs_rows(root, _d, st))
    r = verifier(root, day, pos, seuil_jours=a.jours)
    verdicts = None
    if a.verdicts:
        verdicts = (json.loads(pathlib.Path(a.verdicts).read_text(
            encoding="utf-8")).get("catalogue") or None)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    elif a.sql:
        print(sql_suspension(r, verdicts))
    else:
        print(texte_journal(r))
        print(f"\n  ⓘ {Counter(x['confirmee'] for x in r['lignes'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
