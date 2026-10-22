# Verdict de pente du 22/10/2026 — ⛔ **Le 57014 est revenu au registre, mais PAS dans la purge.** Et deux annonces de la veille sont démenties.

La nuit a tourné proprement. Le fait du jour est un piège de lecture évité :
`n_57014 = 1` après quatorze nuits à zéro, et l'occurrence n'est pas une tranche
de purge — c'est `rpc/bw_character_avance`, rattrapée sans perte. Trois
commentaires Jira posés, aucun ticket fermé, rouvert ni créé.

## 13:40 (Paris) — routine Balise Watch, run complet

**Étape 0 : faite en entier.**

- `git log --oneline --since=midnight` dans `balise-watch-server` **et** dans
  `surveillance balise` : **aucun commit aujourd'hui** dans les deux dépôts
  ⇒ aucun autre run n'a tourné ce matin.
- `claude/verdict-pente-22-10.md` **absent** du projet (`project_read` répond
  « No doc at… ») ⇒ cette note est une **création**, pas une fusion.
- `claude/verdict-pente-21-10.md` lu en entier : run à 18:00, jalon record à
  3 424 Mo, trois commentaires, trois démentis de la note du 20/10.
- `notes-projet/README.md` relu : les quatre règles.

## 1. Le relevé de la nuit du 21→22/10 — la nuit a bien tourné

`lancement = timer` · `result = success` · `exec_status = 0` · `oom = 0`
Début 05:58:58, fin 07:26:33 (Paris). 794 553 lignes écrites en base.

| | 20/10 | 21/10 | 22/10 | Δ nuit |
|---|---:|---:|---:|---:|
| `duree_s` | 5 256 | 5 113 | **5 242** | **+129** |
| `cpu_s` | 4 171,4 | 3 973,1 | **4 171,7** | **+198,6** |
| `marge_s` | 2 844 | 2 987 | **2 858** | −129 |
| marge / garde (8 100 s) | 35,1 % | 36,9 % | **35,3 %** | −1,6 pt |
| `jalon_max_mo` | 3 193 | 3 424 | **3 412** | −12 |
| `mem_peak_mo` | 3 591,7 | 3 626,8 | **3 597,7** | −29,1 |
| `swap_peak_mo` | 2 151,5 | 2 183,0 | **2 206,0** | ⛔ **+23,0, RECORD** |
| `swap_out_pages` | 2 756 422 | 2 115 062 | **2 450 545** | +335 483 |
| `n_57014` | 0 | 0 | ⛔ **1** | **+1** |
| `lignes_regime` | 132 406 | 133 252 | **136 857** | +3 605 |
| `lignes_score_zone` | 142 819 | 143 625 | **147 216** | +3 591 |
| `lignes_daily` | 69 136 | 66 746 | **66 744** | −2 |
| `balise_jours_rejeu` | 2 082 153 | 2 080 071 | **2 077 376** | −2 695 |

### Les deux rapports qui valent mieux que les valeurs brutes

**Coût par ligne rejouée** (`jalon_max_mo × 1048576 / balise_jours_rejeu`) :

```
16/10 1 701,2 o · 17/10 1 701,4 o · 18/10 1 706,1 o · 19/10 1 702,0 o
20/10 1 608,0 o · 21/10 1 726,1 o · 22/10 1 722,2 o
```

⇒ **sept nuits, aucune pente dans aucun sens.** Le point du jour est à 3,9 o de
celui de la veille. Ce qui a changé n'est pas le niveau mais l'**amplitude** :
1 608 → 1 726 → 1 722 en trois nuits, contre **5 o d'amplitude sur les quatre
premières**. La « bande 1 686–1 717 » du 07/10 n'est plus une bande, c'est le
centre d'une oscillation élargie. ✅ La note du 21/10 avait raison sur ce point,
et il tient une nuit de plus.

**Coût par ligne de `regime`** (`etapes_s.regime / lignes_regime × 1000`) :

```
19/10 12,37 ms · 20/10 13,13 ms · 21/10 12,14 ms · 22/10 12,59 ms
```

⇒ **le critère `bw-regime-sensibilite` est à 1 / 2.** Le coût **monte de 3,70 %**,
mais la veille il **baissait de 7,53 %** : il n'y a **pas deux hausses
consécutives**. Donc pas de motif, et **aucune question reposée à Yann** sur ce
point. ⓘ À revérifier demain : une seconde hausse remplirait le critère.

**Calcul ou attente ?** `cpu_s` fait **+198,6 s** pendant que la durée fait
+129 s. Le CPU monte **plus** que la durée : c'est du **calcul**, pas de
l'attente.

## 2. ⛔ Le 57014 est revenu au registre — et il ne vient PAS de la purge

C'est le point à ne pas lire de travers. `n_57014 = 1` après quatorze nuits à
zéro. L'**unique** occurrence de « 57014 » dans tout le journal de la nuit
(recherche élargie à toutes les unités sur 24 h : **1 seule**) est celle-ci :

```
06:20:58  ⚠️ rpc/bw_character_avance : HTTP 500 {"code":"57014","details":null,
          "hint":null,"message":"canceling statement due to statement timeout"}
          — reprise 1/3
06:22:17  → model_character : 492031 accumulateurs avancés sur 492031 envoyés
```

**La reprise a abouti** : 492 031 / 492 031, zéro perte, aucune reprise 2/3 ni
3/3. L'étape touchée est l'**avance des accumulateurs de `model_character`**, pas
la purge par tranches de `model_score_zone`. Même code d'erreur (le `statement
timeout` de 8 s), **autre requête, autre objet.**

⚠️ **Conséquence de lecture, à retenir** : le compteur `n_57014` du registre
compte les 57014 **partout dans la nuit**, pas seulement dans le bloc purge. Un
`n_57014 = 1` ne vaut donc **pas à lui seul** une purge en échec. C'est la leçon
du 28/09 prise **dans l'autre sens** : elle disait de ne pas conclure « il reste
des lignes » d'un 57014 isolé ; elle dit aussi de ne pas conclure « la purge a
échoué » d'un compteur de registre. Le contrôle de 07:30 s'est tu sur ce motif,
et **il a raison de se taire**.

## 3. Purge `model_score_zone` — nuit propre, 15ᵉ d'affilée

```
→ purge model_score_zone : 138 250 ligne(s) effacée(s) en 8 tranche(s)
ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée.
```

- **Aucun avertissement de tranche** : pas une ligne
  `purge model_score_zone (?as_of=eq.J&regime=eq.R) : HTTP 500 57014`.
- **Aucune sonde en défaut** (pas de « plus vieille journée illisible »).
- **Aucun « des lignes RESTENT »** ⇒ rien ne reste en base.
- Nombre de lignes **lisible** et 8 tranches ⇒ **la purge a abouti**.
- Volume effacé 138 250 (138 389 la veille) : il suit la journée purgée, **il ne
  signifie rien**.

**Compteur de fermeture KAN-5 : 15 / 3.**

## 4. ⛔ Mémoire — le jalon recule à peine, le swap au pic fait un record

```
rejeu d'archive         2 998 → 3 004 Mo   (+6)     ⛔ au-dessus du seuil
score par régime        2 783 → 2 944 Mo   (+161)   ⛔ REPASSE au-dessus
oubli fenêtre rejouée   3 424 → 3 412 Mo   (−12)    ⛔ RECORD de la veille, à peine entamé
```

**Trois `incidents` cette nuit au lieu de deux.** Le jalon max reste **+612 Mo
au-dessus du seuil**, et le **swap au pic** bat son record à **2 206,0 Mo**.

⛔ **Démenti n° 1 de la note du 21/10.** Elle annonçait que le palier « score par
régime » passait « **SOUS le seuil pour la première fois de la série récente** »
et en faisait « **le seul mouvement de fond lisible côté mémoire** ». Il est
remonté de +161 Mo en une nuit. Ce n'était pas un mouvement de fond, c'était un
point.

**Contrôle de pente du 22/10 à 07:30:31 — MUET :**

```
ⓘ 84 relevé(s), 63 comparable(s) ; durée : 10 points, pente -69 s/nuit ;
  mémoire : 10 points, pente -12 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate/négative, ou échéance hors horizon
```

**Calcul à taux constant** : à −12 Mo/nuit depuis 3 412 Mo, le retour sous 2 800
tomberait dans **51 nuits, vers le 12/12** — chiffre donné **pour ce qu'il vaut**,
c'est-à-dire l'extrapolation d'une pente que les points ne montrent pas
(3 381 → 3 193 → 3 424 → 3 412). ⓘ La pente affichée s'est elle-même aplatie de
−22 à −12 Mo/nuit : l'échéance d'hier (18/11) a reculé de trois semaines en une
nuit, ce qui dit tout de sa valeur.

Le seul remède chiffré reste la **ligne en tuple** (§2.6 de l'enquête du 10/09) :
≈ −1 030 o/ligne, soit ≈ **−2 041 Mo** sur les 2 077 376 balise-jours rejoués de
cette nuit. **Rien de déployé côté mémoire depuis `af25efb` (21/09) — 31ᵉ jour.**
⚠️ L'élagage de `units` avait rendu −124 Mo au lieu de −1 500 : les gains sont
dans la **structure**, pas dans le volume des champs.

## 5. Durée — en hausse, et toute la hausse est dans les étapes

```
            étapes     hors étapes   total
21/10      2 964,1       2 148,9     5 113
22/10      3 143,8       2 098,2     5 242
Δ            +179,3        −50,7      +129
```

`regime` **+105,3** · `glissant` +40,4 · `stabilite` +31,8 · `rejeu` +2,2.

La hausse est **entièrement dans les étapes**, et le bloc **hors étapes recule de
50,7 s**. C'est l'**image inverse exacte du 21/10** (baisse dans les étapes,
hors-étapes +46,3 s). Ce bloc (publication, Murphy, événements, pression, duels,
purge) **n'est pas instrumenté**, mais cette nuit il n'est pas en cause : la
demande de jalons de temps dans `run.sh` reste ouverte **sans urgence**.

**Découplage temps / volume sur `regime`** :

```
lignes_regime  133 252 → 136 857   (+3 605, +2,71 %)
temps regime   1 617,8 → 1 723,1 s        (+6,51 %)
coût par ligne    12,14 → 12,59 ms        (+3,70 %)
```

⇒ le temps monte **deux fois et demie plus vite** que le volume : le coût
unitaire monte de lui-même, ce n'est pas un effet de volume.

⛔ **Démenti n° 2 de la note du 21/10.** Elle concluait « la durée BAISSE » et
corrigeait le point ouvert du 07/10 en disant que la série oscille d'environ
±150 s autour de 5 150 s. **La correction tient, pas la baisse** : 5 103 → 5 256
→ 5 113 → **5 242**. L'oscillation est confirmée par un quatrième point, et c'est
précisément pourquoi la hausse de ce matin n'est **pas** une pente non plus.

**Marge à 35,3 % du garde**, en recul de 1,6 pt — mais elle **ne bat pas** le
plancher de 35,1 % du 20/10. ⛔ **Remontée du chien de garde : NON LANCÉE et NON
PROPOSÉE.** `controle_quotidien.proposition()` ne se déclenche pas (pente
négative). Si la hausse revient, la forme est connue : écrire la mesure dans
l'en-tête de `10-timeout-s3.conf` (135 → 140/145 min), déployer, vérifier par
`systemctl show`. **C'est Yann qui décide et qui lance.**

⚠️ **Rappel de construction** : la pente du contrôle est le **25ᵉ centile des
différences**. Elle ignore par construction les deux plus grosses hausses : elle
n'a vu ni le +153 s du 01/10, ni le +336 s du 06/10, ni le +70 s du 07/10, ni le
**+129 s de cette nuit**. Un « −69 s/nuit » annoncé le matin d'une hausse de
+129 s n'est pas une contradiction, c'est le quantile qui fait son travail.

## 6. ⛔ R2 — `agrume/pi` confirmé, 9ᵉ nuit de +48 objets exactement

```
22/10   10,280 Go   (102,8 %)   ⛔ DÉPASSÉ de 280 Mo   6 794 objets
21/10   10,228 Go   (102,3 %)   ⛔ DÉPASSÉ de 228 Mo   6 733 objets
```

**+52 Mo et +61 objets en une nuit.** Série des dépassements : +22 Mo (17→18),
+74 (18→19), +107 (19→20), +83 (20→21), **+52 (21→22)**.

### 6.1 ✅ Le coupable reste `agrume/pi`, et `agrume/grille` est rentré dans sa case

```
            agrume/grille                     agrume/pi
20/10   5,323 Go   766 obj          1,527 Go   3 429 obj   (+48)
21/10   5,344 Go   769 obj          1,546 Go   3 477 obj   (+48)
22/10   5,323 Go   766 obj          1,567 Go   3 525 obj   (+48)
```

**Neuvième nuit consécutive à +48 objets exactement, sans un seul recul**, et
+21 Mo. Pente affichée **+0,578 Go/mois**, juste.

✅ **Et la prudence du 21/10 est récompensée** : elle avait vu `agrume/grille`
bouger de +21 Mo et +3 objets et avait écrit « c'est son oscillation habituelle,
pas une accumulation ». Il est **exactement revenu à 5,323 Go et 766 objets**.
L'index le réclame intégralement (**766 / 766**). Hors de cause, confirmé.

### 6.2 ⛔ L'écart non réclamé grossit toujours au rythme exact de l'accumulation

```
│ agrume/pi/grille/                        19 présentes /   19 réclamées   ✓
│ agrume/pi/rafraichissement/              28 présentes /   28 réclamées   ✓
```

47 objets couverts sur **3 525** ⇒ **3 478 objets non réclamés par aucun index**
(3 430 hier). L'écart grossit de **+48 par nuit**, soit *exactement* le rythme
d'accumulation : **tout ce que `agrume/pi` ajoute chaque nuit tombe hors de la vue
des index.** ⓘ Ce n'est pas la preuve qu'ils sont orphelins ; c'est la
constatation qu'on n'en sait rien, et que la question n'a jamais été posée pour ce
préfixe.

### 6.3 ✅ Le diagnostic des fenêtres glissantes tient pour la troisième nuit

```
arome/rafale   63 objets fixes   0,906 → 0,915 Go   pente affichée −0,332 Go/mois
arome/sol      63 objets fixes   0,632 → 0,637 Go   pente affichée −0,276 Go/mois
```

Les deux ont **encore grossi** et affichent **encore** une pente négative. La
pente totale annoncée est **+0,094 Go/mois** alors que le réel est ≈ 52 Mo/nuit,
soit ≈ **+1,6 Go/mois** : un facteur 17. Le mécanisme — le 25ᵉ centile des
différences appliqué à une série qui oscille sans dériver rend une valeur
négative, additionnée aux positifs réels — est **confirmé une nuit de plus**.

### 6.4 ⓘ `bw-garde-fou-r2.service` est `failed` pour la 7ᵉ fois — toujours PAS une panne

```
⚠️  palier gratuit DÉPASSÉ : 10.28 Go sur 10 Go — R2 facture déjà
   run garde-fou-r2 en ÉCHEC (code 1, 6s) — 7 consécutif(s)
```

La démonstration du 21/10 (§5.4) tient : `code 1` veut dire « j'ai quelque chose à
dire », pas « je suis cassé ». ⇒ **rien à corriger, rien à chercher.** Le service
restera `failed` tant que R2 dépasse, et **deux cris partent pour le même fait**
(l'avertissement R2 + l'alerte générique « service en échec »).

## 7. Position — 3 confirmées, liste INCHANGÉE, donc pas de cri

```
⛔ position : 16 balise(s) divergent du gel (10 j lus), dont 3 CONFIRMÉE(S)
   ⛔ pioupiou:2171          38 915 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE
   ⛔ pioupiou:367            6 764 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE
   ⛔ infoclimat:STATIC0491   1 159 m · 10 j · nœud 0,01 CHANGE
```

**Exactement les trois mêmes qu'hier.** Liste constante ⇒ **aucun cri de
position** cette nuit, et c'est le comportement attendu : il est **à front, pas à
état**. ✅ Troisième vérification du mécanisme en trois jours (silence le 20/10 à
liste constante, cri le 21/10 au changement, silence le 22/10 à liste constante).
ⓘ La question du 01/10 reste ouverte : faut-il qu'il recrie à état constant ?

⚠️ **À regarder : `pioupiou:1378` a fait un bond de 18 508 m à 340 941 m**, et
reste à **9 j** — elle n'est donc pas encore confirmée, mais 341 km n'est plus un
décalage de coordonnées plausible. Candidate nette « AUTRE balise ».
`pioupiou:84` est à 9 748 m et 9 j : elle sera confirmée demain si elle tient.

⛔ **Le total des divergentes passe de 10 à 16** : six balises neuves à **1 j**
(327, 1749, 1568, 1558, 70, 1724, 1715, 1435, 175, 2058, 633). ⓘ Un paquet de
nouvelles à 1 j ne veut rien dire encore — c'est la fenêtre qui se remplit.

**Geste attendu de Yann** : trancher chaque cas, puis poser `position_suspecte` +
`position_note` sur `station_zone` par `.sql`.

## 8. Les trois correctifs du 07/10 — verdict correctif par correctif

| correctif | verdict du 22/10 |
|---|---:|
| **1. webhook `--ipv4`** | ✅ **tient.** Un `ⓘ push parti (webhook, HTTP 200)` à 07:26:39 (garde-fou R2), suivi d'un mail `smtpstatus=250`. **Aucun HTTP 429 ntfy** (recherche dédiée : 0). Volume du jour : **1 push**, dans la fourchette normale de 2 à 7 — aucun runner qui s'emballe. |
| **2. garde-fou des deux jetons** | ✅ **tient.** Le contrôle de 07:30:31 s'est tu : aucun jeton posé, aucun doublon possible. `controle_quotidien.sh` conserve son `$ETAT` — **non touché**. |
| **3. rejeu de purge ≠ échec** | ✅ **tient, et cette nuit il a servi en creux** : aucun avertissement de tranche, donc `bilan_purge()` n'avait rien à rattraper — et il s'est tu malgré `n_57014 = 1`, ce qui est exactement la bonne lecture (§2). |

⚠️ **Les 429 du journal ne sont pas les nôtres.** Dix-neuf chaînes « 429 »
apparaissent aujourd'hui, mais **zéro HTTP 429 ntfy**. Elles viennent toutes de
`run-ingest-pi.sh` et `run-ingest-pi-rafale.sh` (quota de l'API AROME-PI, série
`aromepi/0025` : 307 à 310 requêtes, 1 à 4 × 429, 8 à 11 attentes de quota), avec
reprise automatique qui aboutit — plus une qui est le `r² +0.429` d'un témoin.
**Comportement normal et géré, hors mission.**

## 9. Les autres témoins

- ⛔ **Démenti n° 3 : le témoin du corrigé REBONDIT.** Part imputable au site :
  24,1 (18/10) → 22,9 → 18,0 → 16,6 → **23,3 pt**. Version FIN, part secteur+heure :
  14,3 → 12,7 → 8,5 → 9,8 → **10,5 pt**. La note du 21/10 annonçait « une 3ᵉ baisse »
  et « −7,5 pt en trois nuits sur le site, c'est net : à surveiller ». **La baisse
  est effacée d'un coup** (+6,7 pt). Rien à surveiller : ça oscille.
- **Témoins du mélange — ça oscille toujours, et le gain repasse négatif.** Sur
  7 472 balise-jours×échéance : **5,731 km/h** contre 5,68 pour le meilleur membre
  a priori ⇒ **gain −0,9 %**, devant dans **48,6 %** des cas ; contre la moyenne
  **uniforme** (n = 1 093) : 5,8292 vs 6,0421 ⇒ **gain +3,5 %**. Série du gain a
  priori : −0,6 % (07/10) · +2,5 % (18/10) · +1,7 % (19/10) · −0,3 % (20/10) ·
  +0,9 % (21/10) · **−0,9 % (22/10)**. ⓘ L'erreur absolue monte encore (5,73 contre
  4,87 km/h) : journée encore plus ventée. ⇒ **oscillation sans dérive, pas de
  motif Jira à demander.**
- **Écarts du recalcul indépendant** : **4** (3 le 21/10, 5 le 20/10), tous de la
  même signature (`ici None, base X : 0 h appariées ici (< 6) mais la base porte
  une ligne`). Récurrent, antérieur, non aggravé.
- **Duels** : `arome_r2 ↔ meteofrance_arome_france_hd (+6 h)`, n = **17 101**,
  médiane **+0,102**, IC95 [+0,083 ; +0,119] → `b_better`, inchangé. Cumul
  toujours **tronqué par la rétention 30 j** (dette connue, `duel.DUEL_DAYS`).
- **Murphy** : 65 766 triplets, 64 102 décomposés, 266 balises tenues dehors.
- **Second canal du téléphone (Discord)** : ⛔ **`BW_DISCORD_WEBHOOK_URL`
  toujours ABSENTE** du `.env` (recherche sur le **nom seul**, aucune valeur lue :
  0 occurrence). Aucun `ⓘ push Discord parti` au journal — cohérent.
  `~/installer-webhook-discord.sh` attend toujours que Yann le lance : **41ᵉ jour**.
- **`mutations_memoire`** : ⓘ **aucune ligne au journal cette nuit non plus** — je
  ne conclus rien : la dette de 3 mutations non vues (2, 5, 13) est reportée telle
  quelle, à revérifier.
- ⓘ `bw-model-oracle.service` toujours en `failed` (oracle mensuel, lot L12).
  **Non examiné** : hors mission.

## 10. Les tickets — ce qui a été fait

**États revérifiés par GET avant toute écriture :**

```
KAN-3 | Terminé | done | updated 2026-10-21T18:12:59+0200 | bw-pente-duree  | 28 comm.
KAN-4 | À faire | new  | updated 2026-10-21T18:12:59+0200 | bw-pente-memoire| 41 comm.
KAN-5 | À faire | new  | updated 2026-10-21T18:13:00+0200 | bw-purge-57014  | 24 comm.
```

⇒ les trois `updated` sont ceux du run du 21/10 : **aucune écriture d'un tiers
depuis**. Pas de collision.

| ticket | décision du 22/10 |
|---|---|
| **KAN-3** | ✅ **commenté** (canal délibéré). La durée **AUGMENTE** (+129 s) : la consigne s'applique. Chiffres, répartition par étape (toute la hausse **dans** les étapes, hors-étapes en recul), découplage temps/volume sur `regime`, critère de sensibilité à **1/2**, rappel du 25ᵉ centile, et la forme de la proposition de remontée du garde **sans la lancer**. **Non rouvert, non transité** — il reste « Terminé ». |
| **KAN-4** | ✅ **commenté**, **reste ouvert**. Les trois conditions de fermeture : contrôle muet ✔, plafond retombé ✘ (**+612 Mo**), swap au pic ≈ 0 ✘ (**2 206,0 Mo, record**). Le commentaire porte les trois incidents, la série à sept nuits du coût par ligne rejouée, **la correction explicite du palier « score par régime »** annoncé sous le seuil la veille, et le calcul à taux constant avec sa réserve. |
| **KAN-5** | ✅ **commenté**, **reste ouvert**. Compteur **15 / 3**, et surtout **l'explication du `n_57014 = 1`** : `rpc/bw_character_avance`, rattrapé 492 031/492 031, pas une tranche de purge. Le `.sql` « base sous tension » n'est toujours pas joué (**24ᵉ jour**), et la fermeture demande l'accord de Yann. |
| `bw-r2-palier` | ⛔ **non créé.** Décision de Yann. |
| 57014 de `bw_character_avance` | ⛔ **aucun motif créé.** Une occurrence rattrapée sans perte ne justifie pas un ticket ; la question est posée dans le commentaire de KAN-5, à l'arbitrage de Yann. |

**Canal : `bw_jira_commenter <CLÉ>`** pour les trois, choix assumé : le contenu
est de l'analyse multi-nuits avec correction explicite de la veille, et
`commenter` prend une **clé**, ne cherche rien, ne crée rien, ne touche pas au
jeton du jour — **aucun risque de créer un ticket neuf**, y compris sur KAN-3 qui
est « Terminé ».

✅ **Corps passés par des heredocs `<<'EOF'` non interprétés**, pipés par
`ssh … bash -s` depuis un script écrit sur le Mac : **rien n'a été écrit sur le
VPS**. **Vérifié par GET sur les trois** : 3 391 / 3 288 / 2 974 octets, et
`regime`, `af25efb`, `tuple`, `swap_peak_mo`, `bw_character_avance`,
`model_score_zone`, `n_57014`, `492 031`, `1 722,2`, `3 412`, `5 242`,
`10-timeout-s3.conf` tous présents. **Aucun nom avalé, aucun erratum nécessaire.**

⚠️ **Piège de signature rencontré et corrigé** : `bw_jira_http` prend **quatre**
positionnels (`méthode chemin corps sortie`). Appelé avec trois, il écrit la
sortie dans une variable vide et rend **HTTP 000** — ce qui ressemble à une panne
de réseau alors que le canal va bien. Noté ici pour la prochaine session.

## 11. Horaire de la routine — +4 h 23

Programmée pour **07:09:05 UTC**, tirée à **11:32:17 UTC**.

```
15/10 +7 h 37 · 16/10 +4 h 03 · 17/10 +1 h 56 · 18/10 +1 h 39
19/10 +7 h 43 · 20/10 +3 h 41 · 21/10 +8 h 50 · 22/10 **+4 h 23**
```

Le retard recule de 4 h 27 par rapport au record d'hier, mais sur huit matins il
va de 1 h 39 à 8 h 50 **sans aucune régularité**. ⓘ Le VPS, lui, est **à
l'heure** : notation à 05:58:58, contrôle à 07:30:31, timer suivant armé pour le
**23/10 à 07:30:43**. **Le trou est côté planification.**

## 12. Décisions en attente de Yann — la liste à jour

1. ⛔ **R2 : rétention sur `agrume/pi`** — **+48 objets chaque nuit, neuf nuits
   d'affilée, sans un seul recul**. Le compte est à **102,8 %** du palier et R2
   facture. **Le plus urgent.**
2. ⛔ **Inventaire des 3 478 objets de `agrume/pi` que l'index ne réclame pas**
   (sur 3 525). L'écart grossit de +48/nuit, exactement le rythme d'accumulation :
   à faire **avant** toute rétention.
3. ⛔ **Pente d'`audit_r2.py`** : ne pas additionner les pentes négatives des
   préfixes à fenêtre glissante, ou les borner à zéro par le bas (§6.3). Une ligne
   de code, mais c'est une **écriture** : non faite.
4. ⛔ **Motif `bw-r2-palier`** — non créé, ton accord requis.
5. ⛔ **`diagnostic_base_sous_tension_2026-09-29.sql`** — toujours pas joué,
   **24ᵉ jour**. Porte de sortie de KAN-5, qui est à 15 nuits propres.
6. ⛔ **Les 3 cas de position** (§7) : trancher, puis `position_suspecte` +
   `position_note` par `.sql`. ⚠️ **Et regarder `pioupiou:1378`** : 341 km à 9 j,
   candidate nette « AUTRE balise ».
7. ⛔ **Mémoire : la ligne en tuple** (≈ −1 030 o/ligne, ≈ −2 041 Mo). **31ᵉ jour
   sans rien de déployé** depuis `af25efb`. Porte de sortie de KAN-4.
8. ⚠️ **`installer-webhook-discord.sh`** — **41ᵉ jour**, variable toujours absente.
9. ⓘ **Le 57014 de `rpc/bw_character_avance`** mérite-t-il un suivi propre ?
   Aucun motif créé ; question posée dans KAN-5.
10. ⓘ **Horaire de la routine** : +4 h 23 ce matin. Côté planification.
11. ⓘ **Jalons de temps dans le bloc hors étapes** de `run.sh` — sans urgence : ce
    bloc **recule** cette nuit (−50,7 s).
12. ⓘ **Le cri de position doit-il recrier** à état constant ? (ouvert depuis le
    01/10 ; le comportement « à front » est maintenant vérifié trois jours de suite)
13. ⓘ **`bw-model-oracle.service` en `failed`** — hors mission, non examiné.

## 13. Ce que ce run a DÉMENTI de la note du 21/10

Sixième fois en treize jours que « une nuit ne fait pas une pente » ressert. Les
trois points à ne pas reprendre tels quels :

| annoncé le 21/10 | relevé le 22/10 |
|---|---|
| mémoire : le palier « score par régime » passe « SOUS le seuil pour la première fois », « le seul mouvement de fond lisible » (2 783 Mo) | **2 944 Mo, +161** — repassé au-dessus en une nuit, c'était un point |
| durée : « la durée BAISSE » (−143 s), marge remontée à 36,9 % | **+129 s, marge 35,3 %** — l'oscillation ±150 s est confirmée, la baisse non |
| témoin du corrigé : « 3ᵉ baisse », « −7,5 pt en trois nuits sur le site, c'est net : à surveiller » (16,6 pt) | **23,3 pt, +6,7** — la baisse est effacée d'un coup |

✅ Ce que le 21/10 avait **juste** et qui tient : `agrume/pi` est le coupable R2
(9ᵉ nuit à +48), `agrume/grille` est hors de cause et **revenu exactement à
766 objets** comme annoncé, le mécanisme des pentes négatives des fenêtres
glissantes (§6.3), le comportement « à front » du cri de position, l'amplitude
élargie du coût par ligne rejouée, et la lecture de `bw-garde-fou-r2` en `failed`
comme un signal et non une panne.

## 14. Respect des règles

✅ **VPS en lecture seule.** Aucun `systemctl` start/restart/daemon-reload, aucun
`enable`, aucun SQL joué, aucun rsync, **rien écrit sur le VPS** — pas même un
fichier temporaire : le script des commentaires a été écrit sur le Mac et pipé par
`ssh … bash -s`. Seules écritures : les trois commentaires Jira.
✅ **Aucun secret lu par valeur** : le `.env` a été **sourcé** pour Jira ;
`BW_DISCORD_WEBHOOK_URL` cherchée **par son nom seul** (`grep -c`) ; le jeton Jira
passe par `curl -K -`, et la seule fois où une config a été affichée, la ligne
`Authorization` était masquée par `sed`.
✅ `10-timeout-s3.conf` **non touché**, remontée du garde non lancée, non proposée.
✅ Aucun ticket créé, fermé, rouvert ni transité. `bw-r2-palier` non créé, motif
`bw_character_avance` non créé.
✅ **Desktop Commander exclusivement** pour fichiers et shell.
✅ Aucun `git push`. Commit local depuis la **racine** du dépôt serveur.
