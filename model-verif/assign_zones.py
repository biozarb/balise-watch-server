#!/usr/bin/env python3
"""Écrit `station_zone` (et les `model_zone` d'échelon 1) depuis le JSON
produit par `PWA/web/scripts/assign-zones.ts`.  Lot C, 08/08/2026.

── LA MOITIÉ PYTHON DU LOT C, ET RIEN DE PLUS ──────────────────────────
Tout le raisonnement géographique est en TypeScript, testé
(`scripts/test-zone.ts` 29 assertions, `scripts/test-subbasins.ts` 23).
Ce script-ci ne fait que trois choses : relire le JSON, en retirer le
bloc `_audit`, et appeler `score.write_station_zones`.

⚠️ IL N'ÉCRIT PAS LES DEUX TABLES LUI-MÊME, et c'est le point.
`station_zone.zone_id` porte une clé étrangère vers `model_zone`
(step35 l. 199) : la ligne de zone doit exister AVANT la balise, sinon
c'est un 23503. `score.write_station_zones` est le point d'entrée écrit
au lot B précisément pour que cette question ne se repose pas à chaque
script d'affectation. On l'appelle ; on ne le réécrit pas.

⚠️ REJOUABLE. Les deux écritures sont des upserts sur leur clé. Relancer
ce script sur le même JSON réécrit exactement les mêmes lignes, et
`assigned_at` garde la trace du dernier passage. La rejouabilité est un
livrable, pas une intention : `--verifier` la démontre en recomptant
avant et après.

── USAGE ───────────────────────────────────────────────────────────────
    ./assign_zones.py ../../web/.data/zones.json            # écrit
    ./assign_zones.py zones.json --dry-run                  # n'écrit rien
    ./assign_zones.py zones.json --verifier                 # écrit puis recompte
"""

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys

import score as J

#: Les colonnes que `station_zone` accepte (step35 l. 195-212). Tout le
#: reste du JSON est de l'audit et ne doit PAS partir vers PostgREST, qui
#: refuse une colonne inconnue — un échec parlant, mais évitable.
#:
#: ⚠️ DEUX COLONNES DE LA TABLE SONT VOLONTAIREMENT ABSENTES D'ICI :
#: `position_suspecte` (étape 42) et `doublon_de` (lot L17, step55).
#: Elles ne viennent pas de l'affectation géographique — elles viennent
#: d'inspections humaines et de la sonde de doublons — et ce script ne
#: doit ni les écrire ni les effacer.
#: ⭐ Et il ne les efface PAS : `score.Supabase.upsert` envoie
#: `Prefer: resolution=merge-duplicates`, et PostgREST ne met alors à
#: jour que les colonnes PRÉSENTES dans le corps. Les ajouter ici à
#: `None` « pour la forme » les remettrait donc à zéro à chaque
#: réaffectation de zones, silencieusement, et une déduplication
#: mesurée sur 21 jours d'archives disparaîtrait sans un message.
#: *(Relu dans le code le 27/08 ; le contrôle en base est écrit dans la
#: section VÉRIFICATION de `supabase_step55_lot_l17_doublon_de.sql`.)*
COLUMNS = (
    "source", "station_id", "zone_id", "basin_id", "basin_uncertain",
    "massif_id", "landform", "dem_alt_m", "tpi_2km_m", "tpi_10km_m",
    "relief_5km_m", "slope_deg", "coast_km",
)

#: Le CHECK du SQL, recopié ici pour échouer AVANT l'envoi plutôt qu'après.
#: Une valeur inventée passe le typage TypeScript comme le typage Python et
#: n'échoue qu'en base, à mi-parcours d'un envoi de 647 lignes.
LANDFORMS = {"valley", "slope", "ridge", "plateau", "plain", "coastal"}


def read_rows(path: pathlib.Path) -> tuple[list[dict], dict]:
    """Le JSON d'affectation, réduit aux colonnes de la table."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload["rows"]
    rows = []
    for r in raw:
        if r["landform"] not in LANDFORMS:
            raise SystemExit(
                f"forme de terrain inconnue « {r['landform']} » sur "
                f"{r['source']}:{r['station_id']} — le CHECK de step35 la refusera")
        if not r.get("zone_id"):
            raise SystemExit(f"zone_id manquant sur {r['source']}:{r['station_id']}")
        rows.append({k: r[k] for k in COLUMNS})
    # Deux fois la même balise dans un envoi : PostgREST refuse
    # (« ON CONFLICT ne peut affecter la ligne une seconde fois »).
    seen = collections.Counter((r["source"], r["station_id"]) for r in rows)
    dups = [k for k, v in seen.items() if v > 1]
    if dups:
        raise SystemExit(f"balises en double dans le JSON : {dups[:5]}")
    return rows, payload


def resume(rows: list[dict]) -> None:
    """Le compte rendu chiffré — celui qui dit si l'algorithme a marché."""
    by = lambda k: collections.Counter(r[k] for r in rows)  # noqa: E731
    basins = collections.Counter(r["basin_id"] for r in rows if r["basin_id"])
    kinds = collections.Counter(J.zone_kind_for(r) for r in rows)
    print(f"  {len(rows)} balises")
    print("  formes      : " + ", ".join(f"{k} {v}" for k, v in by("landform").most_common()))
    print("  échelon 1   : " + ", ".join(f"{k} {v}" for k, v in kinds.most_common()))
    print(f"  bassins     : {len(basins)} distincts, "
          f"le plus peuplé {basins.most_common(1)[0] if basins else '—'}")
    print(f"  à 1 balise  : {sum(1 for v in basins.values() if v == 1)}, "
          f"balises dans un bassin ≥ 3 : {sum(v for v in basins.values() if v >= 3)}")
    print(f"  incertaines : {sum(1 for r in rows if r['basin_uncertain'])}")
    print(f"  littoral    : {sum(1 for r in rows if r['landform'] == 'coastal')}")


def compter(sb: J.Supabase) -> dict[str, int]:
    """Compte les lignes des tables que ce lot touche, en base."""
    out = {}
    for t in ("station_zone", "model_zone"):
        # ⚠️ Le « ? » est obligatoire : `Supabase.select` ne l'ajoute que
        # lorsque la requête ne contient pas déjà « select= ».
        # ⚠️ CE FICHIER SAVAIT, ET C'EST LÀ LA LEÇON DU 08/08. Le lot C
        # avait bien vu que PostgREST plafonne une réponse à 1 000 lignes
        # et posait ici un garde-fou. Mais le garde-fou est resté LOCAL :
        # `Supabase.select` continuait de tronquer en silence pour tout
        # le monde, et `model_character` (81 960 lignes) y perdait sa
        # mémoire chaque nuit. Une connaissance rangée dans un seul
        # fichier ne protège que ce fichier.
        #
        # Depuis le lot F, `select` pagine et l'ordre est explicite. Le
        # compte ci-dessous est donc complet, et le garde-fou n'a plus
        # lieu d'être — on garde la trace de son existence, pas le test.
        rows = sb.select(t, "?select=source" if t == "station_zone" else "?select=zone_id",
                         order="source,station_id" if t == "station_zone" else "zone_id")
        out[t] = len(rows)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("json", type=pathlib.Path, help="sortie de scripts/assign-zones.ts")
    ap.add_argument("--dry-run", action="store_true",
                    help="tout vérifier et tout compter, sans rien écrire")
    ap.add_argument("--verifier", action="store_true",
                    help="recompter en base avant et après, et par kind")
    args = ap.parse_args()

    rows, payload = read_rows(args.json)
    print(f"▶ {args.json} — grille {payload.get('subbasin_stats', {}).get('cells', '?')} mailles, "
          f"seuil rivière {payload.get('subbasins', {}).get('streamAreaKm2', '?')} km²")
    resume(rows)

    # Les lignes `model_zone` d'échelon 1 qui vont partir AVANT les balises.
    zone_rows = J.zone_rows_for(rows)
    print(f"  lignes `model_zone` d'échelon 1 à écrire : {len(zone_rows)}")

    if args.dry_run:
        print("\nⓘ --dry-run : rien n'a été écrit.")
        return 0

    sb = J.Supabase()
    avant = compter(sb) if args.verifier else None
    n_zone, n_stat = J.write_station_zones(sb, rows)
    print(f"\n✅ {n_zone} lignes `model_zone`, {n_stat} lignes `station_zone`")

    if args.verifier:
        apres = compter(sb)
        print(f"  `station_zone` : {avant['station_zone']} → {apres['station_zone']}")
        print(f"  `model_zone`   : {avant['model_zone']} → {apres['model_zone']}")
        kinds = collections.Counter(
            r["kind"] for r in sb.select("model_zone", "?select=kind,zone_id",
                                         order="zone_id"))
        print("  `model_zone` par kind : "
              + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
        zones = sb.select(
            "station_zone",
            "?select=source,station_id,zone_id,basin_id,landform,basin_uncertain",
            order="source,station_id")
        b = collections.Counter(z["basin_id"] for z in zones if z["basin_id"])
        print(f"  en base : {len(zones)} balises, {len(b)} bassins distincts, "
              f"{sum(1 for z in zones if z['basin_uncertain'])} incertaines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
