#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/ingest_pi_rafale.py — un run de rafale AROME-PI, du portail
#                               à R2                       (09/09/2026)
#                               Lot « cellule qui approche », lot 2
#
#  ⛔ CE QU'IL FAIT, ET RIEN D'AUTRE. Il détecte le run publié le plus
#  frais et COMPLET, tire ses 24 échéances sur la boîte PIAF, vérifie la
#  géométrie et les unités de CHACUNE, réduit en 0,02° par maximum et
#  écrit deux objets sur R2. Il ne pousse rien, il n'évalue aucun seuil,
#  il ne parle à aucun utilisateur : tout cela vit dans
#  `lib/rafale-pi.js` et dans `index.js`.
#
#  ── LES TROIS PIÈGES QUI ONT COÛTÉ UNE HEURE LE 09/09 ────────────────
#  1. ⛔ Le compteur d'échéances de PIAF rend **1** ici, sur un run
#     parfaitement complet — il prend le premier `coefficients` non vide
#     et tombe sur l'axe `height`. Sans `coefficients_temps`, cette
#     chaîne dirait « aucun run complet » pour toujours, et le voyant
#     resterait vert (code 3 = « rien à faire » !) pendant qu'elle
#     n'écrirait plus rien. ⚠️ C'est le pire des défauts possibles pour
#     ce projet : un silence qui ressemble à un calme.
#  2. ⛔ `agregation="PT15M"` est obligatoire DÈS `valider_champ`. Sans
#     lui, le champ « n'existe sur aucun run témoin » — et le message
#     accuse le nom du champ, qui est correct.
#  3. ⛔ `axe="height"` en dur à chaque `get_coverage`. Sinon
#     `Portail.axe_vertical()` part sur un identifiant sans suffixe et
#     ramène le même 404 que le piège nº 2.
#
#  ── CODES DE SORTIE ──────────────────────────────────────────────────
#      0  un run a été ingéré ET écrit             → ping vert
#      3  rien à faire (déjà ingéré, ou pas encore
#         publié — le cas NOMINAL 5 fois sur 6)    → AUCUN ping
#      autre  échec                                → ping rouge
#
#  ⚠️ Le producteur ne sort qu'un run par heure et la chaîne passe
#  toutes les 10 min : cinq passages sur six sortent en 3. Le service
#  systemd DOIT porter `SuccessExitStatus=3`, sinon il est rouge en
#  permanence — la faute que `bw-agrume-ingest-pi.service` a déjà
#  corrigée une fois.
#
#  Usage :  python3 agrume/ingest_pi_rafale.py
#           python3 agrume/ingest_pi_rafale.py --run 2026-09-09T15:00:00Z
#           python3 agrume/ingest_pi_rafale.py --sans-ecriture --limite-echeances 3
#           python3 agrume/ingest_pi_rafale.py --verifier
# ══════════════════════════════════════════════════════════════════════
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

import pi_rafale  # noqa: E402
from pi_rafale import (AGREGATION, AXE_VERTICAL, BOITE,  # noqa: E402
                       CHAMP_WCS, CLE_INDEX, GRILLE, NB_ECHEANCES,
                       NIVEAU_M, Abort, Run, axes_boite, cles_du_run,
                       echeances, run_en_ligne, runs_candidats,
                       verifier_alignement)
from portail import (SERVICE_AROMEPI, CouvertureAbsente,  # noqa: E402
                     ErreurPortail, Portail)

CODE_RIEN_A_FAIRE = 3
#: Budget mesuré le 09/09 : 24 échéances × 5,9 s ≈ 141 s. Au-delà de
#: 300 s ce n'est plus « un peu long » : c'est que le portail rame ou que
#: le quota est partagé avec `ingest_pi` / `ingest_piaf`, dont les
#: compteurs sont PAR PROCESSUS et ne se voient pas les uns les autres.
ALERTE_SECONDES = 300


def crier(msg=""):
    print(msg, flush=True)


# ══════════════════════════════════════════════════════════════════════
#  DÉTECTION DU RUN
# ══════════════════════════════════════════════════════════════════════
def coefficients_temps(arbre):
    """Les coefficients de l'axe `time`, ET DE LUI SEUL.

    ⛔⛔ LE PIÈGE Nº 1, ET IL ÉCHOUE EN SILENCE.
    `ingest_piaf.nb_echeances_publiees` prend le PREMIER `coefficients`
    non vide de la réponse. Chez PIAF le champ est de SURFACE : les axes
    `long` et `lat` sont réguliers (coefficients vides) et le premier
    non-vide est donc bien le temps. Ici le champ porte un axe `height`,
    dont le coefficient vaut `10` — un seul nombre. La recette de PIAF
    rend donc **1 échéance** sur un run qui en publie 24.

    ⚠️ Mesuré le 09/09 à 16:07 Z : huit runs d'affilée annoncés
    « partiel (1) » alors que le 15:00 Z était complet depuis une heure.
    Et comme « pas de run complet » sort en code 3, le voyant serait
    resté VERT sur une chaîne qui n'écrit plus rien.

    On lit donc `gridAxesSpanned` et on ne garde que `time`.
    """
    for ax in arbre.iter():
        if not ax.tag.endswith("GeneralGridAxis"):
            continue
        spanned = coeffs = None
        for el in ax.iter():
            if el.tag.endswith("gridAxesSpanned"):
                spanned = (el.text or "").strip()
            elif el.tag.endswith("coefficients"):
                coeffs = (el.text or "").strip()
        if spanned == "time" and coeffs:
            return [int(x) for x in coeffs.split()]
    return []


def verifier_coefficients(coeffs, run):
    """⛔ Les coefficients ATTENDUS, pas seulement leur nombre.

    Compter 24 ne suffit pas : 24 coefficients espacés de 20 min
    décriraient un ruban de 8 h publié sous le même nom, et chaque
    requête réussirait. On vérifie donc la SUITE : 900, 1 800, … 21 600 s.
    """
    attendus = [60 * pi_rafale.PAS_MIN * k
                for k in range(1, NB_ECHEANCES + 1)]
    if coeffs != attendus:
        raise Abort(
            f"le run {run} publie {len(coeffs)} coefficients temporels "
            f"{coeffs[:3]}…{coeffs[-1:]} au lieu des {len(attendus)} "
            f"attendus {attendus[:3]}…{attendus[-1:]}. ⛔ Le producteur a "
            f"changé de pas ou d'horizon : ingérer quand même publierait "
            f"un ruban dont chaque valeur est juste et dont l'axe du "
            f"temps est faux.")
    return True


def dernier_run(portail, deja=(), maintenant=None, journal=crier):
    """Le run publié le plus frais, COMPLET et pas encore ingéré.

    Renvoie `(run, latence_min)` ou `(None, None)`.

    ⚠️ On interroge par `DescribeCoverage` (~5 ko) et non par
    `GetCapabilities` (3,27 Mo pour 10 288 identifiants) — un facteur 575
    pour une information qui tient dans quelques centaines d'octets.
    """
    t = maintenant or dt.datetime.now(dt.timezone.utc)
    for run in runs_candidats(maintenant=t):
        if run in deja:
            # ⛔ On S'ARRÊTE à la première déjà connue : les candidates
            # sont ordonnées de la plus fraîche à la plus ancienne, donc
            # tout ce qui suit est plus vieux encore.
            journal(f"  run {run} déjà en ligne — rien à faire")
            return None, None
        try:
            arbre = portail.describe(CHAMP_WCS, run, agregation=AGREGATION)
        except CouvertureAbsente:
            continue
        coeffs = coefficients_temps(arbre)
        if len(coeffs) != NB_ECHEANCES:
            journal(f"  ⚠️ {run} est publié mais annonce {len(coeffs)} "
                    f"échéances au lieu de {NB_ECHEANCES} — passé")
            continue
        verifier_coefficients(coeffs, run)
        latence = (t - pi_rafale._instant(run)).total_seconds() / 60.0
        return run, round(latence, 1)
    return None, None


# ══════════════════════════════════════════════════════════════════════
#  LE TIRAGE
# ══════════════════════════════════════════════════════════════════════
def verifier_geometrie(h, lats, lons, quoi):
    """⛔⛔ LE GARDE-FOU LE PLUS IMPORTANT DU MODULE.

    Le WCS découpe SA fenêtre à partir de la boîte qu'on lui donne. Rien
    ne garantit qu'elle coïncide avec celle qu'on attend — et le 10/08,
    sur AROME-PI, elles différaient déjà d'une colonne (61 × 85 contre
    61 × 84), née d'une égalité en virgule flottante à une borne. Une
    colonne, c'est 1,11 km de décalage sur TOUT le domaine : la rafale
    serait annoncée au mauvais endroit, d'un kilomètre, partout, et
    aucune requête n'échouerait.

    ⚠️ TOLÉRANCE 1e-4, ET ON NE L'ÉLARGIT PAS. Si un écart réel
    apparaît, c'est la BOÎTE qu'on ajuste — élargir la tolérance ne fait
    que rendre le décalage acceptable, pas juste.

    ⚠️ `norm` est redéfini ici : le GRIB écrit les longitudes en 0-360
    (354,79 pour −5,21).
    """
    import eccodes as ec                                   # noqa: PLC0415

    def norm(x):
        return x - 360.0 if x > 180.0 else x

    lu = dict(
        Nj=ec.codes_get(h, "Nj"), Ni=ec.codes_get(h, "Ni"),
        lat_premier=ec.codes_get(h, "latitudeOfFirstGridPointInDegrees"),
        lon_premier=norm(ec.codes_get(
            h, "longitudeOfFirstGridPointInDegrees")),
        pas_lat=ec.codes_get(h, "jDirectionIncrementInDegrees"),
        pas_lon=ec.codes_get(h, "iDirectionIncrementInDegrees"))
    attendu = dict(
        Nj=len(lats), Ni=len(lons),
        lat_premier=float(lats[0]), lon_premier=float(lons[0]),
        pas_lat=pi_rafale.PAS_DEG, pas_lon=pi_rafale.PAS_DEG)
    for cle, att in attendu.items():
        if abs(lu[cle] - att) > 1e-4:
            raise Abort(
                f"{quoi} : le portail a servi {cle} = {lu[cle]} au lieu de "
                f"{att}. ⛔ La fenêtre reçue n'est pas celle attendue — "
                f"publier ces octets mettrait la rafale au mauvais endroit "
                f"sur toute la carte, sans qu'aucune requête n'échoue. "
                f"⚠️ Ajuster la BOÎTE, jamais la tolérance.")

    # ── Ce que la DONNÉE dit d'elle-même ─────────────────────────────
    unites = ec.codes_get(h, "units")
    if unites != "m s**-1":
        raise Abort(
            f"{quoi} : `units = {unites!r}` au lieu de 'm s**-1'. ⛔ Le "
            f"lot 2 publie des MÈTRES PAR SECONDE et le lecteur multiplie "
            f"par 3,6 ; un champ déjà en km/h passerait à 144 km/h là où "
            f"il y en a 40.")
    pas_de_temps = ec.codes_get(h, "stepType")
    if pas_de_temps != "max":
        raise Abort(
            f"{quoi} : `stepType = {pas_de_temps!r}` au lieu de 'max'. ⛔ "
            f"Un `instant` ou une `avg` servis sous ce nom donneraient une "
            f"nappe lisse et systématiquement TROP BASSE — c'est-à-dire un "
            f"produit qui rassure alors qu'il devrait alerter.")
    niveau = ec.codes_get(h, "level")
    if int(niveau) != NIVEAU_M:
        raise Abort(
            f"{quoi} : `level = {niveau}` au lieu de {NIVEAU_M} m. ⛔ La "
            f"rafale à 100 m vaut couramment le double de celle à 10 m.")
    return True


def tirer(portail, run, boite=None, journal=crier, limite=None):
    """Les 24 échéances, une requête chacune, au pas natif 0,01°.

    ⚠️ SÉQUENTIEL, jamais en parallèle. Mesuré le 10/08 sur ce portail :
    à forte concurrence il COUPE la connexion (102 `ConnectionResetError`
    + 502 sur 200 requêtes) au lieu de répondre 429.
    """
    import eccodes as ec                                   # noqa: PLC0415
    b = dict(boite or BOITE)
    lats, lons = axes_boite(b)
    n = NB_ECHEANCES if limite is None else min(limite, NB_ECHEANCES)
    natif = np.full((NB_ECHEANCES, len(lats), len(lons)), np.nan,
                    dtype=np.float32)
    t0 = time.perf_counter()
    for e in echeances(run)[:n]:
        octets = portail.get_coverage(
            CHAMP_WCS, run, e["instant_demande"], NIVEAU_M, b,
            axe=AXE_VERTICAL, agregation=AGREGATION)
        h = ec.codes_new_from_message(octets)
        try:
            verifier_geometrie(h, lats, lons, f"échéance +{e['fin_min']} min")
            natif[e["rang"]] = np.asarray(
                ec.codes_get_values(h), dtype=np.float32).reshape(
                    len(lats), len(lons))
        finally:
            ec.codes_release(h)
        if (e["rang"] + 1) % 6 == 0 or e["rang"] + 1 == n:
            journal(f"     {e['rang'] + 1:2d}/{n} échéances "
                    f"({time.perf_counter() - t0:.0f} s)")
    return natif, lats, lons


# ══════════════════════════════════════════════════════════════════════
#  LA RELECTURE — ce qui est SERVI, pas ce qui est en mémoire
# ══════════════════════════════════════════════════════════════════════
def verifier_en_ligne(st, journal=crier):
    """Relit l'index, le manifeste et les octets TELS QUE SERVIS.

    ⛔ Il n'y a pas de coupe à confronter au calque ici (le lot 2 ne
    publie qu'un jeu). On confronte donc le calque à ce que le MANIFESTE
    dit du champ natif, par deux invariants EXACTS de la réduction par
    maximum — pas par une ressemblance :

      1. `max(calque) == max(natif)`. Un maximum de blocs qui partitionne
         la grille conserve le maximum global, à l'octet près. Toute
         différence signale une réduction qui n'est plus un maximum (une
         moyenne, une décimation) ou un `reshape` transposé.
      2. `n_calque ≤ n_natif ≤ 4 × n_calque`, où `n` compte les mailles
         au-dessus du seuil. Un bloc est retenu dès qu'UN de ses quatre
         points l'est ; il ne peut donc ni en perdre, ni en inventer plus
         de quatre.

    ⚠️ Ces deux contrôles se lisent sur les octets SERVIS, pas sur ceux
    de la mémoire — c'est la leçon du Lot L3b, et c'est la seule façon
    d'attraper une écriture tronquée qui rend quand même un tableau
    parfaitement décodable.
    """
    run = run_en_ligne(st)
    if not run:
        journal(f"⛔ aucun run LISIBLE — `dernier` est vide dans {CLE_INDEX}")
        return 1
    cles = cles_du_run(run)
    man = st.get_json(cles[-1])
    if not man:
        journal(f"⛔ manifeste absent : {cles[-1]}")
        return 1
    if man.get("run") != run:
        journal(f"⛔ le manifeste servi sous {cles[-1]} porte "
                f"run={man.get('run')!r} : des objets d'un AUTRE run.")
        return 1
    age = (dt.datetime.now(dt.timezone.utc)
           - pi_rafale._instant(run)).total_seconds() / 60.0
    journal(f"✅ run lisible : {run} · âge {age:.1f} min · "
            f"latence de publication "
            f"{man['source']['latence_publication_min']} min")
    journal(f"   {man['octets_publies'] / 1e6:.1f} Mo publiés · "
            f"mesures {man['mesures']}")
    creux = [i for i, r in enumerate(man["remplissage_par_echeance"])
             if r < 1.0]
    journal(f"   remplissage : "
            + (f"plein sur les {NB_ECHEANCES} tranches" if not creux
               else f"CREUX aux rangs {creux}"))

    cal = man["service"]["calque"]
    attendu = cal["octets_par_echeance"] * NB_ECHEANCES
    octets = st.get(cal["cle"])
    if octets is None:
        journal(f"   ⛔ {cal['cle']} : absent alors que l'index le nomme.")
        return 1
    if len(octets) != attendu:
        journal(f"   ⛔ {cal['cle']} : {len(octets)} octets servis au lieu "
                f"de {attendu}. ⚠️ Un fichier tronqué se décode QUAND MÊME "
                f"— numpy lirait simplement moins d'échéances.")
        return 1
    a = np.frombuffer(octets, dtype=pi_rafale.DTYPE).astype(np.float32)
    fini = np.isfinite(a)
    if not fini.any():
        journal("   ⛔ calque entièrement NaN — un champ mort, pas un "
                "jour sans vent.")
        return 1
    seuil = man["mesures"]["seuil_part_ventee_ms"]
    n_calque = int(np.count_nonzero(np.where(fini, a, 0.0) >= seuil))
    n_natif = round(man["mesures"]["part_ventee"]
                    * man["mesures"]["renseignees"]
                    * man["mesures"]["mailles"])
    max_calque = round(float(np.nanmax(a)), 2)
    journal(f"   invariant 1 — max(calque) {max_calque} m/s vs "
            f"max(natif) {man['mesures']['max_ms']} m/s")
    if abs(max_calque - man["mesures"]["max_ms"]) > 0.02:
        journal("   ⛔ les deux maxima diffèrent. La réduction publiée "
                "n'est PAS un maximum de blocs (moyenne ? décimation ? "
                "`reshape` transposé ?).")
        return 1
    journal(f"   invariant 2 — mailles ≥ {seuil:.2f} m/s : calque "
            f"{n_calque}, natif {n_natif} (attendu : "
            f"{n_calque} ≤ {n_natif} ≤ {4 * n_calque})")
    if not (n_calque <= n_natif <= 4 * n_calque):
        journal("   ⛔ un bloc ne peut ni perdre une maille au-dessus du "
                "seuil, ni en inventer plus de quatre.")
        return 1
    journal("   ✅ les deux invariants de la réduction par maximum tiennent.")
    return 0


# ══════════════════════════════════════════════════════════════════════
#  LE PROGRAMME
# ══════════════════════════════════════════════════════════════════════
def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument("--run", help="run visé (ISO Z, heure ronde) ; sinon le "
                                 "plus frais publié et complet")
    a.add_argument("--grille", default=GRILLE, choices=("001", "0025"),
                   help="⛔ `0025` ne se réduit PAS en 0,02° par un "
                        "facteur entier — présent pour le diagnostic seul")
    a.add_argument("--sans-ecriture", action="store_true",
                   help="tout faire sauf écrire sur R2")
    a.add_argument("--forcer", action="store_true",
                   help="réingérer même si le run est déjà dans l'index")
    a.add_argument("--limite-echeances", type=int,
                   help="s'arrêter après N tranches (mise au point)")
    a.add_argument("--verifier", action="store_true",
                   help="relire ce qui est SERVI et rien d'autre")
    a = a.parse_args(argv)

    from storage import Storage                            # noqa: PLC0415
    st = Storage("agrume-pi-rafale", "AGRUME_BUCKET", "wind-grid",
                 plafond=pi_rafale.PLAFOND_ECRITURES)
    if a.verifier:
        return verifier_en_ligne(st)

    depart = time.perf_counter()
    nj, ni = verifier_alignement()
    lats, lons = axes_boite()
    crier(f"AGRUME — rafale à venir · boîte {BOITE['latmin']} → "
          f"{BOITE['latmax']} N × {BOITE['lonmin']} → {BOITE['lonmax']} E "
          f"= {nj} × {ni} au pas {pi_rafale.PAS_DEG}°")
    crier(f"   calque publié : {nj // 2} × {ni // 2} au pas "
          f"{pi_rafale.PAS_CALQUE_DEG}° — superposable au calque de pluie "
          f"de `agrume/piaf/`")

    if a.grille != GRILLE:
        crier(f"   ⚠️ grille {a.grille} demandée à la main : la réduction "
              f"en 0,02° n'a de sens QUE depuis {GRILLE}. Sortie "
              f"`--sans-ecriture` forcée.")
        a.sans_ecriture = True
    portail = Portail(SERVICE_AROMEPI, a.grille,
                      journal=lambda m: crier(f"   {m}"))

    # ── Valider le CHAMP avant de chercher un run ────────────────────
    # ⛔ PIÈGE Nº 2. Sans `agregation`, `describe` part sur un
    # identifiant sans `_PT15M` et récolte un `NoSuchCoverage` — le même
    # code que « run absent ». Sans ce contrôle, un nom de champ faux et
    # un portail muet sont indiscernables, et le message d'erreur accuse
    # le mauvais coupable.
    hier = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    temoins = [(hier + dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:00:00Z")
               for h in (0, 1, 2)]
    portail.valider_champ(CHAMP_WCS, temoins, agregation=AGREGATION)
    crier(f"   champ validé : {CHAMP_WCS}_{AGREGATION} "
          f"(niveau {NIVEAU_M} m, axe « {AXE_VERTICAL} »)")

    # ── Quel run ? ───────────────────────────────────────────────────
    if a.run:
        run = a.run
        arbre = portail.describe(CHAMP_WCS, run, agregation=AGREGATION)
        coeffs = coefficients_temps(arbre)
        if len(coeffs) != NB_ECHEANCES:
            raise Abort(
                f"le run {run} annonce {len(coeffs)} échéances au lieu de "
                f"{NB_ECHEANCES} — incomplet, et demandé explicitement.")
        verifier_coefficients(coeffs, run)
        latence = round((dt.datetime.now(dt.timezone.utc)
                         - pi_rafale._instant(run)).total_seconds() / 60.0, 1)
    else:
        # ⛔ Par l'INDEX, jamais par `HeadObject` : chaque tête est une
        # requête de classe A facturée, et la chaîne passe 144 fois par
        # jour.
        deja = (() if (a.forcer or a.sans_ecriture)
                else tuple(filter(None, [run_en_ligne(st)])))
        run, latence = dernier_run(portail, deja=deja, journal=crier)
        if run is None:
            crier("   rien de nouveau à ingérer.")
            return CODE_RIEN_A_FAIRE
    crier(f"   run retenu : {run} · publié depuis ≤ {latence} min")

    # ── Le tirage ────────────────────────────────────────────────────
    natif, lats, lons = tirer(portail, run, journal=crier,
                              limite=a.limite_echeances)
    ruban = Run(run, natif, lats, lons, latence_min=latence)
    crier(f"   mesures : {ruban.mesures()}")

    # ⛔ REFUS NOMMÉ : une tranche entièrement non renseignée. Publier un
    # ruban troué ferait un quart d'heure de « pas de rafale » au milieu
    # d'un orage — la forme de silence la plus dangereuse de ce projet.
    if a.limite_echeances is None:
        vides = [k for k, r in enumerate(ruban.remplissage_par_echeance())
                 if r == 0.0]
        if vides:
            raise Abort(
                f"les tranches {vides} sont entièrement vides. ⛔ Publier "
                f"ce ruban montrerait « pas de rafale » à ces échéances, "
                f"ce qui est indiscernable d'un calme — au moment précis "
                f"où le pilote regarde.")

    if a.sans_ecriture:
        crier("   (--sans-ecriture : rien n'est publié)")
    else:
        pi_rafale.ecrire(st, ruban, journal=crier,
                         extra=dict(fabrique_par="ingest_pi_rafale.py"))
        st.bilan(log=crier)
    crier(f"   {portail.bilan()}")

    duree = time.perf_counter() - depart
    crier(f"   durée totale : {duree:.0f} s")
    if duree > ALERTE_SECONDES:
        crier(f"   ⚠️ au-delà du budget de {ALERTE_SECONDES} s — le "
              f"portail rame, ou le quota est partagé avec `ingest_pi` / "
              f"`ingest_piaf`, dont les compteurs sont PAR PROCESSUS et "
              f"ne se voient pas.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Abort, ErreurPortail) as err:
        crier(f"⛔ {type(err).__name__} : {err}")
        sys.exit(1)
