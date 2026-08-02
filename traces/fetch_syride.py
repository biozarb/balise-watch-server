#!/usr/bin/env python3
"""
fetch_syride.py — Étape 3 v1 (collecte stats Syride, SANS IGC)

Contexte : SONDAGE_TRACES_RESULTATS.md a établi que l'IGC brut Syride
est derrière login (non anonyme) — v2 seulement. En revanche les STATS
par vol (distance, plafond, durée, date, heure) sont publiques via
l'outil "Explorer" du site, endpoint trouvé en session (24/07/2026,
recherche réseau via navigateur piloté) :

    GET https://www.syride.com/scripts/explorer_vols.php
        ?site=<ID>&page=<N>&date=&pilote=&finesse=3&limit=500
        &terrain=&vol=&pays=&zone=&km=0&biplace=0&type=&altitude=0
        &flightTime=0&view=1&l=fr

Vérifié en direct : pagination `page=N` fonctionne jusqu'à la toute
première page (testé site=543/page=3765, atteint mars 2012 puis des
horodatages 1980 visiblement corrompus côté Syride — filtrés ici).
20 lignes par page (le paramètre `limit` ne semble PAS contrôler la
pagination — laissé à 500 par calque avec l'URL observée, non expliqué,
documenté tel quel plutôt que supposé). Le paramètre `date=` avec un
format "DD/MM/YYYY - DD/MM/YYYY" n'a PAS filtré lors du sondage — filtre
par date non fonctionnel par cette voie, à re-sonder plus tard si besoin
(pas bloquant : la pagination brute suffit pour un backfill complet).

Pas de nom de pilote conservé : la colonne pilote n'est pas parsée
(inutile pour le schéma v1 — cf. ETAPE2_SCHEMAS_FEATURES.md §2 — et
alignée sur la règle maison "aucun nom de pilote nulle part dans ce qui
atteint la PWA", ici on ne le stocke même pas en cache brut).

⚠️ BLOQUANT avant tout backfill complet (24/07/2026, à lire avant de
lancer sans --max-pages) : le mail envoyé à Syride
(MAIL_TRACES_SOURCES.md §2) promet explicitement « Je préfère vous
demander avant de lire quoi que ce soit en volume, plutôt que de le
faire en silence ». Ce script existe et est TESTÉ (petit site
aussois_bellecote, 3 vols, 1 page — même volume que le sondage), mais
un run complet sur saint_hilaire (~3765 pages) ou montmin_forclaz
(~1761 pages) attend soit leur réponse, soit une décision explicite de
Yann de passer outre. Ne pas lancer --all ni un site sans --max-pages
sans revérifier ce point.

Politesse réseau (PLAN_BATAILLE_TRACES_SOURCES.md §1 + habitude kk7) :
User-Agent identifiable, délai >= 1.1 s entre pages, cache JSONL
incrémental gitignoré (reprise possible, jamais de re-téléchargement
inutile).

Sortie : traces_cache/syride_<site_slug>.jsonl (une ligne JSON par vol),
gitignoré. `build_site_pack.py` (étape suivante) les assemble avec
DHV + balises en JSON statique par site pour la PWA.

Usage :
    python3 fetch_syride.py --site aussois_bellecote            # petit site, test
    python3 fetch_syride.py --site saint_hilaire --max-pages 5   # test limité
    python3 fetch_syride.py --site saint_hilaire                 # backfill complet (cf. avertissement ci-dessus)
    python3 fetch_syride.py --all                                # les 3 sites tests (idem)
"""

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

UA = "BaliseWatch-traces/0.1 (+argonautes.sim@gmail.com; usage non-commercial, backfill ponctuel)"
PAUSE_S = 1.2  # politesse réseau — même principe que le throttle kk7/Open-Meteo

# Sites tests fixés (SONDAGE_TRACES_RESULTATS.md §1) — IDs Syride
# retrouvés en session (24/07/2026) via l'outil /fr/explorer, requête
# réseau `explorer_vols.php?site=<ID>`.
SITES = {
    "saint_hilaire": 543,
    "montmin_forclaz": 633,
    "aussois_bellecote": 11690,
}

CACHE_DIR = Path(__file__).parent / "traces_cache"
CACHE_DIR.mkdir(exist_ok=True)

BASE_URL = "https://www.syride.com/scripts/explorer_vols.php"


class _RowParser(HTMLParser):
    """Extrait les <tr> du listing Explorer par classe de <td>.

    Classes observées en session (DOM réel, St-Hilaire site=543) :
    searchDistance, searchPlafond, searchTemps, searchDate. Le premier
    <td> (pilote) et le second (nom de site) sont ignorés : voir
    l'en-tête du module — on ne conserve aucun nom de pilote, et le
    site est déjà connu (on l'a demandé par ID)."""

    def __init__(self):
        super().__init__()
        self.rows = []
        self._cur_row = None
        self._cur_cls = None
        self._buf = []
        self.total_vols = None

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "tr":
            self._cur_row = {}
        elif tag == "td" and self._cur_row is not None:
            self._cur_cls = d.get("class", "")
            self._buf = []

    def handle_data(self, data):
        if self._cur_cls is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self._cur_row is not None and self._cur_cls is not None:
            text = "".join(self._buf)
            if self._cur_cls in ("searchDistance", "searchPlafond", "searchTemps", "searchDate"):
                self._cur_row[self._cur_cls] = text
            self._cur_cls = None
        elif tag == "tr" and self._cur_row is not None:
            if any(k in self._cur_row for k in ("searchDistance", "searchDate")):
                self.rows.append(self._cur_row)
            self._cur_row = None


def _parse_total(html: str):
    m = re.search(r"([\d\s,]+)\s*vols", html)
    if not m:
        return None
    return int(re.sub(r"[\s,]", "", m.group(1)))


def _parse_row(raw: dict):
    """Convertit les cellules brutes en champs du schéma vol (v1, sans
    polyline/bbox/categorie_aile — non disponibles dans ce listing)."""
    dist_m = re.search(r"([\d.]+)", raw.get("searchDistance", ""))
    alt_m = re.search(r"([\d.]+)", raw.get("searchPlafond", ""))
    dur_m = re.search(r"(\d{2}):(\d{2}):(\d{2})", raw.get("searchTemps", ""))
    date_block = raw.get("searchDate", "")
    date_m = re.search(r"(\d{2})/(\d{2})/(\d{4})", date_block)
    hours = re.findall(r"(\d{1,2})h", date_block)
    if not (dist_m and alt_m and dur_m and date_m):
        return None
    dd, mm, yyyy = date_m.groups()
    date_iso = f"{yyyy}-{mm}-{dd}"
    # Filtre défensif : quelques horodatages visiblement corrompus côté
    # Syride vus en session (ex. 11/01/1980) — écartés plutôt que gardés
    # comme données valides (méthode maison : on ne suppose pas qu'une
    # date à l'évidence fausse vaut la peine d'être matchée à une
    # météo). Le site existe depuis ~2009 selon le footer du site.
    if int(yyyy) < 2005:
        return None
    h, m_, s = dur_m.groups()
    duree_min = int(h) * 60 + int(m_) + (1 if int(s) >= 30 else 0)
    heure_deco_locale = int(hours[0]) if hours else None
    return {
        "date": date_iso,
        "heure_deco_locale": heure_deco_locale,  # heure LOCALE Paris, pas UTC — conversion à l'étape 4
        "duree_min": duree_min,
        "dist_km": float(dist_m.group(1)),
        "alt_max_m": int(float(alt_m.group(1))),
        "gain_max_m": None,  # pas dans ce listing (nécessiterait l'IGC, v2)
        "categorie_aile": None,  # pas dans ce listing (modèle de voile visible sur la page vol individuelle, pas la classe EN)
    }


def fetch_page(site_id: int, page: int):
    params = (
        f"?date=&site={site_id}&pilote=&finesse=3&limit=500&terrain=&vol="
        f"&pays=&zone=&km=0&biplace=0&type=&altitude=0&flightTime=0&view=1&l=fr"
        f"&page={page}"
    )
    req = urllib.request.Request(BASE_URL + params, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode("utf-8", errors="replace")
    total = _parse_total(html)
    parser = _RowParser()
    parser.feed(html)
    rows = [row for raw in parser.rows if (row := _parse_row(raw)) is not None]
    return total, rows


def fetch_site(site_slug: str, max_pages=None, resume: bool = True):
    """Backfill complet (ou limité à `max_pages` pour un test) d'un
    site. Écrit en JSONL incrémental — reprise possible (`resume`) en
    sautant les pages déjà présentes dans le cache si le fichier existe
    déjà et que son nombre de lignes est cohérent."""
    site_id = SITES[site_slug]
    out_path = CACHE_DIR / f"syride_{site_slug}.jsonl"
    seen_dates_count = 0
    mode = "a"
    if out_path.exists() and resume:
        with open(out_path) as f:
            seen_dates_count = sum(1 for _ in f)
        print(f"[{site_slug}] cache existant : {seen_dates_count} vols déjà en cache, reprise")
    else:
        mode = "w"

    total, rows = fetch_page(site_id, 1)
    if total is None:
        print(f"[{site_slug}] ERREUR : total introuvable (structure de page a peut-être changé)")
        return
    n_pages = (total + 19) // 20
    print(f"[{site_slug}] {total} vols annoncés, ~{n_pages} pages à 20 vols/page")

    start_page = (seen_dates_count // 20) + 1 if resume and seen_dates_count else 1
    end_page = n_pages if max_pages is None else min(n_pages, start_page + max_pages - 1)

    with open(out_path, mode) as f:
        for page in range(start_page, end_page + 1):
            if page == 1 and start_page == 1:
                page_rows = rows
            else:
                time.sleep(PAUSE_S)
                try:
                    _, page_rows = fetch_page(site_id, page)
                except urllib.error.URLError as e:
                    print(f"[{site_slug}] page {page} : erreur réseau ({e}), on continue")
                    continue
            for row in page_rows:
                row["site_id"] = site_slug
                row["source"] = "syride"
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            if page % 50 == 0 or page == end_page:
                print(f"[{site_slug}] page {page}/{n_pages} ({len(page_rows)} vols)")

    print(f"[{site_slug}] terminé (ou pause à {end_page}/{n_pages}) -> {out_path}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--site", choices=list(SITES), help="un seul site")
    ap.add_argument("--all", action="store_true", help="les 3 sites tests")
    ap.add_argument("--max-pages", type=int, default=None, help="limite de pages (test)")
    ap.add_argument("--no-resume", action="store_true", help="ignorer le cache existant, tout re-télécharger")
    args = ap.parse_args()

    targets = list(SITES) if args.all else ([args.site] if args.site else [])
    if not targets:
        ap.error("préciser --site <slug> ou --all")
    for slug in targets:
        fetch_site(slug, max_pages=args.max_pages, resume=not args.no_resume)
