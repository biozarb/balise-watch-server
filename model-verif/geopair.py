#!/usr/bin/env python3
"""
geopair.py — L'APPARIEMENT GÉOGRAPHIQUE, séparé de ce qu'on apparie.

    Session 21/08/2026, lot S1.
    Conception complète : `claude/lot-s1-conception-appariement-21-08.md`.

┌─ POURQUOI CE FICHIER EXISTE ────────────────────────────────────────┐
│ `score.py::daily_rows` n'apparie QUE par identité exacte            │
│ (`source:station_id`). C'est juste pour le vent : la prévision est  │
│ demandée à la coordonnée de la balise, donc les deux bouts sont le  │
│ même point.                                                          │
│                                                                      │
│ Ça ne l'est plus dès qu'une variable est PRÉVUE quelque part et      │
│ OBSERVÉE ailleurs. C'est le cas de la pression : `pmsl` n'est        │
│ archivé qu'aux ~648 coordonnées Pioupiou, qui ne mesurent jamais de  │
│ pression ; les quatre réseaux qui en mesurent sont ailleurs.         │
│ Ce sera le cas de la prochaine variable synoptique qu'on voudra      │
│ noter, à l'identique.                                                │
│                                                                      │
│ D'où un module, et pas un `if variable == "pres"` dans `daily_rows`. │
└──────────────────────────────────────────────────────────────────────┘

═══ CE QUE CE MODULE NE FAIT PAS, ET C'EST DÉLIBÉRÉ ═══

Il ne lit aucun fichier, n'ouvre aucune connexion, n'importe ni
`score.py`, ni `scoring.py`, ni numpy. Il prend deux listes de dicts et
rend un dictionnaire. C'est ce qui le rend testable seul
(`test_geopair.py`) et réutilisable par autre chose que la notation — le
S6 aura exactement la même question pour les stations de radiosondage.

Il ne connaît AUCUNE variable. Il n'y a ni « pression » ni « vent » dans
ce fichier : les plafonds arrivent par argument.

═══ ⛔ CE QU'IL NE FAUT PAS EN FAIRE ═══

**Ne pas apparier le VENT avec ça.** Le vent à 10 m d'une balise de
décollage n'est pas un champ synoptique décalé de quelques kilomètres :
c'est le vent DE CE SITE-LÀ, et le lot S2 existe tout entier parce que
ce biais de site est énorme. Apparier un METAR d'aérodrome au Pioupiou
d'une crête à 30 km produirait des lignes, un `n` et un classement —
tous faux, et rigoureusement indistinguables d'un vrai une fois publiés.

L'autorisation d'apparier géographiquement se déclare PAR VARIABLE, avec
sa raison écrite, dans `score.py` (`GEOPAIR_VARIABLES`). Un mécanisme
général qui marche est aussi un mécanisme général qu'on peut brancher là
où il ne faut pas.

═══ LES TROIS BORNES, ET POURQUOI IL EN FAUT TROIS ═══

Mesuré le 21/08 sur deux réseaux indépendants (Météo-France 168 stations
calibrées / 48 h, Infoclimat 764 stations amateur / 30 h) — §1 de la
note de conception :

  · la DISTANCE horizontale coûte peu et régulièrement : l'écart médian
    de pression entre deux baromètres calibrés passe de 0,10 hPa à
    5-10 km à 1,00 hPa à 160-200 km ;
  · l'ÉCART D'ALTITUDE coûte AUTANT. À moins de 30 km, 300 à 600 m de
    dénivelé coûtent 0,286 hPa — le même ordre que 60 à 100 km à
    altitude égale (0,500). Sur la tendance à 3 h d'Infoclimat, 600 à
    1 200 m de dénivelé à moins de 30 km (0,400) coûtent PLUS que
    100-200 km à altitude égale (0,360) ;
  · l'ALTITUDE ABSOLUE est une borne à part, et elle existait déjà :
    `PRESSURE_MAX_ALT = 1000` (`web/src/lib/pressure.ts`), établie le
    03/08 sur Samedan (LSZS, 1 708 m) qui annonçait Q1025 quand toute la
    Suisse était entre Q1013 et Q1018, et restait 2 à 3 hPa au-dessus de
    ses voisins MÊME APRÈS conversion en QFF. Au-delà de 1 200 m d'écart,
    la mesure d'Infoclimat retrouve 3,1 à 4,2 hPa quelle que soit la
    distance : ce n'est plus le champ, c'est le désaccord de deux
    réductions au niveau de la mer.

Un plafond à une seule dimension accepterait exactement les paires les
plus fausses. D'où trois.

═══ « LE PLUS PROCHE PARMI LES ÉLIGIBLES », PAS « LE PLUS PROCHE PUIS
    FILTRÉ » ═══

La nuance n'est pas cosmétique. Chercher le plus proche PUIS tester les
plafonds jette une paire parfaitement valable dès qu'un candidat non
éligible se trouve être un peu plus près. Mesuré sur les quatre réseaux
de pression : 5 à 10 POINTS DE COUVERTURE d'écart entre les deux
sémantiques — et c'est le genre d'écart qu'on ne revoit jamais, parce
que le résultat est plausible dans les deux cas.

Le banc `test_geopair.py` garde ce cas précis (n°3).

═══ COÛT MESURÉ, ET POURQUOI IL N'Y A PAS D'INDEX ═══

815 184 distances (1 258 stations × 648 points de prévision) en
**0,75 s**, force brute, Python pur, Mac, 21/08. Aux ~4 000 balises des
cinq réseaux on resterait sous 2,5 s, une fois par journée notée — et le
rejeu met déjà chaque journée en cache (`score.replay_write`).

Un index par tuile de latitude diviserait ça par ~50. Il n'est PAS
écrit : il coûterait vingt lignes et une occasion de se tromper, pour
gagner deux secondes par nuit. **Le seuil où il le deviendrait** : au-delà
de ~50 000 cibles, ou si l'appariement quittait le cache de rejeu pour
être refait à chaque échéance. Ni l'un ni l'autre n'est vrai aujourd'hui.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

#: Rayon terrestre moyen (km), WGS84 — la même valeur que `assign-zones.ts`.
R_TERRE_KM = 6371.0088


def distance_km(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    """Haversine. Erreur < 0,5 % sur la BBOX, largement sous les seuils.

    ⓘ Pourquoi pas une distance euclidienne sur (lat, lon×cos φ) : elle
    serait plus rapide et suffisante ici, mais elle dérive avec la
    latitude et le jour où quelqu'un réutilise ce module hors BBOX il
    n'y aurait rien pour le prévenir. Le coût mesuré ne justifie pas
    l'économie (cf. l'en-tête).
    """
    p1, p2 = math.radians(lat_a), math.radians(lat_b)
    dp = p2 - p1
    dl = math.radians(lon_b - lon_a)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_TERRE_KM * math.asin(min(1.0, math.sqrt(h)))


@dataclass(frozen=True)
class Appariement:
    """Le résultat pour UNE cible. La distance fait partie du résultat.

    ⚠️ `km` et `dz_m` ne sont pas du journal : ils sont publiés sur la
    ligne (`pair_km`, `pair_dz_m`). C'est ce qui rend le plafond
    révisable PAR LA MESURE dans quinze nuits — l'erreur tracée en
    fonction de `pair_km` EST la mesure du compromis — plutôt que par
    une seconde discussion. Sans ces deux colonnes, le choix du plafond
    resterait une opinion pour toujours.
    """
    cle: str
    km: float
    dz_m: float | None


@dataclass
class Bilan:
    """Pourquoi les cibles NON appariées ne le sont pas.

    ⚠️ Une population qui rétrécit sans dire pourquoi se relit six mois
    plus tard comme « le modèle s'est amélioré ». Chaque refus est
    compté et le motif est nommé ; `resume()` est fait pour être
    imprimé tel quel par le run de nuit.
    """
    apparies: int = 0
    sans_altitude: int = 0
    cible_trop_haute: int = 0
    hors_rayon: int = 0
    hors_dz: int = 0
    aucun_candidat: int = 0
    #: Les candidats écartés d'emblée (trop hauts) — compté une fois,
    #: pas une fois par cible, sinon le chiffre ne veut rien dire.
    candidats_trop_hauts: int = 0
    candidats_sans_altitude: int = 0
    distances_km: list[float] = field(default_factory=list)

    def resume(self) -> str:
        med = "—"
        if self.distances_km:
            d = sorted(self.distances_km)
            med = f"{d[len(d) // 2]:.1f} km"
        return (f"{self.apparies} appariées (médiane {med}) ; refusées : "
                f"{self.hors_rayon} hors rayon, {self.hors_dz} hors Δz, "
                f"{self.cible_trop_haute} trop haute, "
                f"{self.sans_altitude} sans altitude, "
                f"{self.aucun_candidat} sans candidat ; "
                f"candidats écartés : {self.candidats_trop_hauts} trop hauts, "
                f"{self.candidats_sans_altitude} sans altitude")


def _alt(p: dict) -> float | None:
    """L'altitude d'un point, en mètres, ou None.

    ⚠️ `dem_alt_m` D'ABORD, et c'est une règle, pas une préférence.
    `station_zone.dem_alt_m` (écrit par le S0.2 pour les 4 019 balises
    des cinq réseaux, 0 manquante) vient des mêmes tuiles Terrarium pour
    tout le monde : c'est la SEULE altitude que comparer ait un sens,
    et la seule qu'aient les points Pioupiou (`collect.load_stations` ne
    stocke que lat/lon/nom).

    ⛔ ET ELLE NE SERT QU'AUX SEUILS. Pour la RÉDUCTION au niveau de la
    mer, c'est l'altitude déclarée par la source (`elev`) qui compte :
    28 m d'erreur décalaient Lugano de 3,3 hPa (mesuré le 03/08). Un
    seuil à 300 m ne voit pas quelques dizaines de mètres ; une
    conversion, si.
    """
    for champ in ("dem_alt_m", "elev"):
        v = p.get(champ)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                return None
    return None


def apparier(cibles: list[dict], candidats: list[dict], *,
             max_km: float,
             max_dz_m: float | None = None,
             max_alt_m: float | None = None,
             cle: str = "cle") -> tuple[dict[str, Appariement], Bilan]:
    """Pour chaque CIBLE, le CANDIDAT le plus proche PARMI LES ÉLIGIBLES.

    `cibles` sont les points d'OBSERVATION (les stations qui mesurent),
    `candidats` les points de PRÉVISION. Le sens compte : chaque
    observation est appariée AU PLUS UNE FOIS (donc comptée une fois
    dans une médiane), tandis qu'un même point de prévision peut servir
    plusieurs observations — mesuré le 21/08 sous 50 km / Δz 300 :
    337 points servent 975 stations, médiane 2, maximum 14.

    ⚠️ CES LIGNES-LÀ SONT CORRÉLÉES ENTRE ELLES, et c'est assumé : même
    décision que les 305 doublons FFVL ↔ Pioupiou du cadrage S0.1
    (« on ne dédoublonne pas »). Sans conséquence tant qu'on publie
    l'erreur brute et le `n` SANS intervalle de confiance — ce que le S1
    fait. Le jour où un IC apparaît, il serait faussement serré : c'est
    l'arbitrage n°1 de la note de conception, et il vit au moment de
    l'AGRÉGATION, pas ici.

    Chaque point (cible ou candidat) est un dict qui porte au minimum
    `lat`, `lon` et la clé nommée par `cle`. `dem_alt_m` ou `elev`
    donnent l'altitude (cf. `_alt`).

    Rend `({clé_cible: Appariement}, Bilan)`. Une cible sans appariement
    est ABSENTE du dictionnaire — jamais présente avec une valeur
    neutre. Une balise-jour sans modèle assez proche est « pas de
    modèle assez proche », **jamais un zéro** : le piège a déjà été payé
    deux fois sur ce chantier (`p01i` du METAR, `gust` vide).
    """
    bilan = Bilan()

    # Les candidats sont préparés UNE FOIS : le filtre d'altitude
    # absolue ne dépend d'aucune cible, l'appliquer dans la boucle
    # interne le rejouerait N fois et fausserait le compte du bilan.
    prets: list[tuple[str, float, float, float | None]] = []
    for c in candidats:
        a = _alt(c)
        if a is None:
            bilan.candidats_sans_altitude += 1
            # Sans altitude on ne peut vérifier NI le plafond absolu NI
            # Δz : le candidat est écarté, pas apparié « au bénéfice du
            # doute ». Un doute apparié devient un chiffre publié.
            if max_alt_m is not None or max_dz_m is not None:
                continue
        elif max_alt_m is not None and a > max_alt_m:
            bilan.candidats_trop_hauts += 1
            continue
        prets.append((str(c[cle]), float(c["lat"]), float(c["lon"]), a))

    out: dict[str, Appariement] = {}
    for t in cibles:
        k = str(t[cle])
        a_t = _alt(t)
        if a_t is None and (max_alt_m is not None or max_dz_m is not None):
            bilan.sans_altitude += 1
            continue
        if max_alt_m is not None and a_t is not None and a_t > max_alt_m:
            bilan.cible_trop_haute += 1
            continue

        lat_t, lon_t = float(t["lat"]), float(t["lon"])
        meilleur: tuple[float, float, str] | None = None
        vu_dans_rayon = False
        for k_c, lat_c, lon_c, a_c in prets:
            d = distance_km(lat_t, lon_t, lat_c, lon_c)
            if d > max_km:
                continue
            vu_dans_rayon = True
            dz = None
            if a_t is not None and a_c is not None:
                dz = abs(a_t - a_c)
            if max_dz_m is not None:
                if dz is None or dz > max_dz_m:
                    continue
            # Ordre de départage ÉCRIT et TOTAL : distance, puis |Δz|,
            # puis la clé. Sans le troisième terme, deux exécutions
            # pourraient rendre deux appariements différents sur une
            # égalité — et un rejeu ne serait plus un rejeu.
            cle_tri = (d, dz if dz is not None else math.inf, k_c)
            if meilleur is None or cle_tri < meilleur:
                meilleur = cle_tri

        if meilleur is None:
            if not prets:
                bilan.aucun_candidat += 1
            elif vu_dans_rayon:
                bilan.hors_dz += 1
            else:
                bilan.hors_rayon += 1
            continue

        d, dz, k_c = meilleur
        out[k] = Appariement(cle=k_c, km=round(d, 3),
                             dz_m=None if dz == math.inf else round(dz, 1))
        bilan.apparies += 1
        bilan.distances_km.append(d)

    return out, bilan
