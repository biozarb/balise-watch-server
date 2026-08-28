#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/filet_arome_wind.py — le filet sous l'Action `arome-wind`
#                                              (lot LW, 28/08/2026)
#
#  ⛔ CE QU'IL RÉPARE, ET IL FAUT LE CHIFFRE POUR COMPRENDRE L'HORAIRE.
#  Le 28/08/2026, `bw-model-arome` a échoué à 06:00 Z : les tuiles en
#  ligne portaient le run 27/08 21 Z, non admis. Cause mesurée le matin
#  même — AUCUN job n'avait échoué (0 échec d'`arome-wind` depuis le
#  13/08 sur 232 runs) : les passages programmés N'AVAIENT PAS EU LIEU.
#  Le planificateur de GitHub, qui avait tenu 96 créneaux sur 96 du 14
#  au 25/08, est tombé à 3 sur 11 à partir du 26/08 au soir, avec un
#  retard médian passé de ~30 min à ~140 min. Et il ne s'agissait pas
#  d'`arome-wind` : les SEPT workflows du dépôt se sont effondrés la
#  même nuit, `keepalive` de 18 passages/jour à 3.
#
#  ⇒ Ce script ne guette rien et ne calcule rien : il DÉCLENCHE, à une
#  heure que le VPS choisit. C'est la doctrine que `agrume/poller.py`
#  énonce déjà en tête (« VPS = détection et ordonnancement ; une GitHub
#  Action est un cron, elle ne peut pas guetter »), appliquée à une
#  seconde chaîne — et c'est le PLUS PETIT des trois remèdes examinés au
#  lot LW, choisi par Yann le 28/08.
#
#  ⚠️ CE N'EST PAS LE GARDE-FOU, ET LA DIFFÉRENCE COMPTE. Un garde-fou
#  LIRAIT les tuiles et n'agirait qu'en cas de manque ; celui-ci
#  déclenche à l'aveugle, tous les jours. Il coûte donc un run de runner
#  (gratuit, dépôt public) même les jours où GitHub fonctionne. En
#  échange il n'a aucune lecture R2 à réussir pour être utile — c'est
#  exactement ce qu'on veut d'un filet : moins de choses qui peuvent
#  casser que ce qu'il rattrape.
#
#  ── POURQUOI 05:00 Z, ET POURQUOI CE N'EST PAS UN CONFORT ────────────
#  `arome-wind/ingest.py::pick_run()` part de l'heure COURANTE arrondie
#  au multiple de 3 h inférieur, puis remonte de 3 h en 3 h. Entre
#  03:00 et 05:59 Z, ses deux premiers candidats sont donc 03 Z et
#  00 Z — et `arome_fcst.RUNS_ADMIS` les admet TOUS LES DEUX. Sur cette
#  plage, le tirage NE PEUT PAS mal tomber. À 06:00 Z il basculerait sur
#  06 Z, non admis.
#  L'autre borne vient de la durée : l'ingestion a pris 11 min 48 le
#  28/08 (12 à 19 min sur les runs récents), et `bw-model-arome` lit à
#  06:00 Z. 05:00 laisse ~45 min de marge.
#  ⓘ Et c'est l'heure du passage programmé qui MARCHAIT : le pavé de
#  `bw-model-arome.timer` a mesuré le 22/08 que celui de 05:00 Z retenait
#  le run 00 Z et écrivait ses tuiles entre 05:34 et 05:42 Z.
#
#  ⚠️ HORS DE CETTE PLAGE, ON AVERTIT — ON NE REFUSE PAS. Un filet qui
#  refuse de partir aurait bloqué le sauvetage du 28/08, qui a été lancé
#  à 07:57 Z et qui était le BON geste : à cette heure-là le run 06 Z
#  n'avait aucun fichier SP1 publié, `pick_run()` est donc retombé sur
#  03 Z. L'heure ne décide pas à la place de `pick_run()` ; elle dit
#  seulement si le coup est sûr ou s'il faut aller lire le journal.
#
#  ⚠️ `concurrency: cancel-in-progress: true` dans `arome-wind.yml` : si
#  un passage programmé démarre pendant celui-ci, il ANNULE celui-ci et
#  fait le même travail. Ce n'est donc pas une course perdante — mais
#  c'est la raison pour laquelle on ne déclenche pas « deux fois pour
#  être sûr » : la seconde tuerait la première.
# ══════════════════════════════════════════════════════════════════════
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

_ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_ICI, os.pardir, "tools"))

from gh_dispatch import cible, dispatch_github  # noqa: E402

#: La cible par défaut. ⓘ Même forme qu'`AGRUME_DISPATCH`
#: (`agrume/run-poller.sh` l. 41) : « dépôt:workflow ».
CIBLE_DEFAUT = "biozarb/balise-watch-server:arome-wind.yml"

#: ⚠️ DUPLIQUÉ depuis `arome_fcst.RUNS_ADMIS`, et sciemment.
#: L'importer obligerait ce filet à charger `arome_fcst`, donc `boto3`,
#: `collect` et `r2_lecture` — trois occasions de ne pas partir, pour un
#: script dont la seule vertu est de partir. C'est le même arbitrage que
#: `TILE_DEG` dans `arome_fcst.py`.
#: ⛔ ET LA PROTECTION N'EST PAS CE COMMENTAIRE : `test_filet_arome_wind.py`
#: importe le VRAI `arome_fcst` et refuse de passer si les deux tuples
#: divergent. Le jour où l'un bouge, c'est le banc qui le dit.
RUNS_ADMIS = (0, 3)

#: Durée d'ingestion observée (min/max sur les runs du 14 au 28/08) et
#: heure de lecture par `bw-model-arome`. Servent au message, pas au
#: calcul — un filet qui refuse de partir parce qu'il est 05:41 serait
#: une panne de plus, pas une sécurité.
INGESTION_MIN_MAX = (12, 19)
LECTURE_H = 6


def runs_candidats(maintenant):
    """Les deux premiers runs que `pick_run()` examinera à cet instant.

    Reproduit `arome-wind/ingest.py::pick_run()` l. 255-259 : l'heure
    courante arrondie au multiple de 3 h inférieur, puis un cran de 3 h
    en arrière. ⓘ On s'arrête à DEUX : au-delà, `pick_run()` ne descend
    que si les deux premiers sont vides, ce qui n'arrive pas dans la
    plage visée — et prétendre le contraire donnerait un message qui
    promet plus que ce qu'on a mesuré.
    """
    base = maintenant.replace(minute=0, second=0, microsecond=0)
    base = base.hour - (base.hour % 3)
    return (base, (base - 3) % 24)


def moment_sur(maintenant):
    """Vrai si les DEUX candidats sont admis — le tirage ne peut pas mal
    tomber. Rend aussi les candidats, pour que l'appelant les dise."""
    cands = runs_candidats(maintenant)
    return all(h in RUNS_ADMIS for h in cands), cands


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    # ⚠️ `--out` est imposé par `run.sh` à TOUS ses modes (l. 499). Ce
    # script n'écrit rien : il l'accepte et l'ignore, plutôt que de
    # faire une exception dans `run.sh` pour un seul mode — l'enveloppe
    # partagée vaut plus qu'un argument inutile.
    p.add_argument("--out", default=None,
                   help="ignoré (ce filet n'écrit aucun état)")
    p.add_argument("--cible", default=os.environ.get("BW_FILET_AROME_DISPATCH")
                   or CIBLE_DEFAUT,
                   help="« dépôt:workflow.yml » à déclencher")
    p.add_argument("--dry-run", action="store_true",
                   help="tout dire, ne rien déclencher")
    a = p.parse_args(argv)

    maintenant = datetime.now(timezone.utc)
    print(f"▶ filet AROME wind — {maintenant:%Y-%m-%dT%H:%M:%SZ}")

    try:
        depot, workflow = cible(a.cible)
    except ValueError as e:
        # ⛔ On sort en erreur AVANT tout réseau. Une cible illisible
        # POSTée quand même rendrait 404, qui ressemble à un problème de
        # droits — et on chercherait le jeton pendant une heure.
        print(f"  ❌ {e}")
        return 2

    sur, cands = moment_sur(maintenant)
    print(f"  cible : {depot} → {workflow}")
    print(f"  runs que pick_run() examinera : "
          + ", ".join(f"{h:02d} Z" for h in cands)
          + f" (admis : {', '.join(f'{h:02d} Z' for h in RUNS_ADMIS)})")
    if sur:
        print(f"  ⭐ moment SÛR : les deux candidats sont admis. Ingestion "
              f"{INGESTION_MIN_MAX[0]}-{INGESTION_MIN_MAX[1]} min, lecture "
              f"par bw-model-arome à {LECTURE_H:02d}:00 Z.")
    else:
        # ⚠️ Un avertissement, pas un refus — voir le pavé d'en-tête.
        print("  ⚠️ MOMENT NON SÛR : au moins un des deux candidats n'est "
              "pas un run admis. Le déclenchement part quand même — c'est "
              "`pick_run()` qui tranche, sur la couverture RÉELLEMENT "
              "publiée — mais il faudra LIRE le journal du run pour "
              "savoir ce qu'il a retenu.")

    if a.dry_run:
        print("  ⓘ --dry-run : rien n'a été déclenché")
        return 0

    if not dispatch_github(depot, workflow, crier=print):
        # ⛔ SORTIE NON NULLE. Un filet qui n'a pas pu se déployer et qui
        # rendrait 0 est pire que pas de filet : `run.sh` écrirait
        # « OK », Healthchecks passerait au vert, et on croirait la
        # chaîne protégée le matin où elle ne l'est pas.
        print("  ❌ le filet n'a PAS été déployé ce matin — l'Action "
              "`arome-wind` n'a donc reçu aucun ordre. Si aucun passage "
              "programmé ne tombe avant 06:00 Z, la journée est perdue "
              "pour arome_r2.")
        return 1

    print("  ⓘ le dispatch est ACCEPTÉ, pas encore RÉUSSI : ce filet ne "
          "relit pas les tuiles. C'est `bw-model-arome` à 06:00 Z qui "
          "dira si la journée est sauvée.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
