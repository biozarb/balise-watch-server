# AGRUME — coupe verticale native AROME

**AGRUME** = *AGRégation Unifiée Multi-Échelles*. Nom de travail,
provisoire et assumé comme tel.

> ⚠️ **On n'utilise pas « PIAF »** : c'est la désignation d'un produit
> opérationnel Météo-France (Prévision Immédiate Agrégée Fusionnée), sur
> le même domaine métier et à partir des mêmes données. La Licence
> Ouverte 2.0 interdit explicitement d'induire un tiers en erreur sur la
> source ou la nature de l'information réutilisée.

Ce paquet couvre les **étapes 2 à 4** de la séquence du lot H :
l'orographie figée, le poller de run, et l'ingestion du produit A.
Les étapes 5 et suivantes (sondage vertical servi, produit B, transect,
composite PI) ne sont pas ici.

---

## Ce qu'il faut savoir avant de toucher au code

Cinq faits mesurés commandent toute l'architecture. Aucun n'est déductible
de la documentation Météo-France, et trois d'entre eux la contredisent.

1. ⛔ **La grille 0,01° n'expose que 4 niveaux hauteur** (10, 20, 50,
   100 m). Les 25 niveaux (10 → 3000 m) n'existent **qu'en 0,025°**.
   Vérifié deux fois, par le S3 (eccodes sur un GRIB réel) et par le WCS
   (`DescribeCoverage`). La 3D sera en 0,025°, ou ne sera pas.
2. ⚠️ **L'orographie ne vit pas dans le même paquet selon la grille** :
   `001/SP3` mais **`0025/SP2`**. `0025/SP3` existe et n'en contient
   aucune. L'erreur serait **silencieuse**, et coûteuse : sur 19 % des
   balises françaises les deux orographies diffèrent de plus de 100 m
   (44 % sur les 125 balises du domaine Nord-Alpes, jusqu'à 643 m).
3. ⛔ **Le WCS ne rend que des coupes 2D.** Une requête = un paramètre ×
   un niveau × une échéance × une boîte. Aucun groupement. Quota mesuré :
   premier 429 à la requête 103–105.
4. ✅ **Le goulot est le réseau, jamais le CPU.** Débit S3 16–21 Mo/s,
   parsing ~21 ms par message décodé, pic mémoire 88 Mo pour digérer un
   fichier de 818 Mo. La seule contrainte matérielle est le **disque du
   runner (14 Go)**.
5. ⚠️ **Le modèle place les balises ~150 m TROP BAS**, pas trop haut
   (médiane −174 m en 0,01°, −135 m en 0,025°, n = 109). C'est l'inverse
   de ce qu'une première version du lot annonçait.

---

## Les fichiers

| fichier | rôle |
|---|---|
| `domaine.py` | **toutes** les constantes communes : grilles, niveaux, domaine, paquets, horizon, raccords |
| `orographie.py` | le sol du modèle, chargé depuis l'artefact figé — et le refus de deviner le paquet |
| `freeze_orographie.py` | extrait les deux orographies **une fois**, les découpe, les versionne |
| `data/orographie-nord-alpes.{npz,json}` | l'artefact figé (94 Ko) et son manifeste |
| `portail.py` | client WCS, avec les six pièges du portail traités |
| `poller.py` | détection de run, back-off borné, **journal de la latence réelle** |
| `colonnes.py` | le produit A : conteneur, quantification, disposition |
| `ingest_colonnes.py` | l'ingestion elle-même — un fichier sur le disque à la fois |
| `marche_raccord.py` | **mesure** la marche entre les deux mailles (critère d'acceptation) |
| `test_*.py` | quatre bancs hors-ligne, sans réseau ni clé |

---

## Les bancs

```
python3 tools/test_mf_s3.py
python3 agrume/test_orographie.py [--stations /var/lib/bw-model-verif/stations.json]
python3 agrume/test_poller.py
python3 agrume/test_colonnes.py
```

Tous tournent **sans réseau et sans clé**. Ils ne vérifient pas que le
code « marche » : ils vérifient les quatre façons qu'il aurait de casser
en silence.

- charger **deux fois la même orographie** (le test échoue si l'écart
  médian des |différences| est nul) ;
- **attendre indéfiniment** un run publié, parce que le portail rend le
  même `NoSuchCoverage` pour « pas encore là » et pour « ça n'existe
  pas » ;
- **quantifier trop grossièrement** — le float16 a un pas *relatif*, donc
  0,25 K à 300 kelvins : la température est stockée en °C, et le banc
  mesure le facteur 8 que ça fait gagner ;
- **laisser un trou en bas de colonne**, parce que le vent n'est servi
  qu'à partir de 20 m sur les niveaux hauteur et que les 10 m viennent
  des champs dédiés `10u`/`10v`.

---

## Où ça tourne

```
  VPS (allumé en permanence)          GitHub Actions (éphémère, gratuit)
  ─────────────────────────           ──────────────────────────────────
  poller.py  ──── dispatch ─────▶     ingest_colonnes.py
  (quelques centaines d'octets        (7 Go de GRIB, décodage eccodes,
   par interrogation)                  écriture sur R2)
```

La seule propriété unique du VPS est d'être **allumé en permanence** :
une Action est un cron, elle ne peut pas guetter. Le VPS **décide
quand**, l'Action **fait le travail**. Le VPS ne touche jamais un GRIB.

⚠️ La clé Météo-France vit sur le VPS (`~/.balise-watch-model-verif.env`,
mode 600) et **n'en sort pas**. Le miroir S3, lui, est sans clé — d'où la
séparation stricte entre `tools/mf_s3.py` (sans clé) et
`agrume/portail.py` (avec).

---

## Ce qui est mesuré, et ce qui ne l'est pas

**Mesuré le 10/08/2026**, sur le run `2026-08-10T03:00:00Z`, 125 balises
du domaine × 7 échéances (0–6 h) :

| | valeur |
|---|---|
| balises dans le domaine Nord-Alpes | **125** sur 648 au référentiel |
| téléchargé | 2,07 Go en 2,2 min (16,0 Mo/s) |
| parsing | 24 s pour 906 champs décodés sur 2 955 balayés |
| **pic disque** | **820 Mo** (un fichier à la fois ; plafond du lot 10 Go) |
| durée totale | **2,9 min** (alerte au-delà de 30) |
| archive produite | **185 Ko** |

Extrapolé à 0–24 h : ~7,4 Go, ~9 min, **~660 Ko d'archive par run** —
soit **~1,9 Go par an** à 8 runs/jour. ⚠️ Le §4.1 du lot annonçait
« 32 Mo/run » pour le produit A : c'était un ordre de grandeur pour
648 balises et un autre format. **La mesure donne ~50 fois moins.**
Le palier R2 gratuit n'est plus un sujet pour ce produit.

⚠️ **Ce qui n'est PAS mesuré**, et qu'il ne faut pas présenter comme
acquis :

- **La latence de mise à disposition.** Le poller tourne depuis le
  10/08 et n'a pour l'instant que des **bornes supérieures** (le run
  était déjà là à la première interrogation). Une borne n'est pas une
  mesure. `poller.py --rapport` le dit explicitement tant que ce n'est
  pas encadré.
- **La marche au raccord de mailles, au-delà d'un run.** Mesurée sur le
  run 03 Z, 0–6 h, 125 balises : écart médian **0,67 m/s** à 100 m/sol
  (q3 1,21 · d9 2,00 · max 4,95 · n = 875), écart d'angle médian 6,8°.
  ⚠️ **Un seul run, de nuit, par vent faible** — dans ces conditions un
  écart absolu petit peut être un écart relatif grand. À rejouer par vent
  fort avant d'en conclure quoi que ce soit.
- **Le raccord hauteur/isobares** (§3.3 du lot) : pas encore implémenté,
  donc pas encore vérifié.
