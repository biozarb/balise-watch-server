#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  verif/purge.py — la rétention GLISSANTE du produit A     (13/08/2026)
#
#  ⛔⛔ LE RENONCEMENT A2, ÉCRIT ICI PARCE QUE C'EST ICI QU'IL SE PAIE.
#
#      À partir du jour où ce fichier tourne, ON RENONCE À RE-SCORER LE
#      PASSÉ AVEC UNE MÉTHODE FUTURE. Si une vérification v2 arrive un
#      jour, elle ne s'appliquera qu'aux runs postérieurs à son
#      déploiement — les colonnes d'avant n'existeront plus. Ce qu'on
#      veut pouvoir dire dans six mois doit donc vivre dans les SCORES,
#      qui ne se purgent jamais (`model_verif_daily`, `model_scores.json`
#      — 14 Mo pour tous les modèles depuis des mois), et pas dans
#      l'archive.
#
#  Ce prix a été présenté chiffré à Yann le 13/08 et accepté (arbitrages
#  A1 et A2 de `claude/roadmap-agrume-post-audit-13-08.md`). Il n'est pas
#  découvert, il est payé.
#
#  ── POURQUOI, ALORS QUE L'ARCHIVE NE PÈSE QUE 27 Mo ──────────────────
#  Mesuré le 13/08 sur R2 : le produit A pèse 27 Mo sur un compte de
#  2,57 Go (palier gratuit 10 Go), soit 1 %. L'urgence n'existe pas.
#  La TRAJECTOIRE, si : depuis la ligne de surface (étape 12 bis) un run
#  pèse 1,73 Mo, soit 13,9 Mo/jour à 8 runs/jour, soit **5,06 Go/an**.
#  À ce rythme le produit A devient le premier poste du compte en ~10
#  mois et fait déborder le palier au printemps 2027. Une rétention de
#  7 jours ramène le résident à ~100 Mo, stationnaires.
#
#  ⚠️ 7 jours, et pas 2 : le scoring a besoin d'horizon + ~24 h de marge
#  (≈ 48 h), et le diagnostic a déjà demandé 3 jours de recul une fois
#  (l'incident du front de Tarentaise). 7 jours laisse la semaine
#  courante rejouable ; le résident reste dérisoire.
#
#  ══════════════════════════════════════════════════════════════════
#  ⛔ LA DÉCISION D'ARCHITECTURE : ON BALAIE UNE FENÊTRE, ON NE VISE PAS
#     UN RUN. Et ce n'est pas une précaution théorique.
#  ══════════════════════════════════════════════════════════════════
#  `ListObjects` est hors de portée dans ce projet (facturé Class A ;
#  `storage.py::exists` LÈVE plutôt que de le laisser passer). La purge
#  ne peut donc pas demander au stockage ce qu'il contient : elle
#  RECONSTRUIT les clés par arithmétique de runs (8 réseaux par jour, à
#  heures fixes, la clé porte le run).
#
#  La version naïve serait « à chaque run, supprimer le run d'il y a
#  exactement N jours ». ⛔ Elle fabriquerait des orphelins DÉFINITIFS,
#  et le taux de fabrication est mesuré, pas supposé :
#
#      Sondé le 13/08 sur les 40 runs théoriques du 09 au 13/08 :
#      22 runs présents, et **2 TROUS à l'intérieur de l'intervalle**
#      (2026-08-10T21:00:00Z et 2026-08-11T21:00:00Z). Soit 8,3 % des
#      runs de la plage couverte. Une ingestion qui tombe, ça arrive
#      une fois tous les douze runs.
#
#  Un trou ne coûte rien à la purge naïve (supprimer une clé absente est
#  un succès chez R2). Ce qui coûte, c'est le SYMÉTRIQUE : le jour où la
#  purge ne tourne pas — Action en panne, poller mort, dépôt bloqué —
#  les runs de ce jour-là ne sont visés qu'UNE fois, et cette fois-là
#  est manquée. Sans `ListObjects`, ils deviennent alors invisibles ET
#  définitivement payés. C'est exactement la fuite qui a laissé 18
#  objets orphelins (24 Mo) sur la grille PI.
#
#  D'où la fenêtre : à chaque run, on balaie TOUS les runs théoriques de
#  `[maintenant − RETENTION − FENETRE, maintenant − RETENTION]`. Chaque
#  run théorique est donc visé **56 fois** (8/jour × 7 jours) avant de
#  sortir de la fenêtre. Pour qu'un objet s'échappe, il faudrait 56
#  purges consécutives manquées, c'est-à-dire **sept jours pleins sans
#  une seule ingestion réussie** — un état que le voyant Healthchecks
#  signale après ~6 h de silence. La borne de la fenêtre est donc
#  accrochée à une alarme qui existe, pas à un espoir.
#
#  ⚠️ CE QUE CETTE PURGE NE SAURA JAMAIS DIRE, et il faut le savoir :
#  `DeleteObject` rend un succès que la clé ait existé ou non. La purge
#  ne peut donc PAS compter ce qu'elle a réellement effacé, ni détecter
#  une fuite. Le compteur qu'elle publie est un compteur de TENTATIVES
#  et d'ÉCHECS, jamais de suppressions réelles — c'est écrit dans le
#  bilan pour que personne ne le lise autrement.
#  ⓘ Le détecteur de fuite, lui, existe déjà et il est ailleurs :
#  `tools/audit_r2.py` (jeton d'AUDIT, qui a le droit de lister) mesure
#  le résident par préfixe ET SA PENTE, et alerte AVANT le palier. Si
#  `balise-watch-grids:agrume` cesse de se stabiliser autour de ~100 Mo
#  sur `colonnes/`, c'est là que ça se verra.
#
#  ── OÙ ÇA TOURNE, ET POURQUOI PAS SUR LE VPS ─────────────────────────
#  ⛔ MESURÉ LE 13/08, opération par opération, pas déduit d'un code
#  d'erreur : le jeton R2 du VPS n'a que `PutObject` — 403 sur `Get`,
#  `List` ET `Delete`. **La purge de la grille PI n'a donc jamais rien
#  supprimé depuis le VPS**, en silence, pendant des semaines.
#  Le jeton des GitHub Actions, lui, SAIT supprimer — vérifié le 13/08
#  sur le produit B en ligne : l'index publié dit trois runs par domaine
#  et `restes = 0`, et les runs évincés (`…/12T18Z`, `…/12T15Z`) rendent
#  bien 404 quand les trois gardés rendent 200. Un `restes` qui se vide
#  est la seule preuve qu'une suppression a abouti, puisque
#  `index_apres_purge` n'y laisse que les ÉCHECS.
#  ⇒ Cette purge est appelée depuis `agrume/ingest_colonnes.py`, qui
#  tourne sur GitHub Actions. Elle ne doit PAS être branchée sur le VPS
#  tant que le jeton `Object Read & Write` demandé à Yann n'existe pas.
#
#  ── L'ORDRE, QUI N'EST PAS INTERCHANGEABLE ───────────────────────────
#      1. le produit A du run courant est écrit, et vérifié
#      2. ALORS seulement la purge tourne
#  Purger avant écrirait le cas où l'écriture échoue après une purge
#  réussie : on aurait perdu un run des deux côtés.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

# ⛔ ARBITRAGE A1 DE YANN, 13/08/2026. Ce n'est pas un réglage : le
# changer change ce que le projet CONSERVE, donc il repasse par Yann.
RETENTION_JOURS = 7

# La largeur du balayage SOUS la rétention, cf. l'en-tête. 7 jours =
# 56 passages par run théorique avant qu'il ne sorte de portée.
FENETRE_JOURS = 7

# ⚠️ Les huit réseaux AROME, à heures fixes. C'est CETTE liste qui rend
# la purge possible sans index : elle est l'arithmétique. Le banc vérifie
# qu'elle décrit bien l'archive réelle (les 22 runs sondés le 13/08
# tombent tous sur un multiple de 3 h).
HEURES_RESEAU = (0, 3, 6, 9, 12, 15, 18, 21)

PREFIXE_A = "agrume/colonnes/"

# ⛔⛔ LE GARDE-FOU N'EST PAS UN PRÉFIXE, C'EST UN MOTIF COMPLET — et la
# différence compte. Le produit B (`agrume/grille/…`) et surtout les
# colonnes AROME-PI (`agrume/pi/colonnes/…`, DÉFINITIVES) vivent dans le
# MÊME bucket. Un préfixe seul laisserait passer n'importe quoi qui
# commence pareil ; un motif ancré des deux bouts n'accepte qu'une clé
# dont le run est syntaxiquement un run et dont le nom d'objet est l'un
# des deux qu'on écrit. Une chaîne de run malformée ne peut donc pas se
# transformer en joker.
MOTIF_CLE = re.compile(
    r"^agrume/colonnes/"
    r"\d{4}-\d{2}-\d{2}T(?:00|03|06|09|12|15|18|21):00:00Z/"
    r"(?:colonnes\.npz|manifest\.json)$")

FORMAT_RUN = "%Y-%m-%dT%H:00:00Z"


class PurgeRefusee(Exception):
    """⚠️ Une purge qui doute s'ARRÊTE ENTIÈREMENT, elle ne supprime pas
    « ce qui est légitime » en continuant. Même règle que
    `grille.verifier_prefixe` : une seule clé douteuse arrête tout."""


def cles_du_run(run):
    """Les deux objets d'un run du produit A. ⚠️ Ils sont écrits par
    `ingest_colonnes.py` sous `agrume/colonnes/{run}/` — si cette
    disposition change, elle change ICI AUSSI ou la purge devient un
    générateur d'orphelins."""
    return [f"{PREFIXE_A}{run}/colonnes.npz",
            f"{PREFIXE_A}{run}/manifest.json"]


def fenetre(maintenant, retention_jours=RETENTION_JOURS,
            fenetre_jours=FENETRE_JOURS):
    """(borne_basse, borne_haute) — les deux instants qui bornent le
    balayage. `borne_haute` est la limite de rétention : rien au-dessus
    n'est touchable, jamais."""
    if retention_jours < 1:
        raise PurgeRefusee(
            f"rétention de {retention_jours} jour(s) : refusé. Le scoring "
            f"a besoin d'horizon + ~24 h de marge (≈ 48 h) ; une rétention "
            f"sous 2 jours détruirait la matière AVANT qu'elle soit notée.")
    if fenetre_jours < 1:
        raise PurgeRefusee(
            f"fenêtre de {fenetre_jours} jour(s) : refusé. Une fenêtre nulle "
            f"est la purge naïve « le run d'il y a exactement N jours », "
            f"celle qui fabrique des orphelins définitifs (cf. l'en-tête).")
    haute = maintenant - timedelta(days=retention_jours)
    return haute - timedelta(days=fenetre_jours), haute


def runs_theoriques(depuis, jusqua):
    """Tous les runs AROME théoriques de `]depuis, jusqua]`, du plus
    ancien au plus récent.

    ⚠️ THÉORIQUES : on ne sait pas lesquels existent, et c'est le point.
    Un run absent (8,3 % de la plage sondée le 13/08) donne une
    suppression qui réussit sans rien faire — inoffensif. C'est
    l'inverse qui serait grave."""
    t = depuis.replace(minute=0, second=0, microsecond=0)
    while t.hour not in HEURES_RESEAU:
        t += timedelta(hours=1)
    out = []
    while t <= jusqua:
        if t > depuis:
            out.append(t.strftime(FORMAT_RUN))
        t += timedelta(hours=1)
        while t.hour not in HEURES_RESEAU:
            t += timedelta(hours=1)
    return out


def cles_a_purger(maintenant, retention_jours=RETENTION_JOURS,
                  fenetre_jours=FENETRE_JOURS):
    basse, haute = fenetre(maintenant, retention_jours, fenetre_jours)
    cles = []
    for run in runs_theoriques(basse, haute):
        cles += cles_du_run(run)
    return cles


def verifier(cles, maintenant, retention_jours=RETENTION_JOURS):
    """⛔ LE GARDE-FOU, ET IL RECALCULE TOUT PLUTÔT QUE DE FAIRE CONFIANCE.

    Il ne relit pas la fenêtre qu'on vient de calculer : il ré-extrait le
    run de CHAQUE clé et vérifie lui-même qu'il est bien sous la limite
    de rétention. Un garde-fou qui fait confiance à son appelant garde
    exactement ce que son appelant garde — c'est-à-dire rien.

    Deux refus distincts, deux messages distincts :
      · une clé qui ne colle pas au motif → ce n'est pas du produit A ;
      · une clé trop RÉCENTE → c'est du produit A, mais encore vivant.
    """
    limite = maintenant - timedelta(days=retention_jours)
    intruses = [c for c in cles if not MOTIF_CLE.match(str(c))]
    if intruses:
        raise PurgeRefusee(
            f"purge refusée : {len(intruses)} clé(s) ne sont pas du produit A "
            f"— {intruses[:3]}. ⚠️ Le MÊME bucket porte le produit B "
            f"(`agrume/grille/…`, jetable) et les colonnes AROME-PI "
            f"(`agrume/pi/colonnes/…`, DÉFINITIVES). Une purge qui s'y "
            f"égarerait détruirait une archive irremplaçable, sans bruit.")
    trop_recentes = []
    for c in cles:
        run = str(c)[len(PREFIXE_A):].split("/")[0]
        if datetime.strptime(run, FORMAT_RUN).replace(
                tzinfo=timezone.utc) > limite:
            trop_recentes.append(c)
    if trop_recentes:
        raise PurgeRefusee(
            f"purge refusée : {len(trop_recentes)} clé(s) sont sous la "
            f"rétention de {retention_jours} jours (limite {limite:%Y-%m-%dT%H:%M:%SZ}) "
            f"— {trop_recentes[:3]}. ⚠️ Le scoring lit le produit A jusqu'à "
            f"~48 h en arrière : supprimer là-dedans ferait un trou dans "
            f"`model_verif_daily` que rien ne rattraperait (renoncement A2).")
    return True


def purger(store, maintenant=None, retention_jours=RETENTION_JOURS,
           fenetre_jours=FENETRE_JOURS, crier=print):
    """Balaie la fenêtre et rend un bilan MESURÉ.

    ⚠️ `tentees` n'est PAS un nombre de suppressions : `DeleteObject`
    réussit sur une clé absente. C'est le nombre de clés VISÉES. Le seul
    chiffre qui porte de l'information est `echecs`.

    ⚠️ Ne lève pas si une suppression échoue : `storage.Storage.delete`
    avale l'exception, journalise et rend `False`. Une purge n'est jamais
    bloquante (correctif du 30/07) — mais son échec est CRIÉ, parce qu'un
    échec silencieux de purge est précisément ce qui a laissé 18 objets
    orphelins sur la grille PI.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    basse, haute = fenetre(maintenant, retention_jours, fenetre_jours)
    runs = runs_theoriques(basse, haute)
    cles = [c for r in runs for c in cles_du_run(r)]
    verifier(cles, maintenant, retention_jours)

    echecs = [c for c in cles if not store.delete(c)]
    bilan = dict(retention_jours=retention_jours, fenetre_jours=fenetre_jours,
                 borne_basse=basse.strftime(FORMAT_RUN),
                 borne_haute=haute.strftime(FORMAT_RUN),
                 runs_theoriques=len(runs), cles_visees=len(cles),
                 echecs=len(echecs),
                 note=("`cles_visees` compte des TENTATIVES, pas des "
                       "suppressions : DeleteObject réussit sur une clé "
                       "absente. Le résident réel se lit dans "
                       "tools/audit_r2.py."))
    crier(f"▶ purge produit A : rétention {retention_jours} j · fenêtre "
          f"{fenetre_jours} j · {len(runs)} run(s) théorique(s) balayé(s) "
          f"de {bilan['borne_basse']} à {bilan['borne_haute']} "
          f"({len(cles)} clé(s) visée(s))")
    if echecs:
        crier(f"  ⚠️ {len(echecs)} suppression(s) EN ÉCHEC — {echecs[:3]}. "
              f"Ce n'est pas anodin : sans ListObjects, un objet non "
              f"supprimé devient invisible. Vérifier les droits du jeton "
              f"R2 (`agrume-sonde-r2.yml`) et le résident "
              f"(`tools/audit_r2.py`).")
    else:
        crier("  ✓ aucune suppression en échec ⓘ ce qui ne prouve PAS "
              "qu'il y avait quelque chose à supprimer")
    return bilan
