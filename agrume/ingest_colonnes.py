#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/ingest_colonnes.py — produit A : ingestion des colonnes
#                                                        (10/08/2026)
#
#  Étape 4 de la séquence du lot H. Le socle : c'est ce fichier qui
#  transforme 7 Go de GRIB France entière en ~1 Mo de colonnes
#  verticales aux balises des Alpes du Nord, archivées indéfiniment.
#
#  ── LA CONTRAINTE MATÉRIELLE, ET C'EST LA SEULE ──────────────────────
#  ⚠️ **Le disque du runner GitHub fait 14 Go.** Un run AGRUME complet
#  tire 4,84 Go de GRIB en 0,025° (HP1 + HP2 sur 0–24 h) plus 2,4 Go en
#  0,01° pour l'hybride, et la chaîne `arome-wind` en tire déjà 4,4 —
#  **ça ne tient pas ensemble.** D'où la règle absolue de ce fichier :
#  **UN SEUL FICHIER SUR LE DISQUE À LA FOIS**, téléchargé, lu, supprimé.
#  Le pic d'occupation est journalisé à chaque run, et un critère
#  d'acceptation du lot exige qu'il reste sous 10 Go.
#
#  ✅ **La mémoire, elle, n'est pas un sujet** : pic RSS mesuré à
#  **88,0 Mo** pour digérer un fichier de 818 Mo, sur des runners qui ont
#  16 Go. On est à 0,5 %. Le pic est dominé par le décodage d'UN message
#  isolé, pas par l'accumulation — et ici on n'accumule que ~125 balises.
#
#  ── LA STRATÉGIE DE LECTURE, MESURÉE ET NON DEVINÉE ──────────────────
#  Sur un bundle réel de 818 Mo (1 225 messages), en 2 vCPU :
#      balayer les en-têtes seuls .............  1,3 s  (1 ms/message)
#      décoder u/v (336 messages) .............  7,9 s  (~21 ms/message)
#      décoder u/v PUIS découper le domaine ...  7,6 s  (la découpe est
#                                                 GRATUITE)
#      tout décoder (1 225 messages) .......... 25,0 s
#  Trois conséquences, appliquées telles quelles ici :
#    • on FILTRE sur l'en-tête (`shortName`/`level`/`step`) avant de
#      décoder — c'est quasi gratuit et ça divise le coût par 3 ;
#    • on décode France entière et on prélève ensuite : chercher à être
#      malin ne rapporterait rien de mesurable ;
#    • **le goulot est le RÉSEAU, jamais le CPU.**
#
#  ── BUDGET ───────────────────────────────────────────────────────────
#  Téléchargement à 20,9 Mo/s mesuré. Marge sous le timeout de 60 min :
#  41,2 min (run `arome-wind` : médiane 12,4, max 18,8, n = 37).
#  Le run le plus lourd prévu ici tient six fois dans cette marge — mais
#  la durée RÉELLE est mesurée et journalisée à chaque passage, avec
#  alerte au-delà de 30 min. Un budget qu'on ne mesure pas n'est pas un
#  budget.
#
#  Usage :
#      python3 agrume/ingest_colonnes.py --stations /var/lib/…/stations.json
#      python3 agrume/ingest_colonnes.py --max-heures 0 --sans-ecriture
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

from colonnes import (PARAMS_001, PARAMS_0025, Abort, Colonnes,  # noqa: E402
                      balises_du_domaine, index_plats, quantifier,
                      verifier_grille)
from domaine import GRID_3D, GRID_FINE, MAX_HOURS, MODEL_DIR  # noqa: E402
from mf_s3 import (bornes_echeances, covered_steps, download_tmp,  # noqa: E402
                   est_fichier_horaire, s3_objets)
from orographie import charger_artefact  # noqa: E402

# ⚠️ Alerte de durée : la MOITIÉ du timeout de 60 min, et six fois le
# budget mesuré. Si on l'atteint, ce n'est pas « c'était un peu long »,
# c'est que quelque chose a changé.
ALERTE_DUREE_MIN = 30
PLAFOND_DISQUE_GO = 10.0


def journal_horodate(msg):
    print(f"[{datetime.now(timezone.utc):%H:%M:%S}] {msg}", flush=True)


# ══════════════════════════════════════════════════════════════════════
#  Choix du run
# ══════════════════════════════════════════════════════════════════════
# Les quatre paquets dont le produit A a besoin. ⚠️ DEUX paquets en
# 0,025°, pas un : HP1 pour le vent et la thermo, HP2 pour la TKE (qui
# vit avec le géopotentiel). Ils pèsent presque autant l'un que l'autre.
PAQUETS = (
    (GRID_3D, "HP1"),
    (GRID_3D, "HP2"),
    (GRID_FINE, "HP1"),      # hybride : u/v à 20, 50, 100 m
    (GRID_FINE, "SP1"),      # hybride : 10u/10v à 10 m
)


def choisir_run(max_heures, profondeur=5, crier=journal_horodate):
    """Run maximisant la couverture COMMUNE aux quatre paquets.

    Même esprit que `arome-wind/ingest.py::pick_run`, et pour la même
    raison, apprise à la dure le 25/07 : prendre le run le plus récent
    dès qu'UN fichier existe donne un run éternellement incomplet, réécrit
    au run suivant, dont les échéances lointaines ne sont JAMAIS publiées.
    Ici le risque est pire, parce que l'archive est définitive : une
    colonne tronquée écrite aujourd'hui le reste pour toujours.
    """
    base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    base -= timedelta(hours=base.hour % 3)
    voulues = list(range(0, max_heures + 1))
    meilleur = None
    for k in range(profondeur):
        run = base - timedelta(hours=3 * k)
        ref = run.strftime("%Y-%m-%dT%H:00:00Z")
        commun = set(voulues)
        detail = []
        for grille, paquet in PAQUETS:
            c = covered_steps(ref, paquet, grille, voulues, model=MODEL_DIR)
            detail.append(f"{grille}/{paquet} {len(c)}")
            commun &= c
        crier(f"  run {ref} : {len(commun)}/{len(voulues)} échéances communes "
              f"({', '.join(detail)})")
        if meilleur is None or len(commun) > len(meilleur[2]):
            meilleur = (ref, run, commun)
        if len(commun) == len(voulues):
            break
    if meilleur is None or not meilleur[2]:
        raise Abort("aucun run ne publie les quatre paquets sur les 5 derniers "
                    "réseaux — rien à archiver.")
    ref, run, commun = meilleur
    crier(f"→ run retenu : {ref} ({len(commun)}/{len(voulues)} échéances)")
    return ref, run, sorted(commun)


def fichiers_du_paquet(ref, grille, paquet, steps, lister=s3_objets):
    """Fichiers à tirer, et RIEN de plus.

    ⚠️ En 0,01° les fichiers sont HORAIRES : ne tirer que les échéances
    retenues évite ~550 Mo de trafic pour rien. En 0,025° ils sont
    groupés par 6 h : on prend le bundle dès qu'il intersecte le besoin.
    """
    besoin = set(steps)
    out = []
    for cle, taille in lister(f"pnt/{ref}/{MODEL_DIR}/{grille}/{paquet}/"):
        b = bornes_echeances(cle)
        if b is None:
            continue
        debut, fin = b
        if est_fichier_horaire(cle):
            if debut in besoin:
                out.append((cle, taille))
        elif any(debut <= h <= fin for h in besoin):
            out.append((cle, taille))
    return sorted(out)


# ══════════════════════════════════════════════════════════════════════
#  Lecture d'un GRIB, message par message
# ══════════════════════════════════════════════════════════════════════
def parcourir(chemin, veut, sur_champ, steps_voulus):
    """Balaie un GRIB, ne décode QUE ce que `veut` retient.

    `veut(shortName, typeOfLevel, level) -> clé | None`
    `sur_champ(cle, step, values, meta)`

    ⚠️ L'ordre des `codes_get` compte : `step` est lu AVANT
    `codes_get_values`, parce que décoder puis jeter coûterait le double
    de temps CPU pour rien (leçon écrite dans `arome-wind/ingest.py`).

    ⚠️ Les messages dont les clés attendues manquent sont IGNORÉS, pas
    fatals — `SP3` en contient au moins un, et ça a cassé un run de
    production le 21/07.
    """
    from eccodes import (codes_get, codes_get_values,
                         codes_grib_new_from_file, codes_release)
    lus = decodes = 0
    with open(chemin, "rb") as f:
        while True:
            gid = codes_grib_new_from_file(f)
            if gid is None:
                break
            lus += 1
            try:
                cle = veut(codes_get(gid, "shortName"),
                           codes_get(gid, "typeOfLevel"),
                           codes_get(gid, "level"))
                if cle is not None:
                    step = codes_get(gid, "step")
                    if step in steps_voulus:
                        meta = dict(
                            Ni=codes_get(gid, "Ni"), Nj=codes_get(gid, "Nj"),
                            lat0=codes_get(gid, "latitudeOfFirstGridPointInDegrees"),
                            lon0=codes_get(gid, "longitudeOfFirstGridPointInDegrees"),
                            di=codes_get(gid, "iDirectionIncrementInDegrees"),
                            dj=codes_get(gid, "jDirectionIncrementInDegrees"),
                            jScan=codes_get(gid, "jScansPositively"))
                        if meta["lon0"] > 180:
                            meta["lon0"] -= 360
                        sur_champ(cle, step, codes_get_values(gid), meta)
                        decodes += 1
            except Exception as e:      # noqa: BLE001
                if isinstance(e, Abort):
                    codes_release(gid)
                    raise
                pass                    # message sans les clés attendues
            codes_release(gid)
    return lus, decodes


def filtre_0025(paquet):
    """Ce qu'on retient dans un bundle 0,025°.

    ⚠️ Le vent n'existe qu'À PARTIR DE 20 m sur les niveaux hauteur : le
    10 m vient des champs dédiés `10u`/`10v`, `typeOfLevel`
    `heightAboveGround`, niveau 10. Sans ce cas particulier, la colonne
    aurait un trou EXACTEMENT à l'altitude où la balise mesure.
    """
    voulus = {p["court"]: p for p in PARAMS_0025 if p["paquet"] == paquet}
    dix = {p["court_10m"]: p for p in PARAMS_0025
           if p["paquet"] == paquet and p["court_10m"]}

    def veut(sn, tol, lvl):
        if sn in dix and lvl == 10:
            return (dix[sn]["nom"], 10)
        p = voulus.get(sn)
        if p is None or tol != "heightAboveGround":
            return None
        from domaine import NIVEAUX_H_0025
        return (p["nom"], lvl) if lvl in NIVEAUX_H_0025 else None
    return veut


def filtre_001(paquet):
    """Ce qu'on retient en maille fine — 4 niveaux, pas un de plus.
    ⛔ Rien n'existe au-dessus de 100 m dans cette grille."""
    from domaine import NIVEAUX_H_001
    voulus = {p["court"]: p for p in PARAMS_001}
    dix = {p["court_10m"]: p for p in PARAMS_001}

    def veut(sn, tol, lvl):
        if paquet == "SP1":
            return (dix[sn]["nom"], 10) if sn in dix and lvl == 10 else None
        p = voulus.get(sn)
        if p is None or tol != "heightAboveGround":
            return None
        return (p["nom"], lvl) if lvl in NIVEAUX_H_001 and lvl != 10 else None
    return veut


# ══════════════════════════════════════════════════════════════════════
def ingerer(ref, run, steps, balises, paire_orog, crier=journal_horodate,
            limite_fichiers=None):
    col = Colonnes(ref, balises, steps)
    par_nom_0025 = {p["nom"]: p for p in PARAMS_0025}
    par_nom_001 = {p["nom"]: p for p in PARAMS_001}
    steps_set = set(steps)

    idx = {}
    for grille, orog in paire_orog.items():
        indices, hors = index_plats(orog.meta, balises)
        if hors:
            crier(f"  ⚠️ {len(hors)} balises hors grille {grille} : "
                  f"{hors[:5]}{'…' if len(hors) > 5 else ''}")
        idx[grille] = indices

    octets = pic_disque = 0
    compte = dict(fichiers=0, messages=0, decodes=0)
    t_dl = t_parse = 0.0

    for grille, paquet in PAQUETS:
        fichiers = fichiers_du_paquet(ref, grille, paquet, steps)
        if limite_fichiers:
            fichiers = fichiers[:limite_fichiers]
        total_mo = sum(t for _, t in fichiers) / 1e6
        crier(f"── {grille}/{paquet} : {len(fichiers)} fichiers, "
              f"{total_mo:.0f} Mo")
        veut = (filtre_0025(paquet) if grille == GRID_3D
                else filtre_001(paquet))
        table = par_nom_0025 if grille == GRID_3D else par_nom_001
        orog = paire_orog[grille]
        indices = idx[grille]
        valides = indices >= 0

        for cle, taille in fichiers:
            t0 = time.time()
            chemin = download_tmp(cle, journal=None)
            t_dl += time.time() - t0
            pic_disque = max(pic_disque, os.path.getsize(chemin))
            octets += os.path.getsize(chemin)
            try:
                def sur_champ(k, step, values, meta, _g=grille, _o=orog,
                              _i=indices, _v=valides, _t=table):
                    verifier_grille(_o.meta, meta, f"{_g}/{paquet}")
                    nom, niveau = k
                    brut = np.full(len(_i), np.nan)
                    brut[_v] = np.asarray(values)[_i[_v]]
                    col.poser(_g, nom, niveau, step, quantifier(brut, _t[nom]))

                t1 = time.time()
                lus, dec = parcourir(chemin, veut, sur_champ, steps_set)
                t_parse += time.time() - t1
                compte["messages"] += lus
                compte["decodes"] += dec
                compte["fichiers"] += 1
            finally:
                # ⚠️ UN SEUL FICHIER SUR LE DISQUE À LA FOIS. Le `finally`
                # n'est pas une politesse : une exception qui laisserait
                # traîner un bundle de 818 Mo remplirait le runner en
                # quelques échéances.
                os.unlink(chemin)
            crier(f"    {cle.split('/')[-1][-28:]} · {taille / 1e6:.0f} Mo · "
                  f"{dec} champs retenus sur {lus}")

    return col, dict(octets=octets, pic_disque=pic_disque, t_dl=t_dl,
                     t_parse=t_parse, **compte)


# ══════════════════════════════════════════════════════════════════════
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stations", default=os.path.join(
        os.environ.get("BW_MODEL_VERIF_ETAT", "/var/lib/bw-model-verif"),
        "stations.json"))
    p.add_argument("--suspectes", default=None,
                   help="fichier JSON [ids] des balises position_suspecte "
                        "(elles sont MARQUÉES, pas retirées)")
    p.add_argument("--max-heures", type=int, default=MAX_HOURS)
    p.add_argument("--limite-fichiers", type=int, default=None,
                   help="banc d'essai : n premiers fichiers par paquet")
    p.add_argument("--sans-ecriture", action="store_true",
                   help="ingère et chiffre, n'écrit rien sur R2")
    p.add_argument("--sortie", default=None,
                   help="dossier local où déposer npz + manifeste")
    a = p.parse_args(argv)

    t_debut = time.time()
    try:
        paire, man_orog = charger_artefact()
        journal_horodate(f"▶ orographie figée du run {man_orog['run_source']} "
                         f"({', '.join(sorted(paire))})")

        stations = json.loads(Path(a.stations).read_text(encoding="utf-8"))
        suspectes = (json.loads(Path(a.suspectes).read_text(encoding="utf-8"))
                     if a.suspectes else [])
        balises = balises_du_domaine(stations, suspectes)
        if not balises:
            raise Abort(f"aucune des {len(stations)} balises du référentiel ne "
                        f"tombe dans le domaine Nord-Alpes")
        marquees = sum(1 for b in balises if b["position_suspecte"])
        journal_horodate(f"▶ {len(balises)} balises dans le domaine "
                         f"(sur {len(stations)} au référentiel)"
                         + (f", dont {marquees} à position suspecte (marquées, "
                            f"pas retirées)" if marquees else ""))

        # Le sol du modèle sous chaque balise, écrit une fois pour toutes
        # dans le manifeste : sans lui, un niveau « 500 m » ne veut rien
        # dire, et l'écart au sol réel ne peut pas être affiché.
        for b in balises:
            for g, o in paire.items():
                z = o.z_at(b["lat"], b["lon"])
                b[f"z_{g}"] = None if z is None else round(z, 1)

        ref, run, steps = choisir_run(a.max_heures)
        col, mesures = ingerer(ref, run, steps, balises, paire,
                               limite_fichiers=a.limite_fichiers)
    except Abort as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2

    duree_min = (time.time() - t_debut) / 60
    remp = col.remplissage()
    manifeste = col.manifeste(dict(
        genere_le=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        orographie=dict(run_source=man_orog["run_source"],
                        sha256={g: man_orog["grilles"][g]["sha256"][:16]
                                for g in man_orog["grilles"]}),
        mesures=dict(
            duree_min=round(duree_min, 2),
            octets_telecharges=mesures["octets"],
            pic_disque_mo=round(mesures["pic_disque"] / 1e6, 1),
            fichiers=mesures["fichiers"],
            messages_balayes=mesures["messages"],
            messages_decodes=mesures["decodes"],
            secondes_reseau=round(mesures["t_dl"], 1),
            secondes_parsing=round(mesures["t_parse"], 1),
            debit_mo_s=round(mesures["octets"] / 1e6 / max(mesures["t_dl"], 1e-6), 1))))

    print()
    journal_horodate("┌─ BILAN DU RUN ───────────────────────────────────")
    journal_horodate(f"│ run                 : {ref}, {len(steps)} échéances")
    journal_horodate(f"│ colonnes            : {len(balises)} balises × "
                     f"{col.c0025.shape[1]}×{col.c0025.shape[2]} (0025) + "
                     f"{col.c001.shape[1]}×{col.c001.shape[2]} (001)")
    journal_horodate(f"│ remplissage         : 0025 {remp[GRID_3D] * 100:.1f} % · "
                     f"001 {remp[GRID_FINE] * 100:.1f} %")
    detail = col.remplissage_par_parametre()
    journal_horodate("│   par paramètre     : "
                     + " · ".join(f"{n} {v * 100:.0f}%"
                                  for n, v in detail[GRID_3D].items())
                     + "  |  fine " + " · ".join(
                         f"{n} {v * 100:.0f}%" for n, v in detail[GRID_FINE].items()))
    if detail[GRID_3D].get("tke", 1.0) < 1.0 and steps and steps[0] == 0:
        journal_horodate("│   ⓘ la TKE manque à l'échéance 0 — MESURÉ le "
                         "10/08, ce n'est pas un défaut d'ingestion")
    journal_horodate(f"│ téléchargé          : {mesures['octets'] / 1e9:.2f} Go "
                     f"en {mesures['t_dl'] / 60:.1f} min "
                     f"({mesures['octets'] / 1e6 / max(mesures['t_dl'], 1e-6):.1f} Mo/s)")
    journal_horodate(f"│ parsing             : {mesures['t_parse']:.0f} s pour "
                     f"{mesures['decodes']} champs décodés sur "
                     f"{mesures['messages']} balayés")
    journal_horodate(f"│ ⚠️ pic disque        : "
                     f"{mesures['pic_disque'] / 1e6:.0f} Mo "
                     f"(un fichier à la fois ; plafond du lot "
                     f"{PLAFOND_DISQUE_GO:.0f} Go)")
    journal_horodate(f"│ durée totale        : {duree_min:.1f} min "
                     f"(alerte au-delà de {ALERTE_DUREE_MIN})")
    journal_horodate("└──────────────────────────────────────────────────")
    if duree_min > ALERTE_DUREE_MIN:
        print(f"⚠️ ALERTE DURÉE : {duree_min:.1f} min > {ALERTE_DUREE_MIN} min "
              f"— la moitié du timeout GitHub. Quelque chose a changé.",
              file=sys.stderr)
    if mesures["pic_disque"] / 1e9 > PLAFOND_DISQUE_GO:
        print(f"⚠️ ALERTE DISQUE : pic à "
              f"{mesures['pic_disque'] / 1e9:.1f} Go", file=sys.stderr)

    dossier = Path(a.sortie) if a.sortie else Path(".")
    dossier.mkdir(parents=True, exist_ok=True)
    p_npz = dossier / f"agrume-colonnes-{ref.replace(':', '')}.npz"
    p_man = dossier / f"agrume-colonnes-{ref.replace(':', '')}.json"
    col.ecrire_npz(p_npz)
    p_man.write_text(json.dumps(manifeste, ensure_ascii=False, indent=1) + "\n",
                     encoding="utf-8")
    journal_horodate(f"▶ {p_npz.name} : {p_npz.stat().st_size / 1024:.0f} Ko · "
                     f"{p_man.name} : {p_man.stat().st_size / 1024:.0f} Ko")

    if a.sans_ecriture:
        journal_horodate("▶ --sans-ecriture : rien n'est monté sur R2")
        return 0

    from storage import CACHE_IMMUABLE, Storage, verifier_dimensionnement
    # ⚠️ Deux objets par run, 8 runs/jour au pire : 480 écritures par
    # mois, soit 0,05 % du palier Class A. Le vrai poste de coût d'AGRUME
    # n'est pas l'écriture, c'est l'archive qui CROÎT — chiffrée dans le
    # manifeste à chaque run pour qu'une dérive se voie au run près.
    plafond = verifier_dimensionnement(
        "agrume-colonnes", objets_par_run=2, runs_par_jour=8,
        mo_par_run=round((p_npz.stat().st_size + p_man.stat().st_size) / 1e6, 2))
    store = Storage("agrume-colonnes", "AGRUME_BUCKET", "wind-grid", plafond)
    base = f"agrume/colonnes/{ref}"
    # ⚠️ CACHE_IMMUABLE : la clé porte le run, donc l'objet n'est JAMAIS
    # réécrit en place — contrairement aux tuiles de vent. C'est le cas
    # où un TTL long est correct (et la leçon des 23-24/07 ne s'applique
    # pas ici, elle vise les clés réécrites).
    store.put(f"{base}/colonnes.npz", p_npz.read_bytes(),
              cache_control=CACHE_IMMUABLE,
              content_type="application/octet-stream")
    store.put(f"{base}/manifest.json",
              json.dumps(manifeste, ensure_ascii=False).encode(),
              cache_control=CACHE_IMMUABLE)
    store.bilan()
    return 0


if __name__ == "__main__":
    sys.exit(main())
