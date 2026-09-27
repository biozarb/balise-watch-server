# Verdict de pente du 27/09/2026 — la durée remonte, le gain mémoire ne se confirme pas

## 09:25 — routine Balise Watch (prévue 07:07 UTC, partie 07:09 UTC), lecture seule sur le VPS + trois commentaires Jira

**Étape 0** : `git log --since=midnight` **vide** dans les deux dépôts
(dernier commit `bc45aca`, 26/09, « Produit B »). Aucune note
`verdict-pente-27-09` avant celle-ci, aucun autre run ce matin.
`notes-projet/README.md` relu.

## 1. Les nuits, bout à bout

| | 24/09 | 25/09 | 26/09 | 27/09 |
|---|---|---|---|---|
| durée | 4 916 s | 4 941 s | 4 756 s | **4 913 s (+157)** |
| garde / marge | 8 100 / 3 184 | 8 100 / 3 159 | 8 100 / 3 344 | **8 100 / 3 187 (−157)** |
| jalon max | 3 371 Mo | 3 410 Mo | 3 317 Mo | **3 340 Mo (+23)** |
| swap au pic | 2 202,0 | 2 172,0 | 2 335,9 | **2 110,3 (−225,6)** |
| pages sorties | 2 298 595 | 2 279 055 | 2 252 141 | **2 076 323** |
| pic système | 3 602,8 | 3 610,0 | 3 619,0 | **3 607,2 (−11,8)** |
| fenêtre rejouée | 1 980 799 | 2 003 977 | 2 022 451 | **2 042 169 (+0,97 %)** |
| o / ligne rejouée | 1 784,5 | 1 784,3 | 1 719,8 | **1 715,0 (−4,8)** |
| `cpu_s` | 3 896,2 | 3 923,3 | 3 755,3 | **3 968,0 (+212,7)** |
| `n_57014` | 5 | 2 | 0 | **1** |
| lancement / résultat | timer/success | timer/success | timer/success | **timer/success** |

La nuit est **comparable** (`lancement=timer`, `exec_status=0`, `oom=0`,
05:55:33→07:17:36 — partie 33 s plus tôt que la veille, finie 2 min plus
tard). Self-test **VERT**. Contrôle de ce matin (07:30:25 CEST) :
« 59 relevé(s), **38 comparable(s)** ; durée : 10 points, pente
**−21 s/nuit** ; mémoire : 10 points, pente **−24 Mo/nuit** ; horizon 30 j ;
seuil 2 800 Mo » — puis « **rien à dire** ». Les deux pentes sont
**identiques à celles d'hier** au chiffre près. Timer sain, prochain tir
lundi 28/09 07:30:57.

## 2. ⚠️ Durée : +157 s — l'oscillation, pas la dérive

La série tient maintenant en une phrase : **4 685 · 4 916 · 4 941 ·
4 756 · 4 913**. Elle monte, elle descend, elle remonte au même endroit.
La marge sous le garde retombe à **3 187 s (39 % de 8 100)**, ce qui reste
très large.

Le détail par étape, 26→27 :

| étape | 26/09 | 27/09 | Δ |
|---|---|---|---|
| `glissant` | 897,5 | 988,6 | **+91,1** |
| `regime` | 1 503,1 | 1 653,4 | **+150,3** |
| `rejeu` | 75,6 | 82,0 | +6,4 |
| `stabilite` | 240,2 | 232,9 | −7,3 |

**96 % du +157 s est dans `regime` + `glissant`**, et `regime` en porte
96 % à lui seul (+150,3 pour +157 net). `cpu_s` **+212,7 s** : c'est du
calcul réel, pas de la contention machine.

⛔ **Et cette fois le volume va dans l'AUTRE sens** : `lignes_regime`
**120 822 → 115 043 (−4,8 %)**, `lignes_score_zone` 131 554 → 125 782
(−4,4 %). `regime` a coûté **+10 % de temps sur 4,8 % de lignes en
moins**. En trois nuits l'étape a fait **−136,0 puis +150,3** — d'abord à
volume constant, maintenant à volume en baisse.

✅ **Le point de veille ouvert le 26/09 est confirmé, et c'est le seul
résultat solide de la nuit** : `regime` a une sensibilité propre,
d'amplitude ±150 s, décorrélée du volume, sans changement de code.
Ce n'est pas une dérive de durée — le contrôle le dit aussi, pente
−21 s/nuit, silence — mais ce n'est plus un accident : trois nuits.

⚠️ **KAN-3 n'a PAS été rouvert** (voir §5) : rouvrir « bw-pente-duree »
sur un signal qui n'est pas une pente serait mal étiqueter le problème.
Proposition faite à Yann, **non exécutée** : un motif à part,
p. ex. `bw-regime-sensibilite`.

## 3. ⛔ Mémoire : le −64,5 o/ligne d'hier ne se reproduit pas

Les trois franchissements, tous au-dessus du seuil :

```
06:44:31  ⛔ après le rejeu d'archive            : 2 980 Mo  (2 936 le 26)
07:12:12  ⛔ après le score par régime           : 2 843 Mo  (2 893 le 26)
07:16:13  ⛔ après l'oubli de la fenêtre rejouée : 3 340 Mo  (3 317 le 26)
```

La courbe par ligne rejouée **se remet à plat aussitôt après son
décrochage** :

```
21/09 1 979 o · 22/09 1 866 · 23/09 1 818,2 · 24/09 1 784,5
25/09 1 784,3 · 26/09 1 719,8 · 27/09 1 715,0   → −4,8 o/ligne (−0,3 %)
```

À 1 719,8 o/ligne (le taux d'hier), la fenêtre de cette nuit aurait donné
**3 349 Mo** ; elle en a fait **3 340**. Autrement dit le **+23 Mo du
jalon est presque entièrement la croissance de la fenêtre (+0,97 %)**, et
l'avertissement du 26/09 était le bon : les 124 Mo « de structure »
étaient une fluctuation de données, **pas un acquis**. Le jalon reste
**540 Mo au-dessus du seuil**.

✅ Une bonne nouvelle isolée : le **swap au pic redescend de 225,6 Mo**
(2 335,9 → 2 110,3), la hausse d'hier s'efface, et les pages sorties
tombent de 175 818. Le pic système recule de 11,8 Mo — le record de la
série reste celui du 26/09 (3 619,0). Mais le **plancher de swap ne bouge
pas** : toujours pas d'air sous le processus.

Le remède reste la **ligne en tuple** (§2.6, ≈ −1 030 o/ligne cumulés),
avec la mesure `tuple` vs `namedtuple` à la sonde AVANT de choisir
(leçon §2.3). **Rien n'est décidé, rien n'est codé** — et rien n'a été
déployé depuis `af25efb` (21/09).

## 4. ⚠️ Un 57014, hors purge — et la purge encore à vide

`n_57014 = 1`, et il n'est **pas** dans le bloc purge :

```
06:10:57  ⚠️ model_verif_daily [0-999] : HTTP 500 57014
          « canceling statement due to statement timeout » — reprise 1/3
```

La reprise 1/3 a suffi (ni 2/3 ni 3/3 au journal), la nuit est allée au
bout (`✅ terminé (651 830 lignes écrites en base)`). **Même appelant que
le 25/09**, absent le 26/09. **Aucun motif neuf.**

⚠️ **`delete_par_tranches` n'a toujours qu'une seule preuve** — troisième
nuit où la purge ne trouve rien :

```
07:17:24  ⓘ purge model_score_zone : rien à effacer (?as_of=lt.2026-09-20)
07:17:24  ⓘ purge model_character : rien avant le 2027-02-04 — aucune requête lancée
```

La borne a encore avancé d'un jour à vide. Le passage du 25/09 (127 633
lignes, 18 tranches, ≈ 29 s) **reste l'unique épreuve réelle**. Le point 3
du 25/09 est inchangé pour la troisième fois.

## 5. Tickets — trois commentaires, aucune transition

États relevés avant d'écrire (GET `/rest/api/3/issue/…`, HTTP 200) :
KAN-3 **Terminé** (`statusCategory` done), KAN-4 **À faire**,
KAN-5 **À faire**.

- **KAN-4 (`bw-pente-memoire`)** — **laissé OUVERT**, commenté
  (HTTP 201). Aucune des trois conditions de fermeture : jalon
  **3 340 > 2 800** (540 Mo au-dessus), swap au pic **2 110,3 ≠ 0**,
  silence du contrôle encore inertiel (−24 Mo/nuit sur une fenêtre qui
  porte l'avant-21/09). Le commentaire porte les trois franchissements, la
  courbe par ligne et le calcul qui montre que le gain d'hier ne s'est pas
  poursuivi.
- **KAN-3 (`bw-pente-duree`)** — **non rouvert**, **commenté**
  (HTTP 201) : +157 s, la répartition par étape, le découplage
  temps/volume de `regime` sur trois nuits, et la proposition d'un motif
  distinct laissée à l'arbitrage de Yann. Aucune remontée du garde-fou :
  `controle_quotidien.proposition()` n'a rien formulé (pente négative,
  échéance hors horizon), et la marge est à 39 %.
- **KAN-5 (`bw-purge-57014`)** — **laissé OUVERT**, **commenté**
  (HTTP 201) : le 57014 hors purge, sa reprise, et la purge à vide pour la
  troisième nuit — donc pas de seconde preuve, donc pas de fermeture.
  Réouverture du 14/09 toujours inexpliquée.

⛔ Aucun ticket fermé, aucune transition jouée.

## 6. Hors périmètre, relevé sur la nuit

- ✅ **Position : 9 balises divergent du gel (10 j lus), 0 CONFIRMÉE**
  (9 et 0 le 26 comme le 25). **Troisième nuit sans aucune alerte**, pas
  de ligne « maille AROME ». Le cri pour zéro balise du 23/09 reste éteint.
- ⚠️ **`push` (webhook) toujours pas éprouvé** : aucun cri déposé cette
  nuit non plus. Canal d'urgence non testé depuis le 23/09, quatrième nuit.
- ⚠️ `⚠️ 6 ÉCART(S)` au recalcul indépendant (4 le 26, 3 le 25), **tous du
  même motif** — « 0 h appariées ici (< 6) mais la base porte une ligne » —
  et tous en `fcstagrume` : `aemet:9211F` (+24 h), `infoclimat:STATIC0211`
  (+6 h), `mf:48148004` (+24 h), `pioupiou:1479` (+6 h), `aemet:9218A`
  (+6 h), `mf:34274001` (+6 h). La série monte : 3 → 4 → 6.
- `lignes_daily` **70 182** (+95), mais **61 576 détails par tranche**
  contre 65 463 la veille (−5,9 %) — même sens que `lignes_regime`.
- Murphy : **66 871** cases, dont 64 445 décomposées (66 882 le 26).
- ⓘ R2 : 4 écritures, plafond 10, **154,7 Mo** — rien près du plafond.
- `mutations_memoire` : aucune ligne au journal de la nuit ; dette
  antérieure de 2 mutations non vues, inchangée.

## 7. Ce qui a été touché

**VPS** : rien hors les trois commentaires Jira. `tail` du registre,
`journalctl` (contrôle et notation), `list-timers`,
`controle_quotidien.py --verbeux`, lecture de `bw_jira.sh`, trois GET
Jira. Aucun `systemctl`, aucun SQL, aucun rsync, rien écrit dans
`~/balise-watch` ni dans `/etc` (les trois textes de commentaire sont
passés par un `mktemp -d` en 700, effacé après).
`~/.balise-watch-alertes.env` **sourcé**, jamais lu.
**Mac** : cette note et son commit local — **pas de `git push`**.

## 8. Ce qui reste

1. **La mémoire** : décider la ligne en tuple. Le gain par ligne du 26/09
   ne s'est pas reproduit (−4,8 o au lieu de −64,5) : jalon 540 Mo
   au-dessus du seuil, aucun levier de structure déployé depuis le 21/09.
2. **La sensibilité de `regime`** : −136 puis +150 s en trois nuits,
   décorrélée du volume. À arbitrer : motif Jira dédié
   (`bw-regime-sensibilite`) ou simple veille ? **Question à Yann.**
3. **KAN-5** : confirmer le faux mouvement du 14/09 et arbitrer la
   fermeture — `delete_par_tranches` n'a toujours qu'une preuve.
4. **Le webhook `push`** : canal d'urgence non éprouvé depuis le 23/09.
5. **Les écarts du recalcul indépendant montent** : 3 → 4 → 6, toujours le
   même motif et toujours en `fcstagrume`. À regarder si la série continue.
6. `mutations_memoire` : 2 mutations non vues.
7. **Corriger le prompt de la routine** : KAN-5 n'est pas clos depuis le
   10/09 (signalé le 25/09 et le 26/09, toujours pas fait).

Miroir git : `notes-projet/verdict-pente-27-09.md`, commit local `0768711`, pas de push.
