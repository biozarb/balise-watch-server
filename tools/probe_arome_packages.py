"""Sonde le bucket AROME public de Météo-France pour établir, EN DIRECT,
quels paquets et quelles variables sont réellement disponibles.

Motif : avant d'écrire le Lot A (veille modèle « front de rafales »), il
faut savoir si les champs dont il a besoin — rafales, pression, CAPE,
précipitations, température — existent dans la source que le projet
utilise DÉJÀ (bucket public S3, aucune clé API), plutôt que d'ajouter une
dépendance à une API Météo-France authentifiée ou à Open-Meteo et son
quota. Réponse mesurée, pas supposée.

    python3 tools/probe_arome_packages.py

Ne télécharge que quelques listings XML (quelques ko) + éventuellement UN
fichier GRIB si --grib est passé, pour lister ses shortNames réels.
"""

import sys
import re
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

S3 = "https://meteofrance-pnt.s3.rbx.io.cloud.ovh.net"


def http_get(url, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": "balise-watch-probe/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def s3_list(prefix, delimiter=None, max_keys=1000):
    url = f"{S3}/?list-type=2&prefix={urllib.parse.quote(prefix)}&max-keys={max_keys}"
    if delimiter:
        url += f"&delimiter={urllib.parse.quote(delimiter)}"
    root = ET.fromstring(http_get(url, 60))
    keys, prefixes = [], []
    for e in root.iter():
        tag = e.tag.split('}')[-1]
        if tag == "Key":
            keys.append(e.text)
        elif tag == "Prefix" and e.text != prefix:
            prefixes.append(e.text)
    return keys, prefixes


def recent_runs(n=4):
    """Références de run plausibles (AROME publie toutes les 3 h)."""
    now = datetime.now(timezone.utc)
    out = []
    h = (now.hour // 3) * 3
    base = now.replace(hour=h, minute=0, second=0, microsecond=0)
    for i in range(n):
        r = base - timedelta(hours=3 * i)
        out.append(r.strftime("%Y-%m-%dT%H:00:00Z"))
    return out


def main():
    ref = None
    for cand in recent_runs(6):
        keys, prefixes = s3_list(f"pnt/{cand}/arome/", delimiter="/")
        if prefixes or keys:
            ref = cand
            break
    if not ref:
        print("Aucun run AROME trouvé — bucket injoignable ou structure changée.")
        return 1

    print(f"\nRun AROME sondé : {ref}\n")

    for grid in ("001", "0025"):
        _, pkgs = s3_list(f"pnt/{ref}/arome/{grid}/", delimiter="/")
        names = sorted(p.rstrip('/').split('/')[-1] for p in pkgs)
        print(f"  grille {grid:>5} → paquets : {', '.join(names) if names else '(aucun)'}")

    print()
    # Combien de fichiers par paquet (indice de complétude du run).
    for grid in ("001", "0025"):
        _, pkgs = s3_list(f"pnt/{ref}/arome/{grid}/", delimiter="/")
        for p in sorted(pkgs):
            pkg = p.rstrip('/').split('/')[-1]
            keys, _ = s3_list(p)
            steps = set()
            for k in keys:
                m = re.search(r"__(\d+)H(?:(\d+)H)?__", k)
                if m:
                    steps.add(int(m.group(1)))
            rng = f"{min(steps)}–{max(steps)} h" if steps else "?"
            print(f"  {grid:>5}/{pkg:<4} : {len(keys):>3} fichiers, échéances {rng}")

    if "--grib" in sys.argv:
        # Inspection des shortNames d'un fichier SP2 (là où se trouvent
        # normalement rafales / CAPE / précipitations).
        try:
            from eccodes import (codes_grib_new_from_file, codes_get,
                                 codes_release)
        except ImportError:
            print("\n(eccodes non installé ici — inspection GRIB sautée)")
            return 0
        # Échéance sondée : PAS 00H. Les champs cumulés ou « max sur
        # l'intervalle » — rafales, précipitations — n'existent pas au pas
        # 0 par construction, et c'est précisément eux qu'on cherche pour
        # le Lot A. On sonde donc une échéance non nulle.
        step = "__03H__"
        for arg in sys.argv:
            if re.fullmatch(r"\d+", arg):
                step = f"__{int(arg):02d}H__"
        print(f"\n(échéance sondée : {step})")
        for pkg in ("SP1", "SP2", "SP3"):
            keys, _ = s3_list(f"pnt/{ref}/arome/001/{pkg}/")
            keys = [k for k in keys if step in k]
            if not keys:
                continue
            path = f"/tmp/probe_{pkg}.grib2"
            print(f"\n  Téléchargement {pkg} ({keys[0].split('/')[-1]})…")
            with open(path, "wb") as fh:
                fh.write(http_get(f"{S3}/{urllib.parse.quote(keys[0])}", 300))
            found = {}
            with open(path, "rb") as fh:
                while True:
                    gid = codes_grib_new_from_file(fh)
                    if gid is None:
                        break
                    sn = codes_get(gid, "shortName")
                    # Certains messages AROME n'exposent pas typeOfLevel
                    # (ex. CAPE_INS) — ne pas laisser ça interrompre la
                    # sonde, c'est justement un champ qui nous intéresse.
                    try:
                        tol = codes_get(gid, "typeOfLevel")
                    except Exception:
                        tol = "?"
                    found.setdefault((sn, tol), 0)
                    found[(sn, tol)] += 1
                    codes_release(gid)
            print(f"  {pkg} — {len(found)} champs :")
            for (sn, tol), n in sorted(found.items()):
                print(f"      {sn:<12} {tol:<24} ×{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
