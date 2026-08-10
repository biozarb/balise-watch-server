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

exec python3 -u "$ICI/poller.py" --source "$SOURCE" --boucle
