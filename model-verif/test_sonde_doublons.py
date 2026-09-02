#!/usr/bin/env python3
"""test_sonde_doublons.py — banc de la DÉDUPLICATION (lot L16).

⛔ CE QUE CE BANC EXISTE POUR ATTRAPER. Cette sonde décide de RETIRER
des balise-jours du classement. Les deux fautes qu'on craint sont
symétriques et toutes deux silencieuses :

  · le FAUX POSITIF — deux vraies balises voisines déclarées doublon.
    On jette alors une observation réelle, et la case perd une station
    qu'elle avait le droit de compter. Rien ne rougit : il y a
    simplement un peu moins de données.
  · le FAUX NÉGATIF — un doublon manqué parce que les deux
    référentiels ne s'accordent pas sur la coordonnée. Le double
    comptage reste en place, et le rapport annonce « traité ».

Et une troisième, plus sournoise : un résultat NON REPRODUCTIBLE. Si le
représentant d'une composante dépend de l'ordre dans lequel les paires
sont arrivées, deux exécutions rendent deux classements différents sans
qu'aucune donnée n'ait bougé.

  A. LE GRAPHE           — huit paires fabriquées, quatre verdicts
                           connus d'avance : doublons, vrais voisins,
                           même point incompatible, indécidable.
  B. LA TRANSITIVITÉ     — A≡B et B≡C font UNE balise, pas deux paires.
  C. LA RÈGLE            — chaque critère tranche, dans l'ordre, et
                           `agrume` passe avant le nombre de modèles.
  D. LA REPRODUCTIBILITÉ — mélanger l'ordre d'entrée ne change rien.
  E. LA PREUVE NOMINALE  — un doublon sans suffixe commun est trouvé
                           quand même ; un voisin avec suffixe commun
                           n'est pas jeté.
  F. LES SEUILS          — `verdict_paire` aux bornes exactes.
  G. ⭐ LE DÉGÂT         — une case à deux vraies balises et un doublon
                           est publiée AVANT et disparaît APRÈS. C'est
                           le dommage `MIN_STATIONS_ZONE = 3`, démontré
                           sur `_case_rows` lui-même.

⚠️ LES FABRIQUES DE JOURNÉES VIENNENT DU BANC DU LOT L6, importées et
pas recopiées. Les deux sondes lisent les MÊMES archives par les MÊMES
fonctions ; deux fabriques « équivalentes » divergeraient un jour, et
c'est le banc qui mentirait en premier.

Aucun `random` : `scoring._XorShift`, graine explicite.

    python3 test_sonde_doublons.py
"""
from __future__ import annotations

import math
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import score as SC
import scoring as S
import sonde_doublons as SD
from test_sonde_representativite import (JOUR0, Bruit, heures_du_jour,
                                         ligne, vent_de_fond)

OK = 0
KO = 0


def check(label: str, cond: bool, detail: str = ""):
    global OK, KO
    if cond:
        OK += 1
    else:
        KO += 1
        print(f"  ❌ {label}" + (f"\n       {detail}" if detail else ""))


def joue(par_jour: dict, fin: datetime, jours: int, rayon=1.0):
    return SD.graphe(pathlib.Path("/inexistant"), fin, jours, rayon,
                     lecteur=lambda d: par_jour.get(d.strftime("%Y-%m-%d"), []),
                     crier=lambda *_a, **_k: None)


# ══════════════════════════════════════════════════════════════════
#  A. LE GRAPHE — huit paires, quatre verdicts, connus d'avance
# ══════════════════════════════════════════════════════════════════

#: (nom, source_b, id_b, décalage de longitude, bruit ajouté à b,
#:  décalage constant, heures gardées, jours actifs)
SCENES = (
    # ── DOUBLONS : même point (ou presque), séries quasi identiques ──
    ("dbl_colle",   "windsmobi", "ffvl-3001", 0.00000, 0.05, None, None, None),
    ("dbl_decale",  "windsmobi", "ffvl-3002", 0.00150, 0.10, None, None, None),
    ("dbl_sans_id", "infoclimat", "ZZZ",      0.00100, 0.10, None, None, None),
    # ── VRAIS VOISINS : 0,4 km, du vrai bruit de site ────────────────
    ("voisin_1",    "res",       "v1",        0.00510, 2.60, None, None, None),
    ("voisin_2",    "windsmobi", "ffvl-3004", 0.00510, 2.60, None, None, None),
    # ⭐ LE FAUX POSITIF QUE TOUT LE LOT EXISTE POUR ÉVITER : deux VRAIES
    # balises à 480 m qui s'accordent très bien (plaine, vent établi).
    # Le critère d'ACCORD seul les jetterait ; c'est la DISTANCE qui les
    # sauve, et c'est la seule raison d'être du seuil géométrique.
    ("voisin_accordant", "res",  "va",        0.00610, 0.30, None, None, None),
    # ⭐ DEUX CHAÎNES DU MÊME MÂT : au même point, mais 2,5 km/h d'écart
    # médian — l'ordre de grandeur mesuré sur les 47 paires
    # `metar` ↔ `mf` (METAR publié en NŒUDS ENTIERS, moyenne 10 min).
    # Ce n'est pas un voisin, et ce n'est pas non plus une coordonnée
    # fausse : c'est un `doublon_probable`.
    ("chaine",      "mf",        "77001",     0.00010, 0.10, (2.4, 0.8),
     None, None),
    # ── MÊME POINT, VENTS INCOMPATIBLES : une coordonnée est fausse ──
    ("incompat",    "infoclimat", "STATIC9",  0.00000, 0.10, (7.0, 4.0),
     None, None),
    # ── INDÉCIDABLE : assez d'heures par jour pour qu'une médiane
    #    journalière existe, mais TROIS JOURS en tout — donc bien moins
    #    que `MIN_HEURES_VERDICT`. C'est ce seuil-là, et lui seul, qui
    #    doit trancher ici.
    ("court",       "windsmobi", "ffvl-3006", 0.00050, 0.05, None, None,
     (0, 3)),
)


def scene_graphe(n_jours: int = 12) -> dict:
    br_a = Bruit(2.0, 0x1000)
    par_jour: dict = {}
    for k in range(n_jours):
        d = JOUR0 + timedelta(days=k)
        rows = []
        for i, (nom, src_b, id_b, dlon, h_b, decale, plage, jours) in \
                enumerate(SCENES):
            if jours is not None and not (jours[0] <= k < jours[1]):
                continue
            lat = 45.0 + 0.2 * i
            heures = heures_du_jour(k, i)
            if plage:
                heures = [h for h in heures if plage[0] <= h < plage[1]]
            br_b = Bruit(h_b, 0x2000 + i)
            uva, uvb = [], []
            for hh in heures:
                u0, v0 = vent_de_fond(d, hh, k + i)
                au, av = br_a.uv()
                bu, bv = br_b.uv()
                uva.append((u0 + au, v0 + av))
                ub, vb = (u0 + au + bu, v0 + av + bv)
                if decale:
                    ub, vb = ub + decale[0], vb + decale[1]
                uvb.append((ub, vb))
            rows.append(ligne("pioupiou", f"{1000 + i}", lat, 6.0, d,
                              heures, uva))
            rows.append(ligne(src_b, id_b, lat, 6.0 + dlon, d, heures, uvb))
        par_jour[d.strftime("%Y-%m-%d")] = rows
    return par_jour


def test_a_graphe():
    g = joue(scene_graphe(), JOUR0 + timedelta(days=11), 12)
    par_nom = {}
    for p in g["paires"]:
        for i, sc in enumerate(SCENES):
            if p["a"].endswith(f":{1000 + i}") or p["b"].endswith(f":{1000 + i}"):
                par_nom[sc[0]] = p
    attendu = {
        "dbl_colle": "doublon", "dbl_decale": "doublon",
        "dbl_sans_id": "doublon", "voisin_1": "voisin",
        "voisin_2": "voisin", "voisin_accordant": "voisin",
        "chaine": "doublon_probable",
        "incompat": "meme_point_incompatible",
        "court": "indecidable",
    }
    for nom, v in attendu.items():
        p = par_nom.get(nom)
        check(f"A · « {nom} » ⇒ {v}",
              p is not None and p["verdict"] == v,
              f"rendu {None if not p else (p['verdict'], round(p['dist_km'], 3), p['ecart_med'], p['n_heures'])}")
    # ⛔ Et ce voisin-là est bien un CAS LIMITE, pas une scène facile :
    # son accord est SOUS le seuil physique. Si le banc le classait
    # « voisin » pour la mauvaise raison (un écart trop grand), il ne
    # testerait plus le seuil géométrique.
    va = par_nom.get("voisin_accordant")
    check("A · le voisin accordant l'est VRAIMENT (accord sous le seuil)",
          va is not None and va["ecart_med"] is not None
          and va["ecart_med"] <= SD.SEUIL_ECART_KMH,
          f"écart {None if not va else va['ecart_med']}")
    check("A · exactement trois doublons, pas quatre",
          g["compte"].get("doublon") == 3, str(g["compte"]))
    check("A · et trois composantes de deux membres",
          len(g["composantes"]) == 3
          and all(c["taille"] == 2 for c in g["composantes"]),
          str([(c["membres"], c["taille"]) for c in g["composantes"]]))
    # ⛔ LES DEUX LECTURES NE SE CONFONDENT PAS : la large ajoute la
    # paire « deux chaînes du même mât », l'étroite ne la voit pas.
    check("A · la lecture LARGE ajoute exactement le doublon probable",
          len(g["composantes_larges"]) == 4,
          str([c["membres"] for c in g["composantes_larges"]]))
    check("A · … et l'étroite ne l'a jamais retiré",
          all("mf:77001" not in c["membres"] for c in g["composantes"]),
          str([c["membres"] for c in g["composantes"]]))
    # ⛔ Le tableau croisé doit MONTRER la séparation, sinon aucun seuil
    # n'est défendable et le rapport doit le dire.
    check("A · le tableau croisé est peuplé des deux côtés",
          len(g["croise"]) >= 2, str(g["croise"]))
    # ⛔ Et ses AXES portent chaque bande une fois et une seule — la
    # faute du lot L6 (première bande en double, dernière absente) s'est
    # reproduite ici le même jour, dans un autre fichier.
    for nom, bornes in (("distance", SD.BANDES_DIST),
                        ("écart", SD.BANDES_ECART)):
        e = SD.etiquettes(bornes)
        check(f"A · l'axe « {nom} » : une étiquette par bande, sans "
              f"doublon ni trou",
              len(e) == len(bornes) + 1 == len(set(e))
              and e[-2] == f"≤ {bornes[-1]:g}", str(e))
        check(f"A · … et chacune est bien celle que rend `bande()`",
              all(SD.bande(b - 1e-9, bornes) == lab
                  for b, lab in zip(bornes, e)), str(e))


# ══════════════════════════════════════════════════════════════════
#  B. LA TRANSITIVITÉ — trois inscriptions, UNE balise
# ══════════════════════════════════════════════════════════════════

def test_b_transitivite():
    br = Bruit(2.0, 0x3000)
    par_jour = {}
    for k in range(12):
        d = JOUR0 + timedelta(days=k)
        heures = heures_du_jour(k, 0)
        uv = []
        for hh in heures:
            u0, v0 = vent_de_fond(d, hh, k)
            du, dv = br.uv()
            uv.append((u0 + du, v0 + dv))
        fin_ = Bruit(0.05, 0x3001)

        def bruite(base):
            return [(u + fin_.uv()[0], v + fin_.uv()[1]) for u, v in base]
        par_jour[d.strftime("%Y-%m-%d")] = [
            ligne("pioupiou", "1", 45.0, 6.0, d, heures, bruite(uv)),
            ligne("windsmobi", "ffvl-1", 45.0, 6.0008, d, heures, bruite(uv)),
            ligne("infoclimat", "X1", 45.0, 6.0016, d, heures, bruite(uv)),
        ]
    g = joue(par_jour, JOUR0 + timedelta(days=11), 12)
    check("B · une seule composante, de trois membres",
          len(g["composantes"]) == 1 and g["composantes"][0]["taille"] == 3,
          str([(c["membres"], c["taille"]) for c in g["composantes"]]))
    check("B · et son diamètre est publié (pour la relire à la main)",
          g["composantes"][0]["diametre_km"] > 0,
          str(g["composantes"][0]))
    check("B · trois sources distinctes reconnues",
          g["composantes"][0]["sources"]
          == ["infoclimat", "pioupiou", "windsmobi"],
          str(g["composantes"][0]["sources"]))


# ══════════════════════════════════════════════════════════════════
#  C. LA RÈGLE — chaque critère tranche, dans l'ordre
# ══════════════════════════════════════════════════════════════════

def _faits(n_modeles, n_jours, heures):
    return {"n_modeles": n_modeles, "n_jours": n_jours, "heures": heures,
            "modeles": [], "n_leads": 1}


def test_c_regle():
    # ⭐ `agrume` AVANT le nombre de modèles : `pioupiou` gagne MÊME en
    # portant moins de modèles, parce que le retirer retirerait
    # `agrume`/`agrume_pi` de la case — la contrainte, pas la préférence.
    faits = {"pioupiou:1": _faits(2, 5, 100),
             "windsmobi:ffvl-1": _faits(9, 30, 900)}
    g, crit = SD.choisir(["windsmobi:ffvl-1", "pioupiou:1"], faits)
    check("C · `pioupiou` gagne malgré 2 modèles contre 9",
          (g, crit) == ("pioupiou:1", "agrume"), f"{g} / {crit}")

    # entre deux non-`pioupiou`, c'est le nombre de MODÈLES
    faits = {"mf:1": _faits(9, 10, 100), "windsmobi:ffvl-2": _faits(5, 30, 900)}
    g, crit = SD.choisir(["windsmobi:ffvl-2", "mf:1"], faits)
    check("C · sinon le plus de modèles gagne (le groupe complet bat le "
          "réduit)", (g, crit) == ("mf:1", "modeles"), f"{g} / {crit}")

    # à égalité de modèles, les JOURS
    faits = {"mf:1": _faits(5, 10, 900), "aemet:2": _faits(5, 30, 100)}
    g, crit = SD.choisir(["mf:1", "aemet:2"], faits)
    check("C · à modèles égaux, la meilleure couverture en jours",
          (g, crit) == ("aemet:2", "jours"), f"{g} / {crit}")

    # à jours égaux, les HEURES
    faits = {"mf:1": _faits(5, 10, 900), "aemet:2": _faits(5, 10, 100)}
    g, crit = SD.choisir(["mf:1", "aemet:2"], faits)
    check("C · à jours égaux, les heures",
          (g, crit) == ("mf:1", "heures"), f"{g} / {crit}")

    # tout à égalité : l'ordre lexical, et il est ANNONCÉ comme tel
    faits = {"mf:1": _faits(5, 10, 100), "aemet:2": _faits(5, 10, 100)}
    g, crit = SD.choisir(["mf:1", "aemet:2"], faits)
    check("C · tout à égalité : l'ordre lexical, nommé « nom »",
          (g, crit) == ("aemet:2", "nom"), f"{g} / {crit}")

    # ⛔ une balise ABSENTE de la base ne doit pas gagner par défaut
    faits = {"mf:1": _faits(9, 30, 900)}
    g, _c = SD.choisir(["mf:1", "aemet:2"], faits)
    check("C · une inscription que la base ne connaît pas ne gagne pas",
          g == "mf:1", g)


def test_c2_faits():
    """Les faits viennent de la BASE, pas d'une supposition — et le banc
    les compte à la main sur un jeu minuscule."""
    daily = [
        {"source": "res", "station_id": "1", "model": "m1", "day": "J1",
         "lead_h": 6, "n_hours": 24},
        {"source": "res", "station_id": "1", "model": "m2", "day": "J1",
         "lead_h": 6, "n_hours": 20},
        {"source": "res", "station_id": "1", "model": "m1", "day": "J2",
         "lead_h": 24, "n_hours": 10},
        {"source": "res", "station_id": "2", "model": "m1", "day": "J1",
         "lead_h": 6, "n_hours": 5},
    ]
    f = SD.faits_par_unite(daily)
    check("C2 · modèles DISTINCTS, pas lignes",
          f["res:1"]["n_modeles"] == 2, str(f["res:1"]))
    check("C2 · jours DISTINCTS, pas lignes",
          f["res:1"]["n_jours"] == 2, str(f["res:1"]))
    check("C2 · heures SOMMÉES sur toutes les lignes",
          f["res:1"]["heures"] == 54, str(f["res:1"]))
    check("C2 · les échéances distinctes sont comptées à part",
          f["res:1"]["n_leads"] == 2, str(f["res:1"]))
    check("C2 · et la seconde balise n'hérite de rien",
          f["res:2"] == {"modeles": ["m1"], "n_modeles": 1, "n_jours": 1,
                         "heures": 5, "n_leads": 1}, str(f["res:2"]))


# ══════════════════════════════════════════════════════════════════
#  D. LA REPRODUCTIBILITÉ — l'ordre d'entrée ne décide de rien
# ══════════════════════════════════════════════════════════════════

def test_d_reproductible():
    faits = {"mf:1": _faits(5, 10, 100), "aemet:2": _faits(5, 10, 100),
             "windsmobi:x": _faits(5, 10, 100)}
    membres = ["mf:1", "aemet:2", "windsmobi:x"]
    reponses = {SD.choisir(m, faits)
                for m in (membres, membres[::-1],
                          [membres[1], membres[2], membres[0]])}
    check("D · le représentant ne dépend pas de l'ordre des membres",
          len(reponses) == 1, str(reponses))

    c1, c2 = SD.Composantes(), SD.Composantes()
    for a, b in (("a", "b"), ("b", "c"), ("d", "e")):
        c1.unir(a, b)
    for a, b in (("d", "e"), ("b", "c"), ("a", "b")):
        c2.unir(a, b)
    check("D · les composantes ne dépendent pas de l'ordre des unions",
          c1.groupes() == c2.groupes(), f"{c1.groupes()} vs {c2.groupes()}")
    # ⭐ Et la garantie vit dans `groupes()`, pas dans `unir()` : les
    # membres d'une composante sortent TRIÉS, et les composantes aussi.
    # C'est ce qui rend le départage lexical de `choisir` déterministe.
    c3 = SD.Composantes()
    for a_, b_ in (("zz", "aa"), ("mm", "aa"), ("bb", "yy")):
        c3.unir(a_, b_)
    gr = c3.groupes()
    check("D · les membres d'une composante sortent TRIÉS",
          all(m == sorted(m) for m in gr), str(gr))
    check("D · et les composantes entre elles aussi",
          [m[0] for m in gr] == sorted(m[0] for m in gr), str(gr))


# ══════════════════════════════════════════════════════════════════
#  E. LA PREUVE NOMINALE — corroboration, JAMAIS critère
# ══════════════════════════════════════════════════════════════════

def test_e_nominal():
    check("E · un suffixe de 3 chiffres est reconnu",
          SD.suffixe_commun("pioupiou:1494", "windsmobi:ffvl-3494") == "494")
    check("E · deux chiffres ne suffisent pas (trop de coïncidences)",
          SD.suffixe_commun("a:12", "b:912") is None,
          str(SD.suffixe_commun("a:12", "b:912")))
    check("E · aucun chiffre commun ⇒ rien",
          SD.suffixe_commun("infoclimat:ZZZ", "pioupiou:1002") is None)

    g = joue(scene_graphe(), JOUR0 + timedelta(days=11), 12)
    sx = g["suffixe"]
    # `dbl_sans_id` (infoclimat:ZZZ) est un doublon SANS suffixe commun :
    # il doit être trouvé quand même, et compté comme manqué par la
    # preuve nominale.
    check("E · un doublon sans suffixe commun est trouvé quand même",
          sx["doublons_sans_suffixe"] >= 1, str(sx))
    check("E · et le rapport sait le compter",
          sx["doublons_avec_suffixe"] + sx["doublons_sans_suffixe"]
          == g["compte"].get("doublon"), str(sx))
    # `voisin_2` (windsmobi:ffvl-3004) partage un suffixe avec
    # `pioupiou:1004` et n'est PAS un doublon : une déduplication écrite
    # sur les identifiants l'aurait jeté.
    check("E · un VRAI voisin qui partage un suffixe n'est pas jeté",
          sx["voisins_avec_suffixe"] >= 1, str(sx))


# ══════════════════════════════════════════════════════════════════
#  F. LES SEUILS — aux bornes exactes, pas à peu près
# ══════════════════════════════════════════════════════════════════

def test_f_seuils():
    N = SD.MIN_HEURES_VERDICT
    cas = (
        ("pile au seuil de distance et d'écart ⇒ doublon",
         (SD.SEUIL_DIST_KM, SD.SEUIL_ECART_KMH, N), "doublon"),
        ("un cheveu au-delà de la distance ⇒ voisin",
         (SD.SEUIL_DIST_KM + 1e-9, SD.SEUIL_ECART_KMH, N), "voisin"),
        ("un cheveu au-delà de l'écart, mais AU MÊME POINT ⇒ probable",
         (SD.SEUIL_DIST_KM, SD.SEUIL_ECART_KMH + 1e-9, N),
         "doublon_probable"),
        ("pile au seuil d'incompatibilité ⇒ encore probable",
         (0.0, SD.SEUIL_INCOMPATIBLE_KMH, N), "doublon_probable"),
        ("au-delà de l'incompatibilité ⇒ défaut de référentiel",
         (0.0, SD.SEUIL_INCOMPATIBLE_KMH + 0.1, N), "meme_point_incompatible"),
        ("une heure de moins que le minimum ⇒ indécidable",
         (0.0, 0.1, N - 1), "indecidable"),
        ("le minimum PILE ⇒ on tranche",
         (0.0, 0.1, N), "doublon"),
    )
    for label, (d, e, n), attendu in cas:
        check(f"F · {label}", SD.verdict_paire(d, e, n) == attendu,
              f"rendu {SD.verdict_paire(d, e, n)}")
    check("F · un écart INCONNU ne se range jamais du côté rassurant",
          SD.verdict_paire(0.0, None, 10 * N) == "indecidable")
    # ⛔ IL N'Y A PAS DE « VOISIN » À DISTANCE NULLE. Deux inscriptions
    # au même mètre sont le même capteur ou une coordonnée fausse — la
    # première version rangeait « voisin » les 47 paires `metar` ↔ `mf`.
    check("F · aucun écart, si grand soit-il, ne rend « voisin » au "
          "même point",
          all(SD.verdict_paire(0.0, e, N) != "voisin"
              for e in (0.0, 0.5, 1.5, 3.9, 4.1, 50.0)),
          str([SD.verdict_paire(0.0, e, N)
               for e in (0.0, 0.5, 1.5, 3.9, 4.1, 50.0)]))


# ══════════════════════════════════════════════════════════════════
#  G. ⭐ LE DÉGÂT — sur `_case_rows` lui-même, pas sur une imitation
# ══════════════════════════════════════════════════════════════════

ZONES_BANC = {
    # zone            landform  balises réelles           doublon ajouté
    "b1:plain":  ("plain",  ["res:a", "res:b", "res:c"], None),
    "b2:ridge":  ("ridge",  ["res:d", "res:e"],          "autre:d2"),
    "b3:valley": ("valley", ["res:f", "res:g", "res:h", "res:i"], "autre:f2"),
}
MODELES_BANC = ("mod_bon", "mod_moyen", "mod_mauvais")


def scene_degat(n_jours: int = 10):
    """Trois zones, dont deux portent un doublon. Les erreurs sont
    FABRIQUÉES pour que le classement soit stable : ce qu'on teste est
    l'effet du doublon, pas la sensibilité du bootstrap."""
    zone_of, daily = {}, []
    rnd = S._XorShift(0x51DE)
    for zid, (lf, reelles, doublon) in ZONES_BANC.items():
        membres = list(reelles) + ([doublon] if doublon else [])
        for u in membres:
            src, sid = u.split(":", 1)
            zone_of[u] = {"zone_id": zid, "landform": lf,
                          "basin_id": zid.split(":")[0],
                          "massif_id": "massif_" + zid.split(":")[0],
                          "basin_uncertain": False,
                          "position_suspecte": False}
        for k in range(n_jours):
            jour = (JOUR0 + timedelta(days=k)).strftime("%Y-%m-%d")
            for u in membres:
                src, sid = u.split(":", 1)
                for j, m in enumerate(MODELES_BANC):
                    base = 3.0 + 1.2 * j
                    daily.append({
                        "day": jour, "source": src, "station_id": sid,
                        "model": m, "lead_h": 6, "fcst_src": "own_archive",
                        "n_hours": 24,
                        "err_vec_med": base + rnd.next() * 0.4,
                        "err_vec_rms": base + 1.0 + rnd.next() * 0.4,
                        "mse_model": None, "mse_persist": None,
                        "mse_clim": None, "err_vec_med_corr": None,
                        "mse_model_corr": None, "bias_n_days": None,
                    })
    return zone_of, daily


def _a_la_zone(cases: list, zid: str) -> bool:
    return any(c and c[0] == zid for c in cases)


def test_g_degat():
    zone_of, daily = scene_degat()
    as_of = datetime(2026, 7, 12, tzinfo=timezone.utc)
    ecartes = {"autre:d2", "autre:f2"}
    d = SD.degat(daily, zone_of, ecartes, as_of,
                 crier=lambda *_a, **_k: None)

    attendus = sum(1 for r in daily
                   if f"{r['source']}:{r['station_id']}" in ecartes)
    check("G · exactement les balise-jours des doublons sont retirés",
          d["balise_jours"]["retires"] == attendus == 10 * 3 * 2,
          f"{d['balise_jours']} attendu {attendus}")

    # ⭐ LE DOMMAGE `MIN_STATIONS_ZONE = 3`, DÉMONTRÉ. `b2:ridge` a DEUX
    # vraies balises et un doublon : elle est publiée tant qu'on compte
    # le doublon, et elle disparaît dès qu'on ne le compte plus. Ce
    # n'est pas une perte d'information — c'est une case qui n'aurait
    # jamais dû être publiée.
    check("G · la case à 2 vraies balises + 1 doublon DISPARAÎT",
          _a_la_zone(d["cases"]["perdues"], "b2:ridge"),
          str(d["cases"]["perdues"]))
    check("G · … et la case à 3 vraies balises, elle, RESTE",
          not _a_la_zone(d["cases"]["perdues"], "b1:plain"),
          str(d["cases"]["perdues"]))
    check("G · le nombre de cases baisse, jamais l'inverse",
          d["cases"]["apres"] < d["cases"]["avant"],
          str(d["cases"]))

    # `b3:valley` garde ses quatre vraies balises : la case SURVIT, mais
    # son `n` était gonflé d'un cinquième.
    gonflees = [x for x in d["inflation"] if x["case"][0] == "b3:valley"]
    check("G · la case à 4 vraies balises survit avec un `n` corrigé",
          bool(gonflees) and gonflees[0]["n_avant"] > gonflees[0]["n_apres"],
          str(d["inflation"][:3]))
    check("G · et l'inflation vaut bien 1/4 (5 balises comptées pour 4)",
          bool(gonflees) and abs(gonflees[0]["inflation"] - 0.25) < 1e-9,
          str(gonflees[:1]))
    check("G · la case sans doublon n'est PAS dans la liste des gonflées",
          not any(x["case"][0] == "b1:plain" for x in d["inflation"]),
          str([x["case"][0] for x in d["inflation"]]))
    check("G · l'inflation médiane est publiée",
          d["inflation_mediane"] is not None, str(d["inflation_mediane"]))
    check("G · rien n'est écrit : `degat` ne rend que des chiffres",
          isinstance(d, dict) and "avant" in d and "apres" in d)
    # ⭐ LE CONTRÔLE DU CÂBLAGE : retirer les doublons À LA MAIN (en
    # amont) et les retirer PAR LA COLONNE `doublon_de` (au fond de
    # `_case_rows`, comme le fera la production) doivent rendre le même
    # objet. Deux chemins, un résultat.
    acc = d["cablage_l17"]
    check("G · les deux chemins de retrait s'accordent sur les six "
          "contrôles",
          all(acc.values()),
          str({k: v for k, v in acc.items() if not v}))
    check("G · … et le contrôle porte sur sept choses, pas sur zéro",
          len(acc) == 7, str(sorted(acc)))
    # ⛔ ET LA PREUVE QUE LA COLONNE A ÉTÉ LUE. Deux passes identiques
    # s'accordent toujours : sans ce témoin, le contrôle passerait au
    # vert en ne contrôlant rien.
    check("G · `score.est_doublon` a VU la colonne (journal à l'appui)",
          acc.get("colonne_lue") is True, str(acc))


# ══════════════════════════════════════════════════════════════════
#  I. LE `.sql` DE PEUPLEMENT — préparé, jamais exécuté
# ══════════════════════════════════════════════════════════════════

def test_i_sql():
    g = joue(scene_graphe(), JOUR0 + timedelta(days=11), 12)
    faits = {u: _faits(9, 20, 400) for c in g["composantes"]
             for u in c["membres"]}
    r = SD.regle(g["composantes"], faits)
    sql = SD.sql_peuplement(g, r, "etroit", "2026-08-26")

    check("I · une transaction, pas une pluie d'UPDATE isolés",
          sql.count("begin;") == 1 and sql.count("commit;") == 1, sql[:80])
    # ⛔ CONVERGENT : la table repart d'une page blanche. Sans ça, les
    # doublons d'une mesure précédente survivraient à celle-ci et
    # personne ne saurait plus quel état la base porte.
    check("I · il REMET À NULL avant de poser",
          "update public.station_zone set doublon_de = null" in sql
          and sql.index("= null") < sql.index("doublon_de = 'pioupiou"),
          "pas de remise à null, ou après les poses")
    n_updates = sql.count("update public.station_zone set doublon_de = '")
    check("I · exactement un UPDATE par inscription écartée",
          n_updates == r["n_ecartes"] == 3,
          f"{n_updates} updates pour {r['n_ecartes']} écartés")

    # ⛔ LE REPRÉSENTANT NE DOIT JAMAIS ÊTRE LA CIBLE D'UN UPDATE :
    # `_case_rows` écarte TOUTE ligne dont `doublon_de` est posé, donc
    # un représentant marqué ferait taire la case au lieu de la
    # dédoublonner.
    for garde in r["gardes"]:
        src, sid = garde.split(":", 1)
        cible = f"where source = '{src}' and station_id = '{sid}';"
        check(f"I · le représentant {garde} n'est jamais marqué",
              cible not in sql, cible)
    for e in r["detail"]:
        for perdu in e["ecartes"]:
            src, sid = perdu.split(":", 1)
            check(f"I · l'écarté {perdu} pointe vers son représentant",
                  f"set doublon_de = '{e['garde']}'\n where source = "
                  f"'{src}' and station_id = '{sid}';" in sql,
                  perdu)
    check("I · et le contrôle « représentants eux-mêmes écartés » est dedans",
          "representants_eux_memes_ecartes" in sql)
    check("I · la preuve de chaque ligne voyage en commentaire",
          sql.count("· écart médian") == r["n_ecartes"],
          sql.count("· écart médian"))

    # ⚠️ Les identifiants viennent de référentiels tiers : une apostrophe
    # dans un `station_id` ne doit pas casser la requête (ni pire).
    check("I · une apostrophe est doublée, pas recopiée",
          SD._lit("l'Alpe") == "'l''Alpe'", SD._lit("l'Alpe"))
    faux = {"detail": [{"garde": "a:b", "ecartes": ["x:y'z"],
                        "critere": "nom", "taille": 2, "diametre_km": 0.0,
                        "faits": {}}],
            "gardes": ["a:b"], "ecartes": ["x:y'z"], "n_ecartes": 1,
            "n_composantes": 1, "par_critere": {}, "ecartes_notes": []}
    s2 = SD.sql_peuplement({"fenetre": g["fenetre"], "paires": []}, faux,
                           "etroit", "2026-08-26")
    check("I · … y compris dans un identifiant réel",
          "station_id = 'y''z'" in s2, s2[-400:])


# ══════════════════════════════════════════════════════════════════
#  H. LE RAPPORT — il doit se lire, et dire ce qu'il ne sait pas
# ══════════════════════════════════════════════════════════════════

def test_h_rapport():
    g = joue(scene_graphe(), JOUR0 + timedelta(days=11), 12)
    faits = {u: _faits(9, 20, 400) for c in g["composantes"]
             for u in c["membres"]}
    r = SD.regle(g["composantes"], faits)
    txt = SD.rapport(g, {"etroit": r, "large": r}, None, None, faits)
    for attendu in ("OÙ LE SEUIL SE LIT", "PREUVE NOMINALE",
                    "MÊME POINT, VENTS INCOMPATIBLES", "LA RÈGLE"):
        check(f"H · le rapport porte « {attendu} »", attendu in txt)
    check("H · sans passe 3, il ne fabrique aucun dégât",
          "LE DÉGÂT" not in txt)
    check("H · exactement UN représentant par composante, jamais zéro "
          "ni deux",
          r["n_ecartes"] == sum(c["taille"] - 1 for c in g["composantes"])
          and len(r["gardes"]) == len(g["composantes"]),
          f"{r['n_ecartes']} écartés, {len(r['gardes'])} gardés, "
          f"{len(g['composantes'])} composantes")
    check("H · la règle garde `pioupiou` partout dans cette scène",
          all(gg.startswith("pioupiou:") for gg in r["gardes"]),
          str(r["gardes"]))
    zone_of, daily = scene_degat()
    d = SD.degat(daily, zone_of, {"autre:d2", "autre:f2"},
                 datetime(2026, 7, 12, tzinfo=timezone.utc),
                 crier=lambda *_a, **_k: None)
    txt2 = SD.rapport(g, {"etroit": r, "large": r},
                      {"etroit": d, "large": d}, None, faits)
    check("H · avec la passe 3, le dégât est écrit et chiffré",
          "LE DÉGÂT" in txt2 and "PODIUMS QUI CHANGENT" in txt2)


# ══════════════════════════════════════════════════════════════════

def main() -> int:
    for f in (test_a_graphe, test_b_transitivite, test_c_regle,
              test_c2_faits,
              test_d_reproductible, test_e_nominal, test_f_seuils,
              test_g_degat, test_i_sql, test_h_rapport):
        f()
    print(f"\n  {OK} vertes, {KO} rouges")
    return 1 if KO else 0


if __name__ == "__main__":
    sys.exit(main())
