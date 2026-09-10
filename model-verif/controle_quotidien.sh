#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  controle_quotidien.sh — le runner du contrôle de pente (07:30 CEST)
#  Lot REGISTRE ET PENTE, 10/09/2026.
#
#  Ce qu'il fait, dans l'ordre :
#    1. attend que `bw-model-score.service` ait fini (le garde est à
#       90 min, le run peut vivre jusqu'à 07:27 CEST ; à 07:30 on ne
#       lit pas la ligne d'hier en croyant lire celle d'aujourd'hui) ;
#    2. joue `controle_quotidien.py` — 0 : silence, 1 : constat(s),
#       2 : le contrôle n'a pas pu tourner ;
#    3. sur 1, chaque constat part vers JIRA (un ticket par motif, un
#       commentaire par jour — `tools/bw_jira.sh`) et dans journald ;
#    4. pingue son check Healthchecks : un contrôle mort doit se voir
#       (lot LV — une variable absente crie une fois par jour).
#
#  ⛔ IL NE REMONTE RIEN, N'ÉCRIT AUCUNE UNITÉ, NE REJOUE AUCUN RUN. La
#  proposition (commande exacte, en-tête à écrire) est DANS le texte du
#  ticket ; Yann la lance.
#
#  ⚠️ PAS UN MODE DE `run.sh` : run.sh porte le chien de garde, le verrou,
#  les secrets R2/Supabase, le self-test — ce contrôle n'a besoin de rien
#  de tout cela, et l'inventaire des modes (test_alertes A1/A5) est
#  calculé sur le `case` de run.sh. Un runner à part, comme
#  `run-confronter-quotidien.sh`, avec le même repli d'outillage.
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail
ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ETAT="${BW_MODEL_VERIF_ETAT:-/var/lib/bw-model-verif}"
LOG="$ETAT/controle.log"
ALERTES_FILE="${BW_ALERTES_FILE:-$HOME/.balise-watch-alertes.env}"
ATTENTE_MAX_S="${BW_CONTROLE_ATTENTE_MAX_S:-2400}"

mkdir -p "$ETAT" 2>/dev/null || true
dire() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"; }

# ── Alertes chargées EN PREMIER (même règle que run.sh) ──────────────
# shellcheck source=/dev/null
[[ -f "$ALERTES_FILE" ]] && source "$ALERTES_FILE"
# shellcheck source=/dev/null
if [ -r "$ICI/../tools/bw_avertir_config.sh" ]; then . "$ICI/../tools/bw_avertir_config.sh"; else bw_avertir_config() { :; }; fi
# shellcheck source=/dev/null
if [ -r "$ICI/../tools/bw_jira.sh" ]; then . "$ICI/../tools/bw_jira.sh"; else
  bw_jira_signaler() { dire "⚠️ tools/bw_jira.sh absent — constat non transmis à Jira : ${2:-}"; }
fi

# Le python du VPS (boto3, zoneinfo) ; ailleurs, celui du PATH.
PYTHON="${BW_PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  if [[ -x /home/debian/venv-balise/bin/python3 ]]; then PYTHON=/home/debian/venv-balise/bin/python3
  else PYTHON="$(command -v python3)"; fi
fi

# ── 1. attendre la fin de la notation ────────────────────────────────
attendu=0
while command -v systemctl >/dev/null 2>&1 \
      && systemctl is-active --quiet bw-model-score.service 2>/dev/null; do
  if (( attendu == 0 )); then dire "notation encore en cours — j'attends (au plus ${ATTENTE_MAX_S}s)"; fi
  sleep 30; attendu=$(( attendu + 30 ))
  if (( attendu >= ATTENTE_MAX_S )); then
    dire "⚠️ notation toujours en cours après ${attendu}s — contrôle sur le registre d'hier"
    break
  fi
done

# ── 2. le contrôle ───────────────────────────────────────────────────
# ⚠️ Nom LITTÉRAL (pas `${!PING_VAR}` comme run.sh) : c'est ce que
# l'inventaire `bw_inv_litterales` sait lire, et ce runner n'a qu'un mode.
PING_VAR="BW_MODEL_CONTROLE_PING_URL"
ping="${BW_MODEL_CONTROLE_PING_URL:-}"
CONSTATS="$(mktemp "${TMPDIR:-/tmp}/bw-controle.XXXXXX")"
"$PYTHON" "$ICI/controle_quotidien.py" --out "$ETAT" --machine > "$CONSTATS" 2>>"$LOG"
code=$?
TEXTE="$("$PYTHON" "$ICI/controle_quotidien.py" --out "$ETAT" --verbeux 2>&1)"
printf '%s\n' "$TEXTE" >> "$LOG"

if (( code == 2 )); then
  dire "⛔ le contrôle n'a pas pu tourner (code 2) — voir $LOG"
  [[ -n "$ping" ]] && curl -fsS -m 10 --data-binary "$TEXTE" "${ping}/fail" >/dev/null 2>&1
  if command -v systemd-cat >/dev/null 2>&1; then
    printf 'controle de pente indisponible : %s\n' "$TEXTE" | systemd-cat -t bw-model-controle -p err 2>/dev/null || true
  fi
elif (( code == 1 )); then
  # ── 3. chaque constat vers Jira, et dans journald ──────────────────
  while IFS=$'\t' read -r motif texte; do
    [[ -n "$motif" ]] || continue
    dire "constat [$motif] $texte"
    if command -v systemd-cat >/dev/null 2>&1; then
      printf '%s\n' "$texte" | systemd-cat -t bw-model-controle -p notice 2>/dev/null || true
    fi
    # ⚠️ Sujet en ASCII : c'est le titre du ticket, et il sert de
    # résumé dans la boîte Jira. Le corps porte les accents.
    sujet="$(printf 'derive notation - %s - %s' "$motif" "$texte" \
      | { iconv -f UTF-8 -t ASCII//TRANSLIT 2>/dev/null || cat; } \
      | LC_ALL=C tr -cd '\40-\176' | cut -c1-200)"
    bw_jira_signaler "$motif" "$sujet" "$texte

$TEXTE" "$ETAT" 2>&1 | tee -a "$LOG"
  done < "$CONSTATS"
else
  dire "rien à dire : pente plate ou négative, ou échéance hors horizon"
fi
rm -f "$CONSTATS"

# ── 4. le check de vie ───────────────────────────────────────────────
if [[ -n "$ping" ]] && (( code != 2 )); then
  curl -fsS -m 10 "$ping" >/dev/null 2>&1 || dire "⚠️ ping de vie non parti"
elif [[ -z "$ping" ]]; then
  dire "⚠️ $PING_VAR absente de $ALERTES_FILE — PERSONNE NE SURVEILLE CE JOB"
  bw_avertir_config "$PING_VAR" "$ALERTES_FILE" "bw-model-controle" "CE JOB (controle)" "$ETAT"
fi
exit 0
