#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════
#  ingest_decos_pge.py — base de décollages pour l'amortissement kk7
#  près des décos (`KK7_LAUNCH_DISCOUNT_RADIUS`, fusion expérimentale).
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
    for cc in COUNTRIES:
        raw = fetch(cc)
        d = json.load(io.BytesIO(raw))
        n_before = len(points)
        for feat in d.get("features", []):
            props = feat.get("properties", {})
            if props.get("place") != "paragliding takeoff":
                continue  # garde-fou : on ne veut QUE des décollages
            lon, lat = feat["geometry"]["coordinates"]
            key = (round(lat, 4), round(lon, 4))
            if key in seen:
                continue  # doublon (site proche frontière listé par 2 pays)
            seen.add(key)
            name = str(props.get("name", "")).strip()[:NAME_MAX_LEN]
            alt = parse_altitude(props.get("takeoff_altitude"))
            sectors = parse_sectors(props)
            points.append([key[0], key[1], name, alt, sectors])
        print(f"  {cc}: +{len(points) - n_before} décos", file=sys.stderr)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(points, f, separators=(",", ":"), ensure_ascii=False)
    size_kb = os.path.getsize(OUT) / 1024
    print(f"\n{len(points)} décos écrits dans {OUT} ({size_kb:.0f} Ko)", file=sys.stderr)


if __name__ == "__main__":
    main()
