#!/usr/bin/env python3
"""Banc du module IFS (lot L22b, 06/09/2026) — SANS RÉSEAU, SANS eccodes.

⛔ CE QU'IL VÉRIFIE N'EST PAS « ÇA MARCHE ». Comme les huit autres bancs
du paquet, il vérifie les façons qu'a ce module de casser EN SILENCE :

  · poser le domaine à 3 000 km de là parce que l'axe des longitudes
    commence à 180° et pas à −180 (le champ reste lisse, donc crédible) ;
  · choisir l'échéance par son NUMÉRO de pas au lieu de son heure valide
    (la coupe est décalée de plusieurs heures, et rien ne le dit) ;
  · interpoler en `p` au lieu de `log p` (biais d'altitude régulier) ;
  · dériver le bloc hauteur à travers de l'air SOUTERRAIN, ou le
    laisser vide sans que rien ne rougisse (`NaN` est légitime partout
    ailleurs — c'est le défaut trouvé le 06/09, 1,1 % du bloc rempli) ;
  · prendre un 404 « pas encore publié » pour une panne, ou l'inverse.

    python3 agrume/test_ifs.py
"""
from __future__ import annotations

import pathlib
import sys
from datetime import datetime, timezone

_ICI = pathlib.Path(__file__).resolve().parent
if str(_ICI) not in sys.path:
    sys.path.insert(0, str(_ICI))

import numpy as np                                          # noqa: E402

import ifs as I                                             # noqa: E402
from domaine import NIVEAUX_H_0025, NIVEAUX_P               # noqa: E402
from quantification import (PARAMS_0025, PARAMS_ISO,        # noqa: E402
                            PARAMS_SURFACE, Abort)

ECHECS: list[str] = []


def verifie(cond, message):
    if cond:
        print(f"  ✅ {message}")
    else:
        print(f"  ❌ {message}")
        ECHECS.append(message)


UTC = timezone.utc


# ══════════════════════════════════════════════════════════════════
#  1. L'ÉCHÉANCE SE CHOISIT PAR SON HEURE VALIDE
# ══════════════════════════════════════════════════════════════════

def test_echeances_par_heure_valide():
    print("\n▶ 1. l'échéance se choisit par l'heure VALIDE, pas par le numéro de pas")
    ag = datetime(2026, 9, 6, 0, tzinfo=UTC)

    verifie(I.echeances_cousues(ag, ag) == [54, 57, 60, 63, 66, 69, 72],
            "run IFS = run AGRUME : les pas SONT les heures (54 → 72)")

    # ⛔ le cas réel : IFS 12 Z de la veille au soir pour un AGRUME 00 Z
    veille = datetime(2026, 9, 5, 12, tzinfo=UTC)
    att = [54 + 12, 57 + 12, 60 + 12, 63 + 12, 66 + 12, 69 + 12, 72 + 12]
    verifie(I.echeances_cousues(ag, veille) == att,
            f"⭐ run IFS 12 h PLUS TÔT : les pas sont décalés de +12 "
            f"({att[0]} → {att[-1]}), pas 54 → 72 — prendre le numéro "
            f"servirait une coupe en avance de 12 h")

    # le run IFS mesuré le 06/09 : 12 Z du MÊME jour, AGRUME 00 Z
    meme = datetime(2026, 9, 6, 12, tzinfo=UTC)
    verifie(I.echeances_cousues(ag, meme) == [42, 45, 48, 51, 54, 57, 60],
            "run IFS 12 h PLUS TARD : pas 42 → 60, et ce sont bien les "
            "heures 54 → 72 après AGRUME")

    verifie(len(I.echeances_cousues(ag, ag)) == 7,
            "sept échéances, jamais huit : la fenêtre est fermée à 72 h")
    # ⛔ LA PROPRIÉTÉ GÉNÉRALE, sur les 4 réseaux IFS × les 2 runs AGRUME
    # admis (00 et 03 Z) : toute heure valide rendue tombe DANS la
    # fenêtre, et tout pas rendu est un multiple du pas natif.
    dedans = True
    for h_ag in (0, 3):
        a = datetime(2026, 9, 6, h_ag, tzinfo=UTC)
        for j, h_ifs in ((5, 18), (6, 0), (6, 6), (6, 12)):
            r = datetime(2026, 9, j, h_ifs, tzinfo=UTC)
            for st in I.echeances_cousues(a, r):
                hv = (r.timestamp() + st * 3600 - a.timestamp()) / 3600
                dedans &= (I.DEBUT_H <= hv <= I.FIN_H) and st % I.PAS_IFS_H == 0
    verifie(dedans,
            "⭐ sur les 4 réseaux IFS × les 2 runs AGRUME admis, toute "
            "heure valide rendue est dans [54, 72] h après AGRUME, et tout "
            "pas est un multiple de 3 h")
    # ⚠️ En pratique le décalage est TOUJOURS un multiple de 3 h (AGRUME
    # à 00/03 Z contre IFS à 00/06/12/18 Z). S'il ne l'était pas, les
    # heures resteraient dans la fenêtre — décalées, jamais arrondies.
    une_h = I.echeances_cousues(ag, datetime(2026, 9, 6, 1, tzinfo=UTC))
    verifie(all(s % 3 == 0 for s in une_h)
            and all(I.DEBUT_H <= s + 1 <= I.FIN_H for s in une_h),
            f"un décalage d'une heure ne fabrique aucune échéance hors "
            f"fenêtre ({une_h})")


# ══════════════════════════════════════════════════════════════════
#  2. UN RUN NON PUBLIÉ N'EST PAS UNE PANNE
# ══════════════════════════════════════════════════════════════════

def test_choix_du_run():
    print("\n▶ 2. le choix du run : un 404 fait reculer, une panne remonte")
    ag = datetime(2026, 9, 6, 0, tzinfo=UTC)
    maintenant = datetime(2026, 9, 6, 20, 55, tzinfo=UTC)
    demandes: list[str] = []

    def tete_18_absent(url):
        demandes.append(url)
        return None if "/18z/" in url else "Sun, 06 Sep 2026 19:34:00 GMT"

    choix = I.run_disponible(ag, maintenant, tete=tete_18_absent,
                             crier=lambda *a: None)
    verifie(choix is not None and choix[0] == datetime(2026, 9, 6, 12, tzinfo=UTC),
            f"⭐ le 18 Z n'est pas publié : on recule au 12 Z "
            f"({choix and choix[0].isoformat()})")
    verifie(choix and choix[1] == [42, 45, 48, 51, 54, 57, 60],
            "… et les pas suivent le run choisi, pas la fenêtre nominale")
    verifie(len(demandes) == 2 and demandes[-1].endswith("-60h-oper-fc.index"),
            f"⭐ UNE sonde par run, sur le DERNIER pas seulement "
            f"({len(demandes)} requêtes, la dernière : "
            f"{demandes[-1].rsplit('-', 3)[-3] if demandes else '?'}h) — les "
            f"sept pas sont publiés au même instant, mesuré")

    def tete_tout_absent(url):
        return None
    verifie(I.run_disponible(ag, maintenant, tete=tete_tout_absent,
                             crier=lambda *a: None) is None,
            "aucun run publié → `None`, et l'appelant décide (il ne lève pas)")

    def tete_qui_casse(url):
        raise RuntimeError("500 chez ECMWF")
    try:
        I.run_disponible(ag, maintenant, tete=tete_qui_casse,
                         crier=lambda *a: None)
        vu = False
    except RuntimeError:
        vu = True
    verifie(vu, "⛔ une VRAIE panne remonte — elle ne se lit pas « le run "
                "n'est pas là » et ne fait pas reculer la chaîne en silence")

    # ⛔ le plafond de recul : un run vieux de 24 h couvrirait la fenêtre
    vieux = []
    def tete_compte(url):
        vieux.append(url)
        return None
    I.run_disponible(ag, maintenant, reculs=4, tete=tete_compte,
                     crier=lambda *a: None)
    verifie(len(vieux) <= 5,
            f"on ne recule pas indéfiniment ({len(vieux)} réseaux essayés, "
            f"plafond 5) — un run de 24 h serait accepté en silence")


# ══════════════════════════════════════════════════════════════════
#  3. LA SÉLECTION, ET LE PIÈGE DU `levelist` EN CHAÎNE
# ══════════════════════════════════════════════════════════════════

def _index_synthetique():
    msgs, off = [], 0
    for p in ("u", "v", "t", "gh", "q", "r", "w", "vo", "d", "z"):
        for n in I.NIVEAUX_IFS:
            msgs.append({"levtype": "pl", "param": p, "levelist": str(n),
                         "_offset": off, "_length": 700_000})
            off += 700_000
    for p in ("10u", "10v", "2t", "msl", "sp", "tp", "skt", "tcc"):
        msgs.append({"levtype": "sfc", "param": p, "_offset": off,
                     "_length": 600_000})
        off += 600_000
    return msgs


def test_selection_et_plages():
    print("\n▶ 3. la sélection ne prend que ce qui a une case dans le produit B")
    msgs = _index_synthetique()
    sel = I.selection(msgs)
    verifie(len(sel) == 6 * 7 + 5,
            f"6 champs × 7 niveaux communs + 5 champs de surface = 47 "
            f"({len(sel)}) — le compte MESURÉ sur le run réel du 06/09")
    niv = {int(m["levelist"]) for m in sel if m["levtype"] == "pl"}
    verifie(niv == set(I.NIVEAUX_COMMUNS),
            f"⭐ SEULS les 7 niveaux que `NIVEAUX_P` partage ({sorted(niv, reverse=True)}) "
            f"— au-dessus de 400 hPa le produit B n'a aucune case à remplir")
    verifie(not any(m["param"] in ("w", "vo", "d", "z") for m in sel),
            "⛔ `z` (géopotentiel m²/s²) N'EST PAS pris : c'est `gh` qu'on "
            "lit, déjà en mètres — diviser deux fois par g donne des "
            "altitudes plausibles, donc invisibles")
    verifie(not any(m.get("param") in ("tp", "skt", "tcc") for m in sel),
            "les champs de surface hors cadrage ne sont pas tirés")

    # ⛔ le piège : `levelist` est une CHAÎNE dans l'index
    verifie(all(isinstance(m["levelist"], str)
                for m in msgs if m["levtype"] == "pl"),
            "l'index porte `levelist` en CHAÎNE (c'est le fichier réel) ; "
            "une comparaison sans `int()` rendrait une sélection VIDE, un "
            "tirage réussi et une grille toute en NaN")

    pl = I.plages(sel)
    verifie(len(pl) < len(sel),
            f"les plages contiguës sont fusionnées ({len(sel)} messages → "
            f"{len(pl)} plages)")
    verifie(all(a < b for a, b in pl) and
            all(pl[k][1] <= pl[k + 1][0] for k in range(len(pl) - 1)),
            "… et elles sortent ordonnées, sans recouvrement")
    verifie(sum(b - a for a, b in pl) == sum(m["_length"] for m in sel),
            "… en couvrant exactement les octets demandés, pas un de plus")


# ══════════════════════════════════════════════════════════════════
#  4. LE RÉGRILLAGE, ET L'AXE QUI COMMENCE À 180°
# ══════════════════════════════════════════════════════════════════

def test_regrillage():
    print("\n▶ 4. le régrillage, et le piège de l'axe des longitudes")
    lats = np.arange(46.45, 43.69, -0.025, dtype=np.float64)
    lons = np.arange(5.00, 7.61, 0.025, dtype=np.float64)
    R = I.Regrilleur(lats, lons)

    # Deux champs SYNTHÉTIQUES dont on connaît la valeur exacte partout :
    # la latitude et la longitude du point source lui-même.
    lat_src = np.repeat(np.linspace(90.0, -90.0, I.SRC_NJ)[:, None],
                        I.SRC_NI, axis=1).astype(np.float32)
    lon_src = np.tile((((np.arange(I.SRC_NI) * I.SRC_PAS + I.SRC_LON0)
                        % 360.0))[None, :], (I.SRC_NJ, 1)).astype(np.float32)
    e_lat = np.abs(R(lat_src) - lats[:, None]).max()
    verifie(e_lat < 1e-4,
            f"⭐ le champ « latitude » se régrille en la latitude cible "
            f"(écart max {e_lat:.2e}°) — l'axe descend depuis 90 N")
    s, c = R(np.sin(np.radians(lon_src))), R(np.cos(np.radians(lon_src)))
    rec = np.degrees(np.arctan2(s, c)) % 360.0
    e_lon = np.abs(((rec - lons[None, :] + 180.0) % 360.0) - 180.0).max()
    verifie(e_lon < 1e-4,
            f"⭐⭐ le champ « longitude » se régrille en la longitude cible "
            f"(écart max {e_lon:.2e}°) — l'axe source commence à 180°")

    # ⓘ `(lon + 180)/0,25` est ÉQUIVALENTE sur [−180, 180[ — le module
    # l'annonçait fautive, ce banc l'a démentie, et le commentaire a été
    # corrigé. VERROUILLÉ ici pour que personne ne « répare » une
    # formule qui est juste.
    equiv = all(int((lo + 180.0) / I.SRC_PAS) % I.SRC_NI
                == int(((lo - I.SRC_LON0) % 360.0) / I.SRC_PAS) % I.SRC_NI
                for lo in (-1.85, 0.0, 5.0, 7.6, 9.5))
    verifie(equiv,
            "ⓘ `(lon + 180)/0,25` et `((lon − 180) mod 360)/0,25` donnent le "
            "MÊME indice sur [−180, 180[ — ce n'est pas là qu'est le piège")

    # ⛔ LE VRAI PIÈGE : supposer la grille calée sur Greenwich.
    i_g = int((lons[0] % 360.0) / I.SRC_PAS) % I.SRC_NI
    lon_g = (i_g * I.SRC_PAS + I.SRC_LON0) % 360.0
    ecart_km = abs(((lon_g - lons[0] + 180) % 360) - 180) * 111.0
    verifie(ecart_km > 10_000.0,
            f"⛔⛔ `i = lon/0,25` (la grille commence à Greenwich — la "
            f"convention la plus répandue) lit le domaine à {ecart_km:.0f} km "
            f"de là, au milieu du Pacifique, et le champ reste lisse")

    # ⛔ ET SON JUMEAU : supposer que les latitudes MONTENT depuis −90.
    j_sud = int((lats[0] + 90.0) / I.SRC_PAS)
    lat_sud = I.SRC_LAT0 - j_sud * I.SRC_PAS
    verifie(lat_sud < 0.0,
            f"⛔ supposer `jScansPositively = 1` bascule le domaine dans "
            f"l'hémisphère sud ({lat_sud:.2f}° au lieu de {lats[0]:.2f}°)")

    # un champ constant reste constant (pas de fuite d'indice)
    verifie(np.allclose(R(np.full((I.SRC_NJ, I.SRC_NI), 3.5, np.float32)), 3.5),
            "un champ constant se régrille en ce constant")
    verifie(R(lat_src).shape == (len(lats), len(lons)),
            "la sortie a la forme de la grille du domaine")


# ══════════════════════════════════════════════════════════════════
#  5. LA VERTICALE : `log p`, ET LES NATIFS RECOPIÉS
# ══════════════════════════════════════════════════════════════════

def test_interpolation_verticale():
    print("\n▶ 5. l'interpolation verticale se fait en log p")
    poids = I.poids_log_p()
    verifie(len(poids) == len(NIVEAUX_P), "un poids par niveau de NIVEAUX_P")
    natifs = [k for k, (a, b, w) in enumerate(poids) if a == b]
    verifie([NIVEAUX_P[k] for k in natifs] == list(I.NIVEAUX_COMMUNS),
            "⭐ les 7 niveaux natifs se RECOPIENT (poids nul), ils ne "
            "s'interpolent pas")

    # ⛔ log p contre p : l'écart, mesuré sur le niveau 950
    k = NIVEAUX_P.index(950)
    a, b, w = poids[k]
    w_lin = (I.NIVEAUX_COMMUNS[a] - 950) / (I.NIVEAUX_COMMUNS[a] - I.NIVEAUX_COMMUNS[b])
    verifie(abs(w - w_lin) > 1e-4,
            f"⛔ à 950 hPa, le poids en log p ({w:.4f}) diffère du poids "
            f"linéaire en p ({w_lin:.4f}) — sur un intervalle de ~650 m, "
            f"c'est un décalage systématique de l'axe vertical")

    pile = np.stack([np.full((3, 4), float(k)) for k in range(7)]).astype(np.float32)
    out = I.interpoler_log_p(pile, poids)
    verifie(out.shape == (14, 3, 4), f"7 niveaux → 14 ({out.shape})")
    for k, n in enumerate(NIVEAUX_P):
        if n in I.NIVEAUX_COMMUNS:
            verifie(np.array_equal(out[k], pile[I.NIVEAUX_COMMUNS.index(n)]),
                    f"… {n} hPa sort bit à bit ce que le GRIB portait") \
                if n == 850 else None
    croissant = all(out[k].mean() <= out[k + 1].mean() + 1e-6
                    for k in range(13))
    verifie(croissant, "… et l'ordre des niveaux est préservé (monotone)")

    try:
        I.poids_log_p(cibles=(300,))
        leve = False
    except Abort:
        leve = True
    verifie(leve, "⛔ un niveau hors de la bande native lève — ce module "
                  "n'extrapole pas, même d'un demi-niveau")


# ══════════════════════════════════════════════════════════════════
#  6. LE BLOC HAUTEUR, ET L'AIR SOUTERRAIN
# ══════════════════════════════════════════════════════════════════

def _colonne(zsol, altitudes, valeurs):
    nj, ni = zsol.shape
    gh = np.stack([np.full((nj, ni), a, np.float32) for a in altitudes])
    v = np.stack([np.full((nj, ni), x, np.float32) for x in valeurs])
    return gh, v


def test_bloc_hauteur_derive():
    print("\n▶ 6. le bloc hauteur, dérivé — et l'air souterrain écarté")
    # une vallée à 200 m, un sommet à 3 000 m
    zsol = np.array([[200.0, 3000.0]], dtype=np.float32)
    # altitudes des 7 niveaux : 1000 hPa à 150 m (sous le sommet),
    # 925 à 800 m, 850 à 1500, 700 à 3100, 600 à 4400, 500 à 5800, 400 à 7200
    gh, u = _colonne(zsol, (150, 800, 1500, 3100, 4400, 5800, 7200),
                     (1, 2, 3, 4, 5, 6, 7))
    ancre = np.full((1, 2), 0.5, dtype=np.float32)

    h = I.deriver_hauteurs(u, gh, zsol, ancre=ancre)
    verifie(h.shape == (len(NIVEAUX_H_0025), 1, 2),
            f"25 niveaux AGL en sortie ({h.shape})")
    verifie(np.allclose(h[0], ancre),
            "⭐ le niveau 10 m/sol vaut EXACTEMENT le champ 10 m — la "
            "colonne est ANCRÉE sur une mesure, pas extrapolée")
    verifie(np.isfinite(h).all(),
            "⭐⭐ le bloc est PLEIN partout (25 niveaux × 2 colonnes) : "
            "c'est le défaut du 06/09 — une première version en "
            "remplissait 1,1 %, et aucun banc ne rougissait")

    # ⛔ dans la vallée (sol 200 m), 1000 hPa est à 150 m : SOUS le sol.
    # La valeur à 10 m/sol ne doit RIEN lui devoir.
    gh2, u2 = _colonne(zsol, (150, 800, 1500, 3100, 4400, 5800, 7200),
                       (-99, 2, 3, 4, 5, 6, 7))     # 1000 hPa = valeur absurde
    h2 = I.deriver_hauteurs(u2, gh2, zsol, ancre=ancre)
    verifie(np.allclose(h, h2, equal_nan=True),
            "⛔⛔ changer la valeur du niveau SOUTERRAIN ne change RIEN au "
            "bloc dérivé — l'air sous le terrain n'entre jamais dans la "
            "colonne (fait nº 5 du README AGRUME)")

    # au sommet (3 000 m), quatre niveaux sont sous le terrain
    verifie(np.isfinite(h[:, 0, 1]).all(),
            "… et la colonne du sommet, dont QUATRE niveaux sont "
            "souterrains, reste pleine grâce à l'ancre")

    # sans ancre : rien sous le premier niveau libre, et jamais un zéro
    hr = I.deriver_hauteurs(u, gh, zsol, ancre=None)
    verifie(not np.isfinite(hr[0]).any(),
            "⛔ SANS ancre (le cas de `r`), le 10 m/sol reste NaN — une "
            "absence, jamais un zéro ni une extrapolation vers le bas")
    verifie(np.isfinite(hr[-1]).all(),
            "… mais le haut de la colonne, lui, est bien renseigné")

    # ⭐ un profil LINÉAIRE en altitude se retrouve exactement
    gh3, u3 = _colonne(zsol, (150, 800, 1500, 3100, 4400, 5800, 7200),
                       (150, 800, 1500, 3100, 4400, 5800, 7200))
    h3 = I.deriver_hauteurs(u3, gh3, zsol,
                            ancre=(zsol + NIVEAUX_H_0025[0]).astype(np.float32))
    cible = np.stack([zsol + float(n) for n in NIVEAUX_H_0025])
    verifie(np.allclose(h3, cible, atol=1e-3),
            "⭐ un champ égal à l'altitude se dérive en l'altitude cible "
            "— l'interpolation ne décale pas la verticale")

    # aucune extrapolation au-dessus du plus haut niveau
    bas = np.array([[7000.0]], dtype=np.float32)
    gh4, u4 = _colonne(bas, (7050, 7100, 7150, 7200, 7250, 7300, 7350),
                       (1, 2, 3, 4, 5, 6, 7))
    h4 = I.deriver_hauteurs(u4, gh4, bas,
                            ancre=np.full((1, 1), 0.0, dtype=np.float32))
    verifie(not np.isfinite(h4[-1]).any(),
            "⛔ au-dessus du plus haut niveau, la valeur reste NaN — on "
            "ne prolonge pas la colonne au-delà de ce qu'on a")


# ══════════════════════════════════════════════════════════════════
#  7. CE QUE LE MANIFESTE DOIT DIRE
# ══════════════════════════════════════════════════════════════════

def test_manifeste():
    print("\n▶ 7. le manifeste nomme les niveaux NATIFS et ce qui manque")
    run = datetime(2026, 9, 6, 12, tzinfo=UTC)
    b = I.bloc_manifeste(run, [42, 45, 48, 51, 54, 57, 60],
                         last_modified="Sun, 06 Sep 2026 19:34:00 GMT")
    verifie(b["modele"] == "ecmwf_ifs025" and b["run_ifs"].endswith("T12:00:00Z"),
            "le modèle et le run IFS sont publiés en clair")
    verifie(b["niveaux_natifs"] == list(I.NIVEAUX_COMMUNS)
            and b["niveaux_interpoles"] == list(I.NIVEAUX_DERIVES),
            "⭐ les 7 natifs et les 7 interpolés sont NOMMÉS — `provenance()` "
            "ne peut pas dire « interpolé verticalement » en recoupant deux "
            "listes qu'il n'a pas")
    verifie(set(b["niveaux_natifs"]) | set(b["niveaux_interpoles"])
            == set(NIVEAUX_P),
            "… et les deux listes couvrent exactement NIVEAUX_P")
    verifie(b["publie_le"] and b["pas_natif_h"] == 3,
            "l'instant de publication et le pas natif y sont")

    # ⛔ ce qui manque est nommé, et les noms existent vraiment
    noms_h = {p["nom"] for p in PARAMS_0025}
    noms_iso = {p["nom"] for p in PARAMS_ISO}
    noms_surf = {p["nom"] for p in PARAMS_SURFACE}
    verifie(set(b["absents"]["hauteur"]) <= noms_h
            and set(b["absents"]["isobare"]) <= noms_iso
            and set(b["absents"]["surface"]) <= noms_surf,
            "⭐ les champs déclarés ABSENTS sont des noms de paramètres qui "
            "existent VRAIMENT dans le produit B — sinon le manifeste "
            "rassurerait sur des cases qui n'ont jamais existé")
    verifie("tke" in b["absents"]["hauteur"] and "cc" in b["absents"]["isobare"],
            "`tke` et `cc` sont déclarés absents : l'open data IFS ne les "
            "porte pas, et un silence se lirait « pas de turbulence »")


def main() -> int:
    print("═" * 66)
    print("  BANC DE LA RALLONGE IFS — lot L22b, 06/09/2026")
    print("═" * 66)
    test_echeances_par_heure_valide()
    test_choix_du_run()
    test_selection_et_plages()
    test_regrillage()
    test_interpolation_verticale()
    test_bloc_hauteur_derive()
    test_manifeste()
    print("\n" + "═" * 66)
    if ECHECS:
        print(f"❌ {len(ECHECS)} assertion(s) en échec :")
        for e in ECHECS:
            print(f"   · {e}")
        return 1
    print("✅ banc de la rallonge IFS : tout est vert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
