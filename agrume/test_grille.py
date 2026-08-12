#!/usr/bin/env python3
"""
test_grille.py — banc du produit B, HORS-LIGNE.

    python3 agrume/test_grille.py

⚠️ CE QUE CE BANC PROTÈGE.

Le produit B ne s'archive pas : il ne survit pas à trois runs. Une
erreur ne s'y grave donc pas pour toujours — mais elle s'y voit encore
moins, parce qu'il n'y a rien d'ancien à quoi la comparer. Cinq façons
de casser en SILENCE, une par section :

  1. **Une carte retournée.** `lats` DÉCROÎT (le premier point est au
     nord). Un consommateur qui suppose l'inverse obtient une carte
     miroir — et sur un domaine presque carré, les Alpes retournées
     ressemblent toujours à des Alpes. Rien ne se voit.
  2. **Un reshape transposé.** eccodes rend un champ PLAT. `(Nj, Ni)`
     et `(Ni, Nj)` donnent tous deux un tableau de la bonne TAILLE ; un
     seul a le bon contenu.
  3. **La maille fine happée par la grille 0,025°.** Les niveaux 10, 20,
     50 et 100 m de la maille fine portent les mêmes noms `u`/`v` ET
     appartiennent aux 25 niveaux du 0,025°. `accepte()` dit donc OUI —
     et c'est correct de sa part. C'est à l'ingestion de vérifier la
     MAILLE, et ce banc verrouille cette responsabilité.
  4. **Une purge qui déborde.** Le produit A, DÉFINITIF, vit dans le même
     bucket sous `agrume/colonnes/`. Une clé mal filtrée y détruirait une
     archive irremplaçable.
  5. **Un manifeste qui ment.** Il annonce des axes et un nombre
     d'échéances ; s'ils ne décrivent pas le tableau livré, tout
     consommateur se trompe en croyant lire le contrat.

Aucun réseau, aucun GRIB, aucune clé.
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

import grille as GR  # noqa: E402
from colonnes import erreur_quantification, quantifier  # noqa: E402
from domaine import NIVEAUX_H_0025  # noqa: E402
from orographie import Orographie  # noqa: E402

echecs = []


def verifier(nom, condition, detail=""):
    print(f"  {'✓' if condition else '✗'} {nom}"
          + (f"   {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


META = dict(Ni=1121, Nj=717, lat0=55.4, lon0=-12.0, di=0.025, dj=0.025,
            jScan=0)
J0, I0, NJ, NI = 364, 700, 61, 85


def orog_bidon(meta=META, j0=J0, i0=I0, nj=NJ, ni=NI):
    """Une orographie synthétique dont la valeur ENCODE sa position :
    z = j * 1000 + i. Toute erreur d'indexation devient donc lisible dans
    la valeur elle-même, au lieu de produire un nombre plausible."""
    z = (np.arange(nj)[:, None] * 1000.0 + np.arange(ni)[None, :])
    return Orographie("0025", z, meta, j0, i0)


def champ_plat(meta=META, j0=J0, i0=I0):
    """Un champ France entière, plat, dont la valeur encode (j, i) de la
    grille NATIVE — même principe."""
    j = np.arange(meta["Nj"])[:, None] * 10000.0
    i = np.arange(meta["Ni"])[None, :] * 1.0
    return (j + i).ravel()


def main():
    print("\n── 1. Les axes, et le sens qui ne se voit pas ──")
    o = orog_bidon()
    lats, lons = GR.axes_depuis_orographie(o)
    verifier("la fenêtre fait bien 61 × 85 points (§4.1, mesuré le 10/08)",
             (len(lats), len(lons)) == (61, 85), f"{len(lats)}×{len(lons)}")
    verifier("⚠️ lats DÉCROÎT — le premier point est au NORD",
             bool(np.all(np.diff(lats) < 0)),
             f"{lats[0]:.3f} → {lats[-1]:.3f}")
    verifier("lons croît — le premier point est à l'OUEST",
             bool(np.all(np.diff(lons) > 0)),
             f"{lons[0]:.3f} → {lons[-1]:.3f}")
    verifier("les coins tombent sur le domaine Nord-Alpes",
             abs(lats[0] - 46.3) < 1e-4 and abs(lats[-1] - 44.8) < 1e-4
             and abs(lons[0] - 5.5) < 1e-4 and abs(lons[-1] - 7.6) < 1e-4)

    # Une grille qui balaie du sud vers le nord doit donner des latitudes
    # CROISSANTES : si le code ignorait `jScan`, ce cas passerait quand
    # même et la convention deviendrait une supposition.
    # `lat0` est choisi pour que la fenêtre couvre EXACTEMENT le même
    # domaine en balayage sud→nord : 44,8 = lat0 + 364 × 0,025.
    meta_sud = dict(META, jScan=1, lat0=44.8 - J0 * META["dj"])
    lats_sud, _ = GR.axes_depuis_orographie(orog_bidon(meta_sud))
    verifier("jScansPositively = 1 → latitudes CROISSANTES "
             "(le sens est LU, pas supposé)",
             bool(np.all(np.diff(lats_sud) > 0)))
    verifier("… et le même domaine est couvert dans les deux sens",
             abs(float(lats_sud.min()) - float(lats.min())) < 1e-4
             and abs(float(lats_sud.max()) - float(lats.max())) < 1e-4)

    # ⚠️ Ce cas est celui qui a démasqué un garde-fou creux le 10/08 : la
    # comparaison des axes à `orog.coords()` ne peut RIEN voir ici, parce
    # que les deux partent des mêmes (meta, j0, i0). Seule une référence
    # extérieure — le domaine déclaré — le détecte.
    faux = orog_bidon()
    faux.j0 += 1                       # un seul point de grille d'écart
    try:
        GR.axes_depuis_orographie(faux)
        decale = False
    except ValueError:
        decale = True
    verifier("⚠️ un décalage d'UN point de grille est refusé "
             "(2,8 km, invisible à l'œil sur une carte)", decale)
    faux_i = orog_bidon()
    faux_i.i0 -= 1
    try:
        GR.axes_depuis_orographie(faux_i)
        decale_i = False
    except ValueError:
        decale_i = True
    verifier("… en longitude aussi", decale_i)

    print("\n── 2. Le découpage : (Nj, Ni) et pas l'inverse ──")
    plat = champ_plat()
    fen = GR.decouper(plat, META, o)
    verifier("la fenêtre découpée a la forme de l'orographie",
             fen.shape == (NJ, NI), str(fen.shape))
    verifier("le coin nord-ouest vaut bien j0·10000 + i0 "
             "(la valeur ENCODE sa position)",
             fen[0, 0] == J0 * 10000.0 + I0, f"{fen[0, 0]:.0f}")
    verifier("le coin sud-est aussi",
             fen[NJ - 1, NI - 1] == (J0 + NJ - 1) * 10000.0 + (I0 + NI - 1))
    verifier("⚠️ un reshape transposé donnerait une AUTRE valeur au même "
             "coin — la taille ne prouve rien",
             plat.reshape(META["Ni"], META["Nj"])[J0, I0] != fen[0, 0])
    try:
        GR.decouper(plat[:-1], META, o)
        taille_refusee = False
    except ValueError:
        taille_refusee = True
    verifier("un champ de la mauvaise taille est refusé, pas rogné",
             taille_refusee)

    print("\n── 3. Le conteneur, et le piège de la maille fine ──")
    g = GR.Grille("2026-08-10T09:00:00Z", [0, 1, 2], lats, lons, o.z)
    verifier("disposition (paramètre, niveau, échéance, lat, lon)",
             g.h0025.shape == (5, 25, 3, 61, 85), str(g.h0025.shape))
    verifier("float16 sur les champs, float32 sur le sol",
             g.h0025.dtype == np.float16 and g.zsol.dtype == np.float32)
    verifier("tableau vide = NaN partout, jamais 0 "
             "(0 est un vent parfaitement crédible)",
             g.remplissage() == 0.0)

    g.poser("u", 3000, 2, np.full((NJ, NI), 7.5))
    k_u, k_3000, k_2 = (g.i_param["u"], g.i_niveau[3000], g.i_step[2])
    verifier("le niveau 3000 m se range bien en DERNIÈRE position "
             "(l'ordre de NIVEAUX_H_0025 est le contrat)",
             k_3000 == len(NIVEAUX_H_0025) - 1)
    verifier("un champ posé se relit à sa place, et nulle part ailleurs",
             float(g.h0025[k_u, k_3000, k_2, 0, 0]) == 7.5
             and np.isnan(float(g.h0025[k_u, k_3000 - 1, k_2, 0, 0])))

    verifier("⚠️⚠️ `accepte()` dit OUI à « u à 20 m » — parce que 20 m EST "
             "un niveau du 0,025°. C'est à l'ingestion de vérifier la "
             "MAILLE, sinon la maille fine (151×211) tomberait ici.",
             g.accepte("u", 20, 0) is True)
    verifier("un niveau qui n'existe pas en 0,025° est refusé",
             g.accepte("u", 35000, 0) is False)
    verifier("un paramètre hors du produit B est refusé (`zp`, isobares)",
             g.accepte("zp", 500, 0) is False)
    verifier("une échéance non ingérée est refusée",
             g.accepte("u", 500, 99) is False)

    print("\n── 4. La quantification, héritée du produit A ──")
    t_k = np.linspace(233.15, 313.15, 5000)         # −40 → +40 °C
    p_t = [p for p in GR.PARAMS_GRILLE if p["nom"] == "t"][0]
    err_c = erreur_quantification(t_k, p_t)
    err_k = erreur_quantification(t_k, dict(p_t, decalage=0.0))
    verifier("⚠️ la température est stockée en °C : le gain sur l'erreur "
             "de quantification est MESURÉ, pas supposé",
             err_k / max(err_c, 1e-12) > 4,
             f"kelvins {err_k:.4f} contre celsius {err_c:.4f} "
             f"(×{err_k / max(err_c, 1e-12):.1f})")
    verifier("le produit B ne redéfinit PAS ses paramètres — il reprend "
             "ceux du produit A (une liste, pas deux)",
             GR.PARAMS_GRILLE is not None
             and [p["nom"] for p in GR.PARAMS_GRILLE]
             == ["u", "v", "t", "r", "tke"])
    sentinelle = quantifier(np.array([9999.0, 3.0]), p_t)
    verifier("la sentinelle 9999 d'eccodes devient NaN, pas une valeur",
             bool(np.isnan(float(sentinelle[0]))))

    print("\n── 5. L'index et la purge, sans jamais lister ──")
    # ⚠️ 12/08 : les clés portent le DOMAINE et la rétention se compte
    # PAR domaine. `STEPS` est court exprès — ce qui est testé ici est
    # l'index, pas la taille des tampons.
    STEPS = [0, 1, 2]
    D = "nord-alpes"

    def cles(r, d=D):
        return GR.cles_du_run(r, d, STEPS)

    index = dict(GR.INDEX_VIDE)
    runs = ["2026-08-10T00:00:00Z", "2026-08-10T03:00:00Z",
            "2026-08-10T06:00:00Z", "2026-08-10T09:00:00Z"]
    supprimes = []
    for r in runs:
        index, a_sup = GR.index_apres(index, r, D, cles(r))
        supprimes += a_sup
        index = GR.index_apres_purge(index, [])
    verifier("après 4 runs, il en reste exactement 3 en ligne",
             len(index["runs"]) == 3, str(len(index["runs"])))
    verifier("le plus récent est en tête (tri antichronologique)",
             index["runs"][0]["run"] == runs[-1])
    verifier("c'est bien le PLUS ANCIEN qui a été purgé, et lui seul",
             supprimes == cles(runs[0]), str(supprimes))
    verifier("un run découpé par échéance publie 1 clé par échéance, "
             "plus le manifeste", len(cles(runs[0])) == len(STEPS) + 1)
    verifier("`restes` est vide quand tout s'est bien supprimé",
             index["restes"] == [])

    # Un run rejoué : il ne doit ni se dupliquer, ni se purger lui-même.
    rejoue, a_sup = GR.index_apres(index, runs[-1], D, cles(runs[-1]))
    verifier("⚠️ rejouer le même run ne le duplique pas dans l'index",
             len(rejoue["runs"]) == 3
             and len({e["run"] for e in rejoue["runs"]}) == 3)
    verifier("⚠️ et ne demande PAS de supprimer ses propres clés",
             not any(c in cles(runs[-1]) for c in a_sup), str(a_sup))

    # Un échec de suppression doit survivre au run suivant.
    idx2 = GR.index_apres_purge(index, ["agrume/grille/vieux/grille.npz"])
    idx3, a_sup3 = GR.index_apres(idx2, "2026-08-10T12:00:00Z", D,
                                  cles("2026-08-10T12:00:00Z"))
    verifier("⚠️ une suppression échouée est REPRISE au run suivant "
             "(sans ListObjects, rien d'autre ne saurait qu'elle existe)",
             "agrume/grille/vieux/grille.npz" in a_sup3)
    verifier("et elle n'est comptée qu'une fois",
             a_sup3.count("agrume/grille/vieux/grille.npz") == 1)

    print("\n── 5 bis. DEUX DOMAINES : les compteurs ne se mélangent pas ──")
    # ⛔ Le défaut que cette section attrape : avec une rétention
    # GLOBALE, écrire deux domaines par run purgerait chaque domaine au
    # bout d'un run et demi — et un domaine dont l'ingestion échoue
    # disparaîtrait entièrement pendant que l'autre garde ses trois runs.
    idx = dict(GR.INDEX_VIDE)
    for r in runs:
        for d in ("nord-alpes", "pyrenees"):
            idx, _ = GR.index_apres(idx, r, d, cles(r, d))
            idx = GR.index_apres_purge(idx, [])
    verifier("deux domaines × 3 runs = 6 entrées, pas 3",
             len(idx["runs"]) == 6, str(len(idx["runs"])))
    for d in ("nord-alpes", "pyrenees"):
        verifier(f"  et chacun garde bien ses 3 runs ({d})",
                 sum(1 for e in idx["runs"] if e["domaine"] == d) == 3)

    # Un domaine qui n'avance plus ne doit pas être vidé par l'autre.
    idx4 = dict(idx)
    for r in ("2026-08-10T12:00:00Z", "2026-08-10T15:00:00Z",
              "2026-08-10T18:00:00Z", "2026-08-10T21:00:00Z"):
        idx4, _ = GR.index_apres(idx4, r, "nord-alpes", cles(r))
        idx4 = GR.index_apres_purge(idx4, [])
    verifier("⚠️ 4 runs alpins de plus n'effacent PAS les Pyrénées "
             "(ingestion pyrénéenne en panne)",
             sum(1 for e in idx4["runs"] if e["domaine"] == "pyrenees") == 3)

    print("\n── 5 ter. Les clés de l'ANCIEN format ne fuient pas ──")
    # ⛔ Sans `ListObjects`, un objet qui sort de l'index sans être
    # supprimé devient INVISIBLE et définitivement perdu. Les entrées
    # d'avant le 12/08 n'ont pas de `domaine` : elles doivent partir à la
    # suppression, pas à l'oubli.
    legacy = dict(GR.INDEX_VIDE, runs=[
        dict(run="2026-08-12T06:00:00Z",
             cles=["agrume/grille/2026-08-12T06:00:00Z/grille.npz",
                   "agrume/grille/2026-08-12T06:00:00Z/manifest.json"]),
        dict(run="2026-08-12T09:00:00Z",
             cles=["agrume/grille/2026-08-12T09:00:00Z/grille.npz",
                   "agrume/grille/2026-08-12T09:00:00Z/manifest.json"])])
    apres, a_sup = GR.index_apres(legacy, "2026-08-12T12:00:00Z", D,
                                  cles("2026-08-12T12:00:00Z"))
    verifier("⛔ les 4 clés de l'ancien format partent à la SUPPRESSION, "
             "pas à l'oubli",
             all(c in a_sup for e in legacy["runs"] for c in e["cles"]),
             f"{len(a_sup)} clé(s) à supprimer")
    verifier("et l'index n'en garde aucune trace muette",
             all(e.get("domaine") for e in apres["runs"]))
    verifier("le garde-fou de préfixe les accepte quand même (même "
             "produit, ancien chemin)", GR.verifier_prefixe(a_sup) is True)

    verifier("le garde-fou accepte les clés du produit B",
             GR.verifier_prefixe(cles(runs[0])) is True)
    try:
        GR.verifier_prefixe(["agrume/colonnes/2026-08-10T00:00:00Z/colonnes.npz"])
        deborde = True
    except ValueError:
        deborde = False
    verifier("⛔ et REFUSE une clé du produit A — archive DÉFINITIVE, "
             "même bucket", not deborde)
    try:
        GR.verifier_prefixe(cles(runs[0]) + ["autre/chose.npz"])
        partiel = True
    except ValueError:
        partiel = False
    verifier("une seule intruse arrête la purge ENTIÈRE — on ne supprime "
             "pas « ce qui est légitime » en attendant", not partiel)

    print("\n── 6. Le manifeste ne ment pas ──")
    m = g.manifeste()
    verifier("il annonce le bon nombre d'échéances",
             len(m["echeances"]) == g.h0025.shape[2])
    verifier("il annonce le bon nombre de niveaux",
             len(m["niveaux_m_sol"]) == g.h0025.shape[1])
    verifier("il annonce le bon nombre de paramètres, dans l'ordre",
             [p["nom"] for p in m["parametres"]]
             == list(g.i_param.keys()) == ["u", "v", "t", "r", "tke"])
    verifier("il annonce les axes, et leurs bornes correspondent",
             m["axes"]["nb_lat"] == g.h0025.shape[3]
             and abs(m["axes"]["lat_premier"] - float(lats[0])) < 1e-3)
    verifier("⚠️ il écrit le SENS des latitudes en toutes lettres",
             "DÉCROISSANTES" in m["axes"]["sens"])
    verifier("il dit que le produit est jetable et donne la rétention",
             m["retention_runs"] == GR.RETENTION_RUNS
             and "JETABLE" in m["avertissement"])
    verifier("il dit que la TKE manque à l'échéance 0 (mesuré, pas un bug)",
             "TKE" in m["avertissement"])
    verifier("il donne la règle de conversion vers l'altitude-mer",
             "zsol" in m["reference_verticale"])

    print("\n  grille :", "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
