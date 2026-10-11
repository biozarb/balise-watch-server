# Verdict de pente du 11/10/2026 — **la nuit du soulagement, et le rattrapage des écritures perdues hier**. La durée **recule de 343 s**, la marge remonte de 34,35 % à **38,58 %**, le **hors-étapes casse sa série monotone** (−133 s après quatre hausses), le coût par ligne mémoire touche son **plus bas de treize nuits** (1 667,8 o) et la purge est **propre pour la quatrième fois d'affilée (4 / 3)**. ⛔ En face : les **trois** jalons mémoire repassent au-dessus du seuil — l'amélioration de structure du 10/10 est **démentie**. ✅ **Les trois commentaires Jira préparés le 10/10 et jamais postés sont partis ce matin.**

## 15:10 (Paris) — routine Balise Watch (tirée à 13:01:48 UTC pour 07:11:05 : **+5 h 51 de retard**), lecture VPS complète, **trois écritures Jira**

**Étape 0 faite.** `git log --oneline --since=midnight` :

- dépôt serveur `PWA/balise-watch-server` : **aucun commit du jour**
- dépôt principal `surveillance balise` : **aucun commit du jour**
- `project_read claude/verdict-pente-11-10.md` → le document **n'existait pas**
  (absent de la liste d'ouverture de session, confirmé par `project_info`)
- `claude/verdict-pente-10-10.md` lu **en entier**, et
  `claude/verdict-pente-09-10.md` aussi (il fallait son contenu pour le miroir
  git manquant)
- `notes-projet/README.md` relu — les quatre règles

⇒ **premier et seul run pente du jour. Rien à fusionner, aucun doublon.**

✅ **LE MAC A TENU TOUT LE RUN.** Après deux matins de déconnexion (09 et
10/10), le bridge n'a pas lâché : les onze lectures VPS, les trois POST Jira et
les écritures sur le Mac sont toutes passées. **C'est ce qui a permis le
rattrapage.**

| à lire / à faire | fait ? |
|---|---|
| registre `historique.jsonl` | ✅ |
| `systemctl list-timers` (contrôle + notation) | ✅ |
| journal `bw-model-controle.service` du jour | ✅ |
| `controle_quotidien.py --verbeux` | ✅ |
| journal `bw-model-score.service` de la nuit | ✅ |
| bloc purge de la nuit 10→11 | ✅ |
| position, témoins, Murphy, duels, τ, ρ, écarts, self-test | ✅ |
| noms des variables du `.env` | ✅ |
| jetons du jour (les DEUX dossiers) | ✅ |
| **GET** de l'état des trois tickets | ✅ |
| **POST** des trois commentaires Jira | ✅ **oui — rattrapage du 10/10** |
| miroir git de cette note | ✅ |
| miroirs git manquants (09/10 et 10/10) | ✅ |

## 1. Les nuits, bout à bout

| | 06/10 | 07/10 | 08/10 | 09/10 | 10/10 | 11/10 |
|---|---|---|---|---|---|---|
| durée | 5 157 s | 5 227 s | 5 228 s | 5 192 s | 5 318 s | **4 975 s (−343)** |
| marge | 2 943 | 2 873 | 2 872 | 2 908 | 2 782 | **3 125 (+343)** |
| marge en % du garde | 36,3 % | 35,5 % | 35,46 % | 35,90 % | 34,35 % | **38,58 %** |
| `cpu_s` | 4 163,6 | 4 244,9 | 4 257,9 | 4 199,5 | 4 237,7 | **4 019,1 (−218,6)** |
| jalon max | 3 364 Mo | 3 420 | 3 429 | 3 356 | 3 394 | **3 321 (−73)** |
| au-dessus du seuil | +564 | +620 | +629 | +556 | +594 | **+521** |
| swap au pic | 2 175,5 | 2 127,7 | 2 267,1 | 2 145,1 | 2 088,1 | **2 129,5 (+41,4)** |
| pages sorties | 2 507 693 | 2 369 940 | 2 556 336 | 2 241 569 | 2 487 135 | **2 501 165 (+14 030)** |
| pic système | 3 619,1 | 3 617,2 | 3 602,9 | 3 615,2 | 3 608,5 | **3 619,9 (+11,4)** |
| fenêtre rejouée | 2 087 575 | 2 088 602 | 2 089 691 | 2 089 138 | 2 088 809 | **2 087 981 (−828)** |
| o / ligne rejouée | 1 689,7 | 1 717,0 | 1 720,6 | 1 684,4 | 1 703,8 | **1 667,8 (−36,0)** |
| `n_57014` | 2 (purge) | 0 | 0 | 0 | 1 (hors purge) | **0** |
| lancement / résultat | timer/success | ↳ | ↳ | ↳ | ↳ | **timer/success** |

Nuit **comparable** : `lancement=timer`, `exec_status=0`, `oom=0`,
`result=success`, 06:00:06 → 07:23:12, `source=run.sh`,
`chevauchement_reduit=true`. Rien à écarter.

**Le contrôle de 07:30 a tiré à 07:30:41 et s'est TU** :

```
ⓘ 73 relevé(s), 52 comparable(s) ; durée : 10 points, pente -55 s/nuit ;
  mémoire : 10 points, pente -53 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate/négative, ou échéance hors horizon
```

⇒ **aucun jeton du jour posé par le contrôle.** Vérifié dans les **deux**
dossiers : `/var/lib/bw-model-verif` porte `cri.jira.bw-pente-duree` du 17/09,
`…memoire` du 23/09, `…purge-57014` du 06/10 ;
`$HOME/.balise-watch-etat-alertes` portait `duree` du 07/10 et les deux autres
du 08/10. **`bw_jira_signaler` était donc libre sur les trois motifs** — c'est
lui qui a servi pour KAN-4 et KAN-5 (voir §9).

## 2. ✅ Durée : elle RECULE de 343 s, et le « plus bas de la série » du 10/10 n'a pas tenu une nuit

`5 157 · 5 227 · 5 228 · 5 192 · 5 318 · **4 975**`. La durée est au plus bas
**depuis le 05/10** (4 821 s) et la marge au plus haut **depuis le 05/10**
(40,5 %) : **2 782 → 3 125 s**, soit **34,35 % → 38,58 %** du garde de 8 100 s.

⚠️ **CORRECTION EXPLICITE DE LA NOTE DU 10/10.** Elle annonçait « 34,35 %, le
plus bas de toute la série » et concluait que le « plateau » du 08/10 « n'était
ni un plateau ni un repli : c'était une pause ». **Les deux lectures sont
démenties** : le point bas est rendu en une nuit, et au-delà. Ni « pause », ni
« dérive » : la durée **oscille** dans une bande de 4 821 à 5 318 s depuis
sept nuits, soit **±5 %**.

**Calcul ou attente ? LES DEUX RECULENT.** `cpu_s` perd **218,6 s** pour
**343 s** d'horloge : le processeur rend **64 %** de la baisse, donc ≈ 124 s de
la baisse **ne sont pas du calcul**. Et `n_57014` repasse de **1 à 0** :
l'attente sur la base, réapparue le 10/10, a disparu. ⇒ **c'est le miroir exact
de la nuit précédente**, qui était « mixte » dans l'autre sens.

| étape | 06/10 | 07/10 | 08/10 | 09/10 | 10/10 | 11/10 |
|---|---|---|---|---|---|---|
| `regime` | 1 820,0 | 1 794,6 | 1 813,6 | 1 751,4 | 1 809,1 | **1 648,5 (−160,6)** |
| `glissant` | 1 002,0 | 1 018,3 | 1 005,9 | 988,2 | 964,4 | **974,1 (+9,7)** |
| `stabilite` | 328,8 | 341,7 | 338,1 | 322,5 | 358,7 | **312,0 (−46,7)** |
| `rejeu` | 81,5 | 88,4 | 79,2 | 78,3 | 85,6 | **73,4 (−12,2)** |
| somme des quatre | 3 232,3 | 3 243,0 | 3 236,8 | 3 140,4 | 3 217,8 | **3 008,0 (−209,8)** |
| hors étapes | 1 924,7 | 1 984,0 | 1 991,2 | 2 051,6 | 2 100,2 | **1 967,0 (−133,2)** |

**61 % de la baisse est DANS les quatre étapes, 39 % hors étapes** —
**exactement le même partage que la HAUSSE du 10/10**, en sens inverse. Sixième
nuit, sixième signature, mais celle-ci est la symétrique de la précédente.

⛔ **LE FAIT LE PLUS IMPORTANT DU MATIN : LE HORS-ÉTAPES RECULE.** Il montait
depuis **quatre nuits sans un seul repli** — 1 924,7 → 1 984,0 → 1 991,2 →
2 051,6 → 2 100,2, soit **+175,5 s** — et c'était, deux matins de suite, le
**seul mouvement monotone du tableau**. Il rend **133,2 s** et repasse **sous
son niveau du 08/10**. ⇒ ✅ **la série monotone est CASSÉE.** La question posée
à Yann les 07, 08, 09 et 10/10 — poser des jalons de temps dans le bloc non
instrumenté de `run.sh` (publication, Murphy, événements, pression, duels,
purge) — **reste pertinente** (on ne sait toujours pas lequel des six postes
bouge, dans un sens comme dans l'autre) **mais perd son caractère d'urgence :
ce n'était pas une dérive de fond.**

**Découplage temps / volume — quatrième nuit, et la plus nette de toutes.**
`lignes_regime` **127 374 (+1 902, soit +1,5 %)** pendant que le temps de
`regime` **perd 8,9 %** : **plus de lignes, moins de temps.** De même
`lignes_score_zone` **137 901 (+1 894)** et `lignes_glissant` **10 527 (−8)** ;
`lignes_daily` **69 255 (−422)**. ⇒ **ce qui pilote la durée n'est pas le
nombre de lignes**, et cette nuit le démontre dans le sens inverse des
précédentes.

Coût par ligne de `regime` (ms) :

```
13,39 (01/10) · 13,24 · 14,02 · 13,67 · 13,53 · 15,07 · 14,86 · 14,87 · 13,99 · 14,42 · 12,94 (11/10)
  → −1,48 : UN RECUL FRANC, et le PLUS BAS de la série
```

✅ **`bw-regime-sensibilite` : critère NON rempli, COMPTEUR REMIS À 0.**
L'arbitrage unique du 07/10 exige **deux hausses consécutives** du coût par
ligne ; le compteur était à **1 / 2** hier, il **repart de zéro**. Rien n'est
créé, et la question n'est pas posée à Yann.
Coût par ligne de `glissant` : **92,5 ms** (91,5 le 10/10, +1,0) — stable.

⚠️ **La pente du contrôle a raison ce matin, mais par coïncidence.** Elle est
le **25e centile des différences** : par construction elle ignore les deux plus
grosses hausses de la fenêtre. Elle n'a vu **ni le +153 s du 01/10, ni le
+336 s du 06/10, ni le +70 s du 07/10, ni le +126 s du 10/10**. Ce matin elle
annonce **−55 s/nuit** sur 10 points (73 relevés, 52 comparables) et se tait —
et les chiffres bruts lui donnent raison. ⇒ ⚠️ **ce n'est pas une validation de
l'indicateur : c'est EXACTEMENT la même valeur (−55 s/nuit) qu'elle annonçait
le 10/10, quand la durée était au plus haut et la marge au plus bas.** Elle a
dit la même chose dans les deux situations opposées.

**Remontée du garde : NON lancée, et le contrôle n'en propose aucune** (sa
pente étant négative, `proposition()` n'est pas atteinte). Garde actuel
**8 100 s (135 min)** pour un run de **82,9 min**. ⛔ `10-timeout-s3.conf`
**n'a pas été touché.** Aucune remontée n'est demandée ce matin.

**KAN-3 : réouverture NON demandée.** La durée recule, la marge remonte, le
hors-étapes casse sa série. Rien ce matin ne la justifie.

## 3. ⚠️ Mémoire : le coût par ligne au PLUS BAS de la série, mais l'amélioration de structure du 10/10 est DÉMENTIE

```
⛔ après le rejeu d'archive            : 3 038 Mo  (2 627 le 10/10)  ← +411, DE NOUVEAU AU-DESSUS
⛔ après le score par régime           : 2 894 Mo  (2 688 le 10/10)  ← +206, DE NOUVEAU AU-DESSUS
⛔ après l'oubli de la fenêtre rejouée : 3 321 Mo  (3 394 le 10/10)  ← jalon max, −73
```

⛔ **LA LECTURE DU 10/10 EST DÉMENTIE.** Le 10/10, `incidents` ne portait plus
qu'**une** ligne mémoire : les deux premiers jalons étaient repassés **sous** le
seuil pour la première fois de la série, et c'était lu comme « la pression ne
disparaît pas, elle se **concentre** » sur le seul jalon que la ligne en tuple
visait. **Cette nuit les trois sont de nouveau au-dessus.** ✅ La note du 10/10
avait écrit « c'est **une** nuit : à revérifier demain avant d'en faire une
tendance (la leçon a resservi sept fois en treize jours) ». **C'est fait, et
c'était une oscillation.** Huitième usage de la leçon en quatorze jours.

✅ **En revanche le coût par ligne touche son plus bas de toute la série.**

```
29/09 1 671,3 o · 30/09 1 692,6 · 01/10 1 685,6 · 02/10 1 689,2
03/10 1 706,4  · 04/10 1 697,4 · 05/10 1 717,2 · 06/10 1 689,7
07/10 1 717,0  · 08/10 1 720,6 · 09/10 1 684,4 · 10/10 1 703,8
11/10 **1 667,8**
  → −36,0 o/ligne ; fourchette 1 667,8–1 720,6 sur TREIZE nuits, TOUJOURS aucune pente
```

Le précédent plus bas (**1 671,3**, le 29/09) tenait depuis **douze nuits**.
⚠️ **Mais cela ne fait toujours pas une pente** : la fourchette s'élargit par
le bas comme elle s'était élargie par le haut le 08/10 (1 720,6), et les deux
fois la nuit suivante a ramené la valeur au milieu.

**Calcul à taux constant.** Au taux du **10/10** (1 703,8 o) la fenêtre de cette
nuit aurait rendu **3 392,6 Mo** ; elle rend **3 321**. Les **−71,6 Mo** sont
donc imputables au **coût par ligne**, pas à la fenêtre — qui ne recule que de
**828 lignes**, soit **−1,3 Mo**. Au taux du **29/09** (1 671,3) : **3 327,9 Mo**
— nous sommes **en dessous**, ce qui confirme le nouveau plus bas.

Autres jalons : agrégat quotidien **1 853 (+4)**, oubli fenêtre glissante
**1 750 (−10)**, oubli du chemin J-0 **979 (+20)**, relecture de l'archive
**833 (+3)**, garde-fou de position **1 218 (+4)**, mélange multi-modèle
**1 208 (+6)**.

**Swap : pic 2 129,5 Mo (+41,4)** et **2 501 165 pages sorties (+14 030)** —
les deux remontent légèrement, cohérents entre eux cette nuit (ils divergeaient
le 10/10). ⚠️ Le plancher tient : **12e nuit consécutive au-dessus de 2,0 Go**.

**Rien de déployé côté mémoire depuis `af25efb` (21/09) — 21e nuit sans
levier.** Remède inchangé : la **ligne en tuple** (`enquete-pente-10-09.md`
§2.6, ≈ −1 030 o/ligne), après la mesure `tuple` vs `namedtuple` à la sonde.
L'élagage de `units` avait rendu −124 Mo au lieu de −1 500 : **les gains sont
dans la structure.**

**Les trois conditions de fermeture de KAN-4 : 1 sur 3.** Jalon mesurément
retombé → **NON** (3 321 Mo, +521 au-dessus du seuil ; c'est le plus bas des
sept dernières nuits, pas un retour sous le seuil). Swap au pic ≈ 0 → **NON**
(2 129,5). Contrôle muet sur `bw-pente-memoire` → **OUI**. ⇒ **le ticket reste
ouvert.**

## 4. ✅ Purge : QUATRIÈME nuit propre d'affilée — **KAN-5 est à 4 / 3**, et le 57014 de `bw_character_avance` ne revient pas

```
→ purge model_score_zone : 129 233 ligne(s) effacée(s) en 8 tranche(s)
ⓘ purge model_character : rien avant le 2027-02-04 (première écriture
  2026-08-08, rétention 180 j) — aucune requête lancée.
```

- **aucune TRANCHE à 57014** (aucun `?as_of=eq.J&regime=eq.R` en HTTP 500)
- **aucune SONDE** (« plus vieille journée illisible » absente)
- **aucun « des lignes RESTENT »** — donc rien ne reste en base
- nombre de lignes **lisible** (129 233), **8 tranches** comme les trois nuits
  précédentes
- `n_57014 = 0` au registre, et **aucun 57014 nulle part** dans le journal
⇒ **nuit propre, au sens arbitré.**

| nuit | état du bloc purge | compteur |
|---|---|---|
| 07→08 (jour 2026-10-08) | `n_57014 = 0`, propre | 1 |
| 08→09 (jour 2026-10-09) | propre, 129 650 l. / 8 tr. | 2 |
| 09→10 (jour 2026-10-10) | propre, 129 594 l. / 8 tr. | 3 |
| 10→11 (jour 2026-10-11) | **propre, 129 233 l. / 8 tr.** | **4** |

⇒ ⛔ **LA CONDITION DE FERMETURE DE KAN-5 EST REMPLIE DEPUIS HIER, ET MAINTENANT
DÉPASSÉE : 4 / 3.** Elle n'est **pas** appliquée : la fermeture se décide avec
Yann. **C'est la question n° 1 du matin, pour le deuxième jour de suite.**
ⓘ Le volume effacé suit le volume de la journée purgée (≈ 125 000–134 000) :
les **361 lignes** d'écart avec hier **ne sont pas un signal**.

✅ **BONNE NOUVELLE : le 57014 du 10/10 ne s'est pas reproduit.** Le `statement
timeout` apparu le 10/10 **ailleurs que dans la purge** —
`rpc/bw_character_avance` : HTTP 500 57014, reprise 1/3 aboutie, 466 509
accumulateurs avancés sur 466 509 envoyés — **est absent cette nuit**. C'est lui
et lui seul qui faisait `n_57014 = 1` le 10/10.

⚠️ **Mais une nuit à 0 n'est pas un correctif, et quatre non plus.** Il y en
avait eu trois d'affilée les 03, 04 et 05/10 avant le retour du 06/10, et le
10/10 a montré que le `statement timeout` **change de requête** plutôt que de
disparaître. **La purge est propre ; la base n'est pas démontrée saine.**
⇒ ⛔ **`diagnostic_base_sous_tension_2026-09-29.sql`** (lecture seule, 9 blocs,
SQL Editor) **attend toujours d'être joué : douze jours.**
⇒ ⚠️ **Si KAN-5 est fermé, il ferme « la purge par tranches de
`model_score_zone` expire », pas « la base est sous tension ». Les deux ne sont
pas le même motif, et le second n'a pas de ticket** (question du 10/10, encore
ouverte).

✅ **Le contrôle s'est tu sur ce motif, et c'est CORRECT** : depuis le 07/10,
`constats()` lit `score.log` via `bilan_purge()` — avertissement **puis** bilan
chiffré ⇒ silence. Le faux « purge en échec » du 06/10 ne s'est pas reproduit :
**cinquième nuit.**

## 5. ⚠️ Position : les **mêmes 3 confirmées**, pas de front, pas de cri — et les sept suivantes sont à **6 j**

```
⛔ position : 11 balise(s) divergent du gel (10 j lus), dont 3 CONFIRMÉE(S) (≥ 10 j)
   ⛔ pioupiou:2171          38 925 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE · Windbird 2171
   ⛔ pioupiou:1388           2 363 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE · Décollage Serre Michèle
   ⛔ infoclimat:STATIC0491   1 159 m · 10 j · nœud 0,01 CHANGE · infoclimat STATIC0491
   ·  pioupiou:1333          87 693 m ·  7 j  ← continue de reculer (10 → 8 → 7)
   ·  1378 (15 778 m) · 367 (6 764) · 1417 (829) · 1375 (747) · 1722 (631) · 1562 (481) · 1678 (422) — toutes à 6 j
```

ⓘ **Le compte des confirmées est inchangé (3), donc pas de front, donc pas de
cri** — cohérent avec l'arbitrage « à front, pas à état ». **Aucun `push` nulle
part dans le journal de la nuit** : c'est normal, il n'y avait rien à crier.
`position_confirmees.json` est toujours daté du **09/10 06:01** — il n'a pas été
réécrit, ce qui confirme l'absence de front.

⚠️ **`pioupiou:1333` continue de sortir** : 10 j → 8 j (10/10) → **7 j**. Le
journal du 09/10 disait « rentrée dans l'ordre (le référentiel et le gel se sont
rejoints, ou la balise n'est plus vue) ». **Deuxième nuit de recul : la sortie
se confirme**, mais on ne sait toujours pas laquelle des deux explications joue
pour la balise la plus éloignée du lot (87,7 km).

⚠️ **Les sept balises à 6 j franchiraient 10 j le 15/10** — exactement comme
annoncé les 09 et 10/10, et la progression est régulière (5 j → 6 j). Ce
jour-là le compte passerait de **3 à 10**, donc **un cri à front**.
**Geste attendu de Yann** : trancher `2171`, `1388`, `STATIC0491`, statuer sur
`1333` qui sort, puis poser `position_suspecte` + `position_note` sur
`station_zone` par `.sql`. **Il reste quatre jours.**
ⓘ Question toujours ouverte depuis le 01/10 : **faut-il que le cri recrie** pour
une balise qui reste confirmée ?

## 6. ⚠️ Le second canal du téléphone reste muet — et le `--ipv4` n'a rien eu à faire cette nuit

**`BW_DISCORD_WEBHOOK_URL` est TOUJOURS ABSENTE du `.env`.** 25 variables
relevées par leur **nom seul** (`sed -E "s/=.*//"`, aucune valeur lue) :
`BW_PING_OK_URL`, `BW_WEBHOOK_URL`, `BW_ALERTE_MAIL`, les quinze
`…_PING_URL` de collecte et de modèles, `BW_MODEL_SELF_TEST_BLOQUANT`, les cinq
`BW_JIRA_*`, `BW_MODEL_CONTROLE_PING_URL`, `BW_AGRUME_PI_RAFALE_PING_URL`.
Fichier **inchangé depuis le 13/09**. ⇒ `bw_push_discord` reste **codé, testé,
muet**. `~/installer-webhook-discord.sh` attend toujours Yann.

ⓘ **Le correctif `--ipv4` du 07/10 n'a pas été sollicité cette nuit** (aucun ⛔ à
front ⇒ aucun push). Il reste **éprouvé** par les trois HTTP 200 des 09 et
10/10, et **aucun 429** n'apparaît nulle part. Trafic conforme à la normale
(2 à 7 messages/jour) : pas de runner qui s'emballe.

## 7. ⛔ Témoins du mélange : **cinquième nuit** sous la barre — la série a confirmé, et elle ne bouge plus

```
⛔ témoins du mélange : sur 7 539 balise-jours×échéance, le mélange fait
   4,4187 km/h contre 4,4167 pour le meilleur membre a priori
   (gain −0,0 %, mélange devant dans 49,2 % des cas) ;
   contre la moyenne UNIFORME, sur 1 114 : 4,3244 vs 4,4756 (gain 3,4 %)
```

```
gain contre le MEILLEUR MEMBRE a priori : 7,4 % → 5,5 % → −0,6 (07/10) → +2,5 (08/10) → −1,2 (09/10) → −0,1 (10/10) → −0,0 (11/10)
   « devant » dans : 49,2 % (07/10) → … → 50,1 % (09/10) → 49,1 % (10/10) → 49,2 % (11/10)
gain contre la moyenne UNIFORME         : 6,0 % → 4,9 → 4,8 → 3,1 (08/10) → 4,8 (09/10) → 3,2 (10/10) → 3,4 (11/10)
```

⛔ **Cinq nuits, moyenne +0,12 %** contre le meilleur membre a priori, contre
7,4 % puis 5,5 % auparavant. Et « devant » dans **moins d'une fois sur deux**
pour la **quatrième fois sur cinq nuits**. ⇒ **le mélange n'apporte plus rien
face au meilleur membre choisi a priori.** La série demandée le 10/10 a
confirmé, et elle est maintenant très plate : l'écart absolu de cette nuit est
de **0,0020 km/h** sur 7 539 cases.

✅ **Le gain contre la moyenne UNIFORME, lui, tient et remonte** : 3,4 %
(3,2 hier). La série **oscille** entre 3,1 et 4,8 depuis six nuits, elle ne
décline pas — la lecture du 08/10 (« quatrième recul consécutif ») reste
démentie. ⇒ **le mélange garde tout son sens contre une moyenne naïve** ; c'est
seulement contre le **meilleur membre** qu'il ne gagne plus.

ⓘ **L'erreur absolue baisse de 3,5 %** (4,5783 → 4,4187 km/h) : journée **moins
venteuse** qu'hier. Ce n'est donc pas un artefact de difficulté — le mélange
échoue à gagner aussi sur une journée facile.

⇒ ⚠️ **À poser à Yann, pour le deuxième jour : veut-il un motif Jira pour les
témoins du mélange ?** La consigne demandait d'attendre que la série confirme ;
**elle a confirmé deux fois.** Rien n'a été créé.

ⓘ Composition du mélange cette nuit : 7 970 balise×échéance avec poids sur 30 j
de cache — +6 h : 2 623 `bw_mix`, 415 témoins uniformes, 197 sans poids ;
+24 h : 2 555 / 392 / 98 ; +48 h : 2 553 / 414 / 264 (61,9 s).

## 8. Le reste du journal

- ✅ **Self-test du scoring : VERT** (lot S3, aucune lecture réelle, aucune
  écriture). Écart des deux mélanges : `mse_comb` 17,841 contre `mse_comb_vec`
  17,841 (**+0,00 %**), skill = 1,0 des deux côtés.
- ✅ **Stabilité des rangs : τ = 0,723 sur 54 cases** (0,709 / 53 le 10/10 ;
  0,751 / 57 le 09/10 ; 0,744 / 60 le 08/10). **La série de deux baisses est
  interrompue**, et le nombre de cases remonte d'une (60 → 57 → 53 → 54).
  À suivre, pas à conclure.
- ⚠️ **ρ hors [0, 1] : 381 balises sur 3 706** (349 le 10/10, 382 le 09/10,
  307 le 08/10). **Oscillation haute**, au niveau du 09/10. Les quatre nuits
  d'amélioration de fin septembre restent perdues.
- ⚠️ **6 écarts au recalcul indépendant** (5 le 10/10, 5 le 09/10, 4 le 08/10)
  — journée recalculée 2026-10-10, 16 strates, tirage de 20, graine
  462458130. **Tous en `fcstagrume`** et tous de la **même signature** : « ici
  None, base X — 0 ou 1 h appariée ici (< 6) mais la base porte une ligne » :
  `infoclimat:STATIC0133` (+24 h), `mf:05061009` (+48 h), `pioupiou:839`
  (agrume_pi +24 h), `windsmobi:ffvl-5027` (+24 h), `aemet:9207` (+6 h),
  `mf:84094001` (agrume_pi +6 h). ⓘ **Quatre nuits de suite la même signature,
  et le compte monte lentement (4 · 5 · 5 · 6)** : ce n'est pas du bruit, c'est
  un désaccord systématique sur le seuil des 6 heures appariées.
- **Murphy** : 66 281 triplets (balise × modèle × échéance), 64 213 décomposés,
  266 balises tenues dehors (doublon ou position suspecte), 0,9 s.
- **Duels appariés** : lead 6 → 65 179 lignes depuis le 11/09 (1 034 retirées) ;
  lead 24 → 23 988 lignes (395 retirées). ⓘ Cumul **tronqué** par la rétention
  de 30 j.
- **Événements** : **30 876 combinaisons publiables**, 29 919 écartées sous le
  quorum de 8.
- **Pression** : 17 935 lignes, 682 points de prévision portent `pmsl`,
  **862 appariées** (médiane 18,1 km) ; refusées : 207 hors rayon, 32 hors Δz,
  4 trop hautes.
- **Référence combinée** : **k médian 0,149** sur 3 706 balises / 3 819
  climatologisées (205,9 s de climatologie horaire).
- **Antécédent du biais** : 67 239 couples sur 30 j de cache (69,6 s) ; antécédent
  fin : 66 867 couples avec au moins une cellule qui parle.
- **Témoins du corrigé** : le vrai antécédent gagne **15,3 %**, celui d'une
  AUTRE balise **−5,6 %** ⇒ part imputable au site **20,9 points** (sur 9 152
  balise-jours). Témoin FIN : le S2 gagne 14,1 % sur le brut, le fin **+9,7
  points** de plus sur le S2 contre −1,9 aux cellules tournées ⇒ part du secteur
  et de l'heure **11,6 points** (sur 5 571).
- **Collecte** : 9 072 lignes, 1 956/1 956 points, **0 refus de quota, 0 groupe
  rendu VIDE**, 2 035 Ko en 10,1 min.
- **Accumulateurs** : 6 090 entrées écartées (`doublon_de`, lot L17), 346
  antérieures à la naissance de la balise (`notee_depuis`, lot L15-bis).
- **Observations** : 3 725 balises le jour, 3 761 la veille.
- **`mutations_memoire`** : ⚠️ **TROISIÈME nuit sans aucune ligne au journal.**
  Le relevé « 3 mutations non vues (2, 5, 13) » ne peut pas être revérifié ;
  dette antérieure, **statut inchangé faute de mesure**.
- `✅ terminé (736 130 lignes écrites en base)` ; `registre : 1 ligne écrite
  (2026-10-11, 4 975 s, jalon max 3 321 Mo, swap 2 129,5 Mo)`.

## 9. ✅ Les tickets : état vérifié par GET **avant** et **après**, et les trois commentaires du 10/10 sont ENFIN partis

GET `/rest/api/3/issue/<clé>?fields=summary,status` avant écriture, HTTP 200
sur les trois. Les trois sujets sont **ceux relevés le 07/10**, inchangés.

| ticket | statut | comm. avant | canal utilisé | comm. après |
|---|---|---|---|---|
| **KAN-3** `bw-pente-duree` | **Terminé** / `done` | 19 | `bw_jira_commenter KAN-3` (**délibéré**) | **20** ✅ |
| **KAN-4** `bw-pente-memoire` | **À faire** / `new` | 30 | `bw_jira_signaler bw-pente-memoire` | **31** ✅ |
| **KAN-5** `bw-purge-57014` | **À faire** / `new` | 13 | `bw_jira_signaler bw-purge-57014` | **14** ✅ |

**Ce que chaque commentaire porte** (tous trois annoncés comme un **rattrapage**
du 10/10, et portant donc les deux nuits) :

- **KAN-4** — jalon 3 321 Mo (−73), +521 au-dessus du seuil ; coût par ligne
  **1 667,8 o, plus bas des treize nuits** ; calcul à taux constant (−71,6 Mo
  imputables au coût par ligne, −1,3 Mo à la fenêtre) ; **démenti explicite de
  l'« amélioration de structure » du 10/10** (les trois jalons sont revenus
  au-dessus du seuil) ; **les trois conditions de fermeture, 1 sur 3** ; 21e
  nuit sans levier ; les six autres jalons ; `mutations_memoire` non mesurable.
- **KAN-5** — bloc purge **propre pour la 4e nuit** (129 233 l. / 8 tr., aucune
  tranche à 57014, aucune sonde, aucun « RESTENT ») ; **compteur 4 / 3** ; la
  bonne nouvelle (`bw_character_avance` ne revient pas) ; les **deux réserves**
  (le timeout change de requête, le `.sql` jamais joué) ; **la fermeture posée à
  Yann, non appliquée** ; et le fait qu'elle ne fermerait que la purge, pas la
  base sous tension.
- **KAN-3** — la durée **recule de 343 s**, marge 34,35 % → **38,58 %** ; la
  répartition 61/39 en miroir du 10/10 ; **le hors-étapes qui casse sa série
  monotone** ; le découplage temps/volume le plus net de la série ; le coût par
  ligne de `regime` à **12,94 ms** et le **compteur `bw-regime-sensibilite`
  remis à 0** ; l'aveuglement du 25e centile **et le fait qu'il a dit −55 s/nuit
  dans les deux situations opposées** ; remontée du garde **non lancée et non
  demandée** ; **réouverture non demandée**.

⛔ **Aucune création, aucune transition, aucune réouverture, aucune fermeture.**
Les trois statuts sont **identiques** après écriture (revérifiés par GET).

ⓘ **Les deux canaux ont été employés comme arbitré le 07/10.** Le contrôle de
07:30 s'étant tu, les jetons du jour étaient **libres** : `bw_jira_signaler` a
donc pu servir pour les deux motifs ouverts, et il a **posé les jetons**
(`cri.jira.bw-pente-memoire` et `cri.jira.bw-purge-57014` datent maintenant du
11/10). `bw_jira_commenter` a servi pour KAN-3, qui est en « Terminé » et que
`bw_jira_chercher` ne trouve pas (`statusCategory != Done`) — un
`bw_jira_signaler` sur ce motif **aurait créé un ticket neuf**. ✅ Vérifié :
`cri.jira.bw-pente-duree` est **toujours daté du 07/10**, le canal délibéré ne
touche pas le jeton du jour, comme prévu.

ⓘ **Technique de l'envoi** : les trois corps ont été écrits sur le **Mac**
(`/tmp/bw-11-10/`), encodés en base64 et passés au VPS **par l'entrée standard
de `ssh`**, décodés dans une variable shell. **Aucun fichier n'a été déposé sur
le VPS, pas même dans `/tmp`.**

## 10. Ce qui a été touché

**VPS — règle de LECTURE SEULE pleine et entière, respectée.** Huit commandes
`ssh`, toutes en lecture sauf les trois POST Jira : `date`, `tail -n 3` du
registre, `systemctl list-timers`, `journalctl` du contrôle, `journalctl -u
bw-model-score.service` (quatre passes avec `grep`/`sed`),
`controle_quotidien.py --verbeux`, `sed` dans `bw_jira.sh`, `ls -la` des deux
dossiers d'état, `sed -E "s/=.*//"` sur le `.env`, et **six GET** Jira (trois
avant, trois après). **Aucun `systemctl start/restart/daemon-reload`, aucun
`enable`, aucun SQL joué, aucun `rsync`, rien écrit dans `~/balise-watch` ni
dans `/etc`, aucun fichier déposé, pas même dans `/tmp`.**
⚠️ `controle_quotidien.py --verbeux` a été **relancé à la main** : c'est une
lecture (il n'écrit son jeton que s'il parle, et il s'est tu) — vérifié, les
jetons de `/var/lib/bw-model-verif` sont inchangés après la relance.
**Aucun secret lu par valeur** : le `.env` est **sourcé** (`set -a; . …;
set +a`) pour les GET et lu **par noms de variables seuls**. `bw_jira.sh` passe
par `curl -K -`, jamais `-u`.
**Écritures Jira : trois commentaires** (voir §9).

**Mac** : trois corps de commentaire dans `/tmp/bw-11-10/` (fichiers de
travail), cette note dans `notes-projet/verdict-pente-11-10.md`, **et les deux
miroirs manquants** `notes-projet/verdict-pente-09-10.md` et
`notes-projet/verdict-pente-10-10.md`. **Un commit local**, depuis la **racine
du dépôt serveur**. **Pas de `git push`.**

**Projet Claude** : cette note, **créée** (`project_read` a rendu « No doc »
avant écriture — vérifié, et confirmé par `project_info` : aucun
`verdict-pente-11-10.md` dans les 51 documents).

✅ **LA DETTE DE MIROIR GIT EST SOLDÉE.** Les notes du **09/10** et du **10/10**
n'existaient que côté projet, sans filet, depuis deux matins de déconnexion du
Mac. Elles sont déposées dans `notes-projet/` et commitées **avec** celle du
jour. Les trois sont désormais dans l'historique git. ⓘ Elles sont **reprises
telles quelles depuis le projet**, par `project_read`, sans retouche.

## 11. ⓘ L'horaire de la routine : **+5 h 51**, deuxième pire valeur de la série

Programmée pour **07:11:05 UTC**, tirée à **13:01:48 UTC**.

```
02–03/10  AUCUN TIR
04–06/10  retard jusqu'à 4 h 10
07/10     à l'heure
08/10     +2 h 10
09/10     +6 h 40   ← pire
10/10     +2 h 13
11/10     +5 h 51   ← deuxième pire
```

ⓘ **Le VPS est à l'heure, et il n'y est pour rien** : notation à **06:00:06**
(prochaine lundi 12/10 **05:57:03**), contrôle à **07:30:41** (prochain lundi
**07:30:13**). **Le trou est côté planification de la routine.**
✅ **Cette fois le retard n'a rien coûté** : le Mac était disponible à 15:02
(Paris) et le bridge a tenu tout le run — contrairement aux 09 et 10/10, où le
retard avait emporté la moitié du travail. ⚠️ **Mais c'est de la chance, pas une
garantie** : à 15:02 un dimanche le Mac de Yann n'a pas de raison d'être
allumé. **Un tir à l'heure vaudrait toujours mieux qu'un run réparé.**

## 12. Ce qui reste — et ce qui demande Yann

**Décisions, par ordre d'urgence :**

1. ⛔ **FERMER KAN-5 ? Le compteur est à 4 / 3** (deuxième jour où la question
   est posée). Quatre nuits consécutives sans 57014 dans le bloc purge, avec un
   nombre de lignes lisible à chaque fois (129 650 · 129 594 · 129 233, plus le
   `n_57014 = 0` du 08/10). La condition arbitrée est **dépassée**. ⚠️ **Deux
   réserves inchangées** : le `statement timeout` a **changé de requête** le
   10/10 (et n'est pas revenu cette nuit, ce qui ne prouve rien), et le
   `diagnostic_base_sous_tension` n'a **jamais été joué**. La cause profonde
   n'est pas mesurément réglée, seulement le symptôme sur la purge. *Un ticket
   fermé à tort vaut moins qu'un ticket ouvert.* ⇒ **Et s'il est fermé, il
   faudra dire où va « la base est sous tension », qui n'a pas de ticket.**
2. ⛔ **TRANCHER LES CAS DE POSITION — il reste QUATRE JOURS.** Les sept balises
   sont passées à **6 j** ; elles franchiront **10 j le 15/10** et le compte
   passera de **3 à 10**, avec un cri à front. À trancher : `2171` (38,9 km),
   `1388` (2 363 m), `STATIC0491` (1 159 m), **et `1333` qui sort du lot**
   (10 → 8 → 7 j). Ensuite `position_suspecte` + `position_note` sur
   `station_zone` par `.sql`.
3. ⛔ **Jouer `diagnostic_base_sous_tension_2026-09-29.sql`** (lecture seule,
   9 blocs, SQL Editor). **Douze jours d'attente**, et c'est la réserve n° 2 de
   la fermeture de KAN-5.
4. ⛔ **L'HORAIRE DE LA ROUTINE : +5 h 51**, deuxième pire valeur (voir §11). Le
   VPS est à l'heure. Cette fois le retard n'a rien coûté, mais c'est un coup de
   chance.
5. ⛔ **Lancer `~/installer-webhook-discord.sh`.** `BW_DISCORD_WEBHOOK_URL`
   toujours absente, 29e jour. ntfy reste **seul**, avec son quota anonyme
   dépendant du voisinage /64 d'OVH. ✅ Le `--ipv4` est éprouvé — mais un canal
   unique reste un canal unique.
6. ⚠️ **Un motif Jira pour les témoins du mélange ?** (deuxième jour.) La série
   a confirmé **deux fois** : cinq nuits à **+0,12 %** de moyenne contre le
   meilleur membre a priori, « devant » dans 49,2 % des cas, et l'écart absolu
   est tombé à 0,0020 km/h. ⓘ Le gain contre la moyenne **uniforme** tient
   (3,4 %) : le mélange reste utile, mais plus face au meilleur membre choisi
   d'avance. **Rien n'a été créé.**
7. ⚠️ **Instrumenter le bloc hors étapes de `run.sh` ?** ✅ **La demande perd son
   urgence** : le hors-étapes a cassé sa série monotone (−133,2 s après +175,5 s
   en quatre nuits). Elle **reste pertinente** — on ne sait toujours pas lequel
   des six postes bouge, dans un sens comme dans l'autre — mais ce n'était pas
   une dérive de fond. C'est une écriture dans `run.sh` : la décision est à toi.
8. ⓘ **Un champ de bilan de purge au registre ?** (question du 08/10.) Avec
   `lignes_effacees` et `tranches`, le §4 tiendrait en trois lignes et le
   compteur de KAN-5 se lirait sans ouvrir un journal.
9. ⓘ **Un motif Jira pour `bw_character_avance`**, ou cela reste-t-il dans
   « base sous tension » ? ⓘ Il n'est pas revenu cette nuit — la question est
   moins pressante, pas close.
10. ⓘ **Le cri de position : à front ou à état ?** (question du 01/10 ; il n'a
    pas crié ce matin, à juste titre.) Et **faut-il un motif Jira pour une panne
    de canal ?** (question du 30/09.)

**Ce que la surveillance regardera au prochain run :**

11. **La mémoire** : **1 667,8 o/ligne confirme-t-il, ou était-ce le symétrique
    du 1 720,6 du 08/10 ?** Et les trois jalons restent-ils au-dessus du seuil,
    ou le 10/10 reviendra-t-il ? C'est la question la plus ouverte du dossier.
12. **La durée** : 38,58 % de marge est le plus haut depuis le 05/10. Le
    hors-étapes **repart-il à la hausse** (il n'a eu qu'un seul recul) ?
13. **Le coût par ligne de `regime`** : 12,94 est le plus bas de la série, le
    compteur `bw-regime-sensibilite` est **à 0**. Il faudrait **deux hausses
    consécutives** pour que la question aille à Yann.
14. **KAN-5** : une **cinquième** nuit propre, ou le retour du 57014 ?
15. **La position, le 15/10** : le cri à front de 3 → 10 confirmées.
16. **Les écarts au recalcul** : 4 · 5 · 5 · **6**, toujours la même signature
    en `fcstagrume`. ⓘ **Le compte monte lentement et la signature ne change
    pas** : à regarder pour lui-même si une cinquième nuit l'augmente encore.
17. **τ** (0,723, la baisse s'interrompt) et **ρ hors [0, 1]** (381, haut) :
    séries à surveiller, aucune conclusion.
