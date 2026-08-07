#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  run.sh — l'enveloppe des deux jobs nocturnes (07/08/2026)
#
#  Usage :  run.sh collect   |   run.sh score
#
#  ═══ POURQUOI UNE ENVELOPPE, ET PAS UN EnvironmentFile ═══
#
#  Les quatre unités écrites le 08/08 déclaraient
#  `EnvironmentFile=/opt/balise-watch/.env`. Deux choses fausses là-
#  dedans, découvertes en sondant le VPS le 07/08 :
#
#   1. `/opt/balise-watch` n'existe pas, et l'utilisateur `balise` non
#      plus. Le VPS range son code dans `~/balise-watch/` et tourne en
#      `debian`, comme `balise-infoclimat.service` le dit depuis le
#      03/08.
#   2. Surtout : `~/.balise-watch-r2.env` est écrit en `export VAR=…`.
#      systemd ne sait pas lire ça — il n'accepte que `VAR=…` et rejette
#      la ligne. C'est précisément pour cette raison que
#      `balise-infoclimat.service` n'a AUCUN EnvironmentFile et lance un
#      script shell : `poller.sh` source les fichiers lui-même.
#
#  On copie donc ce patron, et on y gagne l'endroit où poser le ping
#  Healthchecks — que le job Python n'a pas.
#
#  ═══ CE QUE CETTE ENVELOPPE IMPOSE, PLUTÔT QUE DE L'ESPÉRER ═══
#
#  ⚠️ `STORAGE_BACKEND` est ABSENTE du .env du VPS (sondé le 07/08).
#     `storage.py` retombe alors sur le Storage Supabase — le défaut
#     trouvé le 03/08 sur le poller Infoclimat, corrigé de la même
#     façon : on impose `r2`, on ne le demande pas.
#
#  ⚠️ `R2_BUCKET="balise-watch-packs"` est définie dans le .env partagé,
#     et `tools/storage.py` ligne 389 dit :
#         bucket_r2 = os.environ.get("R2_BUCKET") or defaut
#     `MODEL_VERIF_BUCKET` ne sert QUE au dos Supabase. Sans la ligne
#     d'écrasement ci-dessous, l'archive irait se déverser à la racine du
#     bucket des packs — HTTP 200, aucune erreur, et `score.py`
#     relirait au même endroit, donc même les essais passeraient. Le
#     bucket `model-verif` créé le 08/08 resterait vide, et on ne s'en
#     apercevrait qu'en allant le regarder.
#
#  ⚠️ `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` ne sont sur le VPS nulle
#     part : aucune chaîne existante n'en a besoin. `score.py` les lit
#     en direct. Elles vivent dans `~/.balise-watch-model-verif.env`,
#     à part, en 600 — cf. `model-verif.env.exemple`.
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

MODE="${1:-}"
case "$MODE" in
  collect|score) ;;
  *) echo "usage: run.sh collect|score" >&2; exit 2 ;;
esac

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${BW_ENV_FILE:-$HOME/.balise-watch-r2.env}"
ALERTES_FILE="${BW_ALERTES_FILE:-$HOME/.balise-watch-alertes.env}"
SUPA_FILE="${BW_MODEL_VERIF_ENV_FILE:-$HOME/.balise-watch-model-verif.env}"

# État et archive au même endroit : c'est l'archive qui commande le
# choix (749 Mo/an, sa place est dans /var/lib et pas dans un home), et
# deux répertoires pour un seul job donneraient deux endroits où
# chercher le soir où ça casse.
ETAT="${BW_MODEL_VERIF_ETAT:-/var/lib/bw-model-verif}"
LOG="$ETAT/$MODE.log"
VERROU="$ETAT/verrou.$MODE"
ECHECS="$ETAT/echecs_consecutifs.$MODE"
MAX_LOG_MO=20

# La collecte dure ~6 min pour 648 points, la notation quelques minutes.
# Les gardes sont larges, mais sous les TimeoutStartSec des unités : on
# veut que ce soit CE script qui constate l'échec et alerte, pas systemd
# qui tue tout sans que personne ne l'apprenne.
if [[ "$MODE" == "collect" ]]; then
  MAX_MINUTES="${BW_MODEL_VERIF_MAX_MINUTES:-40}"
  # ⚠️ Une nuit non collectée est perdue définitivement — aucun modèle
  # Météo-France n'a d'historique de runs passés chez Open-Meteo (sondé
  # le 08/08). On alerte au PREMIER échec, pas au troisième comme le
  # poller Infoclimat, où un cycle raté se rattrape cinq minutes plus
  # tard.
  SEUIL_ALERTE=1
else
  MAX_MINUTES="${BW_MODEL_VERIF_MAX_MINUTES:-25}"
  # La notation, elle, se rejoue sur l'archive autant de fois qu'on veut
  # (`score.py --day AAAA-MM-JJ`). Un échec isolé n'est pas une urgence.
  SEUIL_ALERTE=2
fi

# Un check Healthchecks par job : la collecte et la notation ont deux
# enjeux, deux durées et deux façons de tomber. Réutiliser un seul check
# ferait passer l'un au rouge pour la faute de l'autre — la règle posée
# en tête de `balise-infoclimat.service`, qui vaut ici aussi.
PING_VAR="BW_MODEL_$(printf '%s' "$MODE" | tr '[:lower:]' '[:upper:]')_PING_URL"

mkdir -p "$ETAT" 2>/dev/null || true
dire() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"; }

# ── Alertes chargées EN PREMIER ──────────────────────────────────────
# Même raison qu'ailleurs (défaut du 03/08) : le premier échec possible
# est « le .env R2 est absent ». Si les canaux d'alerte vivaient dedans,
# cette alerte-là partirait dans le vide.
# shellcheck source=/dev/null
[[ -f "$ALERTES_FILE" ]] && source "$ALERTES_FILE"

alerter() {
  local sujet="$1" corps="$2"
  dire "ALERTE — $sujet : $corps"

  local ping="${!PING_VAR:-}"
  if [[ -n "$ping" ]]; then
    curl -fsS -m 10 --data-binary "$corps" "${ping}/fail" >/dev/null 2>&1 \
      || dire "⚠️ ping d'échec non parti"
  fi

  if command -v systemd-cat >/dev/null 2>&1; then
    printf '%s : %s\n' "$sujet" "$corps" \
      | systemd-cat -t "bw-model-$MODE" -p err 2>/dev/null || true
  fi

  # ⚠️ `Subject:` ne transporte pas d'UTF-8 (bug du 03/08 : un « é »
  # faisait rejeter l'envoi). Sujet translittéré, corps en UTF-8 déclaré.
  if [[ -n "${BW_ALERTE_MAIL:-}" ]] && command -v msmtp >/dev/null 2>&1; then
    local sujet_h
    sujet_h=$(printf '%s' "$sujet" \
      | { iconv -f UTF-8 -t ASCII//TRANSLIT 2>/dev/null || cat; } \
      | LC_ALL=C tr -cd '\40-\176')
    [[ -z "$sujet_h" ]] && sujet_h="score modeles"
    printf 'To: %s\nSubject: [Balise Watch] %s\nContent-Type: text/plain; charset=UTF-8\n\n%s\n\nMachine : %s\nJournal : %s\n' \
      "$BW_ALERTE_MAIL" "$sujet_h" "$corps" "$(hostname)" "$LOG" \
      | msmtp --read-recipients >/dev/null 2>&1 \
      || dire "⚠️ e-mail non parti — voir ~/.msmtp.log"
  fi
}

# ── Verrou ───────────────────────────────────────────────────────────
# Un verrou périmé (run tué, machine redémarrée) doit expirer seul,
# sinon la collecte resterait bloquée des nuits durant sans que rien ne
# le dise — et ces nuits-là ne se rattrapent pas.
mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0; }
if [[ -f "$VERROU" ]]; then
  age=$(( $(date +%s) - $(mtime "$VERROU") ))
  if (( age < MAX_MINUTES * 60 )); then
    dire "run $MODE déjà en cours (verrou de ${age}s) — sortie sans rien faire"
    exit 0
  fi
  dire "verrou $MODE périmé (${age}s) — on le reprend"
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
  alerter "score modèles ($MODE)" "fichier $ENV_FILE absent — rien ne peut tourner"
  exit 1
fi
set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
# shellcheck source=/dev/null
[[ -f "$SUPA_FILE" ]] && source "$SUPA_FILE"
set +a

# ⚠️ LES DEUX LIGNES QUI COMPTENT — voir l'en-tête. Elles viennent APRÈS
# le `source`, exprès : elles écrasent ce que le .env partagé a posé.
BUCKET="${BW_MODEL_VERIF_BUCKET:-model-verif}"
export STORAGE_BACKEND="r2"
export R2_BUCKET="$BUCKET"
export MODEL_VERIF_BUCKET="$BUCKET"

# ⚠️ Sans ça, Python bufferise stdout dès qu'il écrit dans un tube — et
# stderr, lui, ne bufferise pas. Constaté au deuxième essai du 07/08 :
# le « ❌ archive pas sur R2 » apparaissait AVANT le récapitulatif qui
# l'explique, et l'ordre du journal ne racontait plus la nuit dans
# l'ordre où elle s'est passée. Un journal qu'on lit à l'envers est un
# journal qu'on lit mal.
export PYTHONUNBUFFERED=1

manque=()
for v in R2_ACCOUNT_ID R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY; do
  [[ -z "${!v:-}" ]] && manque+=("$v")
done
if [[ "$MODE" == "score" ]]; then
  for v in SUPABASE_URL SUPABASE_SERVICE_KEY; do
    [[ -z "${!v:-}" ]] && manque+=("$v")
  done
fi
if (( ${#manque[@]} )); then
  alerter "score modèles ($MODE)" \
    "variables absentes : ${manque[*]} — voir $SUPA_FILE et $ENV_FILE"
  exit 1
fi

PYTHON="${BW_PYTHON:-$(command -v python3)}"
if [[ ! -x "$PYTHON" ]]; then
  alerter "score modèles ($MODE)" \
    "python3 introuvable ($PYTHON) — définir BW_PYTHON dans $ENV_FILE"
  exit 1
fi
# ⚠️ `boto3` n'est PAS dans le python3 système du VPS (sondé le 07/08) :
# il vit dans le venv désigné par BW_PYTHON. `storage.py` sort en Abort
# sans lui, donc on le constate ici, une fois, plutôt que de le
# découvrir au milieu d'une collecte.
if ! "$PYTHON" -c "import boto3" >/dev/null 2>&1; then
  alerter "score modèles ($MODE)" \
    "boto3 absent de $PYTHON — l'archive R2 ne peut pas s'écrire"
  exit 1
fi

# ── Le run ───────────────────────────────────────────────────────────
debut=$(date +%s)
dire "▶ $MODE — bucket R2 « $BUCKET », python $PYTHON"
# ⚠️ `timeout` est dans coreutils, donc présent sur le VPS mais ABSENT
# d'un macOS nu — et son absence rend 127, un code qui ressemble à un
# échec du job alors que le job n'a pas été lancé. Constaté à l'essai du
# 07/08 : on distingue les deux plutôt que de rendre un chiffre trompeur.
# ⚠️ La sortie du job passe par `tee` et non par `>>` (corrigé le 07/08,
# au premier essai réel) : renvoyée seulement dans le journal, elle
# rendait un `--dry-run` interactif parfaitement muet — « run OK en 0s »
# et rien de ce que le job avait à dire. Un essai à blanc dont on ne
# voit pas le résultat ne vérifie rien. Sous systemd, ce même flux part
# dans journald, ce qui est le comportement voulu.
# `${PIPESTATUS[0]}` et pas `$?` : c'est le code du JOB qu'on veut, pas
# celui de `tee`, qui réussit toujours.
if command -v timeout >/dev/null 2>&1; then
  timeout --signal=TERM --kill-after=60s "${MAX_MINUTES}m" \
    "$PYTHON" "$ICI/$MODE.py" --out "$ETAT" "${@:2}" 2>&1 | tee -a "$LOG"
  code=${PIPESTATUS[0]}
else
  dire "⚠️ timeout absent — run sans chien de garde (seul TimeoutStartSec borne)"
  "$PYTHON" "$ICI/$MODE.py" --out "$ETAT" "${@:2}" 2>&1 | tee -a "$LOG"
  code=${PIPESTATUS[0]}
fi
duree=$(( $(date +%s) - debut ))

if (( code == 0 )); then
  echo 0 > "$ECHECS"
  ping="${!PING_VAR:-}"
  if [[ -n "$ping" ]]; then
    curl -fsS -m 10 "$ping" >/dev/null 2>&1 \
      || dire "⚠️ ping de vie non parti (réseau ?) — le check va passer en retard"
  else
    # Un job qui pingue dans le vide a exactement l'allure d'un job
    # surveillé. La panne ne se verrait qu'au moment où l'on irait
    # chercher des chiffres qui n'existent pas.
    dire "⚠️ $PING_VAR absente de $ALERTES_FILE — PERSONNE NE SURVEILLE CE JOB"
  fi
  dire "run $MODE OK en ${duree}s"
  exit 0
fi

n=$(( $(cat "$ECHECS" 2>/dev/null || echo 0) + 1 ))
echo "$n" > "$ECHECS"
dire "run $MODE en ÉCHEC (code $code, ${duree}s) — $n consécutif(s)"
if (( n >= SEUIL_ALERTE )); then
  alerter "score modeles ($MODE) en echec" \
    "$n run(s) consécutif(s) en échec (code $code, ${duree}s). Dernières lignes :
$(tail -n 25 "$LOG")"
fi

# ⚠️ On sort NON NUL, contrairement à `poller.sh`. Un poll raté se
# rattrape cinq minutes plus tard ; une nuit de collecte ratée, jamais.
# On veut que `systemctl --failed` et `systemctl status` le disent, en
# plus de Healthchecks.
exit "$code"
