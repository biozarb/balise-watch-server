#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  run.sh — l'enveloppe des jobs nocturnes (07/08/2026,
#           3e mode « garde-fou-r2 » ajouté le 10/08/2026)
#
#  Usage :  run.sh collect | run.sh score | run.sh garde-fou-r2
#           run.sh agrume         (4e mode, lot I  du 13/08/2026)
#           run.sh arome          (5e mode, lot S0.5 du 22/08/2026)
#           run.sh collect-p2     (6e mode, lot S0.6 du 22/08/2026 —
#                                  INERTE tant que son timer n'est pas
#                                  installé, et il ne l'est pas)
#           run.sh collect-reduit (7e mode, lot S0.11 du 23/08/2026 —
#                                  le groupe réduit sur les candidates)
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
  collect|collect-p2|collect-reduit|score|garde-fou-r2|agrume|arome) ;;
  *) echo "usage: run.sh collect|collect-p2|collect-reduit|score|garde-fou-r2|agrume|arome" >&2
     exit 2 ;;
esac

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Où vit le job de ce mode (10/08/2026) ────────────────────────────
# Ajouté avec le garde-fou R2. Les deux premiers modes sont des jobs
# `model-verif` et vivent à côté de ce script ; la jauge R2 n'a rien à
# voir avec le score des modèles et vit dans `tools/`, avec les autres
# outils d'infrastructure (`audit_storage.py`, `purge_*.py`).
#
# ⚠️ On étend cette enveloppe plutôt que d'en écrire une deuxième. Tout
# ce qui suit — verrou expirant, rotation de journal, chargement des
# .env dans le bon ordre, comptage des échecs consécutifs, ping
# Healthchecks, e-mail au sujet translittéré — a été payé au prix de
# plusieurs pannes. Le recopier pour un troisième job, c'est s'engager
# à corriger deux fois chaque bug suivant.
# `LIBELLE` sert de sujet d'alerte. Sans lui, une jauge R2 qui déborde
# enverrait un mail intitulé « score modèles » — et on chercherait le
# problème dans la mauvaise moitié du projet.
#
# ⛔ ET `EXTRA` : LES ARGUMENTS QUE LE MODE IMPOSE, DÉRIVÉS ICI ET PAS
# RECOPIÉS DANS L'UNITÉ SYSTEMD (lot S0.6, 22/08/2026). La passe 2 de
# la collecte a besoin de `--passe 2`. Le mettre dans l'`ExecStart`
# marcherait — jusqu'au jour où quelqu'un réinstalle l'unité sans le
# drapeau : la passe 2 collecterait alors TOUS les modèles, dans la
# fenêtre horaire de 04:35, et l'archive porterait deux fois les mêmes
# lignes sous deux clés. Ici, le mode et son drapeau ne peuvent pas se
# séparer.
EXTRA=()
case "$MODE" in
  collect|score)  SCRIPT="$ICI/$MODE.py";               LIBELLE="score modeles" ;;
  # ⚠️ UN MODE À PART, DONC UN VERROU, UN COMPTEUR D'ÉCHECS ET UN PING
  # À PART — et c'est tout l'intérêt. `run.sh collect --passe 2`
  # aurait partagé `verrou.collect` avec la passe 1 : le soir où la
  # passe 1 déborde, la passe 2 serait sortie sur « run déjà en
  # cours », SANS ALERTE et sans une ligne dans le journal du bon job.
  # Une nuit à une passe sur deux doit se voir, pas se taire.
  collect-p2)     SCRIPT="$ICI/collect.py"; EXTRA=(--passe 2)
                  LIBELLE="score modeles (passe 2 - surface)" ;;
  # ⭐ LE GROUPE RÉDUIT SUR LES CANDIDATES (lot S0.11, 23/08/2026).
  # ⚠️ UN SCRIPT NEUF, DONC UN VERROU, UN COMPTEUR D'ÉCHECS ET UN PING
  # À PART — même raison que `collect-p2` : la nuit où la passe de
  # 03:19 déborde, celle de 05:00 doit échouer SOUS SON PROPRE NOM,
  # avec sa propre alerte et sa propre ligne de journal. Un verrou
  # partagé la ferait sortir sur « run déjà en cours », en silence.
  # ⛔ Et il n'a AUCUN drapeau `EXTRA` : `collect_reduit.py` n'a pas de
  # `--passe`. Sa population et son cap se calculent tout seuls, à
  # chaque nuit, depuis les référentiels et le budget mesuré.
  collect-reduit) SCRIPT="$ICI/collect_reduit.py"
                  LIBELLE="score modeles (groupe reduit - candidates)" ;;
  garde-fou-r2)   SCRIPT="$ICI/../tools/audit_r2.py";   LIBELLE="garde-fou R2" ;;
  agrume)         SCRIPT="$ICI/agrume_fcst.py";         LIBELLE="flux AGRUME" ;;
  # ⚠️ CE MODE-CI N'ARCHIVE PAS HIER, IL ARCHIVE AUJOURD'HUI, et c'est
  # la seule différence de fond avec `agrume`. Les tuiles `arome/sol`
  # sont RÉÉCRITES EN PLACE toutes les 3 h par l'Action `arome-wind` :
  # il n'existe aucune archive des runs passés. Un run manqué n'est
  # donc pas « à rattraper demain », il est PERDU — d'où l'horaire
  # serré du timer (06:00 UTC, entre la publication du run 00 Z vers
  # 05:42 et son écrasement vers 08:30) et d'où l'alerte.
  arome)          SCRIPT="$ICI/arome_fcst.py";          LIBELLE="flux AROME R2" ;;
esac
if [[ ! -f "$SCRIPT" ]]; then
  echo "job introuvable : $SCRIPT" >&2; exit 2
fi
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
if [[ "$MODE" == "collect-p2" ]]; then
  # ⚠️ 40 MIN COMME `collect`, ET IL FAUT SAVOIR CE QU'ILS COUVRENT :
  # jusqu'à `ATTENTE_PASSE_MAX_S` = 25 min d'attente de quota au
  # démarrage (si la passe 1 a débordé sur son heure), puis ~8 min de
  # collecte à 965 points. 33 min mesurés au pire, 40 de garde.
  # ⛔ Relever l'un sans l'autre casserait le raisonnement : c'est le
  # couple (attente bornée, chien de garde) qui tient, pas l'un des deux.
  MAX_MINUTES="${BW_MODEL_VERIF_P2_MAX_MINUTES:-40}"
  # Même nature de perte que `collect` : une nuit de prévisions non
  # collectée ne se rattrape jamais. Alerte au PREMIER échec.
  SEUIL_ALERTE=1
elif [[ "$MODE" == "collect-reduit" ]]; then
  # ⚠️ 40 MIN, ET IL FAUT SAVOIR CE QU'ELLES COUVRENT — c'est le COUPLE
  # (attente bornée, chien de garde) qui tient, jamais l'un des deux :
  # jusqu'à `collect.ATTENTE_PASSE_MAX_S` = 25 min d'attente de quota au
  # démarrage (si la passe Pioupiou de 03:19 a débordé sur son heure),
  # puis ~7,6 min de collecte à 2 905 points (4 067 pondérés ÷ 534,5
  # pondérés/min, la cadence mesurée le 22/08). 32,6 min au pire, 40 de
  # garde, et le `TimeoutStartSec` de l'unité est à 50.
  # ⛔ Relever la borne d'attente sans relever ce chien de garde ferait
  # tuer la passe PENDANT qu'elle attend — et l'attente serait alors
  # pire que le refus (S0.6 §5).
  MAX_MINUTES="${BW_MODEL_VERIF_REDUIT_MAX_MINUTES:-40}"
  # ⛔ SEUIL_ALERTE=1, COMME `collect`. CE FLUX NE SE REJOUE PAS :
  # Open-Meteo n'a AUCUN historique de runs passés (mesuré le 08/08 :
  # 0/384). Une nuit manquée est perdue pour toujours — il n'y a pas de
  # `--day AAAA-MM-JJ` qui la ramène, et la fenêtre est étroite (05:00
  # UTC, entre la publication d'`icon_d2` 03 Z à 04:26 et celle de
  # `gfs_global` à 05:35).
  SEUIL_ALERTE=1
elif [[ "$MODE" == "collect" ]]; then
  MAX_MINUTES="${BW_MODEL_VERIF_MAX_MINUTES:-40}"
  # ⚠️ Une nuit non collectée est perdue définitivement — aucun modèle
  # Météo-France n'a d'historique de runs passés chez Open-Meteo (sondé
  # le 08/08). On alerte au PREMIER échec, pas au troisième comme le
  # poller Infoclimat, où un cycle raté se rattrape cinq minutes plus
  # tard.
  SEUIL_ALERTE=1
elif [[ "$MODE" == "agrume" ]]; then
  # Un objet lu sur R2 (660 Ko), une conversion, un objet écrit.
  # Mesuré à quelques secondes ; 10 min est déjà dix fois trop.
  MAX_MINUTES="${BW_AGRUME_FCST_MAX_MINUTES:-10}"
  # ⚠️ SEUIL_ALERTE=2, et c'est la SEULE différence de nature avec
  # `collect` : ce flux se REJOUE. Le produit A est encore là (il ne
  # se purge pas tant que l'arbitrage A1 n'est pas tranché), donc
  # une nuit manquée se rattrape par `run.sh agrume --day AAAA-MM-JJ`.
  # Alerter au premier échec ferait sonner pour une chose réparable,
  # et on cesserait de lire les alertes de `collect`, qui, elle, ne
  # se rattrape pas.
  SEUIL_ALERTE=2
elif [[ "$MODE" == "arome" ]]; then
  # 98 objets lus sur R2 (~540 Mo), un objet écrit. Mesuré le 22/08 :
  # 46 s de lecture, 78 s en tout. 15 min laisse dix fois la marge, et
  # reste sous le TimeoutStartSec de l'unité.
  MAX_MINUTES="${BW_AROME_FCST_MAX_MINUTES:-15}"
  # ⛔ SEUIL_ALERTE=1, COMME `collect` ET PAS COMME `agrume`, et la
  # raison est exactement la même que pour la collecte Open-Meteo :
  # CE FLUX NE SE REJOUE PAS. `arome-wind/ingest.py` réécrit ses tuiles
  # EN PLACE toutes les 3 h (bucket entièrement mutable), il n'existe
  # aucune archive des runs passés. Une nuit manquée est perdue pour
  # toujours — il n'y a pas de `--day AAAA-MM-JJ` qui la ramène.
  # ⚠️ Et la fenêtre est étroite : le run 00 Z n'est en ligne que de
  # ~05:42 à ~08:30 UTC. Un échec doit sonner le matin même, tant qu'un
  # rattrapage à la main est encore possible.
  SEUIL_ALERTE=1
elif [[ "$MODE" == "garde-fou-r2" ]]; then
  # Un listing complet des buckets, rien de plus. 10 min est déjà très
  # large ; si un jour ça dépasse, c'est que le compte a explosé — et
  # c'est précisément ce que ce job est censé annoncer.
  MAX_MINUTES="${BW_GARDE_FOU_R2_MAX_MINUTES:-10}"
  # ⚠️ SEUIL_ALERTE=1 : un seuil de stockage franchi n'est PAS un
  # incident passager qu'on peut attendre de voir se répéter. Chaque
  # nuit d'attente est une nuit de facturation, et la valeur de ce job
  # est de prévenir tôt. Attendre un second échec annulerait sa raison
  # d'être.
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
# ⚠️ Les tirets sont translittérés en `_` (10/08/2026, ajout du mode
# `garde-fou-r2`). Sans ça, `${!PING_VAR}` porterait sur
# `BW_MODEL_GARDE-FOU-R2_PING_URL`, qui n'est pas un nom de variable
# shell valide : l'expansion rendrait vide, le job pinguerait dans le
# vide, et il aurait exactement l'allure d'un job surveillé.
PING_VAR="BW_MODEL_$(printf '%s' "$MODE" | tr '[:lower:]-' '[:upper:]_')_PING_URL"

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
    [[ -z "$sujet_h" ]] && sujet_h="balise watch"
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
  alerter "$LIBELLE ($MODE)" "fichier $ENV_FILE absent — rien ne peut tourner"
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
  alerter "$LIBELLE ($MODE)" \
    "variables absentes : ${manque[*]} — voir $SUPA_FILE et $ENV_FILE"
  exit 1
fi

PYTHON="${BW_PYTHON:-$(command -v python3)}"
if [[ ! -x "$PYTHON" ]]; then
  alerter "$LIBELLE ($MODE)" \
    "python3 introuvable ($PYTHON) — définir BW_PYTHON dans $ENV_FILE"
  exit 1
fi
# ⚠️ `boto3` n'est PAS dans le python3 système du VPS (sondé le 07/08) :
# il vit dans le venv désigné par BW_PYTHON. `storage.py` sort en Abort
# sans lui, donc on le constate ici, une fois, plutôt que de le
# découvrir au milieu d'une collecte.
if ! "$PYTHON" -c "import boto3" >/dev/null 2>&1; then
  alerter "$LIBELLE ($MODE)" \
    "boto3 absent de $PYTHON — l'archive R2 ne peut pas s'écrire"
  exit 1
fi
# ⚠️ Même raisonnement pour numpy, que SEUL le mode `agrume` exige :
# le produit A est un `.npz`. On le constate ici, une fois, plutôt
# que de le découvrir dans une trace d'import à 03:40. ⛔ Et on ne
# fabrique PAS de version « qui saute si numpy est absent » : un job
# qui se désactive tout seul est un job dont on cesse de lire le
# journal (règle du lot P).
if [[ "$MODE" == "agrume" ]] && ! "$PYTHON" -c "import numpy" >/dev/null 2>&1; then
  alerter "$LIBELLE ($MODE)" \
    "numpy absent de $PYTHON — le produit A ne peut pas se relire"
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
  # `${EXTRA[@]+"${EXTRA[@]}"}` et pas `"${EXTRA[@]}"` : sous `set -u`,
  # un tableau VIDE fait sortir bash en erreur avant la 4.4. Le VPS est
  # en 5.x, mais un script d'infrastructure ne doit pas dépendre d'une
  # version de shell qu'il ne vérifie pas.
  timeout --signal=TERM --kill-after=60s "${MAX_MINUTES}m" \
    "$PYTHON" "$SCRIPT" --out "$ETAT" ${EXTRA[@]+"${EXTRA[@]}"} "${@:2}" \
    2>&1 | tee -a "$LOG"
  code=${PIPESTATUS[0]}
else
  dire "⚠️ timeout absent — run sans chien de garde (seul TimeoutStartSec borne)"
  "$PYTHON" "$SCRIPT" --out "$ETAT" ${EXTRA[@]+"${EXTRA[@]}"} "${@:2}" \
    2>&1 | tee -a "$LOG"
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
  alerter "$LIBELLE ($MODE) en echec" \
    "$n run(s) consécutif(s) en échec (code $code, ${duree}s). Dernières lignes :
$(tail -n 25 "$LOG")"
fi

# ⚠️ On sort NON NUL, contrairement à `poller.sh`. Un poll raté se
# rattrape cinq minutes plus tard ; une nuit de collecte ratée, jamais.
# On veut que `systemctl --failed` et `systemctl status` le disent, en
# plus de Healthchecks.
exit "$code"
