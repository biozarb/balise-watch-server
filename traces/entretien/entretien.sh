#!/bin/bash
# ══════════════════════════════════════════════════════════════════════
#  entretien.sh — enveloppe du run quotidien de backfill_packs.py
#  (02/08/2026 · porté Linux le 03/08/2026)
#  Lancé par cron/systemd (VPS) ou launchd (Mac), jamais à la main.
#
#  Ce que cette enveloppe apporte, et que le script Python ne fait pas :
#    · charge ~/.balise-watch-r2.env (les `export` ne survivent pas au
#      terminal — c'est la raison d'être du fichier) ;
#    · un verrou : deux runs simultanés doubleraient les écritures R2 ;
#    · un chien de garde : un run qui dépasse MAX_MINUTES est tué. Sans
#      ça, une plage bloquée peut tenir la machine jusqu'au run suivant ;
#    · un journal permanent, ROTATÉ (un log qui grossit sans fin finit
#      par être le problème qu'il devait aider à résoudre) ;
#    · le compte d'échecs CONSÉCUTIFS, et une alerte au deuxième.
#
#  ⚠️ PORTABILITÉ — la raison de la réécriture du 03/08.
#  La version du 02/08 était écrite pour macOS et se cassait en silence
#  sous Linux, sur trois points :
#    · `stat -f %m`  → syntaxe BSD. Sous GNU, `-f` signifie
#      --file-system : le calcul d'âge du verrou partait en vrille et
#      la protection anti-run-simultané ne tenait plus.
#    · `stat -f %Lp` → idem pour le contrôle des permissions du .env.
#    · `osascript`   → inexistant sous Linux, et le `|| true` avalait
#      l'échec : AUCUNE alerte ne partait jamais.
#  Les helpers `mtime()` / `perms_de()` essaient GNU puis retombent sur
#  BSD : ce script reste utilisable sur le Mac de Yann.
#
#  ⚠️ CE QUE CETTE ENVELOPPE NE PEUT PAS DÉTECTER SEULE : sa propre
#  absence. Si le déclencheur cesse d'appeler ce script, aucune ligne
#  ici ne s'exécutera pour le dire. D'où BW_PING_OK_URL (interrupteur
#  d'homme mort) : un service extérieur attend un signal quotidien et
#  alerte quand il ne vient plus. C'est le SEUL canal qui ne dépend pas
#  du mécanisme qu'il surveille. Le second témoin, gratuit, reste le
#  client pilote : chaque pack porte `genere_le` et sa dernière date.
#
#  ⚠️ JAMAIS DEPUIS L'IP DE RENDER. Le quota Open-Meteo se compte par
#  IP, et celle de Render porte déjà la veille et le foehn en prod.
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRACES="$(cd "$ICI/.." && pwd)"
ENV_FILE="${BW_ENV_FILE:-$HOME/.balise-watch-r2.env}"
ETAT="$HOME/.balise-watch-entretien"
LOG="$ETAT/entretien.log"
ECHECS="$ETAT/echecs_consecutifs"
DERNIER_OK="$ETAT/dernier_succes"
VERROU="$ETAT/verrou"
MAX_MINUTES="${BW_MAX_MINUTES:-180}"
MAX_LOG_MO=10

mkdir -p "$ETAT"

dire() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$LOG"; }

# ── Configuration des alertes, chargée EN PREMIER ────────────────────
# ⚠️ Elle vit dans SON PROPRE fichier, et pas dans .balise-watch-r2.env,
#    pour une raison précise (défaut trouvé le 03/08) : le premier
#    échec possible du script est « fichier .balise-watch-r2.env
#    absent ». Si les canaux d'alerte étaient configurés dedans, cette
#    alerte-là — la seule qui dise « je ne peux pas travailler du tout »
#    — partirait dans le vide. Un dispositif d'alerte ne doit pas
#    dépendre de ce qu'il surveille.
#    Second effet utile : ce fichier ne contient aucun identifiant R2,
#    il n'a donc pas la même sensibilité et peut être copié seul.
ALERTES_FILE="${BW_ALERTES_FILE:-$HOME/.balise-watch-alertes.env}"
if [[ -f "$ALERTES_FILE" ]]; then
  # shellcheck source=/dev/null
  source "$ALERTES_FILE"
fi

# ── Portabilité GNU / BSD ─────────────────────────────────────────────
# GNU d'abord (le VPS est la cible principale), BSD en repli (le Mac).
mtime()    { stat -c %Y "$1" 2>/dev/null || stat -f %m  "$1" 2>/dev/null || echo 0; }
perms_de() { stat -c %a "$1" 2>/dev/null || stat -f %Lp "$1" 2>/dev/null || echo ""; }

# ── Alerte, quatre canaux, tous optionnels ────────────────────────────
# Chaque canal ne s'active que si sa variable est définie dans le .env.
# Aucun canal ne doit pouvoir faire échouer le script : une alerte qui
# casse le run qu'elle surveille est pire que pas d'alerte du tout.
# Un seul essai, court, jamais de boucle de réessai — même discipline
# que les écritures R2 du worker de packs.
alerter() {   # $1 = titre, $2 = message
  local titre="$1" msg="$2"
  dire "ALERTE — $titre : $msg"

  # 1. Notification locale macOS (silencieusement ignorée sous Linux).
  if command -v osascript >/dev/null 2>&1; then
    osascript -e "display notification \"$msg\" with title \"Balise Watch — $titre\"" 2>/dev/null || true
  fi

  # 2. journald — trace système consultable via `journalctl -t balise-entretien`.
  if command -v systemd-cat >/dev/null 2>&1; then
    printf '%s : %s\n' "$titre" "$msg" | systemd-cat -t balise-entretien -p err 2>/dev/null || true
  fi

  # 3. Signal d'ÉCHEC vers l'interrupteur d'homme mort.
  #    C'est le canal à privilégier, pour une raison d'architecture :
  #    Healthchecks alerte depuis l'EXTÉRIEUR, par tous les moyens qu'on
  #    lui a configurés. Un push émis par le VPS lui-même ne peut parler
  #    que si le VPS va assez bien pour parler — or les pannes qui
  #    comptent (machine éteinte, timer mort, facture impayée) sont
  #    justement celles où il se taira. Une seule intégration couvre
  #    donc les deux cas : « le run a échoué » ET « le run n'a pas eu
  #    lieu ».
  if [[ -n "${BW_PING_OK_URL:-}" ]]; then
    curl -fsS --max-time 10 --data-binary "$msg" \
         "${BW_PING_OK_URL}/fail" >/dev/null 2>&1 \
      || dire "⚠️ ping d'échec non parti"
  fi

  # 4. Webhook push direct, optionnel et redondant avec le précédent
  #    (ntfy, Discord, Slack…). Topic LONG et non devinable : un topic
  #    ntfy public est lisible par qui en connaît le nom.
  #    ⚠️ Le titre part dans un EN-TÊTE HTTP, qui ne transporte pas
  #       d'UTF-8 : on le translittère en ASCII, sinon un simple « é »
  #       fait rejeter la requête. Le corps, lui, reste en UTF-8.
  if [[ -n "${BW_WEBHOOK_URL:-}" ]]; then
    titre_h=$(printf '%s' "Balise Watch - $titre" \
      | { iconv -f UTF-8 -t ASCII//TRANSLIT 2>/dev/null || cat; } \
      | LC_ALL=C tr -cd '\40-\176')
    [[ -z "$titre_h" ]] && titre_h="Balise Watch"
    http=$(curl -fsS --max-time 10 -o /dev/null -w '%{http_code}' \
         -H "Title: $titre_h" -H "Priority: high" \
         -d "$msg" "$BW_WEBHOOK_URL" 2>/dev/null) \
      || dire "⚠️ webhook injoignable (HTTP ${http:-?}) — 429 = quota du service, pas un bug d'ici"
  fi

  # 4. E-mail via msmtp. Seul canal qui pose un vrai secret sur la
  #    machine (mot de passe d'application) : d'où son caractère
  #    facultatif. Config attendue dans ~/.msmtprc, chmod 600.
  if [[ -n "${BW_ALERTE_MAIL:-}" ]] && command -v msmtp >/dev/null 2>&1; then
    printf 'To: %s\nSubject: [Balise Watch] %s\nContent-Type: text/plain; charset=UTF-8\n\n%s\n\nMachine : %s\nJournal : %s\n' \
      "$BW_ALERTE_MAIL" "$titre" "$msg" "$(hostname)" "$LOG" \
      | msmtp --read-recipients >/dev/null 2>&1 \
      || dire "⚠️ e-mail non parti — voir ~/.msmtp.log"
  fi
}

# ── Rotation du journal ───────────────────────────────────────────────
if [[ -f "$LOG" ]]; then
  taille=$(( $(wc -c < "$LOG") / 1048576 ))
  if (( taille >= MAX_LOG_MO )); then
    mv "$LOG" "$LOG.1"
    dire "journal rotaté (${taille} Mo) → $(basename "$LOG").1"
  fi
fi

# ── Verrou ────────────────────────────────────────────────────────────
if ! mkdir "$VERROU" 2>/dev/null; then
  age=$(( $(date +%s) - $(mtime "$VERROU") ))
  if (( age > MAX_MINUTES * 60 )); then
    dire "verrou périmé (${age}s) — retiré"
    rmdir "$VERROU" 2>/dev/null && mkdir "$VERROU"
  else
    dire "un run est déjà en cours (verrou de ${age}s) — abandon"
    exit 0
  fi
fi
trap 'rmdir "$VERROU" 2>/dev/null' EXIT

# ── Environnement ─────────────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
  alerter "entretien" "fichier $ENV_FILE absent — voir balise-watch-r2.env.exemple"
  exit 1
fi
perms=$(perms_de "$ENV_FILE")
if [[ -n "$perms" && "$perms" != "600" ]]; then
  dire "⚠️ $ENV_FILE est en $perms — attendu 600. Correction."
  chmod 600 "$ENV_FILE"
fi
# shellcheck source=/dev/null
source "$ENV_FILE"

# Le venv du VPS n'est pas dans le PATH de cron : BW_PYTHON est la voie
# normale de le désigner (ex. $HOME/venv-balise/bin/python3).
PYTHON="${BW_PYTHON:-$(command -v python3)}"
if [[ -z "$PYTHON" || ! -x "$PYTHON" ]]; then
  alerter "entretien" "python3 introuvable ($PYTHON) — définir BW_PYTHON dans $ENV_FILE"
  exit 1
fi

# ── Run, sous chien de garde ──────────────────────────────────────────
dire "── run entretien · $PYTHON · deadline ${MAX_MINUTES} min ──"
cd "$TRACES" || exit 1

"$PYTHON" backfill_packs.py --mode entretien --go >>"$LOG" 2>&1 &
pid=$!
( sleep $(( MAX_MINUTES * 60 )); kill -TERM "$pid" 2>/dev/null ) &
chien=$!
wait "$pid"; code=$?
kill "$chien" 2>/dev/null

# ── Suite ─────────────────────────────────────────────────────────────
if (( code == 0 )); then
  date -u +%Y-%m-%dT%H:%M:%SZ > "$DERNIER_OK"
  echo 0 > "$ECHECS"
  dire "✅ run terminé (code 0)"
  # Interrupteur d'homme mort : ce ping n'est PAS une alerte, c'est un
  # signe de vie. Le service extérieur alerte quand il CESSE d'arriver
  # — seul moyen de détecter un déclencheur mort.
  if [[ -n "${BW_PING_OK_URL:-}" ]]; then
    curl -fsS --max-time 10 "$BW_PING_OK_URL" >/dev/null 2>&1 \
      || dire "⚠️ ping de vie non parti (le run, lui, est bon)"
  fi
  exit 0
fi

n=$(( $(cat "$ECHECS" 2>/dev/null || echo 0) + 1 ))
echo "$n" > "$ECHECS"
# code 2 = Abort (plafond atteint ou invariant violé) : c'est le worker
# qui refuse d'écrire, pas une panne. On le distingue dans le message,
# parce que la conduite à tenir n'est pas la même.
motif=$([[ $code -eq 2 ]] && echo "ABORT (plafond ou invariant — voir le log)" || echo "code $code")
dire "❌ échec — $motif · $n échec(s) consécutif(s)"

if (( n >= 2 )); then
  alerter "entretien en échec" "$n jours de suite ($motif). Les packs n'avancent plus."
fi
exit "$code"
