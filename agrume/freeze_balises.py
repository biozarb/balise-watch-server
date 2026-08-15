#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/freeze_balises.py — l'axe « balise » de l'archive, figé
#                                                        (10/08/2026)
#
#  ⚠️ POURQUOI CETTE LISTE EST UN ARTEFACT COMMITÉ ET PAS UN APPEL RÉSEAU.
#
#  L'archive du produit A est disposée en `(balise, paramètre, niveau,
#  échéance)`. **L'axe des balises doit donc être STABLE d'un run à
#  l'autre**, sinon concaténer deux runs demande de remapper les indices
#  — et personne ne s'en apercevrait avant d'avoir empilé des semaines de
#  colonnes décalées les unes par rapport aux autres.
#
#  Or le référentiel amont ne l'est pas : `collect.py::load_stations` se
#  rafraîchit depuis le catalogue LIVE de Pioupiou, où une balise à
#  batterie plate disparaît puis revient. C'est exactement pour ça que
#  `collect.py` applique une discipline d'AJOUT SEUL — « on ajoute, on
#  marque `seen_at`, on ne retire jamais » — et c'est cette même
#  discipline qu'on reprend ici.
#
#  Le second avantage est pratique : l'ingestion tourne sur GitHub
#  Actions, qui n'a accès ni au VPS ni à `/var/lib/bw-model-verif`. Une
#  liste commitée rend le run **autonome et reproductible** : rejouer un
#  run d'il y a un mois donne le même axe qu'à l'époque, ce qu'un appel
#  au catalogue live ne garantit pas.
#
#  ⚠️ Ce script se lance À LA MAIN, jamais dans un run — même raison que
#  `freeze_orographie.py` : un axe qui se régénère tout seul n'est plus
#  un axe.
#
#      python3 agrume/freeze_balises.py --stations /var/lib/bw-model-verif/stations.json
#      python3 agrume/freeze_balises.py --catalogue     # depuis Pioupiou
#      python3 agrume/freeze_balises.py --verifier
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from domaine import (DOMAINES, ZONES_INTERET,  # noqa: E402
                     dans_domaine, dans_zone_interet, domaine_de)

ARTEFACT = Path(__file__).resolve().parent / "data" / "balises-nord-alpes.json"
PIOUPIOU_LIVE = "https://api.pioupiou.fr/v1/live-with-meta/all"

# Déplacement au-delà duquel on considère que ce n'est plus la même
# position. 200 m : au-delà, la balise change probablement de maille en
# 0,01° (1,1 km) et sûrement de colonne — donc l'historique archivé sous
# cet identifiant cesse d'être comparable.
SEUIL_DEPLACEMENT_M = 200.0


class Abort(Exception):
    pass


def distance_m(a, b):
    """Distance approchée entre deux (lat, lon), en mètres. Suffisante
    pour détecter un déménagement, pas pour de la navigation."""
    import math
    dlat = (a[0] - b[0]) * 111195.0
    dlon = (a[1] - b[1]) * 111195.0 * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot(dlat, dlon)


def depuis_catalogue():
    """Le catalogue live de Pioupiou — la même source que `collect.py`."""
    req = urllib.request.Request(
        PIOUPIOU_LIVE, headers={"User-Agent": "balise-watch-agrume/1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.loads(r.read().decode("utf-8"))
    out = []
    for d in payload.get("data", []):
        loc = d.get("location") or {}
        lat, lon = loc.get("latitude"), loc.get("longitude")
        if lat is None or lon is None:
            continue
        out.append(dict(id=str(d["id"]), source="pioupiou",
                        lat=round(float(lat), 4), lon=round(float(lon), 4),
                        name=(d.get("meta") or {}).get("name") or ""))
    return out


def charger_artefact(chemin=ARTEFACT):
    p = Path(chemin)
    if not p.exists():
        raise Abort(f"artefact de balises absent ({p.name}) — le régénérer "
                    f"avec `python3 agrume/freeze_balises.py`")
    man = json.loads(p.read_text(encoding="utf-8"))
    # ⚠️ 12/08 — le garde-fou compare maintenant TOUS les domaines, et il
    # accepte encore l'ancienne forme à un seul (`domaine`). Ce n'est pas
    # de la complaisance : un axe figé le 10/08 décrit exactement les
    # mêmes balises qu'aujourd'hui côté Alpes, et le refuser ferait
    # échouer tout run lancé entre le déploiement du code et le regel de
    # l'axe. Ce qu'il doit attraper reste intact — un axe figé sur des
    # bornes qui ne sont plus celles du code.
    #
    # ⛔⛔ 15/08 — CE TEST S'EST TROMPÉ DE CIBLE, ET ÇA A COÛTÉ 3 BALISES.
    # `fige != attendu` compare l'ENSEMBLE des domaines : ajouter un
    # TROISIÈME domaine (`tarn-aveyron-herault`) l'a fait lever, pour la
    # mauvaise raison — rien n'avait changé côté Nord-Alpes ni Pyrénées.
    # Et `geler()` rattrape cet `Abort` en le lisant comme « aucun
    # artefact existant » (`except Abort: existantes = []`) : la
    # discipline d'AJOUT SEUL saute entièrement, et toute balise pas
    # LIVE à l'instant précis du gel est perdue en silence — constaté :
    # 1333, 1361, 365 disparus d'un axe qui n'aurait dû que grandir.
    #
    # Le vrai invariant à protéger n'est PAS « les deux ensembles de
    # domaines sont identiques », c'est « aucun domaine DÉJÀ FIGÉ n'a
    # changé de bornes ». Un domaine ajouté DEPUIS le dernier gel n'en
    # est pas un — c'est exactement le cas que le message d'avertissement
    # ci-dessous existe pour couvrir, pas pour être contredit par l'Abort
    # juste au-dessus.
    fige = man.get("domaines")
    if fige is None and man.get("domaine") is not None:
        fige = {"nord-alpes": man["domaine"]}
    attendu = {n: d for n, d in DOMAINES.items()}
    if fige is None:
        raise Abort(
            f"⚠️ l'artefact ne porte aucun domaine reconnaissable "
            f"({man.keys()}). Régénérer explicitement.")
    incoherents = {n: (fige[n], attendu.get(n)) for n in fige
                  if n not in attendu or attendu[n] != fige[n]}
    if incoherents:
        raise Abort(
            f"⚠️ l'artefact a été figé sur des BORNES DIFFÉRENTES de "
            f"celles du code pour {sorted(incoherents)} — {incoherents}. "
            f"Les colonnes archivées et celles à venir ne porteraient pas "
            f"sur les mêmes balises. Régénérer explicitement.")
    nouveaux = [n for n in DOMAINES if n not in fige]
    if nouveaux:
        print(f"  ⚠️ axe figé AVANT l'ajout de {', '.join(nouveaux)} : "
              f"les balises de ce(s) domaine(s) ne seront pas archivées "
              f"tant que `freeze_balises.py` n'aura pas été relancé.")
    return man["balises"], man


def fusionner(existantes, candidates, crier=print):
    """Fusion À AJOUT SEUL, comme `collect.py`.

    Renvoie (liste triée, nb_ajouts, deplacements).

    ⚠️ Une balise absente du catalogue n'est PAS retirée : elle est
    peut-être seulement hors ligne. La retirer décalerait l'axe de
    l'archive et rendrait son historique orphelin — le défaut que
    `collect.py` évite depuis l'origine, pour la même raison.
    """
    connues = {b["id"]: dict(b) for b in existantes}
    ajouts, deplacements = 0, []
    for c in candidates:
        # ⚠️ Les points de RADIOSONDAGE sont volontairement HORS du
        # domaine (Payerne est 0,51° au nord de `latmax`). Ils ne sont
        # pas des balises : ils portent `source = "radiosondage"`, et
        # c'est ce marqueur — pas leur position — qui les fait entrer.
        # Aucun score de balise ne doit les avaler par erreur.
        # ⚠️ 12/08 — TROIS façons d'entrer dans l'axe, et une seule qui
        # donne droit au produit B. Une balise d'une ZONE D'INTÉRÊT hors
        # de toute boîte entre elle aussi : sa colonne ne coûte rien de
        # plus (indexation sur la grille native) et l'archive est
        # définitive. Elle est marquée `hors_domaine` pour que personne ne
        # la croie servie par le calque ou la coupe.
        dans_boite = dans_domaine(c["lat"], c["lon"])
        if (c.get("source") != "radiosondage" and not dans_boite
                and not dans_zone_interet(c["lat"], c["lon"])):
            continue
        ancienne = connues.get(c["id"])
        if ancienne is None:
            connues[c["id"]] = dict(c, position_suspecte=False,
                                    hors_domaine=not dans_boite
                                    and c.get("source") != "radiosondage",
                                    vue_le=datetime.now(timezone.utc)
                                    .strftime("%Y-%m-%d"))
            ajouts += 1
            continue
        d = distance_m((ancienne["lat"], ancienne["lon"]), (c["lat"], c["lon"]))
        if d > SEUIL_DEPLACEMENT_M:
            deplacements.append((c["id"], ancienne["name"], round(d)))
        ancienne["name"] = c["name"] or ancienne["name"]
        # ⛔ 15/08 — `hors_domaine` N'ÉTAIT JAMAIS RECALCULÉ POUR UNE
        # BALISE DÉJÀ CONNUE. Une balise gelée AVANT l'ajout d'un
        # troisième domaine restait marquée `hors_domaine=True` même
        # quand ce nouveau domaine la couvre désormais — constaté à
        # l'ajout de `tarn-aveyron-herault` : 10 balises géométriquement
        # DANS la boîte (Dourgne, Lautrec, Curvalle…) sont restées
        # étiquetées comme isolées. Ce n'est PAS le défaut que la
        # discipline d'ajout seul protège — on ne RETIRE personne, on
        # corrige juste un champ. Recalculer sur la position FIGÉE
        # (`ancienne`, jamais `c` qui peut avoir bougé sans validation —
        # cf. `deplacements` ci-dessus) et ne jamais faire flipper
        # `False → True` : les domaines ne rétrécissent pas
        # (`verifier_domaines_disjoints`/le refus d'élargir un domaine
        # existant l'empêchent), donc seul `True → False` est un cas
        # légitime.
        etait_hors = ancienne.get("hors_domaine", False)
        est_hors = (not dans_domaine(ancienne["lat"], ancienne["lon"])
                   and ancienne.get("source") != "radiosondage")
        if etait_hors and not est_hors:
            crier(f"  ⓘ {c['id']} · {ancienne['name']} : entre dans un "
                  f"domaine de production (n'est plus hors_domaine)")
            ancienne["hors_domaine"] = False
    return sorted(connues.values(), key=_rang), ajouts, deplacements


def _rang(b):
    """Position d'un point dans l'axe.

    ⚠️ CE QUE CET AXE GARANTIT, ET CE QU'IL NE GARANTIT PAS — constaté le
    10/08 en y ajoutant les radiosondages.

    L'en-tête de ce fichier dit que « l'axe des balises doit être STABLE
    d'un run à l'autre, sinon concaténer deux runs demande de remapper
    les indices ». La discipline d'ajout seul garantit qu'aucune balise ne
    DISPARAÎT. Elle ne garantit PAS que les positions ne bougent pas :
    l'axe est trié par identifiant, donc une nouvelle balise Pioupiou
    d'identifiant plus petit qu'une balise existante DÉCALE toutes celles
    qui la suivent. Ça n'a rien cassé jusqu'ici parce que chaque archive
    porte SA propre liste `balises` dans son manifeste et que
    `sonder.py::trouver_balise` cherche par identifiant — mais empiler
    deux runs sur l'indice, comme la promesse le suggère, serait faux.
    À traiter comme une décision à part ; ici on se contente de ne PAS
    aggraver.

    D'où le premier terme du tri : les points de radiosondage passent
    APRÈS toutes les balises, quoi qu'il arrive. Sans lui, un
    identifiant non numérique comme « RS-06610 » tomberait en TÊTE de ce
    fichier (`int(...) if isdigit() else 0`), ce qui se lit très mal.

    ⚠️ Et ce tri-ci ne range QUE le fichier figé. L'axe réel de l'archive
    est trié ailleurs, par `quantification.balises_du_domaine()`, et sur la
    CHAÎNE de l'identifiant. Deux tris pour une même notion, c'est un de
    trop — c'est écrit des deux côtés en attendant qu'on tranche.
    """
    radiosondage = 1 if b.get("source") == "radiosondage" else 0
    return (radiosondage,
            int(b["id"]) if str(b["id"]).isdigit() else 0,
            str(b["id"]))


def points_radiosondage():
    """Les stations actives, en candidates pour l'axe.

    ⚠️ `source = "radiosondage"` est le marqueur qui les distingue d'une
    balise partout ailleurs dans la chaîne : ce ne sont pas des
    anémomètres, elles n'ont pas de mesure à comparer, et aucun score ne
    doit les traiter comme des balises."""
    from radiosondage import STATIONS
    return [dict(id=f"RS-{s['wmo']}", source="radiosondage",
                 lat=s["lat"], lon=s["lon"],
                 name=f"Radiosondage {s['nom']} ({s['wmo']})")
            for s in STATIONS if s["active"]]


def geler(candidates, suspectes=(), chemin=ARTEFACT, crier=print):
    try:
        existantes, _ = charger_artefact(chemin)
    except Abort:
        existantes = []
    # Les points de radiosondage entrent à CHAQUE gel, comme les balises
    # du catalogue : la discipline d'ajout seul s'occupe de ne pas les
    # dupliquer, et une station qu'on désactive dans `radiosondage.py`
    # n'est pas retirée de l'axe pour autant — sinon l'axe se décalerait.
    balises, ajouts, deplacements = fusionner(
        existantes, list(candidates) + points_radiosondage(), crier)
    sus = {str(x) for x in suspectes}
    for b in balises:
        if b["id"] in sus:
            b["position_suspecte"] = True

    if deplacements:
        # ⚠️ On SIGNALE, on ne corrige pas tout seul. Déplacer une balise
        # dans l'artefact changerait la colonne archivée sous le même
        # identifiant, donc casserait la comparabilité de son historique
        # sans que rien ne le dise. C'est une décision, pas un détail.
        crier(f"\n⚠️ {len(deplacements)} balise(s) ONT BOUGÉ de plus de "
              f"{SEUIL_DEPLACEMENT_M:.0f} m depuis le gel :")
        for i, nom, d in deplacements:
            crier(f"     {i} · {nom} · {d} m")
        crier("   La position figée est CONSERVÉE. Décider explicitement : "
              "soit c'est une correction de coordonnées (et l'historique "
              "d'avant n'est plus comparable), soit la balise a déménagé "
              "(et c'est une autre balise).")

    # ⚠️ 12/08 — l'axe couvre DEUX domaines, et le nom du fichier ment.
    # `balises-nord-alpes.json` porte maintenant aussi les Pyrénées. Le
    # renommer serait plus propre à lire et plus risqué à faire : c'est
    # le fichier que `charger_artefact()` ouvre, et un renommage est la
    # seule opération de ce module qui puisse casser un run en cours de
    # journée. Le manifeste dit donc la vérité que le nom ne dit pas —
    # et le renommage reste ouvert, comme un geste à part.
    par_domaine = {}
    for b in balises:
        d = domaine_de(b["lat"], b["lon"])
        par_domaine[d or "hors domaine"] = par_domaine.get(d or "hors domaine", 0) + 1
    manifeste = dict(
        produit="AGRUME — axe des balises, figé (tous domaines)",
        ecrit_le=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        domaines=DOMAINES,
        zones_interet=ZONES_INTERET,
        n=len(balises),
        n_par_domaine=par_domaine,
        n_hors_domaine=sum(1 for b in balises if b.get("hors_domaine")),
        note=("Fusion À AJOUT SEUL : une balise hors ligne n'est jamais "
              "retirée, sinon l'axe de l'archive se décalerait et son "
              "historique deviendrait orphelin. ⚠️ L'ajout seul garantit "
              "qu'aucune balise ne DISPARAÎT ; il ne garantit PAS que les "
              "positions dans ce fichier ne bougent pas — l'axe est trié "
              "par identifiant (cf. `_rang`), donc une balise d'identifiant "
              "plus petit décale les suivantes. Chaque archive porte SA "
              "propre liste et la recherche se fait par identifiant, jamais "
              "par indice. ⚠️ Le nom du fichier dit « nord-alpes » pour des "
              "raisons de continuité ; l'axe couvre tous les domaines de "
              "`domaine.DOMAINES`. Régénérer avec "
              "`python3 agrume/freeze_balises.py`."),
        balises=balises)
    Path(chemin).parent.mkdir(parents=True, exist_ok=True)
    Path(chemin).write_text(
        json.dumps(manifeste, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    crier(f"\n▶ {len(balises)} balises dans le domaine ({ajouts} ajoutées), "
          f"{Path(chemin).stat().st_size / 1024:.0f} Ko")
    return manifeste


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stations", default=None,
                   help="référentiel écrit par collect.py (à préférer : il "
                        "porte déjà la discipline d'ajout seul)")
    p.add_argument("--catalogue", action="store_true",
                   help="interroger le catalogue live de Pioupiou")
    p.add_argument("--suspectes", default=None)
    p.add_argument("--radiosondages-seulement", action="store_true",
                   help="ajoute uniquement les points de radiosondage, sans "
                        "toucher aux balises")
    p.add_argument("--verifier", action="store_true")
    a = p.parse_args(argv)

    try:
        if a.verifier:
            balises, man = charger_artefact()
            # ⚠️⚠️ CETTE LIGNE A CASSÉ LA PRODUCTION LE 12/08 AU SOIR, et
            # elle mérite d'être racontée : la clé du manifeste est passée
            # de `domaine` à `domaines` avec le second domaine (commit
            # `c06de92`), `charger_artefact` ci-dessus a été rendu tolérant
            # aux deux formes — et CE `print`-ci, dix lignes plus bas, est
            # resté au singulier. `KeyError: 'domaine'`, sur un artefact
            # parfaitement valide, dans une vérification qui ne vérifiait
            # plus rien puisqu'elle levait avant.
            #
            # ⛔ CE QUI L'A LAISSÉ PASSER N'EST PAS L'INATTENTION, C'EST
            # L'ABSENCE DE BANC. `--verifier` ne tourne que dans le
            # workflow ; le workflow n'avait pas été relancé depuis le
            # renommage. `test_freeze_balises.py` existe maintenant et
            # rejoue exactement ce chemin. *« Un banc qu'on ne lance
            # jamais cesse de protéger » — celui-ci n'existait même pas.*
            #
            # ⓘ Les deux formes sont acceptées ici comme ailleurs : entre
            # le déploiement du code et le regel d'un artefact, il existe
            # toujours une fenêtre où l'ancienne circule.
            doms = man.get("domaines")
            if doms is None and man.get("domaine") is not None:
                doms = {"nord-alpes": man["domaine"]}
            print(f"▶ artefact du {man['ecrit_le']} · {man['n']} balises · "
                  f"domaine(s) : {', '.join(sorted(doms or {})) or '—'}")
            par = man.get("n_par_domaine") or {}
            if par:
                # ⓘ Publié parce que c'est LE chiffre qui bouge quand un
                # domaine entre ou sort : un total de 203 ne dit pas si
                # les Pyrénées sont dedans.
                print("  " + " · ".join(f"{k} : {v}"
                                        for k, v in sorted(par.items())))
            sus = [b for b in balises if b.get("position_suspecte")]
            print(f"  {len(sus)} à position suspecte (marquées, pas retirées)")
            return 0
        if a.radiosondages_seulement:
            # ⚠️ N'ajoute QUE les points de radiosondage. Sans ça, il
            # faudrait passer par le catalogue live, qui ajouterait aussi
            # les balises Pioupiou apparues depuis le dernier gel — et
            # mélangerait deux changements d'axe dans un seul commit.
            candidates = []
        elif a.stations:
            candidates = json.loads(
                Path(a.stations).read_text(encoding="utf-8"))
        elif a.catalogue:
            candidates = depuis_catalogue()
        else:
            raise Abort("préciser --stations <fichier>, --catalogue ou "
                        "--radiosondages-seulement")
        suspectes = (json.loads(Path(a.suspectes).read_text(encoding="utf-8"))
                     if a.suspectes else [])
        geler(candidates, suspectes)
        return 0
    except Abort as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
