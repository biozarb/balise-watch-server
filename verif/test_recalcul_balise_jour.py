#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  verif/test_recalcul_balise_jour.py — le banc du contrôle n°2 (S3)
#                                                        (23/08/2026)
#
#  ⛔ CE BANC DOIT SAVOIR ÉCHOUER. Chacune des mutations du §3 du prompt
#  S3 qui le concerne est rejouée ici, EN MÉMOIRE, et l'assertion qui
#  rougit est NOMMÉE dans son libellé — pas seulement « le banc rougit ».
#  Leçon du S0.5 : un banc qui teste deux gardes à la fois n'en teste
#  qu'une.
#
#  ⚠️ ET LA LEÇON DU S0.11 : compter n'est pas mesurer, et une mutation
#  doit être VÉRIFIÉE COMME S'ÉTANT APPLIQUÉE. Ici les mutations ne sont
#  pas des `str.replace` sur du texte : ce sont de vraies fonctions
#  fausses, passées en paramètre. Elles ne peuvent donc pas « ne pas
#  s'appliquer ».
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import ast
import math
import os
import sys
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))

# ⛔ L'IMPORT EST SOUS `try`, ET CE N'EST PAS DE LA PRUDENCE DÉCORATIVE.
# La campagne de mutations du 23/08 a montré que la mutation n°3 (« le
# recalcul importe `scoring` ») faisait CRASHER ce banc à l'import —
# `scoring` n'est pas sur le chemin de `verif/` — au lieu de le faire
# rougir. Un banc qui plante et un banc qui échoue ne se lisent pas
# pareil : le premier ne dit pas ce qui ne va pas, et un outil de
# mutation qui compte les ❌ le prend pour un SURVIVANT. Ici, la faute
# est nommée.
try:
    import recalcul_balise_jour as R      # noqa: E402
    ERREUR_IMPORT = None
except Exception as exc:                  # noqa: BLE001
    R = None
    ERREUR_IMPORT = exc

OK = KO = 0


def check(label, got, want, tol=1e-9):
    global OK, KO
    if isinstance(got, bool) or isinstance(want, bool):
        same = got is want
    elif isinstance(got, (int, float)) and isinstance(want, (int, float)):
        same = abs(got - want) <= tol + tol * abs(want)
    else:
        same = got == want
    if same:
        OK += 1
    else:
        KO += 1
        print(f"  ❌ {label}\n       obtenu  : {got!r}\n       attendu : {want!r}")


# ══════════════════════════════════════════════════════════════════
#  1. ⛔ MUTATION N°3 — le recalcul ne doit RIEN importer du scoring
# ══════════════════════════════════════════════════════════════════

def _imports_de(fichier: Path) -> set[str]:
    """Les modules importés, Y COMPRIS dans les imports LOCAUX — c'est
    justement à l'intérieur d'une fonction qu'on triche."""
    arbre = ast.parse(fichier.read_text(encoding="utf-8"), filename=str(fichier))
    noms = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Import):
            noms.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            noms.add(n.module.split(".")[0])
    return noms


INTERDITS = {"score", "scoring", "inference", "events"}


def test_aucun_import_du_scoring():
    print("\n── ⛔ le recalcul est-il vraiment indépendant ? ──")
    fichier = ICI / "recalcul_balise_jour.py"
    trouves = _imports_de(fichier) & INTERDITS
    check("`recalcul_balise_jour.py` n'importe NI `score` NI `scoring` "
          "(ni `inference`, ni `events`)", sorted(trouves), [])

    # ⛔ LE BANC SAIT-IL ÉCHOUER ? On fabrique la faute en mémoire et on
    # vérifie que la règle la voit — statiquement, donc même dans une
    # branche qui ne s'exécuterait jamais.
    faux = ast.parse(
        "def f():\n"
        "    if 0:\n"
        "        from scoring import series_error\n"
        "    return 1\n")
    noms = set()
    for n in ast.walk(faux):
        if isinstance(n, ast.ImportFrom) and n.module:
            noms.add(n.module.split(".")[0])
    check("MUTATION 3 — un `from scoring import …` caché dans une branche "
          "morte serait bien vu comme un import interdit",
          bool(noms & INTERDITS), True)
    # ⚠️ Et la seconde barrière, qui vaut mieux qu'une règle : le fichier
    # n'ouvre AUCUN chemin vers `model-verif/`. Même écrit, l'import
    # interdit ne se résoudrait pas.
    texte = fichier.read_text(encoding="utf-8")
    chemins = [l for l in texte.splitlines() if "sys.path" in l]
    check("le seul chemin ajouté est `tools/` — jamais `model-verif/`",
          all("outils" in l or "sys.path:" in l for l in chemins)
          and not any("model-verif" in l for l in chemins),
          True)


# ══════════════════════════════════════════════════════════════════
#  2. L'ARITHMÉTIQUE — vérifiée contre une valeur CALCULÉE À LA MAIN
# ══════════════════════════════════════════════════════════════════
#
#  ⛔ Les valeurs attendues ci-dessous ne sortent pas du code : elles
#  sortent de la trigonométrie. Deux vents de MÊME force `V` séparés
#  d'un angle `Δ` ont pour écart vectoriel `2·V·sin(Δ/2)` — un triangle
#  isocèle, rien de plus. Comparer le code à lui-même n'aurait rien
#  prouvé ; c'est le défaut que le contrôle n°2 existe pour ne pas avoir.

def test_erreur_horaire():
    print("\n── l'erreur d'une heure, contre la trigonométrie ──")
    # 10 km/h à 200° contre 10 km/h à 260° : Δ = 60°, 2·10·sin(30°) = 10.
    check("deux vents égaux à 60° d'écart → 2·V·sin(Δ/2) = 10,0",
          R.erreur_horaire(10.0, 200.0, 10.0, 260.0), 10.0, tol=1e-9)
    # Δ = 180° : les vecteurs s'opposent, l'écart vaut 2·V.
    check("deux vents égaux opposés → 2·V = 24,0",
          R.erreur_horaire(12.0, 10.0, 12.0, 190.0), 24.0, tol=1e-9)
    # Même direction, forces différentes : l'écart vaut |ΔV|.
    check("même direction, 18 contre 11 → 7,0",
          R.erreur_horaire(18.0, 45.0, 11.0, 45.0), 7.0, tol=1e-9)
    # ⚠️ SOUS 5 km/h D'UN CÔTÉ, LE REPLI EST SCALAIRE. Un vent de 3 km/h
    # plein sud et un vent de 9 km/h plein nord ont un écart VECTORIEL de
    # 12 ; la définition dit 6, parce que la direction d'un vent de
    # 3 km/h est du bruit. C'est le repli, et il est testé pour lui-même.
    check("sous 5 km/h, repli scalaire : |9 − 3| = 6,0 (et NON 12)",
          R.erreur_horaire(9.0, 0.0, 3.0, 180.0), 6.0, tol=1e-9)
    check("… sans direction prévue non plus, repli scalaire",
          R.erreur_horaire(20.0, None, 14.0, 90.0), 6.0, tol=1e-9)

    # ⛔ MUTATION 2 (a) — la norme SCALAIRE au lieu de la vectorielle.
    def scalaire(f, fd, o, od):
        return abs(f - o)
    check("MUTATION 2a — une erreur purement scalaire rendrait 0 sur "
          "deux vents égaux opposés, là où la définition dit 24",
          scalaire(12.0, 10.0, 12.0, 190.0) == 24.0, False)

    # ⛔ MUTATION 2 (b) — un facteur faux (le classique m/s ↔ km/h).
    def facteur(f, fd, o, od):
        return R.erreur_horaire(f, fd, o, od) / 3.6
    check("MUTATION 2b — un facteur 3,6 ferait rendre 2,78 là où la "
          "définition dit 10,0",
          abs(facteur(10.0, 200.0, 10.0, 260.0) - 10.0) <= R.ECART_MAX_KMH,
          False)


def test_moyenne_des_releves():
    print("\n── la moyenne d'une fenêtre d'observation ──")
    # Force : moyenne ARITHMÉTIQUE. Direction : moyenne VECTORIELLE.
    # 350° et 10° : la moyenne vectorielle vaut 0°, l'arithmétique 180°.
    f, d, n = R.moyenne_des_releves([(0, 10.0, 350.0), (1, 10.0, 10.0)])
    check("force = moyenne arithmétique", f, 10.0)
    check("⛔ direction = moyenne VECTORIELLE : 350° et 10° → 0°, "
          "jamais 180°", round(d, 6), 0.0)
    check("n = nombre de forces finies", n, 2)

    # Un relevé sans girouette contribue à la FORCE mais pas à la
    # direction : sinon une station sans girouette ne serait jamais notée.
    f, d, n = R.moyenne_des_releves([(0, 20.0, 90.0), (1, 10.0, None)])
    check("un relevé sans direction compte quand même dans la force",
          f, 15.0)
    check("… et la direction reste celle du seul relevé qui en a une",
          round(d, 6), 90.0)

    # Sous 5 km/h, la direction est jetée — la force reste.
    f, d, n = R.moyenne_des_releves([(0, 2.0, 90.0), (1, 2.0, 270.0)])
    check("deux relevés à 2 km/h : la force survit", f, 2.0)
    check("… et la direction est None (bruit jeté, pas moyenné à zéro)",
          d, None)

    check("aucune force finie ⇒ (None, None, 0)",
          R.moyenne_des_releves([(0, None, 90.0)]), (None, None, 0))


# ══════════════════════════════════════════════════════════════════
#  3. L'APPARIEMENT — la partie que le §2.2 du prompt appelait « le
#     vrai risque », et qu'on a choisi de REFAIRE plutôt que de sauter
# ══════════════════════════════════════════════════════════════════

JOUR_MS = 1_787_356_800_000          # 2026-08-22 00:00:00 UTC


def _prevision(vitesses, directions=None, t0_ms=JOUR_MS, pas_s=3600):
    return {"t0": t0_ms // 1000, "step_s": pas_s, "speed": vitesses,
            "dir": directions if directions is not None
            else [200.0] * len(vitesses)}


def _releves(heures, force, direction=200.0, decalage_s=0):
    return [(JOUR_MS + h * 3_600_000 + decalage_s * 1000, force, direction)
            for h in heures]


def test_appariement():
    print("\n── l'appariement, refait depuis la définition ──")
    # 24 heures prévues, un relevé pile à l'heure, prévision = observation.
    prev = _prevision([12.0] * 24)
    obs = _releves(range(24), 12.0)
    err, n = R.recalculer(prev, obs, JOUR_MS)
    check("prévision = observation → erreur nulle sur 24 h", err, 0.0)
    check("… sur 24 heures appariées", n, 24)

    # ⚠️ ±20 MIN, PAS 21. Un relevé à 21 min n'est PAS dans la fenêtre :
    # l'heure est ABSENTE, jamais comblée.
    err, n = R.recalculer(prev, _releves(range(24), 12.0, decalage_s=20 * 60),
                          JOUR_MS)
    check("un relevé à +20 min pile est DANS la fenêtre", n, 24)
    err, n = R.recalculer(prev, _releves(range(24), 12.0, decalage_s=21 * 60),
                          JOUR_MS)
    check("⛔ un relevé à +21 min ne l'est plus — et l'heure n'est pas "
          "comblée : 0 heure appariée", n, 0)
    check("… donc pas d'`err_vec_med` du tout", err, None)

    # Le seuil de 6 heures.
    err, n = R.recalculer(_prevision([12.0] * 5), _releves(range(5), 12.0),
                          JOUR_MS)
    check("5 heures appariées : sous le seuil, aucune valeur", err, None)
    err, n = R.recalculer(_prevision([12.0] * 6), _releves(range(6), 12.0),
                          JOUR_MS)
    check("6 heures appariées : la journée compte", err, 0.0)

    # ⛔ SEULS LES PAS DE LA JOURNÉE NOTÉE. Une prévision émise l'avant-
    # veille couvre 72 h ; seules ses heures 48-71 tombent dans la
    # journée notée, et c'est ce qui donne la classe « +48 h ».
    prev72 = _prevision([12.0] * 72, t0_ms=JOUR_MS - 2 * 86_400_000)
    err, n = R.recalculer(prev72, _releves(range(24), 12.0), JOUR_MS)
    check("une prévision de 72 h émise à J−2 n'apparie que les 24 h de "
          "la journée notée", n, 24)

    # Une vitesse absente ne s'apparie pas — et ne vaut JAMAIS 0.
    v = [12.0] * 24
    v[3] = None
    err, n = R.recalculer(_prevision(v), _releves(range(24), 12.0), JOUR_MS)
    check("une vitesse prévue absente saute son heure (jamais 0)", n, 23)
    check("… et n'introduit aucune erreur", err, 0.0)


def test_ecart_detectable():
    print("\n── un écart réel est-il vu ? ──")
    # Prévision décalée de 6 km/h en force : err_vec_med = 6.
    prev = _prevision([18.0] * 24)
    err, _ = R.recalculer(prev, _releves(range(24), 12.0), JOUR_MS)
    check("6 km/h d'écart constant → err_vec_med = 6,0", err, 6.0)
    check("… c'est 120 fois le seuil de signalement",
          err > R.ECART_MAX_KMH, True)
    # Un écart SOUS le seuil ne doit PAS crier : le détecteur ne doit pas
    # se déclencher sur l'arrondi à 4 décimales de la base.
    err, _ = R.recalculer(_prevision([12.02] * 24),
                          _releves(range(24), 12.0), JOUR_MS)
    check("0,02 km/h d'écart reste SOUS le seuil de 0,05",
          err <= R.ECART_MAX_KMH, True)


# ══════════════════════════════════════════════════════════════════
#  4. ⛔ MUTATION N°5 — le tirage rendu UNIFORME
# ══════════════════════════════════════════════════════════════════
#
#  Le chiffre qui justifie la stratification est réel : le 22/08,
#  2 925 balises sur 3 497 ne portaient qu'`arome_r2`. La fixture le
#  reproduit à l'échelle — une strate écrasante et une strate rare.

def _population(gros: int, petit: int):
    c = [{"flux": "fcstarome", "source": "windsmobi",
          "station_id": f"w{i}", "model": "arome_r2", "lead_h": 6}
         for i in range(gros)]
    c += [{"flux": "fcst", "source": "pioupiou",
           "station_id": f"p{i}", "model": "ecmwf_ifs025", "lead_h": 6}
          for i in range(petit)]
    return c


def test_tirage_stratifie():
    print("\n── ⛔ le tirage est-il stratifié, et reproductible ? ──")
    pop = _population(2925, 572)
    choisis, tailles = R.tirer_stratifie(pop, 20, R.graine_du_jour(
        __import__("datetime").datetime(2026, 8, 22)))
    petits = sum(1 for c in choisis if c["flux"] == "fcst")
    check("les deux strates sont vues", len(tailles), 2)
    check("20 balise-jours tirés", len(choisis), 20)
    check("⭐ la strate RARE reçoit sa moitié (10), pas sa proportion "
          "(≈3) — c'est toute la raison d'être de la stratification",
          petits, 10)

    # ⛔ MUTATION 5 — le tirage uniforme, écrit ici pour être éprouvé.
    def uniforme(candidats, n, graine):
        rnd = R.Xorshift32(graine)
        lot = list(candidats)
        for i in range(len(lot) - 1, 0, -1):
            j = int(rnd.suivant() * (i + 1))
            lot[i], lot[j] = lot[j], lot[i]
        return lot[:n], {}
    tires_u, _ = uniforme(pop, 20, 1234)
    petits_u = sum(1 for c in tires_u if c["flux"] == "fcst")
    check("MUTATION 5 — un tirage uniforme laisse la strate rare sous "
          "sa moitié (elle pèse 16 % de la population)",
          petits_u >= 10, False)

    # ⛔ REPRODUCTIBLE : la graine vient du JOUR, jamais de l'horloge.
    dt = __import__("datetime")
    g1 = R.graine_du_jour(dt.datetime(2026, 8, 22))
    g2 = R.graine_du_jour(dt.datetime(2026, 8, 22))
    g3 = R.graine_du_jour(dt.datetime(2026, 8, 23))
    check("même journée ⇒ même graine", g1, g2)
    check("journée différente ⇒ graine différente", g1 == g3, False)
    a, _ = R.tirer_stratifie(pop, 20, g1)
    b, _ = R.tirer_stratifie(pop, 20, g1)
    check("⭐ deux tirages de la même journée sont IDENTIQUES — un écart "
          "qu'on ne peut pas rejouer n'est pas un signalement",
          [x["station_id"] for x in a], [x["station_id"] for x in b])

    # Une strate vide ne bloque pas le tour de table.
    choisis, tailles = R.tirer_stratifie(_population(3, 0), 20, g1)
    check("une population plus petite que le tirage ne boucle pas",
          len(choisis), 3)


def test_cles_darchive():
    print("\n── les clés d'archive, réécrites et non importées ──")
    dt = __import__("datetime")
    j = dt.datetime(2026, 8, 22)
    check("`fcst`", R.FLUX_PREVISION["fcst"](j),
          "fcst/2026/08/fcst_2026-08-22.ndjson.gz")
    check("`fcst` partie 2", R.cle_fcst_partie(j, 2),
          "fcst/2026/08/fcst_2026-08-22_p2.ndjson.gz")
    check("`fcstreduit` (S0.11)", R.FLUX_PREVISION["fcstreduit"](j),
          "fcstreduit/2026/08/fcstreduit_2026-08-22.ndjson.gz")
    check("`obsmetar` (entré à la notation le 23/08)",
          R.FLUX_OBSERVATION["metar"](j),
          "obsmetar/2026/08/obsmetar_2026-08-22.ndjson.gz")
    check("les six flux d'observation sont là", len(R.FLUX_OBSERVATION), 6)
    check("les quatre flux de prévision sont là", len(R.FLUX_PREVISION), 4)


def main() -> int:
    # ⛔ LA RÈGLE STATIQUE D'ABORD : elle ne demande pas le module, donc
    # elle parle même quand le module ne s'importe plus.
    test_aucun_import_du_scoring()
    if R is None:
        check(f"⛔ `recalcul_balise_jour` ne s'importe pas : "
              f"{type(ERREUR_IMPORT).__name__} — {ERREUR_IMPORT}",
              False, True)
        print(f"\n{OK} assertions vertes, {KO} rouges.")
        return 1
    for fn in (test_erreur_horaire,
               test_moyenne_des_releves, test_appariement,
               test_ecart_detectable, test_tirage_stratifie,
               test_cles_darchive):
        fn()
    print(f"\n{OK} assertions vertes, {KO} rouges.")
    return 1 if KO else 0


if __name__ == "__main__":
    sys.exit(main())
