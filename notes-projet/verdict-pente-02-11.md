# Verdict de pente du 02/11/2026 — ⛔ **Le critère `bw-regime-sensibilite` n'est PLUS rempli : la nuit du 01/11, que la routine n'avait pas pu lire, casse la série de hausses. La question prioritaire n°1 du 31/10 n'a plus d'objet.** ✅ **Purge propre DEUX nuits de plus : KAN-5 à 7 / 3, et ta décision a quatre jours de retard.** ⬆️ **R2 remonte à 10,402 Go (104,0 %) : +151 Mo, cinquième nuit au-dessus du palier.** ⚠️ **Mémoire : trois reculs d'affilée, mais c'est EXACTEMENT la configuration du 30/10, annulée en vingt-quatre heures.**

## 08:30–08:55 (Paris, CET) — routine Balise Watch, run du jour

**Étape 0 : faite en entier, avant toute autre chose.**

- `git log --oneline --since=midnight` : ⛔ **IL Y A un commit du jour** dans
  `balise-watch-server` — **`edfa879`** « AGRUME : regel L15-bis du 02/11 ».
  Aucun dans le dépôt principal. ⇒ **Une autre session a bien tourné ce matin**
  (note projet `claude/session-position-l15-02-11.md`, écrite à 07:24 UTC),
  mais sur le **cri de position / AGRUME**, pas sur la pente : elle a pris le
  troisième avis sur les 7 confirmées, déplacé 1378 / 2171 / 175 sur décision de
  Yann, redéployé AGRUME et **poussé** le commit.
- `project_read claude/verdict-pente-02-11.md` : **absent** ⇒ cette note est une
  **création**, pas une fusion. Elle est en **section horodatée** (règle n°2).
- `project_read claude/verdict-pente-01-11.md` : ✅ **lu en entier** — c'est la
  note d'**échec d'accès** (Mac injoignable, aucun chiffre). `verdict-pente-31-10.md` :
  ✅ **lu en entier**, c'est lui qui sert de référence.
- `notes-projet/README.md` relu : les quatre règles.
- ⓘ **Le travail de pente n'était PAS fait.** Je ne le refais donc pas : je le
  fais. Et je ne touche à rien de ce que la session position a fait.

### ⚠️ Rattrapage de la nuit du 01/11

La routine du 01/11 n'avait **rien pu lire** (pont vers le Mac tombé). Le trou
est **comblé sans rien inventer** : `historique.jsonl` garde la ligne du
01/11, et `journalctl --since "2026-11-01 00:00"` était encore dans la fenêtre.
**Tous les chiffres du 01/11 de cette note sont relevés, pas reconstitués.**
⇒ Et c'est ce point relevé après coup qui **démolit** la conclusion la plus
pressante du 31/10 (§1).

## 1. ⛔ LE CRITÈRE `bw-regime-sensibilite` EST CASSÉ — correction de la note du 31/10

**Coût par ligne de `regime`** (`etapes_s.regime / lignes_regime × 1000`) :

```
21/10 12,14 ms · 22/10 12,59 · 23/10 11,97 · 24/10 11,42 · 25/10 12,19
26/10 11,44 · 27/10 11,21 · 28/10 11,71 · 29/10 10,86 · 30/10 11,30
31/10 11,88 · 01/11 ⬇️ 10,92 · 02/11 11,13 ms
```

Le 31/10, le critère unique arbitré le 07/10 — « la hausse s'additionne **deux
nuits de suite** » — était **REMPLI (2 / 2)** : 10,86 → 11,30 → 11,88. La
question d'un motif Jira était posée comme **point n°1** de la liste.

⇒ ⛔ **La nuit du 01/11 le DÉMENT** : 10,92 ms, soit **−0,96 ms**, le **plus gros
recul de toute la série**. La série de hausses est **cassée**. Le 02/11 reprend
**+0,21 ms** (11,13) ⇒ compteur **1 / 2**.
⇒ ✅ **LE CRITÈRE N'EST PAS REMPLI. La question du 31/10 n'a plus d'objet, et
rien n'avait été créé** — ce qui était la bonne décision.
⇒ ⛔ **Et c'est une leçon de méthode, pas un détail** : le point qui casse la
série est **celui de la nuit que la routine n'avait pas vue**. Un critère compté
sur **deux nuits consécutives** est fragile à un **trou d'observation**. C'est
exactement pourquoi la règle dit de **reposer la question** au lieu de créer.
ⓘ Nuance maintenue dans les deux sens : 11,13 ms n'est **pas** un niveau
remarquable (12,59 le 22/10). Le niveau n'a jamais été le critère.

## 2. Le relevé des deux nuits

`lancement = timer` · `result = success` · `exec_status = 0` · `oom = 0` pour
**les deux** nuits. Self-test du scoring **VERT** le 02/11 (les cinq contrôles ;
`mse_comb` 17,841 ; permuté 2,198 ; skill contre persistance −2,2604). Relevés
**comparables** : le verdict porte.

Nuit du 01→02/11 : début **04:56:35**, fin **06:19:57** (CET). Journée notée
**2026-11-01**. Contrôle passé à **07:30:05** CET, suivant armé pour le **03/11
à 07:30:50 CET**.

| | 31/10 | 01/11 | 02/11 | Δ(01→02) |
|---|---:|---:|---:|---:|
| `duree_s` | 5 079 | 4 900 | **4 989** | **+89** |
| `cpu_s` | 4 068,4 | 3 883,3 | **4 006,3** | +123,0 |
| `marge_s` | 3 021 | 3 200 | 3 111 | −89 |
| marge / garde (8 100 s) | 37,30 % | 39,51 % | 38,41 % | −1,10 pt |
| étapes (somme) | 3 050,5 | 2 883,4 | **2 936,1** | **+52,7** |
| hors étapes | 2 028,5 | 2 016,6 | **2 052,9** | **+36,3** |
| `jalon_max_mo` | 3 397 | 3 374 | **3 348** | −26 |
| `mem_peak_mo` | 3 612,7 | 3 619,0 | 3 598,5 | −20,5 |
| `swap_peak_mo` | 2 213,5 | 2 356,0 | **2 337,5** | −18,5 |
| `swap_out_pages` | 2 172 144 | 2 344 525 | 2 164 500 | −180 025 |
| `n_57014` | 1* | 1* | ✅ **0** | **−1** |
| `incidents` | 3 | 3 | ✅ **2** | **−1** |
| `lignes_regime` | 139 999 | 140 956 | **143 669** | **+2 713** |
| `lignes_score_zone` | 150 712 | 151 649 | 154 362 | +2 713 |
| `lignes_daily` | 68 572 | 65 111 | 66 009 | +898 |
| `lignes_glissant` | 10 713 | 10 693 | 10 693 | 0 |
| `balise_jours_rejeu` | 2 060 898 | 2 056 179 | 2 052 228 | −3 951 |

(*) `n_57014 = 1`, mais **hors bloc purge** — voir §3.2.

Répartition par étape (s) :

| étape | 31/10 | 01/11 | 02/11 | Δ(01→02) |
|---|---:|---:|---:|---:|
| `regime` | 1 663,3 | 1 539,7 | **1 598,7** | **+59,0** |
| `glissant` | 985,6 | 970,6 | 962,1 | −8,5 |
| `stabilite` | 321,4 | 300,0 | 290,2 | −9,8 |
| `rejeu` | 80,2 | 73,1 | 85,1 | +12,0 |

⇒ ⚠️ **Hausse PARTAGÉE** : 52,7 s dans les étapes (59 %) et 36,3 s hors étapes
(41 %). `regime` porte **59 s à lui seul**, plus que la hausse totale, les deux
autres grosses étapes reculant.

### 2.1 Les deux rapports qui valent mieux que les valeurs brutes

**Coût par ligne rejouée** (`jalon_max_mo × 1048576 / balise_jours_rejeu`) :

```
19/10 1 702,0 o · 20/10 1 608,0 · 21/10 1 726,1 · 22/10 1 722,2 · 23/10 1 621,3
24/10 1 723,8 · 25/10 1 743,9 · 26/10 1 595,7 · 27/10 1 726,9 · 28/10 1 740,7
29/10 1 744,3 · 30/10 1 728,9 · 31/10 1 728,4 · 01/11 1 720,6 · 02/11 1 710,6 o
```

⇒ ⚠️ **−17,8 o sur deux nuits**, et la bande **1 596 à 1 744 o** tient une
**treizième** nuit. **1 710,6 o est DANS la bande, pas en dessous.** Aucune
pente sur quinze nuits.
ⓘ Et **`balise_jours_rejeu` recule aussi** (−8 670 sur deux nuits) : le jalon et
la fenêtre vont dans le **même** sens, donc une partie du recul du jalon est un
recul de **fenêtre**, pas un gain de structure.

**Calcul ou attente ?** ⛔ **Du calcul.** La durée prend **89 s** et `cpu_s` en
prend **123,0**. Le CPU monte **plus** que l'horloge : la machine n'a pas
attendu, elle a travaillé.

## 3. ✅ LA PURGE : deux nuits propres de plus — compteur KAN-5 à 7 / 3

Bloc purge du **02/11**, en entier :

```
2026-11-02 06:19:41  → purge model_score_zone : 148683 ligne(s) effacée(s) en 8 tranche(s)
2026-11-02 06:19:41  ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée
```

Bloc purge du **01/11**, en entier :

```
2026-11-01 06:17:43  → purge model_score_zone : 148173 ligne(s) effacée(s) en 8 tranche(s)
2026-11-01 06:17:43  ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée
```

Les quatre tests de lecture (règles du 28/09 complétées le 07/10), pour les
**deux** nuits :

| test | 01/11 | 02/11 |
|---|---|---|
| tranche en échec | ✅ **✘ aucune** | ✅ **✘ aucune** |
| bilan chiffré | ✅ **✔ 148 173 / 8 tr.** | ✅ **✔ 148 683 / 8 tr.** |
| « des lignes RESTENT » | ✅ **✘ absent** | ✅ **✘ absent** |
| sonde en défaut | ✅ **✘ aucun** | ✅ **✘ aucun** |

⇒ ✅ **DEUX NUITS PROPRES PLEINES**, sonde comprise.

### 3.1 ✅ Compteur de fermeture KAN-5 : 7 / 3 — quatre jours de retard

```
27/10 propre → 1 / 3 · 28/10 → 2 / 3 · 29/10 → 3 / 3  ⇐ CRITÈRE REMPLI
30/10 → 4 / 3 · 31/10 → 5 / 3 · 01/11 → 6 / 3 · 02/11 → 7 / 3
```

⇒ ❓ **Le critère écrit est rempli depuis le 29/10, soit QUATRE jours.** Question
posée pour la **quatrième** fois (28/10, 30/10, 31/10, 02/11). ⛔ **Rien n'est
fermé, rien n'est transité.**
ⓘ **Vérifié par une troisième voie** : le GET d'avant écriture rend
`updated = 2026-10-31T08:24:41+0100` et **33** commentaires — **exactement**
l'état laissé par le run du 31/10. **Aucun tiers n'a écrit depuis, aucune
réponse n'a été enregistrée.**

### 3.2 ✅ `n_57014 = 0` — la série de la ligne `bw_character_avance` s'interrompt

**Première nuit à zéro depuis le 28/10.** Et cela **casse** la série de la ligne
`rpc/bw_character_avance : HTTP 500 57014`, qui était tombée **quatre nuits de
suite** : 29/10, 30/10, 31/10 **et 01/11** (ce dernier point est neuf, relevé
ici).

```
13/10 0 · 14/10 1 · 15/10 0 · 16/10 1 · 17/10 0 · 18/10 0 · 19/10 0 · 20/10 0
21/10 0 · 22/10 1 · 23/10 4 · 24/10 0 · 25/10 3 · 26/10 1 · 27/10 0 · 28/10 0
29/10 1* · 30/10 1* · 31/10 1* · 01/11 1* · 02/11 ✅ 0     (* hors purge)
```

Recherche élargie sur **toutes** les unités, 36 h : `grep -c 57014` = **1**, et
cette unique ligne est celle du **01/11**, rattrapée à **100 %** (369 080
accumulateurs avancés sur 369 080 envoyés). Cette nuit : **463 740 / 463 740**,
zéro perte.
⇒ ⛔ **Mon avis est inchangé : NE PAS créer `bw-character-57014`.** Motif
antérieur, qui se rattrape seul, et dont la série vient de s'**interrompre
d'elle-même**. ⚠️ Et la lecture du 31/10 (« fait neuf, il tombe trois nuits de
suite ») est à **relativiser rétrospectivement** : c'était quatre nuits, puis
plus rien. **Quatre points ne faisaient pas une pente** — quinzième application.

### 3.3 Le volume : au plus haut de la fourchette, et toujours pas un signal

```
28/10 142 819 · 29/10 143 625 · 30/10 147 216 · 31/10 145 123
01/11 148 173 · 02/11 148 683 lignes — toutes en 8 tranches
```

⇒ **Six nuits de suite à 8 tranches.** Le volume effacé suit le volume de la
journée purgée : **il monte et descend sans rien signifier.** Il n'est lu comme
un signal **ni à la hausse ni à la baisse**, même au plus haut de la fourchette.
⛔ **Et il n'y a toujours AUCUNE preuve** que la plus vieille journée soit partie
de la base. Seul un `select as_of, count(*) … group by as_of order by as_of
limit 5` le dirait, et **aucun SQL n'a été joué.**

### 3.4 ⛔ Les deux défauts de code restent entiers — huitième nuit non testée

1. **(a)** `bilan_purge` ignore le suffixe « des lignes RESTENT » — faux négatif
   démontré le 25/10.
2. **(b)** `registre_nuit._INCIDENT` ne reconnaît pas la ligne de sonde, donc la
   branche `sonde_ko` de `controle_quotidien.constats()` est du **code mort** —
   démontré le 26/10.

⛔ **Il faut les DEUX.** Ni le 01/11 ni le 02/11 n'avaient de ligne restante ni
de sonde en défaut : **huitième nuit de suite** où ils ne peuvent être **ni**
confirmés **ni** réfutés. Ce sont des **écritures dans le code** : Yann tranche.

### 3.5 Le contrôle s'est tu, et par la bonne porte

```
2026-11-02T06:30:05Z rien à dire : pente plate ou négative, ou échéance hors horizon
```

Verbeux, relancé à la main en lecture seule :

```
ⓘ 95 relevé(s), 74 comparable(s) ; durée : 10 points, pente -119 s/nuit ;
  mémoire : 10 points, pente -24 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate/négative, ou échéance hors horizon
```

✅ Le silence est **juste** et **par la bonne porte** : `incidents` ne porte
aucun avertissement de purge **parce qu'il n'y en a eu aucun** — et non, comme
le 26/10, parce que le motif du registre ne sait pas lire la ligne de sonde.
ⓘ **95 relevés / 74 comparables** contre 93 / 72 le 31/10 : **+2 et +2**,
cohérent avec exactement **deux** nuits de plus. ✅ Le registre a bien écrit la
nuit du 01/11 **même si la routine ne l'a pas lue** : la chaîne du VPS n'a pas
de trou, seule l'observation en avait un.
⚠️ **Une seule ligne au journal du contrôle** ⇒ pas de second tir, jeton du jour
**libre** quand la routine a écrit.

## 4. ⚠️ Mémoire — trois reculs d'affilée, et la configuration du 30/10 à l'identique

```
                        31/10   01/11   02/11   Δ(2 nuits)   vs seuil 2 800
rejeu d'archive         2 995   2 968   2 941     −54          ⛔ +141
score par régime        2 832   2 853   2 739     −93          ✅ −61  (SOUS LE SEUIL)
oubli fenêtre rejouée   3 397   3 374   3 348     −49          ⛔ +548
```

`incidents` : 3 → 3 → **2**.

### 4.1 ⚠️ L'avertissement que je pose moi-même — et c'est le point principal

⛔ **Cette configuration est EXACTEMENT celle du 30/10.** Ce matin-là, le même
jalon « score par régime » venait de repasser **sous** le seuil et `incidents`
tombait de 3 à 2. La note du 30/10 avait ajouté la réserve « une journée un peu
plus chargée le fera repasser au-dessus » — et elle a été **vérifiée en
vingt-quatre heures** (2 832 Mo le 31/10, `incidents` de retour à 3).

⇒ ⚠️ **Je pose donc la même réserve, mot pour mot, et je ne présente PAS ce
recul comme une amélioration de fond** : 2 739 Mo n'est qu'à **61 Mo** sous le
seuil, et **rien n'a été déployé** côté mémoire qui puisse l'expliquer.
⇒ ⚠️ **Avec une nuance honnête qui va dans l'autre sens** : la journée notée du
02/11 était **beaucoup plus ventée** que celle du 31/10 (erreur absolue du
mélange **5,70** contre **3,00** km/h), le volume écrit en base a fait **+21 %**
— et le jalon a **baissé** quand même. ⇒ La lecture « c'est la charge du jour »
est donc **moins solide** cette fois, **dans un sens comme dans l'autre**. Je
n'en tire **aucune** conclusion de structure.

### 4.2 ⚠️ Le jalon qui décide : bande inchangée, treizième nuit, pas un plancher

```
19/10 3 381 · 20/10 3 193 · 21/10 3 424 · 22/10 3 412 · 23/10 3 210 · 24/10 3 411
25/10 3 452 · 26/10 3 151 · 27/10 3 399 · 28/10 3 420 · 29/10 3 424 · 30/10 3 400
31/10 3 397 · 01/11 3 374 · 02/11 3 348
```

⇒ ⚠️ **Trois reculs consécutifs, −49 Mo sur deux nuits.** Mais la bande va
toujours de **3 151 à 3 452 Mo, INCHANGÉE pour la treizième nuit** : 3 348 Mo
reste **au-dessus** du 20/10 (3 193), du 23/10 (3 210) et du 26/10 (3 151).
**Ce n'est pas un plancher de la série**, et sur quinze nuits il n'y a **aucune
pente nette**.
⚠️ « Une nuit ne fait pas une pente » — **et trois non plus** quand l'amplitude
reste dans la bande. **Quinzième** application en vingt-quatre jours.

### 4.3 ⚠️ Le swap MONTE sur deux nuits

`swap_peak_mo` : 2 213,5 → 2 356,0 → **2 337,5** (**+124,0** sur deux nuits).
`swap_out_pages` : 2 172 144 → 2 344 525 → **2 164 500** (−7 644 sur deux nuits).
⇒ ⛔ La divergence pic / pages signalée les 30 et 31/10 **se poursuit**, et je ne
conclus **rien** d'aucun des deux pris seul. ⚠️ **Mais le pic de swap n'est pas
proche de zéro : il est en HAUSSE.** C'est une des trois conditions de fermeture
de KAN-4, et elle s'éloigne pendant que le jalon se rapproche.

### 4.4 L'estimateur de pente, douzième matin contradictoire

**−24 Mo/nuit**, inchangé depuis le 30/10, pendant que le jalon fait −23 puis
−26 Mo. C'est le **25ᵉ centile des différences**, qui ignore par construction
les deux plus grosses variations. Conclusion du 23/10 **confirmée une neuvième
fois** : **cet estimateur n'est pas utilisable en prévision** sur cette série.
ⓘ L'échéance étant hors horizon, le contrôle se tait — et sur ce point précis
**il a raison**.

### 4.5 Les trois conditions de fermeture de KAN-4

| condition | état |
|---|---|
| le contrôle se tait sur `bw-pente-memoire` | ✅ **remplie** (5ᵉ matin) |
| le jalon est mesurément retombé | ⛔ **non** — 3 348 Mo, **+548** au-dessus |
| le swap au pic ≈ 0 | ⛔ **non** — 2 337,5 Mo, **et en hausse** |

⇒ ⛔ **NON RÉUNIES. KAN-4 reste ouvert.**

### 4.6 Le remède, inchangé

La **ligne en tuple** (§2.6 de l'enquête du 10/09) : ≈ **−1 030 o/ligne**, soit
≈ **−2 015 Mo** sur les 2 052 228 balise-jours rejoués cette nuit — à comparer
aux **548 Mo** qui séparent le jalon du seuil. ⛔ **Rien de déployé côté mémoire
depuis `af25efb` (21/09) — 42ᵉ jour.** ⚠️ L'élagage de `units` avait rendu
−124 Mo au lieu de −1 500 : les gains sont dans la **structure**. La mesure
`tuple` contre `namedtuple` à la sonde reste le préalable.
ⓘ Un calcul à taux constant donnerait « seuil atteint en N nuits » ; je le
**refuse**, parce que la série n'a pas de pente — **ni à la hausse, ni à la
baisse**.

## 5. Durée — +89 s, hausse partagée, et surtout du VOLUME

```
            étapes     hors étapes   total
31/10      3 050,5       2 028,5     5 079
01/11      2 883,4       2 016,6     4 900
02/11      2 936,1       2 052,9     4 989
```

### 5.1 La signature : 59 % dans les étapes, 41 % hors étapes

⇒ ⚠️ **Ni l'un ni l'autre des deux cas purs** vus en octobre. Le 31/10 toute la
hausse était **dans** les étapes ; les cinq nuits d'avant, elle était **hors**
étapes. Cette nuit elle est **partagée**.
⇒ ⚠️ **Hors étapes à 2 052,9 s : le plus haut des quatre dernières nuits.** Ce
bloc n'est **toujours pas instrumenté** (publication, Murphy, événements,
pression, duels, purge). ⬇️ La demande de jalons de temps dans `run.sh` **ne se
renforce pas franchement** — 41 % d'une hausse de 89 s, c'est petit — mais elle
**ne s'affaiblit pas** non plus. C'est une **écriture** dans `run.sh` : Yann
décide.

### 5.2 ⚠️ Le niveau : ce n'est PAS un maximum, et la durée BAISSE sur deux nuits

```
24/10 5 064 · 25/10 5 252 · 26/10 5 133 · 27/10 4 728 · 28/10 4 927
29/10 4 921 · 30/10 4 934 · 31/10 5 079 · 01/11 4 900 · 02/11 4 989 s
```

⇒ ⚠️ **4 989 s est le CINQUIÈME point le plus haut des dix**, sous le 25/10
(5 252), le 26/10 (5 133), le 31/10 (5 079) et le 24/10 (5 064). ✅ **Et par
rapport au 31/10 la durée a BAISSÉ de 90 s.**
⚠️ **Solde des deltas depuis le 23/10** : +58, −236, +188, −119, −405, +199, −6,
+13, +145, −179, **+89** ⇒ **−253 s sur onze nuits.** Le solde reste **négatif**
et il **s'est creusé**.
⚠️ **Marge : 38,41 % du garde**, 3 111 s de réserve sur 8 100. **Aucune urgence
mécanique.**

### 5.3 ✅ Volume contre temps : cette fois, c'est du volume

`lignes_regime` fait **+2 713** pendant que l'étape prend **+59 s** ⇒ le travail
par ligne ne monte que de **0,21 ms**. ⇒ **L'essentiel de la hausse de `regime`
est du VOLUME.** C'est l'**inverse** du 31/10 (lignes **−704**, temps **+73,5 s**),
et c'est précisément ce qui casse le critère du §1.

ⓘ **Et le volume général monte franchement** : `model_verif_event` **37 535 →
72 506** lignes (`breeze_yield` **148**, `drop` 24 917, `onset` 23 493, `ramp`
21 390, `reversal` 2 558), accumulateurs **369 080 → 463 740**, lignes écrites en
base **640 930 → 774 214**, détails par tranche **73 436**. Journée **beaucoup
plus ventée** (erreur absolue du mélange 5,70 contre 3,51 km/h la veille), donc
beaucoup plus d'événements à noter. **La durée n'a pris que 89 s pour tout cela.**
⚠️ Je ne fais pas de ce lien une loi : c'est **une** nuit, et l'explication par
le niveau de vent a été **abandonnée le 27/10** sur les témoins du mélange. Je
le note comme **cohérence**, pas comme cause établie.

### 5.4 Le garde

⛔ **Remontée du chien de garde : NON LANCÉE et NON DEMANDÉE.**
`controle_quotidien.proposition()` ne se déclenche pas. La forme, **décrite** et
non demandée : écrire la mesure dans l'en-tête de `10-timeout-s3.conf`
(135 → 140/145 min), déployer, vérifier. **C'est Yann qui décide et qui lance.**

ⓘ Rappel : la pente du contrôle est le **25ᵉ centile des différences**. Elle
affiche encore **−119 s/nuit**. Elle n'a vu ni le +153 s du 01/10, ni le +336 s
du 06/10, ni le +70 s du 07/10, ni le +188 s du 25/10, ni le +199 s du 28/10,
ni le +145 s du 31/10, et elle ne verra pas le **+89 s** de cette nuit.

## 6. ⬆️ R2 : le palier remonte — 10,402 Go, cinquième nuit au-dessus

```
                      30/10             31/10             02/11            Δ vs 31/10
total compte     10,276 Go 102,8 %  10,251 Go 102,5 %  10,402 Go 104,0 %   ⬆️ +151 Mo
objets             7 281             7 343             7 467              +124
pente mesurée    +0,028 Go/mois     +0,008 Go/mois     +0,021 Go/mois
palier atteint      0 j               0 j               0 j
```

⇒ ⬆️ **DÉMENTI de la lecture prudente du 31/10 dans le mauvais sens** : le recul
de 25 Mo n'annonçait rien, et le total **remonte de 151 Mo** en deux nuits —
**le plus haut relevé de la série**. Le journal le dit sans détour :
`⚠️ palier gratuit DÉPASSÉ : 10.40 Go sur 10 Go — R2 facture déjà`.
⇒ ⛔ **Cinquième nuit consécutive au-dessus du palier gratuit** (le garde-fou dit
« **5 consécutif(s)** »), et c'est désormais **le plus haut**, pas un plateau.
ⓘ Le seuil d'alerte (12 Go) et le seuil d'arrêt de chaîne (6 Go) ne sont pas en
cause ; couverture **complète**.

Par bucket : `balise-watch-grids` **9,445 Go / 6 200 obj** (+127 Mo, +96 obj) ·
`model-verif` **0,952 Go / 1 054 obj** (+23 Mo, +28 obj) ·
`balise-watch-packs` 0,005 Go / 213.

Par préfixe (31/10 → 02/11) : `agrume/grille` 5,323 → **5,323 Go / 766 obj**
(identique au Mo près) · `agrume/pi` 1,751 → **1,791 Go / 4 051 obj** ·
`arome/rafale` 0,797 → 0,837 · `arome/sol` 0,540 → 0,567 ·
`agrume/colonnes` 0,517 → 0,528 Go / **98 obj**.

### 6.1 ✅ `bw-garde-fou-r2` code 1 : son comportement normal

```
2026-11-02T05:20:04Z run garde-fou-r2 en ÉCHEC (code 1, 6s) — 5 consécutif(s)
```

✅ **Ce n'est PAS une panne.** La démonstration du 21/10 tient : **code 1 =
« j'ai quelque chose à dire »**. Le palier est dépassé, donc il parle, et son
cri est parti (§8).

### 6.2 ✅ `agrume/grille` : la fermeture du 31/10 tient

**766 / 766 et 5,323 Go**, au Mo et à l'objet près, pour la **cinquième** nuit
consécutive, et toujours aucune ligne « suppression(s) ratée(s) ». La question
du 27/10 est restée **refermée** ; je ne la réouvre pas.

### 6.3 ⛔ `agrume/pi` : vingtième nuit d'accumulation, sans un seul recul

```
│ agrume/pi/grille/            19 présentes /  19 réclamées   ✓
│ agrume/pi/rafraichissement/  28 présentes /  28 réclamées   ✓
```

47 objets couverts sur **4 051** ⇒ **4 004 objets que nul index ne réclame**
(3 910 le 31/10). **+94 en deux nuits, soit +47 par nuit — exactement le rythme,
pour la vingtième nuit consécutive.**
ⓘ Ce n'est pas la preuve qu'ils sont orphelins ; c'est la constatation qu'on
n'en sait rien. **L'inventaire reste le geste à faire avant toute rétention.**
✅ **Et pour une fois la leçon du 24/10 §7.1 ne s'applique PAS à l'envers** : le
total du compte **monte** cette fois, en même temps que l'accumulation. Cela
**ne** fait pas du total un indicateur de l'accumulation — les deux ont
simplement coïncidé.

⛔ Le point sur **`audit_r2.py`** (borner à zéro les pentes négatives des
préfixes à fenêtre glissante) reste **entier** : `arome/rafale` **−0,381**,
`arome/sol` **−0,290**, `arome/alt` −0,091, `arome/lod` −0,047 Go/mois tirent la
pente du total à **+0,021 Go/mois** pendant que `agrume/pi` monte à **+0,580**.
ⓘ Conséquence : « palier atteint dans **0 j** », juste **par accident** (le
palier EST dépassé) et non par la pente. **Une écriture, non faite.**

## 7. ⛔ Position — le cri est parti, et une autre session l'a déjà traité

```
⛔ position : 19 balise(s) divergent du gel (10 j lus), dont 7 CONFIRMÉE(S) (≥ 10 j)
   ⛔ pioupiou:1378        340 941 m · 10 j · nœud + profil CHANGENT · Col de la Merquiere
   ⛔ pioupiou:2171         38 915 m · 10 j · nœud + profil CHANGENT · Windbird 2171
   ⛔ infoclimat:STATIC0491  1 159 m · 10 j · nœud 0,01 CHANGE
   ⛔ pioupiou:70              551 m · 10 j · nœud 0,01 CHANGE · Déco Salève
   ⛔ pioupiou:175             483 m · 10 j · nœud 0,01 CHANGE · Col de la Core
   ⛔ pioupiou:1715            429 m · 10 j · nœud + profil CHANGENT · Windbird 1715
   ⛔ pioupiou:2058            242 m · 10 j · nœud 0,01 CHANGE · Ernio
⛔ position : 7 balise(s) CONFIRMÉE(S) — cri déposé pour envoi
   - pioupiou:84 : rentree dans l'ordre
```

⇒ ✅ **Le mécanisme « à front, pas à état » est vérifié DEUX fois de plus, dans
les deux sens** : le **01/11**, l'état est resté à **8 confirmées** et **aucun
cri n'est parti** (13ᵉ vérification) ; le **02/11**, `pioupiou:84` rentre dans
l'ordre, l'état passe de **8 à 7**, et **le cri part** (14ᵉ vérification). ⚠️ Fait
neuf, petit : **un front à la BAISSE déclenche aussi le cri** — on ne l'avait
jamais observé.
ⓘ La question du 01/10 — faut-il qu'il recrie à état constant ? — reste ouverte,
et **moins pressante** encore.
ⓘ `pioupiou:84` passe à **9 j**, `pioupiou:367` reste à **9 j**, `mf:05170001`
à 9 j. Les huit balises du 29/10 sont à **5 j**. `pioupiou:157` apparaît à
**172 591 m · 1 j** — à regarder quand elle aura du recul, **rien à en conclure**.

⬇️ **Et le geste attendu a déjà été fait ce matin, par l'autre session** :
troisième avis à la sonde, décision de Yann (renaissance pour 1378 / 2171 / 175,
suspension pour 1715 / 2058 / 70 / STATIC0491), commit `edfa879`, AGRUME
redéployé. ⇒ **Je ne touche à rien** ; il reste à Yann à jouer
`model-verif/position_l15_2026-11-02.sql`. Le point n°7 de la liste du 31/10 est
donc **largement soldé**.

## 8. Les trois correctifs du 07/10 — verdict correctif par correctif

| correctif | verdict du 02/11 |
|---|---|
| **1. webhook `--ipv4`** | ✅ **CONFIRMÉ une TROISIÈME fois, sur deux cris distincts.** Deux choses à envoyer (cri de position **et** palier R2), **deux** `ⓘ push parti (webhook, HTTP 200)` à **05:19:54Z** et **05:20:04Z**. ✅ **Aucun HTTP 429 ntfy** : `grep -i ntfy \| grep -c 429` = **0** sur 36 h. ✅ Les deux mails sont partis (`msmtp … smtpstatus=250 … exitcode=EX_OK`, 1 157 et 2 806 octets). ⇒ Six pushes partis au total sur trois nuits : le correctif **tient**. |
| **2. garde-fou des deux jetons** | ✅ **tient** mécaniquement : le contrôle de 07:30:05 s'est **tu**, **une seule ligne** au journal, aucun jeton posé, aucun doublon possible — et les trois commentaires de ce matin sont passés par le canal **délibéré**, qui ne touche pas au jeton. `controle_quotidien.sh` conserve son `$ETAT` — **non touché**. |
| **3. rejeu de purge ≠ échec** | ⓘ **non sollicité**, huitième nuit : purges propres, aucun avertissement, rien à lire. Les deux défauts du §3.4 restent **entiers**. |

## 9. Les autres témoins

- ⛔ **Témoins du mélange : PREMIER point négatif après six positifs.**
  ```
  31/10 : gain +3,3 %, devant 52,4 %, erreur 2,998 km/h
  01/11 : gain +0,6 %, devant 49,3 %, erreur 3,5115 km/h   (point neuf)
  02/11 : gain −0,8 %, devant 48,2 %, erreur 5,7029 km/h
  ```
  Série du gain contre le **meilleur membre a priori** : −0,6 % (07/10) · +2,5 ·
  +1,7 · −0,3 · +0,9 · −0,9 · +0,1 · +0,8 · −4,0 (25/10) · −2,2 · +5,2 · +2,3 ·
  +0,5 · +3,0 · +3,3 · **+0,6** · **−0,8 %**.
  ⇒ ⚠️ **Compteur du motif `bw-melange-sans-gain` : 1 / 3 négatifs.** Il faut
  **trois** points négatifs consécutifs. ✅ **La question reste refermée ; mon
  avis est inchangé : ne pas créer le motif.**
  ⚠️ **Et la pondération du 07/10 s'applique mot pour mot** : l'erreur absolue a
  **presque doublé** (3,00 → 5,70 km/h, journée bien plus ventée) et le gain
  contre la moyenne **uniforme** tient (**+3,0 %**). ⛔ Je **ne** ressuscite pas
  l'explication par le niveau de vent (abandonnée le 27/10) ; je dis seulement
  que ce point **n'est pas comparable** aux cinq précédents.
- ⚠️ **Témoin du corrigé** : part site **22,0 pt** (sur 8 629 balise-jours —
  vrai antécédent +13,4 %, autre balise −8,6 %). Série : 27,8 → 27,6 → 27,1 →
  17,9 → 17,0 → 19,8 → 15,0 → 15,7 → **16,6** (01/11) → **22,0 pt**. Version FIN,
  part secteur+heure : 11,4 → 10,9 → 11,8 → 9,1 → 9,6 → **11,8** → **11,5 pt**
  (5 849 balise-jours). ⓘ **Ça oscille**, comme conclu depuis le 22/10. **Rien à
  surveiller** — et la remontée à 22,0 n'est pas lue comme une tendance.
- ⚠️ **Écarts du recalcul indépendant : 8 — HORS de la bande pour la première
  fois.** Série : 5 · 4 · 7 · 4 · 7 · 5 · 4 · 4 · 4 · 4 · 6 · **5** (01/11) ·
  **8**. La bande allait de **3 à 7** ; **8 en sort**. Signature : **6 sur 8**
  portent `0 h appariées ici (< 6)` et **2 sur 8** portent `1 h` — **même
  signature de fond**, récurrente et antérieure (« la base porte une ligne alors
  que le recalcul n'en apparie pas assez »). ⓘ Les huit :
  `fcstagrume/infoclimat:000RO` (+24 h, 1 h), `fcstagrume/mf:39485002` (+6 h),
  `fcstagrume/pioupiou:1215` (+48 h), `fcstagrume/windsmobi:holfuy-1297`
  (+48 h), `fcstagrume/infoclimat:STATIC0202` (+24 h, 1 h),
  `fcstagrume/mf:05007003` (+48 h), `fcstagrume/pioupiou:1427` (+48 h),
  `fcstagrume/windsmobi:ffvl-2336` (+24 h). ⚠️ **Un point hors bande ne fait pas
  une pente** : le tirage est de 20 strates sur 9 balise-jours comparés, donc
  très bruité, et la journée était **beaucoup plus ventée**. **À revoir demain,
  rien de plus.** Et surtout : **je ne reprends pas la lecture de la signature
  comme une tendance** — elle change tous les jours depuis le 27/10.
- ⓘ **Écart des deux mélanges** : `mse_comb` 17,841 contre `mse_comb_vec`
  17,841 (**+0,00 %**) — les deux chemins restent confondus.
- **Duels** : `agrume ↔ agrume_pi (+6 h)` n = 7 105, médiane +0,010, IC95
  [+0,005 ; +0,015] → `b_better` · `agrume_pi ↔ bw_mix (+6 h)` n = 7 089,
  médiane +0,395, IC95 [+0,320 ; +0,495] → `b_better` ·
  `agrume ↔ meteofrance_arome_france_hd (+6 h)` médiane −0,001, IC95
  [−0,003 ; +0,001] → **`not_separable`** ·
  `arome_r2 ↔ meteofrance_arome_france_hd (+6 h)` n = 16 606 sur **29 j**,
  médiane +0,086 → `b_better` · `agrume_pi ↔ bw_mix (+24 h)` n = 6 843 sur
  **29 j**, médiane +0,465 → `b_better`. Cumul toujours **tronqué par la
  rétention 30 j** (dette connue, `duel.DUEL_DAYS`).
  ⓘ **La journée AROME/R2 perdue du 25/10 se voit encore** : `arome_r2` porte
  **29 j** quand les duels +6 h vont jusqu'au 2026-11-01. Jusqu'au **24/11**.
- **Murphy** : 67 271 triplets / **63 839** décomposés / 266 tenus dehors.
- ⚠️ **Observations : un recul de 270 balises qui TIENT deux nuits.**
  **3 457** balises observées (3 461 le 01/11, **3 731** le 31/10), 3 158 zonées,
  1 234 cases fines dont 603 sous les 2 balises. ⚠️ **Fait neuf, à surveiller** :
  ce n'est pas du bruit d'une nuit, c'est **−274 depuis le 31/10 et stable
  depuis**. `lignes_daily` suit (68 572 → 65 111 → 66 009). ⓘ Je **ne** l'explique
  pas et je **ne** l'attribue pas au regel L15-bis de ce matin, qui est
  **postérieur** au run. **À revoir demain** ; si le recul persiste, il mérite
  une question à part.
  ⓘ **FDR** : 6 908 tests, 1 672 survivants à BH α=0,1, 117 rangs retirés sur
  966 publiés ; version corrigée 6 588 / 1 133, 103 retirés sur 573.
  ⓘ `model_events.json` 9 876 Ko, `model_scores.json` 135 236 Ko,
  `model_murphy.json` 25 850 Ko. **36 183** lignes non publiées, **35 347**
  combinaisons publiables, 34 901 écartées sous le quorum de 8.
- **Second canal du téléphone (Discord)** : ⛔ **`BW_DISCORD_WEBHOOK_URL`
  toujours ABSENTE** du `.env` (recherche sur le **nom seul**, `grep -c` = 0,
  aucune valeur lue). **52ᵉ jour.** ⓘ Et c'est **mesurable** pour la troisième
  fois : **deux** ⛔ ont crié cette nuit, `ⓘ push parti (webhook)` apparaît
  **2 fois**, `push Discord` **0 fois**. Le script
  `~/installer-webhook-discord.sh` est **sur le Mac**. ⇒ **Troisième occasion
  manquée consécutive de prouver le second canal.**
- **`mutations_memoire`** : ⓘ **aucune ligne au journal sur 36 h**
  (`grep -c` = 0) — rien conclu : la dette de 3 mutations non vues (2, 5, 13)
  est reportée telle quelle.
- ⓘ `bw-model-oracle.service` : **non examiné, hors mission.**

## 10. ✅ Les tickets — trois commentaires délibérés, aucun ticket touché

**États revérifiés par GET AVANT toute écriture :**

```
KAN-3 | Terminé | done | updated 2026-10-31T08:24:42+0100 | 36 comm.
KAN-4 | À faire | new  | updated 2026-10-31T08:24:42+0100 | 50 comm.
KAN-5 | À faire | new  | updated 2026-10-31T08:24:41+0100 | 33 comm.
```

⇒ ✅ Les trois `updated` sont **exactement** ceux laissés par le run du 31/10 :
**aucun tiers n'a écrit depuis** — ni la session position de ce matin, ni Yann.
⛔ **Cela confirme par une troisième voie qu'aucune réponse n'a été donnée à la
question de fermeture de KAN-5, ni au motif `regime`.**

**Après écriture**, les trois appels rendent « Jira : commentaire délibéré
ajouté à KAN-5 / KAN-4 / KAN-3 », **une seule fois chacun**.

**Vérifié par GET APRÈS écriture :**

```
KAN-3 | Terminé | done | updated 2026-11-02T08:43:00+0100 | 37 comm.  (+1)
KAN-4 | À faire | new  | updated 2026-11-02T08:42:59+0100 | 51 comm.  (+1)
KAN-5 | À faire | new  | updated 2026-11-02T08:42:58+0100 | 34 comm.  (+1)
```

⇒ ✅ **+1 chacun, exactement** : aucun doublon, et **aucun changement d'état**.

| ticket | ce qui a été posté | état |
|---|---|---|
| **KAN-5** | Les **deux** blocs purge en entier (01/11 **rattrapé** et 02/11) ; les quatre tests de lecture pour les deux nuits, tous au vert, **sonde comprise** ; le compteur **7 / 3** et le fait que le critère est rempli depuis **quatre** jours ⇒ question posée une **quatrième** fois ; ✅ **`n_57014 = 0`** et la **rupture** de la série `bw_character_avance` (quatre nuits, 29/10 au 01/11, le 01/11 étant un point neuf), rattrapée à 100 % (369 080 / 369 080 puis 463 740 / 463 740) ; la série sur 20 nuits ; le volume donné **explicitement** comme non significatif malgré son plus haut ; les **deux** défauts de code, entiers et non sollicités (8ᵉ nuit) ; pourquoi le silence du contrôle est juste *et* par la bonne porte ; la réserve maintenue sur l'absence de preuve SQL. | ✅ **posté ×1** — reste **ouvert** |
| **KAN-4** | Les trois jalons et leurs deltas sur **deux** nuits ; ⚠️ **l'avertissement central** : la configuration est **exactement celle du 30/10**, annulée en vingt-quatre heures, réserve **recitée mot pour mot**, recul **non** présenté comme une amélioration de fond ; la nuance honnête en sens inverse (journée bien plus ventée, +21 % de volume, et le jalon baisse quand même) ; la bande **3 151–3 452 inchangée** (13ᵉ nuit) et **3 348 Mo n'est pas un plancher** ; le coût par ligne rejouée à **1 710,6 o**, **dans** la bande, et le fait que `balise_jours_rejeu` recule en même temps ; ⚠️ **le swap au pic MONTE** (+124 Mo sur deux nuits) alors que c'est une condition de fermeture ; **douzième** matin contradictoire de l'estimateur ; les **trois conditions** ⇒ **non réunies** ; le remède tuple à ≈ −2 015 Mo, **42ᵉ jour**, et le **refus** du calcul à taux constant. | ✅ **posté ×1** — reste **ouvert** |
| **KAN-3** | **Commenté** (canal délibéré) parce que la durée **augmente** de 89 s par rapport à la nuit précédente, et surtout parce qu'une **question prioritaire du 31/10 devait être corrigée**. ⛔ **Le critère `bw-regime-sensibilite` n'est PLUS rempli** : série complète, le −0,96 ms du 01/11 qui la casse, compteur ramené à **1 / 2**, et la **leçon de méthode** (un critère sur deux nuits est fragile à un trou d'observation). Le relevé des deux nuits ; la signature **partagée** (59 % étapes / 41 % hors étapes) et le bloc hors étapes au plus haut des quatre nuits ; la répartition par étape ; le découplage **calcul** (cpu +123 > durée +89) ; ✅ **la hausse de `regime` est du VOLUME** (lignes +2 713, coût par ligne +0,21 ms), l'inverse exact du 31/10 ; le niveau remis dans la série (**5ᵉ des dix**, et **−90 s** vs le 31/10) ; le solde **−253 s sur onze nuits** ; la marge 38,41 % et 3 111 s de réserve ; le rappel du 25ᵉ centile ; la remontée du garde **décrite sans être demandée**. **Avis : NE PAS ROUVRIR.** ⛔ **Non rouvert, non transité.** | ✅ **posté ×1** — reste **Terminé** |
| `bw-regime-sensibilite` | ✅ **NON POSÉ, et la question est RETIRÉE.** Le critère **n'est plus rempli** (1 / 2, §1). Rien n'a été créé, et il n'y a plus de raison d'en créer. | — |
| `bw-melange-sans-gain` | ⛔ **non créé** : **1 / 3** négatifs, et le point n'est pas comparable (§9). Avis : ne pas le créer. | — |
| `bw-r2-palier` | ⛔ **non créé.** ⬆️⬆️ Urgence **RENFORCÉE** : cinquième nuit au-dessus, et le total **remonte** de 151 Mo au plus haut de la série (§6). ❓ **Question reposée.** | — |
| `bw-character-57014` | ⛔ **non créé**, et la série vient de **s'interrompre d'elle-même** (§3.2). Avis : ne pas le créer. | — |
| motif pour la purge | ⛔ **aucun motif neuf** : le motif existe, c'est **KAN-5**, et il est ouvert. | — |

ⓘ **Pourquoi `bw_jira_commenter` trois fois et `bw_jira_signaler` zéro fois** :
le contrôle s'est **tu** ce matin, donc le jeton du jour était **libre** — mais
`bw_jira_signaler` aurait **créé un ticket neuf** sur le motif « Terminé »
(KAN-3, puisque `bw_jira_chercher` filtre sur `statusCategory != Done`), et sur
les deux autres il n'apportait rien de plus. `bw_jira_commenter` prend une
**clé**, ne cherche rien, ne crée rien, ne touche pas au jeton du jour. Choix
assumé de l'arbitrage du 07/10. Signature revérifiée dans `bw_jira.sh` avant
appel (`bw_jira_commenter()`, **ligne 85** ; `bw_jira_http()` ligne 149).

## 11. ⚠️ Horaire de la routine — +19 minutes

Programmée pour le **02/11 à 07:09:05 UTC**, tirée le **02/11 à 07:28:05 UTC** :
**+0 h 19**.

```
24/10 +0 h 02 · 25/10 +0 h 01 · 26/10 +0 h 02 · 27/10 +10 h 09 · 28/10 +1 h 34
29/10 ⛔ +23 h 18 (matin SAUTÉ) · 30/10 +0 h 00 · 31/10 +0 h 00 (47 s)
01/11 ⚠️ +0 h 55 · 02/11 ⚠️ +0 h 19
```

⇒ ⚠️ **Deux matins de retard d'affilée**, mais **beaucoup plus court** (55 min
puis 19 min). Le tir a bien eu lieu, et **une seule fois** — pas de risque de
second run. ⓘ Le VPS est à l'heure : notation à 04:56:35 CET, contrôle à
07:30:05 CET, timer suivant armé pour le **03/11 à 07:30:50 CET**. Le trou, quand
il y en a, est **côté planification**, pas côté VPS.

## 12. Décisions en attente de Yann — la liste à jour

1. ❓ **PRIORITAIRE, et en retard de quatre jours : fermeture de KAN-5.** Le
   critère écrit est **REMPLI** (7 / 3, rempli dès le 29/10). **Veux-tu le
   fermer ?** Je ne ferme rien sans ta réponse. **Quatrième** fois que la
   question est posée.
2. ⬆️⬆️ **PRIORITAIRE, et ça empire : R2 facture, cinquième nuit.** **10,402 Go
   (104,0 %), +151 Mo en deux nuits, plus haut de la série** (§6). ❓ Motif Jira
   `bw-r2-palier`, ou action de rétention ?
3. ⛔ **Mémoire : la ligne en tuple** (≈ −1 030 o/ligne, ≈ −2 015 Mo). **42ᵉ jour
   sans rien de déployé** depuis `af25efb`. Seule porte de sortie de KAN-4 : le
   jalon est à **+548 Mo** du seuil, et le swap au pic **monte**.
4. ⬆️ **`installer-webhook-discord.sh`** (sur le Mac) — **52ᵉ jour**. ⬆️ Son
   intérêt **monte encore** : deux cris cette nuit, **troisième** occasion
   manquée consécutive (§9).
5. ⛔ **Les DEUX correctifs de lecture de la purge** (§3.4), inchangés :
   (a) `bilan_purge` et le suffixe « des lignes RESTENT » ; (b)
   `registre_nuit._INCIDENT` et la ligne de sonde. **Il faut les deux.**
6. ⬆️ **`position_l15_2026-11-02.sql`** à jouer (4 suspensions + 3 renaissances),
   préparé par la session position de ce matin. ✅ Les **sept** cas de position
   sont **tranchés** : ce point n'attend plus qu'un SQL.
7. ⛔ **Deux miroirs git en souffrance** : celui du **24/10** (jamais déposé) et
   celui du **26/10** (présent mais **non suivi par git**). ⚠️ **Et celui du
   01/11 n'a pas pu être déposé** (Mac injoignable) : **trois** dettes. **Rien
   fabriqué après coup.**
8. ⛔ **R2 : rétention sur `agrume/pi`** — **+47 objets chaque nuit, vingt nuits
   d'affilée, sans un seul recul** (§6.3).
9. ⛔ **Inventaire des 4 004 objets de `agrume/pi` que l'index ne réclame pas**
   (sur 4 051). À faire **avant** toute rétention.
10. ⬇️ **`diagnostic_base_sous_tension_2026-09-29.sql`** — **35ᵉ jour** sans être
    joué. Urgence **basse** : huitième nuit d'affilée où la purge aboutit, sept
    sans le moindre avertissement, et `n_57014` est retombé à **0**.
11. ⬇️ **Le `select as_of, count(*)`** sur `model_score_zone` : seule façon de
    **prouver** que la plus vieille journée est partie. **Aucun SQL joué sans ton
    accord.**
12. ⛔ **Pente d'`audit_r2.py`** : borner à zéro les pentes négatives des préfixes
    à fenêtre glissante (§6.3). Une ligne, mais c'est une **écriture**.
13. ⓘ **Réouverture de KAN-3** : **mon avis est NON** — la durée **baisse** de
    90 s sur deux nuits, 4 989 s est le 5ᵉ point des dix, le solde est **−253 s**
    sur onze nuits, la marge est de 3 111 s, et le critère `regime` **n'est plus
    rempli**.
14. ⬇️ **Jalons de temps dans le bloc hors étapes de `run.sh`** — maintenu à
    « utile sans urgence » : 41 % d'une hausse de 89 s, l'argument **ne se
    renforce pas franchement** (§5.1).
15. ⚠️ **NOUVEAU, à surveiller : le recul de 274 balises observées** (3 731 →
    3 461 → 3 457), **stable sur deux nuits** (§9). Pas une question à trancher
    aujourd'hui ; si ça persiste demain, ça en devient une.
16. ⚠️ **NOUVEAU, à surveiller : 8 écarts du recalcul indépendant**, hors de la
    bande 3–7 pour la première fois (§9). Un point très bruité : **à revoir
    demain**, rien de plus.
17. ❓ **`bw-melange-sans-gain`** : **1 / 3** négatifs, point non comparable
    (§9). Mon avis : ne pas créer le motif. À toi de refermer.
18. ⓘ **Le cri de position doit-il recrier** à état constant ? (ouvert depuis le
    01/10) ⬇️ **Encore moins pressant** : on vient de vérifier qu'un front est
    signalé **dans les deux sens** (§7).
19. ⓘ **`mutations_memoire`** : 3 mutations non vues (2, 5, 13), dette
    antérieure, inchangée.
20. ⓘ **`bw-model-oracle.service`** en `failed` — hors mission, non examiné.

✅ **Retirées de la liste** : le motif `bw-regime-sensibilite` (critère **cassé**,
§1) et les **huit cas de position** (tranchés ce matin, §7 — ne reste que le SQL,
point 6). `bw-character-57014` sort aussi : la série s'est interrompue.

## 13. Ce que ce run a DÉMENTI, et ce qu'il a CONFIRMÉ, de la note du 31/10

| annoncé le 31/10 | relevé le 02/11 |
|---|---|
| ⛔ critère `regime` **REMPLI (2 / 2)**, question posée en point n°1 | ⛔ **DÉMENTI, et par la nuit non observée** : 10,92 ms le 01/11 (−0,96), série **cassée**, compteur **1 / 2**. ✅ Rien n'avait été créé |
| ✅ compteur KAN-5 à **5 / 3**, question posée 3ᵉ fois | ✅ **CONFIRMÉ et renforcé** : **7 / 3**, deux nuits propres de plus, 4ᵉ question. ⛔ **Toujours aucune réponse** (vérifié au GET) |
| ⛔ R2 **10,251 Go**, recul de 25 Mo, « rien n'indique un retour sous la barre » | ⛔ **CONFIRMÉ dans le mauvais sens** : **10,402 Go (104,0 %)**, **+151 Mo**, plus haut de la série, 5ᵉ nuit |
| ⚠️ jalon **3 397 Mo**, bande 3 151–3 452, « aucune pente » | ⚠️ **3 348 Mo** : **trois reculs d'affilée** mais bande **inchangée** (13ᵉ nuit) et **pas un plancher**. Validé une **6ᵉ** fois |
| ⚠️ « score par régime » **au-dessus** du seuil, `incidents` 3 | ⚠️ **repassé SOUS** (2 739), `incidents` **2** — ⛔ **exactement la configuration du 30/10**, qui fut annulée en 24 h. **Même réserve posée** |
| ⚠️ coût par ligne rejouée **1 728,4 o**, bande 1 596–1 744 | ⚠️ **1 710,6 o** : −17,8 o, **dans** la bande, 13ᵉ nuit |
| ⚠️ swap : pic **+64,2**, pages **−312 114**, « ne lire ni l'un ni l'autre seul » | ⚠️ pic **+124,0 sur deux nuits** (2 337,5), pages −7 644. ⛔ **Le pic MONTE** : la condition de fermeture s'éloigne |
| ⛔ durée **+145 s** (5 079), hausse **entièrement dans** les étapes | ⚠️ **4 989 s** : **−90 s** vs 31/10, +89 vs 01/11, hausse **PARTAGÉE** (59 / 41 %). Solde **−253 s** sur onze nuits |
| ⛔ `regime` : **pas du volume** (lignes −704, temps +73,5 s) | ✅ **INVERSÉ** : lignes **+2 713**, temps +59 s ⇒ **c'est du VOLUME**, coût par ligne +0,21 ms seulement |
| ⚠️ témoins du mélange **+3,3 %**, « devant » 52,4 %, cinq positifs | ⛔ **+0,6 % puis −0,8 %** : **1 / 3** négatifs, « devant » **48,2 %**. ⚠️ Mais erreur absolue **presque doublée** ⇒ point **non comparable** |
| ⚠️ `n_57014 = 1` hors purge, « fait neuf : TROIS nuits de suite » | ⚠️ quatre nuits (01/11 inclus) puis ✅ **0**. **La série s'interrompt** — quatre points ne faisaient pas une pente |
| ⛔ **8** confirmées de position, cri parti, 12ᵉ vérification « à front » | ✅ **13ᵉ** (01/11 : état constant, **aucun** cri) et **14ᵉ** (02/11 : 8 → **7**, cri parti). ⚠️ **Fait neuf : un front à la BAISSE crie aussi** |
| ⛔ **8 cas de position** à trancher (point n°7) | ✅ **TRANCHÉS ce matin** par l'autre session, `edfa879` poussé. Ne reste que le `.sql` |
| ⛔ `agrume/pi` **18ᵉ** nuit à +48 | ⛔ **20ᵉ nuit**, +47/nuit (4 051 obj, **4 004** non réclamés) |
| ✅ `agrume/grille` refermée à 766 / 766 | ✅ **TIENT** : 5ᵉ nuit à 766 / 766 et 5,323 Go, au Mo près |
| ⚠️ estimateur de pente mémoire **−24 Mo/nuit** | ✅ **validé une 9ᵉ fois** : encore **−24** pendant que le jalon fait −23 puis −26 |
| ✅ webhook `--ipv4` confirmé une 2ᵉ fois (2 pushes) | ✅ **CONFIRMÉ une 3ᵉ fois** : 2 pushes de plus, HTTP 200, **zéro 429**, 2 mails partis |
| ⛔ `BW_DISCORD_WEBHOOK_URL` absente, **50ᵉ** jour | ⛔ **52ᵉ jour**, **3ᵉ** occasion manquée consécutive (2 cris, 0 `push Discord`) |
| ⚠️ écarts du recalcul **6**, bande 3–7 | ⚠️ **5** (01/11) puis ⛔ **8** — **hors bande** pour la première fois. Très bruité, à revoir |
| ⚠️ témoin du corrigé **15,7 pt**, « ça oscille » | ⚠️ 16,6 puis **22,0 pt** — ça oscille toujours, **rien à surveiller** |
| ✅ horaire **+0 h 00** | ⚠️ **+0 h 55** (01/11) puis **+0 h 19** — deux retards, mais qui se **résorbent** |
| ⛔ miroirs git du 24/10 et du 26/10 en souffrance | ⛔ **inchangé**, ⚠️ **plus celui du 01/11** ⇒ trois dettes. **Rien fabriqué** |

⚠️ **« Une nuit ne fait pas une pente » — et quatre non plus.** Appliqué ce
matin à : les **trois** reculs du jalon mémoire (§4.2), le passage sous le seuil
du « score par régime » (§4.1), le −17,8 o du coût par ligne rejouée (§2.1), le
+89 s de la durée (§5.2), le point négatif du mélange (§9), les 8 écarts du
recalcul (§9), le recul de 274 balises observées (§9) et le `n_57014 = 0` (§3.2).
**Aucun des huit n'est présenté comme une tendance.** La tentation du jour était
de lire « la mémoire s'améliore enfin » — alors que c'est **mot pour mot** la
configuration du 30/10, annulée en vingt-quatre heures.

⛔ **Et trois fois, ce matin, la leçon ne s'applique PAS** :
1. Le **critère de fermeture de KAN-5** est une **règle écrite comptée sur trois
   nuits**. Il est rempli depuis **quatre jours**.
2. Le **dépassement du palier R2** est un **fait de facturation**, pas une pente —
   et il **empire**.
3. Les **deux défauts de lecture de la purge** sont des **lectures de code**,
   vraies indépendamment du nombre de nuits.

⛔ **La leçon neuve du jour, et elle est de méthode** : le critère `regime` était
**rempli** le 31/10 sur deux nuits consécutives, et c'est **le point de la nuit
que la routine n'a pas pu lire** qui le casse. ⇒ **Un critère compté sur deux
points consécutifs est fragile à un trou d'observation**, et un trou
d'observation n'est pas une absence d'événement : le registre du VPS avait la
ligne, c'est nous qui ne l'avions pas lue. **Conséquence pratique : après un
matin raté, rattraper la nuit manquante AVANT de reprendre une conclusion
comptée sur des nuits consécutives.** C'est ce qui a été fait ici, et c'est ce
qui a évité de créer un motif Jira sur une série qui n'existait pas.

## 14. Respect des règles

✅ **VPS en LECTURE SEULE, pleine et entière.** Aucun `systemctl`
start/restart/daemon-reload, aucun `enable`, **aucun SQL joué**, aucun rsync,
rien écrit dans `~/balise-watch` ni dans `/etc`. **Aucune redirection vers
`/tmp` du VPS** : toutes les sorties sont allées dans des fichiers du **Mac**
(`/Users/yann/bw-run-02-11/`) et relues avec `read_file`. ⓘ Seules exceptions,
qui sont le fonctionnement normal du code de production : `bw_jira_http` écrit
sa réponse dans un `mktemp -d` du VPS, et le `controle_quotidien.py --verbeux`
relancé à la main ne fait que lire. ⓘ **Le redéploiement AGRUME de ce matin
n'est pas de mon fait** : c'est la session position, avec l'accord de Yann.
✅ **Aucun secret lu par valeur** : `.balise-watch-alertes.env` **sourcé**
(`set -a; . … ; set +a`) ; `BW_DISCORD_WEBHOOK_URL` cherchée **par son nom seul**
(`grep -c`) ; le jeton Jira passe par `curl -K -`, jamais `-u`.
✅ `10-timeout-s3.conf` **non touché** ; remontée du garde **non lancée**, et
seulement **décrite** dans le commentaire KAN-3.
✅ `controle_quotidien.sh` **non touché**, son `$ETAT` conservé. Les deux
correctifs du §3.4 sont **proposés**, pas écrits.
✅ **Aucun ticket créé, fermé, rouvert ni transité.** Trois commentaires, tous
par `bw_jira_commenter`, GET **avant** ET **après** (§10) : +1 commentaire
chacun, aucun doublon, aucun changement d'état.
⛔ **Aucun motif créé**, et celui dont le critère semblait rempli hier est
**retiré** parce que le critère est **cassé** (§1).
✅ **Desktop Commander exclusivement** pour fichiers et shell.
✅ **Lire avant d'écrire** : `git log --since=midnight` dans les deux dépôts
(**un commit trouvé**, lu, et son travail **non refait**) ; `project_read` du
02/11 (absent ⇒ création), du 01/11 et du 31/10 (lus en entier) ;
`notes-projet/README.md` relu ; **note en section horodatée**.
⛔ **Aucun `git push`** de mon fait.
ⓘ **Rien fabriqué pour combler les miroirs manquants** (24/10, 26/10, 01/11).
ⓘ **Rien reconstitué pour la nuit du 01/11** : tous ses chiffres viennent du
registre et du journal du VPS.

## 15. ⓘ Outillage — les pièges connus, tous reconfirmés

1. ✅ **`SSH_AUTH_SOCK` manquant** (piège n°1) : confirmé une huitième fois,
   correctif bon du premier coup.

   ```
   export SSH_AUTH_SOCK="$(launchctl getenv SSH_AUTH_SOCK)"
   ```

2. ✅ **Le lecteur de flux qui perd des lignes** (piège n°2) : contourné d'emblée.
   **Toute sortie dont une ligne compte est redirigée vers un fichier du Mac et
   relue avec `read_file`.**
3. ✅ **« did not respond within 60s » alors que la commande aboutit** (piège
   n°3) : confirmé, et c'est arrivé à **tous** les appels ssh de la session.
   ⛔ **Jamais relancé.** ✅ La bonne réaction : lire le fichier de sortie.
4. ✅ **Les heredocs cités pour le texte français** : les trois corps sont écrits
   dans un script du Mac avec l'outil d'écriture de fichier, dans des heredocs
   `<<'XEOF'`, et le script est passé par `ssh … 'bash -s' < post.sh`. Rien
   d'écrit sur le VPS. Corps **sans accents** ; les accents restent dans la note.
5. ✅ **`bw_jira_http` prend QUATRE arguments** (piège du 31/10) : `$1` méthode,
   `$2` chemin, `$3` corps JSON (**vide** pour un GET), `$4` fichier de sortie.
   Repris tel quel, aucun aller-retour perdu.
