# Verdict de pente du 14/10/2026 — **la nuit où le correctif `--ipv4` passe son premier vrai examen, et le réussit**. Un cri de position est parti : `ⓘ push parti (webhook, HTTP 200)`. ⛔ Le **57014 est revenu, sur une AUTRE requête** (`purge model_verif_daily`) alors que `model_score_zone` signe sa **septième nuit propre (7 / 3)** : la réserve n° 1 est démontrée une seconde fois. ⛔ Le coût par ligne de `regime` fait sa **troisième hausse consécutive** (critère `bw-regime-sensibilite` à **3 / 2**). ⚠️ Le troisième incident mémoire est **de retour** — la lecture d'hier n'a pas tenu une nuit. ✅ **L'échéance position du 15/10 est DÉMENTIE** : cinq des sept balises ont quitté la liste.

## 15:30 (Paris) — routine Balise Watch (tirée à 13:22:19 UTC pour 07:11:05 : **+6 h 11**, contre +52 min hier), lecture VPS complète, **trois écritures Jira**

**Étape 0 faite.** `git log --oneline --since=midnight` :

- dépôt serveur `PWA/balise-watch-server` : **aucun commit du jour** (dernier : `32ed215`, la note du 13/10)
- dépôt principal `surveillance balise` : **aucun commit du jour** (dernier : `379cc2f`, 13/10)
- `claude/verdict-pente-14-10.md` **absent** de la liste d'ouverture de session
- `claude/verdict-pente-13-10.md` lu **en entier**
- `notes-projet/README.md` relu — les quatre règles

⇒ **premier et seul run pente du jour. Rien à fusionner, aucun doublon.**

## 1. Les nuits, bout à bout

| | 09/10 | 10/10 | 11/10 | 12/10 | 13/10 | 14/10 |
|---|---|---|---|---|---|---|
| durée | 5 192 s | 5 318 s | 4 975 s | 5 029 s | 5 046 s | **5 032 s (−14)** |
| marge | 2 908 | 2 782 | 3 125 | 3 071 | 3 054 | **3 068 (+14)** |
| marge en % du garde | 35,90 % | 34,35 % | 38,58 % | 37,91 % | 37,70 % | **37,88 %** |
| `cpu_s` | 4 199,5 | 4 237,7 | 4 019,1 | 4 021,9 | 4 056,7 | **4 029,7 (−27,0)** |
| jalon max | 3 356 Mo | 3 394 | 3 321 | **3 444 (record)** | 3 422 | **3 416 (−6)** |
| au-dessus du seuil | +556 | +594 | +521 | +644 | +622 | **+616** |
| swap au pic | 2 145,1 | 2 088,1 | 2 129,5 | **2 595,3 (record)** | 2 091,8 | **2 417,0 (+325,2)** |
| pages sorties | 2 241 569 | 2 487 135 | 2 501 165 | 2 514 657 | 2 171 262 | **2 254 634 (+83 372)** |
| pic système | 3 615,2 | 3 608,5 | 3 619,9 | 3 616,1 | 3 595,4 | **3 612,1 (+16,7)** |
| fenêtre rejouée | 2 089 138 | 2 088 809 | 2 087 981 | 2 087 197 | 2 086 539 | **2 085 860 (−679)** |
| o / ligne rejouée | 1 684,4 | 1 703,8 | 1 667,8 | **1 730,2 (record)** | 1 719,7 | **1 717,2 (−2,5)** |
| incidents mémoire | 3 | 3 | 3 | 3 | **2** | **3 (retour)** |
| `n_57014` | 0 | 1 (hors purge) | 0 | 0 | 0 | **1 (hors `model_score_zone`)** |
| lancement / résultat | timer/success | ↳ | ↳ | ↳ | ↳ | **timer/success** |

Nuit **comparable** : `lancement=timer`, `exec_status=0`, `oom=0`,
`result=success`, **05:59:59 → 07:24:04**, `source=run.sh`,
`chevauchement_reduit=true`. Rien à écarter.
ⓘ Le départ **remonte** comme annoncé : 05:57:06 → 05:55:06 → **05:59:59**
(`bw-model-score.timer` prochaine **jeudi 05:57:41**). **Rien d'anormal.**

**Le contrôle de 07:30 a tiré à 07:30:44 et s'est TU** :

```
ⓘ 76 relevé(s), 55 comparable(s) ; durée : 10 points, pente -14 s/nuit ;
  mémoire : 10 points, pente -53 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate/négative, ou échéance hors horizon
```

⚠️ **CINQUIÈME MATIN DE SUITE À EXACTEMENT −53 Mo/nuit** (10, 11, 12, 13 et
14/10). La pente de durée **remonte vers zéro sans l'atteindre** : −55 → −36 →
**−14 s/nuit**. **Le 25e centile des différences reste aveugle** par
construction aux deux plus grosses hausses de la fenêtre.

⇒ **Aucun jeton du jour posé par le contrôle.** Vérifié dans les **deux**
dossiers avant écriture : `/var/lib/bw-model-verif` portait
`cri.jira.bw-pente-duree` du 17/09, `…memoire` du 23/09, `…purge-57014` du
06/10 ; `$HOME/.balise-watch-etat-alertes` portait `duree` du 07/10 et les deux
autres du **13/10**. **`bw_jira_signaler` était donc libre sur les trois motifs.**

## 2. ⛔ Mémoire : le **troisième incident revient**, la lecture d'hier n'a pas tenu une nuit

```
⛔ après le rejeu d'archive            : 3 056 Mo  (3 021 le 13/10)  ← +35
⛔ après le score par régime           : 2 914 Mo  (2 738 le 13/10)  ← +176, DE NOUVEAU AU-DESSUS
⛔ après l'oubli de la fenêtre rejouée : 3 416 Mo  (3 422 le 13/10)  ← −6
```

⛔ **CORRECTION EXPLICITE DE LA NOTE DU 13/10.** Elle relevait « **deux
incidents au lieu de trois** » et le passage du « score par régime » **sous le
seuil** de 2 800 Mo, en y voyant une première depuis le 10/10. **Il repasse
au-dessus dès la nuit suivante, et de 114 Mo.** ⇒ **Onzième usage en dix-sept
jours de la leçon « une nuit ne fait pas une pente »** — et c'est la **troisième
note consécutive** qui doit corriger la précédente.

Le jalon max reste le **troisième plus haut de toute la série** (3 444 le 12/10,
3 429 le 08/10) : le repli n'est que de 6 Mo, **on reste très haut**, +616
au-dessus du seuil.

Les neuf jalons, **quatre en hausse, cinq en recul** — aucune concentration :
agrégat quotidien **1 810 (−26)**, oubli fenêtre glissante **1 775 (+36)**,
oubli fenêtre rejouée **3 416 (−6)**, oubli du chemin J-0 **953 (−18)**,
relecture de l'archive **809 (−8)**, garde-fou de position **1 193 (−9)**,
mélange multi-modèle **1 180 (−12)**, rejeu d'archive **3 056 (+35)**, score par
régime **2 914 (+176)**.

**COÛT PAR LIGNE REJOUÉE : 1 717,2 o (−2,5).**

```
29/09 1 671,3 o · 30/09 1 692,6 · 01/10 1 685,6 · 02/10 1 689,2
03/10 1 706,4  · 04/10 1 697,4 · 05/10 1 717,2 · 06/10 1 689,7
07/10 1 717,0  · 08/10 1 720,6 · 09/10 1 684,4 · 10/10 1 703,8
11/10 1 667,8  · 12/10 1 730,2 · 13/10 1 719,7 · 14/10 **1 717,2**
  → fourchette 1 667,8–1 730,2 sur SEIZE nuits (±1,9 % autour de 1 699)
```

⚠️ **Toujours aucune pente, ni à la hausse ni à la baisse, sur seize nuits.** La
troisième valeur de suite dans la bande haute (1 717–1 730) **sans que la bande
se déplace**.

**Calcul à taux constant.** Au taux du **13/10** (1 719,7 o) la fenêtre de cette
nuit aurait rendu **3 420,9 Mo** ; elle rend **3 416**. Les **−4,9 Mo** sont
imputables au **coût par ligne** ; la fenêtre ne retire que **679 lignes**
(**−1,1 Mo**). Au taux du **29/09** (1 671,3 o) : **3 324,6 Mo** — nous sommes
**91,4 Mo au-dessus**.

⚠️ **SWAP : LA BANDE DE DOUZE NUITS EST DE NOUVEAU QUITTÉE.** Pic **2 417,0 Mo
(+325,2, soit +15,5 %)**, au-dessus de la bande **2,0–2,3 Go** tenue du 30/09 au
11/10 puis le 13/10 — mais **178 Mo SOUS le record** du 12/10 (2 595,3). Pages
sorties **2 254 634 (+83 372, soit +3,8 %)**. ⓘ **Les deux indicateurs vont dans
le même sens pour la deuxième nuit de suite.** `oom = 0`, pic système
**3 612,1 Mo (+16,7)**.

**Les trois conditions de fermeture de KAN-4 : 1 sur 3**, inchangé. Jalon
mesurément retombé → **NON** (3e plus haut de la série, +616 au-dessus du
seuil). Swap au pic ≈ 0 → **NON** (2 417,0 Mo, **en hausse**). Contrôle muet sur
`bw-pente-memoire` → **OUI**. ⇒ **le ticket reste ouvert.**

**Rien de déployé côté mémoire depuis `af25efb` (21/09) — 24e nuit sans
levier.** Remède inchangé : la **ligne en tuple** (`enquete-pente-10-09.md`
§2.6, ≈ −1 030 o/ligne), après la mesure `tuple` vs `namedtuple` à la sonde.
⚠️ **Seize nuits sans pente disent ce qu'il faut attendre du dossier** : ce n'est
pas une dérive qui monte, c'est un **plafond qu'il faut baisser**. Les gains sont
dans la **structure** (l'élagage de `units` avait rendu −124 Mo au lieu de
−1 500).

## 3. Durée : −14 s, et la signature s'inverse une **troisième** fois

```
durée  5 046 → 5 032 s  (−14)
marge  3 054 → 3 068 s  (+14)  ⇒ 37,70 % → 37,88 % du garde de 8 100 s
cpu_s  4 056,7 → 4 029,7 (−27,0)
```

⚠️ **L'ÉCONOMIE EST DU CALCUL, ET L'ATTENTE AUGMENTE.** Le processeur rend
**−27,0 s** pour **−14 s** d'horloge : il recule **deux fois plus vite** que la
durée, donc il y a environ **13 s d'attente en PLUS** qu'hier. Hier c'était du
calcul **en hausse** (cpu +34,8 pour +17 d'horloge) ; avant-hier **95 %
d'attente**. ⛔ **Trois nuits, trois signatures.**

Série : `5 192 · 5 318 · 4 975 · 5 029 · 5 046 · **5 032**`. La durée **oscille**
dans une bande de 4 821 à 5 318 s depuis dix nuits (**±5 %**) : ni plateau, ni
dérive, ni repli.

| étape | 11/10 | 12/10 | 13/10 | 14/10 |
|---|---|---|---|---|
| `regime` | 1 648,5 | 1 664,7 | 1 680,6 | **1 687,1 (+6,5)** |
| `glissant` | 974,1 | 958,0 | 988,4 | **938,7 (−49,7)** |
| `stabilite` | 312,0 | 309,0 | 309,4 | **346,1 (+36,7)** |
| `rejeu` | 73,4 | 81,5 | 78,6 | **84,7 (+6,1)** |
| somme des quatre | 3 008,0 | 3 013,2 | 3 057,0 | **3 056,6 (−0,4)** |
| hors étapes | 1 967,0 | 2 015,8 | 1 989,0 | **1 975,4 (−13,6)** |

⛔ **LES QUATRE ÉTAPES NE BOUGENT PAS** (−0,4 s sur une somme de 3 057) : les
**−14 s** de l'horloge sont à **97 % dans le hors-étapes** (−13,6). Hier le
mouvement était **entièrement dans les étapes** ; le 12/10, **90 % hors
étapes**. Sur trois nuits le hors-étapes a porté **90 %, puis −158 %, puis
97 %** du mouvement. ⇒ **on ne sait toujours pas lequel des six postes bouge.**

À l'intérieur des étapes, deux postes **se compensent presque exactement** :
`stabilite` **+36,7 s** contre `glissant` **−49,7 s**.

**Hors étapes :**

```
1 924,7 (06/10) · 1 984,0 · 1 991,2 · 2 051,6 · 2 100,2 (10/10) · 1 967,0 · 2 015,8 · 1 989,0 · 1 975,4 (14/10)
```

La série monotone **reste cassée** ; le hors-étapes **oscille comme le reste** et
demeure le poste le plus volatil. ⛔ **Le bloc n'est toujours pas instrumenté** —
publication, Murphy, événements, pression, duels, purge : six postes, **aucun
jalon de temps**. La demande d'instrumentation de `run.sh` reste ouverte (c'est
une **écriture**, elle attend Yann).

### ⛔ 3.1 `bw-regime-sensibilite` : **TROISIÈME HAUSSE CONSÉCUTIVE (3 / 2)**

Coût par ligne de `regime` (ms) :

```
13,39 (01/10) · 13,24 · 14,02 · 13,67 · 13,53 · 15,07 · 14,86 · 14,87
· 13,99 · 14,42 · 12,94 (11/10) · 13,02 · 13,14 · **13,20 (14/10)**
                                   +0,08   +0,12   +0,06
```

L'**arbitrage unique du 07/10** pose le critère comme **deux hausses
consécutives** (et non un niveau absolu). Il était à **2 / 2** hier ; il est à
**3 / 2** ce matin. ⇒ **Ce n'est plus un déclenchement de bord : la hausse se
répète.**

⛔ **Conformément à l'arbitrage, RIEN N'A ÉTÉ CRÉÉ : la question est reposée à
Yann.** Les deux éléments, rechiffrés :

- **POUR** : **trois** hausses consécutives, c'est le critère **et davantage**.
  La répétition écarte l'hypothèse du bruit d'une nuit.
- **CONTRE** : **le niveau reste bas.** 13,20 ms est le **4e plus bas des
  quatorze relevés** ; les trois hausses cumulées font **+0,26 ms (+2,0 %)**
  après un recul de −1,48 ms (−10,3 %) le 11/10 ; nous sommes encore **1,87 ms
  SOUS** le 15,07 du 06/10 qui avait motivé le critère, et 0,79 ms sous le 13,99
  du 09/10.

⇒ **Le critère est rempli à la lettre, trois fois ; l'ampleur ne ressemble
toujours pas à ce qu'il visait.** ⓘ Question de fond portée au commentaire :
faut-il un motif, ou faut-il **ajouter un plancher de niveau** au critère, qui ne
se déclencherait qu'au-dessus (par exemple) du niveau médian de la série ?

**Temps et volume sont découplés, dans les deux sens** : `lignes_regime`
**127 805 (−100, soit −0,08 %)** pour un temps de `regime` à **+0,4 %** ;
`lignes_glissant` **10 445 (−39, −0,37 %)** pour un `glissant` à **−5,0 %**. Coût
par ligne de `glissant` **89,87 ms** (94,28 hier, **−4,41**) après **+3,13**
hier. `lignes_score_zone` **138 250 (−139)**, `lignes_daily` **69 536 (−14)**.

**Remontée du garde : NON lancée, NON demandée.** Le contrôle n'en propose
aucune (pente négative, `proposition()` n'est pas atteinte). Garde actuel
**8 100 s (135 min)** pour un run de **83,9 min**. ⛔ `10-timeout-s3.conf`
**n'a pas été touché.**

**KAN-3 : réouverture NON demandée.** −14 s, marge à 37,88 %, durée dans sa bande
depuis dix nuits, étapes immobiles.

## 4. ⛔ Purge : **septième nuit propre sur `model_score_zone` (7 / 3)**, mais le 57014 revient **ailleurs**

```
⚠️ purge model_verif_daily : HTTP 500 — {"code":"57014", "message":"canceling
   statement due to statement timeout"}
→ purge model_score_zone : 131 391 ligne(s) effacée(s) en 8 tranche(s)
ⓘ purge model_character : rien avant le 2027-02-04 (première écriture
  2026-08-08, rétention 180 j) — aucune requête lancée.
```

**Sur `model_score_zone`, qui est LE motif suivi par KAN-5, le bloc est propre :**

- **aucune TRANCHE à 57014** (aucun `?as_of=eq.J&regime=eq.R` en HTTP 500)
- **aucune SONDE** (« plus vieille journée illisible » absente)
- **aucun « des lignes RESTENT »** — donc rien ne reste en base
- nombre de lignes **lisible** (131 391), **8 tranches** comme les six nuits
  précédentes

| nuit | état du bloc `model_score_zone` | compteur |
|---|---|---|
| 07→08 (2026-10-08) | `n_57014 = 0`, propre | 1 |
| 08→09 (2026-10-09) | propre, 129 650 l. / 8 tr. | 2 |
| 09→10 (2026-10-10) | propre, 129 594 l. / 8 tr. | 3 |
| 10→11 (2026-10-11) | propre, 129 233 l. / 8 tr. | 4 |
| 11→12 (2026-10-12) | propre, 129 534 l. / 8 tr. | 5 |
| 12→13 (2026-10-13) | propre, 132 089 l. / 8 tr. | 6 |
| 13→14 (2026-10-14) | **propre, 131 391 l. / 8 tr.** | **7** |

ⓘ Les **698 lignes** d'écart avec hier **ne sont pas un signal** : le volume
effacé suit le volume de la journée purgée (≈ 125 000–134 000).

### ⛔ 4.1 Ce qui change cette nuit, et qui compte plus que le compteur

`n_57014 = 1` au registre, et **ce 1 ne vient pas de `model_score_zone`** : il
vient de la purge de **`model_verif_daily`**, une requête qui **n'avait jamais
expiré** jusqu'ici.

⛔ **C'EST LA RÉSERVE N° 1 DÉMONTRÉE UNE SECONDE FOIS.** Elle est au dossier
depuis le 10/10 : *le `statement timeout` **change de requête** plutôt que de
disparaître.*

- **10/10** : il quitte la purge et apparaît sur `bw_character_avance`
- **14/10** : il quitte `bw_character_avance` (**416 829 accumulateurs avancés
  sur 416 829 envoyés**, propre pour la **4e** nuit) et apparaît sur **la purge
  de `model_verif_daily`**

⚠️ Trois nuits sans 57014 sur la purge n'avaient rien démontré les 03, 04 et
05/10 avant son retour le 06. **Sept nuits ne démontrent pas davantage que la
base n'est plus sous tension : elles démontrent que CETTE requête-ci ne la touche
plus.**

⇒ ⛔ **La condition de fermeture est largement dépassée (7 / 3), et elle n'est
pas appliquée.** La question est posée **pour le cinquième jour**, mais
l'argument **CONTRE s'est renforcé cette nuit** : le timeout a changé de requête
pour la **deuxième fois en cinq nuits**, et
`diagnostic_base_sous_tension_2026-09-29.sql` n'a **jamais été joué : QUINZE
JOURS**. *Un ticket fermé à tort vaut moins qu'un ticket ouvert.*
⚠️ **Et s'il est fermé, il faudra dire où va « la base est sous tension », qui
n'a toujours pas de ticket** — la purge de `model_verif_daily` qui expire cette
nuit n'a, elle, **aucun motif du tout**.

✅ Le contrôle s'est tu sur ce motif, et c'est **correct** : depuis le 07/10,
`constats()` lit `score.log` via `bilan_purge()` — avertissement **puis** bilan
chiffré ⇒ il se tait. Le faux « purge en échec » du 06/10 ne s'est pas
reproduit : **huitième nuit.**

## 5. ✅ Position : le cri est parti, et **l'échéance du 15/10 est DÉMENTIE**

```
⛔ position : 11 balise(s) divergent du gel (10 j lus), dont 2 CONFIRMÉE(S) (≥ 10 j)
   ⛔ pioupiou:2171          38 915 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE
   ⛔ infoclimat:STATIC0491   1 159 m · 10 j · nœud 0,01 CHANGE
   ·  pioupiou:1378  18 508 m · 9 j   ·  pioupiou:367  6 764 m · 9 j
   ·  pioupiou:1333  87 693 m · 4 j   ← continue de reculer (10 → 8 → 7 → 6 → 5 → 4)
   ·  84 (9 753 m) · 2139 (1 913) · 1618 (744) · 1766 (739) · 1698 (321) · 1710 (259) — toutes à 1 j
⛔ position : 2 balise(s) CONFIRMÉE(S) — cri déposé pour envoi
```

⛔ **CORRECTION EXPLICITE DES NOTES DES 09, 10, 11, 12 ET 13/10.** Elles
annonçaient, cinq matins de suite, que **sept balises** franchiraient 10 j **le
15/10** et que le compte passerait de **3 à 10**. **C'est faux.** Cette nuit,
**cinq des sept ont quitté la liste** (`1417`, `1375`, `1722`, `1562`, `1678`
sont absentes) ; il n'en reste que **deux à 9 j** (`1378` et `367`). Au mieux le
compte passera donc de **2 à 4** demain, pas de 3 à 10. ⇒ **Sixième démenti
d'une échéance annoncée** : l'extrapolation linéaire sur ce compteur **ne vaut
rien**, parce que la liste **se renouvelle** (six entrées neuves à 1 j cette
nuit).

⛔ **ET `pioupiou:1388` EST SORTIE DES CONFIRMÉES** — elle était à 10 j hier et
« s'éloignait ». Le journal de l'alerte le dit :
`pioupiou:1388 : rentree dans l'ordre (le referentiel et le gel se sont
rejoints, ou la balise n'est plus vue)`.

ⓘ **Le compte est passé de 3 à 2 ⇒ c'est un front ⇒ le cri est parti.** Réponse
partielle à la question ouverte depuis le 01/10 : **le cri est à front dans les
DEUX sens** — une sortie de liste crie autant qu'une entrée. Il reste à décider
s'il doit **recrier** pour une balise qui reste confirmée.

**Geste attendu de Yann** (inchangé, mais la liste a maigri) : trancher `2171`
(38,9 km) et `STATIC0491` (1 159 m), statuer sur `1333` qui **continue de sortir
du lot** (10 → 8 → 7 → 6 → 5 → **4 j**), puis poser `position_suspecte` +
`position_note` sur `station_zone` par `.sql`.

## 6. ✅ Le correctif `--ipv4` du 07/10 : **premier vrai examen, réussi**

```
2026-10-14T05:24:01Z ALERTE — score modeles — position des balises : …
2026-10-14T05:24:02Z ⓘ push parti (webhook, HTTP 200)
host=smtp.gmail.com … smtpstatus=250 … exitcode=EX_OK
```

✅ **C'EST LE PREMIER ⛔ À FRONT DEPUIS LE 07/10, DONC LE PREMIER PUSH RÉEL
DEPUIS LE CORRECTIF — ET IL EST PARTI EN HTTP 200.** Aucun `429` nulle part dans
le journal. Les trois cris perdus (30/09, 02/10, 07/10) ne se sont **pas**
reproduits : le `--ipv4` dans les trois appelants **tient**, et le code HTTP part
bien au journal comme prévu. ⓘ L'e-mail est parti aussi (`smtpstatus=250`).

⚠️ **`BW_DISCORD_WEBHOOK_URL` est TOUJOURS ABSENTE du `.env`.** Relevé par
**noms seuls** (`sed -E "s/=.*//"`, aucune valeur lue) : les 25 mêmes variables
qu'hier, fichier **inchangé depuis le 13/09 18:08**. ⇒ `bw_push_discord` reste
**codé, testé, muet** — et cette nuit il y avait justement un ⛔ à pousser.
`~/installer-webhook-discord.sh` attend toujours Yann : **32e jour**. ntfy reste
**seul canal push**, avec son quota anonyme dépendant du voisinage /64 d'OVH.

## 7. ⚠️ Témoins du mélange : repli — et l'erreur absolue dit pourquoi

```
⛔ témoins du mélange : sur 7 611 balise-jours×échéance, le mélange fait
   3,245 km/h contre 3,3196 pour le meilleur membre a priori
   (gain 2,2 %, mélange devant dans 50,0 % des cas) ;
   contre la moyenne UNIFORME, sur 1 124 : 3,3217 vs 3,4858 (gain 4,7 %)
```

```
gain contre le MEILLEUR MEMBRE : 7,4 % → 5,5 → −0,6 (07/10) → +2,5 → −1,2 → −0,1 → −0,0 → +1,6 → +3,1 (13/10) → **+2,2 (14/10)**
« devant » dans : 49,2 % → 50,1 → 49,1 → 49,2 → 50,1 → 51,6 → **50,0 %**
gain contre la moyenne UNIFORME : 6,0 % → 4,9 → 4,8 → 3,1 → 4,8 → 3,2 → 3,4 → 4,7 → 6,5 → **4,7 %**
```

⚠️ **La remontée de deux nuits s'arrête**, sur les deux fronts : **+2,2 %**
contre le meilleur membre (contre +3,1 hier) et **4,7 %** contre la moyenne
uniforme (contre 6,5). Le mélange est devant dans **exactement 50,0 %** des cas.
⇒ **Mais la valeur reste POSITIVE sur les deux mesures**, et la décision du
12/10 de **ne pas** créer de motif Jira est maintenue.

ⓘ **L'erreur absolue remonte de 11,6 %** (2,908 → 3,245 km/h) : journée **plus
venteuse** après deux journées calmes. ✅ **C'est la troisième confirmation de la
leçon du 12/10** : l'indicateur **suit la météo du jour** autant que la qualité
du mélange. Le gain baisse quand l'erreur absolue monte, exactement comme le
07/10. **Toute lecture de cette série doit passer par l'erreur absolue.**

ⓘ Composition : 7 979 balise×échéance avec poids sur 30 j de cache — +6 h :
2 639 `bw_mix`, 417 témoins uniformes, 194 sans poids ; +24 h : 2 563 / 393 /
93 ; +48 h : 2 562 / 414 / 259 (64,0 s).

## 8. Le reste du journal

- ✅ **Self-test du scoring : VERT** (lot S3, aucune lecture réelle, aucune
  écriture). Écart des deux mélanges : `mse_comb` 17,841 contre `mse_comb_vec`
  17,841 (**+0,00 %**). `rms(perm)/rms(clim)` 2,198, dans [1,0 ; 3,0].
- ✅ **Stabilité des rangs : τ = 0,756 sur 62 cases** (0,735 / 56 le 13/10 ;
  0,742 / 50 le 12/10). ⓘ **Les deux séries montent ensemble cette fois** : τ au
  plus haut de la semaine et l'échantillon aussi (60 → 57 → 53 → 54 → 50 → 56 →
  **62**). À suivre, pas à conclure.
- ⛔ **ρ hors [0, 1] : 475 balises sur 3 706** (437 le 13/10, 413 le 12/10, 381
  le 11/10, 349 le 10/10, 382 le 09/10, 307 le 08/10). ⛔ **NOUVEAU PLUS HAUT
  pour la deuxième nuit de suite, et CINQUIÈME hausse sur SIX nuits** : **+54,7 %
  depuis le 08/10**, soit 12,8 % des balises. C'est **la seule série du journal
  qui monte franchement et sans démenti** — six points désormais, et la pente ne
  s'est pas cassée une seule fois depuis le 10/10. ⓘ **C'est le candidat le plus
  net à un motif neuf, et il mûrit.** Rien n'a été créé : la décision engage,
  elle est à Yann (§12).
- ⚠️ **6 écarts au recalcul indépendant** (7 le 13/10, 5 le 12/10) — journée
  recalculée **2026-10-13**, 10 balise-jours comparés dont 10 sous le seuil de
  6 h. **Tous en `fcstagrume`** et tous de la **même signature** : `aemet:9263X`
  (agrume_pi +6 h), `infoclimat:000S0` (agrume +6 h), `pioupiou:2084`
  (agrume_pi +48 h), `windsmobi:ffvl-2129` (agrume_pi +24 h), `aemet:9812M`
  (agrume_pi +24 h), `mf:74136005` (agrume_pi +6 h).
  ⓘ **Septième nuit de suite la même signature** (4 · 5 · 5 · 6 · 5 · 7 · **6**) ;
  les balises concernées **changent chaque nuit** : ce n'est pas un lot fixe,
  c'est un **désaccord systématique sur le seuil des 6 heures appariées**.
- **Murphy** : 66 110 triplets, 64 170 décomposés, 266 balises tenues dehors
  (doublon ou position suspecte), 0,9 s.
- **FDR** : brut 6 951 tests, 1 793 survivants à BH α = 0,1, 100 rangs retirés
  sur 1 104 publiés ; corrigé 6 647 tests, 1 180 survivants, 114 rangs retirés
  sur 638.
- **Duels appariés** : lead 6 → 65 209 lignes depuis le 14/09 (899 retirées) ;
  lead 24 → 24 001 lignes (341 retirées). ⓘ Cumul tronqué par la rétention 30 j.
- **Événements** : **31 422 combinaisons publiables**, 29 342 écartées sous le
  quorum de 8 ; 40 261 lignes en base, 38 717 non publiées.
- **Pression** : 17 857 lignes, 682 points de prévision portent `pmsl`,
  **859 appariées** (médiane 18,1 km) ; refusées : 208 hors rayon, 32 hors Δz,
  4 trop hautes.
- **Référence combinée** : **k médian 0,143** sur 3 706 balises / 3 819
  climatologisées (206,0 s de climatologie horaire).
- **Publication** : `model_scores.json` 121 072 Ko, `model_scores_light.json`
  7 303 Ko (528 Ko gzippé), `model_events.json` 8 772 Ko, `model_murphy.json`
  25 407 Ko (2 662 Ko gzippé).
- **Manches** : 47 nuits suivies depuis le 24/08, 713 cases zone×lead×modèle avec
  au moins une manche gagnée.
- **Accumulateurs** : 5 383 entrées écartées (`doublon_de`, lot L17), 318
  antérieures à la naissance de la balise (`notee_depuis`, lot L15-bis).
- **Rejeu d'archive** : 2 085 860 balise-jours sur 30 journées (0 rejouée cette
  nuit, 0 vide, 4 358 balise-jours écartés) en 84,7 s.
- **Observations** : 3 739 balises le jour, 3 734 la veille.
- **`mutations_memoire`** : ⚠️ **SIXIÈME nuit sans aucune ligne au journal.**
  Le relevé « 3 mutations non vues (2, 5, 13) » ne peut pas être revérifié ;
  dette antérieure, **statut inchangé faute de mesure**.
- `✅ terminé (682 827 lignes écrites en base)` (663 442 le 13/10) ; `registre :
  1 ligne écrite (2026-10-14, 5 032 s, jalon max 3 416 Mo, swap 2 417,0 Mo)`.
- ⓘ `→ model_verif_collect_part : 3 ligne(s)`.

## 9. ✅ Les tickets : état vérifié par GET **avant** et **après**, trois commentaires

GET `/rest/api/3/issue/<clé>?fields=summary,status,comment` avant écriture,
HTTP 200 sur les trois. Les trois sujets sont **ceux relevés le 07/10**,
inchangés.

| ticket | statut | comm. avant | canal utilisé | comm. après |
|---|---|---|---|---|
| **KAN-3** `bw-pente-duree` | **Terminé** / `done` | 22 | `bw_jira_commenter KAN-3` (**délibéré**) | **23** ✅ |
| **KAN-4** `bw-pente-memoire` | **À faire** / `new` | 33 | `bw_jira_signaler bw-pente-memoire` | **34** ✅ |
| **KAN-5** `bw-purge-57014` | **À faire** / `new` | 16 | `bw_jira_signaler bw-purge-57014` | **17** ✅ |

**Ce que chaque commentaire porte :**

- **KAN-4** — jalon **3 416 Mo (−6)**, 3e plus haut de la série, +616 au-dessus
  du seuil ; ⛔ **le troisième incident est de retour** (« le score par régime »
  à 2 914 Mo, +176, de nouveau au-dessus) et **la lecture du 13/10 est corrigée
  explicitement** ; les neuf jalons chiffrés (4 en hausse, 5 en recul, aucune
  concentration) ; coût par ligne **1 717,2 o (−2,5)** et **seize nuits sans
  pente** (±1,9 %) ; calcul à taux constant (−4,9 Mo imputables au coût par
  ligne, −1,1 Mo à la fenêtre ; +91,4 Mo au-dessus du taux du 29/09) ; ⚠️ **swap
  2 417,0 Mo (+325,2), sortie de la bande de douze nuits mais 178 Mo sous le
  record**, les deux indicateurs convergents pour la 2e nuit ; les trois
  conditions de fermeture **1 sur 3** ; **24e nuit sans levier** et la ligne en
  tuple ; `mutations_memoire` non mesurable (6e nuit) ; **le contrôle qui annonce
  −53 Mo/nuit pour la 5e fois de suite**.
- **KAN-5** — bloc `model_score_zone` **propre pour la 7e nuit** (131 391 l. /
  8 tr., aucune tranche à 57014, aucune sonde, aucun « RESTENT ») ; le
  **compteur nuit par nuit, 7 / 3** ; ⛔ **le 57014 revenu sur `purge
  model_verif_daily`**, requête qui n'avait jamais expiré, avec la **réserve n° 1
  démontrée une seconde fois** (10/10 `bw_character_avance`, 14/10
  `model_verif_daily`) ; `bw_character_avance` propre (416 829 / 416 829, 4e
  nuit) ; le `.sql` **jamais joué — quinze jours** ; **la fermeture posée à Yann,
  non appliquée**, avec l'argument CONTRE **renforcé** ; et le fait qu'elle ne
  fermerait que la purge par tranches, pas la base sous tension — qui n'a
  toujours pas de ticket, pas plus que `model_verif_daily`.
- **KAN-3** — durée **−14 s** (5 032 s, marge **37,88 %**) ; **l'économie est du
  calcul et l'attente augmente** (cpu −27,0 pour −14 d'horloge), **troisième
  signature différente en trois nuits** ; ⛔ **les quatre étapes immobiles
  (−0,4 s) et 97 % du mouvement hors étapes**, avec `stabilite` +36,7 contre
  `glissant` −49,7 qui se compensent ; le tableau des étapes et du hors-étapes,
  la série monotone cassée et le bloc **non instrumenté** ; ⛔ **le coût par ligne
  de `regime` à 13,20 ms = 3e hausse consécutive ⇒ critère
  `bw-regime-sensibilite` à 3 / 2**, avec **le POUR et le CONTRE** (4e plus bas
  des quatorze relevés, +2,0 % cumulé, encore 1,87 ms sous le 15,07 du 06/10) et
  ⓘ **la question du plancher de niveau** ; le découplage temps/volume dans les
  **deux** sens ; l'aveuglement du 25e centile et la pente de durée qui remonte
  vers zéro (−55 → −36 → −14) ; remontée du garde **non lancée, non demandée** ;
  **réouverture non demandée**.

⛔ **Aucune création, aucune transition, aucune réouverture, aucune fermeture.**
Les trois statuts sont **identiques** après écriture (revérifiés par GET).

ⓘ **Les deux canaux ont été employés comme arbitré le 07/10.** Le contrôle
s'étant tu, les jetons du jour étaient **libres** : `bw_jira_signaler` a servi
pour les deux motifs ouverts et a **posé les jetons**
(`cri.jira.bw-pente-memoire` et `cri.jira.bw-purge-57014` datent maintenant du
**14/10 15:28**). `bw_jira_commenter` a servi pour KAN-3, en « Terminé » — un
`bw_jira_signaler` sur ce motif **aurait créé un ticket neuf**. ✅ Vérifié après
coup : `cri.jira.bw-pente-duree` est **toujours daté du 07/10** côté `$HOME` et
du **17/09** côté `/var/lib` — le canal délibéré ne touche pas le jeton du jour.

ⓘ **Technique de l'envoi** : les trois corps ont été écrits sur le **Mac**
(`/tmp/bw-14-10/`), encodés en base64 et passés au VPS **par l'entrée standard
de `ssh`**, décodés dans une variable shell. **Aucun fichier n'a été déposé sur
le VPS** en dehors des `mktemp -d` internes à `bw_jira_http`, effacés par la
fonction elle-même (vérifié).

## 10. Ce qui a été touché

**VPS — règle de LECTURE SEULE pleine et entière, respectée.** Dix commandes
`ssh`, toutes en lecture sauf les trois POST Jira : `date -u`, `tail -n 3` du
registre, `systemctl list-timers`, `journalctl` du contrôle, plusieurs passes de
`journalctl -u bw-model-score.service` avec `grep`/`sed`,
`controle_quotidien.py --verbeux`, `sed`/`grep` dans `bw_jira.sh`, `ls -la` des
deux dossiers d'état, `sed -E "s/=.*//"` sur le `.env`, et **six GET** Jira
(trois avant, trois après).
**Aucun `systemctl start/restart/daemon-reload`, aucun `enable`, aucun SQL joué,
aucun `rsync`, rien écrit dans `~/balise-watch` ni dans `/etc`.**
⚠️ `controle_quotidien.py --verbeux` a été **relancé à la main** : c'est une
lecture (il n'écrit son jeton que s'il parle, et il s'est tu) — vérifié, les
jetons de `/var/lib/bw-model-verif` sont **inchangés** après la relance (17/09,
23/09, 06/10).
**Aucun secret lu par valeur** : le `.env` est **sourcé** (`set -a; . …;
set +a`) et lu **par noms de variables seuls**. `bw_jira.sh` passe par
`curl -K -`, jamais `-u`.
**Écritures Jira : trois commentaires** (voir §9).

**Mac** : trois corps de commentaire dans `/tmp/bw-14-10/` (fichiers de
travail), cette note dans `notes-projet/verdict-pente-14-10.md`. **Un commit
local**, depuis la **racine du dépôt serveur**. **Pas de `git push`.**

**Projet Claude** : cette note, **créée** (absente de la liste d'ouverture de
session).

## 11. ⚠️ L'horaire de la routine : **+6 h 11**

Programmée pour **07:11:05 UTC**, tirée à **13:22:19 UTC**.

```
02–03/10  AUCUN TIR
04–06/10  retard jusqu'à 4 h 10
07/10     à l'heure
08/10     +2 h 10
09/10     +6 h 40
10/10     +2 h 13
11/10     +5 h 51
12/10     +10 h 59   ← pire valeur de la série
13/10     +52 min    ← meilleur depuis le 07/10
14/10     +6 h 11
```

⚠️ **Le +52 min d'hier n'était pas une tendance** — la note du 13/10 le disait
explicitement, et elle avait raison. Sept matins sur treize ont dérivé, deux
n'ont pas tiré. ⓘ **Le VPS est à l'heure, et il n'y est pour rien** : notation à
**05:59:58** (prochaine jeudi **05:57:41**), contrôle à **07:30:44** (prochain
jeudi **07:30:18**). **Le trou est côté planification de la routine**, et il
reste le premier risque du dispositif : il a déjà emporté la moitié du travail
les 09 et 10/10.

## 12. Ce qui reste — et ce qui demande Yann

**Décisions, par ordre d'urgence :**

1. ⛔ **`bw-regime-sensibilite` : LE CRITÈRE EST À 3 / 2.** Troisième hausse
   consécutive du coût par ligne de `regime` (12,94 → 13,02 → 13,14 → **13,20
   ms**). L'arbitrage du 07/10 demande de **reposer la question sans rien
   créer** : c'est fait. ⚠️ **Mais le niveau reste bas** — 4e plus bas des
   quatorze relevés, **+2,0 %** cumulé, encore **1,87 ms sous** le 15,07 du
   06/10 qui a motivé le critère. ⇒ Faut-il un motif, ou faut-il **ajouter un
   plancher de niveau** au critère (il ne se déclencherait qu'au-dessus de la
   médiane de la série, par exemple) ? **Rien n'a été créé.**
2. ⛔ **FERMER KAN-5 ? Le compteur est à 7 / 3**, cinquième jour où la question
   est posée. ⚠️ **Mais l'argument CONTRE s'est renforcé cette nuit** : le
   `statement timeout` a **changé de requête pour la deuxième fois en cinq
   nuits** (`purge model_verif_daily`, qui n'avait jamais expiré). Sept nuits
   propres démontrent que **cette requête-ci** ne touche plus la base, pas que la
   base n'est plus sous tension. ⇒ **Ma lecture : ne pas fermer.** Et s'il est
   fermé, il faut dire où va « la base est sous tension », qui n'a pas de
   ticket — et où va `model_verif_daily`, qui n'a aucun motif.
3. ⛔ **Jouer `diagnostic_base_sous_tension_2026-09-29.sql`** (lecture seule,
   9 blocs, SQL Editor). **Quinze jours d'attente**, et c'est la réserve n° 2 de
   la fermeture de KAN-5 — réserve qui vient de gagner un argument.
4. ⚠️ **ρ hors [0, 1] : 475 / 3 706 (12,8 %), NOUVEAU PLUS HAUT pour la 2e nuit,
   5e hausse sur six nuits, +54,7 % depuis le 08/10.** C'est **la seule série du
   journal qui monte sans démenti**, et elle a maintenant **six points**. ⇒ **Le
   candidat le plus net à un motif neuf, et il mûrit.** Veux-tu un motif
   `bw-rho-hors-bornes` ? **Rien n'a été créé** (la création engage).
5. ⛔ **Trancher les cas de position — mais l'urgence est tombée.** ✅
   **L'échéance du 15/10 est DÉMENTIE** : cinq des sept balises ont quitté la
   liste, il n'en reste **deux à 9 j**, donc le compte passera au mieux de **2 à
   4** demain, pas de 3 à 10. Reste à trancher `2171` (38,9 km) et `STATIC0491`
   (1 159 m), et à statuer sur `1333` qui **continue de sortir du lot** (10 → 8 →
   7 → 6 → 5 → **4 j**). Puis `position_suspecte` + `position_note` sur
   `station_zone` par `.sql`. ⓘ **Leçon : l'extrapolation linéaire sur ce
   compteur ne vaut rien** — la liste se renouvelle (six entrées neuves à 1 j
   cette nuit). Cinq notes l'avaient annoncée, elle n'a pas eu lieu.
6. ⚠️ **La mémoire ne se détend pas : elle oscille.** Le troisième incident est
   **revenu**, le swap **ressort** de sa bande (2 417,0 Mo, +325,2), le jalon
   reste le **3e plus haut** (3 416 Mo, +616) et le coût par ligne **n'a toujours
   aucune pente sur seize nuits** (±1,9 %). **24e nuit sans levier** depuis
   `af25efb` (21/09). ⇒ **Ce n'est pas une dérive qu'on attend, c'est un plafond
   qu'il faut baisser** : la **ligne en tuple** (≈ −1 030 o/ligne) après la mesure
   `tuple` vs `namedtuple` à la sonde.
7. ⛔ **Lancer `~/installer-webhook-discord.sh`.** `BW_DISCORD_WEBHOOK_URL`
   toujours absente, **32e jour** — et cette nuit il y avait justement un ⛔ à
   pousser. ✅ Bonne nouvelle en face : le `--ipv4` a tenu son premier vrai
   examen (HTTP 200), donc ntfy **fonctionne** ; mais il reste **seul**.
8. ⚠️ **Instrumenter le bloc hors étapes de `run.sh` ?** La demande reste
   ouverte et **l'argument revient en sa faveur** : cette nuit les quatre étapes
   sont **immobiles** (−0,4 s) et **97 % du mouvement est hors étapes**. Sur
   trois nuits le hors-étapes a porté 90 %, −158 %, puis 97 % : on ne sait
   toujours pas lequel des six postes bouge. C'est une écriture dans `run.sh` :
   la décision est à toi.
9. ✅ **Un motif Jira pour les témoins du mélange ? NON — la question reste
   close.** Repli à **+2,2 %** contre le meilleur membre et **4,7 %** contre la
   moyenne uniforme, devant dans **50,0 %** des cas : les deux restent positifs.
   ⓘ Et l'erreur absolue est remontée de 11,6 % (journée plus venteuse) :
   **troisième confirmation** que l'indicateur suit la météo du jour.
10. ⓘ **Le cri de position : à front, dans les DEUX sens.** La question du 01/10
    est à moitié répondue : une **sortie** de liste crie (`1388 : rentrée dans
    l'ordre`). Reste à décider s'il doit **recrier** pour une balise qui **reste**
    confirmée.
11. ⓘ **Un champ de bilan de purge au registre ?** (question du 08/10.) Avec
    `lignes_effacees` et `tranches`, le §4 tiendrait en trois lignes. ⚠️ Et il
    faudrait **nommer la requête** qui porte le `n_57014` : cette nuit le `1` du
    registre ne vient pas de `model_score_zone`, et rien dans le registre ne le
    dit.
12. ⓘ **Faut-il un motif Jira pour une panne de canal ?** (question du 30/09.)
    **Un motif pour `bw_character_avance` ?** — absent pour la 4e nuit, la
    question est moins pressante, pas close.

**Ce que la surveillance regardera au prochain run :**

13. **Le coût par ligne de `regime`** : **3 / 2 atteint.** Une **quatrième
    hausse** en ferait une vraie pente et changerait la nature de la question ; un
    recul remettrait le compteur à 0. C'est la question n° 1 de demain.
14. **Le 57014** : revient-il sur `model_verif_daily`, repart-il ailleurs, ou
    `model_score_zone` signe-t-il une **huitième** nuit propre ?
15. **ρ hors [0, 1]** : **475, deux plus hauts d'affilée.** Une sixième hausse
    sur sept nuits ferait de cette série la première vraie pente du journal.
16. **La mémoire** : le troisième incident **repart-il** ? Le swap **rentre-t-il**
    dans la bande 2,0–2,3 Go ? Le jalon retombe-t-il sous 3 400 ?
17. **La position, le 15/10** : le compte passe-t-il de **2 à 4** (`1378` et
    `367` à 9 j) — et le cri repart-il à front ?
18. **La durée** : la signature **s'inverse-t-elle une quatrième fois** ? Trois
    nuits de suite, calcul/attente et étapes/hors-étapes ont changé de camp.
19. **`mutations_memoire`** : une septième nuit muette, ou le retour du relevé ?
20. **L'horaire** : **+6 h 11** après +52 min. Sept matins de dérive sur treize.
