#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════
#  fusion_ffvl.py — fusion des terrains FFVL (open data) dans
#  decos.json / atterros.json (13/11/2026). Appelé par
#  ingest_decos_pge.py après la lecture pgEarth.
#
#  ── LA RÈGLE (décision Yann, 13/11/2026) ──────────────────────────
#  « Si doublon : on prend FFVL, et on garde les uniques d'un côté et
#  de l'autre. » Donc trois populations :
#    · 'fp' — doublon : position, nom, altitude, orientations, statut
#             FFVL ; le nom pgEarth est gardé en ALIAS (recherche) ;
#    · 'f'  — FFVL seule ;
#    · 'p'  — pgEarth seule (dont tout l'étranger : CH, IT, ES, DE, AT).
#
#  ── QU'EST-CE QU'UN DOUBLON, MESURÉ LE 13/11 ──────────────────────
#  Sur les 2 156 décos pgEarth de la zone France, distance au déco FFVL
#  le plus proche : 443 à ≤ 50 m, 645 à ≤ 200 m, 681 à ≤ 300 m, puis la
#  courbe s'aplatit (733 à 500 m, 776 à 1 km). Sous 300 m, les noms
#  diffèrent souvent sans que ce soit deux sites (pgEarth dit
#  « Montgellafrey », la FFVL dit le lieu-dit « GRANDE LECHERE », 0 m
#  d'écart). Entre 300 m et 1 km, on ne retient que les paires qui
#  partagent un mot du nom (« Puy de st romain » / « PUY SAINT-ROMAIN »,
#  301 m) — sans mot commun, c'est souvent un AUTRE déco du même massif
#  (« Coursegoules » / « VIERIOU », 540 m). Appariement 1-à-1, le plus
#  proche d'abord : un déco FFVL n'absorbe jamais deux décos pgEarth.
#  Mêmes seuils pour les atterros (distance seule : un atterro pgEarth
#  n'a pas de nom propre).
#
#  ── CE QUE ÇA CASSE, ET LA PARADE ──────────────────────────────────
#  `siteKey` (lib/decos.ts) = coordonnées arrondies. Un doublon prend la
#  position FFVL → sa clé change → `origin_site` (user_watched,
#  user_foehn_watch) et `user_deco_favorites.site_key` écrits sous
#  l'ancienne clé deviennent orphelins. Ce script écrit donc la table
#  de correspondance ancienne → nouvelle clé ET le .sql de migration
#  (web/supabase_step72_sites_ffvl_keymap.sql) — préparé, JAMAIS exécuté
#  par Claude. À jouer AU MOMENT du déploiement du nouveau decos.json.
#
#  ── FORMATS DE SORTIE (rétro-compatibles : on AJOUTE en fin de tuple) ─
#  decos.json   : [lat, lon, name, alt, sectors, src, status, alias, suid]
#  atterros.json: [lat, lon, parentName, label]
#    - parentName : nom EXACT du déco parent dans decos.json (lien
#      explicite de la source), '' si aucun ;
#    - label      : nom propre de l'atterro (FFVL), '' si pgEarth.
#  sites_ffvl.json (chargé à l'ouverture d'une fiche, pas au démarrage) :
#    {suid: [restrictions, alerte, avertissements]}
#
#  `status` : '' actif · 'auth' autorisation systématique requise ·
#  'temp' non praticable temporairement · 'int' interdit ·
#  'int_auth' interdit sauf autorisation.
#
#  Licence : FFVL = Licence Ouverte 2.0 (Etalab), crédit dans À propos.
#  ⚠️ terrains.json contient les coordonnées d'un référent par terrain
#  (`terrain_coordonnes_referent`) : jamais copiées.
# ══════════════════════════════════════════════════════════════════

from __future__ import annotations

import json
import math
import os
import re
import sys
import unicodedata
import urllib.request

FFVL_TERRAINS_URL = "https://www.data.gouv.fr/api/1/datasets/r/4375c95d-cf26-4e71-b72d-2e09be5a0e36"
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache_ffvl", "terrains.json")
# Métropole + Corse : les terrains d'outre-mer (Réunion, Polynésie…)
# sortent du domaine des modèles de l'app (AROME, ARPEGE-EU).
BBOX = (41.2, 51.6, -5.5, 10.2)
DUP_KM = 0.3
DUP_NAME_KM = 1.0
TEXT_MAX = 400

STATUS = {
    "actif": "",
    "actif_autorisation_systematique_requise": "auth",
    "non_praticable_temporaire": "temp",
    "interdit": "int",
    "interdit_sauf_autorisation": "int_auth",
}
SECTOR_FFVL = {"N": 0, "NE": 1, "E": 2, "SE": 3, "S": 4, "SO": 5, "O": 6, "NO": 7}
SMALL = {"de", "du", "des", "la", "le", "les", "l", "d", "et", "en", "sur", "sous", "au", "aux", "a", "à"}
STOP = {"deco", "decollage", "atterro", "atterrissage", "site", "les", "des", "col", "mont",
        "sud", "nord", "est", "ouest", "pente", "ecole", "saint", "sainte"}


def fetch_terrains() -> list:
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    try:
        req = urllib.request.Request(FFVL_TERRAINS_URL, headers={"User-Agent": "balise-watch.app"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        rows = json.loads(data)
        if not isinstance(rows, list) or len(rows) < 1000:
            raise ValueError(f"réponse suspecte ({type(rows).__name__}, {len(rows) if isinstance(rows, list) else '?'})")
        with open(CACHE, "wb") as f:
            f.write(data)
        return rows
    except Exception as e:  # repli : dernière copie connue
        print(f"⚠️  terrains FFVL indisponibles ({e}) — cache local", file=sys.stderr)
        with open(CACHE, "rb") as f:
            return json.load(f)


def km(a, b, c, d) -> float:
    y = (a - c) * 111.32
    x = (b - d) * 111.32 * math.cos(math.radians(a))
    return math.hypot(x, y)


def tokens(s: str) -> set:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    s = s.replace("st ", "saint ").replace("ste ", "sainte ")
    return {w for w in re.split(r"[^a-z0-9]+", s) if len(w) > 2 and w not in STOP}


def pretty(name: str) -> str:
    """« LES CONTAMINES MONTJOIE - LA KOUZNA » → « Les Contamines Montjoie - La Kouzna ».
    Ne touche pas un nom déjà en casse mixte."""
    name = re.sub(r"\s+", " ", (name or "").strip())
    if not name or name != name.upper():
        return name
    out = []
    for i, w in enumerate(re.split(r"(\s+|-|')", name.lower())):
        if not w or w.isspace() or w in "-'":
            out.append(w)
            continue
        out.append(w if (i > 0 and w in SMALL) else w[:1].upper() + w[1:])
    return "".join(out)


def sectors_ffvl(t: dict) -> str | None:
    """OK → '2', NOK et non cité → '0' (la FFVL liste ce qui marche) ;
    None si la FFVL ne renseigne aucune orientation."""
    def parse(field):
        idx = set()
        for lab in filter(None, (t.get(field) or "").split(";")):
            for part in lab.split("-"):  # « NO-N », « S-SO » : les deux secteurs
                if part.strip() in SECTOR_FFVL:
                    idx.add(SECTOR_FFVL[part.strip()])
        return idx
    ok = parse("wind_orientations_ok")
    if not ok:
        return None
    return "".join("2" if i in ok else "0" for i in range(8))


def clip(s) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    if s.lower() in {"", "ras", "rien", "néant", "neant", "aucun", "aucune", "-"}:
        return ""
    return s if len(s) <= TEXT_MAX else s[: TEXT_MAX - 1].rstrip() + "…"


def site_key(lat: float, lon: float) -> str:
    return f"{lat:.4f}|{lon:.4f}"  # = siteKey() de lib/decos.ts (toFixed(4))


def in_bbox(lat, lon) -> bool:
    return BBOX[0] < lat < BBOX[1] and BBOX[2] < lon < BBOX[3]


def match(pg: list, ff: list, use_names: bool) -> dict:
    """Appariement 1-à-1 pg_index → ff_index, le plus proche d'abord."""
    pairs = []
    for i, (plat, plon, pname) in enumerate(pg):
        if not in_bbox(plat, plon):
            continue
        for j, (flat, flon, fname) in enumerate(ff):
            if abs(flat - plat) > 0.02 or abs(flon - plon) > 0.03:
                continue
            d = km(plat, plon, flat, flon)
            if d <= DUP_KM or (use_names and d <= DUP_NAME_KM and tokens(pname) & tokens(fname)):
                pairs.append((d, i, j))
    pairs.sort()
    used_p, used_f, out = set(), set(), {}
    for d, i, j in pairs:
        if i in used_p or j in used_f:
            continue
        used_p.add(i); used_f.add(j); out[i] = j
    return out


def fuse(pg_decos: list, pg_landings: list) -> tuple[list, list, dict, dict, dict]:
    """pg_decos : [lat, lon, name, alt, sectors] ; pg_landings :
    [lat, lon, parent_index]. Rend (decos, atterros, details, keymap, stats)."""
    T = fetch_terrains()
    para = [t for t in T
            if "parapente" in (t.get("possible_usages_text") or "")
            and isinstance(t.get("latitude"), (int, float)) and isinstance(t.get("longitude"), (int, float))
            and in_bbox(t["latitude"], t["longitude"])]
    fdec = [t for t in para if "décollage" in (t.get("flying_functions_text") or "")]
    fatt = [t for t in para if "atterrissage" in (t.get("flying_functions_text") or "")]

    m = match([(d[0], d[1], d[2]) for d in pg_decos],
              [(t["latitude"], t["longitude"], t["toponym"]) for t in fdec], use_names=True)
    ff_taken = set(m.values())

    decos, new_name_of_pg, keymap, details = [], {}, {}, {}

    def ffvl_tuple(t, pg=None):
        lat, lon = round(t["latitude"], 4), round(t["longitude"], 4)
        name = pretty(t.get("toponym"))[:48]
        alt = t.get("altitude")
        alt = int(round(alt)) if isinstance(alt, (int, float)) and alt > 0 else (pg[3] if pg else None)
        sec = sectors_ffvl(t) or (pg[4] if pg else "")
        alias = ""
        if pg and not (tokens(pg[2]) and tokens(pg[2]) <= tokens(name)):
            alias = pg[2]
        suid = t.get("suid")
        det = [clip(t.get("restrictions")), clip(t.get("alert_msg")), clip(t.get("warnings"))]
        if any(det) and suid is not None:
            details[str(suid)] = det
        return [lat, lon, name, alt, sec, "fp" if pg else "f", STATUS.get(t.get("status"), ""), alias, suid]

    for i, d in enumerate(pg_decos):
        if i in m:
            row = ffvl_tuple(fdec[m[i]], pg=d)
            old, new = site_key(d[0], d[1]), site_key(row[0], row[1])
            if old != new:
                keymap[old] = new
        else:
            row = [d[0], d[1], d[2], d[3], d[4], "p", "", "", None]
        new_name_of_pg[i] = row[2]
        decos.append(row)
    ffvl_only = [ffvl_tuple(t) for j, t in enumerate(fdec) if j not in ff_taken]
    decos.extend(ffvl_only)

    # Nom → déco FFVL qui est AUSSI un atterro (même terrain) : lien explicite.
    own_deco_name = {t.get("suid"): pretty(t.get("toponym"))[:48] for t in fdec}

    am = match([(l[0], l[1], "") for l in pg_landings],
               [(t["latitude"], t["longitude"], "") for t in fatt], use_names=False)
    a_taken = set(am.values())
    atterros, seen = [], set()

    def push(row):
        k = (row[0], row[1])
        if k not in seen:
            seen.add(k); atterros.append(row)

    for i, l in enumerate(pg_landings):
        parent = new_name_of_pg.get(l[2], "")
        if i in am:
            t = fatt[am[i]]
            push([round(t["latitude"], 4), round(t["longitude"], 4), parent, pretty(t.get("toponym"))[:48]])
        else:
            push([l[0], l[1], parent, ""])
    for j, t in enumerate(fatt):
        if j in a_taken:
            continue
        parent = own_deco_name.get(t.get("suid"), "") if "décollage" in (t.get("flying_functions_text") or "") else ""
        push([round(t["latitude"], 4), round(t["longitude"], 4), parent, pretty(t.get("toponym"))[:48]])

    stats = {
        "ffvl_decos": len(fdec), "ffvl_atterros": len(fatt),
        "doublons_decos": len(m), "ffvl_seules": len(ffvl_only),
        "pg_seules": len(pg_decos) - len(m),
        "doublons_atterros": len(am), "cles_changees": len(keymap),
        "statuts": {s: sum(1 for d in decos if d[6] == s) for s in ("auth", "temp", "int", "int_auth")},
        "fiches_detail": len(details),
    }
    return decos, atterros, details, keymap, stats


def write_keymap_sql(keymap: dict, path: str) -> None:
    values = ",\n  ".join(f"('{o}', '{n}')" for o, n in sorted(keymap.items()))
    sql = f"""-- ════════════════════════════════════════════════════════════════════
--  Étape 72 — terrains FFVL fusionnés dans decos.json (13/11/2026)
--  GÉNÉRÉ par balise-watch-server/arome-thermal/fusion_ffvl.py.
--  Préparé par Claude, JAMAIS exécuté par Claude — Yann le joue dans le
--  SQL Editor, AU MOMENT où le nouveau decos.json part en production.
-- ════════════════════════════════════════════════════════════════════
--  Un décollage présent chez pgEarth ET à la FFVL prend désormais la
--  position FFVL, donc une autre clé `lat|lon` (siteKey, lib/decos.ts).
--  Les lignes écrites sous l'ancienne clé deviendraient orphelines :
--  « Ne plus surveiller ce site » ne les retrouverait plus, le nom du
--  site disparaîtrait des push, le favori de déco ne se rallumerait pas.
--  {len(keymap)} clés changent. Idempotent : rejouer ne change plus rien.
--
--  1) Aperçu (lecture seule) — combien de lignes sont concernées.
with keymap(old_key, new_key) as (values
  {values}
)
select 'user_watched' as tbl, count(*) from user_watched w join keymap k on w.origin_site = k.old_key
union all
select 'user_foehn_watch', count(*) from user_foehn_watch w join keymap k on w.origin_site = k.old_key
union all
select 'user_deco_favorites', count(*) from user_deco_favorites f join keymap k on f.site_key = k.old_key;

--  2) Migration — dans une transaction.
begin;
create temporary table _keymap(old_key text primary key, new_key text not null) on commit drop;
insert into _keymap values
  {values};

update user_watched w set origin_site = k.new_key
from _keymap k where w.origin_site = k.old_key;

update user_foehn_watch w set origin_site = k.new_key
from _keymap k where w.origin_site = k.old_key;

-- Favoris de déco : clé ET coordonnées (le client recalcule la clé
-- depuis lat/lon). Un favori déjà présent sous la nouvelle clé (ajouté
-- après le déploiement) gagne : on supprime l'ancien plutôt que de
-- violer unique(user_id, site_key).
delete from user_deco_favorites f
using _keymap k
where f.site_key = k.old_key
  and exists (select 1 from user_deco_favorites g where g.user_id = f.user_id and g.site_key = k.new_key);

update user_deco_favorites f
set site_key = k.new_key,
    lat = split_part(k.new_key, '|', 1)::double precision,
    lon = split_part(k.new_key, '|', 2)::double precision
from _keymap k where f.site_key = k.old_key;
commit;
"""
    with open(path, "w") as f:
        f.write(sql)
