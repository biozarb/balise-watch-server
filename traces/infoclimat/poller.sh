#!/bin/bash
# ══════════════════════════════════════════════════════════════════════
#  poller.sh — enveloppe du poller Infoclimat (03/08/2026)
#  Lancé par balise-infoclimat.timer, jamais à la main en production.
#
#  ⚠️ CE N'EST PAS `entretien.sh`, ET ÇA NE DOIT PAS LE DEVENIR.
#  L'entretien tourne UNE FOIS PAR JOUR ; ce poller toutes les 5 min.
#  Greffer l'un sur l'autre ferait tourner l'entretien 288 fois par jour
#  ou le poller une fois — les deux sont des pannes. Verrou séparé,
#  journal séparé, check Healthchecks séparé, état séparé.
#
#  Ce que cette enveloppe apporte, et que le Python ne fait pas :
#    · charge ~/.balise-watch-r2.env (les `export` ne survivent pas au
#      terminal, et systemd n'a ni PATH d'utilisateur ni variables de
#      session) ;
#    · un verrou : deux runs simultanés DOUBLERAIENT les appels chez
#      Infoclimat et les écritures R2 ;
#    · un chien de garde : un run qui dépasse sa propre cadence est
#      cassé par définition — on le tue plutôt que de le laisser
#      recouvrir le suivant ;
#    · un journal rotaté (un log qui grossit sans fin finit par être le
#      problème qu'il devait aider à résoudre) ;
#    · le compte d'échecs CONSÉCUTIFS, et une alerte au troisième.
#
#  ⚠️ POURQUOI AU TROISIÈME ET PAS AU DEUXIÈME, contrairement à
#  l'entretien : à 5 min de cadence, un incident réseau passager
#  produirait des alertes en rafale. Trois échecs d'affilée = 15 min
#  sans donnée, c'est le moment où ça devient un vrai problème. Le
#  bon signal, ici, c'est le silence prolongé — d'où Healthchecks.
#
#  ⚠️ JAMAIS DEPUIS L'IP DE RENDER. La clé Infoclimat est liée à
#  51.91.102.146. Ailleurs, c'est `Wrong ip address` — en HTTP 200.
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${BW_ENV_FILE:-$HOME/.balise-watch-r2.env}"
ALERTES_FILE="${BW_ALERTES_FILE:-$HOME/.balise-watch-alertes.env}"
ETAT="${BW_INFOCLIMAT_ETAT:-$HOME/.balise-watch-infoclimat}"
LOG="$ETAT/poller.log"
ECHECS="$ETAT/echecs_consecutifs"
VERROU="$ETAT/verrou"
MAX_MINUTES="${BW_POLLER_MAX_MINUTES:-8}"
MAX_LOG_MO=10
SEUIL_ALERTE=3

mkdir -p "$ETAT"
dire() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"; }

# ── Alertes chargées EN PREMIER ──────────────────────────────────────
# Même raison que dans entretien.sh (défaut trouvé le 03/08) : le
# premier échec possible est « .balise-watch-r2.env absent ». Si les
# canaux d'alerte vivaient dedans, cette alerte-là partirait dans le
# vide. Un dispositif d'alerte ne doit pas dépendre de ce qu'il
# surveille.
[[ -f "$ALERTES_FILE" ]] && source "$ALERTES_FILE"

# ── Portabilité GNU / BSD (le Mac reste une cible d'essai) ───────────
mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0; }

alerter() {
  local sujet="$1" corps="$2"
  dire "ALERTE — $sujet : $corps"
  # ⚠️ Le titre part dans un EN-TÊTE HTTP, qui ne transporte pas d'UTF-8
  #    (bug corrigé le 03/08 : un simple « é » faisait rejeter la
  #    requête). Corps en UTF-8, titre translittéré.
  if [[ -n "${BW_PING_FAIL_URL:-}" ]]; then
    curl -fsS -m 10 --data-raw "$corps" "$BW_PING_FAIL_URL" >/dev/null 2>&1 || true
  fi
  if [[ -n "${BW_MAIL_TO:-}" ]] && command -v msmtp >/dev/null 2>&1; then
    printf 'Subject: %s\nTo: %s\nContent-Type: text/plain; charset=UTF-8\n\n%s\n' \
      "$(printf '%s' "$sujet" | iconv -t ASCII//TRANSLIT 2>/dev/null || echo 'balise-watch poller')" \
      "$BW_MAIL_TO" "$corps" | msmtp "$BW_MAIL_TO" >/dev/null 2>&1 || true
  fi
}

# ── Verrou ───────────────────────────────────────────────────────────
# Un verrou périmé (run tué, machine redémarrée) doit expirer tout seul,
# sinon le poller resterait bloqué jusqu'à ce que quelqu'un le remarque
# — et personne ne le remarquerait avant que les calques ne vieillissent.
if [[ -f "$VERROU" ]]; then
  age=$(( $(date +%s) - $(mtime "$VERROU") ))
  if (( age < MAX_MINUTES * 60 )); then
    dire "run déjà en cours (verrou de ${age}s) — sortie sans rien faire"
    exit 0
  fi
  dire "verrou périmé (${age}s) — on le reprend"
fi
echo $$ > "$VERROU"
trap 'rm -f "$VERROU"' EXIT

# ── Rotation du journal ──────────────────────────────────────────────
if [[ -f "$LOG" ]] && (( $(wc -c < "$LOG") > MAX_LOG_MO * 1024 * 1024 )); then
  mv -f "$LOG" "$LOG.1"
  dire "journal rotaté"
fi

# ── Environnement ────────────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
  alerter "poller Infoclimat" "fichier $ENV_FILE absent — rien ne peut tourner"
  exit 1
fi
set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a

PYTHON="${BW_PYTHON:-$(command -v python3)}"
if [[ ! -x "$PYTHON" ]]; then
  alerter "poller Infoclimat" "python3 introuvable ($PYTHON) — définir BW_PYTHON dans $ENV_FILE"
  exit 1
fi

# ── Le run ───────────────────────────────────────────────────────────
debut=$(date +%s)
timeout --signal=TERM --kill-after=30s "${MAX_MINUTES}m" \
  "$PYTHON" "$ICI/poller_infoclimat.py" --go >>"$LOG" 2>&1
code=$?
duree=$(( $(date +%s) - debut ))

if (( code == 0 )); then
  echo 0 > "$ECHECS"
  # Ping de vie : c'est le SEUL canal capable de signaler que ce script
  # ne tourne PLUS DU TOUT — aucune ligne d'ici ne s'exécuterait pour le
  # dire. Healthchecks alerte depuis l'extérieur, sur le silence.
  [[ -n "${BW_INFOCLIMAT_PING_URL:-}" ]] && \
    curl -fsS -m 10 "$BW_INFOCLIMAT_PING_URL" >/dev/null 2>&1 || true
  dire "run OK en ${duree}s"
  exit 0
fi

n=$(( $(cat "$ECHECS" 2>/dev/null || echo 0) + 1 ))
echo "$n" > "$ECHECS"
dire "run en ÉCHEC (code $code, ${duree}s) — $n consécutif(s)"
if (( n >= SEUIL_ALERTE )); then
  alerter "poller Infoclimat en echec" \
    "$n runs consécutifs en échec (code $code). Dernières lignes :
$(tail -n 20 "$LOG")"
fi
# ⚠️ On sort en 0 : un échec de poll n'est pas un échec de SERVICE.
# Le dernier latest.json reste servi, et systemd n'a rien à réparer —
# c'est le compteur ci-dessus et Healthchecks qui portent l'alerte.
exit 0
