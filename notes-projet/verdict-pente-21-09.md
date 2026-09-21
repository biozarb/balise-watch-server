# Verdict de pente du 21/09/2026 — la durée tient son palier (pente +0 s/nuit), la mémoire bat encore son record (3 510 Mo)

## 18:20 — routine Balise Watch (lancée en retard : prévue 07:01 UTC, partie 16:13 UTC), lecture seule sur le VPS + deux commentaires Jira

Étape 0 faite : `git log --since=midnight` **vide dans les deux dépôts**
(derniers commits `7135de7` et `7c136db`, 20/09). Pas de note du jour côté
projet, aucune autre session ce matin. `notes-projet/README.md` relu.
Le trou du 19/09 a été rattrapé côté git hier (`7135de7`, miroir tronqué
commité tel quel) ; `claude/verdict-pente-19-09.md` manque toujours côté projet.

## 1. Les nuits, bout à bout

| | 18/09 | 19/09 | 20/09 | 21/09 |
|---|---|---|---|---|
| durée | 4 739 s | morte 1 767 s | 4 740 s | **4 719 s** (−21) |
| garde / marge | 8 100 / 3 361 s | 8 100 / — | 8 100 / 3 360 s | **8 100 / 3 381 s** |
| jalon max | 3 385 Mo | 1 872 Mo | 3 433 Mo | **3 510 Mo** (+77) |
| swap au pic | 2 163,7 Mo | 2 200,1 Mo | 2 350,8 Mo | **2 251,8 Mo** (−99) |
| pages sorties | 2 099 718 | 1 401 347 | 2 851 116 | **2 401 337** (−16 %) |
| pic système | 3 617,5 Mo | 3 605,0 Mo | 3 596,0 Mo | **3 614,8 Mo** |
| réserve avant OOM | 207,5 Mo | — | 229 Mo | **≈ 210 Mo** |
| `balise_jours_rejeu` | 1 694 837 | — | 1 805 495 | **1 859 008** (+3,0 %) |
| `n_57014` | 4 | 13 | 2 | **1** |
| lancement / résultat | timer/success | timer/exit-code | timer/success | **timer/success** |

**La nuit 20→21 est comparable** : `lancement=timer`, `exec_status=0`,
05:55:56 → 07:14:45. Le contrôle : « 53 relevé(s), 32 comparable(s) ».

## 2. ✅ Durée : palier confirmé, la pente s'est éteinte

4 719 s, **troisième nuit comparable d'affilée au même niveau**
(4 739 / 4 740 / 4 719). Surtout, le contrôle mesure désormais une pente
de **+0 s/nuit sur 10 points** (hier +64). Hier le silence venait du garde
remonté ; aujourd'hui il vient aussi de la durée elle-même.

Étapes 20→21 : `glissant` 967,2 → 948,3 ; `regime` 1 411,6 → **1 439,3**
(+27,7, en hausse mais loin des +156,9 de la veille) ; `rejeu` 61,3 → 62,0 ;
`stabilite` 252,7 → 275,7.

## 3. ⛔ Mémoire : nouveau record, toujours trois franchissements

```
06:44:26  ⛔ après le rejeu d'archive          : 3 012 Mo
07:08:30  ⛔ après le score par régime         : 3 071 Mo
07:13:17  ⛔ après l'oubli de la fenêtre rejouée : 3 510 Mo
```

Le porteur ne change pas : la fenêtre rejouée gagne encore +3,0 %
(1 859 008 balise-jours). Le swap au pic et les pages sorties reculent,
mais la réserve avant OOM retombe à ≈ 210 Mo. Contrôle de 07:30 :
« +24 à +77 Mo/nuit → AU-DESSUS du seuil (2 800 Mo) depuis le 09/09 ».

## 4. Purge et 57014

- Le `compte model_score_zone : HTTP 500` d'hier **n'est pas revenu** :
  `purge model_score_zone : rien à effacer (?as_of=lt.2026-09-14)`, sans
  comptage raté. Motif toujours non ticketé, et désormais sans objet ce soir.
- `n_57014 = 1`, hors bloc purge (`model_verif_daily [0-999]`, reprise 1/3,
  repartie). KAN-5 reste clos.

## 5. Tickets — les deux commentés (HTTP 201), les deux laissés OUVERTS

- **KAN-4** : aucune condition de fermeture remplie. Commentaire : chiffres,
  trois franchissements, réserve, leviers structurels à décider.
- **KAN-3** : ⚠️ **fermeture proposée à Yann, non jouée.** Trois nuits
  plates et pente +0 : les chiffres la défendent. Réserve : `regime` monte
  encore. Aucune remontée du garde proposée.

Commentaires posés par `bw_jira_http` (API v3, `curl -K -`), script passé
par `ssh … 'bash -s'` puis effacé ; aucun jeton `cri.jira.*` écrit, aucune
transition. Statut des deux : « À faire ».

## 6. Ce qui reste

1. **Décider KAN-3** (fermer ou attendre une 4e nuit).
2. **La mémoire** : chaînes partagées (−316 Mo) / ligne en tuple (−970 Mo) /
   `--regime-days`. Seul sujet qui empire.
3. `claude/verdict-pente-19-09.md` toujours absent du projet.
4. `mutations_memoire` : 2 mutations non vues (dette).
5. Hors périmètre, relevé dans le journal : `⛔ position : 19 balise(s)
   divergent du gel, dont 8 CONFIRMÉE(S)` (16 hier) ; `⚠️ 5 ÉCART(S)` au
   recalcul indépendant (inchangé). Non instruits.

## 7. Ce qui a été touché

**VPS** : rien hors Jira (`tail` du registre, `journalctl`, `list-timers`,
`free`, `controle_quotidien.py --verbeux`, lecture de `bw_jira.sh`).
**Mac** : cette note et son commit local — pas de `git push`.

## 18:45 — session Cowork avec Yann : KAN-3 fermé, trou du 19/09 comblé, avis sur la mémoire

- **KAN-3 fermé** sur décision de Yann : commentaire de clôture (HTTP 201),
  transition 41 « Terminé » (HTTP 204), statut relu `Terminé / done`. Si la
  pente revient, `bw_jira.sh` ouvrira un ticket neuf (sa recherche ignore
  la catégorie Done). **KAN-4 reste ouvert.**
- **Trou du 19/09** : `claude/verdict-pente-19-09.md` créé côté projet ; le
  miroir garde le texte tronqué d'origine intact, suivi d'une
  reconstitution marquée comme telle (sources : registre,
  `session-lecture-day-19-09.md`, `verdict-pente-20-09.md`).
- **Levier mémoire — avis donné à Yann, rien de codé** :
  1. d'abord les **chaînes partagées** dans `replay_window` (l. ~3154,
     `memo.setdefault` sur les valeurs `str`, `unit` compris) : aucun
     lecteur touché, −253 o/ligne mesurés le 11/09, soit ≈ −470 Mo au
     prorata de la fenêtre d'aujourd'hui (1 859 008 lignes, non re-mesuré).
     Ne suffit pas seul : à +77 Mo/nuit, ça achète ~une semaine ;
  2. ensuite la **ligne en tuple** (≈ −1 030 o/ligne cumulés, ≈ −1,9 Go
     au prorata) : le vrai remède, mais `_case_rows`, `regime_scores`,
     `stability_report`, `bilan_dispersion` passent à l'accès par index —
     mesurer `tuple` vs `namedtuple` à la sonde AVANT de choisir (leçon §2.3) ;
  3. `--regime-days` seulement en frein d'urgence : la fenêtre est à
     30 jours fixes, elle grossit parce que chaque journée porte plus de
     lignes ; raccourcir la fenêtre ne coupe qu'une fois et change ce que
     le score par régime mesure.
  ⚠️ §2.4 : le jalon ne baissera pas au prorata (tas non rendu au noyau) ;
  le signe attendu est d'abord le swap au pic qui s'effondre.

## 19:15 — session Cowork avec Yann : chaînes partagées codées, DÉPLOYÉES et poussées

Sur feu vert explicite de Yann (« Déployer + push »).

- **Code** (`af25efb`, dépôt serveur) — `replay_window` : un seul
  `memo: dict[str, str]` pour TOUTE la fenêtre (pas un par journée), et
  après l'élagage chaque valeur `str` de la ligne pointe vers l'exemplaire
  partagé. L'élagage (`if k in CLES_REJEU`) est laissé tel quel, ligne
  comprise (les mutations du 10/09 la visent). Aucun lecteur touché.
  `unit` passe par le même partage (elle est dans la ligne), pas de ligne
  à part : elle aurait fait une mutation équivalente.
- **Banc** : `test_21_09_la_fenetre_rejouee_partage_ses_chaines` regarde
  l'IDENTITÉ des objets (le score, lui, ne bouge pas) — avec un témoin qui
  prouve d'abord que `json.loads` seul ne partage pas. Mac **1 130/0**,
  VPS **1 128/0** (le même écart de 2 que d'habitude).
- **Mutations** (`mutations_memoire.py`) : 2 nouvelles, toutes deux VUES
  (partage retiré ; dictionnaire remis à zéro chaque journée). Les 2 non
  vues d'avant (n° 2 motif introuvable, n° 5 `gc.collect`) : inchangées, dette.
- **Mesuré ce soir sur le VPS** (sonde, 3 journées, lecture seule) :
  `telquel` 2 303 o/ligne → `memo` 2 051 o/ligne, **−252 o/ligne**, soit
  4 083 → 3 637 Mo extrapolés sur 1 859 008 lignes (**≈ −446 Mo**). La
  sonde partage par journée ; le code partage sur la fenêtre, donc au
  moins autant.
- **Déployé** : `rsync model-verif/` → 3 fichiers seulement
  (`score.py`, `test_score.py`, `mutations_memoire.py`), sha256 identiques
  des deux côtés (`score.py` `bb1e42f4…126b`). Aucun service touché ;
  `bw-model-score.timer` prendra le code le **mar. 22/09 à 05:59:47 CEST**.
- **Poussé** : `0d108d7..af25efb` (inclut les notes `notes-projet/` des
  20 et 21/09).

**À lire demain matin** : le swap au pic (2 251,8 Mo ce matin) et les
pages sorties doivent chuter nettement ; le jalon baissera moins que
−446 Mo (§2.4). Si le swap ne bouge pas, le partage n'a pas pris et il
faut le mesurer en production avant d'attaquer la ligne en tuple.
