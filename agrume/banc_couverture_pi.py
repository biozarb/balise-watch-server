#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/banc_couverture_pi.py — BANC JETABLE (Lot M, 19/08/2026)
#
#  ⛔ CE FICHIER N'EST PAS UN PRODUIT. Il répond à UNE question, la
#  moins chère et la plus bloquante du Lot M : **le portail sert-il
#  vraiment des données AROME-PI sur les boîtes Pyrénées et
#  Tarn/Aveyron/Hérault ?** Rien dans le projet ne le confirme. Le nom
#  de la couverture porte « FRANCE » et la géométrie mesurée le 10/08
#  était celle d'AROME 0025 national — de bonnes raisons de penser que
#  oui, mais c'est une INFÉRENCE.
#
#  Il mesure aussi, pour chaque boîte :
#    · la taille du GRIB rendu (le seul levier de payload du portail) ;
#    · la géométrie rendue, et si `aligner_sur_axes()` accepte la
#      fenêtre CONTRE L'OROGRAPHIE GELÉE DE CE DOMAINE — le piège du
#      10/08 (une colonne d'écart) est propre à CHAQUE boîte ;
#    · la part de valeurs finies (un 200 avec un champ tout-NaN serait
#      un faux positif) ;
#    · la durée par requête, hors attente de quota.
#
#  ⚠️ Coût : 3 niveaux × 3 échéances × 1 paramètre × N domaines.
#  9 requêtes par domaine, 27 pour les trois. À comparer aux 300 d'un
#  run. On ne mesure pas le quota ici — on mesure la COUVERTURE.
#
#  Usage (SUR LE VPS, la clé n'en sort pas) :
#      python3 agrume/banc_couverture_pi.py --run 2026-08-19T10:00:00Z
#      python3 agrume/banc_couverture_pi.py            # cherche un run
# ══════════════════════════════════════════════════════════════════════
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from domaine import DOMAINES  # noqa: E402
from grille import axes_depuis_orographie  # noqa: E402
from orographie import charger_artefacts  # noqa: E402
from pi import (Abort, NIVEAUX_PI, aligner_sur_axes,  # noqa: E402
                instants_du_run, params_actifs)
from ingest_pi import lire_grib_2d  # noqa: E402
from portail import (SERVICE_AROMEPI, CouvertureAbsente,  # noqa: E402
                     ErreurPortail, Portail)

NIVEAUX_SONDE = (10, 100, 500)
ECHEANCES_SONDE = (0, 180, 360)

# ⛔⛔ MESURÉ LE 19/08 — ET C'EST LE SEUL VRAI OBSTACLE DU LOT M.
# Le WCS rend les points STRICTEMENT DANS la boîte demandée. Quand les
# bornes du domaine tombent sur la grille 0,025° (nord-alpes : 43,70 /
# 46,45 / 5,00 / 7,60 ; pyrenees : 42,40 / 43,40 / −1,80 / 3,30), la
# fenêtre rendue coïncide au point près avec celle de l'orographie.
# Quand elles n'y tombent PAS — `DOMAINE_TAH` = 43,43 / 44,26 / 1,88 /
# 3,96, dont AUCUNE des quatre n'est un multiple de 0,025 — `fenetre()`
# arrondit vers le point le PLUS PROCHE (donc parfois vers l'EXTÉRIEUR)
# tandis que le WCS coupe vers l'INTÉRIEUR. Mesuré : 33 × 83 rendus
# contre 34 × 84 attendus, `aligner_sur_axes()` REFUSE, écart 0,025001°.
#
# ⚠️ La réponse N'EST PAS d'élargir la tolérance d'alignement — c'est
# écrit dans le message d'erreur de `pi.py` et ça reste vrai. C'est de
# DEMANDER PLUS LARGE et de laisser `aligner_sur_axes()` recouper : une
# marge d'un pas de grille suffit, elle ne déplace aucun point servi, et
# elle ne coûte que les quelques octets du liseré.
MARGE_DEG_DEFAUT = 0.03


def boite_elargie(boite, marge):
    """La boîte à DEMANDER au portail. ⚠️ Pas celle qu'on sert."""
    if not marge:
        return dict(boite)
    return dict(latmin=boite["latmin"] - marge, latmax=boite["latmax"] + marge,
                lonmin=boite["lonmin"] - marge, lonmax=boite["lonmax"] + marge)


def crier(m=""):
    print(m, flush=True)


def dernier_run_publie(portail, champ, recul_max=8):
    """Un run COMPLET, sans toucher à l'index R2 (on ne veut rien écrire).

    ⚠️ La complétude se sonde sur la DERNIÈRE échéance — PI publie au fil
    de l'eau (mesuré le 10/08). Sonder sur l'échéance 0 rendrait « publié »
    un run à 24 %.
    """
    t = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0,
                                                 microsecond=0)
    dernier_instant = None
    for recul in range(recul_max):
        run = (t - dt.timedelta(hours=recul)).strftime("%Y-%m-%dT%H:00:00Z")
        if not portail.existe(champ, run):
            continue
        dernier = instants_du_run(run)[-1]
        try:
            portail.get_coverage(champ, run, dernier, 100,
                                 DOMAINES["nord-alpes"])
        except (ErreurPortail, CouvertureAbsente):
            crier(f"  ⏳ {run} publié mais INCOMPLET — on recule.")
            continue
        return run
    raise Abort("aucun run PI complet dans les 8 dernières heures")


def sonder(portail, champ, run, nom, boite, orog3d, marge=0.0,
           journal=crier):
    """Une boîte, 9 champs. Renvoie un dict de MESURES, pas un verdict."""
    lats, lons = axes_depuis_orographie(orog3d, domaine=boite)
    demandee = boite_elargie(boite, marge)
    journal(f"\n── {nom} — boîte lat {boite['latmin']}→{boite['latmax']} · "
            f"long {boite['lonmin']}→{boite['lonmax']}"
            + (f" · DEMANDÉE avec marge {marge}°" if marge else ""))
    journal(f"   orographie gelée : {len(lats)} × {len(lons)} = "
            f"{len(lats) * len(lons)} points")
    instants = instants_du_run(run)
    res = dict(domaine=nom, boite=boite, demandee=demandee, marge=marge,
               cible=[len(lats), len(lons)], champs=[], erreurs=[],
               alignement=None)
    axe = portail.axe_vertical(champ, run)
    for niveau in NIVEAUX_SONDE:
        for minute in ECHEANCES_SONDE:
            k = list(range(0, 361, 15)).index(minute)
            t0 = time.monotonic()
            try:
                octets = portail.get_coverage(champ, run, instants[k], niveau,
                                              demandee, axe=axe)
            except (ErreurPortail, CouvertureAbsente) as e:
                res["erreurs"].append(dict(niveau=niveau, minute=minute,
                                           cause=f"{type(e).__name__}: {e}"[:220]))
                journal(f"   ⛔ {niveau:>4} m · +{minute:>3} min : "
                        f"{type(e).__name__} — {e}"[:180])
                continue
            dt_s = time.monotonic() - t0
            try:
                champ2d, meta = lire_grib_2d(octets)
            except Abort as e:
                res["erreurs"].append(dict(niveau=niveau, minute=minute,
                                           cause=f"GRIB illisible: {e}"[:220]))
                journal(f"   ⛔ {niveau:>4} m · +{minute:>3} min : GRIB "
                        f"illisible — {e}")
                continue
            fini = float(np.isfinite(champ2d).mean())
            mesure = dict(niveau=niveau, minute=minute, octets=len(octets),
                          forme=[int(meta["Nj"]), int(meta["Ni"])],
                          lat0=round(float(meta["lat0"]), 5),
                          lon0=round(float(meta["lon0"]), 5),
                          di=float(meta["di"]), dj=float(meta["dj"]),
                          part_finie=round(fini, 4),
                          mini=round(float(np.nanmin(champ2d)), 3),
                          maxi=round(float(np.nanmax(champ2d)), 3),
                          ecart_type=round(float(np.nanstd(champ2d)), 3),
                          secondes=round(dt_s, 3))
            res["champs"].append(mesure)
            journal(f"   ✅ {niveau:>4} m · +{minute:>3} min : "
                    f"{len(octets):>7} o · {meta['Nj']}×{meta['Ni']} · "
                    f"fini {fini * 100:.1f}% · "
                    f"[{mesure['mini']:+.1f}, {mesure['maxi']:+.1f}] m/s · "
                    f"σ {mesure['ecart_type']:.2f} · {dt_s:.2f} s")
            if res["alignement"] is None:
                # ⚠️⚠️ LE CONTRÔLE QUI COMPTE VRAIMENT. Un 200 avec du
                # vent plausible ne dit RIEN sur le fait que la fenêtre
                # rendue par le WCS recouvre l'axe de l'orographie de CE
                # domaine. Le piège du 10/08 (61×85 contre 61×84, une
                # égalité en virgule flottante à la borne) est par
                # construction PROPRE À CHAQUE BOÎTE.
                try:
                    a = aligner_sur_axes(champ2d, meta, lats, lons)
                    res["alignement"] = dict(ok=True, forme=list(a.shape),
                                             attendu=[len(lats), len(lons)])
                    journal(f"   ✅ aligner_sur_axes : {a.shape} "
                            f"(attendu {(len(lats), len(lons))})")
                except Abort as e:
                    res["alignement"] = dict(ok=False, cause=str(e)[:400])
                    journal(f"   ⛔⛔ aligner_sur_axes REFUSE : {e}")
    return res


def charger(portail, champ, run, noms, arts, marge, journal=crier):
    """⛔ LA MESURE QUI REMPLACE L'EXTRAPOLATION : un run PI COMPLET sur
    N domaines, dans UN SEUL processus — donc avec la MÊME fenêtre de
    quota que la production, qui est mono-processus elle aussi.

    2 paramètres × 6 niveaux × 25 échéances × N domaines. Rien n'est
    écrit. On chronomètre, on compte les requêtes RÉELLEMENT consommées
    (les 502 retentés en ajoutent), et on regarde si le portail change
    de comportement à 900 requêtes — 429, coupure de connexion, ou rien.
    """
    from domaine import GRID_3D
    params = params_actifs(False)
    instants = instants_du_run(run)
    axes = {p["nom"]: portail.axe_vertical(p["wcs"], run) for p in params}
    cibles = {}
    for nom in noms:
        paire, _ = arts[nom]
        cibles[nom] = axes_depuis_orographie(paire[GRID_3D],
                                             domaine=DOMAINES[nom])
    t_global = time.monotonic()
    par_domaine = []
    for nom in noms:
        lats, lons = cibles[nom]
        demandee = boite_elargie(DOMAINES[nom], marge)
        t0 = time.monotonic()
        avant = dict(portail.compteur)
        faits, rates, refus = 0, [], 0
        for p in params:
            for niveau in NIVEAUX_PI:
                for k, minute in enumerate(range(0, 361, 15)):
                    try:
                        octets = portail.get_coverage(
                            p["wcs"], run, instants[k], niveau, demandee,
                            axe=axes[p["nom"]])
                        champ2d, meta = lire_grib_2d(octets)
                        aligner_sur_axes(champ2d, meta, lats, lons)
                        faits += 1
                    except Abort as e:
                        refus += 1
                        if refus <= 2:
                            journal(f"   ⛔ alignement/GRIB : {e}"[:200])
                    except (ErreurPortail, CouvertureAbsente) as e:
                        rates.append(dict(param=p["nom"], niveau=niveau,
                                          minute=minute,
                                          cause=f"{type(e).__name__}: {e}"[:180]))
                journal(f"   {nom} · {p['nom']} · {niveau:>4} m : "
                        f"{faits} ok ({time.monotonic() - t0:.0f} s)")
        d = time.monotonic() - t0
        delta = {k: portail.compteur[k] - avant.get(k, 0)
                 for k in portail.compteur}
        par_domaine.append(dict(domaine=nom, secondes=round(d, 1),
                                champs_ok=faits, refus_alignement=refus,
                                echecs=len(rates), detail_echecs=rates[:10],
                                compteur=delta))
        journal(f"  ── {nom} : {faits}/300 champs en {d / 60:.2f} min · "
                f"{delta.get('requetes', 0)} requêtes · "
                f"{delta.get('http_429', 0)} × 429 · "
                f"{sum(delta.get(f'http_{c}_retente', 0) for c in (502, 503, 504))}"
                f" × 5xx retentés · {delta.get('reseau', 0)} incidents réseau "
                f"· {delta.get('attente_quota', 0)} attentes de quota")
    total = time.monotonic() - t_global
    journal(f"\n  ⏱️  {len(noms)} domaines · {total / 60:.2f} min au total")
    return dict(secondes_total=round(total, 1), domaines=par_domaine)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", default=None)
    p.add_argument("--domaines", default=None,
                   help="liste séparée par des virgules (défaut : tous)")
    p.add_argument("--json", default=None, help="où écrire les mesures")
    p.add_argument("--marge-deg", type=float, default=0.0,
                   help="élargir la boîte DEMANDÉE au portail (l'alignement "
                        "recoupe) — 0.03 corrige le refus mesuré sur TAH")
    p.add_argument("--charge", action="store_true",
                   help="⚠️ 300 requêtes PAR DOMAINE : la mesure de durée "
                        "et de quota, pas la sonde de couverture")
    a = p.parse_args(argv)

    noms = ([x.strip() for x in a.domaines.split(",")] if a.domaines
            else list(DOMAINES))
    params = params_actifs(False)
    champ = params[0]["wcs"]

    portail = Portail(SERVICE_AROMEPI, "0025",
                      journal=lambda m: crier(f"   {m}"))
    crier("BANC COUVERTURE PI — Lot M · jetable")
    hier = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    temoins = [(hier + dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:00:00Z")
               for h in (0, 1, 2)]
    portail.valider_champ(champ, temoins)
    crier(f"  ✅ champ validé : {champ}")

    run = a.run or dernier_run_publie(portail, champ)
    crier(f"  run : {run}")

    # ⚠️ `charger_artefacts` rend un COUPLE (dict, absents), pas un dict.
    arts, manquants = charger_artefacts(noms, obligatoires=())
    if manquants:
        crier(f"  ⚠️ orographie ABSENTE pour : {manquants} — ces domaines "
              f"sont sondés sans contrôle d'alignement")

    from domaine import GRID_3D
    if a.charge:
        vivants = [n for n in noms if n in arts]
        marge = a.marge_deg if a.marge_deg else MARGE_DEG_DEFAUT
        crier(f"\n⚠️  MODE CHARGE — {len(vivants)} × 300 = "
              f"{len(vivants) * 300} requêtes, marge {marge}°")
        charge = charger(portail, champ, run, vivants, arts, marge)
        crier(f"\n══ BILAN ══\n  {portail.bilan()}")
        crier(f"  octets reçus : {portail.compteur['octets'] / 1e6:.3f} Mo")
        if a.json:
            with open(a.json, "w", encoding="utf-8") as f:
                json.dump(dict(run=run, charge=charge,
                               compteur=dict(portail.compteur)), f,
                          ensure_ascii=False, indent=1)
            crier(f"  mesures écrites dans {a.json}")
        return 0

    sorties = []
    for nom in noms:
        if nom not in arts:
            continue
        paire, _man = arts[nom]
        sorties.append(sonder(portail, champ, run, nom, DOMAINES[nom],
                              paire[GRID_3D], marge=a.marge_deg))

    crier("\n══ BILAN ══")
    crier(f"  {portail.bilan()}")
    crier(f"  octets reçus : {portail.compteur['octets'] / 1e6:.3f} Mo")
    for s in sorties:
        n_ok = len(s["champs"])
        moy = (sum(c["octets"] for c in s["champs"]) / n_ok) if n_ok else 0
        al = s["alignement"]
        crier(f"  {s['domaine']:>22} : {n_ok}/9 champs · "
              f"{moy:.0f} o/champ en moyenne · cible {s['cible'][0]}×"
              f"{s['cible'][1]} · alignement "
              f"{'OK' if al and al.get('ok') else 'REFUSÉ' if al else 'non testé'}"
              + (f" · {len(s['erreurs'])} erreurs" if s["erreurs"] else ""))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(dict(run=run, mesures=sorties,
                           compteur=dict(portail.compteur)), f,
                      ensure_ascii=False, indent=1)
        crier(f"  mesures écrites dans {a.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
