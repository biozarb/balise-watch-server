#!/usr/bin/env python3
"""Rejoue les bancs contre des variantes CASSÉES du lot L3
(multiplicité BH-FDR, p-valeur bootstrap, gap apparié, `n_comparable`).

⛔ Un banc vert ne prouve rien tant qu'on n'a pas vu ce qui le fait
rougir (même discipline que `mutations_duel.py` et
`mutations_duplicate_chain.py`). Et la faute qu'on craint ici n'est
jamais le plantage : c'est une correction de multiplicité qui a l'air
de tourner — un message dans le log, un compte plausible — et qui ne
corrige rien, parce que la famille est trop petite, parce que le seuil
est constant, ou parce que la p-valeur ne dit pas ce qu'elle prétend.
Aucune de ces fautes ne rougit toute seule.

Deux bancs sont concernés : `test_inference.py` (la statistique) et
`test_score.py` (l'intégration). Chaque mutation nomme le sien.

Restauration en `finally` : les fichiers reviennent à leur état
d'origine même si l'on interrompt.

    python3 mutations_fdr.py
"""
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent

# ⛔ (02/09/2026) copie d'origine sur le disque + sha256 + purge du
# bytecode, pour TOUS les harnais — voir `model-verif/harnais.py`.
sys.path.insert(0, str(ICI))
import harnais as HARNAIS  # noqa: E402
SCORE = ICI / "score.py"
INFER = ICI / "inference.py"
B_SCORE = ICI / "test_score.py"
B_INFER = ICI / "test_inference.py"

MUTATIONS = [
    # ── la p-valeur bootstrap ───────────────────────────────────────
    ("la p-valeur devient UNILATÉRALE (le facteur 2 saute) — deux fois "
     "trop de cases paraissent extrêmes",
     INFER, B_INFER,
     '    return min(1.0, 2.0 * (1 + min(n_neg, n_pos)) / (B + 1))',
     '    return min(1.0, 1.0 * (1 + min(n_neg, n_pos)) / (B + 1))'),

    ("la correction `+1` disparaît — `p = 0` redevient possible, et une "
     "case passe pour infiniment improbable alors qu'on a seulement "
     "épuisé la résolution du tirage",
     INFER, B_INFER,
     '    return min(1.0, 2.0 * (1 + min(n_neg, n_pos)) / (B + 1))',
     '    return min(1.0, 2.0 * (min(n_neg, n_pos)) / B)'),

    ("on lit le mauvais côté de la distribution (`max` au lieu de "
     "`min`) — les cas francs deviennent les moins significatifs",
     INFER, B_INFER,
     '    return min(1.0, 2.0 * (1 + min(n_neg, n_pos)) / (B + 1))',
     '    return min(1.0, 2.0 * (1 + max(n_neg, n_pos)) / (B + 1))'),

    ("la p-valeur et l'IC ne sortent plus du MÊME tirage : `block_ci_by_day` "
     "ne rend plus de p du tout",
     INFER, B_INFER,
     '        p_value=_p_bilaterale(meds))',
     '        p_value=None)'),

    # ── Benjamini-Hochberg ──────────────────────────────────────────
    ("BH devient une SUITE DE TESTS : seuil constant `alpha`, sans le "
     "rang — c'est-à-dire aucune correction, avec le nom d'une",
     INFER, B_INFER,
     '        if p_values[i] <= rang * alpha / m:\n            k = rang',
     '        if p_values[i] <= alpha:\n            k = rang'),

    ("BH devient STEP-DOWN : on s'arrête au premier échec au lieu de "
     "retenir le plus grand k — les p-valeurs sous le seuil retenu "
     "sont perdues",
     INFER, B_INFER,
     '        if p_values[i] <= rang * alpha / m:\n            k = rang',
     '        if p_values[i] > rang * alpha / m:\n            break\n'
     '        k = rang'),

    ("le seuil oublie de diviser par la taille de la famille "
     "(`rang * alpha` au lieu de `rang * alpha / m`)",
     INFER, B_INFER,
     '        if p_values[i] <= rang * alpha / m:',
     '        if p_values[i] <= rang * alpha:'),

    # ── la famille : le point le plus facile à rater ────────────────
    ("⭐ LA FAMILLE SE RÉDUIT AUX CASES PUBLIÉES — l'erreur classique, "
     "celle qui donne l'illusion d'avoir corrigé",
     SCORE, B_SCORE,
     '            if p is None:\n                continue          # aucun test joué ici : hors famille',
     '            if p is None or not any(l.get(cle_reason) == "ok"\n'
     '                                    for l in lignes):\n                continue'),

    ("la case n'est plus (zone, lead, fenêtre, régime, échelon) mais "
     "(zone, lead) — le glissant et le régime se confondent, `m` fond "
     "de moitié",
     SCORE, B_SCORE,
     '    return (r.get("zone_id"), r.get("lead_h"), r.get("window_kind"),\n'
     '            r.get("regime"), r.get("agg_level"))',
     '    return (r.get("zone_id"), r.get("lead_h"))'),

    # ── la rétrogradation elle-même ─────────────────────────────────
    ("la rétrogradation balaie TOUTES les lignes de la case — le motif "
     "`duplicate_chain` du lot L2 est effacé au passage",
     SCORE, B_SCORE,
     '                if l.get(cle_reason) == "ok":\n'
     '                    l[cle_reason] = RANK_REASON_FDR\n'
     '                    l[cle_rank] = None',
     '                l[cle_reason] = RANK_REASON_FDR\n'
     '                l[cle_rank] = None'),

    ("le rang est retiré mais la RAISON reste « ok » — une purge "
     "silencieuse, exactement ce que le lot interdit",
     SCORE, B_SCORE,
     '                    l[cle_reason] = RANK_REASON_FDR\n'
     '                    l[cle_rank] = None',
     '                    l[cle_rank] = None'),

    ("le corrigé écrit son verdict dans `rank_reason` (la colonne du "
     "brut) au lieu de `rank_reason_corr` — les deux familles se "
     "mélangent à l'écriture",
     SCORE, B_SCORE,
     '            ("corrige", FDR_P_CORR, "rank_corr", "rank_reason_corr")):',
     '            ("corrige", FDR_P_CORR, "rank_corr", "rank_reason")):'),

    ("les clés privées de transport ne sont plus retirées — elles "
     "partent dans le JSON publié",
     SCORE, B_SCORE,
     '    for r in rows:\n        r.pop(FDR_P_BRUT, None)\n        r.pop(FDR_P_CORR, None)\n    return rapport',
     '    return rapport'),

    ("`_apply_rank` ne dépose plus la p-valeur — la correction tourne "
     "chaque nuit sur une famille VIDE, en silence",
     SCORE, B_SCORE,
     '        for r in admis:\n            r[FDR_P_BRUT] = p_case',
     '        _ = p_case   # mutation L3-14 : la p-valeur n\'est plus déposée'),

    # ── le gap apparié (objectif 2) ─────────────────────────────────
    ("⭐ le gap pratique repart sur les populations PROPRES — le défaut "
     "mesuré de l'audit §2.5, restauré",
     INFER, B_INFER,
     '    med_a = _med_appariee(rows_a)\n    med_b = _med_appariee(rows_b)',
     '    med_a = S.median([r.get(value_key) for r in rows_a])\n'
     '    med_b = S.median([r.get(value_key) for r in rows_b])'),

    ("un seul des deux côtés est apparié — l'asymétrie qui ne se voit "
     "pas à la lecture",
     INFER, B_INFER,
     '    med_b = _med_appariee(rows_b)',
     '    med_b = S.median([r.get(value_key) for r in rows_b])'),

    ("`n_comparable` compte les lignes de A au lieu des balise-jours "
     "communs",
     INFER, B_INFER,
     '    n_comparable = len(communs)',
     '    n_comparable = len(rows_a)'),

    # ── n_comparable dans la ligne de score ─────────────────────────
    ("`n_comparable` devient une UNION au lieu d'une intersection — il "
     "annonce une population commune que le test n'a jamais eue",
     SCORE, B_SCORE,
     '        noyau = j if noyau is None else (noyau & j)',
     '        noyau = j if noyau is None else (noyau | j)'),

    ("`n_comparable` compte les lignes présentes, sans exiger une "
     "`err_vec_med` finie — il compte des balise-jours vides",
     SCORE, B_SCORE,
     '    return {(r.get("day"), r.get("unit")) for r in (rows_du_modele or ())\n'
     '            if S._finite(r.get("err_vec_med"))}',
     '    return {(r.get("day"), r.get("unit")) for r in (rows_du_modele or ())}'),
]


def joue(debut: int = 1, fin: int = len(MUTATIONS)) -> int:
    """⚠️ `debut`/`fin` NE SONT PAS UN CONFORT. Chaque mutation restaure
    son fichier en `finally` — mais un processus TUÉ (délai d'outil,
    pont Cowork qui tombe) ne passe jamais par son `finally`, et laisse
    le fichier MUTÉ sur le disque. Vécu deux fois le 27/08 : deux
    mutations sont restées appliquées, et les bancs suivants
    rougissaient sans qu'on sache pourquoi. Jouer par tranches courtes
    dans un shell qui a le temps de finir, et contrôler l'intégrité
    après (chaque motif `avant` doit être présent), est la seule façon
    sûre depuis une session Cowork.
    """
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
                      f"{lignes[0] if lignes else 'banc rouge'}"
                      + (f" (+{len(lignes) - 1} autres)"
                         if len(lignes) > 1 else ""))
        finally:
            HARNAIS.rendre(fichier, origine)
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations du lot L3 (multiplicité, p-valeur, gap apparié) — "
          "chaque ligne doit être VERTE,\n  c'est-à-dire : le banc a bien "
          "ROUGI sur la faute.\n")
    debut = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    fin = int(sys.argv[2]) if len(sys.argv) > 2 else len(MUTATIONS)
    n = joue(debut, fin)
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
