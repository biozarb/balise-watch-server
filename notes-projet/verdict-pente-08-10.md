# Verdict de pente du 08/10/2026 — la hausse de durée **S'ARRÊTE** (+1 s, plateau) mais la marge reste au **plus bas** de la série ; la mémoire **BAT ENCORE son record** (3 429 Mo) et le coût par ligne passe au plus haut jamais vu ; la purge est **PROPRE (2 / 3)** ; les témoins du mélange **REMONTENT au-dessus de la barre** — la note d'hier est démentie ; le cri de position **ne repart pas** (toujours 4, canal à front) ; **Discord est toujours muet** et la routine a tiré **2 h 10 en retard**

## 11:35 (Paris) — routine Balise Watch (tirée à 09:21 UTC pour 07:11 : **2 h 10 de RETARD**), lecture seule sur le VPS + trois commentaires Jira

**Étape 0 faite.** `git log --oneline --since=midnight` : **aucun commit du
jour**, ni dans `balise-watch-server` ni dans le dépôt principal.
`project_read` de `claude/verdict-pente-08-10.md` → « No doc » ;
`claude/verdict-pente-07-10.md` lu **en entier** (les deux vagues de
correctifs et les quatre arbitrages). `notes-projet/README.md` relu. États
Jira relevés par GET **avant** toute écriture. ⇒ **premier et seul run du
jour, rien à fusionner.**

⚠️ **LE RETARD DE TIR EST REVENU.** La tâche était programmée pour
**07:11:05 UTC** et a tiré à **09:21:28 UTC** : **2 h 10 de retard**. Le
point n° 12 d'hier (« à revérifier demain avant de considérer la chose
réglée ») est donc **tranché dans le mauvais sens** : la matinée à l'heure du
07/10 était une exception, pas une réparation. Historique : retards les 04,
05 et 06/10 (jusqu'à 4 h 10), **aucun tir** les 02 et 03/10, à l'heure le
07/10, **+2 h 10 aujourd'hui**. ⓘ **Le VPS, lui, est à l'heure** : le timer
`bw-model-controle.timer` a tiré à **07:30:50** (prochain vendredi 09/10
07:30:39) et la notation à 05:58:33. **Le trou est côté planification de la
routine, pas côté machine.**

## 1. Les nuits, bout à bout

| | 03/10 | 04/10 | 05/10 | 06/10 | 07/10 | 08/10 |
|---|---|---|---|---|---|---|
| durée | 4 944 s | 4 876 s | 4 821 s | 5 157 s | 5 227 s | **5 228 s (+1)** |
| garde / marge | 8 100 / 3 156 | 8 100 / 3 224 | 8 100 / 3 279 | 8 100 / 2 943 | 8 100 / 2 873 | **8 100 / 2 872 (−1)** |
| marge en % du garde | 39,0 % | 39,8 % | 40,5 % | 36,3 % | 35,5 % | **35,46 % ← plus bas** |
| `cpu_s` | 3 961,3 | 3 964,5 | 3 853,3 | 4 163,6 | 4 244,9 | **4 257,9 (+13,0) ← plus haut** |
| jalon max | 3 389 Mo | 3 376 Mo | 3 417 Mo | 3 364 Mo | 3 420 Mo | **3 429 Mo (+9) ← RECORD** |
| au-dessus du seuil | +589 | +576 | +617 | +564 | +620 | **+629** |
| swap au pic | 2 301,7 | 2 592,1 | 2 218,3 | 2 175,5 | 2 127,7 | **2 267,1 (+139,4)** |
| pages sorties | 2 684 787 | 2 338 891 | 2 579 457 | 2 507 693 | 2 369 940 | **2 556 336 (+186 396)** |
| pic système | 3 625,3 | 3 624,7 | 3 600,5 | 3 619,1 | 3 617,2 | **3 602,9 (−14,3)** |
| fenêtre rejouée | 2 082 544 | 2 085 523 | 2 086 473 | 2 087 575 | 2 088 602 | **2 089 691 (+1 089)** |
| o / ligne rejouée | 1 706,4 | 1 697,4 | 1 717,2 | 1 689,7 | 1 717,0 | **1 720,6 (+3,6) ← plus haut** |
| `n_57014` | 0 | 0 | 0 | 2 (purge) | 0 | **0** |
| purge (lignes / tranches) | 131 657 / 8 | 131 554 / 8 | 125 782 / 8 | 124 678 / 8 | 126 857 / 8 | **130 517 / 8** |
| lancement / résultat | timer/success | timer/success | timer/success | timer/success | timer/success | **timer/success** |

Nuit **comparable** : `lancement=timer`, `exec_status=0`, `oom=0`,
`result=success`, 05:58:33 → 07:25:50, `✅ terminé (758 275 lignes écrites en
base)` — contre 674 216 hier. Rien à écarter. **Zéro `⚠️` dans tout le
journal de la nuit** (compté : 0).

Contrôle de ce matin, **tir régulier 07:30:50** : « **70 relevé(s),
49 comparable(s)** ; durée : 10 points, pente **−68 s/nuit** ; mémoire :
10 points, pente **−9 Mo/nuit** ; horizon 30 j ; seuil 2 800 Mo » puis
« **rien à dire : pente plate/négative, ou échéance hors horizon** ». ⇒ **il
n'a crié sur aucun motif et n'a commenté aucun ticket aujourd'hui** (vérifié :
les trois jetons de `/var/lib/bw-model-verif` sont restés au 17/09, 23/09 et
06/10). Le garde-fou réparé le 07/10 était donc **libre** : les deux
`bw_jira_signaler` du jour sont passés sans collision.

## 2. ✅ Durée : la hausse S'ARRÊTE — +1 s, plateau au niveau haut

`4 876 · 4 821 · 5 157 · 5 227 · **5 228**`. Après **+336** puis **+70**, la
nuit prend **+1 s**. ⇒ **la troisième nuit de hausse annoncée hier n'a pas eu
lieu.** Deux points ne faisaient pas une pente ; trois points disent
maintenant un **plateau**, pas une rampe.

⚠️ **Mais le plateau est au plus mauvais endroit** : marge **2 872 s =
35,46 % de 8 100**, le plus bas de la série suivie. Rien n'est rendu des
+406 s des deux nuits précédentes.

`cpu_s` **4 257,9 (+13,0)** pour **+1 s** d'horloge : le processeur monte
encore plus que le temps réel, donc le peu qui bouge est du **calcul** — et
`n_57014 = 0` partout (ni dans la fenêtre de `rpc/bw_character_avance`, ni
dans la purge) : **zéro attente sur la base**, deuxième nuit d'affilée.

| étape | 05/10 | 06/10 | 07/10 | 08/10 |
|---|---|---|---|---|
| `regime` | 1 643,3 | 1 820,0 | 1 794,6 | **1 813,6 (+19,0)** |
| `glissant` | 929,8 | 1 002,0 | 1 018,3 | **1 005,9 (−12,4)** |
| `stabilite` | 288,2 | 328,8 | 341,7 | **338,1 (−3,6)** |
| `rejeu` | 74,0 | 81,5 | 88,4 | **79,2 (−9,2)** |
| somme des quatre | 2 935,3 | 3 232,3 | 3 243,0 | **3 236,8 (−6,2)** |
| hors étapes | 1 885,7 | 1 924,7 | 1 984,0 | **1 991,2 (+7,2)** |

⚠️ **La signature du 07/10 ne se reproduit pas.** Hier **85 %** de la hausse
était **hors étapes** ; cette nuit les deux blocs bougent **en sens
contraire**, de quelques secondes chacun (−6,2 dans les étapes, +7,2 hors).
Le net de +1 s est la somme de deux mouvements plus grands qui s'annulent.
⇒ ⓘ **trois nuits, trois signatures différentes** (06/10 : dans les étapes ;
07/10 : hors étapes ; 08/10 : les deux, en sens opposés). **Une nuit ne fait
pas une pente, et une signature de nuit ne fait pas une cause.** Le bloc hors
étapes — publication, Murphy, événements, pression, duels, purge — **reste
non instrumenté** : on ne peut rien dire de plus fin que « +7,2 s ».

⛔ **LE DÉCOUPLAGE TEMPS / VOLUME S'INVERSE, et c'est le fait neuf du
matin.** `lignes_regime` **121 977 (+1 232)**, `lignes_score_zone`
**132 525 (+1 226)**, `lignes_glissant` **10 548 (−6)**, `lignes_daily`
**69 664 (−110)**. Après **trois** nuits où tous les volumes baissaient
pendant que la durée montait, les deux plus gros volumes montent d'environ
**1 %** et la durée **ne bouge pas** : un surcroît de volume **absorbé à
temps constant**. ⚠️ Cela affaiblit la lecture « ce n'est pas du volume » :
en réalité le temps et le volume ne sont **pas corrélés du tout**, ni dans un
sens ni dans l'autre, ce qui est une information différente.

Coût par ligne de `regime` :

```
13,39 (01/10) · 13,24 · 14,02 · 13,67 · 13,53 · 15,07 · 14,86 · 14,87 ms (08/10)
  → +0,006 ms après −0,21 : PLATEAU
```

⚠️ **`bw-regime-sensibilite` : critère NON rempli, rien n'est créé.**
L'arbitrage unique du 07/10 exige **deux hausses consécutives** du coût par
ligne. Il y a **une** hausse, et elle est de **six millièmes de milliseconde**
— indiscernable du bruit. Le seuil de 14,5 ms de la note du 06/10 est retiré
depuis hier et n'est pas ressorti. **Aucun motif neuf.**

Coût par ligne de `glissant` : **96,5 → 95,4 ms**. ⓘ `stabilite` : `tau` sur
**60 cases** cette nuit contre 67 hier — moins de cases, moins de travail,
cohérent avec les −3,6 s.

⚠️ **KAN-3 COMMENTÉ, NON rouvert**, par **`bw_jira_commenter KAN-3`** — la
fonction ajoutée le 07/10, dont c'est le premier usage par la routine (avant,
c'était un `POST` jetable réécrit trois fois). HTTP 201 → **19 commentaires**.
**Statut inchangé : Terminé / `done`.** ⓘ Le jeton `cri.jira.bw-pente-duree`
est **resté au 07/10** : c'est le comportement voulu, le canal délibéré ne
touche pas au garde-fou du canal automatique. **Vérifié après écriture.**

⚠️ **Remontée du chien de garde : AUCUNE proposée.** `proposition()` n'a rien
formulé (échéance hors horizon de 30 j). **`10-timeout-s3.conf` n'a pas été
touché** et ne le sera pas sans Yann.

ⓘ **25e centile, quatrième matin d'affilée.** Le contrôle affiche
**−68 s/nuit**, exactement la même valeur qu'hier. La pente est le **25e
centile des différences** : elle n'a vu ni le +153 s du 01/10, ni le +336 s du
06/10, ni le +70 s du 07/10. **Son silence ne vaut pas acquittement — mais
cette nuit, pour une fois, la nuit lui donne raison.**

## 3. ⛔ Mémoire : RECORD BATTU DE NOUVEAU — 3 429 Mo, et le coût par ligne passe au plus haut jamais relevé

```
⛔ après le rejeu d'archive            : 3 024 Mo  (2 995 le 07, 3 002 le 06)
⛔ après le score par régime           : 2 901 Mo  (2 909 le 07, 2 853 le 06)
⛔ après l'oubli de la fenêtre rejouée : 3 429 Mo  (3 420 le 07, 3 364 le 06)  ← jalon max, RECORD
```

Jalon max **3 429 Mo (+9)**, **629 Mo au-dessus du seuil**. Le record de
3 420 Mo d'hier est battu de 9 Mo, le deuxième matin de suite.

```
29/09 1 671,3 o · 30/09 1 692,6 · 01/10 1 685,6 · 02/10 1 689,2
03/10 1 706,4  · 04/10 1 697,4 · 05/10 1 717,2 · 06/10 1 689,7
07/10 1 717,0  · 08/10 1 720,6
  → +3,6 o/ligne, à fenêtre en HAUSSE de 1 089 balise-jours
  → 1 720,6 est le PLUS HAUT de la série (précédent : 1 717,2 le 05/10)
```

À taux constant, dans les deux sens : au taux du **07/10** (1 717,0 o/ligne)
la nuit aurait rendu **3 421,4 Mo** (elle a rendu 3 429, soit **+7,6 Mo**) ;
au taux du **01/10** (1 685,6), **3 359,0 Mo** (soit **+70,0 Mo**).

⚠️ **CORRECTION DE LA LECTURE D'HIER, qui elle-même corrigeait celle du
06/10.** La note du 07/10 décrivait la série comme « oscillant entre 1 686 et
1 717 sans pente nette ». À **dix** nuits, la fourchette s'étire vers le
**haut** (1 686–1 721) et les **deux dernières nuits sont les deux plus
hautes valeurs jamais relevées**. ⛔ **Ce n'est TOUJOURS PAS une pente
établie** — le 06/10 était à 1 689,7, au bas de la fourchette, et deux points
hauts d'affilée ne font pas une rampe (la leçon a resservi cinq fois en onze
jours). **Mais ce n'est plus une oscillation symétrique** : les trois
dernières valeurs sont **1 689,7 → 1 717,0 → 1 720,6**. ⇒ **à surveiller en
priorité demain** : une quatrième valeur haute changerait la lecture.

**Swap : pic 2 267,1 Mo (+139,4)** et **2 556 336 pages sorties (+186 396)**.
⚠️ **Hier ces deux chiffres étaient les PLUS BAS de la série ; ils remontent
ensemble.** C'est cohérent (les deux mesurent la même pression) et cela
**démentit** la lecture encourageante d'hier sur ce point précis. Le plancher
tient : **9e nuit consécutive au-dessus de 2,1 Go**. Pic système
**3 602,9 Mo (−14,3)**.

**KAN-4 reste OUVERT, commenté** (`bw_jira_signaler`, HTTP 201 →
**30 commentaires**). Les trois conditions de fermeture : jalon mesurément
retombé → **NON (record)** ; swap au pic ≈ 0 → **NON (2 267,1, en hausse)** ;
contrôle muet → oui, mais pente **−9 Mo/nuit** au 25e centile, **silence
inertiel**.

Le remède reste la **ligne en tuple** (`enquete-pente-10-09.md` §2.6,
≈ −1 030 o/ligne cumulés), après la mesure `tuple` vs `namedtuple` à la
sonde. ⚠️ Rappel de l'échec de l'élagage de `units` (−124 Mo au lieu de
−1 500) : **les gains sont dans la structure**. **Rien de déployé côté
mémoire depuis `af25efb` (21/09) — 18e nuit sans levier.**

## 4. ✅ Purge : nuit PROPRE, 130 517 lignes en 8 tranches — compteur **2 / 3**

Le bloc purge, en entier :

```
07:25:39  → purge model_score_zone : 130 517 ligne(s) effacée(s) en 8 tranche(s)
07:25:39  ⓘ purge model_character : rien avant le 2027-02-04 (première écriture 2026-08-08,
          rétention 180 j) — aucune requête lancée.
07:25:39  ✅ terminé (758 275 lignes écrites en base)
```

**Rien d'autre.** Point par point : aucune tranche en échec, **aucun 57014**
(`n_57014 = 0`) ; **130 517 lignes, nombre lisible**, aucun `?` ; **8
tranches**, une par régime, **aucune sans `&regime=`** (le code du VPS n'a pas
été écrasé par un ancien) ; aucun `⚠️ compte model_score_zone : HTTP 500` ;
**aucun `des lignes RESTENT`** ; et ⓘ **la sonde « plus vieille journée » n'a
pas bronché**, donc cette absence est **pleinement concluante**.

Volume effacé : **131 640 · 131 657 · 131 554 · 125 782 · 124 678 · 126 857 ·
130 517**. Il **remonte** de 3 660 lignes — ⚠️ **ce n'est pas un signal**, il
suit le volume de la journée purgée (ici le **2026-09-30**).

**Compteur de fermeture : 2 / 3.** (6/3 le 05/10, remis à 0 le 06/10, 1/3 le
07/10, **2/3 ce matin**.) ⇒ **si la nuit du 08→09 est propre, le compteur
atteint 3/3 et la question de la fermeture de KAN-5 sera POSÉE à Yann** —
elle ne sera pas tranchée par la routine, et elle n'est pas posée aujourd'hui.

**KAN-5 commenté** (`bw_jira_signaler`, HTTP 201 → **13 commentaires**).
Le sujet réécrit le 07/10 est bien en place (vérifié par GET) : il décrit le
**motif suivi**, plus une nuit.

## 5. ✅ `n_57014 = 0` — deuxième nuit d'affilée, et ça ne referme rien

Série : **1 (28/09) · 2 · 0 · 3 (01/10) · 2 · 0 · 0 · 0 · 2 (06/10) · 0 ·
0 (08/10)**.

⚠️ **Le dossier « base sous tension » ne se referme pas pour autant** —
troisième fois que ce rappel est nécessaire.
`model-verif/diagnostic_base_sous_tension_2026-09-29.sql` (lecture seule,
9 blocs, SQL Editor) **n'a toujours pas été joué**, et il y a eu **trois**
nuits à zéro d'affilée (03, 04, 05/10) avant que le 57014 revienne le 06.
ⓘ Comme hier, la quasi-stabilité de la durée est du **calcul** : elle ne
plaide **pas** pour la base.

## 6. ⓘ Position : toujours **4 CONFIRMÉES**, aucun cri — le canal « à front » se vérifie une troisième fois

```
08/10 05:59:52  ⛔ position : 11 balise(s) divergent du gel (10 j lus), dont 4 CONFIRMÉE(S) (≥ 10 j)
                (et RIEN d'autre : pas de « cri déposé pour envoi », pas de msmtp, pas de push)
```

| balise | 06/10 | 07/10 | 08/10 | état |
|---|---|---|---|---|
| `pioupiou:1333` (87 693 m) | 10 j | 10 j | **10 j** | CONFIRMÉE |
| `pioupiou:2171` (38 925 m) | 10 j | 10 j | **10 j** | CONFIRMÉE |
| `pioupiou:1388` (2 363 m) | 9 j | 10 j | **10 j** | CONFIRMÉE |
| `infoclimat:STATIC0491` (1 159 m) | 9 j | 10 j | **10 j** | CONFIRMÉE |
| `pioupiou:1378` (15 778 m) | 1 j | 2 j | **3 j** | 10 j le 15/10 |
| `pioupiou:367` (6 764 m) | 1 j | 2 j | **3 j** | 10 j le 15/10 |
| `pioupiou:1417` (829 m) | 1 j | 2 j | **3 j** | 10 j le 15/10 |
| `pioupiou:1375` (747 m) | 1 j | 2 j | **3 j** | 10 j le 15/10 |
| `pioupiou:1722` (631 m) | 1 j | 2 j | **3 j** | 10 j le 15/10 |
| `pioupiou:1562` (481 m) | 1 j | 2 j | **3 j** | 10 j le 15/10 |
| `pioupiou:1678` (422 m) | 1 j | 2 j | **3 j** | 10 j le 15/10 |

Le compte reste à **4**, donc **aucun cri** : `position_confirmees.json` est
resté daté du **07/10 06:00**. ⇒ ⓘ **démonstration directe du canal « à
front, pas à état »** : hier 2 → 4 ⇒ cri ; ce matin 4 → 4 ⇒ silence. **La
question du 01/10 reste ouverte et devient plus concrète** : une situation
⛔ en cours ne se rappelle jamais d'elle-même. Les **sept** nouvelles sont
toutes passées de 2 j à **3 j** (aucune n'est sortie) — elles franchiraient
10 j le **15/10**, et ce jour-là le compte passerait de 4 à 11, donc un cri.

⛔ **CONSÉQUENCE DIRECTE : le webhook `push` n'a PAS pu être éprouvé cette
nuit.** Aucun ⛔ n'est parti, donc aucun appel ntfy. Le correctif `--ipv4` du
07/10 et le journal bavard (`ⓘ push parti (webhook, HTTP 200)`) **attendent
toujours leur première vérification en conditions réelles** — elle viendra au
prochain cri, c'est-à-dire au prochain changement de front, ou le 15/10 au
plus tard si les sept tiennent leur rythme.

⚠️ **`BW_DISCORD_WEBHOOK_URL` est ABSENTE du `.env`** (vérifié par les
**noms** de variables seuls, jamais par valeur : 25 variables exportées, et
celle-là n'y est pas). ⇒ **le second canal du téléphone est codé, testé, et
toujours MUET.** `~/installer-webhook-discord.sh` n'a pas été lancé. ntfy
reste donc le canal unique, avec son quota de voisinage.

Le contrôle **ne corrige rien** (règle de `freeze_balises.geler`) : **geste
attendu de Yann**, inchangé depuis hier — trancher chacun des quatre cas
(`1333` à 87,7 km et `2171` à 38,9 km → candidates **AUTRE balise** ;
`1388` à 2 363 m, qui s'était **éloignée** → à regarder pour elle-même ;
`infoclimat:STATIC0491` à 1 159 m, stable → profil **changement de maille**),
puis poser `position_suspecte` + `position_note` sur `station_zone` par
`.sql`.

## 7. ✅ DÉMENTI : les témoins du mélange REMONTENT au-dessus de la barre

```
⛔ témoins du mélange : sur 7 590 balise-jours × échéance, le mélange fait
   4,6481 km/h contre 4,7679 pour le meilleur membre a priori
   (gain 2,5 %, mélange devant dans 53,1 % des cas) ;
   contre la moyenne UNIFORME, sur 1 122 : 4,502 vs 4,6471 (gain 3,1 %)
```

| | 05/10 | 06/10 | 07/10 | 08/10 |
|---|---|---|---|---|
| gain contre le meilleur membre a priori | 7,4 % | 5,5 % | **−0,6 %** | **+2,5 %** |
| mélange devant, en % des cas | 55,9 % | 55,4 % | **49,2 %** | **53,1 %** |
| gain contre la moyenne uniforme | 6,0 % | 4,9 % | 4,8 % | **3,1 %** |
| erreur absolue du mélange | — | 2,7173 | 3,3621 | **4,6481** |

✅ **La note du 07/10 est démentie, et c'est exactement ce qu'elle avait
annoncé comme possible.** Elle écrivait « ⛔ la barre est franchie » tout en
notant que l'erreur absolue avait bondi de 24 % et qu'« une nuit ne fait pas
une pente ». La nuit suivante, le mélange repasse **devant** (+2,5 %) et
**devant dans 53,1 %** des cas — alors que l'erreur absolue a encore bondi
(**+38 %**, 4,6481 contre 3,3621 : journée encore plus venteuse). ⇒ ⛔ **le
passage sous la barre du 07/10 était un accident de journée, pas une
dérive.** **Aucun motif Jira n'est créé, et la question n° 9 du §14 d'hier
(« faut-il un motif si la nuit du 07→08 confirme ? ») est close par la
mesure : non, elle n'a pas confirmé.**

⚠️ **Ce qui bouge vraiment, et dans l'autre sens** : le gain contre la moyenne
**uniforme** recule, lui, pour la **quatrième** nuit — 6,0 → 4,9 → 4,8 →
**3,1 %**. C'est le témoin de la **pondération**, celui qui tenait hier. Il
est encore largement positif ; **à regarder demain**, sans rien en conclure
aujourd'hui.

ⓘ Et à côté : `tau` **cesse de baisser** (0,788 → 0,784 → 0,742 → **0,744**),
sur **60** cases contre 67. Le rapprochement §7 ↔ `tau` suggéré hier n'est pas
confirmé non plus.

## 8. Hors périmètre, relevé sur la nuit du 07→08

- ⚠️ **Écarts au recalcul indépendant : 4** (3 le 07, 3 le 06, 7 le 05) —
  toujours **tous en `fcstagrume`**, toujours le même motif (« 0 h appariée
  ici (< 6) mais la base porte une ligne »), et **aucune reprise d'hier** :
  `infoclimat:STATIC0024` (agrume +6 h), `mf:05126001` (agrume_pi +6 h),
  `aemet:9808X` (agrume_pi +6 h), `mf:06136005` (agrume +48 h).
  **Cinquième confirmation** : motif d'appariement qui frappe au hasard, pas
  un lot figé. 15 balise-jours comparés, 5 sous le seuil de 6 h.
- ✅ **Self-test du scoring VERT** (lot S3) : les six contrôles (a) à 1,0 ou
  0,0 exactement, le (b) permuté à 2,198 dans l'intervalle attendu.
- `lignes_daily` **69 664** (−110) · `lignes_glissant` **10 548** (−6) ·
  `lignes_regime` **121 977** (+1 232) · `lignes_score_zone` **132 525**
  (+1 226).
- Observations du jour : **3 746 balises** (veille 3 749).
- Stabilité des rangs : **`tau = 0,744` sur 60 cases**, 0 jour partagé.
- Témoin du corrigé : le vrai antécédent gagne **15,1 %**, celui d'une AUTRE
  balise **−2,9 %** ⇒ part imputable au site **18,0 points** (18,7 hier).
  Témoin FIN : le S2 gagne **14,4 %** sur le brut, le fin **+7,6 points** de
  plus sur le S2 contre **−1,9** aux cellules tournées ⇒ part du secteur et de
  l'heure **9,5 points** (12,3 hier). ⚠️ **Les deux témoins reculent** cette
  nuit, après s'être renforcés hier — même journée venteuse, mêmes réserves.
- Mélange multi-modèle : **7 978** balise×échéance avec poids sur 30 j de
  cache (+6 h : 2 631 `bw_mix`, 416 témoins uniformes, 197 sans poids).
- Référence combinée : médiane **`k = 0,152`** (0,162 le 07, 0,155 le 06) sur
  3 696 balises / 3 812 climatologisées ; ⚠️ **307** balises avaient un ρ hors
  [0, 1] ramené à la borne (253 le 07, 277 le 06, 297 le 05) — **la série de
  quatre nuits d'amélioration est cassée**, retour au niveau du 05/10.
- Murphy : **66 319** cases, dont **64 299** décomposées, **266** balises
  dehors (inchangé depuis le 01/10). ⓘ **Quatre** combinaisons à SS positif
  cette nuit, contre une seule hier : `bw_mix` +6 h **+0,050**, `bw_mix` +24 h
  **+0,014**, `bw_mix_u` +6 h **+0,031**, `arome_r2` +6 h **+0,021** (plus
  trois `agrume_court`/`agrume_quart` courts à +0,03…+0,06). **À lire à côté
  du §7** : le mélange va mieux cette nuit sur les deux mesures.
- FDR : 6 873 tests / 1 806 survivants à BH α=0,1 (brut, 101 rangs retirés sur
  1 088 publiés) ; 6 564 / 1 325 (corrigé, 116 retirés sur 693).
- Duel apparié : 65 144 lignes en lead 6 (1 169 retirées), 23 980 en lead 24
  (449). `agrume_pi ↔ bw_mix` +6 h : médiane **+0,365** → `b_better` ;
  +24 h : **+0,515** → `b_better`. ⓘ **Verdicts inchangés** depuis hier.
- Manches : **41 nuits** suivies depuis le 24/08, **676 cases**
  zone×lead×modèle avec au moins une manche gagnée.
- Pression : 18 021 lignes, 682 points de prévision portent `pmsl`,
  **865 appariées** (médiane 18,1 km).
- Événements notés : **27 684** combinaisons publiables, **27 552** écartées
  sous le quorum de 8 ; `model_verif_event` 74 787 lignes.
- ⓘ R2 : **4 écritures**, plafond 10, **160,2 Mo** — rien près du plafond.
  `model_scores.json` 116 064 Ko (114 991 hier), `model_scores_light.json`
  7 189 Ko (528 Ko gzippé), `model_murphy.json` 25 485 Ko.
- `mutations_memoire` : **aucune ligne** au journal de la nuit ; dette
  antérieure de **3 mutations non vues** (2, 5, 13), inchangée.
- Lots : 6 408 entrées écartées en `doublon_de` (L17), 405 en `notee_depuis`
  (L15-bis) ; 6 794 balise-jours écartés au rejeu pour naissance postérieure ;
  **9 balises nées sous leur identifiant** (L15-bis, toutes au 2026-09-25) —
  dont `pioupiou:1375`, qui figure aussi parmi les sept de la position.
- `model_character` : **463 184** accumulateurs avancés sur 463 184 envoyés
  (410 952 hier).

## 9. Tickets — trois commentaires, aucune transition, aucune création

États relevés **avant** d'écrire (GET `/rest/api/3/issue/…`, HTTP 200) :

| ticket | motif | statut | `statusCategory` | maj avant | comm. avant |
|---|---|---|---|---|---|
| KAN-3 | `bw-pente-duree` | **Terminé** | `done` | 07/10 09:15:25 | 18 |
| KAN-4 | `bw-pente-memoire` | **À faire** | `new` | 07/10 09:15:24 | 29 |
| KAN-5 | `bw-purge-57014` | **À faire** | `new` | 07/10 12:01:03 | 12 |

- **KAN-4 (mémoire) — OUVERT, commenté** (`bw_jira_signaler`, HTTP 201 →
  **30**). Les trois conditions de fermeture échouent (§3). Le commentaire
  porte le record, la courbe du coût par ligne sur **dix** nuits, les **deux
  calculs à taux constant**, la correction de la lecture d'hier (la fourchette
  s'étire vers le haut) et le **rebond du swap**.
- **KAN-5 (purge) — OUVERT, commenté** (`bw_jira_signaler`, HTTP 201 →
  **13**). Le contrôle n'a rien dit aujourd'hui, le garde-fou était libre. Le
  commentaire porte la nuit propre (130 517 / 8 tranches / zéro 57014), l'état
  de la sonde, le compteur **2/3**, et le rappel des trois nuits propres
  d'affilée de la semaine dernière suivies d'un retour du 57014.
- **KAN-3 (durée, Terminé) — COMMENTÉ, NON rouvert**, par
  **`bw_jira_commenter KAN-3`** (HTTP 201 → **19**). ⓘ **Premier usage de la
  fonction par la routine** : plus de script jetable. La durée n'augmente
  pas, mais le commentaire d'hier annonçait une tendance — **corriger le
  compte rendu là où il a été écrit** est précisément l'usage pour lequel la
  fonction a été créée. Le commentaire porte le plateau (+1 s), la marge au
  plus bas, la répartition par étape et son **troisième** changement de
  signature, l'**inversion du découplage temps/volume**, le plateau du coût
  par ligne de `regime` (critère `bw-regime-sensibilite` **non rempli**), le
  rappel du 25e centile, et le fait qu'aucune remontée du garde n'est
  proposée. **Statut inchangé : Terminé / `done`.**
- **Aucun motif neuf créé.** `bw-regime-sensibilite` : critère non rempli
  (§2). Les témoins du mélange : **démentis** (§7), donc pas de ticket. Le cri
  de position et le silence de Discord **ne sont pas de la dérive** (partage
  des canaux en tête de `bw_jira.sh` : Jira = dérive ; mail + push = les ⛔).

Vérification après écriture (GET, HTTP 200) : **KAN-3 Terminé/`done`,
19 commentaires, maj 08/10 11:30:43** · **KAN-4 À faire/`new`,
30 commentaires, maj 08/10 11:30:42** · **KAN-5 À faire/`new`,
13 commentaires, maj 08/10 11:30:43**.
⛔ Aucun ticket fermé, aucune transition jouée, aucun ticket créé, aucune
réouverture. **Jetons après écriture** : `bw-pente-memoire` et
`bw-purge-57014` au **08/10 11:30** (les deux `signaler`) ;
`bw-pente-duree` **resté au 07/10** — `bw_jira_commenter` ne touche pas au
jeton, comme prévu.

## 10. Ce qui a été touché

**VPS — règle de LECTURE SEULE pleine et entière, rétablie depuis le 07/10 et
respectée.** Rien hors les **trois** commentaires Jira. `tail -n 2` du
registre, `journalctl` (notation de la nuit et contrôle du jour, **sans
élévation de droits**), `list-timers`, `controle_quotidien.py --verbeux` (lu
par un tube), lecture de l'en-tête de `bw_jira.sh` (signatures de
`bw_jira_signaler` et `bw_jira_commenter`), **six GET Jira** (trois avant,
trois après), listage de `/var/lib/bw-model-verif` et de
`~/.balise-watch-etat-alertes`, et les **noms seuls** des variables du `.env`
(`sed "s/=.*//"` — **aucune valeur lue**).
**Aucun `systemctl start/restart/daemon-reload`, aucun `enable`, aucun SQL
joué, aucun `rsync`, rien écrit dans `~/balise-watch` ni dans `/etc`, aucun
fichier déposé sur le VPS.**
Écritures : les textes de KAN-4 et KAN-5 par `bw_jira_signaler`, celui de
KAN-3 par `bw_jira_commenter`, et les **deux jetons du jour** dans
`~/.balise-watch-etat-alertes` (pas celui de `bw-pente-duree`).
`~/.balise-watch-alertes.env` **sourcé**, jamais lu par valeur ; `curl -K -`,
jamais `-u` ; `--ipv4` sur les GET Jira. Les deux scripts passés au VPS l'ont
été par `ssh 'bash -s' <` depuis le Mac, et les corps de commentaire par un
`mktemp -d` en 700 **effacé après**.

**Mac** : cette note et son miroir git, plus deux scripts jetables dans
`/Users/yann/` (hors dépôt : `bw-jira-get-08-10.sh`,
`bw-jira-post-08-10b.sh`) — **pas de `git push`**.

ⓘ **Un piège de méthode à noter, il coûtera du temps à la prochaine
session** : un `corps=$(cat <<'EOF' … EOF)` — heredoc **dans** une
substitution de commande — est refusé par le `bash 3.2` de macOS dès que le
texte contient une apostrophe ou une parenthèse non appariée (`bash -n` rend
« syntax error near unexpected token `(` » sur une ligne de **données**). Le
contournement est d'écrire le corps par un heredoc **de premier niveau**
(`cat > "$trav/c4" <<'EOF4'`) puis de faire `corps4=$(cat "$trav/c4")`.
C'est ce qui est utilisé ici, et le script passe `bash -n` des deux côtés.

## 11. Ce qui reste — et ce qui demande Yann

**Pour toi, et rien ne bougera sans toi :**

1. ⛔ **Lancer `~/installer-webhook-discord.sh`** depuis le Terminal du Mac.
   **Vérifié ce matin : `BW_DISCORD_WEBHOOK_URL` est absente du `.env`.** Le
   second canal est codé et testé depuis hier, et **muet**. ntfy reste seul,
   avec son quota anonyme de voisinage — et ⚠️ **le correctif `--ipv4` n'a
   toujours pas été éprouvé en conditions réelles**, faute de ⛔ cette nuit.
2. ⛔ **Jouer `diagnostic_base_sous_tension_2026-09-29.sql`** dans le SQL
   Editor (lecture seule, 9 blocs). **Neuf jours d'attente.** Deux nuits à
   `n_57014 = 0` n'y changent rien : il y en a eu trois d'affilée avant le
   retour du 06/10.
3. ⛔ **Trancher les 4 cas de position** (`1333` à 87,7 km et `2171` à
   38,9 km → AUTRE balise ? `1388` à 2 363 m, qui s'était éloignée ?
   `STATIC0491` à 1 159 m → maille ?), puis poser `position_suspecte` +
   `position_note` par `.sql`. ⓘ Les **sept** autres sont à **3 j** et
   franchiraient 10 j le **15/10** — ce jour-là le compte passerait de 4 à 11,
   donc un cri, donc la première épreuve réelle du webhook si rien ne bouge
   avant.
4. ⚠️ **Dire si tu veux instrumenter le bloc hors étapes de `run.sh`.** La
   question d'hier reste entière, mais elle est **moins pressante** : la
   durée a cessé de monter, et cette nuit le hors-étapes n'a bougé que de
   +7,2 s. C'est une écriture dans le chemin de la nuit, donc ta décision.
5. ⚠️ **L'HORAIRE DE LA ROUTINE A REDÉRIVÉ : +2 h 10 ce matin** (tir à 09:21
   UTC pour 07:11). La matinée à l'heure du 07/10 était une exception. Le VPS
   est à l'heure (contrôle 07:30:50, notation 05:58:33) : **le trou est côté
   planification**. Veux-tu qu'on regarde ce point en propre ?
6. ⓘ **Le cri de position : à front ou à état ?** Question du 01/10,
   **démontrée une troisième fois ce matin** (4 → 4 ⇒ silence). Une situation
   ⛔ en cours ne se rappelle jamais d'elle-même.
7. ⓘ **Faut-il un champ de bilan de purge au registre ?** (question n° 3 du
   §13 d'hier, sans réponse). Et **faut-il un motif Jira pour une panne de
   canal**, alors que `bw_jira.sh` réserve Jira à la dérive ? (question n° 4
   du §11 du 07/10, sans réponse depuis le 30/09).

**Ce que la surveillance regardera demain matin, sans rien décider :**

8. ⛔ **La mémoire, en priorité** : le coût par ligne fait **1 689,7 →
   1 717,0 → 1 720,6**. Une **quatrième** valeur haute ferait basculer la
   lecture d'« oscillation » vers « pente » — c'est le point le plus près de
   changer de nature. Et le jalon bat son record deux matins de suite.
9. La **durée** : le plateau tient-il, ou la marge repart-elle vers le bas
   depuis 35,46 % ?
10. La **purge** : **3 / 3** si la nuit est propre ⇒ la question de la
    fermeture de KAN-5 sera posée à Yann.
11. Les **témoins** : le gain contre la moyenne **uniforme** recule pour la
    quatrième nuit (6,0 → 4,9 → 4,8 → 3,1 %), et les deux témoins du corrigé
    reculent aussi. Rien n'est conclu ; c'est la série à suivre maintenant que
    celle du « meilleur membre » est démentie.
12. Le **ρ hors [0, 1]** : 307 après quatre nuits d'amélioration (253 hier).
13. Le **webhook** : première épreuve réelle au prochain ⛔.
14. `mutations_memoire` : 3 mutations non vues, dette antérieure, inchangée.
