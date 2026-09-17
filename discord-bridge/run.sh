#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  run.sh — lanceur du pont Discord → Jira               (09/09/2026)
#
#  Calqué sur model-verif/run.sh : les secrets ne sont PAS dans l'unité
#  systemd (elle est versionnée, eux non). Ils vivent dans un fichier en
#  600 dans le home, chargé ici. Si une variable manque, on sort en 78
#  (EX_CONFIG) — et l'unité a RestartPreventExitStatus=78, donc systemd
#  n'insiste pas : une clé absente ne se répare pas toute seule, autant
#  que ça se voie dans le journal plutôt que de tourner en rafale.
#
#  Usage :  ./run.sh              # lance le pont (c'est ce que fait systemd)
#           ./run.sh --controle   # vérifie la config et les accès, puis sort
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FIC="${BW_DISCORD_ENV:-$HOME/.balise-watch-discord.env}"
VENV="${BW_DISCORD_VENV:-$HOME/venv-discord}"

echec() { printf '❌ %s\n' "$*" >&2; exit 78; }

[ -r "$ENV_FIC" ] || echec "secrets illisibles : $ENV_FIC (attendu en 600)"

# ⚠️ Permissions : un token Discord lisible par tout le monde sur la
# machine, c'est le serveur entier qui change de main.
perms=$(stat -c '%a' "$ENV_FIC" 2>/dev/null || echo "???")
[ "$perms" = "600" ] || printf '⚠️  %s est en %s, attendu 600\n' "$ENV_FIC" "$perms" >&2

set -a
# shellcheck source=/dev/null
. "$ENV_FIC"
set +a

for v in BW_DISCORD_TOKEN BW_JIRA_EMAIL BW_JIRA_TOKEN; do
  [ -n "${!v:-}" ] || echec "variable manquante dans $ENV_FIC : $v"
done

[ -x "$VENV/bin/python" ] || echec "venv absent : $VENV (voir README.md)"

if [ "${1:-}" = "--controle" ]; then
  printf '▶ Contrôle de la configuration\n'
  printf '  env          : %s (%s)\n' "$ENV_FIC" "$perms"
  printf '  venv         : %s\n' "$VENV"
  printf '  site Jira    : %s\n' "${BW_JIRA_SITE:-https://balisewatch.atlassian.net}"
  printf '  projet Jira  : %s\n' "${BW_JIRA_PROJET:-KAN}"
  printf '  état         : %s\n' "${BW_ETAT_DIR:-/var/lib/bw-discord-bridge}"
  "$VENV/bin/python" - <<'PY'
import base64, json, os, sys, urllib.request, urllib.error
UA = "BaliseWatchBridge/1.0 (+https://balise-watch.app)"
def get(url, hdr):
    # ⚠️ L'User-Agent par défaut d'urllib se fait refouler en 403 par
    # Cloudflare devant l'API Discord. Constaté depuis le VPS le 09/09.
    r = urllib.request.Request(url, headers={"User-Agent": UA})
    [r.add_header(*h) for h in hdr.items()]
    with urllib.request.urlopen(r, timeout=20) as x: return json.loads(x.read())
try:
    me = get("https://discord.com/api/v10/users/@me",
             {"Authorization": "Bot " + os.environ["BW_DISCORD_TOKEN"]})
    print(f"  Discord      : OK — {me['username']}")
except Exception as e:
    print(f"  Discord      : ÉCHEC — {e}"); sys.exit(78)
try:
    site = os.environ.get("BW_JIRA_SITE", "https://balisewatch.atlassian.net")
    tok = base64.b64encode(
        f"{os.environ['BW_JIRA_EMAIL']}:{os.environ['BW_JIRA_TOKEN']}".encode()).decode()
    who = get(site.rstrip("/") + "/rest/api/3/myself",
              {"Authorization": "Basic " + tok, "Accept": "application/json"})
    print(f"  Jira         : OK — {who['emailAddress']}")
except Exception as e:
    print(f"  Jira         : ÉCHEC — {e}"); sys.exit(78)
print("✅ configuration valide")
PY
  exit $?
fi

cd "$ICI" || echec "répertoire introuvable : $ICI"
exec "$VENV/bin/python" -u bridge.py
