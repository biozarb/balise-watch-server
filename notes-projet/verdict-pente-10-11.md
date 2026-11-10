# Verdict de pente du 10/11/2026 — ⛔ **R2 repasse sous le palier, et c'est un ARTEFACT** (3ᵉ creux d'`agrume/grille`, garde-fou muet pile cette nuit-là). ✅ **Bloc purge PROPRE** + **correction de méthode : `n_57014` n'est pas un indicateur de purge.** ⛔ **Durée +177 s, 81 % hors étapes.** ⚠️ **Témoins du mélange sous 50 % pour la première fois.** Trois commentaires délibérés, aucun ticket fermé.

## 08:17–08:30 (Paris, CET) — routine Balise Watch, run complet

**Étape 0 : faite en entier, avant toute autre chose.**

- `git log --oneline --since=midnight` dans **les deux** dépôts : ✅ **aucun
  commit du jour**. Dernier commit serveur : **`f5f308f` du 09/11** (rectification
  du compteur `agrume/pi` dans la note du 09/11). Dépôt principal : `cc10b42`
  du 01/11. ⇒ **Aucune autre session n'a tourné ce matin.**
- `project_read claude/verdict-pente-10-11.md` : **absent** ⇒ cette note est une
  **création**, pas une fusion.
- `project_read claude/verdict-pente-09-11.md` : ✅ **lu en entier** — c'est lui
  qui fixe les séries à vérifier et les deux corrections à ne pas reconduire.
- `notes-projet/README.md` relu : les quatre règles.
- ⓘ **Confirmation indépendante par Jira** : le dernier commentaire d'avant
  écriture datait du **09/11 08:20** sur les trois tickets ⇒ rien d'autre
  n'avait écrit ce matin.

## 1. ✅ L'ouverture SSH robuste du 09/11 a servi dès le premier appel

Les deux lignes du §1.1 d'hier, dans cet ordre, à **chaque** appel de shell :

```
export SSH_AUTH_SOCK="$(launchctl getenv SSH_AUTH_SOCK)"
ssh-add --apple-load-keychain >/dev/null 2>&1
```

`ssh-add -l` → `256 SHA256:d0C/G0LX… balise-watch-vps (ED25519)`, rc=0 ;
`ssh debian@51.91.102.146 date -u` → répond. ✅ **Aucun des deux pièges frères
ne s'est présenté ce matin**, et je ne peux pas dire si c'est parce que les deux
lignes les ont neutralisés ou parce qu'aucun n'était là — **les deux lignes
coûtent 0,2 s, la question n'a pas à être tranchée.**

⚠️ **Piège n°3, neuf, documenté et payé ce matin** : le shell de Desktop
Commander est **zsh**, et zsh **ne découpe pas** une variable sur les espaces.
Un `S="ssh -o BatchMode=yes …"` puis `$S 'cmd'` rend **rc=127** (`command not
found`) sur chaque appel — trois lectures perdues. ⇒ **Écrire `ssh` en entier à
chaque appel**, jamais via une variable.

## 2. La nuit, chiffre par chiffre

`lancement=timer`, `result=success`, `exec_status=0` ⇒ relevé **comparable**, et
le contrôle le compte (**103 relevés, 82 comparables**, contre 102/81 hier).

| | 07/11 | 08/11 | 09/11 | **10/11** |
|---|---|---|---|---|
| durée (s) | 4 806 | 4 889 | 4 874 | **5 051** (+177) |
| cpu (s) | 3 848,9 | 3 970,2 | 3 921,8 | **3 998,6** (+76,8) |
| marge / garde 8 100 s | 40,67 % | 39,64 % | 39,83 % | **37,64 %** |
| jalon max (Mo) | 3 369 | 3 352 | 3 366 | **3 379** (+13) |
| jalon − seuil 2 800 | +569 | +552 | +566 | **+579** |
| swap au pic (Mo) | 2 474,3 | 2 087,5 | 2 100,5 | **2 319,4** (+218,9) |
| pages sorties | 2 593 421 | 2 244 601 | 2 118 377 | **2 239 155** |
| coût / ligne rejouée (o) | 1 730,2 | 1 722,7 | 1 731,2 | **1 739,1** (+8,0) |
| coût / ligne `regime` (ms) | 10,680 | 11,559 | 10,948 | **10,895** (−0,053) |
| `n_57014` | 0 | 0 | 1 | **1** (hors purge, §3.2) |
| lignes effacées (purge) | 151 401 | 150 712 | 151 649 | **154 362** |
| balise-jours rejoués | 2 041 814 | 2 040 335 | 2 038 813 | **2 037 288** |
| lignes `regime` | 144 170 | 141 261 | 141 805 | **144 062** |

Répartition du temps (les quatre étapes instrumentées contre le reste) :

| | 09/11 | **10/11** |
|---|---|---|
| glissant (s) | 947,8 | 974,7 (+26,9) |
| `regime` (s) | 1 552,5 | 1 569,6 (+17,1) |
| rejeu (s) | 88,9 | 74,7 (−14,2) |
| stabilité (s) | 311,9 | 315,2 (+3,3) |
| **somme des 4 étapes** | 2 901,1 | **2 934,2** (+33,1) |
| **bloc hors étapes** | 1 972,9 | **2 116,8** (+143,9) |

⇒ ⛔ **+143,9 s sur +177, soit 81 % de la hausse DANS le bloc non instrumenté**
(publication, Murphy, événements, pression, duels, purge). **Quatrième fois en
sept jours** que la réponse tombe là. ⇒ ⬆️ **La demande de jalons de temps dans
`run.sh` se repose, inchangée** : c'est une écriture, donc c'est Yann.

### 2.1 Ce que ces chiffres ne disent PAS — et c'est l'essentiel

J'ai relu **vingt-cinq nuits** de `historique.jsonl` (et non les quatre
dernières) avant d'écrire une seule phrase de tendance. Résultat :

- ⚠️ **37,64 % n'est PAS un record de marge basse** : **34,57 %** le 23/10 et
  **35,11 %** le 20/10 sont plus bas. 5 051 s est la plus haute durée depuis le
  **31/10 (5 079 s)**. Le garde de 8 100 s n'est pas menacé.
- ⚠️ **3 379 Mo n'est PAS une pente** : la bande **3 151–3 452 Mo est inchangée
  depuis vingt-cinq nuits** (3 151 le 26/10, 3 452 le 25/10). Deux hausses de
  suite (3 352 → 3 366 → 3 379) **ne font pas une pente** — exactement
  symétrique aux « cinq reculs » annoncés le 09/11 puis cassés le même jour.
- ⚠️ **2 319,4 Mo de swap n'est PAS un record** : **2 541,0** le 24/10 et
  **2 474,3** le 07/11 sont plus hauts. Le swap reste **sans série et sans
  explication** — et je ne reprends pas davantage l'explication par la charge
  que je n'avais abandonnée le 07/11.
- ⚠️ **Le coût par ligne rejouée touche 1 739,1 o**, soit **8 o au-dessus** du
  haut de la bande des onze nuits précédentes (1 686–1 731), soit **+0,5 %**.
  Je ne le compte pas comme une pente. Et ce n'est pas le volume : la fenêtre
  rejouée **décroît encore** (−1 525 balise-jours, quatrième nuit de baisse).

### 2.2 Deux relevés neufs — et tous deux relativisés dans la même phrase

a) ⚠️ **Le jalon du rejeu d'archive monte QUATRE nuits de suite** :
   2 935 → 2 946 → 2 953 → **2 981 Mo**. ⛔ **Mais 2 981 est un RETOUR dans la
   bande d'octobre** (2 941–3 029, plus haut **3 029** le 25/10), **pas une
   sortie**. ⇒ **Quatre points ne font pas une pente.** C'est la leçon payée
   cinq fois en six semaines, et je l'applique ici **contre** mon propre relevé.
b) ⚠️ **Une TROISIÈME ligne d'incident** cette nuit : `⛔ mémoire après le score
   par régime : 2 861 Mo — AU-DESSUS DU SEUIL`. ⛔ **Ce n'est PAS neuf** :
   **2 944 Mo le 22/10**, **2 914 le 04/11**, **2 901 le 25/10** dépassaient
   déjà. Le motif avait juste été absent trois nuits. ⇒ **Je ne l'annonce pas
   comme un fait nouveau.**

ⓘ **Un indice de charge**, qui explique une partie et pas le tout : la journée
notée (09/11) était bien plus active — `model_verif_event` rend **60 524 lignes**
contre 23 435 le 07/11, les lignes de `regime` remontent de **+2 257** et
`model_score_zone` passe à **154 748**. Mais publication et événements sont
justement **dans le bloc non instrumenté** : ⇒ **sans jalons de temps, cette
hypothèse n'est pas vérifiable.** Je la pose, je ne la conclus pas.

## 3. ✅ LE BLOC PURGE EST PROPRE — et une correction de méthode qui vaut pour toutes les nuits à venir

### 3.1 Le bloc, mot pour mot, en entier

```
→ purge model_score_zone : 154362 ligne(s) effacée(s) en 8 tranche(s)
ⓘ purge model_character : rien avant le 2027-02-04 (première écriture
  2026-08-08, rétention 180 j) — aucune requête lancée.
```

Lecture, grille du 28/09 et du 06/10, **sans l'élargir** :

- ✅ **AUCUNE tranche en échec** : pas une ligne portant `?as_of=eq.J&regime=eq.R`.
- ✅ **AUCUN avertissement de SONDE** : « plus vieille journée illisible » est
  **absente** cette nuit, contrairement au 09/11.
- ✅ **8 tranches, 154 362 lignes, nombre lisible** ⇒ **la purge a abouti.**
- ✅ `des lignes RESTENT` est absente — **et cette nuit cette absence vaut**,
  puisque la sonde n'a pas bronché. ⓘ **Différence réelle avec le 09/11**, où la
  sonde avait bronché et où je refusais d'en conclure quoi que ce soit.
- ⚠️ **154 362 lignes est un peu au-dessus de la bande relevée jusqu'ici**
  (≈ 125 000 à 152 000). **Ce n'est pas un signal** : le volume suit la journée
  purgée, il monte et descend sans rien signifier. **Je ne le lis pas.**

### 3.2 ⛔ CORRECTION DE MÉTHODE : `n_57014` du registre n'est PAS un indicateur de purge

Le registre porte **`n_57014 = 1`** cette nuit, et le bloc purge est **propre**.
Le **seul** 57014 de tout le journal de la nuit est **ailleurs** :

```
2026-11-10T05:21:41+01:00 ⚠️ rpc/bw_character_avance : HTTP 500
  {"code":"57014", … statement timeout} — reprise 1/3
2026-11-10T05:23:36+01:00 → model_character : 407309 accumulateurs avancés
  sur 407309 envoyés
```

⇒ ✅ **Il a été RATTRAPÉ** (407 309 / 407 309, soit 100 %), deux minutes plus
tard, au premier rejeu sur trois disponibles.
⇒ ⛔ **`n_57014` compte les 57014 de TOUTE la nuit, pas ceux de la purge.** Il ne
faut **jamais** lire `n_57014 ≥ 1` comme « la purge a eu un timeout ».
⇒ ⓘ **Cela lève une contradiction apparente dans les notes** : plusieurs nuits
comptées « propres » entre le 29/10 et le 08/11 portent `n_57014 = 1` (**29, 30,
31/10, 01 et 04/11**). Elles étaient bien propres **côté purge** ; le compteur du
registre parlait d'autre chose. **Aucune note antérieure n'est démentie, mais
l'ambiguïté est levée.**

### 3.3 Où en est le compteur KAN-5 — deux lectures, toujours pas tranchées

1. **Critère ÉCRIT** sur le ticket et dans le prompt (« trois nuits consécutives
   **sans 57014 dans le bloc purge** ») : le 09/11 en portait un (de sonde) ⇒
   remise à zéro ; cette nuit est propre ⇒ **1 / 3**.
2. **Critère par NATURE** (aucune tranche perdue, purge aboutie, nombre lisible) :
   **quinzième nuit consécutive**, et le ticket serait **fermable depuis onze
   jours**.

⇒ ⬆️ **Question posée à Yann pour la NEUVIÈME fois**, sur le ticket. **Rien n'est
fermé ni transité en attendant** : un ticket fermé à tort vaut moins qu'un
ticket ouvert.

## 4. ⛔ LE FAIT DU MATIN : R2 repasse sous le palier, et c'est un ARTEFACT

```
│ total compte   :    9.988 Go   ( 99.9 % du palier 10 Go)
│ objets         :     7861
│ pente mesurée  :   -0.005 Go/mois  (somme des préfixes, 25e centile des différences)
│ balise-watch-grids:agrume/grille   4.500 Go    652 objets   -0.004 Go/mois
│ balise-watch-grids:agrume/pi       1.959 Go   4435 objets   +0.582 Go/mois
2026-11-10T05:24:08Z run garde-fou-r2 OK en 5s
```

| | 08/11 | 09/11 | **10/11** |
|---|---|---|---|
| total compte | 10,693 Go (106,9 %) | 10,701 Go (107,0 %) | **9,988 Go (99,9 %)** |
| objets | 7 845 | 7 911 | **7 861** |
| `agrume/grille` | 5,323 Go / 766 obj. | 5,323 Go / 766 obj. | **4,500 Go / 652 obj.** |
| `agrume/pi` | 1,938 Go / 4 387 obj. | 1,938 Go / 4 387 obj. | **1,959 Go / 4 435 obj.** |
| verdict garde-fou | ⚠️ DÉPASSÉ, code 1 | ⚠️ DÉPASSÉ, code 1 | ✅ **OK, code 0** |

⛔ **Il ne faut PAS lire ce 99,9 % comme une guérison.** `agrume/grille` perd
**0,823 Go et 114 objets** en une nuit — c'est **exactement** le motif du
**27/10** et du **05/11** (4,609 Go / 667 objets cette nuit-là), où le préfixe
revenait **au Mo et à l'objet près** la nuit suivante. ⇒ **Troisième occurrence
du même creux**, et c'est lui, à lui seul, qui fait repasser le total sous le
palier : **4,500 + 0,823 = 5,323 Go**, soit **10,811 Go** au compte réel, donc
**108,1 %** si `agrume/grille` est à son niveau habituel.

⇒ ⛔ **Et c'est la prédiction du 09/11 qui se vérifie, à la lettre** : « le
garde-fou se tait les nuits de creux, et c'est précisément là que personne n'est
averti ». Cette nuit le garde-fou rend **code 0**, **aucun cri n'est parti**, et
le journal ne porte **aucune** ligne `⚠️ palier gratuit DÉPASSÉ`. **La nuit où
l'audit se trompe est la nuit où il se tait.**
⇒ ⓘ **Le bloc « produits indexés » confirme le mécanisme** plutôt qu'il ne le
démentit : il dit `agrume/grille/ 652 présentes / 652 réclamées ✓` — **l'index
et le listing lisent le même état partiel**. Un `✓` ne prouve donc rien sur la
complétude réelle du préfixe. ⚠️ Il ne porte par ailleurs plus que **trois**
sous-préfixes (`agrume/piaf/` a disparu de ce bloc par rapport au 09/11) : noté,
**pas interprété**.

### 4.1 Ce qui, lui, ne bronche pas : `agrume/pi`

**1,938 → 1,959 Go**, **4 387 → 4 435 objets**, soit **+48 objets**, **28ᵉ nuit
sans un seul recul**, à **+0,582 Go/mois**.
⇒ ⛔ **L'illusion de la pente est intacte** : **−0,005 Go/mois affiché** au total
pendant qu'`agrume/pi` seul fait **+0,582**. Le 25ᵉ centile des différences,
encore lui. ⇒ **Geste attendu de Yann inchangé** : décider d'une rétention sur
`agrume/pi`, ou accepter la facture.

## 5. Ce qui a été fait sur les tickets — et pourquoi par ce canal

⚠️ **Le contrôle de 07:30 s'est TU**, pour le deuxième matin de suite :

```
2026-11-10T07:30:48+01:00 … rien à dire : pente plate ou négative, ou échéance hors horizon
ⓘ 103 relevé(s), 82 comparable(s) ; durée : 10 points, pente -15 s/nuit ;
  mémoire : 10 points, pente -17 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
```

⚠️ **La pente de durée est passée de −101 à −15 s/nuit en une nuit** : elle reste
négative (d'où le silence), mais elle a perdu 85 % de sa valeur. ⓘ Mécanique,
pas mystérieux : le +177 s entre dans la fenêtre de dix points et tire le 25ᵉ
centile vers le haut. ✅ Timer armé pour demain : `Wed 2026-11-11 07:30:25 CET`.

**Canal retenu : `bw_jira_commenter` (délibéré), sur les trois tickets.**
Justification redite, puisque le choix doit se dire : le contrôle ne parlant de
rien, `bw_jira_signaler` aurait été **libre** pour KAN-4 et KAN-5 — mais il
**cherche par étiquette et CRÉE si rien ne répond**, et créer un ticket sans
l'accord de Yann est interdit. `bw_jira_commenter` prend la **clé**, ne cherche
rien, ne crée rien, ne touche pas au jeton du jour. Pour KAN-3 (« Terminé ») il
n'y a de toute façon pas d'autre voie, `bw_jira_chercher` filtrant sur
`statusCategory != Done`. ⇒ **Trois commentaires délibérés, assumés.**

**GET avant ET après écriture :**

| ticket | étiquette | statut avant | statut après | comm. avant | comm. après |
|---|---|---|---|---|---|
| KAN-3 | `bw-pente-duree` | Terminé / `done` | **Terminé / `done`** | 40 | **41** |
| KAN-4 | `bw-pente-memoire` | À faire / `new` | **À faire / `new`** | 54 | **55** |
| KAN-5 | `bw-purge-57014` | À faire / `new` | **À faire / `new`** | 37 | **38** |

✅ **+1 chacun, aucun changement d'état, aucun ticket créé.**

### 5.1 KAN-4 (mémoire) — **reste ouvert, 1 condition sur 3**

- le jalon **n'est pas mesurément retombé** : **+579 Mo** au-dessus du seuil ;
- le swap au pic **n'est pas ≈ 0** : **2 319,4 Mo** ;
- ✅ seul le **silence du contrôle** est acquis.
⇒ **Pas de fermeture.** Le commentaire porte les chiffres, le coût par ligne
rejouée, **les deux relativisations du §2.1 et les deux relevés neufs du §2.2**,
et le rappel que **rien n'a été déployé côté mémoire depuis `af25efb` (21/09)**,
soit **CINQUANTE jours**. Remède mesuré inchangé : la **ligne en tuple**
(≈ −1 030 o/ligne, §2.6 de l'enquête du 10/09), après la mesure `tuple` vs
`namedtuple` à la sonde, **jamais jouée**. L'élagage de `units` avait rendu
−124 Mo au lieu de −1 500 : **les gains sont dans la structure.**
ⓘ **Calcul à taux constant : impossible et vide de sens** — la pente est
**négative**, aucune échéance ne se calcule. Le problème est un **NIVEAU**, pas
une dérive.

### 5.2 KAN-5 (purge) — **reste ouvert, question posée (9ᵉ)**

Le commentaire donne le bloc purge **mot pour mot**, la **correction de méthode
du §3.2** (c'est la pièce neuve de ce matin), les deux lectures du compteur, et
la question. ⛔ **Rien fermé.** ⓘ
`diagnostic_base_sous_tension_2026-09-29.sql` en est à son **43ᵉ jour**.

### 5.3 KAN-3 (durée, « Terminé ») — **avis : NE PAS ROUVRIR**

La durée **a monté** (+177 s) ⇒ la règle demande un commentaire, il est posé :
chiffres, répartition par étape, **découplage calcul/attente** (cpu rend +76,8 s
sur +177, soit **43 % de calcul et 57 % d'attente** — les trois nuits
précédentes tranchaient nettement, celle-ci est **mixte** et je ne force pas la
lecture), et le fait que **81 % de la hausse est hors étapes**, dans un bloc
**non instrumenté**.
Mais : pente **−15 s/nuit**, marge **37,64 %** dans la bande des trois dernières
semaines, garde **non menacé**. ⇒ ⛔ **Pas de réouverture demandée**, et la
remontée du garde (`10-timeout-s3.conf`) **n'est ni lancée ni proposée** :
`proposition()` ne la formule pas, puisque le contrôle se tait.
ⓘ Rappel écrit dans le commentaire : la pente est le **25ᵉ centile des
différences** — elle ignore **par construction** les deux plus grosses hausses
de sa fenêtre. Elle n'a vu ni le +153 s du 01/10, ni le +336 s du 06/10, ni le
+83 s du 08/11, **ni le +177 s de cette nuit.**

### 5.4 `bw-regime-sensibilite` — **critère 0/2, rien posé**

Coût par ligne de `regime` : 11,559 → 10,948 (**recul**) → **10,895** (**recul**).
Le critère unique du 07/10 demande **deux hausses consécutives** ⇒ **non
rempli, et à zéro.** ⛔ **Aucun motif créé.**
ⓘ Et ce n'est pas un effet de volume : les lignes de `regime` **remontent**
(+2 257) pendant que le coût par ligne **baisse**.

## 6. Le verdict correctif par correctif — les trois du 07/10

1. ⚠️ **Webhook `--ipv4` : NI confirmé NI démenti cette nuit — faute d'occasion.**
   ⛔ **Aucun cri n'est parti** (`grep -c "push parti|push Discord"` sur tout le
   journal du jour → **0**), parce qu'**aucun ⛔ n'a appelé d'alerte** : le
   garde-fou R2 rend code 0 (§4) et la position n'a pas de front (§7.2).
   ⇒ **Je ne compte donc PAS une 8ᵉ confirmation.** L'absence de push est
   **attendue** ici, pas un symptôme. ✅ **Zéro `429` ntfy.**
   ⚠️ **Les `429` du journal viennent de l'API AROME**, pas de ntfy :
   `run-ingest-pi.sh` sur `aromepi/0025` à 07:41:55 — `429 (quota) — pause 20 s
   [essai 1/4]`, puis `307 requêtes, 1 × 429, 18 attentes de quota`. **Famille
   différente, même code HTTP** : un `grep 429` seul ne répond pas à la question.
2. ✅ **Garde-fou « un commentaire par jour et par motif » : il tient.**
   Le contrôle s'est tu **sans écrire de jeton** ; mes trois écritures sont
   passées par le canal délibéré, **qui ne touche pas au jeton du jour** ⇒ le
   canal automatique garde son garde-fou intact pour demain.
   ⛔ `controle_quotidien.sh` **non touché**, son `$ETAT` conservé.
3. ✅ **Rejeu de purge ≠ échec : CONFIRMÉ, par l'autre bout cette fois.**
   Cette nuit il n'y avait **ni avertissement ni rejeu** dans le bloc purge, et
   le contrôle s'est tu sur `bw-purge-57014` — **ce qui est le comportement
   juste.** ⓘ Le correctif est désormais vérifié dans ses **deux** cas :
   avertissement **puis** bilan (09/11) et **bilan seul** (ce matin).

## 7. Les autres points ouverts, relevés sans être refaits

### 7.1 ⚠️ Témoins du mélange : **sous 50 % pour la première fois** — mais le gain reste positif

```
⛔ témoins du mélange : sur 7294 balise-jours×échéance, le mélange fait 4.955 km/h
   contre 4.9973 pour le meilleur membre a priori (gain 0.8 %, mélange devant
   dans 47.8 % des cas) ; contre la moyenne UNIFORME, sur 1063 : 5.2627 vs
   5.3693 (gain 2.0 %)
```

| | 07/11 | 08/11 | 09/11 | **10/11** |
|---|---|---|---|---|
| gain vs meilleur membre a priori | +8,2 % | +4,7 % | +3,9 % | **+0,8 %** |
| mélange devant, part des cas | 57,1 % | 55,5 % | 52,7 % | **47,8 %** |
| gain vs moyenne UNIFORME | +4,8 % | +2,8 % | +4,4 % | **+2,0 %** |
| erreur du mélange (km/h) | 2,3586 | 2,2496 | 3,2254 | **4,9550** |

⇒ ⚠️ **Trois reculs de suite sur les deux mesures**, et la part « devant » passe
**sous 50 % pour la première fois de cette série**. ✅ **Mais les deux gains
restent POSITIFS** (+0,8 % et +2,0 %).
⇒ ⓘ **Compteur de passage sous la barre : je le mets à 1/3**, pas 0/3 — la part
« devant » est le critère qui a basculé, le gain ne l'est pas. **Rien créé.**
⚠️ **Et c'est le même piège que le 07/11 et le 09/11, en pire** : l'erreur
absolue du mélange **bondit de 54 %** (3,2254 → 4,9550 km/h) après un +43 % la
veille, soit **deux journées de plus en plus ventées** (`model_verif_event`
60 524 lignes). ⇒ **Les niveaux de ces quatre nuits ne sont PAS comparables ;
seuls les signes le sont.** Si la série confirme sur une journée calme,
**demander à Yann s'il veut un motif.**

### 7.2 Position : **14 divergentes (contre 13), 3 confirmées, aucun front ⇒ aucun cri**

```
⛔ position : 14 balise(s) divergent du gel (10 j lus), dont 3 CONFIRMÉE(S) (≥ 10 j)
```

| balise | écart | jours | signature |
|---|---|---|---|
| `pioupiou:367` | 6 764 m | 10 j | nœud 0,01 **et** profil 0,025 CHANGE — « Le relais » |
| `infoclimat:STATIC0491` | 1 159 m | 10 j | nœud 0,01 CHANGE |
| `mf:05170001` | 330 m | 10 j | nœud 0,01 CHANGE |

⇒ ✅ **Mêmes trois confirmées qu'hier, au mètre près** ⇒ **aucun front ⇒ aucun
cri** : **19ᵉ vérification du « à front, pas à état »**. ⓘ La question du 01/10
reste ouverte : **faut-il qu'il recrie** quand une balise reste confirmée onze
nuits de suite ?
ⓘ **Le détail du reste, et une observation qui corrige une intuition** :
- **Huit** à **6 j** (1562, 2338, 1473, 1544, 1636, 1476, 175, 1595) — les
  mêmes huit qu'hier à 5 j, **+1 j chacune**.
- **`pioupiou:308`** à **2 j** (inchangée).
- ⚠️ **`pioupiou:84` est RETOMBÉE de 2 j à 1 j**, et **`pioupiou:1334` (37 911 m)
  entre à 1 j**. ⇒ ⓘ **Le compteur de jours peut DESCENDRE** : une balise sort
  puis rentre. **Donc une balise à 6 j n'arrive pas mécaniquement à 10 j.**
⛔ **Je n'annonce AUCUNE échéance** : je me suis trompé deux fois là-dessus
(28/10 démenti le 30/10, 29/10 démenti le 07/11), et le recul de `pioupiou:84`
ce matin **montre le mécanisme exact** de ces deux erreurs. ⓘ C'est la première
fois que j'en vois la cause, et pas seulement l'effet.
- `pioupiou:367` reste confirmée ⇒ ⛔ **`position_l15_2026-11-02.sql` est
  toujours périmé**, et de toute façon **jamais joué** (§7.4).

### 7.3 ⛔ Recalcul indépendant : **5 écarts, tous `fcstagrume/`, pour la DEUXIÈME nuit — le critère que je m'étais fixé est REMPLI**

```
12 balise-jours comparés, 8 sous le seuil de 6 h
⚠️ 5 ÉCART(S) — le recalcul indépendant ne retrouve pas la base :
  fcstagrume/infoclimat:000S0     agrume_pi +6h  — ici None, base 5.7499 : 0 h appariées
  fcstagrume/mf:34269001          agrume_pi +6h  — ici None, base 4.1288 : 0 h appariées
  fcstagrume/windsmobi:ffvl-5052  agrume    +6h  — ici None, base 11.9393 : 0 h appariées
  fcstagrume/infoclimat:000IA     agrume_pi +48h — ici None, base 4.36   : 0 h appariées
  fcstagrume/pioupiou:1344        agrume   +24h  — ici None, base 1.8438 : 1 h appariée
```

| | 09/11 | **10/11** |
|---|---|---|
| balise-jours comparés | 13 | 12 |
| sous le seuil de 6 h | 7 | 8 |
| écarts | **5** | **5** |
| famille | **toutes `fcstagrume/`** | **toutes `fcstagrume/`** |
| motif | moins de 6 h appariées ici, la base porte une ligne | **identique** |

⇒ ⛔ **La note du 09/11 posait le critère : « si demain le compte et la famille
sont les mêmes, c'est un seuil d'appariement qui diverge entre `run.sh` et le
recalcul, et ça mérite son propre motif. » IL EST REMPLI.** Le compte (5), la
famille (`fcstagrume/` à 100 %) et le motif sont identiques, sur un tirage
**aléatoire** de 20 strates à graine différente — donc **ce n'est pas le même
échantillon qui se répète** : ce sont d'autres balises, du même préfixe, avec le
même symptôme. **C'est ce qui rend la répétition significative.**
⇒ ⬆️ **Je ne crée RIEN seul.** Question à Yann : **créer un motif
`bw-appariement-fcstagrume` ?** ⚠️ **Deux nuits ne font pas une pente non plus** :
c'est pour cela que je demande au lieu de poser. Mais ici le critère était écrit
**à l'avance** et par moi — il faut donc le porter, pas l'oublier.
ⓘ **Ordre de grandeur, sans sur-interpréter** : 5 écarts sur 12 comparés, mais
les 5 sont parmi les **8 sous le seuil de 6 h** — le symptôme n'est pas « la
base est fausse », c'est « le recalcul refuse une case que `run.sh` a acceptée ».

### 7.4 ⛔ Toujours **9** balises nées sous leur identifiant — 5ᵉ confirmation

```
ⓘ 9 balise(s) née(s) sous leur identifiant (`notee_depuis`, lot L15-bis) :
  pioupiou:1363, 1375, 1414, 1495, 1531, 1595, 2005, 2139, 2189 (toutes 2026-09-25)
```

⇒ ⛔ **L'annonce du 02/11 (9 → 12 au 05/11) n'a jamais eu lieu**, et c'est la
**cinquième** voie qui le confirme : le `.sql` **n'a jamais été joué**.

### 7.5 ⛔ `BW_DISCORD_WEBHOOK_URL` : toujours absente, **mesurée ce matin**

`grep -c BW_DISCORD_WEBHOOK_URL ~/.balise-watch-alertes.env` → **0**.
Les **25** variables présentes ont été lues **par leur nom seul** (`cut -d= -f1`),
**aucune valeur** : `BW_WEBHOOK_URL`, `BW_ALERTE_MAIL`, `BW_JIRA_*`,
`BW_*_PING_URL` (×13), `BW_MODEL_SELF_TEST_BLOQUANT`, `BW_PING_OK_URL`.
⇒ **Le second canal du téléphone reste muet**, et `installer-webhook-discord.sh`
est toujours sur le Mac, à lancer par Yann. ⓘ **60ᵉ jour.**

### 7.6 Dette inchangée, relevée sans y toucher

- ⛔ **Sept `.sql` en attente**, tous encore là, tous non suivis par git
  (`git status` relu) : `diagnostic_base_sous_tension_2026-09-29.sql` (**43ᵉ
  jour**) · `position_l15_2026-11-02.sql` · `suspension_l15_2026-11-02.sql` ·
  `naissance_l15bis_2026-09-22.sql` · `rattrapage_purge_2026-09-29.sql` ·
  `schema_l15bis_notee_depuis_2026-09-22.sql` · `suspension_l15_2026-09-22.sql`.
- ⛔ **Quatre miroirs git en souffrance**, vérifiés un par un et **NON arrangés** :
  `24/10` **absent** · `26/10` **présent mais NON suivi** · `01/11` **absent** ·
  `04/11` **absent**. ✅ `07/11`, `08/11` et `09/11` **présents et suivis**.
  ⓘ **Rien n'a été fabriqué après coup.**
- `mutations_memoire` : **3 mutations non vues** (2, 5, 13), dette antérieure,
  inchangée.
- **Duels, inchangés au millième** : `agrume ↔ agrume_pi (+6 h)` médiane
  **+0,010**, IC95 [+0,005 ; +0,016] → `b_better` ;
  `agrume ↔ meteofrance_arome_france_hd` médiane **−0,001**, IC95
  [−0,002 ; +0,002] → **`not_separable`** ;
  `arome_r2 ↔ arome_hd` médiane +0,083 → `b_better` ;
  `agrume_pi ↔ bw_mix` médiane +0,386 (+6 h) et +0,440 (+24 h) → `b_better`.
  ⓘ Le **cumul reste TRONQUÉ par la rétention de 30 j** sur les quatre duels :
  le « depuis la naissance de la paire » n'est plus vrai, et le journal le dit
  lui-même à chaque ligne.
- ✅ **Self-test vert** : les quatre contrôles (a) à 1,0, la prévision permutée
  à `rms(perm)/rms(clim) = 2,198` dans [1,0 ; 3,0] et `beats_persist` faux.

## 8. ✅ L'horaire de la routine : à l'heure, troisième matin de suite

Programmée pour le **10/11 à 07:09:05 UTC**, tirée le **10/11 à 07:16:52 UTC** :
✅ **+7 min 47 s.**

```
29/10 ⛔ SAUTÉ · 30/10 +0 h 00 · 31/10 +0 h 00 · 01/11 +0 h 55 · 02/11 +0 h 19
03/11 ✅ +0 h 01 · 04/11 ⚠️ +4 h 42 · 05/11 ⛔ SAUTÉ · 06/11 ⛔ SAUTÉ
07/11 ⚠️ +3 h 49 · 08/11 ✅ +0 h 03 · 09/11 ✅ +0 h 05 · 10/11 ✅ +0 h 08
```

⇒ ✅ **Trois tirs nets d'affilée, les premiers depuis le 03/11.** ⓘ Le VPS, lui,
est à l'heure (`debut` 04:59:41, `lancement=timer`) et son `debut` dérive de
**+26 s par nuit** depuis le 07/11 (04:58:23 → 04:58:49 → 04:59:15 → 04:59:41) :
⚠️ régulier, minuscule, **noté sans être interprété**.

## 9. ⬆️ Décisions en attente de Yann — par ordre d'urgence

1. ⛔ **Ne pas croire le vert de R2** (§4). Le compte est à **99,9 %** et le
   garde-fou à **code 0** uniquement parce qu'`agrume/grille` est dans son
   **troisième creux d'audit**. Au niveau habituel du préfixe, le compte est à
   **≈ 108,1 %**. ⇒ Geste attendu, inchangé : **décider d'une rétention sur
   `agrume/pi`** (+48 objets/nuit, **28 nuits** sans un recul), ou accepter la
   facture. ⚠️ **Et traiter le creux lui-même comme un défaut de l'audit** : la
   nuit où il se trompe est la nuit où il se tait.
2. ⛔ **Trancher la lecture du compteur KAN-5** (§3.3). **Neuvième** fois.
   Une phrase suffit et vaut pour toutes les nuits : « un 57014 de **SONDE**
   casse-t-il le compteur, ou seulement un 57014 de **TRANCHE** ? »
   ⓘ Le §3.2 **réduit le périmètre de la question** : `n_57014` du registre n'y
   entre pas, il ne mesure pas la purge.
3. ⬆️ **Créer un motif pour les écarts du recalcul indépendant ?** (§7.3) Le
   critère que je m'étais fixé **la veille** est rempli : 5 écarts, tous
   `fcstagrume/`, deux nuits de suite, sur des tirages différents.
   **Je ne crée rien seul.**
4. ⛔ **La ligne en tuple** (KAN-4) : **cinquante jours** sans rien déployer côté
   mémoire depuis `af25efb`. La mesure `tuple` vs `namedtuple` à la sonde est le
   préalable, et elle n'a **jamais** été jouée.
5. ⬆️ **Jalons de temps dans `run.sh`** pour le bloc hors étapes (§2) :
   **81 % de la hausse y est**, **quatrième fois en sept jours**, et sans eux
   l'hypothèse de charge du §2.1 n'est pas vérifiable. C'est une écriture.
6. ⬆️ **Jouer `diagnostic_base_sous_tension_2026-09-29.sql`** (**43ᵉ jour**,
   lecture seule, 9 blocs, SQL Editor).
7. ⬆️ **Position** : trancher `pioupiou:367`, `infoclimat:STATIC0491` et
   `mf:05170001`, puis poser `position_suspecte` / `position_note` par `.sql`.
   ⚠️ **`position_l15_2026-11-02.sql` est périmé et n'a jamais été joué** — à
   refaire, pas à rejouer.
8. ⬆️ **`installer-webhook-discord.sh`** : **60ᵉ jour** sans second canal.
9. ⓘ **Question de fond, ouverte depuis le 01/10** : le cri de position doit-il
   **recrier** quand une balise reste confirmée onze nuits de suite ?
10. ⓘ **À surveiller demain, sans rien en conclure** : les **témoins du mélange**
    (§7.1, 1/3, et il faudra une journée calme pour que le niveau parle), et le
    jalon du **rejeu d'archive** après quatre hausses (§2.2a).

⇒ ⓘ Les points du §9 de la note du 09/11 qui ne sont pas repris ci-dessus
restent valables **tels quels**. ✅ **Aucun point du 09/11 n'est démenti par ce
run** — c'est la première fois depuis le 07/11. Deux sont **confirmés** : la
prédiction sur le creux d'`agrume/grille` (§4) et le critère du recalcul
indépendant (§7.3).

## 10. Respect des règles

✅ **VPS en LECTURE SEULE, pleine et entière.** Aucun `systemctl start/restart/
daemon-reload`, aucun `enable`, aucun SQL joué, aucun `rsync`, rien écrit dans
`~/balise-watch` ni dans `/etc`. Seules écritures : **les trois commentaires
Jira**. ⓘ Les deux scripts Jira sont passés par `bash -s` (**aucun fichier
déposé sur le VPS**) ; les seuls fichiers temporaires sont ceux que
`bw_jira_http` crée lui-même dans un `mktemp -d` en 700, effacés par la
fonction. La levée nominative du 07/10 n'a **pas** été invoquée.
✅ **Aucun secret lu par valeur.** `~/.balise-watch-alertes.env` est **sourcé**
(`set -a; . …; set +a`), jamais lu ; les seuls relevés dessus sont un `grep -c`
sur un **nom** et un `cut -d= -f1` qui ne rend que des **noms**. `bw_jira.sh`
passe par `curl -K -`, jamais `-u`.
✅ **Aucun ticket créé, fermé, rouvert ni transité.** Trois commentaires, +1
chacun, **statuts identiques avant et après** (GET des deux côtés).
✅ **Aucun motif neuf créé** : `bw-regime-sensibilite` à **0/2**, témoins du
mélange à **1/3**, et le motif candidat du §7.3 est **posé en question, pas
créé**.
✅ `10-timeout-s3.conf` **non touché** ; remontée du garde **non lancée et non
proposée** (le contrôle se tait, `proposition()` ne la formule pas).
✅ `controle_quotidien.sh` **non touché**, son `$ETAT` conservé.
✅ **Desktop Commander exclusivement** pour fichiers et shell, du début à la fin.
✅ **Lire avant d'écrire** : `git log --since=midnight` dans les **deux** dépôts
(aucun commit) ; `project_read` du 10/11 (**absent ⇒ création**) et du 09/11
(**lu en entier**) ; `README.md` relu ; **note en section horodatée**.
⛔ **Aucun `git push`.** Commit local depuis la **racine** du dépôt serveur.
✅ **Yann averti par notification** avec l'artefact R2, les chiffres et les trois
questions.

## 11. ⓘ Outillage — ce que ce matin apprend

1. ⛔ **Piège n°3, neuf** : le shell de Desktop Commander est **zsh**, qui **ne
   découpe pas** les variables sur les espaces. `S="ssh -o …"; $S 'cmd'` rend
   **rc=127** sans message explicite — trois lectures perdues avant de
   comprendre. ⇒ **Écrire `ssh` en entier à chaque appel.**
2. ✅ **Lire vingt-cinq nuits avant d'écrire une phrase de tendance.** Ce matin
   cela a **empêché trois fausses annonces** : « marge la plus basse »
   (34,57 % le 23/10 est plus bas), « record de swap » (2 541,0 le 24/10), et
   « troisième incident mémoire inédit » (2 944 Mo le 22/10). ⇒ ⓘ Les quatre
   dernières nuits **ne suffisent pas** : c'est la bande de vingt-cinq nuits qui
   dit si un chiffre est remarquable.
3. ⛔ **Un indicateur dont on ne sait pas ce qu'il compte est pire qu'un
   indicateur absent** — la leçon du 09/11, rejouée sur un autre objet.
   `n_57014 = 1` cette nuit avec un bloc purge **propre** : il compte **toute la
   nuit**. ⇒ ⓘ Le symétrique de la leçon d'hier (un test qui ne mesure pas ce
   qu'il prétend) : **vérifier la provenance d'un compteur avant de le lire**,
   ici par un `grep 57014` sur le journal entier, pas sur le seul bloc purge.
4. ✅ **Une prédiction écrite la veille s'est vérifiée** (§4, le creux
   d'`agrume/grille` et le silence du garde-fou). ⇒ ⓘ C'est la contrepartie des
   corrections du 09/11 : **écrire la prédiction, même quand on annonce qu'elle
   est incertaine, est ce qui permet de la compter.** Même mécanique au §7.3.
5. ⚠️ **Une absence de push n'est pas une panne de push.** Zéro cri cette nuit
   parce qu'**aucun ⛔ n'appelait d'alerte** ⇒ **ni confirmation ni démenti** du
   correctif `--ipv4`. ⓘ Le compter comme une 8ᵉ confirmation aurait été faux ;
   le compter comme une régression aussi.
6. ⓘ **Le compteur de jours de position peut DESCENDRE** (`pioupiou:84`, 2 j → 1 j,
   §7.2). ⇒ C'est **la cause mécanique** de mes deux échéances démenties
   (28/10, 29/10). Première fois que je la vois, et pas seulement son effet.
7. ⓘ Les sorties brutes de ce run sont sur le Mac dans
   `/Users/yann/bw-run-10-11/` (`etape0.txt`, `ssh-diag.txt`, `hist.json`,
   `hist25.json`, `ctrl.txt`, `ctrlv.txt`, `timer.txt`, `score-full.txt`,
   `purge.txt`, `all57014.txt`, `milieu.txt`, `queue.txt`, `r2-fenetre.txt`,
   `gardefou-r2.txt`, `envnames.txt`, `local.txt`, `jira-avant.txt`,
   `jira-post.txt`, `jira-apres.txt`) — **relisibles telles quelles**, et
   `get-jira.sh` / `comm-jira.sh` sont **rejouables**.
