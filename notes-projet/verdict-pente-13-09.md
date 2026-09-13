# Verdict de pente du 13/09/2026 — la mémoire repart au plus haut, la durée aussi

## 13:40 — routine Balise Watch, lecture seule sur le VPS + deux commentaires Jira

⚠️ **Cette note couvre DEUX nuits.** Aucune session n'a tourné le
12/09 : pas de `claude/verdict-pente-12-09.md`, aucun commit du 12/09
dans les deux dépôts (dernier commit `4b6216e`, 11/09 23:09). La nuit
11→12 — celle qui devait être « le vrai verdict » selon la note du
11/09 — n'a donc jamais été relue par personne. Elle l'est ici.

Étape 0 faite : `git log --since=midnight` vide dans
`balise-watch-server` **et** dans `surveillance balise` ; note du jour
inexistante ; note de la veille (11/09) lue en entier. Pas de doublon,
pas d'écrasement.

## 1. Les quatre nuits, bout à bout

| | 09→10 (10/09) | 10→11 (11/09) | 11→12 (12/09) | 12→13 (13/09) |
|---|---|---|---|---|
| durée | 3 860 s | 3 675 s | 3 987 s | **4 062 s** |
| marge sous le garde | 1 540 s | 1 725 s | 1 413 s | **1 338 s** |
| jalon max | 2 897 Mo | 2 856 Mo | 2 838 Mo | **3 038 Mo** |
| porteur du jalon | score par régime | fenêtre rejouée | fenêtre rejouée | fenêtre rejouée |
| `rejeu d'archive` | 2 373 Mo | 2 431 Mo | 2 516 Mo | 2 548 Mo |
| swap au pic | 2 048,0 Mo | 1 759,7 Mo | **651,2 Mo** | **2 042,2 Mo** |
| pages sorties | — | 589 276 | 321 714 | **1 176 609** |
| pic système | 3 379,2 Mo | 3 528,1 Mo | 3 573,2 Mo | **3 610,9 Mo** |
| `n_57014` | 7 | 4 | 5 | 6 |
| `lignes_score_zone` | 122 691 | 126 071 | 126 441 | 126 668 |
| `balise_jours_rejeu` | 1 253 232 | 1 309 861 | 1 365 943 | 1 421 406 |
| lancement / résultat | timer / success | timer / **exit-code** | timer / success | timer / success |

Les deux dernières nuits sont `lancement=timer`, `exec_status=0`,
`result=success` : elles sont comparables, et le contrôle ne répète plus
les chiffres de la veille comme le 11/09. **Le verdict de ce matin est
un vrai verdict.**

## 2. Correctif par correctif

**Le `NameError` de l'étape 6 (commit `14381b2`) : réglé.** Deux nuits
consécutives en `success`, l'étape 6 tourne, `bw-model-score.service` est
repassé `Result=success / ExecMainStatus=0`. Le voyant Healthchecks est
reparti au vert avec le ping du 12/09 ~07:03, comme prévu.

**`delete_par_tranches` : premier test réel PASSÉ, et personne ne l'avait
vu.** Nuit 11→12, borne `< 09-05` :

```
2026-09-12T07:03:32  → purge model_score_zone : 96576 ligne(s) effacée(s) en 18 tranche(s)
```

96 576 lignes, 18 tranches, **aucun 57014 dans le bloc purge** — c'est
exactement ce que le lot du 10/09 cherchait à obtenir après le constat
que `limit` est ignoré par cette base. Le correctif tient.

**L'élagage de `units` : toujours pas le levier.** Rien de neuf depuis
le 11/09 ; la sonde (`bc018a0`) donne −124 Mo, pas −1 500. Les chiffres
de cette nuit le confirment par l'absurde : la fenêtre a grossi de 4,1 %
et la mémoire a suivi.

## 3. Ce qui va mal : la mémoire, et elle va plus mal qu'avant

La nuit 11→12 avait donné le premier signe encourageant du ticket :
**swap au pic divisé par 2,7** (1 759,7 → 651,2 Mo) et jalon en légère
baisse. La nuit 12→13 a effacé ce gain en une seule fois :

- jalon **3 038 Mo**, la valeur la plus haute jamais enregistrée,
  +200 Mo sur la veille et 238 Mo au-dessus du seuil de 2 800 ;
- swap au pic **2 042,2 Mo**, revenu au niveau du 10/09 ;
- pages sorties **1 176 609**, soit 3,7 × celles de la veille ;
- pic système **3 610,9 Mo sur 3 825 Mo de RAM** — **214 Mo de
  réserve**. C'est la configuration qui a emporté la nuit du 28/08 par
  OOM. Le run a fini, mais il est passé près.

⚠️ **Ce n'est pas un défaut neuf.** La fenêtre rejouée grossit d'environ
4 % par nuit (`balise_jours_rejeu` +4,3 % puis +4,1 %) et la mémoire suit
mécaniquement : 2 838 × 1,041 = 2 954 Mo, l'écart restant tient dans le
bruit d'une nuit. La croissance connue, simplement, continue — et elle
est désormais assez haute pour que le swap explose. Le §2.4 de l'enquête
l'avait annoncé : le vrai symptôme, c'est le SWAP, pas le jalon.

## 4. La durée : elle monte, et ce n'est plus de l'inertie de fenêtre

4 062 s, +75 s sur la veille, **+387 s sur le 11/09**. Marge tombée de
1 725 à 1 338 s en deux nuits. Le contrôle de 07:30 :

```
durée 4 062 s, +64 à +223 s/nuit → franchit le garde (5 400 s) entre le 19/09 et le 05/10
ⓘ 44 relevé(s), 26 comparable(s) ; durée : 10 points, pente +64 s/nuit ;
  mémoire : 10 points, pente +26 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
```

La fenêtre de 10 points porte encore des nuits pré-correctifs — mais
contrairement au 11/09, **la hausse est confirmée par les points bruts** :
les deux nuits post-correctifs (3 987 puis 4 062 s) sont toutes deux
au-dessus du 11/09. Les étapes qui portent le temps suivent la fenêtre :
`glissant` 747 → 878 s, `regime` 930 → 1 042 s. Durée et mémoire ont le
même porteur.

## 5. Les tickets — les deux commentés, les deux laissés OUVERTS

**KAN-4 (`bw-pente-memoire`)** — non fermé, et de loin. Aucune des trois
conditions n'est remplie : le jalon n'est pas retombé (il est au plus
haut), le swap au pic n'est pas voisin de zéro (2 042 Mo), le contrôle
parle toujours. Commentaire posté (HTTP 201) avec la série des quatre
nuits, la réserve de 214 Mo avant l'OOM, et le rappel que les vrais
leviers sont structurels (chaînes partagées −316 Mo, ligne en tuple
−970 Mo cumulés), rien n'étant décidé.

**KAN-3 (`bw-pente-duree`)** — non fermé : la durée AUGMENTE. Commentaire
posté (HTTP 201) avec la série, la distinction inertie / hausse réelle,
et la **proposition du script recopiée mais NON LANCÉE** (10-timeout-s3.conf,
90 → 130 min, à écrire dans l'en-tête puis à déployer). ⛔ Le chien de
garde est inchangé à 5 400 s — c'est Yann qui lance, pas la routine.

**Motif neuf** — aucun. Le contrôle est muet sur `bw-purge-57014`, et
cette fois ce n'est **pas** un faux négatif comme le 11/09 : le bloc
purge a bien tourné les deux nuits. Les 6 × 57014 de cette nuit viennent
de `rpc/bw_character_avance` (×5) et `model_verif_event [0-999]` (×1),
aucun du bloc purge. KAN-5 reste clos.

## 6. Une question ouverte sur la purge — à instruire, pas à conclure

Cette nuit, borne `< 09-06` :

```
2026-09-13T07:06:46  ⓘ purge model_score_zone : rien à effacer (?as_of=lt.2026-09-06)
```

Or la veille, borne `< 09-05`, la purge avait effacé 96 576 lignes. Si la
rétention est bien de 7 jours et que les tranches du 12/09 n'ont emporté
que la journée 09-04, la journée **09-05 aurait dû être effacée ce
matin** — et elle ne l'a pas été. Deux lectures possibles, aucune
vérifiée :

1. les 18 tranches du 12/09 ont emporté 09-04 **et** 09-05 (donc une
   journée de plus que la borne ne l'autorise — un décalage d'un cran
   dans la boucle de tranches) ;
2. la journée 09-05 n'existait pas dans `model_score_zone`.

⛔ Trancher demande une lecture SQL de `model_score_zone`, que la routine
n'a pas le droit de jouer. À regarder demain matin : la borne sera
`< 09-07`, et si la purge dit encore « rien à effacer », c'est la
lecture 1 qui est vraie et il y a un décalage à corriger. Ce n'est pas
urgent — la purge efface trop tôt, pas trop tard, donc rien ne
s'accumule.

## 7. Ce qui reste

1. **La mémoire est le sujet, et il devient pressant** : 214 Mo de
   réserve avant l'OOM, et la fenêtre grossit de 4 % par nuit. À la
   même pente, la marge est mangée en deux à trois nuits. Décision à
   prendre entre les chaînes partagées (−316 Mo, sans rien retirer à
   personne) et la ligne en tuple (−970 Mo cumulés, quatre lecteurs à
   convertir).
2. **Chien de garde 90 → 130 min** : proposé par le script, recopié dans
   KAN-3, **non lancé**. À l'arbitrage de Yann.
3. **La purge du 09-05** (§6) — à confirmer demain.
4. **`mutations_memoire` : 2 mutations non vues**, dette antérieure au
   lot du 11/09, toujours à instruire.
5. Les commentaires du 11/09 sur KAN-3 et KAN-4, qui parlaient en fait
   de la nuit 09→10, sont maintenant suivis d'un commentaire juste ; la
   mise au point n'a pas été écrite séparément, elle est implicite dans
   la série des quatre nuits.

## 8. Ce qui a été touché

**Sur le VPS : rien.** Lecture seule — `tail` du registre, `journalctl`,
`systemctl list-timers` / `show`, `controle_quotidien.py --verbeux`,
`sed` sur `bw_jira.sh`, `free`. Aucun service démarré ou rechargé, aucun
SQL joué, aucun `rsync`, rien écrit dans `~/balise-watch` ni dans `/etc`.
Le seul écrit : les deux commentaires Jira, posés par `bw_jira_http` du
canal maison (API v3, `curl -K -`, jeton jamais lu par valeur ni exposé
dans `ps`). Le script de travail et son dossier temporaire ont été
effacés.

**Sur le Mac** : cette note, son miroir dans le projet Claude, et un
commit local — **pas de `git push`**.
