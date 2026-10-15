# Verdict de pente du 15/10/2026 — **la nuit où le plafond mémoire baisse tout seul**. Le coût par ligne rejouée **sort de sa bande de seize nuits, vers le bas** (1 588,8 o, −7,5 %) et le jalon max tombe de 255 Mo. ✅ **Aucun 57014 nulle part** : `model_score_zone` signe sa **huitième nuit propre (8 / 3)** et `model_verif_daily` n'a pas récidivé. ✅ **Le critère `bw-regime-sensibilite` RETOMBE à 0 / 2** — la question de la veille est tranchée par la mesure. ⛔ **ρ hors [0, 1] recule enfin (452, −23)** : la seule série qui montait sans démenti est démentie. ✅ **Et pour la première fois, une échéance annoncée se réalise** : position 2 → 4.

## 16:55 (Paris) — routine Balise Watch (tirée à 14:48:32 UTC pour 07:11:05 : **+7 h 37**), lecture VPS complète, **trois écritures Jira**

**Étape 0 faite.** `git log --oneline --since=midnight` :

- dépôt serveur `PWA/balise-watch-server` : **aucun commit du jour** (dernier : `3f42aca`, la note du 14/10)
- dépôt principal `surveillance balise` : **aucun commit du jour** (dernier : `379cc2f`, 13/10)
- `claude/verdict-pente-15-10.md` **absent** de la liste d'ouverture de session
- `claude/verdict-pente-14-10.md` lu **en entier**
- `notes-projet/README.md` relu — les quatre règles

⇒ **premier et seul run pente du jour. Rien à fusionner, aucun doublon.**

## 1. Les nuits, bout à bout

| | 10/10 | 11/10 | 12/10 | 13/10 | 14/10 | 15/10 |
|---|---|---|---|---|---|---|
| durée | 5 318 s | 4 975 s | 5 029 s | 5 046 s | 5 032 s | **5 051 s (+19)** |
| marge | 2 782 | 3 125 | 3 071 | 3 054 | 3 068 | **3 049 (−19)** |
| marge en % du garde | 34,35 % | 38,58 % | 37,91 % | 37,70 % | 37,88 % | **37,64 %** |
| `cpu_s` | 4 237,7 | 4 019,1 | 4 021,9 | 4 056,7 | 4 029,7 | **4 058,9 (+29,2)** |
| jalon max | 3 394 Mo | 3 321 | **3 444** | 3 422 | 3 416 | **3 161 (−255)** |
| au-dessus du seuil | +594 | +521 | +644 | +622 | +616 | **+361** |
| swap au pic | 2 088,1 | 2 129,5 | **2 595,3** | 2 091,8 | 2 417,0 | **2 226,6 (−190,4)** |
| pages sorties | 2 487 135 | 2 501 165 | 2 514 657 | 2 171 262 | 2 254 634 | **2 918 498 (record)** |
| pic système | 3 608,5 | 3 619,9 | 3 616,1 | 3 595,4 | 3 612,1 | **3 597,2 (−14,9)** |
| fenêtre rejouée | 2 088 809 | 2 087 981 | 2 087 197 | 2 086 539 | 2 085 860 | **2 086 137 (+277)** |
| o / ligne rejouée | 1 703,8 | 1 667,8 | **1 730,2** | 1 719,7 | 1 717,2 | **1 588,8 (−128,4)** |
| incidents mémoire | 3 | 3 | 3 | 2 | 3 | **3** |
| `n_57014` | 1 (hors purge) | 0 | 0 | 0 | 1 (hors purge) | **0** |
| lancement / résultat | timer/success | ↳ | ↳ | ↳ | ↳ | **timer/success** |

Nuit **comparable** : `lancement=timer`, `exec_status=0`, `oom=0`,
`result=success`, **05:58:00 → 07:22:25**, `source=run.sh`,
`chevauchement_reduit=true`. Rien à écarter.
ⓘ Le départ : 05:55:06 → 05:59:59 → **05:58:00** (`bw-model-score.timer`
prochaine **vendredi 05:57:00**). **Rien d'anormal.**

**Le contrôle de 07:30 a tiré à 07:30:18 et s'est TU** :

```
ⓘ 77 relevé(s), 56 comparable(s) ; durée : 10 points, pente -14 s/nuit ;
  mémoire : 10 points, pente -73 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate/négative, ou échéance hors horizon
```

⚠️ **LE PLATEAU À −53 Mo/NUIT EST CASSÉ** : après **cinq matins à exactement
−53** (10 au 14/10), la pente mémoire passe à **−73 Mo/nuit**. Elle se creuse
dans le sens de la détente, et cela concorde avec le jalon. La pente de durée
**s'arrête à −14 s/nuit** après avoir remonté vers zéro (−55 → −36 → −14 →
**−14**). **Le 25e centile des différences reste aveugle** par construction aux
deux plus grosses hausses de la fenêtre.

⇒ **Aucun jeton du jour posé par le contrôle.** Vérifié dans les **deux**
dossiers avant écriture : `/var/lib/bw-model-verif` portait
`cri.jira.bw-pente-duree` du 17/09, `…memoire` du 23/09, `…purge-57014` du
06/10 ; `$HOME/.balise-watch-etat-alertes` portait `duree` du 07/10 et les deux
autres du **14/10**. **`bw_jira_signaler` était donc libre sur les trois motifs.**

## 2. ⛔ Mémoire : **le plafond baisse, et personne ne l'a touché**

```
⛔ après le rejeu d'archive            : 3 005 Mo  (3 056 le 14/10)  ← −51
⛔ après le score par régime           : 2 836 Mo  (2 914 le 14/10)  ← −78
⛔ après l'oubli de la fenêtre rejouée : 3 161 Mo  (3 416 le 14/10)  ← −255
```

**Jalon max 3 161 Mo (−255), +361 au-dessus du seuil.** C'est **le plus bas de
toute la série récente** — 3 356 · 3 394 · 3 321 · 3 444 · 3 422 · 3 416 ·
**3 161** — et il est **160 Mo sous le précédent plus bas**.

**COÛT PAR LIGNE REJOUÉE : 1 588,8 o (−128,4 o, soit −7,5 %).**

```
29/09 1 671,3 o · 30/09 1 692,6 · 01/10 1 685,6 · 02/10 1 689,2
03/10 1 706,4  · 04/10 1 697,4 · 05/10 1 717,2 · 06/10 1 689,7
07/10 1 717,0  · 08/10 1 720,6 · 09/10 1 684,4 · 10/10 1 703,8
11/10 1 667,8  · 12/10 1 730,2 · 13/10 1 719,7 · 14/10 1 717,2
15/10 **1 588,8**  ← 79,0 o SOUS le plancher de la bande des seize nuits
```

⛔ **CORRECTION EXPLICITE DE LA NOTE DU 14/10.** Elle concluait, sur seize nuits
plates (±1,9 % autour de 1 699 o) : « *ce n'est pas une dérive qui monte, c'est
un plafond qu'il faut baisser* ». **Le plafond a baissé cette nuit, tout seul**,
sans qu'aucun levier n'ait été déployé — rien depuis `af25efb` (21/09), **25e
nuit**. C'est le **premier mouvement réel de la série en dix-sept nuits**.

⚠️ **ET LA LEÇON VAUT DANS CE SENS-CI AUSSI : une nuit ne fait pas une pente.**
**Douzième usage en dix-huit jours.** Une baisse de 7,5 % sur un indicateur qui
n'avait pas bougé de plus de 1,9 % en seize nuits est soit un changement de
régime, soit une nuit atypique. Deux ou trois nuits le diront. **Rien n'est
conclu.**

**Calcul à taux constant.** Au taux du **14/10** (1 717,2 o) la fenêtre de cette
nuit aurait rendu **3 416,4 Mo** ; elle rend **3 161**. Les **−255,4 Mo** sont
**imputables au coût par ligne**, pas à la fenêtre (+277 lignes = **+0,45 Mo**).
Au taux du **29/09** (1 671,3 o) : **3 325,0 Mo** — nous sommes **164,0 Mo
SOUS** ce taux, **pour la première fois de la série**.

**Les neuf jalons, trois en hausse, six en recul — et la baisse est CONCENTRÉE
là où le problème est** : oubli fenêtre rejouée **3 161 (−255)**, score par
régime **2 836 (−78)**, rejeu d'archive **3 005 (−51)** — soit **−384 Mo sur les
trois jalons d'incident** ; agrégat quotidien **1 832 (+22)**, oubli fenêtre
glissante **1 712 (−63)**, oubli du chemin J-0 **985 (+32)**, relecture de
l'archive **802 (−7)**, garde-fou de position **1 185 (−8)**, mélange
multi-modèle **1 174 (−6)**. ⓘ **Première nuit de la série où le recul se
concentre sur les incidents** et non au hasard.

**Incidents : toujours trois.** Le « score par régime » reste au-dessus du
seuil, mais de **36 Mo** seulement (2 738 le 13/10 → 2 914 le 14/10 → **2 836**) :
il oscille autour de la barre.

⚠️ **SWAP : LES DEUX INDICATEURS DIVERGENT, et c'est nouveau.** Pic **2 226,6 Mo
(−190,4)** : il **rentre** dans la bande **2,0–2,3 Go** quittée hier. Mais les
pages sorties font **2 918 498 (+663 864, soit +29,4 %)** — **NOUVEAU RECORD**,
le précédent étant 2 514 657 le 12/10. **Plus de trafic de swap pour un pic plus
bas.** Les deux nuits précédentes, les deux indicateurs allaient dans le **même**
sens ; cette nuit ils s'opposent. **À suivre, pas à conclure.** `oom = 0`, pic
système **3 597,2 Mo (−14,9)**.

**Les trois conditions de fermeture de KAN-4 : 1 sur 3**, inchangé.
Jalon mesurément retombé → **NON**, et c'est le point délicat : **−255 Mo est
une vraie baisse**, mais nous restons **+361 au-dessus du seuil avec trois
incidents**. Un jalon qui passe de 3 416 à 3 161 n'est pas un jalon retombé,
c'est un jalon **un peu moins haut**. Swap au pic ≈ 0 → **NON** (2 226,6 Mo, et
les pages sorties à un record). Contrôle muet sur `bw-pente-memoire` → **OUI**.
⇒ **le ticket reste ouvert.**

**Le remède ne change pas** : la **ligne en tuple** (`enquete-pente-10-09.md`
§2.6, ≈ −1 030 o/ligne), après la mesure `tuple` vs `namedtuple` à la sonde. La
baisse de cette nuit ne le remplace pas — elle n'est **ni expliquée, ni
reproduite, ni pilotée**. **25e nuit sans levier.**

## 3. Durée : +19 s, du calcul, et **le poste qui bouge est enfin nommé**

```
durée  5 032 → 5 051 s  (+19)
marge  3 068 → 3 049 s  (−19)  ⇒ 37,88 % → 37,64 % du garde de 8 100 s
cpu_s  4 029,7 → 4 058,9 (+29,2)
```

⚠️ **C'EST DU CALCUL, ET L'ATTENTE DIMINUE.** Le processeur rend **+29,2 s**
pour **+19 s** d'horloge : il monte **1,54 fois plus vite** que la durée, donc
il y a environ **10,2 s d'attente en MOINS** qu'hier. Hier c'était l'inverse
exact (cpu −27,0 pour −14 d'horloge) ; avant-hier du calcul en hausse ; le
12/10, 95 % d'attente. ⛔ **Quatre nuits, quatre signatures.**

Série : `5 318 · 4 975 · 5 029 · 5 046 · 5 032 · **5 051**`. La durée **oscille**
dans une bande de 4 821 à 5 318 s depuis onze nuits (**±5 %**) : ni plateau, ni
dérive, ni repli.

| étape | 12/10 | 13/10 | 14/10 | 15/10 |
|---|---|---|---|---|
| `regime` | 1 664,7 | 1 680,6 | 1 687,1 | **1 671,7 (−15,4)** |
| `glissant` | 958,0 | 988,4 | 938,7 | **1 017,5 (+78,8)** |
| `stabilite` | 309,0 | 309,4 | 346,1 | **296,6 (−49,5)** |
| `rejeu` | 81,5 | 78,6 | 84,7 | **83,1 (−1,6)** |
| somme des quatre | 3 013,2 | 3 057,0 | 3 056,6 | **3 068,9 (+12,3)** |
| hors étapes | 2 015,8 | 1 989,0 | 1 975,4 | **1 982,1 (+6,7)** |

⇒ **65 % du mouvement est DANS les quatre étapes**, 35 % hors étapes. Hier
c'était **97 % hors étapes** (étapes immobiles à −0,4 s) ; le 12/10, 90 % hors
étapes. Sur quatre nuits le hors-étapes a porté **90 %, −158 %, 97 %, puis
35 %**.

✅ **ET LE POSTE EST IDENTIFIÉ : c'est `glissant`, +78,8 s** — plus de quatre
fois le mouvement total d'horloge, en partie compensé par `stabilite` (−49,5) et
`regime` (−15,4). Coût par ligne de `glissant` **97,56 ms** (89,87 hier,
**+7,69**) pour `lignes_glissant` **10 430 (−15, soit −0,14 %)** : le temps monte
de **8,4 %** pour un volume stable. **Découplage temps/volume, net.**

**Hors étapes :**

```
1 924,7 (06/10) · 1 984,0 · 1 991,2 · 2 051,6 · 2 100,2 (10/10) · 1 967,0 · 2 015,8 · 1 989,0 · 1 975,4 · 1 982,1 (15/10)
```

⛔ **Le bloc n'est toujours pas instrumenté** — publication, Murphy, événements,
pression, duels, purge : six postes, **aucun jalon de temps**. La demande
d'instrumentation de `run.sh` reste ouverte (c'est une **écriture**, elle attend
Yann). ⓘ **L'argument s'affaiblit cette nuit** : pour une fois, le mouvement est
majoritairement dans les étapes, et nommé.

### ✅ 3.1 `bw-regime-sensibilite` : **LE COMPTEUR RETOMBE À 0 / 2**

Coût par ligne de `regime` (ms) :

```
13,39 (01/10) · 13,24 · 14,02 · 13,67 · 13,53 · 15,07 · 14,86 · 14,87
· 13,99 · 14,42 · 12,94 (11/10) · 13,02 · 13,14 · 13,20 · **13,06 (15/10)**
                                   +0,08   +0,12   +0,06   **−0,14**
```

✅ **CORRECTION DE LA NOTE DU 14/10.** Elle relevait une **troisième hausse
consécutive** et portait le critère à **3 / 2**, en posant la question à Yann
sans rien créer. Cette nuit le coût **recule de 0,14 ms** — **plus que les trois
hausses cumulées** (+0,26 ms). L'arbitrage unique du 07/10 demande **deux
hausses consécutives** : **le compteur est remis à zéro.**

⇒ ✅ **Aucun motif `bw-regime-sensibilite` n'est à poser, et la question de la
nuit dernière est tranchée par la mesure, pas par un avis.** 13,06 ms est le
**3e plus bas des quinze relevés**, et **2,01 ms sous** le 15,07 du 06/10 qui
avait motivé le critère.

ⓘ **La question de fond reste ouverte, et elle gagne en force** : faut-il
**ajouter un plancher de niveau** au critère (ne se déclencher qu'au-dessus de
la médiane de la série) ? **Trois hausses de +0,06 ms dans le bas de la bande
ont suffi à poser la question, un seul recul l'a fermée** : le critère est
sensible au bruit. C'est une décision de conception, elle est à Yann.

**Volumes** : `lignes_regime` **127 965 (+160)**, `lignes_score_zone`
**138 395 (+145)**, `lignes_daily` **69 545 (+9)**.

**Remontée du garde : NON lancée, NON demandée.** Le contrôle n'en propose
aucune (pente négative, `proposition()` n'est pas atteinte). Garde actuel
**8 100 s (135 min)** pour un run de **84,2 min**. ⛔ `10-timeout-s3.conf`
**n'a pas été touché.**

**KAN-3 : réouverture NON demandée.** +19 s, marge à 37,64 %, durée dans sa
bande depuis onze nuits, un poste identifié et compensé par deux autres.

## 4. ✅ Purge : **huitième nuit propre (8 / 3), et aucun 57014 nulle part**

```
→ purge model_score_zone : 131 299 ligne(s) effacée(s) en 8 tranche(s)
ⓘ purge model_character : rien avant le 2027-02-04 (première écriture
  2026-08-08, rétention 180 j) — aucune requête lancée.
```

**Le bloc est propre, poste par poste :**

- **aucune TRANCHE à 57014** (aucun `?as_of=eq.J&regime=eq.R` en HTTP 500)
- **aucune SONDE** (« plus vieille journée illisible » absente)
- **aucun « des lignes RESTENT »** — donc rien ne reste en base
- nombre de lignes **lisible** (131 299), **8 tranches** comme les sept nuits
  précédentes
- `n_57014 = 0` au registre

| nuit | état du bloc `model_score_zone` | compteur |
|---|---|---|
| 07→08 (2026-10-08) | `n_57014 = 0`, propre | 1 |
| 08→09 | propre, 129 650 l. / 8 tr. | 2 |
| 09→10 | propre, 129 594 l. / 8 tr. | 3 |
| 10→11 | propre, 129 233 l. / 8 tr. | 4 |
| 11→12 | propre, 129 534 l. / 8 tr. | 5 |
| 12→13 | propre, 132 089 l. / 8 tr. | 6 |
| 13→14 | propre, 131 391 l. / 8 tr. | 7 |
| 14→15 (2026-10-15) | **propre, 131 299 l. / 8 tr.** | **8** |

ⓘ Les **92 lignes** d'écart avec hier **ne sont pas un signal** : le volume
effacé suit le volume de la journée purgée (≈ 125 000–134 000).

### ✅ 4.1 Le 57014 n'est nulle part — et ce que cela démontre, exactement

`n_57014 = 0`. La purge de **`model_verif_daily`**, qui avait expiré la nuit
dernière pour la première fois de son histoire, **n'a pas récidivé**.
`bw_character_avance` est propre pour la **cinquième** nuit (**379 821
accumulateurs avancés sur 379 821 envoyés**).

⇒ **L'argument CONTRE la fermeture de KAN-5 s'affaiblit, mais il ne tombe pas** :

- **La réserve n° 1** (le timeout **change de requête** plutôt que de
  disparaître) a été démontrée **deux fois** — 10/10 vers `bw_character_avance`,
  14/10 vers `purge model_verif_daily`. Une nuit sans 57014 ne réfute pas ce
  schéma : **les 03, 04 et 05/10 avaient déjà donné trois nuits à `n_57014 = 0`
  avant son retour le 06/10.**
- **La réserve n° 2 tient entièrement** :
  `diagnostic_base_sous_tension_2026-09-29.sql` (lecture seule, 9 blocs, SQL
  Editor) **n'a toujours pas été joué — SEIZE JOURS.** C'est le seul document
  qui dirait si la base est sous tension ou si c'était cette requête-ci.

⇒ ⛔ **La fermeture est posée à Yann pour le sixième jour, et n'est pas
appliquée.** **Ma lecture, révisée à la hausse mais pas renversée** : le dossier
s'est amélioré cette nuit (zéro 57014, 8 / 3) ; **si le `.sql` est joué et
revient propre, la fermeture se défend. Sans le `.sql`, je ne ferme pas.**
*Un ticket fermé à tort vaut moins qu'un ticket ouvert.*
⚠️ **Et s'il est fermé, deux motifs restent sans ticket** : « la base est sous
tension », qui n'en a jamais eu, et `model_verif_daily`, qui a expiré le 14/10.

✅ Le contrôle s'est tu sur ce motif, et c'est **correct** : depuis le 07/10,
`constats()` lit `score.log` via `bilan_purge()`. Le faux « purge en échec » du
06/10 ne s'est pas reproduit : **neuvième nuit.**

## 5. ✅ Position : **l'échéance annoncée se réalise — une première**

```
⛔ position : 11 balise(s) divergent du gel (10 j lus), dont 4 CONFIRMÉE(S) (≥ 10 j)
   ⛔ pioupiou:2171          38 915 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE · Windbird 2171
   ⛔ pioupiou:1378          18 508 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE · Col de la Merquiere
   ⛔ pioupiou:367            6 764 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE · Le relais
   ⛔ infoclimat:STATIC0491   1 159 m · 10 j · nœud 0,01 CHANGE
   ·  pioupiou:1333  87 693 m ·  3 j   ← continue de reculer (10 → 8 → 7 → 6 → 5 → 4 → 3)
   ·  84 (9 753 m) · 2139 (1 913) · 1618 (744) · 1766 (739) · 1698 (321) · 1710 (259) — toutes à 2 j
⛔ position : 4 balise(s) CONFIRMÉE(S) — cri déposé pour envoi
```

✅ **LA NOTE DU 14/10 AVAIT RAISON, ET C'EST LA PREMIÈRE FOIS.** Elle annonçait
« *au mieux le compte passera de 2 à 4 demain* », avec `1378` et `367` à 9 j.
**Les deux ont franchi les 10 j, et le compte est exactement 4.** Après **six
démentis d'échéance** en dix jours, une prévision tient — et c'est celle qui
avait **corrigé** l'extrapolation linéaire au lieu de la reprendre. ⓘ **La leçon
se précise : l'extrapolation ne vaut rien sur le compte global (la liste se
renouvelle), mais elle vaut à un jour pour une balise nommée déjà à 9 j.**

**Le cri est parti** (compte 2 → 4, donc un front) : `ⓘ push parti (webhook,
HTTP 200)` à 05:22:22 Z, e-mail `smtpstatus=250`.

**Geste attendu de Yann** (la liste s'est rallongée) : trancher **`2171`**
(38,9 km) et **`STATIC0491`** (1 159 m) — candidates « AUTRE balise » et
changement de maille —, puis **`1378`** (18,5 km) et **`367`** (6,8 km), neuves
parmi les confirmées. Statuer sur **`1333`** qui **continue de sortir du lot**
(10 → 8 → 7 → 6 → 5 → 4 → **3 j**). Puis poser `position_suspecte` +
`position_note` sur `station_zone` par `.sql`.

ⓘ Question toujours ouverte depuis le 01/10 : **le cri est à front dans les deux
sens** (une sortie crie autant qu'une entrée, vu le 14/10) ; reste à décider s'il
doit **recrier** pour une balise qui **reste** confirmée.

## 6. ✅ Le correctif `--ipv4` du 07/10 : **deuxième examen, réussi**

```
2026-10-15T05:22:22Z ALERTE — score modeles — position des balises : … 4 balise(s)
2026-10-15T05:22:22Z ⓘ push parti (webhook, HTTP 200)
host=smtp.gmail.com … smtpstatus=250 … exitcode=EX_OK
```

✅ **Deuxième ⛔ à front depuis le correctif, deuxième push réel, HTTP 200.**
Aucun `429` nulle part dans le journal. Les trois cris perdus (30/09, 02/10,
07/10) ne se reproduisent pas.

⚠️ **`BW_DISCORD_WEBHOOK_URL` est TOUJOURS ABSENTE du `.env`.** Relevé par
**noms seuls** (`sed -E "s/=.*//"`, aucune valeur lue) : les **25 mêmes
variables** qu'hier, fichier **inchangé depuis le 13/09 18:08**. ⇒
`bw_push_discord` reste **codé, testé, muet** — et cette nuit il y avait encore
un ⛔ à pousser. `~/installer-webhook-discord.sh` attend toujours Yann : **33e
jour**. ntfy reste **seul canal push**.

## 7. ⛔ ρ hors [0, 1] : **la seule série qui montait sans démenti est démentie**

```
ⓘ référence combinée : 452 balise(s) sur 3 705 avaient un ρ hors [0, 1],
  ramené à la borne
```

```
307 (08/10) · 382 · 349 · 381 · 413 · 437 · 475 (14/10) · **452 (15/10)**
```

⛔ **CORRECTION EXPLICITE DE LA NOTE DU 14/10, point n° 4.** Elle appelait cette
série « **la seule du journal qui monte franchement et sans démenti** », notait
**deux plus hauts d'affilée** et **cinq hausses sur six nuits**, et la désignait
comme « **le candidat le plus net à un motif neuf** », en demandant à Yann s'il
voulait un motif `bw-rho-hors-bornes`. **Elle recule de 23 balises au septième
point** (**12,82 % → 12,20 %** du parc). ⇒ **Treizième usage de la leçon, et
cette fois sur la série qui semblait la plus solide.** La hausse depuis le 08/10
n'est plus de +54,7 % mais de **+47,2 %**.

⇒ ⚠️ **La question du motif `bw-rho-hors-bornes` perd son urgence, elle ne
disparaît pas** : 452 reste le **deuxième plus haut** de la série, et le niveau
est 47 % au-dessus du 08/10. **Rien n'a été créé.** Une deuxième baisse en
ferait une oscillation comme les autres ; une reprise de hausse rouvrirait la
question entière.

`k médian` **0,145** (0,143) sur **3 705** balises / 3 818 climatologisées.

## 8. ✅ Témoins du mélange : remontée sur le meilleur membre, repli sur l'uniforme

```
⛔ témoins du mélange : sur 7 593 balise-jours×échéance, le mélange fait
   2,7485 km/h contre 2,8417 pour le meilleur membre a priori
   (gain 3,3 %, mélange devant dans 52,3 % des cas) ;
   contre la moyenne UNIFORME, sur 1 123 : 2,9132 vs 3,033 (gain 3,9 %)
```

```
gain contre le MEILLEUR MEMBRE : 7,4 % → 5,5 → −0,6 (07/10) → +2,5 → −1,2 → −0,1 → −0,0 → +1,6 → +3,1 → +2,2 → **+3,3 (15/10)**
« devant » dans : 49,2 % → 50,1 → 49,1 → 49,2 → 50,1 → 51,6 → 50,0 → **52,3 %**
gain contre la moyenne UNIFORME : 6,0 % → 4,9 → 4,8 → 3,1 → 4,8 → 3,2 → 3,4 → 4,7 → 6,5 → 4,7 → **3,9 %**
```

✅ **Le mélange est devant dans 52,3 % des cas — le plus haut de toute la
série**, et le gain contre le meilleur membre remonte à **+3,3 %**. ⚠️ **Mais le
gain contre la moyenne uniforme recule à 3,9 %** (4,7 hier) : **les deux mesures
divergent cette nuit.**

ⓘ **L'erreur absolue BAISSE de 15,3 %** (3,245 → **2,7485 km/h**) : journée
**bien plus calme** après une journée ventée. ✅ **Quatrième confirmation de la
leçon du 12/10**, dans le bon sens : l'erreur absolue baisse, le gain contre le
meilleur membre monte — exactement la relation inverse constatée le 07/10 et le
14/10. **Toute lecture de cette série doit passer par l'erreur absolue.**
⇒ **La décision du 12/10 de ne pas créer de motif Jira est maintenue**, et plus
solidement : les deux mesures sont positives.

ⓘ Composition : **7 971** balise×échéance avec poids sur 30 j de cache (65,2 s)
— +6 h : 2 622 `bw_mix`, 413 témoins uniformes, 204 sans poids ; +24 h :
2 558 / 395 / 95 ; +48 h : 2 562 / 415 / 259.

## 9. Le reste du journal

- ✅ **Self-test du scoring : VERT** (lot S3, aucune lecture réelle, aucune
  écriture). Écart des deux mélanges : `mse_comb` 17,841 contre `mse_comb_vec`
  17,841 (**+0,00 %**).
- ⚠️ **Stabilité des rangs : τ = 0,735 sur 65 cases** (0,756 / 62 le 14/10 ;
  0,735 / 56 le 13/10). ⓘ **Les deux séries divergent de nouveau** : τ
  redescend à sa valeur du 13/10 tandis que l'échantillon monte à son plus haut
  (60 → 57 → 53 → 54 → 50 → 56 → 62 → **65**). À suivre, pas à conclure.
- ✅ **4 écarts au recalcul indépendant** (6 le 14/10, 7 le 13/10) — journée
  recalculée **2026-10-14**, 13 balise-jours comparés dont 7 sous le seuil de
  6 h. **Tous en `fcstagrume`** et tous de la **même signature** :
  `aemet:9784P` (agrume_pi +24 h), `infoclimat:000DG` (agrume +48 h),
  `pioupiou:1216` (agrume +48 h), `mf:74135001` (agrume +6 h).
  ⓘ **Huitième nuit de suite la même signature** (4 · 5 · 5 · 6 · 5 · 7 · 6 ·
  **4**), **au plus bas de la série** ; les balises concernées **changent chaque
  nuit** : ce n'est pas un lot fixe, c'est un **désaccord systématique sur le
  seuil des 6 heures appariées**.
- **Murphy** : 66 123 triplets, 64 152 décomposés, 266 balises tenues dehors
  (doublon ou position suspecte), 1,0 s.
- **FDR** : brut 6 958 tests, 1 791 survivants à BH α = 0,1, 109 rangs retirés
  sur 1 091 publiés ; corrigé 6 673 tests, 1 143 survivants, 128 rangs retirés
  sur 625.
- **Duels appariés** : lead 6 → 65 249 lignes depuis le 15/09 (849 retirées) ;
  lead 24 → 24 015 lignes (321 retirées). ⓘ Cumul tronqué par la rétention 30 j.
- **Événements** : **30 314 combinaisons publiables**, 29 100 écartées sous le
  quorum de 8 ; 28 706 lignes en base (`drop` 13 572, `onset` 10 267, `ramp`
  2 531, `reversal` 2 334, `breeze_yield` 2), 38 540 non publiées. ⓘ 3 447
  balises zonées, 1 419 cases fines dont 733 à moins de 2 balises.
- **Pression** : 17 889 lignes, 691 points de prévision portent `pmsl`,
  **858 appariées** (médiane 18,0 km) ; refusées : 211 hors rayon, 31 hors Δz,
  4 trop hautes.
- **Rétrécissement vers le parent** : 136 796 cases fines rapprochées de leur
  échelon supérieur.
- **Publication** : `model_scores.json` 121 203 Ko, `model_scores_light.json`
  7 256 Ko (525 Ko gzippé), `model_events.json` 8 461 Ko, `model_murphy.json`
  25 411 Ko (2 654 Ko gzippé).
- **Manches** : 48 nuits suivies depuis le 24/08, 716 cases zone×lead×modèle
  avec au moins une manche gagnée.
- **Accumulateurs** : 5 270 entrées écartées (`doublon_de`, lot L17), 317
  antérieures à la naissance de la balise (`notee_depuis`, lot L15-bis).
- ✅ **`model_character` : 379 821 accumulateurs avancés sur 379 821 envoyés** —
  propre pour la **cinquième** nuit.
- **Rejeu d'archive** : 2 086 137 balise-jours sur 30 journées (0 rejouée, 0
  vide, 3 952 balise-jours écartés) en 83,1 s.
- **Observations** : 3 742 balises le jour, 3 739 la veille.
- **`mutations_memoire`** : ⚠️ **SEPTIÈME nuit sans aucune ligne au journal.**
  Le relevé « 3 mutations non vues (2, 5, 13) » ne peut pas être revérifié ;
  dette antérieure, **statut inchangé faute de mesure**.
- `✅ terminé (634 450 lignes écrites en base)` (682 827 le 14/10) ; `registre :
  1 ligne écrite (2026-10-15, 5 051 s, jalon max 3 161 Mo, swap 2 226,6 Mo)`.

## 10. ✅ Les tickets : état vérifié par GET **avant** et **après**, trois commentaires

GET `/rest/api/3/issue/<clé>?fields=summary,status,comment` avant écriture,
HTTP 200 sur les trois. Les trois sujets sont **ceux relevés le 07/10**,
inchangés.

| ticket | statut | comm. avant | canal utilisé | comm. après |
|---|---|---|---|---|
| **KAN-3** `bw-pente-duree` | **Terminé** / `done` | 23 | `bw_jira_commenter KAN-3` (**délibéré**) | **24** ✅ |
| **KAN-4** `bw-pente-memoire` | **À faire** / `new` | 34 | `bw_jira_signaler bw-pente-memoire` | **35** ✅ |
| **KAN-5** `bw-purge-57014` | **À faire** / `new` | 17 | `bw_jira_signaler bw-purge-57014` | **18** ✅ |

**Ce que chaque commentaire porte :**

- **KAN-4** — ⛔ **le coût par ligne rejouée SORT de sa bande vers le bas**
  (1 588,8 o, **−128,4**, **79,0 o sous le plancher** des seize nuits) et le
  jalon tombe à **3 161 Mo (−255)**, le plus bas de la série récente ; **la
  conclusion du 14/10 est corrigée explicitement** (le plafond a baissé seul,
  sans levier, 25e nuit) **avec l'avertissement entier qu'une nuit ne fait pas
  une pente** ; calcul à taux constant (−255,4 Mo imputables au coût par ligne,
  +0,45 Mo à la fenêtre ; **164,0 Mo SOUS le taux du 29/09, une première**) ;
  les neuf jalons chiffrés et **la baisse concentrée sur les trois incidents
  (−384 Mo)** ; ⚠️ **les deux indicateurs de swap qui divergent** (pic 2 226,6
  rentré dans la bande, pages sorties à un **record** de 2 918 498, +29,4 %) ;
  les trois conditions de fermeture **1 sur 3** et pourquoi « moins haut » n'est
  pas « retombé » ; **la pente du contrôle qui passe de −53 à −73 Mo/nuit** après
  cinq matins ; la ligne en tuple ; `mutations_memoire` non mesurable (7e nuit).
- **KAN-5** — bloc `model_score_zone` **propre pour la 8e nuit** (131 299 l. /
  8 tr., aucune tranche, aucune sonde, aucun « RESTENT ») ; le **compteur nuit
  par nuit, 8 / 3** ; ✅ **aucun 57014 nulle part cette nuit**,
  `model_verif_daily` **n'a pas récidivé**, `bw_character_avance` propre (5e
  nuit) ; la **réserve n° 1 non réfutée** (les 03–05/10 avaient déjà donné trois
  nuits propres) ; la **réserve n° 2 entière** — le `.sql` **jamais joué, seize
  jours** ; **la fermeture posée à Yann, non appliquée**, avec ma lecture
  **révisée à la hausse** (si le `.sql` revient propre, elle se défend) ; et les
  deux motifs qui resteraient sans ticket.
- **KAN-3** — durée **+19 s** (5 051 s, marge **37,64 %**) ; **c'est du calcul
  et l'attente diminue** (cpu +29,2 pour +19 d'horloge, ≈ −10,2 s d'attente),
  **quatrième signature en quatre nuits** ; ✅ **le poste est identifié,
  `glissant` +78,8 s**, coût par ligne 97,56 ms (+7,69) pour un volume à
  −0,14 % — découplage net ; le tableau des étapes (65 % du mouvement dedans,
  contre 97 % dehors hier) et le bloc **non instrumenté** ; ✅ **le critère
  `bw-regime-sensibilite` RETOMBE à 0 / 2** (13,06 ms, **−0,14**, plus que les
  trois hausses cumulées) — **correction du 3 / 2 de la note du 14/10**, avec
  ⓘ **la question du plancher de niveau renforcée** ; l'aveuglement du 25e
  centile et la pente de durée qui s'arrête à −14 ; remontée du garde **non
  lancée, non demandée** ; **réouverture non demandée**.

⛔ **Aucune création, aucune transition, aucune réouverture, aucune fermeture.**
Les trois statuts sont **identiques** après écriture (revérifiés par GET).

ⓘ **Les deux canaux ont été employés comme arbitré le 07/10.** Le contrôle
s'étant tu, les jetons du jour étaient **libres** : `bw_jira_signaler` a servi
pour les deux motifs ouverts et a **posé les jetons**
(`cri.jira.bw-pente-memoire` et `cri.jira.bw-purge-57014` datent maintenant du
**15/10 16:55**). `bw_jira_commenter` a servi pour KAN-3, en « Terminé » — un
`bw_jira_signaler` sur ce motif **aurait créé un ticket neuf**. ✅ Vérifié après
coup : `cri.jira.bw-pente-duree` est **toujours daté du 07/10** côté `$HOME` et
du **17/09** côté `/var/lib` — le canal délibéré ne touche pas le jeton du jour.

ⓘ **Technique de l'envoi** : les trois corps ont été écrits sur le **Mac**
(`/tmp/bw-15-10/`), encodés en base64 et passés au VPS **par l'entrée standard
de `ssh`**, décodés dans une **variable shell**. **Aucun fichier n'a été déposé
sur le VPS** en dehors des `mktemp -d` internes à `bw_jira_http`, effacés par la
fonction elle-même.

## 11. Ce qui a été touché

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
jetons de `/var/lib/bw-model-verif` sont **inchangés** après la relance (17/09,
23/09, 06/10).
**Aucun secret lu par valeur** : le `.env` est **sourcé** (`set -a; . …;
set +a`) et lu **par noms de variables seuls**. `bw_jira.sh` passe par
`curl -K -`, jamais `-u`.
**Écritures Jira : trois commentaires** (voir §10).

**Mac** : trois corps de commentaire dans `/tmp/bw-15-10/` (fichiers de
travail), cette note dans `notes-projet/verdict-pente-15-10.md`. **Un commit
local**, depuis la **racine du dépôt serveur**. **Pas de `git push`.**

**Projet Claude** : cette note, **créée** (absente de la liste d'ouverture de
session).

## 12. ⚠️ L'horaire de la routine : **+7 h 37**

Programmée pour **07:11:05 UTC**, tirée à **14:48:32 UTC**.

```
02–03/10  AUCUN TIR
04–06/10  retard jusqu'à 4 h 10
07/10     à l'heure
08/10     +2 h 10
09/10     +6 h 40
10/10     +2 h 13
11/10     +5 h 51
12/10     +10 h 59   ← pire valeur de la série
13/10     +52 min
14/10     +6 h 11
15/10     +7 h 37
```

⚠️ **Huit matins sur quatorze ont dérivé, deux n'ont pas tiré.** ⓘ **Le VPS est
à l'heure, et il n'y est pour rien** : notation à **05:57:59** (prochaine
vendredi **05:57:00**), contrôle à **07:30:18** (prochain vendredi
**07:30:45**). **Le trou est côté planification de la routine**, et il reste le
premier risque du dispositif : il a déjà emporté la moitié du travail les 09 et
10/10.

## 13. Ce qui reste — et ce qui demande Yann

**Décisions, par ordre d'urgence :**

1. ⛔ **Jouer `diagnostic_base_sous_tension_2026-09-29.sql`** (lecture seule,
   9 blocs, SQL Editor). **SEIZE JOURS d'attente**, et c'est devenu **la seule
   réserve qui tienne encore** contre la fermeture de KAN-5. Cette nuit n'a
   produit **aucun 57014** : si le `.sql` revient propre, le dossier se ferme
   proprement. **C'est désormais la décision n° 1.**
2. ⛔ **FERMER KAN-5 ? Le compteur est à 8 / 3**, sixième jour où la question est
   posée. ✅ **L'argument CONTRE s'est affaibli** : zéro 57014 nulle part,
   `model_verif_daily` sans récidive, `bw_character_avance` propre (5e nuit).
   ⚠️ **Mais il ne tombe pas** : les 03, 04 et 05/10 avaient déjà donné trois
   nuits propres avant le retour du 06/10, et le `.sql` n'est pas joué. ⇒ **Ma
   lecture : ne pas fermer AVANT le `.sql` ; après, si propre, fermer.** Et il
   faudra dire où vont « la base est sous tension » et `model_verif_daily`, qui
   n'ont aucun motif.
3. ⚠️ **La mémoire a bougé, pour la première fois en dix-sept nuits — et dans le
   bon sens.** Coût par ligne **1 588,8 o (−7,5 %)**, **79 o sous** la bande des
   seize nuits, **164 Mo sous** le taux du 29/09 ; jalon **3 161 Mo (−255)** ;
   pente du contrôle de **−53 à −73 Mo/nuit**. ⛔ **Mais une nuit ne fait pas une
   pente, et rien n'a été déployé** (25e nuit sans levier) : la baisse n'est ni
   expliquée, ni reproduite, ni pilotée. ⇒ **Le remède reste la ligne en tuple**
   (≈ −1 030 o/ligne) après la mesure `tuple` vs `namedtuple` à la sonde — et
   **deux ou trois nuits diront** si c'est un changement de régime. **KAN-4 reste
   ouvert (1 / 3).**
4. ⛔ **Trancher les cas de position — la liste s'est rallongée à 4.** ✅
   `1378` (18,5 km) et `367` (6,8 km) ont rejoint `2171` (38,9 km) et
   `STATIC0491` (1 159 m), **exactement comme la note du 14/10 l'annonçait**.
   Statuer aussi sur `1333` qui **continue de sortir du lot** (10 → … → **3 j**).
   Puis `position_suspecte` + `position_note` sur `station_zone` par `.sql`.
5. ⛔ **Lancer `~/installer-webhook-discord.sh`.** `BW_DISCORD_WEBHOOK_URL`
   toujours absente, **33e jour** — et cette nuit il y avait encore un ⛔ à
   pousser. ✅ Le `--ipv4` tient (2e push réel, HTTP 200), mais ntfy reste
   **seul**.
6. ⓘ **Ajouter un plancher de niveau au critère `bw-regime-sensibilite` ?** La
   question gagne beaucoup de force : **trois hausses de +0,06 ms dans le bas de
   la bande ont suffi à poser la question le 14/10, un seul recul de −0,14 ms l'a
   fermée ce matin.** Le critère « deux hausses consécutives » est **sensible au
   bruit**. Un plancher (ne se déclencher qu'au-dessus de la médiane de la série)
   éviterait le va-et-vient. **Décision de conception, elle est à toi.**
7. ⚠️ **Un motif `bw-rho-hors-bornes` ? La question perd son urgence.** 452 /
   3 705 (**12,20 %**) après **475** : **première baisse en sept points**, et la
   note du 14/10 qui l'appelait « la seule série qui monte sans démenti » est
   **corrigée**. Le niveau reste le **2e plus haut** et **+47,2 % au-dessus du
   08/10**. ⇒ **Rien n'a été créé** ; une deuxième baisse en ferait une
   oscillation, une reprise rouvrirait tout.
8. ⚠️ **Instrumenter le bloc hors étapes de `run.sh` ?** La demande reste
   ouverte, mais **l'argument s'affaiblit cette nuit** : 65 % du mouvement est
   **dans** les étapes, et le poste est **nommé** (`glissant`, +78,8 s). Sur
   quatre nuits le hors-étapes a porté 90 %, −158 %, 97 %, puis 35 %. C'est une
   écriture dans `run.sh` : la décision est à toi.
9. ✅ **Un motif Jira pour les témoins du mélange ? NON — la question reste
   close**, et plus solidement : **+3,3 %** contre le meilleur membre, devant
   dans **52,3 %** des cas (**le plus haut de la série**), **+3,9 %** contre la
   moyenne uniforme. ⓘ L'erreur absolue a **baissé de 15,3 %** (journée calme) :
   **quatrième confirmation** que l'indicateur suit la météo du jour.
10. ⓘ **Un champ de bilan de purge au registre ?** (question du 08/10.) Avec
    `lignes_effacees` et `tranches`, le §4 tiendrait en trois lignes — et il
    faudrait **nommer la requête** qui porte le `n_57014`, comme le 14/10 l'a
    montré.
11. ⓘ **Le cri de position : à front, dans les DEUX sens.** Reste à décider s'il
    doit **recrier** pour une balise qui **reste** confirmée (question du 01/10).
12. ⓘ **Faut-il un motif Jira pour une panne de canal ?** (question du 30/09.)
    **Un motif pour `bw_character_avance` ?** — propre pour la 5e nuit, la
    question est encore moins pressante, pas close.

**Ce que la surveillance regardera au prochain run :**

13. **Le coût par ligne rejouée** : **1 588,8 o.** Une deuxième nuit sous 1 650
    ferait un **changement de régime** ; un retour dans la bande 1 668–1 730 en
    ferait une nuit atypique. **C'est la question n° 1 de demain.**
14. **Le 57014** : une **neuvième** nuit propre, ou un retour — sur
    `model_score_zone`, sur `model_verif_daily`, ou ailleurs encore ?
15. **Le swap** : les deux indicateurs **se recalent-ils** ? Le record de
    2 918 498 pages sorties tient-il, et pour quel pic ?
16. **ρ hors [0, 1]** : **452 après 475.** Une deuxième baisse, ou la reprise de
    la hausse ?
17. **Le coût par ligne de `regime`** : compteur à **0 / 2**. Une hausse le
    remettrait à 1.
18. **La position** : `1333` est à **3 j** et recule ; le compte de 4 tient-il, et
    le cri repart-il à front ?
19. **La durée** : la signature **s'inverse-t-elle une cinquième fois**, et
    `glissant` **rend-il** ses +78,8 s ?
20. **`mutations_memoire`** : une huitième nuit muette, ou le retour du relevé ?
21. **L'horaire** : **+7 h 37.** Huit matins de dérive sur quatorze.
