# Verdict de pente du 21/10/2026 — ⛔ **Mémoire : jalon RECORD à 3 424 Mo. Et la baisse annoncée hier était un point isolé.**

La nuit est saine par ailleurs : durée en baisse, purge propre pour la 14ᵉ fois,
une balise de position rentrée dans l'ordre. Trois commentaires Jira posés,
aucun ticket fermé, rouvert ni créé.

## 18:00 (Paris) — routine Balise Watch, run complet

**Étape 0 : faite en entier.**

- `git log --oneline --since=midnight` dans `balise-watch-server` **et** dans
  `surveillance balise` : **aucun commit aujourd'hui** dans les deux dépôts
  ⇒ aucun autre run n'a tourné ce matin.
- `claude/verdict-pente-21-10.md` **absent** du projet (vérifié par
  `project_read`, qui répond « No doc at… ») ⇒ cette note est une **création**,
  pas une fusion.
- `claude/verdict-pente-20-10.md` lu en entier : run complet à 12:55, R2 à
  10,145 Go, coupable identifié `agrume/pi`, trois commentaires + trois errata.
- `notes-projet/README.md` relu : les quatre règles.

## 1. Le relevé de la nuit du 20→21/10 — la nuit a bien tourné

`lancement = timer` · `result = success` · `exec_status = 0` · `oom = 0`
Début 05:59:08, fin 07:24:33 (Paris). 775 518 lignes écrites en base.

| | 19/10 | 20/10 | 21/10 | Δ nuit |
|---|---:|---:|---:|---:|
| `duree_s` | 5 103 | 5 256 | **5 113** | **−143** |
| `cpu_s` | 4 031,5 | 4 171,4 | **3 973,1** | **−198,3** |
| `marge_s` | 2 997 | 2 844 | **2 987** | +143 |
| marge / garde (8 100 s) | 37,0 % | 35,1 % | **36,9 %** | remonte |
| `jalon_max_mo` | 3 381 | 3 193 | **3 424** | ⛔ **+231, RECORD** |
| `mem_peak_mo` | 3 607,3 | 3 591,7 | **3 626,8** | +35,1 (record) |
| `swap_peak_mo` | 2 190,5 | 2 151,5 | **2 183,0** | +31,5 |
| `swap_out_pages` | 2 151 461 | 2 756 422 | **2 115 062** | **−641 360** |
| `n_57014` | 0 | 0 | **0** | = |
| `lignes_regime` | 130 654 | 132 406 | **133 252** | +846 |
| `lignes_score_zone` | 141 051 | 142 819 | **143 625** | +806 |
| `lignes_daily` | 69 018 | 69 136 | **66 746** | −2 390 |
| `balise_jours_rejeu` | 2 082 945 | 2 082 153 | **2 080 071** | −2 082 |

### Les deux rapports qui valent mieux que les valeurs brutes

**Coût par ligne rejouée** (`jalon_max_mo × 1048576 / balise_jours_rejeu`) :

```
16/10 1 701,2 o · 17/10 1 701,4 o · 18/10 1 706,1 o
19/10 1 702,0 o · 20/10 1 608,0 o · 21/10 1 726,1 o
```

⛔ **La note du 20/10 est démentie sur ce point.** Elle annonçait « la première
sortie PAR LE BAS de la bande 1 686–1 717 o » et « le premier mouvement de fond
apparent », en prenant soin d'ajouter qu'une nuit ne fait pas une pente. Elle
avait raison de se méfier : **le point suivant sort par le HAUT**, à 1 726,1 o,
nouveau plus-haut de la série.

Ce qui a changé en dix nuits n'est donc **pas le niveau mais l'AMPLITUDE** :
118 o d'écart en deux nuits, contre 31 o d'amplitude totale sur les neuf
précédentes. **Aucune pente, dans aucun sens** — et la bande de 07/10 n'est plus
une bande, c'est le centre d'une oscillation qui s'élargit.

**Coût par ligne de `regime`** (`etapes_s.regime / lignes_regime × 1000`) :

```
16/10 12,57 ms · 17/10 13,12 ms · 18/10 13,04 ms
19/10 12,37 ms · 20/10 13,13 ms · 21/10 12,14 ms
```

⇒ **le critère `bw-regime-sensibilite` est à 0 / 2** : le coût **baisse**, et de
7,53 %. Pas deux hausses consécutives, donc pas de motif, et **aucune question
reposée à Yann** sur ce point.

**Calcul ou attente ?** `cpu_s` fait **−198,3 s** pendant que la durée fait
−143 s. Le CPU baisse **plus** que la durée : c'est du **calcul rendu**, pas de
l'attente gagnée.

## 2. ⛔ Mémoire — le jalon fait un record, mais un palier passe sous le seuil

```
rejeu d'archive         3 000 → 2 998 Mo   (−2)     ⛔ au-dessus du seuil
score par régime        2 816 → 2 783 Mo   (−33)    ✅ SOUS le seuil
oubli fenêtre rejouée   3 193 → 3 424 Mo   (+231)   ⛔ RECORD
```

**Deux `incidents` cette nuit au lieu de trois** : le *score par régime* repasse
sous les 2 800 Mo **pour la première fois de la série récente**. C'est le seul
mouvement de fond lisible côté mémoire.

Le **jalon max** à **3 424 Mo** bat le record du 07/10 (3 420 Mo) et siège
**+624 Mo au-dessus du seuil** — le plus haut écart de la série. Le **pic
processus** (3 626,8 Mo) est un record aussi.

⚠️ **Et `swap_out_pages` démentit la veille à son tour** : hier, 2 756 422 pages
sorties, « un record sur la fenêtre », avec cette conclusion : *« c'est le second
qui se dégrade, et il faut le suivre »*. Ce matin : **2 115 062, soit −641 360**,
sous le niveau du 19/10. **Le record n'a pas tenu une nuit.** Il oscille, il ne
dérive pas. ⓘ La distinction pic / pages sorties reste juste et utile ; c'est la
**conclusion de tendance** qui était prématurée, pas la mesure.

**Contrôle de pente du 21/10 à 07:30:36 — MUET :**

```
ⓘ 83 relevé(s), 62 comparable(s) ; durée : 10 points, pente -69 s/nuit ;
  mémoire : 10 points, pente -22 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate/négative, ou échéance hors horizon
```

⚠️ **Le contrôle annonce −22 Mo/nuit le matin même d'un record à +231 Mo.** C'est
le 25ᵉ centile des différences qui fait son travail : par construction il ignore
les deux plus grosses hausses. **Calcul à taux constant** : à −22 Mo/nuit depuis
3 424 Mo, le retour sous 2 800 tomberait dans **28 nuits, vers le 18/11** —
chiffre donné **pour ce qu'il vaut**, c'est-à-dire l'extrapolation d'une pente
que les points ne montrent pas (3 381 → 3 193 → 3 424 en deux nuits).

Le seul remède chiffré reste la **ligne en tuple** (§2.6 de l'enquête du 10/09) :
≈ −1 030 o/ligne, soit ≈ **−2 045 Mo** sur les 2 080 071 balise-jours rejoués de
cette nuit. **Rien de déployé côté mémoire depuis `af25efb` (21/09) — 30ᵉ jour.**

## 3. Durée — en baisse, et toute la baisse est dans les étapes

```
            étapes     hors étapes   total
20/10      3 153,4       2 102,6     5 256
21/10      2 964,1       2 148,9     5 113
Δ            −189,3         +46,3     −143
```

`regime` −120,4 · `glissant` −45,8 · `stabilite` −14,4 · `rejeu` −8,7.

La baisse est **entièrement dans les étapes**, et le bloc **hors étapes monte de
+46,3 s en sens inverse**. Ce bloc (publication, Murphy, événements, pression,
duels, purge) **n'est pas instrumenté** : on ne sait pas lequel des six postes
bouge. Il a fait +4 s puis +46 s : **il ne dérive pas**, la demande de jalons de
temps dans `run.sh` reste ouverte sans urgence.

**Découplage temps / volume sur `regime`** :

```
lignes_regime  132 406 → 133 252   (+846, +0,64 %)
temps regime   1 738,2 → 1 617,8 s       (−6,93 %)
coût par ligne    13,13 → 12,14 ms       (−7,53 %)
```

⇒ le volume **monte** pendant que le temps **baisse** : le coût unitaire baisse
de lui-même.

**Marge à 36,9 % du garde**, remontée de 1,8 pt. ⛔ **Remontée du chien de garde :
NON LANCÉE et NON PROPOSÉE.** `controle_quotidien.proposition()` ne se déclenche
pas (pente négative). Si la hausse revient, la forme est connue : écrire la
mesure dans l'en-tête de `10-timeout-s3.conf` (135 → 140/145 min), déployer,
vérifier par `systemctl show`. **C'est Yann qui décide et qui lance.**

⛔ **Correction de la note du 20/10 (§5) et du point ouvert du 07/10** : « la
durée monte deux nuits de suite » n'était pas une pente. La série 5 103 → 5 256 →
5 113 oscille d'environ ±150 s autour de 5 150 s, et le plancher de marge de
35,1 % n'a pas tenu une nuit.

## 4. Purge `model_score_zone` — nuit propre, 14ᵉ d'affilée

```
→ purge model_score_zone : 138 389 ligne(s) effacée(s) en 8 tranche(s)
ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée.
```

- **Aucun 57014** : ni au registre (`n_57014 = 0`), ni dans le bloc purge, ni
  ailleurs dans le journal de la nuit (recherche élargie sur 24 h).
- **Aucun avertissement de tranche**, donc aucun rejeu à interpréter.
- **Aucune sonde en défaut** (pas de « plus vieille journée illisible »).
- **Aucun « des lignes RESTENT »** ⇒ rien ne reste en base.
- Nombre de lignes **lisible** et 8 tranches ⇒ **la purge a abouti**.
- Volume effacé 138 389 (138 363 le 20/10) : il suit la journée purgée, **il ne
  signifie rien**.

**Compteur de fermeture KAN-5 : 14 / 3.**

## 5. ⛔ R2 — `agrume/pi` confirmé, 8ᵉ nuit de +48 objets, et le palier s'enfonce

```
21/10   10,228 Go   (102,3 %)   ⛔ DÉPASSÉ de 228 Mo   6 733 objets
20/10   10,145 Go   (101,5 %)   ⛔ DÉPASSÉ de 145 Mo   6 668 objets
```

**+83 Mo et +65 objets en une nuit.** Série des dépassements : +22 Mo (17→18),
+74 (18→19), +107 (19→20), **+83 (20→21)**.

### 5.1 ✅ La correction du 20/10 tient : le coupable est bien `agrume/pi`

```
            agrume/grille                     agrume/pi
19/10   5,323 Go   766 obj          1,506 Go   3 381 obj   (+48)
20/10   5,323 Go   766 obj          1,527 Go   3 429 obj   (+48)
21/10   5,344 Go   769 obj          1,546 Go   3 477 obj   (+48)
```

**Huitième nuit consécutive à +48 objets exactement, sans un seul recul**, et
+19 Mo. Pente affichée **+0,578 Go/mois**, juste. ⓘ `agrume/grille` bouge d'un
cheveu cette nuit (+21 Mo, +3 objets) après quatre nuits strictement plates —
c'est son oscillation habituelle, pas une accumulation : sa pente reste
**−0,004 Go/mois** et **l'index le réclame intégralement (769 / 769)**.

### 5.2 ⛔ Et l'écart non réclamé grossit exactement au rythme de l'accumulation

```
│ agrume/pi/grille/                        19 présentes /   19 réclamées   ✓
│ agrume/pi/rafraichissement/              28 présentes /   28 réclamées   ✓
```

47 objets couverts sur **3 477** ⇒ **3 430 objets non réclamés par aucun index**
(3 382 hier). L'écart grossit de **+48 par nuit**, soit *exactement* le rythme
d'accumulation : **tout ce que `agrume/pi` ajoute chaque nuit tombe hors de la
vue des index.** ⓘ Ce n'est pas la preuve qu'ils sont orphelins ; c'est la
constatation qu'on n'en sait rien, et que la question n'a jamais été posée pour
ce préfixe.

### 5.3 ✅ Le diagnostic des fenêtres glissantes (§2.3 du 20/10) tient

```
arome/rafale   63 objets fixes   0,892 → 0,906 Go   pente affichée −0,344 Go/mois
arome/sol      63 objets fixes   0,619 → 0,632 Go   pente affichée −0,277 Go/mois
```

Les deux ont **encore grossi** et affichent **encore** une pente négative. La
pente totale annoncée est **+0,076 Go/mois** alors que le réel est ≈ 83 Mo/nuit,
soit ≈ **+2,5 Go/mois** : un facteur 33. Le mécanisme décrit hier — le 25ᵉ
centile des différences appliqué à une série qui oscille sans dériver rend une
valeur négative, additionnée aux positifs réels — est **confirmé par une nuit de
plus**.

### 5.4 ⓘ `bw-garde-fou-r2.service` est en état `failed` — et ce n'est PAS une panne

`systemctl list-units` montre `● bw-garde-fou-r2.service … failed`, et le journal
dit : `run garde-fou-r2 en ÉCHEC (code 1, 6s) — 6 consécutif(s)`. **Avant de
partir en enquête : le service signale par son code de sortie.**

La preuve est dans l'échec n° 1, le 16/10 :

```
│ total compte : 9.959 Go  ( 99.6 % du palier 10 Go)
⚠️  au rythme mesuré (+0.03 Go/mois), palier atteint dans 35 jours
   run garde-fou-r2 en ÉCHEC (code 1, 6s) — 1 consécutif(s)
```

À 99,6 % du palier, **sans dépassement**, il sort déjà en code 1. Les échecs des
16, 17 et 18/10 (n° 1, 2 et 3) n'ont **aucune ligne « palier DÉPASSÉ »** : leur
cause est l'échéance dans l'horizon, pas le dépassement, qui n'apparaît qu'à
partir du 19/10. **`code 1` veut dire « j'ai quelque chose à dire », pas « je
suis cassé ».**

⇒ **Rien à corriger, et rien à chercher.** Deux conséquences à connaître :
le service **restera `failed` tant que R2 dépasse**, et **deux cris partent
chaque matin pour le même fait** (l'avertissement R2 + l'alerte générique
« service en échec »). ⓘ C'est la première fois que la série des échecs est
relevée : les notes des 16 au 20/10 ne mentionnaient que les cris.

## 6. Position — ⛔ 3 confirmées (une de moins), cri parti

```
⛔ position : 10 balise(s) divergent du gel (10 j lus), dont 3 CONFIRMÉE(S)
   ⛔ pioupiou:2171          38 915 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE
   ⛔ pioupiou:367            6 764 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE
   ⛔ infoclimat:STATIC0491   1 159 m · 10 j · nœud 0,01 CHANGE
```

**`pioupiou:1378` est rentrée dans l'ordre** (18 508 m mais **9 j**) : le
référentiel et le gel se sont rejoints, ou la balise n'est plus vue. C'est un
**changement de front**, donc le cri est parti : `ALERTE — position des balises …
pour 3 balise(s)`, `ⓘ push parti (webhook, HTTP 200)` à 07:24:31.

✅ **Le comportement « à front, pas à état » est donc vérifié dans les deux
sens** : silence hier à liste constante, cri ce matin dès que la liste change.
ⓘ La question du 01/10 reste ouverte : faut-il qu'il recrie à état constant ?

Sept autres balises sont à **8 ou 9 j** (1378, 84, 2139, 1618, 1766, 1698, 1710).
**Geste attendu de Yann** : trancher chaque cas, puis poser `position_suspecte` +
`position_note` sur `station_zone` par `.sql`.

## 7. Les trois correctifs du 07/10 — verdict correctif par correctif

| correctif | verdict du 21/10 |
|---|---:|
| **1. webhook `--ipv4`** | ✅ **tient.** Deux `ⓘ push parti (webhook, HTTP 200)` : position à 07:24:31, garde-fou R2 à 07:24:40. **Aucun 429 ntfy.** Volume du jour : **2 pushes**, dans la fourchette normale de 2 à 7 — aucun runner qui s'emballe. |
| **2. garde-fou des deux jetons** | ✅ **tient.** Le contrôle de 07:30:36 s'est tu : aucun jeton posé, aucun doublon possible. `controle_quotidien.sh` conserve son `$ETAT` — **non touché**. |
| **3. rejeu de purge ≠ échec** | ✅ **tient, non sollicité.** Aucun avertissement de tranche : `bilan_purge()` n'avait rien à rattraper. |

## 8. Les autres témoins

- **Témoins du mélange — ça oscille toujours, et le gain revient positif.** Sur
  7 477 balise-jours×échéance : **4,8657 km/h** contre 4,9109 pour le meilleur
  membre a priori ⇒ **gain +0,9 %**, devant dans **50,9 %** des cas ; contre la
  moyenne **uniforme** (n = 1 103) : 4,9497 vs 5,2074 ⇒ **gain +4,9 %**. Série du
  gain a priori : −0,6 % (07/10) · +2,5 % (18/10) · +1,7 % (19/10) · −0,3 %
  (20/10) · **+0,9 % (21/10)**. ⓘ L'erreur absolue monte encore (4,87 contre 4,05
  km/h) : journée plus ventée. ⇒ **oscillation sans dérive, pas de motif Jira à
  demander** — et le passage sous la barre du 07/10 reste un accident isolé.
- ⚠️ **Témoin du corrigé — la part « site » enchaîne une 3ᵉ baisse.** Part
  imputable au site : 24,1 (18/10) → 22,9 (19/10) → 18,0 (20/10) → **16,6 pt**.
  Version FIN, part secteur+heure : 14,3 → 12,7 → 8,5 → **9,8 pt** (elle
  **rebondit**). Donc la « double baisse de belle taille » annoncée hier se
  vérifie sur la première part et **se démentit sur la seconde**. −7,5 pt en
  trois nuits sur le site, c'est net : **à surveiller, pas encore à conclure.**
- **Écarts du recalcul indépendant** : **3** (5 le 20/10, 6 le 19/10), tous de la
  même signature (`ici None, base X : 0 h appariées ici (< 6) mais la base porte
  une ligne`). Récurrent, antérieur, **en baisse**, non aggravé.
- **Duels** : `arome_r2 ↔ meteofrance_arome_france_hd (+6 h)`, n = **17 096**,
  médiane **+0,099**, IC95 [+0,083 ; +0,113] → `b_better`, inchangé. Cumul
  toujours **tronqué par la rétention 30 j** (dette connue, `duel.DUEL_DAYS`).
- **Murphy** : 65 892 triplets, 64 115 décomposés, 266 balises tenues dehors.
- **Second canal du téléphone (Discord)** : ⛔ **`BW_DISCORD_WEBHOOK_URL`
  toujours ABSENTE** du `.env` (recherche sur le **nom seul**, aucune valeur
  lue : 0 occurrence). Aucun `ⓘ push Discord parti` au journal — cohérent.
  `~/installer-webhook-discord.sh` attend toujours que Yann le lance : **40ᵉ
  jour**. ⓘ `bw-discord-bridge.service` (pont Discord → Jira) tourne, lui : c'est
  un autre objet, il ne remplace pas le canal de notification.
- **`mutations_memoire`** : ⓘ **aucune ligne au journal de `bw-model-score` cette
  nuit** — je ne l'ai pas revue, donc je ne conclus rien : la dette de 3 mutations
  non vues (2, 5, 13) est reportée telle quelle, à revérifier.
- ⓘ `bw-model-oracle.service` est également en `failed` (oracle mensuel, lot L12).
  **Non examiné** : hors mission. À regarder un autre jour.

## 9. Les tickets — ce qui a été fait

**États revérifiés par GET avant toute écriture :**

```
KAN-3 | Terminé | done | updated 2026-10-20T12:56:40+0200 | bw-pente-duree
KAN-4 | À faire | new  | updated 2026-10-20T12:56:41+0200 | bw-pente-memoire
KAN-5 | À faire | new  | updated 2026-10-20T12:56:41+0200 | bw-purge-57014
```

⇒ les trois `updated` sont ceux des errata du run du 20/10 : **aucune écriture
d'un tiers depuis**. Pas de collision.

| ticket | décision du 21/10 |
|---|---|
| **KAN-3** | ✅ **commenté** (canal délibéré). La durée **BAISSE** (−143 s), donc la consigne « commenter si elle augmente » ne s'applique pas — mais le commentaire du 20/10 annonçait une hausse de deux nuits et une marge record basse, et **c'est faux dès le lendemain**. Une correction de la veille est exactement l'usage prévu du canal délibéré. Chiffres, répartition par étape, découplage temps/volume, rappel du 25ᵉ centile, forme de la proposition de remontée du garde **sans la lancer**. **Non rouvert, non transité** — il reste « Terminé ». |
| **KAN-4** | ✅ **commenté**, **reste ouvert**. Les trois conditions de fermeture : contrôle muet ✔, plafond retombé ✘ (**+624 Mo**, le plus haut écart de la série), swap au pic ≈ 0 ✘ (2 183,0 Mo). Le commentaire porte le record, la série à six nuits du coût par ligne rejouée, **la correction explicite de la note du 20/10**, et le calcul à taux constant avec sa réserve. |
| **KAN-5** | ✅ **commenté**, **reste ouvert**. Compteur **14 / 3**, mais le `.sql` « base sous tension » n'est toujours pas joué (**23ᵉ jour**), le précédent des 03–05/10 rappelle qu'une série propre n'est pas un correctif, et la fermeture demande l'accord de Yann. |
| `bw-r2-palier` | ⛔ **non créé.** Décision de Yann. |

**Canal : `bw_jira_commenter <CLÉ>`** pour les trois, choix assumé : le contenu
est de l'analyse multi-nuits avec correction explicite de la veille, et
`commenter` prend une **clé**, ne cherche rien, ne crée rien, ne touche pas au
jeton du jour — **aucun risque de créer un ticket neuf**, y compris sur KAN-3
qui est « Terminé ».

✅ **Leçon du 20/10 appliquée** : les trois corps sont passés par des **heredocs
`<<'EOF'` non interprétés** au lieu de guillemets doubles. **Vérifié par GET sur
KAN-4** : 4 658 octets, et `units`, `regime`, `af25efb`, `1 726` tous présents.
**Aucun nom avalé, aucun erratum nécessaire.**

## 10. Horaire de la routine — ⛔ +8 h 50, nouveau record négatif

Programmée pour **07:09:05 UTC**, tirée à **15:59:09 UTC**.

```
15/10 +7 h 37 · 16/10 +4 h 03 · 17/10 +1 h 56 · 18/10 +1 h 39
19/10 +7 h 43 · 20/10 +3 h 41 · 21/10 **+8 h 50**
```

⛔ **Pire que le record du 19/10.** Sur sept matins, le retard va de 1 h 39 à
8 h 50 sans aucune régularité. ⓘ Le VPS, lui, est **à l'heure** : notation à
05:59:08, contrôle à 07:30:36, timer suivant armé pour le **22/10 à 07:30:30**.
**Le trou est côté planification**, et il s'aggrave.

ⓘ Le pont vers le Mac a aussi lâché une fois en cours de run (≈ 4 min) ; les
lectures ont été reprises à l'identique après reconnexion, sans rien manquer.

## 11. Décisions en attente de Yann — la liste à jour

1. ⛔ **R2 : rétention sur `agrume/pi`** — **+48 objets et +19 à +22 Mo chaque
   nuit, huit nuits d'affilée, sans un seul recul**. Le compte est à **102,3 %**
   du palier et R2 facture. **Le plus urgent.** (La cible est bien `agrume/pi`,
   pas `agrume/grille` : correction du 20/10 confirmée par une nuit de plus.)
2. ⛔ **Inventaire des 3 430 objets de `agrume/pi` que l'index ne réclame pas**
   (sur 3 477). L'écart grossit de +48/nuit, exactement le rythme
   d'accumulation : à faire **avant** toute rétention.
3. ⛔ **Pente d'`audit_r2.py`** : ne pas additionner les pentes négatives des
   préfixes à fenêtre glissante, ou les borner à zéro par le bas (§5.3). Une
   ligne de code, mais c'est une **écriture** : non faite.
4. ⛔ **Motif `bw-r2-palier`** — non créé, ton accord requis.
5. ⛔ **`diagnostic_base_sous_tension_2026-09-29.sql`** — toujours pas joué,
   **23ᵉ jour**. Porte de sortie de KAN-5, qui est à 14 nuits propres.
6. ⛔ **Les 3 cas de position** (§6) : trancher, puis `position_suspecte` +
   `position_note` par `.sql`. ⓘ `pioupiou:1378` est sortie de la liste des
   confirmées : un cas de moins.
7. ⛔ **Mémoire : la ligne en tuple** (≈ −1 030 o/ligne, ≈ −2 045 Mo). **30ᵉ jour
   sans rien de déployé** depuis `af25efb`. Porte de sortie de KAN-4, qui vient
   de faire un record.
8. ⚠️ **`installer-webhook-discord.sh`** — **40ᵉ jour**, variable toujours absente.
9. ⓘ **Horaire de la routine** : +8 h 50 ce matin, record négatif. Côté
   planification, pas côté VPS.
10. ⓘ **Jalons de temps dans le bloc hors étapes** de `run.sh` — toujours sans
    urgence (+4 s puis +46 s).
11. ⓘ **Le cri de position doit-il recrier** à état constant ? (ouvert depuis le
    01/10 ; le comportement « à front » est maintenant vérifié dans les deux sens)
12. ⓘ **`bw-model-oracle.service` en `failed`** — hors mission, non examiné.

## 12. Ce que ce run a DÉMENTI de la note du 20/10

C'est la cinquième fois en douze jours que « une nuit ne fait pas une pente »
ressert. Les trois points à ne pas reprendre tels quels :

| annoncé le 20/10 | relevé le 21/10 |
|---|---|
| coût par ligne rejouée : « première sortie PAR LE BAS », « premier mouvement de fond apparent » (1 608,0 o) | **1 726,1 o, sortie par le HAUT** — point isolé, l'amplitude s'élargit, aucune pente |
| `swap_out_pages` : « record sur la fenêtre, c'est le second qui se dégrade, il faut le suivre » (2 756 422) | **2 115 062, −641 360** — le record n'a pas tenu une nuit |
| durée : « la hausse est DANS les étapes », marge à 35,1 % « le plus bas de la série » | **durée −143 s, marge à 36,9 %** — oscillation ±150 s, pas une pente |

✅ Ce que le 20/10 avait **juste** et qui tient : `agrume/pi` est le coupable R2
(8ᵉ nuit à +48), `agrume/grille` est hors de cause (769/769 réclamés), et le
mécanisme des pentes négatives des fenêtres glissantes (§5.3).

## 13. Respect des règles

✅ **VPS en lecture seule.** Aucun `systemctl` start/restart/daemon-reload, aucun
`enable`, aucun SQL joué, aucun rsync, rien écrit dans `~/balise-watch` ni dans
`/etc`. Seules écritures : les trois commentaires Jira.
✅ **Aucun secret lu par valeur** : le `.env` a été **sourcé** pour Jira ;
`BW_DISCORD_WEBHOOK_URL` a été cherchée **par son nom seul** (`grep -c`).
✅ `10-timeout-s3.conf` **non touché**, remontée du garde non lancée, non proposée.
✅ Aucun ticket créé, fermé, rouvert ni transité. `bw-r2-palier` non créé.
✅ **Desktop Commander exclusivement** pour fichiers et shell.
✅ Aucun `git push`. Commit local depuis la **racine** du dépôt serveur.
