# ══════════════════════════════════════════════════════════════════════
#  model-verif/test_agrume_pi_fcst.py — le banc de la série `agrume_pi`
#                                                          (26/08/2026)
#
#  Sans réseau, sans clé, sans base. Il ne vérifie pas que le composite
#  « marche » : il vérifie les NEUF façons qu'il aurait de casser EN
#  SILENCE — c'est-à-dire en rendant un vent parfaitement crédible.
#
#      python3 test_agrume_pi_fcst.py
#
#  ⚠️ Il exige numpy. Pas de version « qui saute si le module est
#  absent » : un banc qui se désactive tout seul est un banc qui ne dit
#  plus rien.
#
#  ═══ CE QUE CHACUN TIENT, ET CE QUE ÇA COÛTERAIT DE NE PAS L'AVOIR ═══
#
#  · invariant    → Δ mal signé (AROME−PI)      → correction à l'envers, crédible
#  · rampe        → w ignoré                    → PI plein pot jusqu'à 6 h
#  · horizon      → Δ propagé au-delà de 6 h    → 18 h corrigées par du vide
#  · appariement  → PI indexé par RANG          → Δ d'une balise sur une autre
#  · maille       → Δ pris en 0,01°             → l'écart de résolution crédité à PI
#  · échéances    → `.get(i)` au lieu de `.get(step)` → décalage sur run troué
#  · absence      → NaN traité comme 0          → « PI ne corrige rien » affirmé
#  · population   → balises sans PI dans la série → apport de PI dilué
#  · axe .npz     → manifeste et npz divergents → chaque Δ sur la mauvaise balise
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np                                          # noqa: E402

import agrume_fcst as A                                     # noqa: E402
from colonnes import Colonnes                               # noqa: E402
from profil import decorer_vent                             # noqa: E402

ECHECS: list[str] = []


def verifie(condition, message):
    if condition:
        print(f"  ✅ {message}")
    else:
        print(f"  ❌ {message}")
        ECHECS.append(message)


# ══════════════════════════════════════════════════════════════════
#  FABRIQUE
# ══════════════════════════════════════════════════════════════════

RUN = "2026-08-12T00:00:00Z"
STEPS = list(range(24))
MINUTES = list(range(0, 361, 15))
NIVEAUX = [10, 20, 50, 100, 250, 500]
PARAMS = [{"nom": "u", "unite": "m/s"}, {"nom": "v", "unite": "m/s"}]

BALISES = [
    {"id": "70", "lat": 46.15, "lon": 6.19, "nom": "Salève",
     "source": "pioupiou", "position_suspecte": False},
    {"id": "1377", "lat": 45.60, "lon": 6.20, "nom": "Un déco",
     "source": "pioupiou", "position_suspecte": False},
    {"id": "RS-06610", "lat": 46.81, "lon": 6.94, "nom": "Payerne",
     "source": "radiosondage", "position_suspecte": False},
]


def archive_a(base10, base20, balises=None, steps=None, base20_fine=None):
    """Un `Colonnes` du produit A : le 10 m en 0,01°, le 20 m en 0,025°.

    `base20_fine` remplit le 20 m de la maille 0,01° — il ne sert QU'À
    prouver que Δ ne le lit pas (banc nº 5).
    """
    bal = BALISES if balises is None else balises
    col = Colonnes(RUN, bal, list(STEPS if steps is None else steps))
    iu1, iv1 = col.i_param_001["u"], col.i_param_001["v"]
    iu2, iv2 = col.i_param_0025["u"], col.i_param_0025["v"]
    j10f, j20f = col.i_niveau_001[10], col.i_niveau_001[20]
    j20 = col.i_niveau_0025[20]
    for k in range(len(bal)):
        for i, s in enumerate(col.steps):
            uv = base10(k, int(s))
            if uv is not None:
                col.c001[k, iu1, j10f, i] = np.float16(uv[0])
                col.c001[k, iv1, j10f, i] = np.float16(uv[1])
            uv2 = base20(k, int(s))
            if uv2 is not None:
                col.c0025[k, iu2, j20, i] = np.float16(uv2[0])
                col.c0025[k, iv2, j20, i] = np.float16(uv2[1])
            if base20_fine is not None:
                uvf = base20_fine(k, int(s))
                if uvf is not None:
                    col.c001[k, iu1, j20f, i] = np.float16(uvf[0])
                    col.c001[k, iv1, j20f, i] = np.float16(uvf[1])
    man = {"run": RUN, "echeances": list(col.steps), "balises": bal}
    return col, man


def archive_pi(val, balises=None, ordre=None, minutes=None, servie=None):
    """`(donnees, manifeste)` des colonnes PI.

    ⚠️ `val` est indexée par IDENTIFIANT de balise, pas par rang — c'est
    ce qui rend le banc nº 4 capable d'échouer : réordonner l'axe ne
    change alors AUCUNE valeur physique, seulement leur position.
    """
    bal = BALISES if balises is None else balises
    mins = MINUTES if minutes is None else list(minutes)
    ordre = list(range(len(bal))) if ordre is None else list(ordre)
    axe = [bal[i] for i in ordre]
    d = np.full((2, len(NIVEAUX), len(mins), len(axe)), np.nan,
                dtype=np.float32)
    j20 = NIVEAUX.index(20)
    for kk, b in enumerate(axe):
        for im, m in enumerate(mins):
            uv = val(str(b["id"]), m)
            if uv is None:
                continue
            d[0, j20, im, kk] = uv[0]
            d[1, j20, im, kk] = uv[1]
    man = {
        "run": RUN, "parametres": PARAMS, "niveaux_m_sol": list(NIVEAUX),
        "echeances_min": list(mins),
        "balises": [dict(id=b["id"],
                         servie=True if servie is None else servie(b["id"]))
                    for b in axe],
    }
    return d, man


def par_id(rows):
    return {r["station_id"]: r for r in rows}


def muet(*_a, **_k):
    pass


# ══════════════════════════════════════════════════════════════════
#  1. L'INVARIANT — le composite au 10 m vaut AROME₁₀ + Δ(20 m)
# ══════════════════════════════════════════════════════════════════

def test_invariant_du_composite():
    """⚠️ ET LE MÊME ARRONDI DES DEUX CÔTÉS.

    L'attendu se calcule depuis les valeurs RELUES du `.npz` (float16),
    pas depuis les flottants qu'on a posés. C'est le piège qui a rendu
    un « 0/125 » parfaitement crédible à l'étape 8 du lot H : comparer
    une valeur quantifiée à une valeur qui ne l'est pas fait échouer un
    invariant juste, ou réussir un invariant faux.
    """
    col, man = archive_a(lambda k, s: (3.0, 4.0), lambda k, s: (2.0, 0.0))
    d_pi, m_pi = archive_pi(lambda i, m: (5.0, 1.0))
    d = A.delta_20m(col, d_pi, m_pi, crier=muet)
    rows = par_id(list(A.lignes(col, man, model=A.MODEL_PI, delta=d,
                                extra={"agrume_pi_run": RUN})))
    r = rows["70"]

    j10 = col.i_niveau_001[10]
    u10 = float(col.c001[0, col.i_param_001["u"], j10, 0])
    v10 = float(col.c001[0, col.i_param_001["v"], j10, 0])
    j20 = col.i_niveau_0025[20]
    u20 = float(col.c0025[0, col.i_param_0025["u"], j20, 0])
    v20 = float(col.c0025[0, col.i_param_0025["v"], j20, 0])
    du, dv = 5.0 - u20, 1.0 - v20

    # ⛔ LES DEUX FACTEURS SONT ÉCRITS EN DUR, PAS LUS DU MODULE.
    # `0.5` est α (le composite MÉLANGE AROME et PI, il ne remplace
    # pas) ; `0.766` est le cisaillement mesuré entre 10 et 20 m. Les
    # lire depuis `composite` ferait bouger les deux côtés de l'égalité
    # ensemble : une mutation « α = 1 » resterait invisible. C'est le
    # piège nº 1 de la phase B, et il s'est reproduit le 26/08 au soir
    # dans `test_composite.py` avant d'être attrapé par la mutation.
    ALPHA, KAPPA = 0.5, 0.766
    attendu = decorer_vent({"u": u10 + ALPHA * KAPPA * du,
                            "v": v10 + ALPHA * KAPPA * dv})
    verifie(abs(r["speed"][0] - attendu["vitesseKmh"]) < 1e-9,
            f"h=0, rampe=1 : le 10 m composite vaut AROME₁₀ + α·κ·Δ(20 m) "
            f"({r['speed'][0]} = {attendu['vitesseKmh']})")
    verifie(abs(r["dir"][0] - attendu["directionDeg"]) < 1e-9,
            f"h=0 : la direction suit le même calcul ({r['dir'][0]}°)")
    # ⚠️ ET LE CONTRÔLE QUI EMPÊCHE CE BANC DE DEVENIR DÉCORATIF : le
    # composite ne doit PAS valoir AROME₁₀ + Δ tel quel. C'est ce qu'il
    # valait jusqu'au 26/08, et c'est mesurément moins bon qu'AROME nu.
    nu = decorer_vent({"u": u10 + du, "v": v10 + dv})
    verifie(abs(r["speed"][0] - nu["vitesseKmh"]) > 1.0,
            f"⛔ et il ne vaut PLUS AROME₁₀ + Δ brut — le remplacement "
            f"d'AROME par PI ({r['speed'][0]:.2f} ≠ {nu['vitesseKmh']:.2f})")

    # ⛔ LE SIGNE. Δ = PI − AROME, jamais l'inverse. Ici PI souffle plus
    # fort qu'AROME (5 contre 2) : le composite doit être PLUS VENTÉ que
    # la série brute, pas moins. Un Δ inversé rendrait un vent
    # parfaitement crédible et un score qui se dégrade sans raison.
    brut = par_id(list(A.lignes(col, man)))["70"]
    verifie(r["speed"][0] > brut["speed"][0],
            f"Δ = PI − AROME et non l'inverse : le composite est plus "
            f"venté ({r['speed'][0]:.2f} > {brut['speed'][0]:.2f} km/h)")


# ══════════════════════════════════════════════════════════════════
#  2. LA RAMPE w_PI, ET L'HORIZON DE 6 H
# ══════════════════════════════════════════════════════════════════

def test_rampe_et_horizon():
    """La rampe est celle du composite SERVI, importée et non recopiée."""
    col, man = archive_a(lambda k, s: (3.0, 4.0), lambda k, s: (2.0, 0.0))
    d_pi, m_pi = archive_pi(lambda i, m: (6.0, 0.0))
    d = A.delta_20m(col, d_pi, m_pi, crier=muet)

    heures = sorted(d[0])
    verifie(heures == [0, 1, 2, 3, 4, 5],
            f"Δ n'existe qu'aux heures 0 à 5 — {heures}")
    verifie(6 not in d[0],
            "à τ = 6 h la rampe vaut 0 : aucun Δ posé, plutôt qu'un Δ "
            "multiplié par zéro qui laisserait croire que PI porte "
            "cette heure")

    du_plein = d[0][4][0]
    du_rampe = d[0][5][0]
    verifie(abs(du_rampe - du_plein / 2.0) < 1e-6,
            f"h=5 : w = 0,5, Δ est bien de moitié "
            f"({du_rampe:.3f} contre {du_plein:.3f})")

    rows = par_id(list(A.lignes(col, man, model=A.MODEL_PI, delta=d)))
    brut = par_id(list(A.lignes(col, man)))
    memes = [h for h in range(6, 24)
             if rows["70"]["speed"][h] == brut["70"]["speed"][h]
             and rows["70"]["dir"][h] == brut["70"]["dir"][h]]
    verifie(len(memes) == 18,
            f"au-delà de l'horizon de PI, les 18 heures restantes sont "
            f"IDENTIQUES à la série brute ({len(memes)}/18) — PI ne "
            f"déborde pas sur ce qu'il ne couvre pas")


# ══════════════════════════════════════════════════════════════════
#  3. L'APPARIEMENT DES BALISES — PAR IDENTIFIANT, JAMAIS PAR RANG
# ══════════════════════════════════════════════════════════════════

def test_appariement_par_identifiant():
    """⚠️ LE DÉFAUT LE PLUS COÛTEUX DE CE FLUX, ET IL NE LÈVE RIEN.

    L'axe des balises de PI vient de `quantification.balises_du_domaine()`,
    celui du produit A vient d'ailleurs. Ils se ressemblent aujourd'hui.
    Le jour où l'un des deux gagne ou perd un point, un Δ indexé par
    RANG atterrit sur la balise d'à côté — et une prévision prise 40 km
    plus loin reste finie, plausible, et fausse.

    Ici l'axe PI est RETOURNÉ. Aucune valeur physique ne change : seule
    leur position change. Un code qui indexe par rang croisera les deux
    balises et le banc le verra.
    """
    par_balise = {"70": (10.0, 0.0), "1377": (0.0, 10.0)}
    col, man = archive_a(lambda k, s: (1.0, 1.0), lambda k, s: (0.0, 0.0))
    d_pi, m_pi = archive_pi(lambda i, m: par_balise.get(i),
                            ordre=[2, 1, 0])
    d = A.delta_20m(col, d_pi, m_pi, crier=muet)

    # Balise 0 du produit A = « 70 » → Δ porté par u ; balise 1 =
    # « 1377 » → Δ porté par v. Croisés, on lirait exactement l'inverse.
    #
    # ⛔ CE BANC TESTE L'APPARIEMENT, PAS L'AMPLITUDE, et il est écrit
    # pour rester vrai quels que soient α et κ : ce qui l'intéresse est
    # QUEL Δ arrive à QUELLE balise. Un banc d'appariement qui tomberait
    # à chaque changement de pondération finirait par être « corrigé »
    # sans qu'on lise ce qu'il dit.
    verifie(d[0][0][0] > 1e-6 and abs(d[0][0][1]) < 1e-9,
            f"« 70 » reçoit SON Δ (porté par u) malgré l'axe PI retourné "
            f"— lu ({d[0][0][0]:.3f}, {d[0][0][1]:.3f})")
    verifie(abs(d[1][0][0]) < 1e-9 and d[1][0][1] > 1e-6,
            f"« 1377 » reçoit SON Δ (porté par v) — lu "
            f"({d[1][0][0]:.3f}, {d[1][0][1]:.3f})")
    # ⚠️ Et l'amplitude séparément, avec les facteurs EN DUR (cf. le
    # banc du 10 m) : Δ posé à 10, servi à 10 × 0,5 × 0,766.
    verifie(abs(d[0][0][0] - 10.0 * 0.5 * 0.766) < 1e-6,
            f"et il arrive à l'échelle α·κ — {d[0][0][0]:.4f} pour "
            f"{10.0 * 0.5 * 0.766:.4f} attendu")


# ══════════════════════════════════════════════════════════════════
#  3bis. LOT L7 — UNE SOURCE NOUVELLEMENT NOTÉE, MAIS ABSENTE DE L'AXE PI
# ══════════════════════════════════════════════════════════════════

def test_source_elargie_sans_correction_pi():
    """⛔ CE QUI AURAIT DÛ ROUGIR SI `not in SOURCE_NOTEE` ÉTAIT RESTÉ
    `!= SOURCE_NOTEE` APRÈS QUE LE LOT L7 A FAIT DE `SOURCE_NOTEE` UN
    ENSEMBLE — et qui ne rougissait dans AUCUN autre banc de ce fichier,
    puisqu'aucun n'ajoute de balise non-pioupiou à l'axe du produit A.
    `str != frozenset(...)` est TOUJOURS vrai en Python : le filtre
    aurait alors exclu TOUTES les balises, pioupiou comprise, et
    `delta_20m` aurait rendu un dict VIDE sans lever — silencieux à
    100 %.

    PI lui-même n'a pas suivi l'extension L7 (son axe vient encore de
    `quantification.balises_du_domaine()`, pioupiou seul) : une balise
    windsmobi doit donc ENTRER dans la boucle (elle est dans
    SOURCE_NOTEE) mais n'avoir AUCUNE correction PI, comme un défaut de
    correspondance ordinaire — pas un crash, pas un Δ inventé.
    """
    balises = BALISES + [
        {"id": "W-9", "lat": 45.70, "lon": 6.05, "nom": "Un capteur windsmobi",
         "source": "windsmobi", "position_suspecte": False},
    ]
    col, man = archive_a(lambda k, s: (3.0, 4.0), lambda k, s: (2.0, 0.0),
                         balises=balises)
    # L'axe PI ne connaît QUE les deux balises pioupiou d'origine — comme
    # en production aujourd'hui.
    d_pi, m_pi = archive_pi(lambda i, m: (5.0, 1.0))
    d = A.delta_20m(col, d_pi, m_pi, crier=muet)

    verifie(len(d) >= 1 and any(k < 2 for k in d),
            f"les balises pioupiou reçoivent toujours leur Δ malgré la "
            f"troisième balise (windsmobi) dans l'axe — clés {sorted(d)}")
    k_windsmobi = next(k for k, b in enumerate(col.balises)
                       if b["id"] == "W-9")
    verifie(k_windsmobi not in d,
            f"la balise windsmobi N'A PAS de Δ (absente de l'axe PI) — "
            f"ni erreur, ni Δ inventé — clés {sorted(d)}")

    ids_agrume = {r["station_id"]
                 for r in A.lignes(col, man, model="agrume")}
    verifie("W-9" in ids_agrume,
            "la série agrume (NON corrigée) porte bien la balise "
            "windsmobi — c'est `lignes()`, pas `delta_20m`, qui décide "
            "de qui est noté")
    ids_pi = {r["station_id"]
             for r in A.lignes(col, man, model=A.MODEL_PI, delta=d)}
    verifie("W-9" not in ids_pi,
            f"…mais la série agrume_pi ne la porte PAS, faute de "
            f"correction — {sorted(ids_pi)}")


# ══════════════════════════════════════════════════════════════════
#  4. LES RADIOSONDAGES RESTENT DEHORS
# ══════════════════════════════════════════════════════════════════

def test_radiosondages_hors_serie_pi():
    col, man = archive_a(lambda k, s: (3.0, 4.0), lambda k, s: (2.0, 0.0))
    d_pi, m_pi = archive_pi(lambda i, m: (5.0, 1.0))
    d = A.delta_20m(col, d_pi, m_pi, crier=muet)
    verifie(2 not in d,
            "le point de radiosondage n'a pas de Δ : il n'a pas "
            "d'anémomètre au sol, une prévision de vent 10 m au-dessus "
            "d'une station de lâcher ne s'apparie à rien")
    ids = {r["station_id"] for r in A.lignes(col, man, model=A.MODEL_PI,
                                             delta=d)}
    verifie(ids == {"70", "1377"},
            f"la série PI ne porte que les balises Pioupiou — {sorted(ids)}")


# ══════════════════════════════════════════════════════════════════
#  5. Δ SE MESURE EN 0,025°, MÊME SI LA BASE EST EN 0,01°
# ══════════════════════════════════════════════════════════════════

def test_delta_pris_dans_la_bonne_maille():
    """⛔ LE PIÈGE QUI CRÉDITERAIT PI D'UNE DIFFÉRENCE DE RÉSOLUTION.

    Le 20 m existe dans LES DEUX mailles du produit A. PI vit en
    0,025°. Prendre `PI(0,025°) − AROME(0,01°)` ferait entrer dans Δ
    l'écart entre deux orographies et deux plus proches voisins — un
    écart bien réel, mais qui n'est pas l'apport d'AROME-PI.

    Ici les deux 20 m portent des valeurs DIFFÉRENTES. Un seul choix
    donne le bon Δ.
    """
    col, man = archive_a(lambda k, s: (3.0, 4.0),
                         lambda k, s: (2.0, 0.0),        # 20 m en 0,025°
                         base20_fine=lambda k, s: (-7.0, 0.0))  # en 0,01°
    d_pi, m_pi = archive_pi(lambda i, m: (5.0, 0.0))
    d = A.delta_20m(col, d_pi, m_pi, crier=muet)
    # ⛔ Les facteurs EN DUR (cf. le banc du 10 m) : α = 0,5, κ = 0,766.
    # Ce qui discrimine reste ENTIER — 3 contre 12 avant pondération,
    # donc 1,149 contre 4,596 après : les deux mailles ne peuvent pas
    # se confondre, quelle que soit la pondération.
    bon, mauvais = 3.0 * 0.5 * 0.766, 12.0 * 0.5 * 0.766
    verifie(abs(d[0][0][0] - bon) < 1e-6,
            f"Δu = α·κ·(PI − AROME(0,025°)) = α·κ·(5 − 2) = {bon:.3f} — "
            f"lu {d[0][0][0]:.3f} (le 0,01° aurait donné {mauvais:.3f})")


# ══════════════════════════════════════════════════════════════════
#  6. LES ÉCHÉANCES SE RANGENT PAR VALEUR, PAS PAR POSITION
# ══════════════════════════════════════════════════════════════════

def test_echeances_par_valeur_sur_run_troue():
    """⛔ SUR UN RUN CONTIGU, `.get(i)` ET `.get(step)` COÏNCIDENT.

    C'est précisément pourquoi la confusion passerait inaperçue jusqu'au
    premier run troué — et les runs troués existent, c'est le défaut de
    dé-accumulation positionnelle de l'audit du 13/08.

    Ici AROME saute les heures 3 et 4. Δ ne doit corriger que les heures
    0, 1, 2 et 5 — à LEUR place dans la série, pas à leur rang.
    """
    steps = [0, 1, 2, 5, 6, 7]
    col, man = archive_a(lambda k, s: (3.0, 4.0), lambda k, s: (2.0, 0.0),
                         steps=steps)
    d_pi, m_pi = archive_pi(lambda i, m: (6.0, 0.0))
    d = A.delta_20m(col, d_pi, m_pi, crier=muet)

    verifie(sorted(d[0]) == [0, 1, 2, 5],
            f"Δ n'existe qu'aux heures qu'AROME sert réellement — "
            f"{sorted(d[0])} (3 et 4 manquent au run)")

    rows = par_id(list(A.lignes(col, man, model=A.MODEL_PI, delta=d)))
    brut = par_id(list(A.lignes(col, man)))
    r, b = rows["70"], brut["70"]
    verifie(r["speed"][3] is None and r["speed"][4] is None,
            "les heures absentes du run le restent — aucune valeur "
            "n'a glissé dans le trou")
    verifie(r["speed"][5] != b["speed"][5],
            f"l'heure 5 EST corrigée bien qu'elle soit en 4ᵉ position "
            f"du tableau ({r['speed'][5]:.2f} ≠ {b['speed'][5]:.2f})")
    verifie(r["speed"][6] == b["speed"][6] and r["speed"][7] == b["speed"][7],
            "les heures 6 et 7 restent brutes — la rampe est arrivée à "
            "zéro, et rien n'a débordé d'un cran")


# ══════════════════════════════════════════════════════════════════
#  7. UN NaN NE DEVIENT PAS UN ZÉRO
# ══════════════════════════════════════════════════════════════════

def test_nan_pi_replie_sur_arome():
    """⛔ « PI NE CORRIGE RIEN ICI » EST UNE AFFIRMATION.

    Un Δ nul posé sur une heure où PI n'a pas de valeur dirait que PI a
    regardé et n'a rien trouvé à corriger. Ne rien poser dit qu'on ne
    sait pas — et c'est ce qui est vrai. À l'écran comme au score, la
    différence entre les deux est exactement la différence entre une
    mesure et une invention.
    """
    col, man = archive_a(lambda k, s: (3.0, 4.0), lambda k, s: (2.0, 0.0))
    d_pi, m_pi = archive_pi(
        lambda i, m: None if m == 120 else (6.0, 0.0))
    d = A.delta_20m(col, d_pi, m_pi, crier=muet)
    verifie(2 not in d[0] and sorted(d[0]) == [0, 1, 3, 4, 5],
            f"l'heure sans valeur PI n'a pas de Δ — {sorted(d[0])}")

    rows = par_id(list(A.lignes(col, man, model=A.MODEL_PI, delta=d)))
    brut = par_id(list(A.lignes(col, man)))
    verifie(rows["70"]["speed"][2] == brut["70"]["speed"][2],
            "elle retombe sur AROME seul, à l'identique — un repli, "
            "pas un zéro")
    verifie(rows["70"]["agrume_pi_heures"] == 5,
            f"et la ligne DIT combien d'heures PI a réellement portées "
            f"({rows['70']['agrume_pi_heures']}) — sans ce compte, une "
            f"ligne à peine corrigée serait indistinguable d'une ligne "
            f"pleinement composite")


# ══════════════════════════════════════════════════════════════════
#  8. UNE BALISE SANS PI NE GONFLE PAS LA SÉRIE
# ══════════════════════════════════════════════════════════════════

def test_population_de_la_serie_pi():
    """⚠️ Une balise hors couverture PI sortirait IDENTIQUE à `agrume`.

    Le score absolu d'`agrume_pi` se lirait alors « PI n'apporte presque
    rien » alors qu'il dirait « PI n'était pas là ». La population de la
    série PI est donc un sous-ensemble strict, et c'est ce qui garde le
    contrôle apparié honnête.
    """
    col, man = archive_a(lambda k, s: (3.0, 4.0), lambda k, s: (2.0, 0.0))
    d_pi, m_pi = archive_pi(lambda i, m: (5.0, 1.0),
                            servie=lambda i: i != "1377")
    d = A.delta_20m(col, d_pi, m_pi, crier=muet)
    ids = {r["station_id"] for r in A.lignes(col, man, model=A.MODEL_PI,
                                             delta=d)}
    verifie(ids == {"70"},
            f"seule la balise couverte par PI entre dans la série — "
            f"{sorted(ids)}")

    # ⛔ ET LA SÉRIE `agrume` NE BOUGE PAS D'UNE LIGNE. C'est la
    # condition qui rend le second nom utile : si la présence de PI
    # changeait `agrume`, la fenêtre glissante mélangerait deux
    # définitions et la comparaison ne comparerait plus rien.
    ids_brut = {r["station_id"] for r in A.lignes(col, man)}
    verifie(ids_brut == {"70", "1377"},
            f"la série `agrume` garde sa population entière, "
            f"indépendamment de PI — {sorted(ids_brut)}")


# ══════════════════════════════════════════════════════════════════
#  9. LES DEUX AXES DE BALISES DOIVENT COÏNCIDER
# ══════════════════════════════════════════════════════════════════

def test_axe_npz_contre_manifeste():
    """⛔ L'AXE EST ÉCRIT DEUX FOIS, ET C'EST LE MANIFESTE QU'ON INDEXE.

    S'ils divergeaient, chaque Δ partirait sur la mauvaise balise en
    rendant des valeurs parfaitement crédibles. On ne suppose pas qu'ils
    coïncident : on le vérifie, et on s'arrête sinon.
    """
    d = np.zeros((2, len(NIVEAUX), len(MINUTES), 2), dtype=np.float32)
    tampon = io.BytesIO()
    np.savez_compressed(tampon, donnees=d,
                        balises=np.asarray(["70", "1377"]))
    npz = tampon.getvalue()
    man = ('{"run": "%s", "parametres": [{"nom": "u"}, {"nom": "v"}], '
           '"niveaux_m_sol": [10, 20, 50, 100, 250, 500], '
           '"echeances_min": [0], '
           '"balises": [{"id": "1377"}, {"id": "70"}]}' % RUN).encode()

    ancien = A._lire_paire_r2
    try:
        A._lire_paire_r2 = lambda base, crier=print, quoi="": (man, npz)
        try:
            A.lire_run_pi(RUN, crier=muet)
            verifie(False, "un axe divergent doit faire s'arrêter la lecture")
        except A.Abort as exc:
            verifie("mauvaise balise" in str(exc),
                    "deux axes de balises divergents : la lecture "
                    "s'arrête au lieu de poser chaque Δ à côté")
    finally:
        A._lire_paire_r2 = ancien

    # Et le cas nominal passe — le banc ne doit pas être vert par
    # aveuglement.
    man_ok = man.replace(b'[{"id": "1377"}, {"id": "70"}]',
                         b'[{"id": "70"}, {"id": "1377"}]')
    try:
        A._lire_paire_r2 = lambda base, crier=print, quoi="": (man_ok, npz)
        donnees, m = A.lire_run_pi(RUN, crier=muet)
        verifie(donnees.shape[-1] == 2 and len(m["balises"]) == 2,
                "un axe cohérent se lit normalement")
    finally:
        A._lire_paire_r2 = ancien


# ══════════════════════════════════════════════════════════════════
#  10. Δ S'AJOUTE SUR u ET v, JAMAIS SUR L'ANGLE
# ══════════════════════════════════════════════════════════════════

def test_delta_sur_uv_jamais_sur_l_angle():
    """⛔ LE PASSAGE DE 350° À 010°, ET LES 180° QU'IL COÛTE.

    C'est la règle du composite (`arome_interpole` la porte mot pour
    mot) et elle vaut ici : moyenner ou additionner des ANGLES autour du
    nord rend le vent exactement à l'opposé, et rien ne lève.

    On pose une base qui vient d'à peu près 350° et un Δ qui la pousse
    de l'autre côté du nord. Un code qui travaillerait sur l'angle
    rendrait quelque chose autour de 180°.
    """
    base = (0.5, 2.0)          # souffle vers le NNE → vient du SSO (~194°)
    col, man = archive_a(lambda k, s: base, lambda k, s: (0.0, 0.0))
    d_pi, m_pi = archive_pi(lambda i, m: (-1.0, 0.0))
    d = A.delta_20m(col, d_pi, m_pi, crier=muet)

    j10 = col.i_niveau_001[10]
    u = float(col.c001[0, col.i_param_001["u"], j10, 0]) + d[0][0][0]
    v = float(col.c001[0, col.i_param_001["v"], j10, 0]) + d[0][0][1]
    attendu = decorer_vent({"u": u, "v": v})

    rows = par_id(list(A.lignes(col, man, model=A.MODEL_PI, delta=d)))
    lu = rows["70"]["dir"][0]
    verifie(abs(lu - attendu["directionDeg"]) < 1e-9,
            f"la direction sort de la SOMME des vecteurs "
            f"({lu:.1f}°), pas d'un calcul sur les angles")

    brut = par_id(list(A.lignes(col, man)))["70"]["dir"][0]
    milieu = (lu + brut) / 2.0
    verifie(abs(lu - milieu) > 1.0,
            f"et elle n'est pas la moyenne des deux angles "
            f"({brut:.2f}° et {lu:.1f}°) — le piège aurait la même "
            f"tête sur une base loin du nord")


# ══════════════════════════════════════════════════════════════════
#  11. LES DEUX SÉRIES, BOUT À BOUT
# ══════════════════════════════════════════════════════════════════

def test_deux_series_dans_un_seul_flux():
    """Le contrôle apparié : mêmes balises, mêmes heures, un seul run.

    ⓘ `score.py` relit un flux et lit `model` ligne par ligne — deux
    noms de modèles dans la même archive ne se marchent pas dessus, la
    clé d'upsert de `model_verif_daily` étant
    `(day, source, station_id, model, lead_h, fcst_src)`.
    """
    col, man = archive_a(lambda k, s: (3.0, 4.0), lambda k, s: (2.0, 0.0))
    d_pi, m_pi = archive_pi(lambda i, m: (5.0, 1.0))
    d = A.delta_20m(col, d_pi, m_pi, crier=muet)

    rows = list(A.lignes(col, man)) + list(A.lignes(
        col, man, model=A.MODEL_PI, delta=d,
        extra={"agrume_pi_run": m_pi["run"],
               "agrume_delta_mesure_m": A.NIVEAU_DELTA_MESURE,
               "agrume_delta_applique_m": A.NIVEAU_DELTA_APPLIQUE}))

    modeles = {r["model"] for r in rows}
    verifie(modeles == {"agrume", "agrume_pi"},
            f"deux séries, deux noms, un seul flux — {sorted(modeles)}")

    a = [r for r in rows if r["model"] == "agrume"]
    p = [r for r in rows if r["model"] == "agrume_pi"]
    verifie({r["station_id"] for r in p} <= {r["station_id"] for r in a},
            "la population PI est un sous-ensemble de celle d'`agrume` — "
            "c'est ce qui rend la différence de score attribuable à PI "
            "et à rien d'autre")
    verifie(all(r["t0"] == a[0]["t0"] for r in rows)
            and len({r["agrume_run"] for r in rows}) == 1,
            "même run et même t0 des deux côtés : aucun avantage de "
            "fraîcheur ne peut se glisser dans la comparaison")
    verifie(all(r.get("agrume_pi_run") == RUN for r in p),
            "et la ligne PI porte le run PI dont elle sort")

    diff = [h for h in range(24)
            if par_id(a)["70"]["speed"][h] != par_id(p)["70"]["speed"][h]]
    verifie(diff == [0, 1, 2, 3, 4, 5],
            f"les deux séries ne diffèrent QUE sur les 6 heures que PI "
            f"couvre — {diff}")




# ══════════════════════════════════════════════════════════════════
#  12. BOUT À BOUT — `score.py` note bien les DEUX séries
# ══════════════════════════════════════════════════════════════════

JOUR = __import__("datetime").datetime(
    2026, 8, 12, tzinfo=__import__("datetime").timezone.utc)


def _obs(speed_kmh, dir_deg):
    """Une balise Pioupiou qui relève toutes les 10 min, toute la
    journée."""
    t0 = int(JOUR.timestamp())
    t, sp, di = [], [], []
    for h in range(24):
        for m in range(0, 60, 10):
            t.append(t0 + h * 3600 + m * 60)
            sp.append(speed_kmh)
            di.append(dir_deg)
    return {"source": "pioupiou", "station_id": "70",
            "t": t, "speed": sp, "dir": di}


def _scorer(u_pi):
    """Les deux séries, passées dans `score.daily_rows`. Rend
    `{model: ligne}`.

    AROME souffle à 8 m/s d'ouest ; la balise relève 20 km/h d'ouest
    (≈ 5,56 m/s). `u_pi` décide si PI pousse vers la vérité ou s'en
    éloigne — et c'est ce qui donne au banc son SIGNE.
    """
    import score as SC

    col, man = archive_a(lambda k, s: (8.0, 0.0), lambda k, s: (8.0, 0.0))
    d_pi, m_pi = archive_pi(lambda i, m: (u_pi, 0.0))
    d = A.delta_20m(col, d_pi, m_pi, crier=muet)
    rows = ([r for r in A.lignes(col, man) if r["station_id"] == "70"]
            + [r for r in A.lignes(col, man, model=A.MODEL_PI, delta=d)
               if r["station_id"] == "70"])
    scores, _ = SC.daily_rows(JOUR, {0: rows, 1: [], 2: []},
                              [_obs(20.0, 270.0)], [], 7200)
    return {r["model"]: r for r in scores}


def test_bout_a_bout_les_deux_series_sont_notees():
    """⛔ DEUX MODÈLES DANS UN SEUL FLUX NE SE MARCHENT PAS DESSUS.

    C'est la seule chose que ce branchement demandait à `score.py`, et
    elle se vérifie plutôt qu'elle ne se déduit de la clé d'upsert.
    """
    s = _scorer(u_pi=20.0 / 3.6)          # PI vise la vérité
    verifie(set(s) == {"agrume", "agrume_pi"},
            f"les deux séries sortent notées — {sorted(s)}")
    if set(s) != {"agrume", "agrume_pi"}:
        return
    verifie(s["agrume_pi"]["lead_h"] == 6 and s["agrume"]["lead_h"] == 6,
            "toutes deux en classe +6 h — aucune ne gagne une classe "
            "par la fraîcheur")
    verifie(s["agrume_pi"]["n_hours"] == s["agrume"]["n_hours"] == 24,
            f"mêmes 24 heures appariées des deux côtés "
            f"({s['agrume']['n_hours']} et {s['agrume_pi']['n_hours']}) — "
            f"c'est ce qui rend l'écart attribuable à Δ seul")
    verifie(abs(s["agrume_pi"]["lead_exact_h"]
                - s["agrume"]["lead_exact_h"]) < 1e-9,
            "et le même `lead_exact_h` : PI ne rajeunit pas la série")


def test_bout_a_bout_le_score_suit_le_signe_de_delta():
    """⛔ LE BANC QUI PROUVE QUE Δ ARRIVE JUSQU'AU SCORE, ET DANS LE BON
    SENS.

    Tout le reste pourrait être vert avec un Δ qui n'atteint jamais la
    note. Ici PI vise d'abord la vérité (le score doit s'améliorer),
    puis s'en éloigne d'autant (il doit se dégrader). Un Δ ignoré
    rendrait les trois chiffres identiques.

    ⓘ On lit `err_vec_rms` et non `mse_model` : ce dernier
    n'existe que si la VEILLE des observations est fournie
    (`skill_vs_persistence`), et ce banc n'en a pas. Les deux
    sont moyennés, ce qui est la seule propriété qui compte ici.
    """
    vise = _scorer(u_pi=20.0 / 3.6)       # PI = l'observation
    rate = _scorer(u_pi=8.0 + (8.0 - 20.0 / 3.6))   # PI à l'opposé
    brut = vise["agrume"]["err_vec_rms"]
    verifie(vise["agrume_pi"]["err_vec_rms"] < brut,
            f"PI qui vise juste AMÉLIORE la série "
            f"({vise['agrume_pi']['err_vec_rms']:.2f} < {brut:.2f})")
    verifie(rate["agrume_pi"]["err_vec_rms"] > brut,
            f"PI qui se trompe la DÉGRADE "
            f"({rate['agrume_pi']['err_vec_rms']:.2f} > {brut:.2f})")
    verifie(abs(rate["agrume"]["err_vec_rms"] - brut) < 1e-9,
            "et la série `agrume` ne bouge pas d'un chiffre entre les "
            "deux cas — elle est bien indépendante de PI")


def test_bout_a_bout_la_mediane_est_structurellement_aveugle():
    """⚠️⚠️ LE RÉSULTAT LE PLUS IMPORTANT DE CE BANC, ET IL N'EST PAS
    UN SUCCÈS.

    `err_vec_med` est une MÉDIANE sur les 24 heures de la journée. PI
    n'en corrige que 6 (dont la dernière à demi). Les 18 heures
    restantes décident donc seules du 12ᵉ et du 13ᵉ rang — et la médiane
    ne peut PAS bouger, quelle que soit la qualité de Δ.

    ⛔ Ce n'est pas un défaut du branchement : c'est une propriété de la
    classe « +6 h ». Elle se constate ici, une fois, plutôt que de se
    découvrir dans trois semaines devant deux colonnes identiques dont
    on conclurait « AROME-PI n'apporte rien ». **Ce que ce flux mesure
    utilement, ce sont les colonnes de MOYENNE (`err_vec_rms`,
    `mse_model`), pas la médiane.**
    """
    vise = _scorer(u_pi=20.0 / 3.6)
    verifie(vise["agrume_pi"]["err_vec_med"] == vise["agrume"]["err_vec_med"],
            f"`err_vec_med` est IDENTIQUE malgré un Δ parfait sur 6 h "
            f"({vise['agrume_pi']['err_vec_med']}) — la médiane de 24 "
            f"heures ne voit pas une correction qui n'en touche que 6")
    verifie(vise["agrume_pi"]["err_vec_rms"] != vise["agrume"]["err_vec_rms"],
            "…alors que `err_vec_rms`, lui, la voit — c'est cette "
            "colonne-là qu'il faudra lire pour juger AROME-PI")


# ══════════════════════════════════════════════════════════════════
#  ⚠️ L'ENTRÉE RESTE LA DERNIÈRE CHOSE DU FICHIER. Un banc ajouté APRÈS
#  elle ne serait jamais exécuté — et un banc qui ne tourne pas se lit
#  exactement comme un banc qui passe. (Constaté ici même le 26/08.)
# ══════════════════════════════════════════════════════════════════

def main() -> int:
    n = 0
    for nom, fn in list(globals().items()):
        if nom.startswith("test_") and callable(fn):
            titre = fn.__doc__.splitlines()[0] if fn.__doc__ else nom
            print(f"\n▶ {titre}")
            fn()
            n += 1
    print("\n" + "═" * 66)
    print(f"  {n} bancs exécutés")
    if ECHECS:
        print(f"❌ banc de la série agrume_pi : {len(ECHECS)} échec(s)")
        for e in ECHECS:
            print(f"   · {e}")
        return 1
    print("✅ banc de la série agrume_pi : tout est vert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
