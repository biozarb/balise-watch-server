#!/usr/bin/env python3
"""Lot L11 — SONDE : le pas de 15 min est-il SERVABLE, et par qui ?

⛔ CE QUE CETTE SONDE RÉPOND, ET POURQUOI ELLE PASSE AVANT LE CODE.
La réserve de la phase B est écrite depuis le 26/08 : « c'est à :15,
:30 et :45 que le composite justifie son existence — là, l'alternative
n'est pas AROME, c'est AROME *interpolé* ». Le lot L11 veut la fermer.
Mais l'audit (§3.4) a posé une condition, et le lot la répète : **le
n_obs par point est plus faible, et il faut le DÉNOMBRER AVANT.**

⭐ L'ARGUMENT D'INDÉPENDANCE — ÉCRIT AVANT LA PREMIÈRE LIGNE, COMME LE
LOT L'EXIGE, ET IL EST ARITHMÉTIQUE, PAS EMPIRIQUE.

    Deux échéances consécutives séparées de `pas` secondes, chacune
    agrégeant les relevés d'une fenêtre CENTRÉE de demi-largeur `demi`,
    ne partagent aucun relevé si et seulement si :

                        2 × demi  <  pas

    C'est la raison, mot pour mot, de `scoring.OBS_HALF_WINDOW_MS` :
    « ±20 min plutôt que ±30 pour que deux heures consécutives ne
    partagent aucun relevé — condition d'indépendance du test apparié ».
    ±20 min sur un pas de 60 min : 40 < 60 ✅. ±20 min sur un pas de
    15 min : 40 > 15 ⛔ — chaque relevé compterait dans TROIS points, et
    les n annoncés seraient faux (l'audit §3.4 le dit ainsi).
    ±7 min sur un pas de 15 min : 14 < 15 ✅.

⛔⛔ CE QUE CET ARGUMENT NE DIT PAS, ET C'EST TOUT L'OBJET DE LA SONDE.
Il garantit qu'on ne compte pas deux fois. Il ne garantit RIEN sur le
fait qu'il y ait quelque chose à compter. Une fenêtre de ±7 min sur un
réseau qui reporte toutes les heures est VIDE 5 fois sur 6 — et une
classe dont les points sont vides ne mesure rien du tout, elle se tait.
La question de fait est donc : **sur la population RÉELLE de la classe
courte, combien de relevés tombent dans une fenêtre de ±7 min autour de
:15, :30 et :45 ?**

⚠️ ET LA POPULATION A CHANGÉ DEPUIS LA MESURE DE L'AUDIT. Le « pas
médian 5 min » du §3.4 a été mesuré sur **576 balises Pioupiou**
(`obs/`, journée du 25/08). Depuis, le lot L7 a étendu l'axe à ~1 100
balises, et le verdict L10 relève, sur l'échantillon lu de la classe
courte : « infoclimat 656, mf 190, aemet 154 ». Ces réseaux-là n'ont
jamais eu la cadence de Pioupiou. **Transporter les 5 min de Pioupiou
sur la population d'aujourd'hui serait exactement la faute que ce
chantier nomme depuis le début : un chiffre plausible, non mesuré, et
faux.** Cette sonde remesure sur la population qui EXISTE.

À lancer SUR LE VPS (les archives y vivent), en LECTURE SEULE :
    ~/venv-balise/bin/python3 model-verif/sonde_pas_15min_l11.py \
        [--jours 20] [--rapport /tmp/rapport-l11.txt]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import gzip
import json
import pathlib
import statistics
import sys

RACINE = pathlib.Path("/var/lib/bw-model-verif")

#: Les six flux d'observation, et leur préfixe d'archive. ⓘ `obs/` est
#: Pioupiou SEUL (décision 1 du cadrage S0.2) ; les cinq autres ont
#: chacun leur clé. Les mélanger ici les mélangerait dans le verdict,
#: alors que c'est précisément leur DIFFÉRENCE de cadence qu'on mesure.
FLUX = {
    "pioupiou": "obs/{a}/{m}/obs_{j}.ndjson.gz",
    "windsmobi": "obswindsmobi/{a}/{m}/obswindsmobi_{j}.ndjson.gz",
    "infoclimat": "obsinfoclimat/{a}/{m}/obsinfoclimat_{j}.ndjson.gz",
    "mf": "obsmf/{a}/{m}/obsmf_{j}.ndjson.gz",
    "aemet": "obsaemet/{a}/{m}/obsaemet_{j}.ndjson.gz",
    "metar": "obsmetar/{a}/{m}/obsmetar_{j}.ndjson.gz",
}

#: Les deux instants de décision de la classe courte (L10, MESURÉS).
T_MATIN, T_APREM = dt.time(6, 50), dt.time(12, 50)

#: La portée servie par instant T : six heures rondes STRICTEMENT après
#: T. ⛔ Ce n'est pas un réglage : PI ne porte que six échéances.
HEURES_CIBLES = 6

#: Les demi-fenêtres mises à l'épreuve, en secondes. ±7 min est celle
#: que l'audit §3.4 propose ; les deux autres bornent la question (±7,5
#: est le maximum STRICT admissible — au-delà les fenêtres se touchent).
DEMI_FENETRES = (300, 420, 449)

#: La demi-fenêtre du dispositif actuel (`scoring.OBS_HALF_WINDOW_MS`),
#: recopiée pour que la sonde soit lisible seule.
DEMI_ACTUELLE = 20 * 60


def cibles(jour: dt.date, pas_min: int) -> list[tuple[str, int, bool]]:
    """`[(instant_T, epoch_s, ronde?)]` — les échéances de la classe.

    ⛔ « STRICTEMENT APRÈS T », comme `agrume_court.heures_cibles`. Une
    échéance déjà passée à T n'est pas une prévision, c'est un constat.
    On reprend la MÊME règle plutôt que d'en réécrire une voisine : deux
    définitions du même cadre finissent toujours par diverger.
    """
    out = []
    for T in (T_MATIN, T_APREM):
        t0 = dt.datetime.combine(jour, T, tzinfo=dt.timezone.utc)
        h0 = t0.replace(minute=0, second=0, microsecond=0) + dt.timedelta(hours=1)
        fin = h0 + dt.timedelta(hours=HEURES_CIBLES - 1)
        t = h0
        while t <= fin:
            out.append((f"{T:%H:%M}", int(t.timestamp()), t.minute == 0))
            t += dt.timedelta(minutes=pas_min)
    return out


def lire(jour: dt.date, flux: str) -> list[dict]:
    p = RACINE / FLUX[flux].format(a=f"{jour:%Y}", m=f"{jour:%m}", j=f"{jour:%Y-%m-%d}")
    if not p.exists():
        return []
    return [json.loads(l) for l in gzip.open(p, "rt") if l.strip()]


def population_courte(jour: dt.date) -> dict[str, str] | None:
    """`{station_id: source}` de la classe courte, LU DANS SON ARCHIVE.

    ⛔ On ne RECONSTRUIT pas la population : on la lit là où elle a été
    écrite. La reconstruire supposerait qu'on sait quels filtres
    `score.py` applique — or le verdict L10 relève justement un écart
    non expliqué (1 104 servies, 940 retenues). Une sonde qui déduit la
    population mesurerait une population qui n'existe pas.
    """
    p = (RACINE / "fcstagrumecourt" / f"{jour:%Y}" / f"{jour:%m}"
         / f"fcstagrumecourt_{jour:%Y-%m-%d}.ndjson.gz")
    if not p.exists():
        return None
    out: dict[str, str] = {}
    for l in gzip.open(p, "rt"):
        if not l.strip():
            continue
        r = json.loads(l)
        out[str(r["station_id"])] = r.get("source") or "?"
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jours", type=int, default=20)
    ap.add_argument("--rapport", default="/tmp/rapport-sonde-pas-15min-l11.txt")
    a = ap.parse_args()

    sortie: list[str] = []

    def dire(s=""):
        print(s)
        sortie.append(s)

    fin = dt.date.today() - dt.timedelta(days=1)
    jours = [fin - dt.timedelta(days=k) for k in range(a.jours)][::-1]

    # ── La population : celle de la classe courte, si son archive existe ──
    pop = None
    for j in jours[::-1]:
        pop = population_courte(j)
        if pop:
            dire(f"▶ population : celle de la classe courte du {j} — "
                 f"{len(pop)} balises")
            break
    if not pop:
        dire("⛔ aucune archive de classe courte trouvée : la sonde "
             "mesurerait une population imaginaire. Arrêt.")
        return 1
    par_source = collections.Counter(pop.values())
    dire("  par réseau : " + " · ".join(f"{s} {n}" for s, n in
                                        par_source.most_common()))
    dire()

    # ══ 1. LA CADENCE RÉELLE, PAR RÉSEAU, SUR CETTE POPULATION ══════════
    dire("═" * 68)
    dire(" 1. CADENCE DE REPORT — mesurée sur la population de la classe")
    dire("═" * 68)
    ecarts: dict[str, list[float]] = collections.defaultdict(list)
    n_balises_vues: dict[str, set] = collections.defaultdict(set)
    for j in jours:
        for flux in FLUX:
            for r in lire(j, flux):
                sid = str(r["station_id"])
                if sid not in pop:
                    continue
                t = sorted(int(x) for x in (r.get("t") or []))
                if len(t) < 3:
                    continue
                n_balises_vues[flux].add(sid)
                d = [t[i + 1] - t[i] for i in range(len(t) - 1)]
                ecarts[flux].append(statistics.median(d) / 60.0)
    dire(f"{'réseau':<12} {'balises':>8} {'bal.-jours':>11} "
         f"{'pas médian':>11} {'d1':>6} {'d9':>6}  {'≤7,5 min':>9}")
    for flux in FLUX:
        e = ecarts[flux]
        if not e:
            dire(f"{flux:<12} {'—':>8} {'0':>11}   (aucune balise de la "
                 f"classe dans ce flux)")
            continue
        e2 = sorted(e)
        q = lambda p: e2[min(len(e2) - 1, int(len(e2) * p))]  # noqa: E731
        part = 100.0 * sum(1 for x in e2 if x <= 7.5) / len(e2)
        dire(f"{flux:<12} {len(n_balises_vues[flux]):>8} {len(e2):>11} "
             f"{statistics.median(e2):>10.1f}′ {q(0.1):>5.1f}′ "
             f"{q(0.9):>5.1f}′  {part:>8.1f}%")
    dire()

    # ══ 2. n_obs PAR FENÊTRE — LE CHIFFRE QUE LE LOT EXIGE ══════════════
    dire("═" * 68)
    dire(" 2. n_obs PAR ÉCHÉANCE — ce que le pas de 15 min trouverait")
    dire("═" * 68)
    dire("⛔ Une fenêtre VIDE n'est pas un petit n : c'est une échéance")
    dire("   ABSENTE du résultat (`pair_series` ne comble jamais). Le")
    dire("   taux de fenêtres non vides est donc le vrai plafond de la")
    dire("   classe, et le plancher se compte dessus.")
    dire()
    # {(demi, ronde?, flux): [n_obs par fenêtre]}
    compte: dict[tuple, list[int]] = collections.defaultdict(list)
    # {(demi, T, jour, sid): nb d'échéances servies} — pour le plancher
    servies: dict[tuple, int] = collections.Counter()
    #: Idem, mais sur les QUARTS SEULS — le périmètre tranché par Yann
    #: le 31/08. 15 échéances par instant T (:15/:30/:45 de 07:15 à
    #: 11:45), les heures rondes restant la propriété de la classe
    #: horaire pour qu'aucun instant ne soit noté deux fois.
    servies_q: dict[tuple, int] = collections.Counter()
    # Contrôle de disjonction : {(demi, jour, sid): [indices de fenêtre]}
    partages: dict[int, int] = collections.Counter()
    #: Horodatages en DOUBLE dans la série d'une balise — trouvé en
    #: écrivant le contrôle de disjonction, et sans rapport avec lui.
    doubles: dict[str, int] = collections.Counter()
    n_releves: dict[str, int] = collections.Counter()
    obs_par_jour_sid: dict[tuple, list[int]] = {}
    for j in jours:
        for flux in FLUX:
            for r in lire(j, flux):
                sid = str(r["station_id"])
                if sid not in pop:
                    continue
                ts = sorted(int(x) for x in (r.get("t") or []))
                sp = r.get("speed") or []
                if not ts:
                    continue
                # ⚠️ On compte les relevés qui ont une VITESSE : c'est ce
                # que `mean_wind` exige. Compter les horodatages nus
                # surestimerait la matière, du bon ordre de grandeur pour
                # passer inaperçu.
                ordre = sorted(range(len(r.get("t") or [])),
                               key=lambda i: int(r["t"][i]))
                ts = [int(r["t"][i]) for i in ordre
                      if i < len(sp) and sp[i] is not None]
                if not ts:
                    continue
                obs_par_jour_sid[(j, sid)] = ts
                n_releves[flux] += len(ts)
                # ⛔ LE CONTRÔLE PORTE SUR LES RELEVÉS, PAS SUR LEURS
                # HORODATAGES. Première version de cette sonde : elle
                # comptait les VALEURS de `t` vues dans plus d'une
                # fenêtre — et elle a crié « ⛔ 467 partages » sur la
                # classe HORAIRE, là où ±20′ contre un pas de 60′ rend
                # le partage arithmétiquement impossible. Ce n'étaient
                # pas des partages : c'étaient des horodatages EN DOUBLE
                # dans la série d'une même balise, comptés deux fois
                # dans UNE seule fenêtre. Le défaut est réel (§ ci-
                # dessous), mais ce n'est pas celui-ci — et une sonde qui
                # confond les deux condamnerait le pas de 15 min pour la
                # faute d'un autre.
                doubles[flux] += len(ts) - len(set(ts))
                for demi in DEMI_FENETRES:
                    vus: dict[int, int] = collections.Counter()
                    for T, epoch, ronde in cibles(j, 15):
                        dedans = [i for i, t in enumerate(ts)
                                  if abs(t - epoch) <= demi]
                        compte[(demi, ronde, flux)].append(len(dedans))
                        if dedans:
                            servies[(demi, T, j, sid)] += 1
                            if not ronde:
                                servies_q[(demi, T, j, sid)] += 1
                            for i in dedans:
                                vus[i] += 1
                    partages[demi] += sum(1 for v in vus.values() if v > 1)
    for demi in DEMI_FENETRES:
        dire(f"── demi-fenêtre ±{demi // 60}′{demi % 60:02d}″ "
             f"(2×{demi}s = {2 * demi}s {'<' if 2 * demi < 900 else '≥'} "
             f"900s : fenêtres {'DISJOINTES' if 2 * demi < 900 else 'QUI SE TOUCHENT ⛔'})")
        dire(f"   {'réseau':<12} {'échéance':<12} {'fen. non vides':>15} "
             f"{'n_obs médian':>13} {'n_obs moyen':>12}")
        for flux in FLUX:
            for ronde, nom in ((True, ":00 (ronde)"), (False, ":15/:30/:45")):
                v = compte.get((demi, ronde, flux))
                if not v:
                    continue
                nz = [x for x in v if x]
                dire(f"   {flux:<12} {nom:<12} "
                     f"{100.0 * len(nz) / len(v):>14.1f}% "
                     f"{(statistics.median(nz) if nz else 0):>13.1f} "
                     f"{(sum(nz) / len(nz) if nz else 0):>12.2f}")
        dire(f"   ⭐ relevés comptés dans PLUS D'UNE fenêtre : "
             f"{partages[demi]} "
             f"{'✅ (disjonction vérifiée empiriquement)' if not partages[demi] else '⛔'}")
        dire()

    # ══ 3. LE PLANCHER — combien d'échéances par balise-jour-T ══════════
    dire("═" * 68)
    dire(" 3. LE PLANCHER — 21 échéances visées par instant T")
    dire("═" * 68)
    dire("⛔ `score.MIN_HOURS_DAILY = 6` se compte en points APPARIÉS. À")
    dire("   21 points visés, un plancher de 6 serait 3,5× plus laxiste")
    dire("   qu'aux heures rondes (6 sur 6). Le chiffre ci-dessous dit ce")
    dire("   qu'un plancher HONNÊTE pourrait valoir — il ne le choisit pas.")
    dire()
    for demi in DEMI_FENETRES:
        vals = [n for (d, _T, _j, _s), n in servies.items() if d == demi]
        if not vals:
            continue
        v = sorted(vals)
        q = lambda p: v[min(len(v) - 1, int(len(v) * p))]  # noqa: E731
        dire(f"   ±{demi // 60}′{demi % 60:02d}″ : {len(v)} balise-jour-T · "
             f"médiane {statistics.median(v):.0f}/21 · d1 {q(0.1)} · "
             f"d9 {q(0.9)} · "
             f"≥18/21 : {100.0 * sum(1 for x in v if x >= 18) / len(v):.1f}% · "
             f"≥12/21 : {100.0 * sum(1 for x in v if x >= 12) / len(v):.1f}% · "
             f"≥6/21 : {100.0 * sum(1 for x in v if x >= 6) / len(v):.1f}%")
    dire()
    dire("   ── LE PÉRIMÈTRE TRANCHÉ : LES 15 QUARTS SEULS ──")
    dire("   ⓘ Une balise-jour-T ABSENTE de ce compte n'a servi aucun")
    dire("     quart : elle n'est pas à 0/15, elle n'existe pas. Les")
    dire("     deux se lisent pareil dans un pourcentage, et pas dans")
    dire("     un dénominateur — d'où la colonne « balise-jour-T ».")
    for demi in DEMI_FENETRES:
        vals = [n for (d, _T, _j, _s), n in servies_q.items() if d == demi]
        if not vals:
            continue
        v = sorted(vals)
        q = lambda p: v[min(len(v) - 1, int(len(v) * p))]  # noqa: E731
        dire(f"   ±{demi // 60}'{demi % 60:02d}\" : {len(v)} balise-jour-T · "
             f"médiane {statistics.median(v):.0f}/15 · d1 {q(0.1)} · "
             f"d9 {q(0.9)} · "
             + " · ".join(f">={k}/15 : {100.0 * sum(1 for x in v if x >= k) / len(v):.1f}%"
                          for k in (14, 13, 12, 11, 8)))
    dire()

    # ══ 4. LE TÉMOIN — ce que la classe HORAIRE obtient aujourd'hui ═════
    dire("═" * 68)
    dire(" 4. TÉMOIN — la classe horaire d'aujourd'hui (±20′, 6 heures)")
    dire("═" * 68)
    dire("ⓘ Sans ce témoin, les taux ci-dessus n'ont pas d'échelle : on")
    dire("  ne saurait pas si un point sur deux servi est bon ou mauvais.")
    temoin: dict[str, list[int]] = collections.defaultdict(list)
    temoin_plancher: dict[tuple, int] = collections.Counter()
    temoin_partages = 0
    for (j, sid), ts in obs_par_jour_sid.items():
        flux = pop.get(sid, "?")
        vus: dict[int, int] = collections.Counter()
        for T, epoch, ronde in cibles(j, 60):
            dedans = [i for i, t in enumerate(ts)
                      if abs(t - epoch) <= DEMI_ACTUELLE]
            temoin[flux].append(len(dedans))
            if dedans:
                temoin_plancher[(T, j, sid)] += 1
                for i in dedans:
                    vus[i] += 1
        temoin_partages += sum(1 for v in vus.values() if v > 1)
    dire(f"   {'réseau':<12} {'fen. non vides':>15} {'n_obs médian':>13}")
    for flux in FLUX:
        v = temoin.get(flux)
        if not v:
            continue
        nz = [x for x in v if x]
        dire(f"   {flux:<12} {100.0 * len(nz) / len(v):>14.1f}% "
             f"{(statistics.median(nz) if nz else 0):>13.1f}")
    vals = sorted(temoin_plancher.values())
    if vals:
        dire(f"   heures servies par balise-jour-T : médiane "
             f"{statistics.median(vals):.0f}/6 · "
             f"≥6/6 : {100.0 * sum(1 for x in vals if x >= 6) / len(vals):.1f}%")
    dire(f"   ⭐ relevés partagés entre deux heures rondes à ±20′ : "
         f"{temoin_partages} "
         f"{'✅' if not temoin_partages else '⛔ (l’indépendance actuelle serait en cause)'}")
    dire()

    # ══ 5. TROUVÉ SANS LE CHERCHER — les horodatages en DOUBLE ═════════
    dire("=" * 68)
    dire(" 5. ⛔ TROUVÉ EN CHEMIN — des horodatages EN DOUBLE dans obs")
    dire("=" * 68)
    dire("Le premier jet de cette sonde a crié « partage » sur la classe")
    dire("HORAIRE, où ±20' contre un pas de 60' rend le partage")
    dire("arithmetiquement impossible. La cause n'etait pas le partage :")
    dire("c'est le MEME horodatage present deux fois dans la serie d'une")
    dire("balise. `scoring.mean_wind` le moyenne alors deux fois, et le")
    dire("`n_obs` publie est gonfle d'autant. Sans rapport avec le pas de")
    dire("15 min — mais il vit dans la classe horaire d'aujourd'hui.")
    dire()
    for flux in FLUX:
        if not n_releves.get(flux):
            continue
        dire(f"   {flux:<12} {doubles[flux]:>7} doublons / "
             f"{n_releves[flux]:>8} releves  "
             f"({100.0 * doubles[flux] / n_releves[flux]:.4f} %)")
    tot_d, tot_n = sum(doubles.values()), sum(n_releves.values())
    if tot_n:
        dire(f"   {'TOTAL':<12} {tot_d:>7} / {tot_n:>8}  "
             f"({100.0 * tot_d / tot_n:.4f} %)")
    dire()

    p = pathlib.Path(a.rapport)
    p.write_text("\n".join(sortie) + "\n", encoding="utf-8")
    print(f"\n▶ rapport écrit : {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
