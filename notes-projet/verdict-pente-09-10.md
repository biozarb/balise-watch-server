# Verdict de pente du 09/10/2026 — RUN INCOMPLET : le Mac s'est déconnecté en pleine Étape 1. Le registre a été lu (et il est **bon** : la mémoire **retombe** de 73 Mo sous son record et le coût par ligne rentre dans le bas de la fourchette ; la durée recule de 36 s), mais **le journal de la nuit, la position, les témoins et le contrôle de 07:30 n'ont PAS pu être lus, et AUCUN ticket Jira n'a été touché**. La routine a tiré **6 h 40 en retard** — pire valeur de la série.

## 16:00 (Paris) — routine Balise Watch (tirée à 13:51:21 UTC pour 07:11:05 : **6 h 40 de RETARD**), lecture du registre seule, **zéro écriture**

**Étape 0 faite, et elle était propre.** `git log --oneline --since=midnight` :
**aucun commit du jour**, ni dans `balise-watch-server` ni dans le dépôt
principal. `project_read` de `claude/verdict-pente-09-10.md` → « No doc » ;
`claude/verdict-pente-08-10.md` lu **en entier**.
`notes-projet/README.md` relu. ⇒ **premier et seul run du jour, rien à
fusionner.**

⛔ **CE RUN EST INCOMPLET — ET C'EST LE FAIT PRINCIPAL DU MATIN.** La session
est linkée au Mac `mbp-local`, qui n'avait **aucun dossier connecté** ; la
seule route vers le VPS est le `ssh` du Mac, par Desktop Commander. Les deux
premières lectures sont passées (registre, `list-timers`), puis **le Mac s'est
déconnecté du bridge** pendant la troisième (`journalctl` du contrôle +
`controle_quotidien.py --verbeux`). Trois reprises après 0, 100 et 340 s :
« device not connected » chaque fois. Le conteneur cloud, lui, n'a **pas** de
route SSH vers `51.91.102.146` (sortie HTTPS par mandataire uniquement) et ne
porte pas la clé — il n'y a pas de contournement.

**Conséquences, à lire comme des trous et non comme des constats :**

| à lire | lu ? |
|---|---|
| registre `historique.jsonl` (3 nuits) | ✅ **oui** |
| `systemctl list-timers` | ✅ oui |
| journal `bw-model-controle.service` du jour | ⛔ **non** |
| `controle_quotidien.py --verbeux` (pentes, « N comparable(s) ») | ⛔ **non** |
| journal `bw-model-score.service` de la nuit (bloc purge, position, témoins, Murphy, duels…) | ⛔ **non** |
| GET Jira des états de KAN-3/4/5 | ⛔ **non** |
| noms des variables du `.env` (`BW_DISCORD_WEBHOOK_URL`) | ⛔ **non** |

⛔ **AUCUN TICKET N'A ÉTÉ TOUCHÉ.** Pas de commentaire, pas de création, pas de
transition, pas de GET. `bw_jira.sh` vit sur le VPS : sans le Mac, il est hors
d'atteinte. **KAN-3, KAN-4 et KAN-5 sont donc restés tels qu'au 08/10**
(Terminé/19 · À faire/30 · À faire/13 commentaires), **non revérifiés**. ⓘ Le
garde-fou n'a pas été consommé par la routine ; si le contrôle de 07:30 a
parlé, c'est lui seul qui a posé les jetons du jour.

⛔ **PAS DE MIROIR GIT POUR CETTE NOTE.** La règle n° 3 du `README.md` demande
un dépôt dans `notes-projet/` et un commit local : **impossible sans le Mac.**
Cette note n'existe donc **que** côté projet, sans filet. ⚠️ **À reprendre
demain matin** : déposer `notes-projet/verdict-pente-09-10.md` et le commiter
en même temps que celui du 10/10.

⚠️ **LE RETARD DE TIR S'AGGRAVE NETTEMENT : 6 h 40.** Programmé pour
**07:11:05 UTC**, tiré à **13:51:21 UTC**. Historique : retards les 04, 05 et
06/10 (jusqu'à 4 h 10), **aucun tir** les 02 et 03/10, **à l'heure** le 07/10,
**+2 h 10** le 08/10, **+6 h 40** aujourd'hui — **la pire valeur relevée**.
ⓘ **Le VPS, lui, est à l'heure** : `bw-model-controle.timer` a tiré à
**07:30:39** (prochain samedi 10/10 07:30:08) et la notation à **06:00:03**.
**Le trou est côté planification de la routine, pas côté machine** — et il est
probablement pour quelque chose dans la déconnexion : à 15:52 (Paris) le Mac
de Yann n'a aucune raison d'être disponible, alors qu'à 09:11 il l'était.

## 1. Les nuits, bout à bout (registre seul)

| | 04/10 | 05/10 | 06/10 | 07/10 | 08/10 | 09/10 |
|---|---|---|---|---|---|---|
| durée | 4 876 s | 4 821 s | 5 157 s | 5 227 s | 5 228 s | **5 192 s (−36)** |
| garde / marge | 8 100 / 3 224 | 8 100 / 3 279 | 8 100 / 2 943 | 8 100 / 2 873 | 8 100 / 2 872 | **8 100 / 2 908 (+36)** |
| marge en % du garde | 39,8 % | 40,5 % | 36,3 % | 35,5 % | 35,46 % | **35,90 %** |
| `cpu_s` | 3 964,5 | 3 853,3 | 4 163,6 | 4 244,9 | 4 257,9 | **4 199,5 (−58,4)** |
| jalon max | 3 376 Mo | 3 417 Mo | 3 364 Mo | 3 420 Mo | **3 429 Mo** | **3 356 Mo (−73) ← plus bas des 7** |
| au-dessus du seuil | +576 | +617 | +564 | +620 | +629 | **+556** |
| swap au pic | 2 592,1 | 2 218,3 | 2 175,5 | 2 127,7 | 2 267,1 | **2 145,1 (−122,0)** |
| pages sorties | 2 338 891 | 2 579 457 | 2 507 693 | 2 369 940 | 2 556 336 | **2 241 569 (−314 767)** |
| pic système | 3 624,7 | 3 600,5 | 3 619,1 | 3 617,2 | 3 602,9 | **3 615,2 (+12,3)** |
| fenêtre rejouée | 2 085 523 | 2 086 473 | 2 087 575 | 2 088 602 | 2 089 691 | **2 089 138 (−553)** |
| o / ligne rejouée | 1 697,4 | 1 717,2 | 1 689,7 | 1 717,0 | **1 720,6** | **1 684,4 (−36,2)** |
| `n_57014` | 0 | 0 | 2 (purge) | 0 | 0 | **0** |
| lancement / résultat | timer/success | timer/success | timer/success | timer/success | timer/success | **timer/success** |

Nuit **comparable** : `lancement=timer`, `exec_status=0`, `oom=0`,
`result=success`, **06:00:03 → 07:26:48**. Rien à écarter. ⚠️ Mais le verdict
du contrôle lui-même (« N comparable(s) », les deux pentes au 25e centile,
l'horizon) **n'a pas été lu** : impossible de dire s'il a crié ou s'il s'est
tu, ni sur quel motif.

## 2. ✅ Mémoire : le record est **DÉFAIT**, et la lecture d'hier est démentie dans le bon sens

```
⛔ après le rejeu d'archive            : 3 048 Mo  (3 024 le 08, 2 995 le 07)  ← plus haut
⛔ après le score par régime           : 2 937 Mo  (2 901 le 08, 2 909 le 07)  ← plus haut
⛔ après l'oubli de la fenêtre rejouée : 3 356 Mo  (3 429 le 08, 3 420 le 07)  ← jalon max, EN BAISSE
```

Jalon max **3 356 Mo (−73)**, **556 Mo au-dessus du seuil**. Après **deux**
matins de record (3 420 puis 3 429), le jalon **retombe sous les sept
dernières nuits** — plus bas que le 3 364 du 06/10.

```
29/09 1 671,3 o · 30/09 1 692,6 · 01/10 1 685,6 · 02/10 1 689,2
03/10 1 706,4  · 04/10 1 697,4 · 05/10 1 717,2 · 06/10 1 689,7
07/10 1 717,0  · 08/10 1 720,6 · 09/10 1 684,4
  → −36,2 o/ligne, le plus gros recul de la série
  → 1 684,4 est le plus bas depuis le 29/09 (deuxième plus bas des onze)
```

✅ **LA NOTE D'HIER EST DÉMENTIE, ET ELLE AVAIT ÉCRIT EXACTEMENT CE QU'IL
FALLAIT.** Le 08/10 posait : « les trois dernières valeurs sont 1 689,7 →
1 717,0 → 1 720,6 ⇒ à surveiller en priorité demain : une **quatrième** valeur
haute changerait la lecture ». La quatrième valeur est arrivée et elle est
**basse** — la plus basse depuis onze jours. ⇒ ⛔ **l'hypothèse « la fourchette
s'étire vers le haut » tombe. Ce n'est pas une pente : c'est bien une
oscillation, et plus large qu'on ne croyait (1 671–1 721, soit 50 o/ligne).**
C'est la **sixième** fois en douze jours que « une nuit ne fait pas une pente »
sert — et la première fois qu'elle protège d'une mauvaise nouvelle au lieu
d'une bonne.

À taux constant : au taux du **08/10** (1 720,6 o/ligne) la nuit aurait rendu
**3 428,1 Mo** — elle a rendu 3 356, soit **−72,1 Mo** gagnés à structure
inchangée. Au taux du **01/10** (1 685,6), **3 358,3 Mo** : l'écart n'est plus
que de **−2,3 Mo**. ⇒ **la nuit est, au coût par ligne, revenue au niveau du
début du mois.**

⚠️ **Deux réserves, et elles comptent :**
- Les **deux premiers** jalons sont au contraire **au plus haut de la série**
  (rejeu d'archive 3 048, score par régime 2 937). Seul le **troisième** —
  celui qui fait le max — recule. La pression ne disparaît pas, elle se
  déplace.
- Le gain arrive avec une fenêtre qui **recule** pour la première fois
  (−553 balise-jours) : minuscule (0,03 %), mais c'est une baisse, pas la
  hausse habituelle. Le coût par ligne neutralise la fenêtre, donc le −36,2
  reste valable.

**Swap : pic 2 145,1 Mo (−122,0)** et **2 241 569 pages sorties
(−314 767)** — les deux reculent ensemble, cohérent. ⚠️ Le plancher tient
quand même : **10e nuit consécutive au-dessus de 2,1 Go**.

**Rien de déployé côté mémoire depuis `af25efb` (21/09) — 19e nuit sans
levier.** Le remède reste la **ligne en tuple** (`enquete-pente-10-09.md`
§2.6, ≈ −1 030 o/ligne), après la mesure `tuple` vs `namedtuple` à la sonde.

⛔ **KAN-4 n'a pas été commenté** (Mac déconnecté). ⓘ Pour mémoire, les trois
conditions de fermeture restent **non remplies** : jalon mesurément retombé →
**partiellement** (−73 Mo, mais toujours +556 au-dessus du seuil et dans la
fourchette des sept dernières nuits) ; swap au pic ≈ 0 → **NON (2 145,1)** ;
contrôle muet → **inconnu, non lu**. ⇒ **rien ne plaidait pour une fermeture
de toute façon.**

## 3. ✅ Durée : le plateau tient et s'incline légèrement vers le bas

`4 821 · 5 157 · 5 227 · 5 228 · **5 192**`. Après +336, +70, +1, la nuit rend
**−36 s**. ⇒ **le plateau du 08/10 se confirme, et pour la première fois depuis
le 05/10 la marge remonte** : 2 908 s = **35,90 %** de 8 100 (contre 35,46 %
hier, le plus bas relevé). ⚠️ **Mais rien n'est rendu des +406 s des 06 et
07/10** : on reste au niveau haut, 371 s au-dessus du 05/10.

`cpu_s` **4 199,5 (−58,4)** pour **−36 s** d'horloge : le processeur baisse
**plus** que le temps réel ⇒ ce qui est rendu est bien du **calcul**, pas de
l'attente. Et `n_57014 = 0` pour la **troisième** nuit d'affilée : **zéro
attente sur la base**.

| étape | 06/10 | 07/10 | 08/10 | 09/10 |
|---|---|---|---|---|
| `regime` | 1 820,0 | 1 794,6 | 1 813,6 | **1 751,4 (−62,2)** |
| `glissant` | 1 002,0 | 1 018,3 | 1 005,9 | **988,2 (−17,7)** |
| `stabilite` | 328,8 | 341,7 | 338,1 | **322,5 (−15,6)** |
| `rejeu` | 81,5 | 88,4 | 79,2 | **78,3 (−0,9)** |
| somme des quatre | 3 232,3 | 3 243,0 | 3 236,8 | **3 140,4 (−96,4)** |
| hors étapes | 1 924,7 | 1 984,0 | 1 991,2 | **2 051,6 (+60,4)** |

⚠️ **Quatrième nuit, quatrième signature — mais celle-ci répète la moitié de
celle d'hier.** Les **quatre** étapes reculent ensemble (−96,4 s au total,
fait inédit de la série), et le **hors-étapes monte de +60,4 s**, son troisième
gain consécutif (1 924,7 → 1 984,0 → 1 991,2 → 2 051,6 : **+127 s en trois
nuits, sans un seul recul**). ⇒ ⓘ **c'est désormais la seule tendance
monotone du tableau**, et elle porte sur le **bloc non instrumenté**
(publication, Murphy, événements, pression, duels, purge). **La question
d'hier à Yann — poser des jalons de temps dans `run.sh` — gagne en force
plutôt qu'elle n'en perd**, même si la durée totale, elle, a cessé de monter.

⛔ **LE DÉCOUPLAGE TEMPS / VOLUME S'INVERSE PLUS FRANCHEMENT ENCORE.**
`lignes_regime` **125 224 (+3 247, soit +2,7 %)**, `lignes_score_zone`
**135 772 (+3 247)**, `lignes_glissant` **10 548 (inchangé au point près)**,
`lignes_daily` **69 599 (−65)**. Le volume de `regime` monte de **2,7 %** et le
temps de `regime` **baisse de 3,4 %**. Deuxième nuit d'affilée où le volume
monte sans que le temps suive — et cette fois il recule. ⇒ ⚠️ **confirmation
de la lecture d'hier : temps et volume ne sont PAS corrélés, ni dans un sens
ni dans l'autre.** Ce qui pilote la durée n'est pas le nombre de lignes.

Coût par ligne de `regime` :

```
13,39 (01/10) · 13,24 · 14,02 · 13,67 · 13,53 · 15,07 · 14,86 · 14,87 · 13,99 (09/10)
  → −0,88 ms : retour au niveau du 03/10, sortie du haut de la fourchette
```

✅ **`bw-regime-sensibilite` : critère NON rempli, rien n'est créé — et il
s'éloigne.** L'arbitrage unique du 07/10 exige **deux hausses consécutives** du
coût par ligne. Il y a une **baisse**, et la plus forte depuis le 07/10. Le
compteur de hausses consécutives retombe à **zéro**. ⓘ Le seuil de 14,5 ms de
la note du 06/10 reste retiré depuis le 07/10 ; à 13,99 il n'aurait de toute
façon pas été franchi.

Coût par ligne de `glissant` : **95,4 → 93,7 ms**.

⛔ **KAN-3 n'a pas été commenté** (Mac déconnecté). ⓘ Il n'y avait de toute
façon **pas de hausse à rapporter** : la consigne de l'Étape 2 ne demande un
`bw_jira_commenter KAN-3` que « si la durée AUGMENTE ». Elle baisse. ⚠️ Mais
le commentaire du 08/10 annonçait un plateau « au plus mauvais endroit » ; la
marge a repris 0,44 point, et **cette correction-là reste à écrire** quand le
canal sera rouvert. **Aucune remontée du garde n'est proposée**, et
`10-timeout-s3.conf` n'a pas été touché.

## 4. ⚠️ Purge : `n_57014 = 0` pour la 3e nuit, mais le bloc **n'a pas été lu** — le compteur de KAN-5 reste à **2 / 3**

Ce que le registre dit, et c'est tout :

```
"n_57014": 0
"incidents": [les TROIS lignes mémoire, et RIEN d'autre]
```

⚠️ **C'est une indication forte, pas un constat.** `incidents` ne porte
**aucun** avertissement de purge — ni tranche à 57014, ni sonde « plus vieille
journée illisible », ni `compte model_score_zone : HTTP 500` — et `n_57014`
est à 0. Depuis le correctif du 07/10, on sait que `incidents` **garde**
l'avertissement même après un rejeu réussi : son silence total est donc plus
concluant que sa présence. ⇒ **la purge de la nuit du 08→09 est très
probablement propre.**

⛔ **MAIS LES DEUX CHIFFRES QUI FERMENT LE DOSSIER MANQUENT** : le **nombre de
lignes effacées** et le **nombre de tranches** ne sont pas au registre (c'est
la question n° 7 d'hier, toujours sans réponse : *faut-il un champ de bilan de
purge au registre ?* — **ce matin en est la démonstration pratique**), et
l'état de la **sonde** ne se lit que dans le journal. La consigne est
explicite : on ne ferme KAN-5 que sur **trois nuits consécutives sans 57014
dans le bloc purge ET avec un nombre de lignes lisible**.

⇒ ⛔ **le compteur reste officiellement à 2 / 3.** Il passera à **3 / 3** dès
que le bloc purge de cette nuit sera lu — c'est la **première chose à faire
demain matin**, avant même la nuit nouvelle (`journalctl -u
bw-model-score.service --since "2026-10-09 00:00" | grep -A2 -B8 "purge
model_score_zone"`). Et ce jour-là **la question de la fermeture de KAN-5 sera
POSÉE à Yann**, pas tranchée par la routine.

⚠️ **Le dossier « base sous tension » ne se referme pas davantage.**
`model-verif/diagnostic_base_sous_tension_2026-09-29.sql` (lecture seule,
9 blocs, SQL Editor) **n'a toujours pas été joué — dix jours d'attente.** Trois
nuits à `n_57014 = 0` ne sont pas un correctif : il y en a eu trois d'affilée
les 03, 04 et 05/10 avant que le 57014 revienne le 06.

⛔ **KAN-5 n'a pas été commenté** (Mac déconnecté).

## 5. ⛔ Non lu cette nuit — à reprendre tel quel demain

Tout ce qui vit dans le journal de `bw-model-score.service` est **absent** de
ce compte rendu. Ce ne sont pas des « rien à signaler », ce sont des trous :

- **Position** : combien de balises divergent, combien de CONFIRMÉES, si un
  cri est parti. Au 08/10 : **4 confirmées** (`pioupiou:1333` 87,7 km,
  `pioupiou:2171` 38,9 km, `pioupiou:1388` 2 363 m, `infoclimat:STATIC0491`
  1 159 m) et **7 à 3 j**, qui franchiraient 10 j le **15/10** — ce jour-là le
  compte passerait de 4 à 11, donc **un cri à front**. Si l'une des sept a
  avancé d'un jour cette nuit, elle est à 4 j. **Non vérifié.**
- **Le webhook `push`** : le correctif `--ipv4` du 07/10 **attend toujours sa
  première épreuve réelle**, faute de ⛔ depuis. Impossible de dire si un cri
  est parti cette nuit. Si le compte de position est resté à 4, le canal « à
  front » est resté muet et le correctif attend encore.
- **`BW_DISCORD_WEBHOOK_URL`** : absente du `.env` au 08/10. **Non revérifiée**
  — le second canal du téléphone est donc, au mieux, dans le même état :
  codé, testé, **muet**.
- **Témoins du mélange** (§7 d'hier) : le gain contre le meilleur membre a
  priori était remonté à **+2,5 %** après le −0,6 % du 07/10, mais le gain
  contre la moyenne **uniforme** reculait pour la quatrième nuit
  (6,0 → 4,9 → 4,8 → **3,1 %**). **C'était la série à suivre ce matin, et elle
  n'a pas pu l'être.**
- **Écarts au recalcul indépendant** (4 le 08/10, tous en `fcstagrume`),
  **self-test du scoring**, **`tau`** (0,744 sur 60 cases), **ρ hors [0, 1]**
  (307 le 08/10, après quatre nuits d'amélioration), **Murphy**, **duels
  appariés**, **R2**, **`mutations_memoire`** (3 mutations non vues, dette
  antérieure), **observations du jour** : tous **non lus**.
- **Le verdict du contrôle de 07:30** : pentes, nombre de relevés comparables,
  propositions. Le timer a bien tiré à **07:30:39** — le service a donc tourné,
  son journal existe, il n'a simplement pas été lu.

## 6. Ce qui a été touché

**VPS — règle de LECTURE SEULE pleine et entière, respectée.** Deux commandes
`ssh` seulement, toutes deux en lecture : `date`, `tail -n 3` du registre,
`systemctl list-timers` (sans élévation de droits). **Aucun `systemctl
start/restart/daemon-reload`, aucun `enable`, aucun SQL joué, aucun `rsync`,
rien écrit dans `~/balise-watch` ni dans `/etc`, aucun fichier déposé.**
**Aucun secret lu, ni par valeur ni par nom.** **Aucune écriture d'aucune
sorte, Jira compris.**

**Mac** : rien. Pas de fichier créé, pas de script, pas de commit, **pas de
miroir git de cette note** (voir plus haut), pas de `git push`.

**Projet Claude** : cette note, créée (`claude/verdict-pente-09-10.md`
n'existait pas — vérifié par `project_read` avant écriture).

## 7. Ce qui reste — et ce qui demande Yann

**Pour toi, et rien ne bougera sans toi :**

1. ⛔ **L'HORAIRE DE LA ROUTINE : +6 h 40, la pire valeur relevée.** Tir à
   13:51 UTC pour 07:11. Série : à l'heure le 07/10, +2 h 10 le 08/10,
   **+6 h 40 le 09/10** ; avant cela jusqu'à 4 h 10 les 04–06/10 et **aucun
   tir** les 02 et 03/10. Le VPS est à l'heure (contrôle 07:30:39, notation
   06:00:03) : **le trou est côté planification.** ⚠️ **Et il coûte
   maintenant des données** : à 15:52 (Paris) ton Mac n'a pas de raison d'être
   disponible, alors qu'à 09:11 il l'était — **c'est le retard qui a fait
   échouer la moitié du run.** C'est devenu le point n° 1.
2. ⛔ **Jouer `diagnostic_base_sous_tension_2026-09-29.sql`** dans le SQL
   Editor (lecture seule, 9 blocs). **Dix jours d'attente.**
3. ⛔ **Trancher les 4 cas de position** (`1333` à 87,7 km et `2171` à 38,9 km
   → AUTRE balise ? `1388` à 2 363 m, qui s'était éloignée ? `STATIC0491` à
   1 159 m → maille ?), puis poser `position_suspecte` + `position_note` par
   `.sql`. ⓘ Les sept autres franchiraient 10 j le **15/10**.
4. ⛔ **Lancer `~/installer-webhook-discord.sh`** depuis le Terminal du Mac.
   ntfy reste seul, avec son quota anonyme de voisinage, et le correctif
   `--ipv4` **n'a toujours pas été éprouvé en conditions réelles**.
5. ⚠️ **Dire si tu veux instrumenter le bloc hors étapes de `run.sh`.** La
   question est **plus pressante qu'hier**, pas moins : le hors-étapes monte
   pour la **troisième nuit d'affilée** (+127 s cumulés, sans un recul), et
   c'est maintenant le **seul** mouvement monotone du tableau — pendant que les
   quatre étapes instrumentées, elles, reculent toutes ensemble.
6. ⓘ **Faut-il un champ de bilan de purge au registre ?** (question n° 7
   d'hier.) ⚠️ **Ce matin répond pour elle** : avec `lignes_effacees` et
   `tranches` au registre, le compteur de KAN-5 serait à 3/3 ce soir au lieu
   d'attendre une lecture de journal. C'est la seule des questions ouvertes à
   laquelle ce run incomplet apporte un argument neuf.
7. ⓘ **Le cri de position : à front ou à état ?** (question du 01/10.) Et
   **faut-il un motif Jira pour une panne de canal** ? (question du 30/09.)

**Ce que la surveillance fera demain matin, dans cet ordre :**

8. ⛔ **Lire le bloc purge de la nuit du 08→09** (journal du 09/10), **avant**
   la nuit nouvelle : c'est lui qui décide si le compteur de KAN-5 passe à
   **3 / 3** — et donc si la question de la fermeture est posée à Yann.
9. ⛔ **Rattraper les trois commentaires Jira non faits** (KAN-4 : le jalon
   retombe de 73 Mo et le coût par ligne rentre à 1 684,4, ce qui **démentit
   le commentaire du 08/10** ; KAN-5 : la nuit propre et le compteur ;
   KAN-3 : la marge reprend 0,44 point, correction du plateau « au plus
   mauvais endroit »). ⓘ Pour KAN-4 et KAN-5 le contrôle aura peut-être déjà
   pris le jeton du jour : alors **`bw_jira_commenter <CLÉ>`**, le canal
   délibéré, comme arbitré le 07/10.
10. ⛔ **Déposer le miroir git de CETTE note** (`notes-projet/verdict-pente-09-10.md`)
    en même temps que celle du 10/10. Elle est pour l'instant **sans filet**.
11. ⚠️ **Les témoins du mélange** : deux nuits non lues d'affilée feraient
    perdre la série du gain contre la moyenne **uniforme**
    (6,0 → 4,9 → 4,8 → 3,1 %), la seule qui reculait encore.
12. **La mémoire** : 1 684,4 confirme-t-il, ou était-ce le symétrique du
    1 720,6 ? La fourchette fait maintenant **1 671–1 721**.
13. **La durée** : la marge continue-t-elle de remonter depuis 35,90 % ?
14. `mutations_memoire` : 3 mutations non vues, dette antérieure, non
    revérifiée.

---
ⓘ Miroir git déposé le **11/10/2026** par la routine du jour, depuis
`claude/verdict-pente-09-10.md` lu par `project_read` et **repris tel quel**.
Le Mac s'étant déconnecté les 09 et 10/10, cette note est restée deux jours
sans filet.
