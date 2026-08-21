#!/usr/bin/env python3
"""test_geopair.py — banc de la MÉCANIQUE d'appariement, pas des métriques.

    Session 21/08/2026, lot S1.
    Conception : `claude/lot-s1-conception-appariement-21-08.md` §3.7.

═══ POURQUOI CE BANC EST À PART ═══

Le prompt du S1 demandait « un banc qui sait échouer, spécifique à la
nouvelle mécanique de proximité ELLE-MÊME, pas seulement aux métriques
de pression qui la consomment ». La raison est concrète : une erreur
dans `pres_err_med` se voit (le chiffre est absurde) ; une erreur dans
l'appariement produit des chiffres parfaitement plausibles sur les
mauvaises paires, et rien ne la signale.

═══ COMMENT IL PROUVE QU'IL SAIT ÉCHOUER ═══

`geopair.py` est un module NEUF : il n'y a pas de « code d'avant » à
rejouer. La preuve est donc faite autrement, et c'est le §3 ci-dessous :
pour chaque garde, le MÊME jeu de données est passé DEUX FOIS — une fois
avec la garde active, une fois avec elle désactivée par son argument —
et le banc exige que **les deux résultats diffèrent**. Un cas de test
qui donnerait le même résultat des deux côtés ne testerait rien ; le
banc le dirait.

Usage :
    python3 test_geopair.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geopair as G  # noqa: E402

OK = 0
KO = 0


def check(label: str, got, want):
    global OK, KO
    if got == want:
        OK += 1
    else:
        KO += 1
        print(f"  ❌ {label}\n       obtenu  : {got!r}\n       attendu : {want!r}")


def diff(label: str, a, b):
    """Exige que deux résultats DIFFÈRENT — c'est ce qui prouve qu'une
    garde est bien celle qui décide, et pas un hasard de géométrie."""
    global OK, KO
    if a != b:
        OK += 1
    else:
        KO += 1
        print(f"  ❌ {label}\n       les deux côtés rendent {a!r} : la garde "
              f"testée ne décide rien ici, le cas de test est faux")


# ── Géométrie de référence ────────────────────────────────────────
#
# On travaille près de 45,0 N où 1° de latitude ≈ 111,20 km et 1° de
# longitude ≈ 78,63 km. Les distances ci-dessous sont VÉRIFIÉES par
# `distance_km` au §0 plutôt que posées de tête : un banc qui suppose sa
# propre géométrie testerait la géométrie, pas l'appariement.

LAT0, LON0 = 45.0, 6.0


def pt(cle, dlat_km=0.0, dlon_km=0.0, alt=500.0, champ="dem_alt_m"):
    p = {"cle": cle,
         "lat": LAT0 + dlat_km / 111.195,
         "lon": LON0 + dlon_km / 78.63}
    if alt is not None:
        p[champ] = alt
    return p


def section(titre):
    print(f"\n── {titre}")


# ══════════════════════════════════════════════════════════════════
#  0. LA GÉOMÉTRIE DU BANC EST VÉRIFIÉE AVANT DE S'EN SERVIR
# ══════════════════════════════════════════════════════════════════

def test_geometrie():
    section("0. géométrie")
    d = G.distance_km(LAT0, LON0, pt("x", dlat_km=10)["lat"], LON0)
    check("10 km en latitude", round(d, 1), 10.0)
    d = G.distance_km(LAT0, LON0, LAT0, pt("x", dlon_km=10)["lon"])
    check("10 km en longitude", round(d, 1), 10.0)
    check("distance à soi-même", G.distance_km(LAT0, LON0, LAT0, LON0), 0.0)


# ══════════════════════════════════════════════════════════════════
#  1. LES SEPT CAS DE LA NOTE DE CONCEPTION §3.7
# ══════════════════════════════════════════════════════════════════

def test_hors_rayon():
    section("1. le plus proche est hors rayon → PAS DE LIGNE, jamais un zéro")
    cibles = [pt("obs")]
    cands = [pt("fc", dlon_km=60)]
    res, bil = G.apparier(cibles, cands, max_km=50)
    check("aucun appariement", res, {})
    check("« obs » absente du dict (pas présente à zéro)", "obs" in res, False)
    check("compté hors rayon", bil.hors_rayon, 1)
    check("compté nulle part ailleurs", bil.apparies + bil.hors_dz, 0)


def test_borne_inclusive():
    section("2. un candidat EXACTEMENT au rayon → apparié (borne inclusive)")
    cibles = [pt("obs")]
    d_exact = G.distance_km(LAT0, LON0, LAT0, pt("x", dlon_km=50)["lon"])
    res, _ = G.apparier(cibles, [pt("fc", dlon_km=50)], max_km=d_exact)
    check("au rayon pile : apparié", "obs" in res, True)
    res, _ = G.apparier(cibles, [pt("fc", dlon_km=50)],
                        max_km=d_exact - 0.001)
    check("un mètre au-delà : refusé", "obs" in res, False)
    res, _ = G.apparier(cibles, [pt("fc", dlon_km=50)],
                        max_km=d_exact + 0.001)
    check("un mètre en deçà : apparié", "obs" in res, True)


def test_plus_proche_parmi_les_eligibles():
    section("3. LE CAS QUI COMPTE — le plus proche N'EST PAS éligible")
    # `pres` est à 5 km mais 900 m plus haut ; `loin` est à 30 km et à la
    # même altitude. « Le plus proche puis filtré » ne rendrait RIEN ;
    # « le plus proche parmi les éligibles » rend `loin`.
    cibles = [pt("obs", alt=500)]
    cands = [pt("pres", dlon_km=5, alt=1400), pt("loin", dlon_km=30, alt=520)]
    res, _ = G.apparier(cibles, cands, max_km=50, max_dz_m=300)
    check("c'est le LOINTAIN éligible qui gagne", res["obs"].cle, "loin")
    check("et sa distance est publiée", round(res["obs"].km), 30)
    # Sans la garde Δz, c'est le proche non éligible qui gagnerait :
    # c'est ce qui prouve que ce cas teste bien quelque chose.
    sans, _ = G.apparier(cibles, cands, max_km=50)
    diff("la garde Δz décide bien ici",
         res["obs"].cle, sans["obs"].cle)
    check("sans la garde, c'est le proche", sans["obs"].cle, "pres")


def test_departage():
    section("4. plusieurs éligibles → distance, puis |Δz|, puis la clé")
    cibles = [pt("obs", alt=500)]
    res, _ = G.apparier(cibles,
                        [pt("b", dlon_km=20, alt=500),
                         pt("a", dlon_km=10, alt=700)],
                        max_km=50, max_dz_m=300)
    check("le plus proche gagne, même moins bien calé", res["obs"].cle, "a")

    # Égalité de distance stricte (symétrie est/ouest), Δz différents.
    res, _ = G.apparier(cibles,
                        [pt("est", dlon_km=10, alt=750),
                         pt("ouest", dlon_km=-10, alt=505)],
                        max_km=50, max_dz_m=300)
    check("à distance égale, le plus petit |Δz|", res["obs"].cle, "ouest")

    # Égalité de distance ET de Δz → la clé, croissante.
    res, _ = G.apparier(cibles,
                        [pt("zzz", dlon_km=10, alt=600),
                         pt("aaa", dlon_km=-10, alt=600)],
                        max_km=50, max_dz_m=300)
    check("à égalité complète, la clé croissante", res["obs"].cle, "aaa")


def test_cible_sans_altitude():
    section("5. cible sans altitude → pas de ligne, et c'est compté")
    cibles = [pt("obs", alt=None)]
    cands = [pt("fc", dlon_km=5, alt=500)]
    res, bil = G.apparier(cibles, cands, max_km=50, max_dz_m=300)
    check("pas d'appariement", res, {})
    check("compté sans_altitude", bil.sans_altitude, 1)
    # Sans plafond vertical du tout, l'altitude ne sert plus à rien et
    # la même cible s'apparie : la garde n'est pas un refus gratuit.
    res2, _ = G.apparier(cibles, cands, max_km=50)
    check("sans plafond vertical, elle s'apparie", res2["obs"].cle, "fc")
    check("et son Δz est None, pas 0", res2["obs"].dz_m, None)


def test_plafond_altitude_absolue():
    section("6. plafond d'altitude ABSOLUE (le cas Samedan), des deux côtés")
    # Candidat le plus proche à 1 700 m : écarté même si Δz passerait.
    cibles = [pt("obs", alt=1600)]
    cands = [pt("haut", dlon_km=5, alt=1700), pt("bas", dlon_km=30, alt=1500)]
    res, bil = G.apparier(cibles, cands, max_km=50, max_dz_m=300,
                          max_alt_m=1000)
    check("cible trop haute : rien", res, {})
    check("comptée cible_trop_haute", bil.cible_trop_haute, 1)
    check("les deux candidats écartés d'emblée", bil.candidats_trop_hauts, 2)

    # Cible basse, candidat proche trop haut, candidat loin acceptable.
    cibles = [pt("obs", alt=400)]
    cands = [pt("haut", dlon_km=5, alt=1200), pt("bas", dlon_km=30, alt=450)]
    res, bil = G.apparier(cibles, cands, max_km=50, max_dz_m=300,
                          max_alt_m=1000)
    check("c'est le bas qui gagne", res["obs"].cle, "bas")
    check("le haut compté une seule fois", bil.candidats_trop_hauts, 1)
    sans, _ = G.apparier(cibles, cands, max_km=50, max_dz_m=1000)
    diff("le plafond absolu décide bien ici", res["obs"].cle, sans["obs"].cle)


def test_determinisme():
    section("7. déterminisme — un rejeu doit être un rejeu")
    cibles = [pt(f"obs{i}", dlat_km=i * 3, alt=500) for i in range(12)]
    cands = [pt(f"fc{i}", dlon_km=(i % 5) * 7, dlat_km=i * 2, alt=500 + i)
             for i in range(9)]
    a, _ = G.apparier(cibles, cands, max_km=50, max_dz_m=300, max_alt_m=1000)
    b, _ = G.apparier(list(reversed(cibles)), list(reversed(cands)),
                      max_km=50, max_dz_m=300, max_alt_m=1000)
    check("même résultat quel que soit l'ordre d'entrée", a, b)


# ══════════════════════════════════════════════════════════════════
#  2. CE QUE LE BILAN DOIT SAVOIR DIRE
# ══════════════════════════════════════════════════════════════════

def test_bilan():
    section("8. le bilan nomme chaque refus")
    cibles = [pt("dedans", dlon_km=1, alt=500),
              pt("loin", dlon_km=200, alt=500),
              pt("haute", dlon_km=1, alt=2000),
              pt("dz", dlon_km=1, alt=900),
              pt("muette", dlon_km=1, alt=None)]
    cands = [pt("fc", alt=500)]
    res, bil = G.apparier(cibles, cands, max_km=50, max_dz_m=300,
                          max_alt_m=1000)
    check("une seule appariée", sorted(res), ["dedans"])
    check("apparies", bil.apparies, 1)
    check("hors_rayon", bil.hors_rayon, 1)
    check("cible_trop_haute", bil.cible_trop_haute, 1)
    check("hors_dz", bil.hors_dz, 1)
    check("sans_altitude", bil.sans_altitude, 1)
    check("le résumé est imprimable", isinstance(bil.resume(), str), True)
    check("aucune cible perdue en route",
          bil.apparies + bil.hors_rayon + bil.cible_trop_haute
          + bil.hors_dz + bil.sans_altitude + bil.aucun_candidat, len(cibles))


def test_aucun_candidat():
    section("9. zéro candidat → « aucun_candidat », pas « hors rayon »")
    res, bil = G.apparier([pt("obs")], [], max_km=50)
    check("rien", res, {})
    check("motif juste", (bil.aucun_candidat, bil.hors_rayon), (1, 0))


def test_altitude_dem_prioritaire():
    section("10. `dem_alt_m` prime sur `elev` — une seule échelle")
    # La même balise avec deux altitudes contradictoires : c'est
    # `dem_alt_m` qui décide, parce que c'est la seule que les DEUX
    # populations aient sur la même échelle (tuiles Terrarium, S0.2).
    cible = pt("obs", alt=500)
    cible["elev"] = 2500.0
    res, _ = G.apparier([cible], [pt("fc", dlon_km=5, alt=520)],
                        max_km=50, max_dz_m=300, max_alt_m=1000)
    check("appariée sur dem_alt_m (500), pas sur elev (2500)",
          "obs" in res, True)
    check("Δz calculé sur dem_alt_m", res["obs"].dz_m, 20.0)
    # Et sans `dem_alt_m`, `elev` reprend la main.
    cible2 = {"cle": "obs", "lat": cible["lat"], "lon": cible["lon"],
              "elev": 2500.0}
    res2, _ = G.apparier([cible2], [pt("fc", dlon_km=5, alt=520)],
                         max_km=50, max_dz_m=300, max_alt_m=1000)
    check("sans dem_alt_m, `elev` décide (et refuse)", res2, {})


def test_plusieurs_cibles_un_candidat():
    section("11. un point de prévision peut servir plusieurs observations")
    cibles = [pt("a", dlon_km=2, alt=500), pt("b", dlon_km=-3, alt=510),
              pt("c", dlat_km=4, alt=505)]
    res, bil = G.apparier(cibles, [pt("fc", alt=500)],
                          max_km=50, max_dz_m=300, max_alt_m=1000)
    check("les trois sont appariées", sorted(res), ["a", "b", "c"])
    check("toutes sur le même point", {v.cle for v in res.values()}, {"fc"})
    check("bilan cohérent", bil.apparies, 3)
    # ⚠️ Ces trois lignes sont CORRÉLÉES. Le banc ne peut pas
    # l'empêcher — c'est une décision d'agrégation (note de conception,
    # arbitrage n°1). Il le CONSTATE, pour que personne ne découvre le
    # fait en lisant un intervalle de confiance trop serré.


def main() -> int:
    for f in (test_geometrie, test_hors_rayon, test_borne_inclusive,
              test_plus_proche_parmi_les_eligibles, test_departage,
              test_cible_sans_altitude, test_plafond_altitude_absolue,
              test_determinisme, test_bilan, test_aucun_candidat,
              test_altitude_dem_prioritaire, test_plusieurs_cibles_un_candidat):
        f()
    print(f"\n{OK} assertions vertes, {KO} rouges.")
    return 1 if KO else 0


if __name__ == "__main__":
    sys.exit(main())
