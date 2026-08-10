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
| `domaine.py` | **toutes** les constantes communes : grilles, niveaux, domaine, paquets, horizon, raccords |
| `orographie.py` | le sol du modèle, chargé depuis l'artefact figé — et le refus de deviner le paquet |
| `freeze_orographie.py` | extrait les deux orographies **une fois**, les découpe, les versionne |
| `data/orographie-nord-alpes.{npz,json}` | l'artefact figé (94 Ko) et son manifeste |
| `freeze_balises.py` | fige l'**axe des balises** de l'archive, en ajout seul |
| `data/balises-nord-alpes.json` | les 125 balises du domaine (26 Ko) |
| `portail.py` | client WCS, avec les six pièges du portail traités |
| `poller.py` | détection de run, back-off borné, **journal de la latence réelle** |
| `colonnes.py` | le produit A : conteneur, quantification, disposition |
| `ingest_colonnes.py` | l'ingestion elle-même — un fichier sur le disque à la fois |
| `grille.py` | le produit B : grille 3D du domaine, index et **purge sans jamais lister** |
| `profil.py` | **le raccord vertical** : axe altitude-mer, masquage, mélange |
| `sonder.py` | lire un profil en un point, en tableau ou en JSON |
| `transect.py` | **la coupe verticale** le long d'un segment, découpée à la demande dans le produit B |
| `couper.py` | lire une coupe, en dessin ASCII ou en JSON |
| `radiosondage.py`, `confronter_sondage.py` | la confrontation au ballon (étape 5 bis) |
| `marche_raccord.py` | **mesure** la marche entre les deux mailles (critère d'acceptation) |
| `sonde_r2.py` | sonde de droits et de purge, sur R2 réel |
| `front_altitude.py` | **étape 10** : fabrique, pour un niveau AGL donné, la grille au format que `gfDetectModel` attend — et ne détecte rien lui-même |
| `test_*.py` | huit bancs hors-ligne, sans réseau ni clé |

---

## Les bancs

```
python3 tools/test_mf_s3.py
python3 agrume/test_orographie.py [--stations /var/lib/bw-model-verif/stations.json]
python3 agrume/test_poller.py
python3 agrume/test_colonnes.py
python3 agrume/test_profil.py [--archive <colonnes.npz> <manifeste.json>]
python3 agrume/test_radiosondage.py
python3 agrume/test_grille.py
python3 agrume/test_transect.py
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
  des champs dédiés `10u`/`10v` ;
- **servir de l'air souterrain** — dans les Alpes, 1000, 950 et 925 hPa
  sont sous le terrain à peu près partout, et le modèle y met des valeurs
  extrapolées parfaitement crédibles à l'affichage ;
- **quantifier l'axe d'altitude en float16** : le pas y vaut 4 m entre
  4 096 et 8 192 m, donc 2 m d'erreur — mesuré — sur l'axe même où l'on
  raccorde deux sources.

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

⚠️ **C'est pour ça que l'axe des balises et les orographies sont des
artefacts COMMITÉS** et non des fichiers du VPS : l'Action n'a accès ni
à `/var/lib/bw-model-verif`, ni au VPS, ni à Supabase. Un run
d'ingestion est ainsi **autonome et reproductible** — rejouer un run
d'il y a un mois donne le même axe et le même sol qu'à l'époque.

Le cron du workflow (`agrume-colonnes.yml`) n'est qu'un **filet** : il
est calé très tard, et n'existe que pour qu'une panne du VPS ne laisse
pas de trou dans une archive qui est définitive. Réécrire le même run
est sans danger — la clé porte le run.

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
    python3 agrume/confronter_sondage.py --run <run> --station 06610 \
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
