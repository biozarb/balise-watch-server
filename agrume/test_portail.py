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



def _grib(charge=b"", annoncee=None):
    """Un GRIB2 de banc, avec une section 0 HONNÊTE.

    ⚠️ L'ancien faux (`b"GRIB" + b"\\x00" * 300 + b"7777"`) annonçait une
    longueur de ZÉRO, et le banc l'acceptait — parce que personne ne
    lisait la section 0. Depuis le 23/09 c'est elle qui garde : un
    fixture qui ment sur sa longueur doit être REFUSÉ, et l'était.
    """
    corps = b"GRIB" + b"\xff\xff" + b"\x00" + b"\x02" + b"\x00" * 8 + charge + b"7777"
    n = (annoncee if annoncee is not None else len(corps)).to_bytes(8, "big")
    return corps[:8] + n + corps[16:]


VRAI_GRIB = _grib(b"\x00" * 300)
GRIB_TRONQUE = _grib(b"\x00" * 300)[:-4]        # coupé avant le 7777

# ⛔⛔ LES 203 OCTETS, TELS QUE MÉTÉO-FRANCE LES A SERVIS (23/09/2026).
#
# Capturés sur le VPS en rejouant la passe `2026-09-23T05:30:00Z` (rang
# 16 sur 39, échéance 75-80 min) — celle qui a tué le service à 07:40
# CEST, après 55 échecs d'affilée la veille au soir. Passés à eccodes
# dans la foulée :
#
#     shortName = tp · Ni = 1472 · Nj = 912
#     numberOfDataPoints = 1 342 464   ⟵ la grille ENTIÈRE
#     packingType = grid_simple · bitsPerValue = 0
#     valeurs : 1 342 464 points, min 0.0, max 0.0, aucun NaN
#
# C'est un champ CONSTANT — il ne pleut nulle part à cette échéance —
# et un champ constant ne coûte aucun bit par point. 203 octets est
# donc la taille NORMALE de « pas de pluie », pas celle d'une panne.
# L'ancien plancher de 256 le refusait, et une seule tranche comme
# celle-ci suffisait à perdre la passe entière.
#
# ⚠️ Ces octets sont le banc. Les régénérer « proprement » à la main
# ferait perdre ce qu'ils prouvent : que la VRAIE donnée passe.
VRAI_GRIB_203 = bytes.fromhex(
    "47524942ffff000200000000000000cb0000001501005400"
    "0005000107ea0917051e00000100000048030000147c0000"
    "00000006ffffffffffffffffffffffffffffff000005c000"
    "00039000000000ffffffff030be0701525aa70300280de80"
    "0090f5600000271000002710000000003a04000000080134"
    "020042000000000000004b01ffffffffffffffffffffff07"
    "ea0917063200010000000001020000000005ff0000000000"
    "0000150500147c0000000000000080100000000000000006"
    "06ff000000050737373737")

# Le même, coupé net par une passerelle qui lâche : la section 0
# annonce toujours 203, le corps n'en porte plus que 120.
GRIB_203_TRONQUE = VRAI_GRIB_203[:120]


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

    # ⚠️ LE MOTIF A CHANGÉ LE 23/09, ET C'EST UN PROGRÈS. Un message
    # coupé est désormais pris par la LONGUEUR ANNONCÉE, avant même
    # qu'on regarde sa fin — un diagnostic plus tôt et plus précis.
    raison = portail.corps_grib_invalide(GRIB_TRONQUE)
    verifier(raison is not None and "TRONQU" in raison,
             f"un GRIB coupé est REFUSÉ, par sa longueur annoncée "
             f"({raison!r})")
    # … et la fin manquante reste gardée POUR ELLE-MÊME : ici la
    # longueur est cohérente, seul le « 7777 » a été remplacé.
    raison = portail.corps_grib_invalide(VRAI_GRIB[:-4] + b"XXXX")
    verifier(raison is not None and "7777" in raison,
             f"un GRIB de longueur cohérente mais sans « 7777 » final "
             f"est REFUSÉ ({raison!r})")

    verifier(portail.corps_grib_invalide(b"") is not None,
             "un corps vide reste refusé (le cas d'origine)")
    verifier(portail.corps_grib_invalide(b"GRIB7777") is not None,
             "trop court pour porter une section 0 : refusé même avec "
             "les deux magies")

    # ══════════════════════════════════════════════════════════════════
    #  ⛔⛔ LA PANNE DU 23/09 — 203 OCTETS DE VRAIE DONNÉE, REFUSÉS
    # ══════════════════════════════════════════════════════════════════
    print("\n1 bis. les 203 octets de Météo-France (23/09)")
    verifier(len(VRAI_GRIB_203) == 203,
             "le corps capturé fait bien 203 octets")
    verifier(int.from_bytes(VRAI_GRIB_203[8:16], "big") == 203,
             "sa section 0 annonce 203 — la longueur est COHÉRENTE, "
             "c'est un message complet")
    verifier(VRAI_GRIB_203.startswith(b"GRIB")
             and VRAI_GRIB_203.endswith(b"7777"),
             "il commence par « GRIB » et finit par « 7777 »")
    verifier(len(VRAI_GRIB_203) < 256,
             "⛔ il est SOUS l'ancien plancher de 256 o — c'est la panne, "
             "en une ligne")
    verifier(portail.corps_grib_invalide(VRAI_GRIB_203) is None,
             "⭐ ET IL EST ACCEPTÉ : un champ constant (bitsPerValue = 0, "
             "aucune pluie) n'est pas une panne")

    # ⭐ Le garde qui remplace le plancher : la longueur ANNONCÉE.
    raison = portail.corps_grib_invalide(GRIB_203_TRONQUE)
    verifier(raison is not None and "TRONQU" in raison,
             f"⭐ le MÊME message coupé à 120 o est refusé — la section 0 "
             f"annonce toujours 203 ({raison!r})")

    # ⛔ Et le plancher ne doit plus servir de garde à personne : un
    # message qui ment sur sa longueur passe la taille et échoue ici.
    verifier(portail.corps_grib_invalide(_grib(b"\x00" * 300, annoncee=0))
             is not None,
             "une section 0 qui annonce 0 est refusée")
    verifier(portail.corps_grib_invalide(
                 _grib(b"\x00" * 300, annoncee=99999)) is not None,
             "une section 0 qui annonce PLUS que le corps est refusée")
    verifier(portail.corps_grib_invalide(VRAI_GRIB + b"   ") is None,
             "un blanc de fin reste toléré (cas vu le 27/08)")
    verifier(portail.corps_grib_invalide(VRAI_GRIB + VRAI_GRIB) is None,
             "deux messages concaténés restent tolérés (annonce < taille)")


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
