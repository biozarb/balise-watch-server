# Verdict de pente du 23/10/2026 — ⛔ **La durée monte en ATTENDANT, et le bloc non instrumenté fait un record.** Pour la première fois la hausse a un candidat nommé.

La nuit a tourné proprement. Le fait du jour n'est pas un chiffre isolé mais la
**convergence de trois constats** : la durée monte pendant que le CPU baisse
(donc de l'attente), le bloc hors étapes atteint son record sur 63 relevés, et
trois expirations de requête tombent **dans** ce bloc — sur la lecture exacte
qui avait tué le run du 19/09. Trois commentaires Jira posés, aucun ticket
fermé, rouvert ni créé.

## 13:40 (Paris) — routine Balise Watch, run complet

**Étape 0 : faite en entier.**

- `git log --oneline --since=midnight` dans `balise-watch-server` **et** dans
  `surveillance balise` : **aucun commit aujourd'hui** dans les deux dépôts
  ⇒ aucun autre run n'a tourné ce matin.
- `claude/verdict-pente-23-10.md` **absent** du projet (`project_read` répond
  « No doc at… ») ⇒ cette note est une **création**, pas une fusion.
- `claude/verdict-pente-22-10.md` lu en entier : run à 13:40, `n_57014 = 1`
  venu de `bw_character_avance`, trois commentaires, trois démentis du 21/10.
- `notes-projet/README.md` relu : les quatre règles.

## 1. Le relevé de la nuit du 22→23/10 — la nuit a bien tourné

`lancement = timer` · `result = success` · `exec_status = 0` · `oom = 0`
Début 05:55:06, fin 07:23:38 (Paris).

| | 21/10 | 22/10 | 23/10 | Δ nuit |
|---|---:|---:|---:|---:|
| `duree_s` | 5 113 | 5 242 | **5 300** | **+58** |
| `cpu_s` | 3 973,1 | 4 171,7 | **3 952,2** | ⛔ **−219,5** |
| `marge_s` | 2 987 | 2 858 | **2 800** | −58 |
| marge / garde (8 100 s) | 36,9 % | 35,3 % | **34,57 %** | ⛔ **−0,71 pt, plancher de la série** |
| étapes (somme) | 2 964,1 | 3 143,8 | **2 938,5** | −205,3 |
| **hors étapes** | 2 148,9 | 2 098,2 | ⛔ **2 361,5** | ⛔ **+263,3, RECORD** |
| `jalon_max_mo` | 3 424 | 3 412 | **3 210** | −202 |
| `mem_peak_mo` | 3 626,8 | 3 597,7 | **3 608,0** | +10,3 |
| `swap_peak_mo` | 2 183,0 | 2 206,0 | **2 180,7** | −25,3 |
| `swap_out_pages` | 2 115 062 | 2 450 545 | **2 573 036** | +122 491 |
| `n_57014` | 0 | 1 | ⛔ **4** | **+3** |
| `lignes_regime` | 133 252 | 136 857 | **134 729** | −2 128 |
| `lignes_score_zone` | 143 625 | 147 216 | **145 123** | −2 093 |
| `lignes_daily` | 66 746 | 66 744 | **68 433** | +1 689 |
| `balise_jours_rejeu` | 2 080 071 | 2 077 376 | **2 076 042** | −1 334 |

### Les deux rapports qui valent mieux que les valeurs brutes

**Coût par ligne rejouée** (`jalon_max_mo × 1048576 / balise_jours_rejeu`) :

```
16/10 1 701,2 o · 17/10 1 701,4 o · 18/10 1 706,1 o · 19/10 1 702,0 o
20/10 1 608,0 o · 21/10 1 726,1 o · 22/10 1 722,2 o · 23/10 1 621,3 o
```

⇒ **huit nuits, aucune pente dans aucun sens.** −100,9 o en une nuit.
✅ L'**élargissement d'amplitude** signalé le 21 puis le 22/10 **tient une nuit
de plus** : les quatre premières nuits tiennent dans 5 o d'écart, les quatre
dernières vont de 1 608 à 1 726 o. La « bande 1 686–1 717 » du 07/10 n'existe
plus ; c'est le centre d'une oscillation large.

**Coût par ligne de `regime`** (`etapes_s.regime / lignes_regime × 1000`) :

```
19/10 12,37 ms · 20/10 13,13 ms · 21/10 12,14 ms · 22/10 12,59 ms · 23/10 11,97 ms
```

⇒ ✅ **le critère `bw-regime-sensibilite` retombe à 0 / 2.** Le coût **baisse de
4,96 %**. La note du 22/10 laissait le critère à 1/2 et demandait de revérifier
ce matin : **la seconde hausse n'est pas venue**, donc pas de motif, et **aucune
question reposée à Yann** sur ce point. Le guet est refermé.

**Calcul ou attente ?** ⛔ `cpu_s` fait **−219,5 s** pendant que la durée fait
**+58 s**. Le CPU **baisse** pendant que la durée monte : c'est de l'**ATTENTE**,
pas du calcul — l'**inverse exact** des nuits du 06, 07 et 22/10.

## 2. ⛔ Le fait du jour : la hausse est entièrement HORS ÉTAPES, et c'est un record

```
            étapes     hors étapes   total
21/10      2 964,1       2 148,9     5 113
22/10      3 143,8       2 098,2     5 242
23/10      2 938,5       2 361,5     5 300
Δ nuit       −205,3        +263,3      +58
```

`regime` **−110,8** · `glissant` −59,6 · `stabilite` −33,6 · `rejeu` −1,3 —
**les quatre étapes instrumentées reculent toutes.**

**2 361,5 s est le RECORD du bloc hors étapes sur les 63 relevés comparables du
registre** (maximum précédent 2 254,2 s le 18/09 ; médiane 1 960,4 s). Sur les
huit nuits précédentes ce bloc tenait entre 1 950 et 2 149 s : **il en sort de
212 s.** Ce n'est pas une oscillation dans la bande, c'est une sortie de bande.

⚠️ Ce bloc (publication, Murphy, événements, pression, duels, purge) **n'est pas
instrumenté**. La demande de jalons de temps dans `run.sh` — ouverte depuis le
07/10, que la note du 22/10 qualifiait « sans urgence » parce que le bloc
**reculait** alors de 50,7 s — **redevient le geste le plus utile.**

## 3. ⛔ `n_57014 = 4` — et aucun des quatre n'est la purge

Recherche élargie à **toutes les unités sur 24 h** : exactement **4**
occurrences de « 57014 », les voici toutes.

```
06:14:01  ⚠️ rpc/bw_character_avance : HTTP 500 57014 — reprise 1/3
06:18:30  → model_character : 461 573 accumulateurs avancés sur 461 573 envoyés
06:25:09  ⚠️ model_verif_event [0-999] : HTTP 500 57014 — reprise 1/3
06:27:00  ⚠️ model_verif_event [0-999] : HTTP 500 57014 — reprise 1/3
06:28:00  ⚠️ model_verif_event [0-999] : HTTP 500 57014 — reprise 1/3
06:28:44  → model_events.json publié (9 046 Ko)
```

- `bw_character_avance` : **rattrapé, 461 573 / 461 573, zéro perte**, aucune
  reprise 2/3 ni 3/3. **Deuxième nuit d'affilée** pour cet objet.
- `model_verif_event [0-999]` : **trois** fois, **chacune rattrapée à la
  PREMIÈRE reprise** (aucun « 2/3 », aucun « 3/3 » au journal), et la
  publication a abouti.

⚠️ **Rappel de lecture, dans les deux sens.** `n_57014` compte les 57014
**partout** dans la nuit, pas seulement dans le bloc purge. Un compteur à 4 ne
vaut **pas à lui seul** une purge en échec, de même qu'un 57014 isolé ne vaut
pas « des lignes RESTENT » (leçon du 28/09). Le contrôle de 07:30:43 s'est tu
sur ce motif et **il a raison de se taire**.

### 3.1 ⛔ Ce qui est neuf, et pourquoi ça compte

Les trois 57014 de `model_verif_event [0-999]` sont les **trois seules
occurrences de cet objet en huit jours**. Répartition des 57014 sur 8 jours :
**16/10 : 1 · 22/10 : 1 · 23/10 : 4** — rien ailleurs.

C'est la lecture de la **première page** (`Range 0-999`) de `model_verif_event`.
L'en-tête de `score.RELECTURES` la nomme : « **la nuit du 18→19 [09] est morte
sur `model_verif_event [0-999]` après 1ʳᵉ, 2ᵉ ET 3ᵉ essai** » — et c'est pour
elle que `RELECTURES` est passé de 2 à 3, sur une mesure de production :

```
0,07 s · 0,08 s · 0,08 s · 0,07 s · ⛔ 8,46 s, 57014
```

⇒ « ce n'est plus la forme de la requête, c'est la base qui a un hoquet ».
**L'étape des événements est DANS le bloc hors étapes** (§2). Attente mesurée +
bloc non instrumenté en record + trois expirations datées dans ce bloc : **trois
constats convergents.**

⚠️ **Ce n'est pas une pente** — une nuit reste une nuit. Mais c'est la **première
fois que la hausse de durée est attribuable, même grossièrement, à un objet
nommé**, et ça déplace le dossier « base sous tension » du soupçon au motif.

### 3.2 ⛔ Erratum sur la note du 22/10

Elle écrivait « `n_57014 = 1` **après quatorze nuits à zéro** ». Le registre dit
autre chose : **14/10 = 1** et **16/10 = 1**. La série de zéros avant le 22/10
était de **cinq nuits** (17 au 21/10), pas quatorze. Corrigé ici et dans le
commentaire de KAN-5.

## 4. ✅ Purge `model_score_zone` — nuit propre, 16ᵉ d'affilée

```
→ purge model_score_zone : 138 395 ligne(s) effacée(s) en 8 tranche(s)
ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée.
```

- **Aucun avertissement de tranche** : pas une ligne
  `purge model_score_zone (?as_of=eq.J&regime=eq.R) : HTTP 500 57014`.
- **Aucune sonde en défaut** (pas de « plus vieille journée illisible »).
- **Aucun « des lignes RESTENT »** ⇒ rien ne reste en base.
- Nombre de lignes **lisible** et 8 tranches ⇒ **la purge a abouti**.
- Volume 138 395 contre 138 250 la veille : il suit la journée purgée, **il ne
  signifie rien**.

**Compteur de fermeture KAN-5 : 16 / 3.**

## 5. Mémoire — le jalon recule de 202 Mo, mais reste 410 Mo au-dessus du seuil

```
rejeu d'archive         3 004 → 2 980 Mo   (−24)     ⛔ au-dessus du seuil
score par régime        2 944 → 2 838 Mo   (−106)    ⛔ TOUJOURS au-dessus
oubli fenêtre rejouée   3 412 → 3 210 Mo   (−202)    ⛔ jalon max
```

**Trois `incidents`**, comme la veille. Le jalon max reste **+410 Mo au-dessus
du seuil** de 2 800 Mo ; le **swap au pic** recule à 2 180,7 Mo (record de la
veille non battu), mais il n'est pas proche de zéro.

⚠️ **Je ne fais pas du palier « score par régime » un mouvement de fond** : il
recule de 106 Mo et **reste au-dessus du seuil**. C'est exactement l'erreur de
la note du 21/10, qui l'avait annoncé « sous le seuil pour la première fois »
avant qu'il remonte de +161 Mo en une nuit.

**Contrôle de pente du 23/10 à 07:30:43 — MUET :**

```
ⓘ 85 relevé(s), 64 comparable(s) ; durée : 10 points, pente -69 s/nuit ;
  mémoire : 10 points, pente -188 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate/négative, ou échéance hors horizon
```

### 5.1 ⛔ Le calcul à taux constant, et la démonstration qu'il ne vaut rien

À **−188 Mo/nuit** depuis 3 210 Mo, le retour sous 2 800 Mo tomberait dans
**2,2 nuits, vers le 25/10**. Or :

| matin | pente affichée | échéance annoncée |
|---|---:|---|
| 21/10 | −22 Mo/nuit | 18/11 |
| 22/10 | −12 Mo/nuit | 12/12 |
| 23/10 | **−188 Mo/nuit** | **25/10** |

**L'échéance a bougé de sept semaines en deux nuits** pendant que les points
bougeaient de 3 193 → 3 424 → 3 412 → 3 210. ⇒ **l'estimateur de pente n'est
pas utilisable en prévision sur cette série**, et le chiffre est donné pour ce
qu'il vaut : rien. C'est la troisième fois en trois jours que ce calcul est
publié avec sa propre réserve ; cette fois la réserve est **démontrée**.

### 5.2 Le remède, inchangé

La **ligne en tuple** (§2.6 de l'enquête du 10/09) : ≈ **−1 030 o/ligne**, soit
≈ **−2 039 Mo** sur les 2 076 042 balise-jours rejoués de cette nuit. **Rien de
déployé côté mémoire depuis `af25efb` (21/09) — 32ᵉ jour.** ⚠️ L'élagage de
`units` avait rendu −124 Mo au lieu de −1 500 : les gains sont dans la
**structure**, pas dans le volume des champs. La mesure `tuple` vs `namedtuple`
à la sonde reste le préalable.

## 6. Durée — marge au plancher de la série, et le rappel du quantile

**Marge à 34,57 % du garde**, en recul de 0,71 pt : **le plus bas des neuf
dernières nuits** (plancher précédent 35,11 % le 20/10).

⚠️ **Deux bornes à ne pas franchir dans la lecture** :

- **5 300 s n'est PAS le record.** Le maximum des 63 relevés comparables est
  **5 318 s le 10/10**. La nuit est la 2ᵉ plus longue, pas la plus longue.
- **34,57 % n'est pas le plancher absolu** : le registre porte **5,87 % le
  09/09**, avant la remontée du garde. C'est le plancher de la série récente.

⛔ **Remontée du chien de garde : NON LANCÉE et NON PROPOSÉE.**
`controle_quotidien.proposition()` ne se déclenche pas (pente négative). La
forme reste connue si la hausse revient : écrire la mesure dans l'en-tête de
`10-timeout-s3.conf` (135 → 140/145 min), déployer, vérifier par
`systemctl show`. **C'est Yann qui décide et qui lance.**

⚠️ **Rappel de construction** : la pente du contrôle est le **25ᵉ centile des
différences**. Elle ignore par construction les deux plus grosses hausses : elle
n'a vu ni le +153 s du 01/10, ni le +336 s du 06/10, ni le +70 s du 07/10, ni le
+129 s du 22/10, ni le **+58 s de cette nuit**. Un « −69 s/nuit » annoncé le
matin d'une hausse n'est pas une contradiction, c'est le quantile qui travaille.

## 7. ⛔ R2 — `agrume/pi` confirmé, 10ᵉ nuit de +48 objets exactement

```
23/10   10,319 Go   (103,2 %)   ⛔ DÉPASSÉ de 319 Mo   6 856 objets
22/10   10,280 Go   (102,8 %)   ⛔ DÉPASSÉ de 280 Mo   6 794 objets
```

**+39 Mo et +62 objets en une nuit.** Série des dépassements : +22 Mo (17→18),
+74, +107, +83, +52, **+39 (22→23)**.

### 7.1 ✅ Le coupable reste `agrume/pi`

```
            agrume/grille                     agrume/pi
21/10   5,344 Go   769 obj          1,546 Go   3 477 obj   (+48)
22/10   5,323 Go   766 obj          1,567 Go   3 525 obj   (+48)
23/10   5,323 Go   766 obj          1,587 Go   3 573 obj   (+48)
```

**Dixième nuit consécutive à +48 objets exactement, sans un seul recul**, et
+20 Mo. Pente affichée **+0,579 Go/mois**, juste.
✅ `agrume/grille` **strictement inchangé** (5,323 Go, 766 objets) et
**intégralement réclamé** (766 / 766) : hors de cause, confirmé une nuit de plus.

### 7.2 ⛔ L'écart non réclamé grossit toujours au rythme exact de l'accumulation

```
│ agrume/pi/grille/                        19 présentes /   19 réclamées   ✓
│ agrume/pi/rafraichissement/              28 présentes /   28 réclamées   ✓
```

47 objets couverts sur **3 573** ⇒ **3 526 objets non réclamés par aucun index**
(3 478 hier). **+48 par nuit, exactement le rythme d'accumulation** : tout ce que
`agrume/pi` ajoute chaque nuit tombe hors de la vue des index. ⓘ Ce n'est pas la
preuve qu'ils sont orphelins ; c'est la constatation qu'on n'en sait rien.

### 7.3 ✅ Le diagnostic des fenêtres glissantes tient pour la quatrième nuit

```
arome/rafale   63 objets fixes   0,915 → 0,919 Go   pente affichée −0,320 Go/mois
arome/sol      63 objets fixes   0,637 → 0,640 Go   pente affichée −0,274 Go/mois
```

Les deux ont **encore grossi** et affichent **encore** une pente négative. La
pente totale annoncée est **+0,111 Go/mois** alors que le réel est ≈ 39 Mo/nuit,
soit ≈ **+1,2 Go/mois** : un facteur ≈ 11. Le mécanisme — le 25ᵉ centile des
différences appliqué à une série qui oscille sans dériver rend une valeur
négative, additionnée aux positifs réels — **confirmé une nuit de plus**.

### 7.4 ⓘ `bw-garde-fou-r2.service` est `failed` pour la 8ᵉ fois — toujours PAS une panne

```
⚠️  palier gratuit DÉPASSÉ : 10.32 Go sur 10 Go — R2 facture déjà
   run garde-fou-r2 en ÉCHEC (code 1, 5s) — 8 consécutif(s)
```

`systemctl show` : `NRestarts=0`, `ExecMainStatus=1`. La démonstration du 21/10
tient : `code 1` veut dire « j'ai quelque chose à dire », pas « je suis cassé ».
⇒ **rien à corriger, rien à chercher.** Et **deux cris partent pour le même
fait** (avertissement R2 + alerte générique « service en échec »).

## 8. ⛔ Position — 4 confirmées, la liste change, donc le cri part

```
⛔ position : 16 balise(s) divergent du gel (10 j lus), dont 4 CONFIRMÉE(S)
   ⛔ pioupiou:2171          38 915 m · 10 j · nœud + profil CHANGENT · Windbird 2171
   ⛔ pioupiou:84             9 748 m · 10 j · nœud + profil CHANGENT · PP84 JokAir Parapente
   ⛔ pioupiou:367            6 764 m · 10 j · nœud + profil CHANGENT · Le relais
   ⛔ infoclimat:STATIC0491   1 159 m · 10 j · nœud 0,01 CHANGE
⛔ position : 4 balise(s) CONFIRMÉE(S) — cri déposé pour envoi
```

✅ **La prévision du 22/10 est tenue au mot** : elle annonçait « `pioupiou:84`
est à 9 748 m et 9 j : **elle sera confirmée demain si elle tient** ». Elle a
tenu, elle est confirmée. **Liste 3 → 4 ⇒ le cri est parti** (`ⓘ push parti
(webhook, HTTP 200)` à 07:23:36, ALERTE « 4 balise(s), depuis au moins
10 jours »). ✅ **Quatrième vérification du mécanisme « à front, pas à état » en
quatre jours** : silence le 20/10 (liste constante), cri le 21/10 (changement),
silence le 22/10 (constante), cri le 23/10 (changement).
ⓘ La question du 01/10 reste ouverte : faut-il qu'il recrie à état constant ?

⚠️ **`pioupiou:1378` reste à 9 j** — et c'est en soi un fait : à 9 j hier, elle
devrait être à 10 j aujourd'hui. **Elle n'a donc pas divergé une des journées
lues**, ce qui l'empêche de se confirmer. Son écart reste à **340 941 m**
(341 km, bond du 22/10 depuis 18 508 m). ⓘ 341 km n'est pas un décalage de
coordonnées plausible : candidate nette « AUTRE balise », mais le compteur de
jours ne la confirmera pas tant qu'elle clignote.

**Le total reste à 16.** Les onze balises arrivées à 1 j hier (327, 1749, 1568,
1558, 70, 1724, 1715, 1435, 175, 2058, 633) sont **toutes à 2 j** : la fenêtre
se remplit, aucune n'a disparu. Rien à en conclure avant 10 j.

**Geste attendu de Yann** : trancher chaque cas, puis poser `position_suspecte` +
`position_note` sur `station_zone` par `.sql`.

## 9. Les trois correctifs du 07/10 — verdict correctif par correctif

| correctif | verdict du 23/10 |
|---|---|
| **1. webhook `--ipv4`** | ✅ **tient.** **Deux** `ⓘ push parti (webhook, HTTP 200)` — 07:23:36 (position) et 07:23:44 (garde-fou R2) — suivis d'un mail `smtpstatus=250`. **Aucun HTTP 429 ntfy** (recherche dédiée : 0). Volume du jour : **2 pushes**, dans la fourchette normale de 2 à 7 ⇒ aucun runner qui s'emballe. |
| **2. garde-fou des deux jetons** | ✅ **tient.** Le contrôle de 07:30:43 s'est tu : aucun jeton posé, aucun doublon possible. `controle_quotidien.sh` conserve son `$ETAT` — **non touché**. |
| **3. rejeu de purge ≠ échec** | ✅ **tient, et il a servi une seconde fois en creux** : aucun avertissement de tranche, donc `bilan_purge()` n'avait rien à rattraper — et il s'est tu **malgré `n_57014 = 4`**, ce qui est exactement la bonne lecture (§3). Sans ce correctif, KAN-5 aurait reçu « purge en échec » ce matin. |

## 10. Les autres témoins

- ✅ **Témoin du corrigé : la lecture du 22/10 est confirmée, ça oscille.** Part
  imputable au site : 24,1 (18/10) → 22,9 → 18,0 → 16,6 → 23,3 → **20,4 pt**.
  Version FIN, part secteur+heure : 14,3 → 12,7 → 8,5 → 9,8 → 10,5 → **12,6 pt**.
  Le 22/10 avait effacé la « baisse nette » du 21/10 et conclu « rien à
  surveiller : ça oscille » — **le sixième point le confirme**.
- **Témoins du mélange — oscillation sans dérive, et la journée est bien plus
  calme.** Sur 7 447 balise-jours×échéance : **4,6873 km/h** contre 4,6911 pour
  le meilleur membre a priori ⇒ **gain +0,1 %**, devant dans **46,0 %** des cas ;
  contre la moyenne **uniforme** (n = 1 101) : 4,8435 vs 5,0475 ⇒ **gain +4,0 %**.
  Série du gain a priori : −0,6 % (07/10) · +2,5 · +1,7 · −0,3 · +0,9 · −0,9 ·
  **+0,1 % (23/10)**. ⓘ L'erreur absolue **retombe de 5,73 à 4,69 km/h** :
  journée nettement moins ventée, après deux jours de hausse. ⇒ **sept points
  qui oscillent autour de zéro : pas de motif Jira à demander.**
- ⓘ **Écart des deux mélanges** : `mse_comb` 17,841 contre `mse_comb_vec` 17,841
  (**+0,00 %**) — les deux chemins restent confondus.
- ⚠️ **Écarts du recalcul indépendant : 7** (4 le 22/10, 3 le 21/10, 5 le 20/10).
  En hausse, mais la signature est la même qu'avant (`0 h appariées ici (< 6)
  mais la base porte une ligne`). Récurrent, antérieur. **Quatre points qui vont
  de 3 à 7 ne font pas une pente** — à revérifier demain, rien de plus.
- **Duels** : `arome_r2 ↔ meteofrance_arome_france_hd (+6 h)`, n = **17 111**,
  moyenne +0,082, médiane **+0,096**, IC95 [+0,078 ; +0,113] → `b_better`,
  inchangé. Cumul toujours **tronqué par la rétention 30 j** (dette connue,
  `duel.DUEL_DAYS`).
- **Murphy** : 65 841 triplets, 64 046 décomposés, 266 balises tenues dehors.
- **Second canal du téléphone (Discord)** : ⛔ **`BW_DISCORD_WEBHOOK_URL`
  toujours ABSENTE** du `.env` (recherche sur le **nom seul**, `grep -c` = 0,
  aucune valeur lue). Aucun `ⓘ push Discord parti` au journal — cohérent.
  `~/installer-webhook-discord.sh` attend toujours que Yann le lance : **42ᵉ jour**.
- **`mutations_memoire`** : ⓘ **aucune ligne au journal cette nuit non plus** — je
  ne conclus rien : la dette de 3 mutations non vues (2, 5, 13) est reportée
  telle quelle, à revérifier.
- ⓘ `bw-model-oracle.service` : **non examiné**, hors mission.

## 11. Les tickets — ce qui a été fait

**États revérifiés par GET avant toute écriture :**

```
KAN-3 | Terminé | done | updated 2026-10-22T13:40:34+0200 | 29 comm.
KAN-4 | À faire | new  | updated 2026-10-22T13:40:34+0200 | 42 comm.
KAN-5 | À faire | new  | updated 2026-10-22T13:40:35+0200 | 25 comm.
```

⇒ les trois `updated` sont ceux du run du 22/10 : **aucune écriture d'un tiers
depuis**. Pas de collision.

| ticket | décision du 23/10 |
|---|---|
| **KAN-3** | ✅ **commenté** (canal délibéré). La durée **AUGMENTE** (+58 s) : la consigne s'applique. Chiffres, **inversion de signature** (`cpu_s` −219,5 ⇒ attente), répartition par étape avec les quatre étapes en recul, **record du bloc hors étapes sur 63 relevés** et le fait qu'il **n'est pas instrumenté**, le candidat daté `model_verif_event [0-999]`, marge au plancher de la série, rappel du 25ᵉ centile, bornes de lecture (5 318 s le 10/10 est le vrai record), et la forme de la proposition de remontée du garde **sans la lancer**. **Non rouvert, non transité** — il reste « Terminé ». |
| **KAN-4** | ✅ **commenté**, **reste ouvert**. Les trois conditions de fermeture : contrôle muet ✔, plafond retombé ✘ (**+410 Mo**), swap au pic ≈ 0 ✘ (**2 180,7 Mo**). Le commentaire porte les trois incidents, la série à **huit nuits** du coût par ligne rejouée, le refus explicite de lire « score par régime » comme un mouvement de fond, et le **tableau des trois échéances contradictoires** (18/11, 12/12, 25/10) qui démontre que l'estimateur de pente n'est pas utilisable en prévision. |
| **KAN-5** | ✅ **commenté**, **reste ouvert**. Compteur **16 / 3**, purge propre détaillée, et surtout **les quatre 57014 nommés un par un** : aucun n'est la purge. L'**erratum** sur les « quatorze nuits à zéro » du 22/10. Le lien daté avec le run mort du 19/09 et le `.sql` « base sous tension » (**25ᵉ jour**). Trois questions posées à Yann, **rien créé ni fermé**. |
| `bw-r2-palier` | ⛔ **non créé.** Décision de Yann. |
| motif `model_verif_event` | ⛔ **aucun motif créé.** Trois occurrences rattrapées à la première reprise ne justifient pas un ticket de ma seule initiative ; la question est posée dans KAN-5. |
| motif `bw_character_avance` | ⛔ **aucun motif créé.** Deuxième nuit, rattrapé les deux fois. Question posée dans KAN-5. |
| `bw-regime-sensibilite` | ⛔ **non posé, et le guet est refermé** : le critère retombe à **0 / 2** (le coût baisse de 4,96 %). Aucune question reposée à Yann. |

**Canal : `bw_jira_commenter <CLÉ>`** pour les trois, choix assumé : le contenu
est de l'analyse multi-nuits avec erratum de la veille, et `commenter` prend une
**clé**, ne cherche rien, ne crée rien, ne touche pas au jeton du jour —
**aucun risque de créer un ticket neuf**, y compris sur KAN-3 qui est « Terminé ».

✅ **Corps passés par des heredocs `<<'EOF'` non interprétés**, pipés par
`ssh … bash -s` depuis un script écrit sur le Mac : **rien n'a été écrit sur le
VPS**. **Vérifié par GET après coup** : 30 / 43 / 26 commentaires, statuts
inchangés (`Terminé` / `À faire` / `À faire`), 7 292 / 5 991 / 7 391 octets, et
`2 361,5`, `model_verif_event`, `−219,5`, `34,57`, `10-timeout-s3.conf`,
`3 210`, `1 621,3`, `af25efb`, `tuple`, `−188 Mo`, `461 573`, `138 395`,
`quatorze`, `25e jour`, `16 / 3` tous présents dans le bon ticket. **Aucun nom
avalé, aucun erratum nécessaire.**

⚠️ **Piège de signature rencontré et corrigé** : `bw_jira_http` attend un chemin
**complet** (`/rest/api/3/issue/KAN-3?…`), pas `issue/KAN-3?…` — un chemin
relatif rend **HTTP 000**, ce qui ressemble à une panne de réseau alors que le
canal va bien. À ajouter au piège déjà noté le 22/10 (quatre positionnels :
`méthode chemin corps sortie`). Les deux ensemble expliquent tous les `000`.

## 12. Horaire de la routine — +4 h 21

Programmée pour **07:09:05 UTC**, tirée à **11:30:00 UTC**.

```
15/10 +7 h 37 · 16/10 +4 h 03 · 17/10 +1 h 56 · 18/10 +1 h 39 · 19/10 +7 h 43
20/10 +3 h 41 · 21/10 +8 h 50 · 22/10 +4 h 23 · 23/10 +4 h 21
```

Quasiment le même retard qu'hier (−2 min), mais sur neuf matins il va de 1 h 39
à 8 h 50 **sans aucune régularité**. ⓘ Le VPS, lui, est **à l'heure** : notation
à 05:55:06, contrôle à 07:30:43, timer suivant armé pour le **24/10 à 07:30:17**.
**Le trou est côté planification.**

## 13. Décisions en attente de Yann — la liste à jour

1. ⛔ **R2 : rétention sur `agrume/pi`** — **+48 objets chaque nuit, dix nuits
   d'affilée, sans un seul recul**. Le compte est à **103,2 %** du palier et R2
   facture. **Le plus urgent.**
2. ⛔ **Inventaire des 3 526 objets de `agrume/pi` que l'index ne réclame pas**
   (sur 3 573). L'écart grossit de +48/nuit, exactement le rythme
   d'accumulation : à faire **avant** toute rétention.
3. ⛔ **`diagnostic_base_sous_tension_2026-09-29.sql`** — toujours pas joué,
   **25ᵉ jour**. ⬆️ **Il monte dans la liste** : cette nuit lui donne un motif
   chiffré qui ne vient plus de la purge (§3.1 — trois expirations sur la
   lecture qui avait tué le run du 19/09, attente mesurée, bloc non instrumenté
   en record). Porte de sortie de KAN-5, qui est à 16 nuits propres.
4. ⛔ **Jalons de temps dans le bloc hors étapes de `run.sh`** — ⬆️ **passe de
   « sans urgence » à utile** : ce bloc fait **+263,3 s** et son **record sur
   63 relevés**, et c'est le seul endroit où la hausse de durée se cache. C'est
   une **écriture** dans `run.sh` : non faite.
5. ⛔ **Mémoire : la ligne en tuple** (≈ −1 030 o/ligne, ≈ −2 039 Mo). **32ᵉ jour
   sans rien de déployé** depuis `af25efb`. Porte de sortie de KAN-4.
6. ⛔ **Pente d'`audit_r2.py`** : ne pas additionner les pentes négatives des
   préfixes à fenêtre glissante, ou les borner à zéro par le bas (§7.3). Une
   ligne de code, mais c'est une **écriture** : non faite.
7. ⛔ **Motif `bw-r2-palier`** — non créé, ton accord requis.
8. ⛔ **Les 4 cas de position** (§8) : trancher, puis `position_suspecte` +
   `position_note` par `.sql`. ⚠️ **Et regarder `pioupiou:1378`** : 341 km, mais
   **bloquée à 9 j parce qu'elle clignote** — elle ne se confirmera jamais seule.
9. ⓘ **Les 57014 de `model_verif_event [0-999]` méritent-ils un motif propre ?**
   Aucun créé ; question posée dans KAN-5.
10. ⓘ **Celui de `rpc/bw_character_avance`**, deuxième nuit d'affilée, rattrapé
    les deux fois : suivi propre ou pas ? Rien créé.
11. ⓘ **Fermeture de KAN-5** à 16/3 nuits propres : ton accord ?
12. ⚠️ **`installer-webhook-discord.sh`** — **42ᵉ jour**, variable toujours absente.
13. ⓘ **Horaire de la routine** : +4 h 21 ce matin. Côté planification.
14. ⓘ **Le cri de position doit-il recrier** à état constant ? (ouvert depuis le
    01/10 ; le comportement « à front » est maintenant vérifié quatre jours de suite)
15. ⓘ **`bw-model-oracle.service` en `failed`** — hors mission, non examiné.

## 14. Ce que ce run a DÉMENTI, et ce qu'il a CONFIRMÉ, de la note du 22/10

⚠️ **La note du 22/10 était largement juste** — c'est la première fois en
plusieurs jours qu'il n'y a pas de démenti de fond à poser. Un seul erratum
factuel, et deux renversements de lecture qu'elle avait elle-même annoncés
comme à revérifier.

| annoncé le 22/10 | relevé le 23/10 |
|---|---|
| ⛔ « `n_57014 = 1` après **quatorze nuits à zéro** » | **faux** : le registre porte 14/10 = 1 et 16/10 = 1 ⇒ **cinq** nuits de zéros (17–21/10). Erratum posé dans KAN-5. |
| ⓘ critère `regime` « à **1/2**, à revérifier demain : une seconde hausse remplirait le critère » | **la seconde hausse n'est pas venue** : −4,96 %, critère **0/2**, guet refermé. La prudence était la bonne. |
| ⓘ « la demande de jalons de temps reste ouverte **sans urgence** » (hors étapes −50,7 s) | **renversé par les chiffres** : hors étapes **+263,3 s et record sur 63 relevés**. La qualification « sans urgence » était juste **cette nuit-là**, elle ne l'est plus. |
| « c'est du **calcul**, pas de l'attente » (`cpu_s` +198,6) | **inversé** : `cpu_s` **−219,5** pendant que la durée monte ⇒ **attente**. Pas un démenti : une nuit différente. |

✅ **Ce que le 22/10 avait juste et qui tient** : `agrume/pi` est le coupable R2
(**10ᵉ nuit à +48**), `agrume/grille` hors de cause et **strictement inchangé à
766 objets**, le mécanisme des pentes négatives des fenêtres glissantes (§7.3),
le comportement « à front » du cri de position (4ᵉ vérification), **la prévision
nominative que `pioupiou:84` serait confirmée ce matin**, l'amplitude élargie du
coût par ligne rejouée (§1), la lecture de `bw-garde-fou-r2` en `failed` comme
un signal et non une panne, le témoin du corrigé qui « oscille », et la lecture
du compteur `n_57014` comme un compteur de nuit entière et non de purge — qui a
resservi **exactement** ce matin, à 4 au lieu de 1.

⚠️ **« Une nuit ne fait pas une pente » — septième fois en quatorze jours.**
Appliqué cette nuit à : le record du bloc hors étapes (§2), les 7 écarts du
recalcul (§10), le palier « score par régime » qui recule (§5), et le gain du
mélange repassé positif (§10). Aucun des quatre n'est présenté comme une
tendance.

## 15. Respect des règles

✅ **VPS en lecture seule.** Aucun `systemctl` start/restart/daemon-reload, aucun
`enable`, aucun SQL joué, aucun rsync, **rien écrit sur le VPS** — pas même un
fichier temporaire : les scripts de GET et de commentaires ont été écrits sur le
Mac et pipés par `ssh … bash -s`. Seules écritures : les trois commentaires Jira.
✅ **Aucun secret lu par valeur** : le `.env` a été **sourcé** (`set -a; . …;
set +a`) pour Jira ; `BW_DISCORD_WEBHOOK_URL` cherchée **par son nom seul**
(`grep -c`) ; le jeton Jira passe par `curl -K -`, jamais `-u`.
✅ `10-timeout-s3.conf` **non touché**, remontée du garde **non lancée, non
proposée** (`proposition()` ne se déclenche pas).
✅ `controle_quotidien.sh` **non touché**, son `$ETAT` conservé.
✅ Aucun ticket créé, fermé, rouvert ni transité. `bw-r2-palier` non créé, motifs
`model_verif_event` et `bw_character_avance` non créés, `bw-regime-sensibilite`
non posé.
✅ **Desktop Commander exclusivement** pour fichiers et shell.
✅ Aucun `git push`. Commit local depuis la **racine** du dépôt serveur.
✅ Scripts temporaires effacés après usage.
