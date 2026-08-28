#!/usr/bin/env python3
"""Rejoue les bancs contre des variantes CASSÉES du lot L9
(compagnon WMO du score · décomposition de Murphy · référence combinée).

⛔ Un banc vert ne prouve rien tant qu'on n'a pas vu ce qui le fait
rougir (même discipline que `mutations_fdr.py`, `mutations_duel.py`).
Et la faute qu'on craint ici n'est jamais le plantage : c'est un
compagnon plausible et faux — un biais de cap moyenné à plat qui
annonce « modèle bien calé » sur un modèle à contresens, un r² de
Murphy qui compte l'amplitude dans le timing, une référence combinée
qui n'est en réalité que la persistance. Aucune de ces fautes ne
rougit toute seule, et toutes se publient.

    python3 mutations_l9.py            # tout
    python3 mutations_l9.py 1 6        # par tranches (voir `joue`)
"""
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
SCORE = ICI / "score.py"
INFER = ICI / "inference.py"
B_SCORE = ICI / "test_score.py"
B_INFER = ICI / "test_inference.py"

MUTATIONS = [
    # ══════════════════════════════════════════════════════════════
    #  VOLET (a) — le compagnon WMO : biais de vitesse et de cap
    # ══════════════════════════════════════════════════════════════
    ("⭐ le cap est moyenné À PLAT (moyenne arithmétique) au lieu de la "
     "moyenne circulaire — un modèle à contresens est annoncé « bien "
     "calé »",
     SCORE, B_SCORE,
     '            "bias_dir_deg": _r(INF.circular_mean_deg(b["bias_dir"]), 1),',
     '            "bias_dir_deg": _r(S.median(b["bias_dir"]), 1),'),

    ("la moyenne circulaire INVENTE 0° quand la résultante est nulle, "
     "au lieu de se taire",
     INFER, B_INFER,
     '    if math.hypot(sx, sy) < 1e-12 * n:\n        return None',
     '    if math.hypot(sx, sy) < 1e-12 * n:\n        return 0.0'),

    ("la moyenne circulaire oublie le sinus (elle ne lit plus qu'un "
     "cosinus, donc ne distingue plus la gauche de la droite)",
     INFER, B_INFER,
     '        sy += math.sin(r)',
     '        sy += 0.0'),

    ("le demi-tour sort à −180 au lieu de +180 : un même écart porte "
     "deux noms selon l'ordre des balises",
     INFER, B_INFER,
     '    return 180.0 if ang <= -180.0 else ang',
     '    return ang'),

    ("⭐ le biais de vitesse de la case devient la MOYENNE des "
     "balise-jours — une seule balise déréglée impose alors le chiffre "
     "publié pour toute la case",
     SCORE, B_SCORE,
     '            "bias_ratio": _r(S.median(b["bias_ratio"]), 3),',
     '            "bias_ratio": _r(sum(b["bias_ratio"]) / len(b["bias_ratio"])\n'
     '                             if b["bias_ratio"] else None, 3),'),

    ("`n_bias_dir` compte les OCCURRENCES de la case au lieu des "
     "balise-jours qui portaient vraiment un cap — le dénominateur "
     "ment, et c'est pire que pas de dénominateur",
     SCORE, B_SCORE,
     '            "n_bias_dir": len(b["bias_dir"]),',
     '            "n_bias_dir": len(values),'),

    ("le garde `_finite` saute à la collecte du cap : les `None` "
     "entrent dans la liste et gonflent `n_bias_dir`",
     SCORE, B_SCORE,
     '            if S._finite(d.get("bias_dir_deg")):\n'
     '                b["bias_dir"].append(d["bias_dir_deg"])',
     '            b["bias_dir"].append(d.get("bias_dir_deg"))'),

    ("le compagnon est ramassé AVANT les exclusions de la case "
     "(doublon L17, `basin_uncertain`, `position_suspecte`) : le biais "
     "publié porte sur des balise-jours que le score a refusés",
     SCORE, B_SCORE,
     '    for d in units:\n        z = zone_of.get(d["unit"])\n'
     '        if z is None or z.get("basin_uncertain"):\n            continue',
     '    for d in units:\n        z = zone_of.get(d["unit"])\n'
     '        if z is not None and not z.get("basin_uncertain"):\n'
     '            pass\n'
     '        elif z is not None:\n'
     '            for _zid, _lvl in fallback_chain(z):\n'
     '                if S._finite(d.get("bias_ratio")):\n'
     '                    acc[(_zid, d["model"], d["lead_h"], _lvl)]["bias_ratio"]\\\n'
     '                        .append(d["bias_ratio"])\n'
     '            continue\n'
     '        if z is None or z.get("basin_uncertain"):\n            continue'),

    ("`n_bias_dir` sort du fichier léger : le cap voyage sans son "
     "dénominateur (la faute exacte que `n_comparable` a nommée au L3)",
     SCORE, B_SCORE,
     '    "bias_ratio", "bias_dir_deg", "n_bias_dir",',
     '    "bias_ratio", "bias_dir_deg",'),

    ("`_pour_la_base` retombe sur la déduction d'avant : les colonnes "
     "du L9 manquantes envoient Yann rejouer `step40`",
     SCORE, B_SCORE,
     '    if set(absentes) & _L9:\n'
     '        fichier = "supabase_step57_lot_l9_compagnons.sql"\n'
     '    elif set(absentes) & _L3:',
     '    if False:\n'
     '        fichier = "supabase_step57_lot_l9_compagnons.sql"\n'
     '    elif set(absentes) & _L3:'),
]


def joue(debut: int = 1, fin: int | None = None) -> int:
    """⚠️ `debut`/`fin` NE SONT PAS UN CONFORT. Chaque mutation restaure
    son fichier en `finally` — mais un processus TUÉ (délai d'outil,
    pont Cowork qui tombe) ne passe jamais par son `finally` et laisse
    le fichier MUTÉ sur le disque (vécu deux fois le 27/08 au lot L3).
    Jouer par tranches courtes dans un shell qui a le temps de finir,
    puis contrôler que chaque motif `avant` est de retour.
    """
    fin = len(MUTATIONS) if fin is None else fin
    rouges = 0
    for i, (nom, fichier, banc, avant, apres) in enumerate(MUTATIONS, 1):
        if not (debut <= i <= fin):
            continue
        origine = fichier.read_text(encoding="utf-8")
        if avant not in origine:
            print(f"  ⛔ {i:>2}. {nom}\n       MOTIF INTROUVABLE dans "
                  f"{fichier.name} — la mutation n'a rien muté, donc elle "
                  f"n'a rien prouvé. (Le code a bougé : réécrire ce motif.)")
            rouges += 1
            continue
        try:
            fichier.write_text(origine.replace(avant, apres, 1),
                               encoding="utf-8")
            r = subprocess.run([sys.executable, str(banc)],
                               capture_output=True, text=True, cwd=ICI)
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
                      f"{lignes[0] if lignes else 'banc rouge'}"
                      + (f" (+{len(lignes) - 1} autres)"
                         if len(lignes) > 1 else ""))
        finally:
            fichier.write_text(origine, encoding="utf-8")
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations du lot L9 (compagnons du score) — chaque ligne "
          "doit être VERTE,\n  c'est-à-dire : le banc a bien ROUGI sur la "
          "faute.\n")
    debut = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    fin = int(sys.argv[2]) if len(sys.argv) > 2 else len(MUTATIONS)
    n = joue(debut, fin)
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
