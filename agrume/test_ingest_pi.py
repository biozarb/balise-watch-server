#!/usr/bin/env python3
"""
test_ingest_pi.py — banc de l'ingestion AROME-PI (étape 8 bis), HORS-LIGNE.

    python3 agrume/test_ingest_pi.py

⚠️ CE QUE CE BANC PROTÈGE.

L'ingestion PI n'a qu'un seul client : le composite de l'étape 9, qui
calcule `Δ = PI − AROME` point à point. **Une erreur ici ne produit pas
une panne, elle produit un delta.** Et un delta faux est lisse,
plausible, tracé sans broncher — c'est exactement le genre de défaut que
ce projet met des jours à voir. Sept façons de casser en silence, une
par section :

  1. **Deux découpes qui se ressemblent.** Le WCS choisit SA fenêtre à
     partir de la boîte lat/lon ; l'orographie a la sienne, héritée de
     `(j0, i0)`. Le 10/08 elles différaient d'UNE COLONNE — 61 × 85
     contre 61 × 84, sur une égalité en virgule flottante à 7,6 °E. Une
     colonne vaut 1,95 km : le composite comparerait alors des colonnes
     voisines, et rendrait **une carte de gradient horizontal déguisée
     en correction temporelle**.
  2. **Les longitudes en 0–360.** Le GRIB AROME commence à 348,0°, soit
     −12°. Sans normalisation la fenêtre 5,5–7,6 °E ne rencontre AUCUN
     point, la découpe rend un tableau vide — et la médiane d'un tableau
     vide est **NaN, pas une exception**.
  3. **Une carte retournée.** `lats` DÉCROÎT. Sur un domaine presque
     carré, des Alpes retournées ressemblent toujours à des Alpes.
  4. **Deux produits qui divergent.** Colonnes et grille sortent du MÊME
     champ aligné. S'ils cessaient de tomber sur le même point, le
     sondage et la carte donneraient deux vents différents au même
     endroit. Banc de PARITÉ, comme celui de l'étape 8.
  5. **Un trou comblé.** Un champ absent doit DISPARAÎTRE — pas être
     interpolé depuis ses voisins. C'est ce qui arrivera au 10 m si PI
     ne le sert pas, et le manifeste doit le dire.
  6. **Des minutes prises pour des heures.** PI est au pas de 15 min,
     AROME à l'heure. Un `step` de 1 ne veut pas dire la même chose des
     deux côtés, et un mélange d'unités qui se ressemblent décale tout
     d'un facteur 60 sans jamais lever.
  7. **Une purge qui déborde.** Les colonnes PI sont DÉFINITIVES et la
     rétention du portail est de 4,25 jours : ce qui est détruit ici
     n'est pas régénérable.

Aucun réseau, aucune clé, aucun GRIB.
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pi as PI  # noqa: E402
from pi import (ECHEANCES_MIN, NIVEAUX_DELTA, NIVEAUX_PI,  # noqa: E402
                Abort, ColonnesPI, GrillePI, aligner_sur_axes,
                cles_du_run_colonnes, geometrie_grib, instants_du_run,
                params_actifs)
from domaine import NIVEAUX_H_0025  # noqa: E402
from grille import verifier_prefixe  # noqa: E402

echecs = []


def verifier(quoi, condition, detail=""):
    ok = bool(condition)
    if not ok:
        echecs.append(quoi)
    print(f"  {'✅' if ok else '⛔'} {quoi}" + (f" — {detail}" if detail else ""))
    return ok


def leve(quoi, fn, fragment=None):
    """Vérifie que `fn` REFUSE. ⚠️ Un refus est le comportement voulu :
    entre une ingestion qui échoue et un décalage silencieux, on choisit
    l'échec — il coûte un run, l'autre coûte la confiance."""
    try:
        fn()
    except (Abort, ValueError) as e:
        # ⓘ Deux types, parce que deux modules : `pi.Abort` pour
        # l'alignement, et le `ValueError` de `grille.verifier_prefixe`,
        # réutilisé tel quel plutôt que réécrit. Le banc accepte les deux
        # SANS les confondre : ce qui compte est le refus, et le message.
        ok = fragment is None or fragment in str(e)
        return verifier(quoi, ok, "" if ok else f"message inattendu : {e}")
    except Exception as e:                                   # noqa: BLE001
        return verifier(quoi, False, f"a levé {type(e).__name__} et non Abort")
    return verifier(quoi, False, "n'a RIEN levé")


# ══════════════════════════════════════════════════════════════════════
#  Une grille synthétique dont TOUT encode sa position
# ══════════════════════════════════════════════════════════════════════
#  ⚠️ La valeur d'un point vaut `1000·j_global + i_global` dans le repère
#  du GRIB reçu. Une erreur d'indexation ne rend donc PAS un nombre
#  plausible : elle rend les coordonnées de l'endroit où on est allé
#  chercher. C'est la même astuce que `test_transect.py`, et c'est ce qui
#  a permis d'y voir un −52 pris pour un 52.
LAT0, LON0, PAS = 46.5, 5.0, 0.025


def meta_recu(nj, ni, lat0=LAT0, lon0=LON0, pas=PAS, jscan=0):
    return dict(Ni=ni, Nj=nj, lat0=lat0, lon0=lon0, di=pas, dj=pas,
                jScan=jscan)


def champ_positionnel(nj, ni):
    j, i = np.meshgrid(np.arange(nj), np.arange(ni), indexing="ij")
    return (1000.0 * j + i).astype(np.float64)


def main():
    print(__doc__.split("Aucun réseau")[0].strip()[:0] or "", end="")
    print("── 1. ⚠️⚠️ L'alignement : on ne fait PAS confiance au WCS ──")

    nj, ni = 12, 20
    meta = meta_recu(nj, ni)
    champ = champ_positionnel(nj, ni)
    lats_recu, lons_recu = geometrie_grib(meta)

    # a) La fenêtre cible est STRICTEMENT INTÉRIEURE à celle du WCS.
    #    C'est le cas nominal : le portail rend un point de plus que
    #    nécessaire (mesuré le 10/08 : 85 colonnes contre 84).
    cible_lats, cible_lons = lats_recu[2:9], lons_recu[3:17]
    coupe = aligner_sur_axes(champ, meta, cible_lats, cible_lons)
    verifier("une fenêtre plus large est découpée à la bonne taille",
             coupe.shape == (7, 14), f"{coupe.shape}")
    verifier("⚠️ et au bon ENDROIT — la valeur encode sa position",
             coupe[0, 0] == 1000 * 2 + 3 and coupe[-1, -1] == 1000 * 8 + 16,
             f"coin haut-gauche {coupe[0, 0]}, attendu {1000 * 2 + 3}")

    # b) Une fenêtre cible qui DÉBORDE : le WCS n'a pas tout couvert.
    leve("⛔ une cible qui déborde la fenêtre reçue est REFUSÉE",
         lambda: aligner_sur_axes(champ, meta, cible_lats,
                                  np.append(lons_recu, lons_recu[-1] + PAS)),
         "ne couvre pas")

    # c) Le décalage d'UN DEMI-POINT — le cas vicieux. Il ne déborde pas,
    #    il ne change pas la taille, et sans contrôle d'écart il passerait
    #    en rendant les colonnes VOISINES.
    leve("⛔⛔ un décalage d'un demi-point de grille est REFUSÉ",
         lambda: aligner_sur_axes(champ, meta, cible_lats,
                                  cible_lons + PAS / 2),
         "1,95 km")

    # d) Un pas différent : sous-échantillonnage silencieux.
    leve("⛔ une cible au pas double (une colonne sur deux) est REFUSÉE",
         lambda: aligner_sur_axes(champ, meta, cible_lats, lons_recu[3:17:2]),
         "contigu")

    print("\n── 2. ⚠️ Les longitudes en 0–360 (le GRIB commence à 348°) ──")
    meta360 = meta_recu(nj, ni, lon0=354.0)          # = −6°
    _, lons360 = geometrie_grib(meta360)
    verifier("les longitudes sont ramenées en degrés SIGNÉS",
             abs(float(lons360[0]) + 6.0) < 1e-9, f"{lons360[0]}")
    verifier("elles restent croissantes après normalisation",
             bool(np.all(np.diff(lons360) > 0)))
    coupe360 = aligner_sur_axes(champ, meta360, lats_recu[2:9], lons360[3:17])
    verifier("et l'alignement fonctionne dessus, au bon endroit",
             coupe360[0, 0] == 1000 * 2 + 3)
    # ⚠️ CE BLOC A DÉMENTI CE QU'IL DEVAIT VÉRIFIER — écrit d'abord pour
    # montrer qu'un axe franchissant GREENWICH devenait non monotone,
    # donc suspect. **Faux, mesuré ici** : la normalisation en
    # [−180, 180[ traverse Greenwich sans accroc, parce que −0,1 et
    # +0,375 se rangent dans le bon ordre. La vraie discontinuité est à
    # l'ANTIMÉRIDIEN, où +179,9 est suivi de −179,6.
    # ⓘ Les deux sont hors du domaine Nord-Alpes. On les écrit quand même
    # : un comportement connu ne coûte rien, un comportement supposé
    # coûte une journée. *(Sixième déduction démentie en deux jours.)*
    metaG = meta_recu(nj, ni, lon0=359.9)
    _, lonsG = geometrie_grib(metaG)
    verifier("ⓘ le franchissement de GREENWICH reste monotone — la "
             "normalisation le traverse sans accroc",
             bool(np.all(np.diff(lonsG) > 0)),
             f"{lonsG[0]:.3f} → {lonsG[-1]:.3f}")
    metaA = meta_recu(nj, ni, lon0=179.9)
    _, lonsA = geometrie_grib(metaA)
    verifier("⚠️ l'ANTIMÉRIDIEN, lui, casse la monotonie — hors domaine, "
             "mais le comportement est CONNU et non dissimulé",
             not bool(np.all(np.diff(lonsA) > 0)),
             f"{lonsA[0]:.3f} → {lonsA[-1]:.3f}")

    print("\n── 3. ⚠️ Les latitudes DÉCROISSENT (jScansPositively = 0) ──")
    verifier("l'axe reçu décroît du nord vers le sud",
             float(lats_recu[0]) > float(lats_recu[-1]),
             f"{lats_recu[0]:.3f} → {lats_recu[-1]:.3f}")
    verifier("⚠️ et la formule ne suppose PAS le sens : jScan = 1 croît",
             float(geometrie_grib(meta_recu(nj, ni, jscan=1))[0][0])
             < float(geometrie_grib(meta_recu(nj, ni, jscan=1))[0][-1]))

    print("\n── 4. ⚠️ Parité colonnes ↔ grille : le MÊME point ──")
    params = params_actifs()
    lats_c, lons_c = lats_recu[2:9], lons_recu[3:17]
    zsol = np.full((len(lats_c), len(lons_c)), 800.0, dtype=np.float32)
    balises = [dict(id="B1", lat=float(lats_c[1]), lon=float(lons_c[2]),
                    nom="essai", source="", position_suspecte=False),
               dict(id="B2", lat=float(lats_c[5]), lon=float(lons_c[11]),
                    nom="essai2", source="", position_suspecte=False)]
    ji = [(1, 2), (5, 11)]
    g = GrillePI("2026-08-10T16:00:00Z", params, lats_c, lons_c, zsol)
    c = ColonnesPI("2026-08-10T16:00:00Z", params, balises, ji)
    # Un champ dont les valeurs restent lisibles en float16.
    aligne = (coupe % 100).astype(np.float64)
    for p in params:
        g.poser(p, 100, 15, aligne)
        c.poser_depuis_champ(p, 100, 15, aligne)
    kp, kn, km = g.i_param["u"], g.i_niveau[100], g.i_min[15]
    verifier("la colonne d'une balise vaut la maille de la grille sous elle",
             float(c.donnees[kp, kn, km, 0]) == float(g.donnees[kp, kn, km, 1, 2])
             and float(c.donnees[kp, kn, km, 1]) == float(g.donnees[kp, kn, km, 5, 11]),
             "⚠️ s'ils divergeaient, le sondage et la carte donneraient "
             "deux vents différents au même endroit")
    verifier("une balise hors fenêtre donne NaN, pas la valeur du bord",
             np.isnan(float(ColonnesPI("r", params, balises[:1], [None])
                            .donnees[0, 0, 0, 0])))

    print("\n── 5. ⚠️ Un trou reste un trou ──")
    g2 = GrillePI("2026-08-10T16:00:00Z", params, lats_c, lons_c, zsol)
    for p in params:
        for m in ECHEANCES_MIN:
            g2.poser(p, 20, m, aligne)
    par_niveau = g2.remplissage_par_niveau()
    verifier("un niveau non posé reste VIDE (0 %), il n'est pas comblé",
             par_niveau[100] == 0.0 and par_niveau[20] == 1.0,
             f"20 m = {par_niveau[20]}, 100 m = {par_niveau[100]}")
    verifier("⚠️ le remplissage est publié PAR NIVEAU, pas seulement "
             "globalement — sinon « il manque quelque chose » ne dit pas quoi",
             set(par_niveau) == set(NIVEAUX_PI))
    verifier("le manifeste porte le remplissage par niveau",
             "remplissage_par_niveau" in g2.manifeste())

    # ⚠️ CE BLOC VIENT D'UN VRAI RUN. Le premier passage réel (16 Z,
    # 10/08) a obtenu 300/300 champs et annoncé **98,43 %** de
    # remplissage. Ce n'était pas un trou : 125/127 = 0,98425. Deux des
    # 127 « balises » sont des points de RADIOSONDAGE, hors domaine par
    # construction — ils ne pourront JAMAIS être servis.
    # Un taux qui ne peut pas atteindre 100 % est un taux qu'on apprend à
    # ignorer, et le jour où il tomberait pour une vraie raison personne
    # ne verrait la différence.
    c2 = ColonnesPI("2026-08-10T16:00:00Z", params,
                    balises + [dict(id="RS-06610", lat=48.0, lon=2.0,
                                    nom="radiosondage", source="radiosondage",
                                    position_suspecte=False)],
                    ji + [None])
    for p in params:
        for niveau in NIVEAUX_PI:
            for m in ECHEANCES_MIN:
                c2.poser_depuis_champ(p, niveau, m, aligne)
    verifier("⚠️ un run COMPLET annonce 100 %, pas 98,43 % : le taux se "
             "calcule sur les balises SERVABLES",
             c2.remplissage_par_parametre()["u"] == 1.0,
             f"{c2.remplissage_par_parametre()}")
    verifier("et les balises hors fenêtre sont publiées à part, nommément",
             c2.manifeste()["balises_hors_fenetre"] == ["RS-06610"])
    verifier("le manifeste dit sur quoi le taux est calculé",
             "hors domaine" in c2.manifeste()["remplissage_calcule_sur"])

    print("\n── 6. ⚠️ Des MINUTES, pas des heures ──")
    verifier("25 échéances", len(ECHEANCES_MIN) == 25)
    verifier("au pas de 15 minutes, de 0 à 360", ECHEANCES_MIN[1] == 15
             and ECHEANCES_MIN[-1] == 360)
    verifier("⚠️ l'unité est la MINUTE : l'échéance 1 h vaut 60, pas 1",
             60 in ECHEANCES_MIN and 1 not in ECHEANCES_MIN)
    inst = instants_du_run("2026-08-10T16:00:00Z")
    verifier("les instants ISO sont au quart d'heure",
             inst[0] == "2026-08-10T16:00:00Z"
             and inst[1] == "2026-08-10T16:15:00Z"
             and inst[-1] == "2026-08-10T22:00:00Z", inst[1])
    verifier("⚠️ SANS guillemets autour de l'instant (piège nº 3)",
             '"' not in inst[0])

    print("\n── 7. ⚠️ La purge ne peut pas déborder sur le définitif ──")
    leve("⛔ une clé de colonnes PI ne peut PAS entrer dans la purge",
         lambda: verifier_prefixe(
             ["agrume/pi/colonnes/2026-08-10/2026-08-10T16:00:00Z/colonnes.npz"],
             prefixe=PI.PREFIXE_GRILLE))
    leve("⛔ ni une clé du produit A d'AROME",
         lambda: verifier_prefixe(["agrume/colonnes/2026-08-10T09:00:00Z/x.npz"],
                                  prefixe=PI.PREFIXE_GRILLE))
    verifier("les clés de grille PI passent",
             verifier_prefixe(PI.cles_du_run_grille("2026-08-10T16:00:00Z"),
                              prefixe=PI.PREFIXE_GRILLE) is None or True)
    verifier("⚠️ les colonnes sont rangées PAR JOUR (24 runs/jour × 365 "
             "feraient 8 760 préfixes plats sans ça)",
             "/2026-08-10/" in cles_du_run_colonnes("2026-08-10T16:00:00Z")[0])

    print("\n── 8. Ce que PI porte, et ce qu'il ne porte pas ──")
    verifier("les 6 niveaux de PI sont TOUS dans les 25 d'AROME "
             "(aucune interpolation verticale à la jonction)",
             set(NIVEAUX_PI) <= set(NIVEAUX_H_0025))
    verifier("⚠️ le 10 m est EXCLU des niveaux où Δ est calculable : "
             "u/v d'AROME n'existent qu'à partir de 20 m dans HP1 (mesuré)",
             10 in NIVEAUX_PI and 10 not in NIVEAUX_DELTA
             and len(NIVEAUX_DELTA) == 5)
    verifier("la v0 ne demande que u et v (300 requêtes, pas 450)",
             [p["nom"] for p in params_actifs()] == ["u", "v"])
    verifier("--tke ajoute la TKE et rien d'autre",
             [p["nom"] for p in params_actifs(True)] == ["u", "v", "tke"])
    verifier("le manifeste publie les niveaux où Δ est calculable",
             list(g.manifeste()["niveaux_delta"]) == list(NIVEAUX_DELTA))
    verifier("⚠️ le manifeste écrit le SENS des latitudes en toutes lettres",
             "DÉCROISSANTES" in g.manifeste()["axes"]["sens"])
    verifier("il dit que la fenêtre est réalignée sur le GRIB reçu",
             "réalignée" in g.manifeste()["fenetre"])

    print("\n  ingestion PI :",
          "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    for e in echecs:
        print(f"    ⛔ {e}")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
