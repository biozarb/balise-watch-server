#!/usr/bin/env python3
"""
test_gh_dispatch.py — banc du déclencheur de workflow, HORS-LIGNE.

    python3 tools/test_gh_dispatch.py

⚠️ CE QUE CE BANC PROTÈGE. Un dispatch a trois modes de panne et les
trois sont SILENCIEUX :

 1. il part vers la mauvaise URL (dépôt mal découpé) → HTTP 404, qui
    ressemble à un problème de droits ; on cherche le jeton pendant une
    heure alors que c'est la chaîne « dépôt:workflow » qui est fautive ;
 2. il ne part pas du tout (jeton absent, DNS muet) et l'appelant croit
    avoir déclenché — c'est la panne que le lot LW veut justement
    supprimer, il serait absurde de la réintroduire ici ;
 3. il journalise le jeton. Une fois écrit dans journald, un jeton est à
    révoquer.

D'où un banc qui vérifie la requête RÉELLEMENT construite — URL, méthode,
en-têtes, corps — et pas seulement la valeur de retour.

Aucun réseau, aucun jeton réel : `urlopen` est injecté.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gh_dispatch import cible, dispatch_github  # noqa: E402

echecs = []


def verifier(nom, condition, detail=""):
    if condition:
        print(f"  ✓ {nom}" + (f"   {detail}" if detail else ""))
    else:
        print(f"  ✗ {nom}" + (f"   {detail}" if detail else ""))
        echecs.append(nom)


class Reponse:
    """Le minimum qu'un `with urlopen(...) as r:` exige."""

    def __init__(self, status=204):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def capteur(status=204):
    """Rend (ouvrir, vues) : `vues` collecte les requêtes construites."""
    vues = []

    def ouvrir(req, timeout=None):
        vues.append((req, timeout))
        return Reponse(status)

    return ouvrir, vues


JETON = "ghp_CECI_EST_UN_FAUX_JETON_0123456789"


def avec_jeton(valeur=JETON):
    if valeur is None:
        os.environ.pop("GITHUB_DISPATCH_TOKEN", None)
    else:
        os.environ["GITHUB_DISPATCH_TOKEN"] = valeur


def main():
    print("\n── La requête réellement construite ─────────────────────")
    avec_jeton()
    ouvrir, vues = capteur()
    lignes = []
    ok = dispatch_github("biozarb/balise-watch-server", "arome-wind.yml",
                         crier=lignes.append, ouvrir=ouvrir)
    verifier("un dispatch accepté rend True", ok is True)
    verifier("une seule requête, pas de nouvelle tentative muette",
             len(vues) == 1, f"{len(vues)} requête(s)")
    req = vues[0][0]
    verifier("l'URL est celle de l'API workflows/dispatches",
             req.full_url == ("https://api.github.com/repos/"
                              "biozarb/balise-watch-server/actions/"
                              "workflows/arome-wind.yml/dispatches"),
             req.full_url)
    verifier("la méthode est POST (un GET rendrait 200 sans rien lancer)",
             req.get_method() == "POST", req.get_method())
    corps = json.loads(req.data.decode())
    verifier("le corps porte la branche et des entrées vides",
             corps == {"ref": "main", "inputs": {}}, str(corps))
    # ⚠️ urllib capitalise les noms d'en-tête : on compare en minuscules.
    ent = {k.lower(): v for k, v in req.headers.items()}
    verifier("l'en-tête Authorization porte « Bearer <jeton> »",
             ent.get("authorization") == f"Bearer {JETON}")
    verifier("⛔ l'en-tête Accept de l'API GitHub est présent — sans lui "
             "l'API peut répondre dans un autre format",
             ent.get("accept") == "application/vnd.github+json")
    verifier("la version d'API est épinglée",
             ent.get("x-github-api-version") == "2022-11-28")
    verifier("le corps est déclaré JSON",
             ent.get("content-type") == "application/json")
    verifier("un délai d'attente est posé (jamais d'attente infinie)",
             isinstance(vues[0][1], (int, float)) and vues[0][1] > 0,
             f"{vues[0][1]} s")

    print("\n── ⛔ Le jeton ne fuit nulle part ───────────────────────")
    verifier("aucune ligne journalisée ne contient le jeton",
             all(JETON not in x for x in lignes), " | ".join(lignes))
    verifier("…et le succès est tout de même DIT (un dispatch muet ne se "
             "distingue pas d'un dispatch absent)",
             any("déclenché" in x for x in lignes))

    print("\n── Les trois façons de ne pas partir ────────────────────")
    avec_jeton(None)
    ouvrir, vues = capteur()
    lignes = []
    ok = dispatch_github("d/e", "w.yml", crier=lignes.append, ouvrir=ouvrir)
    verifier("⛔ sans jeton : rend False", ok is False)
    verifier("⛔ …et n'ouvre AUCUNE connexion", not vues, f"{len(vues)}")
    verifier("⛔ …et le DIT (le silence serait la panne qu'on répare)",
             any("GITHUB_DISPATCH_TOKEN absent" in x for x in lignes))

    avec_jeton()

    def ouvrir_http(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url, 403, "Forbidden", {},
            __import__("io").BytesIO(b'{"message":"Resource not accessible"}'))

    lignes = []
    ok = dispatch_github("d/e", "w.yml", crier=lignes.append,
                         ouvrir=ouvrir_http)
    verifier("un refus HTTP rend False", ok is False)
    verifier("…et le code ET le motif sont dits",
             any("403" in x and "not accessible" in x for x in lignes),
             " | ".join(lignes))

    def ouvrir_reseau(req, timeout=None):
        raise urllib.error.URLError("Name or service not known")

    lignes = []
    ok = dispatch_github("d/e", "w.yml", crier=lignes.append,
                         ouvrir=ouvrir_reseau)
    verifier("⛔ RÉSEAU COUPÉ : rend False au lieu de lever — c'est le "
             "défaut trouvé au lot LW, il tuait le poller en boucle",
             ok is False)
    verifier("…et le motif réseau est dit, pas une trace Python",
             any("réseau ou DNS" in x for x in lignes), " | ".join(lignes))

    print("\n── La cible « dépôt:workflow » ─────────────────────────")
    verifier("une cible bien formée se découpe",
             cible("biozarb/balise-watch-server:arome-wind.yml")
             == ("biozarb/balise-watch-server", "arome-wind.yml"))
    verifier("⛔ le séparateur est le DERNIER « : »",
             cible("a/b:c:w.yml") == ("a/b:c", "w.yml"))
    for mauvaise in ("", None, "sans-deux-points.yml", ":w.yml",
                     "a/b:", "pasdeslash:w.yml"):
        try:
            cible(mauvaise)
            verifier(f"cible illisible refusée : {mauvaise!r}", False)
        except ValueError:
            verifier(f"cible illisible refusée : {mauvaise!r}", True)

    print("\n── Ce que l'appelant peut imposer ──────────────────────")
    ouvrir, vues = capteur()
    dispatch_github("a/b", "w.yml", ref="essai", entrees={"x": "1"},
                    crier=lambda *_: None, ouvrir=ouvrir)
    verifier("la branche et les entrées passent jusqu'au corps",
             json.loads(vues[0][0].data.decode())
             == {"ref": "essai", "inputs": {"x": "1"}})

    print("\n  gh_dispatch :", "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
