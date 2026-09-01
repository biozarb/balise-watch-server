#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  run-ingest-pi.sh — lance l'ingestion AROME-PI sur le VPS (10/08/2026)
#
#  Étape 8 bis. Même motif que `run-poller.sh` et `model-verif/run.sh`,
#  et pour la même raison déjà payée deux fois : `~/.balise-watch-*.env`
#  est écrit en `export VAR=…`, une syntaxe que systemd NE SAIT PAS lire
#  dans un EnvironmentFile. **C'est le script qui source, pas l'unité.**
#
#  ⚠️ TROIS fichiers d'environnement, et l'ORDRE compte (voir plus bas).
#  ⚠️ AUCUNE CLÉ NE S'AFFICHE. Pas de `set -x`, et rien n'est imprimé,
#  pas même tronqué.
#
#  Usage :  ./run-ingest-pi.sh              # dernier run complet publié
#           ./run-ingest-pi.sh --tke        # arguments passés tels quels
#           ./run-ingest-pi.sh --run 2026-08-10T17:00:00Z
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${BW_PYTHON:-$HOME/venv-balise/bin/python}"
ALERTES_FILE="${BW_ALERTES_ENV:-$HOME/.balise-watch-alertes.env}"

# ══════════════════════════════════════════════════════════════════════
#  ⚠️ LES ALERTES SE CHARGENT EN PREMIER — leçon du 03/08
#  Le tout premier échec possible est « un fichier d'environnement est
#  absent ». Si le canal d'alerte vivait DANS l'un de ces fichiers,
#  cette alerte-là partirait dans le vide, et la panne aurait exactement
#  l'allure d'un service qui marche.
# ══════════════════════════════════════════════════════════════════════
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

PING="${BW_AGRUME_PI_PING_URL:-}"

dire() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2; }

pinguer() {
  # $1 = "" pour un succès, "/fail" pour un échec ; $2 = corps éventuel.
  [ -n "$PING" ] || return 0
  curl -fsS -m 10 --retry 2 --data-binary "${2:-}" "${PING}$1" >/dev/null 2>&1 \
    || dire "⚠️ ping '$1' non parti (réseau ?) — le check passera en retard"
}

if [ -z "$PING" ]; then
  # ⚠️ Un job qui pingue dans le vide a EXACTEMENT l'allure d'un job
  # surveillé. La panne ne se verrait que le jour où l'on irait chercher
  # des colonnes qui n'existent pas.
  dire "⚠️ BW_AGRUME_PI_PING_URL absente de $ALERTES_FILE — PERSONNE NE SURVEILLE CETTE CHAÎNE"
  bw_avertir_config BW_AGRUME_PI_PING_URL "$ALERTES_FILE" bw-agrume-ingest-pi "CETTE CHAINE (ingestion AROME-PI)"
fi

charger() {
  f="$1"; quoi="$2"
  if [ -r "$f" ]; then
    set -a
    # shellcheck source=/dev/null
    . "$f"
    set +a
  else
    # ⚠️ Refuser de démarrer plutôt que tourner en boucle sur des erreurs
    # d'authentification : un service qui redémarre toutes les cinq
    # secondes RESSEMBLE à un service qui marche.
    dire "❌ $f illisible — l'ingestion PI a besoin de $quoi"
    pinguer /fail "fichier d'environnement illisible : $f ($quoi)"
    exit 78   # EX_CONFIG
  fi
}

charger "${BW_MF_ENV:-$HOME/.balise-watch-model-verif.env}" "la clé Météo-France"
charger "${BW_R2_ENV:-$HOME/.balise-watch-r2.env}" "R2_ACCOUNT_ID"

# ⚠️⚠️ UN TROISIÈME FICHIER, ET C'EST DÉLIBÉRÉ — NE PAS ÉCRASER LE
# JETON EXISTANT.
# `~/.balise-watch-r2.env` porte le jeton des PACKS, qui sait écrire
# `balise-watch-packs` et `model-verif` et **rien d'autre** (sondé le
# 10/08 : AccessDenied sur `balise-watch-grids`). Le jeton d'AGRUME,
# lui, ne sait écrire QUE `balise-watch-grids`.
#
# Remplacer les `R2_*` du premier fichier par ceux du second CASSERAIT
# `balise-entretien`, `balise-infoclimat` et `bw-model-*`, qui le
# partagent — et ça se verrait des heures plus tard, sur un autre
# service. Chaque jeton garde donc son fichier, et celui-ci est chargé
# EN DERNIER pour qu'il gagne, dans ce processus seulement.
charger "${BW_AGRUME_R2_ENV:-$HOME/.balise-watch-agrume-r2.env}" \
        "le jeton R2 d'AGRUME (écriture sur balise-watch-grids)"

# ⚠️ AGRUME écrit sur R2 et NULLE PART AILLEURS. Le quota Storage de
# Supabase a déjà cassé le projet le 30/07, et cette archive CROÎT par
# construction — 24 runs par jour.
export STORAGE_BACKEND=r2

# ⚠️⚠️ DEUX NOMS POUR LE MÊME MAGASIN, ET ILS NE SE RESSEMBLENT PAS.
# Le code d'AGRUME porte partout le défaut `"wind-grid"` : c'est le nom
# du bucket **Supabase**, hérité de la chaîne d'origine. Côté **R2**, le
# compartiment s'appelle **`balise-watch-grids`** — vérifié sur le
# dashboard le 10/08 : le compte a `balise-watch-grids` (806 objets,
# 840 Mo, contenant `agrume/`, `arome/`, `arpege/`),
# `balise-watch-isobars`, `balise-watch-packs` et `model-verif`.
# **Aucun compartiment ne s'appelle `wind-grid`.**
#
# ⚠️ Et `~/.balise-watch-r2.env` pose `R2_BUCKET=balise-watch-packs`
# pour les packs. Sans la ligne ci-dessous, les colonnes PI —
# DÉFINITIVES — partiraient dans le mauvais compartiment, et personne ne
# le verrait avant que le composite ne trouve rien à lire.
#
# ⓘ C'est aussi ce qui m'a fait publier un mauvais diagnostic : une
# sonde d'écriture sur `wind-grid` rend `AccessDenied`, exactement comme
# un refus de droits — alors que le compartiment n'existe simplement
# pas. *Un code d'erreur d'API n'est pas un diagnostic.*
export R2_BUCKET="${AGRUME_R2_BUCKET:-balise-watch-grids}"

# Sans ça, `print()` est bufferisé par blocs de 8 Ko quand la sortie ne
# va pas vers un terminal : le journal n'apparaîtrait qu'à la fin, d'un
# coup — donc trop tard pour voir un run qui dérape.
export PYTHONUNBUFFERED=1

# ══════════════════════════════════════════════════════════════════════
#  ⚠️⚠️ CE QUE LE VOYANT SURVEILLE, ET CE QU'IL NE SURVEILLE PAS
#
#  Le timer repasse toutes les 10 minutes, mais PI ne sort qu'une fois
#  par heure : **cinq passages sur six n'ont RIEN à faire.** Pinguer à
#  chaque passage garderait le voyant au vert pendant que la chaîne
#  aurait cessé d'ÉCRIRE depuis des jours — c'est le « faux vert » que
#  ce projet a déjà eu deux fois (quotas du 30/07, découverts par un
#  mail du fournisseur).
#
#  On ne pingue donc AU SUCCÈS que lorsqu'un run a été RÉELLEMENT INGÉRÉ
#  ET ÉCRIT (code 0). « Rien à faire » (code 3) ne pingue rien et ne
#  compte pas non plus comme un échec : c'est le cas nominal, cinq fois
#  sur six.
#
#  ⓘ Réglage du check, côté healthchecks.io :
#     période 1 h (PI sort 24 fois par jour) · grâce 1 h
#  → alerte après ~2 h de silence, soit deux runs manqués. Assez lâche
#  pour absorber la latence de complétion mesurée (entre +24 et +52 min),
#  assez serré pour ne pas laisser passer une demi-journée.
#
#  Ce voyant s'allume en rouge dans trois cas, tous légitimes : le timer
#  ne tourne plus, le portail ne répond plus (clé expirée comprise), ou
#  R2 refuse l'écriture.
# ══════════════════════════════════════════════════════════════════════
"$PY" "$ICI/ingest_pi.py" "$@"
code=$?

case "$code" in
  0)
    pinguer "" "run ingéré et écrit"
    ;;
  3)
    dire "rien à faire (code 3) — aucun ping, c'est le cas nominal"
    ;;
  *)
    pinguer /fail "ingest_pi.py a rendu le code $code"
    ;;
esac

exit "$code"
