#!/usr/bin/env python3
"""Rejoue les bancs contre des variantes CASSÉES du lot L11
(la classe au quart d'heure : `agrume_quart.py`, `scoring.demi_fenetre`,
`score.plancher_du_pas`).

⛔ UN BANC VERT NE PROUVE RIEN TANT QU'ON N'A PAS VU CE QUI LE FAIT
ROUGIR — et la faute centrale de CE lot-ci est encore plus discrète que
celle du L10. Garder la demi-fenêtre de ±20 min sur un pas de 15 min ne
casse rien, ne lève rien, et ne déplace presque pas les erreurs : elle
compte simplement chaque relevé dans TROIS points au lieu d'un. Seuls
les `n_obs` gonflent — et personne ne relit un `n`. C'est la mutation
nº 1, et c'est pour elle que ce fichier existe.

⚠️ Le harnais (restauration en `finally`, ménage du `__pycache__`) est
celui du L10, IMPORTÉ tel quel : le piège du bytecode trouvé le 30/08
— une mutation de même longueur restaurée dans la même seconde, et
Python recharge le `.pyc` MUTÉ — a coûté trois lignes vertes qui ne
prouvaient rien. On ne réécrit pas un harnais qui a déjà payé.

    python3 mutations_pas_15min.py
"""
import os
import pathlib
import shutil
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent

# ⛔ (02/09/2026) copie d'origine sur le disque + sha256 + purge du
# bytecode, pour TOUS les harnais — voir `model-verif/harnais.py`.
sys.path.insert(0, str(ICI))
import harnais as HARNAIS  # noqa: E402
SCORE = ICI / "score.py"
SCORING = ICI / "scoring.py"
QUART = ICI / "agrume_quart.py"

BANC_QUART = "test_agrume_quart.py"
BANC_SCORE = "test_score.py"

MUTATIONS = [
    # ── ⛔⛔ LA FAUTE CENTRALE : l'indépendance du test apparié ───────
    ("⛔⛔ la demi-fenêtre de l'HEURE RONDE est gardée sur un pas de "
     "15 min — chaque relevé compté dans TROIS points, les `n_obs` "
     "publiés faux, et aucun chiffre qui ait l'air anormal",
     SCORE, BANC_QUART,
     '            pairs = S.pair_series(sub_t, sub_s, sub_d, obs,\n'
     '                                  S.demi_fenetre(pas_s))',
     '            pairs = S.pair_series(sub_t, sub_s, sub_d, obs)'),

    ("⛔ la table met ±20 min sur le pas de 15 min — l'invariant "
     "2×demi < pas tombe, et avec lui la licéité du test apparié",
     SCORING, BANC_QUART,
     '    900: 7 * 60 * 1000,',
     '    900: 20 * 60 * 1000,'),

    ("la demi-fenêtre d'un pas INCONNU n'est plus bornée par "
     "l'invariant — une classe neuve casserait l'indépendance en silence",
     SCORING, BANC_QUART,
     '    return max(0, min(OBS_HALF_WINDOW_MS, (int(step_s) * 1000) // 2 - 60_000))',
     '    return OBS_HALF_WINDOW_MS'),

    ("⛔ NON-RÉGRESSION : l'heure ronde perd ses ±20 min — toutes les "
     "séries existantes changent de population sans qu'une ligne ne le "
     "dise",
     SCORING, BANC_QUART,
     '    3600: OBS_HALF_WINDOW_MS,',
     '    3600: 15 * 60 * 1000,'),

    # ── le plancher ─────────────────────────────────────────────────
    ("le plancher du pas est ignoré : 6 points sur 15 suffisent, "
     "c'est 2,5 fois plus laxiste que l'heure ronde et rien ne le dit",
     SCORE, BANC_QUART,
     '            if len(pairs) < plancher_du_pas(pas_s):',
     '            if len(pairs) < MIN_HOURS_DAILY:'),

    ("le plancher du quart d'heure retombe à 6 — les 39 balises aemet, "
     "qui ne servent AUCUN quart, cesseraient d'être écartées par la "
     "règle",
     SCORE, BANC_QUART,
     'PLANCHER_PAR_PAS = {3600: MIN_HOURS_DAILY, 900: 13}',
     'PLANCHER_PAR_PAS = {3600: MIN_HOURS_DAILY, 900: 6}'),

    ("⛔ NON-RÉGRESSION : l'heure ronde perd son plancher de 6",
     SCORE, BANC_QUART,
     'PLANCHER_PAR_PAS = {3600: MIN_HOURS_DAILY, 900: 13}',
     'PLANCHER_PAR_PAS = {3600: 3, 900: 13}'),

    # ── le périmètre ────────────────────────────────────────────────
    ("⛔ les HEURES RONDES entrent dans la classe du quart d'heure — "
     "le même instant noté DEUX fois sur les mêmes observations, et le "
     "`m` du BH-FDR gonflé d'autant",
     QUART, BANC_QUART,
     '        if t.minute != 0:\n            out.append(t)',
     '        out.append(t)'),

    ("la plage déborde d'une heure celle de la classe horaire — les "
     "deux classes ne parlent plus du même intervalle",
     QUART, BANC_QUART,
     '    while t < rondes[-1]:',
     '    while t < rondes[-1] + timedelta(hours=1):'),

    # ── ⛔⛔ UNE SEULE POPULATION (la leçon du L9(c)) ────────────────
    ("⛔⛔ le TÉMOIN garde un quart que PI n'a pas — trois erreurs "
     "comparées sur trois populations d'heures différentes, exactement "
     "la faute que le lot L9(c) a passé trois nuits à instruire",
     QUART, BANC_QUART,
     '            if not all(np.isfinite(x) for x in\n'
     '                       (u_b, v_b, u_a20, v_a20, u_pi, v_pi)):',
     '            if not all(np.isfinite(x) for x in (u_b, v_b)):'),

    ("le compte publié par la ligne dit les quarts VISÉS et non les "
     "quarts SERVIS — une ligne à 3 points sur 15 se lit comme pleine",
     QUART, BANC_QUART,
     '"agrume_quart_quarts": len(servables),',
     '"agrume_quart_quarts": len(quarts),'),

    ("PI horaire est étiré sur les quarts par le plus proche voisin — "
     "une classe « au quart d'heure » sans un seul chiffre natif dedans, "
     "qui compare deux interpolations du même champ",
     QUART, BANC_QUART,
     '        if m_pi not in pi_min:\n'
     '            # PI ne porte pas ce quart : par la règle d\'UNE SEULE\n'
     '            # POPULATION, il ne sera servi dans AUCUNE des trois.\n'
     '            n_hors_couverture += 1\n'
     '            continue\n'
     '        i_min = pi_min.index(m_pi)',
     '        i_min = min(range(len(pi_min)),\n'
     '                    key=lambda z: abs(pi_min[z] - m_pi))'),

    # ── la construction ─────────────────────────────────────────────
    ("l'AROME n'est plus interpolé mais pris à l'heure ronde la plus "
     "proche — un escalier servi sous le nom d'une prévision au quart "
     "d'heure",
     QUART, BANC_QUART,
     '    return arome_interpole(bloc, steps_h, minutes_arome)',
     '    return bloc[..., int(round(minutes_arome / 60.0))]'),

    ("le cisaillement disparaît : Δ(20 m) est servi tel quel au 10 m, "
     "une correction calibrée pour un vent ~30 % plus fort",
     QUART, BANC_QUART,
     '    kz = facteur_cisaillement(NIVEAU_DELTA_APPLIQUE)',
     '    kz = 1.0'),

    ("Δ est mesuré dans la maille de la BASE au lieu de la sienne — "
     "l'écart de résolution entre 0,01° et 0,025° entre dans Δ",
     QUART, BANC_QUART,
     '    bloc_ar, i_niv_ar, i_par_ar = _bloc_maille(col, MAILLE_DELTA)',
     '    bloc_ar, i_niv_ar, i_par_ar = _bloc_maille(col, MAILLE_DEFAUT)'),

    ("la base est prise dans la maille de Δ au lieu de la sienne",
     QUART, BANC_QUART,
     '    u10, v10 = _u_v_10m(col, MAILLE_DEFAUT)',
     '    u10, v10 = _u_v_10m(col, MAILLE_DELTA)'),

    ("l'appariement des balises se fait par RANG et non par "
     "identifiant — une prévision prise 40 km plus loin, finie et "
     "plausible",
     QUART, BANC_QUART,
     '        kpi = ix_pi.get(str(b["id"]))',
     '        kpi = k if k < len(ix_pi) else None'),

    # ── ce que la ligne déclare ─────────────────────────────────────
    ("la ligne déclare un pas HORAIRE — appariée à ±20 min sur un pas "
     "de 15, et le plancher de l'heure ronde avec",
     QUART, BANC_QUART,
     '"t0": t0, "step_s": PAS_QUART_S,',
     '"t0": t0, "step_s": 3600,'),

    ("`base_interpolee` ment : les trois séries se disent non "
     "interpolées à une échéance qui n'existe dans aucun run AROME",
     QUART, BANC_QUART,
     '"agrume_quart_base_interpolee": True,',
     '"agrume_quart_base_interpolee": False,'),

    ("⛔ Q5 — `fetched_at` porte l'heure du run AROME et non celle du "
     "run PI : la classe crédite PI d'une fraîcheur qui n'est pas la "
     "sienne, et `lead_exact_h` glisse de six heures",
     QUART, BANC_QUART,
     '"fetched_at": r_p.strftime("%Y-%m-%dT%H:%M:%S+00:00"),',
     '"fetched_at": r_a.strftime("%Y-%m-%dT%H:%M:%S+00:00"),'),

    # ── les étiquettes et le classement ─────────────────────────────
    ("les étiquettes du quart d'heure reprennent celles de la classe "
     "courte — DEUX PAS DE TEMPS sous une seule étiquette, la variante "
     "(b) refusée en Q2 le 30/08",
     SCORE, BANC_QUART,
     'LEAD_QUART_MATIN = -3',
     'LEAD_QUART_MATIN = -1'),

    ("les trois sous-séries du quart d'heure reprennent un rang — dont "
     "le TÉMOIN, c'est-à-dire de l'AROME fabriqué classé contre le "
     "produit qu'il sert à juger",
     SCORE, BANC_QUART,
     '        if r["model"] in MODELES_COURTS or r["model"] in MODELES_QUARTS:',
     '        if r["model"] in MODELES_COURTS:'),

    ("la classe au quart d'heure nourrit la MÉMOIRE DU CARACTÈRE — "
     "trois mois de moyenne exponentielle pour un témoin fabriqué",
     SCORE, BANC_QUART,
     '    banded = [b for b in banded if b["lead_h"] not in LEADS_INSTANT_T]',
     '    banded = [b for b in banded if b["lead_h"] not in LEADS_COURTS]'),

    ("l'archive du quart d'heure écrase celle de la classe courte — un "
     "job qui échoue au milieu emporte l'archive de l'autre",
     SCORE, BANC_QUART,
     '    return (f"fcstagrumequart/{day:%Y/%m}/"\n'
     '            f"fcstagrumequart_{day:%Y-%m-%d}.ndjson.gz")',
     '    return fcst_agrume_court_key(day)'),
]


def _env_sans_pyc() -> dict:
    """L'environnement du banc, SANS écriture ni lecture de bytecode.

    ⛔⛔ LE PIÈGE, TROUVÉ LE 30/08/2026 SUR LE LOT L10, ET IL REND UNE
    MUTATION MENTEUSE. `HEURES_CIBLES = 6` muté en `= 7` fait EXACTEMENT
    la même longueur de fichier ; si la restauration retombe dans la même
    SECONDE, l'horodatage ne bouge pas non plus. Python juge son cache
    `__pycache__` sur (mtime, taille) : il a donc rechargé le bytecode
    MUTÉ pour les trois mutations suivantes, qui ont rougi — mais pour la
    faute de la précédente. Trois lignes vertes qui ne prouvaient rien.
    ⇒ `-B` (ne pas écrire) et `PYTHONDONTWRITEBYTECODE` (pour les
    sous-processus), plus le ménage ci-dessous. Une mutation qui ne peut
    pas prouver ce qu'elle affirme est pire qu'une mutation absente.
    """
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for p in ICI.rglob("__pycache__"):
        shutil.rmtree(p, ignore_errors=True)
    return env


def joue() -> int:
    rouges = 0
    for i, (nom, fichier, banc, avant, apres) in enumerate(MUTATIONS, 1):
        origine = HARNAIS.garder(fichier)
        if avant not in origine:
            print(f"  ⛔ {i:>2}. {nom}\n       MOTIF INTROUVABLE dans "
                  f"{fichier.name} — la mutation n'a rien muté, donc elle "
                  f"n'a rien prouvé. (Le code a bougé : réécrire ce motif.)")
            rouges += 1
            continue
        try:
            fichier.write_text(origine.replace(avant, apres, 1), encoding="utf-8")
            r = subprocess.run([sys.executable, "-B", str(ICI / banc)],
                               capture_output=True, text=True, cwd=ICI,
                               env=_env_sans_pyc())
            if r.returncode == 0:
                print(f"  ❌ {i:>2}. {nom}\n       LE BANC {banc} RESTE "
                      f"VERT — il ne tient pas cette propriété.")
                rouges += 1
            else:
                lignes = [l.strip() for l in r.stdout.splitlines()
                          if l.strip().startswith("❌")]
                if not lignes:
                    lignes = [l.strip() for l in r.stderr.splitlines()[-3:]]
                print(f"  ✅ {i:>2}. {nom}\n       [{banc}] "
                      f"{lignes[0] if lignes else 'banc rouge'}"
                      + (f" (+{len(lignes) - 1} autres)"
                         if len(lignes) > 1 else ""))
        finally:
            HARNAIS.rendre(fichier, origine)
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations du lot L11 (la classe au quart d'heure) — chaque ligne doit "
          "être VERTE,\n  c'est-à-dire : le banc a bien ROUGI sur la faute.\n")
    n = joue()
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
