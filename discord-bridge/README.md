# discord-bridge — le pont Discord → Jira

*Posé le 09/09/2026, en même temps que le serveur Discord.*

## Ce qu'il fait

**Un post dans `#bugs` ou `#idées` devient un ticket Jira.** Titre du post → résumé,
premier message → description, tags de module → labels, lien du fil dans le ticket.
Le bot répond dans le fil avec la clé, et pose le tag `Nouveau` (bugs) ou `À trier` (idées).

**Le statut Jira commande le tag Discord.** Toutes les 5 minutes, le pont relit les
statuts et met les tags en accord. C'est le seul canal par lequel un pilote apprend
que son bug avance — et il n'a rien à faire pour ça.

| Statut Jira | Tag sur un bug | Tag sur une idée |
|---|---|---|
| À faire | Confirmé | Retenue |
| En cours / En cours de revue / Mise en prod | En cours | En cours |
| Terminé | Corrigé | Livrée |

Quand un ticket passe à *Terminé*, le bot poste aussi un mot dans le fil, avec le
rappel du cache — parce que la moitié des « c'est toujours pas corrigé » du WhatsApp
étaient une vieille version en cache.

**Un post dans `#prévu-vs-observé` ne crée aucun ticket.** Il est journalisé dans
`observations.jsonl`. Un retour terrain isolé n'est pas actionnable ; c'est le
recoupement entre pilotes qui l'est, et ça ne se fait pas dans un backlog.

## Ce qu'il ne fait pas

Il ne modère rien, ne supprime rien, et n'écrit dans aucun salon public autre que
le fil qu'un pilote vient d'ouvrir. Tout le reste de sa parole va dans `#flux-jira`,
qui est privé.

Le pont est **unidirectionnel pour le contenu, bidirectionnel pour le statut** :
Discord crée le ticket, Jira commande le tag, jamais l'inverse. C'est pour ça que
les tags de statut sont déclarés `moderated` côté Discord — un pilote ne peut pas
marquer son propre bug « Corrigé ».

## Installation

```bash
# 1. le venv, séparé de venv-balise expressément
python3 -m venv ~/venv-discord
~/venv-discord/bin/pip install -U pip discord.py

# 2. les secrets
cat > ~/.balise-watch-discord.env <<'EOF'
BW_DISCORD_TOKEN=...
BW_JIRA_EMAIL=biozarb@gmail.com
BW_JIRA_TOKEN=...
BW_JIRA_SITE=https://balisewatch.atlassian.net
BW_JIRA_PROJET=KAN
EOF
chmod 600 ~/.balise-watch-discord.env

# 3. l'état
sudo mkdir -p /var/lib/bw-discord-bridge
sudo chown debian:debian /var/lib/bw-discord-bridge

# 4. contrôle avant de lancer quoi que ce soit
./run.sh --controle

# 5. le service
sudo cp systemd/bw-discord-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bw-discord-bridge
journalctl -u bw-discord-bridge -f
```

## Exploitation

```bash
systemctl status bw-discord-bridge          # est-il vivant ?
journalctl -u bw-discord-bridge -n 100      # les 100 dernières lignes
./run.sh --controle                         # les deux accès répondent-ils ?
cat /var/lib/bw-discord-bridge/etat.json    # la correspondance fil ↔ ticket
wc -l /var/lib/bw-discord-bridge/observations.jsonl   # les retours terrain
```

**Le pont ne rattrape pas ce qu'il a manqué.** Discord ne rejoue pas les évènements
d'un bot déconnecté : un post ouvert pendant une panne n'aura jamais son ticket.
`Restart=always` est là pour ça, mais si le service reste à terre plusieurs heures,
il faut relire les posts de la période à la main.

**Si un secret manque**, `run.sh` sort en 78 et systemd n'insiste pas
(`RestartPreventExitStatus=78`). Le journal dit laquelle.

## Les identifiants Discord en dur

Ils sont dans `bridge.py` comme valeurs par défaut, surchargeables par l'environnement.
Si un forum est recréé, son identifiant change — le mettre dans le fichier `.env` :

| Salon | Variable | Identifiant |
|---|---|---|
| `#bugs` | `BW_FORUM_BUGS` | 1547197502179119144 |
| `#idées` | `BW_FORUM_IDEES` | 1547197506117574746 |
| `#prévu-vs-observé` | `BW_FORUM_TERRAIN` | 1547197494986023085 |
| `#flux-jira` | `BW_SALON_FLUX` | 1547197453759938581 |

Serveur : `1547190772699369523`.

## Ce qui n'est pas fait, volontairement

- **Pas de création de ticket depuis `#prévu-vs-observé`.** Voir plus haut.
- **Pas de fermeture de ticket depuis Discord.** Le tag `Non reproductible` ne
  referme rien côté Jira : la décision reste dans Jira, sinon les deux côtés
  se contredisent un jour ou l'autre.
- **Pas de synchronisation des commentaires.** Une discussion de fil n'a pas
  vocation à polluer un ticket. Si un échange fait avancer le diagnostic,
  c'est un commentaire Jira écrit à la main.
