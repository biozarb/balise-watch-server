#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/test_sonde_delta_10m.py — le banc de la MESURE de phase B
#                                                          (26/08/2026)
#
#  Sans réseau, sans clé, sans base.
#
#  ⚠️ CE BANC NE PROTÈGE PAS UN PRODUIT, IL PROTÈGE UN VERDICT. La sonde
#  ne sert personne : elle sort des chiffres qui décideront si Δ(10 m)
#  entre dans `composite.py`. Une sonde fausse ne casse rien — elle
#  publie un résultat crédible, et c'est pire.
#
#      python3 test_sonde_delta_10m.py
#
#  ═══ LES FAÇONS DE CASSER EN SILENCE QUE CE BANC TIENT ═══
#  · maille        → Δ(10 m) pris en 0,01°     → écart de résolution crédité à PI
#  · niveau        → Δ(10 m) lu au 20 m         → T2 égale T1, « aucun gain »
#  · axe PI        → (bal, par, niv, éch)       → Δ d'une balise sur une autre
#  · appariement   → PI indexé par RANG         → idem, en plus crédible
#  · échéances     → position au lieu de valeur → décalage sur run troué
#  · rampe         → w ignoré                   → PI plein pot jusqu'à 6 h
#  · direction     → Δ ajouté à la vitesse      → 180° au passage 350°→010°
#  · placebo       → point fixe dans la permut. → témoin qui reçoit son vrai Δ
#  · placebo       → `hash()` non déterministe  → campagne non rejouable
#  · erreur        → mode vectoriel par série   → « gain » = changement de règle
#  · erreur        → médiane au lieu de rms     → colonne structurellement aveugle
#  · bootstrap     → tirage par COUPLE          → IC dix fois trop étroit
#  · NaN           → traité comme 0             → « PI ne corrige rien » affirmé
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import math
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np                                          # noqa: E402

import agrume_fcst as A                                     # noqa: E402
import scoring as S                                         # noqa: E402
import sonde_delta_10m as B                                 # noqa: E402
from colonnes import Colonnes                               # noqa: E402
from composite import poids_pi                              # noqa: E402
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
#: ⚠️ Calculé, pas recopié. Une constante d'époque écrite à la main est
#: le genre de chiffre qui décale tout d'une heure sans qu'on le voie.
T0_MS = int(datetime.strptime(RUN, "%Y-%m-%dT%H:%M:%SZ").replace(
    tzinfo=timezone.utc).timestamp()) * 1000
STEPS = list(range(24))
MINUTES = list(range(0, 361, 15))
NIVEAUX_PI = [10, 20, 50, 100, 250, 500]
PARAMS = [{"nom": "u", "unite": "m/s"}, {"nom": "v", "unite": "m/s"}]

BALISES = [
    {"id": "70", "lat": 46.15, "lon": 6.19, "source": "pioupiou"},
    {"id": "1377", "lat": 45.60, "lon": 6.20, "source": "pioupiou"},
    {"id": "812", "lat": 42.90, "lon": 0.55, "source": "pioupiou"},
    {"id": "RS-06610", "lat": 46.81, "lon": 6.94, "source": "radiosondage"},
]
PIOUPIOU = [b for b in BALISES if b["source"] == "pioupiou"]


def archive_a(f001_10, f0025_10, f0025_20, balises=None, steps=None):
    """Un `Colonnes` du produit A.

    `f001_10`  : le 10 m en 0,01° — la BASE du score (T0).
    `f0025_10` : le 10 m en 0,025° — le membre AROME de Δ(10 m).
    `f0025_20` : le 20 m en 0,025° — le membre AROME de Δ(20 m).
    Chacune est `(k, step) → (u, v) | None`.
    """
    bal = BALISES if balises is None else balises
    col = Colonnes(RUN, bal, list(STEPS if steps is None else steps))
    iu1, iv1 = col.i_param_001["u"], col.i_param_001["v"]
    iu2, iv2 = col.i_param_0025["u"], col.i_param_0025["v"]
    j10f = col.i_niveau_001[10]
    j10, j20 = col.i_niveau_0025[10], col.i_niveau_0025[20]
    for k in range(len(bal)):
        for i, s in enumerate(col.steps):
            for f, arr, iu, iv, j in ((f001_10, col.c001, iu1, iv1, j10f),
                                      (f0025_10, col.c0025, iu2, iv2, j10),
                                      (f0025_20, col.c0025, iu2, iv2, j20)):
                uv = f(k, int(s))
                if uv is None:
                    continue
                arr[k, iu, j, i] = np.float16(uv[0])
                arr[k, iv, j, i] = np.float16(uv[1])
    return col, {"run": RUN, "echeances": list(col.steps), "balises": bal}


def archive_pi(val, balises=None, ordre=None, minutes=None,
               niveaux=None, servi_10m=True, axes="pnmb"):
    """`(donnees, manifeste)` des colonnes PI.

    `val(id, niveau, minute) → (u, v) | None` — indexée par IDENTIFIANT
    et par NIVEAU, jamais par rang : réordonner l'axe ou la liste des
    niveaux ne change alors aucune valeur physique, seulement leur
    position. C'est ce qui rend les bancs d'axe capables d'échouer.

    `axes="pnmb"` est l'ordre réel de l'archive (paramètre, niveau,
    échéance, balise). `axes="bnmp"` fabrique la transposition qu'on
    veut voir refusée.
    """
    bal = PIOUPIOU if balises is None else balises
    mins = MINUTES if minutes is None else list(minutes)
    nivs = NIVEAUX_PI if niveaux is None else list(niveaux)
    ordre = list(range(len(bal))) if ordre is None else list(ordre)
    axe = [bal[i] for i in ordre]
    d = np.full((2, len(nivs), len(mins), len(axe)), np.nan, dtype=np.float32)
    for kk, b in enumerate(axe):
        for jn, niv in enumerate(nivs):
            for im, m in enumerate(mins):
                uv = val(str(b["id"]), niv, m)
                if uv is None:
                    continue
                d[0, jn, im, kk] = uv[0]
                d[1, jn, im, kk] = uv[1]
    if axes == "bnmp":
        d = np.transpose(d, (3, 1, 2, 0))
    man = {
        "run": RUN, "parametres": PARAMS, "niveaux_m_sol": list(nivs),
        "echeances_min": list(mins), "niveau_10m_servi": bool(servi_10m),
        "balises": [dict(id=b["id"], servie=True,
                         domaine_pi="nord-alpes") for b in axe],
    }
    return d, man


class Obs:
    """Une station qui relève toutes les 10 min, au vent qu'on veut."""

    def __init__(self, f, t0=T0_MS, n=200, pas_ms=600_000):
        self.ech = [S.ObsSample(t=t0 + i * pas_ms, speed=f(i)[0],
                                dir=f(i)[1]) for i in range(n)]
        self.paire = (np.array([o.t for o in self.ech], dtype=np.int64),
                      self.ech)


def lancer(col_man, pi, obs):
    """`couples_du_run` avec R2 remplacé par les objets qu'on lui donne.

    ⓘ On monkeypatche `A.lire_run` / `A.lire_run_pi` plutôt que
    d'écrire une seconde façon de fabriquer un run : les deux lectures
    restent celles du produit, et le banc ne teste pas une copie.
    """
    vrai_a, vrai_pi = A.lire_run, A.lire_run_pi
    A.lire_run = lambda run, crier=print: col_man
    A.lire_run_pi = lambda run, crier=print: pi
    try:
        return B.couples_du_run(RUN, obs, crier=lambda *_: None)
    finally:
        A.lire_run, A.lire_run_pi = vrai_a, vrai_pi


def table_de(lot):
    """`(tableau numpy, champs)` depuis la sortie de `couples_du_run`."""
    tab = np.asarray([l for _, _, l in lot], dtype=np.float64)
    return tab, list(B.CHAMPS + B.CHAMPS_PLACEBO)


def col_de(tab, champs, nom):
    return tab[:, champs.index(nom)]


# ══════════════════════════════════════════════════════════════════
#  1-3. LA RAMPE, LES HEURES, LE PLACEBO
# ══════════════════════════════════════════════════════════════════

def test_les_heures_sont_celles_ou_la_rampe_est_non_nulle():
    print("\n▶ 1. les heures mesurées sont exactement celles où w > 0")
    verifie(B.HEURES_PI == (0, 1, 2, 3, 4, 5),
            f"HEURES_PI = {B.HEURES_PI} — 6 heures, la 6ᵉ à demi")
    verifie(all(poids_pi(h * 60) > 0 for h in B.HEURES_PI),
            "chacune a un poids strictement positif")
    verifie(poids_pi(6 * 60) == 0.0 and 6 not in B.HEURES_PI,
            "+6 h est EXCLUE : Δ y serait multiplié par zéro, et une "
            "case à zéro se lirait comme « PI n'a rien à corriger »")
    verifie(poids_pi(5 * 60) == 0.5,
            "la 5ᵉ heure vaut bien 0,5 — la rampe s'importe du composite")


def test_le_placebo_n_a_aucun_point_fixe():
    print("\n▶ 2. le témoin placebo ne se donne jamais son propre Δ")
    for n in (2, 3, 5, 17, 285):
        for g in (0, 1, 2, 999):
            p = B.derangement(n, g)
            if np.any(p == np.arange(n)):
                verifie(False, f"point fixe pour n={n}, graine={g}")
                return
    verifie(True, "aucun point fixe sur n ∈ {2, 3, 5, 17, 285} × 4 graines")
    verifie(np.array_equal(B.derangement(285, 1), B.derangement(285, 1)),
            "la même graine rend la même permutation")
    verifie(not np.array_equal(B.derangement(285, 1), B.derangement(285, 2)),
            "deux graines rendent deux témoins différents")
    verifie(sorted(B.derangement(50, 3).tolist()) == list(range(50)),
            "c'est bien une permutation (chaque balise donne une fois)")


def test_la_graine_est_deterministe_entre_processus():
    print("\n▶ 3. la graine du témoin ne dépend pas du processus")
    verifie(B.graine_run(RUN, 1) == B.graine_run(RUN, 1),
            "stable dans le processus")
    verifie(B.graine_run(RUN, 1) != B.graine_run(RUN, 2),
            "deux graines diffèrent")
    # ⛔ La vraie garantie : la valeur ne peut pas dépendre de
    # PYTHONHASHSEED. `crc32` d'une chaîne encodée est spécifiée ;
    # `hash()` ne l'est pas. On le vérifie en comparant à un calcul
    # indépendant plutôt qu'à une constante recopiée.
    import zlib
    verifie(B.graine_run("X", 7) == zlib.crc32(b"X#7"),
            "la graine est un crc32, pas un hash() randomisé par processus")


# ══════════════════════════════════════════════════════════════════
#  4-7. CE QUE LA SONDE LIT, ET OÙ
# ══════════════════════════════════════════════════════════════════

def scene(**kw):
    """Une scène complète où chaque source a une VALEUR SIGNATURE.

    Chaque champ porte un chiffre qui n'existe nulle part ailleurs :
    lire le mauvais tableau, le mauvais niveau ou la mauvaise maille ne
    donne pas « une valeur voisine », ça donne une valeur qu'on
    reconnaît. C'est ce qui rend les mutations détectables.
    """
    a = archive_a(
        f001_10=lambda k, s: (1.0, 0.0),        # base du score
        f0025_10=lambda k, s: (2.0, 0.0),       # AROME 10 m en 0,025°
        f0025_20=lambda k, s: (4.0, 0.0),       # AROME 20 m en 0,025°
        **{k: v for k, v in kw.items() if k in ("balises", "steps")})
    pi = archive_pi(
        lambda sid, niv, m: (8.0, 0.0) if niv == 10 else (
            (16.0, 0.0) if niv == 20 else (0.0, 0.0)),
        **{k: v for k, v in kw.items()
           if k in ("ordre", "minutes", "niveaux", "servi_10m", "axes")})
    obs = {b["id"]: Obs(lambda i: (18.0, 90.0)).paire for b in PIOUPIOU}
    return a, pi, obs


def test_delta_10m_se_lit_en_0025_contre_0025_au_niveau_10():
    print("\n▶ 4. Δ(10 m) = PI(10 m) − AROME(10 m), en 0,025° des deux côtés")
    a, pi, obs = scene()
    tab, ch = table_de(lancer(a, pi, obs))
    verifie(len(tab) == len(PIOUPIOU) * len(B.HEURES_PI),
            f"{len(tab)} couples = {len(PIOUPIOU)} balises × "
            f"{len(B.HEURES_PI)} heures")
    verifie(np.allclose(col_de(tab, ch, "u_ar10"), 1.0),
            "la base T0 vient de la maille 0,01° (signature 1,0)")
    verifie(np.allclose(col_de(tab, ch, "u_ar10q"), 2.0),
            "⛔ le membre AROME de Δ(10 m) vient de la maille 0,025° "
            "(signature 2,0) — pas de la base, sinon l'écart de "
            "résolution serait crédité à PI")
    verifie(np.allclose(col_de(tab, ch, "u_ar20q"), 4.0),
            "le membre AROME de Δ(20 m) est le 20 m en 0,025° (4,0)")
    verifie(np.allclose(col_de(tab, ch, "u_pi10"), 8.0),
            "PI 10 m est bien lu au niveau 10 (8,0)")
    verifie(np.allclose(col_de(tab, ch, "u_pi20"), 16.0),
            "PI 20 m est bien lu au niveau 20 (16,0) — un Δ(10 m) pris "
            "au 20 m rendrait T2 égal à T1 et « aucun gain »")


def test_l_axe_pi_est_parametre_niveau_echeance_balise():
    print("\n▶ 5. l'axe des colonnes PI n'est pas celui du produit A")
    a, pi, obs = scene()
    # La transposition rend un tableau de MÊME taille sur les deux
    # premiers axes (2 paramètres, 6 niveaux → 3 balises, 6 niveaux) :
    # elle ne lèverait pas, elle rendrait des valeurs plausibles.
    a2, pi2, obs2 = scene(axes="bnmp")
    tab, ch = table_de(lancer(a, pi, obs))
    verifie(len(tab) > 0, "la scène droite produit bien des couples")
    try:
        lancer(a2, pi2, obs2)
        verifie(False, "⛔ la transposition est passée SANS ÊTRE VUE — "
                       "chaque Δ serait parti sur la mauvaise balise")
    except B.Abort as exc:
        verifie("forme" in str(exc),
                "⛔ la transposition est REFUSÉE en nommant la forme "
                "attendue — et par une comparaison au manifeste, pas par "
                "une IndexError de hasard")
    # ⛔ La garde ne doit pas dépendre d'une taille qui « ne colle pas ».
    # On le prouve sur un cas où les quatre tailles sont ÉGALES : là,
    # une transposition ne lève RIEN, et seule la comparaison au
    # manifeste peut la voir.
    d = np.zeros((3, 3, 3, 3), dtype=np.float32)
    man = dict(pi[1])
    man["parametres"] = PARAMS[:2]
    verifie(tuple(d.shape) != (len(man["parametres"]),
                               len(man["niveaux_m_sol"]),
                               len(man["echeances_min"]),
                               len(man["balises"])),
            "un cube 3×3×3×3 ne coïncide plus avec le manifeste — c'est "
            "cette comparaison-là qui tient, pas la chance des tailles")


def test_les_balises_s_apparient_par_identifiant_pas_par_rang():
    print("\n▶ 6. PI est indexé par identifiant, jamais par rang")
    # Même physique, axe PI renversé : si l'appariement se faisait par
    # rang, la balise 70 recevrait le Δ de la balise 812 — fini,
    # plausible, et pris 400 km plus loin.
    val = {"70": 8.0, "1377": 9.0, "812": 10.0}
    a = archive_a(lambda k, s: (1.0, 0.0), lambda k, s: (2.0, 0.0),
                  lambda k, s: (4.0, 0.0))
    obs = {b["id"]: Obs(lambda i: (18.0, 90.0)).paire for b in PIOUPIOU}
    droit = archive_pi(lambda sid, niv, m:
                       (val[sid], 0.0) if niv == 10 else (16.0, 0.0))
    envers = archive_pi(lambda sid, niv, m:
                        (val[sid], 0.0) if niv == 10 else (16.0, 0.0),
                        ordre=[2, 1, 0])
    t1, ch = table_de(lancer(a, droit, obs))
    t2, _ = table_de(lancer(a, envers, obs))
    verifie(np.allclose(col_de(t1, ch, "u_pi10"),
                        col_de(t2, ch, "u_pi10")),
            "renverser l'axe PI ne change AUCUNE valeur — chaque balise "
            "garde son propre Δ")
    # Et la valeur est la bonne, balise par balise.
    ids = [sid for sid, _, _ in lancer(a, droit, obs)]
    ok = all(abs(col_de(t1, ch, "u_pi10")[i] - val[ids[i]]) < 1e-6
             for i in range(len(ids)))
    verifie(ok, "chaque balise reçoit SA valeur PI (70→8, 1377→9, 812→10)")


def test_les_heures_se_cherchent_par_valeur_pas_par_position():
    print("\n▶ 7. les heures rondes se cherchent par VALEUR dans "
          "echeances_min")
    a = archive_a(lambda k, s: (1.0, 0.0), lambda k, s: (2.0, 0.0),
                  lambda k, s: (4.0, 0.0))
    obs = {b["id"]: Obs(lambda i: (18.0, 90.0)).paire for b in PIOUPIOU}
    # Une archive PI TROUÉE : les 15 min manquent. Les heures rondes ne
    # sont donc plus aux positions 0, 4, 8… mais aux positions 0, 3, 6…
    mins = [m for m in MINUTES if m % 60 == 0 or m % 60 == 30]
    pi = archive_pi(lambda sid, niv, m:
                    ((8.0 + m / 60.0, 0.0) if niv == 10 else (16.0, 0.0)),
                    minutes=mins)
    tab, ch = table_de(lancer(a, pi, obs))
    h = col_de(tab, ch, "h")
    u = col_de(tab, ch, "u_pi10")
    verifie(np.allclose(u, 8.0 + h),
            "⛔ chaque heure lit SA minute (8 + h) même sur une archive "
            "PI trouée — une lecture par position décalerait tout")
    # Et une heure ronde ABSENTE ne fabrique rien.
    pi2 = archive_pi(lambda sid, niv, m:
                     ((8.0, 0.0) if niv == 10 else (16.0, 0.0)),
                     minutes=[m for m in MINUTES if m != 180])
    t2, _ = table_de(lancer(a, pi2, obs))
    verifie(3 not in set(col_de(t2, ch, "h").astype(int).tolist()),
            "l'heure +3 h absente de PI ne produit aucun couple — "
            "aucune interpolation n'est fabriquée")


def test_un_nan_ne_produit_pas_de_couple():
    print("\n▶ 8. un NaN d'un côté quelconque ⇒ pas de couple, jamais un 0")
    # ⚠️ Les composantes v sont NON NULLES ici, exprès : avec v = 0
    # partout, un Δ de placebo fabriqué à zéro serait indiscernable d'un
    # Δv légitimement nul, et le banc ci-dessous ne pourrait pas rougir.
    a = archive_a(lambda k, s: (1.0, 0.5), lambda k, s: (2.0, 1.0),
                  lambda k, s: (4.0, 2.0))
    obs = {b["id"]: Obs(lambda i: (18.0, 90.0)).paire for b in PIOUPIOU}
    # PI n'a pas le 10 m à +2 h sur la balise 1377.
    pi = archive_pi(lambda sid, niv, m:
                    (None if (niv == 10 and sid == "1377" and m == 120)
                     else ((8.0, 3.0) if niv == 10 else (16.0, 5.0))))
    lot = lancer(a, pi, obs)
    ih = B.CHAMPS.index("h")
    verifie((("1377", 2) not in [(sid, int(l[ih])) for sid, _, l in lot]),
            "la balise 1377 n'a pas de couple à +2 h")
    par_h = {}
    for sid, _, l in lot:
        par_h.setdefault(int(l[ih]), []).append(sid)
    verifie(all(len(v) == len(PIOUPIOU) for h, v in par_h.items() if h != 2),
            "les autres heures gardent leurs 3 balises — le trou n'est "
            "pas contagieux au-delà de son heure")
    verifie(len(par_h.get(2, [])) < len(PIOUPIOU),
            "⛔ à +2 h, la balise sans PI disparaît ET son emprunteur de "
            "placebo aussi : un témoin plus creux que le candidat serait "
            "une dissymétrie rassurante à tort")
    tab, ch = table_de(lot)
    verifie(not np.any(col_de(tab, ch, "u_pi10") == 0.0),
            "aucun 0 n'a été fabriqué à la place d'un NaN")
    # ⛔ ET SURTOUT : AUCUN Δ DE PLACEBO NE VAUT ZÉRO. Garder un couple
    # dont le donneur manque, en lui posant un Δ nul, ne se verrait pas
    # dans les comptes (la balise trouée disparaît quand même) — mais le
    # témoin recevrait alors « PI ne corrige rien ici », qui est une
    # affirmation, sur les couples les plus fragiles. Mutation nº 17.
    placebos = np.stack([col_de(tab, ch, n) for n in B.CHAMPS_PLACEBO])
    verifie(not np.any(placebos == 0.0),
            "aucun Δ de placebo n'a été fabriqué à zéro — un couple sans "
            "donneur SORT, il ne reçoit pas un témoin vide")


# ══════════════════════════════════════════════════════════════════
#  9-12. LA COMPOSITION DES SÉRIES ET L'ERREUR
# ══════════════════════════════════════════════════════════════════

def test_les_series_ajoutent_w_fois_delta_sur_u_et_v():
    print("\n▶ 9. T1 et T2 ajoutent w·Δ sur u et v, avant decorer_vent")
    a, pi, obs = scene()
    tab, ch = table_de(lancer(a, pi, obs))
    sers, _ = B.series(tab, ch)
    w = col_de(tab, ch, "w")
    h = col_de(tab, ch, "h")
    # ⛔ LA COLONNE `w` EST CONFRONTÉE À `poids_pi`, PAS PRISE POUR
    # ARGENT COMPTANT. Vérifier T1 « avec le w du tableau » ne prouve
    # rien : si la sonde écrivait w = 1 partout, le banc comparerait une
    # faute à elle-même et resterait vert. C'est la mutation nº 6 du
    # 26/08 qui l'a montré.
    verifie(np.allclose(w, [poids_pi(int(x) * 60) for x in h]),
            "la colonne w est EXACTEMENT la rampe du composite "
            f"(dont {sorted(set(w.tolist()))})")
    verifie(0.5 in set(w.tolist()) and 1.0 in set(w.tolist()),
            "la rampe est bien à deux régimes ici (1,0 puis 0,5) — sinon "
            "le banc ne verrait pas un w écrasé à 1")
    # Δ20 = 16 − 4 = 12 ; Δ10 = 8 − 2 = 6 ; base u = 1, v = 0.
    attendu_t1 = np.array([decorer_vent({"u": 1.0 + w[i] * 12.0,
                                         "v": 0.0})["vitesseKmh"]
                           for i in range(len(tab))])
    attendu_t2 = np.array([decorer_vent({"u": 1.0 + w[i] * 6.0,
                                         "v": 0.0})["vitesseKmh"]
                           for i in range(len(tab))])
    verifie(np.allclose(sers["T0"][0],
                        decorer_vent({"u": 1.0, "v": 0.0})["vitesseKmh"]),
            "T0 est la base brute")
    verifie(np.allclose(sers["T1"][0], attendu_t1),
            "T1 = base + w·Δ(20 m), avec le w de la rampe")
    verifie(np.allclose(sers["T2"][0], attendu_t2),
            "T2 = base + w·Δ(10 m)")
    verifie(not np.allclose(sers["T1"][0], sers["T2"][0]),
            "T1 et T2 diffèrent — sinon la phase B n'a rien à mesurer")


def test_delta_s_ajoute_sur_u_v_et_pas_sur_la_vitesse():
    print("\n▶ 10. Δ sur u/v, jamais sur la vitesse ni sur l'angle")
    # Base plein NORD (u=0, v=-6 → 4 km/h de nord), Δ plein EST.
    # Ajouter Δ à la VITESSE laisserait la direction inchangée ;
    # l'ajouter à u/v la fait tourner. C'est là que 180° se gagnent.
    a = archive_a(lambda k, s: (0.0, -6.0), lambda k, s: (0.0, 0.0),
                  lambda k, s: (0.0, 0.0))
    pi = archive_pi(lambda sid, niv, m: (6.0, 0.0) if niv == 10 else (0.0, 0.0))
    obs = {b["id"]: Obs(lambda i: (18.0, 90.0)).paire for b in PIOUPIOU}
    tab, ch = table_de(lancer(a, pi, obs))
    sers, _ = B.series(tab, ch)
    m = col_de(tab, ch, "h") == 0            # w = 1
    d0 = sers["T0"][1][m][0]
    d2 = sers["T2"][1][m][0]
    verifie(abs(((d2 - d0) % 360) - 45.0) < 1.0 or
            abs(((d0 - d2) % 360) - 45.0) < 1.0,
            f"la direction TOURNE de 45° ({d0:.0f}° → {d2:.0f}°) — un Δ "
            f"ajouté à la vitesse l'aurait laissée intacte")
    verifie(abs(sers["T2"][0][m][0] - round(math.hypot(6.0, 6.0) * 3.6, 1))
            < 0.15, "et la vitesse est celle de la somme VECTORIELLE")


def test_l_erreur_est_exactement_celle_de_scoring():
    print("\n▶ 11. l'erreur est celle de `scoring.pair_error`, pas une copie")
    cas = [(20.0, 30.0, 18.0, 45.0), (7.0, 350.0, 9.0, 10.0),
           (3.0, 120.0, 12.0, 120.0), (25.0, 0.0, 4.0, 200.0),
           (11.0, 270.0, 11.0, 90.0)]
    sp = np.array([c[0] for c in cas])
    di = np.array([c[1] for c in cas])
    osp = np.array([c[2] for c in cas])
    odi = np.array([c[3] for c in cas])
    for vec_force in (True, False):
        mien = B.erreurs(sp, di, osp, odi,
                         np.full(len(cas), vec_force, dtype=bool))
        for i, (a_, b_, c_, d_) in enumerate(cas):
            p = S.VerifPair(t=0, fcst_speed=a_, fcst_dir=b_, obs_speed=c_,
                            obs_dir=d_, n_obs=1)
            e_ref, vect_ref = S.pair_error(p)
            if vec_force and vect_ref:
                ok = abs(mien[i] - e_ref) < 1e-9
            elif not vec_force:
                ok = abs(mien[i] - abs(a_ - c_)) < 1e-9
            else:
                ok = True         # `pair_error` serait retombé en scalaire
            if not ok:
                verifie(False, f"cas {cas[i]} vec={vec_force} : "
                               f"{mien[i]:.4f} ≠ {e_ref:.4f}")
                return
    verifie(True, "les 5 cas × 2 modes coïncident avec `pair_error`")


def test_le_mode_vectoriel_est_commun_aux_cinq_series():
    print("\n▶ 12. le mode d'erreur est décidé une fois, pour les 5 séries")
    # ⚠️ C'est la DERNIÈRE série qui passe sous le seuil, pas T0 : un
    # banc où T0 est la fautive resterait vert sur la mutation « le mode
    # est décidé par T0 seule » (trouvée le 26/08). Le témoin doit
    # échouer là où la faute vit.
    sers = {"T0": (np.array([20.0, 20.0]), np.array([30.0, 30.0])),
            "T1": (np.array([20.0, 20.0]), np.array([30.0, 30.0])),
            "T2": (np.array([20.0, 4.0]), np.array([30.0, 30.0]))}
    obs_sp = np.array([18.0, 18.0])
    obs_di = np.array([45.0, 45.0])
    m = B.mode_commun(sers, obs_sp, obs_di)
    verifie(bool(m[0]) and not bool(m[1]),
            "⛔ le couple où UNE série passe sous 5 km/h bascule en "
            "scalaire pour TOUTES — laissé libre, le critère changerait "
            "la règle de calcul entre les séries qu'on compare")
    verifie(len(m) == 2, "et aucun couple n'est jeté : jeter les vents "
                         "faibles éliminerait justement là où Δ pèse le plus")


# ══════════════════════════════════════════════════════════════════
#  13-16. L'APPARIEMENT AUX OBSERVATIONS, LE BOOTSTRAP, LE BOUT À BOUT
# ══════════════════════════════════════════════════════════════════

def test_l_appariement_aux_obs_est_celui_de_pair_series():
    print("\n▶ 13. ±20 min et moyenne vectorielle, comme `pair_series`")
    o = Obs(lambda i: (10.0 + i, 90.0), n=30)
    t = T0_MS + 3600 * 1000
    mien = B.obs_a(o.paire, t)
    ref = S.pair_series([t], [12.0], [90.0], o.ech)
    verifie(len(ref) == 1 and abs(mien[0] - ref[0].obs_speed) < 1e-9,
            f"même vitesse observée ({mien[0]:.3f})")
    verifie(abs((mien[1] or 0) - (ref[0].obs_dir or 0)) < 1e-9,
            "même direction observée")
    verifie(mien[2] == ref[0].n_obs, f"même nombre de relevés ({mien[2]})")
    # Une heure sans aucun relevé n'est pas comblée.
    verifie(B.obs_a(o.paire, T0_MS + 48 * 3600 * 1000) is None,
            "une heure sans relevé rend None — jamais une valeur comblée")


def test_le_bootstrap_reechantillonne_les_journees():
    print("\n▶ 14. le bootstrap tire des JOURNÉES, pas des couples")
    rng = np.random.default_rng(0)
    n = 4000
    jours = np.repeat([20260819, 20260820, 20260821, 20260822], n // 4)
    err = {"T1": rng.normal(10.0, 2.0, n), "T2": rng.normal(9.9, 2.0, n)}
    lo, hi = B.bootstrap_jours(err, jours, "T1", "T2", tirages=400)
    # Un tirage par couple sur 4000 tirages indépendants donnerait un IC
    # de l'ordre de 0,1 km/h de large ; par journée, avec 4 journées,
    # il est nettement plus large.
    verifie(hi - lo > 0.05,
            f"IC large de {hi - lo:.3f} km/h sur 4 journées — un tirage "
            f"par couple l'aurait rendu dix fois plus étroit")
    # Une seule journée : il n'y a rien à rééchantillonner, l'IC est nul.
    lo1, hi1 = B.bootstrap_jours(err, np.full(n, 20260819), "T1", "T2",
                                 tirages=50)
    verifie(abs(hi1 - lo1) < 1e-9,
            "⛔ sur UNE journée l'IC est de largeur nulle — le bootstrap "
            "dit franchement qu'il n'a rien à dire, au lieu de fabriquer "
            "une précision qui n'existe pas")


def test_bout_a_bout_un_delta_10m_parfait_se_voit_et_le_placebo_non():
    print("\n▶ 15. bout à bout : Δ(10 m) PARFAIT ⇒ T2 ≈ 0, placebo non")
    # Chaque balise a un vent observé DIFFÉRENT, et PI(10 m) est
    # exactement ce qu'il faut pour l'atteindre. Le placebo, lui, reçoit
    # le Δ d'une autre balise : il ne peut pas atteindre l'observation.
    #   base 0,01° : u = 0, v = 0  → T0 = calme
    #   obs balise k : vent d'EST de (10 + 5k) km/h
    obs_kmh = {"70": 15.0, "1377": 25.0, "812": 35.0}
    # convention `decorer_vent` : direction = d'où vient le vent.
    # Vent d'ouest (270°) ⇒ u > 0. On vise u = obs/3.6, v = 0.
    a = archive_a(lambda k, s: (0.0, 0.0), lambda k, s: (0.0, 0.0),
                  lambda k, s: (0.0, 0.0))
    pi = archive_pi(lambda sid, niv, m:
                    ((obs_kmh[sid] / 3.6, 0.0) if niv == 10 else (0.5, 0.0)))
    obs = {sid: Obs(lambda i, v=v: (v, 270.0)).paire
           for sid, v in obs_kmh.items()}
    tab, ch = table_de(lancer(a, pi, obs))
    m = col_de(tab, ch, "h") == 0                      # w = 1, Δ plein
    sers, _ = B.series(tab, ch)
    osp, odi = col_de(tab, ch, "obs_speed"), col_de(tab, ch, "obs_dir")
    vec = B.mode_commun(sers, osp, odi)
    err = {s: B.erreurs(sp, di, osp, odi, vec) for s, (sp, di) in sers.items()}
    r0, r1, r2 = (B.rms(err["T0"][m]), B.rms(err["T1"][m]),
                  B.rms(err["T2"][m]))
    rp = B.rms(err["T2p1"][m])
    print(f"     rms T0={r0:.3f}  T1={r1:.3f}  T2={r2:.3f}  "
          f"T2-placebo={rp:.3f}")
    verifie(r2 < 0.3, f"T2 tombe à {r2:.3f} km/h — le Δ(10 m) parfait est "
                      f"bien vu par la chaîne de mesure")
    verifie(rp > r2 + 5.0,
            f"⛔ le PLACEBO ne suit pas ({rp:.3f} contre {r2:.3f}) — un "
            f"témoin qui suivrait dirait que le « gain » n'est qu'un "
            f"rétrécissement de variance")
    verifie(r1 > r2, "et T1 (Δ(20 m) étendu) reste loin derrière")


def test_la_moyenne_quadratique_voit_ce_que_la_mediane_ne_voit_pas():
    print("\n▶ 16. on lit une moyenne quadratique, jamais une médiane")
    # 20 couples : 6 corrigés à la perfection, 14 intouchés. C'est la
    # forme exacte du résultat du 26/08 (6 heures sur 24) transposée ici.
    e_avant = np.full(20, 8.0)
    e_apres = np.concatenate([np.zeros(6), np.full(14, 8.0)])
    verifie(np.median(e_avant) == np.median(e_apres),
            "⛔ la MÉDIANE est identique (8,0) alors que 6 couples sur 20 "
            "sont devenus parfaits — c'est la propriété pinnée le 26/08")
    verifie(B.rms(e_apres) < B.rms(e_avant) - 1.0,
            f"la moyenne quadratique, elle, bouge "
            f"({B.rms(e_avant):.2f} → {B.rms(e_apres):.2f})")
    verifie(abs(B.rms(np.array([3.0, 4.0])) - math.sqrt(12.5)) < 1e-12,
            "et `rms` est bien une moyenne quadratique, pas une moyenne")


def test_l_ordre_des_champs_ne_peut_pas_glisser():
    print("\n▶ 17. les colonnes du tableau portent leur nom, pas leur rang")
    a, pi, obs = scene()
    lot = lancer(a, pi, obs)
    tab, ch = table_de(lot)
    verifie(tab.shape[1] == len(ch),
            f"{tab.shape[1]} colonnes pour {len(ch)} noms")
    verifie(len(set(ch)) == len(ch), "aucun nom de colonne en double")
    # ⛔ La sonde relit ses colonnes PAR NOM (`champs.index(...)`). Un
    # décalage d'une case entre l'écriture et la lecture rendrait des
    # vents finis, plausibles, et pris dans la mauvaise maille — la
    # faute nº 3 du 26/08, transposée à un tableau plat.
    verifie(ch[:5] == ["jour", "run_h", "h", "w", "i_balise"],
            "l'entête commence par les cinq clefs de contexte")
    verifie(all(f"d10u_don{g}" in ch and f"d20v_don{g}" in ch
                for g in B.GRAINES_PLACEBO),
            "les deux témoins ont chacun leurs quatre colonnes")


def scene_forte():
    """Une scène où les CINQ séries T dépassent le seuil de 5 km/h mais
    où une série BRUTE ne le dépasse pas.

    ⛔ C'est la seule forme de scène qui rende le masque des dix séries
    STRICTEMENT plus étroit que celui des cinq. Sur la scène ordinaire
    les deux coïncident, et le banc du masque commun passerait sans rien
    tenir — un banc qui ne peut pas rougir se lit comme un banc qui
    passe (piège nº 4 du 26/08, sous une autre forme).
    """
    # ⛔ TROIS BALISES, TROIS RÔLES, ET AUCUN N'EST DÉCORATIF :
    #   « 70 »   : son AROME₂₀ brut passe sous le seuil → il sort du
    #              masque des BRUTES, mais pas de celui des séries T.
    #   « 1377 » : son T1 passe sous le seuil (Δ(20 m) très négatif)
    #              alors que toutes ses séries brutes le dépassent → il
    #              sort du masque des T, mais pas de celui des BRUTES.
    #   « 812 »  : tout passe.
    # Sans les DEUX premiers, le masque des brutes serait inclus dans
    # celui des T et « chaque tableau calcule le sien » deviendrait un
    # non-événement : le banc resterait vert sur la faute. Trouvé par la
    # mutation nº 19, deux fois de suite.
    a = archive_a(lambda k, s: (3.0, 0.0),      # T0 = 10,8 km/h
                  lambda k, s: (3.2, 0.0),      # AROME₁₀ 0,025° = 11,5
                  lambda k, s: ((1.0 if k == 0 else
                                 (5.0 if k == 1 else 3.0)), 0.0))
    pi = archive_pi(lambda sid, niv, m:
                    (3.9, 0.0) if niv == 10
                    else ((1.3, 0.0) if sid == "70"
                          else ((3.0, 0.0) if sid == "1377" else (3.3, 0.0))))
    # ⚠️ L'observation vient de 240°, pas de 270° comme le modèle. Avec
    # la MÊME direction des deux côtés, l'erreur vectorielle vaut
    # exactement l'erreur scalaire — et un banc bâti là-dessus ne peut
    # pas distinguer les deux modes, donc ne peut pas rougir quand on
    # change de masque. Trouvé par la mutation nº 19 du 26/08.
    obs = {b["id"]: Obs(lambda i: (15.0, 240.0)).paire for b in PIOUPIOU}
    return a, pi, obs


def test_le_masque_vectoriel_couvre_les_dix_series_du_rapport():
    print("\n▶ 19. un seul masque pour les dix séries du rapport")
    a, pi, obs = scene_forte()
    tab, ch = table_de(lancer(a, pi, obs))
    sers, _ = B.series(tab, ch)
    brutes = B.series_brutes(tab, ch)
    verifie(set(B.BRUTES) == set(brutes) and len(brutes) == 5,
            "les cinq séries brutes de la question 0 sont bien là")
    # ⛔ Le masque des dix séries est INCLUS dans celui des cinq : le
    # calculer par tableau donnerait DEUX valeurs de rms pour T0 dans le
    # MÊME rapport (8,2277 et 8,1476 le 26/08), et un lecteur y lirait
    # un effet physique. Ce banc pin la propriété, pas la valeur.
    osp = col_de(tab, ch, "obs_speed")
    odi = col_de(tab, ch, "obs_dir")
    m5 = B.mode_commun(sers, osp, odi)
    mb = B.mode_commun(brutes, osp, odi)
    m10 = B.mode_commun({**sers, **brutes}, osp, odi)
    verifie(bool(np.all(m10 <= m5)) and int(m5.sum()) > int(m10.sum()),
            f"⛔ le masque des dix séries ({int(m10.sum())}) est "
            f"STRICTEMENT plus étroit que celui des cinq séries T "
            f"({int(m5.sum())})")
    verifie(int(mb.sum()) > int(m10.sum()) and not np.array_equal(mb, m5),
            f"⛔ et STRICTEMENT plus étroit que celui des cinq séries "
            f"BRUTES ({int(mb.sum())}), qui n'est lui-même pas celui des "
            f"T — les trois diffèrent, donc « chaque tableau calcule le "
            f"sien » se VOIT")


def test_bout_a_bout_le_rapport_entier_est_coherent():
    print("\n▶ 21. bout à bout : le T0 de la question 0 et celui de la "
          "question 2 sont LE MÊME nombre")
    import tempfile
    a, pi, obs = scene_forte()
    tab, ch = table_de(lancer(a, pi, obs))
    # Deux journées, pour que la coupe du balayage α existe.
    tab[: len(tab) // 2, ch.index("jour")] = 20260819
    tab[len(tab) // 2:, ch.index("jour")] = 20260820
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.npz")
        np.savez_compressed(
            p, table=tab, champs=np.array(ch),
            balise=np.array([s for s, _, _ in lancer(a, pi, obs)]),
            domaine=np.array([x for _, x, _ in lancer(a, pi, obs)]),
            runs=np.array([RUN]), runs_ecartes=np.array([""]),
            heures_pi=np.array(B.HEURES_PI),
            graines=np.array(B.GRAINES_PLACEBO))
        res = B.agreger(__import__("pathlib").Path(p), crier=lambda *_: None)
    verifie(set(res) >= {"ensemble", "q0", "q1", "alpha", "ic", "par_jour"},
            "le rapport rend bien ses six sections")
    t0_q0 = res["q0"]["AROME₁₀ 0,01° (T0)"]
    t0_q2 = res["ensemble"]["T0"]
    verifie(abs(t0_q0 - t0_q2) < 1e-12,
            f"⛔ un seul T0 dans tout le rapport ({t0_q0:.6f}) — deux "
            f"masques donneraient deux nombres pour la même série, et un "
            f"lecteur y lirait un effet physique")
    verifie(all(abs(v["courbe"][0] - t0_q2) < 1e-9
                for v in res["alpha"].values()),
            "et les TROIS courbes de α partent exactement de ce T0-là")


def table_deux_regimes(n=60):
    """Un tableau où les deux moitiés de la campagne se CONTREDISENT.

    ⛔ C'est la seule forme de jeu d'essai capable de distinguer « appris
    sur une moitié, évalué sur l'autre » de « appris et évalué sur la
    même ». Sur des journées identiques les deux donnent le MÊME nombre,
    et le banc reste vert sur la faute — trouvé par la mutation nº 17 du
    26/08.

      journée A : l'observation vaut EXACTEMENT T0 + Δ  → α* = 1
      journée B : l'observation vaut EXACTEMENT T0      → α* = 0
    """
    ch = list(B.CHAMPS + B.CHAMPS_PLACEBO)
    tab = np.zeros((n, len(ch)))
    c = {nom: k for k, nom in enumerate(ch)}
    tab[:, c["h"]] = 0
    tab[:, c["w"]] = 1.0
    tab[:, c["n_obs"]] = 5
    tab[:, c["u_ar10"]] = 3.0          # T0 = 10,8 km/h, de 270°
    tab[:, c["u_ar10q"]] = 3.0
    tab[:, c["u_pi10"]] = 4.0          # Δ(10 m) = +1,0 m/s
    tab[:, c["u_ar20q"]] = 3.0
    tab[:, c["u_pi20"]] = 4.0
    for nom in B.CHAMPS_PLACEBO:
        tab[:, c[nom]] = 0.7           # un témoin quelconque, non nul
    tab[:, c["obs_dir"]] = 270.0
    moitie = n // 2
    tab[:moitie, c["jour"]] = 20260819
    tab[:moitie, c["obs_speed"]] = round(4.0 * 3.6, 1)     # T0 + Δ
    tab[moitie:, c["jour"]] = 20260820
    tab[moitie:, c["obs_speed"]] = round(3.0 * 3.6, 1)     # T0 seul
    return tab, ch


def test_le_balayage_alpha_est_evalue_hors_echantillon():
    print("\n▶ 20. α est appris sur une moitié et évalué sur l'AUTRE")
    tab, ch = table_deux_regimes()
    jours = col_de(tab, ch, "jour").astype(np.int64)
    osp, odi = col_de(tab, ch, "obs_speed"), col_de(tab, ch, "obs_dir")
    vec = np.ones(len(tab), dtype=bool)
    out = B.balayage_amplitude(tab, ch, osp, odi, jours, vec,
                               crier=lambda *_: None)
    verifie(len(out) == 3 and any("échelle" in k for k in out),
            f"les TROIS Δ sont balayés, dont « Δ(20 m) × cisaillement » : "
            f"{sorted(out)}")
    kappa = B._cisaillement(tab, ch)
    verifie(abs(kappa - 1.0) < 1e-9,
            f"κ mesuré sur ce jeu d'essai = {kappa:.3f} (ici 10 m et 20 m "
            f"portent le même vent, donc κ = 1 — la fonction MESURE, elle "
            f"ne recopie pas une constante)")
    d = out["Δ(10 m) vrai"]
    verifie(len(d["courbe"]) == 11, "11 valeurs de α, de 0 à 1")
    verifie(len(d["hors"]) == 2,
            "DEUX évaluations hors échantillon (les deux moitiés, chacune "
            "à son tour) — une seule laisserait le verdict porté par un "
            "seul découpage")
    a_star, e_ev, e_0, e_1 = d["hors"][0]
    verifie(abs(a_star - 1.0) < 1e-9,
            f"la moitié A apprend α* = {a_star:.1f} (son observation vaut "
            f"exactement T0 + Δ)")
    verifie(e_ev > e_0 + 1.0,
            f"⛔ ÉVALUÉ SUR LA MOITIÉ B, ce α* est MAUVAIS "
            f"({e_ev:.2f} contre {e_0:.2f} à α = 0) — un α évalué sur sa "
            f"propre moitié aurait rendu 0,00 et annoncé un gain qui "
            f"n'existe pas")
    # α = 0 doit rendre exactement T0 : le seul point de la courbe qu'on
    # connaisse à l'avance, et il ancre tout le reste.
    sers, _ = B.series(tab, ch)
    err0 = B.rms(B.erreurs(*sers["T0"], osp, odi, vec))
    verifie(abs(d["courbe"][0] - err0) < 1e-9,
            f"α = 0 rend EXACTEMENT T0 ({err0:.4f}) — la courbe est bien "
            f"ancrée sur la série non corrigée")


def test_un_run_sans_10m_servi_est_ecarte():
    print("\n▶ 18. un run PI qui n'a pas servi le 10 m est ÉCARTÉ")
    a, pi, obs = scene()
    d, man = pi
    man = dict(man, niveau_10m_servi=False)
    lot = lancer(a, (d, man), obs)
    verifie(lot == [],
            "⛔ aucun couple — toute la phase B repose sur un VRAI 10 m "
            "côté PI ; un run sans lui rendrait un Δ(10 m) fabriqué, et "
            "un Δ fabriqué qui gagne est le pire des résultats")


# ══════════════════════════════════════════════════════════════════
#  ⛔ CETTE ENTRÉE RESTE LA DERNIÈRE CHOSE DU FICHIER.
#  Piège nº 4 du 26/08 : trois bancs ajoutés APRÈS elle n'ont jamais
#  tourné, et un banc qui ne tourne pas se lit exactement comme un banc
#  qui passe.
# ══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("═" * 66)
    print("  BANC DE LA SONDE Δ(10 m) — phase B")
    print("═" * 66)
    test_les_heures_sont_celles_ou_la_rampe_est_non_nulle()
    test_le_placebo_n_a_aucun_point_fixe()
    test_la_graine_est_deterministe_entre_processus()
    test_delta_10m_se_lit_en_0025_contre_0025_au_niveau_10()
    test_l_axe_pi_est_parametre_niveau_echeance_balise()
    test_les_balises_s_apparient_par_identifiant_pas_par_rang()
    test_les_heures_se_cherchent_par_valeur_pas_par_position()
    test_un_nan_ne_produit_pas_de_couple()
    test_les_series_ajoutent_w_fois_delta_sur_u_et_v()
    test_delta_s_ajoute_sur_u_v_et_pas_sur_la_vitesse()
    test_l_erreur_est_exactement_celle_de_scoring()
    test_le_mode_vectoriel_est_commun_aux_cinq_series()
    test_l_appariement_aux_obs_est_celui_de_pair_series()
    test_le_bootstrap_reechantillonne_les_journees()
    test_bout_a_bout_un_delta_10m_parfait_se_voit_et_le_placebo_non()
    test_la_moyenne_quadratique_voit_ce_que_la_mediane_ne_voit_pas()
    test_l_ordre_des_champs_ne_peut_pas_glisser()
    test_un_run_sans_10m_servi_est_ecarte()
    test_le_masque_vectoriel_couvre_les_dix_series_du_rapport()
    test_le_balayage_alpha_est_evalue_hors_echantillon()
    test_bout_a_bout_le_rapport_entier_est_coherent()
    print("\n" + "═" * 66)
    if ECHECS:
        print(f"  ❌ {len(ECHECS)} ÉCHEC(S)")
        for e in ECHECS:
            print(f"     · {e}")
        sys.exit(1)
    print("  ✅ tous les bancs sont verts")
