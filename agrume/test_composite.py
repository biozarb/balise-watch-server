#!/usr/bin/env python3
"""
test_composite.py — banc du composite temporel (étape 9), HORS-LIGNE.

    python3 agrume/test_composite.py

⚠️ CE QUE CE BANC PROTÈGE.

Le composite est un objet qui a l'air juste dès qu'il a l'air continu.
Il mélange deux modèles, deux pas de temps et deux jeux de niveaux, et
**aucune de ses erreurs ne lève** : elles produisent toutes une courbe
lisse et plausible. Sept façons de casser en silence :

  1. **⚠️⚠️ L'INVARIANT.** Aux niveaux communs et tant que `w_PI = 1`, le
     composite DOIT reproduire PI exactement — les deux termes se
     compensent (`AROME_interp + (PI − AROME_interp) = PI`). Si ce n'est
     pas le cas, c'est qu'on a inventé une valeur là où PI en donnait
     une. C'est le critère d'acceptation de l'étape.
  2. **Un delta propagé en τ.** La question du §4.3 (« garder le dernier
     Δ ou l'interpoler ? ») n'a pas d'objet : PI est publié aux 25
     échéances. Un Δ figé entre deux heures rendrait un composite qui
     s'écarte de PI à `:15`, `:30`, `:45` — alors que PI y est.
  3. **Une direction interpolée.** 350° et 010° donnent 180° si l'on
     interpole l'angle : le vent EXACTEMENT à l'opposé, sans rien lever.
  4. **Une rampe qui dépasse l'horizon.** Le §4.3 faisait descendre
     `w_PI` jusqu'à 7 h alors que PI s'arrête à 6 h — la formule
     pondérait du vide.
  5. **Une marche au ras du sol.** Δ n'est pas défini sous 20 m ; le
     mettre à 0 créerait une discontinuité exactement à l'altitude du
     pilote.
  6. **Une extrapolation muette.** Hors de la couverture d'AROME, on
     REFUSE plutôt que de prolonger la dernière valeur.
  7. **Une résolution temporelle qu'on laisse croire.** Le composite
     sert 25 échéances à 3 000 m comme à 20 m. Seule la tranche basse
     a été OBSERVÉE à 15 min.

Aucun réseau, aucune clé, aucun GRIB.
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import composite as CO  # noqa: E402
from composite import (Abort, arome_interpole, composer,  # noqa: E402
                       etendre_delta, poids_pi, resolution_temporelle)
from domaine import NIVEAUX_H_0025  # noqa: E402
from pi import ECHEANCES_MIN, NIVEAUX_DELTA, NIVEAUX_PI  # noqa: E402

echecs = []


def verifier(quoi, cond, detail=""):
    ok = bool(cond)
    if not ok:
        echecs.append(quoi)
    print(f"  {'✅' if ok else '⛔'} {quoi}" + (f" — {detail}" if detail else ""))
    return ok


def leve(quoi, fn, fragment=None):
    try:
        fn()
    except Abort as e:
        ok = fragment is None or fragment in str(e)
        return verifier(quoi, ok, "" if ok else f"message inattendu : {e}")
    except Exception as e:                                   # noqa: BLE001
        return verifier(quoi, False, f"a levé {type(e).__name__}")
    return verifier(quoi, False, "n'a RIEN levé")


def jeu(nb_pts=4, graine=7):
    """Un couple PI/AROME synthétique, volontairement PEU LISSE en τ.

    ⚠️ Un champ lisse ferait passer un composite faux : l'interpolation
    d'AROME y serait presque exacte, donc Δ presque nul, donc l'invariant
    trivialement vérifié. On force donc une variation forte et non
    linéaire d'une heure à l'autre — c'est d'ailleurs ce que la mesure
    dit du vrai champ (exposant 0,5–0,9, pas 2).
    """
    rng = np.random.default_rng(graine)
    steps = list(range(0, 13))
    ar = rng.normal(0, 4, size=(2, len(NIVEAUX_H_0025), len(steps), nb_pts))
    pi = rng.normal(0, 4, size=(2, len(NIVEAUX_PI), len(ECHEANCES_MIN), nb_pts))
    return pi, ar, steps


def main():
    print("── 1. ⚠️⚠️ L'INVARIANT : le composite reproduit PI ──")
    pi, ar, steps = jeu()
    comp, diag = composer(pi, ar, steps)
    verifier("la forme est (2, 25 niveaux, 25 échéances, points)",
             comp.shape == (2, len(NIVEAUX_H_0025), len(ECHEANCES_MIN), 4),
             str(comp.shape))

    i_pi = [NIVEAUX_PI.index(z) for z in NIVEAUX_DELTA]
    i_co = [list(NIVEAUX_H_0025).index(z) for z in NIVEAUX_DELTA]
    pleins = [k for k, m in enumerate(ECHEANCES_MIN) if poids_pi(m) == 1.0]
    ecart = np.abs(comp[:, i_co][:, :, pleins] - pi[:, i_pi][:, :, pleins])
    verifier("⚠️⚠️ aux 5 niveaux communs et tant que w_PI = 1, "
             "composite == PI À LA PRÉCISION MACHINE",
             float(ecart.max()) < 1e-9,
             f"écart max {float(ecart.max()):.2e} m/s sur "
             f"{ecart.size} valeurs")
    verifier("et ça porte sur les échéances NON RONDES aussi "
             "(c'est tout l'objet du §4.3)",
             len(pleins) == 17 and 15 in [ECHEANCES_MIN[k] for k in pleins],
             f"{len(pleins)} échéances à w = 1, dont "
             f"{[ECHEANCES_MIN[k] for k in pleins[:4]]}")

    # ⚠️ Le contrôle qui donne son sens au précédent : si le composite
    # valait AROME au lieu de PI, l'invariant serait faux. On le montre.
    # ⚠️ `arome_interpole` travaille sur la DERNIÈRE dimension : ici l'axe
    # des échéances est en position 2. Sans ce `moveaxis`, numpy diffuse
    # « niveaux × points » contre « niveaux × échéances » — et si les
    # deux comptes se trouvaient égaux, ça passerait SANS LEVER en
    # rendant n'importe quoi. *Le même défaut existait dans `composer`,
    # et c'est ce banc qui l'a fait tomber.*
    ar_par_step = np.moveaxis(ar, 2, -1)
    ar_interp = np.stack([arome_interpole(ar_par_step[c], steps,
                                          ECHEANCES_MIN[4])
                          for c in (0, 1)])
    verifier("ⓘ contrôle : PI et AROME DIFFÈRENT vraiment sur ce jeu — "
             "l'invariant ne passe pas par hasard",
             float(np.abs(pi[:, i_pi, 4] - ar_interp[:, i_co]).max()) > 1.0)

    print("\n── 2. ⚠️ Δ est CALCULÉ à :15, pas propagé depuis :00 ──")
    # Si Δ était figé sur l'heure ronde, le composite s'écarterait de PI
    # aux quarts d'heure. L'invariant ci-dessus l'exclut déjà ; on le
    # vérifie ici SÉPARÉMENT, sur une échéance non ronde isolée.
    k15 = ECHEANCES_MIN.index(15)
    e15 = np.abs(comp[:, i_co, k15] - pi[:, i_pi, k15])
    verifier("à τ = 15 min, le composite vaut PI exactement",
             float(e15.max()) < 1e-9, f"{float(e15.max()):.2e}")

    print("\n── 3. ⚠️ Interpolation sur u et v, jamais sur l'angle ──")
    # 350° et 010° : deux vents presque identiques. En u/v, le milieu est
    # 000°. En angle, ce serait 180° — le vent à l'opposé.
    import math
    a1, a2 = math.radians(350), math.radians(10)
    uv = np.array([[[-math.sin(a1), -math.sin(a2)]],
                   [[-math.cos(a1), -math.cos(a2)]]])   # (2, 1, 2)
    milieu = arome_interpole(uv, [0, 1], 30)
    dir_uv = (math.degrees(math.atan2(-milieu[0, 0], -milieu[1, 0])) + 360) % 360
    verifier("⚠️ le milieu de 350° et 010° vaut 0°, pas 180°",
             min(dir_uv, 360 - dir_uv) < 1.0, f"{dir_uv:.2f}°")

    print("\n── 4. ⚠️ La rampe s'arrête à l'HORIZON de PI ──")
    verifier("w = 1 jusqu'à 4 h", poids_pi(0) == 1.0 and poids_pi(240) == 1.0)
    verifier("w = 0,5 à 5 h (milieu de la rampe)", poids_pi(300) == 0.5)
    verifier("⛔ w = 0 à 6 h — et PAS une valeur non nulle qui réclamerait "
             "un PI inexistant (le §4.3 écrivait 7 h)",
             poids_pi(360) == 0.0 and CO.TAU_FIN_MIN == 360)
    verifier("w décroît sans jamais remonter",
             all(poids_pi(a) >= poids_pi(b)
                 for a, b in zip(ECHEANCES_MIN, ECHEANCES_MIN[1:])))
    verifier("le diagnostic publie la rampe en toutes lettres",
             "6 h" in diag["conventions"]["rampe"])

    print("\n── 5. ⚠️ Pas de marche au ras du sol ──")
    d = np.array([[1.0, 2.0, 3.0, 4.0, 5.0]])          # (1, 5) sur 20…500
    e = etendre_delta(d)
    z = list(NIVEAUX_H_0025)
    verifier("Δ(10 m) vaut Δ(20 m) — étendu, pas mis à zéro",
             e[0, z.index(10)] == e[0, z.index(20)] == 1.0,
             f"10 m → {e[0, z.index(10)]}")
    verifier("Δ est interpolé entre deux niveaux PI (35 m entre 20 et 50)",
             1.0 < e[0, z.index(35)] < 2.0, f"{e[0, z.index(35)]:.3f}")
    verifier("Δ s'éteint linéairement : à 750 m il vaut la moitié de "
             "Δ(500)", abs(e[0, z.index(750)] - 2.5) < 1e-9,
             f"{e[0, z.index(750)]:.3f}")
    verifier("⛔ Δ est NUL au-dessus de 1 000 m — le composite y vaut "
             "AROME interpolé, et rien d'autre",
             all(e[0, z.index(zz)] == 0.0
                 for zz in (1000, 1500, 2000, 3000)))
    # ⚠️ CETTE VÉRIFICATION A ÉTÉ ÉCRITE FAUSSE D'ABORD. Elle regardait
    # l'écart entre deux NIVEAUX VOISINS de l'axe AROME et exigeait qu'il
    # reste petit — or 500 → 625 m est un saut de 125 m d'altitude, sur
    # lequel Δ perd 1,25 légitimement. Le banc criait sur un
    # comportement correct.
    # Ce qu'on veut vérifier est la CONTINUITÉ EN z, pas la finesse de
    # l'échantillonnage : on évalue donc Δ sur un axe fin. Une
    # discontinuité vraie (mettre Δ = 0 sous 20 m, par exemple) sauterait
    # aux yeux ici et nulle part ailleurs.
    # ⓘ La pente maximale de ce Δ d'essai est de 1 sur 30 m, soit
    # 0,033 par mètre. Au pas de 0,1 m, un saut légitime vaut donc au
    # plus 0,0033 : le seuil de 0,01 laisse trois fois cette marge, et
    # refuserait n'importe quelle VRAIE discontinuité (elles valent ici
    # 1 ou plus).
    fin = [round(10 + 0.1 * k, 1) for k in range(29901)]
    ef = etendre_delta(d, niveaux_cibles=fin)
    saut = float(np.abs(np.diff(ef[0])).max())
    verifier("⚠️ Δ étendu est CONTINU en z — vérifié au pas de 0,1 m, pas "
             "sur les 25 niveaux (bien trop espacés pour le dire)",
             saut < 0.01, f"saut max {saut:.5f} sur un pas de 0,1 m")
    verifier("ⓘ et la continuité tient AUX TROIS RACCORDS : 20 m (fin de "
             "l'extension basse), 500 m (début de l'extinction) et "
             "1 000 m (Δ = 0)",
             all(abs(float(ef[0][fin.index(z)] - ef[0][fin.index(z + 0.1)]))
                 < 0.01 for z in (20.0, 500.0, 999.9)))

    print("\n── 6. ⛔ Hors couverture, on REFUSE ──")
    leve("une échéance au-delà de la couverture AROME est refusée",
         lambda: arome_interpole(np.zeros((1, 3)), [0, 1, 2], 250), "hors de")
    leve("une échéance avant le début aussi",
         lambda: arome_interpole(np.zeros((1, 3)), [5, 6, 7], 0), "hors de")
    leve("un Δ au mauvais nombre de niveaux est refusé",
         lambda: etendre_delta(np.zeros((1, 3))), "niveaux")
    leve("u et v doivent être en première dimension",
         lambda: composer(np.zeros((3, 6, 25, 1)), np.zeros((3, 25, 13, 1)),
                          list(range(13))), "u et v")

    print("\n── 7. ⚠️ La résolution temporelle RÉELLE est publiée ──")
    r20, r750, r3000 = (resolution_temporelle(20), resolution_temporelle(750),
                        resolution_temporelle(3000))
    verifier("à 20 m : 15 min, OBSERVÉE, incertitude nulle",
             r20["resolutionTemporelleMin"] == 15
             and r20["erreurInterpolationMs"] == 0.0)
    verifier("à 750 m : la zone d'extinction est signalée comme dégradée",
             "dégradée" in r750["regime"])
    verifier("⚠️ à 3 000 m : 60 min, INTERPOLÉE, et l'erreur est chiffrée",
             r3000["resolutionTemporelleMin"] == 60
             and r3000["erreurInterpolationMs"] > 0.5,
             f"{r3000['erreurInterpolationMs']} m/s")
    verifier("le diagnostic porte les 25 niveaux avec leur régime",
             len(diag["niveaux"]) == len(NIVEAUX_H_0025)
             and all("regime" in n for n in diag["niveaux"]))
    verifier("il dit que l'extinction est une CONVENTION, pas une mesure",
             "CONVENTION" in diag["conventions"]["extinction"])
    verifier("et il porte les deux chiffres qui justifient le composite",
             diag["mesures"]["delta_pi_arome_median_ms"] > 2
             * diag["mesures"]["erreur_interpolation_median_ms"],
             f"Δ {diag['mesures']['delta_pi_arome_median_ms']} contre "
             f"{diag['mesures']['erreur_interpolation_median_ms']} m/s")

    print("\n  composite :", "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    for e in echecs:
        print(f"    ⛔ {e}")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
