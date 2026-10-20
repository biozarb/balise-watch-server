# Verdict de pente du 20/10/2026 — ⛔ **R2 : le coupable est `agrume/pi`, pas `agrume/grille`. La note du 19/10 est corrigée.**

La nuit est saine par ailleurs. Lecture du VPS complète, trois commentaires
Jira postés, aucun ticket fermé, rouvert ni créé.

## 12:55 (Paris) — routine Balise Watch, run complet

**Étape 0 : faite en entier.**

- `git log --oneline --since=midnight` dans `balise-watch-server` **et** dans
  `surveillance balise` : **aucun commit aujourd'hui** dans les deux dépôts.
  ⇒ aucun autre run n'a tourné ce matin.
- `claude/verdict-pente-20-10.md` **absent** du projet (vérifié par
  `project_read`, qui répond « No doc at… ») ⇒ cette note est une **création**,
  pas une fusion.
- `claude/verdict-pente-19-10.md` lu en entier : run complet, R2 franchi à
  10,038 Go, KAN-4 et KAN-5 commentés à 17:59.
- `notes-projet/README.md` relu : les quatre règles.

## 1. Le relevé de la nuit du 19→20/10 — la nuit a bien tourné

`lancement = timer` · `result = success` · `exec_status = 0` · `oom = 0`
Début 05:55:36, fin 07:23:22 (Paris). 719 402 lignes écrites en base.

| | 18/10 | 19/10 | 20/10 | Δ nuit |
|---|---:|---:|---:|---:|
| `duree_s` | 5 172 | 5 103 | **5 256** | **+153** |
| `cpu_s` | 4 131,5 | 4 031,5 | **4 171,4** | **+139,9** |
| `marge_s` | 2 928 | 2 997 | **2 844** | −153 |
| marge / garde (8 100 s) | 36,1 % | 37,0 % | **35,1 %** | ⛔ plus bas de la série |
| `jalon_max_mo` | 3 391 | 3 381 | **3 193** | **−188** |
| `mem_peak_mo` | 3 609,3 | 3 607,3 | **3 591,7** | −15,6 |
| `swap_peak_mo` | 2 275,9 | 2 190,5 | **2 151,5** | −39,0 |
| `swap_out_pages` | 2 592 870 | 2 151 461 | **2 756 422** | ⚠️ **+604 961** |
| `n_57014` | 0 | 0 | **0** | = |
| `lignes_regime` | 128 148 | 130 654 | **132 406** | +1 752 |
| `lignes_score_zone` | 138 545 | 141 051 | **142 819** | +1 768 |
| `balise_jours_rejeu` | 2 084 163 | 2 082 945 | **2 082 153** | −792 |

### Les deux rapports qui valent mieux que les valeurs brutes

**Coût par ligne rejouée** (`jalon_max_mo × 1048576 / balise_jours_rejeu`) :

```
16/10 1 701,2 o · 17/10 1 701,4 o · 18/10 1 706,1 o · 19/10 1 702,0 o · 20/10 1 608,0 o
```

⇒ **−94 o en une nuit, et la première sortie PAR LE BAS de la bande
1 686–1 717 o** posée le 07/10. Après neuf nuits de plat, c'est le premier
mouvement de fond apparent. ⚠️ **Une nuit ne fait pas une pente** — cette leçon
a resservi quatre fois en dix jours. **Point à confirmer sur deux ou trois
nuits, et surtout pas à reprendre comme une tendance.**

**Coût par ligne de `regime`** (`etapes_s.regime / lignes_regime × 1000`) :

```
16/10 12,57 ms · 17/10 13,12 ms · 18/10 13,04 ms · 19/10 12,37 ms · 20/10 13,13 ms
```

⇒ **le critère `bw-regime-sensibilite` est à 1 / 2**, pas rempli : une hausse
isolée après une baisse franche, pas deux hausses consécutives. **Aucun motif
posé, aucune question reposée à Yann sur ce point.**

**Calcul ou attente ?** `cpu_s` +139,9 s pendant que la durée fait +153 s :
c'est du **calcul**, pas de l'attente.

## 2. ⛔ R2 — LE COUPABLE EST IDENTIFIÉ, et ce n'est pas celui qu'on croyait

```
20/10   10,145 Go   (101,5 %)   ⛔ DÉPASSÉ de 145 Mo   6 668 objets
19/10   10,038 Go   (100,4 %)   ⛔ DÉPASSÉ de  38 Mo   6 606 objets
```

**+107 Mo et +62 objets en une nuit.** La série des dépassements s'accélère :
+22 Mo (17→18), +74 Mo (18→19), **+107 Mo (19→20)**.

Le garde-fou a crié **trois fois** ce matin, dans les trois appelants :
`⚠️ palier gratuit DÉPASSÉ : 10.15 Go sur 10 Go — R2 facture déjà`.

### 2.1 ⛔ Correction de la note du 19/10 : `agrume/grille` est HORS DE CAUSE

La note du 19/10 (§2 et §12 point 1) désignait `agrume/grille` comme l'auteur
des à-coups et mettait sa rétention en tête des décisions. **Les chiffres de
sept nuits la démentent** :

```
            agrume/grille                     agrume/pi
14/10   5,323 Go   766 obj          1,403 Go   3 141 obj
15/10   4,652 Go   673 obj          1,423 Go   3 189 obj   (+48)
16/10   5,344 Go   769 obj          1,445 Go   3 237 obj   (+48)
17/10   5,323 Go   766 obj          1,465 Go   3 285 obj   (+48)
18/10   5,323 Go   766 obj          1,485 Go   3 333 obj   (+48)
19/10   5,323 Go   766 obj          1,506 Go   3 381 obj   (+48)
20/10   5,323 Go   766 obj          1,527 Go   3 429 obj   (+48)
```

- **`agrume/grille` est strictement plat depuis quatre nuits** — même taille au
  millième de Go, même compte d'objets, pente mesurée **−0,004 Go/mois**. Son
  seul mouvement de la semaine est le creux du 15/10 (−671 Mo) immédiatement
  rendu le 16/10 : une **oscillation**, pas une accumulation. Une rétention sur
  `agrume/grille` ne rendrait rien du tout aujourd'hui.
- **`agrume/pi` grossit de EXACTEMENT +48 objets et de +20 à +22 Mo chaque
  nuit, sept nuits d'affilée, sans un seul recul.** C'est une **accumulation
  monotone**, soit ≈ **+0,62 Go/mois**, et c'est **la seule** de ce profil dans
  tout le compte. Sa propre pente affichée (+0,577 Go/mois) est **juste**.

### 2.2 ⛔ Et l'index ne réclame que 47 de ses 3 429 objets

```
│ agrume/pi/grille/                        19 présentes /   19 réclamées   ✓
│ agrume/pi/rafraichissement/              28 présentes /   28 réclamées   ✓
```

19 + 28 = **47 objets couverts sur 3 429**. **3 382 objets du préfixe
`agrume/pi` ne sont vérifiés par aucun index** — le bloc « tout est-il
réclamé ? » affiche trois coches vertes et passe à côté de 98,6 % du préfixe.
C'est exactement le **profil « orphelins »** déjà documenté pour
`agrume/grille` (`orphelins-agrume-grille-26-09.md`, `-10-10.md`). ⓘ Ce n'est
pas une preuve qu'ils sont orphelins — c'est la constatation qu'**on n'en sait
rien**, et que la question n'a jamais été posée pour ce préfixe.

### 2.3 ⛔ Pourquoi la jauge n'a rien vu venir — le mécanisme

Le total annonce **+0,064 Go/mois** alors que le réel est ≈ +3,2 Go/mois.
L'en-tête le dit lui-même : *« pente mesurée : somme des préfixes, 25e centile
des différences »*. Or les préfixes à **fenêtre glissante** (compte d'objets
FIXE, taille qui oscille avec la météo du jour) rendent de **gros faux
négatifs** :

```
arome/rafale   63 objets fixes   0,815 → 0,892 Go en 7 j   pente affichée −0,351 Go/mois
arome/sol      63 objets fixes   0,567 → 0,619 Go en 7 j   pente affichée −0,279 Go/mois
arome/alt     441 objets fixes                             pente affichée −0,087 Go/mois
arome/lod     407 objets fixes                             pente affichée −0,047 Go/mois
                                                   somme ≈ −0,764 Go/mois
```

Ces quatre-là **ont tous grossi** sur la semaine, et affichent tous une pente
négative. Leur somme **annule à elle seule** le +0,577 de `agrume/pi`. Retirer
les fenêtres glissantes de la somme donne une pente ≈ **+0,8 Go/mois** : à ce
rythme, le palier était **prévisible depuis des semaines**, au lieu d'être
annoncé « dans 57 j » le 17/10 et « dans 0 j » le 19/10.

⚠️ **La cause n'est donc pas « le rythme mesuré sous-estime » en général** (ce
que disait la note du 19/10) : c'est que **le 25e centile des différences,
appliqué à une série qui oscille sans dériver, rend une valeur négative**, et
que ces négatifs sont additionnés aux positifs réels.

### 2.4 ⛔ Décisions pour Yann — rien n'a été créé, modifié ni supprimé

1. **Rétention sur `agrume/pi`** — c'est **le fond** de la croissance, +48
   objets/nuit sans fin. C'est la décision qui compte. *(remplace « rétention
   d'`agrume/grille` », qui ne rendrait rien)*
2. **Inventaire des 3 382 objets non réclamés de `agrume/pi`** — avant toute
   rétention, savoir ce qu'ils sont. Même démarche que pour `agrume/grille` en
   septembre.
3. **Pente d'`audit_r2.py`** — ne pas sommer la pente des préfixes à fenêtre
   glissante, ou la borner à zéro par le bas. Une ligne de code, mais c'est une
   **écriture** : je ne l'ai pas faite.
4. **Motif Jira `bw-r2-palier`** — toujours **non créé** (aucun ticket ne porte
   ce label). Le créer suppose ton accord.

ⓘ Écritures de la nuit : `backend=r2 écritures=4 (plafond 10) lectures=0
suppressions=0 octets=170,4 Mo` — nominal, et **ce n'est pas le coupable** (ces
écritures écrasent en place).

## 3. Purge `model_score_zone` — nuit propre, 13ᵉ d'affilée

```
→ purge model_score_zone : 138 363 ligne(s) effacée(s) en 8 tranche(s)
ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée.
```

- **Aucun 57014** : ni au registre (`n_57014 = 0`), ni dans le bloc purge, ni
  nulle part ailleurs dans le journal de la nuit (vérification élargie).
- **Aucun avertissement de tranche**, donc aucun rejeu à interpréter.
- **Aucune sonde en défaut** (pas de « plus vieille journée illisible »).
- **Aucun « des lignes RESTENT »** ⇒ rien ne reste en base.
- Nombre de lignes **lisible** et 8 tranches ⇒ **la purge a abouti**.
- Volume effacé 138 363 (137 901 le 19/10) : il suit la journée purgée, **il ne
  signifie rien**.

**Compteur de fermeture KAN-5 : 13 / 3.**

## 4. Mémoire — le plafond recule franchement, mais un témoin va à contre-sens

Le **jalon max** fait **−188 Mo** (3 381 → 3 193), la plus forte baisse de la
série récente. Il reste **+393 Mo au-dessus** du seuil de 2 800. Le pic
processus baisse (−15,6) et le swap au pic aussi (−39,0 ; −124,4 sur deux
nuits).

⚠️ **Mais `swap_out_pages` fait +604 961 et atteint 2 756 422, un record sur la
fenêtre**, alors que le pic de swap baisse. Les deux ne disent pas la même
chose : le **pic** dit ce qui est occupé à l'instant le plus chargé, les **pages
sorties** disent combien le noyau a dû évacuer sur toute la nuit. **C'est le
second qui se dégrade**, et il faut le suivre.

Trois jalons restent au-dessus du seuil, comme hier, mais ils ne bougent pas
ensemble :

```
rejeu d'archive         2 993 → 3 000 Mo   (+7)
score par régime        2 835 → 2 816 Mo   (−19)
oubli fenêtre rejouée   3 381 → 3 193 Mo   (−188)
```

**Contrôle de pente du 20/10 à 07:31:01 — MUET :**

```
ⓘ 82 relevé(s), 61 comparable(s) ; durée : 10 points, pente -14 s/nuit ;
  mémoire : 10 points, pente -22 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate/négative, ou échéance hors horizon
```

⚠️ **Le contrôle annonce −14 s/nuit sur la durée alors que la nuit fait
+153 s.** C'est le 25ᵉ centile des différences faisant son travail : par
construction il ignore les deux plus grosses hausses. Il n'a vu ni le +153 s du
01/10, ni le +336 s du 06/10, ni le +70 s du 07/10, **ni celle-ci**.

## 5. Durée — la hausse est DANS les étapes, l'inverse du 07/10

```
            étapes     hors étapes   total
19/10      3 004,4       2 098,6     5 103
20/10      3 153,4       2 102,6     5 256
Δ            +149,0         +4,0      +153
```

**97,4 % de la hausse est dans les étapes**, et **+122,6 s dans `regime` seul**
(82 % du total) · `glissant` +18,0 · `rejeu` +9,6 · `stabilite` −1,2.

C'est **l'inverse de la signature du 07/10**, où 85 % de la hausse était **hors
étapes**. Le bloc hors étapes (publication, Murphy, événements, pression,
duels, purge) est **stable cette nuit** (+4 s) : il reste non instrumenté, mais
**il n'est pas en cause ici**. La demande de jalons de temps dans `run.sh`
(question du 07/10 à Yann) perd encore de son urgence.

**Découplage temps / volume sur `regime`** :

```
lignes_regime  130 654 → 132 406   (+1 752, +1,34 %)
temps regime   1 615,6 → 1 738,2 s (+7,59 %)
coût par ligne    12,37 → 13,13 ms (+6,17 %)
```

⇒ **le volume n'explique qu'un sixième de la hausse** : le coût unitaire monte
aussi.

**Marge à 35,1 % du garde — le plus bas de la série** (35,5 % le 07/10 était le
précédent record). ⛔ **Remontée du chien de garde : NON LANCÉE, et même pas
proposée ce matin.** `controle_quotidien.proposition()` ne se déclenche pas (sa
pente est négative), et une nuit en hausse après une baisse ne fait pas une
pente. Si la hausse se répète, la forme de la proposition est connue : écrire
la mesure dans l'en-tête de `10-timeout-s3.conf` (135 → 140/145 min), déployer,
vérifier par `systemctl show`. **C'est Yann qui décide et qui lance.**

## 6. Les trois correctifs du 07/10 — verdict correctif par correctif

| correctif | verdict du 20/10 |
|---|---|
| **1. webhook `--ipv4`** | ✅ **tient.** `ⓘ push parti (webhook, HTTP 200)` à 07:23:29. Aucun 429 ntfy depuis le déploiement. ⓘ Les `429 (quota)` visibles au journal à 08:40 et 12:40 sont ceux de l'**API Météo-France** (`run-ingest-pi`), sans rapport. |
| **2. garde-fou des deux jetons** | ✅ **tient.** Le contrôle de 07:31 s'est tu : pas de jeton posé, pas de doublon possible. `controle_quotidien.sh` conserve son `$ETAT` — **non touché**. |
| **3. rejeu de purge ≠ échec** | ✅ **tient, non sollicité.** Aucun avertissement de tranche cette nuit : `bilan_purge()` n'avait rien à rattraper. |

## 7. Position — 4 balises confirmées, liste INCHANGÉE, pas de cri

```
⛔ position : 10 balise(s) divergent du gel (10 j lus), dont 4 CONFIRMÉE(S) (≥ 10 j)
   ⛔ pioupiou:2171          38 915 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE · Windbird 2171
   ⛔ pioupiou:1378          18 508 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE · Col de la Merquiere
   ⛔ pioupiou:367            6 764 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE · Le relais
   ⛔ infoclimat:STATIC0491   1 159 m · 10 j · nœud 0,01 CHANGE ·          infoclimat STATIC0491
```

**Identique au 19/10, balise par balise et mètre par mètre.** Le cri est **à
front, pas à état** : rien de neuf ⇒ pas de cri, comportement attendu.
ⓘ La question du 01/10 reste ouverte : **faut-il qu'il recrie** à état constant ?
**Geste attendu de Yann** : trancher chaque cas, puis poser `position_suspecte`
+ `position_note` sur `station_zone` par `.sql`.

## 8. Les autres témoins

- **Témoins du mélange — signaux contradictoires, aucune pente.** 20/10 : sur
  7 523 balise-jours×échéance, **4,051 km/h** contre 4,0399 pour le meilleur
  membre a priori ⇒ **gain −0,3 %**, mais mélange devant dans **52,0 %** des cas
  (le plus haut de la série) ; contre la moyenne **uniforme** (n = 1 120) :
  3,8007 vs 3,8874 ⇒ **gain +2,2 %**. Série du gain a priori : −0,6 % (07/10)
  · +2,5 % (18/10) · +1,7 % (19/10) · **−0,3 % (20/10)**. Le « devant » monte
  pendant que le gain baisse : **ça oscille, ça ne dérive pas**. ⇒ **pas de
  motif Jira à demander.**
- ⚠️ **Témoin du corrigé — les deux parts chutent nettement** : part imputable
  au site **18,0 pt** (22,9 le 19/10, 24,1 le 18/10) ; version FIN, part
  secteur+heure **8,5 pt** (12,7 puis 14,3). Deux baisses consécutives et de
  belle taille, hors de la bande observée jusqu'ici. **À surveiller, pas à
  conclure** — et à vérifier au prochain run plutôt qu'à reprendre tel quel.
- **Écarts du recalcul indépendant** : **5** (6 le 19/10), tous de la même
  signature (`ici None, base X : 0–1 h appariées ici (< 6) mais la base porte
  une ligne`). Récurrent, antérieur, non aggravé.
- **Événements** : 3 444 balises zonées, 1 425 cases fines, aucun événement
  retenu faute de confirmation réseau — inchangé.
- **Duels** : `arome_r2 ↔ meteofrance_arome_france_hd (+6 h)`, n = 17 087,
  médiane +0,102, IC95 [+0,090 ; +0,118] → `b_better`, inchangé. Cumul toujours
  **tronqué par la rétention 30 j** (dette connue, `duel.DUEL_DAYS`).
- **Second canal du téléphone (Discord)** : ⛔ **`BW_DISCORD_WEBHOOK_URL`
  toujours ABSENTE** du `.env` (liste des noms relevée, aucune valeur lue).
  Aucun `ⓘ push Discord parti` au journal — cohérent.
  `~/installer-webhook-discord.sh` attend toujours que Yann le lance : **39ᵉ
  jour**.
- **`mutations_memoire`** : 3 mutations non vues (2, 5, 13), dette antérieure,
  inchangée.

## 9. Les tickets — ce qui a été fait

**États revérifiés par GET avant toute écriture :**

```
KAN-3 | Terminé | done | updated 2026-10-17T11:10:12+0200 | bw-pente-duree
KAN-4 | À faire | new  | updated 2026-10-19T17:59:42+0200 | bw-pente-memoire
KAN-5 | À faire | new  | updated 2026-10-19T18:00:02+0200 | bw-purge-57014
```

⇒ aucune écriture d'un tiers depuis le run du 19/10. Pas de collision.

| ticket | décision du 20/10 |
|---|---|
| **KAN-3** | ✅ **commenté** (canal délibéré). La durée **AUGMENTE** (+153 s) : la consigne demande de commenter dans ce cas. Chiffres, répartition par étape, découplage temps/volume, rappel du 25ᵉ centile, forme de la proposition de remontée du garde **sans la lancer**. **Non rouvert, non transité** — il reste « Terminé ». |
| **KAN-4** | ✅ **commenté**, **reste ouvert**. Les trois conditions de fermeture : contrôle muet ✔, plafond retombé ✘ (+393 Mo au-dessus du seuil), swap au pic ≈ 0 ✘ (2 151,5 Mo, et les pages sorties en record). |
| **KAN-5** | ✅ **commenté**, **reste ouvert**. Compteur **13 / 3**, mais le `.sql` « base sous tension » n'est toujours pas joué (**22ᵉ jour**) et la fermeture demande l'accord de Yann. |
| `bw-r2-palier` | ⛔ **non créé.** Décision de Yann (§2.4). |

**Canal : `bw_jira_commenter <CLÉ>`** (délibéré) pour les trois, et c'est un
choix assumé : le contenu est de l'analyse sur plusieurs nuits avec correction
explicite de la note de la veille, et `commenter` prend une **clé**, ne cherche
rien, ne crée rien — donc **aucun risque de créer un ticket neuf** sur un motif
dont le contrôle a déjà parlé, ni sur un ticket « Terminé ».

### ⚠️ Incident d'écriture, corrigé dans la minute

Les trois premiers commentaires sont partis depuis un script `bash -s` où les
corps étaient entre **guillemets doubles** : le shell a interprété les **accents
graves** comme des substitutions de commande et a **avalé six noms**
(`regime` ×2, `bw-regime-sensibilite`, `controle_quotidien.proposition()`,
`units`, le chemin du `.sql`). **Aucun chiffre et aucune conclusion n'ont été
altérés** — vérifié en relisant le commentaire posté sur KAN-3 par GET.
**Trois errata** ont été postés aussitôt, un par ticket, qui rétablissent les
noms manquants. *Leçon : corps de commentaire en guillemets **simples**, ou
passés par fichier.*

## 10. Horaire de la routine — +3 h 41

Programmée pour **07:09:05 UTC**, tirée à **10:49:46 UTC**.

```
15/10 +7 h 37 · 16/10 +4 h 03 · 17/10 +1 h 56 · 18/10 +1 h 39
19/10 +7 h 43 · 20/10 **+3 h 41**
```

Mieux que le record négatif de la veille, toujours loin de l'heure. ⓘ Le VPS,
lui, est **à l'heure** : notation à 05:55:36, contrôle à 07:31:01, timer suivant
armé pour le 21/10 à 07:30:22. **Le trou est côté planification.**

## 11. Décisions en attente de Yann — la liste à jour

1. ⛔ **R2 : rétention sur `agrume/pi`** (+48 objets et +20,5 Mo chaque nuit,
   sept nuits d'affilée). ⚠️ **Remplace la décision « rétention d'`agrume/grille` »**
   des notes des 16 et 19/10, qui visait le mauvais préfixe. **Le plus urgent :
   il court et il s'accélère.**
2. ⛔ **Inventaire des 3 382 objets de `agrume/pi` que l'index ne réclame pas**
   (sur 3 429). Profil « orphelins », jamais vérifié pour ce préfixe.
3. ⛔ **Pente d'`audit_r2.py`** : ne pas additionner les pentes négatives des
   préfixes à fenêtre glissante (§2.3). Écriture ⇒ non faite.
4. ⛔ **Motif `bw-r2-palier`** — non créé, ton accord requis.
5. ⛔ **`diagnostic_base_sous_tension_2026-09-29.sql`** — toujours pas joué,
   **22ᵉ jour**. Porte de sortie de KAN-5.
6. ⛔ **Les 4 cas de position** (§7) : trancher, puis `position_suspecte` +
   `position_note` par `.sql`.
7. ⛔ **Mémoire : la ligne en tuple** (≈ −1 030 o/ligne). Rien de déployé depuis
   `af25efb` (21/09). Porte de sortie de KAN-4.
8. ⚠️ **`installer-webhook-discord.sh`** — **39ᵉ jour**, variable toujours
   absente.
9. ⚠️ **Jalons de temps dans le bloc hors étapes** de `run.sh` — **moins urgent
   encore** : ce bloc n'a bougé que de +4 s cette nuit.
10. ⓘ **Le cri de position doit-il recrier** à état constant ? (ouvert depuis le
    01/10)

## 12. Respect des règles

✅ **VPS en lecture seule.** Aucun `systemctl` start/restart/daemon-reload,
aucun `enable`, aucun SQL joué, aucun rsync, rien écrit dans `~/balise-watch`
ni dans `/etc`. Seules écritures : les six commentaires Jira (trois + trois
errata).
✅ **Aucun secret lu par valeur** : le `.env` a été **sourcé** pour Jira ; la
liste de ses variables a été relevée **sans les valeurs** (`sed "s/=.*//"`).
✅ `10-timeout-s3.conf` **non touché**, remontée du garde non lancée.
✅ Aucun ticket créé, fermé, rouvert ni transité. `bw-r2-palier` non créé.
✅ Aucun `git push`. Commit local depuis la **racine** du dépôt serveur.
