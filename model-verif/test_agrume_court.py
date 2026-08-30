# ══════════════════════════════════════════════════════════════════════
#  model-verif/test_agrume_court.py — le banc de la CLASSE COURTE
#                                              (Lot L10, 30/08/2026)
#
#  Sans réseau, sans clé, sans base.
#
#      python3 test_agrume_court.py
#
#  ═══ CE QUE CHACUN TIENT, ET CE QUE ÇA COÛTERAIT DE NE PAS L'AVOIR ═══
#
#  · heure cible   → l'heure de T comptée      → on note un constat, pas
#                                                une prévision
#  · run du futur  → run choisi sur son HEURE  → ⛔ information du futur :
#                    et non sur sa POSE          la classe brille, et rien
#                                                n'a l'air anormal
#  · alignement    → Δ posé échéance à échéance→ la correction de 10 h Z
#                    sur deux runs décalés       sur la prévision de 04 h Z
#  · décalage nul  → le lot L10 change la       → la classe +6 h dérive
#                    classe +6 h en passant       sans qu'une ligne ne le dise
#  · poids         → la rampe survit dans la    → de l'AROME pur sous une
#                    classe courte                étiquette PI
#  · découpe       → heures éteintes avec 0     → « le modèle annonçait
#                                                 calme » sur une heure
#                                                 jamais servie
#  · préfixe PI    → deux écritures divergentes → on énumère un préfixe que
#                                                 plus personne n'alimente
#  · étiquettes    → une seule pour deux T      → deux runs dans une même
#                                                 journée-balise
# ══════════════════════════════════════════════════════════════════════
from __future__ import annotations

import os
import sys
from datetime import datetime, time, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import agrume_court as C                                    # noqa: E402
import agrume_fcst as A                                     # noqa: E402
import score as J                                           # noqa: E402
# ⓘ LA FABRIQUE S'IMPORTE, ELLE NE SE RECOPIE PAS. `archive_a` et
# `archive_pi` construisent des archives conformes aux DEUX ordres
# d'axes (produit A en `(balise, param, niveau, échéance)`, PI en
# `(param, niveau, échéance, balise)`) — les recopier ici serait se
# donner une seconde occasion de les confondre, ce que le banc du
# 26/08 nomme comme la faute qui « ne lèverait pas ».
from test_agrume_pi_fcst import (BALISES, MINUTES,          # noqa: E402
                                 archive_a, archive_pi)
from composite import facteur_cisaillement, poids_pi        # noqa: E402
from pi import cles_du_run_colonnes                         # noqa: E402

ECHECS: list[str] = []
UTC = timezone.utc


def verifie(condition, message):
    if condition:
        print(f"  ✅ {message}")
    else:
        print(f"  ❌ {message}")
        ECHECS.append(message)


def muet(*_a, **_k):
    pass


# ══════════════════════════════════════════════════════════════════
#  1. LES HEURES CIBLES — strictement après T
# ══════════════════════════════════════════════════════════════════

def test_heures_cibles_strictement_apres_t():
    """Les six heures cibles suivent T, et l'heure de T ne compte pas."""
    jour = datetime(2026, 8, 29, tzinfo=UTC)
    for h, m, attendu in ((6, 50, [7, 8, 9, 10, 11, 12]),
                          (12, 50, [13, 14, 15, 16, 17, 18]),
                          (6, 30, [7, 8, 9, 10, 11, 12]),
                          # ⛔ LE CAS LIMITE : à 06:00 PILE, l'heure 06 Z
                          # n'est pas une prévision, c'est l'instant même.
                          (6, 0, [7, 8, 9, 10, 11, 12])):
        T = jour.replace(hour=h, minute=m)
        got = [x.hour for x in C.heures_cibles(T)]
        verifie(got == attendu,
                f"T = {h:02d}:{m:02d} Z → heures cibles {got}")
    verifie(len(C.heures_cibles(jour.replace(hour=6, minute=50)))
            == C.HEURES_CIBLES,
            f"il y en a exactement {C.HEURES_CIBLES}")


# ══════════════════════════════════════════════════════════════════
#  2. ⛔⛔ LE RUN DU FUTUR — la faute qui rendrait tout le lot faux
# ══════════════════════════════════════════════════════════════════

def test_le_run_du_futur_est_refuse():
    """Un run existe à son heure ; nos octets, eux, arrivent plus tard."""
    jour = datetime(2026, 8, 29, tzinfo=UTC)
    runs = {
        jour.replace(hour=0): jour.replace(hour=5, minute=30),   # posé 05:30
        jour.replace(hour=6): jour.replace(hour=6, minute=42),   # posé 06:42
        jour.replace(hour=7): jour.replace(hour=7, minute=41),   # posé 07:41
    }
    r, pose = C.run_disponible(runs, jour.replace(hour=6, minute=50))
    verifie(r == jour.replace(hour=6),
            f"à 06:50 Z, le run retenu est 06 Z (posé 06:42) — {r}")

    r30, _ = C.run_disponible(runs, jour.replace(hour=6, minute=30))
    verifie(r30 == jour.replace(hour=0),
            "⛔ à 06:30 Z, le run 06 Z n'était PAS encore posé (06:42) : "
            f"on retombe sur 00 Z — {r30}")
    verifie(r30 != jour.replace(hour=6),
            "⛔⛔ et surtout PAS le run 06 Z : le choisir sur son HEURE "
            "plutôt que sur sa POSE serait se noter avec de "
            "l'information du futur")

    vide, _ = C.run_disponible(runs, jour.replace(hour=3))
    verifie(vide is None,
            "avant toute pose, il n'y a pas de run — et on le dit "
            "plutôt que d'en inventer un")


# ══════════════════════════════════════════════════════════════════
#  3. ⛔⛔ L'ALIGNEMENT — par heure VALIDE, jamais par échéance
# ══════════════════════════════════════════════════════════════════

def _archives_marquees():
    """AROME porte `u = step`, PI porte `u = 100 + heure_pi`.

    ⭐ LES VALEURS SONT DES MARQUEURS, PAS DE LA MÉTÉO : chaque heure
    porte un nombre différent, donc un Δ pris à la mauvaise heure rend
    un nombre différent lui aussi. Un banc bâti sur un vent constant
    serait vert quel que soit l'alignement — c'est-à-dire inutile.
    """
    col, man = archive_a(lambda k, s: (float(s), 0.0),
                         lambda k, s: (float(s), 0.0))
    d_pi, man_pi = archive_pi(lambda bid, m: (100.0 + m / 60.0, 0.0))
    return col, man, d_pi, man_pi


def test_delta_aligne_sur_l_heure_valide():
    """Un PI plus frais de 6 h se pose sur la BONNE heure d'AROME."""
    col, man, d_pi, man_pi = _archives_marquees()
    d = A.delta_20m(col, d_pi, man_pi, crier=muet, decalage_h=6, poids=1.0)
    k0 = 0
    heures = sorted(d[k0])
    verifie(heures == [6, 7, 8, 9, 10, 11, 12],
            f"les heures corrigées sont les échéances AROME 6..12 — {heures}")
    f = facteur_cisaillement(A.NIVEAU_DELTA_APPLIQUE)
    # u_pi(h−6) = 100 + (h−6) ; u_ar(h) = h ⇒ Δ = 94, à toute heure.
    attendu = f * 94.0
    verifie(all(abs(d[k0][h][0] - attendu) < 1e-3 for h in heures),
            f"⭐ Δu vaut {attendu:.3f} à CHAQUE heure — c'est-à-dire "
            "`u_pi(h−6) − u_ar(h)`, l'appariement par heure valide")
    # ⛔ Ce qu'aurait rendu un alignement par ÉCHÉANCE (le défaut) :
    faux = f * 100.0
    verifie(abs(d[k0][heures[0]][0] - faux) > 1e-3,
            "⛔ et surtout PAS `u_pi(h) − u_ar(h)` = "
            f"{faux:.3f} : ce serait la correction de 10 h Z posée sur "
            "la prévision de 04 h Z — finie, plausible, fausse de six heures")


def test_decalage_nul_ne_change_rien():
    """Le lot L10 ne doit pas déplacer la classe +6 h d'un centième."""
    col, man, d_pi, man_pi = _archives_marquees()
    avant = A.delta_20m(col, d_pi, man_pi, crier=muet)
    apres = A.delta_20m(col, d_pi, man_pi, crier=muet, decalage_h=0,
                        poids=None)
    verifie(avant == apres,
            "`decalage_h=0, poids=None` rend EXACTEMENT ce que rendait "
            "l'appel d'avant le lot L10")
    f = facteur_cisaillement(A.NIVEAU_DELTA_APPLIQUE)
    h = sorted(avant[0])[1]
    attendu = poids_pi(h * 60) * f * 100.0
    verifie(abs(avant[0][h][0] - attendu) < 1e-3,
            f"… et la RAMPE y est toujours (h={h} : {attendu:.3f})")


def test_poids_constant_remplace_la_rampe():
    """Dans la classe courte, le poids est constant — Q7."""
    col, man, d_pi, man_pi = _archives_marquees()
    f = facteur_cisaillement(A.NIVEAU_DELTA_APPLIQUE)
    for w in (1.0, 0.5):
        d = A.delta_20m(col, d_pi, man_pi, crier=muet, decalage_h=6, poids=w)
        heures = sorted(d[0])
        vals = {round(d[0][h][0] / (f * 94.0), 6) for h in heures}
        verifie(vals == {round(w, 6)},
                f"w = {w} : le facteur est LE MÊME aux six heures — {vals}")
    d1 = A.delta_20m(col, d_pi, man_pi, crier=muet, decalage_h=6, poids=1.0)
    d05 = A.delta_20m(col, d_pi, man_pi, crier=muet, decalage_h=6, poids=0.5)
    h = sorted(d1[0])[0]
    verifie(abs(d05[0][h][0] * 2 - d1[0][h][0]) < 1e-6,
            "⭐ w=0,5 rend exactement la moitié de w=1 — les deux "
            "sous-séries ne diffèrent QUE par le poids")
    # ⛔ La rampe, elle, vaudrait autre chose à chaque heure.
    rampe = A.delta_20m(col, d_pi, man_pi, crier=muet, decalage_h=6)
    verifie(len({round(rampe[0][h][0], 4) for h in sorted(rampe[0])}) > 1,
            "⛔ … alors que la rampe donnerait une valeur DIFFÉRENTE par "
            "heure : la confondre servirait de l'AROME pur sous une "
            "étiquette PI")


# ══════════════════════════════════════════════════════════════════
#  4. LA DÉCOUPE — éteindre avec `None`, jamais avec 0
# ══════════════════════════════════════════════════════════════════

def test_restreindre_eteint_avec_none_jamais_zero():
    """Une heure hors classe est ABSENTE, pas calme."""
    row = {"speed": [float(i) for i in range(12)],
           "dir": [float(i) for i in range(12)]}
    n = C.restreindre(row, {7, 8, 9})
    verifie(n == 3, f"trois heures servies — {n}")
    verifie(row["speed"][7] == 7.0 and row["dir"][9] == 9.0,
            "les heures visées sont intactes")
    verifie(all(row["speed"][i] is None for i in range(12) if i not in (7, 8, 9)),
            "⛔ toutes les autres valent `None`")
    verifie(not any(row["speed"][i] == 0 for i in range(12) if i not in (7, 8, 9)),
            "⛔⛔ et AUCUNE ne vaut 0 — un 0 est un vent crédible, et le "
            "scoring lirait « le modèle annonçait calme »")
    creux = {"speed": [None] * 6, "dir": [None] * 6}
    verifie(C.restreindre(creux, {1, 2}) == 0,
            "une ligne sans aucune valeur rend 0 (elle sera écartée)")


# ══════════════════════════════════════════════════════════════════
#  5. LES CONVENTIONS QUI NE DOIVENT PAS DIVERGER
# ══════════════════════════════════════════════════════════════════

def test_prefixe_pi_coherent():
    """Le préfixe énuméré est celui que la lecture emploie."""
    cle, _ = cles_du_run_colonnes("2026-08-29T06:00:00Z")
    verifie(cle.startswith(C.PREFIXE_PI),
            f"`{C.PREFIXE_PI}` préfixe bien `{cle}` — les deux écritures "
            "de la convention ne peuvent pas diverger en silence")


def test_les_deux_t_ne_partagent_pas_leur_etiquette():
    """Deux instants T, deux `lead_h` — et négatifs."""
    verifie(J.LEAD_COURT_MATIN != J.LEAD_COURT_APREM,
            "les deux instants T portent DEUX étiquettes distinctes : "
            "sans ça, la clé primaire de `model_verif_daily` obligerait "
            "à mêler deux runs dans une même journée-balise")
    verifie(all(l < 0 for l in J.LEADS_COURTS),
            "⛔ elles sont NÉGATIVES : impossible de les lire comme une "
            "échéance à côté de 6, 24 et 48")
    verifie(not set(J.LEADS_COURTS) & set(J.LEAD_BY_OFFSET.values()),
            "… et elles ne collident avec aucune échéance existante")
    verifie(set(C.POIDS) == set(J.MODELES_COURTS),
            "les deux sous-séries du collecteur sont exactement celles "
            "que `score.py` écarte du rang")
    verifie(C.POIDS[J.AGRUME_COURT_W1] == 1.0
            and C.POIDS[J.AGRUME_COURT_W05] == 0.5,
            "⭐ le NOM de chaque série porte son poids — un poids qui ne "
            "vivrait que dans un manifeste deviendrait illisible")
    verifie((C.T_MATIN, C.T_APREM) == (time(6, 50), time(12, 50)),
            "les deux instants T sont ceux que la sonde du 30/08 a "
            "mesurés (06:50 et 12:50 Z), pas ceux de l'exemple")


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
        print(f"❌ banc de la classe courte : {len(ECHECS)} échec(s)")
        for e in ECHECS:
            print(f"   · {e}")
        return 1
    print("✅ banc de la classe courte : tout est vert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
