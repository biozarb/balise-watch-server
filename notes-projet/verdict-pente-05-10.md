# Verdict de pente du 05/10/2026 — la mémoire BAT SON RECORD (3 417 Mo, +19,9 o/ligne en une nuit, à volume étale), la purge passe à 6/3, la durée est au plus bas de la série, et la cohorte de onze balises est à deux nuits de 10 j

## 11:20 — routine Balise Watch (tirée à 08:56 UTC pour 07:07 ; ~1 h 50 de retard), lecture seule sur le VPS + deux commentaires Jira

**Étape 0 faite, et elle est nette.** `git log --oneline --since=midnight` :
**aucun commit du jour**, ni dans `balise-watch-server` (dernier :
`a4dbc65`, 04/10) ni dans le dépôt principal (dernier : `10bb605`,
01/10). `project_read` de `claude/verdict-pente-05-10.md` → « No doc » ;
`claude/verdict-pente-04-10.md` lu en entier. Jetons `cri.jira.*` avant
écriture : `bw-pente-memoire` et `bw-purge-57014` au **04/10 19:56**
(le run d'hier soir), `bw-pente-duree` au **01/10**. `notes-projet/README.md`
relu. ⇒ **premier et seul run du jour, rien à fusionner, rien à ne pas
refaire.**

⚠️ **Quatrième matin de suite hors horaire** : tir à 08:56 UTC pour 07:07
(hier : 17:51 pour 07:00 ; les 02 et 03/10 : pas de tir du tout). Le VPS,
lui, est à l'heure : `bw-model-controle.timer` a tiré à **07:30:41**
(prochain mardi 06/10 07:30:52) et `bw-model-score.service` a tourné.
**Le décalage est côté planification de la routine**, pas serveur.

## 1. Les nuits, bout à bout

| | 30/09 | 01/10 | 02/10 | 03/10 | 04/10 | 05/10 |
|---|---|---|---|---|---|---|
| durée | 4 992 s | 5 145 s | 4 865 s | 4 944 s | 4 876 s | **4 821 s (−55)** |
| garde / marge | 8 100 / 3 108 | 8 100 / 2 955 | 8 100 / 3 235 | 8 100 / 3 156 | 8 100 / 3 224 | **8 100 / 3 279 (+55)** |
| marge en % du garde | 38,4 % | 36,5 % | 39,9 % | 39,0 % | 39,8 % | **40,5 %** |
| `cpu_s` | 4 012,9 | 3 962,7 | 3 833,9 | 3 961,3 | 3 964,5 | **3 853,3 (−111,2)** |
| jalon max | 3 347 Mo | 3 338 Mo | 3 350 Mo | 3 389 Mo | 3 376 Mo | **3 417 Mo (+41) RECORD** |
| au-dessus du seuil | +547 | +538 | +550 | +589 | +576 | **+617** |
| swap au pic | 2 161,8 | 2 209,3 | 2 111,0 | 2 301,7 | 2 592,1 | **2 218,3 (−373,8)** |
| pages sorties | 2 612 719 | 2 341 013 | 1 963 835 | 2 684 787 | 2 338 891 | **2 579 457 (+240 566)** |
| pic système | 3 606,2 | 3 593,6 | 3 606,1 | 3 625,3 | 3 624,7 | **3 600,5 (−24,2)** |
| fenêtre rejouée | 2 073 480 | 2 076 504 | 2 079 507 | 2 082 544 | 2 085 523 | **2 086 473 (+950)** |
| o / ligne rejouée | 1 692,6 | 1 685,6 | 1 689,2 | 1 706,4 | 1 697,4 | **1 717,3 (+19,9)** |
| `n_57014` | 0 | 3 | 2 | 0 | 0 | **0** |
| purge (lignes / tranches) | 129 666 / 8 | 133 646 / 8 | 131 640 / 8 | 131 657 / 8 | 131 554 / 8 | **125 782 / 8** |
| lancement / résultat | timer/success | timer/success | timer/success | timer/success | timer/success | **timer/success** |

Nuit **comparable** : `lancement=timer`, `exec_status=0`, `oom=0`,
`result=success`, 05:58:11 → 07:18:44, `✅ terminé (642 068 lignes
écrites en base)`. Rien à écarter.

Contrôle de ce matin, **tir régulier 07:30:41** (prochain 06/10
07:30:52) : « **67 relevé(s), 46 comparable(s)** ; durée : 10 points,
pente **−68 s/nuit** ; mémoire : 10 points, pente **−9 Mo/nuit** ;
horizon 30 j ; seuil 2 800 Mo » puis « rien à dire : pente plate/négative,
ou échéance hors horizon ». **Il s'est tu sur les trois motifs** ⇒ aucun
commentaire Jira de sa part, la règle « un commentaire par jour et par
motif » ne bloquait rien (jetons confirmés au 04/10 avant écriture).

## 2. ✅ Durée : au plus bas de la série suivie

`4 865 · 4 944 · 4 876 · **4 821**`. La marge sous le garde atteint
**3 279 s = 40,5 % de 8 100**, la meilleure de toute la série. `cpu_s`
**3 853,3 (−111,2)** : du temps d'horloge en moins ET du calcul en moins,
l'inverse exact du découplage du 01/10.

| étape | 02/10 | 03/10 | 04/10 | 05/10 |
|---|---|---|---|---|
| `regime` | 1 574,3 | 1 661,4 | 1 624,7 | **1 643,3 (+18,6)** |
| `glissant` | 923,7 | 957,3 | 994,6 | **929,8 (−64,8)** |
| `stabilite` | 261,8 | 290,6 | 275,2 | **288,2 (+13,0)** |
| `rejeu` | 71,6 | 74,3 | 80,8 | **74,0 (−6,8)** |
| somme des quatre | 2 831,4 | 2 983,6 | 2 975,3 | **2 935,3 (−40,0)** |

⚠️ **À noter, et ce n'est pas une dérive** : `lignes_regime` saute à
**121 418 (+2 558)** et `lignes_score_zone` à **132 089 (+2 555)** — le
plus gros volume de régime de la série. Et pourtant `regime` ne monte que
de 18,6 s : **13,53 ms/ligne** contre 13,67 hier. Série du coût par
ligne : **13,39 (01/10) · 13,24 · 14,02 · 13,67 · 13,53 (05/10)** — elle
oscille autour de 13,6 **sans tendance**, et cette nuit elle baisse alors
que le volume monte de 2,2 %.

⇒ **L'arbitrage du 29/09 tient : `bw-regime-sensibilite` reste en simple
veille.** La condition « la hausse s'additionne deux nuits de suite »
n'est pas remplie — c'est l'inverse qui se produit. **Aucun motif neuf
créé.**

⚠️ **KAN-3 n'a PAS été commenté et n'a PAS été rouvert.** La consigne est
de commenter *quand la durée augmente* : elle **baisse** (−55 s sur la
nuit, **−324 s depuis le 01/10**). La pente du contrôle est à
**−68 s/nuit** et `controle_quotidien.proposition()` **n'a rien
formulé** ⇒ **aucune remontée du chien de garde n'est proposée**, et
`10-timeout-s3.conf` n'a pas été touché. Son jeton
`cri.jira.bw-pente-duree` reste au **01/10**, intact.

ⓘ Rappel de méthode, deux fois utile : la pente du contrôle est le **25e
centile des différences**, elle ignore par construction les deux plus
grosses hausses — c'est pourquoi elle n'avait pas vu le +153 s du 01/10.
Et `bw_jira_chercher` filtre sur `statusCategory != Done` : un
`bw_jira_signaler bw-pente-duree` **créerait un ticket neuf** au lieu de
commenter KAN-3 ; il faudrait un `POST /rest/api/3/issue/KAN-3/comment`
direct, comme le 01/10.

⇒ **Le +153 s du 01/10 est confirmé pour la deuxième fois** : `n_57014`
fait **3 · 2 · 0 · 0 · 0** et la durée fait
**5 145 · 4 865 · 4 944 · 4 876 · 4 821**. Les deux séries se suivent, et
rien n'a été déployé entre-temps : c'est la base qui s'est calmée.

## 3. ⛔ Mémoire : RECORD de la série, et la hausse est maintenant propre à lire

Les trois franchissements de cette nuit, tous au-dessus du seuil de 2 800 :

```
⛔ après le rejeu d'archive            : 3 023 Mo  (3 004 le 04, 3 035 le 03)
⛔ après le score par régime           : 2 857 Mo  (2 813 le 04, 2 817 le 03)
⛔ après l'oubli de la fenêtre rejouée : 3 417 Mo  (3 376 le 04, 3 389 le 03)  ← jalon max
```

Jalon max **3 417 Mo = RECORD de toute la série suivie** (précédent
3 389 le 03/10), **617 Mo au-dessus du seuil**.

Coût par ligne rejouée, la mesure qui neutralise la croissance de la
fenêtre :

```
29/09 1 671,3 o · 30/09 1 692,6 · 01/10 1 685,6
02/10 1 689,2  · 03/10 1 706,4 · 04/10 1 697,4 · 05/10 1 717,3
  → +19,9 o/ligne EN UNE NUIT (plus forte hausse de la série)
  → +31,7 o/ligne (+1,88 %) depuis le 01/10
```

⛔ **Et cette nuit, l'argument est propre : le volume est étale.** La
fenêtre n'a grandi que de **+950 balise-jours** (2 086 473), contre
+2 979 la nuit d'avant. Vérification à taux constant :

- au taux du **04/10** (1 697,4 o/ligne) la nuit aurait rendu
  **3 376,5 Mo** ; elle a rendu **3 417**, soit **+40,5 Mo** ;
- au taux du **01/10** (1 685,6 o/ligne) elle aurait rendu **3 354,0 Mo**,
  soit **63,0 Mo de moins** que le relevé.

⇒ les +41 Mo ne sont **pas** un effet de volume : à volume quasi
constant, le jalon monte quand même. **Quatrième nuit de hausse de fond.**
La lecture « plate, pas en baisse » du 01/10 est définitivement démentie,
et la correction posée hier est confirmée par une nuit où le volume ne
peut plus servir d'explication.

**Swap : pic 2 218,3 Mo (−373,8** après le record de 2 592,1 hier**)**,
mais **2 579 457 pages sorties (+240 566)** — c'est un échange **moins
haut et plus long**, pas une détente. Le plancher d'environ **2,2 Go**
est toujours là, sixième nuit de suite au-dessus de 2,1 Go. Pic système
3 600,5 Mo (−24,2), le plus bas depuis le 01/10. La condition de
fermeture « swap au pic ≈ 0 » reste hors de portée.

⚠️ **Le silence du contrôle se dégrade encore.** Sa pente mémoire :
**−30** (quatre matinées) → **−24** (01/10) → **−13** (04/10) →
**−9 Mo/nuit** aujourd'hui. Elle remonte vers zéro **pendant que le jalon
bat son record**. Étant le 25e centile des différences, elle ignore par
construction les deux plus grosses hausses de la fenêtre : le **+41 Mo**
de cette nuit et le **+39** du 03/10 **ne peuvent pas** y apparaître.
Silence **inertiel**, pas acquittement — et à ce rythme la pente passera
positive d'elle-même d'ici deux ou trois nuits, ce qui déclenchera le cri
du contrôle sans qu'il se soit rien passé de neuf.

Le remède reste la **ligne en tuple** (§2.6 de l'enquête, ≈ −1 030 o/ligne
cumulés), avec la mesure `tuple` vs `namedtuple` à la sonde **AVANT** de
choisir (leçon §2.3). ⚠️ Rappel de l'échec de l'élagage de `units`
(−124 Mo au lieu de −1 500) : les gains sont dans la **structure**, pas
dans le nombre de clés. **Rien n'est décidé, rien n'est codé, et rien
n'est déployé côté mémoire depuis `af25efb` (21/09)** — **quinzième nuit
sans levier**.

## 4. ✅✅✅ Purge : sixième nuit propre d'affilée — **6 / 3**

```
05/10 07:18:29  → purge model_score_zone : 125 782 ligne(s) effacée(s) en 8 tranche(s)
                ⓘ purge model_character : rien avant le 2027-02-04 (première écriture
                  2026-08-08, rétention 180 j) — aucune requête lancée.
                ✅ terminé (642 068 lignes écrites en base)
```

Les six points de l'attendu, vérifiés un par un sur la nuit nouvelle :

- **8 tranches, une par régime, toutes réussies** — aucune ligne
  `⚠️ purge model_score_zone (?as_of=eq.J&regime=eq.R) : HTTP 500 57014`.
- **Nombre de lignes effacées lisible** (`Content-Range` de chaque
  `DELETE`). **Aucun `?`**.
- **Aucune tranche sans `&regime=`** ⇒ le code du VPS n'a pas été écrasé
  par un ancien.
- **Aucun `⚠️ compte model_score_zone : HTTP 500`** : le `HEAD count=exact`
  sur `as_of < seuil` a bien disparu.
- **Aucun `des lignes RESTENT (plus vieille journée : J)`** — la seule
  phrase qui dirait qu'il reste quelque chose. **Rien ne reste en base.**
- **8 tranches, pas 540 `DELETE` à vide** : plus de repli aveugle sur
  `seuil − 60 j`.

Volume effacé, nuit après nuit : **129 666 · 133 646 · 131 640 ·
131 657 · 131 554 · 125 782**. Le recul d'environ **5 800 lignes** suit le
volume de la journée purgée (les 8 tranches sont toutes présentes et
toutes lisibles) — ⚠️ **ce n'est pas un échec de tranche**, et c'est
exactement le genre de chiffre qu'il ne faut pas sur-interpréter (leçon
du 28/09).

⇒ **Décompte : 6 / 3.** `e83d814` tient. La barre posée — trois nuits
consécutives sans 57014 dans le bloc purge **et** un nombre de lignes
effacées lisible — est franchie du double.
**KAN-5 reste ouvert : sa fermeture est SOUMISE à Yann** (§7, §10), et la
question est posée sans réponse depuis hier.

## 5. ✅ `n_57014` : troisième nuit à zéro

Aucun 57014 nulle part dans le journal de la nuit. Série :
**1 (28/09) · 2 (29/09) · 0 (30/09) · 3 (01/10) · 2 (02/10) · 0 (03/10) ·
0 (04/10) · 0 (05/10)**, et auparavant 10/09, 16/09.

⚠️ **Trois nuits à zéro ne sont pas un correctif.**
`model-verif/diagnostic_base_sous_tension_2026-09-29.sql` (lecture seule,
9 blocs, SQL Editor) **n'a toujours pas été joué**, et le plan à balayage
séquentiel sur des statistiques périmées n'a pas bougé. Le 30/09 était
déjà à 0 et le 01/10 a battu le record à 3 : c'est une base qui respire
par à-coups, pas une base réparée. Elle **se compte et se signale sans
dramatiser**, et elle reste la cause probable du prochain pic de durée.

## 6. ⛔ Position : la cohorte est à **8 j** — onze balises franchissent 10 j **le 07/10**, dans deux nuits

```
05/10 05:59:26  ⛔ position : 15 balise(s) divergent du gel (10 j lus), dont 2 CONFIRMÉE(S) (≥ 10 j)
                (aucun cri déposé — compte de CONFIRMÉES inchangé depuis le 02/10)
```

| balise | 03/10 | 04/10 | 05/10 | 10 j le |
|---|---|---|---|---|
| `pioupiou:1333` (87 693 m) | 10 j | 10 j | **10 j** | CONFIRMÉE |
| `pioupiou:2171` (38 925 m) | 10 j | 10 j | **10 j** | CONFIRMÉE |
| `infoclimat:STATIC0491` (1 159 m) | 6 j | 7 j | **8 j** | **07/10** |
| `pioupiou:1344` (1 050 m) | 6 j | 7 j | **8 j** | **07/10** |
| `pioupiou:2026` (1 038 m) | 6 j | 7 j | **8 j** | **07/10** |
| `pioupiou:1746` (914 m) | 6 j | 7 j | **8 j** | **07/10** |
| `pioupiou:1691` (833 m) | 6 j | 7 j | **8 j** | **07/10** |
| `pioupiou:1338` (596 m) | 6 j | 7 j | **8 j** | **07/10** |
| `pioupiou:1388` (592 m) | 6 j | 7 j | **8 j** | **07/10** |
| `pioupiou:1618` (473 m) | 6 j | 7 j | **8 j** | **07/10** |
| `pioupiou:2047` (391 m) | 6 j | 7 j | **8 j** | **07/10** |
| `pioupiou:2125` (374 m) | 6 j | 7 j | **8 j** | **07/10** |
| `pioupiou:2052` (266 m) | 6 j | 7 j | **8 j** | **07/10** |
| `pioupiou:1354` (1 847 m) | 3 j | 4 j | **5 j** | 10/10 |
| `pioupiou:1334` (61 156 m) | 2 j | 2 j | **1 j** | compteur réarmé (2e fois) |

⇒ **L'échéance d'hier est confirmée à la nuit près : le 07/10 au matin, le
compte de CONFIRMÉES passera de 2 à 13.** C'est un front, donc **le cri
partira** — et **par mail seulement** si le webhook n'est pas réparé d'ici
là. Il reste **deux nuits**.

Le canal reste **à front, pas à état** (démontré dans les deux sens : cri
le 02/10 quand le compte est passé de 1 à 2, silence les 03, 04 et 05 à
compte égal). Une balise qui reste confirmée **ne recrie pas**.

⛔ **Webhook `push` : toujours 0 / 2**, et toujours pas éprouvé. Échec au
premier vrai cri (30/09), échec au deuxième (02/10) pendant que le mail
partait proprement (`exitcode=EX_OK`). Pas de cri cette nuit, donc pas de
nouvelle tentative : le compteur reste à 0/2. `bw_avertir_config` n'a rien
crié (`cri.BW_MODEL_SCORE_PING_URL` toujours daté du 01/09) ⇒ la variable
`BW_WEBHOOK_URL` est présente, l'échec est au `POST`. **Rien n'a été testé
ici** (hors périmètre : aucune écriture hors Jira).

Le contrôle **ne corrige rien** (règle de `freeze_balises.geler`) :
**geste attendu de Yann** — trancher, pour chacun des 15 cas, correction
de coordonnées **ou** AUTRE balise, puis poser `position_suspecte` +
`position_note` sur `station_zone` par `.sql`. Onze des quinze sont à
moins de 1 200 m de leur gel (simple changement de maille AROME) ;
`pioupiou:1333` (87,7 km) et `pioupiou:2171` (38,9 km) sont les candidates
« AUTRE balise ». ⓘ `pioupiou:1334` (61,2 km) a réarmé son compteur pour
la deuxième fois (2 j → 1 j) : elle oscille autour du gel, elle ne dérive
pas.

## 7. Tickets — deux commentaires, aucune transition, aucune création

États relevés **avant** d'écrire (GET `/rest/api/3/issue/…`, HTTP 200) :

| ticket | motif | statut | `statusCategory` | maj avant | commentaires |
|---|---|---|---|---|---|
| KAN-3 | `bw-pente-duree` | **Terminé** | `done` | 01/10 09:15 | 16 |
| KAN-4 | `bw-pente-memoire` | **À faire** | `new` | 04/10 19:56 | 26 |
| KAN-5 | `bw-purge-57014` | **À faire** | `new` | 04/10 19:56 | 9 |

- **KAN-4 (`bw-pente-memoire`)** — **laissé OUVERT**, **commenté**
  (`bw_jira_signaler`, HTTP 201 → **27 commentaires**). Les trois
  conditions de fermeture : jalon mesurablement retombé → **NON**
  (**record 3 417 Mo**, +617 au-dessus, **+19,9 o/ligne en une nuit à
  volume étale**) ; swap au pic ≈ 0 → **NON** (2 218,3 Mo et
  2,58 M de pages sorties) ; contrôle muet → oui, mais **−9 Mo/nuit**
  contre −13 puis −24 puis −30 : silence **inertiel qui se dégrade**. Le
  commentaire porte les trois franchissements, la courbe du coût par
  ligne, les **deux calculs à taux constant** (+40,5 Mo au taux du 04/10,
  +63,0 au taux du 01/10) et le fait que **le volume ne peut plus servir
  d'explication cette nuit**.
- **KAN-5 (`bw-purge-57014`)** — **laissé OUVERT**, **commenté**
  (HTTP 201 → **10 commentaires**). Le commentaire porte le bloc purge de
  la nuit, les six points vérifiés, le décompte **6 / 3**, la série des
  volumes effacés avec la mise en garde contre la sur-lecture du recul de
  5 800 lignes, et il se termine en **soumettant la fermeture à Yann**.
  **Aucune transition jouée.** Le contrôle de 07:30 s'étant tu, ce
  commentaire ne double rien.
- **KAN-3 (`bw-pente-duree`, Terminé)** — **NON rouvert et NON commenté**,
  délibérément : la durée **baisse** (−55 s sur la nuit, −324 s depuis le
  01/10), la pente du contrôle est à −68 s/nuit et `proposition()` n'a
  rien formulé. Jeton `cri.jira.bw-pente-duree` resté au **01/10**.
- **Aucun motif neuf créé.** `bw-regime-sensibilite` reste en veille et la
  condition du 29/09 est encore moins remplie qu'hier : `regime` descend à
  **13,53 ms/ligne** alors que le volume monte de 2 558 lignes. Les 57014
  de `rpc/bw_character_avance` restent rattachés au dossier « base sous
  tension » (aucun cette nuit). Le cri de position et la panne du webhook
  **ne sont pas de la dérive** (partage des canaux en tête de
  `bw_jira.sh` : Jira = dérive ; mail + push = les ⛔) — d'où la question
  n° 4 du §10, posée depuis le 30/09 et toujours non tranchée.

Vérification après écriture (GET, HTTP 200) : **KAN-3 Terminé/`done`,
16 commentaires, maj 01/10** · **KAN-4 À faire/`new`, 27 commentaires,
maj 05/10 11:15** · **KAN-5 À faire/`new`, 10 commentaires, maj 05/10
11:15**. Jetons après écriture : `bw-pente-memoire` = 2026-10-05,
`bw-purge-57014` = 2026-10-05, `bw-pente-duree` = **2026-10-01** (intact).
⛔ Aucun ticket fermé, aucune transition jouée, aucun ticket créé.

## 8. Hors périmètre, relevé sur la nuit du 04→05

- ⚠️ **Écarts au recalcul indépendant : 7** (4 le 04, 6 le 03, 6 le 02) —
  toujours **tous en `fcstagrume`**, toujours le même motif
  (« 0 ou 1 h appariée ici (< 6) mais la base porte une ligne »), et
  **toujours des balises neuves** : `aemet:9460X`, `infoclimat:STATIC0392`,
  `mf:74135001`, `pioupiou:2009`, `windsmobi:ffvl-2326`,
  `infoclimat:STATIC0440`, `mf:09289001` — **aucune reprise d'hier**. Ce
  n'est pas un lot figé de balises fautives, c'est un motif d'appariement
  qui frappe au hasard dans `fcstagrume`. Dette ancienne, le compte remonte
  (4 → 7) : à resurveiller.
- `lignes_daily` **69 726** (69 852 le 04) · `lignes_glissant` **10 671**
  (−3) · `lignes_regime` **121 418 (+2 558)** · `lignes_score_zone`
  **132 089 (+2 555)**.
- Observations du jour : **3 734 balises** (veille 3 739) — deuxième nuit
  de reflux.
- Stabilité des rangs : **`tau = 0,788` sur 58 cases**, 0 jour partagé
  (0,797 sur 57 le 04 ; 0,816 sur 60 le 03).
- Témoins du mélange : sur **7 610** balise-jours×échéance, le mélange
  fait **2,7105 km/h** contre **2,9257** pour le meilleur membre a priori
  (**gain 7,4 %**, devant dans **55,9 %** des cas) ; contre la moyenne
  **uniforme**, sur 1 122 : 2,6238 vs 2,7925 (**gain 6,0 %**). Le mélange
  **reste au-dessus** du seuil du « devant une fois sur deux ».
- Mélange multi-modèle : 8 000 balise×échéance avec poids sur 30 j de
  cache (+6 h : 2 642 `bw_mix`, 415 témoins uniformes, 190 sans poids).
- Référence combinée : médiane **`k = 0,144`** (0,129 le 04, 0,130 le 03)
  sur 3 702 balises / 3 819 climatologisées ; **297** balises avaient un ρ
  hors [0, 1] ramené à la borne (366 le 04 — l'amélioration continue).
- Murphy : **66 521** cases, dont **64 347** décomposées, **266** balises
  dehors (inchangé depuis le 01/10).
- FDR : 6 866 tests / 1 925 survivants à BH α=0,1 (brut, 95 rangs retirés
  sur 1 123 publiés) ; 6 558 / 1 387 (corrigé, 110 retirés sur 738).
- Duel apparié : 65 095 lignes en lead 6 (1 304 retirées), 23 963 en
  lead 24 (503). `agrume_pi ↔ bw_mix` +6 h : médiane **+0,382**
  → `b_better` ; +24 h : **+0,525** → `b_better`. `agrume ↔ agrume_pi`
  +6 h : médiane +0,004 → `b_better` (IC95j [+0,002 ; +0,007]).
- Manches : **38 nuits** suivies depuis le 24/08, **652 cases**
  zone×lead×modèle avec au moins une manche gagnée.
- Pression : 17 905 lignes, 859 appariées (médiane 18,1 km).
- Événements notés : 27 979 combinaisons publiables, 27 764 écartées sous
  le quorum de 8.
- ⓘ R2 : **4 écritures**, plafond 10, **160,1 Mo** — rien près du plafond.
- `mutations_memoire` : **aucune ligne** au journal de la nuit ; dette
  antérieure de **3 mutations non vues** (2, 5, 13), inchangée.
- Lots : 5 295 entrées écartées en `doublon_de` (L17), 317 en
  `notee_depuis` (L15-bis) ; 7 958 balise-jours écartés au rejeu pour
  naissance postérieure.

## 9. Ce qui a été touché

**VPS** : rien hors les **deux** commentaires Jira. `tail -n 4` du
registre, `journalctl` (notation et contrôle du jour, **sans élévation de
droits : les lignes utiles sont lisibles par `debian`**), `list-timers`,
`controle_quotidien.py --verbeux`, lecture de `bw_jira.sh` (en-tête,
`bw_jira_http`, `bw_jira_chercher`, `bw_jira_signaler`), **six GET Jira**
(trois avant écriture, trois après vérification), listage et lecture du
dossier de jetons `~/.balise-watch-etat-alertes`. **Aucun `systemctl
start/restart/daemon-reload`, aucun `enable`, aucun SQL joué, aucun
`rsync`, rien écrit dans `~/balise-watch` ni dans `/etc`.** Écritures : les
deux textes de KAN-4 et KAN-5 par `bw_jira_signaler` (qui travaille dans
un `mktemp -d` en 700 effacé après), et les **deux jetons
`cri.jira.<motif>` du jour**. ⓘ Une seule exception à signaler
honnêtement : la sortie de `controle_quotidien.py --verbeux` a été
redirigée vers **`/tmp/ctl.txt`** pour être lue en entier (le `tail` ne
rendait qu'une ligne) — fichier jetable hors `~/balise-watch` et hors
`/etc`, mais c'est bien une écriture sur le VPS.
`~/.balise-watch-alertes.env` **sourcé**, jamais lu par valeur ;
`curl -K -`, jamais `-u`. Les deux scripts passés au VPS l'ont été par
`ssh 'bash -s' <` depuis le Mac — **rien n'a été déposé sur le VPS**.

**Mac** : cette note et son miroir git, plus deux scripts jetables dans
`/Users/yann/` (hors dépôt : `bw-jira-get-05-10.sh`,
`bw-jira-post-05-10.sh`) — **pas de `git push`**.

## 10. Ce qui reste — et ce qui demande Yann

1. ⛔ **DEUX NUITS AVANT LE 07/10 : onze balises franchissent 10 j** et le
   compte de CONFIRMÉES passera de **2 à 13**. Le cri partira (c'est un
   front), **par mail seulement** si le webhook n'est pas réparé. C'est
   l'échéance la plus proche du dossier : trancher les 15 cas (correction
   de coordonnées **ou** AUTRE balise), puis `position_suspecte` +
   `position_note` sur `station_zone` par `.sql`. Onze des quinze sont à
   moins de 1 200 m (changement de maille) ; `pioupiou:1333` (87,7 km) et
   `pioupiou:2171` (38,9 km) sont les candidates « AUTRE balise » ;
   `pioupiou:1334` (61,2 km) oscille (compteur réarmé deux fois).
2. ⛔ **LA MÉMOIRE (KAN-4) BAT SON RECORD, et cette fois sans excuse de
   volume.** Jalon **3 417 Mo** (+617 au-dessus du seuil) ; coût par ligne
   **1 717,3 o, +19,9 en UNE nuit** alors que la fenêtre n'a grandi que de
   950 balise-jours ; **+31,7 o/ligne depuis le 01/10**. Quatrième nuit de
   hausse de fond. **Aucun levier déployé depuis le 21/09 (15 nuits)** :
   décider la **ligne en tuple**, après la mesure `tuple` vs `namedtuple`
   à la sonde. ⚠️ À ce rythme la pente du contrôle (−9 Mo/nuit, contre
   −30 il y a une semaine) passera positive d'elle-même d'ici deux ou
   trois nuits, et il criera alors sans qu'il se soit rien passé de neuf.
3. ✅ **LA PURGE EST À 6 / 3 : faut-il fermer KAN-5 ?** Six nuits
   consécutives (30/09 → 05/10), 8 tranches et un nombre lisible chaque
   nuit, zéro 57014 dans le bloc purge, zéro `?`, zéro
   `des lignes RESTENT`. `e83d814` tient. **La fermeture te revient**,
   aucune transition n'a été jouée. Question posée hier, sans réponse.
   (Si tu veux la jouer : API v3, `curl -K -`, même façon que le 10/09.)
4. ⛔ **LE WEBHOOK `push` RESTE CASSÉ : 0 / 2**, et pas éprouvé depuis.
   La variable est présente (pas de cri de `bw_avertir_config`), donc
   c'est le `POST` qui échoue. Deux questions, posées depuis le 30/09 :
   veux-tu qu'une session éprouve `BW_WEBHOOK_URL` par un `curl` de test
   **hors run**, ou préfères-tu regarder toi-même ? Et faut-il un motif
   Jira pour une panne de canal, alors que `bw_jira.sh` réserve Jira à la
   dérive ? ⚠️ L'urgence est datée : le cri du 07/10 sera le troisième
   essai, et le plus gros.
5. ⛔ **LE CRI DE POSITION EST « À FRONT »** (démontré dans les deux
   sens). Question du 01/10, toujours ouverte : veux-tu que le garde-fou
   **recrie** tant qu'une balise reste confirmée (même motif, une fois par
   jour), ou qu'il se taise comme aujourd'hui ?
6. ⛔ **LE DOSSIER « BASE SOUS TENSION » reste le levier de la durée.**
   `diagnostic_base_sous_tension_2026-09-29.sql` (lecture seule, 9 blocs)
   **attend toujours d'être joué dans le SQL Editor** ; les correctifs
   candidats (ANALYZE / VACUUM / autovacuum par table) y sont en
   commentaire. Trois nuits à `n_57014 = 0` ne sont pas un correctif : le
   30/09 était déjà à 0 et le 01/10 a battu le record à 3.
7. ✅ **LA DURÉE (KAN-3) : rien à décider.** 4 821 s, marge 3 279 s
   (**40,5 %, le meilleur de la série**), pente −68 s/nuit, `cpu_s` en
   baisse de 111 s. KAN-3 reste **Terminé**, **non commenté**. Et le
   volume de régime a sauté de +2 558 lignes **sans** coûter de temps par
   ligne (13,53 ms contre 13,67) ⇒ `bw-regime-sensibilite` reste en
   veille, rien de créé.
8. ⚠️ **QUATRIÈME MATIN DE SUITE HORS HORAIRE** : 08:56 UTC pour 07:07
   aujourd'hui, 17:51 pour 07:00 hier, et **aucun tir** les 02 et 03/10.
   Le VPS est à l'heure les quatre matins (contrôle à 07:30, notation
   nocturne complète) : **le trou est du côté de la planification de la
   routine**. Quatre matinées de suite, ça mérite un coup d'œil à la
   configuration de la tâche.
9. ⚠️ **Écarts au recalcul : 7 (contre 4)**, toutes balises neuves, toutes
   en `fcstagrume` — motif d'appariement au hasard, pas un lot figé. Dette
   ancienne, le compte remonte.
10. `mutations_memoire` : 3 mutations non vues (dette antérieure).

Miroir git : ce fichier même, commité en local depuis la racine du dépôt
serveur (le hash est celui du commit qui le porte). Pas de `git push`.
