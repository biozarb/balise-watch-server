#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/test_portail.py — le banc de la passerelle       (27/08/2026)
#
#  ⛔ Écrit APRÈS coup, sur une panne réelle : nuit du 26 au 27/08, la
#  passerelle Météo-France sature (`mw:code` 868502, « Can't start new
#  thread ») et TROIS passes de la pluie à venir meurent sur
#  `gribapi.errors.KeyValueNotFoundError: Key/value not found`.
#
#  Ce module n'avait aucun banc. Il en a un, et il rejoue exactement ce
#  chemin-là — les deux façons qu'avait le portail de mentir sans qu'une
#  seule requête n'échoue :
#
#   1. RENDRE SA PAGE D'ERREUR EN HTTP 200. Le plancher de 256 octets ne
#      voyait que le corps VIDE ; le corps FAUX fait 416 octets et
#      passait. `ec.codes_new_from_message()` en fait un handle valide
#      (vérifié sur le VPS le 27/08) et la panne n'apparaît que dix
#      lignes plus loin, sans nommer ni le champ ni l'échéance.
#   2. ÉPUISER QUATRE ESSAIS EN QUINZE SECONDES, sur une saturation qui
#      dure des minutes.
#
#  ⚠️ Sans réseau, sans clé, sans R2. `urlopen` et `sleep` sont
#  remplacés ; le banc ne dort jamais.
#      python3 agrume/test_portail.py
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys
import urllib.error

os.environ.setdefault("METEOFRANCE_API_KEY", "cle-bidon-de-banc")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import portail  # noqa: E402

ECHECS = []


def verifier(condition, quoi):
    if condition:
        print(f"  ✅ {quoi}")
    else:
        print(f"  ❌ {quoi}")
        ECHECS.append(quoi)


# ── Les corps, tels que le portail les a vraiment servis ──────────────
# ⚠️ Recopié du journal du VPS, nuit du 26 au 27/08 (à la troncature du
# journal près). Il fait 416 octets une fois rembourré comme il l'était :
# AU-DESSUS du plancher de 256. C'est tout le piège.
FAUX_200 = (
    b'<?xml version="1.0" encoding="UTF-8"?><mw:fault xmlns:mw='
    b'"http://metwork-framework.org/"><mw:code>868502</mw:code>'
    b'<mw:message>Bad Gateway</mw:message><mw:description>'
    b"Can't start new thread</mw:description></mw:fault>"
) + b" " * 200

VRAI_GRIB = b"GRIB" + b"\x00" * 300 + b"7777"
GRIB_TRONQUE = b"GRIB" + b"\x00" * 300          # coupé avant le 7777


# ══════════════════════════════════════════════════════════════════════
#  1. LE CORPS FAUX SE RECONNAÎT — ET LE PLANCHER SEUL NE SUFFISAIT PAS
# ══════════════════════════════════════════════════════════════════════
def test_reconnaissance_du_corps():
    print("\n1. corps_grib_invalide")

    # ⛔ LE POINT CENTRAL DU BANC. Si cette ligne devenait fausse, tout
    # le reste serait vrai POUR LA MAUVAISE RAISON : le corps d'erreur
    # serait rejeté par la longueur, et on ne saurait pas si la magie
    # GRIB sert à quelque chose. Elle documente la panne.
    verifier(len(FAUX_200) > portail.MIN_OCTETS_GRIB,
             f"le corps d'erreur ({len(FAUX_200)} o) PASSE le plancher de "
             f"{portail.MIN_OCTETS_GRIB} o — c'est pourquoi il faut la magie")

    verifier(portail.corps_grib_invalide(VRAI_GRIB) is None,
             "un GRIB2 plausible est accepté")

    raison = portail.corps_grib_invalide(FAUX_200)
    verifier(raison is not None and "GRIB" in raison,
             f"le corps d'erreur en 200 est REFUSÉ ({raison!r})")

    raison = portail.corps_grib_invalide(GRIB_TRONQUE)
    verifier(raison is not None and "7777" in raison,
             "un GRIB tronqué (sans 7777 final) est REFUSÉ")

    verifier(portail.corps_grib_invalide(b"") is not None,
             "un corps vide reste refusé (le cas d'origine)")
    verifier(portail.corps_grib_invalide(b"GRIB7777") is not None,
             "trop court reste refusé même avec les deux magies")


# ══════════════════════════════════════════════════════════════════════
#  2. LE REPLI — les valeurs EN TOUTES LETTRES
# ══════════════════════════════════════════════════════════════════════
def test_repli():
    print("\n2. repli")
    # ⚠️ Écrites en dur et pas dérivées de `REPLI_PASSERELLE` : un banc
    # qui compare le code à sa propre constante bouge avec elle et ne
    # vérifie rien (BUGS.md, 26/08, piège nº 3).
    attendu = [1.5, 5.0, 15.0, 30.0]
    obtenu = [portail.repli(n) for n in range(4)]
    verifier(obtenu == attendu, f"les quatre paliers valent {attendu}")
    verifier(sum(obtenu) > 45.0,
             f"la patience totale dépasse 45 s ({sum(obtenu):.1f} s) — "
             f"les 15 s d'avant ont perdu six passes en une nuit")
    verifier(obtenu[0] <= 2.0,
             "le PREMIER essai reste rapide : la plupart des 502 passent là")
    verifier(portail.repli(99) == attendu[-1],
             "au-delà du dernier palier, on plafonne au lieu de lever")


# ══════════════════════════════════════════════════════════════════════
#  3. LA BOUCLE — un corps faux est RETENTÉ, pas levé
# ══════════════════════════════════════════════════════════════════════
class FausseReponse:
    def __init__(self, octets):
        self.octets = octets

    def read(self):
        return self.octets

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def brancher(reponses, dodos):
    """Remplace `urlopen` par une file de réponses, et `sleep` par un
    carnet. ⚠️ Le banc ne dort JAMAIS : sans ça, le seul scénario
    « quatre essais épuisés » coûterait 51,5 s de CI."""
    file = list(reponses)

    def faux_urlopen(req, timeout=None):
        r = file.pop(0)
        if isinstance(r, Exception):
            raise r
        return FausseReponse(r)

    portail.urllib.request.urlopen = faux_urlopen
    portail.time.sleep = dodos.append


def http_502(corps=FAUX_200):
    return urllib.error.HTTPError("http://x", 502, "Bad Gateway", {},
                                  __import__("io").BytesIO(corps))


def test_boucle():
    print("\n3. _http")
    vrai_urlopen = portail.urllib.request.urlopen
    vrai_sleep = portail.time.sleep
    try:
        # ── a. deux corps faux en 200, puis la donnée ────────────────
        dodos = []
        brancher([FAUX_200, FAUX_200, VRAI_GRIB], dodos)
        p = portail.Portail("piaf", "001", journal=None)
        octets = p._http("http://x", valider=portail.corps_grib_invalide)
        verifier(octets == VRAI_GRIB,
                 "deux corps faux en 200 sont retentés, la donnée finit "
                 "par passer")
        verifier(p.compteur["corps_invalide"] == 2,
                 "les deux corps faux sont COMPTÉS (ils n'ont aucun code "
                 "HTTP d'erreur pour les trahir)")
        verifier(dodos == [1.5, 5.0],
                 f"et l'attente a suivi les paliers ({dodos})")

        # ── b. sans validateur, un corps XML passe ───────────────────
        # ⚠️ `describe()` appelle le MÊME `_http` et attend du XML. Un
        # contrôle GRIB appliqué à tout le monde casserait le poller.
        dodos = []
        brancher([FAUX_200], dodos)
        p = portail.Portail("piaf", "001", journal=None)
        verifier(p._http("http://x") == FAUX_200,
                 "sans validateur, le corps traverse — `describe()` lit "
                 "du XML par ce même chemin")

        # ── c. quatre essais épuisés : on lève, en NOMMANT la cause ──
        dodos = []
        brancher([FAUX_200] * 4, dodos)
        p = portail.Portail("piaf", "001", journal=None)
        try:
            p._http("http://x", valider=portail.corps_grib_invalide)
            verifier(False, "quatre corps faux d'affilée doivent lever")
        except portail.ErreurPortail as e:
            verifier("corps illisible" in str(e),
                     f"l'erreur finale NOMME la cause : {str(e)[:60]!r}")
            verifier(len(dodos) == 4,
                     "quatre essais, quatre attentes — aucun abandon "
                     "silencieux")

        # ── d. un 502 franc suit les mêmes paliers ───────────────────
        dodos = []
        brancher([http_502(), VRAI_GRIB], dodos)
        p = portail.Portail("piaf", "001", journal=None)
        verifier(p._http("http://x") == VRAI_GRIB and dodos == [1.5],
                 "un 502 franc est retenté au premier palier")
    finally:
        portail.urllib.request.urlopen = vrai_urlopen
        portail.time.sleep = vrai_sleep


if __name__ == "__main__":
    print("═" * 62)
    print("  BANC DE LA PASSERELLE — la nuit du 26 au 27/08, rejouée")
    print("═" * 62)
    test_reconnaissance_du_corps()
    test_repli()
    test_boucle()
    print("\n" + "═" * 62)
    if ECHECS:
        print(f"❌ {len(ECHECS)} vérification(s) en échec :")
        for e in ECHECS:
            print(f"   · {e}")
        sys.exit(1)
    print("✅ banc de la passerelle : tout passe")
