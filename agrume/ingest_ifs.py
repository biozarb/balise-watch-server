#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/ingest_ifs.py — LA RALLONGE IFS DU PRODUIT B (51 → 72 h)
#                                         (Lot L22b, 07/09/2026)
#
#  `ifs.py` porte le format et les conversions ; ce fichier-ci fait le
#  travail : il choisit le run IFS, tire les sept pas, remplit les
#  échéances neuves de chaque grille de domaine, et rend les grilles
#  ÉTENDUES. Il n'écrit rien sur R2 — c'est `ingest_colonnes.publier_
#  grilles()` qui publie, une seule fois, comme avant ce lot.
#
#  ═══ POURQUOI DANS LA MÊME PASSE, ET PAS EN ÉTAPE D'ACTION SÉPARÉE ═══
#
#  Le cadrage du 04/09 disait « une étape "rallonge IFS" après la
#  rallonge AROME ». Une étape séparée est un AUTRE PROCESSUS, donc elle
#  ne voit pas les grilles en mémoire : il lui faudrait RELIRE le run
#  qu'on vient de publier — 52 tampons × 3 domaines, **~1,1 Go** tirés
#  de R2 (Class B) — pour y ajouter sept échéances, puis republier
#  `colonnes.bin` et les manifestes une seconde fois.
#
#  ⛔ Et ce n'est pas qu'une question de coût : republier deux fois le
#  même run sous les mêmes clés est exactement ce qui a produit le
#  HTTP 416 du 13/08 au soir (manifeste d'une génération, octets d'une
#  autre). Le projet a déjà payé ce défaut ; on ne s'en redonne pas
#  l'occasion pour économiser une ligne de workflow.
#
#  Ici, les grilles sont déjà en mémoire, remplies d'AROME. On les
#  ÉTEND (`Grille.etendre`), on remplit les sept échéances neuves, et la
#  publication qui suit voit un run complet 0 → 72 h. Une passe, une
#  publication, un manifeste.
#
#  ⛔ ET ELLE NE PART QUE SI LA RALLONGE AROME EST COMPLÈTE. Coudre du
#  54-72 h sur une grille qui s'arrête à 24 h laisserait un trou de
#  TRENTE heures au milieu de la coupe — pire qu'une coupe courte, parce
#  qu'un trou au milieu se lit comme une panne alors qu'une coupe courte
#  se lit comme un horizon. `ingest_colonnes` ne l'appelle donc qu'après
#  une rallonge AROME réussie, et `--sans-ifs` la coupe.
#
#  ⚠️ CE QUE ÇA COÛTE, MESURÉ LE 06/09 (VM du Mac, pas un runner) :
#  29,3 Mo par pas × 7 pas = **205 Mo par run**, tirés à 11,6 Mo/s en
#  six plages parallèles, soit **~18 s de réseau**. Le régrillage et la
#  dérivation sont du numpy sur 11 655 colonnes : négligeables devant.
#  ⚠️ Le chiffre du RUNNER n'est pas mesuré — il le sera au premier
#  déclenchement, et c'est lui qui compte pour l'alerte à 30 min.
#
#      python3 agrume/ingest_ifs.py --run 2026-09-06T00:00:00Z --sonde
#      python3 agrume/ingest_ifs.py --run … --domaine nord-alpes --sans-ecriture
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import pathlib
import sys
import time
from datetime import datetime, timezone

_ICI = pathlib.Path(__file__).resolve().parent
for _p in (_ICI, _ICI.parent / "tools"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

import numpy as np                                          # noqa: E402

import ifs as I                                             # noqa: E402
from domaine import NIVEAUX_H_0025, NIVEAUX_P               # noqa: E402
from quantification import Abort                            # noqa: E402

#: ⛔ CE QUE CHAQUE BLOC REÇOIT, ET DE QUOI. La table est ici et pas dans
#: `ifs.py` : `ifs.py` convertit des champs, il ne sait pas ce qu'est un
#: produit B. Chaque entrée dit (nom dans le produit B, nom IFS sur les
#: niveaux isobares, ancre de surface pour la dérivation, décalage
#: d'unité).
#:
#: ⚠️ LE DÉCALAGE EST CELUI DE `quantification.PARAMS_*`, RECOPIÉ ICI —
#: et c'est la seule duplication de ce fichier. Elle est nommée parce
#: qu'elle est dangereuse : le produit B stocke la température en °C
#: (le float16 a un pas RELATIF, donc 0,25 K à 300 kelvins), et publier
#: des kelvins ferait des valeurs 273 fois trop grandes… qui se
#: quantifieraient sans erreur et s'afficheraient comme un été caniculaire
#: permanent. `test_ifs.py::test_unites` compare les deux tables.
CHAMPS_H = (
    # (produit B, IFS pl, ancre sfc, niveau de l'ancre, décalage)
    ("u", "u", "10u", 10, 0.0),
    ("v", "v", "10v", 10, 0.0),
    ("t", "t", "2t", 2, -273.15),
    ("r", "r", None, None, 0.0),
)
CHAMPS_ISO = (("u", "u", 0.0), ("v", "v", 0.0), ("t", "t", -273.15),
              ("r", "r", 0.0))

#: Les champs de surface qu'on sait remplir. ⚠️ Les neuf autres restent
#: `NaN` (`ifs.ABSENTS`) — une absence, jamais un zéro.
CHAMPS_SURF = (("pression_mer", "msl", 0.01),)


def _ancre(champs, court, niveau):
    """Le champ de surface qui ancre la colonne, ou `None`.

    ⚠️ La clé du décodeur est `(shortName, level)` et le niveau d'un
    champ de surface N'EST PAS TOUJOURS ZÉRO : `10u`/`10v` sortent au
    niveau 10, `2t` au niveau 2, `msl`/`sp` au niveau 0. Chercher `0`
    partout rendrait `None` sur trois champs sur cinq — et
    `deriver_hauteurs` sans ancre laisse le bas de colonne vide, ce qui
    ne lève rien.
    """
    if court is None:
        return None
    for niv in ((niveau,) if niveau is not None else ()) + (0,):
        if (court, niv) in champs:
            return champs[(court, niv)]
    raise Abort(f"champ de surface `{court}` absent du GRIB tiré — la "
                f"sélection et la table des ancres ont divergé")


def remplir(g, champs, step_agrume, regrilleur=None, poids=None,
            crier=print):
    """Remplit UNE échéance d'UNE grille depuis les champs IFS décodés.

    ⚠️ `regrilleur` et `poids` se passent plutôt que se recalculer : ils
    ne dépendent que des axes du domaine et des niveaux, donc ils sont
    les MÊMES pour les sept échéances. Les refaire à chaque appel, c'est
    21 fois (7 pas × 3 domaines) le même calcul d'indices.
    """
    R = regrilleur if regrilleur is not None else I.Regrilleur(g.lats, g.lons)
    zsol = np.asarray(g.zsol, dtype=np.float32)
    poids = poids if poids is not None else I.poids_log_p()

    # ── l'axe vertical : `gh` régrillé, natif puis interpolé ─────────
    gh = np.stack([R(champs[("gh", n)]) for n in I.NIVEAUX_COMMUNS])
    # ⛔ `ziso` EST L'ALTITUDE DES NIVEAUX ISOBARES, et elle sort de `gh`
    # SANS division : `gh` est déjà en mètres géopotentiels. Diviser par
    # g (le réflexe, parce que le produit A part d'un `z` en m²/s²)
    # donnerait des altitudes ~9,8 fois trop petites — et le raccord
    # hauteur/isobares se ferait à 700 m au lieu de 7 000.
    ziso = I.interpoler_log_p(gh, poids)
    for k in range(len(NIVEAUX_P)):
        g.ziso[k, g.i_step[step_agrume]] = ziso[k]

    # ── le bloc isobare ──────────────────────────────────────────────
    for nom_b, nom_ifs, dec in CHAMPS_ISO:
        pile = np.stack([R(champs[(nom_ifs, n)]) for n in I.NIVEAUX_COMMUNS])
        val = I.interpoler_log_p(pile, poids) + dec
        for k, niv in enumerate(NIVEAUX_P):
            g.poser_isobare(nom_b, niv, step_agrume, val[k])

    # ── le bloc hauteur, DÉRIVÉ ──────────────────────────────────────
    for nom_b, nom_ifs, court, niv_anc, dec in CHAMPS_H:
        pile = np.stack([R(champs[(nom_ifs, n)]) for n in I.NIVEAUX_COMMUNS])
        anc = _ancre(champs, court, niv_anc)
        h = I.deriver_hauteurs(pile, gh, zsol,
                               ancre=None if anc is None else R(anc))
        h = h + dec
        for k, niveau in enumerate(NIVEAUX_H_0025):
            g.poser(nom_b, niveau, step_agrume, h[k])

    # ── la surface, et la pression sol ───────────────────────────────
    # ⛔⛔ `R(...)` ET PAS LE CHAMP BRUT. Les champs de surface passent
    # par le MÊME régrillage que les autres — ils arrivent sur la grille
    # mondiale 721 × 1440, pas sur celle du domaine. La première version
    # les posait bruts : `ValueError: could not broadcast (721,1440) into
    # (111,105)`. ⚠️ Elle a levé, et c'est une chance : si la grille du
    # domaine avait eu la même forme qu'un sous-tableau du monde, numpy
    # aurait accepté et publié la Sibérie sous le nom des Alpes.
    for nom_b, court, fac in CHAMPS_SURF:
        g.poser_surface(nom_b, step_agrume, R(_ancre(champs, court, 0)) * fac)
    # ⛔ `psol` est en hPa (`PARAM_PRESSION_SOL.facteur = 0.01`) et en
    # float32 : c'est l'ancre basse de la pression dérivée, et le
    # float16 y coûterait 1 à 2 m d'altitude.
    g.psol[g.i_step[step_agrume]] = R(_ancre(champs, "sp", 0)) * 0.01


def appliquer(grilles, run_agrume, crier=print, maintenant=None,
              parallele=I.PARALLELE):
    """Étend et remplit les grilles de tous les domaines. Rend
    `(grilles_etendues, bilan)` — ou `(grilles, bilan)` inchangées si
    aucun run IFS n'est disponible. `grilles` est `{domaine: Grille}`,
    la forme que `ingest_colonnes.ingerer()` rend.

    ⛔ JAMAIS BLOQUANT, ET C'EST LA RÈGLE DE LA RALLONGE. La rallonge
    AROME du 13/08 est « au mieux » : celle-ci l'est aussi. Un run IFS
    absent, un 500 chez ECMWF, un champ manquant — la coupe s'arrête à
    51 h comme avant ce lot, le bilan le DIT, et le run se publie. Faire
    tomber l'ingestion pour une rallonge, ce serait perdre 0-51 h pour
    n'avoir pas eu 54-72.
    """
    bilan = {"run_ifs": None, "steps": [], "domaines": {}, "erreur": None,
             "octets": 0, "secondes": 0.0, "publie_le": None}
    t0 = time.monotonic()
    try:
        choix = I.run_disponible(run_agrume, maintenant, crier=crier)
        if choix is None:
            bilan["erreur"] = "aucun run IFS publié ne couvre la fenêtre"
            crier(f"▶ rallonge IFS : {bilan['erreur']} — la coupe s'arrête "
                  f"à {I.DEBUT_H - I.PAS_IFS_H} h, comme avant ce lot")
            return grilles, bilan
        run_ifs, steps_ifs, lm = choix
        bilan.update(run_ifs=f"{run_ifs:%Y-%m-%dT%H:%M:%SZ}", publie_le=lm)
        steps_agrume = I.heures_agrume(steps_ifs, run_agrume, run_ifs)
        bilan["steps"] = steps_agrume
        crier(f"▶ rallonge IFS : run {run_ifs:%Y-%m-%dT%HZ} (publié {lm}), "
              f"pas {steps_ifs} → échéances AGRUME {steps_agrume}")

        # ⛔ ON ÉTEND AVANT DE TIRER. Si le tirage échoue au troisième
        # pas, on rend les grilles étendues avec des échéances NaN — que
        # `publier_grilles` refuserait de publier ? NON : il les
        # publierait. C'est pourquoi on ne remplace les grilles de
        # l'appelant qu'à la toute fin, en une fois.
        # ⛔ DOMAINE PAR DOMAINE, EN LÂCHANT L'ANCIENNE AU FUR ET À
        # MESURE. `etendre` alloue une grille neuve : les trois domaines
        # d'un run complet pèsent ~556 Mo, et les étendre d'un bloc en
        # tiendrait ~1,19 Go en même temps. En vidant `grilles` au
        # passage, le pic retombe à ~556 + la plus grosse des neuves
        # (~320 Mo sur nord-alpes). ⚠️ `grilles` est CONSOMMÉ : l'appelant
        # reçoit le dictionnaire rendu, il ne réutilise pas le sien.
        etendues = {}
        for nom in sorted(grilles):
            etendues[nom] = grilles[nom].etendre(steps_agrume, crier=crier)
            grilles[nom] = None
        # ⚠️ Un régrilleur par domaine, calculé une fois : ses poids ne
        # dépendent que des axes, et il servira 7 fois.
        regrilleurs = {nom: I.Regrilleur(g.lats, g.lons)
                       for nom, g in etendues.items()}
        poids = I.poids_log_p()

        for st_ifs, st_ag in zip(steps_ifs, steps_agrume):
            url = I.url_pas(run_ifs, st_ifs)
            sel = I.selection(I.lire_index(url))
            plages = I.plages(sel)
            octets = I.tirer(url, plages, parallele=parallele)
            bilan["octets"] += len(octets)
            champs = I.decoder(octets)
            for nom in etendues:
                remplir(etendues[nom], champs, st_ag,
                        regrilleur=regrilleurs[nom], poids=poids, crier=crier)
            crier(f"  +{st_ag} h (pas IFS {st_ifs}) : {len(sel)} messages, "
                  f"{len(octets) / 1e6:.1f} Mo, {len(plages)} plages")

        man = I.bloc_manifeste(run_ifs, steps_ifs, last_modified=lm,
                               sonde=f"HEAD {I.url_pas(run_ifs, max(steps_ifs))}.index")
        for nom, g in etendues.items():
            g.ifs = man
            g.steps_ifs = set(steps_agrume)
            bilan["domaines"][nom] = len(steps_agrume)
        bilan["secondes"] = round(time.monotonic() - t0, 1)
        crier(f"▶ rallonge IFS : {len(steps_agrume)} échéance(s) × "
              f"{len(etendues)} domaine(s), {bilan['octets'] / 1e6:.0f} Mo "
              f"tirés en {bilan['secondes']:.0f} s")
        return etendues, bilan
    except Exception as exc:                                # noqa: BLE001
        # ⚠️ Si l'échec survient APRÈS l'extension, `grilles` a été vidé :
        # on rend les grilles ÉTENDUES (échéances neuves à NaN) plutôt
        # que des `None`. Elles se publient — `remplissage()` montre le
        # vide, et `steps_ifs` reste vide donc `provenance()` ne promet
        # aucune IFS. ⛔ C'est le seul cas où le produit sort avec des
        # échéances vides, et il est nommé.
        if any(v is None for v in grilles.values()):
            grilles = {n: g for n, g in (locals().get("etendues") or {}).items()}
        bilan["erreur"] = f"{type(exc).__name__} : {exc}"
        bilan["secondes"] = round(time.monotonic() - t0, 1)
        crier(f"⚠️ rallonge IFS ABANDONNÉE ({bilan['erreur']}) — la coupe "
              f"s'arrête à {I.DEBUT_H - I.PAS_IFS_H} h et le run se publie "
              f"quand même")
        return grilles, bilan


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", required=True,
                    help="le run AGRUME (2026-09-06T00:00:00Z)")
    ap.add_argument("--domaine", default=None,
                    help="un seul domaine (défaut : tous)")
    ap.add_argument("--sonde", action="store_true",
                    help="dire quel run IFS serait retenu, et s'arrêter")
    ap.add_argument("--sans-ecriture", action="store_true", default=True,
                    help="(toujours vrai : ce module n'écrit jamais sur R2)")
    a = ap.parse_args(argv)
    run = datetime.strptime(a.run, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc)

    if a.sonde:
        choix = I.run_disponible(run)
        if choix is None:
            print("aucun run IFS publié ne couvre la fenêtre")
            return 1
        r, steps, lm = choix
        print(f"run IFS retenu : {r:%Y-%m-%dT%H:%M:%SZ} (publié {lm})")
        print(f"  pas IFS        : {steps}")
        print(f"  → échéances AGRUME : {I.heures_agrume(steps, run, r)}")
        return 0

    import orographie
    from domaine import DOMAINES
    from grille import Grille, axes_depuis_orographie

    arts, _ = orographie.charger_artefacts()
    grilles = {}
    for nom, ent in sorted(arts.items()):
        if a.domaine and nom != a.domaine:
            continue
        o3d = ent[0] if isinstance(ent, tuple) else ent
        if isinstance(o3d, dict):
            o3d = o3d.get("0025") or list(o3d.values())[0]
        lats, lons = axes_depuis_orographie(o3d, DOMAINES.get(nom))
        # ⚠️ Une grille VIDE aux échéances AROME : à la main, on ne
        # télécharge pas 21 Go pour vérifier la couture. Le run publié,
        # lui, part d'une grille déjà pleine.
        grilles[nom] = Grille(a.run, [0], lats, lons, o3d.z, domaine=nom)

    etendues, bilan = appliquer(grilles, run)
    print(f"\nbilan : {bilan}")
    for nom, g in etendues.items():
        if not g.steps_ifs:
            continue
        s = sorted(g.steps_ifs)[0]
        k = g.i_step[s]
        u = np.asarray(g.h0025[g.i_param["u"], :, k], dtype=np.float32)
        t = np.asarray(g.h0025[g.i_param["t"], :, k], dtype=np.float32)
        print(f"  [{nom}] +{s} h : u {100 * np.isfinite(u).mean():.1f} % "
              f"renseigné (médiane {np.nanmedian(u):+.2f} m/s) · "
              f"t médiane {np.nanmedian(t):+.1f} °C · "
              f"ziso 850 hPa médiane "
              f"{np.nanmedian(np.asarray(g.ziso[NIVEAUX_P.index(850), k])):.0f} m")
    return 0 if not bilan["erreur"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
