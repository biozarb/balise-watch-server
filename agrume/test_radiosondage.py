#!/usr/bin/env python3
"""
test_radiosondage.py — banc de la confrontation au ballon.

    python3 agrume/test_radiosondage.py
    python3 agrume/test_radiosondage.py --reseau   # + un vrai sondage

⚠️ CE QUE CE BANC PROTÈGE, ET IL EST NÉ D'UN DÉFAUT RÉEL.

  1. **L'UNITÉ SUPPOSÉE.** Le 10/08, `index.js` rangeait la colonne de
     vitesse de Wyoming dans `speedKt` en croyant à des nœuds. Le fichier
     dit `m/s`, sur la ligne d'unités que le parseur sautait : les vents
     affichés aux pilotes valaient 0,514 fois la réalité, pendant des
     semaines, sans qu'aucun test ne s'allume. Ce banc vérifie que
     l'unité est LUE, que les deux unités connues convertissent juste, et
     surtout qu'un en-tête inconnu fait ÉCHOUER le parsing.
  2. **Le mélange par l'angle.** Interpoler entre 350° et 010° en degrés
     donne 180°, l'inverse exact. Comme dans `test_profil.py`, et pour la
     même raison — sauf qu'ici c'est le SONDAGE qu'on interpole.
  3. **La comparaison hors sujet.** Comparer une échéance voisine de
     l'heure du lâcher ferait passer une erreur d'horodatage pour un
     défaut du modèle.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import radiosondage as RS  # noqa: E402

echecs = []


def verifier(nom, condition, detail=""):
    print(f"  {'✓' if condition else '✗'} {nom}" + (f"   {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


# ── Extrait RÉEL de Payerne, run 00 Z du 10/08/2026 ───────────────────
# ⚠️ Figé exprès, en-tête compris : c'est l'en-tête qui porte l'unité, et
# c'est lui qu'il faut protéger d'une régression. Les valeurs viennent du
# fichier servi ce jour-là, pas d'une invention.
FIXTURE = """<HTML>
<H2>06610 LSMP Payerne Observations at 00Z 10 Aug 2026</H2>
<PRE>
-----------------------------------------------------------------------------
   PRES   HGHT   TEMP   DWPT   RELH   MIXR   DRCT   SPED   THTA   THTE   THTV
    hPa      m      C      C      %   g/kg    deg    m/s      K      K      K
-----------------------------------------------------------------------------
  960.6    491   19.6   14.4     72  10.81    163    0.8  296.1  327.5  298.1
  925.0    822   24.1    9.3     39   7.95    237    6.5  304.0  328.1  305.4
  850.0   1555   20.2    7.9     45   7.86    222    7.7  307.3  331.4  308.7
  700.0   3191    7.6   -3.0     47   4.38    260    7.3  310.9  324.8  311.7
  500.0   5860  -10.3  -39.3      7   0.25    251    9.6  320.4  321.4  320.4
  400.0   7543  -21.0  -34.9     28   0.50    261   17.7  327.6  329.5  327.7
  300.0   9601  -36.8  -57.2     10   0.06    244   21.2  333.3  333.6  333.3
  250.0  10834  -47.5  -55.6     39   0.08    239   22.8  335.3  335.6  335.3
  200.0  12272  -58.0  -62.8     54   0.04    253   26.0  340.8  341.0  340.8
  150.0  14111  -54.3  -81.7      2   0.00    232   25.8  376.4  376.4  376.4
  100.0  16699  -56.1  -84.6      2   0.00    257   10.4  419.1  419.1  419.1
</PRE>
</HTML>"""

FIXTURE_NOEUDS = (FIXTURE.replace("    m/s", "   knot")
                  .replace("   SPED", "   SKNT"))
FIXTURE_INCONNUE = FIXTURE.replace("    m/s", "   ????")


def sondage_synthetique(dir_deg, force_ms, z0=500, z1=8000, pas=100):
    """Un sondage à vent constant — le seul cas où la dérive se calcule
    à la main, donc le seul qui vaille comme test."""
    n = []
    for z in range(z0, z1 + 1, pas):
        u = -force_ms * math.sin(math.radians(dir_deg))
        v = -force_ms * math.cos(math.radians(dir_deg))
        n.append(dict(pHPa=1000.0, altitudeM=float(z), tC=10.0, tdC=0.0,
                      hr=50.0, directionDeg=float(dir_deg),
                      vitesseMs=float(force_ms), u=u, v=v))
    return n


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--reseau", action="store_true",
                   help="télécharge en plus un sondage réel")
    a = p.parse_args(argv)

    print("\n── 1. L'UNITÉ EST LUE, JAMAIS SUPPOSÉE ──")
    n = RS.parse_wyoming(FIXTURE)
    verifier("le bloc PRE est parsé", len(n) == 11, f"{len(n)} niveaux")
    p850 = next(x for x in n if x["pHPa"] == 850.0)
    verifier("SPED en m/s est pris pour des m/s",
             abs(p850["vitesseMs"] - 7.7) < 1e-6,
             f"{p850['vitesseMs']} m/s = {p850['vitesseMs'] * 3.6:.1f} km/h")
    verifier("⚠️ ce qu'affichait le défaut du 10/08 était bien la moitié",
             abs(p850["vitesseMs"] * 1.852 - 14.26) < 0.05,
             f"14,3 km/h affichés au lieu de {p850['vitesseMs'] * 3.6:.1f}")

    nk = RS.parse_wyoming(FIXTURE_NOEUDS)
    p850k = next(x for x in nk if x["pHPa"] == 850.0)
    verifier("SKNT en nœuds est converti (× 0,514)",
             abs(p850k["vitesseMs"] - 7.7 * 0.514444) < 1e-4,
             f"{p850k['vitesseMs']:.3f} m/s")

    refuse = False
    try:
        RS.parse_wyoming(FIXTURE_INCONNUE)
    except RS.Abort:
        refuse = True
    verifier("⚠️ une unité INCONNUE fait échouer le parsing "
             "(pas de conversion au hasard)", refuse)

    print("\n── 2. LES COMPOSANTES, JAMAIS L'ANGLE ──")
    # Vent d'ouest (270°) : il va VERS l'est, donc u > 0 et v ≈ 0.
    ouest = next(x for x in RS.parse_wyoming(FIXTURE) if x["pHPa"] == 500.0)
    u_o = -9.6 * math.sin(math.radians(251))
    verifier("convention météo respectée (u = −V·sin(dir))",
             abs(ouest["u"] - u_o) < 1e-6, f"u = {ouest['u']:.2f} m/s")

    # 350° puis 010° : la moyenne en degrés vaudrait 180°, l'inverse.
    croise = [dict(altitudeM=1000.0, u=-10 * math.sin(math.radians(350)),
                   v=-10 * math.cos(math.radians(350)), tC=0.0, hr=50.0),
              dict(altitudeM=2000.0, u=-10 * math.sin(math.radians(10)),
                   v=-10 * math.cos(math.radians(10)), tC=0.0, hr=50.0)]
    milieu = RS.interpoler(croise, 1500.0)
    dir_milieu = (270 - math.degrees(math.atan2(milieu["v"], milieu["u"]))) % 360
    verifier("interpolé entre 350° et 010° → ~0°, pas 180°",
             min(dir_milieu, 360 - dir_milieu) < 1.0,
             f"{dir_milieu:.1f}°")

    print("\n── 3. LA DÉRIVE, CALCULABLE À LA MAIN ──")
    # 10 m/s constant, ascension 5 m/s, 500 → 5500 m : 5000 m de montée en
    # 1000 s, donc 10 000 m de dérive. Exactement 10 km.
    trace = RS.derive(sondage_synthetique(270, 10.0), ascension_ms=5.0)
    d = RS.derive_a(trace, 5500.0)
    verifier("10 m/s constant, w = 5 m/s, 5 000 m de montée → 10,0 km",
             abs(d - 10.0) < 0.05, f"{d} km")
    lent = RS.derive(sondage_synthetique(270, 10.0), ascension_ms=4.0)
    verifier("⚠️ une ascension supposée plus lente dérive PLUS loin "
             "(le chiffre dépend d'une hypothèse)",
             RS.derive_a(lent, 5500.0) > d,
             f"{RS.derive_a(lent, 5500.0)} km à w = 4 m/s")

    print("\n── 4. ON NE COMPARE QUE L'ÉCHÉANCE QUI TOMBE JUSTE ──")
    runs = dict(RS.runs_pour("2026-08-10", "12", max_heures=24))
    verifier("le run 00 Z donne l'échéance 12 h",
             runs.get("2026-08-10T00:00:00Z") == 12)
    verifier("le run 12 Z donne l'échéance 0 h (analyse)",
             runs.get("2026-08-10T12:00:00Z") == 0)
    verifier("aucun run hors du cycle 3 h n'est proposé",
             all(int(r[11:13]) % 3 == 0 for r in runs))
    verifier("la veille 12 Z donne 24 h, et rien au-delà",
             runs.get("2026-08-09T12:00:00Z") == 24 and max(runs.values()) == 24)

    print("\n── 5. LA CONFRONTATION ──")
    # Profil AGRUME synthétique : même vent que le ballon PARTOUT sauf
    # dans la zone de mélange, décalée de 3 m/s. Le découpage par source
    # doit isoler ça — c'est toute la raison d'être du découpage.
    ballon = sondage_synthetique(270, 10.0, z0=400, z1=8000, pas=50)
    profil = []
    for z, src in ((1000, "hauteur"), (1500, "hauteur"),
                   (2500, "melange"), (3000, "melange"),
                   (5000, "isobare"), (6000, "isobare")):
        u = 10.0 + (3.0 if src == "melange" else 0.0)
        profil.append(dict(altitudeM=float(z), source=src, poidsHauteur=0.5,
                           u=u, v=0.0, t=10.0, hr=50.0))
    reponse = dict(run="2026-08-10T00:00:00Z", echeanceH=12,
                   solModeleM=dict(grille_0025=500.0), profil=profil)
    c = RS.confronter(reponse, ballon)
    par = {b["libelle"]: b for b in c["parSource"]}
    verifier("les 6 points sont comparables", c["nPointsCompares"] == 6)
    verifier("tranche « hauteur seule » : écart nul",
             par["hauteur seule"]["ecartVentMs"]["max"] < 1e-6)
    verifier("tranche « isobares seules » : écart nul",
             par["isobares seules"]["ecartVentMs"]["max"] < 1e-6)
    verifier("⚠️ le MÉLANGE est isolé, et son écart ressort à 3 m/s",
             abs(par["MÉLANGE (raccord)"]["ecartVentMs"]["mediane"] - 3.0) < 1e-3,
             "c'est exactement ce que le découpage par source doit voir")
    verifier("le biais de vitesse est signé (AGRUME − ballon)",
             par["MÉLANGE (raccord)"]["biaisVitesseMs"] > 0)
    verifier("un point au-dessus du sondage n'est pas extrapolé",
             RS.interpoler(ballon, 9000.0) is None)

    print("\n── 6. LA TABLE DES STATIONS DIT CE QU'ELLE SAIT ──")
    cuneo = RS.station("16117")
    verifier("⚠️ Cuneo est marquée INACTIVE, avec la mesure qui le dit",
             not cuneo["active"] and "404" in cuneo["mesure"])
    verifier("les stations actives ont une altitude de station",
             all(s["sol_station_m"] for s in RS.STATIONS if s["active"]))

    print("\n── 7. L'AXE : les radiosondages passent EN DERNIER ──")
    from colonnes import balises_du_domaine
    axe = balises_du_domaine([
        dict(id="999", lat=45.5, lon=6.5, name="balise", source="pioupiou"),
        dict(id="RS-06610", lat=46.813, lon=6.943, name="Payerne",
             source="radiosondage"),
        dict(id="1377", lat=45.5, lon=6.9, name="balise", source="pioupiou")])
    verifier("le point hors domaine entre par sa `source`, pas sa position",
             len(axe) == 3, [b["id"] for b in axe])
    verifier("⚠️ il se range EN DERNIER, donc ne décale aucune balise",
             axe[-1]["id"] == "RS-06610")

    if a.reseau:
        print("\n── 8. UN VRAI SONDAGE (réseau) ──")
        try:
            st = RS.station("06610")
            txt = RS.telecharger(st["wmo"], "2026-08-10", "00")
            vrai = RS.parse_wyoming(txt)
            verifier("Payerne répond et se parse", len(vrai) > 100,
                     f"{len(vrai)} niveaux")
            verifier("le premier niveau est au sol de la station "
                     "(± 30 m)",
                     abs(vrai[0]["altitudeM"] - st["sol_station_m"]) < 30,
                     f"{vrai[0]['altitudeM']:.0f} m contre "
                     f"{st['sol_station_m']} m")
            t = RS.derive(vrai)
            print(f"     ⓘ dérive estimée : {RS.derive_a(t, 2000)} km à "
                  f"2 000 m · {RS.derive_a(t, 4000)} km à 4 000 · "
                  f"{RS.derive_a(t, 6000)} km à 6 000")
        except RS.Abort as e:
            verifier("sondage réel accessible", False, str(e))

    print("\n  radiosondage :", "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
