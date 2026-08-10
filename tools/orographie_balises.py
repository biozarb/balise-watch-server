#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  orographie_balises.py — le relief tel qu'AROME le voit, balise par
#                          balise                        (10/08/2026)
#
#  ⚠️ CE QUE CE SCRIPT MESURE, ET CE QU'IL NE MESURE PAS.
#
#  Il ne calcule PAS « l'erreur d'orographie » du modèle. Il ne le peut
#  pas : le référentiel Pioupiou donne latitude et longitude, et RIEN
#  d'autre — pas d'altitude (vérifié le 10/08 dans `collect.py::
#  load_stations`, qui n'écrit que id/source/lat/lon/name/seen_at).
#  L'altitude réelle des 648 balises n'existe nulle part dans ce projet.
#
#  Il mesure donc ce qui est mesurable aujourd'hui, et qui est déjà
#  beaucoup :
#
#    1. `z_modele`  — l'altitude que le modèle donne au sol sous la
#                     balise. C'est le plancher de toute prévision à ce
#                     point, et le zéro de tout niveau « hauteur ».
#    2. `amplitude` — l'écart entre le point le plus haut et le plus bas
#                     que le modèle voit dans un rayon donné. C'est du
#                     RELIEF RÉSOLU : combien de dénivelé la maille
#                     porte réellement autour de ce point.
#    3. `sigma`     — l'écart-type de l'orographie dans le même rayon.
#    4. `creux`     — `z_modele − médiane du voisinage`. Négatif = le
#                     modèle place la balise dans un fond ; positif =
#                     sur une bosse. Dit de quel côté il se trompe
#                     probablement.
#
#  ⚠️ POURQUOI C'EST UTILE MÊME SANS L'ALTITUDE RÉELLE. Un site où le
#  modèle ne voit que 40 m de dénivelé dans 5 km est un site où la
#  vallée n'existe pas pour lui — quelle que soit l'altitude vraie. La
#  littérature du dossier Tarentaise le dit en clair : un modèle ne
#  résout pas les structures de la taille de sa maille mais de 5 à 7 Δx,
#  soit 5,5 à 7,7 km à 0,01°. `amplitude` mesure directement ce qui
#  survit à ce filtre.
#
#  Ce que ça devient : une covariable, à confronter à `model_verif_daily`.
#  L'hypothèse — testable, pas démontrée — est que l'erreur de prévision
#  à une balise croît avec le relief NON résolu autour d'elle.
#
#  ⚠️ LECTURE SEULE, aucune écriture R2, aucune clé d'API. La source est
#  le miroir S3 public d'OVH, la même que `arome-wind/ingest.py` — le
#  champ d'orographie est déjà téléchargé à chaque run par cette chaîne
#  (paquet SP3, grille 001, shortName `h`, statique). On ne fait que le
#  relire ailleurs.
#
#  Usage :
#      python3 tools/orographie_balises.py --out /var/lib/bw-model-verif
#      python3 tools/orographie_balises.py --out … --csv       # tableur
#      python3 tools/orographie_balises.py --out … --top 25    # palmarès
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Mêmes constantes que `arome-wind/ingest.py` — miroir S3 public, sans
# clé ni quota. Ne pas basculer sur le portail : ce champ est statique et
# gratuit ici, y ajouter une clé serait une dépendance pour rien.
S3 = "https://meteofrance-pnt.s3.rbx.io.cloud.ovh.net"
MODEL_DIR = "arome"
GRID = "001"                      # 0,01° — la seule qui porte SP3/HP*

# Rayons d'analyse. 3 km ≈ la largeur d'un fond de vallée alpin ; 8 km ≈
# l'échelle à laquelle un modèle à 1,3 km commence tout juste à résoudre
# (5-7 Δx). Les deux ensemble disent si le relief local existe pour le
# modèle, et à quelle échelle.
RAYONS_KM = (3.0, 8.0)


class Abort(Exception):
    pass


# ══════════════════════════════════════════════════════════════════════
#  PARTIE PURE  —  testable sans réseau
# ══════════════════════════════════════════════════════════════════════
def norm_lon(x):
    return x - 360 if x > 180 else x


def indices(meta, lat, lon):
    """(j, i) du point de grille le plus proche, ou None hors domaine.
    Même convention de balayage que `arome-wind/ingest.py::elev_at`."""
    i = round((lon - meta["lon0"]) / meta["di"])
    j = (round((meta["lat0"] - lat) / meta["dj"]) if meta["jScan"] != 1
         else round((lat - meta["lat0"]) / meta["dj"]))
    if i < 0 or i >= meta["Ni"] or j < 0 or j >= meta["Nj"]:
        return None
    return j, i


def demi_fenetre(meta, lat, rayon_km):
    """Combien de points de grille couvrent `rayon_km` en j et en i.

    ⚠️ Un degré de longitude ne vaut pas un degré de latitude, et l'écart
    grandit avec la latitude : à 45 °N un pas de 0,01° fait 1,11 km en
    latitude mais seulement 0,79 km en longitude. Prendre la même demi-
    fenêtre dans les deux directions donnerait une ellipse au lieu d'un
    disque, et sous-estimerait le relief est-ouest de 40 %.
    """
    km_par_deg_lat = 111.195
    km_par_deg_lon = 111.195 * max(math.cos(math.radians(lat)), 1e-6)
    dj = max(1, int(math.ceil(rayon_km / (meta["dj"] * km_par_deg_lat))))
    di = max(1, int(math.ceil(rayon_km / (meta["di"] * km_par_deg_lon))))
    return dj, di


def voisinage(valeurs, meta, lat, lon, rayon_km):
    """Altitudes du modèle dans un disque de `rayon_km` autour du point.

    Disque, pas carré : on teste la distance réelle de chaque point de la
    fenêtre. Sans ça, les coins d'un carré de 8 km portent à 11,3 km et
    ramèneraient du relief qui n'est pas dans le rayon annoncé.
    """
    ji = indices(meta, lat, lon)
    if ji is None:
        return []
    j0, i0 = ji
    dj, di = demi_fenetre(meta, lat, rayon_km)
    km_lat = meta["dj"] * 111.195
    km_lon = meta["di"] * 111.195 * max(math.cos(math.radians(lat)), 1e-6)
    out = []
    for j in range(max(0, j0 - dj), min(meta["Nj"], j0 + dj + 1)):
        for i in range(max(0, i0 - di), min(meta["Ni"], i0 + di + 1)):
            if math.hypot((j - j0) * km_lat, (i - i0) * km_lon) > rayon_km:
                continue
            v = valeurs[j * meta["Ni"] + i]
            if v is not None and not (isinstance(v, float) and math.isnan(v)):
                out.append(float(v))
    return out


# ══════════════════════════════════════════════════════════════════════
#  ALTITUDE LUE DANS LE NOM  —  une vérité terrain gratuite, et partielle
# ══════════════════════════════════════════════════════════════════════
#  ⚠️ TROUVÉE EN REGARDANT LES RÉSULTATS, PAS PRÉVUE. Les pilotes
#  nomment leurs balises « Déco Planpraz Chamonix 1958m », « Atterro
#  Aussois 1506m ». 109 des 648 noms (17 %) portent ainsi une altitude.
#  C'est la seule vérité terrain disponible dans ce projet — le
#  référentiel Pioupiou n'a que lat/lon.
#
#  ⚠️ ELLE EST DÉCLARATIVE, DONC FAILLIBLE. Trois pièges rencontrés :
#    · « Chur 80m AGL » est une hauteur sol, pas une altitude → exclu
#      sur le mot AGL ;
#    · « Petit Mont-Rond 1 535m » : séparateur de milliers ESPACE. Une
#      regex naïve y lit 535 et fabrique un écart de +718 m qui n'existe
#      pas. C'était le plus gros « écart positif » du premier passage —
#      entièrement un bug de lecture ;
#    · rien ne garantit que le pilote ait mis l'altitude du CAPTEUR
#      plutôt que celle du décollage voisin.
#
#  On l'utilise donc comme INDICE, jamais comme référence, et on
#  l'étiquette partout `z_nom`.
_ALT_NOM = re.compile(r"(?<![\d,.])(\d{1,2}[  .](\d{3})|\d{2,4})\s*m\b", re.I)


def altitude_du_nom(nom: str):
    """Altitude (m) lue dans le nom, ou None. Voir l'avertissement."""
    if not nom or re.search(r"\bAGL\b", nom, re.I):
        return None
    meilleurs = []
    for brut, _ in _ALT_NOM.findall(nom):
        v = re.sub(r"[  .]", "", brut)
        try:
            z = int(v)
        except ValueError:
            continue
        if 20 <= z <= 4200:
            meilleurs.append(z)
    return max(meilleurs) if meilleurs else None


def mediane(xs):
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def ecart_type(xs):
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def analyser_point(valeurs, meta, lat, lon, rayons_km=RAYONS_KM):
    """Le calcul, pour une balise. Rend None hors domaine."""
    ji = indices(meta, lat, lon)
    if ji is None:
        return None
    j, i = ji
    z = valeurs[j * meta["Ni"] + i]
    if z is None or (isinstance(z, float) and math.isnan(z)):
        return None
    z = float(z)
    res = {"z_modele": round(z, 1)}
    for r in rayons_km:
        vs = voisinage(valeurs, meta, lat, lon, r)
        cle = f"r{r:g}km"
        if not vs:
            res[cle] = None
            continue
        med = mediane(vs)
        res[cle] = {
            "n": len(vs),
            "amplitude": round(max(vs) - min(vs), 1),
            "sigma": round(ecart_type(vs), 1),
            "creux": round(z - med, 1),
            "min": round(min(vs), 1),
            "max": round(max(vs), 1),
        }
    return res


# ══════════════════════════════════════════════════════════════════════
#  PARTIE E/S
# ══════════════════════════════════════════════════════════════════════
def http_get(url, timeout=120):
    req = urllib.request.Request(
        url, headers={"User-Agent": "balise-watch-orographie/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def s3_keys(prefix):
    url = f"{S3}/?list-type=2&prefix={urllib.parse.quote(prefix)}&max-keys=1000"
    root = ET.fromstring(http_get(url, 60))
    return [e.text for e in root.iter() if e.tag.split("}")[-1] == "Key"]


def trouver_sp3(max_recul=8):
    """Le SP3 00H le plus récent disponible.

    ⚠️ Contrairement à `pick_run()` de `arome-wind`, on ne cherche pas le
    run le plus COMPLET : l'orographie est **statique**. N'importe quel
    run fait l'affaire, et le plus récent publié est le plus simple à
    trouver. On remonte simplement jusqu'à en trouver un.
    """
    base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    base -= timedelta(hours=base.hour % 3)
    for back in range(max_recul):
        run = base - timedelta(hours=3 * back)
        ref = run.strftime("%Y-%m-%dT%H:00:00Z")
        keys = sorted(k for k in s3_keys(f"pnt/{ref}/{MODEL_DIR}/{GRID}/SP3/")
                      if "__00H__" in k)
        if keys:
            return ref, keys[0]
    raise Abort("aucun paquet SP3 00H trouvé sur les 24 dernières heures")


def charger_orographie(cle, log=print):
    """Le champ `h` (surface) du paquet SP3.

    ⚠️ Lecture message par message avec filet, comme
    `arome-wind::load_orography` — et pour la même raison, payée en prod
    le 21/07 : SP3 contient au moins un message dont `typeOfLevel` /
    `level` n'existent pas, et un `codes_get` sans garde y lève
    `KeyValueNotFoundError` au milieu du fichier.
    """
    try:
        from eccodes import (codes_get, codes_get_values,  # noqa: PLC0415
                             codes_grib_new_from_file, codes_release)
    except ImportError:
        raise Abort("eccodes absent — lancer avec "
                    "/home/debian/venv-balise/bin/python3")

    url = f"{S3}/{urllib.parse.quote(cle)}"
    log(f"  téléchargement {cle.rsplit('/', 1)[-1]}")
    with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as t:
        t.write(http_get(url, 300))
        chemin = t.name
    meta = valeurs = None
    try:
        with open(chemin, "rb") as f:
            while True:
                gid = codes_grib_new_from_file(f)
                if gid is None:
                    break
                try:
                    if (codes_get(gid, "shortName") == "h"
                            and codes_get(gid, "typeOfLevel") == "surface"):
                        meta = dict(
                            Ni=codes_get(gid, "Ni"), Nj=codes_get(gid, "Nj"),
                            lat0=codes_get(gid, "latitudeOfFirstGridPointInDegrees"),
                            lon0=norm_lon(codes_get(
                                gid, "longitudeOfFirstGridPointInDegrees")),
                            di=codes_get(gid, "iDirectionIncrementInDegrees"),
                            dj=codes_get(gid, "jDirectionIncrementInDegrees"),
                            jScan=codes_get(gid, "jScansPositively"))
                        valeurs = codes_get_values(gid)
                        codes_release(gid)
                        break
                except Exception:      # noqa: BLE001 — message sans ces clés
                    pass
                codes_release(gid)
    finally:
        os.unlink(chemin)
    if valeurs is None:
        raise Abort("champ 'h' (surface) absent du paquet SP3")
    return valeurs, meta


def charger_stations(chemin: Path):
    if not chemin.exists():
        raise Abort(f"référentiel absent : {chemin} — il est écrit par "
                    f"`collect.py` (défaut <out>/stations.json)")
    return json.loads(chemin.read_text(encoding="utf-8"))


# ══════════════════════════════════════════════════════════════════════
def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        description="Le relief tel qu'AROME le voit, balise par balise.")
    p.add_argument("--out", default=os.environ.get("BW_MODEL_VERIF_ETAT",
                                                   "/var/lib/bw-model-verif"))
    p.add_argument("--stations", default=None)
    p.add_argument("--top", type=int, default=15,
                   help="taille du palmarès affiché")
    p.add_argument("--csv", action="store_true")
    a = p.parse_args(argv)

    out = Path(a.out)
    stations_path = Path(a.stations) if a.stations else out / "stations.json"

    try:
        stations = charger_stations(stations_path)
        print(f"▶ {len(stations)} balises au référentiel")
        ref, cle = trouver_sp3()
        print(f"▶ orographie AROME, run {ref} (champ statique)")
        valeurs, meta = charger_orographie(cle)
    except Abort as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2

    print(f"  grille {meta['Ni']}×{meta['Nj']} à {meta['di']}°, "
          f"origine {meta['lat0']:.3f}/{meta['lon0']:.3f}")

    lignes, hors = [], 0
    for st in stations:
        r = analyser_point(valeurs, meta, st["lat"], st["lon"])
        if r is None:
            hors += 1
            continue
        nom = st.get("name", "")
        z_nom = altitude_du_nom(nom)
        ligne = {"id": st["id"], "source": st.get("source", ""), "name": nom,
                 "lat": st["lat"], "lon": st["lon"], **r}
        if z_nom is not None:
            ligne["z_nom"] = z_nom
            ligne["ecart_nom"] = round(r["z_modele"] - z_nom, 1)
        lignes.append(ligne)

    if hors:
        print(f"  ⚠️ {hors} balises hors du domaine AROME — ignorées")

    dest = out / "orographie_balises.ndjson"
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as f:
        for l in lignes:
            f.write(json.dumps(l, ensure_ascii=False) + "\n")
    print(f"▶ {len(lignes)} lignes écrites dans {dest}")

    if a.csv:
        dest_csv = out / "orographie_balises.csv"
        with dest_csv.open("w", encoding="utf-8") as f:
            f.write("id;name;lat;lon;z_modele;ampl_3km;sigma_3km;creux_3km;"
                    "ampl_8km;sigma_8km;creux_8km\n")
            for l in lignes:
                a3, a8 = l.get("r3km") or {}, l.get("r8km") or {}
                f.write(f"{l['id']};{l['name']};{l['lat']};{l['lon']};"
                        f"{l['z_modele']};{a3.get('amplitude','')};"
                        f"{a3.get('sigma','')};{a3.get('creux','')};"
                        f"{a8.get('amplitude','')};{a8.get('sigma','')};"
                        f"{a8.get('creux','')}\n")
        print(f"▶ CSV : {dest_csv}")

    # ── Ce que ça raconte ────────────────────────────────────────────
    amps = [l["r8km"]["amplitude"] for l in lignes if l.get("r8km")]
    if amps:
        amps_tries = sorted(amps)
        n = len(amps_tries)
        def q(p_):
            return amps_tries[min(n - 1, int(p_ * n))]
        print("\n┌─ RELIEF RÉSOLU PAR AROME DANS 8 km (dénivelé, m) ────────────")
        print(f"│ balises : {n}")
        print(f"│ décile 1 {q(0.1):6.0f}  ·  médiane {q(0.5):6.0f}  ·  "
              f"décile 9 {q(0.9):6.0f}  ·  max {amps_tries[-1]:6.0f}")
        plats = sum(1 for x in amps if x < 200)
        print(f"│ {plats} balises ({plats / n * 100:.0f} %) avec moins de 200 m "
              f"de dénivelé résolu dans 8 km")
        print("└──────────────────────────────────────────────────────────────")

        print(f"\n── Les {a.top} balises au relief le plus marqué "
              f"(là où la maille travaille le plus) ──")
        for l in sorted([x for x in lignes if x.get("r8km")],
                        key=lambda x: -x["r8km"]["amplitude"])[:a.top]:
            r8 = l["r8km"]
            print(f"  {l['z_modele']:6.0f} m  ampl {r8['amplitude']:5.0f} m  "
                  f"σ {r8['sigma']:5.0f}  creux {r8['creux']:+6.0f}  "
                  f"{l['name'][:40]}")

        creux = sorted([x for x in lignes if x.get("r8km")],
                       key=lambda x: x["r8km"]["creux"])[:a.top]
        print(f"\n── Les {a.top} balises que le modèle place le plus EN CREUX ──")
        print("   (creux très négatif = fond de vallée ; c'est là que le "
              "remblaiement de maille fait le plus de dégâts)")
        for l in creux:
            r8 = l["r8km"]
            print(f"  {l['z_modele']:6.0f} m  creux {r8['creux']:+6.0f} m  "
                  f"ampl {r8['amplitude']:5.0f}  {l['name'][:40]}")

    # ── Écart au nom, quand il existe ────────────────────────────────
    ecs = [l for l in lignes if "ecart_nom" in l]
    if ecs:
        vals = sorted(l["ecart_nom"] for l in ecs)
        m = len(vals)
        def qe(p_):
            return vals[min(m - 1, int(p_ * m))]
        print(f"\n┌─ ÉCART z_modèle − z_nom (m), sur {m} balises "
              f"({m / len(lignes) * 100:.0f} % du réseau) ──")
        print(f"│ d1 {qe(.1):+6.0f}  q1 {qe(.25):+6.0f}  MÉDIANE {qe(.5):+6.0f}  "
              f"q3 {qe(.75):+6.0f}  d9 {qe(.9):+6.0f}")
        print(f"│ ⚠️ z_nom est DÉCLARATIF (lu dans le nom de la balise) — un")
        print(f"│    indice, jamais une référence.")
        gros = [l for l in ecs if abs(l["ecart_nom"]) > 300]
        print(f"│ {len(gros)} balises à plus de 300 m d'écart → à INSPECTER :")
        print(f"│    coordonnées fausses, nom trompeur, ou relief vraiment raboté")
        print("└──────────────────────────────────────────────────────────────")
        for l in sorted(gros, key=lambda x: x["ecart_nom"])[:10]:
            a8 = (l.get("r8km") or {}).get("amplitude", 0)
            print(f"  {l['ecart_nom']:+7.0f} m  modèle {l['z_modele']:6.0f}  "
                  f"nom {l['z_nom']:5d}  relief8 {a8:5.0f}  {l['name'][:38]}")

    print("\n⚠️ Rappel : `z_modele` n'est pas une erreur, c'est ce que le")
    print("   modèle VOIT. L'altitude réelle des 648 balises n'existe pas dans")
    print("   ce projet ; `z_nom` n'en couvre qu'une fraction, et déclarative.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
