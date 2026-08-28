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
from __future__ import annotations

import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
SCORE = ICI / "score.py"
INFER = ICI / "inference.py"
MURPHY = ICI / "murphy.py"
B_SCORE = ICI / "test_score.py"
B_INFER = ICI / "test_inference.py"
B_MURPHY = ICI / "test_murphy.py"

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

    # ══════════════════════════════════════════════════════════════
    #  VOLET (b) — la décomposition de Murphy
    # ══════════════════════════════════════════════════════════════
    ("⭐ la somme croisée Σfo est perdue : `r` tombe à zéro et tout "
     "modèle passe pour aveugle au TIMING",
     MURPHY, B_MURPHY,
     '        sfo += f * o',
     '        sfo += 0.0'),

    ("la variance est prise à n−1 (convention d'ÉCHANTILLON) alors que "
     "le MSE divise par n : l'identité de Murphy ne tient plus",
     MURPHY, B_MURPHY,
     '    var_f = max(sff / n - mf * mf, 0.0)\n'
     '    var_o = max(soo / n - mo * mo, 0.0)',
     '    var_f = max((sff - n * mf * mf) / (n - 1), 0.0)\n'
     '    var_o = max((soo - n * mo * mo) / (n - 1), 0.0)'),

    ("le biais CONDITIONNEL change de signe (`r + s_f/s_o`) — une "
     "amplitude juste devient une amplitude fausse",
     MURPHY, B_MURPHY,
     '    bc = r - (sdf / sdo)',
     '    bc = r + (sdf / sdo)'),

    ("le biais SYSTÉMATIQUE est normalisé par l'écart-type de la "
     "PRÉVISION au lieu de celui de l'observation",
     MURPHY, B_MURPHY,
     '    bs = (mf - mo) / sdo',
     '    bs = (mf - mo) / (sdf if sdf > 0 else sdo)'),

    ("`ss` cesse d'être l'identité et redevient le seul potentiel "
     "(`r²`) : les deux biais disparaissent du verdict",
     MURPHY, B_MURPHY,
     '        "ss": round(r * r - bc * bc - bs * bs, 4),',
     '        "ss": round(r * r, 4),'),

    ("⭐ `pool` MOYENNE les journées au lieu de les additionner — les "
     "sommes ne sont plus des sommes, et 30 jours pèsent comme 1",
     MURPHY, B_MURPHY,
     '        tot[0] += int(m[0])\n'
     '        for i in range(1, 6):\n            tot[i] += float(m[i])',
     '        tot[0] = int(m[0])\n'
     '        for i in range(1, 6):\n            tot[i] = float(m[i])'),

    ("⭐⭐ les moments sont additionnés ENTRE BALISES (la clé de "
     "regroupement perd l'unité) : la variance inter-sites est prise "
     "pour du talent",
     MURPHY, B_MURPHY,
     '        b = acc[(d["unit"], d["model"], d["lead_h"])]',
     '        b = acc[("*", d["model"], d["lead_h"])]'),

    ("une balise sous le plancher DISPARAÎT au lieu d'être publiée avec "
     "son motif — une ligne absente et une ligne à zéro se lisent "
     "pareil",
     MURPHY, B_MURPHY,
     '            dec = {**dec, "r": None, "r2": None, "bc": None,'
     ' "bs": None,\n'
     '                   "ss": None, "sd_ratio": None,'
     ' "reason": "too_few_pairs"}',
     '            continue'),

    ("des observations SANS variance rendent un `ss` fabriqué au lieu "
     "de `flat_obs` : une journée sans vent se lit comme un verdict",
     MURPHY, B_MURPHY,
     '    if sdo <= 0.0:\n        return {**vide, "n": n,'
     ' "mean_f": round(mf, 4),',
     '    if False:\n        return {**vide, "n": n,'
     ' "mean_f": round(mf, 4),'),

    ("une prévision CONSTANTE fait disparaître la ligne (`r = None`) "
     "alors que sa décomposition est parfaitement définie",
     MURPHY, B_MURPHY,
     '    r = 0.0 if sdf <= 0.0 else cov / (sdf * sdo)',
     '    r = cov / (sdf * sdo) if sdf > 0 else float("nan")'),

    ("⭐ les clés privées ne sont retirées qu'APRÈS le `if not cols` : "
     "un schéma illisible envoie `_murphy` à PostgREST",
     SCORE, B_SCORE,
     '    if any(k.startswith("_") for k in rows[0]):\n'
     '        rows = [{k: v for k, v in r.items() if not k.startswith("_")}\n'
     '                for r in rows]\n'
     '    cols = sb.columns(table)\n'
     '    if not cols:\n        return rows',
     '    cols = sb.columns(table)\n'
     '    if not cols:\n        return rows\n'
     '    if any(k.startswith("_") for k in rows[0]):\n'
     '        rows = [{k: v for k, v in r.items() if not k.startswith("_")}\n'
     '                for r in rows]'),

    ("`REPLAY_FORMULA` reste à 4 : un cache d'avant le lot est réutilisé "
     "et la fenêtre de Murphy mélange des journées qui portent les six "
     "sommes et des journées qui ne les portent pas",
     SCORE, B_SCORE,
     'REPLAY_FORMULA = 5',
     'REPLAY_FORMULA = 4'),

    # ══════════════════════════════════════════════════════════════
    #  VOLET (c) — la référence combinée (Murphy 1992)
    # ══════════════════════════════════════════════════════════════
    ("⭐⭐ la FORCE du mélange devient la norme du mélange (u, v) — une "
     "référence artificiellement faible, donc un skill "
     "artificiellement bon",
     INFER, B_INFER,
     '    force = k * sp + (1.0 - k) * sc',
     '    _uu = k * S.to_uv(sp, dp if dp is not None else 0.0)[0] + '
     '(1.0 - k) * S.to_uv(sc, dc if dc is not None else 0.0)[0]\n'
     '    _vv = k * S.to_uv(sp, dp if dp is not None else 0.0)[1] + '
     '(1.0 - k) * S.to_uv(sc, dc if dc is not None else 0.0)[1]\n'
     '    force = math.hypot(_uu, _vv)'),

    ("le CAP du mélange est moyenné à plat (arithmétique) au lieu du "
     "mélange circulaire",
     INFER, B_INFER,
     '    up, vp = S.to_uv(1.0, dp)\n    uc, vc = S.to_uv(1.0, dc)',
     '    return force, k * dp + (1.0 - k) * dc\n'
     '    up, vp = S.to_uv(1.0, dp)\n    uc, vc = S.to_uv(1.0, dc)'),

    ("⭐ les poids sont ÉCHANGÉS : `k` porte sur la climatologie et "
     "`1−k` sur la persistance — les deux bornes du mélange s'inversent",
     INFER, B_INFER,
     '    force = k * sp + (1.0 - k) * sc',
     '    force = (1.0 - k) * sp + k * sc'),

    ("⭐⭐ le ρ se mesure sur la force BRUTE, sans retirer la "
     "climatologie : le cycle diurne est pris pour de la persistance et "
     "`k` file vers 1 partout",
     INFER, B_INFER,
     '            anomalies[(day, hod)] = sum(vals) / len(vals) - ref[0]',
     '            anomalies[(day, hod)] = sum(vals) / len(vals)'),

    ("des journées NON consécutives s'apparient à « 24 h » : un trou "
     "d'archive fait comparer lundi à vendredi",
     INFER, B_INFER,
     '        if not _jours_consecutifs(veille, day):\n            continue',
     '        if False:\n            continue'),

    ("le poids n'est plus borné : une anti-persistance devient une "
     "référence publiée",
     INFER, B_INFER,
     '    if rho < 0.0:\n        return 0.0, True',
     '    if rho < -99.0:\n        return 0.0, True'),

    ("le mélange se contente de la persistance quand la climatologie "
     "manque à cette heure-là — la référence change de définition en "
     "cours de journée, sans le dire",
     INFER, B_INFER,
     '        if c is None or not S._finite(c[0]):\n            continue',
     '        if c is None or not S._finite(c[0]):\n'
     '            c = (ref_s, ref_d, 0)'),

    ("⭐ `skill_comb` de la case est calculé contre `mse_model` (la "
     "population « persistance ») au lieu de son témoin apparié "
     "`mse_model_comb`",
     SCORE, B_SCORE,
     '                b["mse_cb"].append((d["mse_model_comb"], d["mse_comb"]))',
     '                b["mse_cb"].append((d["mse_model"], d["mse_comb"]))'),

    ("une balise sans `k` reçoit un poids par DÉFAUT au lieu de rester "
     "muette — un poids inventé sur une référence publiée",
     SCORE, B_SCORE,
     '            if clim and poids_comb:\n'
     '                c = clim.get(key)\n'
     '                kk = poids_comb.get(key)',
     '            if clim:\n'
     '                c = clim.get(key)\n'
     '                kk = (poids_comb or {}).get(key, 0.5)'),

    ("le cache de climatologie garde son nom d'AVANT le lot : relu, il "
     "rend une climatologie complète et AUCUN poids, sans que rien ne "
     "le dise",
     SCORE, B_SCORE,
     'f"clim_{day:%Y-%m-%d}_{n_days}_v2.json.gz"',
     'f"clim_{day:%Y-%m-%d}_{n_days}.json.gz"'),

    ("le poids n'est pas ÉCRIT dans le cache : la première nuit le "
     "calcule, toutes les suivantes le perdent",
     SCORE, B_SCORE,
     '             "k": poids},',
     '             "k": {}},'),
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
