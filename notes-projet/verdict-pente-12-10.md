# Verdict de pente du 12/10/2026 — **la nuit du double record mémoire**. Le jalon touche **3 444 Mo**, plus haut de toute la série, le coût par ligne **1 730,2 o**, plus haut de quatorze nuits, et le **swap au pic bondit à 2 595,3 Mo** en cassant une bande tenue douze nuits. Le « plus bas de la série » d'hier **n'a pas tenu une nuit**. La durée remonte de 54 s mais c'est de l'**attente** (95 %) et c'est **hors étapes** (90 %). ✅ La purge est **propre pour la cinquième fois d'affilée (5 / 3)**.

## 20:16 (Paris) — routine Balise Watch (tirée à 18:10:56 UTC pour 07:11:05 : **+10 h 59 de retard, pire valeur de la série**), lecture VPS complète, **trois écritures Jira**

**Étape 0 faite.** `git log --oneline --since=midnight` :

- dépôt serveur `PWA/balise-watch-server` : **aucun commit du jour**
- dépôt principal `surveillance balise` : **aucun commit du jour**
- `project_read claude/verdict-pente-12-10.md` → le document **n'existait pas**
  (absent de la liste d'ouverture de session, confirmé par l'erreur de lecture)
- `claude/verdict-pente-11-10.md` lu **en entier**
- `notes-projet/README.md` relu — les quatre règles

⇒ **premier et seul run pente du jour. Rien à fusionner, aucun doublon.**

✅ **Le Mac a tenu tout le run** : onze commandes `ssh`, trois POST Jira, six GET, les écritures locales.

## 1. Les nuits, bout à bout

| | 07/10 | 08/10 | 09/10 | 10/10 | 11/10 | 12/10 |
|---|---|---|---|---|---|---|
| durée | 5 227 s | 5 228 s | 5 192 s | 5 318 s | 4 975 s | **5 029 s (+54)** |
| marge | 2 873 | 2 872 | 2 908 | 2 782 | 3 125 | **3 071 (−54)** |
| marge en % du garde | 35,5 % | 35,46 % | 35,90 % | 34,35 % | 38,58 % | **37,91 %** |
| `cpu_s` | 4 244,9 | 4 257,9 | 4 199,5 | 4 237,7 | 4 019,1 | **4 021,9 (+2,8)** |
| jalon max | 3 420 Mo | 3 429 | 3 356 | 3 394 | 3 321 | **3 444 (+123) ⛔ RECORD** |
| au-dessus du seuil | +620 | +629 | +556 | +594 | +521 | **+644 ⛔ RECORD** |
| swap au pic | 2 127,7 | 2 267,1 | 2 145,1 | 2 088,1 | 2 129,5 | **2 595,3 (+465,8) ⛔ RECORD** |
| pages sorties | 2 369 940 | 2 556 336 | 2 241 569 | 2 487 135 | 2 501 165 | **2 514 657 (+13 492)** |
| pic système | 3 617,2 | 3 602,9 | 3 615,2 | 3 608,5 | 3 619,9 | **3 616,1 (−3,8)** |
| fenêtre rejouée | 2 088 602 | 2 089 691 | 2 089 138 | 2 088 809 | 2 087 981 | **2 087 197 (−784)** |
| o / ligne rejouée | 1 717,0 | 1 720,6 | 1 684,4 | 1 703,8 | 1 667,8 | **1 730,2 (+62,4) ⛔ RECORD** |
| `n_57014` | 0 | 0 | 0 | 1 (hors purge) | 0 | **0** |
| lancement / résultat | timer/success | ↳ | ↳ | ↳ | ↳ | **timer/success** |

Nuit **comparable** : `lancement=timer`, `exec_status=0`, `oom=0`,
`result=success`, **05:57:06 → 07:21:10**, `source=run.sh`,
`chevauchement_reduit=true`. Rien à écarter.
ⓘ Le départ est passé de 06:00:06 à **05:57:06** : c'est le timer de notation
qui a glissé (`bw-model-score.timer` tiré lundi à 05:57:05, prochain mardi
**05:55:04**), exactement comme la note du 11/10 l'annonçait. **Rien d'anormal.**

**Le contrôle de 07:30 a tiré à 07:30:15 et s'est TU** :

```
ⓘ 74 relevé(s), 53 comparable(s) ; durée : 10 points, pente -55 s/nuit ;
  mémoire : 10 points, pente -53 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate/négative, ou échéance hors horizon
```

⚠️ **TROISIÈME MATIN DE SUITE OÙ IL ANNONCE EXACTEMENT −55 s/nuit ET
−53 Mo/nuit** — le 10/10 (durée au plus haut, marge au plus bas), le 11/10
(durée au plus bas depuis le 05/10) et ce matin (jalon mémoire au record
absolu). **Trois situations opposées, deux chiffres identiques.** Ce n'est pas
une validation de l'indicateur, c'est son aveuglement : il est le **25e centile
des différences** et ignore par construction les deux plus grosses hausses de
la fenêtre.

⇒ **Aucun jeton du jour posé par le contrôle.** Vérifié dans les **deux**
dossiers : `/var/lib/bw-model-verif` porte `cri.jira.bw-pente-duree` du 17/09,
`…memoire` du 23/09, `…purge-57014` du 06/10 ; `$HOME/.balise-watch-etat-alertes`
portait `duree` du 07/10 et les deux autres du **11/10**. **`bw_jira_signaler`
était donc libre sur les trois motifs.**

## 2. ⛔ Mémoire : **DOUBLE RECORD**, et le plus bas d'hier démenti en une nuit

```
⛔ après le rejeu d'archive            : 3 024 Mo  (3 038 le 11/10)  ← −14
⛔ après le score par régime           : 2 830 Mo  (2 894 le 11/10)  ← −64
⛔ après l'oubli de la fenêtre rejouée : 3 444 Mo  (3 321 le 11/10)  ← +123, RECORD
```

Les **trois** jalons restent au-dessus du seuil, **deuxième nuit de suite**. Le
jalon max est le **plus haut de toute la série** : le précédent record était
**3 429 Mo** (08/10), et l'excédent sur le seuil, **+644 Mo**, n'avait jamais
été atteint.

⚠️ **LA PRESSION SE CONCENTRE SUR UN SEUL JALON.** Huit des neuf jalons
reculent ou tiennent ; seul l'oubli de la fenêtre rejouée monte : agrégat
quotidien **1 823 (−30)**, oubli fenêtre glissante **1 736 (−14)**, oubli du
chemin J-0 **958 (−21)**, relecture de l'archive **825 (−8)**, garde-fou de
position **1 209 (−9)**, mélange multi-modèle **1 197 (−11)**. C'est exactement
le jalon que la **ligne en tuple** vise. ⛔ **Mais c'est UNE nuit — et une
lecture très proche (« la pression se concentre », note du 10/10) a été
démentie dès le lendemain.** À revérifier demain avant d'en faire quoi que ce
soit.

⛔ **COÛT PAR LIGNE REJOUÉE : 1 730,2 o — NOUVEAU RECORD HAUT.**

```
29/09 1 671,3 o · 30/09 1 692,6 · 01/10 1 685,6 · 02/10 1 689,2
03/10 1 706,4  · 04/10 1 697,4 · 05/10 1 717,2 · 06/10 1 689,7
07/10 1 717,0  · 08/10 1 720,6 · 09/10 1 684,4 · 10/10 1 703,8
11/10 1 667,8  · 12/10 **1 730,2**
  → +62,4 o/ligne ; fourchette 1 667,8–1 730,2 sur QUATORZE nuits
```

⛔ **CORRECTION EXPLICITE DE LA NOTE DU 11/10.** Elle annonçait « le plus bas de
toute la série » et « le précédent plus bas tenait depuis douze nuits ». **Le
plus bas (1 667,8) et le plus haut (1 730,2) de la série sont maintenant DEUX
NUITS CONSÉCUTIVES.** La fourchette est de **±1,9 % autour de 1 699** sur
quatorze nuits : **toujours aucune pente, ni à la hausse ni à la baisse.**
⇒ **Neuvième usage en quinze jours de la leçon « une nuit ne fait pas une
pente »** — et cette fois c'est la note de la veille qui en fait les frais,
exactement comme la consigne le demandait.

**Calcul à taux constant.** Au taux du **11/10** (1 667,8 o) la fenêtre de cette
nuit aurait rendu **3 319,7 Mo** ; elle rend **3 444**. Les **+124,3 Mo** sont
donc imputables au **coût par ligne**, pas à la fenêtre — qui ne recule que de
**784 lignes**, soit **−1,2 Mo**. Au taux du **29/09** (1 671,3 o) : **3 326,7 Mo**
— nous sommes **117 Mo au-dessus**.

⛔ **SWAP : RECORD AUSSI, ET LA BANDE DE DOUZE NUITS EST CASSÉE.** Pic
**2 595,3 Mo (+465,8)**, soit **+21,9 %** en une nuit, après douze nuits entre
**2,0 et 2,3 Go**. Pages sorties **2 514 657 (+13 492)**, soit **+0,54 %
seulement**. ⚠️ **Les deux divergent très fortement** : le pic de résidence en
swap bondit sans que la pagination suive. `oom = 0`, pic système **3 616,1 Mo
(−3,8)** — le plafond système, lui, n'a pas bougé.

**Les trois conditions de fermeture de KAN-4 : 1 sur 3**, inchangé. Jalon
mesurément retombé → **NON** (record absolu). Swap au pic ≈ 0 → **NON** (record
absolu). Contrôle muet sur `bw-pente-memoire` → **OUI**. ⇒ **le ticket reste
ouvert.**

**Rien de déployé côté mémoire depuis `af25efb` (21/09) — 22e nuit sans
levier.** Remède inchangé : la **ligne en tuple** (`enquete-pente-10-09.md`
§2.6, ≈ −1 030 o/ligne), après la mesure `tuple` vs `namedtuple` à la sonde.
L'élagage de `units` avait rendu −124 Mo au lieu de −1 500 : **les gains sont
dans la structure**, et le record de cette nuit le confirme.

## 3. ⚠️ Durée : +54 s, mais c'est de l'**attente** (95 %) et c'est **hors étapes** (90 %)

```
durée  4 975 → 5 029 s  (+54)
marge  3 125 → 3 071 s  (−54)  ⇒ 38,58 % → 37,91 % du garde de 8 100 s
cpu_s  4 019,1 → 4 021,9 (+2,8)
```

⚠️ Le processeur ne rend que **2,8 s** des 54 s d'horloge : **95 % de la hausse
n'est pas du calcul**, c'est de l'**attente**. Et pourtant `n_57014 = 0` et
**aucun 57014 nulle part** dans le journal : **l'attente de cette nuit n'est pas
un `statement timeout`.** On ne sait pas où elle est.

Série : `5 157 · 5 227 · 5 228 · 5 192 · 5 318 · 4 975 · **5 029**`. La durée
**oscille** dans une bande de 4 821 à 5 318 s depuis huit nuits (**±5 %**) : ni
plateau, ni dérive, ni repli.

| étape | 09/10 | 10/10 | 11/10 | 12/10 |
|---|---|---|---|---|
| `regime` | 1 751,4 | 1 809,1 | 1 648,5 | **1 664,7 (+16,2)** |
| `glissant` | 988,2 | 964,4 | 974,1 | **958,0 (−16,1)** |
| `stabilite` | 322,5 | 358,7 | 312,0 | **309,0 (−3,0)** |
| `rejeu` | 78,3 | 85,6 | 73,4 | **81,5 (+8,1)** |
| somme des quatre | 3 140,4 | 3 217,8 | 3 008,0 | **3 013,2 (+5,2)** |
| hors étapes | 2 051,6 | 2 100,2 | 1 967,0 | **2 015,8 (+48,8)** |

⚠️ **90 % DE LA HAUSSE EST HORS ÉTAPES.** Les quatre étapes instrumentées se
compensent entre elles à **+5,2 s** près.

**Le hors-étapes repart à la hausse — la question posée hier est tranchée.**

```
1 924,7 (06/10) · 1 984,0 · 1 991,2 · 2 051,6 · 2 100,2 (10/10) · 1 967,0 (11/10) · 2 015,8 (12/10)
```

Il avait monté **quatre nuits sans un repli** (+175,5 s), puis rendu 133,2 s en
une nuit. Il en **reprend 48,8**, soit 37 % de ce qu'il avait rendu, et **reste
sous son pic du 10/10**. ⇒ **le repli d'hier était un point, pas un
retournement** ; mais la série monotone **reste cassée**, donc ce n'est pas non
plus une dérive de fond. Le hors-étapes **oscille comme le reste**, en étant le
poste qui bouge le plus. ⛔ **Et ce bloc n'est toujours pas instrumenté** :
publication, Murphy, événements, pression, duels, purge — six postes, aucun
jalon de temps. **Deux nuits de suite il porte l'essentiel du mouvement** (90 %
cette nuit, 39 % hier en sens inverse) et on ne sait pas lequel des six bouge.

**Découplage temps / volume : cette nuit les deux vont dans LE MÊME SENS**, pour
la première fois depuis quatre nuits. `lignes_regime` **127 853 (+479, +0,4 %)**
pour un temps de `regime` à **+1,0 %**. `lignes_score_zone` **138 363 (+462)**,
`lignes_glissant` **10 510 (−17)**, `lignes_daily` **69 378 (+123)**. ⇒ le
découplage des quatre nuits précédentes **n'est pas une loi** : le volume
n'explique pas la durée, mais il ne la contredit pas toujours.

Coût par ligne de `regime` (ms) :

```
13,39 (01/10) · 13,24 · 14,02 · 13,67 · 13,53 · 15,07 · 14,86 · 14,87 · 13,99 · 14,42 · 12,94 (11/10) · 13,02 (12/10)
  → +0,08 : UNE HAUSSE, la première depuis le recul franc d'hier
```

⚠️ **`bw-regime-sensibilite` : compteur à 1 / 2.** L'arbitrage unique du 07/10
exige **deux hausses consécutives** du coût par ligne. Le compteur, remis à 0
hier, passe à **1**. **Le critère n'est pas rempli, rien n'est créé, la question
n'est pas posée à Yann.** ⇒ **à surveiller demain : une seconde hausse
l'enverrait à l'arbitrage.**
Coût par ligne de `glissant` : **91,15 ms** (92,54 le 11/10, **−1,4**).

**Remontée du garde : NON lancée, NON demandée.** Le contrôle n'en propose
aucune (pente négative, `proposition()` n'est pas atteinte). Garde actuel
**8 100 s (135 min)** pour un run de **83,8 min**. ⛔ `10-timeout-s3.conf`
**n'a pas été touché.**

**KAN-3 : réouverture NON demandée.** +54 s, marge encore à 37,91 %, série
monotone du hors-étapes toujours cassée. Rien ce matin ne la justifie.

## 4. ✅ Purge : **CINQUIÈME nuit propre d'affilée — KAN-5 est à 5 / 3**

```
→ purge model_score_zone : 129 534 ligne(s) effacée(s) en 8 tranche(s)
ⓘ purge model_character : rien avant le 2027-02-04 (première écriture
  2026-08-08, rétention 180 j) — aucune requête lancée.
```

Le bloc ne porte **aucun avertissement au-dessus de ces deux lignes** :

- **aucune TRANCHE à 57014** (aucun `?as_of=eq.J&regime=eq.R` en HTTP 500)
- **aucune SONDE** (« plus vieille journée illisible » absente)
- **aucun « des lignes RESTENT »** — donc rien ne reste en base
- nombre de lignes **lisible** (129 534), **8 tranches** comme les quatre nuits
  précédentes
- `n_57014 = 0` au registre, et **aucun 57014 nulle part** dans le journal

| nuit | état du bloc purge | compteur |
|---|---|---|
| 07→08 (2026-10-08) | `n_57014 = 0`, propre | 1 |
| 08→09 (2026-10-09) | propre, 129 650 l. / 8 tr. | 2 |
| 09→10 (2026-10-10) | propre, 129 594 l. / 8 tr. | 3 |
| 10→11 (2026-10-11) | propre, 129 233 l. / 8 tr. | 4 |
| 11→12 (2026-10-12) | **propre, 129 534 l. / 8 tr.** | **5** |

⇒ ⛔ **LA CONDITION DE FERMETURE EST DÉPASSÉE : 5 / 3.** Elle n'est **pas**
appliquée : la fermeture se décide avec Yann. **C'est la question n° 1 du
matin, pour le TROISIÈME jour de suite.**
ⓘ Les **301 lignes** d'écart avec hier **ne sont pas un signal** : le volume
effacé suit le volume de la journée purgée (≈ 125 000–134 000).

✅ **`bw_character_avance` est passé proprement** : **430 150 accumulateurs
avancés sur 430 150 envoyés**, sans reprise. Le 57014 apparu là le 10/10 est
absent pour la deuxième nuit.

⚠️ **Les deux réserves sont inchangées et toujours valides.** (1) Le `statement
timeout` **change de requête** plutôt que de disparaître — le 10/10 l'a montré,
et deux nuits sans lui ne démontrent rien. (2)
**`diagnostic_base_sous_tension_2026-09-29.sql`** (lecture seule, 9 blocs, SQL
Editor) **n'a jamais été joué : treize jours.** Rappel : trois nuits à 0
d'affilée (03, 04, 05/10) avant le retour du 06/10.
⇒ ⚠️ **Si KAN-5 est fermé, il ferme « la purge par tranches expire », pas « la
base est sous tension ». Le second motif n'a toujours pas de ticket.**

✅ Le contrôle s'est tu sur ce motif, et c'est **correct** : depuis le 07/10,
`constats()` lit `score.log` via `bilan_purge()`. Le faux « purge en échec » du
06/10 ne s'est pas reproduit : **sixième nuit.**

## 5. ⚠️ Position : **mêmes 3 confirmées, pas de front, pas de cri** — et les sept suivantes sont à **7 j**

```
⛔ position : 11 balise(s) divergent du gel (10 j lus), dont 3 CONFIRMÉE(S) (≥ 10 j)
   ⛔ pioupiou:2171          38 925 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE · Windbird 2171
   ⛔ pioupiou:1388           2 363 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE · Décollage Serre Michèle
   ⛔ infoclimat:STATIC0491   1 159 m · 10 j · nœud 0,01 CHANGE · infoclimat STATIC0491
   ·  1378 (15 778 m) · 367 (6 764) · 1417 (829) · 1375 (747) · 1722 (631) · 1562 (481) · 1678 (422) — toutes à 7 j
   ·  pioupiou:1333          87 693 m ·  6 j  ← continue de reculer (10 → 8 → 7 → 6)
```

ⓘ **Le compte des confirmées est inchangé (3) ⇒ pas de front ⇒ pas de cri** —
cohérent avec l'arbitrage « à front, pas à état ». Aucun `push` nulle part dans
le journal : il n'y avait rien à crier.

⛔ **LES SEPT BALISES SONT PASSÉES À 7 j : elles franchiront 10 j LE 15/10.** La
progression est régulière (5 → 6 → 7 j) et l'échéance annoncée les 09, 10 et
11/10 **tient**. Ce jour-là le compte passerait de **3 à 10**, donc **un cri à
front**. ⇒ **IL RESTE TROIS JOURS.**
**Geste attendu de Yann** : trancher `2171` (38,9 km), `1388` (2 363 m),
`STATIC0491` (1 159 m), statuer sur `1333` qui **sort du lot** (10 → 8 → 7 →
6 j), puis poser `position_suspecte` + `position_note` sur `station_zone` par
`.sql`.
ⓘ Question toujours ouverte depuis le 01/10 : **faut-il que le cri recrie** pour
une balise qui reste confirmée ?

## 6. ⚠️ Le second canal du téléphone reste muet

**`BW_DISCORD_WEBHOOK_URL` est TOUJOURS ABSENTE du `.env`.** 25 variables
relevées par leur **nom seul** (`sed -E "s/=.*//"`, aucune valeur lue), les
mêmes qu'hier. Fichier **inchangé depuis le 13/09 18:08**. ⇒ `bw_push_discord`
reste **codé, testé, muet**. `~/installer-webhook-discord.sh` attend toujours
Yann : **30e jour**.

ⓘ **Le correctif `--ipv4` du 07/10 n'a pas été sollicité cette nuit** (aucun ⛔
à front ⇒ aucun push). **Aucun 429 nulle part.** Trafic conforme à la normale.

## 7. ✅ Témoins du mélange : **la série « sous la barre » est interrompue** — et le motif Jira n'a pas lieu d'être

```
⛔ témoins du mélange : sur 7 568 balise-jours×échéance, le mélange fait
   3,3197 km/h contre 3,372 pour le meilleur membre a priori
   (gain 1,6 %, mélange devant dans 50,1 % des cas) ;
   contre la moyenne UNIFORME, sur 1 126 : 3,4857 vs 3,6575 (gain 4,7 %)
```

```
gain contre le MEILLEUR MEMBRE : 7,4 % → 5,5 → −0,6 (07/10) → +2,5 → −1,2 → −0,1 → −0,0 (11/10) → **+1,6 (12/10)**
« devant » dans : 49,2 % → 50,1 (09/10) → 49,1 → 49,2 → **50,1 %**
gain contre la moyenne UNIFORME : 6,0 % → 4,9 → 4,8 → 3,1 → 4,8 → 3,2 → 3,4 → **4,7 %**
```

⚠️ **CORRECTION DE LA NOTE DU 11/10.** Elle concluait « le mélange n'apporte plus
rien face au meilleur membre a priori » et « la série a confirmé deux fois ».
**Cette nuit le gain remonte à +1,6 % et le mélange repasse devant dans plus
d'une fois sur deux.** La moyenne des six dernières nuits est **+0,37 %** :
l'indicateur **oscille autour de zéro**, il ne **décline** pas. ⇒ ⛔ **la série
n'a PAS confirmé : il ne faut PAS créer de motif Jira.** Rien n'a été créé.

ⓘ **L'erreur absolue chute de 24,9 %** (4,4187 → 3,3197 km/h) : journée
**beaucoup moins venteuse**. ⚠️ C'est la réserve symétrique de celle du 07/10 :
le gain remonte sur une journée facile, comme il avait chuté sur une journée
difficile. **L'indicateur dépend de la météo du jour autant que du mélange** —
c'est peut-être la vraie leçon de ces huit nuits.

✅ Le gain contre la moyenne **uniforme** tient et remonte : **4,7 %**, haut de
la bande 3,1–4,8. Le mélange garde tout son sens contre une moyenne naïve.

ⓘ Composition : 7 974 balise×échéance avec poids sur 30 j de cache — +6 h :
2 645 `bw_mix`, 414 témoins uniformes, 191 sans poids ; +24 h : 2 549 / 392 /
101 ; +48 h : 2 554 / 414 / 264 (64,2 s).

## 8. Le reste du journal

- ✅ **Self-test du scoring : VERT** (lot S3, aucune lecture réelle, aucune
  écriture). Écart des deux mélanges : `mse_comb` 17,841 contre `mse_comb_vec`
  17,841 (**+0,00 %**), skill contre la climatologie = 1,0 (`mse_clim` 18,000),
  prévision = observation → `err_vec_med` max 0,000000 km/h.
- ✅ **Stabilité des rangs : τ = 0,742 sur 50 cases** (0,723 / 54 le 11/10 ;
  0,709 / 53 le 10/10 ; 0,751 / 57 le 09/10). **Deuxième hausse de suite**, mais
  le nombre de cases **retombe à 50**, le plus bas de la série (60 → 57 → 53 →
  54 → 50). ⓘ τ monte pendant que l'échantillon maigrit : à suivre, pas à
  conclure.
- ⚠️ **ρ hors [0, 1] : 413 balises sur 3 708** (381 le 11/10, 349 le 10/10, 382
  le 09/10, 307 le 08/10). **C'est le plus haut de la série récente**, et la
  troisième hausse sur quatre nuits. Les quatre nuits d'amélioration de fin
  septembre restent perdues.
- ⚠️ **5 écarts au recalcul indépendant** (6 le 11/10, 5 le 10/10, 5 le 09/10)
  — journée recalculée **2026-10-11**. **Tous en `fcstagrume`** et tous de la
  **même signature** : « ici None, base X — 0 ou 1 h appariée ici (< 6) mais la
  base porte une ligne » : `aemet:9784P` (agrume +48 h), `infoclimat:000GF`
  (agrume_pi +6 h), `mf:05070003` (agrume +6 h), `infoclimat:000W1`
  (agrume +6 h), `mf:30176002` (agrume_pi +24 h). ⓘ **Cinquième nuit de suite la
  même signature** (4 · 5 · 5 · 6 · 5) ; le compte ne monte plus. Les balises
  concernées **changent chaque nuit** : ce n'est pas un lot fixe, c'est un
  désaccord systématique sur le seuil des 6 heures appariées.
- **Murphy** : 66 247 triplets, 64 252 décomposés, 266 balises tenues dehors
  (doublon ou position suspecte), 1,1 s. Deux `TIMING` relevés
  (`chmi_aladin_central_europe_2km` +48 h, `dmi_harmonie_arome_europe` +24 h).
- **Duels appariés** : lead 6 → 65 193 lignes depuis le 12/09 (989 retirées) ;
  lead 24 → 23 993 lignes (377 retirées). ⓘ Cumul tronqué par la rétention 30 j.
- **Événements** : **31 311 combinaisons publiables**, 29 509 écartées sous le
  quorum de 8 ; 3 440 balises zonées, 1 418 cases fines dont 731 à moins de
  2 balises.
- **Pression** : 17 813 lignes, 682 points de prévision portent `pmsl`,
  **856 appariées** (médiane 18,1 km) ; refusées : 206 hors rayon, 32 hors Δz,
  4 trop hautes.
- **Référence combinée** : **k médian 0,145** sur 3 708 balises / 3 818
  climatologisées (231,6 s de climatologie horaire).
- **Antécédent du biais** : 67 246 couples sur 30 j de cache (74,2 s) ;
  antécédent fin : 66 879 couples avec au moins une cellule qui parle.
- **Témoins du corrigé** : le vrai antécédent gagne **16,1 %**, celui d'une
  AUTRE balise **−3,8 %** ⇒ part imputable au site **19,9 points** (sur 9 153
  balise-jours). Témoin FIN : le S2 gagne **18,0 %** sur le brut, le fin **+9,7
  points** de plus sur le S2 contre **−2,4** aux cellules tournées ⇒ part du
  secteur et de l'heure **12,2 points** (sur 4 946).
- **Publication** : `model_scores.json` 121 182 Ko, `model_scores_light.json`
  7 312 Ko (535 Ko gzippé) ; manches : 45 nuits suivies depuis le 24/08, 702
  cases zone×lead×modèle avec au moins une manche gagnée. R2 : 4 écritures
  (plafond 10), 0 lecture, 0 suppression, 166,6 Mo.
- **Accumulateurs** : 5 474 entrées écartées (`doublon_de`, lot L17), 318
  antérieures à la naissance de la balise (`notee_depuis`, lot L15-bis) ; 9
  balises nées sous leur identifiant.
- **Observations** : 3 721 balises le jour, 3 725 la veille.
- **`mutations_memoire`** : ⚠️ **QUATRIÈME nuit sans aucune ligne au journal.**
  Le relevé « 3 mutations non vues (2, 5, 13) » ne peut pas être revérifié ;
  dette antérieure, **statut inchangé faute de mesure**.
- `✅ terminé (701 789 lignes écrites en base)` ; `registre : 1 ligne écrite
  (2026-10-12, 5 029 s, jalon max 3 444 Mo, swap 2 595,3 Mo)`.
- ⓘ **La ligne de collecte n'a pas été relevée ce run** (le grep ne l'a pas
  ramenée) : rien n'est affirmé sur le quota ni sur les groupes vides.

## 9. ✅ Les tickets : état vérifié par GET **avant** et **après**, trois commentaires

GET `/rest/api/3/issue/<clé>?fields=summary,status,comment` avant écriture,
HTTP 200 sur les trois. Les trois sujets sont **ceux relevés le 07/10**,
inchangés.

| ticket | statut | comm. avant | canal utilisé | comm. après |
|---|---|---|---|---|
| **KAN-3** `bw-pente-duree` | **Terminé** / `done` | 20 | `bw_jira_commenter KAN-3` (**délibéré**) | **21** ✅ |
| **KAN-4** `bw-pente-memoire` | **À faire** / `new` | 31 | `bw_jira_signaler bw-pente-memoire` | **32** ✅ |
| **KAN-5** `bw-purge-57014` | **À faire** / `new` | 14 | `bw_jira_signaler bw-purge-57014` | **15** ✅ |

**Ce que chaque commentaire porte :**

- **KAN-4** — jalon **3 444 Mo, record absolu**, +644 au-dessus du seuil ; les
  trois jalons au-dessus pour la 2e nuit ; **huit des neuf jalons reculent, seul
  celui de la fenêtre rejouée monte** (avec la réserve explicite « c'est une
  nuit ») ; coût par ligne **1 730,2 o, record haut**, et **démenti explicite du
  « plus bas de treize nuits » d'hier** ; calcul à taux constant (+124,3 Mo
  imputables au coût par ligne, −1,2 Mo à la fenêtre) ; **swap record 2 595,3 Mo
  et la divergence pic/pages** ; les trois conditions de fermeture **1 sur 3** ;
  22e nuit sans levier ; les six autres jalons ; `mutations_memoire` non
  mesurable ; **le contrôle qui annonce −53 Mo/nuit pour la 3e fois de suite**.
- **KAN-5** — bloc purge **propre pour la 5e nuit** (129 534 l. / 8 tr., aucune
  tranche à 57014, aucune sonde, aucun « RESTENT ») ; **compteur 5 / 3** ;
  `bw_character_avance` passé proprement (430 150 / 430 150) ; les **deux
  réserves** (le timeout change de requête, le `.sql` jamais joué — treize
  jours) ; **la fermeture posée à Yann, non appliquée** ; et le fait qu'elle ne
  fermerait que la purge, pas la base sous tension.
- **KAN-3** — durée **+54 s** (5 029 s, marge **37,91 %**) ; **95 % de la hausse
  est de l'attente** (cpu +2,8 s) **et pourtant aucun 57014** ; **90 % est hors
  étapes** ; le hors-étapes qui **repart à la hausse** sans reprendre sa série
  monotone ; le découplage temps/volume **qui ne tient pas cette nuit** ; coût
  par ligne de `regime` **13,02 ms (+0,08) ⇒ compteur `bw-regime-sensibilite`
  à 1 / 2** ; l'aveuglement du 25e centile **et les −55 s/nuit annoncés trois
  matins de suite dans trois situations opposées** ; remontée du garde **non
  lancée, non demandée** ; **réouverture non demandée**.

⛔ **Aucune création, aucune transition, aucune réouverture, aucune fermeture.**
Les trois statuts sont **identiques** après écriture (revérifiés par GET).

ⓘ **Les deux canaux ont été employés comme arbitré le 07/10.** Le contrôle
s'étant tu, les jetons du jour étaient **libres** : `bw_jira_signaler` a servi
pour les deux motifs ouverts et a **posé les jetons** (`cri.jira.bw-pente-memoire`
et `cri.jira.bw-purge-57014` datent maintenant du **12/10 20:16**).
`bw_jira_commenter` a servi pour KAN-3, en « Terminé » — un `bw_jira_signaler`
sur ce motif **aurait créé un ticket neuf**. ✅ Vérifié après coup :
`cri.jira.bw-pente-duree` est **toujours daté du 07/10**, le canal délibéré ne
touche pas le jeton du jour.

ⓘ **Technique de l'envoi** : les trois corps ont été écrits sur le **Mac**
(`/tmp/bw-12-10/`), encodés en base64 et passés au VPS **par l'entrée standard
de `ssh`**, décodés dans une variable shell. **Aucun fichier n'a été déposé sur
le VPS, pas même dans `/tmp`.**

## 10. Ce qui a été touché

**VPS — règle de LECTURE SEULE pleine et entière, respectée.** Onze commandes
`ssh`, toutes en lecture sauf les trois POST Jira : `date -u`, `tail -n 3` du
registre, `systemctl list-timers`, `journalctl` du contrôle, quatre passes de
`journalctl -u bw-model-score.service` avec `grep`, `controle_quotidien.py
--verbeux`, `sed` dans `bw_jira.sh`, `ls -la` des deux dossiers d'état,
`sed -E "s/=.*//"` sur le `.env`, et **six GET** Jira (trois avant, trois après).
**Aucun `systemctl start/restart/daemon-reload`, aucun `enable`, aucun SQL joué,
aucun `rsync`, rien écrit dans `~/balise-watch` ni dans `/etc`, aucun fichier
déposé, pas même dans `/tmp`.**
⚠️ `controle_quotidien.py --verbeux` a été **relancé à la main** : c'est une
lecture (il n'écrit son jeton que s'il parle, et il s'est tu) — vérifié, les
jetons de `/var/lib/bw-model-verif` sont **inchangés** après la relance.
**Aucun secret lu par valeur** : le `.env` est **sourcé** (`set -a; . …;
set +a`) pour les GET et lu **par noms de variables seuls**. `bw_jira.sh` passe
par `curl -K -`, jamais `-u`.
**Écritures Jira : trois commentaires** (voir §9).

**Mac** : trois corps de commentaire dans `/tmp/bw-12-10/` (fichiers de
travail), cette note dans `notes-projet/verdict-pente-12-10.md`. **Un commit
local**, depuis la **racine du dépôt serveur**. **Pas de `git push`.**

**Projet Claude** : cette note, **créée** (`project_read` a rendu « No doc »
avant écriture).

## 11. ⛔ L'horaire de la routine : **+10 h 59, DE LOIN la pire valeur de la série**

Programmée pour **07:11:05 UTC**, tirée à **18:10:56 UTC**.

```
02–03/10  AUCUN TIR
04–06/10  retard jusqu'à 4 h 10
07/10     à l'heure
08/10     +2 h 10
09/10     +6 h 40
10/10     +2 h 13
11/10     +5 h 51
12/10     +10 h 59   ← PIRE, et de loin
```

ⓘ **Le VPS est à l'heure, et il n'y est pour rien** : notation à **05:57:05**
(prochaine mardi 13/10 **05:55:04**), contrôle à **07:30:15** (prochain mardi
**07:30:46**). **Le trou est côté planification de la routine.**
⚠️ **Le retard devient le premier risque du dispositif.** Six matins sur onze
ont dérivé, deux n'ont pas tiré, et le retard a déjà emporté la moitié du
travail les 09 et 10/10. Cette fois le Mac était allumé un lundi soir — **c'est
de la chance, pas une garantie.** Un tir à l'heure vaudrait toujours mieux
qu'un run réparé.

## 12. Ce qui reste — et ce qui demande Yann

**Décisions, par ordre d'urgence :**

1. ⛔ **TRANCHER LES CAS DE POSITION — il reste TROIS JOURS.** Les sept balises
   sont passées à **7 j** ; elles franchiront **10 j le 15/10** et le compte
   passera de **3 à 10**, avec un cri à front. À trancher : `2171` (38,9 km),
   `1388` (2 363 m), `STATIC0491` (1 159 m), **et `1333` qui sort du lot**
   (10 → 8 → 7 → 6 j). Ensuite `position_suspecte` + `position_note` sur
   `station_zone` par `.sql`.
2. ⛔ **FERMER KAN-5 ? Le compteur est à 5 / 3** (troisième jour où la question
   est posée). Cinq nuits consécutives sans 57014 dans le bloc purge, avec un
   nombre de lignes lisible à chaque fois. ⚠️ **Deux réserves inchangées** : le
   `statement timeout` a **changé de requête** le 10/10, et le
   `diagnostic_base_sous_tension` n'a **jamais été joué** (treize jours). La
   cause profonde n'est pas mesurément réglée, seulement le symptôme sur la
   purge. *Un ticket fermé à tort vaut moins qu'un ticket ouvert.* ⇒ **Et s'il
   est fermé, il faudra dire où va « la base est sous tension », qui n'a pas de
   ticket.**
3. ⛔ **La mémoire est le dossier qui empire.** Jalon **record absolu**
   (3 444 Mo), coût par ligne **record haut** (1 730,2 o), swap **record**
   (2 595,3 Mo) : les trois records de la série sont tombés **la même nuit**, et
   la **22e nuit sans levier déployé** depuis `af25efb` (21/09). La **ligne en
   tuple** (≈ −1 030 o/ligne) reste le remède, après la mesure `tuple` vs
   `namedtuple` à la sonde. ⚠️ Rien de tout cela ne fait une **pente** — la
   fourchette du coût par ligne est de ±1,9 % sur quatorze nuits — mais le
   plafond monte.
4. ⛔ **Jouer `diagnostic_base_sous_tension_2026-09-29.sql`** (lecture seule,
   9 blocs, SQL Editor). **Treize jours d'attente**, et c'est la réserve n° 2 de
   la fermeture de KAN-5.
5. ⛔ **L'HORAIRE DE LA ROUTINE : +10 h 59**, pire valeur de la série (voir §11).
   Le VPS est à l'heure.
6. ⛔ **Lancer `~/installer-webhook-discord.sh`.** `BW_DISCORD_WEBHOOK_URL`
   toujours absente, **30e jour**. ntfy reste **seul**, avec son quota anonyme
   dépendant du voisinage /64 d'OVH.
7. ⚠️ **Instrumenter le bloc hors étapes de `run.sh` ?** **La demande reprend de
   la force** : deux nuits de suite le hors-étapes porte l'essentiel du
   mouvement (90 % cette nuit), et on ne sait pas lequel des six postes bouge.
   C'est une écriture dans `run.sh` : la décision est à toi.
8. ✅ **Un motif Jira pour les témoins du mélange ? NON — la question se
   referme.** Le gain contre le meilleur membre **remonte à +1,6 %** et le
   mélange repasse devant dans 50,1 % des cas : la série **n'a pas confirmé**,
   elle **oscille autour de zéro** (moyenne +0,37 % sur six nuits). ⓘ Et elle
   suit la météo du jour : l'erreur absolue a chuté de 24,9 %.
9. ⓘ **Un champ de bilan de purge au registre ?** (question du 08/10.) Avec
   `lignes_effacees` et `tranches`, le §4 tiendrait en trois lignes et le
   compteur de KAN-5 se lirait sans ouvrir un journal.
10. ⓘ **Le cri de position : à front ou à état ?** (question du 01/10.) **Faut-il
    un motif Jira pour une panne de canal ?** (question du 30/09.) **Un motif
    pour `bw_character_avance` ?** — il n'est pas revenu, la question est moins
    pressante, pas close.

**Ce que la surveillance regardera au prochain run :**

11. **La mémoire** : **1 730,2 o/ligne confirme-t-il**, ou était-ce le symétrique
    du 1 667,8 d'hier ? Et le **swap retombe-t-il dans la bande 2,0–2,3 Go**,
    ou le plancher a-t-il monté d'un étage ? C'est la question n° 1 du dossier.
12. **La concentration sur un seul jalon** : huit jalons sur neuf ont reculé
    cette nuit. **Se reproduit-elle ?** Si oui, la ligne en tuple vise le bon
    endroit.
13. **Le coût par ligne de `regime`** : **1 / 2**. Une **seconde hausse
    consécutive** enverrait `bw-regime-sensibilite` à l'arbitrage de Yann.
14. **Le hors-étapes** : 2 015,8 après 1 967,0 et 2 100,2. **Reprend-il sa série
    monotone**, ou continue-t-il d'osciller ?
15. **KAN-5** : une **sixième** nuit propre, ou le retour du 57014 ?
16. **La position, le 15/10** : le cri à front de 3 → 10 confirmées.
17. **ρ hors [0, 1]** (413, le plus haut) et **τ** (0,742 sur 50 cases, le plus
    petit échantillon) : séries à surveiller, aucune conclusion.
18. **`mutations_memoire`** : une cinquième nuit muette, ou le retour du relevé ?
