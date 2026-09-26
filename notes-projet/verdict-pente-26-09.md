# Verdict de pente du 26/09/2026 — tout redescend, et personne ne sait pourquoi

## 10:55 — routine Balise Watch (prévue 07:07 UTC, partie 08:42 UTC), lecture seule sur le VPS + trois commentaires Jira

**Étape 0** : `git log --since=midnight` **vide** dans les deux dépôts
(dernier commit `fe2182f`, 25/09, `notes-projet/`). Aucune note
`verdict-pente-26-09` avant celle-ci. Aucun autre run ce matin.
`notes-projet/README.md` relu.

## 1. Les nuits, bout à bout

| | 23/09 | 24/09 | 25/09 | 26/09 |
|---|---|---|---|---|
| durée | 4 685 s | 4 916 s | 4 941 s | **4 756 s (−185)** |
| garde / marge | 8 100 / 3 415 | 8 100 / 3 184 | 8 100 / 3 159 | **8 100 / 3 344 (+185)** |
| jalon max | 3 373 Mo | 3 371 Mo | 3 410 Mo | **3 317 Mo (−93)** |
| swap au pic | 2 281,6 | 2 202,0 | 2 172,0 | **2 335,9 (+164)** ⚠️ |
| pages sorties | 2 166 535 | 2 298 595 | 2 279 055 | **2 252 141** |
| pic système | 3 589,3 | 3 602,8 | 3 610,0 | **3 619,0 (+9)** |
| fenêtre rejouée | 1 945 246 | 1 980 799 | 2 003 977 | **2 022 451 (+0,92 %)** |
| o / ligne rejouée | 1 818,2 | 1 784,5 | 1 784,3 | **1 719,8 (−64,5)** |
| `cpu_s` | — | 3 896,2 | 3 923,3 | **3 755,3 (−168)** |
| `n_57014` | 2 | 5 | 2 | **0** |
| lancement / résultat | timer/success | timer/success | timer/success | **timer/success** |

La nuit est **comparable** (`lancement=timer`, `exec_status=0`,
05:56:06→07:15:32 — partie 3 min 49 s plus tôt que la veille).
Contrôle de ce matin (07:30:38 CEST) : « 58 relevé(s), **37
comparable(s)** ; durée : 10 points, pente **−21 s/nuit** ; mémoire :
10 points, pente **−24 Mo/nuit** (−2 hier) ; horizon 30 j ; seuil
2 800 Mo » — puis « **rien à dire** ». Timer sain, prochain tir
dimanche 27/09 07:30:24.

## 2. ⚠️ Durée : la hausse du 25/09 s'est inversée — question du §4 d'hier close

**−185 s**, et la marge sous le garde remonte de 3 159 à **3 344 s**
(41 % de 8 100). La série : 4 685 · 4 916 · 4 941 · **4 756**. On est
revenu au niveau du 22/09 (4 757 s).

La baisse est **au même endroit que la hausse**, et dans les mêmes
proportions — étapes 25→26 :

| étape | 25/09 | 26/09 | Δ |
|---|---|---|---|
| `glissant` | 962,6 | 897,5 | **−65,1** |
| `regime` | 1 639,1 | 1 503,1 | **−136,0** |
| `rejeu` | 75,3 | 75,6 | +0,3 |
| `stabilite` | 255,2 | 240,2 | −15,0 |

**73 % de la baisse est dans `regime`**, qui portait 81 % de la hausse.
Et comme à la hausse, le volume ne l'explique pas : `lignes_regime`
121 022 → 120 822 (−0,2 %) pour −136 s. `cpu_s` −168 s : c'est du
**calcul réel**, pas de la contention machine.

✅ **La question laissée à Yann le 25/09 (« faut-il rouvrir KAN-3 ? »)
n'a plus lieu d'être** : la hausse n'était pas une dérive, elle s'est
défaite d'elle-même en une nuit. KAN-3 reste « Terminé », **non
rouvert**, et porte désormais un commentaire qui le dit.

⚠️ Ce qui reste, et qui est nouveau : **la sensibilité de `regime`**.
±190 s d'un soir à l'autre à volume constant, sans changement de code.
Ce n'est pas une dérive, c'est du bruit d'amplitude inexpliquée — à
surveiller, pas à traiter.

## 3. ⛔ Mémoire : −93 Mo, et c'est là qu'il faut se méfier

Les trois franchissements sont toujours là, tous les trois **au-dessus
du seuil** :

```
06:44:56  ⛔ après le rejeu d'archive            : 2 936 Mo  (2 950 le 25)
07:10:03  ⛔ après le score par régime           : 2 893 Mo  (3 002 le 25)
07:14:09  ⛔ après l'oubli de la fenêtre rejouée : 3 317 Mo  (3 410 le 25)
```

Le jalon baisse de 93 Mo **pendant que la fenêtre grossit de 0,92 %**.
La courbe par ligne rejouée, que la note du 25/09 déclarait *plate et le
levier épuisé*, décroche d'un coup :

```
21/09 1 979 o · 22/09 1 866 · 23/09 1 818 · 24/09 1 784,5
25/09 1 784,3 · 26/09 1 719,8   → −64,5 o/ligne (−3,6 %)
```

À 1 784 o/ligne, la fenêtre de cette nuit (2 022 451 balise-jours)
aurait donné **3 441 Mo**. Elle en a fait 3 317 : **124 Mo** viennent de
la structure des données de la nuit.

⚠️ **Ce gain n'est le crédit d'aucun correctif.** Rien n'a été déployé
depuis `af25efb` (chaînes partagées, 21/09) ; les commits du 23 et du 25
ne touchent que `notes-projet/`. Les candidats sont tous du côté des
données : Murphy décompose **66 882** cases contre 67 927 la veille,
`lignes_daily` **remonte à 70 087** après son décrochage à 67 597 (le
point « à surveiller » du 25/09 était donc un accident isolé),
`lignes_regime` 120 822 (−200). **Une nuit ne fait pas une tendance**, et
c'est l'exact miroir de l'avertissement d'hier : on ne lit pas un
correctif dans une fluctuation, dans un sens comme dans l'autre.

⚠️ **Deux signaux vont à contre-courant de la baisse** : le **swap au pic
remonte de +164 Mo** (2 172,0 → 2 335,9) et le **pic système est le plus
haut de toute la série** (3 619,0 Mo). Le plancher de swap ne bouge pas :
il n'y a pas d'air sous le processus.

Le remède reste la **ligne en tuple** (§2.6, ≈ −1 030 o/ligne cumulés),
avec la mesure `tuple` vs `namedtuple` à la sonde AVANT de choisir
(leçon §2.3). Rien n'est décidé, rien n'est codé.

## 4. ✅ Zéro 57014 — mais la purge n'a rien eu à faire

**`n_57014 = 0`. Première nuit de la série sans un seul « canceling
statement due to statement timeout »**, ni dans le bloc purge ni ailleurs.
Les deux de la veille (`model_verif_daily [0-999]`,
`rpc/bw_character_avance`) n'ont pas reparu. **Aucun motif neuf.**

⚠️ Mais `delete_par_tranches` **n'a pas été éprouvé une seconde fois** :

```
07:15:20  ⓘ purge model_score_zone : rien à effacer (?as_of=lt.2026-09-19)
07:15:20  ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée
```

La borne a avancé d'un jour et n'a rien trouvé : la nuit du 25/09 avait
déjà effacé tout ce qui précédait. Le passage réussi du 25/09 (127 633
lignes, 18 tranches, ≈ 29 s) **reste la seule preuve**. Le point 3 du
25/09 est donc inchangé, pas avancé.

## 5. Tickets — trois commentaires, aucune transition

- **KAN-4 (`bw-pente-memoire`)** — « À faire », **laissé OUVERT**,
  commenté (HTTP 201, `bw_jira_http`, API v3, `curl -K -`). Aucune des
  trois conditions de fermeture remplie : jalon **3 317 > 2 800** (517 Mo
  au-dessus), swap au pic **2 335,9 ≠ 0** et en hausse, silence du
  contrôle encore inertiel (−24 Mo/nuit sur une fenêtre qui porte
  l'avant-21/09). Le commentaire porte les trois franchissements, la
  courbe par ligne et le calcul des 124 Mo non attribuables.
- **KAN-3 (`bw-pente-duree`)** — « Terminé / done », **non rouvert**,
  **commenté** (HTTP 201) : la hausse s'est inversée, le détail par étape,
  et la sensibilité de `regime` comme point de veille. Aucune remontée du
  garde-fou proposée — `controle_quotidien.proposition()` n'a rien formulé.
- **KAN-5 (`bw-purge-57014`)** — « À faire » depuis la réouverture du
  14/09, **laissé OUVERT**, **commenté** (HTTP 201) : zéro 57014, mais
  purge à vide, donc pas de seconde preuve. Réouverture du 14/09 toujours
  inexpliquée.
  ⚠️ Le prompt de la routine dit encore « KAN-5 est clos depuis le
  10/09 » : **faux depuis douze jours**, signalé le 25/09, toujours à
  corriger.

⛔ Aucun ticket fermé, aucune transition jouée.

## 6. Hors périmètre, relevé sur la nuit

- ✅ **Position : 9 balises divergent du gel (10 j lus), 0 CONFIRMÉE**
  (9 et 0 le 25/09). **Deuxième nuit sans aucune alerte** — pas de ligne
  « maille AROME ». Le cri pour zéro balise du 23/09 ne s'est pas répété
  en deux nuits : le point peut être considéré comme éteint, sauf reprise.
- ⚠️ **`push` (webhook) toujours pas éprouvé** : aucun cri déposé cette
  nuit non plus, donc le canal d'urgence reste non testé depuis le 23/09.
  Point inchangé.
- `⚠️ 4 ÉCART(S)` au recalcul indépendant (3 le 25/09, 7 le 24/09), tous
  du même motif — « 0 h appariées ici (< 6) mais la base porte une ligne »
  — et tous en `fcstagrume` : `aemet:9244X` (+24h), `windsmobi:ffvl-5023`
  (+24h), `aemet:9208E` (+24h), `infoclimat:000RO` (+48h). Sur 16
  balise-jours comparés dont 4 sous le seuil de 6 h.
- ✅ `lignes_daily` **remonte à 70 087** (67 597 le 25) : le décrochage
  d'hier était isolé.
- ⓘ R2 : 4 écritures, plafond 10, 159,9 Mo — rien près du plafond.
- `mutations_memoire` : 2 mutations non vues, dette antérieure, inchangée.

## 7. Ce qui a été touché

**VPS** : rien hors les trois commentaires Jira. `tail` du registre,
`journalctl` (contrôle et notation), `list-timers`, `controle_quotidien.py
--verbeux`, lecture de `bw_jira.sh`, trois GET Jira. Aucun `systemctl`,
aucun SQL, aucun rsync, rien écrit dans `~/balise-watch` ni dans `/etc`
(les trois textes de commentaire sont passés par un `mktemp -d` en 700
sous `/tmp`, effacé après). `~/.balise-watch-alertes.env` **sourcé**,
jamais lu.
**Mac** : cette note et son commit local — **pas de `git push`**.

## 8. Ce qui reste

1. **La mémoire** : décider la ligne en tuple. Le −64,5 o/ligne de cette
   nuit vient des données, pas du code — il ne change pas le diagnostic :
   517 Mo au-dessus du seuil, swap au pic en hausse, aucun levier de
   structure déployé depuis le 21/09.
2. **La sensibilité de `regime`** : ±190 s à volume constant, dans les
   deux sens en deux nuits. Nouveau point de veille, pas une dérive.
3. **KAN-5** : confirmer le faux mouvement du 14/09 et arbitrer la
   fermeture — toujours une seule preuve pour `delete_par_tranches`.
4. **Le webhook `push`** : canal d'urgence non éprouvé depuis le 23/09.
5. `mutations_memoire` : 2 mutations non vues.
6. **Corriger le prompt de la routine** : KAN-5 n'est pas clos (signalé
   le 25/09, non fait).
