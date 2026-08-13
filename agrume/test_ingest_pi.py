#!/usr/bin/env python3
"""
test_ingest_pi.py — banc de l'ingestion AROME-PI (étape 8 bis), HORS-LIGNE.

    python3 agrume/test_ingest_pi.py

⚠️ CE QUE CE BANC PROTÈGE.

L'ingestion PI n'a qu'un seul client : le composite de l'étape 9, qui
calcule `Δ = PI − AROME` point à point. **Une erreur ici ne produit pas
une panne, elle produit un delta.** Et un delta faux est lisse,
plausible, tracé sans broncher — c'est exactement le genre de défaut que
ce projet met des jours à voir. Dix façons de casser en silence, une par
section — et les trois dernières ne viennent pas d'une relecture, elles
viennent de runs réels qui ont mal tourné :

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
  8. **Un niveau qu'on croit commun.** Les 6 niveaux de PI sont dans les
     25 d'AROME, mais `u`/`v` d'AROME n'existent qu'à partir de 20 m.
  9. **⚠️ Un run « publié » qui n'est pas complet.** MESURÉ : à 17:23:51
     UTC le run 17 Z répondait au `DescribeCoverage` et servait 2 de ses
     5 échéances sondées. Archiver ça, c'est perdre 76 % d'un run pour
     toujours — et le produit serait dentelé, pas franchement tronqué.
 10. **⚠️ Un 502 pris pour un refus.** MESURÉ : le premier run écrit sur
     R2 a rendu 297 champs sur 300, trois `HTTP 502 Bad Gateway` sans
     rapport entre eux. Un hoquet de passerelle laissait trois trous
     PERMANENTS dans une archive irremplaçable.

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

    print("\n── 9. ⚠️⚠️ « Publié » ne veut pas dire « complet » ──")
    # MESURÉ le 10/08 à 17:23:51 UTC : le run 17 Z répondait au
    # DescribeCoverage et servait ses échéances 0 et 90 min ; les
    # échéances 180, 270 et 360 min n'existaient pas. Les runs 16 Z et
    # 15 Z étaient complets. **PI publie ses échéances au fil de l'eau.**
    # Sans le contrôle ci-dessous, l'ingestion archivait un run à 24 %
    # dans une archive DÉFINITIVE, et l'index disait « fait ».
    import ingest_pi as IP

    class PortailFactice:
        """⚠️ Le faux portail reproduit le comportement MESURÉ, pas celui
        qu'on aurait supposé : un run peut répondre `existe` et n'avoir
        que ses premières échéances."""

        def __init__(self, publies, complets):
            self.publies, self.complets = set(publies), set(complets)
            self.vus = []

        def existe(self, champ, run):
            self.vus.append(("existe", run))
            return run in self.publies

        def get_coverage(self, champ, run, instant, niveau, domaine, **kw):
            self.vus.append(("get", run, instant))
            if run in self.complets:
                return b"x" * 8000
            raise IP.CouvertureAbsente("échéance absente", code=404)

        def bilan(self):
            return "factice"

    maintenant = __import__("datetime").datetime(2026, 8, 10, 17, 23, 51,
                                                 tzinfo=__import__("datetime").timezone.utc)
    p1 = PortailFactice(publies=["2026-08-10T17:00:00Z", "2026-08-10T16:00:00Z"],
                        complets=["2026-08-10T16:00:00Z"])
    run, recul = IP.dernier_run_utile(p1, "CHAMP", deja=set(),
                                      maintenant=maintenant, journal=lambda m: None)
    verifier("⛔ un run publié mais INCOMPLET est écarté, on prend le "
             "précédent", run == "2026-08-10T16:00:00Z" and recul == 1, str(run))

    p2 = PortailFactice(publies=["2026-08-10T17:00:00Z", "2026-08-10T16:00:00Z"],
                        complets=["2026-08-10T16:00:00Z"])
    run2, _ = IP.dernier_run_utile(p2, "CHAMP", deja={"2026-08-10T16:00:00Z"},
                                   maintenant=maintenant, journal=lambda m: None)
    verifier("rien à faire si le dernier run complet est déjà archivé",
             run2 is None)
    verifier("⚠️ et on s'arrête là : aucune requête sur les heures "
             "antérieures (le quota n'est pas gratuit)",
             all(v[1] >= "2026-08-10T16:00:00Z" for v in p2.vus), str(p2.vus))

    p3 = PortailFactice(publies=["2026-08-10T17:00:00Z"],
                        complets=["2026-08-10T17:00:00Z"])
    run3, recul3 = IP.dernier_run_utile(p3, "CHAMP", deja=set(),
                                        maintenant=maintenant,
                                        journal=lambda m: None)
    verifier("un run frais ET complet est pris tout de suite",
             run3 == "2026-08-10T17:00:00Z" and recul3 == 0)
    verifier("⚠️ la sonde porte sur la DERNIÈRE échéance (360 min), celle "
             "qui arrive en dernier",
             any(v[0] == "get" and v[2].endswith("T23:00:00Z") for v in p3.vus),
             str(p3.vus[-1]))

    print("\n── 10. ⚠️⚠️ Un 502 est un hoquet, pas un refus ──")
    # MESURÉ : le premier run PI écrit sur R2 a rendu 297 champs sur 300.
    # Trois `HTTP 502 Bad Gateway`, à trois niveaux et trois échéances
    # sans rapport entre eux. Le client les traitait comme définitifs —
    # et les colonnes PI sont DÉFINITIVES, donc c'étaient trois trous
    # permanents dans une archive irremplaçable.
    import urllib.error as _ue
    import urllib.request as _ur

    import portail as PO

    vrai_urlopen = _ur.urlopen

    class _Reponse:
        def __init__(self, corps):
            self.corps = corps

        def read(self):
            return self.corps

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def faux_urlopen(codes, corps=b"G" * 9000):
        suite = list(codes)

        def _ouvrir(req, timeout=None):
            if suite:
                code = suite.pop(0)
                raise _ue.HTTPError(req.full_url, code, "boum", {},
                                    __import__("io").BytesIO(b"<html>502</html>"))
            return _Reponse(corps)
        return _ouvrir

    p = PO.Portail(PO.SERVICE_AROMEPI, "0025", cle="factice", journal=None)
    try:
        _ur.urlopen = faux_urlopen([502])
        corps = p._http("https://exemple/x")
        verifier("⛔ un 502 est RETENTÉ, et la requête aboutit",
                 len(corps) == 9000)
        verifier("et il est compté comme retenté, pas comme un échec",
                 p.compteur["http_502_retente"] == 1,
                 str(dict(p.compteur)))

        _ur.urlopen = faux_urlopen([503, 504])
        p2 = PO.Portail(PO.SERVICE_AROMEPI, "0025", cle="factice", journal=None)
        verifier("503 et 504 aussi — même famille de passerelle",
                 len(p2._http("https://exemple/x")) == 9000)

        # ⚠️ Mais un 502 PERMANENT doit finir par lever : un client qui
        # retenterait indéfiniment ressemblerait à un client qui marche.
        _ur.urlopen = faux_urlopen([502, 502, 502, 502, 502, 502])
        p3 = PO.Portail(PO.SERVICE_AROMEPI, "0025", cle="factice", journal=None)
        try:
            p3._http("https://exemple/x", essais=3)
            verifier("⚠️ un 502 permanent finit par lever", False,
                     "n'a rien levé")
        except PO.ErreurPortail:
            verifier("⚠️ un 502 permanent finit par lever, il ne boucle pas",
                     True)

        # ⓘ Et le 404 `NoSuchCoverage`, lui, n'est PAS retenté : c'est une
        # réponse, pas un incident. Le retenter brûlerait du quota pour
        # apprendre trois fois la même chose.
        def _404(req, timeout=None):
            raise _ue.HTTPError(
                req.full_url, 404, "nope", {},
                __import__("io").BytesIO(
                    b'<ExceptionReport><Exception exceptionCode="NoSuchCoverage">'
                    b'<ExceptionText>absent</ExceptionText></Exception></ExceptionReport>'))
        _ur.urlopen = _404
        p4 = PO.Portail(PO.SERVICE_AROMEPI, "0025", cle="factice", journal=None)
        try:
            p4._http("https://exemple/x", essais=4)
            verifier("ⓘ un NoSuchCoverage lève tout de suite", False)
        except PO.CouvertureAbsente:
            verifier("ⓘ un NoSuchCoverage lève TOUT DE SUITE, sans retenter "
                     "(c'est une réponse, pas un incident)",
                     p4.compteur["requetes"] == 1, str(p4.compteur["requetes"]))
    finally:
        _ur.urlopen = vrai_urlopen

    # ══════════════════════════════════════════════════════════════════
    #  11. LA PURGE DE L'INDEX PI — et la fratrie qui l'a cassée
    # ══════════════════════════════════════════════════════════════════
    print("\n── 11. ⛔ purge de l'index PI, et l'arité de index_apres ──")

    # ⚠️ CE QUI EST ARRIVÉ, ET POURQUOI AUCUN BANC NE L'A VU. Le 12/08,
    # `grille.index_apres` a gagné un paramètre POSITIONNEL (`domaine`),
    # pour compter la rétention par domaine. Deux sites d'appel ne l'ont
    # jamais reçu : `ingest_pi.purger` et `sonde_r2`. Résultat mesuré
    # dans le journal du VPS le 13/08, à CHAQUE run de PI :
    #     ⚠️ grille NON écrite (TypeError: index_apres() missing 1
    #        required positional argument: 'cles')
    # La grille partait quand même sur R2 — mais l'index, non. Or
    # `ListObjects` est hors de portée du jeton ordinaire : un objet
    # hors index est INVISIBLE, donc définitivement perdu. Une fuite,
    # pas un déchet. C'est la fratrie décrite dans BUGS.md le 13/08 :
    # « quand une fonction à paramètres change, grepper TOUS ses appels ».
    import json as _json
    import ingest_pi as IP  # noqa: PLC0415
    from pi import CLE_INDEX_GRILLE as _CLE, DOMAINE_INDEX as _DOM

    class _FauxStore:
        def __init__(self):
            self.objets, self.supprimes = {}, []
        def get_json(self, k):
            return _json.loads(self.objets[k]) if k in self.objets else None
        def put(self, k, b, **kw):
            self.objets[k] = b.decode() if isinstance(b, bytes) else b
        def delete(self, k):
            self.supprimes.append(k); return True

    _st = _FauxStore()
    _runs = ["2026-08-13T0%d:00:00Z" % h for h in (1, 2, 3, 4, 5)]
    try:
        for _r in _runs:
            IP.purger(_st, _r, ["agrume/pi/grille/%s/grille.npz" % _r],
                      journal=lambda *a, **k: None)
        _idx = _json.loads(_st.objets[_CLE])
        verifier("⛔ `purger()` tourne de bout en bout — c'est CE "
                 "TypeError qui a fait perdre l'index PI du 12 au 13/08",
                 True)
        verifier("la rétention de 3 runs tient",
                 len(_idx["runs"]) == 3, str(len(_idx["runs"])))
        verifier("… et chaque entrée porte son domaine (sans lui, "
                 "`index_apres` l'enverrait à la suppression au run "
                 "suivant, comme une entrée d'ancien format)",
                 all(e.get("domaine") == _DOM for e in _idx["runs"]),
                 str(sorted({e.get("domaine") for e in _idx["runs"]})))
        verifier("les deux plus vieux runs partent, et EUX SEULS",
                 _st.supprimes == ["agrume/pi/grille/%s/grille.npz" % r
                                   for r in _runs[:2]],
                 str(_st.supprimes))
    except TypeError as exc:
        verifier(f"⛔ `purger()` lève encore : {exc}", False)

    # ⛔ ET LE FRÈRE SUIVANT, MÉCANIQUEMENT. Un banc qui ne teste qu'UN
    # site d'appel ne protège que celui-là ; c'est justement ce qui a
    # manqué. On compte donc les arguments de TOUS les appels à
    # `index_apres` du paquet, et on les compare à la signature réelle.
    import ast as _ast, inspect as _inspect, glob as _glob
    from grille import index_apres as _ia
    _requis = [n for n, prm in _inspect.signature(_ia).parameters.items()
               if prm.default is _inspect.Parameter.empty]
    _mauvais = []
    for _f in sorted(_glob.glob(os.path.join(os.path.dirname(
            os.path.abspath(__file__)), "*.py"))):
        if os.path.basename(_f).startswith("test_"):
            continue
        for _n in _ast.walk(_ast.parse(open(_f, encoding="utf-8").read())):
            if (isinstance(_n, _ast.Call)
                    and isinstance(_n.func, _ast.Name)
                    and _n.func.id == "index_apres"):
                _fournis = len(_n.args) + len(
                    [k for k in _n.keywords if k.arg in _requis])
                if _fournis != len(_requis):
                    _mauvais.append("%s:%d (%d arg. pour %d requis)"
                                    % (os.path.basename(_f), _n.lineno,
                                       _fournis, len(_requis)))
    verifier("⛔ tous les appels à `index_apres` du paquet ont le bon "
             "nombre d'arguments requis (%s)" % ", ".join(_requis),
             not _mauvais, " · ".join(_mauvais))

    print("\n  ingestion PI :",
          "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    for e in echecs:
        print(f"    ⛔ {e}")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
