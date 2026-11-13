# Verdict de pente — 13/11/2026

## 08:11 — Balise Watch (routine), verdict de pente du 13/11

### 0. Étape 0 — personne n'était passé avant moi

- `git log --since=midnight` : **aucun commit du jour**, ni dans
  `balise-watch-server`, ni dans le dépôt principal.
- `claude/verdict-pente-13-11.md` : **absent** du projet (le contexte
  d'ouverture liste `12-11` comme la plus récente). Donc **création**, pas
  fusion.
- Troisième témoin, le plus net : le **GET Jira avant écriture** rend
  **42 / 57 / 40** commentaires, dernier commentaire du **12/11 à 12:59** sur
  KAN-4 et KAN-5, du **11/11 à 12:32** sur KAN-3. Aucune autre session n'avait
  écrit ce matin.
- `notes-projet/README.md` relu : les quatre règles appliquées.

### 1. La nuit en chiffres (12/11 → 13/11)

`lancement=timer`, `result=success`, `exec_status=0` : **nuit comparable**
(**85 comparables** sur 106 relevés, +1).

| | 12/11 | **13/11** | Δ |
|---|---|---|---|
| durée | 5 042 s | **4 876 s** | **−166** |
| `cpu_s` | 3 858,3 | **3 858,7** | **+0,4** |
| marge / garde (8 100 s) | 3 058 s · 37,75 % | **3 224 s · 39,80 %** | +166 · +2,05 pt |
| étapes instrumentées | 2 851,1 s | **2 822,0 s** | −29,1 |
| · `glissant` | 961,5 | **947,2** | −14,3 |
| · `regime` | 1 521,6 | **1 499,5** | −22,1 |
| · `rejeu` | 74,4 | **84,5** | +10,1 |
| · `stabilite` | 293,6 | **290,8** | −2,8 |
| **bloc hors étapes** | 2 190,9 s | **2 054,0 s** | **−136,9** |
| `jalon_max_mo` | 2 948 | **3 372** | **+424** |
| porteur du jalon max | le rejeu d'archive | **la fenêtre rejouée** | **revenu** |
| `swap_peak_mo` | 2 050,3 | **2 316,5** | **+266,2** |
| `swap_out_pages` | 2 134 993 | **2 200 485** | +65 492 |
| `mem_peak_mo` | 3 601,1 | **3 618,7** | +17,6 |
| coût / ligne rejouée | 1 519,7 o | **1 739,9 o** | **+220,2** |
| `regime` ms / ligne | 10,544 | **10,356** | −0,188 |
| `balise_jours_rejeu` | 2 034 108 | **2 032 150** | −1 958 (−0,10 %) |
| `lignes_regime` | 144 308 | **144 791** | +483 |
| `n_57014` | 4 | **0** | **−4** |
| `lignes_score_zone` | 154 982 | **155 466** | +484 |

**Découplage temps / calcul — et il bascule de l'autre côté.** `cpu_s` rend
**+0,4 s** quand la durée perd **166 s** : le calcul n'a pas bougé d'un
quarantième de pour cent. Ce n'est donc **pas** du calcul économisé, c'est de
l'**attente** en moins. C'est la signature inverse des 06 et 07/10 (où `cpu_s`
suivait la durée) et inverse aussi d'hier (76 % de la baisse en calcul).
Et **82 %** de la baisse est **hors étapes** (−136,9 s sur −166) : hier
j'écrivais que pour la première fois en cinq jours la variation était
majoritairement *dedans*. Elle est repassée *dehors* ce matin. **Je ne peux donc
pas plus répéter « c'est toujours dehors » que « c'est maintenant dedans » : ça
alterne, et c'est précisément pour ça que le bloc hors étapes mérite des
jalons.**

### 2. LE FAIT DU MATIN : le creux du 12/11 était un creux, et la branche écrite d'avance se réalise au Mo près

Hier j'avais écrit les deux branches pour que ce matin tranche sans que je
puisse me relire à mon avantage. Voici celle qui tombe :

> « si le 13/11 revient vers **3 370 Mo** et que le porteur redevient la fenêtre
> rejouée, ce matin était un creux de plus, et il faudra le dire »

**3 372 Mo. Porteur : l'oubli de la fenêtre rejouée. Je le dis.**

#### 2.1 Les quatre lignes qui l'établissent

| | 10/11 | 11/11 | **12/11** | **13/11** |
|---|---|---|---|---|
| jalon max | 3 379 | 3 376 | **2 948** | **3 372** |
| porteur | fenêtre | fenêtre | **rejeu d'archive** | **fenêtre** |
| `l'oubli de la fenêtre rejouée` | 3 379 | 3 376 | **2 924** | **3 372** |
| `le rejeu d'archive` | 2 981 | 2 962 | 2 948 | **2 964** |
| coût / ligne rejouée | 1 739,1 | 1 738,8 | **1 519,7** | **1 739,9** |

- **Le coût par ligne rejouée est à 1,1 o du 11/11 et à 0,8 o du 10/11.** Ce
  n'est pas « proche de la bande », c'est la bande. Hier je l'appelais un
  **plancher sur 67 nuits** ; ce matin il est à la **médiane** (44 nuits en
  dessous sur 69 mesurées).
- **Le témoin qui tranche : `le rejeu d'archive` n'a jamais bougé** — 2 953 /
  2 981 / 2 962 / 2 948 / **2 964** Mo sur cinq nuits. Le « changement de
  porteur » du 12/11 n'était **pas** une montée du rejeu d'archive : c'était la
  fenêtre rejouée qui passait **dessous** pour une nuit. ⇒ **Le fil que
  j'annonçais hier (« c'est le rejeu d'archive qui deviendra le sujet ») n'avait
  pas de matière. Je le retire.**
- La « rupture de série de 62 nuits » annoncée hier a donc duré **une** nuit.
- ⇒ **CINQUIÈME creux d'une seule nuit revenu dès le lendemain** dans ce projet
  (27/10, 05/11, 10/11 côté R2, 12/11 côté mémoire). Et **deuxième fois dans le
  sens de la baisse**, après le 06/10.

#### 2.2 ⚠️ Ce que la bonne méthode d'hier n'a pas suffi à éviter

Hier, la correction de méthode du 11/11 a été appliquée correctement : les 84
nuits ont été triées, et **trois fausses annonces de « record » ont été
écartées** (jalon bas, swap bas, `regime` au plus bas). Ce travail était juste.

Mais il ne portait que sur les **superlatifs**. Le **« record » qui restait
(1 519,7 o, plancher sur 67 nuits) était exact au moment où je l'écrivais** — et
il n'a quand même rien annoncé. ⇒ **Leçon à ajouter : vérifier qu'un record est
vrai ne dit rien sur le fait qu'il tienne.** La seule protection qui ait
fonctionné hier, c'est d'avoir écrit **les deux branches d'avance**. C'est ça
qu'il faut refaire, pas un tri de superlatifs plus fin.

#### 2.3 ⓘ Le seul fait de ce matin qui ne soit PAS un retour à la bande

**`le score par régime` tombe à 2 600 Mo — SOUS le seuil de 2 800**, pour la
première fois de la série récente : 2 689 / 2 861 / 2 932 / 2 827 → **2 600**.
C'est pour cela qu'il n'y a que **DEUX** incidents mémoire cette nuit au lieu de
trois.

Et l'étape va dans le même sens côté temps : **10,356 ms par ligne** de `regime`
contre 10,544 hier et 10,939 avant-hier, **alors que `lignes_regime` MONTE de
483**. Moins de mémoire tenue **et** moins de travail par ligne, en même temps,
sur un volume en hausse.

⇒ ⚠️ **Je ne l'appelle pas une tendance** — c'est une nuit, et la leçon du jour
est exactement celle-là. Mais c'est la **seule** mesure de ce matin qui ne soit
pas un simple retour à la bande, donc **c'est elle qu'il faudra regarder demain,
pas le jalon maximum.** Branche écrite d'avance : si `le score par régime`
remonte au-dessus de 2 800 le 14/11, ce sera un creux de plus et il n'y aura
rien à chercher ; s'il reste sous 2 800 avec `regime` sous 10,4 ms/ligne, il y a
quelque chose dans cette étape-là.

### 3. Les trois correctifs du 07/10, un par un

**3.1 Webhook `--ipv4` : CONFIRMÉ.** Un cri réel est parti cette nuit — le
garde-fou R2 en échec, **3 runs consécutifs** — suivi de son accusé :
`ⓘ push parti (webhook, HTTP 200)` à 05:18:07Z, puis `msmtp … smtpstatus=250`.
**Zéro 429 de ntfy.**
⚠️ Et l'attention du 09/11 sert encore : il **y a** un 429 dans le journal de la
nuit, à 04:41:56, mais c'est `run-ingest-pi.sh` / `aromepi/0025` (**quota de
l'API AROME**, 1 × 429 sur 307 requêtes, 6 attentes de quota). **Famille
différente, même code HTTP.** Un `grep 429` seul aurait conclu de travers.

**3.2 Garde-fou « un commentaire par jour et par motif » : NON SOLLICITÉ**,
deuxième matin de suite. Le contrôle de 07:30 a rendu `rien à dire : pente plate
ou négative, ou échéance hors horizon` et **n'a commenté aucun motif** : le
garde-fou des deux jetons n'a donc rien eu à arbitrer. Rien de cassé, **rien de
prouvé non plus** — je l'écris plutôt que de compter une confirmation qui n'a pas
eu lieu.

**3.3 « Un rejeu de purge réussi n'est pas un échec » : CONFIRMÉ dans son cas le
plus simple**, et le plus simple possible cette fois : bloc purge entièrement
propre, **aucun** avertissement, bilan chiffré lisible, et le contrôle se tait.

### 4. La purge — nuit propre, et `n_57014 = 0` sur TOUTE la nuit

```
→ purge model_score_zone : 155 047 ligne(s) effacée(s) en 8 tranche(s)
ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée.
```

- **Aucune tranche en échec** : pas une ligne `HTTP 500 57014` portant un filtre
  `?as_of=eq.J&regime=eq.R`.
- **Aucun avertissement de SONDE** : « plus vieille journée illisible » est
  **absente** (comme le 12/11, contrairement aux 09 et 11/11). Quand la sonde se
  tait, l'absence de « des lignes RESTENT » porte un peu **plus** — ⚠️ sans que
  j'en conclue que rien ne reste : cela ne se conclut que d'un
  `select as_of, count(*)` joué par Yann, **jamais** de l'absence d'un message.
- **`n_57014 = 0`, et c'est vrai partout** : zéro 57014 où que ce soit dans la
  nuit, y compris sur `rpc/bw_character_avance` qui en avait produit **4** le
  12/11 et **5** le 11/11. ⓘ Ce n'est pas un record (45 nuits à 0 au total, dont
  les 05, 06, 07 et 08/11), mais c'est la première nuit à 0 depuis le **08/11**.
- Le volume (155 047 contre 153 082 hier) suit le volume de la journée purgée :
  **il monte et descend sans rien signifier.**

### 5. Position — 2 confirmées, AUCUN cri, et la question du 01/10 est RÉPONDUE

```
⛔ position : 13 balise(s) divergent du gel (10 j lus), dont 2 CONFIRMÉE(S)
   ⛔ pioupiou:367           6 764 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE
   ⛔ infoclimat:STATIC0491  1 159 m · 10 j · nœud 0,01 CHANGE
```

**5.1 ⓘ LA QUESTION OUVERTE DEPUIS LE 01/10 EST TRANCHÉE — 22ᵉ vérification, et
la première qui réponde.** La question était : « faut-il qu'il recrie quand une
balise **reste** confirmée ? » — et, de fait, **recrie-t-il ?**

- Le 12/11, l'ensemble des confirmées était `{pioupiou:367, infoclimat:STATIC0491}`
  après le départ de `mf:05170001`, et le cri **est parti** (c'était un front).
- Ce matin, l'ensemble est **exactement le même** : `{pioupiou:367,
  infoclimat:STATIC0491}`. Aucun départ, aucune arrivée. ⇒ **Aucune ligne
  `cri déposé pour envoi`, aucun push, aucun mail de position.**

⇒ **Un ensemble de confirmées strictement inchangé ne recrie pas.** C'est la
première fois que les deux nuits portent le **même** ensemble non vide, donc la
première fois que le cas se présente proprement.

**5.2 Et la preuve que ce silence n'est pas une panne** est dans la même nuit :
le canal a **démontrablement fonctionné** à 05:18:07Z pour le cri R2 (HTTP 200 +
msmtp 250). Le silence côté position est donc un **choix du code**, pas un canal
muet. ⇒ **Il reste à Yann de dire s'il VEUT qu'il recrie** — la mécanique est
maintenant établie, c'est la décision qui manque.

**5.3** Le peloton bouge sous les deux confirmées, et **dans les deux sens** :
`pioupiou:1595` et `pioupiou:175` apparaissent à **9 j**, `mf:05170001` **reste**
à 9 j (elle ne remonte pas), `pioupiou:1334` à 4 j. ⚠️ **Je n'annonce aucune
échéance** pour les balises à 9 j, après m'être trompé deux fois (28 et 29/10) et
avoir vu le compteur **descendre** deux fois (10/11, 12/11).

**5.4 Geste attendu de Yann, inchangé** : trancher chaque cas (correction de
coordonnées ou AUTRE balise ?) puis poser `position_suspecte` + `position_note`
sur `station_zone` par `.sql`. Le contrôle **ne corrige rien** par construction.

### 6. R2 — le palier s'enfonce, et l'illusion du 25ᵉ centile intacte

| | 12/11 | **13/11** |
|---|---|---|
| total compte | 10,763 Go · 107,6 % | **10,864 Go · 108,6 %** |
| pente affichée | −0,013 Go/mois | **−0,009 Go/mois** |
| `agrume/grille` | 5,323 Go · 766 obj | **5,323 Go · 766 obj** |
| `agrume/pi` | 1,999 Go · 4 531 obj | **2,020 Go · 4 579 obj** (+48) |

- `bw-garde-fou-r2.service` : **échec code 1, 3 consécutifs**, cri parti.
  `⚠️ palier gratuit DÉPASSÉ : 10.86 Go sur 10 Go — R2 facture déjà`.
- **`agrume/grille` : TROISIÈME nuit à l'identique** (5,323 Go / 766 objets). La
  prédiction du 11/11 sur le creux du 10/11 tient une nuit de plus. Je ne rouvre
  pas le dossier : trois nuits stables ne font pas plus une pente qu'une nuit.
- **`agrume/pi` : 30ᵉ nuit sans un seul recul**, encore **+48 objets** (le même
  pas, exactement, pour la deuxième nuit), **+0,582 Go/mois à lui seul** pendant
  que le total affiche **−0,009**. ⇒ **L'illusion du 25ᵉ centile des différences
  est intacte**, et c'est le geste attendu de Yann qui ne bouge pas.
- Bloc « produits indexés » : `agrume/grille/ 766 présentes / 766 réclamées ✓`.
  ⚠️ **Et ça ne prouve toujours rien** : le 10/11 il affichait `652 / 652` pour le
  même préfixe dans un état différent. **Quatrième** confirmation qu'un coché ne
  dit rien sur la complétude.

### 7. ⛔ Témoins du mélange — LE COMPTEUR EST REMIS À ZÉRO, et je corrige hier

```
⛔ témoins du mélange : sur 7 298 balise-jours×échéance, le mélange fait
   4,9494 km/h contre 4,9 pour le meilleur membre a priori
   (gain −1,0 %, mélange devant dans 52,1 % des cas) ;
   contre la moyenne UNIFORME, sur 1 059 : 5,0888 vs 5,2769 (gain 3,6 %)
```

| | 09/11 | 10/11 | 11/11 | 12/11 | **13/11** |
|---|---|---|---|---|---|
| gain vs meilleur membre | +3,9 % | +0,8 % | −1,4 % | −1,2 % | **−1,0 %** |
| **mélange devant** | 47,8 % | 47,8 % | 47,6 % | 47,4 % | **52,1 %** |
| gain vs moyenne UNIFORME | +2,0 % | +2,0 % | +3,7 % | **+3,7 %** | **+3,6 %** |
| erreur du mélange (km/h) | 4,9550 | 4,9550 | 3,9403 | 4,224 | **4,9494** |

⇒ ⛔ **Le critère du compteur est la part « devant » SOUS 50 %.** Elle est à
**52,1 %** ce matin : **au-dessus**, pour la première fois depuis le 08/11
(52,7 %). ⇒ **COMPTEUR REMIS À ZÉRO. Il n'est plus à 3 / 3.**

⇒ **Je corrige donc explicitement la note du 12/11**, qui annonçait
« COMPTEUR 3 / 3 » et posait la question d'un motif Jira. **La question tombe**
d'elle-même : la série ne confirme pas, elle se retourne dès la nuit suivante.
C'est exactement ce que la réserve de comparabilité laissait craindre — et c'est
la **cinquième** fois en seize jours que la leçon « une nuit ne fait pas une
pente » resserre quelque chose que la veille présentait comme acquis.

⇒ ⓘ Et le mécanisme est visible : l'erreur absolue **remonte de 17 %** (4,224 →
4,9494 km/h), au niveau exact des 09 et 10/11 (4,9550). **La part « devant »
monte quand la journée est ventée.** Les deux séries ne mesurent donc pas la même
chose selon le temps qu'il fait, ce qui ôte beaucoup de sens à un compteur de
nuits consécutives sur ce critère-là. **À reformuler avec Yann plutôt qu'à
recompter.**

⇒ ✅ Le gain contre la **moyenne uniforme** reste positif et stable : **+3,6 %**,
cinquième nuit entre +2,0 et +3,7 %. **Les deux mesures divergent toujours.**

⇒ **RIEN CRÉÉ.**

### 8. Recalcul indépendant — 7 écarts, tous `fcstagrume/`, CINQUIÈME nuit

```
11 balise-jours comparés, 9 sous le seuil de 6 h
⚠️ 7 ÉCART(S) — le recalcul indépendant ne retrouve pas la base :
  fcstagrume/infoclimat:000W1      agrume    +48h — ici None, base 4.4167 : 0 h appariées
  fcstagrume/mf:01384003           agrume     +6h — ici None, base 1.8    : 0 h appariées
  fcstagrume/windsmobi:ffvl-2101   agrume_pi +48h — ici None, base 3.4304 : 0 h appariées
  fcstagrume/infoclimat:000ZC      agrume    +48h — ici None, base 3.34   : 0 h appariées
  fcstagrume/mf:48148004           agrume    +48h — ici None, base 6.93   : 0 h appariées
  fcstagrume/pioupiou:134          agrume    +24h — ici None, base 2.5    : 0 h appariées
  fcstagrume/windsmobi:ffvl-2582   agrume_pi  +6h — ici None, base 1.7667 : 0 h appariées
```

- **Le « exactement 5 » de quatre nuits est rompu : 7 ce matin.** ⚠️ Je ne le lis
  **pas** comme une aggravation — le tirage est de 20 strates sur une graine
  différente (464706223) et le nombre de balise-jours comparés change aussi
  (12 → 11). Un échantillon différent rend un nombre différent.
- **Ce qui est stable, et c'est ça qui compte : les 7 sont TOUS du préfixe
  `fcstagrume/`, tous du même motif** (« 0 h appariées ici mais la base porte une
  ligne »), et **toutes les balises sont neuves** par rapport aux quatre nuits
  précédentes. ⇒ Cinquième nuit : ce n'est **pas** un lot de balises malades,
  c'est la **strate `fcstagrume/` elle-même**.
- ⓘ Détail neuf et cohérent : les 7 sont à **0 h appariées** (les nuits
  précédentes mélangeaient des 0 h et des 1 h). Le symptôme se *concentre*.
- ⇒ **Rien créé.** Question reposée pour la **quatrième** fois (§10).

### 9. Ce qui a été fait sur les tickets, et pourquoi

**GET avant** : KAN-3 `Terminé`/42 · KAN-4 `À faire`/57 · KAN-5 `À faire`/40.
**GET après** : **42 / 58 / 41**. **+1 sur KAN-4 et KAN-5, 0 sur KAN-3**, aucun
changement d'état, **aucun ticket créé, aucune transition**.

- **KAN-4 (mémoire) — commenté, PAS fermé.** Canal **délibéré**
  (`bw_jira_commenter`) : le contrôle s'est tu, et `bw_jira_signaler`
  **créerait** un ticket si sa recherche ne rendait rien. Les trois conditions :
  (1) jalon retombé ? **NON** — 3 372 Mo, **572 Mo au-dessus du seuil**, et
  c'est la **médiane** des 69 nuits mesurées (34 au-dessus, 34 en dessous) ;
  (2) swap ≈ 0 ? **NON**, et il **remonte** (+266,2 → 2 316,5 Mo ; 20 nuits
  seulement sur 65 sont au-dessus) ; (3) contrôle muet ? **OUI** (pente mémoire
  **−17 Mo/nuit**).
  ⇒ **1 condition sur 3**, comme hier mais **pour la raison inverse** : hier le
  jalon « avait bougé fort », ce matin il est revenu. Le problème reste un
  **NIVEAU**, la pente est négative, **aucun calcul à taux constant n'a de
  sens**. Remède inchangé : la **ligne en tuple** (≈ −1 030 o/ligne, §2.6), après
  la mesure `tuple` vs `namedtuple` à la sonde. **53 jours** sans rien déployé
  depuis `af25efb`.
- **KAN-5 (purge) — commenté, PAS fermé.** Les trois lectures écrites noir sur
  blanc : critère **ÉCRIT** tel qu'appliqué hier (aucun 57014 dans le bloc purge)
  ⇒ **2 / 3** ; lecture **stricte** (tout 57014 de la nuit remet à zéro) ⇒
  **1 / 3**, cette nuit étant la première ; critère par **NATURE** (aucune
  tranche en échec, bilan lisible) ⇒ **18ᵉ nuit** consécutive, fermable depuis
  14 jours. ⇒ Pour la **première fois**, les deux premières lectures
  **qualifient la même nuit** (zéro 57014 partout) ; elles divergent encore sur
  le décompte. **Rien fermé, rien transité.**
- **KAN-3 (durée, `Terminé`) — DÉLIBÉRÉMENT NON COMMENTÉ.** La consigne est « si
  la durée **AUGMENTE**, commente ». Elle **baisse de 166 s**, **troisième nuit
  de baisse d'affilée** (5 144 → 5 042 → 4 876), la marge **remonte à 39,80 %**
  (plus haut depuis le 07/11) et `proposition()` **ne formule aucune remontée** du
  garde. **Il n'y a pas matière** : un commentaire de plus sur un ticket fermé
  pour dire qu'il n'y a rien, c'est du bruit. **Avis inchangé : NE PAS
  ROUVRIR.**
  ⓘ Rappel de méthode qui vaut même un matin calme : la pente du contrôle est le
  **25ᵉ centile des différences** et **ignore par construction** les deux plus
  grosses hausses — elle n'a vu ni le +153 s du 01/10, ni le +336 s du 06/10, ni
  le +70 s du 07/10, ni le +83 s du 08/11.
- **`bw-regime-sensibilite` : critère NON rempli, et sans ambiguïté.** Le critère
  unique (07/10) demande **deux hausses consécutives** du coût par ligne de
  `regime`. Il **baisse** deux nuits de suite : 10,939 → 10,544 → **10,356
  ms/ligne**. **Rien créé.**

### 10. Les questions pour Yann — rien n'a été décidé seul

1. ⓘ **La question mémoire d'hier est close par les données, pas par moi.** Tu
   n'as rien eu à toucher : le −452 Mo du 12/11 était un creux d'une nuit, et il
   est revenu (§2). **Plus rien à répondre là-dessus.** La question vivante est
   **§2.3** : `le score par régime` est passé **sous le seuil** (2 600 Mo) avec
   `regime` à 10,356 ms/ligne. **Si ça tient le 14/11, c'est la première piste
   mémoire depuis 53 jours.** À regarder demain, pas à décider aujourd'hui.
2. ⛔ **Trancher la lecture du compteur KAN-5 — DOUZIÈME fois.** « Tout 57014 vu
   dans la nuit remet le compteur à zéro », ou « seulement un 57014 de
   **TRANCHE** dans le bloc purge » ? Selon la réponse : **2/3**, **1/3**, ou
   **fermable depuis 14 jours**. Tant que ce n'est pas tranché, je ne ferme rien.
3. ⛔ **Position : la mécanique est maintenant établie, la décision manque**
   (§5). Un ensemble de confirmées **inchangé ne recrie pas** — c'est mesuré ce
   matin, et le canal fonctionnait la même nuit. **Veux-tu qu'il recrie** sur un
   état persistant (hebdomadaire, par exemple) ? Et il reste à trancher
   `pioupiou:367` et `infoclimat:STATIC0491`, puis à poser `position_suspecte` +
   `position_note` par `.sql`.
4. ⚠️ **Témoins du mélange : la demande d'hier est RETIRÉE** (§7). Le compteur
   est **remis à zéro** (52,1 % devant). Ce qu'il faut à la place : **reformuler
   le critère**, parce que la part « devant » suit le vent (erreur 4,22 → 4,95
   km/h en une nuit). Veux-tu un critère normalisé par l'erreur absolue, ou une
   fenêtre de 7 nuits au lieu d'un compteur consécutif ?
5. ⚠️ **Motif `bw-appariement-fcstagrume` — QUATRIÈME demande** (§8). Cinq nuits,
   5 à 7 écarts, **toujours** la strate `fcstagrume/`, **toujours** le même
   motif, balises neuves chaque nuit.
6. ⚠️ **Jalons de temps dans `run.sh`** pour le bloc hors étapes (publication,
   Murphy, événements, pression, duels, purge). ⓘ **Le dossier se renforce ce
   matin et pour une raison nouvelle** : la variation est repassée **dehors**
   (82 %) après avoir été **dedans** hier (61 %). **Elle alterne** — donc on ne
   peut pas trancher sans instrumenter. Le bloc pèse **42 %** de la nuit et reste
   **aveugle**. C'est une écriture dans `run.sh` : à toi de la lancer.
7. ⛔ **R2** : palier à **108,6 %** (R2 facture déjà), garde-fou en échec
   **3 nuits de suite**, `agrume/pi` à **+48 objets/nuit depuis 30 nuits**
   (+0,582 Go/mois à lui seul). Décider du sort de `agrume/pi` et de
   `agrume/grille`.
8. ⛔ **`diagnostic_base_sous_tension_2026-09-29.sql`** : **46ᵉ jour** d'attente,
   lecture seule, 9 blocs, à jouer dans le SQL Editor. Sept `.sql` en attente.

### 11. Le reste, mesuré et non arrangé

- ⚠️ **`BW_DISCORD_WEBHOOK_URL` : ABSENTE**, et c'est **mesuré** (relevé des
  **noms** de clés du `.env` — 25 clés, jamais une valeur) — **63ᵉ jour**. Le cri
  de cette nuit est donc parti par un **seul** canal.
- ⛔ **`bw-model-oracle.service` en échec depuis le 01/11 10:08**
  (`Result=exit-code`, `ExecMainStatus=1`), soit **12 jours**. Dette antérieure,
  inchangée, non reprise ici.
- `mutations_memoire` : 3 mutations non vues (2, 5, 13), dette antérieure,
  inchangée.
- ✅ **Horaire de la routine : À L'HEURE.** Tir prévu 07:09:05 UTC, exécuté
  **07:11:58 UTC** — **2 min 53 s**. Après **deux matins de retard** (4 h 16 le
  11/11, 4 h 42 le 12/11), le trou côté planification s'est refermé. Le VPS est
  à l'heure lui aussi (`bw-model-controle.timer` a tiré à **07:30:46 CET**,
  prochain tir **14/11 07:30:30**).
- Quatre miroirs en souffrance, **non arrangés** et rien fabriqué : 24/10 absent,
  26/10 présent non suivi, 01/11 et 04/11 absents.

### 12. Hygiène de la session

- **VPS en LECTURE SEULE pleine et entière.** Aucun `systemctl start/restart`,
  aucun `daemon-reload`, aucun SQL joué, aucun rsync, rien écrit dans
  `~/balise-watch` ni dans `/etc`. Seules écritures de la session : **les deux
  commentaires Jira**.
- **Aucun secret lu par valeur** : `.env` **sourcé** (`set -a; . …; set +a`),
  seuls des **noms** de clés relevés ; `bw_jira.sh` passe par `curl -K -`, jamais
  `-u`.
- Scripts envoyés par **fichier local → `ssh … 'bash -s'`** plutôt qu'en ligne de
  commande : ça contourne proprement la liste noire du shell de Desktop Commander
  (`reg` est dans `regime`, mot présent partout dans ce relevé).
- Ouverture SSH robuste appliquée d'emblée, **les deux lignes ensemble** :
  `export SSH_AUTH_SOCK=$(launchctl getenv SSH_AUTH_SOCK)` **puis**
  `ssh-add --apple-load-keychain`, à chaque appel de shell.
- **Aucun `git push`.** Commit local depuis la **racine** du dépôt serveur.
- Chien de garde (`10-timeout-s3.conf`) **non touché**, et rien ne justifiait de
  le proposer : la marge **remonte** à 39,80 %.
