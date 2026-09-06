#!/usr/bin/env python3
"""Rejoue le banc contre des variantes CASSÉES du lot L22b — la rallonge
IFS 54 → 72 h du produit B (07/09/2026).

⛔ CE QU'ON CRAINT ICI EST D'UNE AUTRE NATURE QU'AU L22a. Le L22a
recopiait une ligne ; celui-ci fabrique une grille à partir d'un GRIB
mondial, et **presque toutes ses fautes rendent un champ lisse**. Un
champ lisse et faux ne lève rien, ne trace aucun trou, et s'affiche comme
une belle coupe. Les huit façons :

  · lire la grille source à Greenwich alors qu'elle commence à 180°
    (le domaine est lu à 19 980 km de là, dans le Pacifique) ;
  · supposer que les latitudes montent (le domaine bascule au sud) ;
  · inverser le signe de la conversion pas IFS → heure AGRUME (les
    échéances 54-72 écrasent les échéances AROME 30-48) ;
  · choisir l'échéance par son NUMÉRO plutôt que par son heure valide ;
  · interpoler la verticale en `p` au lieu de `log p` ;
  · dériver le bloc hauteur À TRAVERS l'air souterrain, ou le laisser
    vide sans que rien ne rougisse ;
  · publier des kelvins, ou `gh` divisé par g ;
  · poser un champ de surface BRUT dans la grille du domaine.

⚠️ Le motif à muter doit exister TEL QUEL : une mutation dont le motif
est introuvable n'a rien muté, donc rien prouvé.

    python3 agrume/mutations_l22b.py
    python3 agrume/mutations_l22b.py 1 4
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
sys.path.insert(0, str(ICI.parent / "model-verif"))
import harnais as HARNAIS  # noqa: E402

IFS = ICI / "ifs.py"
GRILLE = ICI / "grille.py"
INGEST = ICI / "ingest_ifs.py"
BANC = ICI / "test_ifs.py"

MUTATIONS = [
    ("⭐⭐ la grille source est lue à Greenwich (la convention la plus "
     "répandue) : le domaine part dans le Pacifique, et le champ reste lisse",
     IFS, BANC,
     "        x = ((lons - SRC_LON0) % 360.0) / SRC_PAS\n",
     "        x = (lons % 360.0) / SRC_PAS\n"),

    ("⭐ les latitudes sont supposées MONTER depuis −90 : le domaine "
     "bascule dans l'hémisphère sud",
     IFS, BANC,
     "        y = (SRC_LAT0 - lats) / SRC_PAS\n",
     "        y = (lats + 90.0) / SRC_PAS\n"),

    ("⭐⭐ le signe de la conversion pas IFS → heure AGRUME est inversé : "
     "la rallonge ÉCRASE les échéances AROME 30 → 48 h",
     IFS, BANC,
     "    return [int(s) - ecart_h for s in steps_ifs]",
     "    return [int(s) + ecart_h for s in steps_ifs]"),

    ("l'échéance est choisie par son NUMÉRO de pas et non par son heure "
     "valide : la coupe est décalée du décalage entre les deux runs",
     IFS, BANC,
     "    return [h + ecart_h for h in range(debut_h, fin_h + 1)\n"
     "            if (h + ecart_h) % PAS_IFS_H == 0 and h + ecart_h >= 0]",
     "    return [h for h in range(debut_h, fin_h + 1)\n"
     "            if h % PAS_IFS_H == 0]"),

    ("la verticale s'interpole en `p` au lieu de `log p` : tout l'axe "
     "isobare glisse, régulièrement",
     IFS, BANC,
     "    lp = np.log(np.asarray(natifs, dtype=np.float64))\n    out = []",
     "    lp = np.asarray(natifs, dtype=np.float64)\n    out = []"),

    ("⭐⭐ les niveaux SOUTERRAINS entrent dans la colonne : le bloc "
     "hauteur est dérivé à travers de l'air fictif",
     IFS, BANC,
     "    libre = gh > z_ancre[None, :, :]\n",
     "    libre = np.ones(gh.shape, dtype=bool)\n"),

    ("⭐ les niveaux souterrains repartent à NaN au lieu d'être écrasés "
     "sur l'ancre : le bloc hauteur se vide (1,1 % rempli, mesuré)",
     IFS, BANC,
     "        z = np.where(libre, gh, z_ancre[None, :, :])\n"
     "        v = np.where(libre, vals_iso, anc[None, :, :])\n",
     "        z = np.where(libre, gh, np.nan)\n"
     "        v = np.where(libre, vals_iso, np.nan)\n"),

    # ⓘ MUTATION RETIRÉE : « le niveau natif n'est plus recopié mais
    # réinterpolé » (`out[k] = pile[a] * (1 - w) + pile[b] * w`, sans le
    # raccourci `a == b`). Le banc restait vert — et il avait RAISON :
    # pour un natif, `a == b` et `w == 0`, donc l'expression vaut
    # `pile[a] * 1 + pile[a] * 0`, c'est-à-dire exactement `pile[a]`.
    # Ce n'était pas un défaut, c'était une écriture équivalente. Le
    # raccourci reste dans le code pour la lisibilité, pas pour
    # l'exactitude — et la mutation ci-dessous, elle, mord vraiment.
    ("⭐⭐ les poids de l'interpolation verticale sont ÉCHANGÉS (w ↔ 1−w) : "
     "chaque niveau fabriqué glisse d'un demi-intervalle, ~300 m, et la "
     "coupe reste lisse ET monotone",
     IFS, BANC,
     "        out[k] = pile[a] if a == b else pile[a] * (1 - w) + pile[b] * w",
     "        out[k] = pile[a] if a == b else pile[a] * w + pile[b] * (1 - w)"),

    ("⭐ la température est publiée en KELVINS : 273 de trop, qui se "
     "quantifient sans erreur et s'affichent comme une canicule",
     INGEST, BANC,
     '    ("t", "t", "2t", 2, -273.15),',
     '    ("t", "t", "2t", 2, 0.0),'),

    ("⭐ `ziso` est divisé par g — le réflexe venu du produit A, où `z` "
     "est un géopotentiel : le raccord se ferait à 700 m au lieu de 7 000",
     INGEST, BANC,
     "    ziso = I.interpoler_log_p(gh, poids)",
     "    ziso = I.interpoler_log_p(gh, poids) / 9.80665"),

    ("⭐⭐ un champ de surface est posé BRUT (721 × 1440) dans la grille "
     "du domaine",
     INGEST, BANC,
     '        g.poser_surface(nom_b, step_agrume, R(_ancre(champs, court, 0)) * fac)',
     '        g.poser_surface(nom_b, step_agrume, _ancre(champs, court, 0) * fac)'),

    ("l'ancre de surface est cherchée au niveau 0 pour tous les champs : "
     "`10u`/`10v`/`2t` deviennent introuvables et la colonne perd son bas",
     IFS, BANC,
     "    return [int(s) - ecart_h for s in steps_ifs]\n",
     "    return [int(s) - ecart_h for s in steps_ifs]\n") if False else
    ("l'ancre de surface est cherchée au seul niveau 0 : `10u`/`10v`/`2t` "
     "sortent aux niveaux 10 et 2, donc deviennent introuvables",
     INGEST, BANC,
     "    for niv in ((niveau,) if niveau is not None else ()) + (0,):",
     "    for niv in (0,):"),

    ("⭐ la sélection prend les 14 niveaux IFS au lieu des 7 utiles : "
     "+21 Mo par pas pour des cases qui n'existent pas dans le produit B",
     IFS, BANC,
     "def selection(msgs: list[dict], niveaux=NIVEAUX_COMMUNS,",
     "def selection(msgs: list[dict], niveaux=NIVEAUX_IFS,"),

    ("un 404 « pas encore publié » est pris pour une panne : la chaîne "
     "tombe au lieu de reculer d'un réseau",
     IFS, BANC,
     "        if exc.code == 404:\n            return None\n        raise",
     "        raise"),

    ("⭐ étendre une grille DÉPLACE les échéances d'avant (resize au lieu "
     "de copie par indice)",
     GRILLE, BANC,
     "        for s in self.steps:\n            a, b = self.i_step[s], g.i_step[s]",
     "        for s in self.steps:\n            a, b = self.i_step[s], self.i_step[s]"),

    ("⭐ la provenance dit AROME sur les échéances cousues : l'écran sert "
     "de l'IFS sous l'étiquette d'un autre modèle",
     GRILLE, BANC,
     "                 blocs=(_blocs_ifs() if int(s) in self.steps_ifs",
     "                 blocs=(_blocs_ifs() if False"),
]


def joue(debut: int = 1, fin: int | None = None) -> int:
    """⚠️ Jouer par tranches courtes : un harnais tué laisse le fichier muté."""
    fin = len(MUTATIONS) if fin is None else fin
    rouges = 0
    for i, (nom, fichier, banc, avant, apres) in enumerate(MUTATIONS, 1):
        if not (debut <= i <= fin):
            continue
        origine = HARNAIS.garder(fichier)
        if avant not in origine:
            print(f"  ⛔ {i:>2}. {nom}\n       MOTIF INTROUVABLE dans "
                  f"{fichier.name} — la mutation n'a rien muté, donc elle "
                  f"n'a rien prouvé. (Le code a bougé : réécrire ce motif.)")
            rouges += 1
            HARNAIS.rendre(fichier, origine)
            continue
        try:
            fichier.write_text(origine.replace(avant, apres, 1),
                               encoding="utf-8")
            r = subprocess.run([sys.executable, str(banc)],
                               capture_output=True, text=True, cwd=ICI,
                               env=HARNAIS.env_banc(ICI))
            if r.returncode == 0:
                print(f"  ❌ {i:>2}. {nom}\n       LE BANC RESTE VERT "
                      f"({banc.name}) — il ne tient pas cette propriété.")
                rouges += 1
            else:
                lignes = [l.strip() for l in r.stdout.splitlines()
                          if l.strip().startswith("❌")]
                if not lignes:
                    lignes = [l.strip() for l in r.stderr.splitlines()[-3:]]
                print(f"  ✅ {i:>2}. {nom}\n       [{banc.name}] "
                      f"{(lignes[0] if lignes else 'banc rouge')[:150]}"
                      + (f" (+{len(lignes) - 1} autres)"
                         if len(lignes) > 1 else ""))
        finally:
            HARNAIS.rendre(fichier, origine)
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations du lot L22b — la rallonge IFS. Chaque ligne doit "
          "être VERTE,\n  c'est-à-dire : le banc a bien ROUGI sur la faute.\n")
    d = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    f = int(sys.argv[2]) if len(sys.argv) > 2 else len(MUTATIONS)
    n = joue(d, f)
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
