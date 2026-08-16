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

from domaine import (DEMI_FENETRE_BALISE_DEG,  # noqa: E402
                     DEMI_FENETRE_VERIF_DEG, DOMAINE, GRID_3D,
                     GRID_FINE, PAQUET_OROGRAPHIE, TEMOIN_VERIF,
                     ZONES_INTERET, fenetre, fenetre_autour)
from mf_s3 import download_tmp, s3_keys, s3_objets  # noqa: E402
from orographie import (ARTEFACTS, ARTEFACT_ISOLEES_JSON,  # noqa: E402
                        ARTEFACT_ISOLEES_NPZ, ARTEFACT_JSON, ARTEFACT_NPZ,
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


def geler(nom_domaine="nord-alpes"):
    """Gèle l'orographie d'UN domaine de production.

    ⚠️ 12/08 — cette fonction ne connaissait qu'un domaine. Elle en prend
    un en argument depuis l'ajout des Pyrénées. Le défaut reste
    `nord-alpes` : tout appel existant, dans un banc ou une commande
    tapée à la main, fait donc exactement ce qu'il faisait avant, et
    produit le MÊME fichier au MÊME sha256. C'était la condition pour
    toucher à ce fichier — les archives du produit A déclarent ce sha.
    """
    import eccodes

    from domaine import DOMAINES, verifier_domaines_disjoints
    verifier_domaines_disjoints()
    if nom_domaine not in DOMAINES:
        raise Abort(f"domaine inconnu : {nom_domaine} "
                    f"(connus : {', '.join(DOMAINES)})")
    dom = DOMAINES[nom_domaine]
    npz_cible, js_cible = ARTEFACTS[nom_domaine]
    print(f"▶ domaine {nom_domaine} : {dom['latmin']}-{dom['latmax']} N × "
          f"{dom['lonmin']}-{dom['lonmax']} E → {npz_cible.name}")

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
        # ⚠️ Les bornes viennent du domaine DEMANDÉ, pas du défaut de
        # `fenetre()`. Un `decouper(..., grille)` tout court aurait
        # découpé les Alpes en croyant faire les Pyrénées : mêmes tailles
        # plausibles, même manifeste, et une orographie de Savoie sous
        # des balises ariégeoises. Rien n'aurait levé.
        orog = decouper(valeurs, meta, grille,
                        bornes=fenetre(meta, domaine=dom))
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
        nom_domaine=nom_domaine,
        domaine=dom,
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
              f"`python3 agrume/freeze_orographie.py --domaine {nom_domaine}`."))

    o_npz, o_json = ecrire_artefact(paire, manifeste, npz_cible, js_cible)
    print(f"\n▶ {npz_cible.name} : {o_npz / 1024:.0f} Ko · "
          f"{js_cible.name} : {o_json / 1024:.0f} Ko")
    return 0


def verifier(nom_domaine="nord-alpes"):
    npz_cible, js_cible = ARTEFACTS[nom_domaine]
    paire, man = charger_artefact(npz_cible, js_cible)
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


def geler_balises_isolees():
    """Le TROISIÈME artefact : une fenêtre de sol autour de chaque balise
    de l'axe qui tombe hors de TOUTE boîte de production.

    ⚠️ POURQUOI CES BALISES EXISTENT. Les boîtes sont dimensionnées par le
    budget du produit B — la grille jetable. Le produit A, lui, est
    définitif et indexé sur la grille NATIVE : la colonne d'une balise
    hors boîte ne coûte rien de plus. Seul son sol manquait. Sans ce
    fichier, 21 sites de vol pyrénéens resteraient hors de l'archive
    permanente à cause du budget d'un produit qui ne survit pas à trois
    runs.

    ⚠️ La liste vient de l'AXE FIGÉ, pas du catalogue live. Deux raisons :
    l'axe est ce que l'ingestion lit réellement, et il porte le drapeau
    `hors_domaine` posé au gel. Repartir du catalogue ferait deux
    définitions de « hors domaine » qui divergeraient le jour où une
    balise bouge.
    """
    import eccodes

    from freeze_balises import charger_artefact as charger_balises
    balises, _man = charger_balises()
    cibles = [b for b in balises if b.get("hors_domaine")]
    if not cibles:
        raise Abort("aucune balise hors domaine dans l'axe figé — rien à "
                    "geler. (Relancer `freeze_balises.py` d'abord ?)")
    ref, objets = trouver_run_complet()
    print(f"▶ run retenu : {ref} — {len(cibles)} balise(s) isolée(s), "
          f"demi-fenêtre {DEMI_FENETRE_BALISE_DEG}° "
          f"(~{DEMI_FENETRE_BALISE_DEG * 111:.0f} km)")

    par_balise = {str(b["id"]): {} for b in cibles}
    manifeste_balises = {str(b["id"]): dict(
        nom=b.get("name") or b["id"], lat=b["lat"], lon=b["lon"],
        source=b.get("source"), grilles={}) for b in cibles}

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
        for b in cibles:
            bid = str(b["id"])
            bornes = fenetre_autour(meta, b["lat"], b["lon"],
                                    DEMI_FENETRE_BALISE_DEG)
            o = decouper(valeurs, meta, grille, bornes=bornes)
            par_balise[bid][grille] = o
            z = o.z_at(b["lat"], b["lon"])
            # ⛔ Le contrôle qui compte : une fenêtre qui ne contient pas
            # SON propre point est une fenêtre calculée au mauvais
            # endroit. Elle aurait la bonne taille et le bon sha256.
            if z is None:
                raise Abort(
                    f"la fenêtre de {bid} ({b['lat']}/{b['lon']}) ne "
                    f"contient pas son propre point — bornes {bornes}")
            manifeste_balises[bid]["grilles"][grille] = dict(
                paquet=paquet, cle_s3=cle,
                meta={k: (float(meta[k]) if isinstance(meta[k], float)
                          else int(meta[k])) for k in CLES_META},
                j0=o.j0, i0=o.i0, nj=o.z.shape[0], ni=o.z.shape[1],
                sha256=_sha256(o.z), z_au_point=round(float(z), 1))

    manifeste = dict(
        produit="AGRUME — sol des balises HORS de toute boîte de production",
        ecrit_le=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        run_source=ref,
        eccodes=eccodes.codes_get_api_version(),
        demi_fenetre_deg=DEMI_FENETRE_BALISE_DEG,
        zones_interet=ZONES_INTERET,
        n=len(cibles),
        balises=manifeste_balises,
        note=("Ces balises ont un profil vertical (produit A) mais PAS de "
              "calque ni de coupe (produit B) : elles sont hors grille 3D. "
              "Régénérer avec `python3 agrume/freeze_orographie.py "
              "--balises-isolees`, APRÈS `freeze_balises.py`."))

    o_npz, o_json = ecrire_artefact_verif(par_balise, manifeste,
                                          ARTEFACT_ISOLEES_NPZ,
                                          ARTEFACT_ISOLEES_JSON)
    print(f"\n▶ {ARTEFACT_ISOLEES_NPZ.name} : {o_npz / 1024:.0f} Ko · "
          f"{ARTEFACT_ISOLEES_JSON.name} : {o_json / 1024:.0f} Ko")
    return 0


def comparer_orographie(ancien_npz, nom_domaine="nord-alpes"):
    """⛔ LE BANC QUI REMPLACE LE SHA256 LE JOUR OÙ ON ÉLARGIT UN DOMAINE.

    ⚠️ POURQUOI IL EXISTE, ET POURQUOI IL EST PLUS FORT QUE CE QU'IL
    REMPLACE. Jusqu'au 16/08, la continuité de l'orographie de production
    était garantie par un fait négatif : on n'élargissait pas `DOMAINE`,
    donc son sha256 ne bougeait pas, donc les archives se rapportaient
    toutes au même fichier. Le jour où on élargit, ce sha change
    forcément — et la question « les altitudes servies ont-elles bougé ? »
    reste entière, sans réponse.

    ⓘ Elle a pourtant une réponse mesurable. `fenetre()` s'aligne sur les
    POINTS de la grille native et `Orographie.z_at()` cherche le plus
    proche voisin : agrandir la découpe ne peut pas déplacer un point de
    grille, seulement en ajouter autour. Le sol d'une balise donnée doit
    donc être IDENTIQUE À L'OCTET avant et après. Ce banc le vérifie au
    lieu de le supposer, balise par balise, sur les deux grilles.

    ⚠️ CE QU'IL FAUT LUI DONNER : le chemin de l'ANCIEN `.npz`, mis de
    côté AVANT le regel (le `.json` est déduit du même nom). Sans copie
    préalable, il n'y a plus rien à comparer — le gel écrase en place.
    C'est délibérément à l'utilisateur de faire cette copie : un banc qui
    fabriquerait lui-même sa référence en la retéléchargeant ne prouverait
    que la reproductibilité du téléchargement.

    ⛔ UN ÉCART NON NUL N'EST PAS UN DÉTAIL À ARRONDIR. Il voudrait dire
    que le découpage ne s'aligne plus sur la grille native — donc que
    TOUTES les altitudes servies sur le domaine ont glissé d'une maille.
    Le banc échoue, et c'est le bon comportement.
    """
    from pathlib import Path

    from freeze_balises import charger_artefact as charger_balises

    anc_npz = Path(ancien_npz)
    anc_json = anc_npz.with_suffix(".json")
    if not anc_npz.exists() or not anc_json.exists():
        raise Abort(
            f"référence absente ({anc_npz.name} / {anc_json.name}). Copier "
            f"l'artefact AVANT de regeler :\n"
            f"    cp agrume/data/orographie-{nom_domaine}.npz "
            f"/tmp/ref-orographie-{nom_domaine}.npz\n"
            f"    cp agrume/data/orographie-{nom_domaine}.json "
            f"/tmp/ref-orographie-{nom_domaine}.json")

    ancien, man_a = charger_artefact(anc_npz, anc_json)
    npz_cible, js_cible = ARTEFACTS[nom_domaine]
    nouveau, man_n = charger_artefact(npz_cible, js_cible)

    print(f"▶ RÉFÉRENCE  {man_a['ecrit_le']} · {man_a['domaine']}")
    print(f"▶ ACTUEL     {man_n['ecrit_le']} · {man_n['domaine']}")
    for g in sorted(nouveau):
        print(f"  {g} : {ancien[g].z.shape} → {nouveau[g].z.shape}")

    # ⚠️ L'axe FIGÉ, pas le catalogue live : c'est la liste que
    # l'ingestion lit réellement. `--rebornage` est passé parce que le
    # code porte déjà les nouvelles bornes au moment où ce banc tourne —
    # c'est même tout l'intérêt de le lancer AVANT le regel de l'axe.
    balises, _ = charger_balises(rebornage=[nom_domaine])

    lignes, pire, communes, entrantes = [], 0.0, 0, 0
    for b in balises:
        if b.get("source") == "radiosondage":
            continue
        for g in sorted(nouveau):
            za = ancien[g].z_at(b["lat"], b["lon"])
            zn = nouveau[g].z_at(b["lat"], b["lon"])
            if za is None and zn is not None:
                entrantes += 1
                continue
            if za is None or zn is None:
                continue
            communes += 1
            e = abs(zn - za)
            if e > 0:
                lignes.append((e, b["id"], b.get("name", ""), g, za, zn))
            pire = max(pire, e)

    print(f"\n── SOL DES BALISES DE L'AXE, ANCIEN vs NOUVEAU ──")
    print(f"  {communes} couple(s) (balise × grille) portés par LES DEUX "
          f"artefacts")
    print(f"  {entrantes} couple(s) que seul le NOUVEAU porte "
          f"(élargissement — rien à comparer, c'est le gain)")
    print(f"  écart max : {pire:.3f} m")
    if lignes:
        print("\n⛔ LES ALTITUDES SERVIES ONT BOUGÉ — l'élargissement n'est "
              "PAS neutre, ne pas publier :")
        for e, i, nom, g, za, zn in sorted(lignes, reverse=True)[:20]:
            print(f"     {i:>6} · {nom[:34]:<34} {g} : "
                  f"{za:8.1f} → {zn:8.1f} m  (Δ {e:+.1f})")
        raise Abort(f"{len(lignes)} couple(s) balise × grille dont le sol a "
                    f"changé. Le découpage ne s'aligne plus sur la grille "
                    f"native — c'est un défaut, pas un arrondi.")
    if not communes:
        # ⚠️ Un banc sur zéro point rend un ✓ qui ne dit rien — la leçon
        # du TÉMOIN de `domaine.py`, exactement.
        raise Abort("aucune balise portée par les deux artefacts : ce banc "
                    "n'a rien vérifié. Vérifier que la référence est bien "
                    f"celle du domaine « {nom_domaine} ».")
    print(f"\n✅ IDENTIQUE À L'OCTET sur les {communes} couples communs. "
          f"L'élargissement n'a déplacé aucune altitude servie.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--domaine", default="nord-alpes",
                   help="domaine de production à geler ou à vérifier "
                        "(nord-alpes | pyrenees | tarn-aveyron-herault). "
                        "⚠️ Le défaut reproduit exactement le "
                        "comportement d'avant le 12/08.")
    p.add_argument("--verifier", action="store_true",
                   help="relit l'artefact existant sans rien retélécharger")
    p.add_argument("--radiosondages", action="store_true",
                   help="gèle le SECOND artefact, autour des stations de "
                        "radiosondage (la production n'est pas touchée)")
    p.add_argument("--verifier-radiosondages", action="store_true",
                   help="relit l'artefact de vérification")
    p.add_argument("--balises-isolees", action="store_true",
                   help="gèle le sol des balises de l'axe qui sont HORS de "
                        "toute boîte (à lancer APRÈS freeze_balises.py)")
    p.add_argument("--comparer-orographie", metavar="ANCIEN_NPZ", default=None,
                   help="compare, balise par balise, le sol rendu par un "
                        "artefact de RÉFÉRENCE et par l'artefact actuel. ⛔ "
                        "À lancer après tout élargissement de domaine : "
                        "c'est ce banc qui remplace le sha256 comme preuve "
                        "de continuité. Copier l'ancien .npz/.json AVANT de "
                        "regeler.")
    a = p.parse_args(argv)
    try:
        if a.comparer_orographie:
            return comparer_orographie(a.comparer_orographie, a.domaine)
        if a.balises_isolees:
            return geler_balises_isolees()
        if a.verifier_radiosondages:
            return verifier_radiosondages()
        if a.radiosondages:
            return geler_radiosondages()
        return verifier(a.domaine) if a.verifier else geler(a.domaine)
    except Abort as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
