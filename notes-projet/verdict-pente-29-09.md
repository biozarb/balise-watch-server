# Verdict de pente du 29/09/2026 — la nuit se détend, la purge est blanchie, la mémoire tient bon

## 09:10 — routine Balise Watch (départ 07:09 UTC), lecture seule sur le VPS + deux commentaires Jira

**Étape 0 faite.** `git log --since=midnight` : **deux commits du jour**
dans le dépôt serveur (`e83d814` la purge réécrite, `b28d25e` le miroir de
note), **rien** dans le dépôt principal. La note
`claude/session-purge-57014-29-09.md` existait déjà : la session de 08:10
avec Yann a débogué la purge, déployé le correctif à 08:35 et corrigé le
prompt de la routine. **Ce travail n'est pas refait ici.** Ce qui manquait,
et que cette section apporte : le **verdict de la nuit du 28→29/09**
(chiffres, deltas, mémoire, durée) et le **traitement des tickets**, que la
session de 08:10 n'a pas touchés. `notes-projet/README.md` relu.

## 1. Les nuits, bout à bout

| | 26/09 | 27/09 | 28/09 | 29/09 |
|---|---|---|---|---|
| durée | 4 756 s | 4 913 s | 5 295 s | **5 232 s (−63)** |
| garde / marge | 8 100 / 3 344 | 8 100 / 3 187 | 8 100 / 2 805 | **8 100 / 2 868 (+63)** |
| jalon max | 3 317 Mo | 3 340 Mo | 3 310 Mo | **3 305 Mo (−5)** |
| swap au pic | 2 335,9 | 2 110,3 | 2 518,2 | **2 329,1 (−189,1)** |
| pages sorties | 2 252 141 | 2 076 323 | 2 488 586 | **2 454 474 (−34 112)** |
| pic système | 3 619,0 | 3 607,2 | 3 619,8 | **3 601,8 (−18,0)** |
| fenêtre rejouée | 2 022 451 | 2 042 169 | 2 061 162 | **2 073 557 (+0,60 %)** |
| o / ligne rejouée | 1 719,8 | 1 715,0 | 1 683,9 | **1 671,3 (−12,6)** |
| `cpu_s` | 3 755,3 | 3 968,0 | 4 155,8 | **4 185,2 (+29,4)** |
| `n_57014` | 0 | 1 | 2 | **2** |
| lancement / résultat | timer/success | timer/success | timer/success | **timer/success** |

Nuit **comparable** (`lancement=timer`, `exec_status=0`, `oom=0`,
05:56:25→07:23:48, `✅ terminé (693 127 lignes écrites en base)`).
Contrôle de ce matin **07:30:25, tir régulier** (prochain mercredi 30/09
07:30:42) : « 61 relevé(s), **40 comparable(s)** ; durée : 10 points, pente
**−63 s/nuit** ; mémoire : 10 points, pente **−30 Mo/nuit** ; horizon 30 j ;
seuil 2 800 Mo » puis « rien à dire : pente plate/négative, ou échéance
hors horizon ». Il s'est tu sur **les trois** motifs — durée, mémoire **et
`bw-purge-57014`** : contrairement au 28/09, il n'a rien commenté dans
Jira ce matin.

## 2. ✅ La purge est blanchie — et le journal de la nuit le confirme

La nuit a tourné avec le code **d'avant** le correctif (déployé à 08:35,
après). Bloc purge en entier :

```
07:23:04  ⚠️ compte model_score_zone : HTTP 500 —
07:23:34  → purge model_score_zone : ? ligne(s) effacée(s) en 540 tranche(s)
07:23:34  ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée.
```

- **Aucun 57014 dans la purge.** Les **540 tranches ont toutes réussi** :
  c'est le repli aveugle sur `seuil − 60 j` de l'ancien code, 540 `DELETE`
  à vide en 30 s.
- Le `⚠️ compte model_score_zone` est le `HEAD … count=exact` sur
  `as_of < seuil`, **pas** la purge — et c'est lui qui écrit le
  `? ligne(s) effacée(s)`.
- **Aucune ligne `des lignes RESTENT`** ⇒ rien ne reste en base. Confirmé
  par l'épreuve directe de 08:35 : `--purge-seule` → « rien à effacer
  (`?as_of=lt.2026-09-22`) ».

Le retard annoncé le 28/09 **n'a jamais existé** (§ détaillé dans
`session-purge-57014-29-09.md`). Les deux `n_57014` de la nuit sont
ailleurs (§5).

⏳ **La vraie épreuve reste la nuit du 29→30** : journée du 22/09 à
effacer, attendu `→ purge model_score_zone : N ligne(s) effacée(s) en
8 tranche(s)` avec N ≈ 125 000 et **aucune** ligne `compte`.

## 3. ✅ Durée : −63 s, la marge remonte, et le découplage ne s'additionne pas

`4 941 · 4 756 · 4 913 · 5 295 · **5 232**`. La hausse du 28/09 ne se
poursuit pas : **−63 s**, et la marge sous le garde repasse à **2 868 s
(35,4 % de 8 100)**. Ce n'est pas un retour au niveau du 27/09 — on reste
au deuxième plus haut de la série — mais la pente n'est plus celle de
l'inquiétude.

| étape | 28/09 | 29/09 | Δ |
|---|---|---|---|
| `regime` | 1 774,0 | 1 787,6 | +13,6 |
| `stabilite` | 303,3 | 295,4 | −7,9 |
| `glissant` | 993,8 | 985,4 | −8,4 |
| `rejeu` | 77,3 | 79,2 | +1,9 |

Les quatre étapes chronométrées sont à **−0,8 s près à l'équilibre** : les
−63 s viennent de ce que le registre n'isole pas. `cpu_s` **+29,4 s** :
du calcul réel, en légère hausse.

⛔→✅ **Le découplage temps/volume de `regime` s'inverse.** Le volume
**remonte** : `lignes_regime` 113 937 → **116 149 (+1,94 %)**,
`lignes_score_zone` 124 678 → **126 857 (+1,75 %)**. `regime` n'a pris que
**+0,77 % de temps pour +1,94 % de lignes**, soit **15,39 ms/ligne contre
15,57 (−1,15 %)**. La série des Δ `regime` sur cinq nuits :
**−136,0 · +150,3 · +120,6 · +13,6**. ⇒ **La condition d'arbitrage du
29/09 n'est PAS remplie** (« sauf si la hausse s'additionne encore deux
nuits de suite ») : `bw-regime-sensibilite` **reste en simple veille**,
aucune question reposée à Yann, aucun motif créé.
⚠️ Nuance honnête : `regime` est quand même à son **plus haut absolu**
(1 787,6 s) ; c'est le coût par ligne qui s'améliore, pas le coût total.

✅ `stabilite` retombe (−7,9 s) après son mouvement neuf du 28/09, et la
qualité monte : **`tau = 0,803` sur 57 cases** (0,772 sur 56 la veille).

`controle_quotidien.proposition()` **n'a rien formulé** (pente négative).
**Aucune remontée du chien de garde n'est proposée par le script**, et
`10-timeout-s3.conf` n'a pas été touché.

## 4. Mémoire : tout bouge dans le bon sens, rien n'est acquis

Les trois franchissements, tous au-dessus du seuil de 2 800 :

```
⛔ après le rejeu d'archive            : 3 004 Mo  (2 977 le 28, +27 — plus haut de la série pour ce jalon)
⛔ après le score par régime           : 2 942 Mo  (2 954 le 28, −12)
⛔ après l'oubli de la fenêtre rejouée : 3 305 Mo  (3 310 le 28, −5)  ← jalon max
```

Jalon max **3 305 Mo**, encore **505 Mo au-dessus du seuil**. Coût par
ligne rejouée :

```
23/09 1 818,2 o · 24/09 1 784,5 · 25/09 1 784,3 · 26/09 1 719,8
27/09 1 715,0 · 28/09 1 683,9 · 29/09 1 671,3   → −12,6 o/ligne (−0,75 %)
```

Au taux de la veille la fenêtre de cette nuit (2 073 557) aurait donné
**3 330 Mo** ; elle en a fait **3 305**, soit **−25 Mo « de structure »**.
⚠️ **Même mise en garde que le 26 et le 28/09** : rien n'est déployé côté
mémoire depuis `af25efb` (21/09). **Trois nuits sur quatre** montrent une
baisse par ligne sans le moindre changement de code ⇒ **fluctuation de
données, pas acquis**. Le −25 Mo ne se compte pas comme un gain.

✅ **Le swap redescend** : pic **2 329,1 Mo (−189,1)**, 34 112 pages
sorties de moins, pic système **3 601,8 Mo (−18,0)** — le record du 28/09
n'est pas battu. Mais 2 329,1 ≠ 0 : le plancher de swap est toujours là.

Le remède reste la **ligne en tuple** (§2.6, ≈ −1 030 o/ligne cumulés),
avec la mesure `tuple` vs `namedtuple` à la sonde AVANT de choisir
(leçon §2.3). **Rien n'est décidé, rien n'est codé.**

## 5. Deux 57014, les deux sur `rpc/bw_character_avance`

```
06:13:57  ⚠️ rpc/bw_character_avance : HTTP 500 57014 — reprise 1/3
06:19:02  ⚠️ rpc/bw_character_avance : HTTP 500 57014 — reprise 1/3
```

Les deux reprises 1/3 ont suffi (ni 2/3 ni 3/3) et `model_character` est
passé **entier : 433 162 accumulateurs avancés sur 433 162 envoyés**. Le
`⚠️ compte model_score_zone : HTTP 500 —` de 07:23:04 n'imprime pas de
code et n'est pas compté dans `n_57014 = 2`.

Ce n'est **pas neuf** (10/09, 16/09, 28/09 ×1, 29/09 ×2) : c'est le
dossier **« base sous tension »**, et
`model-verif/diagnostic_base_sous_tension_2026-09-29.sql` (lecture seule,
9 blocs) **attend d'être joué par Yann**. Ça se compte, ça se signale, ça
ne se dramatise pas. ⚠️ Deuxième nuit d'affilée avec cet appelant, et le
compte passe de 1 à 2.

## 6. Tickets — deux commentaires, aucune transition

États relevés **avant** d'écrire (GET `/rest/api/3/issue/…`, HTTP 200) :

| ticket | motif | statut | `statusCategory` | dernier commentaire avant ce matin |
|---|---|---|---|---|
| KAN-3 | `bw-pente-duree` | **Terminé** | `done` (résolu 21/09) | 28/09 17:02 |
| KAN-4 | `bw-pente-memoire` | **À faire** | `new` | 28/09 17:02 |
| KAN-5 | `bw-purge-57014` | **À faire** | `new` | 28/09 07:30:58 (le contrôle) |

- **KAN-4 (`bw-pente-memoire`)** — **laissé OUVERT**, **commenté**
  (HTTP 201, via `bw_jira_signaler`). Aucune des trois conditions de
  fermeture : jalon **3 305 > 2 800** (505 Mo au-dessus, pas
  « mesurablement retombé »), swap au pic **2 329,1 ≠ 0**, silence du
  contrôle encore inertiel (−30 Mo/nuit, inchangé au chiffre près depuis
  trois matinées, sur une fenêtre qui porte l'avant-21/09). Le commentaire
  porte les trois franchissements, la courbe par ligne, le calcul des
  −25 Mo **et** l'avertissement que c'est le même mirage que le 26 et le
  28/09.
- **KAN-5 (`bw-purge-57014`)** — **laissé OUVERT**, **commenté**
  (HTTP 201). Le contrôle de 07:30:25 **n'a rien commenté ce matin** (il
  s'est tu), donc la règle « un commentaire par jour et par motif » ne
  bloquait pas. Le commentaire **corrige le diagnostic faux du 28/09** :
  aucun 57014 dans la purge cette nuit, aucune ligne en retard, la
  neuvième tranche sans `&regime=` ne pouvait rien trouver, le `compte`
  n'était pas la purge ; puis le correctif `e83d814` déployé à 08:35 et
  l'attendu de la nuit 29→30. Fermeture : **trois nuits consécutives sans
  57014 dans le bloc purge ET un nombre de lignes lisible**, et c'est
  Yann qui tranche.
- **KAN-3 (`bw-pente-duree`, Terminé)** — **non rouvert, NON commenté.**
  La consigne est de commenter si la durée **augmente** : elle **baisse**
  (−63 s, marge +63). Bonne nouvelle, pas de motif de dépenser le
  commentaire du jour sur un ticket clos. La correction du découplage est
  ici, au §3.
- **Aucun motif neuf créé** : `bw-regime-sensibilite` reste en veille
  (condition non remplie, §3), et le 57014 de `rpc/bw_character_avance`
  reste rattaché au dossier « base sous tension » (§5).

⛔ Aucun ticket fermé, aucune transition jouée, aucun ticket créé.

## 7. Hors périmètre, relevé sur la nuit

- ✅ **Écarts au recalcul indépendant : 3** (6 le 28, 6 le 27, 4 le 26,
  3 le 25) — la série **redescend**. Toujours **tous en `fcstagrume`**,
  et cette fois **tous à « 0 h appariées »** (plus de cas frôlant le seuil
  de 6 h) : `windsmobi:holfuy-1169` (agrume_pi +24 h),
  `infoclimat:000YN` (agrume +48 h), `mf:12145001` (agrume +6 h) — trois
  balises **différentes** de celles du 28/09.
- ⚠️ **Position : 17 balises divergent du gel (10 j lus), 0 CONFIRMÉE** —
  **deuxième nuit à 17** (9 · 9 · 9 · 17 · 17). Le saut du 28/09 **se
  maintient** au lieu de retomber. Toujours aucune confirmation, donc
  aucun cri, mais la série tient : à surveiller une troisième nuit.
- ⚠️ **`push` (webhook) toujours pas éprouvé** : aucun cri déposé cette
  nuit non plus. Canal d'urgence non testé depuis le 23/09, **sixième
  nuit**.
- `lignes_daily` **70 055** (−233) et **65 052 détails par tranche**
  contre 66 013 (−961) : léger reflux après le rebond du 28/09.
- Murphy : **66 798** cases, dont **64 325** décomposées, 266 balises
  dehors (inchangé).
- FDR : brut 7 156 tests, 2 181 survivants (85 rangs retirés sur 1 275) ;
  corrigé 6 830 tests, 1 649 survivants (94 sur 803).
- ⓘ R2 : **4 écritures**, plafond 10, **155,8 Mo** — rien près du plafond.
- `mutations_memoire` : **aucune ligne** au journal de la nuit ; dette
  antérieure de **3 mutations non vues** (2, 5, 13 — motifs anciens qui
  ont bougé, relevée ce matin par la session de 08:10).
- Témoins : part du site **15,9 pts** (18,2 le 28), part secteur+heure
  **10,3 pts** (11,7), mélange **+2,4 %** vs meilleur membre a priori
  (+0,3 % le 28) et **+5,7 %** vs uniforme (+4,4 %). Le mélange gagne
  nettement plus que la veille.
- 9 balises nées sous leur identifiant (`notee_depuis`, lot L15-bis),
  toutes du 25/09.

## 8. Ce qui a été touché

**VPS** : rien hors les **deux** commentaires Jira. `tail` du registre,
`journalctl` (contrôle et notation), `list-timers`,
`controle_quotidien.py --verbeux`, lecture de `bw_jira.sh`, cinq GET Jira,
listage du dossier de jetons `~/.balise-watch-etat-alertes`. Aucun
`systemctl`, aucun SQL, aucun rsync, rien écrit dans `~/balise-watch` ni
dans `/etc` (les deux textes de commentaire sont passés par
`bw_jira_signaler`, qui travaille dans un `mktemp -d` en 700 effacé
après ; seuls les deux jetons `cri.jira.<motif>` du jour ont été écrits,
par le canal lui-même). `~/.balise-watch-alertes.env` **sourcé**, jamais
lu. **Mac** : cette note (+ son miroir git, voir plus bas) — **pas de
`git push`**.

## 9. Ce qui reste — et ce qui demande Yann

1. ⏳ **La nuit du 29→30, première vraie épreuve du correctif de purge.**
   C'est le seul point vraiment en attente d'un fait : journée du 22/09,
   ≈ 125 000 lignes, 8 tranches, aucune ligne `compte`.
2. **Le dossier « base sous tension »** :
   `diagnostic_base_sous_tension_2026-09-29.sql` et
   `rattrapage_purge_2026-09-29.sql` **attendent d'être joués par Yann**
   dans le SQL Editor. Tant que ce n'est pas fait,
   `rpc/bw_character_avance` continuera de rendre un 57014 repris une ou
   deux fois par nuit (deuxième nuit d'affilée, ×2 cette fois).
3. **La mémoire (KAN-4)** : décider la ligne en tuple. Jalon 505 Mo
   au-dessus du seuil, swap au pic 2 329,1 Mo, **aucun levier déployé
   depuis le 21/09**. La baisse par ligne de cette nuit ne compte pas.
4. ✅ **La durée** : plus rien à décider ce matin. Marge 2 868 s (35,4 %),
   pente du contrôle −63 s/nuit, découplage `regime` inversé.
   `bw-regime-sensibilite` reste en veille, conformément à l'arbitrage du
   29/09.
5. **Position : deuxième nuit à 17 divergences** sans confirmation. Une
   troisième nuit à ce niveau mériterait un coup d'œil au gel.
6. **Le webhook `push`** : canal d'urgence non éprouvé depuis le 23/09,
   sixième nuit.
7. `mutations_memoire` : 3 mutations non vues (dette antérieure).
8. ✅ **Le prompt de la routine est corrigé** (session de 08:10) : le point
   9 du verdict du 28/09 est réglé.

---

ⓘ **Déposé le 30/09/2026 à 09:16 par la routine du lendemain.** Le pont
vers le Mac avait lâché le 29/09 juste après les commentaires Jira : ce
miroir n'avait pas pu être écrit ce jour-là. Le texte est celui du
document projet `claude/verdict-pente-29-09.md`, repris à l'identique.
