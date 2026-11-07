# Verdict de pente du 07/11/2026 — ⛔ **DEUX MATINS SAUTÉS (05 et 06/11) : ce run couvre TROIS nuits.** ⛔ **SWAP AU PIC À SON RECORD : 2 474,3 Mo, troisième hausse d'affilée, pendant que la charge BAISSE.** ⛔ **R2 à 10,551 Go (105,5 %), nouveau plus haut — et le « premier recul » du 04/11 est démenti.** ✅ **Purge : douze nuits propres, compteur KAN-5 à 12 / 3, critère rempli depuis NEUF jours.** ✅ **Trois commentaires Jira posés et vérifiés.**

## 11:49–12:05 (Paris, CET) — routine Balise Watch, run du jour

**Étape 0 : faite en entier, avant toute autre chose.**

- `git log --oneline --since=midnight` dans **les deux** dépôts : ✅ **aucun
  commit du jour**. Dernier commit du dépôt serveur : **`5c560e6` du 03/11**
  (miroir du verdict du 03/11). **Aucune autre session n'a tourné ce matin.**
- `project_read claude/verdict-pente-07-11.md` : **absent** ⇒ cette note est une
  **création**, pas une fusion. `verdict-pente-06-11.md` et `-05-11.md` :
  **absents aussi** ⇒ voir §0.
- `project_read claude/verdict-pente-04-11.md` : ✅ **lu en entier** — c'est lui
  qui sert de référence, et c'est lui que je corrige sur **cinq** points
  (§3, §5.1, §6, §7 et §9).
- `notes-projet/README.md` relu : les quatre règles.
- ⓘ **Le travail n'était pas fait. Je l'ai fait, en entier.**

## 0. ⛔ CE RUN COUVRE TROIS NUITS : les matins du 05 et du 06/11 n'ont pas tiré

| matin | note projet | miroir git | commentaires Jira |
|---|---|---|---|
| **04/11** | ✅ déposée | ⛔ non (Mac tombé) | ⛔ **aucun** |
| **05/11** | ⛔ **aucune** | ⛔ aucun | ⛔ **aucun** |
| **06/11** | ⛔ **aucune** | ⛔ aucun | ⛔ **aucun** |
| **07/11** | ✅ celle-ci | ✅ déposé + commit | ✅ **trois, vérifiés** |

⇒ ⛔ **Les tickets n'avaient rien reçu depuis le 03/11** : le GET d'avant
écriture le prouve (KAN-3 38 comm., KAN-4 52, KAN-5 35 — exactement les chiffres
que la note du 04/11 donnait comme « dernier état connu », et dernier
commentaire daté du **03/11 à 08:15**). **Quatre matins sans un mot sur les
tickets.**
⇒ ✅ **C'est rattrapé ce matin** : les trois commentaires couvrent les trois
nuits, chiffres à l'appui (§10).
⚠️ **Et c'est un problème de planification, pas de VPS** : le VPS a tourné les
trois nuits, à l'heure, et le contrôle de 07:30 a parlé les trois matins (§11).

## 1. ⚠️ Le critère `bw-regime-sensibilite` : 1 / 2, et la hausse est du bruit

**Coût par ligne de `regime`** (`etapes_s.regime / lignes_regime × 1000`) :

```
29/10 10,86 ms · 30/10 11,30 · 31/10 11,88 · 01/11 10,92 · 02/11 11,13
03/11 11,58 · 04/11 10,71 · 05/11 10,70 · 06/11 10,67 · 07/11 10,68 ms
```

⇒ **Une seule hausse, de +0,01 ms.** Compteur **1 / 2** ⇒ ⛔ **le critère unique
arbitré le 07/10 n'est PAS rempli, aucune question posée, rien créé.**
ⓘ Et il faut le dire franchement : **+0,01 ms est du bruit**, pas une hausse.
Les quatre dernières nuits tiennent dans **0,04 ms** (10,67 à 10,71) — c'est le
passage le plus plat de la série.
ⓘ **10,67 ms (06/11) est le point le plus bas des dix-huit nuits.** Je n'en tire
rien : la bande va de 10,67 à 12,59 ms et elle n'a **aucune direction**.
❓ **La question de règle posée le 04/11 reste entière** : faut-il compter ce
critère sur **trois** nuits au lieu de deux ? Il a été rempli puis cassé en 24 h
**deux fois en cinq jours**. C'est à Yann de trancher ; j'applique la règle
écrite.

## 2. Le relevé des trois nuits

`lancement = timer` · `result = success` · `exec_status = 0` · `oom = 0` **pour
les trois nuits**. ✅ **Self-test du scoring VERT**, les **cinq** contrôles lus
un par un (prévision = observation 0,000000 ; skill contre persistance 1,0,
mse_persist 26,683 ; contre climatologie 1,0, mse_clim 18,000 ; contre combinée
1,0, `mse_comb` 17,841 ; contre combinée vectorielle 1,0, `mse_comb_vec`
17,841 ; permutée 2,198 et skill −2,2604). Relevés **comparables** : le verdict
porte.

Nuit du 06→07/11 : début **04:58:23**, fin **06:18:39** (CET). Journée notée
**2026-11-06**. Contrôle passé à **07:30:12** CET, suivant armé pour le **08/11
à 07:30:57 CET**.

| | 04/11 | 05/11 | 06/11 | 07/11 | Δ(06→07) |
|---|---:|---:|---:|---:|---:|
| `duree_s` | 4 905 | 4 893 | 4 907 | ✅ **4 806** | **−101** |
| `cpu_s` | 3 868,9 | 3 928,1 | 3 871,4 | 3 848,9 | −22,5 |
| `marge_s` | 3 195 | 3 207 | 3 193 | **3 294** | +101 |
| marge / garde (8 100 s) | 39,44 % | 39,59 % | 39,42 % | ✅ **40,67 %** | **+1,25 pt** |
| étapes (somme) | 2 814,9 | 2 868,7 | 2 849,4 | **2 877,5** | **+28,1** |
| hors étapes | 2 090,1 | 2 024,3 | 2 057,6 | **1 928,5** | **−129,1** |
| `jalon_max_mo` | 3 406 | 3 378 | 3 373 | **3 369** | −4 |
| `mem_peak_mo` | 3 623,2 | 3 607,5 | 3 597,4 | 3 594,7 | −2,7 |
| `swap_peak_mo` | 2 166,8 | 2 234,0 | 2 374,3 | ⛔ **2 474,3** | **+100,0** |
| `swap_out_pages` | 2 253 482 | 2 304 562 | 2 253 484 | ⛔ **2 593 421** | **+339 937** |
| `n_57014` | 1 | ✅ 0 | ✅ 0 | ✅ **0** | 0 |
| `incidents` | 3 | 2 | 2 | **2** | 0 |
| `lignes_regime` | 142 398 | 144 362 | 143 801 | 144 170 | +369 |
| `lignes_score_zone` | 153 082 | 155 047 | 154 487 | 154 861 | +374 |
| `lignes_daily` | 67 867 | 67 748 | 67 941 | 68 032 | +91 |
| `lignes_glissant` | 10 684 | 10 685 | 10 686 | 10 691 | +5 |
| `balise_jours_rejeu` | 2 047 433 | 2 045 279 | 2 043 446 | 2 041 814 | −1 632 |

Répartition par étape (s) :

| étape | 04/11 | 05/11 | 06/11 | 07/11 | Δ(06→07) |
|---|---:|---:|---:|---:|---:|
| `regime` | 1 525,2 | 1 544,3 | 1 534,6 | **1 539,7** | **+5,1** |
| `glissant` | 915,9 | 942,2 | 937,4 | 954,0 | +16,6 |
| `stabilite` | 295,8 | 302,5 | 293,5 | 305,9 | +12,4 |
| `rejeu` | 78,0 | 79,7 | 83,9 | 77,9 | −6,0 |

⇒ ⚠️ **La signature a rebasculé : 128 % du recul est HORS des étapes.** Les
quatre étapes **prennent 28 s** pendant que la durée totale en **rend 101**, et
tout vient du bloc hors étapes (**−129,1 s**). C'est l'inverse exact du 04/11
(116 % **dans** les étapes).

### 2.1 Les deux rapports qui valent mieux que les valeurs brutes

**Coût par ligne rejouée** (`jalon_max_mo × 1048576 / balise_jours_rejeu`) :

```
29/10 1 743,9 o · 30/10 1 728,7 · 31/10 1 728,4 · 01/11 1 720,6 · 02/11 1 710,6
03/11 1 713,1 · 04/11 1 744,4 · 05/11 1 731,8 · 06/11 1 730,8 · 07/11 1 730,2 o
```

⇒ **−14,2 o depuis le plus haut du 04/11, puis deux nuits quasi immobiles**
(−1,0 puis −0,6 o). La bande **1 596 à 1 744 o** tient une **dix-huitième**
nuit. ⓘ `balise_jours_rejeu` **recule encore** (−1 632) pendant que le jalon
recule aussi (−4) : les deux vont dans le même sens, donc le rapport bouge peu —
c'est le cas le plus lisible depuis longtemps.

**Calcul ou attente ?** ⚠️ **De l'ATTENTE, et c'est net.** La durée rend
**101 s** et `cpu_s` n'en rend que **22,5**, soit ≈ **78 s d'attente en moins**.
⇒ Parfaitement cohérent avec les **−129 s hors étapes** : ce bloc est fait
d'écritures et de publications, donc d'attente. **C'est le premier matin depuis
plusieurs semaines où les deux lectures (hors étapes et cpu) se recoupent
franchement.**

## 3. ✅ LA PURGE : douze nuits propres — compteur KAN-5 à 12 / 3

Bloc purge, les **trois** nuits, en entier :

```
2026-11-05 06:19:23  → purge model_score_zone : 149223 ligne(s) effacée(s) en 8 tranche(s)
2026-11-06 06:19:23  → purge model_score_zone : 149486 ligne(s) effacée(s) en 8 tranche(s)
2026-11-07 06:18:26  → purge model_score_zone : 151401 ligne(s) effacée(s) en 8 tranche(s)
```

(plus, chaque nuit, `ⓘ purge model_character : rien avant le 2027-02-04 — aucune
requête lancée`.)

Les quatre tests de lecture (règles du 28/09 complétées le 07/10) :

| test | 05/11 | 06/11 | 07/11 |
|---|---|---|---|
| tranche en échec | ✅ ✘ aucune | ✅ ✘ aucune | ✅ ✘ aucune |
| bilan chiffré | ✅ ✔ 149 223 / 8 tr. | ✅ ✔ 149 486 / 8 tr. | ✅ ✔ 151 401 / 8 tr. |
| « des lignes RESTENT » | ✅ ✘ absent | ✅ ✘ absent | ✅ ✘ absent |
| sonde en défaut | ✅ ✘ aucun | ✅ ✘ aucun | ✅ ✘ aucun |

⇒ ✅ **TROIS NUITS PROPRES PLEINES de plus**, sonde comprise.
⇒ ✅ **`n_57014 = 0` aux trois registres, ET zéro occurrence de `57014` sur
TOUTES les unités du VPS** (`journalctl --since 2026-11-05` → `grep -c` rend
**0**). **Première série de trois nuits à zéro partout depuis les 03-05/10.**
⚠️ **Et c'est précisément la série qui n'avait rien prouvé** : le 57014 était
revenu le 06/10. **Je ne présente donc pas ces trois nuits comme un correctif**,
et c'est la même réserve que celle que je me suis appliquée le 04/11 — ce
matin-là elle avait servi.

### 3.1 Compteur de fermeture KAN-5 : 12 / 3 — neuf jours de retard

```
27/10 → 1 / 3 · 28/10 → 2 / 3 · 29/10 → 3 / 3  ⇐ CRITÈRE REMPLI
30/10 → 4 · 31/10 → 5 · 01/11 → 6 · 02/11 → 7 · 03/11 → 8 · 04/11 → 9
05/11 → 10 · 06/11 → 11 · 07/11 → 12 / 3
```

⇒ ❓ **Le critère écrit est rempli depuis le 29/10, soit NEUF jours.** La
question est **reposée sur le ticket ce matin, pour la septième fois** (§10).
⛔ **Rien n'est fermé, rien n'est transité.** ✅ Et le GET d'avant écriture
confirme qu'**aucun tiers n'a touché au ticket** depuis le 03/11.

### 3.2 ✅ CORRECTION de ma note du 04/11 : le 57014 hors purge ne revient pas

Le 04/11 je relevais `n_57014 = 1` **hors bloc purge**
(`rpc/bw_character_avance`, reprise aboutie à 410 004 / 410 004) et j'écrivais
« motif **intermittent** […] **ne pas créer `bw-character-57014`** ».
⇒ ✅ **Trois nuits à zéro depuis.** L'avis est **inchangé et renforcé** : sur
vingt-cinq nuits le motif est intermittent, il se rattrape toujours, il ne coûte
aucune ligne. ⛔ **Ne pas créer de motif.**
⚠️ **Mais je ne dis pas « c'est réglé »** : trois nuits à zéro, c'est exactement
ce qui avait précédé le retour du 06/10.

### 3.3 Le volume : en hausse, et toujours pas un signal

```
03/11 149 592 · 04/11 149 281 · 05/11 149 223 · 06/11 149 486 · 07/11 151 401
```

⇒ **Onze nuits de suite à 8 tranches.** Les **+1 915 lignes** de cette nuit ne
sont pas plus un signal que les −58 de l'avant-veille : le volume effacé suit le
volume de la journée purgée.
⛔ **Et il n'y a toujours AUCUNE preuve** que la plus vieille journée soit partie
de la base : seul un `select as_of, count(*) … group by as_of order by as_of
limit 5` le dirait, et **aucun SQL n'a été joué**.

### 3.4 ⛔ Les deux défauts de code restent entiers — treizième nuit non testée

1. **(a)** `bilan_purge` ignore le suffixe « des lignes RESTENT » — faux négatif
   démontré le 25/10.
2. **(b)** `registre_nuit._INCIDENT` ne reconnaît pas la ligne de sonde, donc la
   branche `sonde_ko` de `controle_quotidien.constats()` est du **code mort** —
   démontré le 26/10.

⛔ **Il faut les DEUX.** Aucune des trois nuits n'avait ni ligne restante ni
sonde en défaut : **treizième nuit d'affilée** où ils ne peuvent être **ni**
confirmés **ni** réfutés. Ce sont des **écritures dans le code** : Yann tranche.

### 3.5 Le contrôle s'est tu les trois matins, et par la bonne porte

```
2026-11-05T06:30:58Z rien à dire : pente plate ou négative, ou échéance hors horizon
2026-11-06T06:30:59Z rien à dire : pente plate ou négative, ou échéance hors horizon
2026-11-07T06:30:12Z rien à dire : pente plate ou négative, ou échéance hors horizon
```

Verbeux, relancé à la main en lecture seule :

```
ⓘ 100 relevé(s), 79 comparable(s) ; durée : 10 points, pente -101 s/nuit ;
  mémoire : 10 points, pente -24 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate/négative, ou échéance hors horizon
```

✅ Le silence est **juste** et **par la bonne porte** : `incidents` ne porte
aucun avertissement de purge **parce qu'il n'y en a eu aucun** — les deux
incidents de la nuit sont **tous deux des jalons mémoire**.
ⓘ **100 / 79** contre 97 / 76 le 04/11 : **+3 et +3**, cohérent avec exactement
**trois** nuits de plus.
⚠️ **Une seule ligne au journal du contrôle aujourd'hui** ⇒ le jeton du jour est
resté **libre**, et c'est la routine qui a écrit, par le canal **délibéré**
(§10).

## 4. ⛔ Mémoire — le jalon recule quatre fois, mais LE SWAP EST À SON RECORD

```
                        04/11   05/11   06/11   07/11   vs seuil 2 800
rejeu d'archive         2 967   2 949   2 956   2 935    ⛔ +135
score par régime        2 914   2 778   2 697   2 534    ✅ −266 (SOUS)
oubli fenêtre rejouée   3 406   3 378   3 373   3 369    ⛔ +569
```

`incidents` : 3 → ⛔ **2**, stable sur les trois nuits.

Les autres jalons du 07/11 : agrégat quotidien J-0 **1 806** Mo (+11) · oubli
fenêtre glissante **1 685** (−18) · garde-fou de position **1 167** (+9) ·
mélange multi-modèle **1 150** (−3) · oubli du chemin J-0 **934** (+9) ·
relecture de l'archive **791** (+9).

### 4.1 Le jalon qui décide : 3 369 Mo, quatre reculs — la bande ne bouge pas

```
25/10 3 452 · 26/10 3 151 · 27/10 3 399 · 28/10 3 420 · 29/10 3 424 · 30/10 3 400
31/10 3 397 · 01/11 3 374 · 02/11 3 348 · 03/11 3 348 · 04/11 3 406
05/11 3 378 · 06/11 3 373 · 07/11 3 369
```

⇒ **Quatre reculs d'affilée, −37 Mo en tout.** ⚠️ **Et ce n'est toujours pas une
pente** : la bande **3 151 à 3 452 Mo est INCHANGÉE depuis dix-huit nuits**, et
3 369 est confortablement dedans. **Dix-huitième application** de « une nuit ne
fait pas une pente » — et cette fois, comme le 04/11, elle joue **contre** la
conclusion qui m'arrangerait.
⛔ Le jalon reste **+569 Mo au-dessus du seuil**.

### 4.2 ⛔ LE FAIT NEUF DU MATIN : le swap au pic est à son RECORD

```
pic (Mo)    2 166,8 → 2 234,0 → 2 374,3 → 2 474,3    (+307,5 en trois nuits)
pages       2 253 482 → 2 304 562 → 2 253 484 → 2 593 421   (+339 937 en une nuit)
```

⇒ ⛔ **2 474,3 Mo est le PLUS HAUT de la série**, au-dessus des 2 431,8 Mo du
29/10. **2 593 421 pages sorties est un record aussi.**
⇒ ⛔ **TROIS hausses consécutives du pic**, et les **deux** témoins vont dans le
**même** sens cette nuit. **Ce n'est plus « une nuit ne fait pas une pente » :
c'est le seul témoin de tout ce relevé qui ait une direction, et elle est
mauvaise.**

⚠️ **Et la charge n'explique pas — deuxième constat de ce type en quatre jours.**
La journée notée était **très calme** : erreur du mélange **2,3586 km/h** contre
4,0266 le 04/11, `model_verif_event` **23 435** lignes contre 43 005.
⇒ **Le swap monte pendant que la charge baisse.** Le 04/11 j'avais écrit que
l'explication « c'est la charge » ne marchait pas dans l'autre sens ; elle ne
marche pas dans celui-ci non plus. ⇒ ⓘ **Conclusion de méthode : abandonner
l'explication par la charge. Elle n'explique ni les hausses, ni les baisses.**

### 4.3 ⚠️ « Score par régime » : 2 534 Mo — et la réserve TIENT

**2 534 Mo, soit 266 Mo SOUS le seuil**, après quatre reculs (2 914 → 2 778 →
2 697 → 2 534). C'est ce jalon qui fait passer `incidents` de 3 à 2.
⛔ **Je ne le présente PAS comme une amélioration de fond, et la raison est
documentée** : la **même** configuration — ce jalon sous le seuil — a été
**démentie en une nuit DEUX fois**, le 31/10 et le 04/11. La réserve écrite les
30/10, 02/11 et 03/11 reste **en vigueur**.
ⓘ Honnêtement : trois nuits sous le seuil, c'est plus que les deux qui avaient
été démenties. **C'est donc le premier élément à surveiller si une quatrième
nuit tient** — mais ce n'est pas une conclusion ce matin.

### 4.4 L'estimateur de pente, douzième matin contradictoire

**−24 Mo/nuit** (25ᵉ centile des différences) pendant que le jalon fait **−4**.
Conclusion du 23/10 **confirmée une douzième fois** : cet estimateur **n'est pas
utilisable en prévision** sur cette série. ⓘ L'échéance étant hors horizon, le
contrôle se tait — et sur ce point **il a raison**.

### 4.5 Les trois conditions de fermeture de KAN-4

| condition | état |
|---|---|
| le contrôle se tait sur `bw-pente-memoire` | ✅ **remplie** (10ᵉ matin) |
| le jalon est mesurément retombé | ⛔ **non** — 3 369 Mo, **+569** au-dessus, bande inchangée depuis 18 nuits |
| le swap au pic ≈ 0 | ⛔ **non** — 2 474,3 Mo, **À SON RECORD**, 3 hausses d'affilée |

⇒ ⛔ **NON RÉUNIES. KAN-4 reste ouvert.** ⚠️ Et la condition de swap s'est
**nettement éloignée** depuis le 04/11.

### 4.6 Le remède, inchangé — 47ᵉ jour

La **ligne en tuple** (§2.6 de l'enquête du 10/09) : ≈ **−1 030 o/ligne**, soit
≈ **−2 005 Mo** sur les 2 041 814 balise-jours rejoués — à comparer aux
**569 Mo** qui séparent le jalon du seuil. ⛔ **Rien de déployé côté mémoire
depuis `af25efb` (21/09) — 47ᵉ jour.** ⚠️ L'élagage de `units` avait rendu
−124 Mo au lieu de −1 500 : les gains sont dans la **structure**. La mesure
`tuple` contre `namedtuple` à la sonde reste le préalable.
ⓘ Aucun calcul à taux constant : la série du jalon n'a **pas** de pente.

## 5. ✅ Durée — 4 806 s, la plus basse depuis le 27/10

```
24/10 5 064 · 25/10 5 252 · 26/10 5 133 · 27/10 4 728 · 28/10 4 927 · 29/10 4 921
30/10 4 934 · 31/10 5 079 · 01/11 4 900 · 02/11 4 989 · 03/11 5 088 · 04/11 4 905
05/11 4 893 · 06/11 4 907 · 07/11 ✅ 4 806 s
```

⇒ ✅ **Point le plus bas depuis le 27/10** (4 728 s), et **101 s d'amplitude sur
quatre nuits** : le passage le plus plat depuis le 30/10.
⚠️ **Solde des deltas depuis le 23/10** : **−436 s sur seize nuits.**
✅ **Marge : 40,67 % du garde**, 3 294 s de réserve sur 8 100 — la marge la plus
confortable depuis le 27/10 (41,63 %). **Aucune urgence mécanique.**

### 5.1 ⚠️ La signature rebascule : 128 % du recul HORS des étapes

```
            étapes     hors étapes   total
04/11      2 814,9       2 090,1     4 905
05/11      2 868,7       2 024,3     4 893
06/11      2 849,4       2 057,6     4 907
07/11      2 877,5       1 928,5     4 806
```

⇒ ⚠️ **Les quatre étapes PRENNENT 28 s pendant que la durée en rend 101.** Tout
le mouvement est dans le bloc **hors étapes** : **−129,1 s**, et **1 928,5 s est
son point le plus bas de la fenêtre**.
⛔ **CORRECTION de ma note du 04/11** : j'y écrivais « la demande de jalons de
temps dans le bloc hors étapes de `run.sh` **NE SE RENFORCE PAS**, pour la
deuxième nuit de suite » et je notais que ce bloc montait trois nuits d'affilée.
⇒ ⚠️ **Démenti** : il a **reculé de 129 s** en une nuit, et il porte **tout** le
mouvement. ⬆️ **La demande de jalons SE RENFORCE nettement ce matin** : sans
eux, un mouvement de 129 s n'est attribuable à rien. C'est une **écriture** dans
`run.sh` : Yann décide.
ⓘ **La leçon vaut dans les deux sens** : ce bloc non instrumenté a porté 85 %
d'une hausse le 07/10 et 128 % d'un recul le 07/11. **Ce n'est pas « du bruit »,
c'est « du non mesuré ».**

### 5.2 Volume et travail par ligne : tous deux en légère hausse

```
lignes_regime     143 801 → 144 170   (+369)
etapes_s.regime     1 534,6 → 1 539,7  (+5,1 s)
coût par ligne        10,67 → 10,68    (+0,01 ms)
```

⇒ Les deux montent **très légèrement** et dans les mêmes proportions : il n'y a
**rien à expliquer**. C'est ce qui laisse le critère du §1 à 1 / 2.

### 5.3 Le garde

⛔ **Remontée du chien de garde : NON LANCÉE et NON DEMANDÉE.**
`controle_quotidien.proposition()` ne se déclenche pas. La forme, **décrite** et
non demandée : écrire la mesure dans l'en-tête de `10-timeout-s3.conf`
(135 → 140/145 min), déployer, vérifier. **C'est Yann qui décide et qui lance.**
⬇️ **L'argument faiblit encore** : la marge remonte à 40,67 %.

ⓘ Rappel : la pente du contrôle est le **25ᵉ centile des différences**. Elle
affiche **−101 s/nuit** — ⓘ et par construction elle n'a vu **aucune** des
grosses hausses : ni le +153 s du 01/10, ni le +336 s du 06/10, ni le +70 s du
07/10, ni le +188 s du 25/10, ni le +199 s du 28/10, ni le +145 s du 31/10, ni
le +89 s du 02/11, ni le +99 s du 03/11. ⇒ **C'est un estimateur qui
n'enregistre que les bonnes nouvelles, et il ne faut pas lui faire dire que la
durée s'améliore.**

## 6. ⛔ R2 : 10,551 Go (105,5 %), nouveau plus haut — et DEUX démentis du 04/11

```
                      04/11             05/11             06/11             07/11
total compte     10,413 Go 104,1 %  ✅ 9,789 Go 97,9 %  10,496 Go 105,0 %  ⛔ 10,551 Go 105,5 %
objets             7 589             7 552             7 719             7 781
pente mesurée    +0,008 Go/mois     +0,015            −0,009            −0,001
garde-fou        code 1, 7 cons.    ✅ code 0 (muet)   code 1, 1 cons.   code 1, 2 cons.
```

⇒ ⛔ **10,551 Go est le plus haut relevé de la série** (le précédent était
10,433 Go le 03/11), et le journal le dit sans détour :
`⚠️ palier gratuit DÉPASSÉ : 10.55 Go sur 10 Go — R2 facture déjà`.

### 6.1 ⛔ PREMIER DÉMENTI du 04/11 : le « premier recul » n'était pas une inversion

Le 04/11 j'écrivais : « ✅ **ELLE S'INVERSE** […] **premier recul de la série** »
avec la réserve « ⚠️ **une nuit ne fait pas une pente, y compris celle-là** ».
⇒ ⛔ **DÉMENTI, et la réserve était la bonne** : après 10,413 Go le compte est
passé à 9,789 puis **10,496 puis 10,551 Go**, soit **+138 Mo au-dessus du
plus haut du 03/11**. Le recul du 04/11 n'annonçait rien.
⚠️ **Et le fait de facturation ne dépend d'aucune pente** : **dixième nuit
au-dessus du palier** sur les onze dernières. ⓘ Le seuil d'alerte (12 Go) et
celui d'arrêt de chaîne (6 Go) ne sont pas en cause ; couverture **complète**.

### 6.2 ⛔ SECOND DÉMENTI, et il est plus grave : `agrume/grille` N'EST PAS stable

```
            agrume/grille            total compte     garde-fou
04/11     5,323 Go / 766 obj        10,413 Go        code 1
05/11  ⛔ 4,609 Go / 667 obj      ✅  9,789 Go     ✅ code 0 — muet
06/11     5,323 Go / 766 obj        10,496 Go        code 1
07/11     5,323 Go / 766 obj        10,551 Go        code 1
```

⇒ ⛔ **Le 05/11, le préfixe a perdu 714 Mo et 99 objets pour UNE nuit, puis il
est revenu au Mo et à l'objet près.** C'est **exactement** le motif du 27/10
(−1 125 Mo / −156 objets, puis retour).
⇒ ⛔ **Ma note du 04/11 est démentie** : j'y écrivais « ✅ la fermeture du 31/10
**tient** — septième nuit à **766 / 766 et 5,323 Go, au Mo et à l'objet près** »
et « je ne la réouvre pas ». **Elle n'a tenu qu'une nuit de plus.**
⇒ ⓘ **Ce que cela apprend, et c'est utile** : le creux n'est **pas** une
suppression et **pas** un geste humain (aucun commit ces jours-là, vérifié à
l'étape 0) — c'est **l'audit qui tombe au milieu d'un cycle de réécriture** du
préfixe. La question du 27/10 n'avait donc pas la bonne réponse : ce n'était pas
« la fenêtre glissante a fini de glisser », c'est « le préfixe se réécrit
périodiquement et l'audit n'est pas synchronisé avec lui ».
⇒ ❓ **Question qui en découle, et elle est neuve** : faut-il que `audit_r2.py`
dise quand il lit un préfixe en cours de réécriture ? Sinon une nuit sur dix la
jauge se trompe de 700 Mo — **et c'est exactement la nuit où le garde-fou se
tait**, donc celle où personne n'est averti.
⚠️ **Je n'ai PAS pu lire la ligne d'index du 05/11** (`agrume/grille/ N présentes
/ N réclamées`) : mon filtre l'a manquée. **Je ne l'invente pas.** Les trois
autres nuits disent **766 / 766 ✓ tout est réclamé**, et aucune des trois ne
porte de ligne « suppression(s) ratée(s) ».

### 6.3 ⛔ `agrume/pi` : vingt-cinquième nuit d'accumulation, sans un seul recul

```
agrume/pi : 4 147 (04/11) → 4 195 → 4 243 → 4 291 objets     (+48 par nuit, exactement)
            1,833 Go      → 1,854 → 1,873 → 1,895 Go
```

```
│ agrume/pi/grille/            19 présentes /  19 réclamées   ✓
│ agrume/pi/rafraichissement/  28 présentes /  28 réclamées   ✓
```

47 objets couverts sur **4 291** ⇒ **4 244 objets que nul index ne réclame**
(4 100 le 04/11). **+48 par nuit, pour la vingt-cinquième nuit consécutive,
sans un seul recul.**
ⓘ Ce n'est pas la preuve qu'ils sont orphelins ; c'est la constatation qu'on
**n'en sait rien**. **L'inventaire reste le geste à faire avant toute
rétention.**

### 6.4 ⛔ La pente d'`audit_r2.py` : l'illusion est maintenant totale

⇒ ⛔ **La pente affichée du total est à −0,001 Go/mois** — c'est-à-dire
**négative** — pendant que le compte est à **105,5 % du palier** et que le seul
préfixe qui croisse vraiment croît à **+0,581 Go/mois**.

```
agrume/pi     +0,581   │  arome/rafale  −0,394   │  arome/sol     −0,297
fcst/2026     +0,085   │  arome/alt     −0,091   │  arome/lod     −0,047
fcstreduit    +0,062   │  agrume/colonnes −0,018 │  agrume/grille −0,004
```

⇒ **Six préfixes à fenêtre glissante portent des pentes négatives qui annulent
la seule vraie croissance.** ⬆️ **Le correctif proposé (borner à zéro les pentes
négatives des préfixes à fenêtre glissante) n'a jamais eu autant d'arguments :
la jauge annonce aujourd'hui une décroissance d'un compte qui facture.** Une
ligne, mais c'est une **écriture**.
ⓘ « Palier atteint dans 0 j » reste juste **par accident** (le palier EST
dépassé), pas par la pente.

## 7. ✅ Position — le cri est parti le 05/11, sur une BAISSE

```
04/11 : 16 divergentes, 5 CONFIRMÉES  (STATIC0491, 70, 1715, mf:05170001, 2058)
05/11 : 12 divergentes, 3 CONFIRMÉES  ⇒ ⛔ « cri déposé pour envoi » + push + mail
06/11 : 12 divergentes, 3 CONFIRMÉES  ⇒ aucun cri (état constant) ✅
07/11 : 13 divergentes, 3 CONFIRMÉES  ⇒ aucun cri (état constant) ✅
```

Les **trois** confirmées, identiques les 05, 06 et 07/11 :

```
⛔ pioupiou:367          6 764 m · 10 j · nœud 0,01 + profil 0,025 CHANGENT · Le relais
⛔ infoclimat:STATIC0491 1 159 m · 10 j · nœud 0,01 CHANGE
⛔ mf:05170001             330 m · 10 j · nœud 0,01 CHANGE
```

⇒ ✅ **Le mécanisme « à front, pas à état » est vérifié une 17ᵉ fois, et pour la
première fois sur une BAISSE** : les confirmées passent de 5 à 3, le front
change, **le cri part**. Les deux matins suivants, l'état est constant et le
canal se tait. **C'est exactement ce que le code doit faire.**

### 7.1 ⚠️ CORRECTION de ma note du 04/11 : la liste des cas a changé

⛔ **Trois des cinq cas du 04/11 ont quitté la liste des confirmées tout seuls** :
`pioupiou:70`, `pioupiou:1715` et `pioupiou:2058`. **Une entrante** :
`pioupiou:367` (Le relais, 6 764 m), qui plafonnait à 9 j depuis des jours.
⚠️ **Attention à la mauvaise lecture** : quitter la liste des *confirmées* veut
dire que le **compteur de jours est retombé sous 10**, PAS que la balise est
réparée — elles sont probablement toujours parmi les 13 divergentes. ⇒ **Leur
divergence est INTERMITTENTE**, ce qui est précisément l'argument du 30/10 : un
compteur de jours est bruité, on ne prédit pas son franchissement.
⇒ ⬆️ **`position_l15_2026-11-02.sql` attend toujours Yann**, mais **son contenu
n'est plus à jour** : il visait 1715, 2058, 70 et STATIC0491, et il faudrait
maintenant y ajouter `mf:05170001` et `pioupiou:367` — en sachant que trois de
ses cibles sont, ce matin, sous le seuil de confirmation.

### 7.2 ⛔ DÉMENTI de l'échéance annoncée le 04/11

Le 04/11 j'écrivais : « les **huit** balises du 29/10 (1344, 1770, 1588, 2190,
1618, 1640, 309, 2156) passent toutes à **7 j** ⇒ **10 j le 07/11**, dans trois
nuits ».
⇒ ⛔ **DÉMENTI : aucune des huit n'est confirmée ce matin**, et aucune
n'apparaît dans les trois premières lignes de la liste. La file visible est
`pioupiou:84` à **4 j**, `pioupiou:1562` à **3 j**, `pioupiou:2338` à **3 j**.
⇒ ⚠️ **C'est la deuxième fois que je fais cette erreur** (la première : le 28/10,
démentie le 30/10). **La leçon est écrite, elle n'a pas été appliquée. Je la
réécris : un compteur de jours qui monte n'est PAS une échéance, dans aucun des
deux sens.**

### 7.3 ⛔ DÉMENTI de l'annonce du 02/11 : toujours 9 balises, pas 12

La session du 02/11 annonçait le passage de **9 à 12** balises « nées sous leur
identifiant » **au 05/11** (`notee_depuis = '2026-11-05'`), et la note du 04/11
disait « rendez-vous demain ».
⇒ ⛔ **Trois matins plus tard, le journal dit toujours « 9 balise(s) née(s) sous
leur identifiant »**, et les neuf sont les mêmes qu'avant (toutes au
2026-09-25).
⇒ ⓘ **Explication la plus simple, et elle est vérifiable** : le `.sql` du 02/11
n'a **jamais été joué**. `git status` du dépôt serveur montre d'ailleurs
`model-verif/suspension_l15_2026-11-02.sql`, `position_l15_2026-11-02.sql` et
`naissance_l15bis_2026-09-22.sql` **non suivis par git**, donc écrits et pas
appliqués. **Ce n'est pas un bug, c'est un geste en attente.**

## 8. Les trois correctifs du 07/10 — verdict correctif par correctif

| correctif | verdict du 07/11 |
|---|---|
| **1. webhook `--ipv4`** | ✅ **CONFIRMÉ une SIXIÈME fois, et cette fois sur trois nuits et deux motifs différents.** 05/11 : cri de position, `ⓘ push parti (webhook, HTTP 200)` à 05:19:37Z + mail (1 431 o). 06/11 : palier R2, push **HTTP 200** à 05:19:41Z + mail (2 806 o). 07/11 : palier R2, push **HTTP 200** à 05:18:44Z + mail (2 806 o). ✅ **`grep -i ntfy \| grep -c 429` sur les trois nuits rend `0`** — c'est la vérification que le 04/11 n'avait pas pu jouer. ⓘ Trafic : **3 messages sur 3 nuits**, soit **1/nuit**, très en dessous des 2 à 7/jour normaux ⇒ aucun runner emballé. |
| **2. garde-fou des deux jetons** | ✅ **tient**, et cette fois des deux côtés. Côté automatique : les trois contrôles de 07:30 se sont **tus**, **une seule ligne** chacun, aucun jeton posé. Côté délibéré : la routine a posté **trois** commentaires par `bw_jira_commenter`, qui **ne touche pas au jeton du jour** — vérifié par GET avant et après (§10). `controle_quotidien.sh` conserve son `$ETAT` : **non touché**. ⓘ Les trois jetons `cri.jira.*` de `$HOME/.balise-watch-etat-alertes` datent toujours des 07 et 17/10 : **aucun n'a été réécrit**, ce qui est exactement attendu. |
| **3. rejeu de purge ≠ échec** | ⓘ **non sollicité**, treizième nuit : purge propre les trois nuits, aucun avertissement, rien à lire. Les deux défauts du §3.4 restent **entiers**. |

## 9. Les autres témoins

- ✅ **Témoins du mélange : MEILLEUR POINT DE LA SÉRIE — +8,2 %.**
  Sur **7 148** balise-jours×échéance, le mélange fait **2,3586** km/h contre
  **2,57** pour le meilleur membre a priori (**gain 8,2 %**, mélange devant dans
  **57,1 %** des cas) ; contre la moyenne **uniforme**, sur 1 052 : **2,2965**
  vs 2,3692 (**gain 3,1 %**).
  Série du gain contre le meilleur membre a priori : … −4,0 (25/10) · −2,2 ·
  **+5,2** · +2,3 · +0,5 · +3,0 · +3,3 · +0,6 · −0,8 · −2,5 · +0,1 (04/11) ·
  **+8,2 %**.
  ⇒ ✅ **Compteur `bw-melange-sans-gain` à 0 / 3, question restée retirée.**
  **+8,2 % bat le +5,2 % du 27/10**, et « devant » repasse **au-dessus de 50 %**
  (57,1 %) pour la première fois depuis six nuits.
  ⚠️ **À pondérer honnêtement** : la journée était **très calme** (erreur absolue
  2,3586 km/h, la plus basse que j'aie relevée), donc le **niveau** n'est pas
  comparable d'une nuit à l'autre. **Ce qui compte est le signe, et il est
  franchement positif.** ⓘ Et c'est l'inverse exact de l'explication tentée le
  27/10 puis abandonnée : journée calme **et** meilleur gain, à nouveau.
- ⚠️ **Témoin du corrigé : DEUX points bas nets, à noter sans conclure.**
  Part site **12,5 pt** (sur 8 962 balise-jours — vrai antécédent **+11,1 %**,
  autre balise **−1,4 %**). Série : 17,9 → 17,0 → 19,8 → 15,0 → 15,7 → 16,6 →
  22,0 → 23,0 → 22,0 → **12,5 pt**.
  Version FIN, part secteur+heure : 11,4 → 10,9 → 11,8 → 9,1 → 9,6 → 11,8 →
  11,5 → 13,0 → 11,5 → **3,9 pt** (S2 gagne 15,3 % sur le brut, le fin 6,6 pt de
  plus, contre 2,7 aux cellules tournées).
  ⇒ ⚠️ **Les deux sortent par le bas de la bande observée depuis trois semaines.**
  ⓘ **Mais l'échantillon FIN a FONDU** : **2 462** balise-jours contre 4 571 le
  04/11, soit presque moitié moins ⇒ l'estimation est beaucoup plus bruitée.
  ⇒ ⓘ **Je ne conclus rien, et je ne reprends pas « ça oscille » comme si rien
  n'avait bougé** : je note les deux points bas et le rétrécissement de
  l'échantillon, et je regarde demain.
- ⚠️ **Écarts du recalcul indépendant : 7 — HAUT de bande.** Série : 4 · 4 · 4 ·
  6 · 5 · 8 · 6 · 5 · (05/11 non relevé) · **3** (06/11) · **7** (07/11). Bande
  3–7 **tenue**, mais aux deux extrêmes en deux nuits.
  Les sept du 07/11 : `fcstagrume/infoclimat:ME125` (+48 h),
  `fcstagrume/mf:06075007` (+24 h), `fcstagrume/windsmobi:meteoswiss-DOL`
  (+24 h, **1 h** appariée), `fcstagrume/infoclimat:00065` (+6 h),
  `fcstagrume/mf:74182001` (+48 h), `fcstagrume/pioupiou:1538` (+24 h),
  `fcstagrume/windsmobi:ffvl-3374` (+24 h). ⓘ **6 sur 7 portent `0 h appariées
  ici (< 6)`** — même signature que les matins précédents. Tirage de 20 strates
  sur **13** strates présentes, 77 520 lignes de prévision, 3 468 balises.
- ⓘ **Écart des deux mélanges** : `mse_comb` 17,841 contre `mse_comb_vec`
  17,841 (**+0,00 %**) — les deux chemins restent confondus.
- **Duels** : `agrume ↔ agrume_pi (+6 h)` n = 7 118, médiane **+0,011**, IC95
  [+0,006 ; +0,017] → `b_better` · `agrume_pi ↔ bw_mix (+6 h)` n = 7 094,
  médiane **+0,387**, IC95 [+0,319 ; +0,480] → `b_better` ·
  `agrume ↔ meteofrance_arome_france_hd (+6 h)` médiane **−0,000**, IC95
  [−0,002 ; +0,002] → **`not_separable`** ·
  `arome_r2 ↔ meteofrance_arome_france_hd (+6 h)` n = 16 618 sur **29 j**,
  médiane **+0,089** → `b_better` · `agrume_pi ↔ bw_mix (+24 h)` n = 6 837 sur
  **29 j**, médiane **+0,445** → `b_better`.
  ⓘ **La journée AROME/R2 perdue du 25/10 se voit encore** : `arome_r2` porte
  **29 j** quand les duels +6 h vont jusqu'au 2026-11-06. **Jusqu'au 24/11.**
- **Murphy** : 68 269 triplets / **64 973** décomposés / 266 tenus dehors.
- ⚠️ **Observations : le recul TIENT, et il se stabilise franchement.**
  **3 468** balises observées (veille 3 466). Série depuis le 31/10 :
  **3 731** → 3 461 → 3 457 → 3 461 → 3 464 → … → **3 468**. ⇒ ⓘ Le recul de
  ≈ **263** balises est **stable sur une semaine**, et la série remonte très
  lentement (+7 en quatre relevés). `lignes_daily` **monte** en parallèle
  (67 867 → 68 032). 3 161 zonées, 1 233 cases fines dont 599 sous les
  2 balises. ⓘ Je **ne** l'explique toujours **pas**. ⇒ ❓ **La question reste
  entière, et elle a une semaine** : 263 balises ont-elles cessé d'émettre, ou
  la chaîne d'ingestion en perd-elle ?
  ⓘ **FDR** : brut 6 877 tests, 1 691 survivants à BH α=0,1, 104 rangs retirés
  sur 939 publiés ; corrigé 6 567 / 1 114, 95 retirés sur 569.
  ⓘ `model_events.json` **9 197** Ko, `model_scores.json` **135 638** Ko,
  `model_scores_light.json` 7 363 Ko, `model_murphy.json` 26 235 Ko.
  **35 190** lignes non publiées, **32 935** combinaisons publiables, 35 403
  écartées sous le quorum de 8.
  ⓘ `model_verif_event` **23 435** lignes (contre 43 005 le 04/11) : `drop`
  10 656, `onset` 8 251, `ramp` 2 580, `reversal` 1 948, `breeze_yield` 0.
  **Journée nettement plus calme.** ⓘ `manches` : **71** nuits suivies depuis le
  2026-08-24, 828 cases avec au moins une manche gagnée. Référence combinée :
  k médian **0,158** sur 3 683 balises / 3 805 climatologisées, 516 ρ ramenés à
  la borne.
- ✅ **CORRECTION / RÉPONSE au point n°6 du 04/11 : les mails « non expliqués »
  ne se reproduisent pas.** Le 04/11 je signalais deux `msmtp … EX_OK` partis à
  **00:45** et **01:00** hors de tout run, et je nommais
  `bw-model-oracle.service` comme candidat **à vérifier**.
  ⇒ ✅ **Sur les trois nuits, il y a exactement TROIS mails, un par nuit, chacun
  dans la seconde qui suit un cri** : 05/11 06:19:43 (1 431 o), 06/11 06:19:44
  (2 806 o), 07/11 06:18:46 (2 806 o). **Aucun mail hors run.**
  ⇒ ⓘ **Donc ce n'était pas un mécanisme régulier.** ⛔ **Mais je ne dis pas que
  c'est expliqué** : je n'ai jamais lu le contenu de ces deux mails du 04/11, et
  ils ne sont plus dans ma fenêtre. **La question se referme comme « non
  reproduite », pas comme « comprise ».**
- ⓘ **`bw-model-oracle.service`** : toujours en échec (`Result=exit-code`,
  `ExecMainStatus=1`). ⇒ **Il n'est PLUS suspect** du point ci-dessus, puisque
  plus aucun mail ne part hors run. Hors mission.
- ⛔ **Second canal du téléphone (Discord) : TOUJOURS ABSENT, et c'est mesuré ce
  matin.** `grep -c BW_DISCORD_WEBHOOK_URL ~/.balise-watch-alertes.env` rend
  **0** (le **nom** seul ; aucune valeur lue). ⇒ **57ᵉ jour.** Le script
  `~/installer-webhook-discord.sh` est **sur le Mac** et c'est Yann qui le
  lance. ⓘ À noter : `bw-discord-bridge.service` est **actif et tourne** — mais
  c'est le pont **Discord → Jira** des forums bugs/idées, pas le canal d'alerte.
  **Ne pas confondre les deux.**
- ⓘ **`mutations_memoire`** : ⚠️ **aucune ligne « mutation » trouvée dans le
  journal de notation du 07/11.** Je ne sais donc pas si la dette de 3 mutations
  non vues (2, 5, 13) a bougé. **Je la reporte telle quelle, en disant que je ne
  l'ai pas vérifiée par cette voie** — et non en recopiant le chiffre comme s'il
  était confirmé.

## 10. ✅ Les tickets — trois commentaires délibérés, vérifiés avant ET après

**GET avant écriture** (règle absolue) :

| ticket | statut | commentaires avant | dernier commentaire avant |
|---|---|---:|---|
| **KAN-3** | Terminé / `done` | 38 | 03/11 à 08:15:53 |
| **KAN-4** | À faire / `new` | 52 | 03/11 à 08:15:52 |
| **KAN-5** | À faire / `new` | 35 | 03/11 à 08:15:51 |

⇒ ✅ **Exactement les chiffres que la note du 04/11 donnait comme « dernier état
connu » : aucun tiers n'a écrit, et les quatre matins muets sont confirmés.**

**GET après écriture** : KAN-3 **39**, KAN-4 **53**, KAN-5 **36** — **+1 chacun**,
dernier commentaire **07/11 à 11:58**, et **aucun changement d'état** (KAN-3
toujours Terminé, KAN-4 et KAN-5 toujours À faire).

| ticket | ce qui a été posté |
|---|---|
| **KAN-5** | Les trois nuits propres pleines (149 223 / 149 486 / 151 401 lignes, 8 tranches), les quatre tests de lecture, `n_57014 = 0` **sur toutes les unités** avec la réserve explicite des 03-05/10 ; compteur **12 / 3** et critère rempli depuis **neuf jours** ⇒ **septième** question de fermeture ; volume donné comme **non significatif** ; absence de preuve que la journée soit partie de la base ; les **deux** défauts de code, **13ᵉ** nuit non testée |
| **KAN-4** | Les trois jalons et les six autres ; jalon **3 369 Mo** (4ᵉ recul) **et** bande 3 151–3 452 **inchangée depuis 18 nuits** ⇒ pas une pente ; ⛔ **le SWAP À SON RECORD** (pic 2 474,3, +307,5 en trois nuits ; pages 2 593 421, record) avec la démonstration que **la charge a BAISSÉ** ; coût par ligne rejouée **1 730,2 o** ; « score par régime » à 2 534 Mo **avec la réserve des 31/10 et 04/11** ; les **trois conditions**, dont une **éloignée** ⇒ non réunies ; le remède tuple, **47ᵉ jour** |
| **KAN-3** | Canal **délibéré** sur un ticket Terminé, pour information, **sans demande de réouverture** : durée **4 806 s** (plus basse depuis le 27/10), marge **40,67 %**, solde **−436 s** sur seize nuits ; ⚠️ **la signature rebascule — 128 % du recul HORS des étapes**, et **correction** de ma note du 04/11 sur ce point précis ; c'est de l'**attente** (cpu ne rend que 22,5 s) ; critère `regime` à **1 / 2** et la hausse qualifiée de **bruit** ; le rappel que la pente du contrôle **n'enregistre que les bonnes nouvelles** ; garde **non remonté, non demandé** |
| `bw-regime-sensibilite` | ⛔ **non créé** — critère à **1 / 2**, hausse de 0,01 ms (§1) |
| `bw-melange-sans-gain` | ⛔ **non créé** — compteur **0 / 3**, meilleur point de la série (§9) |
| `bw-r2-palier` | ⛔ **non créé.** ⬆️ **Dixième nuit au-dessus du palier**, nouveau plus haut (§6). ❓ **Question maintenue, et renforcée** |
| `bw-character-57014` | ⛔ **non créé** ; trois nuits à zéro, avis inchangé (§3.2) |

⛔ **Aucun ticket créé, fermé, rouvert ni transité.** Seules écritures du run :
les **trois commentaires**.
ⓘ **Le canal délibéré est assumé et il se dit ici** : le contrôle de 07:30 s'est
tu les trois matins, donc le jeton du jour était libre ; j'ai néanmoins utilisé
`bw_jira_commenter` (et non `bw_jira_signaler`) pour les trois, parce que
j'avais les chiffres de **trois** nuits, deux **corrections** de la note du 04/11
à porter, et qu'un des trois tickets est **Terminé**.

## 11. ⛔ Horaire de la routine — DEUX matins sautés et un gros retard

Programmée pour le **07/11 à 07:00:00 UTC**, tirée le **07/11 à 10:49:32 UTC** :
⚠️ **+3 h 49 min 32 s**.

```
27/10 +10 h 09 · 28/10 +1 h 34 · 29/10 ⛔ SAUTÉ · 30/10 +0 h 00 · 31/10 +0 h 00
01/11 +0 h 55 · 02/11 +0 h 19 · 03/11 ✅ +0 h 01 · 04/11 ⚠️ +4 h 42
05/11 ⛔ SAUTÉ · 06/11 ⛔ SAUTÉ · 07/11 ⚠️ +3 h 49
```

⇒ ⛔ **TROIS matins sautés en douze jours, et trois retards de plus de 3 h.**
Sur les quatre derniers matins, **un seul a produit du travail sur les tickets**
— celui-ci. **C'est le défaut le plus coûteux de la période**, bien plus que
n'importe lequel des chiffres ci-dessus.
ⓘ **Le VPS est à l'heure, les trois nuits** : notation à 04:57:53 / 04:57:39 /
04:58:23 CET, contrôle à 07:30:58 / 07:30:59 / 07:30:12 CET, timer suivant armé
pour le **08/11 à 07:30:57 CET**. **Le trou est entièrement côté
planification**, comme les fois précédentes.
⇒ ❓ **Geste attendu de Yann** : regarder la planification de la routine. Un
matin sauté, c'est une journée de chiffres qui n'arrive jamais sur les tickets.

## 12. Décisions en attente de Yann — la liste à jour

1. ❓ **PRIORITAIRE, et en retard de neuf jours : fermeture de KAN-5.** Le
   critère écrit est **REMPLI** (12 / 3, rempli dès le 29/10), douze nuits
   propres d'affilée. **Veux-tu le fermer ?** Je ne ferme rien sans ta réponse.
   ✅ La question est **posée sur le ticket ce matin**.
2. ⬆️ **PRIORITAIRE : R2 facture, dixième nuit.** **10,551 Go (105,5 %)**,
   **nouveau plus haut** de la série, et le « recul » du 04/11 est démenti
   (§6.1). ❓ Motif Jira `bw-r2-palier`, ou action de rétention ?
3. ⛔ **NOUVEAU et sérieux : le swap au pic est à son record** (2 474,3 Mo,
   **trois** hausses d'affilée, +307,5 Mo) **pendant que la charge baisse**
   (§4.2). C'est le seul témoin du relevé qui ait une direction. ❓ Veux-tu que
   j'ouvre un motif `bw-swap-pic` si une quatrième hausse vient, ou cela
   appartient-il à KAN-4 ?
4. ⛔ **Mémoire : la ligne en tuple** (≈ −1 030 o/ligne, ≈ −2 005 Mo). **47ᵉ jour
   sans rien de déployé** depuis `af25efb`. Seule porte de sortie de KAN-4.
5. ⬆️ **NOUVEAU : `audit_r2.py` lit `agrume/grille` en cours de réécriture**
   (§6.2). Une nuit sur dix, la jauge se trompe de **700 Mo** — et c'est
   exactement la nuit où le garde-fou **se tait**. ❓ Faut-il qu'il le signale ?
6. ⬆️ **Pente d'`audit_r2.py`** : borner à zéro les pentes négatives des préfixes
   à fenêtre glissante (§6.4). ⬆️ **L'argument n'a jamais été aussi fort** : la
   jauge annonce **−0,001 Go/mois** sur un compte à **105,5 %** du palier, alors
   que le seul préfixe qui croisse fait **+0,581**. Une ligne, mais une
   **écriture**.
7. ⬆️ **`position_l15_2026-11-02.sql`** : ⚠️ **son contenu n'est plus à jour**
   (§7.1). Les confirmées sont maintenant **trois** — `pioupiou:367`,
   `infoclimat:STATIC0491`, `mf:05170001` — et trois de ses cibles (70, 1715,
   2058) sont retombées sous le seuil. **À refaire avant de le jouer.**
8. ❓ **Faut-il que le cri de position RECRIE à état constant ?** (ouvert depuis
   le 01/10) ⓘ **Nuance apportée ce matin** : le mécanisme a bien crié le 05/11,
   **sur une baisse**, donc il n'est pas muet — il est seulement muet quand
   l'état ne bouge pas. **Avec trois balises cassées en permanence, c'est
   toujours la bonne question.**
9. ❓ **L'annonce du 02/11 (9 → 12 balises nées sous leur identifiant au 05/11)
   n'a pas eu lieu** (§7.3). Le `.sql` du 02/11 n'a vraisemblablement **jamais
   été joué** — à confirmer de ton côté.
10. ❓ **Faut-il compter `bw-regime-sensibilite` sur TROIS nuits au lieu de
    deux ?** (§1) ⓘ **C'est une règle : c'est à toi de la changer.** J'applique
    la règle écrite.
11. ⛔ **Les DEUX correctifs de lecture de la purge** (§3.4), inchangés :
    (a) `bilan_purge` et le suffixe « des lignes RESTENT » ; (b)
    `registre_nuit._INCIDENT` et la ligne de sonde. **Il faut les deux.**
    **Treizième nuit** où ils ne peuvent être ni confirmés ni réfutés.
12. ⛔ **R2 : rétention sur `agrume/pi`** — **+48 objets par nuit,
    vingt-cinq nuits d'affilée, sans un seul recul** (§6.3).
13. ⛔ **Inventaire des 4 244 objets de `agrume/pi` que l'index ne réclame pas**
    (sur 4 291). À faire **avant** toute rétention.
14. ❓ **Le recul de ≈ 263 balises observées tient une SEMAINE**
    (3 731 → 3 468) (§9). Ont-elles cessé d'émettre, ou la chaîne d'ingestion en
    perd-elle ?
15. ⬇️ **Jalons de temps dans le bloc hors étapes de `run.sh`** — ⬆️ **l'argument
    SE RENFORCE ce matin, et je corrige ma note du 04/11** : ce bloc a porté
    **128 %** du recul de la nuit (§5.1). Sans jalons, 129 s ne sont attribuables
    à rien.
16. ⛔ **Horaire de la routine : deux matins sautés (05 et 06/11) + 3 h 49 de
    retard ce matin** (§11). ⇒ **Trois matins sautés en douze jours.** C'est
    côté planification, pas côté VPS.
17. ⛔ **`installer-webhook-discord.sh`** (sur le Mac) : `BW_DISCORD_WEBHOOK_URL`
    **absente, mesurée ce matin** — **57ᵉ jour** (§9).
18. ⬇️ **`diagnostic_base_sous_tension_2026-09-29.sql`** — **40ᵉ jour** sans
    être joué. Urgence **basse** : treize nuits d'affilée où la purge aboutit,
    douze sans le moindre avertissement, et zéro 57014 sur les trois dernières.
19. ⬇️ **Le `select as_of, count(*)`** sur `model_score_zone` : seule façon de
    **prouver** que la plus vieille journée est partie. **Aucun SQL joué sans ton
    accord.**
20. ⓘ **Réouverture de KAN-3** : **mon avis est NON** — durée la plus basse
    depuis le 27/10, marge à **40,67 %**, solde **−436 s** sur seize nuits,
    critère `regime` à 1 / 2.
21. ⛔ **QUATRE miroirs git en souffrance**, vérifiés et **non arrangés** :
    **24/10** (jamais déposé), **26/10** (présent mais non suivi par git),
    **01/11** et **04/11** (Mac injoignable). ⓘ Les matins du 05 et du 06/11
    n'ont **pas** de dette de miroir : il n'y a jamais eu de note à refléter.
22. ⓘ **`mutations_memoire`** : dette de 3 mutations (2, 5, 13) reportée, ⚠️ **non
    vérifiée ce matin** — la ligne est absente du journal (§9).
23. ⓘ **`bw-model-oracle.service`** en échec — hors mission, et **plus suspect de
    rien** depuis que les mails hors run ne se reproduisent pas (§9).
24. ⚠️ **À regarder demain, sans conclusion aujourd'hui** : le témoin du corrigé
    sort par le **bas** de sa bande (12,5 pt et 3,9 pt), avec un échantillon FIN
    **moitié plus petit** (§9).

✅ **Retirées / refermées** : le point n°6 du 04/11 (mails de 00:45 et 01:00 —
**non reproduits** sur trois nuits, §9) ; le candidat `bw-model-oracle` qui en
découlait.

## 13. Ce que ce run a DÉMENTI, et ce qu'il a CONFIRMÉ, de la note du 04/11

| annoncé le 04/11 | relevé le 07/11 |
|---|---|
| ✅ critère `regime` **cassé (0 / 2)**, question retirée ; avis « il mérite trois nuits » | ✅ **CONFIRMÉ** : 10,70 → 10,67 → 10,68 ms, compteur **1 / 2**, non rempli. La hausse fait **0,01 ms** |
| ✅ compteur KAN-5 à **9 / 3**, 4ᵉ nuit propre, question jamais posée faute de Mac | ✅ **CONFIRMÉ et renforcé** : **12 / 3**, douze nuits propres, et ✅ **la question est enfin posée sur le ticket** |
| ⚠️ `n_57014 = 1` hors purge, motif **intermittent**, « ne pas créer » ; réserve : deux nuits à zéro ne prouvent rien | ✅ **CONFIRMÉ** : **trois nuits à zéro sur toutes les unités**, avis inchangé. ⚠️ Et je maintiens la réserve : c'est ce qui avait précédé le retour du 06/10 |
| ⛔ swap pic **+74,6 Mo**, pages **+319 818**, « l'explication par la charge ne marche pas » | ⛔ **CONFIRMÉ ET AGGRAVÉ** : pic **2 474,3 Mo (record, 3ᵉ hausse)**, pages **2 593 421 (record)**, et la charge a **baissé**. ⇒ **J'abandonne l'explication par la charge** |
| ⛔ jalon **3 406 Mo (+58)**, bande 3 151–3 452 inchangée, « ce n'est pas une pente » | ✅ **CONFIRMÉ dans les deux sens** : quatre reculs (3 369 Mo) et la bande **toujours** inchangée, 18ᵉ nuit. Ce n'est pas une pente **à la baisse** non plus |
| ✅ « score par régime » **2 914 Mo**, repassé au-dessus, réserve vérifiée | ⚠️ **2 534 Mo**, trois nuits **sous** le seuil, `incidents` à 2. ⛔ **Réserve MAINTENUE** : la même configuration a été démentie en une nuit les 31/10 et 04/11 |
| ⛔ coût par ligne rejouée **1 744,4 o**, plus haut de la série | ✅ **1 730,2 o** : −14,2 o, et deux nuits quasi immobiles. Bande 1 596–1 744 **tenue**, 18ᵉ nuit |
| ✅ durée **4 905 s (−183)**, **116 % du recul DANS les étapes**, marge 39,44 % | ✅ **4 806 s**, plus basse depuis le 27/10, marge **40,67 %**. ⛔ **Mais la signature REBASCULE : 128 % du recul HORS des étapes** |
| ⬇️ « la demande de jalons dans `run.sh` **ne se renforce pas** », bloc hors étapes en hausse trois nuits | ⛔ **DÉMENTI** : le bloc **rend 129 s** et atteint son point le plus bas. ⬆️ **La demande SE RENFORCE** |
| ✅ R2 **10,413 Go (104,1 %)**, **premier recul de la série**, avec la réserve « une nuit ne fait pas une pente » | ⛔ **DÉMENTI, et la réserve était la bonne** : 9,789 → 10,496 → **10,551 Go**, **nouveau plus haut**, 10ᵉ nuit au-dessus |
| ✅ `agrume/grille` : « la fermeture du 31/10 **tient** — 7ᵉ nuit à 766 / 766 et 5,323 Go au Mo près », « je ne la réouvre pas » | ⛔ **DÉMENTI en une nuit** : le 05/11 il tombe à **4,609 Go / 667 objets**, puis revient à l'identique. ⇒ **Ce n'est pas stable, c'est un cycle de réécriture que l'audit intercepte** (§6.2) |
| ⛔ `agrume/pi` **22ᵉ** nuit, 4 100 non réclamés | ⛔ **25ᵉ nuit**, **+144** ⇒ **4 244** non réclamés sur 4 291 |
| ✅ **5** confirmées de position, aucun cri, 16ᵉ vérification « à front » **par l'absence** | ✅ **17ᵉ vérification, et la première sur une BAISSE** : 5 → **3** le 05/11, **cri parti** ; puis deux matins muets à état constant. ⚠️ **Mais la LISTE a changé** (§7.1) |
| ⚠️ les **huit** balises du 29/10 « passent à 10 j le **07/11**, dans trois nuits » | ⛔ **DÉMENTI : aucune des huit n'est confirmée.** ⚠️ **Deuxième fois que je commets cette erreur** (28/10, démentie le 30/10) |
| ⓘ « 9 nées sous leur identifiant, passage à **12 au 05/11** — rendez-vous demain » | ⛔ **DÉMENTI : toujours 9**, les mêmes. Le `.sql` du 02/11 n'a vraisemblablement jamais été joué (§7.3) |
| ✅ webhook `--ipv4` confirmé une 5ᵉ fois, mais ⚠️ **test des 429 non joué** | ✅ **CONFIRMÉ une 6ᵉ fois**, sur **trois** nuits et deux motifs. ✅ **Et le test manquant est joué : zéro 429** |
| ⛔ `BW_DISCORD_WEBHOOK_URL` **non vérifiée**, « je ne compte pas un 54ᵉ jour non mesuré » | ⛔ **VÉRIFIÉE ce matin : absente.** **57ᵉ jour**, mesuré |
| ⚠️ témoins du mélange **+0,1 %** (match nul), « devant » sous 50 % | ✅ **+8,2 %, MEILLEUR point de la série**, « devant » à **57,1 %**. ⚠️ Mais journée très calme : le niveau n'est pas comparable |
| ⚠️ témoin du corrigé **22,0 pt**, « ça oscille, rien à surveiller » | ⚠️ **12,5 pt et FIN à 3,9 pt** : les deux sortent **par le bas**. ⓘ Je ne reprends donc **pas** « rien à surveiller » — avec la nuance que l'échantillon FIN a fondu de moitié |
| ⚠️ écarts du recalcul **5**, bande 3–7 | ✅ **3 puis 7** : la bande est tenue, mais aux deux extrêmes en deux nuits |
| ⚠️ recul de **270 balises** observées, 4ᵉ nuit, question entière | ⚠️ **CONFIRMÉ, une semaine** : 3 468 (≈ −263). La question reste entière |
| ❓ deux mails à **00:45 et 01:00** sans push visible, candidat `bw-model-oracle` | ✅ **NON REPRODUITS** sur trois nuits : exactement un mail par nuit, chacun après un cri. ⛔ **Non reproduit ≠ compris** |
| ⚠️ horaire **+4 h 42** | ⛔ **AGGRAVÉ : deux matins SAUTÉS puis +3 h 49.** Trois matins sautés en douze jours |
| ⛔ quatre miroirs git en souffrance | ⛔ **quatre, inchangés**, vérifiés et non arrangés. ✅ Celui du 07/11 est déposé et commité |
| ⛔ aucun ticket touché, aucun GET joué, état **inconnu** | ✅ **TOUT RATTRAPÉ** : GET avant (38/52/35), trois commentaires, GET après (39/53/36), aucun changement d'état |

⚠️ **« Une nuit ne fait pas une pente » — appliqué ce matin** à : les quatre
reculs du jalon mémoire (§4.1, et c'est celui qui m'arrangerait), les trois
nuits sous le seuil du « score par régime » (§4.3), le point bas de la durée
(§5), le +8,2 % du mélange (§9), les deux points bas du témoin du corrigé (§9),
les trois nuits à zéro du 57014 (§3.2) et le point le plus bas du coût par ligne
de `regime` (§1). **Aucun des sept n'est présenté comme une tendance.**

⛔ **Et cinq fois, ce matin, la leçon ne s'applique PAS** :
1. Le **critère de fermeture de KAN-5** est une **règle écrite** comptée sur
   trois nuits. Il est rempli depuis **neuf jours**.
2. Le **dépassement du palier R2** est un **fait de facturation**, pas une
   pente — et c'est un **nouveau plus haut**.
3. Le **swap au pic** fait **trois hausses consécutives** et touche son
   **record** : trois points dans le même sens, plus les pages dans le même sens
   la dernière nuit. **Ce n'est plus une nuit.**
4. Les **deux défauts de lecture de la purge** sont des **lectures de code**,
   vraies indépendamment du nombre de nuits.
5. **Deux matins sautés** ne sont pas un aléa statistique : c'est du travail qui
   n'a pas eu lieu.

ⓘ **La leçon neuve du jour, et elle est désagréable** : j'ai commis **deux fois
la même erreur de prévision** — annoncer que des compteurs de jours atteindraient
10 j à une date (§7.2), exactement comme le 28/10, démenti le 30/10. **Et j'avais
écrit la leçon moi-même.** ⇒ **Une leçon écrite et non appliquée ne vaut rien.
Désormais : aucune date de franchissement annoncée pour un compteur de jours de
position, jamais, dans aucun sens.**
ⓘ **La bonne nouvelle de méthode** : les **réserves** que j'avais écrites le
04/11 ont toutes servi — sur R2, sur `agrume/grille`, sur le swap, sur le 57014.
**Ce qui marche, c'est de dater les affirmations et de les relire.**

## 14. Respect des règles

✅ **VPS en LECTURE SEULE, pleine et entière.** Aucun `systemctl`
start/restart/daemon-reload, aucun `enable`, **aucun SQL joué**, aucun rsync,
rien écrit dans `~/balise-watch` ni dans `/etc`, **aucun fichier créé sur le
VPS** (le script Jira est passé par l'entrée standard, `bash -s`, et n'a jamais
touché le disque du VPS). ⓘ Seules exceptions, qui sont le fonctionnement normal
du code de production : le `controle_quotidien.py --verbeux` relancé à la main
(il ne fait que lire) et les lectures `journalctl` / `systemctl show`.
✅ **Aucun secret lu par valeur.** `~/.balise-watch-alertes.env` a été **sourcé**
(`set -a; . …; set +a`) pour les appels Jira, et le seul `grep` dessus porte sur
le **nom** `BW_DISCORD_WEBHOOK_URL` (`grep -c`, qui ne rend qu'un **compte**).
`bw_jira.sh` passe par `curl -K -`, jamais `-u`.
✅ `10-timeout-s3.conf` **non touché** ; remontée du garde **non lancée**, et
seulement **décrite** (§5.3).
✅ `controle_quotidien.sh` **non touché**, son `$ETAT` conservé. Les deux
correctifs du §3.4 restent **proposés**, pas écrits.
✅ **Trois commentaires posés, vérifiés par GET avant ET après.** ⛔ **Aucun
ticket créé, fermé, rouvert ni transité.** ⛔ **Aucun motif créé**, et les deux
dont le critère était en jeu ne sont **pas** remplis (§1, §9).
✅ **Desktop Commander exclusivement** pour fichiers et shell, du début à la fin.
✅ **Lire avant d'écrire** : `git log --since=midnight` dans les **deux** dépôts
(**aucun commit**) ; `project_read` du 07/11 (**absent ⇒ création**), du 06/11 et
du 05/11 (**absents ⇒ matins sautés**) et du 04/11 (**lu en entier**) ;
`notes-projet/README.md` relu ; **note en section horodatée**.
✅ **Miroir git déposé et commité en local**, depuis la **racine** du dépôt
serveur. ⛔ **Aucun `git push`.**
⛔ **Les quatre miroirs en souffrance (24/10, 26/10, 01/11, 04/11) sont
vérifiés et NON arrangés. Rien n'a été fabriqué après coup.**

## 15. ⓘ Outillage — ce qui a marché

1. ✅ **`SSH_AUTH_SOCK` manquant** (piège n°1) : confirmé une onzième fois,
   correctif bon du premier coup.

   ```
   export SSH_AUTH_SOCK="$(launchctl getenv SSH_AUTH_SOCK)"
   ```

2. ✅ **Le lecteur de flux qui perd des lignes** (piège n°2) : contourné d'emblée.
   **Toute sortie dont une ligne compte a été redirigée vers un fichier du Mac
   et relue avec `read_file`.**
3. ✅ **La leçon de méthode du 04/11 a été APPLIQUÉE** : la partie **Jira** a été
   faite **AVANT** les vérifications secondaires (57014 toutes unités, 429 ntfy,
   Discord, mutations, mails). Le pont a tenu, mais s'il était tombé sur ces
   greps, **les trois commentaires étaient déjà posés.** ⇒ ✅ **C'est le bon
   ordre, il est maintenant éprouvé.**
4. ⓘ **Piège neuf, mineur mais à retenir** : `bw-garde-fou-r2` écrit dans **sa
   propre** unité, pas dans `bw-model-score.service`. Un `grep push` sur le seul
   journal de notation fait croire qu'aucun cri n'est parti les 06 et 07/11 —
   alors que les deux sont partis avec un **HTTP 200**. **Toujours lire
   `journalctl -u bw-garde-fou-r2.service` pour les cris R2.**
5. ⓘ Les sorties brutes de ce run sont sur le Mac dans
   `/Users/yann/bw-run-07-11/` (`hist.json`, `ctrl.txt`, `ctrlv.txt`,
   `score3.txt`, `r2.txt`, `r2-0506.txt`, `jira-get.txt`, `jira-verif.txt`,
   `secondaire.txt`, `units.txt`) — **relisibles telles quelles**.
