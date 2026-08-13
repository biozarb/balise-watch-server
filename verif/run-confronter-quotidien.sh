#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  run-confronter-quotidien.sh — la confrontation ballon, une fois par
#                                 jour, sur le VPS               (13/08/2026)
#
#  Même motif que `run-ingest-pi.sh`/`run-poller.sh`, pour la même
#  raison payée deux fois : `~/.balise-watch-*.env` est écrit en
#  `export VAR=…`, une syntaxe que systemd NE SAIT PAS lire dans un
#  EnvironmentFile. C'est le script qui source, jamais l'unité.
#
#  ⚠️ IL FAUT LIRE R2, PAS ÉCRIRE. `verif/sonder.py::depuis_r2` fait un
#  GET sur `agrume/colonnes/<run>/…` — mesuré le 13/08 (cf. CLAUDE.md) :
#  le jeton ordinaire du VPS ne sait qu'ÉCRIRE (403 sur Get, List ET
#  Delete). Ce script charge donc le jeton d'AUDIT, PAS
#  `~/.balise-watch-agrume-r2.env` (celui-là n'a que Put).
#  ⛔⛔ ACTION YANN si ce fichier n'existe pas encore sous ce nom :
#  créer `~/.balise-watch-r2-audit.env` (mode 600) avec R2_ACCOUNT_ID,
#  R2_ACCESS_KEY_ID/R2_SECRET_ACCESS_KEY du jeton `BW_R2_AUDIT_*` déjà
#  utilisé par `sonde_r2.py`/l'audit — ou pointer BW_R2_AUDIT_ENV sur le
#  fichier existant s'il porte déjà ces identifiants sous un autre nom.
#
#  Usage :  ./run-confronter-quotidien.sh              # confronte la veille
#           ./run-confronter-quotidien.sh --date 2026-08-10
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${BW_PYTHON:-python3}"
ALERTES_FILE="${BW_ALERTES_ENV:-$HOME/.balise-watch-alertes.env}"
AUDIT_FILE="${BW_R2_AUDIT_ENV:-$HOME/.balise-watch-r2-audit.env}"

# shellcheck source=/dev/null
[ -r "$ALERTES_FILE" ] && . "$ALERTES_FILE"
PING="${BW_AGRUME_CONFRONTATION_PING_URL:-}"

dire() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }

pinguer() {
  [ -n "$PING" ] || return 0
  curl -fsS -m 10 --retry 2 --data-binary "${2:-}" "${PING}$1" >/dev/null 2>&1 \
    || dire "⚠️ ping '$1' non parti (réseau ?) — le check passera en retard"
}

if [ -z "$PING" ]; then
  dire "⚠️ BW_AGRUME_CONFRONTATION_PING_URL absente de $ALERTES_FILE — PERSONNE NE SURVEILLE CETTE CHAÎNE"
fi

if [ ! -r "$AUDIT_FILE" ]; then
  dire "❌ $AUDIT_FILE illisible — la confrontation a besoin du jeton R2 EN LECTURE (BW_R2_AUDIT_*, cf. l'en-tête)"
  pinguer /fail "fichier d'environnement illisible : $AUDIT_FILE"
  exit 78   # EX_CONFIG
fi
set -a
# shellcheck source=/dev/null
. "$AUDIT_FILE"
set +a

export STORAGE_BACKEND=r2
export R2_BUCKET="${AGRUME_R2_BUCKET:-balise-watch-grids}"
export PYTHONUNBUFFERED=1

"$PY" "$ICI/confronter_quotidien.py" "$@"
code=$?

if [ "$code" -eq 0 ]; then
  pinguer "" "confrontation quotidienne écrite"
else
  pinguer /fail "confronter_quotidien.py a rendu le code $code"
fi
exit "$code"
