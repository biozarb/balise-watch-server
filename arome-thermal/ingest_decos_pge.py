#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════
#  ingest_decos_pge.py — base de décollages pour l'amortissement kk7
#  près des décos (`KK7_LAUNCH_DISCOUNT_RADIUS`, fusion expérimentale).
#  Depuis le 27/07/2026, écrit AUSSI `atterros.json` (cf. § ATTERROS).
#
#  ── POURQUOI ParaglidingEarth ET PAS FFVL ────────────────────────
#  FFVL était la source recommandée en premier
#  (PROPOSITION_FUSION_CALQUES_THERMIQUES.md §7) : jeu de données
#  officiel, licence Ouverte 2.0, distingue explicitement
#  Décollage/Atterrissage. **Vérifié le 21/07/2026 : bloqué.** Le
#  endpoint data.gouv.fr redirige vers data.ffvl.fr/json/sites.json, qui
#  répond désormais :
#    "This data is now available using an FFVL API key to be requested
#    at : informatique@ffvl.fr"
#  Donc plus de téléchargement anonyme — la doc kk7/FFVL a changé de
#  politique d'accès entre la rédaction du §7 (recherche web générale) et
#  cette vérification directe. Si Yann obtient une clé FFVL, ce script
#  est à remplacer par un appel à leur API — pas à modifier en
#  rafistolant l'existant, la source de données change complètement.
#
#  ── SOURCE UTILISÉE : ParaglidingEarth (pgEarth) ─────────────────
#  API publique, pas de clé requise, endpoint `getCountrySites.php`
#  (résultats déjà filtrés `place=paragliding takeoff`, pas besoin de
#  filtrer nous-mêmes décollage/atterrissage). Licence : les
#  contributions pgEarth depuis décembre 2024 sont sous ODbL 1.0
#  (ShareAlike sur les DONNÉES, pas seulement l'affichage) — à garder en
#  tête si ce fichier est un jour redistribué tel quel plutôt qu'utilisé
#  en interne pour amortir un calcul. Usage ici : lecture pour un calcul
#  de distance (amortissement), rien de republié en tant que base de
#  données consultable.
#
#  ── COUVERTURE ────────────────────────────────────────────────────
#  France + voisins immédiats (principe déjà posé plusieurs fois par
#  Yann dans CLAUDE.md : "toute la France + pays limitrophes, pas
#  seulement une région") : FR, CH, IT, ES, DE. Pas de Benelux/UK —
#  zones de vol negligeables pour ce projet, ajoutable plus tard sans
#  douleur si besoin (juste étendre COUNTRIES).
#
#  ── SORTIE ─────────────────────────────────────────────────────────
#  `PWA/web/public/data/decos.json` — tableau compact de tableaux (pas
#  d'objets : le gain de poids est réel sur ~3300 entrées) :
#
#    [[lat, lon, name, alt, sectors], ...]
#     45.9058, 5.7614, "Colombier", 1509, "00000020"
#
#  - `lat`/`lon` : 4 décimales (~11 m), comme avant.
#  - `name` : tronqué à 48 caractères.
#  - `alt` : `takeoff_altitude` en entier, `null` si vide/non numérique
#    — jamais 0 par défaut, l'absence doit rester visible.
#  - `sectors` : chaîne de 8 caractères, secteurs N,NE,E,SE,S,SW,W,NW
#    dans cet ordre, un caractère "0"/"1"/"2" chacun (valeur brute
#    pgEarth, non interprétée ici — cf. PLAN_KK7_UTILE.md §4.4, le sens
#    exact 0/1/2 est encore [non vérifié]).
#
#  Changement du 25/07/2026 (lot 0, PLAN_KK7_UTILE.md) : cette ligne
#  disait auparavant « PAS de nom/altitude/description : on n'en a pas
#  besoin pour une distance » — c'était vrai TANT QUE le seul usage
#  était l'amortissement kk7 (une distance suffit). Ça cesse de l'être
#  avec le lot 1 (panneau déco : orientation vs vent du jour), qui a
#  besoin du nom, de l'altitude et des secteurs. Pas de `takeoff_description`
#  (poids, pas d'usage identifié) ni des coordonnées de parking/atterro
#  (idem — à rajouter le jour où un lot en aura besoin, pas « au cas
#  où »). Poids mesuré sur ce format : 3313 décos, 160 Ko brut / 65 Ko
#  gzip (contre 56,7 Ko avant, format `[lat, lon]` seul).
#
#  ── ATTERROS (27/07/2026, module de recherche) ────────────────────
#  **Vérifié sur les 5 payloads réels du cache le 27/07/2026** :
#  `getCountrySites.php` ne renvoie AUCUNE feature
#  `place == "paragliding landing"` — 3317/3317 features valent
#  `"paragliding takeoff"`. Le filtre ci-dessous reste donc un garde-fou
#  (il ne retire rien aujourd'hui), il ne suffit PAS à sortir les
#  atterros : ils ne sont pas des features, mais des ATTRIBUTS du
#  décollage (`landing_lat`/`landing_lng`, chaînes, souvent vides).
#  Renseignés sur 1485 sites / 3317 (~45 % — 51 % en FR, 62 % en IT,
#  25 % en DE), soit 1451 points uniques après dédoublonnage.
#
#  Conséquences assumées, à ne pas maquiller côté client :
#  - **Pas de nom propre** : un atterro pgEarth n'a pas de champ nom.
#    On transporte le nom du site PARENT (`name`), et c'est l'UI qui
#    préfixe (« Atterro X ») — le JSON ne fabrique pas de libellé.
#  - **Pas d'altitude, pas de secteurs** : ces champs n'existent pas
#    pour un atterro chez pgEarth. On n'écrit donc PAS de colonne
#    `alt`/`sectors` à `null` : format à 3 éléments, l'absence est
#    structurelle, pas une valeur manquante.
#  - **Couverture partielle** : ~55 % des décos n'ont pas d'atterro
#    renseigné. Ne jamais présenter cette base comme exhaustive.
#
#  Sortie : `PWA/web/public/data/atterros.json`, même esprit compact :
#    [[lat, lon, name_du_site_parent], ...]
#     45.8792, 5.7364, "Colombier"
#
#  Fichier SÉPARÉ de `decos.json` (décision Yann, 27/07/2026) :
#  `decos.json` est préchargé pour l'amortissement kk7 (chemin CHAUD,
#  ThermalGridLayer) alors que les atterros ne servent qu'au module de
#  recherche, chargé à la demande. Fusionner les deux aurait alourdi de
#  ~45 % un fichier du chemin chaud pour un usage ponctuel.
#
#  ── FRAÎCHEUR ──────────────────────────────────────────────────────
#  Pas de cron/Action GitHub pour ce fichier : la base de décos évolue
#  très lentement (nouveaux sites rares) et ce n'est qu'un amortissement
#  d'un calque déjà expérimental — pas justifié de payer l'infrastructure
#  d'un rafraîchissement automatique pour l'instant. Relancer ce script à
#  la main de temps en temps suffit. Si ça change, s'inspirer de
#  `arome-wind/ingest.py` (déjà un vrai pipeline GitHub Action) plutôt
#  que d'improviser un nouveau mécanisme.
# ══════════════════════════════════════════════════════════════════

from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.request

COUNTRIES = ["fr", "ch", "it", "es", "de"]
URL = "https://paraglidingearth.com/api/geojson/getCountrySites.php?iso={cc}"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache_pge")
UA = "balise-watch/ingest_decos_pge (contact via balise-watch project)"
OUT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "web", "public", "data", "decos.json"
)
# Second fichier de sortie (27/07/2026) — cf. § ATTERROS de l'en-tête.
OUT_LANDINGS = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "web", "public", "data", "atterros.json"
)


def fetch(cc: str) -> bytes:
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{cc}.json")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    req = urllib.request.Request(URL.format(cc=cc), headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    with open(path, "wb") as f:
        f.write(data)
    time.sleep(0.3)  # politesse, même logique que compare_kk7.py
    return data


SECTOR_ORDER = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
NAME_MAX_LEN = 48


def parse_altitude(raw: str | None) -> int | None:
    """`takeoff_altitude` pgEarth est une chaîne, parfois vide, parfois non
    numérique. `None` si absent/invalide — jamais 0 par défaut, l'absence
    doit rester visible côté client (même règle que nearestDecoDistanceKm)."""
    if raw is None:
        return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        return int(round(float(raw)))
    except ValueError:
        return None


def parse_landing(props: dict) -> tuple[float, float] | None:
    """Coordonnées de l'atterrissage rattaché au site, ou `None`.

    `landing_lat`/`landing_lng` sont des CHAÎNES chez pgEarth, vides dans
    ~55 % des cas (cf. § ATTERROS de l'en-tête). `(0, 0)` est rejeté
    explicitement : c'est le remplissage classique d'un champ jamais
    saisi, pas un point au large du golfe de Guinée. Même règle que
    `parse_altitude` — mieux vaut l'absence qu'une valeur inventée."""
    raw_lat = str(props.get("landing_lat", "")).strip()
    raw_lon = str(props.get("landing_lng", "")).strip()
    if not raw_lat or not raw_lon:
        return None
    try:
        lat = float(raw_lat)
        lon = float(raw_lon)
    except ValueError:
        return None
    if lat == 0 and lon == 0:
        return None
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return None
    return (round(lat, 4), round(lon, 4))


def parse_sectors(props: dict) -> str:
    """Chaîne de 8 caractères N,NE,E,SE,S,SW,W,NW (ordre fixe), un digit
    "0"/"1"/"2" par secteur. Valeur brute pgEarth non interprétée ici — cf.
    PLAN_KK7_UTILE.md §4.4."""
    out = []
    for sector in SECTOR_ORDER:
        v = str(props.get(sector, "0")).strip()
        out.append(v if v in ("0", "1", "2") else "0")
    return "".join(out)


def main() -> None:
    seen: set[tuple[float, float]] = set()
    points: list[list] = []
    # Dédoublonnage des atterros INDÉPENDANT de celui des décos : deux
    # décollages voisins peuvent partager le même atterrissage (vallée
    # commune), c'est même fréquent — sans set dédié, on écrirait deux
    # fois le même point sous deux noms de site différents.
    seen_landings: set[tuple[float, float]] = set()
    landings: list[list] = []
    n_place_other = 0
    for cc in COUNTRIES:
        raw = fetch(cc)
        d = json.load(io.BytesIO(raw))
        n_before = len(points)
        n_land_before = len(landings)
        for feat in d.get("features", []):
            props = feat.get("properties", {})
            if props.get("place") != "paragliding takeoff":
                # Garde-fou historique : on ne veut QUE des décollages ici.
                # Vérifié le 27/07/2026 — pgEarth ne renvoie de toute façon
                # QUE des `paragliding takeoff` sur cet endpoint (0 rejet
                # sur 3317 features). Le compteur ci-dessous existe pour
                # que ça se VOIE tout de suite si ça change un jour, plutôt
                # que de perdre silencieusement des features.
                n_place_other += 1
                continue
            lon, lat = feat["geometry"]["coordinates"]
            key = (round(lat, 4), round(lon, 4))
            if key in seen:
                continue  # doublon (site proche frontière listé par 2 pays)
            seen.add(key)
            name = str(props.get("name", "")).strip()[:NAME_MAX_LEN]
            alt = parse_altitude(props.get("takeoff_altitude"))
            sectors = parse_sectors(props)
            points.append([key[0], key[1], name, alt, sectors])
            # Atterro rattaché au site, quand pgEarth le renseigne. Nom du
            # site PARENT tel quel — le préfixe « Atterro … » est posé par
            # l'UI, pas fabriqué ici (cf. § ATTERROS de l'en-tête).
            land = parse_landing(props)
            if land is not None and land not in seen_landings:
                seen_landings.add(land)
                landings.append([land[0], land[1], name])
        print(
            f"  {cc}: +{len(points) - n_before} décos, "
            f"+{len(landings) - n_land_before} atterros",
            file=sys.stderr,
        )

    if n_place_other:
        print(
            f"\n⚠️  {n_place_other} features ignorées (place != 'paragliding takeoff') — "
            f"pgEarth n'en renvoyait aucune le 27/07/2026, vérifier ce qui a changé",
            file=sys.stderr,
        )

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(points, f, separators=(",", ":"), ensure_ascii=False)
    size_kb = os.path.getsize(OUT) / 1024
    print(f"\n{len(points)} décos écrits dans {OUT} ({size_kb:.0f} Ko)", file=sys.stderr)

    with open(OUT_LANDINGS, "w") as f:
        json.dump(landings, f, separators=(",", ":"), ensure_ascii=False)
    land_kb = os.path.getsize(OUT_LANDINGS) / 1024
    pct = 100 * len(landings) / len(points) if points else 0
    print(
        f"{len(landings)} atterros écrits dans {OUT_LANDINGS} ({land_kb:.0f} Ko) "
        f"— {pct:.0f} % des décos ont un atterro renseigné chez pgEarth",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
