# `model-verif/` — le job nocturne du score de fiabilité des modèles

Session du 08/08/2026. Conception complète :
`PWA/web/CONCEPTION_SCORE_MODELES_06-08.md` — **§15, §16 et §17 font
foi** en cas de contradiction avec les §8 et §9.

---

## Ce que ça fait

Trois fichiers, deux responsabilités, séparées exprès.

| Fichier | Rôle |
|---|---|
| `collect.py` | **Collecte.** Archive les prévisions des 10 modèles nommés et les observations Pioupiou, en NDJSON gzip sur R2. Ne calcule aucun score. |
| `score.py` | **Notation.** Relit l'archive, apparie prévu/observé, écrit `model_verif_daily`, fait avancer `model_character`, recalcule `model_score_zone`, publie `model_scores.json`. |
| `scoring.py` | **L'arithmétique**, sans réseau ni base. Portage de `src/lib/verifScore.ts`, `modelCharacter.ts` et `regime.ts`. |

Séparer collecte et notation est délibéré : **un bug dans la formule de
score ne doit jamais pouvoir corrompre la collecte**, qui est
irremplaçable. La formule, elle, se rejoue sur l'archive.

---

## ⚠️ Le sondage du 08/08, et ce qu'il a changé

Le §9.1 faisait reposer tout le dispositif sur l'API Previous Runs
d'Open-Meteo, en disant lui-même n'avoir jamais été sondé en direct.
Il l'a été. Résultat mesuré :

| modèle | `wind_speed_10m` | `_previous_day1` |
|---|---|---|
| `meteofrance_arome_france_hd` | 384/384 | **0/384** |
| `meteofrance_arome_france` | 48/48 | **0/48** |
| `meteofrance_arpege_europe` | 72/72 | **0/72** |
| `meteofrance_seamless` | 48/48 | **0/48** |
| `icon_d2` | 48/48 | 48/48 |
| `icon_eu` | 72/72 | 72/72 |
| `gfs_global` | 72/72 | 72/72 (jusqu'à `_day5`) |
| `ecmwf_ifs025` | 72/72 | 72/72 |
| `meteoswiss_icon_ch2` | 72/72 | 72/72 |
| `meteoswiss_icon_ch1` | 72/72 | **0/72** (horizon 33 h — normal) |

**Aucun modèle Météo-France n'a d'historique de runs passés.** HTTP 200,
le bon nombre d'heures, et rien que des NULL — le piège exact qu'ERA5
avait déjà tendu à ce projet. Reproduit sur mars 2026 : ce n'est pas une
panne du jour. La documentation d'Open-Meteo annonce pourtant « les
mêmes modèles que l'API forecast » ; elle a tort.

AROME étant le modèle que lisent réellement les pilotes, **le rattrapage
rétroactif est impossible**. D'où le choix : on archive les prévisions de
tous les modèles chaque nuit. C'est plus lent à démarrer — quinze nuits
avant le premier score à +24 h — mais c'est symétrique.

Corollaire dans l'autre sens : `wind_gusts_10m_previous_day1` rend bien
des valeurs (72/72 sur `icon_d2`). Le §9.1 affirme le contraire.

---

## Installer sur le VPS

Le VPS (OVH, Debian 13, `51.91.102.146`) utilise des **timers systemd**,
pas cron — c'est ce qui porte déjà `balise-entretien` depuis le 03/08, et
`Persistent=true` rattrape un run manqué au démarrage suivant, ce que
cron ne sait pas faire.

> ⚠️ **Cette section a été réécrite le 07/08 APRÈS avoir sondé le VPS,
> et elle décrivait auparavant une machine qui n'existe pas.** Elle
> parlait de `/opt/balise-watch/`, d'un utilisateur `balise` et d'un
> `EnvironmentFile` : les trois sont faux. Le VPS range son code dans
> `~/balise-watch/`, tourne en `debian`, et son `.env` est écrit en
> `export VAR=…`, syntaxe que systemd ne sait pas lire — c'est pour ça
> que `balise-infoclimat.service` passe par un script shell. La recette
> ci-dessous a réellement tourné.

### La vraie machine, mesurée le 07/08

| | valeur |
|---|---|
| Utilisateur | `debian` (l'utilisateur `balise` n'existe pas) |
| Code | `/home/debian/balise-watch/balise-watch-server/` |
| Python | `/home/debian/venv-balise/bin/python3` (**`boto3` n'est PAS dans le python3 système**) |
| Secrets partagés | `~/.balise-watch-r2.env` — `export VAR=…` |
| Alertes | `~/.balise-watch-alertes.env` |
| Chaînes déjà là | **deux** : `balise-entretien`, `balise-infoclimat` (pas cinq) |

⚠️ **`R2_BUCKET="balise-watch-packs"` est dans le `.env` partagé, et
`tools/storage.py` ligne 389 fait `os.environ.get("R2_BUCKET") or defaut`
côté R2.** `MODEL_VERIF_BUCKET` ne sert donc QUE au dos Supabase :
laissée seule, l'archive irait se déverser à la racine du bucket des
packs, HTTP 200 et sans un mot. C'est `run.sh` qui écrase `R2_BUCKET`
après avoir sourcé le `.env`, et `sonde_r2.py` qui vérifie que rien n'a
débordé.

```bash
# 1. code (ce n'est PAS un clone git sur le VPS — rsync)
rsync -av --exclude '__pycache__' model-verif/ \
  debian@51.91.102.146:~/balise-watch/balise-watch-server/model-verif/
# tools/storage.py y est déjà depuis le 03/08 — vérifier par sha256sum
# des deux côtés plutôt que de le réenvoyer à l'aveugle.

# 2. l'état doit EXISTER avant tout démarrage : un ReadWritePaths qui
#    pointe sur un chemin absent fait échouer le montage (piège du 03/08)
sudo install -d -o debian -g debian -m 755 /var/lib/bw-model-verif

# 3. le fichier de secrets propre à cette chaîne — cf.
#    model-verif.env.exemple. Aucune autre chaîne du VPS n'écrit dans
#    les TABLES Supabase, donc SUPABASE_URL / SUPABASE_SERVICE_KEY n'y
#    sont nulle part.
#    ⚠️ Un secret ne se retape pas, il se copie, et on compare par
#    sha256 sans jamais l'afficher.

# 4. deux checks Healthchecks DÉDIÉS, puis leurs URL dans les alertes :
#      BW_MODEL_COLLECT_PING_URL   et   BW_MODEL_SCORE_PING_URL
#    Sans elles, run.sh journalise « PERSONNE NE SURVEILLE CE JOB ».

# 5. les unités
sudo cp systemd/bw-model-*.service systemd/bw-model-*.timer /etc/systemd/system/
sudo systemd-analyze verify /etc/systemd/system/bw-model-collect.service
sudo systemctl daemon-reload
sudo systemctl enable --now bw-model-collect.timer bw-model-score.timer
systemctl list-timers 'bw-model-*'
```

`collect` tourne à 03 h 15 UTC, `score` à 03 h 55 — quarante minutes
d'écart, de quoi laisser la collecte finir (**mesuré le 07/08 : 380 s
pour les 648 points en prévisions, ~9 min avec les observations**).

### Avant le premier run

1. **Exécuter le SQL** — `PWA/web/supabase_step35_model_verification.sql`,
   dans le SQL Editor Supabase. **Par Yann, jamais par Claude.** *(fait
   le 08/08)*
2. **Créer le bucket R2** `model-verif` — et ⚠️ **élargir le jeton R2 à
   ce bucket** : un jeton limité à `balise-watch-packs` rend
   `AccessDenied` sur `PutObject`, ce que le run signale désormais par un
   code de sortie 2 (07/08).
3. Les essais, dans l'ordre — chacun sert à quelque chose :
   ```bash
   ./run.sh collect --dry-run            # l'encadré de quota, aucune requête
   ./run.sh collect --limit 5 --skip-obs # un vrai objet sur R2
   set -a; . ~/.balise-watch-r2.env; set +a
   /home/debian/venv-balise/bin/python3 sonde_r2.py   # ⚠️ le CONTENU, pas la forme
   ./run.sh collect                      # le run complet, à la main
   ./run.sh score                        # 0 ligne le premier soir est NORMAL
   ```

---

## Ce qui n'est pas fait, et qu'il ne faut pas croire fait

- **`station_zone` est vide.** Rattacher une balise à son bassin-versant
  demande de lire le relief (`zoneClass.assignZone` + `watershed`), ce
  qui n'est pas dans ce lot. Conséquence assumée : `collect.py` et les
  étapes 1-3 de `score.py` tournent quand même, mais **les
  accumulateurs et les scores de zone sont sautés, en le disant**. Une
  balise sans zone n'est pas rangée dans une case au hasard.

  Le script qui la remplira, lui, n'a plus rien à décider : il appelle
  `score.write_station_zones(sb, lignes)`, qui écrit `model_zone` PUIS
  `station_zone` dans cet ordre — voir juste en dessous.

- **Aucun score n'a jamais été calculé sur des données réelles.** Les
  bancs d'essai tournent sur des journées fabriquées. Le premier vrai
  chiffre demandera quinze nuits de collecte.
- **Aucun seuil n'est calibré.** Ni ceux de `regime.py`/`regime.ts`
  (25 / 12 km/h), ni ceux de `windEvents.ts`, ni ceux de `watershed.ts`.
- **Le régime est étiqueté sur du 850 hPa, pas sur `crestWind.ts`.**
  C'est un proxy assumé, et les seuils de `REGIME_THRESHOLDS` ont été
  raisonnés sur un vent de crête. Le jour où on calibrera, c'est le
  couple seuil/niveau qu'il faudra reprendre ensemble.
- **Aucun événement n'est noté.** `model_verif_event` existe, rien ne
  l'alimente : le §16.2 a tranché « petit à petit », et les seuils de
  `windEvents.ts` et `breezeConflict.ts` ne valent pas encore d'être
  notés.
- **Pas de backfill Previous Runs.** Écrire un rattrapage pour les
  quatre modèles qui l'ont produirait des chiffres asymétriques,
  impossibles à mettre côte à côte avec AROME sans mentir. La colonne
  `fcst_src` existe pour que ce soit faisable proprement le jour venu.

---

## Qui crée les lignes `model_zone` — décision du 08/08 (lot B)

Trois producteurs se partagent cette table, et **la frontière entre eux
se lit dans le schéma, pas dans un usage** :

| échelon | exemple | producteur |
|---|---|---|
| 1 `basin_landform` | `b45.28_6.51:valley` | le script d'affectation |
| 2 `massif_landform` | `alpes-nord:valley` | `score.py:zone_rows_needed` |
| 3 `landform` | `*:valley` | le SQL step35, une fois |
| 4 `massif` | `alpes-nord:*` | `score.py:zone_rows_needed` |
| 5 `global` | `*:*` | le SQL step35, une fois |

**La raison :** `station_zone.zone_id` porte lui-même une clé étrangère
vers `model_zone` (step35 l. 199). L'échelon 1 doit donc exister *avant*
que la balise ne soit rattachée — donc avant que le job de nuit ne voie
quoi que ce soit. Aucun autre producteur n'est possible, et c'est ce qui
tranche la question.

⚠️ **Et donc le job n'a pas de « filet » pour l'échelon 1** : il serait
du code mort. La contrainte garantit déjà que toute ligne `station_zone`
lue la nuit a sa ligne `model_zone`. La vraie défense est la clé
étrangère elle-même, qui échoue tôt — au moment de l'affectation, en
pleine session, avec un message clair — et non trois heures avant l'aube
dans un journal que personne ne lit.

Le point d'entrée du script d'affectation est
`score.write_station_zones(sb, lignes)` : il écrit `model_zone` puis
`station_zone`, dans cet ordre, en upsert, et il est rejouable.

Deux corollaires, vérifiés au banc (`test_score.py:test_lignes_de_zone`) :

- la case fine d'une balise **sans bassin** est `massif:forme`, celle
  d'une balise **sans bassin ni massif** est `*:forme`. `agg_level` le
  dit désormais honnêtement : avant le 08/08, `fallback_chain`
  étiquetait le premier échelon `basin_landform` quoi qu'il arrive, et
  le score contredisait alors le `kind` de sa propre zone — exactement
  ce que cette colonne existe pour empêcher ;
- `assignZone` rendait `hors-zone:forme` quand ni bassin ni massif
  n'étaient connus : un identifiant que personne n'insérait, donc une
  balise que la clé étrangère refusait. Il rend `*:forme`, dont la ligne
  est déjà semée.

---

## Les bancs d'essai

### `scoring.py` — unité **et parité avec le TypeScript**

`scoring.py` duplique `src/lib/verifScore.ts` & co. **Une duplication
non vérifiée finit toujours par diverger**, et du côté qui n'est pas
testé. D'où un banc qui rejoue les mêmes entrées des deux côtés et exige
des sorties identiques.

```bash
cd PWA/balise-watch-server/model-verif
python3 test_scoring.py --emit-fixtures /tmp/bw-parity/fixtures.json

cd ../../web
rm -rf /tmp/bwp && npx tsc --ignoreConfig \
  src/lib/verifScore.ts src/lib/modelCharacter.ts src/lib/regime.ts \
  scripts/parity-scoring.ts --outDir /tmp/bwp --module esnext \
  --target es2022 --moduleResolution bundler --strict 2>&1 | grep -v TS2591
cd /tmp/bwp && echo '{"type":"module"}' > package.json
find . -name '*.js' -exec sed -i '' -E "s|(from '\.[^']*)'|\1.js'|g" {} \;
TZ=UTC node /tmp/bwp/scripts/parity-scoring.js \
  /tmp/bw-parity/fixtures.json /tmp/bw-parity/ts_results.json

cd - && python3 test_scoring.py --ts-results /tmp/bw-parity/ts_results.json
```

⚠️ **`TZ=UTC` n'est pas décoratif.** `dominantRegime` en TS lit
`new Date(t).getHours()`, donc l'heure locale de la machine. Sans
`TZ=UTC`, le banc échouerait sur un réglage de fuseau et masquerait les
vraies divergences.

⚠️ **L'absence du fichier TS est un échec, pas un saut.** Il faut
`--unit-only` pour l'ignorer, et c'est explicite.

### `score.py`

```bash
python3 test_score.py
```

Aucun réseau, aucune base : `score.py` sépare la lecture d'archive du
calcul pour que ce soit possible. Les entrées sont des lignes NDJSON de
la forme **exacte** que `collect.py` écrit.

---

## Chiffres mesurés le 08/08

| | valeur | source |
|---|---|---|
| Points Pioupiou, France + limitrophes | **648** | catalogue live, pas une estimation |
| Archive de prévisions | **3,1 Ko gzippés / point / nuit** | run réel de `collect.py`, 10 modèles |
| | **2,1 Mo/nuit → 749 Mo/an** | 7,5 %/an du palier R2 gratuit |
| Horizons réels | AROME 52 h · ICON-D2 52 h · ICON-CH1 34 h | réponse réelle, 72 h demandées |

⚠️ **Deux lignes de ce tableau étaient fausses et ont été retirées le
08/08 (après-midi).** Elles annonçaient « ~694 appels pondérés/nuit,
6,9 % du plafond », calculés en `648 × (3/14) × (50/10)`. **La remise
`jours/14` avait été retirée du code le 07/08 au matin**, précisément
parce qu'elle rendait le garde-fou muet et avait coûté 24 points en
`HTTP 429` — mais personne n'avait mis le tableau à jour. Le chiffre
survivait donc dans la doc, et il a été recopié tel quel dans le prompt
de reprise du 09/08 comme une valeur « mesurée ». Elle ne l'était pas.

Le compte juste, tel que `quota_projete` le journalise à chaque run :

| | avant le 08/08 (5 variables) | depuis le 08/08 (8 variables) |
|---|---|---|
| variables × modèles | 5 × 10 = 50 | 8 × 10 = 80 |
| poids d'une requête | 5,00 | **8,00** |
| total du run (648 points) | 3 240 pondérés — **32,4 %** | **5 184 — 51,8 %** |
| pause de la passe prévisions | `BATCH_PAUSE_S` 0,45 s | **`FCST_PAUSE_S` 0,70 s** |
| cadence pondérée | 448/min (plafond 600) | **522/min** |
| seuil du garde-fou journalier | 50 % | **60 %**, justifié dans le code |

---

## Les trois flux archivés (mis à jour le 08/08, après-midi)

| clé R2 | contenu | rattrapable ? |
|---|---|---|
| `fcst/` | 10 modèles × 648 points × 72 h — vent (`speed`, `dir`, `gust`), plus **`precip`, `pmsl`, `t2m` depuis le 09/08** ; `aloft_*` pour ECMWF seul | **NON.** Aucun modèle Météo-France n'a d'historique de runs passés chez Open-Meteo. Une nuit manquée est perdue. |
| `obs/` | Pioupiou, ~4 min de résolution, `speed`/`gust`/`dir` | oui — l'archive Pioupiou reste interrogeable |
| `obsmetar/` | **nouveau le 08/08.** 225 aérodromes servis sur 278 dans la bbox, 9 réseaux, ~22,6 relevés/jour chacun — `speed`, `gust`, `dir`, **`qnh`**, `t2m`, plus `elev` | oui — l'archive Iowa State est rétroactive |

Ce que le METAR apporte et ce qu'il n'apporte pas, **mesuré le 08/08 sur
5 090 relevés réels du 07/08** :

| champ demandé | remplissage | verdict |
|---|---|---|
| `alti` → `qnh` | **100 %** | la référence de pression d'E6, en plaine comme à 2 173 m |
| `tmpf` → `t2m` | 100 % | vérité terrain de la température |
| `sknt` → `speed` | 99 % | vent de plaine, hors biais de site de relief |
| `drct` → `dir` | 83 % | un cap absent reste `None`, jamais 0 |
| `gust` | **0,4 %** | une rafale n'est diffusée que si elle existe |
| `mslp` | **2 %** | **écarté.** Le METAR européen diffuse le QNH, pas la pression SYNOP |
| `p01i` | 100 % servi, **0,00 partout** | **écarté.** Voir ci-dessous |

⚠️ **Il n'y a PAS de vérité terrain de précipitation dans le METAR
européen.** Le champ `p01i` répond, à 100 %, et vaut zéro dans tous les
cas : 2 976 valeurs sur janvier 2026 et 2 880 sur novembre 2025 (4
stations françaises), **aucune non nulle** — contre 251 non nulles sur
1 438 pour deux stations américaines le même mois. Le groupe de
précipitation horaire est une particularité ASOS américaine. L'archiver
aurait produit une colonne de `0.0` qu'on aurait relue comme « il n'a
pas plu » et contre laquelle on aurait noté E4 à tort.

**Conséquence : E4 attend Météo-France.** Sondé le 08/08 :
`public-api.meteofrance.fr` répond **HTTP 401** sans clé, et l'ancien
portail libre `donneespubliques.meteofrance.fr` ne sert plus que du HTML
(les fichiers SYNOP `.csv.gz` n'y sont plus). Il faut donc une clé
applicative sur `portail-api.meteofrance.fr`, à créer par Yann, puis une
variable dans `~/.balise-watch-model-verif.env`. En attendant, la
**prévision** de précipitation est archivée (elle, irréversible) sans sa
vérification — ce qui est le bon ordre, l'archive se rejouant.

Le §9.2 tablait sur 250 points et 5 modèles. Le catalogue en compte
**648**, et le lot en suit **10** (8 le 08/08 au matin, plus DMI HARMONIE
et ALADIN CE après cartographie des domaines réels). Le quota n'est plus
« très confortable » comme l'annonçait cette page : à 51,8 % du plafond
journalier, il reste 4 000 appels pondérés de marge, et c'est cette marge
qui doit absorber un `traces/backfill_packs.py` lancé à la main dans la
journée — depuis la même IP, donc sur le même plafond. La
volumétrie de `model_verif_daily` est en revanche **quatre fois**
l'estimation du §15.2 — à re-mesurer sur un vrai mois plutôt qu'à croire
sur parole.

---

## Les modèles suivis, et pourquoi ceux-là (mis à jour le 08/08)

Question de Yann : « ICON-CH1 n'est pas valable pour les Pyrénées — on a
un modèle de remplacement là-bas ? » Oui, et il manquait à la table.

Domaines cartographiés sur une grille de **805 points** (41-52 N ×
−6-11 E, pas de 0,5°), par requêtes multi-points :

| endroit | modèles fins qui répondent |
|---|---|
| Pyrénées (Ossau) | AROME HD, **DMI HARMONIE 2 km**, KNMI 5,5 km |
| Bretagne (Brest, Rennes) | AROME HD, DMI, KNMI, UKMO |
| Beauce (Chartres) | AROME HD, DMI, KNMI, ALADIN CE, ICON-CH1/CH2, ICON-D2, UKMO |
| Maurienne, Annecy | les dix |

Dans les Pyrénées, `icon_seamless` est **sous** le domaine d'ICON-D2
(`MODEL_COVERAGE.latMin = 43.18`) : l'app y affiche déjà, honnêtement,
« ICON → Global / DWD 11km ». Hors AROME, un pilote pyrénéen n'avait donc
que du 11 à 13 km. **DMI HARMONIE à 2 km y est le premier vrai second
avis à maille fine.**

⚠️ **Répondre n'est pas valoir.** `meteofrance_arome_france_hd` répond
aux 805 points, y compris au large du Portugal ; `ukmo_uk_deterministic_2km`
répond en Maurienne ; `meteoswiss_icon_ch1` répond en Beauce, à 500 km
des Alpes. Open-Meteo sert la donnée bien au-delà de la zone où un modèle
à aire limitée vaut quelque chose. Les boîtes de `localModels.ts` restent
donc rognées à la main — mais elles sont désormais calées sur des bords
mesurés au lieu d'être devinées.

Deux erreurs corrigées au passage, toutes deux dans la table du 07/08 :
`knmi_harmonie_arome_europe` est à **5,5 km** (le 2 km de KNMI, c'est la
variante « netherlands »), et sa boîte s'arrêtait au nord de la France
alors qu'il répond jusqu'aux Pyrénées.

### L'ordre des onglets

Trié par **maille effective au point**, la plus fine à gauche (demande
Yann, 08/08) — `effectiveMeshKmAt` dans `config.ts`. « Effective » parce
que les quatre fixes sont des `*_seamless` dont la maille change avec
l'endroit :

- Maurienne : ICON-CH1 1 km · AROME 1,3 · ICON 2,2 · ARPEGE 11 · GFS 13
- Pyrénées : AROME 1,3 · **DMI 2** · ICON **11** · ARPEGE 11 · GFS 13

Un tri sur la maille nominale mettrait « ICON 2 km » à gauche d'ARPEGE
dans les Pyrénées, où la donnée est du 11 km. Le test est le même que
celui qui décide déjà du libellé (« ICON → Global ») et du badge
(« DWD 11km ») : une seule vérité, trois usages.

À maille égale — trois modèles sont à 2 km sur la Côte d'Azur — c'est le
modèle dont le **domaine est le mieux centré** sur le point qui passe
devant. Même argument que partout ailleurs dans ce fichier : un modèle à
aire limitée vaut le plus au centre et le moins près de ses bords. C'est
un départage géométrique par défaut, en attendant que le score tranche
sur des mesures.

---

## Défauts trouvés dans l'existant, pas encore corrigés

Tous côté TypeScript, aucun ne casse le build.

1. **`modelCharacter.Regime` vaut encore `'gradient' | 'thermal' |
   'calm'`** — la typologie à 3 types du §7.1, abandonnée par le §16.2
   au profit des six de `regime.ts`. Deux types `Regime` coexistent
   dans `src/lib/`, et c'est celui-là que le fichier SQL du 06/08
   recopiait.
2. **`TraitMetric` n'a aucune métrique pour l'ERREUR.** Ses quatre
   valeurs décrivent toutes un biais. Or le §16.1 demande l'erreur
   typique en km/h par régime, et elle doit vivre dans un accumulateur.
   `scoring.py` et le SQL corrigé ajoutent `errKmh`, `mseModel`,
   `msePersist` ; le TS reste à mettre à jour.
3. **`RegimeScore.aggLevel` n'a que 4 valeurs** (`basin | massif |
   landform | global`) alors que `zoneFallbackChain` en rend **cinq** :
   il manque `massif_landform`. Le SQL corrigé porte les cinq.
4. **`dominantRegime` dépend du fuseau de la machine.** Juste dans un
   navigateur français, faux sur un VPS en UTC, où « 10 h - 19 h
   locales » devient 12 h - 21 h heure de Paris en été — et glisse au
   changement d'heure. Le portage Python prend un décalage explicite ;
   le TS gagnerait à faire pareil.

5. **Le commentaire de `OpenMeteoHourly` disait « quand plusieurs
   modèles sont DEMANDÉS ».** La règle mesurée est « quand plusieurs
   modèles SERVENT » : à un point couvert par un seul modèle, la clé
   revient nue (`wind_speed_10m`) et la réponse ne dit pas lequel a
   répondu. Corrigé côté types, et `collect.py` abandonne bruyamment un
   tel point plutôt que d'attribuer la série au hasard. Le client n'est
   pas exposé — ARPEGE et GFS sont mondiaux, donc deux modèles servent
   toujours — mais c'est vrai par accident, pas par construction.
