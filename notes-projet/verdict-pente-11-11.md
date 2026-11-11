# Verdict de pente du 11/11/2026 — ✅ **La prédiction du 10/11 se vérifie AU MO ET À L'OBJET PRÈS** : `agrume/grille` revient à 5,323 Go / 766 objets, le compte à **108,3 %**, le garde-fou crie. ✅ **Et c'est l'occasion qui manquait : `--ipv4` CONFIRMÉ, push parti HTTP 200.** ⛔ **Durée +93 s, 122 % hors étapes.** ⛔ **Une annonce du 10/11 RETIRÉE** (le coût par ligne rejouée ne sortait pas de sa bande). ⚠️ **Routine en retard de 4 h 16.**

## 12:25–12:45 (Paris, CET) — routine Balise Watch, run complet

**Étape 0 : faite en entier, avant toute autre chose.**

- `git log --oneline --since=midnight` dans **les deux** dépôts. ⚠️ **Un commit
  du jour existe** dans le dépôt serveur — mais il n'est **pas** de cette
  routine : `08a9b45`, le 11/11 à 11:16:54 UTC, « arpege-isobars : les runs #408
  et #409 tombaient sur botocore 1.44.0 — boto3 rejoint l'unique pip install, et
  un pip check avant tout téléchargement », soit `.github/workflows/
  arpege-isobars.yml` (+38) et `BUGS.md` (+43). **Autre sujet, autre chaîne : je
  n'y touche pas et je ne le reprends pas.** Dépôt principal : rien du jour,
  dernier commit `cc10b42` du 01/11.
- `project_read claude/verdict-pente-11-11.md` : **absent** ⇒ cette note est une
  **création**, pas une fusion. `notes-projet/verdict-pente-11-11.md` : absent
  également.
- `project_read claude/verdict-pente-10-11.md` : ✅ **lu en entier** — c'est lui
  qui fixe les séries à vérifier, les deux prédictions à compter et l'annonce à
  démentir.
- `notes-projet/README.md` relu : les quatre règles.
- ⓘ **Confirmation indépendante par Jira** : avant écriture, les trois tickets
  portaient **41 / 55 / 38** commentaires, exactement les chiffres de fin du
  10/11 ⇒ **aucune autre session n'avait écrit sur les tickets ce matin.**

## 1. ✅ Outillage : les trois pièges connus, et aucun n'a mordu

Les deux lignes d'ouverture SSH du 09/11, à **chaque** appel de shell :

```
export SSH_AUTH_SOCK="$(launchctl getenv SSH_AUTH_SOCK)"
ssh-add --apple-load-keychain >/dev/null 2>&1
```

`ssh-add -l` → `256 SHA256:d0C/G0LX… balise-watch-vps (ED25519)`, rc=0.
✅ **Piège n°3 du 10/11 respecté** : `ssh` écrit **en entier** à chaque appel,
jamais via une variable (zsh ne découpe pas sur les espaces → rc=127 muet).
✅ Les deux scripts Jira sont passés par `bash -s` depuis le Mac ⇒ **aucun
fichier déposé sur le VPS**, et ils contournent la liste noire du shell de
Desktop Commander puisqu'ils sont écrits par son outil d'écriture de fichier.

## 2. La nuit, chiffre par chiffre

`lancement=timer`, `result=success`, `exec_status=0` ⇒ relevé **comparable**, et
le contrôle le compte (**104 relevés, 83 comparables**, contre 103/82 hier).

| | 08/11 | 09/11 | 10/11 | **11/11** |
|---|---|---|---|---|
| durée (s) | 4 889 | 4 874 | 5 051 | **5 144** (+93) |
| cpu (s) | 3 970,2 | 3 921,8 | 3 998,6 | **3 936,0** (−62,6) |
| marge / garde 8 100 s | 39,64 % | 39,83 % | 37,64 % | **36,49 %** |
| jalon max (Mo) | 3 352 | 3 366 | 3 379 | **3 376** (−3) |
| jalon − seuil 2 800 | +552 | +566 | +579 | **+576** |
| swap au pic (Mo) | 2 087,5 | 2 100,5 | 2 319,4 | **2 147,8** (−171,6) |
| pages sorties | 2 244 601 | 2 118 377 | 2 239 155 | **2 548 710** (+309 555) |
| coût / ligne rejouée (o) | 1 722,7 | 1 731,2 | 1 739,1 | **1 738,8** (−0,3) |
| coût / ligne `regime` (ms) | 11,559 | 10,948 | 10,895 | **10,939** (+0,044) |
| `n_57014` | 0 | 1 | 1 | **5** (§3.2) |
| lignes effacées (purge) | 150 712 | 151 649 | 154 362 | **154 706** |
| balise-jours rejoués | 2 040 335 | 2 038 813 | 2 037 288 | **2 035 925** |
| lignes `regime` | 141 261 | 141 805 | 144 062 | **144 539** |

Répartition du temps (les quatre étapes instrumentées contre le reste) :

| | 10/11 | **11/11** |
|---|---|---|
| glissant (s) | 974,7 | 938,7 (−36,0) |
| `regime` (s) | 1 569,6 | 1 581,1 (+11,5) |
| rejeu (s) | 74,7 | 87,8 (+13,1) |
| stabilité (s) | 315,2 | 306,2 (−9,0) |
| **somme des 4 étapes** | 2 934,2 | **2 913,8** (−20,4) |
| **bloc hors étapes** | 2 116,8 | **2 230,2** (+113,4) |

⇒ ⛔ **Les quatre étapes instrumentées BAISSENT de 20,4 s pendant que la durée
monte de 93 s.** La totalité de la hausse — **122 %** — est dans le bloc **non
instrumenté** (publication, Murphy, événements, pression, duels, purge).
**Cinquième fois en huit jours.** ⇒ ⬆️ **La demande de jalons de temps dans
`run.sh` se repose, inchangée** : c'est une écriture, donc c'est Yann.

⇒ ✅ **La signature est NETTE cette nuit** : la durée monte (+93 s) pendant que
le `cpu` **baisse** (−62,6 s) ⇒ c'est de l'**ATTENTE**, pas du calcul. ⓘ Plus
propre qu'hier, où le cpu rendait +76,8 s sur +177 (43 % / 57 %) et où j'avais
refusé de forcer la lecture.

### 2.1 Ce que ces chiffres ne disent PAS — vingt-six nuits relues avant d'écrire une phrase de tendance

- ⚠️ **5 144 s n'est PAS un record de durée** : **5 300 s** le 23/10, 5 256 le
  20/10, 5 252 le 25/10, 5 242 le 22/10, 5 172 le 18/10 sont plus hauts. C'est la
  plus haute **depuis le 25/10**.
- ⚠️ **36,49 % n'est PAS un record de marge basse** : **34,57 %** le 23/10,
  35,11 % le 20/10, 35,16 % le 25/10, 35,28 % le 22/10, 36,15 % le 18/10 sont
  plus bas. Le garde de 8 100 s n'est pas menacé.
- ⚠️ **2 230,2 s hors étapes n'est PAS un record** non plus : **2 361,5 s** le
  23/10 est plus haut. C'est la **deuxième** valeur la plus haute des vingt-six.
- ⚠️ **2 548 710 pages sorties n'est PAS un record** : 2 756 422 le 20/10,
  2 737 964 le 24/10, 2 593 421 le 07/11 sont plus hauts. ⓘ **Mais la
  divergence est réelle et je la note sans l'interpréter** : les pages sorties
  bondissent de +309 555 pendant que le swap **au pic** recule de −171,6 Mo.
- ⚠️ **3 376 Mo n'est PAS une pente** : la bande **3 151–3 452 Mo est inchangée
  depuis vingt-six nuits**. Et le jalon **recule** de 3 Mo après deux hausses.

### 2.2 ⛔ UNE ANNONCE DU 10/11 EST RETIRÉE — mesurée fausse ce matin

La note du 10/11 (§2.1, dernier point) écrivait : « le coût par ligne rejouée
touche **1 739,1 o**, soit **8 o au-dessus** du haut de la bande des onze nuits
précédentes (**1 686–1 731**) ». ⛔ **C'est FAUX.** Relecture du registre :

| nuit | coût / ligne rejouée (o) |
|---|---|
| **04/11** | **1 744,4** ← le plus haut |
| 29/10 | 1 744,3 |
| 25/10 | 1 743,9 |
| 28/10 | 1 740,7 |
| 10/11 | 1 739,1 |
| **11/11** | **1 738,8** |

Le **04/11 tombe DANS la fenêtre de onze nuits** que la note invoquait, et il
porte **1 744,4 o**. Le haut de la bande est donc **1 744,4**, pas 1 731 — et
**ni 1 739,1 ni les 1 738,8 de cette nuit n'en sortent.**
⇒ ⓘ **L'annonce est retirée, pas masquée**, et elle est retirée **dans le
commentaire KAN-4** comme ici. C'est la règle : une annonce de la veille se
vérifie avant d'être reprise, et se corrige explicitement si elle est démentie.
⇒ ⚠️ **Cause de l'erreur** : la bande avait été calculée sur une liste de
valeurs, pas recalculée sur le registre. **Onze nuits lues de mémoire valent
moins que onze nuits relues.**

### 2.3 ✅ Et une annonce du 10/11 qui est, elle, DÉMENTIE DANS LE BON SENS

La note du 10/11 (§2.2a) relevait le jalon du **rejeu d'archive** en **quatre
hausses de suite** (2 935 → 2 946 → 2 953 → **2 981 Mo**) et demandait de le
surveiller, tout en écrivant que « quatre points ne font pas une pente ».
⇒ ✅ **Il RECULE : 2 962 Mo.** La prudence était la bonne lecture, et la
cinquième nuit la confirme.
ⓘ Le troisième incident, `le score par régime` à **2 932 Mo**, est la **deuxième**
valeur la plus haute de la série (**2 944 Mo le 22/10** reste le plus haut),
devant 2 914 (04/11) et 2 901 (25/10) : **pas un fait nouveau.**

## 3. Le bloc purge — la purge ABOUTIT, et deux avertissements qu'il ne faut pas confondre

### 3.1 Le bloc, mot pour mot, en entier

```
⚠️ purge model_verif_daily : HTTP 500 — {"code":"57014", "message":"canceling statement due to statement timeout"}
⚠️ purge model_score_zone : plus vieille journée illisible (essai 1/2 : {"code":"57014", …})
→ purge model_score_zone : 154706 ligne(s) effacée(s) en 8 tranche(s)
ⓘ purge model_character : rien avant le 2027-02-04 (première écriture 2026-08-08, rétention 180 j) — aucune requête lancée.
```

Lecture, grille du 28/09 et du 06/10, **sans l'élargir** :

- ✅ **AUCUNE tranche en échec** : pas une ligne portant
  `?as_of=eq.J&regime=eq.R` — compte vérifié à **0** sur tout le journal.
- ✅ **8 tranches, 154 706 lignes, nombre lisible** ⇒ **la purge de
  `model_score_zone` a ABOUTI.**
- ⚠️ **La SONDE a bronché** (« plus vieille journée illisible », essai 1/2).
  `des lignes RESTENT` est absente — **mais cette nuit cette absence est MOINS
  concluante**, comme le 09/11 et contrairement au 10/11 où la sonde était
  muette. ⇒ **Je n'en conclus rien.**
- ⚠️ **154 706 lignes contre 154 362** : le volume suit la journée purgée. **Je
  ne le lis pas comme un signal.**

### 3.2 ⛔ `purge model_verif_daily` n'est PAS un motif neuf — et `n_57014 = 5` n'est PAS un record

Deux réflexes à retenir, tous deux vérifiés **avant** d'écrire :

a) ⛔ **`⚠️ purge model_verif_daily : HTTP 500` a QUATRE occurrences au
   registre** : **14/10, 16/10, 25/10** et cette nuit. ⇒ **Je ne l'annonce donc
   pas comme un fait nouveau**, alors que c'était ma première lecture. ⓘ Et ce
   n'est **pas la même table** que celle que suit KAN-5 : c'est la purge de
   `model_verif_daily`, pas la purge par tranches de `model_score_zone`.
   ⇒ ⬆️ **Question posée à Yann** sur le ticket : cette table entre-t-elle dans
   le périmètre de KAN-5, ou mérite-t-elle son propre suivi ?
b) ⛔ **`n_57014 = 5` est le plus haut depuis septembre, mais PAS un record** :
   le registre porte **13 le 19/09**, 11 le 16/09, 10 le 06/09, 9 le 14/09.
   ⓘ Et, conformément à la **correction de méthode du 10/11**, ce compteur
   compte les 57014 de **TOUTE la nuit** : les cinq sont **trois** timeouts sur
   `rpc/bw_character_avance` (05:22:31, 05:23:03, 05:23:42) **plus** les deux du
   bloc purge. ✅ **Les trois ont été RATTRAPÉS** :
   `→ model_character : 399171 accumulateurs avancés sur 399171 envoyés`,
   soit **100 %**. ⇒ **Il ne faut pas lire `n_57014 = 5` comme cinq échecs de
   purge** — et c'est la deuxième nuit où cette correction sert.

### 3.3 Où en est le compteur KAN-5 — deux lectures, toujours pas tranchées

1. **Critère ÉCRIT** (« trois nuits consécutives **sans 57014 dans le bloc
   purge** ») : le bloc en porte **DEUX** cette nuit ⇒ **remise à zéro, 0 / 3.**
2. **Critère par NATURE** (aucune tranche perdue, purge aboutie, nombre
   lisible) : **seizième nuit consécutive**, et le ticket serait **fermable
   depuis douze jours**.

⇒ ⬆️ **Question posée à Yann pour la DIXIÈME fois**, sur le ticket. **Rien n'est
fermé ni transité en attendant.**
ⓘ `diagnostic_base_sous_tension_2026-09-29.sql` en est à son **44ᵉ jour**.

## 4. ✅ LE FAIT DU MATIN : la prédiction du 10/11 se vérifie AU MO ET À L'OBJET PRÈS

```
│ total compte   :   10.829 Go   ( 108.3 % du palier 10 Go)
│ objets         :     8037
│ pente mesurée  :   +0.002 Go/mois  (somme des préfixes, 25e centile des différences)
│ palier atteint dans :   0 j (~2026-11-11)
│ balise-watch-grids:agrume/grille   5.323 Go    766 objets   -0.004 Go/mois
│ balise-watch-grids:agrume/pi       1.980 Go   4483 objets   +0.582 Go/mois
⚠️  palier gratuit DÉPASSÉ : 10.83 Go sur 10 Go — R2 facture déjà
2026-11-11T05:24:38Z run garde-fou-r2 en ÉCHEC (code 1, 4s) — 1 consécutif(s)
```

| | 08/11 | 09/11 | 10/11 | **11/11** |
|---|---|---|---|---|
| total compte | 10,693 Go (106,9 %) | 10,701 Go (107,0 %) | 9,988 Go (99,9 %) | **10,829 Go (108,3 %)** |
| objets | 7 845 | 7 911 | 7 861 | **8 037** |
| `agrume/grille` | 5,323 Go / 766 obj. | 5,323 Go / 766 obj. | 4,500 Go / 652 obj. | **5,323 Go / 766 obj.** |
| `agrume/pi` | 1,938 Go / 4 387 | 1,938 Go / 4 387 | 1,959 Go / 4 435 | **1,980 Go / 4 483** |
| verdict garde-fou | ⚠️ DÉPASSÉ, code 1 | ⚠️ DÉPASSÉ, code 1 | ✅ OK, code 0 | **⚠️ DÉPASSÉ, code 1** |

⇒ ✅ **`agrume/grille` revient à 5,323 Go et 766 objets : le chiffre EXACT des
08 et 09/11, au Mo et à l'objet près.** C'était mot pour mot la prédiction du
10/11 (« c'est exactement le motif du 27/10 et du 05/11, où le préfixe revenait
au Mo et à l'objet près la nuit suivante »). **Troisième occurrence du creux,
troisième retour à l'identique.**
⇒ ✅ **La prédiction chiffrée tombe juste à 0,2 point** : la note du 10/11
annonçait **≈ 108,1 %** au niveau habituel du préfixe ; le compte rend
**108,3 %**. ⓘ L'écart de 0,018 Go s'explique entièrement par la croissance
d'`agrume/pi` dans l'intervalle (1,959 → 1,980 Go).
⇒ ⛔ **Donc le vert du 10/11 ne valait RIEN, et c'est démontré, plus supposé.**
Le creux d'audit est bien un **défaut de l'audit** : la nuit où il se trompe est
la nuit où il se tait. **Il faudra s'en souvenir au prochain creux** — ce sera
le quatrième.
⇒ ⓘ **Et le bloc « produits indexés » le confirme une seconde fois** : il dit
`agrume/grille/ 766 présentes / 766 réclamées ✓` cette nuit, et disait
`652 / 652 ✓` hier. **Le même `✓` pour deux états différents** ⇒ un `✓` ne prouve
rien sur la complétude réelle. ⓘ Les quatre sous-préfixes sont de nouveau
listés, `agrume/piaf/` compris (il avait disparu du bloc le 10/11) : **noté, pas
interprété.**

### 4.1 `agrume/pi` : **28ᵉ nuit sans un seul recul**

**1,959 → 1,980 Go**, **4 435 → 4 483 objets**, soit **+48 objets** — le même
pas que les nuits précédentes, à **+0,582 Go/mois**.
ⓘ Compteur conforme à la rectification `f5f308f` : le 10/11 était la **27ᵉ**,
donc cette nuit est la **28ᵉ**.
⇒ ⛔ **L'illusion de la pente est intacte, et pire qu'hier** : **+0,002 Go/mois
affiché** au total pendant qu'`agrume/pi` seul fait **+0,582**. Le 25ᵉ centile
des différences, encore lui. ⇒ **Geste attendu de Yann inchangé** : décider
d'une rétention sur `agrume/pi`, ou accepter la facture. ⓘ Le garde-fou dit
lui-même `palier atteint dans 0 j`.

## 5. ✅ Le verdict correctif par correctif — les trois du 07/10

1. ✅ **Webhook `--ipv4` : CONFIRMÉ, et c'est l'occasion qui manquait hier.**
   Le garde-fou R2 rend **code 1** ⇒ une alerte part ⇒ le journal porte :
   ```
   2026-11-11T05:24:39Z ⓘ push parti (webhook, HTTP 200)
   ```
   ⇒ ✅ **HTTP 200, un seul cri, aucun `429` de ntfy.** ⓘ C'est exactement ce
   que le 10/11 ne pouvait **pas** compter (« aucun ⛔ n'appelait d'alerte ⇒ ni
   confirmation ni démenti ») : **la nuit d'après fournit l'occasion, et le
   correctif tient.** ⇒ **Le compte des confirmations repart, sur une occasion
   réelle.**
   ⚠️ **Et aucun `429` de l'API AROME cette nuit non plus** — contrairement au
   10/11, où les `429` du journal venaient d'`aromepi/0025` et pas de ntfy. ⓘ Le
   piège du `grep 429` seul reste valable : **deux familles, même code HTTP.**
2. ✅ **Garde-fou « un commentaire par jour et par motif » : il tient.**
   Le contrôle s'est tu **sans écrire de jeton** ; mes trois écritures sont
   passées par le canal **délibéré**, qui **ne touche pas au jeton du jour** ⇒ le
   canal automatique garde son garde-fou intact pour demain.
   ⛔ `controle_quotidien.sh` **non touché**, son `$ETAT` conservé.
3. ✅ **Rejeu de purge ≠ échec : CONFIRMÉ dans un TROISIÈME cas de figure.**
   Cette nuit le bloc porte **deux avertissements de natures différentes** (une
   autre table, et la sonde) **puis** un bilan chiffré lisible — et le contrôle
   s'est **tu** sur `bw-purge-57014`. ✅ **C'est le comportement juste.**
   ⓘ Le correctif est désormais vérifié dans ses **trois** cas : avertissement
   **puis** bilan (09/11), **bilan seul** (10/11), **deux avertissements
   hétérogènes puis bilan** (ce matin).

## 6. Ce qui a été fait sur les tickets — et pourquoi par ce canal

⚠️ **Le contrôle de 07:30 s'est TU**, pour le **troisième** matin de suite :

```
2026-11-11T07:30:26+01:00 … rien à dire : pente plate ou négative, ou échéance hors horizon
ⓘ 104 relevé(s), 83 comparable(s) ; durée : 10 points, pente -15 s/nuit ;
  mémoire : 10 points, pente -5 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
```

⚠️ **La pente mémoire passe de −17 à −5 Mo/nuit** ; la pente durée reste à
**−15 s/nuit**, inchangée malgré le +93 s. ⓘ Mécanique, pas mystérieux : le 25ᵉ
centile ignore par construction les deux plus grosses hausses de sa fenêtre.
✅ Timer armé pour demain : `Thu 2026-11-12 07:30:29 CET`.

**Canal retenu : `bw_jira_commenter` (délibéré), sur les trois tickets.**
Justification redite : le contrôle ne parlant de rien, `bw_jira_signaler` aurait
été **libre** pour KAN-4 et KAN-5 — mais il **cherche par étiquette et CRÉE si
rien ne répond**, et créer un ticket sans l'accord de Yann est interdit.
`bw_jira_commenter` prend la **clé**, ne cherche rien, ne crée rien, ne touche
pas au jeton du jour. Pour KAN-3 (« Terminé ») il n'y a de toute façon pas
d'autre voie, `bw_jira_chercher` filtrant sur `statusCategory != Done`.
⇒ **Trois commentaires délibérés, assumés.**

**GET avant ET après écriture :**

| ticket | étiquette | statut avant | statut après | comm. avant | comm. après |
|---|---|---|---|---|---|
| KAN-3 | `bw-pente-duree` | Terminé / `done` | **Terminé / `done`** | 41 | **42** |
| KAN-4 | `bw-pente-memoire` | À faire / `new` | **À faire / `new`** | 55 | **56** |
| KAN-5 | `bw-purge-57014` | À faire / `new` | **À faire / `new`** | 38 | **39** |

✅ **+1 chacun, aucun changement d'état, aucun ticket créé.**

### 6.1 KAN-4 (mémoire) — **reste ouvert, 1 condition sur 3**

- le jalon **n'est pas mesurément retombé** : **+576 Mo** au-dessus du seuil,
  26ᵉ nuit dans la même bande ;
- le swap au pic **n'est pas ≈ 0** : **2 147,8 Mo** ;
- ✅ seul le **silence du contrôle** est acquis (pente **−5 Mo/nuit**).
⇒ **Pas de fermeture.** Le commentaire porte les chiffres, **le retrait explicite
de l'annonce du 10/11** (§2.2), **le démenti de la série de quatre hausses du
rejeu d'archive** (§2.3), et le rappel que **rien n'a été déployé côté mémoire
depuis `af25efb` (21/09)**, soit **CINQUANTE ET UN jours**. Remède mesuré
inchangé : la **ligne en tuple** (≈ −1 030 o/ligne, §2.6 de l'enquête du 10/09),
après la mesure `tuple` vs `namedtuple` à la sonde, **jamais jouée**.
ⓘ **Calcul à taux constant : impossible et vide de sens** — la pente est
**négative**. Le problème est un **NIVEAU**, pas une dérive.

### 6.2 KAN-5 (purge) — **reste ouvert, compteur à 0/3, question posée (10ᵉ)**

Le commentaire donne le bloc **mot pour mot**, les **deux** points à ne pas
sur-interpréter du §3.2 (la table `model_verif_daily` qui a quatre antécédents,
et `n_57014 = 5` qui n'est pas un record), les deux lectures du compteur, et la
question. ⛔ **Rien fermé.**

### 6.3 KAN-3 (durée, « Terminé ») — **avis : NE PAS ROUVRIR**

La durée **a monté** (+93 s) ⇒ la règle demande un commentaire, il est posé :
chiffres, répartition par étape, **découplage calcul/attente** (cette nuit c'est
**net** : cpu −62,6 s pendant que la durée monte de +93 ⇒ de l'**attente**), et
le fait que **122 % de la hausse soit hors étapes**, dans un bloc **non
instrumenté**.
Mais : pente **−15 s/nuit**, marge **36,49 %** dans la bande des quatre dernières
semaines et **pas un record** (34,57 % le 23/10), garde **non menacé**.
⇒ ⛔ **Pas de réouverture demandée**, et la remontée du garde
(`10-timeout-s3.conf`) **n'est ni lancée ni proposée** : `proposition()` ne la
formule pas, puisque le contrôle se tait.
ⓘ Rappel écrit dans le commentaire : la pente est le **25ᵉ centile des
différences** — elle n'a vu ni le +153 s du 01/10, ni le +336 s du 06/10, ni le
+83 s du 08/11, ni le +177 s du 10/11, **ni le +93 s de cette nuit.**

### 6.4 `bw-regime-sensibilite` — **critère 1/2, rien posé**

Coût par ligne de `regime` : 10,948 → 10,895 (**recul**) → **10,939**
(**hausse**). Le critère unique du 07/10 demande **deux hausses consécutives**
⇒ **1 / 2, non rempli.** ⛔ **Aucun motif créé.**
ⓘ La valeur reste **près du bas** de la bande des vingt-six nuits
(10,672 – 13,128 ms), et les lignes de `regime` montent encore (+477).

## 7. Les autres points ouverts, relevés sans être refaits

### 7.1 ⚠️ Témoins du mélange : le gain passe NÉGATIF — mais ce n'est **pas** une première

```
⛔ témoins du mélange : sur 7328 balise-jours×échéance, le mélange fait 3.9403 km/h
   contre 3.8841 pour le meilleur membre a priori (gain -1.4 %, mélange devant
   dans 47.6 % des cas) ; contre la moyenne UNIFORME, sur 1067 : 3.9702 vs
   4.1215 (gain 3.7 %)
```

| | 08/11 | 09/11 | 10/11 | **11/11** |
|---|---|---|---|---|
| gain vs meilleur membre a priori | +4,7 % | +3,9 % | +0,8 % | **−1,4 %** |
| mélange devant, part des cas | 55,5 % | 52,7 % | 47,8 % | **47,6 %** |
| gain vs moyenne UNIFORME | +2,8 % | +4,4 % | +2,0 % | **+3,7 %** |
| erreur du mélange (km/h) | 2,2496 | 3,2254 | 4,9550 | **3,9403** |

⇒ ⛔ **Quatre reculs de suite** sur le gain contre le meilleur membre, et il
passe **négatif**. La part « devant » reste **sous 50 %** pour la deuxième nuit.
⇒ ⚠️ **Mais ce n'est PAS une première, et c'est ce qui change la lecture** : le
**07/10** la série était déjà descendue à **−0,6 %** et **49,2 % devant**, puis
elle est remontée à +8,2 % le 07/11. **Un gain négatif a donc déjà été vu et
s'est déjà corrigé.** ⇒ Je ne l'annonce pas comme un fait nouveau.
⇒ ✅ **Et le gain contre la moyenne UNIFORME REMONTE** (+2,0 → **+3,7 %**), donc
les deux mesures **divergent** cette nuit. ⓘ L'erreur absolue, elle, **recule de
20 %** (4,9550 → 3,9403 km/h) : journée moins ventée qu'hier, mais toujours plus
que les 2,25 du 08/11 — **les niveaux ne sont pas encore comparables.**
⇒ ⓘ **Compteur de passage sous la barre : 2 / 3**, pas davantage (la part
« devant » est le critère qui a basculé ; le gain uniforme, lui, s'améliore).
**Rien créé.** Si la série confirme **sur une journée calme**, demander à Yann
s'il veut un motif.

### 7.2 ⛔ Recalcul indépendant : **5 écarts, tous `fcstagrume/`, TROISIÈME nuit**

```
13 balise-jours comparés, 7 sous le seuil de 6 h
⚠️ 5 ÉCART(S) — le recalcul indépendant ne retrouve pas la base :
  fcstagrume/pioupiou:827            agrume    +24h — ici None, base 5.501  : 1 h appariée
  fcstagrume/windsmobi:ffvl-187      agrume    +48h — ici None, base 2.05   : 0 h appariées
  fcstagrume/infoclimat:STATIC0228   agrume_pi +48h — ici None, base 1.2833 : 0 h appariées
  fcstagrume/pioupiou:2183           agrume_pi +48h — ici None, base 6.7656 : 0 h appariées
  fcstagrume/windsmobi:ffvl-49       agrume_pi +48h — ici None, base 11.1   : 0 h appariées
```

| | 09/11 | 10/11 | **11/11** |
|---|---|---|---|
| balise-jours comparés | 13 | 12 | **13** |
| sous le seuil de 6 h | 7 | 8 | **7** |
| écarts | **5** | **5** | **5** |
| famille | **100 % `fcstagrume/`** | **100 % `fcstagrume/`** | **100 % `fcstagrume/`** |
| graine du tirage | — | — | **464706221** |

⇒ ⛔ **Troisième nuit identique**, sur un tirage **aléatoire de graine
différente** : **ce ne sont pas les mêmes balises**, c'est le même préfixe avec
le même symptôme. Le critère écrit **à l'avance** le 09/11 était rempli le
10/11 ; il l'est **deux fois**.
⇒ ⬆️ **Je ne crée RIEN seul. Question reposée à Yann (2ᵉ fois)** : créer un motif
`bw-appariement-fcstagrume` ?
ⓘ **Le symptôme reste le même** : les 5 écarts sont parmi les **7 sous le seuil
de 6 h** — « le recalcul refuse une case que `run.sh` a acceptée », pas « la base
est fausse ».

### 7.3 Position : **13 divergentes (contre 14), 3 confirmées, aucun front ⇒ aucun cri**

| balise | écart | jours | signature |
|---|---|---|---|
| `pioupiou:367` | 6 764 m | 10 j | nœud 0,01 **et** profil 0,025 CHANGE — « Le relais » |
| `infoclimat:STATIC0491` | 1 159 m | 10 j | nœud 0,01 CHANGE |
| `mf:05170001` | 330 m | 10 j | nœud 0,01 CHANGE |

⇒ ✅ **Mêmes trois confirmées qu'hier, au mètre près** ⇒ **aucun front ⇒ aucun
cri** : **20ᵉ vérification du « à front, pas à état ».** ⓘ La question du 01/10
reste ouverte : **faut-il qu'il recrie** quand une balise reste confirmée douze
nuits de suite ?
ⓘ Le détail du reste, **et la deuxième confirmation d'un mécanisme** :
- **Huit** à **7 j** (1562, 2338, 1473, 1544, 1636, 1476, 175, 1595) — les mêmes
  huit qu'hier à 6 j, **+1 j chacune**.
- **`pioupiou:1334`** (37 911 m) passe de 1 j à **2 j** ; **`pioupiou:308`**
  reste à **2 j**.
- ⚠️ **`pioupiou:84` a DISPARU de la liste** : elle était à 2 j le 09/11, à 1 j
  le 10/11, elle n'y est plus. ⇒ ✅ **Deuxième confirmation, par le bout
  extrême, de l'observation du 10/11** : le compteur de jours **descend**, et une
  balise **sort** complètement. ⓘ C'est ce qui fait passer le total de 14 à 13.
⛔ **Je n'annonce AUCUNE échéance** : deux erreurs là-dessus (28/10 démenti le
30/10, 29/10 démenti le 07/11), et le mécanisme est maintenant vu **deux fois**.
- `pioupiou:367` reste confirmée ⇒ ⛔ **`position_l15_2026-11-02.sql` est
  toujours périmé**, et jamais joué (§7.5).

### 7.4 ⛔ Toujours **9** balises nées sous leur identifiant — 6ᵉ confirmation

```
ⓘ 9 balise(s) née(s) sous leur identifiant (`notee_depuis`, lot L15-bis) :
  pioupiou:1363, 1375, 1414, 1495, 1531, 1595, 2005, 2139, 2189 (toutes 2026-09-25)
```

⇒ ⛔ **L'annonce du 02/11 (9 → 12 au 05/11) n'a jamais eu lieu** : **sixième**
voie qui confirme que le `.sql` **n'a jamais été joué**.

### 7.5 ⛔ `BW_DISCORD_WEBHOOK_URL` : toujours absente, **mesurée ce matin**

`grep -c BW_DISCORD_WEBHOOK_URL ~/.balise-watch-alertes.env` → **0**.
Les **25** variables présentes ont été lues **par leur nom seul** (`cut -d= -f1`),
**aucune valeur** : `BW_WEBHOOK_URL`, `BW_ALERTE_MAIL`, `BW_JIRA_*` (×5),
`BW_*_PING_URL` (×13), `BW_MODEL_SELF_TEST_BLOQUANT`, `BW_PING_OK_URL`.
⇒ **Le second canal du téléphone reste muet**, et `installer-webhook-discord.sh`
est toujours sur le Mac, à lancer par Yann. ⓘ **61ᵉ jour.**
⚠️ **Et cette nuit le coût était visible** : un cri est parti, **par un seul
canal**. Si le webhook unique avait échoué, personne n'aurait été averti.

### 7.6 Dette inchangée, relevée sans y toucher

- ⛔ **Sept `.sql` en attente**, tous encore là, tous non suivis par git :
  `diagnostic_base_sous_tension_2026-09-29.sql` (**44ᵉ jour**) ·
  `position_l15_2026-11-02.sql` · `suspension_l15_2026-11-02.sql` ·
  `naissance_l15bis_2026-09-22.sql` · `rattrapage_purge_2026-09-29.sql` ·
  `schema_l15bis_notee_depuis_2026-09-22.sql` · `suspension_l15_2026-09-22.sql`.
- ⛔ **Quatre miroirs git en souffrance**, **NON arrangés** : `24/10` absent ·
  `26/10` présent mais non suivi · `01/11` absent · `04/11` absent.
  ✅ `07/11` à `10/11` présents et suivis. ⓘ **Rien n'a été fabriqué après coup.**
- ⓘ `mutations_memoire` : **aucune ligne cette nuit** dans le journal — la dette
  antérieure (3 mutations non vues : 2, 5, 13) est donc **relevée comme
  inchangée, pas comme vérifiée.**
- **Duels** : `agrume ↔ agrume_pi (+6 h)` médiane **+0,010**, IC95
  [+0,006 ; +0,017] → `b_better` (hier [+0,005 ; +0,016]) ;
  `agrume ↔ meteofrance_arome_france_hd` médiane **−0,001**, IC95
  [−0,002 ; +0,002] → **`not_separable`** ;
  `arome_r2 ↔ arome_hd` médiane **+0,077** (hier +0,083) → `b_better` ;
  `agrume_pi ↔ bw_mix` médiane **+0,384** (+6 h) et **+0,438** (+24 h) →
  `b_better`. ⓘ Le **cumul reste TRONQUÉ par la rétention de 30 j**, et le
  journal le dit lui-même à chaque ligne.
- ✅ **Self-test vert** : les quatre contrôles (a) à 1,0, la prévision permutée à
  `rms(perm)/rms(clim) = 2,198` dans [1,0 ; 3,0] et `beats_persist` faux.

## 8. ⚠️ L'horaire de la routine : **4 h 16 de retard**, après trois matins nets

Programmée pour le **11/11 à 07:09:05 UTC**, tirée le **11/11 à 11:25:25 UTC** :
⚠️ **+4 h 16 min 20 s.**

```
30/10 +0 h 00 · 31/10 +0 h 00 · 01/11 +0 h 55 · 02/11 +0 h 19 · 03/11 ✅ +0 h 01
04/11 ⚠️ +4 h 42 · 05/11 ⛔ SAUTÉ · 06/11 ⛔ SAUTÉ · 07/11 ⚠️ +3 h 49
08/11 ✅ +0 h 03 · 09/11 ✅ +0 h 05 · 10/11 ✅ +0 h 08 · 11/11 ⚠️ **+4 h 16**
```

⇒ ⚠️ **La série de trois tirs nets est cassée**, et le retard est du même ordre
que ceux du 04/11 (+4 h 42) et du 07/11 (+3 h 49). ⓘ **Le VPS, lui, est à
l'heure** : `debut` 04:58:38, `lancement=timer`, contrôle à 07:30:26 CET.
⇒ **Le trou est côté planification, pas côté machine.** ⓘ Et le `debut` du VPS
**casse sa dérive** de +26 s/nuit (04:58:23 → 04:58:49 → 04:59:15 → 04:59:41 →
**04:58:38**, soit −63 s) : **noté sans être interprété**, et la série de quatre
hausses est démentie.

## 9. ⬆️ Décisions en attente de Yann — par ordre d'urgence

1. ⛔ **R2 est à 108,3 % et le garde-fou crie de nouveau** (§4). Le vert du
   10/11 est **démontré faux**, pas seulement soupçonné. ⇒ Geste attendu,
   inchangé : **décider d'une rétention sur `agrume/pi`** (+48 objets/nuit,
   **28 nuits** sans un recul, +0,582 Go/mois à lui seul) ou **accepter la
   facture**. ⓘ Le garde-fou écrit `palier atteint dans 0 j`.
2. ⛔ **Trancher la lecture du compteur KAN-5** (§3.3). **Dixième** fois. Une
   phrase suffit : « un 57014 de **SONDE**, ou d'une **autre table**, casse-t-il
   le compteur, ou seulement un 57014 de **TRANCHE** ? »
3. ⬆️ **Créer un motif pour les écarts du recalcul indépendant ?** (§7.2)
   **Troisième nuit identique**, tirages différents. **Je ne crée rien seul.**
4. ⬆️ **`purge model_verif_daily` entre-t-elle dans KAN-5** (quatre occurrences :
   14/10, 16/10, 25/10, 11/11) **ou mérite-t-elle son propre suivi ?** (§3.2a)
5. ⛔ **La ligne en tuple** (KAN-4) : **cinquante et un jours** sans rien déployé
   côté mémoire depuis `af25efb`. La mesure `tuple` vs `namedtuple` à la sonde
   est le préalable, **jamais jouée**.
6. ⬆️ **Jalons de temps dans `run.sh`** pour le bloc hors étapes (§2) :
   **122 % de la hausse y est**, **cinquième fois en huit jours**, et les quatre
   étapes instrumentées **baissent**. C'est une écriture.
7. ⬆️ **Jouer `diagnostic_base_sous_tension_2026-09-29.sql`** (**44ᵉ jour**,
   lecture seule, 9 blocs, SQL Editor).
8. ⬆️ **Position** : trancher `pioupiou:367`, `infoclimat:STATIC0491` et
   `mf:05170001`, puis poser `position_suspecte` / `position_note` par `.sql`.
   ⚠️ **`position_l15_2026-11-02.sql` est périmé et jamais joué** — à refaire.
9. ⬆️ **`installer-webhook-discord.sh`** : **61ᵉ jour** sans second canal, et
   cette nuit le cri est parti **par un seul canal** (§7.5).
10. ⚠️ **L'horaire de la routine** (§8) : **+4 h 16** après trois matins nets.
    Le VPS est à l'heure ; **le trou est côté planification.**
11. ⓘ **Question de fond, ouverte depuis le 01/10** : le cri de position doit-il
    **recrier** quand une balise reste confirmée douze nuits de suite ?
12. ⓘ **À surveiller demain, sans rien en conclure** : les **témoins du mélange**
    (§7.1, **2/3**, et il faut une journée calme pour que le niveau parle), et le
    coût par ligne de `regime` après **une** hausse (§6.4, 1/2).

⇒ ⓘ Les points du §9 de la note du 10/11 qui ne sont pas repris ci-dessus restent
valables **tels quels**. **Bilan des prédictions du 10/11 : deux CONFIRMÉES**
(le creux d'`agrume/grille` au Mo près, §4 ; le critère du recalcul indépendant,
§7.2), **une DÉMENTIE DANS LE BON SENS** (le jalon du rejeu d'archive recule,
§2.3), **et une RETIRÉE parce que fausse** (la bande du coût par ligne rejouée,
§2.2).

## 10. Respect des règles

✅ **VPS en LECTURE SEULE, pleine et entière.** Aucun `systemctl start/restart/
daemon-reload`, aucun `enable`, aucun SQL joué, aucun `rsync`, rien écrit dans
`~/balise-watch` ni dans `/etc`. Seules écritures : **les trois commentaires
Jira**. ⓘ Les deux scripts Jira sont passés par `bash -s` (**aucun fichier déposé
sur le VPS**) ; les seuls fichiers temporaires sont ceux que `bw_jira_http` crée
lui-même dans un `mktemp -d` en 700, effacés par la fonction. La levée nominative
du 07/10 n'a **pas** été invoquée.
✅ **Aucun secret lu par valeur.** `~/.balise-watch-alertes.env` est **sourcé**
(`set -a; . …; set +a`), jamais lu ; les seuls relevés dessus sont un `grep -c`
sur un **nom** et un `cut -d= -f1` qui ne rend que des **noms**. `bw_jira.sh`
passe par `curl -K -`, jamais `-u`.
✅ **Aucun ticket créé, fermé, rouvert ni transité.** Trois commentaires, +1
chacun, **statuts identiques avant et après** (GET des deux côtés).
✅ **Aucun motif neuf créé** : `bw-regime-sensibilite` à **1/2**, témoins du
mélange à **2/3**, le motif candidat du §7.2 **posé en question**, et
`purge model_verif_daily` **posée en question** au lieu d'être déclarée neuve.
✅ `10-timeout-s3.conf` **non touché** ; remontée du garde **non lancée et non
proposée**.
✅ `controle_quotidien.sh` **non touché**, son `$ETAT` conservé.
✅ **Desktop Commander exclusivement** pour fichiers et shell, du début à la fin.
✅ **Lire avant d'écrire** : `git log --since=midnight` dans les **deux** dépôts
(**un commit du jour trouvé, lu, et identifié comme étranger à cette routine**) ;
`project_read` du 11/11 (**absent ⇒ création**) et du 10/11 (**lu en entier**) ;
`README.md` relu ; **note en section horodatée** ; GET Jira avant écriture
comme troisième témoin.
⛔ **Aucun `git push`.** Commit local depuis la **racine** du dépôt serveur.
✅ **Yann averti par notification.**

## 11. ⓘ Outillage — ce que ce matin apprend

1. ⛔ **Une bande se recalcule, elle ne se cite pas.** L'annonce retirée du
   §2.2 vient d'une bande (1 686–1 731) **reprise d'une note** au lieu d'être
   **recalculée sur le registre** : le 04/11 à 1 744,4 o était dedans et
   l'invalidait. ⇒ ⓘ C'est le pendant exact de la leçon du 10/11 (« lire
   vingt-cinq nuits avant d'écrire une phrase de tendance ») : **lire vingt-cinq
   nuits ne suffit pas si on lit la note au lieu des données.**
2. ✅ **Deux vérifications d'antériorité ont empêché deux fausses annonces** :
   `purge model_verif_daily` paraissait neuve (**quatre antécédents**), et
   `n_57014 = 5` paraissait un record (**13 le 19/09**). ⇒ ⓘ Le réflexe est le
   même dans les deux cas : **`grep` le registre avant d'écrire « neuf » ou
   « record »**, et il coûte une seconde.
3. ✅ **Une prédiction écrite la veille s'est vérifiée AU CHIFFRE**, pas
   seulement dans sa direction (§4 : 108,3 % contre 108,1 % annoncés, et le
   préfixe à l'objet près). ⇒ ⓘ C'est la deuxième fois en deux jours que
   l'écriture préalable permet de **compter** le résultat. Même mécanique au
   §7.2.
4. ✅ **Une absence de push n'était pas une panne de push** — et la nuit
   suivante l'a prouvé. Le 10/11 je refusais de compter une confirmation faute
   d'occasion ; l'occasion est venue (§5.1) et le correctif tient. ⇒ ⓘ **Ne pas
   conclure faute de cas est parfois la seule lecture juste**, et elle se
   rattrape vite.
5. ⓘ **Le compteur de position peut non seulement descendre, mais SORTIR**
   (`pioupiou:84` disparue, §7.3). Deuxième confirmation du mécanisme vu le
   10/11, et cette fois par son bout extrême.
6. ⓘ **Un `✓` d'index ne prouve rien**, et c'est maintenant démontré par deux
   états contradictoires du même préfixe (`652 / 652 ✓` hier,
   `766 / 766 ✓` ce matin, §4).
7. ⓘ Les sorties brutes de ce run sont sur le Mac dans
   `/Users/yann/bw-run-11-11/` (`hist.json`, `hist30.json`, `ctrl.txt`,
   `ctrlv.txt`, `timer.txt`, `score-full.txt`, `gardefou-r2.txt`,
   `r2-bloc.txt`, `r2-fenetre.txt`, `push.txt`, `envnames.txt`,
   `jira-avant.txt`, `jira-post.txt`, `jira-apres.txt`) — **relisibles telles
   quelles**, et `get-jira.sh` / `comm-jira.sh` sont **rejouables**.
