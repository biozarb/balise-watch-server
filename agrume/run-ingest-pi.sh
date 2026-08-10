#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  run-ingest-pi.sh — lance l'ingestion AROME-PI sur le VPS (10/08/2026)
#
#  Étape 8 bis. Même motif que `run-poller.sh`, et pour la même raison
#  déjà payée deux fois : `~/.balise-watch-*.env` est écrit en
#  `export VAR=…`, une syntaxe que systemd NE SAIT PAS lire dans un
#  EnvironmentFile. **C'est le script qui source, pas l'unité.**
#
#  ⚠️ DEUX fichiers d'environnement ici, et c'est nouveau :
#      ~/.balise-watch-model-verif.env  →  METEOFRANCE_API_KEY
#      ~/.balise-watch-r2.env           →  R2_* (écriture sur wind-grid)
#  Le second n'existait que pour LIRE : jusqu'au 10/08 le jeton R2 du
#  VPS ne pouvait ni lire ni écrire `wind-grid` (AccessDenied sur les
#  trois opérations, sondé). L'étape 8 bis a demandé un jeton élargi.
#
#  ⚠️ AUCUNE CLÉ NE S'AFFICHE. Pas de `set -x`, et le script ne les
#  imprime pas, pas même tronquées.
#
#  Usage :  ./run-ingest-pi.sh              # dernier run publié
#           ./run-ingest-pi.sh --tke        # arguments passés tels quels
# ══════════════════════════════════════════════════════════════════════
set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${BW_PYTHON:-$HOME/venv-balise/bin/python}"

charger() {
  local f="$1" quoi="$2"
  if [ -r "$f" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$f"
    set +a
  else
    # ⚠️ Refuser de démarrer plutôt que tourner en boucle sur des erreurs
    # d'authentification : un service qui redémarre toutes les cinq
    # secondes RESSEMBLE à un service qui marche.
    echo "❌ $f illisible — l'ingestion PI a besoin de $quoi" >&2
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
# lui, ne saura écrire QUE `balise-watch-grids`.
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
# DÉFINITIVES — partiraient dans le mauvais compartiment, et personne
# ne le verrait avant que le composite ne trouve rien à lire.
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

exec "$PY" "$ICI/ingest_pi.py" "$@"
