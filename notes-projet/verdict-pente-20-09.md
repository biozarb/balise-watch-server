# Verdict de pente du 20/09/2026 — la nuit revit et la durée est PLATE (+1 s), mais la mémoire bat son record et franchit le seuil trois fois

## 12:10 — routine Balise Watch, lecture seule sur le VPS + deux commentaires Jira

Étape 0 faite : `git log --since=midnight` **vide dans les deux dépôts**
(dernier commit `6c4f780`, 19/09). Aucune autre session n'a tourné ce
matin. `notes-projet/README.md` relu.

⚠️ **Anomalie de la veille** : le miroir git
`notes-projet/verdict-pente-19-09.md` existe, mais le document projet
`claude/verdict-pente-19-09.md` **est absent de la liste du projet**, et
le miroir lui-même s'arrête au milieu d'une phrase (28 lignes, fin sur
« ⛔ Non vérifié en base »). Le run du 19/09 a donc été coupé avant
d'écrire dans le projet. Rien n'a été écrasé — c'est le filet git qui a
tenu. Repris tel quel ici, non réparé.

## 1. Les nuits, bout à bout

| | 17/09 | 18/09 | 19/09 | 20/09 |
|---|---|---|---|---|
| durée | 4 482 s | 4 739 s | **morte 1 767 s** | **4 740 s** |
| garde / marge | 5 400 / 918 s | 8 100 / 3 361 s | 8 100 / — | **8 100 / 3 360 s** |
| jalon max | 3 317 Mo | 3 385 Mo | 1 872 Mo | **3 433 Mo** |
| swap au pic | 2 429,8 Mo | 2 163,7 Mo | 2 200,1 Mo | **2 350,8 Mo** |
| pages sorties | — | 2 099 718 | 1 401 347 | **2 851 116** |
| pic système | 3 623,5 Mo | 3 617,5 Mo | 3 605,0 Mo | **3 596,0 Mo** |
| réserve avant OOM | 201 Mo | 207,5 Mo | — | **229 Mo** |
| `balise_jours_rejeu` | 1 640 013 | 1 694 837 | — | **1 805 495** |
| `n_57014` | 8 | 4 | 13 | **2** |
| lancement / résultat | timer/success | timer/success | timer/**exit-code** | timer/**success** |

**La nuit 19→20 est comparable** : `lancement=timer`, `exec_status=0`,
`result=success`, 05:57:45 → 07:17:06. Le verdict est un vrai verdict.
La nuit 18→19 est morte et écartée — le contrôle le dit : « 52 relevé(s),
**31 comparable(s)** ».

## 2. ✅ Le correctif du 19/09 tient : la pagination sur `day`

Le commit `0d108d7` (19/09, « une lecture filtrée sur `day` pagine
désormais sur `day` ») a passé son premier test réel. La nuit 18→19
mourait à 06:28:08 sur `model_verif_event [0-999]` après trois reprises
(`reprise 1/2`, `2/2`, `3/2`) ; cette nuit, la même lecture repart **dès
la reprise 1/3** :

```
06:13:20  ⚠️ model_verif_daily [0-999] : HTTP 500 … 57014 — reprise 1/3
06:24:00  ⚠️ model_verif_event [0-999] : HTTP 500 … 57014 — reprise 1/3
```

Et la journée est notée : `lignes_score_zone` 127 675,
`lignes_glissant` 10 667, `lignes_regime` 117 008, `balise_jours_rejeu`
1 805 495. Aucun de ces champs n'était présent le 19/09. **`n_57014`
tombe à 2**, le plus bas de la série, et aucun ne vient du bloc purge :
le contrôle reste muet sur `bw-purge-57014`, **KAN-5 reste clos**.

Au passage, les reprises sont bien passées de `/2` à `/3` : le lot
`12f7e57` du 17/09 est lui aussi déployé.

## 3. ✅ La durée : plate, et le garde est déployé

**4 740 s contre 4 739 s le 18/09 : +1 s.** Pour la première fois
depuis le 11/09, deux nuits comparables consécutives sont au même
niveau. Le garde est à **8 100 s** (135 min) dans le registre depuis le
17/09 : le drop-in `10-timeout-s3.conf` écrit ce jour-là **est
déployé**, et la marge est remontée de 918 à **3 360 s**.

⚠️ **Mais le contrôle s'est tu sur la durée, et ce silence se lit mal.**
À 07:31 il n'a commenté que KAN-4. Il mesure pourtant toujours une pente
de **+64 s/nuit sur 10 points** ; avec 3 360 s de marge le franchissement
tombe vers **52 nuits**, au-delà de l'horizon de 30 jours, et le script
se tait par construction. **C'est le garde qui a bougé, pas la durée.**

Et la fenêtre de 10 relevés porte encore des nuits pré-correctifs, plus
deux nuits mortes écartées (16/09, 19/09). L'argument d'inertie, que le
17/09 déclarait mort, redevient partiellement vrai — mais dans l'autre
sens : il masque désormais autant qu'il expliquait.

Étapes, 18/09 → 20/09 : `glissant` 953,7 → 967,2 s (+13,5),
**`regime` 1 254,7 → 1 411,6 s (+156,9)**, `rejeu` 61,1 → 61,3,
`stabilite` 215,3 → 252,7. Le score par régime monte toujours.

## 4. ⛔ La mémoire : record battu, et trois franchissements au lieu d'un

Jalon max **3 433 Mo** (« l'oubli de la fenêtre rejouée ») — **record**,
+48 Mo sur le 18/09, +116 sur le 17/09. Swap au pic **2 350,8 Mo**
(+187,1 en une nuit). Pages sorties **2 851 116**, **+36 %**.

**Trois franchissements du seuil de 2 800 Mo dans la même nuit**, contre
un seul le 18/09 :

```
06:46:26  ⛔ après le rejeu d'archive          : 2 902 Mo
07:10:02  ⛔ après le score par régime         : 3 068 Mo
07:14:25  ⛔ après l'oubli de la fenêtre rejouée : 3 433 Mo
```

Le porteur est inchangé : la fenêtre rejouée passe de 1 694 837 à
**1 805 495** balise-jours, **+6,5 %** d'une nuit comparable à l'autre —
presque le double du +3,5 % relevé le 17/09.

Seule éclaircie, et elle est paradoxale : le **pic système baisse**
(3 623,5 → 3 617,5 → 3 596,0 Mo), donc la réserve avant l'OOM remonte à
**229 Mo** sur 3 825 de RAM. Le processus prend plus de mémoire, mais
l'ensemble de la machine en occupe un peu moins. Ce n'est pas une marge
gagnée par le correctif ; c'est du bruit système.

Contrôle de 07:31, texte exact :

```
mémoire 3 433 Mo (plancher : 2 351 Mo de swap au pic), +24 à +84 Mo/nuit
  → AU-DESSUS du seuil (2 800 Mo) depuis le 09/09
ⓘ 52 relevé(s), 31 comparable(s) ; durée : 10 points, pente +64 s/nuit ;
  mémoire : 10 points, pente +24 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
```

## 5. ⚠️ Motif neuf, non ticketé : `compte model_score_zone : HTTP 500`

Nouveau dans les incidents du registre, jamais vu avant ce matin :

```
07:16:42  ⚠️ compte model_score_zone : HTTP 500 —
07:16:42  → purge model_score_zone : ? ligne(s) effacée(s) en 27 tranche(s)
```

La purge **a tourné** — 27 tranches, contre 18 le 17/09 — mais le
comptage préalable a expiré, d'où le `?` au lieu d'un nombre.
Cause probable : la table a grossi et le `count` dépasse le
`statement_timeout`, comme les lectures que `0d108d7` vient de corriger
par la pagination. **C'est cosmétique tant que la purge mord**, et rien
n'indique qu'elle ne mord pas. Le contrôle n'a ouvert aucun ticket pour
ce motif, et **je n'en ai pas ouvert non plus** : à toi de dire si ça
mérite son `bw-compte-57014`.

`purge model_character` : rien avant le 2027-02-04, aucune requête
lancée — normal, rétention 180 j.

## 6. Les tickets — les deux commentés, les deux laissés OUVERTS

**KAN-4 (`bw-pente-memoire`)** — non fermé, commentaire posté
(HTTP 201). Aucune des trois conditions n'est remplie : le jalon n'est
pas retombé (il bat son record), le swap au pic n'est pas voisin de zéro
(2 351 Mo), le contrôle parle toujours. Commentaire : la série des
quatre nuits, les trois franchissements, les 229 Mo de réserve, le
rappel que les leviers restants sont structurels.

**KAN-3 (`bw-pente-duree`)** — non fermé, commentaire posté (HTTP 201).
⛔ **La tentation était de le fermer** : la durée est plate et le
contrôle se tait. Les deux raisons sont fausses. Le silence vient de la
remontée du garde, pas de la disparition de la pente (+64 s/nuit,
toujours mesurée) ; et une seule nuit plate ne fait pas une tendance.
Commentaire : la durée à +1 s, le garde déployé, l'explication du
silence, les étapes porteuses, le correctif `day` validé. **Aucune
remontée du garde proposée** : le script n'en formule pas puisqu'il est
muet sur la durée.

⚠️ KAN-4 portait déjà le commentaire automatique de 07:31 (jeton
`cri.jira.bw-pente-memoire`). Les deux commentaires ci-dessus sont ceux
de la routine, posés par `bw_jira_http` (API v3, `curl -K -`, jeton
jamais lu par valeur ni exposé dans `ps`). **Aucune transition jouée.**
KAN-3 et KAN-4 sont tous deux au statut « À faire ».

## 7. Ce qui reste

1. **La mémoire est le seul sujet qui empire.** Record, trois
   franchissements, fenêtre rejouée à +6,5 %/nuit. La décision entre
   chaînes partagées (−316 Mo) et ligne en tuple (−970 Mo cumulés) est
   toujours à prendre, et elle ne s'améliorera pas en attendant.
2. **Surveiller la durée deux ou trois nuits de plus.** Le +1 s peut
   être le premier vrai palier depuis le 11/09, ou un hasard. Trois
   nuits comparables d'affilée trancheront.
3. **Décider pour `compte model_score_zone : HTTP 500`** (§5) : ticket
   ou pas.
4. **Réparer le trou du 19/09** : `claude/verdict-pente-19-09.md` manque
   côté projet, et le miroir est tronqué. Ni l'un ni l'autre n'a été
   touché ici.
5. **`mutations_memoire` : 2 mutations non vues**, dette antérieure au
   lot du 11/09, toujours à instruire.
6. Hors périmètre de cette note, relevé au passage dans le journal de la
   nuit : `⛔ position : 16 balise(s) divergent du gel, dont 8
   CONFIRMÉE(S)`, et `⚠️ 5 ÉCART(S)` au recalcul indépendant (contre 7
   le 17/09). Non instruits.

## 8. Ce qui a été touché

**Sur le VPS : rien.** Lecture seule — `tail` du registre, `journalctl`,
`systemctl list-timers`, `free`, `controle_quotidien.py --verbeux`, et
la lecture de `tools/bw_jira.sh`. Aucun service démarré ou rechargé,
aucun SQL joué, aucun `rsync`, rien écrit dans `~/balise-watch` ni dans
`/etc`. Les seuls écrits : les **deux commentaires Jira**. Le dossier de
travail temporaire (`/tmp/bw-jira.XXXXXX`, 700) a été effacé.

**Sur le Mac** : cette note, son miroir dans le projet Claude
(`claude/verdict-pente-20-09.md`), et un commit local — **pas de
`git push`**.
