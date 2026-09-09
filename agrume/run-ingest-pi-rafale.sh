#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  run-ingest-pi-rafale.sh — la rafale à venir, sur le VPS  (09/09/2026)
#                            Lot « cellule qui approche », lot 2
#
#  Décalque de `run-ingest-piaf.sh`, et volontairement : les trois
#  fichiers d'environnement, leur ORDRE, le verrou de concurrence, le
#  refus de démarrer plutôt que de boucler, et l'hystérésis du voyant
#  (SEUIL_ECHECS et SEUIL_REPRISE) — tout ça a déjà été payé, deux fois,
#  les 27/08 et 07/09.
#
#  ⚠️ AUCUNE CLÉ NE S'AFFICHE. Pas de `set -x`, rien d'imprimé, pas même
#  tronqué.
#
#  ── CE QUI CHANGE PAR RAPPORT À PIAF, ET CE QUE ÇA IMPLIQUE ──────────
#  ⛔⛔ LE PRODUCTEUR NE SORT QU'UN RUN PAR HEURE, avec 47 à 68 min de
#  latence (mesuré le 09/09 ; le 08/09 la note parlait de H+2 h 40 — ce
#  chiffre n'est PAS une constante). Trois conséquences, et il faut les
#  tenir ensemble :
#
#   1. Le timer passe toutes les 10 min quand même. Un rendez-vous
#      horaire fixe raterait la moitié des runs d'une demi-heure, et
#      attendrait alors soixante minutes pour rien.
#   2. ⛔ CINQ PASSAGES SUR SIX NE FONT RIEN et sortent en code 3. C'est
#      le cas NOMINAL. Le service systemd doit porter
#      `SuccessExitStatus=3` — sans lui il est rouge en permanence, la
#      faute que `bw-agrume-ingest-pi.service` a déjà corrigée une fois.
#   3. ⛔ ET LE VOYANT NE VOIT DONC QU'UN PING PAR HEURE. Le réglage
#      healthchecks n'est PAS celui de PIAF (période 10 min / grâce
#      25 min) mais celui de PI : **période 1 h · grâce 30 min** — alerte
#      après ~90 min de silence, soit un run entier manqué plus une
#      marge. Régler 10 min ici enverrait un DOWN toutes les heures sur
#      une chaîne parfaitement saine.
#
#  ⛔⛔ LE VERROU DE CONCURRENCE, ET IL SERT PLUS QU'ON NE CROIT.
#  Un run met 42 s en temps normal (mesuré le 09/09), mais 24 requêtes
#  retentées quatre fois chacune tiennent 20 minutes — deux passages
#  chevaucheraient. DEUX processus écrivant le même index : le second
#  lirait l'index d'avant, y inscrirait ses clés, et effacerait celles
#  du premier. Des objets EN LIGNE et HORS INDEX, invisibles et payés —
#  le motif des 18 orphelins des 12-13/08, par un autre chemin.
#  `flock -n` refuse de démarrer plutôt que de doubler. Un passage sauté
#  n'est pas un trou : le run reste publié 4,25 jours au portail, et le
#  passage suivant le reprendra dix minutes plus tard.
#
#  Usage :  ./run-ingest-pi-rafale.sh
#           ./run-ingest-pi-rafale.sh --sans-ecriture
#           ./run-ingest-pi-rafale.sh --verifier
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${BW_PYTHON:-$HOME/venv-balise/bin/python}"
ALERTES_FILE="${BW_ALERTES_ENV:-$HOME/.balise-watch-alertes.env}"
VERROU="${BW_PI_RAFALE_VERROU:-/tmp/bw-agrume-pi-rafale.lock}"
# ⚠️ PAS dans /tmp : le compteur doit survivre à un redémarrage du VPS,
# sinon une panne longue se remettrait à zéro toute seule au pire moment.
COMPTEUR="${BW_PI_RAFALE_COMPTEUR:-$HOME/.bw-agrume-pi-rafale-echecs}"
# ⛔ 27/08 — LE VOYANT CLIGNOTAIT POUR UNE PASSE PERDUE SUR TRENTE-SIX.
# Voir le pavé « CE QUE LE VOYANT SURVEILLE » plus bas.
SEUIL_ECHECS="${BW_PI_RAFALE_SEUIL_ECHECS:-3}"
# ⛔ 07/09 — ET IL CLIGNOTAIT AUSSI DANS L'AUTRE SENS. Les 05 et 06/09,
# la passerelle a rendu 203 octets en HTTP 200 PAR BOUFFÉES pendant
# ~8 h cumulées : trois passes perdues → DOWN, UNE passe qui passe →
# UP, trois perdues → DOWN… Trente « voyant tombe » au journal, une
# quinzaine de mails DOWN/UP dans la boîte de Yann pour UNE panne amont.
# Le remède est symétrique au premier : le voyant, une fois tombé, ne se
# relève qu'après SEUIL_REPRISE réussites CONSÉCUTIVES. Trente minutes
# de passes fraîches, pas une passe chanceuse au milieu d'une bouffée.
SEUIL_REPRISE="${BW_PI_RAFALE_SEUIL_REPRISE:-3}"
REPRISE="$COMPTEUR.reprise"

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

PING="${BW_AGRUME_PI_RAFALE_PING_URL:-}"

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
  dire "⚠️ BW_AGRUME_PI_RAFALE_PING_URL absente de $ALERTES_FILE — PERSONNE NE SURVEILLE CETTE CHAÎNE"
  bw_avertir_config BW_AGRUME_PI_RAFALE_PING_URL "$ALERTES_FILE" bw-agrume-pi-rafale "CETTE CHAINE (rafale AROME-PI)"
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
#  ⛔ LE TIMER REPASSE TOUTES LES 10 MIN, LE PRODUCTEUR PUBLIE TOUTES
#  LES HEURES. Cinq passages sur six ne trouvent rien de neuf et
#  sortent en code 3, qui ne pingue rien — c'est le cas NOMINAL, comme
#  pour l'ingestion PI et contrairement à PIAF, où il y a toujours
#  quelque chose à faire.
#
#  ⚠️ CE QUE ÇA CHANGE POUR LE VOYANT : il ne voit qu'UN ping par
#  heure. Le réglage de PIAF (période 10 min) enverrait donc un DOWN à
#  chaque heure sur une chaîne parfaitement saine.
#
#  ⓘ Réglage du check, côté healthchecks.io :
#     période 1 h · grâce 30 min
#  → alerte après ~90 min de silence, soit un run entier manqué plus
#  une marge. Assez lâche pour absorber une latence de publication qui
#  glisse de 47 à 68 min, assez serré pour que « la rafale à venir » ne
#  soit pas vieille de trois heures sans que personne ne le sache.
#
#  ══════════════════════════════════════════════════════════════════
#  ⛔⛔ 27/08 — UN `/fail` COURT-CIRCUITE CETTE GRÂCE, ET C'EST CE QUI
#     A REMPLI LA BOÎTE DE YANN.
#
#  Le réglage ci-dessus est juste : trois passages manqués avant de
#  crier. Mais il ne s'applique qu'au SILENCE. Un `/fail` explicite,
#  lui, fait tomber le voyant SUR-LE-CHAMP — grâce ou pas.
#
#  Nuit du 26 au 27/08, sur la chaîne PIAF : la passerelle
#  Météo-France sature par bouffées. SIX passes perdues sur ~36, jamais
#  deux d'affilée, douze mails DOWN/UP pour une chaîne qui n'a jamais
#  eu plus de dix minutes de retard.
#
#  ⚠️ ICI LE MÉCANISME EST LE MÊME, MAIS LE RATTRAPAGE EST MEILLEUR :
#  le run reste publié 4,25 jours au portail, donc un échec est repris
#  À L'IDENTIQUE dix minutes plus tard — ce n'est même pas un run plus
#  vieux qu'on rattrape, c'est le même. Raison de plus pour se taire
#  aux deux premiers.
#
#  ⚠️ Un voyant qui crie pour une perte SANS CONSÉQUENCE apprend à
#  être ignoré, et c'est la seule panne dont ce projet ne se remet
#  pas : le jour où il criera pour de bon, personne ne regardera.
#
#  Donc : on COMPTE les échecs consécutifs et on ne pingue `/fail`
#  qu'au troisième. En dessous, on se TAIT — et le silence est déjà
#  surveillé, par la grâce de 30 min réglée plus haut. Les deux
#  mécanismes disent alors la même chose au même moment (~90 min sans
#  run frais), l'un explicitement, l'autre par défaut.
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
  dire "⏭️  une ingestion est DÉJÀ en cours — ce passage est sauté (pas un échec : le run reste au portail, le passage suivant le reprendra)"
  exit 3
fi

"$PY" "$ICI/ingest_pi_rafale.py" "$@"
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
    n=$(lire_compteur)
    if [ "$n" -ge "$SEUIL_ECHECS" ]; then
      # ⛔ 07/09 — le voyant est TOMBÉ : une réussite isolée au milieu
      # d'une bouffée ne le relève pas. On compte les réussites
      # d'affilée, et on se tait jusqu'à SEUIL_REPRISE.
      r=$(( $(tr -cd '0-9' < "$REPRISE" 2>/dev/null || echo 0) + 1 ))
      if [ "$r" -lt "$SEUIL_REPRISE" ]; then
        echo "$r" > "$REPRISE" 2>/dev/null || dire "⚠️ $REPRISE non inscriptible"
        dire "✅ run ingéré, reprise $r/$SEUIL_REPRISE — le voyant reste tombé (pas de ping)"
        exit "$code"
      fi
      dire "✅ $r réussites CONSÉCUTIVES (seuil $SEUIL_REPRISE) — le voyant se relève"
    fi
    # ⚠️ Remise à zéro AVANT le ping : si le ping échoue (réseau), on
    # veut quand même avoir enregistré que la chaîne est repartie.
    echo 0 > "$COMPTEUR" 2>/dev/null || dire "⚠️ $COMPTEUR non inscriptible"
    rm -f "$REPRISE"
    pinguer "" "run ingéré et écrit"
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
    # Un échec casse la série de réussites : la reprise repart de zéro.
    rm -f "$REPRISE"
    if [ "$n" -ge "$SEUIL_ECHECS" ]; then
      dire "⛔ $n échecs CONSÉCUTIFS (seuil $SEUIL_ECHECS) — le voyant tombe"
      pinguer /fail "ingest_pi_rafale.py a rendu le code $code — $n échecs consécutifs"
    else
      # ⚠️ Aucun ping du tout, pas même un succès : le voyant doit
      # rester sur la grâce, pas repartir à zéro sur un run perdu.
      dire "⚠️ échec $n/$SEUIL_ECHECS (code $code) — pas encore de /fail : le passage suivant reprendra le même run dans 10 min"
    fi
    ;;
esac

exit "$code"
