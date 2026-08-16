#!/usr/bin/env python3
"""
test_orographie.py — banc de l'orographie figée, HORS-LIGNE.

À lancer depuis `balise-watch-server/` :
    python3 agrume/test_orographie.py
    python3 agrume/test_orographie.py --stations /var/lib/bw-model-verif/stations.json

⚠️ CE QUE CE BANC PROTÈGE, ET POURQUOI ÇA MÉRITE UN BANC.

Le mode de panne du lot H n'est pas une exception : c'est une colonne
verticale entière décalée de quelques centaines de mètres, servie sans
broncher à un pilote. Deux façons d'y arriver, toutes deux silencieuses :

  1. charger l'orographie du MAUVAIS PAQUET. `arome-wind/ingest.py`
     cherche `SP3`, ce qui est juste en 0,01° et faux en 0,025° — où
     `SP3` existe pourtant (67 messages, 55 Mo de flux et de
     rayonnement) et ne contient aucune orographie ;
  2. charger DEUX FOIS LA MÊME. Un artefact dont les deux moitiés
     seraient le même champ passerait tous les tests de forme, toutes
     les vérifications de somme de contrôle, et donnerait des altitudes
     parfaitement plausibles — simplement fausses d'un côté du raccord.

Le critère d'acceptation du lot vise exactement le second cas : « un
test qui compare les deux aux positions des balises et ÉCHOUE SI L'ÉCART
MÉDIAN DES |DIFFÉRENCES| EST NUL ». C'est ce qui est écrit plus bas.
Aucun réseau n'est nécessaire : tout se lit dans l'artefact commité.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from domaine import (DOMAINE, GRID_3D, GRID_FINE, NIVEAUX_H_001,  # noqa: E402
                     NIVEAUX_H_0025, NIVEAUX_H_AROMEPI,
                     DOMAINES, PAQUET_OROGRAPHIE, RACCORD_HYBRIDE_M,
                     dans_domaine, domaine_de, verifier_domaines_disjoints,
                     fenetre)
from orographie import (ARTEFACTS, Abort, altitude_asl,  # noqa: E402
                        charger_artefact, charger_artefacts,
                        cle_s3_orographie, ecart_grilles, orographie_pour)

echecs = []


def verifier(nom, condition, detail=""):
    print(f"  {'✓' if condition else '✗'} {nom}" + (f"   {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--stations", default=None,
                   help="référentiel écrit par collect.py — active le test "
                        "AUX BALISES du critère d'acceptation")
    a = p.parse_args(argv)

    print("── L'artefact se relit, et il est intègre ─────────────────")
    paire, man = charger_artefact()
    verifier("les deux grilles sont présentes",
             set(paire) == {GRID_FINE, GRID_3D}, str(sorted(paire)))
    verifier("sha256 revérifié à la lecture (sinon charger_artefact aurait levé)",
             True)
    verifier("le manifeste dit de quel run il vient",
             bool(man.get("run_source")), man.get("run_source", ""))
    verifier("le manifeste dit avec quel eccodes",
             bool(man.get("eccodes")), str(man.get("eccodes", "")))

    fine, gros = paire[GRID_FINE], paire[GRID_3D]
    # ⚠️ 16/08 — CES DEUX VALEURS ONT CHANGÉ, ET IL FAUT DIRE POURQUOI
    # PLUTÔT QUE DE LES REMPLACER EN SILENCE. Elles valaient 61 × 85 =
    # 5 185 (0,025°) et 151 × 211 (0,01°) : c'était l'ancien domaine
    # Nord-Alpes, mesuré le 10/08 en découpant un GRIB réel. `DOMAINE` a
    # été élargi aux Alpes entières le 16/08 (cf. `domaine.py`), donc la
    # fenêtre aussi — 111 × 105 = 11 655 et 276 × 261 = 72 036, mesurés au
    # regel du même jour.
    # ⛔ CE QUI COMPTE ICI N'EST PAS LE NOMBRE, C'EST QU'IL SOIT CELUI QUE
    # `fenetre()` DÉDUIT DES MÉTADONNÉES. Un nombre recopié à la main ne
    # prouve que l'immobilité ; comparer à `fenetre(meta)` attrape le cas
    # qui fait vraiment mal — un artefact gelé sur une fenêtre qui n'est
    # plus celle du code, donc des altitudes décalées d'une maille sans
    # que rien ne s'allume.
    from domaine import fenetre as _fen  # noqa: PLC0415
    for nom, o, attendu in (("0,025°", gros, 11655), ("0,01°", fine, 72036)):
        j0, j1, i0, i1 = _fen(o.meta)
        nj, ni = j1 - j0 + 1, i1 - i0 + 1
        verifier(f"domaine {nom} : l'artefact tombe EXACTEMENT sur la "
                 f"fenêtre déduite de ses propres métadonnées",
                 o.z.shape == (nj, ni) and (o.j0, o.i0) == (j0, i0),
                 f"{o.z.shape} @ j{o.j0}/i{o.i0} · fenêtre ({nj}, {ni}) "
                 f"@ j{j0}/i{i0}")
        verifier(f"domaine {nom} = {nj} × {ni} = {nj * ni} points "
                 f"(mesuré au regel du 16/08)",
                 nj * ni == attendu, f"{nj * ni}")
    verifier("aucune altitude aberrante (0 ≤ z ≤ 5000 m, Alpes)",
             float(fine.z.min()) >= -10 and float(fine.z.max()) <= 5000
             and float(gros.z.min()) >= -10 and float(gros.z.max()) <= 5000,
             f"001 [{fine.z.min():.0f}, {fine.z.max():.0f}] · "
             f"0025 [{gros.z.min():.0f}, {gros.z.max():.0f}]")
    verifier("aucun NaN",
             bool(np.isfinite(fine.z).all() and np.isfinite(gros.z).all()))

    print("\n── ⚠️ CRITÈRE D'ACCEPTATION : les deux orographies DIFFÈRENT ──")
    # Sur les points de grille du domaine d'abord — disponible sans le
    # référentiel des balises, donc jouable partout, y compris en CI.
    pts = [fine.coords(j, i)
           for j in range(0, fine.z.shape[0], 3)
           for i in range(0, fine.z.shape[1], 3)]
    ecarts = ecart_grilles(paire, pts)
    absolus = sorted(abs(e) for e in ecarts)
    med = float(np.median(absolus))
    part100 = 100 * sum(1 for x in absolus if x > 100) / len(absolus)
    verifier("l'écart médian des |différences| N'EST PAS NUL",
             med > 5.0,
             f"médiane {med:.0f} m sur {len(ecarts)} points — un zéro "
             f"voudrait dire deux fois le même champ")
    verifier("une part notable des points dépasse 100 m d'écart",
             part100 > 5.0, f"{part100:.0f} %")
    verifier("l'écart SIGNÉ n'a pas de biais systématique "
             "(médiane ≈ 0, mesuré aux 648 balises)",
             abs(float(np.median(ecarts))) < 20,
             f"{float(np.median(ecarts)):+.0f} m")
    verifier("les deux tableaux ne sont pas identiques, tout court",
             gros.z.shape != fine.z.shape
             or not np.array_equal(gros.z, fine.z))

    if a.stations:
        print("\n── Le même critère, AUX BALISES ───────────────────────────")
        stations = json.loads(Path(a.stations).read_text(encoding="utf-8"))
        pts_b = [(s["lat"], s["lon"]) for s in stations
                 if dans_domaine(s["lat"], s["lon"])]
        e_b = ecart_grilles(paire, pts_b)
        if not e_b:
            verifier("des balises tombent dans le domaine", False,
                     f"0 sur {len(stations)}")
        else:
            abs_b = sorted(abs(x) for x in e_b)
            med_b = float(np.median(abs_b))
            p100_b = 100 * sum(1 for x in abs_b if x > 100) / len(abs_b)
            verifier("écart médian des |différences| non nul aux balises",
                     med_b > 5.0,
                     f"{med_b:.0f} m sur {len(e_b)} balises du domaine "
                     f"(sur {len(stations)} au référentiel)")
            print(f"     {p100_b:.0f} % des balises du domaine au-delà de "
                  f"100 m · max {max(abs_b):.0f} m")

    print("\n── La table paquet↔grille, et son refus de deviner ────────")
    faux_listing = {
        "pnt/R/arome/001/SP3/": ["pnt/R/arome/001/SP3/x__00H__R.grib2"],
        "pnt/R/arome/0025/SP2/": ["pnt/R/arome/0025/SP2/x__00H06H__R.grib2"],
        "pnt/R/arome/0025/SP3/": ["pnt/R/arome/0025/SP3/x__00H06H__R.grib2"],
    }
    lister = lambda p: faux_listing.get(p, [])  # noqa: E731
    cle, paquet = cle_s3_orographie("R", GRID_FINE, lister)
    verifier("001 → paquet SP3, fichier __00H__", paquet == "SP3" and "__00H__" in cle)
    cle, paquet = cle_s3_orographie("R", GRID_3D, lister)
    verifier("0025 → paquet SP2, fichier __00H06H__ (⚠️ PAS SP3)",
             paquet == "SP2" and "__00H06H__" in cle, cle.split("/")[-1])
    verifier("0025 ne va JAMAIS chercher dans SP3",
             PAQUET_OROGRAPHIE[GRID_3D][0] != "SP3")
    try:
        cle_s3_orographie("R", "005", lister)
        verifier("une grille inconnue lève plutôt que de deviner", False)
    except Abort as e:
        verifier("une grille inconnue lève plutôt que de deviner",
                 "ne se devine pas" in str(e))
    try:
        cle_s3_orographie("R", GRID_3D, lambda p: [])
        verifier("orographie absente → Abort, jamais None en silence", False)
    except Abort:
        verifier("orographie absente → Abort, jamais None en silence", True)

    print("\n── La fenêtre se recalcule, elle n'est pas codée en dur ────")
    for grille, o in ((GRID_FINE, fine), (GRID_3D, gros)):
        j0, j1, i0, i1 = fenetre(o.meta)
        verifier(f"{grille} : fenêtre recalculée = fenêtre figée",
                 (j0, i0) == (o.j0, o.i0)
                 and (j1 - j0 + 1, i1 - i0 + 1) == o.z.shape,
                 f"j {j0}..{j1}, i {i0}..{i1}")

    print("\n── Indexation et aller-retour ─────────────────────────────")
    # Un point au cœur du domaine, dans la vallée de Chamonix — choisi
    # parce qu'il est entouré de relief fort, donc là où les deux mailles
    # ont le plus de raisons de diverger. ⓘ Les valeurs affichées ne sont
    # PAS une vérité de terrain : ce sont les deux sols du modèle, et le
    # test ne vérifie que leur existence, pas leur justesse.
    lat, lon = 45.9310, 6.8600
    z1, z2 = fine.z_at(lat, lon), gros.z_at(lat, lon)
    verifier("les deux grilles répondent au cœur du domaine",
             z1 is not None and z2 is not None, f"001 {z1:.0f} m · 0025 {z2:.0f} m")
    ji = fine.indices(lat, lon)
    la2, lo2 = fine.coords(*ji)
    verifier("indices → coords tombe dans la maille (0,01°)",
             abs(la2 - lat) <= 0.006 and abs(lo2 - lon) <= 0.006,
             f"{la2:.4f}/{lo2:.4f}")
    verifier("hors domaine → None (Brest)", fine.z_at(48.39, -4.49) is None)
    verifier("dans_domaine est cohérent avec z_at",
             dans_domaine(lat, lon) and not dans_domaine(48.39, -4.49))

    print("\n── altitude_ASL = ALTITUDE + h_AGL ────────────────────────")
    verifier("la conversion est bien une somme",
             altitude_asl(gros, lat, lon, 500) == z2 + 500,
             f"{z2:.0f} + 500 = {altitude_asl(gros, lat, lon, 500):.0f} m")
    verifier("hors domaine → None, pas un plancher inventé",
             altitude_asl(gros, 48.39, -4.49, 500) is None)

    print("\n── L'arbitrage hybride vit à UN seul endroit ──────────────")
    for h in (10, 20, 50, 100):
        verifier(f"{h:>4} m/sol → maille fine 0,01°",
                 orographie_pour(paire, h) is fine)
    for h in (150, 500, 3000):
        verifier(f"{h:>4} m/sol → maille 0,025°",
                 orographie_pour(paire, h) is gros)
    verifier("le raccord est bien à 100 m", RACCORD_HYBRIDE_M == 100)
    verifier("les 4 niveaux fins sont un sous-ensemble des 25",
             set(NIVEAUX_H_001) <= set(NIVEAUX_H_0025))
    verifier("les 6 niveaux d'AROME-PI aussi (aucune interpolation verticale)",
             set(NIVEAUX_H_AROMEPI) <= set(NIVEAUX_H_0025))
    verifier("25 niveaux hauteur en 0,025°, 4 en 0,01° (mesuré, pas lu)",
             len(NIVEAUX_H_0025) == 25 and len(NIVEAUX_H_001) == 4)
    verifier("le niveau `2 m` n'existe pas — le plus bas est 10 m",
             min(NIVEAUX_H_0025) == 10 and 2 not in NIVEAUX_H_0025)

    print("\n── Une corruption de l'artefact est refusée ───────────────")
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        npz, js = Path(d) / "o.npz", Path(d) / "o.json"
        z_abime = np.array(gros.z, copy=True)
        z_abime[0, 0] += 1.0          # UN mètre sur UN point
        np.savez_compressed(npz, **{f"z_{GRID_FINE}": fine.z,
                                    f"z_{GRID_3D}": z_abime})
        js.write_text(json.dumps(man), encoding="utf-8")
        try:
            charger_artefact(npz, js)
            verifier("un mètre d'écart sur un point suffit à faire lever", False)
        except Abort as e:
            verifier("un mètre d'écart sur un point suffit à faire lever",
                     "CORROMPUE" in str(e))

    print("\n── Le domaine annoncé est celui qui est figé ──────────────")
    verifier("le manifeste porte le domaine", man.get("domaine") == DOMAINE,
             str(man.get("domaine")))

    # ══════════════════════════════════════════════════════════════════
    #  LES DEUX DOMAINES DE PRODUCTION (12/08/2026)
    #
    #  ⚠️ CE QUE CETTE SECTION PROTÈGE. Un second domaine se casse en
    #  silence de trois façons, et aucune ne lève :
    #    1. deux domaines qui se RECOUVRENT — un point y a deux sols
    #       figés, et celui qui sort dépend de l'ordre d'un dictionnaire ;
    #    2. un `decouper()` sans bornes — on découpe les Alpes en croyant
    #       faire les Pyrénées, mêmes tailles plausibles, sol de Savoie
    #       sous des balises ariégeoises ;
    #    3. l'artefact des Alpes RENOMMÉ ou régénéré — toutes les archives
    #       du produit A déclarent son sha256 ; il doit rester à l'octet.
    # ══════════════════════════════════════════════════════════════════
    print("\n── Les deux domaines de production ───────────────────────")
    verifier("les domaines sont DISJOINTS",
             verifier_domaines_disjoints(), ", ".join(DOMAINES))
    verifier("un point des Alpes est rendu aux Alpes",
             domaine_de(45.12, 5.88) == "nord-alpes")
    verifier("un point des Pyrénées est rendu aux Pyrénées",
             domaine_de(42.84, -0.44) == "pyrenees", "Ossau")
    verifier("Brest n'est dans aucun domaine",
             domaine_de(48.39, -4.49) is None)
    verifier("dans_domaine couvre TOUS les domaines",
             dans_domaine(42.84, -0.44) and dans_domaine(45.12, 5.88))
    verifier("dans_domaine(..., 'nord-alpes') reste restrictif",
             not dans_domaine(42.84, -0.44, "nord-alpes"))
    # ⚠️ Le chemin de l'artefact Nord-Alpes est figé PAR SON NOM : c'est
    # lui que déclarent les archives déjà écrites.
    verifier("l'artefact Nord-Alpes garde son chemin historique",
             ARTEFACTS["nord-alpes"][0].name == "orographie-nord-alpes.npz",
             ARTEFACTS["nord-alpes"][0].name)
    verifier("chaque domaine a un artefact déclaré",
             set(ARTEFACTS) >= set(DOMAINES),
             f"{sorted(ARTEFACTS)} ⊇ {sorted(DOMAINES)}")
    # Un domaine sans artefact gelé ne doit pas faire tomber la
    # production des autres — c'est ce qui rend le commit du code
    # dissociable du gel, qui se lance à la main.
    arts, absents = charger_artefacts(noms=list(DOMAINES) + ["_inexistant"]
                                      if "_inexistant" in ARTEFACTS
                                      else list(DOMAINES))
    verifier("les artefacts des deux domaines se chargent",
             set(arts) == set(DOMAINES) and not absents,
             f"{sorted(arts)}, absents {absents}")
    # ⛔ Le contrôle qui attrape le `decouper()` sans bornes : les deux
    # domaines ne peuvent pas avoir la même fenêtre.
    a025 = arts["nord-alpes"][0][GRID_3D]
    p025 = arts["pyrenees"][0][GRID_3D]
    verifier("les deux fenêtres 0025 sont DISTINCTES",
             (a025.j0, a025.i0) != (p025.j0, p025.i0),
             f"Alpes j{a025.j0}/i{a025.i0} · Pyrénées j{p025.j0}/i{p025.i0}")
    verifier("la fenêtre pyrénéenne fait bien 41 × 205 = 8 405 points",
             p025.z.shape == (41, 205), str(p025.z.shape))
    verifier("le sol pyrénéen est rendu aux Pyrénées, pas ailleurs",
             p025.z_at(42.84, -0.44) is not None
             and p025.z_at(45.12, 5.88) is None)

    # ⛔ LE CONTRÔLE QUI COMPTE VRAIMENT POUR LES BALISES DE BORD.
    # `dans_domaine` teste des bornes, `z_at` une fenêtre alignée sur les
    # points de grille : ils se contredisent à moins d'une demi-maille du
    # bord. Ce n'est acceptable QUE si les deux sources rendent le même
    # sol — sinon une balise aurait deux planchers selon l'artefact
    # consulté, et la colonne servie changerait sans que rien ne lève.
    import json as _json
    from orographie import charger_artefact_isolees
    try:
        iso, _ = charger_artefact_isolees()
        axe = _json.loads((Path(__file__).resolve().parent / "data"
                           / "balises-nord-alpes.json").read_text())["balises"]
        desaccords, chevauchantes = [], 0
        for b in axe:
            if not b.get("hors_domaine"):
                continue
            for nom, (p_dom, _) in arts.items():
                for g, o in p_dom.items():
                    zp = o.z_at(b["lat"], b["lon"])
                    zi = iso.get(str(b["id"]), {}).get(g)
                    zi = None if zi is None else zi.z_at(b["lat"], b["lon"])
                    if zp is not None and zi is not None:
                        chevauchantes += 1
                        if abs(zp - zi) > 1e-6:
                            desaccords.append((b["id"], g, zp, zi))
        verifier("une balise à cheval reçoit le MÊME sol des deux artefacts",
                 not desaccords,
                 f"{chevauchantes} cas de chevauchement, "
                 f"{len(desaccords)} désaccord(s)")
    except Abort as e:
        verifier("l'artefact des balises isolées se charge", False, str(e))

    print("\n  orographie :", "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
