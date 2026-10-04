# Verdict de pente du 04/10/2026 — la purge atteint 5/3, la mémoire MONTE (le « plate » du 01/10 est démenti), la durée est revenue, et deux trous de surveillance s'ouvrent

## 19:58 — routine Balise Watch (tirée à 17:51 UTC pour 07:00 ; ~11 h de retard), lecture seule sur le VPS + deux commentaires Jira

**Étape 0 faite, et elle a trouvé quelque chose.** `git log --oneline
--since=midnight` : **aucun commit du jour**, ni dans
`balise-watch-server` (dernier : `cd59edf`, 01/10) ni dans le dépôt
principal (dernier : `10bb605`, 01/10). `project_read` de
`claude/verdict-pente-04-10.md` → « No doc ». Rien à fusionner, rien à ne
pas refaire. `notes-projet/README.md` relu.

⛔ **Mais le contexte d'ouverture ne liste NI `verdict-pente-02-10.md` NI
`verdict-pente-03-10.md`**, et `notes-projet/` n'en porte pas le miroir.
Les jetons `cri.jira.*` étaient encore **tous datés du 01/10 09:15**.
⇒ **la routine n'a pas tourné les 02 et 03/10.** Ce n'est pas une
collision, c'est l'inverse : **deux matinées manquées**. Les deux nuits
sont donc relevées ici (registre pris sur `tail -n 6`, pas `-n 3`), et
leurs chiffres entrent dans les commentaires Jira.

⚠️ **Trois matins de suite hors horaire** : le tir de ce jour est parti à
17:51 UTC pour 07:00. À regarder côté planification de la routine — ce
n'est pas le VPS (le timer `bw-model-controle.timer` a tiré à 07:30:10,
07:30:55 et 07:30:11 les 02, 03 et 04, et `bw-model-score.service` a
tourné les trois nuits).

## 1. Les nuits, bout à bout

| | 29/09 | 30/09 | 01/10 | 02/10 | 03/10 | 04/10 |
|---|---|---|---|---|---|---|
| durée | 5 232 s | 4 992 s | 5 145 s | 4 865 s | 4 944 s | **4 876 s (−68)** |
| garde / marge | 8 100 / 2 868 | 8 100 / 3 108 | 8 100 / 2 955 | 8 100 / 3 235 | 8 100 / 3 156 | **8 100 / 3 224 (+68)** |
| marge en % du garde | 35,4 % | 38,4 % | 36,5 % | 39,9 % | 39,0 % | **39,8 %** |
| `cpu_s` | 4 185,2 | 4 012,9 | 3 962,7 | 3 833,9 | 3 961,3 | **3 964,5 (+3,2)** |
| jalon max | 3 305 Mo | 3 347 Mo | 3 338 Mo | 3 350 Mo | 3 389 Mo | **3 376 Mo (−13)** |
| au-dessus du seuil | +505 | +547 | +538 | +550 | +589 | **+576** |
| swap au pic | 2 329,1 | 2 161,8 | 2 209,3 | 2 111,0 | 2 301,7 | **2 592,1 (+290,4)** |
| pages sorties | 2 454 474 | 2 612 719 | 2 341 013 | 1 963 835 | 2 684 787 | **2 338 891** |
| pic système | 3 601,8 | 3 606,2 | 3 593,6 | 3 606,1 | 3 625,3 | **3 624,7** |
| fenêtre rejouée | 2 073 557 | 2 073 480 | 2 076 504 | 2 079 507 | 2 082 544 | **2 085 523 (+2 979)** |
| o / ligne rejouée | 1 671,3 | 1 692,6 | 1 685,6 | 1 689,2 | 1 706,4 | **1 697,4 (−9,0)** |
| `n_57014` | 2 | 0 | 3 | 2 | 0 | **0** |
| purge (lignes / tranches) | — | 129 666 / 8 | 133 646 / 8 | 131 640 / 8 | 131 657 / 8 | **131 554 / 8** |
| lancement / résultat | timer/success | timer/success | timer/success | timer/success | timer/success | **timer/success** |

Nuit **comparable** (`lancement=timer`, `exec_status=0`, `oom=0`,
05:56:56→07:18:23, `✅ terminé (626 268 lignes écrites en base)`).
Les trois nuits 02, 03 et 04 sont toutes comparables — rien n'est à
écarter.

Contrôle de ce matin **07:30:10, tir régulier** (prochain lundi 05/10
07:30:41) : « **66 relevé(s), 45 comparable(s)** ; durée : 10 points,
pente **−185 s/nuit** ; mémoire : 10 points, pente **−13 Mo/nuit** ;
horizon 30 j ; seuil 2 800 Mo » puis « rien à dire : pente plate/négative,
ou échéance hors horizon ». Il s'est tu sur **les trois** motifs, et il
s'était tu de même les 02 et 03 ⇒ **aucun commentaire Jira de sa part sur
aucune des trois matinées**, la règle « un commentaire par jour et par
motif » ne bloquait rien.

## 2. ✅ Durée : revenue — et le diagnostic du 01/10 est confirmé

`5 145 · 4 865 · 4 944 · **4 876**`. La marge sous le garde remonte à
**3 224 s (39,8 % de 8 100)**, la meilleure depuis le 27/09 après celle du
02/10.

| étape | 01/10 | 02/10 | 03/10 | 04/10 |
|---|---|---|---|---|
| `regime` | 1 592,8 | 1 574,3 | 1 661,4 | **1 624,7** |
| `glissant` | 981,9 | 923,7 | 957,3 | **994,6** |
| `stabilite` | 272,0 | 261,8 | 290,6 | **275,2** |
| `rejeu` | 78,6 | 71,6 | 74,3 | **80,8** |
| somme des quatre | 2 925,3 | 2 831,4 | 2 983,6 | **2 975,3** |

⇒ **L'hypothèse du 01/10 est vérifiée.** Ce matin-là, la durée montait de
+153 s pendant que `cpu_s` baissait de 50 s et que les quatre étapes
chronométrées baissaient de 45,8 s : du temps d'horloge en plus avec du
calcul en moins, soit de l'**attente**, attribuée aux **trois 57014** de
`rpc/bw_character_avance` tombés entre 06:22 et 06:24. Depuis :
`n_57014` fait **3 · 2 · 0 · 0**, et la durée fait
**5 145 · 4 865 · 4 944 · 4 876**. Les deux séries se suivent. Le
découplage temps/volume du 01/10 n'était pas une dérive de calcul, c'était
bien le coût d'expiration répété — et quand les 57014 cessent, la durée
revient. **Rien n'a été déployé entre-temps** : c'est la base qui s'est
calmée, pas le code qui a été corrigé.

`regime` par ligne : **13,39 (01/10) · 13,24 (02/10) · 14,02 (03/10) ·
13,67 ms/ligne (04/10)** pour `lignes_regime` à 118 860 (−357 sur trois
nuits). Pas de tendance : la série oscille autour de 13,6.

⚠️ **KAN-3 n'a PAS été commenté et n'a PAS été rouvert.** La consigne est
de commenter *quand la durée augmente* : elle **baisse** (−68 s sur la
nuit, −269 s depuis le 01/10). La pente du contrôle est à **−185 s/nuit**
et `controle_quotidien.proposition()` **n'a rien formulé** ⇒ **aucune
remontée du chien de garde n'est proposée**, et `10-timeout-s3.conf` n'a
pas été touché. Rappel utile quand même : cette pente est le **25e centile
des différences**, elle ignore par construction les deux plus grosses
hausses — c'est pourquoi elle n'avait pas vu le +153 s du 01/10 et ne
verrait pas davantage le prochain.

## 3. ⚠️ Mémoire : la série MONTE — le « plate » du 01/10 est démenti

Les trois franchissements de cette nuit, tous au-dessus du seuil de 2 800 :

```
⛔ après le rejeu d'archive            : 3 004 Mo  (3 035 le 03, 3 006 le 02)
⛔ après le score par régime           : 2 813 Mo  (2 817 le 03, 2 866 le 02)
⛔ après l'oubli de la fenêtre rejouée : 3 376 Mo  (3 389 le 03, 3 350 le 02)  ← jalon max
```

Jalon max **3 376 Mo**, **576 Mo au-dessus du seuil**, deuxième plus haut
de la série derrière le 3 389 de la veille. Coût par ligne rejouée, la
mesure qui neutralise la croissance de la fenêtre :

```
29/09 1 671,3 o · 30/09 1 692,6 · 01/10 1 685,6
02/10 1 689,2  · 03/10 1 706,4 · 04/10 1 697,4     → +11,8 o/ligne en 3 nuits (+0,70 %)
```

⛔ **La note du 01/10 concluait « plate, pas en baisse ». Trois nuits plus
tard, ce n'est plus vrai : elle monte.** Vérification à taux constant — la
fenêtre a grandi de **+2 979 balise-jours** (2 085 523) :

- au taux du **03/10** (1 706,4 o/ligne) elle aurait rendu **3 393,8 Mo** ;
  elle en a rendu **3 376**, soit **−17,8 Mo** ;
- au taux du **01/10** (1 685,6 o/ligne) elle aurait rendu **3 352,5 Mo** ;
  elle en a rendu **23,5 Mo de plus**.

⇒ la baisse d'hier à aujourd'hui est du **bruit DANS une hausse de fond**.
C'est exactement le piège du 29/09 (« mirage de baisse ») vu par l'autre
bout : un delta d'une nuit ne dit rien, la pente par ligne sur trois nuits
dit quelque chose.

⛔ **Swap : pic 2 592,1 Mo, +290,4 en une nuit et RECORD de toute la série
suivie** (précédent : 2 518,2 le 28/09). Et ce n'est pas un échange
« moins haut, plus longtemps » comme le 01/10 : **2 338 891 pages sorties**
(contre 1 963 835 le 02 et 2 684 787 le 03) et pic système **3 624,7 Mo**,
tous deux dans le haut de la série. Le plancher de swap d'environ 2,2 Go
n'est pas seulement toujours là : **il se creuse**. La condition de
fermeture « swap au pic ≈ 0 » est plus loin qu'il y a une semaine.

⚠️ **Le silence du contrôle n'est pas un acquittement, et il se dégrade.**
Sa pente mémoire passe de **−30** (quatre matinées), à **−24** (01/10), à
**−13 Mo/nuit** aujourd'hui : elle **remonte vers zéro pendant que le
jalon monte**. Étant le 25e centile des différences, elle ignore par
construction les deux plus grosses hausses de la fenêtre — donc le +39 Mo
du 03/10 et le +12 du 02/10 ne peuvent pas y apparaître. Silence
**inertiel**.

Le remède reste la **ligne en tuple** (§2.6, ≈ −1 030 o/ligne cumulés),
avec la mesure `tuple` vs `namedtuple` à la sonde AVANT de choisir
(leçon §2.3). ⚠️ Rappel de l'échec de l'élagage de `units` (−124 Mo au
lieu de −1 500) : les gains sont dans la **structure**, pas dans le nombre
de clés. **Rien n'est décidé, rien n'est codé, et rien n'est déployé côté
mémoire depuis `af25efb` (21/09)** — c'est la quatorzième nuit sans
levier.

## 4. ✅✅✅ Purge : cinq nuits propres d'affilée — **5 / 3**

```
30/09 07:21  → purge model_score_zone : 129 666 ligne(s) effacée(s) en 8 tranche(s)
01/10 07:24  → purge model_score_zone : 133 646 ligne(s) effacée(s) en 8 tranche(s)
02/10 07:19  → purge model_score_zone : 131 640 ligne(s) effacée(s) en 8 tranche(s)
03/10 07:18  → purge model_score_zone : 131 657 ligne(s) effacée(s) en 8 tranche(s)
04/10 07:18  → purge model_score_zone : 131 554 ligne(s) effacée(s) en 8 tranche(s)
             ⓘ purge model_character : rien avant le 2027-02-04 (première écriture
               2026-08-08, rétention 180 j) — aucune requête lancée.
             ✅ terminé (626 268 lignes écrites en base)
```

Les six points de l'attendu, vérifiés un par un sur **chacune des trois
nuits nouvelles** :

- **8 tranches, une par régime, toutes réussies** — aucune ligne
  `⚠️ purge model_score_zone (?as_of=eq.J&regime=eq.R) : HTTP 500 57014`.
- **Nombre de lignes effacées lisible** chaque nuit (`Content-Range` de
  chaque `DELETE`). **Aucun `?`**.
- **Aucune tranche sans `&regime=`** ⇒ le code du VPS n'a pas été écrasé
  par un ancien.
- **Aucun `⚠️ compte model_score_zone : HTTP 500`** : le `HEAD count=exact`
  sur `as_of < seuil` a bien disparu.
- **Aucun `des lignes RESTENT (plus vieille journée : J)`** — la seule
  phrase qui dirait qu'il reste quelque chose. Rien ne reste en base.
- **8 tranches, pas 540 `DELETE` à vide** : plus de repli aveugle sur
  `seuil − 60 j`.

Le volume est **stable autour de 131 600** sur les trois dernières nuits.
⇒ **Décompte : 5 / 3.** `e83d814` tient. La barre posée — trois nuits
consécutives sans 57014 dans le bloc purge **et** un nombre de lignes
effacées lisible — est franchie, et largement.
**KAN-5 reste ouvert : sa fermeture est SOUMISE à Yann** (§7, §10).

## 5. ✅ `n_57014` : deux nuits à zéro, et aucun dans la purge

```
02/10  06:15:05  ⚠️ rpc/bw_character_avance : HTTP 500 {"code":"57014", … statement timeout} — reprise 1/3
02/10  06:21:09  ⚠️ rpc/bw_character_avance : HTTP 500 {"code":"57014", … statement timeout} — reprise 1/3
03/10            (aucun)
04/10            (aucun)
```

Série : **1 (28/09) · 2 (29/09) · 0 (30/09) · 3 (01/10) · 2 (02/10) ·
0 (03/10) · 0 (04/10)**, et auparavant 10/09, 16/09. Les deux du 02/10
sont **tous les deux** sur `rpc/bw_character_avance`, chacun **repris une
fois et réussi** (« reprise 1/3 », jamais 2/3 ni 3/3), et **aucun dans le
bloc purge** : dossier « base sous tension », pas KAN-5.

⚠️ **Deux nuits à zéro ne sont pas un correctif.**
`model-verif/diagnostic_base_sous_tension_2026-09-29.sql` (lecture seule,
9 blocs, SQL Editor) **n'a toujours pas été joué**, et le plan à balayage
séquentiel sur des statistiques périmées n'a pas bougé. La nuit calme du
30/09 avait déjà été suivie du record de 3 le 01/10 : c'est une base qui
respire par à-coups, pas une base réparée. Elle **se compte et se signale
sans dramatiser**, et elle reste la cause probable du prochain pic de
durée.

## 6. ⛔ Position : deux trous de surveillance, et une échéance au 07/10

### 6.1 — Le cri est bien « à front », et c'est maintenant démontré

```
02/10 05:59:46  ⛔ position : 15 balise(s) divergent du gel (10 j lus), dont 2 CONFIRMÉE(S)
02/10 05:59:46  ⛔ position : 2 balise(s) CONFIRMÉE(S) — cri déposé pour envoi
02/10 07:19:46  msmtp … recipients=biozarb@gmail.com … exitcode=EX_OK
02/10 07:19:46  ⚠️ push non parti (webhook)
03/10 05:57:13  ⛔ position : 15 balise(s) … dont 2 CONFIRMÉE(S)      ← aucun cri
04/10 05:58:12  ⛔ position : 15 balise(s) … dont 2 CONFIRMÉE(S)      ← aucun cri
```

Le 01/10, `pioupiou:1333` était à **9 j** ; le 02/10 elle franchit **10 j**
et rejoint `pioupiou:2171` ⇒ le compte de CONFIRMÉES passe de 1 à 2,
**c'est un front**, et le cri part. Les 03 et 04, toujours 2 CONFIRMÉES,
**même nombre** ⇒ **silence**. La conclusion posée le 01/10 (« le canal
est à front, pas à état ») est **vérifiée dans les deux sens** : il crie
quand le compte change, il se tait quand il stagne, quelle que soit la
gravité. **Une balise qui reste confirmée ne recrie pas** : si le mail du
02/10 est passé inaperçu, rien ne le redit.

### 6.2 — ⛔ Le webhook est cassé : **0 / 2**

Le 30/09 (premier vrai cri) : `⚠️ push non parti (webhook)`.
Le 02/10 (deuxième) : `⚠️ push non parti (webhook)`, **tandis que le mail
partait proprement** (`msmtp … smtpstatus=250 … exitcode=EX_OK`).
**Deux tentatives, deux échecs.** Ce n'est plus un incident isolé : le
canal d'urgence `push` est **en panne confirmée**, et seul le mail porte
encore les ⛔. Le webhook n'a jamais été « éprouvé » depuis le 23/09 ; il
est maintenant éprouvé — et il échoue.

ⓘ `bw_avertir_config` n'a rien crié (`cri.BW_MODEL_SCORE_PING_URL` reste
daté du 01/09) : **la variable `BW_WEBHOOK_URL` est donc bien présente**.
L'échec est au `POST`, pas à la configuration. Rien n'a été testé ici
(hors périmètre : aucune écriture hors Jira).

### 6.3 — ⛔ Onze balises vont franchir 10 j ensemble le 07/10

L'effectif tient à **15** depuis trois nuits, mais la cohorte **vieillit
d'un jour par nuit, en bloc** :

| balise | 02/10 | 03/10 | 04/10 | 10 j le |
|---|---|---|---|---|
| `pioupiou:1333` (87 693 m) | **10 j** | **10 j** | **10 j** | CONFIRMÉE |
| `pioupiou:2171` (38 925 m) | **10 j** | **10 j** | **10 j** | CONFIRMÉE |
| `infoclimat:STATIC0491` (1 159 m) | 5 j | 6 j | **7 j** | **07/10** |
| `pioupiou:1344` (1 050 m) | 5 j | 6 j | **7 j** | **07/10** |
| `pioupiou:2026` (1 038 m) | 5 j | 6 j | **7 j** | **07/10** |
| `pioupiou:1746` (914 m) | 5 j | 6 j | **7 j** | **07/10** |
| `pioupiou:1691` (833 m) | 5 j | 6 j | **7 j** | **07/10** |
| `pioupiou:1338` (596 m) | 5 j | 6 j | **7 j** | **07/10** |
| `pioupiou:1388` (592 m) | 5 j | 6 j | **7 j** | **07/10** |
| `pioupiou:1618` (473 m) | 5 j | 6 j | **7 j** | **07/10** |
| `pioupiou:2047` (391 m) | 5 j | 6 j | **7 j** | **07/10** |
| `pioupiou:2125` (374 m) | 5 j | 6 j | **7 j** | **07/10** |
| `pioupiou:2052` (266 m) | 5 j | 6 j | **7 j** | **07/10** |
| `pioupiou:1354` (1 847 m) | 2 j | 3 j | **4 j** | 10/10 |
| `pioupiou:1334` (61 156 m) | 2 j | 2 j | **2 j** | compteur réarmé |

⇒ **le 07/10 au matin, le compte de CONFIRMÉES passera de 2 à 13.** C'est
un front, donc **le cri partira** — par mail seulement si le webhook n'est
pas réparé d'ici là. Onze des treize sont à moins de 1 200 m de leur gel
(simple changement de maille AROME) ; les deux grosses (87,7 km et
38,9 km) sont les candidates « AUTRE balise ».

Le contrôle **ne corrige rien** (règle de `freeze_balises.geler`) :
**geste attendu de Yann** — trancher, pour chaque cas, correction de
coordonnées **ou** AUTRE balise, puis poser `position_suspecte` +
`position_note` sur `station_zone` par `.sql`. Il y a **trois nuits** pour
le faire avant que la liste ne passe à 13.

## 7. Tickets — deux commentaires, aucune transition, aucune création

États relevés **avant** d'écrire (GET `/rest/api/3/issue/…`, HTTP 200) :

| ticket | motif | statut | `statusCategory` | maj avant ce soir | commentaires |
|---|---|---|---|---|---|
| KAN-3 | `bw-pente-duree` | **Terminé** | `done` | 01/10 09:15 | 16 |
| KAN-4 | `bw-pente-memoire` | **À faire** | `new` | 01/10 09:15 | 25 |
| KAN-5 | `bw-purge-57014` | **À faire** | `new` | 01/10 09:15 | 8 |

Les trois jetons `cri.jira.*` étaient datés du **01/10** ⇒ confirmation
indépendante que **rien n'a été commenté les 02, 03 et 04/10**, ni par la
routine ni par le contrôle de 07:30.

- **KAN-4 (`bw-pente-memoire`)** — **laissé OUVERT**, **commenté**
  (`bw_jira_signaler`, HTTP 201 → **26 commentaires**). Les trois
  conditions de fermeture : jalon mesurablement retombé → **NON**
  (3 376 Mo, 576 au-dessus, **coût par ligne en hausse de +11,8 o sur
  trois nuits**) ; swap au pic ≈ 0 → **NON** (2 592,1 Mo, **record de la
  série**) ; contrôle muet → oui, mais **−13 Mo/nuit** contre −24 puis
  −30 : silence **inertiel qui se dégrade**. Le commentaire porte les
  trois franchissements des trois nuits, la courbe par ligne, les deux
  calculs à taux constant (−17,8 Mo au taux du 03/10, **+23,5 au taux du
  01/10**), et la correction explicite de la note du 01/10 : **la série
  monte, elle n'est pas plate**.
- **KAN-5 (`bw-purge-57014`)** — **laissé OUVERT**, **commenté**
  (HTTP 201 → **9 commentaires**). Le commentaire porte le bloc purge des
  cinq nuits, les six points vérifiés sur chacune des trois nuits
  nouvelles, le décompte **5 / 3**, et la nuance : `n_57014 = 2` le 02/10
  **mais aucun dans la purge** (les deux sur `rpc/bw_character_avance`).
  Il se termine en soumettant la fermeture à Yann. **Aucune transition
  jouée.**
- **KAN-3 (`bw-pente-duree`, Terminé)** — **NON rouvert et NON commenté**,
  et c'est délibéré : la consigne est de commenter *quand la durée
  augmente*, or elle **baisse** (−68 s sur la nuit, −269 s depuis le
  01/10), la pente du contrôle est à −185 s/nuit et `proposition()` n'a
  rien formulé. Son jeton `cri.jira.bw-pente-duree` reste au **01/10**,
  intact. ⓘ Rappel pour la prochaine fois : `bw_jira_chercher` filtre sur
  `statusCategory != Done`, donc `bw_jira_signaler bw-pente-duree`
  **créerait un ticket neuf** au lieu de commenter KAN-3 — il faut un
  `POST /rest/api/3/issue/KAN-3/comment` direct, comme le 01/10.
- **Aucun motif neuf créé.** `bw-regime-sensibilite` reste en veille et la
  condition du 29/09 est définitivement non remplie (`regime` oscille,
  13,39 → 13,24 → 14,02 → 13,67 ms/ligne, sans tendance). Les 57014 de
  `rpc/bw_character_avance` restent rattachés au dossier « base sous
  tension ». Le cri de position et la panne du webhook **ne sont pas de la
  dérive** (partage des canaux en tête de `bw_jira.sh` : Jira = dérive ;
  mail + push = les ⛔) — d'où la question n° 3 du §10, posée et non
  tranchée.

Vérification après écriture (GET, HTTP 200) : **KAN-3 Terminé/`done`,
16 commentaires, maj 01/10** · **KAN-4 À faire/`new`, 26 commentaires,
maj 04/10 19:56** · **KAN-5 À faire/`new`, 9 commentaires, maj 04/10
19:56**. Jetons après écriture : `bw-pente-memoire` = 2026-10-04,
`bw-purge-57014` = 2026-10-04, `bw-pente-duree` = **2026-10-01** (intact).
⛔ Aucun ticket fermé, aucune transition jouée, aucun ticket créé.

## 8. Hors périmètre, relevé sur la nuit du 03→04

- ⚠️ **Écarts au recalcul indépendant : 4** (6 le 03, 6 le 02, 6 le 30,
  6 le 01) — toujours **tous en `fcstagrume`**, et toujours le même motif
  (« 0 h appariées ici (< 6) mais la base porte une ligne », une fois
  « 1 h » le 03/10). **Les balises sont neuves chaque nuit** :
  `aemet:9244X`, `mf:74105002`, `pioupiou:984`, `windsmobi:ffvl-5110` ce
  matin, aucune reprise du 02 ni du 03. Ce n'est **pas un lot figé de
  balises fautives**, c'est un motif d'appariement qui frappe au hasard
  dans `fcstagrume`. 14 balise-jours comparés, 6 sous le seuil de 6 h.
- `lignes_daily` **69 852** (69 960 le 03, 69 830 le 02, 69 800 le 01) —
  stable. `lignes_glissant` **10 674** (−24).
- Observations du jour : **3 739 balises** (veille 3 745) — premier reflux
  après trois nuits à 3 745/3 746.
- Stabilité des rangs : **`tau = 0,797` sur 57 cases** (0,816 sur 60 le
  03 ; 0,809 sur 56 le 02).
- Témoins : part du site **15,3 pts** (17,3 le 01), part secteur+heure
  **9,2 pts** (11,0), mélange **+5,0 %** vs meilleur membre a priori
  (devant dans **55,7 %** des cas) et **+3,5 %** vs uniforme. Le mélange
  **reste au-dessus** du seuil du « devant une fois sur deux » les trois
  nuits (56,4 % · 53,2 % · 55,7 %).
- Référence combinée : médiane **`k = 0,129`** (0,130 le 03, 0,126 le 02,
  0,124 le 01) sur 3 705 balises / 3 817 climatologisées ; **366** balises
  avaient un ρ hors [0, 1] ramené à la borne (380 le 01 — amélioration qui
  se tient).
- Murphy : **66 628** cases, dont **64 456** décomposées, **266** balises
  dehors (inchangé depuis le 01/10).
- FDR : 6 948 tests, 1 988 survivants à BH α=0,1 (brut) ; 6 622 / 1 461
  (corrigé) — 80 et 109 rangs retirés.
- ⓘ R2 : **4 écritures**, plafond 10, **157,9 Mo** — rien près du plafond
  les trois nuits (158,2 le 02, 157,7 le 03).
- `mutations_memoire` : **aucune ligne** au journal des trois nuits ;
  dette antérieure de **3 mutations non vues** (2, 5, 13), inchangée.
- Duel apparié : 65 094 lignes lues en lead 6 (1 349 retirées), 23 965 en
  lead 24 (521 retirées). `agrume_pi ↔ bw_mix` +6 h : médiane **+0,380**
  → `b_better` ; +24 h : **+0,515** → `b_better`.
- Manches : **37 nuits** suivies depuis le 24/08, **648 cases**
  zone×lead×modèle avec au moins une manche gagnée.
- 9 balises nées sous leur identifiant (`notee_depuis`, lot L15-bis),
  toutes du 25/09 — inchangé depuis dix nuits.

## 9. Ce qui a été touché

**VPS** : rien hors les **deux** commentaires Jira. `tail -n 6` du
registre, `journalctl` (notation sur 02→04 et contrôle sur 02→04, **sans
élévation de droits : les lignes utiles sont lisibles par `debian`**),
`list-timers`, `controle_quotidien.py --verbeux`, lecture de
`bw_jira.sh`, **six GET Jira** (trois avant écriture, trois après
vérification), listage et lecture du dossier de jetons
`~/.balise-watch-etat-alertes`. **Aucun `systemctl start/restart/
daemon-reload`, aucun `enable`, aucun SQL joué, aucun `rsync`, rien écrit
dans `~/balise-watch` ni dans `/etc`.** Écritures : les deux textes de
KAN-4 et KAN-5 par `bw_jira_signaler` (qui travaille dans un `mktemp -d`
en 700 effacé après), et les **deux jetons `cri.jira.<motif>` du jour**.
`~/.balise-watch-alertes.env` **sourcé**, jamais lu par valeur ;
`curl -K -`, jamais `-u`. Les deux scripts passés au VPS l'ont été par
`ssh 'bash -s' <` depuis le Mac — **rien n'a été déposé sur le VPS**.
**Mac** : cette note et son miroir git, plus deux scripts jetables dans
`/Users/yann/` (hors dépôt) — **pas de `git push`**.

## 10. Ce qui reste — et ce qui demande Yann

1. ✅ **LA PURGE EST À 5 / 3 : faut-il fermer KAN-5 ?** Cinq nuits
   consécutives (30/09 → 04/10), 8 tranches et un nombre lisible chaque
   nuit, zéro 57014 dans le bloc purge, zéro `?`, zéro
   `des lignes RESTENT`. `e83d814` tient. La barre est franchie et
   largement ; **la fermeture te revient**, aucune transition n'a été
   jouée. (Si tu veux la jouer : API v3, `curl -K -`, même façon que le
   10/09 sur KAN-5.)
2. ⛔ **LE WEBHOOK `push` EST CASSÉ : 0 / 2.** Échec le 30/09, échec le
   02/10, pendant que le mail partait proprement (`exitcode=EX_OK`). La
   variable est présente (pas de cri de `bw_avertir_config`), donc c'est
   le `POST` qui échoue. Deux questions, posées depuis le 30/09 et
   toujours sans réponse : veux-tu qu'une session éprouve
   `BW_WEBHOOK_URL` par un `curl` de test **hors run**, ou préfères-tu
   regarder toi-même ? Et faut-il un motif Jira pour une panne de canal,
   alors que `bw_jira.sh` réserve Jira à la dérive ?
3. ⛔ **ONZE BALISES FRANCHISSENT 10 j LE 07/10** → le compte de
   CONFIRMÉES passera de **2 à 13**, le cri partira (c'est un front),
   **par mail seulement** si le webhook n'est pas réparé d'ici là. Trois
   nuits pour trancher les 15 cas : correction de coordonnées **ou** AUTRE
   balise, puis `position_suspecte` + `position_note` sur `station_zone`
   par `.sql`. Onze des quinze sont à moins de 1 200 m (changement de
   maille) ; `pioupiou:1333` (87,7 km) et `pioupiou:2171` (38,9 km) sont
   les candidates « AUTRE balise ».
4. ⛔ **LE CRI DE POSITION EST « À FRONT », C'EST MAINTENANT DÉMONTRÉ**
   (crie le 02/10 quand le compte passe de 1 à 2, se tait les 03 et 04 à
   compte égal). Question du 01/10, toujours ouverte : veux-tu que le
   garde-fou **recrie** tant qu'une balise reste confirmée (même motif,
   une fois par jour), ou qu'il se taise comme aujourd'hui ?
5. ⚠️ **LA MÉMOIRE (KAN-4) MONTE, et la note du 01/10 est corrigée.**
   Jalon **3 376 Mo** (576 au-dessus) ; coût par ligne **+11,8 o en trois
   nuits** ; swap au pic **2 592 Mo = record de la série**. Ce n'était pas
   « plate » : c'était le début d'une hausse. **Aucun levier déployé
   depuis le 21/09** (14 nuits) : décider la **ligne en tuple**, après la
   mesure `tuple` vs `namedtuple` à la sonde.
6. ⛔ **LE DOSSIER « BASE SOUS TENSION » reste le levier de la durée.**
   `diagnostic_base_sous_tension_2026-09-29.sql` (lecture seule, 9 blocs)
   **attend toujours d'être joué dans le SQL Editor** ; les correctifs
   candidats (ANALYZE / VACUUM / autovacuum par table) y sont en
   commentaire. Deux nuits à `n_57014 = 0` ne sont pas un correctif : le
   30/09 était déjà à 0 et le 01/10 a battu le record à 3.
7. ✅ **LA DURÉE (KAN-3) : rien à décider, et une hypothèse confirmée.**
   4 876 s, marge 3 224 s (39,8 %), pente −185 s/nuit. Le +153 s du 01/10
   était bien l'attente des trois 57014 : les deux séries se suivent
   (`n_57014` 3·2·0·0 ↔ durée 5 145·4 865·4 944·4 876). KAN-3 reste
   **Terminé**, **non commenté** cette fois. Si la durée remonte, c'est le
   point 6 qu'il faudra ouvrir, pas le garde.
8. ⚠️ **LA ROUTINE A MANQUÉ LES 02 ET 03/10**, et le tir de ce jour est
   parti à 17:51 UTC pour 07:00. Le VPS, lui, a tourné les trois nuits et
   le contrôle a tiré à l'heure les trois matins : **le trou est du côté
   de la planification de la routine**, pas du serveur. Trois matinées de
   suite hors horaire méritent un coup d'œil.
9. ⚠️ **Écarts au recalcul : 4, toutes balises neuves** — le motif
   d'appariement `fcstagrume` frappe au hasard, ce n'est pas un lot figé.
   Dette ancienne, à resurveiller.
10. `mutations_memoire` : 3 mutations non vues (dette antérieure).
