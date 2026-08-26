#!/usr/bin/env python3
"""Rejoue `test_sonde_delta_10m.py` contre des variantes CASSÉES.

⛔ Un banc vert ne prouve rien tant qu'on n'a pas vu ce qui le fait
rougir. Chaque mutation ci-dessous est une faute qu'on pourrait écrire
sans s'en apercevoir ; celle qui laisse le banc VERT désigne un banc
trop faible — ou, comme le 26/08, un couplage à supprimer plutôt qu'une
vérification à ajouter.

Restauration en `finally` : le fichier revient à son état d'origine même
si l'on interrompt.

    python3 mutations_sonde_delta_10m.py
"""
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
SONDE = ICI / "sonde_delta_10m.py"

MUTATIONS = [
    ("Δ(10 m) pris dans la maille 0,01° au lieu de 0,025°",
     SONDE,
     'u_q10 = float(bloc_q[k, iu_q, jq_bas, i_step])',
     'u_q10 = float(bloc_b[k, iu_b, jb_bas, i_step])'),
    ("Δ(10 m) lu au niveau 20 m côté PI",
     SONDE,
     'u_p10 = float(pi_donnees[iu_pi, j_pi_bas, i_min, kpi])',
     'u_p10 = float(pi_donnees[iu_pi, j_pi_haut, i_min, kpi])'),
    ("AROME 20 m lu au niveau 10 m",
     SONDE,
     'u_q20 = float(bloc_q[k, iu_q, jq_haut, i_step])',
     'u_q20 = float(bloc_q[k, iu_q, jq_bas, i_step])'),
    ("PI indexé par RANG et non par identifiant",
     SONDE,
     'kpi = ix_pi[sid]',
     'kpi = k'),
    ("heures PI prises par POSITION et non par valeur",
     SONDE,
     'i_min = pi_min.index(h * 60)      # PAR VALEUR, jamais par position',
     'i_min = h'),
    ("la rampe w est ignorée (PI plein pot jusqu'à 6 h)",
     SONDE,
     'w = poids_pi(h * 60)',
     'w = 1.0'),
    ("Δ(10 m) de signe inversé (AROME − PI) dans la composition des séries",
     SONDE,
     '    d10u = tab[:, c["u_pi10"]] - tab[:, c["u_ar10q"]]\n'
     '    d10v = tab[:, c["v_pi10"]] - tab[:, c["v_ar10q"]]\n'
     '    out = {',
     '    d10u = tab[:, c["u_ar10q"]] - tab[:, c["u_pi10"]]\n'
     '    d10v = tab[:, c["v_ar10q"]] - tab[:, c["v_pi10"]]\n'
     '    out = {'),
    ("le placebo garde ses points fixes",
     SONDE,
     '    for i in range(n):\n        if p[i] != i:\n            continue\n'
     '        j = (i + 1) % n\n        p[i], p[j] = p[j], p[i]',
     '    pass'),
    ("la graine du placebo repasse par hash()",
     SONDE,
     'return zlib.crc32(f"{run}#{g}".encode("utf-8"))',
     'return abs(hash(f"{run}#{g}")) % (2 ** 32)'),
    ("le mode vectoriel est décidé par T0 seule",
     SONDE,
     '    for sp, di in sers.values():\n        ok &= np.isfinite(di) & '
     '(sp >= S.DIR_MIN_WIND_KMH)',
     '    sp, di = sers["T0"]\n    ok &= np.isfinite(di) & '
     '(sp >= S.DIR_MIN_WIND_KMH)'),
    ("rms remplacée par une médiane",
     SONDE,
     'return float(np.sqrt(np.mean(e * e))) if len(e) else float("nan")',
     'return float(np.median(np.abs(e))) if len(e) else float("nan")'),
    ("bootstrap rééchantillonné par COUPLE",
     SONDE,
     '        pris = rng.choice(uniques, size=len(uniques), replace=True)\n'
     '        idx = np.concatenate([par_jour[j] for j in pris])',
     '        idx = rng.integers(0, len(jours), len(jours))'),
    ("un NaN est traité comme une valeur",
     SONDE,
     '    return all(np.isfinite(x) for x in xs)',
     '    return True'),
    ("la garde de forme du tableau PI est retirée",
     SONDE,
     '    if tuple(pi_donnees.shape) != attendue:',
     '    if False:'),
    ("un run sans 10 m servi est quand même mesuré",
     SONDE,
     '    if not pi_man.get("niveau_10m_servi", False):',
     '    if False:'),
    ("la fenêtre d'appariement passe de ±20 min à ±60 min",
     SONDE,
     '    lo = t_ms - S.OBS_HALF_WINDOW_MS\n    hi = t_ms + S.OBS_HALF_WINDOW_MS',
     '    lo = t_ms - 3600_000\n    hi = t_ms + 3600_000'),
    ("α évalué SUR la moitié où il a été appris (pas hors échantillon)",
     SONDE,
     '            hors.append((a_star, err_de(du, dv, a_star, eval_),\n'
     '                         err_de(du, dv, 0.0, eval_),\n'
     '                         err_de(du, dv, 1.0, eval_)))',
     '            hors.append((a_star, err_de(du, dv, a_star, appr),\n'
     '                         err_de(du, dv, 0.0, appr),\n'
     '                         err_de(du, dv, 1.0, appr)))'),
    ("la courbe de α n'est plus ancrée sur T0 (α = 0 décalé)",
     SONDE,
     '    alphas = np.round(np.arange(0.0, 1.05, 0.1), 2)',
     '    alphas = np.round(np.arange(0.05, 1.05, 0.1), 2)'),
    ("le cisaillement κ est écrit en dur au lieu d'être mesuré",
     SONDE,
     '    return float(np.median(v10[ok] / v20[ok])) if ok.any() else 1.0',
     '    return 0.766'),
    ("la question 0 recalcule SON PROPRE masque (le vrai bug du 26/08)",
     SONDE,
     '    q0 = question_0(tab, champs, obs_sp, obs_di, vec=vec, crier=crier)',
     '    q0 = question_0(tab, champs, obs_sp, obs_di, crier=crier)'),
    ("un couple sans donneur de placebo est gardé quand même",
     SONDE,
     '            if dons is None:\n                continue',
     '            if dons is None:\n                dons = {g: (0.0, 0.0, 0.0, 0.0)\n'
     '                        for g in GRAINES_PLACEBO}'),
]


def banc_vert() -> bool:
    r = subprocess.run([sys.executable, str(ICI / "test_sonde_delta_10m.py")],
                       capture_output=True, text=True, cwd=str(ICI))
    return r.returncode == 0


def main():
    if not banc_vert():
        print("⛔ le banc est DÉJÀ rouge sur le code intact — on s'arrête")
        return 1
    print(f"banc vert sur le code intact — {len(MUTATIONS)} mutations\n")
    survivantes = []
    for i, (nom, cible, avant, apres) in enumerate(MUTATIONS, 1):
        src = cible.read_text(encoding="utf-8")
        if src.count(avant) != 1:
            print(f"  ⚠️  {i:2d}. {nom}\n       motif introuvable ou "
                  f"ambigu ({src.count(avant)} occurrences) — MUTATION "
                  f"NON APPLIQUÉE")
            survivantes.append(f"[non appliquée] {nom}")
            continue
        try:
            cible.write_text(src.replace(avant, apres), encoding="utf-8")
            vert = banc_vert()
        finally:
            cible.write_text(src, encoding="utf-8")
        if vert:
            print(f"  ❌ {i:2d}. {nom}\n       le banc reste VERT")
            survivantes.append(nom)
        else:
            print(f"  ✅ {i:2d}. {nom} → banc rouge")
    print()
    if survivantes:
        print(f"⛔ {len(survivantes)} mutation(s) survivante(s) :")
        for s in survivantes:
            print(f"   · {s}")
        return 1
    print(f"✅ les {len(MUTATIONS)} mutations font toutes tomber le banc")
    return 0


if __name__ == "__main__":
    sys.exit(main())
