#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/agrume_quart.py — LA CLASSE AU QUART D'HEURE
#                                            (Lot L11, 31/08/2026)
#
#  ⛔ CE QU'ELLE NOTE, EN UNE PHRASE : la MÊME question que la classe
#  courte — « ce que tu pouvais savoir à l'instant T » — mais posée aux
#  seuls instants où le composite prétend valoir quelque chose : :15,
#  :30 et :45. Jamais l'heure ronde.
#
#  ═══ LA RÉSERVE QU'ELLE EXISTE POUR FERMER ═══
#
#  Phase B, 26/08, écrite dans « ce qui n'a PAS été vérifié » :
#
#      « La sonde ne lit que les heures rondes, exprès (aucune
#        interpolation possible, donc rien de fabriqué). Or c'est à :15,
#        :30 et :45 que le composite justifie son existence — là,
#        l'alternative n'est pas AROME, c'est AROME *interpolé*. Ce
#        rapport ne dit RIEN sur ce cas-là, et c'est peut-être là que PI
#        gagne. »
#
#  Cinq jours plus tard, la réserve est toujours ouverte, et elle l'est
#  parce que RIEN dans le dispositif ne notait cet AROME interpolé. Ce
#  fichier le note. C'est la série `agrume_quart_w0`, et elle est un
#  TÉMOIN, pas un concurrent.
#
#  ⭐ ET C'EST ICI, ET NULLE PART AILLEURS, QUE LE DUEL EXISTE. Aux
#  heures rondes les deux produits sont également réels, et la phase B a
#  mesuré que PI n'y gagne pas (+0,08 km/h). Aux quarts d'heure, PI a une
#  valeur qu'il a CALCULÉE (c'est son pas natif) et AROME n'en a aucune :
#  la sienne est fabriquée par interpolation, et cette fabrication coûte
#  0,31 m/s en médiane, 1,08 au q90 (`composite.arome_interpole`, mesuré).
#  C'est ce coût-là que le composite prétend éviter, et `w` dit quelle
#  part du point vient du côté qui n'a rien fabriqué.
#
#  ⚠️⚠️ ET NON, `w = 1` N'EST PAS « DU PI PUR » — je l'avais écrit ici,
#  et c'est faux. La valeur servie est, à tout `w` :
#
#      V(w) = AROME₁₀ᶦⁿᵗᵉʳᵖ + w · kz · (PI₂₀ − AROME₂₀ᶦⁿᵗᵉʳᵖ)
#
#  À `w = 1` il reste `AROME₁₀ᶦⁿᵗᵉʳᵖ − kz·AROME₂₀ᶦⁿᵗᵉʳᵖ` : un RÉSIDU
#  interpolé, petit mais non nul, parce que la base est au 10 m en 0,01°
#  quand Δ se mesure au 20 m en 0,025° (règle 2 de `delta_20m` — les
#  mélanger ferait entrer l'écart de résolution dans Δ). ⛔ AUCUNE des
#  trois sous-séries n'est exempte d'interpolation ; ce qui change avec
#  `w`, c'est le POIDS donné au seul terme dont la moitié est native.
#  Écrire « w = 1 = PI » aurait été un de ces énoncés plausibles, non
#  mesurés et faux que ce chantier traque depuis le premier jour.
#
#  ═══ ⛔⛔ LA RÈGLE QUI TIENT TOUT LE LOT : UNE SEULE POPULATION ═══
#
#  Un quart d'heure n'est servi QUE si PI y a une valeur — et il est
#  alors servi dans LES TROIS sous-séries, ou dans aucune.
#
#  La tentation était forte de faire autrement : `w = 1` est censé être
#  « du PI », donc un quart sans PI aurait dû en sortir, pendant que
#  `w = 0` (qui n'a pas besoin de PI) l'aurait gardé. C'est exactement
#  la faute que le lot L9(c) vient de passer trois nuits à instruire :
#  trois erreurs quadratiques comparées sur trois populations d'heures
#  différentes, et une « violation de Jensen » qui n'était qu'une
#  comparaison mal posée. On ne la refait pas cinq jours plus tard, dans
#  un lot dont le SEUL objet est une comparaison.
#  ⓘ Prix nommé : `w = 0` sert moins de points qu'il ne pourrait. C'est
#  le prix d'un appariement exact, et il est petit.
#
#  ═══ ⛔ L'ARGUMENT D'INDÉPENDANCE — ÉCRIT AVANT LA PREMIÈRE LIGNE ═══
#
#  Le lot l'exigeait, et il est ARITHMÉTIQUE : deux échéances séparées
#  de `pas`, fenêtres centrées de demi-largeur `demi`, ne partagent
#  aucun relevé ssi `2 × demi < pas`. ±20 min / 60 min : 40 < 60 ✅ —
#  c'est la raison écrite de `scoring.OBS_HALF_WINDOW_MS`, et elle n'a
#  jamais été qu'un cas particulier. ±7 min / 15 min : 14 < 15 ✅.
#  La règle vit désormais dans `scoring.DEMI_FENETRE_MS`, avec une
#  assertion à l'import : une table qui casserait l'indépendance ne peut
#  pas atteindre la production.
#  ⭐ Et elle a été vérifiée EMPIRIQUEMENT en plus d'être démontrée :
#  sonde du 31/08, 20 jours, 1 104 balises — **0 relevé compté dans deux
#  fenêtres**, aux trois demi-fenêtres essayées.
#
#  ═══ ⚠️ CE QUE LA SONDE A CORRIGÉ DANS L'AUDIT LUI-MÊME ═══
#
#  L'audit §3.4 fondait ce lot sur « pas médian 5 min, 93 % des balises
#  ≤ 7,5 min » — mesuré sur 576 balises **Pioupiou**. Sur les 1 104
#  balises que la classe sert vraiment, c'est faux pour trois réseaux
#  sur cinq : windsmobi 10,1′ (2,4 % ≤ 7,5′), infoclimat 10,0′ (0,0 %),
#  aemet 60,0′ (0,0 %). ⭐ La conclusion tient quand même, pour une
#  AUTRE raison que la sienne : le critère « ≤ 7,5 min » n'était pas le
#  bon — ce qui compte est qu'un relevé TOMBE dans ±7 min d'un quart
#  d'heure, et une cadence de 10 min y tombe 96,7 % du temps.
#  ⛔ Sauf aemet : 60 min pile sur l'heure ronde, **0,0 %** aux quarts.
#  Ces 39 balises tomberont sous le plancher — par la RÈGLE
#  (`score.PLANCHER_PAR_PAS`), sans qu'un nom de réseau soit écrit ici.
#
#  Usage :
#      set -a; . ~/.balise-watch-r2.env; . ~/.balise-watch-agrume-r2.env; set +a
#      python3 model-verif/agrume_quart.py [--day 2026-08-30] [--dry-run]
# ══════════════════════════════════════════════════════════════════════
from __future__ import annotations

import argparse
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import numpy as np

_ICI = pathlib.Path(__file__).resolve().parent
for _p in (_ICI.parent / "agrume", _ICI.parent / "verif", _ICI.parent / "tools"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

# ⛔ TOUT CE QUI DÉCIDE « QUEL RUN À QUEL INSTANT » EST IMPORTÉ DE LA
# CLASSE COURTE, JAMAIS RECOPIÉ. Les deux instants T (06:50 / 12:50) ont
# coûté une sonde pour être mesurés, `run_disponible` porte le refus de
# l'information du futur, et `heures_cibles` porte le « strictement
# après T ». Une seconde écriture de l'un des trois, c'est deux classes
# qui divergent en silence le jour où l'une bouge.
from agrume_court import (PREFIXE_PI, T_APREM, T_MATIN,     # noqa: E402
                          _client_r2, heures_cibles, run_disponible,
                          runs_poses)
from agrume_fcst import (BUCKET_R2_DEFAUT, BUCKET_R2_ENV,   # noqa: E402
                         MAILLE_DEFAUT, MAILLE_DELTA, NIVEAU_DELTA_APPLIQUE,
                         NIVEAU_DELTA_MESURE, PREFIXE_COLONNES, SOURCE_NOTEE,
                         _bloc_maille, _u_v_10m, decorer_vent, lire_run,
                         lire_run_pi)
from collect import temoin, upload_r2, write_ndjson_gz      # noqa: E402
from composite import arome_interpole, facteur_cisaillement  # noqa: E402
from r2_lecture import bucket_r2, prefixe_lecture           # noqa: E402
from score import (AGRUME_QUART_W0, AGRUME_QUART_W05,       # noqa: E402
                   AGRUME_QUART_W1, LEAD_QUART_APREM, LEAD_QUART_MATIN,
                   PAS_QUART_S, fcst_agrume_quart_key)
from storage import Abort                                   # noqa: E402

#: Les deux instants de décision, avec les étiquettes du QUART D'HEURE.
#: ⓘ Les instants viennent de `agrume_court`, les étiquettes de `score` :
#: même cadre, autre pas de temps, autre clé.
INSTANTS = ((T_MATIN, LEAD_QUART_MATIN), (T_APREM, LEAD_QUART_APREM))

#: Les trois poids de Δ. ⛔ `w = 0` EST LE TÉMOIN, et il n'est pas une
#: quatrième idée : c'est l'AROME interpolé, la seule chose contre
#: laquelle le composite puisse être jugé à ces instants-là.
POIDS = {AGRUME_QUART_W0: 0.0, AGRUME_QUART_W1: 1.0, AGRUME_QUART_W05: 0.5}


def quarts_cibles(T: datetime) -> list[datetime]:
    """Les quarts d'heure notés pour l'instant de décision `T`.

    ⛔ LE PÉRIMÈTRE EST DÉRIVÉ DE CELUI DE LA CLASSE HORAIRE, PAS ÉCRIT
    À CÔTÉ. On prend les heures rondes de `agrume_court.heures_cibles`,
    et on garde les quarts STRICTEMENT ENTRE la première et la dernière.
    Deux conséquences, et les deux comptent :

      1. La classe au quart d'heure couvre exactement la même PLAGE que
         la classe horaire. Le jour où `HEURES_CIBLES` bouge, les deux
         bougent ensemble — écrire la plage une seconde fois ici, c'est
         se donner rendez-vous avec deux classes qui ne parlent plus du
         même intervalle.
      2. ⛔ AUCUNE HEURE RONDE. C'est la décision de périmètre de Yann
         du 31/08 : les heures rondes appartiennent à la classe horaire,
         et un instant noté DEUX FOIS gonflerait le `m` du BH-FDR (lot
         L3) et les `n` annoncés, sur exactement les mêmes observations.

    À T = 06:50 : heures rondes 07…12 Z, donc les quarts de 07:15 à
    11:45 — **quinze**, et c'est le compte que le plancher 13/15
    suppose.
    """
    rondes = heures_cibles(T)
    out: list[datetime] = []
    t = rondes[0] + timedelta(minutes=15)
    while t < rondes[-1]:
        if t.minute != 0:
            out.append(t)
        t += timedelta(minutes=15)
    return out


def _interp(bloc, steps_h, minutes_arome: float):
    """AROME interpolé en τ, sur (balise, échéance).

    ⓘ `composite.arome_interpole` est IMPORTÉ, jamais réécrit : il
    interpole sur u et v et jamais sur l'angle (interpoler 350° et 010°
    donnerait 180°, le vent exactement à l'opposé, et rien ne lèverait),
    il refuse d'extrapoler hors de la couverture AROME, et il porte dans
    sa propre docstring le coût de ce qu'il fabrique. C'est la règle de
    l'écran, et elle vaut ici mot pour mot.
    """
    return arome_interpole(bloc, steps_h, minutes_arome)


def series_du_t(col, man, pi_donnees, pi_man, T: datetime, lead: int,
                r_a: datetime, r_p: datetime, crier=print) -> list[dict]:
    """Les lignes d'archive des TROIS sous-séries, pour un instant T."""
    decalage_h = int((r_p - r_a).total_seconds() // 3600)
    quarts = quarts_cibles(T)
    steps_h = sorted(int(s) for s in col.steps)

    # ── Les index, pris ENSEMBLE, exactement comme `delta_20m` ────────
    if MAILLE_DELTA != "0025":
        raise Abort(f"maille de Δ inattendue : {MAILLE_DELTA!r}")
    try:
        pi_par = {p["nom"]: k for k, p in enumerate(pi_man["parametres"])}
        pi_niv = list(pi_man["niveaux_m_sol"])
        pi_min = list(pi_man["echeances_min"])
        j_pi = pi_niv.index(NIVEAU_DELTA_MESURE)
        iu_pi, iv_pi = pi_par["u"], pi_par["v"]
    except (KeyError, ValueError) as exc:
        raise Abort(f"le manifeste PI ne décrit pas le niveau "
                    f"{NIVEAU_DELTA_MESURE} m ou les champs u/v ({exc}) — "
                    f"refus de deviner la tranche") from exc
    bloc_ar, i_niv_ar, i_par_ar = _bloc_maille(col, MAILLE_DELTA)
    try:
        j_ar = i_niv_ar[NIVEAU_DELTA_MESURE]
        iu_ar, iv_ar = i_par_ar["u"], i_par_ar["v"]
    except KeyError as exc:
        raise Abort(f"le produit A n'a pas le niveau {NIVEAU_DELTA_MESURE} m "
                    f"en 0,025° ({exc}) — Δ est incalculable, et un Δ nul "
                    f"serait un mensonge crédible") from exc

    # Le vent 10 m qui sert de BASE (0,01°), et le 20 m qui sert de Δ
    # (0,025°). ⛔ Deux mailles, et c'est la règle 2 de `delta_20m` :
    # mélanger les mailles ferait entrer l'écart de résolution dans Δ.
    u10, v10 = _u_v_10m(col, MAILLE_DEFAUT)
    u20 = bloc_ar[:, iu_ar, j_ar, :]
    v20 = bloc_ar[:, iv_ar, j_ar, :]

    # ⛔ L'appariement des balises PAR IDENTIFIANT, jamais par rang —
    # les deux axes viennent de deux artefacts différents, et une
    # prévision prise 40 km plus loin reste finie et plausible.
    ix_pi = {str(b["id"]): k for k, b in enumerate(pi_man.get("balises", []))
             if b.get("servie", True)}

    kz = facteur_cisaillement(NIVEAU_DELTA_APPLIQUE)
    t0 = int(heures_cibles(T)[0].timestamp())
    n_cases = int((heures_cibles(T)[-1].timestamp() - t0) // PAS_QUART_S) + 1

    # ── Pour chaque quart : la base interpolée et Δ, sur TOUTES les
    #    balises d'un coup. Une boucle balise × quart aurait rappelé
    #    `arome_interpole` 1 100 fois par quart pour le même résultat.
    par_quart: dict[int, tuple] = {}
    n_hors_couverture = 0
    for q in quarts:
        m_ar = (q - r_a).total_seconds() / 60.0
        m_pi = int((q - r_p).total_seconds() // 60)
        if m_pi not in pi_min:
            # PI ne porte pas ce quart : par la règle d'UNE SEULE
            # POPULATION, il ne sera servi dans AUCUNE des trois.
            n_hors_couverture += 1
            continue
        i_min = pi_min.index(m_pi)
        try:
            bu10, bv10 = _interp(u10, steps_h, m_ar), _interp(v10, steps_h, m_ar)
            bu20, bv20 = _interp(u20, steps_h, m_ar), _interp(v20, steps_h, m_ar)
        except Abort:
            # L'échéance sort de la couverture AROME. `arome_interpole`
            # REFUSE d'extrapoler, et c'est la bonne réponse — on note
            # le quart comme absent plutôt que de le fabriquer deux fois.
            n_hors_couverture += 1
            continue
        i_case = int((q.timestamp() - t0) // PAS_QUART_S)
        par_quart[i_case] = (bu10, bv10, bu20, bv20, i_min)

    crier(f"    quarts visés {len(quarts)} · servis {len(par_quart)} · "
          f"hors couverture {n_hors_couverture}")

    out: list[dict] = []
    n_hors_pi = 0
    for k, b in enumerate(col.balises):
        if b.get("source") not in SOURCE_NOTEE:
            continue
        kpi = ix_pi.get(str(b["id"]))
        if kpi is None:
            n_hors_pi += 1
            continue
        # ⛔ UNE SEULE POPULATION : on établit d'ABORD la liste des
        # quarts servables pour CETTE balise, puis on la sert aux trois
        # sous-séries. L'écrire dans l'autre ordre (une boucle par
        # série, chacune décidant pour elle) est exactement ce qui a
        # produit le faux « Jensen violé » du lot L9(c).
        servables: dict[int, tuple[float, float, float, float]] = {}
        for i_case, (bu10, bv10, bu20, bv20, i_min) in par_quart.items():
            u_b, v_b = float(bu10[k]), float(bv10[k])
            u_a20, v_a20 = float(bu20[k]), float(bv20[k])
            u_pi = float(pi_donnees[iu_pi, j_pi, i_min, kpi])
            v_pi = float(pi_donnees[iv_pi, j_pi, i_min, kpi])
            if not all(np.isfinite(x) for x in
                       (u_b, v_b, u_a20, v_a20, u_pi, v_pi)):
                continue
            servables[i_case] = (u_b, v_b,
                                 kz * (u_pi - u_a20), kz * (v_pi - v_a20))
        if not servables:
            continue
        for model, w in POIDS.items():
            speed: list[float | None] = [None] * n_cases
            direction: list[float | None] = [None] * n_cases
            for i_case, (u_b, v_b, du, dv) in servables.items():
                p = decorer_vent({"u": u_b + w * du, "v": v_b + w * dv})
                speed[i_case] = p["vitesseKmh"]
                direction[i_case] = p["directionDeg"]
            out.append({
                "station_id": str(b["id"]),
                "source": b.get("source"),
                "lat": b.get("lat"), "lon": b.get("lon"),
                "model": model,
                # ⛔ Q5 (L10) — FRAÎCHEUR DU MODÈLE : l'heure du run PI,
                # parce que le composite N'EXISTAIT PAS avant lui. Le
                # moment où NOS octets ont été posés — une heure de plus,
                # du temps de détection — n'entre nulle part : c'est la
                # nôtre, elle ne se crédite pas à PI.
                "fetched_at": r_p.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                "t0": t0, "step_s": PAS_QUART_S,
                "speed": speed, "dir": direction,
                # ⛔ L'ÉCHÉANCE EST PORTÉE PAR LA LIGNE (`daily_rows` la
                # lit) — sans elle ces lignes seraient notées « +6 h ».
                "lead_h": lead,
                "agrume_run": man["run"],
                "agrume_maille": MAILLE_DEFAUT,
                "agrume_pi_run": pi_man["run"],
                "agrume_delta_mesure_m": NIVEAU_DELTA_MESURE,
                "agrume_delta_applique_m": NIVEAU_DELTA_APPLIQUE,
                "agrume_delta_maille": MAILLE_DELTA,
                "agrume_quart_poids": w,
                "agrume_quart_t": T.isoformat(),
                "agrume_quart_decalage_h": decalage_h,
                # ⛔ VRAI SUR LES TROIS SOUS-SÉRIES, SANS EXCEPTION : à
                # une échéance non ronde, les entrées AROME de cette
                # ligne sont INTERPOLÉES en temps. Le champ est donc
                # constant — et c'est justement pour ça qu'il vaut : une
                # relecture qui trouverait `false` ici saurait que
                # quelque chose sert des heures rondes sous l'étiquette
                # du quart d'heure. `agrume_quart_poids` dit, lui, quelle
                # part du point vient du terme à moitié natif (Δ).
                # ⚠️ Ne PAS écrire « part interpolée = 1 − w » : à w = 1
                # il reste le résidu AROME₁₀ − kz·AROME₂₀, interpolé lui
                # aussi (voir l'en-tête).
                "agrume_quart_base_interpolee": True,
                "agrume_quart_quarts": len(servables),
            })
    crier(f"    {len(out)} lignes ({len(out) // max(1, len(POIDS))} balises "
          f"× {len(POIDS)} sous-séries) · {n_hors_pi} balises hors "
          f"couverture PI")
    return out


def rows_du_jour(day: datetime, crier=print, client=None) -> list[dict]:
    """Les lignes d'archive de la classe au quart d'heure pour `day`."""
    with bucket_r2(os.environ.get(BUCKET_R2_ENV) or BUCKET_R2_DEFAUT,
                   prefixe_lecture()):
        s3 = client or _client_r2()
        depuis = day - timedelta(days=2)
        arome = runs_poses(PREFIXE_COLONNES, depuis, s3)
        pi = runs_poses(PREFIXE_PI, depuis, s3)
    crier(f"  runs connus sur R2 : {len(arome)} AROME, {len(pi)} PI "
          f"(depuis {depuis:%Y-%m-%d})")

    out: list[dict] = []
    for heure_t, lead in INSTANTS:
        T = datetime.combine(day.date(), heure_t, tzinfo=timezone.utc)
        r_a, pose_a = run_disponible(arome, T)
        r_p, pose_p = run_disponible(pi, T)
        if r_a is None or r_p is None:
            crier(f"  T={heure_t:%H:%M} Z — aucun run "
                  f"{'AROME' if r_a is None else 'PI'} posé à cet instant "
                  f"(archive purgée ou journée trop ancienne) : "
                  f"aucune ligne pour ce T.")
            continue
        crier(f"  T={heure_t:%H:%M} Z — AROME {r_a:%m-%d %HZ} (posé "
              f"{(pose_a - r_a).total_seconds() / 3600:.1f} h après) · "
              f"PI {r_p:%m-%d %HZ} (posé "
              f"{(pose_p - r_p).total_seconds() / 3600:.1f} h après) · "
              f"décalage {int((r_p - r_a).total_seconds() // 3600):+d} h")
        lu = lire_run(r_a.strftime("%Y-%m-%dT%H:%M:%SZ"), crier=crier)
        if lu is None:
            crier("    colonnes AROME illisibles — ce T est sauté.")
            continue
        col, man = lu
        lu_pi = lire_run_pi(r_p.strftime("%Y-%m-%dT%H:%M:%SZ"), crier=crier)
        if lu_pi is None:
            crier("    colonnes PI illisibles — ce T est sauté (sans PI, "
                  "les trois sous-séries seraient le même AROME).")
            continue
        pi_donnees, pi_man = lu_pi
        out += series_du_t(col, man, pi_donnees, pi_man, T, lead, r_a, r_p,
                           crier=crier)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="/var/lib/bw-model-verif")
    ap.add_argument("--day", default=None,
                    help="journée notée (défaut : hier, comme score.py)")
    ap.add_argument("--dry-run", action="store_true",
                    help="tout lire, tout compter, n'écrire ni fichier ni R2")
    args = ap.parse_args()

    day = (datetime.strptime(args.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
           if args.day
           else datetime.now(timezone.utc) - timedelta(days=1)).replace(
               hour=0, minute=0, second=0, microsecond=0)
    print(f"▶ classe au quart d'heure (lot L11) — journée {day:%Y-%m-%d}, "
          f"T = {T_MATIN:%H:%M} et {T_APREM:%H:%M} Z, "
          f"échéances :15/:30/:45 SEULEMENT")
    try:
        rows = rows_du_jour(day)
    except Abort as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if not rows:
        print("  aucune ligne pour cette journée — voir les motifs "
              "ci-dessus. Rien n'est écrit.")
        return 0

    key = fcst_agrume_quart_key(day)
    if args.dry_run:
        print(f"  (dry-run) {key} — {len(rows)} lignes, non écrites")
        return 0
    path = pathlib.Path(args.out) / key
    n = write_ndjson_gz(path, rows)
    print(f"  écrit : {path} ({n} lignes, "
          f"{path.stat().st_size / 1024:.1f} Ko)")
    if not upload_r2(path, key):
        print("❌ archive de la classe au quart d'heure non montée sur R2 "
              "(conservée localement)", file=sys.stderr)
        return 2
    print(f"  témoin posé : {temoin(path).name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
