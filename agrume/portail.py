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
SERVICE_PIAF = "piaf"

# ── Piège nº 5 : l'URL des capabilities ment sur le chemin ────────────
# Le `xlink:href` déclaré dans le GetCapabilities OMET le `/1.0/` du
# chemin réel. Les deux formes fonctionnent, mais un client qui suit
# aveuglément le lien ne s'en rend pas compte — et ne le découvre que le
# jour où l'une des deux cesse de répondre. On écrit le chemin réel.
#
# ── ⛔ Piège nº 7 : IL Y A DEUX CIRCUITS, ET PAS SEULEMENT DEUX ────────
#    PRÉFIXES (20/08/2026, Lot Q2)
#
# La prévision immédiate agrégée n'est PAS servie par `public-api`. Elle
# vit sur un AUTRE HOTE et sous un AUTRE préfixe :
#
#     AROME / AROME-PI  https://public-api.meteofrance.fr/public/…
#     immédiate (piaf)  https://api.meteofrance.fr/pro/…
#
# ⚠️ Sept chemins ont rendu HTTP 404 avant que ce fait ne soit établi, et
# ils ressemblaient tous à « la clé n'est pas abonnée » — parce que le
# piège nº 2 fait arriver à peu près tout en 404. La clé, elle, était
# abonnée depuis le début. **Un 404 sur ce portail ne dit jamais
# pourquoi ; seul le corps le dit, et parfois il ne le dit pas non plus.**
BASES = {
    "public": ("https://public-api.meteofrance.fr/public/{service}"
               "/1.0/wcs/{couverture}"),
    "pro": "https://api.meteofrance.fr/pro/{service}/1.0/wcs/{couverture}",
}
#: Rétrocompatibilité : `BASE` désignait le circuit public, et il n'y en
#: avait qu'un. Le nom reste pour ne pas casser un appel existant.
BASE = BASES["public"]

CIRCUITS = {SERVICE_AROME: "public", SERVICE_AROMEPI: "public",
            SERVICE_PIAF: "pro"}

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
    # ⛔ La prévision immédiate agrégée, en 0,01°. ⚠️ Le service publie
    # AUSSI un WMS (`GetMap`), et on ne s'en sert PAS : il rendrait des
    # images toutes faites, mais la clé devrait alors voyager jusqu'au
    # navigateur. Il faudrait un proxy — c'est-à-dire exactement le rendu
    # d'image côté serveur que l'arbitrage A16 a écarté.
    (SERVICE_PIAF, "001"): "MF-NWP-HIGHRES-PIAF-001-FRANCE-WCS",
}

# ── Piège nº 4 : le nom du format ─────────────────────────────────────
# `application/wmo-grib2` rend un HTTP 400. Le SEUL nom accepté est
# `application/wmo-grib` (l'autre format offert étant `image/tiff`).
FORMAT_GRIB = "application/wmo-grib"

# ── Le nom de l'axe vertical : LU, jamais supposé ─────────────────────
# ✅ Mesuré le 10/08 sur `aromepi/0025` : les axes déclarés par le
# `DescribeCoverage` sont `height`, `lat`, `long`, `time`.
# ⚠️ Cette liste sert à RECONNAÎTRE l'axe dans ce qui est déclaré, pas à
# en choisir un par défaut : `axe_vertical()` lève si aucun ne
# correspond, parce qu'une mauvaise étiquette d'axe rend un HTTP 404
# impossible à distinguer d'un run non publié (piège nº 2).
AXES_VERTICAUX_CONNUS = ("height", "z", "elevation", "vertical", "depth")

# Plancher de plausibilité d'un GRIB2. ⚠️ Il ne protège pas d'un GRIB
# corrompu — il protège du cas VRAIMENT vicieux : HTTP 200, corps vide
# ou tronqué. Le champ deviendrait alors une nappe de NaN, indiscernable
# d'un trou légitime. L'en-tête GRIB2 seul fait déjà 16 octets, et le
# plus petit champ réel mesuré sur ce domaine en fait 7 957.
MIN_OCTETS_GRIB = 256

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
        # ⚠️ Le circuit se LIT dans `CIRCUITS`, il ne se devine pas au nom
        # du service : `piaf` vit sur un autre hôte (piège nº 7). Un
        # service inconnu de la table est un service dont on ignore le
        # circuit — on refuse plutôt que de replier sur « public », ce
        # qui rendrait sept 404 indiscernables d'un défaut d'abonnement.
        if service not in CIRCUITS:
            raise ErreurPortail(
                f"service {service!r} sans circuit déclaré — connus : "
                f"{sorted(CIRCUITS)}. ⚠️ NE PAS replier sur `public` : le "
                f"portail rend HTTP 404 pour un mauvais hôte comme pour "
                f"un run absent.")
        self.circuit = CIRCUITS[service]
        self.base = BASES[self.circuit].format(
            service=service, couverture=COUVERTURES[(service, grille)])
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
        # Nom de l'axe vertical par champ, lu une fois (cf.
        # `axe_vertical`). C'est une propriété du service, pas du run.
        self._axes: dict[str, str] = {}

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

                # ⚠️⚠️ 502 / 503 / 504 — MESURÉ LE 10/08, ET ÇA COÛTAIT DES
                # TROUS DÉFINITIFS. Le premier run d'ingestion PI écrit sur
                # R2 a rendu **297 champs sur 300** : trois `HTTP 502 Bad
                # Gateway`, à trois niveaux et trois échéances sans rapport
                # entre eux (v/50 m/360 min, v/100 m/240 min,
                # v/250 m/225 min). Deux portaient un corps `mw:fault` du
                # framework MetWork, un portait la page nginx nue.
                #
                # Ce sont des incidents de PASSERELLE, de la même famille
                # que le 500 SUSPENDED — le portail est là, son
                # intermédiaire hoquette. Le module savait déjà que « à
                # forte concurrence, le portail COUPE LA CONNEXION (102
                # ConnectionResetError et UN 502 sur 200 requêtes) » : le
                # 502 était donc DÉJÀ observé, et traité comme définitif.
                #
                # ⛔ Or les colonnes PI sont DÉFINITIVES. Un 502 non
                # retenté, c'est un trou permanent dans une archive qu'on
                # ne peut pas reconstituer — la rétention du portail est de
                # 4,25 jours.
                if e.code in (502, 503, 504):
                    self.compteur[f"http_{e.code}_retente"] += 1
                    self._crier(f"    {e.code} (passerelle) — on retente "
                                f"[essai {essai + 1}/{essais}]")
                    time.sleep(1.5 * (essai + 1))
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
    def id_couverture(champ, run_iso, agregation=None):
        """`{CHAMP}___{run}` où le run porte des POINTS et non des
        deux-points : `2026-08-10T08.00.00Z`. C'est la forme relevée dans
        le GetCapabilities, et le portail ne reconnaît qu'elle.

        ⚠️⚠️ ET LA PRÉVISION IMMÉDIATE Y AJOUTE UN SUFFIXE, AVEC UN SEUL
        SOULIGNÉ (20/08). Relevé dans son GetCapabilities :

            TOTAL_PRECIPITATION_RATE__GROUND_OR_WATER_SURFACE___2026-08-20T07.35.00Z_PT5M
                                                              ^^^            ^
                                                          trois            UN

        Le séparateur du run est `___`, celui de l'agrégation `_`. Écrire
        `___PT5M` par symétrie rend un `NoSuchCoverage` — c'est-à-dire
        exactement ce que rend un run non publié (cf. `CouvertureAbsente`),
        donc un poller lancé là-dessus attendrait pour toujours.

        ⓘ Cinq agrégations sont publiées pour chaque passe : `PT5M`,
        `PT15M`, `PT30M`, `PT1H`, `PT3H`.
        """
        cid = f"{champ}___{run_iso.replace(':', '.')}"
        return f"{cid}_{agregation}" if agregation else cid

    def describe(self, champ, run_iso, timeout=30, agregation=None):
        """`DescribeCoverage` — LA primitive de détection de run.

        ✅ Mesuré le 10/08 : 5 687 octets en 0,12 s quand le run est en
        ligne, 593 octets en 0,10 s quand il ne l'est pas. À comparer aux
        **3,27 Mo** d'un `GetCapabilities` (10 288 identifiants, 105 runs,
        52 familles) : un facteur ~575. Poller par GetCapabilities toutes
        les 2 minutes coûterait 2,3 Go par jour pour une information qui
        tient dans 600 octets.

        Renvoie l'arbre XML parsé, ou lève `CouvertureAbsente`.
        """
        cid = self.id_couverture(champ, run_iso, agregation)
        url = (f"{self.base}/DescribeCoverage?service=WCS&version=2.0.1"
               f"&coverageid={urllib.parse.quote(cid)}")
        return ET.fromstring(self._http(url, timeout=timeout))

    def existe(self, champ, run_iso, agregation=None):
        """Le run est-il publié pour ce champ ? True / False.

        ⚠️ Un False ici ne prouve PAS que le run n'est pas publié : il
        peut aussi vouloir dire que `champ` est mal écrit (le portail
        rend le même `NoSuchCoverage` dans les deux cas). Toujours
        appeler `valider_champ()` d'abord.
        """
        try:
            self.describe(champ, run_iso, agregation=agregation)
            return True
        except CouvertureAbsente:
            return False

    def valider_champ(self, champ, runs_temoins, agregation=None):
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
                self.describe(champ, r, agregation=agregation)
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

    # ── GetCoverage — la primitive qui rapporte de la DONNÉE ──────────
    def axe_vertical(self, champ, run_iso):
        """Le nom de l'axe vertical, **LU** dans le `DescribeCoverage`.

        ⚠️ ON NE LE DEVINE PAS. Le WCS 2.0.1 laisse le serveur nommer ses
        axes comme il veut, et se tromper de nom ne rend pas une erreur
        franche : le portail répond en **HTTP 404** (piège nº 2),
        c'est-à-dire exactement ce que rend un run absent. Un client qui
        supposerait `z` attendrait donc la publication d'un run déjà
        publié, pour toujours.

        ✅ Mesuré le 10/08 sur `aromepi/0025` : `height`, `lat`, `long`,
        `time`. ⓘ Noter au passage que la longitude s'appelle **`long`**
        et non `lon` — `subset_boite()` le sait déjà.

        Le résultat est mémorisé : une requête de plus par champ serait
        payée sur le quota pour une propriété qui ne change pas.
        """
        if champ in self._axes:
            return self._axes[champ]
        arbre = self.describe(champ, run_iso)
        vus = set()
        for el in arbre.iter():
            for cle in ("axisLabels", "axisLabel"):
                if cle in el.attrib:
                    vus.update(el.attrib[cle].split())
            if el.tag.endswith("axisLabels"):
                vus.update((el.text or "").split())
        axe = next((a for a in sorted(vus)
                    if a.lower() in AXES_VERTICAUX_CONNUS), None)
        if axe is None:
            raise ErreurPortail(
                f"aucun axe vertical reconnu dans le DescribeCoverage de "
                f"{champ!r} — axes déclarés : {sorted(vus) or 'aucun'}. "
                f"⚠️ Ne PAS replier sur une valeur par défaut : une "
                f"mauvaise étiquette d'axe rend un HTTP 404 impossible à "
                f"distinguer d'un run non publié.")
        self._axes[champ] = axe
        return axe

    def get_coverage(self, champ, run_iso, instant_iso, niveau, domaine,
                     axe=None, timeout=60, agregation=None):
        """Un champ 2D en GRIB2 : UN paramètre × UN niveau × UNE échéance
        × UNE boîte. Renvoie les octets bruts — le décodage appartient à
        l'appelant, pour que ce module reste sans dépendance lourde.

        ⛔ **Le grain n'est pas un choix de ce code, c'est le serveur.**
        Toute tentative de groupement est refusée :

            Slicing on height is mandatory : only a 2D coverage can be downloaded
            Slicing on time   is mandatory : only a 2D coverage can be downloaded

        D'où un compte de requêtes non négociable : **6 niveaux ×
        2 paramètres × 25 échéances = 300 requêtes par run de PI.**
        Toutes les variantes d'intervalle ont été essayées le 10/08, sur
        AROME comme sur AROME-PI, et rejetées.

        ⚠️ Piège nº 4 : le format s'écrit `application/wmo-grib`.
        `application/wmo-grib2` rend un HTTP 400 — et le « 2 » est
        exactement ce qu'on ajoute d'instinct, puisque le fichier reçu
        EST du GRIB2.

        ⓘ Mesuré le 10/08 : 7 957 octets par champ en 0,025° sur la
        boîte Nord-Alpes, **constant quel que soit le niveau**, et
        0,180 s par requête hors attente de quota.

        ⚠️ 19/08 — CE CHIFFRE A VIEILLI, ET PAS PARCE QUE LE PORTAIL A
        CHANGÉ : la boîte Nord-Alpes a doublé le 16/08 (5 185 → 11 655
        colonnes). Remesuré le même jour, à la même heure, sur le même
        service : **17 662 octets** pour Nord-Alpes, 12 787 pour les
        Pyrénées, 4 288 pour Tarn/Aveyron/Hérault, et **92 356 pour leur
        boîte englobante** — celle que `ingest_pi.py` demande depuis le
        Lot M. Le poids suit la SURFACE, il ne suit ni le niveau ni
        l'échéance, et c'est ce qui rend l'englobante payable.
        """
        # ⛔ `niveau=None` — LE CHAMP DE SURFACE, ET IL N'A PAS D'AXE
        # VERTICAL DU TOUT (20/08, Lot Q2). Mesuré sur le DescribeCoverage
        # de la prévision immédiate : `axisLabels="long lat time"`, trois
        # axes, pas quatre. Demander `height(…)` sur un champ qui n'a pas
        # cet axe est refusé — et le refus arrive en 404, indiscernable
        # d'un run absent. Appeler `axe_vertical()` ici lèverait d'ailleurs
        # tout seul (« aucun axe vertical reconnu »), ce qui est le bon
        # comportement pour AROME et le mauvais diagnostic pour celui-ci.
        #
        # ⚠️ `None` et `0` ne sont PAS la même chose : `subset_niveau(axe,
        # 0)` écrirait `height(0)`, une requête syntaxiquement valide sur
        # un axe inexistant. C'est pourquoi le test est `is None`.
        surface = niveau is None
        if not surface:
            axe = axe or self.axe_vertical(champ, run_iso)
        cid = self.id_couverture(champ, run_iso, agregation)
        boite = subset_boite(domaine["latmin"], domaine["latmax"],
                             domaine["lonmin"], domaine["lonmax"])
        url = (f"{self.base}/GetCoverage?service=WCS&version=2.0.1"
               f"&coverageid={urllib.parse.quote(cid)}"
               f"&subset={subset_temps(instant_iso)}"
               + ("" if surface else f"&subset={subset_niveau(axe, niveau)}")
               + f"&subset={boite}"
               f"&format={FORMAT_GRIB}")
        octets = self._http(url, timeout=timeout)
        self.compteur["octets"] += len(octets)
        # ⚠️ Un corps vide n'est PAS une erreur HTTP : le portail a
        # répondu 200. Sans ce contrôle, il traverserait le décodeur et
        # deviendrait une nappe de NaN — c'est-à-dire un trou qui
        # ressemble à une donnée manquante légitime, et qui se
        # propagerait jusque dans le delta du composite.
        if len(octets) < MIN_OCTETS_GRIB:
            raise ErreurPortail(
                f"GetCoverage a rendu {len(octets)} octets pour {champ} au "
                f"niveau {niveau} à {instant_iso} — trop court pour un "
                f"GRIB2. ⚠️ Le portail a pourtant répondu HTTP 200.")
        return octets

    def bilan(self):
        c = self.compteur
        return (f"{self.service}/{self.grille} : {c['requetes']} requêtes"
                + (f", {c['http_429']} × 429" if c["http_429"] else "")
                + (f", {c['500_suspended']} × 500 SUSPENDED"
                   if c["500_suspended"] else "")
                + (f", {c['reseau']} incidents réseau" if c["reseau"] else "")
                + "".join(f", {c[f'http_{k}_retente']} × {k} retentés"
                          for k in (502, 503, 504) if c[f"http_{k}_retente"])
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


def subset_niveau(axe, niveau):
    """⚠️ Le niveau est un ENTIER sans unité, et l'axe porte le nom que
    le serveur lui donne (`axe_vertical()`). Écrire `height(100 m)` ou
    `height(100.0)` n'a pas été essayé et n'a pas à l'être : la forme
    ci-dessous est celle qui a rendu 150 champs sans un refus."""
    return f"{axe}({int(niveau)})"


def subset_boite(latmin, latmax, lonmin, lonmax):
    """Sous-domaine géographique — ✅ le seul levier du portail qui marche
    vraiment, et il est spectaculaire : 1 099 000 octets pour la France
    entière contre **7 957 octets** pour le Nord-Alpes en 0,025°, soit un
    facteur 138. Et le poids est CONSTANT quel que soit le niveau
    (vérifié à 10, 500, 1500 et 3000 m)."""
    return f"lat({latmin},{latmax})&subset=long({lonmin},{lonmax})"
