# Verdict de pente du 11/09/2026 — la nuit 10→11 a échoué, puis corrigée et redéployée

Session Cowork, Desktop Commander + ssh depuis le Mac. Deux temps :
d'abord un constat en LECTURE SEULE (rien touché, aucun ticket) ; puis,
sur feu vert explicite de Yann, le correctif, le rattrapage de la purge,
la sonde mémoire, deux commits poussés et le déploiement.

## 1. La nuit 10→11/09 : `exec_status = 1`

```
2026-09-11T06:59:14 Traceback (most recent call last):
  File ".../model-verif/score.py", line 7923, in <module> sys.exit(main())
  File ".../model-verif/score.py", line 7886, in main     _purges(sb, today)
NameError: name 'today' is not defined
2026-09-11T06:59:16 run score en ÉCHEC (code 1, 3675s) — 1 consécutif(s)
```

**Régression du lot du 10/09.** En extrayant l'étape 6 dans `_purges(sb,
today)` (pour `--purge-seule`), l'appel historique de `main` est resté
sur le nom `today`, qui n'existe plus dans cette portée — elle s'appelle
`as_of` (l. 6908). Le frère jumeau, l. 6927, passait bien
`datetime.now(timezone.utc)`. Python ne résout un global qu'à
l'EXÉCUTION : le run est mort sur sa DERNIÈRE ligne, 3 675 s après son
début.

⚠️ **La notation était bonne.** `model_murphy.json`, `model_scores.json`
(110 110 Ko), `model_scores_light.json` et les manches ont tous été
publiés à 06:59:14, juste avant le crash. La PWA avait ses données.
Seule l'étape 6 n'a jamais tourné.

## 2. Les chiffres (nuit 09→10 pré-correctifs → nuit 10→11 post-correctifs)

| | 09→10 (10/09) | 10→11 (11/09) | Δ |
|---|---|---|---|
| durée | 3 860 s | **3 675 s** | −185 s (garde 5 400, marge 1 725) |
| jalon max | 2 897 Mo (`score par régime`) | **2 856 Mo** (`oubli de la fenêtre rejouée`) | **−41 Mo** |
| `rejeu d'archive` | 2 373 Mo | **2 431 Mo** | **+58 Mo** |
| `score par régime` | 2 897 Mo | 2 629 Mo | −268 Mo |
| swap au pic | 2 048,0 Mo | **1 759,7 Mo** | −288 Mo (589 276 pages sorties) |
| `n_57014` | 7 | 4 | aucun du bloc purge |
| `lignes_score_zone` | 122 691 | 126 071 | +3 380 |
| `balise_jours_rejeu` | 1 253 232 | 1 309 861 | +4,5 % |
| lancement / résultat | timer / success | timer / **exit-code** | — |

Les 4 × 57014 de la nuit viennent de `rpc/bw_character_avance` (×2, contre
5 le 09/09) et `model_verif_event [0-999]` (×2). **Aucun du bloc purge —
parce que le bloc purge n'a pas tourné.** Le silence du motif
`bw-purge-57014` ce matin était donc un faux négatif.

## 3. Ce que le contrôle a dit à 07:30 — et pourquoi il ne fallait pas le croire

Le timer a tourné normalement (07:30:47, code 0) et a **commenté KAN-3 et
KAN-4** :

```
durée 3 860 s, +94 à +240 s/nuit → franchit le garde (5 400 s) entre le 17/09 et le 27/09   → KAN-3
mémoire 2 897 Mo (plancher : 2 048 Mo de swap au pic), +44 à +147 Mo/nuit
  → AU-DESSUS du seuil (2 800 Mo) depuis le 09/09                                          → KAN-4
```

⚠️ **Ce sont les chiffres du 10/09, mot pour mot.** `comparable()` écarte
la nuit (`exec_status != 0`) : `comparables[-1]` est toujours le 10/09,
la fenêtre de 10 relevés est inchangée, la pente aussi (+94 s/nuit,
+44 Mo/nuit, 24 comparables sur 42). Le contrôle fait exactement ce qu'il
doit faire — mais ces deux commentaires **ne mesurent pas la nuit
post-correctifs**. KAN-3 et KAN-4 n'ont donc été ni commentés ni
transitionnés par la session : le verdict n'a pas eu lieu.

## 4. Le correctif — commit `14381b2`, poussé et déployé

`score.py:7895` : `_purges(sb, as_of)`.

Le banc ne regardait pas `main` : il teste des fonctions. Plutôt qu'une
assertion sur `today`, **`test_11_09_aucun_nom_lu_sans_etre_lie`** tient
la classe entière via `symtable` — aucun nom LU sans être lié, dans
aucune portée, dans les **41 modules de production** du dossier — et se
vérifie elle-même en réintroduisant le défaut exact sur un faux source.
(Avant correction, le balayage sortait exactement `main → today`.)

Bancs : `test_score` **1 107/0** (Mac) et **1 105/0** (VPS) ·
`test_controle_quotidien` 35/35 · `mutations_controle_quotidien` 17/17 ·
`test_run_selftest` 39/39. ⚠️ `mutations_memoire` : **2 mutations non
vues** — vérifié identique sur la version d'avant le commit (`git stash`),
donc dette antérieure, pas de ce lot, mais à instruire.

Déploiement : `rsync model-verif/`, sha256 identiques Mac ↔ VPS sur
`score.py`, `test_score.py`, `sonde_fenetre_rejeu.py`. Les deux timers
sont armés (score 12/09 05:56, contrôle 12/09 07:30).

## 5. La purge rattrapée — et pas de retard, par chance

`score.py --purge-seule` sur le VPS, sans incident :

```
▶ purges seules (--purge-seule) — aucune notation
  ⓘ purge model_score_zone : rien à effacer (?as_of=lt.2026-09-04)
  ⓘ purge model_character : rien avant le 2027-02-04 (première écriture
    2026-08-08, rétention 180 j) — aucune requête lancée.
✅ terminé (purges seules)
```

⚠️ **Correction de ce que je craignais** : la nuit sautée n'a créé AUCUN
retard. Le 10/09, Yann avait rattrapé 09-02 **et 09-03** à la main —
c'est-à-dire une journée de plus que nécessaire — et la borne de ce matin
est justement `< 09-04`. Le garde-fou calendaire de `model_character`
marche : zéro requête, donc zéro 57014 de ce côté.

⛔ **Conséquence : `delete_par_tranches` n'a toujours PAS été éprouvé dans
le run de nuit.** La borne de demain sera `< 09-05`, avec une vraie
journée à effacer — la nuit du 11→12 est le premier test réel.

## 6. L'écart mémoire, instruit — commit `bc018a0`, `sonde_fenetre_rejeu.py`

Sonde rejouée sur le VPS au repos, 3 journées = 211 459 lignes, **un
processus par variante** (le tas n'est pas rendu au noyau), lecture seule :

| variante | champs | o/ligne | fenêtre du 11/09 (1 309 861 l.) |
|---|---:|---:|---:|
| `brut` — élagage neutralisé | 32 | 2 927 | 3 656 Mo |
| **`deploye` — tel qu'il tourne** | **22** | **2 828** | **3 532 Mo** |
| `k21` — une clé de moins | 21 | 2 700 | 3 373 Mo |
| `telquel` (boucle rejouée) | 22 | 2 354 | 2 940 Mo |
| `memo` — chaînes partagées | 22 | 2 101 | 2 624 Mo |
| **`tuple` — ligne en tuple + chaînes** | 22 | **1 577** | **1 970 Mo** |

**Gain réel de l'élagage : 99 o/ligne ≈ −124 Mo.** Un douzième des
−1 500 Mo annoncés. Deux raisons, toutes deux vérifiables :

1. **Le nombre de clés n'était pas le levier.** Le dict d'une ligne pèse
   832 o sur ~2 830 : les 2 000 autres sont ses VALEURS. Retirer dix clés
   ne retire que dix pointeurs.
2. **Et la table n'a même pas rétréci.** CPython 3.13 loge 21 clés dans
   464 o et **double à 832 dès la 22e** (`sys.getsizeof`, vérifié sur le
   VPS). `CLES_REJEU` en a exactement 22 — **une de trop**. La ligne
   « 22 clés → 1 301 o/ligne » de l'enquête §2.3 n'est pas
   reproductible : elle vient d'une sonde qui filtrait la ligne du CACHE,
   où `unit` n'existe pas encore (`replay_window` l'ajoute) — donc 21
   clés, donc sous la falaise. **Une clé oubliée dans la sonde a fait
   toute la prédiction.**

Les −1 500 Mo sont dans la **structure**, pas dans le nombre de clés :
chaînes partagées (−316 Mo), puis ligne en tuple (−970 Mo cumulés). Rien
de cela n'est fait — la sonde mesure, elle ne décide pas. Détail et
correction dans l'enquête, **§2.6** (ajouté sur le Mac ;
`amelioration scoring/agrume/enquete-pente-10-09.md`, dossier non suivi
par git).

⚠️ §2.4 reste vrai et borne ce qu'on peut espérer du JALON : le tas n'est
pas rendu au noyau, le rejeu s'installe dans le trou de la fenêtre
glissante, `VmRSS` exclut les pages en échange. Une fenêtre deux fois
plus légère ne fera pas un jalon deux fois plus bas — elle fera
disparaître le SWAP, qui est le vrai symptôme.

## 7. Ce qui reste

1. **Demain matin, le vrai verdict** : la nuit 11→12 est la première
   post-correctif ET le premier test réel de `delete_par_tranches`
   (borne `< 09-05`). C'est elle qui décide de KAN-3 et KAN-4.
2. **KAN-3 / KAN-4 toujours ouverts**, portant chacun un commentaire du
   11/09 qui parle en fait de la nuit du 09→10. Une ligne de mise au
   point s'y justifierait — pas écrite, à décider.
3. **La mémoire** : décider entre chaînes partagées seules (−316 Mo, sans
   rien retirer à personne) et la ligne en tuple (−970 Mo cumulés, mais
   quatre lecteurs à convertir à l'accès par index).
4. **`mutations_memoire` : 2 mutations non vues**, antérieures à ce lot.
5. **Chien de garde : rien fait, rien proposé de neuf.** Marge 1 725 s
   sur 5 400. La proposition du script reste la sienne, à lancer par Yann.
6. L'unité `bw-model-score.service` reste en état `failed` (trace honnête
   de cette nuit) ; le prochain run réussi la remettra au vert.

Commits poussés sur `balise-watch-server` : `14381b2` (le correctif et
son banc), `bc018a0` (la sonde). Rien d'autre n'a été écrit sur le VPS —
les fichiers de travail de `/tmp` ont été effacés.

---

## 09:07 → 10:45 — second run de la même routine : doublon, écrasement, restauration

⛔ **Cette note a été écrasée à 09:07 et restaurée à 10:45.** Un SECOND
run de la routine « Contrôle de pente 11/09 » a été lancé vers 09:00,
sans savoir que le premier (`session_011GUcBxK8TVyRBgFFbq7uaK`, 05:38 →
08:26) avait déjà fait le travail. Il a refait le constat depuis le VPS,
est arrivé aux mêmes chiffres, puis a fait un `project_write` sur ce
chemin **sans `project_read` préalable** : remplacement intégral,
`created_at` réinitialisé, aucune version conservée côté projet.

Le texte ci-dessus a été récupéré **intact** dans le transcript du
premier run (l'appel `project_write` en porte le contenu complet), via
Chrome sur le Mac. Rien n'est perdu.

**Ce que le second run avait écrit de FAUX**, et qu'il faut ignorer si on
en retrouve une copie :

- « la purge n'a pas tourné → ~190 000 lignes à rattraper cette nuit » :
  **non**. `--purge-seule` est passé à 08:1x sans un seul 57014, et la
  borne de ce matin (`< 09-04`) n'avait rien à effacer. La vraie échéance
  est la borne `< 09-05` de la nuit 11→12.
- « corrigé par Yann à 08:15 » : c'est le **premier run de la routine**
  qui a écrit, bancé, commité et déployé le correctif, sur feu vert de
  Yann.

**Correctifs mis en place le 11/09 pour que ça ne se reproduise pas** —
voir `notes-projet/README.md`.
