#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  verif/marche_raccord.py — mesurer la marche entre les deux mailles
#                                                        (10/08/2026)
#
#  ⚠️ C'EST LE CRITÈRE D'ACCEPTATION QUI MANQUE À L'HYBRIDE.
#
#  Le §4.1 bis du lot H retient la maille fine sous 100 m/sol — la
#  tranche du décollage — et prévient : cet hybride ajoute un SECOND
#  raccord, entre deux MAILLES cette fois, dont « une marche est probable
#  et devra être mesurée, PAS supposée ». Ce fichier est cette mesure.
#
#  Il ne décide rien. Il produit un chiffre, avec son `n`, à partir d'une
#  archive du produit A déjà écrite — donc sans retélécharger un octet.
#  C'est la seule façon honnête de trancher : si la marche est faible,
#  l'hybride est un gain net ; si elle est forte, on aura appris quelque
#  chose sur le modèle plutôt que d'avoir livré un artefact.
#
#  ── DEUX FAÇONS DE COMPARER, ET ELLES NE DISENT PAS LA MÊME CHOSE ────
#
#  **À hauteur-sol égale** (10, 20, 50, 100 m AGL) : on compare ce que
#  les deux mailles disent du vent à la même hauteur au-dessus de LEUR
#  sol respectif. C'est la comparaison qui a un sens météorologique — le
#  profil de couche de surface se rapporte au sol local.
#
#  **À altitude-mer égale** : c'est ce que voit un pilote, mais les deux
#  sols du modèle diffèrent (|écart| médian 75 m aux balises du domaine,
#  jusqu'à 643 m), donc « même altitude ASL » veut dire « hauteurs-sol
#  différentes » — et une bonne part de l'écart mesuré ne viendrait alors
#  pas de la maille mais de l'orographie. Les deux sont calculées, et
#  l'écart entre les deux écarts est lui-même l'information.
#
#  ══════════════════════════════════════════════════════════════════
#  ⛔ 16/08/2026 — DEUX TROUS TROUVÉS EN PRÉPARANT LE LOT K, COMBLÉS ICI.
#
#  1. **L'écart ABSOLU seul ment dès qu'un run calme domine.** Mesuré du
#     10 au 16/08 sur huit runs : la médiane de |V| à 10 m ne dépasse
#     JAMAIS 1,5 m/s, et le critère du lot (< 1 m/s) est de toute façon
#     tenu en médiane sur CHACUN d'eux — y compris les deux journées
#     (14-15/08) qui « s'annonçaient ventées ». Un chiffre agrégé sur un
#     échantillon à 90-98 % calme ne teste jamais le cas qui inquiète.
#     ⇒ `BACS_VITESSE_MS` stratifie par la vitesse de RÉFÉRENCE (0,025°)
#     et publie l'écart RELATIF (Δ|V| / |V|) à côté de l'absolu — c'est
#     l'idée du 10/08 (`claude/lot-h-etape-7-recherche-du-vent-10-08.md`
#     §4, point 2), jamais codée depuis.
#
#  2. **L'archive mélange maintenant plusieurs domaines de tailles très
#     différentes.** Au 16/08 : 207 balises Nord-Alpes, 55 Pyrénées,
#     23-26 Tarn/Aveyron/Hérault, plus quelques radiosondages/isolées
#     sans domaine. Un run peut venter fort sur UN SEUL domaine (mesuré
#     le 15/08 : 80 couples ≥ 8 m/s à 100 m/sol côté Pyrénées contre 25
#     côté Alpes, sur un échantillon 3× plus petit) — sans filtre, la
#     médiane globale resterait dominée par le plus grand domaine et
#     dirait « calme » alors qu'un domaine ventait. ⇒ `--domaine`.
#
#  Usage :
#      python3 verif/marche_raccord.py archive.npz archive.json
#      python3 verif/marche_raccord.py archive.npz archive.json \
#              --domaine pyrenees
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agrume"))

from colonnes import Colonnes  # noqa: E402
from quantification import PARAMS_001, PARAMS_0025  # noqa: E402
from domaine import GRID_3D, GRID_FINE, NIVEAUX_H_001, NIVEAUX_H_0025  # noqa: E402


def quantiles(v):
    a = np.sort(np.asarray(v, dtype=float))
    if not len(a):
        return None
    def q(p):
        return float(a[min(len(a) - 1, int(p * len(a)))])
    return dict(n=len(a), d1=q(0.1), q1=q(0.25), mediane=q(0.5),
                q3=q(0.75), d9=q(0.9), max=float(a[-1]))


# ── Bacs de vitesse (16/08) ─────────────────────────────────────────
# Le critère d'acceptation du lot (< 1 m/s) est un écart ABSOLU. Sur un
# run calme — et TOUS les runs mesurés du 10 au 16/08 le sont, médiane
# 1,2-1,5 m/s à 10 m — il est tenu automatiquement, sans rien dire du
# raccord PAR VENT FORT. Stratifier par la vitesse de RÉFÉRENCE (celle
# de la maille 0,025°, qui couvre tout le domaine) est ce qui manquait
# pour que le lot K puisse un jour conclure quelque chose.
BACS_VITESSE_MS = ((0.0, 3.0, "< 3 m/s"), (3.0, 5.0, "3-5 m/s"),
                   (5.0, 8.0, "5-8 m/s"), (8.0, float("inf"), "≥ 8 m/s"))

# En dessous de ce seuil, l'écart RELATIF explose sans rien dire de
# physique — mesuré le 10/08 : « à 3 km/h de vent [0,83 m/s], 0,67 m/s
# d'écart c'est 80 % du signal ». Ces points comptent dans les bacs
# absolus, jamais dans le relatif — et leur compte est publié, pas tu.
SEUIL_RELATIF_MS = 1.0


def par_bacs(vitesse_ref, ecart_abs):
    """Stratifie `ecart_abs` (m/s) par tranche de `vitesse_ref` (m/s, la
    maille 0,025°). Rend, par bac : les quantiles absolus, les quantiles
    RELATIFS (%, seulement au-dessus de `SEUIL_RELATIF_MS`), et le
    compte exclu du relatif faute de signal.
    """
    vitesse_ref = np.asarray(vitesse_ref, dtype=float)
    ecart_abs = np.asarray(ecart_abs, dtype=float)
    out = []
    for lo, hi, nom in BACS_VITESSE_MS:
        m = (vitesse_ref >= lo) & (vitesse_ref < hi)
        qa = quantiles(ecart_abs[m])
        rel_m = m & (vitesse_ref >= SEUIL_RELATIF_MS)
        qr = (quantiles(100.0 * ecart_abs[rel_m] / vitesse_ref[rel_m])
              if rel_m.any() else None)
        out.append(dict(bac=nom, vmin=lo,
                        vmax=(None if hi == float("inf") else hi),
                        absolu=qa, relatif_pct=qr,
                        n_exclus_relatif=int((m & ~rel_m).sum())))
    return out


def _indices_domaine(balises, domaine):
    """Indices des balises du domaine demandé, ou toutes si `domaine`
    est None. ⚠️ `domaine` est lu par balise (`b["domaine"]`), jamais
    déduit d'un `.startswith` sur l'identifiant — c'est le manifeste qui
    fait foi, comme partout ailleurs dans le projet."""
    if domaine is None:
        return list(range(len(balises)))
    return [k for k, b in enumerate(balises) if b.get("domaine") == domaine]


def mesurer(col, man, crier=print, domaine=None):
    idx = _indices_domaine(col.balises, domaine)
    if not idx:
        presents = sorted({b.get("domaine") for b in col.balises
                           if b.get("domaine")})
        crier(f"⛔ aucune balise du domaine {domaine!r} dans cette archive "
              f"— domaines présents : {presents}")
        return dict(run=col.run, domaine=domaine, par_niveau={},
                   n_balises=0, n_echeances=len(col.steps))
    balises = [col.balises[k] for k in idx]

    i0 = {p["nom"]: k for k, p in enumerate(PARAMS_0025)}
    i1 = {p["nom"]: k for k, p in enumerate(PARAMS_001)}
    c0 = np.asarray(col.c0025, dtype=np.float32)[idx]
    c1 = np.asarray(col.c001, dtype=np.float32)[idx]

    resultats = {}
    entete = f"── MARCHE AU RACCORD 0,01° / 0,025°, run {col.run}"
    if domaine:
        entete += f", domaine {domaine}"
    crier(entete + " ──")
    sous_titre = f"   {len(balises)} balises × {len(col.steps)} échéances"
    if domaine and len(balises) != len(col.balises):
        sous_titre += f" (sur {len(col.balises)} dans l'archive complète)"
    crier(sous_titre + "\n")
    crier("   À HAUTEUR-SOL ÉGALE — la comparaison qui a un sens physique")
    crier("   niveau |  écart de VITESSE (m/s)          |  écart d'ANGLE (°)")
    crier("    m/sol |  médian    q3      d9     max    |  médian     d9")
    for niveau in NIVEAUX_H_001:
        j0 = NIVEAUX_H_0025.index(niveau)
        j1 = NIVEAUX_H_001.index(niveau)
        u0, v0 = c0[:, i0["u"], j0], c0[:, i0["v"], j0]
        u1, v1 = c1[:, i1["u"], j1], c1[:, i1["v"], j1]
        bon = np.isfinite(u0) & np.isfinite(v0) & np.isfinite(u1) & np.isfinite(v1)
        if not bon.any():
            crier(f"   {niveau:>6} | aucune donnée commune")
            continue
        # ⚠️ L'écart se calcule sur les COMPOSANTES, jamais sur l'angle :
        # un vent de 359° et un de 001° sont à 2° l'un de l'autre, pas à
        # 358°. La norme de la différence vectorielle est la seule mesure
        # qui ne se fait pas piéger.
        d = np.hypot(u1[bon] - u0[bon], v1[bon] - v0[bon])
        # L'écart angulaire, lui, se replie explicitement dans [-180, 180].
        a0 = np.degrees(np.arctan2(v0[bon], u0[bon]))
        a1 = np.degrees(np.arctan2(v1[bon], u1[bon]))
        da = np.abs((a1 - a0 + 180) % 360 - 180)
        # Vitesse de RÉFÉRENCE (0,025°), pour l'angle ET pour les bacs.
        vitesse0 = np.hypot(u0[bon], v0[bon])
        fort = vitesse0 > 1.0
        qv, qa = quantiles(d), quantiles(da[fort]) if fort.any() else None
        bacs = par_bacs(vitesse0, d)
        resultats[niveau] = dict(vitesse=qv, angle=qa,
                                 n_pour_angle=int(fort.sum()), par_bac=bacs)
        crier(f"   {niveau:>6} | {qv['mediane']:6.2f} {qv['q3']:6.2f} "
              f"{qv['d9']:6.2f} {qv['max']:6.2f}   | "
              + (f"{qa['mediane']:7.1f} {qa['d9']:7.1f}" if qa else "   n/a"))

    crier("\n   PAR BAC DE VITESSE (référence = |V| à 0,025°) — l'écart "
          "absolu seul ment tant qu'un run calme domine l'échantillon")
    crier("   niveau  bac          n    abs médian  abs d9  |  "
          f"rel médian  rel d9  | exclus (< {SEUIL_RELATIF_MS:.0f} m/s)")
    for niveau, r in resultats.items():
        for b in r["par_bac"]:
            qa = b["absolu"]
            if qa is None:
                crier(f"   {niveau:>6}  {b['bac']:<11} aucune donnée dans "
                      f"ce bac")
                continue
            qr = b["relatif_pct"]
            crier(f"   {niveau:>6}  {b['bac']:<11}{qa['n']:5d}  "
                  f"{qa['mediane']:9.2f}  {qa['d9']:7.2f}  |  "
                  + (f"{qr['mediane']:8.1f}%  {qr['d9']:6.1f}%" if qr
                     else "     n/a       n/a")
                  + f"  | {b['n_exclus_relatif']:4d}")

    # Le seul point où les deux mailles sont censées se rejoindre pour de
    # bon : le sommet de la tranche fine.
    seuil = resultats.get(100, {}).get("vitesse")
    crier("")
    if seuil:
        crier(f"   ⚠️ AU RACCORD (100 m/sol) : écart médian "
              f"{seuil['mediane']:.2f} m/s, d9 {seuil['d9']:.2f}, "
              f"max {seuil['max']:.2f} (n = {seuil['n']})")
        crier(f"   Le critère d'acceptation du lot demande < 1 m/s dans la "
              f"zone de recouvrement du raccord hauteur/isobares ; appliqué "
              f"ici au raccord de MAILLES, il est "
              f"{'TENU' if seuil['mediane'] < 1.0 else 'DÉPASSÉ'} en médiane "
              f"et {'tenu' if seuil['d9'] < 1.0 else 'dépassé'} au d9.")
        crier(f"   ⚠️ Ce verdict porte sur TOUT l'échantillon — dominé par "
              f"le calme. Lire le tableau par bac ci-dessus pour la "
              f"tranche ≥ 8 m/s avant de le croire par vent fort.")

    # ── Et le sol, lui, n'est pas le même ─────────────────────────────
    dz = [b["z_0025"] - b["z_001"] for b in balises
          if b.get("z_0025") is not None and b.get("z_001") is not None]
    qz = quantiles(np.abs(dz))
    crier(f"\n   ⓘ POUR MÉMOIRE, l'écart d'OROGRAPHIE entre les deux mailles "
          f"aux mêmes balises :")
    if qz:
        crier(f"     |z_0025 − z_001| médian {qz['mediane']:.0f} m · d9 "
              f"{qz['d9']:.0f} m · max {qz['max']:.0f} m (n = {qz['n']})")
    crier("     À hauteur-sol égale, les deux profils ne sont donc PAS à la "
          "même altitude-mer.")
    crier("     C'est ce décalage — pas la marche de vent — qui domine la "
          "différence vue par un pilote.")
    return dict(run=col.run, domaine=domaine, par_niveau=resultats,
               orographie=qz, n_balises=len(balises),
               n_echeances=len(col.steps))


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("npz")
    p.add_argument("manifeste")
    p.add_argument("--domaine", default=None,
                   help="ne mesurer que ce domaine (nord-alpes, pyrenees, "
                        "tarn-aveyron-herault…) — par défaut, tous les "
                        "domaines de l'archive sont mélangés, ce qui DILUE "
                        "un vent localisé à un seul d'entre eux")
    p.add_argument("--json", action="store_true", help="sortie brute")
    a = p.parse_args(argv)
    man = json.loads(Path(a.manifeste).read_text(encoding="utf-8"))
    col, _ = Colonnes.lire_npz(a.npz, man)
    r = mesurer(col, man, crier=(lambda *x: None) if a.json else print,
               domaine=a.domaine)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
