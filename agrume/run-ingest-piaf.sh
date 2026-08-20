#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  run-ingest-piaf.sh — la pluie à venir, sur le VPS      (20/08/2026)
#                       Lot Q2 · A20 = « le VPS tire »
#
#  Décalque de `run-ingest-pi.sh`, et volontairement : les trois fichiers
#  d'environnement, leur ORDRE, le refus de démarrer plutôt que de
#  boucler, et le voyant qui ne pingue au vert que sur une écriture
#  RÉELLE — tout ça a déjà été payé.
#
#  ⚠️ AUCUNE CLÉ NE S'AFFICHE. Pas de `set -x`, rien d'imprimé, pas même
#  tronqué.
#
#  ⛔⛔ CE QUE CE FICHIER AJOUTE : LE VERROU DE CONCURRENCE.
#  À 10 minutes de cadence, une passe qui traîne (portail qui rame,
#  incident réseau retenté) chevaucherait la suivante — et DEUX processus
#  écriraient le même index. Le second lirait l'index d'avant, y
#  inscrirait ses clés, et effacerait celles que le premier vient
#  d'ajouter : des objets EN LIGNE et HORS INDEX, c'est-à-dire invisibles
#  et définitivement payés. C'est exactement le motif des 18 orphelins
#  des 12-13/08, par un autre chemin.
#  `flock -n` refuse de démarrer plutôt que de doubler. Un passage sauté
#  n'est pas un trou : la passe suivante sort dans 5 minutes.
#
#  Usage :  ./run-ingest-piaf.sh
#           ./run-ingest-piaf.sh --sans-ecriture
#           ./run-ingest-piaf.sh --verifier
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${BW_PYTHON:-$HOME/venv-balise/bin/python}"
ALERTES_FILE="${BW_ALERTES_ENV:-$HOME/.balise-watch-alertes.env}"
VERROU="${BW_PIAF_VERROU:-/tmp/bw-agrume-piaf.lock}"

# ⚠️ LES ALERTES SE CHARGENT EN PREMIER — leçon du 03/08. Le tout premier
# échec possible est « un fichier d'environnement est absent » ; si le
# canal d'alerte vivait dedans, cette alerte-là partirait dans le vide.
# shellcheck source=/dev/null
[ -r "$ALERTES_FILE" ] && . "$ALERTES_FILE"

PING="${BW_AGRUME_PIAF_PING_URL:-}"

dire() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }

pinguer() {
  [ -n "$PING" ] || return 0
  curl -fsS -m 10 --retry 2 --data-binary "${2:-}" "${PING}$1" >/dev/null 2>&1 \
    || dire "⚠️ ping '$1' non parti (réseau ?) — le check passera en retard"
}

if [ -z "$PING" ]; then
  # ⚠️ Un job qui pingue dans le vide a EXACTEMENT l'allure d'un job
  # surveillé. Et celui-ci s'exécute 144 fois par jour : sa panne ne se
  # verrait pas dans l'onglet d'un dépôt, elle ne se verrait nulle part.
  dire "⚠️ BW_AGRUME_PIAF_PING_URL absente de $ALERTES_FILE — PERSONNE NE SURVEILLE CETTE CHAÎNE"
fi

charger() {
  f="$1"; quoi="$2"
  if [ -r "$f" ]; then
    set -a
    # shellcheck source=/dev/null
    . "$f"
    set +a
  else
    dire "❌ $f illisible — l'ingestion de la pluie a besoin de $quoi"
    pinguer /fail "fichier d'environnement illisible : $f ($quoi)"
    exit 78   # EX_CONFIG
  fi
}

charger "${BW_MF_ENV:-$HOME/.balise-watch-model-verif.env}" "la clé Météo-France"
charger "${BW_R2_ENV:-$HOME/.balise-watch-r2.env}" "R2_ACCOUNT_ID"
# ⚠️ EN DERNIER, pour qu'il gagne — et dans ce processus seulement. Le
# jeton des PACKS ne sait pas écrire `balise-watch-grids`, celui d'AGRUME
# ne sait écrire QUE lui. Les intervertir casserait `balise-entretien`,
# `balise-infoclimat` et `bw-model-*`, des heures plus tard, ailleurs.
charger "${BW_AGRUME_R2_ENV:-$HOME/.balise-watch-agrume-r2.env}" \
        "le jeton R2 d'AGRUME (écriture sur balise-watch-grids)"

export STORAGE_BACKEND=r2
# ⚠️ Aucun compartiment ne s'appelle `wind-grid` : c'est le nom Supabase
# hérité. Côté R2 c'est `balise-watch-grids`.
export R2_BUCKET="${AGRUME_R2_BUCKET:-balise-watch-grids}"
export PYTHONUNBUFFERED=1

# ══════════════════════════════════════════════════════════════════════
#  ⚠️⚠️ CE QUE LE VOYANT SURVEILLE, ET CE QU'IL NE SURVEILLE PAS
#
#  Le timer repasse toutes les 10 min et le producteur publie toutes les
#  5 : il y a donc TOUJOURS quelque chose à faire, contrairement à
#  l'ingestion PI où cinq passages sur six sont vides. Le code 3 reste
#  possible (un passage qui retombe sur la passe déjà ingérée, si
#  l'horloge dérive) et ne pingue rien.
#
#  ⓘ Réglage du check, côté healthchecks.io :
#     période 10 min · grâce 25 min
#  → alerte après ~35 min de silence, soit trois passages manqués. Assez
#  lâche pour absorber un incident réseau retenté, assez serré pour que
#  « la pluie à venir » ne soit pas vieille d'une heure sans que
#  personne ne le sache.
#
#  ⛔ ET C'EST LE SEUL VOYANT. À 144 exécutions par jour, la surveillance
#  ne peut pas passer par la lecture d'un journal : personne ne lit 144
#  lignes par jour, et un silence ne se voit pas « en cherchant bien ».
# ══════════════════════════════════════════════════════════════════════

# ⛔ Le verrou. `-n` = on ne fait pas la queue : on renonce.
exec 9>"$VERROU" || { dire "❌ verrou $VERROU inouvrable"; exit 74; }
if ! flock -n 9; then
  dire "⏭️  une ingestion est DÉJÀ en cours — ce passage est sauté (pas un échec : la passe suivante sort dans 5 min)"
  exit 3
fi

"$PY" "$ICI/ingest_piaf.py" "$@"
code=$?

case "$code" in
  0) pinguer "" "passe ingérée et écrite" ;;
  3) dire "rien à faire (code 3) — aucun ping" ;;
  *) pinguer /fail "ingest_piaf.py a rendu le code $code" ;;
esac

exit "$code"
