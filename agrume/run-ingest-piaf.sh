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
# ⚠️ PAS dans /tmp : le compteur doit survivre à un redémarrage du VPS,
# sinon une panne longue se remettrait à zéro toute seule au pire moment.
COMPTEUR="${BW_PIAF_COMPTEUR:-$HOME/.bw-agrume-piaf-echecs}"
# ⛔ 27/08 — LE VOYANT CLIGNOTAIT POUR UNE PASSE PERDUE SUR TRENTE-SIX.
# Voir le pavé « CE QUE LE VOYANT SURVEILLE » plus bas.
SEUIL_ECHECS="${BW_PIAF_SEUIL_ECHECS:-3}"

# ⚠️ LES ALERTES SE CHARGENT EN PREMIER — leçon du 03/08. Le tout premier
# échec possible est « un fichier d'environnement est absent » ; si le
# canal d'alerte vivait dedans, cette alerte-là partirait dans le vide.
# shellcheck source=/dev/null
[ -r "$ALERTES_FILE" ] && . "$ALERTES_FILE"

# ── L'avertissement de configuration SORT du journal (lot LV, 01/09) ──
# ⛔ Sans ce fichier, « PERSONNE NE SURVEILLE » n'allait que dans
# `journalctl`, que RIEN ne lit sur cette machine (mesuré le 01/09 :
# 0 logcheck, aucune crontab, OnFailure= sur 0 des 31 unités). La
# confrontation a crié 20 jours d'affilée sans atteindre personne.
# ⚠️ Le repli est une fonction VIDE, et c'est délibéré : un runner de
# production ne doit pas mourir parce qu'un fichier d'outillage manque.
# Le `dire` d'origine, lui, reste en place quoi qu'il arrive.
# shellcheck source=/dev/null
if [ -r "$ICI/../tools/bw_avertir_config.sh" ]; then . "$ICI/../tools/bw_avertir_config.sh"; else bw_avertir_config() { :; }; fi

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
  bw_avertir_config BW_AGRUME_PIAF_PING_URL "$ALERTES_FILE" bw-agrume-piaf "CETTE CHAINE (passe piaf)"
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
#  ══════════════════════════════════════════════════════════════════
#  ⛔⛔ 27/08 — UN `/fail` COURT-CIRCUITE CETTE GRÂCE, ET C'EST CE QUI
#     A REMPLI LA BOÎTE DE YANN.
#
#  Le réglage ci-dessus est juste : trois passages manqués avant de
#  crier. Mais il ne s'applique qu'au SILENCE. Un `/fail` explicite,
#  lui, fait tomber le voyant SUR-LE-CHAMP — grâce ou pas.
#
#  Nuit du 26 au 27/08 : la passerelle Météo-France sature par
#  bouffées. SIX passes perdues sur ~36, jamais deux d'affilée. Chaque
#  passe perdue = un mail DOWN ; la passe suivante, dix minutes plus
#  tard, = un mail UP. Douze mails pour une chaîne qui n'a jamais eu
#  plus de dix minutes de retard — parce que le producteur publie
#  toutes les 5 min et qu'une passe manquée est intégralement rattrapée
#  par la suivante, plus fraîche.
#
#  ⚠️ Un voyant qui crie pour une perte SANS CONSÉQUENCE apprend à
#  être ignoré, et c'est la seule panne dont ce projet ne se remet
#  pas : le jour où il criera pour de bon, personne ne regardera.
#
#  Donc : on COMPTE les échecs consécutifs et on ne pingue `/fail`
#  qu'au troisième. En dessous, on se TAIT — et le silence est déjà
#  surveillé, par la grâce de 25 min réglée plus haut. Les deux
#  mécanismes disent alors la même chose au même moment (~30-35 min
#  sans passe fraîche), l'un explicitement, l'autre par défaut.
#
#  ⛔ Le compteur se remet à zéro à la PREMIÈRE réussite, jamais par
#  le temps qui passe : deux échecs séparés d'une réussite ne sont pas
#  une panne, ce sont deux hoquets.
#  ⚠️ Les échecs de CONFIGURATION (fichier d'env illisible, plus haut)
#  gardent leur `/fail` immédiat : ceux-là ne se rattrapent pas tout
#  seuls dans dix minutes.
#  ══════════════════════════════════════════════════════════════════
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

# ⚠️ Filtré aux chiffres : un fichier tronqué par un redémarrage rendrait
# `$(( ... + 1 ))` fatal, et le script mourrait AVANT de pouvoir pinguer
# quoi que ce soit — un garde-fou qui casse le voyant qu'il garde.
lire_compteur() {
  n=$(tr -cd '0-9' < "$COMPTEUR" 2>/dev/null)
  echo "${n:-0}"
}

case "$code" in
  0)
    # ⚠️ Remise à zéro AVANT le ping : si le ping échoue (réseau), on
    # veut quand même avoir enregistré que la chaîne est repartie.
    echo 0 > "$COMPTEUR" 2>/dev/null || dire "⚠️ $COMPTEUR non inscriptible"
    pinguer "" "passe ingérée et écrite"
    ;;
  3)
    # ⚠️ « Rien à faire » n'est ni une réussite ni un échec : le
    # compteur ne bouge pas. Le remettre à zéro effacerait une panne
    # en cours qu'un simple saut de verrou aurait masquée.
    dire "rien à faire (code 3) — aucun ping"
    ;;
  *)
    n=$(( $(lire_compteur) + 1 ))
    echo "$n" > "$COMPTEUR" 2>/dev/null || dire "⚠️ $COMPTEUR non inscriptible"
    if [ "$n" -ge "$SEUIL_ECHECS" ]; then
      dire "⛔ $n échecs CONSÉCUTIFS (seuil $SEUIL_ECHECS) — le voyant tombe"
      pinguer /fail "ingest_piaf.py a rendu le code $code — $n échecs consécutifs"
    else
      # ⚠️ Aucun ping du tout, pas même un succès : le voyant doit
      # rester sur la grâce, pas repartir à zéro sur une passe perdue.
      dire "⚠️ échec $n/$SEUIL_ECHECS (code $code) — pas encore de /fail : la passe suivante sort dans 5 min"
    fi
    ;;
esac

exit "$code"
