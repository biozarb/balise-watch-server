# Verdict de pente du 10/10/2026 — **lecture COMPLÈTE** (tout a été lu, contrairement au 09/10) mais **ZÉRO écriture Jira** : le Mac s'est déconnecté juste après le GET des tickets. Trois commentaires sont **rédigés et prêts**, non postés. Faits du jour : la **durée au plus bas de marge de toute la série** (34,35 %), la **mémoire qui s'améliore en structure** (deux jalons repassent sous le seuil), **KAN-5 à 3/3** — fermeture à décider — et le correctif `--ipv4` du 07/10 **enfin ÉPROUVÉ** (cri parti le 09/10, HTTP 200).

## 11:30 (Paris) — routine Balise Watch (tirée à 09:24:07 UTC pour 07:11:05 : **+2 h 13 de retard**), lecture VPS complète, **aucune écriture nulle part**

**Étape 0 faite, et elle a servi.** `git log --oneline --since=midnight` :
- dépôt serveur : **deux commits du jour**, `874729f` et `c9497da` — « produit B : une passe tombée entre ses écritures et l'index ne laisse plus d'orphelins » et l'entrée `BUGS.md` qui va avec. ⇒ **une autre session a bien travaillé ce matin, mais sur un TOUT AUTRE sujet** (orphelins / agrume-grille, cf. `claude/orphelins-agrume-grille-10-10.md`). Rien à fusionner côté pente.
- dépôt principal : aucun commit du jour.
- `project_read claude/verdict-pente-10-10.md` → « No doc ». `verdict-pente-09-10.md` lu **en entier**. `notes-projet/README.md` relu.
⇒ **premier et seul run pente du jour.**

⛔ **LE MAC S'EST DÉCONNECTÉ — DEUXIÈME MATIN D'AFFILÉE.** Cette fois la coupure
est arrivée **après** toute l'Étape 1 et **après** le GET de vérification des
trois tickets, donc **le diagnostic est complet** ; seules les **écritures**
Jira sont tombées. Six reprises sur ~20 min (0, 120, 240, 300 s, plus deux
`RefreshMcpTools`) : « device not connected » chaque fois, et les serveurs MCP
locaux (Desktop Commander) ne sont pas revenus. Le conteneur cloud n'a **pas**
de route SSH vers `51.91.102.146` et ne porte pas la clé ; Jira est hors
d'atteinte faute de jeton (et un secret ne se lit pas par valeur). **Il n'y a
pas de contournement.**

| à lire / à faire | fait ? |
|---|---|
| registre `historique.jsonl` | ✅ |
| `systemctl list-timers` (contrôle + notation) | ✅ |
| journal `bw-model-controle.service` du jour | ✅ |
| `controle_quotidien.py --verbeux` | ✅ |
| journal `bw-model-score.service` de la nuit, **en entier** | ✅ |
| bloc purge de la nuit 09→10 **et** de la nuit 08→09 (trou d'hier) | ✅ |
| position, témoins, Murphy, duels, τ, ρ, écarts, self-test | ✅ |
| noms des variables du `.env` | ✅ |
| **GET** de l'état des trois tickets | ✅ |
| **POST** des trois commentaires Jira | ⛔ **NON** |
| miroir git de cette note (et de celle du 09/10) | ⛔ **NON** |

## 1. Les nuits, bout à bout

| | 05/10 | 06/10 | 07/10 | 08/10 | 09/10 | 10/10 |
|---|---|---|---|---|---|---|
| durée | 4 821 s | 5 157 s | 5 227 s | 5 228 s | 5 192 s | **5 318 s (+126)** |
| marge | 3 279 | 2 943 | 2 873 | 2 872 | 2 908 | **2 782 (−126)** |
| marge en % du garde | 40,5 % | 36,3 % | 35,5 % | 35,46 % | 35,90 % | **34,35 % ← plus bas relevé** |
| `cpu_s` | 3 853,3 | 4 163,6 | 4 244,9 | 4 257,9 | 4 199,5 | **4 237,7 (+38,2)** |
| jalon max | 3 417 Mo | 3 364 | 3 420 | 3 429 | 3 356 | **3 394 (+38)** |
| au-dessus du seuil | +617 | +564 | +620 | +629 | +556 | **+594** |
| swap au pic | 2 218,3 | 2 175,5 | 2 127,7 | 2 267,1 | 2 145,1 | **2 088,1 (−57,0)** |
| pages sorties | 2 579 457 | 2 507 693 | 2 369 940 | 2 556 336 | 2 241 569 | **2 487 135 (+245 566)** |
| pic système | 3 600,5 | 3 619,1 | 3 617,2 | 3 602,9 | 3 615,2 | **3 608,5 (−6,7)** |
| fenêtre rejouée | 2 086 473 | 2 087 575 | 2 088 602 | 2 089 691 | 2 089 138 | **2 088 809 (−329)** |
| o / ligne rejouée | 1 717,2 | 1 689,7 | 1 717,0 | 1 720,6 | 1 684,4 | **1 703,8 (+19,4)** |
| `n_57014` | 0 | 2 (purge) | 0 | 0 | 0 | **1 (HORS purge)** |
| lancement / résultat | timer/success | ↳ | ↳ | ↳ | ↳ | **timer/success** |

Nuit **comparable** : `lancement=timer`, `exec_status=0`, `oom=0`,
`result=success`, 06:00:06 → 07:28:59. Rien à écarter.

**Le contrôle de 07:30 a tiré à 07:30:10 et s'est TU** :
`ⓘ 72 relevé(s), 51 comparable(s) ; durée : 10 points, pente −55 s/nuit ;
mémoire : 10 points, pente −13 Mo/nuit ; horizon 30 j ; seuil 2 800 Mo` puis
`ⓘ rien à dire : pente plate/négative, ou échéance hors horizon`.
⇒ **aucun jeton du jour n'a été posé par le contrôle**, ni côté
`/var/lib/bw-model-verif` (derniers : 17/09, 23/09, 06/10) ni côté
`$HOME/.balise-watch-etat-alertes` (derniers : 07/10, 08/10, 08/10).
**`bw_jira_signaler` était donc libre sur les trois motifs** — c'est lui qui
était prévu pour KAN-4 et KAN-5, et `bw_jira_commenter` pour KAN-3 (Terminé).

## 2. ⛔ Durée : elle REMONTE, et la marge n'a jamais été si basse

`4 821 · 5 157 · 5 227 · 5 228 · 5 192 · **5 318**`. Le recul de 36 s du 09/10
est **entièrement rendu, et 91 s de plus**. Marge **2 782 s = 34,35 %** du
garde de 8 100 s : **le plus bas de toute la série** (précédent plus bas
35,46 %, le 08/10). ⚠️ **Le « plateau » annoncé le 08/10 et à moitié démenti le
09/10 n'était ni un plateau ni un repli : c'était une pause.**

**Calcul ou attente ? Les deux — et c'est la première fois.** `cpu_s` monte de
**+38,2 s** pour **+126 s** d'horloge : le processeur monte **trois fois
moins** que le temps réel, donc ≈ 88 s de la hausse **ne sont pas du calcul**.
Et `n_57014 = 1` cette nuit (après trois nuits à 0) : il y a bien eu de
l'attente sur la base. Les quatre nuits précédentes étaient du calcul pur ;
celle-ci est **mixte**.

| étape | 06/10 | 07/10 | 08/10 | 09/10 | 10/10 |
|---|---|---|---|---|---|
| `regime` | 1 820,0 | 1 794,6 | 1 813,6 | 1 751,4 | **1 809,1 (+57,7)** |
| `glissant` | 1 002,0 | 1 018,3 | 1 005,9 | 988,2 | **964,4 (−23,8)** |
| `stabilite` | 328,8 | 341,7 | 338,1 | 322,5 | **358,7 (+36,2)** |
| `rejeu` | 81,5 | 88,4 | 79,2 | 78,3 | **85,6 (+7,3)** |
| somme des quatre | 3 232,3 | 3 243,0 | 3 236,8 | 3 140,4 | **3 217,8 (+77,4)** |
| hors étapes | 1 924,7 | 1 984,0 | 1 991,2 | 2 051,6 | **2 100,2 (+48,6)** |

**61 % de la hausse est DANS les quatre étapes, 39 % hors étapes.** Cinquième
nuit, **cinquième signature** (88 % dans les étapes le 06/10 ; 85 % hors
étapes le 07/10 ; les quatre étapes reculant ensemble le 09/10). Rien ne se
répète — sauf une chose :

⛔ **LE HORS-ÉTAPES MONTE POUR LA QUATRIÈME NUIT D'AFFILÉE, SANS UN SEUL
RECUL** : 1 924,7 → 1 984,0 → 1 991,2 → 2 051,6 → 2 100,2, soit **+175,5 s en
quatre nuits**. C'est, pour la deuxième journée de suite, **le seul mouvement
monotone du tableau**, et il porte sur le **bloc non instrumenté**
(publication, Murphy, événements, pression, duels, purge) : on ne sait pas
lequel des six postes monte. ⇒ **la question posée à Yann les 07, 08 et 09/10
— poser des jalons de temps dans `run.sh` — est maintenant la plus mûre du
dossier.**

**Découplage temps / volume, troisième nuit de confirmation.**
`lignes_regime` **125 472 (+248, soit +0,2 %)** pendant que le temps de
`regime` monte de **+3,3 %** ; `lignes_glissant` **10 535 (−13)** pendant que
le coût par ligne de `glissant` **baisse** (93,7 → **91,5 ms**).
`lignes_score_zone` 136 007 (+235), `lignes_daily` 69 677 (+78).
⇒ **ce qui pilote la durée n'est pas le nombre de lignes.**

Coût par ligne de `regime` (ms) :

```
13,39 (01/10) · 13,24 · 14,02 · 13,67 · 13,53 · 15,07 · 14,86 · 14,87 · 13,99 · 14,42 (10/10)
  → +0,43 : UNE hausse
```

✅ **`bw-regime-sensibilite` : critère NON rempli, rien n'est créé.**
L'arbitrage unique du 07/10 exige **deux hausses consécutives**. Il y en a
**une** : compteur à **1 / 2**. (Le seuil absolu de 14,5 ms de la note du 06/10
reste retiré depuis le 07/10 ; à 14,42 il n'aurait de toute façon pas été
franchi.)

⚠️ **La pente du contrôle ne voit pas cette hausse, par construction.** Elle
est le **25e centile des différences** : **−55 s/nuit** sur 10 points ce matin
(51 comparables sur 72), donc « rien à dire ». Elle ignore structurellement les
deux plus grosses hausses de la fenêtre — elle n'a vu **ni le +153 s du 01/10,
ni le +336 s du 06/10, ni le +70 s du 07/10, ni le +126 s de cette nuit**.
KAN-3 est en « Terminé » sur la foi de cette pente ; les chiffres bruts sont au
plus haut.

**Remontée du garde : à PROPOSER, non lancée — et le contrôle n'en propose
aucune cette nuit** (sa pente étant négative, `proposition()` n'est pas
atteinte). Garde actuel **8 100 s (135 min)** pour un run de **88,6 min**.
⛔ `10-timeout-s3.conf` **n'a pas été touché**.

## 3. ✅ Mémoire : le jalon max remonte un peu, mais **la structure s'améliore** — deux jalons repassent sous le seuil

```
⛔ après l'oubli de la fenêtre rejouée : 3 394 Mo  (3 356 le 09, 3 429 le 08)  ← jalon max, +38
ⓘ après le rejeu d'archive            : 2 627 Mo  (3 048 le 09)  ← −421, SOUS LE SEUIL
ⓘ après le score par régime           : 2 688 Mo  (2 937 le 09)  ← −249, SOUS LE SEUIL
```

✅ **FAIT NEUF : `incidents` ne porte plus qu'UNE ligne mémoire au lieu de
trois.** C'est la **première nuit de la série** dans ce cas. Les deux premiers
jalons, qui dépassaient 2 800 Mo depuis des semaines, rentrent sous le seuil.
⇒ **la pression ne disparaît pas, elle se CONCENTRE** sur le seul jalon de
« l'oubli de la fenêtre rejouée » — précisément celui que la **ligne en tuple**
visait. ⚠️ C'est **une** nuit : à revérifier demain avant d'en faire une
tendance (la leçon a resservi sept fois en treize jours).

Autres jalons : agrégat quotidien 1 849 (=), oubli fenêtre glissante 1 760
(−24), oubli du chemin J-0 959 (+8), relecture de l'archive 830 (+14),
garde-fou de position 1 214 (=), mélange multi-modèle 1 202 (−8).

```
29/09 1 671,3 o · 30/09 1 692,6 · 01/10 1 685,6 · 02/10 1 689,2
03/10 1 706,4  · 04/10 1 697,4 · 05/10 1 717,2 · 06/10 1 689,7
07/10 1 717,0  · 08/10 1 720,6 · 09/10 1 684,4 · 10/10 1 703,8
  → +19,4 o/ligne ; fourchette 1 671–1 721 sur douze nuits, TOUJOURS aucune pente
```

⇒ ✅ **la lecture du 09/10 tient : c'est une oscillation, pas une pente.** Ni
le 1 720,6 du 08/10 (lu alors comme « la fourchette s'étire vers le haut ») ni
le 1 684,4 du 09/10 (le plus bas en onze jours) n'annonçaient quoi que ce soit.

À taux constant, sur la fenêtre de cette nuit : au taux du **09/10** (1 684,4)
elle aurait rendu **3 355,4 Mo** — l'écart réel (**+38,6 Mo**) est donc
imputable au **coût par ligne**, pas à la fenêtre, qui a **reculé** pour la
deuxième nuit. Au taux du **01/10** : 3 357,8 Mo. Au taux du **08/10** :
3 427,5 Mo.

**Swap : pic 2 088,1 Mo (−57,0)** — plus bas de la série — mais **2 487 135
pages sorties (+245 566)** : les deux divergent cette nuit (pic en baisse,
trafic en hausse). ⚠️ Le plancher tient : **11e nuit consécutive au-dessus de
2,0 Go**.

**Rien de déployé côté mémoire depuis `af25efb` (21/09) — 20e nuit sans
levier.** Remède inchangé : la **ligne en tuple** (`enquete-pente-10-09.md`
§2.6, ≈ −1 030 o/ligne), après la mesure `tuple` vs `namedtuple` à la sonde.
L'élagage de `units` avait rendu −124 Mo au lieu de −1 500 : **les gains sont
dans la structure**.

## 4. ✅ Purge : nuit PROPRE, et le trou d'hier est comblé — **KAN-5 est à 3 / 3**

```
→ purge model_score_zone : 129 594 ligne(s) effacée(s) en 8 tranche(s)
ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée
```

- **aucune TRANCHE à 57014** (aucun `?as_of=eq.J&regime=eq.R` en HTTP 500)
- **aucune SONDE** (« plus vieille journée illisible » absente)
- **aucun « des lignes RESTENT »**
⇒ **nuit propre, avec un nombre de lignes lisible.**

✅ **Le trou n° 8 du 09/10 est comblé** : le bloc purge de la nuit du **08→09**
a été lu ce matin — **129 650 lignes en 8 tranches, propre lui aussi**. Le
compteur se reconstitue donc :

| nuit | état du bloc purge | compteur |
|---|---|---|
| 07→08 (jour 2026-10-08) | `n_57014 = 0`, propre | 1 |
| 08→09 (jour 2026-10-09) | **propre**, 129 650 l. / 8 tr. | 2 |
| 09→10 (jour 2026-10-10) | **propre**, 129 594 l. / 8 tr. | **3** |

⇒ ⛔ **LA CONDITION DE FERMETURE DE KAN-5 EST REMPLIE : 3 / 3.** Elle n'est
**pas** appliquée — la fermeture se décide avec Yann. **C'est la question n° 1
du matin.**
ⓘ Le volume effacé suit le volume de la journée purgée (≈ 125 000–134 000) :
les 56 lignes d'écart avec hier **ne sont pas un signal**.

⚠️ **MAIS UN 57014 EST APPARU CETTE NUIT, AILLEURS QUE DANS LA PURGE** — et
c'est pour cela, et cela seulement, que le registre porte `n_57014 = 1` :

```
⚠️ rpc/bw_character_avance : HTTP 500 {"code":"57014" … statement timeout} — reprise 1/3
→ model_character : 466 509 accumulateurs avancés sur 466 509 envoyés
```

⇒ **la reprise a abouti, rien n'est perdu, ce n'est pas un échec.** Mais le
`statement timeout` n'a pas disparu de la base : **il a changé de requête.**
Trois nuits à `n_57014 = 0` ne sont pas un correctif (il y en avait eu trois
d'affilée les 03, 04 et 05/10 avant le retour du 06/10) ; cette nuit le redit
autrement. ⇒ **à poser à Yann : un motif Jira propre pour
`bw_character_avance`, ou le dossier « base sous tension » ?** Aucun motif neuf
n'a été créé.

✅ **Le contrôle s'est tu sur ce motif, et c'est CORRECT** : depuis le 07/10,
`constats()` lit `score.log` via `bilan_purge()` — avertissement **puis** bilan
chiffré ⇒ silence. Le faux « purge en échec » du 06/10 ne s'est pas reproduit,
**quatrième nuit**.

⛔ **`diagnostic_base_sous_tension_2026-09-29.sql`** (lecture seule, 9 blocs,
SQL Editor) **attend toujours d'être joué : onze jours.**

## 5. ✅ Le correctif `--ipv4` du 07/10 est ÉPROUVÉ — et c'est la meilleure nouvelle du matin

Le cri de position **est parti le 09/10**, et il est **passé** :

```
2026-10-09T06:01:20  ⛔ position : 3 balise(s) CONFIRMÉE(S) — cri déposé pour envoi
2026-10-09T07:26:46  ⓘ push parti (webhook, HTTP 200)
2026-10-09T07:26:53  ⓘ push parti (webhook, HTTP 200)
2026-10-10T07:29:05  ⓘ push parti (webhook, HTTP 200)
```

⇒ **deux pushes à HTTP 200 le 09/10, un ce matin, aucun 429.** Le correctif du
07/10 (quota ntfy du préfixe IPv6 **partagé** d'OVH, contourné par `--ipv4`)
**fonctionne en conditions réelles** — il attendait son épreuve depuis trois
jours. Trafic conforme à la normale (2 à 7 messages/jour) : pas de runner qui
s'emballe.

⚠️ **`BW_DISCORD_WEBHOOK_URL` est TOUJOURS ABSENTE du `.env`** (25 variables
relevées par leur **nom seul** ; fichier inchangé depuis le 13/09). Le second
canal du téléphone reste **codé, testé, muet**. `~/installer-webhook-discord.sh`
attend toujours Yann.

## 6. ⚠️ Position : **4 → 3 confirmées**, et le cri « à front » a bien fonctionné

```
⛔ position : 11 balise(s) divergent du gel (10 j lus), dont 3 CONFIRMÉE(S) (≥ 10 j)
   ⛔ pioupiou:2171          38 925 m · 10 j · nœud+profil CHANGE · Windbird 2171
   ⛔ pioupiou:1388           2 363 m · 10 j · nœud+profil CHANGE · Décollage Serre Michèle
   ⛔ infoclimat:STATIC0491   1 159 m · 10 j · nœud CHANGE
   ·  pioupiou:1333          87 693 m ·  8 j  ← N'EST PLUS CONFIRMÉE
   ·  1378 (15 778 m) · 367 (6 764) · 1417 (829) · 1375 (747) · 1722 (631) · 1562 (481) · 1678 (422) — toutes à 5 j
```

⛔ **`pioupiou:1333` est SORTIE du lot confirmé**, et le journal du 09/10 dit
pourquoi : `- pioupiou:1333 : rentrée dans l'ordre (le référentiel et le gel se
sont rejoints, ou la balise n'est plus vue)`. Elle est passée 10 → 9 → **8 j**.
⇒ ⚠️ **le cas « la balise à 87,7 km » n'est plus un cas de position
divergente** : soit sa coordonnée a été corrigée à la source, soit elle a cessé
d'émettre. **À regarder pour lui-même** — c'est la balise la plus éloignée du
lot, et elle disparaît sans qu'on sache laquelle des deux explications joue.

ⓘ **Le cri est bien « à front »** : il est parti le 09/10 quand le compte est
passé de 4 à 3, et **il ne repart pas ce matin** puisque les trois confirmées
sont les mêmes. La question du 01/10 reste ouverte : **faut-il qu'il recrie ?**

⚠️ **Les sept balises à 5 j franchiraient 10 j le 15/10** — ce jour-là le compte
passerait de 3 à **10**, donc un cri à front. **Geste attendu de Yann** :
trancher `2171`, `1388`, `STATIC0491` (et désormais statuer sur `1333` qui
sort), puis poser `position_suspecte` + `position_note` sur `station_zone` par
`.sql`.
ⓘ `position_confirmees.json` est daté du **09/10 06:01** : il n'a **pas** été
réécrit cette nuit — cohérent avec « pas de front », mais à garder en tête.

## 7. ⚠️ Témoins du mélange : la série ne tient plus — et le trou du 09/10 est comblé

```
gain contre le MEILLEUR MEMBRE a priori : 7,4 % → 5,5 % → −0,6 (07/10) → +2,5 (08/10) → −1,2 (09/10) → −0,1 (10/10)
   « devant » dans : …  → 49,2 % (07/10) → … → 50,1 % (09/10) → 49,1 % (10/10)
gain contre la moyenne UNIFORME         : 6,0 % → 4,9 → 4,8 → 3,1 (08/10) → 4,8 (09/10) → 3,2 (10/10)
```

⛔ **Ce n'est plus « une nuit ».** Sur les **quatre** dernières nuits lues, le
gain contre le meilleur membre a priori fait **−0,6 · +2,5 · −1,2 · −0,1**,
soit une moyenne de **+0,15 %** — contre 7,4 % puis 5,5 % auparavant. Et le
mélange est « devant » dans **49,1 %** des cas, c'est-à-dire **moins d'une fois
sur deux**, pour la troisième fois sur quatre nuits. ⇒ ⚠️ **le mélange
n'apporte plus rien face au meilleur membre choisi a priori.** Détail de la
nuit : 4,5783 km/h contre 4,5746 sur 7 587 balise-jours×échéance.

✅ **En revanche la lecture du 08/10 est DÉMENTIE** : elle annonçait un
quatrième recul consécutif du gain contre la moyenne **uniforme**
(6,0 → 4,9 → 4,8 → 3,1). La valeur du 09/10, lue ce matin, est **4,8** — la
série **oscille** entre 3,1 et 4,8, elle ne décline pas. Le mélange garde donc
tout son sens **contre une moyenne naïve** (3,2 % cette nuit, sur 1 127) ;
c'est seulement contre le **meilleur membre** qu'il ne gagne plus.

⇒ ⚠️ **À poser à Yann : veut-il un motif Jira pour les témoins du mélange ?**
La consigne demandait d'attendre que la série confirme. **Elle a confirmé.**
Rien n'a été créé.

## 8. Le reste du journal

- ✅ **Self-test du scoring : VERT** (lot S3, aucune lecture réelle). Écart des
  deux mélanges : `mse_comb` 17,841 contre `mse_comb_vec` 17,841 (+0,00 %).
- ⚠️ **Stabilité des rangs : τ = 0,709 sur 53 cases** (0,744 le 08/10 ; 0,751
  le 09/10 sur 57 cases). **Deux baisses, et le nombre de cases recule aussi**
  (60 → 57 → 53). À suivre, pas à conclure.
- ⚠️ **ρ hors [0, 1] : 349 balises sur 3 700** (307 le 08/10, **382** le 09/10).
  Oscillation haute ; les quatre nuits d'amélioration de fin septembre sont
  perdues.
- ⚠️ **5 écarts au recalcul indépendant** (4 le 08/10, **5** le 09/10), **tous
  en `fcstagrume`** et tous de la même signature : « ici None, base X — 0 ou 1 h
  appariée ici (< 6) mais la base porte une ligne » (`infoclimat:STATIC0386`,
  `mf:74056001`, `pioupiou:1506`, `windsmobi:meteoswiss-ATT`,
  `infoclimat:STATIC0309`). 13 balise-jours comparés, 7 sous le seuil de 6 h.
- **Murphy** : 66 272 triplets, 64 248 décomposés, 266 balises tenues dehors
  (1,0 s). `agrume +48h` et `agrume_pi +48h` restent en **TIMING** (SS −0,320,
  « aucune pente n'y peut rien ») ; tout le reste est en AMPLITUDE.
- **Duels appariés** : `agrume_pi ↔ bw_mix` toujours `b_better` (+0,476 à +6 h
  sur 7 056 balise-jours, +0,619 à +24 h) ; `agrume ↔ arome_france_hd`
  `a_better` de peu (−0,016) ; `arome_r2 ↔ arome_france_hd` `b_better`
  (+0,110). ⓘ Cumul **tronqué** par la rétention de 30 j.
- **Événements** : 52 918 lignes, 30 183 combinaisons publiables, 30 256
  écartées sous le quorum de 8 ; 41 231 lignes non publiées (familles hors
  onset/drop/ramp/breeze_yield). `model_events.json` publié (8 426 Ko).
- **Pression** : 17 986 lignes, 864 appariées (médiane 18,1 km).
- **Référence combinée** : k médian 0,149 sur 3 700 balises / 3 819
  climatologisées.
- **R2** : `écritures=4 (plafond 10)`, 164,1 Mo. Rien à signaler.
- **`mutations_memoire`** : ⚠️ **aucune ligne dans le journal des deux
  dernières nuits** — le relevé « 3 mutations non vues (2, 5, 13) » ne peut pas
  être revérifié ici. Dette antérieure, **statut inchangé faute de mesure**.
- `✅ terminé (743 191 lignes écrites en base)` ; `registre : 1 ligne écrite`.

## 9. ⛔ Les tickets : état VÉRIFIÉ par GET, mais **rien n'a été écrit**

GET `/rest/api/3/issue/<clé>` passé **avant** la coupure, HTTP 200 sur les
trois :

| ticket | statut | commentaires | ce qui était prêt |
|---|---|---|---|
| **KAN-3** `bw-pente-duree` | **Terminé** / `done` | **19** | `bw_jira_commenter` — la durée remonte (+126), marge 34,35 % au plus bas, 61/39 étapes/hors-étapes, hors-étapes +175,5 s en 4 nuits, découplage temps/volume, aveuglement du 25e centile, remontée du garde **proposée non lancée**, correction du « plateau » du 08/10 |
| **KAN-4** `bw-pente-memoire` | **À faire** / `new` | **30** | `bw_jira_signaler` — jalon 3 394 (+38) mais **deux jalons sous le seuil**, coût 1 703,8 o, calcul à taux constant, **les trois conditions de fermeture non remplies**, le 09/10 jamais porté |
| **KAN-5** `bw-purge-57014` | **À faire** / `new` | **13** | `bw_jira_signaler` — nuit propre 129 594 l. / 8 tr., **compteur 3/3**, le 57014 déplacé sur `bw_character_avance`, fermeture **posée** à Yann |

⛔ **AUCUN POST N'EST PARTI.** Les trois corps sont rédigés et conservés dans
le transcript de ce run (encodés pour un envoi en une passe) : **ils peuvent
être postés tels quels dès que le Mac répond.** Aucune création, aucune
transition, aucune réouverture, aucune fermeture.
ⓘ **Le garde-fou n'a été consommé par personne aujourd'hui** (ni le contrôle,
qui s'est tu, ni la routine, qui n'a pu écrire) : les trois motifs sont encore
libres pour un rattrapage **aujourd'hui**, par `bw_jira_signaler` pour KAN-4 et
KAN-5 et `bw_jira_commenter` pour KAN-3.

## 10. Ce qui a été touché

**VPS — règle de LECTURE SEULE pleine et entière, respectée.** Huit commandes
`ssh`, **toutes en lecture** : `date`, `tail` du registre, `list-timers` ×2,
`journalctl` ×5, `controle_quotidien.py --verbeux`, `grep` dans `bw_jira.sh` et
`controle_quotidien.py`, `ls` de `/var/lib/bw-model-verif` et du dossier
d'état, et trois **GET** Jira. **Aucun `systemctl start/restart/daemon-reload`,
aucun `enable`, aucun SQL joué, aucun `rsync`, rien écrit dans
`~/balise-watch` ni dans `/etc`, aucun fichier déposé, pas même dans `/tmp`.**
**Aucun secret lu par valeur** : le `.env` a été sourcé pour les GET et lu
**par noms de variables seuls** (`sed -E "s/=.*//"`). `bw_jira.sh` passe par
`curl -K -`.
**Aucune écriture Jira** (voir §9).

**Mac** : rien. Aucun fichier créé, aucun script, **aucun commit**, **pas de
miroir git** (voir ci-dessous), pas de `git push`.

**Projet Claude** : cette note, **créée** (`project_read` a rendu « No doc »
avant écriture — vérifié).

⛔ **DEUX NOTES SANS MIROIR GIT, MAINTENANT.** La règle n° 3 du `README.md`
demande un dépôt dans `notes-projet/` et un commit local : impossible sans le
Mac, deux matins de suite. **`notes-projet/verdict-pente-09-10.md` ET
`notes-projet/verdict-pente-10-10.md` restent à déposer et à commiter
ensemble.** Elles n'existent pour l'instant que côté projet, sans filet.

## 11. Ce qui reste — et ce qui demande Yann

**Décisions, par ordre d'urgence :**

1. ⛔ **FERMER KAN-5 ? Le compteur est à 3 / 3.** Trois nuits consécutives sans
   57014 dans le bloc purge, avec un nombre de lignes lisible à chaque fois
   (129 650 puis 129 594). La condition arbitrée est remplie. ⚠️ **Deux
   réserves à peser avant de dire oui** : le `statement timeout` a **changé de
   requête** (`bw_character_avance` cette nuit, repris et abouti), et le
   `diagnostic_base_sous_tension` n'a **jamais été joué** — donc la cause
   profonde n'est pas mesurément réglée, seulement la purge. *Un ticket fermé à
   tort vaut moins qu'un ticket ouvert.*
2. ⛔ **L'HORAIRE DE LA ROUTINE, et la déconnexion qui va avec.** +2 h 13
   aujourd'hui (09:24 UTC pour 07:11), après +6 h 40 le 09/10, +2 h 10 le
   08/10, à l'heure le 07/10, jusqu'à 4 h 10 les 04–06/10, **aucun tir** les 02
   et 03/10. **Le VPS est à l'heure** (contrôle 07:30:10, notation 06:00:05,
   prochains 07:30:41 et 05:59:56). Le trou est côté **planification**. ⚠️ Et
   pour le **deuxième matin de suite**, le Mac s'est déconnecté en cours de run
   — c'est ce qui a coûté les écritures Jira. **Un tir à l'heure vaudrait
   mieux qu'un run réparé.**
3. ⛔ **Jouer `diagnostic_base_sous_tension_2026-09-29.sql`** (lecture seule,
   9 blocs, SQL Editor). **Onze jours d'attente**, et le 57014 vient de
   démontrer qu'il se déplace.
4. ⛔ **Trancher les cas de position** : `2171` (38,9 km), `1388` (2 363 m),
   `STATIC0491` (1 159 m) — puis dire ce qu'on fait de **`1333`, qui est sortie
   du lot** (10 → 8 j, « rentrée dans l'ordre »). Ensuite `position_suspecte` +
   `position_note` par `.sql`. ⓘ **Sept balises franchiraient 10 j le 15/10**,
   faisant passer le compte de 3 à 10.
5. ⛔ **Lancer `~/installer-webhook-discord.sh`.** ✅ Bonne nouvelle : le
   correctif `--ipv4` **est maintenant éprouvé** (HTTP 200, trois pushes). Mais
   ntfy reste **seul**, et son quota anonyme dépend toujours du voisinage /64
   d'OVH.
6. ⚠️ **Instrumenter le bloc hors étapes de `run.sh` ?** Quatrième hausse
   consécutive (+175,5 s), **seul mouvement monotone du tableau**, deuxième
   matin de suite. C'est une écriture dans `run.sh` : la décision est à toi.
7. ⚠️ **Un motif Jira pour les témoins du mélange ?** La série a **confirmé** :
   quatre nuits à +0,15 % de moyenne contre le meilleur membre a priori, et
   « devant » dans 49,1 % des cas. ⓘ Le gain contre la moyenne **uniforme**,
   lui, tient (3,2 %) : le mélange reste utile, mais plus face au meilleur
   membre choisi d'avance.
8. ⚠️ **Un motif Jira pour `bw_character_avance`**, ou cela reste-t-il dans
   « base sous tension » ?
9. ⓘ **Un champ de bilan de purge au registre ?** (question du 08/10.) Ce
   matin a dû lire **deux** journaux pour reconstituer le compteur de KAN-5.
   Avec `lignes_effacees` et `tranches` au registre, le §4 aurait tenu en trois
   lignes.
10. ⓘ **Le cri de position : à front ou à état ?** (question du 01/10.) Il a
    bien fonctionné à front le 09/10. Et **faut-il un motif Jira pour une panne
    de canal ?** (question du 30/09.)

**Ce que la surveillance fera au prochain run, dans cet ordre :**

11. ⛔ **Poster les trois commentaires préparés** (KAN-4 et KAN-5 par
    `bw_jira_signaler`, KAN-3 par `bw_jira_commenter`), en les **réactualisant**
    avec la nuit nouvelle plutôt qu'en les postant à l'identique.
12. ⛔ **Déposer les DEUX miroirs git manquants** (`verdict-pente-09-10.md` et
    `verdict-pente-10-10.md`) et les commiter en même temps que la note du jour.
13. **La mémoire** : les deux premiers jalons restent-ils **sous le seuil** ?
    C'est le point le plus intéressant de la nuit, et il n'a qu'un point.
14. **La durée** : 34,35 % de marge est le plus bas relevé. Le hors-étapes
    fait-il une **cinquième** hausse ?
15. **Le coût par ligne de `regime`** : 14,42 est **une** hausse. Une seconde
    remplirait le critère `bw-regime-sensibilite` — et alors la question va à
    Yann, rien ne se crée seul.
16. **τ** (0,709, deux baisses) et **ρ hors [0, 1]** (349) : séries à
    surveiller, aucune conclusion.

---
ⓘ Miroir git déposé le **11/10/2026** par la routine du jour, depuis
`claude/verdict-pente-10-10.md` lu par `project_read` et **repris tel quel**.
Le Mac s'étant déconnecté les 09 et 10/10, cette note est restée deux jours
sans filet.
