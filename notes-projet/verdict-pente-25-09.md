# Verdict de pente du 25/09/2026 — le contrôle se tait, et c'est la fenêtre qui le fait taire

## 11:20 — routine Balise Watch (prévue 07:00 UTC, partie 09:18 UTC), lecture seule sur le VPS + deux commentaires Jira

**Étape 0** : `git log --since=midnight` **vide** dans les deux dépôts.
Une autre session a tourné ce matin (08:37 UTC) mais sur un tout autre
sujet — `claude/alerte-garde-fou-r2-25-09.md`, le seuil R2 franchi —
sans toucher à la pente ni aux tickets. Aucune note
`verdict-pente-25-09` avant celle-ci, et **aucune note du 24/09** : la
nuit 23→24 n'avait jamais été lue. `notes-projet/README.md` relu.

## 1. Les nuits, bout à bout

| | 22/09 | 23/09 | 24/09 | 25/09 |
|---|---|---|---|---|
| durée | 4 757 s | 4 685 s | 4 916 s (+231) | **4 941 s (+25)** |
| garde / marge | 8 100 / 3 343 | 8 100 / 3 415 | 8 100 / 3 184 | **8 100 / 3 159** |
| jalon max | 3 397 Mo | 3 373 Mo | 3 371 Mo (−2) | **3 410 Mo (+39)** |
| swap au pic | 2 000,0 | 2 281,6 | 2 202,0 (−80) | **2 172,0 (−30)** |
| pages sorties | 2 039 231 | 2 166 535 | 2 298 595 | **2 279 055** |
| pic système | 3 610,5 | 3 589,3 | 3 602,8 | **3 610,0** |
| fenêtre rejouée | 1 909 457 | 1 945 246 | 1 980 799 (+1,8 %) | **2 003 977 (+1,2 %)** |
| `n_57014` | 5 | 2 | 5 | **2** |
| lancement / résultat | timer/success | timer/success | timer/success | **timer/success** |

Les deux nuits lues sont **comparables** (`lancement=timer`,
`exec_status=0`, 05:59:21→07:21:29 puis 05:59:55→07:22:25). Contrôle de
ce matin (07:30:31 CEST) : « 57 relevé(s), **36 comparable(s)** ;
durée : 10 points, pente **−21 s/nuit** ; mémoire : 10 points, pente
**−2 Mo/nuit** ; horizon 30 j ; seuil 2 800 Mo » — puis « **rien à
dire** : pente plate ou négative, ou échéance hors horizon ».

## 2. ✅ La purge : le point ouvert depuis le 11/09 est levé

**`delete_par_tranches` a passé son premier test réel, et il l'a passé.**

```
07:21:43  → model_scores_light.json publié
07:22:12  → purge model_score_zone : 127 633 ligne(s) effacée(s) en 18 tranche(s)
07:22:12  ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée
07:22:12  ✅ terminé (706 598 lignes écrites en base)
```

≈ 29 s pour 127 633 lignes, **aucune reprise, aucun HTTP 500 dans le
bloc purge**. Depuis le 11/09 la borne ne trouvait jamais rien à
effacer — encore la veille : « rien à effacer (`?as_of=lt.2026-09-17`) ».
Cette nuit la borne est passée sur une vraie journée, et le découpage en
tranches a tenu la charge qui avait fait tomber la purge d'un bloc.
C'est le **point 5 de la liste du 23/09**, réglé.

Les deux `57014` de la nuit sont **hors bloc purge**, comme les nuits
précédentes : `model_verif_daily [0-999]` à 06:14:39 et
`rpc/bw_character_avance` à 06:21:58, chacun repris 1/3 et reparti. La
nuit 23→24 en portait 5, même profil, tous hors purge. **Aucun motif
neuf.**

## 3. ⛔ Mémoire : le contrôle se tait, mais par inertie de fenêtre

Les trois franchissements sont toujours là, et le plus gros **remonte** :

```
06:48:37  ⛔ après le rejeu d'archive            : 2 950 Mo  (2 915 le 23)
07:16:00  ⛔ après le score par régime           : 3 002 Mo  (3 017 le 23)
07:20:23  ⛔ après l'oubli de la fenêtre rejouée : 3 410 Mo  (3 373 le 23)
```

Le contrôle lit **−2 Mo/nuit** sur 10 points et se tait. ⚠️ **Ce silence
n'est pas une résolution** : la fenêtre de 10 relevés porte encore les
nuits d'avant les chaînes partagées (jalon 3 510 Mo le 21/09), donc la
régression descend pendant que le jalon est à **son plus haut des quatre
dernières nuits**. C'est exactement l'inertie décrite pour la durée le
21/09, dans l'autre sens.

**Ramené à la ligne rejouée, le levier est épuisé** : 1 979 o/ligne le
21/09, 1 866 le 22, **1 818 le 23, 1 785 le 24, 1 784 le 25**. Le gain
des chaînes partagées (`af25efb`) est entièrement absorbé — la courbe
par ligne est plate depuis deux nuits. La fenêtre, elle, continue :
**+58 731 balise-jours en deux nuits (+3,0 %)**, soit ≈ **+50 Mo** de
jalon par cette seule voie. Le pronostic du 23/09 (« le partage achète
deux nuits ») s'est vérifié à la nuit près.

Le remède reste la **ligne en tuple** (§2.6, ≈ −1 030 o/ligne cumulés),
avec la mesure `tuple` vs `namedtuple` à la sonde AVANT de choisir
(leçon §2.3). Rien n'est décidé, rien n'est codé.

## 4. ⚠️ Durée : elle remonte, et le contrôle ne peut pas encore le voir

**+256 s en deux nuits** (4 685 → 4 916 → 4 941), et la marge sous le
garde tombe de 3 415 à **3 159 s**. Le contrôle lit pourtant **−21 s/nuit**
sur 10 points, pour la même raison qu'au §3 : la fenêtre porte encore
les longues nuits d'avant le 21/09. Il se tait, **KAN-3 reste « Terminé »**.

La hausse est localisée, elle n'est pas diffuse — étapes 23→24→25 :

| étape | 23/09 | 24/09 | 25/09 | Δ 2 nuits |
|---|---|---|---|---|
| `glissant` | 934,0 | 951,4 | 962,6 | **+28,6** |
| `regime` | 1 431,8 | 1 624,2 | 1 639,1 | **+207,3** |
| `rejeu` | 67,9 | 72,2 | 75,3 | **+7,4** |
| `stabilite` | 219,2 | 241,4 | 255,2 | **+36,0** |

**81 % de la hausse est dans `regime`**, et `regime` a sauté d'un coup la
nuit 23→24 (+192 s) alors que `lignes_regime` a *baissé* (122 994 →
121 002 → 121 022). Ce n'est donc pas un simple effet de volume. La
fenêtre rejouée (+3,0 %) explique `rejeu` et une part de `glissant`,
pas ce saut-là.

⛔ **Question pour Yann, je n'ai pas tranché** : le mandat dit « si la
durée AUGMENTE, laisse ouvert et commente », mais KAN-3 est **fermé**
depuis le 21/09 et le contrôle se tait. Rouvrir un ticket clos est une
décision qui engage — je ne l'ai pas prise. Deux nuits de plus et la
fenêtre basculera d'elle-même ; d'ici là, la marge (3 159 s sous 8 100,
soit 39 %) laisse largement le temps. **Aucune remontée du garde-fou
n'est proposée** : `controle_quotidien.proposition()` n'a rien formulé.

## 5. Tickets

- **KAN-4 (`bw-pente-memoire`)** — « À faire », **laissé OUVERT**,
  commenté (HTTP 201, `bw_jira_http`, API v3, `curl -K -`). Aucune des
  trois conditions de fermeture n'est remplie : jalon 3 410 > 2 800,
  swap au pic 2 172 ≠ 0, et le silence du contrôle est inertiel, pas
  mesuré. Le commentaire porte le tableau des trois nuits, les
  franchissements, la courbe par ligne et le calcul des +50 Mo.
- **KAN-3 (`bw-pente-duree`)** — « Terminé / done », **non touché**
  (dernière maj 21/09). Voir la question du §4.
- **KAN-5 (`bw-purge-57014`)** — toujours « À faire » depuis la
  réouverture du 14/09 à 21:41, **commenté** (HTTP 201) avec le premier
  passage réussi de `delete_par_tranches`. **Non refermé** : un seul
  passage ne fait pas une preuve, et la réouverture du 14/09 reste
  inexpliquée (même minute que KAN-9 et KAN-11 — faux mouvement
  probable pendant un tri Jira). Une fermeture s'arbitre.
  ⚠️ Le prompt de la routine dit toujours « KAN-5 est clos depuis le
  10/09 » : c'est faux depuis onze jours, à corriger.

## 6. Hors périmètre, relevé sur la nuit

- ✅ **Position : 9 balises divergent du gel (10 j lus), 0 CONFIRMÉE**
  (10 et 0 le 23/09). Et cette fois **aucune alerte n'est partie** — pas
  de ligne « maille AROME » dans le journal de la nuit. Le cri pour zéro
  balise signalé le 23/09 ne s'est pas répété ; à re-vérifier une nuit
  de plus avant d'en conclure quoi que ce soit.
- ✅ **Aucun `push non parti (webhook)`** cette nuit — mais aucun cri
  n'a été déposé non plus, donc la jambe *push* n'a pas été éprouvée.
  Le point reste ouvert.
- `⚠️ 3 ÉCART(S)` au recalcul indépendant (7 le 24/09, 4 le 23/09), tous
  du même motif : « 0 h appariées ici (< 6) mais la base porte une
  ligne » — `fcstagrume/infoclimat:STATIC0442`, `fcstagrume/mf:04134002`,
  `fcstagrume/pioupiou:827`, toutes en `+6h`.
- ⓘ `lignes_daily` recule : 70 146 → 70 199 → **67 597**. Premier vrai
  décrochage de la série ; à surveiller, rien de concluant ce matin.
- `mutations_memoire` : 2 mutations non vues, dette antérieure, inchangée.

## 7. Ce qui a été touché

**VPS** : rien hors les deux commentaires Jira. `tail` du registre,
`journalctl` (contrôle et notation), `list-timers`, `controle_quotidien.py
--verbeux`, lecture de `bw_jira.sh`, lectures Jira en GET. Aucun
`systemctl`, aucun SQL, aucun rsync, rien écrit dans `~/balise-watch`
ni dans `/etc` (les deux textes de commentaire sont passés par `/tmp` et
ont été effacés).
**Mac** : cette note et son commit local — pas de `git push`.

## 8. Ce qui reste

1. **La mémoire** : décider la ligne en tuple — le levier par ligne des
   chaînes partagées est épuisé (plat à 1 784 o/ligne), la fenêtre
   continue de monter. C'est le seul levier à la bonne échelle.
2. **La durée qui remonte** (+256 s en deux nuits, 81 % dans `regime`) :
   dire s'il faut rouvrir KAN-3, ou attendre que la fenêtre bascule.
3. **KAN-5** : confirmer le faux mouvement du 14/09, et arbitrer la
   fermeture maintenant que `delete_par_tranches` a fait ses preuves une
   fois.
4. **Le webhook push** : canal d'urgence non éprouvé depuis le 23/09.
5. **L'alerte position** : n'a pas crié cette nuit, à confirmer.
6. `mutations_memoire` : 2 mutations non vues.
7. Corriger le prompt de la routine : KAN-5 n'est pas clos.

Miroir git : `notes-projet/verdict-pente-25-09.md`, commit local `d79d577`, pas de push.
