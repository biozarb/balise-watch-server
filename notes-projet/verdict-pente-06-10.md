# Verdict de pente du 06/10/2026 — la durée BONDIT de 336 s en CALCUL (cpu_s +310) à volume de régime en baisse, la mémoire RECULE de 53 Mo et rend la « hausse de fond » des quatre nuits, la purge REPART À ZÉRO (un 57014 revient dans le bloc après six nuits propres), et la cohorte des onze balises S'EFFONDRE : le front du 07/10 sera 2 → 4, pas 2 → 13

## 13:35 (Paris) — routine Balise Watch (tirée à 11:17 UTC pour 07:07 ; ~4 h 10 de retard), lecture seule sur le VPS + deux commentaires Jira

**Étape 0 faite, et elle est nette.** `git log --oneline --since=midnight` :
**aucun commit du jour**, ni dans `balise-watch-server` (dernier :
`3119a04`, 05/10) ni dans le dépôt principal (dernier : `ce4c5a6`,
05/10). `project_read` de `claude/verdict-pente-06-10.md` → « No doc » ;
`claude/verdict-pente-05-10.md` lu en entier. `notes-projet/README.md`
relu. États Jira relevés par GET **avant** toute écriture. ⇒ **premier et
seul run du jour, rien à fusionner, rien à ne pas refaire.**

⚠️ **Cinquième matin de suite hors horaire** : tir à 11:17 UTC pour 07:07
(hier 08:56 pour 07:07 ; avant-hier 17:51 pour 07:00 ; aucun tir les 02 et
03/10). Le VPS, lui, est à l'heure : `bw-model-controle.timer` a tiré à
**07:30:52** (prochain mercredi 07/10 07:30:52) et `bw-model-score.service`
a tourné de **05:58:41 à 07:24:47**. **Le décalage est côté planification
de la routine**, pas serveur. Cinq matins, ça ne se répare pas tout seul.

## 1. Les nuits, bout à bout

| | 01/10 | 02/10 | 03/10 | 04/10 | 05/10 | 06/10 |
|---|---|---|---|---|---|---|
| durée | 5 145 s | 4 865 s | 4 944 s | 4 876 s | 4 821 s | **5 157 s (+336)** |
| garde / marge | 8 100 / 2 955 | 8 100 / 3 235 | 8 100 / 3 156 | 8 100 / 3 224 | 8 100 / 3 279 | **8 100 / 2 943 (−336)** |
| marge en % du garde | 36,5 % | 39,9 % | 39,0 % | 39,8 % | 40,5 % | **36,3 %** |
| `cpu_s` | 3 962,7 | 3 833,9 | 3 961,3 | 3 964,5 | 3 853,3 | **4 163,6 (+310,3)** |
| jalon max | 3 338 Mo | 3 350 Mo | 3 389 Mo | 3 376 Mo | 3 417 Mo | **3 364 Mo (−53)** |
| au-dessus du seuil | +538 | +550 | +589 | +576 | +617 | **+564** |
| swap au pic | 2 209,3 | 2 111,0 | 2 301,7 | 2 592,1 | 2 218,3 | **2 175,5 (−42,8)** |
| pages sorties | 2 341 013 | 1 963 835 | 2 684 787 | 2 338 891 | 2 579 457 | **2 507 693 (−71 764)** |
| pic système | 3 593,6 | 3 606,1 | 3 625,3 | 3 624,7 | 3 600,5 | **3 619,1 (+18,6)** |
| fenêtre rejouée | 2 076 504 | 2 079 507 | 2 082 544 | 2 085 523 | 2 086 473 | **2 087 575 (+1 102)** |
| o / ligne rejouée | 1 685,6 | 1 689,2 | 1 706,4 | 1 697,4 | 1 717,3 | **1 689,3 (−28,0)** |
| `n_57014` | 3 | 2 | 0 | 0 | 0 | **2 (les deux dans la purge)** |
| purge (lignes / tranches) | 133 646 / 8 | 131 640 / 8 | 131 657 / 8 | 131 554 / 8 | 125 782 / 8 | **124 678 / 8** |
| lancement / résultat | timer/success | timer/success | timer/success | timer/success | timer/success | **timer/success** |

Nuit **comparable** : `lancement=timer`, `exec_status=0`, `oom=0`,
`result=success`, 05:58:41 → 07:24:47, `✅ terminé (624 745 lignes écrites
en base)` (642 068 hier). Rien à écarter.

Contrôle de ce matin, **tir régulier 07:30:52** : « **68 relevé(s),
47 comparable(s)** ; durée : 10 points, pente **−68 s/nuit** ; mémoire :
10 points, pente **−13 Mo/nuit** ; horizon 30 j ; seuil 2 800 Mo ». Il a
crié sur **un seul motif, `bw-purge-57014`**, et il a **commenté KAN-5
lui-même à 07:30:54**. Muet sur la durée et sur la mémoire.

## 2. ⛔ Durée : +336 s, et pour la première fois c'est du CALCUL

`4 944 · 4 876 · 4 821 · **5 157**`. La marge tombe à **2 943 s = 36,3 %
de 8 100** (40,5 % hier, le meilleur de la série). Et surtout :
**`cpu_s` monte de 310,3 s** pour +336 s de durée — **92 % de la hausse
est du calcul**.

| étape | 03/10 | 04/10 | 05/10 | 06/10 |
|---|---|---|---|---|
| `regime` | 1 661,4 | 1 624,7 | 1 643,3 | **1 820,0 (+176,7)** |
| `glissant` | 957,3 | 994,6 | 929,8 | **1 002,0 (+72,2)** |
| `stabilite` | 290,6 | 275,2 | 288,2 | **328,8 (+40,6)** |
| `rejeu` | 74,3 | 80,8 | 74,0 | **81,5 (+7,5)** |
| somme des quatre | 2 983,6 | 2 975,3 | 2 935,3 | **3 232,3 (+297,0)** |
| hors étapes | 1 960,4 | 1 900,7 | 1 885,7 | **1 924,7 (+39,0)** |

**Les quatre étapes montent ensemble** et **88 %** des 336 s se retrouvent
dans leur somme. Le reste (+39 s) est hors étapes.

⛔ **Ce n'est pas l'attente du 01/10.** Le +153 s du 01/10 était du temps
d'horloge **sans** calcul (`cpu_s` en **baisse** de 50 s) : trois 57014 sur
`rpc/bw_character_avance` dans la fenêtre. Cette nuit c'est **l'inverse
exact**. Et les **deux** 57014 de la nuit sont **tous les deux dans le bloc
purge** (07:24:00 et 07:24:27), donc **après** la fin des quatre étapes
(`regime` se termine à 07:16:37) : ils **ne peuvent pas** expliquer la
hausse. `rpc/bw_character_avance` n'a rendu **aucun** 57014 cette nuit.

⛔ **Ce n'est pas le volume non plus — le découplage est net, et dans le
sens coûteux :**

| | 05/10 | 06/10 |
|---|---|---|
| `lignes_regime` | 121 418 | **120 779 (−639)** |
| `lignes_score_zone` | 132 089 | **131 391 (−698)** |
| `lignes_glissant` | 10 671 | **10 612 (−59)** |
| `lignes_daily` | 69 726 | **69 902 (+176)** |

Le volume de régime **baisse de 0,5 %** et l'étape `regime` coûte
**10,8 % de plus**. Coût par ligne de `regime` :

```
13,39 (01/10) · 13,24 · 14,02 · 13,67 · 13,53 · 15,07 ms (06/10)
  → 15,07 ms/ligne = le PLUS HAUT de la série suivie, +11,4 % en une nuit
```

Jusqu'ici cette série « oscillait autour de 13,6 sans tendance » (note du
05/10). **15,07 sort de l'oscillation.**

ⓘ Une part de `stabilite` s'explique proprement : `tau` est calculé sur
**65 cases** cette nuit contre **58** hier — plus de cases, plus de
travail. Rien d'équivalent n'explique `regime` ni `glissant`.

⚠️ **`bw-regime-sensibilite` RESTE EN VEILLE** (arbitrage du 29/09). La
condition est « la hausse s'additionne **deux** nuits de suite ». Hier le
coût par ligne **baissait** (13,53 contre 13,67) ; cette nuit il saute à
15,07. Cela fait **une** nuit, pas deux. **Aucun motif neuf créé.** Si la
nuit du 06→07 confirme, **la question revient à Yann** (§10 n° 2).

⚠️ **KAN-3 a été COMMENTÉ, et NON rouvert.** La consigne est de commenter
quand la durée **augmente** : elle augmente de 336 s. `bw_jira_chercher`
filtre sur `statusCategory != Done`, donc un `bw_jira_signaler` aurait
**créé un ticket neuf** : le commentaire est parti par un
`POST /rest/api/3/issue/KAN-3/comment` direct, comme le 01/10. **Statut
inchangé : Terminé / `done`.**

⚠️ **Remontée du chien de garde : AUCUNE proposée.**
`controle_quotidien.proposition()` **n'a rien formulé**, et la marge reste
large (2 943 s = 36,3 % du garde). **`10-timeout-s3.conf` n'a pas été
touché** et ne le sera pas sans Yann.

ⓘ Rappel de méthode, et il compte beaucoup ce matin : la pente du contrôle
est le **25e centile des différences**, elle **ignore par construction les
deux plus grosses hausses** de la fenêtre. Elle affiche **−68 s/nuit**
pendant que la nuit prend +336 s — exactement comme elle n'avait pas vu le
+153 s du 01/10. **Son silence ne vaut pas acquittement.**

## 3. ✅ Mémoire : RECUL de 53 Mo, et la « hausse de fond » des quatre nuits est rendue

Les trois franchissements, tous encore au-dessus du seuil de 2 800 :

```
⛔ après le rejeu d'archive            : 3 002 Mo  (3 023 le 05, 3 004 le 04)
⛔ après le score par régime           : 2 853 Mo  (2 857 le 05, 2 813 le 04)
⛔ après l'oubli de la fenêtre rejouée : 3 364 Mo  (3 417 le 05, 3 376 le 04)  ← jalon max
```

Jalon max **3 364 Mo (−53)**, **564 Mo au-dessus du seuil**. Le record de
3 417 Mo d'hier n'a tenu qu'une nuit.

Coût par ligne rejouée, la mesure qui neutralise la croissance de la
fenêtre :

```
29/09 1 671,3 o · 30/09 1 692,6 · 01/10 1 685,6 · 02/10 1 689,2
03/10 1 706,4  · 04/10 1 697,4 · 05/10 1 717,3 · 06/10 1 689,3
  → −28,0 o/ligne EN UNE NUIT, alors que la fenêtre a GRANDI de 1 102 balise-jours
  → écart au 01/10 : +3,7 o/ligne (il était de +31,7 hier)
```

Vérification à taux constant, dans les deux sens :

- au taux du **05/10** (1 717,3 o/ligne) la nuit aurait rendu
  **3 418,6 Mo** ; elle a rendu **3 364**, soit **−54,6 Mo** ;
- au taux du **01/10** (1 685,6 o/ligne) elle aurait rendu **3 355,8 Mo** ;
  elle a rendu **3 364**, soit **+8,2 Mo**.

⚠️ **Il faut corriger ce que cette note a écrit hier.** Le 04 et le 05/10,
la routine a lu « hausse de fond, quatrième nuit, +31,7 o/ligne depuis le
01/10 » et a dit la lecture « plate » du 01/10 « définitivement démentie ».
Cette nuit **rend presque tout** : l'écart au 01/10 retombe à +3,7 o/ligne.
À huit nuits de recul, la série **oscille autour de 1 695 o/ligne sans
pente nette** — ce n'est pas une baisse non plus. **Quatre points ne font
pas une pente** : c'est la leçon du 28/09, et elle vient de resservir sur
notre propre lecture. Le commentaire du jour sur KAN-4 porte cette
correction explicitement.

**Swap : pic 2 175,5 Mo (−42,8)**, le plus bas depuis le 02/10, avec
**2 507 693 pages sorties (−71 764)** — les deux baissent ensemble, ce qui
est cohérent, contrairement au 05/10 (pic en baisse, pages en forte
hausse). Mais le plancher d'environ **2,2 Go** est toujours là :
**septième nuit de suite au-dessus de 2,1 Go**. Pic système 3 619,1 Mo
(+18,6).

⚠️ **La pente du contrôle redescend : −13 Mo/nuit** (contre −9 hier, −13 le
04, −24 le 01, −30 la semaine dernière). Elle suit le recul du jalon. Reste
qu'étant le 25e centile des différences, elle ignore par construction les
deux plus grosses hausses de la fenêtre : **son silence reste inertiel.**

Le remède reste la **ligne en tuple** (§2.6 de l'enquête, ≈ −1 030 o/ligne
cumulés), avec la mesure `tuple` vs `namedtuple` à la sonde **AVANT** de
choisir (leçon §2.3). ⚠️ Rappel de l'échec de l'élagage de `units`
(−124 Mo au lieu de −1 500) : les gains sont dans la **structure**, pas
dans le nombre de clés. **Rien n'est décidé, rien n'est codé, rien n'est
déployé côté mémoire depuis `af25efb` (21/09)** — **seizième nuit sans
levier.**

## 4. ⛔ Purge : le compteur REPART À ZÉRO — **0 / 3** après six nuits propres

Le bloc purge de la nuit, en entier :

```
07:24:00  ⚠️ purge model_score_zone (?as_of=eq.2026-09-28&regime=eq.fluxW) : HTTP 500
          — {"code":"57014","message":"canceling statement due to statement timeout"} — rejouée dans 5 s
07:24:27  ⚠️ purge model_score_zone : plus vieille journée illisible
          (essai 1/2 : {"code":"57014","message":"canceling statement due to statement timeout"})
07:24:37  → purge model_score_zone : 124 678 ligne(s) effacée(s) en 8 tranche(s)
07:24:37  ⓘ purge model_character : rien avant le 2027-02-04 (première écriture 2026-08-08,
          rétention 180 j) — aucune requête lancée.
07:24:37  ✅ terminé (624 745 lignes écrites en base)
```

**Ce qui a marché, point par point :**

- **La tranche en échec a été rattrapée.** `?as_of=eq.2026-09-28&regime=eq.fluxW`
  expire, est **rejouée après 5 s**, et ne reparaît pas : **8 tranches**
  au compte final, une par régime.
- **124 678 lignes effacées, nombre LISIBLE** (`Content-Range` de chaque
  `DELETE`). **Aucun `?`**.
- **Aucune tranche sans `&regime=`** ⇒ le code du VPS n'a pas été écrasé
  par un ancien.
- **Aucun `⚠️ compte model_score_zone : HTTP 500`** : le `HEAD count` sur
  `as_of < seuil` reste bien parti.
- **Aucun `des lignes RESTENT (plus vieille journée : J)`** — la seule
  phrase qui dirait qu'il reste quelque chose.
- **8 tranches, pas 540 `DELETE` à vide.** `e83d814` tient.

**Ce qui n'a PAS marché, et il faut le dire sans le gonfler :**

- ⛔ **Un 57014 est revenu DANS le bloc purge.** La barre de fermeture est
  « **trois nuits consécutives sans 57014 dans le bloc purge** et un
  nombre de lignes effacées lisible ». Le compteur était à **6 / 3** hier
  soir ; il **repart à 0 / 3** ce matin. Série : 30/09 → 05/10 propres
  (six), **06/10 : un 57014**.
- ⚠️ **Message NOUVEAU, à documenter** :
  `⚠️ purge model_score_zone : plus vieille journée illisible (essai 1/2 : 57014)`.
  Ce n'est **pas** une tranche : c'est la **sonde** qui lit la plus vieille
  journée restante, et elle a expiré au premier de ses deux essais. Aucun
  `essai 2/2` au journal, donc le second essai a abouti.
  ⚠️ **Conséquence à ne pas oublier** : l'absence de
  `des lignes RESTENT` est, cette nuit, **moins concluante** que sur une
  nuit propre — la phrase qui l'aurait dite vient d'une sonde qui a
  bronché. On **ne conclut donc pas** « rien ne reste en base » avec la
  confiance des six nuits précédentes ; on ne conclut pas l'inverse non
  plus. Seul un `select as_of, count(*)` joué par Yann trancherait.
- ⚠️ **Le constat du contrôle sur-lit, lui aussi.** Il a écrit à KAN-5
  « **purge en échec cette nuit** (model_score_zone) … chaque nuit ratée
  double la suivante ». C'est inexact : la purge **a abouti** (8 tranches,
  124 678 lignes). Le contrôle lit la liste `incidents` du registre, qui
  conserve la ligne d'avertissement **même quand le rejeu réussit** — il ne
  voit pas le rattrapage. C'est exactement l'erreur de la note du 28/09,
  côté machine cette fois. ⇒ **à corriger dans `controle_quotidien.py`**
  (§10 n° 5) : un `⚠️ purge … rejouée dans 5 s` suivi d'un
  `→ purge … N ligne(s) effacée(s) en 8 tranche(s)` n'est **pas** un échec.

Volume effacé, nuit après nuit : **133 646 · 131 640 · 131 657 · 131 554 ·
125 782 · 124 678**. Le recul suit le volume de la journée purgée (ici le
**2026-09-28**) — ⚠️ **ce n'est pas un échec de tranche**, et c'est
toujours le genre de chiffre qu'il ne faut pas sur-interpréter.

**KAN-5 reste ouvert, et ce matin la question de sa fermeture se répond
d'elle-même : non.** Posée à Yann les 04 et 05/10, elle est **retirée**
jusqu'à trois nouvelles nuits propres.

## 5. ⚠️ `n_57014 = 2` — les deux dans la purge, aucun sur `rpc/bw_character_avance`

Série : **1 (28/09) · 2 (29/09) · 0 · 3 (01/10) · 2 · 0 · 0 · 0 (05/10) ·
2 (06/10)**, et auparavant 10/09, 16/09.

Les deux de cette nuit sont la **tranche `fluxW` du 2026-09-28** et la
**sonde « plus vieille journée »**, à 27 s d'intervalle, au tout dernier
moment du run. **`rpc/bw_character_avance` n'a rien rendu** — c'est la
première fois qu'un 57014 apparaît dans la purge depuis le 29/09.

⚠️ **Le dossier « base sous tension » redevient urgent.**
`model-verif/diagnostic_base_sous_tension_2026-09-29.sql` (lecture seule,
9 blocs, SQL Editor) **n'a toujours pas été joué**, et le plan à balayage
séquentiel sur des statistiques périmées n'a pas bougé. Ce matin il y a
deux signaux au même endroit : **un timeout dans la purge** et **+176,7 s
sur `regime`** — ce sont deux symptômes possibles d'une même base qui
travaille mal, même si le `cpu_s` en hausse plaide plutôt pour du calcul
côté client. **Les trois nuits à zéro de la semaine n'étaient pas un
correctif** : c'est confirmé une fois de plus.

## 6. ✅⚠️ Position : la cohorte des onze S'EFFONDRE — le front du 07/10 sera **2 → 4**, pas 2 → 13

```
06/10 06:00:06  ⛔ position : 11 balise(s) divergent du gel (10 j lus), dont 2 CONFIRMÉE(S) (≥ 10 j)
                (aucun cri déposé — compte de CONFIRMÉES inchangé depuis le 02/10)
```

**15 divergences hier, 11 cette nuit.** Et surtout : **neuf des onze
balises qui étaient à 8 j ont disparu de la liste** — compteur remis à
zéro, elles se sont réalignées sur leur gel en une seule nuit.

| balise | 04/10 | 05/10 | 06/10 | 10 j le |
|---|---|---|---|---|
| `pioupiou:1333` (87 693 m) | 10 j | 10 j | **10 j** | CONFIRMÉE |
| `pioupiou:2171` (38 925 m) | 10 j | 10 j | **10 j** | CONFIRMÉE |
| `pioupiou:1388` (592 m → **2 363 m**) | 7 j | 8 j | **9 j** | **07/10** |
| `infoclimat:STATIC0491` (1 159 m) | 7 j | 8 j | **9 j** | **07/10** |
| `pioupiou:1378` (15 778 m) | — | — | **1 j** | 15/10 |
| `pioupiou:367` (6 764 m) | — | — | **1 j** | 15/10 |
| `pioupiou:1417` (829 m) | — | — | **1 j** | 15/10 |
| `pioupiou:1375` (747 m) | — | — | **1 j** | 15/10 |
| `pioupiou:1722` (631 m) | — | — | **1 j** | 15/10 |
| `pioupiou:1562` (481 m) | — | — | **1 j** | 15/10 |
| `pioupiou:1678` (422 m) | — | — | **1 j** | 15/10 |
| ~~`pioupiou:1344`, `2026`, `1746`, `1691`, `1338`, `1618`, `2047`, `2125`, `2052`~~ | 7 j | 8 j | **sorties** | compteurs réarmés |
| ~~`pioupiou:1354`~~ (1 847 m) | 4 j | 5 j | **sortie** | compteur réarmé |
| ~~`pioupiou:1334`~~ (61 156 m) | 2 j | 1 j | **sortie** | compteur réarmé (3e fois) |

⇒ ⚠️ **L'échéance annoncée hier est FAUSSE et doit être corrigée** : la
note du 05/10 a écrit « le 07/10 au matin, le compte de CONFIRMÉES passera
de 2 à 13 » et l'a donnée « confirmée à la nuit près ». Il ne reste que
**deux** candidates à 9 j : `pioupiou:1388` et `infoclimat:STATIC0491`.
**Demain matin le compte passera de 2 à 4.** Le cri partira quand même
(c'est un **front**), mais il sera **quatre fois plus petit** que ce que
cette note annonçait.

✅ **Et cet effondrement EST l'argument décisif pour la lecture « maille
AROME ».** Neuf balises à **moins de 1 200 m** de leur gel sont revenues
dans la maille d'un coup : ce n'était pas une dérive de position, c'était
un basculement de maille qui a tenu huit nuits puis s'est défait. ⇒ les
**onze** « changements de maille » du dossier ne demandent probablement
**aucune correction de coordonnées**.

⛔ **Deux cas qui restent, et ils sont d'une autre nature :**

- `pioupiou:1333` (**87,7 km**) et `pioupiou:2171` (**38,9 km**) :
  CONFIRMÉES depuis le 02/10, inchangées, candidates **« AUTRE balise »**.
- ⚠️ `pioupiou:1388` : **592 m hier → 2 363 m cette nuit**, compteur qui
  **continue** (8 → 9 j). Elle est la seule à **s'éloigner** pendant que
  les autres rentrent. Elle sort du lot « maille AROME » et mérite d'être
  regardée pour elle-même.
- `infoclimat:STATIC0491` (1 159 m, distance stable, 9 j) : seule
  rescapée du lot des petites distances, à surveiller demain.

ⓘ `pioupiou:1375` (747 m, nouvelle à 1 j) figure aussi dans les **9 balises
nées sous leur identifiant** de la nuit (`notee_depuis`, lot L15-bis,
naissance 2026-09-25) : une balise neuve qui diverge à 1 j n'est pas la
même chose qu'une balise installée qui dérive.

Le canal reste **à front, pas à état** (démontré dans les deux sens : cri
le 02/10 quand le compte est passé de 1 à 2, silence les 03, 04, 05 et 06 à
compte égal). Une balise qui reste confirmée **ne recrie pas**.

⛔ **Webhook `push` : toujours 0 / 2**, toujours pas éprouvé. Pas de cri
cette nuit, donc pas de nouvelle tentative. `bw_avertir_config` n'a rien
crié (`cri.BW_MODEL_SCORE_PING_URL` toujours daté du 01/09) ⇒ la variable
`BW_WEBHOOK_URL` est présente, l'échec est au `POST`. **Rien n'a été testé
ici** (hors périmètre : aucune écriture hors Jira). ⚠️ **L'urgence de
demain est réelle mais plus petite** : le cri du 07/10 sera le troisième
essai, sur 4 CONFIRMÉES et non 13.

Le contrôle **ne corrige rien** (règle de `freeze_balises.geler`) :
**geste attendu de Yann** — trancher, pour chacun des cas qui restent,
correction de coordonnées **ou** AUTRE balise, puis poser
`position_suspecte` + `position_note` sur `station_zone` par `.sql`. Le
dossier a **beaucoup maigri** ce matin : de 15 cas à 4 qui comptent
(`1333`, `2171`, `1388`, `STATIC0491`), les 7 nouvelles étant à 1 j.

## 7. Tickets — deux commentaires, aucune transition, aucune création, KAN-5 volontairement intouché

États relevés **avant** d'écrire (GET `/rest/api/3/issue/…`, HTTP 200) :

| ticket | motif | statut | `statusCategory` | maj avant | commentaires |
|---|---|---|---|---|---|
| KAN-3 | `bw-pente-duree` | **Terminé** | `done` | 01/10 09:15 | 16 |
| KAN-4 | `bw-pente-memoire` | **À faire** | `new` | 05/10 11:15 | 27 |
| KAN-5 | `bw-purge-57014` | **À faire** | `new` | **06/10 07:30:54** | **11** |

- **KAN-5 (`bw-purge-57014`) — RIEN AJOUTÉ, délibérément.** Le contrôle de
  07:30 l'a **commenté lui-même à 07:30:54** (11e commentaire) ; la règle
  « un commentaire par jour et par motif » interdit d'en remettre un. Le
  compteur de la purge **repart à 0 / 3** et la question de sa fermeture
  est **retirée** jusqu'à trois nouvelles nuits propres. Les nuances du §4
  (la purge a abouti ; la sonde a bronché ; le constat du contrôle sur-lit)
  sont consignées **ici**, pas dans le ticket : elles iront dans le
  commentaire de demain si la nuit est propre.
- **KAN-4 (`bw-pente-memoire`) — laissé OUVERT, commenté**
  (`bw_jira_signaler`, HTTP 201 → **28 commentaires**). Les trois
  conditions de fermeture : jalon mesurablement retombé → **NON** (−53 Mo,
  mais **+564 au-dessus du seuil**, et 3 364 est au milieu de la série
  3 338–3 417 des huit dernières nuits) ; swap au pic ≈ 0 → **NON**
  (2 175,5 Mo, 7e nuit > 2,1 Go) ; contrôle muet → oui, mais pente à
  −13 Mo/nuit, silence **inertiel**. Le commentaire porte les trois
  franchissements, la courbe du coût par ligne, les **deux calculs à taux
  constant**, et **la correction explicite de la lecture des 04 et 05/10**.
- **KAN-3 (`bw-pente-duree`, Terminé) — COMMENTÉ, NON rouvert**
  (`POST /rest/api/3/issue/KAN-3/comment` direct, HTTP 201 →
  **17 commentaires**). La durée **augmente** de 336 s : la consigne
  s'applique. Le commentaire porte les chiffres, la répartition par étape,
  le **double découplage** (+310,3 s de `cpu_s` ⇒ du calcul, pas de
  l'attente ; −639 lignes de régime ⇒ pas du volume), les deux 57014
  **postérieurs** aux quatre étapes, le coût par ligne de `regime` à
  **15,07 ms**, le rappel du **25e centile**, et le fait qu'**aucune
  remontée du garde n'est proposée** (`proposition()` muet, marge 36,3 %).
  **Statut inchangé : Terminé / `done`.**
- **Aucun motif neuf créé.** `bw-regime-sensibilite` **reste en veille** :
  une nuit de hausse, pas deux. Les 57014 de la purge restent rattachés à
  KAN-5 et au dossier « base sous tension ». Le cri de position et la panne
  du webhook **ne sont pas de la dérive** (partage des canaux en tête de
  `bw_jira.sh` : Jira = dérive ; mail + push = les ⛔).

Vérification après écriture (GET, HTTP 200) : **KAN-3 Terminé/`done`,
17 commentaires, maj 06/10 13:26** · **KAN-4 À faire/`new`,
28 commentaires, maj 06/10 13:26** · **KAN-5 À faire/`new`,
11 commentaires, maj 06/10 07:30:54 (intact)**.
⛔ Aucun ticket fermé, aucune transition jouée, aucun ticket créé, aucune
réouverture.

## 7-bis. ⛔ TROUVÉ CE MATIN : le garde-fou « un commentaire par jour et par motif » est COUPÉ EN DEUX

En vérifiant les jetons avant d'écrire, une incohérence : le contrôle a
commenté KAN-5 à 07:30:54, et pourtant
`~/.balise-watch-etat-alertes/cri.jira.bw-purge-57014` était **resté au
2026-10-05**. Explication, trouvée dans `controle_quotidien.sh:98` :

```
bw_jira_signaler "$motif" "$sujet" "$texte\n\n$TEXTE" "$ETAT"
                                                       ^^^^^^
avec, ligne 29 :  ETAT="${BW_MODEL_VERIF_ETAT:-/var/lib/bw-model-verif}"
```

Le contrôle passe **`/var/lib/bw-model-verif`** comme dossier d'état, alors
que le défaut de `bw_jira_signaler` (et ce que les sessions de la routine
utilisent) est **`$HOME/.balise-watch-etat-alertes`**. Relevé ce matin :

| jeton | côté contrôle (`/var/lib/bw-model-verif`) | côté routine (`~/.balise-watch-etat-alertes`) |
|---|---|---|
| `cri.jira.bw-pente-duree` | 2026-09-17 | 2026-10-01 → **2026-10-06** |
| `cri.jira.bw-pente-memoire` | 2026-09-23 | 2026-10-05 → **2026-10-06** |
| `cri.jira.bw-purge-57014` | **2026-10-06** | **2026-10-05** (intact) |

⇒ **Deux magasins de jetons qui ne se parlent pas.** Le garde-fou protège
le contrôle contre lui-même et la routine contre elle-même, **mais pas l'un
contre l'autre**. Concrètement : un `bw_jira_signaler bw-purge-57014`
lancé par une session **aurait doublé** le commentaire du contrôle ce
matin, sans aucun avertissement. Ce qui l'a évité, c'est **uniquement** la
lecture du journal du contrôle imposée par le prompt de la routine —
autrement dit une discipline humaine, pas le mécanisme.
⚠️ `BW_MODEL_VERIF_ETAT` et le dossier d'état des alertes sont deux choses
différentes et le code les confond à cet endroit. **Rien n'a été corrigé**
(lecture seule) : voir §10 n° 4.

## 8. Hors périmètre, relevé sur la nuit du 05→06

- ✅ **Écarts au recalcul indépendant : 3** (7 le 05, 4 le 04, 6 le 03) —
  toujours **tous en `fcstagrume`**, toujours le même motif (« 0 h appariée
  ici (< 6) mais la base porte une ligne »), et **toujours des balises
  neuves** : `mf:74136005` (+48 h), `pioupiou:1710` (+6 h),
  `mf:31042012` (+6 h) — **aucune reprise d'hier**. Le compte redescend ;
  confirmation que c'est un motif d'appariement qui frappe au hasard, pas
  un lot figé.
- `lignes_daily` **69 902** (+176) · `lignes_glissant` **10 612** (−59) ·
  `lignes_regime` **120 779 (−639)** · `lignes_score_zone`
  **131 391 (−698)**.
- Observations du jour : **3 753 balises** (veille 3 734) — le reflux de
  deux nuits est terminé.
- Stabilité des rangs : **`tau = 0,784` sur 65 cases**, 0 jour partagé
  (0,788 sur 58 le 05 ; 0,797 sur 57 le 04). ⓘ **65 cases contre 58** :
  c'est ce qui explique une partie du +40,6 s de l'étape `stabilite`.
- ⚠️ **Témoins du mélange, le gain recule** : sur **7 628** balise-jours ×
  échéance, le mélange fait **2,7173 km/h** contre **2,8753** pour le
  meilleur membre a priori (**gain 5,5 %**, devant dans **55,4 %** des cas,
  contre 7,4 % et 55,9 % hier) ; contre la moyenne **uniforme**, sur
  1 128 : 2,7805 vs 2,9250 (**gain 4,9 %**, contre 6,0 % hier). Le mélange
  **reste au-dessus** du seuil du « devant une fois sur deux », mais la
  marge se réduit deux jours de suite — à resurveiller.
- Témoin du corrigé : le vrai antécédent gagne **14,4 %**, celui d'une
  AUTRE balise **−1,9 %** ⇒ part imputable au site **16,3 points**. Témoin
  FIN : le S2 gagne **15,7 %** sur le brut, le fin **+10,1 points** de plus
  sur le S2 contre **−0,7** aux cellules tournées ⇒ part du secteur et de
  l'heure **10,8 points**.
- Mélange multi-modèle : 8 000 balise×échéance avec poids sur 30 j de cache
  (+6 h : 2 650 `bw_mix`, 413 témoins uniformes, 187 sans poids).
- Référence combinée : médiane **`k = 0,155`** (0,144 le 05, 0,129 le 04)
  sur 3 700 balises / 3 814 climatologisées ; **277** balises avaient un ρ
  hors [0, 1] ramené à la borne (297 le 05, 366 le 04 — **l'amélioration
  continue, troisième nuit**).
- Murphy : **66 455** cases, dont **64 286** décomposées, **266** balises
  dehors (inchangé depuis le 01/10). Tous les modèles restent en
  « AMPLITUDE (une pente peut aider) ».
- FDR : 6 929 tests / 1 839 survivants à BH α=0,1 (brut, 113 rangs retirés
  sur 1 126 publiés) ; 6 620 / 1 391 (corrigé, 120 retirés sur 750).
- Duel apparié : 65 119 lignes en lead 6 (1 259 retirées), 23 970 en
  lead 24 (485). `agrume_pi ↔ bw_mix` +6 h : médiane **+0,382**
  → `b_better` ; +24 h : **+0,522** → `b_better`. `agrume ↔ agrume_pi`
  +6 h : médiane **+0,005** (IC95j [+0,002 ; +0,007]) → `b_better`.
  `agrume ↔ meteofrance_arome_france_hd` +6 h : médiane **−0,002**
  → `a_better`. `arome_r2 ↔ meteofrance_arome_france_hd` +6 h : médiane
  **+0,130** → `b_better`.
- Manches : **39 nuits** suivies depuis le 24/08, **656 cases**
  zone×lead×modèle avec au moins une manche gagnée.
- Pression : 17 971 lignes, 677 points de prévision portent `pmsl`,
  **863 appariées** (médiane 18,1 km).
- Événements notés : **27 760** combinaisons publiables, **26 926**
  écartées sous le quorum de 8.
- ⓘ R2 : **4 écritures**, plafond 10, **159,4 Mo** — rien près du plafond.
  `model_scores.json` 115 070 Ko, `model_scores_light.json` 7 289 Ko
  (533 Ko gzippé).
- `mutations_memoire` : **aucune ligne** au journal de la nuit ; dette
  antérieure de **3 mutations non vues** (2, 5, 13), inchangée.
- Lots : 4 897 entrées écartées en `doublon_de` (L17), 315 en
  `notee_depuis` (L15-bis) ; 7 570 balise-jours écartés au rejeu pour
  naissance postérieure ; **9 balises nées sous leur identifiant**
  (L15-bis, toutes au 2026-09-25).

## 9. Ce qui a été touché

**VPS** : rien hors les **deux** commentaires Jira. `tail -n 3` du
registre, `journalctl` (notation de la nuit et contrôle du jour, **sans
élévation de droits : les lignes utiles sont lisibles par `debian`**),
`list-timers`, `controle_quotidien.py --verbeux`, lecture de `bw_jira.sh`
(en-tête, `bw_jira_http`, `bw_jira_chercher`, `bw_jira_signaler`) et de
`controle_quotidien.sh` (lignes 29 et 88-100), `systemctl cat
bw-model-controle.service`, **six GET Jira** (trois avant écriture, trois
après vérification), listage et lecture des **deux** dossiers de jetons
(`~/.balise-watch-etat-alertes` et `/var/lib/bw-model-verif`).
**Aucun `systemctl start/restart/daemon-reload`, aucun `enable`, aucun SQL
joué, aucun `rsync`, rien écrit dans `~/balise-watch` ni dans `/etc`.**
Écritures : le texte de KAN-4 par `bw_jira_signaler` (qui travaille dans un
`mktemp -d` en 700 effacé après), le texte de KAN-3 par `POST` direct (même
`mktemp -d`), et les **deux jetons `cri.jira.bw-pente-memoire` et
`cri.jira.bw-pente-duree` du jour** dans `~/.balise-watch-etat-alertes`.
✅ **Aucune écriture dans `/tmp` cette fois** : la sortie de
`controle_quotidien.py --verbeux` a été lue par un tube (`| cat`), sans
fichier intermédiaire — l'exception signalée le 05/10 n'est pas reconduite.
`~/.balise-watch-alertes.env` **sourcé**, jamais lu par valeur (seule
`BW_ETAT_ALERTES` a été testée pour son existence, et elle est **non
définie**) ; `curl -K -`, jamais `-u`. Les deux scripts passés au VPS l'ont
été par `ssh 'bash -s' <` depuis le Mac — **rien n'a été déposé sur le
VPS**.

**Mac** : cette note et son miroir git, plus deux scripts jetables dans
`/Users/yann/` (hors dépôt : `bw-jira-get-06-10.sh`,
`bw-jira-post-06-10.sh`) — **pas de `git push`**.

Miroir git : `notes-projet/verdict-pente-06-10.md`, commité en local depuis
la racine du dépôt serveur. Pas de `git push`.

## 10. Ce qui reste — et ce qui demande Yann

1. ⛔ **LA DURÉE A BONDI DE 336 s, ET C'EST DU CALCUL.** 5 157 s, marge
   2 943 s (36,3 % du garde), `cpu_s` **+310,3 s** : 92 % de la hausse est
   du calcul, pas de l'attente — **l'inverse du 01/10**. Les quatre étapes
   montent ensemble (+297 s sur la somme), et le volume de régime
   **baisse** de 639 lignes. Coût par ligne de `regime` : **15,07 ms**,
   plus haut de la série, +11,4 % en une nuit. KAN-3 **commenté**, laissé
   **Terminé**, **aucune remontée du garde proposée** (`proposition()`
   muet). ⚠️ **Rien à décider aujourd'hui, tout à relire demain matin.**
2. ⚠️ **`bw-regime-sensibilite` : la question revient DEMAIN, pas
   aujourd'hui.** L'arbitrage du 29/09 demande deux nuits de hausse qui
   s'additionnent ; il y en a **une**. **Si le coût par ligne de `regime`
   reste au-dessus de 14,5 ms la nuit du 06→07, la condition est remplie et
   c'est à toi de trancher** : motif Jira neuf, ou veille prolongée ? Rien
   n'a été créé.
3. ⛔ **LA PURGE REPART À 0 / 3** après six nuits propres : un 57014 est
   revenu dans le bloc (tranche `?as_of=eq.2026-09-28&regime=eq.fluxW`,
   rejouée et **rattrapée** — la purge a bien abouti : 124 678 lignes en
   8 tranches). ⇒ **la question « faut-il fermer KAN-5 ? », posée les 04 et
   05/10, est RETIRÉE** : la réponse est non, et elle ne se reposera
   qu'après trois nouvelles nuits propres. ⚠️ La sonde « plus vieille
   journée » a elle aussi expiré (essai 1/2) : l'absence de
   `des lignes RESTENT` est **moins concluante** cette nuit. Un
   `select as_of, count(*)` de ta part trancherait en une minute.
4. ⛔ **GARDE-FOU CASSÉ, TROUVÉ CE MATIN (§7-bis) : les jetons « un
   commentaire par jour et par motif » vivent dans DEUX dossiers
   différents.** Le contrôle écrit dans `/var/lib/bw-model-verif`
   (`controle_quotidien.sh:98` passe `$ETAT`), la routine dans
   `$HOME/.balise-watch-etat-alertes` (le défaut de `bw_jira_signaler`).
   Résultat : **rien n'empêche techniquement un double commentaire** le
   même jour sur le même motif — ce matin, seule la lecture du journal du
   contrôle l'a évité sur KAN-5. **Correctif à décider par toi** : soit le
   contrôle cesse de passer `$ETAT` (une ligne), soit les deux passent
   explicitement par le même dossier. Rien n'a été touché.
5. ⚠️ **LE CONSTAT DU CONTRÔLE SUR-LIT LES REJEUX.** Il a écrit à KAN-5
   « purge **en échec** cette nuit », alors que la tranche a été rejouée et
   que la purge a abouti. Il lit la liste `incidents` du registre, qui garde
   la ligne d'avertissement même après un rejeu réussi. ⇒ dans
   `controle_quotidien.py`, un `⚠️ purge … rejouée dans 5 s` suivi d'un
   `→ purge … N ligne(s) effacée(s) en 8 tranche(s)` **ne devrait pas**
   compter comme un échec. C'est la leçon du 28/09, côté machine.
6. ✅ **LA MÉMOIRE (KAN-4) RECULE, ET CETTE NOTE DOIT SE CORRIGER.** Jalon
   **3 364 Mo (−53)**, coût par ligne **1 689,3 o (−28,0)** à fenêtre en
   **hausse** de 1 102 balise-jours. La « hausse de fond de quatre nuits »
   annoncée les 04 et 05/10 est **rendue** : l'écart au 01/10 retombe de
   +31,7 à **+3,7 o/ligne**. À huit nuits, la série **oscille autour de
   1 695 sans pente nette**. KAN-4 reste **ouvert** (+564 Mo au-dessus du
   seuil, swap 2 175,5 Mo). ⚠️ **Aucun levier déployé depuis le 21/09
   (16 nuits)** : la **ligne en tuple** reste le remède, après la mesure
   `tuple` vs `namedtuple` à la sonde.
7. ✅⚠️ **LE DOSSIER POSITION A FONDU, ET L'ÉCHÉANCE D'HIER ÉTAIT FAUSSE.**
   15 divergences → **11** ; **neuf des onze balises à 8 j sont sorties**
   (compteurs réarmés). **Demain le compte de CONFIRMÉES passera de 2 à 4,
   pas de 2 à 13.** Le cri partira quand même (c'est un front). Restent
   quatre cas qui comptent : `pioupiou:1333` (87,7 km) et `pioupiou:2171`
   (38,9 km), candidates **AUTRE balise** ; ⚠️ `pioupiou:1388` qui
   **s'éloigne** (592 m → 2 363 m, compteur 8 → 9 j) et sort du lot
   « maille » ; `infoclimat:STATIC0491` (1 159 m, stable, 9 j). ⇒ **les
   onze « changements de maille » ne demandent probablement aucune
   correction de coordonnées** : ils se sont réalignés seuls.
8. ⛔ **LE WEBHOOK `push` RESTE CASSÉ : 0 / 2**, pas éprouvé depuis le
   02/10. La variable est présente (pas de cri de `bw_avertir_config`),
   donc c'est le `POST` qui échoue. Deux questions, posées depuis le
   30/09 : veux-tu qu'une session éprouve `BW_WEBHOOK_URL` par un `curl` de
   test **hors run**, ou préfères-tu regarder toi-même ? Et faut-il un
   motif Jira pour une panne de canal, alors que `bw_jira.sh` réserve Jira
   à la dérive ? ⓘ Le cri de demain sera le troisième essai — **sur
   4 CONFIRMÉES, pas 13**.
9. ⛔ **LE DOSSIER « BASE SOUS TENSION » redevient le levier du jour.**
   `diagnostic_base_sous_tension_2026-09-29.sql` (lecture seule, 9 blocs)
   **attend toujours d'être joué dans le SQL Editor** ; les correctifs
   candidats (ANALYZE / VACUUM / autovacuum par table) y sont en
   commentaire. Ce matin, **deux** signaux au même endroit : un timeout
   dans la purge et +176,7 s sur `regime`. Les trois nuits à
   `n_57014 = 0` de la semaine n'étaient pas un correctif — c'est dit pour
   la deuxième fois.
10. ⛔ **LE CRI DE POSITION EST « À FRONT »** (démontré dans les deux
    sens). Question du 01/10, toujours ouverte : veux-tu que le garde-fou
    **recrie** tant qu'une balise reste confirmée (même motif, une fois par
    jour), ou qu'il se taise comme aujourd'hui ?
11. ⚠️ **CINQUIÈME MATIN DE SUITE HORS HORAIRE** : 11:17 UTC pour 07:07
    aujourd'hui (≈ 4 h 10 de retard), 08:56 hier, 17:51 le 04, et **aucun
    tir** les 02 et 03/10. Le VPS est à l'heure les cinq matins (contrôle à
    07:30:52, notation nocturne complète) : **le trou est du côté de la
    planification de la routine**. Cinq matinées de suite, ça mérite
    vraiment un coup d'œil à la configuration de la tâche.
12. ⚠️ **Témoins du mélange : le gain recule deux nuits de suite**
    (7,4 % → 5,5 % contre le meilleur membre ; 6,0 % → 4,9 % contre
    l'uniforme ; « devant » 55,9 % → 55,4 %). Toujours au-dessus du seuil,
    mais la marge se réduit.
13. `mutations_memoire` : 3 mutations non vues (dette antérieure,
    inchangée).
