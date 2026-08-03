# Poller Infoclimat — le VPS poll, R2 transporte, Render lit

> Créé le 03/08/2026. Le module Infoclimat de `index.js` était écrit
> depuis le 17/07 mais n'a jamais tourné : sa clé est liée à UNE IP, et
> Render en a plusieurs. Ce dossier est la réponse.

| Fichier | Rôle |
|---|---|
| `poller_infoclimat.py` | le poller. Lit Infoclimat, écrit deux objets dans R2. |
| `poller.sh` | enveloppe : env, verrou, chien de garde, journal rotaté, alertes. |
| `balise-infoclimat.service` / `.timer` | déclencheur systemd, toutes les 5 min. |

---

## Ce qu'il faut avoir compris avant d'y toucher

**La fenêtre d'une heure n'existe pas.** `start`/`end` sont des DATES.
Tout composant horaire renvoie `status:"OK"`, `errors:[]`, `data:[]` et
aucune clé `hourly` — mesuré le 03/08, 7 appels
(`traces/sonde_fenetre_infoclimat.py`). Le minimum indivisible est la
journée. **Ne pas retenter.**

**Trois échecs de cette API arrivent en HTTP 200** et ressemblent à un
succès : `Wrong ip address` en texte brut, une réponse non-JSON, et
`status:"OK"` sans `hourly`. Les trois sont traités dans `fetch_lot()`.
Ne pas « simplifier » en regardant le code de statut.

**Le VPS sort en IPv6 par défaut.** `gai.conf` est un filet, pas une
garantie. `forcer_ipv4()` est obligatoire.

**`urllib` n'envoie pas `Accept-Encoding`.** Sans l'en-tête posé dans
`get()`, un lot de 100 pèse 2,90 Mo au lieu de 82 Ko. C'est la seule
ligne dont l'oubli ne casse rien de visible tout en multipliant la
charge par 35.

---

## Installation, une fois

```bash
# 1. L'état doit EXISTER avant le premier démarrage : un
#    ReadWritePaths pointant sur un chemin absent fait échouer le
#    montage systemd (piège rencontré le 03/08 sur l'entretien).
mkdir -p ~/.balise-watch-infoclimat

# 2. La clé Infoclimat vit dans le .env R2 déjà en place.
grep -q INFOCLIMAT_API_KEY ~/.balise-watch-r2.env || echo "⚠️ clé absente"

# 3. Un check Healthchecks DÉDIÉ — pas celui de l'entretien.
#    Sur healthchecks.io : nouveau check « poller Infoclimat »,
#    Period 5 min, Grace 20 min. Copier son URL de ping, puis :
#      printf 'export BW_INFOCLIMAT_PING_URL="https://hc-ping.com/<UUID>"\n' \
#        >> ~/.balise-watch-alertes.env
#      chmod 600 ~/.balise-watch-alertes.env
#    Vérifier SANS révéler l'UUID :
#      grep -c BW_INFOCLIMAT_PING_URL ~/.balise-watch-alertes.env   # → 1
#    Puis forcer un run et voir le check passer au vert :
#      sudo systemctl start balise-infoclimat.service
#      tail -n 5 ~/.balise-watch-infoclimat/poller.log
#    ⚠️ Si le journal dit « PERSONNE NE SURVEILLE CE POLLER », la
#    variable n'a pas été chargée : `poller.sh` source le fichier
#    d'alertes AVANT le .env R2, et systemd ne relit rien tout seul.

# 4. Les unités.
sudo cp balise-infoclimat.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now balise-infoclimat.timer
systemctl list-timers balise-infoclimat.timer
```

### Avant d'armer le timer, les trois essais dans l'ordre

```bash
set -a; . ~/.balise-watch-r2.env; set +a
cd ~/balise-watch/balise-watch-server/traces/infoclimat

# a. Ni appel, ni écriture. Vérifie le classement des cadences.
~/venv-balise/bin/python3 poller_infoclimat.py --dry-run

# b. Appelle pour de vrai, n'écrit rien. Vérifie la clé et les volumes.
~/venv-balise/bin/python3 poller_infoclimat.py --dry-run --reseau --limit 40

# c. Pour de vrai.
~/venv-balise/bin/python3 poller_infoclimat.py --go
```

### Ce qu'il faut voir au point c (relevé le 03/08, démarrage à froid)

```
parc : 1205 stations · 10 min: 57 · 30 min: 394 · 60 min: 431 · 180 min: 323
1205 stations dues → 13 lot(s) · 0 appel(s) déjà faits aujourd'hui / 500
2597 Ko sur le fil · 864 relevés neufs · 0 lot(s) en échec
latest.json écrit — 214 Ko → 32 Ko compressé
history.json écrit — 3136 Ko → 444 Ko compressé
R2 : 2 Class A · 1 Class B
```

⚠️ **`0 lot(s) en échec` est la ligne qui compte.** Si elle affiche 13,
c'est `Wrong ip address` : la clé n'est pas valide depuis cette IP, et
comme il arrive en HTTP 200, rien d'autre ne le dira.

---

## Ce que le poller écrit, et ce que Render doit en faire

Bucket `balise-watch-packs`, préfixe `infoclimat/`. Base publique :
`https://pub-14b7b6ffdba34729b51280359c8f2c01.r2.dev/`

| objet | taille | cadence | qui le lit |
|---|---|---|---|
| `infoclimat/latest.json` | 32 Ko gzip | chaque run utile | Render, pour la carte |
| `infoclimat/history.json` | 444 Ko gzip | toutes les 30 min | Render, en RAM |

**`latest.json`** remplace l'appel direct de `refreshInfoclimatObs` :
côté Render, ça change une constante d'URL, rien d'autre. Il porte les
métadonnées ET la dernière observation des stations fraîches (< 90 min).

**`history.json`** est au **format colonnaire** : chaque station porte
des tableaux ALIGNÉS sur `t`. Une série absente = entièrement nulle.
Un trou = `null` à sa position — ne jamais compacter les séries
indépendamment, ça afficherait un vent à la mauvaise heure.

> ⚠️ **`raf` n'est PAS null partout.** Ce document l'a écrit jusqu'au
> 03/08, sur la foi de 8 stations sondées le matin. Mesuré le soir sur
> l'objet réel : **25 stations sur 865 publient de vraies rafales**,
> souvent 140 à 178 points sur 30 h, avec un facteur rafale/moyenne
> allant de **1,1 à 4,1**. C'est justement l'omission des séries nulles
> qui masquait le fait : chez les 840 autres la clé `raf` DISPARAÎT au
> lieu d'apparaître pleine de `null`, ce qui ressemble à une absence
> générale quand on regarde une station au hasard.
>
> Conséquence pratique : **ne jamais reconstituer une rafale** à partir
> de la moyenne pour combler le trou. Le facteur varie du simple au
> quadruple d'une station à l'autre — une rafale déduite serait fausse,
> et fausse dans le sens qui la sous-estime. Côté PWA, l'absence est
> dite (« Rafale non fournie par cette station »), pas comblée.

> ⚠️ **Render doit le relire sur SA cadence et le garder en RAM**, comme
> `mfObsCache`, puis servir une station à la fois. Le relire à chaque
> requête client ferait transiter 444 Ko pour afficher un graphe — le
> même gaspillage qu'on vient de retirer chez Infoclimat, déplacé d'un
> cran.

> ⚠️ **Pas de Supabase**, contrairement aux stations MF. MF n'a aucun
> historique natif, d'où `mf_station_history` qui s'accumule point par
> point. Infoclimat renvoie la journée entière à chaque appel :
> l'historique, on l'a déjà.

### La compression est transparente, vérifié le 03/08

Cloudflare normalise selon ce que demande le client :

| requête | reçu |
|---|---|
| sans `Accept-Encoding` | 218 Ko, JSON en clair, pas d'en-tête d'encodage |
| avec `Accept-Encoding: gzip` | 33 Ko, `Content-Encoding: gzip` |

Le `fetch` de Node envoie `Accept-Encoding` de lui-même : Render lira
33 Ko sans qu'on ait rien à écrire.

---

## Les licences

⚠️ **La licence VARIE d'une station à l'autre**, y compris dans un rayon
de 20 km. Relevé sur les 854 stations servies le 03/08 :

| licence | stations |
|---|---|
| `NON-COMMERCIAL ONLY: CC BY NC` | 442 |
| `CC BY` | 412 |

Elle voyage **par station** dans `latest.json`. Toute UI doit porter la
licence **de la station affichée**, jamais une mention globale : elle
serait fausse pour une station sur deux.

---

## Cadence, et pourquoi elle est ce qu'elle est

Par **densité de décos** dans 25 km, pas par département — une frontière
administrative n'a pas de sens météo, et un déco de bordure lit
forcément des stations de l'autre côté.

| décos dans 25 km | stations | cadence |
|---|---|---|
| 20 et + | 57 | 10 min |
| 5 à 19 | 394 | 30 min |
| 1 à 4 | 431 | 60 min |
| 0 | 323 | 180 min |

Charge chez Infoclimat : **1,82 M de lignes lues/jour contre 7,06 M**,
soit 3,9× moins. (Et non 190× : ce chiffre du prompt de reprise
multipliait la cadence par un gain de 60× sur la fenêtre, qui n'existe
pas.)

Trois règles ne peuvent que **ralentir**, une seule accélère :

1. **cadence native apprise** — l'intervalle effectif est
   `max(palier, cadence observée)`. Elle s'apprend gratuitement, dans
   les réponses qu'on reçoit déjà.
2. **rétrogradation sans anémomètre** — aucun vent depuis 3 jours → 180
   min. 26 % du parc était sans relevé le 03/08.
3. **escalade sur événement** — la seule qui accélère, bornée au
   plancher de 10 min.

⚠️ **Le plancher de 10 min est dur.** Les stations mesurent toutes les
10 à 14,7 min : en dessous, on redemande la même valeur.

---

## L'escalade (§3) — mécanisme posé, déclencheur absent

Les signaux flightwatch (`sig_pressure_drop`, `sig_vigilance`,
`sig_wind_surge`) et les axes de foehn sont calculés **par Render**. Le
VPS ne les voit pas, et on ne lui ouvre aucun port entrant.

Canal retenu : le même que dans l'autre sens. **Render écrit
`infoclimat/escalade.json` dans R2, le poller le lit.** Tant que Render
ne l'écrit pas, le mécanisme est inerte — c'est voulu et sans risque.

```json
{ "stations": { "STATIC0216": { "cadence_min": 10,
                                "expire_ts": 1785780000 } } }
```

⚠️ **`expire_ts` est OBLIGATOIRE.** La désescalade se fait par
expiration, **jamais** par « l'événement est fini » : un état bloqué en
alerte pollerait au maximum indéfiniment. Une entrée expirée est
ignorée et journalisée.

---

## Les plafonds, et quoi faire quand ils sautent

| plafond | valeur | effet |
|---|---|---|
| `MAX_APPELS_JOUR` | 500 | abort net, aucun réessai |
| `MAX_APPELS_RUN` | 20 lots | borné, et journalisé |
| plafond d'écritures R2 | 4 par run | abort net (`storage.py`) |

Cible mesurée : **328 requêtes/jour**. Si le plafond quotidien saute,
**comprendre avant de relever la constante** : escalade bloquée ?
cadence apprise à zéro ? timer trop fréquent ? Le relever sans
diagnostic, c'est déplacer le problème chez des bénévoles.

---

## Le principe qui commande tout

Infoclimat est une **association loi 1901 à but non lucratif**, tenue
par des bénévoles, dont la page open data demande explicitement d'éviter
les abus. Les stations sont hébergées par des **particuliers** qui ont
accepté de partager leurs mesures.

**Réduire la charge n'est pas une optimisation technique ici, c'est la
condition d'usage.** Chaque constante qu'on remonte se paie chez eux.
