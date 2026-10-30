# Verdict de pente du 30/10/2026 — ✅ **Le critère de fermeture de KAN-5 est REMPLI depuis le 29/10 : quatre nuits de purge propres d'affilée, compteur 4 / 3. Ta décision est attendue.** ⛔ **R2 a redépassé le palier gratuit en une nuit (10,291 Go), exactement comme annoncé le 28/10.** ✅ **Et le correctif webhook `--ipv4` est CONFIRMÉ pour la première fois : « push parti, HTTP 200 » les deux nuits.** ⛔ **La routine n'a PAS tiré le 29/10 : +23 h 18, verdict jamais rendu.**

⛔ **Cette note couvre DEUX nuits.** Programmée pour le 29/10 à 07:09:05 UTC, la
routine a été tirée le **30/10 à 06:27:01 UTC**, soit **+23 h 18** — le pire
retard de la série, et en pratique un **matin sauté** : le verdict du 29/10
n'a jamais été rendu, et **la question de fermeture de KAN-5 posée le 28/10
pour « demain » est restée sans réponse faute d'avoir été posée.** Les deux
nuits (29 et 30/10) sont relevées ici.

Cinq faits, dans l'ordre d'importance. **(1)** ✅ **Le critère écrit de
fermeture de KAN-5 est REMPLI.** La purge de `model_score_zone` est propre de
bout en bout pour la **quatrième nuit d'affilée** (27, 28, 29, 30/10) :
143 625 puis 147 216 lignes en 8 tranches, **aucune** tranche en échec,
**aucun** défaut de sonde. Le compteur passe **2 / 3 → 3 / 3 (le 29/10, donc
hier) → 4 / 3**. ⚠️ Le registre porte `n_57014 = 1` les **deux** nuits, mais
**pas dans la purge** : les deux lignes sont sur `rpc/bw_character_avance`, et
la reprise a abouti à **100 %** les deux fois. **Rien n'est fermé : c'est Yann
qui tranche.** **(2)** ⛔ **R2 a redépassé le palier gratuit, et en une seule
nuit** : 9,564 → **10,291 Go (102,9 %)** le 29/10, **10,276 Go (102,8 %)**
aujourd'hui. L'avertissement du 28/10 (« une nuit comme celle-ci et le palier
est redépassé ») est **vérifié dès le lendemain**. `bw-garde-fou-r2` repasse en
**code 1** (2 consécutifs) — comportement normal. **(3)** ✅ **Le correctif
webhook `--ipv4` est CONFIRMÉ, pour la première fois depuis son déploiement** :
`ⓘ push parti (webhook, HTTP 200)` les **deux** nuits, **zéro** HTTP 429 ntfy,
et le mail est parti aussi (`exitcode=EX_OK`). Ce n'est plus « ni confirmé ni
mis en défaut » : il y avait quelque chose à envoyer, et c'est parti.
**(4)** ⓘ **La question du 27/10 sur `agrume/grille` est pratiquement
refermée** : le préfixe est revenu à **766 présentes / 766 réclamées** et
**5,323 Go**, et la ligne « 28 suppression(s) ratée(s) » a **disparu**. La
fenêtre glissante a rendu puis repris : c'était le **mécanisme**, pas un geste
humain. **(5)** ✅ **La durée ne bouge plus** : 4 927 → 4 921 → 4 934 s, soit
**13 s d'amplitude sur trois nuits** — le passage le plus plat du mois.

⛔ **KAN-4 reste ouvert** : jalon à **3 400 Mo, +600 Mo au-dessus du seuil**, et
swap au pic à **2 149,3 Mo**. ✅ Un seul point favorable, et petit : le jalon
« score par régime » repasse **sous** le seuil (2 665 puis 2 633 Mo), donc les
`incidents` mémoire passent de **3 à 2**.

⚠️ **Et un démenti net de la note du 28/10** : les onze balises de position
annoncées à 10 j pour le 31/10 **n'y seront pas** — **sept d'entre elles ont
quitté la liste**, il n'en reste que quatre.

## 07:30–07:55 (Paris, CET) — routine Balise Watch, run COMPLET sur deux nuits

**Étape 0 : faite en entier, avant toute autre chose.**

- `git log --oneline --since=midnight` dans `balise-watch-server` **et** dans
  `surveillance balise` : **aucun commit aujourd'hui** dans les deux dépôts
  ⇒ aucun autre run n'a tourné ce matin. Dernier commit serveur :
  **`bec3636`** (le miroir du 28/10) — **rien depuis**, ce qui confirme qu'il
  n'y a pas eu de run le 29/10.
- `project_read` de `claude/verdict-pente-30-10.md` : **absent** ⇒ cette note
  est une **création**, pas une fusion. `claude/verdict-pente-29-10.md` :
  **absent lui aussi** ⇒ la routine du 29/10 n'a rien écrit.
  `claude/verdict-pente-28-10.md` lu en **entier**.
- `notes-projet/README.md` relu : les quatre règles.
- ⛔ **État des miroirs git, vérifié et non arrangé** : `verdict-pente-24-10.md`
  **toujours absent** ; `verdict-pente-26-10.md` **toujours non suivi par git**
  (`?? notes-projet/verdict-pente-26-10.md`) ; `verdict-pente-29-10.md`
  **absent, et c'est normal** — il n'y a pas eu de run. **Rien fabriqué.**
- ⚠️ **Risque de collision aujourd'hui** : l'occurrence du 29/10 ayant été
  tirée ce matin à 06:27 UTC, celle du **30/10 à 07:09 UTC** peut encore
  partir et produire un **second run le même jour**. Cette note est donc en
  **section horodatée** (règle n°2) : un second run doit **fusionner**, pas
  remplacer.

## 1. Le relevé des deux nuits

`lancement = timer` · `result = success` · `exec_status = 0` · `oom = 0` — pour
les **deux** nuits. Self-test du scoring **VERT** les deux nuits (les cinq
contrôles : (a) à 1,0 sur les deux références, (b) permuté à 2,198 dans la
fourchette, skill contre persistance à −2,2604). Relevés **comparables** : le
verdict porte.

Nuit du 28→29/10 : début 04:56:41, fin 06:18:51 (CET).
Nuit du 29→30/10 : début 04:57:06, fin 06:19:29 (CET).
Contrôles passés à **07:31:05** et **07:30:08** CET, suivant armé pour le
**31/10 à 07:30:43 CET**.

| | 28/10 | 29/10 | Δ | 30/10 | Δ |
|---|---:|---:|---:|---:|---:|
| `duree_s` | 4 927 | **4 921** | −6 | **4 934** | +13 |
| `cpu_s` | 3 935,6 | 3 868,7 | −66,9 | 3 900,2 | +31,5 |
| `marge_s` | 3 173 | 3 179 | +6 | 3 166 | −13 |
| marge / garde (8 100 s) | 39,17 % | 39,25 % | +0,08 pt | **39,09 %** | −0,16 pt |
| étapes (somme) | 2 957,6 | 2 802,6 | −155,0 | 2 901,6 | +99,0 |
| hors étapes | 1 969,4 | **2 118,4** | +149,0 | 2 032,4 | −86,0 |
| `jalon_max_mo` | 3 420 | 3 424 | +4 | ⛔ **3 400** | −24 |
| `mem_peak_mo` | 3 587,2 | 3 623,8 | +36,6 | 3 603,9 | −19,9 |
| `swap_peak_mo` | 2 416,6 | 2 431,8 | +15,2 | **2 149,3** | −282,5 |
| `swap_out_pages` | 2 222 837 | 2 212 450 | −10 387 | ⚠️ **2 484 258** | +271 808 |
| `n_57014` | 0 | 1* | +1 | 1* | 0 |
| `incidents` | 3 | ✅ **2** | −1 | **2** | 0 |
| `lignes_regime` | 138 581 | 138 828 | +247 | 140 703 | +1 875 |
| `lignes_score_zone` | 149 223 | 149 486 | +263 | 151 401 | +1 915 |
| `lignes_daily` | 66 560 | 68 287 | +1 727 | 68 430 | +143 |
| `lignes_glissant` | 10 642 | 10 658 | +16 | 10 698 | +40 |
| `balise_jours_rejeu` | 2 060 134 | 2 058 366 | −1 768 | 2 062 126 | +3 760 |

(*) `n_57014 = 1` les deux nuits, mais **hors bloc purge** — voir §2.2.

Les `incidents` sont **tous** de mémoire, et il n'y en a plus que **deux** :
rejeu d'archive (2 995 puis 2 982 Mo) et oubli de la fenêtre rejouée (3 424
puis 3 400 Mo). ✅ **Aucun avertissement de purge, pour la quatrième nuit
d'affilée.**

Répartition par étape :

| étape | 28/10 | 29/10 | Δ | 30/10 | Δ |
|---|---:|---:|---:|---:|---:|
| `regime` | 1 622,6 | 1 508,1 | −114,5 | 1 589,8 | +81,7 |
| `glissant` | 965,5 | 933,9 | −31,6 | 935,4 | +1,5 |
| `stabilite` | 291,8 | 287,2 | −4,6 | 295,6 | +8,4 |
| `rejeu` | 77,7 | 73,4 | −4,3 | 80,8 | +7,4 |

⇒ `regime` fait **presque tout** le mouvement, dans les deux sens. Les trois
autres étapes bougent de moins de 32 s.

### Les deux rapports qui valent mieux que les valeurs brutes

**Coût par ligne rejouée** (`jalon_max_mo × 1048576 / balise_jours_rejeu`) :

```
19/10 1 702,0 o · 20/10 1 608,0 o · 21/10 1 726,1 o · 22/10 1 722,2 o
23/10 1 621,3 o · 24/10 1 723,8 o · 25/10 1 743,9 o · 26/10 1 595,7 o
27/10 1 726,9 o · 28/10 1 740,7 o · 29/10 1 744,3 o · 30/10 1 728,9 o
```

⇒ ⚠️ **1 744,3 o le 29/10 est le plus haut de la série — mais de 0,4 o sur le
25/10, c'est-à-dire INDISCERNABLE du record précédent.** Je ne l'annonce donc
**pas** comme un record. La bande **1 596 à 1 744 o** tient une **dixième**
nuit, et sur douze nuits il n'y a **aucune pente**.
ⓘ Et ce n'est **pas** un artefact de fenêtre le 29/10 : `balise_jours_rejeu`
**recule** de 1 768, donc le jalon monte **pendant que** la fenêtre se réduit.
Le 30/10 la fenêtre remonte de 3 760 et le jalon **baisse** de 24 Mo.

**Coût par ligne de `regime`** (`etapes_s.regime / lignes_regime × 1000`) :

```
21/10 12,14 ms · 22/10 12,59 ms · 23/10 11,97 ms · 24/10 11,42 ms
25/10 12,19 ms · 26/10 11,44 ms · 27/10 11,21 ms · 28/10 11,71 ms
29/10 10,86 ms · 30/10 11,30 ms
```

⇒ ✅ **10,86 ms le 29/10 est le POINT LE PLUS BAS de la série** : l'étape perd
114,5 s en traitant 247 lignes de **plus**. Le 30/10 remonte à 11,30 ms en
traitant 1 875 lignes de plus — la hausse est **en partie du volume**.
⇒ **critère `bw-regime-sensibilite` : 1 / 2.** ⚠️ **Et cela CORRIGE la note du
28/10, qui annonçait 1 / 2** : cette série-là a été **interrompue par la baisse
du 29/10**, qui remet le compteur à 0 ; le 30/10 est la **première** hausse de
la nouvelle série. **Rien posé, aucune question remontée.**

**Calcul ou attente ?** Les deux nuits ne sont **pas** de la même nature :
- **29/10** : la durée perd 6 s, `cpu_s` en perd **66,9** ⇒ le CPU recule **dix
  fois plus** que l'horloge. Moins de calcul, plus d'**attente**.
- **30/10** : la durée prend 13 s, `cpu_s` en prend **31,5** ⇒ c'est du
  **calcul**, et il monte plus que l'horloge.

Aucune des deux n'a d'effet sur le total.

## 2. ✅ LA PURGE : quatre nuits propres — le critère de fermeture de KAN-5 est REMPLI

Les deux blocs purge, en entier :

```
2026-10-29 06:18:39  → purge model_score_zone : 143625 ligne(s) effacée(s) en 8 tranche(s)
2026-10-29 06:18:39  ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée
2026-10-30 06:19:17  → purge model_score_zone : 147216 ligne(s) effacée(s) en 8 tranche(s)
2026-10-30 06:19:17  ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée
```

Deux lignes chacune, et c'est tout. Lecture selon les règles du 28/09
complétées le 07/10 :

| test | 29/10 | 30/10 |
|---|---|---|
| tranche en échec | ✅ **✘ aucune** | ✅ **✘ aucune** |
| bilan chiffré | ✅ **✔ 143 625 / 8 tr.** | ✅ **✔ 147 216 / 8 tr.** |
| « des lignes RESTENT » | ✅ **✘ absent** | ✅ **✘ absent** |
| sonde en défaut | ✅ **✘ aucun** | ✅ **✘ aucun** |

⇒ ✅ **DEUX NUITS PROPRES PLEINES**, sonde comprise. Aucune ligne
`?as_of=eq.J&regime=eq.R : HTTP 500`, aucune ligne « plus vieille journée
illisible ». La réserve du 26/10 ne s'applique à aucune des deux.

### 2.1 ✅ Compteur de fermeture KAN-5 : 4 / 3 — le critère est rempli

Le critère écrit — « trois nuits consécutives sans 57014 **dans le bloc purge**
ET avec un nombre de lignes lisible » — est rempli sur ses deux branches :

```
27/10  propre  → 1 / 3
28/10  propre  → 2 / 3
29/10  propre  → 3 / 3   ⇐ CRITÈRE REMPLI (hier)
30/10  propre  → 4 / 3
```

⇒ ❓ **LE CRITÈRE EST REMPLI, et il l'était dès le 29/10.** ⛔ **Rien n'est
fermé, rien n'est transité** : c'est Yann qui tranche, et la question lui est
posée pour la deuxième fois.
ⓘ La sous-question du 26/10 — la sonde doit-elle compter ? — **ne se pose ni
l'une ni l'autre de ces nuits**, puisqu'il n'y a aucun défaut de sonde. Elle
reste ouverte pour le jour où le cas se représentera.

### 2.2 ⚠️ Le point à ne pas mal lire : `n_57014 = 1` aux deux registres

Après deux nuits à 0, le registre repasse à **1** les 29 **et** 30/10. Ce n'est
**pas** un retour du 57014 de purge. Recherche élargie sur **toutes** les
unités, 48 h : `grep -c 57014` = **2**, et les deux lignes sont identiques :

```
⚠️ rpc/bw_character_avance : HTTP 500 {"code":"57014", …
   "canceling statement due to statement timeout"} — reprise 1/3
```

C'est l'**avance des accumulateurs**, pas la purge. Et la reprise a abouti
**pleinement** les deux fois : « model_character : **428 285** accumulateurs
avancés sur 428 285 envoyés » (29/10) et « **375 302** sur 375 302 » (30/10).
**Zéro perte.**
ⓘ **Précédent** : le 23/10, `n_57014 = 4` dont **aucun** dans la purge.
ⓘ **Historique de cette ligne précise sur quinze jours**, vérifié : **22/10,
23/10, 29/10, 30/10** — quatre dates, motif **récurrent et antérieur**, qui se
rattrape seul. ⚠️ C'est la **première fois qu'il tombe deux nuits de suite** :
à surveiller, **rien de plus**, et surtout **pas** un motif neuf.

Série `n_57014` au registre sur dix-huit nuits :

```
13/10 0 · 14/10 1 · 15/10 0 · 16/10 1 · 17/10 0 · 18/10 0 · 19/10 0 · 20/10 0
21/10 0 · 22/10 1 · 23/10 4 · 24/10 0 · 25/10 3 · 26/10 1 · 27/10 0 · 28/10 0
29/10 1* · 30/10 1*          (* hors purge)
```

### 2.3 Le volume : fourchette normale, et toujours pas une preuve

```
28/10   142 819 lignes en 8 tranches
29/10   143 625 lignes en 8 tranches
30/10   147 216 lignes en 8 tranches
```

⇒ Trois nuits de suite à **8 tranches** et dans la fourchette habituelle
(125 000 à 147 000). **Le volume effacé suit le volume de la journée purgée :
il monte et descend sans rien signifier**, et il n'est pas lu comme un signal.
⛔ **Et il n'y a toujours AUCUNE preuve** que la journée 2026-10-17 soit partie
de la base. Seul un `select as_of, count(*) from model_score_zone group by
as_of order by as_of limit 5` le dirait, et **aucun SQL n'a été joué.**
⬇️ Son intérêt reste au niveau du 28/10 : seule réponse ferme, pas urgente.

### 2.4 ⛔ Les deux défauts de code restent entiers, et ces nuits ne les testent pas

1. **(a)** `bilan_purge` ignore le suffixe « des lignes RESTENT » — faux négatif
   démontré le 25/10.
2. **(b)** `registre_nuit._INCIDENT` ne reconnaît pas la ligne de sonde, donc la
   branche `sonde_ko` de `controle_quotidien.constats()` est du **code mort** —
   démontré le 26/10.

⛔ **Aucun des deux n'est déployé, et il faut les DEUX.** Ces deux nuits
n'avaient **ni** ligne restante **ni** sonde en défaut : elles ne pouvaient
**ni** les confirmer **ni** les réfuter — **quatrième et cinquième** nuit de
suite dans ce cas. Ce sont des **écritures dans le code** : Yann tranche.
ⓘ Et ce n'est toujours pas une raison de retirer le correctif du 07/10 : sans
lui, KAN-5 recevrait « purge en échec » toutes les nuits où une tranche est
rejouée puis rattrapée, ce qui est le cas normal.

### 2.5 Le contrôle de pente s'est tu les deux matins, et par la bonne porte

```
2026-10-29T06:31:05Z rien à dire : pente plate ou négative, ou échéance hors horizon
2026-10-30T06:30:08Z rien à dire : pente plate ou négative, ou échéance hors horizon
```

Verbeux, relancé à la main en lecture seule ce matin :

```
ⓘ 92 relevé(s), 71 comparable(s) ; durée : 10 points, pente -119 s/nuit ;
  mémoire : 10 points, pente -24 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate/négative, ou échéance hors horizon
```

✅ Le silence est **juste** et **par la bonne porte** : `incidents` ne porte
aucun avertissement de purge **parce qu'il n'y en a eu aucun** — et non, comme
le 26/10, parce que le motif du registre ne sait pas lire la ligne de sonde. Le
défaut (b) n'a, là encore, pas eu l'occasion de nuire.
ⓘ 92 relevés / 71 comparables contre 90 / 69 le 28/10 : **+2 et +2**, cohérent
avec exactement deux nuits de plus.

## 3. ⛔ R2 : le palier gratuit est redépassé — et l'avertissement du 28/10 est vérifié en une nuit

### 3.1 Le compte

```
                      28/10            29/10             30/10            Δ total
total compte     9,564 Go 95,6 %  10,291 Go 102,9 %  10,276 Go 102,8 %   +712 Mo
objets             7 077            7 225             7 281             +204
pente mesurée                      +0,023 Go/mois    +0,028 Go/mois
palier atteint                        0 j               0 j
```

⇒ ⛔ **Le palier est redépassé dès le 29/10** : +727 Mo en une nuit, puis
−15 Mo. L'avertissement du 28/10 — « il reste 436 Mo, une nuit comme celle-ci
et le palier est redépassé » — est **vérifié dès le lendemain**, et c'est la
lecture la plus franche de ces deux nuits. ⚠️ Le journal le dit sans détour :
`⚠️ palier gratuit DÉPASSÉ : 10,29 Go sur 10 Go — R2 facture déjà`.
ⓘ Le seuil d'alerte (12 Go) et le seuil d'arrêt de chaîne (6 Go) ne sont pas
en cause ; couverture **complète** (tous les buckets du compte).

Par préfixe :

```
                      28/10              29/10              30/10
agrume/grille    4,654 Go  680 obj   5,323 Go  766 obj   5,323 Go  766 obj
agrume/pi        1,690 Go 3 813 obj  1,710 Go 3 861 obj  1,730 Go 3 909 obj
arome/rafale     0,806 Go             0,826 Go            0,823 Go
agrume/colonnes  0,558 Go  102 obj    0,556 Go  102 obj   0,520 Go   96 obj
arome/sol        0,556 Go             0,566 Go            0,560 Go
```

Par bucket au 30/10 : `balise-watch-grids` **9,351 Go / 6 056 obj** ·
`model-verif` **0,920 Go / 1 012 obj** · `balise-watch-packs` 0,004 Go / 213.

### 3.2 ⓘ LE FAIT DU JOUR : `agrume/grille` est revenu à 766 / 766, et la ligne « 28 suppressions ratées » a disparu

```
│ agrume/grille/                          766 présentes /  766 réclamées   ✓ tout est réclamé
```

Historique de cette ligne sur neuf jours, vérifié :

```
22/10   766 présentes / 766 réclamées    (aucune mention de suppression)
23/10   766 / 766 · 24/10  766 / 766 · 25/10  772 / 772 · 26/10  766 / 766
27/10   610 / 610                        ← le retrait de 1 125 Mo
28/10   680 / 652   + « 28 suppression(s) ratée(s) »   ← inédit
29/10   766 / 766   ← revenu au nominal, ligne DISPARUE
30/10   766 / 766   ← stable
```

⇒ ⓘ **La question du 27/10 est pratiquement refermée.** Le préfixe est revenu
**exactement** à ses 766 objets et à **5,323 Go**, et l'écart 680 − 652 = 28
s'est résorbé **en une nuit** sans que personne n'intervienne. C'est le
comportement d'une **fenêtre glissante** qui s'est vidée puis remplie, et la
ligne « 28 suppression(s) ratée(s) » était bien ce qu'elle disait : une
**reprise annoncée au prochain run**, qui a eu lieu.
⇒ ⓘ Donc le retrait de **1 125 Mo / 156 objets** du 27/10 était **le mécanisme
de rétention, pas un geste humain**. C'était la piste du 28/10 ; elle est
maintenant **cohérente de bout en bout**. ⚠️ Je ne dis pas « prouvée » : je
n'ai ni le code de rétention sous les yeux ni un journal de suppression
nominatif. Mais la question « est-ce toi ? » **n'a plus besoin de réponse**, et
la sous-question « pourquoi 28 suppressions échouent-elles ? » devient « elles
n'échouent plus — c'était transitoire ».

### 3.3 ⛔ `bw-garde-fou-r2` repasse en code 1 — et c'est son comportement normal

```
2026-10-29T05:18:57Z run garde-fou-r2 en ÉCHEC (code 1, 6s) — 1 consécutif(s)
2026-10-30T05:19:35Z run garde-fou-r2 en ÉCHEC (code 1, 5s) — 2 consécutif(s)
Result=exit-code · NRestarts=0 · ExecMainStatus=1 · ActiveState=failed
```

⇒ ✅ **Ce n'est PAS une panne.** La démonstration du 21/10 tient : **code 1 =
« j'ai quelque chose à dire »**. Le palier est dépassé, donc il parle. Les deux
nuits à code 0 des 27 et 28/10 correspondaient exactement aux deux nuits où le
compte était **sous** le palier. **Le garde-fou fait son travail.**

### 3.4 ⛔ `agrume/pi` : seizième et dix-septième nuit à +48 objets, sans un seul recul

```
│ agrume/pi/grille/                        19 présentes /   19 réclamées   ✓
│ agrume/pi/rafraichissement/              28 présentes /   28 réclamées   ✓
```

47 objets couverts sur **3 909** ⇒ **3 862 objets que nul index ne réclame**
(3 814 le 29/10, 3 766 le 28/10). **+48 par nuit, exactement le rythme
d'accumulation, pour la DIX-SEPTIÈME nuit consécutive.**
ⓘ Ce n'est pas la preuve qu'ils sont orphelins ; c'est la constatation qu'on
n'en sait rien. **L'inventaire reste le geste à faire avant toute rétention.**
⚠️ Et **la leçon du 24/10 (§7.1) s'applique une DIXIÈME fois** : le total du
compte a pris 727 Mo puis rendu 15 Mo pendant que l'accumulation n'a bougé que
de ses +48 habituels. **Le total du compte n'est pas un indicateur de
l'accumulation**, ni à la hausse ni à la baisse.

Pente affichée de `agrume/pi` : **+0,581 Go/mois** (+0,580 le 29/10),
inchangée.
⛔ Le point sur **`audit_r2.py`** (borner à zéro les pentes négatives des
préfixes à fenêtre glissante) reste **entier** : `arome/rafale` **−0,378**,
`arome/sol` **−0,287**, `arome/alt` −0,091, `arome/lod` −0,047 Go/mois tirent
la pente du total à **+0,028 Go/mois** pendant que `agrume/pi` monte à +0,581.
ⓘ Conséquence visible ce matin : « palier atteint dans **0 j** », ce qui est
juste par accident (le palier EST dépassé) et non par la pente. **Une écriture,
non faite.**

ⓘ **Mouvement neuf, petit** : `agrume/colonnes` rend **−36 Mo et −6 objets**
(0,556 → 0,520 Go, 102 → 96 obj) le 30/10, après être resté à 102 objets
pendant une semaine. Premier recul de ce préfixe. **Rien conclu** : une nuit.

## 4. ⚠️ Mémoire — le jalon qui compte n'a pas bougé, mais un incident sur trois s'efface

```
                        28/10   29/10    Δ     30/10    Δ     vs seuil 2800
rejeu d'archive         2 979   2 995   +16    2 982   −13    ⛔ +182
score par régime        2 808   2 665  −143    2 633   −32    ✅ −167 (SOUS)
oubli fenêtre rejouée   3 420   3 424    +4    3 400   −24    ⛔ +600
```

### 4.1 ✅ Le seul fait neuf : un avertissement mémoire sur trois s'éteint

`incidents` passe de **3 à 2** et y reste : le jalon « score par régime » est
repassé **sous** le seuil de 2 800 Mo les deux nuits (2 665 puis 2 633 Mo),
après 2 808 le 28/10. **Première fois de la série récente qu'un des trois
avertissements mémoire s'éteint.**
⚠️ **Et je le présente pour ce qu'il vaut, pas plus** : ce jalon n'était qu'à
**+8 Mo** au-dessus du seuil le 28/10. Il a franchi une ligne sur laquelle il
était **assis** — ce n'est pas un gain de structure, **rien n'a été déployé**
qui puisse l'expliquer, et une journée un peu plus chargée le fera repasser
au-dessus. **Ce n'est pas un début de pente.**

### 4.2 ⛔ Le jalon qui décide : bande inchangée, record non battu

```
19/10 3 381 · 20/10 3 193 · 21/10 3 424 · 22/10 3 412 · 23/10 3 210
24/10 3 411 · 25/10 3 452 · 26/10 3 151 · 27/10 3 399 · 28/10 3 420
29/10 3 424 · 30/10 3 400
```

⇒ ⚠️ **La bande va de 3 151 à 3 452 Mo, INCHANGÉE pour la dixième nuit.** Le
record du 25/10 n'est **pas** battu : il reste **28 Mo** au-dessus du 29/10 et
**52 Mo** au-dessus du 30/10. Sur douze nuits il y a autant de montées que de
descentes et **aucune pente nette**.
⚠️ C'est la **treizième** fois en vingt-et-un jours que « une nuit ne fait pas
une pente » s'applique ici, et la **quatrième** fois de suite que la prudence
de la note de la veille se trouve validée.

### 4.3 ⚠️ Bornes de lecture — et une divergence à signaler

✅ `mem_peak_mo` monte de 36,6 puis **baisse** de 19,9 (3 603,9) : le pic du
processus reste dans sa bande.
⚠️ **Le swap diverge le 30/10** : le **pic** baisse de **282,5 Mo** (2 149,3)
pendant que le **nombre de pages sorties** monte de **271 808** (2 484 258 — le
plus haut de la série récente). **Moins haut, mais plus longtemps.** Je ne
conclus rien de cette divergence ; je la signale pour qu'on ne lise **pas** le
recul du pic comme une amélioration franche. ⓘ La réserve du 27/10 (« ce n'est
pas un plancher de série ») s'applique aussi bien dans ce sens-là.

### 4.4 L'estimateur de pente, neuvième et dixième matin contradictoire

| matin | pente affichée | la nuit correspondante |
|---|---:|---|
| 26/10 | −188 Mo/nuit | chute de −301 Mo |
| 27/10 | −188 Mo/nuit | hausse de +248 Mo |
| 28/10 | −188 Mo/nuit | hausse de +21 Mo |
| 30/10 | **−24 Mo/nuit** | +4 Mo (29/10) puis −24 Mo (30/10) |

⇒ Après **trois matins collés à −188 Mo/nuit**, il affiche **−24**. C'est le
**25ᵉ centile des différences**, qui ignore par construction les deux plus
grosses variations. Conclusion posée le 23/10, **confirmée une septième fois** :
**cet estimateur n'est pas utilisable en prévision** sur cette série.
ⓘ L'échéance étant hors horizon (30 j), le contrôle se tait — et sur ce point
précis **il a raison**.

### 4.5 Les trois conditions de fermeture de KAN-4

| condition | état |
|---|---|
| le contrôle se tait sur `bw-pente-memoire` | ✅ **remplie** (deux matins) |
| le jalon est mesurément retombé | ⛔ **non** — 3 400 Mo, **+600** au-dessus du seuil |
| le swap au pic ≈ 0 | ⛔ **non** — 2 149,3 Mo |

⇒ ⛔ **NON RÉUNIES. KAN-4 reste ouvert.** Le seul mouvement favorable (§4.1)
porte sur le **plus petit** des trois jalons et ne touche pas celui qui décide.

### 4.6 Le remède, inchangé — et toujours le seul à la bonne échelle

La **ligne en tuple** (§2.6 de l'enquête du 10/09) : ≈ **−1 030 o/ligne**, soit
≈ **−2 024 Mo** sur les 2 062 126 balise-jours rejoués cette nuit — à comparer
aux **600 Mo** qui séparent le jalon du seuil. ⛔ **Rien de déployé côté mémoire
depuis `af25efb` (21/09) — 39ᵉ jour.** ⚠️ L'élagage de `units` avait rendu
−124 Mo au lieu de −1 500 : les gains sont dans la **structure**. La mesure
`tuple` contre `namedtuple` à la sonde reste le préalable.
ⓘ Un calcul à taux constant donnerait « seuil atteint en N nuits » ; je le
**refuse**, parce que la série n'a pas de pente et qu'un taux constant n'y a
aucun sens.

## 5. ✅ Durée — la série la plus plate du mois

```
            étapes     hors étapes   total
28/10      2 957,6       1 969,4     4 927
29/10      2 802,6       2 118,4     4 921
30/10      2 901,6       2 032,4     4 934
```

⇒ ✅ **4 927 → 4 921 → 4 934 s : treize secondes d'amplitude sur trois nuits**,
sur un run de plus de 80 minutes, soit **0,26 %**. C'est le passage le plus
**plat** du mois. La marge reste entre **39,09 %** et **39,25 %** du garde, loin
du plancher de série (34,57 % le 23/10).
⚠️ **Solde depuis le 23/10** : +58, −236, +188, −119, −405, +199, −6, +13 ⇒
**−308 s sur huit nuits**. La série oscille autour d'un niveau stable et le
solde reste **négatif**.

### 5.1 ⚠️ Le point intéressant : ≈ 150 s font l'aller-retour entre les deux blocs

```
29/10 : −155 s DANS les étapes, +149 s HORS étapes  ⇒ total −6 s
30/10 :  +99 s DANS les étapes,  −86 s HORS étapes  ⇒ total +13 s
```

⇒ Les deux nuits **échangent à peu près la même quantité de temps** entre le
bloc instrumenté et celui qui ne l'est pas, pendant que le total ne bouge
pratiquement pas.
⇒ ⛔ **Le bloc hors étapes n'est pas instrumenté** (publication, Murphy,
événements, pression, duels, purge), donc ces **+149 s** puis **−86 s** ne sont
**pas explicables depuis le journal** — **cinquième et sixième écart inexpliqué
en cinq nuits**.
ⓘ Pour situer : **2 118,4 s** (29/10) et **2 032,4 s** (30/10) contre une
médiane de ≈ **1 967 s** relevée le 28/10 sur 69 comparables. Le 29/10 est le
point notable des deux.
⬇️ Je **maintiens** la demande de **jalons de temps dans `run.sh`** à « **utile
sans urgence** ». L'argument se renforce à chaque nuit, mais aucun de ces
écarts n'a de conséquence mécanique. C'est une **écriture** : non faite.

### 5.2 Le garde

⛔ **Remontée du chien de garde : NON LANCÉE et NON PROPOSÉE.**
`controle_quotidien.proposition()` ne se déclenche pas (pente négative,
échéance hors horizon). La forme reste connue et je la **décris** sans la
demander : écrire la mesure dans l'en-tête de `10-timeout-s3.conf`
(135 → 140/145 min), déployer, vérifier. Avec **3 166 s** de réserve sur 8 100,
aucune urgence mécanique. **C'est Yann qui décide et qui lance.**

ⓘ Rappel, qui vaut pour KAN-3 : la pente du contrôle est le **25ᵉ centile des
différences**. Elle n'a vu ni le +153 s du 01/10, ni le +336 s du 06/10, ni le
+70 s du 07/10, ni le +188 s du 25/10, ni le +199 s du 28/10, et elle ne verra
pas le **+13 s** de cette nuit. Ce matin elle affiche **−119 s/nuit** (−143 le
28/10).

## 6. ⚠️ Témoins du mélange — quatre points positifs de suite, et « devant » repasse au-dessus de 50 %

```
29/10 : sur 7 446 balise-jours×échéance, le mélange fait 3,8015 km/h contre
        3,8204 pour le meilleur membre a priori (gain +0,5 %, devant 49,7 %) ;
        contre la moyenne UNIFORME, sur 1 102 : 3,9125 vs 4,086 (gain +4,2 %)
30/10 : sur 7 455, le mélange fait 3,0745 km/h contre 3,1688 (gain +3,0 %,
        devant 52,2 %) ; uniforme sur 1 099 : 3,173 vs 3,227 (gain +1,7 %)
```

Série du gain contre le **meilleur membre a priori** :

```
−0,6 % (07/10) · +2,5 · +1,7 · −0,3 · +0,9 · −0,9 · +0,1 · +0,8
· −4,0 % (25/10) · −2,2 · +5,2 · +2,3 · +0,5 (29/10) · +3,0 % (30/10)
```

⇒ ⚠️ **Quatre points positifs de suite**, et la part « devant » **repasse
au-dessus de la barre : 52,2 %** (49,7 % les 28 et 29/10) — première fois
depuis plusieurs nuits.
⇒ ✅ **La question du motif `bw-melange-sans-gain` reste refermée** : il
faudrait trois points **négatifs** consécutifs, et on en est à **quatre
positifs**. **Mon avis est inchangé : ne pas créer le motif.**
⚠️ Et **l'abandon de l'explication par le niveau de vent se confirme une
quatrième fois** : l'erreur absolue passe de 3,4982 (28/10) à **3,8015** (29/10,
journée plus agitée, gain qui **baisse** à +0,5 %) puis à **3,0745** (30/10,
journée bien plus calme, gain qui **remonte** à +3,0 %). Cette fois les deux
vont dans le **même** sens — ce qui, après trois nuits où ils divergeaient,
**confirme surtout que rien dans le journal ne prédit cette série**.

## 7. ⚠️ Position — aucun cri, et un démenti net de la note du 28/10

```
⛔ position : 18 balise(s) divergent du gel (10 j lus), dont 3 CONFIRMÉE(S)
   ⛔ pioupiou:2171          38 915 m · 10 j · nœud + profil CHANGENT
   ⛔ pioupiou:84             9 744 m · 10 j · nœud + profil CHANGENT
   ⛔ infoclimat:STATIC0491   1 159 m · 10 j · nœud 0,01 CHANGE
```

⇒ ✅ **Liste des confirmées strictement identique les deux nuits** — mêmes 3
balises, mêmes écarts au mètre — et **aucune ligne « cri déposé pour envoi »**
pour la position. C'est la **10ᵉ et la 11ᵉ vérification** du mécanisme « à
front, pas à état ». **Le mécanisme est établi.**
ⓘ La question du 01/10 reste ouverte — **faut-il qu'il recrie à état
constant ?** C'est exactement le cas depuis douze jours.

### 7.1 ⛔ Le démenti : les onze balises à 7 j n'atteindront PAS 10 j le 31/10

La note du 28/10 annonçait, pour la **troisième** fois, que les onze balises à
7 j (327, 1749, 1568, 1558, 70, 1724, 1715, 1435, 175, 2058, 633)
atteindraient 10 j le **31/10**. **C'est démenti** : le 29/10 la liste n'en
porte plus que **quatre** — **70, 175, 1715, 2058** (à 8 j, puis 9 j le 30/10).
**Les sept autres ont quitté la liste** : 327, 1749, 1568, 1558, 1724, 1435,
633 ont cessé de divergeur du gel.
⇒ ⚠️ **Seules quatre balises atteindraient 10 j le 31/10, pas onze.** Et comme
ces compteurs re-clignotent, même cette échéance-là n'est pas acquise.
⇒ ⓘ **La leçon est la même que pour les pentes** : un compteur de jours qui
monte n'est pas une échéance, parce qu'il peut se remettre à zéro. Je **ne
reprendrai plus** cette échéance sans la revérifier.

⚠️ **`pioupiou:1378` reste bloquée à 9 j pour les SEPTIÈME et HUITIÈME jours**,
écart inchangé à **340 941 m**. Elle re-clignote, donc **le compteur de jours
ne la confirmera jamais seule.** 341 km n'est pas un décalage de coordonnées
plausible : candidate nette « AUTRE balise », à trancher à la main.
ⓘ `pioupiou:367` (6 764 m) reste à **9 j**, cinquième jour hors des confirmées.
ⓘ `mf:05170001` passe de 4 à **5** puis **6 j** (330 m) : rien à en conclure.
ⓘ **Huit balises neuves** apparaissent à 1 j le 29/10 (1344, 1770, 1588, 2190,
1618, 1640, 309, 2156) et sont à 2 j le 30/10 — c'est le renouvellement
habituel de la queue de liste.

## 8. Les trois correctifs du 07/10 — verdict correctif par correctif

| correctif | verdict des 29 et 30/10 |
|---|---|
| **1. webhook `--ipv4`** | ✅ **CONFIRMÉ, et pour la première fois.** Il y avait quelque chose à envoyer (le palier R2 dépassé) et c'est **parti les deux nuits** : `ⓘ push parti (webhook, HTTP 200)` à 05:18:57Z et 05:19:36Z. ✅ **Aucun HTTP 429 ntfy** : `grep -i ntfy \| grep -c 429` = **0**. Les **47** occurrences de « 429 » du journal sur 48 h viennent des pollers aromepi, **rien à voir avec ntfy**. ✅ Le mail est parti aussi les deux nuits (`msmtp … smtpstatus=250 … exitcode=EX_OK`). ⇒ Ce correctif sort de l'état « ni confirmé ni mis en défaut » où il était depuis le 27/10. |
| **2. garde-fou des deux jetons** | ✅ **tient** mécaniquement : les contrôles de 07:31:05 et 07:30:08 se sont **tus**, aucun jeton posé, aucun doublon possible — et les trois commentaires de ce matin sont passés par le canal **délibéré**, qui ne touche pas au jeton. `controle_quotidien.sh` conserve son `$ETAT` — **non touché**. |
| **3. rejeu de purge ≠ échec** | ⓘ **non sollicité**, quatrième et cinquième nuit : purge propre, aucun avertissement, rien à lire. Les deux défauts du §2.4 restent **entiers**. |

## 9. Les autres témoins

- ⚠️ **Témoin du corrigé** : **19,8 pt** (29/10, sur 9 082 balise-jours — vrai
  antécédent +15,1 %, autre balise −4,7 %) puis **15,0 pt** (30/10, sur 9 116 —
  +13,5 % et −1,5 %). Série de la part site : 18,0 → 16,6 → 23,3 → 20,4 → 27,8
  → 27,6 → 27,1 → 17,9 → 17,0 → **19,8** → **15,0 pt**. Version FIN, part
  secteur+heure : 10,5 → 12,6 → 12,2 → 13,3 → 13,4 → 11,4 → 10,9 → **11,8** →
  **9,1 pt** (3 735 balise-jours contre 5 322 la veille). ⓘ **Ça oscille**,
  comme conclu les 22 au 28/10. **Rien à surveiller.**
- ⚠️ **Écarts du recalcul indépendant : 4 et 4.** Série : 5 · 4 · 7 · 4 · 7 · 5
  · 4 · 4 · **4** · **4** ⇒ elle va de 3 à 7 ; rien à en tirer sur le nombre.
  ⓘ **Et la signature se resserre puis se relâche à nouveau** : le 29/10,
  **4 sur 4** portent `0 h appariées ici (< 6)` ; le 30/10, **3 sur 4** en
  `0 h` et une en `1 h`. ⚠️ **C'est exactement l'oscillation que la note du
  27/10 avait prise pour une installation du `0 h` et que le 28/10 avait
  démentie** : elle change tous les jours. Même signature de fond (« la base
  porte une ligne alors que le recalcul n'en apparie pas assez »), récurrente
  et antérieure. Les quatre du 30/10 : `fcstagrume/aemet:9445L` (+24 h),
  `fcstagrume/infoclimat:STATIC0009` (+48 h), `fcstagrume/infoclimat:000OS`
  (+48 h), `fcstagrume/mf:05181002` (+24 h, **1 h**).
- ⓘ **Écart des deux mélanges** : `mse_comb` 17,841 contre `mse_comb_vec`
  17,841 (**+0,00 %**) les deux nuits — les deux chemins restent confondus.
- **Duels** (30/10) : `agrume ↔ agrume_pi (+6 h)` n = 7 121, médiane +0,011,
  IC95 [+0,007 ; +0,016] → `b_better` · `agrume_pi ↔ bw_mix (+6 h)` n = 7 106,
  médiane +0,408 → `b_better` · `agrume ↔ meteofrance_arome_france_hd (+6 h)`
  médiane −0,002, IC95 [−0,003 ; +0,000] → **`not_separable`** ·
  `arome_r2 ↔ meteofrance_arome_france_hd (+6 h)` n = 16 585 sur **29 j**,
  médiane +0,072 → `b_better` · `agrume_pi ↔ bw_mix (+24 h)` n = 6 860 sur
  29 j, médiane +0,489 → `b_better`. Cumul toujours **tronqué par la rétention
  30 j** (dette connue, `duel.DUEL_DAYS`).
  ⓘ **La journée AROME/R2 perdue du 25/10 se voit encore** : le duel `arome_r2`
  porte **29 j** quand les autres duels +6 h vont jusqu'au 2026-10-29. Elle
  restera dans la fenêtre glissante jusqu'au **24/11**.
- **Murphy** : 67 049 triplets / **63 975** décomposés / 266 dehors (29/10) ;
  67 108 / **63 907** / 266 (30/10).
- ⚠️ **Volumes : net recul le 30/10, et c'est cohérent.** **29 738**
  `model_verif_event` contre 45 901 la veille (**−35 %**), et la famille
  `breeze_yield` **disparaît** (39 lignes le 29/10, aucune le 30/10) ;
  **375 302** accumulateurs avancés contre 428 285 ; **642 777** lignes écrites
  en base contre 709 892 ; détails par tranche 60 814 contre 65 344.
  `model_events.json` 9 780 Ko, `model_scores.json` 132 587 Ko,
  `model_murphy.json` 25 787 Ko. ⓘ **Les observations montent pourtant**
  (3 730 balises contre 3 723) : c'est la **journée** qui était bien plus calme
  (erreur absolue **3,07 km/h** contre 3,80), pas la collecte qui a changé.
  3 425 balises zonées, 1 427 cases fines dont 745 sous les 2 balises.
- **Second canal du téléphone (Discord)** : ⛔ **`BW_DISCORD_WEBHOOK_URL`
  toujours ABSENTE** du `.env` (recherche sur le **nom seul**, `grep -c` = 0,
  aucune valeur lue). **49ᵉ jour.** ⓘ Et c'est **mesurable** ce matin : deux
  ⛔ ont crié les deux nuits, `ⓘ push parti (webhook)` apparaît **2 fois**,
  `push Discord` **0 fois**. Le script `~/installer-webhook-discord.sh` est
  **sur le Mac**. ⇒ **Si la variable avait été posée, on aurait eu la preuve que
  le second canal marche.** C'est l'occasion manquée du jour.
- **`mutations_memoire`** : ⓘ **aucune ligne au journal sur 48 h** (`grep -c`
  = 0) — rien conclu : la dette de 3 mutations non vues (2, 5, 13) est
  reportée telle quelle.
- ⓘ `bw-model-oracle.service` : **non examiné, hors mission.**

## 10. ✅ Les tickets — trois commentaires délibérés, aucun ticket touché

**États revérifiés par GET AVANT toute écriture :**

```
KAN-3 | Terminé | done | updated 2026-10-28T09:59:51+0100 | 34 comm.
KAN-4 | À faire | new  | updated 2026-10-28T09:59:50+0100 | 48 comm.
KAN-5 | À faire | new  | updated 2026-10-28T09:59:50+0100 | 31 comm.
```

⇒ ✅ Les trois `updated` sont **exactement** ceux laissés par le run du 28/10 :
**aucun tiers n'a écrit depuis**, aucune collision. ⓘ Et **aucun commentaire du
29/10 sur aucun des trois** — ce qui confirme par une troisième voie que la
routine n'a pas tourné hier **et** que les contrôles de 07:30 se sont tus.

**Après écriture**, les trois appels rendent `RC=0` et le message « Jira :
commentaire délibéré ajouté à KAN-5 / KAN-4 / KAN-3 », **une seule fois
chacun**.

**Vérifié par GET APRÈS écriture :**

```
KAN-3 | Terminé | done | updated 2026-10-30T07:44:32+0100 | 35 comm.  (+1)
KAN-4 | À faire | new  | updated 2026-10-30T07:44:31+0100 | 49 comm.  (+1)
KAN-5 | À faire | new  | updated 2026-10-30T07:44:30+0100 | 32 comm.  (+1)
```

⇒ ✅ **+1 chacun, exactement** : aucun doublon, et **aucun changement d'état**.

| ticket | ce qui a été posté | état |
|---|---|---|
| **KAN-5** | L'avertissement que le commentaire couvre **deux** nuits et pourquoi ; les deux blocs purge en entier ; les **quatre** tests de lecture ×2, tous au vert, **sonde comprise** ; le **compteur 4 / 3** et le fait que **le critère était rempli dès le 29/10** ⇒ question de fermeture posée une seconde fois ; l'explication complète du `n_57014 = 1` **hors purge** avec l'historique sur quinze jours et la preuve que la reprise a abouti à 100 % ; la série sur 18 nuits ; le volume donné **explicitement** comme non significatif ; les **deux** défauts de code, entiers et non sollicités ; pourquoi le silence du contrôle est juste *et* par la bonne porte ; la réserve maintenue sur l'absence de preuve pour le 2026-10-17. | ✅ **posté ×1** — reste **ouvert** |
| **KAN-4** | Les trois jalons et leurs deltas sur deux nuits ; le **seul fait neuf** (« score par régime » sous le seuil ⇒ incidents 3 → 2) **et sa mise en perspective immédiate** (il n'était qu'à +8 Mo, rien n'a été déployé) ; la bande 3 151–3 452 **inchangée** et le record du 25/10 non battu ; le coût par ligne rejouée avec le **refus d'annoncer un record à 0,4 o près** ; la **divergence pic / pages de swap** signalée sans conclusion ; **neuvième et dixième** matin contradictoire de l'estimateur (−188 trois matins, puis −24) ; les **trois conditions de fermeture** ⇒ **non réunies** ; le remède tuple à ≈ −2 024 Mo, **39ᵉ jour**, et le **refus** du calcul à taux constant. | ✅ **posté ×1** — reste **ouvert** |
| **KAN-3** | **Commenté** (canal délibéré) parce que deux nuits n'avaient pas été rapportées. Le relevé complet ×2 ; **13 s d'amplitude sur trois nuits**, le passage le plus plat du mois ; la répartition par étape ; **les ≈ 150 s qui font l'aller-retour** entre bloc instrumenté et bloc non instrumenté ⇒ **5ᵉ et 6ᵉ écart inexpliqué en 5 nuits** ; découplage calcul/attente **différent pour chaque nuit** ; découplage temps/volume et le **point le plus bas** du coût par ligne de `regime` ; le critère `regime` remis à **1 / 2** avec la **correction explicite** de la note du 28/10 ; le rappel du 25ᵉ centile ; le solde **−308 s sur huit nuits** ; la remontée du garde **décrite sans être demandée**. **Avis : NE PAS ROUVRIR.** ⛔ **Non rouvert, non transité.** | ✅ **posté ×1** — reste **Terminé** |
| `bw-regime-sensibilite` | ⛔ **non posé**, critère **1 / 2** — la série du 28/10 a été interrompue par la baisse du 29/10. Aucune question remontée. | — |
| `bw-melange-sans-gain` | ⛔ **non créé** : **quatre** points positifs de suite (§6). Avis : ne pas le créer. | — |
| `bw-r2-palier` | ⛔ **non créé.** ⬆️ Mais son urgence **monte encore** : le palier est **effectivement dépassé** depuis deux nuits et R2 facture (§3.1). ❓ **Question posée à Yann.** | — |
| `bw-character-57014` | ⛔ **non créé**, et je recommande de ne pas le créer : motif **antérieur** (22, 23/10), qui se **rattrape seul** à 100 % (§2.2). À surveiller seulement. | — |
| motif pour la purge | ⛔ **aucun motif neuf** : le motif existe, c'est **KAN-5**, et il est ouvert. | — |

ⓘ **Pourquoi `bw_jira_commenter` trois fois et `bw_jira_signaler` zéro fois** :
les contrôles se sont tus les deux matins, donc le jeton du jour était libre —
mais `bw_jira_signaler` aurait **créé un ticket neuf** sur le motif « Terminé »
(KAN-3, puisque `bw_jira_chercher` filtre sur `statusCategory != Done`), et sur
les deux autres il n'apportait rien de plus. `bw_jira_commenter` prend une
**clé**, ne cherche rien, ne crée rien, ne touche pas au jeton du jour. C'est le
choix assumé de l'arbitrage du 07/10.

## 11. ⛔ Horaire de la routine — +23 h 18, un matin sauté

Programmée pour le **29/10 à 07:09:05 UTC**, tirée le **30/10 à 06:27:01 UTC** :
**+23 h 18**.

```
17/10 +1 h 56 · 18/10 +1 h 39 · 19/10 +7 h 43 · 20/10 +3 h 41 · 21/10 +8 h 50
22/10 +4 h 23 · 23/10 +4 h 21 · 24/10 +0 h 02 · 25/10 +0 h 01 · 26/10 +0 h 02
27/10 +10 h 09 · 28/10 +1 h 34 · 29/10 ⛔ +23 h 18 (matin SAUTÉ)
```

⇒ ⛔ **C'est le pire de la série, et d'un autre ordre que les précédents** : ce
n'est plus un retard, c'est un **matin perdu**. Conséquences concrètes :
1. Le verdict du 29/10 **n'a jamais été rendu** — ni note, ni miroir git, ni
   commentaire Jira.
2. **La question de fermeture de KAN-5, posée le 28/10 pour « demain », n'a
   jamais été posée.** Le critère s'est rempli hier matin sans que personne ne
   le dise. C'est le **coût réel** de ce trou.
3. Les deux nuits arrivent ensemble, donc les deltas de ce matin portent sur
   **deux** nuits et pas une — ce qui a été écrit explicitement partout.
ⓘ **Le trou est côté planification, pas côté VPS.** Le VPS est à l'heure sur
les deux nuits : notation à 04:56:41 puis 04:57:06 CET, contrôles à 07:31:05 et
07:30:08 CET, timer suivant armé pour le **31/10 à 07:30:43 CET**.
⚠️ **Et l'occurrence du 30/10 (07:09 UTC) peut encore partir aujourd'hui** :
voir l'avertissement de collision en tête de section.

## 12. Décisions en attente de Yann — la liste à jour

1. ❓ **PRIORITAIRE, et en retard d'un jour : fermeture de KAN-5.** Le critère
   écrit est **REMPLI** (4 / 3, rempli dès le 29/10). **Veux-tu le fermer ?**
   Je ne ferme rien sans ta réponse.
2. ⬆️ **PRIORITAIRE : R2 facture.** Le palier gratuit est dépassé depuis deux
   nuits (10,291 puis 10,276 Go, §3.1). ❓ Veux-tu un motif Jira
   `bw-r2-palier`, ou une action de rétention ?
3. ✅ **La question du 27/10 sur `agrume/grille` peut être refermée** (§3.2) :
   766 / 766, ligne de suppressions ratées disparue, c'était la fenêtre
   glissante. Confirme et je la retire de cette liste.
4. ⚠️ **`installer-webhook-discord.sh`** (sur le Mac) — **49ᵉ jour**. ⬆️ Son
   intérêt **monte** : deux cris sont partis cette nuit, c'était l'occasion de
   prouver le second canal (§9).
5. ⛔ **Trois miroirs git en souffrance** : celui du **24/10** (jamais déposé),
   celui du **26/10** (présent mais **non suivi par git**), et le **29/10**
   (inexistant, et c'est normal — pas de run). Rien fabriqué après coup. Le
   miroir du 26/10 est **réparable sans rien inventer**. Dis-moi.
6. ⛔ **Les DEUX correctifs de lecture de la purge** (§2.4), inchangés :
   (a) `bilan_purge` et le suffixe « des lignes RESTENT » ; (b)
   `registre_nuit._INCIDENT` et la ligne de sonde. **Il faut les deux.**
7. ⬇️ **`diagnostic_base_sous_tension_2026-09-29.sql`** — **32ᵉ jour** sans
   être joué. Urgence **basse** : cinquième nuit d'affilée où la purge aboutit,
   quatre sans le moindre avertissement. Lecture seule, 9 blocs, SQL Editor.
8. ⬇️ **Le `select as_of, count(*)`** sur `model_score_zone` : seule façon de
   **prouver** que le 2026-10-17 est parti. **Aucun SQL joué sans ton accord.**
9. ⛔ **R2 : rétention sur `agrume/pi`** — **+48 objets chaque nuit, dix-sept
   nuits d'affilée, sans un seul recul** (§3.4).
10. ⛔ **Inventaire des 3 862 objets de `agrume/pi` que l'index ne réclame pas**
    (sur 3 909). À faire **avant** toute rétention.
11. ⛔ **Mémoire : la ligne en tuple** (≈ −1 030 o/ligne, ≈ −2 024 Mo). **39ᵉ
    jour sans rien de déployé** depuis `af25efb`. Seule porte de sortie de
    KAN-4 : le jalon est à **+600 Mo** du seuil.
12. ⛔ **Pente d'`audit_r2.py`** : borner à zéro les pentes négatives des
    préfixes à fenêtre glissante (§3.4). Une ligne, mais c'est une **écriture**.
13. ⛔ **Les 3 cas de position confirmés** (§7) : trancher, puis
    `position_suspecte` + `position_note` par `.sql`. ⚠️ **`pioupiou:1378`** :
    341 km, bloquée à 9 j **huit jours de suite** — elle ne se confirmera jamais
    seule. ⓘ **Et l'échéance du 31/10 ne vaut plus que pour QUATRE balises**,
    pas onze (§7.1).
14. ⓘ **Réouverture de KAN-3** : **mon avis est NON** — 13 s d'amplitude sur
    trois nuits, solde **−308 s** sur huit.
15. ⬇️ **Jalons de temps dans le bloc hors étapes de `run.sh`** — maintenu à
    « utile sans urgence » (§5.1), mais **5ᵉ et 6ᵉ écart inexpliqué en 5 nuits**.
16. ❓ **`bw-melange-sans-gain`** : **ne se confirme pas** (quatre points
    positifs, §6). Mon avis : ne pas créer le motif. À toi de refermer.
17. ⓘ **Horaire de la routine** : ⛔ un **matin entier sauté** le 29/10
    (§11). Si ça se reproduit, le coût est un verdict perdu.
18. ⓘ **Le cri de position doit-il recrier** à état constant ? (ouvert depuis le
    01/10 ; « à front » vérifié **onze** jours de suite — §7)
19. ⓘ **`mutations_memoire`** : 3 mutations non vues (2, 5, 13), dette
    antérieure, inchangée.
20. ⓘ **`bw-model-oracle.service`** en `failed` — hors mission, non examiné.

## 13. Ce que ce run a DÉMENTI, et ce qu'il a CONFIRMÉ, de la note du 28/10

| annoncé le 28/10 | relevé les 29 et 30/10 |
|---|---|
| ✅ compteur KAN-5 à **2 / 3**, fermeture possible **dès le 29/10** | ✅ **CONFIRMÉ et TENU** : 3 / 3 le 29/10, 4 / 3 le 30/10 — critère **rempli**. Mais la question n'a pas été posée, faute de run |
| ⛔ R2 à 9,564 Go, « **une nuit comme celle-ci et le palier est redépassé** » | ⛔ **VÉRIFIÉ DÈS LE LENDEMAIN** : **10,291 Go (102,9 %)**, +727 Mo en une nuit |
| ⓘ « 28 suppression(s) ratée(s) » ⇒ **piste** d'un mécanisme de suppression actif | ✅ **CONFIRMÉE, et la question se referme** : 766 / 766, ligne **disparue**, 5,323 Go — la fenêtre glissante a repris ce qu'elle avait rendu |
| ✅ `bw-garde-fou-r2` rend code 0, 2ᵉ nuit | ⛔ **repasse en code 1** (1 puis 2 consécutifs) — **et c'est correct** : le palier est dépassé, il a quelque chose à dire |
| ⓘ webhook `--ipv4` « ni confirmé ni mis en défaut : rien à envoyer » | ✅ **CONFIRMÉ** : deux ⛔ à crier, `push parti (HTTP 200)` **×2**, zéro 429, mail parti |
| ⛔ `agrume/pi` **15ᵉ** nuit à +48 | ⛔ **16ᵉ et 17ᵉ nuit à +48**, et le total du compte fait +727 puis −15 ⇒ **10ᵉ vérification** du §7.1 du 24/10 |
| ⚠️ jalon 3 420 Mo, bande 3 151–3 452, « aucune pente » | ⚠️ **3 424 puis 3 400 Mo** : bande **inchangée**, record du 25/10 **non battu**. Le refus de lire une pente est **validé une 4ᵉ fois** |
| ⚠️ réserve sur l'estimateur de pente (−188 trois matins de suite) | ✅ **validée une SEPTIÈME fois** : il affiche maintenant **−24 Mo/nuit** |
| ⛔ swap **2 416,6 Mo** (+359), gain d'hier annulé | ⚠️ **2 431,8 puis 2 149,3 Mo** — mais `swap_out_pages` **monte** de 271 808 le 30/10 : pic et pages **divergent** |
| ⚠️ durée **+199 s**, 2ᵉ plus basse des 13 nuits | ✅ **−6 puis +13 s** : **13 s d'amplitude sur trois nuits**, le passage le plus **plat** du mois |
| ⚠️ bloc hors étapes **à la médiane**, 3ᵉ écart inexpliqué | ⚠️ **2 118,4 puis 2 032,4 s** : 4ᵉ, 5ᵉ et 6ᵉ écart inexpliqué. Demande **maintenue** à « utile sans urgence » |
| ⚠️ critère `regime` à **1 / 2**, première hausse | ⛔ **CORRIGÉ** : le 29/10 est une **baisse** (10,86 ms, point le plus bas) qui remet le compteur à **0** ; le 30/10 repart à **1 / 2** |
| ⚠️ témoins du mélange **+2,3 %**, « devant » 49,7 % | ⚠️ **+0,5 puis +3,0 %**, « devant » **52,2 %** ⇒ **quatre** points positifs, question **reste refermée** |
| ✅ « à front, pas à état », 9ᵉ vérification | ✅ **10ᵉ et 11ᵉ vérification** : confirmées identiques au mètre, aucun cri, aucun push de position |
| ⚠️ `pioupiou:1378` bloquée à 9 j, 6ᵉ jour | ⚠️ **7ᵉ et 8ᵉ jour**, écart inchangé à 340 941 m |
| ⓘ **onze balises à 7 j, 10 j le 31/10** (annoncé 3 fois) | ⛔ **DÉMENTI** : **sept ont quitté la liste**. Il n'en reste **quatre** (70, 175, 1715, 2058), à 9 j |
| ⚠️ témoin du corrigé 17,0 pt, « ça oscille » | ✅ **confirmé** : 19,8 puis 15,0 pt |
| ⛔ écarts du recalcul : 4, **1 sur 4** en `0 h` | ⚠️ 4 et 4 ; **4 sur 4** en `0 h` le 29/10, **3 sur 4** le 30/10 ⇒ ça **oscille tous les jours** |
| ⓘ `n_57014 = 0`, deux nuits | ⚠️ **1 et 1 — mais HORS purge** (`rpc/bw_character_avance`), rattrapé à 100 % |
| ⛔ horaire **+1 h 34** | ⛔ **+23 h 18** : pire de la série, et un **matin sauté** |
| ⛔ miroirs git du 24/10 et du 26/10 en souffrance | ⛔ **inchangé**, vérifié et non arrangé |

⚠️ **« Une nuit ne fait pas une pente » — treizième fois en vingt-et-un jours.**
Appliqué ce matin à : la hausse puis la baisse du jalon (§4.2), le coût par
ligne rejouée à 0,4 o du record (§1), les deux mouvements de durée (§5), le
coût par ligne de `regime` (§1), le recul de `agrume/colonnes` (§3.4), la
divergence du swap (§4.3) et le recul des volumes (§9). **Aucun des sept n'est
présenté comme une tendance.** La tentation du jour était de lire « tout se
calme » — la durée est plate, un incident mémoire s'éteint, le mélange est
positif quatre fois — alors que le fait dur de la matinée est que **R2
facture**.

⛔ **Et trois fois, ce matin, la leçon ne s'applique PAS.** Le critère de
fermeture de KAN-5 est une **règle écrite comptée sur quatre nuits**, pas une
tendance. Le dépassement du palier R2 est un **fait de facturation**, pas une
pente. Et les **deux défauts de lecture de la purge** sont des **lectures de
code**, vraies indépendamment du nombre de nuits.

⛔ **Enfin, une leçon neuve, et elle est à retenir** (§7.1) : **un compteur de
jours qui monte n'est pas une échéance.** L'échéance « onze balises à 10 j le
31/10 » avait été reprise **trois matins de suite** sans être revérifiée ; sept
des onze balises ont simplement quitté la liste. C'est la même erreur que de
lire une pente dans quatre points, mais sur un objet qui *ressemblait* à un
décompte sûr.

## 14. Respect des règles

✅ **VPS en LECTURE SEULE, pleine et entière.** Aucun `systemctl`
start/restart/daemon-reload, aucun `enable`, **aucun SQL joué**, aucun rsync,
rien écrit dans `~/balise-watch` ni dans `/etc`. **Aucune redirection vers
`/tmp` du VPS** : toutes les sorties sont allées dans des fichiers du **Mac** et
relues avec `read_file`. ⓘ Seules exceptions, qui sont le fonctionnement normal
du code de production : `bw_jira_http` écrit sa réponse dans un `mktemp -d` du
VPS, et le `controle_quotidien.py --verbeux` relancé à la main ne fait que lire.
✅ **Aucun secret lu par valeur** : `.balise-watch-alertes.env` **sourcé**
(`set -a; . … ; set +a`) ; `BW_DISCORD_WEBHOOK_URL` cherchée **par son nom seul**
(`grep -c`) ; le jeton Jira passe par `curl -K -`, jamais `-u`.
✅ `10-timeout-s3.conf` **non touché** ; remontée du garde **non lancée**, et
seulement **décrite** dans le commentaire KAN-3.
✅ `controle_quotidien.sh` **non touché**, son `$ETAT` conservé. Les deux
correctifs du §2.4 sont **proposés**, pas écrits.
✅ **Aucun ticket créé, fermé, rouvert ni transité.** Trois commentaires, tous
par `bw_jira_commenter`, GET **avant** ET **après** chacun (§10) : +1
commentaire chacun, aucun doublon, aucun changement d'état.
✅ **Desktop Commander exclusivement** pour fichiers et shell.
✅ **Lire avant d'écrire** : `project_read` du 30/10 (absent ⇒ création), du
29/10 (absent ⇒ pas de run) et du 28/10 (lu en entier) ;
`git log --since=midnight` dans les deux dépôts ; `notes-projet/README.md`
relu ; **note en section horodatée** par prudence de collision (§0).
⛔ **Aucun `git push`.**
ⓘ **Rien fabriqué pour combler les miroirs manquants** (24/10, 26/10, 29/10).

## 15. ⓘ Outillage — les pièges connus, tous reconfirmés

1. ✅ **`SSH_AUTH_SOCK` manquant** (piège n°1) : confirmé une sixième fois, et
   le correctif marche du premier coup.

   ```
   export SSH_AUTH_SOCK="$(launchctl getenv SSH_AUTH_SOCK)"
   ```

   Dans un **process persistant** (`start_process "bash -l"` +
   `interact_with_process`), `ssh-add -l` voit ensuite
   `balise-watch-vps (ED25519)`.
2. ✅ **Le lecteur de flux qui perd des lignes** (piège n°2) : contourné
   d'emblée. **Toute sortie dont une ligne compte est redirigée vers un fichier
   du Mac et relue avec `read_file`.**
3. ✅ **« did not respond within 60s » alors que la commande aboutit** (piège
   n°3) : confirmé, et c'est arrivé à **presque tous** les appels ssh.
   ⛔ **Jamais relancé.** ✅ La bonne réaction : lire le fichier de sortie.
4. ✅ **Les heredocs cités pour le texte français** : les corps des trois
   commentaires sont écrits dans un script du Mac avec l'outil d'écriture de
   fichier, dans des heredocs `<<'XEOF'` (donc sans expansion ni échappement),
   et le script est passé par `ssh … 'bash -s' < post.sh`. Aucun mot de la
   liste noire dans la commande, et **rien d'écrit sur le VPS**.
   ⓘ Les corps sont rédigés **sans accents** pour éviter tout risque de
   mutilation en transit ; les accents restent dans la note.
5. ✅ **Le GET de contrôle par python du VPS** : `get_states.sh` lit la réponse
   Jira avec `/home/debian/venv-balise/bin/python3` dans un `mktemp -d`, en
   **lecture seule**. Le même script sert avant et après écriture, ce qui rend
   la comparaison exacte.

## 08:11–08:20 (Paris, CET) — SECOND run du jour : vérification seule, RIEN refait

⛔ **La collision annoncée au §0 a bien eu lieu.** L'occurrence du **30/10 à
07:09 UTC** est partie à **07:11 UTC (08:11 CET)**, soit **16 minutes** après
que le run précédent (l'occurrence du 29/10, tirée en retard) ait fini d'écrire.
Étape 0 appliquée : `git log --since=midnight` a montré **`a003d19`**
(07:53:54 CET, miroir du 30/10), et `project_read` a rendu la note **déjà
écrite** à 06:55:17Z. ⇒ **Le travail du matin était fait. Il n'a pas été
refait**, et cette section **fusionne** au lieu de remplacer (règle n°2 — c'est
exactement le cas du 11/09/2026 que le README documente, évité cette fois).

**Ce qui a été revérifié, en lecture seule, et ce que ça donne :**

| vérification | résultat |
|---|---|
| **Jira, GET des trois tickets** | ✅ **KAN-3** Terminé/`done`, **35** comm. · **KAN-4** À faire/`new`, **49** comm. · **KAN-5** À faire/`new`, **32** comm. — **exactement** les comptes annoncés au §10, derniers commentaires à **07:44:30/31/32**. **Aucun doublon, aucun changement d'état, aucun quatrième commentaire.** |
| **Registre des nuits, 2 dernières lignes** | ✅ **conforme au §1 au chiffre près** : `duree_s` 4 921 puis 4 934 · `cpu_s` 3 868,7 puis 3 900,2 · `jalon_max_mo` 3 424 puis 3 400 · `swap_peak_mo` 2 431,8 puis 2 149,3 · `n_57014` 1 et 1 · `lancement = timer` · `result = success` |
| **`incidents`** | ✅ **deux** les deux nuits, **tous deux de mémoire** (rejeu d'archive 2 995 / 2 982 Mo ; oubli de la fenêtre 3 424 / 3 400 Mo). **Aucun avertissement de purge** ⇒ le compteur KAN-5 à **4 / 3** est confirmé par une seconde lecture. |
| **Contrôle de 07:30** | ✅ une **seule** ligne aujourd'hui : `07:30:08 … rien à dire : pente plate ou négative, ou échéance hors horizon`. Pas de second tir, pas de second jeton. |
| **Miroir git** | ✅ `verdict-pente-30-10.md` présent (56 113 o, 07:52) et **commité** (`a003d19`). ⛔ Les deux miroirs en souffrance sont **inchangés** : 24/10 absent, 26/10 présent mais **non suivi** (`?? notes-projet/verdict-pente-26-10.md`). **Rien fabriqué, rien commité de plus** — c'est la décision n°5, elle reste à Yann. |

⇒ ✅ **Le verdict du run précédent est CONFIRMÉ par une relecture indépendante
des sources.** Rien n'est à corriger, rien n'est à compléter sur le fond.

⛔ **Les deux décisions prioritaires restent entières et personne n'y a
répondu** : (1) la **fermeture de KAN-5**, critère rempli depuis le 29/10
(4 / 3) ; (2) **R2 facture** — palier gratuit dépassé deux nuits de suite
(10,291 puis 10,276 Go). La liste du §12 est à jour telle quelle.

### Respect des règles sur ce second run

✅ **VPS en LECTURE SEULE** : trois `ssh` seulement — un `sed` sur `bw_jira.sh`,
un GET Jira (`bw_jira_http GET`, aucun POST), un `tail` du registre plus
`journalctl`. Aucun `systemctl`, aucun SQL, aucun rsync, rien écrit dans
`~/balise-watch` ni `/etc`. ✅ **Aucune écriture Jira** : pas un seul
`bw_jira_signaler`, pas un seul `bw_jira_commenter`. ✅ **Aucun secret lu par
valeur** (`.balise-watch-alertes.env` **sourcé**, `curl -K -`). ✅ **Desktop
Commander exclusivement** ; sorties redirigées vers des fichiers du Mac et
relues avec `read_file` (piège n°2), `SSH_AUTH_SOCK` exporté (piège n°1), les
trois « did not respond within 60s » **jamais relancés** (piège n°3). ⛔ **Aucun
`git push`.** ✅ **Lire avant d'écrire** : `project_read` avant ce `project_write`,
qui est une **fusion**.
