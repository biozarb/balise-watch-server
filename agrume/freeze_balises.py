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

from domaine import DOMAINE, dans_domaine  # noqa: E402

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
    if man.get("domaine") != DOMAINE:
        raise Abort(
            f"⚠️ l'artefact a été figé sur un AUTRE domaine "
            f"({man.get('domaine')}) que celui du code ({DOMAINE}). Les "
            f"colonnes archivées et celles à venir ne porteraient pas sur "
            f"les mêmes balises. Régénérer explicitement.")
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
        if c.get("source") != "radiosondage" and not dans_domaine(c["lat"], c["lon"]):
            continue
        ancienne = connues.get(c["id"])
        if ancienne is None:
            connues[c["id"]] = dict(c, position_suspecte=False,
                                    vue_le=datetime.now(timezone.utc)
                                    .strftime("%Y-%m-%d"))
            ajouts += 1
            continue
        d = distance_m((ancienne["lat"], ancienne["lon"]), (c["lat"], c["lon"]))
        if d > SEUIL_DEPLACEMENT_M:
            deplacements.append((c["id"], ancienne["name"], round(d)))
        ancienne["name"] = c["name"] or ancienne["name"]
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
    est trié ailleurs, par `colonnes.balises_du_domaine()`, et sur la
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

    manifeste = dict(
        produit="AGRUME — axe des balises du domaine Nord-Alpes, figé",
        ecrit_le=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        domaine=DOMAINE,
        n=len(balises),
        note=("Fusion À AJOUT SEUL : une balise hors ligne n'est jamais "
              "retirée, sinon l'axe de l'archive se décalerait et son "
              "historique deviendrait orphelin. Régénérer avec "
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
            print(f"▶ artefact du {man['ecrit_le']} · {man['n']} balises · "
                  f"domaine {man['domaine']}")
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
