# Verdict de pente du 31/10/2026 — ⛔ **Le critère `bw-regime-sensibilite` est REMPLI pour la première fois depuis son arbitrage (2 / 2) : deux hausses consécutives du coût par ligne, et ce n'est pas du volume.** ✅ **Purge propre pour la 5ᵉ nuit : KAN-5 à 5 / 3, et ta décision manque depuis trois jours.** ⛔ **Un cri de position est parti : les confirmées passent de 3 à 8.** ⚠️ **Et le « seul fait neuf favorable » d'hier côté mémoire est annulé en une nuit, exactement comme annoncé.**

Cinq faits, dans l'ordre d'importance.

**(1)** ⛔ **Le critère `regime` est rempli, et de la façon la plus franche
possible.** Le coût par ligne de `regime` fait **10,86 → 11,30 → 11,88 ms** :
**deux hausses consécutives**, ce qui est exactement le critère unique arbitré
le 07/10. Et ce n'est **pas** du volume : `lignes_regime` **baisse de 704**
pendant que l'étape prend **73,5 s de plus**. ❓ **La question t'est posée, rien
n'est créé.** ⚠️ À relativiser sur un point : 11,88 ms n'est **pas** un record
(12,59 ms le 22/10) — c'est la **deuxième hausse** qui remplit le critère, pas
le niveau.

**(2)** ✅ **La purge est propre pour la CINQUIÈME nuit d'affilée** : 145 123
lignes en 8 tranches, **aucune** tranche en échec, **aucun** défaut de sonde.
Compteur **5 / 3**. Le critère écrit de fermeture de KAN-5 est rempli **depuis
le 29/10**, soit trois jours, et la question t'est posée pour la **troisième**
fois. **Rien n'est fermé.**

**(3)** ⛔ **Un cri de position est parti cette nuit** : les balises confirmées
passent de **3 à 8**. Les **quatre** annoncées hier (70, 175, 1715, 2058) ont
bien atteint 10 j — l'annonce du 30/10 est **tenue au balise près** — et
`pioupiou:1378` a franchi le seuil avec elles. ⚠️ **Ce qui DÉMENT la note
d'hier sur un point précis** : elle écrivait que 1378 « ne se confirmera jamais
seule ». Elle s'est confirmée seule.

**(4)** ⚠️ **Mémoire : le seul mouvement favorable d'hier est annulé en une
nuit.** Le jalon « score par régime » repasse **au-dessus** du seuil
(2 633 → **2 832 Mo**, +199) et les `incidents` reviennent de **2 à 3**. La
note du 30/10 écrivait mot pour mot : « une journée un peu plus chargée le fera
repasser au-dessus ». ✅ **Vérifié en vingt-quatre heures.**

**(5)** ⛔ **La durée reprend 145 s (5 079 s), et la signature des cinq nuits
précédentes s'inverse** : pour la **première fois**, la hausse est
**entièrement dans les étapes instrumentées** (+148,9 s) et le bloc hors étapes
est **plat** (−3,9 s). ⚠️ Mais **ce n'est pas un maximum du mois** : 5 079 s est
le 5ᵉ point le plus haut des dix derniers, sous le 23/10 (5 300 s).

⛔ **R2 facture pour la troisième nuit** : 10,251 Go (102,5 % du palier),
−25 Mo seulement. ✅ **Et le correctif webhook `--ipv4` est confirmé une
deuxième fois** : **deux** cris, **deux** `push parti (HTTP 200)`, zéro 429.

## 08:15–08:40 (Paris, CET) — routine Balise Watch, run du jour

**Étape 0 : faite en entier, avant toute autre chose.**

- `git log --oneline --since=midnight` dans `balise-watch-server` **et** dans
  `surveillance balise` : **aucun commit aujourd'hui** dans les deux dépôts
  ⇒ **aucun autre run n'a tourné ce matin.** Dernier commit serveur :
  **`5aeaf78`** (le second run du 30/10), précédé de **`a003d19`** (le miroir
  du 30/10). **Rien depuis.**
- `project_read` de `claude/verdict-pente-31-10.md` : **absent** ⇒ cette note
  est une **création**, pas une fusion. `claude/verdict-pente-30-10.md` : lu en
  **entier** (les deux sections, celle de 07:30 et celle de 08:11).
- `notes-projet/README.md` relu : les quatre règles.
- ⛔ **État des miroirs git, vérifié et non arrangé** : `verdict-pente-24-10.md`
  **toujours absent** ; `verdict-pente-26-10.md` **toujours non suivi par git**.
  **Rien fabriqué.**
- ⓘ **Risque de collision aujourd'hui : faible.** Le tir est **à l'heure**
  (§11), donc il n'y a pas d'occurrence en retard qui traînerait derrière
  celle-ci. La note est tout de même en **section horodatée** (règle n°2).

## 1. Le relevé de la nuit

`lancement = timer` · `result = success` · `exec_status = 0` · `oom = 0`.
Self-test du scoring **VERT** (les cinq contrôles : (a) à 1,0 sur les deux
références, `mse_comb` 17,841 ; (b) permuté à 2,198 dans la fourchette, skill
contre persistance à −2,2604). Relevé **comparable** : le verdict porte.

Nuit du 30→31/10 : début **04:59:48**, fin **06:24:40** (CET).
Contrôle passé à **07:30:44** CET, suivant armé pour le **01/11 à 07:30:56 CET**.

| | 29/10 | 30/10 | 31/10 | Δ |
|---|---:|---:|---:|---:|
| `duree_s` | 4 921 | 4 934 | ⛔ **5 079** | **+145** |
| `cpu_s` | 3 868,7 | 3 900,2 | **4 068,4** | +168,2 |
| `marge_s` | 3 179 | 3 166 | 3 021 | −145 |
| marge / garde (8 100 s) | 39,25 % | 39,09 % | ⚠️ **37,30 %** | −1,79 pt |
| étapes (somme) | 2 802,6 | 2 901,6 | **3 050,5** | **+148,9** |
| hors étapes | 2 118,4 | 2 032,4 | ✅ **2 028,5** | **−3,9** |
| `jalon_max_mo` | 3 424 | 3 400 | 3 397 | −3 |
| `mem_peak_mo` | 3 623,8 | 3 603,9 | 3 612,7 | +8,8 |
| `swap_peak_mo` | 2 431,8 | 2 149,3 | 2 213,5 | +64,2 |
| `swap_out_pages` | 2 212 450 | 2 484 258 | 2 172 144 | −312 114 |
| `n_57014` | 1* | 1* | 1* | 0 |
| `incidents` | 2 | 2 | ⚠️ **3** | **+1** |
| `lignes_regime` | 138 828 | 140 703 | **139 999** | **−704** |
| `lignes_score_zone` | 149 486 | 151 401 | 150 712 | −689 |
| `lignes_daily` | 68 287 | 68 430 | 68 572 | +142 |
| `lignes_glissant` | 10 658 | 10 698 | 10 713 | +15 |
| `balise_jours_rejeu` | 2 058 366 | 2 062 126 | 2 060 898 | −1 228 |

(*) `n_57014 = 1`, mais **hors bloc purge** — voir §2.2.

Les `incidents` sont **tous** de mémoire, et il y en a de nouveau **trois** :
rejeu d'archive (2 995 Mo), **score par régime (2 832 Mo — revenu
au-dessus)**, oubli de la fenêtre rejouée (3 397 Mo). ✅ **Aucun avertissement
de purge, pour la cinquième nuit d'affilée.**

Répartition par étape :

| étape | 29/10 | 30/10 | 31/10 | Δ |
|---|---:|---:|---:|---:|
| `regime` | 1 508,1 | 1 589,8 | **1 663,3** | **+73,5** |
| `glissant` | 933,9 | 935,4 | **985,6** | **+50,2** |
| `stabilite` | 287,2 | 295,6 | **321,4** | **+25,8** |
| `rejeu` | 73,4 | 80,8 | 80,2 | −0,6 |

⇒ ⚠️ **Hausse RÉPARTIE, pas une étape qui déraille.** `regime` fait la moitié
du mouvement, mais `glissant` et `stabilite` prennent **76 s à elles deux**.
C'est différent des nuits précédentes, où `regime` faisait « presque tout » le
mouvement dans les deux sens.

### Les deux rapports qui valent mieux que les valeurs brutes

**Coût par ligne rejouée** (`jalon_max_mo × 1048576 / balise_jours_rejeu`) :

```
19/10 1 702,0 o · 20/10 1 608,0 o · 21/10 1 726,1 o · 22/10 1 722,2 o
23/10 1 621,3 o · 24/10 1 723,8 o · 25/10 1 743,9 o · 26/10 1 595,7 o
27/10 1 726,9 o · 28/10 1 740,7 o · 29/10 1 744,3 o · 30/10 1 728,9 o
31/10 1 728,4 o
```

⇒ ⚠️ **1 728,4 o, soit 0,5 o sous la veille : INDISCERNABLE.** La bande
**1 596 à 1 744 o** tient une **onzième** nuit, et sur treize nuits il n'y a
**aucune pente**.
ⓘ Et ce n'est pas un artefact de fenêtre : `balise_jours_rejeu` **recule** de
1 228 pendant que le jalon recule de 3 Mo — les deux vont dans le même sens, de
façon négligeable.

**Coût par ligne de `regime`** (`etapes_s.regime / lignes_regime × 1000`) :

```
21/10 12,14 ms · 22/10 12,59 ms · 23/10 11,97 ms · 24/10 11,42 ms
25/10 12,19 ms · 26/10 11,44 ms · 27/10 11,21 ms · 28/10 11,71 ms
29/10 10,86 ms · 30/10 11,30 ms · 31/10 ⛔ 11,88 ms
```

⇒ ⛔ **DEUXIÈME HAUSSE CONSÉCUTIVE : le critère `bw-regime-sensibilite` est
REMPLI (2 / 2).** 10,86 → 11,30 (+0,44) → 11,88 (+0,58). C'est la **première
fois** depuis l'arbitrage du 07/10 que ce critère unique — « la hausse
s'additionne deux nuits de suite » — est satisfait. Voir §10 pour la question
posée.
⇒ ⛔ **Et il est rempli de la façon la plus nette possible** : `lignes_regime`
**baisse de 704** pendant que l'étape prend **73,5 s de plus**. Le travail par
ligne augmente **réellement** ; ce n'est pas un effet de volume.
⇒ ⚠️ **Nuance que je pose moi-même** : **11,88 ms n'est pas un record.** La
série est montée à **12,59 ms** (22/10) et **12,19** (25/10). Le niveau actuel
est **dans la bande** ; c'est la deuxième hausse qui remplit le critère, pas le
niveau. Je le dis pour que la question posée à Yann ne soit pas lue comme une
alerte de niveau.

**Calcul ou attente ?** ⛔ **Du calcul, nettement.** La durée prend **145 s** et
`cpu_s` en prend **168,2**. Le CPU monte **plus** que l'horloge : la machine n'a
pas attendu, elle a travaillé.

## 2. ✅ LA PURGE : cinquième nuit propre — compteur KAN-5 à 5 / 3

Le bloc purge, en entier :

```
2026-10-31 06:24:25  → purge model_score_zone : 145123 ligne(s) effacée(s) en 8 tranche(s)
2026-10-31 06:24:25  ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée
```

Deux lignes, et c'est tout. Lecture selon les règles du 28/09 complétées le
07/10 :

| test | 31/10 |
|---|---|
| tranche en échec | ✅ **✘ aucune** |
| bilan chiffré | ✅ **✔ 145 123 / 8 tr.** |
| « des lignes RESTENT » | ✅ **✘ absent** |
| sonde en défaut | ✅ **✘ aucun** |

⇒ ✅ **NUIT PROPRE PLEINE**, sonde comprise. Aucune ligne
`?as_of=eq.J&regime=eq.R : HTTP 500`, aucune ligne « plus vieille journée
illisible ».

### 2.1 ✅ Compteur de fermeture KAN-5 : 5 / 3 — et la décision a trois jours de retard

```
27/10  propre  → 1 / 3
28/10  propre  → 2 / 3
29/10  propre  → 3 / 3   ⇐ CRITÈRE REMPLI
30/10  propre  → 4 / 3
31/10  propre  → 5 / 3
```

⇒ ❓ **Le critère écrit est rempli depuis le 29/10, soit trois jours.** La
question a été posée le 28/10 (« possible dès demain »), le 30/10, et elle est
posée ce matin pour la **troisième** fois. ⛔ **Rien n'est fermé, rien n'est
transité.**
ⓘ **Vérifié par une troisième voie** : le GET des trois tickets montre
qu'**aucune réponse n'a été enregistrée** sur KAN-5 depuis le 28/10 — les deux
derniers commentaires sont ceux de la routine (28/10 et 30/10).
ⓘ La sous-question du 26/10 — la sonde doit-elle compter ? — **ne se pose pas**
cette nuit non plus, puisqu'il n'y a aucun défaut de sonde. Elle reste ouverte
pour le jour où le cas se représentera.

### 2.2 ⚠️ `n_57014 = 1`, et pour la TROISIÈME nuit de suite — toujours hors purge

Recherche élargie sur **toutes** les unités, 36 h : `grep -c 57014` = **1**, et
la ligne unique est :

```
⚠️ rpc/bw_character_avance : HTTP 500 {"code":"57014", …
   "canceling statement due to statement timeout"} — reprise 1/3
```

C'est l'**avance des accumulateurs**, pas la purge. Et la reprise a abouti
**pleinement** : « model_character : **362 862** accumulateurs avancés sur
362 862 envoyés ». **Zéro perte.**
ⓘ **Historique de cette ligne précise** : **22/10, 23/10, 29/10, 30/10,
31/10**. ⚠️ **Fait neuf, petit** : c'est la **première fois qu'il tombe TROIS
nuits de suite** (le 30/10 notait la première série de deux). **À surveiller,
rien de plus** — et surtout **pas** un motif neuf. Mon avis reste : **ne pas
créer `bw-character-57014`**, le motif est antérieur et se rattrape seul à
100 %.

Série `n_57014` au registre sur dix-neuf nuits :

```
13/10 0 · 14/10 1 · 15/10 0 · 16/10 1 · 17/10 0 · 18/10 0 · 19/10 0 · 20/10 0
21/10 0 · 22/10 1 · 23/10 4 · 24/10 0 · 25/10 3 · 26/10 1 · 27/10 0 · 28/10 0
29/10 1* · 30/10 1* · 31/10 1*          (* hors purge)
```

### 2.3 Le volume : fourchette normale, et toujours pas un signal

```
28/10   142 819 lignes en 8 tranches
29/10   143 625 lignes en 8 tranches
30/10   147 216 lignes en 8 tranches
31/10   145 123 lignes en 8 tranches
```

⇒ Quatre nuits de suite à **8 tranches** et dans la fourchette habituelle
(125 000 à 147 000). **Le volume effacé suit le volume de la journée purgée :
il monte et descend sans rien signifier**, et il n'est lu comme un signal **ni
à la hausse ni à la baisse**.
⛔ **Et il n'y a toujours AUCUNE preuve** que la plus vieille journée soit
partie de la base. Seul un `select as_of, count(*) from model_score_zone group
by as_of order by as_of limit 5` le dirait, et **aucun SQL n'a été joué.**

### 2.4 ⛔ Les deux défauts de code restent entiers, et cette nuit ne les teste pas

1. **(a)** `bilan_purge` ignore le suffixe « des lignes RESTENT » — faux négatif
   démontré le 25/10.
2. **(b)** `registre_nuit._INCIDENT` ne reconnaît pas la ligne de sonde, donc la
   branche `sonde_ko` de `controle_quotidien.constats()` est du **code mort** —
   démontré le 26/10.

⛔ **Aucun des deux n'est déployé, et il faut les DEUX.** Cette nuit n'avait
**ni** ligne restante **ni** sonde en défaut : elle ne pouvait **ni** les
confirmer **ni** les réfuter — **sixième** nuit de suite dans ce cas. Ce sont
des **écritures dans le code** : Yann tranche.
ⓘ Et ce n'est toujours pas une raison de retirer le correctif du 07/10 : sans
lui, KAN-5 recevrait « purge en échec » toutes les nuits où une tranche est
rejouée puis rattrapée, ce qui est le cas normal.

### 2.5 Le contrôle de pente s'est tu ce matin, et par la bonne porte

```
2026-10-31T06:30:44Z rien à dire : pente plate ou négative, ou échéance hors horizon
```

Verbeux, relancé à la main en lecture seule :

```
ⓘ 93 relevé(s), 72 comparable(s) ; durée : 10 points, pente -119 s/nuit ;
  mémoire : 10 points, pente -24 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate/négative, ou échéance hors horizon
```

✅ Le silence est **juste** et **par la bonne porte** : `incidents` ne porte
aucun avertissement de purge **parce qu'il n'y en a eu aucun** — et non, comme
le 26/10, parce que le motif du registre ne sait pas lire la ligne de sonde. Le
défaut (b) n'a, là encore, pas eu l'occasion de nuire.
ⓘ **93 relevés / 72 comparables** contre 92 / 71 hier : **+1 et +1**, cohérent
avec exactement une nuit de plus.
⚠️ **Une seule ligne au journal du contrôle aujourd'hui** ⇒ pas de second tir,
pas de second jeton, et le jeton du jour était **libre** quand la routine a
écrit (§10).

## 3. ⛔ R2 : le palier reste dépassé, troisième nuit

### 3.1 Le compte

```
                      29/10             30/10             31/10            Δ
total compte     10,291 Go 102,9 %  10,276 Go 102,8 %  10,251 Go 102,5 %  −25 Mo
objets             7 225             7 281             7 343             +62
pente mesurée    +0,023 Go/mois     +0,028 Go/mois     +0,008 Go/mois
palier atteint      0 j               0 j               0 j
```

⇒ ⛔ **Troisième nuit au-dessus du palier gratuit**, et le journal le dit sans
détour : `⚠️ palier gratuit DÉPASSÉ : 10.25 Go sur 10 Go — R2 facture déjà`.
⚠️ **Le recul est de 25 Mo seulement** : rien n'indique un retour sous la barre.
ⓘ Le seuil d'alerte (12 Go) et le seuil d'arrêt de chaîne (6 Go) ne sont pas
en cause ; couverture **complète** (tous les buckets du compte).

Par bucket : `balise-watch-grids` **9,318 Go / 6 104 obj** (−33 Mo, +48 obj) ·
`model-verif` **0,929 Go / 1 026 obj** (+9 Mo, +14 obj) ·
`balise-watch-packs` 0,005 Go / 213.

Par préfixe :

```
                      29/10              30/10              31/10
agrume/grille    5,323 Go  766 obj   5,323 Go  766 obj   5,323 Go  766 obj
agrume/pi        1,710 Go 3 861 obj  1,730 Go 3 909 obj  1,751 Go 3 957 obj
arome/rafale     0,826 Go             0,823 Go            0,797 Go
agrume/colonnes  0,556 Go  102 obj    0,520 Go   96 obj   0,517 Go   96 obj
arome/sol        0,566 Go             0,560 Go            0,540 Go
```

### 3.2 ✅ `agrume/grille` : la question du 27/10 est REFERMÉE

```
│ agrume/grille/                          766 présentes /  766 réclamées   ✓ tout est réclamé
```

Troisième nuit consécutive à **766 / 766 et 5,323 Go**, à l'objet et au Mo près,
et toujours **aucune** ligne « suppression(s) ratée(s) ».

```
27/10   610 / 610                        ← le retrait de 1 125 Mo
28/10   680 / 652   + « 28 suppression(s) ratée(s) »   ← inédit
29/10   766 / 766   ← revenu au nominal, ligne DISPARUE
30/10   766 / 766 · 31/10  766 / 766     ← stable
```

⇒ ✅ **Je referme cette question.** Le 30/10 la disait « pratiquement
refermée » ; une troisième nuit identique au Mo près ne laisse plus de place au
doute raisonnable : c'était la **fenêtre glissante**, pas un geste humain, et
les 28 suppressions ratées étaient bien la **reprise annoncée au prochain run**.
⚠️ Je ne dis pas « prouvée au sens du code » — je n'ai ni le code de rétention
sous les yeux ni un journal de suppression nominatif. Mais la question
« est-ce toi ? » **n'a plus besoin de réponse**, et elle quitte la liste du §12.

### 3.3 ⛔ `bw-garde-fou-r2` : code 1, 3 consécutifs — et c'est son comportement normal

```
2026-10-31T05:24:47Z run garde-fou-r2 en ÉCHEC (code 1, 6s) — 3 consécutif(s)
Result=exit-code · NRestarts=0 · ExecMainStatus=1 · ActiveState=failed
```

⇒ ✅ **Ce n'est PAS une panne.** La démonstration du 21/10 tient : **code 1 =
« j'ai quelque chose à dire »**. Le palier est dépassé, donc il parle. **Le
garde-fou fait son travail**, et son cri est parti (§8).

### 3.4 ⛔ `agrume/pi` : dix-huitième nuit à +48 objets, sans un seul recul

```
│ agrume/pi/grille/                        19 présentes /   19 réclamées   ✓
│ agrume/pi/rafraichissement/              28 présentes /   28 réclamées   ✓
```

47 objets couverts sur **3 957** ⇒ **3 910 objets que nul index ne réclame**
(3 862 hier, 3 814 le 29/10). **+48 par nuit, exactement le rythme
d'accumulation, pour la DIX-HUITIÈME nuit consécutive.**
ⓘ Ce n'est pas la preuve qu'ils sont orphelins ; c'est la constatation qu'on
n'en sait rien. **L'inventaire reste le geste à faire avant toute rétention.**
⚠️ Et **la leçon du 24/10 (§7.1) s'applique une ONZIÈME fois** : le total du
compte rend 25 Mo pendant que l'accumulation prend ses +48 habituels. **Le
total du compte n'est pas un indicateur de l'accumulation.**

Pente affichée de `agrume/pi` : **+0,581 Go/mois**, **inchangée** pour la
troisième nuit.
⛔ Le point sur **`audit_r2.py`** (borner à zéro les pentes négatives des
préfixes à fenêtre glissante) reste **entier**, et il est **plus visible que
jamais** : `arome/rafale` **−0,389**, `arome/sol` **−0,295**, `arome/alt`
−0,092, `arome/lod` −0,047 Go/mois tirent la pente du total à **+0,008 Go/mois**
pendant que `agrume/pi` monte à +0,581. ⓘ Conséquence : « palier atteint dans
**0 j** », juste par accident (le palier EST dépassé) et non par la pente.
**Une écriture, non faite.**

ⓘ `agrume/colonnes` reste à **96 objets** après son recul d'hier : −3 Mo, rien
conclu.

## 4. ⚠️ Mémoire — le mouvement favorable d'hier est annulé en vingt-quatre heures

```
                        29/10   30/10   31/10     Δ     vs seuil 2800
rejeu d'archive         2 995   2 982   2 995    +13    ⛔ +195
score par régime        2 665   2 633   2 832   +199    ⛔ +32  (REVENU AU-DESSUS)
oubli fenêtre rejouée   3 424   3 400   3 397     −3    ⛔ +597
```

### 4.1 ⚠️ La confirmation de prudence du matin

Le 30/10, le « seul fait neuf, et petit » était que le jalon « score par
régime » venait de repasser **sous** le seuil, faisant tomber `incidents` de
3 à 2. La note l'avait assorti d'une réserve explicite :

> « il n'était qu'à **+8 Mo** au-dessus du seuil le 28/10 ; il a franchi une
> ligne sur laquelle il était **assis** ; ce n'est pas un gain de structure,
> rien n'a été déployé qui puisse l'expliquer, et **une journée un peu plus
> chargée le fera repasser au-dessus**. Ce n'est pas un début de pente. »

⇒ ✅ **Vérifié en une nuit** : **2 832 Mo**, +199, de nouveau **au-dessus** du
seuil, `incidents` revient à **3**. **La réserve était la bonne lecture**, et il
n'y a eu **aucune** amélioration de fond. C'est la **cinquième** fois de suite
que la prudence de la note de la veille est validée sur ce ticket.

### 4.2 ⛔ Le jalon qui décide : bande inchangée, record non battu, onzième nuit

```
19/10 3 381 · 20/10 3 193 · 21/10 3 424 · 22/10 3 412 · 23/10 3 210
24/10 3 411 · 25/10 3 452 · 26/10 3 151 · 27/10 3 399 · 28/10 3 420
29/10 3 424 · 30/10 3 400 · 31/10 3 397
```

⇒ ⚠️ **La bande va de 3 151 à 3 452 Mo, INCHANGÉE pour la onzième nuit.** Le
record du 25/10 n'est **pas** battu : il reste **55 Mo** au-dessus de cette
nuit. Sur treize nuits il y a autant de montées que de descentes et **aucune
pente nette**.
⚠️ C'est la **quatorzième** fois en vingt-deux jours que « une nuit ne fait pas
une pente » s'applique ici.

### 4.3 ⚠️ La divergence du swap s'INVERSE — et c'est la leçon à en tirer

✅ `mem_peak_mo` remonte de 8,8 Mo (3 612,7) : le pic du processus reste dans sa
bande.
⚠️ **Le 30/10** : le **pic** de swap baissait de 282,5 Mo pendant que les
**pages sorties** montaient de 271 808.
⚠️ **Le 31/10** : **l'inverse exact** — le pic remonte de 64,2 Mo (2 213,5)
pendant que les pages sortent **312 114 de moins** (2 172 144).
⇒ ⛔ **Je ne conclus rien de cette divergence, dans un sens comme dans
l'autre.** Deux nuits de suite, les deux indicateurs de swap bougent en sens
**opposés** l'un de l'autre. C'est une raison de **ne lire aucun des deux
seul** — ni le recul du pic d'hier comme une amélioration, ni son retour
aujourd'hui comme une dégradation.

### 4.4 L'estimateur de pente, onzième matin contradictoire

| matin | pente affichée | la nuit correspondante |
|---|---:|---|
| 26/10 | −188 Mo/nuit | chute de −301 Mo |
| 27/10 | −188 Mo/nuit | hausse de +248 Mo |
| 28/10 | −188 Mo/nuit | hausse de +21 Mo |
| 30/10 | −24 Mo/nuit | +4 puis −24 Mo |
| 31/10 | **−24 Mo/nuit** | −3 Mo |

⇒ C'est le **25ᵉ centile des différences**, qui ignore par construction les deux
plus grosses variations. Conclusion posée le 23/10, **confirmée une huitième
fois** : **cet estimateur n'est pas utilisable en prévision** sur cette série.
ⓘ L'échéance étant hors horizon (30 j), le contrôle se tait — et sur ce point
précis **il a raison**.

### 4.5 Les trois conditions de fermeture de KAN-4

| condition | état |
|---|---|
| le contrôle se tait sur `bw-pente-memoire` | ✅ **remplie** (3ᵉ matin) |
| le jalon est mesurément retombé | ⛔ **non** — 3 397 Mo, **+597** au-dessus |
| le swap au pic ≈ 0 | ⛔ **non** — 2 213,5 Mo |

⇒ ⛔ **NON RÉUNIES. KAN-4 reste ouvert.** Et le seul mouvement favorable
annoncé hier est **annulé** ce matin (§4.1).

### 4.6 Le remède, inchangé — et toujours le seul à la bonne échelle

La **ligne en tuple** (§2.6 de l'enquête du 10/09) : ≈ **−1 030 o/ligne**, soit
≈ **−2 023 Mo** sur les 2 060 898 balise-jours rejoués cette nuit — à comparer
aux **597 Mo** qui séparent le jalon du seuil. ⛔ **Rien de déployé côté mémoire
depuis `af25efb` (21/09) — 40ᵉ jour.** ⚠️ L'élagage de `units` avait rendu
−124 Mo au lieu de −1 500 : les gains sont dans la **structure**. La mesure
`tuple` contre `namedtuple` à la sonde reste le préalable.
ⓘ Un calcul à taux constant donnerait « seuil atteint en N nuits » ; je le
**refuse**, parce que la série n'a pas de pente.

## 5. ⛔ Durée — +145 s, et la signature des cinq nuits précédentes s'inverse

```
            étapes     hors étapes   total
28/10      2 957,6       1 969,4     4 927
29/10      2 802,6       2 118,4     4 921
30/10      2 901,6       2 032,4     4 934
31/10      3 050,5       2 028,5     5 079
```

### 5.1 ✅ LE FAIT NEUF : pour la première fois, tout est DANS les étapes

⇒ ⛔ Les étapes prennent **+148,9 s** pendant que le bloc hors étapes ne bouge
que de **−3,9 s**. **La hausse est entièrement dans le bloc instrumenté.**
⇒ ✅ **C'est l'inverse exact des cinq nuits précédentes**, où le bloc **non**
instrumenté faisait l'essentiel du mouvement et produisait cinq écarts
inexplicables de suite (le 29/10 encore : −155 s dans les étapes, +149 s hors
étapes). Cette nuit, **tout se lit dans le journal.**
⬇️ **Conséquence sur la demande de jalons de temps dans `run.sh`** : elle reste
« utile sans urgence », et ce matin elle **n'aurait rien apporté**. C'est le
premier matin depuis le 26/10 où l'argument **ne se renforce pas**.

### 5.2 ⚠️ Le niveau : à remettre dans la série du mois, et ce n'est PAS un maximum

```
22/10 5 242 · 23/10 5 300 · 24/10 5 064 · 25/10 5 252 · 26/10 5 133
27/10 4 728 · 28/10 4 927 · 29/10 4 921 · 30/10 4 934 · 31/10 5 079 s
```

⇒ ⚠️ **5 079 s est le CINQUIÈME point le plus haut des dix** : il reste sous le
23/10 (5 300), le 25/10 (5 252), le 22/10 (5 242) et le 26/10 (5 133). Cette
nuit **ne fait pas un maximum** — elle **ramène** la durée dans la bande du
22 au 26/10 après quatre nuits basses.
⚠️ **Solde des deltas depuis le 23/10** : +58, −236, +188, −119, −405, +199, −6,
+13, **+145** ⇒ **−163 s sur neuf nuits.** Le solde reste **négatif**.
⚠️ **Marge : 37,30 % du garde**, la plus basse **depuis le 23/10** (34,57 %,
plancher de la série). Avec **3 021 s** de réserve sur 8 100, **aucune urgence
mécanique**.

### 5.3 Le garde

⛔ **Remontée du chien de garde : NON LANCÉE et NON DEMANDÉE.**
`controle_quotidien.proposition()` ne se déclenche pas (pente négative, échéance
hors horizon). La forme reste connue et je la **décris** sans la demander :
écrire la mesure dans l'en-tête de `10-timeout-s3.conf` (135 → 140/145 min),
déployer, vérifier. **C'est Yann qui décide et qui lance.**

ⓘ Rappel, qui vaut pour KAN-3 : la pente du contrôle est le **25ᵉ centile des
différences**. Elle n'a vu ni le +153 s du 01/10, ni le +336 s du 06/10, ni le
+70 s du 07/10, ni le +188 s du 25/10, ni le +199 s du 28/10, et elle ne verra
pas le **+145 s** de cette nuit : ce matin elle affiche encore **−119 s/nuit**,
exactement comme hier.

## 6. ⚠️ Témoins du mélange — cinquième point positif de suite

```
31/10 : sur 7 462 balise-jours×échéance, le mélange fait 2,998 km/h contre
        3,100 pour le meilleur membre a priori (gain +3,3 %, devant 52,4 %) ;
        contre la moyenne UNIFORME, sur 1 101 : 3,082 vs 3,179 (gain +3,1 %)
```

Série du gain contre le **meilleur membre a priori** :

```
−0,6 % (07/10) · +2,5 · +1,7 · −0,3 · +0,9 · −0,9 · +0,1 · +0,8
· −4,0 % (25/10) · −2,2 · +5,2 · +2,3 · +0,5 · +3,0 · +3,3 % (31/10)
```

⇒ ⚠️ **Cinq points positifs de suite**, et « devant » tient **au-dessus de la
barre** à **52,4 %** (52,2 % hier).
⇒ ✅ **La question du motif `bw-melange-sans-gain` reste refermée** : il
faudrait trois points **négatifs** consécutifs, et on en est à **cinq
positifs**. **Mon avis est inchangé : ne pas créer le motif.**
ⓘ L'erreur absolue passe de 3,0745 à **2,998** : journée encore un peu plus
calme, gain qui monte un peu. Les deux vont dans le **même** sens pour la
deuxième nuit — ce qui ne ressuscite pas l'explication par le niveau de vent
(abandonnée le 27/10), mais ne la contredit pas cette nuit-là non plus. ⚠️ **Je
n'en tire rien : deux nuits concordantes après trois nuits discordantes, c'est
du bruit.**

## 7. ⛔ Position — LE CRI EST PARTI : les confirmées passent de 3 à 8

```
⛔ position : 18 balise(s) divergent du gel (10 j lus), dont 8 CONFIRMÉE(S) (≥ 10 j)
   ⛔ pioupiou:1378          340 941 m · 10 j · nœud + profil CHANGENT · Col de la Merquiere
   ⛔ pioupiou:2171           38 915 m · 10 j · nœud + profil CHANGENT · Windbird 2171
   ⛔ pioupiou:84              9 744 m · 10 j · nœud + profil CHANGENT · PP84 JokAir
   ⛔ infoclimat:STATIC0491    1 159 m · 10 j · nœud 0,01 CHANGE
   ⛔ pioupiou:70                551 m · 10 j · nœud 0,01 CHANGE · Déco Salève
   ⛔ pioupiou:175               483 m · 10 j · nœud 0,01 CHANGE · Col de la Core
   ⛔ pioupiou:1715              429 m · 10 j · nœud + profil CHANGENT · Windbird 1715
   ⛔ pioupiou:2058              242 m · 10 j · nœud 0,01 CHANGE · Ernio
⛔ position : 8 balise(s) CONFIRMÉE(S) — cri déposé pour envoi
```

⇒ ⛔ **L'état a changé, donc le cri est parti.** C'est la **douzième**
vérification du mécanisme « à front, pas à état » — et la **première depuis le
07/10 dans le sens POSITIF** : onze nuits d'état constant sans un cri, puis un
front, et il crie. ✅ **Le mécanisme est établi dans les deux sens.**
ⓘ La question du 01/10 reste ouverte — **faut-il qu'il recrie à état
constant ?** Elle est désormais moins pressante, puisqu'on vient de vérifier
qu'un vrai changement est bien signalé.

### 7.1 ✅ L'annonce du 30/10 est TENUE — et démentie sur un point

La note du 30/10 corrigeait celle du 28/10 : **quatre** balises (70, 175, 1715,
2058), et non onze, atteindraient 10 j le 31/10.

⇒ ✅ **Tenue au balise près** : les **quatre** y sont, nommément, et les sept
qui avaient quitté la liste n'y sont pas revenues. **La correction du 30/10
était juste**, et c'est la première fois qu'une échéance de ce type est
annoncée puis vérifiée exactement.
⇒ ⛔ **Mais la note du 30/10 est DÉMENTIE sur `pioupiou:1378`.** Elle écrivait :
« elle re-clignote, donc **le compteur de jours ne la confirmera jamais
seule** ». ⚠️ **Il l'a confirmée seule** : 1378 est passée de 9 j (bloquée
depuis huit jours) à **10 j**, écart inchangé à **340 941 m**, et elle est dans
le cri. ⇒ **Cinq nouvelles confirmées, pas quatre.**
ⓘ **La leçon se retourne donc proprement** : le 30/10 disait « un compteur de
jours qui monte n'est pas une échéance » — c'est vrai, mais la réciproque
« un compteur qui re-clignote ne franchira jamais » est **fausse aussi**. Les
deux sont des prédictions sur un compteur bruité, et **aucune des deux ne
devait être posée**. Je ne reprendrai plus ni l'une ni l'autre.

⚠️ **`pioupiou:1378` est maintenant confirmée, et c'est le cas le plus net de
la liste** : **341 km** n'est pas un décalage de coordonnées plausible.
**Candidate « AUTRE balise », à trancher à la main.**
ⓘ `pioupiou:367` (6 764 m) reste à **9 j**, sixième jour hors des confirmées.
ⓘ `mf:05170001` passe de 6 à **7 j** (330 m) : rien à en conclure.
ⓘ Les **huit balises** apparues à 1 j le 29/10 (1344, 1770, 1588, 2190, 1618,
1640, 309, 2156) sont à **3 j** : renouvellement habituel de la queue de liste.

## 8. Les trois correctifs du 07/10 — verdict correctif par correctif

| correctif | verdict du 31/10 |
|---|---|
| **1. webhook `--ipv4`** | ✅ **CONFIRMÉ une DEUXIÈME fois, et sur deux cris distincts.** Il y avait deux choses à envoyer (le cri de position **et** le palier R2) et les deux sont parties : `ⓘ push parti (webhook, HTTP 200)` à **05:24:37Z** et **05:24:47Z**. ✅ **Aucun HTTP 429 ntfy** : `grep -i ntfy \| grep -c 429` = **0**. ✅ Les deux mails sont partis (`msmtp … smtpstatus=250 … exitcode=EX_OK`, 1 317 et 2 806 octets). ⇒ Deux nuits de suite avec quelque chose à dire, et quatre pushes partis au total : le correctif **tient**. |
| **2. garde-fou des deux jetons** | ✅ **tient** mécaniquement : le contrôle de 07:30:44 s'est **tu**, **une seule ligne** au journal, aucun jeton posé, aucun doublon possible — et les trois commentaires de ce matin sont passés par le canal **délibéré**, qui ne touche pas au jeton. `controle_quotidien.sh` conserve son `$ETAT` — **non touché**. |
| **3. rejeu de purge ≠ échec** | ⓘ **non sollicité**, sixième nuit : purge propre, aucun avertissement, rien à lire. Les deux défauts du §2.4 restent **entiers**. |

## 9. Les autres témoins

- ⚠️ **Témoin du corrigé** : **15,7 pt** (sur 9 061 balise-jours — vrai
  antécédent +11,5 %, autre balise −4,2 %). Série de la part site : 18,0 → 16,6
  → 23,3 → 20,4 → 27,8 → 27,6 → 27,1 → 17,9 → 17,0 → 19,8 → 15,0 → **15,7 pt**.
  Version FIN, part secteur+heure : 12,6 → 12,2 → 13,3 → 13,4 → 11,4 → 10,9 →
  11,8 → 9,1 → **9,6 pt** (3 761 balise-jours). ⓘ **Ça oscille**, comme conclu
  les 22 au 30/10. **Rien à surveiller.**
- ⚠️ **Écarts du recalcul indépendant : 6.** Série : 5 · 4 · 7 · 4 · 7 · 5 · 4 ·
  4 · 4 · 4 · **6** ⇒ la bande va de **3 à 7** ; **6 est dedans**, rien à en
  tirer sur le nombre. Signature : **4 sur 6** portent `0 h appariées ici (< 6)`
  et **2 sur 6** portent `1 h` — même signature de fond (« la base porte une
  ligne alors que le recalcul n'en apparie pas assez »), récurrente et
  antérieure. ⓘ Les six : `fcstagrume/aemet:9843A` (+48 h),
  `fcstagrume/mf:64155001` (+24 h, 1 h), `fcstagrume/pioupiou:935` (+48 h),
  `fcstagrume/windsmobi:ffvl-2347` (+24 h, 1 h), `fcstagrume/aemet:9252X`
  (+48 h), `fcstagrume/mf:06075007` (+6 h). ⚠️ **Et je ne reprends plus la
  lecture de la signature comme une tendance** : elle a été annoncée en train de
  « s'installer » le 27/10, démentie le 28, re-démentie les 29 et 30. Elle
  change tous les jours.
- ⓘ **Écart des deux mélanges** : `mse_comb` 17,841 contre `mse_comb_vec`
  17,841 (**+0,00 %**) — les deux chemins restent confondus.
- **Duels** : `agrume ↔ agrume_pi (+6 h)` n = 7 116, médiane +0,011, IC95
  [+0,007 ; +0,017] → `b_better` · `agrume_pi ↔ bw_mix (+6 h)` n = 7 100,
  médiane +0,387, IC95 [+0,317 ; +0,498] → `b_better` ·
  `agrume ↔ meteofrance_arome_france_hd (+6 h)` médiane −0,002, IC95
  [−0,003 ; +0,000] → **`not_separable`** ·
  `arome_r2 ↔ meteofrance_arome_france_hd (+6 h)` n = 16 593 sur **29 j**,
  médiane +0,072 → `b_better` · `agrume_pi ↔ bw_mix (+24 h)` n = 6 854 sur
  **29 j**, médiane +0,472 → `b_better`. Cumul toujours **tronqué par la
  rétention 30 j** (dette connue, `duel.DUEL_DAYS`).
  ⓘ **La journée AROME/R2 perdue du 25/10 se voit encore** : `arome_r2` porte
  **29 j** quand les duels +6 h vont jusqu'au 2026-10-30. Elle restera dans la
  fenêtre glissante jusqu'au **24/11**.
- **Murphy** : 67 079 triplets / **63 874** décomposés / 266 tenus dehors.
- ⚠️ **Volumes : légère remontée, et c'est cohérent.** **30 984**
  `model_verif_event` contre 29 738 hier (+4,2 %), et la famille `breeze_yield`
  **réapparaît avec 1 ligne** (0 le 30/10, 39 le 29/10) ; **362 862**
  accumulateurs avancés contre 375 302 ; **631 050** lignes écrites en base
  contre 642 777 ; détails par tranche 59 504 contre 60 814.
  `model_events.json` 9 795 Ko, `model_scores.json` 131 987 Ko,
  `model_murphy.json` 25 775 Ko. Observations : **3 731** balises (3 730 hier),
  3 426 zonées, 1 424 cases fines dont 738 sous les 2 balises.
  ⓘ **FDR** : 7 106 tests, 1 743 survivants à BH α=0,1, 114 rangs retirés sur
  984 publiés ; version corrigée 6 800 / 1 140, 118 retirés sur 560.
- **Second canal du téléphone (Discord)** : ⛔ **`BW_DISCORD_WEBHOOK_URL`
  toujours ABSENTE** du `.env` (recherche sur le **nom seul**, `grep -c` = 0,
  aucune valeur lue). **50ᵉ jour.** ⓘ Et c'est **mesurable** pour la deuxième
  fois : **deux** ⛔ ont crié cette nuit, `ⓘ push parti (webhook)` apparaît
  **2 fois**, `push Discord` **0 fois**. Le script
  `~/installer-webhook-discord.sh` est **sur le Mac**. ⇒ **Deuxième occasion
  manquée consécutive de prouver le second canal.**
- **`mutations_memoire`** : ⓘ **aucune ligne au journal sur 36 h**
  (`grep -c` = 0) — rien conclu : la dette de 3 mutations non vues (2, 5, 13)
  est reportée telle quelle.
- ⓘ `bw-model-oracle.service` : **non examiné, hors mission.**

## 10. ✅ Les tickets — trois commentaires délibérés, aucun ticket touché

**États revérifiés par GET AVANT toute écriture :**

```
KAN-3 | Terminé | done | updated 2026-10-30T07:44:32+0100 | 35 comm.
KAN-4 | À faire | new  | updated 2026-10-30T07:44:31+0100 | 49 comm.
KAN-5 | À faire | new  | updated 2026-10-30T07:44:30+0100 | 32 comm.
```

⇒ ✅ Les trois `updated` sont **exactement** ceux laissés par le run du 30/10 :
**aucun tiers n'a écrit depuis**, aucune collision. ⛔ **Et cela confirme par
une troisième voie qu'aucune réponse n'a été donnée à la question de fermeture
de KAN-5.**

**Après écriture**, les trois appels rendent `RC=0` et le message « Jira :
commentaire délibéré ajouté à KAN-5 / KAN-4 / KAN-3 », **une seule fois
chacun**.

**Vérifié par GET APRÈS écriture :**

```
KAN-3 | Terminé | done | updated 2026-10-31T08:24:42+0100 | 36 comm.  (+1)
KAN-4 | À faire | new  | updated 2026-10-31T08:24:42+0100 | 50 comm.  (+1)
KAN-5 | À faire | new  | updated 2026-10-31T08:24:41+0100 | 33 comm.  (+1)
```

⇒ ✅ **+1 chacun, exactement** : aucun doublon, et **aucun changement d'état**.

| ticket | ce qui a été posté | état |
|---|---|---|
| **KAN-5** | Le bloc purge en entier ; les **quatre** tests de lecture, tous au vert, **sonde comprise** ; le compteur **5 / 3** et le fait que le critère est rempli **depuis trois jours** ⇒ question posée une **troisième** fois ; l'explication complète du `n_57014 = 1` **hors purge**, le fait **neuf** qu'il tombe pour la **troisième** nuit de suite, et la preuve que la reprise a abouti à 100 % (362 862 / 362 862) ; la série sur 19 nuits ; le volume donné **explicitement** comme non significatif ; les **deux** défauts de code, entiers et non sollicités (6ᵉ nuit) ; pourquoi le silence du contrôle est juste *et* par la bonne porte ; la réserve maintenue sur l'absence de preuve SQL. | ✅ **posté ×1** — reste **ouvert** |
| **KAN-4** | Les trois jalons et leurs deltas ; **la confirmation de prudence du matin** — le mouvement favorable annoncé hier est **annulé en une nuit** (2 633 → 2 832 Mo, `incidents` 2 → 3), avec la citation exacte de la réserve posée le 30/10 ; la bande 3 151–3 452 **inchangée** (11ᵉ nuit) et le record du 25/10 non battu ; le coût par ligne rejouée à **0,5 o** de la veille, donné comme **indiscernable** ; **l'inversion** de la divergence pic / pages de swap, signalée **sans conclusion dans aucun des deux sens** ; **onzième** matin contradictoire de l'estimateur ; les **trois conditions de fermeture** ⇒ **non réunies** ; le remède tuple à ≈ −2 023 Mo, **40ᵉ jour**, et le **refus** du calcul à taux constant. | ✅ **posté ×1** — reste **ouvert** |
| **KAN-3** | **Commenté** (canal délibéré) parce que la durée **augmente** de 145 s. Le relevé complet ; **le fait neuf** : la hausse est pour la **première fois entièrement DANS les étapes** (+148,9 s) et le bloc hors étapes est **plat** (−3,9 s) ⇒ la demande de jalons dans `run.sh` **ne se renforce pas** ce matin ; la répartition par étape et le constat qu'elle est **répartie**, pas due à une seule étape ; le découplage **calcul** (cpu +168,2 > durée +145) ; ⛔ **le critère `bw-regime-sensibilite` REMPLI (2 / 2)** avec la série complète, le fait que ce **n'est pas du volume** (lignes −704, temps +73,5 s) **et** la nuance que **11,88 ms n'est pas un record** ⇒ **question posée, rien créé** ; le niveau remis dans la série du mois (**5ᵉ des dix, pas un maximum**) ; le solde **−163 s sur neuf nuits** ; la marge 37,30 % et les 3 021 s de réserve ; le rappel du 25ᵉ centile ; la remontée du garde **décrite sans être demandée**. **Avis : NE PAS ROUVRIR.** ⛔ **Non rouvert, non transité.** | ✅ **posté ×1** — reste **Terminé** |
| `bw-regime-sensibilite` | ⛔ **NON POSÉ, et c'est la décision du jour.** Le critère unique arbitré le 07/10 est **REMPLI (2 / 2)** pour la **première fois**. ❓ **Question posée à Yann** : veut-il le motif ? **Rien n'a été créé.** | — |
| `bw-melange-sans-gain` | ⛔ **non créé** : **cinq** points positifs de suite (§6). Avis : ne pas le créer. | — |
| `bw-r2-palier` | ⛔ **non créé.** ⬆️ Urgence **maintenue** : le palier est dépassé depuis **trois** nuits et R2 facture (§3.1). ❓ **Question reposée.** | — |
| `bw-character-57014` | ⛔ **non créé**, et je recommande de ne pas le créer : motif **antérieur**, qui se **rattrape seul** à 100 % — même si c'est sa **troisième** nuit de suite (§2.2). À surveiller seulement. | — |
| motif pour la purge | ⛔ **aucun motif neuf** : le motif existe, c'est **KAN-5**, et il est ouvert. | — |

ⓘ **Pourquoi `bw_jira_commenter` trois fois et `bw_jira_signaler` zéro fois** :
le contrôle s'est **tu** ce matin, donc le jeton du jour était **libre** — mais
`bw_jira_signaler` aurait **créé un ticket neuf** sur le motif « Terminé »
(KAN-3, puisque `bw_jira_chercher` filtre sur `statusCategory != Done`), et sur
les deux autres il n'apportait rien de plus. `bw_jira_commenter` prend une
**clé**, ne cherche rien, ne crée rien, ne touche pas au jeton du jour. C'est le
choix assumé de l'arbitrage du 07/10. Signature vérifiée dans `bw_jira.sh`
avant appel (`bw_jira_commenter() { local cle sujet corps … }`, ligne 85).

## 11. ✅ Horaire de la routine — À L'HEURE, à 47 secondes près

Programmée pour le **31/10 à 07:09:05 UTC**, tirée le **31/10 à 07:09:52 UTC** :
**+0 h 00 (47 s)**.

```
17/10 +1 h 56 · 18/10 +1 h 39 · 19/10 +7 h 43 · 20/10 +3 h 41 · 21/10 +8 h 50
22/10 +4 h 23 · 23/10 +4 h 21 · 24/10 +0 h 02 · 25/10 +0 h 01 · 26/10 +0 h 02
27/10 +10 h 09 · 28/10 +1 h 34 · 29/10 ⛔ +23 h 18 (matin SAUTÉ) · 30/10 +0 h 00
31/10 ✅ +0 h 00
```

⇒ ✅ **Le trou du 29/10 ne s'est pas reproduit**, et c'est le deuxième tir net
d'affilée. ⓘ Le VPS est à l'heure lui aussi : notation à 04:59:48 CET, contrôle
à 07:30:44 CET, timer suivant armé pour le **01/11 à 07:30:56 CET**.
ⓘ **Conséquence pratique** : pas d'occurrence en retard derrière celle-ci, donc
**pas de risque de second run aujourd'hui** comme le 30/10.

## 12. Décisions en attente de Yann — la liste à jour

1. ⛔ **NOUVEAU, PRIORITAIRE : le critère `bw-regime-sensibilite` est REMPLI
   (2 / 2).** Première fois depuis l'arbitrage du 07/10 : deux hausses
   consécutives du coût par ligne de `regime` (10,86 → 11,30 → 11,88 ms), et ce
   **n'est pas du volume** (lignes −704, temps +73,5 s). ❓ **Veux-tu un motif
   Jira ?** Rien n'a été créé. ⚠️ Rappel honnête : 11,88 ms n'est pas un record
   (12,59 le 22/10) — c'est la **série**, pas le niveau.
2. ❓ **PRIORITAIRE, et en retard de trois jours : fermeture de KAN-5.** Le
   critère écrit est **REMPLI** (5 / 3, rempli dès le 29/10). **Veux-tu le
   fermer ?** Je ne ferme rien sans ta réponse. Troisième fois que la question
   est posée.
3. ⬆️ **PRIORITAIRE : R2 facture, troisième nuit.** 10,251 Go (102,5 %), recul
   de 25 Mo seulement (§3.1). ❓ Motif Jira `bw-r2-palier`, ou action de
   rétention ?
4. ⚠️ **`installer-webhook-discord.sh`** (sur le Mac) — **50ᵉ jour**. ⬆️ Son
   intérêt **monte encore** : deux cris sont partis cette nuit, deuxième
   occasion manquée consécutive de prouver le second canal (§9).
5. ⛔ **Deux miroirs git en souffrance** : celui du **24/10** (jamais déposé) et
   celui du **26/10** (présent mais **non suivi par git**). **Rien fabriqué
   après coup.** Le miroir du 26/10 est **réparable sans rien inventer**.
6. ⛔ **Les DEUX correctifs de lecture de la purge** (§2.4), inchangés :
   (a) `bilan_purge` et le suffixe « des lignes RESTENT » ; (b)
   `registre_nuit._INCIDENT` et la ligne de sonde. **Il faut les deux.**
7. ⛔ **Les HUIT cas de position confirmés** (§7), dont **cinq nouveaux ce
   matin**. Trancher chaque cas, puis poser `position_suspecte` +
   `position_note` sur `station_zone` par `.sql`. ⚠️ **`pioupiou:1378`** est
   maintenant confirmée : **341 km**, candidate « AUTRE balise » la plus nette
   de la liste. Les trois autres grands écarts : `pioupiou:2171` (38,9 km),
   `pioupiou:84` (9,7 km), `pioupiou:367` (6,8 km, encore à 9 j).
8. ⬇️ **`diagnostic_base_sous_tension_2026-09-29.sql`** — **33ᵉ jour** sans
   être joué. Urgence **basse** : sixième nuit d'affilée où la purge aboutit,
   cinq sans le moindre avertissement. Lecture seule, 9 blocs, SQL Editor.
9. ⬇️ **Le `select as_of, count(*)`** sur `model_score_zone` : seule façon de
   **prouver** que la plus vieille journée est partie. **Aucun SQL joué sans ton
   accord.**
10. ⛔ **R2 : rétention sur `agrume/pi`** — **+48 objets chaque nuit, dix-huit
    nuits d'affilée, sans un seul recul** (§3.4).
11. ⛔ **Inventaire des 3 910 objets de `agrume/pi` que l'index ne réclame pas**
    (sur 3 957). À faire **avant** toute rétention.
12. ⛔ **Mémoire : la ligne en tuple** (≈ −1 030 o/ligne, ≈ −2 023 Mo). **40ᵉ
    jour sans rien de déployé** depuis `af25efb`. Seule porte de sortie de
    KAN-4 : le jalon est à **+597 Mo** du seuil.
13. ⛔ **Pente d'`audit_r2.py`** : borner à zéro les pentes négatives des
    préfixes à fenêtre glissante (§3.4). Une ligne, mais c'est une **écriture**.
14. ⓘ **Réouverture de KAN-3** : **mon avis est NON** — le niveau n'est pas un
    maximum du mois (5ᵉ des dix), le solde sur neuf nuits est **−163 s**, et la
    marge est de 3 021 s.
15. ⬇️ **Jalons de temps dans le bloc hors étapes de `run.sh`** — maintenu à
    « utile sans urgence », et ⬇️ **l'argument NE se renforce PAS ce matin** :
    pour la première fois en six nuits le bloc hors étapes est plat (§5.1).
16. ❓ **`bw-melange-sans-gain`** : **ne se confirme pas** (cinq points
    positifs, §6). Mon avis : ne pas créer le motif. À toi de refermer.
17. ⓘ **Le cri de position doit-il recrier** à état constant ? (ouvert depuis le
    01/10) ⬇️ **Moins pressant** : on vient de vérifier qu'un vrai front est
    bien signalé (§7).
18. ⓘ **`mutations_memoire`** : 3 mutations non vues (2, 5, 13), dette
    antérieure, inchangée.
19. ⓘ **`bw-model-oracle.service`** en `failed` — hors mission, non examiné.

✅ **Retirée de la liste** : la question du 27/10 sur `agrume/grille` (§3.2),
refermée après trois nuits identiques au Mo près.

## 13. Ce que ce run a DÉMENTI, et ce qu'il a CONFIRMÉ, de la note du 30/10

| annoncé le 30/10 | relevé le 31/10 |
|---|---|
| ✅ compteur KAN-5 à **4 / 3**, critère rempli, question posée | ✅ **CONFIRMÉ** : 5 / 3, cinquième nuit propre. ⛔ **Et toujours aucune réponse** — vérifié par le GET |
| ✅ « score par régime » sous le seuil, **avec la réserve** qu'une journée plus chargée le ferait repasser au-dessus | ✅ **RÉSERVE VÉRIFIÉE EN UNE NUIT** : 2 832 Mo, `incidents` 2 → 3. Le mouvement favorable est **annulé** |
| ⚠️ critère `regime` à **1 / 2**, première hausse de la nouvelle série | ⛔ **2 / 2 — LE CRITÈRE EST REMPLI.** 11,88 ms, et **pas** du volume (lignes −704) |
| ✅ durée **plate** : 13 s d'amplitude sur trois nuits | ⛔ **DÉMENTI** : **+145 s**. Mais pas un maximum du mois (5ᵉ des dix) et solde encore **−163 s** sur neuf nuits |
| ⛔ bloc hors étapes : **5ᵉ et 6ᵉ écart inexpliqué**, demande de jalons maintenue | ✅ **INVERSÉ** : hors étapes **plat** (−3,9 s), toute la hausse **dans** les étapes. L'argument **ne se renforce pas** |
| ⛔ R2 **10,276 Go**, palier dépassé | ⛔ **CONFIRMÉ** : 10,251 Go (102,5 %), 3ᵉ nuit, **−25 Mo seulement** |
| ⓘ `agrume/grille` « pratiquement refermée » à 766 / 766 | ✅ **REFERMÉE** : 3ᵉ nuit à 766 / 766 et 5,323 Go, au Mo près. Quitte la liste du §12 |
| ⛔ `agrume/pi` **17ᵉ** nuit à +48 | ⛔ **18ᵉ nuit à +48** (3 957 obj, 3 910 non réclamés) ⇒ **11ᵉ vérification** du §7.1 du 24/10 |
| ⚠️ jalon 3 400 Mo, bande 3 151–3 452, « aucune pente » | ⚠️ **3 397 Mo** : bande **inchangée** (11ᵉ nuit), record du 25/10 **non battu**. Validé une **5ᵉ** fois |
| ⚠️ coût par ligne rejouée 1 728,9 o, bande 1 596–1 744 | ⚠️ **1 728,4 o** — 0,5 o d'écart, **indiscernable**. Bande tenue une 11ᵉ nuit |
| ⚠️ réserve sur l'estimateur de pente (−24 Mo/nuit) | ✅ **validée une HUITIÈME fois** : encore **−24** pendant que le jalon fait −3 |
| ⚠️ swap : pic **baisse** de 282,5, pages **montent** de 271 808 | ⚠️ **INVERSION EXACTE** : pic **+64,2**, pages **−312 114**. Ne lire **ni l'un ni l'autre seul** |
| ⚠️ témoins du mélange **+3,0 %**, « devant » 52,2 % | ⚠️ **+3,3 %**, « devant » **52,4 %** ⇒ **cinq** points positifs, question **reste refermée** |
| ⓘ **quatre** balises (70, 175, 1715, 2058) à 10 j le 31/10 | ✅ **TENU AU BALISE PRÈS** — les quatre y sont, et les sept parties n'ont pas reparu |
| ⚠️ `pioupiou:1378` « ne se confirmera **jamais seule** » | ⛔ **DÉMENTI** : elle est passée à **10 j** et elle est dans le cri. ⇒ **cinq** nouvelles, pas quatre |
| ✅ « à front, pas à état », 10ᵉ et 11ᵉ vérification (aucun cri) | ✅ **12ᵉ vérification, et la première dans le sens POSITIF** : l'état change (3 → 8), **le cri part** |
| ✅ webhook `--ipv4` confirmé (2 pushes) | ✅ **CONFIRMÉ une 2ᵉ fois** : 2 pushes de plus, HTTP 200, zéro 429, 2 mails partis |
| ⛔ `BW_DISCORD_WEBHOOK_URL` absente, 49ᵉ jour | ⛔ **50ᵉ jour**, et **2ᵉ occasion manquée consécutive** (2 cris, 0 `push Discord`) |
| ⛔ écarts du recalcul : 4, signature qui **oscille** | ⚠️ **6** (bande 3–7, dedans) ; 4 en `0 h`, 2 en `1 h`. Signature **toujours** oscillante |
| ⓘ `n_57014 = 1` **hors purge**, 1ʳᵉ série de deux nuits | ⚠️ **1, hors purge, TROISIÈME nuit de suite** — fait neuf, petit. Rattrapé à 100 % |
| ⛔ horaire **+0 h 00** après le matin sauté | ✅ **+0 h 00 (47 s)** — deuxième tir net d'affilée |
| ⛔ miroirs git du 24/10 et du 26/10 en souffrance | ⛔ **inchangé**, vérifié et non arrangé |

⚠️ **« Une nuit ne fait pas une pente » — quatorzième fois en vingt-deux
jours.** Appliqué ce matin à : la hausse de 145 s de la durée (§5.2), le recul
de 3 Mo du jalon (§4.2), le coût par ligne rejouée à 0,5 o d'écart (§1),
l'inversion du swap (§4.3), le retour de `breeze_yield` à 1 ligne (§9), les
6 écarts du recalcul (§9) et le recul de 25 Mo de R2 (§3.1). **Aucun des sept
n'est présenté comme une tendance.** La tentation du jour était de lire
« la durée repart » — alors que 5 079 s n'est que le 5ᵉ point des dix derniers
et que le solde reste négatif.

⛔ **Et quatre fois, ce matin, la leçon ne s'applique PAS** — il faut le dire
aussi clairement :
1. Le **critère `regime`** est une **règle écrite comptée sur deux nuits**, pas
   une tendance. Il est rempli. La question doit être posée.
2. Le **critère de fermeture de KAN-5** est une **règle écrite comptée sur trois
   nuits**. Il est rempli depuis trois jours.
3. Le **dépassement du palier R2** est un **fait de facturation**, pas une pente.
4. Les **deux défauts de lecture de la purge** sont des **lectures de code**,
   vraies indépendamment du nombre de nuits.

⛔ **Enfin, la leçon neuve du jour, et elle corrige celle d'hier** (§7.1) : le
30/10 avait retenu qu'« un compteur de jours qui monte n'est pas une échéance ».
C'est vrai. Mais la même note a aussitôt posé la **réciproque** — « 1378 ne se
confirmera **jamais** seule » — et celle-là est **démentie dès le lendemain**.
Les deux sont des **prédictions sur un compteur bruité**, et **aucune des deux
ne devait être écrite**. La bonne règle est plus courte : **on relève l'état du
compteur, on ne prédit pas son franchissement, dans aucun des deux sens.**

## 14. Respect des règles

✅ **VPS en LECTURE SEULE, pleine et entière.** Aucun `systemctl`
start/restart/daemon-reload, aucun `enable`, **aucun SQL joué**, aucun rsync,
rien écrit dans `~/balise-watch` ni dans `/etc`. **Aucune redirection vers
`/tmp` du VPS** : toutes les sorties sont allées dans des fichiers du **Mac**
(`/Users/yann/bw-run-31-10/`) et relues avec `read_file`. ⓘ Seules exceptions,
qui sont le fonctionnement normal du code de production : `bw_jira_http` écrit
sa réponse dans un `mktemp -d` du VPS, et le `controle_quotidien.py --verbeux`
relancé à la main ne fait que lire.
✅ **Aucun secret lu par valeur** : `.balise-watch-alertes.env` **sourcé**
(`set -a; . … ; set +a`) ; `BW_DISCORD_WEBHOOK_URL` cherchée **par son nom seul**
(`grep -c`) ; le jeton Jira passe par `curl -K -`, jamais `-u`.
✅ `10-timeout-s3.conf` **non touché** ; remontée du garde **non lancée**, et
seulement **décrite** dans le commentaire KAN-3.
✅ `controle_quotidien.sh` **non touché**, son `$ETAT` conservé. Les deux
correctifs du §2.4 sont **proposés**, pas écrits.
✅ **Aucun ticket créé, fermé, rouvert ni transité.** Trois commentaires, tous
par `bw_jira_commenter`, GET **avant** ET **après** chacun (§10) : +1
commentaire chacun, aucun doublon, aucun changement d'état.
⛔ **Le motif `bw-regime-sensibilite` n'a PAS été créé** alors que son critère
est rempli : la règle dit de **reposer la question**, pas de créer. Question
posée (§12.1).
✅ **Desktop Commander exclusivement** pour fichiers et shell.
✅ **Lire avant d'écrire** : `project_read` du 31/10 (absent ⇒ création) et du
30/10 (lu en entier, les deux sections) ; `git log --since=midnight` dans les
deux dépôts ; `notes-projet/README.md` relu ; **note en section horodatée**.
⛔ **Aucun `git push`.**
ⓘ **Rien fabriqué pour combler les miroirs manquants** (24/10, 26/10).

## 15. ⓘ Outillage — les pièges connus, tous reconfirmés

1. ✅ **`SSH_AUTH_SOCK` manquant** (piège n°1) : confirmé une septième fois, et
   le correctif marche du premier coup.

   ```
   export SSH_AUTH_SOCK="$(launchctl getenv SSH_AUTH_SOCK)"
   ```

   Dans un **process persistant** (`start_process "bash -l"` +
   `interact_with_process`), `ssh-add -l` voit ensuite
   `balise-watch-vps (ED25519)`.
2. ✅ **Le lecteur de flux qui perd des lignes** (piège n°2) : contourné
   d'emblée. **Toute sortie dont une ligne compte est redirigée vers un fichier
   du Mac et relue avec `read_file`.**
3. ✅ **« did not respond within 60s » alors que la commande aboutit** (piège
   n°3) : confirmé, et c'est arrivé à **tous** les appels ssh de la session.
   ⛔ **Jamais relancé.** ✅ La bonne réaction : lire le fichier de sortie.
4. ✅ **Les heredocs cités pour le texte français** : les corps des trois
   commentaires sont écrits dans un script du Mac avec l'outil d'écriture de
   fichier, dans des heredocs `<<'XEOF'` (donc sans expansion ni échappement),
   et le script est passé par `ssh … 'bash -s' < post.sh`. Aucun mot de la
   liste noire dans la commande, et **rien d'écrit sur le VPS**.
   ⓘ Les corps sont rédigés **sans accents** pour éviter toute mutilation en
   transit ; les accents restent dans la note.
5. ⚠️ **PIÈGE NEUF, et il a coûté un aller-retour** : `bw_jira_http` prend
   **quatre** arguments — `$1` méthode, `$2` chemin, `$3` **corps JSON (vide
   pour un GET)**, `$4` fichier de sortie. Appelé avec trois, il échoue sur
   `$4: unbound variable` sous `set -u` et rend un code HTTP **vide**. Le GET de
   contrôle s'écrit donc :
   `bw_jira_http GET "/rest/api/3/issue/$K?fields=…" "" "$T/$K.json"`.
   ⓘ À reprendre tel quel dans les prochains runs.
