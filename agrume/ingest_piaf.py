#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/ingest_piaf.py — l'ingestion de la pluie à venir  (20/08/2026)
#                          Lot Q2 · arbitrage A20 = « le VPS tire »
#
#  ── OÙ ÇA TOURNE, ET POURQUOI CE N'EST PAS UN RUNNER ─────────────────
#  Sur le VPS, par timer systemd, toutes les 10 minutes.
#
#  ⛔ ET LE CADRAGE SE TROMPAIT EN ÉCRIVANT « le VPS ne touche jamais un
#  GRIB ». C'était vrai du produit A/B (le miroir S3, 7 Go, un runner) ;
#  ce n'est PLUS vrai depuis le Lot L : `ingest_pi.py` tire 300 champs
#  WCS depuis le VPS toutes les heures, 28,3 Mo, et écrit 142,4 Mo sur
#  R2. Cette chaîne-ci est le MÊME patron, pas une exception.
#
#  ⚠️ Le cron GitHub avait été retenu (A20, première rédaction), puis
#  MESURÉ sur les 500 derniers runs du `keepalive.yml` de ce dépôt :
#  **81 % des créneaux `*/10` sautés**, médiane 41 min entre deux
#  exécutions, maximum 6 h 39. À 53 min d'âge médian, onze des
#  trente-neuf échéances d'une passe sont déjà du passé — pour un produit
#  qui s'appelle « prévision immédiate ». Le timer systemd, lui, tient sa
#  cadence : c'est la seule propriété unique du VPS, être allumé.
#
#  ── LE BUDGET, MESURÉ LE 20/08 SUR LE VPS ────────────────────────────
#      39 requêtes · 65,7 Mo · 14,9 s   (boîte A19 d'origine)
#      39 requêtes · 71,0 Mo · ~20 s    (boîte élargie de ce module)
#      médiane 0,371 s/requête, max 0,516
#  → 3,9 req/min sur le quota du portail (limite mesurée : 100/min).
#    Le quota ne mord PAS ici, et c'est la première chaîne du projet dont
#    ce soit vrai. ⚠️ Le quota du circuit `pro` n'a PAS été mesuré comme
#    séparé de celui d'AROME-PI ; à 3,9 req/min la question est sans
#    objet, mais elle le redeviendrait si la cadence passait à 5 min.
#
#  ⛔ NE JAMAIS PARALLÉLISER. Mesuré le 10/08 et écrit dans `portail.py` :
#  à forte concurrence le portail COUPE LA CONNEXION au lieu de rendre
#  429 (102 `ConnectionResetError` sur 200 requêtes).
#
#  ── LES CODES DE SORTIE, ET LE FAUX VERT ─────────────────────────────
#      0  une passe a été ingérée ET écrite     → ping vert
#      3  rien à faire (déjà ingérée)           → AUCUN ping
#      autre  échec                             → ping rouge
#  ⚠️ Le 3 existe pour la même raison que dans `ingest_pi.py` : pinguer
#  au vert quand il n'y a rien eu à faire garderait le voyant allumé
#  pendant que la chaîne aurait cessé d'écrire.
#
#  Usage :
#      python3 agrume/ingest_piaf.py                  # la passe la plus fraîche
#      python3 agrume/ingest_piaf.py --sans-ecriture  # chiffrer sans écrire
#      python3 agrume/ingest_piaf.py --passe 2026-08-20T07:35:00Z --forcer
#      python3 agrume/ingest_piaf.py --verifier       # relire ce qui est SERVI
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

import piaf  # noqa: E402
from piaf import (AGREGATION, BOITE, CHAMP_WCS, CLE_INDEX,  # noqa: E402
                  NB_ECHEANCES, PAS_DEG, Abort, Passe, axes_boite,
                  cles_de_la_passe, echeances, passes_candidates,
                  verifier_parite)
from portail import (SERVICE_PIAF, CouvertureAbsente,  # noqa: E402
                     ErreurPortail, Portail)

CODE_RIEN_A_FAIRE = 3
#: Au-delà, ce n'est pas « un peu long » : c'est que le portail rame ou
#: que le quota est partagé. Le budget mesuré est de ~40 s.
ALERTE_SECONDES = 240


def crier(msg=""):
    print(msg, flush=True)


# ══════════════════════════════════════════════════════════════════════
#  DÉTECTION DE LA PASSE
# ══════════════════════════════════════════════════════════════════════
def nb_echeances_publiees(arbre):
    """Le nombre de coefficients temporels déclarés par le DescribeCoverage.

    ⛔ C'EST LE CONTRÔLE DE COMPLÉTUDE, et il coûte 5 ko. Sans lui, une
    passe publiée à moitié se découvrirait à la 27ᵉ requête — après avoir
    payé 26 champs, et avec un ruban troué au milieu.

    ⚠️ L'élément `coefficients` apparaît DEUX fois dans la réponse, et la
    première est VIDE (`<gmlrgrid:coefficients/>`). Prendre la première
    rendrait 0 échéance sur une passe parfaitement complète.
    """
    for el in arbre.iter():
        if el.tag.endswith("coefficients") and (el.text or "").strip():
            return len((el.text or "").split())
    return 0


def derniere_passe(portail, deja=(), maintenant=None, journal=crier):
    """La passe publiée la plus fraîche, COMPLÈTE et pas encore ingérée.

    Renvoie `(passe, latence_min)` ou `(None, None)`.

    ⚠️ On interroge par `DescribeCoverage` (≈5 ko) et non par
    `GetCapabilities` (1,89 Mo pour 12 270 identifiants) — un facteur 375
    pour une information qui tient dans quelques centaines d'octets.
    """
    t = maintenant or dt.datetime.now(dt.timezone.utc)
    for passe in passes_candidates(maintenant=t):
        if passe in deja:
            # ⛔ On S'ARRÊTE à la première déjà connue : les candidates
            # sont ordonnées de la plus fraîche à la plus ancienne, donc
            # tout ce qui suit est plus vieux encore. Continuer
            # réingérerait du passé.
            journal(f"  passe {passe} déjà en ligne — rien à faire")
            return None, None
        try:
            arbre = portail.describe(CHAMP_WCS, passe, agregation=AGREGATION)
        except CouvertureAbsente:
            continue
        n = nb_echeances_publiees(arbre)
        if n != NB_ECHEANCES:
            journal(f"  ⚠️ {passe} est publiée mais annonce {n} échéances "
                    f"au lieu de {NB_ECHEANCES} — passée")
            continue
        latence = (t - piaf._instant(passe)).total_seconds() / 60.0
        return passe, round(latence, 1)
    return None, None


# ══════════════════════════════════════════════════════════════════════
#  LE TIRAGE
# ══════════════════════════════════════════════════════════════════════
def verifier_geometrie(h, lats, lons, quoi):
    """⛔⛔ LE GARDE-FOU LE PLUS IMPORTANT DU MODULE.

    Le WCS choisit SA découpe. Le piège est déjà payé côté PI le 10/08 :
    61 × 85 rendus là où 61 × 84 étaient attendus. Une colonne d'écart
    vaut ~750 m ici, et TOUTE la nappe serait décalée — une carte de
    pluie juste, posée à côté du terrain, sans une seule erreur.

    ⚠️ `longitudeOfFirstGridPointInDegrees` rend **358.15** pour −1,85 :
    le GRIB écrit les longitudes en 0…360. Comparer sans normaliser
    déclencherait le refus sur une géométrie parfaitement correcte.
    """
    import eccodes as ec                                   # noqa: PLC0415

    def norm(x):
        return x - 360.0 if x > 180.0 else x

    recu = dict(
        nb_lat=int(ec.codes_get(h, "Nj")),
        nb_lon=int(ec.codes_get(h, "Ni")),
        lat_premier=float(ec.codes_get(h, "latitudeOfFirstGridPointInDegrees")),
        lat_dernier=float(ec.codes_get(h, "latitudeOfLastGridPointInDegrees")),
        lon_premier=norm(float(ec.codes_get(
            h, "longitudeOfFirstGridPointInDegrees"))),
        lon_dernier=norm(float(ec.codes_get(
            h, "longitudeOfLastGridPointInDegrees"))),
        pas_lat=float(ec.codes_get(h, "jDirectionIncrementInDegrees")),
        pas_lon=float(ec.codes_get(h, "iDirectionIncrementInDegrees")))
    attendu = dict(
        nb_lat=len(lats), nb_lon=len(lons),
        lat_premier=float(lats[0]), lat_dernier=float(lats[-1]),
        lon_premier=float(lons[0]), lon_dernier=float(lons[-1]),
        pas_lat=PAS_DEG, pas_lon=PAS_DEG)
    for cle, attend in attendu.items():
        recue = recu[cle]
        ecart = abs(recue - attend)
        if (ecart > 1e-4) if isinstance(attend, float) else (recue != attend):
            raise Abort(
                f"{quoi} : géométrie REFUSÉE — {cle} vaut {recue} et non "
                f"{attend}. ⛔ Le WCS a recoupé autrement. Une colonne "
                f"d'écart vaut ~750 m et décalerait toute la nappe, sans "
                f"qu'une seule requête n'échoue. NE PAS élargir la "
                f"tolérance.")
    # ⚠️ L'unité et le type de traitement se vérifient à CHAQUE champ, pas
    # une fois : le producteur peut changer d'avis entre deux passes, et
    # le mot « RATE » du nom de couverture rendrait le changement
    # invisible.
    if ec.codes_get(h, "units") != "kg m**-2":
        raise Abort(f"{quoi} : unité {ec.codes_get(h, 'units')!r} au lieu "
                    f"de 'kg m**-2'. ⛔ Ce module publie des mm.")
    if ec.codes_get(h, "stepType") != "accum":
        raise Abort(f"{quoi} : `stepType` = {ec.codes_get(h, 'stepType')!r} "
                    f"au lieu de 'accum'. ⛔ La donnée a cessé d'être un "
                    f"cumul — l'agrégat horaire deviendrait faux.")
    return recu


def tirer(portail, passe, boite=None, journal=crier, limite=None):
    """Les 39 tranches, une requête à la fois. Rend `(natif, lats, lons)`.

    ⛔ Une requête = un instant. Le portail refuse tout groupement :
    « Slicing on time is mandatory : only a 2D coverage can be
    downloaded », et l'INTERVALLE est refusé aussi. 39 requêtes, ce n'est
    pas un choix de ce code.
    """
    import eccodes as ec                                   # noqa: PLC0415

    b = dict(boite or BOITE)
    lats, lons = axes_boite(b)
    ech = echeances(passe)[:limite or NB_ECHEANCES]
    natif = np.full((NB_ECHEANCES, len(lats), len(lons)), np.nan,
                    dtype=np.float32)
    t0 = time.monotonic()
    for e in ech:
        octets = portail.get_coverage(
            CHAMP_WCS, passe, e["instant_demande"], None, b,
            agregation=AGREGATION)
        h = ec.codes_new_from_message(octets)
        try:
            verifier_geometrie(h, lats, lons,
                               f"échéance +{e['fin_min']} min")
            natif[e["rang"]] = np.asarray(
                ec.codes_get_values(h), dtype=np.float32).reshape(
                    len(lats), len(lons))
        finally:
            ec.codes_release(h)
        if (e["rang"] + 1) % 10 == 0 or e["rang"] + 1 == len(ech):
            journal(f"    {e['rang'] + 1}/{len(ech)} tranches "
                    f"({time.monotonic() - t0:.0f} s)")
    return natif, lats, lons


# ══════════════════════════════════════════════════════════════════════
#  LA VÉRIFICATION — « fait ≠ commité ≠ déployé ≠ VU »
# ══════════════════════════════════════════════════════════════════════
def verifier_en_ligne(st, journal=crier):
    """Relit l'index, le manifeste et les octets TELS QUE SERVIS, et
    confronte le calque à la coupe sur un échantillon de mailles.

    ⛔ Une divergence ici voudrait dire que le calque et la coupe montrent
    deux pluies différentes au même instant. C'est le défaut que « les
    objets s'écrivent ensemble ou pas du tout » existe pour ne pas créer,
    et il ne se voit que sur les octets SERVIS — pas sur ceux de la
    mémoire (leçon du Lot L3b).

    ⚠️ Le calque étant un MAXIMUM de bloc, l'égalité attendue n'est pas
    « identiques » mais « calque ≥ coupe, et calque = max des 4 ». On
    vérifie donc l'invariant exact, pas une ressemblance.
    """
    passe = piaf.passe_en_ligne(st)
    if not passe:
        journal(f"⛔ aucune passe LISIBLE — `dernier` est vide dans "
                f"{CLE_INDEX}")
        return 1
    cles = cles_de_la_passe(passe)
    man = st.get_json(cles[-1])
    if not man:
        journal(f"⛔ manifeste absent : {cles[-1]}")
        return 1
    age = (dt.datetime.now(dt.timezone.utc)
           - piaf._instant(passe)).total_seconds() / 60.0
    journal(f"✅ passe lisible : {passe} · âge {age:.1f} min")
    journal(f"   {man['octets_publies'] / 1e6:.1f} Mo publiés · "
            f"mesures {man['mesures']}")
    creux = [i for i, r in enumerate(man["remplissage_par_echeance"])
             if r < 1.0]
    journal(f"   remplissage : {'plein sur les 39 tranches' if not creux else f'CREUX aux rangs {creux}'}")
    journal(f"   heures entières : "
            f"{[h['heure'] for h in man['heures_entieres']]}")

    cal = man["service"]["calque"]
    cou = man["service"]["coupe"]
    pas_e, njc, nic = cal["octets_par_echeance"], cal["nb_lat"], cal["nb_lon"]
    pas_k = cou["octets_par_colonne"]
    f = piaf.FACTEUR_CALQUE
    pires, n, non_nuls = [], 0, 0
    for nom, d in cou["domaines"].items():
        cle_col = cou["gabarit_cle"].format(domaine=nom)
        nj, ni = d["nb_lat"], d["nb_lon"]
        # Décalage du coin du domaine dans la boîte, en mailles natives.
        dj = round((man["axes"]["lat_premier"] - d["lat_premier"]) / PAS_DEG)
        di = round((d["lon_premier"] - man["axes"]["lon_premier"]) / PAS_DEG)
        # ⛔ ON BALAIE, ON NE PIQUE PAS TROIS POINTS. Un contrôle qui ne
        # tombe que sur des mailles à 0,0 mm est VERT SANS RIEN PROUVER :
        # zéro égale zéro quel que soit l'offset. C'est le défaut du
        # premier jet, vu à la première exécution réelle — 27 mailles
        # confrontées, écart maximal 0,000e+00, et pas une goutte dedans.
        # 25 colonnes réparties sur toute la fenêtre trouvent de la pluie
        # dès qu'il en tombe quelque part, et `non_nuls` le COMPTE.
        echantillon = [(j, i)
                       for j in range(0, nj, max(1, nj // 5))
                       for i in range(0, ni, max(1, ni // 5))]
        for (j, i) in echantillon[:25]:
            brut = st.get_range(cle_col, (j * ni + i) * pas_k, pas_k)
            if brut is None:
                journal(f"   ⛔ {cle_col} : absent alors que l'index le "
                        f"réclame")
                return 1
            serie = np.frombuffer(brut, dtype="<f2", count=NB_ECHEANCES)
            # La maille du calque qui CONTIENT ce point natif.
            bj, bi = (dj + j) // f, (di + i) // f
            if bj >= njc or bi >= nic:
                continue
            for rang in (0, NB_ECHEANCES // 2, NB_ECHEANCES - 1):
                o = rang * pas_e + (bj * nic + bi) * 2
                v = float(np.frombuffer(st.get_range(cles[0], o, 2),
                                        dtype="<f2")[0])
                c = float(serie[rang])
                n += 1
                if c > 0.0 or v > 0.0:
                    non_nuls += 1
                # ⛔ L'INVARIANT : le calque est un MAXIMUM, donc il
                # majore toujours la coupe. Un calque INFÉRIEUR à la
                # coupe voudrait dire que la réduction a perdu la maille
                # qu'elle est censée garder.
                if np.isfinite(c) and np.isfinite(v):
                    pires.append(c - v)
                elif np.isfinite(c) != np.isfinite(v):
                    pires.append(float("inf"))
    pire = max(pires) if pires else 0.0
    journal(f"   ⛔ calque ≥ coupe, {n} mailles confrontées dont "
            f"{non_nuls} PLUVIEUSES : pire dépassement de la coupe "
            f"{pire:.3e} mm")
    if pire > 0:
        journal("   ⛔ LE CALQUE EST INFÉRIEUR À LA COUPE quelque part — "
                "la réduction par maximum a perdu une maille. Le pilote "
                "verrait moins de pluie sur la carte que dans sa coupe.")
        return 1
    if non_nuls == 0:
        # ⛔ VERT SANS RIEN PROUVER. Zéro égale zéro quel que soit
        # l'offset : sur une passe entièrement sèche, ce contrôle ne
        # distingue pas deux jeux d'octets bien alignés de deux jeux
        # décalés. Ce n'est pas un échec — c'est un contrôle qui n'a rien
        # eu à mordre, et il doit le DIRE plutôt que d'afficher un ✅ qui
        # se lira comme une preuve.
        journal(f"   ⚠️ CONTRÔLE VIDE : aucune des {n} mailles "
                f"confrontées ne portait de pluie. L'alignement des deux "
                f"jeux n'est donc PAS vérifié par cette exécution — "
                f"rejouer quand il pleut quelque part dans les domaines "
                f"(`mesures.part_pluvieuse` le dit).")
        return 0
    journal(f"   ✅ le calque majore la coupe partout où l'on a regardé, "
            f"et {non_nuls} de ces mailles portaient réellement de la "
            f"pluie — l'alignement des deux jeux est donc CONFRONTÉ, pas "
            f"seulement compatible.")
    return 0


# ══════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--passe", default=None,
                   help="passe visée (ISO Z, multiple de 5 min) ; par "
                        "défaut la plus fraîche publiée")
    p.add_argument("--sans-ecriture", action="store_true",
                   help="tout faire sauf écrire sur R2")
    p.add_argument("--forcer", action="store_true",
                   help="réingérer même si la passe est déjà dans l'index")
    p.add_argument("--limite-echeances", type=int, default=None,
                   help="s'arrêter après N tranches (mise au point)")
    p.add_argument("--verifier", action="store_true",
                   help="relire ce qui est SERVI et confronter les deux jeux")
    a = p.parse_args(argv)

    from storage import Storage                            # noqa: PLC0415
    st = Storage("agrume-piaf", "AGRUME_BUCKET", "wind-grid",
                 plafond=piaf.PLAFOND_ECRITURES)

    if a.verifier:
        return verifier_en_ligne(st)

    debut = time.monotonic()
    verifier_parite()
    lats, lons = axes_boite()
    crier(f"AGRUME — pluie à venir · boîte {BOITE['latmin']}–"
          f"{BOITE['latmax']} N × {BOITE['lonmin']}–{BOITE['lonmax']} E "
          f"= {len(lats)} × {len(lons)}")

    portail = Portail(SERVICE_PIAF, "001",
                      journal=lambda m: crier(f"   {m}"))

    # ⛔ VALIDER LE CHAMP AVANT DE CHERCHER LA PASSE. Sans ça, un nom de
    # champ faux et une passe non publiée rendent EXACTEMENT la même
    # chose — HTTP 404, `NoSuchCoverage` — et la détection conclurait
    # « rien n'est publié » pour toujours. La rétention du producteur
    # étant de 4,3 jours, un témoin d'il y a deux heures est sûr.
    t = dt.datetime.now(dt.timezone.utc).replace(second=0, microsecond=0)
    t -= dt.timedelta(minutes=t.minute % piaf.PAS_MIN)
    temoins = [piaf.horodatage(t - dt.timedelta(hours=h)) for h in (2, 3, 4)]
    portail.valider_champ(CHAMP_WCS, temoins, agregation=AGREGATION)
    crier("  ✅ champ validé sur une passe témoin")

    if a.passe:
        passe, latence = a.passe, None
    else:
        # ⚠️ Par l'INDEX, jamais par `exists` : `HeadObject` est facturé
        # Class A chez R2, et le timer repasse toutes les 10 min.
        deja = () if (a.forcer or a.sans_ecriture) else tuple(
            filter(None, [piaf.passe_en_ligne(st)]))
        passe, latence = derniere_passe(portail, deja=deja, journal=crier)
        if passe is None:
            crier(f"  {portail.bilan()}")
            # ⚠️ 3 et non 0 — cf. l'en-tête : le faux vert.
            return CODE_RIEN_A_FAIRE
    crier(f"  passe retenue : {passe}"
          + (f" (latence de publication {latence} min)"
             if latence is not None else ""))

    natif, lats, lons = tirer(portail, passe, journal=crier,
                              limite=a.limite_echeances)
    crier(f"  {portail.bilan()}")
    crier(f"  octets reçus : {portail.compteur['octets'] / 1e6:.2f} Mo")

    ruban = Passe(passe, natif, lats, lons, latence_min=latence)
    rempl = ruban.remplissage_par_echeance()
    crier(f"  mesures : {ruban.mesures()}")
    vides = [k for k, r in enumerate(rempl) if r == 0.0]
    if vides and not a.limite_echeances:
        raise Abort(
            f"{len(vides)} tranche(s) ENTIÈREMENT non finies (rangs "
            f"{vides[:6]}) — publier un ruban troué ferait un blanc de "
            f"5 minutes dans l'animation, à l'endroit exact où le pilote "
            f"regarde, sans que rien ne le dise.")
    crier(f"  à publier : {ruban.octets_publies() / 1e6:.1f} Mo · "
          f"heures entières {[h['heure'] for h in ruban.heures]}")

    if a.sans_ecriture:
        crier("  ⓘ --sans-ecriture : rien n'a été écrit.")
    else:
        piaf.ecrire(st, ruban, journal=crier,
                    extra=dict(fabrique_par="ingest_piaf.py"))
        st.bilan(log=crier)

    secondes = time.monotonic() - debut
    crier(f"  durée totale : {secondes:.0f} s")
    if secondes > ALERTE_SECONDES:
        crier(f"  ⚠️ AU-DELÀ DE {ALERTE_SECONDES} s — le budget mesuré est "
              f"de ~40 s. Ce n'est pas « un peu long » : c'est que le "
              f"portail rame ou que le quota est partagé.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Abort, ErreurPortail) as err:
        crier(f"⛔ {type(err).__name__} : {err}")
        sys.exit(1)
