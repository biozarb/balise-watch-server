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
#  `PWA/web/public/data/decos.json` — tableau compact `[[lat, lon], ...]`
#  (4 décimales, ~11 m de précision, largement suffisant pour un
#  amortissement à l'échelle de quelques centaines de mètres). PAS de
#  nom/altitude/description : on n'en a pas besoin pour une distance, et
#  ça garde le fichier petit (chargé une fois par session côté client,
#  cf. lib/decos.ts).
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


def main() -> None:
    seen: set[tuple[float, float]] = set()
    points: list[list[float]] = []
    for cc in COUNTRIES:
        raw = fetch(cc)
        d = json.load(io.BytesIO(raw))
        n_before = len(points)
        for feat in d.get("features", []):
            if feat.get("properties", {}).get("place") != "paragliding takeoff":
                continue  # garde-fou : on ne veut QUE des décollages
            lon, lat = feat["geometry"]["coordinates"]
            key = (round(lat, 4), round(lon, 4))
            if key in seen:
                continue  # doublon (site proche frontière listé par 2 pays)
            seen.add(key)
            points.append([key[0], key[1]])
        print(f"  {cc}: +{len(points) - n_before} décos", file=sys.stderr)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(points, f, separators=(",", ":"))
    size_kb = os.path.getsize(OUT) / 1024
    print(f"\n{len(points)} décos écrits dans {OUT} ({size_kb:.0f} Ko)", file=sys.stderr)


if __name__ == "__main__":
    main()
