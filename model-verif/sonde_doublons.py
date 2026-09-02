#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/sonde_doublons.py — COMBIEN DE FOIS NOTE-T-ON LE MÊME
#  VENT ?                                          (Lot L16, 27/08/2026)
#
#  PONCTUELLE, LECTURE SEULE. Aucune écriture, aucun SQL, aucun
#  déploiement. Elle lit les archives d'observation et la base de
#  production, et rend un rapport.
#
#  ═══ D'OÙ VIENT CETTE SONDE ═══
#
#  Le lot L6 (plancher de représentativité) cherchait des paires de
#  balises PROCHES pour estimer combien de l'erreur est irréductible.
#  Il en a trouvé 1 179 à moins de 3 km — et **346 d'entre elles, 29 %,
#  étaient à moins de 100 m**, c'est-à-dire au même point :
#  270 `pioupiou` ↔ `windsmobi/ffvl` (0,475 km/h d'écart médian),
#  47 `metar` ↔ `mf`. Plus 17 autres au-delà de 100 m, que les deux
#  référentiels placent à des coordonnées différentes
#  (`pioupiou:1494` ↔ `windsmobi:ffvl-3494` : 111 m d'écart archivé,
#  0,30 km/h d'accord sur 144 heures).
#
#  Ce n'était pas le sujet du L6, et c'est peut-être plus grave que son
#  sujet. La clé de `model_verif_daily` est
#  `(day, source, station_id, model, lead_h, fcst_src)` : pour la base,
#  ces balises sont **deux balise-jours INDÉPENDANTS**. Or trois
#  dispositifs supposent cette indépendance, et aucun ne peut la
#  vérifier lui-même :
#
#    · le BOOTSTRAP PAR BLOCS DE JOURS (lot G) rééchantillonne les
#      jours ; deux valeurs corrélées DANS un jour rétrécissent
#      l'intervalle sans que rien ne le dise ;
#    · BENJAMINI-HOCHBERG (lot L3) compte des cases `m` et suppose des
#      tests dont la corrélation est POSITIVE mais pas l'identité ;
#    · le DUEL APPARIÉ (lot L1) apparie sur `(unit, day)` : deux
#      inscriptions du même capteur font deux paires au lieu d'une.
#
#  Et un quatrième, plus brutal : `MIN_STATIONS_ZONE = 3`. Une case qui
#  n'a que deux vraies balises et un doublon est publiée sur la foi
#  d'une troisième station qui n'existe pas.
#
#  ═══ CE QUE CETTE SONDE MESURE, ET DANS QUEL ORDRE ═══
#
#    PASSE 1 — LE GRAPHE. Quelles balises sont la même balise, et
#              combien. Le seuil de décision se LIT dans la
#              distribution, il ne se pose pas d'avance.
#    PASSE 2 — LA RÈGLE. Laquelle des deux (ou des trois) garde le
#              billet. Chaque critère est CHIFFRÉ, aucun supposé.
#    PASSE 3 — LE DÉGÂT. La nuit rejouée DEUX FOIS — avec et sans les
#              doublons — par `score._case_rows`, la fonction de
#              production elle-même. Ce qui change est mesuré ligne à
#              ligne : cases, rangs, `n`, `m` de BH, podiums.
#
#  ⛔ L'ORDRE COMPTE. Mesurer le dégât avant d'avoir fixé la règle
#  obligerait à choisir un représentant au hasard, et « au hasard »
#  n'est pas reproductible : le même rapport rendrait deux chiffres
#  différents à deux exécutions.
#
#  ═══ TROIS PREUVES, JAMAIS FONDUES ═══
#
#    (a) GÉOMÉTRIQUE — la distance entre les coordonnées ARCHIVÉES.
#        Elle ne suffit pas : les deux référentiels se contredisent
#        (le L4 l'a mesuré entre `agrume` et `arome_r2` : 160 balises
#        sur 285 n'ont pas la même coordonnée des deux côtés, jusqu'à
#        147 km).
#    (b) PHYSIQUE — l'accord des deux séries sur les heures communes.
#        Elle ne suffit pas non plus : deux balises VRAIMENT voisines
#        s'accordent bien, et les jeter sur leur accord serait
#        circulaire.
#    (c) NOMINALE — le motif d'identifiant (`pioupiou:1494` /
#        `windsmobi:ffvl-3494`). ⛔ ELLE N'EST JAMAIS UN CRITÈRE, et
#        c'est important : elle ne trouverait que les doublons qui ont
#        la politesse de partager une convention de nommage, et
#        laisserait passer tous les autres en donnant l'impression
#        d'avoir cherché. Elle sert de CORROBORATION, elle est comptée
#        à part, et le rapport dit combien de doublons elle RATE.
#
#  Le critère est (a) ET (b). Le seuil de chacun est lu dans le tableau
#  croisé distance × accord que la sonde publie AVANT de trancher.
#
#  ═══ CE QUE CETTE SONDE NE FAIT PAS ═══
#
#  ⛔ Elle ne corrige rien. Elle ne propose pas de `.sql`. Elle ne
#  touche ni `collect.py`, ni `score.py`, ni la base. Le geste de
#  fermeture dépend de ce qu'elle mesure — et il y a au moins trois
#  gestes possibles, de coûts très différents (voir la fin du rapport).
#  ⛔ Elle ne dit pas laquelle des deux séries est la plus JUSTE. Elle
#  dit laquelle est la plus UTILE au dispositif, ce qui n'est pas la
#  même question. Quand les deux séries divergent franchement au même
#  point, ce n'est plus un doublon : c'est un défaut de référentiel, et
#  elle le range ailleurs.
#
#  ═══ USAGE ═══
#
#      # sur le VPS (les archives obs n'existent que là)
#      ssh debian@51.91.102.146
#      cd ~/balise-watch/balise-watch-server/model-verif
#      set -a && . ~/.balise-watch-model-verif.env && set +a
#      ~/venv-balise/bin/python3 sonde_doublons.py --jours 21
#
#      python3 sonde_doublons.py --sans-score   # passe 1 et 2 seules
#      python3 sonde_doublons.py --json
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import os
import pathlib
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import score as SC                         # noqa: E402
import scoring as S                        # noqa: E402
import sonde_representativite as SR        # noqa: E402


# ══════════════════════════════════════════════════════════════════
#  CONSTANTES — les seuils sont LUS dans la distribution, pas posés
# ══════════════════════════════════════════════════════════════════

#: Le rayon de RECHERCHE. Plus large que le seuil de décision, et
#: exprès : c'est ce qui permet de VOIR où s'arrête la population des
#: doublons au lieu de le décréter. Le L6 a mesuré que les
#: republications connues vivent toutes sous 0,3 km ; on cherche
#: jusqu'à trois fois plus loin pour que le tableau croisé montre le
#: vide entre les deux populations — s'il y en a un.
RAYON_RECHERCHE_KM = 1.0

#: Le seuil GÉOMÉTRIQUE de décision. Deux référentiels qui décrivent le
#: même mât ne s'accordent pas au mètre : `pioupiou:1494` et
#: `windsmobi:ffvl-3494` sont archivés à 111 m l'un de l'autre. 300 m
#: laisse la place à cette imprécision sans atteindre la distance à
#: laquelle deux décollages distincts d'un même site commencent
#: (mesurée au L6 : le plancher a déjà 3,0 km/h à 0,3-0,8 km).
SEUIL_DIST_KM = 0.3

#: Le seuil PHYSIQUE. 1,0 km/h d'écart MÉDIAN sur les heures communes.
#: ⚠️ Ce n'est pas « les deux séries se ressemblent » : au L6, deux
#: balises à 300-800 m d'un même site diffèrent de 4,25 km/h médian
#: (plancher 3,005 × √2). Un mètre-ruban de 1 km/h est donc à un
#: facteur QUATRE de ce que fait un vrai voisinage — c'est ce facteur
#: qui rend le critère utilisable, pas la valeur ronde.
SEUIL_ECART_KMH = 1.0

#: Sous ce nombre d'heures communes, on ne tranche pas : la paire est
#: rangée « indécidable » et comptée. Une médiane sur 20 heures ne dit
#: pas si deux capteurs sont le même.
MIN_HEURES_VERDICT = 120

#: Les bandes du tableau croisé qui sert à LIRE les seuils.
BANDES_DIST = (0.05, 0.15, 0.3, 0.5, 1.0)
BANDES_ECART = (0.5, 1.0, 2.0, 4.0)

#: La source que `agrume_fcst.SOURCE_NOTEE` note, et la seule. Retirer
#: une balise `pioupiou` du classement retirerait aussi la série
#: `agrume`/`agrume_pi` de sa case : c'est tout le chantier qui
#: s'éteindrait à cet endroit. Ce n'est donc pas une préférence, c'est
#: une contrainte, et elle passe avant les autres critères.
SOURCE_AGRUME = "pioupiou"

DAY_MS = 24 * 3600 * 1000

CACHE_DAILY = os.path.join(os.path.expanduser("~"), ".sonde_doublons_daily.ndjson")
CACHE_ZONES = os.path.join(os.path.expanduser("~"), ".sonde_doublons_zones.json")


# ══════════════════════════════════════════════════════════════════
#  UNION-FIND — parce qu'une balise peut vivre dans TROIS réseaux
# ══════════════════════════════════════════════════════════════════

class Composantes:
    """Les classes d'équivalence « c'est la même balise ».

    ⛔ POURQUOI PAS UNE SIMPLE LISTE DE PAIRES. `metar:LSMP`,
    `windsmobi:meteoswiss-PAY` et `mf:…` peuvent décrire le même mât :
    trois inscriptions, trois paires, UNE balise. Traiter les paires
    indépendamment garderait deux représentants sur trois et laisserait
    le double comptage en place, tout en affichant « doublons traités ».
    La transitivité n'est pas un raffinement, c'est le sujet.

    ⚠️ Et la transitivité PEUT abusivement fusionner : A≡B et B≡C
    n'implique pas A≡C quand les seuils sont serrés. La sonde publie
    donc la taille des composantes et le DIAMÈTRE géométrique de
    chacune — une composante large est à relire à la main, pas à
    croire.
    """

    def __init__(self):
        self.parent: dict = {}

    def _racine(self, x):
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def unir(self, a, b):
        ra, rb = self._racine(a), self._racine(b)
        if ra != rb:
            # Racine stable (la plus petite en ordre lexical) — pour que
            # la STRUCTURE interne soit la même à chaque exécution, ce
            # qui aide à débuguer.
            # ⚠️ CE N'EST PAS CE QUI REND LE RÉSULTAT REPRODUCTIBLE, et
            # le commentaire précédent le prétendait. Une mutation qui
            # retirait ce `if` est restée VERTE : la reproductibilité
            # vient du `sorted()` de `groupes()`, pas d'ici. Un
            # commentaire qui s'attribue une garantie tenue ailleurs
            # fait chercher au mauvais endroit le jour où elle tombe.
            if rb < ra:
                ra, rb = rb, ra
            self.parent[rb] = ra

    def groupes(self) -> list:
        """⭐ LES DEUX `sorted` SONT LA GARANTIE DE REPRODUCTIBILITÉ, et
        c'est ici qu'elle vit — pas dans `unir`. Sans eux, l'ordre des
        membres suit l'itération d'un `set` et l'ordre des composantes
        celui d'un `dict` : deux exécutions rendraient les mêmes
        composantes écrites différemment, et le représentant choisi par
        `choisir` (qui départage à l'ordre lexical) pourrait changer."""
        out: dict = defaultdict(set)
        for x in self.parent:
            out[self._racine(x)].add(x)
        return [sorted(v) for _k, v in sorted(out.items())]


def bande(x, bornes) -> str:
    for haut in bornes:
        if x <= haut:
            return f"≤ {haut:g}"
    return f"> {bornes[-1]:g}"


def etiquettes(bornes) -> list:
    """Les étiquettes d'un axe, dans l'ordre, une par bande et une seule.

    ⛔ LA MÊME FAUTE QUE LE LOT L6, DANS UN AUTRE FICHIER, LE MÊME JOUR.
    On est tenté de fabriquer ces étiquettes en appelant `bande()` sur
    les BORNES. Mais `bande` range sur `x <= haut` : `bande(0.05)` rend
    « ≤ 0.05 » exactement comme `bande(0.0)`, si bien que la PREMIÈRE
    bande sort deux fois et que la DERNIÈRE bande finie ne sort pas du
    tout. Vu à l'écran le 27/08 sur la première exécution réelle : deux
    lignes « ≤ 0.05 » identiques, et la colonne « ≤ 4 » absente d'un
    tableau qui avait l'air complet.
    ⇒ Les étiquettes se dérivent des BORNES, jamais de la fonction de
    rangement appliquée à ses propres frontières.
    """
    return [f"≤ {b:g}" for b in bornes] + [f"> {bornes[-1]:g}"]


def suffixe_commun(a: str, b: str) -> str | None:
    """La corroboration NOMINALE : le plus long suffixe de chiffres
    partagé par les deux identifiants, s'il fait au moins trois signes.

    `pioupiou:1494` / `windsmobi:ffvl-3494` → « 494 ».

    ⛔ CE N'EST JAMAIS UN CRITÈRE DE DÉCISION. Un identifiant qui finit
    par 494 des deux côtés est une COÏNCIDENCE dans un cas sur mille, et
    une preuve dans les autres — sauf qu'on ne sait pas lequel est
    lequel, et qu'il y a des milliers de paires. Ce que ce signal sert à
    faire, c'est mesurer combien de doublons il RATE : s'il en rate la
    moitié, alors une déduplication écrite à la main sur les
    identifiants en raterait autant.
    """
    da = "".join(c for c in a.split(":", 1)[-1] if c.isdigit())
    db = "".join(c for c in b.split(":", 1)[-1] if c.isdigit())
    n = 0
    while n < min(len(da), len(db)) and da[-1 - n] == db[-1 - n]:
        n += 1
    return da[-n:] if n >= 3 else None


# ══════════════════════════════════════════════════════════════════
#  PASSE 1 — LE GRAPHE : qui est la même balise que qui
# ══════════════════════════════════════════════════════════════════

#: Au-delà de cet écart AU MÊME POINT, ce n'est plus un doublon : c'est
#: un défaut de référentiel. Deux inscriptions qui se disent au même
#: mètre et mesurent des vents qui diffèrent de plus de ça ne peuvent
#: pas être le même capteur — l'une des deux coordonnées est fausse.
#: (Mesuré au L6 : `infoclimat:STATIC0022` ≡ `STATIC0491`, 0,000 km,
#: 11,4 km/h d'écart médian.)
SEUIL_INCOMPATIBLE_KMH = 4.0

VERDICTS = ("doublon", "doublon_probable", "meme_point_incompatible",
            "voisin", "indecidable")

#: Les verdicts qui font retirer une inscription, en lecture ÉTROITE et
#: en lecture LARGE. Le rapport publie le dégât pour les deux : le vrai
#: chiffre est entre les deux, exactement comme le minorant et le
#: majorant du plancher au lot L6.
RETENUS_ETROIT = ("doublon",)
RETENUS_LARGE = ("doublon", "doublon_probable")


def verdict_paire(dist_km: float, ecart: float | None, n_heures: int) -> str:
    """Le verdict d'une paire — cinq issues, jamais deux.

    ⛔ IL N'Y A PAS DE « VOISIN » À DISTANCE NULLE, et c'est le
    correctif de la première exécution réelle (27/08). Deux inscriptions
    que les deux référentiels placent au même mètre sont soit le même
    capteur, soit une coordonnée fausse — jamais deux balises voisines.
    La première version rangeait « voisin » tout ce qui, au même point,
    s'accordait entre 1 et 4 km/h : c'est-à-dire **les 47 paires
    `metar` ↔ `mf`**, deux flux du même mât d'aérodrome dont l'écart
    médian vaut 2,1 km/h parce que le METAR est publié en NŒUDS ENTIERS
    (1,852 km/h de quantum) sur une moyenne de dix minutes. Elles
    étaient donc gardées toutes les deux, sous une étiquette qui disait
    l'inverse de ce qu'elles sont.

    Au même point, l'écart se lit donc en trois tranches :
      ≤ SEUIL_ECART        → `doublon` — le même capteur, c'est sûr ;
      ≤ SEUIL_INCOMPATIBLE → `doublon_probable` — le même capteur vu par
                             deux CHAÎNES (arrondi, fenêtre de
                             moyennage, hauteur de mât) ; on ne le
                             déclare pas d'office, on le compte et on
                             mesure le dégât AVEC et SANS ;
      au-delà              → `meme_point_incompatible` — aucune chaîne
                             ne fabrique 5 km/h d'écart : une des deux
                             coordonnées est fausse.

    ⚠️ « indécidable » N'EST PAS « voisin ». Une paire qu'on n'a pas pu
    juger faute d'heures communes doit se compter comme une INCERTITUDE,
    pas se ranger silencieusement du côté rassurant. Sinon le rapport
    dirait « 340 doublons » là où il faut lire « 340 doublons, et 60
    paires sur lesquelles je ne sais pas ».
    """
    if ecart is None or n_heures < MIN_HEURES_VERDICT:
        return "indecidable"
    if dist_km > SEUIL_DIST_KM:
        return "voisin"
    if ecart > SEUIL_INCOMPATIBLE_KMH:
        return "meme_point_incompatible"
    return "doublon" if ecart <= SEUIL_ECART_KMH else "doublon_probable"


def graphe(root: pathlib.Path, fin: datetime, jours: int,
           rayon: float = RAYON_RECHERCHE_KM, storage=None,
           lecteur=None, crier=print) -> dict:
    """Les paires candidates, leurs trois preuves, et les composantes.

    ⚠️ TOUTE LA LECTURE D'ARCHIVES EST CELLE DU LOT L6 : `paires_proches`
    (le pavage prouvé contre la force brute), `serie_horaire` +
    `pair_series` (l'appariement symétrique), `series_error`
    (l'arithmétique de production). Rien n'est réécrit ici — une seconde
    implémentation de l'appariement serait la première chose à diverger,
    et les deux sondes ne parleraient plus du même écart.
    """
    if lecteur is None:
        def lecteur(d):
            return SC.all_obs_rows(root, d, storage)

    dists: dict = defaultdict(list)
    meds: dict = defaultdict(list)
    heures: dict = defaultdict(int)
    sous_seuil: dict = defaultdict(int)
    reseaux: dict = {}
    jours_lus = 0
    n_lignes = 0
    unites = set()

    for k in range(jours):
        d = fin - timedelta(days=k)
        rows = lecteur(d)
        if not rows:
            continue
        jours_lus += 1
        n_lignes += len(rows)
        jour_ms = int(d.replace(tzinfo=timezone.utc).timestamp()) * 1000
        positions: dict = {}
        echantillons: dict = {}
        for r in rows:
            la, lo = r.get("lat"), r.get("lon")
            if la is None or lo is None:
                continue
            u = SR.unite(r)
            ech = SC.to_obs_samples(r)
            if not ech:
                continue
            positions[u] = (float(la), float(lo))
            echantillons.setdefault(u, []).extend(ech)
            unites.add(u)
            if r.get("network"):
                reseaux[u] = str(r["network"])

        cache: dict = {}
        for a, b, dist in SR.paires_proches(positions, rayon):
            if a not in cache:
                cache[a] = SR.serie_horaire(echantillons[a], jour_ms)
            times, sp, di = cache[a]
            vpairs = S.pair_series(times, sp, di, echantillons[b])
            se = S.series_error(vpairs)
            cle = (a, b)
            dists[cle].append(dist)
            heures[cle] += se.n
            sous_seuil[cle] += sum(1 for e in se.per_hour if abs(e) <= 0.5)
            if se.med is not None and se.n >= SR.MIN_HEURES_PAIRE_JOUR:
                meds[cle].append(se.med)

    # ── LES PAIRES, avec leurs trois preuves ────────────────────────
    paires = []
    for cle, dl in dists.items():
        a, b = cle
        ecart = S.median(meds[cle]) if meds[cle] else None
        d_med = S.median(dl)
        paires.append({
            "a": a, "b": b,
            "dist_km": d_med,
            "dist_min_km": min(dl), "dist_max_km": max(dl),
            "ecart_med": ecart,
            "n_heures": heures[cle], "n_jours": len(meds[cle]),
            "part_accord": (sous_seuil[cle] / heures[cle]) if heures[cle] else 0.0,
            "suffixe": suffixe_commun(a, b),
            "verdict": verdict_paire(d_med, ecart, heures[cle]),
        })
    paires.sort(key=lambda p: (p["verdict"], p["dist_km"]))

    # ── LE TABLEAU CROISÉ : le seuil se LIT ici ─────────────────────
    croise: dict = defaultdict(Counter)
    for p in paires:
        if p["ecart_med"] is None:
            continue
        croise[bande(p["dist_km"], BANDES_DIST)][
            bande(p["ecart_med"], BANDES_ECART)] += 1

    # ── LES COMPOSANTES, en lecture étroite ET en lecture large ─────
    def _composantes(verdicts_retenus) -> list:
        comp = Composantes()
        for p in paires:
            if p["verdict"] in verdicts_retenus:
                comp.unir(p["a"], p["b"])
        out = []
        for membres in comp.groupes():
            diam = 0.0
            for p in paires:
                if p["a"] in membres and p["b"] in membres:
                    diam = max(diam, p["dist_max_km"])
            out.append({
                "membres": membres,
                "taille": len(membres),
                "diametre_km": round(diam, 3),
                "sources": sorted({SR.reseau(u) for u in membres}),
                "fournisseurs": sorted({SR.fournisseur(u, reseaux)
                                        for u in membres}),
            })
        out.sort(key=lambda c: (-c["taille"], c["membres"][0]))
        return out

    composantes = _composantes(RETENUS_ETROIT)
    composantes_larges = _composantes(RETENUS_LARGE)

    compte = Counter(p["verdict"] for p in paires)
    dbl = [p for p in paires if p["verdict"] == "doublon"]
    return {
        "fenetre": {"fin": fin.strftime("%Y-%m-%d"),
                    "jours_demandes": jours, "jours_lus": jours_lus,
                    "lignes_obs": n_lignes, "balises": len(unites),
                    "rayon_km": rayon},
        "seuils": {"dist_km": SEUIL_DIST_KM, "ecart_kmh": SEUIL_ECART_KMH,
                   "incompatible_kmh": SEUIL_INCOMPATIBLE_KMH,
                   "min_heures": MIN_HEURES_VERDICT},
        "compte": dict(compte),
        "croise": {k: dict(v) for k, v in croise.items()},
        "paires": paires,
        "composantes": composantes,
        "composantes_larges": composantes_larges,
        "reseaux": reseaux,
        # ⭐ CE QUE LA PREUVE NOMINALE RATERAIT si on s'y fiait seule.
        "suffixe": {
            "doublons_avec_suffixe": sum(1 for p in dbl if p["suffixe"]),
            "doublons_sans_suffixe": sum(1 for p in dbl if not p["suffixe"]),
            "voisins_avec_suffixe": sum(
                1 for p in paires
                if p["verdict"] == "voisin" and p["suffixe"]),
        },
    }


# ══════════════════════════════════════════════════════════════════
#  PASSE 2 — LA RÈGLE : laquelle des deux garde le billet
# ══════════════════════════════════════════════════════════════════

#: Les critères, DANS L'ORDRE, et ce qu'ils coûtent si on les inverse.
CRITERES = (
    ("agrume", "la source notée par AGRUME (`pioupiou`) — retirer cette "
               "inscription-là retirerait `agrume` et `agrume_pi` de la "
               "case, c'est-à-dire tout l'objet du chantier"),
    ("modeles", "le plus de MODÈLES distincts notés — le groupe complet "
                "(9 modèles + AROME) bat le groupe réduit (5) ; garder le "
                "réduit reviendrait à jeter quatre avis pour en garder un"),
    ("jours", "la meilleure COUVERTURE en balise-jours"),
    ("heures", "la meilleure couverture en heures notées"),
    ("nom", "l'ordre lexical — pour que deux exécutions rendent la MÊME "
            "réponse ; un départage au hasard ferait bouger le classement "
            "d'une nuit à l'autre sans qu'aucune donnée n'ait changé"),
)


def faits_par_unite(daily) -> dict:
    """Ce que la BASE sait de chaque balise — pas ce qu'on en suppose."""
    f: dict = defaultdict(lambda: {"modeles": set(), "jours": set(),
                                   "heures": 0, "leads": set()})
    for r in daily:
        u = f"{r['source']}:{r['station_id']}"
        d = f[u]
        d["modeles"].add(r["model"])
        d["jours"].add(r["day"])
        d["leads"].add(r["lead_h"])
        if r.get("n_hours"):
            d["heures"] += int(r["n_hours"])
    return {u: {"modeles": sorted(v["modeles"]), "n_modeles": len(v["modeles"]),
                "n_jours": len(v["jours"]), "heures": v["heures"],
                "n_leads": len(v["leads"])}
            for u, v in f.items()}


def choisir(membres: list, faits: dict) -> tuple:
    """Le représentant d'une composante, et le critère qui a tranché.

    ⛔ LE PREMIER CRITÈRE N'EST PAS UN JUGEMENT DE QUALITÉ. `pioupiou`
    n'est pas « la meilleure » source : c'est la SEULE que
    `agrume_fcst.SOURCE_NOTEE` note, donc la seule dont le retrait
    ferait disparaître `agrume` et `agrume_pi` de la case. Le jour où
    AGRUME notera d'autres sources (lot L7), ce critère devra être
    RELU — il est daté, pas éternel.
    """
    def cle(u):
        d = faits.get(u) or {"n_modeles": 0, "n_jours": 0, "heures": 0}
        return (0 if SR.reseau(u) == SOURCE_AGRUME else 1,
                -d["n_modeles"], -d["n_jours"], -d["heures"], u)
    tries = sorted(membres, key=cle)
    gagnant = tries[0]
    perdant = tries[1] if len(tries) > 1 else None
    if perdant is None:
        return gagnant, "seul"
    ka, kb = cle(gagnant), cle(perdant)
    for i, (nom, _pourquoi) in enumerate(CRITERES):
        if ka[i] != kb[i]:
            return gagnant, nom
    return gagnant, "nom"


def regle(composantes: list, faits: dict) -> dict:
    """Un représentant par composante, et tout le reste est ÉCARTÉ."""
    gardes, ecartes, detail = [], [], []
    par_critere = Counter()
    for c in composantes:
        g, crit = choisir(c["membres"], faits)
        perdus = [u for u in c["membres"] if u != g]
        gardes.append(g)
        ecartes.extend(perdus)
        par_critere[crit] += 1
        detail.append({
            "garde": g, "ecartes": perdus, "critere": crit,
            "taille": c["taille"], "diametre_km": c["diametre_km"],
            "faits": {u: faits.get(u) for u in c["membres"]},
        })
    return {
        "gardes": sorted(gardes), "ecartes": sorted(ecartes),
        "n_composantes": len(composantes), "n_ecartes": len(ecartes),
        "par_critere": dict(par_critere), "detail": detail,
        # ⚠️ Une balise ÉCARTÉE qui n'apparaît nulle part dans la base
        # ne coûte rien à personne : la compter dans le dégât gonflerait
        # le chiffre sans qu'aucune ligne ne bouge.
        "ecartes_notes": sorted(u for u in ecartes if u in faits),
    }


# ══════════════════════════════════════════════════════════════════
#  PASSE 3 — LE DÉGÂT : la nuit rejouée DEUX FOIS
# ══════════════════════════════════════════════════════════════════

def _podium(rows: list) -> dict:
    """Le vainqueur publié de chaque case (`rank == 1`), s'il existe."""
    out = {}
    for r in rows:
        if r.get("rank") == 1:
            out[SC._cle_de_case(r)] = r["model"]
    return out


def _n_par_case(rows: list) -> dict:
    out: dict = defaultdict(int)
    for r in rows:
        out[SC._cle_de_case(r)] += int(r.get("occurrences") or 0)
    return dict(out)


def rejouer(units: list, zone_of: dict, as_of: datetime, crier=print):
    """`_case_rows` PUIS `appliquer_fdr` — la chaîne de la nuit, entière.

    ⛔ ON APPELLE LA FONCTION DE PRODUCTION, ON N'EN ÉCRIT PAS UNE
    IMITATION. Une réimplémentation « équivalente » du classement
    donnerait un écart avant/après qui mesurerait surtout la différence
    entre les deux implémentations. `_case_rows` avec `with_ci=False`
    est exactement ce que fait `sonde_fdr.py` : le bootstrap UNAIRE est
    sauté (500 tirages par ligne, le poste le plus cher), l'apparié —
    d'où sortent p-valeurs et rangs — ne bouge pas.
    """
    t0 = time.monotonic()
    scores = SC._case_rows(units, zone_of, as_of, "rolling15", "all",
                           SC.MIN_STATIONS_ZONE, with_ci=False)
    bilan_fdr = SC.appliquer_fdr(scores)
    cases = {SC._cle_de_case(r) for r in scores}
    ok = {SC._cle_de_case(r) for r in scores if r.get("rank_reason") == "ok"}
    crier(f"    {len(scores)} lignes · {len(cases)} cases · "
          f"{len(ok)} avec un rang publié · {time.monotonic() - t0:.0f} s")
    return {
        "lignes": len(scores), "cases": cases, "cases_ok": ok,
        "podium": _podium(scores), "n_par_case": _n_par_case(scores),
        "rangs": {(SC._cle_de_case(r), r["model"]): r.get("rank")
                  for r in scores},
        "motifs": dict(Counter(r.get("rank_reason") for r in scores)),
        "fdr": bilan_fdr,
        "stations_par_case": None,
    }


def degat(daily: list, zone_of: dict, ecartes: set, as_of: datetime,
          crier=print) -> dict:
    """Ce que le double comptage change, ligne à ligne."""
    units = []
    for d in daily:
        r = dict(d)
        r["unit"] = f"{d['source']}:{d['station_id']}"
        units.append(r)
    apres_units = [u for u in units if u["unit"] not in ecartes]

    crier("  ▸ la nuit TELLE QU'ELLE EST (doublons compris)")
    av = rejouer(units, zone_of, as_of, crier)
    crier("  ▸ la nuit SANS les doublons (un représentant par balise)")
    ap = rejouer(apres_units, zone_of, as_of, crier)

    # ── ⭐ LE CONTRÔLE DU CÂBLAGE (lot L17) ─────────────────────────
    # Les deux passes ci-dessus retirent les doublons EN AMONT, à la
    # main. La production, elle, les retirera par la COLONNE
    # `station_zone.doublon_de`, lue par `score.est_doublon` au fond de
    # `_case_rows`. Ce sont deux chemins différents vers le même
    # résultat — et deux chemins qui doivent rendre le MÊME objet.
    #
    # ⛔ POURQUOI CE CONTRÔLE VAUT PLUS QUE LE BANC. Le banc joue sur
    # cinq balises fabriquées ; ici on rejoue la nuit RÉELLE, 298 122
    # balise-jours, par le code qui tournera. Un `continue` mal placé,
    # une colonne mal nommée, une exclusion qui laisserait passer les
    # échelons agrégés : rien de tout ça ne rougit sur cinq balises.
    zone_colonne = {u: dict(z) for u, z in zone_of.items()}
    for u in ecartes:
        if u in zone_colonne:
            zone_colonne[u][SC.COL_DOUBLON] = "(peu importe qui)"
    crier("  ▸ la MÊME nuit, mais retirée par la COLONNE `doublon_de`")
    # ⛔ ET ON CAPTURE LE JOURNAL DE CETTE PASSE-LÀ. Sans ça, le
    # contrôle « les deux chemins s'accordent » se satisfait d'un
    # troisième rejeu qui n'aurait jamais lu la colonne : deux passes
    # identiques s'accordent toujours, et le contrôle passerait au vert
    # en ne contrôlant rien. Le journal de `_case_rows` est la seule
    # preuve que `score.est_doublon` a VU quelque chose.
    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon):
        ap2 = rejouer(units, zone_colonne, as_of, lambda *_a, **_k: None)
    journal = tampon.getvalue()
    crier(journal.rstrip() or "    (aucun journal)")
    vus = 0
    for ligne in journal.splitlines():
        m = re.search(r"(\d+) balise-jour\(s\) écarté\(s\)", ligne)
        if m and SC.COL_DOUBLON in ligne:
            vus = int(m.group(1))
    accord = {
        "colonne_lue": vus > 0,
        "lignes": ap["lignes"] == ap2["lignes"],
        "cases": ap["cases"] == ap2["cases"],
        "cases_ok": ap["cases_ok"] == ap2["cases_ok"],
        "podium": ap["podium"] == ap2["podium"],
        "n_par_case": ap["n_par_case"] == ap2["n_par_case"],
        "motifs": ap["motifs"] == ap2["motifs"],
    }
    crier(f"    → la colonne a écarté {vus} balise-jour(s) "
          f"(le pré-filtre en retirait {len(units) - len(apres_units)} : "
          f"l'écart est ce qui était DÉJÀ exclu pour une autre raison)")
    # ⚠️ LE NOMBRE DE CONTRÔLES EST COMPTÉ, PAS ÉCRIT. Une phrase qui
    # dit « six » pendant qu'on en ajoute un septième est un
    # commentaire qui ment — et il ment d'autant mieux qu'il a été vrai.
    crier("    → les deux chemins s'accordent : "
          + (f"OUI, sur les {len(accord)} contrôles" if all(accord.values())
             else "⛔ NON — " + ", ".join(k for k, v in accord.items()
                                          if not v)))

    perdues = av["cases"] - ap["cases"]
    perdues_ok = av["cases_ok"] - ap["cases_ok"]
    gagnees_ok = ap["cases_ok"] - av["cases_ok"]
    communes = av["cases"] & ap["cases"]
    podium_change = sorted(
        {c for c in communes
         if av["podium"].get(c) != ap["podium"].get(c)})
    rangs_changes = sum(
        1 for k, v in av["rangs"].items()
        if k[0] in communes and ap["rangs"].get(k) != v)

    # ── L'INFLATION DE `n`, là où elle a lieu ───────────────────────
    infl = []
    for c in sorted(communes):
        na, nb = av["n_par_case"].get(c, 0), ap["n_par_case"].get(c, 0)
        if na > nb:
            infl.append({"case": list(c), "n_avant": na, "n_apres": nb,
                         "inflation": (na - nb) / nb if nb else None})
    infl.sort(key=lambda x: -(x["inflation"] or 0))

    return {
        "cablage_l17": accord,
        "balise_jours": {"avant": len(units), "apres": len(apres_units),
                         "retires": len(units) - len(apres_units)},
        "avant": {k: v for k, v in av.items()
                  if k in ("lignes", "motifs", "fdr")},
        "apres": {k: v for k, v in ap.items()
                  if k in ("lignes", "motifs", "fdr")},
        "cases": {"avant": len(av["cases"]), "apres": len(ap["cases"]),
                  "perdues": sorted(list(c) for c in perdues)},
        "cases_ok": {"avant": len(av["cases_ok"]), "apres": len(ap["cases_ok"]),
                     "perdues": sorted(list(c) for c in perdues_ok),
                     "gagnees": sorted(list(c) for c in gagnees_ok)},
        "podium_change": [list(c) for c in podium_change],
        "podium_change_detail": [
            {"case": list(c), "avant": av["podium"].get(c),
             "apres": ap["podium"].get(c)} for c in podium_change[:20]],
        "rangs_changes": rangs_changes,
        "cases_touchees": len(infl),
        "inflation": infl[:20],
        "inflation_mediane": S.median(
            [x["inflation"] for x in infl if x["inflation"] is not None]),
    }


def degat_duel(daily: list, ecartes: set, crier=print) -> dict:
    """Le duel apparié du lot L1, rejoué avec et sans les doublons.

    ⓘ `DUEL_SOURCE = "pioupiou"` : seuls les doublons INTERNES à
    Pioupiou peuvent le toucher. Les 270 paires
    `pioupiou` ↔ `windsmobi/ffvl` n'y changent rien — la règle garde
    `pioupiou` des deux côtés. C'est une bonne nouvelle qui ne se
    devine pas : elle se mesure, et si elle était fausse, elle le
    serait en silence.
    ⚠️ La fenêtre lue ici est celle du glissant (15 j), pas les 30 j du
    duel nocturne : ce sont les DIFFÉRENCES avant/après qui se lisent,
    pas les valeurs absolues.
    """
    try:
        import duel as DUEL                       # noqa: PLC0415
    except Exception as e:                        # noqa: BLE001
        crier(f"  ⚠️ duel illisible ({type(e).__name__})")
        return {}
    apres = [r for r in daily
             if f"{r['source']}:{r['station_id']}" not in ecartes]
    av = DUEL.duels(daily)
    ap = DUEL.duels(apres)
    return {"avant": av, "apres": ap,
            "lignes": [{"paire": f"{a['model_a']} ↔ {a['model_b']}",
                        "n_avant": a["n_pairs"], "n_apres": b["n_pairs"],
                        "med_avant": a["median_diff"],
                        "med_apres": b["median_diff"],
                        "verdict_avant": a["verdict"],
                        "verdict_apres": b["verdict"]}
                       for a, b in zip(av, ap)]}


# ══════════════════════════════════════════════════════════════════
#  LE RAPPORT
# ══════════════════════════════════════════════════════════════════

def _f(x, n=3):
    return "—" if x is None else f"{x:.{n}f}"


def rapport(g: dict, regles: dict, degats: dict | None, du: dict | None,
            faits: dict) -> str:
    """`regles` et `degats` portent DEUX lectures : « etroit » (les
    doublons certains) et « large » (+ les probables). Le rapport les
    publie côte à côte — le vrai chiffre est entre les deux, et ne pas
    choisir est ici la seule honnêteté possible."""
    r = regles["etroit"]
    L = []
    A = L.append
    f = g["fenetre"]
    s = g["seuils"]
    A("═" * 72)
    A("  COMBIEN DE FOIS NOTE-T-ON LE MÊME VENT ?")
    A("  Déduplication des réseaux d'observation            (lot L16)")
    A("═" * 72)
    A(f"  fenêtre  : {f['jours_lus']} journée(s) sur {f['jours_demandes']}, "
      f"fin {f['fin']} · {f['lignes_obs']} lignes d'obs · "
      f"{f['balises']} balises")
    A(f"  recherche: toutes les paires à moins de {f['rayon_km']} km")
    A(f"  seuils   : doublon si distance ≤ {s['dist_km']} km ET écart "
      f"médian ≤ {s['ecart_kmh']} km/h,")
    A(f"             sur au moins {s['min_heures']} heures communes ; "
      f"au-delà de {s['incompatible_kmh']} km/h")
    A("             au même point, ce n'est plus un doublon mais un "
      "défaut de référentiel.")

    A("")
    A("── 1. OÙ LE SEUIL SE LIT — distance × accord, toutes les paires ───")
    cols = etiquettes(BANDES_ECART)
    A("  {:<12}".format("dist \\ écart") + "".join(f"{c:>10}" for c in cols))
    for bd in etiquettes(BANDES_DIST):
        ligne = g["croise"].get(bd)
        if not ligne:
            continue
        A("  {:<12}".format(bd)
          + "".join(f"{ligne.get(c, 0):>10}" for c in cols))
    A("  ⭐ C'EST CE TABLEAU QUI JUSTIFIE LES SEUILS, pas l'inverse. Si")
    A("     les doublons existent, ils forment un AMAS en haut à gauche")
    A("     (proches ET d'accord), séparé du reste par du vide. Si le")
    A("     tableau est continu, aucun seuil n'est défendable et il faut")
    A("     le dire au lieu d'en choisir un.")

    A("")
    A("── 2. LE VERDICT DES PAIRES ───────────────────────────────────────")
    for v in VERDICTS:
        A(f"  {v:<28} {g['compte'].get(v, 0):>6}")
    for nom, cle in (("ÉTROITE (doublons certains)", "composantes"),
                     ("LARGE (+ doublons probables)", "composantes_larges")):
        comps = g[cle]
        tailles = Counter(c["taille"] for c in comps)
        rr = regles["etroit" if cle == "composantes" else "large"]
        A(f"  → lecture {nom} : {len(comps)} composantes "
          f"({' · '.join(f'{n} de taille {t}' for t, n in sorted(tailles.items()))})"
          f" · {rr['n_ecartes']} inscriptions en trop, dont "
          f"{len(rr['ecartes_notes'])} vues en base")
    comps = g["composantes"]
    grosses = [c for c in comps if c["taille"] > 2]
    if grosses:
        A("  ⚠️ composantes de plus de deux membres — à relire à la main,")
        A("     la transitivité peut fusionner abusivement :")
        for c in grosses[:8]:
            A(f"     {' ≡ '.join(c['membres'])}  (diamètre "
              f"{c['diametre_km']} km)")

    A("")
    A("── 3. CE QUE LA PREUVE NOMINALE RATERAIT ──────────────────────────")
    sx = g["suffixe"]
    tot = sx["doublons_avec_suffixe"] + sx["doublons_sans_suffixe"]
    A(f"  doublons dont les identifiants partagent un suffixe de "
      f"chiffres : {sx['doublons_avec_suffixe']} / {tot}")
    if tot:
        A(f"  ⛔ une déduplication écrite À LA MAIN sur les identifiants "
          f"en raterait {sx['doublons_sans_suffixe']} "
          f"({100 * sx['doublons_sans_suffixe'] / tot:.0f} %) — et elle")
        A(f"     ramasserait au passage {sx['voisins_avec_suffixe']} "
          f"VRAIS voisins qui partagent un suffixe par hasard.")

    incompat = [p for p in g["paires"]
                if p["verdict"] == "meme_point_incompatible"]
    if incompat:
        A("")
        A("── 4. MÊME POINT, VENTS INCOMPATIBLES — pas des doublons ──────────")
        A("  Une des deux coordonnées est fausse. Ces paires ne sont NI")
        A("  dédupliquées NI comptées comme voisins : elles vont au L15.")
        for p in sorted(incompat, key=lambda x: -(x["ecart_med"] or 0))[:12]:
            A(f"    {p['a']:<28} ≡ {p['b']:<28} {p['dist_km']:>6.3f} km "
              f"{p['ecart_med']:>7.2f} km/h  {p['n_heures']} h")

    A("")
    A("── 5. LA RÈGLE — qui garde le billet, et POURQUOI ─────────────────")
    for nom, pourquoi in CRITERES:
        n = r["par_critere"].get(nom, 0)
        A(f"  {nom:<10} {n:>5} composante(s)")
        for ligne in _plier(pourquoi, 62):
            A(f"             {ligne}")
    A("")
    A("  {:<30} {:<30} {:>9}".format("gardée", "écartée", "critère"))
    for e in r["detail"][:25]:
        for perdu in e["ecartes"]:
            fg = faits.get(e["garde"]) or {}
            fp = faits.get(perdu) or {}
            A("  {:<30} {:<30} {:>9}".format(e["garde"], perdu, e["critere"]))
            A("      modèles {} vs {} · jours {} vs {} · heures {} vs {}"
              .format(fg.get("n_modeles", "—"), fp.get("n_modeles", "—"),
                      fg.get("n_jours", "—"), fp.get("n_jours", "—"),
                      fg.get("heures", "—"), fp.get("heures", "—")))
    if len(r["detail"]) > 25:
        A(f"  … et {len(r['detail']) - 25} autres composantes "
          f"(toutes dans le JSON).")
    return "\n".join(L) + ("\n" + _rapport_degat(degats, du)
                            if degats else "")


def _plier(texte: str, largeur: int) -> list:
    mots, ligne, out = texte.split(), "", []
    for m in mots:
        if len(ligne) + len(m) + 1 > largeur:
            out.append(ligne)
            ligne = m
        else:
            ligne = f"{ligne} {m}".strip()
    if ligne:
        out.append(ligne)
    return out


def _rapport_degat(degats: dict, du: dict | None) -> str:
    L = []
    A = L.append
    A("")
    A("── 6. LE DÉGÂT — la nuit rejouée par `_case_rows`, deux lectures ──")
    A("  {:<44} {:>12} {:>12}".format("", "ÉTROITE", "LARGE"))
    de, dl = degats["etroit"], degats["large"]

    def _duo(label, va, vb, fmt="{}"):
        A("  {:<44} {:>12} {:>12}".format(label, fmt.format(va),
                                          fmt.format(vb)))
    _duo("balise-jours retirés", de["balise_jours"]["retires"],
         dl["balise_jours"]["retires"])
    _duo("… soit", 100 * de["balise_jours"]["retires"] / de["balise_jours"]["avant"],
         100 * dl["balise_jours"]["retires"] / dl["balise_jours"]["avant"],
         "{:.2f} %")
    _duo("cases publiées (avant → après)",
         f"{de['cases']['avant']}→{de['cases']['apres']}",
         f"{dl['cases']['avant']}→{dl['cases']['apres']}")
    _duo("cases qui DISPARAISSENT", len(de["cases"]["perdues"]),
         len(dl["cases"]["perdues"]))
    _duo("cases AVEC un rang publié",
         f"{de['cases_ok']['avant']}→{de['cases_ok']['apres']}",
         f"{dl['cases_ok']['avant']}→{dl['cases_ok']['apres']}")
    _duo("⭐ podiums qui CHANGENT", len(de["podium_change"]),
         len(dl["podium_change"]))
    _duo("rangs individuels qui changent", de["rangs_changes"],
         dl["rangs_changes"])
    _duo("cases dont le `n` était gonflé", de["cases_touchees"],
         dl["cases_touchees"])
    _duo("inflation médiane de `n`",
         100 * (de["inflation_mediane"] or 0),
         100 * (dl["inflation_mediane"] or 0), "{:.1f} %")
    A("")
    for nom, dd in (("ÉTROITE", de), ("LARGE", dl)):
        acc = dd.get("cablage_l17") or {}
        A(f"  ⭐ CÂBLAGE L17 ({nom}) — la même nuit retirée par la COLONNE")
        A("     `station_zone.doublon_de`, c'est-à-dire par le code qui")
        A("     tournera : "
          + (f"les deux chemins s'accordent sur les {len(acc)} contrôles."
             if acc and all(acc.values())
             else "⛔ DÉSACCORD sur " + ", ".join(
                 k for k, v in acc.items() if not v) if acc
             else "non mesuré."))
    A("")
    A("  ⛔ LES DEUX COLONNES SONT UN ENCADREMENT, PAS UN CHOIX. La")
    A("     lecture étroite ne retire que ce dont on est SÛR ; la large")
    A("     ajoute les paires au même point dont l'écart s'explique par")
    A("     la chaîne (arrondi en nœuds, fenêtre de moyennage). Le vrai")
    A("     dégât est entre les deux, et publier une seule des deux")
    A("     colonnes serait choisir sans le dire.")
    A("")
    A("  ── le détail de la lecture LARGE ────────────────────────────")
    d = dl
    bj = d["balise_jours"]
    A(f"  balise-jours : {bj['avant']} → {bj['apres']} "
      f"({bj['retires']} retirés, "
      f"{100 * bj['retires'] / bj['avant']:.2f} %)")
    A(f"  lignes de score : {d['avant']['lignes']} → {d['apres']['lignes']}")
    A(f"  cases           : {d['cases']['avant']} → {d['cases']['apres']}"
      f"  ({len(d['cases']['perdues'])} disparaissent)")
    A(f"  cases AVEC UN RANG PUBLIÉ : {d['cases_ok']['avant']} → "
      f"{d['cases_ok']['apres']}")
    A(f"      {len(d['cases_ok']['perdues'])} perdent leur rang · "
      f"{len(d['cases_ok']['gagnees'])} en gagnent un")
    infl_med = ("—" if d["inflation_mediane"] is None
                else f"{100 * d['inflation_mediane']:.1f} %")
    A(f"  cases dont le `n` était GONFLÉ : {d['cases_touchees']}"
      f"  · inflation médiane {infl_med}")
    A(f"  ⭐ PODIUMS QUI CHANGENT : {len(d['podium_change'])}")
    for e in d["podium_change_detail"][:12]:
        z, lead, wk, reg, lvl = e["case"]
        A(f"     {z}/+{lead}h [{lvl}] : {e['avant']} → {e['apres']}")
    A(f"  rangs individuels qui changent : {d['rangs_changes']}")
    A("")
    A("  motifs de `rank_reason`, avant → après :")
    motifs = sorted(set(d["avant"]["motifs"]) | set(d["apres"]["motifs"]),
                    key=lambda k: str(k))
    for m in motifs:
        A(f"    {str(m):<22} {d['avant']['motifs'].get(m, 0):>6} → "
          f"{d['apres']['motifs'].get(m, 0):>6}")
    fa, fp = d["avant"].get("fdr") or {}, d["apres"].get("fdr") or {}
    if fa or fp:
        A("")
        A("  Benjamini-Hochberg (lot L3), avant → après :")
        # ⚠️ `appliquer_fdr` rend un dict PAR FAMILLE (« brut » et
        # « corr »), pas un dict de nombres. Une première version lisait
        # le niveau du dessus et n'imprimait donc RIEN — sans erreur,
        # sans ligne vide visible, juste un titre suivi du néant.
        for fam in sorted(set(fa) | set(fp)):
            ba, bb = fa.get(fam) or {}, fp.get(fam) or {}
            A(f"    famille « {fam} »")
            for k in ("m", "k", "seuil", "retires"):
                if k in ba or k in bb:
                    A(f"      {k:<10} {str(ba.get(k, '—')):>10} → "
                      f"{str(bb.get(k, '—')):>10}")
    if d["inflation"]:
        A("")
        A("  les cases les plus gonflées :")
        A("  {:<40} {:>8} {:>8} {:>8}".format("case", "n avant", "n après", "×"))
        for x in d["inflation"][:12]:
            z, lead, wk, reg, lvl = x["case"]
            A("  {:<40} {:>8} {:>8} {:>7.1f}%".format(
                f"{z}/+{lead}h [{lvl}]", x["n_avant"], x["n_apres"],
                100 * (x["inflation"] or 0)))
    if du and du.get("lignes"):
        A("")
        A("── 7. LE DUEL APPARIÉ (lot L1), avant → après ─────────────────────")
        for l in du["lignes"]:
            A(f"    {l['paire']}")
            A(f"      n {l['n_avant']} → {l['n_apres']} · médiane "
              f"{_f(l['med_avant'], 4)} → {_f(l['med_apres'], 4)} · "
              f"{l['verdict_avant']} → {l['verdict_apres']}")
    return "\n".join(L)


# ══════════════════════════════════════════════════════════════════
#  LE PEUPLEMENT — un `.sql` préparé, jamais exécuté d'ici
# ══════════════════════════════════════════════════════════════════

def _lit(s: str) -> str:
    """Un littéral SQL. Les identifiants viennent de référentiels tiers
    (`ffvl-3494`, `STATIC0022`, `LFBA`) : on ne les recopie pas dans une
    requête sans les échapper, même « parce qu'ils sont propres »."""
    return "'" + str(s).replace("'", "''") + "'"


def sql_peuplement(g: dict, regle_: dict, lecture: str,
                   jour: str) -> str:
    """L'`UPDATE` qui pose `doublon_de`, idempotent ET CONVERGENT.

    ⛔ CONVERGENT VEUT DIRE : après ce fichier, la base porte EXACTEMENT
    la liste mesurée — ni plus, ni moins. Un fichier qui ne ferait
    qu'AJOUTER laisserait en place les doublons d'une mesure précédente
    qui ne sont plus des doublons (une balise déplacée, un réseau qui
    cesse de republier), et personne ne saurait plus lequel des deux
    états la base porte. Le prix à payer est écrit en tête du fichier
    produit : une ligne posée À LA MAIN par Yann serait effacée au
    prochain passage. C'est un prix, pas un détail — mais l'autre
    option, c'est une table dont l'historique est un empilement.

    ⚠️ ET LE REPRÉSENTANT EST REMIS À `null` EXPLICITEMENT. `_case_rows`
    écarte TOUTE ligne dont `doublon_de` est posé : si le représentant
    d'aujourd'hui était l'écarté d'hier, la case perdrait ses DEUX
    inscriptions et se tairait — le contraire du geste. Le `.sql` ne se
    contente donc pas de poser les écartés, il nettoie les gardés.
    """
    ecartes = {}
    for e in regle_["detail"]:
        for perdu in e["ecartes"]:
            ecartes[perdu] = e["garde"]
    preuve = {}
    for pp in g["paires"]:
        preuve[(pp["a"], pp["b"])] = pp
        preuve[(pp["b"], pp["a"])] = pp

    L = []
    A = L.append
    A("-- ═══════════════════════════════════════════════════════════════════")
    A("--  Peuplement de `station_zone.doublon_de` — lot L17")
    A(f"--  PRODUIT PAR model-verif/sonde_doublons.py, lecture « {lecture} »,")
    A(f"--  sur la fenêtre finissant le {jour} "
      f"({g['fenetre']['jours_lus']} journées d'archives,")
    A(f"--  {g['fenetre']['lignes_obs']} lignes d'observation, "
      f"{g['fenetre']['balises']} balises).")
    A("--")
    A("--  ⚠️ À JOUER PAR YANN, DANS L'ÉDITEUR SQL SUPABASE.")
    A("--  ⚠️ `supabase_step55_lot_l17_doublon_de.sql` doit être passé AVANT")
    A("--     (il crée la colonne).")
    A("--")
    A("--  ⛔ CE FICHIER EST CONVERGENT, PAS ADDITIF. Il remet `doublon_de`")
    A("--     à null PARTOUT où la mesure ne le pose pas — y compris sur une")
    A("--     ligne posée à la main. Après lui, la base porte exactement la")
    A("--     liste ci-dessous.")
    A("--")
    A(f"--  Seuils de la mesure : distance ≤ {SEUIL_DIST_KM} km ET écart médian")
    A(f"--  ≤ {SEUIL_ECART_KMH} km/h (lecture étroite), sur ≥ {MIN_HEURES_VERDICT}")
    A("--  heures communes. Lecture « large » : + les paires au même point")
    A(f"--  dont l'écart reste sous {SEUIL_INCOMPATIBLE_KMH} km/h (deux chaînes)")
    A("--  ⇒ voir le rapport du lot L16 pour ce que chaque lecture coûte.")
    A("--")
    A(f"--  {len(ecartes)} inscriptions écartées · "
      f"{regle_['n_composantes']} composantes.")
    A("-- ═══════════════════════════════════════════════════════════════════")
    A("")
    A("begin;")
    A("")
    A("-- 1. La table repart d'une page blanche : voir « convergent » ci-dessus.")
    A("update public.station_zone set doublon_de = null")
    A(" where doublon_de is not null;")
    A("")
    A("-- 2. Les écartés, un par ligne, avec la preuve qui les a désignés.")
    for perdu in sorted(ecartes):
        garde = ecartes[perdu]
        pp = preuve.get((perdu, garde))
        src, sid = perdu.split(":", 1)
        if pp:
            A(f"--    {pp['dist_km']:.3f} km · écart médian "
              f"{pp['ecart_med']:.2f} km/h · {pp['n_heures']} h · "
              f"{pp['n_jours']} j · {pp['verdict']}"
              + (f" · suffixe « {pp['suffixe']} »" if pp["suffixe"] else ""))
        A(f"update public.station_zone set doublon_de = {_lit(garde)}")
        A(f" where source = {_lit(src)} and station_id = {_lit(sid)};")
    A("")
    A("-- 3. ⛔ LE CONTRÔLE QUI DOIT RENDRE ZÉRO, DANS LA MÊME TRANSACTION.")
    A("--    Un représentant qui serait lui-même écarté ferait taire la case")
    A("--    entière au lieu de la dédoublonner.")
    A("select count(*) as representants_eux_memes_ecartes")
    A("  from public.station_zone z")
    A("  join public.station_zone c")
    A("    on c.source || ':' || c.station_id = z.doublon_de")
    A(" where z.doublon_de is not null and c.doublon_de is not null;")
    A("")
    A("-- 4. Et le compte, pour le noter dans le suivi du lot.")
    A("select source, count(*) as doublons")
    A("  from public.station_zone where doublon_de is not null")
    A(" group by source order by doublons desc;")
    A("")
    A("commit;")
    A("")
    return "\n".join(L)


# ══════════════════════════════════════════════════════════════════
#  LECTURE DE LA BASE — étroite, paginée, reprenable
# ══════════════════════════════════════════════════════════════════

#: Les colonnes lues, et rien d'autre. ⚠️ Elles servent TROIS clients :
#: `_case_rows` (le classement), `duel.duels` (`err_vec_rms`) et
#: `faits_par_unite` (`n_hours`). Un `select=*` sur ~300 000 lignes
#: coûterait des minutes de REST pour rien. À tenir à jour avec
#: `sonde_fdr.COLONNES`, dont celle-ci est le sur-ensemble.
COLONNES = ("day,source,station_id,model,lead_h,fcst_src,n_hours,"
            "err_vec_med,err_vec_rms,mse_model,mse_persist,mse_clim,"
            "err_vec_med_corr,mse_model_corr,bias_n_days")


def lire_daily(sb, since: str, cache: str = CACHE_DAILY, crier=print):
    """`model_verif_daily` sur la fenêtre glissante, avec cache disque.

    ⚠️ REPRENABLE, et le cache vit HORS des dossiers de Yann : c'est du
    brouillon de plusieurs dizaines de Mo, pas un livrable. Le supprimer
    est toujours sans conséquence — c'est même le geste à faire quand la
    fenêtre change (`--vider-cache`).
    """
    lignes: list[dict] = []
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as fh:
            lignes = [json.loads(l) for l in fh if l.strip()]
        crier(f"  ⓘ cache : {len(lignes)} ligne(s) déjà lues")
    page = 1000
    t0 = time.monotonic()
    with open(cache, "a", encoding="utf-8") as fh:
        while True:
            deb = len(lignes)
            lot = sb._page(
                f"model_verif_daily?select={COLONNES}&day=gte.{since}"
                f"&order=day,source,station_id,model,lead_h,fcst_src",
                deb, deb + page - 1)
            if not lot:
                break
            for r in lot:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            fh.flush()
            lignes.extend(lot)
            if len(lot) < page:
                break
            if len(lignes) % 20000 < page:
                crier(f"    … {len(lignes)} lignes "
                      f"({time.monotonic() - t0:.0f} s)", flush=True)
    return lignes


# ══════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════

def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Déduplication des réseaux d'observation (lot L16)")
    p.add_argument("--root", default="/var/lib/bw-model-verif")
    p.add_argument("--fin", default=None, help="dernier jour lu (défaut : hier)")
    p.add_argument("--jours", type=int, default=21,
                   help="profondeur des archives obs pour le GRAPHE")
    p.add_argument("--rayon", type=float, default=RAYON_RECHERCHE_KM)
    p.add_argument("--sans-score", action="store_true",
                   help="passes 1 et 2 seules — aucune lecture de la base")
    p.add_argument("--vider-cache", action="store_true")
    p.add_argument("--sql", default=None,
                   help="écrire le .sql de peuplement dans ce fichier "
                        "(PRÉPARÉ, jamais exécuté d'ici)")
    p.add_argument("--sql-lecture", choices=("etroit", "large"),
                   default="etroit",
                   help="quelle lecture le .sql applique (défaut : "
                        "étroite — on ne retire que ce dont on est sûr)")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    fin = (datetime.strptime(a.fin, "%Y-%m-%d") if a.fin
           else datetime.now(timezone.utc).replace(tzinfo=None)
           - timedelta(days=1))
    fin = fin.replace(hour=0, minute=0, second=0, microsecond=0)
    crier = (lambda *_a, **_k: None) if a.json else (
        lambda *x, **k: print(*x, **{kk: vv for kk, vv in k.items()
                                     if kk == "flush"}))

    if a.vider_cache:
        for c in (CACHE_DAILY, CACHE_ZONES):
            if os.path.exists(c):
                os.remove(c)
        crier("  ⓘ caches vidés")

    storage = None
    try:
        import storage as ST                      # noqa: PLC0415
        storage = ST.make_storage()
    except Exception:                             # noqa: BLE001
        storage = None

    crier(f"▶ PASSE 1 — le graphe ({a.jours} j d'archives obs, "
          f"rayon {a.rayon} km)")
    g = graphe(pathlib.Path(a.root), fin, a.jours, a.rayon, storage,
               crier=crier)
    crier(f"  {sum(g['compte'].values())} paires jugées · "
          f"{g['compte'].get('doublon', 0)} doublons · "
          f"{len(g['composantes'])} composantes")

    daily, zone_of, faits = [], {}, {}
    du = None
    if not a.sans_score:
        crier("▶ lecture de la base")
        sb = SC.Supabase()
        as_of = datetime.now(timezone.utc)
        since = (fin - timedelta(days=SC.ROLLING_DAYS - 1)).strftime("%Y-%m-%d")
        if os.path.exists(CACHE_ZONES):
            with open(CACHE_ZONES, encoding="utf-8") as fh:
                zones_raw = json.load(fh)
        else:
            zones_raw = sb.select("station_zone", order="source,station_id")
            with open(CACHE_ZONES, "w", encoding="utf-8") as fh:
                json.dump(zones_raw, fh)
        zone_of = {f"{z['source']}:{z['station_id']}": z for z in zones_raw}
        crier(f"  balises rattachées à une zone : {len(zone_of)}")
        daily = lire_daily(sb, since, crier=crier)
        crier(f"  balise-jours lus depuis {since} : {len(daily)}")
        faits = faits_par_unite(daily)

    crier("▶ PASSE 2 — la règle (lecture étroite ET lecture large)")
    regles = {"etroit": regle(g["composantes"], faits),
              "large": regle(g["composantes_larges"], faits)}
    for nom, rr in regles.items():
        crier(f"  {nom:<7} : {rr['n_composantes']} composantes · "
              f"{rr['n_ecartes']} écartées, dont "
              f"{len(rr['ecartes_notes'])} notées")

    degats = None
    if daily:
        crier("▶ PASSE 3 — le dégât, deux fois deux nuits")
        degats = {}
        for nom, rr in regles.items():
            crier(f"  ══ lecture {nom} ══")
            degats[nom] = degat(daily, zone_of, set(rr["ecartes"]), as_of,
                                crier=crier)
        du = degat_duel(daily, set(regles["large"]["ecartes"]),
                        crier=crier)

    if a.sql:
        # ⛔ ÉCRIT, JAMAIS JOUÉ. Règle du chantier : aucun SQL ne part
        # d'une session de travail. Le fichier est déposé, Yann le lit
        # et l'exécute.
        chemin = pathlib.Path(a.sql)
        chemin.write_text(
            sql_peuplement(g, regles[a.sql_lecture], a.sql_lecture,
                           fin.strftime("%Y-%m-%d")), encoding="utf-8")
        crier(f"▶ .sql de peuplement écrit ({a.sql_lecture}) : {chemin}")
        crier(f"  {regles[a.sql_lecture]['n_ecartes']} inscriptions "
              f"écartées — À EXÉCUTER PAR YANN, jamais d'ici.")

    if a.json:
        # ⚠️ Les `set` et les tuples de `rejouer` ne sont pas sérialisables
        # et n'ont rien à faire dans un objet publié : seul ce qui a été
        # RÉDUIT en chiffres sort d'ici.
        print(json.dumps({"graphe": {k: v for k, v in g.items()
                                     if k != "reseaux"},
                          "regles": regles, "degats": degats, "duel": du,
                          "faits": faits},
                         ensure_ascii=False, indent=1, default=str))
    else:
        print(rapport(g, regles, degats, du, faits))
    return 0


if __name__ == "__main__":
    sys.exit(main())
