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

```bash
# code
rsync -av model-verif/ vps:/opt/balise-watch/model-verif/
rsync -av ../tools/storage.py vps:/opt/balise-watch/tools/

# variables (mêmes noms que les cinq chaînes existantes)
#   SUPABASE_URL, SUPABASE_SERVICE_KEY
#   STORAGE_BACKEND=r2
#   R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY
#   MODEL_VERIF_BUCKET=model-verif   (bucket à créer côté Cloudflare)

sudo cp systemd/*.service systemd/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now bw-model-collect.timer bw-model-score.timer
systemctl list-timers 'bw-model-*'
```

`collect` tourne à 03 h 15 UTC, `score` à 03 h 55 — quarante minutes
d'écart, largement de quoi laisser la collecte finir (≈ 6 min pour 648
points à 0,25 s la requête, deux fois).

### Avant le premier run

1. **Exécuter le SQL** — `PWA/web/supabase_step35_model_verification.sql`,
   dans le SQL Editor Supabase. **Par Yann, jamais par Claude.**
2. **Créer le bucket R2** `model-verif`.
3. Faire un essai à blanc :
   ```bash
   python3 collect.py --out /var/lib/bw-model-verif --dry-run
   python3 collect.py --out /var/lib/bw-model-verif --limit 5 --skip-obs
   ```

---

## Ce qui n'est pas fait, et qu'il ne faut pas croire fait

- **`station_zone` est vide.** Rattacher une balise à son bassin-versant
  demande de lire le relief (`zoneClass.assignZone` + `watershed`), ce
  qui n'est pas dans ce lot. Conséquence assumée : `collect.py` et les
  étapes 1-3 de `score.py` tournent quand même, mais **les
  accumulateurs et les scores de zone sont sautés, en le disant**. Une
  balise sans zone n'est pas rangée dans une case au hasard.
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
| Quota Open-Meteo | **~694 appels pondérés/nuit** | 648 × (3/14) × (50/10) |
| | soit **6,9 %** du plafond journalier | plafond 10 000/jour, pondéré par IP |
| Horizons réels | AROME 52 h · ICON-D2 52 h · ICON-CH1 34 h | réponse réelle, 72 h demandées |

Le §9.2 tablait sur 250 points et 5 modèles. Le catalogue en compte
**648**, et le lot en suit **10** (8 le 08/08 au matin, plus DMI HARMONIE
et ALADIN CE après cartographie des domaines réels). Le quota reste très confortable, la
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
