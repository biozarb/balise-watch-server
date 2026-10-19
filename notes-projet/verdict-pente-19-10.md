# Verdict de pente du 19/10/2026 — ⛔ **R2 A FRANCHI LE PALIER GRATUIT : 10,038 Go sur 10 Go. Cloudflare facture déjà.**

Le reste de la nuit est sain. **La lecture du VPS est complète** ; les écritures
Jira, d'abord empêchées par la chute du pont vers le Mac, ont finalement été
postées à la reprise de 17:59 UTC — voir §9 et §13.

## 16:53 → 17:20 (Paris) — routine Balise Watch, lecture complète, écritures Jira empêchées

**Étape 0 : faite en entier.**

- `git log --oneline --since=midnight` dans `balise-watch-server` **et** dans
  `surveillance balise` : **aucun commit aujourd'hui** dans les deux dépôts.
  Derniers : `53e1f55` (notes-projet 17/10) côté serveur, `379cc2f` (13/10)
  côté racine. ⇒ **aucun autre run n'a tourné ce matin.**
- `claude/verdict-pente-19-10.md` **absent** de la liste d'ouverture (59
  documents, le plus récent `verdict-pente-18-10.md`) ⇒ cette note est une
  **création**, pas une fusion.
- `claude/verdict-pente-18-10.md` lu en entier : **run empêché** (Mac hors
  ligne), zéro mesure, zéro écriture. `verdict-pente-17-10.md` reste la
  dernière note *mesurée*.
- `notes-projet/README.md` relu : les quatre règles.

## 1. Le relevé de la nuit du 18→19/10 — la nuit a bien tourné

`lancement = timer` · `result = success` · `exec_status = 0` · `oom = 0`
Début 05:58:51, fin 07:24:03 (Paris).

| | 17/10 | 18/10 | 19/10 | Δ nuit |
|---|---:|---:|---:|---:|
| `duree_s` | 5 001 | 5 172 | **5 103** | **−69** |
| `cpu_s` | 4 001,0 | 4 131,5 | **4 031,5** | **−100** |
| `marge_s` | 3 099 | 2 928 | **2 997** | +69 |
| marge / garde (8 100 s) | 38,3 % | 36,1 % | **37,0 %** | +0,9 pt |
| `jalon_max_mo` | 3 383 | 3 391 | **3 381** | **−10** |
| `mem_peak_mo` | 3 603,6 | 3 609,3 | **3 607,3** | −2,0 |
| `swap_peak_mo` | 2 347,4 | 2 275,9 | **2 190,5** | **−85,4** |
| `swap_out_pages` | 2 482 829 | 2 592 870 | **2 151 461** | **−441 409** |
| `n_57014` | 0 | 0 | **0** | = |
| `lignes_regime` | 127 718 | 128 148 | **130 654** | **+2 506** |
| `lignes_score_zone` | 138 132 | 138 545 | **141 051** | **+2 506** |
| `balise_jours_rejeu` | 2 084 935 | 2 084 163 | **2 082 945** | −1 218 |

⚠️ **Le 18/10 est lu ici pour la première fois** : la nuit avait bien tourné
sur le VPS, c'est la routine qui n'avait pas pu la lire (Mac hors ligne). Le
registre `historique.jsonl` porte les deux lignes, donc **la consécutivité est
mesurable malgré le matin manqué** — exactement comme le §3.1 de la note du
18/10 le demandait. **Aucune comparaison 17/10 → 19/10 n'a été faite** : tous
les deltas ci-dessus sont nuit à nuit.

### Les deux rapports qui valent mieux que les valeurs brutes

**Coût par ligne rejouée** (`jalon_max_mo × 1048576 / balise_jours_rejeu`) :

```
16/10 1 701,2 o · 17/10 1 701,4 o · 18/10 1 706,1 o · 19/10 1 702,0 o
```

**Quatre nuits dans une bande de 5 octets.** La bande historique (1 686–1 717 o,
posée le 07/10) tient. **Ni pente de fond, ni rupture** : le plafond respire, il
ne dérive pas.

**Coût par ligne de `regime`** (`etapes_s.regime / lignes_regime × 1000`) :

```
16/10 12,57 ms · 17/10 13,12 ms · 18/10 13,04 ms · 19/10 12,37 ms
```

⇒ **le critère `bw-regime-sensibilite` retombe à 0 / 2.** Le compteur valait
**1 / 2** au 17/10 (hausse 12,57 → 13,12). Le 18/10 **baisse** (13,04) : la
consécutivité est cassée, et le 19/10 baisse encore, fortement. **Aucun motif à
poser, aucune question à te reposer sur ce point.** ✅ *La note du 17/10 est
ainsi démentie sur son point n° 1 : la deuxième hausse n'est pas venue.*

**Calcul ou attente ?** `cpu_s` −100 s pendant que la durée fait −69 s : c'est
du **calcul en moins**, pas de l'attente. Cohérent.

**Répartition de la baisse de durée** (somme des quatre étapes vs hors étapes) :

```
            étapes     hors étapes   total
17/10      3 041,1       1 959,9     5 001
18/10      3 093,4       2 078,6     5 172
19/10      3 004,4       2 098,6     5 103
Δ 18→19      −89,0         +20,0       −69
```

La baisse est **entièrement dans les étapes** (`regime` −55,5 · `stabilite`
−36,0 · `rejeu` −8,1 · `glissant` +10,6). Le **bloc hors étapes continue de
monter** doucement (+118,7 puis +20,0 s) et **reste non instrumenté**
(publication, Murphy, événements, pression, duels, purge) — la question posée le
07/10 à Yann (poser des jalons de temps dans `run.sh`) **reste ouverte**, mais
elle n'est plus urgente : la durée baisse.

## 2. ⛔ R2 — LE PALIER EST FRANCHI, c'est le fait du jour

```
17/10   9,942 Go   ( 99,4 %)   58 Mo de marge   « palier atteint dans 57 j »
18/10   9,964 Go   ( 99,6 %)   36 Mo de marge   « palier atteint dans 27 j »
19/10  10,038 Go   (100,4 %)   ⛔ DÉPASSÉ       « palier atteint dans 0 j »
```

Le garde-fou l'a crié **trois fois** ce matin, dans les trois appelants :

```
⚠️  palier gratuit DÉPASSÉ : 10.04 Go sur 10 Go — R2 facture déjà
```

**C'était l'avertissement n° 2 de la note du 17/10**, qui disait « à vérifier en
premier au prochain run, avant les tickets ». Il l'a été. **La prédiction était
juste et l'échéance est tombée pendant le trou du 18/10.**

⚠️ **Le « rythme mesuré » du garde-fou sous-estime** : il annonçait
+0,04 Go/mois (≈ 1,3 Mo/jour) alors que les deltas réels sont **+22 Mo** puis
**+74 Mo** sur les deux dernières nuits. Son estimation est un lissage long ; ce
sont les **à-coups** qui ont mangé la marge — `agrume/grille` avait pris
**+692 Mo** le 16/10 avant d'en rendre 21 le 17/10. **Ne pas se fier à
l'échéance affichée pour la suite** : c'est la pente d'`audit_r2.py` qui est en
cause (décision déjà en attente, §12).

Écritures de la nuit : `backend=r2 écritures=4 (plafond 10) lectures=0
suppressions=0 octets=168,6 Mo` — nominal, et **ce n'est pas le coupable** (ces
écritures écrasent en place). Le total qui monte, c'est de l'**accumulation**.

⛔ **Décision pour Yann — rien n'a été créé sans son accord :**

1. **Rétention d'`agrume/grille`** : c'est elle qui fait les à-coups. Décision
   en attente depuis le 16/10.
2. **Motif Jira `bw-r2-palier`** : aucun ticket ne porte ce label (vérifié par
   JQL sur tout le projet : KAN-2 → KAN-17, seuls KAN-3/4/5 portent
   `bw-surveillance`). **Le créer suppose ton accord** — je ne l'ai pas créé.
3. La facturation R2 au-delà de 10 Go est au Go-mois : le dépassement actuel
   (38 Mo) est négligeable **aujourd'hui**, mais il court tous les jours tant
   que la rétention n'est pas tranchée.

## 3. Purge `model_score_zone` — nuit propre, 12ᵉ d'affilée

```
→ purge model_score_zone : 137 901 ligne(s) effacée(s) en 8 tranche(s)
ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée.
```

- **Aucun 57014**, nulle part : `n_57014 = 0` au registre, et rien dans le bloc.
- **Aucun avertissement de tranche**, donc aucun rejeu à interpréter.
- **Aucune sonde en défaut** (pas de « plus vieille journée illisible »).
- **Aucun « des lignes RESTENT »** ⇒ rien ne reste en base.
- Volume effacé 137 901 (136 007 le 18/10) : il suit la journée purgée, **il ne
  signifie rien** — on ne le lit pas comme un signal.

**Compteur de fermeture KAN-5 : 12 / 3** (10 au 17/10, +18/10, +19/10).

⚠️ **La réserve du 17/10 tient, mais s'allège :** le 57014 **changeait
d'adresse** (10/10, 14/10, puis 16/10 avec `⚠️ purge model_verif_daily :
HTTP 500`). Les nuits du 18 et du 19/10 n'en portent **aucun, même ailleurs**.
Deux nuits ne font pas une pente non plus — la réserve reste notée.

## 4. Mémoire — plat, swap qui recule, un TROISIÈME jalon passe le seuil

Le **jalon max** ne bouge pas (3 381 Mo, +581 au-dessus du seuil de 2 800), le
**swap au pic recule** franchement (−85,4 Mo, −156,9 sur deux nuits) et les
pages sorties en swap chutent de 441 409.

**Fait nouveau** : un **troisième** jalon franchit le seuil cette nuit —

```
⛔ mémoire après le score par régime : 2 835 Mo — AU-DESSUS DU SEUIL
   série du jalon : 2 638 (17/10) → 2 785 (18/10) → 2 835 (19/10)
```

Il y avait **deux** jalons au-dessus du seuil les 17 et 18/10 (« rejeu
d'archive » 2 993 Mo et « oubli de la fenêtre rejouée » 3 381 Mo) ; il y en a
**trois** cette nuit.

⚠️ **Mais il monte AVEC LE VOLUME, pas tout seul** : `lignes_regime` fait
+2 936 en deux nuits (127 718 → 130 654) et `lignes_score_zone` +2 919, pendant
que le **coût par ligne de `regime` BAISSE** (13,12 → 12,37 ms). Plus de lignes
à traiter, pas un traitement plus lourd. **Ce n'est pas une dérive**, et le
jalon max, lui, n'a pas bougé.

**Contrôle de pente du 19/10 à 07:30 — MUET sur les deux motifs :**

```
ⓘ 81 relevé(s), 60 comparable(s) ; durée : 10 points, pente -69 s/nuit ;
  mémoire : 10 points, pente -22 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate/négative, ou échéance hors horizon
```

Rappel : cette pente est le **25ᵉ centile des différences** — elle ignore par
construction les deux plus grosses hausses.

**Calcul à taux constant, à titre indicatif et PAS une prévision** : à
−22 Mo/nuit, il faut 581 / 22 = **26,4 nuits** pour repasser sous 2 800 Mo, soit
vers le **14/11/2026**. ⚠️ **À ne pas reprendre comme une échéance** : la série
du coût par ligne est **plate**, pas descendante ; la pente −22 Mo/nuit vient de
la forme de la distribution des différences, pas d'un mouvement de fond.

## 5. Les trois correctifs du 07/10 — verdict correctif par correctif

| correctif | verdict du 19/10 |
|---|---|
| **1. webhook `--ipv4`** | ✅ **tient.** `ⓘ push parti (webhook, HTTP 200)` le 18/10 **et** le 19/10. Aucun 429 depuis le déploiement. Trafic nominal (1 push/nuit, bien dans les 2–7 msg/j attendus). |
| **2. garde-fou des deux jetons** | ✅ **tient.** Le contrôle de 07:30 s'est tu (« rien à dire ») : pas de jeton posé, pas de doublon possible. `controle_quotidien.sh` conserve son `$ETAT` — **non touché**. |
| **3. rejeu de purge ≠ échec** | ✅ **tient, non sollicité.** Aucun avertissement de tranche cette nuit, donc `bilan_purge()` n'avait rien à rattraper. Le contrôle n'a rien dit de faux sur la purge. |

## 6. Position — 4 balises confirmées, liste INCHANGÉE, pas de cri

```
⛔ position : 10 balise(s) divergent du gel (10 j lus), dont 4 CONFIRMÉE(S) (≥ 10 j)
   ⛔ pioupiou:2171          38 915 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE · Windbird 2171
   ⛔ pioupiou:1378          18 508 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE · Col de la Merquiere
   ⛔ pioupiou:367            6 764 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE · Le relais
   ⛔ infoclimat:STATIC0491   1 159 m · 10 j · nœud 0,01 CHANGE ·          infoclimat STATIC0491
```

**Identique au 18/10, balise par balise et mètre par mètre.** Le cri est **à
front, pas à état** : rien de neuf ⇒ pas de cri, et c'est le comportement
attendu. ⓘ La question du 01/10 reste ouverte : **faut-il qu'il recrie** quand
une balise reste confirmée ?

⚠️ **La composition a changé depuis le 07/10** : `pioupiou:1333` (87,7 km) et
`pioupiou:1388` (2 363 m, qui s'éloignait) **ne sont plus dans la liste
confirmée** ; `pioupiou:1378` et `pioupiou:367` y sont entrées. **Le geste
attendu de Yann porte donc sur la liste d'aujourd'hui, pas sur celle du 07/10** :
trancher chaque cas, puis poser `position_suspecte` + `position_note` sur
`station_zone` par `.sql`.

## 7. Les autres témoins — rien qui demande un ticket

- **Témoins du mélange — ils sont repassés au-dessus de la barre.** 19/10 : sur
  7 498 balise-jours×échéance, **4,0565 km/h** contre 4,125 pour le meilleur
  membre a priori ⇒ **gain +1,7 %**, mélange devant dans **50,2 %** des cas ;
  contre la moyenne **uniforme** (n = 1 110) : 4,1115 vs 4,3193, **gain
  +4,8 %**. Le 18/10 : +2,5 % et 49,4 %. ✅ **L'alerte du 07/10 (−0,6 %, 49,2 %)
  est démentie** : le gain est redevenu positif et le « devant » a repassé 50 %.
  L'erreur absolue a aussi beaucoup baissé (4,06 contre 4,41 km/h la veille) —
  journée moins ventée. **Pas de motif Jira à demander.**
- **Témoin du corrigé** : part imputable au site **22,9 pt** (24,1 la veille) ;
  version FIN : part secteur+heure **12,7 pt** (14,3). Stable dans la bande.
- **Écarts du recalcul indépendant** : **6** (5 le 18/10), tous de la même
  signature (`ici None, base X : 0–1 h appariées ici (< 6) mais la base porte une
  ligne`). Récurrent, antérieur, non aggravé.
- **Événements** : 3 444 balises zonées, aucun événement retenu faute de
  confirmation réseau — inchangé.
- **Duels** : `arome_r2 ↔ meteofrance_arome_france_hd (+6 h)` médiane +0,104,
  IC95 [+0,093 ; +0,119] → `b_better`, inchangé. Le cumul reste **tronqué par la
  rétention 30 j** (dette connue, `duel.DUEL_DAYS`).
- **Second canal du téléphone (Discord)** : ⛔ **`BW_DISCORD_WEBHOOK_URL` toujours
  ABSENTE** du `.env` (nom seulement, valeur non lue). Aucun `ⓘ push Discord
  parti` au journal — cohérent. `~/installer-webhook-discord.sh` attend toujours
  que Yann le lance : **38ᵉ jour**.
- **`mutations_memoire`** : 3 mutations non vues (2, 5, 13), dette antérieure,
  inchangée.

## 8. Les tickets — ce qui a été décidé

**États revérifiés par GET avant toute écriture** (`updated` = 2026-10-17 11:10
pour les trois, c'est-à-dire les commentaires du run du 17/10) :

| ticket | label | statut | décision du 19/10 |
|---|---|---|---|
| **KAN-3** | `bw-pente-duree` | **Terminé** (`done`) | ⛔ **rien.** La durée **BAISSE** (−69 s), `cpu_s` baisse aussi, et le contrôle annonce une pente de −69 s/nuit. La consigne est claire : on ne commente que si elle **augmente**. **Non rouvert, non commenté, non touché.** |
| **KAN-4** | `bw-pente-memoire` | **À faire** | **reste ouvert**, ✅ **commenté à la reprise** (§13). Les trois conditions de fermeture ne sont PAS réunies : contrôle muet ✔, mais plafond non retombé (−10 Mo, +581 au-dessus du seuil) et **swap au pic à 2 190 Mo, très loin de 0**. ⛔ *Un ticket fermé à tort vaut moins qu'un ticket ouvert.* |
| **KAN-5** | `bw-purge-57014` | **À faire** | **reste ouvert**, ✅ **commenté à la reprise** (§13). Compteur **12 / 3**, mais la condition de fermeture est inchangée : jouer `diagnostic_base_sous_tension_2026-09-29.sql` d'abord — **21ᵉ jour d'attente** — **et** l'accord de Yann. |
| *(aucun)* | `bw-r2-palier` | — | ⛔ **non créé.** Le palier est franchi, mais créer un motif engage : **c'est à Yann de trancher** (§2). |

**Canal choisi : `bw_jira_commenter <CLÉ>`** (le canal délibéré), et non
`bw_jira_signaler`. Deux raisons, et c'est un choix assumé qui se dit ici :
le contenu est de l'**analyse délibérée** (séries sur quatre nuits, correction
explicite de deux annonces de la note du 17/10, coûts par ligne) ; et
`commenter` prend une **clé**, ne cherche rien, ne crée rien, ce qui **exclut
tout risque de créer un ticket neuf** — le piège nommé dans la consigne.

## 9. La chute du pont, et ce qu'elle a coûté

**Le pont vers le Mac est tombé pendant la phase d'écriture**, après que toute
la lecture du VPS était terminée. Il est revenu une fois pour ~1 minute, puis
est retombé ; **six tentatives** espacées (45 s, 90 s, 2 min, 2 min, 2 min,
2 min) ont échoué avec « The device this session is bound to is not connected to
the bridge », et le serveur `Desktop_Commander` a cessé d'être annoncé.

**Le Mac est le seul chemin vers le VPS** (la clé SSH y vit) **et vers Jira**
(les identifiants ne se lisent qu'en sourçant le `.env` du VPS, jamais par
valeur). Les deux commentaires et ce miroir ont donc attendu la reprise (§13).

⚠️ **Deux notifications sont parties à Yann**, et la seconde corrige la
première : la première annonçait « KAN-4 et KAN-5 commentés » alors que les
écritures venaient d'échouer. **La correction a été envoyée dans la minute.**
*Leçon : ne pas annoncer une écriture au passé avant d'en avoir le retour.*

✅ **Règle de lecture seule sur le VPS : respectée.** Aucun `systemctl`
start/restart/daemon-reload, aucun `enable`, aucun SQL joué, aucun rsync, rien
écrit dans `~/balise-watch` ni dans `/etc`. Aucun secret lu par valeur (le
`.env` a été **sourcé**, jamais affiché ; seule la *présence* de
`BW_DISCORD_WEBHOOK_URL` a été testée). `10-timeout-s3.conf` non touché. Aucun
ticket créé, fermé, rouvert ni transité. Aucun `git push`.

## 10. Les textes des deux commentaires

Ils ont été postés tels quels à la reprise — voir KAN-4 et KAN-5 pour le texte
intégral. Résumé :

### KAN-4 — « plafond stable, swap qui recule, un troisième jalon passe le seuil »

Plafond 3 381 Mo (seuil 2 800, +581 au-dessus) ; série 3 383 → 3 391 → 3 381.
Pic processus 3 607,3 Mo (plat). Swap au pic 2 190,5 Mo (−85,4 sur la nuit,
−156,9 sur deux nuits). Pages sorties en swap −441 409. `oom = 0`. Coût par
ligne rejouée 1 701,2 → 1 701,4 → 1 706,1 → **1 702,0 o** : quatre nuits dans
une bande de 5 o. Contrôle **muet** (pente −22 Mo/nuit, 25ᵉ centile des
différences). Calcul à taux constant **indicatif** : 26,4 nuits, vers le 14/11 —
**à ne pas reprendre comme une échéance**. Fait nouveau : « score par régime » à
**2 835 Mo** (2 638 → 2 785 → 2 835), trois jalons au-dessus du seuil contre
deux, mais il monte **avec le volume** pendant que le coût par ligne de `regime`
**baisse**. **Reste ouvert** : swap très loin de 0. Remède inchangé : **ligne en
tuple** (≈ −1 030 o/ligne), rien de déployé depuis `af25efb` (21/09).

### KAN-5 — « purge propre, 12ᵉ nuit consécutive sans 57014 »

137 901 lignes effacées en 8 tranches, nombre lisible ⇒ **purge aboutie**. Aucun
57014, aucun avertissement de tranche, aucune sonde en défaut, aucun « des
lignes RESTENT ». Volume effacé **non lu comme un signal**. Compteur **12 / 3**.
**Réserve maintenue mais allégée** : le 57014 changeait d'adresse (10/10, 14/10,
16/10 sur `model_verif_daily`) ; les 18 et 19/10 n'en portent aucun, même
ailleurs — mais deux nuits ne font pas une pente. **Reste ouvert** : le `.sql`
d'abord (**21ᵉ jour**) et l'accord de Yann. Douze nuits propres ne sont pas un
correctif : il y en avait eu trois d'affilée (03–05/10) avant le retour du 06.

## 11. Horaire de la routine — ⛔ **+7 h 43, le pire de la série**

Programmée pour **07:09:05 UTC**, tirée à **14:52:36 UTC**.

```
13/10 +52 min · 14/10 +6 h 11 · 15/10 +7 h 37 · 16/10 +4 h 03
17/10 +1 h 56 · 18/10 +1 h 39 · 19/10 **+7 h 43**  ← record négatif
```

ⓘ Le VPS, lui, est **à l'heure** : notation à 05:58:51, contrôle à 07:30:25,
timer suivant armé pour le 20/10 à 07:30:52. **Le trou est côté planification**,
et il s'aggrave. Conséquence concrète ce matin : le dépassement R2 a été constaté
**près de huit heures après qu'il s'est produit**.

## 12. Décisions en attente de Yann — la liste à jour

1. ⛔ **R2 : le palier est franchi** (10,038 Go). Rétention d'`agrume/grille`,
   et/ou pente d'`audit_r2.py` (son « rythme mesuré » sous-estime les à-coups),
   et/ou motif `bw-r2-palier` (**non créé**). **Le plus urgent : il court.**
2. ⛔ **`diagnostic_base_sous_tension_2026-09-29.sql`** — toujours pas joué,
   **21ᵉ jour**. C'est la porte de sortie de KAN-5.
3. ⛔ **Les 4 cas de position** (liste du §6, **recomposée** depuis le 07/10) :
   trancher, puis `position_suspecte` + `position_note` par `.sql`.
4. ⛔ **Mémoire : la ligne en tuple** (≈ −1 030 o/ligne). Rien de déployé depuis
   le 21/09. C'est la porte de sortie de KAN-4.
5. ⚠️ **`installer-webhook-discord.sh`** — **38ᵉ jour**, variable toujours
   absente.
6. ⚠️ **Jalons de temps dans le bloc hors étapes** de `run.sh` (écriture) — moins
   urgent : la durée baisse, mais le bloc monte encore (+20 s).
7. ⓘ **Le cri de position doit-il recrier** à état constant ? (ouvert depuis le
   01/10)

## 13. 17:59 (UTC) — reprise, écritures Jira et miroir git

Le pont est revenu ~1 h après la chute. **Vérification faite avant d'écrire**,
comme le §9 l'exigeait :

```
KAN-4 "updated":"2026-10-17T11:10:08.182+0200"   ← INCHANGÉ
KAN-5 "updated":"2026-10-17T11:10:10.282+0200"   ← INCHANGÉ
```

⇒ **l'essai interrompu n'avait jamais atteint le VPS** : la commande était morte
côté pont. **Aucun risque de doublon**, les deux commentaires ont donc été
postés.

| action | état |
|---|---|
| GET `updated` de KAN-4 et KAN-5 avant écriture | ✅ fait, inchangés |
| `bw_jira_commenter KAN-4` | ✅ **« commentaire délibéré ajouté à KAN-4 »** |
| `bw_jira_commenter KAN-5` | ✅ **« commentaire délibéré ajouté à KAN-5 »** |
| miroir `notes-projet/verdict-pente-19-10.md` | ✅ écrit |
| commit local (racine du dépôt serveur, sans push) | ✅ fait |
| fusion de cette section dans le document projet | ✅ faite (`project_read` puis `project_write`) |

✅ Aucun ticket créé, fermé, rouvert ni transité. `bw-r2-palier` **non créé**.
VPS en lecture seule, hormis les deux commentaires Jira. Aucun `git push`.
