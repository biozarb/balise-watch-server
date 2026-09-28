# Verdict de pente du 28/09/2026 — la purge casse pour de vrai, la durée au plus haut

## 16:55 — routine Balise Watch (prévue 07:07 UTC, partie 14:55 UTC), lecture seule sur le VPS + deux commentaires Jira

**Étape 0** : `git log --since=midnight` **vide** dans les deux dépôts,
aucune note `verdict-pente-28-09` avant celle-ci, aucun autre run ce
matin. `notes-projet/README.md` relu. Le run a démarré 7 h 48 en retard
sur son horaire (14:55 UTC au lieu de 07:07) — la nuit et le contrôle de
07:30 avaient donc déjà tourné depuis longtemps.

## 1. Les nuits, bout à bout

| | 25/09 | 26/09 | 27/09 | 28/09 |
|---|---|---|---|---|
| durée | 4 941 s | 4 756 s | 4 913 s | **5 295 s (+382)** |
| garde / marge | 8 100 / 3 159 | 8 100 / 3 344 | 8 100 / 3 187 | **8 100 / 2 805 (−382)** |
| jalon max | 3 410 Mo | 3 317 Mo | 3 340 Mo | **3 310 Mo (−30)** |
| swap au pic | 2 172,0 | 2 335,9 | 2 110,3 | **2 518,2 (+407,9)** |
| pages sorties | 2 279 055 | 2 252 141 | 2 076 323 | **2 488 586 (+412 263)** |
| pic système | 3 610,0 | 3 619,0 | 3 607,2 | **3 619,8 (record)** |
| fenêtre rejouée | 2 003 977 | 2 022 451 | 2 042 169 | **2 061 162 (+0,93 %)** |
| o / ligne rejouée | 1 784,3 | 1 719,8 | 1 715,0 | **1 683,9 (−31,1)** |
| `cpu_s` | 3 923,3 | 3 755,3 | 3 968,0 | **4 155,8 (+187,8)** |
| `n_57014` | 2 | 0 | 1 | **2** |
| lancement / résultat | timer/success | timer/success | timer/success | **timer/success** |

Nuit **comparable** (`lancement=timer`, `exec_status=0`, `oom=0`,
05:57:06→07:25:30, `✅ terminé (698 699 lignes écrites en base)`).
Contrôle de ce matin (07:30:57, tir régulier ; prochain mardi 29/09
07:30:16) : « 60 relevé(s), **39 comparable(s)** ; durée : 10 points,
pente **−21 s/nuit** ; mémoire : 10 points, pente **−30 Mo/nuit** ;
horizon 30 j ; seuil 2 800 Mo ». Il s'est tu sur la durée et la mémoire,
et il a **parlé sur `bw-purge-57014`** — le seul constat de la matinée.

## 2. ⛔ LE FAIT DE LA NUIT : la purge par tranches a échoué sur une vraie journée

C'est le point ouvert depuis le 11/09 qui se referme, et mal. La borne
n'est plus un `lt.` à vide : **une journée réelle à effacer, et un 57014
dessus**.

```
07:24:39  ⚠️ compte model_score_zone : HTTP 500 —
07:25:11  ⚠️ purge model_score_zone (?as_of=eq.2026-09-21) : HTTP 500
          {"code":"57014","message":"canceling statement due to statement timeout"}
07:25:19  ⚠️ compte model_score_zone : HTTP 500 —
07:25:19  → purge model_score_zone : ? ligne(s) effacée(s) en 18 tranche(s)
07:25:19  ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée.
```

Trois choses à retenir :

1. **Le `eq.` marche, le `DELETE` expire quand même.** `delete_par_tranches`
   a bien découpé — 18 tranches, comme le 25/09 — mais la requête a
   expiré. Le passage réussi du 25/09 (127 633 lignes, 18 tranches, ≈ 29 s)
   n'est donc **plus l'unique épreuve : c'est une épreuve sur deux**.
2. **Le compte échoue aussi**, avant et après (07:24:39 et 07:25:19) :
   d'où le `? ligne(s) effacée(s)`. Ce n'est pas seulement le `DELETE`
   qui souffre, c'est aussi un `count` sur la même table.
3. ⛔ **C'est exactement le cas que l'enquête avait posé comme bascule** :
   `controle_quotidien` l'écrit lui-même ce matin — « depuis le 10/09 la
   purge va par tranches et le rattrapage est `score.py --purge-seule` ;
   **si ça expire ENCORE, ce n'est plus la taille du retard, c'est la
   base** » (enquete-pente-10-09.md §1.6, §5). Le découpage n'a pas
   suffi : le soupçon se déplace sur la base (index, autovacuum,
   `statement_timeout` côté PostgREST).

⚠️ Et le retard **double** : la journée du 21/09 reste en base, celle du
22/09 arrive cette nuit. `score.py --purge-seule` existe pour rattraper —
**rien n'a été lancé**, c'est une décision pour Yann.

## 3. ⚠️ Durée : +382 s, la marge au plus bas de la série

`4 685 · 4 916 · 4 941 · 4 756 · 4 913 · **5 295**`. Cette fois la hausse
ne revient pas au point de départ : c'est le **plus haut de la série**, et
la marge sous le garde tombe à **2 805 s (34,6 % de 8 100)**, son plus bas
(3 344 → 3 187 → 2 805).

| étape | 27/09 | 28/09 | Δ |
|---|---|---|---|
| `regime` | 1 653,4 | 1 774,0 | **+120,6** |
| `stabilite` | 232,9 | 303,3 | **+70,4** |
| `glissant` | 988,6 | 993,8 | +5,2 |
| `rejeu` | 82,0 | 77,3 | −4,7 |

Les quatre étapes chronométrées expliquent **+191,5 s des +382** ; le
reste se répartit sur ce que le registre n'isole pas (climatologie horaire
225,0 s, antécédent du biais 65,6 s, antécédent fin…). `cpu_s` **+187,8 s** :
du calcul réel, pas de la contention.

⛔ **Et le volume baisse encore** : `lignes_regime` 115 043 → **113 937**
(−0,96 %), `lignes_score_zone` 125 782 → **124 678** (−0,88 %). `regime` a
coûté **+7,3 % de temps sur 1 % de lignes en moins**. En quatre nuits :
**−136,0 · +150,3 · +120,6**. Le découplage temps/volume ouvert le 26/09
se vérifie une troisième fois, et pour la première fois il **s'additionne
sur deux nuits** (+270,9 s cumulés) au lieu d'osciller.

⚠️ **Nouveau : `stabilite` +70,4 s (+30 %)**, pour 56 cases classées et
`tau = 0,772` (ok). Première fois que cette étape bouge de cet ordre.

✅ **Pourquoi le contrôle se tait quand même, et pourquoi ce n'est pas un
quitus** : la pente est le **25e centile des différences nuit à nuit sur
10 points** (en-tête de `controle_quotidien.py`, transposé d'`audit_r2`).
Par construction elle **ignore les deux plus grandes hausses** de la
fenêtre. D'où **−21 s/nuit pour la troisième matinée de suite, au chiffre
près**, une nuit à +382 s comprise. Le silence est le comportement voulu
(« un contrôle bavard est un contrôle mort »), il ne dit rien sur cette
nuit-là.

`controle_quotidien.proposition()` **n'a rien formulé** : pente négative,
échéance hors horizon. **Aucune remontée du chien de garde n'est proposée
par le script**, et `10-timeout-s3.conf` n'a pas été touché.

## 4. Mémoire : le jalon cède 30 Mo, le swap reprend 408

Les trois franchissements, tous au-dessus du seuil de 2 800 :

```
⛔ après le rejeu d'archive            : 2 977 Mo  (2 980 le 27)
⛔ après le score par régime           : 2 954 Mo  (2 843 le 27, +111)
⛔ après l'oubli de la fenêtre rejouée : 3 310 Mo  (3 340 le 27)
```

Jalon max **3 310 Mo**, encore **510 Mo au-dessus du seuil**. Coût par
ligne rejouée :

```
23/09 1 818,2 o · 24/09 1 784,5 · 25/09 1 784,3
26/09 1 719,8 · 27/09 1 715,0 · 28/09 1 683,9   → −31,1 o/ligne (−1,8 %)
```

Au taux de la veille la fenêtre de cette nuit aurait donné **3 371 Mo** ;
elle en a fait **3 310**, soit **−61 Mo « de structure »**. ⚠️ **Rien n'est
déployé depuis `af25efb` (21/09)** : c'est le même mirage que le 26/09
(−64,5 o/ligne, 124 Mo, effacé dès le 27/09). Deux nuits sur trois
montrent une baisse par ligne sans le moindre changement de code — donc
**fluctuation de données, pas acquis**. La leçon du 27/09 tient.

⛔ **Le swap va dans le mauvais sens** : pic **2 518,2 Mo (+407,9)**, le
plus haut depuis le 21/09, et **412 263 pages sorties de plus**. Le pic
système **3 619,8 Mo** est un **nouveau record** de la série (il passe
devant les 3 619,0 du 26/09). Le plancher de swap ne s'est pas seulement
maintenu : il est remonté.

Le remède reste la **ligne en tuple** (§2.6, ≈ −1 030 o/ligne cumulés),
avec la mesure `tuple` vs `namedtuple` à la sonde AVANT de choisir
(leçon §2.3). **Rien n'est décidé, rien n'est codé.**

## 5. ⚠️ Deux 57014, dont un appelant NEUF

`n_57014 = 2`, à deux endroits différents :

```
06:13:56  ⚠️ rpc/bw_character_avance : HTTP 500 57014 — reprise 1/3   ← HORS purge, appelant NEUF
07:25:11  ⚠️ purge model_score_zone (?as_of=eq.2026-09-21) : HTTP 500 57014   ← DANS la purge (§2)
```

Le premier est **un appelant qu'on n'avait pas encore vu** : ni
`model_verif_daily` (25/09, 27/09) ni la purge, mais le **RPC
`bw_character_avance`**. La reprise 1/3 a suffi (ni 2/3 ni 3/3), et
`model_character` est passé entier : **437 671 accumulateurs avancés sur
437 671 envoyés**. Les deux `⚠️ compte model_score_zone : HTTP 500`
(07:24:39, 07:25:19) sont vraisemblablement le même timeout, sans code
imprimé.

⚠️ Trois tables distinctes ont maintenant expiré en quatre nuits
(`model_verif_daily`, `rpc/bw_character_avance`, `model_score_zone`).
Ça ressemble moins à une requête à corriger qu'à une base sous tension —
même conclusion que le point 3 du §2.

## 6. Tickets — deux commentaires, aucune transition

États relevés **avant** d'écrire (GET `/rest/api/3/issue/…`, HTTP 200) :
KAN-3 **Terminé** (`statusCategory` = `done`), KAN-4 **À faire**,
KAN-5 **À faire** (mis à jour à 07:30:58 par le contrôle lui-même).

- **KAN-4 (`bw-pente-memoire`)** — **laissé OUVERT**, **commenté**
  (HTTP 201). Aucune des trois conditions de fermeture : jalon
  **3 310 > 2 800** (510 Mo au-dessus), swap au pic **2 518,2 ≠ 0 et en
  hausse**, silence du contrôle encore inertiel (−30 Mo/nuit sur une
  fenêtre qui porte l'avant-21/09). Le commentaire porte les trois
  franchissements, la courbe par ligne, le calcul des −61 Mo et
  l'avertissement qu'il s'agit du même mirage que le 26/09.
- **KAN-3 (`bw-pente-duree`)** — **non rouvert**, **commenté** (HTTP 201) :
  +382 s, la marge à 2 805 s, la répartition par étape, le découplage
  temps/volume de `regime` sur quatre nuits, le mouvement neuf de
  `stabilite`, et **l'explication du 25e centile** qui dit pourquoi le
  contrôle rend −21 s/nuit malgré tout. Aucune remontée du garde-fou
  (`proposition()` n'a rien formulé). La réouverture, ou l'ouverture d'un
  motif distinct `bw-regime-sensibilite`, reste à l'arbitrage de Yann.
- **KAN-5 (`bw-purge-57014`)** — **laissé OUVERT**, **non commenté par
  moi** : le contrôle a déjà déposé son constat à 07:30:58, et
  `bw_jira.sh` est explicite — « **un commentaire par jour et par motif,
  pas plus** ». Le détail du §2 est ici, dans cette note, et dans le
  message à Yann.

⛔ Aucun ticket fermé, aucune transition jouée, aucun ticket créé.

## 7. Hors périmètre, relevé sur la nuit

- ⚠️ **Position : 17 balises divergent du gel (10 j lus), 0 CONFIRMÉE** —
  contre **9** les trois nuits précédentes. **La série double.** Toutes à
  `nœud 0,01 CHANGE`, la plupart à 1 j, trois au-delà du kilomètre
  (`pioupiou:2132` 87 693 m et 2 j, `pioupiou:2023` 56 337 m et 2 j,
  `pioupiou:1354` 1 847 m). Aucune confirmation, donc aucun cri — mais le
  saut mérite un œil si la quatrième nuit le garde.
- ⚠️ **`push` (webhook) toujours pas éprouvé** : aucun cri déposé cette
  nuit non plus. Canal d'urgence non testé depuis le 23/09, **cinquième
  nuit**.
- ⚠️ `⚠️ 6 ÉCART(S)` au recalcul indépendant (6 le 27, 4 le 26, 3 le 25) :
  la série **se stabilise au lieu de monter**. Toujours **tous en
  `fcstagrume`**, toujours le même motif (« n h appariées ici (< 6) mais
  la base porte une ligne ») — `aemet:9262P`, `mf:06075007`,
  `windsmobi:ffvl-3994`, `aemet:9201X`, `infoclimat:000DG`,
  `mf:34205001`. Nuance : **deux d'entre eux sont à « 4 h appariées »**,
  pas à 0 — le seuil de 6 h est frôlé, pas absent.
- `lignes_daily` **70 288** (+106), et **66 013 détails par tranche**
  contre 61 576 (**+7,2 %**) : le creux de la veille est repris.
- Murphy : **66 817** cases, dont 64 427 décomposées, 266 balises dehors.
- ⓘ R2 : 4 écritures, plafond 10, **153,8 Mo** — rien près du plafond.
- `mutations_memoire` : aucune ligne au journal de la nuit ; dette
  antérieure de 2 mutations non vues, inchangée.
- Témoins du corrigé et du mélange : les trois `⛔ témoin` sont présents et parlants
  (part du site 18,2 pts, part secteur+heure 11,7 pts, mélange +0,3 % vs
  meilleur membre et +4,4 % vs uniforme).

## 8. Ce qui a été touché

**VPS** : rien hors les **deux** commentaires Jira. `tail` du registre,
`journalctl` (contrôle et notation), `list-timers`,
`controle_quotidien.py --verbeux`, lecture de `bw_jira.sh` et de l'en-tête
de `controle_quotidien.py`, trois GET Jira. Aucun `systemctl`, aucun SQL,
aucun rsync, rien écrit dans `~/balise-watch` ni dans `/etc` (les deux
textes de commentaire sont passés par un `mktemp -d` en 700, effacé
après). `~/.balise-watch-alertes.env` **sourcé**, jamais lu.
**Mac** : cette note et son commit local — **pas de `git push`**.

## 9. Ce qui reste — et ce qui demande Yann maintenant

1. ⛔ **La purge (le plus urgent)** : `delete_par_tranches` a échoué sur
   sa deuxième vraie épreuve. Le découpage ne suffit pas → la piste
   passe à la base (§1.6, §5). Deux décisions : lancer
   `score.py --purge-seule` pour rattraper le 21/09 avant que le retard
   double, et instruire le côté base. **Aucune des deux n'a été prise.**
2. ⚠️ **La durée** : marge à 2 805 s (34,6 %). Encore large, mais c'est le
   plus bas de la série et la hausse ne s'est pas annulée cette fois.
   À revoir dès demain matin — deux nuits de plus dans ce sens et la
   question du garde se posera pour de vrai.
3. **La sensibilité de `regime`** : −136 · +150 · +121 en quatre nuits,
   décorrélée du volume. Motif Jira dédié (`bw-regime-sensibilite`) ou
   simple veille ? **Question posée le 27/09, sans réponse.**
4. **La mémoire** : décider la ligne en tuple. Jalon 510 Mo au-dessus du
   seuil, swap au pic au plus haut, aucun levier déployé depuis le 21/09.
5. **Le 57014 sur `rpc/bw_character_avance`** : appelant neuf. Troisième
   table à expirer en quatre nuits. Motif Jira à part, ou à joindre au
   dossier « base sous tension » ? **Rien créé.**
6. **Le webhook `push`** : canal d'urgence non éprouvé depuis le 23/09.
7. **Position : 9 → 17 divergences** en une nuit, sans confirmation.
8. `mutations_memoire` : 2 mutations non vues.
9. **Corriger le prompt de la routine** : KAN-5 **n'est pas** clos depuis
   le 10/09 (signalé les 25, 26 et 27/09 — toujours pas fait), et KAN-3
   est en « Terminé » (`statusCategory = done`) alors que le prompt le
   décrit comme suivi — la date de fermeture n'a pas été relevée.

Miroir git : `notes-projet/verdict-pente-28-09.md`, commit local `bc057e4`, pas de push.
