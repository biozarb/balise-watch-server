# Verdict de pente du 03/11/2026 — ⛔ **Le critère `bw-regime-sensibilite` est de nouveau REMPLI (2 / 2) : 10,92 → 11,13 → 11,58 ms. Question reposée, rien créé.** ✅ **Purge propre une TROISIÈME nuit : KAN-5 à 8 / 3, et ta décision a cinq jours de retard.** ⬆️ **R2 à 10,433 Go (104,3 %) : sixième nuit au-dessus du palier, encore le plus haut.** ✅ **Swap au pic −245 Mo : ma note du 02/11 est corrigée, dans le bon sens.**

## 08:10–08:35 (Paris, CET) — routine Balise Watch, run du jour

**Étape 0 : faite en entier, avant toute autre chose.**

- `git log --oneline --since=midnight` : ✅ **aucun commit du jour**, ni dans
  `balise-watch-server`, ni dans le dépôt principal. **Aucune autre session n'a
  tourné ce matin.**
- `project_read claude/verdict-pente-03-11.md` : **absent** ⇒ cette note est une
  **création**, pas une fusion. Elle est en **section horodatée** (règle n°2).
- `project_read claude/verdict-pente-02-11.md` : ✅ **lu en entier** — c'est lui
  qui sert de référence, et c'est lui que je corrige sur deux points (§4.3 et
  §9). `claude/session-position-l15-02-11.md` : ✅ **lu**, et sa prédiction est
  **vérifiée** ce matin (§7).
- `notes-projet/README.md` relu : les quatre règles.
- ⓘ **Le travail n'était pas fait. Je le fais.**

## 1. ⛔ LE CRITÈRE `bw-regime-sensibilite` EST DE NOUVEAU REMPLI — 2 / 2

**Coût par ligne de `regime`** (`etapes_s.regime / lignes_regime × 1000`) :

```
21/10 12,14 ms · 22/10 12,59 · 23/10 11,97 · 24/10 11,42 · 25/10 12,19
26/10 11,44 · 27/10 11,21 · 28/10 11,71 · 29/10 10,86 · 30/10 11,30
31/10 11,88 · 01/11 10,92 · 02/11 11,13 · 03/11 ⬆️ 11,58 ms
```

Deux hausses consécutives : **10,92 → 11,13 (+0,21) → 11,58 (+0,46)**. Le critère
unique arbitré le 07/10 — « la hausse s'additionne **deux nuits de suite** » —
est donc **REMPLI (2 / 2)**.
⇒ ✅ **Conformément à la règle, RIEN N'A ÉTÉ CRÉÉ. La question est reposée à
Yann.**

### 1.1 ⚠️ La mise en garde que je me fais à moi-même — et elle compte

⛔ **C'est EXACTEMENT la situation du 31/10.** Ce matin-là le critère était
rempli 2 / 2 (10,86 → 11,30 → 11,88) et la question était posée en **point
n°1**. Il a été **démoli vingt-quatre heures plus tard** par le point du 01/11
(10,92 ms, **−0,96**), une nuit que la routine n'avait pas pu lire.
⇒ ⚠️ La **leçon de méthode du 02/11 tient toujours** : un critère compté sur deux
nuits consécutives est **fragile**. Et **11,58 ms n'est pas un niveau
remarquable** — 12,59 le 22/10, 12,19 le 25/10, 12,14 le 21/10. **Le niveau n'a
jamais été le critère.**
⇒ ⓘ **Mon avis : attendre une troisième nuit avant de poser un motif.** Mais
c'est la décision de Yann, pas la mienne, et la règle dit de **reposer la
question** — c'est fait.

## 2. Le relevé de la nuit

`lancement = timer` · `result = success` · `exec_status = 0` · `oom = 0`.
Self-test du scoring **VERT** (les cinq contrôles ; `mse_comb` 17,841 ;
permuté 2,198 ; skill contre persistance −2,2604). Relevé **comparable** : le
verdict porte.

Nuit du 02→03/11 : début **04:55:06**, fin **06:20:08** (CET). Journée notée
**2026-11-02**. Contrôle passé à **07:31:05** CET, suivant armé pour le **04/11
à 07:30:18 CET**.

| | 31/10 | 02/11 | 03/11 | Δ(02→03) |
|---|---:|---:|---:|---:|
| `duree_s` | 5 079 | 4 989 | **5 088** | **+99** |
| `cpu_s` | 4 068,4 | 4 006,3 | **4 077,5** | +71,2 |
| `marge_s` | 3 021 | 3 111 | 3 012 | −99 |
| marge / garde (8 100 s) | 37,30 % | 38,41 % | **37,19 %** | −1,22 pt |
| étapes (somme) | 3 050,5 | 2 936,1 | **3 026,9** | **+90,8** |
| hors étapes | 2 028,5 | 2 052,9 | **2 061,1** | **+8,2** |
| `jalon_max_mo` | 3 397 | 3 348 | **3 348** | **0** |
| `mem_peak_mo` | 3 612,7 | 3 598,5 | 3 595,9 | −2,6 |
| `swap_peak_mo` | 2 213,5 | 2 337,5 | ✅ **2 092,2** | **−245,3** |
| `swap_out_pages` | 2 172 144 | 2 164 500 | **1 933 664** | −230 836 |
| `n_57014` | 1* | 0 | ✅ **0** | 0 |
| `incidents` | 3 | 2 | **2** | 0 |
| `lignes_regime` | 139 999 | 143 669 | **144 012** | **+343** |
| `lignes_score_zone` | 150 712 | 154 362 | 154 706 | +344 |
| `lignes_daily` | 68 572 | 66 009 | 66 916 | +907 |
| `lignes_glissant` | 10 713 | 10 693 | 10 694 | +1 |
| `balise_jours_rejeu` | 2 060 898 | 2 052 228 | 2 049 292 | −2 936 |

(*) `n_57014 = 1` le 31/10, mais **hors bloc purge**.

Répartition par étape (s) :

| étape | 31/10 | 02/11 | 03/11 | Δ(02→03) |
|---|---:|---:|---:|---:|
| `regime` | 1 663,3 | 1 598,7 | **1 668,2** | **+69,5** |
| `glissant` | 985,6 | 962,1 | 967,9 | +5,8 |
| `stabilite` | 321,4 | 290,2 | 307,5 | +17,3 |
| `rejeu` | 80,2 | 85,1 | 83,3 | −1,8 |

⇒ ⚠️ **Hausse à 92 % DANS les étapes** (90,8 s sur 99) et 8 % hors étapes
(8,2 s). C'est la signature du **31/10**, et l'inverse exact des cinq nuits
d'octobre où tout était hors étapes. **`regime` porte 69,5 s à lui seul**, soit
70 % de la hausse totale.

### 2.1 Les deux rapports qui valent mieux que les valeurs brutes

**Coût par ligne rejouée** (`jalon_max_mo × 1048576 / balise_jours_rejeu`) :

```
19/10 1 702,0 o · 20/10 1 608,0 · 21/10 1 726,1 · 22/10 1 722,2 · 23/10 1 621,3
24/10 1 723,8 · 25/10 1 743,9 · 26/10 1 595,7 · 27/10 1 717,5 · 28/10 1 740,4
29/10 1 743,9 · 30/10 1 728,7 · 31/10 1 728,4 · 01/11 1 720,6 · 02/11 1 710,6
03/11 1 713,1 o
```

⇒ ⚠️ **Le recul de trois nuits s'arrête : +2,5 o.** La bande **1 596 à 1 744 o**
tient une **quatorzième** nuit, et **1 713,1 o est DANS la bande**.
ⓘ Et `balise_jours_rejeu` **recule encore** (−2 936) alors que le jalon **ne
bouge pas** : la fenêtre se rétrécit sans que le jalon suive.

**Calcul ou attente ?** ⚠️ **Majoritairement du calcul, mais pas entièrement.**
La durée prend **99 s** et `cpu_s` en prend **71,2**, soit **72 %** de la hausse.
≈ 28 s ne sont pas du CPU. ⓘ **Je ne conclus rien de ces 28 s** : c'est dans le
bruit d'une nuit.

## 3. ✅ LA PURGE : troisième nuit propre — compteur KAN-5 à 8 / 3

Bloc purge du **03/11**, en entier :

```
2026-11-03 06:19:52  → purge model_score_zone : 149592 ligne(s) effacée(s) en 8 tranche(s)
2026-11-03 06:19:52  ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée
```

Les quatre tests de lecture (règles du 28/09 complétées le 07/10) :

| test | 03/11 |
|---|---|
| tranche en échec | ✅ **✘ aucune** |
| bilan chiffré | ✅ **✔ 149 592 / 8 tr.** |
| « des lignes RESTENT » | ✅ **✘ absent** |
| sonde en défaut | ✅ **✘ aucun** |

⇒ ✅ **TROISIÈME NUIT PROPRE PLEINE d'affilée**, sonde comprise.

### 3.1 ✅ Compteur de fermeture KAN-5 : 8 / 3 — cinq jours de retard

```
27/10 propre → 1 / 3 · 28/10 → 2 / 3 · 29/10 → 3 / 3  ⇐ CRITÈRE REMPLI
30/10 → 4 / 3 · 31/10 → 5 / 3 · 01/11 → 6 / 3 · 02/11 → 7 / 3 · 03/11 → 8 / 3
```

⇒ ❓ **Le critère écrit est rempli depuis le 29/10, soit CINQ jours.** Question
posée pour la **cinquième** fois (28/10, 30/10, 31/10, 02/11, 03/11).
⛔ **Rien n'est fermé, rien n'est transité.**
ⓘ **Vérifié par une troisième voie** : le GET d'avant écriture rend
`updated = 2026-11-02T08:42:58+0100` et **34** commentaires — **exactement**
l'état laissé par le run du 02/11. **Aucun tiers n'a écrit depuis, aucune
réponse n'a été enregistrée** — ni sur KAN-5, ni sur R2, ni sur `regime`.

### 3.2 ✅ `n_57014 = 0` : deuxième nuit, et pour la première fois ZÉRO PARTOUT

Recherche élargie sur **toutes** les unités, 36 h : `grep -c 57014` = **0**.
⇒ ✅ **Zéro occurrence nulle part**, ce qui n'était **encore jamais arrivé** dans
la série. Les accumulateurs passent à **100 %** : **432 583 / 432 583**.

```
13/10 0 · 14/10 1 · 15/10 0 · 16/10 1 · 17/10 0 · 18/10 0 · 19/10 0 · 20/10 0
21/10 0 · 22/10 1 · 23/10 4 · 24/10 0 · 25/10 3 · 26/10 1 · 27/10 0 · 28/10 0
29/10 1* · 30/10 1* · 31/10 1* · 01/11 1* · 02/11 0 · 03/11 ✅ 0   (* hors purge)
```

⇒ ⛔ **Avis inchangé : NE PAS créer `bw-character-57014`.** La série s'est
interrompue d'elle-même. ⚠️ **Et deux nuits à zéro partout ne sont pas une preuve
de correctif** — il y a eu **trois** nuits à zéro d'affilée (03, 04, 05/10) avant
que le 57014 revienne le 06.

### 3.3 Le volume : encore un plus haut, et toujours pas un signal

```
28/10 142 819 · 29/10 143 625 · 30/10 147 216 · 31/10 145 123
01/11 148 173 · 02/11 148 683 · 03/11 149 592 lignes — toutes en 8 tranches
```

⇒ **Sept nuits de suite à 8 tranches.** Le volume effacé suit le volume de la
journée purgée : **il monte et descend sans rien signifier**, ni à la hausse ni
à la baisse. ⛔ **Et il n'y a toujours AUCUNE preuve** que la plus vieille journée
soit partie de la base : seul un `select as_of, count(*) … group by as_of order
by as_of limit 5` le dirait, et **aucun SQL n'a été joué**.

### 3.4 ⛔ Les deux défauts de code restent entiers — neuvième nuit non testée

1. **(a)** `bilan_purge` ignore le suffixe « des lignes RESTENT » — faux négatif
   démontré le 25/10.
2. **(b)** `registre_nuit._INCIDENT` ne reconnaît pas la ligne de sonde, donc la
   branche `sonde_ko` de `controle_quotidien.constats()` est du **code mort** —
   démontré le 26/10.

⛔ **Il faut les DEUX.** Cette nuit n'avait ni ligne restante ni sonde en défaut :
**neuvième nuit de suite** où ils ne peuvent être **ni** confirmés **ni**
réfutés. Ce sont des **écritures dans le code** : Yann tranche.

### 3.5 Le contrôle s'est tu, et par la bonne porte

```
2026-11-03T06:31:05Z rien à dire : pente plate ou négative, ou échéance hors horizon
```

Verbeux, relancé à la main en lecture seule :

```
ⓘ 96 relevé(s), 75 comparable(s) ; durée : 10 points, pente -119 s/nuit ;
  mémoire : 10 points, pente -24 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate/négative, ou échéance hors horizon
```

✅ Le silence est **juste** et **par la bonne porte** : `incidents` ne porte aucun
avertissement de purge **parce qu'il n'y en a eu aucun**.
ⓘ **96 / 75** contre 95 / 74 le 02/11 : **+1 et +1**, cohérent avec exactement
**une** nuit de plus.
⚠️ **Une seule ligne au journal du contrôle** ⇒ pas de second tir, jeton du jour
**libre** quand la routine a écrit.

## 4. ✅ Mémoire — le jalon est exactement stable, et le swap recule franchement

```
                        02/11   03/11   Δ      vs seuil 2 800
rejeu d'archive         2 941   2 951   +10     ⛔ +151
score par régime        2 739   2 725   −14     ✅ −75  (SOUS LE SEUIL, 2ᵉ nuit)
oubli fenêtre rejouée   3 348   3 348     0     ⛔ +548
```

`incidents` : 2 → **2**.

### 4.1 ⚠️ Le jalon qui décide : 3 348 Mo au Mo près, bande inchangée (14ᵉ nuit)

```
19/10 3 381 · 20/10 3 193 · 21/10 3 424 · 22/10 3 412 · 23/10 3 210 · 24/10 3 411
25/10 3 452 · 26/10 3 151 · 27/10 3 399 · 28/10 3 420 · 29/10 3 424 · 30/10 3 400
31/10 3 397 · 01/11 3 374 · 02/11 3 348 · 03/11 3 348
```

⇒ ⚠️ **Le recul de trois nuits s'arrête net : delta 0.** La bande va toujours de
**3 151 à 3 452 Mo, INCHANGÉE pour la quatorzième nuit** ; 3 348 Mo reste
**au-dessus** du 20/10 (3 193), du 23/10 (3 210) et du 26/10 (3 151). **Ce n'est
pas un plancher**, et sur seize nuits il n'y a **aucune pente nette**.
⚠️ **Seizième application** de « une nuit ne fait pas une pente » : le recul de
trois nuits annoncé hier **ne s'est pas poursuivi**, exactement comme je m'en
étais réservé la possibilité.

### 4.2 ⚠️ « Score par régime » : deuxième nuit sous le seuil — réserve maintenue

2 725 Mo, soit **75 Mo** sous le seuil (contre 61 Mo hier). ⚠️ **Je maintiens la
réserve du 30/10 et du 02/11, mot pour mot** : la configuration du 30/10 (jalon
sous le seuil, `incidents` à 2) avait été **annulée en vingt-quatre heures**.
Elle tient cette fois **deux** nuits — c'est une nuit de plus que la fois
précédente, **pas une tendance**. ⛔ Et **rien n'a été déployé** côté mémoire qui
puisse l'expliquer.

### 4.3 ✅ CORRECTION de ma note du 02/11 : le swap au pic RECULE

⛔ **Le 02/11 j'ai écrit** : « le pic de swap n'est pas proche de zéro : il est en
**HAUSSE** » (+124 Mo sur deux nuits) et « la condition de fermeture **s'éloigne**
pendant que le jalon se rapproche ».
⇒ ✅ **DÉMENTI ce matin, dans le bon sens** :

```
swap_peak_mo     2 337,5 → 2 092,2 Mo   (−245,3, le plus gros recul de la série)
swap_out_pages   2 164 500 → 1 933 664  (−230 836)
```

✅ Les **deux** indicateurs vont pour la première fois dans le **même** sens, à la
baisse : la **divergence pic / pages** signalée les 30, 31/10 et 02/11 est
**levée** cette nuit.
⚠️ **Mais je ne présente PAS cela comme une amélioration de fond** : 2 092,2 Mo
n'est pas « ≈ 0 », c'est encore **plus de 2 Go** de swap au pic, et **rien n'a été
déployé** qui puisse l'expliquer. **Une nuit ne fait pas une pente — y compris
quand elle va dans le sens qui m'arrange.**
⚠️ **Lecture honnête du contexte** : la journée notée était **beaucoup MOINS
ventée** que la veille — erreur absolue du mélange **4,41** contre 5,70 km/h,
`model_verif_event` **51 382** lignes contre 72 506, lignes écrites en base
**723 226** contre 774 214. ⇒ Une partie du recul du swap est **très probablement
de la charge en moins**, pas de la structure en mieux.

### 4.4 L'estimateur de pente, treizième matin contradictoire

**−24 Mo/nuit**, inchangé depuis le 30/10, pendant que le jalon fait −26 puis
**0**. C'est le **25ᵉ centile des différences**. Conclusion du 23/10 **confirmée
une dixième fois** : **cet estimateur n'est pas utilisable en prévision** sur
cette série. ⓘ L'échéance étant hors horizon, le contrôle se tait — et sur ce
point précis **il a raison**.

### 4.5 Les trois conditions de fermeture de KAN-4

| condition | état |
|---|---|
| le contrôle se tait sur `bw-pente-memoire` | ✅ **remplie** (6ᵉ matin) |
| le jalon est mesurément retombé | ⛔ **non** — 3 348 Mo, **+548** au-dessus |
| le swap au pic ≈ 0 | ⛔ **non** — 2 092,2 Mo, **en net recul mais très loin de 0** |

⇒ ⛔ **NON RÉUNIES. KAN-4 reste ouvert.**

### 4.6 Le remède, inchangé

La **ligne en tuple** (§2.6 de l'enquête du 10/09) : ≈ **−1 030 o/ligne**, soit
≈ **−2 012 Mo** sur les 2 049 292 balise-jours rejoués cette nuit — à comparer
aux **548 Mo** qui séparent le jalon du seuil. ⛔ **Rien de déployé côté mémoire
depuis `af25efb` (21/09) — 43ᵉ jour.** ⚠️ L'élagage de `units` avait rendu
−124 Mo au lieu de −1 500 : les gains sont dans la **structure**. La mesure
`tuple` contre `namedtuple` à la sonde reste le préalable.
ⓘ Un calcul à taux constant donnerait « seuil atteint en N nuits » ; je le
**refuse**, parce que la série n'a pas de pente — **ni à la hausse, ni à la
baisse**.

## 5. Durée — +99 s, et cette fois ce n'est PAS du volume

```
            étapes     hors étapes   total
31/10      3 050,5       2 028,5     5 079
02/11      2 936,1       2 052,9     4 989
03/11      3 026,9       2 061,1     5 088
```

### 5.1 La signature : 92 % dans les étapes

⇒ ⚠️ **Signature du 31/10 retrouvée.** ⬇️ **Conséquence pratique : la demande de
jalons de temps dans le bloc hors étapes de `run.sh` NE SE RENFORCE PAS ce
matin** — ce bloc n'explique que **8,2 s sur 99**. Elle reste « utile sans
urgence », et c'est une **écriture** : Yann décide.

### 5.2 ⛔ Volume contre temps : c'est le TRAVAIL PAR LIGNE, l'inverse de la veille

```
lignes_regime     143 669 → 144 012   (+343 seulement)
etapes_s.regime    1 598,7 → 1 668,2  (+69,5 s)
coût par ligne       11,13 → 11,58    (+0,46 ms)
```

⇒ ⛔ Le **02/11** les lignes faisaient **+2 713** pour +59 s : c'était du
**volume**. Cette nuit le volume est **quasi constant** et le temps monte : c'est
le **travail par ligne**. `lignes_score_zone` +344, `lignes_daily` +907,
`lignes_glissant` +1 : **aucun des trois n'explique les 69,5 s**.
⇒ C'est précisément ce qui **remplit** le critère du §1.

### 5.3 Le niveau et la marge

```
24/10 5 064 · 25/10 5 252 · 26/10 5 133 · 27/10 4 728 · 28/10 4 927
29/10 4 921 · 30/10 4 934 · 31/10 5 079 · 01/11 4 900 · 02/11 4 989 · 03/11 5 088 s
```

⇒ ⚠️ **5 088 s est le TROISIÈME point le plus haut des dix derniers**, sous le
25/10 (5 252) et le 26/10 (5 133), et il dépasse de **9 s** le pic local du
31/10.
⚠️ **Solde des deltas depuis le 23/10** : +58, −236, +188, −119, −405, +199, −6,
+13, +145, −179, +89, **+99** ⇒ **−154 s sur douze nuits.** Le solde reste
**négatif**, mais il **s'est réduit de 99 s** : première remontée en trois nuits.
⚠️ **Marge : 37,19 % du garde**, 3 012 s de réserve sur 8 100. C'est la marge la
**plus basse depuis le 07/10** (35,5 %), mais **aucune urgence mécanique**.

### 5.4 Le garde

⛔ **Remontée du chien de garde : NON LANCÉE et NON DEMANDÉE.**
`controle_quotidien.proposition()` ne se déclenche pas. La forme, **décrite** et
non demandée : écrire la mesure dans l'en-tête de `10-timeout-s3.conf`
(135 → 140/145 min), déployer, vérifier. **C'est Yann qui décide et qui lance.**

ⓘ Rappel : la pente du contrôle est le **25ᵉ centile des différences**. Elle
affiche encore **−119 s/nuit**. Elle n'a vu ni le +153 s du 01/10, ni le +336 s
du 06/10, ni le +70 s du 07/10, ni le +188 s du 25/10, ni le +199 s du 28/10,
ni le +145 s du 31/10, ni le +89 s du 02/11, et elle ne verra pas le **+99 s**
de cette nuit.

## 6. ⬆️ R2 : sixième nuit au-dessus du palier — 10,433 Go, encore le plus haut

```
                      31/10             02/11             03/11            Δ vs 02/11
total compte     10,251 Go 102,5 %  10,402 Go 104,0 %  10,433 Go 104,3 %   ⬆️ +31 Mo
objets             7 343             7 467             7 527              +60
pente mesurée    +0,008 Go/mois     +0,021 Go/mois     +0,020 Go/mois
palier atteint      0 j               0 j               0 j
```

⇒ ⬆️ **Sixième nuit consécutive au-dessus du palier gratuit** (le garde-fou dit
« **6 consécutif(s)** »), et c'est **encore le plus haut relevé de la série**. Le
journal le dit sans détour :
`⚠️ palier gratuit DÉPASSÉ : 10.43 Go sur 10 Go — R2 facture déjà`.
ⓘ La hausse **ralentit** (+151 Mo sur deux nuits, puis +31 Mo sur une) — mais
elle **ne s'inverse pas**, et le fait de facturation ne dépend pas d'une pente.
ⓘ Le seuil d'alerte (12 Go) et le seuil d'arrêt de chaîne (6 Go) ne sont pas en
cause ; couverture **complète**.

Par bucket : `balise-watch-grids` **9,467 Go / 6 246 obj** (+22 Mo, **+46 obj**) ·
`model-verif` **0,962 Go / 1 068 obj** (+10 Mo, +14 obj) ·
`balise-watch-packs` 0,005 Go / 213 obj (inchangé).
ⓘ Les deux hausses d'objets s'additionnent exactement au total : 46 + 14 = **60**.

Par préfixe (02/11 → 03/11) : `agrume/grille` 5,323 → **5,323 Go / 766 obj**
(identique au Mo près) · `agrume/pi` 1,791 → **1,812 Go / 4 099 obj** ·
`arome/rafale` 0,837 → 0,840 · `arome/sol` 0,567 → 0,570 ·
`agrume/colonnes` 0,528 → **0,519 Go / 96 obj** (**−2 objets**).

### 6.1 ✅ `bw-garde-fou-r2` code 1 : son comportement normal

```
2026-11-03T05:20:15Z run garde-fou-r2 en ÉCHEC (code 1, 6s) — 6 consécutif(s)
```

✅ **Ce n'est PAS une panne.** La démonstration du 21/10 tient : **code 1 =
« j'ai quelque chose à dire »**. Le palier est dépassé, donc il parle, et son
cri est parti (§8).

### 6.2 ✅ `agrume/grille` : la fermeture du 31/10 tient — sixième nuit

**766 / 766 et 5,323 Go**, au Mo et à l'objet près, pour la **sixième** nuit
consécutive, et toujours aucune ligne « suppression(s) ratée(s) ». La question
du 27/10 reste **refermée** ; je ne la réouvre pas.
ⓘ Fait neuf, petit : sa pente passe à **−0,004 Go/mois** (elle était à 0). C'est
l'effet d'un préfixe strictement stable dans une fenêtre glissante, **rien de
plus**.

### 6.3 ⛔ `agrume/pi` : vingt-et-unième nuit d'accumulation, sans un seul recul

```
│ agrume/pi/grille/            19 présentes /  19 réclamées   ✓
│ agrume/pi/rafraichissement/  28 présentes /  28 réclamées   ✓
```

47 objets couverts sur **4 099** ⇒ **4 052 objets que nul index ne réclame**
(4 004 le 02/11). **+48 en une nuit — exactement le rythme, pour la vingt-et-
unième nuit consécutive.**
ⓘ Ce n'est pas la preuve qu'ils sont orphelins ; c'est la constatation qu'on
**n'en sait rien**. **L'inventaire reste le geste à faire avant toute rétention.**

⛔ Le point sur **`audit_r2.py`** (borner à zéro les pentes négatives des préfixes
à fenêtre glissante) reste **entier** : `arome/rafale` **−0,378**, `arome/sol`
**−0,287**, `arome/alt` −0,091, `arome/lod` −0,047, `agrume/colonnes` −0,024 et
désormais `agrume/grille` −0,004 Go/mois tirent la pente du total à
**+0,020 Go/mois** pendant que `agrume/pi` monte à **+0,581**.
ⓘ Conséquence : « palier atteint dans **0 j** », juste **par accident** (le palier
EST dépassé) et non par la pente. **Une écriture, non faite.**

## 7. ✅ Position — le cri est parti, et la prédiction du 02/11 est VÉRIFIÉE

```
⛔ position : 16 balise(s) divergent du gel (10 j lus), dont 5 CONFIRMÉE(S) (≥ 10 j)
   ⛔ infoclimat:STATIC0491  1 159 m · 10 j · nœud 0,01 CHANGE
   ⛔ pioupiou:70              551 m · 10 j · nœud 0,01 CHANGE · Déco Salève
   ⛔ pioupiou:1715            429 m · 10 j · nœud + profil CHANGENT · Windbird 1715
   ⛔ mf:05170001              330 m · 10 j · nœud 0,01 CHANGE
   ⛔ pioupiou:2058            242 m · 10 j · nœud 0,01 CHANGE · Ernio
⛔ position : 5 balise(s) CONFIRMÉE(S) — cri déposé pour envoi
   + mf:05170001 : 330 m, 10 j
   - pioupiou:1378 : rentree dans l'ordre
   - pioupiou:175  : rentree dans l'ordre
   - pioupiou:2171 : rentree dans l'ordre
```

⇒ ✅ **LA PRÉDICTION DE LA SESSION POSITION DU 02/11 EST VÉRIFIÉE, et en une
nuit** : elle annonçait « le cri de position doit se refermer pour
**1378 / 2171 / 175**, puisque gel = vivant après la première ingestion AGRUME
sur le nouvel artefact ». **Les trois sont rentrées dans l'ordre.** Le regel
L15-bis (`edfa879`) a fait exactement ce qu'il devait faire.
⇒ ⚠️ **Il reste les quatre suspensions** (1715, 2058, 70, STATIC0491) : elles sont
**toujours confirmées**, ce qui est **attendu** — le `.sql` de suspension n'a pas
été joué (point n°6 de la liste). ⛔ **`position_l15_2026-11-02.sql` attend
toujours Yann.**
⇒ ⚠️ **Et une balise NEUVE confirmée : `mf:05170001`**, 330 m, 10 j, nœud 0,01
change. Elle était à 9 j le 02/11 ; elle est arrivée à l'échéance. **Un cas à
trancher, le même geste que les sept autres.**
ⓘ **Le mécanisme « à front, pas à état » est vérifié une 15ᵉ fois** : l'état passe
de 7 à 5, trois sorties et une entrée ⇒ le cri part, et il **nomme les deltas**,
pas l'état.
ⓘ `pioupiou:367` à **9 j**, `pioupiou:84` **retombée à 8 j** (elle était rentrée
dans l'ordre le 02/11, elle ressort — à surveiller). Les huit balises du 29/10
sont à **6 j** (10 j le **07/11**). `pioupiou:157` passe à **2 j**, 172 591 m —
**rien à en conclure encore**.
ⓘ La ligne « **9 balise(s) née(s) sous leur identifiant** » est **inchangée** :
c'est **normal**, la session du 02/11 annonçait le passage de 9 à 12 **au 05/11**
(`notee_depuis = '2026-11-05'`). **Rendez-vous dans deux nuits.**

## 8. Les trois correctifs du 07/10 — verdict correctif par correctif

| correctif | verdict du 03/11 |
|---|---|
| **1. webhook `--ipv4`** | ✅ **CONFIRMÉ une QUATRIÈME fois, sur deux cris distincts.** Deux choses à envoyer (cri de position **et** palier R2), **deux** `ⓘ push parti (webhook, HTTP 200)` à **05:20:06Z** et **05:20:15Z**. ✅ **Aucun HTTP 429 ntfy** : `grep -i ntfy \| grep -c 429` = **0** sur 36 h. ✅ Les deux mails sont partis (`msmtp … smtpstatus=250 … exitcode=EX_OK`, 1 432 et 2 806 octets). ⇒ Huit pushes partis sur quatre nuits : le correctif **tient**. |
| **2. garde-fou des deux jetons** | ✅ **tient** mécaniquement : le contrôle de 07:31:05 s'est **tu**, **une seule ligne** au journal, aucun jeton posé, aucun doublon possible — et les trois commentaires de ce matin sont passés par le canal **délibéré**, qui ne touche pas au jeton. `controle_quotidien.sh` conserve son `$ETAT` — **non touché**. |
| **3. rejeu de purge ≠ échec** | ⓘ **non sollicité**, neuvième nuit : purge propre, aucun avertissement, rien à lire. Les deux défauts du §3.4 restent **entiers**. |

## 9. Les autres témoins

- ⛔ **Témoins du mélange : DEUXIÈME point négatif consécutif — compteur 2 / 3.**
  ```
  31/10 : gain +3,3 %, devant 52,4 %, erreur 2,998 km/h
  01/11 : gain +0,6 %, devant 49,3 %, erreur 3,5115 km/h
  02/11 : gain −0,8 %, devant 48,2 %, erreur 5,7029 km/h
  03/11 : gain −2,5 %, devant 46,9 %, erreur 4,4082 km/h
  ```
  Série du gain contre le **meilleur membre a priori** : −0,6 % (07/10) · +2,5 ·
  +1,7 · −0,3 · +0,9 · −0,9 · +0,1 · +0,8 · −4,0 (25/10) · −2,2 · +5,2 · +2,3 ·
  +0,5 · +3,0 · +3,3 · +0,6 · −0,8 · **−2,5 %**.
  ⇒ ⚠️ **Compteur du motif `bw-melange-sans-gain` : 2 / 3 négatifs.** Il faut
  **trois** points négatifs consécutifs. ⛔ **Une nuit de plus et le critère est
  rempli** — c'est le point à surveiller demain.
  ⚠️ **Et cette fois la pondération du 07/10 joue CONTRE moi, honnêtement** :
  l'erreur absolue a **baissé** (5,70 → 4,41 km/h, journée moins ventée) et le
  gain contre la moyenne **uniforme** tient encore (**+4,8 %**), mais le gain
  contre le meilleur membre **s'aggrave** et « devant » descend pour la
  **quatrième** nuit de suite (52,4 → 49,3 → 48,2 → **46,9 %**). ⇒ L'excuse
  « journée atypique » ne s'applique **pas** ce matin. ❓ **Avis : ne pas créer le
  motif aujourd'hui (2 / 3), mais la question est à reposer demain.**
- ⚠️ **Témoin du corrigé** : part site **23,0 pt** (sur 8 680 balise-jours —
  vrai antécédent +14,7 %, autre balise −8,3 %). Série : 27,8 → 27,6 → 27,1 →
  17,9 → 17,0 → 19,8 → 15,0 → 15,7 → 16,6 → 22,0 → **23,0 pt**. Version FIN,
  part secteur+heure : 11,4 → 10,9 → 11,8 → 9,1 → 9,6 → 11,8 → 11,5 → **13,0 pt**
  (5 017 balise-jours). ⓘ **Ça oscille**, comme conclu depuis le 22/10. **Rien à
  surveiller.**
- ✅ **Écarts du recalcul indépendant : 6 — RETOUR DANS LA BANDE.** Série :
  5 · 4 · 7 · 4 · 7 · 5 · 4 · 4 · 4 · 4 · 6 · 5 · 8 · **6**. ⇒ ✅ **Le point hors
  bande du 02/11 (8) était bien du bruit** : la bande 3–7 est **restaurée**, et
  ma réserve d'hier (« très bruité, à revoir demain, rien de plus ») est
  **vérifiée**. Signature : **4 sur 6** portent `0 h appariées ici (< 6)` et
  **2 sur 6** portent `4 h` — même signature de fond, récurrente et antérieure.
  ⓘ Les six : `fcstagrume/infoclimat:STATIC0287` (+48 h),
  `fcstagrume/mf:26168001` (+24 h, 4 h), `fcstagrume/pioupiou:1623` (+24 h, 4 h),
  `fcstagrume/infoclimat:000YH` (+48 h), `fcstagrume/pioupiou:1352` (+24 h),
  `fcstagrume/windsmobi:ffvl-5093` (+6 h). ⓘ Tirage de 20 strates sur **13**
  balise-jours comparés, dont 7 sous le seuil de 6 h.
- ⓘ **Écart des deux mélanges** : `mse_comb` 17,841 contre `mse_comb_vec`
  17,841 (**+0,00 %**) — les deux chemins restent confondus.
- **Duels** : `agrume ↔ agrume_pi (+6 h)` n = 7 099, médiane +0,010, IC95
  [+0,006 ; +0,016] → `b_better` · `agrume_pi ↔ bw_mix (+6 h)` n = 7 082,
  médiane +0,390, IC95 [+0,317 ; +0,479] → `b_better` ·
  `agrume ↔ meteofrance_arome_france_hd (+6 h)` médiane −0,000, IC95
  [−0,002 ; +0,002] → **`not_separable`** ·
  `arome_r2 ↔ meteofrance_arome_france_hd (+6 h)` n = 16 613 sur **29 j**,
  médiane +0,087 → `b_better` · `agrume_pi ↔ bw_mix (+24 h)` n = 6 836 sur
  **29 j**, médiane +0,464 → `b_better`. Cumul toujours **tronqué par la
  rétention 30 j** (dette connue, `duel.DUEL_DAYS`).
  ⓘ **La journée AROME/R2 perdue du 25/10 se voit encore** : `arome_r2` porte
  **29 j** quand les duels +6 h vont jusqu'au 2026-11-02. Jusqu'au **24/11**.
- **Murphy** : 67 653 triplets / **63 709** décomposés / 266 tenus dehors.
- ⚠️ **Observations : le recul TIENT une troisième nuit.**
  **3 461** balises observées (3 457 le 02/11, 3 461 le 01/11, **3 731** le
  31/10). ⚠️ Le recul de ≈ 270 balises est donc **stable sur trois nuits**, il
  n'oscille pas : 3 731 → 3 461 → 3 457 → 3 461. `lignes_daily` suit
  (68 572 → 65 111 → 66 009 → 66 916). 3 160 zonées, 1 231 cases fines dont 601
  sous les 2 balises. ⓘ Je **ne** l'explique toujours **pas**. ⇒ ❓ **Trois nuits
  stables : ça mérite maintenant une question à part**, c'est-à-dire de savoir si
  270 balises ont cessé d'émettre ou si la chaîne d'ingestion en perd.
  ⓘ **FDR** : brut 6 842 tests, 1 645 survivants à BH α=0,1, 113 rangs retirés
  sur 952 publiés ; corrigé 6 527 / 1 143, 120 retirés sur 589.
  ⓘ `model_events.json` 9 861 Ko, `model_scores.json` 135 541 Ko,
  `model_murphy.json` 25 996 Ko. **36 195** lignes non publiées, **35 286**
  combinaisons publiables, 35 025 écartées sous le quorum de 8.
  ⓘ `model_verif_event` **51 382** lignes (contre 72 506) : `breeze_yield` 74,
  `drop` 19 533, `onset` 18 255, `ramp` 12 001, `reversal` 1 519. Journée
  **beaucoup moins ventée**.
- **Second canal du téléphone (Discord)** : ⛔ **`BW_DISCORD_WEBHOOK_URL`
  toujours ABSENTE** du `.env` (recherche sur le **nom seul**, `grep -c` = 0,
  aucune valeur lue). **53ᵉ jour.** ⓘ Et c'est **mesurable** pour la quatrième
  fois : **deux** ⛔ ont crié cette nuit, `ⓘ push parti (webhook)` apparaît
  **2 fois**, `push Discord` **0 fois**. Le script
  `~/installer-webhook-discord.sh` est **sur le Mac**. ⇒ **Quatrième occasion
  manquée consécutive de prouver le second canal.**
- **`mutations_memoire`** : ⓘ **aucune ligne au journal sur 36 h**
  (`grep -c` = 0) — rien conclu : la dette de 3 mutations non vues (2, 5, 13)
  est reportée telle quelle.
- ⓘ `bw-model-oracle.service` : **non examiné, hors mission.**

## 10. ✅ Les tickets — trois commentaires délibérés, aucun ticket touché

**États revérifiés par GET AVANT toute écriture :**

```
KAN-3 | Terminé | done | updated 2026-11-02T08:43:00+0100 | 37 comm.
KAN-4 | À faire | new  | updated 2026-11-02T08:42:59+0100 | 51 comm.
KAN-5 | À faire | new  | updated 2026-11-02T08:42:58+0100 | 34 comm.
```

⇒ ✅ Les trois `updated` sont **exactement** ceux laissés par le run du 02/11 :
**aucun tiers n'a écrit depuis.**
⛔ **Cela confirme par une troisième voie qu'aucune réponse n'a été donnée** —
ni à la question de fermeture de KAN-5 (5ᵉ fois posée), ni à R2, ni au motif
`regime`.

**Après écriture**, les trois appels rendent « Jira : commentaire délibéré
ajouté à KAN-5 / KAN-4 / KAN-3 », **une seule fois chacun**.

**Vérifié par GET APRÈS écriture :**

```
KAN-3 | Terminé | done | updated 2026-11-03T08:15:53+0100 | 38 comm.  (+1)
KAN-4 | À faire | new  | updated 2026-11-03T08:15:52+0100 | 52 comm.  (+1)
KAN-5 | À faire | new  | updated 2026-11-03T08:15:51+0100 | 35 comm.  (+1)
```

⇒ ✅ **+1 chacun, exactement** : aucun doublon, et **aucun changement d'état**.

| ticket | ce qui a été posté | état |
|---|---|---|
| **KAN-5** | Le bloc purge en entier ; les quatre tests de lecture, tous au vert, **sonde comprise** ⇒ **troisième** nuit propre pleine ; le compteur **8 / 3** et le fait que le critère est rempli depuis **cinq** jours ⇒ question posée une **cinquième** fois ; ✅ **`n_57014 = 0` et pour la première fois ZÉRO PARTOUT sur 36 h** (grep toutes unités = 0), accumulateurs **432 583 / 432 583** ; la série sur 21 nuits et le rappel que **trois nuits à zéro (03-05/10) n'avaient pas été un correctif** ; le volume donné **explicitement** comme non significatif malgré son plus haut ; les **deux** défauts de code, entiers et non sollicités (9ᵉ nuit) ; pourquoi le silence du contrôle est juste *et* par la bonne porte (96 / 75 relevés, +1/+1) ; la réserve maintenue sur l'absence de preuve SQL. | ✅ **posté ×1** — reste **ouvert** |
| **KAN-4** | Les trois jalons et leurs deltas ; le jalon **exactement stable à 3 348 Mo** et la bande **3 151–3 452 inchangée** (14ᵉ nuit), **pas un plancher** ; le coût par ligne rejouée à **1 713,1 o** (+2,5), **dans** la bande, et `balise_jours_rejeu` qui recule sans que le jalon suive ; ✅ **la CORRECTION explicite de ma note du 02/11** : le swap au pic **recule de 245,3 Mo** (le plus gros recul de la série) et les deux indicateurs vont enfin dans le même sens — **sans** être présenté comme une amélioration de fond, et avec la nuance que la journée était **beaucoup moins ventée** ; la réserve du 30/10 **recitée** pour « score par régime » sous le seuil ; **treizième** matin contradictoire de l'estimateur ; les **trois conditions** ⇒ **non réunies** ; le remède tuple à ≈ −2 012 Mo, **43ᵉ jour**, et le **refus** du calcul à taux constant. | ✅ **posté ×1** — reste **ouvert** |
| **KAN-3** | **Commenté** (canal délibéré) parce que la durée **augmente** de 99 s **et** parce que le critère `regime` est de nouveau rempli. ⛔ **Critère `bw-regime-sensibilite` REMPLI 2 / 2** : série complète, **question reposée, rien créé**, et la **mise en garde** que c'est mot pour mot la situation du 31/10, démolie en 24 h — avec mon avis (attendre une 3ᵉ nuit) clairement séparé de la décision de Yann. Le relevé ; la signature **92 % dans les étapes** et la conséquence que les jalons hors étapes **ne gagnent pas** en urgence ; la répartition par étape ; ⛔ **ce n'est PAS du volume** (lignes +343, temps +69,5 s, coût/ligne +0,46 ms), l'inverse exact du 02/11 ; le découplage **72 % de calcul** et le refus de conclure sur les 28 s restantes ; le niveau (**3ᵉ des dix**, +9 s sur le pic du 31/10) ; le solde **−154 s sur douze nuits**, qui **remonte** ; la marge **37,19 %**, la plus basse depuis le 07/10 ; le rappel du 25ᵉ centile ; la remontée du garde **décrite sans être demandée**. **Avis : NE PAS ROUVRIR.** ⛔ **Non rouvert, non transité.** | ✅ **posté ×1** — reste **Terminé** |
| `bw-regime-sensibilite` | ❓ **CRITÈRE REMPLI (2 / 2), question REPOSÉE, RIEN CRÉÉ** (§1). Mon avis : attendre une troisième nuit. **C'est à Yann de trancher.** | — |
| `bw-melange-sans-gain` | ⛔ **non créé** : **2 / 3** négatifs. ⚠️ **Une nuit de plus et le critère est rempli**, et l'excuse « journée atypique » ne joue pas ce matin (§9). | — |
| `bw-r2-palier` | ⛔ **non créé.** ⬆️ Urgence **maintenue** : sixième nuit au-dessus, encore le plus haut (§6). ❓ **Question reposée.** | — |
| `bw-character-57014` | ⛔ **non créé** ; la série reste interrompue, zéro partout (§3.2). Avis : ne pas le créer. | — |
| motif pour la purge | ⛔ **aucun motif neuf** : le motif existe, c'est **KAN-5**, et il est ouvert. | — |

ⓘ **Pourquoi `bw_jira_commenter` trois fois et `bw_jira_signaler` zéro fois** :
le contrôle s'est **tu** ce matin, donc le jeton du jour était **libre** — mais
`bw_jira_signaler` aurait **créé un ticket neuf** sur le motif « Terminé »
(KAN-3, puisque `bw_jira_chercher` filtre sur `statusCategory != Done`), et sur
les deux autres il n'apportait rien de plus. `bw_jira_commenter` prend une
**clé**, ne cherche rien, ne crée rien, ne touche pas au jeton du jour. Choix
assumé de l'arbitrage du 07/10. Signatures revérifiées dans `bw_jira.sh` avant
appel : `bw_jira_commenter()` **ligne 85**, `bw_jira_http()` **149**,
`bw_jira_chercher()` **176**, `bw_jira_signaler()` **195**.

## 11. ✅ Horaire de la routine — à l'heure

Programmée pour le **03/11 à 07:09:05 UTC**, tirée le **03/11 à 07:10:13 UTC** :
**+1 min 08 s**.

```
27/10 +10 h 09 · 28/10 +1 h 34 · 29/10 ⛔ +23 h 18 (matin SAUTÉ)
30/10 +0 h 00 · 31/10 +0 h 00 (47 s) · 01/11 ⚠️ +0 h 55 · 02/11 ⚠️ +0 h 19
03/11 ✅ +0 h 01
```

⇒ ✅ **Le retard se résorbe complètement** : 55 min, puis 19 min, puis **68 s**.
Le tir a bien eu lieu, et **une seule fois**. ⓘ Le VPS est à l'heure : notation à
04:55:06 CET, contrôle à 07:31:05 CET, timer suivant armé pour le **04/11 à
07:30:18 CET**.

## 12. Décisions en attente de Yann — la liste à jour

1. ❓ **PRIORITAIRE, et en retard de cinq jours : fermeture de KAN-5.** Le
   critère écrit est **REMPLI** (8 / 3, rempli dès le 29/10). **Veux-tu le
   fermer ?** Je ne ferme rien sans ta réponse. **Cinquième** fois que la
   question est posée.
2. ❓ **NOUVEAU / REVENU : le critère `bw-regime-sensibilite` est REMPLI (2 / 2)**
   — 10,92 → 11,13 → 11,58 ms (§1). **Veux-tu un motif Jira ?** ⚠️ Mon avis :
   **attendre une troisième nuit**, parce que la même configuration du 31/10 a
   été démolie en vingt-quatre heures. **Rien n'a été créé.**
3. ⬆️ **PRIORITAIRE : R2 facture, sixième nuit.** **10,433 Go (104,3 %)**, encore
   le plus haut, hausse qui **ralentit sans s'inverser** (§6). ❓ Motif Jira
   `bw-r2-palier`, ou action de rétention ?
4. ⛔ **Mémoire : la ligne en tuple** (≈ −1 030 o/ligne, ≈ −2 012 Mo). **43ᵉ jour
   sans rien de déployé** depuis `af25efb`. Seule porte de sortie de KAN-4 : le
   jalon est à **+548 Mo** du seuil. ⓘ Le swap recule de 245 Mo cette nuit, mais
   il reste **à plus de 2 Go**, et une nuit ne fait pas une pente.
5. ⚠️ **NOUVEAU, pressant : `bw-melange-sans-gain` à 2 / 3.** Deux points
   négatifs consécutifs (−0,8 puis −2,5 %), « devant » en baisse pour la 4ᵉ nuit,
   et **l'excuse « journée atypique » ne joue pas** (§9). ❓ **Si demain est
   négatif, le critère est rempli : veux-tu un motif ?**
6. ⬆️ **`position_l15_2026-11-02.sql`** à jouer : **4 suspensions** (1715, 2058,
   70, STATIC0491) — ⛔ **elles sont toujours confirmées ce matin**, précisément
   parce que le SQL n'a pas été joué. Les 3 renaissances, elles, **ont déjà
   fonctionné** (§7). ⚠️ **Et il faut y ajouter un cas neuf : `mf:05170001`**,
   confirmée ce matin à 330 m / 10 j.
7. ⬆️ **`installer-webhook-discord.sh`** (sur le Mac) — **53ᵉ jour**, **4ᵉ**
   occasion manquée consécutive (2 cris, 0 `push Discord`) (§9).
8. ⛔ **Les DEUX correctifs de lecture de la purge** (§3.4), inchangés :
   (a) `bilan_purge` et le suffixe « des lignes RESTENT » ; (b)
   `registre_nuit._INCIDENT` et la ligne de sonde. **Il faut les deux.**
9. ⛔ **Deux miroirs git en souffrance** : celui du **24/10** (jamais déposé) et
   celui du **26/10** (présent mais **non suivi par git**). ⚠️ **Plus celui du
   01/11** (Mac injoignable ce matin-là) ⇒ **trois** dettes. **Rien fabriqué
   après coup.**
10. ⛔ **R2 : rétention sur `agrume/pi`** — **+48 objets cette nuit, vingt-et-une
    nuits d'affilée, sans un seul recul** (§6.3).
11. ⛔ **Inventaire des 4 052 objets de `agrume/pi` que l'index ne réclame pas**
    (sur 4 099). À faire **avant** toute rétention.
12. ❓ **NOUVEAU : le recul de 270 balises observées tient une TROISIÈME nuit**
    (3 731 → 3 461 → 3 457 → 3 461) (§9). Ce n'est plus du bruit. ⇒ **Ça devient
    une question** : 270 balises ont-elles cessé d'émettre, ou la chaîne
    d'ingestion en perd-elle ?
13. ⬇️ **`diagnostic_base_sous_tension_2026-09-29.sql`** — **36ᵉ jour** sans être
    joué. Urgence **basse** : neuvième nuit d'affilée où la purge aboutit, huit
    sans le moindre avertissement, et `n_57014` est à **0 partout**.
14. ⬇️ **Le `select as_of, count(*)`** sur `model_score_zone` : seule façon de
    **prouver** que la plus vieille journée est partie. **Aucun SQL joué sans ton
    accord.**
15. ⛔ **Pente d'`audit_r2.py`** : borner à zéro les pentes négatives des préfixes
    à fenêtre glissante (§6.3) — elles sont maintenant **six**. Une ligne, mais
    c'est une **écriture**.
16. ⓘ **Réouverture de KAN-3** : **mon avis est NON** — 5 088 s avec 3 012 s de
    réserve, solde **−154 s** sur douze nuits, 3ᵉ point des dix. ⚠️ Mais la marge
    (37,19 %) est la plus basse depuis le 07/10 : à resurveiller.
17. ⬇️ **Jalons de temps dans le bloc hors étapes de `run.sh`** — ⬇️ **l'argument
    FAIBLIT ce matin** : 8 s sur 99 (§5.1). Maintenu à « utile sans urgence ».
18. ⓘ **Le cri de position doit-il recrier** à état constant ? (ouvert depuis le
    01/10) ⬇️ **Encore moins pressant** : le front est bien signalé dans les deux
    sens, et il **nomme les deltas** (§7).
19. ⓘ **`mutations_memoire`** : 3 mutations non vues (2, 5, 13), dette
    antérieure, inchangée.
20. ⓘ **`bw-model-oracle.service`** en `failed` — hors mission, non examiné.

✅ **Retirées / allégées** : les **8 écarts du recalcul** du 02/11 (retour dans la
bande à 6 — c'était bien du bruit, §9) ; le **suivi des 3 renaissances de
position** (elles ont fonctionné en une nuit, §7).

## 13. Ce que ce run a DÉMENTI, et ce qu'il a CONFIRMÉ, de la note du 02/11

| annoncé le 02/11 | relevé le 03/11 |
|---|---|
| ⛔ critère `regime` **CASSÉ**, compteur 1 / 2, question **retirée** | ⛔ **REVENU et REMPLI (2 / 2)** : 11,13 → **11,58** (+0,46). Question **reposée**, rien créé. ⚠️ Avec la mise en garde que le 31/10 avait le même score et fut démoli en 24 h |
| ✅ compteur KAN-5 à **7 / 3**, question posée 4ᵉ fois | ✅ **CONFIRMÉ et renforcé** : **8 / 3**, 3ᵉ nuit propre, 5ᵉ question. ⛔ **Toujours aucune réponse** (vérifié au GET) |
| ⬆️ R2 **10,402 Go (104,0 %)**, +151 Mo, 5ᵉ nuit, plus haut de la série | ⬆️ **CONFIRMÉ** : **10,433 Go (104,3 %)**, +31 Mo, **6ᵉ nuit**, encore le plus haut. ⓘ La hausse **ralentit** mais ne s'inverse pas |
| ⚠️ jalon **3 348 Mo**, trois reculs d'affilée, bande 3 151–3 452 « pas un plancher » | ⚠️ **3 348 Mo, delta 0** : le recul **s'arrête**. Bande **inchangée** (14ᵉ nuit). Validé une **7ᵉ** fois |
| ⚠️ « score par régime » **sous** le seuil (2 739), réserve du 30/10 recitée | ⚠️ **2 725 Mo**, 2ᵉ nuit sous le seuil. Réserve **maintenue** : deux nuits, ce n'est pas la tendance que le 30/10 avait démentie en une |
| ⚠️ coût par ligne rejouée **1 710,6 o**, bande 1 596–1 744 | ⚠️ **1 713,1 o** : +2,5 o, **dans** la bande, 14ᵉ nuit |
| ⛔ swap : pic **+124 Mo sur deux nuits**, « la condition de fermeture s'éloigne » | ✅ **DÉMENTI, dans le bon sens** : pic **−245,3 Mo** (2 092,2), pages **−230 836**. ⛔ Mais **toujours > 2 Go**, et la journée était bien moins ventée |
| ⚠️ durée **4 989 s**, hausse **partagée** (59 / 41 %) | ⚠️ **5 088 s (+99)**, hausse **92 % dans les étapes** — signature du 31/10 retrouvée. Solde **−154 s** sur douze nuits |
| ✅ `regime` : **c'est du VOLUME** (lignes +2 713, temps +59 s) | ⛔ **INVERSÉ** : lignes **+343**, temps **+69,5 s** ⇒ c'est le **travail par ligne**. C'est ce qui remplit le critère du §1 |
| ⚠️ témoins du mélange **−0,8 %**, **1 / 3**, « point non comparable » | ⛔ **AGGRAVÉ** : **−2,5 %**, **2 / 3**, « devant » 46,9 % (4ᵉ baisse). ⚠️ Et l'excuse « journée atypique » **ne joue pas** : l'erreur a **baissé** |
| ✅ `n_57014 = 0`, série `bw_character_avance` interrompue | ✅ **CONFIRMÉ et mieux** : **0 partout** sur 36 h (une première), accumulateurs **100 %** |
| ⛔ **7** confirmées de position, cri parti, 14ᵉ vérification « à front » | ✅ **5** confirmées, **15ᵉ** vérification. ✅ **1378 / 2171 / 175 rentrées dans l'ordre** ⇒ **la prédiction de la session position du 02/11 est VÉRIFIÉE en une nuit** |
| ⛔ 4 suspensions + 3 renaissances dans `position_l15_2026-11-02.sql`, à jouer | ✅ Les **3 renaissances** ont fonctionné **sans le SQL** (regel AGRUME). ⛔ Les **4 suspensions** sont **toujours confirmées** : le SQL manque toujours. ⚠️ **Plus un cas neuf : `mf:05170001`** |
| ⛔ `agrume/pi` **20ᵉ** nuit, 4 004 non réclamés | ⛔ **21ᵉ nuit**, **+48** ⇒ **4 052** non réclamés sur 4 099 |
| ✅ `agrume/grille` refermée à 766 / 766 | ✅ **TIENT** : **6ᵉ** nuit à 766 / 766 et 5,323 Go, au Mo près |
| ⚠️ estimateur de pente mémoire **−24 Mo/nuit** | ✅ **validé une 10ᵉ fois** : encore **−24** pendant que le jalon fait −26 puis **0** |
| ✅ webhook `--ipv4` confirmé une 3ᵉ fois (2 pushes) | ✅ **CONFIRMÉ une 4ᵉ fois** : 2 pushes de plus, HTTP 200, **zéro 429**, 2 mails partis |
| ⛔ `BW_DISCORD_WEBHOOK_URL` absente, **52ᵉ** jour | ⛔ **53ᵉ jour**, **4ᵉ** occasion manquée consécutive |
| ⚠️ écarts du recalcul **8**, « hors bande, très bruité, à revoir demain » | ✅ **6 — RETOUR DANS LA BANDE.** Ma réserve d'hier est **vérifiée** : c'était du bruit |
| ⚠️ témoin du corrigé **22,0 pt**, « ça oscille » | ⚠️ **23,0 pt** — ça oscille toujours, **rien à surveiller** |
| ⚠️ recul de **274 balises** observées, « stable sur deux nuits, à revoir demain » | ⚠️ **CONFIRMÉ, 3ᵉ nuit** : 3 461. ⇒ ❓ **Ça devient une question à part**, comme annoncé |
| ⚠️ horaire **+0 h 19**, « les retards se résorbent » | ✅ **CONFIRMÉ** : **+1 min 08 s**. Résorption **complète** |
| ⛔ trois miroirs git en souffrance (24/10, 26/10, 01/11) | ⛔ **inchangé**. **Rien fabriqué** |

⚠️ **« Une nuit ne fait pas une pente » — appliqué ce matin** à : l'arrêt du recul
du jalon mémoire (§4.1), la **deuxième** nuit sous le seuil du « score par
régime » (§4.2), le recul de 245 Mo du swap (§4.3), le +2,5 o du coût par ligne
rejouée (§2.1), le +99 s de la durée (§5.3), le ralentissement de R2 (§6) et le
`n_57014 = 0` partout (§3.2). **Aucun des sept n'est présenté comme une
tendance** — et la tentation du jour était la §4.3, parce qu'elle allait dans le
sens qui m'arrangeait.

⛔ **Et quatre fois, ce matin, la leçon ne s'applique PAS** :
1. Le **critère de fermeture de KAN-5** est une **règle écrite comptée sur trois
   nuits**. Il est rempli depuis **cinq jours**.
2. Le **critère `bw-regime-sensibilite`** est une **règle écrite comptée sur deux
   nuits**. Il est **rempli**. Je ne l'ignore pas sous prétexte de prudence : je
   le **signale**, avec mon avis et son précédent.
3. Le **dépassement du palier R2** est un **fait de facturation**, pas une pente.
4. Les **deux défauts de lecture de la purge** sont des **lectures de code**,
   vraies indépendamment du nombre de nuits.

ⓘ **La leçon neuve du jour** : un critère **symétrique** se juge symétriquement.
Le 02/11 j'ai annoncé le critère `regime` **cassé** et retiré la question ; ce
matin il est **rempli** et je la repose. ⇒ **Un critère qui se casse en une nuit
se remplit en une nuit** : c'est la même fragilité, et elle ne doit pas servir
d'argument seulement quand elle arrange la conclusion. Même chose pour le swap
(§4.3), où j'avais annoncé une tendance à la hausse hier et où je corrige
aujourd'hui, explicitement.

## 14. Respect des règles

✅ **VPS en LECTURE SEULE, pleine et entière.** Aucun `systemctl`
start/restart/daemon-reload, aucun `enable`, **aucun SQL joué**, aucun rsync,
rien écrit dans `~/balise-watch` ni dans `/etc`. **Aucune redirection vers
`/tmp` du VPS** : toutes les sorties sont allées dans des fichiers du **Mac**
(`/Users/yann/bw-run-03-11/`) et relues avec `read_file`. ⓘ Seules exceptions,
qui sont le fonctionnement normal du code de production : `bw_jira_http` écrit
sa réponse dans un `mktemp -d` du VPS, et le `controle_quotidien.py --verbeux`
relancé à la main ne fait que lire.
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
⛔ **Aucun motif créé**, et celui dont le critère est **rempli** (`regime`) est
**posé en question**, pas créé (§1).
✅ **Desktop Commander exclusivement** pour fichiers et shell.
✅ **Lire avant d'écrire** : `git log --since=midnight` dans les deux dépôts
(**aucun commit**) ; `project_read` du 03/11 (absent ⇒ création), du 02/11 et de
`session-position-l15-02-11` (lus en entier) ; `notes-projet/README.md` relu ;
**note en section horodatée**.
⛔ **Aucun `git push`.** Commit **local** depuis la racine du dépôt serveur.

## 15. ⓘ Outillage — les pièges connus, tous reconfirmés

1. ✅ **`SSH_AUTH_SOCK` manquant** (piège n°1) : confirmé une neuvième fois,
   correctif bon du premier coup.

   ```
   export SSH_AUTH_SOCK="$(launchctl getenv SSH_AUTH_SOCK)"
   ```

2. ✅ **Le lecteur de flux qui perd des lignes** (piège n°2) : contourné d'emblée.
   **Toute sortie dont une ligne compte est redirigée vers un fichier du Mac et
   relue avec `read_file`.**
3. ✅ **Les heredocs cités pour le texte français** : les trois corps sont écrits
   dans un script du Mac avec l'outil d'écriture de fichier, dans des heredocs
   `<<'XEOF'`, et le script est passé par `ssh … 'bash -s' < post.sh`. Rien
   d'écrit sur le VPS. Corps **sans accents** ; les accents restent dans la note.
4. ✅ **`bw_jira_http` prend QUATRE arguments** : `$1` méthode, `$2` chemin,
   `$3` corps JSON (**vide** pour un GET), `$4` fichier de sortie. Repris tel
   quel, aucun aller-retour perdu.
5. ⓘ **Piège neuf, évité de justesse** : dans `post.sh` j'avais d'abord écrit
   `"$C3_UNUSED$C4"` pour le corps de KAN-4. Bash aurait interprété
   `$C3_UNUSED` comme une variable vide — le résultat aurait été juste **par
   accident**. Corrigé en `"$C4"` **avant** l'envoi. ⇒ **Relire la ligne d'appel,
   pas seulement le corps.**
