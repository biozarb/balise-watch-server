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

check "A1  les 11 modes de run.sh sont énumérés" \
      "$(bw_inv_modes "$RACINE" | wc -l | tr -d ' ')" "11"
check "A2  ⭐ les 11 noms CONSTRUITS sont reconstitués" \
      "$(bw_inv_construites "$RACINE" | wc -l | tr -d ' ')" "11"
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

check "A6  19 variables de canal lues au total" \
      "$(bw_inv_lues "$RACINE" | wc -l | tr -d ' ')" "19"
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
check "E2  ⓘ et il y en a bien 35 à vérifier (le périmètre n'a pas fondu)" \
      "$(find . -name '*.service' -o -name '*.timer' | grep -v node_modules | grep -v _to_delete | wc -l | tr -d ' ')" "35"
fi

# ══════════════════════════════════════════════════════════════════════
echo
if [ "$ROUGES" -eq 0 ]; then
  echo "  ✓ $VERTS assertions vertes, 0 rouge — les canaux d'alerte tiennent"
  exit 0
fi
echo "  ❌ $ROUGES assertion(s) rouge(s) sur $((VERTS+ROUGES))"
exit 1
