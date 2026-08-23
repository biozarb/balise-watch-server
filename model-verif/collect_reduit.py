#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/collect_reduit.py — LE GROUPE RÉDUIT SUR LES CANDIDATES
#                                          (Lot S0.11, 23/08/2026)
#
#  Une SECONDE PASSE de collecte Open-Meteo, sur une AUTRE population
#  (les balises des cinq réseaux d'observation, hors Pioupiou et hors
#  METAR) et un AUTRE groupe de modèles (cinq, en vent seul, plus le
#  couple 850 hPa sur deux d'entre eux), écrite dans un flux R2 distinct
#  (`fcstreduit/`) que `score.py` lit d'UNE ligne, SOUS LES MÊMES NOMS
#  DE MODÈLES que le groupe Pioupiou.
#
#  ⭐ POURQUOI LES MÊMES NOMS — C'EST TOUTE LA RAISON D'ÊTRE DU LOT.
#  Un tau de Kendall compare deux classements DES MÊMES MODÈLES. Au
#  23/08/2026, les deux populations n'en partagent qu'UN (`arome_r2`,
#  écrit gratuitement par `arome_fcst.py` depuis le 22/08) : zéro paire,
#  donc pas de tau, donc le contrôle n°3 du lot S3 est hors périmètre.
#  Avec ce flux, `k = 6` (les cinq d'ici + `arome_r2`) ⇒ **15 paires**,
#  et le contrôle redevient calculable TROIS NUITS après la première
#  collecte (`score.BIAIS_MIN_JOURS = 3` — le seul classement qui ait un
#  sens depuis le S2 est le CORRIGÉ).
#  ⛔ Un `icon_d2_reduit` rendrait `k = 1` et donc zéro paire — l'état
#  d'aujourd'hui, pour le prix d'une nuit de quota. Le banc
#  `test_modeles_partages_avec_la_population_pioupiou` tient la
#  propriété.
#
#  ⛔ CE QUI N'EST PAS COLLECTÉ UNE NUIT N'EXISTERA JAMAIS. Open-Meteo
#  n'a AUCUN historique de runs passés (mesuré le 08/08 : 0/384 sur
#  `_previous_day1`). Chaque nuit sans ce flux est une nuit perdue pour
#  toujours. C'est la seule urgence de ce fichier, et elle n'a pas de
#  date butoir, juste un coût quotidien.
#
#  ═══════════════════════════════════════════════════════════════════
#  POURQUOI UN SCRIPT NEUF ET PAS UN `--population` DANS `collect.py`
#  ═══════════════════════════════════════════════════════════════════
#
#  Tranché par comptage au lot S0.10, pas au goût. `collect.py` fait
#  1 736 lignes de code, dont :
#
#    · 808 (46,5 %) sont PUREMENT OBSERVATIONS — Pioupiou, METAR,
#      winds.mobi, Infoclimat, Météo-France, AEMET. Une passe candidates
#      ne doit JAMAIS les exécuter. Un `if` qui protège 808 lignes n'est
#      pas une extension, c'est une cohabitation.
#    · 287 (16,5 %) passeraient sous un paramètre — dont `quota_projete`
#      (104 lignes) et `construire_manifeste` (69), toutes deux
#      corrigées la veille au S0.9.
#    · ⭐ 319 (18,4 %) se réutilisent PAR IMPORT, sans une ligne
#      modifiée. C'est ce que fait ce fichier, et c'est le patron
#      qu'`arome_fcst.py` applique déjà en production depuis le 22/08.
#
#  ⭐ ET L'ARGUMENT DÉCISIF EST STRUCTUREL, PAS ESTHÉTIQUE. Le piège
#  n°1 du `BUGS.md` (S0.3) dit qu'un garde-fou de quota ne doit pas
#  détruire une donnée que le quota ne concerne pas : dans `collect.py`,
#  un `Abort` de `quota_projete` faisait `return 1` AVANT la passe
#  observations, dont trois réseaux n'ont que 30 à 48 h de rétention
#  amont. Ici, dans un script qui NE CONNAÎT PAS les observations, un
#  `Abort` ne peut tuer que lui-même. La garantie vient de
#  l'architecture, pas d'un `try`.
#
#  ⛔ ET `test_collect.py` (215 assertions) RESTE UN TÉMOIN. Le jour où
#  ce fichier casse quelque chose de partagé, c'est LUI qui rougit — ce
#  qui serait impossible s'il était devenu le banc des deux programmes.
# ══════════════════════════════════════════════════════════════════════
#
#  ═══ LES SEPT DÉCISIONS, ET CE QU'ELLES COÛTENT ═══
#
#  1. ⛔ **05:00 UTC, `RandomizedDelaySec=60`.** Mesuré au S0.10 sur les
#     `meta.json` d'Open-Meteo : à 04:35 (l'heure que le S0.6 avait
#     choisie pour d'excellentes raisons budgétaires), `icon_d2` publie
#     son run 03 Z à 04:26 — NEUF MINUTES de marge. L'écart de fraîcheur
#     avec la passe Pioupiou de 03:19 serait donc INTERMITTENT, et un
#     écart intermittent est le seul qu'on ne puisse ni corriger ni
#     déclarer : la fenêtre glissante de 15 jours mélangerait deux
#     régimes SANS DATE DE BASCULE. À 05:00, l'écart vaut 3 h, il est
#     STABLE (34 min après `icon_d2` 04:26, 35 min avant `gfs_global`
#     05:35 — le point qui maximise la plus petite des deux marges), et
#     la sonde du §`sonde_fraicheur` l'écrit dans chaque ligne.
#     ⓘ La paire inversée (candidates 03:00 / Pioupiou 04:15) rendrait
#     l'écart NUL, mais sur 4 minutes de marge et une seule nuit
#     mesurée, et il faudrait déplacer `bw-model-collect` ET ses six
#     passes d'observation. Écartée, pas oubliée : la sonde la rend
#     rejugeable sur cinq nuits au lieu d'une.
#
#  2. ⛔ **La population est une RÈGLE, jamais une liste.** « Les 2 925
#     candidates » du S0.8 n'est PAS une population collectable : c'est
#     le résultat d'un calcul fait dans `model_verif_daily` APRÈS la
#     notation de 03:56, pour la veille. Un collecteur qui part à 05:00
#     ne peut pas le lire pour la nuit qu'il collecte. Ce qu'il PEUT
#     construire, localement et sans base :
#
#         les six référentiels dédoublonnés par `source:id`
#           − `source == "pioupiou"`      (le flux `fcst/` les sert déjà)
#           − `source == "metar"`         (107,4 % de la fenêtre horaire)
#           − les balises SANS AUCUNE observation dans les archives
#             `obs*` de la veille
#
#     ⚠️ **Mesuré le 23/08 : cette règle rend 2 942, pas 2 925.** La
#     note du S0.10 §4.3 annonçait « exactement 2 925 » ; recompté sur
#     les archives du 22/08, elle rend **3 366 − 424 = 2 942**, et
#     AUCUN seuil sur le nombre de relevés ne reproduit les 441 muettes
#     annoncées (essayé : ligne présente 424, ≥ 1 vent 424, ≥ 2 relevés
#     428, ≥ 12 relevés 432). Les 2 925 sont le nombre de balises
#     NOTÉES, qui exige en plus `MIN_HOURS_DAILY` heures appariables :
#     17 balises ont une ligne d'observation sans être notables. ⇒ Le
#     chiffre de la RÈGLE est 2 942 aujourd'hui ; l'égalité avec 2 925
#     était une coïncidence mesurée une fois, pas une propriété.
#
#  3. ⛔ **Le cap vient du budget MESURÉ, et il exclut sa propre
#     étiquette.** Notre seuil interne de 60 % (`collect.quota_projete`)
#     ne mord pas le premier sur cette passe : il est AVEUGLE. Il juge
#     `n_points × par_point_jour` de SA population — 2 942 × 1,40 =
#     4 119 < 6 000 — sans jamais voir les 3 810,6 pondérés de Pioupiou.
#     ⇒ La passe candidates ne se compare pas à un plafond : elle
#     calcule CE QUE LE BUDGET LUI LAISSE (cf. `cap_budgetaire`).
#     ⛔⛔ Et l'exclusion de sa propre étiquette n'est PAS un détail :
#     `Budget.etat()["fenetres"]["jour"]` est une fenêtre GLISSANTE de
#     24 h. Sans elle, une nuit où la passe part deux minutes plus tôt
#     que la veille verrait SA PROPRE CONSOMMATION DE LA VEILLE encore
#     dedans et calculerait un cap de ~0 point. La nuit serait perdue
#     EN SILENCE, une fois sur deux. C'est le piège le plus vicieux du
#     lot, et le banc `test_cap_ignore_sa_propre_consommation_de_la_veille`
#     est le seul qui le tienne.
#
#  4. ⛔ **L'ordre d'éviction, en trois rangs DÉCLARÉS.** Rang 0 :
#     l'exclusion des muettes — ce n'est pas une éviction, c'est une
#     exclusion gratuite (407 des 424 sont des stations Infoclimat, des
#     baromètres amateurs qui « respirent » ; les collecter coûterait
#     570 pondérés par nuit pour une prévision que rien n'apparierait).
#     Rang 1 : **altitude décroissante**. Rang 2 : `source:station_id`,
#     pour que l'ordre soit DÉTERMINISTE.
#     ⚠️ **Écart au S0.10, mesuré** : la note disait de trier sur
#     `station_zone.dem_alt_m`, qui vit EN BASE, et signalait 6 balises
#     sans altitude. Recompté le 23/08 : **les 3 366 balises hors
#     Pioupiou/METAR portent TOUTES un champ `elev` dans leur propre
#     référentiel local** (0 manquante). On trie donc sur `elev`, ce qui
#     retire à ce collecteur toute dépendance à PostgREST à 05:00 du
#     matin. Le code gère quand même le cas `elev` absent — sans
#     altitude, on sort EN PREMIER.
#     ⛔ Et une éviction se COMPTE ET SE NOMME : patron de `--limit`,
#     corrigé au S0.4 (`collect.py` l. 2503-2519).
#
#  5. ⛔ **Le manifeste déclare CE QUE CE RUN ÉCRIT, jamais
#     `len(groupes)`.** C'est le défaut du S0.9, corrigé la veille, et
#     il ne doit pas être refabriqué sur un flux neuf. Ici le
#     discriminant est structurel : `construire_manifeste` prend LA
#     LISTE DES CLÉS que le run va écrire, et `parties` en est la
#     longueur. Ce run en écrit une, toujours.
#
#  6. ⛔ **`FLUX_PARTITIONNE = "fcst"` de `collect.py` reste vrai, et ce
#     flux-ci n'est PAS une partie de `fcst/`.** La partition du S0.6
#     découpe UNE population par groupe de modèles ; ici c'est UNE AUTRE
#     POPULATION. Les confondre ferait compter la passe candidates comme
#     une partie manquante de la nuit Pioupiou — c'est-à-dire
#     exactement l'incident que le S0.9 vient d'éteindre.
#
#  7. ⭐ **La sonde de fraîcheur écrit le run servi DANS CHAQUE LIGNE.**
#     Neuf appels `meta.json` par nuit, par `Budget.demander()`, depuis
#     le VPS, **1 pondéré réservé par appel au pire cas** (`poids_url`
#     rendrait son plancher, 0,1, et ce que facture réellement cet
#     endpoint N'EST PAS ÉTABLI — on réserve le pire, jamais l'espéré).
#     Sans elle, l'écart de 3 h sur `icon_d2` reste une hypothèse à
#     n = 1 dans une archive irremplaçable.
#     ⚠️ **Un échec de la sonde NE TUE PAS LA PASSE** : elle écrit ce
#     qu'elle a, dit ce qui manque, et la collecte part quand même. Une
#     colonne d'information ne doit jamais coûter une nuit d'archive.
#
#  ═══ CE QUE CE FLUX NE PEUT PAS DIRE ═══
#
#  ⛔ **Le vent, et rien d'autre, et pour toujours sur ces nuits-là.**
#  Pas de rafales, pas de pluie, pas de pression, pas de température :
#  E4 et E6 restent fermés à ces 2 942 balises. Remesuré le 23/08 : les
#  rafales seules portent la composition à 1,90/point (5 590 pondérés,
#  101 % du plafond journalier effectif restant), les six variables à
#  3,40 (10 003, 147 %). Ce n'est pas un dosage, c'est l'un ou l'autre.
#
#  ⛔ **185 candidates pyrénéennes n'auront aucun avis à maille fine**
#  hors `arome_r2` et `icon_eu` : `dmi_harmonie_arome_europe` — le seul
#  modèle à 2 km qui couvre les Pyrénées, la Bretagne et le Sud-Ouest —
#  n'est pas dans le groupe, et `icon_d2` n'y sert qu'une balise sur 99.
#
#  ⚠️ **Trois ICON sur cinq.** Un biais de la famille ICON serait
#  indétectable sur les candidates, faute de témoin extérieur. Perte de
#  DIVERSITÉ, pas de précision — et elle ne se voit que le jour où elle
#  compte.
#
#      python3 collect_reduit.py --dry-run     # tout chiffrer, ne rien envoyer
#      python3 collect_reduit.py --day 2026-08-24
#      python3 collect_reduit.py --sans-sonde  # sauter les 9 meta.json
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

_ICI = pathlib.Path(__file__).resolve().parent
for _p in (_ICI.parent / "tools",):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

# ⭐ LES 319 LIGNES RÉUTILISÉES SANS EN MODIFIER UNE. Patron
# d'`arome_fcst.py` l. 186. ⛔ On IMPORTE `collect.py`, on ne le modifie
# pas : c'est le fichier qui porte la seule chaîne irremplaçable du
# chantier, et il a été déployé, retiré et redéployé trois fois en un
# matin le 22/08.
from collect import (                                        # noqa: E402
    ALOFT_VARS, COMPAGNON_ALTITUDE, FORECAST_API, REGIME_REF_MODEL, Abort,
    _get_json_retry, attendre_la_place, charger_quota, en_retard,
    fetch_forecast, forecast_rows, rattraper, temoin, upload_r2,
    write_ndjson_gz,
)
# ⓘ `en_retard` n'est pas appelé ici — `rattraper()` s'en sert — mais il
# est importé EXPRÈS : c'est lui que le banc
# `test_en_retard_voit_le_manifeste_du_flux_neuf` interroge, et le
# réexporter dit que ce flux dépend de son comportement.
_ = en_retard
# ⚠️ `OBS_KEY_FUNCS` EST DÉRIVÉ, PAS RECOPIÉ, et c'est ce qui rend la
# règle du §2 juste : « les archives `obs*` de la veille » doit vouloir
# dire LES MÊMES que celles que la notation lit. Le jour où un réseau
# entre dans `score.OBS_KEY_FUNCS`, il entre du même coup dans le
# dénominateur de cette règle, sans que personne n'y pense.
from score import OBS_KEY_FUNCS, read_ndjson                 # noqa: E402

# ══════════════════════════════════════════════════════════════════
#  CONSTANTES
# ══════════════════════════════════════════════════════════════════

#: Le nom du flux, donc du préfixe R2, donc des deux clés. Le patron des
#: trois flux existants (`fcst`, `fcstagrume`, `fcstarome`) : préfixe =
#: nom du flux, sans tiret ni souligné.
FLUX = "fcstreduit"

#: ⛔ LES MODÈLES DE SURFACE DU GROUPE RÉDUIT — ET LEURS NOMS SONT CEUX
#: DU GROUPE PIOUPIOU, SANS SUFFIXE NI VARIANTE. Cf. l'en-tête : un
#: `icon_d2_reduit` rendrait `k = 1`, donc zéro paire, donc pas de tau.
#: Ce sont des chaînes qui doivent rester ÉGALES à celles de
#: `collect.MODELS` — le banc `test_noms_de_modeles_identiques_a_collect`
#: le vérifie, parce qu'une égalité de chaînes qui n'est vérifiée nulle
#: part se défait un jour sans un message.
MODELS_REDUIT_SURFACE = ["icon_d2", "meteoswiss_icon_ch2", "icon_eu"]

#: ⛔ LE GROUPE D'ALTITUDE EST DÉRIVÉ DE `collect.py`, JAMAIS RECOPIÉ.
#: `REGIME_REF_MODEL` parce que c'est LE modèle qui étiquette le régime
#: de la journée, et qu'il doit être le même pour tout le monde —
#: `score.day_regime` n'en connaît qu'un. `COMPAGNON_ALTITUDE` parce que
#: la règle du suffixe (cf. `collect.forecast_rows`) abandonne
#: bruyamment un point servi par UN SEUL modèle : il faut un compagnon
#: MONDIAL, qui serve tous les points de la BBOX, y compris ceux que les
#: référentiels ajouteront demain.
MODELS_REDUIT_ALTITUDE = [REGIME_REF_MODEL, COMPAGNON_ALTITUDE]

#: L'union, DANS L'ORDRE DÉCLARÉ (altitude d'abord, comme
#: `collect.groupes_requete`). Dérivée, jamais recopiée.
MODELS_REDUIT = [*MODELS_REDUIT_ALTITUDE, *MODELS_REDUIT_SURFACE]

#: ⛔ VENT SEUL. Deux variables, pas trois : ajouter `wind_gusts_10m`
#: porte la composition de 1,40 à 1,90 pondéré par point, soit 101 % de
#: ce que le budget laisse (mesuré le 23/08). Ce n'est pas un dosage.
VENT = ["wind_speed_10m", "wind_direction_10m"]

#: Les six référentiels que `collect.py` tient à jour chaque nuit vers
#: 03:19-03:45 UTC. ⚠️ DUPLIQUÉ D'`arome_fcst.REFERENTIELS`, et le banc
#: `test_referentiels_identiques_a_arome_fcst` tient l'égalité — on ne
#: l'importe pas, parce qu'`arome_fcst` importe `r2_lecture` et le
#: paquet de lecture des grilles, dont ce collecteur n'a aucun besoin.
#: Une duplication DÉCLARÉE ET BANCÉE, jamais une duplication muette.
REFERENTIELS = ("stations.json", "windsmobi_stations.json",
                "infoclimat_stations.json", "mf_stations.json",
                "aemet_stations.json", "metar_stations.json")

#: ⛔⛔ LE FILTRE QUI TIENT LE PIÈGE `ref_by_st`, ET IL N'Y EN A PAS
#: D'AUTRE. `score.daily_rows` (l. 909-913) établit le régime d'une
#: balise ainsi :
#:
#:     for row in snapshots.get(0, []):
#:         if "aloft_speed" in row:
#:             ref_by_st[f"{source}:{station_id}"] = row
#:
#: — LE DERNIER GAGNE, et le test porte sur la PRÉSENCE de la clé, pas
#: sur sa valeur. Ce flux-ci porte un vrai `aloft_speed` (ECMWF à
#: 850 hPa, écrit par `collect.forecast_rows`) ET il est lu EN DERNIER
#: par `snapshot_rows_et_bilan`. Si une balise Pioupiou entrait dans
#: cette population, SON RÉGIME SERAIT VOLÉ — mesuré au S0.5 : `fluxW`
#: devient `thermal`, sur 13 795 lignes par nuit, sans un message et
#: sans un banc rouge.
#: ⇒ La garantie est ICI, dans une exclusion PAR SOURCE, jamais dans un
#: « celles qui n'ont pas de ligne Open-Meteo » : cette seconde
#: définition se calcule en base, elle bouge d'une nuit à l'autre, et
#: une balise Pioupiou muette une nuit y rentrerait.
#: ⚠️ `metar` est exclu pour une tout autre raison, arithmétique :
#: +278 points porte la passe à 107,4 % de la fenêtre horaire, donc à
#: une passe de plus, donc à un troisième créneau entre deux
#: publications de run — et il n'y en a pas (S0.10 §4.5).
SOURCES_EXCLUES = ("pioupiou", "metar")

#: ⭐ L'ÉTIQUETTE DE CE CONSOMMATEUR DANS LE BUDGET PARTAGÉ. C'est elle
#: que `cap_budgetaire` EXCLUT du calcul — cf. décision 3 de l'en-tête.
#: Elle doit être DIFFÉRENTE de `"collect"` (la passe Pioupiou) sans
#: quoi les deux consommations se mélangeraient et plus personne ne
#: saurait qui a pris quoi.
ETIQUETTE_BUDGET = "collect_reduit"

#: ⭐ LA RÉSERVE, NOMMÉE ET CHIFFRÉE (S0.10 §5.4). Ce n'est pas une
#: marge de confort : c'est LE TERME QUI DÉFINIT LE CAP.
#:
#:   · 870 — croissance du référentiel Pioupiou. Mesuré : ~4,5 points
#:     par semaine × 5,80 pondérés = 26/semaine ; 870 couvre 150 points,
#:     soit ~33 semaines. ⚠️ Le prochain palier tombe le 29 ou 30/08
#:     (`stations.json` mtime 22/08 03:19 UTC, `load_stations`
#:     `max_age_days=7`).
#:   · 500 — les scripts qui partagent l'IP quand on les lance à la main
#:     (`match_analogs.py`, `day_features.py`, `sonde_openmeteo.py`).
#:     ⚠️ NON MESURÉ : ils n'ont tourné ni le 21, ni le 22, ni le 23/08.
#:     Les 9 pondérés de la sonde de fraîcheur sont pris là-dedans.
RESERVE_NON_COMPTEE = 1_370.0

#: ⚠️ CE QUE LA NUIT PIOUPIOU + L'ENTRETIEN PÈSENT, POUR LE SEUL CAS OÙ
#: LE BUDGET PARTAGÉ EST ILLISIBLE (cf. `cap_budgetaire`). 252,0
#: pondérés est la consommation quotidienne de `backfill_packs`, mesurée
#: les 21, 22 et 23/08 dans `/var/lib/bw-quota/openmeteo.json`. Le poids
#: de la passe Pioupiou, lui, n'est PAS une constante : il est dérivé du
#: référentiel réel et de `collect.poids_par_point()`.
BACKFILL_PACKS_MESURE = 252.0

#: Le point d'entrée de métadonnées d'Open-Meteo, mesuré au S0.10 :
#: HTTP 200 sur les dix domaines interrogés, et il rend
#: `last_run_initialisation_time` / `last_run_availability_time`.
#: ⛔ CE N'EST PAS LE MIROIR AWS. Le même fichier existe sur
#: `openmeteo.s3.amazonaws.com` SANS QUOTA — et il est PÉRIMÉ : mesuré
#: le 23/08, `dwd_icon_d2` y portait encore le run du 15/08, huit jours
#: de retard. Le miroir ne reflète pas ce que l'API sert, et pas de la
#: même façon selon le modèle. La route gratuite n'existe pas.
META_API = "https://api.open-meteo.com/data/{domaine}/static/meta.json"

#: ⛔ POIDS RÉSERVÉ PAR APPEL DE SONDE — LE PIRE CAS, PAS L'ESPÉRÉ.
#: `quota_openmeteo.poids_url()` calcule le poids depuis les paramètres
#: de l'URL ; celle-ci n'en a AUCUN, donc elle rendrait son plancher
#: (0,1). Ce que cet endpoint facture réellement N'EST PAS ÉTABLI. On
#: réserve donc 1 pondéré par appel, soit 9 par nuit — 0,19 % de la
#: fenêtre horaire effective. C'est ce chiffre-là qui est budgété,
#: jamais 0,9.
POIDS_SONDE = 1.0

#: Les domaines Open-Meteo des cinq modèles du groupe réduit. ⚠️ Ce sont
#: des noms DE DOMAINE, pas des noms de modèle : `gfs_global` est servi
#: par `ncep_gfs013` (mesuré au S0.10 — `ncep_gfs025`, lui, publie
#: 43 min plus tard). Une correspondance fausse ici écrirait dans
#: l'archive le run d'un autre modèle, ce qui est pire que pas de
#: colonne du tout.
DOMAINE_PAR_MODELE = {
    "icon_d2": "dwd_icon_d2",
    "icon_eu": "dwd_icon_eu",
    "meteoswiss_icon_ch2": "meteoswiss_icon_ch2",
    "ecmwf_ifs025": "ecmwf_ifs025",
    "gfs_global": "ncep_gfs013",
}

#: Quatre domaines de plus, sondés pour le JOURNAL et le MANIFESTE, pas
#: pour les lignes : ce sont les modèles que la passe Pioupiou collecte
#: et que celle-ci ne collecte pas. Sans eux, on ne saurait pas, la nuit
#: où l'écart bougerait, si c'est `icon_d2` qui a changé ou toute la
#: chaîne de publication. Neuf appels au total — le chiffre budgété.
DOMAINES_TEMOINS = ("meteofrance_arome_france_hd", "meteofrance_arpege_europe",
                    "dmi_harmonie_arome_europe",
                    "chmi_aladin_central_europe_2km")


# ══════════════════════════════════════════════════════════════════
#  LE GROUPE RÉDUIT
# ══════════════════════════════════════════════════════════════════

def groupes_reduit() -> list[tuple[list[str], list[str]]]:
    """La requête d'un point, découpée en `(modèles, variables)`.

    Même forme et même discipline que `collect.groupes_requete()` :
    DÉRIVÉ, jamais recopié. Deux groupes, parce que le couple 850 hPa ne
    sert qu'à `REGIME_REF_MODEL` et qu'Open-Meteo prend UNE liste
    `hourly` pour tous les modèles d'une requête — le demander aux cinq
    coûterait 2 × 5 / 10 = 1,0 pondéré par point pour quatre modèles
    dont on jetterait la réponse.

    ⛔ ET CHAQUE GROUPE PORTE AU MOINS DEUX MODÈLES, sous peine
    d'`Abort`. C'est la règle du suffixe de `collect.forecast_rows` :
    Open-Meteo ne suffixe les clés par le nom du modèle que si PLUSIEURS
    modèles SERVENT le point. Un groupe à un seul modèle produirait donc
    ZÉRO ligne partout, avec des HTTP 200 parfaitement formés — la panne
    ERA5 du 06/08, sur une archive non rejouable.
    """
    groupes = [(list(MODELS_REDUIT_ALTITUDE), [*VENT, *ALOFT_VARS]),
               (list(MODELS_REDUIT_SURFACE), list(VENT))]
    for modeles, _variables in groupes:
        if len(modeles) < 2:
            raise Abort(
                f"groupe à {len(modeles)} modèle(s) ({', '.join(modeles)}) : "
                f"Open-Meteo ne suffixe les clés par le nom du modèle que si "
                f"PLUSIEURS modèles SERVENT le point. Un groupe à un seul "
                f"modèle rendrait `wind_speed_10m` tout court, sans dire qui "
                f"a répondu, et `forecast_rows` abandonnerait TOUS les points "
                f"— zéro ligne, HTTP 200, aucune erreur. Il faut au moins un "
                f"compagnon MONDIAL (cf. `collect.COMPAGNON_ALTITUDE`).")
    if REGIME_REF_MODEL not in MODELS_REDUIT_ALTITUDE:
        raise Abort(
            f"{REGIME_REF_MODEL} absent du groupe d'altitude : c'est le seul "
            f"modèle dont `collect.forecast_rows` écrit `aloft_speed`, et "
            f"sans lui les {len(MODELS_REDUIT)} modèles de ce flux "
            f"laisseraient toute leur population en `regime = \"unknown\"` — "
            f"c'est-à-dire exactement l'état que ce lot existe pour quitter.")
    return groupes


def poids_par_point_reduit() -> float:
    """Poids Open-Meteo d'UN point, tous groupes confondus.

    ⚠️ Même dérivation que `collect.poids_par_point()` : variables ×
    modèles / 10. Mesuré le 23/08 par `quota_openmeteo.poids_url()` sur
    des URL CONSTRUITES ET NON ENVOYÉES : 0,8000 (altitude) + 0,6000
    (surface) = **1,4000**.
    """
    return sum(len(v) * len(m) for m, v in groupes_reduit()) / 10


# ══════════════════════════════════════════════════════════════════
#  LA POPULATION — une RÈGLE, jamais une liste
# ══════════════════════════════════════════════════════════════════

def charger_population(root: pathlib.Path, veille: datetime,
                       crier=print) -> tuple[list[dict], dict]:
    """Les candidates de CETTE nuit, calculées localement et sans base.

    Rend `(balises, journal)`. Les balises sont au format que
    `collect.forecast_rows` attend : `id`, `source`, `lat`, `lon` —
    plus `elev`, qui sert au rang 1 de l'éviction.

    ⚠️ Un référentiel ABSENT n'est pas une erreur : `metar_stations.json`
    n'existait pas avant le S1, et chaque réseau du S0.2 est arrivé à sa
    date. On le DIT et on continue.

    ⚠️ **LE REPLI EST ÉCRIT, PAS SUBI.** Si AUCUNE archive
    d'observations de la veille n'est lisible (une nuit où les
    collecteurs ont échoué, un disque remonté à vide), la règle n'a rien
    à retirer : on garde tout, le cap budgétaire du `cap_budgetaire`
    tranche, et **le journal DIT lequel des deux chemins a été pris**.
    Jamais un plantage — une nuit d'archive vaut plus qu'une règle —,
    jamais un silence.
    """
    jrn: dict = {"referentiels": {}, "dedup": 0, "exclues_source": {},
                 "obs_lues": {}, "obs_absentes": [], "muettes": 0,
                 "muettes_par_source": {}, "repli_sans_obs": False,
                 "sans_elev": 0}

    vues: dict[str, dict] = {}
    for nom in REFERENTIELS:
        p = root / nom
        if not p.exists():
            crier(f"  ⓘ référentiel absent : {nom} — ignoré")
            jrn["referentiels"][nom] = None
            continue
        try:
            liste = json.loads(p.read_text("utf-8"))
        except Exception as exc:                             # noqa: BLE001
            raise Abort(f"{nom} illisible ({exc}) — un référentiel corrompu "
                        f"se répare, il ne se contourne pas") from exc
        n = 0
        for b in liste:
            lat, lon = b.get("lat"), b.get("lon")
            if lat is None or lon is None:
                continue
            # ⚠️ Clé `source:id`, EXACTEMENT celle de `score.daily_rows`.
            # Deux réseaux peuvent porter le même `id` sans se marcher
            # dessus, et c'est déjà le cas (`mf` et `infoclimat`).
            vues[f"{b['source']}:{b['id']}"] = {
                "id": str(b["id"]), "source": b["source"],
                "lat": float(lat), "lon": float(lon),
                "elev": (float(b["elev"]) if b.get("elev") is not None
                         else None),
            }
            n += 1
        jrn["referentiels"][nom] = n
    jrn["dedup"] = len(vues)

    # ── rang 0a : l'exclusion PAR SOURCE ────────────────────────────
    # ⛔ C'est la garantie du piège `ref_by_st`, cf. `SOURCES_EXCLUES`.
    gardees: dict[str, dict] = {}
    for cle, b in vues.items():
        if b["source"] in SOURCES_EXCLUES:
            jrn["exclues_source"][b["source"]] = \
                jrn["exclues_source"].get(b["source"], 0) + 1
            continue
        gardees[cle] = b

    # ── rang 0b : l'exclusion des MUETTES de la veille ──────────────
    observees: set[str] = set()
    for key_fn in OBS_KEY_FUNCS:
        cle = key_fn(veille)
        lignes = read_ndjson(root, cle)
        if not lignes:
            jrn["obs_absentes"].append(cle)
            continue
        jrn["obs_lues"][cle.split("/")[0]] = len(lignes)
        for r in lignes:
            observees.add(f"{r['source']}:{r['station_id']}")

    if not observees:
        # ⚠️ LE REPLI, ÉCRIT. On ne retire rien, et on le DIT.
        jrn["repli_sans_obs"] = True
        crier("  ⛔ AUCUNE archive d'observations lisible pour la veille "
              f"({veille:%Y-%m-%d}) — la règle des muettes n'a rien à "
              f"retirer. REPLI : on garde les {len(gardees)} points des "
              f"référentiels, et c'est le CAP BUDGÉTAIRE qui tranche. "
              f"(archives cherchées : "
              f"{', '.join(jrn['obs_absentes'])})")
        population = list(gardees.values())
    else:
        muettes = [c for c in gardees if c not in observees]
        jrn["muettes"] = len(muettes)
        for c in muettes:
            s = c.split(":")[0]
            jrn["muettes_par_source"][s] = jrn["muettes_par_source"].get(s, 0) + 1
        population = [b for c, b in gardees.items() if c in observees]

    jrn["sans_elev"] = sum(1 for b in population if b["elev"] is None)
    # Ordre stable AVANT tout tri d'éviction : deux runs successifs sur
    # le même référentiel doivent présenter la même liste.
    population.sort(key=lambda b: (b["source"], b["id"]))
    return population, jrn


# ══════════════════════════════════════════════════════════════════
#  LE CAP — ce que le budget MESURÉ laisse, réserve nommée déduite
# ══════════════════════════════════════════════════════════════════

def cap_budgetaire(qm, budget, cout_point: float,
                   conso_repli: float | None = None,
                   crier=print) -> tuple[int, dict]:
    """Combien de points le budget laisse à CETTE passe, ce soir.

    ⛔ CE N'EST PAS UNE COMPARAISON À UN PLAFOND, ET C'EST LA DIFFÉRENCE
    QUI COMPTE. Le seuil de 60 % de `collect.quota_projete` juge
    `n_points × par_point_jour` de SA population : deux populations dans
    deux processus lui sont invisibles. Il n'est pas trop serré, il NE
    REGARDE PAS. Ici, la passe candidates lit ce qui RESTE :

        cap = ⌊ (plafond_jour_effectif − conso_des_AUTRES − RÉSERVE)
                / coût_point ⌋

    ⭐ TROIS PROPRIÉTÉS QUE « 60 % D'UN PLAFOND » N'A PAS :

    1. **C'est toujours la passe candidates qui cède, jamais Pioupiou.**
       Elle est la seule à lire ce qui reste ; Pioupiou part à 03:19 et
       n'a rien à céder. Si le référentiel Pioupiou grandit de 150
       points (+870 pondérés), le cap tombe tout seul, et personne n'a à
       y penser.
    2. ⛔⛔ **L'exclusion de sa propre étiquette n'est pas un détail.**
       `Budget.etat()["fenetres"]["jour"]` est une fenêtre GLISSANTE de
       24 h. Sans elle, une nuit où la passe part deux minutes plus tôt
       que la veille verrait SA PROPRE CONSOMMATION DE LA VEILLE encore
       dedans et calculerait un cap de ~0 point. ⛔ La nuit serait perdue
       EN SILENCE, une fois sur deux, sans qu'aucun garde-fou ne crie.
    3. **Il se journalise AVANT la première requête**, comme
       `quota_projete` le fait déjà.

    ⚠️ **ET LE REPLI EST DÉRIVÉ, PAS INVENTÉ.** Si le module de budget
    est absent (un rsync qui n'a copié que `model-verif/`, par exemple —
    c'est le cas que `collect.charger_quota` rattrape déjà), on ne
    connaît pas ce qui reste. On prend alors l'hypothèse la plus
    DÉFAVORABLE : la nuit Pioupiou a consommé tout ce qu'elle consomme
    d'habitude (dérivé du référentiel réel × `collect.poids_par_point()`)
    plus `backfill_packs`. Un garde-fou qui se trompe doit se tromper du
    côté qui protège.
    """
    jrn: dict = {"source": None, "plafond_jour": None, "autres": None,
                 "reserve": RESERVE_NON_COMPTEE, "cout_point": cout_point,
                 "cap": 0, "par_consommateur": {}}

    if qm is None or budget is None:
        if conso_repli is None:
            raise Abort(
                "budget partagé indisponible ET aucune consommation de repli "
                "dérivée — impossible de savoir ce que la nuit a déjà pris. "
                "On ne devine pas un budget : regarder "
                "`tools/quota_openmeteo.py` sur cette machine.")
        plafond = 9_500.0     # cf. `quota_openmeteo.plafond_effectif("jour")`
        jrn["source"] = "repli-derive"
        autres = float(conso_repli)
    else:
        plafond = qm.plafond_effectif("jour")
        etat = budget.etat()
        jour = etat["fenetres"]["jour"]
        jrn["par_consommateur"] = dict(jour["par_consommateur"])
        # ⛔ SA PROPRE ÉTIQUETTE EST EXCLUE — propriété 2 ci-dessus.
        autres = sum(v for k, v in jour["par_consommateur"].items()
                     if k != ETIQUETTE_BUDGET)
        jrn["source"] = "budget-mesure"

    jrn["plafond_jour"] = plafond
    jrn["autres"] = autres
    reste = plafond - autres - RESERVE_NON_COMPTEE
    cap = int(reste // cout_point) if reste > 0 else 0
    jrn["cap"] = max(0, cap)
    return jrn["cap"], jrn


def trier_et_evincer(population: list[dict], cap: int,
                     crier=print) -> tuple[list[dict], list[dict]]:
    """L'éviction, en deux rangs DÉCLARÉS, et elle COMPTE ET NOMME.

    ⛔ UNE SOUPAPE QUI TRONQUE DOIT COMPTER ET NOMMER CE QU'ELLE ÉCARTE.
    C'est le patron de `--limit`, corrigé au S0.4 (`collect.py`
    l. 2503-2519) : avant, la coupe se faisait EN SILENCE, et comme la
    liste était triée par `id` et non par ancienneté, ce sont des
    balises arbitraires qui disparaissaient d'une archive
    irremplaçable, sans une ligne de journal. Un trou nommé vaut mieux
    qu'un run tué ; un trou ANONYME ne vaut rien du tout, parce qu'on ne
    saura jamais qu'il est là.

    **Rang 1 — altitude DÉCROISSANTE.** Mesuré au S0.10 : les deux
    ordres candidats (altitude seule, ou massif puis altitude) gardent
    tous les deux les mêmes balises d'altitude et le même contingent
    alpin au cap d'aujourd'hui. Le tri par massif n'apporte donc rien
    que celui-ci ne donne déjà, et il demanderait un tableau de rangs de
    massifs à tenir à jour. ⚠️ Une balise SANS altitude sort EN PREMIER
    — on préfère perdre celle dont on ne sait rien.

    **Rang 2 — `source:station_id`.** Il ne départage rien de physique :
    il rend l'ordre DÉTERMINISTE, pour que deux runs sur le même
    référentiel évincent les mêmes balises. Sans lui, l'ordre des
    ex æquo dépendrait de l'ordre de lecture des fichiers, et le tau
    comparerait des populations qui bougent sans raison.
    """
    #: −inf pour les sans-altitude : elles sortent en premier.
    def _rang(b: dict) -> tuple:
        alt = b["elev"] if b["elev"] is not None else float("-inf")
        return (-alt, b["source"], b["id"])

    ordonnee = sorted(population, key=_rang)
    if cap >= len(ordonnee):
        return ordonnee, []
    gardees, evincees = ordonnee[:cap], ordonnee[cap:]
    apercu = ", ".join(
        f"{b['source']}:{b['id']}"
        + (f" ({b['elev']:.0f} m)" if b["elev"] is not None else " (sans alt.)")
        for b in evincees[:5])
    crier(f"⚠️ CAP BUDGÉTAIRE {cap} : {len(evincees)} balise(s) ÉVINCÉE(S) "
          f"de la passe candidates — {apercu}"
          + (" …" if len(evincees) > 5 else "")
          + " (rang 1 = altitude DÉCROISSANTE, les plus basses sortent "
            "d'abord ; rang 2 = source:id, pour que l'ordre soit "
            "déterministe)")
    return gardees, evincees


# ══════════════════════════════════════════════════════════════════
#  LA SONDE DE FRAÎCHEUR DE RUN
# ══════════════════════════════════════════════════════════════════

def sonde_fraicheur(budget, avec_temoins: bool = True,
                    crier=print) -> tuple[dict, dict]:
    """Quel run Open-Meteo sert CE SOIR, par modèle. Rend `(par_modele,
    journal)`.

    ⭐ C'EST LA COLONNE QUI TRANSFORME UNE HYPOTHÈSE EN DONNÉE. Le S0.10
    a mesuré, sur UNE nuit, qu'`icon_d2` sert un run 03 Z aux candidates
    (05:00) et un run 00 Z à Pioupiou (03:19) : trois heures d'écart, sur
    un modèle sur six. Tant que ce n'est pas ÉCRIT DANS L'ARCHIVE, le
    tau de Kendall du §S3 ne pourra pas le neutraliser, et l'écart
    restera une hypothèse à n = 1 dans une archive irremplaçable.

    ⛔ **CHAQUE APPEL PASSE PAR `Budget.demander()`, ET RÉSERVE LE PIRE
    CAS** (`POIDS_SONDE`, cf. son pavé). Le S0.10 a mesuré ces mêmes
    URL depuis le Mac, précisément pour ne pas engager le seau du VPS ;
    en production c'est l'inverse qui est vrai — le quota Open-Meteo se
    compte par adresse IP, et c'est celle du VPS qui collecte.

    ⚠️ **UN ÉCHEC NE TUE PAS LA PASSE.** On écrit ce qu'on a, on dit ce
    qui manque, et la collecte part quand même : une colonne
    d'information ne doit jamais coûter une nuit d'archive.
    """
    par_modele: dict[str, dict] = {}
    jrn: dict = {"appels": 0, "ok": 0, "echecs": [], "refuses": [],
                 "temoins": {}, "poids_reserve": 0.0}

    cibles = [(m, d) for m, d in DOMAINE_PAR_MODELE.items()]
    if avec_temoins:
        cibles += [(None, d) for d in DOMAINES_TEMOINS]

    for modele, domaine in cibles:
        if budget is not None:
            try:
                budget.demander(POIDS_SONDE,
                                etiquette=f"sonde meta.json {domaine}")
                jrn["poids_reserve"] += POIDS_SONDE
            except Exception as exc:                         # noqa: BLE001
                # ⚠️ `BudgetRefuse` est un refus ARGUMENTÉ, pas une
                # panne — et il ne doit pas emporter la collecte.
                jrn["refuses"].append(f"{domaine} ({exc})")
                continue
        jrn["appels"] += 1
        d = _get_json_retry(META_API.format(domaine=domaine),
                            f"meta.json {domaine}")
        if not isinstance(d, dict) or not d.get("last_run_initialisation_time"):
            jrn["echecs"].append(domaine)
            continue
        jrn["ok"] += 1
        info = {
            "domaine": domaine,
            "init": d.get("last_run_initialisation_time"),
            "avail": d.get("last_run_availability_time"),
        }
        if modele:
            par_modele[modele] = info
        else:
            jrn["temoins"][domaine] = info

    if jrn["echecs"] or jrn["refuses"]:
        crier(f"  ⚠️ sonde de fraîcheur INCOMPLÈTE : {jrn['ok']}/"
              f"{len(cibles)} domaines rendus"
              + (f" · échecs : {', '.join(jrn['echecs'])}"
                 if jrn["echecs"] else "")
              + (f" · refusés par le budget : {', '.join(jrn['refuses'])}"
                 if jrn["refuses"] else "")
              + " — la collecte part quand même, les lignes des modèles "
                "manquants n'auront pas `run_init`.")
    return par_modele, jrn


# ══════════════════════════════════════════════════════════════════
#  LES CLÉS ET LE MANIFESTE
# ══════════════════════════════════════════════════════════════════

#: Version du format de manifeste — la MÊME que `collect.py`, parce
#: qu'un lecteur qui voit un numéro qu'il ne connaît pas doit s'ARRÊTER,
#: pas deviner, et qu'il n'y a aucune raison d'avoir deux numérotations.
MANIFESTE_VERSION = 1


def fcstreduit_cle(quand: datetime) -> str:
    """La clé R2 des données. UN objet par jour, jamais réécrit.

    ⛔ CE FLUX N'EST PAS UNE PARTIE DE `fcst/`, et le préfixe est ce qui
    le dit. `collect.FLUX_PARTITIONNE` vaut `"fcst"` et reste vrai : la
    partition du S0.6 découpe UNE population par groupe de modèles, ici
    c'est UNE AUTRE POPULATION. Écrire dans `fcst_*` ferait compter
    cette passe comme une partie manquante de la nuit Pioupiou — donc
    basculer des centaines de cases en `partie_manquante` sur une nuit
    qui n'a rien perdu. Le banc `test_cles_caractere_pour_caractere` le
    tient, à la chaîne près.
    """
    return f"{FLUX}/{quand:%Y/%m}/{FLUX}_{quand:%Y-%m-%d}.ndjson.gz"


def manifeste_cle(quand: datetime) -> str:
    """La clé du manifeste — LATÉRALE, jamais une ligne dans l'archive.

    ⚠️ Elle finit par `.manifeste.json` et non `.ndjson.gz`, et c'est
    ce suffixe-là qui la fait voir par `collect.en_retard()` : celui-ci
    cherche `("*.ndjson.gz", "*.manifeste.json")` en `rglob` sur TOUTE
    la racine, donc le préfixe neuf est couvert sans une ligne de plus
    — mais ça se VÉRIFIE, ça ne se suppose pas. 300 octets perdus font
    noter une nuit sur une partie sur deux, en silence (S0.6).
    Banc : `test_en_retard_voit_le_manifeste_du_flux_neuf`.
    """
    return f"{FLUX}/{quand:%Y/%m}/{FLUX}_{quand:%Y-%m-%d}.manifeste.json"


def construire_manifeste(quand: datetime, n_points: int,
                         cles_ecrites: list[str],
                         groupes: list | None = None,
                         sonde: dict | None = None) -> dict:
    """Ce que la nuit DÉCLARE écrire, avant d'avoir collecté quoi que ce
    soit.

    ⛔⛔ **LE DISCRIMINANT EST `cles_ecrites` — CE QUE CE RUN ÉCRIT —,
    JAMAIS `len(groupes)`.** C'est le défaut du S0.9, trouvé et corrigé
    la veille de ce lot : `collect.construire_manifeste` déclarait deux
    parties parce que `groupes_requete()` en rend toujours deux, alors
    que le run `--passe 0` écrivait TOUT dans une seule clé. 513 cases
    ont failli basculer en `partie_manquante` sur une nuit complète.
    Ici, le nombre de parties est la LONGUEUR DE LA LISTE DES CLÉS que
    l'appelant va écrire : il ne peut pas mentir sans que l'appelant
    mente d'abord.

    ⚠️ **ÉCRIT AVANT LA PREMIÈRE LIGNE DE DONNÉES, ET JAMAIS RÉÉCRIT.**
    C'est l'ORDRE qui fait tout le travail : si l'écriture des données
    échoue après, la déclaration existe déjà. L'inverse laisserait
    exactement le trou qu'un manifeste ferme, parce que le cas qui nous
    intéresse est celui où la passe meurt en cours de route.

    ⚠️ **LE BILAN NOMME SON FLUX.** `flux` n'est pas décoratif :
    `score.snapshot_rows` lit QUATRE flux depuis ce lot, et un seul est
    partitionné. Sans le nom, « 1 partie » se lirait « il manque des
    flux ».

    ⭐ `sonde` porte le run servi par chaque domaine cette nuit-là,
    témoins compris — les quatre modèles que la passe Pioupiou collecte
    et que celle-ci ne collecte pas. Sans eux, la nuit où l'écart
    bougerait, on ne saurait pas si c'est `icon_d2` qui a changé ou
    toute la chaîne de publication.
    """
    groupes = groupes if groupes is not None else groupes_reduit()
    modeles_union = [m for m in MODELS_REDUIT
                     if m in {x for grp, _v in groupes for x in grp}]
    n_vars_union = len({v for _m, vs in groupes for v in vs})
    detail = [{
        "i": i,
        "cle": cle,
        "modeles": modeles_union,
        "n_vars": n_vars_union,
        "poids_point": round(poids_par_point_reduit(), 4),
    } for i, cle in enumerate(cles_ecrites, 1)]
    manifeste = {
        "version": MANIFESTE_VERSION,
        "flux": FLUX,
        "jour": f"{quand:%Y-%m-%d}",
        "parties": len(detail),
        "n_points": n_points,
        "poids_point_total": round(
            sum(d["poids_point"] for d in detail), 4),
        "detail": detail,
        "ecrit_par": "collect_reduit.py",
        "ecrit_a": quand.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if sonde is not None:
        manifeste["sonde_fraicheur"] = sonde
    return manifeste


# ══════════════════════════════════════════════════════════════════
#  LA COLLECTE
# ══════════════════════════════════════════════════════════════════

def collecter(stations: list[dict], groupes: list, budget, qm,
              fetched_at: str, fraicheur: dict, forecast_days: int,
              jrn: dict, crier=print):
    """Génère les lignes NDJSON. Remplit `jrn` au passage.

    ⚠️ **AU FIL DE L'EAU, JAMAIS EN MÉMOIRE.** `write_ndjson_gz` écrit
    chaque ligne à mesure : si le script est tué à mi-parcours, on garde
    ce qui a été collecté. Tout garder pour n'écrire qu'à la fin, c'est
    risquer de tout perdre sur une coupure — et une nuit de collecte
    perdue ne se rattrape pas.

    ⚠️ **UN REFUS DE BUDGET EST UN TROU DÉCLARÉ, JAMAIS COMBLÉ**, et il
    ne tue pas le run : c'était la mort du 09/08. Il se compte, par
    groupe, et la ligne de journal le dit.
    """
    poids_groupe = ([qm.poids(len(v), len(m)) for m, v in groupes]
                    if qm else [None] * len(groupes))
    jrn.setdefault("collectes_g", [0] * len(groupes))
    jrn.setdefault("refuses_g", [0] * len(groupes))
    jrn.setdefault("failed", 0)
    jrn.setdefault("partiels", 0)
    jrn.setdefault("refuses", 0)
    jrn.setdefault("lignes_par_modele", {})

    for i, st in enumerate(stations, 1):
        perdus = 0
        for gi, ((modeles, variables), p) in enumerate(
                zip(groupes, poids_groupe)):
            if budget is not None:
                try:
                    budget.demander(
                        p, etiquette=f"{st['lat']:.3f},{st['lon']:.3f} "
                                     f"g{gi + 1}")
                except qm.BudgetRefuse as exc:
                    crier(f"  ⛔ {exc}")
                    jrn["refuses"] += 1
                    jrn["refuses_g"][gi] += 1
                    perdus += 1
                    continue
            else:
                # Module absent : cadence conservatrice, celle qui a
                # tenu le 08/08, divisée par le nombre de groupes.
                time.sleep(0.70 / len(groupes))

            payload = fetch_forecast(st["lat"], st["lon"], forecast_days,
                                     modeles, variables)
            if payload is None:
                perdus += 1
                continue
            jrn["collectes_g"][gi] += 1
            for row in forecast_rows(st, payload, fetched_at, modeles):
                # ⭐ LA COLONNE QUI REND L'ÉCART MESURABLE, écrite DANS
                # CHAQUE LIGNE et non dans un fichier à côté : une
                # archive qu'on relira dans trois ans ne doit dépendre
                # d'aucun objet latéral. ⚠️ Un champ ABSENT signifie
                # « la sonde n'a pas eu ce domaine cette nuit-là », ce
                # qui est une information ; un `null` ne dirait rien.
                info = fraicheur.get(row["model"])
                if info:
                    row["run_init"] = info["init"]
                    row["run_avail"] = info["avail"]
                jrn["lignes_par_modele"][row["model"]] = \
                    jrn["lignes_par_modele"].get(row["model"], 0) + 1
                yield row
        if perdus:
            jrn["failed"] += 1
            if perdus < len(groupes):
                jrn["partiels"] += 1
        if i % 250 == 0:
            crier(f"  … {i}/{len(stations)} ({jrn['failed']} points entamés)")


def dire_journal(jrn_pop: dict, crier=print) -> None:
    """⚠️ LE JOURNAL EST UN LIVRABLE, pas un confort de mise au point.

    Ce chantier existe parce qu'une session a écrit quatre fois « reste
    à constater la première nuit » sans jamais aller compter. Ce journal
    dit, à chaque run : d'où vient la population, ce que la règle a
    exclu, ce que la réserve a évincé, ce que la sonde a mesuré, et ce
    que la nuit a réellement coûté.
    """
    crier("┌─ POPULATION ─────────────────────────────────────────────────")
    for nom, n in jrn_pop["referentiels"].items():
        crier(f"│   {nom:30s} {'ABSENT' if n is None else f'{n:5d} points'}")
    crier(f"│ dédoublonné (source:id)  : {jrn_pop['dedup']}")
    crier(f"│ − sources exclues        : "
          + " · ".join(f"{k} {v}" for k, v in sorted(
              jrn_pop["exclues_source"].items())))
    if jrn_pop["repli_sans_obs"]:
        crier("│ ⛔ REPLI : aucune archive d'observations de la veille — "
              "la règle des muettes n'a RIEN retiré")
    else:
        crier(f"│ − muettes de la veille   : {jrn_pop['muettes']}  ("
              + " · ".join(f"{k} {v}" for k, v in sorted(
                  jrn_pop["muettes_par_source"].items())) + ")")
        crier("│   archives lues          : "
              + " · ".join(f"{k} {v}" for k, v in sorted(
                  jrn_pop["obs_lues"].items())))
    if jrn_pop["obs_absentes"]:
        crier(f"│   ⚠️ archives ABSENTES   : "
              f"{', '.join(jrn_pop['obs_absentes'])}")
    if jrn_pop["sans_elev"]:
        crier(f"│   ⚠️ sans altitude       : {jrn_pop['sans_elev']} "
              f"(évincées EN PREMIER — rang 1)")
    crier("└──────────────────────────────────────────────────────────────")


def dire_budget(population: int, jrn_cap: dict, evincees: int,
                crier=print) -> None:
    """La ligne de budget, ÉCRITE AVANT LA PREMIÈRE REQUÊTE.

    ⛔ Elle NOMME le garde-fou qui mord. Un garde-fou qui annonce
    l'échéance d'un autre ne sert à rien — c'est la correction du S0.4
    sur `quota_projete`, transposée.
    """
    cap, cout = jrn_cap["cap"], jrn_cap["cout_point"]
    crier("┌─ BUDGET DE LA PASSE CANDIDATES ──────────────────────────────")
    crier(f"│ source du budget       : {jrn_cap['source']}")
    if jrn_cap["par_consommateur"]:
        crier("│ fenêtre JOUR par consommateur : "
              + " · ".join(f"{k} {v:.1f}" for k, v
                           in jrn_cap["par_consommateur"].items()))
    crier(f"│ plafond jour effectif  : {jrn_cap['plafond_jour']:.0f}")
    crier(f"│ budget mesuré (AUTRES) : {jrn_cap['autres']:.1f}  "
          f"(sa propre étiquette « {ETIQUETTE_BUDGET} » est EXCLUE — "
          f"fenêtre glissante de 24 h)")
    crier(f"│ réserve nommée         : {jrn_cap['reserve']:.0f}  "
          f"(870 croissance Pioupiou + 500 scripts manuels, sonde comprise)")
    crier(f"│ coût / point           : {cout:.2f} pondérés")
    crier(f"│ ⇒ CAP                  : {cap} points")
    crier(f"│ population du jour     : {population} points")
    crier(f"│ ⇒ ÉVINCÉES             : {evincees}")
    n = min(cap, population)
    crier(f"│ poids projeté du run   : {n * cout:.0f} pondérés "
          f"({n} points × {cout:.2f})")
    qui = ("la RÉSERVE BUDGÉTAIRE" if evincees else
           "aucun — la population tient sous le cap")
    crier(f"│ GARDE-FOU QUI MORD     : {qui}")
    crier("└──────────────────────────────────────────────────────────────")


def dire_sonde(jrn_sonde: dict, fraicheur: dict, crier=print) -> None:
    crier("┌─ SONDE DE FRAÎCHEUR DE RUN ──────────────────────────────────")
    crier(f"│ appels : {jrn_sonde['appels']} · rendus {jrn_sonde['ok']} · "
          f"{jrn_sonde['poids_reserve']:.0f} pondérés RÉSERVÉS "
          f"(pire cas {POIDS_SONDE:.0f}/appel — le poids réel de cet "
          f"endpoint n'est pas établi)")
    for m in MODELS_REDUIT:
        info = fraicheur.get(m)
        if info:
            crier(f"│   {m:28s} run {info['init']} · publié {info['avail']}")
        else:
            crier(f"│   {m:28s} ⚠️ non rendu — lignes sans `run_init`")
    for d, info in sorted(jrn_sonde["temoins"].items()):
        crier(f"│   (témoin) {d:20s} run {info['init']} · publié "
              f"{info['avail']}")
    crier("└──────────────────────────────────────────────────────────────")


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="/var/lib/bw-model-verif",
                    help="racine locale de l'archive")
    ap.add_argument("--forecast-days", type=int, default=3)
    ap.add_argument("--day", default=None,
                    help="journée d'ÉMISSION (défaut : aujourd'hui). Les "
                         "muettes se lisent sur la veille de ce jour-là.")
    ap.add_argument("--sans-sonde", action="store_true",
                    help="ne pas appeler les 9 meta.json (−9 pondérés). "
                         "⚠️ La donnée n'est PAS rejouable : les lignes de "
                         "cette nuit n'auront jamais `run_init`.")
    ap.add_argument("--dry-run", action="store_true",
                    help="tout chiffrer et sortir, sans une seule requête "
                         "météo et sans un octet écrit")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    now = (datetime.strptime(args.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
           if args.day else datetime.now(timezone.utc))
    veille = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0,
                                               microsecond=0)
    fetched_at = now.isoformat()
    cout = poids_par_point_reduit()

    print(f"▶ groupe réduit sur les candidates — journée d'émission "
          f"{now:%Y-%m-%d}, {len(MODELS_REDUIT)} modèles "
          f"({', '.join(MODELS_REDUIT)}), {cout:.2f} pondéré/point")

    try:
        groupes = groupes_reduit()
        population, jrn_pop = charger_population(out, veille)
        if not population:
            raise Abort(
                f"population VIDE : les référentiels de {out} ne donnent "
                f"aucun point hors {'/'.join(SOURCES_EXCLUES)} qui ait été "
                f"observé le {veille:%Y-%m-%d}. Ce n'est pas une nuit "
                f"maigre, c'est une chaîne cassée — regarder "
                f"`bw-model-collect` de cette nuit.")
        dire_journal(jrn_pop)

        qm = charger_quota()
        budget = qm.Budget(ETIQUETTE_BUDGET) if qm else None
        # ⚠️ Le repli est DÉRIVÉ du référentiel réel, jamais d'un nombre
        # écrit ici : `collect.poids_par_point()` suit les modèles et les
        # variables de la passe Pioupiou, un 3 810,6 en dur non.
        import collect as _c                                  # noqa: PLC0415
        n_pp = jrn_pop["referentiels"].get("stations.json") or 0
        conso_repli = n_pp * _c.poids_par_point() + BACKFILL_PACKS_MESURE
        cap, jrn_cap = cap_budgetaire(qm, budget, cout, conso_repli)
        stations, evincees = trier_et_evincer(population, cap)
        dire_budget(len(population), jrn_cap, len(evincees))
    except Abort as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    key = fcstreduit_cle(now)
    m_key = manifeste_cle(now)

    if args.dry_run:
        # ⛔ AUCUNE REQUÊTE, PAS MÊME LA SONDE. Le §8 du prompt est
        # formel : la PREMIÈRE dépense Open-Meteo du groupe réduit est
        # la première nuit après activation. Tout chiffrage passe par
        # `poids_url()` sur des URL construites et non envoyées.
        urls = []
        for modeles, variables in groupes:
            params = {"latitude": "45.9000", "longitude": "6.1000",
                      "hourly": ",".join(variables),
                      "models": ",".join(modeles),
                      "forecast_days": str(args.forecast_days),
                      "wind_speed_unit": "kmh", "timeformat": "unixtime"}
            urls.append(f"{FORECAST_API}?{urllib.parse.urlencode(params)}")
        print("┌─ CHIFFRAGE (URL CONSTRUITES, JAMAIS ENVOYÉES) ───────────────")
        total = 0.0
        for u, (modeles, variables) in zip(urls, groupes):
            p = qm.poids_url(u) if qm else (len(modeles) * len(variables) / 10)
            total += p
            print(f"│ {len(modeles)} modèles × {len(variables)} vars = "
                  f"{p:.4f} pondéré/point — {', '.join(modeles)}")
        print(f"│ TOTAL / point : {total:.4f}"
              + ("  ⛔ INCOHÉRENT avec poids_par_point_reduit() "
                 f"({cout:.4f})" if abs(total - cout) > 1e-9 else ""))
        print(f"│ passe        : {len(stations)} points × {cout:.2f} = "
              f"{len(stations) * cout:.0f} pondérés")
        print(f"│ sonde        : {0 if args.sans_sonde else len(DOMAINE_PAR_MODELE) + len(DOMAINES_TEMOINS)}"
              f" appels × {POIDS_SONDE:.0f} = "
              f"{0 if args.sans_sonde else (len(DOMAINE_PAR_MODELE) + len(DOMAINES_TEMOINS)) * POIDS_SONDE:.0f}"
              f" pondérés réservés")
        print(f"│ clé données  : {key}")
        print(f"│ clé manifeste: {m_key}")
        print("└──────────────────────────────────────────────────────────────")
        print("  (dry-run : aucune requête météo, aucun fichier, aucun R2)")
        return 0

    # ── 0. RATTRAPAGE ────────────────────────────────────────────
    # ⚠️ Avant tout le reste, et il couvre TOUS les préfixes :
    # `collect.en_retard()` fait un `rglob` sur la racine, donc le flux
    # neuf y entre sans une ligne de plus. Vérifié, pas supposé.
    rattraper(out)

    # ── 1. LA SONDE, AVANT LE MANIFESTE ──────────────────────────
    fraicheur: dict = {}
    jrn_sonde = {"appels": 0, "ok": 0, "echecs": [], "refuses": [],
                 "temoins": {}, "poids_reserve": 0.0}
    if not args.sans_sonde:
        fraicheur, jrn_sonde = sonde_fraicheur(budget)
        dire_sonde(jrn_sonde, fraicheur)
    else:
        print("  ⚠️ --sans-sonde : les lignes de cette nuit n'auront JAMAIS "
              "`run_init` — la donnée n'est pas rejouable.")

    # ── 2. LE MANIFESTE, AVANT LA PREMIÈRE LIGNE DE DONNÉES ──────
    # ⛔ Et JAMAIS réécrit. C'est l'ordre qui fait le travail : si
    # l'écriture des données échoue après, la déclaration existe déjà.
    m_path = out / m_key
    m_path.parent.mkdir(parents=True, exist_ok=True)
    manifeste = construire_manifeste(
        now, len(stations), [key], groupes,
        sonde={"par_modele": fraicheur, "temoins": jrn_sonde["temoins"],
               "poids_reserve": jrn_sonde["poids_reserve"]})
    m_path.write_text(json.dumps(manifeste, ensure_ascii=False, indent=1)
                      + "\n", encoding="utf-8")
    print(f"  ⓘ manifeste : {manifeste['parties']} partie(s) déclarée(s) "
          f"pour le flux `{FLUX}/` du {now:%Y-%m-%d} → {m_key}")
    if not upload_r2(m_path, m_key):
        print("  ⚠️ manifeste non monté sur R2 — présent en local, "
              "rattrapage au prochain run", file=sys.stderr)

    # ── 3. LA PASSE DEMANDE SA PLACE, ELLE NE LA SUPPOSE PAS ─────
    # ⚠️ Importé de `collect.py`, sans une ligne modifiée. Si la passe
    # Pioupiou a débordé sur son heure, ses événements ne sortent de la
    # fenêtre glissante qu'une heure après son DERNIER appel : partir
    # quand même ferait refuser POINT PAR POINT, en fabriquant des
    # milliers de trous déclarés là où attendre une fois ramène tout.
    attendu = 0.0
    try:
        attendu = attendre_la_place(budget, len(stations) * cout, 1)
    except Abort as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    # ── 4. LA COLLECTE ───────────────────────────────────────────
    path = out / key
    print(f"▶ prévisions : {len(stations)} points × {len(MODELS_REDUIT)} "
          f"modèles, en {len(groupes)} requête(s) par point "
          + " + ".join(f"{len(m)}×{len(v)}" for m, v in groupes)
          + f" → {path}")
    jrn_col: dict = {}
    debut = time.time()
    n = write_ndjson_gz(path, collecter(stations, groupes, budget, qm,
                                        fetched_at, fraicheur,
                                        args.forecast_days, jrn_col))
    duree = time.time() - debut

    if not n:
        print("❌ zéro ligne écrite alors que la population n'est pas vide — "
              "ce n'est pas une nuit maigre, c'est un run cassé (règle du "
              "suffixe de modèle ? budget refusé de bout en bout ?).",
              file=sys.stderr)
        return 1

    print(f"✅ {n} lignes, {jrn_col['failed']} point(s) ayant perdu au moins "
          f"un groupe (dont {jrn_col['partiels']} partiel(s), "
          f"{jrn_col['refuses']} refus de quota), "
          f"{path.stat().st_size / 1024:.0f} Ko, {duree / 60:.1f} min"
          + (f", après {attendu:.0f}s d'attente de quota au démarrage"
             if attendu else ""))
    for gi, (modeles, variables) in enumerate(groupes):
        pds = jrn_col["collectes_g"][gi] * len(modeles) * len(variables) / 10
        print(f"   groupe {gi + 1}/{len(groupes)} ({len(modeles)} modèles × "
              f"{len(variables)} vars, {len(modeles) * len(variables) / 10:.1f} "
              f"pondéré/point) : {jrn_col['collectes_g'][gi]}/{len(stations)} "
              f"points collectés, {jrn_col['refuses_g'][gi]} refusés faute de "
              f"budget — {pds:.1f} pondérés")
    print("   lignes par modèle : "
          + " · ".join(f"{k} {v}" for k, v
                       in sorted(jrn_col["lignes_par_modele"].items())))
    # ⚠️ LA LIGNE QUI NOMME LES CONSOMMATEURS. Un budget partagé qui ne
    # dit pas QUI a consommé QUOI déplace le problème au lieu de le
    # résoudre.
    if budget is not None:
        print(f"ⓘ {budget.resume()}")
        for nom_f, info in budget.etat()["fenetres"].items():
            if info["par_consommateur"]:
                detail = ", ".join(f"{q} {v:.0f}" for q, v
                                   in info["par_consommateur"].items())
                print(f"   {nom_f:<7} {info['consomme']:>6.0f}/"
                      f"{info['plafond']:<6} — {detail}")

    if not upload_r2(path, key):
        # Même politique que `collect.py` et `arome_fcst.py` : le local
        # reste, le témoin n'est pas posé, `rattraper()` réessaiera — et
        # le run SORT EN ERREUR plutôt que d'annoncer un succès sur une
        # archive qui n'existe que sur le disque d'une machine que
        # personne ne sauvegarde.
        print("❌ archive du groupe réduit non montée sur R2 (conservée "
              "localement)", file=sys.stderr)
        return 2
    print(f"  témoin posé : {temoin(path).name}")

    # ⚠️ Sortie en erreur si plus d'un point sur cinq a échoué : une
    # nuit à moitié collectée doit réveiller quelqu'un, pas passer au
    # vert. `run.sh collect-reduit` a `SEUIL_ALERTE=1` — ce flux ne se
    # rejoue pas.
    if jrn_col["failed"] > len(stations) // 5:
        print(f"❌ {jrn_col['failed']}/{len(stations)} points ont perdu au "
              f"moins un groupe — plus d'un sur cinq. La nuit est écrite "
              f"mais elle est TROUÉE, et ces trous ne se rattrapent pas.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
