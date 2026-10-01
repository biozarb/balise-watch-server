# Verdict de pente du 01/10/2026 — la purge confirme (2/3), la mémoire est plate, la durée remonte **sans calcul en plus**, et le cri de position ne repart pas

## 09:15 — routine Balise Watch (départ 07:08 UTC), lecture seule sur le VPS + trois commentaires Jira

**Étape 0 faite.** `git log --oneline --since=midnight` : **aucun commit du
jour**, ni dans `balise-watch-server` (dernier : `5d84f09`, 30/09) ni dans
le dépôt principal (dernier : `af14849`, 30/09). Aucune note
`claude/verdict-pente-01-10.md` (le `project_read` rend « No doc »), et les
jetons `cri.jira.*` étaient encore datés du **30/09 09:13** : **aucun
commentaire Jira déposé ce matin avant cette session**. ⇒ première et
seule session de la matinée, rien à fusionner, rien à ne pas refaire.
`notes-projet/README.md` relu.

## 1. Les nuits, bout à bout

| | 27/09 | 28/09 | 29/09 | 30/09 | 01/10 |
|---|---|---|---|---|---|
| durée | 4 913 s | 5 295 s | 5 232 s | 4 992 s | **5 145 s (+153)** |
| garde / marge | 8 100 / 3 187 | 8 100 / 2 805 | 8 100 / 2 868 | 8 100 / 3 108 | **8 100 / 2 955 (−153)** |
| `cpu_s` | 3 968,0 | 4 155,8 | 4 185,2 | 4 012,9 | **3 962,7 (−50,2)** |
| jalon max | 3 340 Mo | 3 310 Mo | 3 305 Mo | 3 347 Mo | **3 338 Mo (−9)** |
| swap au pic | 2 110,3 | 2 518,2 | 2 329,1 | 2 161,8 | **2 209,3 (+47,5)** |
| pages sorties | 2 076 323 | 2 488 586 | 2 454 474 | 2 612 719 | **2 341 013 (−271 706)** |
| pic système | 3 607,2 | 3 619,8 | 3 601,8 | 3 606,2 | **3 593,6 (−12,6)** |
| fenêtre rejouée | 2 042 169 | 2 061 162 | 2 073 557 | 2 073 480 | **2 076 504 (+3 024)** |
| o / ligne rejouée | 1 715,0 | 1 683,9 | 1 671,3 | 1 692,7 | **1 685,6 (−7,1)** |
| `n_57014` | 1 | 2 | 2 | 0 | **3 (+3)** |
| lancement / résultat | timer/success | timer/success | timer/success | timer/success | **timer/success** |

Nuit **comparable** (`lancement=timer`, `exec_status=0`, `oom=0`,
05:58:47→07:24:45, `✅ terminé (745 630 lignes écrites en base)`).
Contrôle de ce matin **07:30:20, tir régulier** (prochain vendredi 02/10
07:30:05) : « **63 relevé(s), 42 comparable(s)** ; durée : 10 points,
pente **−72 s/nuit** ; mémoire : 10 points, pente **−24 Mo/nuit** ;
horizon 30 j ; seuil 2 800 Mo » puis « rien à dire : pente plate/négative,
ou échéance hors horizon ». Il s'est tu sur **les trois** motifs :
**aucun commentaire Jira de sa part ce matin**, la règle « un commentaire
par jour et par motif » ne bloquait donc rien.

## 2. ⛔ Durée : +153 s — et c'est de l'ATTENTE, pas du calcul

`4 913 · 5 295 · 5 232 · 4 992 · **5 145**`. La marge sous le garde
retombe à **2 955 s (36,5 % de 8 100)**, −153 s.

| étape | 30/09 | 01/10 | Δ |
|---|---|---|---|
| `regime` | 1 627,4 | **1 592,8** | **−34,6** |
| `glissant` | 1 001,8 | **981,9** | **−19,9** |
| `stabilite` | 253,6 | **272,0** | +18,4 |
| `rejeu` | 88,3 | **78,6** | **−9,7** |
| somme des quatre | 2 971,1 | **2 925,3** | **−45,8** |

Les quatre étapes chronométrées **baissent de 45,8 s** pendant que le
total **monte de 153 s** : environ **+199 s hors des étapes que le
registre isole**. Et `cpu_s` tombe à **3 962,7 s (−50,2)**. Du temps
d'horloge en plus **avec du calcul en moins** : ce n'est pas du calcul,
c'est de l'attente. Le journal systemd le confirme de son côté :
`Consumed 1h 6min 2.680s CPU time` pour 1 h 25 min 58 s de mur.

Le découplage temps/volume est **inversé** par rapport aux nuits de hausse
de la semaine dernière : le volume **baisse** légèrement
(`lignes_regime` 119 813 → **118 948, −865** ; `lignes_score_zone`
130 517 → **129 650, −867**). Ce n'est donc pas le volume. Et `regime`
continue de s'améliorer par ligne : **13,39 ms/ligne contre 13,58
(−1,4 %)**, quatrième meilleur chiffre de la série.

⚠️ **Le silence du contrôle n'est pas un acquittement.** Sa pente est le
**25e centile des différences** : elle ignore par construction les deux
plus grosses hausses de la fenêtre, donc une hausse isolée de +153 s ne
peut **pas** y apparaître — et de fait la pente durée reste à **−72 s/nuit,
inchangée au chiffre près**. `controle_quotidien.proposition()` **n'a rien
formulé** (pente négative) : **aucune remontée du chien de garde n'est
proposée par le script**, et `10-timeout-s3.conf` n'a pas été touché.

⇒ Le levier n'est pas le garde, c'est le §3.

## 3. ⛔ `n_57014 = 3` — record de la série, et **tout** sur `rpc/bw_character_avance`

```
06:22:02  ⚠️ rpc/bw_character_avance : HTTP 500 {"code":"57014", … statement timeout} — reprise 1/3
06:22:57  ⚠️ rpc/bw_character_avance : HTTP 500 {"code":"57014", … statement timeout} — reprise 1/3
06:24:06  ⚠️ rpc/bw_character_avance : HTTP 500 {"code":"57014", … statement timeout} — reprise 1/3
```

Trois expirations, **chacune reprise une fois et réussie** (« reprise
1/3 », jamais 2/3 ni 3/3). Série : **1 (28/09) · 2 (29/09) · 0 (30/09) ·
3 (01/10)** — et auparavant 10/09 et 16/09. **Aucun dans le bloc purge**
(§4) : c'est le dossier « base sous tension », pas KAN-5.

Les trois tombent dans la demi-heure 06:22–06:24, c'est-à-dire **au milieu
des +199 s d'attente du §2**. Chaque 57014 coûte son délai d'expiration
(le `statement_timeout` de PostgREST) **plus** son rejeu : trois d'affilée
expliquent naturellement un ordre de grandeur de deux à trois minutes.
Les deux faits de la nuit — durée en hausse sans calcul, et 57014 au
record — sont **très probablement le même fait**.

⇒ `model-verif/diagnostic_base_sous_tension_2026-09-29.sql` (lecture
seule, 9 blocs, SQL Editor) **attend toujours d'être joué par Yann**.
Le plan à balayage séquentiel sur des statistiques périmées n'a pas bougé,
et la nuit calme du 30/09 n'était donc pas un correctif — c'est écrit noir
sur blanc dans la note d'hier, et cette nuit le confirme.

## 4. ✅✅ Purge : deuxième nuit propre — **2 / 3**

```
07:24:30  → purge model_score_zone : 133646 ligne(s) effacée(s) en 8 tranche(s)
07:24:30  ⓘ purge model_character : rien avant le 2027-02-04 (première écriture
          2026-08-08, rétention 180 j) — aucune requête lancée.
07:24:30  ✅ terminé (745630 lignes écrites en base)
```

Les six points de l'attendu, vérifiés un par un comme hier :

- **8 tranches, une par régime, toutes réussies** — aucune ligne
  `⚠️ purge model_score_zone (?as_of=eq.J&regime=eq.R) : HTTP 500 57014`.
- **133 646 lignes effacées, nombre lisible** (`Content-Range` de chaque
  `DELETE`). **Aucun `?`**.
- **Aucune tranche sans `&regime=`** ⇒ le code du VPS n'a pas été écrasé
  par un ancien.
- **Aucun `⚠️ compte model_score_zone : HTTP 500`** : le `HEAD count=exact`
  sur `as_of < seuil` a bien disparu.
- **Aucun `des lignes RESTENT (plus vieille journée : J)`** — la seule
  phrase qui dirait qu'il reste quelque chose. Rien ne reste en base.
- **8 tranches, pas 540 `DELETE` à vide** : plus de repli aveugle sur
  `seuil − 60 j`.

Décompte : 30/09 → 129 666 en 8 tranches, propre ; 01/10 → **133 646 en
8 tranches, propre**. ⇒ **2 / 3**. Une troisième nuit propre (02/10) et la
fermeture de KAN-5 se proposera à Yann.

## 5. ⚠️ Mémoire : **plate** à volume constant — ni le mirage, ni la rechute

Les trois franchissements, tous au-dessus du seuil de 2 800 :

```
⛔ après le rejeu d'archive            : 2 923 Mo  (2 995 le 30, −72)
⛔ après le score par régime           : 2 908 Mo  (2 902 le 30,  +6)
⛔ après l'oubli de la fenêtre rejouée : 3 338 Mo  (3 347 le 30,  −9)  ← jalon max
```

Jalon max **3 338 Mo** : **538 Mo au-dessus du seuil**, et **deuxième plus
haut** de la série (3 340 · 3 310 · 3 305 · 3 347 · **3 338**). Coût par
ligne rejouée :

```
26/09 1 719,8 o · 27/09 1 715,0 · 28/09 1 683,9 · 29/09 1 671,3
30/09 1 692,7 · 01/10 1 685,6              → −7,1 o/ligne (−0,42 %)
```

La fenêtre a grandi de **+3 024 balise-jours** (2 076 504). Au taux de la
veille elle aurait rendu **≈ 3 352 Mo** ; elle en a rendu **3 338**, soit
**−14 Mo**. ⇒ à volume quasi constant, la mémoire est **plate**. Les
+21,4 o/ligne du 30/09 ne se poursuivent pas ; les −25 Mo « de structure »
annoncés le 29/09 ne reviennent pas non plus. **Rien n'est déployé côté
mémoire depuis `af25efb` (21/09)**, et c'est exactement ce que ce chiffre
dit : la série oscille, elle ne tend pas.

Swap, lecture en deux temps : pic **2 209,3 Mo (+47,5)** mais **2 341 013
pages sorties (−271 706)** et pic système **3 593,6 Mo (−12,6)** —
**l'inverse exact de la nuit précédente** (moins haut, plus longtemps).
Le plancher de swap d'environ **2,2 Go** est toujours là ; il n'est pas
près de 0.

Le remède reste la **ligne en tuple** (§2.6, ≈ −1 030 o/ligne cumulés),
avec la mesure `tuple` vs `namedtuple` à la sonde AVANT de choisir
(leçon §2.3). ⚠️ Rappel de l'échec de l'élagage de `units` (−124 Mo au
lieu de −1 500) : les gains sont dans la **structure**, pas dans le nombre
de clés. **Rien n'est décidé, rien n'est codé.**

## 6. ⛔ Position : quatrième nuit à 17 — et **le cri ne repart pas**

```
06:00:02  ⛔ position : 17 balise(s) divergent du gel (10 j lus), dont 1 CONFIRMÉE(S) (≥ 10 j)
             ⛔ pioupiou:2171   38925 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE · Windbird 2171
```

Série des divergences : `9 · 9 · 9 · 17 · 17 · 17 · **17**` — **quatrième
nuit à 17**, le saut du 28/09 ne retombe pas. `pioupiou:2171` reste la
seule **CONFIRMÉE**, toujours à **38 925 m** et à **10 j** (le compteur
plafonne : la fenêtre lue *est* de 10 j).

L'effectif tient à 17 mais **sa composition tourne** : douze balises à
4 j, `pioupiou:1333` à 9 j (87 693 m), `pioupiou:1334` à 3 j (61 156 m),
`pioupiou:1354` à 2 j, puis `pioupiou:2132` **retombée de 2 j à 1 j** et
`pioupiou:2023` **neuve à 1 j** (56 337 m). Ce n'est donc pas une cohorte
figée : des compteurs se réarment.

⛔ **Et surtout : aucun cri ce matin.** Pas de ligne
`⛔ position : 1 balise(s) CONFIRMÉE(S) — cri déposé pour envoi`, pas de
`msmtp`, pas de `⚠️ push non parti (webhook)` — **rien** (vérifié par
`grep -i` sur `cri|alerte|envoi|mail|webhook|push` dans tout le journal de
la nuit : zéro ligne). Deux conséquences, et les deux demandent Yann :

1. **Une balise qui RESTE confirmée ne recrie pas.** `pioupiou:2171` est
   confirmée depuis hier ; hier elle a crié, ce matin non. Le canal est
   donc **à front**, pas à état : si tu n'as pas vu le mail d'hier,
   **rien** ne te le redira. C'est un trou de surveillance, pas un bug du
   run.
2. **Le webhook n'a pas été re-sollicité**, donc sa panne du 30/09 n'est
   **ni confirmée ni réparée** — on ne sait toujours pas s'il remarche.
   Il n'a donc pas regagné son statut d'« éprouvé ».

Le contrôle **ne corrige rien** (règle de `freeze_balises.geler`) :
**geste attendu de Yann** — trancher, pour chaque cas, correction de
coordonnées **ou** AUTRE balise, puis poser `position_suspecte` +
`position_note` sur `station_zone` par `.sql`.

## 7. Tickets — trois commentaires, aucune transition, aucune création

États relevés **avant** d'écrire (GET `/rest/api/3/issue/…`, HTTP 200) :

| ticket | motif | statut | `statusCategory` | dernière maj avant ce matin |
|---|---|---|---|---|
| KAN-3 | `bw-pente-duree` | **Terminé** | `done` | 28/09 17:02 |
| KAN-4 | `bw-pente-memoire` | **À faire** | `new` | 30/09 09:13 |
| KAN-5 | `bw-purge-57014` | **À faire** | `new` | 30/09 09:13 |

- **KAN-4 (`bw-pente-memoire`)** — **laissé OUVERT**, **commenté**
  (`bw_jira_signaler`, HTTP 201, 25 commentaires au total). Les trois
  conditions de fermeture : jalon mesurablement retombé → **NON**
  (3 338 Mo, 538 au-dessus, deuxième plus haut) ; swap au pic ≈ 0 →
  **NON** (2 209,3 Mo) ; contrôle muet → oui, mais **−24 Mo/nuit** (il
  était à −30 pendant quatre matinées), silence **inertiel**. Le
  commentaire porte les trois franchissements, la courbe par ligne, le
  calcul des −14 Mo à taux constant, et la conclusion : **plate**, pas en
  baisse.
- **KAN-5 (`bw-purge-57014`)** — **laissé OUVERT**, **commenté**
  (HTTP 201, 8 commentaires). Le contrôle de 07:30:20 s'était tu, rien ne
  bloquait. Le commentaire porte le bloc purge entier, les six points
  vérifiés, le décompte **2 / 3**, et — en gras — la nuance qui compte :
  `n_57014 = 3` **mais aucun dans la purge**.
- **KAN-3 (`bw-pente-duree`, Terminé)** — **NON rouvert**, mais
  **commenté** cette fois (HTTP 201, 16 commentaires), parce que la
  consigne est de commenter **quand la durée augmente** : elle augmente de
  153 s. Le commentaire porte les chiffres, la répartition par étape, le
  découplage temps/volume **inversé**, le `cpu_s` en baisse, les trois
  57014 comme cause probable, le rappel du **25e centile**, et le fait que
  `proposition()` n'a rien formulé — donc **aucune remontée du garde
  proposée**. Réouverture : **c'est Yann qui tranche.**
  ⚠️ **Fait à la main, et il faut le savoir** : `bw_jira_chercher` filtre
  sur `statusCategory != Done`, donc `bw_jira_signaler bw-pente-duree`
  aurait **créé un ticket neuf** au lieu de commenter KAN-3. Le
  commentaire est donc parti par un `POST
  /rest/api/3/issue/KAN-3/comment` direct (via `bw_jira_http`, `curl -K -`,
  jeton jamais en clair), et le jeton `cri.jira.bw-pente-duree` du jour a
  été écrit **ensuite**, à la main, pour préserver « un commentaire par
  jour et par motif ».
- **Aucun motif neuf créé.** `bw-regime-sensibilite` reste en veille (la
  condition du 29/09 est définitivement non remplie : `regime` baisse
  encore, −34,6 s) ; les trois 57014 de `rpc/bw_character_avance` restent
  rattachés au dossier « base sous tension » ; le cri de position et le
  webhook ne sont pas de la dérive (partage des canaux en tête de
  `bw_jira.sh` : Jira = dérive ; mail + push = les ⛔).

Vérification après écriture (GET, HTTP 200) : **KAN-3 Terminé/`done`**,
**KAN-4 À faire/`new`**, **KAN-5 À faire/`new`** — statuts **inchangés**.
⛔ Aucun ticket fermé, aucune transition jouée, aucun ticket créé.

## 8. Hors périmètre, relevé sur la nuit

- ⚠️ **Écarts au recalcul indépendant : 6** (6 le 30, 3 le 29, 6 le 28) —
  toujours **tous en `fcstagrume`**, et toujours le même motif (« 0 h
  appariées ici (< 6) mais la base porte une ligne »). Mais **cinq des six
  balises sont neuves** : seul `aemet:9451F` (+6 h) revient d'hier ;
  s'ajoutent `infoclimat:000DH`, `mf:30297001`, `windsmobi:ffvl-2247`,
  `aemet:9218A` (+48 h), `infoclimat:000XB`. Ce n'est donc pas un lot figé
  de balises fautives, c'est un motif d'appariement qui frappe au hasard
  dans `fcstagrume`. 13 balise-jours comparés, 7 sous le seuil de 6 h.
- `lignes_daily` **69 800 (+5 130)** — le reflux de 5 385 de la veille est
  intégralement rendu ; `lignes_glissant` 10 702 (−2).
- Observations du jour : **3 746 balises** (veille 3 733).
- Stabilité des rangs : **`tau = 0,817` sur 58 cases** (0,798 sur 60) —
  moins de cases classées, corrélation meilleure.
- Témoins : part du site **17,3 pts** (17,5), part secteur+heure
  **11,0 pts** (10,6), mélange **+2,6 %** vs meilleur membre a priori
  (devant dans **52,6 %** des cas, contre +0,3 % et 49,5 % la veille) et
  **+4,0 %** vs uniforme (+4,9 %). Le mélange **repasse au-dessus** du
  seuil du « devant une fois sur deux ».
- Référence combinée : médiane **`k = 0,124`** (0,092 la veille) sur
  3 712 balises / 3 814 climatologisées ; **380** balises avaient un ρ hors
  [0, 1] ramené à la borne (670 la veille — nette amélioration).
- Murphy : **66 804** cases, dont **64 504** décomposées, 266 balises
  dehors (inchangé).
- ⓘ R2 : **4 écritures**, plafond 10, **158,7 Mo** — rien près du plafond.
- `mutations_memoire` : **aucune ligne** au journal de la nuit ; dette
  antérieure de **3 mutations non vues** (2, 5, 13), inchangée.
- Duel apparié : 63 371 lignes lues en lead 6 (1 448 retirées), 21 556 en
  lead 24 (503 retirées).
- ⓘ Skill nul sur 30 cases (persistance) et 32 (climatologie) — « le vent
  n'a pas bougé, la question n'a pas eu lieu ».
- Manches : **34 nuits** suivies depuis le 24/08, **634 cases**
  zone×lead×modèle avec au moins une manche gagnée.
- 9 balises nées sous leur identifiant (`notee_depuis`, lot L15-bis),
  toutes du 25/09 — inchangé.

## 9. Ce qui a été touché

**VPS** : rien hors les **trois** commentaires Jira. `tail` du registre,
`journalctl` (notation et contrôle, droits élevés, lecture),
`list-timers`, `controle_quotidien.py --verbeux`, lecture de
`bw_jira.sh`, six GET Jira (trois avant écriture, trois après
vérification), listage du dossier de jetons
`~/.balise-watch-etat-alertes`. **Aucun `systemctl start/restart/
daemon-reload`, aucun `enable`, aucun SQL joué, aucun `rsync`, rien écrit
dans `~/balise-watch` ni dans `/etc`.** Écritures : les deux textes de
KAN-4 et KAN-5 par `bw_jira_signaler` (qui travaille dans un `mktemp -d`
en 700 effacé après), le texte de KAN-3 par `bw_jira_http` direct, et les
**trois jetons `cri.jira.<motif>` du jour**.
`~/.balise-watch-alertes.env` **sourcé**, jamais lu par valeur ;
`curl -K -`, jamais `-u`. **Mac** : cette note et son miroir projet, plus
un script jetable dans `/tmp` (hors dépôt) — **pas de `git push`**.

## 10. Ce qui reste — et ce qui demande Yann

1. ⛔ **Le dossier « base sous tension » est devenu le point n° 1.**
   `n_57014 = 3`, record de la série, **tout** sur
   `rpc/bw_character_avance`, et dans la fenêtre exacte où la nuit a perdu
   ses ≈ +199 s d'attente. `diagnostic_base_sous_tension_2026-09-29.sql`
   (lecture seule, 9 blocs) **attend d'être joué dans le SQL Editor** ;
   les correctifs candidats (ANALYZE / VACUUM / autovacuum par table) y
   sont en commentaire. C'est le levier de la durée, pas le garde.
2. ⛔ **Le cri de position est « à front », pas « à état ».**
   `pioupiou:2171` est toujours CONFIRMÉE et **n'a pas crié ce matin**
   (aucune ligne de cri, aucun mail, aucun webhook). Si le mail d'hier est
   passé inaperçu, plus rien ne te le redira. **Question posée, rien
   lancé** : veux-tu que le garde-fou recrie tant qu'une balise reste
   confirmée (même motif, une fois par jour), ou qu'il se taise comme
   aujourd'hui ?
3. ⛔ **Le webhook `push` n'a pas été re-sollicité** — sa panne du 30/09
   est donc **ni confirmée ni réparée**. Mêmes deux questions qu'hier,
   restées sans réponse : veux-tu qu'une prochaine session éprouve
   `BW_WEBHOOK_URL` par un `curl` de test hors run, ou préfères-tu
   regarder toi-même ? Et faut-il un motif Jira pour une panne de canal,
   alors que `bw_jira.sh` réserve Jira à la dérive ?
4. ⛔ **`pioupiou:2171` et les 16 autres divergences** (4ᵉ nuit à 17) :
   trancher pour chaque cas, correction de coordonnées **ou** AUTRE
   balise, puis `position_suspecte` + `position_note` sur `station_zone`
   par `.sql`. La composition tourne (`pioupiou:2132` réarmée à 1 j,
   `pioupiou:2023` neuve à 1 j).
5. ⚠️ **La mémoire (KAN-4)** : jalon **3 338 Mo**, 538 au-dessus du seuil,
   coût par ligne **−7,1 o** — la série est **plate**, elle n'a ni le
   mirage de baisse du 29/09 ni la rechute du 30/09. **Aucun levier
   déployé depuis le 21/09** : décider la **ligne en tuple**, après la
   mesure `tuple` vs `namedtuple` à la sonde.
6. ✅ **La purge : 2 / 3.** `e83d814` tient. Une nuit propre de plus
   (02/10) et la fermeture de KAN-5 te sera proposée.
7. ✅ **La durée (KAN-3)** : rien à décider **aujourd'hui**. Marge
   2 955 s (36,5 %), pente du contrôle −72 s/nuit inchangée, `regime` à
   13,39 ms/ligne. KAN-3 reste **Terminé** mais **commenté** ; si la hausse
   se confirme la nuit prochaine, c'est le point 1 qu'il faudra ouvrir,
   pas le garde.
8. ⚠️ **Écarts au recalcul : 6, dont 5 balises neuves** — le motif
   d'appariement `fcstagrume` frappe au hasard, ce n'est pas un lot figé.
   Dette ancienne, à resurveiller.
9. `mutations_memoire` : 3 mutations non vues (dette antérieure).

Miroir git : `notes-projet/verdict-pente-01-10.md`, commité en local depuis
la racine du dépôt serveur. Pas de `git push`.
