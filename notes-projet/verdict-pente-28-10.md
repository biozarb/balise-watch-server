# Verdict de pente du 28/10/2026 — ✅ **Deuxième nuit propre sur la purge : compteur KAN-5 à 2 / 3, fermeture possible dès le 29/10 avec l'accord de Yann.** ⛔ **R2 reprend 443 Mo et revient à une nuit du palier gratuit (9,564 Go, 95,6 %).** ⓘ **Et l'audit R2 dit pour la PREMIÈRE fois « 28 suppression(s) ratée(s) » : c'est une piste sérieuse sur la question d'hier.** ⚠️ Durée +199 s, jalon +21 Mo — deux rebonds sans portée.

Quatre faits, dans l'ordre d'importance. **(1)** La purge de
`model_score_zone` est **propre de bout en bout pour la deuxième nuit
d'affilée** : 142 819 lignes en 8 tranches, **aucune** tranche en échec,
**aucun** défaut de sonde, `n_57014 = 0` sur toutes les unités ⇒ compteur
KAN-5 **2 / 3**. La troisième nuit propre serait celle du **29/10** :
fermeture envisageable **dès demain**, et **seulement avec l'accord de
Yann**. **(2)** ⓘ **La question ouverte d'hier avance.** L'audit R2 porte
cette nuit une ligne **inédite en sept jours** — `ⓘ 28 suppression(s)
ratée(s), reprise(s) au prochain run` — et l'index de `agrume/grille` lit
**680 présentes / 652 réclamées**, l'écart valant exactement ces 28 objets.
⇒ **Il existe donc bien un mécanisme de suppression actif sur ce préfixe**,
ce qui rend le retrait de 1 125 Mo du 27/10 **beaucoup plus plausible comme
reprise automatique que comme geste humain**. ⚠️ C'est une **piste, pas une
preuve** : la question reste posée à Yann, mais elle change de nature. **(3)**
⛔ **Le répit sur le palier gratuit se referme vite** : 9,121 → **9,564 Go
(95,6 %)**, **+443 Mo et +134 objets en une nuit**, dont +456 Mo sur
`agrume/grille` seul. Il reste **436 Mo** avant les 10 Go : **une nuit
comme celle-ci et le palier est redépassé.** `bw-garde-fou-r2.service` rend
encore `OK en 6s`, code 0 (2ᵉ nuit). **(4)** Durée **+199 s** et jalon
**+21 Mo** : deux rebonds après la nuit record d'hier, **aucun des deux ne
sort de sa bande**, et aucun ne change une décision.

⛔ **KAN-4 reste ouvert** : jalon à **+620 Mo** du seuil et swap au pic qui
**repart de +359 Mo**, annulant aux deux tiers le seul mouvement favorable
d'hier.

ⓘ **Horaire : +1 h 34.** Programmée à 07:09:05 UTC, tirée à 08:42:48 UTC.
Après le +10 h 09 d'hier, c'est un **retour à l'ordre de grandeur des bons
matins**, sans être net pour autant.

## 09:43–10:30 (Paris, CET) — routine Balise Watch, run COMPLET

**Étape 0 : faite en entier, avant toute autre chose.**

- `git log --oneline --since=midnight` dans `balise-watch-server` **et** dans
  `surveillance balise` : **aucun commit aujourd'hui** dans les deux dépôts
  ⇒ aucun autre run n'a tourné ce matin. Dernier commit serveur :
  **`69c5865`** (le miroir du 27/10) — rien de neuf depuis.
- `project_read` de `claude/verdict-pente-28-10.md` : **absent** ⇒ cette note
  est une **création**, pas une fusion. `claude/verdict-pente-27-10.md` lu en
  **entier**.
- `notes-projet/README.md` relu : les quatre règles.
- ⛔ **État des miroirs git, vérifié et non arrangé** : `verdict-pente-24-10.md`
  **toujours absent** ; `verdict-pente-26-10.md` **toujours non suivi par git**
  (`?? notes-projet/verdict-pente-26-10.md`). Rien fabriqué après coup.

## 1. Le relevé de la nuit du 27→28/10

`lancement = timer` · `result = success` · `exec_status = 0` · `oom = 0`
Début 04:57:11, fin 06:19:27 (heure locale du VPS, CET). En UTC le run part à
**03:57:11 Z** contre 03:58:41 Z la veille — **90 s plus tôt**. Le contrôle
est passé à **07:30:20 CET**, suivant armé pour le **29/10 à 07:30:43 CET**.
Relevé **comparable** : le verdict porte.
Self-test du scoring : **VERT** (les cinq contrôles — (a) à 1,0 sur les deux
références, (b) permuté à 2,198 dans la fourchette, skill contre persistance
à −2,2604).

| | 26/10 | 27/10 | 28/10 | Δ nuit |
|---|---:|---:|---:|---:|
| `duree_s` | 5 133 | **4 728** | ⚠️ **4 927** | ⚠️ **+199** |
| `cpu_s` | 4 021,5 | 3 773,8 | **3 935,6** | +161,8 |
| `marge_s` | 2 967 | 3 372 | **3 173** | −199 |
| marge / garde (8 100 s) | 36,63 % | 41,63 % | **39,17 %** | −2,46 pt |
| étapes (somme) | 2 957,6 | 2 853,7 | **2 957,6** | +103,9 |
| hors étapes | 2 175,4 | 1 874,3 | **1 969,4** | +95,1 |
| `jalon_max_mo` | 3 151 | 3 399 | ⚠️ **3 420** | ⚠️ **+21** |
| `mem_peak_mo` | 3 611,1 | 3 618,7 | ✅ **3 587,2** | ✅ **−31,5** |
| `swap_peak_mo` | 2 398,9 | 2 057,4 | ⛔ **2 416,6** | ⛔ **+359,2** |
| `swap_out_pages` | 2 521 164 | 2 023 143 | **2 222 837** | +199 694 |
| `n_57014` | 1 | 0 | ✅ **0** | 0 |
| `incidents` | 3 | 3 | **3** | 0 |
| `lignes_regime` | 139 112 | 138 722 | **138 581** | −141 |
| `lignes_score_zone` | 149 592 | 149 281 | **149 223** | −58 |
| `lignes_daily` | 65 089 | 63 448 | **66 560** | +3 112 |
| `lignes_glissant` | 10 480 | 10 559 | **10 642** | +83 |
| `balise_jours_rejeu` | 2 070 596 | 2 063 862 | **2 060 134** | −3 728 |

Les trois `incidents` sont **tous** de mémoire (rejeu d'archive 2 979, score
par régime 2 808, oubli de la fenêtre rejouée 3 420 Mo). ✅ **Aucun
avertissement de purge, pour la deuxième nuit d'affilée.**

Répartition par étape : `regime` 1 554,7 → **1 622,6** (+67,9) · `glissant`
921,2 → **965,5** (+44,3) · `rejeu` 74,6 → **77,7** (+3,1) · `stabilite`
303,2 → **291,8** (−11,4).

ⓘ La somme des étapes retombe **exactement** sur la valeur du 26/10
(2 957,6 s). C'est une **coïncidence à la décimale**, pas un signal : les
quatre étapes ont bougé séparément dans les deux sens.

### Les deux rapports qui valent mieux que les valeurs brutes

**Coût par ligne rejouée** (`jalon_max_mo × 1048576 / balise_jours_rejeu`) :

```
19/10 1 702,0 o · 20/10 1 608,0 o · 21/10 1 726,1 o · 22/10 1 722,2 o
23/10 1 621,3 o · 24/10 1 723,8 o · 25/10 1 743,9 o · 26/10 1 595,7 o
27/10 1 726,9 o · 28/10 1 740,7 o
```

⇒ ⚠️ **1 740,7 o : +13,8 o, deuxième valeur la plus haute de la série**, à
**3,2 o** du plafond du 25/10. La bande **1 596 à 1 744 o** tient une
**huitième** nuit, et sur dix nuits il n'y a **aucune pente**.
ⓘ Et ce n'est **pas** un artefact de fenêtre, par la même démonstration
qu'hier : `balise_jours_rejeu` **recule** de 3 728, donc le jalon monte
**pendant que** la fenêtre se réduit.

**Coût par ligne de `regime`** (`etapes_s.regime / lignes_regime × 1000`) :

```
21/10 12,14 ms · 22/10 12,59 ms · 23/10 11,97 ms · 24/10 11,42 ms
25/10 12,19 ms · 26/10 11,44 ms · 27/10 11,21 ms · 28/10 11,71 ms
```

⇒ ⚠️ **+4,4 % en une nuit**, après le point le plus bas de la série.
⇒ **critère `bw-regime-sensibilite` : 1 / 2.** Le critère unique arbitré le
07/10 demande **deux hausses consécutives** ; celle-ci est la **première**, la
veille était une **baisse**. **Rien posé, aucune question remontée.**
ⓘ `lignes_regime` recule de 141 : la hausse n'est pas un effet de volume.

**Calcul ou attente ?** La durée prend **199 s**, `cpu_s` **161,8 s** ⇒ environ
**81 %** de la seconde d'horloge ajoutée est une seconde de **calcul**. Les
deux montent ensemble : ce n'est pas de l'attente.

## 2. ✅ LA PURGE : deuxième nuit propre — compteur KAN-5 à 2 / 3

Le bloc purge, en entier :

```
06:19:15  → purge model_score_zone : 142819 ligne(s) effacée(s) en 8 tranche(s)
06:19:15  ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée
```

Deux lignes, et c'est tout. Lecture selon les règles du 28/09 complétées le
07/10 :

| test | verdict |
|---|---|
| tranche en échec | ✅ **✘ aucune** — pas une ligne `?as_of=eq.J&regime=eq.R : HTTP 500` |
| bilan chiffré | ✅ **✔ 142 819 lignes, 8 tranches** |
| « des lignes RESTENT » | ✅ **✘ absent** de la ligne de bilan |
| sonde en défaut | ✅ **✘ aucun** — pas de ligne « plus vieille journée illisible » |

⇒ ✅ **NUIT PROPRE PLEINE, la deuxième d'affilée**, sonde comprise. La réserve
du 26/10 (« l'absence de RESTENT est moins concluante quand la sonde
bronche ») ne s'applique pas davantage ce matin qu'hier.

`n_57014 = 0` au registre, et **0 sur toutes les unités** du journal sur 24 h
(recherche élargie, `grep -c 57014` = 0).

```
13/10 0 · 14/10 1 · 15/10 0 · 16/10 1 · 17/10 0 · 18/10 0 · 19/10 0 · 20/10 0
21/10 0 · 22/10 1 · 23/10 4 · 24/10 0 · 25/10 3 · 26/10 1 · 27/10 0 · 28/10 0
```

### 2.1 ✅ Compteur de fermeture KAN-5 : 2 / 3

Le critère écrit — « trois nuits consécutives sans 57014 dans le bloc purge
ET avec un nombre de lignes lisible » — est rempli sur ses deux branches pour
la **deuxième** fois. Le compteur passe de **1 / 3** à **2 / 3**.
⇒ ❓ **Fermeture envisageable au plus tôt le 29/10, c'est-à-dire DEMAIN, et
seulement avec l'accord de Yann.** Rien n'est fermé, rien n'est transité.
ⓘ La sous-question du 26/10 — la sonde doit-elle compter ? — **ne se pose pas
cette nuit** non plus, puisqu'il n'y a aucun défaut de sonde. Elle reste
ouverte pour les nuits où le cas se représentera.

### 2.2 Le volume : fourchette normale, et toujours pas une preuve

```
26/10   168 198 lignes en 16 tranches, rattrapage
27/10   141 051 lignes en  8 tranches, rien au journal
28/10   142 819 lignes en  8 tranches, rien au journal
```

⇒ Deux nuits de suite à **8 tranches** et dans la fourchette habituelle
(125 000 à 143 000). **Le volume effacé suit le volume de la journée purgée :
il monte et descend sans rien signifier**, et il n'est pas lu comme un signal.
⛔ **Et il n'y a toujours AUCUNE preuve** que la journée 2026-10-17 soit partie
de la base. Seul un `select as_of, count(*) from model_score_zone group by
as_of order by as_of limit 5` le dirait, et **aucun SQL n'a été joué**.
⬇️ Son intérêt reste au niveau d'hier : c'est la seule réponse ferme, et elle
n'est plus urgente.

### 2.3 ⛔ Les deux défauts de code restent entiers, et cette nuit ne les teste pas

1. **(a)** `bilan_purge` ignore le suffixe « des lignes RESTENT » — faux négatif
   démontré le 25/10.
2. **(b)** `registre_nuit._INCIDENT` ne reconnaît pas la ligne de sonde, donc la
   branche `sonde_ko` de `controle_quotidien.constats()` est du **code mort** —
   démontré le 26/10.

⛔ **Aucun des deux n'est déployé, et il faut les DEUX.** Cette nuit n'avait
**ni** ligne restante **ni** sonde en défaut : elle ne pouvait donc **ni** les
confirmer **ni** les réfuter — pour la **deuxième** nuit de suite. Ce sont des
**écritures dans le code** : c'est Yann qui tranche.
ⓘ Et ce n'est toujours pas une raison de retirer le correctif du 07/10 : sans
lui, KAN-5 recevrait « purge en échec » toutes les nuits où une tranche est
rejouée puis rattrapée, ce qui est le cas normal.

### 2.4 Le contrôle de pente s'est tu, et par la bonne porte

```
2026-10-28T06:30:20Z rien à dire : pente plate ou négative, ou échéance hors horizon
```

Verbeux, relancé à la main en lecture seule :

```
ⓘ 90 relevé(s), 69 comparable(s) ; durée : 10 points, pente -143 s/nuit ;
  mémoire : 10 points, pente -188 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate/négative, ou échéance hors horizon
```

✅ Le silence est **juste** et il est **par la bonne porte** : `incidents` ne
porte aucun avertissement de purge **parce qu'il n'y en a eu aucun** — et non,
comme le 26/10, parce que le motif du registre ne sait pas lire la ligne de
sonde. Le défaut (b) n'a, là encore, pas eu l'occasion de nuire.

## 3. ⓘ⛔ LE FAIT DU JOUR : l'audit R2 nomme un mécanisme de suppression — et le palier revient à portée

### 3.1 ⓘ La ligne inédite, et ce qu'elle change à la question d'hier

```
│ agrume/grille/                          680 présentes /  652 réclamées   ✓
│                                        ⓘ 28 suppression(s) ratée(s), reprise(s) au prochain run
```

Historique de cette ligne sur sept jours, vérifié :

```
22/10   766 présentes / 766 réclamées    (aucune mention de suppression)
23/10   766 / 766                        (idem)
24/10   766 / 766                        (idem)
25/10   772 / 772                        (idem)
26/10   766 / 766                        (idem)
27/10   610 / 610                        (idem)  ← le retrait de 1 125 Mo
28/10   680 / 652   + « 28 suppression(s) ratée(s) »   ← INÉDIT
```

⇒ ⓘ **C'est la première apparition de cette ligne en sept jours.** Et l'écart
**680 − 652 = 28** tombe **exactement** sur le nombre de suppressions ratées :
les 28 objets sont présents mais plus réclamés parce que leur suppression a
échoué, et le code annonce qu'il les reprendra.
⇒ ⓘ **Il existe donc bien un mécanisme de suppression actif sur
`agrume/grille`.** Cela rend le retrait de **1 125 Mo / 156 objets** du 27/10
**beaucoup plus plausible comme reprise automatique de ce mécanisme que comme
geste humain** — ce qui était l'hypothèse que je ne pouvais pas départager
hier.
⚠️ **Mais c'est une PISTE, pas une preuve**, et je ne la présente pas
autrement : je constate un mécanisme capable de faire ce retrait, je ne
constate pas qu'il l'a fait. ❓ **La question à Yann reste donc posée, mais
elle change** : non plus « est-ce toi ? » mais « **est-ce bien la rétention de
`agrume/grille` qui a rendu ces 1 125 Mo, et pourquoi 28 de ses suppressions
échouent-elles ?** »

### 3.2 ⛔ Le compte reprend 443 Mo : une nuit avant de redépasser le palier

```
                      26/10            27/10            28/10            Δ nuit
total compte     10,312 Go 103,1 %  9,121 Go 91,2 %  9,564 Go 95,6 %   +443 Mo
objets             7 035            6 943            7 077            +134
pente mesurée                      +0,032 Go/mois   +0,016 Go/mois
palier atteint                        813 j            842 j
```

Par préfixe :

```
                      27/10              28/10              Δ nuit
agrume/grille    4,198 Go  610 obj   4,654 Go  680 obj   +456 Mo / +70 obj
agrume/pi        1,669 Go 3 765 obj  1,690 Go 3 813 obj   +21 Mo / +48 obj
arome/rafale     0,830 Go            0,806 Go             −24 Mo
agrume/colonnes  0,548 Go  100 obj   0,558 Go  102 obj    +10 Mo
arome/sol        0,576 Go            0,556 Go             −20 Mo
```

⇒ ⛔ **La hausse vient presque entièrement de `agrume/grille`** (+456 Mo sur
+443 Mo nets) : le préfixe **reconstruit** ce qu'il avait rendu la veille.
⇒ ⛔ **Il reste 436 Mo avant les 10 Go.** À ce rythme, **une seule nuit
comme celle-ci suffit à redépasser le palier gratuit**. ⚠️ Mais le mot « rythme »
est de trop : c'est un préfixe à **fenêtre glissante** qui vient de rendre
1 125 Mo puis d'en reprendre 456, donc **ni la baisse d'hier ni la hausse
d'aujourd'hui ne sont des tendances**. Ce qu'on peut dire sans se tromper :
**le répit est mince et il n'est pas acquis.**
✅ `bw-garde-fou-r2.service` rend encore **`OK en 6s`, `ExecMainStatus=0`,
`NRestarts=0`, `Result=success`** — **deuxième nuit** de code 0 après onze
échecs. ⓘ Conséquence : **aucun cri n'est parti** (ni R2, ni position), donc
**zéro push**, comme hier.

### 3.3 ⛔ `agrume/pi` : quinzième nuit à +48 objets, sans un seul recul

```
│ agrume/grille/                          680 présentes /  652 réclamées
│ agrume/pi/grille/                        19 présentes /   19 réclamées   ✓
│ agrume/pi/rafraichissement/              28 présentes /   28 réclamées   ✓
│ agrume/piaf/                             11 présentes /   11 réclamées   ✓
```

47 objets couverts sur **3 813** ⇒ **3 766 objets que nul index ne réclame**
(3 718 hier). **+48 par nuit, exactement le rythme d'accumulation, pour la
QUINZIÈME nuit consécutive.**
ⓘ Ce n'est pas la preuve qu'ils sont orphelins ; c'est la constatation qu'on
n'en sait rien. **L'inventaire reste le geste à faire avant toute rétention.**
⚠️ Et **la leçon du 24/10 (§7.1) s'applique une NEUVIÈME fois, dans le sens
inverse d'hier** : hier le total perdait 1 191 Mo sans que l'accumulation
bouge ; aujourd'hui il reprend 443 Mo et l'accumulation n'a toujours bougé que
de ses +48 habituels. **Le total du compte n'est pas un indicateur de
l'accumulation**, ni à la baisse ni à la hausse.

Pente affichée de `agrume/pi` : **+0,580 Go/mois** (hier +0,579), inchangée.
⛔ Le point sur **`audit_r2.py`** (borner à zéro les pentes négatives des
préfixes à fenêtre glissante) reste **entier** : `arome/rafale` **−0,385**,
`arome/sol` **−0,292**, `arome/alt` −0,091, `arome/lod` −0,047 Go/mois tirent
la pente du total à **+0,016 Go/mois** pendant que `agrume/pi` monte à +0,580
— d'où un « palier atteint dans **842 j** » qui n'a aucun sens. **Une
écriture, non faite.**

## 4. ⚠️ Mémoire — +21 Mo, troisième mouvement de suite dans la même bande

```
rejeu d'archive         2 987 → 2 979 Mo    (−8)    ⛔ au-dessus du seuil : +179
score par régime        2 833 → 2 808 Mo   (−25)    ⛔ au-dessus du seuil :   +8
oubli fenêtre rejouée   3 399 → 3 420 Mo   (+21)    ⛔ au-dessus du seuil : +620
```

```
19/10 3 381 · 20/10 3 193 · 21/10 3 424 · 22/10 3 412 · 23/10 3 210
24/10 3 411 · 25/10 3 452 · 26/10 3 151 · 27/10 3 399 · 28/10 3 420
```

⇒ ⚠️ **La bande va de 3 151 à 3 452 Mo, inchangée.** Le record du 25/10 n'est
**pas** battu : il reste **32 Mo** au-dessus. Trois nuits de suite le jalon
bouge (−301, +248, +21) **sans sortir de la bande** ; sur dix nuits il y a
autant de montées que de descentes et **aucune pente nette**.
⚠️ C'est la **douzième** fois en dix-neuf jours que « une nuit ne fait pas une
pente » s'applique ici, et la **troisième** fois de suite que la prudence de la
note de la veille se trouve validée.

### 4.1 L'estimateur de pente, HUITIÈME matin contradictoire

| matin | pente affichée | ce qui s'est passé cette nuit-là |
|---|---:|---|
| 23/10 | −188 Mo/nuit | échéance 25/10 ⇒ démentie dès le 24/10 (+201 Mo) |
| 24/10 | −12 Mo/nuit | ≈ 14/12 |
| 25/10 | −12 Mo/nuit | le matin d'un **record** de +41 Mo |
| 26/10 | −188 Mo/nuit | le matin d'une **chute** de −301 Mo |
| 27/10 | −188 Mo/nuit | le matin d'une **hausse** de +248 Mo |
| 28/10 | **−188 Mo/nuit** | le matin d'une **hausse** de +21 Mo |

⇒ Il affiche la **même** valeur, −188 Mo/nuit, **trois matins de suite**, pour
trois nuits de −301, +248 et +21 Mo. C'est le **25ᵉ centile des différences**,
qui ignore par construction les deux plus grosses variations. Conclusion posée
le 23/10, **confirmée une sixième fois** : **cet estimateur n'est pas
utilisable en prévision** sur cette série. ⓘ L'échéance étant hors horizon
(30 j), le contrôle se tait — et sur ce point précis **il a raison**.

### 4.2 ⚠️ Bornes de lecture, et un mouvement dans chaque sens

✅ `mem_peak_mo` **baisse de 31,5 Mo** (3 587,2) : le pic du processus **recule**
pendant que le jalon monte. C'est donc bien le **jalon seul** qui bouge, et de
peu.
⛔ En revanche le **swap repart** : pic **2 416,6 Mo** (+359,2) et **2 222 837**
pages sorties (+199 694). Le recul du swap, présenté hier comme le seul
mouvement favorable, est **annulé aux deux tiers en une nuit** — ce qui valide
au passage la réserve d'hier (« ce n'est pas un plancher de série »).

### 4.3 Les trois conditions de fermeture de KAN-4

| condition | état |
|---|---|
| le contrôle se tait sur `bw-pente-memoire` | ✅ **remplie** |
| le jalon est mesurément retombé | ⛔ **non** — 3 420 Mo, **+620** au-dessus du seuil |
| le swap au pic ≈ 0 | ⛔ **non** — 2 416,6 Mo, **en hausse de 359** |

⇒ ⛔ **NON RÉUNIES. KAN-4 reste ouvert.**

### 4.4 Le remède, inchangé — et toujours le seul à la bonne échelle

La **ligne en tuple** (§2.6 de l'enquête du 10/09) : ≈ **−1 030 o/ligne**, soit
≈ **−2 023 Mo** sur les 2 060 134 balise-jours rejoués cette nuit — à comparer
aux **620 Mo** qui séparent le jalon du seuil. ⛔ **Rien de déployé côté mémoire
depuis `af25efb` (21/09) — 37ᵉ jour.** ⚠️ L'élagage de `units` avait rendu
−124 Mo au lieu de −1 500 : les gains sont dans la **structure**. La mesure
`tuple` contre `namedtuple` à la sonde reste le préalable.

## 5. ⚠️ Durée — +199 s, moitié hors étapes, et rien qui change une décision

```
            étapes     hors étapes   total
26/10      2 957,6       2 175,4     5 133
27/10      2 853,7       1 874,3     4 728
28/10      2 957,6       1 969,4     4 927
Δ nuit       +103,9         +95,1     +199
```

⇒ ⚠️ **52 % de la hausse est hors étapes, 48 % dans les étapes** — à peu près
moitié-moitié, soit la configuration la plus **banale** de la série récente
(le 26/10 était 100 % dans les étapes, le 27/10 74 % hors étapes).
⇒ ✅ **4 927 s reste la deuxième durée la plus basse des treize dernières
nuits**, et la marge à **39,17 %** est le **troisième meilleur niveau du mois**,
loin du plancher de série (34,57 % le 23/10).

### 5.1 Le bloc hors étapes : troisième écart inexpliqué en trois nuits

Classement sur les **69 relevés comparables** : **1 969,4 s** se place autour
de la **médiane** (1 967,0 s) — contre la 45ᵉ place hier et la 4ᵉ avant-hier.
⇒ ⚠️ **Le bloc n'est pas instrumenté** (publication, Murphy, événements,
pression, duels, purge), donc les **95,1 s** qu'il reprend ne sont **pas
explicables depuis le journal** — comme ne l'étaient ni le +12,7 s du 26/10 ni
le −301,1 s du 27/10. **Trois écarts inexpliqués en trois nuits.**
⬇️ Je **maintiens** la demande de **jalons de temps dans `run.sh`** à « **utile
sans urgence** » (position prise hier) : l'argument se renforce à chaque nuit,
mais aucun de ces écarts n'a de conséquence mécanique. C'est une **écriture**
dans `run.sh` : non faite.

### 5.2 Bornes de lecture, et le garde

⚠️ **Une nuit ne fait pas une pente, et six non plus** : 23/10 **+58**, 24/10
**−236**, 25/10 **+188**, 26/10 **−119**, 27/10 **−405**, 28/10 **+199**.
**Solde des six nuits : −315 s.** La série oscille, et le rebond du jour ne
renverse pas ce solde.

⛔ **Remontée du chien de garde : NON LANCÉE et NON PROPOSÉE.**
`controle_quotidien.proposition()` ne se déclenche pas (pente négative,
échéance hors horizon). La forme reste connue et je la **décris** sans la
demander : écrire la mesure dans l'en-tête de `10-timeout-s3.conf`
(135 → 140/145 min), déployer, vérifier. Avec **3 173 s** de réserve sur 8 100,
aucune urgence mécanique. **C'est Yann qui décide et qui lance.**

ⓘ Rappel, qui vaut pour KAN-3 : la pente du contrôle est le **25ᵉ centile des
différences**. Elle n'a vu ni le +153 s du 01/10, ni le +336 s du 06/10, ni le
+70 s du 07/10, ni le +188 s du 25/10, et elle ne verra pas le **+199 s** de
cette nuit. Ce matin elle affiche **−143 s/nuit**.

## 6. ⚠️ Témoins du mélange — deuxième point positif, et la série reste illisible

```
⛔ témoins du mélange : sur 7 468 balise-jours×échéance, le mélange fait
   3,4982 km/h contre 3,58 pour le meilleur membre a priori
   (gain +2,3 %, mélange devant dans 49,7 % des cas) ;
   contre la moyenne UNIFORME, sur 1 111 : 3,5337 vs 3,6804 (gain +4,0 %)
```

Série du gain contre le **meilleur membre a priori** :

```
−0,6 % (07/10) · +2,5 · +1,7 · −0,3 · +0,9 · −0,9 · +0,1 · +0,8
· −4,0 % (25/10) · −2,2 % (26/10) · +5,2 % (27/10) · +2,3 % (28/10)
```

⇒ ⚠️ **Deuxième point positif de suite**, mais la part « devant » **repasse
juste sous la barre : 49,7 %** (50,3 % hier). Le gain contre la moyenne
**uniforme** tient à **+4,0 %**.
⇒ ✅ **La question du motif `bw-melange-sans-gain` reste refermée** : il
faudrait trois points négatifs consécutifs, et on en est à deux positifs. **Mon
avis est inchangé : ne pas créer le motif.**
⚠️ Et **l'abandon d'hier de l'explication par le niveau de vent se confirme** :
l'erreur absolue remonte à **3,4982 km/h** (3,3749 hier, 7,47 avant-hier) et le
gain **baisse** de 5,2 à 2,3 % — troisième nuit où erreur absolue et gain ne
vont pas dans le même sens. **La série du gain varie beaucoup et rien dans le
journal ne la prédit.**

## 7. ✅ Position — liste strictement identique, aucun cri : 9ᵉ vérification du « à front »

```
⛔ position : 17 balise(s) divergent du gel (10 j lus), dont 3 CONFIRMÉE(S)
   ⛔ pioupiou:2171          38 915 m · 10 j · nœud + profil CHANGENT
   ⛔ pioupiou:84             9 748 m · 10 j · nœud + profil CHANGENT
   ⛔ infoclimat:STATIC0491   1 159 m · 10 j · nœud 0,01 CHANGE
```

⇒ ✅ **Liste strictement identique à celle du 27/10** — mêmes 17 balises, mêmes
3 confirmées, mêmes écarts au mètre — et **aucune ligne « cri déposé pour
envoi »**, **aucun push**, **aucun mail**. C'est la **9ᵉ vérification** du
mécanisme « à front, pas à état ». **Le mécanisme est établi.**
ⓘ La question du 01/10 reste ouverte — **faut-il qu'il recrie à état
constant ?** C'est exactement le cas de ce matin pour le dixième jour de suite.

⚠️ **`pioupiou:1378` reste bloquée à 9 j pour la SIXIÈME journée**, écart
inchangé à **340 941 m**. Elle re-clignote, donc **le compteur de jours ne la
confirmera jamais seule.** 341 km n'est pas un décalage de coordonnées
plausible : candidate nette « AUTRE balise », à trancher à la main.
ⓘ `pioupiou:367` (6 764 m) reste à **9 j**, troisième jour hors des confirmées.
ⓘ **Les onze balises à 6 j hier sont toutes à 7 j** (327, 1749, 1568, 1558, 70,
1724, 1715, 1435, 175, 2058, 633) : la fenêtre se remplit, **aucune n'a
disparu** — elles atteindraient 10 j le **31/10**, échéance confirmée pour la
troisième fois. Et `mf:05170001` passe de 3 à **4 j** (330 m) : rien à en
conclure.

## 8. Les trois correctifs du 07/10 — verdict correctif par correctif

| correctif | verdict du 28/10 |
|---|---|
| **1. webhook `--ipv4`** | ⓘ **ni confirmé ni mis en défaut : rien à envoyer**, pour la deuxième nuit. Aucun ⛔ n'avait à crier (liste de position inchangée, palier non dépassé) ⇒ **zéro push**, et c'est le comportement correct. ✅ **Aucun HTTP 429 ntfy** : `grep -i ntfy \| grep -c 429` = **0**. Les **92** occurrences de « 429 » du journal viennent des pollers aromepi (`run-ingest-pi.sh` 74, `run-ingest-pi-rafale.sh` 12, `run-poller.sh` 4) et de **2 faux positifs** (des nombres dans d'autres lignes de `run.sh`, vérifiés un par un) — **rien à voir avec ntfy**. |
| **2. garde-fou des deux jetons** | ✅ **tient** mécaniquement : le contrôle de 07:30:20 s'est tu, aucun jeton posé, aucun doublon possible. `controle_quotidien.sh` conserve son `$ETAT` — **non touché**. |
| **3. rejeu de purge ≠ échec** | ⓘ **non sollicité**, deuxième nuit : purge propre, aucun avertissement, rien à lire. Les deux défauts du §2.3 restent **entiers**. |

## 9. Les autres témoins

- ⚠️ **Témoin du corrigé : 17,0 pt** (17,9 hier), sur 8 799 balise-jours — vrai
  antécédent **+14,9 %**, autre balise **−2,2 %**. Série de la part site :
  22,9 → 18,0 → 16,6 → 23,3 → 20,4 → 27,8 → 27,6 → 27,1 → 17,9 → **17,0 pt**.
  Version FIN, part secteur+heure : 12,7 → 8,5 → 9,8 → 10,5 → 12,6 → 12,2 →
  13,3 → 13,4 → 11,4 → **10,9 pt** (4 482 balise-jours). ⓘ **Ça oscille**, comme
  conclu les 22 au 27/10 — et après le mouvement de −9,2 pt d'hier, un −0,9 pt
  est un **retour au calme**, pas une tendance. **Rien à surveiller.**
- ⚠️ **Écarts du recalcul indépendant : 4** (4 hier, 5 avant-hier). Série :
  5 · 4 · 7 · 4 · 7 · 5 · 4 · **4** ⇒ elle va de 3 à 7 ; rien à en tirer sur le
  nombre. ✅ **Mais la signature se RELÂCHE, et ma réserve d'hier est
  démentie** : **3 sur 4** portent `1 h appariées ici (< 6)` et **une seule**
  `0 h`, contre **4 sur 4** en `0 h` hier. Hier j'écrivais « le `0 h`
  s'installe » — **c'est démenti en vingt-quatre heures**. Les quatre de cette
  nuit : `fcstagrume/aemet:9814X` (+24 h, 1 h), `fcstagrume/infoclimat:000ZA`
  (+24 h, 1 h), `fcstagrume/aemet:9245X` (+6 h, **0 h**),
  `fcstagrume/infoclimat:STATIC0259` (+24 h, 1 h). Même signature de fond
  (« la base porte une ligne alors que le recalcul n'en apparie pas assez »),
  récurrente et antérieure.
- ⓘ **Écart des deux mélanges** : `mse_comb` 17,841 contre `mse_comb_vec`
  17,841 (**+0,00 %**) — les deux chemins restent confondus.
- **Duels** : `agrume ↔ agrume_pi (+6 h)` n = 7 143, médiane +0,010, IC95
  [+0,007 ; +0,016] → `b_better` · `agrume_pi ↔ bw_mix (+6 h)` n = 7 112,
  médiane +0,422 → `b_better` · `agrume ↔ meteofrance_arome_france_hd (+6 h)`
  médiane −0,001, IC95 [−0,003 ; +0,000] → **`not_separable`** ·
  `agrume_pi ↔ bw_mix (+24 h)` n = 6 866 sur 29 j, médiane +0,498 →
  `b_better`. Cumul toujours **tronqué par la rétention 30 j** (dette connue,
  `duel.DUEL_DAYS`).
  ⓘ **La journée AROME/R2 perdue du 25/10 se voit encore** : le duel
  `arome_r2 ↔ meteofrance_arome_france_hd (+6 h)` porte n = **16 577** sur
  **29 j** quand les autres duels +6 h vont jusqu'au 2026-10-27. Même trou
  qu'hier, qui restera dans la fenêtre glissante jusqu'au 24/11.
- **Murphy** : 67 034 triplets, **63 958** décomposés, 266 balises dehors.
- ⚠️ **Volumes de la nuit, en net rebond, et c'est cohérent** : **66 560**
  agrégats quotidiens (+3 112), **46 455** `model_verif_event` contre 40 850
  (**+14 %**), **405 234** accumulateurs avancés sur 405 234 (374 845 hier),
  `model_events.json` 9 732 Ko, `model_scores.json` 130 733 Ko,
  `model_murphy.json` 25 762 Ko, **685 353 lignes écrites en base** (646 271 la
  veille). ⓘ Les observations suivent à peine (**3 719** balises contre 3 708) :
  c'est la **journée** qui était un peu plus agitée (erreur absolue 3,50 km/h
  contre 3,37), pas la collecte qui a changé. 3 419 balises zonées pour les
  événements, 1 419 cases fines dont 735 sous les 2 balises.
- **Second canal du téléphone (Discord)** : ⛔ **`BW_DISCORD_WEBHOOK_URL`
  toujours ABSENTE** du `.env` (recherche sur le **nom seul**, `grep -c` = 0,
  aucune valeur lue). **47ᵉ jour.** Le script `~/installer-webhook-discord.sh`
  est **sur le Mac**, pas sur le VPS.
- **`mutations_memoire`** : ⓘ **aucune ligne au journal cette nuit non plus**
  (`grep -c` = 0) — rien conclu : la dette de 3 mutations non vues (2, 5, 13)
  est reportée telle quelle.
- ⓘ `bw-model-oracle.service` : **non examiné, hors mission.**

## 10. ✅ Les tickets — trois commentaires postés, aucun ticket touché

**États revérifiés par GET AVANT toute écriture :**

```
KAN-3 | Terminé | done | updated 2026-10-27T18:43:41+0100 | 33 comm.
KAN-4 | À faire | new  | updated 2026-10-27T18:43:40+0100 | 47 comm.
KAN-5 | À faire | new  | updated 2026-10-27T18:43:39+0100 | 30 comm.
```

⇒ ✅ Les trois `updated` sont exactement ceux laissés par le run du 27/10 :
**aucun tiers n'a écrit depuis**, pas de collision.

**Après écriture**, les trois appels rendent `RC=0` et le message
« Jira : commentaire délibéré ajouté à KAN-5 / KAN-4 / KAN-3 », **une seule
fois chacun**.

**Vérifié par GET APRÈS écriture** (joué à 10:59 CET, après le retour du pont —
§16) :

```
KAN-3 | Terminé | done | updated 2026-10-28T09:59:51+0100 | 34 comm.  (+1)
KAN-4 | À faire | new  | updated 2026-10-28T09:59:50+0100 | 48 comm.  (+1)
KAN-5 | À faire | new  | updated 2026-10-28T09:59:50+0100 | 31 comm.  (+1)
```

⇒ ✅ **+1 chacun, exactement** : aucun doublon malgré la coupure, et **aucun
changement d'état**.

| ticket | ce qui a été posté | état |
|---|---|---|
| **KAN-5** | Le bloc purge en entier ; les **quatre** tests de lecture, tous au vert, **sonde comprise**, pour la deuxième nuit ; `n_57014 = 0` sur toutes les unités et la série sur 16 nuits ; le compteur **2 / 3** avec la fermeture possible **dès le 29/10** et le rappel qu'elle demande l'accord de Yann ; le volume (8 tranches, fourchette normale) donné **explicitement comme non significatif** ; les **deux** défauts de code, entiers, et le fait que cette nuit ne pouvait **ni** les confirmer **ni** les réfuter ; pourquoi le silence du contrôle est juste *et* par la bonne porte ; la réserve maintenue sur l'absence de preuve pour le 2026-10-17. | ✅ **posté ×1** — reste **ouvert** |
| **KAN-4** | Les trois jalons et leurs deltas ; **3 420 Mo (+21)**, le record du 25/10 **non battu** à 32 Mo près, et le refus d'y lire une reprise ; coût par ligne rejouée **1 740,7 o** (2ᵉ plus haut) avec la démonstration que ce n'est pas un effet de fenêtre ; `mem_peak` qui **baisse** pendant que le jalon monte, et le **swap qui repart** (+359) en annulant le seul gain d'hier ; **huitième** matin contradictoire de l'estimateur, qui affiche −188 Mo/nuit **trois matins de suite** ; les **trois conditions de fermeture** (muet ✔, plafond ✘ **+620**, swap ✘ **2 416,6 Mo**) ⇒ **non réunies** ; un calcul à taux constant donné **et** réfuté ; le remède tuple à ≈ −2 023 Mo, **37ᵉ jour**. | ✅ **posté ×1** — reste **ouvert** |
| **KAN-3** | **Commenté** (canal délibéré) parce que **la durée remonte**. +199 s, marge **39,17 %**, répartition par étape complète, 52 % hors étapes / 48 % dans les étapes, découplage calcul/attente (**81 % de calcul**), découplage temps/volume (`lignes_regime` recule) ; le bloc hors étapes **non instrumenté** et son **troisième écart inexpliqué en trois nuits** ; critère `regime` **1 / 2** avec la série du coût par ligne et le rappel qu'il faut **deux hausses consécutives** ; le rappel du 25ᵉ centile et la liste des hausses qu'il n'a pas vues ; solde des six nuits **−315 s** ; la remontée du garde **décrite sans être demandée**. **Avis donné : NE PAS ROUVRIR.** ⛔ **Non rouvert, non transité** : reste « Terminé ». | ✅ **posté ×1** — reste **Terminé** |
| `bw-regime-sensibilite` | ⛔ **non posé**, critère **1 / 2** (une seule hausse, la veille était une baisse). Aucune question remontée. | — |
| `bw-melange-sans-gain` | ⛔ **non créé** : deux points **positifs** de suite (§6). Avis : ne pas le créer. | — |
| `bw-r2-palier` | ⛔ **non créé.** ⬆️ Mais son urgence **remonte** : il reste 436 Mo avant le palier (§3.2). | — |
| motif pour la purge | ⛔ **aucun motif neuf** : le motif existe, c'est **KAN-5**, et il est ouvert. | — |

ⓘ **Pourquoi `bw_jira_commenter` trois fois et `bw_jira_signaler` zéro fois** :
le contrôle s'est tu ce matin, donc le jeton du jour était libre — mais
`bw_jira_signaler` aurait **créé un ticket neuf** sur le motif « Terminé »
(KAN-3, puisque `bw_jira_chercher` filtre sur `statusCategory != Done`), et sur
les deux autres il n'apportait rien de plus. `bw_jira_commenter` prend une
**clé**, ne cherche rien, ne crée rien, ne touche pas au jeton du jour. C'est le
choix assumé de l'arbitrage du 07/10.

## 11. ⓘ Horaire de la routine — +1 h 34, retour à l'ordre de grandeur habituel

Programmée pour **07:09:05 UTC**, tirée à **08:42:48 UTC** : **+1 h 34**.

```
17/10 +1 h 56 · 18/10 +1 h 39 · 19/10 +7 h 43 · 20/10 +3 h 41 · 21/10 +8 h 50
22/10 +4 h 23 · 23/10 +4 h 21 · 24/10 +0 h 02 · 25/10 +0 h 01 · 26/10 +0 h 02
27/10 ⛔ +10 h 09 · 28/10 ⓘ +1 h 34
```

ⓘ Après le pire retard du mois, c'est le **troisième meilleur de la série
depuis le 17/10**, mais ce n'est pas « à l'heure » : un verdict rendu à 9 h 43
au lieu de 8 h 09 reste une heure et demie après le fait.
ⓘ **Le trou est côté planification, pas côté VPS.** Le VPS est à l'heure :
notation à 04:57:11 CET, contrôle à 07:30:20 CET, timer suivant armé pour le
**29/10 à 07:30:43 CET**.

## 12. Décisions en attente de Yann — la liste à jour

1. ❓ **PRIORITAIRE : fermeture de KAN-5.** Compteur **2 / 3**. Si la nuit du
   29/10 est propre, le critère écrit est rempli. **Veux-tu le fermer demain ?**
   Je ne ferme rien sans ta réponse.
2. ❓ **La question du 27/10 sur `agrume/grille`, reformulée** (§3.1) : l'audit
   montre un **mécanisme de suppression actif** (« 28 suppression(s) ratée(s) »,
   ligne inédite) ⇒ le retrait de 1 125 Mo était **probablement** cette reprise
   et **pas** un geste humain. Reste à confirmer, et à savoir **pourquoi 28
   suppressions échouent**.
3. ⬆️ **R2 : il reste 436 Mo avant le palier gratuit** (9,564 Go, 95,6 %), après
   +443 Mo en une nuit (§3.2). Le répit d'hier n'est pas acquis.
4. ⛔ **Deux miroirs git en souffrance** : celui du **24/10** (jamais déposé) et
   celui du **26/10** (présent mais **non suivi par git**). Rien fabriqué après
   coup. Le miroir du 26/10 est **réparable sans rien inventer** (le document
   projet est complet). Dis-moi si tu veux que je le fasse.
5. ⛔ **Les DEUX correctifs de lecture de la purge** (§2.3), inchangés :
   (a) `bilan_purge` et le suffixe « des lignes RESTENT » ; (b)
   `registre_nuit._INCIDENT` et la ligne de sonde. **Il faut les deux.**
6. ⬇️ **`diagnostic_base_sous_tension_2026-09-29.sql`** — **30ᵉ jour** sans être
   joué. Urgence basse : **troisième nuit d'affilée** où la purge aboutit, deux
   sans le moindre avertissement. Lecture seule, 9 blocs, SQL Editor.
7. ⬇️ **Le `select as_of, count(*)`** sur `model_score_zone` : seule façon de
   **prouver** que le 2026-10-17 est parti. **Aucun SQL joué sans ton accord.**
8. ⛔ **R2 : rétention sur `agrume/pi`** — **+48 objets chaque nuit, quinze
   nuits d'affilée, sans un seul recul** (§3.3).
9. ⛔ **Inventaire des 3 766 objets de `agrume/pi` que l'index ne réclame pas**
   (sur 3 813). À faire **avant** toute rétention.
10. ⛔ **Mémoire : la ligne en tuple** (≈ −1 030 o/ligne, ≈ −2 023 Mo). **37ᵉ
    jour sans rien de déployé** depuis `af25efb`. Seule porte de sortie de
    KAN-4 : le jalon est à **+620 Mo** du seuil.
11. ⛔ **Pente d'`audit_r2.py`** : borner à zéro les pentes négatives des
    préfixes à fenêtre glissante (§3.3) — le « palier dans 842 j » n'a aucun
    sens. Une ligne, mais c'est une **écriture**.
12. ⛔ **Les 3 cas de position confirmés** (§7) : trancher, puis
    `position_suspecte` + `position_note` par `.sql`. ⚠️ Et **`pioupiou:1378`** :
    341 km, bloquée à 9 j **six jours de suite** parce qu'elle clignote — elle
    ne se confirmera jamais seule. ⓘ Les onze balises à 7 j atteindraient 10 j
    le **31/10**.
13. ⓘ **Réouverture de KAN-3** : **mon avis est NON** — un rebond de 199 s après
    −405 s, dans une bande dont le solde sur six nuits est **−315 s**.
14. ⬇️ **Jalons de temps dans le bloc hors étapes de `run.sh`** — maintenu à
    « utile sans urgence » (§5.1), mais **troisième écart inexpliqué en trois
    nuits**.
15. ❓ **`bw-melange-sans-gain`** : **ne se confirme pas** (deux points positifs,
    §6). Mon avis : ne pas créer le motif. À toi de refermer la question.
16. ⚠️ **`installer-webhook-discord.sh`** (sur le Mac) — **47ᵉ jour**, variable
    absente.
17. ⓘ **Le cri de position doit-il recrier** à état constant ? (ouvert depuis le
    01/10 ; « à front » vérifié **neuf** jours de suite — §7)
18. ⓘ **`mutations_memoire`** : 3 mutations non vues (2, 5, 13), dette
    antérieure, inchangée.
19. ⓘ **`bw-model-oracle.service`** en `failed` — hors mission, non examiné.

## 13. Ce que ce run a DÉMENTI, et ce qu'il a CONFIRMÉ, de la note du 27/10

| annoncé le 27/10 | relevé le 28/10 |
|---|---|
| ✅ compteur KAN-5 à **1 / 3**, fermeture au plus tôt le 29/10 | ✅ **2 / 3** : deuxième nuit propre pleine ⇒ l'échéance du **29/10** est **tenue** |
| ⛔ les deux défauts de code (a) et (b), entiers | ⓘ **non sollicités une 2ᵉ nuit** : ni ligne restante, ni sonde en défaut. Restent **entiers** |
| ⛔ volume « cohérent mais pas une preuve » pour le 2026-10-17 | ⓘ **toujours pas de preuve**, et toujours aucun SQL joué |
| ❓ « qui a retiré 1 125 Mo de `agrume/grille` ? » — **auteur inconnu** | ⓘ **PISTE SÉRIEUSE** : ligne inédite « 28 suppression(s) ratée(s) » + index 680/652 ⇒ un **mécanisme de suppression actif** existe. Pas une preuve, mais la question change de nature |
| ✅ R2 **9,121 Go (91,2 %)**, « gain non acquis » | ⛔ **VÉRIFIÉ, et vite** : **9,564 Go (95,6 %)**, +443 Mo en une nuit, 436 Mo avant le palier |
| ✅ `bw-garde-fou-r2` rend code 0, fin de 11 échecs | ✅ **2ᵉ nuit à code 0** : `OK en 6s`, `Result=success` |
| ⛔ `agrume/pi` **14ᵉ** nuit à +48 | ⛔ **15ᵉ nuit à +48**, et le total **remonte** ⇒ **9ᵉ vérification** du §7.1 du 24/10, en sens inverse |
| ⚠️ jalon 3 399 Mo (+248), « aucune pente » | ⚠️ **3 420 Mo (+21)** : bande 3 151–3 452 **inchangée**, record du 25/10 **non battu**. Le refus de lire une pente est **validé une 3ᵉ fois** |
| ⚠️ réserve sur l'estimateur de pente | ✅ **validée une SIXIÈME fois** : −188 Mo/nuit **trois matins de suite** pour −301, +248, +21 |
| ✅ swap au plus bas (2 057,4 Mo), « pas un plancher de série » | ✅ **réserve VALIDÉE** : **2 416,6 Mo** (+359), le gain est annulé aux deux tiers |
| ✅ durée −405 s, la plus basse des 12 nuits | ⚠️ **+199 s** : rebond, mais **2ᵉ plus basse des 13 nuits** et solde sur six nuits **−315 s** |
| ⛔ bloc hors étapes : 45ᵉ sur 68, « bosse finie », demande à « utile sans urgence » | ⚠️ **retour à la médiane** (1 969,4 s) : ni bosse ni creux, **3ᵉ écart inexpliqué en 3 nuits**. Demande **maintenue** à « utile sans urgence » |
| ⓘ critère `regime` à 0 / 2, point le plus bas | ⚠️ **passe à 1 / 2** : +4,4 %, première hausse. Rien posé |
| ✅ témoins du mélange **+5,2 %**, question refermée | ⚠️ **+2,3 %**, « devant » **49,7 %** ⇒ 2ᵉ point positif, question **reste refermée** |
| ⛔ explication du mélange par le niveau de vent **abandonnée** | ✅ **confirmée abandonnée** : erreur absolue **remonte** et gain **baisse** — 3ᵉ nuit où les deux divergent |
| ✅ « à front, pas à état », 8ᵉ vérification | ✅ **9ᵉ vérification** : liste identique au mètre ⇒ aucun cri, aucun push |
| ⚠️ `pioupiou:1378` bloquée à 9 j, 5ᵉ jour | ⚠️ **6ᵉ jour**, écart inchangé à 340 941 m |
| ⓘ onze balises à 6 j, 10 j le 31/10 | ✅ **toutes à 7 j**, échéance **31/10** confirmée une 3ᵉ fois |
| ⚠️ témoin du corrigé 17,9 pt, « ça oscille » | ✅ **confirmé** : 17,0 pt (−0,9), retour au calme après −9,2 |
| ⛔ écarts du recalcul : 4, **4 sur 4** en `0 h`, « le `0 h` s'installe » | ⛔ **DÉMENTI en 24 h** : 4 écarts, **1 sur 4** en `0 h`, 3 en `1 h` |
| ⛔ horaire **+10 h 09**, pire retard du mois | ⓘ **+1 h 34** : retour à l'ordre de grandeur habituel, sans être net |
| ⛔ miroirs git du 24/10 et du 26/10 en souffrance | ⛔ **inchangé**, vérifié et non arrangé |

⚠️ **« Une nuit ne fait pas une pente » — douzième fois en dix-neuf jours.**
Appliqué ce matin à : la hausse du jalon (§4), la hausse du coût par ligne
rejouée (§1), la hausse de la durée (§5.2), la hausse du coût par ligne de
`regime` (§1), la hausse du total R2 (§3.2), la baisse du témoin du mélange
(§6) et le rebond des volumes (§9). **Aucun des sept n'est présenté comme une
tendance.** La tentation du jour était la symétrique d'hier : hier presque tout
se retournait vers le mieux, aujourd'hui presque tout revient — et dans les
deux cas une nuit ne dit rien.

⛔ **Et deux fois, ce matin, la leçon ne s'applique PAS.** La ligne « 28
suppression(s) ratée(s) » est un **fait de journal** inédit en sept jours, pas
une tendance à confirmer. Et les **deux défauts de lecture de la purge** sont
des **lectures de code**, vraies indépendamment du nombre de nuits.

## 14. Respect des règles

✅ **VPS en LECTURE SEULE, pleine et entière.** Aucun `systemctl`
start/restart/daemon-reload, aucun `enable`, **aucun SQL joué**, aucun rsync,
rien écrit dans `~/balise-watch` ni dans `/etc`. **Aucune redirection vers
`/tmp` du VPS** : toutes les sorties sont allées dans des fichiers du **Mac** et
relues avec `read_file`. ⓘ Seules exceptions, qui sont le fonctionnement normal
du code de production : `bw_jira_http` écrit sa réponse dans un `mktemp -d` du
VPS, et le `controle_quotidien.py --verbeux` relancé à la main ne fait que lire.
✅ **Aucun secret lu par valeur** : `.balise-watch-alertes.env` **sourcé**
(`set -a; . … ; set +a`) ; `BW_DISCORD_WEBHOOK_URL` cherchée **par son nom seul**
(`grep -c`) ; le jeton Jira passe par `curl -K -`, jamais `-u`.
✅ `10-timeout-s3.conf` **non touché** ; remontée du garde **non lancée**, et
seulement **décrite** dans le commentaire KAN-3.
✅ `controle_quotidien.sh` **non touché**, son `$ETAT` conservé. Les deux
correctifs du §2.3 sont **proposés**, pas écrits.
✅ **Aucun ticket créé, fermé, rouvert ni transité.** Trois commentaires, tous
par `bw_jira_commenter`, GET **avant** ET **après** chacun (§10) : +1
commentaire chacun, aucun doublon, aucun changement d'état.
✅ **Desktop Commander exclusivement** pour fichiers et shell.
✅ **Lire avant d'écrire** : `project_read` du 28/10 (absent ⇒ création) et du
27/10 (lu en entier) ; `git log --since=midnight` dans les deux dépôts ;
`notes-projet/README.md` relu.
⛔ **Aucun `git push`.**
ⓘ **Rien fabriqué pour combler les miroirs manquants** (24/10, 26/10).

## 15. ⓘ Outillage — les pièges connus, et une coupure

1. ✅ **`SSH_AUTH_SOCK` manquant** (piège n°1) : confirmé une cinquième fois, et
   le correctif marche du premier coup.

   ```
   export SSH_AUTH_SOCK="$(launchctl getenv SSH_AUTH_SOCK)"
   ```

   Dans un **process persistant** (`start_process "bash -l"` +
   `interact_with_process`), `ssh-add -l` voit ensuite
   `balise-watch-vps (ED25519)`.
2. ✅ **Le lecteur de flux qui perd des lignes** (piège n°2) : contourné
   d'emblée. **Toute sortie dont une ligne compte est redirigée vers un fichier
   du Mac et relue avec `read_file`** — c'est ce qui a permis de récupérer le
   résultat des trois `bw_jira_commenter` malgré la coupure.
3. ✅ **« did not respond within 60s » alors que la commande aboutit** (piège
   n°3) : confirmé, et c'est arrivé à **presque tous** les appels. ⛔ **Jamais
   relancé.** ✅ La bonne réaction : lire le fichier de sortie.
4. ✅ **Les heredocs cités pour le texte français** : les corps des trois
   commentaires sont écrits dans un script du Mac avec l'outil d'écriture de
   fichier, dans des heredocs `<<'XEOF'` (donc sans expansion ni échappement),
   et le script est passé par `ssh … 'bash -s' < post.sh`. Aucune apostrophe
   mutilée, aucun mot de la liste noire dans la commande, et **rien d'écrit sur
   le VPS**. Plus simple que le base64 du 27/10, et suffisant.
5. ⛔ **Le pont vers le Mac a COUPÉ** juste après la pose des trois
   commentaires : d'abord un `disconnected before responding`, puis la
   disparition complète des outils Desktop Commander (serveur MCP déconnecté).
   ⇒ Sur le moment, deux choses restaient en suspens : le **GET de contrôle
   après écriture** et le **miroir git**. Les trois commentaires, eux, étaient
   bien partis **une fois chacun** (`RC=0` et message du canal lus dans le
   fichier de sortie avant la coupure).
   ✅ **Les deux ont été reprises après le retour du pont, sans rien
   reposter — voir §16.**
   ⓘ **Ce qui a sauvé le run** : la règle du piège n°2 (toute sortie qui compte
   va dans un fichier du Mac). Le résultat des trois `bw_jira_commenter` était
   déjà sur disque quand le pont a coupé ; sans ça, j'aurais eu à choisir entre
   ne rien savoir et risquer un doublon.

## 16. ✅ 10:55–11:10 (Paris, CET) — reprise après la coupure du pont

Le pont vers le Mac est revenu une quinzaine de minutes après la coupure. Les
**deux** points laissés en suspens au §15.5 sont faits, et **rien n'a été
reposté**.

1. ✅ **GET de contrôle des trois tickets, joué** (`get_states.sh`, déjà sur le
   Mac) : **34 / 48 / 31** commentaires contre 33 / 47 / 30 avant écriture,
   soit **+1 chacun exactement**, et **aucun changement d'état** (KAN-3
   Terminé/done, KAN-4 et KAN-5 À faire/new). ⇒ **Aucun doublon n'a été créé
   par la coupure.** Détail reporté au §10.
2. ✅ **Miroir git déposé et commité en LOCAL** dans
   `notes-projet/verdict-pente-28-10.md`, depuis la **racine** du dépôt
   serveur. ⛔ **Aucun `git push`.**

ⓘ **Comment le miroir a été déposé sans retranscrire 650 lignes** : plutôt que
de réécrire la note chunk par chunk avec l'outil d'écriture de fichier, le
fichier a été transféré directement du conteneur vers le Mac
(`device_request_folder_access` sur `notes-projet/`, puis
`device_commit_files`), et seul le `git add` / `git commit` est passé par le
shell. **Le texte n'a pas traversé le contexte une deuxième fois** — c'est la
variante « descendante » de l'astuce du 07/10, et elle marche aussi bien.

⚠️ **Et ce qui n'a PAS été arrangé** : les miroirs du **24/10** (jamais déposé)
et du **26/10** (présent mais non suivi par git) restent **tels quels**. Rien
fabriqué après coup — ils attendent l'accord de Yann (§12, point 4).
