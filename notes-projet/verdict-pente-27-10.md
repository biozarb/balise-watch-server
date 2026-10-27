# Verdict de pente du 27/10/2026 — ✅ **Nuit propre sur la purge : compteur KAN-5 à 1 / 3.** ✅ **Le palier gratuit R2 n'est PLUS dépassé (9,121 Go) et le garde-fou cesse d'échouer après 11 nuits.** ✅ **Durée au plus bas des douze nuits, marge 41,6 %.** ⛔ **Mais la routine a tiré avec 10 h 09 de retard, et `agrume/grille` a perdu 1,125 Go sans que je sache qui l'a fait.**

Cinq faits, dans l'ordre d'importance. **(1)** La purge de
`model_score_zone` est **propre de bout en bout** : 141 051 lignes en 8
tranches, **aucune** tranche en échec, **aucun** défaut de sonde,
`n_57014 = 0` sur toutes les unités — la première nuit pleinement propre
depuis la rupture du 25/10 ⇒ compteur KAN-5 **1 / 3**. **(2)** Le compte R2
est repassé **sous** le palier gratuit : **9,121 Go (91,2 %)** contre 10,312
hier, et `bw-garde-fou-r2.service` rend **`OK en 5s`, code 0** — la série de
**11 échecs consécutifs s'arrête**, exactement comme la démonstration du
21/10 l'annonçait (`code 1` = « j'ai quelque chose à dire »). ⛔ **Mais la
cause est un retrait de 1 125 Mo et 156 objets sur `agrume/grille`, et je ne
sais pas qui l'a fait** : aucun commit dans les deux dépôts aujourd'hui.
**(3)** La durée tombe à **4 728 s (−405)**, la plus basse des douze
dernières nuits, marge **41,63 %** du garde. **(4)** Le bloc hors étapes, seul
point d'inquiétude d'hier, **rend 301 s** et repasse **sous la médiane** : la
réserve du 26/10 est démentie et corrigée dans KAN-3. **(5)** Les témoins du
mélange **remontent à +5,2 %** : la suite de deux nuits négatives ne devient
pas trois, donc **la question du motif `bw-melange-sans-gain` posée hier ne
se confirme pas** — et l'explication par la météo tombe dans les deux sens.

⛔ **Le seul vrai reproche du jour n'est pas sur le VPS, il est sur la
planification** : la routine était programmée à 07:09:05 UTC et a tiré à
**17:18:40 UTC**, soit **+10 h 09** — le pire retard du mois, après trois
matins nets. Le VPS, lui, était à l'heure.

⚠️ **Jalon mémoire : +248 Mo (3 399).** Le plancher d'hier est effacé en
vingt-quatre heures, comme ce plancher avait effacé le record du 25/10.
**Toujours aucune pente**, et KAN-4 reste ouvert.

## 18:19–18:50 (Paris, CET) — routine Balise Watch, run COMPLET

**Étape 0 : faite en entier, avant toute autre chose.**

- `git log --oneline --since=midnight` dans `balise-watch-server` **et** dans
  `surveillance balise` : **aucun commit aujourd'hui** dans les deux dépôts
  ⇒ aucun autre run n'a tourné. Dernier commit serveur : **`b9100c0`**
  (« Poller Infoclimat : disjoncteur sur panne amont (5xx/timeout) et alertes
  dédupliquées ») — **nouveau depuis la note du 26/10**, qui s'arrêtait à
  `a74c626`. Ce n'est pas un commit de routine : c'est du travail de Yann, et
  je ne l'ai pas examiné (hors mission).
- `project_read` de `claude/verdict-pente-27-10.md` : **absent** ⇒ cette note
  est une **création**, pas une fusion. `claude/verdict-pente-26-10.md` lu en
  **entier**.
- `notes-projet/README.md` relu : les quatre règles.
- ⛔ **État des miroirs git, vérifié et non arrangé** : `verdict-pente-24-10.md`
  **toujours absent**. `verdict-pente-26-10.md` **présent (723 lignes) mais
  tronqué au §13 et NON SUIVI par git** (`?? notes-projet/verdict-pente-26-10.md`)
  — exactement ce que la note du 26/10 annonçait après la coupure du pont.

## 1. Le relevé de la nuit du 26→27/10

`lancement = timer` · `result = success` · `exec_status = 0` · `oom = 0`
Début 04:58:41, fin 06:17:39 (heure locale du VPS, CET). En UTC le run part à
**03:58:41 Z** contre 03:57:40 Z la veille — **61 s de dérive**. Le contrôle
est passé à **07:30:21 CET**, suivant armé pour le **28/10 à 07:30:20 CET**.
Relevé **comparable** : le verdict porte.
Self-test du scoring : **VERT** (les cinq contrôles (a) à 1,0, le (b) permuté à
2,198 dans la fourchette attendue).

| | 25/10 | 26/10 | 27/10 | Δ nuit |
|---|---:|---:|---:|---:|
| `duree_s` | 5 252 | 5 133 | ✅ **4 728** | ✅ **−405** |
| `cpu_s` | 4 144,7 | 4 021,5 | **3 773,8** | **−247,7** |
| `marge_s` | 2 848 | 2 967 | **3 372** | +405 |
| marge / garde (8 100 s) | 35,16 % | 36,63 % | ✅ **41,63 %** | +5,00 pt |
| étapes (somme) | 3 089,3 | 2 957,6 | **2 853,7** | ✅ **−103,9** |
| hors étapes | 2 162,7 | 2 175,4 | ✅ **1 874,3** | ✅ **−301,1** |
| `jalon_max_mo` | 3 452 | 3 151 | ⚠️ **3 399** | ⚠️ **+248** |
| `mem_peak_mo` | 3 611,9 | 3 611,1 | **3 618,7** | +7,6 |
| `swap_peak_mo` | 2 491,2 | 2 398,9 | ✅ **2 057,4** | ✅ **−341,5** |
| `swap_out_pages` | 2 573 946 | 2 521 164 | **2 023 143** | −498 021 |
| `n_57014` | 3 | 1 | ✅ **0** | −1 |
| `incidents` | 5 | 3 | **3** | 0 |
| `lignes_regime` | 138 279 | 139 112 | **138 722** | −390 |
| `lignes_score_zone` | 148 683 | 149 592 | **149 281** | −311 |
| `lignes_daily` | 68 009 | 65 089 | **63 448** | −1 641 |
| `lignes_glissant` | 10 404 | 10 480 | **10 559** | +79 |
| `balise_jours_rejeu` | 2 075 594 | 2 070 596 | **2 063 862** | −6 734 |

Les trois `incidents` sont **tous** de mémoire (rejeu d'archive 2 987, score par
régime 2 833, oubli de la fenêtre rejouée 3 399 Mo). ✅ **Aucun avertissement de
purge, pour la première fois depuis le 24/10.**

Répartition par étape : `glissant` 992,5 → **921,2** (−71,3) · `regime`
1 591,7 → **1 554,7** (−37,0) · `stabilite` 293,4 → **303,2** (+9,8) ·
`rejeu` 80,0 → **74,6** (−5,4).

### Les deux rapports qui valent mieux que les valeurs brutes

**Coût par ligne rejouée** (`jalon_max_mo × 1048576 / balise_jours_rejeu`) :

```
16/10 1 701,4 o · 17/10 1 701,4 o · 18/10 1 706,1 o · 19/10 1 702,0 o
20/10 1 608,0 o · 21/10 1 726,1 o · 22/10 1 722,2 o · 23/10 1 621,3 o
24/10 1 723,8 o · 25/10 1 743,9 o · 26/10 1 595,7 o · 27/10 1 726,9 o
```

⇒ ⚠️ **1 726,9 o : +131,2 o en une nuit, deuxième valeur la plus haute de la
série**, juste derrière le plafond du 25/10 — et au lendemain du plancher. La
bande **1 596 à 1 744 o** tient une **septième** nuit. Sur douze nuits,
toujours **aucune pente** dans un sens ni dans l'autre.
ⓘ Et ce n'est **pas** un artefact de fenêtre, par la même démonstration qu'hier
mais en sens inverse : `balise_jours_rejeu` **recule** de 6 734, donc le jalon
monte **pendant que** la fenêtre se réduit.

**Coût par ligne de `regime`** (`etapes_s.regime / lignes_regime × 1000`) :

```
18/10 13,04 ms · 19/10 12,37 ms · 20/10 13,13 ms · 21/10 12,14 ms
22/10 12,59 ms · 23/10 11,97 ms · 24/10 11,42 ms · 25/10 12,19 ms
26/10 11,44 ms · 27/10 11,21 ms
```

⇒ ✅ **−2,0 % en une nuit, et c'est le point le plus bas de la série.**
`lignes_regime` recule de 390, donc ce n'est pas un effet de volume.
⇒ **critère `bw-regime-sensibilite` : reste à 0 / 2** (le critère demande deux
*hausses* consécutives ; c'est une baisse). Rien posé, aucune question.

**Calcul ou attente ?** La durée rend **405 s**, `cpu_s` **247,7 s** ⇒ environ
**61 %** de la seconde d'horloge rendue est une seconde de **calcul**, le reste
est de l'**attente en moins**. Les deux bougent dans le même sens : la
configuration la plus simple de la série récente, là où le 23/10 était de
l'attente pure et le 26/10 du calcul pur.

## 2. ✅ LA PURGE : nuit propre de bout en bout — compteur KAN-5 à 1 / 3

Le bloc purge, en entier :

```
06:17:26  → purge model_score_zone : 141051 ligne(s) effacée(s) en 8 tranche(s)
06:17:26  ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée
```

Deux lignes, et c'est tout. Lecture selon les règles du 28/09 complétées le
07/10 :

| test | verdict |
|---|---|
| tranche en échec | ✅ **✘ aucune** — pas une ligne `?as_of=eq.J&regime=eq.R` : HTTP 500 |
| bilan chiffré | ✅ **✔ 141 051 lignes, 8 tranches** |
| « des lignes RESTENT » | ✅ **✘ absent** de la ligne de bilan |
| sonde en défaut | ✅ **✘ aucun** — pas de ligne « plus vieille journée illisible » |

⇒ ✅ **NUIT PROPRE PLEINE**, la première depuis la rupture du 25/10. Et c'est la
première depuis le 24/10 où **même la sonde** se tait : la réserve qui pesait
sur le 26/10 (« l'absence de RESTENT est moins concluante quand la sonde
bronche ») **ne s'applique pas** ce matin.

`n_57014 = 0`, recherche élargie à **toutes** les unités sur 24 h : zéro.

```
13/10 0 · 14/10 1 · 15/10 0 · 16/10 1 · 17/10 0 · 18/10 0 · 19/10 0 · 20/10 0
21/10 0 · 22/10 1 · 23/10 4 · 24/10 0 · 25/10 3 · 26/10 1 · 27/10 0
```

### 2.1 Le volume : cohérent avec un retard résorbé — et ce n'est pas une preuve

```
25/10   108 479 lignes en  8 tranches, DES LIGNES RESTENT
26/10   168 198 lignes en 16 tranches, rattrapage (le double de tranches)
27/10   141 051 lignes en  8 tranches, rien au journal
```

⇒ Retour à **8 tranches** et à un volume de la fourchette habituelle
(125 000 à 141 000). C'est **cohérent** avec la résorption du retard de la
journée 2026-10-17 annoncée hier.
⛔ **Ce n'est pas une preuve.** Seul un `select as_of, count(*) from
model_score_zone group by as_of order by as_of limit 5` le dirait, et **aucun
SQL n'a été joué**. ⬇️ L'intérêt de cette requête **redescend d'un cran** par
rapport à hier, mais elle reste la seule réponse ferme.

### 2.2 ✅ Compteur de fermeture KAN-5 : 1 / 3

Le critère écrit — « trois nuits consécutives sans 57014 dans le bloc purge
ET avec un nombre de lignes lisible » — est rempli sur ses deux branches.
Le compteur passe de **0 / 3** à **1 / 3**. Fermeture envisageable **au plus
tôt le 29/10**, et **seulement avec l'accord de Yann**. Rien de fermé.
ⓘ La sous-question du 26/10 — la sonde doit-elle compter ? — **ne se pose pas
cette nuit** puisqu'il n'y a aucun défaut de sonde. Elle reste ouverte pour les
nuits où le cas se représentera.

### 2.3 ⛔ Les deux défauts de code restent entiers, et cette nuit ne les teste pas

1. **(a)** `bilan_purge` ignore le suffixe « des lignes RESTENT » — faux négatif
   démontré le 25/10.
2. **(b)** `registre_nuit._INCIDENT` ne reconnaît pas la ligne de sonde, donc la
   branche `sonde_ko` de `controle_quotidien.constats()` est du **code mort** —
   démontré le 26/10.

⛔ **Aucun des deux n'est déployé, et il faut les DEUX** : séparément, aucun ne
suffit. Cette nuit n'avait **ni** ligne restante **ni** sonde en défaut : elle
ne pouvait donc ni les confirmer ni les réfuter. Ce sont des **écritures dans
le code** : c'est Yann qui tranche.
ⓘ Et ce n'est toujours pas une raison de retirer le correctif du 07/10 : sans
lui, KAN-5 recevrait « purge en échec » toutes les nuits où une tranche est
rejouée puis rattrapée, ce qui est le cas normal.

### 2.4 Le contrôle de pente s'est tu, et cette fois par la bonne porte

```
2026-10-27T06:30:21Z rien à dire : pente plate ou négative, ou échéance hors horizon
```

Verbeux, relancé à la main en lecture seule :

```
ⓘ 89 relevé(s), 68 comparable(s) ; durée : 10 points, pente -143 s/nuit ;
  mémoire : 10 points, pente -188 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate/négative, ou échéance hors horizon
```

✅ Le silence est **juste** et il est **par la bonne porte** : `incidents` ne
porte aucun avertissement de purge **parce qu'il n'y en a eu aucun** — et non
plus, comme le 26/10, parce que le motif du registre ne sait pas reconnaître la
ligne de sonde. Le défaut (b) n'a simplement pas eu l'occasion de nuire.

## 3. ✅⛔ LE FAIT DU JOUR : R2 repasse sous le palier gratuit — et je ne sais pas pourquoi

```
26/10   10,312 Go   (103,1 %)   ⛔ DÉPASSÉ de 312 Mo   7 035 objets
27/10    9,121 Go   ( 91,2 %)   ✅ SOUS LE PALIER       6 943 objets
```

⇒ ✅ **−1 191 Mo et −92 objets en une nuit.** Le compte n'est plus au-dessus des
10 Go gratuits, pour la première fois depuis au moins onze nuits.
⇒ ✅ **`bw-garde-fou-r2.service` rend `OK en 5s`, `ExecMainStatus=0`,
`NRestarts=0`.** La série de **11 échecs consécutifs s'arrête**. C'est la
**vérification** de la démonstration du 21/10 : `code 1` ne signalait pas une
panne, il signalait « j'ai quelque chose à dire ». Il n'a plus rien à dire, et
il rend 0. ⇒ **rien à corriger, et rien n'avait été cassé.**
ⓘ Conséquence : **aucun cri n'est parti cette nuit** (ni R2, ni position), donc
**zéro push** — contre 2 hier.

### 3.1 ⛔ La cause, et la question que je ne tranche pas

```
                      25/10            26/10            27/10            Δ nuit
agrume/grille    5,366 Go  772 obj  5,323 Go  766 obj  4,198 Go  610 obj  −1 125 Mo / −156 obj
agrume/pi        1,628 Go 3 669 obj 1,649 Go 3 717 obj 1,669 Go 3 765 obj     +20 Mo /  +48 obj
arome/rafale     0,902 Go           0,883 Go           0,830 Go               −53 Mo
arome/sol        0,631 Go           0,616 Go           0,576 Go               −40 Mo
```

⇒ ⛔ **La baisse du compte vient presque entièrement de `agrume/grille`** :
1 125 Mo et 156 objets retirés, et son index lit maintenant
**610 présentes / 610 réclamées ✓**.
⛔ **Je ne sais pas qui a fait ce retrait.** Aucun commit aujourd'hui dans les
deux dépôts ; le seul commit récent (`b9100c0`) porte sur le poller Infoclimat.
Ce n'est ni une rétention que je connaisse, ni un geste de cette routine (VPS en
lecture seule). ❓ **Question à Yann : est-ce toi ? Ou une rétention qu'on a
oubliée ?** Tant qu'on ne le sait pas, **ce gain n'est pas acquis** : un retrait
dont on ignore l'auteur peut ne pas se reproduire, ou se reproduire là où on ne
le veut pas.
ⓘ ⚠️ **Et la leçon du 24/10 (§7.1) s'applique une HUITIÈME fois, dans le sens
le plus spectaculaire** : *le total du compte n'est pas un indicateur de
l'accumulation.* Le total perd 1 191 Mo et **l'accumulation n'a pas bougé d'un
objet** — `agrume/pi` fait **+48 objets pour la QUATORZIÈME nuit consécutive**,
sans un seul recul.

### 3.2 ⛔ `agrume/pi` : rien de changé, et l'écart non réclamé grossit toujours

```
│ agrume/grille/                          610 présentes /  610 réclamées   ✓
│ agrume/pi/grille/                        19 présentes /   19 réclamées   ✓
│ agrume/pi/rafraichissement/              28 présentes /   28 réclamées   ✓
│ agrume/piaf/                             11 présentes /   11 réclamées   ✓
```

47 objets couverts sur **3 765** ⇒ **3 718 objets que nul index ne réclame**
(3 670 hier). **+48 par nuit, exactement le rythme d'accumulation.**
ⓘ Ce n'est pas la preuve qu'ils sont orphelins ; c'est la constatation qu'on
n'en sait rien. **L'inventaire reste le geste à faire avant toute rétention** —
et il est **plus** urgent aujourd'hui, pas moins : le répit sur le palier retire
la pression sans retirer le problème.

Pente affichée de `agrume/pi` : **+0,579 Go/mois**, inchangée. Pente du total
du compte : **+0,032 Go/mois** (hier +0,047), palier annoncé dans **813 j**
(≈ 2029-01-17).
⛔ Le point sur **`audit_r2.py`** (borner à zéro les pentes négatives des
préfixes à fenêtre glissante) reste **entier**, et l'écart entre les deux pentes
s'élargit encore : `arome/rafale` **−0,376**, `arome/sol` **−0,285**,
`arome/alt` −0,090, `arome/lod` −0,047 Go/mois tirent la pente du total vers
zéro pendant que `agrume/pi` monte à +0,579. **Une écriture, non faite.**

## 4. ⚠️ Mémoire — le plancher d'hier effacé en 24 h, toujours aucune pente

```
rejeu d'archive         3 014 → 2 987 Mo   (−27)    ⛔ au-dessus du seuil : +187
score par régime        2 813 → 2 833 Mo   (+20)    ⛔ au-dessus du seuil :  +33
oubli fenêtre rejouée   3 151 → 3 399 Mo  (+248)    ⛔ au-dessus du seuil : +599
```

```
18/10 3 391 · 19/10 3 381 · 20/10 3 193 · 21/10 3 424 · 22/10 3 412
23/10 3 210 · 24/10 3 411 · 25/10 3 452 · 26/10 3 151 · 27/10 3 399
```

⇒ ⚠️ **La bande va de 3 151 à 3 452 Mo.** Le plancher d'hier est effacé en une
nuit — exactement comme ce plancher avait effacé le record du 25/10. Deux nuits
de suite, le mouvement du jalon annule celui de la veille.
⚠️ **Et la lecture est strictement la même qu'hier, dans l'autre sens** : ce
n'est **pas** une reprise de fond. Dix nuits, autant de montées que de
descentes, **aucune pente nette**. C'est la onzième fois en dix-huit jours que
« une nuit ne fait pas une pente » s'applique ici — et la deuxième fois en deux
jours que la note de la veille se trouve confirmée dans sa prudence.

### 4.1 L'estimateur de pente, SEPTIÈME matin contradictoire

| matin | pente affichée | ce qui s'est passé cette nuit-là |
|---|---:|---|
| 21/10 | −22 Mo/nuit | échéance 18/11 |
| 22/10 | −12 Mo/nuit | échéance 12/12 |
| 23/10 | −188 Mo/nuit | échéance 25/10 ⇒ démentie dès le 24/10 (+201 Mo) |
| 24/10 | −12 Mo/nuit | ≈ 14/12 |
| 25/10 | −12 Mo/nuit | **le matin d'un record de +41 Mo** |
| 26/10 | −188 Mo/nuit | **le matin d'une chute de −301 Mo** |
| 27/10 | **−188 Mo/nuit** | **le matin d'une hausse de +248 Mo** |

⇒ Il affiche la **même** valeur, −188 Mo/nuit, deux matins de suite, pour deux
nuits **opposées** de 301 Mo et 248 Mo. C'est le **25ᵉ centile des différences**,
qui ignore par construction les deux plus grosses variations. Conclusion posée
le 23/10, **confirmée une cinquième fois** : **cet estimateur n'est pas
utilisable en prévision** sur cette série. ⓘ L'échéance étant hors horizon
(30 j), le contrôle se tait — et sur ce point précis **il a raison**.

### 4.2 ⚠️ Bornes de lecture, et le seul mouvement vraiment favorable

`mem_peak` monte de **7,6 Mo seulement** (3 618,7) : le pic du processus est
quasi plat pour la troisième nuit, c'est **le jalon seul** qui bouge — dans un
sens hier, dans l'autre aujourd'hui.
✅ En revanche le **swap** rend beaucoup : pic **2 057,4 Mo** (−341,5) et
**2 023 143** pages sorties (−498 021). C'est le plus bas des nuits récentes.
⚠️ Mais ce n'est **pas** un plancher de série : septembre portait 111,4 Mo
(08/09) et 165,7 Mo (01/09) — un autre régime de charge, pas une référence.

### 4.3 Les trois conditions de fermeture de KAN-4

| condition | état |
|---|---|
| le contrôle se tait sur `bw-pente-memoire` | ✅ **remplie** |
| le jalon est mesurément retombé | ⛔ **non** — 3 399 Mo, **+599** au-dessus du seuil |
| le swap au pic ≈ 0 | ⛔ **non** — 2 057,4 Mo |

⇒ ⛔ **NON RÉUNIES. KAN-4 reste ouvert.**

### 4.4 Le remède, inchangé — et toujours le seul à la bonne échelle

La **ligne en tuple** (§2.6 de l'enquête du 10/09) : ≈ **−1 030 o/ligne**, soit
≈ **−2 027 Mo** sur les 2 063 862 balise-jours rejoués cette nuit — à comparer
aux **599 Mo** qui séparent le jalon du seuil. ⛔ **Rien de déployé côté mémoire
depuis `af25efb` (21/09) — 36ᵉ jour.** ⚠️ L'élagage de `units` avait rendu
−124 Mo au lieu de −1 500 : les gains sont dans la **structure**. La mesure
`tuple` contre `namedtuple` à la sonde reste le préalable.

## 5. ✅ Durée — −405 s, et la réserve d'hier sur le bloc hors étapes est DÉMENTIE

```
            étapes     hors étapes   total
25/10      3 089,3       2 162,7     5 252
26/10      2 957,6       2 175,4     5 133
27/10      2 853,7       1 874,3     4 728
Δ nuit       −103,9        −301,1     −405
```

⇒ ✅ **74 % de la baisse est HORS des étapes** — l'inverse exact du 26/10, où
toute la baisse était dans les étapes (−131,7 pour −119 au total).
⇒ ✅ **4 728 s est la durée la plus basse des douze dernières nuits** (la
précédente était 4 861 s le 16/10). ⚠️ La série comparable porte bien plus bas
en août (249 s le 10/08) : c'était un autre régime de run, pas une référence.
⇒ ✅ **Marge à 41,63 % du garde**, contre 36,63 % hier et un plancher de série à
34,57 % le 23/10. Le meilleur niveau du mois.

### 5.1 ✅ Le bloc hors étapes : la suite de trois nuits s'arrête à trois

Classement sur les **68 relevés comparables** :

```
1.  23/10   2 361,5 s
2.  18/09   2 254,2 s
3.  01/10   2 219,7 s
4.  26/10   2 175,4 s
5.  25/10   2 162,7 s
6.  24/10   2 154,0 s
…
45. 27/10   1 874,3 s   ← cette nuit
médiane    1 967,0 s
```

⇒ ✅ **De la 4ᵉ place à la 45ᵉ sur 68, et sous la médiane.** La note du 26/10
écrivait : « trois nuits consécutives au-dessus de 2 150 s, et quatre des six
premières places sont les quatre dernières nuits — ce n'est pas encore une
pente, mais ce n'est plus le pic d'une nuit ». ⇒ **Démenti : c'était bien une
bosse de trois nuits, et elle est finie.**
⬇️ **Je redescends donc ma propre demande** : les **jalons de temps dans le bloc
hors étapes de `run.sh`** repassent de ⬆️ « utile » (position du 26/10) à
« **utile sans urgence** ». ⚠️ Mais ils gardent leur seul vrai argument, et il
est renforcé : ce bloc (publication, Murphy, événements, pression, duels, purge)
n'est **pas instrumenté**, et on ne peut donc expliquer **ni** le +12,7 s d'hier
**ni** le −301,1 s d'aujourd'hui. C'est une **écriture** dans `run.sh` : non
faite.

### 5.2 Bornes de lecture, et le garde

⚠️ **Une nuit ne fait pas une pente, et cinq non plus** : 23/10 **+58**, 24/10
**−236**, 25/10 **+188**, 26/10 **−119**, 27/10 **−405**. **Solde des cinq
nuits : −514 s.** La série oscille, avec une inclinaison récente à la baisse
qu'aucun des cinq points ne suffit à établir.

⛔ **Remontée du chien de garde : NON LANCÉE et NON PROPOSÉE.**
`controle_quotidien.proposition()` ne se déclenche pas (pente négative, échéance
hors horizon). La forme reste connue et je la **décris** sans la demander :
écrire la mesure dans l'en-tête de `10-timeout-s3.conf` (135 → 140/145 min),
déployer, vérifier. Avec **3 372 s** de réserve sur 8 100, aucune urgence
mécanique. **C'est Yann qui décide et qui lance.**

ⓘ Rappel, qui vaut pour KAN-3 : la pente du contrôle est le **25ᵉ centile des
différences**. Elle n'a vu ni le +153 s du 01/10, ni le +336 s du 06/10, ni le
+70 s du 07/10, ni le +188 s du 25/10. Ce matin elle affiche **−143 s/nuit**, ce
qui pour une fois ne contredit rien.

## 6. ✅ Témoins du mélange — la suite négative s'arrête à deux, et l'explication par la météo tombe

```
⛔ témoins du mélange : sur 6 840 balise-jours×échéance, le mélange fait
   3,3749 km/h contre 3,5589 pour le meilleur membre a priori
   (gain +5,2 %, mélange devant dans 50,3 % des cas) ;
   contre la moyenne UNIFORME, sur 1 109 : 3,6544 vs 3,7775 (gain +3,3 %)
```

Série du gain contre le **meilleur membre a priori** :

```
−0,6 % (07/10) · +2,5 · +1,7 · −0,3 · +0,9 · −0,9 · +0,1 · +0,8
· −4,0 % (25/10) · −2,2 % (26/10) · +5,2 % (27/10)
```

⇒ ✅ **+5,2 % est le meilleur point de la série**, et la part « devant » repasse
**au-dessus de la barre : 50,3 %** (44,1 puis 45,0 les deux nuits précédentes).
⇒ ❓ **La question posée hier à Yann — veux-tu un motif `bw-melange-sans-gain` ?
— NE SE CONFIRME PAS.** La consigne était « si la série confirme, demander ».
Elle ne confirme pas : deux points négatifs ne deviennent pas trois. ⇒ **Mon
avis : ne pas créer le motif.** Rien créé, et la question d'hier est donc
refermée — mais c'est à Yann de le dire s'il veut la garder ouverte.

⚠️ **Et il faut corriger une explication, pas seulement un verdict.** Le 25/10
la note proposait : « le mélange perd justement quand il y a peu à gagner »
(erreur absolue 6,11 km/h, journée calme). Le 26/10 cette excuse était déclarée
tombée (erreur 7,47, gain toujours négatif). Cette nuit l'erreur absolue tombe à
**3,37 km/h (−55 %)** — **la journée la plus calme des trois** — et le gain est
le **meilleur** de la série. ⇒ ⛔ **L'explication par le niveau de vent ne tient
donc NI dans un sens NI dans l'autre, et je l'abandonne.** Les trois nuits
disent : le gain varie beaucoup, et l'erreur absolue ne le prédit pas.

## 7. ✅ Position — liste identique, aucun cri : 8ᵉ vérification du « à front »

```
⛔ position : 17 balise(s) divergent du gel (10 j lus), dont 3 CONFIRMÉE(S)
   ⛔ pioupiou:2171          38 915 m · 10 j · nœud + profil CHANGENT
   ⛔ pioupiou:84             9 748 m · 10 j · nœud + profil CHANGENT
   ⛔ infoclimat:STATIC0491   1 159 m · 10 j · nœud 0,01 CHANGE
```

⇒ ✅ **Liste strictement identique à celle du 26/10**, et **aucune ligne « cri
déposé pour envoi »**, **aucun push**, **aucun mail**. C'est la **8ᵉ
vérification** du mécanisme « à front, pas à état » — les sept précédentes
étaient six « liste identique ⇒ pas de cri » et, hier, le premier **départ**
(`pioupiou:367` sortant de la liste faisait partir un cri). Cette nuit : liste
identique, silence. **Le mécanisme est maintenant bien établi.**
ⓘ La question du 01/10 reste ouverte — **faut-il qu'il recrie à état constant ?**
C'est précisément le cas de ce matin : trois balises restent confirmées depuis
dix jours, et rien ne le rappelle.

⚠️ **`pioupiou:1378` reste bloquée à 9 j pour la CINQUIÈME journée**, écart
inchangé à **340 941 m**. Elle re-clignote, donc **le compteur de jours ne la
confirmera jamais seule.** 341 km n'est pas un décalage de coordonnées
plausible : candidate nette « AUTRE balise », à trancher à la main.
ⓘ `pioupiou:367` (6 764 m) reste à **9 j**, deuxième jour hors des confirmées.
ⓘ **Les onze balises à 5 j hier sont toutes à 6 j** (327, 1749, 1568, 1558, 70,
1724, 1715, 1435, 175, 2058, 633) : la fenêtre se remplit, aucune n'a disparu —
elles atteindraient 10 j le **31/10**. Et `mf:05170001` passe de 2 à **3 j**
(330 m) : rien à en conclure.

## 8. Les trois correctifs du 07/10 — verdict correctif par correctif

| correctif | verdict du 27/10 |
|---|---|
| **1. webhook `--ipv4`** | ⓘ **ni confirmé ni mis en défaut : rien à envoyer.** Aucun ⛔ n'avait à crier cette nuit (liste de position inchangée, palier R2 plus dépassé) ⇒ **zéro push**, et c'est le comportement correct. ✅ **Aucun HTTP 429 ntfy** : recherche dédiée sur 24 h, `grep -i ntfy | grep -c 429` = **0**. Les **82** occurrences de « 429 » du journal viennent **toutes** des pollers de l'API aromepi (`run-ingest-pi.sh` 35, `run-ingest-pi-rafale.sh` 27, `run-ingest-piaf.sh` 16, `run-poller.sh` 4) — sans rapport avec ntfy. |
| **2. garde-fou des deux jetons** | ✅ **tient** mécaniquement : le contrôle de 07:30:21 s'est tu, aucun jeton posé, aucun doublon possible. `controle_quotidien.sh` conserve son `$ETAT` — **non touché**. |
| **3. rejeu de purge ≠ échec** | ⓘ **non sollicité** : purge propre, aucun avertissement, rien à lire. Son faux négatif du 25/10 (défaut (a)) reste **entier et non corrigé**, et le second chemin démontré hier (défaut (b)) aussi. |

## 9. Les autres témoins

- ⚠️ **Témoin du corrigé : 17,9 pt** (27,1 hier), sur 8 379 balise-jours — vrai
  antécédent **+15,4 %**, autre balise **−2,6 %**. Série de la part site :
  24,1 (18/10) → 22,9 → 18,0 → 16,6 → 23,3 → 20,4 → 27,8 → 27,6 → 27,1 →
  **17,9 pt**. C'est le **plus gros mouvement d'une nuit** de la série
  (−9,2 pt), et il reprend très exactement le niveau du 20/10. Version FIN,
  part secteur+heure : 14,3 → 12,7 → 8,5 → 9,8 → 10,5 → 12,6 → 12,2 → 13,3 →
  13,4 → **11,4 pt** (4 090 balise-jours). ⓘ **Ça oscille**, comme conclu les
  22, 23, 24, 25 et 26/10 — et un mouvement plus large n'est pas une pente.
  **Rien à surveiller.**
- ⚠️ **Écarts du recalcul indépendant : 4** (5 le 26/10, 7 le 25/10). Série :
  3 · 5 · 4 · 7 · 4 · 7 · 5 · **4** ⇒ **elle va de 3 à 7 et revient** ; rien à
  en tirer sur le nombre. ⛔ **Mais la signature se durcit** : **4 sur 4**
  portent `0 h appariées ici (< 6)` et non `1 h`, contre 4 sur 5 hier et 6 sur
  7 avant-hier — soit **14 sur 16 en trois nuits**. Les quatre de cette nuit :
  `fcstagrume/aemet:9677`, `fcstagrume/infoclimat:000RB`,
  `fcstagrume/windsmobi:slf-ARO3`, `fcstagrume/mf:66082004`, toutes en `+6 h`.
  Même signature de fond (« la base porte une ligne alors que le recalcul n'en
  apparie aucune »), récurrente et antérieure — mais le `0 h` **s'installe** et
  mérite d'être resuivi.
- ⓘ **Écart des deux mélanges** : `mse_comb` 17,841 contre `mse_comb_vec`
  17,841 (**+0,00 %**) — les deux chemins restent confondus.
- **Duels** : `agrume ↔ agrume_pi (+6 h)` n = 7 154, médiane +0,010, IC95
  [+0,006 ; +0,015] → `b_better` · `agrume_pi ↔ bw_mix (+6 h)` n = 7 116,
  médiane +0,422 → `b_better` · `agrume ↔ meteofrance_arome_france_hd (+6 h)`
  médiane −0,001, IC95 [−0,003 ; +0,000] → **`not_separable`** ·
  `agrume_pi ↔ bw_mix (+24 h)` n = 6 870 sur 29 j → `b_better`. Cumul toujours
  **tronqué par la rétention 30 j** (dette connue, `duel.DUEL_DAYS`).
  ⓘ **La journée AROME/R2 perdue du 25/10 se voit encore** : le duel
  `arome_r2 ↔ meteofrance_arome_france_hd (+6 h)` porte n = **16 574** sur
  **29 j** quand les autres duels +6 h vont jusqu'au 2026-10-26. C'est le même
  trou qu'hier, qui restera dans la fenêtre glissante jusqu'au 24/11.
- **Murphy** : 66 692 triplets, **63 963** décomposés, 266 balises dehors.
- ⚠️ **Volumes de la nuit, tous en net recul, et c'est cohérent** : 63 448
  agrégats quotidiens (−1 641), **40 850** `model_verif_event` contre 79 742
  (**−49 %**), **374 845** accumulateurs avancés sur 374 845 (contre 485 617),
  `model_events.json` 9 680 Ko, `model_scores.json` 130 794 Ko,
  `model_murphy.json` 25 633 Ko, **646 271 lignes écrites en base** (797 752 la
  veille). ⓘ **Ce n'est pas une panne de collecte** : les observations sont là
  (**3 708** balises contre 3 695 la veille). C'est la **journée** qui était
  calme — 3 409 balises zonées pour les événements contre 3 695, et une erreur
  absolue à 3,37 km/h contre 7,47. Moins de vent, moins d'événements de vent.
- **Second canal du téléphone (Discord)** : ⛔ **`BW_DISCORD_WEBHOOK_URL`
  toujours ABSENTE** du `.env` (recherche sur le **nom seul**, `grep -c` = 0,
  aucune valeur lue). **46ᵉ jour.** Le script `~/installer-webhook-discord.sh`
  est **sur le Mac**, pas sur le VPS (erreur d'outillage notée le 26/10, non
  refaite).
- **`mutations_memoire`** : ⓘ **aucune ligne au journal cette nuit non plus**
  (`grep -c` = 0) — rien conclu : la dette de 3 mutations non vues (2, 5, 13)
  est reportée telle quelle.
- ⓘ `bw-model-oracle.service` : **non examiné, hors mission.**

## 10. ✅ Les tickets — trois commentaires postés, aucun ticket touché

**États revérifiés par GET AVANT toute écriture :**

```
KAN-3 | Terminé | done | updated 2026-10-26T08:35:57+0100 | 32 comm.
KAN-4 | À faire | new  | updated 2026-10-26T08:34:47+0100 | 46 comm.
KAN-5 | À faire | new  | updated 2026-10-26T08:33:40+0100 | 29 comm.
```

⇒ ✅ Les trois `updated` sont exactement ceux laissés par le run du 26/10 :
**aucun tiers n'a écrit depuis**, pas de collision.

**Vérifié par GET APRÈS écriture :**

```
KAN-3 | Terminé | done | updated 2026-10-27T18:43:41+0100 | 33 comm.  (+1)
KAN-4 | À faire | new  | updated 2026-10-27T18:43:40+0100 | 47 comm.  (+1)
KAN-5 | À faire | new  | updated 2026-10-27T18:43:39+0100 | 30 comm.  (+1)
```

⇒ ✅ **+1 chacun, exactement** : aucun doublon, et **aucun changement d'état**.

| ticket | ce qui a été posté | état |
|---|---|---|
| **KAN-5** | Le bloc purge en entier (deux lignes) ; les **quatre** tests de lecture, tous au vert, **sonde comprise** ; `n_57014 = 0` sur toutes les unités et la série sur 15 nuits ; le compteur **1 / 3** avec sa date de fermeture possible au plus tôt (29/10) et le rappel qu'elle demande l'accord de Yann ; le volume (8 tranches, retour en fourchette) donné comme **cohérent** avec un retard résorbé et **explicitement pas comme une preuve** ; les **deux** défauts de code, entiers, et le fait que cette nuit ne pouvait **ni** les confirmer **ni** les réfuter ; pourquoi le silence du contrôle est juste *et* par la bonne porte. | ✅ **posté ×1** — reste **ouvert** |
| **KAN-4** | Les trois jalons et leurs deltas ; **3 399 Mo (+248)**, le plancher d'hier effacé en 24 h, et le refus explicite d'y lire une reprise ; coût par ligne rejouée **1 726,9 o** (2ᵉ plus haut), avec la démonstration que ce n'est pas un effet de fenêtre (`balise_jours_rejeu` recule) ; **septième** matin contradictoire de l'estimateur, qui affiche −188 Mo/nuit deux matins de suite pour deux nuits opposées ; les **trois conditions de fermeture** (muet ✔, plafond ✘ **+599**, swap ✘ **2 057,4 Mo**) ⇒ **non réunies** ; le recul du swap donné comme le seul mouvement favorable et comme insuffisant ; le remède tuple à ≈ −2 027 Mo, **36ᵉ jour** ; un calcul à taux constant donné **et** réfuté. | ✅ **posté ×1** — reste **ouvert** |
| **KAN-3** | **Commenté** (canal délibéré) pour **corriger la réserve que j'y avais écrite hier**. −405 s, marge **41,63 %**, répartition par étape, 74 % de la baisse hors étapes, découplage calcul/attente (61 % de calcul) ; le bloc hors étapes **de la 4ᵉ à la 45ᵉ place sur 68** et sous la médiane ⇒ la suite de trois nuits s'arrête à trois, et la demande de jalons dans `run.sh` **redescend** de « utile » à « utile sans urgence », en gardant son seul vrai argument ; critère `regime` **0 / 2** avec la série du coût par ligne ; le rappel du 25ᵉ centile ; solde des cinq nuits **−514 s** ; la remontée du garde **décrite sans être demandée**. **Avis donné : NE PAS ROUVRIR.** ⛔ **Non rouvert, non transité** : reste « Terminé ». | ✅ **posté ×1** — reste **Terminé** |
| `bw-melange-sans-gain` | ⛔ **non créé**, et la question d'hier **ne se confirme pas** (§6). Avis : ne pas le créer. | — |
| `bw-r2-palier` | ⛔ **non créé.** ⬇️ Et son urgence **tombe** : le palier n'est plus dépassé (§3). | — |
| `bw-regime-sensibilite` | ⛔ **non posé**, critère **0 / 2**. | — |
| motif pour la purge | ⛔ **aucun motif neuf** : le motif existe, c'est **KAN-5**, et il est ouvert. | — |

ⓘ **Pourquoi `bw_jira_commenter` trois fois et `bw_jira_signaler` zéro fois** :
le contrôle s'est tu ce matin, donc le jeton du jour était libre — mais
`bw_jira_signaler` aurait **créé un ticket neuf** sur le motif « Terminé »
(KAN-3, puisque `bw_jira_chercher` filtre sur `statusCategory != Done`), et sur
les deux autres il n'apportait rien de plus. `bw_jira_commenter` prend une
**clé**, ne cherche rien, ne crée rien, ne touche pas au jeton du jour. C'est le
choix assumé de l'arbitrage du 07/10, et il se dit ici comme il doit.

## 11. ⛔ Horaire de la routine — +10 h 09, le pire retard du mois

Programmée pour **07:09:05 UTC**, tirée à **17:18:40 UTC**, première commande
jouée à **17:19:27 UTC** (18:19 CET) : **+10 h 09**.

```
15/10 +7 h 37 · 16/10 +4 h 03 · 17/10 +1 h 56 · 18/10 +1 h 39 · 19/10 +7 h 43
20/10 +3 h 41 · 21/10 +8 h 50 · 22/10 +4 h 23 · 23/10 +4 h 21 · 24/10 +0 h 02
25/10 +0 h 01 · 26/10 +0 h 02 · 27/10 ⛔ +10 h 09
```

⛔ **La série de trois matins nets est rompue, et par le plus gros retard du
mois** (le précédent record était +8 h 50 le 21/10). Les trois matins propres
des 24, 25 et 26/10 n'étaient donc **pas** une correction : la note du 26/10
écrivait « trois ne font pas encore une correction définitive » — **c'est
vérifié, et dans le mauvais sens**.
ⓘ **Le trou est côté planification, pas côté VPS.** Le VPS est parfaitement à
l'heure : notation à 04:58:41 CET, contrôle à 07:30:21 CET, timer suivant armé
pour le **28/10 à 07:30:20 CET**. Rien dans le relevé de la nuit ne dépend de
l'heure à laquelle cette routine lit — mais un verdict rendu à 18 h 19 au lieu
de 8 h 09 arrive **dix heures** après le fait, et une nuit en échec aurait
attendu autant.
❓ **À regarder, Yann** : c'est la deuxième fois en sept jours qu'un retard
dépasse huit heures.

## 12. Décisions en attente de Yann — la liste à jour

0. ❓ **NOUVEAU et prioritaire : qui a retiré 1 125 Mo et 156 objets de
   `agrume/grille` cette nuit ?** (§3.1) C'est ce qui fait repasser le compte R2
   sous le palier gratuit. Aucun commit, pas cette routine. Tant qu'on ne sait
   pas, **le gain n'est pas acquis**.
1. ⛔ **Deux miroirs git en souffrance** : celui du **24/10** (jamais déposé) et
   celui du **26/10** (présent mais tronqué au §13 et **non suivi par git**).
   Rien fabriqué après coup. ⇒ **Le miroir du 26/10 est réparable sans rien
   inventer** : le document projet est complet, il suffit de recopier ses §14 à
   §16. Dis-moi si tu veux que je le fasse.
2. ⛔ **Les DEUX correctifs de lecture de la purge** (§2.3), inchangés :
   (a) `bilan_purge` et le suffixe « des lignes RESTENT » ; (b)
   `registre_nuit._INCIDENT` et la ligne de sonde. **Il faut les deux.**
3. ⬇️ **`diagnostic_base_sous_tension_2026-09-29.sql`** — **29ᵉ jour** sans être
   joué. Son urgence **redescend encore** : deuxième nuit d'affilée où la purge
   aboutit, et cette fois sans le moindre avertissement. Lecture seule, 9 blocs,
   SQL Editor.
4. ⬇️ **Le `select as_of, count(*)`** sur `model_score_zone` : son intérêt
   redescend d'un cran (§2.1), mais il reste la seule façon de **prouver** que
   le 2026-10-17 est parti. **Aucun SQL joué sans ton accord.**
5. ⛔ **R2 : rétention sur `agrume/pi`** — **+48 objets chaque nuit, quatorze
   nuits d'affilée, sans un seul recul.** ⚠️ Et surtout : **le répit sur le
   palier ne change rien à ce dossier.** Le total a perdu 1 191 Mo et
   l'accumulation n'a pas bougé d'un objet (§3.1).
6. ⛔ **Inventaire des 3 718 objets de `agrume/pi` que l'index ne réclame pas**
   (sur 3 765). À faire **avant** toute rétention — et le répit sur le palier le
   rend plus facile, pas moins nécessaire.
7. ⛔ **Mémoire : la ligne en tuple** (≈ −1 030 o/ligne, ≈ −2 027 Mo). **36ᵉ jour
   sans rien de déployé** depuis `af25efb`. Seule porte de sortie de KAN-4 : le
   jalon est à **+599 Mo** du seuil.
8. ⛔ **Pente d'`audit_r2.py`** : borner à zéro les pentes négatives des préfixes
   à fenêtre glissante (§3.2). Une ligne, mais c'est une **écriture**.
9. ⬇️ **Jalons de temps dans le bloc hors étapes de `run.sh`** — **redescend** de
   « utile » à « utile sans urgence » (§5.1). L'argument restant : ce bloc n'est
   pas instrumenté, et deux écarts de 300 s en deux nuits restent inexpliqués.
10. ⛔ **Motif `bw-r2-palier`** — non créé, et ⬇️ son urgence tombe (§3).
11. ⛔ **Les 3 cas de position confirmés** (§7) : trancher, puis
    `position_suspecte` + `position_note` par `.sql`. ⚠️ Et **`pioupiou:1378`** :
    341 km, bloquée à 9 j **cinq jours de suite** parce qu'elle clignote — elle
    ne se confirmera jamais seule. ⓘ Les onze balises à 6 j atteindraient 10 j
    le **31/10**.
12. ⓘ **Fermeture de KAN-5** : compteur **1 / 3**, possible au plus tôt le
    **29/10**, et seulement avec ton accord. Sous-question du 26/10 (la sonde
    compte-t-elle ?) sans objet cette nuit, mais toujours ouverte.
13. ⓘ **Réouverture de KAN-3** : **mon avis est NON**, et plus franchement
    qu'hier — durée au plus bas des douze nuits, marge 41,6 %, solde des cinq
    nuits −514 s, et la seule réserve qui restait est démentie.
14. ❓ **`bw-melange-sans-gain`** : la question d'hier **ne se confirme pas**
    (§6). Mon avis : **ne pas créer le motif**. À toi de refermer ou de garder.
15. ⚠️ **`installer-webhook-discord.sh`** (sur le Mac) — **46ᵉ jour**, variable
    absente.
16. ⓘ **Le cri de position doit-il recrier** à état constant ? (ouvert depuis le
    01/10 ; « à front » vérifié **huit** jours de suite — §7)
17. ❓ **NOUVEAU : l'horaire de la routine** (§11) — +10 h 09 ce matin, deuxième
    retard de plus de huit heures en sept jours.
18. ⓘ **`bw-model-oracle.service`** en `failed` — hors mission, non examiné.
19. ⓘ **`b9100c0`** (disjoncteur du poller Infoclimat) — ton commit, non examiné,
    noté pour mémoire.

## 13. Ce que ce run a DÉMENTI, et ce qu'il a CONFIRMÉ, de la note du 26/10

| annoncé le 26/10 | relevé le 27/10 |
|---|---|
| ⛔ compteur KAN-5 à **0 / 3** (57014 de la sonde) | ✅ **1 / 3** : nuit propre pleine, sonde comprise |
| ⛔ défaut (b) : la sonde n'arrive jamais au contrôle | ⓘ **non sollicité** : aucune sonde en défaut. Le défaut reste **entier** (c'est une lecture de code, pas une pente) |
| ✅ purge aboutie, 16 tranches, retard du 2026-10-17 repris | ✅ **cohérent** : retour à 8 tranches et 141 051 lignes, fourchette normale — **sans preuve**, le SQL n'a pas été joué |
| ✅ jalon **plancher** à 3 151 Mo | ⚠️ **effacé en 24 h** : 3 399 Mo (+248). Le refus d'y lire une baisse de fond est **validé** |
| ⚠️ « un plancher n'est pas une pente — à revérifier demain » | ✅ **refus VALIDÉ en 24 h**, pour la deuxième fois en deux jours |
| ⚠️ réserve sur l'estimateur de pente | ✅ **validée une CINQUIÈME fois** : −188 Mo/nuit deux matins de suite, pour −301 puis +248 Mo |
| ✅ durée −119 s, pas de deuxième hausse | ✅ **−405 s de plus** : plus basse des douze nuits, marge 41,63 % |
| ⚠️ bloc hors étapes : 3 nuits > 2 150 s, 4 des 6 premières places, demande remontée à ⬆️ « utile » | ⛔ **DÉMENTI** : 1 874,3 s, **45ᵉ sur 68**, sous la médiane. La demande **redescend** à « utile sans urgence » |
| ⓘ critère `regime` à 0 / 2 | ✅ **reste 0 / 2** : −2,0 %, point le plus bas de la série |
| ⛔ témoins du mélange : **2ᵉ** point négatif, « la série vient de confirmer », question posée à Yann | ⛔ **NE SE CONFIRME PAS** : **+5,2 %**, le meilleur point de la série, « devant » à 50,3 %. Avis : ne pas créer le motif |
| ⛔ l'excuse « journée calme » déclarée tombée | ⛔ **elle tombe dans l'AUTRE sens aussi** : journée la plus calme des trois (3,37 km/h) **et** meilleur gain ⇒ explication abandonnée |
| ⛔ `bw-garde-fou-r2.service` en échec, **11ᵉ** fois, « pas une panne » | ✅ **VÉRIFIÉ** : palier plus dépassé ⇒ `OK en 5s`, code **0**. La démonstration du 21/10 est confirmée par la sortie du cas |
| ⛔ total R2 10,312 Go, dépassé de 312 Mo | ✅ **9,121 Go (91,2 %)** — mais ⛔ **auteur inconnu** du retrait sur `agrume/grille` |
| ⛔ `agrume/pi` **13ᵉ** nuit à +48 | ⛔ **14ᵉ nuit à +48**, et le total perd 1 191 Mo ⇒ **8ᵉ vérification** du §7.1 du 24/10 |
| ✅ `agrume/grille` : à-coup tranché, retour exact à 5,323 Go / 766 obj | ⛔ **la question se rouvre, autrement** : −1 125 Mo / −156 obj, index à 610/610 |
| ✅ « à front, pas à état », 7ᵉ vérification (sur un départ) | ✅ **8ᵉ vérification** : liste identique ⇒ aucun cri, aucun push |
| ⚠️ `pioupiou:1378` bloquée à 9 j, 4ᵉ jour | ⚠️ **5ᵉ jour**, écart inchangé à 340 941 m |
| ⓘ onze balises à 5 j, 10 j le 31/10 | ✅ **toutes à 6 j**, échéance **31/10** confirmée |
| ⚠️ témoin du corrigé « oscille » (27,1 pt) | ✅ **confirmé, et largement** : 17,9 pt (−9,2) |
| ⚠️ écarts du recalcul : 5, dont 4 en `0 h` | ⚠️ **4, dont 4 sur 4 en `0 h`** — 14 sur 16 en trois nuits : le `0 h` s'installe |
| ✅ trois matins à l'heure, « trois ne font pas une correction » | ⛔ **VÉRIFIÉ, dans le mauvais sens** : **+10 h 09**, pire retard du mois |
| ⛔ miroirs git du 24/10 et du 26/10 en souffrance | ⛔ **inchangé**, vérifié et non arrangé |

⚠️ **« Une nuit ne fait pas une pente » — onzième fois en dix-huit jours.**
Appliqué ce matin à : la hausse du jalon (§4), la hausse du coût par ligne
rejouée (§1), la baisse de la durée (§5.2), la baisse du coût par ligne de
`regime` (§1), la baisse du total R2 (§3.1), le bond du témoin du mélange (§6),
la chute du témoin du corrigé (§9) et le recul des volumes (§9). **Aucun des
huit n'est présenté comme une tendance.** La tentation du jour était l'inverse
de celle d'hier : hier presque tout s'améliorait, aujourd'hui presque tout se
retourne — et dans les deux cas une nuit ne dit rien.

⛔ **Et deux fois, ce matin, la leçon ne s'applique PAS.** Le défaut (b) de la
sonde est une **lecture de code**, vraie indépendamment du nombre de nuits. Et
le retrait sur `agrume/grille` n'est pas une tendance à confirmer : c'est un
**événement** dont il faut connaître l'auteur.

## 14. Respect des règles

✅ **VPS en LECTURE SEULE, pleine et entière** (la levée nominative du 07/10 ne
valait que pour cette session-là). Aucun `systemctl` start/restart/
daemon-reload, aucun `enable`, **aucun SQL joué**, aucun rsync, rien écrit dans
`~/balise-watch` ni dans `/etc`. **Aucune redirection vers `/tmp` du VPS** :
toutes les sorties sont allées dans des fichiers du **Mac** et relues avec
`read_file`. ⓘ Seules exceptions, qui sont le fonctionnement normal du code de
production : `bw_jira_http` écrit sa réponse dans un `mktemp -d` du VPS, et le
`controle_quotidien.py --verbeux` relancé à la main ne fait que lire.
✅ **Aucun secret lu par valeur** : `.balise-watch-alertes.env` **sourcé**
(`set -a; . … ; set +a`) ; `BW_DISCORD_WEBHOOK_URL` cherchée **par son nom seul**
(`grep -c`) ; le jeton Jira passe par `curl -K -`, jamais `-u`.
✅ `10-timeout-s3.conf` **non touché** ; remontée du garde **non lancée**, et
seulement **décrite** dans le commentaire KAN-3, pas demandée au système.
✅ `controle_quotidien.sh` **non touché**, son `$ETAT` conservé. Les deux
correctifs du §2.3 sont **proposés**, pas écrits.
✅ **Aucun ticket créé, fermé, rouvert ni transité.** Trois commentaires, tous
par `bw_jira_commenter`, tous vérifiés par un GET **avant** et **après**.
✅ **Desktop Commander exclusivement** pour fichiers et shell.
✅ **Lire avant d'écrire** : `project_read` du 27/10 (absent ⇒ création) et du
26/10 (lu en entier) ; `git log --since=midnight` dans les deux dépôts ;
`notes-projet/README.md` relu ; GET Jira avant **et** après chaque écriture.
⛔ **Aucun `git push`.** Commit **local** du miroir, depuis la **racine** du
dépôt serveur.
ⓘ **Rien fabriqué pour combler les miroirs manquants** (24/10, 26/10) : ils sont
signalés tels quels au §12.

## 15. ⓘ Outillage — les trois pièges connus, tous confirmés

1. ✅ **`SSH_AUTH_SOCK` manquant** (piège n°1) : confirmé une quatrième fois, et
   le correctif marche du premier coup.

   ```
   export SSH_AUTH_SOCK="$(launchctl getenv SSH_AUTH_SOCK)"
   ```

   Dans un **process persistant** (`start_process "bash -l"` +
   `interact_with_process`), `ssh-add -l` voit ensuite
   `balise-watch-vps (ED25519)`.
2. ✅ **Le lecteur de flux qui perd des lignes** (piège n°2) : contourné
   d'emblée, et il a bien perdu une ligne (le `git log -1` de `b9100c0`).
   **Toute sortie dont une ligne compte est redirigée vers un fichier du Mac et
   relue avec `read_file`.**
3. ✅ **« did not respond within 60s » alors que la commande aboutit** (piège
   n°3) : confirmé, et c'est arrivé à **presque tous** les appels, y compris
   celui qui postait les **trois** commentaires Jira. ⛔ **Jamais relancé.** ✅
   La bonne réaction : lire le fichier de sortie. Les trois commentaires sont
   partis **une seule fois chacun**, vérifié par le compte avant/après
   (32→33, 46→47, 29→30).
4. ⓘ **Nouveau, mineur** : pour poster du texte français dans Jira sans se
   battre avec les apostrophes et la liste noire du shell, le texte est écrit
   dans un fichier du Mac avec l'outil d'écriture, encodé en **base64** dans un
   script local, et le script est passé par `ssh … 'bash -s' < payload.sh`.
   Aucun guillemet à échapper, aucune apostrophe mutilée, et rien d'écrit sur le
   VPS.
5. ⚠️ **Le pont vers le Mac n'a PAS coupé** cette fois (contre deux coupures le
   26/10). La note est complète ici **et** dans le projet.
