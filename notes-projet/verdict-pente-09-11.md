# Verdict de pente du 09/11/2026 — ✅ **LE VPS EST DE NOUVEAU LISIBLE**, deux nuits rattrapées (08 et 09/11). ⛔ **Le 57014 est revenu — mais c'est la SONDE, pas une tranche.** ⛔ **Deux séries que j'annonçais sont CASSÉES** (reculs du jalon, record de swap). ✅ Trois commentaires délibérés posés, aucun ticket fermé.

## 08:14–08:45 (Paris, CET) — routine Balise Watch, run complet

**Étape 0 : faite en entier, avant toute autre chose.**

- `git log --oneline --since=midnight` dans **les deux** dépôts : ✅ **aucun
  commit du jour**. Dernier commit serveur : **`fbbc269` du 08/11** (miroir du
  verdict bloqué). Dépôt principal : `cc10b42` du 01/11.
  ⇒ **Aucune autre session n'a tourné ce matin.**
- `project_read claude/verdict-pente-09-11.md` : **absent** ⇒ cette note est une
  **création**, pas une fusion.
- `project_read claude/verdict-pente-08-11.md` : ✅ **lu en entier** — c'est le
  run bloqué, et c'est lui qui dit quoi rattraper.
- `notes-projet/README.md` relu : les quatre règles.

## 1. ✅ Le blocage SSH est levé — mais pas pour la raison que j'avais écrite

Les cinq lectures de l'étape 1 passent, `rc=0` partout. Ce qui a changé, mesuré :

```
ssh-add --apple-load-keychain   → rc=0 · Identity added: /Users/yann/.ssh/id_ed25519 (balise-watch-vps)
ssh-add -l                      → 256 SHA256:d0C/G0LX… balise-watch-vps (ED25519)
ssh debian@51.91.102.146 date -u → répond
```

⛔ **Mais il faut corriger la note du 08/11 sur deux points.**

1. ⛔ **Ce matin, `SSH_AUTH_SOCK` était VIDE** dans le shell de Desktop
   Commander (`ssh-add -l` rendait « Could not open a connection to your
   authentication agent », rc=2). C'est le **piège n°1**, pas celui d'hier.
   ⇒ ⓘ **Les deux pièges frères se sont donc présentés deux matins de suite,
   chacun une fois.** `launchctl getenv SSH_AUTH_SOCK` rend bien
   `/private/tmp/com.apple.launchd.xVKaupT5FP/Listeners` (identique à hier,
   le Mac n'a pas redémarré depuis : `kern.boottime` toujours au 07/11 17:15:05).
2. ⚠️ **Je ne peux PAS affirmer que la phrase de passe a été ajoutée au
   trousseau ce matin.** Les deux `security find-generic-password` que j'avais
   joués hier rendent **encore** `rc=44` (« item could not be found ») —
   pourtant `--apple-load-keychain` **charge la clé**. ⇒ ⛔ **Ces deux requêtes
   n'étaient donc pas un test valable de présence au trousseau**, et mon §1.2
   du 08/11 s'appuyait en partie sur un test qui ne mesure pas ce qu'il
   prétend. Ce qui est **mesuré** aujourd'hui : `--apple-load-keychain` rendait
   `rc=1` hier et rend `rc=0` ce matin. **Pourquoi, je ne le sais pas** — soit
   Yann a joué `ssh-add --apple-use-keychain`, soit l'entrée existait sous un
   autre libellé et quelque chose d'autre la bloquait hier. **Je ne devine pas.**

### 1.1 ⬆️ L'ouverture robuste, à mettre dans tout run à venir

```
export SSH_AUTH_SOCK="$(launchctl getenv SSH_AUTH_SOCK)"
ssh-add --apple-load-keychain >/dev/null 2>&1
```

Les **deux** lignes, dans cet ordre, à chaque appel de shell (chaque appel est
un shell neuf). La première soigne le piège n°1, la seconde le piège frère.
C'est ce qui a été utilisé pour **toutes** les lectures de ce run.

## 2. Les deux nuits, chiffre par chiffre

`lancement=timer`, `result=success`, `exec_status=0` **les deux nuits** ⇒ les
deux relevés sont comparables, et le contrôle les compte (81 comparables / 102).

| | 07/11 | 08/11 | 09/11 |
|---|---|---|---|
| durée (s) | 4 806 | **4 889** (+83) | **4 874** (−15) |
| cpu (s) | 3 848,9 | **3 970,2** (+121,3) | **3 921,8** (−48,4) |
| marge / garde 8 100 s | 40,67 % | 39,64 % | **39,83 %** |
| jalon max (Mo) | 3 369 | **3 352** (−17) | **3 366** (+14) |
| jalon − seuil 2 800 | +569 | +552 | **+566** |
| swap au pic (Mo) | 2 474,3 | **2 087,5** (−386,8) | **2 100,5** (+13,0) |
| pages sorties | 2 593 421 | 2 244 601 | **2 118 377** |
| coût / ligne rejouée (o) | 1 730,2 | 1 722,7 | **1 731,2** |
| coût / ligne `regime` (ms) | 10,680 | **11,559** (+0,880) | **10,948** (−0,611) |
| `n_57014` | 0 | **0** | **1** (sonde) |
| lignes effacées (purge) | 151 401 | **150 712** | **151 649** |
| balise-jours rejoués | 2 041 814 | 2 040 335 | 2 038 813 |
| lignes `regime` | 144 170 | 141 261 | 141 805 |

Répartition du temps (les quatre étapes instrumentées contre le reste) :

| | 07/11 | 08/11 | 09/11 |
|---|---|---|---|
| somme des 4 étapes (s) | 2 877,5 | 2 994,0 (+116,5) | 2 901,1 (−92,9) |
| bloc **hors étapes** (s) | 1 928,5 | 1 895,0 (−33,5) | **1 972,9** (+77,9) |

⇒ ⛔ **Sur le solde de deux nuits (+68 s), +44,4 s sont HORS étapes** et +23,6 s
dedans : **65 % de la hausse est dans le bloc non instrumenté** (publication,
Murphy, événements, pression, duels, purge). **Troisième fois en six jours** que
la réponse tombe là. ⇒ ⬆️ **La demande de jalons de temps dans `run.sh` se
repose, inchangée** : c'est une écriture, donc c'est Yann qui tranche.

## 3. ⛔ LE FAIT DU MATIN : le 57014 est revenu, et c'est la SONDE

Le bloc purge du 09/11, mot pour mot, dans l'ordre :

```
⚠️ purge model_score_zone : plus vieille journée illisible
   (essai 1/2 : {"code":"57014", "message":"canceling statement due to statement timeout"})
→ purge model_score_zone : 151 649 ligne(s) effacée(s) en 8 tranche(s)
```

Lecture, en appliquant la grille du 28/09 et du 06/10 sans l'élargir :

- ✅ **C'est la SONDE** (« plus vieille journée illisible », essai 1/2), **pas
  une TRANCHE** : aucune ligne ne porte `?as_of=eq.J&regime=eq.R`.
- ✅ **AUCUNE tranche n'a échoué** : 8 tranches, **151 649 lignes effacées**,
  nombre lisible ⇒ **la purge a ABOUTI.**
- ⚠️ **`des lignes RESTENT` est ABSENTE** — mais c'est la **sonde** qui a
  bronché, donc cette absence est ce matin **moins concluante** que d'habitude.
  Elle ne prouve pas à elle seule qu'il ne reste rien. Seul un
  `select as_of, count(*)` joué à la main le dirait. ⛔ **Je ne conclus donc
  PAS « rien ne reste ».**
- ✅ **C'est le SEUL 57014 de tout le journal, toutes unités confondues, depuis
  le 07/11 00:00** (vérifié par un `grep` sur le journal entier, pas seulement
  sur `bw-model-score`).
- ✅ **La nuit du 08/11 était propre, pleine** : 150 712 lignes en 8 tranches,
  zéro 57014 partout, aucune sonde en défaut. **Treizième nuit propre.**

### 3.1 ⛔ Où en est le compteur KAN-5 — deux lectures, et je n'ai pas tranché

1. **Critère ÉCRIT sur le ticket et dans le prompt** (« trois nuits consécutives
   **sans 57014 dans le bloc purge** ») : le 57014 **est** dans le bloc purge
   ⇒ le compteur **RETOMBE À 0/3**, après **treize** nuits propres (29/10 → 08/11).
2. **Critère par NATURE** (aucune tranche en échec, purge aboutie, nombre de
   lignes lisible) : la série continue, **quatorzième nuit d'affilée** sans une
   seule tranche perdue.

La différence n'est pas rhétorique : la lecture 1 remet le compteur à zéro pour
la **deuxième fois en six semaines** sur un **timeout de sonde** qui n'a rien
effacé de moins ; la lecture 2 ferait de KAN-5 un ticket **fermable depuis dix
jours**. ⇒ ⬆️ **Question posée à Yann sur le ticket (la huitième)**, et **rien
n'est fermé ni transité en attendant.** C'est la règle : un ticket fermé à tort
vaut moins qu'un ticket ouvert.

⚠️ **Le volume effacé n'est pas un signal.** 150 712 puis 151 649 lignes : dans
la bande habituelle (≈ 125 000 à 152 000), qui suit le volume de la journée
purgée. Il monte et descend sans rien signifier.

## 4. ⛔ DEUX SÉRIES QUE J'ANNONÇAIS SONT CASSÉES — corrections à mon débit

### 4.1 Les « quatre reculs » du jalon mémoire : un cinquième, puis la casse

3 406 → 3 378 → 3 373 → 3 369 → **3 352** (08/11, point le plus bas) →
**3 366** (09/11, **+14**).
⇒ ⛔ **Ce n'était pas une pente à la baisse.** La bande **3 151–3 452 Mo est
inchangée depuis vingt nuits** : ni hausse de fond, ni baisse. Le jalon reste
**+566 Mo au-dessus du seuil** de 2 800 Mo.
⇒ ⓘ Le coût par ligne rejouée dit la même chose : 1 730,2 → 1 722,7 → 1 731,2 o,
**onze nuits d'oscillation entre 1 686 et 1 731 o sans pente nette.** Et la
fenêtre rejouée **décroît** régulièrement (2 041 814 → 2 038 813 balise-jours) :
⇒ **ce n'est pas le volume qui tient le jalon en l'air.**

### 4.2 Le « record de swap » du 07/11 : DÉMENTI, et c'était le fait le plus sérieux de la note du 07/11

2 474,3 Mo (07/11, annoncé comme record et **troisième hausse consécutive**) →
**2 087,5** (−386,8) → **2 100,5** (+13,0).
Pages sorties : 2 593 421 → 2 244 601 → **2 118 377**, **deux baisses de suite**.
⇒ ⛔ **La série de trois hausses est cassée, et le pic a reculé de 374 Mo en deux
nuits.** L'alerte que je portais le 07/11 — « ce n'est plus une nuit » — **tombe**.
⇒ ⓘ **« Une nuit ne fait pas une pente », et trois non plus.** C'est la
**cinquième** fois en six semaines que cette leçon ressert (28/09 la purge,
05/10 et 06/10 la mémoire, 07/11 les témoins, 09/11 le swap). Elle resservira.
⚠️ J'avais aussi **abandonné l'explication par la charge** le 07/11 au vu de ce
record ; cet abandon reposait sur un point qui n'existe plus. ⇒ **Je ne le
reprends pas non plus** : trois points ne décident de rien dans un sens comme
dans l'autre. **Le swap reste sans explication, et sans série.**

## 5. Ce qui a été fait sur les tickets — et pourquoi par ce canal

⚠️ **Le contrôle de 07:30 s'est TU ce matin** — il n'a commenté **aucun** motif :

```
2026-11-09T07:30:27+01:00 … rien à dire : pente plate ou négative, ou échéance hors horizon
ⓘ 102 relevé(s), 81 comparable(s) ; durée : 10 points, pente -101 s/nuit ;
  mémoire : 10 points, pente -23 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
```

⇒ ✅ Le timer est armé pour demain (`Tue 2026-11-10 07:30:48 CET`).

**Canal retenu : `bw_jira_commenter` (délibéré), sur les trois tickets.**
Justification, puisque le choix doit se dire : le contrôle ne parlant de rien,
`bw_jira_signaler` aurait été légitime pour KAN-4 et KAN-5 — mais il **cherche
par étiquette et CRÉE si rien ne répond**, et créer un ticket sans l'accord de
Yann est interdit. `bw_jira_commenter` prend la **clé**, ne cherche rien, ne
crée rien, ne touche pas au jeton du jour. Pour KAN-3 (« Terminé ») il n'y a de
toute façon pas d'autre voie. ⇒ **Trois commentaires délibérés, assumés.**

**GET avant écriture** (règle : revérifier l'état avant d'écrire) :

| ticket | étiquette | statut | comm. avant | comm. après |
|---|---|---|---|---|
| KAN-3 | `bw-pente-duree` | Terminé / `done` | 39 | **40** |
| KAN-4 | `bw-pente-memoire` | À faire / `new` | 53 | **54** |
| KAN-5 | `bw-purge-57014` | À faire / `new` | 36 | **37** |

✅ **+1 chacun, aucun changement d'état, aucun ticket créé.** Le dernier
commentaire d'avant datait du **07/11 11:58** sur les trois ⇒ ✅ **confirmation
que la routine bloquée du 08/11 n'a bien RIEN écrit.**

### 5.1 KAN-4 (mémoire) — **reste ouvert, 1 condition sur 3**

- le jalon **n'est pas mesurément retombé** : +566 Mo au-dessus du seuil ;
- le swap au pic **n'est pas ≈ 0** : 2 100,5 Mo ;
- ✅ seul le **silence du contrôle** est acquis.
⇒ **Pas de fermeture.** Le commentaire porte les chiffres des deux nuits, le
coût par ligne rejouée sur onze nuits, **les deux corrections du §4**, et le
rappel que **rien n'a été déployé côté mémoire depuis `af25efb` (21/09)**, soit
**quarante-neuf jours**. Remède mesuré inchangé : la **ligne en tuple**
(≈ −1 030 o/ligne, §2.6 de l'enquête du 10/09), après la mesure `tuple` vs
`namedtuple` à la sonde. L'élagage de `units` avait rendu −124 Mo au lieu de
−1 500 : **les gains sont dans la structure.**

### 5.2 KAN-5 (purge) — **reste ouvert, question posée**

Le commentaire donne le bloc purge **mot pour mot** des deux nuits, la
distinction sonde / tranche, les deux lectures du compteur du §3.1, et la
question. ⛔ **Rien fermé.** ⓘ Le dossier
`diagnostic_base_sous_tension_2026-09-29.sql` en est à son **42ᵉ jour** d'attente.

### 5.3 KAN-3 (durée, « Terminé ») — **avis : NE PAS ROUVRIR**

La durée **a monté** sur le solde (+68 s en deux nuits) ⇒ la règle du prompt
demande un commentaire, il est posé. Mais : pente du contrôle **−101 s/nuit**,
marge **39,83 %**, série de seize nuits toujours orientée à la baisse.
⇒ ⛔ **Pas de réouverture demandée**, et **la remontée du garde
(`10-timeout-s3.conf`) n'est ni lancée ni proposée** : `proposition()` ne la
formule pas, puisque le contrôle se tait.
ⓘ Rappel écrit dans le commentaire : la pente du contrôle est le **25ᵉ centile
des différences** — elle ignore **par construction** les deux plus grosses
hausses de sa fenêtre. Elle n'a vu ni le +153 s du 01/10, ni le +336 s du 06/10,
ni le +70 s du 07/10, **ni le +83 s du 08/11**. Son silence veut dire « pas de
dérive au 25ᵉ centile », pas « rien n'a bougé ».

### 5.4 `bw-regime-sensibilite` — **critère à 1/2, CASSÉ, rien posé**

Coût par ligne de `regime` : 10,680 → **11,559** (+0,880, une hausse) →
**10,948** (−0,611, un recul). Le critère unique du 07/10 demande **deux hausses
consécutives** ⇒ **non rempli**. ⛔ **Aucun motif créé.**
ⓘ Et ce n'est pas un effet de volume : les lignes de `regime` **baissent** les
deux nuits (144 170 → 141 261 → 141 805).

## 6. Le verdict correctif par correctif — les trois du 07/10

1. ✅ **Webhook `--ipv4` : CONFIRMÉ une 7ᵉ fois**, sur les deux nuits.
   `ⓘ push parti (webhook, HTTP 200)` le 08/11 à 06:20:36 et le 09/11 à 06:20:45,
   suivi chaque fois d'un mail `msmtp … smtpstatus=250 … exitcode=EX_OK`.
   ✅ **Zéro `429` ntfy** sur les deux journées.
   ⚠️ **Il y a bien des `429` dans le journal, mais ce ne sont PAS ceux-là** :
   ils viennent de `run-ingest-pi.sh` / `run-ingest-pi-rafale.sh` sur
   `aromepi/0025` et `aromepi/001` (quota de l'API AROME, 1 à 4 par passe, avec
   pause 20 s et jusqu'à 4 essais). **Rien à voir avec ntfy** — à ne pas
   confondre dans les runs suivants, c'est le même code HTTP.
2. ✅ **Garde-fou « un commentaire par jour et par motif » : il tient.**
   Le contrôle s'est tu sans écrire de jeton, mes trois écritures sont passées
   par le canal délibéré qui **ne touche pas au jeton du jour** ⇒ le canal
   automatique garde son garde-fou intact pour demain.
3. ✅ **Rejeu de purge ≠ échec : CONFIRMÉ, et de la bonne manière.**
   C'est exactement le cas que le correctif visait : un **avertissement** (la
   sonde) **puis un bilan chiffré** (151 649 lignes) ⇒ **le contrôle s'est tu
   sur `bw-purge-57014`**, et il a eu raison. ⓘ Sans ce correctif, KAN-5 aurait
   reçu « purge en échec cette nuit » pour un timeout de sonde, comme le 06/10.

## 7. Les autres points ouverts, relevés sans être refaits

### 7.1 ⛔ R2 : nouveau plus haut, douzième nuit au-dessus du palier

| | 07/11 | 08/11 | 09/11 |
|---|---|---|---|
| total compte | 10,551 Go | **10,693 Go** (106,9 %) | **10,701 Go** (**107,0 %**) |
| objets | — | 7 845 | **7 911** |
| pente affichée | — | −0,009 | **−0,009 Go/mois** |

⛔ **Le palier gratuit est dépassé les deux nuits** : `⚠️ palier gratuit DÉPASSÉ
… R2 facture déjà`. Le garde-fou rend **code 1**, **3 puis 4 runs consécutifs en
échec**, et **le cri est parti les deux fois** (§6.1).
⇒ ⛔ **L'illusion de la pente est intacte** : **−0,009 Go/mois affiché** sur un
compte à **107 %** du palier, alors que `agrume/pi` seul fait **+0,582 Go/mois**.
Le 25ᵉ centile des différences, encore lui.
- `agrume/pi` : **1,917 → 1,938 Go**, **4 339 → 4 387 objets**, soit **+48
  objets par nuit**, **27ᵉ et 28ᵉ nuit sans un seul recul**.
- `agrume/grille` : **5,323 Go / 766 objets les deux nuits**, au Mo et à l'objet
  près — identique au 07/11. ⚠️ **Mais la fermeture du 31/10 avait déjà « tenu »
  avant de ne plus tenir** (creux d'une nuit le 05/11, exactement comme le
  27/10) : **deux nuits stables ne rouvrent pas le dossier.** Le garde-fou se
  tait les nuits de creux, et c'est précisément là que personne n'est averti.
- ⓘ Le bloc « produits indexés » dit `766 présentes / 766 réclamées ✓` pour
  `agrume/grille/` et `19/19`, `28/28`, `11/11` pour les sous-préfixes de
  `agrume/pi/`. ⛔ **Ce n'est PAS un démenti du « 4 244 objets que nul index ne
  réclame » du 07/11** : ce bloc ne contrôle que les **sous-préfixes indexés**,
  et les 4 387 objets de `agrume/pi` n'y sont pas tous. **Je ne compte donc pas
  ce point comme réglé.**

### 7.2 Position : 3 confirmées les deux nuits, **pas de front donc pas de cri**

```
08/11 : ⛔ position : 13 balise(s) divergent du gel (10 j lus), dont 3 CONFIRMÉE(S)
09/11 : ⛔ position : 13 balise(s) divergent du gel (10 j lus), dont 3 CONFIRMÉE(S)
```

Les trois confirmées du 09/11, nommées :

| balise | écart | jours | signature |
|---|---|---|---|
| `pioupiou:367` | 6 764 m | 10 j | nœud 0,01 **et** profil 0,025 CHANGE — « Le relais » |
| `infoclimat:STATIC0491` | 1 159 m | 10 j | nœud 0,01 CHANGE |
| `mf:05170001` | 330 m | 10 j | nœud 0,01 CHANGE |

⇒ ✅ **13 / 3 les deux nuits, aucun front ⇒ aucun cri** : **18ᵉ vérification du
« à front, pas à état »**. ⓘ La question du 01/10 reste ouverte : **faut-il
qu'il recrie** quand une balise reste confirmée dix nuits de suite ?
⚠️ **Je n'ai PAS les identités du 08/11** (le journal ne garde que la ligne de
résumé à cette profondeur) ⇒ je ne peux pas jurer que **la même liste** tenait
les deux nuits, seulement que **le compte** est identique. **Je ne le compte pas
comme un fait acquis.**
- `pioupiou:367` était déjà entrée le 07/11 ⇒ ⛔ **`position_l15_2026-11-02.sql`
  n'est toujours pas à jour**, et de toute façon **jamais joué** (§7.4).
- **Huit** balises à **5 j** (1562, 2338, 1473, 1544, 1636, 1476, 175, 1595) et
  **deux** à **2 j** (84, 308) — 3 + 8 + 2 = 13, le compte est bon.
  ⛔ **Je n'annonce AUCUNE échéance** :
  je me suis trompé deux fois là-dessus (28/10 démenti le 30/10, 29/10 démenti
  le 07/11), et **une leçon écrite et non appliquée ne vaut rien.**

### 7.3 ⚠️ Témoins du mélange : deux reculs, mais toujours positifs

| | 07/11 | 08/11 | 09/11 |
|---|---|---|---|
| gain vs meilleur membre a priori | +8,2 % | **+4,7 %** | **+3,9 %** |
| mélange devant, part des cas | 57,1 % | **55,5 %** | **52,7 %** |
| gain vs moyenne UNIFORME | +4,8 % | **+2,8 %** | **+4,4 %** |
| erreur du mélange (km/h) | 2,3586 | 2,2496 | **3,2254** |

⇒ ⚠️ **Deux reculs de suite**, et le « meilleur point de la série » du 07/11
s'éloigne — mais **les deux gains restent positifs** et le mélange reste devant
dans **plus de la moitié** des cas. ⇒ **Compteur de passage sous la barre :
0/3. Rien créé.**
⚠️ **À pondérer, et c'est le même piège que le 07/11** : l'erreur absolue a
**bondi de 43 %** entre le 08 et le 09/11 (2,2496 → 3,2254 km/h), soit une
journée **bien plus ventée**. Les niveaux de ces trois nuits **ne sont pas
comparables entre eux** ; seul le signe du gain l'est.

### 7.4 ⛔ Toujours **9** balises nées sous leur identifiant — 4ᵉ confirmation

```
ⓘ 9 balise(s) née(s) sous leur identifiant (`notee_depuis`, lot L15-bis) :
  pioupiou:1363, 1375, 1414, 1495, 1531, 1595, 2005, 2139, 2189 (toutes 2026-09-25)
```

⇒ ⛔ **L'annonce du 02/11 (9 → 12 au 05/11) n'a jamais eu lieu**, et c'est la
**quatrième** voie qui le confirme : le `.sql` **n'a jamais été joué**. Les
**sept `.sql`** restent en attente sur le Mac, non suivis par git.

### 7.5 ⛔ `BW_DISCORD_WEBHOOK_URL` : toujours absente, **mesurée ce matin**

`grep -c BW_DISCORD_WEBHOOK_URL ~/.balise-watch-alertes.env` → **0**.
Les 25 variables présentes ont été lues **par leur nom seul** (`cut -d= -f1`),
**aucune valeur** : `BW_WEBHOOK_URL`, `BW_ALERTE_MAIL`, `BW_JIRA_*`,
`BW_*_PING_URL`, `BW_MODEL_SELF_TEST_BLOQUANT`, `BW_PING_OK_URL`.
⇒ **Le second canal du téléphone reste muet**, et `installer-webhook-discord.sh`
est toujours sur le Mac, à lancer par Yann. ⓘ Le dernier relevé **mesuré**
était le 57ᵉ jour (07/11) ; celui-ci est le **59ᵉ**.

### 7.6 ⚠️ Recalcul indépendant : 5 écarts, tous de la même famille

```
13 balise-jours comparés, 7 sous le seuil de 6 h
⚠️ 5 ÉCART(S) — le recalcul indépendant ne retrouve pas la base :
  fcstagrume/infoclimat:00018 agrume +24h — ici None, base 4.529 : 1 h appariée (< 6) mais la base porte une ligne
  fcstagrume/mf:73132003 · fcstagrume/pioupiou:2036 · fcstagrume/infoclimat:STATIC0342 · fcstagrume/mf:65344001
```

⇒ ⓘ **Les cinq sont le même motif** : le recalcul refuse la case faute de 6 h
appariées, la base porte quand même une ligne. **Les cinq sont `fcstagrume/`.**
⚠️ **Je ne sais pas si c'est neuf** : je n'ai pas de relevé antérieur de ce bloc
dans les notes que j'ai lues. ⇒ **Point à SUIVRE, pas un fait établi** : si
demain le compte et la famille sont les mêmes, c'est un seuil d'appariement qui
diverge entre `run.sh` et le recalcul, et ça mérite son propre motif.

### 7.7 Dette inchangée, relevée sans y toucher

- ⛔ **Sept `.sql` en attente**, tous encore là, tous non suivis par git :
  `diagnostic_base_sous_tension_2026-09-29.sql` (**42ᵉ jour**) ·
  `position_l15_2026-11-02.sql` · `suspension_l15_2026-11-02.sql` ·
  `naissance_l15bis_2026-09-22.sql` · `rattrapage_purge_2026-09-29.sql` ·
  `schema_l15bis_notee_depuis_2026-09-22.sql` · `suspension_l15_2026-09-22.sql`.
- ⛔ **Quatre miroirs git en souffrance**, vérifiés un par un et **NON arrangés** :
  `24/10` **absent** · `26/10` **présent mais NON suivi** · `01/11` **absent** ·
  `04/11` **absent**. ✅ `07/11` et `08/11` **présents et suivis**.
  ⓘ **Rien n'a été fabriqué après coup.**
- `mutations_memoire` : **3 mutations non vues** (2, 5, 13), dette antérieure,
  inchangée.
- `agrume ↔ agrume_pi (+6 h)` : `b_better`, médiane +0,010, IC95 [+0,006 ; +0,015].
  `agrume ↔ meteofrance_arome_france_hd` : **`not_separable`**, médiane −0,001.
  ⓘ Le **cumul reste TRONQUÉ par la rétention de 30 j** sur les quatre duels :
  le « depuis la naissance de la paire » n'est plus vrai, et le journal le dit
  lui-même à chaque ligne.

## 8. ✅ L'horaire de la routine : à l'heure, deuxième matin de suite

Programmée pour le **09/11 à 07:09:05 UTC**, tirée le **09/11 à 07:13:59 UTC** :
✅ **+4 min 54 s.**

```
29/10 ⛔ SAUTÉ · 30/10 +0 h 00 · 31/10 +0 h 00 · 01/11 +0 h 55 · 02/11 +0 h 19
03/11 ✅ +0 h 01 · 04/11 ⚠️ +4 h 42 · 05/11 ⛔ SAUTÉ · 06/11 ⛔ SAUTÉ
07/11 ⚠️ +3 h 49 · 08/11 ✅ +0 h 03 · 09/11 ✅ +0 h 05
```

⇒ ✅ **Deux tirs nets d'affilée, les premiers depuis le 03/11.** Et cette fois le
tir à l'heure a servi : la lecture a abouti. ⓘ Le VPS, lui, est à l'heure sur
les deux nuits (`debut` 04:58:49 puis 04:59:15, `lancement=timer`).

## 9. ⬆️ Décisions en attente de Yann — par ordre d'urgence

1. ⛔ **Trancher la lecture du compteur KAN-5** (§3.1). C'est la **huitième**
   fois que la question est posée, et aujourd'hui elle **coûte** : selon la
   lecture retenue, le ticket est soit à **0/3** soit **fermable depuis dix
   jours**. ⇒ **Une phrase de Yann suffit, et elle vaut pour toutes les nuits à
   venir** : « un 57014 de SONDE casse-t-il le compteur, ou seulement un 57014
   de TRANCHE ? »
2. ⛔ **R2 facture — douzième nuit, 107,0 %, nouveau plus haut.** `agrume/pi`
   grossit de **+48 objets par nuit depuis 28 nuits** sans un seul recul, et
   **la pente affichée (−0,009 Go/mois) est fausse par construction**. ⇒ Geste
   attendu : décider d'une rétention sur `agrume/pi`, ou accepter la facture.
3. ⛔ **La ligne en tuple** (KAN-4) : **quarante-neuf jours** sans rien déployer
   côté mémoire depuis `af25efb`. La mesure `tuple` vs `namedtuple` à la sonde
   est le préalable, et elle n'a jamais été jouée.
4. ⬆️ **Jalons de temps dans `run.sh`** pour le bloc hors étapes (§2) :
   **65 % de la hausse de deux nuits y est**, et je ne peux pas aller plus loin.
   C'est une écriture dans `run.sh`, donc c'est Yann.
5. ⬆️ **Jouer `diagnostic_base_sous_tension_2026-09-29.sql`** (**42ᵉ jour**,
   lecture seule, 9 blocs, SQL Editor). ⚠️ **Une nuit à `n_57014 = 0` n'est pas
   un correctif** : il y en a eu treize d'affilée avant ce matin.
6. ⬆️ **Position** : trancher `pioupiou:367`, `infoclimat:STATIC0491` et
   `mf:05170001`, puis poser `position_suspecte` / `position_note` par `.sql`.
   ⚠️ **`position_l15_2026-11-02.sql` est périmé** (la liste a changé depuis) et
   **n'a jamais été joué** — à refaire, pas à rejouer.
7. ⬆️ **`installer-webhook-discord.sh`** : **59ᵉ jour** sans second canal.
8. ⓘ **Question de fond, ouverte depuis le 01/10** : le cri de position doit-il
   **recrier** quand une balise reste confirmée dix nuits de suite ?
9. ⓘ **À surveiller demain, sans rien en conclure** : les **5 écarts du recalcul
   indépendant**, tous `fcstagrume/` (§7.6), et les **témoins du mélange** après
   deux reculs (§7.3).

⇒ ⓘ Les points du §12 de la note du 07/11 qui ne sont pas repris ci-dessus
restent valables **tels quels**. Deux d'entre eux sont **démentis** par ce run
et ne doivent plus être reconduits : la **série de reculs du jalon** et le
**record de swap** (§4).

## 10. Respect des règles

✅ **VPS en LECTURE SEULE, pleine et entière.** Aucun `systemctl start/restart/
daemon-reload`, aucun `enable`, aucun SQL joué, aucun `rsync`, rien écrit dans
`~/balise-watch` ni dans `/etc`. Seules écritures : **les trois commentaires
Jira**. ⓘ Les deux scripts Jira sont passés par `bash -s` (aucun fichier déposé
sur le VPS) ; les seuls fichiers temporaires sont ceux que `bw_jira_http` crée
lui-même dans un `mktemp -d` en 700, effacés par la fonction. La levée
nominative du 07/10 n'a **pas** été invoquée.
✅ **Aucun secret lu par valeur.** `~/.balise-watch-alertes.env` est **sourcé**
(`set -a; . …; set +a`), jamais lu ; le seul relevé fait dessus est un
`grep -c` sur un **nom** et un `cut -d= -f1` qui ne rend que des **noms**.
`bw_jira.sh` passe par `curl -K -`, jamais `-u`.
✅ **Aucun ticket créé, fermé, rouvert ni transité.** Trois commentaires, +1
chacun, **statuts identiques avant et après** (GET des deux côtés).
✅ **Aucun motif neuf créé** : `bw-regime-sensibilite` est à 1/2, les témoins du
mélange à 0/3, et le point du §7.6 est laissé en observation.
✅ `10-timeout-s3.conf` **non touché** ; remontée du garde **non lancée et non
proposée** (le contrôle se tait, `proposition()` ne la formule pas).
✅ `controle_quotidien.sh` **non touché**, son `$ETAT` conservé.
✅ **Desktop Commander exclusivement** pour fichiers et shell, du début à la fin.
✅ **Lire avant d'écrire** : `git log --since=midnight` dans les **deux** dépôts
(aucun commit) ; `project_read` du 09/11 (**absent ⇒ création**) et du 08/11
(**lu en entier**) ; `README.md` relu ; **note en section horodatée**.
⛔ **Aucun `git push`.** Commit local depuis la **racine** du dépôt serveur.
✅ **Yann averti par notification** avec les chiffres et la question du §3.1.

## 11. ⓘ Outillage — ce que ce matin apprend

1. ✅ **Les deux pièges SSH sont désormais traités ensemble** (§1.1), et c'est
   ce qui a débloqué le run : hier c'était l'agent vide, ce matin la variable
   vide. ⇒ ⓘ **Ne diagnostiquer qu'un seul des deux, c'est se condamner à
   recommencer le lendemain.** Les deux lignes coûtent 0,2 s.
2. ⛔ **Leçon amère, et c'est la vraie de ce matin : un test qui ne mesure pas
   ce qu'il prétend est pire qu'une absence de test.** Mes deux
   `security find-generic-password` du 08/11 rendaient « item could not be
   found » — ils le rendent **encore ce matin**, alors que la clé se charge.
   ⇒ **J'ai donc écrit hier une cause (« la phrase de passe n'est PAS dans le
   trousseau ») sur la foi d'un test invalide.** Elle était peut-être juste,
   mais elle n'était **pas mesurée**. À l'avenir : pour savoir si le trousseau
   porte la clé, le seul test valable est **`ssh-add --apple-load-keychain` puis
   `ssh-add -l`**, pas une requête `security` dont le libellé est deviné.
3. ✅ **Le lecteur de flux qui perd des lignes** (piège n°2) : contourné d'emblée,
   **toute** sortie redirigée vers un fichier du Mac et relue avec `read_file`.
4. ⚠️ **Deux `429` de familles différentes dans le même journal** (§6.1) : ceux
   de l'API AROME (`aromepi/*`, bénins, avec pause et réessai) et ceux de ntfy
   (le bug du 07/10). ⇒ **Un `grep 429` seul ne répond pas à la question « le
   webhook est-il passé ? »** — il faut chercher `push parti` et son code HTTP.
5. ⓘ **Le canal délibéré a été préféré au canal automatique alors que
   l'automatique était libre**, et la raison est écrite au §5 : `signaler`
   **crée** si sa recherche ne rend rien, et créer est interdit sans Yann. ⇒ Le
   coût de ce choix est qu'il n'écrit pas le jeton du jour ; le bénéfice est
   qu'aucun doublon de ticket n'est possible. **Choix assumé, redit ici.**
6. ⓘ Les sorties brutes de ce run sont sur le Mac dans
   `/Users/yann/bw-run-09-11/` (`etape0.txt`, `ssh-diag.txt`, `hist.json`,
   `ctrl.txt`, `ctrlv.txt`, `timer.txt`, `score.txt`, `score-tete.txt`,
   `purge-08.txt`, `all57014.txt`, `cmp-08.txt`, `pos-08.txt`, `push.txt`,
   `push2.txt`, `gardefou-r2.txt`, `envnames2.txt`, `calc.txt`, `local.txt`,
   `jira-avant.txt`, `jira-post.txt`, `jira-apres.txt`) — **relisibles telles
   quelles**, et `get-jira.sh` / `comm-jira.sh` sont **rejouables**.
