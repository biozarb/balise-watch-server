#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/freeze_orographie.py — extraire une fois, figer, commiter
#                                                        (10/08/2026)
#
#  Le champ `h` (orographie du modèle) est STATIQUE : il ne bouge ni
#  d'une échéance à l'autre, ni d'un run à l'autre. Le retélécharger à
#  chaque run coûterait ~50 Mo pour rien ET mettrait une dépendance
#  réseau sous le SOCLE de toute la chaîne — celui dont dépend chaque
#  altitude servie à un pilote.
#
#  Ce script l'extrait donc UNE FOIS, pour les DEUX grilles, le découpe
#  au domaine Nord-Alpes et écrit un artefact versionné d'environ 150 Ko.
#  Il se relance à la main, jamais dans un run.
#
#      python3 agrume/freeze_orographie.py            # gèle
#      python3 agrume/freeze_orographie.py --verifier # relit, ne réécrit pas
#
#  ⚠️ NE PAS le câbler dans une GitHub Action. Un champ figé qui se
#  régénère tout seul n'est plus figé : il change le jour où
#  Météo-France change son maillage, silencieusement, et toutes les
#  altitudes archivées avant ce jour cessent d'être comparables à celles
#  d'après. Si le champ doit changer, ça se voit dans un diff et ça
#  s'assume dans un commit.
#
#  ⚠️ MÉNAGE. Les GRIB téléchargés (7,5 Mo en 001, 43,4 Mo en 0025) sont
#  supprimés dans un `finally`. La consigne du projet est ferme : on ne
#  laisse pas traîner de GRIB, ni sur le container, ni sur le VPS.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

from domaine import (DEMI_FENETRE_VERIF_DEG, DOMAINE, GRID_3D,  # noqa: E402
                     GRID_FINE, PAQUET_OROGRAPHIE, TEMOIN_VERIF,
                     fenetre_autour)
from mf_s3 import download_tmp, s3_keys, s3_objets  # noqa: E402
from orographie import (ARTEFACT_JSON, ARTEFACT_NPZ,  # noqa: E402
                        ARTEFACT_VERIF_JSON, ARTEFACT_VERIF_NPZ, Abort,
                        CLES_META, _sha256, accord_avec_production,
                        charger_artefact, charger_artefact_verif, decouper,
                        ecart_grilles, ecrire_artefact, ecrire_artefact_verif,
                        lire_champ_h)
from radiosondage import STATIONS  # noqa: E402


def runs_candidats(n=8):
    """Les `n` derniers runs synoptiques, du plus récent au plus ancien.

    ⚠️ Aucune heure de mise à disposition n'est codée en dur — ni ici, ni
    ailleurs dans AGRUME. La documentation Météo-France est incohérente
    avec elle-même sur ce point (5 h 05 de délai annoncé pour le run 06
    contre 3 h 30 pour le run 09) et ne dit même pas si ces heures sont
    en UTC ou en heure légale. On remonte donc jusqu'à trouver un run
    publié, ce qui est vrai quoi qu'annonce la doc.
    """
    base = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    base -= timedelta(hours=base.hour % 3)
    for back in range(n):
        yield (base - timedelta(hours=3 * back)).strftime("%Y-%m-%dT%H:00:00Z")


def trouver_run_complet():
    """Premier run qui publie l'orographie SUR LES DEUX GRILLES.

    ⚠️ Les deux ensemble, jamais l'une sans l'autre : l'hybride du
    §4.1 bis a besoin des deux, et surtout un artefact dont les deux
    moitiés viendraient de runs différents serait indétectable à la
    relecture. Les deux champs sont statiques, donc ce n'est en principe
    pas grave — mais « en principe » n'est pas une garantie qu'on peut
    écrire dans un manifeste.
    """
    for ref in runs_candidats():
        trouve = {}
        for grille in (GRID_FINE, GRID_3D):
            paquet, motif = PAQUET_OROGRAPHIE[grille]
            objets = [(k, t) for k, t in
                      s3_objets(f"pnt/{ref}/arome/{grille}/{paquet}/")
                      if motif in k]
            if objets:
                trouve[grille] = sorted(objets)[0]
        if len(trouve) == 2:
            return ref, trouve
        if trouve:
            print(f"  · {ref} : {sorted(trouve)} seulement — on remonte")
    raise Abort("aucun run ne publie l'orographie sur les deux grilles sur "
                "les 8 derniers réseaux — le miroir S3 est-il en panne ?")


def quantiles(v, qs=(0.1, 0.25, 0.5, 0.75, 0.9)):
    a = np.sort(np.asarray(v, dtype=float))
    return [float(a[min(len(a) - 1, int(q * len(a)))]) for q in qs] if len(a) else []


def geler():
    import eccodes

    ref, objets = trouver_run_complet()
    print(f"▶ run retenu : {ref} (champ statique, le run ne fait que dater "
          f"l'extraction)")

    paire, grilles_manifeste = {}, {}
    for grille in (GRID_FINE, GRID_3D):
        cle, taille = objets[grille]
        paquet, _ = PAQUET_OROGRAPHIE[grille]
        print(f"\n── grille {grille} · paquet {paquet} "
              f"({taille / 1e6:.1f} Mo) ──")
        chemin = download_tmp(cle)
        try:
            valeurs, meta = lire_champ_h(chemin)
        finally:
            os.unlink(chemin)          # ménage : jamais de GRIB qui traîne
        orog = decouper(valeurs, meta, grille)
        paire[grille] = orog
        j0, i0 = orog.j0, orog.i0
        nj, ni = orog.z.shape
        print(f"  grille native {meta['Ni']}×{meta['Nj']} @ {meta['di']}° · "
              f"origine {meta['lat0']}/{meta['lon0']}")
        print(f"  domaine       {nj}×{ni} = {nj * ni} points "
              f"(j {j0}..{j0 + nj - 1}, i {i0}..{i0 + ni - 1})")
        print(f"  altitude      min {orog.z.min():.0f} · médiane "
              f"{np.median(orog.z):.0f} · max {orog.z.max():.0f} m")
        grilles_manifeste[grille] = dict(
            paquet=paquet, cle_s3=cle, octets_source=taille,
            meta={k: (float(meta[k]) if isinstance(meta[k], float) else int(meta[k]))
                  for k in CLES_META},
            j0=j0, i0=i0, nj=nj, ni=ni,
            sha256=_sha256(orog.z),
            z_min=round(float(orog.z.min()), 1),
            z_med=round(float(np.median(orog.z)), 1),
            z_max=round(float(orog.z.max()), 1))

    # ── Ce que les deux grilles ne disent PAS pareil ──────────────────
    # Mesuré ici, sur les points de grille du domaine, et pas seulement
    # aux balises : c'est ce chiffre-là qui décide si l'artefact est
    # exploitable. S'il tombait à zéro, les deux moitiés seraient le même
    # champ — l'erreur exacte que tout ce module existe pour empêcher.
    fine = paire[GRID_FINE]
    pts = [fine.coords(j, i)
           for j in range(0, fine.z.shape[0], 3)
           for i in range(0, fine.z.shape[1], 3)]
    ecarts = ecart_grilles(paire, pts)
    absolus = [abs(e) for e in ecarts]
    q = quantiles(ecarts)
    print(f"\n── ÉCART z_0025 − z_001 sur {len(ecarts)} points du domaine ──")
    print(f"  d1 {q[0]:+.0f} · q1 {q[1]:+.0f} · MÉDIANE {q[2]:+.0f} · "
          f"q3 {q[3]:+.0f} · d9 {q[4]:+.0f} m")
    print(f"  |écart| médian {np.median(absolus):.0f} m · moyen "
          f"{np.mean(absolus):.0f} m · max {max(absolus):.0f} m")
    part100 = 100 * sum(1 for a in absolus if a > 100) / len(absolus)
    print(f"  {part100:.0f} % des points au-delà de 100 m")

    manifeste = dict(
        produit="AGRUME — orographie du modèle, figée",
        ecrit_le=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        run_source=ref,
        eccodes=eccodes.codes_get_api_version(),
        domaine=DOMAINE,
        grilles=grilles_manifeste,
        ecart_0025_moins_001=dict(
            n=len(ecarts),
            d1=round(q[0], 1), q1=round(q[1], 1), mediane=round(q[2], 1),
            q3=round(q[3], 1), d9=round(q[4], 1),
            abs_median=round(float(np.median(absolus)), 1),
            abs_max=round(float(max(absolus)), 1),
            part_au_dela_100m=round(part100, 1)),
        note=("Champ `h` (surface), STATIQUE. ⚠️ Le paquet CHANGE avec la "
              "grille : 001/SP3 mais 0025/SP2 — 0025/SP3 existe et ne "
              "contient aucune orographie. Régénérer avec "
              "`python3 agrume/freeze_orographie.py`."))

    o_npz, o_json = ecrire_artefact(paire, manifeste)
    print(f"\n▶ {ARTEFACT_NPZ.name} : {o_npz / 1024:.0f} Ko · "
          f"{ARTEFACT_JSON.name} : {o_json / 1024:.0f} Ko")
    return 0


def verifier():
    paire, man = charger_artefact()
    print(f"▶ artefact du {man['ecrit_le']}, run source {man['run_source']}, "
          f"eccodes {man['eccodes']}")
    for grille, o in sorted(paire.items()):
        print(f"  {o!r}  sha256 ✓")
    e = man["ecart_0025_moins_001"]
    print(f"  écart 0025−001 : médiane {e['mediane']:+.0f} m, "
          f"|écart| médian {e['abs_median']:.0f} m, "
          f"{e['part_au_dela_100m']:.0f} % au-delà de 100 m (n = {e['n']})")
    return 0


def geler_radiosondages():
    """Le SECOND artefact : une petite fenêtre de sol autour de chaque
    station de radiosondage active.

    ⚠️ Écrit à côté de la production, jamais à sa place. Cf. la note de
    `domaine.py` : élargir l'artefact de production aurait changé son
    sha256, donc rompu la comparabilité de toutes les archives déjà
    écrites, pour un besoin qui ne concerne que la vérification.
    """
    import eccodes

    actives = [s for s in STATIONS if s["active"]]
    if not actives:
        raise Abort("aucune station de radiosondage active")
    # ⚠️ Le témoin est découpé AVEC les stations, dans le même run et le
    # même passage : c'est ce qui rend le garde-fou non vide (cf. la note
    # de `domaine.py`). Il n'entre jamais dans l'axe des balises.
    cibles = actives + [TEMOIN_VERIF]
    ref, objets = trouver_run_complet()
    print(f"▶ run retenu : {ref} — {len(actives)} station(s) : "
          + ", ".join(f"{s['nom']} ({s['wmo']})" for s in actives)
          + f" · + 1 témoin en {TEMOIN_VERIF['lat']}/{TEMOIN_VERIF['lon']}")

    par_station = {s["wmo"]: {} for s in cibles}
    manifeste_stations = {s["wmo"]: dict(
        nom=s["nom"], pays=s["pays"], lat=s["lat"], lon=s["lon"],
        sol_station_m=s["sol_station_m"], grilles={}) for s in cibles}

    for grille in (GRID_FINE, GRID_3D):
        cle, taille = objets[grille]
        paquet, _ = PAQUET_OROGRAPHIE[grille]
        chemin = download_tmp(cle)
        try:
            valeurs, meta = lire_champ_h(chemin)
        finally:
            os.unlink(chemin)          # ménage : jamais de GRIB qui traîne
        print(f"\n── grille {grille} · paquet {paquet} "
              f"({taille / 1e6:.1f} Mo) ──")
        for s in cibles:
            bornes = fenetre_autour(meta, s["lat"], s["lon"])
            orog = decouper(valeurs, meta, grille, bornes)
            par_station[s["wmo"]][grille] = orog
            z_s = orog.z_at(s["lat"], s["lon"])
            if z_s is None:
                raise Abort(f"{s['nom']} tombe hors de sa propre fenêtre — "
                            f"la station est-elle dans la grille AROME ?")
            nj, ni = orog.z.shape
            # ⚠️ L'écart au sol RÉEL de la station est publié ici parce
            # qu'il conditionne la lecture de toute la confrontation : un
            # modèle qui place Payerne 40 m trop haut décale la colonne
            # entière avant même qu'on parle de météo.
            sol = s["sol_station_m"]
            print(f"  {s['nom']:<28} {nj}×{ni} pts · sol modèle {z_s:7.1f} m"
                  + ("" if sol is None else
                     f" · station {sol:>4} m · écart {z_s - sol:+7.1f} m"))
            manifeste_stations[s["wmo"]]["grilles"][grille] = dict(
                paquet=paquet, cle_s3=cle,
                meta={k: (float(meta[k]) if isinstance(meta[k], float)
                          else int(meta[k])) for k in CLES_META},
                j0=orog.j0, i0=orog.i0, nj=nj, ni=ni,
                sha256=_sha256(orog.z),
                z_station=round(float(z_s), 1),
                ecart_sol_station_m=(None if sol is None
                                     else round(float(z_s) - sol, 1)))

    # ── Le garde-fou des deux fenêtres ────────────────────────────────
    paire_prod, man_prod = charger_artefact()
    n_communs, pire = accord_avec_production(par_station, paire_prod)
    print(f"\n── ACCORD AVEC LA PRODUCTION : {n_communs} points communs, "
          f"écart max {pire:.4f} m ──")
    if n_communs and pire > 0.0:
        raise Abort(
            f"⚠️ les deux artefacts NE DISENT PAS LA MÊME CHOSE là où ils se "
            f"recouvrent (écart max {pire:.3f} m). Ce n'est pas une "
            f"tolérance : c'est le même champ statique lu deux fois. Les "
            f"deux artefacts viennent-ils du même run, ou un indice "
            f"est-il décalé ?")
    if not n_communs:
        print("  ⓘ aucun point commun : les fenêtres de vérification sont "
              "entièrement hors du domaine Nord-Alpes. C'est attendu pour "
              "Payerne et Cameri — le garde-fou ne peut alors rien dire, et "
              "il le dit plutôt que de rendre un ✓ vide.")

    manifeste = dict(
        produit="AGRUME — orographie sous les points de radiosondage, figée",
        ecrit_le=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        run_source=ref,
        eccodes=eccodes.codes_get_api_version(),
        demi_fenetre_deg=DEMI_FENETRE_VERIF_DEG,
        accord_production=dict(n_points_communs=n_communs,
                               ecart_max_m=round(float(pire), 4),
                               run_source_production=man_prod["run_source"]),
        stations=manifeste_stations,
        note=("⚠️ Artefact de VÉRIFICATION, pas de production. Aucune colonne "
              "servie à un pilote n'en dépend : il ne donne un sol qu'aux "
              "points marqués `source = \"radiosondage\"` dans l'axe des "
              "balises. La production (`orographie-nord-alpes.*`) n'est PAS "
              "touchée, donc son sha256 non plus. Régénérer avec "
              "`python3 agrume/freeze_orographie.py --radiosondages`."))

    o_npz, o_json = ecrire_artefact_verif(par_station, manifeste)
    print(f"\n▶ {ARTEFACT_VERIF_NPZ.name} : {o_npz / 1024:.0f} Ko · "
          f"{ARTEFACT_VERIF_JSON.name} : {o_json / 1024:.0f} Ko")
    return 0


def verifier_radiosondages():
    par_station, man = charger_artefact_verif()
    print(f"▶ artefact de vérification du {man['ecrit_le']}, run source "
          f"{man['run_source']}, demi-fenêtre {man['demi_fenetre_deg']}°")
    for wmo, entree in sorted(man["stations"].items()):
        sol = entree["sol_station_m"]
        print(f"  {entree['nom']} ({wmo})"
              + ("" if sol is None else f" — sol station {sol} m"))
        for grille, g in sorted(entree["grilles"].items()):
            ec = g["ecart_sol_station_m"]
            print(f"     {grille} : {g['nj']}×{g['ni']} pts · modèle "
                  f"{g['z_station']:7.1f} m"
                  + ("" if ec is None else f" · écart {ec:+7.1f} m")
                  + " · sha256 ✓")
    a = man["accord_production"]
    print(f"  accord production : {a['n_points_communs']} points communs, "
          f"écart max {a['ecart_max_m']} m")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--verifier", action="store_true",
                   help="relit l'artefact existant sans rien retélécharger")
    p.add_argument("--radiosondages", action="store_true",
                   help="gèle le SECOND artefact, autour des stations de "
                        "radiosondage (la production n'est pas touchée)")
    p.add_argument("--verifier-radiosondages", action="store_true",
                   help="relit l'artefact de vérification")
    a = p.parse_args(argv)
    try:
        if a.verifier_radiosondages:
            return verifier_radiosondages()
        if a.radiosondages:
            return geler_radiosondages()
        return verifier() if a.verifier else geler()
    except Abort as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
