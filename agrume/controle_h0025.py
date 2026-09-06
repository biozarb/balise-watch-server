#!/usr/bin/env python3
"""Le CONTRÔLE D'ACCEPTATION du bloc `h0025` IFS (lot L22b, 06/09/2026).

⛔ LA QUESTION QU'IL POSE, ET POURQUOI ELLE N'A PAS DE RÉPONSE THÉORIQUE.
Le bloc hauteur des échéances IFS n'est pas mesuré : il est DÉRIVÉ de
sept niveaux isobares dont, dans les Alpes, les deux plus bas sont sous
le terrain (mesuré : 1000 hPa souterrain sur 98,9 % des mailles du
domaine nord-alpes, 925 sur 58,6 %). Entre l'ancre 10 m et le premier
niveau libre, la colonne est une DROITE — pas un profil de couche
limite. Ce que ça coûte ne se déduit pas ; ça se mesure.

⛔ ET IL EXISTE UNE FENÊTRE OÙ LES DEUX MODÈLES SE RECOUVRENT : AROME va
jusqu'à 51 h, IFS commence à être cousu à 54 h — mais IFS publie AUSSI
48 et 51 h. On compare donc, à HEURE VALIDE ÉGALE et à RUN ÉGAL, le
bloc hauteur d'AROME (mesuré) et le bloc hauteur dérivé d'IFS. C'est le
seul chiffre qui puisse dire si ce bloc mérite d'être servi.

⚠️ CE QU'IL NE DIT PAS. Un écart AROME ↔ IFS n'est pas une erreur : ce
sont deux modèles, et à +48 h le nôtre n'est pas forcément le bon (nos
propres scores donnent IFS premier dans tous les massifs alpins à cette
échéance). Ce contrôle mesure une DIFFÉRENCE, pas une justesse. Ce qu'on
y cherche est plus étroit : que l'écart ne soit pas d'un autre ORDRE en
bas de colonne qu'en haut — parce que ça, ce serait la dérivation qui
parle, pas la météo.

⛔ DEUX MACHINES, ET C'EST LA RÈGLE DU PROJET QUI L'IMPOSE. « Le VPS ne
touche aucun GRIB IFS » : la partie qui télécharge tourne là où il y a
du réseau et eccodes (le runner, ou une session de dev) et dépose un
`.npz` ; la partie qui lit le produit B sur R2 tourne sur le VPS, qui
seul a le jeton de LECTURE de `balise-watch-grids`.

    # là où il y a réseau + eccodes
    python3 agrume/controle_h0025.py --produire /tmp/ifs-ctl.npz \
            --run 2026-09-06T12:00:00Z --domaine nord-alpes
    # sur le VPS
    python3 agrume/controle_h0025.py --comparer /tmp/ifs-ctl.npz
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from datetime import datetime, timezone

_ICI = pathlib.Path(__file__).resolve().parent
for _p in (_ICI, _ICI.parent / "tools", _ICI.parent / "model-verif"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

import numpy as np                                          # noqa: E402

#: Les échéances de recouvrement : AROME les a (0-51 h), IFS aussi
#: (pas natif 3 h). ⚠️ 48 ET 51, pas seulement 48 : une seule échéance
#: ne distinguerait pas un écart de modèle d'un écart d'instant.
STEPS_COMMUNS = (48, 51)

#: Ce qu'on compare. `r` n'y est pas : sans ancre à 2 m, le bloc dérivé
#: est vide en bas de colonne dans les Alpes (mesuré : 0 % à 10 m/sol),
#: et comparer du vide à du plein ne mesure rien.
CHAMPS = ("u", "v", "t")


def _zsol_ifs(gh, sp_hpa, natifs):
    """L'altitude où la pression vaut `sp` — le sol du modèle IFS.

    ⚠️ `sp` dépasse 1000 hPa au niveau de la mer : sous le plus bas
    niveau natif, on PROLONGE la droite (1000, 925) en log p plutôt que
    de rendre `NaN`. C'est une extrapolation, elle est nommée, et elle
    ne sert qu'à ce contrôle — jamais au produit servi.
    """
    lp = np.log(np.asarray(natifs, dtype=np.float64))
    x = np.log(np.clip(np.asarray(sp_hpa, dtype=np.float64), 1.0, None))
    out = np.full(x.shape, np.nan, dtype=np.float32)
    for k in range(len(natifs) - 1):
        m = (lp[k] >= x) & (x >= lp[k + 1])
        if m.any():
            w = (lp[k] - x[m]) / (lp[k] - lp[k + 1])
            out[m] = gh[k][m] + w * (gh[k + 1][m] - gh[k][m])
    bas = x > lp[0]                       # sous 1000 hPa (plaine, mer)
    if bas.any():
        w = (lp[0] - x[bas]) / (lp[0] - lp[1])
        out[bas] = gh[0][bas] + w * (gh[1][bas] - gh[0][bas])
    return out.astype(np.float32)


def produire(chemin, run_txt, domaine):
    """Le bloc hauteur DÉRIVÉ d'IFS, aux échéances de recouvrement."""
    import ifs as I
    import orographie
    from grille import axes_depuis_orographie
    from domaine import DOMAINES, NIVEAUX_H_0025

    run = datetime.strptime(run_txt, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc)
    arts, _ = orographie.charger_artefacts()
    ent = arts[domaine]
    o3d = ent[0] if isinstance(ent, tuple) else ent
    if isinstance(o3d, dict):
        o3d = o3d.get("0025") or list(o3d.values())[0]
    lats, lons = axes_depuis_orographie(o3d, DOMAINES[domaine])
    zsol = np.asarray(o3d.z, dtype=np.float32)
    R = I.Regrilleur(lats, lons)

    out = {}
    for step in STEPS_COMMUNS:
        url = I.url_pas(run, step)
        C = I.decoder(I.tirer(url, I.plages(I.selection(I.lire_index(url)))))
        gh = np.stack([R(C[("gh", n)]) for n in I.NIVEAUX_COMMUNS])
        # ⛔ L'OROGRAPHIE D'IFS, DÉRIVÉE DE `sp` — parce que c'est
        # l'explication la plus probable de tout écart de TEMPÉRATURE en
        # bas de colonne, et qu'une explication probable se mesure. Le
        # sol du modèle est l'altitude où la pression vaut `sp` : on la
        # trouve en interpolant `gh` en log p à p = sp.
        out[f"zsol_ifs_{step}"] = _zsol_ifs(gh, R(C[("sp", 0)]) / 100.0,
                                            I.NIVEAUX_COMMUNS)
        for nom, court10 in (("u", "10u"), ("v", "10v"), ("t", "2t")):
            pile = np.stack([R(C[(nom, n)]) for n in I.NIVEAUX_COMMUNS])
            anc = R(C[(court10, 10 if nom != "t" else 2)])
            h = I.deriver_hauteurs(pile, gh, zsol, ancre=anc)
            if nom == "t":
                h = h - 273.15          # le produit B stocke des °C
            out[f"{nom}_{step}"] = h.astype(np.float32)
        print(f"  IFS +{step} h dérivé : "
              f"{100 * np.isfinite(out[f'u_{step}']).mean():.1f} % renseigné")
    np.savez_compressed(chemin, zsol=zsol, lats=lats, lons=lons,
                        run=run_txt, domaine=domaine,
                        niveaux=np.asarray(NIVEAUX_H_0025), **out)
    ko = pathlib.Path(chemin).stat().st_size / 1024
    print(f"  écrit : {chemin} ({ko:.0f} Ko)")


def comparer(chemin):
    """AROME (mesuré) contre IFS (dérivé), même run, mêmes heures valides."""
    import glob as _glob

    for f in sorted(_glob.glob(os.path.expanduser("~/.balise-watch*.env"))):
        for ligne in open(f):
            ligne = ligne.strip()
            if ligne and not ligne.startswith("#") and "=" in ligne:
                k, v = ligne.split("=", 1)
                os.environ.setdefault(k.replace("export ", "").strip(),
                                      v.strip().strip('"').strip("'"))
    os.environ.setdefault("STORAGE_BACKEND", "r2")

    from r2_lecture import bucket_r2, prefixe_lecture
    import grille as G
    from domaine import NIVEAUX_H_0025
    from storage import Storage

    d = np.load(chemin, allow_pickle=False)
    run = str(d["run"]) if d["run"].shape == () else str(d["run"][()])
    domaine = str(d["domaine"]) if d["domaine"].shape == () else str(d["domaine"][()])
    print(f"▶ contrôle h0025 — run {run}, domaine {domaine}")

    with bucket_r2("balise-watch-grids", prefixe_lecture()):
        st = Storage("controle-h0025", "AGRUME_BUCKET", "wind-grid")
        base = G.prefixe_run(run, domaine)
        man = json.loads(st.get(f"{base}/manifest.json"))
        zsol_oct = st.get(f"{base}/zsol.bin")
        tampons = {s: st.get(f"{base}/e{s:02d}.bin") for s in STEPS_COMMUNS}
        manquants = [s for s, t in tampons.items() if not t]
        if manquants:
            print(f"❌ échéance(s) {manquants} absente(s) du run AROME — "
                  f"la rallonge n'est allée que jusqu'à "
                  f"{max(man['echeances'])} h", file=sys.stderr)
            return 1
        g = G.Grille.depuis_tampons(man, tampons, zsol_oct)

    print(f"\n  {'niveau':>7}  " + "  ".join(f"{c:>22}" for c in CHAMPS))
    print(f"  {'m/sol':>7}  " + "  ".join(f"{'médiane   d9   max':>22}"
                                          for _ in CHAMPS))
    lignes = []
    for k, niv in enumerate(NIVEAUX_H_0025):
        bouts = []
        for c in CHAMPS:
            ia = g.i_param[c]
            ecarts = []
            for s in STEPS_COMMUNS:
                a = np.asarray(g.h0025[ia, k, g.i_step[s]], dtype=np.float32)
                b = d[f"{c}_{s}"][k]
                m = np.isfinite(a) & np.isfinite(b)
                if m.any():
                    ecarts.append(np.abs(a[m] - b[m]))
            if not ecarts:
                bouts.append(f"{'—':>22}")
                continue
            e = np.concatenate(ecarts)
            bouts.append(f"{np.median(e):7.2f}{np.percentile(e, 90):7.2f}"
                         f"{e.max():8.2f}")
            lignes.append((niv, c, float(np.median(e))))
        print(f"  {niv:>7}  " + "  ".join(bouts))

    # ⛔ LE CHIFFRE QUI DÉCIDE : le bas de colonne parle-t-il d'autre
    # chose que le haut ? Si oui, c'est la dérivation, pas la météo.
    for c in CHAMPS:
        bas = [m for n, cc, m in lignes if cc == c and n <= 500]
        haut = [m for n, cc, m in lignes if cc == c and n >= 2000]
        if bas and haut:
            r = np.median(bas) / max(np.median(haut), 1e-6)
            print(f"\n  {c} : écart médian bas de colonne (≤500 m) "
                  f"{np.median(bas):.2f} · haut (≥2000 m) {np.median(haut):.2f} "
                  f"· rapport ×{r:.2f}")
    # ⛔ LA CAUSE, MESURÉE PLUTÔT QUE SUPPOSÉE. Le sol d'IFS (0,25°)
    # n'est pas celui d'AROME (0,025°) : l'ancre 10 m d'IFS est donc
    # posée à une altitude qui n'est pas celle du sol sur lequel on la
    # pose. Sur la température, un écart de sol se paie directement au
    # gradient (~6,5 °C/km) ; sur le vent, beaucoup moins.
    cle = f"zsol_ifs_{STEPS_COMMUNS[0]}"
    if cle in d:
        z_ifs = d[cle]
        z_ar = np.asarray(d["zsol"], dtype=np.float32)
        dz = z_ifs - z_ar
        fini = np.isfinite(dz)
        print(f"\n  ⛔ orographie IFS − orographie AROME : médiane "
              f"{np.median(dz[fini]):+.0f} m · |médiane| "
              f"{np.median(np.abs(dz[fini])):.0f} m · d9 "
              f"{np.percentile(np.abs(dz[fini]), 90):.0f} m · max "
              f"{np.abs(dz[fini]).max():.0f} m")
        # la corrélation entre |Δsol| et l'écart de température à 10 m
        ia = g.i_param["t"]
        a = np.asarray(g.h0025[ia, 0, g.i_step[STEPS_COMMUNS[0]]], np.float32)
        b = d[f"t_{STEPS_COMMUNS[0]}"][0]
        m = np.isfinite(a) & np.isfinite(b) & fini
        if m.sum() > 100:
            x, y = np.abs(dz[m]), np.abs(a[m] - b[m])
            rho = float(np.corrcoef(x, y)[0, 1])
            pente = float(np.polyfit(x, y, 1)[0]) * 1000.0
            print(f"  ⭐ |Δsol| ↔ |Δt| à 10 m/sol : r = {rho:.2f}, pente "
                  f"{pente:.1f} °C/km — le gradient atmosphérique vaut "
                  f"~6,5 °C/km")

    print("\n  ⚠️ Un écart n'est pas une erreur : ce sont deux modèles. Ce "
          "qu'on lit ici, c'est si le BAS de colonne se comporte comme le "
          "haut — sinon c'est la dérivation qui parle.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--produire", metavar="NPZ")
    ap.add_argument("--comparer", metavar="NPZ")
    ap.add_argument("--run", default=None)
    ap.add_argument("--domaine", default="nord-alpes")
    a = ap.parse_args()
    if a.produire:
        if not a.run:
            print("❌ --produire demande --run", file=sys.stderr)
            return 2
        produire(a.produire, a.run, a.domaine)
        return 0
    if a.comparer:
        return comparer(a.comparer)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
