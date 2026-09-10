# ══════════════════════════════════════════════════════════════════════
#  bw_jira.sh — LE CANAL JIRA : la DÉRIVE, qui se lit à tête reposée.
#  Lot REGISTRE ET PENTE, 10/09/2026.  ⛔ FICHIER SOURCÉ, JAMAIS EXÉCUTÉ.
#
#  ⛔ PARTAGE DES CANAUX, ET IL N'EST PAS NÉGOCIABLE :
#    · Jira    → la dérive : pentes, dates de franchissement, ce qui
#                mérite une trace qui S'ACCUMULE (un ticket, ses
#                commentaires nuit après nuit) et se lit le matin.
#    · mail +  → les ⛔ : nuit morte, code 124, OOM. Un ticket ne réveille
#      push      personne ; ces deux-là restent à `alerter()` (run.sh) et
#                `bw_avertir_config`.
#
#  ⛔ DÉDUPLICATION PAR LABEL : UN TICKET PAR MOTIF, PAS UN PAR MATIN.
#  `bw-pente-duree`, `bw-pente-memoire`, `bw-purge-57014` : on CHERCHE
#  d'abord (`jql = project = KAN AND labels = <motif> AND statusCategory
#  != Done`), on COMMENTE si un ticket est ouvert, on CRÉE sinon. Sans
#  ça, 300 tickets par an, et le projet devient un flux que personne
#  n'ouvre — c'est le sort du journal du VPS avant le lot LV.
#  ⓘ « Mise en prod » (10004) est en catégorie `new`, pas `done` : un
#  ticket reste ouvert tant qu'il attend son déploiement. C'est la
#  bonne sémantique, et c'est pour ça que le test est `statusCategory`
#  et pas un nom de statut.
#
#  ⚠️ ET UN COMMENTAIRE PAR JOUR ET PAR MOTIF, PAS PLUS. Le jeton
#  `cri.jira.<motif>` de `bw_avertir_config.sh`, même patron, ÉCRIT EN
#  DERNIER : si le canal échoue, on recrie demain — bruyant, jamais muet.
#
#  ⛔ AUTH BASIC PAR `curl -K -` SUR L'ENTRÉE STANDARD, JAMAIS `-u`. Un
#  `-u mail:jeton` s'affiche dans `ps` et dans le journal de tout
#  wrapper qui trace ses commandes. Le jeton (192 caractères) ne passe
#  ici QUE par un tube, encodé en base64 avec le mail.
#
#  ⚠️ NE SURCHARGE PAS `BW_WEBHOOK_URL` : il est taillé pour ntfy (titre
#  dans un EN-TÊTE HTTP, corps en texte brut — défaut UTF-8 du 03/08).
#  Jira veut du JSON, en ADF. Deux canaux, deux fonctions.
#
#  Variables (dans ~/.balise-watch-alertes.env, sourcé par les runners) :
#    BW_JIRA_URL     https://balisewatch.atlassian.net
#    BW_JIRA_MAIL    le compte Atlassian
#    BW_JIRA_TOKEN   le jeton d'API (192 car.)
#    BW_JIRA_PROJET  KAN (défaut)
#    BW_JIRA_TYPE    Bug (défaut)
#
#  Usage (sourcé) :
#    . tools/bw_jira.sh
#    bw_jira_signaler bw-pente-duree "durée 3 860 s …" "corps…" "$ETAT"
#  Rend TOUJOURS 0 (un canal ne tue pas un runner). Dit ce qu'il fait
#  sur stdout, ce qui manque sur stderr. `BW_JIRA_DERNIER` porte la clé
#  du ticket touché (KAN-12) pour l'appelant.
# ══════════════════════════════════════════════════════════════════════

BW_JIRA_LABEL_SURVEILLANCE="bw-surveillance"
BW_JIRA_DERNIER=""

# ── Une chaîne → un littéral JSON (sans les guillemets) ──────────────
# ⚠️ Pas de python ici : ce fichier doit vivre dans un runner shell nu.
bw_jira_chaine() {
  printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/\t/\\t/g' \
    | awk 'NR>1{printf "\\n"} {printf "%s", $0}'
}

# ── Un texte → un document ADF (un paragraphe par ligne) ─────────────
bw_jira_adf() {
  local ligne premier=1
  printf '{"type":"doc","version":1,"content":['
  while IFS= read -r ligne || [ -n "$ligne" ]; do
    [ "$premier" = 1 ] || printf ','
    premier=0
    if [ -z "$ligne" ]; then
      printf '{"type":"paragraph","content":[]}'
    else
      printf '{"type":"paragraph","content":[{"type":"text","text":"%s"}]}' \
        "$(bw_jira_chaine "$ligne")"
    fi
  done <<EOF
$1
EOF
  printf ']}'
}

# ── L'appel HTTP : la config de curl arrive par l'ENTRÉE STANDARD ────
# $1 méthode · $2 chemin (/rest/…) · $3 corps JSON (vide = GET) ·
# $4 fichier de sortie (le corps de la réponse) · sortie : le code HTTP.
bw_jira_http() {
  local methode="$1" chemin="$2" corps="${3:-}" sortie="$4" auth
  auth=$(printf '%s:%s' "$BW_JIRA_MAIL" "$BW_JIRA_TOKEN" | base64 | tr -d '\n')
  {
    printf 'url = "%s%s"\n' "$BW_JIRA_URL" "$chemin"
    printf 'header = "Authorization: Basic %s"\n' "$auth"
    printf 'header = "Accept: application/json"\n'
    printf 'header = "Content-Type: application/json"\n'
    printf 'request = "%s"\n' "$methode"
    printf 'silent\nshow-error\nmax-time = 20\n'
    printf 'output = "%s"\n' "$sortie"
    printf 'write-out = "%%{http_code}"\n'
    if [ -n "$corps" ]; then
      printf 'data-binary = "@%s"\n' "$sortie.req"
    fi
  } > "$sortie.cfg"
  [ -n "$corps" ] && printf '%s' "$corps" > "$sortie.req"
  # ⛔ `-K -` : la config (donc le jeton encodé) part par le tube. Rien
  # de tout cela n'apparaît dans `ps`. Le fichier .cfg vit dans un
  # dossier 700 et est effacé juste après.
  local code
  code=$(curl -K - < "$sortie.cfg" 2>/dev/null) || code="000"
  rm -f "$sortie.cfg" "$sortie.req"
  printf '%s' "${code:-000}"
}

# ── La clé d'un ticket OUVERT portant ce motif, ou rien ──────────────
bw_jira_chercher() {   # $1 motif · $2 dossier de travail
  local motif="$1" trav="$2" jql code
  jql="project = ${BW_JIRA_PROJET:-KAN} AND labels = \"$motif\" AND statusCategory != Done ORDER BY created DESC"
  # ⚠️ `/search/jql` (2025), plus `/search` : l'ancien point d'entrée
  # est déprécié et refuse les nouveaux sites.
  code=$(bw_jira_http POST "/rest/api/3/search/jql" \
    "{\"jql\":\"$(bw_jira_chaine "$jql")\",\"maxResults\":1,\"fields\":[\"key\"]}" \
    "$trav/cherche.json")
  if [ "$code" != "200" ]; then
    printf 'HTTP %s\n' "$code" >&2
    return 1
  fi
  sed -n 's/.*"key"[[:space:]]*:[[:space:]]*"\([A-Z][A-Z0-9]*-[0-9]*\)".*/\1/p' \
    "$trav/cherche.json" | head -1
}

# ── Signaler : commenter le ticket ouvert du motif, ou le créer ──────
# $1 motif (label de dédup.) · $2 sujet · $3 corps · $4 dossier d'état
# (jeton du jour) — le même que celui passé à bw_avertir_config.
bw_jira_signaler() {
  local motif="${1:-}" sujet="${2:-}" corps="${3:-}"
  local etat="${4:-${BW_ETAT_ALERTES:-$HOME/.balise-watch-etat-alertes}}"
  BW_JIRA_DERNIER=""
  [ -n "$motif" ] || return 0

  # ── Sans configuration, on le DIT, et on rend 0 ─────────────────
  local manque="" v
  for v in BW_JIRA_URL BW_JIRA_MAIL BW_JIRA_TOKEN; do
    eval "[ -n \"\${$v:-}\" ]" || manque="$manque $v"
  done
  if [ -n "$manque" ]; then
    printf '⚠️ canal Jira non configuré (%s absente) — « %s » reste dans le journal\n' \
      "${manque# }" "$sujet" >&2
    return 0
  fi

  # ── Un commentaire par jour et par motif ────────────────────────
  local jour jeton
  jour="$(date -u +%Y-%m-%d)"
  jeton="$etat/cri.jira.$motif"
  if [ -r "$jeton" ] && [ "$(cat "$jeton" 2>/dev/null)" = "$jour" ]; then
    printf 'ⓘ Jira : « %s » déjà signalé aujourd'"'"'hui (%s)\n' "$motif" "$jour"
    return 0
  fi

  local trav
  trav=$(mktemp -d "${TMPDIR:-/tmp}/bw-jira.XXXXXX") || return 0
  chmod 700 "$trav"

  local cle code corps_complet
  corps_complet="$corps

Machine : $(hostname 2>/dev/null || echo '?') · $(date -u +%Y-%m-%dT%H:%MZ)
ⓘ Signalé par bw_jira.sh (motif $motif) — un ticket par motif, un commentaire par jour."

  cle=$(bw_jira_chercher "$motif" "$trav") || cle=""
  if [ -n "$cle" ]; then
    code=$(bw_jira_http POST "/rest/api/3/issue/$cle/comment" \
      "{\"body\":$(bw_jira_adf "$sujet
$corps_complet")}" "$trav/comment.json")
    if [ "$code" = "201" ]; then
      printf 'Jira : commentaire ajouté à %s (%s)\n' "$cle" "$motif"
      BW_JIRA_DERNIER="$cle"
    else
      printf '⚠️ Jira : commentaire sur %s refusé (HTTP %s)\n' "$cle" "$code" >&2
    fi
  else
    code=$(bw_jira_http POST "/rest/api/3/issue" \
      "{\"fields\":{\"project\":{\"key\":\"${BW_JIRA_PROJET:-KAN}\"},\"issuetype\":{\"name\":\"${BW_JIRA_TYPE:-Bug}\"},\"summary\":\"$(bw_jira_chaine "$sujet")\",\"labels\":[\"$BW_JIRA_LABEL_SURVEILLANCE\",\"$motif\"],\"description\":$(bw_jira_adf "$corps_complet")}}" \
      "$trav/create.json")
    if [ "$code" = "201" ]; then
      cle=$(sed -n 's/.*"key"[[:space:]]*:[[:space:]]*"\([A-Z][A-Z0-9]*-[0-9]*\)".*/\1/p' \
        "$trav/create.json" | head -1)
      printf 'Jira : ticket créé %s (%s)\n' "${cle:-?}" "$motif"
      BW_JIRA_DERNIER="$cle"
    else
      printf '⚠️ Jira : création refusée (HTTP %s) — %s\n' "$code" \
        "$(head -c 200 "$trav/create.json" 2>/dev/null)" >&2
    fi
  fi
  rm -rf "$trav"

  # ── Le jeton s'écrit EN DERNIER, et seulement si quelque chose est
  #    parti : un canal cassé recrie demain, il ne se tait pas. ────────
  if [ -n "$BW_JIRA_DERNIER" ]; then
    mkdir -p "$etat" 2>/dev/null || return 0
    printf '%s\n' "$jour" > "$jeton" 2>/dev/null || true
  fi
  return 0
}
