#!/usr/bin/env python3
"""Lot L10 — SONDE : que peut-on savoir à l'instant T ?

⛔ CE QUE CETTE SONDE RÉPOND, ET POURQUOI ELLE PASSE AVANT LE CODE.
Le cadre 2 note « ce que tu pouvais savoir à l'instant T ». Tout le lot
repose donc sur une question de fait : à 06:30 Z et à 12:30 Z, quel run
AROME et quel run AROME-PI sont RÉELLEMENT dans notre archive ? Et
combien d'heures cibles ces runs couvrent-ils, face au plancher
`MIN_HOURS_DAILY = 6` (§6.2 de la conception : « 6 heures cibles par T,
aucune marge ») ?

⭐ LA MESURE EST LE `LastModified` DES OBJETS R2, PAS `genere_le`.
`genere_le` date la dernière PASSE d'écriture, et le filet de sécurité
réécrit un manifeste à l'identique quelques heures plus tard (§1.2 de
la conception : il surestimait de 2 h). Le `LastModified` de l'objet,
lui, dit quand NOS octets ont été posés — c'est-à-dire exactement
l'instant à partir duquel un lecteur aurait pu s'en servir. C'est la
seule horloge qui réponde à la question du cadre 2.

⚠️ CE QUE CETTE SONDE NE PEUT PAS DIRE. Elle mesure le PLAFOND : les
heures que le modèle est capable d'offrir à T. Le plancher
`MIN_HOURS_DAILY` se compte en heures APPARIÉES (modèle ET observation).
La colonne « heures cibles couvertes » est donc un maximum ; le côté
observation ne peut que le faire baisser. Un plafond à 6 pile signifie
qu'une seule heure d'observation manquante fait tomber la journée.

À lancer SUR LE VPS (les jetons R2 y vivent) :
    set -a; . ~/.balise-watch-r2.env; . ~/.balise-watch-agrume-r2.env; set +a
    ~/venv-balise/bin/python3 model-verif/sonde_instants_t_l10.py [--jours 20]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import os
import re
import sys

BUCKET = os.environ.get("AGRUME_R2_BUCKET", "balise-watch-grids")
PREFIXE_AROME = "agrume/colonnes/"
PREFIXE_PI = "agrume/pi/colonnes/"

#: Les deux instants de décision tranchés par Yann le 30/08 (Q4).
INSTANTS_T = (dt.time(6, 30), dt.time(12, 30))

#: Le plancher du dispositif (`score.MIN_HOURS_DAILY`), recopié ici pour
#: que la sonde soit lisible seule — et vérifié à l'import plus bas.
MIN_HOURS_DAILY = 6

#: Combien d'heures cibles une classe courte peut viser par instant T.
#: ⛔ SIX, ET CE N'EST PAS UN CHOIX DE CETTE SONDE : AROME-PI ne porte
#: que 6 échéances (§3.2). Au-delà, on noterait de l'AROME pur sous une
#: étiquette PI — le défaut que la Q7 ferme.
HEURES_CIBLES = 6

#: Ce que PI couvre à partir de son propre run : H+1 … H+6.
PI_PORTEE_H = 6

RUN_RE = re.compile(r"(\d{4}-\d{2}-\d{2}T\d{2}):00:00Z/manifest\.json$")


def _client():
    import boto3
    manquants = [v for v in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID",
                             "R2_SECRET_ACCESS_KEY") if not os.environ.get(v)]
    if manquants:
        sys.exit("⛔ variables absentes : %s — sourcer les .env du VPS"
                 % ", ".join(manquants))
    return boto3.client(
        "s3",
        endpoint_url="https://%s.r2.cloudflarestorage.com"
                     % os.environ["R2_ACCOUNT_ID"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto")


def _runs(s3, prefixe: str, depuis: dt.datetime) -> dict[dt.datetime, dt.datetime]:
    """`{heure du run → instant où NOS octets ont été posés}`.

    ⚠️ On indexe sur `manifest.json` et non sur `colonnes.npz` : c'est le
    manifeste qui est écrit EN DERNIER (vu dans les deux préfixes, à
    quelques centaines de millisecondes), donc lui qui date le moment où
    la paire devient lisible. Prendre le `.npz` daterait un état
    incomplet — le piège que `_lire_paire_r2` nomme déjà côté lecture.
    """
    out: dict[dt.datetime, dt.datetime] = {}
    jeton = None
    while True:
        kw = {"Bucket": BUCKET, "Prefix": prefixe, "MaxKeys": 1000}
        if jeton:
            kw["ContinuationToken"] = jeton
        r = s3.list_objects_v2(**kw)
        for o in r.get("Contents", ()):
            m = RUN_RE.search(o["Key"])
            if not m:
                continue
            run = dt.datetime.strptime(m.group(1), "%Y-%m-%dT%H").replace(
                tzinfo=dt.timezone.utc)
            if run >= depuis:
                out[run] = o["LastModified"]
        if not r.get("IsTruncated"):
            return out
        jeton = r.get("NextContinuationToken")


def _heures_cibles(T: dt.datetime) -> list[dt.datetime]:
    """Les `HEURES_CIBLES` heures rondes STRICTEMENT APRÈS T.

    ⛔ « STRICTEMENT », ET C'EST TOUT LE CADRE 2. Une heure déjà
    commencée à T n'est pas une prévision : c'est un constat. L'inclure
    donnerait au dispositif un point qu'il n'a pas eu à prévoir, et le
    verdict du lot entier s'en trouverait flatté sans que rien ne le
    dise. Le cas limite compte : à T = 06:00 pile, l'heure 06 Z est
    ÉCARTÉE, pas gardée.
    """
    h0 = T.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
    return [h0 + dt.timedelta(hours=k) for k in range(HEURES_CIBLES)]


def _dernier_dispo(runs: dict, t: dt.datetime):
    """Le run le plus récent dont les octets étaient posés à `t`."""
    candidats = [(r, pose) for r, pose in runs.items() if pose <= t]
    return max(candidats, key=lambda p: p[0]) if candidats else (None, None)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jours", type=int, default=20)
    a = ap.parse_args()

    fin = dt.datetime.now(dt.timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0)
    debut = fin - dt.timedelta(days=a.jours)
    s3 = _client()
    arome = _runs(s3, PREFIXE_AROME, debut - dt.timedelta(days=2))
    pi = _runs(s3, PREFIXE_PI, debut - dt.timedelta(days=2))

    print("=" * 78)
    print("LOT L10 — SONDE DES DEUX INSTANTS T (cadre 2)")
    print("=" * 78)
    print("Fenêtre : %s → %s (%d journées) · bucket %s"
          % (debut.date(), fin.date(), a.jours, BUCKET))
    print("Horloge : `LastModified` de `manifest.json` sur R2 — l'instant")
    print("où NOS octets ont été posés, pas `genere_le`.")
    print()
    print("Runs AROME trouvés : %d · runs PI trouvés : %d" % (len(arome), len(pi)))
    par_jour_a = collections.Counter(r.date() for r in arome)
    par_jour_p = collections.Counter(r.date() for r in pi)
    if par_jour_a:
        print("  AROME : %.1f run/jour en moyenne (min %d, max %d)"
              % (sum(par_jour_a.values()) / len(par_jour_a),
                 min(par_jour_a.values()), max(par_jour_a.values())))
    if par_jour_p:
        print("  PI    : %.1f run/jour en moyenne (min %d, max %d)"
              % (sum(par_jour_p.values()) / len(par_jour_p),
                 min(par_jour_p.values()), max(par_jour_p.values())))
    print()

    bilan = {t: [] for t in INSTANTS_T}
    for i in range(a.jours):
        jour = (debut + dt.timedelta(days=i)).date()
        for heure_t in INSTANTS_T:
            T = dt.datetime.combine(jour, heure_t, tzinfo=dt.timezone.utc)
            ra, pose_a = _dernier_dispo(arome, T)
            rp, pose_p = _dernier_dispo(pi, T)
            # Les 6 heures cibles : celles qui SUIVENT T, heures rondes
            # (Q6). T = 06:30 → 07, 08, 09, 10, 11, 12 Z.
            cibles = _heures_cibles(T)
            # AROME porte +24 h depuis son run ; PI porte 6 échéances.
            couv_a = [h for h in cibles
                      if ra is not None and 0 < (h - ra).total_seconds() / 3600 <= 24]
            couv_pi = [h for h in cibles
                       if rp is not None
                       and 0 < (h - rp).total_seconds() / 3600 <= PI_PORTEE_H]
            deux = [h for h in couv_a if h in couv_pi]
            bilan[heure_t].append({
                "jour": jour, "run_a": ra, "age_a":
                    None if ra is None else (T - ra).total_seconds() / 3600,
                "retard_a":
                    None if ra is None else (pose_a - ra).total_seconds() / 3600,
                "run_pi": rp,
                "retard_pi":
                    None if rp is None else (pose_p - rp).total_seconds() / 3600,
                "n_a": len(couv_a), "n_pi": len(couv_pi), "n_deux": len(deux)})

    for heure_t in INSTANTS_T:
        print("─" * 78)
        print("T = %s Z — heures cibles %02d..%02d Z"
              % (heure_t.strftime("%H:%M"),
                 (heure_t.hour + 1) % 24,
                 (heure_t.hour + HEURES_CIBLES) % 24))
        print("─" * 78)
        print("  %-11s %-14s %6s %7s │ %-14s %7s │ %5s %5s %6s"
              % ("jour", "run AROME", "âge h", "posé+h", "run PI", "posé+h",
                 "AROME", "PI", "LES 2"))
        for l in bilan[heure_t]:
            print("  %-11s %-14s %6s %7s │ %-14s %7s │ %5d %5d %6d"
                  % (l["jour"],
                     l["run_a"].strftime("%m-%d %HZ") if l["run_a"] else "— AUCUN",
                     "%.0f" % l["age_a"] if l["age_a"] is not None else "—",
                     "%.1f" % l["retard_a"] if l["retard_a"] is not None else "—",
                     l["run_pi"].strftime("%m-%d %HZ") if l["run_pi"] else "— AUCUN",
                     "%.1f" % l["retard_pi"] if l["retard_pi"] is not None else "—",
                     l["n_a"], l["n_pi"], l["n_deux"]))
        n = len(bilan[heure_t])
        tenus = sum(1 for l in bilan[heure_t] if l["n_deux"] >= MIN_HOURS_DAILY)
        tenus_a = sum(1 for l in bilan[heure_t] if l["n_a"] >= MIN_HOURS_DAILY)
        med = sorted(l["n_deux"] for l in bilan[heure_t])[n // 2] if n else 0
        print()
        print("  ⇒ AROME seul  ≥ %d heures : %d/%d journées"
              % (MIN_HOURS_DAILY, tenus_a, n))
        print("  ⇒ AROME ET PI ≥ %d heures : %d/%d journées (médiane %d heures)"
              % (MIN_HOURS_DAILY, tenus, n, med))
        ages = [l["retard_a"] for l in bilan[heure_t] if l["retard_a"] is not None]
        if ages:
            ages.sort()
            print("  ⇒ retard médian de NOTRE archive AROME : %.1f h "
                  "(min %.1f, max %.1f)" % (ages[len(ages) // 2], ages[0], ages[-1]))
        agesp = [l["retard_pi"] for l in bilan[heure_t] if l["retard_pi"] is not None]
        if agesp:
            agesp.sort()
            print("  ⇒ retard médian de NOTRE archive PI    : %.1f h "
                  "(min %.1f, max %.1f)" % (agesp[len(agesp) // 2], agesp[0], agesp[-1]))
        print()
    # ══════════════════════════════════════════════════════════════
    #  LE BALAYAGE — parce que 06:30 et 12:30 sont un « p. ex. »
    # ══════════════════════════════════════════════════════════════
    # ⛔ LA CONCEPTION ÉCRIT « deux T par jour (p. ex. 06:30 et 12:30 Z) ».
    # Ce sont des exemples, pas une mesure. Si le tableau ci-dessus
    # montre un plafond à 5 heures, la question suivante n'est pas
    # « comment coder autour » mais « existe-t-il un T qui tient ? ».
    # On balaie donc les minutes, et on laisse les chiffres répondre.
    print("─" * 78)
    print("BALAYAGE — quel instant T tient le plancher de %d heures ?"
          % MIN_HOURS_DAILY)
    print("─" * 78)
    print("  ⓘ Sur les seules journées où l'archive AROME existe encore")
    print("    (rétention R2) ; PI, lui, remonte plus loin.")
    print()
    print("  %-13s │ %-26s │ %-26s" % ("T (Z)", "matin : journées ≥ 6 h",
                                       "après-midi : journées ≥ 6 h"))
    for minute in (0, 10, 20, 30, 40, 50):
        ligne = []
        for base in (6, 12):
            ok = tot = 0
            for i in range(a.jours):
                jour = (debut + dt.timedelta(days=i)).date()
                T = dt.datetime.combine(jour, dt.time(base, minute),
                                        tzinfo=dt.timezone.utc)
                ra, _ = _dernier_dispo(arome, T)
                rp, _ = _dernier_dispo(pi, T)
                if ra is None or rp is None:
                    continue          # archive purgée : la journée ne compte pas
                tot += 1
                cibles = _heures_cibles(T)
                n = sum(1 for h in cibles
                        if 0 < (h - ra).total_seconds() / 3600 <= 24
                        and 0 < (h - rp).total_seconds() / 3600 <= PI_PORTEE_H)
                ok += (n >= MIN_HOURS_DAILY)
            ligne.append("%d/%d journées" % (ok, tot) if tot else "aucune donnée")
        print("  %02d:%02d / %02d:%02d │ %-26s │ %-26s"
              % (6, minute, 12, minute, ligne[0], ligne[1]))
    print()
    print("  ⚠️ `h0` est ici la PREMIÈRE HEURE RONDE STRICTEMENT APRÈS T :")
    print("     c'est la règle du cadre 2 (on ne note pas une heure déjà")
    print("     commencée) et elle décide tout le tableau ci-dessus.")
    print()
    print("=" * 78)
    print("⚠️ RAPPEL : ces comptes sont un PLAFOND (le modèle). Le plancher")
    print("   MIN_HOURS_DAILY = %d se compte en heures APPARIÉES ; le côté" % MIN_HOURS_DAILY)
    print("   observation ne peut que faire baisser ces chiffres.")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
