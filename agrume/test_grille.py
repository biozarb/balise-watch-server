#!/usr/bin/env python3
"""
test_grille.py — banc du produit B, HORS-LIGNE.

    python3 agrume/test_grille.py

⚠️ CE QUE CE BANC PROTÈGE.

Le produit B ne s'archive pas : il ne survit pas à trois runs. Une
erreur ne s'y grave donc pas pour toujours — mais elle s'y voit encore
moins, parce qu'il n'y a rien d'ancien à quoi la comparer. Cinq façons
de casser en SILENCE, une par section :

  1. **Une carte retournée.** `lats` DÉCROÎT (le premier point est au
     nord). Un consommateur qui suppose l'inverse obtient une carte
     miroir — et sur un domaine presque carré, les Alpes retournées
     ressemblent toujours à des Alpes. Rien ne se voit.
  2. **Un reshape transposé.** eccodes rend un champ PLAT. `(Nj, Ni)`
     et `(Ni, Nj)` donnent tous deux un tableau de la bonne TAILLE ; un
     seul a le bon contenu.
  3. **La maille fine happée par la grille 0,025°.** Les niveaux 10, 20,
     50 et 100 m de la maille fine portent les mêmes noms `u`/`v` ET
     appartiennent aux 25 niveaux du 0,025°. `accepte()` dit donc OUI —
     et c'est correct de sa part. C'est à l'ingestion de vérifier la
     MAILLE, et ce banc verrouille cette responsabilité.
  4. **Une purge qui déborde.** Le produit A, DÉFINITIF, vit dans le même
     bucket sous `agrume/colonnes/`. Une clé mal filtrée y détruirait une
     archive irremplaçable.
  5. **Un manifeste qui ment.** Il annonce des axes et un nombre
     d'échéances ; s'ils ne décrivent pas le tableau livré, tout
     consommateur se trompe en croyant lire le contrat.

Aucun réseau, aucun GRIB, aucune clé.
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

import grille as GR  # noqa: E402
import quantification as CO  # noqa: E402
from quantification import (erreur_quantification,  # noqa: E402
                            quantifier)
from domaine import NIVEAUX_H_0025  # noqa: E402
from domaine import fenetre as _fenetre  # noqa: E402
from orographie import Orographie  # noqa: E402

echecs = []


def verifier(nom, condition, detail=""):
    print(f"  {'✓' if condition else '✗'} {nom}"
          + (f"   {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


META = dict(Ni=1121, Nj=717, lat0=55.4, lon0=-12.0, di=0.025, dj=0.025,
            jScan=0)

# ⚠️ 16/08 — CES QUATRE NOMBRES ÉTAIENT CODÉS EN DUR (364, 700, 61, 85),
# c'est-à-dire l'ancien domaine Nord-Alpes recopié à la main dans un
# banc. L'élargissement de `DOMAINE` les a rendus faux, et le banc est
# tombé — pas sur une régression, sur sa propre copie périmée.
#
# ⛔ C'est exactement le défaut que `domaine.py` existe pour empêcher, et
# il s'était glissé dans le banc plutôt que dans le code : « les indices
# se DÉDUISENT des métadonnées du GRIB, ils ne sont jamais codés en
# dur ». Un banc qui recopie une constante ne vérifie plus le code, il
# vérifie que personne n'a touché à la constante — et il devient un frein
# le jour où on y touche pour de bonnes raisons.
#
# Ils se déduisent donc de `fenetre()`, comme la production. Le banc suit
# désormais le domaine tout seul.
_J0, _J1, _I0, _I1 = _fenetre(META)
J0, I0, NJ, NI = _J0, _I0, _J1 - _J0 + 1, _I1 - _I0 + 1


def orog_bidon(meta=META, j0=J0, i0=I0, nj=NJ, ni=NI):
    """Une orographie synthétique dont la valeur ENCODE sa position :
    z = j * 1000 + i. Toute erreur d'indexation devient donc lisible dans
    la valeur elle-même, au lieu de produire un nombre plausible."""
    z = (np.arange(nj)[:, None] * 1000.0 + np.arange(ni)[None, :])
    return Orographie("0025", z, meta, j0, i0)


def champ_plat(meta=META, j0=J0, i0=I0):
    """Un champ France entière, plat, dont la valeur encode (j, i) de la
    grille NATIVE — même principe."""
    j = np.arange(meta["Nj"])[:, None] * 10000.0
    i = np.arange(meta["Ni"])[None, :] * 1.0
    return (j + i).ravel()


def section_10_identite_ab():
    """⛔ L'IDENTITÉ PRODUIT A ↔ PRODUIT B, AUX BALISES.

    Les deux produits sont remplis DANS LE MÊME `sur_champ`, depuis le
    MÊME message décodé — mais par deux chemins qui n'ont rien en commun :

        produit A :  values[ index_plats(meta, balises) ]   → quantifier
        produit B :  decouper(values, meta, orog)[j, i]     → quantifier

    ⚠️ RIEN NE LES FORCE À S'ACCORDER. `quantifier` est élémentaire, donc
    la valeur ne peut pas diverger — ce qui peut diverger, c'est LE POINT
    QU'ON DÉSIGNE. Un `j0`/`i0` décalé d'une case, un reshape transposé,
    un `jScan` mal lu : les deux produits serviraient alors deux points
    différents sous le même nom de balise, avec des valeurs parfaitement
    plausibles des deux côtés. Personne ne regarde les deux écrans en
    même temps.

    ⓘ C'est le dernier point ouvert de l'étape 12 bis (« identité produit
    A ↔ produit B aux niveaux isobares, aux balises »), et il est vérifié
    HORS LIGNE : le faire sur un run réel aurait demandé un run, donc
    n'aurait tourné qu'une fois. Le champ synthétique encode sa position
    (`j * 10000 + i`), donc un décalage d'une seule case se lit dans la
    valeur au lieu de se cacher dedans.
    """
    print("\n── 10. ⛔ Identité produit A ↔ produit B, aux balises ──")
    o = orog_bidon()
    champ = champ_plat()
    nj, ni = o.z.shape

    # Des balises posées PILE sur des points de grille du domaine — dont
    # les quatre coins, là où un décalage d'une case se voit le mieux.
    coins = [(0, 0), (0, ni - 1), (nj - 1, 0), (nj - 1, ni - 1),
             (nj // 2, ni // 2), (7, 3), (nj - 5, ni - 9)]
    balises = []
    for (j, i) in coins:
        balises.append(dict(
            id=f"{j}_{i}",
            lat=META["lat0"] - (J0 + j) * META["dj"],
            lon=META["lon0"] + (I0 + i) * META["di"]))

    idx, hors = CO.index_plats(META, balises)
    verifier("les balises de contrôle sont toutes DANS la grille native",
             not hors, f"{len(hors)} hors grille")

    fenetre = GR.decouper(champ, META, o)
    verifier("⚠️ la fenêtre découpée a la forme de l'orographie, pas celle "
             "du champ", fenetre.shape == (nj, ni), f"{fenetre.shape}")

    # ── LE CONTRÔLE ────────────────────────────────────────────────────
    desaccords = []
    for k, (j, i) in enumerate(coins):
        a = float(champ[idx[k]])          # ce que le produit A archiverait
        b = float(fenetre[j, i])          # ce que le produit B découpe
        if a != b:
            desaccords.append((balises[k]["id"], a, b))
    verifier("⛔ LE MÊME POINT : pour chaque balise, le produit A et le "
             "produit B tirent la MÊME valeur du même champ — un j0/i0 "
             "décalé d'une case donnerait deux points plausibles et "
             "différents",
             not desaccords,
             f"{len(coins)} balises · " + (f"1er écart {desaccords[0]}"
                                           if desaccords else "0 désaccord"))

    # ⚠️ ET LA RÉCIPROQUE : le banc doit ÊTRE CAPABLE d'échouer. Un
    # contrôle d'identité qui passe sur une orographie décalée ne vérifie
    # rien du tout — c'est l'erreur que `verif/test_colonnes.py` a déjà faite le
    # 12/08 en nourrissant `erreur_quantification` dans la mauvaise unité.
    o_faux = orog_bidon(i0=I0 + 1)
    fen_faux = GR.decouper(champ, META, o_faux)
    verifier("⚠️ …et le contrôle SAIT échouer : décalé d'une seule case en "
             "longitude, il détecte le désaccord",
             any(float(champ[idx[k]]) != float(fen_faux[j, i])
                 for k, (j, i) in enumerate(coins)))

    # ── Et l'identité vaut aussi APRÈS quantification, isobares comprises
    # ⓘ `zp` est le cas qui compte : il est le SEUL en float32, et sa
    # conversion (÷ G) vit dans `PARAM_ALTITUDE`. Si les deux produits ne
    # la faisaient pas au même endroit, l'axe vertical de la coupe et
    # celui du calque ne seraient pas le même — et les deux resteraient
    # plausibles.
    from quantification import PARAM_ALTITUDE             # noqa: PLC0415
    # ⚠️ REMIS DANS LA PLAGE PHYSIQUE, et ce n'est pas cosmétique :
    # `quantifier` NaN-ifie tout ce qui dépasse `PLAFOND_PHYSIQUE['zp']`
    # (20 000 m). La première version de ce bloc multipliait le champ
    # encodé par 3 — 730 000 m d'altitude — et rendait donc `nan` des
    # deux côtés. ⛔ Il aurait « passé » sur une comparaison plus
    # tolérante : deux NaN qui se ressemblent ne sont pas une identité.
    # Ici : 29 000 → 100 600 m²/s², soit 2 957 → 10 259 m.
    geop = 29000.0 + champ * 0.01
    qa = CO.quantifier(geop[idx], PARAM_ALTITUDE, dtype=np.float32)
    qb = CO.quantifier(GR.decouper(geop, META, o), PARAM_ALTITUDE,
                       dtype=np.float32)
    verifier("⛔ et l'identité tient APRÈS quantification, `zp` compris — "
             "la division par G vit dans `PARAM_ALTITUDE`, donc au même "
             "endroit pour les deux produits",
             all(np.isfinite(qa[k]) and float(qa[k]) == float(qb[j, i])
                 for k, (j, i) in enumerate(coins)),
             f"{float(qa[0]):.1f} → {float(qa[3]):.1f} m")


def section_8_surface():
    """── 8. La surface, et les trois sémantiques de temps ──

    ⛔ CE QUE CETTE SECTION PROTÈGE. `0025/SP1` et `0025/SP2` mélangent
    TROIS conventions de temps, et les confondre ne lève rien :

      instant   2t 2d sp prmsl blh CAPE_INS lcc mcc hcc
      max       max_i10fg — déjà horaire (stepRange 0-1, 1-2, 2-3…)
      accum     tp ssrd  — ⛔ CUMULÉS DEPUIS LE DÉBUT DU RUN (0-1, 0-2…)

    Servir `tp` sans différencier donne une pluie horaire qui ne décroît
    JAMAIS : une courbe lisse, croissante, et fausse. C'est le mode de
    panne de ce bloc, et il est invisible à l'œil.
    """
    from grille import PARAMS_GRILLE_SURF                # noqa: PLC0415

    print("\n── 8. La surface, et les trois sémantiques de temps ──")
    NECH = 5
    rng = np.random.default_rng(1308)
    g = GR.Grille("R", list(range(NECH)), np.linspace(46.3, 44.8, 3),
                  np.linspace(5.5, 7.6, 4),
                  np.zeros((3, 4), dtype=np.float32), domaine="banc")

    verifier("⛔ `psol` est en float32 — c'est l'ANCRE de la pression "
             "dérivée, et le float16 y coûte 0,125 à 0,25 hPa (1 à 2 m) "
             "contre 0,016 hPa pour la dérivation qu'elle ancre",
             g.psol.dtype == np.float32, str(g.psol.dtype))
    verifier("…et les autres champs de surface restent en float16",
             g.surf.dtype == np.float16)
    verifier("⚠️ un champ de surface est refusé à une échéance absente, "
             "et `psol` est accepté bien qu'absent de PARAMS_GRILLE_SURF",
             g.accepte_surface("psol", 0) and g.accepte_surface("t2m", 0)
             and not g.accepte_surface("t2m", 99)
             and not g.accepte_surface("u", 0))

    # ── Un cumul CROISSANT, comme le GRIB le publie ───────────────────
    cumul = [0.0, 0.4, 1.0, 1.0, 2.5]        # mm depuis le début du run
    for s in range(1, NECH):                 # ⛔ absent à τ=0, comme MF
        g.poser_surface("precipitation", s,
                        np.full((3, 4), cumul[s], dtype=np.float16))
        g.poser_surface("t2m", s, np.full((3, 4), 12.0, dtype=np.float16))
    g.poser_surface("t2m", 0, np.full((3, 4), 11.0, dtype=np.float16))
    for s in range(NECH):
        g.poser_surface("psol", s, np.full((3, 4), 913.25, dtype=np.float32))

    avant = np.asarray(g.surf[g.i_param_surf["precipitation"]][:, 0, 0],
                       dtype=np.float64)
    verifier("avant dé-accumulation, la pluie ne décroît jamais — c'est "
             "le cumul, pas l'horaire",
             all(np.nan_to_num(avant[k]) <= np.nan_to_num(avant[k + 1]) + 1e-9
                 for k in range(1, NECH - 1)),
             " ".join(f"{x:.1f}" for x in avant))

    g.deaccumuler()
    apres = np.asarray(g.surf[g.i_param_surf["precipitation"]][:, 0, 0],
                       dtype=np.float64)
    attendu = [np.nan, 0.4, 0.6, 0.0, 1.5]
    verifier("⛔ après dé-accumulation, chaque échéance porte SON heure",
             all((np.isnan(a) and np.isnan(b)) or abs(a - b) < 1e-2
                 for a, b in zip(apres, attendu)),
             " ".join("NaN" if np.isnan(x) else f"{x:.1f}" for x in apres))
    verifier("⚠️ l'échéance 0 est NaN et pas ZÉRO — un cumul sur zéro "
             "heure n'est pas « il n'a pas plu »",
             bool(np.isnan(apres[0])))
    verifier("⚠️ un champ `instant` n'est PAS touché par la dé-accumulation",
             abs(float(g.surf[g.i_param_surf["t2m"], 1, 0, 0]) - 12.0) < 1e-2)
    verifier("⛔ et `deaccumuler()` REFUSE d'être rejoué — différencier "
             "des différences donnerait une pluie négative un pas sur deux",
             _leve(g.deaccumuler))

    # ── ⛔ Un TROU dans les échéances (audit du 13/08) ────────────────
    # `steps = sorted(commun)` est une intersection de paquets : la
    # fenêtre 0–24 n'est PAS contiguë par construction, seule la
    # rallonge l'est. Sur [0, 1, 3, 4], la position de 3 h porterait
    # `cumul(3) − cumul(1)` : DEUX heures de pluie étiquetées UNE heure —
    # plus grande, jamais négative, donc invisible au garde `< 0`. La
    # première version de ce code faisait exactement ça ; le banc l'a
    # démentie.
    gt = GR.Grille("R", [0, 1, 3, 4], np.linspace(46.3, 44.8, 3),
                   np.linspace(5.5, 7.6, 4),
                   np.zeros((3, 4), dtype=np.float32), domaine="banc")
    for k, s in enumerate([1, 3, 4]):
        gt.poser_surface("precipitation", s,
                         np.full((3, 4), [0.4, 1.4, 1.6][k],
                                 dtype=np.float16))
    gt.deaccumuler()
    troue = np.asarray(
        gt.surf[gt.i_param_surf["precipitation"]][:, 0, 0], np.float64)
    verifier("⛔ une échéance qui SUIT UN TROU sort NaN, pas un cumul de "
             "deux heures étiqueté une heure",
             bool(np.isnan(troue[2])),
             "NaN" if np.isnan(troue[2]) else f"{troue[2]:.1f} mm — FAUX")
    verifier("…et les échéances au pas horaire, avant comme après le "
             "trou, gardent leur valeur",
             abs(troue[1] - 0.4) < 1e-2 and abs(troue[3] - 0.2) < 1e-2,
             " ".join("NaN" if np.isnan(x) else f"{x:.1f}" for x in troue))
    # ⚠️ Et sur [0, 2, …] la ligne « première échéance utile » ne doit
    # PAS s'appliquer : `a[1]` y est le cumul de DEUX heures.
    gs = GR.Grille("R", [0, 2, 3], np.linspace(46.3, 44.8, 3),
                   np.linspace(5.5, 7.6, 4),
                   np.zeros((3, 4), dtype=np.float32), domaine="banc")
    for s, v in ((2, 0.8), (3, 1.0)):
        gs.poser_surface("precipitation", s,
                         np.full((3, 4), v, dtype=np.float16))
    gs.deaccumuler()
    saut = np.asarray(
        gs.surf[gs.i_param_surf["precipitation"]][:, 0, 0], np.float64)
    verifier("⛔ si τ = 1 MANQUE, le cumul à τ = 2 n'est pas promu en "
             "valeur horaire",
             bool(np.isnan(saut[1])) and abs(saut[2] - 0.2) < 1e-2,
             " ".join("NaN" if np.isnan(x) else f"{x:.1f}" for x in saut))

    # ── Le remplissage explicite, et pourquoi il a remplacé un refus ──
    for forme in ((5, 7), (61, 85), (41, 205), (3, 4)):
        gg = GR.Grille("R", [0, 1], np.linspace(46.3, 44.8, forme[0]),
                       np.linspace(5.5, 7.6, forme[1]),
                       np.zeros(forme, dtype=np.float32), domaine="banc")
        tr, tc = gg.tranches(), gg.tranches_colonne()
        mal = [c for c, v in list(tr.items()) + list(tc.items())
               if v["offset"] % (4 if v["dtype"] == "float32" else 2)]
        verifier(f"⛔ {forme[0]}×{forme[1]} : toutes les tranches sont "
                 f"alignées, tampon ET colonne",
                 not mal and gg.octets_par_colonne() % 4 == 0
                 and len(gg.tampon_echeance(0)) == gg.octets_par_echeance(),
                 f"{gg.octets_par_echeance()} o/éch · "
                 f"{gg.octets_par_colonne()} o/col")


def _leve(fn):
    try:
        fn()
    except Exception:
        return True
    return False


def section_7_isobares():
    """── 7. Les isobares, la nébulosité, et les DEUX dispositions ──

    ⚠️ CE QUE CETTE SECTION PROTÈGE, ET QUI EST NOUVEAU AU LOT 12 : le
    produit publie désormais LA MÊME DONNÉE DEUX FOIS, sur deux axes.
    Le calque lit l'une, la vue de coupe lit l'autre, et RIEN dans le
    produit ne les force à s'accorder — sinon ce banc. Deux dispositions
    qui divergeraient ne lèveraient aucune exception : elles rendraient
    deux vents différents pour le même point, sur deux écrans que
    personne ne regarde en même temps.
    """
    import json

    from domaine import NIVEAUX_P                       # noqa: PLC0415
    from grille import (PARAMS_GRILLE, PARAMS_GRILLE_ISO,  # noqa: PLC0415
                        PARAMS_GRILLE_SURF)

    print("\n── 7. Les isobares, la nébulosité, et les deux dispositions ──")
    NJ2, NI2, NECH = 5, 7, 4
    rng = np.random.default_rng(1208)
    lats = np.linspace(46.3, 44.8, NJ2)
    lons = np.linspace(5.5, 7.6, NI2)
    g = GR.Grille("R", list(range(NECH)), lats, lons,
                  rng.uniform(150, 3900, (NJ2, NI2)).astype(np.float32),
                  domaine="banc")

    verifier("⛔ `ziso` est en float32 — le SEUL tableau du produit qui "
             "n'est pas en float16 (2,00 m d'erreur mesurés contre 0,24 mm)",
             g.ziso.dtype == np.float32, str(g.ziso.dtype))
    verifier("…et `iso` reste en float16", g.iso.dtype == np.float16)
    verifier("14 niveaux isobares, 1000 → 400 hPa",
             g.iso.shape[1] == 14 and min(NIVEAUX_P) == 400)

    # ⚠️ Les hauteurs et les pressions se RECOUVRENT numériquement :
    # 1000, 750 et 500 sont à la fois des niveaux m/sol et des hPa.
    verifier("⚠️ un niveau isobare de 500 hPa n'est pas accepté comme "
             "« 500 m/sol », ni l'inverse",
             g.accepte_isobare("u", 500, 0) and g.accepte("u", 500, 0)
             and not g.accepte_isobare("u", 375, 0)
             and not g.accepte("u", 925, 0))
    verifier("`zp` est accepté bien qu'absent de PARAMS_GRILLE_ISO — "
             "sinon `ziso` resterait NaN sans une erreur",
             g.accepte_isobare("zp", 700, 0))

    # ── Remplissage : des valeurs uniques, et le NaN de τ=0 ────────────
    # ⚠️ Tirées au sort, pas construites : une formule du genre
    # `k*1e6 + niveau*1e3` déborde le float16 (max 65 504) et rend des
    # `inf` — la première version de ce banc l'a fait, et son résultat
    # ressemblait à un défaut du code.
    for p in PARAMS_GRILLE:
        for niveau in NIVEAUX_H_0025:
            for s in range(NECH):
                g.poser(p["nom"], niveau, s,
                        rng.uniform(-99, 99, (NJ2, NI2)).astype(np.float16))
    for p in PARAMS_GRILLE_ISO:
        for hpa in NIVEAUX_P:
            for s in range(NECH):
                if p.get("absent_a_tau0") and s == 0:
                    continue        # ⛔ la règle de l'ingestion, rejouée
                g.poser_isobare(p["nom"], hpa, s,
                                rng.uniform(0, 99, (NJ2, NI2)).astype(np.float16))
    for hpa in NIVEAUX_P:
        for s in range(NECH):
            g.poser_isobare("zp", hpa, s,
                            rng.uniform(100, 7600, (NJ2, NI2)).astype(np.float32))

    rp = g.remplissage_par_parametre()
    verifier("⛔ `cc` est VIDE à τ=0 et pleine ailleurs — un zéro publié "
             "n'est pas une donnée (mesuré sur deux runs le 12/08)",
             abs(rp["iso_cc"] - (NECH - 1) / NECH) < 1e-6,
             f"{rp['iso_cc']:.2%} (attendu {(NECH-1)/NECH:.0%})")
    verifier("⚠️ `u` hauteur et `u` isobare sont comptés SÉPARÉMENT",
             "u" in rp and "iso_u" in rp and rp["u"] == 1.0)

    for p in PARAMS_GRILLE_SURF:
        for s_ in range(NECH):
            if p.get("absent_a_tau0") and s_ == 0:
                continue
            g.poser_surface(p["nom"], s_,
                            rng.uniform(0, 90, (NJ2, NI2)).astype(np.float16))
    for s_ in range(NECH):
        g.poser_surface("psol", s_,
                        rng.uniform(630, 996, (NJ2, NI2)).astype(np.float32))

    def reference(cle, j, i):
        """Le tableau que la tranche `cle` décrit, pour la colonne (j, i).

        ⚠️ Une seule table de correspondance, partagée par les deux
        relectures. Deux tables divergeraient exactement comme les deux
        dispositions qu'on vérifie ici."""
        if cle == "ziso":
            return g.ziso[:, :, j, i]
        if cle == "psol":
            return g.psol[None, :, j, i]
        if cle.startswith("iso_"):
            return g.iso[g.i_param_iso[cle[4:]], :, :, j, i]
        if cle in g.i_param_surf:
            return g.surf[g.i_param_surf[cle]][None, :, j, i]
        return g.h0025[g.i_param[cle], :, :, j, i]

    # ── Le contrat publié tient-il ? ──────────────────────────────────
    man = json.loads(json.dumps(g.manifeste()))     # comme il sera servi
    srv = man["service"]
    tr_e, tr_c = srv["tranches"], srv["colonnes"]["tranches"]
    pas = srv["colonnes"]["octets_par_colonne"]
    buf_e = [g.tampon_echeance(s) for s in g.steps]
    buf_c = g.tampon_colonnes()

    verifier("le tampon d'échéance fait exactement la taille annoncée",
             len(buf_e[0]) == srv["octets_par_echeance"],
             f"{len(buf_e[0])} o")
    verifier("l'objet colonnes fait `octets_par_colonne` × nb de colonnes",
             len(buf_c) == pas * NJ2 * NI2)
    verifier("⛔ le pas d'une colonne est multiple de 4 — sinon "
             "`new Float32Array(buffer, offset)` lève une colonne sur deux",
             pas % 4 == 0, f"{pas} o")
    verifier("⛔ chaque tranche float32 tombe sur un décalage aligné",
             all(t["offset"] % 4 == 0 for t in tr_e.values()
                 if t["dtype"] == "float32")
             and all(t["offset"] % 4 == 0 for t in tr_c.values()
                     if t["dtype"] == "float32"))
    verifier("⚠️ le manifeste publie le DTYPE de chaque tranche — le "
             "tampon n'est plus homogène",
             all("dtype" in t for t in tr_e.values())
             and tr_e["ziso"]["dtype"] == "float32"
             and tr_e["u"]["dtype"] == "float16")
    verifier("⚠️ tout ce que le calque lit est CONTIGU EN TÊTE "
             "(u, v hauteur puis u, v isobares puis ziso)",
             [c for c in tr_e][:5] == ["u", "v", "iso_u", "iso_v", "ziso"]
             and tr_e["u"]["offset"] == 0)

    # ── ⛔ LE TEST DU LOT : les deux dispositions se contredisent-elles ?
    # On relit les octets en n'utilisant QUE le manifeste, comme le fera
    # le navigateur. Un décodeur qui partagerait le code de l'encodeur ne
    # prouverait rien.
    desaccords = mal = 0
    for j in range(NJ2):
        for i in range(NI2):
            base = (j * man["axes"]["nb_lon"] + i) * pas
            for cle, tc in tr_c.items():
                dt = np.dtype(tc["dtype"])
                col = np.frombuffer(buf_c, dtype=dt, offset=base + tc["offset"],
                                    count=tc["niveaux"] * tc["echeances"]
                                    ).reshape(tc["niveaux"], tc["echeances"])
                te = tr_e[cle]
                ech = np.stack([
                    np.frombuffer(buf_e[s], dtype=dt, offset=te["offset"],
                                  count=te["niveaux"] * NJ2 * NI2
                                  ).reshape(te["niveaux"], NJ2, NI2)[:, j, i]
                    for s in range(NECH)], axis=1)
                if not np.array_equal(col, ech, equal_nan=True):
                    desaccords += 1
                # …et les deux disent-elles bien ce que porte le tableau ?
                ref = reference(cle, j, i)
                if not np.array_equal(col, np.asarray(ref, dtype=dt),
                                      equal_nan=True):
                    mal += 1
    n = NJ2 * NI2 * len(tr_c)
    verifier("⛔ les DEUX dispositions rendent la même valeur pour chaque "
             "colonne, chaque tranche, chaque échéance",
             desaccords == 0, f"{n - desaccords}/{n}")
    verifier("…et cette valeur est bien celle du tableau (relue par le "
             "seul manifeste, comme le fera le navigateur)",
             mal == 0, f"{n - mal}/{n}")

    verifier("le manifeste annonce la clé de l'objet colonnes",
             srv["cle_colonnes"].endswith("/colonnes.bin"))
    verifier("⚠️ il dit que `cc` manque à τ=0, et distingue « pas de "
             "nuages » de « pas de donnée »",
             "NÉBULOSITÉ" in man["avertissement"].upper()
             and "pas de donnée" in man["avertissement"])
    verifier("⚠️ il dit que les niveaux souterrains sont à MASQUER à la "
             "lecture, pas absents",
             "MASQUÉS À LA LECTURE" in man["avertissement"].upper())
    verifier("il publie le plafond mesuré, avant et après les isobares",
             man["plafond"]["avec_isobares_m"][0] > 7000
             and man["plafond"]["sans_isobares_m"][0] < 4000)

    section_8_surface()


def main():
    print("\n── 1. Les axes, et le sens qui ne se voit pas ──")
    o = orog_bidon()
    lats, lons = GR.axes_depuis_orographie(o)
    # ⚠️ 16/08 — la valeur attendue était « 61 × 85 (§4.1, mesuré le
    # 10/08) », donc l'ancien domaine recopié. Elle se déduit maintenant
    # de `fenetre()` : ce que ce contrôle doit prouver, c'est que
    # `axes_depuis_orographie` rend UN AXE PAR POINT de la fenêtre, pas
    # que la fenêtre vaut tel nombre — ça, c'est le travail de
    # `test_orographie`, sur l'artefact réel.
    verifier("la fenêtre rend un axe par point du domaine",
             (len(lats), len(lons)) == (NJ, NI),
             f"{len(lats)}×{len(lons)} (attendu {NJ}×{NI})")
    verifier("⚠️ lats DÉCROÎT — le premier point est au NORD",
             bool(np.all(np.diff(lats) < 0)),
             f"{lats[0]:.3f} → {lats[-1]:.3f}")
    verifier("lons croît — le premier point est à l'OUEST",
             bool(np.all(np.diff(lons) > 0)),
             f"{lons[0]:.3f} → {lons[-1]:.3f}")
    # ⚠️ 16/08 — les quatre bornes étaient recopiées (46.3 / 44.8 / 5.5 /
    # 7.6). Elles viennent maintenant de `DOMAINE`, pour la même raison
    # que `J0/I0/NJ/NI` ci-dessus : un banc qui recopie une constante ne
    # vérifie plus que personne ne l'a recopiée de travers.
    from domaine import DOMAINE as _DOM  # noqa: PLC0415
    verifier("les coins tombent sur le domaine",
             abs(lats[0] - _DOM["latmax"]) < 1e-4
             and abs(lats[-1] - _DOM["latmin"]) < 1e-4
             and abs(lons[0] - _DOM["lonmin"]) < 1e-4
             and abs(lons[-1] - _DOM["lonmax"]) < 1e-4,
             f"{lats[0]:.3f}/{lats[-1]:.3f} N × "
             f"{lons[0]:.3f}/{lons[-1]:.3f} E")

    # Une grille qui balaie du sud vers le nord doit donner des latitudes
    # CROISSANTES : si le code ignorait `jScan`, ce cas passerait quand
    # même et la convention deviendrait une supposition.
    # `lat0` est choisi pour que la fenêtre couvre EXACTEMENT le même
    # domaine en balayage sud→nord : latmin = lat0 + J0 × dj.
    # ⚠️ 16/08 — `44.8` était écrit en dur ici aussi.
    meta_sud = dict(META, jScan=1, lat0=_DOM["latmin"] - J0 * META["dj"])
    lats_sud, _ = GR.axes_depuis_orographie(orog_bidon(meta_sud))
    verifier("jScansPositively = 1 → latitudes CROISSANTES "
             "(le sens est LU, pas supposé)",
             bool(np.all(np.diff(lats_sud) > 0)))
    verifier("… et le même domaine est couvert dans les deux sens",
             abs(float(lats_sud.min()) - float(lats.min())) < 1e-4
             and abs(float(lats_sud.max()) - float(lats.max())) < 1e-4)

    # ⚠️ Ce cas est celui qui a démasqué un garde-fou creux le 10/08 : la
    # comparaison des axes à `orog.coords()` ne peut RIEN voir ici, parce
    # que les deux partent des mêmes (meta, j0, i0). Seule une référence
    # extérieure — le domaine déclaré — le détecte.
    faux = orog_bidon()
    faux.j0 += 1                       # un seul point de grille d'écart
    try:
        GR.axes_depuis_orographie(faux)
        decale = False
    except ValueError:
        decale = True
    verifier("⚠️ un décalage d'UN point de grille est refusé "
             "(2,8 km, invisible à l'œil sur une carte)", decale)
    faux_i = orog_bidon()
    faux_i.i0 -= 1
    try:
        GR.axes_depuis_orographie(faux_i)
        decale_i = False
    except ValueError:
        decale_i = True
    verifier("… en longitude aussi", decale_i)

    print("\n── 2. Le découpage : (Nj, Ni) et pas l'inverse ──")
    plat = champ_plat()
    fen = GR.decouper(plat, META, o)
    verifier("la fenêtre découpée a la forme de l'orographie",
             fen.shape == (NJ, NI), str(fen.shape))
    verifier("le coin nord-ouest vaut bien j0·10000 + i0 "
             "(la valeur ENCODE sa position)",
             fen[0, 0] == J0 * 10000.0 + I0, f"{fen[0, 0]:.0f}")
    verifier("le coin sud-est aussi",
             fen[NJ - 1, NI - 1] == (J0 + NJ - 1) * 10000.0 + (I0 + NI - 1))
    verifier("⚠️ un reshape transposé donnerait une AUTRE valeur au même "
             "coin — la taille ne prouve rien",
             plat.reshape(META["Ni"], META["Nj"])[J0, I0] != fen[0, 0])
    try:
        GR.decouper(plat[:-1], META, o)
        taille_refusee = False
    except ValueError:
        taille_refusee = True
    verifier("un champ de la mauvaise taille est refusé, pas rogné",
             taille_refusee)

    print("\n── 3. Le conteneur, et le piège de la maille fine ──")
    g = GR.Grille("2026-08-10T09:00:00Z", [0, 1, 2], lats, lons, o.z)
    # ⚠️ 16/08 — `61, 85` était l'ancien domaine recopié une fois de plus.
    # Ce que ce contrôle protège est l'ORDRE des axes (paramètre, niveau,
    # échéance, lat, lon) : une transposition y serait invisible autrement.
    # Les deux derniers viennent donc de la fenêtre.
    verifier("disposition (paramètre, niveau, échéance, lat, lon)",
             g.h0025.shape == (5, 25, 3, NJ, NI), str(g.h0025.shape))
    verifier("float16 sur les champs, float32 sur le sol",
             g.h0025.dtype == np.float16 and g.zsol.dtype == np.float32)
    verifier("tableau vide = NaN partout, jamais 0 "
             "(0 est un vent parfaitement crédible)",
             g.remplissage() == 0.0)

    g.poser("u", 3000, 2, np.full((NJ, NI), 7.5))
    k_u, k_3000, k_2 = (g.i_param["u"], g.i_niveau[3000], g.i_step[2])
    verifier("le niveau 3000 m se range bien en DERNIÈRE position "
             "(l'ordre de NIVEAUX_H_0025 est le contrat)",
             k_3000 == len(NIVEAUX_H_0025) - 1)
    verifier("un champ posé se relit à sa place, et nulle part ailleurs",
             float(g.h0025[k_u, k_3000, k_2, 0, 0]) == 7.5
             and np.isnan(float(g.h0025[k_u, k_3000 - 1, k_2, 0, 0])))

    verifier("⚠️⚠️ `accepte()` dit OUI à « u à 20 m » — parce que 20 m EST "
             "un niveau du 0,025°. C'est à l'ingestion de vérifier la "
             "MAILLE, sinon la maille fine (151×211) tomberait ici.",
             g.accepte("u", 20, 0) is True)
    verifier("un niveau qui n'existe pas en 0,025° est refusé",
             g.accepte("u", 35000, 0) is False)
    verifier("un paramètre hors du produit B est refusé (`zp`, isobares)",
             g.accepte("zp", 500, 0) is False)
    verifier("une échéance non ingérée est refusée",
             g.accepte("u", 500, 99) is False)

    print("\n── 4. La quantification, héritée du produit A ──")
    t_k = np.linspace(233.15, 313.15, 5000)         # −40 → +40 °C
    p_t = [p for p in GR.PARAMS_GRILLE if p["nom"] == "t"][0]
    err_c = erreur_quantification(t_k, p_t)
    err_k = erreur_quantification(t_k, dict(p_t, decalage=0.0))
    verifier("⚠️ la température est stockée en °C : le gain sur l'erreur "
             "de quantification est MESURÉ, pas supposé",
             err_k / max(err_c, 1e-12) > 4,
             f"kelvins {err_k:.4f} contre celsius {err_c:.4f} "
             f"(×{err_k / max(err_c, 1e-12):.1f})")
    verifier("le produit B ne redéfinit PAS ses paramètres — il reprend "
             "ceux du produit A (une liste, pas deux)",
             GR.PARAMS_GRILLE is not None
             and [p["nom"] for p in GR.PARAMS_GRILLE]
             == ["u", "v", "t", "r", "tke"])
    sentinelle = quantifier(np.array([9999.0, 3.0]), p_t)
    verifier("la sentinelle 9999 d'eccodes devient NaN, pas une valeur",
             bool(np.isnan(float(sentinelle[0]))))

    print("\n── 5. L'index et la purge, sans jamais lister ──")
    # ⚠️ 12/08 : les clés portent le DOMAINE et la rétention se compte
    # PAR domaine. `STEPS` est court exprès — ce qui est testé ici est
    # l'index, pas la taille des tampons.
    STEPS = [0, 1, 2]
    D = "nord-alpes"

    def cles(r, d=D):
        return GR.cles_du_run(r, d, STEPS)

    index = dict(GR.INDEX_VIDE)
    runs = ["2026-08-10T00:00:00Z", "2026-08-10T03:00:00Z",
            "2026-08-10T06:00:00Z", "2026-08-10T09:00:00Z"]
    supprimes = []
    for r in runs:
        index, a_sup = GR.index_apres(index, r, D, cles(r))
        supprimes += a_sup
        index = GR.index_apres_purge(index, [])
    verifier("après 4 runs, il en reste exactement 3 en ligne",
             len(index["runs"]) == 3, str(len(index["runs"])))
    verifier("le plus récent est en tête (tri antichronologique)",
             index["runs"][0]["run"] == runs[-1])
    verifier("c'est bien le PLUS ANCIEN qui a été purgé, et lui seul",
             supprimes == cles(runs[0]), str(supprimes))
    verifier("un run publie 1 clé par échéance, plus `colonnes.bin`, "
             "plus le manifeste", len(cles(runs[0])) == len(STEPS) + 2)
    # ⛔ 12/08 — LE TEST QUI COMPTE VRAIMENT ICI. `colonnes.bin` est le
    # plus gros objet du produit (57,8 Mo). Absent de `cles_du_run`, il
    # serait écrit à chaque run et purgé JAMAIS : sans `ListObjects`, un
    # objet hors index est définitivement invisible et définitivement
    # facturé. Le compte ci-dessus le dirait mal ; la présence, bien.
    verifier("⚠️ `colonnes.bin` est DANS les clés du run — donc dans "
             "l'index, donc purgeable",
             GR.cle_colonnes(runs[0], D) in cles(runs[0]))
    verifier("⚠️ et il part bien à la SUPPRESSION quand le run sort",
             GR.cle_colonnes(runs[0], D) in supprimes)
    verifier("`restes` est vide quand tout s'est bien supprimé",
             index["restes"] == [])

    # Un run rejoué : il ne doit ni se dupliquer, ni se purger lui-même.
    rejoue, a_sup = GR.index_apres(index, runs[-1], D, cles(runs[-1]))
    verifier("⚠️ rejouer le même run ne le duplique pas dans l'index",
             len(rejoue["runs"]) == 3
             and len({e["run"] for e in rejoue["runs"]}) == 3)
    verifier("⚠️ et ne demande PAS de supprimer ses propres clés",
             not any(c in cles(runs[-1]) for c in a_sup), str(a_sup))

    # Un échec de suppression doit survivre au run suivant.
    idx2 = GR.index_apres_purge(index, ["agrume/grille/vieux/grille.npz"])
    idx3, a_sup3 = GR.index_apres(idx2, "2026-08-10T12:00:00Z", D,
                                  cles("2026-08-10T12:00:00Z"))
    verifier("⚠️ une suppression échouée est REPRISE au run suivant "
             "(sans ListObjects, rien d'autre ne saurait qu'elle existe)",
             "agrume/grille/vieux/grille.npz" in a_sup3)
    verifier("et elle n'est comptée qu'une fois",
             a_sup3.count("agrume/grille/vieux/grille.npz") == 1)

    print("\n── 5 bis. DEUX DOMAINES : les compteurs ne se mélangent pas ──")
    # ⛔ Le défaut que cette section attrape : avec une rétention
    # GLOBALE, écrire deux domaines par run purgerait chaque domaine au
    # bout d'un run et demi — et un domaine dont l'ingestion échoue
    # disparaîtrait entièrement pendant que l'autre garde ses trois runs.
    idx = dict(GR.INDEX_VIDE)
    for r in runs:
        for d in ("nord-alpes", "pyrenees"):
            idx, _ = GR.index_apres(idx, r, d, cles(r, d))
            idx = GR.index_apres_purge(idx, [])
    verifier("deux domaines × 3 runs = 6 entrées, pas 3",
             len(idx["runs"]) == 6, str(len(idx["runs"])))
    for d in ("nord-alpes", "pyrenees"):
        verifier(f"  et chacun garde bien ses 3 runs ({d})",
                 sum(1 for e in idx["runs"] if e["domaine"] == d) == 3)

    # Un domaine qui n'avance plus ne doit pas être vidé par l'autre.
    idx4 = dict(idx)
    for r in ("2026-08-10T12:00:00Z", "2026-08-10T15:00:00Z",
              "2026-08-10T18:00:00Z", "2026-08-10T21:00:00Z"):
        idx4, _ = GR.index_apres(idx4, r, "nord-alpes", cles(r))
        idx4 = GR.index_apres_purge(idx4, [])
    verifier("⚠️ 4 runs alpins de plus n'effacent PAS les Pyrénées "
             "(ingestion pyrénéenne en panne)",
             sum(1 for e in idx4["runs"] if e["domaine"] == "pyrenees") == 3)

    print("\n── 5 ter. Les clés de l'ANCIEN format ne fuient pas ──")
    # ⛔ Sans `ListObjects`, un objet qui sort de l'index sans être
    # supprimé devient INVISIBLE et définitivement perdu. Les entrées
    # d'avant le 12/08 n'ont pas de `domaine` : elles doivent partir à la
    # suppression, pas à l'oubli.
    legacy = dict(GR.INDEX_VIDE, runs=[
        dict(run="2026-08-12T06:00:00Z",
             cles=["agrume/grille/2026-08-12T06:00:00Z/grille.npz",
                   "agrume/grille/2026-08-12T06:00:00Z/manifest.json"]),
        dict(run="2026-08-12T09:00:00Z",
             cles=["agrume/grille/2026-08-12T09:00:00Z/grille.npz",
                   "agrume/grille/2026-08-12T09:00:00Z/manifest.json"])])
    apres, a_sup = GR.index_apres(legacy, "2026-08-12T12:00:00Z", D,
                                  cles("2026-08-12T12:00:00Z"))
    verifier("⛔ les 4 clés de l'ancien format partent à la SUPPRESSION, "
             "pas à l'oubli",
             all(c in a_sup for e in legacy["runs"] for c in e["cles"]),
             f"{len(a_sup)} clé(s) à supprimer")
    verifier("et l'index n'en garde aucune trace muette",
             all(e.get("domaine") for e in apres["runs"]))
    verifier("le garde-fou de préfixe les accepte quand même (même "
             "produit, ancien chemin)", GR.verifier_prefixe(a_sup) is True)

    verifier("le garde-fou accepte les clés du produit B",
             GR.verifier_prefixe(cles(runs[0])) is True)
    try:
        GR.verifier_prefixe(["agrume/colonnes/2026-08-10T00:00:00Z/colonnes.npz"])
        deborde = True
    except ValueError:
        deborde = False
    verifier("⛔ et REFUSE une clé du produit A — archive DÉFINITIVE, "
             "même bucket", not deborde)
    try:
        GR.verifier_prefixe(cles(runs[0]) + ["autre/chose.npz"])
        partiel = True
    except ValueError:
        partiel = False
    verifier("une seule intruse arrête la purge ENTIÈRE — on ne supprime "
             "pas « ce qui est légitime » en attendant", not partiel)

    print("\n── 6. Le manifeste ne ment pas ──")
    m = g.manifeste()
    verifier("il annonce le bon nombre d'échéances",
             len(m["echeances"]) == g.h0025.shape[2])
    verifier("il annonce le bon nombre de niveaux",
             len(m["niveaux_m_sol"]) == g.h0025.shape[1])
    verifier("il annonce le bon nombre de paramètres, dans l'ordre",
             [p["nom"] for p in m["parametres"]]
             == list(g.i_param.keys()) == ["u", "v", "t", "r", "tke"])
    verifier("il annonce les axes, et leurs bornes correspondent",
             m["axes"]["nb_lat"] == g.h0025.shape[3]
             and abs(m["axes"]["lat_premier"] - float(lats[0])) < 1e-3)
    verifier("⚠️ il écrit le SENS des latitudes en toutes lettres",
             "DÉCROISSANTES" in m["axes"]["sens"])
    verifier("il dit que le produit est jetable et donne la rétention",
             m["retention_runs"] == GR.RETENTION_RUNS
             and "JETABLE" in m["avertissement"])
    verifier("il dit que la TKE manque à l'échéance 0 (mesuré, pas un bug)",
             "TKE" in m["avertissement"])
    verifier("il donne la règle de conversion vers l'altitude-mer",
             "zsol" in m["reference_verticale"])

    section_7_isobares()

    # ── 9. ⛔ LE DÉCALAGE DE PRÉCISION SE PUBLIE ──────────────────────
    # `prmsl` est archivé en `hPa − 1000` pour gagner de la précision
    # float16, mais l'unité publiée reste « hPa ». Sans le champ, un
    # client qui suit le manifeste affiche −13 hPa au lieu de 987 : une
    # valeur fausse, finie, tracée sans une erreur. Ce bloc verrouille les
    # deux moitiés du contrat — l'archive EST décalée, le manifeste LE DIT.
    print("\n── 9. ⛔ Le décalage de PRÉCISION, publié et défaisable ──")
    surf = {p["nom"]: p for p in m["parametres_surface"]}
    mer = surf["pression_mer"]
    verifier("le manifeste publie `decalage_precision` pour `prmsl`",
             mer.get("decalage_precision") == -1000.0,
             f"{mer.get('decalage_precision')!r}")
    verifier("⚠️ et il vaut 0 pour tous ceux qui n'en ont pas — un champ "
             "absent obligerait le client à deviner",
             all(p.get("decalage_precision") == 0.0
                 for n, p in surf.items() if n != "pression_mer"))
    verifier("⛔ le décalage d'UNITÉ n'y entre PAS : `2t` est archivé en °C, "
             "le défaire ajouterait 273,15",
             surf["t2m"]["unite"] == "°C"
             and surf["t2m"].get("decalage_precision") == 0.0)
    # Le contrat, joué en entier sur une valeur : 101 350 Pa → 1013,5 hPa.
    p_mer = next(p for p in CO.PARAMS_SURFACE if p["nom"] == "pression_mer")
    archive = float(CO.quantifier(np.array([101350.0]), p_mer)[0])
    rendu = archive - mer["decalage_precision"]
    verifier("⛔ archivé décalé, rendu juste : 101 350 Pa → "
             f"{archive:.3f} archivé → {rendu:.3f} hPa",
             abs(rendu - 1013.5) < 0.15,
             f"écart {abs(rendu - 1013.5):.4f} hPa")
    # ⚠️ MESURÉ SUR LA PLAGE RÉELLE DU DOMAINE, pas sur une valeur. Sur la
    # seule valeur 1013,5 hPa les deux erreurs valent ZÉRO — elle tombe
    # pile sur un float16 représentable dans les deux dispositions, et le
    # banc aurait conclu « le décalage ne sert à rien ». C'est exactement
    # l'erreur de mesure que ce projet a déjà faite deux fois.
    plage = np.linspace(63000.0, 99600.0, 20001)
    avec = CO.erreur_quantification(plage, p_mer)
    sans = CO.erreur_quantification(plage, {**p_mer, "decalage_precision": 0.0})
    verifier("⚠️ et le décalage GAGNE bien de la précision — sans lui, "
             "l'erreur float16 double",
             avec < sans / 1.5,
             f"{avec:.4f} hPa avec · {sans:.4f} sans")

    section_10_identite_ab()
    section_11_relecture_r2()
    section_12_provenance()

    print("\n  grille :", "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    return 0 if not echecs else 1


# ══════════════════════════════════════════════════════════════════════
#  §12 — LA PROVENANCE (Lot L, arbitrage A4 · 17/08/2026)
# ══════════════════════════════════════════════════════════════════════
#  ⛔ CE QUE CE BANC EXISTE POUR ATTRAPER, ET C'EST UN SEUL DÉFAUT :
#  **une fusion qui ne se dit pas.** Le jour où le rafraîchissement PI
#  entrera dans la chaîne, la seule chose qui distinguera « cette valeur
#  vient d'AROME » de « cette valeur vient de PI » sera ce champ. S'il
#  ment, ou s'il se tait, l'écran affirmera quelque chose de faux SANS
#  QU'AUCUNE REQUÊTE N'ÉCHOUE — c'est le mode de panne de tout ce
#  fichier.
#
#  ⚠️ ET IL SAIT ÉCHOUER, par construction : le dernier contrôle rejoue
#  le manifeste AMPUTÉ de son champ `provenance` — c'est-à-dire le code
#  d'AVANT le Lot L — et exige qu'il devienne IMPOSSIBLE d'y distinguer
#  un domaine servi par PI d'un domaine qui ne l'est pas. Si ce contrôle
#  passait aussi sans le champ, le champ ne servirait à rien.
def section_12_provenance():
    import json                                          # noqa: PLC0415

    print("\n── 12. La provenance : ce qui est dit, et ce qui est TU ──")
    from domaine import DOMAINES_PI  # noqa: PLC0415

    o = orog_bidon()
    lats, lons = GR.axes_depuis_orographie(o)
    steps = [0, 1, 2, 3]
    run = "2026-08-17T03:00:00Z"

    # ⚠️ DEUX domaines, et c'est tout l'objet du contrôle : un couvert
    # par PI, un qui ne l'est pas. Un banc sur un seul domaine ne peut
    # pas voir la différence qu'A9 demande de PUBLIER.
    couvert = DOMAINES_PI[0]
    sans_pi = next(d for d in ("pyrenees", "tarn-aveyron-herault")
                   if d not in DOMAINES_PI)

    g_ok = GR.Grille(run, steps, lats, lons, o.z, domaine=couvert)
    g_no = GR.Grille(run, steps, lats, lons, o.z, domaine=sans_pi)
    p_ok, p_no = g_ok.provenance(), g_no.provenance()

    # ── a. La granularité, et rien de plus fin ────────────────────────
    verifier("une entrée par ÉCHÉANCE, et les trois blocs à chacune",
             len(p_ok["par_echeance"]) == len(steps)
             and all(set(e["blocs"]) == {"hauteur", "isobare", "surface"}
                     for e in p_ok["par_echeance"]),
             f"{len(p_ok['par_echeance'])} échéances")
    verifier("⛔ les noms de blocs sont EXACTEMENT ceux que "
             "`service.tranches[*].bloc` publie — deux vocabulaires "
             "pour un seul découpage, et le client choisit mal",
             set(p_ok["blocs"])
             == {t["bloc"] for t in g_ok.tranches().values()})

    # ── b. Tant qu'il n'y a rien à fusionner, elle dit AROME ──────────
    verifier("⛔ sans fusion, la provenance dit `arome` PARTOUT — une "
             "affirmation vraie, pas un remplissage",
             all(b["modele"] == "arome" and b["run"] == run
                 for e in p_ok["par_echeance"] for b in e["blocs"].values()))

    # ── c. ⛔ L'ÂGE N'EST PAS PUBLIÉ ──────────────────────────────────
    # ⚠️ Il périme à la lecture. Un manifeste qui porterait « il y a
    # 25 min » serait faux 25 minutes plus tard, et le client n'aurait
    # aucun moyen de le savoir. Ce contrôle est là parce que c'est la
    # pente naturelle : publier l'âge est plus commode pour l'écran.
    plat = json.dumps(p_ok, ensure_ascii=False)
    verifier("⛔ AUCUN âge publié — il se calcule à l'écran depuis `run`",
             not any(cle in plat for cle in
                     ('"age', '"ageMin', '"age_min', '"il_y_a', '"anciennete')))

    # ── d. Le chiffrage, MESURÉ — et il dément la note du 13/08 ───────
    # ⛔ La note `note-provenance-pyramide-priorites-13-08.md` annonçait
    # « ~2–3 Ko dans le MANIFESTE ». **Mesuré ici le 17/08 : 11,1 Ko sur
    # 52 échéances** — 3,7× l'estimation. L'écart vient d'un détail que
    # l'estimation ne voyait pas : l'horodatage du run est répété
    # 156 fois (3 blocs × 52 échéances), soit ~7 Ko de la facture.
    #
    # ⚠️ CE CHIFFRE NE ROUVRE PAS A4, et il faut dire pourquoi plutôt
    # que de le corriger en douce : l'arbitrage opposait échéance×bloc à
    # une carte PAR POINT chiffrée à **31,5 Mo**. 11 Ko contre 31,5 Mo,
    # c'est le même verdict que 3 Ko contre 31,5 Mo — un facteur 2 800
    # au lieu de 10 000. Ce qui aurait dû le rouvrir, c'est une dérive
    # vers le mégaoctet ; le plafond est donc posé là où ça compte.
    #
    # ⓘ Et la redondance est GARDÉE sciemment : factoriser le run
    # (« sauf mention contraire, c'est celui du manifeste ») ferait du
    # champ un différentiel, donc un piège le jour où deux blocs d'une
    # même échéance viendront de deux runs — exactement le cas que ce
    # champ existe pour porter.
    g52 = GR.Grille(run, list(range(52)), lats, lons, o.z, domaine=couvert)
    ko = len(json.dumps(g52.provenance()["par_echeance"],
                        ensure_ascii=False).encode()) / 1024
    verifier("⚠️ sur 52 échéances, `par_echeance` tient sous 20 Ko — "
             "la note du 13/08 disait ~3 Ko, la MESURE dit 11,1 ; "
             "l'arbitrage tient quand même (contre 31,5 Mo par point)",
             ko < 20.0, f"{ko:.1f} Ko")

    # ── e. ⛔ L'ABSENCE SE DIT (A9) ───────────────────────────────────
    verifier(f"⛔ sur `{sans_pi}`, PI est déclaré INDISPONIBLE",
             p_no["arome_pi"]["disponible"] is False)
    verifier("⛔ …AVEC sa raison, en toutes lettres — « pas de champ » et "
             "« pas de champ POUR CETTE RAISON » ne se lisent pas pareil",
             isinstance(p_no["arome_pi"]["pourquoi"], str)
             and sans_pi in p_no["arome_pi"]["pourquoi"]
             and len(p_no["arome_pi"]["pourquoi"]) > 80)
    verifier("⚠️ …et il n'y a AUCUNE route de rafraîchissement à suivre — "
             "une route publiée là rendrait des 404 pour toujours",
             p_no["arome_pi"]["rafraichissement"] is None)
    verifier(f"⛔ sur `{couvert}`, PI est déclaré DISPONIBLE, et sans "
             "raison d'absence à inventer",
             p_ok["arome_pi"]["disponible"] is True
             and p_ok["arome_pi"]["pourquoi"] is None)

    # ── f. La route est PUBLIÉE, pas déductible ──────────────────────
    raf = p_ok["arome_pi"]["rafraichissement"]
    verifier("la route du rafraîchissement est publiée (gabarit + index + "
             "objets) — rien à coder en dur côté client",
             isinstance(raf, dict)
             and "{domaine}" in raf["gabarit_cle"]
             and "{run_pi}" in raf["gabarit_cle"]
             and raf["cle_index"].endswith("index.json")
             and set(raf["objets"]) == {"carte.bin", "colonnes.bin",
                                        "manifest.json"})
    verifier("⛔ la préséance dit `u`/`v` du bloc `hauteur` et RIEN "
             "D'AUTRE — un rafraîchissement qui déborderait sur les "
             "isobares écraserait ce qu'il ne sait pas calculer",
             raf["blocs_concernes"] == ["hauteur"]
             and raf["parametres_concernes"] == ["u", "v"])
    verifier("⚠️ …et le manifeste du produit B ne NOMME aucun run PI : il "
             "est publié 8 fois par jour, PI 24 — le run que le client "
             "lira n'existe pas encore quand ce manifeste s'écrit",
             not any(k for k, v in raf.items()
                     if isinstance(v, str) and v.endswith("00:00Z")))

    # ── g. ⛔ LE CONTRÔLE QUI SAIT ÉCHOUER ────────────────────────────
    # Le manifeste d'AVANT le Lot L, reconstitué : le même, moins
    # `provenance`. Si un consommateur pouvait quand même distinguer les
    # deux domaines, le champ serait décoratif.
    man_ok = {k: v for k, v in g_ok.manifeste().items() if k != "provenance"}
    man_no = {k: v for k, v in g_no.manifeste().items() if k != "provenance"}
    neutre = {"produit", "domaine", "bornes", "axes", "remplissage",
              "remplissage_par_parametre"}
    verifier("⛔ SANS le champ, les deux manifestes ne diffèrent que par "
             "leur GÉOGRAPHIE — rien n'y dit que l'un est servi par PI "
             "et l'autre pas. C'est ce trou-là que le Lot L bouche.",
             {k for k in man_ok if man_ok[k] != man_no.get(k)} <= neutre,
             str(sorted({k for k in man_ok
                         if man_ok[k] != man_no.get(k)} - neutre)))
    verifier("…et AVEC le champ, la différence est explicite et lisible",
             g_ok.manifeste()["provenance"]["arome_pi"]["disponible"]
             is not g_no.manifeste()["provenance"]["arome_pi"]["disponible"])


def section_11_relecture_r2():
    import json                                          # noqa: PLC0415
    """── 11. ⛔ La relecture d'un run PUBLIÉ, tampon par tampon ──

    `couper.py --run` et `front_altitude.py` lisaient
    `agrume/grille/{run}/grille.npz` — une clé SUPPRIMÉE par l'étape 11
    (le format npz n'est plus jamais écrit sur R2, et `index_apres`
    envoie les clés sans domaine à la suppression). 404 à chaque appel,
    pendant deux lots, et aucun banc ne le voyait : la CI ne couvrait
    que `construire()`. Ce banc prouve désormais l'aller-retour
    `tampon_echeance()` → `depuis_tampons()` à l'octet près — la route
    que ces deux lecteurs empruntent maintenant.
    """
    print("\n── 11. ⛔ La relecture d'un run publié (depuis_tampons) ──")
    rng = np.random.default_rng(1313)
    NECH = 3
    g = GR.Grille("2026-08-13T00:00:00Z", list(range(NECH)),
                  np.linspace(46.3, 44.8, 5), np.linspace(5.5, 7.6, 7),
                  rng.uniform(150, 3900, (5, 7)).astype(np.float32),
                  domaine="banc")
    from domaine import NIVEAUX_H_0025, NIVEAUX_P       # noqa: PLC0415
    for p in GR.PARAMS_GRILLE:
        for niveau in NIVEAUX_H_0025:
            for s in range(NECH):
                g.poser(p["nom"], niveau, s,
                        rng.uniform(-40, 40, (5, 7)).astype(np.float16))
    for p in GR.PARAMS_GRILLE_ISO:
        for hpa in NIVEAUX_P:
            for s in range(NECH):
                g.poser_isobare(p["nom"], hpa, s,
                                rng.uniform(-40, 40, (5, 7))
                                .astype(np.float16))
        for s in range(NECH):
            g.poser_isobare("zp", 500, s,
                            rng.uniform(5000, 6000, (5, 7))
                            .astype(np.float32))
    for p in GR.PARAMS_GRILLE_SURF:
        for s in range(NECH):
            g.poser_surface(p["nom"], s,
                            rng.uniform(0, 30, (5, 7)).astype(np.float16))
    for s in range(NECH):
        g.poser_surface("psol", s,
                        rng.uniform(650, 990, (5, 7)).astype(np.float32))
    g.deaccumuler()

    man = json.loads(json.dumps(g.manifeste()))     # comme depuis R2
    tampons = {s: g.tampon_echeance(s) for s in range(NECH)}
    zsol_octets = g.tampon_zsol()
    g2 = GR.Grille.depuis_tampons(man, tampons, zsol_octets)

    def identiques(a, b):
        a32, b32 = a.astype(np.float32), b.astype(np.float32)
        return bool(np.array_equal(a32, b32, equal_nan=True))

    verifier("⛔ h0025, iso, ziso, surf et psol reviennent À L'OCTET "
             "PRÈS — c'est la route de `couper.py --run` et de "
             "`front_altitude.py`",
             all(identiques(getattr(g, n), getattr(g2, n))
                 for n in ("h0025", "iso", "ziso", "surf", "psol")))
    verifier("…et zsol, lats, lons aussi",
             identiques(g.zsol, g2.zsol) and identiques(g.lats, g2.lats)
             and identiques(g.lons, g2.lons))
    verifier("⚠️ la grille relue refuse `deaccumuler()` — un run publié "
             "porte des cumuls DÉJÀ différenciés",
             _leve(g2.deaccumuler))
    verifier("⚠️ un tampon PARTIEL laisse ses NaN au lieu de lever — une "
             "échéance absente est un trou, pas une panne",
             bool(np.isnan(np.float32(
                 GR.Grille.depuis_tampons(man, {0: tampons[0]}, zsol_octets)
                 .h0025[0, 0, 1, 0, 0]))))
    verifier("⛔ un step INCONNU du manifeste lève — c'est un mélange de "
             "runs, pas un trou",
             _leve(lambda: GR.Grille.depuis_tampons(
                 man, {9: tampons[0]}, zsol_octets)))
    tronque = tampons[1][:-2]
    verifier("⛔ un tampon TRONQUÉ est refusé en citant la taille annoncée",
             _leve(lambda: GR.Grille.depuis_tampons(
                 man, {1: tronque}, zsol_octets)))


if __name__ == "__main__":
    sys.exit(main())
