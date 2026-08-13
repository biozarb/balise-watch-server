#!/usr/bin/env python3
"""
test_colonnes.py — banc du produit A, HORS-LIGNE.

    python3 verif/test_colonnes.py

⚠️ CE QUE CE BANC PROTÈGE.

Le produit A est ARCHIVÉ INDÉFINIMENT : une erreur d'écriture n'est pas
un incident, c'est une donnée fausse pour toujours. Trois façons de la
produire, toutes silencieuses :

  1. **Un décalage d'indice.** Les indices des balises sont calculés une
     fois depuis l'orographie figée. Si la grille reçue changeait, ils
     désigneraient d'autres points — valeurs plausibles, prises ailleurs.
  2. **Une quantification trop grossière.** Le float16 a un pas RELATIF :
     à 300 kelvins il vaut 0,25 K. Stocker une température en kelvins
     plutôt qu'en degrés Celsius perd un facteur 8 de précision, sans
     rien casser de visible. Ce banc le MESURE.
  3. **Un trou en bas de colonne.** Le vent n'existe qu'à partir de 20 m
     sur les niveaux hauteur ; les 10 m viennent des champs dédiés
     `10u`/`10v`. Un filtre qui l'ignore laisse un trou EXACTEMENT à
     l'altitude où la balise mesure — donc exactement là où le produit
     sert à quelque chose.

Aucun réseau, aucun GRIB : les listings et les valeurs sont injectés.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "agrume"))

import colonnes as C  # noqa: E402
import quantification as Q  # noqa: E402
import ingest_colonnes as I  # noqa: E402
from domaine import (G, GRID_3D, GRID_FINE, NIVEAUX_H_001,  # noqa: E402
                     NIVEAUX_H_0025, NIVEAUX_P, NIVEAUX_P_TOUS)

echecs = []


def verifier(nom, condition, detail=""):
    print(f"  {'✓' if condition else '✗'} {nom}" + (f"   {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


META_0025 = dict(Ni=1121, Nj=717, lat0=55.4, lon0=-12.0, di=0.025, dj=0.025,
                 jScan=0)

STATIONS = [
    dict(id="1", lat=45.93, lon=6.86, name="Chamonix"),        # dedans
    dict(id="2", lat=45.20, lon=5.80, name="Grenoble-ish"),    # dedans
    dict(id="3", lat=48.39, lon=-4.49, name="Brest"),          # dehors
    dict(id="4", lat=44.79, lon=6.00, name="juste sous latmin"),  # dehors
    dict(id="5", lat=45.00, lon=7.00, name="suspecte"),        # dedans
]


def section_horizons():
    """⛔ DEUX HORIZONS, ET TROIS FAÇONS DE LES CASSER EN SILENCE (13/08).

    Le produit B va à 51 h, l'archive reste à 24 h. Trois pièges, un par
    bloc, et aucun ne lève :

      1. **La fraîcheur troquée contre des heures lointaines.** Si la
         rallonge entrait dans le critère de sélection, un run vieux de
         trois heures publiant ses 52 échéances battrait un run FRAIS qui
         n'en publie que 25 — les deux sont valides, et `meilleur`
         compare des longueurs.
      2. **Un trou au milieu de la coupe.** Les tampons sont indexés par
         position ; une rallonge non contiguë ferait disparaître 14 h
         entre 13 h et 15 h.
      3. **L'archive qui avale la rallonge.** Elle est DÉFINITIVE ; une
         échéance de trop y reste pour toujours.
    """
    print("\n── 9. ⛔ Deux horizons : l'archive à 24 h, la grille à 51 ──")
    vrai = I.covered_steps
    try:
        # ── 1. Un run FRAIS et complet gagne, et on n'interroge même pas
        #       le précédent — même s'il publierait 51 h.
        vus = []

        def stub_frais(ref, paquet, grille, voulues, model=None):
            if ref not in vus:
                vus.append(ref)
            # Le plus récent : complet à 24 h, rien au-delà.
            # Les précédents : tout, jusqu'à 51 h.
            return ({h for h in voulues if h <= 24} if vus.index(ref) == 0
                    else set(voulues))

        I.covered_steps = stub_frais
        ref, _run, steps = I.choisir_run(24, profondeur=3,
                                         crier=lambda *_a: None,
                                         max_heures_grille=51)
        verifier("⛔ un run FRAIS complet à 24 h est retenu SANS que le "
                 "précédent soit même interrogé — sinon on troquerait la "
                 "fraîcheur, seule chose qu'AGRUME apporte, contre des "
                 "heures lointaines",
                 len(vus) == 1 and steps == list(range(0, 25)),
                 f"{len(vus)} run(s) sondé(s) · {len(steps)} échéances")

        # ── 2. La rallonge, et le trou qui l'arrête.
        def stub_trou(_ref, _paquet, _grille, voulues, model=None):
            return {h for h in voulues if h <= 33 and h != 30}

        I.covered_steps = stub_trou
        _r, _run, steps = I.choisir_run(24, profondeur=1,
                                        crier=lambda *_a: None,
                                        max_heures_grille=51)
        verifier("⚠️ la rallonge s'arrête au PREMIER trou (33 est publié, "
                 "30 non → on va jusqu'à 29) — un trou au milieu ferait "
                 "disparaître une heure entre deux autres",
                 steps == list(range(0, 30)),
                 f"jusqu'à +{steps[-1]} h")

        # ── 3. Archive incomplète : PAS de rallonge du tout.
        def stub_court(_ref, _paquet, _grille, voulues, model=None):
            return {h for h in voulues if h <= 19 or h >= 25}

        I.covered_steps = stub_court
        _r, _run, steps = I.choisir_run(24, profondeur=1,
                                        crier=lambda *_a: None,
                                        max_heures_grille=51)
        verifier("⛔ archive tronquée (0→19) : la rallonge est ABANDONNÉE, "
                 "pas recollée — sinon la coupe aurait un trou de six "
                 "heures en son milieu",
                 steps == list(range(0, 20)),
                 f"jusqu'à +{steps[-1]} h")

        # ── 4. Et l'archive n'avale pas la rallonge.
        col = C.Colonnes("2026-08-13T00:00:00Z",
                         [{"id": "x", "lat": 45.0, "lon": 6.0}],
                         list(range(0, 25)))
        verifier("⛔ `accepte_echeance` refuse ce qui dépasse l'horizon de "
                 "l'archive — sans lui `poser()` lèverait un KeyError, que "
                 "`parcourir()` AVALE, et la grille perdrait justement les "
                 "échéances qu'on est allé chercher",
                 col.accepte_echeance(24) and not col.accepte_echeance(25))
        verifier("⚠️ et l'archive a bien la taille de SES échéances, pas de "
                 "celles qui ont été téléchargées",
                 col.c0025.shape[-1] == 25 and col.ziso.shape[-1] == 25,
                 f"{col.c0025.shape[-1]} échéances")
    finally:
        I.covered_steps = vrai


def main():
    print("── Sélection des balises ─────────────────────────────────")
    b = Q.balises_du_domaine(STATIONS, suspectes=["5"])
    verifier("seules les balises du domaine sont retenues",
             [x["id"] for x in b] == ["1", "2", "5"], str([x["id"] for x in b]))
    verifier("les bornes du domaine sont exclusives de ce qui est dehors",
             all(x["id"] != "4" for x in b))
    verifier("⚠️ une balise `position_suspecte` est MARQUÉE, pas retirée",
             any(x["id"] == "5" and x["position_suspecte"] for x in b))
    verifier("les autres ne le sont pas",
             not any(x["position_suspecte"] for x in b if x["id"] != "5"))
    verifier("l'ordre est stable (trié par identifiant)",
             [x["id"] for x in b] == sorted(x["id"] for x in b))

    print("\n── Indexation dans la grille native ──────────────────────")
    idx, hors = Q.index_plats(META_0025, b)
    verifier("chaque balise du domaine a un indice", (idx >= 0).all(), str(idx))
    verifier("aucune n'est hors grille France", hors == [], str(hors))
    # Vérification arithmétique indépendante, sur la première balise.
    i = round((b[0]["lon"] - META_0025["lon0"]) / META_0025["di"])
    j = round((META_0025["lat0"] - b[0]["lat"]) / META_0025["dj"])
    verifier("l'indice plat vaut bien j × Ni + i",
             idx[0] == j * META_0025["Ni"] + i, f"{idx[0]} = {j}×1121+{i}")
    dehors = Q.index_plats(META_0025, [dict(id="x", lat=80.0, lon=0.0,
                                            nom="", source="",
                                            position_suspecte=False)])
    verifier("une balise hors grille vaut -1 et est signalée",
             dehors[0][0] == -1 and dehors[1] == ["x"])

    print("\n── ⚠️ Le garde-fou contre le décalage silencieux ──────────")
    Q.verifier_grille(META_0025, dict(META_0025), "témoin")
    verifier("une grille identique passe", True)
    for cle, faux in (("Ni", 1120), ("di", 0.05), ("jScan", 1)):
        m = dict(META_0025); m[cle] = faux
        try:
            Q.verifier_grille(META_0025, m, "témoin")
            verifier(f"un changement de {cle} fait LEVER", False)
        except Q.Abort as e:
            verifier(f"un changement de {cle} fait LEVER",
                     "sans que rien n'ait l'air anormal" in str(e))
    m = dict(META_0025); m["lat0"] = 55.4001
    try:
        Q.verifier_grille(META_0025, m, "témoin")
        verifier("un déplacement d'origine de 0,0001° fait LEVER", False)
    except Q.Abort:
        verifier("un déplacement d'origine de 0,0001° fait LEVER", True)

    print("\n── ⚠️ Quantification : on MESURE la perte, on ne la suppose pas ──")
    rng = np.random.default_rng(42)
    echantillons = {
        "u": rng.uniform(-40, 40, 20000),
        "v": rng.uniform(-40, 40, 20000),
        "t": rng.uniform(220, 320, 20000),        # KELVINS, comme le GRIB
        "r": rng.uniform(0, 100, 20000),
        "tke": rng.uniform(0, 20, 20000),
    }
    par_nom = {p["nom"]: p for p in Q.PARAMS_0025}
    for nom, ech in echantillons.items():
        p = par_nom[nom]
        err = Q.erreur_quantification(ech, p)
        verifier(f"{nom:>3} : erreur ≤ {p['tolerance']} {p['unite']}",
                 err <= p["tolerance"], f"mesurée {err:.4f} {p['unite']}")

    # Le cœur du sujet : la même température, SANS le décalage.
    sans = dict(par_nom["t"]); sans["decalage"] = 0.0
    err_k = Q.erreur_quantification(echantillons["t"], sans)
    err_c = Q.erreur_quantification(echantillons["t"], par_nom["t"])
    verifier("⚠️ en KELVINS le float16 perd un facteur ~8 — c'est bien "
             "pour ça qu'on stocke en °C",
             err_k > 6 * err_c,
             f"{err_k:.3f} K contre {err_c:.4f} °C, rapport "
             f"×{err_k / max(err_c, 1e-9):.0f}")

    print("\n── Valeurs manquantes : NaN, jamais zéro ─────────────────")
    v = np.array([3.0, np.nan, 9999.0, -9999.0, 1e9, 5.0])
    q = Q.quantifier(v, par_nom["u"])
    verifier("NaN reste NaN", bool(np.isnan(q[1])))
    verifier("la sentinelle 9999 devient NaN, PAS 9999",
             bool(np.isnan(q[2])) and bool(np.isnan(q[3])))
    verifier("une valeur physiquement absurde devient NaN",
             bool(np.isnan(q[4])))
    verifier("les valeurs saines survivent",
             abs(float(q[0]) - 3.0) < 0.01 and abs(float(q[5]) - 5.0) < 0.01)
    verifier("⚠️ aucun manquant ne devient 0 (0 m/s est un vent crédible)",
             not np.any(np.asarray(q, dtype=np.float32)[[1, 2, 3, 4]] == 0.0))

    print("\n── ⚠️ Le 10 m ne vient pas d'où on croit ──────────────────")
    f = I.filtre_0025("HP1")
    verifier("`10u` au niveau 10 → u à 10 m",
             f("10u", "heightAboveGround", 10) == ("u", 10))
    verifier("`u` au niveau 20 → u à 20 m",
             f("u", "heightAboveGround", 20) == ("u", 20))
    verifier("`u` à un niveau qui n'existe pas est ignoré",
             f("u", "heightAboveGround", 42) is None)
    verifier("un isobare n'est jamais pris pour un niveau hauteur",
             f("u", "isobaricInhPa", 850) is None)
    verifier("la TKE n'est PAS dans HP1", f("tke", "heightAboveGround", 500) is None)
    f2 = I.filtre_0025("HP2")
    verifier("⚠️ la TKE est dans HP2, et elle y est bien prise",
             f2("tke", "heightAboveGround", 500) == ("tke", 500))
    verifier("le vent n'est PAS repris depuis HP2",
             f2("u", "heightAboveGround", 500) is None)

    fh = I.filtre_001("HP1")
    fs = I.filtre_001("SP1")
    verifier("maille fine : u à 20/50/100 m depuis HP1",
             [fh("u", "heightAboveGround", n) for n in (20, 50, 100)]
             == [("u", 20), ("u", 50), ("u", 100)])
    verifier("⛔ maille fine : rien au-dessus de 100 m (la donnée n'existe pas)",
             fh("u", "heightAboveGround", 250) is None)
    verifier("maille fine : les 10 m viennent de SP1, pas de HP1",
             fh("10u", "heightAboveGround", 10) is None
             and fs("10u", "heightAboveGround", 10) == ("u", 10))
    verifier("SP1 ne livre que les 10 m",
             fs("u", "heightAboveGround", 100) is None)

    print("\n── Choix des fichiers à tirer ────────────────────────────")
    faux = {
        "pnt/R/arome/0025/HP1/": [
            ("a__0025__HP1__00H06H__R.grib2", 818_000_000),
            ("a__0025__HP1__07H12H__R.grib2", 693_000_000),
            ("a__0025__HP1__49H51H__R.grib2", 350_000_000)],
        "pnt/R/arome/001/SP1/": [
            (f"a__001__SP1__{h:02d}H__R.grib2", 23_000_000) for h in range(0, 52)],
    }
    f0 = I.fichiers_du_paquet("R", "0025", "HP1", list(range(0, 8)),
                              lister=lambda p: faux[p])
    verifier("0,025° : on prend les bundles qui INTERSECTENT le besoin",
             [c.split("__")[3] for c, _ in f0] == ["00H06H", "07H12H"],
             str([c.split("__")[3] for c, _ in f0]))
    f1 = I.fichiers_du_paquet("R", "001", "SP1", [0, 3, 7],
                              lister=lambda p: faux[p])
    verifier("0,01° : on ne tire QUE les heures retenues "
             "(sinon ~550 Mo pour rien)",
             len(f1) == 3, f"{len(f1)} fichiers sur 52 publiés")

    print("\n── Le conteneur, sa disposition et son remplissage ───────")
    col = C.Colonnes("2026-08-10T00:00:00Z", b, [0, 1, 2])
    verifier("disposition (balise, paramètre, niveau, échéance)",
             col.c0025.shape == (3, len(Q.PARAMS_0025), 25, 3)
             and col.c001.shape == (3, 2, 4, 3),
             f"{col.c0025.shape} et {col.c001.shape}")
    verifier("float16 des deux côtés",
             col.c0025.dtype == np.float16 and col.c001.dtype == np.float16)
    verifier("un conteneur neuf est VIDE, pas nul",
             col.remplissage()[GRID_3D] == 0.0)
    col.poser(GRID_3D, "u", 500, 1, np.array([1.0, 2.0, 3.0], dtype=np.float16))
    k = NIVEAUX_H_0025.index(500)
    verifier("`poser` écrit à la bonne case",
             list(np.asarray(col.c0025[:, 0, k, 1], dtype=np.float32))
             == [1.0, 2.0, 3.0])
    verifier("et nulle part ailleurs",
             not np.isfinite(np.asarray(col.c0025[:, 0, k, 0],
                                        dtype=np.float32)).any())
    col.poser(GRID_FINE, "v", 100, 0, np.array([7.0, 8.0, 9.0], dtype=np.float16))
    verifier("la maille fine a ses propres niveaux",
             float(col.c001[0, 1, NIVEAUX_H_001.index(100), 0]) == 7.0)
    verifier("un run partiel SE VOIT dans le remplissage",
             0.0 < col.remplissage()[GRID_3D] < 0.02,
             f"{col.remplissage()[GRID_3D] * 100:.2f} %")

    print("\n── ⚠️ Les deux mailles restent SÉPARÉES dans l'archive ────")
    man = col.manifeste()
    verifier("le manifeste porte les deux jeux de niveaux",
             man["niveaux"][GRID_3D] == list(NIVEAUX_H_0025)
             and man["niveaux"][GRID_FINE] == list(NIVEAUX_H_001))
    verifier("il dit que 35 m et 75 m n'existent pas en maille fine",
             "35 m et 75 m n'existent PAS" in man["avertissement"])
    verifier("il dit que le raccord n'est pas mesuré",
             "n'est pas encore mesurée" in man["avertissement"])
    verifier("il dit que les niveaux sont AGL, au-dessus du sol MODÈLE",
             "sol MODÈLE" in man["reference_verticale"])
    verifier("il porte chaque balise, avec son identifiant",
             len(man["balises"]) == 3 and man["balises"][0]["id"] == "1")

    print("\n── Aller-retour sur disque ───────────────────────────────")
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "c.npz"
        col.ecrire_npz(p)
        relu, man2 = C.Colonnes.lire_npz(p, man)
        a = np.asarray(col.c0025, dtype=np.float32)
        bb = np.asarray(relu.c0025, dtype=np.float32)
        verifier("les valeurs survivent au tour de disque",
                 np.array_equal(a[np.isfinite(a)], bb[np.isfinite(bb)]))
        verifier("les NaN aussi (donc les trous restent des trous)",
                 np.array_equal(np.isnan(a), np.isnan(bb)))
        verifier("le run et les échéances sont relus",
                 relu.run == col.run and relu.steps == col.steps)
        taille = p.stat().st_size
        verifier("une archive de 3 balises tient en quelques kilo-octets",
                 taille < 50_000, f"{taille / 1024:.1f} Ko")

    print("\n── ⚠️ L'ALTITUDE DES ISOBARES NE PASSE PAS PAR LE float16 ──")
    # Le float16 a un pas RELATIF de ~0,05 % : à 7 000 m ça fait 8 m. Or
    # cet axe porte le raccord et sert à discuter d'écarts d'orographie de
    # quelques dizaines de mètres. Et contrairement aux kelvins, aucun
    # décalage ne sauve : une altitude va de 0 à 7 000 m.
    # ⚠️ 12/08 — ON ENTRE DÉSORMAIS UN GÉOPOTENTIEL, PAS UNE ALTITUDE.
    # `PARAM_ALTITUDE` porte maintenant `facteur = 1/G` : la division est
    # dans le descripteur, donc dans `quantifier()`, donc au même endroit
    # pour les deux produits. Nourrir ce banc en mètres reviendrait à
    # diviser une seconde fois — il rendait 0,25 m au lieu de 2,00 et
    # concluait « le float16 suffit », exactement l'erreur que ce test
    # existe pour empêcher.
    alt = rng.uniform(0, 7500, 20000)
    geo = alt * G
    e16 = Q.erreur_quantification(geo, Q.PARAM_ALTITUDE, np.float16)
    e32 = Q.erreur_quantification(geo, Q.PARAM_ALTITUDE, np.float32)
    # ⓘ 2,00 m exactement, et ce n'est pas un hasard : entre 4 096 et
    # 8 192 m le pas du float16 vaut 4 m, donc l'arrondi coûte au pire la
    # moitié. Le seuil est posé sous cette valeur pour que le test dise
    # « des mètres » et pas « exactement 2,00 », qui serait un test de
    # l'implémentation du float16 plutôt que de notre choix.
    verifier("en float16, l'altitude perd des MÈTRES",
             e16 >= 1.0, f"{e16:.2f} m")
    verifier("en float32, elle perd un millimètre au plus",
             e32 < 0.01, f"{e32 * 1000:.3f} mm")
    verifier("⚠️ le float32 fait au moins 20 fois mieux — c'est ce qui "
             "justifie les 175 Ko de plus par run",
             e16 / max(e32, 1e-12) > 20,
             f"rapport ×{e16 / max(e32, 1e-12):.0f}")
    verifier("le plafond physique attrape une altitude absurde",
             bool(np.isnan(Q.quantifier(np.array([1e6]), Q.PARAM_ALTITUDE,
                                        np.float32)[0])))

    print("\n── Les isobares dans le conteneur ─────────────────────────")
    col2 = C.Colonnes("R", b, [0, 1])
    verifier("ciso en float16, ziso en float32",
             col2.ciso.dtype == np.float16 and col2.ziso.dtype == np.float32,
             f"{col2.ciso.dtype} / {col2.ziso.dtype}")
    verifier("14 niveaux isobares retenus sur les 24 publiés",
             col2.ciso.shape[2] == 14 and len(NIVEAUX_P_TOUS) == 24)
    verifier("⚠️ la bande monte à 400 hPa, pas 500 — sinon les balises "
             "les plus hautes n'auraient RIEN au-dessus de z_s + 3000",
             min(NIVEAUX_P) == 400)
    j = NIVEAUX_P.index(700)
    col2.poser_isobare("zp", 700, 0, np.array([1000.0, 2000.0, 3000.0]))
    verifier("`zp` va dans ziso…",
             list(np.asarray(col2.ziso[:, j, 0])) == [1000.0, 2000.0, 3000.0])
    verifier("…et NULLE PART dans ciso (l'axe ne passe pas par le float16)",
             not np.isfinite(np.asarray(col2.ciso, dtype=np.float32)).any())
    col2.poser_isobare("u", 700, 0, np.array([5.0, 6.0, 7.0], dtype=np.float16))
    verifier("les autres paramètres vont dans ciso",
             float(col2.ciso[0, 0, j, 0]) == 5.0)
    m2 = col2.manifeste()
    verifier("le manifeste porte les niveaux isobares",
             m2["niveaux"]["isobares_hPa"] == list(NIVEAUX_P))
    verifier("il dit que les niveaux souterrains sont archivés mais à masquer",
             "masqués à la lecture" in m2["avertissement"])
    verifier("le remplissage distingue les isobares de leur altitude",
             "isobares" in m2["remplissage"]
             and "altitude_iso" in m2["remplissage"])

    with tempfile.TemporaryDirectory() as d:
        p2 = Path(d) / "c.npz"
        col2.ecrire_npz(p2)
        relu, _ = C.Colonnes.lire_npz(p2, m2)
        verifier("l'altitude isobare survit au disque SANS perte",
                 float(relu.ziso[1, j, 0]) == 2000.0)
        # Une archive écrite avant l'étape 5 n'a ni ciso ni ziso.
        p3 = Path(d) / "vieux.npz"
        np.savez_compressed(p3, c0025=col2.c0025, c001=col2.c001,
                            echeances=np.asarray(col2.steps, dtype=np.int16))
        vieux, _ = C.Colonnes.lire_npz(p3, m2)
        verifier("⚠️ une archive d'AVANT les isobares se relit quand même",
                 vieux.c0025.shape == col2.c0025.shape
                 and not np.isfinite(np.asarray(vieux.ziso,
                                                dtype=np.float32)).any())

    print("\n── ⚠️ Le vent se compare par u/v, JAMAIS par l'angle ──────")
    # Critère d'acceptation du lot : « vérifié sur une colonne traversant
    # 350° → 010° ». C'est le piège classique : deux vents à 20° l'un de
    # l'autre de part et d'autre du nord ont des angles qui diffèrent de
    # 340 si on les soustrait naïvement.
    import marche_raccord as M

    def uv(deg_meteo, force):
        # convention météo : d'où vient le vent
        a = np.radians(270.0 - deg_meteo)
        return force * np.cos(a), force * np.sin(a)

    u_a, v_a = uv(350.0, 5.0)
    u_b, v_b = uv(10.0, 5.0)
    ecart_vect = float(np.hypot(u_b - u_a, v_b - v_a))
    naif = abs(10.0 - 350.0)
    a0 = np.degrees(np.arctan2(v_a, u_a))
    a1 = np.degrees(np.arctan2(v_b, u_b))
    replie = float(abs((a1 - a0 + 180) % 360 - 180))
    verifier("350° → 010° : la soustraction naïve donne 340°, absurde",
             abs(naif - 340) < 1e-9)
    verifier("le repliement dans [-180,180] donne bien 20°",
             abs(replie - 20.0) < 1e-6, f"{replie:.3f}°")
    verifier("la norme de la différence VECTORIELLE reste petite "
             "(2·5·sin(10°) ≈ 1,74 m/s)",
             abs(ecart_vect - 2 * 5.0 * np.sin(np.radians(10))) < 1e-6,
             f"{ecart_vect:.3f} m/s")
    verifier("les quantiles de l'outil de marche sont bien ordonnés",
             (lambda q: q["d1"] <= q["mediane"] <= q["d9"] <= q["max"])(
                 M.quantiles([3, 1, 2, 9, 5, 4, 8, 7, 6, 10])))
    verifier("quantiles d'un échantillon vide → None, pas une erreur",
             M.quantiles([]) is None)

    section_horizons()

    print("\n  colonnes :", "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
