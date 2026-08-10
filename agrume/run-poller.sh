#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  run-poller.sh — lance le guet AGRUME sur le VPS      (10/08/2026)
#
#  ⚠️ POURQUOI CE WRAPPER EXISTE PLUTÔT QU'UN ExecStart DIRECT.
#  `~/.balise-watch-model-verif.env` est écrit en `export VAR=…`, une
#  syntaxe que systemd NE SAIT PAS lire dans un EnvironmentFile. La
#  leçon est déjà payée par `model-verif/run.sh` : c'est le script qui
#  source, pas l'unité.
#
#  ⚠️ LA CLÉ NE S'AFFICHE JAMAIS. Pas de `set -x` ici, et le poller ne
#  l'imprime pas, pas même tronquée.
#
#  Usage :  ./run-poller.sh aromepi
#           ./run-poller.sh arome
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

SOURCE="${1:-aromepi}"
ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${BW_MF_ENV:-$HOME/.balise-watch-model-verif.env}"

if [ -r "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
elif [ "$SOURCE" != "arome" ] && [ "$SOURCE" != "arome-paquets" ]; then
  # ⚠️ Seules les sources qui passent par le MIROIR S3 (`arome`,
  # `arome-paquets`) se passent de clé — le miroir est public. Pour le
  # portail, mieux vaut refuser de démarrer que tourner en boucle sur
  # des erreurs d'authentification : un service qui redémarre toutes
  # les cinq secondes ressemble à un service qui marche.
  echo "❌ $ENV_FILE illisible — la source '$SOURCE' passe par le portail" >&2
  exit 78   # EX_CONFIG
fi

# ⚠️ LE DÉCLENCHEMENT EST OPTIONNEL, ET SON ABSENCE SE DIT.
# `AGRUME_DISPATCH` (posé dans le .env, par exemple
# `biozarb/balise-watch-server:agrume-colonnes.yml`) fait déclencher
# l'Action dès que les paquets guettés sont publiés. Sans lui, le poller
# DATE les runs sans rien lancer — mode de fonctionnement légitime, mais
# à ne pas confondre avec « la chaîne tourne ». Le poller le dit
# lui-même dans ses logs si `GITHUB_DISPATCH_TOKEN` manque.
#
# ⚠️⚠️ MAIS SEULES LES SOURCES QUI CONDITIONNENT L'INGESTION DÉCLENCHENT.
# Le `.env` est LU PAR TOUS LES SERVICES : poser `AGRUME_DISPATCH` dedans
# le rend visible aussi bien du guet AROME-PI que de celui des paquets
# AROME. Or le produit A ne dépend QUE des quatre paquets AROME —
# laisser PI déclencher lancerait un run de 7 Go **vingt-quatre fois par
# jour** pour rien, et réécrirait indéfiniment les mêmes archives.
# (Défaut introduit puis corrigé le 10/08, avant qu'un seul run ne parte.)
# Le composite PI, lui, est l'étape 9 : il aura sa propre chaîne et son
# propre déclencheur le jour où il existera.
case "$SOURCE" in
  arome|arome-paquets) DECLENCHE="${AGRUME_DISPATCH:-}" ;;
  *)                   DECLENCHE="" ;;
esac

if [ -n "$DECLENCHE" ]; then
  exec python3 -u "$ICI/poller.py" --source "$SOURCE" --boucle \
       --dispatch "$DECLENCHE"
fi

exec python3 -u "$ICI/poller.py" --source "$SOURCE" --boucle
