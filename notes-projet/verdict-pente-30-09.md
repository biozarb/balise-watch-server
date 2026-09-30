# Verdict de pente du 30/09/2026 — la purge est éprouvée, la mémoire repart à la hausse, le webhook rate son premier vrai cri

## 09:15 — routine Balise Watch (départ 07:09 UTC), lecture seule sur le VPS + deux commentaires Jira

**Étape 0 faite.** `git log --oneline --since=midnight` : **aucun commit du
jour**, ni dans `balise-watch-server` (dernier : `b28d25e`, 29/09) ni dans
le dépôt principal (dernier : `544309d`, 24/09). Aucune note
`claude/verdict-pente-30-09.md` au contexte de session. Jetons
`cri.jira.*` datés du **29/09 09:13**, donc aucun commentaire Jira déposé
ce matin avant cette session. ⇒ **première et seule session de la
matinée**, rien à fusionner, rien à ne pas refaire.
`notes-projet/README.md` relu.

## 1. Les nuits, bout à bout

| | 26/09 | 27/09 | 28/09 | 29/09 | 30/09 |
|---|---|---|---|---|---|
| durée | 4 756 s | 4 913 s | 5 295 s | 5 232 s | **4 992 s (−240)** |
| garde / marge | 8 100 / 3 344 | 8 100 / 3 187 | 8 100 / 2 805 | 8 100 / 2 868 | **8 100 / 3 108 (+240)** |
| jalon max | 3 317 Mo | 3 340 Mo | 3 310 Mo | 3 305 Mo | **3 347 Mo (+42)** |
| swap au pic | 2 335,9 | 2 110,3 | 2 518,2 | 2 329,1 | **2 161,8 (−167,3)** |
| pages sorties | 2 252 141 | 2 076 323 | 2 488 586 | 2 454 474 | **2 612 719 (+158 245)** |
| pic système | 3 619,0 | 3 607,2 | 3 619,8 | 3 601,8 | **3 606,2 (+4,4)** |
| fenêtre rejouée | 2 022 451 | 2 042 169 | 2 061 162 | 2 073 557 | **2 073 480 (−77)** |
| o / ligne rejouée | 1 719,8 | 1 715,0 | 1 683,9 | 1 671,3 | **1 692,7 (+21,4)** |
| `cpu_s` | 3 755,3 | 3 968,0 | 4 155,8 | 4 185,2 | **4 012,9 (−172,3)** |
| `n_57014` | 0 | 1 | 2 | 2 | **0 (−2)** |
| lancement / résultat | timer/success | timer/success | timer/success | timer/success | **timer/success** |

Nuit **comparable** (`lancement=timer`, `exec_status=0`, `oom=0`,
05:58:11→07:21:35, `✅ terminé (716 151 lignes écrites en base)`).
Contrôle de ce matin **07:30:43, tir régulier** (prochain jeudi 01/10
07:30:20) : « **62 relevé(s), 41 comparable(s)** ; durée : 10 points,
pente **−72 s/nuit** ; mémoire : 10 points, pente **−30 Mo/nuit** ;
horizon 30 j ; seuil 2 800 Mo » puis « rien à dire : pente plate/négative,
ou échéance hors horizon ». Il s'est tu sur **les trois** motifs — durée,
mémoire et `bw-purge-57014` : **aucun commentaire Jira de sa part ce
matin**, la règle « un commentaire par jour et par motif » ne bloquait
donc rien.

## 2. ✅✅ La purge passe son épreuve — la forme attendue, au caractère près

C'était **le** point en attente d'un fait. Bloc purge en entier :

```
07:21:17  → purge model_score_zone : 129666 ligne(s) effacée(s) en 8 tranche(s)
07:21:17  ⓘ purge model_character : rien avant le 2027-02-04 (première écriture
          2026-08-08, rétention 180 j) — aucune requête lancée.
07:21:17  ✅ terminé (716151 lignes écrites en base)
```

Point par point, contre l'attendu écrit dans le prompt et dans la note du
29/09 :

- **8 tranches, une par régime, toutes réussies.** Aucun
  `⚠️ purge model_score_zone (?as_of=eq.J&regime=eq.R) : HTTP 500 57014`.
- **129 666 lignes effacées, nombre lisible** — lu dans le `Content-Range`
  de chaque `DELETE`. L'attendu était ≈ 125 000 pour la journée du 22/09 ;
  129 666 effacées contre 130 517 écrites cette nuit, l'ordre de grandeur
  est le bon. **Aucun `?`** : tous les `Content-Range` ont été lus.
- **Aucune ligne `⚠️ compte model_score_zone : HTTP 500`.** Le `HEAD
  count=exact` sur `as_of < seuil` — celui qui expirait les 28 et 29/09,
  celui qui écrivait le `?` — a bien disparu du code.
- **Aucune ligne `des lignes RESTENT (plus vieille journée : J)`** : c'est
  la seule phrase qui dirait qu'il reste quelque chose, et elle n'est pas
  là. Rien ne reste en base.
- **Aucune tranche sans `&regime=`** : le `?as_of=eq.J` nu de l'ancien code
  ne peut plus apparaître, et il n'apparaît pas — donc le code du VPS n'a
  pas été écrasé par un ancien.
- **Plus de repli aveugle sur `seuil − 60 j`** : 8 tranches, et non les
  540 `DELETE` à vide du 29/09.

⇒ **`e83d814` est éprouvé.** C'est la **première** nuit qui remplit les
deux conditions de fermeture de KAN-5 (pas de 57014 dans la purge **et**
nombre lisible) : **1 / 3**.

## 3. ✅ `n_57014 = 0` — première nuit blanche depuis le 26/09

Pas un seul `HTTP 500 57014` sur toute la nuit : ni dans la purge, ni sur
`rpc/bw_character_avance`, qui n'a rien eu à reprendre (contre ×1 le 28/09
et ×2 le 29/09). Série : `0 · 1 · 2 · 2 · **0**`.

⚠️ **Ça ne clôt pas le dossier « base sous tension ».**
`model-verif/diagnostic_base_sous_tension_2026-09-29.sql` (lecture seule,
9 blocs) **attend toujours d'être joué par Yann** : une nuit calme n'est
pas un correctif, et le plan à balayage séquentiel sur des statistiques
périmées est toujours là. À recompter demain.

## 4. ✅ Durée : −240 s, et le découplage de `regime` s'inverse franchement

`4 756 · 4 913 · 5 295 · 5 232 · **4 992**`. La marge sous le garde
remonte à **3 108 s (38,4 % de 8 100)**, la meilleure depuis le 26/09. La
pente du contrôle passe de −63 à **−72 s/nuit**.

| étape | 29/09 | 30/09 | Δ |
|---|---|---|---|
| `regime` | 1 787,6 | **1 627,4** | **−160,2** |
| `stabilite` | 295,4 | **253,6** | **−41,8** |
| `glissant` | 985,4 | **1 001,8** | +16,4 |
| `rejeu` | 79,2 | **88,3** | +9,1 |

Les quatre étapes chronométrées rendent **−176,5 s** ; le reste des −240 s
(−63,5) vient de ce que le registre n'isole pas. `cpu_s` **−172,3 s** :
c'est du calcul réel en moins, pas un artefact d'horloge.

✅ **Et le volume a AUGMENTÉ pendant ce temps** : `lignes_regime`
116 149 → **119 813 (+3,15 %)**, `lignes_score_zone`
126 857 → **130 517 (+2,89 %)**. `regime` a donc pris **−8,96 % de temps
pour +3,15 % de lignes**, soit **13,58 ms/ligne contre 15,39 (−11,8 %)** —
le plus gros gain par ligne de la série. Les Δ `regime` sur six nuits :
**−136,0 · +150,3 · +120,6 · +13,6 · −160,2**.

⇒ **La condition d'arbitrage du 29/09 est définitivement non remplie**
(« sauf si la hausse s'additionne encore deux nuits de suite ») :
`bw-regime-sensibilite` **reste en simple veille**, aucune question
reposée à Yann, aucun motif créé. Et `regime` n'est plus à son plus haut
absolu.

`controle_quotidien.proposition()` **n'a rien formulé** (pente négative) :
**aucune remontée du chien de garde n'est proposée par le script**, et
`10-timeout-s3.conf` n'a pas été touché.

`stabilite` retombe de 41,8 s ; la qualité recule légèrement :
**`tau = 0,798` sur 60 cases** (0,803 sur 57 la veille) — plus de cases
classées, corrélation un cheveu plus basse.

## 5. ⛔ Mémoire : la baisse par ligne était bien un mirage — elle s'inverse

Les trois franchissements, tous au-dessus du seuil de 2 800 :

```
⛔ après le rejeu d'archive            : 2 995 Mo  (3 004 le 29, −9)
⛔ après le score par régime           : 2 902 Mo  (2 942 le 29, −40)
⛔ après l'oubli de la fenêtre rejouée : 3 347 Mo  (3 305 le 29, +42)  ← jalon max
```

Jalon max **3 347 Mo** : **plus haut de la série** (3 317 · 3 340 · 3 310 ·
3 305 · **3 347**), et **547 Mo au-dessus du seuil**. Coût par ligne
rejouée :

```
23/09 1 818,2 o · 24/09 1 784,5 · 25/09 1 784,3 · 26/09 1 719,8
27/09 1 715,0 · 28/09 1 683,9 · 29/09 1 671,3 · 30/09 1 692,7
                                      → +21,4 o/ligne (+1,28 %)
```

La fenêtre est **pratiquement identique** : 2 073 480 contre 2 073 557
(−77 balise-jours). Au taux de la veille elle aurait rendu **3 305 Mo** ;
elle en a fait **3 347**. Les +42 Mo ne s'expliquent pas par le volume.

⇒ **La mise en garde des notes des 26, 28 et 29/09 est vérifiée.** Trois
nuits de baisse par ligne sans le moindre changement de code, puis une
remontée : c'était une **fluctuation de données**, pas un acquis. Les
−25 Mo « de structure » annoncés le 29/09 sont repartis, et 17 Mo de plus
avec eux. Rien n'est déployé côté mémoire depuis `af25efb` (21/09), et
c'est exactement ce que ce chiffre dit.

Swap, lecture en deux temps : le pic **redescend** à **2 161,8 Mo
(−167,3)**, le plus bas depuis le 27/09 — mais **2 612 719 pages sorties
(+158 245)**, le record de la série, et pic système **3 606,2 Mo (+4,4)**.
Moins haut, plus longtemps : le noyau a poussé davantage de pages dehors
pour tenir un pic plus bas. Et 2 161,8 n'est pas 0 : le plancher de swap
est toujours là.

Le remède reste la **ligne en tuple** (§2.6, ≈ −1 030 o/ligne cumulés),
avec la mesure `tuple` vs `namedtuple` à la sonde AVANT de choisir (leçon
§2.3). ⚠️ Rappel de l'échec de l'élagage de `units` (−124 Mo au lieu de
−1 500) : les gains sont dans la **structure**, pas dans le nombre de
clés. **Rien n'est décidé, rien n'est codé.**

## 6. ⛔ NOUVEAU — position : première balise CONFIRMÉE, et le webhook rate son cri

C'est le fait neuf de la nuit, et il demande Yann.

```
05:59:29  ⛔ position : 17 balise(s) divergent du gel (10 j lus), dont 1 CONFIRMÉE(S) (≥ 10 j)
             ⛔ pioupiou:2171   38925 m · 10 j · nœud 0,01 CHANGE · profil 0,025 CHANGE · Windbird 2171
05:59:29  ⛔ position : 1 balise(s) CONFIRMÉE(S) — cri déposé pour envoi
...
07:21:33  ⚠️ push non parti (webhook)
07:21:34  msmtp … smtpstatus=250 smtpmsg='250 2.0.0 OK' exitcode=EX_OK
```

Deux choses, distinctes :

1. **Le garde-fou de position confirme pour la première fois.** Série des
   divergences : `9 · 9 · 9 · 17 · 17 · **17**` — **troisième nuit à 17**,
   le saut du 28/09 ne retombe pas, et cette fois **une** balise franchit
   les 10 jours : `pioupiou:2171` (Windbird 2171), **38 925 m** d'écart,
   **nœud AROME 0,01 ET profil 0,025 tous deux CHANGE**. Les 16 autres
   sont à 2–9 jours (le plus gros : `pioupiou:1333`, 87 693 m, 9 j, et
   `pioupiou:2132`, 87 693 m, 2 j). Le contrôle **ne corrige rien** (règle
   de `freeze_balises.geler`) : **geste attendu de Yann** — trancher, pour
   chaque cas, correction de coordonnées **ou** AUTRE balise, puis poser
   `position_suspecte` + `position_note` sur `station_zone` par `.sql`.
2. ⛔ **Le webhook `push` a échoué sur sa première vraie sollicitation.**
   Non éprouvé depuis le 23/09 (septième nuit) : cette nuit il avait
   enfin un cri à porter, et `⚠️ push non parti (webhook)`. Le mail est
   passé (msmtp, `250 OK`, vers biozarb@gmail.com), donc **l'alerte n'a
   pas été perdue** — mais le canal de secours est, lui, **mesurément
   cassé**, pas seulement « non testé ». C'est une panne de canal
   d'alerte, pas une dérive : elle n'a **pas** sa place dans Jira selon le
   partage des canaux écrit en tête de `bw_jira.sh` (Jira = dérive ;
   mail + push = les ⛔). **Aucun ticket créé de ma propre initiative** —
   voir §9.

## 7. Tickets — deux commentaires, aucune transition

États relevés **avant** d'écrire (GET `/rest/api/3/issue/…`, HTTP 200) :

| ticket | motif | statut | `statusCategory` | dernière maj avant ce matin |
|---|---|---|---|---|
| KAN-3 | `bw-pente-duree` | **Terminé** | `done` | 28/09 17:02 |
| KAN-4 | `bw-pente-memoire` | **À faire** | `new` | 29/09 09:13 |
| KAN-5 | `bw-purge-57014` | **À faire** | `new` | 29/09 09:13 |

- **KAN-4 (`bw-pente-memoire`)** — **laissé OUVERT**, **commenté**
  (HTTP 201, `bw_jira_signaler`). Les trois conditions de fermeture :
  jalon mesurablement retombé → **NON** (3 347 Mo, 547 au-dessus, plus
  haut de la série) ; swap au pic ≈ 0 → **NON** (2 161,8 Mo) ; contrôle
  muet → oui, mais **−30 Mo/nuit inchangé au chiffre près depuis quatre
  matinées**, donc silence inertiel. Le commentaire porte les trois
  franchissements, la courbe par ligne **avec son inversion**, le calcul
  des +42 Mo à fenêtre constante, et la conclusion que la baisse des trois
  nuits précédentes était bien un mirage.
- **KAN-5 (`bw-purge-57014`)** — **laissé OUVERT**, **commenté**
  (HTTP 201). Le contrôle de 07:30:43 s'est tu, donc rien ne bloquait.
  Le commentaire porte le bloc purge entier, les six points de l'attendu
  vérifiés un par un, `n_57014 = 0`, et le décompte : **1 / 3** nuits
  (le 28→29 n'avait pas de 57014 dans la purge non plus, mais il tournait
  l'ancien code et le nombre était `?` — il ne compte pas). Fermeture :
  **trois nuits consécutives**, et **c'est Yann qui tranche**.
- **KAN-3 (`bw-pente-duree`, Terminé)** — **non rouvert, NON commenté.**
  La consigne est de commenter si la durée **augmente** : elle **baisse**
  de 240 s, la marge remonte de 240 s, la pente passe à −72 s/nuit.
  ⚠️ Note technique : `bw_jira_chercher` filtre sur
  `statusCategory != Done`, donc un `bw_jira_signaler bw-pente-duree`
  n'aurait **pas** commenté KAN-3 — il aurait **créé un ticket neuf**.
  Piège à garder en tête le jour où la durée remontera.
- **Aucun motif neuf créé.** `bw-regime-sensibilite` reste en veille
  (condition définitivement non remplie, §4) ; le 57014 de
  `rpc/bw_character_avance` reste rattaché au dossier « base sous
  tension » (§3) ; l'échec du webhook n'est pas une dérive (§6.2).

⛔ Aucun ticket fermé, aucune transition jouée, aucun ticket créé.

## 8. Hors périmètre, relevé sur la nuit

- ⚠️ **Écarts au recalcul indépendant : 6** (3 le 29, 6 le 28, 6 le 27) —
  la série remonte au niveau des 27–28/09. Toujours **tous en
  `fcstagrume`** : `aemet:9451F` (+6 h), `infoclimat:STATIC0087` (+48 h),
  `mf:38567002` (+48 h), `pioupiou:2176` (+24 h), `windsmobi:holfuy-1168`
  (+48 h), `aemet:9995Y` (+24 h). Quatre à « 0 h appariées », deux à
  « 1 h » — toujours le même motif : la base porte une ligne là où le
  recalcul n'a pas de quoi apparier.
- ⛔ **Position : 17 divergences, 1 CONFIRMÉE** — voir §6, c'est le point
  neuf.
- ⛔ **Webhook `push` : ÉCHEC sur un vrai cri** — voir §6.2. Ce n'est plus
  « non éprouvé », c'est « en panne ».
- `lignes_daily` **64 670** (−5 385, net reflux) et **70 097 détails par
  tranche** contre 65 052 (+5 045) : les deux bougent en sens opposé.
- Murphy : **66 789** cases, dont **64 423** décomposées, 266 balises
  dehors (inchangé).
- FDR : brut 7 149 tests, 2 147 survivants (98 rangs retirés sur 1 266) ;
  corrigé 6 831 tests, 1 569 survivants (118 sur 822).
- ⓘ R2 : **4 écritures**, plafond 10, **159,4 Mo** — rien près du plafond.
- `mutations_memoire` : **aucune ligne** au journal de la nuit ; dette
  antérieure de **3 mutations non vues** (2, 5, 13), inchangée.
- Témoins : part du site **17,5 pts** (15,9 le 29), part secteur+heure
  **10,6 pts** (10,3), mélange **+0,3 %** vs meilleur membre a priori
  (+2,4 % le 29, devant dans 49,5 % des cas) et **+4,9 %** vs uniforme
  (+5,7 %). Le mélange gagne nettement moins que la veille : il repasse
  sous le seuil du « devant une fois sur deux ».
- Référence combinée : médiane `k = 0,092` sur 3 714 balises / 3 815
  climatologisées ; 670 balises avaient un ρ hors [0, 1], ramené à la
  borne.
- Self-test S3 : ✅ (a) skill contre combinée vectorielle = 1.0,
  ✅ (b) rms(perm)/rms(clim) = 2.198 (attendu 1,0–3,0).
- 9 balises nées sous leur identifiant (`notee_depuis`, lot L15-bis),
  toutes du 25/09 — inchangé.
- Manches : 33 nuits suivies depuis le 24/08, 625 cases zone×lead×modèle
  avec au moins une manche gagnée.

## 9. Ce qui a été touché

**VPS** : rien hors les **deux** commentaires Jira. `tail` du registre,
`journalctl` (contrôle et notation), `list-timers`,
`controle_quotidien.py --verbeux`, lecture de `bw_jira.sh`, six GET Jira
(trois avant écriture, trois après vérification), listage du dossier de
jetons `~/.balise-watch-etat-alertes`. Aucun `systemctl`, aucun SQL, aucun
rsync, rien écrit dans `~/balise-watch` ni dans `/etc` (les deux textes
sont passés par `bw_jira_signaler`, qui travaille dans un `mktemp -d` en
700 effacé après ; seuls les deux jetons `cri.jira.<motif>` du jour ont
été écrits, par le canal lui-même). `~/.balise-watch-alertes.env`
**sourcé**, jamais lu. **Mac** : cette note et son miroir git, plus un
script jetable dans `/tmp` (hors dépôt) — **pas de `git push`**.

## 10. Ce qui reste — et ce qui demande Yann

1. ⛔ **`pioupiou:2171`, première balise CONFIRMÉE par le garde-fou de
   position** (38 925 m, 10 j, nœud **et** profil AROME changés). Le geste
   est à toi : correction de coordonnées **ou** AUTRE balise, puis
   `position_suspecte` + `position_note` sur `station_zone` par `.sql`.
   Et **troisième nuit à 17 divergences** : le lot des 8 balises apparues
   le 28/09 ne retombe pas.
2. ⛔ **Le webhook `push` est en panne, pas seulement non testé.** Premier
   vrai cri depuis le 23/09, et il n'est pas parti. Le mail a pris le
   relais, donc rien n'a été perdu cette nuit — mais le canal de secours
   ne répond plus. **Question posée, rien lancé** : veux-tu que la
   prochaine session éprouve `BW_WEBHOOK_URL` (un `curl` de test hors
   run), ou préfères-tu regarder toi-même ? Et : faut-il un motif Jira
   pour une panne de canal, alors que `bw_jira.sh` réserve Jira à la
   dérive ?
3. ⛔ **La mémoire (KAN-4)** : jalon **3 347 Mo**, plus haut de la série,
   547 Mo au-dessus du seuil, coût par ligne **en hausse de 21,4 o**.
   L'inversion de cette nuit prouve que les trois baisses précédentes
   n'étaient pas un acquis. **Aucun levier déployé depuis le 21/09** :
   décider la **ligne en tuple**, après la mesure `tuple` vs `namedtuple`
   à la sonde.
4. **Le dossier « base sous tension »** :
   `diagnostic_base_sous_tension_2026-09-29.sql` et
   `rattrapage_purge_2026-09-29.sql` **attendent d'être joués** dans le
   SQL Editor. `n_57014 = 0` cette nuit est une bonne nouvelle, **pas** un
   correctif.
5. ✅ **La purge : plus rien en attente d'un fait.** `e83d814` est
   éprouvé. Reste à compter deux nuits propres de plus (01/10, 02/10)
   avant de te proposer la fermeture de KAN-5.
6. ✅ **La durée** : rien à décider. Marge 3 108 s (38,4 %), pente −72
   s/nuit, `regime` à **13,58 ms/ligne (−11,8 %)**. KAN-3 reste Terminé,
   `bw-regime-sensibilite` reste en veille.
7. ⚠️ **Écarts au recalcul remontés à 6**, tous `fcstagrume` — dette
   ancienne, à resurveiller.
8. `mutations_memoire` : 3 mutations non vues (dette antérieure).

Miroir git : `notes-projet/verdict-pente-30-09.md`, commité en local
depuis la racine du dépôt serveur. Pas de `git push`.
