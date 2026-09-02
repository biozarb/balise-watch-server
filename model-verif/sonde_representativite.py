#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/sonde_representativite.py — LE PLANCHER D'ERREUR QUE
#  AUCUN MODÈLE NE PASSERA                          (Lot L6, 27/08/2026)
#
#  PONCTUELLE, LECTURE SEULE. Elle n'écrit rien en base, ne publie rien,
#  ne s'installe dans aucun timer. Elle lit les archives d'observation
#  de TOUTES les sources et rend un rapport.
#
#  ═══ LA QUESTION, ET POURQUOI ELLE EST RÉPONDABLE ═══
#
#  Une balise est un point ; une maille AROME fait 1,3 km et le modèle
#  ne résout vraiment que 5 à 7 Δx, soit 7 à 9 km. Une part de
#  « l'erreur » qu'on impute aux modèles est donc IRRÉDUCTIBLE : c'est
#  la différence entre le vent d'un point et le vent moyen du volume
#  que le modèle sait décrire. Sans une estimation de ce plancher,
#  l'écart de 0,08 km/h entre deux modèles n'est interprétable par
#  personne (audit §4.1, lacune nº 1 face à l'état de l'art).
#
#  ⭐ CE QUI REND LE PLANCHER MESURABLE SANS UN SEUL MODÈLE : deux
#  balises assez PROCHES pour que le modèle leur serve la même
#  prévision. Notons V le vent que le modèle peut connaître, et
#  ε l'écart entre le vent d'un point et V :
#
#      V_A = V + ε_A        V_B = V + ε_B        Δ = V_A − V_B
#
#  V disparaît de la soustraction. Si ε_A et ε_B sont indépendants et de
#  même dispersion σ :
#
#      E‖Δ‖² = E‖ε_A‖² + E‖ε_B‖² = 2σ²   ⇒   σ = √(½·E‖Δ‖²)
#
#  C'est la demi-variance des paires proches (Ben Bouallègue 2020,
#  ECMWF TM 865 ; Saetra 2004 ; méthode « réseau dense »). Le facteur
#  ½ est TOUT ce qu'il y a de savant là-dedans : deux balises portent
#  deux bruits, un modèle n'en affronte qu'un.
#
#  ⚠️ ET LA MÉDIANE ALORS ? Le lot demande ½·médiane‖Δ‖². L'identité
#  ci-dessus vaut pour l'ESPÉRANCE, pas pour la médiane — mais
#  médiane(‖Δ‖²) = médiane(‖Δ‖)², donc √(½·médiane‖Δ‖²) = médiane‖Δ‖/√2
#  quoi qu'il arrive. Et sous le modèle isotrope gaussien (ε bivarié
#  centré, composantes indépendantes de même σ), ‖Δ‖ et ‖ε‖ sont deux
#  Rayleigh dont les échelles sont dans le rapport √2 : la médiane
#  passe donc par le MÊME √2 que la moyenne quadratique. L'hypothèse
#  est NOMMÉE ici parce qu'elle est réfutable, pas parce qu'elle est
#  vraie : les deux lectures sont publiées côte à côte, et si elles
#  divergent beaucoup c'est l'isotropie qui tombe.
#
#  ⭐ ET C'EST POURQUOI IL Y A DEUX PLANCHERS, PAS UN. Le produit
#  publie `err_vec_med` (médiane des heures d'une balise-jour) et
#  `err_vec_rms` (moyenne quadratique des mêmes heures). Chacun a SON
#  plancher, calculé de la même façon sur les mêmes heures :
#
#      plancher_med = médiane(‖Δ‖)/√2      face à `err_vec_med`
#      plancher_rms = rms(‖Δ‖)/√2          face à `err_vec_rms`
#
#  Comparer un plancher médian à une erreur rms, ou l'inverse, ferait
#  un chiffre parfaitement crédible et faux d'un tiers.
#
#  ═══ LE SECOND PARTAGE : CE QU'UNE CORRECTION DE SITE PEUT REPRENDRE ═══
#
#  Tout le plancher n'est pas hors de portée. Sur une paire, l'écart
#  moyen D̄ = moyenne(V_A − V_B) est PERSISTANT : une balise abritée
#  l'est tous les jours. Le lot S2 apprend exactement ce genre de
#  chose (pente et décalage de direction par site, sur J−30..J−1).
#  L'identité, exacte sur les heures vectorielles :
#
#      ½·E‖Δ‖²  =  ½‖D̄‖²  +  ½·E‖Δ − D̄‖²
#      plancher² = persistant²        + fluctuant²
#
#  ⛔ Le fluctuant est le VRAI plancher : rien ne le reprendra, ni une
#  correction de site, ni une maille plus fine (il vit sous la maille).
#  Le persistant borne ce qu'un `err_corrigee` peut espérer gagner.
#  La sonde VÉRIFIE l'identité sur chaque groupe au lieu de l'affirmer.
#
#  ═══ LE CONFONDANT NOMMÉ PAR LE LOT, ET LES QUATRE AUTRES ═══
#
#  (1) MÊME RÉSEAU. Deux Pioupiou à 800 m partagent leur mât, leur
#      firmware, leur fenêtre de moyennage et leur façon d'arrondir.
#      Leur Δ est donc plus PETIT que la vérité : le bruit d'instrument
#      commun s'annule dans la soustraction. → paires intra-réseau
#      séparées des inter-réseaux, TOUJOURS, et jamais fondues.
#  (2) RÉSEAUX DIFFÉRENTS. À l'inverse : hauteur de capteur (METAR à
#      10 m sur un aérodrome, Pioupiou à 4-6 m sur un déco), pas de
#      temps de moyennage, unité d'arrondi. Leur Δ est plus GRAND que
#      la vérité. ⇒ intra-réseau = MINORANT, inter-réseaux = MAJORANT,
#      et le vrai plancher est entre les deux. C'est la seule lecture
#      honnête de ces deux nombres, et le rapport la dit en toutes
#      lettres.
#  (3) LE DOUBLON. Une même balise inscrite deux fois (deux réseaux,
#      deux identifiants) rendrait Δ ≡ 0 et tirerait le plancher vers
#      zéro. Détecté (distance quasi nulle ET écart nul sur presque
#      toutes les heures), ÉCARTÉ, et compté.
#  (4) LE DÉNIVELÉ. Deux balises à 900 m l'une de l'autre mais 400 m
#      l'une au-dessus de l'autre ne sont pas le même site — et le
#      modèle, lui, les distingue par son orographie. → bandes de Δz
#      (`station_zone.dem_alt_m`), et le plancher publié est celui des
#      paires de même niveau.
#  (5) LA DENSITÉ. Une balise entourée de cinq autres donne cinq paires
#      qui ne sont pas indépendantes. Le rapport publie donc n(paires)
#      ET n(balises) partout, et l'intervalle est tiré par BLOCS DE
#      JOURS (`inference.block_ci_by_day`), pas sur les paires.
#
#  ═══ CE QUE CETTE SONDE NE PEUT PAS DIRE ═══
#
#  ⛔ Elle ne mesure pas le plancher d'UNE balise, seulement celui d'une
#  CLASSE de balises. Un plancher par site demanderait des voisines à
#  chaque site ; elles n'existent qu'aux endroits denses.
#  ⛔ Elle ne sépare pas l'erreur de représentativité du bruit
#  d'instrument. Les deux sont irréductibles pour un modèle, donc les
#  deux appartiennent au plancher — mais le nom exact est « plancher
#  d'observation », pas « représentativité pure ».
#  ⛔ Elle ne dit rien des distances SOUS la plus petite paire observée.
#  Le plancher vu à 800 m n'est pas celui à 0 m ; il est PLUS PETIT que
#  celui d'un point contre une maille de 1,3 km. Le profil par bande de
#  distance est publié pour qu'on voie la pente au lieu de l'ignorer.
#
#  ═══ USAGE ═══
#
#      # sur le VPS (les archives obs n'existent que là)
#      ssh debian@51.91.102.146
#      cd ~/balise-watch/balise-watch-server/model-verif
#      set -a && . ~/.balise-watch-model-verif.env && set +a
#      ~/venv-balise/bin/python3 sonde_representativite.py --jours 30
#
#      python3 sonde_representativite.py --fin 2026-08-26 --jours 30
#      python3 sonde_representativite.py --json          # objet brut
#      python3 sonde_representativite.py --sans-zones    # sans Supabase
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import inference as INF      # noqa: E402
import score as SC           # noqa: E402
import scoring as S          # noqa: E402
from geopair import distance_km   # noqa: E402


# ══════════════════════════════════════════════════════════════════
#  CONSTANTES — chacune motivée, aucune ronde par hasard
# ══════════════════════════════════════════════════════════════════

#: Les deux rayons du lot. 1,5 km ≈ une maille AROME 0,01° (1,3 km) :
#: à cette distance le modèle sert littéralement le même nœud ou son
#: voisin. 3 km reste sous les 5-7 Δx que le modèle résout vraiment.
RAYONS_KM = (1.5, 3.0)

#: Bornes HAUTES des bandes du profil. Le profil existe pour montrer la
#: PENTE : un plancher qui grandit vite avec la distance dit que ce
#: qu'on mesure est de la décorrélation spatiale (donc bien de la
#: représentativité) ; un plancher plat dirait du bruit d'instrument.
BANDES_KM = (0.3, 0.8, 1.5, 2.2, 3.0)

RACINE_2 = math.sqrt(2.0)

#: Bandes de dénivelé (m). 50 m : sous le pas vertical que l'orographie
#: AROME distingue à cette maille. 150 m : au-delà, deux balises sont
#: sur deux étages différents de la même pente.
DZ_BANDES = (50.0, 150.0)

#: Sous ce nombre d'heures communes, la médiane d'une paire-jour ne dit
#: rien — même seuil d'esprit que `WINNER_MIN_PAIRS` (4) mais plus
#: exigeant : ici une paire-jour est l'unité qu'on agrège, comme une
#: balise-jour dans `score.py`, et une balise-jour de 3 heures ne serait
#: pas notée non plus.
MIN_HEURES_PAIRE_JOUR = 6

#: Sous ce nombre de paires, aucun chiffre de classe n'est publié : on
#: écrit `n` et on se tait. Trois paires ne font pas une classe de
#: terrain, elles font trois voisinages.
MIN_PAIRES_CLASSE = 5

#: ⛔ SOUS CETTE DISTANCE, LA MÉTHODE NE S'APPLIQUE PLUS — et c'est le
#: résultat le plus important de la première exécution réelle (27/08).
#: La demi-variance suppose DEUX POINTS séparés : c'est la séparation
#: qui décorrèle. À d ≈ 0, il n'y a rien à décorréler, et ce qu'on
#: mesure n'est pas de la représentativité mais de la CHAÎNE : le même
#: capteur physique republié par deux réseaux (`pioupiou:1214` et
#: `windsmobi:ffvl-3214`, `metar:LFBA` et `mf:47091001`), ou deux
#: inscriptions du même mât, ou deux coordonnées bidon identiques.
#: ⚠️ Mesuré : 503 paires sur 1 170 étaient à moins de 50 m, et elles
#: tiraient le plancher « inter-réseaux » à 0,63 km/h — un chiffre
#: parfaitement lisible qui ne disait rien du sujet du lot.
#: ⭐ Ces paires ne sont PAS jetées : elles mesurent le SOCLE
#: d'observation (le « nugget » du variogramme), c'est-à-dire le
#: désaccord entre deux lectures du même vent. Un modèle ne descendra
#: pas sous lui non plus. Elles sont donc publiées à part, sous leur
#: vrai nom, et jamais mélangées au plancher spatial.
DIST_MIN_KM = 0.1

#: ⛔ ET LA MÊME MALADIE SURVIT AU-DELÀ DE 100 m — mesuré le 27/08 et
#: non prévu. `windsmobi/ffvl` REPUBLIE des balises Pioupiou sous un
#: autre identifiant ET une autre coordonnée : `pioupiou:1494` et
#: `windsmobi:ffvl-3494` sont archivées à 111 m l'une de l'autre et
#: s'accordent à 0,30 km/h médian sur 144 heures. Elles passent donc
#: sous le radar de `DIST_MIN_KM`, et elles tirent le plancher
#: « inter-réseaux » SOUS le plancher « intra-réseau » — l'inverse de
#: ce que la physique impose. (C'est la même divergence de
#: référentiels que le lot L4 a mesurée entre `agrume` et `arome_r2` :
#: 160 balises sur 285 n'ont pas la même coordonnée des deux côtés.)
#: ⚠️ CES PAIRES NE SONT PAS ÉCARTÉES D'OFFICE, et c'est délibéré :
#: les écarter sur leur ACCORD serait circulaire — on jetterait les
#: paires qui se ressemblent pour mesurer à quel point les paires se
#: ressemblent. Elles sont NOMMÉES, comptées, et le plancher est
#: publié DEUX FOIS, avec et sans elles. L'écart entre les deux
#: lectures est l'incertitude que cette contamination introduit.
RAYON_QUASI_KM = 0.5
SEUIL_QUASI_KMH = 1.0

#: Un doublon d'inscription : deux identifiants pour un seul capteur.
#: 50 m est plus petit que la précision d'un référentiel (4 décimales
#: ≈ 11 m) fois quelques unités ; la distance seule ne suffit pas, il
#: faut AUSSI l'écart nul (voir `est_doublon`).
CLONE_DIST_KM = 0.05
CLONE_PART_NULLE = 0.90

#: Au-delà, la balise a DÉMÉNAGÉ pendant la fenêtre (lot L15 : 11
#: déménagements confirmés). Une paire dont un bout bouge n'a pas de
#: distance, donc pas de bande : elle sort, et elle est comptée.
DERIVE_MAX_KM = 0.1

DAY_MS = 24 * 3600 * 1000
HEURE_MS = 3600 * 1000

#: Les classes de terrain de `station_zone.landform` — le CHECK de la
#: base, recopié ici (même geste que `assign_zones.LANDFORMS`).
#: ⭐ POURQUOI CELLES-LÀ ET PAS UNE CLASSIFICATION MAISON : ce sont les
#: classes qui composent déjà `zone_id` (« alpes-nord:plain »), donc
#: celles dans lesquelles le score est PUBLIÉ. Un plancher rangé
#: autrement ne se poserait à côté d'aucun chiffre existant.
LANDFORMS = ("valley", "slope", "ridge", "plateau", "plain", "coastal")

LANDFORM_FR = {
    "valley": "vallée", "slope": "pente", "ridge": "crête",
    "plateau": "plateau", "plain": "plaine", "coastal": "littoral",
    "mixte": "MIXTE (les deux bouts diffèrent)", "?": "inconnu",
}


# ══════════════════════════════════════════════════════════════════
#  LE NOYAU — des fonctions pures, bançables sans une seule archive
# ══════════════════════════════════════════════════════════════════

def unite(row: dict) -> str:
    """La clé d'une balise, celle de tout le reste du projet."""
    return f"{row['source']}:{row['station_id']}"


def reseau(u: str) -> str:
    """Le réseau d'une balise — la partie avant les deux points."""
    return u.split(":", 1)[0]


def fournisseur(u: str, reseaux: dict) -> str:
    """Le vrai producteur de la mesure, pas le flux qui la transporte.

    ⛔ `windsmobi` N'EST PAS UN RÉSEAU, C'EST UN AGRÉGATEUR. Mesuré sur
    l'archive du 26/08 : 466 balises `ffvl`, 378 `holfuy`, 193 `slf`,
    155 `meteoswiss`, et douze autres fournisseurs derrière la même
    source. Deux balises « intra-windsmobi » peuvent donc être deux
    capteurs de deux constructeurs — c'est-à-dire exactement le cas
    que « intra-réseau = minorant » prétend exclure. Le champ
    `network` de la ligne d'archive porte le fournisseur : on le lit.
    """
    n = reseaux.get(u)
    s = reseau(u)
    return f"{s}/{n}" if n and n != s else s


def paires_proches(positions: dict, rayon_km: float) -> list:
    """Toutes les paires de balises à moins de `rayon_km`, une seule fois.

    ⚠️ PAS DE BOUCLE EN n². Avec ~2 000 balises ce serait tenable, mais
    la sonde est rejouée à chaque rayon et à chaque fenêtre : on pave.

    ⭐ LE PAVAGE EST CORRECT PAR CONSTRUCTION, pas par chance. La case
    fait `rayon/111,32` degrés en latitude et
    `rayon/(111,32·cos φ_max)` en longitude, où φ_max est la latitude
    la plus haute du jeu. La largeur RÉELLE d'une case à la latitude φ
    vaut donc `rayon·cos φ / cos φ_max`, c'est-à-dire ≥ rayon partout
    où |φ| ≤ φ_max. Une case mesurant au moins `rayon` dans les deux
    directions, deux points distants de moins de `rayon` sont
    forcément dans deux cases adjacentes : le voisinage 3×3 suffit, et
    il ne peut RIEN rater. (Un pavage à pas fixe, lui, se met à rater
    des paires dès qu'on monte en latitude — sans jamais le dire.)
    """
    if not positions or rayon_km <= 0:
        return []
    lat_max = max(abs(la) for la, _ in positions.values())
    cos_min = max(math.cos(math.radians(min(lat_max, 85.0))), 0.05)
    pas_lat = rayon_km / 111.32
    pas_lon = rayon_km / (111.32 * cos_min)

    cases: dict = defaultdict(list)
    for u, (la, lo) in positions.items():
        cases[(math.floor(la / pas_lat), math.floor(lo / pas_lon))].append(u)

    vues: set = set()
    out = []
    for (ci, cj), membres in cases.items():
        voisins = []
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                voisins.extend(cases.get((ci + di, cj + dj), ()))
        for a in membres:
            la_a, lo_a = positions[a]
            for b in voisins:
                if a == b:
                    continue
                cle = (a, b) if a < b else (b, a)
                if cle in vues:
                    continue
                la_b, lo_b = positions[b]
                d = distance_km(la_a, lo_a, la_b, lo_b)
                if d <= rayon_km:
                    vues.add(cle)
                    out.append((cle[0], cle[1], d))
    out.sort(key=lambda p: (p[2], p[0], p[1]))
    return out


def serie_horaire(samples, jour_ms: int,
                  demi_fenetre_ms: int = S.OBS_HALF_WINDOW_MS):
    """Les 24 heures rondes UTC d'une journée, vues par UNE balise.

    ⚠️ C'EST LA MOITIÉ « MODÈLE » DE `pair_series`, ET C'EST VOULU.
    `scoring.pair_series` est asymétrique — une série de prévision d'un
    côté, des relevés de l'autre — alors qu'ici les deux bouts sont des
    relevés. Il faut donc qu'un des deux côtés soit préparé à la main.
    La symétrie n'est pas obtenue par précaution mais par CONSTRUCTION :
    ce côté-ci passe par `scoring.mean_wind`, l'autre y passe aussi
    (dans `pair_series`), avec la même demi-fenêtre et le même seuil de
    direction. Le banc le vérifie en échangeant A et B — l'écart doit
    être identique au bit près.
    """
    ordered = sorted((s for s in samples if S._finite(s.speed)),
                     key=lambda s: s.t)
    times = [jour_ms + h * HEURE_MS for h in range(24)]
    speeds: list = []
    dirs: list = []
    lo = 0
    for t in times:
        while lo < len(ordered) and ordered[lo].t < t - demi_fenetre_ms:
            lo += 1
        j = lo
        win = []
        while j < len(ordered) and ordered[j].t <= t + demi_fenetre_ms:
            win.append(ordered[j])
            j += 1
        sp, di, _n = S.mean_wind(win) if win else (None, None, 0)
        speeds.append(sp)
        dirs.append(di)
    return times, speeds, dirs


def ecarts_paire_jour(obs_a, obs_b, jour_ms: int):
    """Les heures COMMUNES d'une paire dans une journée, et leurs écarts.

    Rend `(SeriesError, [(du, dv), …])` — le second uniquement sur les
    heures VECTORIELLES, seules où un écart a deux composantes.

    ⚠️ Les heures sans relevé d'un des deux côtés sont ABSENTES, jamais
    comblées : c'est la règle de `pair_series`, et on la reprend telle
    quelle plutôt que de fabriquer un vent pour compléter une journée.
    """
    times, sp, di = serie_horaire(obs_a, jour_ms)
    vpairs = S.pair_series(times, sp, di, obs_b)
    se = S.series_error(vpairs)
    duv = []
    for p in vpairs:
        _err, vectorielle = S.pair_error(p)
        if not vectorielle:
            continue
        au, av = S.to_uv(p.fcst_speed, p.fcst_dir)
        bu, bv = S.to_uv(p.obs_speed, p.obs_dir)
        duv.append((au - bu, av - bv))
    return se, duv


def est_doublon(dist_km: float, per_hour) -> bool:
    """Deux identifiants pour un seul capteur — pas une paire.

    ⛔ LA DISTANCE SEULE NE SUFFIT PAS, et c'est le piège : deux
    Pioupiou VRAIMENT posés à 30 m l'un de l'autre sont la paire la
    plus précieuse du jeu (le plancher à distance quasi nulle). Les
    écarter sur la seule distance jetterait l'observation la plus
    informative pour éviter un doublon. Il faut donc les DEUX signes :
    quasi même point ET écart nul presque partout. Un vrai voisinage à
    30 m garde du bruit ; une inscription en double n'en a aucun.
    """
    if dist_km > CLONE_DIST_KM or not per_hour:
        return False
    nuls = sum(1 for e in per_hour if e == 0.0)
    return nuls >= CLONE_PART_NULLE * len(per_hour)


def bande_distance(d: float) -> str:
    """L'étiquette de bande d'une distance."""
    bas = 0.0
    for haut in BANDES_KM:
        if d <= haut:
            return f"{bas:.1f}–{haut:.1f} km"
        bas = haut
    return f"> {BANDES_KM[-1]:.1f} km"


def _etiquettes_bandes() -> list:
    """Les étiquettes du profil, dans l'ordre, une par bande et une
    seule — au format exact que rend `bande_distance`."""
    bornes = (0.0,) + BANDES_KM
    return [f"{bornes[i]:.1f}–{bornes[i + 1]:.1f} km"
            for i in range(len(BANDES_KM))]


def bande_dz(dz) -> str:
    """L'étiquette de bande d'un dénivelé, `?` si une altitude manque."""
    if dz is None:
        return "?"
    dz = abs(dz)
    if dz < DZ_BANDES[0]:
        return f"< {DZ_BANDES[0]:.0f} m"
    if dz < DZ_BANDES[1]:
        return f"{DZ_BANDES[0]:.0f}–{DZ_BANDES[1]:.0f} m"
    return f"≥ {DZ_BANDES[1]:.0f} m"


def classe_terrain(la, lb) -> str:
    """La classe d'une PAIRE : celle des deux bouts s'ils s'accordent.

    ⚠️ « mixte » N'EST PAS UN REBUT. Une paire crête/vallée mesure une
    vraie chose — la variabilité entre deux expositions que le modèle
    confond — mais elle ne mesure pas le plancher DE la crête ni celui
    DE la vallée. Elle est donc gardée, comptée, et publiée à part.
    """
    if la is None or lb is None:
        return "?"
    return la if la == lb else "mixte"


# ══════════════════════════════════════════════════════════════════
#  L'AGRÉGATION — de la paire-jour au plancher d'une classe
# ══════════════════════════════════════════════════════════════════

@dataclass
class AccPaire:
    """Ce qu'on retient d'une paire sur TOUTE la fenêtre.

    ⚠️ Le partage persistant / fluctuant se calcule sur la fenêtre
    entière, pas par jour : le biais d'exposition d'un site est
    justement ce qui NE change pas d'un jour à l'autre. Le calculer par
    jour puis moyenner le noierait dans le fluctuant — l'erreur qui
    ferait croire qu'une correction de site ne peut rien reprendre.
    """
    n: int = 0
    somme_carres: float = 0.0     # Σ‖Δ‖² sur les heures VECTORIELLES
    su: float = 0.0
    sv: float = 0.0


def stats_paire(acc: AccPaire):
    """(moyenne‖Δ‖², ‖D̄‖², fluctuant) d'une paire. `None` si trop court.

    L'identité `ms = pers + fluct` est EXACTE (König-Huygens), pas
    approchée : c'est pour ça qu'elle sert de contrôle plus loin.
    """
    if acc.n < 2:
        return None
    ms = acc.somme_carres / acc.n
    pers = (acc.su / acc.n) ** 2 + (acc.sv / acc.n) ** 2
    return ms, pers, max(0.0, ms - pers)


def plancher(x) -> float | None:
    """La règle du lot, appliquée une seule fois dans tout le fichier :
    un écart entre DEUX balises porte DEUX bruits, un modèle un seul."""
    if x is None or not S._finite(x):
        return None
    return x / RACINE_2


def agreger(enrs: list, accs: dict, min_jours: int = INF.MIN_DAYS_BLOCK):
    """Le plancher d'un groupe de paires-jours, avec tout ce qui le qualifie.

    ⚠️ L'INTERVALLE EST TIRÉ PAR BLOCS DE JOURS, jamais sur les paires.
    Deux paires qui partagent une balise ne sont pas indépendantes, et
    deux heures du même jour encore moins : un IC tiré sur les paires
    serait faux d'un facteur qu'on ne saurait même pas nommer.
    `inference.block_ci_by_day` est celui du duel L1 et du lot L3 — on
    l'appelle, on n'en écrit pas un second (leçon du L1, arbitrage 1).
    """
    if not enrs:
        return None
    med_par_jour: dict = defaultdict(list)
    rms_par_jour: dict = defaultdict(list)
    paires, balises, jours = set(), set(), set()
    n_heures = n_vect = 0
    for e in enrs:
        cle = (e["a"], e["b"])
        paires.add(cle)
        balises.add(e["a"])
        balises.add(e["b"])
        jours.add(e["jour"])
        n_heures += e["n"]
        n_vect += e["n_vect"]
        if e["med"] is not None:
            med_par_jour[e["jour"]].append(e["med"])
        if e["rms"] is not None:
            rms_par_jour[e["jour"]].append(e["rms"])

    med_ci = INF.block_ci_by_day(med_par_jour, min_days=min_jours)
    rms_ci = INF.block_ci_by_day(rms_par_jour, min_days=min_jours)

    # ── le partage persistant / fluctuant, mis en commun ────────────
    # Pondéré par le nombre d'heures : c'est la seule mise en commun où
    # l'identité de König-Huygens survit à l'agrégation.
    tot_n = 0
    tot_carres = 0.0
    tot_pers = 0.0
    tot_fluct = 0.0
    n_paires_uv = 0
    for cle in paires:
        acc = accs.get(cle)
        if acc is None:
            continue
        st = stats_paire(acc)
        if st is None:
            continue
        ms, pers, fl = st
        tot_n += acc.n
        tot_carres += ms * acc.n
        tot_pers += pers * acc.n
        tot_fluct += fl * acc.n
        n_paires_uv += 1
    ms_moy = tot_carres / tot_n if tot_n else None
    pers_moy = tot_pers / tot_n if tot_n else None
    # ⛔ LE FLUCTUANT EST MIS EN COMMUN, PAS REDÉDUIT. Le calculer ici
    # par `ms_moy − pers_moy` rendrait le « résidu » ci-dessous
    # tautologiquement nul : un contrôle d'identité qui ne peut pas
    # échouer n'est pas un contrôle. Trouvé par la mutation nº 15, qui
    # restait VERTE tant que cette ligne redéduisait au lieu de lire.
    fluct_moy = tot_fluct / tot_n if tot_n else None

    def _rac(x):
        return plancher(math.sqrt(x)) if x is not None else None

    return {
        "n_paires": len(paires),
        "n_balises": len(balises),
        "n_paire_jours": len(enrs),
        "n_jours": len(jours),
        "n_heures": n_heures,
        "part_vectorielle": (n_vect / n_heures) if n_heures else 0.0,
        "dist_med_km": S.median([e["dist"] for e in enrs]),
        # ── les deux planchers du lot ───────────────────────────────
        "plancher_med": plancher(med_ci.median),
        "plancher_med_bas": plancher(med_ci.ci_low),
        "plancher_med_haut": plancher(med_ci.ci_high),
        "ci_raison": med_ci.reason,
        "block_days": med_ci.block_days,
        "plancher_rms": plancher(rms_ci.median),
        "plancher_rms_bas": plancher(rms_ci.ci_low),
        "plancher_rms_haut": plancher(rms_ci.ci_high),
        # ── le second partage ───────────────────────────────────────
        "n_paires_uv": n_paires_uv,
        "n_heures_uv": tot_n,
        "plancher_quad": _rac(ms_moy),
        "plancher_persistant": _rac(pers_moy),
        "plancher_fluctuant": _rac(fluct_moy),
        # Contrôle d'identité : pers² + fluct² − quad² doit être NUL.
        "residu_identite": (
            None if None in (ms_moy, pers_moy, fluct_moy)
            else abs((pers_moy + fluct_moy) - ms_moy) / 2.0),
    }


# ══════════════════════════════════════════════════════════════════
#  LES RÉFÉRENTIELS DE TERRAIN — classe et altitude, par balise
# ══════════════════════════════════════════════════════════════════

def charger_zones(crier=print) -> dict:
    """`station_zone` : la classe de terrain et l'altitude DEM, par balise.

    ⭐ POURQUOI CETTE TABLE PLUTÔT QUE `orographie_balises.ndjson`, que
    le lot nomme. Trois raisons, mesurées et non déduites :
      1. `orographie_balises.ndjson` est produit à la main depuis
         `stations.json` — donc le référentiel Pioupiou, et lui seul.
         Le lot demande TOUTES les sources ; la moitié des paires
         intéressantes est inter-réseaux et n'y figure pas.
      2. `station_zone.landform` porte les classes qui composent déjà
         `zone_id` (« alpes-nord:plain ») : le plancher se pose donc à
         côté d'un `err_vec_med` rangé de la MÊME façon. Une classe
         maison ne se poserait à côté de rien.
      3. Elle porte `dem_alt_m`, une altitude RÉELLE — et le
         référentiel Pioupiou n'en a aucune (relevé le 10/08 dans
         l'en-tête de `tools/orographie_balises.py`). Sans elle, le
         confondant nº 4 (le dénivelé) ne serait pas mesurable.
    ⓘ `orographie_balises.ndjson` reste lu s'il est là, en covariable
    de relief — c'est sa vraie valeur ajoutée, et elle est ailleurs.
    """
    try:
        sb = SC.Supabase()
        rows = sb.select("station_zone", order="source,station_id")
    except Exception as e:                       # noqa: BLE001
        crier(f"  ⚠️ `station_zone` illisible ({type(e).__name__}) — "
              f"aucune classe de terrain, aucun dénivelé. Les planchers "
              f"par distance et par réseau restent valides.")
        return {}
    out = {}
    for r in rows:
        u = f"{r.get('source')}:{r.get('station_id')}"
        out[u] = {
            "landform": r.get("landform"),
            "alt": r.get("dem_alt_m"),
            "relief_5km": r.get("relief_5km_m"),
        }
    crier(f"  · `station_zone` : {len(out)} balises classées")
    return out


def charger_orographie(root: pathlib.Path, crier=print) -> dict:
    """La covariable de relief RÉSOLU par AROME, si le fichier est là.

    Absent = pas une panne : il se produit à la main
    (`tools/orographie_balises.py --out …`) et n'a pas de timer.
    """
    p = root / "orographie_balises.ndjson"
    if not p.exists():
        crier("  ⓘ pas d'`orographie_balises.ndjson` — axe relief AROME "
              "absent (produit à la main, sans timer)")
        return {}
    out = {}
    for ligne in p.read_text(encoding="utf-8").splitlines():
        if not ligne.strip():
            continue
        try:
            d = json.loads(ligne)
        except ValueError:
            continue
        u = f"{d.get('source')}:{d.get('id')}"
        r8 = d.get("r8km") or {}
        if r8.get("amplitude") is not None:
            out[u] = float(r8["amplitude"])
    crier(f"  · relief AROME 8 km : {len(out)} balises")
    return out


def bande_relief(x) -> str:
    """Le dénivelé que le modèle RÉSOUT autour de la balise, en bandes."""
    if x is None:
        return "?"
    if x < 200:
        return "< 200 m (plat pour AROME)"
    if x < 600:
        return "200–600 m"
    if x < 1200:
        return "600–1200 m"
    return "≥ 1200 m"


# ══════════════════════════════════════════════════════════════════
#  LA SONDE — une passe sur les archives, jour par jour
# ══════════════════════════════════════════════════════════════════

def sonder(root: pathlib.Path, fin: datetime, jours: int,
           rayon_max: float = 3.0, storage=None, zones=None,
           relief=None, lecteur=None, crier=print) -> dict:
    """La mesure. Lecture seule, une journée à la fois en mémoire.

    ⭐ `lecteur` EST CE QUI REND CETTE SONDE BANÇABLE. C'est
    `jour -> lignes d'archive`, et il vaut par défaut la lecture réelle.
    Le banc lui passe des journées FABRIQUÉES dont il connaît le
    plancher parce qu'il l'a posé : c'est la seule façon de vérifier
    qu'un estimateur rend le bon nombre, et pas seulement un nombre.
    ⚠️ Sans ce paramètre, le banc n'aurait pu tester que le noyau, et
    la boucle qui l'appelle — exclusions, axes, agrégation — serait
    partie sur la production sans qu'une assertion l'ait vue.
    """
    zones = zones if zones is not None else {}
    relief = relief if relief is not None else {}
    if lecteur is None:
        def lecteur(d):
            return SC.all_obs_rows(root, d, storage)

    enrs: list = []
    accs: dict = defaultdict(AccPaire)
    dist_par_paire: dict = defaultdict(list)
    per_hour_par_paire: dict = defaultdict(list)
    pos_par_unite: dict = defaultdict(list)
    reseaux_par_unite: dict = {}
    jours_lus, jours_vides = 0, 0
    n_lignes = 0
    sources_vues: dict = defaultdict(int)

    for k in range(jours):
        d = fin - timedelta(days=k)
        rows = lecteur(d)
        if not rows:
            jours_vides += 1
            continue
        jours_lus += 1
        n_lignes += len(rows)
        jour_ms = int(d.replace(tzinfo=timezone.utc).timestamp()) * 1000
        jour_txt = d.strftime("%Y-%m-%d")

        positions: dict = {}
        echantillons: dict = {}
        for r in rows:
            la, lo = r.get("lat"), r.get("lon")
            if la is None or lo is None:
                continue
            u = unite(r)
            ech = SC.to_obs_samples(r)
            if not ech:
                continue
            positions[u] = (float(la), float(lo))
            # ⚠️ Une balise peut apparaître sur DEUX lignes du même jour
            # (deux passes de collecte) : on concatène, `mean_wind` fera
            # la moyenne. Écraser perdrait une demi-journée en silence.
            echantillons.setdefault(u, []).extend(ech)
            sources_vues[reseau(u)] += 1
            pos_par_unite[u].append((float(la), float(lo)))
            if r.get("network"):
                reseaux_par_unite[u] = str(r["network"])

        cache_serie: dict = {}
        for a, b, dist in paires_proches(positions, rayon_max):
            if a not in cache_serie:
                cache_serie[a] = serie_horaire(echantillons[a], jour_ms)
            times, sp, di = cache_serie[a]
            vpairs = S.pair_series(times, sp, di, echantillons[b])
            se = S.series_error(vpairs)
            if se.n < MIN_HEURES_PAIRE_JOUR:
                continue
            cle = (a, b)
            dist_par_paire[cle].append(dist)
            per_hour_par_paire[cle].extend(se.per_hour)
            acc = accs[cle]
            n_vect = 0
            for p in vpairs:
                _e, vectorielle = S.pair_error(p)
                if not vectorielle:
                    continue
                n_vect += 1
                au, av = S.to_uv(p.fcst_speed, p.fcst_dir)
                bu, bv = S.to_uv(p.obs_speed, p.obs_dir)
                du, dv = au - bu, av - bv
                acc.n += 1
                acc.somme_carres += du * du + dv * dv
                acc.su += du
                acc.sv += dv
            enrs.append({
                "jour": jour_txt, "a": a, "b": b, "dist": dist,
                "n": se.n, "n_vect": n_vect,
                "med": se.med, "rms": se.rms,
            })

    # ── LES EXCLUSIONS, décidées à la fin sur la fenêtre entière ────
    doublons, derives = set(), set()
    for cle, dists in dist_par_paire.items():
        if max(dists) - min(dists) > DERIVE_MAX_KM:
            derives.add(cle)
            continue
        if est_doublon(min(dists), per_hour_par_paire[cle]):
            doublons.add(cle)
    ecartees = doublons | derives
    retenus = [e for e in enrs if (e["a"], e["b"]) not in ecartees]
    # ⛔ LA PARTITION QUI DÉCIDE DE TOUT : sous DIST_MIN_KM on ne mesure
    # plus une distance, on mesure une chaîne. Les deux populations ne
    # se mélangent jamais, et chacune est publiée sous son vrai nom.
    co_implantees = [e for e in retenus if e["dist"] < DIST_MIN_KM]
    gardes = [e for e in retenus if e["dist"] >= DIST_MIN_KM]

    unites_mobiles = sum(
        1 for u, ps in pos_par_unite.items()
        if len(ps) > 1 and distance_km(min(p[0] for p in ps),
                                       min(p[1] for p in ps),
                                       max(p[0] for p in ps),
                                       max(p[1] for p in ps)) > DERIVE_MAX_KM)

    # ── LES AXES ────────────────────────────────────────────────────
    def _z(u, champ):
        return (zones.get(u) or {}).get(champ)

    for e in gardes + co_implantees:
        a, b = e["a"], e["b"]
        fa = fournisseur(a, reseaux_par_unite)
        fb = fournisseur(b, reseaux_par_unite)
        e["intra"] = fa == fb
        e["reseaux"] = f"{fa} ↔ {fa}" if e["intra"] else " ↔ ".join(
            sorted((fa, fb)))
        e["bande"] = bande_distance(e["dist"])
        e["terrain"] = classe_terrain(_z(a, "landform"), _z(b, "landform"))
        alt_a, alt_b = _z(a, "alt"), _z(b, "alt")
        e["dz"] = (None if alt_a is None or alt_b is None
                   else abs(float(alt_a) - float(alt_b)))
        e["bande_dz"] = bande_dz(e["dz"])
        ra, rb = relief.get(a), relief.get(b)
        e["relief"] = bande_relief(None if ra is None or rb is None
                                   else (ra + rb) / 2.0)

    def _sel(pred):
        return agreger([e for e in gardes if pred(e)], accs)

    resultat = {
        "fenetre": {
            "fin": fin.strftime("%Y-%m-%d"), "jours_demandes": jours,
            "jours_lus": jours_lus, "jours_vides": jours_vides,
            "lignes_obs": n_lignes,
            "reseaux": dict(sorted(sources_vues.items())),
            "rayon_max_km": rayon_max,
        },
        "exclusions": {
            "paires_doublon": sorted(f"{a} ≡ {b}" for a, b in doublons),
            "paires_deriveuses": sorted(f"{a} ↔ {b}" for a, b in derives),
            "balises_deplacees": unites_mobiles,
            "paire_jours_ecartes": len(enrs) - len(retenus),
            "paire_jours_co_implantes": len(co_implantees),
        },
        "rayons": {}, "profil": {}, "reseaux": {},
        "terrain": {}, "denivele": {}, "relief": {},
        "socle": {}, "socle_couples": {}, "socle_extremes": [],
        "quasi_identiques": {}, "hors_quasi": None,
        "paires_les_plus_proches": [],
    }

    # ── LES QUASI-IDENTIQUES (republications à coordonnée décalée) ──
    med_par_paire: dict = defaultdict(list)
    for e in gardes:
        if e["med"] is not None:
            med_par_paire[(e["a"], e["b"])].append(e["med"])
    quasi = {cle for cle, v in med_par_paire.items()
             if S.median(v) is not None and S.median(v) < SEUIL_QUASI_KMH}
    quasi = {cle for cle in quasi
             if min(dist_par_paire[cle]) < RAYON_QUASI_KM}
    resultat["quasi_identiques"] = {
        "n_paires": len(quasi),
        "seuil_km": RAYON_QUASI_KM, "seuil_kmh": SEUIL_QUASI_KMH,
        "par_couple": dict(sorted(
            {c: sum(1 for e in gardes
                    if (e["a"], e["b"]) in quasi and e["reseaux"] == c
                    and e["jour"] == gardes[0]["jour"]) for c in
             {e["reseaux"] for e in gardes
              if (e["a"], e["b"]) in quasi}}.items(),
            key=lambda kv: -kv[1])),
        "paires": [
            {"paire": f"{a_} ↔ {b_}",
             "dist_km": round(min(dist_par_paire[(a_, b_)]), 3),
             "ecart_med": round(S.median(med_par_paire[(a_, b_)]), 3),
             "n_jours": len(med_par_paire[(a_, b_)])}
            for a_, b_ in sorted(
                quasi, key=lambda c: S.median(med_par_paire[c]))[:12]],
    }
    resultat["hors_quasi"] = agreger(
        [e for e in gardes
         if (e["a"], e["b"]) not in quasi and e["dist"] <= RAYONS_KM[1]],
        accs)

    # ── LE SOCLE D'OBSERVATION (d < DIST_MIN_KM) ────────────────────
    resultat["socle"] = agreger(co_implantees, accs)
    for c in sorted({e["reseaux"] for e in co_implantees}):
        g = agreger([e for e in co_implantees if e["reseaux"] == c], accs)
        if g and g["n_paires"] >= MIN_PAIRES_CLASSE:
            resultat["socle_couples"][c] = g
    # ⚠️ Deux balises AU MÊME POINT dont les vents ne se ressemblent pas
    # ne sont pas un socle : c'est un défaut de référentiel. On les
    # NOMME au lieu de les moyenner (relevé le 27/08 :
    # `infoclimat:STATIC0022 ≡ STATIC0491`, 0,000 km, 13,6 km/h d'écart).
    par_paire_socle: dict = defaultdict(list)
    for e in co_implantees:
        if e["med"] is not None:
            par_paire_socle[(e["a"], e["b"], e["dist"])].append(e["med"])
    resultat["socle_extremes"] = [
        {"paire": f"{a} ↔ {b}", "dist_km": round(d, 3),
         "n_jours": len(v), "ecart_med": round(S.median(v), 3)}
        for (a, b, d), v in sorted(par_paire_socle.items(),
                                   key=lambda kv: -S.median(kv[1]))[:10]]

    for rayon in RAYONS_KM:
        resultat["rayons"][f"< {rayon} km"] = {
            "tous": _sel(lambda e, r=rayon: e["dist"] <= r),
            "intra_reseau": _sel(lambda e, r=rayon:
                                 e["dist"] <= r and e["intra"]),
            "inter_reseaux": _sel(lambda e, r=rayon:
                                  e["dist"] <= r and not e["intra"]),
        }

    # ⚠️ LES ÉTIQUETTES SE FABRIQUENT DEPUIS LES BORNES, PAS DEPUIS
    # `bande_distance` APPELÉE SUR LES BORNES. `bande_distance` range
    # sur `d <= haut` : appelée sur 0,3 elle rend « 0.0–0.3 », si bien
    # que la première bande sortait DEUX FOIS et que la dernière
    # (2.2–3.0 km) — celle qui porte le plus de paires — ne sortait
    # PAS DU TOUT. Le profil paraissait complet et s'arrêtait à 2,2 km.
    for b in _etiquettes_bandes():
        resultat["profil"][b] = _sel(lambda e, bb=b: e["bande"] == bb)

    couples = sorted({e["reseaux"] for e in gardes})
    for c in couples:
        g = _sel(lambda e, cc=c: e["reseaux"] == cc)
        if g and g["n_paires"] >= MIN_PAIRES_CLASSE:
            resultat["reseaux"][c] = g

    for t in sorted({e["terrain"] for e in gardes}):
        resultat["terrain"][t] = _sel(
            lambda e, tt=t: e["terrain"] == tt and e["dist"] <= RAYONS_KM[1])

    for z in sorted({e["bande_dz"] for e in gardes}):
        resultat["denivele"][z] = _sel(
            lambda e, zz=z: e["bande_dz"] == zz and e["dist"] <= RAYONS_KM[1])

    for rl in sorted({e["relief"] for e in gardes}):
        resultat["relief"][rl] = _sel(
            lambda e, rr=rl: e["relief"] == rr and e["dist"] <= RAYONS_KM[1])

    vues = {}
    for e in gardes:
        cle = (e["a"], e["b"])
        vues.setdefault(cle, {"dist": e["dist"], "n": 0, "meds": []})
        vues[cle]["n"] += e["n"]
        if e["med"] is not None:
            vues[cle]["meds"].append(e["med"])
    resultat["paires_les_plus_proches"] = [
        {"paire": f"{a} ↔ {b}", "dist_km": round(v["dist"], 3),
         "n_heures": v["n"], "n_jours": len(v["meds"]),
         "plancher_med": (None if not v["meds"]
                          else round(plancher(S.median(v["meds"])), 4))}
        for (a, b), v in sorted(vues.items(), key=lambda kv: kv[1]["dist"])[:12]
    ]
    return resultat


# ══════════════════════════════════════════════════════════════════
#  L'ERREUR TYPIQUE, MESURÉE — pas reprise d'un rapport
# ══════════════════════════════════════════════════════════════════

def erreur_typique(jour: datetime, lead_h: int = 6, zones=None,
                   crier=print) -> dict:
    """La médiane des `err_vec_med` / `err_vec_rms` d'une journée réelle.

    ⚠️ MESURÉE, PAS RECOPIÉE. Le lot parle d'« err_vec_med typiques
    (4-5 km/h) » ; ce chiffre vient d'un rapport, donc d'un état du code
    et d'une population qui ont pu bouger. Comparer un plancher mesuré
    ce soir à une erreur citée de mémoire, c'est exactement le nombre
    plausible et faux que tout ce chantier existe pour éviter.
    """
    try:
        sb = SC.Supabase()
        rows = sb.select(
            "model_verif_daily",
            # ⚠️ LE « ? » EST OBLIGATOIRE ICI. `Supabase.select` n'ajoute
            # son séparateur que lorsqu'il colle son propre `select=*` ;
            # une requête qui porte déjà un `select=` est concaténée
            # TELLE QUELLE au nom de la table. Sans le « ? », l'URL
            # devient `model_verif_dailyday=eq.…` et le serveur répond
            # une HTTPError qu'on lirait comme « table illisible ».
            # (Mesuré sur le VPS le 27/08 — le même piège que
            # `sonde_fdr.py`, qui passe par `_page` pour l'éviter.)
            query=(f"?day=eq.{jour:%Y-%m-%d}&lead_h=eq.{lead_h}"
                   "&select=source,station_id,model,err_vec_med,"
                   "err_vec_rms"))
    except Exception as e:                       # noqa: BLE001
        crier(f"  ⚠️ `model_verif_daily` illisible ({type(e).__name__}) — "
              f"pas de comparaison à l'erreur typique")
        return {}
    med = S.median([r["err_vec_med"] for r in rows
                    if r.get("err_vec_med") is not None])
    rms = S.median([r["err_vec_rms"] for r in rows
                    if r.get("err_vec_rms") is not None])
    par_source: dict = defaultdict(list)
    par_landform: dict = defaultdict(list)
    zones = zones or {}
    for r in rows:
        if r.get("err_vec_med") is None:
            continue
        par_source[r["source"]].append(r["err_vec_med"])
        # ⭐ LA MÊME CLASSE DES DEUX CÔTÉS. Comparer un plancher de
        # CRÊTE à une erreur typique TOUTES BALISES CONFONDUES ferait
        # dire au rapport que les crêtes n'ont presque plus de marge —
        # alors que l'erreur y est plus grande AUSSI. Les deux nombres
        # doivent être rangés dans la même case, ou ils ne se
        # comparent pas.
        lf = (zones.get(f"{r['source']}:{r['station_id']}") or {}).get(
            "landform")
        if lf:
            par_landform[lf].append(r["err_vec_med"])
    return {
        "jour": jour.strftime("%Y-%m-%d"), "lead_h": lead_h,
        "n_lignes": len(rows), "err_vec_med": med, "err_vec_rms": rms,
        "par_source": {k: {"n": len(v), "med": S.median(v)}
                       for k, v in sorted(par_source.items())},
        "par_landform": {k: {"n": len(v), "med": S.median(v)}
                         for k, v in sorted(par_landform.items())},
    }


# ══════════════════════════════════════════════════════════════════
#  LE RAPPORT
# ══════════════════════════════════════════════════════════════════

def _f(x, n=4):
    return "—" if x is None else f"{x:.{n}f}"


def _ligne_groupe(nom: str, g) -> str:
    if not g:
        return f"  {nom:<34} —"
    ic = ("" if g["plancher_med_bas"] is None
          else f"  [{g['plancher_med_bas']:.3f} ; {g['plancher_med_haut']:.3f}]")
    court = "" if g["plancher_med_bas"] is not None else f"  {g['ci_raison']}"
    return (f"  {nom:<34} {_f(g['plancher_med'], 3):>7}"
            f" {_f(g['plancher_rms'], 3):>8}"
            f"   {g['n_paires']:>4} {g['n_balises']:>5} {g['n_jours']:>4}"
            f" {g['n_heures']:>7}" + ic + court)


ENTETE_GROUPE = ("  {:<34} {:>7} {:>8}   {:>4} {:>5} {:>4} {:>7}"
                 .format("groupe", "med", "rms", "pair", "bal", "j", "heures"))


def rapport(r: dict, typique: dict | None = None) -> str:
    L = []
    A = L.append
    f = r["fenetre"]
    A("═" * 72)
    A("  PLANCHER DE REPRÉSENTATIVITÉ PAR SITE — demi-variance des")
    A("  paires de balises proches                        (lot L6)")
    A("═" * 72)
    A(f"  fenêtre    : {f['jours_lus']} journée(s) lue(s) sur "
      f"{f['jours_demandes']} demandée(s), fin {f['fin']}"
      + (f" ({f['jours_vides']} vide(s))" if f["jours_vides"] else ""))
    A(f"  archives   : {f['lignes_obs']} lignes d'observation, "
      f"rayon max {f['rayon_max_km']} km")
    A("  réseaux    : " + " · ".join(f"{k} {v}"
                                     for k, v in f["reseaux"].items()))
    x = r["exclusions"]
    A(f"  écartés    : {len(x['paires_doublon'])} paire(s) DOUBLON · "
      f"{len(x['paires_deriveuses'])} paire(s) dont un bout a bougé · "
      f"{x['paire_jours_ecartes']} paire-jours perdus\n"
      f"               · {x['paire_jours_co_implantes']} paire-jours "
      f"CO-IMPLANTÉS (d < {DIST_MIN_KM} km) — sortis du plancher "
      f"spatial, lus en §2")
    if x["paires_doublon"]:
        for p in x["paires_doublon"][:8]:
            A(f"               ⛔ doublon : {p}")
    if x["balises_deplacees"]:
        A(f"               ⚠️ {x['balises_deplacees']} balise(s) ont "
          f"changé de coordonnée pendant la fenêtre (cf. lot L15)")

    A("")
    A("── 1. LE PLANCHER, PAR RAYON ET PAR TYPE DE PAIRE ─────────────────")
    A("  (km/h ; `med` face à `err_vec_med`, `rms` face à `err_vec_rms`)")
    A(ENTETE_GROUPE)
    for rayon, blocs in r["rayons"].items():
        A(f"  ▸ {rayon}")
        for nom, g in blocs.items():
            A(_ligne_groupe("    " + nom, g))
    A("")
    A("  ⛔ COMMENT LIRE CES DEUX LIGNES, ET SEULEMENT COMME ÇA :")
    A("     intra-réseau = MINORANT (mât, firmware et moyennage")
    A("       communs s'annulent dans la soustraction) ;")
    A("     inter-réseaux = MAJORANT (hauteur de capteur, pas de temps")
    A("       et arrondi différents s'y AJOUTENT).")
    A("     Le vrai plancher est ENTRE LES DEUX. Publier « le »")
    A("     plancher sans dire de quel côté on l'a pris, c'est publier")
    A("     un nombre juste au hasard.")

    q = r.get("quasi_identiques") or {}
    if q.get("n_paires"):
        A("")
        A("  ⛔ ET LE MÊME PIÈGE SURVIT AU-DELÀ DE 100 m — LIRE CECI")
        A("     AVANT LES CHIFFRES CI-DESSUS.")
        A(f"     {q['n_paires']} paires distantes de moins de "
          f"{q['seuil_km']} km s'accordent à moins de")
        A(f"     {q['seuil_kmh']} km/h médian : ce sont des")
        A("     REPUBLICATIONS à coordonnée décalée, pas des voisins.")
        for nom, n in list(q.get("par_couple", {}).items())[:6]:
            A(f"       {nom:<44} {n:>4} paires")
        A("     les plus flagrantes :")
        for e in q["paires"][:6]:
            A(f"       {e['paire']:<46} {e['dist_km']:>6.3f} km "
              f"{e['ecart_med']:>6.2f} km/h  {e['n_jours']} j")
        hq = r.get("hors_quasi")
        if hq:
            A("")
            A("     ⭐ LE PLANCHER RELU SANS ELLES (< 3 km, toutes paires) :")
            A(_ligne_groupe("     hors quasi-identiques", hq))
            A("     C'est CE chiffre-là qui vaut, et l'écart avec la")
            A("     ligne « tous » du tableau est le prix de la")
            A("     duplication des réseaux d'observation.")

    A("")
    A("── 2. LE SOCLE D'OBSERVATION — les paires à moins de 100 m ────────")
    s = r.get("socle")
    if not s:
        A("  (aucune paire co-implantée)")
    else:
        A(f"  {s['n_paires']} paires · {s['n_balises']} balises · "
          f"{s['n_heures']} heures · distance médiane "
          f"{_f(s['dist_med_km'], 3)} km")
        A(f"  écart médian ENTRE LES DEUX LECTURES : "
          f"{_f((s['plancher_med'] or 0) * RACINE_2, 3)} km/h "
          f"(rms {_f((s['plancher_rms'] or 0) * RACINE_2, 3)})")
        A("  ⛔ CE N'EST PAS UN PLANCHER SPATIAL, et ces paires sont hors")
        A("     de tout le reste du rapport. À d ≈ 0 il n'y a aucune")
        A("     séparation à décorréler : ce qu'on lit là est la CHAÎNE")
        A("     — le même capteur republié par deux réseaux, deux")
        A("     inscriptions du même mât, ou deux coordonnées bidon.")
        A("  ⭐ Ça reste un plancher : un modèle ne peut pas être plus")
        A("     juste que le désaccord de deux lectures du même vent.")
        A("     ⓘ L'écart est publié BRUT (pas divisé par √2) : les deux")
        A("     flux ne sont pas deux capteurs indépendants.")
        if r.get("socle_couples"):
            A("")
            A("  par couple de fournisseurs (écart médian brut, km/h) :")
            for nom, g in r["socle_couples"].items():
                A(f"    {nom:<40} {_f((g['plancher_med'] or 0) * RACINE_2, 3):>7}"
                  f"   {g['n_paires']:>4} paires {g['n_heures']:>7} h")
        if r.get("socle_extremes"):
            A("")
            A("  ⚠️ MÊME POINT, VENTS INCOMPATIBLES — un défaut de")
            A("     référentiel, pas un socle. Les dix pires :")
            for e in r["socle_extremes"]:
                A(f"    {e['paire']:<46} {e['dist_km']:>6.3f} km "
                  f"{e['ecart_med']:>7.2f} km/h  {e['n_jours']} j")

    A("")
    A("── 3. CE QU'UNE CORRECTION DE SITE PEUT REPRENDRE, ET LE RESTE ────")
    A("  {:<34} {:>8} {:>12} {:>12} {:>10}".format(
        "groupe", "quad.", "persistant", "fluctuant", "résidu"))
    for rayon, blocs in r["rayons"].items():
        for nom, g in blocs.items():
            if not g or g["plancher_quad"] is None:
                continue
            A("  {:<34} {:>8} {:>12} {:>12} {:>10}".format(
                f"{rayon} · {nom}", _f(g["plancher_quad"], 3),
                _f(g["plancher_persistant"], 3),
                _f(g["plancher_fluctuant"], 3),
                _f(g["residu_identite"], 8)))
    A("  ⓘ persistant² + fluctuant² = quadratique² — le `résidu` EST le")
    A("    contrôle de cette identité, pas une approximation. S'il")
    A("    grossit, c'est que les heures vectorielles ne sont plus les")
    A("    mêmes des deux côtés du partage.")
    A("  ⭐ Le FLUCTUANT est le vrai plancher : ni le lot S2 (biais de")
    A("    site), ni une maille plus fine ne le reprendront. Le")
    A("    PERSISTANT borne, lui, ce qu'un `err_corrigee` peut espérer.")

    A("")
    A("── 4. LE PROFIL PAR DISTANCE — la PENTE, pas le point ─────────────")
    A(ENTETE_GROUPE)
    for b, g in r["profil"].items():
        A(_ligne_groupe(b, g))
    A("  ⓘ Un plancher qui CROÎT avec la distance mesure bien de la")
    A("    décorrélation spatiale (donc de la représentativité). Un")
    A("    profil PLAT dirait qu'on mesure surtout du bruit")
    A("    d'instrument — et le chiffre ne s'appellerait plus pareil.")

    for titre, cle in (("5. PAR COUPLE DE FOURNISSEURS", "reseaux"),
                       ("6. PAR CLASSE DE TERRAIN — LE LIVRABLE DU LOT",
                        "terrain"),
                       ("7. PAR DÉNIVELÉ ENTRE LES DEUX BALISES",
                        "denivele"),
                       ("8. PAR RELIEF RÉSOLU PAR AROME DANS 8 km",
                        "relief")):
        A("")
        A(f"── {titre} " + "─" * max(0, 66 - len(titre)))
        A(ENTETE_GROUPE)
        vide = True
        for nom, g in r[cle].items():
            if not g:
                continue
            vide = False
            etiq = LANDFORM_FR.get(nom, nom) if cle == "terrain" else nom
            marque = "" if g["n_paires"] >= MIN_PAIRES_CLASSE else "  ⚠️ trop peu"
            A(_ligne_groupe(etiq, g) + marque)
        if vide:
            A("  (rien — référentiel absent ou aucune paire classée)")
        if cle == "terrain" and (typique or {}).get("par_landform"):
            A("")
            A("  ⭐ CLASSE PAR CLASSE, face à l'erreur DE CETTE CLASSE :")
            A("  {:<14} {:>9} {:>11} {:>11} {:>10}".format(
                "classe", "plancher", "err_vec_med", "part var.",
                "err propre"))
            for nom, g in r["terrain"].items():
                e = (typique["par_landform"].get(nom) or {}).get("med")
                if not g or g["plancher_med"] is None or e is None:
                    continue
                pl = g["plancher_med"]
                pr = (math.sqrt(e * e - pl * pl) if pl < e else None)
                A("  {:<14} {:>9.3f} {:>11.3f} {:>10.1f}% {:>10}".format(
                    LANDFORM_FR.get(nom, nom), pl, e,
                    100 * (pl / e) ** 2,
                    "IMPOSSIBLE" if pr is None else f"{pr:.3f}"))
            brut, propre = [], []
            for nom, g in r["terrain"].items():
                e = (typique["par_landform"].get(nom) or {}).get("med")
                if (not g or g["plancher_med"] is None or e is None
                        or g["plancher_med"] >= e):
                    continue
                brut.append(e)
                propre.append(math.sqrt(e * e - g["plancher_med"] ** 2))
            if len(brut) >= 3:
                def _cv(v):
                    m = sum(v) / len(v)
                    return math.sqrt(sum((x - m) ** 2 for x in v)
                                     / len(v)) / m
                A("")
                A(f"  ⭐ DISPERSION ENTRE CLASSES — brut {100 * _cv(brut):.1f} %"
                  f"  ·  après retrait du plancher {100 * _cv(propre):.1f} %"
                  f"  ({len(brut)} classes)")
                A("     C'est le contrôle qui vaut plus que chaque")
                A("     ligne prise séparément : si le plancher est bien")
                A("     ce qu'on croit, l'erreur PROPRE des modèles doit")
                A("     être à peu près la MÊME partout — un modèle n'a")
                A("     aucune raison d'être bon en vallée et mauvais en")
                A("     crête, c'est la balise qui change, pas lui. Une")
                A("     dispersion qui s'effondre valide la méthode par")
                A("     un chemin indépendant ; une dispersion qui ne")
                A("     bouge pas (ou grandit) la réfute.")
            A("  ⛔ « IMPOSSIBLE » n'est pas une panne : c'est un")
            A("     plancher qui DÉPASSE l'erreur observée de la même")
            A("     classe. Deux lectures, une seule à retenir — soit")
            A("     les paires de cette classe ne sont pas des voisins")
            A("     comparables (dénivelé, exposition), soit la classe")
            A("     est trop petite. Le rapport le DIT au lieu de")
            A("     publier une racine de nombre négatif.")

    A("")
    A("── 9. LES PAIRES LES PLUS PROCHES (hors co-implantées) ────────────")
    A("  {:<44} {:>7} {:>7} {:>4} {:>8}".format(
        "paire", "km", "heures", "j", "planch."))
    for p in r["paires_les_plus_proches"]:
        A("  {:<44} {:>7.3f} {:>7} {:>4} {:>8}".format(
            p["paire"], p["dist_km"], p["n_heures"], p["n_jours"],
            _f(p["plancher_med"], 3)))

    if typique:
        A("")
        A("── 10. CE QUE ÇA CHANGE À LA LECTURE DES ÉCARTS ENTRE MODÈLES ────")
        A(lecture(r, typique))
    A("")
    A("═" * 72)
    return "\n".join(L)


def lecture(r: dict, typique: dict) -> str:
    """Le seul endroit du fichier qui INTERPRÈTE — et qui le dit.

    ⛔ TROIS RÉSULTATS, ET LE TROISIÈME EST CONTRE-INTUITIF.

    (1) La part IRRÉDUCTIBLE de l'erreur publiée. Si `plancher` et
        l'erreur propre du modèle sont indépendantes,
        err_obs² = err_modele² + plancher². La part de VARIANCE que
        personne ne reprendra vaut donc (plancher/err_obs)².

    (2) Le plafond de SKILL. Un site dont le plancher est haut ne
        montrera jamais un bon score absolu, quel que soit le modèle.
        Comparer deux SITES sur `err_vec_med` n'a donc pas de sens ;
        comparer deux MODÈLES sur le même site en a, puisque le
        plancher leur est commun.

    (3) ⭐ ET LE PLANCHER N'ATTÉNUE PAS LES ÉCARTS ENTRE MODÈLES : IL
        LES AMPLIFIE. C'est l'inverse de l'intuition (« le bruit noie
        les différences »). Deux modèles séparés de δ sur l'erreur
        OBSERVÉE sont séparés de δ·(err_obs/err_modele) sur leur erreur
        PROPRE, et ce facteur est > 1 par construction. Conséquence
        directe et chiffrable pour ce produit : le seuil pratique
        `MIN_RELATIVE_GAP` = 15 %, appliqué à l'erreur observée,
        exige en réalité davantage de l'erreur propre des modèles.

    ⚠️ ET LA LIMITE DE (1) ET (3), qui n'est pas une précaution de
    style : la soustraction en quadrature suppose l'INDÉPENDANCE entre
    l'erreur du modèle et l'erreur de représentativité. Elle est
    défendable pour la part FLUCTUANTE (sous-maille, que le modèle ne
    peut pas connaître) ; elle est fausse pour la part PERSISTANTE (un
    modèle qui ignore l'abri d'un site se trompe DANS le même sens que
    l'abri). Le calcul est donc mené deux fois — plancher complet et
    plancher fluctuant seul — et l'écart entre les deux lectures EST
    l'incertitude de cette hypothèse.
    """
    L = []
    A = L.append
    err = typique.get("err_vec_med")
    err_rms = typique.get("err_vec_rms")
    if err is None:
        return "  (pas d'erreur typique mesurée — comparaison impossible)"
    A(f"  erreur typique MESURÉE : err_vec_med médiane = {err:.3f} km/h · "
      f"err_vec_rms {_f(err_rms, 3)} "
      f"({typique['n_lignes']} lignes, {typique['jour']}, "
      f"lead +{typique['lead_h']} h)")

    bloc = r["rayons"].get(f"< {RAYONS_KM[1]} km", {})

    def _tableau(titre, reference, lignes):
        """⚠️ UN PLANCHER MÉDIAN NE SE COMPARE QU'À UNE ERREUR MÉDIANE.
        Les deux tableaux existent pour ça : mélanger les échelles
        rendrait un nombre crédible et faux d'un bon tiers."""
        if reference is None or not lignes:
            return
        A("")
        A(f"  ▸ {titre} (référence {reference:.3f} km/h)")
        A("  {:<26} {:>9} {:>10} {:>11} {:>11} {:>9}".format(
            "hypothèse", "plancher", "part var.", "err propre",
            "amplif. δ", "15 % ⇒"))
        for nom, p_ in lignes:
            if p_ is None or p_ >= reference:
                A("  {:<26} {:>9} {:>10} {:>11} {:>11} {:>9}".format(
                    nom, _f(p_, 3), "—", "—", "—", "—"))
                continue
            part = (p_ / reference) ** 2
            propre = math.sqrt(reference * reference - p_ * p_)
            amp = reference / propre
            A("  {:<26} {:>9.3f} {:>9.1f}% {:>11.3f} {:>11.3f} {:>8.1f}%"
              .format(nom, p_, 100 * part, propre, amp,
                      100 * INF.MIN_RELATIVE_GAP * amp * amp))

    _tableau("MÉDIANE — face à `err_vec_med`, la colonne du classement",
             err,
             [({"intra_reseau": "intra-réseau (MINORANT)",
                "inter_reseaux": "inter-réseaux (MAJORANT)",
                "tous": "toutes paires"}[nom],
               (bloc.get(nom) or {}).get("plancher_med"))
              for nom in ("intra_reseau", "inter_reseaux", "tous")
              if bloc.get(nom)])

    g = bloc.get("tous") or {}
    _tableau("QUADRATIQUE — face à `err_vec_rms`, la colonne du duel L1",
             err_rms,
             [("plancher complet", g.get("plancher_quad")),
              ("dont FLUCTUANT seul", g.get("plancher_fluctuant"))])
    if (err_rms is not None and g.get("plancher_quad") is not None
            and g["plancher_quad"] >= err_rms):
        A("  ⛔ LE PLANCHER QUADRATIQUE DÉPASSE L'ERREUR QU'IL BORNE —")
        A("     donc il ne la borne pas. Ce n'est pas une panne, c'est")
        A("     ce qu'une moyenne de CARRÉS fait d'une queue : quelques")
        A("     paires à coordonnée fausse ou à exposition opposée")
        A("     pèsent au carré et emportent la statistique. Les mêmes")
        A("     paires ne déplacent pas la MÉDIANE, qui, elle, borne")
        A("     bien son erreur. ⇒ **la lecture quadratique de ce lot")
        A("     est INEXPLOITABLE en l'état ; c'est la lecture médiane")
        A("     qui fait foi**, et le partage persistant/fluctuant du")
        A("     §3 hérite du même défaut : il se lit en PROPORTION")
        A("     (quelle part est reprenable), jamais en km/h absolus.")

    A("")
    A("  ⭐ colonne « 15 % ⇒ » : ce que le seuil pratique de")
    A(f"     `MIN_RELATIVE_GAP` ({100 * INF.MIN_RELATIVE_GAP:.0f} %), lu sur")
    A("     l'erreur OBSERVÉE, exige en fait de l'erreur PROPRE des")
    A("     modèles. Le classement est donc plus SÉVÈRE qu'il n'en a")
    A("     l'air, pas moins — le plancher AMPLIFIE les écarts entre")
    A("     modèles, il ne les noie pas. C'est l'inverse de")
    A("     l'intuition, et c'est le résultat le plus utile du lot.")
    A("  ⚠️ La soustraction en quadrature suppose l'INDÉPENDANCE entre")
    A("     l'erreur du modèle et celle de représentativité. Elle est")
    A("     défendable pour la part FLUCTUANTE (sous-maille, que le")
    A("     modèle ne peut pas connaître), fausse pour la part")
    A("     PERSISTANTE (un modèle qui ignore l'abri d'un site se")
    A("     trompe DANS le même sens que l'abri). L'écart entre les")
    A("     deux lignes du second tableau EST l'incertitude de cette")
    A("     hypothèse ; il n'y a pas de troisième chiffre à publier.")
    A("  ⛔ et l'inverse pour les SITES : un site dont le plancher est")
    A("     haut plafonne le score de tout le monde. Un palmarès de")
    A("     BALISES sur `err_vec_med` classe les sites, pas les")
    A("     modèles — c'est la lacune nº 1 de l'audit §4.1, et c'est")
    A("     ce nombre-ci qui permettrait de la fermer (publier")
    A("     err/plancher, ou ne comparer qu'à l'intérieur d'une")
    A("     classe de terrain).")
    if typique.get("par_source"):
        A("")
        A("  err_vec_med médiane par réseau d'observation :")
        for k, v in typique["par_source"].items():
            A(f"    {k:<14} n={v['n']:<6} {v['med']:.3f} km/h")
    return "\n".join(L)


# ══════════════════════════════════════════════════════════════════
#  CLI
# ══════════════════════════════════════════════════════════════════

def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Plancher de représentativité "
                                            "par site (lot L6)")
    p.add_argument("--root", default="/var/lib/bw-model-verif")
    p.add_argument("--fin", default=None, help="dernier jour lu (défaut : hier)")
    p.add_argument("--jours", type=int, default=30)
    p.add_argument("--rayon", type=float, default=RAYONS_KM[1],
                   help="rayon maximal des paires (km)")
    p.add_argument("--sans-zones", action="store_true",
                   help="ne pas lire `station_zone` (ni terrain ni dénivelé)")
    p.add_argument("--sans-typique", action="store_true",
                   help="ne pas lire `model_verif_daily`")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    fin = (datetime.strptime(a.fin, "%Y-%m-%d") if a.fin
           else datetime.now(timezone.utc).replace(tzinfo=None)
           - timedelta(days=1))
    fin = fin.replace(hour=0, minute=0, second=0, microsecond=0)
    crier = (lambda *_a, **_k: None) if a.json else print

    root = pathlib.Path(a.root)
    storage = None
    try:
        import storage as ST                      # noqa: PLC0415
        storage = ST.make_storage()
    except Exception:                             # noqa: BLE001
        storage = None                            # archives locales seules

    crier("▶ référentiels")
    zones = {} if a.sans_zones else charger_zones(crier)
    relief = charger_orographie(root, crier)
    crier(f"▶ lecture des archives obs ({a.jours} j, fin {fin:%Y-%m-%d})")
    r = sonder(root, fin, a.jours, rayon_max=a.rayon, storage=storage,
               zones=zones, relief=relief, crier=crier)
    typique = ({} if a.sans_typique
               else erreur_typique(fin, zones=zones, crier=crier))

    if a.json:
        print(json.dumps({"sonde": r, "typique": typique},
                         ensure_ascii=False, indent=1))
    else:
        print(rapport(r, typique))
    return 0


if __name__ == "__main__":
    sys.exit(main())
