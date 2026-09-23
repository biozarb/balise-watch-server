# Verdict de pente du 23/09/2026 — les chaînes partagées ont pris, mais la fenêtre les rattrape en deux nuits

## 23:30 — routine Balise Watch (prévue 07:07 UTC, partie 21:22 UTC), lecture seule sur le VPS + un commentaire Jira

**Étape 0** : deux commits du jour, aucun sur la pente — `c74a32e`
(serveur, PIAF 203 octets) et `286fe9d` (principal, BUGS.md, même sujet).
Pas de note `verdict-pente-23-09` avant celle-ci. Personne n'avait lu le
contrôle de pente aujourd'hui. `notes-projet/README.md` relu.

**Le blocage du 22/09 est levé** : `ssh debian@51.91.102.146` répond en
`BatchMode` sans agent (`SSH_AUTH_SOCK` vide) — la clé est utilisable
telle quelle depuis la routine. Les deux nuits manquées sont lues ici.

## 1. Les nuits, bout à bout

| | 20/09 | 21/09 | 22/09 | 23/09 |
|---|---|---|---|---|
| durée | 4 740 s | 4 719 s | 4 757 s (+38) | **4 685 s (−72)** |
| garde / marge | 8 100 / 3 360 | 8 100 / 3 381 | 8 100 / 3 343 | **8 100 / 3 415** |
| jalon max | 3 433 Mo | 3 510 Mo | 3 397 Mo (−113) | **3 373 Mo (−24)** |
| swap au pic | 2 350,8 | 2 251,8 | 2 000,0 (−252) | **2 281,6 (+282)** |
| pages sorties | 2 851 116 | 2 401 337 | 2 039 231 (−15 %) | **2 166 535 (+6 %)** |
| pic système | 3 596,0 | 3 614,8 | 3 610,5 | **3 589,3** |
| fenêtre rejouée | 1 805 495 | 1 859 008 | 1 909 457 (+2,7 %) | **1 945 246 (+1,9 %)** |
| `n_57014` | 2 | 1 | 5 | **2** |
| lancement / résultat | timer/success | timer/success | timer/success | **timer/success** |

Les deux nuits sont **comparables** (`lancement=timer`, `exec_status=0`,
05:59:51→07:19:21 puis 05:58:11→07:16:28). Contrôle du 23 :
« 55 relevé(s), 34 comparable(s) ; durée : 10 points, pente −21 s/nuit ;
mémoire : 10 points, pente +24 Mo/nuit ; horizon 30 j ; seuil 2 800 Mo ».

## 2. ✅ Durée : rien à signaler, le contrôle se tait

4 685 s, la plus courte des quatre, et la pente sur 10 points est passée
de **+0 à −21 s/nuit**. Marge 3 415 s sous un garde de 8 100. Le contrôle
n'a émis **que** `bw-pente-memoire` ce matin : aucun ticket de durée n'a
été rouvert ni créé. **KAN-3 reste « Terminé »** — la fermeture du 21/09
tient. Étapes 22→23 : `glissant` 962,7 → 934,0 ; `regime` 1 445,1 →
1 431,8 ; `rejeu` 66,1 → 67,9 ; `stabilite` 219,5 → 219,2.

## 3. ⛔ Mémoire : le correctif a pris, et il est déjà mangé

Les trois franchissements sont toujours là, mais tous en baisse :

```
06:47:09  ⛔ après le rejeu d'archive          : 2 915 Mo  (3 012 le 21)
07:11:05  ⛔ après le score par régime         : 3 017 Mo  (3 071 le 21)
07:14:50  ⛔ après l'oubli de la fenêtre rejouée : 3 373 Mo  (3 510 le 21)
```

**Ce que les chaînes partagées (`af25efb`, première nuit 21→22) ont fait :**

1. **Le correctif a pris.** Ramené à la ligne, le jalon passe de
   **1 979 → 1 866 → 1 818 o/balise-jour rejoué** (−161 o/ligne en deux
   nuits). La sonde du 21 au soir mesurait −252 o/ligne sur la fenêtre
   seule : le bon ordre de grandeur, le jalon portant aussi le reste.
2. **Le jalon ne tombe que de −137 Mo** là où −446 étaient extrapolés —
   exactement §2.4 (tas non rendu au noyau). Le signe attendu était
   ailleurs et il est là : nuit 21→22, **swap au pic −252 Mo et pages
   sorties −15 %**. Le partage a bien pris en production.
3. **Mais la nuit suivante l'annule.** 22→23 : le swap au pic **remonte
   à 2 281,6 Mo**, au-dessus du 21/09, pendant que le jalon continue de
   descendre. La fenêtre a gagné **+86 238 balise-jours en deux nuits
   (+4,6 %)**, dont l'apport de L15-bis déployé le 22 au matin
   (+30 balises ; 11 172 balise-jours écartés au rejeu par `notee_depuis`).
   À 1 818 o/ligne et +1,9 % de fenêtre par nuit, le jalon **remonte de
   ≈ +64 Mo/nuit**. Le partage achète **deux nuits**, pas la semaine
   estimée le 21/09.

**Conclusion** : le levier par ligne marche, sa taille est juste
inférieure à la vitesse de croissance de la fenêtre. Le remède reste la
**ligne en tuple** (§2.6, ≈ −1 030 o/ligne cumulés), avec la mesure
`tuple` vs `namedtuple` à la sonde AVANT de choisir (leçon §2.3).
Rien n'est décidé, rien n'est codé. Aucune remontée de garde proposée.

## 4. Purge et 57014

- **Purge propre les deux nuits** : `purge model_score_zone : rien à
  effacer (?as_of=lt.2026-09-16)`, sans comptage raté ; `model_character :
  rien avant le 2027-02-04 — aucune requête lancée`. Le HTTP 500 du
  comptage (20/09) n'est pas revenu.
- **`n_57014 = 2` le 23** (5 le 22), **tous hors bloc purge** :
  `model_verif_daily [0-999]` à 06:13:10 et `model_verif_event [0-999]`
  à 06:25:03, chacun repris 1/3 et reparti. Aucun motif neuf.
- ⚠️ **Le premier test réel de `delete_par_tranches` n'a toujours pas eu
  lieu** : la borne (`lt.2026-09-16`) ne trouve rien à effacer. Le point
  ouvert du 11/09 reste ouvert.

## 5. Tickets

- **KAN-4 (`bw-pente-memoire`)** — **laissé OUVERT**, commenté
  (HTTP 201, `bw_jira_http`, API v3, `curl -K -`). Aucune des trois
  conditions de fermeture n'est remplie : jalon 3 373 > 2 800, swap au
  pic 2 281,6 ≠ 0, et le contrôle parle encore. Le commentaire porte le
  tableau des trois nuits, le verdict par ligne et le calcul des
  +64 Mo/nuit. Le contrôle de 07:30 avait déjà posé son commentaire
  automatique le même matin.
- **KAN-3 (`bw-pente-duree`)** — « Terminé / done », non touché. Rien
  ne justifie de rouvrir : le contrôle se tait sur la durée.
- ⚠️ **KAN-5 (`bw-purge-57014`) est ROUVERT depuis le 14/09 à 21:41**
  (« Terminé → À faire »), sans un commentaire pour dire pourquoi, et
  sans mise à jour depuis. La minute est la même que les transitions de
  KAN-9 et KAN-11 ce soir-là (21:41–21:42) : **ça ressemble à un faux
  mouvement pendant un tri Jira**, à confirmer par Yann. Conséquence
  concrète : `bw_jira.sh` déduplique sur `statusCategory != Done`, donc
  le prochain échec de purge **commentera KAN-5 au lieu de créer un
  ticket neuf**. Non touché (hors mandat, et une fermeture s'arbitre).
  ⚠️ Le prompt de la routine dit encore « KAN-5 est clos depuis le
  10/09 » : à corriger.

## 6. Hors périmètre, relevé cette nuit

- ✅ **Position : 0 balise CONFIRMÉE** (19 le 21/09, 9 le 22/09) — le
  regel L15-bis a purgé la divergence. 10 balises divergent encore sur
  10 jours lus, aucune confirmée.
- ⚠️ **Mais l'alerte est partie quand même**, texte compris : « Le gel
  des balises et le référentiel vivant ne tombent plus dans la même
  maille AROME pour **0 balise(s)** ». Un cri pour zéro : le seuil de
  déclenchement ne teste pas le compte des confirmées.
- ⚠️ **`push non parti (webhook)`** les **19/09, 22/09 et 23/09** — à
  chaque fois qu'un cri est déposé. La jambe *push* du canal d'urgence
  (celui qui doit réveiller sur OOM ou nuit morte) échoue en silence
  depuis au moins quatre jours. Le mail, lui, part.
- `⚠️ 4 ÉCART(S)` au recalcul indépendant (5 le 21/09), tous du même
  motif : « 0 h appariées ici (< 6) mais la base porte une ligne ».
- `mutations_memoire` : 2 mutations non vues, dette antérieure, inchangée.

## 7. Ce qui a été touché

**VPS** : rien hors le commentaire Jira (`tail` du registre, `journalctl`,
`list-timers`, `controle_quotidien.py --verbeux`, lecture de `bw_jira.sh`,
lectures Jira en GET). Aucun `systemctl`, aucun SQL, aucun rsync.
**Mac** : cette note et son commit local — pas de `git push`.

## 8. Ce qui reste

1. **La mémoire** : décider la ligne en tuple (le seul levier à la bonne
   échelle), après mesure `tuple` vs `namedtuple` à la sonde.
2. **KAN-5** : confirmer le faux mouvement du 14/09 et refermer, ou dire
   ce qui l'a rouvert.
3. **Le webhook push** : canal d'urgence à moitié mort depuis le 19/09.
4. **L'alerte position qui crie pour 0 balise.**
5. `delete_par_tranches` toujours pas éprouvé en vrai.
6. `mutations_memoire` : 2 mutations non vues.

Miroir git : `notes-projet/verdict-pente-23-09.md`, commit local `328a131`, pas de push.
