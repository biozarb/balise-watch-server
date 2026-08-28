#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  tools/gh_dispatch.py — déclencher une GitHub Action depuis le VPS
#                                                        (lot LW, 28/08/2026)
#
#  ⛔ POURQUOI CE MODULE EXISTE, ET POURQUOI IL EST DANS `tools/`.
#  La fonction vivait dans `agrume/poller.py` depuis le 10/08 et n'avait
#  qu'un seul appelant. Le lot LW lui en donne un second
#  (`model-verif/filet_arome_wind.py`), et le projet a déjà tranché ce
#  cas deux fois : `mf_s3.bornes_echeances()` (« une seule expression
#  régulière pour tout le projet, au lieu d'une par appelant ») et le
#  refus, dans `arome-rallonge`, d'un second point d'entrée écrivant le
#  même objet — « deux façons d'écrire le même objet, c'est-à-dire deux
#  façons de se tromper ».
#  ⇒ Un seul chemin de déclenchement pour tout le dépôt. `poller.py`
#  l'IMPORTE désormais et n'en garde aucune copie.
#
#  ⚠️ CE QUE CE MODULE NE FAIT PAS, ET C'EST VOULU : il ne décide pas
#  QUAND déclencher, et il ne vérifie pas que le déclenchement a produit
#  quoi que ce soit. Il POSTe et il rend compte. Le « quand » appartient
#  à l'appelant — le poller le déduit d'un guet, le filet d'un horaire —
#  et le « qu'est-ce que ça a produit » appartient au job qui relit
#  l'objet publié. Mélanger les trois donnerait un module qu'on ne peut
#  ni bancer ni relire.
#
#  ⚠️ LE JETON NE SE JOURNALISE JAMAIS. Il est lu dans l'environnement
#  (`GITHUB_DISPATCH_TOKEN`) et n'apparaît dans aucun message, aucune
#  trace d'erreur, aucun `repr`. Les messages d'échec ne recopient que
#  les 200 premiers octets du CORPS de la réponse GitHub, qui ne
#  contient pas la requête.
# ══════════════════════════════════════════════════════════════════════
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

#: Délai d'attente du POST, en secondes. ⓘ Le dispatch est une écriture
#: minuscule (quelques centaines d'octets) : 30 s couvrent très
#: largement une latence réseau, et bornent l'attente d'un appelant qui,
#: lui, tourne sous un chien de garde.
TIMEOUT_S = 30


def dispatch_github(depot, workflow, ref="main", entrees=None, crier=print,
                    ouvrir=None):
    """Déclenche un `workflow_dispatch`. Optionnel, et volontairement
    minimal : le VPS décide QUAND, l'Action fait le travail.

    ⚠️ Le jeton se lit dans l'environnement et n'est jamais journalisé.
    Sans jeton, on ne déclenche rien et on le DIT — un dispatch qui
    échoue en silence donnerait un poller qui a l'air de marcher et une
    chaîne qui ne tourne jamais.

    `ouvrir` n'existe que pour les bancs : c'est `urllib.request.urlopen`
    par défaut. ⓘ Injecté plutôt que rustiné (`monkeypatch`) parce que
    le banc doit pouvoir vérifier l'URL, la méthode ET les en-têtes
    RÉELLEMENT construits — c'est là que sont les fautes qu'on craint
    (un dépôt mal découpé, un `Accept` oublié), et une rustine sur le
    module les laisserait passer.

    Rend True si GitHub a accepté (HTTP 2xx), False sinon. ⓘ Ne LÈVE
    jamais : l'appelant décide si un dispatch refusé est fatal. Le
    poller continue de guetter ; le filet, lui, sort en erreur.
    """
    jeton = os.environ.get("GITHUB_DISPATCH_TOKEN")
    if not jeton:
        crier("  ⚠️ GITHUB_DISPATCH_TOKEN absent — aucun déclenchement "
              "(le run a bien été daté, mais rien n'a été lancé)")
        return False
    url = (f"https://api.github.com/repos/{depot}/actions/workflows/"
           f"{workflow}/dispatches")
    corps = json.dumps({"ref": ref, "inputs": entrees or {}}).encode()
    req = urllib.request.Request(url, data=corps, method="POST", headers={
        "Authorization": f"Bearer {jeton}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json"})
    ouvrir = ouvrir or urllib.request.urlopen
    try:
        with ouvrir(req, timeout=TIMEOUT_S) as r:
            crier(f"  ▶ workflow {workflow} déclenché (HTTP {r.status})")
            return True
    except urllib.error.HTTPError as e:
        crier(f"  ❌ dispatch refusé : HTTP {e.code} "
              f"{e.read()[:200].decode('utf-8', 'replace')}")
        return False
    # ⛔ AJOUTÉ AU LOT LW, ET C'EST UNE VRAIE PANNE VUE : `URLError` (DNS
    # muet, réseau coupé, TLS) n'est PAS une `HTTPError` et remontait
    # donc en exception nue jusqu'à l'appelant. Chez le poller, qui
    # tourne en boucle, elle tuait le service ; ici elle aurait fait
    # sortir le filet sur une trace Python au lieu du message qui dit
    # quoi faire. Les deux appelants veulent la MÊME chose : un False.
    except urllib.error.URLError as e:
        crier(f"  ❌ dispatch impossible — réseau ou DNS : {e.reason}")
        return False


def cible(chaine):
    """Découpe `depot/nom:workflow.yml` en `(depot, workflow)`.

    ⚠️ LE SÉPARATEUR EST LE DERNIER `:`, pas le premier. Le nom de dépôt
    en contient rarement, mais `rsplit` coûte le même prix que `split`
    et retire la question. ⓘ Format repris tel quel d'`AGRUME_DISPATCH`
    (`run-poller.sh` l. 41) : deux variables d'environnement qui ont la
    même forme se relisent sans y penser.

    Lève `ValueError` sur une chaîne mal formée — et c'est délibéré :
    une cible illisible doit arrêter le job au démarrage, pas produire
    un POST vers une URL inventée qui rendrait 404 et ressemblerait à un
    problème de droits.
    """
    if not chaine or ":" not in chaine:
        raise ValueError(
            f"cible de dispatch illisible : {chaine!r} — attendu "
            "« proprietaire/depot:workflow.yml »")
    depot, workflow = chaine.rsplit(":", 1)
    if not depot or not workflow or "/" not in depot:
        raise ValueError(
            f"cible de dispatch illisible : {chaine!r} — attendu "
            "« proprietaire/depot:workflow.yml »")
    return depot, workflow
