# Verdict de pente du 17/10/2026 — **la nuit calme qui tranche trois questions d'un coup**. ✅ Le **57014 n'est nulle part** (`n_57014 = 0`, 10e nuit propre sur `model_score_zone`) et `model_verif_daily` **ne récidive pas une 3e fois**. ✅ **R2 n'a PAS franchi le palier** : 9,959 → **9,942 Go (−17 Mo)**, `agrume/grille` **rend 21 Mo** — les +692 Mo d'hier ne se reproduisent pas. ✅ Le **coût par ligne rejouée est IDENTIQUE à la veille (1 701,4 o, −0,02)** : le 15/10 était bien une nuit atypique, et c'est maintenant une mesure répétée. ⚠️ La **durée remonte (+140 s)**, mais **93 % du mouvement est DANS les étapes** et tous les volumes reculent : c'est du **coût unitaire**.

## 11:05 → 11:15 (Paris) — routine Balise Watch (tirée à 09:03:28 UTC pour 07:07:05 : **+1 h 56**), lecture VPS complète, **trois écritures Jira**, **une notification**

**Étape 0 faite.** `git log --oneline --since=midnight` :

- dépôt serveur `PWA/balise-watch-server` : **aucun commit du jour**
- dépôt principal `surveillance balise` : **aucun commit du jour**
- `claude/verdict-pente-17-10.md` **absent** de la liste d'ouverture de session,
  et `notes-projet/verdict-pente-17-10.md` **absent** du dossier miroir
- `claude/verdict-pente-16-10.md` lu **en entier**
- `notes-projet/README.md` relu — les quatre règles

⇒ **premier et seul run du jour. Rien à fusionner, aucun doublon.**

## 1. Les nuits, bout à bout

| | 12/10 | 13/10 | 14/10 | 15/10 | 16/10 | 17/10 |
|---|---|---|---|---|---|---|
| durée | 5 029 s | 5 046 s | 5 032 s | 5 051 s | 4 861 s | **5 001 s (+140)** |
| marge | 3 071 | 3 054 | 3 068 | 3 049 | 3 239 | **3 099 (−140)** |
| marge en % du garde | 37,91 % | 37,70 % | 37,88 % | 37,64 % | **39,99 %** | **38,26 %** |
| `cpu_s` | 4 021,9 | 4 056,7 | 4 029,7 | 4 058,9 | 3 895,0 | **4 001,0 (+106,0)** |
| attente (durée − `cpu_s`) | — | — | — | 992,1 | 966,0 | **1 000,0 (+34,0)** |
| jalon max | 3 444 Mo | 3 422 | 3 416 | 3 161 | 3 384 | **3 383 (−1)** |
| au-dessus du seuil | +644 | +622 | +616 | +361 | +584 | **+583** |
| swap au pic | 2 595,3 | 2 091,8 | 2 417,0 | 2 226,6 | 2 429,5 | **2 347,4 (−82,1)** |
| pages sorties | 2 514 657 | 2 171 262 | 2 254 634 | **2 918 498** | 2 472 955 | **2 482 829 (+9 874)** |
| pic système | 3 616,1 | 3 595,4 | 3 612,1 | 3 597,2 | 3 584,5 | **3 603,6 (+19,1)** |
| fenêtre rejouée | 2 087 197 | 2 086 539 | 2 085 860 | 2 086 137 | 2 085 521 | **2 084 935 (−586)** |
| o / ligne rejouée | 1 730,2 | 1 719,7 | 1 717,2 | **1 588,8** | 1 701,4 | **1 701,4 (−0,02)** |
| incidents mémoire | 3 | 2 | 3 | 3 | 2 | **2 (=)** |
| `n_57014` | 0 | 0 | 1 (hors purge) | 0 | 1 (hors purge) | **0** |
| lancement / résultat | timer/success | ↳ | ↳ | ↳ | ↳ | **timer/success** |

Nuit **comparable** : `lancement=timer`, `exec_status=0`, `oom=0`,
`result=success`, **05:56:04 → 07:19:36**, `source=run.sh`,
`chevauchement_reduit=true`. Rien à écarter.
ⓘ Le départ : 05:58:00 → 05:57:06 → **05:56:04** (`bw-model-score.timer`
prochain **dimanche 05:59:38**). **Rien d'anormal.**

**Le contrôle de 07:30 a tiré à 07:31:01 et s'est TU** :

```
ⓘ 79 relevé(s), 58 comparable(s) ; durée : 10 points, pente -36 s/nuit ;
  mémoire : 10 points, pente -73 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate/négative, ou échéance hors horizon
```

**Les deux pentes sont identiques à hier** (−36 s/nuit, −73 Mo/nuit). Le
**25e centile des différences reste aveugle** par construction aux deux plus
grosses hausses de la fenêtre — il ne verra pas davantage le +140 s de cette
nuit.

⇒ **Aucun jeton du jour posé par le contrôle.** Vérifié dans les **deux**
dossiers avant écriture : `/var/lib/bw-model-verif` portait
`cri.jira.bw-pente-duree` du 17/09, `…memoire` du 23/09, `…purge-57014` du
06/10 ; `$HOME/.balise-watch-etat-alertes` portait `duree` du 07/10 et les deux
autres du **16/10 13:18**. **`bw_jira_signaler` était donc libre sur les trois.**

## 2. ✅ R2 : **le palier n'a PAS été franchi, et `agrume/grille` a rendu 21 Mo**

C'était la question n° 1 de la note d'hier, et elle est tranchée par la mesure.

| | 15/10 | 16/10 | 17/10 | Δ nuit |
|---|---|---|---|---|
| **total compte** | 9,228 Go | **9,959 Go** | **9,942 Go (99,4 %)** | **−17 Mo** |
| objets | — | 6 423 | **6 482** | +59 |
| `balise-watch-grids` | 8,467 Go | 9,189 Go | **9,162 Go** | −27 Mo |
| `model-verif` | 0,756 Go | 0,766 Go | **0,775 Go** | +9 Mo |
| **dont `agrume/grille`** | 4,652 Go / 673 | **5,344 Go / 769** | **5,323 Go / 766** | **−21 Mo / −3 obj.** |

✅ **LA HAUSSE DE +692 Mo SUR `agrume/grille` NE S'EST PAS REPRODUITE** — le
préfixe a **rendu** trois objets et 21 Mo. Le compte **recule** de 17 Mo et il
reste **58 Mo de marge** avant le palier (41 Mo hier). ⇒ **Le +731 Mo du 16/10
était une nuit, pas un régime.** ⚠️ **Mais la marge reste minuscule** : une
seule nuit comme celle du 16/10 franchit le palier.

✅ **Toujours aucun orphelin** : `agrume/grille/ : 766 présentes / 766
réclamées ✓`, idem `agrume/pi/grille/` (19/19), `agrume/pi/rafraichissement/`
(28/28), `agrume/piaf/` (11/11). Le correctif `874729f` + `c9497da` du 10/10
**tient pour la deuxième nuit**. ⇒ **le sujet reste la RÉTENTION, pas la
publication.**

### ⚠️ 2.1 Le préfixe qui monte vraiment n'est pas celui qu'on regarde

```
balise-watch-grids:agrume/pi        1.465 Go   3285 objets   +0.576 Go/mois  ← le seul en hausse franche
balise-watch-grids:agrume/grille    5.323 Go    766 objets   -0.004 Go/mois  ← le plus gros, "en baisse"
balise-watch-grids:arome/rafale     0.848 Go     63 objets   -0.371 Go/mois
balise-watch-grids:arome/sol        0.577 Go     63 objets   -0.283 Go/mois
balise-watch-grids:agrume/colonnes  0.542 Go    102 objets   -0.016 Go/mois
model-verif:fcst/2026               0.206 Go    127 objets   +0.085 Go/mois
```

ⓘ **`agrume/pi` porte 3 285 objets pour 1,465 Go** (≈ 446 Ko/objet) et affiche
**+0,576 Go/mois** : c'est le seul préfixe dont la pente mesurée soit nettement
positive. Il pèse sept fois moins que `agrume/grille` mais il **croît**.
⚠️ **À regarder quand la rétention sera tranchée** — pas une alerte
aujourd'hui, un point à ne pas perdre.

### ⛔ 2.2 L'échéance du palier : **641 j → 35 j → 57 j en trois nuits**

```
13/10  252 j (OK)   ·  14/10  182 j (OK)  ·  15/10  641 j (OK)
16/10   35 j (ÉCHEC) ·  17/10   57 j (ÉCHEC)
```

⛔ **Le défaut écrit le 25/09 est toujours là**, et cette nuit le démontre une
fois de plus : la pente est la **somme des 25e centiles des différences par
préfixe**, donc `agrume/grille` affiche **−0,004 Go/mois** après avoir pris
692 Mo puis rendu 21 Mo. Trois valeurs d'échéance pour le même palier en trois
nuits, dans un rapport de **1 à 18**.
ⓘ **C'est le MÊME statistique et le MÊME aveuglement que la pente du contrôle
de pente.** Les deux usages ont le même vice ; il mérite d'être traité **une
fois pour les deux**. C'est une **écriture**, elle attend ton accord.

### 2.3 Le garde-fou R2 reste en `failed`, et le cri est parti

```
2026-10-17T05:19:42Z run garde-fou-r2 en ÉCHEC (code 1, 6s) — 2 consécutif(s)
2026-10-17T05:19:42Z ALERTE — garde-fou R2 (garde-fou-r2) en echec …
2026-10-17T05:19:42Z ⓘ push parti (webhook, HTTP 200)
host=smtp.gmail.com … smtpstatus=250 … exitcode=EX_OK
```

⚠️ `bw-garde-fou-r2.service` est laissé en **`failed`** : c'est son état normal
après un cri, et le remettre à zéro serait une écriture. **Toujours aucun
ticket Jira pour ce motif**, et en créer un demande ton accord.

## 3. ✅ Mémoire : **le coût par ligne est IDENTIQUE à la veille — le 15/10 est définitivement une nuit atypique**

```
⛔ après le rejeu d'archive            : 3 010 Mo  (3 002 le 16/10)  ←   +8
ⓘ  après le score par régime          : 2 638 Mo  (2 606 le 16/10)  ←  +32  SOUS LE SEUIL
⛔ après l'oubli de la fenêtre rejouée : 3 383 Mo  (3 384 le 16/10)  ←   −1
```

**Jalon max 3 383 Mo (−1), +583 au-dessus du seuil.**

**COÛT PAR LIGNE REJOUÉE : 1 701,4 o (−0,02 o).**

```
29/09 1 671,3 o · 30/09 1 692,6 · 01/10 1 685,6 · 02/10 1 689,2
03/10 1 706,4  · 04/10 1 697,4 · 05/10 1 717,2 · 06/10 1 689,7
07/10 1 717,0  · 08/10 1 720,6 · 09/10 1 684,4 · 10/10 1 703,8
11/10 1 667,8  · 12/10 1 730,2 · 13/10 1 719,7 · 14/10 1 717,2
15/10 1 588,8  ← hors bande, vers le bas
16/10 1 701,4  ← retour dans la bande
17/10 **1 701,4**  ← AU MÊME MILLIÈME. Dix-neuf nuits, bande 1 667,8 – 1 730,2
```

✅ **Deux nuits dans la bande, dont une au même millième que la précédente.**
La note du 15/10 avait posé le critère d'avance ; le 16/10 l'avait tranché ;
cette nuit le **confirme par répétition**. ⇒ **Le 1 588,8 du 15/10 reste un
point isolé**, et ce n'est plus une lecture mais une mesure répétée.

**Calcul à taux constant.** Au taux du **16/10** (1 701,4 o) la fenêtre de
cette nuit rendrait **3 383,0 Mo** ; elle rend **3 383**. **Écart 0,0 Mo** : ni
le taux ni le volume n'ont bougé. Au taux du **14/10** (1 717,2 o) :
**3 414,4 Mo**, nous sommes **31,4 Mo sous**. Au taux du **29/09**
(1 671,3 o) : **3 323,1 Mo**, nous sommes **59,9 Mo au-dessus** — exactement
comme hier. La fenêtre a reculé de **586 lignes (−0,95 Mo)**.

✅ **DEUXIÈME NUIT À DEUX INCIDENTS.** Le « score par régime » reste **sous**
le seuil de 2 800 Mo (2 606 → **2 638**, +32, encore **162 Mo sous la barre**).
C'est le seul acquis réel côté mémoire, et **il tient une nuit de plus**.

**Les neuf jalons** : oubli fenêtre rejouée **3 383 (−1)**, rejeu d'archive
**3 010 (+8)**, score par régime **2 638 (+32)**, agrégat quotidien
**1 841 (+13)**, oubli fenêtre glissante **1 714 (−15)**, garde-fou de position
**1 183 (−17)**, mélange multi-modèle **1 172 (−23)**, oubli du chemin J-0
**954 (−5)**, relecture de l'archive **806 (+4)**. ⓘ **Aucun jalon ne bouge de
plus de 32 Mo** : la nuit est, côté mémoire, la plus plate de la série.

**La série du jalon max** : `3 356 · 3 394 · 3 321 · 3 444 · 3 422 · 3 416 ·
3 161 · 3 384 · 3 383`. Sur dix-neuf nuits elle oscille **entre 3 161 et 3 444
sans pente nette**.

✅ **SWAP : LA DIVERGENCE DE DEUX NUITS SE RECALE.** Les 15 et 16/10 les deux
indicateurs allaient en sens inverse, avec des signes **inversés** d'une nuit à
l'autre. Cette nuit ils vont **ensemble et faiblement** : pic **2 347,4 Mo
(−82,1)**, pages sorties **2 482 829 (+9 874, +0,4 %)**. ⇒ **La question n° 18
de la note du 16/10 (« troisième nuit de divergence, ou recalage ? ») est
tranchée : RECALAGE.** Le record de 2 918 498 pages du 15/10 ne revient pas et
reste ce qu'il était : **une nuit, pas un palier**. `oom = 0`, pic système
**3 603,6 Mo (+19,1)**.

**Les trois conditions de fermeture de KAN-4 : 1 sur 3**, inchangé.
Jalon mesurément retombé → **NON** (3 383 Mo, −1, +583 au-dessus du seuil).
Swap au pic ≈ 0 → **NON** (2 347,4 Mo). Contrôle muet sur `bw-pente-memoire`
→ **OUI**. ⇒ **le ticket reste ouvert.**

**Le remède ne change pas** : la **ligne en tuple** (`enquete-pente-10-09.md`
§2.6, ≈ −1 030 o/ligne), après la mesure `tuple` vs `namedtuple` à la sonde.
L'élagage de `units` avait échoué (−124 Mo au lieu de −1 500) : les gains sont
dans la **structure**. **Rien de déployé côté mémoire depuis `af25efb`
(21/09) : 27e nuit sans levier.**

## 4. ⚠️ Durée : **+140 s, du calcul, et 93 % du mouvement est DANS les étapes**

```
durée  4 861 → 5 001 s  (+140)
marge  3 239 → 3 099 s  (−140)  ⇒ 39,99 % → 38,26 % du garde de 8 100 s
cpu_s  3 895,0 → 4 001,0 (+106,0)
attente  966,0 → 1 000,0 (+34,0)
```

⚠️ **C'est du calcul à 76 %** (+106,0 s de calcul contre +34,0 s d'attente).
La durée **reste dans la bande de la semaine** (4 861 – 5 051) et la marge
au-dessus de **38 %** du garde : c'est un **retour au niveau des 11–15/10**
après la nuit basse du 16/10, pas une dérive.

| étape | 14/10 | 15/10 | 16/10 | 17/10 |
|---|---|---|---|---|
| `regime` | 1 687,1 | 1 671,7 | 1 608,2 | **1 675,3 (+67,1)** |
| `glissant` | 938,7 | 1 017,5 | 942,4 | **963,8 (+21,4)** |
| `stabilite` | 346,1 | 296,6 | 284,9 | **316,4 (+31,5)** |
| `rejeu` | 84,7 | 83,1 | 75,6 | **85,6 (+10,0)** |
| somme des quatre | 3 056,6 | 3 068,9 | 2 911,1 | **3 041,1 (+130,0)** |
| hors étapes | 1 975,4 | 1 982,1 | 1 949,9 | **1 959,9 (+10,0)** |

⇒ **93 % du mouvement est DANS les quatre étapes**, 7 % hors étapes. Sur six
nuits le hors-étapes a porté **90 %, −158 %, 97 %, 35 %, 17 %, puis 7 %**.

⛔ **DÉCOUPLAGE TEMPS / VOLUME : le temps monte, TOUS les volumes baissent.**

```
lignes_regime       127 915 →   127 718   (−197)
lignes_glissant      10 416 →    10 414   (−2)
lignes_score_zone   138 331 →   138 132   (−199)
lignes_daily         69 597 →    69 573   (−24)
balise_jours_rejeu 2 085 521 → 2 084 935  (−586)
```

⇒ **La hausse n'est pas un effet de volume : c'est du coût unitaire.** Coût par
ligne de `regime` **13,12 ms (+0,55)** ; coût par ligne de `glissant`
**92,55 ms (+2,07)** pour un volume stable (−2 lignes).

**Hors étapes** (onze nuits) :

```
1 991,2 · 2 051,6 · 2 100,2 (10/10) · 1 967,0 · 2 015,8 · 1 989,0
· 1 975,4 · 1 982,1 · 1 949,9 · 1 959,9 (17/10)
```

⛔ **Le bloc n'est toujours pas instrumenté** — publication, Murphy, événements,
pression, duels, purge : six postes, **aucun jalon de temps**.
ⓘ **Mais l'argument s'affaiblit une TROISIÈME nuit de suite** : 93 % du
mouvement est dans les étapes déjà instrumentées, et le poste est nommé
(`regime`, +67,1 s). **La demande reste ouverte, elle n'est plus urgente.**

### ⚠️ 4.1 `bw-regime-sensibilite` : **le compteur passe à 1 / 2**

Coût par ligne de `regime` (ms) :

```
13,39 (01/10) · 13,24 · 14,02 · 13,67 · 13,53 · 15,07 · 14,86 · 14,87
· 13,99 · 14,42 · 12,94 (11/10) · 13,02 · 13,14 · 13,20 · 13,06
· 12,57 (16/10)  ← le plus bas des seize relevés
· **13,12 (17/10)**  ← +0,55, PREMIÈRE HAUSSE après deux reculs
```

⚠️ **Première hausse : compteur à 1 / 2.** L'arbitrage unique du 07/10 demande
**deux hausses consécutives** ; il n'y en a qu'une. **Aucun motif n'est posé**,
et je n'en pose pas seul. ⓘ **Le niveau reste bas** : 13,12 ms est **sous** les
13,39 du 01/10 et **1,95 ms sous** les 15,07 du 06/10 qui avaient motivé le
critère. ⇒ **Si une deuxième hausse suit demain, la question te sera reposée
— c'est exactement le cas que le critère est fait pour attraper.**

**Volumes** : `lignes_regime` **127 718 (−197)**, `lignes_score_zone`
**138 132 (−199)**, `lignes_daily` **69 573 (−24)**, `lignes_glissant`
**10 414 (−2)**.

**Remontée du garde : NON lancée, NON demandée.** Le contrôle n'en propose
aucune (pente négative, `proposition()` n'est pas atteinte). Garde **8 100 s
(135 min)** pour un run de **83,4 min**. ⛔ `10-timeout-s3.conf` **n'a pas été
touché.**

**KAN-3 : commenté, par `bw_jira_commenter`, et NON rouvert.** ⓘ La consigne
dit de commenter **si la durée AUGMENTE** : elle augmente de 140 s. Le
commentaire porte les chiffres, la répartition par étape, le découplage
temps/volume, le compteur `regime-sensibilite` à 1/2, et le rappel que le
25e centile ne verra pas ce +140 s. **Aucune réouverture, aucune transition.**

## 5. ✅ Purge : **dixième nuit propre (10 / 3), et le 57014 n'est NULLE PART**

```
→ purge model_score_zone : 135 772 ligne(s) effacée(s) en 8 tranche(s)
ⓘ purge model_character : rien avant le 2027-02-04 (première écriture
  2026-08-08, rétention 180 j) — aucune requête lancée.
```

**Le bloc `model_score_zone` est propre, poste par poste :**

- **aucune TRANCHE à 57014** (aucun `?as_of=eq.J&regime=eq.R` en HTTP 500)
- **aucune SONDE** (« plus vieille journée illisible » absente)
- **aucun « des lignes RESTENT »** — donc rien ne reste en base
- nombre de lignes **lisible** (135 772), **8 tranches** comme les neuf nuits
  précédentes

| nuit | état du bloc `model_score_zone` | compteur |
|---|---|---|
| 07→08 (08/10) | propre | 1 |
| 08→09 | propre, 129 650 l. / 8 tr. | 2 |
| 09→10 | propre, 129 594 l. / 8 tr. | 3 |
| 10→11 | propre, 129 233 l. / 8 tr. | 4 |
| 11→12 | propre, 129 534 l. / 8 tr. | 5 |
| 12→13 | propre, 132 089 l. / 8 tr. | 6 |
| 13→14 | propre, 131 391 l. / 8 tr. | 7 |
| 14→15 | propre, 131 299 l. / 8 tr. | 8 |
| 15→16 | propre, 132 525 l. / 8 tr. | 9 |
| 16→17 (17/10) | **propre, 135 772 l. / 8 tr.** | **10** |

ⓘ Les **3 247 lignes** d'écart avec hier **ne sont pas un signal** : le volume
effacé suit le volume de la journée purgée (≈ 125 000–136 000).

### ✅ 5.1 **ET `model_verif_daily` NE RÉCIDIVE PAS** — pas de troisième fois

```
14/10   purge model_verif_daily : 57014     ← première fois
15/10   rien
16/10   purge model_verif_daily : 57014     ← récidive
17/10   rien — model_verif_daily écrit ses 69 573 lignes sans incident
```

✅ **`n_57014 = 0` au registre, et le journal ne porte aucun 57014, nulle
part.** C'est le point nouveau de la nuit.

⛔ **MAIS LA RÉSERVE N° 1 TIENT, ET C'EST ELLE QUI COMMANDE.** Le 57014 a
**changé d'adresse** trois fois au lieu de disparaître (10/10 vers
`bw_character_avance`, 14/10 et 16/10 vers `purge model_verif_daily`). **Une
nuit à zéro ne réfute pas ce schéma**, et le précédent est exactement
celui-là : **les 03, 04 et 05/10 avaient déjà donné trois nuits à
`n_57014 = 0` avant le retour du 06/10.** *Une nuit ne fait pas une pente*, et
celle-ci est **une** nuit — seizième usage de la leçon en vingt jours.

⛔ **LA RÉSERVE N° 2 TIENT ENTIÈREMENT ET ELLE EMPIRE.**
`model-verif/diagnostic_base_sous_tension_2026-09-29.sql` (lecture seule,
9 blocs, SQL Editor) **n'a toujours pas été joué : DIX-HUIT JOURS.**

⇒ ⛔ **Ma lecture : NE PAS FERMER.** Le compteur du motif suivi est à **10 / 3**
et remplit sa condition depuis sept jours ; la nuit est **entièrement propre** ;
mais **la dernière récidive date d'HIER**, sur une requête de purge voisine, et
le diagnostic qui dirait si c'est « cette requête-ci » ou « la base entière »
n'a pas été joué. Fermer maintenant reviendrait à fermer « le 57014 » sur la
foi d'**une seule nuit sans lui**. *Un ticket fermé à tort vaut moins qu'un
ticket ouvert.* **La condition raisonnable ne change pas : jouer le `.sql`
d'abord.**
⚠️ **Et deux motifs resteraient sans ticket** : « la base est sous tension »,
qui n'en a jamais eu, et `model_verif_daily`, qui a expiré **deux fois en
quatre nuits**.

✅ Le contrôle s'est tu sur ce motif, et c'est **correct** : depuis le 07/10,
`constats()` lit `score.log` via `bilan_purge()`. Ici il n'y a **même pas**
d'avertissement à interpréter. Le faux « purge en échec » du 06/10 ne s'est pas
reproduit : **onzième nuit.**
✅ `bw_character_avance` propre pour la **septième** nuit (**391 356
accumulateurs avancés sur 391 356 envoyés**).

## 6. Position : **les quatre confirmées tiennent, aucun cri — troisième nuit**

```
⛔ position : 11 balise(s) divergent du gel (10 j lus), dont 4 CONFIRMÉE(S) (≥ 10 j)
   ⛔ pioupiou:2171          38 915 m · 10 j · nœud CHANGE · profil CHANGE · Windbird 2171
   ⛔ pioupiou:1378          18 508 m · 10 j · nœud CHANGE · profil CHANGE · Col de la Merquiere
   ⛔ pioupiou:367            6 764 m · 10 j · nœud CHANGE · profil CHANGE · Le relais
   ⛔ infoclimat:STATIC0491   1 159 m · 10 j · nœud CHANGE
   ·  84 (9 753 m) · 2139 (1 913) · 1618 (744) · 1766 (739) · 1698 (321) · 1710 (259) — toutes à 4 j
   ·  pioupiou:1333  87 693 m ·  1 j   ← continue de reculer (10 → … → 3 → 2 → 1)
```

✅ **Aucun cri n'est parti, et c'est le comportement voulu** : le compte reste
à **4**, donc **pas de front**. Les quatre confirmées sont **exactement les
mêmes** que les 15 et 16/10 — **troisième nuit identique**.
ⓘ Les six balises à 3 j sont passées à **4 j** ; `1333` descend de **2 à 1 j**
et **continue de sortir du lot**. ⚠️ **Aucune prévision ici** : la leçon
affinée du 15/10 dit que l'extrapolation ne vaut **qu'à un jour, pour une
balise nommée déjà à 9 j** — aucune n'y est. Les six à 4 j arriveraient à 10 j
**dans six nuits**, et sept démentis d'échéance en onze jours disent de ne pas
l'écrire comme une échéance.

**Geste attendu de Yann, inchangé** : trancher **`2171`** (38,9 km) et
**`STATIC0491`** (1 159 m) — candidates « AUTRE balise » et changement de
maille —, puis **`1378`** (18,5 km) et **`367`** (6,8 km). Statuer sur
**`1333`**. Puis poser `position_suspecte` + `position_note` sur `station_zone`
par `.sql`.
ⓘ **Question toujours ouverte depuis le 01/10** : le cri est **à front dans
les deux sens** ; faut-il qu'il **recrie** pour une balise qui **reste**
confirmée ? **Troisième nuit d'affilée que la question se pose dans les mêmes
termes** : quatre balises confirmées, deux depuis dix jours, **zéro signal**.

## 7. ✅ Le correctif `--ipv4` du 07/10 : **quatrième examen, réussi**

```
2026-10-17T05:19:42Z ALERTE — garde-fou R2 (garde-fou-r2) en echec …
2026-10-17T05:19:42Z ⓘ push parti (webhook, HTTP 200)
host=smtp.gmail.com … smtpstatus=250 … exitcode=EX_OK
```

✅ **Quatrième ⛔ depuis le correctif, quatrième push réel, HTTP 200.** Aucun
`429` de `ntfy` nulle part.

⚠️ **`BW_DISCORD_WEBHOOK_URL` est TOUJOURS ABSENTE du `.env`.** Relevé par
**noms seuls** (aucune valeur lue) : **25 variables**, les mêmes, fichier
**inchangé depuis le 13/09 18:08**. ⇒ `bw_push_discord` reste **codé, testé,
muet** — et cette nuit il y avait **un ⛔ à pousser**.
`~/installer-webhook-discord.sh` attend toujours Yann : **35e jour.** ntfy
reste **seul canal push**.

## 8. ✅ ρ hors [0, 1] : **troisième baisse consécutive**

```
ⓘ référence combinée : 383 balise(s) sur 3 704 avaient un ρ hors [0, 1],
  ramené à la borne
```

```
307 (08/10) · 382 · 349 · 381 · 413 · 437 · 475 (14/10) · 452 · 404 · **383 (17/10)**
```

✅ **Troisième recul consécutif (−21)** : **475 → 452 → 404 → 383**, soit
**−19 % en trois nuits**. **10,34 % du parc** contre 10,91 % hier.
⇒ **Rien n'a été créé, et il n'y a toujours pas de raison de créer.** Le
niveau reste **+24,8 % au-dessus du 08/10** (307), mais la série **oscille
comme toutes les autres**. ⓘ La question du 14/10 (« la seule série qui monte
franchement et sans démenti ») est **close** : elle a été démentie trois fois
de suite.

## 9. ✅ Témoins du mélange : **la grille de lecture du 12/10 REMARCHE — l'anomalie d'hier n'a duré qu'une nuit**

```
⛔ témoins du mélange : sur 7 545 balise-jours×échéance, le mélange fait
   3,192 km/h contre 3,1735 pour le meilleur membre a priori
   (gain −0,6 %, mélange devant dans 48,0 % des cas) ;
   contre la moyenne UNIFORME, sur 1 120 : 3,2352 vs 3,3921 (gain 4,6 %)
```

```
gain contre le MEILLEUR MEMBRE : 7,4 % → 5,5 → −0,6 (07/10) → +2,5 → −1,2 → −0,1 → −0,0 → +1,6 → +3,1 → +2,2 → +3,3 → +1,1 → **−0,6 (17/10)**
« devant » dans : 49,2 % → 50,1 → 49,1 → 49,2 → 50,1 → 51,6 → 50,0 → 52,3 → 49,9 → **48,0 %**
gain contre la moyenne UNIFORME : 6,0 % → 4,9 → 4,8 → 3,1 → 4,8 → 3,2 → 3,4 → 4,7 → 6,5 → 4,7 → 3,9 → 2,6 → **4,6 %**
```

✅ **ET L'EXPLICATION HABITUELLE REVIENT.** La leçon du 12/10 dit que cet
indicateur **suit l'erreur absolue** (journée ventée ⇒ gain qui baisse). Hier
elle avait **échoué** pour la première fois : le gain reculait de 2,2 points à
erreur **plate**. Cette nuit, l'erreur absolue **bondit de 16,6 %**
(2,7365 → **3,192 km/h**) et le gain contre le meilleur membre recule de
1,7 point : **la grille remarche exactement.**

⇒ **L'anomalie du 16/10 n'a duré qu'une nuit.** La note d'hier avait prévenu
qu'elle ne concluait rien : **elle a bien fait.**

⚠️ **Et les deux mesures divergent, dans le bon sens** : le gain contre la
moyenne **uniforme** **MONTE** (2,6 → **4,6 %**, +2,0 points) pendant que le
gain contre le meilleur membre baisse. Sur une journée nettement plus ventée,
le mélange **reprend de l'avance sur l'uniforme** — c'est ce qu'on attend d'un
mélange pondéré.

⇒ ✅ **La décision du 12/10 de ne pas créer de motif Jira est MAINTENUE, et
pour une raison PLUS SOLIDE qu'hier** : l'indicateur se comporte comme la
grille le prédit, et la mesure contre l'uniforme progresse. ⓘ **Ce qu'il faut
regarder demain reste le même** : un recul **à erreur absolue constante**.

ⓘ Composition : **7 950** balise×échéance avec poids sur 30 j de cache
(64,6 s) — +6 h : 2 616 `bw_mix`, 414 témoins uniformes, 207 sans poids ;
+24 h : 2 528 / 391 / 110 ; +48 h : 2 529 / 413 / 274.
ⓘ **Témoin du corrigé** : sur 9 167 balise-jours échantillonnés, le vrai
antécédent gagne **15,9 %** et celui d'une AUTRE balise **−0,6 %** — part
imputable au site **16,5 points** (15,8 hier).
ⓘ **Témoin du corrigé FIN** : sur 4 188 balise-jours, le S2 gagne **16,6 %**
sur le brut ; le fin gagne **8,0 points de plus** sur le S2, contre **−2,0**
aux cellules TOURNÉES — part imputable au secteur et à l'heure : **10,0
points**.

## 10. Le reste du journal

- ✅ **Self-test du scoring : VERT** (lot S3, aucune lecture réelle, aucune
  écriture). Écart des deux mélanges : `mse_comb` 17,841 contre `mse_comb_vec`
  17,841 (**+0,00 %**).
- ⚠️ **Stabilité des rangs : τ = 0,784 sur 65 cases** (0,79 / 71 le 16/10).
  **Les deux redescendent ENSEMBLE**, légèrement, après les deux plus hauts
  d'hier : l'échantillon fait 53 → 54 → 50 → 56 → 62 → 65 → 71 → **65**, et τ
  passe de 0,79 à **0,784**. ⓘ **Deuxième nuit où les deux vont dans le même
  sens** — à suivre, pas à conclure.
- ⚠️ **5 écarts au recalcul indépendant** (4 le 16/10) — journée recalculée
  **2026-10-16**, 13 balise-jours comparés, 7 sous le seuil de 6 h.
  **Tous en `fcstagrume`**, et pour la première fois **tous en `agrume_pi`**,
  tous de la **même signature** (« 0 ou 1 h appariée ici (< 6) mais la base
  porte une ligne ») : `aemet:9839V` (+6 h), `mf:65125001` (+48 h),
  `pioupiou:124` (+24 h), `windsmobi:ffvl-5051` (+48 h), `infoclimat:000YD`
  (+24 h). ⓘ **Dixième nuit de suite la même signature** (5 · 5 · 6 · 5 · 7 ·
  6 · 4 · 4 · **5**) ; les balises concernées **changent entièrement chaque
  nuit** : ce n'est pas un lot fixe, c'est un **désaccord systématique sur le
  seuil des 6 heures appariées**.
- ⚠️ **Événements : 33 882 lignes en base** (`onset` 13 593, `drop` 12 806,
  `ramp` 5 943, `reversal` 1 482, `breeze_yield` 58) contre **20 661** hier,
  soit **+64 %** ; **29 244 combinaisons publiables** (29 220 hier), 29 545
  écartées sous le quorum de 8, **33 614 lignes non publiées**. ⓘ **Le saut
  est sur les lignes en base, pas sur les combinaisons publiables** — cohérent
  avec une journée bien plus ventée (erreur absolue +16,6 %, §9) : plus de
  vent, plus d'événements détectés. **Une nuit : rien à conclure**, mais c'est
  le plus gros mouvement du journal après R2.
  ⓘ 3 452 balises zonées, 1 423 cases fines dont **739** à moins de 2 balises.
- **Murphy** : 66 137 triplets, 63 999 décomposés, 266 balises tenues dehors
  (doublon ou position suspecte), 0,9 s.
- **FDR** : brut 7 010 tests, 1 792 survivants à BH α = 0,1 (seuil p ≤ 0,02395,
  p min 0,00399), 137 rangs retirés sur 1 113 publiés ; corrigé 6 699 tests,
  1 197 survivants (seuil p ≤ 0,01597), 144 rangs retirés sur 669.
- **Duels appariés** : lead 6 → 65 348 lignes depuis le 17/09 (749 retirées) ;
  lead 24 → 24 050 lignes (281 retirées). ⓘ Cumul tronqué par la rétention 30 j.
- **Pression** : 17 926 lignes, 691 points de prévision portent `pmsl`,
  **862 appariées** (médiane 18,1 km) ; refusées : 212 hors rayon, 30 hors Δz,
  4 trop hautes.
- **Rétrécissement vers le parent** : 136 533 cases fines rapprochées de leur
  échelon supérieur.
- **Publication** : `model_scores.json` 120 945 Ko, `model_scores_light.json`
  7 196 Ko (520 Ko gzippé).
- **Manches** : **50 nuits** suivies depuis le 24/08, **722 cases**
  zone×lead×modèle avec au moins une manche gagnée.
- **Accumulateurs** : 5 418 entrées écartées (`doublon_de`, lot L17), 348
  antérieures à la naissance de la balise (`notee_depuis`, lot L15-bis).
- **Rejeu d'archive** : 2 084 935 balise-jours sur 30 journées (0 rejouée, 0
  vide, 3 140 écartés) en 85,6 s.
- **Climatologie horaire** : 3 815 balises (233,0 s) ; médiane *k* = 0,162.
- **Observations** : **3 747** balises le jour, 3 742 la veille (+5).
- **`mutations_memoire`** : ⚠️ **NEUVIÈME nuit sans aucune ligne au journal.**
  Le relevé « 3 mutations non vues (2, 5, 13) » ne peut pas être revérifié ;
  dette antérieure, **statut inchangé faute de mesure.**
- `✅ terminé (650 963 lignes écrites en base)` (589 744 le 16/10) ; `registre :
  1 ligne écrite (2026-10-17, 5 001 s, jalon max 3 383 Mo, swap 2 347,4 Mo)`.

## 11. ✅ Les tickets : état vérifié par GET **avant** et **après**, trois commentaires

GET `/rest/api/3/issue/<clé>?fields=summary,status,comment` avant écriture,
**HTTP 200** sur les trois. Les trois sujets sont **ceux relevés le 07/10**,
inchangés.

| ticket | statut | comm. avant | canal utilisé | comm. après |
|---|---|---|---|---|
| **KAN-3** `bw-pente-duree` | **Terminé** / `done` | 24 | **`bw_jira_commenter KAN-3`** | **25** ✅ |
| **KAN-4** `bw-pente-memoire` | **À faire** / `new` | 36 | `bw_jira_signaler bw-pente-memoire` | **37** ✅ |
| **KAN-5** `bw-purge-57014` | **À faire** / `new` | 19 | `bw_jira_signaler bw-purge-57014` | **20** ✅ |

**Ce que chaque commentaire porte :**

- **KAN-3** — ⚠️ la durée **AUGMENTE de 140 s** (consigne : commenter dans ce
  cas) ; **76 % de calcul** (+106,0 s) contre 34,0 s d'attente ; la répartition
  par étape et le fait que **93 % du mouvement est DANS les quatre étapes** —
  donc la demande d'instrumenter le hors-étapes **s'affaiblit une troisième
  nuit** ; ⛔ le **découplage temps/volume** (tous les volumes reculent pendant
  que les étapes prennent +130 s ⇒ **coût unitaire**, 13,12 ms/ligne pour
  `regime`, 92,55 pour `glissant`) ; ⚠️ **`bw-regime-sensibilite` à 1 / 2**,
  aucun motif posé ; le rappel que la pente du contrôle est le **25e centile
  des différences** et ne verra pas ce +140 s, **comme la pente d'`audit_r2.py`
  qui a dit 641 j, 35 j puis 57 j en trois nuits** ; **remontée du garde ni
  lancée ni demandée**. ⛔ **Aucune réouverture.**
- **KAN-4** — ✅ le coût par ligne rejouée **IDENTIQUE à 0,02 o près**
  (1 701,4 o), qui **confirme par répétition** que le 15/10 était une nuit
  atypique ; le jalon à **3 383 Mo (−1)**, **+583** au-dessus du seuil ; le
  calcul à taux constant (**écart 0,0 Mo** au taux d'hier, **31,4 Mo sous** le
  taux du 14/10, **59,9 Mo au-dessus** de celui du 29/09) ; les neuf jalons
  chiffrés (**aucun ne bouge de plus de 32 Mo**) et ✅ la **deuxième nuit à
  deux incidents** (score par régime 2 638, 162 Mo sous la barre) ; ✅ **le
  RECALAGE du swap** qui tranche la question n° 18 du 16/10 ; les trois
  conditions de fermeture **1 sur 3** ; la pente du contrôle à **−73 Mo/nuit** ;
  la ligne en tuple et la **27e nuit sans levier** ; `mutations_memoire` non
  mesurable (9e nuit).
- **KAN-5** — ✅ bloc `model_score_zone` **propre pour la 10e nuit** (135 772 l.
  / 8 tr., aucune tranche, aucune sonde, aucun « RESTENT »), **compteur 10 / 3**
  nuit par nuit ; ✅ **`n_57014 = 0` et AUCUN 57014 nulle part**, donc **pas de
  troisième fois** sur `model_verif_daily` ; ⛔ **mais la réserve n° 1 tient**
  (le 57014 change d'adresse : 10/10, 14/10, 16/10) avec le précédent des
  03–05/10, trois nuits à zéro avant le retour du 06 ; ⛔ **la réserve n° 2
  entière** — le `.sql` **jamais joué, dix-huit jours** ; ⛔ **ma lecture : ne
  pas fermer**, et pourquoi fermer sur une seule nuit sans lui serait prématuré ;
  les deux motifs qui resteraient sans ticket ; `bw_character_avance` propre
  (7e nuit) et le contrôle correctement muet (11e nuit).

⛔ **Aucune création, aucune transition, aucune réouverture, aucune fermeture.**
Les trois statuts sont **identiques** après écriture (revérifiés par GET).

ⓘ **Les deux canaux ont servi, et chacun à sa place.** Le contrôle s'étant tu,
les jetons du jour étaient **libres** : `bw_jira_signaler` a servi pour les
deux motifs **ouverts** et a **posé les jetons** (`cri.jira.bw-pente-memoire`
et `cri.jira.bw-purge-57014` datent maintenant du **17/10 11:10**, côté
`$HOME` uniquement). **`bw_jira_commenter` a servi pour KAN-3**, parce qu'il
est **« Terminé »** et qu'un `bw_jira_signaler` sur ce motif **créerait un
ticket neuf** — `bw_jira_chercher` filtre sur `statusCategory != Done`.
✅ Vérifié après coup : `cri.jira.bw-pente-duree` est **inchangé** (07/10 côté
`$HOME`, 17/09 côté `/var/lib`) — le commentaire délibéré **ne touche pas au
jeton du jour**, comme prévu.
✅ Vérifié après coup : `/var/lib/bw-model-verif` est **inchangé** (17/09,
23/09, 06/10) — la relance manuelle du contrôle n'a rien écrit, puisqu'il s'est
tu.

ⓘ **Technique de l'envoi** (celle des 15 et 16/10) : les trois corps ont été
écrits sur le **Mac** (`/tmp/bw-17-10/`), encodés en base64 et passés au VPS
**par l'entrée standard de `ssh`**, décodés dans une **variable shell**.
**Aucun fichier n'a été déposé sur le VPS** en dehors des `mktemp -d` internes
à `bw_jira_http`, effacés par la fonction elle-même.

## 12. Ce qui a été touché

**VPS — règle de LECTURE SEULE pleine et entière, respectée.** Toutes les
commandes `ssh` en lecture sauf les trois POST Jira : `date -u`, `tail -n 3`
du registre, `journalctl` du contrôle, `systemctl list-timers`,
`controle_quotidien.py --verbeux`, plusieurs passes de
`journalctl -u bw-model-score.service` et `-u bw-garde-fou-r2.service` avec
`grep`/`sed`, `systemctl status` du garde-fou R2, `sed`/`grep` dans
`bw_jira.sh`, `ls -la` des deux dossiers d'état, relevé du `.env` **par noms de
variables seuls**, et **six GET** Jira (trois avant, trois après).
**Aucun `systemctl start/restart/daemon-reload`, aucun `enable`, aucun SQL
joué, aucun `rsync`, rien écrit dans `~/balise-watch` ni dans `/etc`. Rien
touché sur R2.**
⚠️ `controle_quotidien.py --verbeux` a été **relancé à la main** : c'est une
lecture (il n'écrit son jeton que s'il parle, et il s'est tu) — vérifié, les
jetons de `/var/lib/bw-model-verif` sont **inchangés** après la relance.
⚠️ `bw-garde-fou-r2.service` est laissé en **`failed`** : c'est son état normal
après un cri, et le remettre à zéro serait une écriture.
**Aucun secret lu par valeur** : le `.env` est **sourcé** (`set -a; . …;
set +a`) et lu **par noms de variables seuls**. `bw_jira.sh` passe par
`curl -K -`, jamais `-u`.
**Écritures Jira : trois commentaires** (voir §11).

**Mac** : trois corps de commentaire et le script d'envoi dans
`/tmp/bw-17-10/` (fichiers de travail), cette note dans
`notes-projet/verdict-pente-17-10.md`. **Un commit local**, depuis la **racine
du dépôt serveur**. **Pas de `git push`.**

**Projet Claude** : cette note, **créée** (absente de la liste d'ouverture de
session).

**Notification : UNE**, sur le fait que le palier R2 **n'a pas été franchi** —
c'est la réponse à la question n° 1 de la note d'hier, et elle ferme la boucle
ouverte par le cri alarmiste du 16/10.

## 13. ✅ L'horaire de la routine : **+1 h 56**, la meilleure valeur depuis le 13/10

Programmée pour **07:07:05 UTC**, tirée à **09:03:28 UTC**.

```
02–03/10  AUCUN TIR
04–06/10  retard jusqu'à 4 h 10
07/10     à l'heure
08/10     +2 h 10   ·  09/10  +6 h 40  ·  10/10  +2 h 13
11/10     +5 h 51   ·  12/10  +10 h 59  ← pire valeur
13/10     +52 min   ·  14/10  +6 h 11  ·  15/10  +7 h 37
16/10     +4 h 03   ·  17/10  **+1 h 56**
```

⚠️ **Dix matins sur seize ont dérivé, deux n'ont pas tiré** — mais c'est
**la deuxième meilleure valeur de la série** après le 13/10.
ⓘ **Le VPS est à l'heure, et il n'y est pour rien** : notation à **05:56:03**
(prochaine dimanche **05:59:38**), contrôle à **07:31:01** (prochain dimanche
**07:30:30**). **Le trou est côté planification de la routine**, et il reste le
premier risque du dispositif.

## 14. Ce qui reste — et ce qui demande Yann

**Décisions, par ordre d'urgence :**

1. ⛔ **R2 : trancher la rétention d'`agrume/grille`.** ✅ Le palier **n'a pas
   été franchi** (9,942 Go, **−17 Mo**, `agrume/grille` **rend 21 Mo et 3
   objets**) : **le +692 Mo d'hier était une nuit, pas un régime**, et il n'y a
   **pas d'urgence ce soir**. ⚠️ **Mais il reste 58 Mo de marge**, et une seule
   nuit comme celle du 16/10 franchit le palier. Franchir **facture, ne bloque
   pas** (et tu l'avais accepté le 27/09). Levier chiffré le 25/09 : **rétention
   3 → 2 runs ≈ −1,7 Go** ; un seul run retiré rend **≈ 700 Mo**. **Ça reste la
   décision n° 1**, mais prise à froid.
2. ⛔ **Jouer `diagnostic_base_sous_tension_2026-09-29.sql`** (lecture seule,
   9 blocs, SQL Editor). **DIX-HUIT JOURS d'attente.** C'est lui seul qui
   tranche « cette requête-ci, ou la base entière ? » — et c'est **la condition
   que je mets à la fermeture de KAN-5**.
3. ⛔ **FERMER KAN-5 ? NON, et l'avis ne bouge pas malgré une nuit parfaite.**
   Compteur du motif suivi **10 / 3**, bloc entièrement propre, **`n_57014 = 0`
   et aucun 57014 nulle part**. Mais la dernière récidive date d'**hier**, la
   réserve n° 1 (le 57014 change d'adresse) tient, et les 03–05/10 avaient déjà
   donné **trois** nuits à zéro avant le retour du 06. ⇒ **Ne pas fermer avant
   le `.sql`.** Et il faudra dire où vont « la base est sous tension » et
   `model_verif_daily`, sans ticket.
4. ⛔ **Veux-tu un motif Jira `bw-r2-palier` ?** `bw-garde-fou-r2` a crié quatre
   fois en dix jours et **n'a aucun ticket**. Rien n'a été créé : **ça demande
   ton accord.** ⓘ Question posée hier, **restée sans réponse**.
5. ⚠️ **Corriger la pente d'`audit_r2.py`.** « Palier atteint dans **57 j** »
   après **35 j** hier et **641 j** avant-hier : **trois valeurs dans un rapport
   de 1 à 18 pour le même palier en trois nuits**. La pente est la **somme des
   25e centiles des différences par préfixe**, et elle affiche **−0,004 Go/mois**
   pour `agrume/grille`. Défaut **écrit le 25/09**, toujours là. ⓘ **Même
   statistique et même aveuglement que la pente du contrôle de pente** : à
   traiter **une fois pour les deux**. C'est une **écriture**.
6. ⚠️ **Mémoire : rien ne bouge, et c'est l'information.** Coût par ligne
   **1 701,4 o (−0,02, identique)**, jalon **3 383 Mo (−1)**, aucun jalon ne
   bouge de plus de 32 Mo. ✅ Deux acquis qui tiennent : **deuxième nuit à deux
   incidents** et **recalage du swap**. ⇒ **Le remède reste la ligne en tuple**
   (≈ −1 030 o/ligne) après la mesure `tuple` vs `namedtuple` à la sonde.
   **KAN-4 reste ouvert (1 / 3), 27e nuit sans levier.**
7. ⛔ **Trancher les cas de position — troisième nuit identique, aucun cri.**
   `2171` (38,9 km), `1378` (18,5 km), `367` (6,8 km), `STATIC0491` (1 159 m),
   plus `1333` qui **continue de sortir du lot** (→ 1 j). Puis `position_suspecte`
   + `position_note` par `.sql`. ⓘ **La question du 01/10 se pose pour la
   troisième nuit dans les mêmes termes** : quatre balises confirmées, deux
   depuis dix jours, **zéro signal**. Faut-il que le cri **recrie** ?
8. ⛔ **Lancer `~/installer-webhook-discord.sh`.** `BW_DISCORD_WEBHOOK_URL`
   toujours absente, **35e jour** — et cette nuit il y avait **un ⛔ à pousser**.
   ✅ Le `--ipv4` tient (4e push réel, HTTP 200), mais ntfy reste **seul**.
9. ⚠️ **Un plancher de niveau pour `bw-regime-sensibilite` ?** La question
   **revient** : compteur **1 / 2** après **+0,55 ms** (12,57 → 13,12). Le
   niveau reste bas (sous le 13,39 du 01/10), mais c'est la première fois en
   quatre matins que le compteur n'est pas à zéro. **Si une deuxième hausse
   suit demain, je te repose la question du motif.**
10. ⚠️ **Instrumenter le bloc hors étapes de `run.sh` ?** **L'argument
    s'affaiblit une TROISIÈME nuit** : 93 % du mouvement est **dans** les étapes
    et le poste est nommé (`regime`, +67,1 s). Sur six nuits le hors-étapes a
    porté 90 %, −158 %, 97 %, 35 %, 17 %, **7 %**. Décision à toi.
11. ✅ **Témoins du mélange : plus rien à décider cette nuit.** La grille de
    lecture du 12/10 **remarche** (erreur absolue **+16,6 %**, gain −1,7 point),
    et le gain contre l'**uniforme MONTE** (2,6 → **4,6 %**). ⇒ **Décision du
    12/10 maintenue, et sur un argument plus solide qu'hier.**
12. ✅ **Un motif `bw-rho-hors-bornes` ? NON, et la question est close.**
    **475 → 452 → 404 → 383** (−19 % en trois nuits), **10,34 %** du parc.
13. ⓘ **Un champ de bilan de purge au registre ?** (question du 08/10.) Avec
    `lignes_effacees` et `tranches`, le §5 tiendrait en trois lignes — et il
    faudrait **nommer la requête** qui porte le `n_57014`.
14. ⓘ **Faut-il un motif Jira pour une panne de canal ?** (question du 30/09.)
    **Un motif pour `bw_character_avance` ?** — propre pour la 7e nuit.

**Ce que la surveillance regardera au prochain run :**

15. **Le total R2** : **9,942 Go, 58 Mo de marge.** `agrume/grille` reprend-il
    700 Mo, ou la nuit du 16/10 reste-t-elle isolée ? ⓘ Et regarder
    **`agrume/pi`** (1,465 Go, 3 285 objets, **+0,576 Go/mois**) : c'est le seul
    préfixe dont la pente soit nettement positive.
16. **Le coût par ligne de `regime`** : **13,12 ms.** Une **deuxième hausse**
    consécutive, et le motif `bw-regime-sensibilite` se pose. **C'est la mesure
    à regarder en premier.**
17. **Le 57014** : une **onzième** nuit à zéro, ou une nouvelle adresse ?
18. **Le coût par ligne rejouée** : **1 701,4 o**, deux nuits au même millième.
19. **Les incidents mémoire** : **2** pour la deuxième nuit. Le « score par
    régime » (2 638) reste-t-il sous les 2 800 ?
20. **Le swap** : recalé cette nuit. Tient-il, ou la divergence revient-elle ?
21. **La durée** : **5 001 s**, dans la bande. `glissant` est à 963,8 s.
22. **Les événements** : **33 882 lignes en base (+64 %)**. Effet d'une journée
    ventée, ou niveau nouveau ?
23. **τ et son échantillon** : **0,784 / 65**, les deux en recul ensemble.
24. **La position** : les six à 4 j, et `1333` à 1 j.
25. **ρ hors [0, 1]** : **383.** Quatrième baisse, ou reprise ?
26. **`mutations_memoire`** : une dixième nuit muette ?
27. **L'horaire** : **+1 h 56.** Dix matins de dérive sur seize.
