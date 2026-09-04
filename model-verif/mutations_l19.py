#!/usr/bin/env python3
"""Rejoue les bancs contre des variantes CASSÉES du lot L19 — le mélange
multi-modèle `bw_mix`, le biais de site FIN (secteur × tranche) et la
dispersion des membres (04/09/2026).

⛔ CE QU'ON CRAINT ICI, c'est un mélange PLAUSIBLE ET FAUX : des poids
qui voient le jour J (le mélange bat tout le monde, et pour cause), un
mélange fait en force scalaire (leçon du L9c, deux vents opposés font
10 km/h), une ligne synthétique qui entre au classement ou dans la
mémoire longue, une correction fine qui retombe sur les sommes du jour,
ou un verdict de dispersion qui dit « exploitable » sans regarder.
Aucune de ces fautes ne plante ; toutes se publient.

⚠️ Le motif à muter doit exister TEL QUEL dans le fichier : une
mutation dont le motif est introuvable n'a rien muté, donc rien prouvé,
et ce script le dit en rouge plutôt que de la compter verte.

    python3 mutations_l19.py            # tout
    python3 mutations_l19.py 1 5        # par tranches
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import harnais as HARNAIS  # noqa: E402

SCORE = ICI / "score.py"
MELANGE = ICI / "melange.py"
BIAIS = ICI / "biais_fin.py"
B_SCORE = ICI / "test_score.py"
B_MELANGE = ICI / "test_melange.py"
B_BIAIS = ICI / "test_biais_fin.py"

MUTATIONS = [
    # ══════════════════════════════════════════════════════════════
    #  A — LES POIDS : jamais le jour J, jamais le mélange lui-même
    # ══════════════════════════════════════════════════════════════
    ("⭐⭐ les poids lisent AUSSI le jour J (range(n_jours, -1, -1)) : le "
     "mélange voit sa propre réponse",
     SCORE, B_SCORE,
     """    accs: dict[tuple, dict[str, MX.AccMse]] = {}
    for k in range(n_jours, 0, -1):""",
     """    accs: dict[tuple, dict[str, MX.AccMse]] = {}
    for k in range(n_jours, -1, -1):"""),

    ("le mélange entre dans ses propres poids (bw_mix pèse dans bw_mix)",
     SCORE, B_SCORE,
     """            if rms is None or r["model"] in MX.MODELES_MELANGE:
                continue""",
     """            if rms is None:
                continue"""),

    ("⭐ le poids est la MSE au lieu de son inverse : le pire modèle "
     "pèse le plus",
     MELANGE, B_MELANGE,
     "        bruts[model] = 1.0 / max(acc.mean, MIX_MSE_MIN)",
     "        bruts[model] = max(acc.mean, MIX_MSE_MIN)"),

    ("le plancher de MSE saute : un calme plat vaut un poids infini",
     MELANGE, B_MELANGE,
     "        bruts[model] = 1.0 / max(acc.mean, MIX_MSE_MIN)",
     "        bruts[model] = 1.0 / max(acc.mean, 1e-12)"),

    ("un membre sous MIX_MIN_JOURS reçoit quand même un poids",
     MELANGE, B_MELANGE,
     "        if acc.days < min_jours or acc.mean is None:",
     "        if acc.mean is None:"),

    ("la mémoire d'erreur ne décroît plus (decay = 1) : une supériorité "
     "d'il y a un mois pèse comme celle d'hier",
     MELANGE, B_MELANGE,
     """        decay = (1.0 if self.last_day is None
                 else 2 ** (-(day_i - self.last_day) / MIX_DEMI_VIE_J))
        self.sum_w = self.sum_w * decay + 1
        self.sum_wx = self.sum_wx * decay + x""",
     """        decay = 1.0
        self.sum_w = self.sum_w * decay + 1
        self.sum_wx = self.sum_wx * decay + x"""),

    # ══════════════════════════════════════════════════════════════
    #  B — LE MÉLANGE : en (u, v), une lecture par famille
    # ══════════════════════════════════════════════════════════════
    ("⭐⭐ le mélange est fait en FORCE scalaire (leçon du L9c) : deux "
     "vents opposés donnent 10 km/h",
     MELANGE, B_MELANGE,
     """            f = math.hypot(u, v)
            speed.append(round(f, 3))
            direction.append(round(S.from_uv(u, v), 1) if f > 1e-9 else None)""",
     """            f = sum(w * math.hypot(uu, vv) for w, uu, vv in vec) / tw
            speed.append(round(f, 3))
            direction.append(round(S.from_uv(u, v), 1) if f > 1e-9 else None)"""),

    ("les poids ne sont plus renormalisés sur les membres PRÉSENTS : une "
     "heure manquante tire le mélange vers zéro",
     MELANGE, B_MELANGE,
     """            tw = sum(w for w, _, _ in vec)
            u = sum(w * uu for w, uu, _ in vec) / tw""",
     """            tw = 1.0
            u = sum(w * uu for w, uu, _ in vec) / tw"""),

    ("⭐ la famille AROME entre TROIS fois (plus de dédoublonnage)",
     MELANGE, B_MELANGE,
     """        gardee = next((m for m in lectures if m in presents), None)
        exclus_famille |= {m for m in lectures if m != gardee}""",
     """        gardee = next((m for m in lectures if m in presents), None)
        exclus_famille |= set()"""),

    ("les lignes qui déclarent une échéance (classe courte) entrent "
     "dans le mélange",
     MELANGE, B_MELANGE,
     """                or r.get("lead_h") is not None or r.get("synthese")""",
     """                or r.get("synthese")"""),

    ("un mélange d'UN seul membre est publié (un modèle sous un autre nom)",
     MELANGE, B_MELANGE,
     """    if len(membs) < MIX_MIN_MEMBRES:
        return None
    w_of =""",
     """    if len(membs) < 1:
        return None
    w_of ="""),

    ("fetched_at = le membre le plus FRAIS : lead_exact_h ment dans le "
     "sens flatteur",
     MELANGE, B_MELANGE,
     '        "fetched_at": min(r["fetched_at"] for r in membs),',
     '        "fetched_at": max(r["fetched_at"] for r in membs),'),

    # ══════════════════════════════════════════════════════════════
    #  C — DANS LA CHAÎNE : noté, pas classé ; ni caractère ni événement
    # ══════════════════════════════════════════════════════════════
    ("⭐⭐ bw_mix ENTRE AU CLASSEMENT (l'exclusion saute)",
     SCORE, B_SCORE,
     """        if (r["model"] in MODELES_COURTS or r["model"] in MODELES_QUARTS
                or r["model"] in MX.MODELES_MELANGE):""",
     """        if (r["model"] in MODELES_COURTS or r["model"] in MODELES_QUARTS):"""),

    ("bw_mix nourrit la mémoire du caractère (hors_caractere ignoré)",
     SCORE, B_SCORE,
     """            if row.get("hors_caractere"):
                continue
            by_band: dict[str, list[S.VerifPair]] = defaultdict(list)""",
     """            by_band: dict[str, list[S.VerifPair]] = defaultdict(list)"""),

    ("bw_mix produit des événements (une moyenne « prudente » parce que "
     "floue)",
     SCORE, B_SCORE,
     """            if row.get("synthese"):
                continue
            key = f"{row['source']}:{row['station_id']}"
            if key not in obs_by_st:
                continue
            series = _series_of(row, day_start_ms)""",
     """            key = f"{row['source']}:{row['station_id']}"
            if key not in obs_by_st:
                continue
            series = _series_of(row, day_start_ms)"""),

    ("le mélange n'entre plus dans le chemin RÉGIME (replay_day sans "
     "ajouter_melange)",
     SCORE, B_SCORE,
     """    snapshots, _ = MX.ajouter_melange(snapshots, prior_poids(root, day),
                                      LEAD_BY_OFFSET)
    rows, _ = daily_rows(day, snapshots, obs_day, obs_prev, utc_offset_s,""",
     """    rows, _ = daily_rows(day, snapshots, obs_day, obs_prev, utc_offset_s,"""),

    ("la dispersion est résumée sur TOUTES les heures du jour, pas sur "
     "les heures appariées",
     SCORE, B_SCORE,
     """                _vals = [_sp[i] for i in idx
                         if times[i] in _apparie and i < len(_sp)
                         and S._finite(_sp[i])]""",
     """                _vals = [_sp[i] for i in idx
                         if i < len(_sp)
                         and S._finite(_sp[i])]"""),

    ("`replay_window` garde `_biais_fin` dans la fenêtre (mémoire)",
     SCORE, B_SCORE,
     """            r.pop(BF.CLE, None)""",
     """            pass"""),

    ("⛔ une colonne neuve n'est plus déclarée dans la table colonne→.sql",
     SCORE, B_SCORE,
     '        "spread_kmh": "supabase_step69_lot_l19_melange_biais_fin.sql",\n',
     ''),

    # ══════════════════════════════════════════════════════════════
    #  D — LE BIAIS FIN : la cellule, le repli, la fuite
    # ══════════════════════════════════════════════════════════════
    ("⭐⭐ l'antécédent fin lit AUSSI le jour J",
     SCORE, B_SCORE,
     """    out: dict[tuple, BF.PriorFin] = {}
    for k in range(n_jours, 0, -1):""",
     """    out: dict[tuple, BF.PriorFin] = {}
    for k in range(n_jours, -1, -1):"""),

    ("⭐ la cellule se prend sur le cap OBSERVÉ (on choisit la correction "
     "après avoir vu la réponse)",
     BIAIS, B_BIAIS,
     """    if p.fcst_dir is None or p.fcst_speed < S.DIR_MIN_WIND_KMH:
        return None
    return f"{S.quadrant(p.fcst_dir)}|{tranche(p.t, utc_offset_s)}\"""",
     """    if p.obs_dir is None or p.fcst_speed < S.DIR_MIN_WIND_KMH:
        return None
    return f"{S.quadrant(p.obs_dir)}|{tranche(p.t, utc_offset_s)}\""""),

    ("le plancher d'heures pondérées saute : trois heures font une pente",
     BIAIS, B_BIAIS,
     """        if (self.days < FIN_MIN_JOURS or self.sum_n < FIN_MIN_HEURES
                or self.sum_ff <= 0):""",
     """        if (self.days < FIN_MIN_JOURS
                or self.sum_ff <= 0):"""),

    ("la pente hors bornes est APPLIQUÉE au lieu d'être refusée",
     BIAIS, B_BIAIS,
     """        p = self.sum_of / self.sum_ff
        if not (FIN_PENTE_MIN <= p <= FIN_PENTE_MAX):
            return None
        return p""",
     """        p = self.sum_of / self.sum_ff
        return p"""),

    ("le repli saute le niveau SECTEUR (cellule → balise directement)",
     BIAIS, B_BIAIS,
     """        acc = self.secteurs.get(secteur_de(cell))
        if acc is not None and acc.pente is not None:
            return acc.pente, NIVEAU_SECTEUR, acc.days
        return None, None, 0""",
     """        return None, None, 0"""),

    ("le placebo ne tourne plus les cellules (il EST le vrai antécédent) : "
     "la part imputable au secteur tombe à zéro sans qu'on le voie",
     BIAIS, B_BIAIS,
     """        rot_q = {"N": "E", "E": "S", "S": "W", "W": "N"}""",
     """        rot_q = {}"""),

    ("l'observation est corrigée à la place de la prévision",
     BIAIS, B_BIAIS,
     """        out.append(replace(p, fcst_speed=fs, fcst_dir=fd))""",
     """        out.append(replace(p, obs_speed=fs, fcst_dir=fd))"""),

    ("le niveau dominant est le PREMIER vu, pas celui qui corrige le "
     "plus d'heures",
     BIAIS, B_BIAIS,
     """    return max(utiles, key=lambda k: (utiles[k], -NIVEAUX.index(k)))""",
     """    return next(iter(utiles))"""),

    # ══════════════════════════════════════════════════════════════
    #  E — LA DISPERSION : pas de pastille sans courbe
    # ══════════════════════════════════════════════════════════════
    ("⭐ le verdict est `exploitable` sans regarder rho ni le rapport",
     MELANGE, B_MELANGE,
     """    exploitable = (rho is not None and rho >= DISP_RHO_MIN
                   and rapport is not None and rapport >= DISP_RAPPORT_MIN)""",
     """    exploitable = True"""),

    ("la courbe accepte les lignes des AUTRES modèles",
     MELANGE, B_MELANGE,
     """        if r.get("model") != MODEL_MIX:
            continue
        d, e = r.get(cle_disp), r.get(cle_err)""",
     """        d, e = r.get(cle_disp), r.get(cle_err)"""),

    ("Spearman sans rang moyen sur les ex æquo",
     MELANGE, B_MELANGE,
     """        moy = (i + j) / 2 + 1""",
     """        moy = i + 1"""),
]


def joue(debut: int = 1, fin: int | None = None) -> int:
    """⚠️ `debut`/`fin` NE SONT PAS UN CONFORT — voir `mutations_l9c_vec.py` :
    un harnais tué laisse le fichier muté, jouer par tranches courtes."""
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
                      f"{lignes[0] if lignes else 'banc rouge'}"
                      + (f" (+{len(lignes) - 1} autres)"
                         if len(lignes) > 1 else ""))
        finally:
            HARNAIS.rendre(fichier, origine)
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations du lot L19 — mélange, biais fin, dispersion. Chaque "
          "ligne doit être VERTE,\n  c'est-à-dire : le banc a bien ROUGI "
          "sur la faute.\n")
    debut = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    fin = int(sys.argv[2]) if len(sys.argv) > 2 else len(MUTATIONS)
    n = joue(debut, fin)
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
