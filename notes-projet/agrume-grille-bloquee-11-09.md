# AGRUME — la grille n'était plus publiée depuis 24 h (11/09/2026)

Session Cowork du soir, Desktop Commander + ssh depuis le Mac + API
GitHub depuis le VPS. Point de départ : « AGRUME n'est dispo que jusqu'à
demain 8 h ».

## 22:20 — le symptôme, chiffré

`agrume/grille/index.json` sur R2 :

```
ecrit_le : 2026-09-11T02:54:47Z          ← 19 h sans republication
runs     : 2026-09-11T00:00:00Z  31 échéances (e00 → e30)
           2026-09-10T00:00:00Z  43 échéances
           2026-09-09T03:00:00Z  43 échéances
```

Réseau 00 Z + 30 h = **12/09 06 Z, soit 08:00 locales**. C'est exactement
la borne que Yann voyait à l'écran, et ce n'était pas un bug d'affichage :
c'est la dernière échéance en ligne.

⚠️ **Le produit A, lui, était parfaitement à jour** — `agrume/colonnes/`
portait le réseau 15 Z écrit à 19:30 Z. Ce sont bien DEUX produits, et un
seul était tombé.

## 22:30 — ce qui n'était PAS en cause

Vérifié avant de chercher plus loin, parce que chacun aurait été une
explication plausible :

- **le guet du VPS** : `bw-agrume-poller`, `-paquets` et `-rallonge` sont
  `active running` et déclenchent normalement (HTTP 204 à 14:29, 17:30,
  20:12 pour les paquets ; 15:17, 18:07, 20:57 pour la rallonge) ;
- **les Actions** : les 26 derniers runs de `agrume-colonnes.yml` sont
  `success`, sans exception ;
- **Météo-France** : les 8 paquets sortent à H+3 h comme d'habitude ;
- **les droits R2** : le produit A s'écrit, avec les mêmes clés.

## 22:45 — la cause, lue dans les logs du runner

Dernière ligne de l'étape « Ingérer les colonnes », run #34636165046 :

```
⚠️ PRODUIT B NON PUBLIÉ : Abort — stockage projeté 5.19 Go > seuil 5.0 Go
   Le produit A est écrit et intact ; le run reste vert.
```

C'est `tools/storage.py`, `verifier_dimensionnement()`, seuil
`SEUIL_STOCKAGE_GO = 5.0`. Balayage des 26 derniers runs :

| quand | échéances | grille |
|---|---|---|
| 10/09 18:08 → 11/09 02:27 | 52 | **Abort 5,26–5,39 Go** |
| 11/09 02:27 | 25 | publiée |
| 11/09 02:35 | 31 | **publiée** ← ce que la PWA sert encore |
| 11/09 04:56 → 18:57 (12 runs) | 52 | **Abort 5,19–5,39 Go** |

Les deux seuls runs passés sont ceux qui, à 02:27 et 02:35, n'avaient
encore que 25 et 31 échéances AROME — donc une projection sous le seuil.
**Le garde-fou ne laissait passer que les runs incomplets.**

## Pourquoi maintenant : une décision appliquée à moitié

La couture IFS du 07/09 (lot L22b) a porté le produit B de 52 à **80
échéances** (+144 h). Le jour même, `BW_R2_SEUIL_GO` — l'alerte de
`audit_r2.py`, côté VPS — est passée de 8,5 à 9,2 Go, avec le
commentaire « couture IFS à +144 h (≈ +1,5 Go à trois runs), décision de
Yann, palier 10 inchangé ».

⛔ **Le garde-fou de CHAÎNE, celui qui ARRÊTE, n'a pas suivi.** L'alerte
a été relevée, l'arrêt non — et comme la grille est écrite « sous filet »
(un échec de grille laisse le run vert, à dessein, pour ne pas apprendre
à ignorer le voyant), plus rien ne criait. `agrume-colonnes.yml` le dit
lui-même dans son en-tête ; c'est le prix assumé de ce filet.

⚠️ Et `grille.py` l'avait écrit noir sur blanc à côté de
`RETENTION_RUNS` : « la rallonge poussée au-delà de 51 h se chiffre AVANT
d'être branchée ».

## L'estimation du 07/09 était basse de 70 %

Mesuré sur le run 15 Z du 11/09 (tampons `eNN.bin` **plus**
`colonnes.bin`, qui republie les mêmes valeurs sur l'axe orthogonal) :

| | par run | à 3 runs |
|---|---:|---:|
| 43 échéances (état en ligne) | 0,84 Go | **2,53 Go** (mesuré sur R2) |
| 80 échéances (avec IFS) | **1,73 Go** | **5,19 Go** |

Soit **+2,66 Go**, et non +1,5. Compte R2 au dernier audit (11/09
04:59 Z) : 6,10 Go sur trois buckets, dont 2,53 de grille → projection
**~8,8 Go sur le palier gratuit de 10**, marge 1,2 Go, avec
`BW_R2_SEUIL_GO=9,2` qui criera avant le palier.

## Le correctif — commit `61c089e`, poussé

`tools/storage.py` : `SEUIL_STOCKAGE_GO` 5,0 → **6,0** (60 % du palier),
avec le raisonnement et les chiffres ci-dessus écrits sur la constante.
Le commentaire « marge ×2 sur tout » a été corrigé : ×1,67 pour le
stockage, ×2 pour les écritures.

Arbitrage de Yann entre trois leviers, chiffrés avant de choisir :

| levier | grille | compte R2 | ce qu'on perd |
|---|---:|---:|---|
| **seuil 5,0 → 6,0** (retenu) | 5,19 Go | ~8,8 Go | la moitié de la marge restante |
| couture IFS `FIN_H` 144 → 96 | 4,35 Go | ~7,9 Go | les échéances 96 → 144 h |
| rétention 3 → 2 runs | 3,46 Go | ~7,0 Go | un run de recollement (A25) |

Bancs verts avant commit : `test_storage_cablage`, `test_audit_r2`,
`test_grille`, `test_purge`, `test_separation`, `test_orographie`.

## Ce qui reste

1. ⛔ **Il reste UNE marche, pas deux.** À 8,8 Go sur 10, le prochain
   domaine, le prochain allongement d'horizon ou la prochaine chaîne se
   chiffrent AVANT d'être branchés. Le vrai gisement est
   `colonnes.bin`, qui double la grille pour servir les profils.
2. ⚠️ **Le trou de surveillance est intact.** Le voyant healthchecks
   d'AGRUME ne regarde que le produit A : une grille qui ne se publie
   plus pendant 24 h ne fait rougir personne. Un contrôle de fraîcheur
   sur `index.json` (`ecrit_le` vieux de plus de ~6 h) serait le
   pendant naturel — pas fait, à décider.
3. ⚠️ **Deux seuils pour une même décision.** `BW_R2_SEUIL_GO` (alerte,
   VPS, variable d'environnement) et `SEUIL_STOCKAGE_GO` (arrêt, dépôt,
   constante) se règlent à deux endroits sans que rien ne lie l'un à
   l'autre. C'est ce découplage qui a produit l'incident.
