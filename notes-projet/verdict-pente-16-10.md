# Verdict de pente du 16/10/2026 — **la nuit où le vrai sujet n'est pas la pente, c'est le stockage R2 à 99,6 % du palier**. ⛔ Le compte R2 passe de **9,228 à 9,959 Go en une nuit (+731 Mo)**, dont **692 Mo sur `agrume/grille`** — il reste **41 Mo**. ✅ Côté notation tout se détend : durée **4 861 s (−190)**, marge au **plus haut de la série (39,99 %)**, **deux incidents mémoire au lieu de trois**. ⚠️ Mais le coût par ligne rejouée **revient dans sa bande (1 701,4 o, +112,6)** : la baisse du 15/10 était une **nuit atypique**, pas un changement de régime. ⛔ Et le **57014 revient sur `model_verif_daily`** : la note du 15/10 est corrigée, sa « révision à la hausse » est retirée.

## 13:10 → 13:25 (Paris) — routine Balise Watch (tirée à 11:09:44 UTC pour 07:07:05 : **+4 h 03**), lecture VPS complète, **deux écritures Jira**, **deux notifications**

**Étape 0 faite.** `git log --oneline --since=midnight` :

- dépôt serveur `PWA/balise-watch-server` : **aucun commit du jour**
- dépôt principal `surveillance balise` : **aucun commit du jour**
- `claude/verdict-pente-16-10.md` **absent** de la liste d'ouverture de session
- `claude/verdict-pente-15-10.md` lu **en entier**
- `notes-projet/README.md` relu — les quatre règles
- `claude/alerte-garde-fou-r2-25-09.md` et `claude/orphelins-agrume-grille-10-10.md`
  lus **parce que la nuit a crié sur ce motif** (voir §2)

⇒ **premier et seul run pente du jour. Rien à fusionner, aucun doublon.**

## 1. Les nuits, bout à bout

| | 11/10 | 12/10 | 13/10 | 14/10 | 15/10 | 16/10 |
|---|---|---|---|---|---|---|
| durée | 4 975 s | 5 029 s | 5 046 s | 5 032 s | 5 051 s | **4 861 s (−190)** |
| marge | 3 125 | 3 071 | 3 054 | 3 068 | 3 049 | **3 239 (+190)** |
| marge en % du garde | 38,58 % | 37,91 % | 37,70 % | 37,88 % | 37,64 % | **39,99 %** |
| `cpu_s` | 4 019,1 | 4 021,9 | 4 056,7 | 4 029,7 | 4 058,9 | **3 895,0 (−163,9)** |
| jalon max | 3 321 Mo | **3 444** | 3 422 | 3 416 | **3 161** | **3 384 (+223)** |
| au-dessus du seuil | +521 | +644 | +622 | +616 | +361 | **+584** |
| swap au pic | 2 129,5 | **2 595,3** | 2 091,8 | 2 417,0 | 2 226,6 | **2 429,5 (+202,9)** |
| pages sorties | 2 501 165 | 2 514 657 | 2 171 262 | 2 254 634 | **2 918 498** | **2 472 955 (−445 543)** |
| pic système | 3 619,9 | 3 616,1 | 3 595,4 | 3 612,1 | 3 597,2 | **3 584,5 (−12,7)** |
| fenêtre rejouée | 2 087 981 | 2 087 197 | 2 086 539 | 2 085 860 | 2 086 137 | **2 085 521 (−616)** |
| o / ligne rejouée | 1 667,8 | **1 730,2** | 1 719,7 | 1 717,2 | **1 588,8** | **1 701,4 (+112,6)** |
| incidents mémoire | 3 | 3 | 2 | 3 | 3 | **2 (−1)** |
| `n_57014` | 0 | 0 | 0 | 1 (hors purge) | 0 | **1 (hors purge)** |
| lancement / résultat | timer/success | ↳ | ↳ | ↳ | ↳ | **timer/success** |

Nuit **comparable** : `lancement=timer`, `exec_status=0`, `oom=0`,
`result=success`, **05:57:06 → 07:18:18**, `source=run.sh`,
`chevauchement_reduit=true`. Rien à écarter.
ⓘ Le départ : 05:59:59 → 05:58:00 → **05:57:06** (`bw-model-score.timer`
prochaine **samedi 05:55:47**). **Rien d'anormal.**

**Le contrôle de 07:30 a tiré à 07:30:46 et s'est TU** :

```
ⓘ 78 relevé(s), 57 comparable(s) ; durée : 10 points, pente -36 s/nuit ;
  mémoire : 10 points, pente -73 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate ou négative, ou échéance hors horizon
```

La pente de durée **repart vers le bas (−36 s/nuit)** après s'être arrêtée
deux matins à −14 ; la pente mémoire reste à **−73 Mo/nuit**, identique à
hier. **Le 25e centile des différences reste aveugle** par construction aux
deux plus grosses hausses de la fenêtre.

⇒ **Aucun jeton du jour posé par le contrôle.** Vérifié dans les **deux**
dossiers avant écriture : `/var/lib/bw-model-verif` portait
`cri.jira.bw-pente-duree` du 17/09, `…memoire` du 23/09, `…purge-57014` du
06/10 ; `$HOME/.balise-watch-etat-alertes` portait `duree` du 07/10 et les deux
autres du **15/10 16:55**. **`bw_jira_signaler` était donc libre sur les trois.**

## 2. ⛔ LE SUJET DE LA MATINÉE : R2 à **9,959 Go sur 10** — il reste 41 Mo

Ce n'est pas un motif suivi par la routine de pente, et c'est pourtant le seul
point de la nuit qui demande une décision. `bw-garde-fou-r2.service` est en
**`failed`** depuis 07:18:26, et le cri est parti (push **HTTP 200**, e-mail
`smtpstatus=250`).

```
┌─ JAUGE R2 (lecture seule) ───────────────────────────────────
│ total compte              :    9.959 Go   ( 99.6 % du palier 10 Go)
│ objets                    :     6423
│ pente mesurée             :   +0.035 Go/mois   (somme des préfixes, 25e centile)
│ palier atteint dans       :       35 j (~2026-11-20)
│ seuil d'alerte            :     12.0 Go   · seuil d'arrêt chaîne 6 Go
│ couverture                : complète (tous les buckets du compte)
```

| | 15/10 | 16/10 | Δ |
|---|---|---|---|
| **total compte** | 9,228 Go (92,3 %) | **9,959 Go (99,6 %)** | **+731 Mo** |
| `balise-watch-grids` | 8,467 Go / 5 247 obj. | **9,189 Go / 5 393 obj.** | +722 Mo / +146 |
| `model-verif` | 0,756 Go / 803 obj. | 0,766 Go / 817 obj. | +10 Mo / +14 |
| **dont `agrume/grille`** | **4,652 Go / 673 obj.** | **5,344 Go / 769 obj.** | **+692 Mo / +96** |

✅ **LA CAUSE EST NOMMÉE : `balise-watch-grids:agrume/grille`, +692 Mo et
+96 objets en une nuit — 95 % de la hausse du compte.** À 7,2 Mo par objet,
cela correspond aux objets de 5,5 Mo relevés le 10/10 : c'est **un jeu de
grilles de plus conservé**, pas une fuite.

⚠️ **Et ce ne sont PAS des orphelins** : l'audit dit
`agrume/grille/ : 769 présentes / 769 réclamées ✓ tout est réclamé`. Le
correctif `874729f` + `c9497da` du 10/10 (clés déclarées `en_vol` avant la
première écriture) **tient** : le cas du 10/10 — deux objets hors index, donc
hors purge pour toujours — **ne s'est pas reproduit**. ⇒ **le problème est la
RÉTENTION, pas la publication.**

### 2.1 ⛔ Deux choses que j'ai dites de travers dans la première notification, et que je corrige ici

J'ai envoyé un premier cri disant que **« la chaîne peut casser cette nuit »**
et que le **seuil d'alerte à 12 Go désarmait le garde-fou**. **Les deux sont
faux**, et c'est le code du projet lui-même qui le dit :

1. ⛔ **Franchir le palier ne bloque rien — ça FACTURE.** `audit_r2.py`,
   en-tête : « *le palier ne bloque rien, ça facture* ». Et **tu avais déjà
   accepté le dépassement le 27/09** (relevé dans
   `orphelins-agrume-grille-10-10.md`, qui notait déjà
   **9,769 Go / 97,7 %**). Il n'y a donc **aucune urgence de ce soir**.
2. ⛔ **Le garde-fou n'est pas désarmé.** `constats()` porte **trois** motifs
   indépendants : `palier gratuit DÉPASSÉ` dès `go >= PALIER_STOCKAGE_GO`
   (10 Go) — **celui-là ne dépend pas du seuil** —, puis `seuil d'alerte
   franchi` à `BW_R2_SEUIL_GO` (réglé ici à **12,0**, défaut 7,0), puis
   l'échéance. Le test au palier **partira** au franchissement.

⇒ **Correction envoyée en seconde notification.** C'est exactement la
discipline que ce projet s'impose aux autres séries : vérifier avant de
reprendre, et corriger explicitement. Elle vaut pour moi aussi.

### 2.2 ⚠️ Ce qui reste vrai : « palier atteint dans 35 j » est du BRUIT

```
10/10   77 j (ÉCHEC)   ·  11/10  643 j (OK)  ·  12/10  307 j (OK)
13/10  252 j (OK)      ·  14/10  182 j (OK)  ·  15/10  641 j (OK)
16/10   35 j (ÉCHEC)   ← 641 → 35 en une nuit
```

⛔ **C'est le défaut écrit noir sur blanc le 25/09, et il n'a pas été corrigé :**
la pente est la **somme des 25e centiles des différences par préfixe**, donc
les préfixes AROME qui oscillent tirent tout vers le négatif et l'échéance
saute d'un facteur 18 d'une nuit à l'autre. La démonstration la plus nette est
dans le tableau de cette nuit : **`agrume/grille` affiche `-0.004 Go/mois`
alors qu'il vient de prendre 692 Mo.**

ⓘ **C'est le MÊME statistique, et le MÊME aveuglement, que la pente du contrôle
de pente** (25e centile des différences, qui n'a vu ni le +153 s du 01/10, ni le
+336 s du 06/10, ni le +70 s du 07/10). Un quantile bas est fait pour ignorer
les sauts ; on lui demande ici de les annoncer. **Les deux usages ont le même
vice, et il mérite d'être traité une fois pour les deux.**

### 2.3 Ce qui est demandé à Yann (rien n'a été fait)

- ⛔ **Trancher la rétention d'`agrume/grille`** — c'est le levier chiffré :
  le 25/09 donnait **rétention grille 3 → 2 runs ≈ −1,7 Go**. Un seul run
  retiré rendrait déjà **≈ 700 Mo**, soit la hausse de cette nuit.
- ⚠️ **Corriger la pente d'`audit_r2.py`** (une moyenne, une régression, ou le
  delta de la veille — pas un 25e centile). C'est une **écriture** : elle
  attend ton accord.
- ⛔ **Aucun ticket Jira créé pour ce motif.** `bw-garde-fou-r2` n'a **aucun
  ticket** et en créer un demande ton accord. **Veux-tu un motif
  `bw-r2-palier` ?** C'est la question n° 1 de cette note.

## 3. ⚠️ Mémoire : **le coût par ligne revient dans sa bande — la baisse d'hier était une nuit atypique**

```
⛔ après le rejeu d'archive            : 3 002 Mo  (3 005 le 15/10)  ←   −3
ⓘ  après le score par régime          : 2 606 Mo  (2 836 le 15/10)  ← −230  SOUS LE SEUIL
⛔ après l'oubli de la fenêtre rejouée : 3 384 Mo  (3 161 le 15/10)  ← +223
```

**Jalon max 3 384 Mo (+223), +584 au-dessus du seuil.**

**COÛT PAR LIGNE REJOUÉE : 1 701,4 o (+112,6 o, soit +7,1 %).**

```
29/09 1 671,3 o · 30/09 1 692,6 · 01/10 1 685,6 · 02/10 1 689,2
03/10 1 706,4  · 04/10 1 697,4 · 05/10 1 717,2 · 06/10 1 689,7
07/10 1 717,0  · 08/10 1 720,6 · 09/10 1 684,4 · 10/10 1 703,8
11/10 1 667,8  · 12/10 1 730,2 · 13/10 1 719,7 · 14/10 1 717,2
15/10 1 588,8  ← hors bande, vers le bas
16/10 **1 701,4**  ← DE RETOUR DANS LA BANDE 1 667,8 – 1 730,2
```

✅ **LA QUESTION N° 1 DE LA NOTE DU 15/10 EST TRANCHÉE PAR LA MESURE.** Elle
posait le critère d'avance, et c'est ce qui la rend utile : « *une deuxième
nuit sous 1 650 ferait un changement de régime ; un retour dans la bande
1 668–1 730 en ferait une nuit atypique* ». ⇒ **Retour dans la bande. Le 15/10
était une NUIT ATYPIQUE.** La bande de seize nuits en fait **dix-sept**, et le
1 588,8 reste un point isolé.

⚠️ **Quatorzième usage de « une nuit ne fait pas une pente » en dix-neuf jours
— et le premier qui démente une BAISSE.** La note du 15/10 avait posé
l'avertissement elle-même, en toutes lettres, tout en titrant sur « le plafond
qui baisse tout seul ». **L'avertissement avait raison, le titre avait tort.**

**Calcul à taux constant.** Au taux du **15/10** (1 588,8 o) la fenêtre de
cette nuit aurait rendu **3 159,9 Mo** ; elle rend **3 384**. Les **+224 Mo**
sont **imputables au coût par ligne** : la fenêtre a **reculé** de 616 lignes
(**−1,0 Mo**). Au taux du **14/10** (1 717,2 o) : **3 415,4 Mo**, nous sommes
**31 Mo sous**. Au taux du **29/09** (1 671,3 o) : **3 324,0 Mo**, nous sommes
**60 Mo AU-DESSUS** — hier nous étions **164 Mo sous** ce taux, **cette avance
est perdue.**

✅ **LE SEUL VRAI ACQUIS : DEUX INCIDENTS AU LIEU DE TROIS.** Le « score par
régime » passe **sous** le seuil de 2 800 Mo (2 738 le 13/10 → 2 914 → 2 836 →
**2 606**, soit **194 Mo sous la barre**). La note du 15/10 le décrivait comme
« oscillant autour de la barre, à 36 Mo » : **il est passé de l'autre côté.**
⚠️ Mais le jalon **maximum**, celui qui porte le ticket, **remonte de 223 Mo**.

**Les neuf jalons** : oubli fenêtre rejouée **3 384 (+223)**, rejeu d'archive
**3 002 (−3)**, score par régime **2 606 (−230)**, agrégat quotidien
**1 828 (−4)**, oubli fenêtre glissante **1 729 (+17)**, garde-fou de position
**1 200 (+15)**, mélange multi-modèle **1 195 (+21)**, oubli du chemin J-0
**959 (−26)**, relecture de l'archive **802 (=)**. ⓘ Hier le recul était
**concentré sur les trois incidents** ; cette nuit il est **concentré sur un
seul** (le score par régime) pendant que le maximum remonte.

**La série du jalon max** : `3 356 · 3 394 · 3 321 · 3 444 · 3 422 · 3 416 ·
3 161 · 3 384`. Sur dix-huit nuits elle oscille **entre 3 161 et 3 444 sans
pente nette**.

⚠️ **SWAP : LES DEUX INDICATEURS DIVERGENT POUR LA DEUXIÈME NUIT, SIGNES
INVERSÉS.** Hier : pic **−190,4**, pages sorties **+29,4 % (record)**. Cette
nuit : pic **2 429,5 Mo (+202,9)**, au-dessus de la bande 2,0–2,3 Go, pendant
que les pages sorties **reculent de 445 543 (−15,3 %)**. ⇒ **Le record de
2 918 498 NE TIENT PAS** : c'était une nuit, pas un palier. **Deux nuits de
divergence, dans les deux sens : aucune lecture simple ne tient, et il faut
cesser de traiter ces deux chiffres comme un seul indicateur.** `oom = 0`, pic
système **3 584,5 Mo (−12,7)**.

**Les trois conditions de fermeture de KAN-4 : 1 sur 3**, inchangé.
Jalon mesurément retombé → **NON** (3 384 Mo, +223, +584 au-dessus du seuil,
deux incidents). Swap au pic ≈ 0 → **NON** (2 429,5 Mo, +202,9). Contrôle muet
sur `bw-pente-memoire` → **OUI**. ⇒ **le ticket reste ouvert.**

**Le remède ne change pas, et la nuit le renforce** : la **ligne en tuple**
(`enquete-pente-10-09.md` §2.6, ≈ −1 030 o/ligne), après la mesure `tuple` vs
`namedtuple` à la sonde. L'élagage de `units` avait échoué (−124 Mo au lieu de
−1 500) : les gains sont dans la **structure**. **Rien de déployé côté mémoire
depuis `af25efb` (21/09) : 26e nuit sans levier.**

## 4. ✅ Durée : **−190 s, du calcul, et `glissant` rend ses +78,8 s**

```
durée  5 051 → 4 861 s  (−190)
marge  3 049 → 3 239 s  (+190)  ⇒ 37,64 % → 39,99 % du garde de 8 100 s
cpu_s  4 058,9 → 3 895,0 (−163,9)
```

✅ **Marge au plus haut de toute la série récente : 39,99 %.** Pour mémoire, le
point bas était **35,5 %** le 07/10.

⚠️ **C'EST DU CALCUL.** L'attente (durée − `cpu_s`) passe de **992,1 s** à
**966,0 s**, soit **−26,1 s** ; le calcul rend **−163,9 s**. ⇒ **86 % de la
baisse est du calcul en moins**, 14 % de l'attente. ⛔ **Cinquième nuit, cinquième
signature** — la question de la note du 15/10 (« la signature s'inverse-t-elle
une cinquième fois ? ») est **répondue : oui**.

| étape | 13/10 | 14/10 | 15/10 | 16/10 |
|---|---|---|---|---|
| `regime` | 1 680,6 | 1 687,1 | 1 671,7 | **1 608,2 (−63,5)** |
| `glissant` | 988,4 | 938,7 | 1 017,5 | **942,4 (−75,1)** |
| `stabilite` | 309,4 | 346,1 | 296,6 | **284,9 (−11,7)** |
| `rejeu` | 78,6 | 84,7 | 83,1 | **75,6 (−7,5)** |
| somme des quatre | 3 057,0 | 3 056,6 | 3 068,9 | **2 911,1 (−157,8)** |
| hors étapes | 1 989,0 | 1 975,4 | 1 982,1 | **1 949,9 (−32,2)** |

⇒ **83 % du mouvement est DANS les quatre étapes**, 17 % hors étapes. Sur cinq
nuits le hors-étapes a porté **90 %, −158 %, 97 %, 35 %, puis 17 %**.

✅ **`glissant` REND SES +78,8 s : −75,1 s**, et la question de la note du
15/10 est réglée au premier essai. Coût par ligne de `glissant` **90,48 ms**
(97,56 hier, **−7,08**) pour `lignes_glissant` **10 416 (−14)** : le temps
redescend de **7,3 %** pour un volume stable. **Le découplage temps/volume
relevé hier s'est défait dans le même sens qu'il s'était fait** — c'était donc
un à-coup, pas une dérive.

**Hors étapes** (dix nuits) :

```
1 984,0 · 1 991,2 · 2 051,6 · 2 100,2 (10/10) · 1 967,0 · 2 015,8 · 1 989,0 · 1 975,4 · 1 982,1 · 1 949,9 (16/10)
```

⛔ **Le bloc n'est toujours pas instrumenté** — publication, Murphy,
événements, pression, duels, purge : six postes, **aucun jalon de temps**.
ⓘ **Mais l'argument s'affaiblit une deuxième nuit de suite** : 83 % du
mouvement est dans les étapes et le poste est nommé. **La demande reste
ouverte, elle n'est plus urgente.**

### ✅ 4.1 `bw-regime-sensibilite` : **le compteur reste à 0 / 2**, au plus bas de la série

Coût par ligne de `regime` (ms) :

```
13,39 (01/10) · 13,24 · 14,02 · 13,67 · 13,53 · 15,07 · 14,86 · 14,87
· 13,99 · 14,42 · 12,94 (11/10) · 13,02 · 13,14 · 13,20 · 13,06
· **12,57 (16/10)**   ← −0,49, LE PLUS BAS DES SEIZE RELEVÉS
```

✅ **Deuxième recul consécutif, et nouveau plus bas** (le précédent était 12,94
le 11/10). L'arbitrage unique du 07/10 demande **deux hausses consécutives** :
⇒ **compteur à 0 / 2, aucun motif à poser.** 12,57 ms est **2,50 ms sous** le
15,07 du 06/10 qui avait motivé le critère.

ⓘ **La question du plancher de niveau se vide d'elle-même** : posée le 14/10
sur trois hausses de +0,06 ms, fermée le 15/10 par un recul, et cette nuit le
coût est **au plus bas**. Le critère « deux hausses consécutives » reste
**sensible au bruit** dans le bas de la bande, mais il n'a **rien produit à
tort** en trois matins. **Décision de conception, elle reste à toi — elle n'est
plus pressante.**

**Volumes** : `lignes_regime` **127 915 (−50)**, `lignes_score_zone`
**138 331 (−64)**, `lignes_daily` **69 597 (+52)**.

**Remontée du garde : NON lancée, NON demandée.** Le contrôle n'en propose
aucune (pente négative, `proposition()` n'est pas atteinte). Garde **8 100 s
(135 min)** pour un run de **81,0 min**. ⛔ `10-timeout-s3.conf` **n'a pas été
touché.**

**KAN-3 : ni commentaire, ni réouverture.** ⓘ **Et c'est un choix explicite** :
la consigne dit de commenter KAN-3 **si la durée AUGMENTE**. Elle **baisse de
190 s**, la marge est au **plus haut de la série**, le contrôle se tait, et sa
pente de durée est **négative (−36 s/nuit)**. Un commentaire sur un ticket
**« Terminé »** pour annoncer une amélioration serait du bruit. **Vérifié après
coup : KAN-3 est resté à 24 commentaires.**

## 5. ⛔ Purge : **neuvième nuit propre (9 / 3)**, mais **le 57014 revient sur `model_verif_daily`**

```
⚠️ purge model_verif_daily : HTTP 500 — {"code":"57014",
   "message":"canceling statement due to statement timeout"}
→ purge model_score_zone : 132 525 ligne(s) effacée(s) en 8 tranche(s)
ⓘ purge model_character : rien avant le 2027-02-04 (première écriture
  2026-08-08, rétention 180 j) — aucune requête lancée.
```

**Le bloc `model_score_zone` est propre, poste par poste :**

- **aucune TRANCHE à 57014** (aucun `?as_of=eq.J&regime=eq.R` en HTTP 500)
- **aucune SONDE** (« plus vieille journée illisible » absente)
- **aucun « des lignes RESTENT »** — donc rien ne reste en base
- nombre de lignes **lisible** (132 525), **8 tranches** comme les huit nuits
  précédentes

| nuit | état du bloc `model_score_zone` | compteur |
|---|---|---|
| 07→08 (08/10) | propre | 1 |
| 08→09 | propre, 129 650 l. / 8 tr. | 2 |
| 09→10 | propre, 129 594 l. / 8 tr. | 3 |
| 10→11 | propre, 129 233 l. / 8 tr. | 4 |
| 11→12 | propre, 129 534 l. / 8 tr. | 5 |
| 12→13 | propre, 132 089 l. / 8 tr. | 6 |
| 13→14 | propre, 131 391 l. / 8 tr. | 7 |
| 14→15 | propre, 131 299 l. / 8 tr. | 8 |
| 15→16 (16/10) | **propre, 132 525 l. / 8 tr.** | **9** |

ⓘ Les **1 226 lignes** d'écart avec hier **ne sont pas un signal** : le volume
effacé suit le volume de la journée purgée (≈ 125 000–134 000).

### ⛔ 5.1 CORRECTION EXPLICITE DE LA NOTE DU 15/10 — la récidive a eu lieu

La note du 15/10 écrivait : « *la purge de `model_verif_daily`, qui avait
expiré la nuit dernière pour la première fois de son histoire, **n'a pas
récidivé** »*, et elle en tirait une lecture « **révisée à la hausse** » sur la
fermeture de KAN-5.

```
14/10   purge model_verif_daily : 57014     ← première fois
15/10   rien                                 ← la nuit qui a motivé la révision
16/10   purge model_verif_daily : 57014     ← RÉCIDIVE
```

⛔ **Deux nuits sur les trois dernières.** La note du 15/10 a tiré une
conclusion de tendance **d'un point unique** — précisément ce que la leçon
maison interdit. ⇒ **Je retire la révision à la hausse** et je reviens à la
lecture du 14/10. ⓘ **C'est le quinzième usage de la leçon en dix-neuf jours,
et le deuxième de cette note** (l'autre est le coût par ligne, §3). Les deux
corrections portent sur **la même note** et vont **dans le même sens** : le
15/10 a lu trois détentes comme des tendances, et les trois se sont défaites en
une nuit.

**LA RÉSERVE N° 1 EST MAINTENANT DÉMONTRÉE TROIS FOIS** — le timeout **change
de requête** au lieu de disparaître :

```
10/10   vers bw_character_avance
14/10   vers purge model_verif_daily
16/10   vers purge model_verif_daily, à nouveau
```

Une nuit propre sur `model_score_zone` **ne réfute donc pas le schéma**, et le
précédent est connu : **les 03, 04 et 05/10 avaient déjà donné trois nuits à
`n_57014 = 0` avant le retour du 06/10.**

**LA RÉSERVE N° 2 TIENT ENTIÈREMENT, ET ELLE EMPIRE.**
`model-verif/diagnostic_base_sous_tension_2026-09-29.sql` (lecture seule,
9 blocs, SQL Editor) **n'a toujours pas été joué : DIX-SEPT JOURS.**

⇒ ⛔ **Ma lecture, RÉVISÉE À LA BAISSE par rapport à hier : NE PAS FERMER.** Le
compteur du motif suivi est à **9 / 3** et remplit sa condition depuis six
jours, mais **le 57014 est dans la base cette nuit**, sur une requête de purge
voisine, **pour la deuxième fois en trois nuits**. Fermer maintenant
reviendrait à fermer « le 57014 » en ne regardant **qu'une de ses adresses**.
*Un ticket fermé à tort vaut moins qu'un ticket ouvert.*
⚠️ **Et deux motifs resteraient sans ticket** : « la base est sous tension »,
qui n'en a jamais eu, et `model_verif_daily`, qui a maintenant **expiré deux
fois**.

✅ Le contrôle s'est tu sur ce motif, et c'est **correct** : depuis le 07/10,
`constats()` lit `score.log` via `bilan_purge()`. Le faux « purge en échec » du
06/10 ne s'est pas reproduit : **dixième nuit.**
✅ `bw_character_avance` propre pour la **sixième** nuit (**343 225
accumulateurs avancés sur 343 225 envoyés**).

## 6. Position : **les quatre confirmées tiennent, aucun cri — et c'est cohérent**

```
⛔ position : 11 balise(s) divergent du gel (10 j lus), dont 4 CONFIRMÉE(S) (≥ 10 j)
   ⛔ pioupiou:2171          38 915 m · 10 j · nœud CHANGE · profil CHANGE · Windbird 2171
   ⛔ pioupiou:1378          18 508 m · 10 j · nœud CHANGE · profil CHANGE · Col de la Merquiere
   ⛔ pioupiou:367            6 764 m · 10 j · nœud CHANGE · profil CHANGE · Le relais
   ⛔ infoclimat:STATIC0491   1 159 m · 10 j · nœud CHANGE
   ·  84 (9 753 m) · 2139 (1 913) · 1618 (744) · 1766 (739) · 1698 (321) · 1710 (259) — toutes à 3 j
   ·  pioupiou:1333  87 693 m ·  2 j   ← continue de reculer (10 → … → 4 → 3 → 2)
```

✅ **Aucun cri n'est parti sur la position, et c'est le comportement voulu** :
le compte reste à **4**, donc **pas de front**. Les quatre confirmées sont
**exactement les mêmes** qu'hier.
ⓘ Les six balises à 2 j sont passées à **3 j** ; `1333` descend de **3 à 2 j**
et **continue de sortir du lot**. ⚠️ **Aucune prévision ici** : la leçon
affinée du 15/10 dit que l'extrapolation ne vaut **qu'à un jour, pour une
balise nommée déjà à 9 j** — aucune n'y est. Les six à 3 j arriveraient à 10 j
**dans sept nuits**, et six démentis d'échéance en dix jours disent de ne pas
l'écrire comme une échéance.

**Geste attendu de Yann, inchangé** : trancher **`2171`** (38,9 km) et
**`STATIC0491`** (1 159 m) — candidates « AUTRE balise » et changement de
maille —, puis **`1378`** (18,5 km) et **`367`** (6,8 km). Statuer sur
**`1333`**. Puis poser `position_suspecte` + `position_note` sur `station_zone`
par `.sql`.
ⓘ Question toujours ouverte depuis le 01/10 : le cri est **à front dans les
deux sens** ; faut-il qu'il **recrie** pour une balise qui **reste** confirmée ?
**Cette nuit en est l'illustration** : quatre balises confirmées, dont deux
depuis dix jours, et **aucun signal**.

## 7. ✅ Le correctif `--ipv4` du 07/10 : **troisième examen, réussi**

```
2026-10-16T05:18:24Z ALERTE — garde-fou R2 (garde-fou-r2) en echec …
2026-10-16T05:18:24Z ⓘ push parti (webhook, HTTP 200)
host=smtp.gmail.com … smtpstatus=250 … exitcode=EX_OK
```

✅ **Troisième ⛔ depuis le correctif, troisième push réel, HTTP 200.** Aucun
`429` de `ntfy` nulle part. ⓘ **Attention à ne pas se tromper de 429** : le
journal en contient plusieurs, tous d'`aromepi` (quota de l'API AROME PI,
`aromepi/0025 : 310 requêtes, 4 × 429, 6 attentes de quota`) — c'est le
comportement normal de la collecte, **sans rapport** avec le canal push.

⚠️ **`BW_DISCORD_WEBHOOK_URL` est TOUJOURS ABSENTE du `.env`.** Relevé par
**noms seuls** (`sed -E "s/=.*//"`, aucune valeur lue) : les **25 mêmes
variables**, fichier **inchangé depuis le 13/09 18:08**. ⇒ `bw_push_discord`
reste **codé, testé, muet** — et cette nuit il y avait **un ⛔ à pousser**.
`~/installer-webhook-discord.sh` attend toujours Yann : **34e jour.** ntfy reste
**seul canal push**.

## 8. ✅ ρ hors [0, 1] : **deuxième baisse — la série est bien une oscillation**

```
ⓘ référence combinée : 404 balise(s) sur 3 702 avaient un ρ hors [0, 1],
  ramené à la borne
```

```
307 (08/10) · 382 · 349 · 381 · 413 · 437 · 475 (14/10) · 452 · **404 (16/10)**
```

✅ **Deuxième recul consécutif (−48), et la question de la note du 14/10 est
définitivement close dans sa forme d'alors.** Elle appelait cette série « la
seule du journal qui monte franchement et **sans démenti** » et la désignait
« le candidat le plus net à un motif neuf » ; le 15/10 l'a corrigée une
première fois, cette nuit la confirme : **475 → 452 → 404**, soit **−15 % en
deux nuits**. **10,91 % du parc** contre 12,20 % hier et 12,82 % le 14/10.

⇒ ✅ **Rien n'a été créé, et il n'y a plus de raison de créer.** Le niveau
reste **+31,6 % au-dessus du 08/10** (307) : la série n'est pas revenue à son
point de départ, mais elle **oscille comme toutes les autres**. ⓘ **Troisième
série « en tendance nette » démentie en deux jours** — avec le coût par ligne
et `model_verif_daily`. Le journal produit des tendances apparentes à un rythme
d'environ **une par nuit** ; aucune n'a tenu plus de deux points.

## 9. ⚠️ Témoins du mélange : les deux mesures reculent, **et l'erreur absolue n'explique rien cette fois**

```
⛔ témoins du mélange : sur 7 575 balise-jours×échéance, le mélange fait
   2,7365 km/h contre 2,7671 pour le meilleur membre a priori
   (gain 1,1 %, mélange devant dans 49,9 % des cas) ;
   contre la moyenne UNIFORME, sur 1 124 : 2,819 vs 2,8956 (gain 2,6 %)
```

```
gain contre le MEILLEUR MEMBRE : 7,4 % → 5,5 → −0,6 (07/10) → +2,5 → −1,2 → −0,1 → −0,0 → +1,6 → +3,1 → +2,2 → +3,3 → **+1,1 (16/10)**
« devant » dans : 49,2 % → 50,1 → 49,1 → 49,2 → 50,1 → 51,6 → 50,0 → 52,3 → **49,9 %**
gain contre la moyenne UNIFORME : 6,0 % → 4,9 → 4,8 → 3,1 → 4,8 → 3,2 → 3,4 → 4,7 → 6,5 → 4,7 → 3,9 → **2,6 %**
```

⚠️ **Les deux mesures reculent ensemble** (−2,2 points contre le meilleur
membre, −1,3 contre l'uniforme), et « devant » repasse **sous 50 %**, après le
plus haut de la série hier (52,3 %).

⛔ **ET LA GRILLE DE LECTURE HABITUELLE NE MARCHE PAS CETTE NUIT.** La leçon du
12/10, confirmée quatre fois, dit que cet indicateur **suit l'erreur absolue**
(journée ventée ⇒ gain qui baisse, journée calme ⇒ gain qui monte). Or l'erreur
absolue est **PLATE** : 2,7485 → **2,7365 km/h**, soit **−0,4 %**. ⇒ **Pour la
première fois, le gain recule de 2,2 points sans que la météo du jour
l'explique.** ⚠️ **Je ne conclus rien** : c'est **une** nuit, et la série
oscille entre −1,2 % et +7,4 % depuis douze relevés.

⇒ ✅ **La décision du 12/10 de ne pas créer de motif Jira est MAINTENUE**, mais
**pour une raison plus faible qu'hier** : hier les deux mesures étaient
positives et cohérentes ; cette nuit elles reculent et l'explication habituelle
ne tient pas. ⓘ **À surveiller : si l'erreur absolue reste plate et que le gain
continue de baisser, la question d'un motif se repose — et cette fois avec un
argument propre.**

ⓘ Composition : **7 956** balise×échéance avec poids sur 30 j de cache (63,9 s)
— +6 h : 2 618 `bw_mix`, 414 témoins uniformes, 207 sans poids ; +24 h :
2 531 / 390 / 107 ; +48 h : 2 553 / 417 / 265.
ⓘ **Témoin du corrigé** : sur 9 194 balise-jours échantillonnés, le vrai
antécédent gagne **13,9 %** et celui d'une AUTRE balise **−1,8 %** — part
imputable au site **15,8 points**.

## 10. Le reste du journal

- ✅ **Self-test du scoring : VERT** (lot S3, aucune lecture réelle, aucune
  écriture). Écart des deux mélanges : `mse_comb` 17,841 contre `mse_comb_vec`
  17,841 (**+0,00 %**).
- ✅ **Stabilité des rangs : τ = 0,79 sur 71 cases** (0,735 / 65 le 15/10).
  **Les deux séries remontent ENSEMBLE, aux deux plus hauts de la série** :
  l'échantillon fait 57 → 53 → 54 → 50 → 56 → 62 → 65 → **71**, et τ passe de
  0,735 à **0,79**. ⓘ Hier elles divergeaient ; **à suivre, pas à conclure.**
- ✅ **4 écarts au recalcul indépendant** (4 le 15/10) — journée recalculée
  **2026-10-15**. **Tous en `fcstagrume`** et tous de la **même signature**
  (« 0 ou 1 h appariée ici (< 6) mais la base porte une ligne ») :
  `aemet:9990X` (agrume +24 h), `infoclimat:000PM` (agrume +24 h),
  `mf:26327001` (agrume_pi +6 h), `windsmobi:ffvl-3536` (agrume +24 h).
  ⓘ **Neuvième nuit de suite la même signature** (4 · 5 · 5 · 6 · 5 · 7 · 6 ·
  4 · **4**), **au plus bas de la série pour la deuxième nuit** ; les balises
  concernées **changent entièrement chaque nuit** : ce n'est pas un lot fixe,
  c'est un **désaccord systématique sur le seuil des 6 heures appariées**.
- **Murphy** : 66 095 triplets, 64 103 décomposés, 266 balises tenues dehors
  (doublon ou position suspecte), 0,8 s.
- **FDR** : brut 6 965 tests, 1 785 survivants à BH α = 0,1 (seuil p ≤ 0,02395,
  p min 0,00399), 123 rangs retirés sur 1 104 publiés ; corrigé 6 682 tests,
  1 185 survivants (seuil p ≤ 0,01597), 139 rangs retirés sur 649.
- **Duels appariés** : lead 6 → 65 296 lignes depuis le 16/09 (799 retirées) ;
  lead 24 → 24 032 lignes (301 retirées). ⓘ Cumul tronqué par la rétention 30 j.
- **Événements** : **29 220 combinaisons publiables**, 29 483 écartées sous le
  quorum de 8 ; **20 661 lignes** en base (`drop` 9 746, `onset` 8 451, `ramp`
  1 162, `reversal` 1 265, `breeze_yield` 37), 35 314 non publiées. ⓘ 3 448
  balises zonées, 1 419 cases fines dont **734** à moins de 2 balises.
- **Pression** : 17 836 lignes, 691 points de prévision portent `pmsl`,
  **860 appariées** (médiane 18,0 km) ; refusées : 211 hors rayon, 31 hors Δz,
  4 trop hautes.
- **Rétrécissement vers le parent** : 136 732 cases fines rapprochées de leur
  échelon supérieur.
- **Publication** : `model_scores.json` 121 138 Ko, `model_scores_light.json`
  7 203 Ko (522 Ko gzippé), `model_events.json` 8 153 Ko, `model_murphy.json`
  25 400 Ko (2 653 Ko gzippé).
- **Manches** : **49 nuits** suivies depuis le 24/08, **720 cases**
  zone×lead×modèle avec au moins une manche gagnée.
- **Accumulateurs** : 4 714 entrées écartées (`doublon_de`, lot L17), 286
  antérieures à la naissance de la balise (`notee_depuis`, lot L15-bis).
  ⓘ 9 balises nées sous leur identifiant (toutes au 25/09).
- **Rejeu d'archive** : 2 085 521 balise-jours sur 30 journées (0 rejouée, 0
  vide, 3 546 écartés) en 75,6 s.
- **Climatologie horaire** : 3 817 balises (246,1 s).
- **Observations** : 3 742 balises le jour, **3 742** la veille (identique).
- **`mutations_memoire`** : ⚠️ **HUITIÈME nuit sans aucune ligne au journal.**
  Le relevé « 3 mutations non vues (2, 5, 13) » ne peut pas être revérifié ;
  dette antérieure, **statut inchangé faute de mesure.**
- `✅ terminé (589 744 lignes écrites en base)` (634 450 le 15/10) ; `registre :
  1 ligne écrite (2026-10-16, 4 861 s, jalon max 3 384 Mo, swap 2 429,5 Mo)`.

## 11. ✅ Les tickets : état vérifié par GET **avant** et **après**, deux commentaires

GET `/rest/api/3/issue/<clé>?fields=summary,status,comment` avant écriture,
HTTP 200 sur les trois. Les trois sujets sont **ceux relevés le 07/10**,
inchangés.

| ticket | statut | comm. avant | canal utilisé | comm. après |
|---|---|---|---|---|
| **KAN-3** `bw-pente-duree` | **Terminé** / `done` | 24 | **aucun — par choix** | **24** ✅ |
| **KAN-4** `bw-pente-memoire` | **À faire** / `new` | 35 | `bw_jira_signaler bw-pente-memoire` | **36** ✅ |
| **KAN-5** `bw-purge-57014` | **À faire** / `new` | 18 | `bw_jira_signaler bw-purge-57014` | **19** ✅ |

**Ce que chaque commentaire porte :**

- **KAN-4** — ⚠️ **le coût par ligne rejouée REVIENT dans sa bande**
  (1 701,4 o, **+112,6**), ce qui **tranche la question n° 1 de la note du
  15/10 dans le sens « nuit atypique »**, avec la **correction explicite** de
  son titre ; le jalon à **3 384 Mo (+223)**, **+584** au-dessus du seuil ; le
  calcul à taux constant (**+224 Mo imputables au coût par ligne**, fenêtre
  **−616 lignes = −1,0 Mo** ; **31 Mo sous** le taux du 14/10 mais **60 Mo
  au-dessus** de celui du 29/09, l'avance d'hier **perdue**) ; les neuf jalons
  chiffrés et ✅ **le passage du « score par régime » SOUS le seuil** (2 606,
  −230) qui ramène les incidents de 3 à **2** ; ⚠️ **la deuxième nuit de
  divergence du swap, signes inversés** (pic **+202,9**, pages sorties
  **−445 543**, **le record d'hier ne tient pas**) ; les trois conditions de
  fermeture **1 sur 3** ; la pente du contrôle à **−73 Mo/nuit** ; la ligne en
  tuple et la **26e nuit sans levier** ; `mutations_memoire` non mesurable (8e
  nuit).
- **KAN-5** — bloc `model_score_zone` **propre pour la 9e nuit** (132 525 l. /
  8 tr., aucune tranche, aucune sonde, aucun « RESTENT »), **compteur 9 / 3**
  nuit par nuit ; ⛔ **mais `n_57014 = 1` sur `purge model_verif_daily`** et la
  **correction explicite** du « n'a pas récidivé » du 15/10, avec le relevé
  14/10 ✗ · 15/10 ✓ · 16/10 ✗ ; ⛔ **la réserve n° 1 démontrée une TROISIÈME
  fois** (10/10, 14/10, 16/10) et le précédent des 03–05/10 ; **la réserve n° 2
  entière** — le `.sql` **jamais joué, dix-sept jours** ; ⛔ **ma lecture
  RÉVISÉE À LA BAISSE : ne pas fermer**, et pourquoi fermer maintenant
  reviendrait à ne regarder qu'une adresse du 57014 ; les deux motifs qui
  resteraient sans ticket ; `bw_character_avance` propre (6e nuit) et le
  contrôle correctement muet (10e nuit).

⛔ **Aucune création, aucune transition, aucune réouverture, aucune fermeture.**
Les trois statuts sont **identiques** après écriture (revérifiés par GET).

ⓘ **Un seul canal employé, et le plus simple.** Le contrôle s'étant tu, les
jetons du jour étaient **libres** : `bw_jira_signaler` a servi pour les deux
motifs ouverts et a **posé les jetons** (`cri.jira.bw-pente-memoire` et
`cri.jira.bw-purge-57014` datent maintenant du **16/10 13:18**, côté `$HOME`
uniquement). **`bw_jira_commenter` n'a pas été nécessaire** : aucun motif
n'avait déjà parlé aujourd'hui, et KAN-3 n'avait rien à recevoir.
✅ Vérifié après coup : `/var/lib/bw-model-verif` est **inchangé** (17/09,
23/09, 06/10) — la relance manuelle du contrôle n'a rien écrit, puisqu'il s'est
tu.

ⓘ **Technique de l'envoi** (celle du 15/10) : les deux corps ont été écrits sur
le **Mac** (`/tmp/bw-16-10/`), encodés en base64 et passés au VPS **par
l'entrée standard de `ssh`**, décodés dans une **variable shell**. **Aucun
fichier n'a été déposé sur le VPS** en dehors des `mktemp -d` internes à
`bw_jira_http`, effacés par la fonction elle-même.

## 12. Ce qui a été touché

**VPS — règle de LECTURE SEULE pleine et entière, respectée.** Huit commandes
`ssh`, toutes en lecture sauf les deux POST Jira : `date -u`, `tail -n 3` du
registre, `systemctl list-timers`, `journalctl` du contrôle, plusieurs passes
de `journalctl -u bw-model-score.service` et `-u bw-garde-fou-r2.service` avec
`grep`, `controle_quotidien.py --verbeux`, `systemctl status` du garde-fou R2,
`grep` dans `bw_jira.sh` et `audit_r2.py`, `ls -la` des deux dossiers d'état,
`sed -E "s/=.*//"` sur le `.env`, et **six GET** Jira (trois avant, trois
après).
**Aucun `systemctl start/restart/daemon-reload`, aucun `enable`, aucun SQL
joué, aucun `rsync`, rien écrit dans `~/balise-watch` ni dans `/etc`. Rien
touché sur R2.**
⚠️ `controle_quotidien.py --verbeux` a été **relancé à la main** : c'est une
lecture (il n'écrit son jeton que s'il parle, et il s'est tu) — vérifié, les
jetons de `/var/lib/bw-model-verif` sont **inchangés** après la relance.
⚠️ `bw-garde-fou-r2.service` est laissé en **`failed`** : c'est son état normal
après un cri, et le remettre à zéro serait une écriture.
**Aucun secret lu par valeur** : le `.env` est **sourcé** (`set -a; . …;
set +a`) et lu **par noms de variables seuls**. `bw_jira.sh` passe par
`curl -K -`, jamais `-u`.
**Écritures Jira : deux commentaires** (voir §11).

**Mac** : deux corps de commentaire dans `/tmp/bw-16-10/` (fichiers de
travail), cette note dans `notes-projet/verdict-pente-16-10.md`. **Un commit
local**, depuis la **racine du dépôt serveur**. **Pas de `git push`.**

**Projet Claude** : cette note, **créée** (absente de la liste d'ouverture de
session).

**Notifications : DEUX** — la première sur le palier R2, **trop alarmiste**
(elle annonçait une chaîne qui casse et un garde-fou désarmé) ; la seconde la
**corrigeant** sur ces deux points, les faits chiffrés étant maintenus. Voir
§2.1.

## 13. ⚠️ L'horaire de la routine : **+4 h 03**

Programmée pour **07:07:05 UTC**, tirée à **11:09:44 UTC**.

```
02–03/10  AUCUN TIR
04–06/10  retard jusqu'à 4 h 10
07/10     à l'heure
08/10     +2 h 10      ·  09/10  +6 h 40  ·  10/10  +2 h 13
11/10     +5 h 51      ·  12/10  +10 h 59  ← pire valeur
13/10     +52 min      ·  14/10  +6 h 11  ·  15/10  +7 h 37
16/10     +4 h 03
```

⚠️ **Neuf matins sur quinze ont dérivé, deux n'ont pas tiré.** ⓘ **Le VPS est à
l'heure, et il n'y est pour rien** : notation à **05:57:05** (prochaine samedi
**05:55:47**), contrôle à **07:30:45** (prochain samedi **07:30:58**). **Le
trou est côté planification de la routine**, et il reste le premier risque du
dispositif.

## 14. Ce qui reste — et ce qui demande Yann

**Décisions, par ordre d'urgence :**

1. ⛔ **R2 : trancher la rétention d'`agrume/grille`.** Le compte est à
   **9,959 Go sur 10 (99,6 %)**, **41 Mo de marge**, après **+731 Mo en une
   nuit dont 692 sur ce seul préfixe** (673 → 769 objets, **tous réclamés**).
   ✅ Franchir le palier **facture, ne bloque pas** (et tu l'avais accepté le
   27/09) : **ce n'est pas une urgence de ce soir**, c'est une décision à
   froid. Levier chiffré le 25/09 : **rétention 3 → 2 runs ≈ −1,7 Go** ; un
   seul run retiré rend **≈ 700 Mo**. **C'est la décision n° 1 de la journée.**
2. ⛔ **Veux-tu un motif Jira `bw-r2-palier` ?** `bw-garde-fou-r2` a crié trois
   fois en neuf jours (08–10/10, puis ce matin) et **n'a aucun ticket**. Rien
   n'a été créé : **ça demande ton accord.**
3. ⚠️ **Corriger la pente d'`audit_r2.py`.** « Palier atteint dans **35 j** »
   après **641 j** hier : la pente est la **somme des 25e centiles des
   différences par préfixe**, et elle affiche **−0,004 Go/mois** pour le
   préfixe qui vient de prendre **692 Mo**. Défaut **écrit le 25/09**, toujours
   là. ⓘ **C'est le même statistique et le même aveuglement que la pente du
   contrôle de pente** : à traiter une fois pour les deux. C'est une
   **écriture**.
4. ⛔ **Jouer `diagnostic_base_sous_tension_2026-09-29.sql`** (lecture seule,
   9 blocs, SQL Editor). **DIX-SEPT JOURS d'attente.** ⛔ **Et la nuit vient de
   renforcer son utilité** : le 57014 est revenu sur `model_verif_daily`, donc
   la question « cette requête-ci, ou la base entière ? » n'est **toujours pas
   tranchée** — et c'est ce `.sql` seul qui la tranche.
5. ⛔ **FERMER KAN-5 ? NON, et je reviens sur l'avis d'hier.** Compteur du
   motif suivi **9 / 3**, septième jour où la question se pose ; mais
   `n_57014 = 1` sur `purge model_verif_daily`, **deuxième fois en trois
   nuits**, et la **réserve n° 1 est démontrée une troisième fois**. ⇒ **Ne pas
   fermer avant le `.sql`.** Et il faudra dire où vont « la base est sous
   tension » et `model_verif_daily`, sans ticket.
6. ⚠️ **Mémoire : la baisse d'hier ne s'est pas reproduite.** Coût par ligne
   **1 701,4 o (+112,6)**, **de retour dans la bande** ; jalon **3 384 Mo
   (+223)**. ✅ Un acquis réel : **deux incidents au lieu de trois** (le score
   par régime passe sous le seuil). ⇒ **Le remède reste la ligne en tuple**
   (≈ −1 030 o/ligne) après la mesure `tuple` vs `namedtuple` à la sonde.
   **KAN-4 reste ouvert (1 / 3), 26e nuit sans levier.**
7. ⛔ **Trancher les cas de position — les quatre tiennent, et aucun cri n'est
   parti** (pas de front, comportement voulu). `2171` (38,9 km), `1378`
   (18,5 km), `367` (6,8 km), `STATIC0491` (1 159 m), plus `1333` qui
   **continue de sortir du lot** (→ 2 j). Puis `position_suspecte` +
   `position_note` par `.sql`. ⓘ **La nuit illustre la question du 01/10** :
   quatre balises confirmées, deux depuis dix jours, **zéro signal**.
8. ⛔ **Lancer `~/installer-webhook-discord.sh`.** `BW_DISCORD_WEBHOOK_URL`
   toujours absente, **34e jour** — et cette nuit il y avait **un ⛔ à pousser**.
   ✅ Le `--ipv4` tient (3e push réel, HTTP 200), mais ntfy reste **seul**.
9. ⚠️ **Témoins du mélange : la grille de lecture ne marche plus.** Gain contre
   le meilleur membre **+1,1 %** (3,3 hier), « devant » **49,9 %**, contre
   l'uniforme **2,6 %** — les deux reculent **alors que l'erreur absolue est
   plate (−0,4 %)**. ⇒ **Décision du 12/10 maintenue (pas de motif)**, mais
   **pour une raison plus faible**. Si le gain continue de baisser à erreur
   constante, la question se repose **avec un argument propre**.
10. ⓘ **Un plancher de niveau pour `bw-regime-sensibilite` ?** La question **se
    vide** : compteur **0 / 2**, coût au **plus bas des seize relevés**
    (12,57 ms, −0,49). Le critère reste sensible au bruit, mais il n'a **rien
    produit à tort** en trois matins. **Plus pressant.**
11. ⚠️ **Instrumenter le bloc hors étapes de `run.sh` ?** **L'argument
    s'affaiblit une deuxième nuit** : 83 % du mouvement est **dans** les étapes
    et le poste est nommé (`glissant`, −75,1 s). Sur cinq nuits le hors-étapes
    a porté 90 %, −158 %, 97 %, 35 %, **17 %**. Décision à toi.
12. ✅ **Un motif `bw-rho-hors-bornes` ? NON — la question est close dans sa
    forme d'origine.** **475 → 452 → 404** (−15 % en deux nuits), **10,91 %** du
    parc. Le niveau reste +31,6 % au-dessus du 08/10, mais la série **oscille
    comme les autres**. Rien n'a été créé.
13. ⓘ **Un champ de bilan de purge au registre ?** (question du 08/10.) Avec
    `lignes_effacees` et `tranches`, le §5 tiendrait en trois lignes — et il
    faudrait **nommer la requête** qui porte le `n_57014`, comme les 14 et
    16/10 viennent de le montrer **deux fois**.
14. ⓘ **Faut-il un motif Jira pour une panne de canal ?** (question du 30/09.)
    **Un motif pour `bw_character_avance` ?** — propre pour la 6e nuit.

**Ce que la surveillance regardera au prochain run :**

15. **Le total R2** : **9,959 Go.** Le palier est-il franchi, et
    `agrume/grille` reprend-il 700 Mo ou les rend-il ?
16. **Le coût par ligne rejouée** : **1 701,4 o**, de retour dans la bande.
    Le 1 588,8 du 15/10 reste-t-il un point isolé ?
17. **Le 57014** : où sera-t-il ? `model_score_zone` (10e nuit propre ?),
    `model_verif_daily` (3e fois ?), ou ailleurs encore ?
18. **Le swap** : **troisième** nuit de divergence, ou recalage ?
19. **Les incidents mémoire** : **2** cette nuit. Le « score par régime » reste-t-il
    sous le seuil ?
20. **Les témoins du mélange** : le gain baisse-t-il encore **à erreur absolue
    constante** ? C'est la mesure à regarder en premier.
21. **La durée** : signature **inversée cinq fois**. `glissant` est à 942,4 s.
22. **ρ hors [0, 1]** : **404.** Troisième baisse, ou reprise ?
23. **τ et son échantillon** : **0,79 / 71**, les deux au plus haut ensemble.
24. **La position** : les six à 3 j, et `1333` à 2 j.
25. **`mutations_memoire`** : une neuvième nuit muette ?
26. **L'horaire** : **+4 h 03.** Neuf matins de dérive sur quinze.
