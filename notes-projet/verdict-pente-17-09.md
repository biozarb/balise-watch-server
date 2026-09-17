# Verdict de pente du 17/09/2026 — durée et mémoire montent ensemble, la marge passe sous les 1 000 s

## 09:30 — routine Balise Watch, lecture seule sur le VPS + deux commentaires Jira

⚠️ **Deuxième session du jour.** La note
`claude/session-controle-et-intervention-17-09.md` (session Cowork de
07:49 → 09:05) couvre le **contrôle scoring/AGRUME et l'intervention**
sur la nuit morte du 16/09 ; elle n'est ni reprise ni remplacée ici.
Cette note-ci couvre le seul **verdict de pente et le traitement de
KAN-3 / KAN-4**, que la première session n'a pas faits.

Étape 0 faite : `git log --since=midnight` → trois commits du jour dans
`balise-watch-server` (`12f7e57`, `aa0a653`, `96ad0b2`, tous de la
session du matin), vide dans `surveillance balise` ; les deux notes
lues ; `notes-projet/README.md` relu. Dernier verdict de pente :
**13/09** — les 14, 15 et 16/09 n'ont eu que le commentaire automatique
de 07:30, aucune relecture humaine.

## 1. Les nuits, bout à bout

| | 13/09 | 14/09 | 15/09 | 16/09 | 17/09 |
|---|---|---|---|---|---|
| durée | 4 062 s | 4 312 s | 4 287 s | **morte 1 398 s** | **4 482 s** |
| marge sous le garde | 1 338 s | 1 088 s | 1 113 s | — | **918 s** |
| jalon max | 3 038 Mo | 3 122 Mo | 3 173 Mo | 1 835 Mo | **3 317 Mo** |
| rejeu d'archive | 2 548 Mo | — | 2 626 Mo | — | **2 754 Mo** |
| swap au pic | 2 042,2 | 2 014,6 | 2 026,1 | 2 042,6 | **2 429,8 Mo** |
| pages sorties | 1 176 609 | 1 379 328 | 1 445 609 | 1 098 033 | **2 183 956** |
| pic système | 3 610,9 | 3 595,3 | 3 596,1 | 3 613,3 | **3 623,5 Mo** |
| `balise_jours_rejeu` | 1 421 406 | 1 476 338 | 1 530 257 | — | **1 640 013** |
| `n_57014` | 6 | 9 | 5 | **11** | 8 |
| lancement / résultat | timer/success | timer/success | timer/success | timer/**exit-code** | timer/**success** |

**La nuit de ce matin est comparable** : `lancement=timer`,
`exec_status=0`, `result=success`. Le verdict est un vrai verdict.
La nuit 15→16, elle, est morte (`Abort: rpc bw_character_avance`,
11 × 57014) : le contrôle l'écarte — « 48 relevé(s), **29 comparable(s)** ».
La série ci-dessus se lit avec ce trou.

## 2. Ce qui va mal — les deux, et par le même porteur

**La durée monte, et ce n'est plus de l'inertie de fenêtre.**
4 482 s, **+195 s** sur la dernière nuit comparable (15/09), **+420 s**
depuis le verdict du 13/09. Marge tombée de 1 338 à **918 s**. Les
quatre nuits comparables post-correctifs (4 062, 4 312, 4 287, 4 482)
sont toutes au-dessus du 11/09 (3 675 s) : les points bruts montent
d'eux-mêmes, l'argument « la fenêtre de 10 relevés porte encore les
nuits pré-correctifs » ne tient plus. Étapes porteuses, 09/09 → 17/09 :
`glissant` 749 → 908 s, `regime` 855 → 1 219 s.

**La mémoire est au plus haut jamais mesuré**, jalon **3 317 Mo**
(+144 sur le 15/09, +279 sur le 13/09), swap au pic **2 429,8 Mo**
(record, +403,7 Mo), pages sorties **+51 % en une nuit**, pic système
3 623,5 Mo sur 3 825 de RAM — **201 Mo de réserve avant l'OOM**
(214 Mo le 13/09). C'est la configuration qui a emporté la nuit du 28/08.

**Le porteur est le même** : la fenêtre rejouée, 1 530 257 → 1 640 013
balise-jours, **+3,5 % par nuit**. Durée et mémoire sont un seul constat,
comme le disait déjà l'en-tête du drop-in au 09/09.

Contrôle de 07:30, texte exact :

```
durée 4 482 s, +75 à +246 s/nuit → franchit le garde (5 400 s) entre le 21/09 et le 30/09
mémoire 3 317 Mo (plancher : 2 430 Mo de swap au pic), +51 à +151 Mo/nuit
  → AU-DESSUS du seuil (2 800 Mo) depuis le 09/09
ⓘ 48 relevé(s), 29 comparable(s) ; durée : 10 points, pente +75 s/nuit ;
  mémoire : 10 points, pente +51 Mo/nuit ; horizon 30 j ; seuil 2800 Mo
```

## 3. ⛔ Le chien de garde est écrit mais PAS déployé

La session du matin a écrit et commité (`12f7e57`) la remontée
**90 → 135 min** dans l'en-tête de `10-timeout-s3.conf`, avec sa mesure.
Le VPS, lui, répond toujours :

```
Environment=BW_MODEL_VERIF_MAX_MINUTES=90
TimeoutStartUSec=1h 40min
```

**Donc ce soir la nuit tourne sur un garde de 5 400 s avec 918 s de
marge.** À la pente basse (+75 s/nuit) cela laisse une douzaine de
nuits ; **à la pente haute (+246 s/nuit), quatre**. Le déploiement est
à la main de Yann — la routine ne remonte jamais le garde, et le
classificateur bloque de toute façon toute écriture sur le VPS
(cf. la note du matin).

## 4. Correctif par correctif

**`delete_par_tranches` : confirmé, et la question du 13/09 §6 est
tranchée.** Ce matin, 118 528 lignes effacées en 18 tranches, **aucun
57014 dans le bloc purge**. La purge mord, la rétention se comporte
comme prévu. (Déjà relevé par la session du matin ; recoupé ici.)

**L'élagage de `units` : toujours pas le levier.** Rien de neuf — la
sonde donne −124 Mo, pas −1 500. Les gains sont dans la STRUCTURE
(chaînes partagées −316 Mo, ligne en tuple −970 Mo cumulés), pas dans
le nombre de clés. Rien n'est décidé.

**Les correctifs du matin (`12f7e57`) ne sont pas encore jugeables** :
SEUIL_ALERTE=1, RPC_LOT 5000 → 2000 avec coupe en deux, événements
rejouables. Ils sont en local, non déployés — **la nuit 17→18 tournera
encore sur l'ancien code**. Leur premier test réel dépend du
déploiement.

## 5. Les tickets — les deux commentés, les deux laissés OUVERTS

**KAN-4 (`bw-pente-memoire`)** — non fermé. Aucune des trois conditions
n'est remplie : le jalon n'est pas retombé (record), le swap au pic
n'est pas voisin de zéro (2 430 Mo, record), le contrôle parle toujours.
Commentaire posté (HTTP 201) : la série des cinq nuits, les 201 Mo de
réserve, le rappel que les leviers restants sont structurels.

**KAN-3 (`bw-pente-duree`)** — non fermé : la durée AUGMENTE.
Commentaire posté (HTTP 201) : la série avec le trou du 16/09, la fin de
l'argument d'inertie, les étapes porteuses, et la **proposition du script
recopiée mais NON LANCÉE** (90 → 135 min), assortie du constat que le
drop-in est écrit et commité mais **pas déployé**.

⚠️ Les deux tickets portaient déjà le commentaire automatique de 07:30
(le script a son propre jeton `cri.jira.<motif>`). Les commentaires
ci-dessus sont ceux de la routine, posés par `bw_jira_http` du canal
maison (API v3, `curl -K -`, jeton jamais lu par valeur ni exposé dans
`ps`). Aucune transition jouée.

**Motif neuf** — aucun. Les 8 × 57014 de la nuit viennent de
`model_verif_daily [50000-50999]` (×2), `rpc/bw_character_avance` (×4)
et `model_verif_event [0-999]` (×2) ; **aucun du bloc purge**. Le
contrôle est muet sur `bw-purge-57014`, KAN-5 reste clos.

## 6. Ce qui reste

1. **Déployer, ou décider de ne pas déployer.** Le garde à 135 min et
   les trois commits du matin sont en local. Tant qu'ils y restent, la
   marge de 918 s court toute seule.
2. **La mémoire reste le sujet de fond** : 201 Mo de réserve, fenêtre
   +3,5 %/nuit. Décision à prendre entre chaînes partagées (−316 Mo) et
   ligne en tuple (−970 Mo cumulés).
3. **`mutations_memoire` : 2 mutations non vues**, dette antérieure au
   lot du 11/09, toujours à instruire.
4. Les points ouverts de la note du matin (R2 à 91 %, recalcul
   indépendant à 7 écarts, fraîcheur de la grille AGRUME,
   `balise-entretien.service` divergent, Healthchecks du 16/09) ne sont
   **pas** repris ici : ils appartiennent à cette note-là.

## 7. Ce qui a été touché

**Sur le VPS : rien.** Lecture seule — `tail` du registre, `journalctl`,
`systemctl list-timers` / `show`, `cat` du drop-in, `controle_quotidien.py
--verbeux`, `free`. Aucun service démarré ou rechargé, aucun SQL joué,
aucun `rsync`, rien écrit dans `~/balise-watch` ni dans `/etc`. Les seuls
écrits : les deux commentaires Jira. Les scripts de travail (sur le Mac,
`/tmp`) et le dossier temporaire du VPS ont été effacés.

**Sur le Mac** : cette note, son miroir dans le projet Claude, et un
commit local — **pas de `git push`**.
