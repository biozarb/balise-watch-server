#!/usr/bin/env python3
"""Rejoue le banc contre des variantes CASSÉES de la sonde de chaîne
(lot L4 : décomposition du plancher d'`arome_r2`).

⛔ Un banc vert ne prouve rien tant qu'on n'a pas vu ce qui le fait
rougir. Et la faute qu'on craint ici n'est pas le plantage : c'est une
décomposition qui SOMME au total — donc qui a l'air juste — en
attribuant à la mauvaise cause. Aucune des mutations ci-dessous ne fait
tomber la sonde ; toutes rendent un rapport parfaitement lisible avec
des parts fausses.

⚠️ JOUER PAR TRANCHES COURTES (`python3 mutations_sonde_chaine_arome.py
1 5`, puis `6 10`…) : un processus TUÉ ne passe pas par son `finally`
et laisse le fichier MUTÉ sur le disque. Vécu deux fois le 27/08 au lot
L3. Contrôle d'intégrité après coup : chaque motif `avant` de la liste
`MUTATIONS` doit être présent dans son fichier.

    python3 mutations_sonde_chaine_arome.py
"""
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent

# ⛔ (02/09/2026) copie d'origine sur le disque + sha256 + purge du
# bytecode, pour TOUS les harnais — voir `model-verif/harnais.py`.
sys.path.insert(0, str(ICI))
import harnais as HARNAIS  # noqa: E402
SONDE = ICI / "sonde_chaine_arome.py"
BANC = ICI / "test_sonde_chaine_arome.py"

MUTATIONS = [
    # ── l'arrondi : la cause (a) ────────────────────────────────────
    ("l'arrondi de tuile devient le DIXIÈME — c'est-à-dire l'arrondi "
     "d'`agrume`, donc plus aucun effet : la cause (a) disparaît en "
     "silence et le reste hérite de sa part",
     '    return float(round(speed))',
     '    return float(round(speed, 1))'),

    ("l'arrondi devient un PLANCHER (`floor`) — il biaise la vitesse "
     "vers le bas au lieu de la quantifier, et surestime sa part",
     '    return float(round(speed))',
     '    return float(math.floor(speed))'),

    ("une vitesse absente devient un calme parfait (0) au lieu de "
     "rester absente",
     '    if speed is None or not S._finite(speed):\n        return None',
     '    if speed is None or not S._finite(speed):\n        return 0.0'),

    ("l'arrondi est appliqué aux vitesses d'`arome_r2` au lieu de celles "
     "d'`agrume` — il est alors une identité (r2 est déjà entier) et "
     "toute la part du nœud bascule dans l'arrondi",
     '    s_q_i = [arrondi_tuile(v) for v in s_ag_i]',
     '    s_q_i = [arrondi_tuile(v) for v in s_r2_i]'),

    # ── le nœud : la cause (b) ──────────────────────────────────────
    ("le nœud se calcule en flottants (`round(lat/maille)*maille`) — "
     "45,02 devient 45,019999999999996 et deux nœuds identiques "
     "cessent de se comparer égaux",
     '    pas = round(1.0 / maille)\n'
     '    return (round(lat * pas) / pas, round(lon * pas) / pas)',
     '    return (round(lat / maille) * maille, round(lon / maille) * maille)'),

    ("le nœud est TRONQUÉ au lieu d'être arrondi — on désigne "
     "systématiquement le nœud du sud-ouest, jamais le plus proche",
     '    pas = round(1.0 / maille)\n'
     '    return (round(lat * pas) / pas, round(lon * pas) / pas)',
     '    pas = round(1.0 / maille)\n'
     '    return (int(lat * pas) / pas, int(lon * pas) / pas)'),

    ("la tolérance tombe à zéro : le centième de km archivé suffit à "
     "déclarer un nœud différent, et TOUTES les balises le deviennent",
     'TOL_NOEUD_KM = 0.011',
     'TOL_NOEUD_KM = 0.0'),

    ("l'écart de nœud rend la DISTANCE archivée au lieu de la "
     "différence — un chiffre plausible qui ne dit plus rien du nœud",
     '    return (ecart > TOL_NOEUD_KM, ecart, float(d_arch), d_theo)',
     '    return (ecart > TOL_NOEUD_KM, float(d_arch), float(d_arch), d_theo)'),

    # ── la décomposition elle-même ──────────────────────────────────
    ("la part des heures change de SIGNE — elle sommerait encore, à un "
     "détail près : l'identité, qui est justement ce qu'on contrôle",
     '            p_heures = a_int - a_tout\n'
     '            p_arrondi = q_int - a_int',
     '            p_heures = a_tout - a_int\n'
     '            p_arrondi = q_int - a_int'),

    ("la part de l'arrondi se compare à la journée ENTIÈRE au lieu des "
     "heures communes — elle avale la part des heures",
     '            p_heures = a_int - a_tout\n'
     '            p_arrondi = q_int - a_int',
     '            p_heures = a_int - a_tout\n'
     '            p_arrondi = q_int - a_tout'),

    ("le reste part de l'agrume BRUT au lieu de l'agrume arrondi — il "
     "recompte l'arrondi une seconde fois",
     '        p_reste = r_int - q_int',
     '        p_reste = r_int - a_int'),

    # ── les heures : la cause (c) ───────────────────────────────────
    ("les heures communes ne vérifient plus qu'`arome_r2` a une valeur "
     "— les trous de 01/02/22/23 comptent comme des heures partagées",
     '             and s_ag[i] is not None and s_r2[par_heure_r2[t]] is not None]',
     '             and s_ag[i] is not None]'),

    ("la journée notée déborde d'une heure (`<=` au lieu de `<`) — 25 "
     "heures, dont une qui appartient au lendemain",
     '           if day_start_ms <= t < day_start_ms + DAY_MS]',
     '           if day_start_ms <= t <= day_start_ms + DAY_MS]'),

    ("le plancher de 6 heures saute : une balise-jour d'une seule heure "
     "entre dans la décomposition avec le même poids que les autres",
     '    if len(pairs) < min_heures:\n        return None',
     '    if len(pairs) < 0:\n        return None',),

    # ── l'écart de chaîne, et l'IC ──────────────────────────────────
    ("l'écart d'arrondi se calcule avec la direction d'`arome_r2` au "
     "lieu de celle d'`agrume` — il n'isole plus l'arrondi, il mesure "
     "les deux causes ensemble",
     '        uq, vq = S.to_uv(arrondi_tuile(sa), da)',
     '        uq, vq = S.to_uv(arrondi_tuile(sa), dr)'),

    ("l'IC accepte de se prononcer sur 2 jours — exactement ce que le "
     "lot L1 a tranché contre l'audit du 26/08",
     '    return INF.block_ci_by_day(valeurs_par_jour)',
     '    return INF.block_ci_by_day(valeurs_par_jour, min_days=2)'),

    ("la série journalière ne voyage plus : il ne reste que le chiffre "
     "poolé, celui-là même dont le banc a montré qu'il peut valoir 0 "
     "quand chaque jour dit le contraire",
     '        "par_jour": {j: {"n": len(v), "mediane": S.median(v),\n'
     '                         "moyenne": sum(v) / len(v) if v else None}\n'
     '                     for j, v in sorted(par_jour.items())},',
     '        "par_jour": {},'),

    # ── le nœud RÉELLEMENT lu par chacune des deux chaînes ──────────
    ("`noeuds_lus` compare `arome_r2` à ELLE-MÊME au lieu de comparer "
     "les deux chaînes — une balise dont les référentiels divergent "
     "passe pour lue au même nœud",
     '    if n_ag != n_r2:\n        return (False, d_coord, "coordonnee")',
     '    if False:\n        return (False, d_coord, "coordonnee")'),

    ("le nœud d'`agrume` est calculé depuis la coordonnée d'`arome_r2` "
     "— les deux chaînes lisent alors toujours le même nœud, par "
     "construction",
     '    n_ag = noeud_le_plus_proche(row_ag["lat"], row_ag["lon"], maille)',
     '    n_ag = noeud_le_plus_proche(row_r2["lat"], row_r2["lon"], maille)'),

    ("tout écart de coordonnée condamne le nœud, même quand il ne "
     "franchit pas le demi-pas — la cause « coordonnée » est alors "
     "surestimée sans qu'aucun total ne bouge",
     '    if n_ag != n_r2:\n        return (False, d_coord, "coordonnee")',
     '    if d_coord > 0.0:\n        return (False, d_coord, "coordonnee")'),

    ("la TUILE cesse de primer : un bord de tuile est rangé sous "
     "« coordonnée », c'est-à-dire imputé au référentiel au lieu de la "
     "chaîne",
     '    if tuile is not None and tuile[0]:\n'
     '        return (False, d_coord, "tuile")',
     '    if False:\n        return (False, d_coord, "tuile")'),

    ("la PART se calcule sur la MÉDIANE au lieu de la moyenne — elle "
     "reste parfaitement lisible et ne fait plus 100 %",
     "    part = (\"—\" if not total or t.get(\"moyenne\") is None\n"
     "            else f\"{100 * t['moyenne'] / total:5.1f} %\")",
     "    part = (\"—\" if not total or t[\"mediane\"] is None\n"
     "            else f\"{100 * t['mediane'] / total:5.1f} %\")"),

    ("le terme ne publie plus sa MOYENNE — il ne reste que la médiane, "
     "et l'additivité de la décomposition n'est plus vérifiable",
     '        "moyenne": (sum(vals) / len(vals)) if vals else None,',
     '        "moyenne": None,'),
]


def joue(debut: int = 1, fin: int = len(MUTATIONS)) -> int:
    rouges = 0
    origine = HARNAIS.garder(SONDE)
    for i, (nom, avant, apres) in enumerate(MUTATIONS, 1):
        if not (debut <= i <= fin):
            continue
        if avant not in origine:
            print(f"  ⛔ {i:>2}. {nom}\n       MOTIF INTROUVABLE — la "
                  f"mutation n'a rien muté, donc elle n'a rien prouvé.")
            rouges += 1
            continue
        try:
            SONDE.write_text(origine.replace(avant, apres, 1),
                             encoding="utf-8")
            r = subprocess.run([sys.executable, str(BANC)],
                               capture_output=True, text=True, cwd=ICI,
                               env=HARNAIS.env_banc(ICI))
            if r.returncode == 0:
                print(f"  ❌ {i:>2}. {nom}\n       LE BANC RESTE VERT — il "
                      f"ne tient pas cette propriété.")
                rouges += 1
            else:
                l = [x.strip() for x in r.stdout.splitlines()
                     if x.strip().startswith("❌")]
                if not l:
                    l = [x.strip() for x in r.stderr.splitlines()[-2:]]
                print(f"  ✅ {i:>2}. {nom}\n       {l[0] if l else 'banc rouge'}"
                      + (f" (+{len(l) - 1} autres)" if len(l) > 1 else ""))
        finally:
            HARNAIS.rendre(SONDE, origine)
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations de la sonde de chaîne (lot L4) — chaque ligne doit "
          "être VERTE,\n  c'est-à-dire : le banc a bien ROUGI sur la faute.\n")
    d = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    f = int(sys.argv[2]) if len(sys.argv) > 2 else len(MUTATIONS)
    n = joue(d, f)
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} non vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
