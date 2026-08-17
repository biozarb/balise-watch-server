# AGRUME — coupe verticale native AROME

**AGRUME** = *AGRégation Unifiée Multi-Échelles*. Nom de travail,
provisoire et assumé comme tel.

> ⚠️ **On n'utilise pas « PIAF »** : c'est la désignation d'un produit
> opérationnel Météo-France (Prévision Immédiate Agrégée Fusionnée), sur
> le même domaine métier et à partir des mêmes données. La Licence
> Ouverte 2.0 interdit explicitement d'induire un tiers en erreur sur la
> source ou la nature de l'information réutilisée.

Ce paquet couvre les **étapes 2 à 6 et 8** de la séquence du lot H :
l'orographie figée, le poller de run, l'ingestion du produit A, le
sondage vertical (et sa confrontation au radiosondage), le produit B, et
la coupe verticale le long d'un segment.

Ne sont **pas** ici : l'étape 7 (marche au raccord par vent fort —
`marche_raccord.py` existe, mais la mesure attend un run venté, absent
jusqu'au 14/08 au moins), le composite PI (9) et le calque altitude (11).

⚠️ **L'étape 10 y est à moitié seulement, et c'est délibéré.** Le
détecteur de front n'est PAS dans ce paquet : il vit dans `gust-front.js`
et il n'a pas été réécrit. `front_altitude.py` lui fabrique une entrée
par niveau, `tools/gust-front-altitude-replay.js` le rejoue. Deux
implémentations d'un même fit divergeraient — c'est le défaut payé deux
fois le 10/08.

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
| `domaine.py` | **toutes** les constantes communes : grilles, niveaux, **les TROIS domaines**, paquets, horizon, raccords |
| `orographie.py` | le sol du modèle, chargé depuis l'artefact figé — et le refus de deviner le paquet |
| `freeze_orographie.py` | extrait les trois orographies **une fois** par domaine (`--domaine`), les découpe, les versionne |
| `data/orographie-nord-alpes.{npz,json}` | l'artefact figé des Alpes (207 Ko), regelé le 16/08 — **111 × 105 = 11 655 colonnes** en 0,025°. ⚠️ Le nom dit « nord-alpes », la boîte descend au Mercantour depuis l'élargissement du 16/08 (43,70-46,45 N × 5,00-7,60 E) : renommer casserait les clés R2 des runs en ligne |
| `data/orographie-pyrenees.{npz,json}` | **celui des Pyrénées** (141 Ko), gelé le 12/08 — 41 × 205 = 8 405 colonnes en 0,025° |
| `data/orographie-tarn-aveyron-herault.{npz,json}` | **celui du Tarn/Aveyron/Hérault** (48 Ko), gelé le 15/08 — 34 × 84 = 2 856 colonnes en 0,025° |
| `freeze_balises.py` | fige l'**axe des balises** de l'archive, en ajout seul |
| `data/balises-nord-alpes.json` | ⚠️ **l'axe COMPLET** : 207 Alpes + 55 Pyrénées + 23 Tarn/Aveyron/Hérault + 15 hors domaine + 3 radiosondages, **303 balises** (64 Ko) au regel du 16/08. Le nom dit « nord-alpes » par continuité — c'est le manifeste qui fait foi |
| `portail.py` | client WCS, avec les six pièges du portail traités |
| `poller.py` | détection de run, back-off borné, **journal de la latence réelle** |
| `quantification.py` | ⚠️ **le FORMAT du produit A** : PARAMS, unités, plafonds, sentinelle, `quantifier()`. Importé par le produit B, AROME-PI et le profil — c'est pourquoi il est resté ICI quand le conteneur est parti dans `verif/` (Lot J, 13/08) |
| `ingest_colonnes.py` | l'ingestion elle-même — un fichier sur le disque à la fois |
| `grille.py` | le produit B : grille 3D du domaine, index, **purge sans jamais lister**, et **`provenance()`** — ce que chaque bloc de chaque échéance doit à quel modèle (Lot L, 17/08) |
| `rafraichissement.py` | **le composite PI publié À PART** (Lot L2, 17/08) : lit `u`/`v` hauteur du produit B par Range, appelle `composite.composer()`, écrit deux jumeaux (`carte.bin` + `colonnes.bin`) sous `agrume/pi/rafraichissement/{domaine}/{run_pi}/`, toutes les heures, depuis le VPS |
| `profil.py` | **le raccord vertical** : axe altitude-mer, masquage, mélange |
| `sonder.py` | lire un profil en un point, en tableau ou en JSON |
| `transect.py` | **la coupe verticale** le long d'un segment, découpée à la demande dans le produit B |
| `couper.py` | lire une coupe, en dessin ASCII ou en JSON |
| `radiosondage.py`, `confronter_sondage.py` | la confrontation au ballon (étape 5 bis) |
| `marche_raccord.py` | **mesure** la marche entre les deux mailles (critère d'acceptation) |
| `sonde_r2.py` | sonde de droits et de purge, sur R2 réel |
| `front_altitude.py` | **étape 10** : fabrique, pour un niveau AGL donné, la grille au format que `gfDetectModel` attend — et ne détecte rien lui-même |
| `test_*.py` | huit bancs hors-ligne, sans réseau ni clé |

⛔ **Ne sont PLUS dans ce paquet depuis le 13/08 (Lot J, arbitrage A3) :**
le conteneur du produit A (`colonnes.py`), `sonder.py`,
`confronter_sondage.py`, `confronter_calque.py` et `marche_raccord.py`
vivent dans **`../verif/`** — ils n'existent que pour vérifier le modèle,
et l'archive n'est plus définitive (rétention glissante 7 jours). Voir
`verif/README.md` ; la règle de dépendance est bancée par
`verif/test_separation.py` : `agrume/` n'importe jamais `verif/`, sauf
`ingest_colonnes.py` et deux bancs, nommés un par un.

---

## Les bancs

```
python3 tools/test_mf_s3.py
python3 agrume/test_orographie.py [--stations /var/lib/bw-model-verif/stations.json]
python3 agrume/test_poller.py
python3 verif/test_colonnes.py
python3 verif/test_purge.py
python3 verif/test_separation.py
python3 agrume/test_profil.py [--archive <colonnes.npz> <manifeste.json>]
python3 agrume/test_radiosondage.py
python3 agrume/test_grille.py
python3 agrume/test_transect.py
python3 agrume/test_composite.py
python3 agrume/test_rafraichissement.py
```

⚠️ **`tools/deploy-agrume-vps.sh` en rejoue 17 SUR LE VPS** avant tout
redémarrage, et s'arrête au premier échec. La liste ci-dessus est celle
qu'on tape à la main ; c'est celle du script qui fait foi.

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
  des champs dédiés `10u`/`10v` ;
- **servir de l'air souterrain** — dans les Alpes, 1000, 950 et 925 hPa
  sont sous le terrain à peu près partout, et le modèle y met des valeurs
  extrapolées parfaitement crédibles à l'affichage ;
- **quantifier l'axe d'altitude en float16** : le pas y vaut 4 m entre
  4 096 et 8 192 m, donc 2 m d'erreur — mesuré — sur l'axe même où l'on
  raccorde deux sources.

---

## Le rafraîchissement PI (Lot L2, 17/08/2026)

Le composite temporel de `composite.py` existait, bancé, depuis le
10/08 — et **il n'avait jamais quitté la mémoire**. Il est désormais
publié, dans un objet à part, écrit par le VPS à chaque ingestion PI.

```
  agrume/pi/rafraichissement/{domaine}/{run_pi}/carte.bin       29,14 Mo
                                              /colonnes.bin     29,14 Mo
                                              /manifest.json
  agrume/pi/rafraichissement/index.json     ← `dernier[domaine]` FAIT FOI
```

**Trois choses à savoir avant de s'en servir.**

- ⛔ **La préséance est publiée, jamais devinée** : cet objet gagne sur
  le produit B **pour `u` et `v` du bloc `hauteur` seulement**, et pour
  les seules échéances qu'il énumère (25 pas de 15 min, 0 → 6 h).
  Partout ailleurs — isobares, surface, `t`/`r`/`tke`, au-delà de
  l'horizon — le produit B reste seul maître. ⚠️ Une valeur non finie
  ici veut dire « rien à en dire » : le client retombe sur le produit B,
  il n'affiche pas un trou.
- ⛔ **C'est `index["dernier"][domaine]` qui désigne le run à lire**, pas
  le `run` du manifeste du produit B (publié 8 fois par jour quand PI
  l'est 24 : le run PI que le client lira n'existe pas encore quand ce
  manifeste-là s'écrit). `dernier` n'avance qu'après les TROIS
  écritures — les deux jumeaux s'écrivent ensemble ou pas du tout.
- ⛔ **`resolutionTemporelleMin` survit au passage, et la provenance
  porte ce qu'il ne peut pas porter.** La table par niveau dit
  « observée (PI), 15 min » sous 500 m/sol — c'est vrai **à `w_PI = 1`**,
  donc jusqu'à 4 h. Au-delà la rampe éteint Δ, et à 6 h la valeur est de
  l'AROME horaire interpolé **à tous les niveaux, 20 m compris**. C'est
  `provenance.par_echeance[*].blocs.hauteur` qui le dit, échéance par
  échéance.

⚠️ **Le cahier des charges du lot se trompait d'échéances, et c'est
mesuré.** Il annonçait « lire les échéances 0→7 du produit B ». Ce n'est
vrai que si les deux runs partent à la même heure. Le 17/08 à 09:37 UTC :
dernier run PI **09 Z**, dernier produit B *ingéré* **03 Z** — donc les
échéances **6 → 12**. Les échéances se déduisent du décalage
(`steps_necessaires()`), et le module **refuse** plutôt que d'extrapoler.
ⓘ Même à décalage nul c'est **0 → 6**, sept échéances et non huit :
l'horizon de PI est 6 h pile.

⛔ **`CACHE_REECRIT`, pas `CACHE_IMMUABLE`.** La clé porte le run PI,
mais les octets dépendent AUSSI du run du produit B disponible à la
composition : « les mêmes octets sortiront toujours de cette clé » est
**faux** ici. Et `CACHE_IMMUABLE` vaut 6 h pour un objet dont la
rétention est de 3 h.

**Mesuré sur le VPS (2 vCPU), run PI 09 Z du 17/08, domaine
111 × 105 :**

| | valeur |
|---|---|
| lu dans le produit B, par Range | **8,16 Mo** (39 Mo en tirant les 7 tampons entiers, 286 Mo pour le run complet) |
| composition | **0,52 s** |
| durée totale du passage | 4,5 s (dont ~3 s de réseau) |
| pic RSS | **363 Mo** (VPS : 3,4 Go disponibles) |
| publié | **58,3 Mo** par run PI · **175 Mo** résidents à 3 runs |

✅ **Vérifié sur les octets SERVIS**, pas sur ceux de la mémoire :
`composite == PI` aux 5 niveaux de Δ tant que `w_PI = 1`, écart max
**0,000e+00 m/s** sur 50 tranches ; et `carte.bin` == `colonnes.bin`
case par case (`--verifier`).

```
python3 agrume/rafraichissement.py --sans-ecriture   # chiffrer sans écrire
python3 agrume/rafraichissement.py                   # rejouer un run à la main
python3 agrume/rafraichissement.py --verifier        # relire ce qui est SERVI
```

---

## La coupe verticale (étape 8, 10/08/2026)

`transect.py` découpe une coupe **à la demande** dans le produit B —
aucun catalogue n'est pré-calculé, et il n'y en aura pas : 40 transects
de 200 points font 8 000 colonnes contre 5 185 pour la grille entière du
domaine. Le catalogue serait plus lourd que la donnée.

```
python3 agrume/couper.py --archive g.npz g.json \
        --de 45.60,5.90 --a 45.45,6.60 --echeance 3
```

**Trois choses à savoir avant de s'en servir :**

- ⛔ **La coupe s'arrête à `solModèle + 3000 m`**, et ce plafond suit le
  relief. Le produit B ne porte AUCUN niveau isobare — ils n'existent
  qu'aux balises, dans le produit A.
- ⚠️ **Plus proche voisin, aucune interpolation horizontale.** Demander
  200 points sur 50 km donne une courbe lisse reposant sur ~25 colonnes.
  La réponse porte donc toujours `nbPoints` **et**
  `nbMaillesDistinctes`, plus le drapeau `escalier`.
- ⚠️ **Pas de rééchantillonnage vertical.** Chaque colonne est servie sur
  SON sol ; l'interpolation à altitude-mer constante est le travail du
  calque altitude (étape 11) et ne sera écrite qu'une fois.

**Vérifié le 10/08 sur le run `2026-08-10T09:00:00Z`** : sur 875
colonnes (125 balises × 7 échéances, 21 875 niveaux), la colonne lue
dans le produit B par `transect.colonne()` est **identique à celle du
produit A** lue par `profil.niveaux_hauteur()`, au même arrondi de
publication près. Les deux passent par des chemins d'indexation
totalement différents — indice plat calculé depuis les métadonnées du
GRIB d'un côté, plus proche voisin sur les axes publiés de l'autre.

ⓘ **Un commentaire démenti par son propre banc** : `point_intermediaire`
annonçait que l'orthodromie et la droite lat/lon « ne diffèrent que de
quelques dizaines de mètres ». Mesuré : **1 215 m sur la diagonale du
domaine** (0,62 maille), 70 m sur 55 km. La réponse publie désormais
`ecartDroiteLatLonM` pour chaque segment demandé.

---

## Le profil vertical, et la seule règle qui le tient

**Une colonne repose sur UN seul sol.** C'est le 0,025°, parce que c'est
la seule maille qui la porte entière.

⚠️ La maille fine n'est **pas** insérée dedans, et ce n'est pas un oubli.
Mesuré sur une colonne réelle : `100 m/sol` en maille fine tombe à 604 m
ASL, `35 m/sol` en 0,025° tombe à 677 m — parce que les deux sols
diffèrent de 138 m ici, de 75 m en médiane, de 643 m au pire. Fusionner
ferait apparaître « 35 m au-dessus du sol » **plus haut** que « 100 m
au-dessus du sol ». La maille fine est donc servie **à côté**
(`profilMailleFine`), avec son propre sol annoncé, et l'écart entre les
deux est **mesuré et publié** (`marcheHybride`) plutôt que dissous dans
un tri par altitude.

Le raccord hauteur ↔ isobares, lui, se fait par mélange à poids linéaire
entre `z_s + 1000` et `z_s + 3000`, par composantes u/v. Et
`ecart_recouvrement()` mesure le désaccord des deux sources **avant** tout
mélange : c'est le test de non-régression du lot, parce qu'**une marche
ne vient jamais de la météo** — elle vient d'une conversion fausse.

✅ Mesuré sur **100 colonnes réelles** (run 06 Z) : écart médian
**0,23 m/s**, d9 0,62, max 1,16 — le critère du lot demande < 1 m/s.

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

**⛔ Et il déclenche DEUX FOIS par réseau, depuis le 14/08.**
`bw-agrume-poller-paquets` part dès que l'archive 0–24 h est complète —
c'est la fraîcheur, la seule chose qu'AGRUME apporte.
`bw-agrume-poller-rallonge` repart quand les échéances 25 → 51 h sont
publiées, et c'est la seule façon d'avoir la coupe à deux jours : la
rallonge du produit B est cherchée à l'instant du dispatch, et
Météo-France publie les échéances lointaines **entre 2 min et 3 h 33
plus tard** (douze réseaux mesurés les 12 et 13/08). Sans ce second
guet, la coupe s'arrêtait à +24 h sur **tous** les runs frais, sans
qu'aucun voyant ne passe au rouge.

**Déploiement du code sur le VPS (Lot P, 13/08) :**
`tools/deploy-agrume-vps.sh` fige la procédure manuelle — rsync de
`agrume/`, `verif/` et `tools/` (les trois, jamais un seul : le piège
déjà payé côté `model-verif/`), sha256 des deux côtés, bancs hors-ligne
rejoués SUR LE VPS, puis redémarrage des seuls services persistants
(`bw-agrume-poller`, `bw-agrume-poller-paquets`,
`bw-agrume-poller-rallonge`). ⛔ Il ne touche jamais
aux timers oneshot ni n'installe de nouvelle unité systemd — ça reste
une action de Yann, une fois, à la main. S'appelle depuis le Mac (jamais
depuis une session cloud — `ssh`/`rsync` passent par Desktop Commander).

⚠️ **C'est pour ça que l'axe des balises et les orographies sont des
artefacts COMMITÉS** et non des fichiers du VPS : l'Action n'a accès ni
à `/var/lib/bw-model-verif`, ni au VPS, ni à Supabase. Un run
d'ingestion est ainsi **autonome et reproductible** — rejouer un run
d'il y a un mois donne le même axe et le même sol qu'à l'époque.

Le cron du workflow (`agrume-colonnes.yml`) n'est qu'un **filet** : il
est calé très tard, et n'existe que pour qu'une panne du VPS ne laisse
pas de trou dans l'archive. Réécrire le même run est sans danger — la
clé porte le run.
⚠️ **Un trou coûte toujours, malgré la rétention glissante du 13/08** :
un run manquant n'est pas un run qu'on rejouera plus tard, c'est une
journée que le scoring ne notera jamais — et les scores, eux, sont
éternels. Mesuré le 13/08 : 2 trous sur les 24 runs théoriques de la
plage couverte, soit 8,3 %.

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

---

## La confrontation au ballon (étape 5 bis, 10/08/2026)

Jusqu'ici le profil n'était vérifié que **contre lui-même** :
`ecart_recouvrement()` mesure si les deux sources d'AROME se contredisent
dans la zone de mélange. C'est un excellent détecteur de conversion
fausse. Ce n'est **pas** une mesure d'exactitude.

    python3 agrume/freeze_orographie.py --radiosondages   # une fois
    python3 agrume/freeze_balises.py --radiosondages-seulement
    python3 verif/confronter_sondage.py --run <run> --station 06610 \
            --date 2026-08-10 --heure 12

⚠️ **LE CHIFFRE À RETENIR, ET IL EST INCONFORTABLE.** Sur la colonne de
Payerne du run 09 Z + 3 h :

| | écart |
|---|---|
| contrôle interne (`ecartRecouvrementMs`) | **0,04 m/s** |
| contre le ballon, même colonne, même instant | **1,73 m/s** (médiane) |

**Un facteur ~40.** Le contrôle interne n'a jamais prétendu mesurer
l'exactitude — mais tant qu'il était le seul chiffre publié, il était le
seul qu'on pouvait citer. Il ne l'est plus.

### Ce qui a été mesuré le 10/08 (n = 2 profils, vent faible)

| | Payerne (06610) | Cameri (16064) |
|---|---|---|
| sol modèle − sol station | −36 m | −41 m |
| hauteur seule | 1,70 m/s (n = 10) | 1,84 (n = 13) |
| **mélange (raccord)** | **1,67** (n = 9) | **2,23** (n = 9) |
| isobares seules | 2,34 (n = 6) | 4,09 (n = 7) |
| tout le profil | 1,73 · d9 2,59 · max 4,66 | 2,00 · d9 4,16 · max 7,20 |
| écart de température | +0,2 °C | +0,2 °C |

✅ **Le raccord n'ajoute pas d'erreur.** C'était la question du lot, et à
Payerne la tranche de mélange fait *mieux* que les deux tranches pures.
⚠️ n = 9 points, un profil : ça oriente, ça ne conclut pas.

⚠️ **La tranche isobare est la pire des trois, et on ne sait pas
pourquoi.** Trois causes s'y superposent et aucune n'est isolable en
l'état : c'est là que le ballon a le plus dérivé (11 à 15 km), c'est là
que le modèle est le plus haut, et à Cameri c'est là que le sondage est
le plus creux (69 niveaux contre 2 848 à Payerne). **Ne pas conclure que
le modèle est mauvais en altitude.**

### Ce que cette comparaison ne prouvera jamais

- **Les deux stations sont en plaine** (491 et 211 m). Elles vérifient
  l'air libre et le raccord, **pas** la couche limite de montagne — qui
  est justement ce qu'AGRUME apporte. Un bon accord à Payerne ne dit rien
  du profil au-dessus d'un décollage à 2 000 m.
- **Le ballon dérive.** Mesuré, pas supposé : 1,0 km à 2 000 m, 2,6 à
  4 000, 7,8 à 8 000 — avec une vitesse d'ascension **supposée** de
  5 m/s, que Wyoming ne publie pas. C'est bien moins que redouté (sous la
  maille 0,025° jusqu'à 2 000 m), mais c'était un jour de vent faible.
- **n restera petit** : deux lâchers par jour et par station.

### Deux défauts trouvés en chemin

⚠️ **Les vents des radiosondages étaient affichés à 51 % de leur valeur.**
Wyoming publie `SPED` en **m/s** et l'écrit dans sa ligne d'unités ;
`index.js` la rangeait dans `speedKt` et le client faisait `× 1,852`.
27,7 km/h à 850 hPa s'affichaient 14,3. Corrigé des deux côtés : l'unité
est désormais **lue**, et un format non reconnu fait échouer le parsing
plutôt qu'inventer une conversion.

⚠️ **8 des 18 stations proposées aux pilotes n'ont aucune donnée** —
404 sur les trois créneaux testés le 10/08 : Nîmes, Cuneo, A Coruña,
Zaragoza, Barcelone, Madrid, Palma, Lisbonne. Cuneo était la seconde
station du plan de ce lot. Le produit, pas AGRUME — mais c'est le même
constat qui a fait passer le lot de Cuneo à Cameri.
ⓘ **Piste** : Innsbruck (11120) répond, en haute résolution, et c'est une
station **de vallée alpine** — exactement ce qui manque ici. Deux
requêtes sur trois ont expiré : fiabilité à mesurer avant d'y compter.
