# Verdict de pente — 12/11/2026

## 12:51 — Balise Watch (routine), verdict de pente du 12/11

### 0. Étape 0 — personne n'était passé avant moi

- `git log --since=midnight` : **aucun commit du jour**, ni dans
  `balise-watch-server`, ni dans le dépôt principal. Le dernier commit serveur
  est `61fdd23` (note du 11/11), le dernier du dépôt principal `cc10b42`
  (01/11).
- `claude/verdict-pente-12-11.md` : **absent** du projet (le contexte
  d'ouverture liste `11-11` comme la plus récente). Donc **création**, pas
  fusion.
- Troisième témoin, et c'est le plus net : le **GET Jira avant écriture** rend
  **42 / 56 / 39** commentaires et un dernier commentaire daté du
  **11/11 à 12:32** sur les trois tickets. Aucune autre session n'avait écrit
  ce matin.
- `notes-projet/README.md` relu : les quatre règles appliquées (lire avant
  d'écrire, une note par jour en sections horodatées, miroir git + commit
  local, commencer par regarder la journée).

### 1. La nuit en chiffres (11/11 → 12/11)

Relevé `lancement=timer`, `result=success`, `exec_status=0` : **nuit
comparable**, rien n'est à écarter.

| | 11/11 | **12/11** | Δ |
|---|---|---|---|
| durée | 5 144 s | **5 042 s** | **−102** |
| `cpu_s` | 3 936,0 | **3 858,3** | **−77,7** |
| marge / garde (8 100 s) | 2 956 s · 36,49 % | **3 058 s · 37,75 %** | +102 · +1,26 pt |
| étapes instrumentées | 2 913,8 s | **2 851,1 s** | −62,7 |
| · `glissant` | 938,7 | **961,5** | +22,8 |
| · `regime` | 1 581,1 | **1 521,6** | −59,5 |
| · `rejeu` | 87,8 | **74,4** | −13,4 |
| · `stabilite` | 306,2 | **293,6** | −12,6 |
| **bloc hors étapes** | 2 230,2 s | **2 190,9 s** | **−39,3** |
| `jalon_max_mo` | 3 376 | **2 948** | **−428** |
| porteur du jalon max | fenêtre rejouée | **le rejeu d'archive** | **changé** |
| jalon « fenêtre rejouée » | 3 376 | **2 924** | **−452** |
| `swap_peak_mo` | 2 147,8 | **2 050,3** | −97,5 |
| `swap_out_pages` | 2 548 710 | **2 134 993** | −413 717 |
| `mem_peak_mo` | 3 587,6 | **3 601,1** | **+13,5** |
| coût / ligne rejouée | 1 738,8 o | **1 519,7 o** | **−219,1** |
| `regime` ms / ligne | 10,939 | **10,544** | −0,395 |
| `balise_jours_rejeu` | 2 035 925 | **2 034 108** | −1 817 (−0,09 %) |
| `lignes_regime` | 144 539 | **144 308** | −231 |
| `n_57014` | 5 | **4** | −1 |
| `lignes_score_zone` | 155 220 | **154 982** | −238 |

**Découplage temps / calcul :** `cpu_s` rend **−77,7 s** sur **−102 s** de durée,
soit **76 %** de la baisse en calcul. Et, pour la première fois depuis cinq
jours, **la baisse est majoritairement DANS les étapes instrumentées** :
−62,7 s sur −102, soit **61 %** dedans et 39 % dehors. Le bloc hors étapes
**baisse aussi** (2 230,2 → 2 190,9 s) : je ne peux donc pas répéter ce matin
que la réponse est systématiquement hors des étapes. Elle ne l'est pas cette
nuit.

### 2. Le fait du matin : la mémoire cède de 452 Mo, et le PORTEUR change

Trois choses se produisent ensemble, et une seule des trois est un record.

**2.1 Le porteur du jalon max change pour la première fois en 62 nuits.**
Depuis le **11/09/2026**, les 62 nuits comparables d'affilée avaient leur jalon
maximum sur **« l'oubli de la fenêtre rejouée »**. Ce matin, ce jalon tombe à
**2 924 Mo** et c'est **« le rejeu d'archive » (2 948 Mo)** qui passe devant.
La dernière nuit où le porteur n'était pas la fenêtre rejouée est le
**10/09/2026** (« le score par régime », 2 897 Mo). C'est un fait de
**structure**, et c'est lui qui dira où chercher si la baisse tient.

**2.2 Le coût par ligne rejouée est un vrai plancher.**
**1 519,7 o** : sur les **67 nuits mesurées**, **aucune** n'était à ce niveau ou
plus bas. C'est la **seule** mesure de ce matin dont je peux dire « record »
sans me tromper — et c'est la mesure qui compte, puisqu'elle neutralise la
taille de la fenêtre.

**2.3 La bande de 29 nuits est enfoncée par le bas.**
Du 14/10 au 11/11, le jalon max tenait entre **3 151 et 3 452 Mo** sans pente
nette. **2 948 Mo** est **203 Mo sous le plancher** de cette bande.

#### 2.4 ⚠️ Trois fausses annonces évitées — le registre lu, pas une note citée

C'est la correction de méthode du 11/11 qui s'applique ici pour la première
fois (« la bande avait été citée d'après une note au lieu d'être recalculée sur
les données »). J'ai donc trié les 84 nuits comparables avant d'écrire un seul
« record » :

- ❌ **« record de jalon bas »** : **FAUX**. Neuf nuits ont fait moins — 1 474 Mo
  le 29/08, 1 500 le 30/08, 1 562 le 31/08, 1 705 le 01/09, 2 157 le 04/09,
  2 764 le 08/09, 2 900 le 09/09, 2 897 le 10/09, **2 838 le 12/09**. Le juste
  énoncé : **le plus bas depuis le 12/09**, soit **61 nuits**.
- ❌ **« record de swap bas »** : **FAUX**. Neuf nuits ont fait moins, dont
  111,4 Mo le 08/09 et **2 000,0 Mo le 22/09**. Le juste énoncé : **le plus bas
  depuis le 22/09**, soit **51 nuits**. 2 050,3 Mo, ce n'est pas « ≈ 0 ».
- ❌ **« `regime` au plus bas »** : **FAUX**, et de loin. 10,544 ms/ligne, mais
  **28 nuits** étaient à ce niveau ou plus bas, la dernière le **17/09**
  (10,4), et 9,7 le 14/09.

#### 2.5 ⛔ Et la réserve qui commande tout : une nuit ne fait pas une pente

**Rien n'a été déployé côté mémoire depuis `af25efb` (21/09), soit 52 jours**, et
la fenêtre rejouée n'a reculé que de **0,09 %** : **aucune cause connue
n'explique −452 Mo.** Ce n'est pas un correctif qui aurait pris effet, puisqu'il
n'y a pas de correctif.

Et ce projet a **trois précédents documentés** de creux d'une seule nuit revenu
**au Mo et à l'objet près** la nuit suivante : 27/10, 05/11 et 10/11, côté R2
(`agrume/grille`). La leçon « une nuit ne fait pas une pente » a déjà resservi
quatre fois en dix jours, **dans les deux sens** — le 06/10 c'était déjà une
baisse de mémoire qui n'en était pas une.

⇒ **Les deux branches sont écrites d'avance, pour que demain tranche sans que je
puisse me relire à mon avantage :**
- si le 13/11 revient vers **3 370 Mo** et que le porteur redevient la fenêtre
  rejouée, **ce matin était un creux de plus**, et il faudra le dire ;
- s'il reste **sous 3 000 Mo**, alors il y a quelque chose à chercher, et le
  **changement de porteur** est le fil : c'est le rejeu d'archive qui deviendra
  le sujet, pas l'oubli de la fenêtre.

### 3. Les trois correctifs du 07/10, un par un

**3.1 Webhook `--ipv4` : CONFIRMÉ, et deux fois dans la même nuit.**
Deux cris réels sont partis, chacun suivi de son accusé :
- position (2 balises confirmées) → `ⓘ push parti (webhook, HTTP 200)` à
  05:23:17Z, puis `msmtp … smtpstatus=250` ;
- garde-fou R2 en échec (2 consécutifs) → `ⓘ push parti (webhook, HTTP 200)` à
  05:23:24Z, puis `msmtp … smtpstatus=250`.

**Zéro 429 de ntfy** sur toute la nuit. ⓘ Et l'attention du 09/11 reste utile :
un `grep 429` seul ne répond pas à la question, parce que les 429 du journal
viennent de l'API AROME (`aromepi`), famille différente, même code HTTP. Cette
nuit il n'y en avait même pas.

**3.2 Garde-fou « un commentaire par jour et par motif » : NON SOLLICITÉ, et
c'est une information en soi.**
Le contrôle de 07:30 a rendu `rien à dire : pente plate ou négative, ou échéance
hors horizon` — il **n'a commenté aucun motif**. Le garde-fou des deux jetons
n'a donc pas eu à arbitrer quoi que ce soit : il ne peut pas y avoir de double
commentaire quand le premier canal se tait. Rien de cassé, rien de prouvé non
plus. Je l'écris plutôt que de compter une confirmation qui n'a pas eu lieu
(c'était la bonne lecture du 10/11 côté webhook, elle vaut ici côté jetons).

**3.3 « Un rejeu de purge réussi n'est pas un échec » : CONFIRMÉ dans son cas le
plus simple.**
Bloc purge **entièrement propre** (§4), bilan chiffré lisible, et le contrôle
**se tait**. C'est le comportement juste : avertissement **puis** bilan ⇒ il se
tait ; et ici il n'y avait même pas d'avertissement.

### 4. La purge — nuit propre, pleine et entière

```
→ purge model_score_zone : 153 082 ligne(s) effacée(s) en 8 tranche(s)
ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée.
```

- **Aucune tranche en échec** : pas une seule ligne `HTTP 500 57014` portant un
  filtre `?as_of=eq.J&regime=eq.R`.
- **Aucun avertissement de SONDE** : la phrase « plus vieille journée illisible »
  est **absente**. C'est différent des 09 et 11/11, et ça change la force de la
  lecture : quand la sonde bronche, l'absence de « des lignes RESTENT » est
  **moins** concluante ; cette nuit la sonde s'est tue, donc l'absence porte un
  peu **plus**. ⚠️ Sans que j'en conclue que rien ne reste : cela ne se conclut
  que d'un `select as_of, count(*)` joué par Yann, **jamais** de l'absence d'un
  message.
- Le volume (153 082) suit le volume de la journée purgée : **il monte et
  descend sans rien signifier**, je ne le lis pas comme un signal.

**4.1 Les quatre 57014 de la nuit ne sont PAS dans la purge.**
`n_57014 = 4`, et les quatre sont `rpc/bw_character_avance`, à 05:21:03,
05:21:46, 05:22:50 et 05:24:07, chacun « reprise 1/3 ». **Tous rattrapés** :
`→ model_character : 403 970 accumulateurs avancés sur 403 970 envoyés`.
La correction de méthode du 10/11 sert pour la **troisième** fois : `n_57014`
compte les 57014 de **toute la nuit** et n'est pas un indicateur de purge.
Et **4 n'est pas un record** (13 le 19/09, 11 le 16/09, 10 le 06/09, 5 hier).

### 5. Position — 2 confirmées, et le cri part sur un DÉPART

```
⛔ position : 13 balise(s) divergent du gel (10 j lus), dont 2 CONFIRMÉE(S)
   ⛔ pioupiou:367           6 764 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE
   ⛔ infoclimat:STATIC0491  1 159 m · 10 j · nœud 0,01 CHANGE
   · mf:05170001              330 m ·  9 j   ← n'est plus confirmée
⛔ position : 2 balise(s) CONFIRMÉE(S) — cri déposé pour envoi
```

**5.1 ⓘ FAIT NEUF, et il répond en partie à une question ouverte depuis le
01/10.** Le cri est parti alors que l'ensemble des confirmées a **RÉTRÉCI**
(3 → 2), et le message nomme explicitement la sortante :

> `- mf:05170001 : rentree dans l'ordre (le referentiel et le gel se sont rejoints, ou la balise n'est plus vue)`

⇒ Le cri est donc bien **à front et pas à état**, et **un départ est un front**,
pas seulement une arrivée. C'est la **première fois** que je l'observe dans ce
sens. ⚠️ Cela ne répond pas encore à « faut-il qu'il recrie quand une balise
**reste** confirmée ? » — question toujours ouverte, 21ᵉ vérification.

**5.2** `mf:05170001` passe à **9 j** : le compteur **descend**, deuxième
mécanisme déjà vu le 10/11 (`pioupiou:84` : 2 j → 1 j → sortie). Je n'annonce
donc **aucune échéance** pour les balises à 8 j, après m'être trompé deux fois
(28 et 29/10).

**5.3 Geste attendu de Yann, inchangé** : trancher chaque cas (correction de
coordonnées ou AUTRE balise ?) puis poser `position_suspecte` + `position_note`
sur `station_zone` par `.sql`. Le contrôle **ne corrige rien** par construction.

**5.4** `ⓘ 9 balise(s) née(s) sous leur identifiant` : **septième** confirmation,
par une voie indépendante, que `position_l15_2026-11-02.sql` n'a **jamais** été
joué — et il est de surcroît périmé.

### 6. R2 — toujours au-dessus du palier, et l'illusion du 25ᵉ centile intacte

| | 11/11 | **12/11** |
|---|---|---|
| total compte | 10,829 Go · 108,3 % | **10,763 Go · 107,6 %** |
| objets | — | **8 099** |
| pente affichée | — | **−0,013 Go/mois** |
| `agrume/grille` | 5,323 Go · 766 obj | **5,323 Go · 766 obj** |
| `agrume/pi` | 1,980 Go · 4 483 obj | **1,999 Go · 4 531 obj** (+48) |

- `bw-garde-fou-r2.service` : **échec code 1, 2 consécutifs**, cri parti.
  `⚠️ palier gratuit DÉPASSÉ : 10.76 Go sur 10 Go — R2 facture déjà`.
- **`agrume/grille` reste à 5,323 Go / 766 objets, deuxième nuit à l'identique.**
  La prédiction du 11/11 (« le creux du 10/11 est un artefact, le prefixe
  revient au Mo près ») **tient une nuit de plus**. Je ne rouvre pas le dossier
  du creux pour autant : deux nuits stables ne font pas davantage une pente que
  une nuit n'en faisait une.
- **`agrume/pi` : 29ᵉ nuit sans un seul recul**, +48 objets encore (le même pas
  exactement), **+0,582 Go/mois à lui seul** pendant que le total affiche
  **−0,013**. ⇒ **L'illusion du 25ᵉ centile des différences est intacte**, et
  c'est le geste attendu de Yann qui ne bouge pas.
- Bloc « produits indexés » : `agrume/grille/ 766 présentes / 766 réclamées ✓`.
  ⚠️ **Et ça ne prouve toujours rien** : le 10/11 il affichait `652 / 652` pour
  le même préfixe dans un état différent. Un coché ne dit rien sur la
  complétude — leçon du 10 et 11/11, confirmée une troisième fois.

### 7. Témoins du mélange — le compteur arrive à 3 / 3

```
⛔ témoins du mélange : sur 7 303 balise-jours×échéance, le mélange fait
   4,224 km/h contre 4,175 pour le meilleur membre a priori
   (gain −1,2 %, mélange devant dans 47,4 % des cas) ;
   contre la moyenne UNIFORME, sur 1 061 : 4,2495 vs 4,4115 (gain 3,7 %)
```

| | 08/11 | 09/11 | 10/11 | 11/11 | **12/11** |
|---|---|---|---|---|---|
| gain vs meilleur membre | +4,7 % | +3,9 % | +0,8 % | −1,4 % | **−1,2 %** |
| mélange devant | 52,7 % | 47,8 % | 47,8 % | 47,6 % | **47,4 %** |
| gain vs moyenne UNIFORME | +4,4 % | +2,0 % | +2,0 % | +3,7 % | **+3,7 %** |
| erreur du mélange (km/h) | 3,2254 | 4,9550 | 4,9550 | 3,9403 | **4,224** |

⇒ **Le critère du compteur est la part « devant » sous 50 %** (c'est lui qui a
basculé le 09/11, pas le gain). Troisième nuit consécutive sous la barre ⇒
**COMPTEUR 3 / 3**.
⇒ ⚠️ **Mais la condition que je m'étais fixée le 11/11 n'est PAS remplie** : j'ai
écrit « si la série confirme **sur une journée calme** ». L'erreur absolue
**remonte de 7 %** (3,9403 → 4,224 km/h) : la journée est **plus** ventée
qu'hier, pas calme. Les niveaux ne sont donc **toujours pas comparables**.
⇒ ⓘ Et le gain négatif n'est pas une première : le **07/10** était à −0,6 % et
49,2 % devant, puis il est **remonté à +8,2 %** le 07/11. Un gain négatif a déjà
été vu **et s'est déjà corrigé**.
⇒ ✅ Les **deux mesures divergent toujours** : le gain contre la moyenne uniforme
reste **positif et stable** à +3,7 %.
⇒ **RIEN CRÉÉ.** Question posée à Yann (§9) : le compteur est plein sur le
critère écrit, mais la réserve de comparabilité tient. C'est à lui de trancher,
pas à moi de créer un motif sur une série dont les niveaux ne se comparent pas.

### 8. Recalcul indépendant — 5 écarts, tous `fcstagrume/`, QUATRIÈME nuit

```
12 balise-jours comparés, 8 sous le seuil de 6 h
⚠️ 5 ÉCART(S) — le recalcul indépendant ne retrouve pas la base :
  fcstagrume/infoclimat:STATIC0318   agrume_pi +24h — ici None, base 9.08    : 1 h appariées (< 6)
  fcstagrume/pioupiou:2012           agrume_pi  +6h — ici None, base 1.6612  : 0 h appariées (< 6)
  fcstagrume/infoclimat:000RT        agrume    +24h — ici None, base 3.7667  : 1 h appariées (< 6)
  fcstagrume/mf:11069001             agrume_pi  +6h — ici None, base 3.4061  : 0 h appariées (< 6)
  fcstagrume/windsmobi:holfuy-1297   agrume    +24h — ici None, base 10.8838 : 1 h appariées (< 6)
```

- **Quatrième nuit de suite**, **exactement 5 écarts**, **tous** du préfixe
  `fcstagrume/`, **tous** du même motif (« moins de 6 h appariées ici mais la
  base porte une ligne »).
- Et les **balises changent** d'une nuit à l'autre (STATIC0318, 2012, 000RT,
  11069001, holfuy-1297 ce matin), sur un tirage de graine différente. ⇒ Ce
  n'est donc **pas un lot de balises malades** : c'est la **strate
  `fcstagrume/` elle-même** qui se comporte ainsi, et le symptôme est stable en
  nombre comme en nature sur quatre nuits.
- ⇒ Le critère que je m'étais fixé le 09/11 est rempli depuis le 10/11, et il se
  renforce. **Rien créé.** Question reposée pour la **troisième** fois (§9).

### 9. Ce qui a été fait sur les tickets, et pourquoi

**GET avant** : KAN-3 `Terminé`/42 · KAN-4 `À faire`/56 · KAN-5 `À faire`/39,
dernier commentaire du 11/11 12:32 sur les trois.
**GET après** : **42 / 57 / 40**. **+1 sur KAN-4 et KAN-5, 0 sur KAN-3**, aucun
changement d'état, **aucun ticket créé**.

- **KAN-4 (mémoire) — commenté, PAS fermé.** Canal **délibéré**
  (`bw_jira_commenter`), parce que j'ai les chiffres et la répartition, et parce
  que `bw_jira_signaler` **créerait** un ticket si sa recherche ne rendait rien.
  Les trois conditions de fermeture : (3) silence du contrôle **ACQUISE** (pente
  mémoire **−17 Mo/nuit**) ; (1) jalon **a bougé fort** mais les **trois** jalons
  restent **au-dessus du seuil de 2 800 Mo** (2 948 / 2 827 / 2 924) et les
  **trois incidents mémoire sont partis** comme les autres matins ; (2) swap au
  pic **2 050,3 Mo**, ce n'est **pas ≈ 0** ⇒ **NON REMPLIE**.
  ⇒ **1 condition sur 3.** Le problème reste un **NIVEAU**, pas une pente — la
  pente est négative, donc **aucun calcul à taux constant n'a de sens**. Remède
  inchangé : la **ligne en tuple** (≈ −1 030 o/ligne, §2.6 de l'enquête), après
  la mesure `tuple` vs `namedtuple` à la sonde. **52 jours** sans rien déployé
  depuis `af25efb`. L'élagage de `units` avait rendu −124 Mo au lieu de −1 500 :
  **les gains sont dans la structure.**
- **KAN-5 (purge) — commenté, PAS fermé.** Les deux lectures écrites noir sur
  blanc : critère **ÉCRIT** (aucun 57014 dans le bloc purge) ⇒ **1 / 3**, le
  11/11 ayant remis à zéro ; critère par **NATURE** (aucune tranche en échec,
  bilan lisible) ⇒ **17ᵉ nuit** consécutive, **fermable depuis 13 jours**.
  **Rien fermé, rien transité.**
- **KAN-3 (durée, `Terminé`) — DÉLIBÉRÉMENT NON COMMENTÉ.** La consigne est
  « si la durée **AUGMENTE**, commente ». Elle **baisse** de 102 s, la pente du
  contrôle est **−101 s/nuit**, la marge **remonte** à 37,75 %, et
  `proposition()` **ne formule aucune remontée** du garde. **Il n'y a pas
  matière** : un commentaire de plus sur un ticket fermé, pour dire qu'il n'y a
  rien, c'est du bruit. **Avis inchangé : NE PAS ROUVRIR.**
  ⓘ Rappel de méthode qui vaut même un matin calme : la pente du contrôle est le
  **25ᵉ centile des différences**, elle **ignore par construction** les deux plus
  grosses hausses — elle n'a vu ni le +153 s du 01/10, ni le +336 s du 06/10, ni
  le +70 s du 07/10, ni le +83 s du 08/11.

### 10. Les questions pour Yann — rien n'a été décidé seul

1. ⛔ **La mémoire : qu'est-ce qui a changé entre le 11 et le 12/11 ?** Je n'ai
   rien déployé (52 jours depuis `af25efb`), le VPS est resté en lecture seule,
   et la fenêtre rejouée n'a bougé que de 0,09 %. **−452 Mo sans cause lisible.**
   Si tu as touché quelque chose, c'est l'explication ; sinon, demain tranche.
2. ⛔ **Trancher la lecture du compteur KAN-5 — ONZIÈME fois.** « Tout 57014 vu
   dans le bloc purge remet le compteur à zéro », ou « seulement un 57014 de
   **TRANCHE** » ? Selon la réponse, le ticket est à 1/3 ou fermable depuis
   13 jours. Tant que ce n'est pas tranché, je ne ferme rien.
3. ⚠️ **Témoins du mélange : compteur 3 / 3 sur le critère écrit** (§7). Veux-tu
   un motif `bw-melange-sous-la-barre` ? Ma réserve : aucune **journée calme**
   n'est encore venue, donc les niveaux ne se comparent pas.
4. ⚠️ **Motif `bw-appariement-fcstagrume` — TROISIÈME demande** (§8). Quatre
   nuits, 5 écarts, strate `fcstagrume/`, balises différentes chaque nuit.
5. ⚠️ **Jalons de temps dans `run.sh`** pour le bloc hors étapes (publication,
   Murphy, événements, pression, duels, purge). ⓘ **Le dossier est moins fort ce
   matin** : le bloc a **baissé** (2 230,2 → 2 190,9 s) et 61 % de la variation
   est **dans** les étapes. Mais il pèse toujours **43 %** de la nuit et reste
   **aveugle**. C'est une écriture dans `run.sh` : à toi de la lancer.
6. ⛔ **Position** : trancher `pioupiou:367` et `infoclimat:STATIC0491`, puis
   poser `position_suspecte` + `position_note` par `.sql`. ⓘ `mf:05170001` est
   **rentrée dans l'ordre** toute seule — un cas de moins.
7. ⛔ **R2** : le palier est dépassé (**107,6 %**, R2 facture déjà), le garde-fou
   est en échec **2 nuits de suite**, et `agrume/pi` prend **+48 objets par nuit
   depuis 29 nuits**. Décider du sort de `agrume/pi` et de `agrume/grille`.
8. ⛔ **`diagnostic_base_sous_tension_2026-09-29.sql`** : **45ᵉ jour** d'attente,
   lecture seule, 9 blocs, à jouer dans le SQL Editor. Sept `.sql` en attente.

### 11. Le reste, mesuré et non arrangé

- ⚠️ **`BW_DISCORD_WEBHOOK_URL` : ABSENTE**, et c'est **mesuré** (relevé des
  **noms** de clés du `.env`, jamais une valeur) — **62ᵉ jour**. Les deux cris de
  cette nuit sont donc partis par un **seul** canal.
- ⛔ **`bw-model-oracle.service` en échec depuis le 01/11 10:08** (`Result=exit-code`),
  soit **11 jours**. Dette antérieure, inchangée, non reprise ici.
- `mutations_memoire` : 3 mutations non vues (2, 5, 13), dette antérieure,
  inchangée.
- ⓘ **Horaire de la routine : 4 h 42 de retard** (tir prévu 07:09 UTC, exécuté
  **11:51 UTC**) — **deuxième matin de retard de suite**, et pire que les 4 h 16
  du 11/11. **Le VPS est à l'heure** (`bw-model-controle.timer` a tiré à
  07:30:30 CET, prochain tir 13/11 07:30:46) : **le trou est côté
  planification**, pas côté machine.
- Quatre miroirs en souffrance, **non arrangés** et rien fabriqué : 24/10 absent,
  26/10 présent non suivi, 01/11 et 04/11 absents.

### 12. Hygiène de la session

- **VPS en LECTURE SEULE pleine et entière.** Aucun `systemctl`, aucun SQL joué,
  aucun rsync, rien écrit dans `~/balise-watch` ni dans `/etc`. Seules écritures
  de la session : **les deux commentaires Jira**.
- **Aucun secret lu par valeur** : `.env` **sourcé** (`set -a; . …; set +a`),
  seuls des **noms** de clés relevés ; `bw_jira.sh` passe par `curl -K -`.
- Scripts passés par `bash -s` et `python3 -` sur l'entrée standard (piège n°3
  du 10/11 : le shell de Desktop Commander est `zsh`, qui ne découpe pas les
  variables sur les espaces).
- Ouverture SSH robuste appliquée d'emblée, **les deux lignes ensemble** :
  `export SSH_AUTH_SOCK=$(launchctl getenv SSH_AUTH_SOCK)` **puis**
  `ssh-add --apple-load-keychain`, à chaque appel de shell. Aucune lecture
  perdue ce matin.
- **Aucun `git push`.** Commit local depuis la **racine** du dépôt serveur.
- Chien de garde (`10-timeout-s3.conf`) **non touché** — et rien ne justifiait de
  le proposer, la marge remonte.
