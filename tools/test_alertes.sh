#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  tools/test_alertes.sh — LE BANC DES CANAUX D'ALERTE  (lot LV, 01/09/2026)
#
#  ⛔ POURQUOI CE BANC EXISTE. Cinq runners criaient « PERSONNE NE
#  SURVEILLE » depuis des semaines et RIEN NE ROUGISSAIT : ni un banc,
#  ni le déploiement, ni personne. `BW_AGRUME_CONFRONTATION_PING_URL` a
#  crié 20 jours d'affilée. Le détecteur marchait ; c'est son cri qui
#  n'allait nulle part.
#
#  ⭐ LA MUTATION CENTRALE — écrite ici en toutes lettres parce que
#  c'est elle qui décide si ce banc vaut quelque chose :
#      RETIRER UNE VARIABLE LUE PAR UN RUNNER DOIT FAIRE ROUGIR,
#      Y COMPRIS QUAND SON NOM EST CONSTRUIT.
#  Les onze `BW_MODEL_*_PING_URL` ne se grepent pas — `run.sh` les
#  fabrique à partir du mode. Un banc qui chercherait des noms littéraux
#  serait vert en ratant onze variables sur dix-neuf : c'est exactement
#  ce qui est arrivé à la sonde du 31/08.
#
#  ⚠️ IL NE TOUCHE NI AU VPS, NI AU FICHIER D'ALERTES, NI AU RÉSEAU :
#  `msmtp`, `curl` et `systemd-cat` sont remplacés par des faux dans un
#  PATH temporaire, et c'est ce qui permet de vérifier que le chien
#  ABOIE — un chien de garde qu'on n'a jamais vu aboyer n'en est pas un.
#
#  Usage :  bash tools/test_alertes.sh      # depuis la racine du dépôt
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail
RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RACINE" || exit 1

VERTS=0; ROUGES=0
check() {  # $1 libellé · $2 obtenu · $3 attendu
  if [ "$2" = "$3" ]; then VERTS=$((VERTS+1))
  else ROUGES=$((ROUGES+1)); printf '  ❌ %s\n     obtenu  : %s\n     attendu : %s\n' "$1" "$2" "$3"; fi
}

TMP=$(mktemp -d "${TMPDIR:-/tmp}/bw-banc-alertes.XXXXXX") || exit 1
trap 'chmod -R u+w "$TMP" 2>/dev/null; rm -rf "$TMP"' EXIT

. tools/bw_inventaire_alertes.sh

# ══════════════════════════════════════════════════════════════════════
# A. L'INVENTAIRE EST DÉRIVÉ DU CODE, PAS ÉCRIT
# ══════════════════════════════════════════════════════════════════════
echo "▶ A. l'inventaire des variables lues"

check "A1  les 12 modes de run.sh sont énumérés" \
      "$(bw_inv_modes "$RACINE" | wc -l | tr -d ' ')" "12"
check "A2  ⭐ les 12 noms CONSTRUITS sont reconstitués" \
      "$(bw_inv_construites "$RACINE" | wc -l | tr -d ' ')" "12"
check "A3  le mode à tirets devient un nom de variable VALIDE" \
      "$(bw_inv_construites "$RACINE" | grep -c 'BW_MODEL_GARDE_FOU_R2_PING_URL' | tr -d ' ')" "1"
check "A4  ⛔ et JAMAIS un nom à tirets (l'expansion rendrait vide)" \
      "$(bw_inv_lues "$RACINE" | grep -c -- '-' | tr -d ' ')" "0"

# ⭐⭐ A5 — LA TRANSLITTÉRATION N'EST PAS RECOPIÉE DE MÉMOIRE : on
# EXTRAIT la ligne `PING_VAR=` de run.sh et on l'exécute pour chaque
# mode. Si quelqu'un change le `tr` là-bas sans le changer ici, ce banc
# rougit — au lieu de laisser diverger deux copies, ce qui est la faute
# du lot LD transposée à ce fichier.
LIGNE_PV=$(grep -m1 '^PING_VAR=' model-verif/run.sh)
CALCULES=$(for M in $(bw_inv_modes "$RACINE"); do
             MODE="$M"; eval "$LIGNE_PV"; printf '%s\n' "$PING_VAR"; done | sort -u)
check "A5  ⭐ l'inventaire == ce que run.sh CALCULE réellement, mode par mode" \
      "$(diff <(printf '%s\n' "$CALCULES") <(bw_inv_construites "$RACINE" | sort -u) >/dev/null && echo identique || echo DIVERGENT)" \
      "identique"

check "A6  20 variables de canal lues au total" \
      "$(bw_inv_lues "$RACINE" | wc -l | tr -d ' ')" "20"
check "A7  ⛔ un nom cité SEULEMENT en commentaire n'est pas 'lu'" \
      "$(bw_inv_lues "$RACINE" | grep -cE '^(BW_PING_FAIL_URL|BW_MAIL_TO)$' | tr -d ' ')" "0"

# ⭐ A8 — A7 ne suffit PAS, et la mutation nº 5 l'a montré : les deux noms
# du 03/08 sont cités entre accents graves, donc SANS `$`, et le motif ne
# les prendrait pas même en gardant les commentaires. La propriété qu'on
# veut vraiment est plus large : *du CODE mis en commentaire n'est plus
# du code.* C'est le cas fréquent — on commente un bloc, la variable
# reste écrite `${…}` — et lui seul discrimine. On le joue sur une
# fixture jetable, parce qu'aucun runner réel ne le porte aujourd'hui.
FIXT="$TMP/racine"; mkdir -p "$FIXT/traces/entretien"
printf '%s\n' \
  '# ancien code, mis en commentaire le 12/08 :' \
  '#   PING="${BW_MORT_PING_URL:-}"' \
  'PING="${BW_VIVANT_PING_URL:-}"' > "$FIXT/traces/entretien/entretien.sh"
check "A8  ⭐ du CODE mis en commentaire n'entre PAS dans l'inventaire" \
      "$(bw_inv_litterales "$FIXT" | grep -c 'BW_MORT_PING_URL' | tr -d ' ')" "0"
check "A9  ⓘ et la ligne vivante juste à côté, elle, y entre" \
      "$(bw_inv_litterales "$FIXT" | grep -c 'BW_VIVANT_PING_URL' | tr -d ' ')" "1"

# ══════════════════════════════════════════════════════════════════════
# B. L'EXEMPLE VERSIONNÉ ANNONCE TOUT CE QUE LE CODE LIT
# ══════════════════════════════════════════════════════════════════════
echo "▶ B. l'exemple versionné"

check "B1  ⭐ aucune variable lue n'est absente de l'exemple" \
      "$(comm -23 <(bw_inv_lues "$RACINE") <(bw_inv_exemple "$RACINE") | tr '\n' ' ' | sed 's/ *$//')" ""
check "B2  et l'exemple n'annonce rien que personne ne lit" \
      "$(comm -13 <(bw_inv_lues "$RACINE") <(bw_inv_exemple "$RACINE") | tr '\n' ' ' | sed 's/ *$//')" ""
check "B3  ⛔ la phrase périmée « ignoré en silence » a disparu de la DOCTRINE" \
      "$(grep -c 'canal ignoré en silence' "$BW_EXEMPLE_ALERTES" | tr -d ' ')" "0"
check "B4  ⓘ mais elle est CITÉE comme corrigée (une correction se date)" \
      "$(grep -c 'CORRIGÉ LE 01/09/2026' "$BW_EXEMPLE_ALERTES" | tr -d ' ')" "1"
check "B5  ⛔ l'exemple ne porte AUCUNE valeur réelle (pas de hc-ping avec UUID)" \
      "$(grep -cE 'hc-ping\.com/[0-9a-f]{8}-' "$BW_EXEMPLE_ALERTES" | tr -d ' ')" "0"

# ══════════════════════════════════════════════════════════════════════
# C. AUCUN RUNNER N'ÉCHAPPE À L'INVENTAIRE
# ══════════════════════════════════════════════════════════════════════
echo "▶ C. le périmètre des runners"

# ⛔ Le trou par lequel une variable s'échapperait : un script qui lit un
# `*_PING_URL` sans figurer dans BW_RUNNERS_ALERTE. Il serait invisible
# du banc ET du déploiement.
ORPHELINS=$(grep -rlE '\$\{?!?BW_[A-Z0-9_]*_PING_URL' --include='*.sh' . 2>/dev/null \
  | sed 's|^\./||' | grep -v '^tools/' | sort > "$TMP/vus"
  printf '%s\n' "$BW_RUNNERS_ALERTE" | sort > "$TMP/declares"
  comm -23 "$TMP/vus" "$TMP/declares" | tr '\n' ' ' | sed 's/ *$//')
check "C1  ⭐ aucun script hors liste ne lit un *_PING_URL" "$ORPHELINS" ""
check "C2  les 5 runners qui criaient appellent bien bw_avertir_config" \
      "$(grep -l 'bw_avertir_config ' model-verif/run.sh traces/infoclimat/poller.sh \
         agrume/run-ingest-pi.sh agrume/run-ingest-piaf.sh verif/run-confronter-quotidien.sh \
         2>/dev/null | wc -l | tr -d ' ')" "5"
check "C3  ⛔ le cri d'origine (dire) est CONSERVÉ à côté de l'alerte" \
      "$(grep -c 'PERSONNE NE SURVEILLE' model-verif/run.sh traces/infoclimat/poller.sh \
         agrume/run-ingest-pi.sh agrume/run-ingest-piaf.sh verif/run-confronter-quotidien.sh \
         | awk -F: '$2>0' | wc -l | tr -d ' ')" "5"
# ⛔ NE PAS CRIER AU LOUP. `collect-p2` et `tau` sont des modes réels dont
# l'unité porte « ne-pas-installer ». Leur variable n'est PAS un trou :
# c'est un mode sans job. Un contrôle qui les compte rougirait deux fois
# à chaque déploiement — et un contrôle qui crie au loup finit ignoré,
# c'est-à-dire dans l'état exact d'où vient ce lot.
check "C5  ⛔ un mode dont l'unité porte le marqueur n'est PAS installable" \
      "$(bw_inv_mode_installable "$RACINE" tau && echo installable || echo non)" "non"
check "C6  ⛔ et un mode VIVANT l'est (sinon le contrôle se tairait sur tout)" \
      "$(bw_inv_mode_installable "$RACINE" agrume-quart && echo installable || echo non)" "installable"
# ⭐ 01/09 (lot L12) : `oracle` les a rejoints le matin et les a
# QUITTÉS le soir — son unité a été installée une fois son check
# Healthchecks créé. Ce banc est ce qui empêche l'ordre inverse : le
# jour où une unité s'installe sans qu'on retire son marqueur, il
# rougit — et sans lui, le job tournerait des mois durant en disant
# « PERSONNE NE SURVEILLE » dans un journal que rien ne lit (lot LV).
check "C7  les deux seuls modes sans job sont collect-p2 et tau" \
      "$(for M in $(bw_inv_modes "$RACINE"); do bw_inv_mode_installable "$RACINE" "$M" || printf '%s ' "$M"; done)" \
      "collect-p2 tau "

check "C4  chaque runner a un repli si l'outillage manque (jamais de mort en prod)" \
      "$(grep -l 'bw_avertir_config() { :; }' model-verif/run.sh traces/infoclimat/poller.sh \
         agrume/run-ingest-pi.sh agrume/run-ingest-piaf.sh verif/run-confronter-quotidien.sh \
         2>/dev/null | wc -l | tr -d ' ')" "5"

# ══════════════════════════════════════════════════════════════════════
# D. ⭐⭐ LE CHIEN ABOIE — POUR DE VRAI
# ══════════════════════════════════════════════════════════════════════
echo "▶ D. bw_avertir_config : le cri sort du journal"

FAUX="$TMP/bin"; mkdir -p "$FAUX"
cat > "$FAUX/msmtp" <<'EOS'
#!/bin/sh
cat >> "$BANC_MAILS"; echo "--MAIL--" >> "$BANC_MAILS"
EOS
cat > "$FAUX/curl" <<'EOS'
#!/bin/sh
echo "$*" >> "$BANC_CURL"
EOS
cat > "$FAUX/systemd-cat" <<'EOS'
#!/bin/sh
cat >> "$BANC_JOURNAL"
EOS
chmod +x "$FAUX/msmtp" "$FAUX/curl" "$FAUX/systemd-cat"
export BANC_MAILS="$TMP/mails.txt" BANC_CURL="$TMP/curl.txt" BANC_JOURNAL="$TMP/journal.txt"
: > "$BANC_MAILS"; : > "$BANC_CURL"; : > "$BANC_JOURNAL"

PATH="$FAUX:$PATH"
export BW_ALERTE_MAIL="essai@example.invalid"
export BW_WEBHOOK_URL="https://ntfy.invalid/bw-essai"
export BW_ETAT_ALERTES="$TMP/etat"
. tools/bw_avertir_config.sh

bw_avertir_config BW_ESSAI_PING_URL /tmp/faux.env banc-essai "CE JOB"
check "D1  ⭐ un e-mail est PARTI (le chien aboie)" \
      "$(grep -c -- '--MAIL--' "$BANC_MAILS" | tr -d ' ')" "1"
check "D2  le webhook a été appelé" \
      "$(grep -c 'ntfy.invalid' "$BANC_CURL" | tr -d ' ')" "1"
check "D3  journald a reçu la ligne en ERREUR (-p err)" \
      "$(grep -c 'configuration incomplete' "$BANC_JOURNAL" | tr -d ' ')" "1"
check "D4  ⛔ le nom de la variable manquante est DANS le message" \
      "$(grep -q 'BW_ESSAI_PING_URL' "$BANC_MAILS" && echo oui || echo non)" "oui"
# ⭐ D4 bis — LE SUJET, PAS SEULEMENT LE CORPS. La mutation nº 15 a
# montré que D4 restait vert quand le nom sortait du sujet : le corps le
# portait encore. Or c'est la ligne de sujet qu'on lit dans une boîte de
# réception, et trois avertissements au même sujet se classent comme un
# doublon. La propriété est donc : le sujet NOMME la variable.
check "D4b ⭐ le SUJET de l'e-mail nomme la variable (pas seulement le corps)" \
      "$(grep -c '^Subject:.*configuration incomplete : BW_ESSAI_PING_URL absente' "$BANC_MAILS" | tr -d ' ')" "1"
check "D5  ⛔ AUCUN ping vers le check d'un autre job (règle « deux jobs, deux checks »)" \
      "$(grep -c 'hc-ping' "$BANC_CURL" | tr -d ' ')" "0"

bw_avertir_config BW_ESSAI_PING_URL /tmp/faux.env banc-essai "CE JOB"
bw_avertir_config BW_ESSAI_PING_URL /tmp/faux.env banc-essai "CE JOB"
check "D6  ⭐ UN SEUL cri par jour et par variable (283 e-mails auraient tué le canal)" \
      "$(grep -c -- '--MAIL--' "$BANC_MAILS" | tr -d ' ')" "1"

bw_avertir_config BW_AUTRE_PING_URL /tmp/faux.env banc-essai "CE JOB"
check "D7  mais une AUTRE variable crie le même jour (le jeton est par variable)" \
      "$(grep -c -- '--MAIL--' "$BANC_MAILS" | tr -d ' ')" "2"

# ⭐⭐ D8 — LE CAS QUI A PRODUIT LE LOT : un job qui crie TOUS LES JOURS.
# Avant ce lot, vingt jours de cris = zéro message. Maintenant, vingt
# jours = vingt messages, un par jour. On rejoue trois journées en
# vieillissant le jeton.
echo "2026-08-13" > "$BW_ETAT_ALERTES/cri.BW_ESSAI_PING_URL"
bw_avertir_config BW_ESSAI_PING_URL /tmp/faux.env banc-essai "CE JOB"
echo "2026-08-14" > "$BW_ETAT_ALERTES/cri.BW_ESSAI_PING_URL"
bw_avertir_config BW_ESSAI_PING_URL /tmp/faux.env banc-essai "CE JOB"
check "D8  ⭐⭐ un job qui crie 3 jours envoie 3 messages, pas 0 (le cas du lot)" \
      "$(grep -c -- '--MAIL--' "$BANC_MAILS" | tr -d ' ')" "4"

# ⭐⭐ D8 bis — LE DOSSIER D'ÉTAT SE PASSE EN ARGUMENT, ET C'EST LA
# PRODUCTION QUI L'A EXIGÉ. Une heure après le déploiement du 01/09, le
# poller a fait partir son push mais n'a écrit NI e-mail NI jeton :
# `balise-infoclimat.service` porte `ProtectHome=read-only` et ne peut
# écrire que dans `~/.balise-watch-infoclimat`. Sans jeton, le repli
# « échouer ouvert » envoyait un push TOUTES LES 5 MINUTES — 288 par
# jour. Le banc vérifie donc les deux moitiés : le 5e argument est bien
# utilisé, et les deux runners DURCIS le passent.
: > "$BANC_MAILS"
AILLEURS="$TMP/ailleurs"; mkdir -p "$AILLEURS"
bw_avertir_config BW_ARG_PING_URL /tmp/f.env banc "X" "$AILLEURS"
check "D8b ⭐ le 5e argument décide où va le jeton" \
      "$(cat "$AILLEURS/cri.BW_ARG_PING_URL" 2>/dev/null)" "$(date -u +%Y-%m-%d)"
bw_avertir_config BW_ARG_PING_URL /tmp/f.env banc "X" "$AILLEURS"
check "D8c ⭐ et il fait bien taire le second appel du jour" \
      "$(grep -c -- '--MAIL--' "$BANC_MAILS" | tr -d ' ')" "1"
check "D8d ⛔ les deux runners DURCIS passent leur dossier d'état inscriptible" \
      "$(grep -c 'bw_avertir_config .*"\$ETAT"' traces/infoclimat/poller.sh model-verif/run.sh \
         | awk -F: '$2==1' | wc -l | tr -d ' ')" "2"

check "D9  le jeton porte la date du jour, en UTC" \
      "$(cat "$BW_ETAT_ALERTES/cri.BW_ESSAI_PING_URL")" "$(date -u +%Y-%m-%d)"

# ⛔ D10 — ÉCHOUER OUVERT. Si l'état ne peut pas s'écrire, on crie CHAQUE
# fois : bruyant, jamais muet. Un dispositif d'alerte ne doit pas se
# taire parce que son propre état est cassé.
: > "$BANC_MAILS"
BLOQUE="$TMP/bloque"; mkdir -p "$BLOQUE"; chmod 500 "$BLOQUE"
BW_ETAT_ALERTES="$BLOQUE/etat" bw_avertir_config BW_BLOQ_PING_URL /tmp/f.env banc "X"
BW_ETAT_ALERTES="$BLOQUE/etat" bw_avertir_config BW_BLOQ_PING_URL /tmp/f.env banc "X"
check "D11 ⛔ jeton inécrivable → on crie QUAND MÊME, chaque fois" \
      "$(grep -c -- '--MAIL--' "$BANC_MAILS" | tr -d ' ')" "2"
chmod 700 "$BLOQUE"

: > "$BANC_MAILS"
bw_avertir_config "" /tmp/f.env banc "X"
check "D12 un appel sans variable ne fait rien et ne casse rien" \
      "$(grep -c -- '--MAIL--' "$BANC_MAILS" | tr -d ' ')" "0"
bw_avertir_config BW_RETOUR_PING_URL /tmp/f.env banc "X"
check "D13 ⛔ la fonction rend TOUJOURS 0 (elle ne doit jamais tuer un runner)" "$?" "0"

: > "$BANC_MAILS"
(unset BW_ALERTE_MAIL BW_WEBHOOK_URL
 BW_ETAT_ALERTES="$TMP/etat2" bw_avertir_config BW_MUET_PING_URL /tmp/f.env banc "X")
check "D14 sans canal configuré, rien ne part et rien ne casse" \
      "$(grep -c -- '--MAIL--' "$BANC_MAILS" | tr -d ' ')" "0"

# ══════════════════════════════════════════════════════════════════════
# E. LES UNITÉS DU DÉPÔT SONT LISIBLES (lot LV, réponse Q4)
# ══════════════════════════════════════════════════════════════════════
# ⛔⛔ CETTE SECTION NE PEUT PAS ÊTRE JOUÉE DEPUIS UNE SESSION COWORK
# (`device_bash`), ET ELLE Y REND UN FAUX ROUGE — vérifié le 02/09 : le
# montage du dossier partagé rapporte **600 pour les 37 fichiers**,
# alors que `stat` sur le Mac lui-même les donne tous en 644. Le banc
# n'y voit donc pas les permissions du dépôt, il voit celles du montage.
# ⇒ Jouer ce banc depuis Desktop Commander (le Mac) ou sur le VPS, comme
# le fait `deploy-agrume-vps.sh`. *Un banc qui lit un montage rend un
# verdict sur le montage.*
echo "▶ E. les modes des unités du dépôt"
# ⚠️ CES DEUX ASSERTIONS LISENT DES PERMISSIONS, donc elles n'ont de sens
# que sur un VRAI système de fichiers. Jouées à travers un montage réseau
# (une session Cowork qui voit le dépôt du Mac par `device_bash`), `stat`
# rend le mode du MONTAGE et non celui du fichier : 35 faux rouges.
# `BW_BANC_SANS_MODES=1` les saute alors EXPLICITEMENT — et le saut se
# DIT, il ne se déduit pas d'un silence.
if [ "${BW_BANC_SANS_MODES:-0}" = "1" ]; then
  echo "  ⓘ E1/E2 SAUTÉES — BW_BANC_SANS_MODES=1 (montage réseau : les modes ne sont pas ceux du dépôt)."
  echo "     ⛔ Elles doivent être rejouées sur le Mac ou sur le VPS avant de conclure."
else
if stat -f '%Lp' . >/dev/null 2>&1; then bw_mode() { stat -f '%Lp' "$1"; }
else bw_mode() { stat -c '%a' "$1"; }; fi
NON644=$(find . -name '*.service' -o -name '*.timer' \
  | grep -v node_modules | grep -v _to_delete \
  | while IFS= read -r f; do [ "$(bw_mode "$f")" = "644" ] || printf '%s ' "$f"; done)
check "E1  ⭐ AUCUN fichier d'unité du dépôt n'est en 600" "$(printf '%s' "$NON644")" ""
check "E2  ⓘ et il y en a bien 37 à vérifier (le périmètre n'a pas fondu)" \
      "$(find . -name '*.service' -o -name '*.timer' | grep -v node_modules | grep -v _to_delete | wc -l | tr -d ' ')" "37"
fi

# ══════════════════════════════════════════════════════════════════════
#  F. UN BANC N'ALERTE PAS LA PRODUCTION          (02/09/2026)
#
#  ⛔ POURQUOI. `model-verif/test_run_selftest.py` lance le VRAI `run.sh`
#  avec un `alertes.env` vide. Depuis le lot LV, « vide » veut dire
#  « aucune variable de ping », donc « PERSONNE NE SURVEILLE », donc un
#  cri. Mesuré sur le journal du VPS entre le 01/09 15:00 Z et le 02/09
#  09:00 Z : **93 cris, dont 50 venus d'un bac de banc — 54 % du total**,
#  et tous estampillés de l'identifiant de PRODUCTION.
#
#  ⚠️ ET LES CANAUX SE TAISAIENT PAR ACCIDENT, PAS PAR CONSTRUCTION : le
#  bac écrase `BW_ALERTES_FILE` par un fichier vide, donc les deux URL
#  restent indéfinies. Mais `_bac()` hérite de `os.environ` — un banc
#  lancé dans un shell qui a sourcé le vrai fichier POUSSERAIT sur le
#  téléphone. Ces assertions rendent la propriété vraie par
#  construction, au lieu de la laisser vraie gratuitement.
# ══════════════════════════════════════════════════════════════════════
echo
echo "▶ F. un banc n'alerte pas la production"

: > "$BANC_MAILS"; : > "$BANC_CURL"; : > "$BANC_JOURNAL"
rm -rf "$TMP/etat-banc"
BW_AVERTIR_CONFIG_BANC="banc-des-essais" \
  bw_avertir_config BW_BANC_PING_URL /tmp/faux.env bw-model-score "CE JOB" "$TMP/etat-banc"
check "F1  ⛔⛔ AUCUN e-mail ne part d'un banc, même avec BW_ALERTE_MAIL défini" \
      "$(grep -c -- '--MAIL--' "$BANC_MAILS" | tr -d ' ')" "0"
check "F2  ⛔⛔ AUCUN webhook non plus — le téléphone ne sonne pas pour un banc" \
      "$(grep -c 'ntfy.invalid' "$BANC_CURL" | tr -d ' ')" "0"
# ⭐ F3 — IL NE SE TAIT PAS, ET C'EST LE POINT. Un drapeau qui rendrait
# muet serait un désarmement à une variable près : posé par erreur en
# production, il effacerait le dispositif entier. Ici il RENOMME.
check "F3  ⭐⭐ le cri va QUAND MÊME dans journald (un drapeau ne doit pas rendre muet)" \
      "$(grep -c 'configuration incomplete' "$BANC_JOURNAL" | tr -d ' ')" "1"
check "F4  ⭐ … et le corps DIT que c'est un banc, avec son nom" \
      "$(grep -c 'ÉMIS PAR UN BANC (banc-des-essais)' "$BANC_JOURNAL" | tr -d ' ')" "1"

# ⭐⭐ F5 — L'ÉTIQUETTE, ET C'EST ELLE QUI RÉPARE LE `grep -c`. Un cri de
# banc portait `bw-model-score`, l'identifiant du job de production :
# impossible de compter les vrais sans lire chaque ligne.
: > "$BANC_JOURNAL"
CAT_ARGS="$TMP/cat-args.txt"; : > "$CAT_ARGS"
cat > "$FAUX/systemd-cat" <<'EOS'
#!/bin/sh
echo "$*" >> "$CAT_ARGS"
cat >> "$BANC_JOURNAL"
EOS
chmod +x "$FAUX/systemd-cat"; export CAT_ARGS
rm -rf "$TMP/etat-banc2"
BW_AVERTIR_CONFIG_BANC=1 \
  bw_avertir_config BW_BANC2_PING_URL /tmp/faux.env bw-model-score "CE JOB" "$TMP/etat-banc2"
check "F5  ⭐⭐ l'étiquette journald devient 'banc-bw-model-score' (le grep -c redevient honnête)" \
      "$(grep -c -- '-t banc-bw-model-score' "$CAT_ARGS" | tr -d ' ')" "1"

rm -rf "$TMP/etat-vrai"
: > "$CAT_ARGS"; : > "$BANC_MAILS"
bw_avertir_config BW_VRAI_PING_URL /tmp/faux.env bw-model-score "CE JOB" "$TMP/etat-vrai"
check "F6  ⛔ SANS le drapeau, rien ne change : l'étiquette reste celle du job…" \
      "$(grep -c -- '-t bw-model-score' "$CAT_ARGS" | tr -d ' ')" "1"
check "F7  ⛔ … et l'e-mail repart (le drapeau ne doit RIEN désarmer par défaut)" \
      "$(grep -c -- '--MAIL--' "$BANC_MAILS" | tr -d ' ')" "1"

# ⭐ F8 — LE BANC QUI A PRODUIT CE LOT : `test_run_selftest.py` doit
# poser le drapeau. Sans cette assertion, le correctif vit dans
# `bw_avertir_config` et personne ne l'appelle.
check "F8  ⭐ test_run_selftest.py DÉCLARE son bac dans l'environnement du run" \
      "$(grep -c '\"BW_AVERTIR_CONFIG_BANC\": ' model-verif/test_run_selftest.py | tr -d ' ')" "1"

# ══════════════════════════════════════════════════════════════════════
#  G. LE CANAL E-MAIL SURVIT AU DURCISSEMENT          (lot LE, 02/09/2026)
#
#  ⛔⛔ LA MUTATION QUE LE LOT DEMANDAIT N'EXISTE PAS, ET IL FAUT LE
#  DIRE ICI. Le lot LE prescrivait : « rendre le chemin de log NON
#  INSCRIPTIBLE et exiger que le banc rougisse ». MESURÉ le 02/09 contre
#  un puits SMTP local : un journal inécrivable N'EMPÊCHE PAS L'ENVOI.
#  msmtp livre d'abord, journalise ensuite, `EXIT=0`. La propriété
#  « le mail part » est donc VRAIE, et elle le reste sous durcissement —
#  la mutation prescrite n'aurait rien mordu, non par faiblesse du banc,
#  mais parce que la faute supposée n'était pas la faute.
#
#  ⭐ Contre-épreuve par l'effet, et c'est elle qui a tranché : les TROIS
#  avertissements émis le 01/09 à 17:40, 17:45 et 17:50 CEST par
#  `balise-infoclimat` — unité DURCIE — SONT ARRIVÉS dans la boîte, sans
#  laisser une ligne dans `~/.msmtp.log`.
#
#  ⇒ CE QUE CETTE SECTION TIENT EST DONC AUTRE CHOSE : non pas « le mail
#  part », mais **« SA TRACE SURVIT »**. Sous `logfile`, un job durci
#  envoie sans accusé : on ne peut plus distinguer un e-mail arrivé d'un
#  e-mail perdu. C'est cette distinction-là qu'on défend.
# ══════════════════════════════════════════════════════════════════════
echo
echo "▶ G. le canal e-mail et sa trace sous durcissement"

check "G1  l'exemple msmtprc est versionné et déclare des réglages" \
      "$(bw_inv_msmtp_exemple "$RACINE" | wc -l | tr -d ' ' | awk '$1>5{print "assez"} $1<=5{print "trop peu"}')" "assez"
check "G2  ⭐ il déclare 'syslog' — la trace va où va déjà tout le reste" \
      "$(bw_inv_msmtp_exemple "$RACINE" | grep -cx 'syslog' | tr -d ' ')" "1"
check "G3  ⛔ et PAS 'logfile' — sous ProtectHome il ne s'écrit pas, et l'accusé de livraison disparaît" \
      "$(bw_inv_msmtp_exemple "$RACINE" | grep -cx 'logfile' | tr -d ' ')" "0"
check "G4  ⛔ l'exemple ne porte AUCUNE valeur réelle (toute adresse est un <placeholder>)" \
      "$(grep -oE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+' "$RACINE/$BW_EXEMPLE_MSMTP" \
         | grep -vcE '(exemple\.invalid|@exemple)' | tr -d ' ')" "0"

# ⭐⭐ G5/G6/G7 — LE COMPARATEUR, JOUÉ SUR DES FIXTURES. C'est lui que le
# déploiement fera tourner contre le VRAI `~/.msmtprc` du VPS, et le
# piège de Q2 est nommé dans le lot : un exemple que rien ne relit
# périme. Le précédent annonçait 4 variables sur 15.
FIXT_M="$TMP/msmtp"; mkdir -p "$FIXT_M"
printf 'defaults\nauth on\ntls on\nsyslog on\naccount x\nhost h\nport 587\nuser u\npassword TRES-SECRET-42\nfrom f\naccount default : x\n' \
  > "$FIXT_M/reel-conforme"
cp "$FIXT_M/reel-conforme" "$FIXT_M/reel-divergent"
printf 'set_from_header on\n' >> "$FIXT_M/reel-divergent"

MANQUE_OK=$(comm -13 <(bw_inv_msmtp_exemple "$RACINE") <(bw_inv_msmtp_noms "$FIXT_M/reel-conforme") | tr '\n' ' ' | sed 's/ *$//')
MANQUE_KO=$(comm -13 <(bw_inv_msmtp_exemple "$RACINE") <(bw_inv_msmtp_noms "$FIXT_M/reel-divergent") | tr '\n' ' ' | sed 's/ *$//')
check "G5  ⭐⭐ un réglage présent chez le VRAI et absent de l'exemple est VU" "$MANQUE_KO" "set_from_header"
check "G6  ⓘ et deux fichiers d'accord ne rendent rien (pas de cri au loup)" "$MANQUE_OK" ""
# ⛔ G7 — LA RÈGLE DE SÉCURITÉ, TENUE PAR UN BANC ET PAS PAR UNE
# INTENTION. `~/.msmtprc` porte un mot de passe d'application ; toute la
# sonde du 02/09 a été faite sans en afficher une ligne. Si l'extraction
# rendait la ligne entière au lieu du premier mot, le secret remonterait
# dans le terminal du déploiement ET dans ses journaux.
check "G7  ⛔ l'extraction ne rend JAMAIS une valeur (le mot de passe ne remonte pas)" \
      "$(bw_inv_msmtp_noms "$FIXT_M/reel-conforme" | grep -c 'TRES-SECRET-42' | tr -d ' ')" "0"

# ⭐⭐ G8-G11 — LA COUVERTURE DU JOURNAL, LUE SUR LES UNITÉS RÉELLES DU
# DÉPÔT. C'est le cas qui a produit le lot : une unité durcie dont le
# `ReadWritePaths` ne couvre pas ce que son canal d'alerte doit écrire.
check "G8  ⛔⛔ le chemin historique (~/.msmtp.log) n'est couvert par AUCUNE unité durcie" \
      "$(bw_inv_journal_couvert "$RACINE" /home/debian/.msmtp.log && echo couvert || echo non)" "non"
# ⭐ G9 — ET C'EST LA DÉMONSTRATION QUE « UN CHEMIN PAR UNITÉ » NE
# TENAIT PAS : même le chemin des ONZE jobs model-verif échoue, parce
# que le poller et l'entretien ont d'autres ReadWritePaths. Les
# ensembles sont DISJOINTS : aucun chemin unique n'existe.
check "G9  ⭐ ni /var/lib/bw-model-verif — les ReadWritePaths sont disjoints" \
      "$(bw_inv_journal_couvert "$RACINE" /var/lib/bw-model-verif/msmtp.log && echo couvert || echo non)" "non"
check "G10 ⭐ seul le chemin VIDE passe : 'syslog on' n'écrit aucun fichier" \
      "$(bw_inv_journal_couvert "$RACINE" '' && echo couvert || echo non)" "couvert"
check "G11 ⓘ et il y a bien 13 unités durcies à vérifier (le périmètre n'a pas fondu)" \
      "$(bw_inv_unites_durcies "$RACINE" | wc -l | tr -d ' ')" "13"

# ⛔ G12 — UN CONTRÔLE QUI NE LIT RIEN NE DOIT PAS DIRE « OUI ». Sans
# cette assertion, le jour où la recherche d'unités casse, tout chemin
# deviendrait « couvert » et la propriété serait vraie GRATUITEMENT.
# C'est le piège nº 3 du lot LD, qui a déjà eu la section D de ce banc.
VIDE="$TMP/sans-unites"; mkdir -p "$VIDE"
check "G12 ⛔ une racine SANS unité rend 'non', pas 'oui' (un contrôle aveugle n'est pas vert)" \
      "$(bw_inv_journal_couvert "$VIDE" /var/lib/bw-model-verif/x && echo couvert || echo non)" "non"

# ⛔ G13 — LE `/` DE LA COMPARAISON DE PRÉFIXE. Sans lui,
# `/var/lib/bw-model-verif-bis` passerait pour couvert par
# `/var/lib/bw-model-verif`, et on autoriserait un journal dans un
# dossier voisin qui n'existe pas dans l'unité.
FIXU="$TMP/racine-u"; mkdir -p "$FIXU"
printf '[Service]\nProtectHome=read-only\nReadWritePaths=/var/lib/bw-model-verif\n' > "$FIXU/u.service"
check "G13 ⛔ un dossier VOISIN n'est pas couvert (/var/lib/bw-model-verif-bis)" \
      "$(bw_inv_journal_couvert "$FIXU" /var/lib/bw-model-verif-bis/m.log && echo couvert || echo non)" "non"
check "G14 ⓘ … alors que le dossier lui-même l'est (sinon G13 serait vrai pour rien)" \
      "$(bw_inv_journal_couvert "$FIXU" /var/lib/bw-model-verif/m.log && echo couvert || echo non)" "couvert"

# ⭐ G15 — LE CONTRÔLE EXISTE ET IL EST APPELÉ. Un contrôle défini mais
# jamais appelé est la faute du lot LV vue une fois déjà (`alerter`
# était dans le fichier, dix lignes plus haut, et personne ne
# l'appelait).
check "G15 ⭐ le déploiement DÉFINIT et APPELLE bw_controle_config_msmtp" \
      "$(grep -c 'bw_controle_config_msmtp' tools/deploy-agrume-vps.sh | tr -d ' ' | awk '$1>=3{print "oui"} $1<3{print "non"}')" "oui"

# ══════════════════════════════════════════════════════════════════════
echo
if [ "$ROUGES" -eq 0 ]; then
  echo "  ✓ $VERTS assertions vertes, 0 rouge — les canaux d'alerte tiennent"
  exit 0
fi
echo "  ❌ $ROUGES assertion(s) rouge(s) sur $((VERTS+ROUGES))"
exit 1
