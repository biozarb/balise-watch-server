#!/bin/bash
# ══════════════════════════════════════════════════════════════════════
#  Installer le webhook Discord comme SECOND canal du téléphone.
#  Écrit par la session Balise Watch du 07/10/2026.
#
#  ⛔ LANCE-LE TOI-MÊME, depuis le Terminal du Mac :
#         bash ~/installer-webhook-discord.sh
#
#  ⚠️ L'URL du webhook est un SECRET (qui l'a peut publier sur le salon).
#  Ce script la lit SANS L'AFFICHER et la pose sur le VPS par un tube :
#  elle n'apparaît ni à l'écran, ni dans ton historique de shell, ni dans
#  `ps`, ni dans aucune conversation. C'est la même règle que BW_JIRA_TOKEN.
#
#  Où trouver l'URL : Discord → le salon voulu → Modifier le salon →
#  Intégrations → Webhooks → Nouveau webhook → Copier l'URL du webhook.
#  Elle ressemble à https://discord.com/api/webhooks/<id>/<jeton>
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail
VPS="debian@51.91.102.146"
ENVF='$HOME/.balise-watch-alertes.env'

printf 'Colle l’URL du webhook Discord (elle ne s’affichera pas), puis Entrée :\n> '
IFS= read -rs URL
echo
if [ -z "${URL:-}" ]; then echo "⛔ rien saisi — j’arrête, rien n’a été changé."; exit 1; fi
case "$URL" in
  https://discord.com/api/webhooks/*|https://discordapp.com/api/webhooks/*) : ;;
  *) echo "⛔ ça ne ressemble pas à une URL de webhook Discord — j’arrête, rien n’a été changé."; exit 1 ;;
esac
echo "✓ URL retenue (${#URL} caractères, jamais affichée)."

echo
echo "── 1. sauvegarde du .env, puis écriture de la variable ──"
printf '%s' "$URL" | ssh "$VPS" 'bash -s' <<'FIN'
set -uo pipefail
ENVF="$HOME/.balise-watch-alertes.env"
URL=$(cat)
cp -p "$ENVF" "$HOME/sauvegardes-balise-watch/alertes.env.avant-discord-07-10" 2>/dev/null \
  || { mkdir -p "$HOME/sauvegardes-balise-watch"; cp -p "$ENVF" "$HOME/sauvegardes-balise-watch/alertes.env.avant-discord-07-10"; }
echo "   sauvegarde : ~/sauvegardes-balise-watch/alertes.env.avant-discord-07-10"
MODE=$(stat -c %a "$ENVF")
# Remplace la ligne si elle existe, l'ajoute sinon. Jamais deux fois.
if grep -q '^export BW_DISCORD_WEBHOOK_URL=' "$ENVF"; then
  grep -v '^export BW_DISCORD_WEBHOOK_URL=' "$ENVF" > "$ENVF.tmp"
  mv "$ENVF.tmp" "$ENVF"
  echo "   ancienne valeur remplacée"
fi
printf 'export BW_DISCORD_WEBHOOK_URL=%s\n' "$URL" >> "$ENVF"
chmod "$MODE" "$ENVF"
echo "   écrit. droits conservés : $(stat -c %a "$ENVF")"
echo "   lignes du .env : $(wc -l < "$ENVF")  (noms seulement ci-dessous)"
sed -e 's/^export //' -e 's/=.*$//' "$ENVF" | grep -c . | sed 's/^/   variables : /'
FIN

echo
echo "── 2. épreuve du canal, pour de vrai ──"
ssh "$VPS" 'bash -s' <<'FIN'
set -uo pipefail
set -a; . "$HOME/.balise-watch-alertes.env"; set +a
. "$HOME/balise-watch/balise-watch-server/tools/bw_avertir_config.sh"
bw_push_discord "Balise Watch - epreuve du second canal" \
  "Si tu lis ceci sur Discord, le second canal du telephone fonctionne. Pose le 07/10/2026 apres la panne du webhook ntfy (quota du prefixe IPv6 partage d OVH)."
echo "   HTTP $BW_PUSH_DISCORD_CODE   (2xx = parti)"
FIN

echo
echo "── 3. et ntfy, toujours vivant ? ──"
ssh "$VPS" 'set -a; . $HOME/.balise-watch-alertes.env; set +a;
  printf "   ntfy IPv4 : "; curl -sS --ipv4 -m 15 https://ntfy.sh/v1/account \
    | /home/debian/venv-balise/bin/python3 -c "import sys,json;d=json.load(sys.stdin);print(d[\"stats\"][\"messages\"],\"/\",d[\"limits\"][\"messages\"],\"- restants\",d[\"stats\"][\"messages_remaining\"])"'

echo
echo "✓ Fini. Les deux canaux partent désormais ensemble sur chaque ⛔."
echo "  Pour revenir en arrière : cp ~/sauvegardes-balise-watch/alertes.env.avant-discord-07-10 ~/.balise-watch-alertes.env  (sur le VPS)"
