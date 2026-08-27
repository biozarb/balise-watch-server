#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/rafraichissement.py — Lot L2 : le composite PI publié À PART
#                                                        (17/08/2026)
#
#  Ce module prend le composite temporel de `composite.py` — qui n'avait
#  jamais quitté la mémoire — et en fait DEUX OBJETS SERVIS, écrits par
#  le VPS à chaque ingestion PI, c'est-à-dire toutes les heures.
#
#  ── L'ARBITRAGE A10, ET IL EST DÉJÀ PAYÉ ─────────────────────────────
#  Décision de Yann, 17/08, chiffrage sous les yeux (cf. `pi.py`, section
#  « LE RAFRAÎCHISSEMENT ») : le composite n'entre PAS dans les tampons
#  du produit B. Trois mesures l'ont dicté — la cadence (8 runs/jour
#  contre 24), le cache (`e{step}.bin` est immuable PARCE QUE ses octets
#  ne changent jamais) et les octets (286 Mo à réécrire chaque heure en
#  place, contre 58,3 à part).
#
#  ⚠️ LE PRIX, PAYÉ SCIEMMENT : la clause « le client ne change pas de
#  route » de l'arbitrage A5 est TOMBÉE. Le client lira un second objet
#  et appliquera une règle de préséance — publiée dans les deux
#  manifestes, jamais devinée.
#
#  ── CE QUE CE FICHIER REFUSE DE FAIRE, ET POURQUOI ───────────────────
#  ⛔ Il ne touche NI au produit A, NI aux tampons du produit B. Le
#     produit A nourrit le scoring depuis le Lot I ; y injecter le
#     composite changerait le SENS de la série AGRUME en cours de route,
#     et les scores sont éternels (renoncement A2, 13/08).
#  ⛔ Il ne réécrit PAS `composer()`. C'est lui qui porte l'invariant
#     bancé (`composite == PI` aux niveaux communs tant que w = 1), et
#     une seconde implémentation de la même formule est le défaut que ce
#     projet a déjà payé deux fois (`gust-front.js`, `LEVELS`).
#  ⛔ Il ne recalcule AUCUN offset dans le produit B : il les lit dans
#     `service.tranches` du manifeste du run visé. Un run écrit par une
#     version antérieure se relit selon SON manifeste.
#
#  ── LES DEUX JUMEAUX ─────────────────────────────────────────────────
#      carte.bin      (échéance, tranche, niveau, lat, lon)   29,14 Mo
#      colonnes.bin   un enregistrement par colonne            29,14 Mo
#
#  ⛔⛔ ILS S'ÉCRIVENT ENSEMBLE OU PAS DU TOUT. `carte.bin` nourrit le
#  calque, `colonnes.bin` nourrit la coupe. Publier l'un sans l'autre
#  ferait dire deux choses différentes au même vent au même instant —
#  c'est exactement la divergence que le produit B a été redessiné pour
#  éliminer le 12/08. C'est `index["dernier"][domaine]` qui rend le
#  couple lisible, et il n'avance qu'après les TROIS écritures.
#
#  ⚠️⚠️ `carte.bin` A LA MÊME DISPOSITION QU'UN TAMPON D'ÉCHÉANCE DU
#  PRODUIT B, RÉPÉTÉE 25 FOIS. Ce n'est pas une coïncidence, c'est le
#  point : un bloc d'échéance de cet objet est octet pour octet ce que le
#  calque lit déjà en tête d'un `e{step}.bin` — `u` puis `v`, 25 niveaux
#  chacun. Le décodeur du client ne change pas ; seule l'adresse change.
#
#  ── LE CACHE : `CACHE_REECRIT`, ET C'EST UN CHOIX, PAS UNE PRUDENCE ──
#  Le critère du 14/08 est « les mêmes octets sortiront-ils TOUJOURS de
#  cette clé ? ». Ici la réponse est **non**, et il faut le dire :
#  la clé porte le run PI, mais les octets dépendent AUSSI du run du
#  produit B disponible au moment de la composition. Rejouer une
#  ingestion PI (`--forcer`) après la publication d'un nouveau run AROME
#  produit d'autres octets sous la même clé.
#  ⚠️ Et `CACHE_IMMUABLE` vaut 21 600 s — SIX HEURES — pour un objet dont
#  la rétention est de trois runs, soit trois heures. Un cache qui
#  survit à l'objet qu'il décrit est précisément la forme du défaut du
#  13/08.
#  ⓘ Le coût est nul ou presque : chaque heure le client lit une clé
#  NEUVE (l'index le lui dit), donc il n'y avait rien à réutiliser.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

from composite import (ALPHA_MELANGE, ERREUR_INTERP_PAR_NIVEAU,  # noqa: E402
                       Z_EXTINCTION_DEBUT, Z_EXTINCTION_FIN, composer,
                       rampe_pi, resolution_temporelle)
from domaine import (DOMAINES_PI, NIVEAUX_H_0025,  # noqa: E402
                     POURQUOI_PAS_DE_PI, pi_couvre)
from grille import (CLE_INDEX as CLE_INDEX_PRODUIT_B,  # noqa: E402
                    PARAMS_GRILLE, index_apres, index_apres_purge,
                    verifier_prefixe)
from pi import (CLE_INDEX_RAFRAICHISSEMENT,  # noqa: E402
                ECHEANCES_MIN, GABARIT_CLE_RAFRAICHISSEMENT,
                HORIZON_MINUTES, NIVEAUX_DELTA, NIVEAUX_PI,
                PREFIXE_RAFRAICHISSEMENT, RETENTION_RUNS, Abort,
                cles_du_rafraichissement, cles_du_run_grille, json_octets)
from quantification import quantifier  # noqa: E402


def crier(msg=""):
    print(msg, flush=True)


# ══════════════════════════════════════════════════════════════════════
#  CE QUE LE RAFRAÎCHISSEMENT PORTE — et rien de plus
# ══════════════════════════════════════════════════════════════════════
#  ⛔ `u` et `v`, bloc `hauteur`, et RIEN D'AUTRE. Ce n'est pas une v0
#  qu'on étendra : c'est tout ce que le composite sait calculer. Δ est
#  mesuré sur `u`/`v` aux niveaux de PI ; la température, l'humidité, la
#  TKE, les isobares et la surface n'ont AUCUN Δ. Les inclure ferait
#  republier du produit B à l'identique sous un nom qui promet du frais.
#  ⚠️ Les trois mots de bloc sont ceux que `service.tranches[*].bloc`
#  publie côté produit B. Ils ne se recopient pas : ils s'importent.
BLOC = "hauteur"
ORDRE_TRANCHES = ("u", "v")

#: Les niveaux du composite : les 25 d'AROME, pas les 6 de PI. C'est
#: tout l'objet de `composite.etendre_delta`.
NIVEAUX = tuple(NIVEAUX_H_0025)

#: Le format de publication, repris du produit B pour que les deux
#: objets soient COMPARABLES à l'octet près. ⚠️ Sans le même arrondi des
#: deux côtés, l'invariant `composite == PI` devient invérifiable — le
#: piège qui a rendu un « 0/125 » parfaitement crédible à l'étape 8.
PARAMS_UV = {p["nom"]: p for p in PARAMS_GRILLE if p["nom"] in ORDRE_TRANCHES}
assert set(PARAMS_UV) == set(ORDRE_TRANCHES), (
    "u/v introuvables dans PARAMS_GRILLE — le produit B a changé de "
    "paramètres sans que ce module le sache")

#: ⚠️ float16 PARTOUT dans les deux jumeaux : aucune tranche float32,
#: contrairement au produit B (`ziso`, `psol`). L'alignement sur 4 n'est
#: donc pas requis dans `carte.bin` — et il n'est PAS garanti. Il l'est
#: en revanche dans `colonnes.bin`, où le pas d'enregistrement vaut
#: 2 × 25 × 25 × 2 = 2 500 octets, multiple de 4 par construction.
DTYPE = np.dtype("<f2")


# ══════════════════════════════════════════════════════════════════════
#  L'APPARIEMENT DES DEUX CHAÎNES
# ══════════════════════════════════════════════════════════════════════
def decalage_minutes(run_pi, run_b):
    """Minutes entre le début du run AROME et celui du run PI.

    ⚠️ C'est ce décalage qui décide QUELLES échéances du produit B il
    faut lire — et le cahier des charges du lot se trompait sur ce
    point : il annonçait « les échéances 0→7 ». **Ce n'est vrai que si
    les deux runs commencent à la même heure.** Mesuré le 17/08 à
    09:37 UTC : dernier run PI 09 Z, dernier produit B ingéré 03 Z, donc
    un décalage de 6 h et les échéances **6 → 12**. Lire 0→7 aurait
    composé PI de 09 h avec de l'AROME valide à 03 h — un Δ de six
    heures de dérive, lisse, plausible, et faux partout.
    """
    import datetime as dt                                # noqa: PLC0415
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    t_pi = dt.datetime.strptime(run_pi, fmt).replace(tzinfo=dt.timezone.utc)
    t_b = dt.datetime.strptime(run_b, fmt).replace(tzinfo=dt.timezone.utc)
    return int((t_pi - t_b).total_seconds() // 60)


def steps_necessaires(decalage_min, steps_disponibles):
    """Les échéances HORAIRES d'AROME qui encadrent la fenêtre de PI.

    ⛔ On REFUSE plutôt que d'extrapoler : `composite.arome_interpole`
    lève hors couverture, et ce module doit lever AVANT d'avoir tiré
    8 Mo pour rien.

    ⚠️ On exige aussi la CONTIGUÏTÉ horaire. Un trou d'échéance dans le
    produit B (une passe de rallonge incomplète) ferait interpoler
    linéairement AU-DESSUS du trou : deux heures d'écart traitées comme
    une, sans que rien ne lève.
    """
    if decalage_min < 0:
        raise Abort(
            f"le run du produit B est POSTÉRIEUR au run PI (décalage "
            f"{decalage_min} min). Composer reviendrait à corriger un "
            f"modèle avec un autre qui décrit un instant différent.")
    dispo = sorted(int(s) for s in steps_disponibles)
    if not dispo:
        raise Abort("le produit B ne publie aucune échéance")
    h0 = decalage_min / 60.0
    h1 = (decalage_min + HORIZON_MINUTES) / 60.0
    avant = [s for s in dispo if s <= h0]
    apres = [s for s in dispo if s >= h1]
    if not avant or not apres:
        raise Abort(
            f"le produit B ne couvre pas la fenêtre PI [{h0:.2f} h, "
            f"{h1:.2f} h] : il publie {dispo[0]}–{dispo[-1]} h. ⛔ On "
            f"n'extrapole PAS — un composite au-delà de l'horizon du "
            f"modèle qui le porte est une valeur inventée.")
    s0, s1 = max(avant), min(apres)
    choisis = [s for s in dispo if s0 <= s <= s1]
    if choisis != list(range(s0, s1 + 1)):
        raise Abort(
            f"trou d'échéance dans le produit B entre {s0} et {s1} h "
            f"(présentes : {choisis}). ⚠️ Interpoler par-dessus le trou "
            f"traiterait deux heures d'écart comme une seule.")
    return choisis


def verifier_axes(man_b, lats, lons, tolerance=1e-4):
    """Les axes du produit B et ceux de la grille PI doivent COÏNCIDER.

    ⚠️⚠️ C'est le garde-fou le plus important du module, et c'est le
    piège déjà payé le 10/08 par `pi.aligner_sur_axes` : le WCS avait
    rendu 61 × 85 là où la découpe du GRIB rendait 61 × 84. **Une colonne
    d'écart vaut 1,95 km en longitude et 2,78 km en latitude.** Δ serait
    alors calculé entre colonnes VOISINES : une carte de gradient
    horizontal déguisée en correction temporelle, lisse, plausible, et
    fausse partout.

    ⓘ Mesuré le 17/08 : les deux font 111 × 105 avec les mêmes bornes.
    C'est une OBSERVATION, pas une garantie — les deux fenêtres sont
    découpées par deux chaînes qui ne se parlent pas, et l'une des deux
    (le WCS) choisit la sienne toute seule.
    """
    ax = man_b.get("axes") or {}
    attendu = dict(nb_lat=len(lats), nb_lon=len(lons),
                   lat_premier=float(lats[0]), lat_dernier=float(lats[-1]),
                   lon_premier=float(lons[0]), lon_dernier=float(lons[-1]))
    for cle in ("nb_lat", "nb_lon"):
        if int(ax.get(cle, -1)) != attendu[cle]:
            raise Abort(
                f"axes incompatibles : le produit B annonce {cle}="
                f"{ax.get(cle)}, la grille PI porte {attendu[cle]}. ⛔ "
                f"REFUS. Une colonne d'écart vaut 1,95 km et rendrait un "
                f"Δ PI−AROME lisse, plausible et faux partout.")
    for cle in ("lat_premier", "lat_dernier", "lon_premier", "lon_dernier"):
        ecart = abs(float(ax.get(cle, 1e9)) - attendu[cle])
        if ecart > tolerance:
            raise Abort(
                f"axes incompatibles : {cle} vaut {ax.get(cle)} côté "
                f"produit B et {attendu[cle]:.4f} côté PI (écart "
                f"{ecart:.6f}°). ⚠️ NE PAS ÉLARGIR LA TOLÉRANCE.")
    niveaux_b = [int(z) for z in (man_b.get("niveaux_m_sol") or [])]
    if niveaux_b != list(NIVEAUX):
        raise Abort(
            f"le produit B publie {len(niveaux_b)} niveaux hauteur, ce "
            f"module en compose {len(NIVEAUX)} — et ce ne sont pas les "
            f"mêmes. Composer alignerait deux verticales différentes par "
            f"leur INDICE, ce qui ne lève jamais.")
    return True


def dernier_run_produit_b(st, domaine):
    """Le run du produit B le plus récent EN LIGNE pour ce domaine.

    ⚠️ Par l'INDEX, jamais par une convention d'heure. Le produit B est
    publié 8 fois par jour mais il est INGÉRÉ quand Météo-France a fini
    de publier — mesuré le 17/08 : à 09:37 UTC le dernier run en ligne
    était encore le 03 Z. Déduire « il est 10 h donc c'est le 09 Z »
    rendrait un 404 une fois sur deux, et pire : un jour où le 09 Z
    existerait à moitié, un Range sur un objet d'une autre génération.
    """
    index = st.get_json(CLE_INDEX_PRODUIT_B) or {}
    runs = sorted(e.get("run") for e in (index.get("runs") or [])
                  if e.get("domaine") == domaine and e.get("run"))
    if not runs:
        raise Abort(
            f"aucun run du produit B en ligne pour le domaine {domaine} "
            f"(index {CLE_INDEX_PRODUIT_B}). ⛔ Sans lui il n'y a rien à "
            f"rafraîchir — et fabriquer un objet vide serait pire que "
            f"n'en fabriquer aucun.")
    return runs[-1]


def lire_uv_produit_b(st, domaine, run_b, man_b, steps, journal=crier):
    """`u` et `v` du bloc `hauteur`, par Range, sur les échéances voulues.

    Renvoie `(uv, octets_lus)` où `uv` a la forme
    `(2, len(NIVEAUX), len(steps), nb_lat, nb_lon)` en float32.

    ⛔ TOUT SE LIT DANS LE MANIFESTE : la clé (`service.cle_echeance`),
    l'offset, la longueur et le dtype de chaque tranche. Rien n'est
    recalculé ici — c'est la même discipline que le client web, et elle
    existe parce qu'un run écrit par une version antérieure du code doit
    se relire selon SON manifeste.
    """
    service = man_b.get("service") or {}
    tr = service.get("tranches") or {}
    nj = int(man_b["axes"]["nb_lat"])
    ni = int(man_b["axes"]["nb_lon"])
    for nom in ORDRE_TRANCHES:
        t = tr.get(nom)
        if not t:
            raise Abort(f"le manifeste du produit B ne publie pas de "
                        f"tranche `{nom}`")
        if t.get("bloc") != BLOC:
            raise Abort(
                f"la tranche `{nom}` du produit B appartient au bloc "
                f"`{t.get('bloc')}` et non `{BLOC}`. ⛔ `u` sur les "
                f"niveaux hauteur et `u` sur les isobares sont DEUX "
                f"champs différents.")
        if t.get("dtype") != "float16":
            raise Abort(f"tranche `{nom}` en {t.get('dtype')} — ce module "
                        f"ne sait décoder que float16")
        if int(t.get("niveaux", -1)) != len(NIVEAUX):
            raise Abort(f"tranche `{nom}` : {t.get('niveaux')} niveaux "
                        f"pour {len(NIVEAUX)} attendus")
        if int(t.get("octets", -1)) != len(NIVEAUX) * nj * ni * DTYPE.itemsize:
            raise Abort(
                f"tranche `{nom}` : {t.get('octets')} octets annoncés "
                f"pour {len(NIVEAUX) * nj * ni * DTYPE.itemsize} déduits "
                f"des axes. Le manifeste se contredit lui-même.")

    gabarit = service.get("cle_echeance")
    if not gabarit:
        raise Abort("le manifeste du produit B ne publie pas "
                    "`service.cle_echeance` — rien à lire")

    debut = min(int(tr[n]["offset"]) for n in ORDRE_TRANCHES)
    fin = max(int(tr[n]["offset"]) + int(tr[n]["octets"])
              for n in ORDRE_TRANCHES)
    longueur = fin - debut

    uv = np.empty((2, len(NIVEAUX), len(steps), nj, ni), dtype=np.float32)
    octets_lus = 0
    for k, step in enumerate(steps):
        cle = gabarit.format(domaine=domaine, run=run_b, step=int(step))
        brut = st.get_range(cle, debut, longueur)
        if brut is None:
            raise Abort(
                f"{cle} : absent. ⚠️ L'index l'annonce en ligne — soit la "
                f"purge a débordé, soit l'index ment. Ne rien composer.")
        octets_lus += len(brut)
        for c, nom in enumerate(ORDRE_TRANCHES):
            o = int(tr[nom]["octets"])
            a = np.frombuffer(brut, dtype=DTYPE,
                              count=o // DTYPE.itemsize,
                              offset=int(tr[nom]["offset"]) - debut)
            uv[c, :, k] = a.reshape(len(NIVEAUX), nj, ni).astype(np.float32)
    journal(f"     produit B {run_b} · échéances {steps[0]}–{steps[-1]} h · "
            f"{octets_lus / 1e6:.2f} Mo lus par Range "
            f"(sur {int(service.get('octets_par_echeance', 0)) * len(steps) / 1e6:.0f} Mo "
            f"si l'on tirait les tampons entiers)")
    return uv, octets_lus


# ══════════════════════════════════════════════════════════════════════
#  LE CONTENEUR
# ══════════════════════════════════════════════════════════════════════
class Rafraichissement:
    """Le composite d'un run PI sur un domaine, prêt à être servi.

        composite : (paramètre, niveau, échéance, lat, lon)  float16
                    paramètres = ORDRE_TRANCHES, niveaux = NIVEAUX,
                    échéances  = ECHEANCES_MIN (25 pas de 15 min)

    ⚠️ Le tableau est gardé en disposition « produit B » (param, niveau,
    échéance, points) et les deux jumeaux en dérivent par `moveaxis`.
    Deux constructions indépendantes des mêmes octets, c'est la
    divergence assurée le jour où l'une bouge — le défaut que
    `grille._blocs()` existe pour éviter.
    """

    def __init__(self, run_pi, domaine, run_b, steps_b, decalage_min,
                 composite, diagnostic, lats, lons, octets_lus=0):
        self.run_pi = run_pi
        self.domaine = domaine
        self.run_b = run_b
        self.steps_b = list(steps_b)
        self.decalage_min = int(decalage_min)
        self.diagnostic = diagnostic
        self.lats = np.asarray(lats, dtype=np.float32)
        self.lons = np.asarray(lons, dtype=np.float32)
        self.octets_lus = int(octets_lus)
        a = np.asarray(composite)
        attendu = (len(ORDRE_TRANCHES), len(NIVEAUX), len(ECHEANCES_MIN),
                   len(self.lats), len(self.lons))
        if a.shape != attendu:
            raise Abort(f"composite {a.shape} au lieu de {attendu}")
        # ⚠️ LE MÊME ARRONDI DE PUBLICATION QUE LE PRODUIT B, sans quoi
        # l'invariant `composite == PI` n'est pas vérifiable.
        self.composite = np.stack(
            [quantifier(a[c], PARAMS_UV[nom])
             for c, nom in enumerate(ORDRE_TRANCHES)]).astype(np.float16)

    # ── Les octets ────────────────────────────────────────────────────
    def octets_par_echeance(self):
        """Un bloc d'échéance de `carte.bin` — octet pour octet ce que le
        calque lit déjà en tête d'un `e{step}.bin` du produit B."""
        return (len(ORDRE_TRANCHES) * len(NIVEAUX) * len(self.lats)
                * len(self.lons) * DTYPE.itemsize)

    def tranches(self):
        """Offset, longueur et dtype de chaque tranche, RELATIFS au début
        d'un bloc d'échéance de `carte.bin`.

        ⚠️ Relatifs, et le manifeste le dit en toutes lettres. Un client
        qui les lirait comme absolus décoderait `v` à la place de `u`
        pour toutes les échéances sauf la première — sans une seule
        erreur, avec un vent tourné de 90°.
        """
        par_niveau = len(self.lats) * len(self.lons) * DTYPE.itemsize
        out, offset = {}, 0
        for nom in ORDRE_TRANCHES:
            octets = len(NIVEAUX) * par_niveau
            out[nom] = dict(offset=offset, octets=octets,
                            dtype=DTYPE.name, niveaux=len(NIVEAUX),
                            disposition="(niveau, lat, lon)", bloc=BLOC)
            offset += octets
        return out

    def carte_bin(self):
        """`(échéance, tranche, niveau, lat, lon)`, C-contigu, sans en-tête.

        ⛔ L'ÉCHÉANCE EST L'AXE EXTERNE, et c'est la décision de forme de
        cet objet. Le calque sert UNE échéance et balaie ensuite toute la
        plage d'altitudes (14 à 25 niveaux — mesuré le 12/08, parce que
        `h = A − zsol` s'étale autant que `zsol`). Avec l'échéance
        dehors, il tire **un seul Range de 1 165 500 octets** et a `u`,
        `v` et les 25 niveaux. Avec le paramètre dehors, il en tirait
        deux, à 14,5 Mo de distance l'un de l'autre.
        """
        return np.ascontiguousarray(
            np.moveaxis(self.composite, 2, 0), dtype=DTYPE).tobytes()

    def octets_par_colonne(self):
        """⚠️ 2 × 25 × 25 × 2 = 2 500 octets, multiple de 4 par
        construction. Aucun bloc float32 ici, donc aucun remplissage à
        prévoir — mais le multiple de 4 est conservé pour que l'objet
        reste indexable comme celui du produit B."""
        return (len(ORDRE_TRANCHES) * len(NIVEAUX) * len(ECHEANCES_MIN)
                * DTYPE.itemsize)

    def tranches_colonne(self):
        out, offset = {}, 0
        for nom in ORDRE_TRANCHES:
            octets = len(NIVEAUX) * len(ECHEANCES_MIN) * DTYPE.itemsize
            out[nom] = dict(offset=offset, octets=octets, dtype=DTYPE.name,
                            niveaux=len(NIVEAUX),
                            echeances=len(ECHEANCES_MIN),
                            disposition="(niveau, echeance)", bloc=BLOC)
            offset += octets
        return out

    def colonnes_bin(self):
        """Un enregistrement par colonne, dans l'ordre (lat, lon).

        ⚠️ Les échéances sont l'axe le PLUS INTERNE, comme dans le
        `colonnes.bin` du produit B : la coupe lit une série temporelle
        par (paramètre, niveau), c'est cette lecture-là qu'on veut
        contiguë. Un Range de 2 500 octets suffit à toute la colonne.
        """
        nj, ni = len(self.lats), len(self.lons)
        a = self.composite.reshape(len(ORDRE_TRANCHES), len(NIVEAUX),
                                   len(ECHEANCES_MIN), nj * ni)
        return np.ascontiguousarray(
            np.moveaxis(a, 3, 0), dtype=DTYPE).tobytes()

    def octets_publies(self):
        return (self.octets_par_echeance() * len(ECHEANCES_MIN)
                + self.octets_par_colonne() * len(self.lats) * len(self.lons))

    def remplissage(self):
        """Par paramètre, comme partout ailleurs dans ce projet.

        ⚠️ Un remplissage global masquerait le cas qui compte : `u`
        servi et `v` absent donne un vent de direction fausse et de
        vitesse plausible.
        """
        return {nom: round(float(np.isfinite(
                    self.composite[c].astype(np.float32)).mean()), 4)
                for c, nom in enumerate(ORDRE_TRANCHES)}

    # ── Ce que le client a le droit d'affirmer ────────────────────────
    def provenance(self):
        """La provenance de CE QUI EST DANS CET OBJET, échéance par
        échéance, dans le vocabulaire du produit B.

        ⛔⛔ ET ELLE PORTE LA DÉPENDANCE EN τ QUE `composite.niveaux` NE
        PEUT PAS PORTER. `composite.resolution_temporelle(z)` répond par
        NIVEAU : « observée (PI) » sous 500 m/sol. C'est vrai tant que
        `w_PI = 1`, c'est-à-dire jusqu'à 4 h — au-delà, la rampe
        d'horizon éteint Δ, et à 6 h le composite vaut de l'AROME
        interpolé À TOUS LES NIVEAUX, y compris à 20 m. Publier la seule
        table par niveau ferait donc affirmer « observée à 15 min » sur
        une valeur qui ne l'est plus.
        ⓘ La table par niveau reste publiée telle quelle (`niveaux`), et
        elle est renvoyée à sa condition de validité. Les deux se lisent
        ensemble ; aucune des deux ne se déduit de l'autre.
        """
        poids = list(self.diagnostic["poids_pi"])
        # ── L5 (27/08/2026) : le désaccord AROME/PI, PAR ÉCHÉANCE ──────
        # ⓘ Le résumé « toutes niveaux confondus » (`angle_deg_echeance`/
        # `ratio_echeance`), pas la table par niveau : `poids_pi` non
        # plus ne varie pas avec l'altitude choisie à l'écran (aucune
        # liste d'altitudes n'existe côté client — cf.
        # `AltitudeWindPanel.tsx`), donc le désaccord affiché À CÔTÉ de
        # lui doit vivre à la même granularité, pas à une plus fine que
        # personne ne peut sélectionner.
        desac = self.diagnostic["desaccord"]
        par_echeance = []
        for k, minute in enumerate(ECHEANCES_MIN):
            w = float(poids[k])
            # ⛔⛔ LE RÉGIME SE LIT SUR LA RAMPE, PAS SUR LE POIDS SERVI —
            # CORRIGÉ LE 26/08/2026, ET VU SUR L'ÉCRAN DE PRODUCTION.
            # Ces trois branches testaient `w`, le poids TOTAL. Tant que
            # α valait 1, `w` et la rampe étaient le même nombre. Depuis
            # que le composite MÉLANGE (α = 0,5), `w` ne vaut plus jamais
            # 1 : la branche « PI seul maître » est devenue INATTEIGNABLE
            # et la branche « rampe d'horizon : ATTÉNUÉE » s'affichait à
            # TOUTES les échéances — y compris à +1 h, où la rampe est
            # pleine et où rien n'est atténué par l'horizon.
            # C'est le troisième exemplaire du même piège en une journée
            # (`niveaux_valables_si`, le commentaire du type web, et
            # ici) : *changer une échelle, c'est réviser toutes les
            # phrases qui la citaient.* Celui-ci n'a été trouvé ni par un
            # banc ni par une relecture, mais en LISANT L'ÉCRAN.
            r = rampe_pi(minute)
            # ⚠️ Le désaccord n'a de sens QUE là où PI existe (r > 0) —
            # ajouté aux DEUX branches "arome+pi", jamais à "arome" seul :
            # sans second vecteur à comparer, publier un angle serait
            # inventer un désaccord qui n'a pas été mesuré.
            champs_desaccord = dict(
                angle_deg_desaccord=desac["angle_deg_echeance"][k],
                ratio_desaccord=desac["ratio_echeance"][k],
                depasse_seuil_desaccord_propose=desac["depasse_seuil_propose"][k])
            if r >= 1.0:
                bloc = dict(
                    modele="arome+pi", run=self.run_b, run_pi=self.run_pi,
                    poids_pi=round(w, 4), alpha_melange=ALPHA_MELANGE,
                    regime_temporel=(
                        f"PI pleinement disponible sous 500 m/sol, mélangé "
                        f"à AROME à parts {ALPHA_MELANGE:.0%} / "
                        f"{1 - ALPHA_MELANGE:.0%}"),
                    **champs_desaccord)
            elif r > 0.0:
                bloc = dict(
                    modele="arome+pi", run=self.run_b, run_pi=self.run_pi,
                    poids_pi=round(w, 4), alpha_melange=ALPHA_MELANGE,
                    regime_temporel=(
                        "rampe d'horizon : la DISPONIBILITÉ de PI décroît "
                        "vers son horizon de 6 h, l'erreur d'interpolation "
                        "résiduelle vaut (1 − poids_pi) × "
                        "erreurInterpolationMs"),
                    **champs_desaccord)
            else:
                bloc = dict(
                    modele="arome", run=self.run_b, poids_pi=0.0,
                    regime_temporel=(
                        "au-delà de l'horizon utile de PI : cette échéance "
                        "est de l'AROME HORAIRE INTERPOLÉ en τ, à TOUS les "
                        "niveaux — aucune trace de PI, et il ne faut pas "
                        "laisser croire le contraire"))
            par_echeance.append(dict(echeance_min=int(minute), blocs={BLOC: bloc}))
        return dict(
            granularite="echeance x bloc",
            blocs=[BLOC],
            note=("provenance de CE QUI EST DANS CET OBJET. ⛔ L'ÂGE N'EST "
                  "PAS PUBLIÉ : il périme à la lecture, il se calcule à "
                  "l'écran depuis `run_pi` et `run_produit_b`. ⚠️ Le nom "
                  "du bloc est celui que `service.tranches[*].bloc` publie "
                  "côté produit B — les mêmes mots, jamais recopiés."),
            modeles=dict(
                arome=dict(nom="AROME 0,025°", runs_par_jour=8,
                           resolution_temporelle_min=60, run=self.run_b),
                arome_pi=dict(nom="AROME-PI 0,025°", runs_par_jour=24,
                              resolution_temporelle_min=15, run=self.run_pi,
                              niveaux_delta_mesure=list(NIVEAUX_DELTA))),
            par_echeance=par_echeance)

    def manifeste(self, extra=None):
        m = dict(
            produit=(f"AGRUME — rafraîchissement PI du produit B, domaine "
                     f"{self.domaine} (jetable)"),
            run_pi=self.run_pi,
            run_produit_b=self.run_b,
            domaine=self.domaine,
            decalage_min=self.decalage_min,
            echeances_produit_b_lues=list(self.steps_b),
            echeances_min=list(ECHEANCES_MIN),
            pas_min=ECHEANCES_MIN[1] - ECHEANCES_MIN[0],
            horizon_min=HORIZON_MINUTES,
            niveaux_m_sol=list(NIVEAUX),
            parametres=[dict(nom=n, unite=PARAMS_UV[n]["unite"], bloc=BLOC)
                        for n in ORDRE_TRANCHES],
            # ══ CE QUE LE CLIENT DOIT LIRE POUR SERVIR ═══════════════
            service=dict(
                cle_carte=GABARIT_CLE_RAFRAICHISSEMENT.format(
                    domaine=self.domaine, run_pi=self.run_pi,
                    objet="carte.bin"),
                cle_colonnes=GABARIT_CLE_RAFRAICHISSEMENT.format(
                    domaine=self.domaine, run_pi=self.run_pi,
                    objet="colonnes.bin"),
                cle_index=CLE_INDEX_RAFRAICHISSEMENT,
                encodage="aucun — les deux objets sont BRUTS, Range-ables",
                carte=dict(
                    disposition=("(echeance, tranche, niveau, lat, lon) "
                                 "little-endian, C-contigu, SANS en-tête"),
                    octets_par_echeance=self.octets_par_echeance(),
                    offset=("index de l'échéance dans `echeances_min` × "
                            "`octets_par_echeance`"),
                    tranches=self.tranches(),
                    note=("⚠️ Les offsets de `tranches` sont RELATIFS au "
                          "début du bloc d'échéance, pas au début de "
                          "l'objet. Un bloc d'échéance est octet pour "
                          "octet ce que le calque lit déjà en tête d'un "
                          "`e{step}.bin` du produit B : `u` puis `v`, 25 "
                          "niveaux chacun. Le décodeur ne change pas, "
                          "seule l'adresse change.")),
                colonnes=dict(
                    disposition=("un enregistrement par colonne, dans "
                                 "l'ordre (lat, lon) — du NORD au sud puis "
                                 "d'ouest en est, comme `zsol` du produit B"),
                    octets_par_colonne=self.octets_par_colonne(),
                    offset=("(j * nb_lon + i) * octets_par_colonne, où j "
                            "indexe `lats` (DÉCROISSANT) et i `lons`"),
                    tranches=self.tranches_colonne(),
                    note=("un Range de `octets_par_colonne` suffit à toute "
                          "la colonne : `u` et `v`, 25 niveaux, 25 "
                          "échéances.")),
                note=("⛔ AUCUNE tranche float32 dans cet objet — "
                      "l'alignement sur 4 n'est donc ni requis ni garanti "
                      "dans `carte.bin`. `colonnes.bin`, lui, a un pas de "
                      "2 500 octets, multiple de 4.")),
            # ⓘ `zsol` n'est PAS republié : ce sont les mêmes niveaux AGL
            # sur le même domaine, donc le `zsol.bin` du produit B fait
            # foi. Le dupliquer aurait créé deux sols pour une colonne —
            # le défaut que `profil.py` existe pour refuser.
            zsol=dict(
                republie=False,
                ou=("`service.cle_zsol` du manifeste du produit B — mêmes "
                    "niveaux AGL, même domaine, même sol modèle"),
                reference_verticale=("niveaux AGL au-dessus du sol DU "
                                     "MODÈLE : altitude_ASL = zsol[j,i] + "
                                     "niveau")),
            axes=dict(
                nb_lat=len(self.lats), nb_lon=len(self.lons),
                lat_premier=round(float(self.lats[0]), 4),
                lat_dernier=round(float(self.lats[-1]), 4),
                lon_premier=round(float(self.lons[0]), 4),
                lon_dernier=round(float(self.lons[-1]), 4),
                sens=("lats DÉCROISSANTES (premier point au NORD) ; lons "
                      "croissantes — VÉRIFIÉES identiques à celles du "
                      "produit B avant composition, et le refus est net")),
            # ══ ⛔⛔ CE QUI DOIT SURVIVRE AU PASSAGE ══════════════════
            # C'est le champ le plus important de la réponse : il dit que
            # le pas de 15 min est OBSERVÉ sous 500 m/sol et INTERPOLÉ
            # au-dessus. Sans lui, l'objet AFFIRME une résolution qu'il
            # n'a pas. Il vient de `composite.composer()` tel quel — pas
            # recopié, pas reformulé.
            niveaux=list(self.diagnostic["niveaux"]),
            # ⛔ FORMULATION CORRIGÉE LE 26/08/2026. Elle disait « à
            # `poids_pi = 1` » — une condition que `poids_pi` ne REMPLIT
            # PLUS JAMAIS depuis que le composite mélange (α = 0,5) au
            # lieu de remplacer. Le client aurait affiché une condition
            # inatteignable, c'est-à-dire une table qu'il n'aurait plus
            # jamais eu le droit de lire. Ce qui compte ici est la
            # DISPONIBILITÉ de PI, pas le poids qu'on lui accorde.
            niveaux_valables_si=(
                "⚠️ la table `niveaux` décrit le régime tant que PI est "
                "PLEINEMENT DISPONIBLE, c'est-à-dire jusqu'à 4 h. Au-delà, "
                "la rampe d'horizon éteint Δ et la résolution EFFECTIVE de "
                "chaque échéance est dans "
                "`provenance.par_echeance[*].blocs.hauteur`. ⓘ Le poids "
                "servi vaut α × disponibilité (voir `conventions.melange`) "
                "et ne vaut donc jamais 1 : le composite MÉLANGE AROME et "
                "AROME-PI, il ne remplace pas l'un par l'autre."),
            poids_pi=list(self.diagnostic["poids_pi"]),
            # ⛔ IL MANQUAIT AU MANIFESTE. `composer()` le mettait bien
            # dans son diagnostic et un banc le vérifiait LÀ — mais ce
            # manifeste recopie des champs NOMMÉS, et celui-ci n'y était
            # pas. Le client déclarait donc `alpha_melange?` dans son
            # type pour un champ que le serveur n'envoyait jamais.
            # Trouvé en lisant l'objet RÉELLEMENT publié sur R2, pas au
            # banc : *vérifier le producteur ne vérifie pas le publié.*
            alpha_melange=self.diagnostic["alpha_melange"],
            conventions=dict(self.diagnostic["conventions"]),
            mesures=dict(self.diagnostic["mesures"]),
            # ⛔ L5 (27/08/2026) : LE MÊME PIÈGE QUE `alpha_melange`
            # CI-DESSUS, ÉVITÉ EN LE RECOPIANT EXPLICITEMENT ICI. Le
            # diagnostic de `composite.composer()` porte bien la clé
            # `desaccord`, et un banc la vérifie LÀ (`test_composite.py`)
            # — mais ce manifeste recopie des champs NOMMÉS, et un champ
            # qu'on oublie de nommer ici n'atteint JAMAIS le client. cf.
            # piège nº 7 de BUGS.md 26/08 : *vérifier le producteur ne
            # vérifie pas le publié.*
            desaccord=dict(self.diagnostic["desaccord"]),
            provenance=self.provenance(),
            # ══ LA PRÉSÉANCE — publiée, jamais devinée ═══════════════
            preseance=(
                "POUR `u` et `v` DU BLOC `hauteur` SEULEMENT, et pour les "
                "seules échéances de `echeances_min` : cet objet gagne sur "
                "le produit B. Partout ailleurs — isobares, surface, "
                "`t`/`r`/`tke`, échéances au-delà de `horizon_min` — le "
                "produit B reste SEUL MAÎTRE, et cet objet n'a rien à en "
                "dire. ⚠️ Une valeur NON FINIE ici signifie « le "
                "rafraîchissement n'a rien à dire sur ce point » : le "
                "client DOIT retomber sur le produit B, jamais afficher "
                "un trou."),
            retention_runs=RETENTION_RUNS,
            remplissage=self.remplissage(),
            octets_publies=self.octets_publies(),
            octets_lus_produit_b=self.octets_lus,
            avertissement=(
                "Produit JETABLE : seuls les {n} derniers runs PI sont en "
                "ligne, et c'est `dernier` dans l'index `{i}` qui désigne "
                "le couple LISIBLE — les deux jumeaux s'écrivent ensemble "
                "ou pas du tout, et `dernier` n'avance qu'après les trois "
                "écritures. ⛔ NE PAS déduire le run PI du `run` du "
                "manifeste du produit B : celui-ci est publié 8 fois par "
                "jour, PI 24."
            ).format(n=RETENTION_RUNS, i=CLE_INDEX_RAFRAICHISSEMENT))
        if extra:
            m.update(extra)
        return m


# ══════════════════════════════════════════════════════════════════════
#  LA COMPOSITION
# ══════════════════════════════════════════════════════════════════════
def composer_rafraichissement(pi_uv, lats, lons, run_pi, domaine, st,
                              journal=crier, alpha=None):
    """Lit le produit B, compose, et rend un `Rafraichissement`.

    `pi_uv` : `(2, len(NIVEAUX_PI), 25, nb_lat, nb_lon)` — `u` et `v` de
    la grille PI, dans cet ordre, sur les 6 niveaux et les 25 échéances.

    ⓘ `alpha` n'existe QUE pour les bancs, et il se contente de traverser
    jusqu'à `composite.composer()` — voir la note qui y est écrite. Il
    permet de rejouer l'invariant historique (« le composite reproduit
    PI ») en forçant α = 1, sans que la production serve ce réglage : la
    phase B l'a mesuré moins bon qu'AROME seul. **Aucun appelant de
    production ne doit le passer.**
    """
    if not pi_couvre(domaine):
        raise Abort(POURQUOI_PAS_DE_PI.format(
            couverts=", ".join(DOMAINES_PI), domaine=domaine))
    a = np.asarray(pi_uv)
    attendu = (2, len(NIVEAUX_PI), len(ECHEANCES_MIN), len(lats), len(lons))
    if a.shape != attendu:
        raise Abort(f"pi_uv {a.shape} au lieu de {attendu}")

    run_b = dernier_run_produit_b(st, domaine)
    man_b = st.get_json(f"agrume/grille/{domaine}/{run_b}/manifest.json")
    if not man_b:
        raise Abort(f"manifeste du produit B introuvable pour {run_b} — "
                    f"l'index l'annonce pourtant en ligne")
    verifier_axes(man_b, lats, lons)

    decalage = decalage_minutes(run_pi, run_b)
    steps = steps_necessaires(decalage, man_b.get("echeances") or [])
    journal(f"     décalage PI − produit B : {decalage} min "
            f"({decalage / 60:.0f} h) → échéances AROME {steps[0]}–{steps[-1]} h")
    uv_b, octets_lus = lire_uv_produit_b(st, domaine, run_b, man_b, steps,
                                         journal=journal)

    t0 = time.monotonic()
    comp, diag = composer(a.astype(np.float64), uv_b.astype(np.float64),
                          steps, decalage_min=decalage, niveaux_cibles=NIVEAUX,
                          alpha=alpha)
    journal(f"     composite calculé en {time.monotonic() - t0:.2f} s "
            f"({comp.shape})")
    return Rafraichissement(run_pi, domaine, run_b, steps, decalage,
                            comp, diag, lats, lons, octets_lus=octets_lus)


# ══════════════════════════════════════════════════════════════════════
#  L'ÉCRITURE — et l'index qui rend le couple LISIBLE
# ══════════════════════════════════════════════════════════════════════
INDEX_VIDE = dict(
    produit="AGRUME — index des rafraîchissements PI en ligne",
    retention_runs=RETENTION_RUNS, runs=[], restes=[], dernier={})


def _horodatage():
    """L'instant de publication, au format des deux index frères."""
    import datetime as dt                                # noqa: PLC0415
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ecrire_index(st, run_pi, domaine, cles, avancer, journal=crier,
                  maintenant=None):
    """Index d'abord, suppression ensuite — l'ordre évite les orphelins
    invisibles, exactement comme pour le produit B.

    ⛔ `avancer=False` EXISTE POUR LES ÉCRITURES PARTIELLES. Si
    `colonnes.bin` échoue après `carte.bin`, l'objet écrit doit quand
    même ENTRER dans l'index : `ListObjects` n'est pas une route de ce
    projet, donc un objet hors index est **invisible et définitivement
    payé** — une fuite, pas un déchet. Il entre donc, il sera purgé au
    troisième run suivant, et `dernier` NE BOUGE PAS : personne ne lira
    un couple dépareillé.

    ⛔⛔ `ecrit_le` — LE TROU DE CACHE DU §7 DE L3a, ET IL SE REFERME ICI
    (Lot L3b, 17/08). Le client prenait le RUN PI comme jeton de cache,
    faute de mieux. Ça couvre le cas normal — une clé neuve chaque heure —
    mais **pas un REJEU sous le même run PI** : `rafraichissement.py`
    relancé à la main après la publication d'un nouveau run AROME réécrit
    exactement les mêmes clés avec d'AUTRES octets. `CACHE_REECRIT` est
    posé pour ça, mais les deux générations ont **la même longueur** :
    ni 416, ni tampon court, rien à quoi se raccrocher côté client. Le
    seul filet était `run_produit_b === run affiché`, qui n'attrape le
    rejeu que s'il change de run AROME.
    ⇒ L'index porte désormais son instant d'écriture, et `jetonDe()`
    (web/src/lib/rafraichissement.ts) le préfère au run PI **depuis le
    Lot L3a, sans qu'une ligne du client ne bouge** : il était écrit
    `idx.ecrit_le || runPi`.

    ⚠️ HORODATÉ UNE SEULE FOIS, pour les DEUX écritures. L'index est
    republié après la purge quand des suppressions ont échoué ; deux
    horodatages différents changeraient le jeton une seconde fois, donc
    feraient retélécharger 58,3 Mo pour des octets identiques. Un jeton
    n'a pas à être frais, il a à être JUSTE.
    """
    from storage import CACHE_REECRIT                     # noqa: PLC0415, F401
    ecrit_le = maintenant or _horodatage()
    index = st.get_json(CLE_INDEX_RAFRAICHISSEMENT) or dict(INDEX_VIDE)
    dernier = dict(index.get("dernier") or {})
    nouveau, a_supprimer = index_apres(index, run_pi, domaine, cles,
                                       retention=RETENTION_RUNS)
    # ⚠️ LE GARDE-FOU QUI EMPÊCHE LA PURGE DE DÉBORDER. Les colonnes PI
    # (`agrume/pi/colonnes/`) sont DÉFINITIVES et vivent dans le même
    # bucket, sous un préfixe voisin d'une lettre près. La rétention du
    # portail est de 4,25 jours : ce qui s'y effacerait est perdu.
    verifier_prefixe(a_supprimer, prefixe=PREFIXE_RAFRAICHISSEMENT)
    if avancer:
        dernier[domaine] = run_pi
    nouveau["dernier"] = dernier
    # ⛔ Le jeton de cache du client (cf. la docstring). Il change à CHAQUE
    # publication, y compris un rejeu sous le même run PI — c'est
    # exactement ce que le run PI seul ne savait pas dire.
    nouveau["ecrit_le"] = ecrit_le
    nouveau["note"] = (
        "⛔ `dernier[domaine]` est LE run à lire : il n'avance qu'après "
        "l'écriture des TROIS objets. `runs` liste ce qui est en ligne "
        "pour la purge, et peut contenir un run incomplet — ne pas le "
        "lire pour choisir quoi servir. ⛔ `ecrit_le` est le JETON DE "
        "CACHE : le client le colle en query sur le manifeste et sur les "
        "octets, parce qu'un rejeu sous le même run PI réécrit les mêmes "
        "clés avec d'autres octets, de MÊME LONGUEUR.")
    # ⚠️ `no-store`, comme les deux index frères (`agrume/grille/` et
    # `agrume/pi/grille/`). Un index mis en cache ferait lire un run PI
    # purgé une heure plus tôt : 404 sur les deux jumeaux, et le client
    # ne saurait pas que c'est le cache et non la rétention.
    st.put(CLE_INDEX_RAFRAICHISSEMENT, json_octets(nouveau),
           cache_control="no-store", content_type="application/json")
    echecs = []
    for cle in a_supprimer:
        # ⛔⛔ ON LIT LA VALEUR DE RETOUR, ET C'EST UN CORRECTIF (L3b,
        # 17/08 — trouvé par le banc, pas par la relecture).
        #
        # `Storage.delete` (tools/storage.py) NE LÈVE JAMAIS : la façade
        # attrape tout et rend `False` — « une purge ne doit jamais être
        # bloquante », correctif du 30/07. Le `try/except Exception` qui
        # était ici n'attrapait donc RIEN. `echecs` restait vide quoi
        # qu'il arrive, `restes` ne se remplissait jamais, la clé n'était
        # jamais réessayée au run suivant — et elle sortait de l'index à
        # la rotation de rétention (3 runs, soit 3 h). ⇒ un objet EN
        # LIGNE et HORS INDEX : invisible, jamais purgé, définitivement
        # payé. C'est le motif EXACT des 18 orphelins des 12-13/08, et la
        # branche « N échecs (réessayés au run suivant)  » du journal
        # juste en dessous était du code MORT.
        #
        # ⓘ `ingest_colonnes.py` le fait bien depuis toujours
        # (`if not store.delete(c)`) : les deux purges du même bucket ne
        # posaient pas la même question à la même façade.
        #
        # ⚠️ Le `try` reste, mais en second rideau : la façade d'AUJOURD'HUI
        # ne lève pas, un backend de DEMAIN pourrait. Les deux chemins
        # mènent au même endroit — `restes`, donc un réessai.
        try:
            if not st.delete(cle):
                echecs.append(cle)
        except Exception:                                  # noqa: BLE001
            echecs.append(cle)
    if a_supprimer:
        journal(f"     purge : {len(a_supprimer) - len(echecs)} clés "
                f"supprimées"
                + (f", {len(echecs)} échecs (réessayés au run suivant)"
                   if echecs else ""))
        st.put(CLE_INDEX_RAFRAICHISSEMENT,
               json_octets(index_apres_purge(nouveau, echecs)),
               cache_control="no-store", content_type="application/json")
    return nouveau


def ecrire(st, raf, extra=None, journal=crier, maintenant=None):
    """Les deux jumeaux puis le manifeste, puis l'index. Dans cet ordre.

    ⛔ TOUT EST SÉRIALISÉ AVANT LA PREMIÈRE ÉCRITURE. Composer les octets
    pendant l'upload laisserait une fenêtre où une erreur de forme (un
    `moveaxis` qui lève) arriverait APRÈS que `carte.bin` soit déjà en
    ligne. Ici, si la sérialisation casse, rien n'est parti.

    ⛔ Le manifeste EN DERNIER des trois : il est ce qui rend l'objet
    lisible, il ne doit jamais décrire des octets absents.
    """
    from storage import CACHE_REECRIT                     # noqa: PLC0415
    c_carte, c_colonnes, c_man = cles_du_rafraichissement(raf.run_pi,
                                                          raf.domaine)
    corps = [(c_carte, raf.carte_bin(), "application/octet-stream"),
             (c_colonnes, raf.colonnes_bin(), "application/octet-stream"),
             (c_man, json_octets(raf.manifeste(extra)), "application/json")]
    ecrites = []
    try:
        for cle, octets, mime in corps:
            st.put(cle, octets, cache_control=CACHE_REECRIT,
                   content_type=mime)
            ecrites.append(cle)
    except Exception:
        if ecrites:
            journal(f"  ⚠️ écriture PARTIELLE ({len(ecrites)}/3) — les clés "
                    f"écrites entrent dans l'index pour être PURGÉES, et "
                    f"`dernier` ne bouge pas : personne ne lira un couple "
                    f"dépareillé.")
            try:
                _ecrire_index(st, raf.run_pi, raf.domaine, ecrites,
                              avancer=False, journal=journal,
                              maintenant=maintenant)
            except Exception as e:                         # noqa: BLE001
                journal(f"  ⛔ …et l'index n'a pas pu être mis à jour "
                        f"({type(e).__name__}: {e}) : {len(ecrites)} objet(s) "
                        f"HORS INDEX, donc invisibles. À supprimer à la main.")
        raise
    journal(f"  ✅ rafraîchissement écrit : {c_carte.rsplit('/', 1)[0]}/ "
            f"({raf.octets_publies() / 1e6:.1f} Mo, deux jumeaux)")
    _ecrire_index(st, raf.run_pi, raf.domaine, [c for c, _, _ in corps],
                  avancer=True, journal=journal, maintenant=maintenant)
    return [c for c, _, _ in corps]


# ══════════════════════════════════════════════════════════════════════
#  L'ORCHESTRATION — appelée par `ingest_pi.ecrire`
# ══════════════════════════════════════════════════════════════════════
def rafraichir(pi_uv, lats, lons, run_pi, domaine=None, st=None,
               extra=None, sans_ecriture=False, journal=crier):
    """Compose et publie le rafraîchissement d'un run PI.

    ⚠️ Lève. C'est l'appelant (`ingest_pi.ecrire`) qui décide que
    l'échec ne fait pas tomber le voyant — mais il doit CRIER.
    """
    if st is None:
        from storage import Storage                       # noqa: PLC0415
        st = Storage("agrume-pi-rafraichissement", "AGRUME_BUCKET",
                     "wind-grid")
    dom = domaine or DOMAINES_PI[0]
    raf = composer_rafraichissement(pi_uv, lats, lons, run_pi, dom, st,
                                    journal=journal)
    journal(f"     remplissage : {raf.remplissage()} · "
            f"{raf.octets_publies() / 1e6:.1f} Mo à publier")
    vides = [n for n, v in raf.remplissage().items() if v == 0.0]
    if vides:
        raise Abort(
            f"le composite est ENTIÈREMENT non fini sur {vides} — publier "
            f"un objet vide sous une clé que le client va préférer au "
            f"produit B remplacerait de la donnée par du néant.")
    if sans_ecriture:
        journal("     ⓘ --sans-ecriture : rien n'a été écrit.")
        return raf
    ecrire(st, raf, extra=extra, journal=journal)
    return raf


# ══════════════════════════════════════════════════════════════════════
#  CLI — pour VOIR, et pour rejouer sans attendre une ingestion
# ══════════════════════════════════════════════════════════════════════
def _grille_pi_en_ligne(st, run_pi, domaine=None):
    """Relit la grille PI publiée (`grille.npz`) et rend `(uv, lats, lons)`.

    ⓘ Existe pour que « déployé » puisse devenir « VU » sans attendre le
    prochain top d'heure : la chaîne réelle passe par la grille en
    mémoire, celle-ci par les octets en ligne — deux chemins, un seul
    résultat attendu.

    ⚠️ 19/08 (Lot M) — LE DOMAINE EST DANS LA CLÉ. Sans lui cette
    fonction relirait `agrume/pi/grille/{run}/grille.npz`, un chemin que
    plus personne n'écrit : le symptôme serait un `absent (rétention
    3 runs)` parfaitement trompeur, qui accuserait la purge d'un défaut
    de chemin.
    """
    c_npz, _c_man = cles_du_run_grille(run_pi, domaine or DOMAINES_PI[0])
    brut = st.get(c_npz)
    if brut is None:
        raise Abort(f"{c_npz} : absent (rétention 3 runs)")
    with np.load(io.BytesIO(brut)) as z:
        donnees, lats, lons = z["donnees"], z["lats"], z["lons"]
    # (paramètre, niveau, échéance, lat, lon) — u et v sont les deux
    # premiers de `PARAMS_V0`, dans cet ordre. ⚠️ Vérifié, pas supposé.
    return donnees[:2].astype(np.float64), lats, lons


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-pi", default=None,
                   help="run PI visé ; par défaut le `dernier` de l'index "
                        "de la grille PI")
    p.add_argument("--domaine", default=DOMAINES_PI[0])
    p.add_argument("--sans-ecriture", action="store_true")
    p.add_argument("--verifier", action="store_true",
                   help="relit les deux jumeaux EN LIGNE et confronte "
                        "carte.bin et colonnes.bin case par case")
    a = p.parse_args(argv)

    from pi import CLE_INDEX_GRILLE                       # noqa: PLC0415
    from storage import Storage                           # noqa: PLC0415
    st = Storage("agrume-pi-rafraichissement", "AGRUME_BUCKET", "wind-grid")

    if a.verifier:
        return _verifier_en_ligne(st, a.domaine)

    run_pi = a.run_pi
    if not run_pi:
        # ⚠️ 19/08 (Lot M) — FILTRÉ SUR LE DOMAINE DEMANDÉ. L'index porte
        # désormais une entrée par domaine ET par run : prendre « le plus
        # récent, tous domaines confondus » rendrait un run dont la
        # grille n'existe pas forcément pour CE domaine-là (une ingestion
        # pyrénéenne peut avoir échoué là où l'alpine a réussi), et le
        # message d'erreur accuserait alors la rétention.
        idx = st.get_json(CLE_INDEX_GRILLE) or {}
        runs = sorted(e.get("run") for e in (idx.get("runs") or [])
                      if e.get("run") and e.get("domaine") == a.domaine)
        if not runs:
            crier(f"⛔ aucune grille PI en ligne pour le domaine "
                  f"{a.domaine!r}")
            return 1
        run_pi = runs[-1]
    crier(f"AGRUME — rafraîchissement PI · run {run_pi} · {a.domaine}")
    uv, lats, lons = _grille_pi_en_ligne(st, run_pi, domaine=a.domaine)
    raf = rafraichir(uv, lats, lons, run_pi, domaine=a.domaine, st=st,
                     sans_ecriture=a.sans_ecriture,
                     extra=dict(fabrique_par="rafraichissement.py --run-pi"))
    crier(f"  produit B consommé : {raf.run_b} (décalage "
          f"{raf.decalage_min} min, échéances {raf.steps_b})")
    st.bilan(log=crier)
    return 0


def _verifier_en_ligne(st, domaine):
    """⛔ « fait ≠ commité ≠ déployé ≠ VU ». Ceci est le « vu ».

    Relit l'index, les deux jumeaux et le manifeste TELS QUE SERVIS, et
    confronte les deux dispositions sur un échantillon de colonnes. Une
    divergence ici voudrait dire que le calque et la coupe montrent deux
    vents différents au même instant — le défaut que ce lot existe pour
    ne pas créer.
    """
    index = st.get_json(CLE_INDEX_RAFRAICHISSEMENT) or {}
    run_pi = (index.get("dernier") or {}).get(domaine)
    if not run_pi:
        crier(f"⛔ aucun rafraîchissement LISIBLE pour {domaine} — "
              f"`dernier` est vide dans {CLE_INDEX_RAFRAICHISSEMENT}")
        return 1
    c_carte, c_colonnes, c_man = cles_du_rafraichissement(run_pi, domaine)
    man = st.get_json(c_man)
    if not man:
        crier(f"⛔ manifeste absent : {c_man}")
        return 1
    crier(f"✅ rafraîchissement lisible : {run_pi} ({domaine})")
    crier(f"   produit B consommé : {man['run_produit_b']} · décalage "
          f"{man['decalage_min']} min · échéances lues "
          f"{man['echeances_produit_b_lues']}")
    crier(f"   remplissage : {man['remplissage']} · "
          f"{man['octets_publies'] / 1e6:.1f} Mo publiés")
    res = {n["niveauMSol"]: n["resolutionTemporelleMin"]
           for n in man["niveaux"]}
    crier(f"   résolution temporelle : 20 m → {res[20]} min · "
          f"500 m → {res[500]} min · 1000 m → {res[1000]} min · "
          f"3000 m → {res[3000]} min")

    nj, ni = man["axes"]["nb_lat"], man["axes"]["nb_lon"]
    tr_c = man["service"]["carte"]["tranches"]
    tr_k = man["service"]["colonnes"]["tranches"]
    pas_e = man["service"]["carte"]["octets_par_echeance"]
    pas_k = man["service"]["colonnes"]["octets_par_colonne"]
    nlev = len(man["niveaux_m_sol"])
    nech = len(man["echeances_min"])

    pires = []
    for (j, i) in ((0, 0), (nj // 2, ni // 3), (nj - 1, ni - 1)):
        col = st.get_range(c_colonnes, (j * ni + i) * pas_k, pas_k)
        for nom in ("u", "v"):
            a_col = np.frombuffer(
                col, dtype="<f2", offset=tr_k[nom]["offset"],
                count=nlev * nech).reshape(nlev, nech)
            for ie in (0, nech // 2, nech - 1):
                for il in (0, nlev // 2, nlev - 1):
                    o = (ie * pas_e + tr_c[nom]["offset"]
                         + (il * nj * ni + j * ni + i) * 2)
                    v = np.frombuffer(st.get_range(c_carte, o, 2),
                                      dtype="<f2")[0]
                    pires.append(abs(float(v) - float(a_col[il, ie])))
    pire = max(pires) if pires else 0.0
    crier(f"   ⛔ les deux jumeaux, {len(pires)} cases confrontées : écart "
          f"max {pire:.3e} m/s")
    if pire != 0.0:
        crier("   ⛔ ILS DIVERGENT — le calque et la coupe montreraient "
              "deux vents différents au même instant.")
        return 1
    crier("   ✅ identiques à l'octet près.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
