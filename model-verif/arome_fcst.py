#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/arome_fcst.py — AROME lu sur R2 entre dans le scoring
#                                          (Lot S0.5, 22/08/2026)
#
#  Un COLLECTEUR, pas un scoreur — jumeau d'`agrume_fcst.py`, sur un
#  autre produit. Il lit les tuiles de vent 10 m qu'`arome-wind/
#  ingest.py` publie sur R2 toutes les 3 h, y prend la valeur À LA
#  COORDONNÉE DE CHAQUE BALISE, et l'écrit dans une archive NDJSON gzip
#  au format EXACT que `collect.py` produit pour les modèles
#  Open-Meteo. `score.py` relit ce flux à côté du sien et n'a rien à
#  savoir d'AROME.
#
#  ⛔ CE FLUX NE CONSOMME AUCUN PONDÉRÉ OPEN-METEO, ET C'EST SA RAISON
#  D'ÊTRE. Le lot S0.3 a mesuré que 2 938 balises d'observation de vent
#  — 83 % de l'archive — ne produisent aucune ligne de score et n'en
#  produiront jamais par Open-Meteo : la fenêtre horaire de la collecte
#  est pleine à 99,6 %, et Yann garde le palier gratuit (arbitrage n°1
#  du S0.3, tranché le 22/08). AROME, lui, est DÉJÀ sur R2 et couvre
#  les 2 938 sans exception.
#
#  ═══════════════════════════════════════════════════════════════════
#  ⛔ CE N'EST PAS `geopair` DÉGUISÉ, ET IL FAUT LE LIRE AVANT DE CRIER
#  ═══════════════════════════════════════════════════════════════════
#
#  La note du lot S1 (§3.2) INTERDIT l'appariement géographique du
#  vent, et elle a raison. Si vous lisez « on note windsmobi sur du
#  vent » et que vous avez le réflexe de crier au geopair, ce réflexe
#  est bon. Voici la réponse, sur place :
#
#   • `geopair` déplace l'OBSERVATION. Il compare le vent mesuré ICI à
#     une prévision faite LÀ-BAS, à 40 km. Le désaccord des deux SITES
#     entre alors dans l'erreur du modèle — et tout le lot S2 existe
#     parce que ce biais de site est énorme. Interdit, et ça le reste.
#
#   • Ici, on lit le modèle À LA COORDONNÉE DE LA BALISE. La grille
#     `arome/sol` est au pas de 0,01° (~1,1 km) : le point lu est DANS
#     LA MAILLE de la balise, à 0,35 km médian (mesuré, §« journal »
#     ci-dessous : le run le dit à chaque nuit). C'est exactement ce
#     que `collect.py` fait déjà en demandant `latitude=…&longitude=…`
#     à Open-Meteo, qui rend elle aussi la maille la plus proche.
#
#  ⇒ La différence entre les deux chemins est de PLOMBERIE, pas de
#  géographie. La borne du S1 §3.2 n'est pas franchie et doit rester
#  écrite. Le garde-fou est `DIST_MAX_KM` : au-delà, le point n'est
#  plus dans la maille de la balise, et la balise SORT — comptée et
#  nommée dans le journal, jamais rattrapée par un rayon.
#
#  ═══ LES DÉCISIONS DE CE LOT, ET CE QU'ELLES COÛTENT ═══
#
#  1. ⛔ **Le modèle s'appelle `arome_r2`, pas `meteofrance_seamless`
#     ni `meteofrance_arome_france_hd`.** La tuile porte
#     `"model": "meteofrance_seamless"` (`arome-wind/ingest.py`
#     l. 123) alors que son contenu vient de `pnt/{ref}/arome/001/SP1/`,
#     soit de l'AROME-HD 0,01° PUR — le libellé est un vestige (entrée
#     BUGS.md du S0.3). Trois raisons de ne pas le reprendre :
#     `collect.py` interdit les modèles `*_seamless` avec sa raison
#     écrite ; `model_verif_daily.model` porte un CHECK
#     `not like '%\\_seamless'` qui ferait échouer l'upsert ENTIER ; et
#     `meteofrance_arome_france_hd` existe déjà côté Open-Meteo — le
#     réutiliser ferait un modèle dont les lignes ne veulent pas dire
#     la même chose selon la balise.
#     ⓘ Le nom est du `text` libre : il se change par un `update` tant
#     qu'il n'a pas voyagé dans `model_scores.json`. C'est l'arbitrage
#     n°3 du S0.3 ; il est ici tranché en `arome_r2` — court, distinct,
#     et il dit d'où vient la lecture, comme `agrume`.
#
#  2. ⛔ **`arome_aloft_*`, PAS `aloft_*`, ET LA DIFFÉRENCE N'EST PAS
#     COSMÉTIQUE.** `daily_rows` choisit le vent d'altitude de
#     référence ainsi :
#         for row in snapshots.get(0, []):
#             if "aloft_speed" in row:
#                 ref_by_st[f"{source}:{station_id}"] = row
#     — LE DERNIER GAGNE, et `snapshot_rows` lit `fcst` D'ABORD. Écrire
#     `aloft_speed` sur nos lignes changerait donc le régime des 570
#     balises Pioupiou déjà notées : il viendrait d'AROME au lieu
#     d'`ecmwf_ifs025` (`collect.REGIME_REF_MODEL`), en silence, sur
#     13 795 lignes par nuit, alors que le pavé de `day_regime` dit
#     « un seul modèle de référence, le même pour tout le monde ».
#     ⇒ On écrit la donnée dès la première nuit — l'arbitrage n°6 du
#     S0.3 le demande et il a raison : les tuiles sont RÉÉCRITES toutes
#     les 3 h, il n'y a AUCUNE archive des runs passés, donc ne pas
#     l'écrire obligerait à tout rejouer, ce qui est impossible. Mais
#     on l'écrit sous un nom que `score.py` ignore. La décision « d'où
#     vient le régime des balises AROME/R2 » reste entière, et elle se
#     prendra plus tard SANS rien rejouer : c'est un renommage.
#
#  3. ⛔ **RUNS_ADMIS = (0, 3), et le job archive AUJOURD'HUI.**
#     `agrume_fcst.py` archive HIER, parce que le produit A est encore
#     sur R2. Ici, NON : `arome-wind/ingest.py` réécrit ses tuiles EN
#     PLACE à chaque run (`CACHE_REECRIT`, « bucket entièrement
#     mutable »), 8 fois par jour. La grille d'hier n'existe plus. Le
#     job doit donc lire LE JOUR MÊME, dans la fenêtre où un run admis
#     est en ligne — mesuré le 22/08 : tuiles `sol` écrites à
#     05:34:38 Z, manifeste à ~05:42 Z, prochain passage de l'Action
#     à 08:00 Z (`cron: "0 2,5,8,11,14,17,20,23 * * *"`).
#     ⇒ Timer à 07:00 UTC. ⛔ IL VALAIT 06:00 JUSQU'AU 30/08, et cette
#     valeur reposait sur UNE observation. Douze mesures prises le
#     30/08 sur les horodatages S3 disent que le run 03 Z n'est jamais
#     exploitable (SP1 ∩ IP1) avant 05:40, au pire 05:49 : lire à 06:00
#     ne laissait pas la place aux 12-19 min d'ingestion. La chaîne ne
#     tenait que par le run 00 Z, prêt vers 03:00 — jusqu'au 30/08, où
#     il a eu trois heures de retard et la journée a été perdue.
#     Cf. le pavé de `bw-model-arome.timer` et le filet de 05:55 Z. L'archive de la journée J est prête 22 h avant que
#     `bw-model-score` la lise (03:56 Z le lendemain).
#     ⚠️ La borne (0, 3) est reprise d'AGRUME et pour la même raison,
#     qui est un point de COMPARABILITÉ : un run de 15 Z couvrirait
#     encore 9 heures de la journée, à +0…+8 h, soit dix heures de
#     fraîcheur d'avance sur les autres modèles sous le même intitulé
#     « +6 h ». On préfère une journée SANS ligne AROME à une journée
#     où AROME gagne par l'horaire.
#
#  3 bis. ⛔⛔ **ET LE POINT DE COMPARABILITÉ QUI MANQUAIT À LA
#     DÉCISION 3 : NOS JOURNÉES N'ONT PAS 24 HEURES.**
#     La décision ci-dessus protège la comparabilité contre un run trop
#     frais. Elle ne dit rien de la seconde, mesurée seulement le 27/08
#     (lot L4) : `arome-wind/ingest.py::keep_step()` ne garde qu'une
#     échéance sur COARSE_EVERY = 3 dans la fenêtre `is_night_utc`,
#     soit [22, 04[ UTC — six heures d'horloge dont il n'en reste que
#     deux. Nommément, pour le run 00 Z, `arome_r2` n'a AUCUNE valeur
#     aux heures **01, 02, 22 et 23 UTC** (vérifié au L4 sur les 4 302
#     lignes du 26/08), là où `agrume` en a 24 sur 24.
#     ⇒ ⚠️ **`n_hours` VAUT 19 OU 20, PAS « 20 ».** Le L4 avait mesuré
#     20 sur une journée servie par le run 00 Z ; remesuré le 01/09 sur
#     les trois nuits des 29, 30 et 31/08 (11 654 à 11 699 balise-jours
#     chacune), le mode est **20 le 29/08 aux deux échéances**, puis
#     **19 à +6 h et 20 à +24 h les 30 et 31/08** — la valeur dépend du
#     run retenu par `pick_run()` et de l'échéance, pas seulement du
#     filtre. Contre **24** pour tous les modèles Open-Meteo aux mêmes
#     nuits. Au niveau des cases publiées (fichier servi du 01/09) :
#     19,6 échéances par balise-jour à +6 h et 19,9 à +24 h, contre
#     23,8 à 23,9 pour les onze autres, sur **851 cases**.
#     ⚠️ *Écrire « 20 » aurait été une constante là où il y a une
#     distribution.* Le chiffre publié par l'écran du L14 est le
#     rapport mesuré case par case, jamais cette valeur-ci.
#     ⛔ ET CE N'EST PAS NEUTRE POUR LE SCORE. `err_vec_med` est une
#     médiane SUR LES HEURES DISPONIBLES : les quatre qui manquent sont
#     les heures calmes de la nuit, celles où l'erreur est petite. Les
#     retirer remonte la médiane. Mesuré au L4 sur 1 245 balise-jours
#     appariés : **63 % du plancher de +0,28 km/h d'`arome_r2` vient de
#     là** — plus que l'arrondi des tuiles (27 %, décision 5) et que le
#     point lu (10 %) réunis. Ce n'est pas un défaut de prévision,
#     c'est un défaut de COMPARABILITÉ, et c'est la cause DOMINANTE :
#     aucun des quatre suspects écrits par l'audit (§0.3, §2.2) ne la
#     nommait, et cet en-tête non plus.
#     ⇒ **Arbitrage de Yann, 27/08 : on ne touche ni aux tuiles ni au
#     scoring — on PUBLIE le nombre d'heures.** Le rapport
#     `n_hours / occurrences` est affiché à côté de chaque rang depuis
#     le lot L14 (01/09), côté web. Corriger `keep_step()` ferait
#     grossir les tuiles pour toutes les cartes du site afin de
#     réparer une seule colonne d'un seul tableau ; rendre le chiffre
#     LISIBLE coûte une division.
#     ⛔⛔ **ET AROME/R2 N'EST PAS SEUL — TROUVÉ EN VÉRIFIANT CE PAVÉ,
#     LE 01/09, ET AUCUN LOT NE L'AVAIT NOMMÉ.** Le L4, l'audit et le
#     prompt du L14 parlent tous d'`arome_r2` comme du cas unique. Sur
#     les trois nuits des 29, 30 et 31/08, `model_verif_daily` dit
#     autre chose, et à une AUTRE échéance :
#       · `dmi_harmonie_arome_europe` à **+48 h : 12 heures** par
#         balise-jour (554 à 557 balise-jours sur ~570, les trois
#         nuits) — la MOITIÉ de la journée — contre 24 à +6 h et +24 h ;
#       · `chmi_aladin_central_europe_2km` à **+48 h : 19 heures**
#         (509 à 514 balise-jours), contre 24 aux deux autres échéances.
#     Ce n'est donc pas un défaut de NOTRE chaîne de lecture, c'est une
#     propriété de la profondeur d'archive de chaque fournisseur — et
#     elle frappe l'échéance la plus lointaine, celle où les modèles se
#     ressemblent le plus. ⓘ Dans ces cases-là, le modèle noté sur le
#     moins d'heures est aussi celui qui affiche la plus petite erreur
#     (DMI 5,71 km/h contre 5,77 à 6,74 pour les cinq autres, case
#     `*:*` +48 h du 01/09) — ce qui est exactement le sens attendu, et
#     exactement ce que l'écran du L14 doit faire voir.
#     ⚠️ Ce pavé vit dans `arome_fcst.py` et parle de deux modèles qui
#     n'y passent pas : c'est assumé, parce que c'est ici qu'un lecteur
#     va chercher « pourquoi ce modèle n'a pas ses 24 heures », et
#     qu'une note vraie au mauvais endroit vaut mieux qu'aucune note.
#
#     ⚠️ Si `keep_step()` change un jour, cette décision et l'écran du
#     L14 deviennent faux ENSEMBLE : le second cessera simplement
#     d'avertir (l'écart tombera sous son seuil), mais ce pavé, lui,
#     restera à mentir. Le remesurer avant de le croire.
#
#  4. ⚠️ **`fetched_at` porte l'heure du RUN**, comme AGRUME et pour la
#     même raison : ce job ne fait aucun appel d'API. Conséquence sur
#     la SEULE colonne qui en dépend, `lead_exact_h` : la nôtre se
#     compte depuis 00:00 Z, celle des modèles Open-Meteo depuis notre
#     appel de 03:19 Z. AROME/R2 affichera donc ~3,3 h de PLUS pour un
#     même run. Les scores eux-mêmes (`err_vec_*`, `mse_*`, `bias_*`)
#     n'en dépendent pas : seule la colonne de diagnostic est
#     asymétrique, et elle l'est DANS LE SENS DÉFAVORABLE à AROME/R2.
#
#  5. ⚠️ **La vitesse des tuiles est ARRONDIE À L'ENTIER**, et on ne le
#     corrige pas. `arome-wind/ingest.py::_ms()` arrondit pour une
#     raison de TAILLE DE FICHIER, pas de physique (« erreur maximale
#     0,5 km/h sur une flèche de carte »).
#
#     ⛔⛔ **CE PAVÉ A DIT « +0,1 %, NÉGLIGEABLE » PENDANT CINQ JOURS,
#     ET C'ÉTAIT LA MAUVAISE GRANDEUR.** Le raisonnement écrit ici
#     était : quantification ±0,5 km/h ⇒ ~0,29 km/h en RMS ⇒ ajoutée en
#     QUADRATURE à une erreur modèle de 5,7 km/h, 5,71, soit +0,1 %.
#     Ce calcul est JUSTE — et il porte sur le RMS, quand le classement
#     publié lit une MÉDIANE. La quadrature ne s'applique pas à elle.
#     ⇒ Mesuré au lot L4 (27/08), sans aucune observation, sur
#     **24 900 balise-heures** : `‖v(arome_r2) − v(agrume)‖` vaut
#     **0,30 km/h en médiane** (p90 0,50, max 0,50 — la borne théorique,
#     retrouvée), et l'arrondi seul en explique la totalité. Sur le
#     score, il pèse **27 % du plancher de +0,28 km/h** d'`arome_r2`
#     (décomposition appariée, 1 245 balise-jours), pas 0,1 %.
#     ⓘ Sur `err_vec_rms` — la colonne du duel L1 — l'ordre s'inverse
#     et l'arrondi redevient le premier terme (51,3 % contre 32,2 %
#     pour les heures manquantes) : le RMS voit bien la quantification
#     que la médiane absorbe, exactement comme le raisonnement en
#     quadrature ci-dessus le laissait attendre. **Les deux lectures
#     sont vraies sur leur propre grandeur ; une seule décrit ce que
#     l'écran publie.**
#     ⇒ Conclusion INCHANGÉE — à écrire, pas à corriger, et toujours
#     DÉFAVORABLE à AROME/R2, jamais l'inverse — mais pour un poids
#     douze fois plus grand, et derrière une cause que ce pavé ne
#     nommait pas du tout (décision 3 bis, 63 %).
#     ⚠️ *Une estimation juste sur la mauvaise grandeur se lit comme
#     une mesure.* Celle-ci a survécu cinq jours parce qu'elle était
#     chiffrée.
#
#  6. ⭐ **On écrit AUSSI les 570 Pioupiou déjà notées**, en doublon
#     apparent avec `meteofrance_arome_france_hd` d'Open-Meteo. C'est
#     le seul moyen d'obtenir la mesure qui compte : NOTRE chaîne de
#     lecture confrontée à CELLE d'Open-Meteo, sur les mêmes balises,
#     le même jour, le même modèle. Le lot I disait déjà ça d'AGRUME
#     (« un écart LARGE serait un défaut de l'une des deux chaînes,
#     pas une nouvelle ») ; ici c'est un contrôle plus serré encore,
#     même modèle et même maille. Et ça ne coûte RIEN : mesuré le
#     22/08, les 2 938 candidates demandent 49 tuiles, les 3 714
#     points de tous les réseaux réunis en demandent… 49.
#
#  7. ⓘ **On écrit aussi les 278 aérodromes `metar`.** Le S1 §3.2 les
#     écartait du vent parce que « leur vent n'a aucun point de
#     prévision à leur propre coordonnée » — cette raison TOMBE ici
#     (215/215 dans l'emprise, mesuré). Écrire leur prévision ne
#     tranche RIEN : sans `obsmetar_key` dans `score.OBS_KEY_FUNCS`,
#     ces lignes ne produisent aucun score. C'est l'arbitrage n°8 du
#     S0.3, laissé ENTIER à Yann — mais avec la donnée déjà là le jour
#     où il le tranche, puisqu'elle n'est pas rejouable.
#
#  ═══ CE QUE CE FLUX NE PEUT PAS DIRE ═══
#
#  ⛔ Une balise notée contre AROME SEUL n'est pas comparable à une
#  balise notée contre neuf modèles. Ce n'est pas un demi-score : c'est
#  un score qui répond à une AUTRE question. Ce qu'il peut dire :
#  « AROME bat-il la climatologie et la persistance ici ? » — les deux
#  références se calculant depuis les OBSERVATIONS, elles existent sans
#  les huit autres modèles. Ce qu'il ne peut pas dire : quel modèle est
#  le meilleur dans cette case.
#  ⚠️ Et le quorum de zone se compte PAR MODÈLE : une case fine avec
#  2 Pioupiou (9 modèles) et 3 windsmobi (AROME seul) devient
#  publiable POUR AROME et reste sous quorum pour les huit autres.
#  `inference.rank_models` rend alors `rank = 1, reason = "ok"` — un
#  « 1ᵉʳ sur 1 » qui se lirait à l'écran comme « AROME est le meilleur
#  ici ». Le garde-fou est dans `inference.py` (lot S0.5) et le banc
#  `test_arome_fcst.py::test_classement_un_seul_modele` le tient.
#
#      python3 arome_fcst.py                       # aujourd'hui, run 00 Z
#      python3 arome_fcst.py --day 2026-08-22
#      python3 arome_fcst.py --dry-run             # tout lire, ne rien écrire
#      python3 arome_fcst.py --sans-aloft          # sauter arome/alt/850
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import bisect
import json
import math
import os
import pathlib
import sys
import time
from datetime import datetime, timedelta, timezone

_ICI = pathlib.Path(__file__).resolve().parent
for _p in (_ICI.parent / "tools",):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

from collect import temoin, upload_r2, write_ndjson_gz     # noqa: E402
from r2_lecture import bucket_r2, prefixe_lecture          # noqa: E402
from score import fcst_arome_key                           # noqa: E402

# ══════════════════════════════════════════════════════════════════
#  CONSTANTES
# ══════════════════════════════════════════════════════════════════

#: Le nom du modèle dans `model_verif_daily` (décision 1 de l'en-tête).
#: La colonne est du `text` libre, seul CHECK : `not like '%\\_seamless'`.
#: Le libellé lisible vit dans
#: `src/lib/stationScore.ts::STATION_MODEL_LABELS`.
MODEL = "arome_r2"

#: L'archive est horaire, et `t0`/`step_s` est le contrat de
#: `score.fcst_times_ms`.
STEP_S = 3600

#: ⛔ Décision 3 de l'en-tête. La borne est un point de COMPARABILITÉ,
#: pas une commodité d'horaire.
RUNS_ADMIS = (0, 3)

#: Le bucket des grilles. ⚠️ CE N'EST PAS CELUI DU MODULE DE SCORING, et
#: ce n'est pas non plus « wind-grid » : `wind-grid` est le nom du DOS
#: SUPABASE (`bucket_env`), le bucket R2 réel s'appelle
#: `balise-watch-grids`. Mêmes noms de variables qu'`agrume_fcst.py`,
#: exprès — deux noms pour une seule notion, c'est ainsi qu'on lit dans
#: le mauvais bucket sans s'en apercevoir.
BUCKET_R2_ENV = "AGRUME_R2_BUCKET"
BUCKET_R2_DEFAUT = "balise-watch-grids"
BUCKET_SUPABASE_ENV = "AGRUME_BUCKET"
BUCKET_SUPABASE_DEFAUT = "wind-grid"

PREFIXE_SOL = "arome/sol/"
PREFIXE_ALT = "arome/alt/{niveau}/"

#: Le niveau du vent d'altitude. ⚠️ Il doit rester ÉGAL à
#: `collect.REGIME_LEVEL` (« 850hPa ») : le jour où l'on décidera que le
#: régime des balises AROME/R2 vient d'AROME (arbitrage n°6 du S0.3),
#: les deux séries devront parler du même niveau, sinon on comparera des
#: journées classées à 850 hPa avec des journées classées ailleurs.
ALOFT_HPA = 850
ALOFT_LEVEL = "850hPa"

#: Le pas de tuilage d'`arome-wind/ingest.py` (`TILE_DEG`). ⚠️ DUPLIQUÉ,
#: et il n'y a pas moyen de faire autrement sans importer un script de
#: GitHub Action dans un job de VPS. La protection n'est pas ce nombre :
#: c'est `DIST_MAX_KM`, qui sort une balise dont le point trouvé n'est
#: plus dans sa maille — un tuilage changé se verrait immédiatement dans
#: le compte « hors grille » du journal, pas six mois plus tard.
TILE_DEG = 2

#: ⛔ LE GARDE-FOU DU §3.2 DU S1, ET C'EST LUI QUI TIENT LA BORNE.
#: La maille `sol` vaut 0,01°, soit 1,11 km en latitude et 0,79 km en
#: longitude à 45° N : le point le plus proche est au pire à une
#: demi-diagonale, 0,68 km (mesuré : 0,08 à 0,68 km sur six balises
#: alpines, S0.3 §7.2). Une balise pile sur un bord de tuile peut voir
#: son plus proche voisin dans la tuile d'à côté, qu'on ne lit pas
#: forcément : l'erreur monte alors à une maille pleine, 1,11 km. On
#: coupe à 2 km — au-delà, ce n'est plus « la maille de la balise »,
#: c'est le vent d'ailleurs, et on ne rattrape RIEN par un rayon.
DIST_MAX_KM = 2.0

#: Même chose pour l'altitude, où la maille vaut 0,05° (5,55 km en
#: latitude) : demi-diagonale ~3,4 km, bord de tuile ~5,6 km. On coupe
#: à 8 km. ⓘ La tolérance est plus large parce que le champ l'est : à
#: 850 hPa, le terrain ne crée pas de structure fine — c'est
#: l'argument, écrit, de `STEP_ALT` dans `arome-wind/ingest.py`.
DIST_MAX_ALT_KM = 8.0

#: Les six référentiels que `collect.py` tient à jour chaque nuit vers
#: 03:19-03:45 UTC. ⭐ C'est la BONNE source, et il n'y en a pas d'autre
#: à écrire : chacun porte `id`/`source`/`lat`/`lon`, ils sont rafraîchis
#: avant que ce job tourne, et une balise neuve y entre toute seule. On
#: n'invente ni liste gelée ni second référentiel.
#: ⚠️ `stations.json` (Pioupiou) est en AJOUT SEUL et ne rétrécit
#: jamais — cf. `collect.load_stations`. Les autres sont réécrits.
REFERENTIELS = ("stations.json", "windsmobi_stations.json",
                "infoclimat_stations.json", "mf_stations.json",
                "aemet_stations.json", "metar_stations.json")


class Abort(Exception):
    pass


# ══════════════════════════════════════════════════════════════════
#  LES BALISES — d'où elles viennent, et pourquoi de là
# ══════════════════════════════════════════════════════════════════

def charger_balises(root: pathlib.Path, crier=print) -> list[dict]:
    """Toutes les balises connues des six référentiels, dédoublonnées.

    ⚠️ Un référentiel ABSENT n'est pas une erreur : `metar_stations.json`
    n'existait pas avant le S1, et chaque réseau du S0.2 est arrivé à sa
    date. On le DIT et on continue — sinon le premier soir d'un nouveau
    réseau ferait tomber tout le flux.

    La clé de dédoublonnage est `source:id`, exactement celle de
    `daily_rows`. Deux réseaux peuvent porter le même `id` sans se
    marcher dessus, et c'est déjà le cas (`mf` et `infoclimat`).
    """
    vues: dict[str, dict] = {}
    for nom in REFERENTIELS:
        p = root / nom
        if not p.exists():
            crier(f"  ⓘ référentiel absent : {nom} — ignoré")
            continue
        try:
            liste = json.loads(p.read_text("utf-8"))
        except Exception as exc:                             # noqa: BLE001
            raise Abort(f"{nom} illisible ({exc}) — un référentiel "
                        f"corrompu se répare, il ne se contourne pas") from exc
        n = 0
        for b in liste:
            lat, lon = b.get("lat"), b.get("lon")
            if lat is None or lon is None:
                continue
            vues[f"{b['source']}:{b['id']}"] = dict(
                station_id=str(b["id"]), source=b["source"],
                lat=float(lat), lon=float(lon))
            n += 1
        crier(f"  {nom:28s} {n:5d} points")
    return sorted(vues.values(), key=lambda b: (b["source"], b["station_id"]))


def tuile_de(lat: float, lon: float) -> tuple[int, int]:
    return (math.floor(lat / TILE_DEG) * TILE_DEG,
            math.floor(lon / TILE_DEG) * TILE_DEG)


def distance_km(lat1, lon1, lat2, lon2) -> float:
    """Distance sur la sphère, formule haversine. À l'échelle du
    kilomètre, la différence avec un ellipsoïde est de l'ordre de 0,3 %
    — trois mètres sur un kilomètre, et le seuil qu'on lui applique est
    à 2 km. `geopair.py` fait le même choix, pour la même raison."""
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


# ══════════════════════════════════════════════════════════════════
#  LIRE UNE TUILE — et les deux pièges qu'elle porte
# ══════════════════════════════════════════════════════════════════

def _ouvrir_store():
    """Un `Storage` braqué sur le bucket des grilles, avec le jeton qui
    sait le LIRE. Cf. `tools/r2_lecture.py` pour la raison de chaque
    ligne — elle a coûté une nuit en août."""
    from storage import Storage                             # noqa: PLC0415

    bucket = os.environ.get(BUCKET_R2_ENV) or BUCKET_R2_DEFAUT
    prefixe = prefixe_lecture()
    return bucket, prefixe, Storage


class Grille:
    """Une tuile lue, indexée pour la recherche du plus proche voisin.

    ⛔ LES ÉCHÉANCES NE SONT PAS CONTIGUËS, ET C'EST LE PIÈGE PRINCIPAL.
    `arome-wind/ingest.py::keep_step()` garde l'heure pleine le jour et
    UNE ÉCHÉANCE SUR TROIS la nuit (fenêtre 22-04 UTC). Mesuré sur le
    run 00 Z du 22/08 : 42 échéances pour 52 heures d'horizon — il
    manque 01, 02, 22, 23, 25, 26, 46, 47, 49, 50.

    Or `score.fcst_times_ms` reconstitue les heures par `t0 + i × step_s`.
    Une série écrite dans l'ORDRE DU TABLEAU décalerait donc TOUTES les
    heures d'après le premier trou — silencieusement, et du bon ordre de
    grandeur pour passer inaperçu. C'est exactement le défaut de
    dé-accumulation positionnelle de l'audit du 13/08, et c'est pour ça
    qu'`agrume_fcst.lignes()` porte le même avertissement.
    ⇒ On alloue `max(heure) + 1` cases et on pose chaque valeur à SON
    heure ; les trous restent `None`. Le banc
    `test_echeances_non_contigues` tient la propriété.
    """

    def __init__(self, brut: bytes, kind: str, tuile: tuple[int, int]):
        d = json.loads(brut)
        if d.get("kind") != kind:
            raise Abort(f"tuile {tuile} : kind={d.get('kind')!r}, "
                        f"attendu {kind!r}")
        if (d.get("tileLat"), d.get("tileLon")) != tuile:
            raise Abort(f"tuile {tuile} : la tuile se déclare "
                        f"({d.get('tileLat')}, {d.get('tileLon')})")
        self.tuile = tuile
        self.times = list(d["times"])
        # ⛔ `t0` VIENT DE LA TUILE, PAS DU MANIFESTE, et ce n'est pas un
        # détail. `arome-wind/ingest.py` téléverse les 63 tuiles `sol`,
        # PUIS les 441 tuiles `alt` (~8 min), PUIS le manifeste. Entre
        # 05:34 et 05:42 le 22/08, le manifeste annonçait donc encore le
        # run PRÉCÉDENT pendant que les tuiles `sol` portaient déjà le
        # nouveau. Un job qui daterait ses lignes d'après le manifeste
        # les daterait de trois heures trop tôt, sans une erreur.
        # La tuile, elle, se décrit elle-même : `times[0]` EST l'heure du
        # run (`keep_step(0)` rend toujours `True`).
        self.t0 = int(datetime.strptime(self.times[0], "%Y-%m-%dT%H:%M")
                      .replace(tzinfo=timezone.utc).timestamp())
        self.heures = [
            (int(datetime.strptime(t, "%Y-%m-%dT%H:%M")
                 .replace(tzinfo=timezone.utc).timestamp()) - self.t0) // 3600
            for t in self.times]
        self.n = max(self.heures) + 1
        pts = d["points"]
        self.index = {(p["lat"], p["lon"]): p for p in pts}
        self.lats = sorted({p["lat"] for p in pts})
        self.lons = sorted({p["lon"] for p in pts})
        self.n_points = len(pts)

    @property
    def run(self) -> datetime:
        return datetime.fromtimestamp(self.t0, timezone.utc)

    @staticmethod
    def _plus_proche(axe: list[float], v: float) -> float:
        i = bisect.bisect_left(axe, v)
        if i == 0:
            return axe[0]
        if i >= len(axe):
            return axe[-1]
        return axe[i - 1] if (v - axe[i - 1]) <= (axe[i] - v) else axe[i]

    def voisin(self, lat: float, lon: float):
        """Rend `(point, distance_km)`, ou `(None, None)` si la tuile est
        vide. La grille est un TREILLIS PLEIN (200 × 200 pour `sol`) :
        le couple (latitude la plus proche, longitude la plus proche)
        EST le point le plus proche, sans parcourir les 40 000."""
        if not self.lats or not self.lons:
            return None, None
        la = self._plus_proche(self.lats, lat)
        lo = self._plus_proche(self.lons, lon)
        p = self.index.get((la, lo))
        if p is None:
            return None, None
        return p, distance_km(lat, lon, la, lo)


# ══════════════════════════════════════════════════════════════════
#  LES LIGNES D'ARCHIVE
# ══════════════════════════════════════════════════════════════════

def _serie(grille: Grille, p: dict, n: int):
    """Range `speed`/`dir` d'un point À LEUR HEURE dans un tableau de `n`
    cases. Les trous restent `None` — une absence reste une absence, et
    un 0 serait un vent calme parfaitement crédible que le scoring
    noterait comme une prévision."""
    speed: list[float | None] = [None] * n
    direction: list[float | None] = [None] * n
    ps, pd = p.get("speed") or [], p.get("dir") or []
    for i, h in enumerate(grille.heures):
        if h >= n or i >= len(ps) or i >= len(pd):
            continue
        s, d = ps[i], pd[i]
        if s is None or d is None:
            continue
        speed[h], direction[h] = s, d
    return speed, direction


def collecter(store, balises: list[dict], jour: datetime,
              avec_aloft: bool = True, crier=print):
    """Rend `(lignes, journal)`. Une lecture de tuile par tuile utile.

    ⚠️ LE JOURNAL EST UN LIVRABLE, pas un confort de mise au point. Le
    lot S0.3 existe parce qu'une session a écrit quatre fois « reste à
    constater la première nuit » sans jamais aller compter. Ce journal
    dit, à chaque run : combien de balises lues, combien de tuiles
    manquaient, combien de points sont tombés hors grille — et la
    distribution des distances, qui est la preuve, nuit après nuit, que
    ce flux lit bien la maille de la balise et pas le vent d'à côté.
    """
    par_tuile: dict[tuple[int, int], list[dict]] = {}
    for b in balises:
        par_tuile.setdefault(tuile_de(b["lat"], b["lon"]), []).append(b)

    jrn = dict(balises=len(balises), tuiles_utiles=len(par_tuile),
               tuiles_absentes=[], tuiles_alt_absentes=[], octets_sol=0,
               octets_alt=0, lectures=0, hors_grille=0, sans_valeur=0,
               distances=[], distances_alt=[], aloft_ecrit=0, run=None,
               t_lecture=0.0)
    lignes: list[dict] = []
    run_dt = None
    prefixe_alt = PREFIXE_ALT.format(niveau=ALOFT_HPA)

    for tuile in sorted(par_tuile):
        cle = f"{PREFIXE_SOL}{tuile[0]}_{tuile[1]}.json"
        t = time.time()
        brut = store.get(cle)
        jrn["lectures"] += 1
        if not brut:
            # ⚠️ Une tuile absente n'est PAS une erreur en soi : la BBOX
            # d'`ingest.py` peut ne pas la couvrir. Mais elle emporte
            # toutes ses balises, donc elle se COMPTE et se NOMME.
            jrn["tuiles_absentes"].append(f"{tuile[0]}_{tuile[1]}")
            jrn["hors_grille"] += len(par_tuile[tuile])
            continue
        jrn["octets_sol"] += len(brut)
        g = Grille(brut, "sol", tuile)
        jrn["t_lecture"] += time.time() - t

        # ── le run : admis, du bon jour, et LE MÊME pour toutes ──────
        if run_dt is None:
            run_dt = g.run
            jrn["run"] = run_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            if run_dt.hour not in RUNS_ADMIS or run_dt.date() != jour.date():
                raise Abort(
                    f"les tuiles en ligne portent le run "
                    f"{run_dt:%Y-%m-%dT%H:%MZ}, qui n'est pas un run admis "
                    f"du {jour:%Y-%m-%d} (admis : "
                    f"{', '.join(f'{h:02d} Z' for h in RUNS_ADMIS)}). "
                    f"⛔ CETTE JOURNÉE EST PERDUE POUR AROME/R2 : les "
                    f"tuiles sont réécrites en place toutes les 3 h, il "
                    f"n'existe aucune archive des runs passés. Regarder "
                    f"l'Action `arome-wind` de ce matin.")
        elif g.run != run_dt:
            raise Abort(
                f"tuile {tuile[0]}_{tuile[1]} : run {g.run:%Y-%m-%dT%H:%MZ} "
                f"alors que les précédentes portaient "
                f"{run_dt:%Y-%m-%dT%H:%MZ}. ⛔ Le téléversement est EN "
                f"COURS (63 tuiles sol, puis 441 alt, puis le manifeste — "
                f"~8 min le 22/08) : une archive mélangeant deux runs "
                f"daterait la moitié de ses lignes de trois heures trop "
                f"tôt. On s'arrête, le timer de demain repassera.")

        alt = None
        if avec_aloft:
            t = time.time()
            brut_a = store.get(f"{prefixe_alt}{tuile[0]}_{tuile[1]}.json")
            jrn["lectures"] += 1
            if brut_a:
                jrn["octets_alt"] += len(brut_a)
                alt = Grille(brut_a, "alt", tuile)
                if alt.run != run_dt:
                    # Le cas exact de la fenêtre de téléversement : les
                    # `sol` sont neuves, les `alt` pas encore. On ne
                    # mélange pas — on écrit le vent sans l'altitude.
                    crier(f"  ⚠️ tuile {tuile[0]}_{tuile[1]} : alt/{ALOFT_HPA} "
                          f"porte encore le run {alt.run:%H:%MZ} — "
                          f"`arome_aloft_*` non écrit pour cette tuile")
                    alt = None
            else:
                jrn["tuiles_alt_absentes"].append(f"{tuile[0]}_{tuile[1]}")
            jrn["t_lecture"] += time.time() - t

        for b in par_tuile[tuile]:
            p, d = g.voisin(b["lat"], b["lon"])
            if p is None or d > DIST_MAX_KM:
                # ⛔ ON NE RATTRAPE RIEN PAR UN RAYON. Au-delà de
                # DIST_MAX_KM, le point n'est plus dans la maille de la
                # balise : ce serait le vent d'ailleurs, c'est-à-dire
                # `geopair` sur du vent, que le S1 §3.2 interdit.
                jrn["hors_grille"] += 1
                continue
            jrn["distances"].append(d)
            speed, direction = _serie(g, p, g.n)
            if all(s is None for s in speed):
                # Même règle que `collect.py` : une balise sans une
                # seule valeur ne rentre pas sous forme de nulls.
                jrn["sans_valeur"] += 1
                continue
            row = {
                "station_id": b["station_id"], "source": b["source"],
                "lat": b["lat"], "lon": b["lon"],
                "model": MODEL,
                # L'heure du RUN, pas celle d'un appel d'API — décision 4.
                "fetched_at": run_dt.isoformat(),
                "t0": g.t0, "step_s": STEP_S,
                "speed": speed, "dir": direction,
                # Traçabilité que `score.py` ignore : sans eux, l'archive
                # ne dirait ni de quel run ni de quelle maille elle sort,
                # et le jour où l'un des deux change les séries d'avant et
                # d'après seraient indistinguables.
                "arome_run": run_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "arome_maille_deg": 0.01,
                "arome_dist_km": round(d, 3),
            }
            if alt is not None:
                pa, da = alt.voisin(b["lat"], b["lon"])
                if pa is not None and da is not None and da <= DIST_MAX_ALT_KM:
                    # ⛔ `arome_aloft_*` et NON `aloft_*` — décision 2 de
                    # l'en-tête. Sous le nom `aloft_speed`, ces lignes
                    # voleraient le régime des 570 Pioupiou à
                    # `ecmwf_ifs025`, en silence, dès la première nuit.
                    a_s, a_d = _serie(alt, pa, g.n)
                    if any(s is not None for s in a_s):
                        row["arome_aloft_level"] = ALOFT_LEVEL
                        row["arome_aloft_speed"] = a_s
                        row["arome_aloft_dir"] = a_d
                        row["arome_aloft_dist_km"] = round(da, 3)
                        jrn["distances_alt"].append(da)
                        jrn["aloft_ecrit"] += 1
            lignes.append(row)
        del g, alt
    return lignes, jrn


# ══════════════════════════════════════════════════════════════════
#  JOURNAL
# ══════════════════════════════════════════════════════════════════

def _quantiles(xs: list[float]) -> str:
    if not xs:
        return "aucune"
    s = sorted(xs)
    def q(f):
        return s[min(len(s) - 1, int(len(s) * f))]
    return (f"min {s[0]:.2f} · médiane {q(0.5):.2f} · p90 {q(0.9):.2f} · "
            f"max {s[-1]:.2f} km")


def dire_journal(jrn: dict, lignes: list[dict], crier=print):
    crier(f"  run retenu : {jrn['run']}")
    crier(f"  tuiles : {jrn['tuiles_utiles']} utiles, "
          f"{jrn['lectures']} lectures (opérations classe B), "
          f"{(jrn['octets_sol'] + jrn['octets_alt']) / 1e6:.0f} Mo lus "
          f"en {jrn['t_lecture']:.1f} s")
    if jrn["tuiles_absentes"]:
        crier(f"  ⚠️ tuiles sol ABSENTES ({len(jrn['tuiles_absentes'])}) : "
              f"{', '.join(jrn['tuiles_absentes'])}")
    if jrn["tuiles_alt_absentes"]:
        crier(f"  ⚠️ tuiles alt/{ALOFT_HPA} absentes "
              f"({len(jrn['tuiles_alt_absentes'])}) : "
              f"{', '.join(jrn['tuiles_alt_absentes'])}")
    crier(f"  balises : {jrn['balises']} présentées · {len(lignes)} écrites "
          f"· {jrn['hors_grille']} hors grille · {jrn['sans_valeur']} sans "
          f"une seule valeur")
    crier(f"  distance balise → maille : {_quantiles(jrn['distances'])}")
    if jrn["aloft_ecrit"]:
        crier(f"  arome_aloft_* écrit sur {jrn['aloft_ecrit']} lignes "
              f"({ALOFT_LEVEL}) — distance : "
              f"{_quantiles(jrn['distances_alt'])}")
    par_src: dict[str, int] = {}
    for r in lignes:
        par_src[r["source"]] = par_src.get(r["source"], 0) + 1
    crier("  par réseau : " + " · ".join(f"{k} {v}"
                                         for k, v in sorted(par_src.items())))


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="/var/lib/bw-model-verif")
    ap.add_argument("--day", default=None,
                    help="journée à archiver (défaut : AUJOURD'HUI — les "
                         "tuiles sont réécrites toutes les 3 h, il n'y a "
                         "rien à rejouer d'hier)")
    ap.add_argument("--sans-aloft", action="store_true",
                    help="ne pas lire arome/alt/850 (−49 classe B, −24 Mo). "
                         "⚠️ La donnée n'est PAS rejouable : à n'utiliser "
                         "qu'à la main, jamais dans le timer.")
    ap.add_argument("--dry-run", action="store_true",
                    help="tout lire, tout compter, n'écrire ni fichier ni R2")
    args = ap.parse_args()

    root = pathlib.Path(args.out)
    jour = (datetime.strptime(args.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if args.day else datetime.now(timezone.utc)).replace(
                hour=0, minute=0, second=0, microsecond=0)
    print(f"▶ journée archivée : {jour:%Y-%m-%d} — flux AROME/R2 "
          f"(modèle « {MODEL} », maille 0,01°)")

    try:
        balises = charger_balises(root)
        if not balises:
            raise Abort("aucun référentiel de balises lisible dans "
                        f"{root} — ce job n'a rien à quoi s'adresser")
        bucket, prefixe, Storage = _ouvrir_store()
        print(f"  lecture des grilles : bucket « {bucket} », "
              f"identifiants {prefixe}*")
        with bucket_r2(bucket, prefixe):
            try:
                store = Storage("arome-verif", BUCKET_SUPABASE_ENV,
                                BUCKET_SUPABASE_DEFAUT)
            except Exception as exc:                         # noqa: BLE001
                # ⚠️ Sans `STORAGE_BACKEND=r2`, `storage.py` retombe sur
                # le dos Supabase et lève sur des variables que ce job
                # n'a aucune raison d'avoir — le défaut du 03/08 sur le
                # poller Infoclimat, puis du 07/08 sur AGRUME. `run.sh`
                # impose la variable ; à la main, on le DIT au lieu de
                # rendre une trace d'import.
                raise Abort(
                    f"lecture des grilles impossible ({exc}) — ce job veut "
                    f"STORAGE_BACKEND=r2 et les R2_* : passer par "
                    f"`run.sh arome`, ou sourcer "
                    f"~/.balise-watch-r2.env") from exc
            lignes, jrn = collecter(store, balises, jour,
                                    avec_aloft=not args.sans_aloft)
    except Abort as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    dire_journal(jrn, lignes)

    if not lignes:
        print("❌ les tuiles existent mais aucune balise n'a de vent — ce "
              "n'est pas un run vide, c'est un run cassé.", file=sys.stderr)
        return 1

    key = fcst_arome_key(jour)
    if args.dry_run:
        ex = lignes[0]
        n_val = sum(1 for s in ex["speed"] if s is not None)
        print(f"  (dry-run) {key} — exemple : {ex['source']}:"
              f"{ex['station_id']}, {n_val} heures servies sur "
              f"{len(ex['speed'])}, à {ex['arome_dist_km']} km de sa maille")
        return 0

    path = root / key
    n = write_ndjson_gz(path, lignes)
    ko = path.stat().st_size / 1024
    print(f"  écrit : {path} ({n} lignes, {ko:.1f} Ko, "
          f"{path.stat().st_size / n:.0f} o/ligne)")

    if not upload_r2(path, key):
        # Même politique que `collect.py` et `agrume_fcst.py` : le local
        # reste, le témoin n'est pas posé, `rattraper()` réessaiera — et
        # le run SORT EN ERREUR plutôt que d'annoncer un succès sur une
        # archive qui n'existe que sur le disque d'une machine que
        # personne ne sauvegarde.
        print("❌ archive AROME/R2 non montée sur R2 (conservée localement)",
              file=sys.stderr)
        return 2
    print(f"  témoin posé : {temoin(path).name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
