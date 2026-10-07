# Verdict de pente du 07/10/2026 — la durée monte une DEUXIÈME nuit (5 227 s, marge 35,5 % = plus bas de la série) mais la hausse change de signature : 85 % HORS étapes, `regime` baisse ; la mémoire BAT SON RECORD (3 420 Mo) et rend la correction d'hier ; la purge est PROPRE (1/3) ; le cri de position est parti sur **4** CONFIRMÉES — exactement ce que la note corrigée annonçait — et le **webhook `push` échoue pour la 3ᵉ fois (0/3)**

## 09:15 (Paris) — routine Balise Watch (tirée à 07:09 UTC pour 07:07 : **à l'heure**), lecture seule sur le VPS + trois commentaires Jira

**Étape 0 faite.** `git log --oneline --since=midnight` : **aucun commit du
jour**, ni dans `balise-watch-server` (dernier : `9c64bb5`, 06/10) ni dans le
dépôt principal (dernier : `ce4c5a6`, 05/10). `project_read` de
`claude/verdict-pente-07-10.md` → « No doc » ; `claude/verdict-pente-06-10.md`
lu en entier. `notes-projet/README.md` relu. États Jira relevés par GET
**avant** toute écriture. ⇒ **premier et seul run du jour, rien à fusionner.**

✅ **PREMIER MATIN À L'HEURE depuis six jours** : tir à **07:09 UTC pour
07:07** (hier 11:17 UTC, avant-hier 08:56, le 04 à 17:51, aucun tir les 02 et
03/10). Le point n° 11 de la note d'hier se referme de lui-même — mais une
matinée ne fait pas une réparation, à revérifier demain.

## 1. Les nuits, bout à bout

| | 02/10 | 03/10 | 04/10 | 05/10 | 06/10 | 07/10 |
|---|---|---|---|---|---|---|
| durée | 4 865 s | 4 944 s | 4 876 s | 4 821 s | 5 157 s | **5 227 s (+70)** |
| garde / marge | 8 100 / 3 235 | 8 100 / 3 156 | 8 100 / 3 224 | 8 100 / 3 279 | 8 100 / 2 943 | **8 100 / 2 873 (−70)** |
| marge en % du garde | 39,9 % | 39,0 % | 39,8 % | 40,5 % | 36,3 % | **35,5 % ← plus bas** |
| `cpu_s` | 3 833,9 | 3 961,3 | 3 964,5 | 3 853,3 | 4 163,6 | **4 244,9 (+81,3) ← plus haut** |
| jalon max | 3 350 Mo | 3 389 Mo | 3 376 Mo | 3 417 Mo | 3 364 Mo | **3 420 Mo (+56) ← RECORD** |
| au-dessus du seuil | +550 | +589 | +576 | +617 | +564 | **+620** |
| swap au pic | 2 111,0 | 2 301,7 | 2 592,1 | 2 218,3 | 2 175,5 | **2 127,7 (−47,8) ← plus bas** |
| pages sorties | 1 963 835 | 2 684 787 | 2 338 891 | 2 579 457 | 2 507 693 | **2 369 940 (−137 753)** |
| pic système | 3 606,1 | 3 625,3 | 3 624,7 | 3 600,5 | 3 619,1 | **3 617,2 (−1,9)** |
| fenêtre rejouée | 2 079 507 | 2 082 544 | 2 085 523 | 2 086 473 | 2 087 575 | **2 088 602 (+1 027)** |
| o / ligne rejouée | 1 689,2 | 1 706,4 | 1 697,4 | 1 717,2 | 1 689,7 | **1 717,0 (+27,3)** |
| `n_57014` | 2 | 0 | 0 | 0 | 2 (purge) | **0** |
| purge (lignes / tranches) | 131 640 / 8 | 131 657 / 8 | 131 554 / 8 | 125 782 / 8 | 124 678 / 8 | **126 857 / 8** |
| lancement / résultat | timer/success | timer/success | timer/success | timer/success | timer/success | **timer/success** |

Nuit **comparable** : `lancement=timer`, `exec_status=0`, `oom=0`,
`result=success`, 05:59:31 → 07:26:49, `✅ terminé (674 216 lignes écrites en
base)` (624 745 hier). Rien à écarter.

Contrôle de ce matin, **tir régulier 07:30:53** (prochain jeudi 08/10
07:30:49) : « **69 relevé(s), 48 comparable(s)** ; durée : 10 points, pente
**−68 s/nuit** ; mémoire : 10 points, pente **−9 Mo/nuit** ; horizon 30 j ;
seuil 2 800 Mo » puis « **rien à dire : pente plate/négative, ou échéance hors
horizon** ». ⇒ **il n'a crié sur AUCUN motif et n'a commenté AUCUN ticket
aujourd'hui** (vérifié : les jetons de `/var/lib/bw-model-verif` sont restés au
06/10). Les trois commentaires du jour sont donc les nôtres, sans collision.

## 2. ⛔ Durée : +70 s, deuxième nuit de hausse — mais la signature CHANGE

`4 876 · 4 821 · 5 157 · **5 227**`. **+406 s en deux nuits.** La marge tombe à
**2 873 s = 35,5 % de 8 100**, le plus bas de la série suivie.

**C'est encore du calcul, et cette fois l'argument est total** : `cpu_s` monte
de **81,3 s** pour +70 s d'horloge — le processeur monte **plus** que le temps
réel — et **`n_57014` = 0 sur toute la nuit**, nulle part : ni dans la fenêtre
de `rpc/bw_character_avance`, ni dans la purge. **Zéro attente sur la base.**
Ce n'est donc ni l'attente du 01/10 (où `cpu_s` *baissait* de 50 s), ni un
effet de base.

| étape | 04/10 | 05/10 | 06/10 | 07/10 |
|---|---|---|---|---|
| `regime` | 1 624,7 | 1 643,3 | 1 820,0 | **1 794,6 (−25,4)** |
| `glissant` | 994,6 | 929,8 | 1 002,0 | **1 018,3 (+16,3)** |
| `stabilite` | 275,2 | 288,2 | 328,8 | **341,7 (+12,9)** |
| `rejeu` | 80,8 | 74,0 | 81,5 | **88,4 (+6,9)** |
| somme des quatre | 2 975,3 | 2 935,3 | 3 232,3 | **3 243,0 (+10,7)** |
| hors étapes | 1 900,7 | 1 885,7 | 1 924,7 | **1 984,0 (+59,3)** |

⚠️ **Les deux nuits de hausse n'ont pas la même signature.** Le 06/10, **88 %**
de la hausse était **dans** les quatre étapes. Cette nuit, **85 %** est **hors
étapes** (+59,3 s sur +70), et l'étape `regime` **baisse** de 25,4 s. Le
travail hors étapes — publication, Murphy, événements, pression, duels, purge —
**n'est pas instrumenté étape par étape** : c'est la zone d'ombre à instrumenter
si la hausse continue (§10 n° 2).

⛔ **Le découplage temps / volume tient, troisième nuit :** `lignes_regime`
**120 745 (−34)**, `lignes_score_zone` **131 299 (−92)**, `lignes_glissant`
**10 554 (−58)**, `lignes_daily` **69 774 (−128)**. Tous les volumes baissent ou
stagnent et la durée monte.

Coût par ligne de `regime` :

```
13,39 (01/10) · 13,24 · 14,02 · 13,67 · 13,53 · 15,07 · 14,86 ms (07/10)
  → RECULE de 0,21 ms, mais reste le 2e plus haut de la série
  → et toujours au-dessus du palier historique (≈ 13,6 ms)
```

Coût par ligne de `glissant` : **94,4 → 96,5 ms**. ⓘ `stabilite` s'explique en
partie proprement : `tau` sur **67 cases** cette nuit contre 65 hier et 58 le
05 — plus de cases, plus de travail.

⚠️ **`bw-regime-sensibilite` : AUCUN motif neuf créé, et les deux lectures
divergent — c'est dit sans trancher.** L'arbitrage du 29/09 exige que la hausse
**s'additionne** deux nuits de suite : **ce n'est pas le cas**, le coût par
ligne a *baissé* (15,07 → 14,86) et l'étape a perdu 25,4 s. Mais le seuil
opérationnel posé par la note du 06/10 — « au-dessus de 14,5 ms la nuit du
06→07 » — **est franchi** (14,86). ⇒ **la question revient à Yann** (§10 n° 2),
rien n'est créé.

⚠️ **KAN-3 COMMENTÉ, NON rouvert** (`POST /rest/api/3/issue/KAN-3/comment`
direct, HTTP 201 → **18 commentaires**). `bw_jira_chercher` filtre sur
`statusCategory != Done` : un `bw_jira_signaler` aurait **créé un ticket neuf**.
**Statut inchangé : Terminé / `done`.**

⚠️ **Remontée du chien de garde : AUCUNE proposée.** `proposition()` n'a rien
formulé, la marge reste large. **`10-timeout-s3.conf` n'a pas été touché** et ne
le sera pas sans Yann. ⓘ Pour le seul repérage : au rythme des deux dernières
nuits (+203 s/nuit) la marge actuelle partirait en une quinzaine de nuits —
**ce n'est pas une projection**, deux points ne font pas une pente.

ⓘ **25e centile, troisième matin d'affilée.** Le contrôle affiche
**−68 s/nuit** pendant que la nuit prend +70 s et la série +406 s en deux
nuits. La pente est le **25e centile des différences** : elle ignore par
construction les deux plus grosses hausses. Elle n'a vu ni le +153 s du 01/10,
ni le +336 s du 06/10, ni le +70 s de cette nuit. **Son silence ne vaut pas
acquittement.**

## 3. ⛔ Mémoire : NOUVEAU RECORD à 3 420 Mo — et la correction d'hier se corrige à son tour

```
⛔ après le rejeu d'archive            : 2 995 Mo  (3 002 le 06, 3 023 le 05)
⛔ après le score par régime           : 2 909 Mo  (2 853 le 06, 2 857 le 05)
⛔ après l'oubli de la fenêtre rejouée : 3 420 Mo  (3 364 le 06, 3 417 le 05)  ← jalon max, RECORD
```

Jalon max **3 420 Mo (+56)**, **620 Mo au-dessus du seuil**. Le record de
3 417 Mo du 05/10 est battu de 3 Mo.

```
29/09 1 671,3 o · 30/09 1 692,6 · 01/10 1 685,6 · 02/10 1 689,2
03/10 1 706,4  · 04/10 1 697,4 · 05/10 1 717,2 · 06/10 1 689,7 · 07/10 1 717,0
  → +27,3 o/ligne EN UNE NUIT, à fenêtre en HAUSSE de 1 027 balise-jours
  → écart au 01/10 : +31,4 o/ligne (il était retombé à +3,7 hier)
```

À taux constant, dans les deux sens : au taux du **06/10** la nuit aurait rendu
**3 364,8 Mo** (elle a rendu 3 420, soit **+55 Mo**) ; au taux du **01/10**,
**3 357,5 Mo** (soit **+62,5 Mo**).

⚠️ **CORRECTION DE LA CORRECTION — et c'est la leçon du jour.** Hier cette note
écrivait que la « hausse de fond de quatre nuits » annoncée les 04 et 05/10
était **rendue** (écart au 01/10 de +31,7 → +3,7 o/ligne). Cette nuit l'écart
**remonte à +31,4** et le jalon bat son record. À neuf nuits de recul, la série
**oscille entre 1 686 et 1 717 o/ligne sans pente nette**, et cette nuit est au
**haut** de la fourchette. **Ni hausse de fond, ni baisse** : une oscillation
d'environ 30 o/ligne dont la cause n'est pas identifiée. ⇒ **quatre points ne
font pas une pente — et sept non plus.** Le 28/09 nous l'a appris sur la purge,
le 05/10 sur la mémoire à la hausse, le 06/10 sur la mémoire à la baisse.
Le commentaire du jour sur KAN-4 porte cette double correction.

**Swap : pic 2 127,7 Mo (−47,8)**, le **plus bas** de la série, avec
**2 369 940 pages sorties (−137 753)**, le plus bas aussi — les deux baissent
ensemble, ce qui est cohérent. Mais le plancher tient : **8e nuit consécutive
au-dessus de 2,1 Go**. Pic système 3 617,2 Mo (−1,9).

**KAN-4 reste OUVERT, commenté** (`bw_jira_signaler`, HTTP 201 →
**29 commentaires**). Les trois conditions : jalon retombé → **NON (record)** ;
swap au pic ≈ 0 → **NON (2 127,7)** ; contrôle muet → oui, mais pente
**−9 Mo/nuit**, 25e centile, **silence inertiel**.

Le remède reste la **ligne en tuple** (§2.6, ≈ −1 030 o/ligne cumulés), après
la mesure `tuple` vs `namedtuple` à la sonde (leçon §2.3). ⚠️ Rappel de l'échec
de l'élagage de `units` (−124 Mo au lieu de −1 500) : les gains sont dans la
**structure**. **Rien de déployé côté mémoire depuis `af25efb` (21/09) —
17e nuit sans levier.**

## 4. ✅ Purge : nuit PROPRE, 126 857 lignes en 8 tranches — compteur **1 / 3**

Le bloc purge, en entier :

```
07:26:35  → purge model_score_zone : 126 857 ligne(s) effacée(s) en 8 tranche(s)
07:26:35  ⓘ purge model_character : rien avant le 2027-02-04 (première écriture 2026-08-08,
          rétention 180 j) — aucune requête lancée.
07:26:35  ✅ terminé (674 216 lignes écrites en base)
```

**Rien d'autre.** Point par point : aucune tranche en échec, **aucun 57014**
(`n_57014 = 0`) ; **126 857 lignes, nombre lisible**, aucun `?` ; **8 tranches**,
une par régime, **aucune sans `&regime=`** (le code du VPS n'a pas été écrasé
par un ancien) ; aucun `⚠️ compte model_score_zone : HTTP 500` ; **aucun
`des lignes RESTENT`** ; et ⓘ **la sonde « plus vieille journée » n'a pas
bronché** cette nuit (contrairement au 06/10), donc cette absence redevient
**pleinement concluante**.

Volume effacé : **131 640 · 131 657 · 131 554 · 125 782 · 124 678 · 126 857**.
Il **remonte** de 2 179 lignes — ⚠️ **ce n'est pas un signal**, il suit le
volume de la journée purgée (ici le **2026-09-29**). Ni dans un sens ni dans
l'autre.

**Compteur de fermeture : 1 / 3.** 6/3 le 05/10, remis à 0 le 06/10, reparti à
1 ce matin. **Fermeture pas avant trois nuits propres consécutives, et avec
l'accord de Yann** — la question n'est pas reposée aujourd'hui.

**KAN-5 commenté** (`bw_jira_signaler`, HTTP 201 → **12 commentaires**). Le
contrôle **n'a rien dit** ce matin, donc le garde-fou « un commentaire par jour
et par motif » était libre. Le commentaire porte **les trois mises au point
reportées d'hier** : (1) la purge du 06/10 **a abouti** et le constat du
contrôle sur-lit la liste `incidents` ; (2) le message neuf
`plus vieille journée illisible (essai 1/2)` est la **sonde**, pas une tranche ;
(3) le **garde-fou coupé en deux** (§7-bis d'hier), relevé à nouveau ce matin.

## 5. ✅ `n_57014 = 0` — aucun timeout nulle part

Série : **1 (28/09) · 2 · 0 · 3 (01/10) · 2 · 0 · 0 · 0 · 2 (06/10) ·
0 (07/10)**, et auparavant 10/09, 16/09.

⚠️ **Mais le dossier « base sous tension » ne se referme pas pour autant** —
c'est exactement l'erreur que la semaine dernière a déjà corrigée deux fois.
`model-verif/diagnostic_base_sous_tension_2026-09-29.sql` (lecture seule,
9 blocs, SQL Editor) **n'a toujours pas été joué**, le plan à balayage
séquentiel sur des statistiques périmées n'a pas bougé, et une nuit à zéro
n'est pas un correctif : il y en a eu **trois d'affilée** la semaine dernière
(03, 04, 05/10) avant que le 57014 revienne le 06. ⓘ Ce matin la hausse de
durée est du **calcul** (`cpu_s` +81,3, zéro 57014) : elle ne plaide **pas**
pour la base, et c'est une information en soi.

## 6. ⚠️ Position : le cri est parti sur **4** CONFIRMÉES — l'échéance corrigée d'hier était juste

```
07/10 06:00:54  ⛔ position : 11 balise(s) divergent du gel (10 j lus), dont 4 CONFIRMÉE(S) (≥ 10 j)
07/10 06:00:54  ⛔ position : 4 balise(s) CONFIRMÉE(S) — cri déposé pour envoi
07/10 07:26:49  msmtp … smtpstatus=250 smtpmsg='250 2.0.0 OK'          ← mail PARTI
07/10 07:26:48  ⚠️ push non parti (webhook)                            ← 3e ÉCHEC
```

| balise | 05/10 | 06/10 | 07/10 | état |
|---|---|---|---|---|
| `pioupiou:1333` (87 693 m) | 10 j | 10 j | **10 j** | CONFIRMÉE |
| `pioupiou:2171` (38 925 m) | 10 j | 10 j | **10 j** | CONFIRMÉE |
| `pioupiou:1388` (2 363 m) | 8 j | 9 j | **10 j** | **CONFIRMÉE ce matin** |
| `infoclimat:STATIC0491` (1 159 m) | 8 j | 9 j | **10 j** | **CONFIRMÉE ce matin** |
| `pioupiou:1378` (15 778 m) | — | 1 j | **2 j** | 10 j le 15/10 |
| `pioupiou:367` (6 764 m) | — | 1 j | **2 j** | 10 j le 15/10 |
| `pioupiou:1417` (829 m) | — | 1 j | **2 j** | 10 j le 15/10 |
| `pioupiou:1375` (747 m) | — | 1 j | **2 j** | 10 j le 15/10 |
| `pioupiou:1722` (631 m) | — | 1 j | **2 j** | 10 j le 15/10 |
| `pioupiou:1562` (481 m) | — | 1 j | **2 j** | 10 j le 15/10 |
| `pioupiou:1678` (422 m) | — | 1 j | **2 j** | 10 j le 15/10 |

✅ **2 → 4, exactement ce que la note corrigée du 06/10 annonçait**, et non le
2 → 13 que la note du 05/10 avait donné « confirmé à la nuit près ». La
correction d'hier était la bonne ; la prévision d'avant-hier était fausse. ⇒ ⓘ
**à retenir comme méthode** : une cohorte de compteurs n'est pas une échéance,
tant que les compteurs peuvent se réarmer — neuf l'ont fait en une nuit le
06/10.

**Les quatre cas, et ils sont de deux natures :**

- `pioupiou:1333` (**87,7 km**) et `pioupiou:2171` (**38,9 km**) : CONFIRMÉES
  depuis le 02/10, inchangées, candidates **« AUTRE balise »** — à ces
  distances, une correction de coordonnées n'a pas de sens.
- ⚠️ `pioupiou:1388` « Décollage Serre Michèle » (**2 363 m**) : elle
  **s'éloignait** (592 m le 05, 2 363 m le 06, stable à 2 363 m ce matin) et
  elle a franchi les 10 j. Elle **sort du lot « maille AROME »** et mérite
  d'être regardée pour elle-même.
- `infoclimat:STATIC0491` (**1 159 m**, distance stable) : seule rescapée du
  lot des petites distances, elle franchit 10 j. À 1 159 m, c'est le profil
  typique du **changement de maille** — probablement **aucune correction de
  coordonnées** nécessaire, à confirmer.

ⓘ Les **sept** nouvelles sont passées de 1 j à **2 j** (aucune n'est sortie) —
elles franchiraient 10 j le **15/10**. `pioupiou:1375` (747 m) figure aussi
parmi les **9 balises nées sous leur identifiant** de la nuit (`notee_depuis`,
lot L15-bis, toutes au 2026-09-25) : une balise neuve qui diverge n'est pas une
balise installée qui dérive.

Le canal reste **à front, pas à état** : le compte est passé de 2 à 4, donc cri.
Une balise qui reste confirmée ne recrie pas.

⛔ **WEBHOOK `push` : 0 / 3.** Troisième échec (`⚠️ push non parti (webhook)` à
07:26:48), **mail OK les trois fois** (`smtpstatus=250`). `bw_avertir_config`
n'a **rien** crié (`cri.BW_MODEL_SCORE_PING_URL` toujours daté du 01/09) ⇒ la
variable `BW_WEBHOOK_URL` **est présente**, l'échec est au `POST` lui-même.
**Rien n'a été testé ici** (hors périmètre : aucune écriture hors Jira). ⇒ **le
canal d'urgence est maintenant cassé sur trois cris réels** (30/09, 02/10,
07/10) — §10 n° 4.

Le contrôle **ne corrige rien** (règle de `freeze_balises.geler`) : **geste
attendu de Yann** — trancher, pour chacun des quatre cas, correction de
coordonnées **ou** AUTRE balise, puis poser `position_suspecte` +
`position_note` sur `station_zone` par `.sql`.

## 7. ⛔ TROUVÉ CE MATIN : les témoins du mélange PASSENT SOUS LA BARRE

```
⛔ témoins du mélange : sur 7 605 balise-jours × échéance, le mélange fait
   3,3621 km/h contre 3,3429 pour le meilleur membre a priori
   (gain −0,6 %, mélange devant dans 49,2 % des cas) ;
   contre la moyenne UNIFORME, sur 1 125 : 3,4255 vs 3,5985 (gain 4,8 %)
```

| | 05/10 | 06/10 | 07/10 |
|---|---|---|---|
| gain contre le meilleur membre a priori | 7,4 % | 5,5 % | **−0,6 %** |
| mélange devant, en % des cas | 55,9 % | 55,4 % | **49,2 %** |
| gain contre la moyenne uniforme | 6,0 % | 4,9 % | **4,8 %** |

⛔ **Troisième nuit de recul, et cette fois la barre est franchie** : le mélange
est **derrière** le meilleur membre a priori, et **devant moins d'une fois sur
deux**. La note du 06/10 le signalait « à resurveiller » — c'est arrivé la nuit
suivante.

⚠️ **À ne pas sur-interpréter pour autant, et pour une raison chiffrée** :
l'erreur absolue a **bondi** (3,3621 km/h contre 2,7173 hier, soit +24 %), donc
la journée notée était **beaucoup plus venteuse**. Un mélange perd souvent son
avantage quand l'amplitude monte, et le gain contre la moyenne **uniforme**
tient (**4,8 %**, quasi inchangé) — ce qui dit que la **pondération** marche
toujours, c'est la comparaison au **meilleur membre** qui flanche. **Une nuit
ne fait pas une pente** (c'est trois fois la même leçon cette semaine).
⇒ **aucun motif Jira créé**, aucun ticket neuf : §10 n° 3, question à Yann.

## 8. Hors périmètre, relevé sur la nuit du 06→07

- ✅ **Écarts au recalcul indépendant : 3** (3 le 06, 7 le 05) — toujours
  **tous en `fcstagrume`**, toujours le même motif (« 0 ou 1 h appariée ici
  (< 6) mais la base porte une ligne »), et **aucune reprise d'hier** :
  `aemet:9218A` (+24 h), `windsmobi:ffvl-5053` (+6 h),
  `infoclimat:STATIC0117` (+24 h). Motif d'appariement qui frappe au hasard,
  pas un lot figé — quatrième confirmation.
- `lignes_daily` **69 774** (−128) · `lignes_glissant` **10 554** (−58) ·
  `lignes_regime` **120 745** (−34) · `lignes_score_zone` **131 299** (−92).
- Observations du jour : **3 749 balises** (veille 3 753).
- Stabilité des rangs : **`tau = 0,742` sur 67 cases**, 0 jour partagé
  (0,784 sur 65 le 06 ; 0,788 sur 58 le 05). ⚠️ `tau` **baisse** trois nuits de
  suite pendant que le nombre de cases monte — à garder en tête à côté du §7.
- Témoin du corrigé : le vrai antécédent gagne **15,4 %**, celui d'une AUTRE
  balise **−3,4 %** ⇒ part imputable au site **18,7 points** (16,3 hier).
  Témoin FIN : le S2 gagne **14,9 %** sur le brut, le fin **+11,1 points** de
  plus sur le S2 contre **−1,2** aux cellules tournées ⇒ part du secteur et de
  l'heure **12,3 points** (10,8 hier). **Les deux témoins se renforcent** —
  à noter, puisque le témoin du mélange, lui, flanche.
- Mélange multi-modèle : **7 981** balise×échéance avec poids sur 30 j de cache
  (+6 h : 2 629 `bw_mix`, 414 témoins uniformes, 198 sans poids).
- Référence combinée : médiane **`k = 0,162`** (0,155 le 06, 0,144 le 05) sur
  3 698 balises / 3 813 climatologisées ; **253** balises avaient un ρ hors
  [0, 1] ramené à la borne (277 le 06, 297 le 05 — **quatrième nuit
  d'amélioration**).
- Murphy : **66 396** cases, dont **64 287** décomposées, **266** balises
  dehors (inchangé depuis le 01/10). Tous les modèles restent en
  « AMPLITUDE » ou « TIMING » selon l'habitude ; `bw_mix_u` +6 h reste le seul
  avec un SS positif (**+0,020**).
- FDR : 6 927 tests / 1 831 survivants à BH α=0,1 (brut, 106 rangs retirés sur
  1 110 publiés) ; 6 629 / 1 369 (corrigé, 107 retirés sur 698).
- Duel apparié : 65 133 lignes en lead 6 (1 214 retirées), 23 976 en lead 24
  (467). `agrume_pi ↔ bw_mix` +6 h : médiane **+0,370** → `b_better` ;
  +24 h : **+0,516** → `b_better`. `agrume ↔ agrume_pi` +6 h : médiane
  **+0,005** (IC95j [+0,002 ; +0,008]) → `b_better`.
  `agrume ↔ meteofrance_arome_france_hd` +6 h : médiane **−0,002** →
  `a_better`. `arome_r2 ↔ meteofrance_arome_france_hd` +6 h : médiane
  **+0,128** → `b_better`. ⓘ Tous les verdicts sont **inchangés** depuis hier.
- Manches : **40 nuits** suivies depuis le 24/08, **665 cases**
  zone×lead×modèle avec au moins une manche gagnée.
- Pression : 17 887 lignes, 682 points de prévision portent `pmsl`,
  **862 appariées** (médiane 18,2 km).
- Événements notés : **27 492** combinaisons publiables, **26 617** écartées
  sous le quorum de 8.
- ⓘ R2 : **4 écritures**, plafond 10, **159,1 Mo** — rien près du plafond.
  `model_scores.json` 114 991 Ko, `model_scores_light.json` 7 206 Ko
  (528 Ko gzippé).
- `mutations_memoire` : **aucune ligne** au journal de la nuit ; dette
  antérieure de **3 mutations non vues** (2, 5, 13), inchangée.
- Lots : 5 385 entrées écartées en `doublon_de` (L17), 344 en `notee_depuis`
  (L15-bis) ; 7 182 balise-jours écartés au rejeu pour naissance postérieure ;
  **9 balises nées sous leur identifiant** (L15-bis, toutes au 2026-09-25).
- `model_character` : 410 952 accumulateurs avancés sur 410 952 envoyés.

## 9. Tickets — trois commentaires, aucune transition, aucune création

États relevés **avant** d'écrire (GET `/rest/api/3/issue/…`, HTTP 200) :

| ticket | motif | statut | `statusCategory` | maj avant | comm. avant |
|---|---|---|---|---|---|
| KAN-3 | `bw-pente-duree` | **Terminé** | `done` | 06/10 13:26 | 17 |
| KAN-4 | `bw-pente-memoire` | **À faire** | `new` | 06/10 13:26 | 28 |
| KAN-5 | `bw-purge-57014` | **À faire** | `new` | 06/10 07:30:54 | 11 |

- **KAN-4 (mémoire) — OUVERT, commenté** (`bw_jira_signaler`, HTTP 201 →
  **29**). Les trois conditions de fermeture échouent (§3). Le commentaire
  porte les trois franchissements, la courbe du coût par ligne sur neuf nuits,
  les **deux calculs à taux constant**, et la **correction de la correction**
  du 06/10.
- **KAN-5 (purge) — OUVERT, commenté** (`bw_jira_signaler`, HTTP 201 →
  **12**). Le contrôle **n'a rien dit** aujourd'hui, le garde-fou était libre.
  Le commentaire porte la nuit propre (126 857 / 8 tranches / zéro 57014), le
  compteur **1/3**, et les **trois mises au point reportées d'hier**.
- **KAN-3 (durée, Terminé) — COMMENTÉ, NON rouvert** (`POST` direct, HTTP 201
  → **18**). La durée **augmente** : la consigne s'applique. Le commentaire
  porte les chiffres, la **répartition par étape et son changement de
  signature**, le double découplage (`cpu_s` +81,3 et `n_57014` = 0 ⇒ du
  calcul ; volumes en baisse ⇒ pas du volume), le coût par ligne de `regime` à
  **14,86 ms**, le rappel du **25e centile**, la divergence des deux lectures
  sur `bw-regime-sensibilite`, et le fait qu'**aucune remontée du garde n'est
  proposée**. **Statut inchangé : Terminé / `done`.**
- **Aucun motif neuf créé.** `bw-regime-sensibilite` reste en veille (lectures
  divergentes, §2). Le recul des témoins du mélange (§7) **n'a pas de ticket** :
  une nuit, et l'erreur absolue a bondi de 24 %. Le cri de position et la panne
  du webhook **ne sont pas de la dérive** (partage des canaux en tête de
  `bw_jira.sh` : Jira = dérive ; mail + push = les ⛔).

Vérification après écriture (GET, HTTP 200) : **KAN-3 Terminé/`done`,
18 commentaires, maj 07/10 09:15:25** · **KAN-4 À faire/`new`,
29 commentaires, maj 07/10 09:15:24** · **KAN-5 À faire/`new`,
12 commentaires, maj 07/10 09:15:25**.
⛔ Aucun ticket fermé, aucune transition jouée, aucun ticket créé, aucune
réouverture.

## 10. Ce qui a été touché

**VPS** : rien hors les **trois** commentaires Jira. `tail -n 3` du registre,
`journalctl` (notation de la nuit et contrôle du jour, **sans élévation de
droits**), `list-timers`, `controle_quotidien.py --verbeux` (lu par un tube,
aucun fichier intermédiaire), lecture de `bw_jira.sh` (en-tête,
`bw_jira_chercher`, `bw_jira_signaler`), **six GET Jira** (trois avant, trois
après), listage et lecture des **deux** dossiers de jetons
(`~/.balise-watch-etat-alertes` et `/var/lib/bw-model-verif`).
**Aucun `systemctl start/restart/daemon-reload`, aucun `enable`, aucun SQL
joué, aucun `rsync`, rien écrit dans `~/balise-watch` ni dans `/etc`.**
Écritures : les textes de KAN-4 et KAN-5 par `bw_jira_signaler`, celui de
KAN-3 par `POST` direct (tous dans un `mktemp -d` en 700 effacé après), et les
**trois jetons du jour** dans `~/.balise-watch-etat-alertes`.
`~/.balise-watch-alertes.env` **sourcé**, jamais lu par valeur ; `curl -K -`,
jamais `-u`. Les deux scripts passés au VPS l'ont été par `ssh 'bash -s' <`
depuis le Mac — **rien n'a été déposé sur le VPS**.

**Mac** : cette note et son miroir git, plus deux scripts jetables dans
`/Users/yann/` (hors dépôt : `bw-jira-get-07-10.sh`, `bw-jira-post-07-10.sh`,
`bw-commit-07-10.sh`) — **pas de `git push`**.

Miroir git : `notes-projet/verdict-pente-07-10.md`, commité en local depuis la
racine du dépôt serveur — **commit `7e4c40e`**. Pas de `git push`.

## 11. Ce qui reste — et ce qui demande Yann

1. ⛔ **DEUXIÈME NUIT DE HAUSSE : 5 227 s, marge 2 873 s = 35,5 % du garde, le
   plus bas de la série.** +406 s en deux nuits. C'est du **calcul**
   (`cpu_s` +81,3 s) et **pas** de l'attente (`n_57014` = 0 partout).
   ⚠️ **Mais la signature a changé** : 85 % de la hausse est **hors étapes**
   cette nuit (contre 88 % **dans** les étapes hier), et `regime` **baisse**.
   KAN-3 **commenté**, laissé **Terminé**, **aucune remontée du garde
   proposée**. ⇒ **Le hors-étapes n'est pas instrumenté.** Veux-tu qu'une
   session pose des jalons de temps sur le bloc hors étapes (publication,
   Murphy, événements, pression, duels, purge) ? C'est une **écriture dans
   `run.sh`**, donc ta décision.
2. ⚠️ **`bw-regime-sensibilite` : LES DEUX LECTURES DIVERGENT, à toi de
   trancher.** L'arbitrage du 29/09 (« la hausse s'additionne deux nuits de
   suite ») **n'est pas rempli** : `regime` a perdu 25,4 s et son coût par
   ligne est passé de 15,07 à **14,86 ms**. Le seuil posé par la note d'hier
   (« au-dessus de 14,5 ms ») **est franchi**. Motif Jira neuf, veille
   prolongée, ou seuil à redéfinir ? **Rien n'a été créé.**
3. ⛔ **TROUVÉ CE MATIN : les témoins du mélange passent SOUS la barre du
   « devant une fois sur deux ».** Gain contre le meilleur membre a priori :
   7,4 % → 5,5 % → **−0,6 %** ; devant dans **49,2 %** des cas (55,4 % hier).
   ⚠️ À pondérer : l'erreur absolue a bondi de **24 %** (journée beaucoup plus
   venteuse) et le gain contre la moyenne **uniforme** tient (4,8 %) — donc la
   pondération marche, c'est la comparaison au meilleur membre qui flanche.
   **Une nuit ne fait pas une pente**, aucun ticket créé. ⇒ **faut-il un motif
   Jira `bw-melange-sous-barre` si la nuit du 07→08 confirme ?**
4. ⛔ **LE WEBHOOK `push` EST CASSÉ SUR TROIS CRIS RÉELS : 0 / 3** (30/09,
   02/10, **07/10**), mail OK les trois fois. La variable `BW_WEBHOOK_URL` est
   **présente** (pas de cri de `bw_avertir_config`), donc c'est le `POST` qui
   échoue. Les deux questions du 30/09 sont toujours sans réponse, et elles
   deviennent pressantes : veux-tu qu'une session éprouve `BW_WEBHOOK_URL` par
   un `curl` de test **hors run**, ou préfères-tu regarder toi-même ? Et
   faut-il un motif Jira pour une panne de canal, alors que `bw_jira.sh`
   réserve Jira à la dérive ?
5. ⛔ **MÉMOIRE (KAN-4) : NOUVEAU RECORD 3 420 Mo**, +620 au-dessus du seuil,
   coût par ligne **1 717,0 o (+27,3)** à fenêtre en hausse de 1 027
   balise-jours. ⚠️ **La correction d'hier se corrige** : l'écart au 01/10
   remonte de +3,7 à **+31,4 o/ligne**. À neuf nuits, la série **oscille entre
   1 686 et 1 717 sans pente nette** — ni hausse de fond, ni baisse. KAN-4
   reste **ouvert**. **Aucun levier déployé depuis le 21/09 (17 nuits)** : la
   **ligne en tuple** reste le remède, après la mesure `tuple` vs
   `namedtuple` à la sonde.
6. ✅ **PURGE PROPRE : compteur 1 / 3.** 126 857 lignes en 8 tranches, zéro
   57014, sonde intacte. La question de la fermeture de KAN-5 **n'est pas
   reposée** — pas avant 3/3.
7. ⛔ **GARDE-FOU CASSÉ (relevé à nouveau ce matin) : les jetons « un
   commentaire par jour et par motif » vivent dans DEUX dossiers.** Le contrôle
   écrit dans `/var/lib/bw-model-verif` (`controle_quotidien.sh:98` passe
   `$ETAT`), la routine dans `$HOME/.balise-watch-etat-alertes`. Relevé
   aujourd'hui : `bw-purge-57014` = 2026-10-06 côté contrôle, 2026-10-05 côté
   routine **avant** notre écriture. **Correctif à décider par toi** : soit le
   contrôle cesse de passer `$ETAT` (une ligne), soit les deux passent
   explicitement par le même dossier. Rien n'a été touché.
8. ⚠️ **LE CONSTAT DU CONTRÔLE SUR-LIT LES REJEUX.** Il a écrit à KAN-5 le
   06/10 « purge **en échec** » alors que la tranche avait été rejouée et la
   purge avait abouti. Il lit la liste `incidents`, qui garde l'avertissement
   après un rejeu réussi. ⇒ dans `controle_quotidien.py`, un
   `⚠️ purge … rejouée dans 5 s` suivi d'un `→ purge … N ligne(s) effacée(s)`
   **ne devrait pas** compter comme un échec. (Le sujet de KAN-5 porte encore
   cette formulation fausse.)
9. ⚠️ **POSITION : 4 CONFIRMÉES, cri parti, geste attendu de toi.**
   `pioupiou:1333` (87,7 km) et `pioupiou:2171` (38,9 km) → candidates
   **AUTRE balise** ; ⚠️ `pioupiou:1388` (2 363 m, s'était **éloignée** de
   592 m) → à regarder pour elle-même, elle sort du lot « maille » ;
   `infoclimat:STATIC0491` (1 159 m, stable) → profil **changement de maille**,
   probablement sans correction de coordonnées. Trancher chaque cas, puis poser
   `position_suspecte` + `position_note` sur `station_zone` par `.sql`. ⓘ Les
   **sept** nouvelles sont à 2 j (10 j le **15/10**).
10. ⛔ **LE DOSSIER « BASE SOUS TENSION » n'est pas refermé par une nuit à
    zéro.** `diagnostic_base_sous_tension_2026-09-29.sql` (lecture seule,
    9 blocs) **attend toujours d'être joué dans le SQL Editor**. Il y a eu
    **trois** nuits à `n_57014 = 0` la semaine dernière avant que le 57014
    revienne le 06/10. ⓘ En revanche la hausse de durée de cette nuit est du
    **calcul**, pas de l'attente : elle ne plaide pas pour la base.
11. ⛔ **LE CRI DE POSITION EST « À FRONT »** (démontré une fois de plus :
    2 → 4 ⇒ cri). Question du 01/10, toujours ouverte : veux-tu que le
    garde-fou **recrie** tant qu'une balise reste confirmée (même motif, une
    fois par jour), ou qu'il se taise ?
12. ✅ **La routine est à l'heure ce matin** (07:09 UTC pour 07:07), après cinq
    matinées de retard et deux jours sans tir. **Une matinée ne fait pas une
    réparation** : à revérifier demain avant de considérer le point n° 11
    d'hier comme réglé.
13. ⚠️ **`tau` baisse trois nuits de suite** (0,788 → 0,784 → **0,742**) tandis
    que le nombre de cases monte (58 → 65 → 67). À lire à côté du §7 : les deux
    disent peut-être la même chose sur la journée notée.
14. `mutations_memoire` : 3 mutations non vues (dette antérieure, inchangée).
