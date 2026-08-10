#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/portail.py — le WCS de Météo-France, avec ses six pièges
#                                                        (10/08/2026)
#
#  ⚠️ POURQUOI CE MODULE EXISTE PLUTÔT QU'UN `urlopen` À LA MAIN. Le
#  portail a SIX comportements non documentés, tous rencontrés en une
#  seule session de sondage, et chacun coûte au minimum une requête
#  perdue — au pire un poller qui attend indéfiniment un run déjà en
#  ligne. Ils sont traités ici, une fois, et commentés à l'endroit exact
#  où ils mordent.
#
#  ⚠️ LA CLÉ NE PASSE JAMAIS PAR LA CONVERSATION NI PAR UN HISTORIQUE DE
#  SHELL. Elle vit sur le VPS dans `~/.balise-watch-model-verif.env`
#  (mode 600), c'est un JWT de 5 222 caractères, et elle s'envoie en
#  en-tête `apikey:` — pas en paramètre d'URL, qui finirait dans les
#  journaux d'accès. Ce module la LIT depuis l'environnement et ne
#  l'imprime jamais, pas même tronquée.
#
#  ⚠️ CE MODULE NE SERT PAS À TÉLÉCHARGER LES VOLUMES. Une requête WCS =
#  UN paramètre × UN niveau × UNE échéance × UNE boîte. Aucun groupement
#  n'existe (§ « piège » nº 0 ci-dessous). Tirer HP1 sur 0–24 h par cette
#  route coûterait 1 250 requêtes et 12,5 min contre 4 requêtes et 2,9
#  min par le miroir S3. Le portail sert à DEUX choses, et deux
#  seulement :
#     • détecter la disponibilité d'un run (DescribeCoverage, 5,7 ko) ;
#     • atteindre AROME-PI, qui n'est PAS sur le miroir S3.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import collections
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# ── Piège nº 6 : le nom du service ────────────────────────────────────
# `aromepi` EN UN MOT. `arome-pi` avec un tiret rend un 404 — et comme le
# piège nº 2 fait arriver les vraies erreurs en 404 elles aussi, on peut
# y passer un moment.
SERVICE_AROME = "arome"
SERVICE_AROMEPI = "aromepi"

# ── Piège nº 5 : l'URL des capabilities ment sur le chemin ────────────
# Le `xlink:href` déclaré dans le GetCapabilities OMET le `/1.0/` du
# chemin réel. Les deux formes fonctionnent, mais un client qui suit
# aveuglément le lien ne s'en rend pas compte — et ne le découvre que le
# jour où l'une des deux cesse de répondre. On écrit le chemin réel.
BASE = "https://public-api.meteofrance.fr/public/{service}/1.0/wcs/{couverture}"

COUVERTURES = {
    (SERVICE_AROME, "0025"): "MF-NWP-HIGHRES-AROME-0025-FRANCE-WCS",
    (SERVICE_AROME, "001"): "MF-NWP-HIGHRES-AROME-001-FRANCE-WCS",
    (SERVICE_AROMEPI, "0025"): "MF-NWP-HIGHRES-AROMEPI-0025-FRANCE-WCS",
    # ⛔ AROME-PI en 0,01° existe mais est INUTILISABLE pour AGRUME :
    # c'est un produit de nowcasting du DANGER (rafales, grêle, CAPE,
    # visibilité). Mesuré le 10/08 par GetCapabilities :
    # `U_COMPONENT_OF_WIND`, `V_`, `WIND_SPEED` et `TKE` y sont TOUS
    # ABSENTS. Il n'y a pas de vent moyen. On ne le déclare donc pas.
    (SERVICE_AROMEPI, "001"): "MF-NWP-HIGHRES-AROMEPI-001-FRANCE-WCS",
}

# ── Piège nº 4 : le nom du format ─────────────────────────────────────
# `application/wmo-grib2` rend un HTTP 400. Le SEUL nom accepté est
# `application/wmo-grib` (l'autre format offert étant `image/tiff`).
FORMAT_GRIB = "application/wmo-grib"

# ── Le quota, MESURÉ et non lu ────────────────────────────────────────
# Rafale de 150 requêtes à 404 req/min → premier HTTP 429 à la requête
# 105. La limite annoncée de 100 req/min est donc réelle et elle mord.
# On se cale un cran en dessous : un 429 n'est pas une erreur qu'on
# encaisse, c'est une attente qu'on aurait pu éviter.
QUOTA_PAR_MIN = 100
MARGE_QUOTA = 5

# ✅ QUOTA COMMUN OU SÉPARÉ ? MESURÉ LE 10/08 — ILS SONT INDÉPENDANTS.
# C'était la dernière question ouverte du lot H, et elle a été tranchée
# par l'expérience directe plutôt que par la doc :
#
#     rafale AROME : 106 requêtes en 17,2 s = 370 req/min
#       200 = 102 · 429 = 4 · PREMIER 429 À LA REQUÊTE 103
#     immédiatement après, dans la même minute :
#       AROME    → 429   (toujours bridé)
#       AROME-PI → 200   (pas bridé du tout)
#
# ⚠️ n = 1, à un instant donné. Ce que ça montre est net — PI répondait
# pendant qu'AROME était coupé — mais une seule observation ne fait pas
# une garantie contractuelle. Le compteur reste basculable :
# `AGRUME_QUOTA_COMMUN=1` force un compteur unique pour les deux APIs.
#
# ⓘ Et le seuil se confirme : premier 429 à la requête 103 ici, à la 105
# lors du sondage du matin. La limite annoncée de 100 req/min est réelle.
#
# ⚠️ PIÈGE ANNEXE, MESURÉ LE MÊME JOUR : à FORTE CONCURRENCE (40 fils,
# 16 000 req/min), le portail ne répond pas 429 — il COUPE LA CONNEXION
# (102 `ConnectionResetError` et un 502 sur 200 requêtes). Un client qui
# traiterait un reset comme une panne réseau définitive se tromperait de
# diagnostic : c'est du bridage, pas une panne. D'où le retry sur erreur
# réseau plus bas, et d'où le fait qu'on n'envoie JAMAIS en parallèle.
POOL_COMMUN = os.environ.get("AGRUME_QUOTA_COMMUN") == "1"

_VERROU = threading.Lock()
_FENETRES: dict[str, collections.deque] = {}


class ErreurPortail(Exception):
    """Erreur du portail. `code` est le code HTTP, `exception_wcs` le
    `exceptionCode` OGC lu DANS LE CORPS — parce que le code HTTP seul ne
    dit rien d'utile ici (cf. piège nº 2)."""

    def __init__(self, message, code=None, exception_wcs=None, corps=""):
        super().__init__(message)
        self.code = code
        self.exception_wcs = exception_wcs
        self.corps = corps


class CouvertureAbsente(ErreurPortail):
    """`NoSuchCoverage` — la couverture demandée n'est pas servie.

    ⚠️ DANGER, ET C'EST MESURÉ : le portail rend EXACTEMENT la même
    exception pour « ce run n'est pas encore publié » et pour « ce nom de
    champ n'existe pas ». Vérifié le 10/08 : un run futur et un champ
    inventé donnent tous deux `HTTP 404` + `NoSuchCoverage`, au `locator`
    près. Un poller qui se contenterait de lire `NoSuchCoverage` comme
    « pas encore là » attendrait donc INDÉFINIMENT sur une faute de
    frappe dans le nom du champ, sans jamais rien signaler.

    C'est pourquoi `Portail.valider_champ()` existe, et pourquoi le
    poller l'appelle AVANT de commencer à attendre.
    """


def _fenetre(cle):
    with _VERROU:
        return _FENETRES.setdefault(cle, collections.deque())


class Portail:
    """Client WCS minimal, mais qui connaît les pièges.

    `journal` reçoit les messages ; passer `None` pour se taire.
    """

    def __init__(self, service, grille="0025", cle=None, journal=print,
                 quota_par_min=QUOTA_PAR_MIN):
        if (service, grille) not in COUVERTURES:
            raise ErreurPortail(
                f"couple service/grille inconnu : {service}/{grille} — "
                f"connus : {sorted(COUVERTURES)}")
        self.service, self.grille = service, grille
        self.base = BASE.format(service=service,
                                couverture=COUVERTURES[(service, grille)])
        self.cle = cle or os.environ.get("METEOFRANCE_API_KEY")
        if not self.cle:
            raise ErreurPortail(
                "METEOFRANCE_API_KEY absente. ⚠️ Elle vit sur le VPS dans "
                "~/.balise-watch-model-verif.env (mode 600) et ne doit pas "
                "en sortir : lancer les requêtes portail DEPUIS le VPS, "
                "jamais en rapatriant la clé.")
        self.journal = journal
        self.quota_par_min = quota_par_min
        self.pool = "commun" if POOL_COMMUN else service
        self.compteur = collections.Counter()

    # ── Quota ─────────────────────────────────────────────────────────
    def _attendre_son_tour(self):
        """Fenêtre glissante d'une minute. Bloque plutôt que de prendre un
        429 : le 429 est une attente déguisée, autant l'assumer."""
        seuil = self.quota_par_min - MARGE_QUOTA
        f = _fenetre(self.pool)
        while True:
            with _VERROU:
                t = time.monotonic()
                while f and t - f[0] > 60.0:
                    f.popleft()
                if len(f) < seuil:
                    f.append(t)
                    return
                dodo = 60.0 - (t - f[0]) + 0.05
            self.compteur["attente_quota"] += 1
            time.sleep(max(dodo, 0.05))

    # ── HTTP ──────────────────────────────────────────────────────────
    def _http(self, url, essais=4, timeout=60):
        """Renvoie le corps (octets). Lève `ErreurPortail`/`CouvertureAbsente`.

        Trois comportements du portail sont traités ici et nulle part
        ailleurs :

        ⚠️ Piège nº 1 — un HTTP 500 transitoire
        `{"code":"303001", … "[ State : SUSPENDED ]"}` arrive sans
        prévenir. **Le retry immédiat passe.** Un client qui traite le
        500 comme définitif s'arrête pour rien.

        ⚠️ Piège nº 2 — une erreur WCS LÉGITIME arrive en HTTP 404, avec
        le vrai message dans le corps (un `InvalidSubsetting` parfaitement
        explicite arrive en 404). **Ne jamais lire un 404 comme
        « coverage absent » sans ouvrir le corps.**

        ⚠️ Le 429 — c'est une attente, pas un échec. On respire et on
        reprend, en resserrant le compteur au passage.
        """
        dernier = None
        for essai in range(essais):
            self._attendre_son_tour()
            self.compteur["requetes"] += 1
            req = urllib.request.Request(
                url, headers={"apikey": self.cle,
                              "User-Agent": "balise-watch-agrume/1"})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return r.read()
            except urllib.error.HTTPError as e:
                corps = e.read()
                texte = corps.decode("utf-8", "replace")
                dernier = (e.code, texte)
                self.compteur[f"http_{e.code}"] += 1

                if e.code == 429:
                    self._crier(f"    429 (quota) — pause 20 s "
                                f"[essai {essai + 1}/{essais}]")
                    time.sleep(20)
                    continue

                if e.code == 500 and "SUSPENDED" in texte:
                    # Mesuré : le retry immédiat passe.
                    self.compteur["500_suspended"] += 1
                    self._crier(f"    500 [State : SUSPENDED] — on retente "
                                f"[essai {essai + 1}/{essais}]")
                    time.sleep(1.5 * (essai + 1))
                    continue

                exc, msg = _lire_exception_wcs(texte)
                if exc == "NoSuchCoverage":
                    raise CouvertureAbsente(
                        msg or "NoSuchCoverage", code=e.code,
                        exception_wcs=exc, corps=texte)
                raise ErreurPortail(
                    f"HTTP {e.code} · {exc or 'sans exceptionCode'} · "
                    f"{msg or texte[:200]}",
                    code=e.code, exception_wcs=exc, corps=texte)
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                dernier = (None, repr(e))
                self.compteur["reseau"] += 1
                self._crier(f"    réseau : {e!r} — on retente "
                            f"[essai {essai + 1}/{essais}]")
                time.sleep(1.5 * (essai + 1))
        code, texte = dernier if dernier else (None, "")
        raise ErreurPortail(f"échec après {essais} essais : {texte[:200]}",
                            code=code, corps=texte)

    def _crier(self, msg):
        if self.journal:
            self.journal(msg)

    # ── Couvertures ───────────────────────────────────────────────────
    @staticmethod
    def id_couverture(champ, run_iso):
        """`{CHAMP}___{run}` où le run porte des POINTS et non des
        deux-points : `2026-08-10T08.00.00Z`. C'est la forme relevée dans
        le GetCapabilities, et le portail ne reconnaît qu'elle."""
        return f"{champ}___{run_iso.replace(':', '.')}"

    def describe(self, champ, run_iso, timeout=30):
        """`DescribeCoverage` — LA primitive de détection de run.

        ✅ Mesuré le 10/08 : 5 687 octets en 0,12 s quand le run est en
        ligne, 593 octets en 0,10 s quand il ne l'est pas. À comparer aux
        **3,27 Mo** d'un `GetCapabilities` (10 288 identifiants, 105 runs,
        52 familles) : un facteur ~575. Poller par GetCapabilities toutes
        les 2 minutes coûterait 2,3 Go par jour pour une information qui
        tient dans 600 octets.

        Renvoie l'arbre XML parsé, ou lève `CouvertureAbsente`.
        """
        cid = self.id_couverture(champ, run_iso)
        url = (f"{self.base}/DescribeCoverage?service=WCS&version=2.0.1"
               f"&coverageid={urllib.parse.quote(cid)}")
        return ET.fromstring(self._http(url, timeout=timeout))

    def existe(self, champ, run_iso):
        """Le run est-il publié pour ce champ ? True / False.

        ⚠️ Un False ici ne prouve PAS que le run n'est pas publié : il
        peut aussi vouloir dire que `champ` est mal écrit (le portail
        rend le même `NoSuchCoverage` dans les deux cas). Toujours
        appeler `valider_champ()` d'abord.
        """
        try:
            self.describe(champ, run_iso)
            return True
        except CouvertureAbsente:
            return False

    def valider_champ(self, champ, runs_temoins):
        """⚠️ LE GARDE-FOU CONTRE L'ATTENTE INFINIE.

        Vérifie que `champ` répond sur AU MOINS UN des `runs_temoins`
        (des runs assez anciens pour être forcément publiés). Si aucun ne
        répond, ce n'est pas que les runs manquent — c'est que le NOM DU
        CHAMP est faux, et un poller lancé là-dessus attendrait pour
        toujours en croyant patienter.

        Renvoie le run témoin qui a répondu. Lève sinon.
        """
        for r in runs_temoins:
            try:
                self.describe(champ, r)
                return r
            except CouvertureAbsente:
                continue
        raise ErreurPortail(
            f"le champ {champ!r} ne répond sur AUCUN des {len(runs_temoins)} "
            f"runs témoins de {self.service}/{self.grille}. ⚠️ Ce n'est très "
            f"probablement pas un problème de publication mais un NOM DE "
            f"CHAMP FAUX : le portail rend le même `NoSuchCoverage` pour un "
            f"run absent et pour un champ inexistant. Vérifier le nom dans "
            f"le GetCapabilities avant de relancer.")

    def bilan(self):
        c = self.compteur
        return (f"{self.service}/{self.grille} : {c['requetes']} requêtes"
                + (f", {c['http_429']} × 429" if c["http_429"] else "")
                + (f", {c['500_suspended']} × 500 SUSPENDED"
                   if c["500_suspended"] else "")
                + (f", {c['reseau']} incidents réseau" if c["reseau"] else "")
                + (f", {c['attente_quota']} attentes de quota"
                   if c["attente_quota"] else ""))


# ══════════════════════════════════════════════════════════════════════
#  PARTIE PURE — testable sans réseau
# ══════════════════════════════════════════════════════════════════════
_RE_EXC = re.compile(r'exceptionCode="([^"]+)"')
_RE_LOC = re.compile(r'locator="([^"]+)"')
_RE_TXT = re.compile(r"<[^>]*ExceptionText[^>]*>([^<]*)<")


def _lire_exception_wcs(texte):
    """(exceptionCode, message) extraits d'un corps d'erreur du portail.

    ⚠️ Le corps est une poupée russe : une `mw:fault` du cadre applicatif
    qui EMBALLE un `ows:ExceptionReport` OGC. Le code HTTP vient de la
    couche externe (et vaut 404 pour à peu près tout), l'information
    utile est dans la couche interne. On lit donc l'intérieur, par
    expression régulière plutôt que par parseur XML : un corps d'erreur
    tronqué ou mal formé ne doit pas provoquer une SECONDE erreur.
    """
    exc = _RE_EXC.search(texte)
    loc = _RE_LOC.search(texte)
    txt = _RE_TXT.search(texte)
    message = (txt.group(1).strip() if txt and txt.group(1).strip()
               else (f"locator={loc.group(1)}" if loc else ""))
    return (exc.group(1) if exc else None), message


def subset_temps(instant_iso):
    """⚠️ Piège nº 3 : `subset=time("…")` AVEC guillemets est REJETÉ.
    Sans guillemets, ça passe — alors que la syntaxe WCS 2.0.1 les admet.
    Cette fonction existe pour que personne ne les remette."""
    return f"time({instant_iso})"


def subset_boite(latmin, latmax, lonmin, lonmax):
    """Sous-domaine géographique — ✅ le seul levier du portail qui marche
    vraiment, et il est spectaculaire : 1 099 000 octets pour la France
    entière contre **7 957 octets** pour le Nord-Alpes en 0,025°, soit un
    facteur 138. Et le poids est CONSTANT quel que soit le niveau
    (vérifié à 10, 500, 1500 et 3000 m)."""
    return f"lat({latmin},{latmax})&subset=long({lonmin},{lonmax})"
