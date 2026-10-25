# Verdict de pente du 25/10/2026 — ⛔ **La purge a ÉCHOUÉ : des lignes RESTENT en base.** ⛔ **Et le contrôle de 07:30 s'est tu à tort — faux négatif du correctif du 07/10.** ✅ **Les cinq commentaires Jira sont partis, dont les deux que la coupure du pont avait bloqués hier.**

Trois faits, dans l'ordre d'importance. **(1)** La purge de
`model_score_zone` n'a pas abouti : la tranche thermique du 2026-10-17 est
restée en base, le journal le dit lui-même (« des lignes RESTENT »), et la
série de **17 nuits propres est rompue** — compteur KAN-5 **remis à 0 / 3**.
**(2)** Le contrôle de pente **s'est tu** sur cette nuit-là : son correctif du
07/10 accorde le silence dès qu'un bilan chiffré existe, sans regarder le
suffixe « des lignes RESTENT ». Le faux positif du 06/10 a été remplacé par un
**faux négatif**, démontré cette nuit pour la première fois. **(3)** Le jalon
mémoire fait un **record à 3 452 Mo**, et la durée remonte de **188 s** avec
une signature inversée : **95 % dans les étapes**.

✅ **Le rattrapage du 24/10 est fait** : les deux commentaires rédigés hier et
bloqués par la coupure du pont ont été postés ce matin, datés explicitement du
24/10, avant les commentaires du jour.

## 08:10–08:45 (Paris, CET) — routine Balise Watch, run COMPLET

**Étape 0 : faite en entier.**

- `git log --oneline --since=midnight` dans `balise-watch-server` **et** dans
  `surveillance balise` : **aucun commit aujourd'hui** dans les deux dépôts
  ⇒ aucun autre run n'a tourné ce matin. Dernier commit serveur : `4c1439f`
  (note du 23/10) — ⛔ **ce qui confirme le §12 du 24/10 : le miroir git du
  24/10 n'a jamais été déposé.**
- `claude/verdict-pente-25-10.md` **absent** du projet (`project_read` répond
  « No doc at… ») ⇒ cette note est une **création**, pas une fusion.
- `claude/verdict-pente-24-10.md` lu en entier — c'est lui qui portait la
  consigne de rattrapage.
- `notes-projet/README.md` relu : les quatre règles.

## 1. Le relevé de la nuit du 24→25/10

`lancement = timer` · `result = success` · `exec_status = 0` · `oom = 0`
Début 04:57:06, fin 06:24:51 (heure locale du VPS).

ⓘ **Changement d'heure cette nuit** (CEST → CET) : le départ paraît une heure
plus tôt à l'horloge, ce n'est **pas une dérive**. En UTC le run part à
**03:57:06 Z** contre 03:56:48 Z la veille — **18 s d'écart**. Le timer du
contrôle, lui, est en heure locale : 07:30:22 CET, suivant armé pour le
**26/10 à 07:30:29 CET**.

| | 23/10 | 24/10 | 25/10 | Δ nuit |
|---|---:|---:|---:|---:|
| `duree_s` | 5 300 | 5 064 | ⛔ **5 252** | ⛔ **+188** |
| `cpu_s` | 3 952,2 | 3 982,9 | **4 144,7** | **+161,8** |
| `marge_s` | 2 800 | 3 036 | **2 848** | −188 |
| marge / garde (8 100 s) | 34,57 % | 37,48 % | **35,16 %** | −2,32 pt |
| étapes (somme) | 2 938,5 | 2 910,0 | **3 089,3** | ⛔ **+179,3** |
| hors étapes | 2 361,5 | 2 154,0 | **2 162,7** | **+8,7** |
| `jalon_max_mo` | 3 210 | 3 411 | ⛔ **3 452** | ⛔ **+41 (RECORD)** |
| `mem_peak_mo` | 3 608,0 | 3 616,4 | **3 611,9** | −4,5 |
| `swap_peak_mo` | 2 180,7 | 2 541,0 | **2 491,2** | −49,8 |
| `swap_out_pages` | 2 573 036 | 2 737 964 | **2 573 946** | −164 018 |
| `n_57014` | 4 | 0 | ⛔ **3** | **+3** |
| `incidents` | 3 | 2 | **5** | +3 |
| `lignes_regime` | 134 729 | 137 769 | **138 279** | +510 |
| `lignes_score_zone` | 145 123 | 148 173 | **148 683** | +510 |
| `lignes_daily` | 68 433 | 68 608 | **68 009** | −599 |
| `lignes_glissant` | 10 394 | 10 404 | **10 404** | 0 |
| `balise_jours_rejeu` | 2 076 042 | 2 074 830 | **2 075 594** | +764 |

Les cinq `incidents` : trois de mémoire (rejeu d'archive 3 029, score par
régime 2 901, oubli de la fenêtre rejouée 3 452 Mo) et **deux de purge** —
c'est la nouveauté de la nuit (§3).

Répartition par étape : `glissant` 969,2 → **993,0** (+23,8) · `regime`
1 572,7 → **1 685,7** (**+113,0**) · `stabilite` 292,6 → **328,8** (+36,2) ·
`rejeu` 75,5 → **81,8** (+6,3).

### Les deux rapports qui valent mieux que les valeurs brutes

**Coût par ligne rejouée** (`jalon_max_mo × 1048576 / balise_jours_rejeu`) :

```
16/10 1 701,4 o · 17/10 1 701,4 o · 18/10 1 706,1 o · 19/10 1 702,0 o
20/10 1 608,0 o · 21/10 1 726,1 o · 22/10 1 722,2 o · 23/10 1 621,3 o
24/10 1 723,8 o · 25/10 1 743,9 o
```

⇒ ⛔ **1 743,9 o est le point le plus haut de la série** (+20,1 o en une nuit),
et la bande va désormais de **1 608 à 1 744 o**. L'élargissement d'amplitude
signalé depuis le 21/10 tient une **cinquième** nuit, et c'est son **bord
supérieur** qui bouge. ⚠️ Sur dix nuits il n'y a toujours **aucune pente nette**
dans un sens ou dans l'autre : la série rebondit. La « bande 1 686–1 717 » du
07/10 est morte depuis longtemps.

**Coût par ligne de `regime`** (`etapes_s.regime / lignes_regime × 1000`) :

```
19/10 12,37 ms · 20/10 13,13 ms · 21/10 12,14 ms · 22/10 12,59 ms
23/10 11,97 ms · 24/10 11,42 ms · 25/10 12,19 ms
```

⇒ ⚠️ **+6,7 % en une nuit, après deux baisses consécutives.** Le volume
n'explique pas la hausse : `lignes_regime` fait **+0,4 %** quand l'étape fait
**+7,2 %**. ⇒ **critère `bw-regime-sensibilite` : 1 / 2** (il demande deux
hausses consécutives). **Rien posé, aucune question reposée à Yann.** Si la
hausse se répète demain, le critère sera rempli et la question sera posée.

**Calcul ou attente ?** La durée fait **+188 s** pendant que `cpu_s` fait
**+161,8 s** ⇒ **86 % de la seconde d'horloge en plus est de la seconde de
CPU** : c'est du **calcul**. Même diagnostic que le 24/10, inverse du 23/10
(`cpu_s` −219,5 pendant que la durée montait : de l'attente pure).

## 2. ⛔ LE FAIT DU JOUR : la purge n'a pas abouti — des lignes RESTENT

Le bloc purge, ligne par ligne :

```
06:23:57  ⚠️ purge model_verif_daily : HTTP 500 — {"code":"57014", …}
06:24:19  ⚠️ purge model_score_zone (?as_of=eq.2026-10-17&regime=eq.thermal)
          : HTTP 500 — 57014 — rejouée dans 5 s
06:24:32  ⚠️ purge model_score_zone (?as_of=eq.2026-10-17&regime=eq.thermal)
          : HTTP 500 — 57014
06:24:36  → purge model_score_zone : 108 479 ligne(s) effacée(s) en
          8 tranche(s), DES LIGNES RESTENT (plus vieille journée : 2026-10-17)
06:24:36  ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête
```

Lecture, selon les règles établies depuis le 28/09 :

| test | verdict |
|---|---|
| tranche en échec | ✔ `?as_of=eq.2026-10-17&regime=eq.thermal` — rejouée **une** fois, refusée **deux** fois ⇒ **un échec**, pas un rejeu rattrapé |
| sonde en défaut | ✘ pas de « plus vieille journée illisible » : la sonde a bien lu la base |
| « des lignes RESTENT » | ⛔ ✔ **et c'est LA seule phrase qui permet de conclure qu'il reste quelque chose** — elle est là, avec la journée nommée |

⇒ **La tranche thermique du 2026-10-17 n'a PAS été effacée.** Ce n'est pas
déduit d'un 57014 isolé (l'erreur du 28/09) : c'est écrit par la sonde, qui a
lu la base **après** la purge.

⇒ ⛔ **Compteur de fermeture KAN-5 : 17 / 3 → REMIS À 0 / 3.** La série de
17 nuits propres s'arrête au 24/10. La demande de fermeture posée hier
(point 9 de la liste du 24/10) est **sans objet**.

### 2.1 ⛔ Ce qui ne s'était jamais vu : un 57014 sur `model_verif_daily`

Toutes les expirations de purge suivies depuis le 10/09 portaient sur
`model_score_zone`. Celle de 06:23:57 porte sur **`model_verif_daily`**. Elle
n'est suivie d'**aucune ligne de rejeu** et d'**aucun bilan** : rien au journal
ne dit combien de lignes cette purge-là a effacées, ni si elle a abouti.
⇒ **Le statut de la purge de `model_verif_daily` cette nuit est INCONNU.**

⚠️ Tout l'outillage de lecture du bloc purge (`bilan_purge`, les deux
expressions régulières) est écrit pour `model_score_zone` **et pour elle
seule** : il ne sait pas lire un bilan de `model_verif_daily`, parce qu'il n'en
existe pas au journal.

### 2.2 Le volume effacé — et pourquoi il compte CETTE FOIS

```
24/10   138 331 lignes en 8 tranches, rien ne reste
25/10   108 479 lignes en 8 tranches, des lignes RESTENT      (−29 852)
```

Règle habituelle : le volume suit la journée purgée (≈ 125 000 à 138 000) et
**ne signifie rien**. ⚠️ Cette nuit l'écart a une **cause nommée au journal**
— la tranche thermique du 2026-10-17 n'est pas passée — donc il n'est pas du
bruit. ⓘ Je **ne prétends pas** pour autant que la tranche manquante vaut
exactement 29 852 lignes : seul un `select as_of, count(*)` joué à la main le
dirait, et je n'ai joué aucun SQL.

### 2.3 `n_57014 = 3` — et cette fois les trois sont DANS la purge

Recherche élargie à **toutes les unités sur 24 h** : exactement **3**
occurrences de « 57014 », et ce sont les trois lignes du §2. ⇒ **L'inverse
exact du 23/10**, où les 4 occurrences venaient d'**ailleurs**
(`model_verif_event [0-999]`, `rpc/bw_character_avance`) et où la purge, elle,
était propre.

✅ Ni `model_verif_event` ni `rpc/bw_character_avance` n'ont bronché cette nuit
(**69 053 lignes** écrites, **479 356 accumulateurs avancés sur 479 356**) :
**deuxième nuit sans reproduction** du motif nommé le 23/10. ⇒ Toujours
**aucun motif Jira créé** pour eux — et l'argument pour attendre se renforce.

```
13/10 0 · 14/10 1 · 15/10 0 · 16/10 1 · 17/10 0 · 18/10 0 · 19/10 0
20/10 0 · 21/10 0 · 22/10 1 · 23/10 4 · 24/10 0 · 25/10 3
```

⛔ **Rappel, qui vient de resservir** : une nuit à `n_57014 = 0` n'est pas un
correctif. Il y en avait eu trois d'affilée (03, 04, 05/10) avant le retour du
06/10 — et **dix-sept** avant celui de cette nuit.

## 3. ⛔ Le contrôle de pente s'est TU, et il aurait dû parler

Le contrôle de **07:30:22 CET** n'a produit qu'une ligne :

```
2026-10-25T06:30:22Z rien à dire : pente plate ou négative, ou échéance hors horizon
```

Verbeux, relancé à la main en lecture seule :

```
ⓘ 87 relevé(s), 66 comparable(s) ; durée : 10 points, pente -69 s/nuit ;
  mémoire : 10 points, pente -12 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
ⓘ rien à dire : pente plate/négative, ou échéance hors horizon
```

**Aucun constat de purge.** La cause, vérifiée dans le code (lecture seule) :

```python
# controle_quotidien.py:253-258
bilan = bilan_purge(journal)
if tranches_ko and bilan and bilan.get("lignes") is not None:
    return out        # « rejouée ET rattrapée : le canal se TAIT »

# controle_quotidien.py:295-297
_RE_BILAN = re.compile(
    r"→ purge model_score_zone\s*:\s*(\?|\d+)\s*ligne\(s\) effacée\(s\)"
    r"\s*en\s*(\d+)\s*tranche\(s\)")
_RE_AVERTI = re.compile(r"⚠️ purge model_score_zone")
```

L'expression régulière **n'est pas ancrée en fin de ligne** : elle reconnaît le
bilan de cette nuit (108 479 lignes, 8 tranches) et **ignore le suffixe**
`, des lignes RESTENT (plus vieille journée : 2026-10-17)`. `bilan["lignes"]`
vaut donc 108 479, la condition de la ligne 254 est remplie, et le contrôle
conclut « rejouée puis rattrapée » — **sur une nuit où la base a gardé ses
lignes.**

⚠️ **C'est l'effet de bord du correctif du 07/10.** Ce correctif a supprimé un
**faux positif réel** (le 06/10, KAN-5 avait reçu « purge en échec » alors que
124 678 lignes avaient bien été effacées). Il introduit un **faux négatif**,
démontré cette nuit **pour la première fois** : le silence est accordé dès
qu'un bilan chiffré existe, même quand ce bilan dit lui-même que des lignes
restent.

### 3.1 Correctif proposé — ⛔ NON déployé, NON écrit

C'est une **écriture dans le code**, donc c'est Yann qui tranche.

1. **Faire dépendre le silence de l'absence de « des lignes RESTENT »** dans la
   ligne de bilan : `bilan_purge` rend un troisième champ (par exemple
   `restent`), et la condition de la ligne 254 devient « bilan chiffré **ET**
   rien ne reste ». Deux lignes de code, une entrée `BUGS.md`.
2. **Accessoirement** : `_RE_AVERTI` ne reconnaît que
   `⚠️ purge model_score_zone`. Un avertissement sur **une autre table** ne
   déplace donc pas le repère du « dernier averti ». Cette nuit c'est **sans
   effet** (l'avertissement `model_verif_daily` précède le bilan), mais
   l'inverse donnerait un faux silence de plus.

⚠️ **Tant que ce n'est pas corrigé**, la nuit où la purge laisse des lignes en
base est une nuit où Jira n'apprend **rien** du contrôle. C'est exactement ce
qui s'est passé ce matin : les commentaires sont partis **par le canal
délibéré, à la main**.

ⓘ **Ce n'est PAS une raison de retirer le correctif du 07/10** : sans lui,
KAN-5 recevrait « purge en échec » toutes les nuits où une tranche est rejouée
puis rattrapée — ce qui est le cas normal. Le correctif est bon ; il lui manque
un test.

## 4. ⛔ Mémoire — record du jalon, et le palier « score par régime » repasse au-dessus en une nuit

```
rejeu d'archive         3 012 → 3 029 Mo   (+17)    ⛔ au-dessus du seuil
score par régime        2 781 → 2 901 Mo   (+120)   ⛔ REPASSE au-dessus
oubli fenêtre rejouée   3 411 → 3 452 Mo   (+41)    ⛔ jalon max — RECORD
```

⛔ **3 452 Mo est un RECORD de la série.** Le maximum était 3 424 Mo (21/10) ;
il est dépassé de **28 Mo**. Le jalon est **+652 Mo au-dessus** du seuil de
2 800 Mo — **le plus loin qu'il ait jamais été**.

✅ **Le refus posé hier est validé en vingt-quatre heures.** La note du 24/10
refusait de lire les 2 781 Mo de « score par régime » comme un mouvement de
fond, liste des dix-sept passages sous le seuil en main. La nuit suivante il
est à **2 901 Mo**, de nouveau au-dessus. Le nombre d'`incidents` de mémoire
remonte de 2 à 3 pour cette seule raison.

### 4.1 ⚠️ Un record n'est pas une pente — huit nuits de jalon

```
18/10 3 393 · 19/10 3 381 · 20/10 3 193 · 21/10 3 424
22/10 3 412 · 23/10 3 210 · 24/10 3 411 · 25/10 3 452
```

⇒ Trois montées, deux descentes, et un plafond qui ne redescend jamais sous
3 193 Mo. Le record du jour est un **fait** ; le présenter comme « une hausse
de fond » serait l'erreur déjà commise les 05/10 (à la hausse), 06/10 (à la
baisse) et 21/10. **« Une nuit ne fait pas une pente »** — à revérifier demain,
et c'est tout ce que ce point autorise.

### 4.2 L'estimateur de pente, cinquième matin contradictoire

| matin | pente affichée | échéance annoncée |
|---|---:|---|
| 21/10 | −22 Mo/nuit | 18/11 |
| 22/10 | −12 Mo/nuit | 12/12 |
| 23/10 | −188 Mo/nuit | **25/10** ⇒ démenti dès le 24/10 (+201 Mo) |
| 24/10 | −12 Mo/nuit | ≈ 14/12 |
| 25/10 | **−12 Mo/nuit** | **≈ 18/12** (54 nuits depuis 3 452 Mo) |

⇒ « Mémoire : pente −12 Mo/nuit » **le matin d'un record de +41 Mo**. C'est le
**25ᵉ centile des différences** : il ignore par construction les deux plus
grosses variations, donc **il ne peut pas voir un record**. Conclusion posée le
23/10, répétée le 24/10, **confirmée une troisième fois** : cet estimateur
**n'est pas utilisable en prévision** sur cette série. Le chiffre du jour est
donné pour ce qu'il vaut : rien. L'échéance étant hors horizon (30 j), le
contrôle se tait — et sur ce point précis **il a raison de se taire**.

### 4.3 ⚠️ Deux bornes de lecture, pour ne pas surjouer

`mem_peak` à **3 611,9 Mo n'est PAS un record** (3 626,8 Mo le 21/10), et le
swap au pic à **2 491,2 Mo n'en est pas un** non plus (2 595,3 Mo le 12/10,
2 592,1 Mo le 04/10) — il **baisse** de 49,8 Mo, et `swap_out_pages` revient à
son niveau du 23/10 (−164 018 pages). **Le record de cette nuit porte sur le
JALON seul.**

### 4.4 Le remède, inchangé

La **ligne en tuple** (§2.6 de l'enquête du 10/09) : ≈ **−1 030 o/ligne**, soit
≈ **−2 039 Mo** sur les 2 075 594 balise-jours rejoués. ⛔ **Rien de déployé
côté mémoire depuis `af25efb` (21/09) — 34ᵉ jour.** ⚠️ L'élagage de `units`
avait rendu −124 Mo au lieu de −1 500 : les gains sont dans la **structure**.
La mesure `tuple` vs `namedtuple` à la sonde reste le préalable.

## 5. ⛔ Durée — +188 s, et la signature s'inverse une fois de plus

```
            étapes     hors étapes   total
23/10      2 938,5       2 361,5     5 300
24/10      2 910,0       2 154,0     5 064
25/10      3 089,3       2 162,7     5 252
Δ nuit       +179,3         +8,7      +188
```

⇒ ⛔ **95 % de la hausse est DANS les étapes**, et **60 % dans `regime` seul**
(+113,0 s). C'est l'exact contraire du 07/10 (85 % hors étapes) et du 23/10
(bloc hors étapes en record). **La hausse de cette nuit est localisée, et elle
est localisée dans une étape INSTRUMENTÉE.** Il n'y a donc, pour cette nuit,
rien à chercher dans le bloc non instrumenté.

Classement du bloc hors étapes sur les **66 relevés comparables** :

```
1.  23/10   2 361,5 s
2.  18/09   2 254,2 s
3.  01/10   2 219,7 s
4.  25/10   2 162,7 s   ← cette nuit
5.  24/10   2 154,0 s
médiane     1 960,4 s
```

ⓘ Le bloc reste **4ᵉ sur 66** et **+202,3 s au-dessus de la médiane**, et il
n'est toujours **pas instrumenté** (publication, Murphy, événements, pression,
duels, purge). La demande de **jalons de temps dans `run.sh`** reste ouverte et
reste classée **« utile sans urgence »** : deux nuits de suite, ce n'est pas
lui qui bouge. C'est une **écriture** : non faite.

⚠️ **Bornes de lecture** : 5 252 s n'est ni un record ni un plancher — le
maximum des 66 comparables reste **5 318 s (10/10)**. La marge, en revanche,
retombe à **35,16 %**, à 0,6 point de son plancher de série (34,57 % le 23/10).

⛔ **Remontée du chien de garde : NON LANCÉE et NON PROPOSÉE.**
`controle_quotidien.proposition()` ne se déclenche pas (pente négative,
échéance hors horizon). La forme reste connue : écrire la mesure dans l'en-tête
de `10-timeout-s3.conf` (135 → 140/145 min), déployer, vérifier par
`systemctl show`. **C'est Yann qui décide et qui lance.** Avec 2 848 s de
réserve sur 8 100, il n'y a aucune urgence mécanique.

⚠️ **Une nuit ne fait pas une pente, deux non plus** : 23/10 **+58**, 24/10
**−236**, 25/10 **+188**. Solde des trois nuits : **+10 s**.

## 6. ⛔ Hors mission mais à savoir : la journée AROME/R2 est PERDUE

Le **second** push du matin (08:00:18 CET) ne vient pas de la notation :

```
❌ les tuiles en ligne portent le run 2026-10-24T15:00Z, qui n'est pas un run
   admis du 2026-10-25 (admis : 00 Z, 03 Z). ⛔ CETTE JOURNÉE EST PERDUE POUR
   AROME/R2 : les tuiles sont réécrites en place toutes les 3 h, il n'existe
   aucune archive des runs passés. Regarder l'Action `arome-wind` de ce matin.
   → run arome en ÉCHEC (code 1, 2s) — 1 consécutif(s)
```

⚠️ **Hypothèse, non vérifiée** : les tuiles sont restées sur le run du 24/10 à
15:00 Z, et cette nuit est **celle du changement d'heure**. Une Action
`arome-wind` programmée en heure locale aurait glissé d'une heure. ⓘ Je n'ai
**pas** examiné l'Action : c'est hors mission et hors VPS.

⇒ **Conséquence pour la notation** : `arome_r2` est l'un des modèles des duels
suivis (n = 17 135 cette nuit). La journée du 25/10 lui manquera, et ça se
verra dans le relevé de **demain**. Rien à faire côté notation, mais à savoir
avant de lire le relevé du 26/10.

## 7. ⛔ R2 — le total remonte, et le mécanisme du §7.1 du 24/10 se vérifie une sixième fois

```
25/10   10,363 Go   (103,6 %)   ⛔ DÉPASSÉ de 363 Mo   6 980 objets
24/10   10,270 Go   (102,7 %)   ⛔ DÉPASSÉ de 270 Mo   6 918 objets
```

**+93 Mo et +62 objets en une nuit.** Le recul de −49 Mo du 24/10 est effacé et
dépassé.

```
            agrume/pi            arome/rafale      arome/sol
24/10   1,608 Go  3 621 obj      0,875 Go  63 obj  0,612 Go  63 obj
25/10   1,628 Go  3 669 obj      0,902 Go  63 obj  0,631 Go  63 obj
Δ         +20 Mo     +48 obj       +27 Mo             +19 Mo
```

⇒ ⛔ **`agrume/pi` fait +48 objets exactement pour la DOUZIÈME nuit
consécutive**, sans un seul recul. Et les deux préfixes à **fenêtre
glissante**, qui avaient rendu −72 Mo hier (et inversé le signe du total), en
reprennent **+46** cette nuit. ⇒ **Sixième jour de vérification du mécanisme**
du §7.1 du 24/10 : *le total du compte n'est pas un indicateur de
l'accumulation.* Hier il baissait sans que rien n'aille mieux ; aujourd'hui il
monte de 93 Mo dont **la moitié** n'est que le retour de balancier des fenêtres
glissantes.

Pente affichée du total : **+0,077 Go/mois** (contre +0,067 hier), alors que
`agrume/pi` **seul** fait **+0,579 Go/mois**. ⛔ Le point 6 de la liste
(borner à zéro les pentes négatives dans `audit_r2.py`) reste **entier** : une
**écriture**, non faite.

### 7.1 ⚠️ `agrume/grille` BOUGE — la série de onze nuits identiques s'arrête

```
24/10   5,323 Go   766 objets   766 / 766 réclamées
25/10   5,366 Go   772 objets   772 / 772 réclamées     (+43 Mo, +6 objets)
```

⚠️ Après **onze nuits strictement inchangé**, `agrume/grille` gagne 6 objets et
43 Mo. ✅ **Mais il reste intégralement réclamé** (772 / 772) : ces 6 objets
sont des produits que l'index revendique, **pas des orphelins**. ⇒ `agrume/pi`
reste le coupable du dossier R2 ; `agrume/grille` reste hors de cause. ⓘ Pente
affichée **−0,004 Go/mois** : à revérifier demain pour savoir si c'est une
reprise de production ou un à-coup.

### 7.2 ⛔ L'écart non réclamé grossit au rythme exact de l'accumulation

```
│ agrume/pi/grille/                        19 présentes /   19 réclamées   ✓
│ agrume/pi/rafraichissement/              28 présentes /   28 réclamées   ✓
```

47 objets couverts sur **3 669** ⇒ **3 622 objets non réclamés par aucun
index** (3 574 hier). **+48 par nuit, exactement le rythme d'accumulation.**
ⓘ Ce n'est pas la preuve qu'ils sont orphelins ; c'est la constatation qu'on
n'en sait rien. **L'inventaire reste le geste à faire avant toute rétention.**

### 7.3 ⓘ `bw-garde-fou-r2.service` est `failed` pour la 10ᵉ fois — toujours PAS une panne

```
⚠️  palier gratuit DÉPASSÉ : 10.36 Go sur 10 Go — R2 facture déjà
   run garde-fou-r2 en ÉCHEC (code 1, 5s) — 10 consécutif(s)
```

`systemctl show` : `NRestarts=0`, `ExecMainStatus=1`, `Result=exit-code`. La
démonstration du 21/10 tient : `code 1` veut dire « j'ai quelque chose à
dire ». ⇒ **rien à corriger.** Et **deux cris partent pour le même fait**
(avertissement R2 + alerte générique « service en échec »).

## 8. ✅ Position — 17 balises, liste des confirmées identique, donc pas de cri : 6ᵉ vérification du « à front »

```
⛔ position : 17 balise(s) divergent du gel (10 j lus), dont 4 CONFIRMÉE(S)
   ⛔ pioupiou:2171          38 915 m · 10 j · nœud + profil CHANGENT
   ⛔ pioupiou:84             9 748 m · 10 j · nœud + profil CHANGENT
   ⛔ pioupiou:367            6 764 m · 10 j · nœud + profil CHANGENT
   ⛔ infoclimat:STATIC0491   1 159 m · 10 j · nœud 0,01 CHANGE
```

**Les quatre sont exactement celles du 23 et du 24/10, aux mètres près.** Le
journal ne porte **aucune** ligne « cri déposé pour envoi » et **aucun push de
position** : ✅ **sixième vérification en six jours** du mécanisme « à front,
pas à état ».
ⓘ La question du 01/10 reste ouverte : faut-il qu'il recrie à état constant ?
Avec **quatre** balises confirmées muettes depuis trois matins, elle gagne
encore en poids.

⚠️ **`pioupiou:1378` reste bloquée à 9 j pour la TROISIÈME journée**, écart
inchangé à **340 941 m**. Elle re-clignote : elle n'a de nouveau pas divergé
une des dix journées lues, donc **le compteur de jours ne la confirmera jamais
seul**. 341 km n'est pas un décalage de coordonnées plausible : candidate nette
« AUTRE balise », à trancher à la main.

ⓘ **Le total passe de 16 à 17** : une **nouvelle venue**, `mf:05170001`
(330 m · 1 j · nœud 0,01 CHANGE) — **la première du réseau `mf`** dans cette
liste, qui ne portait jusqu'ici que du `pioupiou` et de l'`infoclimat`. Rien à
en conclure à 1 j. Les onze balises à 3 j hier (327, 1749, 1568, 1558, 70,
1724, 1715, 1435, 175, 2058, 633) sont **toutes à 4 j** : la fenêtre se
remplit, aucune n'a disparu.

## 9. Les trois correctifs du 07/10 — verdict correctif par correctif

| correctif | verdict du 25/10 |
|---|---|
| **1. webhook `--ipv4`** | ✅ **tient.** Deux `ⓘ push parti (webhook, HTTP 200)` — 06:24:58 (garde-fou R2) et 08:00:18 (échec AROME/R2, §6) — chacun suivi d'un mail `smtpstatus=250`. **Aucun HTTP 429 ntfy** (recherche dédiée : 0 ; les quatre 429 du journal viennent de `run-ingest-pi.sh`, quota de l'API aromepi, sans rapport). Volume du jour : **2 pushes**, dans la fourchette normale de 2 à 7 ⇒ aucun runner qui s'emballe. |
| **2. garde-fou des deux jetons** | ✅ **tient** mécaniquement : le contrôle de 07:30:22 s'est tu, aucun jeton posé, aucun doublon possible. ⛔ **Mais son silence était cette fois INJUSTIFIÉ** (§3) — ce n'est pas le garde-fou des jetons qui est en cause, c'est `bilan_purge`. `controle_quotidien.sh` conserve son `$ETAT` — **non touché**. |
| **3. rejeu de purge ≠ échec** | ⛔ **IL A PARLÉ TROP FORT ET SE TAIT TROP** : il a bien évité le faux positif, mais il a produit un **faux négatif** sur une purge qui n'a pas abouti (§3). Première mise en défaut depuis son déploiement. Correctif proposé au §3.1, **non déployé**. |

## 10. Les autres témoins

- ⚠️ **Témoins du mélange — le point le plus BAS des neuf, et il est net.** Sur
  **7 378** balise-jours×échéance : **6,1068 km/h** contre **5,8709** pour le
  meilleur membre a priori ⇒ **gain −4,0 %**, devant dans **44,1 %** des cas.
  Contre la moyenne **uniforme** (n = 1 095) : 5,7401 vs 6,1005 ⇒ **gain
  +5,9 %**, qui tient. Série du gain a priori : −0,6 % (07/10) · +2,5 · +1,7 ·
  −0,3 · +0,9 · −0,9 · +0,1 · +0,8 · **−4,0 % (25/10)**.
  ⚠️ **À pondérer** : l'erreur absolue **retombe de 7,83 à 6,11 km/h (−22 %)**
  — journée beaucoup plus calme, et le mélange perd justement quand il y a peu
  à gagner. ⇒ **Pas de motif Jira demandé** : deux points négatifs sur neuf,
  non consécutifs, et le gain contre l'uniforme tient. **Mais c'est le plus
  mauvais des neuf sur les deux mesures : à revérifier demain en priorité.**
- ⚠️ **Témoin du corrigé : 27,6 pt** (contre 27,8 hier), sur 9 070 balise-jours
  — vrai antécédent **+17,3 %**, autre balise **−10,3 %**. Série de la part
  site : 24,1 (18/10) → 22,9 → 18,0 → 16,6 → 23,3 → 20,4 → 27,8 → **27,6 pt**.
  Version FIN, part secteur+heure : 14,3 → 12,7 → 8,5 → 9,8 → 10,5 → 12,6 →
  12,2 → **13,3 pt** (6 622 balise-jours). ⓘ **Ça oscille**, comme conclu les
  22, 23 et 24/10. **Rien à surveiller.**
- ⚠️ **Écarts du recalcul indépendant : 7** (4 le 24/10, 7 le 23/10, 4 le
  22/10, 3 le 21/10). Série : 3 · 5 · 4 · 7 · 4 · **7** ⇒ **elle va de 3 à 7 et
  revient** ; rien à en tirer. ⓘ **Une nuance neuve** : **six des sept**
  portent `0 h appariées ici (< 6)` et non `1 h` comme toutes les précédentes.
  Même signature de fond (« la base porte une ligne »), récurrente, antérieure
  — mais à regarder si le `0 h` se répète.
- ⓘ **Écart des deux mélanges** : `mse_comb` 17,841 contre `mse_comb_vec`
  17,841 (**+0,00 %**) — les deux chemins restent confondus.
- **Duels** : `arome_r2 ↔ meteofrance_arome_france_hd (+6 h)`, n = **17 135**,
  moyenne +0,084, médiane **+0,092**, IC95 [+0,069 ; +0,112] → `b_better`,
  inchangé. ⚠️ Et c'est `arome_r2` qui perdra la journée du 25/10 (§6). Cumul
  toujours **tronqué par la rétention 30 j** (dette connue, `duel.DUEL_DAYS`).
- **Murphy** : 65 906 triplets, **63 985** décomposés, 266 balises dehors.
- **Volumes de la nuit** : 68 009 agrégats quotidiens (−599), **69 053**
  `model_verif_event` (contre 106 861 — journée calme : 3 688 balises observées
  contre 3 727, 1 414 cases fines contre 1 425), **479 356** accumulateurs
  avancés sur 479 356, `model_events.json` 9 412 Ko, `model_scores.json`
  130 265 Ko. **782 776 lignes écrites en base** (866 024 la veille).
- **Second canal du téléphone (Discord)** : ⛔ **`BW_DISCORD_WEBHOOK_URL`
  toujours ABSENTE** du `.env` (recherche sur le **nom seul**, `grep -c` = 0,
  aucune valeur lue). Aucun `ⓘ push Discord parti` au journal — cohérent.
  `~/installer-webhook-discord.sh` attend toujours : **44ᵉ jour**.
- **`mutations_memoire`** : ⓘ **aucune ligne au journal cette nuit non plus** —
  rien conclu : la dette de 3 mutations non vues (2, 5, 13) est reportée telle
  quelle.
- ⓘ `bw-model-oracle.service` : **non examiné ce matin, hors mission.** Je ne
  dis pas qu'il va mieux, je dis que je n'ai pas regardé.

## 11. ✅ Les tickets — cinq commentaires postés, aucun ticket touché

**États revérifiés par GET AVANT toute écriture :**

```
KAN-3 | Terminé | done | updated 2026-10-23T13:37:38+0200 | 30 comm.
KAN-4 | À faire | new  | updated 2026-10-23T13:37:39+0200 | 43 comm.
KAN-5 | À faire | new  | updated 2026-10-23T13:37:40+0200 | 26 comm.
```

⇒ ⛔ **Les trois `updated` étaient encore ceux du run du 23/10** : cela
**confirme** que les deux commentaires du 24/10 ne sont jamais partis, et
qu'aucun tiers n'a écrit depuis. Pas de collision.

**Vérifié par GET APRÈS écriture :**

```
KAN-3 | Terminé | done | updated 2026-10-25T08:30:04+0100 | 31 comm.  (+1)
KAN-4 | À faire | new  | updated 2026-10-25T08:30:03+0100 | 45 comm.  (+2)
KAN-5 | À faire | new  | updated 2026-10-25T08:28:54+0100 | 28 comm.  (+2)
```

| ticket | ce qui a été posté | état |
|---|---|---|
| **KAN-5** | **(a) rattrapage du 24/10**, daté explicitement, reconstruit depuis la note du 24/10 (§4, §3.1, §11) : purge propre 138 331 lignes, 17ᵉ nuit, `n_57014 = 0` partout avec les 4 occurrences du 23/10 datées, les trois constats du 23/10 qui tombent. **(b) verdict du 25/10** : le bloc purge ligne par ligne, « des lignes RESTENT », le compteur **17/3 → 0/3**, le 57014 inédit sur `model_verif_daily`, le défaut de lecture du contrôle avec le code cité, le correctif proposé non déployé, trois questions. | ✅ **posté ×2** — reste **ouvert** |
| **KAN-4** | **(a) rattrapage du 24/10** : le script `/tmp/bw-comm-kan4.sh` écrit hier était complet et correct (relu avant exécution, `bw_jira_commenter`, aucune transition) — joué tel quel. **(b) verdict du 25/10** : jalon **record 3 452 Mo**, « score par régime » qui repasse au-dessus en une nuit (refus d'hier validé), coût par ligne rejouée au **plus haut** des dix nuits, cinquième échéance contradictoire, trois conditions de fermeture (muet ✔, plafond ✘ **+652 Mo**, swap ✘ 2 491,2 Mo), les deux bornes de lecture. | ✅ **posté ×2** — reste **ouvert** |
| **KAN-3** | **Commenté** (canal délibéré) parce que **la durée AUGMENTE** : +188 s, marge 35,16 %, répartition par étape, **95 % dans les étapes** et 60 % dans `regime`, découplage temps/volume, le rappel du 25ᵉ centile et des hausses qu'il n'a pas vues, la forme de la remontée du garde **proposée sans être lancée**, et le solde +10 s sur trois nuits. ⛔ **Non rouvert, non transité** : reste « Terminé ». La réouverture est à Yann. | ✅ **posté ×1** — reste **Terminé** |
| `bw-r2-palier` | ⛔ **non créé.** Décision de Yann. | — |
| motifs `model_verif_event` / `bw_character_avance` | ⛔ **aucun motif créé** — deuxième nuit sans reproduction. | — |
| `bw-regime-sensibilite` | ⛔ **non posé**, critère **1 / 2** (+6,7 %, une seule hausse). Aucune question reposée. | — |
| motif pour la purge | ⛔ **aucun motif neuf** : le motif existe déjà, c'est **KAN-5**, et il est ouvert. | — |

ⓘ **Pourquoi le canal délibéré cinq fois et `bw_jira_signaler` zéro fois** : le
contrôle s'est tu ce matin, donc le jeton du jour était libre — mais
`bw_jira_signaler` aurait créé un **ticket neuf** sur un motif « Terminé »
(KAN-3) et n'aurait pas permis deux commentaires datés différemment sur le même
ticket. `bw_jira_commenter` prend une **clé**, ne cherche rien, ne crée rien,
ne touche pas au jeton. C'est le choix assumé de l'arbitrage du 07/10.

## 12. ⓘ Horaire de la routine — ✅ à l'heure, deuxième matin de suite

Programmée pour **07:09:05 UTC**, tirée à **≈ 07:10:1x UTC** : **≈ +1 min**.

```
15/10 +7 h 37 · 16/10 +4 h 03 · 17/10 +1 h 56 · 18/10 +1 h 39 · 19/10 +7 h 43
20/10 +3 h 41 · 21/10 +8 h 50 · 22/10 +4 h 23 · 23/10 +4 h 21 · 24/10 +0 h 02
25/10 +0 h 01
```

✅ **Deux matins nets d'affilée, après dix de dérive.** ⚠️ Deux ne font pas une
correction — à revérifier, mais c'est la meilleure paire de la série.
ⓘ Le VPS est à l'heure lui aussi : notation à 04:57:06 CET (= 03:57:06 Z,
18 s après l'instant UTC de la veille), contrôle à 07:30:22 CET, **timer
suivant armé pour le 26/10 à 07:30:29 CET**.

## 13. Décisions en attente de Yann — la liste à jour

0. ✅ **Fait** : les deux commentaires du 24/10 sont postés, le miroir git de
   la note du 25/10 est déposé et commité. ⛔ **Reste en souffrance** : la note
   du **24/10 n'a pas de miroir git** (le run d'hier est tombé avant). Je ne
   l'ai pas fabriqué après coup — dis-moi si tu le veux, je recopierai le
   document projet du 24/10 dans `notes-projet/` et je le commiterai en le
   datant honnêtement.
1. ⛔ **NOUVEAU ET IMPORTANT : le défaut de lecture de `bilan_purge`** (§3.1).
   Deux lignes de code, une entrée `BUGS.md`. C'est une **écriture** : non
   faite. **Sans elle, une purge qui laisse des lignes en base est muette côté
   Jira.**
2. ⛔ **`diagnostic_base_sous_tension_2026-09-29.sql`** — **27ᵉ jour** sans
   être joué. ⬆️ **Son urgence REMONTE d'un cran et dépasse celle du 23/10** :
   il a été écrit pour ce cas exact, et **le cas vient de se produire** (des
   lignes restent en base). Lecture seule, 9 blocs, SQL Editor ; les correctifs
   candidats (ANALYZE / VACUUM / autovacuum par table) y sont en commentaire.
3. ⓘ **Un `select as_of, count(*) from model_score_zone group by as_of order by
   as_of limit 5`** dirait ce qui reste réellement du 2026-10-17. **Aucun SQL
   joué sans ton accord.**
4. ⛔ **R2 : rétention sur `agrume/pi`** — **+48 objets chaque nuit, douze
   nuits d'affilée, sans un seul recul**. ⚠️ Et ne pas se laisser tromper par
   le total : il a baissé hier et remonté de 93 Mo aujourd'hui sans que
   l'accumulation change d'un objet (§7).
5. ⛔ **Inventaire des 3 622 objets de `agrume/pi` que l'index ne réclame pas**
   (sur 3 669). À faire **avant** toute rétention.
6. ⛔ **Mémoire : la ligne en tuple** (≈ −1 030 o/ligne, ≈ −2 039 Mo). **34ᵉ
   jour sans rien de déployé** depuis `af25efb`. Porte de sortie de KAN-4,
   d'autant que le jalon vient de faire un record.
7. ⛔ **Pente d'`audit_r2.py`** : borner à zéro les pentes négatives des
   préfixes à fenêtre glissante (§7). Une ligne, mais c'est une **écriture**.
8. ⛔ **Jalons de temps dans le bloc hors étapes de `run.sh`** — ⬇️ reste
   « utile sans urgence » : deux nuits de suite la hausse est **dans** les
   étapes. Toujours 4ᵉ sur 66 et non instrumenté.
9. ⛔ **Motif `bw-r2-palier`** — non créé, ton accord requis.
10. ⛔ **Les 4 cas de position** (§8) : trancher, puis `position_suspecte` +
    `position_note` par `.sql`. ⚠️ Et **`pioupiou:1378`** : 341 km, bloquée à
    9 j **trois jours de suite** parce qu'elle clignote — elle ne se confirmera
    jamais seule.
11. ⓘ **Fermeture de KAN-5** : **sans objet**, le compteur est retombé à 0/3.
12. ⓘ **Réouverture de KAN-3** ? La durée monte de 188 s mais le solde de trois
    nuits est de +10 s. Mon avis : **attendre une deuxième hausse**. À toi.
13. ⚠️ **`installer-webhook-discord.sh`** — **44ᵉ jour**, variable absente.
14. ⓘ **Le cri de position doit-il recrier** à état constant ? (ouvert depuis
    le 01/10 ; « à front » vérifié **six** jours de suite)
15. ⓘ **AROME/R2 : journée du 25/10 perdue** (§6) — regarder l'Action
    `arome-wind`, hypothèse du changement d'heure. Hors mission.
16. ⓘ **`bw-model-oracle.service`** en `failed` — hors mission, non examiné.

## 14. Ce que ce run a DÉMENTI, et ce qu'il a CONFIRMÉ, de la note du 24/10

⚠️ **La note du 24/10 était une note de soulagement — « les trois alarmes
d'hier retombent toutes les trois ». Ce matin, deux de ses lectures rassurantes
sont renversées, et son refus le plus net est validé.**

| annoncé le 24/10 | relevé le 25/10 |
|---|---|
| ✅ purge propre, **17ᵉ** nuit, compteur 17/3, fermeture proposée | ⛔ **renversé** : la purge **n'aboutit pas**, des lignes RESTENT, compteur **0/3**, fermeture sans objet |
| ✅ `n_57014 = 0` partout | ⛔ **renversé** : 3, et les trois **dans la purge** |
| ⚠️ refus de lire « score par régime » à 2 781 Mo comme un mouvement de fond | ✅ **validé en 24 h** : 2 901 Mo, de nouveau au-dessus du seuil |
| ⚠️ réserve sur l'estimateur de pente (« pas utilisable en prévision ») | ✅ **validée une troisième fois** : −12 Mo/nuit le matin d'un record de +41 |
| ✅ le bloc hors étapes était un **pic d'une nuit**, pas un palier | ✅ **confirmé** : +8,7 s seulement, et la hausse du jour est **dans** les étapes |
| ✅ `agrume/pi` coupable R2, 11ᵉ nuit à +48 | ✅ **confirmé**, 12ᵉ nuit à +48, sans un recul |
| ✅ `agrume/grille` **strictement inchangé** à 766 objets, 11ᵉ nuit | ⚠️ **ne tient plus** : 772 objets, +43 Mo — mais **toujours 100 % réclamé**, donc toujours hors de cause |
| ✅ mécanisme des pentes négatives des fenêtres glissantes (§7.1) | ✅ **vérifié une sixième fois**, dans l'autre sens : elles rendent +46 Mo et le total remonte |
| ✅ « à front, pas à état » pour le cri de position | ✅ **6ᵉ vérification** : liste des confirmées identique, aucun cri |
| ✅ les trois correctifs du 07/10 tiennent | ⛔ **le troisième est mis en défaut** : faux négatif sur `bilan_purge` (§3, §9) |
| ⓘ critère `regime` à **0 / 2** | ⚠️ **remonte à 1 / 2** : +6,7 % après deux baisses |
| ✅ témoin du corrigé « oscille » | ✅ **confirmé** : 27,6 pt après 27,8 |
| ✅ écarts du recalcul « la hausse est défaite » (4) | ⚠️ **7 de nouveau** — et la série 3·5·4·7·4·7 montre qu'aucune des deux lectures n'était une tendance |

⚠️ **« Une nuit ne fait pas une pente » — neuvième fois en seize jours.**
Appliqué ce matin à : le record du jalon (§4.1), la hausse de la durée (§5), la
hausse du coût par ligne de `regime` (§1), le point bas des témoins du mélange
(§10), le mouvement de `agrume/grille` (§7.1), le `0 h appariées` du recalcul
(§10) et les deux matins à l'heure (§12). **Aucun des sept n'est présenté comme
une tendance.**

⛔ **Et une fois, ce matin, la leçon NE s'applique PAS** : « des lignes RESTENT »
n'est pas une pente, c'est un **fait d'une nuit** — et il suffit à lui seul,
parce qu'il s'auto-amplifie (une purge ratée double la suivante,
`enquete-pente-10-09.md` §1.4). Confondre les deux serait l'erreur inverse.

## 15. Respect des règles

✅ **VPS en LECTURE SEULE, pleine et entière** (la levée nominative du 07/10 ne
valait que pour cette session-là). Aucun `systemctl` start/restart/
daemon-reload, aucun `enable`, **aucun SQL joué**, aucun rsync, rien écrit dans
`~/balise-watch` ni dans `/etc`. Aucune redirection vers `/tmp` **du VPS** cette
fois : toutes les sorties sont redirigées vers le **Mac** (l'entorse mineure du
24/10 n'est pas répétée). ⓘ Seule exception, qui est le fonctionnement normal du
code de production : `bw_jira_http` écrit sa réponse dans un `mktemp -d` du VPS.
✅ **Aucun secret lu par valeur** : `.balise-watch-alertes.env` **sourcé**
(`set -a; . … ; set +a`) ; `BW_DISCORD_WEBHOOK_URL` cherchée **par son nom
seul** (`grep -c`) ; le jeton Jira passe par `curl -K -`, jamais `-u`.
✅ `10-timeout-s3.conf` **non touché** ; remontée du garde **non lancée**, et
seulement **décrite** dans le commentaire KAN-3, pas demandée au système.
✅ `controle_quotidien.sh` **non touché**, son `$ETAT` conservé. Le correctif du
§3.1 est **proposé**, pas écrit.
✅ **Aucun ticket créé, fermé, rouvert ni transité.** Cinq commentaires, tous
par `bw_jira_commenter`, tous vérifiés par un GET avant et après.
✅ **Desktop Commander exclusivement** pour fichiers et shell.
✅ **Aucun `git push`.** Un **commit local** depuis la **racine du dépôt
serveur** (jamais depuis un sous-dossier — cf. `BUGS.md`).
✅ **Lire avant d'écrire** : `project_read` du 25/10 (absent ⇒ création) et du
24/10 (lu en entier) ; `git log --since=midnight` dans les deux dépôts.

## 16. ⓘ Outillage — le piège du 24/10 confirmé, et un nouveau

1. ✅ **Le `SSH_AUTH_SOCK` manquant** (piège n°1 du 24/10) : confirmé, et le
   correctif marche du premier coup.

   ```
   export SSH_AUTH_SOCK="$(launchctl getenv SSH_AUTH_SOCK)"
   ```

   Dans un **process persistant** (`start_process "bash -l"` +
   `interact_with_process`), `ssh-add -l` voit ensuite
   `balise-watch-vps (ED25519)`. **Trois appels économisés** par rapport au
   24/10.
2. ✅ **Le lecteur de flux qui perd des lignes** (piège n°2 du 24/10) :
   confirmé une deuxième fois — la ligne `rc=…` a été avalée à chaque appel.
   ⇒ **Toute sortie dont une ligne compte est redirigée vers un fichier sur le
   Mac et relue avec `read_file`.** Appliqué systématiquement ce matin, aucune
   ligne perdue.
3. ⚠️ **NOUVEAU : `interact_with_process` rend « did not respond within 60s »
   alors que la commande tourne et aboutit.** C'est arrivé à **huit** appels
   sur neuf, y compris sur les deux appels qui postaient dans Jira. ⛔ **Ne
   jamais relancer** un appel d'écriture après ce message : il aurait doublé
   les commentaires. ✅ **La bonne réaction** : lire le fichier de sortie
   (`read_file`) ou `read_process_output`, et constater. Les cinq commentaires
   ont ainsi été postés **une seule fois chacun**, vérifié par le compte de
   commentaires avant/après (30→31, 43→45, 26→28).
