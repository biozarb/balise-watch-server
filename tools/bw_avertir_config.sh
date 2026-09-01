# ══════════════════════════════════════════════════════════════════════
#  bw_avertir_config.sh — l'avertissement de CONFIGURATION sort du
#  journal.  Lot LV, 01/09/2026.  ⛔ FICHIER SOURCÉ, JAMAIS EXÉCUTÉ.
#
#  ⛔⛔ POURQUOI CE FICHIER EXISTE. Cinq runners portaient déjà le
#  garde-fou « PERSONNE NE SURVEILLE CE JOB ». Mesuré le 01/09 sur les
#  29 jours de journal du VPS : 315 cris, sept variables.
#  `BW_AGRUME_CONFRONTATION_PING_URL` a crié 20 JOURS D'AFFILÉE — dès la
#  PREMIÈRE passe, 8 secondes après l'installation de son unité — et le
#  job a continué de tourner comme si de rien n'était.
#
#  ⭐ Et le diagnostic n'est pas « il manque une oreille ». Sur les sept
#  variables, CINQ ont été réparées, quatre le jour même, et aucune
#  réparation n'est tracée nulle part. L'oreille EXISTE — c'est un
#  humain qui travaillait ce jour-là sur cette chaîne-là. Quand personne
#  ne travaillait dessus, le cri est parti vingt jours dans le vide.
#  Ce n'était donc pas un canal manquant : c'était un canal dont la
#  fiabilité était celle de l'attention d'une personne.
#
#  ⛔ LA CAUSE MÉCANIQUE ÉTAIT À UNE LIGNE. L'avertissement passait par
#  `dire` (→ stdout → journal) et JAMAIS par `alerter` (→ e-mail,
#  webhook, journald `-p err`). La fonction qui sait parler DEHORS était
#  dans le même fichier, dix lignes plus haut. Elle n'était pas appelée.
#  Et rien, sur cette machine, ne lit le journal — vérifié le 01/09 :
#  0 paquet logcheck/logwatch, aucune crontab, `OnFailure=` déclaré sur
#  0 des 31 unités installées.
#
#  ⚠️ TROIS DES CINQ RUNNERS N'AVAIENT PAS D'`alerter` DU TOUT.
#  `run-ingest-pi.sh`, `run-ingest-piaf.sh` et `run-confronter-quotidien.sh`
#  n'ont qu'un `pinguer`, qui ne fait RIEN quand l'URL manque — or l'URL
#  qui manque est précisément le sujet de l'avertissement. Recopier un
#  `alerter` dans chacun, c'était s'engager à corriger trois fois chaque
#  bug suivant (la règle écrite en tête de `model-verif/run.sh`). D'où
#  ce fichier, sourcé par les cinq.
#
#  ⛔ CE QU'IL N'ENVOIE PAS, ET C'EST DÉLIBÉRÉ : aucun ping Healthchecks.
#  Le check de ce job est justement celui dont l'URL manque. Et
#  réutiliser `BW_PING_OK_URL` (celui de l'entretien) ferait passer au
#  rouge le check d'un AUTRE job — la règle « deux jobs, deux checks »
#  posée en tête de `balise-infoclimat.service`. Restent trois canaux
#  qui, eux, ne dépendent pas de la variable absente :
#    journald `-p err` · webhook ntfy · e-mail msmtp.
#
#  ⚠️ UN CRI PAR VARIABLE ET PAR JOUR, PAS PLUS. Sans ce jeton, la
#  confrontation aurait envoyé 20 e-mails et le poller 283 — et un
#  dispositif d'alerte qu'on apprend à ignorer ne sert plus (c'est
#  l'arbitrage du banc du voyant piaf, « six passes perdues ne font pas
#  une panne », appliqué à la configuration).
#  ⛔ MAIS IL ÉCHOUE OUVERT : si le jeton ne peut pas s'écrire, on
#  avertit QUAND MÊME, chaque fois. Un dispositif d'alerte ne doit pas
#  se taire parce que son propre état est cassé — c'est la faute qu'on
#  répare ici, à un étage de plus.
# ══════════════════════════════════════════════════════════════════════

# ⚠️ Sous `set -u`, un `${1:-}` protège de l'appel mal formé : ce fichier
# est chargé par des scripts qui tournent en production la nuit.
bw_avertir_config() {
  bw_ac_var="${1:-}"; bw_ac_fichier="${2:-}"
  bw_ac_etiq="${3:-balise-watch}"; bw_ac_quoi="${4:-CE JOB}"
  # $5 = LE DOSSIER D'ÉTAT DU JOB APPELANT. ⛔⛔ AJOUTÉ LE 01/09 À 17:45,
  # UNE HEURE APRÈS LE DÉPLOIEMENT, PARCE QUE LA PRODUCTION L'A DIT.
  # Le premier vrai passage du poller a fait partir le push — le chien a
  # bien aboyé — mais NI l'e-mail NI le jeton ne se sont écrits. Cause :
  # `balise-infoclimat.service` porte `ProtectHome=read-only` et
  # `ReadWritePaths=/home/debian/.balise-watch-infoclimat`. Le défaut
  # `$HOME/.balise-watch-etat-alertes` n'est PAS inscriptible pour lui.
  # ⇒ Sans jeton, le repli « échouer ouvert » s'appliquait : un push
  #   toutes les 5 minutes, soit 288 par jour. Un dispositif d'alerte
  #   qu'on apprend à ignorer ne sert plus — c'est la faute même que ce
  #   lot répare, retournée contre lui en une heure.
  # ⚠️ Chaque runner passe donc SON dossier d'état, celui que son unité
  # systemd déclare déjà en `ReadWritePaths`. Le défaut ne sert plus qu'aux
  # runners sans durcissement (les trois d'agrume/ et verif/).
  bw_ac_dir="${5:-${BW_ETAT_ALERTES:-$HOME/.balise-watch-etat-alertes}}"
  [ -n "$bw_ac_var" ] || return 0

  bw_ac_sujet="configuration incomplete : $bw_ac_var absente"
  bw_ac_corps="⚠️ $bw_ac_var est absente de $bw_ac_fichier — PERSONNE NE SURVEILLE $bw_ac_quoi.
Le job continue de tourner : il n'échoue pas, il est INVISIBLE. Un job qui
pingue dans le vide a exactement l'allure d'un job surveillé.
Geste : créer le check chez le service extérieur, puis ajouter la ligne
        export $bw_ac_var=\"…\"  dans $bw_ac_fichier
Machine : $(hostname 2>/dev/null || echo '?')
ⓘ Cet avertissement ne repart qu'une fois par jour et par variable."

  # ── Le jeton : une fois par jour et par variable ────────────────────
  bw_ac_jour="$(date -u +%Y-%m-%d)"
  bw_ac_jeton="$bw_ac_dir/cri.$bw_ac_var"
  if [ -r "$bw_ac_jeton" ] \
     && [ "$(cat "$bw_ac_jeton" 2>/dev/null)" = "$bw_ac_jour" ]; then
    return 0
  fi

  # ── 1. journald, en ERREUR — pas en info ────────────────────────────
  # Même destination qu'avant, mais à une sévérité qui se filtre :
  # `journalctl -p err` ne rend plus 315 lignes noyées dans 2 000.
  if command -v systemd-cat >/dev/null 2>&1; then
    printf '%s : %s\n' "$bw_ac_sujet" "$bw_ac_corps" \
      | systemd-cat -t "$bw_ac_etiq" -p err 2>/dev/null || true
  fi

  # ── 2. Webhook push (ntfy) ──────────────────────────────────────────
  # ⚠️ Le titre part dans un EN-TÊTE HTTP, qui ne transporte pas d'UTF-8
  # (défaut du 03/08) : `$bw_ac_sujet` est écrit en ASCII pur plus haut,
  # exprès, et non translittéré ici.
  if [ -n "${BW_WEBHOOK_URL:-}" ]; then
    curl -fsS --max-time 10 -o /dev/null \
         -H "Title: Balise Watch - $bw_ac_sujet" -H "Priority: default" \
         -d "$bw_ac_corps" "$BW_WEBHOOK_URL" >/dev/null 2>&1 || true
  fi

  # ── 3. E-mail via msmtp ─────────────────────────────────────────────
  if [ -n "${BW_ALERTE_MAIL:-}" ] && command -v msmtp >/dev/null 2>&1; then
    printf 'To: %s\nSubject: [Balise Watch] %s\nContent-Type: text/plain; charset=UTF-8\n\n%s\n' \
      "$BW_ALERTE_MAIL" "$bw_ac_sujet" "$bw_ac_corps" \
      | msmtp --read-recipients >/dev/null 2>&1 || true
  fi

  # ── Le jeton s'écrit EN DERNIER ─────────────────────────────────────
  # S'il s'écrivait en premier, un échec des trois canaux serait tu
  # jusqu'au lendemain. Et s'il ne s'écrit pas du tout, on recriera
  # demain : bruyant, jamais muet.
  mkdir -p "$bw_ac_dir" 2>/dev/null || return 0
  printf '%s\n' "$bw_ac_jour" > "$bw_ac_jeton" 2>/dev/null || true
  return 0
}
