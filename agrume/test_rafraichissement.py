"""
test_rafraichissement.py — banc du rafraîchissement PI (Lot L2), HORS-LIGNE.

    python3 agrume/test_rafraichissement.py

⚠️ CE QUE CE BANC PROTÈGE.

Ce module publie, sous une clé que le client va PRÉFÉRER au produit B,
une valeur calculée à partir de deux chaînes qui ne tournent ni au même
endroit ni à la même cadence. Aucune de ses erreurs ne lève : elles
produisent toutes un vent lisse, continu et plausible. Neuf façons de
casser en silence, une par section :

  1. **Lire les mauvaises échéances du produit B.** Le cahier des
     charges du lot annonçait « les échéances 0→7 ». Ce n'est vrai que
     si les deux runs commencent à la même heure — mesuré le 17/08, le
     dernier produit B avait SIX HEURES de retard sur le dernier run PI.
     Composer PI de 09 h avec de l'AROME valide à 03 h donnerait un Δ de
     six heures de dérive, lisse et faux partout.
  2. **Des axes qui ne coïncident pas.** Une colonne d'écart vaut
     1,95 km : Δ deviendrait une carte de gradient horizontal déguisée
     en correction temporelle. Déjà payé le 10/08 (61×85 contre 61×84).
  3. **Fabriquer là où PI n'existe pas.** Deux domaines sur trois n'ont
     aucun champ PI. Un objet vide y serait pire qu'aucun objet.
  4. **Perdre l'invariant.** Aux niveaux communs et tant que `w_PI = 1`,
     le composite DOIT reproduire PI. Sinon on a inventé une valeur là
     où PI en donnait une.
  5. **Laisser croire au-delà de l'horizon.** À 6 h, `w_PI = 0` : la
     valeur est de l'AROME horaire INTERPOLÉ, à tous les niveaux — y
     compris à 20 m, où la table par niveau dit « observée (PI) ».
  6. **Deux jumeaux qui divergent.** `carte.bin` nourrit le calque,
     `colonnes.bin` la coupe. S'ils ne disent pas la même chose, le même
     vent au même instant a deux valeurs selon l'écran regardé.
  7. **Un manifeste qui ment sur les octets.** Les offsets publiés sont
     tout ce que le client a ; un offset faux rend des octets VALIDES au
     mauvais endroit, et le Range répond 206.
  8. **Perdre `resolutionTemporelleMin`.** C'est le champ le plus
     important de la réponse : sans lui l'objet affirme une résolution
     qu'il n'a pas.
  9. **Publier un couple dépareillé.** Les jumeaux s'écrivent ensemble
     ou pas du tout, et un objet écrit hors index est une FUITE — pas un
     déchet — puisque `ListObjects` n'est pas une route de ce projet.

Aucun réseau, aucune clé, aucun GRIB.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

import grille as GR  # noqa: E402
import rafraichissement as RA  # noqa: E402
from composite import TAU_PLEIN_MIN, arome_interpole  # noqa: E402
from domaine import DOMAINES_PI  # noqa: E402
from pi import (CLE_INDEX_RAFRAICHISSEMENT, ECHEANCES_MIN,  # noqa: E402
                NIVEAUX_DELTA, NIVEAUX_PI, Abort,
                cles_du_rafraichissement)
from quantification import quantifier  # noqa: E402

echecs = []


def verifier(nom, condition, detail=""):
    print(f"  {'✓' if condition else '✗'} {nom}"
          + (f"   {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


def leve(nom, fn, fragment=None):
    try:
        fn()
    except Abort as e:
        ok = fragment is None or fragment in str(e)
        return verifier(nom, ok, "" if ok else f"message inattendu : {e}")
    except Exception as e:                                   # noqa: BLE001
        return verifier(nom, False, f"a levé {type(e).__name__}: {e}")
    return verifier(nom, False, "n'a RIEN levé")


# ══════════════════════════════════════════════════════════════════════
#  Le décor : un domaine 5 × 7, et ce n'est pas un hasard
# ══════════════════════════════════════════════════════════════════════
#  ⚠️ 5 × 7 est la forme qui a démenti l'alignement « par arithmétique
#  heureuse » du produit B le 12/08 : sur le domaine réel les offsets
#  tombaient juste par coïncidence. Un banc sur 111 × 105 aurait laissé
#  passer la même chose ici.
NJ, NI = 5, 7
RUN_PI = "2026-08-17T10:00:00Z"
RUN_B = "2026-08-17T03:00:00Z"
DOMAINE = DOMAINES_PI[0]
SANS_PI = "pyrenees"
STEPS_B = list(range(0, 20))

LATS = np.array([46.45 - 0.025 * k for k in range(NJ)], dtype=np.float32)
LONS = np.array([5.00 + 0.025 * k for k in range(NI)], dtype=np.float32)
ZSOL = (np.arange(NJ)[:, None] * 100.0
        + np.arange(NI)[None, :] * 10.0).astype(np.float32)


class StockBidon:
    """Un R2 en mémoire, avec Range — et qui SAIT tomber en panne.

    ⚠️ Il refuse les Range hors bornes plutôt que de rendre un tampon
    raboté : c'est exactement ce que le vrai objet fait (416), et c'est
    le défaut du 13/08 qu'on veut pouvoir rejouer.
    """

    def __init__(self):
        self.objets = {}
        self.entetes = {}
        self.supprimes = []
        self.panne = set()
        self.ordre_ecriture = []

    def get(self, cle):
        return self.objets.get(cle)

    def get_json(self, cle):
        brut = self.objets.get(cle)
        return json.loads(brut) if brut is not None else None

    def get_range(self, cle, debut, octets):
        brut = self.objets.get(cle)
        if brut is None:
            return None
        if debut < 0 or debut + octets > len(brut):
            raise Abort(f"Range {debut}+{octets} hors de {cle} "
                        f"({len(brut)} octets) — 416")
        return brut[debut:debut + octets]

    def put(self, cle, corps, *, cache_control, content_type="application/json",
            content_encoding=None):
        if cle in self.panne:
            raise RuntimeError("panne réseau simulée")
        self.objets[cle] = bytes(corps)
        self.entetes[cle] = (cache_control, content_type)
        self.ordre_ecriture.append(cle)
        return 200

    def delete(self, cle):
        self.supprimes.append(cle)
        self.objets.pop(cle, None)
        return True

    def bilan(self, log=print):
        return {}


def _champ_arome(c, z, h, j, i):
    """AROME analytique, volontairement PEU LISSE en τ.

    ⚠️ Un champ linéaire en τ ferait passer un composite faux :
    l'interpolation y serait exacte, donc Δ égal à l'écart PI−AROME
    vrai, donc l'invariant trivialement vérifié. La mesure dit d'ailleurs
    que le champ réel n'est pas lisse à l'échelle de l'heure (exposant
    0,5–0,9, pas 2).
    """
    return (3.0 + c * 1.5 + 0.4 * np.sin(h * 1.7 + z / 700.0 + c)
            + 0.05 * j - 0.03 * i + 0.2 * np.cos(h * 0.9))


def produit_b(stock, domaine=DOMAINE, run=RUN_B, steps=None,
              lats=LATS, lons=LONS, zsol=ZSOL, publier_index=True):
    """Un VRAI produit B : `Grille`, ses tampons, son manifeste, l'index.

    ⛔ On ne fabrique pas un faux manifeste à la main. Tout l'objet du
    banc est que ce module lise le format RÉEL — offsets, dtypes, noms
    de blocs, gabarit de clé — et non une paraphrase qui pourrait
    diverger de la production sans que rien ne le dise.
    """
    steps = STEPS_B if steps is None else steps
    g = GR.Grille(run, steps, lats, lons, zsol, domaine=domaine)
    jj, ii = np.meshgrid(np.arange(len(lats)), np.arange(len(lons)),
                         indexing="ij")
    for nom in ("u", "v"):
        c = 0 if nom == "u" else 1
        for z in RA.NIVEAUX:
            for s in steps:
                g.poser(nom, z, s, _champ_arome(c, z, float(s), jj, ii))
    base = f"agrume/grille/{domaine}/{run}"
    for s in steps:
        stock.objets[GR.cle_echeance(run, domaine, s)] = g.tampon_echeance(s)
    stock.objets[f"{base}/manifest.json"] = json.dumps(
        g.manifeste(), ensure_ascii=False).encode()
    if publier_index:
        idx = stock.get_json(GR.CLE_INDEX) or dict(runs=[], restes=[])
        idx["runs"] = [e for e in idx["runs"]
                       if not (e.get("run") == run
                               and e.get("domaine") == domaine)]
        idx["runs"].append(dict(run=run, domaine=domaine,
                                cles=GR.cles_du_run(run, domaine, steps)))
        stock.objets[GR.CLE_INDEX] = json.dumps(idx).encode()
    return g


def pi_bidon(lats=LATS, lons=LONS, ecart=1.3):
    """PI = AROME à l'instant vrai, PLUS un écart franc.

    ⓘ `ecart` est appliqué aux niveaux de Δ seulement. Il vaut 1,3 m/s,
    c'est-à-dire l'ordre de grandeur mesuré (0,76 m/s en médiane, 1,78
    au q90) : assez grand pour qu'un composite qui ignorerait Δ se voie,
    assez petit pour rester dans le domaine du float16.
    """
    nj, ni = len(lats), len(lons)
    jj, ii = np.meshgrid(np.arange(nj), np.arange(ni), indexing="ij")
    out = np.full((2, len(NIVEAUX_PI), len(ECHEANCES_MIN), nj, ni), np.nan)
    for c in (0, 1):
        for iz, z in enumerate(NIVEAUX_PI):
            for it, m in enumerate(ECHEANCES_MIN):
                h = 7.0 + m / 60.0            # l'instant VRAI en τ AROME
                v = _champ_arome(c, z, h, jj, ii)
                if z in NIVEAUX_DELTA:
                    v = v + ecart * (1.0 + 0.1 * np.sin(m / 37.0))
                out[c, iz, it] = v
    return out


def fabriquer(stock=None, domaine=DOMAINE, run_pi=RUN_PI, **kw):
    stock = StockBidon() if stock is None else stock
    if not stock.objets:
        produit_b(stock, domaine=domaine, **kw)
    raf = RA.composer_rafraichissement(pi_bidon(), LATS, LONS, run_pi,
                                       domaine, stock, journal=lambda *_: None)
    return stock, raf


# ══════════════════════════════════════════════════════════════════════
def section_1_appariement():
    print("\n── 1. QUELLES échéances du produit B, et le cahier se "
          "trompait ──")
    verifier("le décalage se calcule sur les DEUX horodatages",
             RA.decalage_minutes(RUN_PI, RUN_B) == 420, "420 min = 7 h")
    # ⛔ LE CONTRÔLE QUI DÉMENT LE CAHIER DES CHARGES DU LOT.
    verifier("⛔ à 7 h de décalage, ce sont les échéances 7→13 du produit "
             "B — PAS « 0→7 » comme l'annonçait le cahier du lot : "
             "0→7 n'est vrai que si les deux runs partent à la même heure",
             RA.steps_necessaires(420, STEPS_B) == [7, 8, 9, 10, 11, 12, 13])
    verifier("…et à décalage nul, ce sont 0→6 (SEPT échéances, pas huit) : "
             "l'horizon de PI est 6 h pile, `arome_interpole` n'a besoin "
             "de rien au-delà",
             RA.steps_necessaires(0, STEPS_B) == [0, 1, 2, 3, 4, 5, 6])
    leve("⛔ un produit B POSTÉRIEUR au run PI est refusé — corriger un "
         "modèle avec un autre qui décrit un autre instant",
         lambda: RA.steps_necessaires(-60, STEPS_B), "POSTÉRIEUR")
    leve("⛔ une couverture trop courte est refusée, jamais extrapolée",
         lambda: RA.steps_necessaires(420, [0, 1, 2, 3]), "n'extrapole PAS")
    leve("⚠️ un TROU d'échéance est refusé : interpoler par-dessus "
         "traiterait deux heures d'écart comme une seule",
         lambda: RA.steps_necessaires(420, [7, 8, 9, 11, 12, 13]), "trou")


def section_2_axes():
    print("\n── 2. Les axes : une colonne d'écart vaut 1,95 km ──")
    stock = StockBidon()
    g = produit_b(stock)
    man = g.manifeste()
    verifier("des axes identiques passent", RA.verifier_axes(man, LATS, LONS))
    leve("⛔ UNE colonne de trop côté PI est refusée — Δ deviendrait une "
         "carte de gradient horizontal déguisée en correction temporelle",
         lambda: RA.verifier_axes(
             man, LATS, np.append(LONS, LONS[-1] + 0.025)), "1,95 km")
    leve("⛔ une fenêtre DÉCALÉE (même compte, autres bornes) est refusée",
         lambda: RA.verifier_axes(man, LATS, LONS + 0.025), "lon_premier")
    man_faux = dict(man, niveaux_m_sol=list(RA.NIVEAUX[:-1]))
    leve("⛔ un produit B qui ne porte pas les mêmes 25 niveaux hauteur "
         "est refusé : composer alignerait deux verticales par leur INDICE",
         lambda: RA.verifier_axes(man_faux, LATS, LONS), "verticales")

    # ── ⛔ ET LE CONTRÔLE SUR LA CHAÎNE ENTIÈRE, PAS SUR LA FONCTION ──
    # ⚠️ Ajouté APRÈS un rejeu qui a démenti ce banc : en retirant
    # l'appel à `verifier_axes()` du pipeline — pas la fonction, juste
    # son APPEL — les quatre contrôles ci-dessus restaient VERTS et le
    # banc rendait 0. Il ne prouvait que l'existence d'un garde-fou,
    # jamais son branchement. C'est mot pour mot la leçon du 13/08 :
    # « un banc qui ne teste qu'un site d'appel ne protège que celui-là ».
    lons_decalees = LONS + 0.025
    stock_dec = StockBidon()
    produit_b(stock_dec, lons=lons_decalees)
    leve("⛔⛔ la CHAÎNE ENTIÈRE refuse un produit B dont la fenêtre est "
         "décalée d'une colonne — le garde-fou est BRANCHÉ, pas seulement "
         "écrit",
         lambda: RA.composer_rafraichissement(
             pi_bidon(), LATS, LONS, RUN_PI, DOMAINE, stock_dec,
             journal=lambda *_: None), "axes incompatibles")
    stock_pi = StockBidon()
    produit_b(stock_pi)
    leve("…et symétriquement, une grille PI d'une colonne de trop est "
         "refusée avant toute lecture d'octets",
         lambda: RA.composer_rafraichissement(
             pi_bidon(lons=np.append(LONS, LONS[-1] + 0.025)), LATS,
             np.append(LONS, LONS[-1] + 0.025), RUN_PI, DOMAINE, stock_pi,
             journal=lambda *_: None), "1,95 km")


def section_3_sans_pi():
    print("\n── 3. Le domaine sans PI : on REFUSE de fabriquer ──")
    stock = StockBidon()
    produit_b(stock, domaine=SANS_PI)
    leve(f"⛔ sur `{SANS_PI}`, aucun rafraîchissement n'est fabriqué",
         lambda: RA.composer_rafraichissement(
             pi_bidon(), LATS, LONS, RUN_PI, SANS_PI, stock,
             journal=lambda *_: None), SANS_PI)
    try:
        RA.composer_rafraichissement(pi_bidon(), LATS, LONS, RUN_PI, SANS_PI,
                                     stock, journal=lambda *_: None)
        msg = ""
    except Abort as e:
        msg = str(e)
    verifier("…AVEC la raison en toutes lettres, celle que l'écran doit "
             "pouvoir dire — pas un code, pas un silence",
             len(msg) > 120 and "portée actuelle" in msg,
             f"{len(msg)} caractères")
    stock2 = StockBidon()
    leve("⛔ et sans AUCUN run du produit B en ligne, on refuse aussi : "
         "un objet vide serait pire qu'aucun objet",
         lambda: RA.composer_rafraichissement(
             pi_bidon(), LATS, LONS, RUN_PI, DOMAINE, stock2,
             journal=lambda *_: None), "aucun run du produit B")


def section_4_invariant():
    print("\n── 4. ⚠️⚠️ L'INVARIANT : aux niveaux communs, τ ≤ 4 h, "
          "composite == PI ──")
    _stock, raf = fabriquer()
    pi = pi_bidon()
    pires = []
    for c, nom in enumerate(RA.ORDRE_TRANCHES):
        # ⚠️ Le MÊME arrondi de publication des deux côtés. Sans lui, on
        # comparerait une valeur quantifiée à une valeur brute et
        # l'écart mesuré serait celui du float16, pas celui du calcul —
        # le piège qui a rendu un « 0/125 » crédible à l'étape 8.
        pi_q = quantifier(pi[c], RA.PARAMS_UV[nom]).astype(np.float32)
        for iz, z in enumerate(NIVEAUX_PI):
            if z not in NIVEAUX_DELTA:
                continue
            k = list(RA.NIVEAUX).index(z)
            for it, m in enumerate(ECHEANCES_MIN):
                if m > TAU_PLEIN_MIN:
                    continue
                a = raf.composite[c, k, it].astype(np.float32)
                pires.append(float(np.nanmax(np.abs(a - pi_q[iz, it]))))
    pire = max(pires)
    verifier("⚠️⚠️ le composite REPRODUIT PI aux 5 niveaux de Δ tant que "
             "`w_PI = 1` — sinon on a inventé une valeur là où PI en "
             "donnait une",
             pire == 0.0, f"écart max {pire:.3e} m/s sur {len(pires)} tranches")
    verifier("…et le composite N'EST PAS l'AROME interpolé : Δ a bien été "
             "appliqué (sinon ce banc ne prouverait rien)",
             float(np.nanmax(np.abs(
                 raf.composite[0, list(RA.NIVEAUX).index(100), 0]
                 .astype(np.float32)
                 - _champ_arome(0, 100, 7.0, *np.meshgrid(
                     np.arange(NJ), np.arange(NI), indexing="ij"))))) > 0.5)

    # ── ⚠️ LE MÊME FILTRE D'INVRAISEMBLANCE QUE LE PRODUIT B ──────────
    # Le composite est une SOMME (`AROME_interp + w·Δ`). Deux valeurs
    # extrêmes qui s'additionnent produisent un nombre fini, publiable,
    # et parfaitement absurde — et `float16` va jusqu'à 65 504, donc rien
    # ne déborde. `quantifier()` porte `PLAFOND_PHYSIQUE` (200 m/s sur
    # `u`/`v`) ; un simple `astype(float16)` ne le porterait pas, et la
    # différence ne se verrait sur AUCUNE donnée normale.
    # ⓘ Contrôle ajouté après un rejeu : sabotée en `astype(float16)`,
    # la publication restait VERTE sur le jeu nominal.
    absurde = np.zeros((2, len(RA.NIVEAUX), len(ECHEANCES_MIN), NJ, NI))
    absurde[0, 0, 0, 0, 0] = 900.0
    r_abs = RA.Rafraichissement(RUN_PI, DOMAINE, RUN_B, [7], 420, absurde,
                                raf.diagnostic, LATS, LONS)
    verifier("⚠️ une valeur physiquement absurde (900 m/s) devient NaN à "
             "la publication, jamais un vent plausible — c'est "
             "`quantifier()` qui le porte, pas `astype(float16)`",
             not np.isfinite(float(r_abs.composite[0, 0, 0, 0, 0]))
             and float(r_abs.composite[0, 1, 0, 0, 0]) == 0.0)


def section_5_horizon():
    print("\n── 5. À 6 h, `w_PI = 0` : aucune trace de PI, et l'objet le "
          "DIT ──")
    _stock, raf = fabriquer()
    poids = raf.diagnostic["poids_pi"]
    verifier("`w_PI` vaut 0 à la dernière échéance (360 min = l'horizon "
             "de PI, pas 7 h)", poids[-1] == 0.0)
    it = len(ECHEANCES_MIN) - 1
    jj, ii = np.meshgrid(np.arange(NJ), np.arange(NI), indexing="ij")
    attendu = arome_interpole(
        np.stack([_champ_arome(0, 20, float(s), jj, ii) for s in raf.steps_b],
                 axis=-1), raf.steps_b, 360 + raf.decalage_min)
    obtenu = raf.composite[0, list(RA.NIVEAUX).index(20), it].astype(np.float64)
    verifier("⛔ à 6 h, même à 20 m/sol, la valeur est de l'AROME HORAIRE "
             "INTERPOLÉ — pas une observation à 15 min",
             float(np.max(np.abs(obtenu - quantifier(
                 attendu, RA.PARAMS_UV["u"]).astype(np.float64)))) == 0.0)
    bloc = raf.provenance()["par_echeance"][-1]["blocs"]["hauteur"]
    verifier("…et la provenance de CETTE échéance dit `arome`, pas "
             "`arome+pi` — sinon l'écran affirmerait du PI qui n'y est pas",
             bloc["modele"] == "arome" and bloc["poids_pi"] == 0.0)
    verifier("…et elle ne nomme AUCUN run PI à cette échéance",
             "run_pi" not in bloc)
    verifier("⚠️ …et le régime temporel effectif est écrit en toutes "
             "lettres, parce que la table par niveau dit encore "
             "« observée (PI) » à 20 m",
             "INTERPOLÉ" in bloc["regime_temporel"])
    plein = raf.provenance()["par_echeance"][0]["blocs"]["hauteur"]
    verifier("à τ = 0, la provenance nomme les DEUX runs — celui d'AROME "
             "et celui de PI",
             plein["modele"] == "arome+pi" and plein["run"] == RUN_B
             and plein["run_pi"] == RUN_PI)


def section_6_jumeaux():
    print("\n── 6. ⛔ Les deux jumeaux disent LA MÊME CHOSE ──")
    _stock, raf = fabriquer()
    carte = raf.carte_bin()
    colonnes = raf.colonnes_bin()
    pas_e = raf.octets_par_echeance()
    pas_k = raf.octets_par_colonne()
    tr_c, tr_k = raf.tranches(), raf.tranches_colonne()
    nlev, nech = len(RA.NIVEAUX), len(ECHEANCES_MIN)
    pire, n = 0.0, 0
    for j in range(NJ):
        for i in range(NI):
            col = colonnes[(j * NI + i) * pas_k:(j * NI + i + 1) * pas_k]
            for nom in RA.ORDRE_TRANCHES:
                a = np.frombuffer(col, dtype="<f2",
                                  offset=tr_k[nom]["offset"],
                                  count=nlev * nech).reshape(nlev, nech)
                for il in range(nlev):
                    for ie in range(nech):
                        o = (ie * pas_e + tr_c[nom]["offset"]
                             + (il * NJ * NI + j * NI + i) * 2)
                        v = np.frombuffer(carte, dtype="<f2", offset=o,
                                          count=1)[0]
                        d = abs(float(v) - float(a[il, ie]))
                        pire = max(pire, d)
                        n += 1
    verifier("⛔ `carte.bin` et `colonnes.bin` rendent la MÊME valeur pour "
             "la même case — sinon le calque et la coupe montreraient deux "
             "vents au même instant",
             pire == 0.0, f"{n} cases, écart max {pire:.3e}")


def section_7_octets():
    print("\n── 7. Le manifeste décrit EXACTEMENT les octets écrits ──")
    _stock, raf = fabriquer()
    man = raf.manifeste()
    carte, colonnes = raf.carte_bin(), raf.colonnes_bin()
    sc = man["service"]["carte"]
    sk = man["service"]["colonnes"]
    verifier("la taille de `carte.bin` == 25 × `octets_par_echeance`",
             len(carte) == sc["octets_par_echeance"] * len(ECHEANCES_MIN),
             f"{len(carte)} o")
    verifier("la taille de `colonnes.bin` == nb_lat × nb_lon × "
             "`octets_par_colonne`",
             len(colonnes) == sk["octets_par_colonne"] * NJ * NI,
             f"{len(colonnes)} o")
    verifier("les tranches de `carte.bin` pavent EXACTEMENT un bloc "
             "d'échéance — ni trou, ni recouvrement",
             sum(t["octets"] for t in sc["tranches"].values())
             == sc["octets_par_echeance"]
             and [t["offset"] for t in sc["tranches"].values()] == [0, 5 * 7 * 25 * 2])
    verifier("…idem pour un enregistrement de `colonnes.bin`",
             sum(t["octets"] for t in sk["tranches"].values())
             == sk["octets_par_colonne"])
    verifier("⚠️ le pas d'enregistrement de `colonnes.bin` est multiple "
             "de 4, sur un domaine 5 × 7 qui a déjà démenti un alignement "
             "« par arithmétique heureuse » le 12/08",
             sk["octets_par_colonne"] % 4 == 0,
             f"{sk['octets_par_colonne']} o")
    verifier("⛔ le manifeste DIT que les offsets de `carte.bin` sont "
             "RELATIFS au bloc d'échéance — un client qui les lirait "
             "absolus décoderait `v` à la place de `u`",
             "RELATIFS" in sc["note"])
    verifier("les deux jumeaux pèsent ce que l'arbitrage A10 a chiffré "
             "(58,3 Mo sur nord-alpes réel : 2 × 29,14)",
             raf.octets_publies() == len(carte) + len(colonnes))
    ko = len(json.dumps(man, ensure_ascii=False).encode()) / 1024
    verifier("⚠️ le manifeste tient sous 30 Ko — au-delà, c'est que "
             "quelqu'un y a mis de la donnée",
             ko < 30.0, f"{ko:.1f} Ko")


def section_8_resolution():
    print("\n── 8. ⛔⛔ `resolutionTemporelleMin` SURVIT au passage ──")
    _stock, raf = fabriquer()
    man = raf.manifeste()
    par_niveau = {n["niveauMSol"]: n for n in man["niveaux"]}
    verifier("la table par NIVEAU est publiée, pour les 25 niveaux",
             set(par_niveau) == set(RA.NIVEAUX))
    verifier("⛔ sous 500 m/sol : 15 min et erreur d'interpolation NULLE "
             "— c'est OBSERVÉ",
             par_niveau[20]["resolutionTemporelleMin"] == 15
             and par_niveau[500]["erreurInterpolationMs"] == 0.0)
    verifier("⛔ au-dessus de 1 000 m/sol : 60 min, et l'erreur est DITE "
             "— le composite y sert 25 échéances qu'il n'a pas observées",
             par_niveau[1000]["resolutionTemporelleMin"] == 60
             and par_niveau[3000]["erreurInterpolationMs"] > 0.0,
             f"3000 m → {par_niveau[3000]['erreurInterpolationMs']} m/s")
    verifier("⚠️ …et la table est RENVOYÉE à sa condition de validité "
             "(`poids_pi = 1`), sans quoi elle affirmerait « observée » "
             "à 6 h d'échéance où plus rien ne l'est",
             "poids_pi = 1" in man["niveaux_valables_si"])
    verifier("les conventions et les deux mesures qui légitiment le "
             "composite survivent aussi (Δ vaut 2,5 fois le bruit)",
             man["mesures"]["rapport"].startswith("Δ vaut")
             and "extinction" in man["conventions"])
    plat = json.dumps(man, ensure_ascii=False)
    verifier("⛔ AUCUN âge publié — il périme à la lecture, il se calcule "
             "depuis `run_pi` et `run_produit_b`",
             not any(c in plat for c in
                     ('"age', '"ageMin', '"age_min', '"il_y_a', '"anciennete')))
    verifier("⛔ la préséance est publiée : `u`/`v` du bloc `hauteur` et "
             "RIEN d'autre, et le repli sur le produit B est écrit",
             "hauteur" in man["preseance"] and "SEUL MAÎTRE" in man["preseance"]
             and "NON FINIE" in man["preseance"])


def section_9_ecriture():
    print("\n── 9. L'écriture : trois objets, un index, une rétention ──")
    stock, raf = fabriquer()
    RA.ecrire(stock, raf, journal=lambda *_: None)
    cles = cles_du_rafraichissement(RUN_PI, DOMAINE)
    verifier("les trois objets sont écrits", all(c in stock.objets for c in cles))
    ecrits = [c for c in stock.ordre_ecriture if c in cles]
    verifier("⛔ le manifeste EN DERNIER des trois : il ne doit jamais "
             "décrire des octets absents",
             ecrits[-1].endswith("manifest.json"))
    verifier("⛔ les trois en `CACHE_REECRIT` : la clé porte le run PI, "
             "mais les octets dépendent AUSSI du run du produit B "
             "consommé — « les mêmes octets » n'est pas vrai ici",
             all(stock.entetes[c][0] == "no-cache, must-revalidate"
                 for c in cles))
    idx = stock.get_json(CLE_INDEX_RAFRAICHISSEMENT)
    verifier("`dernier[domaine]` désigne le run LISIBLE",
             idx["dernier"][DOMAINE] == RUN_PI)
    verifier("l'index est servi en `no-store`, comme ses deux frères — "
             "un index en cache ferait lire un run purgé",
             stock.entetes[CLE_INDEX_RAFRAICHISSEMENT][0] == "no-store")
    verifier("les trois clés sont dans l'index : un objet hors index est "
             "invisible, donc définitivement payé",
             set(idx["runs"][0]["cles"]) == set(cles))

    # ── La rétention, PAR DOMAINE et sur quatre runs ──────────────────
    for h in (11, 12, 13):
        r = RA.Rafraichissement(f"2026-08-17T{h}:00:00Z", DOMAINE, RUN_B,
                                raf.steps_b, raf.decalage_min,
                                raf.composite.astype(np.float64),
                                raf.diagnostic, LATS, LONS)
        RA.ecrire(stock, r, journal=lambda *_: None)
    idx = stock.get_json(CLE_INDEX_RAFRAICHISSEMENT)
    verifier("après quatre runs, trois restent en ligne (rétention 3)",
             len(idx["runs"]) == 3, str([e["run"] for e in idx["runs"]]))
    verifier("…et le plus ancien a été SUPPRIMÉ, ses trois clés avec",
             all(c in stock.supprimes for c in cles))
    verifier("⛔ la purge n'est jamais sortie du préfixe du "
             "rafraîchissement — les colonnes PI, DÉFINITIVES, vivent "
             "sous un préfixe voisin d'une lettre près",
             all(c.startswith(RA.PREFIXE_RAFRAICHISSEMENT)
                 for c in stock.supprimes))
    verifier("`restes` est vidé après une purge réussie — un compteur qui "
             "ne redescend jamais n'est pas un compteur",
             idx["restes"] == [])


def section_10_ensemble_ou_pas():
    print("\n── 10. ⛔⛔ Les jumeaux ensemble, ou pas du tout ──")
    stock, raf = fabriquer()
    c_carte, c_colonnes, c_man = cles_du_rafraichissement(RUN_PI, DOMAINE)
    stock.panne.add(c_colonnes)
    try:
        RA.ecrire(stock, raf, journal=lambda *_: None)
        leve_ok = False
    except Exception:                                        # noqa: BLE001
        leve_ok = True
    verifier("une panne sur le second jumeau fait ÉCHOUER l'écriture "
             "entière — elle ne se rattrape pas ici", leve_ok)
    idx = stock.get_json(CLE_INDEX_RAFRAICHISSEMENT) or {}
    verifier("⛔ `dernier` N'A PAS bougé : personne ne lira un couple "
             "dépareillé, où le calque et la coupe diraient deux vents",
             not (idx.get("dernier") or {}).get(DOMAINE))
    verifier("⚠️ …mais l'objet DÉJÀ ÉCRIT entre quand même dans l'index, "
             "pour être purgé : `ListObjects` n'est pas une route de ce "
             "projet, donc un objet hors index est une FUITE",
             any(c_carte in (e.get("cles") or [])
                 for e in (idx.get("runs") or [])))
    verifier("…et le manifeste n'a PAS été écrit : rien n'est lisible",
             c_man not in stock.objets)


def section_12_jeton_de_cache():
    """⛔ `ecrit_le` — le trou du §7 de L3a, et il ne se voit qu'au REJEU.

    Le client prenait le RUN PI comme jeton de cache. Ça couvre le cas
    normal — une clé neuve chaque heure — mais pas le rejeu sous le MÊME
    run PI après la publication d'un nouveau run AROME : mêmes clés,
    autres octets, et **la même longueur**. Ni 416, ni tampon court, rien
    à quoi se raccrocher. Le seul filet restant était
    `run_produit_b === run affiché`, qui n'attrape le rejeu que s'il
    change de run AROME — c'est-à-dire pas le cas qui nous occupe.
    """
    print("\n── 12. ⛔ Le jeton de cache : `ecrit_le`, et le REJEU ──")
    import re                                            # noqa: PLC0415

    stock, raf = fabriquer()
    RA.ecrire(stock, raf, journal=lambda *_: None)
    idx = stock.get_json(CLE_INDEX_RAFRAICHISSEMENT)
    verifier("⛔ l'index publie `ecrit_le` — sans lui, un rejeu sous le "
             "même run PI resert des octets périmés sous une clé "
             "inchangée, de MÊME LONGUEUR",
             bool(idx.get("ecrit_le")), str(idx.get("ecrit_le")))
    verifier("…au format des deux index frères (`…Z`, seconde entière) — "
             "il part en query, un format exotique casserait l'URL",
             bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z",
                               str(idx.get("ecrit_le") or ""))))

    # ── ⛔⛔ LE CONTRÔLE QUI PROUVE LE BRANCHEMENT, pas le champ ───────
    # Leçon du Lot L2, payée le matin même : quatre contrôles au vert
    # avec le garde-fou DÉBRANCHÉ. Ici la question n'est pas « le champ
    # existe-t-il ? » mais « CHANGE-T-il quand les octets changent ? ».
    # On rejoue donc le MÊME run PI, sur le MÊME domaine.
    avant = idx["ecrit_le"]
    RA.ecrire(stock, raf, journal=lambda *_: None,
              maintenant="2026-08-17T11:07:00Z")
    idx2 = stock.get_json(CLE_INDEX_RAFRAICHISSEMENT)
    verifier("⛔⛔ un REJEU sous le MÊME run PI change `ecrit_le` — c'est "
             "TOUT l'objet du champ, et c'est ce que le run PI seul ne "
             "savait pas dire",
             idx2.get("ecrit_le") == "2026-08-17T11:07:00Z" != avant,
             f"{avant} → {idx2.get('ecrit_le')}")
    verifier("…alors que les CLÉS, elles, n'ont pas bougé d'un caractère "
             "— c'est bien le même objet, et c'est le problème",
             set(idx2["runs"][0]["cles"])
             == set(cles_du_rafraichissement(RUN_PI, DOMAINE)))
    verifier("…et `dernier` désigne toujours ce run : un rejeu ne "
             "dépareille rien", idx2["dernier"][DOMAINE] == RUN_PI)

    # ── ⚠️ UN SEUL HORODATAGE POUR LES DEUX ÉCRITURES ────────────────
    # L'index est republié après la purge quand des suppressions ont
    # échoué. Deux horodatages différents changeraient le jeton une
    # seconde fois, donc feraient retélécharger 58,3 Mo pour des octets
    # identiques. Un jeton n'a pas à être frais, il a à être JUSTE.
    stock2, raf2 = fabriquer()
    corps = []
    vrai_put = stock2.put

    def put_espion(cle, corps_, **kw):
        if cle == CLE_INDEX_RAFRAICHISSEMENT:
            corps.append(json.loads(bytes(corps_)))
        return vrai_put(cle, corps_, **kw)

    stock2.put = put_espion
    # ⛔ `Storage.delete` NE LÈVE PAS, il rend False (tools/storage.py).
    # C'est LA forme d'échec réelle, et c'est celle que le code d'avant
    # L3b n'attrapait pas : il n'écoutait que les exceptions.
    stock2.delete = lambda _cle: False
    # ⚠️ UN HORODATAGE DIFFÉRENT PAR RUN, sinon ce contrôle passe au vert
    # par HASARD : sans injection, les quatre écritures tombent dans la
    # même seconde et « les deux derniers sont égaux » est vrai quoi qu'il
    # arrive. C'est exactement le faux positif qui apprend à ignorer un
    # banc — celui-ci l'a fait à sa première écriture.
    RA.ecrire(stock2, raf2, journal=lambda *_: None,
              maintenant="2026-08-17T10:01:00Z")
    for h in (11, 12, 13):                    # quatre runs ⇒ une purge
        r = RA.Rafraichissement(f"2026-08-17T{h}:00:00Z", DOMAINE, RUN_B,
                                raf2.steps_b, raf2.decalage_min,
                                raf2.composite.astype(np.float64),
                                raf2.diagnostic, LATS, LONS)
        RA.ecrire(stock2, r, journal=lambda *_: None,
                  maintenant=f"2026-08-17T{h}:01:00Z")
    verifier("⛔⛔ une suppression qui rend False (et ne LÈVE pas) est "
             "comptée comme un échec — sinon `restes` reste vide, la clé "
             "n'est jamais réessayée, et elle sort de l'index à la "
             "rotation : un objet EN LIGNE et HORS INDEX",
             len(corps) >= 2 and bool(corps[-1].get("restes")),
             f"{len(corps)} écriture(s) d'index, "
             f"{len(corps[-1].get('restes') or [])} reste(s)")
    verifier("⚠️ …et les DEUX écritures d'un MÊME passage portent le même "
             "`ecrit_le` : un jeton qui bouge deux fois ferait "
             "retélécharger 58,3 Mo pour des octets identiques",
             corps[-1].get("ecrit_le") == corps[-2].get("ecrit_le")
             == "2026-08-17T13:01:00Z",
             f"{corps[-2].get('ecrit_le')} / {corps[-1].get('ecrit_le')}")
    verifier("…et le passage PRÉCÉDENT portait bien un autre horodatage — "
             "sans quoi le contrôle ci-dessus serait vrai par hasard",
             corps[-3].get("ecrit_le") != corps[-1].get("ecrit_le"),
             f"{corps[-3].get('ecrit_le')}")


def section_11_sait_echouer():
    print("\n── 11. ⛔ LE CONTRÔLE QUI SAIT ÉCHOUER ──")
    # La version NAÏVE : le composite publié tel quel, avec le manifeste
    # qu'on écrirait « naturellement » — les axes, les échéances, les
    # octets. C'est-à-dire tout sauf ce qui dit À QUI la valeur est due.
    _stock, raf = fabriquer()
    man = raf.manifeste()
    naif = {k: v for k, v in man.items()
            if k not in ("provenance", "niveaux", "niveaux_valables_si",
                         "poids_pi", "preseance", "mesures", "conventions")}
    plat = json.dumps(naif, ensure_ascii=False)
    verifier("⛔ SANS ces champs, rien dans le manifeste ne distingue une "
             "échéance CORRIGÉE par PI d'une échéance qui ne l'est pas — "
             "et les deux sont servies sous la même clé, dans le même "
             "objet, à 15 minutes d'intervalle",
             "poids_pi" not in plat and "resolutionTemporelle" not in plat)
    verifier("…ALORS QUE les valeurs, elles, DIFFÈRENT bel et bien : "
             "l'objet naïf affirmerait donc quelque chose de faux sans "
             "qu'aucune requête n'échoue",
             float(np.nanmax(np.abs(
                 raf.composite[0, list(RA.NIVEAUX).index(20), 0]
                 .astype(np.float32)
                 - raf.composite[0, list(RA.NIVEAUX).index(20), -1]
                 .astype(np.float32)))) > 0.5)
    verifier("AVEC les champs, la différence est explicite : la première "
             "échéance dit `arome+pi`, la dernière dit `arome`",
             man["provenance"]["par_echeance"][0]["blocs"]["hauteur"]["modele"]
             != man["provenance"]["par_echeance"][-1]["blocs"]["hauteur"]["modele"])


def main():
    print("═" * 70)
    print("  BANC — rafraîchissement PI (Lot L2, 17/08/2026)")
    print("═" * 70)
    # ⚠️ CHAQUE SECTION EST ISOLÉE, et ce n'est pas de la politesse.
    # Rejoué contre du code saboté, ce banc rendait bien 1 — mais en
    # MOURANT à la première section touchée, donc sans jamais imprimer
    # la liste des contrôles au rouge. Un banc qui échoue sans dire
    # LEQUEL de ses contrôles a cédé fait perdre le temps qu'il devait
    # faire gagner. Une exception devient donc un rouge NOMMÉ, et les
    # sections suivantes tournent quand même.
    for section in (section_1_appariement, section_2_axes, section_3_sans_pi,
                    section_4_invariant, section_5_horizon,
                    section_6_jumeaux, section_7_octets,
                    section_8_resolution, section_9_ecriture,
                    section_10_ensemble_ou_pas, section_12_jeton_de_cache,
                    section_11_sait_echouer):
        try:
            section()
        except Exception as e:                               # noqa: BLE001
            verifier(f"⛔ {section.__name__} a LEVÉ au lieu de conclure",
                     False, f"{type(e).__name__}: {str(e)[:160]}")
    print("\n" + "═" * 70)
    if echecs:
        print(f"⛔ {len(echecs)} CONTRÔLE(S) AU ROUGE :")
        for e in echecs:
            print(f"   · {e}")
        return 1
    print("✅ tous les contrôles passent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
