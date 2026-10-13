# Verdict de pente du 13/10/2026 — **la nuit où les trois records d'hier tombent tous les trois**. Jalon **3 422 Mo (−22)**, coût par ligne **1 719,7 o (−10,5)**, swap **2 091,8 Mo (−503,5)** de retour dans la bande de douze nuits. « Le score par régime » **repasse sous le seuil** : deux incidents mémoire au lieu de trois. ⛔ Mais le coût par ligne de `regime` fait sa **deuxième hausse consécutive** : le critère `bw-regime-sensibilite` est **REMPLI** — question posée à Yann, rien créé. ✅ Purge propre pour la **sixième fois (6 / 3)**.

## 10:04 (Paris) — routine Balise Watch (tirée à 08:03:24 UTC pour 07:11:05 : **+52 min**, contre +10 h 59 hier), lecture VPS complète, **trois écritures Jira**

**Étape 0 faite.** `git log --oneline --since=midnight` :

- dépôt serveur `PWA/balise-watch-server` : **aucun commit du jour**
- dépôt principal `surveillance balise` : **aucun commit du jour**
- `claude/verdict-pente-13-10.md` **absent** de la liste d'ouverture de session
- `claude/verdict-pente-12-10.md` lu **en entier**
- `notes-projet/README.md` relu — les quatre règles

⇒ **premier et seul run pente du jour. Rien à fusionner, aucun doublon.**

## 1. Les nuits, bout à bout

| | 08/10 | 09/10 | 10/10 | 11/10 | 12/10 | 13/10 |
|---|---|---|---|---|---|---|
| durée | 5 228 s | 5 192 s | 5 318 s | 4 975 s | 5 029 s | **5 046 s (+17)** |
| marge | 2 872 | 2 908 | 2 782 | 3 125 | 3 071 | **3 054 (−17)** |
| marge en % du garde | 35,46 % | 35,90 % | 34,35 % | 38,58 % | 37,91 % | **37,70 %** |
| `cpu_s` | 4 257,9 | 4 199,5 | 4 237,7 | 4 019,1 | 4 021,9 | **4 056,7 (+34,8)** |
| jalon max | 3 429 Mo | 3 356 | 3 394 | 3 321 | **3 444 (record)** | **3 422 (−22)** |
| au-dessus du seuil | +629 | +556 | +594 | +521 | +644 | **+622** |
| swap au pic | 2 267,1 | 2 145,1 | 2 088,1 | 2 129,5 | **2 595,3 (record)** | **2 091,8 (−503,5)** |
| pages sorties | 2 556 336 | 2 241 569 | 2 487 135 | 2 501 165 | 2 514 657 | **2 171 262 (−343 395)** |
| pic système | 3 602,9 | 3 615,2 | 3 608,5 | 3 619,9 | 3 616,1 | **3 595,4 (−20,7)** |
| fenêtre rejouée | 2 089 691 | 2 089 138 | 2 088 809 | 2 087 981 | 2 087 197 | **2 086 539 (−658)** |
| o / ligne rejouée | 1 720,6 | 1 684,4 | 1 703,8 | 1 667,8 | **1 730,2 (record)** | **1 719,7 (−10,5)** |
| incidents mémoire | 3 | 3 | 3 | 3 | 3 | **2** |
| `n_57014` | 0 | 0 | 1 (hors purge) | 0 | 0 | **0** |
| lancement / résultat | timer/success | ↳ | ↳ | ↳ | ↳ | **timer/success** |

Nuit **comparable** : `lancement=timer`, `exec_status=0`, `oom=0`,
`result=success`, **05:55:06 → 07:19:22**, `source=run.sh`,
`chevauchement_reduit=true`. Rien à écarter.
ⓘ Le départ glisse encore : 06:00:06 → 05:57:06 → **05:55:06**
(`bw-model-score.timer` tiré mardi à 05:55:05, prochain mercredi
**05:59:42** — il remonte). **Rien d'anormal.**

**Le contrôle de 07:30 a tiré à 07:30:46 et s'est TU** :

```
ⓘ 75 relevé(s), 54 comparable(s) ; durée : 10 points, pente -36 s/nuit ;
  mémoire : 10 points, pente -53 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate/négative, ou échéance hors horizon
```

⚠️ **QUATRIÈME MATIN DE SUITE À EXACTEMENT −53 Mo/nuit** — les 10, 11, 12 et
13/10, dont le record absolu d'hier. La pente de durée, elle, bouge enfin
(−55 → **−36 s/nuit**) après trois matins identiques. **Le 25e centile des
différences reste aveugle** : il ignore par construction les deux plus grosses
hausses de la fenêtre.

⇒ **Aucun jeton du jour posé par le contrôle.** Vérifié dans les **deux**
dossiers avant écriture : `/var/lib/bw-model-verif` portait
`cri.jira.bw-pente-duree` du 17/09, `…memoire` du 23/09, `…purge-57014` du
06/10 ; `$HOME/.balise-watch-etat-alertes` portait `duree` du 07/10 et les deux
autres du **12/10**. **`bw_jira_signaler` était donc libre sur les trois motifs.**

## 2. ✅ Mémoire : **les trois records d'hier sont démentis en une nuit**

```
⛔ après le rejeu d'archive            : 3 021 Mo  (3 024 le 12/10)  ← −3
✅ après le score par régime           : 2 738 Mo  (2 830 le 12/10)  ← −92, SOUS LE SEUIL
⛔ après l'oubli de la fenêtre rejouée : 3 422 Mo  (3 444 le 12/10)  ← −22
```

✅ **DEUX INCIDENTS AU LIEU DE TROIS.** « Le score par régime » **repasse sous
le seuil de 2 800 Mo** après deux nuits au-dessus. C'est la première fois depuis
le 10/10 que le registre ne porte que deux `incidents`.

Le jalon max reste le **deuxième plus haut de toute la série** (record 3 444 Mo
hier) : le repli n'est que de 22 Mo, **on reste très haut**.

⚠️ **LA CONCENTRATION SUR UN SEUL JALON NE SE REPRODUIT PAS.** Hier huit des
neuf jalons reculaient et seul l'oubli de la fenêtre rejouée montait ; la note
du 12/10 en faisait un indice en faveur de la ligne en tuple, **avec la réserve
explicite « c'est une nuit »**. Cette nuit : quatre montent, cinq reculent —
agrégat quotidien **1 836 (+13)**, oubli fenêtre glissante **1 739 (+3)**, oubli
du chemin J-0 **971 (+13)**, relecture de l'archive **817 (−8)**, garde-fou de
position **1 202 (−7)**, mélange multi-modèle **1 192 (−5)**. ⇒ **la lecture
d'hier est DÉMENTIE**, exactement comme celle du 10/10 l'avait été.

**COÛT PAR LIGNE REJOUÉE : 1 719,7 o (−10,5).**

```
29/09 1 671,3 o · 30/09 1 692,6 · 01/10 1 685,6 · 02/10 1 689,2
03/10 1 706,4  · 04/10 1 697,4 · 05/10 1 717,2 · 06/10 1 689,7
07/10 1 717,0  · 08/10 1 720,6 · 09/10 1 684,4 · 10/10 1 703,8
11/10 1 667,8  · 12/10 1 730,2 · 13/10 **1 719,7**
  → fourchette 1 667,8–1 730,2 sur QUINZE nuits (±1,9 % autour de 1 699)
```

⛔ **CORRECTION EXPLICITE DE LA NOTE DU 12/10.** Elle posait la question n° 1 du
dossier : « 1 730,2 o/ligne confirme-t-il, ou était-ce le symétrique du 1 667,8
d'hier ? » **Réponse : c'était le symétrique.** Le record haut n'a pas tenu une
nuit, exactement comme le record bas de l'avant-veille. ⇒ **Dixième usage en
seize jours de la leçon « une nuit ne fait pas une pente » — et deux notes
consécutives y passent.** Toujours **aucune pente**, ni à la hausse ni à la
baisse, sur quinze nuits.

**Calcul à taux constant.** Au taux du **12/10** (1 730,2 o) la fenêtre de cette
nuit aurait rendu **3 442,9 Mo** ; elle rend **3 422**. Les **−20,9 Mo** sont
imputables au **coût par ligne** ; la fenêtre ne recule que de **658 lignes**
(**−1,0 Mo**). Au taux du **29/09** (1 671,3 o) : **3 325,7 Mo** — nous sommes
**96 Mo au-dessus**.

✅ **SWAP : LA BANDE DE DOUZE NUITS EST RETROUVÉE.** Pic **2 091,8 Mo
(−503,5, soit −19,4 %)**, de retour dans la bande **2,0–2,3 Go** tenue du 30/09
au 11/10. ⇒ **le pic de 2 595,3 Mo du 12/10 était UN POINT, pas un étage** — la
seconde question du 12/10 est tranchée, et dans le bon sens. Pages sorties
**2 171 262 (−343 395, soit −13,7 %)**, le plus bas depuis le 09/10. ⓘ **Les
deux indicateurs vont cette fois dans le MÊME SENS**, après avoir fortement
divergé hier. `oom = 0`, pic système **3 595,4 Mo (−20,7)**, le plus bas de la
série récente.

**Les trois conditions de fermeture de KAN-4 : 1 sur 3**, inchangé. Jalon
mesurément retombé → **NON** (2e plus haut de la série, +622 au-dessus du
seuil). Swap au pic ≈ 0 → **NON** (2 091,8 Mo). Contrôle muet sur
`bw-pente-memoire` → **OUI**. ⇒ **le ticket reste ouvert.**

**Rien de déployé côté mémoire depuis `af25efb` (21/09) — 23e nuit sans
levier.** Remède inchangé : la **ligne en tuple** (`enquete-pente-10-09.md`
§2.6, ≈ −1 030 o/ligne), après la mesure `tuple` vs `namedtuple` à la sonde.
⚠️ **Quinze nuits sans pente disent ce qu'il faut attendre du dossier** : ce
n'est pas une dérive qui monte, c'est un **plafond qu'il faut baisser**. Les
gains sont dans la **structure** (l'élagage de `units` avait rendu −124 Mo au
lieu de −1 500).

## 3. ⛔ Durée : +17 s, et la signature s'inverse **deux fois** par rapport à hier

```
durée  5 029 → 5 046 s  (+17)
marge  3 071 → 3 054 s  (−17)  ⇒ 37,91 % → 37,70 % du garde de 8 100 s
cpu_s  4 021,9 → 4 056,7 (+34,8)
```

⚠️ **C'EST DU CALCUL.** Le processeur rend **+34,8 s** pour **+17 s** d'horloge :
il monte **deux fois plus** que la durée, donc il y a même **un peu moins
d'attente** qu'hier. ⛔ Hier c'était l'**inverse exact** (cpu +2,8 s pour +54 s
d'horloge, 95 % d'attente). **Deux nuits consécutives, deux signatures
opposées.**

Série : `5 227 · 5 228 · 5 192 · 5 318 · 4 975 · 5 029 · **5 046**`. La durée
**oscille** dans une bande de 4 821 à 5 318 s depuis neuf nuits (**±5 %**) : ni
plateau, ni dérive, ni repli.

| étape | 10/10 | 11/10 | 12/10 | 13/10 |
|---|---|---|---|---|
| `regime` | 1 809,1 | 1 648,5 | 1 664,7 | **1 680,6 (+15,9)** |
| `glissant` | 964,4 | 974,1 | 958,0 | **988,4 (+30,4)** |
| `stabilite` | 358,7 | 312,0 | 309,0 | **309,4 (+0,4)** |
| `rejeu` | 85,6 | 73,4 | 81,5 | **78,6 (−2,9)** |
| somme des quatre | 3 217,8 | 3 008,0 | 3 013,2 | **3 057,0 (+43,8)** |
| hors étapes | 2 100,2 | 1 967,0 | 2 015,8 | **1 989,0 (−26,8)** |

⚠️ **ET LA HAUSSE EST DANS LES ÉTAPES — second renversement.** Les quatre étapes
instrumentées prennent **+43,8 s** quand l'horloge n'en prend que **+17** : le
hors-étapes **restitue 26,8 s**. Hier **90 % du mouvement était hors étapes** ;
cette nuit il est **entièrement dans les étapes**, et le poste qui bouge le plus
est **`glissant` (+30,4 s)**, devant `regime` (+15,9).

**Hors étapes :**

```
1 924,7 (06/10) · 1 984,0 · 1 991,2 · 2 051,6 · 2 100,2 (10/10) · 1 967,0 · 2 015,8 · 1 989,0 (13/10)
```

Il avait monté **quatre nuits sans un repli** (+175,5 s), rendu 133,2 s, repris
48,8, et rend maintenant **26,8**. ⇒ **la série monotone reste cassée** : le
hors-étapes **oscille comme le reste**. Il demeure le poste le plus volatil, et
⛔ **le bloc n'est toujours pas instrumenté** — publication, Murphy, événements,
pression, duels, purge : six postes, **aucun jalon de temps**. La demande
d'instrumentation de `run.sh` reste ouverte (c'est une **écriture**, elle attend
Yann).

### ⛔ 3.1 `bw-regime-sensibilite` : **LE CRITÈRE EST REMPLI (2 / 2)**

Coût par ligne de `regime` (ms) :

```
13,39 (01/10) · 13,24 · 14,02 · 13,67 · 13,53 · 15,07 · 14,86 · 14,87
· 13,99 · 14,42 · 12,94 (11/10) · 13,02 (12/10) · **13,14 (13/10)**
                                    +0,08          +0,12
```

L'**arbitrage unique du 07/10** pose le critère comme **deux hausses
consécutives** du coût par ligne de `regime` (et non un niveau absolu). Le
compteur était à **1 / 2** hier ; il est à **2 / 2** ce matin. ⇒ **LE CRITÈRE
EST REMPLI.**

⛔ **Conformément à l'arbitrage, RIEN N'A ÉTÉ CRÉÉ : la question est posée à
Yann.** Les deux éléments à mettre en balance, tels qu'ils ont été portés au
commentaire de KAN-3 :

- **POUR** : deux hausses consécutives, c'est **exactement** le critère, et il a
  été choisi pour se déclencher sans discussion.
- **CONTRE** : **le niveau est bas.** 13,14 ms est le **troisième plus bas des
  treize relevés**, très loin du 15,07 du 06/10 qui avait motivé le critère. Les
  deux hausses cumulées font **+0,20 ms (+1,5 %)** après un recul de −1,48 ms
  (−10,3 %) le 11/10 ; en valeur nous sommes encore **1,28 ms SOUS** le niveau
  du 09/10.

⇒ **Le critère est rempli à la lettre ; l'ampleur ne ressemble pas à ce qu'il
visait.** C'est la décision de Yann — et c'est peut-être aussi le signe que le
critère mérite un plancher de niveau, pas seulement une direction.

**Coût par ligne de `glissant` : 94,28 ms** (91,15 le 12/10, **+3,13**), pour un
volume en **légère baisse** (10 484 lignes, −26) : sur `glissant`, temps et
volume sont **découplés** cette nuit.

**Ailleurs aussi** : `lignes_regime` **127 905 (+52, soit +0,04 %)** pour un
temps de `regime` à **+1,0 %** — le volume n'explique pas davantage la hausse de
`regime`. `lignes_score_zone` **138 389 (+26)**, `lignes_daily` **69 550 (+172)**,
`lignes_glissant` **10 484 (−26)**.

**Remontée du garde : NON lancée, NON demandée.** Le contrôle n'en propose
aucune (pente négative, `proposition()` n'est pas atteinte). Garde actuel
**8 100 s (135 min)** pour un run de **84,1 min**. ⛔ `10-timeout-s3.conf`
**n'a pas été touché.**

**KAN-3 : réouverture NON demandée.** +17 s, marge encore à 37,70 %, durée dans
sa bande depuis neuf nuits, série monotone du hors-étapes toujours cassée.

## 4. ✅ Purge : **SIXIÈME nuit propre d'affilée — KAN-5 est à 6 / 3**

```
→ purge model_score_zone : 132 089 ligne(s) effacée(s) en 8 tranche(s)
ⓘ purge model_character : rien avant le 2027-02-04 (première écriture
  2026-08-08, rétention 180 j) — aucune requête lancée.
```

Le bloc ne porte **aucun avertissement au-dessus de ces deux lignes** :

- **aucune TRANCHE à 57014** (aucun `?as_of=eq.J&regime=eq.R` en HTTP 500)
- **aucune SONDE** (« plus vieille journée illisible » absente)
- **aucun « des lignes RESTENT »** — donc rien ne reste en base
- nombre de lignes **lisible** (132 089), **8 tranches** comme les cinq nuits
  précédentes
- `n_57014 = 0` au registre, et **aucun 57014 nulle part** dans le journal

| nuit | état du bloc purge | compteur |
|---|---|---|
| 07→08 (2026-10-08) | `n_57014 = 0`, propre | 1 |
| 08→09 (2026-10-09) | propre, 129 650 l. / 8 tr. | 2 |
| 09→10 (2026-10-10) | propre, 129 594 l. / 8 tr. | 3 |
| 10→11 (2026-10-11) | propre, 129 233 l. / 8 tr. | 4 |
| 11→12 (2026-10-12) | propre, 129 534 l. / 8 tr. | 5 |
| 12→13 (2026-10-13) | **propre, 132 089 l. / 8 tr.** | **6** |

⇒ ⛔ **LA CONDITION DE FERMETURE EST DÉPASSÉE : 6 / 3.** Elle n'est **pas**
appliquée : la fermeture se décide avec Yann. **C'est la question posée pour le
QUATRIÈME jour de suite.**
ⓘ Les **2 555 lignes** d'écart avec hier **ne sont pas un signal** : le volume
effacé suit le volume de la journée purgée (≈ 125 000–134 000). 132 089 est dans
la bande, en haut.

✅ **`bw_character_avance` est passé proprement** : **403 403 accumulateurs
avancés sur 403 403 envoyés**, sans reprise. Le 57014 apparu là le 10/10 est
absent pour la **troisième** nuit.

⚠️ **Les deux réserves sont inchangées et toujours valides.** (1) Le `statement
timeout` **change de requête** plutôt que de disparaître — le 10/10 l'a montré,
et trois nuits sans lui ne démontrent rien (il y en avait eu trois d'affilée les
03, 04, 05/10 avant le retour du 06). (2)
**`diagnostic_base_sous_tension_2026-09-29.sql`** (lecture seule, 9 blocs, SQL
Editor) **n'a jamais été joué : QUATORZE JOURS.**
⇒ ⚠️ **Si KAN-5 est fermé, il ferme « la purge par tranches expire », pas « la
base est sous tension ». Le second motif n'a toujours pas de ticket.**

✅ Le contrôle s'est tu sur ce motif, et c'est **correct** : depuis le 07/10,
`constats()` lit `score.log` via `bilan_purge()`. Le faux « purge en échec » du
06/10 ne s'est pas reproduit : **septième nuit.**

## 5. ⛔ Position : **mêmes 3 confirmées, pas de cri** — mais les sept sont à **8 j** : échéance **le 15/10, dans DEUX JOURS**

```
⛔ position : 11 balise(s) divergent du gel (10 j lus), dont 3 CONFIRMÉE(S) (≥ 10 j)
   ⛔ pioupiou:2171          38 925 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE · Windbird 2171
   ⛔ pioupiou:1388           2 363 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE · Décollage Serre Michèle
   ⛔ infoclimat:STATIC0491   1 159 m · 10 j · nœud 0,01 CHANGE · infoclimat STATIC0491
   ·  1378 (15 778 m) · 367 (6 764) · 1417 (829) · 1375 (747) · 1722 (631) · 1562 (481) · 1678 (422) — toutes à 8 j
   ·  pioupiou:1333          87 693 m ·  5 j  ← continue de reculer (10 → 8 → 7 → 6 → 5)
```

ⓘ **Le compte des confirmées est inchangé (3) ⇒ pas de front ⇒ pas de cri** —
cohérent avec l'arbitrage « à front, pas à état ». Aucun `push` nulle part dans
le journal : il n'y avait rien à crier.

⛔ **LES SEPT BALISES SONT À 8 j : elles franchiront 10 j LE 15/10.** La
progression est régulière (5 → 6 → 7 → **8 j**) et l'échéance annoncée les 09,
10, 11 et 12/10 **tient toujours**. Ce jour-là le compte passerait de **3 à 10**,
donc **un cri à front**. ⇒ **IL RESTE DEUX JOURS.**
**Geste attendu de Yann** : trancher `2171` (38,9 km), `1388` (2 363 m),
`STATIC0491` (1 159 m), statuer sur `1333` qui **sort du lot** (10 → 8 → 7 → 6 →
**5 j**), puis poser `position_suspecte` + `position_note` sur `station_zone` par
`.sql`.
ⓘ Question toujours ouverte depuis le 01/10 : **faut-il que le cri recrie** pour
une balise qui reste confirmée ?

## 6. ⚠️ Le second canal du téléphone reste muet

**`BW_DISCORD_WEBHOOK_URL` est TOUJOURS ABSENTE du `.env`.** 25 variables
relevées par leur **nom seul** (`sed -E "s/=.*//"`, aucune valeur lue), les
mêmes qu'hier. Fichier **inchangé depuis le 13/09 18:08**. ⇒ `bw_push_discord`
reste **codé, testé, muet**. `~/installer-webhook-discord.sh` attend toujours
Yann : **31e jour**.

ⓘ **Le correctif `--ipv4` du 07/10 n'a pas été sollicité cette nuit** (aucun ⛔
à front ⇒ aucun push). **Aucun 429 nulle part.** Trafic conforme à la normale.

## 7. ✅ Témoins du mélange : **deuxième nuit de remontée — la question est close**

```
⛔ témoins du mélange : sur 7 595 balise-jours×échéance, le mélange fait
   2,908 km/h contre 3,0 pour le meilleur membre a priori
   (gain 3,1 %, mélange devant dans 51,6 % des cas) ;
   contre la moyenne UNIFORME, sur 1 126 : 2,9529 vs 3,1569 (gain 6,5 %)
```

```
gain contre le MEILLEUR MEMBRE : 7,4 % → 5,5 → −0,6 (07/10) → +2,5 → −1,2 → −0,1 → −0,0 → +1,6 (12/10) → **+3,1 (13/10)**
« devant » dans : 49,2 % → 50,1 (09/10) → 49,1 → 49,2 → 50,1 → **51,6 %**
gain contre la moyenne UNIFORME : 6,0 % → 4,9 → 4,8 → 3,1 → 4,8 → 3,2 → 3,4 → 4,7 → **6,5 %**
```

✅ **Deuxième remontée consécutive, et la meilleure valeur depuis le 08/10** sur
les deux fronts : **+3,1 %** contre le meilleur membre (le plus haut depuis huit
nuits) et **6,5 %** contre la moyenne uniforme (**haut de la bande 3,1–6,5**). Le
mélange repasse devant dans **51,6 %** des cas. ⇒ **La note du 11/10 (« le
mélange n'apporte plus rien ») est définitivement démentie, et la décision du
12/10 de ne PAS créer de motif Jira est confirmée.** Rien n'a été créé.

ⓘ **L'erreur absolue chute encore de 12,4 %** (3,3197 → 2,908 km/h) : deuxième
journée **moins venteuse** d'affilée. ⚠️ **C'est la confirmation de la leçon du
12/10** : l'indicateur suit la **météo du jour** autant que la qualité du
mélange — il avait chuté sur une journée très venteuse (07/10), il remonte sur
deux journées calmes. **Toute lecture de cette série doit passer par l'erreur
absolue.**

ⓘ Composition : 7 974 balise×échéance avec poids sur 30 j de cache — +6 h :
2 642 `bw_mix`, 415 témoins uniformes, 193 sans poids ; +24 h : 2 562 / 392 /
94 ; +48 h : 2 546 / 415 / 267 (64,0 s).

## 8. Le reste du journal

- ✅ **Self-test du scoring : VERT** (lot S3, aucune lecture réelle, aucune
  écriture). Écart des deux mélanges : `mse_comb` 17,841 contre `mse_comb_vec`
  17,841 (**+0,00 %**).
- ⚠️ **Stabilité des rangs : τ = 0,735 sur 56 cases** (0,742 / 50 le 12/10 ;
  0,723 / 54 le 11/10 ; 0,709 / 53 le 10/10). τ **recule légèrement** mais
  l'échantillon **remonte à 56 cases** (60 → 57 → 53 → 54 → 50 → **56**). ⓘ La
  lecture d'hier (« τ monte pendant que l'échantillon maigrit ») **ne se
  reproduit pas** : les deux séries bougent en sens inverse d'une nuit sur
  l'autre. À suivre, pas à conclure.
- ⚠️ **ρ hors [0, 1] : 437 balises sur 3 708** (413 le 12/10, 381 le 11/10, 349
  le 10/10, 382 le 09/10, 307 le 08/10). ⛔ **NOUVEAU PLUS HAUT de la série, et
  quatrième hausse sur cinq nuits.** C'est la seule série du journal qui monte
  franchement et sans démenti : **+42 % depuis le 08/10**. Les quatre nuits
  d'amélioration de fin septembre restent perdues. ⓘ **C'est le candidat le plus
  net à un motif neuf** — mais cinq points ne font pas une pente non plus, et
  rien n'a été créé.
- ⚠️ **7 écarts au recalcul indépendant** (5 le 12/10, 6 le 11/10, 5 le 10/10)
  — journée recalculée **2026-10-12**. **Tous en `fcstagrume`** et tous de la
  **même signature** : « ici None, base X — 0 ou 1 h appariée ici (< 6) mais la
  base porte une ligne » : `aemet:9211F` (agrume_pi +48 h),
  `infoclimat:STATIC0238` (agrume_pi +24 h), `mf:12145001` (agrume +6 h),
  `pioupiou:1558` (agrume_pi +24 h), `windsmobi:ffvl-3657` (agrume_pi +6 h),
  `aemet:9838B` (agrume_pi +24 h), `infoclimat:STATIC0440` (agrume +48 h).
  ⓘ **Sixième nuit de suite la même signature** (4 · 5 · 5 · 6 · 5 · **7**) ; le
  compte remonte à son plus haut. Les balises concernées **changent chaque
  nuit** : ce n'est pas un lot fixe, c'est un **désaccord systématique sur le
  seuil des 6 heures appariées**.
- **Murphy** : 66 230 triplets, 64 244 décomposés, 266 balises tenues dehors
  (doublon ou position suspecte), 0,9 s.
- **Duels appariés** : lead 6 → 65 203 lignes depuis le 13/09 (944 retirées) ;
  lead 24 → 23 997 lignes (359 retirées). ⓘ Cumul tronqué par la rétention 30 j.
- **Événements** : **31 332 combinaisons publiables**, 29 353 écartées sous le
  quorum de 8.
- **Pression** : 17 894 lignes, 682 points de prévision portent `pmsl`,
  **859 appariées** (médiane 18,1 km) ; refusées : 207 hors rayon, 32 hors Δz,
  4 trop hautes.
- **Référence combinée** : **k médian 0,142** sur 3 708 balises / 3 820
  climatologisées (223,9 s de climatologie horaire).
- **Publication** : `model_scores.json` 121 194 Ko, `model_scores_light.json`
  7 300 Ko (532 Ko gzippé).
- **Accumulateurs** : 5 272 entrées écartées (`doublon_de`, lot L17), 314
  antérieures à la naissance de la balise (`notee_depuis`, lot L15-bis).
- **Rejeu d'archive** : 2 086 539 balise-jours sur 30 journées (0 rejouée cette
  nuit, 0 vide, 4 764 balise-jours écartés) en 78,6 s.
- **Observations** : 3 734 balises le jour, 3 721 la veille.
- **`mutations_memoire`** : ⚠️ **CINQUIÈME nuit sans aucune ligne au journal.**
  Le relevé « 3 mutations non vues (2, 5, 13) » ne peut pas être revérifié ;
  dette antérieure, **statut inchangé faute de mesure**.
- `✅ terminé (663 442 lignes écrites en base)` (701 789 le 12/10) ; `registre :
  1 ligne écrite (2026-10-13, 5 046 s, jalon max 3 422 Mo, swap 2 091,8 Mo)`.
- ⓘ `→ model_verif_collect_part : 3 ligne(s)`.

## 9. ✅ Les tickets : état vérifié par GET **avant** et **après**, trois commentaires

GET `/rest/api/3/issue/<clé>?fields=summary,status,comment` avant écriture,
HTTP 200 sur les trois. Les trois sujets sont **ceux relevés le 07/10**,
inchangés.

| ticket | statut | comm. avant | canal utilisé | comm. après |
|---|---|---|---|---|
| **KAN-3** `bw-pente-duree` | **Terminé** / `done` | 21 | `bw_jira_commenter KAN-3` (**délibéré**) | **22** ✅ |
| **KAN-4** `bw-pente-memoire` | **À faire** / `new` | 32 | `bw_jira_signaler bw-pente-memoire` | **33** ✅ |
| **KAN-5** `bw-purge-57014` | **À faire** / `new` | 15 | `bw_jira_signaler bw-purge-57014` | **16** ✅ |

**Ce que chaque commentaire porte :**

- **KAN-4** — jalon **3 422 Mo (−22)**, 2e plus haut de la série, +622 au-dessus
  du seuil ; **deux incidents au lieu de trois**, « le score par régime »
  repasse sous le seuil (2 738 Mo, −92) ; coût par ligne **1 719,7 o (−10,5)** et
  **démenti explicite du record haut d'hier** ; fourchette ±1,9 % sur quinze
  nuits ; calcul à taux constant (−20,9 Mo imputables au coût par ligne, −1,0 Mo
  à la fenêtre) ; **swap 2 091,8 Mo (−503,5), retour dans la bande de douze
  nuits** et les deux indicateurs qui **convergent** cette fois ; **la
  concentration sur un seul jalon qui ne se reproduit pas**, avec les neuf
  jalons chiffrés ; les trois conditions de fermeture **1 sur 3** ; 23e nuit
  sans levier et la ligne en tuple ; `mutations_memoire` non mesurable ; **le
  contrôle qui annonce −53 Mo/nuit pour la 4e fois de suite**.
- **KAN-5** — bloc purge **propre pour la 6e nuit** (132 089 l. / 8 tr., aucune
  tranche à 57014, aucune sonde, aucun « RESTENT ») ; le **compteur nuit par
  nuit, 6 / 3** ; `bw_character_avance` passé proprement (403 403 / 403 403) ;
  les **deux réserves** (le timeout change de requête, le `.sql` jamais joué —
  quatorze jours) ; **la fermeture posée à Yann, non appliquée** ; et le fait
  qu'elle ne fermerait que la purge, pas la base sous tension.
- **KAN-3** — durée **+17 s** (5 046 s, marge **37,70 %**) ; **c'est du calcul**
  (cpu +34,8 pour +17 d'horloge) **et c'est dans les étapes** (+43,8), **double
  inversion** par rapport à hier ; le tableau des quatre étapes et du
  hors-étapes ; la série monotone toujours cassée et le bloc **non
  instrumenté** ; ⛔ **le coût par ligne de `regime` à 13,14 ms = 2e hausse
  consécutive ⇒ critère `bw-regime-sensibilite` REMPLI**, avec **le POUR et le
  CONTRE** (le niveau est le 3e plus bas des treize relevés, +1,5 % cumulé,
  encore 1,28 ms sous le 09/10) et **la question posée, rien créé** ; le
  découplage temps/volume sur `glissant` et `regime` ; l'aveuglement du 25e
  centile et les −53 Mo/nuit quatre matins de suite ; remontée du garde **non
  lancée, non demandée** ; **réouverture non demandée**.

⛔ **Aucune création, aucune transition, aucune réouverture, aucune fermeture.**
Les trois statuts sont **identiques** après écriture (revérifiés par GET).

ⓘ **Les deux canaux ont été employés comme arbitré le 07/10.** Le contrôle
s'étant tu, les jetons du jour étaient **libres** : `bw_jira_signaler` a servi
pour les deux motifs ouverts et a **posé les jetons**
(`cri.jira.bw-pente-memoire` et `cri.jira.bw-purge-57014` datent maintenant du
**13/10 10:09**). `bw_jira_commenter` a servi pour KAN-3, en « Terminé » — un
`bw_jira_signaler` sur ce motif **aurait créé un ticket neuf**. ✅ Vérifié après
coup : `cri.jira.bw-pente-duree` est **toujours daté du 07/10** côté `$HOME` et
du **17/09** côté `/var/lib` — le canal délibéré ne touche pas le jeton du jour.

ⓘ **Technique de l'envoi** : les trois corps ont été écrits sur le **Mac**
(`/tmp/bw-13-10/`), encodés en base64 et passés au VPS **par l'entrée standard
de `ssh`**, décodés dans une variable shell. **Aucun fichier n'a été déposé sur
le VPS, pas même dans `/tmp`.**

## 10. Ce qui a été touché

**VPS — règle de LECTURE SEULE pleine et entière, respectée.** Huit commandes
`ssh`, toutes en lecture sauf les trois POST Jira : `date -u`, `tail -n 3` du
registre, `systemctl list-timers`, `journalctl` du contrôle, plusieurs passes de
`journalctl -u bw-model-score.service` avec `grep`/`sed`,
`controle_quotidien.py --verbeux`, `sed`/`grep` dans `bw_jira.sh`, `ls -la` des
deux dossiers d'état, `sed -E "s/=.*//"` sur le `.env`, et **six GET** Jira
(trois avant, trois après).
**Aucun `systemctl start/restart/daemon-reload`, aucun `enable`, aucun SQL joué,
aucun `rsync`, rien écrit dans `~/balise-watch` ni dans `/etc`.**
⚠️ `controle_quotidien.py --verbeux` a été **relancé à la main** : c'est une
lecture (il n'écrit son jeton que s'il parle, et il s'est tu) — vérifié, les
jetons de `/var/lib/bw-model-verif` sont **inchangés** après la relance.
**Aucun secret lu par valeur** : le `.env` est **sourcé** (`set -a; . …;
set +a`) pour les GET et lu **par noms de variables seuls**. `bw_jira.sh` passe
par `curl -K -`, jamais `-u`.
**Écritures Jira : trois commentaires** (voir §9).

**Mac** : trois corps de commentaire et trois petits scripts d'envoi dans
`/tmp/bw-13-10/` (fichiers de travail), cette note dans
`notes-projet/verdict-pente-13-10.md`. **Un commit local**, depuis la **racine
du dépôt serveur**. **Pas de `git push`.**

**Projet Claude** : cette note, **créée** (absente de la liste d'ouverture de
session).

## 11. ✅ L'horaire de la routine : **+52 min**, le meilleur depuis le 07/10

Programmée pour **07:11:05 UTC**, tirée à **08:03:24 UTC**.

```
02–03/10  AUCUN TIR
04–06/10  retard jusqu'à 4 h 10
07/10     à l'heure
08/10     +2 h 10
09/10     +6 h 40
10/10     +2 h 13
11/10     +5 h 51
12/10     +10 h 59   ← pire valeur de la série
13/10     +52 min    ← meilleur depuis le 07/10
```

✅ **Le retard retombe d'un ordre de grandeur** après la pire valeur de la
série. ⓘ **Le VPS est à l'heure, et il n'y est pour rien** : notation à
**05:55:05** (prochaine mercredi 14/10 **05:59:42**), contrôle à **07:30:46**
(prochain mercredi **07:30:44**). **Le trou est côté planification de la
routine.**
⚠️ **Une valeur ne fait pas une tendance, ici non plus** : six matins sur douze
ont dérivé et deux n'ont pas tiré. Le retard reste le premier risque du
dispositif, et il a déjà emporté la moitié du travail les 09 et 10/10.

## 12. Ce qui reste — et ce qui demande Yann

**Décisions, par ordre d'urgence :**

1. ⛔ **TRANCHER LES CAS DE POSITION — il reste DEUX JOURS.** Les sept balises
   sont passées à **8 j** ; elles franchiront **10 j le 15/10** et le compte
   passera de **3 à 10**, avec un cri à front. À trancher : `2171` (38,9 km),
   `1388` (2 363 m), `STATIC0491` (1 159 m), **et `1333` qui sort du lot**
   (10 → 8 → 7 → 6 → 5 j). Ensuite `position_suspecte` + `position_note` sur
   `station_zone` par `.sql`.
2. ⛔ **`bw-regime-sensibilite` : LE CRITÈRE EST REMPLI (2 / 2).** Deuxième
   hausse consécutive du coût par ligne de `regime` (12,94 → 13,02 → **13,14 ms**).
   L'arbitrage du 07/10 demande de **reposer la question, sans rien créer** :
   c'est fait. ⚠️ **Mais le niveau est bas** — 3e plus bas des treize relevés,
   +1,5 % cumulé, encore 1,28 ms sous le 09/10. Faut-il un motif, ou faut-il
   **ajouter un plancher de niveau au critère** ? **Rien n'a été créé.**
3. ⛔ **FERMER KAN-5 ? Le compteur est à 6 / 3** (quatrième jour où la question
   est posée). Six nuits consécutives sans 57014, nombre de lignes lisible à
   chaque fois. ⚠️ **Deux réserves inchangées** : le `statement timeout` a
   **changé de requête** le 10/10, et le `diagnostic_base_sous_tension` n'a
   **jamais été joué** (quatorze jours). La cause profonde n'est pas mesurément
   réglée, seulement le symptôme sur la purge. *Un ticket fermé à tort vaut
   moins qu'un ticket ouvert.* ⇒ **Et s'il est fermé, il faudra dire où va « la
   base est sous tension », qui n'a pas de ticket.**
4. ⛔ **Jouer `diagnostic_base_sous_tension_2026-09-29.sql`** (lecture seule,
   9 blocs, SQL Editor). **Quatorze jours d'attente**, et c'est la réserve n° 2
   de la fermeture de KAN-5.
5. ⚠️ **La mémoire se détend, sans changer de nature.** Les trois records d'hier
   sont **tous démentis** et « le score par régime » repasse **sous le seuil** —
   mais le jalon reste le **2e plus haut** (3 422 Mo, +622), le coût par ligne
   **n'a toujours aucune pente sur quinze nuits** (±1,9 %), et c'est la **23e
   nuit sans levier** depuis `af25efb` (21/09). ⇒ **Ce n'est pas une dérive
   qu'on attend, c'est un plafond qu'il faut baisser** : la **ligne en tuple**
   (≈ −1 030 o/ligne) après la mesure `tuple` vs `namedtuple` à la sonde.
6. ⚠️ **ρ hors [0, 1] : 437 / 3 708, NOUVEAU PLUS HAUT, 4e hausse sur cinq
   nuits (+42 % depuis le 08/10).** C'est désormais **la seule série du journal
   qui monte sans démenti**. ⇒ **Candidat le plus net à un motif neuf** — mais
   cinq points ne font pas une pente : à revoir demain avant d'en faire quoi que
   ce soit. **Rien n'a été créé.**
7. ⛔ **Lancer `~/installer-webhook-discord.sh`.** `BW_DISCORD_WEBHOOK_URL`
   toujours absente, **31e jour**. ntfy reste **seul**, avec son quota anonyme
   dépendant du voisinage /64 d'OVH.
8. ⚠️ **Instrumenter le bloc hors étapes de `run.sh` ?** La demande reste
   ouverte, mais **l'argument d'hier s'est retourné** : cette nuit le mouvement
   est **entièrement dans les étapes**. Sur trois nuits le hors-étapes a porté
   39 %, 90 % puis −158 % du mouvement : on ne sait toujours pas lequel des six
   postes bouge. C'est une écriture dans `run.sh` : la décision est à toi.
9. ✅ **Un motif Jira pour les témoins du mélange ? NON — question close.**
   Deuxième remontée consécutive, **+3,1 %** contre le meilleur membre et
   **6,5 %** contre la moyenne uniforme, devant dans **51,6 %** des cas. ⓘ Et
   l'erreur absolue a encore chuté de 12,4 % : **l'indicateur suit la météo du
   jour**, c'est la leçon à retenir de ces neuf nuits.
10. ⓘ **Un champ de bilan de purge au registre ?** (question du 08/10.) Avec
    `lignes_effacees` et `tranches`, le §4 tiendrait en trois lignes et le
    compteur de KAN-5 se lirait sans ouvrir un journal.
11. ⓘ **Le cri de position : à front ou à état ?** (question du 01/10.)
    **Faut-il un motif Jira pour une panne de canal ?** (question du 30/09.)
    **Un motif pour `bw_character_avance` ?** — absent pour la 3e nuit, la
    question est moins pressante, pas close.

**Ce que la surveillance regardera au prochain run :**

12. **Le coût par ligne de `regime`** : **2 / 2 atteint.** Une **troisième
    hausse** ferait du critère autre chose qu'un déclenchement de bord ; un
    recul le remettrait à 0. C'est la question n° 1 de demain.
13. **La position, le 15/10** : le cri à front de **3 → 10** confirmées. Les
    sept sont à 8 j.
14. **ρ hors [0, 1]** : **437, nouveau plus haut.** Une cinquième hausse sur six
    nuits ferait de cette série la première vraie pente du journal.
15. **La mémoire** : le jalon **retombe-t-il sous 3 400**, et « le score par
    régime » **reste-t-il sous le seuil** ? Le swap **tient-il** la bande
    2,0–2,3 Go ?
16. **KAN-5** : une **septième** nuit propre, ou le retour du 57014 ?
17. **La durée** : la signature **se re-inverse-t-elle une troisième fois** ?
    Deux nuits de suite, calcul/attente et étapes/hors-étapes ont changé de
    camp.
18. **`mutations_memoire`** : une sixième nuit muette, ou le retour du relevé ?
19. **L'horaire** : **+52 min** après +10 h 59. Le tir se stabilise-t-il ?
