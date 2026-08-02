#!/bin/bash
# ══════════════════════════════════════════════════════════════════════
#  entretien.sh — enveloppe du run quotidien de backfill_packs.py
#  (02/08/2026). Lancé par launchd, jamais à la main en temps normal.
#
#  Ce que cette enveloppe apporte, et que le script Python ne fait pas :
#    · charge ~/.balise-watch-r2.env (les `export` ne survivent pas au
#      terminal — c'est la raison d'être du fichier) ;
#    · un verrou : deux runs simultanés doubleraient les écritures R2 ;
#    · un chien de garde : un run qui dépasse MAX_MINUTES est tué. Sans
#      ça, une plage bloquée peut tenir la machine jusqu'au run suivant ;
#    · un journal permanent, ROTATÉ (un log qui grossit sans fin finit
#      par être le problème qu'il devait aider à résoudre) ;
#    · le compte d'échecs CONSÉCUTIFS, et une alerte au deuxième.
#
#  ⚠️ CE QUE CETTE ENVELOPPE NE PEUT PAS DÉTECTER : sa propre absence.
#  Si launchd cesse d'appeler ce script, aucune ligne de ce fichier ne
#  s'exécutera pour le dire. Le vrai détecteur d'un job mort est
#  AILLEURS, et il est gratuit : chaque pack porte `genere_le` et sa
#  dernière date. Un pack qui n'avance plus se voit depuis le client
#  pilote, qui affiche « comparables jusqu'au … ». C'est le seul
#  témoin qui ne dépend pas du mécanisme qu'il surveille.
#
#  ⚠️ JAMAIS DEPUIS L'IP DE RENDER. Ce script tourne sur le poste de
#  Yann. Le quota Open-Meteo se compte par IP, et celle de Render porte
#  déjà la veille et le foehn en production.
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRACES="$(cd "$ICI/.." && pwd)"
ENV_FILE="${BW_ENV_FILE:-$HOME/.balise-watch-r2.env}"
ETAT="$HOME/.balise-watch-entretien"
LOG="$ETAT/entretien.log"
ECHECS="$ETAT/echecs_consecutifs"
DERNIER_OK="$ETAT/dernier_succes"
VERROU="$ETAT/verrou"
MAX_MINUTES="${BW_MAX_MINUTES:-180}"
MAX_LOG_MO=10

mkdir -p "$ETAT"

dire() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"; }

alerter() {   # $1 = titre, $2 = message
  dire "ALERTE — $1 : $2"
  # Notification macOS. Volontairement sans dépendance : osascript est
  # présent partout, et une alerte qui exige d'installer quelque chose
  # est une alerte qui ne partira pas le jour où il faut.
  osascript -e "display notification \"$2\" with title \"Balise Watch — $1\"" 2>/dev/null || true
}

# ── Rotation du journal ───────────────────────────────────────────────
if [[ -f "$LOG" ]]; then
  taille=$(( $(wc -c < "$LOG") / 1048576 ))
  if (( taille >= MAX_LOG_MO )); then
    mv "$LOG" "$LOG.1"
    dire "journal rotaté (${taille} Mo) → $(basename "$LOG").1"
  fi
fi

# ── Verrou ────────────────────────────────────────────────────────────
if ! mkdir "$VERROU" 2>/dev/null; then
  age=$(( $(date +%s) - $(stat -f %m "$VERROU" 2>/dev/null || echo 0) ))
  if (( age > MAX_MINUTES * 60 )); then
    dire "verrou périmé (${age}s) — retiré"
    rmdir "$VERROU" 2>/dev/null && mkdir "$VERROU"
  else
    dire "un run est déjà en cours (verrou de ${age}s) — abandon"
    exit 0
  fi
fi
trap 'rmdir "$VERROU" 2>/dev/null' EXIT

# ── Environnement ─────────────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
  alerter "entretien" "fichier $ENV_FILE absent — voir balise-watch-r2.env.exemple"
  exit 1
fi
perms=$(stat -f %Lp "$ENV_FILE")
if [[ "$perms" != "600" ]]; then
  dire "⚠️ $ENV_FILE est en $perms — attendu 600. Correction."
  chmod 600 "$ENV_FILE"
fi
# shellcheck source=/dev/null
source "$ENV_FILE"

PYTHON="${BW_PYTHON:-$(command -v python3)}"
if [[ -z "$PYTHON" ]]; then
  alerter "entretien" "python3 introuvable dans le PATH de launchd"
  exit 1
fi

# ── Run, sous chien de garde ──────────────────────────────────────────
dire "── run entretien · $PYTHON · deadline ${MAX_MINUTES} min ──"
cd "$TRACES" || exit 1

"$PYTHON" backfill_packs.py --mode entretien --go >>"$LOG" 2>&1 &
pid=$!
( sleep $(( MAX_MINUTES * 60 )); kill -TERM "$pid" 2>/dev/null ) &
chien=$!
wait "$pid"; code=$?
kill "$chien" 2>/dev/null

# ── Suite ─────────────────────────────────────────────────────────────
if (( code == 0 )); then
  date -u +%Y-%m-%dT%H:%M:%SZ > "$DERNIER_OK"
  echo 0 > "$ECHECS"
  dire "✅ run terminé (code 0)"
  exit 0
fi

n=$(( $(cat "$ECHECS" 2>/dev/null || echo 0) + 1 ))
echo "$n" > "$ECHECS"
# code 2 = Abort (plafond atteint ou invariant violé) : c'est le worker
# qui refuse d'écrire, pas une panne. On le distingue dans le message,
# parce que la conduite à tenir n'est pas la même.
motif=$([[ $code -eq 2 ]] && echo "ABORT (plafond ou invariant — voir le log)" || echo "code $code")
dire "❌ échec — $motif · $n échec(s) consécutif(s)"

if (( n >= 2 )); then
  alerter "entretien en échec" "$n jours de suite ($motif). Les packs n'avancent plus."
fi
exit "$code"
