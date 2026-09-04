#!/usr/bin/env python3
"""score.py — apparier, agréger, accumuler, publier.

    Session 08/08/2026.
    cf. PWA/web/CONCEPTION_SCORE_MODELES_06-08.md §8, §15.2, §16.1, §16.3
    et PWA/web/supabase_step35_model_verification.sql.

═══ CE QUE FAIT UN RUN ═══

Pour UNE journée D (hier par défaut) :

  1. relit l'archive de `collect.py` — les prévisions émises les jours
     D, D-1 et D-2, et les observations des jours D et D-1 ;
  2. apparie prévu/observé heure par heure, par (station, modèle,
     classe d'échéance) ;
  3. écrit un agrégat quotidien par ligne dans `model_verif_daily` ;
  4. fait avancer les accumulateurs à mémoire longue de
     `model_character`, par zone × régime × tranche de vent ;
  5. recalcule `model_score_zone` et publie `model_scores.json` sur R2 ;
  6. purge ce qui a dépassé sa rétention.

⚠️ LE JOB EST IDEMPOTENT. Le relancer sur la même journée écrit les
mêmes lignes (upsert) et ne fait PAS avancer les accumulateurs deux
fois (`accumulate` refuse une journée déjà intégrée). C'est la même
exigence que partout ailleurs dans ce projet, et elle est ici
particulièrement importante : un accumulateur compté deux fois ne se
répare pas, il faudrait rejouer toute l'histoire.

═══ LA CLASSE D'ÉCHÉANCE, ET POURQUOI CE N'EST PAS UNE ÉCHÉANCE ═══

Le snapshot du jour X, pris vers 03 h UTC, couvre X à X+2. Pour noter
la journée D :

  · le snapshot de D   → échéances 3 à 21 h   → classe « +6 h »
  · le snapshot de D-1 → échéances 24 à 45 h  → classe « +24 h »
  · le snapshot de D-2 → échéances 48 à 69 h  → classe « +48 h »

`lead_exact_h` porte l'échéance réelle moyenne de la journée, parce que
la classe seule ferait croire à une précision qu'elle n'a pas. Le §8.3
parle de « +6 h / +24 h / +48 h » comme si c'étaient des échéances
exactes ; ce sont des bandes, et c'est vrai aussi de l'API Previous
Runs, dont `previous_dayN` désigne un RUN et pas une échéance.

═══ CE QUI DÉGRADE PROPREMENT ═══

`station_zone` est probablement vide au premier run : l'affectation
d'une balise à son bassin-versant demande le relief, et n'est pas faite
par ce lot. Conséquence assumée : les étapes 1 à 3 tournent quand même
(elles ne connaissent aucune zone), et les étapes 4 et 5 sautent en le
DISANT. Une balise sans zone n'est pas rangée dans une case au hasard.
"""
from __future__ import annotations

import argparse
import gc
import gzip
import json
import math
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import controle_position as CP  # noqa: E402
import biais_fin as BF  # noqa: E402
import duel as DUEL  # noqa: E402
import melange as MX  # noqa: E402
import events as EV  # noqa: E402
import inference as INF  # noqa: E402
import murphy as MU  # noqa: E402
import scoring as S  # noqa: E402

DAY_MS = 86_400_000

#: Classe d'échéance ← nombre de jours entre le snapshot et la journée notée.
LEAD_BY_OFFSET = {0: 6, 1: 24, 2: 48}

#: ⛔ LA CLASSE COURTE (lot L10, 30/08/2026) — DEUX ÉTIQUETTES, ET
#: ELLES SONT NÉGATIVES EXPRÈS.
#:
#: Le cadre 2 ne note pas un HORIZON, il note un INSTANT DE DÉCISION :
#: « ce que tu pouvais savoir à T ». Les six heures qu'il note sont à
#: +1 … +6 h de T, donc l'échéance moyenne vaut ~3,5 h et elle vit dans
#: `lead_exact_h`, comme partout ailleurs. Il fallait néanmoins une
#: valeur de `lead_h` pour CLÉER la classe (décision Q2 de Yann : une
#: nouvelle valeur + CHECK élargi, jamais un nouveau nom de modèle sous
#: `lead_h = 6` — « un avantage silencieux sous le même intitulé »,
#: refusé le 13/08).
#:
#: ⛔ POURQUOI PAS 3, NI 1, NI 0. N'importe quel petit entier POSITIF se
#: lirait comme une échéance et s'alignerait, dans un tableau, à côté de
#: 6, 24 et 48 comme s'il était de la même famille. Il ne l'est pas :
#: ces trois-là disent « à combien d'heures », celle-ci dit « depuis
#: quel instant ». Un entier NÉGATIF est impossible à confondre avec une
#: échéance, et c'est exactement le service qu'on lui demande.
#:
#: ⚠️ ET DEUX VALEURS, PAS UNE. Les deux instants T ne sont pas
#: interchangeables : le matin et l'après-midi n'ont ni le même régime,
#: ni le même run disponible. Les fondre sous une seule clé mélangerait
#: deux runs dans une même journée-balise — et la clé primaire de
#: `model_verif_daily` (`day, source, station_id, model, lead_h,
#: fcst_src`) ne le permettrait qu'au prix d'un `fetched_at` unique pour
#: deux runs, c'est-à-dire d'un `lead_exact_h` FAUX sur la moitié des
#: heures.
LEAD_COURT_MATIN = -1
LEAD_COURT_APREM = -2
LEADS_COURTS = (LEAD_COURT_MATIN, LEAD_COURT_APREM)

#: ⛔ LA CLASSE AU QUART D'HEURE (lot L11, 31/08/2026) — deux étiquettes
#: de plus, NÉGATIVES pour la même raison, et DISTINCTES de celles de la
#: classe courte pour une raison qui lui est propre.
#:
#: Ces lignes notent les MÊMES deux instants de décision (06:50 et
#: 12:50 Z) que la classe courte, mais pas les mêmes échéances : `:15`,
#: `:30` et `:45`, jamais l'heure ronde. Les fondre sous `−1`/`−2`
#: mettrait DEUX PAS DE TEMPS sous une seule étiquette — c'est
#: exactement la variante (b) refusée en Q2 le 30/08 (« un avantage
#: silencieux sous le même intitulé »), prise par l'autre bout : ici ce
#: ne serait pas la fraîcheur qui se cacherait, ce serait la RÉSOLUTION,
#: et un lecteur du tableau de fiabilité ne pourrait plus dire lequel
#: des deux pas il regarde.
#: ⓘ Décision de Yann du 31/08 (question « clé SQL » du lot L11).
LEAD_QUART_MATIN = -3
LEAD_QUART_APREM = -4
LEADS_QUARTS = (LEAD_QUART_MATIN, LEAD_QUART_APREM)

#: ⛔ TOUTES LES ÉTIQUETTES D'INSTANT DE DÉCISION, en un seul endroit.
#: Les trois lieux qui doivent les écarter (le caractère, le classement,
#: le repli d'upsert) lisent CELLE-CI. Trois listes recopiées, c'est
#: trois occasions d'en oublier une le jour d'une quatrième classe.
LEADS_INSTANT_T = LEADS_COURTS + LEADS_QUARTS

#: Le modèle maison, lu dans un flux à part (lot I, 13/08/2026). Il ne
#: sert ICI qu'à compter des lignes dans le journal : `daily_rows` ne
#: connaît toujours aucun modèle par son nom, et c'est ce qui a rendu
#: ce lot court.
#: ⛔ CE N'EST PLUS VRAI DEPUIS LE LOT L18 (30/08/2026). `_apply_rank`
#: le nomme désormais pour lui REFUSER le rang quand le composite est
#: dans la même case : `agrume` est le vent 10 m BRUT du produit A, un
#: produit que l'écran ne sert à personne (`agrume_fcst.py` le dit en
#: tête de fichier). Il reste collecté, noté et publié — il ne se
#: classe plus CONTRE le produit servi.
AGRUME_MODEL = "agrume"

#: La série composite AROME + AROME-PI (26/08/2026), écrite par
#: `agrume_fcst.py` dans le MÊME flux et sous un SECOND nom.
#: ⛔ Un second nom et non une correction d'`agrume` : muter la série en
#: place aurait mélangé deux définitions dans une même fenêtre glissante
#: de 14 et 30 jours, sans qu'une seule ligne ne le dise. La raison
#: complète est dans `agrume_fcst.MODEL_PI`.
#: ⓘ Comme `AGRUME_MODEL`, il ne sert ICI qu'à compter des lignes dans
#: le journal — `daily_rows` ne connaît toujours aucun modèle par son
#: nom, et c'est ce qui rend ce branchement court.
AGRUME_PI_MODEL = "agrume_pi"

#: ⛔ LES DEUX SOUS-SÉRIES DE LA CLASSE COURTE (lot L10, décision Q7 de
#: Yann du 30/08) — le MÊME composite, à deux poids de Δ.
#:
#: `w = 1` sert le plus frais tel quel ; `w = 0,5` sert la moyenne des
#: deux, que la phase B mesure comme l'optimum hors échantillon (gain
#: +0,08 à +0,15 km/h, appris sur huit journées d'août seulement).
#: ⛔ AUCUNE DES DEUX N'EST CLASSÉE, et c'est le fond de la décision :
#: choisir maintenant reviendrait à deviner sur huit journées, et
#: publier les deux au classement ferait concourir un produit contre
#: lui-même. Elles sont NOTÉES — donc lisibles dans la feuille de
#: fiabilité, avec leurs erreurs absolues — et le tableau tranchera sur
#: plusieurs semaines. Le motif est `RANK_REASON_SERIE_EN_ESSAI`.
#: ⚠️ La rampe `poids_pi` ne s'applique PAS ici : à ces échéances elle
#: servirait de l'AROME pur sous une étiquette PI (§3.3 de la
#: conception). Le poids est CONSTANT sur les six heures, et il est
#: dans le nom de la série.
AGRUME_COURT_W1 = "agrume_court_w1"
AGRUME_COURT_W05 = "agrume_court_w05"
MODELES_COURTS = (AGRUME_COURT_W1, AGRUME_COURT_W05)

#: ⛔⛔ LES TROIS SOUS-SÉRIES DE LA CLASSE AU QUART D'HEURE (lot L11,
#: 31/08/2026), ET LA PREMIÈRE EST UN TÉMOIN, PAS UN CONCURRENT.
#:
#: La réserve de la phase B, écrite le 26/08 et jamais refermée depuis :
#: « c'est à :15, :30 et :45 que le composite justifie son existence —
#: là, l'alternative n'est pas AROME, c'est AROME *interpolé* ». Aucune
#: classe du dispositif ne notait cet AROME interpolé. Sans lui, la
#: classe au quart d'heure publierait deux composites que rien ne
#: permettrait de comparer à quoi que ce soit : elle mesurerait, sans
#: rien répondre.
#:
#: `agrume_quart_w0` EST cet AROME interpolé, et ses valeurs aux quarts
#: d'heure sont FABRIQUÉES — 0,31 m/s d'erreur d'interpolation en
#: médiane, 1,08 au q90, mesurés contre PI (`composite.arome_interpole`,
#: qui le dit lui-même). ⛔ C'est précisément pour ça qu'il est publié :
#: le coût de l'interpolation est ce que le composite prétend faire
#: mieux, et on ne peut pas le lire s'il n'est pas noté. Chaque ligne
#: porte `agrume_quart_base_interpolee = true` pour qu'aucune relecture
#: ne puisse le confondre avec une mesure.
#:
#: ⚠️ AUCUNE des trois n'échappe à l'interpolation, et il ne faut PAS
#: lire « part fabriquée = 1 − w » : la valeur servie vaut
#: `AROME₁₀ⁱⁿᵗ + w·kz·(PI₂₀ − AROME₂₀ⁱⁿᵗ)`, donc à `w = 1` il reste le
#: résidu `AROME₁₀ⁱⁿᵗ − kz·AROME₂₀ⁱⁿᵗ`. Ce qui change avec `w`, c'est le
#: poids donné au seul terme dont la moitié est native.
#:
#: ⛔ AUCUNE des trois ne se classe (`RANK_REASON_SERIE_EN_ESSAI`, comme
#: au L10) : faire concourir un témoin fabriqué contre le produit qu'il
#: sert à juger n'aurait aucun sens dans un classement public.
AGRUME_QUART_W0 = "agrume_quart_w0"
AGRUME_QUART_W1 = "agrume_quart_w1"
AGRUME_QUART_W05 = "agrume_quart_w05"
MODELES_QUARTS = (AGRUME_QUART_W0, AGRUME_QUART_W1, AGRUME_QUART_W05)

#: Le pas de la classe au quart d'heure, en secondes. ⓘ Il n'est PAS
#: recopié dans `agrume_quart.py` : c'est lui qui l'importe d'ici, comme
#: `agrume_fcst` importe déjà `STEP_S`. Deux écritures d'un même pas,
#: c'est une demi-fenêtre appariée sur l'un et des heures sur l'autre.
PAS_QUART_S = 900

#: Les deux chaînes qui lisent le MÊME modèle AROME (lot L2, 27/08/2026)
#: — `meteofrance_arome_france_hd` via Open-Meteo, `arome_r2` via nos
#: propres tuiles `arome/sol` relues sur R2 (lot S0.5). L'écart de
#: chaîne mesuré entre les deux (+0,17 km/h médian, audit §2.2/PS2) est
#: de l'ordre des écarts qui séparent des modèles DIFFÉRENTS : dans les
#: 573 Pioupiou où les deux concourent, AROME prenait deux billets au
#: podium pour une seule prévision. Nommées ici parce qu'aucune des
#: deux ne l'était encore dans ce fichier — contrairement à
#: `AGRUME_MODEL`/`AGRUME_PI_MODEL`, qui existaient déjà.
AROME_HD_MODEL = "meteofrance_arome_france_hd"
AROME_R2_MODEL = "arome_r2"

#: Heures minimales appariées pour qu'une journée-balise-modèle compte.
#: En dessous, l'agrégat est du bruit : une balise qui n'a émis que
#: trois heures ne dit rien de la qualité d'un modèle sur la journée.
MIN_HOURS_DAILY = 6

#: ⛔ LE PLANCHER APPARTIENT AU PAS DE LA SÉRIE (lot L11, 31/08/2026),
#: comme la demi-fenêtre — et pour une raison qui se voit en une ligne :
#: `MIN_HOURS_DAILY = 6` sur une classe qui vise 15 échéances serait
#: 2,5 fois plus laxiste que sur une classe qui en vise 6. Une balise
#: notée sur 6 points parmi 15 entrerait dans le même tableau qu'une
#: balise notée sur 15, avec le même intitulé et rien pour le dire.
#:
#: ⚠️ 13 SUR 15, ET C'EST LA TRANSPOSITION EXACTE DU CHOIX DE YANN.
#: Il a tranché « 18 sur 21 » le 31/08, sur le périmètre de 21 points
#: qu'il a ensuite réduit aux 15 quarts seuls : 18/21 = 85,7 %, et
#: 13/15 = 86,7 % — le même niveau d'exigence, transposé plutôt que
#: redécidé. MESURÉ par la sonde du L11 sur vingt jours : **93,8 %** des
#: balise-jour-T tiennent 13/15 à ±7 min (témoin : la classe horaire
#: tient son 6/6 dans 97,9 %).
#:
#: ⭐ CONSÉQUENCE ASSUMÉE, ET C'EST UN RETRAIT PAR LA RÈGLE. Les 39
#: balises `aemet` de la population reportent une fois par heure, à
#: l'heure ronde : la sonde mesure **0,0 %** de fenêtres non vides aux
#: quarts d'heure. Elles tombent sous ce plancher et ne publient rien
#: dans cette classe — sans qu'un seul nom de réseau soit écrit dans le
#: code (VÉRIFIÉ sur la production le 31/08 : 39 servies, 0 notées). Un
#: cas particulier nommé aurait été une règle de plus à maintenir, et
#: une règle qu'un sixième réseau aurait prise en défaut.
PLANCHER_PAR_PAS = {3600: MIN_HOURS_DAILY, 900: 13}


def plancher_du_pas(step_s: int) -> int:
    """Le nombre minimal d'échéances appariées pour qu'une balise-jour
    entre dans le tableau, pour une série de pas `step_s`.

    ⚠️ Un pas inconnu retombe sur `MIN_HOURS_DAILY` : c'est le
    comportement d'avant ce lot, donc aucune série existante ne change
    de population. Le prix est nommé — une classe neuve à un pas non
    déclaré serait notée avec le plancher de l'heure ronde, ce qui est
    laxiste mais visible, plutôt que refusée, ce qui coûterait une nuit.
    """
    return PLANCHER_PAR_PAS.get(int(step_s), MIN_HOURS_DAILY)

#: Balises minimales dans une case avant de publier un score de zone.
MIN_STATIONS_ZONE = 3

#: ⛔ PLANCHER DE LA RÉFÉRENCE D'UN SKILL, EN (km/h)² — 1,0, soit une
#: erreur RMS de 1 km/h. En dessous, `skill`, `skill_clim`,
#: `beats_persist` et `beats_clim` sortent à **null** : jamais à
#: `false`, jamais à un nombre.
#:
#: ⚠️ SON ABSENCE A COÛTÉ TROIS NUITS DE SCORING (12, 13 et 14/08).
#: `1 − MSE_modèle / MSE_référence` divise par presque rien dès qu'une
#: journée sans vent rend la persistance quasi parfaite. Mesuré le
#: 13/08 en rejouant la journée du 11/08 : `skill` descendait à
#: **−2 573 000**, `skill_clim` à **−35 980**. Le second est un
#: `numeric(8,4)` en base (plafond 10⁴) : l'upsert ENTIER repartait en
#: `HTTP 400 — numeric field overflow`, donc aucun score de zone n'était
#: écrit et `model_scores.json` gelait — pour onze lignes sur 27 812.
#:
#: Le seuil n'est pas choisi au jugé. Dénombré le 13/08 sur les 72 751
#: balise-jours de `model_verif_daily` depuis le 30/07 : 2 719 (3,74 %)
#: ont une persistance dont l'erreur RMS est sous 1 km/h, et 1 855
#: (2,55 %) sous 0,1 km/h — du vent qui n'a pas bougé de la journée.
#: « Ce modèle bat la persistance » n'y a pas de contenu, et un chiffre
#: qui écrase toutes les échelles où il entre est pire qu'une absence.
#:
#: ⓘ Les scores ABSOLUS (`typical_err_kmh`, `worst_decile_kmh`,
#: `err_sd`, `pooled_err_kmh`) ne bougent pas d'un chiffre : ce plancher
#: ne touche QUE le rapport à une référence.
SKILL_MIN_REF_MSE = 1.0

#: Fenêtre du score glissant (§8.4).
ROLLING_DAYS = 15

RETENTION_DAILY_D = 30
RETENTION_EVENT_D = 90
RETENTION_SCORE_D = 7

#: Silence au-delà duquel un accumulateur de caractère ne pèse plus rien.
#:
#: ⚠️ CE N'EST PAS UNE RÉTENTION DE FENÊTRE, et la nuance décide de tout :
#: un accumulateur ne se périme pas par son ÂGE, il se périme par son
#: SILENCE. La demi-vie est de 30 jours, donc une case muette depuis
#: 180 jours pèse `2^(-180/30)` = 1,6 % d'une journée fraîche. La jeter
#: ne change aucun chiffre affiché.
#:
#: ⛔ ET ELLE NE REND RIEN AUJOURD'HUI — le dire plutôt que de le vendre.
#: Mesuré le 25/08 : `last_day < 2026-02-26` = **0 ligne**. La plus
#: vieille ligne de la table a 18 jours. Même en descendant le seuil à
#: 16 jours, on ne récupérerait que 36 581 lignes sur 739 916 (4,9 %).
#: Cette constante est écrite pour le régime permanent, pas pour
#: maintenant. Cf. `claude/lot-s14-croissance-model-character-25-08.md`.
RETENTION_CHARACTER_D = 180

# ══════════════════════════════════════════════════════════════════
#  LOT G — LES TROIS ARBITRAGES, TRANCHÉS LE 09/08/2026
# ══════════════════════════════════════════════════════════════════
#
# 1. PROFONDEUR D'ARCHIVE. L'archive R2 commence le 07/08/2026 : deux
#    jours au moment où ce code est écrit. Un bootstrap par blocs de
#    jours sur deux jours n'a aucun sens, et le partial pooling non
#    plus. Décision : ÉCRIRE LE CODE MAINTENANT et le laisser rendre
#    `None` avec une raison explicite (`window_too_short`) tant que la
#    fenêtre est trop courte. Le code est prêt le jour où les données
#    arrivent, et l'archive permet de tout REJOUER — c'est
#    précisément ce pour quoi elle ne se purge jamais.
#    Le contraire (attendre deux semaines) aurait fait écrire le même
#    code plus tard, sans banc, sur des données qu'on n'aurait pas pu
#    rejouer avant.
#
# 2. `hold_ms` — cf. `events.py`, en-tête de `HOLD_MS`. Fenêtre
#    ADAPTATIVE au pas réel de la série, plutôt qu'un seuil fixe.
#
# 3. PARTIAL POOLING ET QUORUM. Le §16.3 dit « en remplacement
#    progressif du quorum sec ». Décision : le pooling AMÉLIORE
#    l'estimation, le quorum reste le seuil d'AFFICHAGE, et le poids
#    emprunté est publié à côté de chaque chiffre. Un remplacement
#    franc ferait apparaître des chiffres partout, y compris là où
#    presque tout est emprunté au parent — c'est-à-dire ouvrirait la
#    vanne au moment précis où on affirme la refermer.

#: Fenêtre du chemin RÉGIME, en jours d'archive rejoués. Le chemin
#: régime ne lit plus les accumulateurs pour son erreur typique : trois
#: sommes (`sum_w`, `sum_wx`, `sum_wx2`) savent faire une moyenne et une
#: variance, jamais un décile. Elles restent la mémoire longue du
#: CARACTÈRE (§15.4) ; la DISTRIBUTION se rejoue depuis les paires
#: brutes.
REGIME_REPLAY_DAYS = 30

#: Où le rejeu range ses journées déjà recalculées, sous `--out`. Une
#: journée rejouée ne change plus jamais : l'archive est immuable et la
#: formule est versionnée par `REPLAY_FORMULA`. Sans ce cache, rejouer
#: 30 jours chaque nuit multiplierait la durée du run par 30.
REPLAY_SUBDIR = "replay"

#: ⚠️ À INCRÉMENTER À CHAQUE FOIS QUE `daily_rows` CHANGE DE RÉSULTAT.
#: Un cache qui survit à un changement de formule sert des chiffres
#: calculés par du code qui n'existe plus, sans que rien ne le signale —
#: le même piège que le `dist_old_*` servi par localhost le 08/08.
#: 2 — lot G4 : `daily_rows` porte désormais `mse_clim` à côté de
#:     `mse_persist`. Les caches de la formule 1 sont donc ignorés.
#: 3 — lot I (13/08) : le flux AGRUME entre dans les snapshots. La
#:     formule n'a pas bougé d'une virgule — c'est l'ENSEMBLE D'ENTRÉE
#:     qui a changé, et ça suffit. Un cache d'avant ne porte aucune
#:     ligne AGRUME ; réutilisé, il donnerait une fenêtre de régime où
#:     AGRUME existe pour les journées récentes et pas pour les
#:     anciennes, sans que rien ne le dise. ⚠️ Le prix est connu et
#:     borné : `--replay-budget` (3 par défaut) rattrape trois journées
#:     par nuit et `replay_window` COMPTE celles qu'il reporte. Pour
#:     rattraper d'un coup : `--replay-budget 30`.
#: 4 — lot S2 (22/08) : `daily_rows` porte la COLONNE CORRIGÉE du biais
#:     de site (`err_vec_med_corr`, `mse_model_corr`, `bias_n_days`) et
#:     la pente du jour (`bias_slope`) dont l'antécédent des journées
#:     suivantes est fait. Un cache de la formule 3 ne porte NI l'une NI
#:     l'autre : réutilisé, il donnerait une fenêtre où le corrigé
#:     existe pour les journées récentes et manque pour les anciennes —
#:     exactement le mélange que la formule 3 refusait déjà pour AGRUME.
#:     ⚠️ Prix connu : au premier run, les 30 caches sont invalides et
#:     l'antécédent repart à zéro. `--replay-budget 30` une fois (mesuré
#:     ~35 s par journée sur le VPS, soit ~18 min) plutôt que dix nuits
#:     à en rattraper trois.
#: 5 — lot L9 volets b ET c (28/08) : `daily_rows` porte DEUX choses de
#:     plus. (b) la clé privée `_murphy` — les six sommes suffisantes
#:     `[n, Σf, Σo, Σf², Σo², Σfo]` de la vitesse, dont `murphy.py`
#:     recompose r²/biais conditionnel/biais systématique une fois
#:     additionnées sur la fenêtre. (c) la colonne `mse_comb` (et son
#:     `mse_model_comb` apparié) — la référence combinée de Murphy 1992,
#:     `k·persistance + (1−k)·climatologie`.
#:     ⛔ UNE SEULE INCRÉMENTATION POUR DEUX VOLETS, ET C'EST UN
#:     ARBITRAGE. Les deux changent `daily_rows` et partent dans le MÊME
#:     déploiement : incrémenter deux fois coûterait soixante rejeux
#:     là où trente suffisent, pour une distinction (« formule 5 sans
#:     mse_comb ») qui n'a jamais existé sur aucune machine.
#:     ⚠️ Un cache de formule 4 ne porte NI l'un NI l'autre : réutilisé,
#:     il donnerait une fenêtre de Murphy où les journées récentes ont
#:     leurs moments et les anciennes pas — c'est-à-dire un r² calculé
#:     sur cinq jours pendant qu'on croit en lire trente. Même refus que
#:     pour les formules 3 et 4.
#:     ⚠️ Prix connu, identique : `--replay-budget 30` une fois
#:     (~18 min sur le VPS) plutôt que dix nuits à en rattraper trois.
#:     ⓘ Et le cache grossit : six nombres de plus par balise-jour. À
#:     MESURER sur le VPS après le premier rejeu complet, pas à estimer
#:     ici.
#:
#:   ⛔ RESTÉE À 5 APRÈS LE L9(c) DU 02/09, ET C'EST UN CONTRAT ROMPU
#:     ASSUMÉ. `daily_rows` a gagné `mse_comb_vec` sans que ce numéro
#:     bouge : le chemin RÉGIME (cache) ne porte la colonne que pour les
#:     journées rejouées après le 02/09, le chemin ROLLING (base) pour
#:     toutes les nuits écrites depuis — deux profondeurs sous une même
#:     colonne. Passer à 6 rejoue trente journées (`--replay-budget 30`,
#:     ~18 min) UNE nuit où le run tourne déjà à **2,7 Go de pic cgroup**
#:     (02/09, contre 2 820 Mo qui ont tué le 28/08) : on ne le fait pas
#:     avant que la mémoire ait fini de monter (fenêtre pleine vers le
#:     12/09). Décision de la vérification du 02/09, à reprendre alors.
#:
#:   ⛔ ET TOUJOURS À 5 APRÈS LE LOT L19 (04/09), MÊME CONTRAT ROMPU,
#:     MÊME RAISON. `daily_rows` a gagné `bw_mix` (une LIGNE de plus par
#:     balise × classe, fabriquée depuis les autres), les colonnes
#:     `*_fin`, `spread_kmh`, `mix_n_models` et la clé privée
#:     `_biais_fin`. Un cache d'avant ne porte rien de tout ça : la
#:     fenêtre RÉGIME ne voit `bw_mix` que sur les journées rejouées
#:     après le déploiement, et l'antécédent FIN se remplit à raison
#:     d'une journée par nuit (il parle à partir de `FIN_MIN_JOURS` = 3
#:     nuits). Le chemin ROLLING (base) est complet dès la première nuit.
#:     ⚠️ Passer à 6 rejouerait trente journées AVEC le mélange et le
#:     fin d'un coup (~18 min + la mémoire) : à faire dans la même nuit
#:     que le passage décidé le 02/09, pas avant.
#: 6 — 04/09/2026, décision de Yann : les DEUX contrats rompus (L9c du
#:     02/09 : `mse_comb_vec` ; L19/L20 du 04/09 : `bw_mix`, `*_fin`,
#:     `spread_kmh`, `_biais_fin`, la ligne sœur AGRUME +24 h) sont
#:     refermés d'un coup. ⛔ PAS PAR LE RUN NOCTURNE : le cache a été
#:     RÉCHAUFFÉ EN JOURNÉE, du plus ancien au plus récent (donc avec
#:     ses antécédents), par un rejeu à part sur le VPS — le run de la
#:     nuit trouve trente caches valides et n'en rejoue aucun. C'est ce
#:     qui évite de rejouer 30 journées à 2,1 Go de RSS (le 28/08 est
#:     mort à 2 820). ⓘ Le chemin régime porte désormais `bw_mix`, les
#:     colonnes fin et AGRUME +24 h sur toute la fenêtre, à la profondeur
#:     des antécédents près (5 j pour les poids, 3 j pour le biais).
REPLAY_FORMULA = 6


class Abort(Exception):
    """Arrêt net et volontaire."""


# ══════════════════════════════════════════════════════════════════
#  LA MÉMOIRE DU RUN — l'instrument, puis le garde-fou (28/08/2026)
# ══════════════════════════════════════════════════════════════════
#
# ⛔ POURQUOI CE BLOC EXISTE : LA NUIT DU 28/08 A ÉTÉ PERDUE SANS UN MOT.
# À 06:20:40 CEST, le noyau a tué ce processus (`oom-kill`, anon-rss
# 2 819 Mo) au milieu du chemin régime. Le journal du run s'arrête en
# pleine phrase : ni ligne d'erreur, ni bilan, ni cause. Il a fallu le
# journal du NOYAU pour apprendre ce qui s'était passé — et une sonde,
# le lendemain, pour apprendre où la mémoire dormait. Trois lots (L2,
# L3, L7) attendaient cette nuit-là leur premier objet publié ; aucun
# ne l'a eu, et rien dans le journal du job ne le disait.
#
# ⚠️ C'EST LE RAISONNEMENT DU CHIEN DE GARDE DES MINUTES, APPLIQUÉ À
# L'AUTRE RESSOURCE. `10-timeout-s3.conf` le dit déjà en toutes lettres
# pour le temps : « on veut que ce soit run.sh qui constate l'échec et
# alerte, jamais systemd qui tue tout sans que personne ne l'apprenne ».
# La mémoire n'avait pas son équivalent. Elle l'a ici.
#
# ⓘ ET CE QUE ÇA NE FAIT PAS : ça n'interrompt rien. Un run tué à 90 %
# est une nuit perdue de toute façon, et s'arrêter tout seul n'en
# sauverait aucune ; le jalon PARLE, c'est la seule chose qui manquait.
# La décision d'arrêter, si elle vient un jour, se prendra sur des
# courbes que ce jalon aura écrites — pas sur celle-ci.

#: Au-delà, chaque jalon crie sur `stderr`. ⛔ CE N'EST PAS UN PLAFOND
#: TECHNIQUE, c'est une MARGE MESURÉE : la machine a 3 825 Mo et aucun
#: swap avant le 28/08 ; `bw-agrume-piaf.service` y prend ~910 Mo
#: (min 909, max 928 sur les vingt passes du 28/08) TOUTES LES DIX
#: MINUTES, donc au moins une fois pendant un run qui dure un quart
#: d'heure. 3 825 − 910 − ~120 Mo de système et de pollers laisse
#: ~2 800 Mo à la notation. Franchir ce seuil, ce n'est pas « être
#: gros » : c'est jouer la nuit à pile ou face contre l'horloge de
#: piaf. Réglable par `BW_MODEL_VERIF_MAX_RSS_MO`, comme les minutes.
MAX_RSS_MO = float(os.environ.get("BW_MODEL_VERIF_MAX_RSS_MO", "2800"))


def _rss_mo(chemin: str = "/proc/self/status") -> float | None:
    """La mémoire résidente de CE processus, en Mo. `None` hors Linux.

    ⚠️ `VmRSS` ET PAS `ru_maxrss`, et la nuance décide de tout ici : on
    veut la mémoire MAINTENANT, pour voir un bloc mourir ENTRE deux
    jalons. `ru_maxrss` ne redescend jamais — il lirait « rien n'a été
    libéré » sur un run qui vient précisément de tout libérer. Le PIC,
    lui, systemd le journalise déjà tout seul (`Consumed … memory
    peak`) : c'est par là qu'on a lu la dérive du 10 au 28/08.

    ⓘ `chemin` n'existe que pour le banc : sans lui, la seule épreuve
    possible serait une allocation réelle, qui ne se joue pas sur un
    Mac — et une mutation qu'on ne peut pas jouer est une mutation qui
    ne prouve rien.
    """
    try:
        with open(chemin, encoding="ascii") as f:
            for ligne in f:
                if ligne.startswith("VmRSS:"):
                    return int(ligne.split()[1]) / 1024.0
    except OSError:
        return None
    return None


def jalon_memoire(etiquette: str, seuil_mo: float = MAX_RSS_MO,
                  rss=None) -> float | None:
    """Dit la mémoire résidente à une étape NOMMÉE du run.

    Rend les Mo lus (ou `None` là où `/proc` n'existe pas — le banc
    tourne aussi sur un Mac). Au-dessus du seuil, la ligne part sur
    `stderr` : c'est ce qui la fait remonter dans l'alerte, et pas
    seulement dans le journal que personne ne lit les nuits qui vont
    bien.
    """
    mo = (rss or _rss_mo)()
    if mo is None:
        return None
    trop = mo > seuil_mo
    texte = f"  {'⛔' if trop else 'ⓘ'} mémoire après {etiquette} : {mo:.0f} Mo"
    if trop:
        texte += (f" — AU-DESSUS DU SEUIL DE {seuil_mo:.0f} Mo. Le noyau "
                  f"tue le plus gros processus sans prévenir : c'est ce "
                  f"qui a emporté la nuit du 28/08.")
    print(texte, file=sys.stderr if trop else sys.stdout)
    return mo


# ══════════════════════════════════════════════════════════════════
#  SUPABASE (PostgREST, clé service_role — contourne RLS)
# ══════════════════════════════════════════════════════════════════

#: Octets lus du corps d'une erreur HTTP. Large, parce qu'on ne lit
#: plus la tête du corps mais ce qu'on y CHOISIT (cf. `_detail_erreur`).
ERREUR_OCTETS = 65536

#: Caractères de `details` (la LIGNE fautive) gardés dans le message.
#: Assez pour reconnaître la ligne, jamais assez pour noyer la cause.
ERREUR_DETAILS_CAR = 300


def _detail_erreur(brut: bytes, car_details: int = ERREUR_DETAILS_CAR) -> str:
    """Le corps d'une erreur PostgREST, ramené à ce qui SERT.

    ⛔⛔ POURQUOI CETTE FONCTION EXISTE, ET ELLE A COÛTÉ DEUX REJEUX
    COMPLETS LE 28/08. Le code lisait `e.read()[:400]` — les 400
    PREMIERS octets du corps. Or PostgREST sérialise ses erreurs dans
    cet ordre :

        {"code":…, "details":…, "hint":…, "message":…}

    et `details` porte LA LIGNE ENTIÈRE qui a été refusée. Sur
    `model_score_zone`, une ligne fait trente-huit colonnes : elle
    dépasse à elle seule les 400 octets. **Le `message` — c'est-à-dire
    le SEUL endroit où le nom de la contrainte apparaît — était donc
    systématiquement coupé.**

    ⚠️ CONSÉQUENCE, ET ELLE EST PLUS GRAVE QUE LE MESSAGE ILLISIBLE :
    le repli d'`_upsert_scores` cherche ce nom (`if "…_check" in
    str(exc)`). Il ne pouvait pas le trouver. **Le repli existait
    depuis le lot G, il était écrit, banc à l'appui, et il n'a JAMAIS
    pu se déclencher sur cette table-là.** Un garde-fou qu'on croit
    armé et qui ne peut pas partir est pire qu'un garde-fou absent :
    on compte dessus.

    ⓘ On lit donc TOUT le corps (`ERREUR_OCTETS`), on le relit comme du
    JSON, et on remonte `code` et `message` EN PREMIER — `details` vient
    à la fin et c'est LUI qu'on tronque. Si le corps n'est pas du JSON
    (une passerelle, un HTML d'erreur), on rend le texte brut : mieux
    vaut un message laid qu'un message absent.
    """
    texte = brut.decode("utf-8", "replace")
    try:
        objet = json.loads(texte)
    except ValueError:
        objet = None
    if not isinstance(objet, dict):
        return texte[:2000]
    bouts = []
    for cle in ("code", "message", "hint", "details"):
        valeur = objet.get(cle)
        if valeur in (None, ""):
            continue
        valeur = str(valeur)
        if cle == "details" and len(valeur) > car_details:
            valeur = (valeur[:car_details]
                      + f"… (+{len(valeur) - car_details} car.)")
        bouts.append(f'"{cle}":"{valeur}"')
    return "{" + ", ".join(bouts) + "}" if bouts else texte[:2000]


class Supabase:
    """Le strict nécessaire : lire une table, en écrire une par upsert.

    Même modèle d'accès que `mf_station_history` (step13) : la clé
    `service_role` contourne RLS, aucune policy d'écriture n'existe et
    n'a à exister.
    """

    def __init__(self, dry_run: bool = False):
        self.url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
        self.key = os.environ.get("SUPABASE_SERVICE_KEY") or ""
        self.dry_run = dry_run
        if not dry_run and not (self.url and self.key):
            raise Abort("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants")
        self.ecritures = 0

    def _req(self, path: str, method: str, data: bytes | None = None,
             extra: dict | None = None):
        return urllib.request.Request(
            f"{self.url}/rest/v1/{path}", data=data, method=method,
            headers={"apikey": self.key, "Authorization": f"Bearer {self.key}",
                     "Content-Type": "application/json", **(extra or {})})

    #: Nombre de lignes qu'un seul appel PostgREST peut rendre. Mesuré en
    #: direct le 08/08 : `Range: 0-4999` sur une table de 1 946 lignes en
    #: rend 1 000, pas 1 946. C'est `db-max-rows` côté serveur, pas une
    #: limite du client — demander plus n'y change rien.
    PAGE = 1000

    #: Le plafond RÉEL du serveur, re-mesuré le 25/08 sur la base de
    #: production : `Range: 0-9999` sur `model_character` (739 916
    #: lignes) en rend 1 000, pas 10 000.
    #:
    #: ⛔ NE PAS AUGMENTER `PAGE` POUR ALLER PLUS VITE. La boucle de
    #: `select` s'arrête sur `len(page) < PAGE` : avec `PAGE = 10_000`
    #: contre un serveur qui plafonne à 1 000, la PREMIÈRE page paraît
    #: incomplète et la lecture s'arrête là. C'est exactement la
    #: troncature silencieuse du 08/08 — rien ne plante, rien n'est
    #: rouge, et 739 000 accumulateurs repartent de zéro. D'où
    #: l'assertion ci-dessous, qui refuse de lire plutôt que de mentir.
    PLAFOND_SERVEUR = 1000

    #: Une lecture ratée ne coûte pas qu'une requête : elle coûte le run
    #: entier, et tout ce qu'il a déjà écrit en base. Deux reprises,
    #: espacées, uniquement sur les 5xx et les coupures réseau — jamais
    #: sur un 4xx, qui est une faute du client et se répéterait à
    #: l'identique.
    RELECTURES = 2
    RELECTURE_PAUSE_S = (2.0, 6.0)

    def _page(self, base: str, deb: int, fin: int) -> list[dict]:
        """Une page, avec reprise sur 5xx. Le seul endroit qui lit le réseau."""
        if self.PAGE > self.PLAFOND_SERVEUR:
            raise Abort(
                f"PAGE={self.PAGE} dépasse le plafond serveur mesuré "
                f"({self.PLAFOND_SERVEUR}) : la boucle de pagination "
                f"prendrait la première page plafonnée pour la fin de la "
                f"table et tronquerait en silence (défaut du 08/08).")
        derniere: Exception | None = None
        for essai in range(self.RELECTURES + 1):
            try:
                req = self._req(base, "GET", None,
                                {"Range-Unit": "items",
                                 "Range": f"{deb}-{fin}"})
                with urllib.request.urlopen(req, timeout=120) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code < 500:
                    raise
                # Le corps porte le VRAI motif — `57014` = délai de
                # requête dépassé. Sans le lire, le journal ne dit que
                # « HTTP Error 500 » et la nuit du 25/08 a été perdue à
                # le deviner.
                try:
                    motif = exc.read().decode("utf-8")[:200]
                except Exception:                      # noqa: BLE001
                    motif = ""
                derniere = exc
                print(f"     ⚠️ {base.split('?')[0]} [{deb}-{fin}] : "
                      f"HTTP {exc.code} {motif} — reprise "
                      f"{essai + 1}/{self.RELECTURES}", file=sys.stderr)
            except urllib.error.URLError as exc:
                derniere = exc
                print(f"     ⚠️ {base.split('?')[0]} [{deb}-{fin}] : "
                      f"{type(exc).__name__} — reprise "
                      f"{essai + 1}/{self.RELECTURES}", file=sys.stderr)
            if essai < self.RELECTURES:
                time.sleep(self.RELECTURE_PAUSE_S[
                    min(essai, len(self.RELECTURE_PAUSE_S) - 1)])
        raise derniere if derniere else Abort("lecture impossible")

    def select_par_cle(self, table: str, cle: str, order: str,
                       query: str = "") -> list[dict]:
        """Lit une table entière SANS `OFFSET`, en avançant sur une clé.

        ⛔ POURQUOI CETTE MÉTHODE EXISTE, mesuré le 25/08 sur la base de
        production. `select` pagine par `OFFSET` : pour rendre 1 000
        lignes à l'offset 600 000, PostgreSQL parcourt d'abord les
        600 000 précédentes. Le coût grandit avec la profondeur ET avec
        la table. Sur `model_character` (739 916 lignes) :

            offset       0 → 200 en 0,4 s
            offset 400 000 → 200 en 2,4 s
            offset 600 000 → 500 en 8,3 s   ⟵ `57014`, délai dépassé
            offset 700 000 → 500 en 8,6 s

        Supabase coupe à 8 s. **La lecture ne peut plus aller au bout**,
        et c'est ce qui a tué le run du 25/08 à 06:02 — pas un aléa de
        réseau, une échéance franchie. Filtrer ne sauve rien : la
        tranche `lead_h=6 & metric=errKmh` (70 798 lignes) expire aussi
        à son offset le plus profond, le filtre n'étant pas indexé.

        Ici on repart de la dernière valeur de `cle` lue
        (`cle=gt.<borne>`), ce qui attaque l'index de la clé primaire
        directement, sans rien parcourir avant. Mesuré aux mêmes
        profondeurs : **0,35 à 0,45 s par page, quelle que soit la
        profondeur**.

        ⚠️ `cle` DOIT ÊTRE LA PREMIÈRE COLONNE DE `order`, et `order`
        doit rester la clé primaire complète — sinon deux pages peuvent
        se recouvrir ou se sauter, exactement comme sans `ORDER BY`.

        ⚠️ LA QUEUE PARTIELLE EST RENDUE, PAS GARDÉE. Une page peut
        couper au milieu d'une valeur de `cle` : on jette toutes les
        lignes qui portent la dernière valeur vue et on redemande à
        partir de la précédente. Rien n'est perdu, rien n'est lu deux
        fois — et c'est la seule façon d'être exact sans comparer un
        n-uplet complet, que PostgREST ne sait pas exprimer.
        """
        if self.dry_run:
            return []
        sep = "&" if "?" in query else "?"
        racine = (f"{table}{query}{sep}select=*" if "select=" not in query
                  else f"{table}{query}")
        racine += f"{'&' if '?' in racine else '?'}order={order}"
        out: list[dict] = []
        borne: str | None = None
        while True:
            base = racine if borne is None else (
                f"{racine}&{cle}=gt.{urllib.parse.quote(str(borne), safe='')}")
            page = self._page(base, 0, self.PAGE - 1)
            if not page:
                return out
            if len(page) < self.PAGE:
                out.extend(page)
                return out
            fin_de_page = page[-1][cle]
            garde = [r for r in page if r[cle] != fin_de_page]
            if not garde:
                # ⚠️ UNE VALEUR DE CLÉ PLUS GROSSE QU'UNE PAGE, et ce
                # n'est pas un cas d'école : mesuré le 25/08, la zone
                # globale `*:*` porte plus de 1 000 accumulateurs à elle
                # seule (elle croise tous les modèles × échéances ×
                # régimes × tranches × métriques), comme `*:valley`
                # (2 301), `alpes-nord:*` (2 654) ou `alpes-nord:ridge`
                # (2 320). Jeter la page laisserait la boucle sur place ;
                # la garder ferait avancer `borne` en perdant la fin de
                # la valeur.
                #
                # On lit donc CETTE valeur à part, filtrée, avec des
                # offsets qui ne dépassent jamais sa propre taille — donc
                # peu profonds par construction. Mesuré : une page à
                # l'offset 4 000 DANS `zone_id=eq.*:*` répond en 0,67 s,
                # là où le même offset sur la table entière expirait.
                out.extend(self._valeur_entiere(racine, cle, fin_de_page))
                borne = fin_de_page
                continue
            out.extend(garde)
            borne = garde[-1][cle]

    def _valeur_entiere(self, racine: str, cle: str, valeur) -> list[dict]:
        """Toutes les lignes d'UNE valeur de clé, par offsets bornés.

        L'offset est ici sans danger : il ne parcourt que les lignes de
        cette valeur, pas la table. C'est la différence entre « la
        400 000ᵉ ligne de `model_character` » (8,3 s, puis `57014`) et
        « la 4 000ᵉ ligne de `zone_id=*:*` » (0,67 s).
        """
        base = (f"{racine}&{cle}=eq."
                f"{urllib.parse.quote(str(valeur), safe='')}")
        out: list[dict] = []
        offset = 0
        while True:
            page = self._page(base, offset, offset + self.PAGE - 1)
            out.extend(page)
            if len(page) < self.PAGE:
                return out
            offset += self.PAGE

    def select(self, table: str, query: str = "", order: str | None = None,
               cle_unique: bool = False) -> list[dict]:
        """Lit une table ENTIÈRE, page par page.

        ⛔ `cle_unique=True` (02/09/2026) : PAGINATION PAR CLÉ, PAS PAR
        DÉCALAGE. Le rejeu de la nuit du 02/09 (14:33 CEST) est mort en
        lisant `model_verif_event` à la page 782 (`Range: 781000-781999`)
        sur trois `57014 statement timeout` de suite. Un `OFFSET n` fait
        RELIRE n lignes au serveur avant d'en rendre mille : la 782ᵉ page
        coûte 782 fois la première, et le coût total d'une table de N
        lignes est en N². Quinze jours d'événements font ~780 000 lignes
        (38 700 par nuit, et le L7 les a fait grossir) — le matin, sous
        faible charge, ça passait ; l'après-midi, non. Avec `cle_unique`,
        chaque page demande `{order}=gt.{dernière valeur}` et `Range:
        0-999` : le serveur va droit à la ligne suivante par l'index de
        la clé, et la 782ᵉ page coûte la première.
        ⚠️ N'EST JUSTE QUE SI `order` EST UNE COLONNE UNIQUE (clé
        primaire) : sur une colonne à doublons, `gt.` sauterait les
        lignes qui partagent la valeur de la borne. C'est pour ça que
        c'est l'appelant qui l'affirme, et que le défaut reste le
        décalage.

        ⚠️ DÉFAUT TROUVÉ LE 08/08 EN VÉRIFIANT LES CHIFFRES DU LOT F, ET
        IL NE DATAIT PAS DU LOT F. La version précédente faisait UN appel
        et rendait ce qui venait. PostgREST plafonne à 1 000 lignes et le
        dit dans un en-tête que personne ne lisait : la fonction rendait
        donc une TRONCATURE SILENCIEUSE, jamais une erreur.
        Conséquences mesurées sur la base réelle :
          · `model_verif_daily` sur 15 jours = 5 407 lignes → 1 000 lues,
            soit un score glissant calculé sur 18 % de sa fenêtre ;
          · `model_character` = 81 960 accumulateurs → 1 000 lus, donc
            80 960 accumulateurs repartaient de ZÉRO chaque nuit. La
            mémoire longue du §15.4, dont c'est toute la raison d'être,
            n'a jamais mémorisé quoi que ce soit.
        Rien ne plantait, rien n'était rouge, et les chiffres avaient
        l'air normaux. C'est le motif exact contre lequel ce chantier se
        bat : une table raisonnée n'est pas une table vérifiée.

        ⚠️ `order` N'EST PAS DÉCORATIF. Sans `ORDER BY`, PostgreSQL n'a
        aucune obligation de rendre deux pages dans un ordre cohérent :
        une ligne peut apparaître deux fois et une autre jamais. On
        ordonne donc sur la clé primaire de la table, et l'appelant la
        passe explicitement — la deviner ici serait la même faute de
        reniflage que celle corrigée dans `zone_kind_for`.
        """
        if self.dry_run:
            return []
        sep = "&" if "?" in query else "?"
        base = (f"{table}{query}{sep}select=*" if "select=" not in query
                else f"{table}{query}")
        if order:
            base += f"{'&' if '?' in base else '?'}order={order}"
        if cle_unique:
            if not order or "," in order or "." in order:
                raise Abort(f"select({table}) : cle_unique exige un `order` "
                            f"sur UNE colonne, reçu {order!r}")
            out: list[dict] = []
            borne = None
            while True:
                b = base
                if borne is not None:
                    b += (f"&{order}=gt."
                          f"{urllib.parse.quote(str(borne), safe='')}")
                page = self._page(b, 0, self.PAGE - 1)
                out.extend(page)
                if len(page) < self.PAGE:
                    return out
                borne = page[-1][order]
        out: list[dict] = []
        offset = 0
        while True:
            page = self._page(base, offset, offset + self.PAGE - 1)
            out.extend(page)
            # Une page incomplète est la fin : c'est le seul signal fiable
            # sans demander un `count=exact`, qui coûte un balayage complet
            # de la table à chaque appel.
            if len(page) < self.PAGE:
                return out
            offset += self.PAGE

    _schema: dict | None = None

    def columns(self, table: str) -> set[str] | None:
        """Les colonnes RÉELLES d'une table, lues une fois par run.

        ⚠️ Ce n'est pas de la curiosité : le lot G ajoute des colonnes à
        `model_score_zone` (`pooled_err_kmh`, `borrowed_weight`, …) et le
        SQL ne s'exécute JAMAIS depuis ici — c'est Yann qui le lance,
        quand il le lance. Entre le déploiement du code et l'exécution du
        SQL, un run qui enverrait les nouvelles colonnes recevrait un
        `PGRST204 — column … does not exist` et la nuit serait perdue.

        On lit donc le schéma que PostgREST publie à sa racine et on
        n'envoie que ce que la table sait recevoir. Le jour où le SQL est
        passé, les colonnes apparaissent d'elles-mêmes : aucun drapeau à
        basculer, donc aucun drapeau à oublier.

        Rend `None` si le schéma n'est pas lisible — l'appelant se
        rabat alors sur le jeu de colonnes historique.
        """
        if self.dry_run:
            return None
        if Supabase._schema is None:
            try:
                req = self._req("", "GET", None, {"Accept": "application/openapi+json"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    Supabase._schema = json.loads(r.read().decode("utf-8"))
            except Exception as exc:                      # noqa: BLE001
                print(f"  ⚠️ schéma PostgREST illisible ({exc}) : on s'en tient "
                      f"aux colonnes historiques.", file=sys.stderr)
                Supabase._schema = {}
        defs = (Supabase._schema or {}).get("definitions", {})
        d = defs.get(table)
        if not d:
            return None
        return set((d.get("properties") or {}).keys())

    def upsert(self, table: str, rows: list[dict], on_conflict: str,
               chunk: int = 500) -> int:
        """Upsert par paquets.

        ⚠️ `resolution=merge-duplicates` et PAS un delete-puis-insert :
        une réécriture en deux temps laisse la table vide entre les
        deux, et l'atelier admin lirait un trou. Sur une table réécrite
        chaque nuit, ce trou dure le temps du run.
        """
        if not rows:
            return 0
        # ⚠️ GARDE-FOU AJOUTÉ LE 08/08, APRÈS AVOIR PAYÉ LE MESSAGE.
        # PostgREST refuse un envoi groupé dont les objets n'ont pas tous
        # le même jeu de clés, et il le dit ainsi :
        #
        #     HTTP 400 — {"code":"PGRST102", … "All object keys must match"}
        #
        # Ni la clé fautive, ni la ligne, ni la table. Le run nocturne
        # tombe alors sur une pile d'appels `urllib` qui parle de tout
        # sauf du problème. On vérifie donc AVANT d'envoyer, et on nomme
        # la clé — le coût est une union d'ensembles sur quelques
        # milliers de lignes, invisible devant l'aller-retour réseau.
        formes = {frozenset(r.keys()) for r in rows}
        if len(formes) > 1:
            communes = frozenset.intersection(*formes)
            variables = sorted(set().union(*formes) - communes)
            raise Abort(
                f"upsert {table} : {len(formes)} jeux de clés différents dans le "
                f"même envoi — PostgREST le refusera (PGRST102). Clés présentes "
                f"dans certaines lignes seulement : {variables}. Les ajouter à "
                f"`None` partout plutôt que de les omettre.")
        if self.dry_run:
            print(f"  (dry-run) {len(rows)} lignes vers {table}")
            return len(rows)
        n = 0
        for i in range(0, len(rows), chunk):
            body = json.dumps(rows[i:i + chunk]).encode("utf-8")
            req = self._req(f"{table}?on_conflict={on_conflict}", "POST", body,
                            {"Prefer": "resolution=merge-duplicates,return=minimal"})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    r.read()
            except urllib.error.HTTPError as e:
                detail = _detail_erreur(e.read(ERREUR_OCTETS))
                raise Abort(f"upsert {table} : HTTP {e.code} — {detail}") from e
            n += len(rows[i:i + chunk])
        self.ecritures += n
        return n

    #: Lignes par appel de `bw_character_avance`.
    #:
    #: ⛔ MESURÉ SUR LA PRODUCTION LE 25/08, PAS CHOISI. Le délai de
    #: requête de Supabase (8 s) s'applique aussi aux RPC, et il tue le
    #: run exactement comme il l'a tué le 25/08 au matin. Mesuré contre
    #: la table de 739 916 lignes, insertion puis mise à jour :
    #:
    #:        500 lignes → 0,20 / 0,21 s        5 000 → 2,57 / 1,54 s
    #:      1 000 lignes → 0,37 / 0,44 s       10 000 → 3,29 / 3,87 s
    #:      2 000 lignes → 0,78 / 0,97 s
    #:     20 000 lignes → ⛔ `57014` à 10,5 s … PUIS UNE RÉUSSITE À 10,7 s
    #:
    #: ⛔ C'EST CE DERNIER POINT QUI FIXE LA VALEUR, pas la vitesse. Une
    #: taille qui échoue UNE FOIS SUR DEUX est bien pire qu'une taille
    #: qui échoue toujours : elle passe en banc et elle tombe une nuit
    #: d'octobre. À 5 000 la marge sous les 8 s est de ×3, et la table
    #: va grandir. 10 000 irait à peine plus vite en divisant la marge
    #: par 1,5.
    #:
    #: ⛔ NE PAS AUGMENTER POUR ALLER PLUS VITE — même défaut que `PAGE`
    #: contre `PLAFOND_SERVEUR`, et même conséquence : une écriture
    #: coupée au milieu, un soir où personne ne regarde.
    RPC_LOT = 5000

    def rpc(self, fonction: str, corps: dict):
        """Appelle une fonction SQL par PostgREST (`/rpc/…`).

        ⚠️ REPRISE SUR 5xx, ALORS QUE `upsert` NE L'A PAS — et ce n'est
        pas une incohérence, c'est une propriété du chemin. Un appel de
        RPC est UNE seule instruction : ou elle s'applique en entier, ou
        elle ne s'applique pas du tout. Et `bw_character_avance` porte
        son propre garde d'idempotence (`p_day > mc.last_day`), donc
        rejouer un lot déjà passé n'a aucun effet. **Atomicité et
        idempotence : ce sont ces deux propriétés-là qui rendent la
        reprise sûre**, pas l'envie de robustesse. Sans elles, reprendre
        doublerait une journée.

        ⛔ Un 4xx n'est JAMAIS repris : c'est une faute du client
        (doublon de clé dans le corps, corps mal formé) et elle se
        répéterait à l'identique.

        ⓘ Le corps de l'erreur est journalisé. Sans lui, « HTTP Error
        500 » ne dit rien — et la matinée du 25/08 est passée à deviner
        que c'était un `57014`.
        """
        if self.dry_run:
            return None
        derniere: Exception | None = None
        for essai in range(self.RELECTURES + 1):
            try:
                req = self._req(f"rpc/{fonction}", "POST",
                                json.dumps(corps).encode("utf-8"))
                with urllib.request.urlopen(req, timeout=120) as r:
                    brut = r.read().decode("utf-8")
                    return json.loads(brut) if brut.strip() else None
            except urllib.error.HTTPError as exc:
                try:
                    motif = exc.read().decode("utf-8", "replace")[:400]
                except Exception:                      # noqa: BLE001
                    motif = ""
                if exc.code < 500:
                    raise Abort(f"rpc {fonction} : HTTP {exc.code} — {motif}")
                derniere = exc
                print(f"     ⚠️ rpc/{fonction} : HTTP {exc.code} {motif} — "
                      f"reprise {essai + 1}/{self.RELECTURES}", file=sys.stderr)
            except urllib.error.URLError as exc:
                derniere = exc
                print(f"     ⚠️ rpc/{fonction} : {type(exc).__name__} — "
                      f"reprise {essai + 1}/{self.RELECTURES}", file=sys.stderr)
            if essai < self.RELECTURES:
                time.sleep(self.RELECTURE_PAUSE_S[
                    min(essai, len(self.RELECTURE_PAUSE_S) - 1)])
        raise Abort(f"rpc {fonction} : échec après {self.RELECTURES} "
                    f"reprises — {derniere}")

    def avance_caractere(self, rows: list[dict], jour: str,
                         lot: int | None = None) -> int:
        """Fait avancer les accumulateurs par `bw_character_avance`.

        ⭐ REND LE NOMBRE DE LIGNES RÉELLEMENT APPLIQUÉES, PAS ENVOYÉES.
        C'est la fonction SQL qui les compte (`get diagnostics`), et
        c'est une différence de nature avec `upsert`, qui rend
        `len(rows)`. L'écart entre envoyé et appliqué n'est pas du
        bruit : il vaut les valeurs non finies écartées par la RPC, plus
        les clés dont la journée était déjà intégrée. ⛔ C'est
        précisément parce que `upsert` comptait ce qu'il ENVOYAIT qu'il
        a été impossible, le 25/08, de réconcilier les 3 615 845
        « avancées » du journal avec les 3 270 977 `days` de la table.
        """
        if not rows:
            return 0
        lot = lot or self.RPC_LOT
        if lot > self.RPC_LOT:
            raise Abort(
                f"avance_caractere : lot de {lot} lignes, au-dessus de "
                f"RPC_LOT={self.RPC_LOT} — mesuré le 25/08 contre le délai "
                f"de 8 s de Supabase. Au-dessus, la fonction rend `57014` EN "
                f"PLEINE ÉCRITURE, et à 20 000 elle ne le fait qu'une fois "
                f"sur deux.")
        if self.dry_run:
            print(f"  (dry-run) {len(rows)} lignes vers model_character (RPC)")
            return len(rows)
        n = 0
        for i in range(0, len(rows), lot):
            n += int(self.rpc("bw_character_avance",
                              {"p_rows": rows[i:i + lot], "p_day": jour}))
        self.ecritures += n
        return n

    def insert(self, table: str, rows: list[dict], chunk: int = 500) -> int:
        """Insertion simple, pour les tables SANS clé d'unicité.

        ⚠️ `model_verif_event` n'a PAS de contrainte d'unicité, et ce
        n'est pas un oubli : elle porte UNE LIGNE PAR ÉVÉNEMENT
        INDIVIDUEL (chaque succès, chaque raté, chaque fausse alarme),
        pas un agrégat par nuit. Deux bascules ratées le même jour par le
        même modèle sur la même zone sont deux lignes légitimes, qu'un
        `on_conflict` fusionnerait en une.

        L'idempotence se joue donc ailleurs : l'appelant PURGE la journée
        avant de réinsérer (`?day=eq.…`). Contrairement au cas de
        `upsert`, le trou de lecture ne coûte rien ici — la purge ne
        touche qu'un jour sur une fenêtre de 90, et personne ne lit cette
        table en direct : le JSON publié est reconstruit après.
        """
        if not rows:
            return 0
        formes = {frozenset(r.keys()) for r in rows}
        if len(formes) > 1:
            communes = frozenset.intersection(*formes)
            variables = sorted(set().union(*formes) - communes)
            raise Abort(
                f"insert {table} : {len(formes)} jeux de clés différents dans le "
                f"même envoi — PostgREST le refusera (PGRST102). Clés présentes "
                f"dans certaines lignes seulement : {variables}.")
        if self.dry_run:
            print(f"  (dry-run) {len(rows)} lignes vers {table}")
            return len(rows)
        n = 0
        for i in range(0, len(rows), chunk):
            body = json.dumps(rows[i:i + chunk]).encode("utf-8")
            req = self._req(table, "POST", body,
                            {"Prefer": "return=minimal"})
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    r.read()
            except urllib.error.HTTPError as e:
                detail = _detail_erreur(e.read(ERREUR_OCTETS))
                raise Abort(f"insert {table} : HTTP {e.code} — {detail}") from e
            n += len(rows[i:i + chunk])
        self.ecritures += n
        return n

    def compte(self, table: str, query: str = "") -> int | None:
        """Combien de lignes ce filtre concerne, sans en rapatrier une seule.

        `HEAD` + `Prefer: count=exact` : PostgREST met le total dans
        `content-range` (`*/0` quand rien ne correspond) et ne rend
        aucun corps. Mesuré le 01/09/2026 sur `model_character`
        (1 223 107 lignes) : 1,3 s sans filtre, 3,0 s avec
        `last_day=lt.…`. ⚠️ Le filtre RALENTIT la requête au lieu de
        l'accélérer — signature d'une colonne sans index utilisable,
        déjà mesurée le 27/08 sur 942 832 lignes (5,3 s contre 1,4 s).

        ⚠️ REND `None` QUAND LE SERVEUR REFUSE, ET EN DRY-RUN : c'est
        « je ne sais pas », pas « zéro ». L'appelant doit distinguer
        les deux — les confondre ferait sauter une purge en silence, et
        le silence est précisément ce qu'on répare ici.
        """
        if self.dry_run:
            return None
        req = self._req(f"{table}{query}", "HEAD", None,
                        {"Prefer": "count=exact", "Range-Unit": "items",
                         "Range": "0-0"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                entete = r.headers.get("content-range") or ""
        except urllib.error.HTTPError as e:
            print(f"  ⚠️ compte {table} : HTTP {e.code} — "
                  f"{_detail_erreur(e.read(ERREUR_OCTETS))}", file=sys.stderr)
            return None
        except urllib.error.URLError as e:
            print(f"  ⚠️ compte {table} : {type(e).__name__} — "
                  f"{getattr(e, 'reason', e)}", file=sys.stderr)
            return None
        total = entete.rsplit("/", 1)[-1]
        return int(total) if total.isdigit() else None

    def delete(self, table: str, query: str) -> None:
        """Supprime — et quand ça rate, DIT POURQUOI.

        ⛔ ELLE N'IMPRIMAIT QUE « HTTP {code} », ET C'EST LA DETTE Nº 1
        DU LOT L13. La purge de `model_character` a rendu 500 les nuits
        des 26, 27 et 29/08 ; le journal du VPS n'en a gardé que trois
        lignes « ⚠️ purge model_character : HTTP 500 », SANS le corps,
        donc sans le code PostgREST. Résultat : `57014` (délai de
        requête dépassé) n'a jamais pu être ni confirmé ni écarté, et
        l'audit a dû l'écrire en « hypothèse forte » pendant cinq
        jours. `_page` lit ce corps depuis le 25/08, `insert` depuis le
        28/08 (`_detail_erreur`) : `delete` était le dernier muet.

        ⚠️ Elle JOURNALISE ET CONTINUE sur un HTTP d'erreur — c'est
        voulu, et les appelants en dépendent (la purge est la toute
        dernière étape du run : la faire échouer perdrait un run
        entièrement écrit pour du ménage). Une coupure réseau, elle,
        continue de remonter : ce n'est pas un refus du serveur, et le
        run a déjà tout écrit avant d'arriver ici.
        """
        if self.dry_run:
            print(f"  (dry-run) delete {table}{query}")
            return
        req = self._req(f"{table}{query}", "DELETE", None, {"Prefer": "return=minimal"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                r.read()
        except urllib.error.HTTPError as e:
            print(f"  ⚠️ purge {table} : HTTP {e.code} — "
                  f"{_detail_erreur(e.read(ERREUR_OCTETS))}", file=sys.stderr)


# ══════════════════════════════════════════════════════════════════
#  ARCHIVE
# ══════════════════════════════════════════════════════════════════

def _storage():
    tools = pathlib.Path(__file__).resolve().parent.parent / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    try:
        from storage import Storage             # type: ignore
        return Storage("model-verif", bucket_env="MODEL_VERIF_BUCKET",
                       defaut="model-verif", plafond=10)
    except Exception:                           # noqa: BLE001
        return None


def read_ndjson(root: pathlib.Path, key: str, storage=None):
    """Lit un objet d'archive, localement d'abord, sur R2 ensuite.

    ⚠️ Un objet ABSENT rend une liste vide, et l'appelant doit le
    traiter comme « pas de donnée ce jour-là », pas comme une erreur :
    au démarrage, D-1 et D-2 n'existent pas encore, et c'est normal.
    Confondre les deux ferait échouer les quinze premiers runs.
    """
    path = root / key
    raw = None
    if path.exists():
        raw = path.read_bytes()
    elif storage is not None:
        raw = storage.get(key)
    if not raw:
        return []
    try:
        text = gzip.decompress(raw).decode("utf-8")
    except OSError:
        text = raw.decode("utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def read_json(root: pathlib.Path, key: str, storage=None):
    """Lit UN objet JSON d'archive, localement d'abord, sur R2 ensuite.

    Même contrat que `read_ndjson` : un objet absent rend `None`, et
    l'appelant doit en faire un fait, pas une erreur.

    ⓘ LE LOCAL D'ABORD, ET ÇA COMPTE POUR LE MANIFESTE. `score.py`
    tourne sur la même machine que `collect.py` : si l'envoi R2 du
    manifeste a échoué, le fichier est quand même là, et la notation de
    la nuit le trouve. R2 n'est le recours que pour un rejeu fait
    ailleurs.
    """
    path = root / key
    raw = None
    if path.exists():
        raw = path.read_bytes()
    elif storage is not None:
        raw = storage.get(key)
    if not raw:
        return None
    try:
        return json.loads(gzip.decompress(raw).decode("utf-8"))
    except OSError:
        pass
    except ValueError:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except ValueError:
        return None


def fcst_key(day: datetime, partie: int = 1) -> str:
    """La clé d'UNE partie du flux `fcst/` — la 1 est la clé historique.

    ⛔ AUCUNE DATE DE BASCULE, ET C'EST LA PROPRIÉTÉ QUI COMPTE.
    `fcst_key(day)` rend exactement ce qu'elle rendait avant le lot S0.6,
    donc les 15 nuits déjà écrites (au 22/08/2026) restent lisibles sans
    condition. Une journée d'avant la partition n'a pas de manifeste,
    n'a qu'une clé, et son union est complète.

    ⓘ Le miroir de `collect.fcst_cle`. Les deux fichiers ne s'importent
    pas l'un l'autre (`score.py` ne doit dépendre ni de numpy ni du
    paquet `agrume/`), donc la forme est écrite deux fois — et le banc
    `test_score.py::test_les_deux_cles_fcst_sont_la_meme_chaine` la
    compare caractère pour caractère plutôt que de faire confiance.
    """
    if partie < 1:
        raise ValueError(f"partie {partie} : elles se comptent à partir de 1")
    suffixe = "" if partie == 1 else f"_p{partie}"
    return f"fcst/{day:%Y/%m}/fcst_{day:%Y-%m-%d}{suffixe}.ndjson.gz"


def fcst_manifeste_key(day: datetime) -> str:
    """Le manifeste de partition du flux `fcst/` — objet LATÉRAL.

    ⚠️ `tools/storage.py` N'A PAS DE `list`, et c'est pour ça que cette
    clé est calculable : on la lit par `get_json`, jamais par listing.
    C'est aussi ce qui condamnait la variante « le nom de la clé porte
    le total » (`_p2sur2`) — il aurait fallu sonder n × n clés pour
    trouver celle qui parle.
    """
    return f"fcst/{day:%Y/%m}/fcst_{day:%Y-%m-%d}.manifeste.json"


def obs_key(day: datetime) -> str:
    return f"obs/{day:%Y/%m}/obs_{day:%Y-%m-%d}.ndjson.gz"


def obswindsmobi_key(day: datetime) -> str:
    """Le flux windsmobi (S0.2, 21/08) — clé à part, jamais dans `obs/`.

    Décision 1 du cadrage : `obs/` reste Pioupiou seul, lu depuis treize
    nuits par `score.py` (ce fichier). windsmobi a sa cadence, ses
    variables (pas de pression, jamais) et sa géographie propres — les
    mélanger dans un fichier déjà relu, c'était risquer de casser une
    notation qui marche pour une donnée que personne ne note encore.
    """
    return f"obswindsmobi/{day:%Y/%m}/obswindsmobi_{day:%Y-%m-%d}.ndjson.gz"


def obsinfoclimat_key(day: datetime) -> str:
    """Le flux infoclimat (S0.2, 21/08, session 2) — clé à part, comme
    windsmobi. Porte aussi `pres_hpa`/`pres_kind`/`licence_code` que le
    S1 lira plus tard ; `score.py` ne les regarde pas encore (cf.
    `to_obs_samples`, qui ne lit que `t`/`speed`/`dir`).
    """
    return f"obsinfoclimat/{day:%Y/%m}/obsinfoclimat_{day:%Y-%m-%d}.ndjson.gz"


def obsmf_key(day: datetime) -> str:
    """Le flux mf (S0.2, 21/08, session 3) — clé à part, comme windsmobi
    et infoclimat. Porte aussi `pres_hpa`/`pres_kind` que le S1 lira
    plus tard ; `score.py` ne les regarde pas encore (cf.
    `to_obs_samples`, qui ne lit que `t`/`speed`/`dir`).
    """
    return f"obsmf/{day:%Y/%m}/obsmf_{day:%Y-%m-%d}.ndjson.gz"


def obsaemet_key(day: datetime) -> str:
    """Le flux aemet (S0.2, 21/08, session 4 — le dernier du sous-lot) —
    clé à part, comme windsmobi/infoclimat/mf. Porte aussi
    `pres_hpa`/`pres_kind` que le S1 lira plus tard ; `score.py` ne les
    regarde pas encore (cf. `to_obs_samples`, qui ne lit que
    `t`/`speed`/`dir`).
    """
    return f"obsaemet/{day:%Y/%m}/obsaemet_{day:%Y-%m-%d}.ndjson.gz"


def obsmetar_key(day: datetime) -> str:
    """L'archive METAR (278 aérodromes Iowa State, depuis le 08/08).

    ⭐ **ELLE EST ENTRÉE DANS `OBS_KEY_FUNCS` LE 23/08/2026 (lot S0.11),
    ET LA RAISON QUI L'EN TENAIT ÉCARTÉE EST TOMBÉE.** Le pavé d'avant
    disait : « le vent d'un aérodrome n'a aucun point de prévision à sa
    propre coordonnée : l'y ajouter produirait zéro ligne aujourd'hui,
    et la première personne à voir ce zéro serait tentée de le réparer
    avec `geopair` ». C'était vrai jusqu'au 22/08. Depuis,
    `arome_fcst.py` écrit **278 lignes METAR par nuit, gratuitement**,
    À LA COORDONNÉE DE CHAQUE AÉRODROME (215/215 dans l'emprise,
    mesuré) : la prévision existe, le zéro n'existe plus, et la
    tentation de `geopair` non plus.

    ⛔ **ET CETTE LIGNE-CI NE COÛTE PAS UN PONDÉRÉ.** Elle n'ajoute AUCUN
    appel Open-Meteo : elle ouvre à la NOTATION une archive déjà écrite
    et déjà payée. C'est l'arbitrage n°8 du S0.3, tranché par Yann le
    23/08 : METAR entre au tau, il n'entre PAS dans le groupe réduit
    (+278 points y porterait la passe à 107,4 % de la fenêtre horaire,
    c'est-à-dire à une passe de plus, et il n'y a pas de créneau pour
    une troisième).

    ⚠️ Ce qu'elle apporte, et ce qu'elle n'apporte pas : une QUATRIÈME
    population pour le tau (aemet/infoclimat/mf/windsmobi + metar), pas
    de paires supplémentaires — sur METAR, `k` reste 1 tant que le
    groupe réduit n'y va pas.
    ⓘ Mesuré le 23/08 sur `obsmetar_2026-08-22.ndjson.gz` : 214 lignes,
    dont **212 portent au moins un relevé de vent**, au format
    `t`/`speed`/`dir` que `to_obs_samples` lit — le même que les cinq
    autres flux, vérifié champ par champ avant d'ajouter la ligne.
    """
    return f"obsmetar/{day:%Y/%m}/obsmetar_{day:%Y-%m-%d}.ndjson.gz"


#: Toutes les clés d'observations de VENT à fusionner pour noter une
#: journée. `obs_key` (Pioupiou) est la seule d'origine ; chaque session
#: du S0.2 y ajoute la sienne au fil de l'eau — windsmobi, infoclimat,
#: mf et aemet faits : S0.2 est clos. ⭐ `obsmetar_key` s'y est ajoutée
#: le 23/08/2026 (lot S0.11) : cf. son pavé — la raison qui l'écartait
#: est tombée le jour où `arome_fcst.py` s'est mis à écrire une
#: prévision à la coordonnée de chaque aérodrome, gratuitement.
#: ⚠️ `score.py` NE CONNAÎT AUCUN RÉSEAU PAR SON NOM au-delà de cette
#: liste : `daily_rows`, `climatology_by_station` et le reste de la
#: notation lisent des lignes génériques (`source`, `station_id`, `t`,
#: `speed`…) sans jamais tester `row["source"] == "windsmobi"`. Ajouter
#: un réseau, c'est ajouter sa fonction de clé ici — rien d'autre à
#: toucher dans ce fichier pour qu'il entre dans le score.
OBS_KEY_FUNCS = [obs_key, obswindsmobi_key, obsinfoclimat_key, obsmf_key,
                 obsaemet_key, obsmetar_key]


def all_obs_rows(root: pathlib.Path, day: datetime, storage=None) -> list[dict]:
    """Les observations de vent de TOUTES les sources, pour une journée.

    Même principe que `snapshot_rows` pour les prévisions (fcst + fcst
    AGRUME) : une fonction qui fusionne, jamais un `if` par réseau semé
    dans le reste du fichier. Un objet absent rend `[]` (`read_ndjson`),
    donc une source qui n'existe pas encore pour cette journée ne casse
    rien — c'est le cas normal des quinze premières nuits de chaque
    nouveau réseau.
    """
    rows: list[dict] = []
    for key_fn in OBS_KEY_FUNCS:
        rows += read_ndjson(root, key_fn(day), storage)
    return rows


def fcst_agrume_key(day: datetime) -> str:
    """Le flux AGRUME — un préfixe à part, et c'est délibéré (lot I).

    ⚠️ POURQUOI PAS DANS `fcst/`. Les deux flux n'ont ni le même
    producteur, ni la même heure, ni la même façon d'échouer :
    `collect.py` interroge Open-Meteo sous quota et son archive est
    IRREMPLAÇABLE (aucun modèle Météo-France n'a d'historique de runs
    passés — mesuré le 08/08 : 0/384 sur `_previous_day1`) ;
    `agrume_fcst.py` relit un produit A qui, lui, est encore là. Les
    mélanger dans une clé réécrite par deux jobs, c'est se donner un
    moyen de perdre l'irremplaçable en réécrivant le rejouable.

    ⓘ Ce préfixe est le seul endroit du dépôt où il est écrit. C'est
    `agrume_fcst.py` qui l'importe d'ici, pas l'inverse — `score.py` ne
    doit dépendre ni de numpy ni du paquet `agrume/`.
    """
    return f"fcstagrume/{day:%Y/%m}/fcstagrume_{day:%Y-%m-%d}.ndjson.gz"


def fcst_agrume_quart_key(day: datetime) -> str:
    """Le flux de la CLASSE AU QUART D'HEURE (lot L11, 31/08/2026).

    ⓘ Quatrième préfixe, quatrième fois le même raisonnement que le lot
    I : `fcstagrume_{J}` porte la classe +6 h, `fcstagrumecourt_{J}` la
    classe courte, celui-ci la classe au quart d'heure. Trois jobs, trois
    clés — un job qui échoue au milieu de son écriture n'emporte que sa
    propre archive, jamais celle d'un autre.
    """
    return (f"fcstagrumequart/{day:%Y/%m}/"
            f"fcstagrumequart_{day:%Y-%m-%d}.ndjson.gz")


def fcst_agrume_court_key(day: datetime) -> str:
    """Le flux de la CLASSE COURTE (lot L10, 30/08/2026) — encore un
    préfixe à part, et pour la troisième fois la même raison.

    ⚠️ POURQUOI PAS DANS `fcstagrume/`. Ce serait la tentation : même
    producteur apparent, même journée, même format. Mais ce sont DEUX
    JOBS, et le second réécrirait la clé du premier. `fcstagrume_{J}`
    porte l'archive de la classe +6 h ; si le job de la classe courte
    échouait au milieu de son écriture sur la MÊME clé, il emporterait
    une archive déjà bonne. C'est le raisonnement du lot I mot pour mot
    (« se donner un moyen de perdre l'irremplaçable en réécrivant le
    rejouable »), appliqué une fois de plus.

    ⓘ Le flux porte le jour NOTÉ, comme `fcstagrume` : la classe courte
    reconstitue après coup ce qui était disponible aux deux instants T
    de la journée J, et l'écrit sous J.
    """
    return ("fcstagrumecourt/%s/fcstagrumecourt_%s.ndjson.gz"
            % (day.strftime("%Y/%m"), day.strftime("%Y-%m-%d")))


def fcst_arome_key(day: datetime) -> str:
    """Le flux AROME lu sur R2 (lot S0.5, 22/08) — un préfixe à part,
    exactement pour les mêmes raisons que `fcstagrume`.

    ⚠️ POURQUOI PAS DANS `fcst/`. Les deux flux n'ont ni le même
    producteur, ni la même heure, ni la même façon d'échouer :
    `collect.py` interroge Open-Meteo sous quota à 03:19 et son archive
    est IRREMPLAÇABLE ; `arome_fcst.py` relit à 06:00 des tuiles que
    l'Action `arome-wind` réécrit toutes les 3 h. Les mélanger dans une
    clé écrite par deux jobs, c'est se donner un moyen de perdre
    l'irremplaçable en réécrivant l'autre.

    ⚠️ ET L'ARCHIVE PORTE LE JOUR DE SON PROPRE RUN, pas la veille.
    `agrume_fcst.py` archive HIER (le produit A est encore sur R2) ;
    ici les tuiles n'ont AUCUN historique, donc le job lit le jour même
    et `fcstarome_{J}` contient bien « les prévisions émises le jour J »
    — la même chose que `fcst_{J}`, écrit le matin de J lui aussi.

    ⓘ Ce préfixe est le seul endroit du dépôt où il est écrit. C'est
    `arome_fcst.py` qui l'importe d'ici, pas l'inverse.
    """
    return f"fcstarome/{day:%Y/%m}/fcstarome_{day:%Y-%m-%d}.ndjson.gz"


def fcst_reduit_key(day: datetime) -> str:
    """Le flux du GROUPE RÉDUIT sur les candidates (lot S0.11, 23/08) —
    un préfixe à part, et cette fois ce n'est pas pour la même raison
    que `fcstagrume` et `fcstarome`.

    ⛔ **CE FLUX N'EST PAS UNE PARTIE DE `fcst/`, ET LES CONFONDRE
    COÛTERAIT DES CENTAINES DE CASES.** `collect.FLUX_PARTITIONNE` vaut
    `"fcst"` et reste vrai : la partition du S0.6 découpe UNE population
    par groupe de modèles, et `fcst_parties()` compte ses parties dans
    le manifeste de `fcst/`. Ici, ce n'est pas un découpage : c'est UNE
    AUTRE POPULATION (les balises des cinq réseaux d'observation, hors
    Pioupiou et hors METAR), collectée par un autre job, à une autre
    heure, avec un autre groupe de modèles. Écrire dans `fcst_*` ferait
    compter cette passe comme une partie manquante de la nuit Pioupiou
    — exactement l'incident que le S0.9 vient d'éteindre.

    ⚠️ **ET IL PORTE LES MÊMES NOMS DE MODÈLES QUE `fcst/`**, à dessein :
    `icon_d2`, `meteoswiss_icon_ch2`, `icon_eu`, `ecmwf_ifs025`,
    `gfs_global`. C'est ce qui donne au contrôle n°3 du lot S3 ses
    `k = 6` modèles partagés (les cinq + `arome_r2`) et ses 15 paires.
    Les suffixer rendrait `k = 1`, donc zéro paire, donc rien.
    ⓘ La clé d'upsert de `model_verif_daily` est
    `(day, source, station_id, model, lead_h, fcst_src)` : les mêmes
    noms de modèles ne peuvent pas créer de collision, parce que
    `source`/`station_id` sont disjoints par construction — la
    population de ce flux exclut `pioupiou` PAR SOURCE, jamais « celles
    qui n'ont pas de ligne Open-Meteo ».

    ⓘ Ce préfixe est le seul endroit du dépôt où il est écrit. C'est
    `collect_reduit.py` qui a le sien (`FLUX`), et le banc
    `test_cles_caractere_pour_caractere` vérifie que les deux chaînes
    coïncident — deux noms pour une seule notion, c'est ainsi qu'on
    écrit dans le mauvais préfixe sans s'en apercevoir.
    """
    return f"fcstreduit/{day:%Y/%m}/fcstreduit_{day:%Y-%m-%d}.ndjson.gz"


def snapshot_rows(root: pathlib.Path, day: datetime, storage=None) -> list[dict]:
    """Toutes les prévisions émises un jour donné, tous flux confondus.

    ⛔ LES FLUX R2 SONT LUS AUX TROIS OFFSETS, EXACTEMENT COMME LES
    AUTRES, et ce n'est pas une négligence. L'horizon d'AGRUME (24 h)
    fait qu'aux offsets 1 et 2 il ne reste que 1 à 4 heures appariables
    dans la journée notée ; celui d'AROME/R2 (51 h) ne laisse que
    2 heures à l'offset 2 — le run 00 Z de J−2 ne touche la journée J
    que par 00:00 et 03:00, `arome-wind/ingest.py::keep_step()` ayant
    déjà retiré 01 h et 02 h de la nuit. Dans les deux cas c'est sous
    `MIN_HOURS_DAILY`, donc `daily_rows` et `event_rows` les écartent
    tous les deux d'eux-mêmes. Écrire ici un `if offset == 0`
    produirait le même résultat en le faisant dépendre d'une constante
    lue à un autre endroit : le jour où l'horizon d'AGRUME passerait à
    48 h (ARPEGE), ou celui où `MAX_HOURS` d'`arome-wind` remonterait,
    il faudrait penser à retirer la garde. Ici, il n'y a rien à
    penser : la donnée décide. Les bancs
    `test_agrume_fcst.py::test_lead_24_ne_sort_aucune_ligne` et
    `test_arome_fcst.py::test_lead_48_ne_sort_aucune_ligne` tiennent
    la propriété.
    """
    return snapshot_rows_et_bilan(root, day, storage)[0]


#: Version de manifeste que ce fichier sait lire. Un numéro inconnu doit
#: ARRÊTER la lecture, pas être ignoré : un manifeste v2 pourrait très
#: bien déclarer ses parties autrement, et les compter comme des v1
#: donnerait un chiffre faux avec l'air d'être juste.
MANIFESTE_VERSION_LUE = 1


def fcst_parties(root: pathlib.Path, day: datetime,
                 storage=None) -> tuple[list[dict], dict]:
    """Les lignes du flux `fcst/` ET le bilan de ses parties.

    ⛔⛔ ON NE DEVINE JAMAIS COMBIEN DE PARTIES LA NUIT ATTENDAIT. C'est
    le piège central du lot S0.6, et il n'a qu'une forme : si la
    partie 2 échoue et que la notation lit « les clés qui existent », la
    journée est notée sur sept modèles en moins SANS QUE RIEN NE LE
    DISE. Le compte vient du MANIFESTE, écrit avant la première ligne de
    données ; il ne vient de nulle part ailleurs.

    Rend `(lignes, bilan)`, où le bilan est :

        {"flux": "fcst", "parties_attendues": 2, "parties_lues": 1,
         "manquantes": [{"i": 2, "cle": …, "modeles": [...]}],
         "modeles_manquants": [...], "etat": "…"}

    ⚠️ `flux` N'EST PAS DÉCORATIF. `snapshot_rows` lit TROIS flux depuis
    le lot S0.5 (`fcst`, `fcstagrume`, `fcstarome`) et UN SEUL est
    partitionné. Sans le nommer, « 1 partie sur 2 » se lit « il manque
    un flux sur deux », qui est une tout autre nuit.

    ⚠️ LES QUATRE ÉTATS, ET AUCUN N'A BESOIN D'UNE DATE DE BASCULE :

    | manifeste | clé historique | `_p2` | lecture                       |
    |-----------|----------------|-------|-------------------------------|
    | présent   | —              | —     | il fait autorité, point       |
    | absent    | présente       | vide  | journée d'AVANT la partition  |
    | absent    | présente       | pleine| ⛔ INCIDENT : manifeste perdu  |
    | absent    | absente        | vide  | ⛔ INCIDENT : nuit sans rien   |

    ⓘ LE SONDAGE DE `_p2` NE SERT PAS À COMPTER. Il ne sert qu'à savoir
    si l'ABSENCE du manifeste est excusable. Une nuit à trois parties qui
    aurait perdu son manifeste tombe donc aussi en incident — ce qui est
    la bonne réponse, puisqu'on ne saura de toute façon plus ce qu'elle
    attendait. Un `get` R2 de plus par journée d'émission, soit trois par
    nuit : Class B, 0,0001 % du palier.
    """
    manifeste = read_json(root, fcst_manifeste_key(day), storage)
    bilan = {"flux": "fcst", "parties_attendues": None, "parties_lues": 0,
             "manquantes": [], "modeles_manquants": [], "etat": "ok"}

    if isinstance(manifeste, dict) and \
            manifeste.get("version") == MANIFESTE_VERSION_LUE:
        detail = manifeste.get("detail") or []
        bilan["parties_attendues"] = int(manifeste.get("parties") or len(detail))
        rows: list[dict] = []
        for d in detail:
            cle = d.get("cle") or fcst_key(day, int(d.get("i", 1)))
            part = read_ndjson(root, cle, storage)
            if part:
                bilan["parties_lues"] += 1
                rows += part
            else:
                bilan["manquantes"].append(
                    {"i": d.get("i"), "cle": cle,
                     "modeles": list(d.get("modeles") or [])})
                bilan["modeles_manquants"] += list(d.get("modeles") or [])
        if bilan["manquantes"]:
            bilan["etat"] = "partie_manquante"
        return rows, bilan

    if isinstance(manifeste, dict):
        # Un manifeste illisible ou d'une version inconnue. ⛔ On ne
        # l'interprète PAS : on lit la clé historique, et on le dit.
        bilan["etat"] = "manifeste_version_inconnue"
        p1 = read_ndjson(root, fcst_key(day), storage)
        bilan["parties_lues"] = 1 if p1 else 0
        return p1, bilan

    # ── Pas de manifeste ────────────────────────────────────────────
    p1 = read_ndjson(root, fcst_key(day), storage)
    p2 = read_ndjson(root, fcst_key(day, 2), storage)
    if p2:
        # ⛔ Une partie 2 sans manifeste : la déclaration a été perdue.
        # On garde les lignes — la donnée est la donnée — mais on
        # REFUSE de dire combien de parties étaient attendues.
        bilan["etat"] = "manifeste_absent_mais_partie_2_presente"
        bilan["parties_lues"] = (1 if p1 else 0) + 1
        return p1 + p2, bilan
    if p1:
        bilan["parties_attendues"] = 1
        bilan["parties_lues"] = 1
        bilan["etat"] = "avant_partition"
        return p1, bilan
    bilan["etat"] = "rien_produit"
    return [], bilan


def snapshot_rows_et_bilan(root: pathlib.Path, day: datetime,
                           storage=None) -> tuple[list[dict], dict]:
    """`snapshot_rows`, plus le bilan des parties du flux `fcst/`.

    ⓘ POURQUOI DEUX FONCTIONS. `snapshot_rows` est appelée par les bancs
    d'`agrume_fcst` et d'`arome_fcst`, qui n'ont que faire du bilan ;
    lui faire rendre un couple aurait cassé trois appelants pour une
    information dont ils ne se servent pas. Et lire le bilan
    séparément aurait relu les archives une seconde fois — 6 Mo par
    offset, trois fois par nuit, pour rien.
    """
    rows, bilan = fcst_parties(root, day, storage)
    return (rows
            + read_ndjson(root, fcst_agrume_key(day), storage)
            # ⛔ LOT L10 — la classe courte, dans son propre flux. Une
            # archive absente est le cas NORMAL tant que le job n'est
            # pas installé : `read_ndjson` rend une liste vide, et rien
            # d'autre du chemin ne change.
            + read_ndjson(root, fcst_agrume_court_key(day), storage)
            # ⛔ LOT L11 — la classe au quart d'heure, encore un flux à
            # part, et pour la quatrième fois la même raison : deux jobs
            # ne partagent pas une clé d'archive, sinon celui qui échoue
            # au milieu emporte l'archive de l'autre.
            + read_ndjson(root, fcst_agrume_quart_key(day), storage)
            + read_ndjson(root, fcst_arome_key(day), storage)
            # ⛔ LE FLUX DU GROUPE RÉDUIT EST LU EN DERNIER, ET IL PORTE
            # UN VRAI `aloft_speed` (ECMWF à 850 hPa). `daily_rows`
            # établit le régime avec « le dernier qui porte la clé
            # gagne » : si une balise Pioupiou entrait dans sa
            # population, son régime serait volé à `ecmwf_ifs025` de
            # `fcst/` — en silence, sur 13 795 lignes par nuit. La
            # garantie n'est PAS ici, elle est dans
            # `collect_reduit.SOURCES_EXCLUES`, qui exclut `pioupiou`
            # PAR SOURCE ; le banc `test_regime_pioupiou_inchange` la
            # tient, et il teste LE RÉGIME, pas le nom du champ.
            + read_ndjson(root, fcst_reduit_key(day), storage)), bilan


def dire_bilan_parties(bilan: dict, offset: int) -> str:
    """Une ligne de journal qui COMPTE et qui NOMME.

    ⛔ « prévisions émises J-0 : 5 595 lignes » ne suffit plus. Un compte
    de lignes ne distingue pas une nuit complète d'une nuit à laquelle
    il manque sept modèles — les deux sont « beaucoup de lignes ». Il
    faut dire combien de parties, sur combien, et LESQUELS des modèles
    manquent.
    """
    f = bilan.get("flux", "?")
    att, lues = bilan.get("parties_attendues"), bilan.get("parties_lues", 0)
    etat = bilan.get("etat")
    if etat == "avant_partition":
        return f"`{f}/` : 1 partie (journée d'avant la partition)"
    if etat == "rien_produit":
        return (f"⛔ `{f}/` : AUCUNE donnée et AUCUN manifeste pour J-{offset} "
                f"— la nuit d'émission n'a rien produit du tout")
    if etat == "manifeste_absent_mais_partie_2_presente":
        return (f"⛔ `{f}/` : {lues} partie(s) lue(s) mais AUCUN MANIFESTE, "
                f"alors qu'une partie 2 existe — la déclaration a été perdue "
                f"et plus rien ne dit combien de parties cette nuit attendait")
    if etat == "manifeste_version_inconnue":
        return (f"⛔ `{f}/` : manifeste d'une version que ce code ne sait pas "
                f"lire — seule la clé historique a été lue")
    if etat == "partie_manquante":
        noms = ", ".join(bilan.get("modeles_manquants") or []) or "?"
        quelles = ", ".join(str(m.get("i")) for m in bilan.get("manquantes", []))
        return (f"⛔ `{f}/` : {lues}/{att} parties — partie(s) {quelles} "
                f"MANQUANTE(S) : {noms}")
    return f"`{f}/` : {lues}/{att} parties"


def to_obs_samples(row: dict) -> list[S.ObsSample]:
    t = row.get("t") or []
    sp = row.get("speed") or []
    di = row.get("dir") or []
    out = []
    for i, ts in enumerate(t):
        out.append(S.ObsSample(
            t=int(ts) * 1000,
            speed=sp[i] if i < len(sp) else None,
            dir=di[i] if i < len(di) else None))
    return out


def fcst_times_ms(row: dict) -> list[int]:
    """Reconstitue les heures valides depuis `t0` + `step_s`."""
    n = len(row.get("speed") or [])
    t0, step = int(row["t0"]), int(row["step_s"])
    return [(t0 + i * step) * 1000 for i in range(n)]


# ══════════════════════════════════════════════════════════════════
#  RÉGIME DE LA JOURNÉE
# ══════════════════════════════════════════════════════════════════

def day_regime(fcst_ref: dict | None, obs: list[S.ObsSample],
               day_start_ms: int, utc_offset_s: int) -> str:
    """Étiquette la journée d'une balise.

    ⚠️ LE VENT D'ALTITUDE VIENT D'UN SEUL MODÈLE DE RÉFÉRENCE, le même
    pour tout le monde (`collect.REGIME_REF_MODEL`). Si chaque modèle
    classait la journée avec son propre vent d'altitude, il pourrait
    « choisir » le régime dans lequel il est noté — un modèle qui voit
    du flux là où les autres voient du thermique se ferait juger sur
    une autre population de journées.

    ⚠️ ET CE N'EST PAS `crestWind.ts`. C'est du 850 hPa, un proxy. Les
    seuils de `REGIME_THRESHOLDS` ont été raisonnés sur un vent de
    crête. Ils ne sont calibrés sur rien (§16.5), mais il ne faut pas
    laisser croire que ce proxy les rend justes : le jour où on
    calibrera, c'est ce couple seuil/niveau qu'il faudra reprendre
    ensemble, pas le seuil seul.
    """
    if fcst_ref is None:
        return "unknown"
    times = fcst_times_ms(fcst_ref)
    aloft_s = fcst_ref.get("aloft_speed") or []
    aloft_d = fcst_ref.get("aloft_dir") or []
    hourly: list[tuple[int, str | None]] = []
    for i, t in enumerate(times):
        if not (day_start_ms <= t < day_start_ms + DAY_MS):
            continue
        cs = aloft_s[i] if i < len(aloft_s) else None
        cd = aloft_d[i] if i < len(aloft_d) else None
        win = [o for o in obs if abs(o.t - t) <= S.OBS_HALF_WINDOW_MS]
        surf, _, _ = S.mean_wind(win) if win else (None, None, 0)
        hourly.append((t, S.classify_regime(cs, cd, surf)))
    return S.dominant_regime(hourly, utc_offset_s=utc_offset_s) or "unknown"


# ══════════════════════════════════════════════════════════════════
#  AGRÉGAT QUOTIDIEN
# ══════════════════════════════════════════════════════════════════

def daily_rows(day: datetime, snapshots: dict[int, list[dict]],
               obs_day: list[dict], obs_prev: list[dict],
               utc_offset_s: int, clim: dict | None = None,
               bias_prior: dict | None = None, temoin: list | None = None,
               poids_comb: dict | None = None,
               bias_prior_fin: dict | None = None,
               temoin_fin: list | None = None):
    """Rend (lignes model_verif_daily, détail par tranche de vent).

    `bias_prior_fin` (lot L19) : `{(unit, model, lead): BF.PriorFin}` bâti
    par `prior_biais_fin` sur les jours STRICTEMENT antérieurs — la pente
    par secteur × tranche, avec repli sur `bias_prior` (S2). `temoin_fin`
    reçoit `(brut, corr_S2, corr_fin, placebo_fin)` sur l'échantillon.
    Absents, les colonnes `*_fin` sortent à `None` et rien d'autre ne
    bouge.

    Le détail par tranche ne va PAS en base : il alimente les
    accumulateurs le soir même. §15.4 — « ce modèle sous-estime le
    vent » est presque toujours faux en moyenne et vrai dans une
    tranche, un modèle collant au vent faible et écrêtant le vent fort.
    Une seule colonne `bias_ratio` par journée ne peut pas porter ça ;
    la stocker par tranche triplerait la table pour une donnée qui ne
    sert qu'une fois.

    `bias_prior` (lot S2) : `{(unit, model, lead): (pente, cap, n_jours)}`
    bâti par `prior_biais` sur les jours STRICTEMENT antérieurs. Absent
    ou vide, les colonnes `*_corr` sortent à `None` et le reste de la
    fonction est bit à bit ce qu'il était — c'est ce qui permet aux
    168 assertions de `test_score.py` de rester vraies sans changer.

    `temoin` : liste que la fonction remplit de couples
    `(err_brut, err_placebo)` pour une balise-jour sur `BIAIS_TEMOIN_PAS`,
    la correction d'une AUTRE balise étant appliquée à celle-ci. ⛔ Ce
    n'est pas une coquetterie : mesuré le 22/08, un antécédent tiré au
    sort rend DÉJÀ 13 % des 29 % de gain. Publier « corrigé −29 % » sans
    ce chiffre laisserait croire que 29 points viennent du site.
    """
    day_start_ms = int(day.replace(tzinfo=timezone.utc).timestamp()) * 1000
    obs_by_st = {f"{r['source']}:{r['station_id']}": to_obs_samples(r) for r in obs_day}
    prev_by_st = {f"{r['source']}:{r['station_id']}": to_obs_samples(r) for r in obs_prev}

    # Le régime s'établit une fois par balise, sur le snapshot le plus
    # frais : c'est celui qui décrit le mieux la journée qui a eu lieu.
    ref_by_st: dict[str, dict] = {}
    for row in snapshots.get(0, []):
        if "aloft_speed" in row:
            ref_by_st[f"{row['source']}:{row['station_id']}"] = row

    regimes: dict[str, str] = {}
    for key, obs in obs_by_st.items():
        regimes[key] = day_regime(ref_by_st.get(key), obs, day_start_ms, utc_offset_s)

    rows: list[dict] = []
    banded: list[dict] = []
    #: (modèle, échéance) → (pente, cap, balise) du dernier échantillon,
    #: la matière du témoin ci-dessous.
    dernier_prior: dict[tuple, tuple] = {}
    #: Lot L19 : le placebo du fin est le MÊME antécédent aux cellules
    #: tournées (`PriorFin.permute`), pas celui d'une autre balise —
    #: un autre site n'aurait pas la même couverture de cellules, et un
    #: placebo qui se tait plus souvent que le vrai gagne moins sans
    #: rien prouver.
    for offset, lead_defaut in LEAD_BY_OFFSET.items():
        for row in snapshots.get(offset, []):
            # ⛔ LOT L10 (30/08/2026) — L'ÉCHÉANCE PEUT VENIR DE LA LIGNE.
            # Jusqu'ici `lead_h` se DÉDUISAIT de l'écart en jours entre
            # le fichier de snapshot et la journée notée. La classe
            # courte casse cette déduction : ses lignes vivent dans le
            # snapshot du jour même (offset 0, donc « +6 h ») alors
            # qu'elles notent tout autre chose.
            # ⚠️ ET AUCUN NOM DE MODÈLE ICI. Le branchement aurait pu
            # tester `row["model"]` ; il aurait alors fallu l'étendre à
            # chaque série neuve, et `daily_rows` se serait mis à
            # connaître les modèles par leur nom — ce que ce fichier
            # refuse depuis le lot I. C'est la LIGNE qui déclare son
            # échéance, ou personne.
            lead_h = row.get("lead_h", lead_defaut)
            key = f"{row['source']}:{row['station_id']}"
            obs = obs_by_st.get(key)
            if not obs:
                continue
            times = fcst_times_ms(row)
            idx = [i for i, t in enumerate(times)
                   if day_start_ms <= t < day_start_ms + DAY_MS]
            if not idx:
                continue
            sub_t = [times[i] for i in idx]
            sub_s = [(row.get("speed") or [None] * len(times))[i] for i in idx]
            sub_d = [(row.get("dir") or [None] * len(times))[i] for i in idx]
            # ⛔ LOT L11 (31/08/2026) — LA DEMI-FENÊTRE ET LE PLANCHER
            # VIENNENT DU PAS DÉCLARÉ PAR LA LIGNE, jamais d'un nom de
            # modèle. Même règle que l'échéance au lot L10 : c'est la
            # LIGNE qui déclare ce qu'elle est, ou personne. Une série
            # au quart d'heure appariée avec la demi-fenêtre de l'heure
            # ronde (±20 min contre un pas de 15) compterait chaque
            # relevé dans TROIS points : le test apparié perdrait son
            # indépendance et les `n_obs` publiés seraient faux, sans
            # qu'aucun chiffre n'ait l'air anormal.
            # ⓘ `step_s = 3600` rend exactement les valeurs d'avant ce
            # lot (±20 min, plancher 6) : aucune série existante ne
            # change de population, et un banc l'exige.
            pas_s = int(row.get("step_s") or 3600)
            pairs = S.pair_series(sub_t, sub_s, sub_d, obs,
                                  S.demi_fenetre(pas_s))
            if len(pairs) < plancher_du_pas(pas_s):
                continue

            # La persistance a besoin de la VEILLE : sans elle, le skill
            # n'est pas calculable et il vaut mieux le dire que de le
            # remplacer par autre chose.
            obs_for_skill = (prev_by_st.get(key) or []) + obs
            err = S.series_error(pairs)
            skill, n_skill, mse_m, mse_r = S.skill_vs_persistence(pairs, obs_for_skill)
            bias = S.site_bias(pairs, min_pairs=MIN_HOURS_DAILY)
            ordered = sorted(err.per_hour)
            p90 = (ordered[min(len(ordered) - 1, math.floor(len(ordered) * 0.9))]
                   if len(ordered) >= 5 else None)
            # ⚠️ `.timestamp()` sur un datetime NAÏF lit l'heure locale de
            # la machine, pas UTC. collect.py écrit bien un offset
            # (`datetime.now(timezone.utc).isoformat()`), mais une archive
            # écrite autrement — ou relue sur une machine en CEST — verrait
            # `lead_exact_h` glisser de deux heures sans que rien ne le
            # signale. On tranche ici plutôt que de faire confiance.
            emitted_dt = datetime.fromisoformat(row["fetched_at"])
            if emitted_dt.tzinfo is None:
                emitted_dt = emitted_dt.replace(tzinfo=timezone.utc)
            emitted = int(emitted_dt.timestamp()) * 1000
            lead_exact = sum(t - emitted for t in (p.t for p in pairs)) / len(pairs) / 3_600_000

            # ── seconde référence : la climatologie horaire (lot G4) ──
            # ⚠️ `mse_clim` sort À CÔTÉ de `mse_persist`, jamais à sa
            # place. Les deux répondent à des questions différentes, et
            # remplacer l'une par l'autre reviendrait à changer la
            # question sans changer le nom de la réponse.
            mse_c = None
            if clim:
                c = clim.get(key)
                if c:
                    _, _, _, mse_c = INF.skill_vs_climatology(pairs, c, utc_offset_s)

            # ── troisième référence : la COMBINAISON optimale (L9c) ───
            # ⭐ Murphy 1992 : `k·persistance + (1−k)·climatologie`, avec
            # `k` = autocorrélation à 24 h de l'anomalie, par site. Elle
            # DOMINE les deux autres par construction — c'est la
            # référence la plus dure, celle qui répond à « votre skill
            # bat-il ce qu'on peut faire sans modèle » (audit §4.4).
            #
            # ⛔ DEUX COLONNES, PAS UNE. Le mélange n'existe qu'aux
            # heures où la persistance ET la climatologie existent :
            # `mse_model_comb` est le MSE du modèle sur CES heures-là.
            # Comparer `mse_model` (population « persistance ») à
            # `mse_comb` comparerait deux échantillons, pas deux
            # prévisions — le défaut §2.5.a de l'audit. Les deux
            # voyagent donc en couple, et `_case_rows` les médianise
            # ensemble.
            #
            # ⚠️ `clim` ET `poids_comb` sont tous les deux nécessaires :
            # `replay_day` n'en passe AUCUN (asymétrie connue depuis le
            # lot G1, cf. le pavé du self-test), donc `mse_comb` est nul
            # sur tout le chemin RÉGIME, exactement comme `mse_clim`. Ce
            # n'est pas une nouveauté de ce lot, et ce lot ne la répare
            # pas — il la NOMME.
            #
            # ⭐ DEUX DÉFINITIONS DEPUIS LE 02/09 (arbitrage de Yann,
            # volet c). `mse_comb` mélange la FORCE en scalaire ;
            # `mse_comb_vec` mélange les VECTEURS, dans l'espace où
            # `pair_error` mesure. Les deux sont défendables et se
            # trompent par des bouts opposés (cf.
            # `INF.combined_reference_vec`) ; on les publie côte à côte
            # et plusieurs semaines de production les départageront.
            # ⓘ UN SEUL `mse_model_comb` pour les deux : elles vivent
            # sur les mêmes heures, donc le numérateur est le même. Une
            # seconde colonne aurait laissé croire à deux populations.
            mse_cb = mse_mcb = mse_cbv = None
            if clim and poids_comb:
                c = clim.get(key)
                kk = poids_comb.get(key)
                if c and kk is not None:
                    cs = INF.skill_vs_combined(
                        pairs, c, kk, obs_for_skill, utc_offset_s)
                    mse_mcb, mse_cb, mse_cbv = (
                        cs.mse_model, cs.mse_comb, cs.mse_comb_vec)

            # ── la colonne corrigée du biais de site (lot S2) ─────────
            # ⛔ L'ANTÉCÉDENT NE CONTIENT JAMAIS LE JOUR J. Il est bâti
            # par `prior_biais` sur [J−30, J−1] et passé tout fait : il
            # n'y a, dans cette fonction, aucun chemin par lequel la
            # journée qu'on note pourrait entrer dans sa propre
            # correction. C'est le seul garde-fou qui compte ici, et
            # `test_score.py` le vérifie en lui donnant un antécédent
            # que J contredit.
            err_corr = mse_corr = n_bias = None
            pente_j = pente_du_jour(pairs)
            if bias_prior:
                prior = bias_prior.get((key, row["model"], lead_h))
                if prior:
                    pente, cap, n_bias = prior
                    cp = S.apply_bias(pairs, S.SiteBias(pente, cap, len(pairs)))
                    err_corr = S.series_error(cp).med
                    _, _, mse_corr, _ = S.skill_vs_persistence(cp, obs_for_skill)
                    # ── le témoin ────────────────────────────────────
                    # On applique à CETTE balise l'antécédent d'une
                    # AUTRE : la précédente balise échantillonnée du
                    # même modèle et de la même échéance. Si l'erreur
                    # tombe quand même, ce qui tombe n'est pas du site.
                    # Une balise-jour sur `BIAIS_TEMOIN_PAS`, pour que
                    # le coût reste une fraction du run.
                    if temoin is not None and len(rows) % BIAIS_TEMOIN_PAS == 0:
                        autre = dernier_prior.get((row["model"], lead_h))
                        if autre is not None and autre[2] != key:
                            pp = S.apply_bias(
                                pairs, S.SiteBias(autre[0], autre[1], len(pairs)))
                            temoin.append((err.med, err_corr,
                                           S.series_error(pp).med))
                        dernier_prior[(row["model"], lead_h)] = (pente, cap, key)

            # ── lot L19 : la pente par SECTEUR × TRANCHE, avec repli ──
            # ⛔ MÊME GARDE-FOU QUE LE S2 : l'antécédent fin est bâti
            # par `prior_biais_fin` sur [J−30, J−1] ; les sommes du
            # jour J (`_biais_fin`) partent dans le cache pour NOURRIR
            # J+1, jamais pour corriger J. Le niveau « balise » du
            # repli est la pente S2 ci-dessus, passée telle quelle.
            err_fin = mse_fin = niveau_fin = n_fin = None
            sommes_fin = BF.sommes_du_jour(pairs, utc_offset_s)
            pf = (bias_prior_fin or {}).get((key, row["model"], lead_h))
            p_s2 = c_s2 = None
            if bias_prior:
                _ps2 = bias_prior.get((key, row["model"], lead_h))
                if _ps2:
                    p_s2, c_s2, _ = _ps2
            if pf is not None or p_s2 is not None:
                cf, compte_fin, nj_fin = BF.appliquer(
                    pairs, pf, p_s2, c_s2, utc_offset_s)
                niveau_fin = BF.niveau_dominant(compte_fin)
                if niveau_fin is not None:
                    err_fin = S.series_error(cf).med
                    _, _, mse_fin, _ = S.skill_vs_persistence(cf, obs_for_skill)
                    n_fin = (nj_fin if niveau_fin != BF.NIVEAU_BALISE
                             else n_bias)
                    # ── le témoin du fin : cellules TOURNÉES ─────────
                    if (temoin_fin is not None and pf is not None
                            and niveau_fin != BF.NIVEAU_BALISE
                            and len(rows) % BIAIS_TEMOIN_PAS == 0):
                        pp, _, _ = BF.appliquer(
                            pairs, pf.permute(), p_s2, c_s2, utc_offset_s)
                        temoin_fin.append((err.med, err_corr, err_fin,
                                           S.series_error(pp).med))

            # ── lot L19 : la DISPERSION des membres, si la ligne en
            # porte une. ⚠️ « La ligne déclare » (patron des L10/L11) :
            # `daily_rows` ne sait pas que `bw_mix` existe, elle lit un
            # champ `spread` aligné sur `t0 + i·step_s` et le résume
            # sur les seules heures APPARIÉES — celles que l'erreur
            # d'à côté mesure, et pas une de plus.
            spread_kmh = None
            if row.get("spread"):
                _sp = row["spread"]
                _apparie = {p.t for p in pairs}
                _vals = [_sp[i] for i in idx
                         if times[i] in _apparie and i < len(_sp)
                         and S._finite(_sp[i])]
                if _vals:
                    spread_kmh = math.sqrt(sum(v * v for v in _vals) / len(_vals))

            rows.append({
                "day": day.strftime("%Y-%m-%d"),
                "source": row["source"], "station_id": row["station_id"],
                "model": row["model"], "lead_h": lead_h,
                "fcst_src": "own_archive",
                "lead_exact_h": round(lead_exact, 2),
                "regime": regimes.get(key, "unknown"),
                "n_hours": err.n,
                "err_vec_rms": _r(err.rms), "err_vec_med": _r(err.med),
                "err_vec_p90": _r(p90),
                "mse_model": _r(mse_m), "mse_persist": _r(mse_r),
                "mse_clim": _r(mse_c),
                # ── lot L9c : la référence combinée, et son témoin ────
                "mse_comb": _r(mse_cb), "mse_model_comb": _r(mse_mcb),
                "mse_comb_vec": _r(mse_cbv),
                "bias_ratio": _r(bias.speed_ratio),
                "bias_dir_deg": _r(bias.dir_offset),
                "vector_ratio": _r(err.vector_ratio),
                # ── lot S2 ────────────────────────────────────────────
                # `bias_slope` est la pente du jour J : elle ne sert PAS
                # à corriger J (ce serait la fuite), elle nourrit
                # l'antécédent de J+1. C'est pour elle que le cache de
                # rejeu change de formule.
                "bias_slope": _r(pente_j),
                "err_vec_med_corr": _r(err_corr),
                "mse_model_corr": _r(mse_corr),
                "bias_n_days": n_bias,
                # ── lot L19 (04/09) : le corrigé FIN, et son niveau ────
                # ⚠️ `bias_fin_niveau` dit QUEL niveau du repli a corrigé
                # le plus d'heures ; `bias_fin_n_days`, sur combien de
                # journées la cellule dominante repose (ou `bias_n_days`
                # quand le repli est retombé sur le S2). Sans le niveau,
                # une colonne « fin » égale à la colonne S2 se lirait
                # comme « le fin n'apporte rien » alors qu'il n'a rien
                # eu à dire.
                "err_vec_med_corr_fin": _r(err_fin),
                "mse_model_corr_fin": _r(mse_fin),
                "bias_fin_niveau": niveau_fin,
                "bias_fin_n_days": n_fin,
                # ── lot L19 : la dispersion des membres (mélange seul) ─
                "spread_kmh": _r(spread_kmh),
                "mix_n_models": row.get("mix_n"),
                # ── lot L19 : les sommes par cellule, clé PRIVÉE ───────
                # Même patron que `_murphy` : elles voyagent dans le
                # cache de rejeu, `_pour_la_base` les retire, et
                # `replay_window` les `pop` de la fenêtre (mémoire).
                BF.CLE: sommes_fin,
                # ── lot L9b (28/08) : les six sommes de Murphy ─────────
                # ⛔ UNE CLÉ PRIVÉE, PAS UNE COLONNE. `[n, Σf, Σo, Σf²,
                # Σo², Σfo]` sur la VITESSE des heures appariées de cette
                # journée : de quoi recomposer, une fois ADDITIONNÉES sur
                # la fenêtre, le r² / biais conditionnel / biais
                # systématique de Murphy 1988 (cf. `murphy.py`). Six
                # nombres par balise-jour, jamais les 24 couples.
                #
                # Le `_` initial n'est pas cosmétique : c'est ce qui
                # tient cette clé hors de `_pour_la_base`, qui prendrait
                # sinon `_murphy` pour une colonne manquante de
                # `model_verif_daily` et nommerait un `.sql` à jouer
                # pour une donnée qui n'a rien à faire en base.
                #
                # ⚠️ ELLES VOYAGENT DANS LE CACHE DE REJEU, et c'est pour
                # elles (avec `mse_comb` du volet c) que REPLAY_FORMULA
                # passe de 4 à 5.
                MU.MURPHY_KEY: MU.moments(pairs),
            })

            # ── détail par tranche de vent OBSERVÉE ──
            # ⛔ LOT L19 — UNE LIGNE SYNTHÉTIQUE NE NOURRIT PAS LA
            # MÉMOIRE DU CARACTÈRE, et c'est la ligne qui le déclare
            # (`hors_caractere`), pas un nom de modèle : même refus que
            # la classe courte au L10, pour la même raison (une mémoire
            # de trois mois pour une série en essai).
            if row.get("hors_caractere"):
                continue
            by_band: dict[str, list[S.VerifPair]] = defaultdict(list)
            for p in pairs:
                by_band[S.wind_band(p.obs_speed)].append(p)
            for band, bp in by_band.items():
                if len(bp) < 3:
                    continue
                be = S.series_error(bp)
                ratios = [p.obs_speed / p.fcst_speed for p in bp
                          if p.fcst_speed >= S.BIAS_MIN_WIND_KMH]
                offs = [S.angular_diff(p.fcst_dir, p.obs_dir) for p in bp
                        if p.fcst_dir is not None and p.obs_dir is not None
                        and p.fcst_speed >= S.BIAS_MIN_WIND_KMH
                        and p.obs_speed >= S.BIAS_MIN_WIND_KMH]
                bskill, _, bmm, bmr = S.skill_vs_persistence(bp, obs_for_skill)
                banded.append({
                    "key": key, "model": row["model"], "lead_h": lead_h,
                    "regime": regimes.get(key, "unknown"), "band": band,
                    "errKmh": be.med,
                    "speedRatio": S.median(ratios),
                    "dirOffset": S.median(offs),
                    "mseModel": bmm, "msePersist": bmr,
                })
    # ⛔ LOT L10 — LA CLASSE COURTE NE NOURRIT PAS LA MÉMOIRE DU
    # CARACTÈRE, et c'est un refus, pas un oubli. `banded` alimente
    # `model_character`, une moyenne exponentielle de TROIS MOIS qui dit
    # « ce modèle sous-estime le vent fort dans cette vallée ». Y verser
    # deux sous-séries encore EN ESSAI (le poids n'est pas tranché,
    # décision Q7) écrirait une mémoire longue pour des séries qui
    # peuvent disparaître dans quelques semaines — et il faudrait alors
    # la nettoyer, ce que personne ne sait faire.
    # ⓘ Conséquence heureuse : le CHECK `lead_h` de `model_character`
    # n'a pas besoin d'être élargi. Une contrainte qu'on laisse étroite
    # est une décision qui se défend toute seule.
    banded = [b for b in banded if b["lead_h"] not in LEADS_INSTANT_T]
    return rows, banded


def _r(x, nd: int = 4):
    return None if x is None or not S._finite(x) else round(float(x), nd)


# ══════════════════════════════════════════════════════════════════
#  LE BIAIS DE SITE APPLIQUÉ — la colonne corrigée (lot S2, 22/08/2026)
# ══════════════════════════════════════════════════════════════════
#
#  Conception et mesures : `claude/lot-s2-erreur-corrigee-22-08.md`.
#  ⛔ LA DÉCISION D N'EST PAS ROUVERTE. Le score de référence reste le
#  BRUT — c'est lui que le pilote voit. Ce qui suit publie une SECONDE
#  colonne, nommée comme telle, qui dit ce qu'un MOS donnerait.
#
#  ═══ POURQUOI UN ESTIMATEUR NEUF ET PAS `S.site_bias` ═══
#
#  `S.site_bias` rend la MÉDIANE de `obs/prev` sur les seules heures où
#  `fcst_speed >= BIAS_MIN_WIND_KMH` (8 km/h). Conditionner sur la
#  PRÉVISION sélectionne les heures où le modèle est haut : si l'erreur
#  est bruitée, `obs/prev` y est mécaniquement inférieur à 1 même quand
#  le modèle ne surestime rien. C'est un retour vers la moyenne, pas un
#  biais de site.
#
#  ⛔ MESURÉ, PAS SUPPOSÉ — 40 539 heures appariées, 19→21/08/2026,
#  ECMWF IFS 0,25° :
#
#      med(obs/prev | prev ≥ 8)  = 0,761      ← ce que `site_bias` rend
#      med(obs/prev | prev ≥ 1)  = 1,003
#      Σobs / Σprev              = 1,112
#      Σ(obs·prev) / Σ(prev²)    = 0,894      ← la pente ci-dessous
#      med(obs/prev | obs ≥ 8)   = 1,514      ← le miroir, qui prouve
#                                               que c'est la sélection
#
#  Un estimateur qui rend 0,76 et 1,51 selon le côté sur lequel on
#  conditionne ne mesure pas le vent, il mesure son propre seuil.
#
#  ⇒ On prend la PENTE DES MOINDRES CARRÉS `Σ(obs·prev) / Σ(prev²)`,
#  sur TOUTES les heures appariées, sans seuil. C'est l'estimateur qui
#  minimise l'erreur quadratique — c'est-à-dire exactement la quantité
#  que `mse_model_corr` publie — et il est insensible à la sélection
#  parce qu'il ne trie aucune heure.
#
#  ⚠️ IL VIT ICI ET PAS DANS `scoring.py`, DÉLIBÉRÉMENT. `scoring.py`
#  est tenu au flottant près par son jumeau `verifScore.ts` et par
#  `parity-scoring.ts` ; y poser une fonction neuve obligerait à écrire
#  le jumeau TS le même jour pour une arithmétique que le navigateur
#  n'appelle jamais. `S.apply_bias`, lui, est bien réutilisé tel quel :
#  la CORRECTION est commune, seule son ESTIMATION est locale.
#
#  ═══ ET POURQUOI L'ANTÉCÉDENT VIENT DES JOURS < J ═══
#
#  Corriger le jour J avec le biais mesuré le jour J, c'est noter une
#  prévision qui a vu sa propre réponse : l'erreur tomberait de moitié
#  sans qu'aucun modèle n'ait rien appris. L'antécédent est donc une
#  EWMA (demi-vie 30 j, même arithmétique en sommes que
#  `S.accumulate` — cf. son avertissement sur le biais d'initialisation)
#  arrêtée la VEILLE, reconstruite depuis le cache de rejeu.
#
#  ⚠️ PAR BALISE, PAS PAR `model_character`. L'accumulateur de
#  `model_character` ne garde AUCUN état historique : il n'a que sa
#  valeur d'aujourd'hui, laquelle a déjà intégré le jour J. L'utiliser
#  pour corriger une journée rejouée serait précisément la fuite
#  ci-dessus. La mesure dit en plus que le niveau ne change presque
#  rien : 29,4 % de gain par balise contre 28,9 % par case fine.

#: Demi-vie de l'antécédent, en jours. Identique à `S.HALF_LIFE_DAYS` —
#: écrite ici parce qu'elle décrit CETTE mémoire-ci, et qu'aligner les
#: deux par hasard n'est pas les aligner.
BIAIS_DEMI_VIE_J = 30

#: Profondeur de cache lue pour bâtir l'antécédent d'une journée.
BIAIS_PRIOR_JOURS = 30

#: Sous ce nombre de journées intégrées, la correction ne sort pas :
#: `err_vec_med_corr` et consorts restent à `None`. Une pente tirée de
#: deux journées est une pente de deux journées, pas un caractère.
BIAIS_MIN_JOURS = 3

#: Heures appariées minimales pour que la pente d'UNE journée soit
#: calculée. Même seuil que `MIN_HOURS_DAILY` : une journée qui mérite
#: une ligne mérite une pente.
BIAIS_MIN_HEURES = MIN_HOURS_DAILY

#: Garde-fous de sanité sur la pente appliquée. ⛔ Hors de ces bornes on
#: ne corrige PAS — on ne rabote pas la valeur. Une pente de 0,2 ou de 4
#: ne dit pas « ce site est très abrité », elle dit « quelque chose ne
#: va pas » (mât cassé, coordonnées fausses, unité mélangée), et publier
#: une correction dessus donnerait un chiffre lisse et faux.
BIAIS_PENTE_MIN = 0.4
BIAIS_PENTE_MAX = 2.5

#: Écart de cap maximal appliqué, en degrés. Au-delà, la girouette est
#: probablement mal orientée sur son mât — c'est une réparation de
#: terrain, pas une correction de modèle.
BIAIS_CAP_MAX_DEG = 90.0

#: Une balise-jour sur N reçoit AUSSI la correction d'une AUTRE balise,
#: pour mesurer la part du gain qui n'est pas du site (§ témoin).
BIAIS_TEMOIN_PAS = 7


def pente_du_jour(pairs) -> float | None:
    """Pente des moindres carrés `Σ(obs·prev) / Σ(prev²)` d'une journée.

    ⚠️ SANS ORDONNÉE À L'ORIGINE, et c'est voulu : une correction
    multiplicative se compose (deux jours à ×0,8 font ×0,64) et
    s'accumule donc en log, ce qu'une affine ne sait pas faire. C'est
    aussi la forme que `S.apply_bias` sait appliquer, et le lot S2 ne
    change pas la correction, seulement son estimation.

    ⚠️ Sur la FORCE seule. Le cap a son propre estimateur (l'écart
    circulaire médian de `S.site_bias`), qui, lui, conditionne des DEUX
    côtés (`fcst_speed >= 8` ET `obs_speed >= 8`) — une condition
    symétrique ne fabrique pas le biais qu'elle mesure, et une girouette
    sous 8 km/h raconte vraiment n'importe quoi.

    ⚠️ L'ARITHMÉTIQUE VIT DANS `scoring.py`, PAS ICI — et c'est le second
    commit du lot S2 qui l'y a mise, en réparant `S.site_bias` du même
    coup. Cette fonction n'est plus qu'un GARDE : le seuil d'heures
    propre au rejeu quotidien. Deux copies de `Σof/Σff` dans le projet
    auraient été exactement la duplication non vérifiée contre laquelle
    l'en-tête de `scoring.py` met en garde.
    """
    if len(pairs) < BIAIS_MIN_HEURES:
        return None
    return S.pente_moindres_carres(pairs)


class AccBiais:
    """EWMA à poids temporel, en SOMMES — le patron de `S.Accumulator`.

    On refait ici les trois lignes plutôt que d'importer l'accumulateur
    de `scoring.py` parce que celui-ci porte `sum_wx2` (la variance) et
    une identité de ligne `model_character` dont on n'a que faire, et
    parce qu'il est tenu par la parité TS. Deux sommes suffisent.
    """
    __slots__ = ("sum_w", "sum_wx", "days", "last_day")

    def __init__(self):
        self.sum_w = 0.0
        self.sum_wx = 0.0
        self.days = 0
        self.last_day = None

    def push(self, day_i: int, x: float) -> None:
        if x is None or not S._finite(x):
            return
        # Une journée déjà intégrée ne se réintègre pas : le rejeu doit
        # pouvoir repasser deux fois sans épaissir la mémoire.
        if self.last_day is not None and day_i <= self.last_day:
            return
        decay = (1.0 if self.last_day is None
                 else 2 ** (-(day_i - self.last_day) / BIAIS_DEMI_VIE_J))
        self.sum_w = self.sum_w * decay + 1
        self.sum_wx = self.sum_wx * decay + x
        self.days += 1
        self.last_day = day_i

    @property
    def mean(self) -> float | None:
        return self.sum_wx / self.sum_w if self.sum_w > 0 else None


def _jour_index(day: datetime) -> int:
    return (day.replace(tzinfo=timezone.utc) - datetime(2026, 1, 1,
                                                        tzinfo=timezone.utc)).days


def prior_biais(root: pathlib.Path, day: datetime,
                n_jours: int = BIAIS_PRIOR_JOURS) -> dict:
    """L'antécédent du jour `day`, bâti sur les jours STRICTEMENT avant.

    Rend `{(unit, model, lead): (pente, ecart_cap_deg, n_jours)}`.

    ⚠️ NE LIT QUE LE CACHE DE REJEU, jamais l'archive. Recalculer trente
    journées pour corriger une journée coûterait trente fois le run, et
    le cache EST la projection rejouable de l'archive — c'est même son
    unique raison d'être. Conséquence assumée et publiée : tant que le
    cache est creux, `bias_n_days` est petit et la correction se tait
    d'elle-même sous `BIAIS_MIN_JOURS`. Elle s'approfondit à mesure que
    `--replay-budget` comble le passé, et `bias_n_days` voyage à côté de
    chaque chiffre pour que personne n'ait à le deviner.

    ⛔ Et le cache d'une AUTRE formule est déjà refusé par
    `replay_read` : un antécédent ne peut donc pas mélanger deux
    définitions de la pente.
    """
    acc_pente: dict[tuple, AccBiais] = {}
    acc_cap: dict[tuple, AccBiais] = {}
    for k in range(n_jours, 0, -1):          # du plus ancien au plus récent
        d = day - timedelta(days=k)
        rows = replay_read(root, d)
        if not rows:
            continue
        di = _jour_index(d)
        for r in rows:
            pente = r.get("bias_slope")
            cap = r.get("bias_dir_deg")
            if pente is None and cap is None:
                continue
            key = (f"{r['source']}:{r['station_id']}", r["model"], r["lead_h"])
            if pente is not None and pente > 0:
                acc_pente.setdefault(key, AccBiais()).push(di, math.log(pente))
            if cap is not None:
                acc_cap.setdefault(key, AccBiais()).push(di, cap)
    out: dict[tuple, tuple] = {}
    for key in set(acc_pente) | set(acc_cap):
        ap = acc_pente.get(key)
        ac = acc_cap.get(key)
        n = ap.days if ap else 0
        if n < BIAIS_MIN_JOURS:
            continue
        pente = math.exp(ap.mean) if ap and ap.mean is not None else None
        if pente is not None and not (BIAIS_PENTE_MIN <= pente <= BIAIS_PENTE_MAX):
            pente = None
        cap = ac.mean if ac and ac.mean is not None else None
        if cap is not None and abs(cap) > BIAIS_CAP_MAX_DEG:
            cap = None
        if pente is None and cap is None:
            continue
        out[key] = (pente, cap, n)
    return out


def prior_biais_fin(root: pathlib.Path, day: datetime,
                    n_jours: int = BIAIS_PRIOR_JOURS) -> dict:
    """L'antécédent FIN du jour `day` (lot L19) : `{(unit, model, lead):
    BF.PriorFin}`, bâti sur les sommes `_biais_fin` du cache de rejeu des
    jours STRICTEMENT antérieurs — exactement comme `prior_biais`, et
    avec les mêmes conséquences assumées : un cache creux, ou écrit
    avant ce lot, ne porte pas la clé et le fin se tait (les colonnes
    `*_fin` retombent sur le S2, `bias_fin_niveau = balise`).
    """
    out: dict[tuple, BF.PriorFin] = {}
    for k in range(n_jours, 0, -1):
        d = day - timedelta(days=k)
        rows = replay_read(root, d)
        if not rows:
            continue
        di = _jour_index(d)
        for r in rows:
            sommes = r.get(BF.CLE)
            if not sommes:
                continue
            key = (f"{r['source']}:{r['station_id']}", r["model"], r["lead_h"])
            out.setdefault(key, BF.PriorFin()).push(di, sommes)
    return {k: v for k, v in out.items() if not v.vide()}


def prior_poids(root: pathlib.Path, day: datetime,
                n_jours: int = MX.MIX_PRIOR_JOURS) -> dict:
    """Les POIDS du mélange du jour `day` (lot L19) : `{(unit, lead):
    {model: poids}}`, l'inverse de l'EWMA de `err_vec_rms²` de chaque
    modèle sur cette balise, lue dans le cache des jours STRICTEMENT
    antérieurs (`MX.AccMse`, demi-vie `MX.MIX_DEMI_VIE_J`).

    ⛔ SUR `err_vec_rms`, PAS `mse_model` : la première est calculée sur
    TOUTES les heures appariées, la seconde sur celles où la persistance
    existe. Le poids doit mesurer le modèle, pas la veille.
    ⛔ ET JAMAIS SUR LE JOUR J — même garde-fou que `prior_biais`.
    ⓘ Les mélanges eux-mêmes n'entrent pas dans leurs propres poids.
    """
    accs: dict[tuple, dict[str, MX.AccMse]] = {}
    for k in range(n_jours, 0, -1):
        d = day - timedelta(days=k)
        rows = replay_read(root, d)
        if not rows:
            continue
        di = _jour_index(d)
        for r in rows:
            rms = r.get("err_vec_rms")
            if rms is None or r["model"] in MX.MODELES_MELANGE:
                continue
            if r["lead_h"] not in LEAD_BY_OFFSET.values():
                continue
            key = (f"{r['source']}:{r['station_id']}", r["lead_h"])
            accs.setdefault(key, {}).setdefault(r["model"], MX.AccMse()).push(
                di, float(rms) ** 2)
    out: dict[tuple, dict[str, float]] = {}
    for key, par_modele in accs.items():
        p = MX.poids_depuis_mse(par_modele)
        if p:
            out[key] = p
    return out


def bilan_temoin(temoin: list) -> dict | None:
    """Ce que la correction gagne, et ce qu'un HASARD gagnerait.

    ⛔ CE CHIFFRE EST LA MOITIÉ DU LIVRABLE DU LOT S2. Mesuré le 22/08
    sur 30 268 balise-jours : le vrai antécédent fait tomber l'erreur
    médiane de 29,4 %, et celui d'une balise tirée au sort la fait
    tomber de 13,0 %. Autrement dit, **44 % du gain affiché n'est pas du
    biais de site** — c'est un rétrécissement de la prévision, qui
    réduit une erreur quadratique dès lors que la prévision est bruitée,
    quelle que soit la balise dont vient le facteur.

    Publier « corrigé −29 % » sans ce témoin serait exact et trompeur à
    la fois. Il sort donc dans le journal du run ET dans le `meta` du
    JSON publié, à côté du chiffre qu'il tempère.
    """
    if len(temoin) < 30:
        return None
    brut = S.median([t[0] for t in temoin])
    corr = S.median([t[1] for t in temoin])
    plac = S.median([t[2] for t in temoin])
    if not brut:
        return None
    g_corr = 100 * (brut - corr) / brut
    g_plac = 100 * (brut - plac) / brut
    return {
        "n": len(temoin),
        "err_brut": _r(brut, 3), "err_corr": _r(corr, 3),
        "err_placebo": _r(plac, 3),
        "gain_pct": _r(g_corr, 1), "gain_placebo_pct": _r(g_plac, 1),
        "part_site_pct": _r(g_corr - g_plac, 1),
        "texte": (f"sur {len(temoin)} balise-jours échantillonnés, le vrai "
                  f"antécédent gagne {g_corr:.1f} % et celui d'une AUTRE "
                  f"balise {g_plac:.1f} % — la part imputable au site est "
                  f"{g_corr - g_plac:.1f} point(s), le reste est un "
                  f"rétrécissement de la prévision"),
    }


# ══════════════════════════════════════════════════════════════════
#  PRESSION (E6) — lot S1, 21/08/2026
# ══════════════════════════════════════════════════════════════════
#
#  Conception complète : `claude/lot-s1-conception-appariement-21-08.md`.
#
#  ⛔ POURQUOI UNE FONCTION SŒUR DE `daily_rows` ET PAS UNE BRANCHE DEDANS
#
#  `daily_rows` boucle sur les PRÉVISIONS et rend une ligne par (point de
#  prévision × modèle × échéance), avec `source:station_id` = le point de
#  prévision, parce que pour le vent les deux bouts SONT le même point.
#
#  Ici, non. `pmsl` n'est archivé qu'aux ~648 coordonnées Pioupiou, qui
#  ne mesurent jamais de pression ; les réseaux qui en mesurent sont
#  ailleurs. Les lignes de pression sont donc clé par la station
#  D'OBSERVATION, sur une autre population, avec d'autres colonnes et
#  d'autres refus. Les faire cohabiter dans une seule boucle demanderait
#  un `if` à chaque étape — c'est-à-dire le pansement que le lot S1
#  refusait explicitement.
#
#  ⇒ `daily_rows` N'EST PAS MODIFIÉE. Les 168 assertions de
#  `test_score.py` ne peuvent pas bouger : le code qu'elles couvrent
#  n'est pas touché. La preuve n'est pas « le banc est vert », c'est
#  « le diff ne contient pas `daily_rows` ».

#: ⛔ QUELLES VARIABLES ONT LE DROIT D'ÊTRE APPARIÉES GÉOGRAPHIQUEMENT.
#: `geopair` ne connaît aucune variable — c'est ICI, et seulement ici,
#: que l'autorisation se donne, avec sa raison écrite.
#:
#: ⛔ `wind` N'Y EST PAS, ET CE N'EST PAS UN OUBLI. Le vent à 10 m d'une
#: balise de décollage n'est pas un champ synoptique décalé de quelques
#: kilomètres : c'est le vent DE CE SITE-LÀ, et le lot S2 existe tout
#: entier parce que ce biais de site est énorme. Apparier un METAR
#: d'aérodrome au Pioupiou d'une crête à 30 km produirait des lignes, un
#: `n` et un classement — tous faux, et indistinguables d'un vrai une
#: fois publiés.
GEOPAIR_VARIABLES = {
    "pres": {
        # Budget de bruit : le déplacement ne doit pas ajouter plus de
        # ~0,25 hPa d'erreur MÉDIANE, soit moins que les 0,3 hPa que le
        # projet accepte déjà sur toute conversion QNH → QFF
        # (`QFF_CONVERSION_UNCERTAINTY_HPA`, pressure.ts).
        # Conséquence MESURÉE le 21/08 sur 168 stations Météo-France
        # calibrées (48 h) : 50 km rend 0,243 hPa, 100 km en rendrait
        # 0,386. Ce n'est PAS `PRESSURE_MAX_KM` (25 km), qui répond à
        # une autre question — cf. §2 de la note de conception.
        "max_km": 50.0,
        # 300 m est le coude mesuré : à moins de 30 km, 300-600 m de
        # dénivelé coûtent 0,286 hPa, soit autant que 60-100 km à
        # altitude égale. Sans cette borne, un Pioupiou de crête se
        # ferait apparier à une station de plaine et le désaccord des
        # deux réductions serait compté comme une erreur de modèle.
        "max_dz_m": 300.0,
        # = `PRESSURE_MAX_ALT` de pressure.ts (03/08, Samedan LSZS :
        # Q1025 quand toute la Suisse était à Q1013-1018, et 2 à 3 hPa
        # de trop MÊME après conversion en QFF). S'applique aux DEUX
        # bouts : le `pressure_msl` d'un point à 2 000 m est la même
        # fiction, réduite depuis l'orographie du modèle.
        "max_alt_m": S.PRESSURE_MAX_ALT,
    },
}

#: Le champ où vit la pression, par source, et la convention à lui
#: appliquer. Le défaut (`pres_hpa` + `pres_kind` de la ligne) est celui
#: du schéma du S0.2 ; METAR est archivé depuis le 08/08 avec un schéma
#: antérieur, d'où l'entrée explicite. Deux entrées, pas quatre `if`.
PRES_FIELDS = {
    "metar": {"value": "qnh", "kind": "qnh", "temp": "t2m"},
}

#: ⛔ LES SEULS RÉSEAUX SUR LESQUELS `pres_err_med` A UN SENS.
#: Mesuré le 21/08 sur 764 stations Infoclimat : l'écart médian entre
#: deux baromètres amateurs distants de MOINS DE 5 KM est de 1,18 hPa,
#: et il n'atteint 1,82 qu'à 200 km — la dispersion de calage écrase
#: complètement le signal spatial. Sur les mêmes stations, la fonction
#: de structure de la TENDANCE colle à celle de Météo-France à moins de
#: 0,04 hPa : les décalages constants s'y annulent. D'où la règle, qui
#: n'est plus une intuition : `pres_err_med` sur les calibrés,
#: `ptend_err_med` sur tout le monde.
PRES_CALIBRATED = frozenset({"metar", "mf", "aemet", "smn"})


#: Toutes les clés d'archive susceptibles de porter une PRESSION.
#: METAR d'abord (le seul rempli à 100 %), puis les trois flux du S0.2.
PRES_OBS_KEY_FUNCS = [obsmetar_key, obsinfoclimat_key, obsmf_key, obsaemet_key]


def pres_obs_rows(root: pathlib.Path, day: datetime, storage=None) -> list[dict]:
    """Les observations de PRESSION de toutes les sources, une journée.

    Même principe que `all_obs_rows` : une fonction qui fusionne, jamais
    un `if` par réseau semé ailleurs. Un objet absent rend `[]`, donc une
    source qui n'existe pas encore ne casse rien — c'est le cas normal
    des premières nuits de chaque flux (les collecteurs du S0.2 ont été
    déployés le 21/08 : la première journée archivée est le 22/08).
    """
    rows: list[dict] = []
    for key_fn in PRES_OBS_KEY_FUNCS:
        rows += read_ndjson(root, key_fn(day), storage)
    return rows


def pres_samples(row: dict, refus: dict | None = None) -> list[S.PresSample]:
    """Une ligne d'archive → des relevés RAMENÉS EN QFF, ou rien.

    ⚠️ La réduction se fait ICI, une seule fois, avec l'altitude
    DÉCLARÉE PAR LA SOURCE (`elev`) — jamais `dem_alt_m`, qui ne sert
    qu'aux seuils d'appariement : 28 m d'erreur décalaient Lugano de
    3,3 hPa (mesuré le 03/08).

    Chaque refus est COMPTÉ dans `refus` plutôt que silencieux : une
    population qui rétrécit sans dire pourquoi se relit six mois plus
    tard comme « le modèle s'est amélioré ».
    """
    src = row.get("source") or ""
    spec = PRES_FIELDS.get(src)
    if spec:
        vals = row.get(spec["value"]) or []
        kind = spec["kind"]
        temps = row.get(spec["temp"]) or [] if spec.get("temp") else []
    else:
        vals = row.get("pres_hpa") or []
        # `pres_kind` est CONSTANT par ligne dans le schéma du S0.2.
        # Absent → `to_qff` refusera avec `unknown-kind`, et le comptera.
        kind = row.get("pres_kind") or ""
        temps = []
    if not vals:
        return []
    ts = row.get("t") or []
    elev = row.get("elev")
    out: list[S.PresSample] = []
    for i, t in enumerate(ts):
        if i >= len(vals):
            break
        temp = temps[i] if i < len(temps) else None
        qff, motif = S.to_qff(vals[i], kind, elev, temp)
        if qff is None:
            if refus is not None and motif:
                refus[motif] = refus.get(motif, 0) + 1
            continue
        out.append(S.PresSample(t=int(t) * 1000, qff=qff))
    return out


def pressure_rows(day: datetime, snapshots: dict[int, list[dict]],
                  pres_obs: list[dict], zone_of: dict | None = None):
    """Les agrégats quotidiens de PRESSION. Rend (lignes, bilan lisible).

    Une ligne par (station d'observation × modèle × échéance), clé par la
    station QUI MESURE — jamais par le point Pioupiou dont vient la
    prévision. Publier `pioupiou:123` sur une erreur mesurée à Ambérieu
    serait un mensonge dans la clé primaire, et plus personne ne pourrait
    s'en apercevoir. Le point utilisé voyage dans `pair_source` /
    `pair_station_id`, avec `pair_km` et `pair_dz_m`.

    ⚠️ L'APPARIEMENT EST CALCULÉ UNE SEULE FOIS, PAS UNE PAR ÉCHÉANCE.
    Sinon une même station pourrait être notée contre un point à +6 h et
    contre un AUTRE point à +48 h, et la comparaison entre échéances —
    qui est exactement ce que l'écran affiche — mélangerait deux
    géométries. L'appariement est une propriété des positions, pas de
    l'échéance.
    """
    import geopair as GP                      # noqa: PLC0415

    conf = GEOPAIR_VARIABLES["pres"]
    day_start_ms = int(day.replace(tzinfo=timezone.utc).timestamp()) * 1000
    zone_of = zone_of or {}

    def dem(cle: str):
        z = zone_of.get(cle)
        return z.get("dem_alt_m") if z else None

    # ── les candidats : les points de prévision qui portent `pmsl` ──
    # Un champ ABSENT veut dire « ce modèle ne sert pas cette variable
    # ici » (cf. `collect.py`, extension du format du 08/08) — ce n'est
    # pas une absence de valeur, c'est une absence de série.
    points: dict[str, dict] = {}
    par_point: dict[str, list[tuple[int, dict]]] = defaultdict(list)
    for offset in LEAD_BY_OFFSET:
        for row in snapshots.get(offset, []):
            if not row.get("pmsl"):
                continue
            cle = f"{row['source']}:{row['station_id']}"
            points.setdefault(cle, {"cle": cle, "lat": row["lat"],
                                    "lon": row["lon"], "dem_alt_m": dem(cle)})
            par_point[cle].append((offset, row))

    # ── les cibles : les stations qui mesurent une pression ce jour-là ──
    refus: dict[str, int] = {}
    cibles, obs_par_cle = [], {}
    for row in pres_obs:
        cle = f"{row['source']}:{row['station_id']}"
        ech = pres_samples(row, refus)
        if not ech:
            continue
        cibles.append({"cle": cle, "lat": row["lat"], "lon": row["lon"],
                       "dem_alt_m": dem(cle), "elev": row.get("elev")})
        obs_par_cle[cle] = (row, ech)

    appariement, bilan = GP.apparier(
        cibles, list(points.values()),
        max_km=conf["max_km"], max_dz_m=conf["max_dz_m"],
        max_alt_m=conf["max_alt_m"])

    rows: list[dict] = []
    for cle, (obs_row, ech) in obs_par_cle.items():
        ap = appariement.get(cle)
        if ap is None:
            continue                # « pas de modèle assez proche », jamais un 0
        calibre = obs_row["source"] in PRES_CALIBRATED
        for offset, frow in par_point.get(ap.cle, []):
            times = fcst_times_ms(frow)
            pmsl = frow.get("pmsl") or []
            idx = [i for i, t in enumerate(times)
                   if day_start_ms <= t < day_start_ms + DAY_MS]
            if not idx:
                continue
            pairs = S.pair_pressure([times[i] for i in idx],
                                    [pmsl[i] if i < len(pmsl) else None
                                     for i in idx], ech)
            if len(pairs) < MIN_HOURS_DAILY:
                continue
            emitted_dt = datetime.fromisoformat(frow["fetched_at"])
            if emitted_dt.tzinfo is None:
                emitted_dt = emitted_dt.replace(tzinfo=timezone.utc)
            emitted = int(emitted_dt.timestamp()) * 1000
            lead_exact = sum(p.t - emitted for p in pairs) / len(pairs) / 3_600_000
            rows.append({
                "day": day.strftime("%Y-%m-%d"),
                "source": obs_row["source"], "station_id": obs_row["station_id"],
                "model": frow["model"], "lead_h": LEAD_BY_OFFSET[offset],
                "fcst_src": "own_archive",
                "lead_exact_h": round(lead_exact, 2),
                "n_hours": len(pairs),
                # ⛔ `None`, pas 0, sur les baromètres non calibrés — la
                # ligne existe (sa tendance est valable), mais son erreur
                # absolue n'a pas de sens et un 0 se lirait comme un
                # modèle parfait.
                "pres_err_med": _r(S.pressure_error(pairs), 3) if calibre else None,
                "ptend_err_med": _r(S.tendency_error(pairs), 3),
                "pres_kind": (PRES_FIELDS.get(obs_row["source"], {}).get("kind")
                              or obs_row.get("pres_kind")),
                "calibrated": calibre,
                "pair_source": ap.cle.split(":", 1)[0],
                "pair_station_id": ap.cle.split(":", 1)[1],
                "pair_km": _r(ap.km, 2),
                "pair_dz_m": _r(ap.dz_m, 1),
            })

    detail = ", ".join(f"{k} {v}" for k, v in sorted(refus.items()))
    resume = (f"{len(rows)} lignes ; {len(points)} points de prévision portent "
              f"`pmsl` ; {bilan.resume()}"
              + (f" ; relevés refusés : {detail}" if detail else ""))
    return rows, resume


# ══════════════════════════════════════════════════════════════════
#  REJEU DE L'ARCHIVE (lot G1)
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ POURQUOI REJOUER PLUTÔT QUE LIRE LES AGRÉGATS.
#
# Le chemin régime posait `worst_decile_kmh = None`, `ci_low = None`,
# `ci_high = None`, `skill = None` — quatre colonnes vides sur
# précisément les lignes qui intéressent un pilote. La cause était
# structurelle : l'accumulateur de `model_character` porte TROIS SOMMES
# (`sum_w`, `sum_wx`, `sum_wx2`). Trois sommes savent faire une moyenne
# et une variance. Elles ne savent pas faire un décile, et aucune
# torsion ne leur en fera produire un — on obtiendrait un nombre qui
# ressemble à un décile sans en être un, ce qui est pire que rien.
#
# Un quantile demande la DISTRIBUTION. Elle existe : dans l'archive R2,
# qui garde les paires brutes et ne se purge jamais. On la rejoue.
#
# ⚠️ ET POURQUOI PAS `model_verif_daily`. Elle porte bien les mêmes
# balise-jours, mais avec 30 jours de rétention et sans garantie
# d'exister pour les journées antérieures au dernier correctif. Le
# rejeu depuis l'archive est la seule source qui remonte aussi loin que
# l'archive elle-même, et la seule qui reste juste quand la formule
# change (il suffit d'incrémenter `REPLAY_FORMULA`).

def replay_path(root: pathlib.Path, day: datetime) -> pathlib.Path:
    return root / REPLAY_SUBDIR / f"replay_{day:%Y-%m-%d}.json.gz"


def replay_write(root: pathlib.Path, day: datetime, rows: list[dict]) -> None:
    """Range une journée déjà calculée à côté de l'archive.

    Appelé avec le résultat de `daily_rows` du run courant : la journée
    notée ce soir est donc mise en cache SANS aucun calcul
    supplémentaire. Le rejeu n'a plus qu'à combler les trous du passé,
    ce qu'il ne fait qu'une fois par journée manquante.
    """
    try:
        p = replay_path(root, day)
        p.parent.mkdir(parents=True, exist_ok=True)
        body = json.dumps({"formula": REPLAY_FORMULA,
                           "day": day.strftime("%Y-%m-%d"),
                           "rows": rows}, separators=(",", ":")).encode("utf-8")
        p.write_bytes(gzip.compress(body))
    except OSError as exc:
        print(f"  ⚠️ cache de rejeu non écrit pour {day:%Y-%m-%d} : {exc}",
              file=sys.stderr)


def replay_read(root: pathlib.Path, day: datetime) -> list[dict] | None:
    p = replay_path(root, day)
    if not p.exists():
        return None
    try:
        d = json.loads(gzip.decompress(p.read_bytes()).decode("utf-8"))
    except (OSError, ValueError):
        return None
    # Un cache produit par une autre formule est IGNORÉ, pas réparé :
    # mélanger deux formules dans une même fenêtre donnerait une
    # distribution qui n'est celle d'aucune des deux.
    if d.get("formula") != REPLAY_FORMULA:
        return None
    return d.get("rows") or []


def replay_day(root: pathlib.Path, day: datetime, storage,
               utc_offset_s: int) -> list[dict]:
    """Les balise-jours d'UNE journée : du cache, ou recalculés."""
    cached = replay_read(root, day)
    if cached is not None:
        return cached
    snapshots = {off: snapshot_rows(root, day - timedelta(days=off), storage)
                 for off in LEAD_BY_OFFSET}
    # ⚠️ TOUTES LES SOURCES DE VENT, PAS SEULEMENT PIOUPIOU — S0.2, 21/08.
    # `all_obs_rows` fusionne `obs_key` (Pioupiou) et chaque flux ajouté
    # depuis (windsmobi, puis infoclimat/mf/aemet) ; le reste de cette
    # fonction ne change pas, il reçoit juste plus de lignes.
    obs_day = all_obs_rows(root, day, storage)
    if not obs_day:
        replay_write(root, day, [])
        return []
    obs_prev = all_obs_rows(root, day - timedelta(days=1), storage)
    # ⚠️ L'ANTÉCÉDENT DE CETTE JOURNÉE-CI, pas celui d'aujourd'hui. Une
    # journée rejouée doit être corrigée par ce qu'on savait AVANT elle,
    # sinon un rejeu de juillet appliquerait le biais d'août et le
    # « corrigé » serait meilleur que la réalité sur toute la
    # profondeur de l'archive — le genre d'erreur qui ne se voit jamais
    # parce qu'elle va dans le sens qu'on espère.
    # ── lot L19 : le mélange entre dans les snapshots, AVANT la
    # notation, avec les poids d'AVANT cette journée-ci (même règle que
    # l'antécédent du biais, juste au-dessus).
    snapshots, _ = MX.ajouter_melange(snapshots, prior_poids(root, day),
                                      LEAD_BY_OFFSET)
    rows, _ = daily_rows(day, snapshots, obs_day, obs_prev, utc_offset_s,
                         bias_prior=prior_biais(root, day),
                         bias_prior_fin=prior_biais_fin(root, day))
    replay_write(root, day, rows)
    return rows


def replay_window(root: pathlib.Path, day: datetime, storage,
                  utc_offset_s: int, n_days: int = REGIME_REPLAY_DAYS,
                  budget_new_days: int | None = None,
                  murphy_acc: dict | None = None,
                  murphy_exclus: set[str] | None = None):
    """La fenêtre rejouée, la plus récente d'abord.

    ⚠️ `murphy_exclus` (02/09/2026) : les unités que Murphy ne doit
    PAS accumuler — `unites_hors_notation(zone_of)`, doublons et
    positions suspectes. Elles restent dans `rows` : le chemin régime
    les écarte lui-même dans `_case_rows`, avec ses propres motifs et
    son propre décompte. Seul l'accumulateur les ignore ici, parce
    qu'il n'a pas de seconde chance — il se remplit au fil de l'eau et
    la clé `_murphy` meurt avec la ligne.

    Rend `(lignes, bilan)`. Chaque ligne porte en plus `unit`
    (« source:station_id »), la clé d'appariement du test du G2.

    ⚠️ `budget_new_days` BORNE LE TRAVAIL D'UNE NUIT. Rejouer trente
    journées jamais vues d'un coup peut multiplier la durée du run par
    trente, et un run qui déborde son timer est un run qui ne finit
    pas. On en rattrape donc quelques-unes par nuit, et — piège n°7 du
    lot G — LE BILAN LE DIT : une fenêtre tronquée en silence se lirait
    comme une fenêtre complète.
    """
    rows: list[dict] = []
    vus, rejoues, manquants, ignores = 0, 0, 0, 0
    for k in range(n_days):
        d = day - timedelta(days=k)
        cached = replay_read(root, d)
        if cached is None:
            if budget_new_days is not None and rejoues >= budget_new_days:
                ignores += 1
                continue
            cached = replay_day(root, d, storage, utc_offset_s)
            rejoues += 1
        if not cached:
            manquants += 1
            continue
        vus += 1
        for r in cached:
            r = dict(r)
            unit = f"{r['source']}:{r['station_id']}"
            r["unit"] = unit
            # ── lot L9b (28/08) : Murphy se FOND ICI, au fil de l'eau ──
            # ⛔⛔ ET LA CLÉ EST RETIRÉE DE LA LIGNE, TOUJOURS. Six
            # flottants et une liste par balise-jour coûtent ~260
            # octets ; la fenêtre en porte 405 486 (mesuré sur la
            # production le 28/08) — soit **~107 Mo au pic**, sur un VPS
            # de 3,8 Go SANS SWAP dont le run de cette nuit-là venait
            # d'être tué par l'OOM killer. L'accumulateur, lui, tient en
            # ~5 Mo parce que les six sommes sont ADDITIVES.
            #
            # ⚠️ `pop` INCONDITIONNEL, même sans accumulateur : personne
            # d'autre que Murphy ne lit cette clé, et la laisser
            # traîner ferait payer la mémoire à qui ne s'en sert pas
            # (`regime_scores`, `stability_report`).
            mo = r.pop(MU.MURPHY_KEY, None)
            # Lot L19 : même sort pour les sommes par cellule — personne
            # ne les lit dans la fenêtre, `prior_biais_fin` relit le
            # cache lui-même.
            r.pop(BF.CLE, None)
            if murphy_acc is not None and (murphy_exclus is None
                                           or unit not in murphy_exclus):
                MU.accumule(murphy_acc, (unit, r["model"], r["lead_h"]), mo)
            rows.append(r)
    bilan = (f"{len(rows)} balise-jours sur {vus} journées "
             f"({rejoues} rejouée(s) cette nuit, {manquants} vide(s)"
             + (f", {ignores} REPORTÉE(S) faute de budget" if ignores else "")
             + ")")
    return rows, bilan


# ══════════════════════════════════════════════════════════════════
#  CLIMATOLOGIE HORAIRE (lot G4) — la seconde référence
# ══════════════════════════════════════════════════════════════════

CLIM_SUBDIR = "clim"

#: Jours d'observations lus pour établir « le vent habituel ici à cette
#: heure-ci ». Plus long que la fenêtre de score : une climatologie qui
#: bouge chaque nuit n'est pas une climatologie.
CLIM_DAYS = 30

#: Journées distinctes minimales pour qu'une heure soit climatologisée.
CLIM_MIN_DAYS = 5


def climatology_by_station(root: pathlib.Path, day: datetime, storage,
                           utc_offset_s: int, n_days: int = CLIM_DAYS):
    """Le vent HABITUEL de chaque balise, heure locale par heure locale.

    ⚠️ POURQUOI UNE SECONDE RÉFÉRENCE. Le skill se mesure aujourd'hui
    contre la persistance — « l'observation de la même heure la veille ».
    C'est une prévision naïve redoutable sur un site de vol, et c'est la
    bonne référence pour la question « le modèle apporte-t-il quelque
    chose par rapport à hier ». Mais ce n'est pas la question que se pose
    un pilote qui consulte trois jours à l'avance : la sienne est « le
    modèle sait-il quelque chose que je ne sais pas déjà ». Battre la
    climatologie et battre la persistance sont deux exploits différents,
    et un modèle peut réussir l'un en échouant l'autre — typiquement
    quand la veille était atypique.

    ⚠️ Rend `{}` plutôt qu'une climatologie fabriquée quand l'archive est
    trop courte : au 09/08 elle porte deux jours, et « le vent habituel »
    tiré de deux journées serait le vent de ces deux journées-là.

    ── lot L9c (28/08) ──────────────────────────────────────────────
    Rend désormais un COUPLE `(clim, poids)` :
      · `clim`  — `{unit: {heure_locale: (force, cap, n_jours)}}`
      · `poids` — `{unit: k}`, le poids de la persistance dans la
        référence combinée de Murphy 1992 (l'autocorrélation à 24 h de
        l'anomalie de force, bornée à [0, 1]). Une balise sans assez
        d'archive n'y figure PAS — un `k` par défaut serait un poids
        inventé sur une référence publiée.
    Les deux sortent de la MÊME lecture de trente journées ; c'est toute
    la raison de les calculer ensemble.
    """
    # ⚠️ `_v2` DEPUIS LE LOT L9c (28/08) : le cache porte désormais DEUX
    # choses — la climatologie horaire ET le poids `k` de la référence
    # combinée, tiré des MÊMES trente journées d'observations. Garder le
    # nom d'avant aurait rendu un cache sans `k` indistinguable d'un
    # cache où aucune balise n'a assez d'archive : tous les `k` seraient
    # sortis nuls, `mse_comb` serait resté vide, et rien ne l'aurait dit.
    # Un cache qui change de CONTENU change de nom, comme une formule de
    # rejeu change de numéro.
    cache = root / CLIM_SUBDIR / f"clim_{day:%Y-%m-%d}_{n_days}_v2.json.gz"
    if cache.exists():
        try:
            d = json.loads(gzip.decompress(cache.read_bytes()).decode("utf-8"))
            return ({u: {int(h): tuple(v) for h, v in hs.items()}
                     for u, hs in d.get("clim", {}).items()},
                    {u: v for u, v in (d.get("k") or {}).items()})
        except (OSError, ValueError):
            pass

    obs_by_unit_day: dict[str, dict[str, list]] = defaultdict(dict)
    for k in range(n_days):
        d = day - timedelta(days=k)
        for row in all_obs_rows(root, d, storage):
            unit = f"{row['source']}:{row['station_id']}"
            obs_by_unit_day[unit][d.strftime("%Y-%m-%d")] = to_obs_samples(row)

    out: dict[str, dict[int, tuple]] = {}
    poids: dict[str, float] = {}
    bornes = 0
    for unit, by_day in obs_by_unit_day.items():
        clim = INF.hourly_climatology(by_day, utc_offset_s, CLIM_MIN_DAYS)
        if not clim:
            continue
        out[unit] = clim
        # ── lot L9c : le poids de Murphy 1992, sur les mêmes journées ──
        # ⛔ CALCULÉ ICI ET PAS AILLEURS, et ce n'est pas de la commodité.
        # `k` est l'autocorrélation à 24 h de l'ANOMALIE À CETTE
        # CLIMATOLOGIE-CI : le calculer dans une seconde fonction
        # obligerait à relire les trente mêmes journées d'archive (le
        # poste le plus cher du run) et ouvrirait la porte à ce qu'un
        # jour les deux ne parlent plus de la même climatologie.
        rho = INF.autocorr_lag24(by_day, clim, utc_offset_s)
        kk, borne = INF.poids_combine(rho)
        if kk is not None:
            poids[unit] = kk
            bornes += int(borne)
    if bornes:
        # ⛔ COMPTÉ ET DIT. Une borne qui se déclenche souvent n'est plus
        # un garde-fou, c'est un modèle faux — cf. le pavé de
        # `INF.poids_combine`.
        print(f"  ⓘ référence combinée : {bornes} balise(s) sur "
              f"{len(poids)} avaient un ρ hors [0, 1], ramené à la borne")
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(gzip.compress(json.dumps(
            {"clim": {u: {str(h): list(v) for h, v in hs.items()}
                      for u, hs in out.items()},
             "k": poids},
            separators=(",", ":")).encode("utf-8")))
    except OSError:
        pass
    return out, poids


# ══════════════════════════════════════════════════════════════════
#  ZONES ET REPLI
# ══════════════════════════════════════════════════════════════════
#
# ═══ QUI CRÉE LES LIGNES `model_zone` — décision du 08/08 (lot B) ═══
#
# Trois producteurs se partagent cette table, et la frontière entre eux
# n'est PAS une affaire de goût : elle se lit dans le schéma.
#
#   échelon 1  `b45.28_6.51:valley`   → LE SCRIPT D'AFFECTATION
#   échelon 2  `alpes-nord:valley`    → `zone_rows_needed`, ici
#   échelon 3  `*:valley`             → le SQL (step35), une fois
#   échelon 4  `alpes-nord:*`         → `zone_rows_needed`, ici
#   échelon 5  `*:*`                  → le SQL (step35), une fois
#
# LA RAISON, et pas seulement le comportement : `station_zone.zone_id`
# porte LUI-MÊME une clé étrangère vers `model_zone` (step35 l. 199).
# L'échelon 1 doit donc exister AVANT que la balise ne soit rattachée —
# donc avant que ce job ne voie quoi que ce soit. Aucun autre producteur
# n'est possible, et c'est ce qui tranche la question.
#
# ⚠️ COROLLAIRE, ET IL COMPTE : ce job n'a PAS à rattraper un échelon 1
# manquant, et un tel « filet » serait du code mort par construction. La
# clé étrangère garantit déjà que toute ligne `station_zone` lue ici a sa
# ligne `model_zone`. Écrire ce filet donnerait l'illusion d'une défense
# là où il n'y a rien à défendre — et masquerait que la vraie défense est
# la contrainte, qui échoue tôt, en pleine session, avec un message clair.
#
# Les échelons 2 et 4, eux, ne sont référencés que par `model_score_zone`
# et `model_character`, écrits des heures plus tard : rien ne force leur
# existence, et ce job est le seul à pouvoir les reconstruire depuis les
# lignes `station_zone` qu'il vient de lire. D'où `zone_rows_needed`.

#: Formes de terrain en français, pour les libellés lus dans l'atelier
#: admin. Les mêmes mots que les libellés semés par le SQL (« Fonds de
#: vallée, tous massifs »), pour qu'une liste triée se lise d'un bloc.
LANDFORM_FR = {
    "valley": "Fonds de vallée", "slope": "Versants", "ridge": "Crêtes",
    "plateau": "Plateaux", "plain": "Plaines", "coastal": "Littoral",
}

#: Massifs en français — MIROIR de `MASSIFS` dans `src/lib/zoneClass.ts`,
#: qui reste la source de vérité. Un identifiant absent d'ici retombe sur
#: lui-même : un libellé moins joli, jamais une ligne manquante.
MASSIF_FR = {
    "alpes-nord": "Alpes du Nord", "alpes-sud": "Alpes du Sud",
    "alpes-suisses": "Alpes suisses", "jura": "Jura", "vosges": "Vosges",
    "pyrenees-ouest": "Pyrénées occidentales",
    "pyrenees-est": "Pyrénées orientales",
    "massif-central": "Massif central", "corse": "Corse",
    "mediterranee": "Pourtour méditerranéen",
    "atlantique": "Façade atlantique", "france-nord": "Moitié nord",
    "france-sud": "Moitié sud", "espagne": "Espagne",
}


def zone_id_for(zone: dict) -> str:
    """L'identifiant de la case fine d'une balise — l'échelon 1.

    Reproduit `zoneClass.assignZone` : le bassin s'il est connu, sinon
    le massif, sinon `*`. Le dernier cas n'est pas un aveu d'échec mais
    la réponse honnête : un point sans bassin ET sans massif n'a pas de
    case à lui, et « cette forme de terrain, partout » est ce qu'on sait
    de plus fin à son sujet.
    """
    head = zone.get("basin_id") or zone.get("massif_id") or "*"
    return f"{head}:{zone['landform']}"


# ══════════════════════════════════════════════════════════════════
#  LES DOUBLONS D'INSCRIPTION (lot L17, 27/08/2026)
# ══════════════════════════════════════════════════════════════════

#: La colonne de `station_zone` qui dit qu'une inscription est la
#: SECONDE d'un capteur déjà noté ailleurs.
#:
#: ⛔ POURQUOI CE GESTE EXISTE — mesuré par le lot L16 sur 21 jours
#: d'archives et 298 122 balise-jours, pas déduit :
#:   · 262 paires de balises sont à moins de 300 m ET s'accordent à
#:     moins d'1 km/h médian sur plus de 120 heures — c'est le même
#:     capteur, republié par deux réseaux (270 paires
#:     `pioupiou` ↔ `windsmobi/ffvl`, 47 `metar` ↔ `mf`) ;
#:   · 79 de plus au même point avec un écart qui s'explique par la
#:     CHAÎNE (le METAR est publié en nœuds ENTIERS, quantum
#:     1,852 km/h, sur une moyenne de dix minutes) ;
#:   · elles pèsent 3,05 à 3,62 % des balise-jours de la fenêtre.
#:
#: ⛔ ET CE QUE ÇA COÛTAIT, mesuré en rejouant la nuit DEUX FOIS :
#:   · **80 à 92 cases publiées n'existaient que grâce à un doublon** —
#:     `MIN_STATIONS_ZONE` vaut 3, et la troisième station était une
#:     seconde inscription de la première ;
#:   · **15 à 16 podiums changeaient** ; `rank_reason = 'ok'` tombe de
#:     584 à 504 lignes une fois les doublons retirés ;
#:   · le `n` de 519 à 553 cases était gonflé (médiane +6 %, queue à
#:     +600 % : une case passait de 84 à 12 balise-jours) ;
#:   · le `m` de Benjamini-Hochberg (lot L3) passait de 665 à 616.
#:
#: ⚠️ ELLE PORTE L'UNITÉ CANONIQUE EN TOUTES LETTRES
#: (« pioupiou:1494 »), jamais un booléen. Un booléen dirait « celle-ci
#: est en trop » sans dire de QUI — et une déduplication dont on ne
#: peut plus retrouver le représentant n'est plus défaisable, ni
#: relisible dans six mois.
#:
#: ⓘ Elle est posée à CÔTÉ de `position_suspecte`, pas à sa place.
#: Les deux excluent, mais pour deux raisons opposées : l'une dit « je
#: ne sais pas OÙ est cette balise », l'autre dit « je sais très bien
#: où elle est — au même endroit qu'une autre ». Les confondre, c'est
#: se condamner à ne plus savoir laquelle des deux exclusions défaire.
COL_DOUBLON = "doublon_de"


def est_doublon(zone: dict | None) -> bool:
    """La balise est-elle une SECONDE inscription d'un capteur déjà noté ?

    ⚠️ UN SEUL TEST POUR TROIS APPELANTS (`_case_rows`,
    `accumulator_updates`, et le filtre du duel dans `main`). Trois
    `z.get("doublon_de")` semés dans le fichier, c'est trois endroits
    où la colonne peut être renommée à moitié — et deux d'entre eux
    continueraient de compter deux fois, sans rien faire rougir.
    """
    return bool(zone and zone.get(COL_DOUBLON))


def unites_hors_notation(zone_of: dict[str, dict]) -> set[str]:
    """Les unités qu'AUCUN diagnostic ne doit compter : doublon
    d'inscription (lot L17) et position suspecte (lot L15).

    ⛔ POURQUOI UNE FONCTION DE PLUS (02/09/2026). La vérification de
    cohérence des lots a compté les chemins qui écartent une balise :
    `_case_rows` et `accumulator_updates` écartaient les deux motifs,
    le duel (L1) n'écartait QUE le doublon, et Murphy (L9b) — rempli
    dans `replay_window`, AVANT toute lecture de `zone_of` —
    n'écartait RIEN : `model_murphy.json` comptait deux fois les
    ~35 000 balise-jours de doublons que le classement venait de
    retirer, et `pioupiou:1333` (147 km entre gel et référentiel)
    alimentait le cumul du duel dont le verdict est attendu à ~40 j.
    Deux diagnostics du même run sur deux populations, sans qu'une
    ligne le dise.

    ⚠️ Ce n'est PAS le filtre de `_case_rows` : lui écarte aussi les
    zones inconnues et `basin_uncertain`, parce qu'une CASE a besoin
    d'une zone. Un diagnostic par balise (duel, Murphy) n'en a pas
    besoin — une balise sans zone y reste, comme l'arbitrage nº 5 du
    L1 l'exige (« on ajoute un filtre, pas une dépendance »).
    """
    return {u for u, z in zone_of.items()
            if est_doublon(z) or z.get("position_suspecte")}


def zone_kind_for(zone: dict) -> str:
    """L'échelon auquel appartient RÉELLEMENT le `zone_id` d'une balise.

    ⚠️ SE DÉDUIT DES COLONNES, JAMAIS DE LA FORME DE LA CHAÎNE. Un
    `LIKE '%*%'` sur l'identifiant est exactement la dépendance au format
    contre laquelle le SQL de step35 met en garde : `kind` y est
    volontairement redondant avec `zone_id` pour qu'on n'ait jamais à
    renifler l'un pour retrouver l'autre.

    ⚠️ ET C'EST AUSSI UN CORRECTIF. Avant le 08/08, `fallback_chain`
    étiquetait le premier échelon `basin_landform` quoi qu'il arrive.
    Une balise sans bassin publiait donc un score `agg_level =
    'basin_landform'` sur une zone dont `model_zone.kind` disait
    `massif_landform` : deux colonnes du même schéma se contredisaient
    sur la même zone, et le score mentait sur sa propre précision — ce
    que la colonne `agg_level` existe précisément pour empêcher.
    """
    if zone.get("basin_id"):
        return "basin_landform"
    if zone.get("massif_id"):
        return "massif_landform"
    return "landform"


def zone_row_for(zone: dict) -> dict | None:
    """La ligne `model_zone` qu'une balise EXIGE pour pouvoir être
    rattachée, ou `None` quand cette ligne est déjà semée par le SQL.

    À appeler par le script d'affectation, AVANT d'écrire `station_zone`
    (cf. la décision ci-dessus). `None` n'est pas un cas dégradé : c'est
    le cas d'une balise dont la case fine est `*:forme`, l'un des sept
    échelons constants posés une fois pour toutes par step35.
    """
    kind = zone_kind_for(zone)
    if kind == "landform":
        return None
    landform = zone["landform"]
    lf = LANDFORM_FR.get(landform, landform)
    massif = zone.get("massif_id")
    basin = zone.get("basin_id")
    if kind == "basin_landform":
        label = f"{lf} du bassin {basin}"
        if massif:
            label += f" ({MASSIF_FR.get(massif, massif)})"
    else:
        label = f"{lf}, {MASSIF_FR.get(massif, massif)}"
    return {"zone_id": zone.get("zone_id") or zone_id_for(zone), "kind": kind,
            "basin_id": basin, "massif_id": massif, "landform": landform,
            "label": label}


def zone_rows_for(zones: list[dict]) -> list[dict]:
    """Les lignes `model_zone` d'échelon 1 d'un lot de balises, dédoublonnées.

    Deux balises de la même vallée partagent leur case fine : sans ce
    dédoublonnage, le même `zone_id` partirait deux fois dans le même
    envoi, ce que PostgREST refuse (« ON CONFLICT ne peut affecter la
    ligne une seconde fois ») — un échec qui n'a rien à voir avec les
    données et tout à voir avec la façon de les envoyer.
    """
    out: dict[str, dict] = {}
    for z in zones:
        row = zone_row_for(z)
        if row:
            out[row["zone_id"]] = row
    return list(out.values())


def write_station_zones(sb, zones: list[dict]) -> tuple[int, int]:
    """Écrit `model_zone` PUIS `station_zone`, dans cet ordre, en upsert.

    ⚠️ L'ORDRE N'EST PAS NÉGOCIABLE et c'est tout l'intérêt de cette
    fonction : un script qui construit les deux jeux en mémoire puis les
    « envoie ensemble » échoue en 23503. Le point d'entrée est ici pour
    que la question ne se repose pas à chaque script d'affectation.

    ⚠️ REJOUABLE. Les deux écritures sont des upserts sur leur clé, donc
    relancer l'affectation sur les mêmes balises réécrit les mêmes
    lignes. `assigned_at` garde la trace du dernier passage.

    Rend (lignes `model_zone` créées ou réécrites, lignes `station_zone`).
    """
    rows = zone_rows_for(zones)
    n_zone = sb.upsert("model_zone", rows, "zone_id") if rows else 0
    n_stat = sb.upsert("station_zone", zones, "source,station_id")
    return n_zone, n_stat


def fallback_chain(zone: dict) -> list[tuple[str, str]]:
    """Les cinq échelons du §16.3, dans l'ordre, avec leur `agg_level`.

    ⚠️ LA FORME PASSE AVANT LE MASSIF (échelon 3 avant échelon 4). Un
    fond de vallée encaissé est mal résolu par une maille de 1,3 km
    dans les Pyrénées comme dans les Alpes, alors qu'une crête et un
    fond de vallée du même massif n'ont pas les mêmes modes d'erreur.

    Reproduit `zoneClass.zoneFallbackChain`, y compris son
    dédoublonnage : quand le bassin manque, la case fine retombe sur
    `massif:forme`, qui serait sinon dupliquée à l'échelon 2.

    ⚠️ LE PREMIER ÉCHELON N'EST PAS TOUJOURS `basin_landform`, et le
    croire était un défaut (corrigé le 08/08) : la case fine d'une
    balise sans bassin EST `massif:forme`, celle d'une balise sans
    bassin ni massif EST `*:forme`. L'étiquette vient donc de
    `zone_kind_for`, la même dérivation que celle qui a servi à écrire
    `model_zone.kind` — de sorte que `agg_level` et `kind` ne peuvent
    plus se contredire sur une même zone.
    """
    landform = zone["landform"]
    massif = zone.get("massif_id")
    chain = [(zone["zone_id"], zone_kind_for(zone))]
    if massif:
        chain.append((f"{massif}:{landform}", "massif_landform"))
    chain.append((f"*:{landform}", "landform"))
    if massif:
        chain.append((f"{massif}:*", "massif"))
    chain.append(("*:*", "global"))
    seen, out = set(), []
    for zid, level in chain:
        if zid in seen:
            continue
        seen.add(zid)
        out.append((zid, level))
    return out


def zone_rows_needed(zones: list[dict]) -> list[dict]:
    """Les lignes `model_zone` que CE JOB doit créer avant d'écrire des
    scores : les échelons `massif:forme` et `massif:*` rencontrés, et
    eux seuls.

    Périmètre exact, décidé le 08/08 (cf. le pavé en tête de section) :

    · `*:forme` et `*:*` sont posés une fois par le fichier SQL —
      inutile de les réécrire chaque nuit ;
    · `bassin:forme` appartient au script d'affectation, parce que la
      clé étrangère de `station_zone.zone_id` l'exige AVANT que la
      balise n'existe. Cette fonction ne le rattrape pas, et ce n'est
      pas un oubli : toute ligne `station_zone` lue par ce job a déjà,
      par contrainte, sa ligne `model_zone`. Un rattrapage ici ne
      pourrait jamais s'exécuter ;
    · restent les échelons 2 et 4, que rien ne force à préexister
      puisqu'ils ne sont référencés que par `model_score_zone` et
      `model_character`, écrits plus loin dans ce même run.
    """
    out: dict[str, dict] = {}
    for z in zones:
        massif = z.get("massif_id")
        if not massif:
            continue
        landform = z["landform"]
        nom = MASSIF_FR.get(massif, massif)
        lf = LANDFORM_FR.get(landform, landform)
        # ⚠️ LES DEUX LIGNES PORTENT EXACTEMENT LES MÊMES CLÉS, y compris
        # celles qui valent `None`. Ce n'est pas de la cosmétique :
        # PostgREST REFUSE un envoi groupé dont les objets n'ont pas le
        # même jeu de clés, avec un `PGRST102 — All object keys must
        # match` qui ne dit ni quelle clé ni quelle ligne.
        #
        # Défaut trouvé le 08/08 sur le PREMIER run réel avec
        # `station_zone` peuplée : `massif:forme` portait `landform`,
        # `massif:*` ne le portait pas, et les 77 lignes partaient dans
        # le même POST. Le défaut était là depuis le lot B, mais il ne
        # pouvait pas se déclencher tant que `station_zone` était vide —
        # `zone_rows_needed` rendait alors une liste vide.
        #
        # La même forme à six clés que `zone_row_for` (l'échelon 1), pour
        # que TOUTE ligne `model_zone` du projet ait la même, quel que
        # soit son producteur.
        out[f"{massif}:{landform}"] = {
            "zone_id": f"{massif}:{landform}", "kind": "massif_landform",
            "basin_id": None, "massif_id": massif, "landform": landform,
            "label": f"{lf}, {nom}"}
        out[f"{massif}:*"] = {
            "zone_id": f"{massif}:*", "kind": "massif",
            "basin_id": None, "massif_id": massif, "landform": None,
            "label": f"{nom}, toutes formes"}
    return list(out.values())


# ══════════════════════════════════════════════════════════════════
#  ACCUMULATEURS
# ══════════════════════════════════════════════════════════════════

#: Ce qu'un accumulateur mesure, et la référence par rapport à laquelle
#: un écart devient un « caractère ».
#: ⚠️ `errKmh`, `mseModel` et `msePersist` N'EXISTENT PAS dans le
#: `TraitMetric` de modelCharacter.ts, et il faudra les y ajouter. Sans
#: eux, le score par régime du §16.1 n'a nulle part où vivre : les
#: quatre métriques d'origine décrivent un BIAIS (« sous-estime le vent
#: fort »), aucune ne porte l'ERREUR TYPIQUE, qui est justement le
#: premier des deux nombres que Yann demande.
#: (définition juste avant `accumulator_updates`, plus bas — la section
#: ÉVÉNEMENTS s'intercale ici parce qu'elle n'a besoin que des zones.)

# ══════════════════════════════════════════════════════════════════
#  ÉVÉNEMENTS — `model_verif_event` (lot F, 08/08)
# ══════════════════════════════════════════════════════════════════
#
# ⚠️ CETTE SECTION ROMPT LE COMMENTAIRE DE `supabase_step35…sql`, ET
# C'EST VOULU. Ce commentaire disait « AUCUN JOB N'ÉCRIT ENCORE ICI, et
# c'est délibéré […] les seuils ne sont calibrés sur rien ». Yann a
# tranché le 08/08 au soir, en connaissance de cause : on écrit et on
# publie, AVEC un drapeau `calibrated: false` qui voyage avec les
# données jusqu'à l'affichage. Le raisonnement complet est en tête
# d'`events.py` — il n'est pas recopié ici pour qu'il n'y ait qu'un seul
# endroit à corriger le jour où les seuils seront mesurés.
#
# ⚠️ CE QUE LE DRAPEAU N'AUTORISE PAS : présenter ces chiffres comme
# calibrés, ici ou dans la PWA.

#: Quorum de balises DISTINCTES pour qu'un événement compte (§3.4).
#: Une girouette qui tourne peut être une bascule, une rafale, un arbre
#: qui a poussé ou un roulement mort ; deux balises de la même case fine
#: qui tournent dans la demi-heure, non.
EVENT_MIN_STATIONS = 2

#: Quorum d'AFFICHAGE : sous ce nombre d'événements réels (succès +
#: ratés), un POD vaut 0, 0,5 ou 1 et ne veut rien dire. Même valeur et
#: même rôle que `S.REGIME_MIN_OCCURRENCES`.
EVENT_MIN_OCCURRENCES = 8

#: Seuil d'établissement/chute. Constante en attendant `ZONE_THRESHOLDS`,
#: dont le recalibrage est hors périmètre de ce lot.
EVENT_ONSET_KMH = 12

#: Les familles qu'on PUBLIE. `reversal` est détecté, apparié et écrit en
#: base comme les autres — mais pas publié, et voici pourquoi.
#:
#: ⚠️ MESURÉ LE 08/08, PAS SUPPOSÉ. Au premier run réel, `reversal`
#: sortait 40 ratés, 0 succès, 0 fausse alarme : aucun des dix modèles
#: n'avait prévu une seule bascule. Avant de publier « POD = 0 » pour
#: tout le monde, on a cherché si c'était de la météo ou un artefact, en
#: dégradant les VRAIES balises à une mesure par heure, comme un modèle :
#:
#:     balises réelles à ~4 min .................. 34 bascules
#:     les mêmes, dégradées à 1 h ................  0 bascule
#:
#: Ce n'est pas de la météo. `hold_ms` vaut 45 min, soit MOINS que le pas
#: horaire d'un modèle : les fenêtres « avant » et « après » ne peuvent
#: jamais contenir deux valeurs horaires distinctes, et la rotation
#: mesurée vaut exactement 0°. Le balayage confirme le seuil net —
#: 45 min : 0 · 60 min : 31 · 75 min : 51 · 90 min : 22 (obs dégradées),
#: contre 34 · 37 · 42 · 42 à pleine cadence.
#:
#: Le défaut est dans `windEvents.ts` autant qu'ici : le portage est
#: fidèle, et le banc de parité le prouve. Publier ce POD dirait « aucun
#: modèle ne prévoit jamais de bascule » alors que la vérité est « notre
#: détecteur ne sait pas voir une bascule dans une série horaire » — une
#: cécité de l'outil attribuée aux modèles. C'est exactement le genre de
#: chiffre que ce chantier refuse d'afficher.
#:
#: ⚠️ ON NE CORRIGE PAS `hold_ms` ICI, ET C'EST DÉLIBÉRÉ. C'est un seuil
#: de détection, donc une décision de calibration : la changer en douce
#: pour faire apparaître des chiffres serait précisément la faute contre
#: laquelle tout le reste de ce fichier met en garde. Arbitrage laissé à
#: Yann, avec les mesures ci-dessus. Les lignes continuent d'être
#: écrites en base pendant ce temps : l'archive R2 permet de tout
#: rejouer le jour où le seuil sera tranché.
EVENT_PUBLISHABLE_TYPES = ("onset", "drop", "ramp", "breeze_yield")

#: ⚠️ VOYAGE JUSQU'AU JSON PUBLIÉ. Passera à `True` le jour où la boucle
#: de calibration (`find-episodes.ts` → `episodeReview.ts`) aura tourné
#: sur quelques dizaines de journées étiquetées en aveugle — pas avant,
#: et surtout pas parce que les chiffres « ont l'air bons ».
EVENTS_CALIBRATED = False


def _series_of(row: dict, day_start_ms: int, aloft: bool = False):
    """Une série de prévision, restreinte à la journée notée.

    ⚠️ ON DÉCOUPE LES DEUX CÔTÉS DE LA MÊME FAÇON, et c'est la raison
    d'être de cette fonction. L'archive d'observations couvre exactement
    la journée UTC ; une prévision, elle, déborde des deux côtés. Si on
    laissait la prévision déborder, le modèle pourrait « voir » une
    bascule à 23 h 50 que l'observation, tronquée, ne peut plus détecter
    faute de fenêtre — et récolterait une fausse alarme pour une
    prévision peut-être juste. Le découpage symétrique fait perdre les
    événements des ~45 premières et dernières minutes de la journée UTC
    des DEUX côtés, ce qui, pour des sites français, tombe au milieu de
    la nuit : aucune brise n'y bascule.

    `aloft=True` rend la série de crête, qui n'est PAS découpée : elle
    n'est jamais détectée, seulement interrogée par `crest_at` avec sa
    propre tolérance de ±90 min, qui a besoin des voisins.
    """
    times = fcst_times_ms(row)
    sp = row.get("aloft_speed" if aloft else "speed") or []
    di = row.get("aloft_dir" if aloft else "dir") or []
    out = []
    for i, t in enumerate(times):
        if not aloft and not (day_start_ms <= t < day_start_ms + DAY_MS):
            continue
        s = sp[i] if i < len(sp) else None
        d = di[i] if i < len(di) else None
        out.append(EV.CrestSample(t=t, speed_kmh=s, dir_deg=d) if aloft
                   else S.ObsSample(t=t, speed=s, dir=d))
    return out


def median_step_ms(series) -> int | None:
    """Le pas RÉEL d'une série, en millisecondes. Médiane des écarts.

    Médiane et pas moyenne : un trou de trois heures au milieu d'une
    journée à 4 min de cadence tirerait la moyenne à 10 min et ferait
    croire à une série grossière là où il n'y a qu'une coupure.
    """
    ts = sorted({s.t for s in series})
    if len(ts) < 3:
        return None
    return int(S.median([ts[i + 1] - ts[i] for i in range(len(ts) - 1)]) or 0) or None


def adaptive_hold_ms(series, base: int = EV.DEFAULT_DETECT.hold_ms) -> int:
    """La fenêtre de maintien, ajustée au pas réel de la série.

    ═══ L'ARBITRAGE, TRANCHÉ LE 09/08/2026 ═══

    Le lot F avait laissé `hold_ms` ouvert et le problème est
    structurel : la détection de bascule compare la fenêtre `hold_ms`
    AVANT à la fenêtre `hold_ms` APRÈS. À 45 min sur une série HORAIRE,
    les deux fenêtres ne peuvent pas contenir deux valeurs distinctes —
    le détecteur est aveugle par construction, pas par réglage.

    Mesuré sur les mêmes balises réelles (pleine cadence ~4 min /
    observations dégradées à 1 h) :

        45 min → 34 / 0      ← l'état actuel : aveugle à l'heure
        60 min → 37 / 31     ← le minimum qui marche
        75 min → 42 / 51     ← la série DÉGRADÉE en trouve plus que la
                               pleine cadence : sur-détection
        90 min → 42 / 22
       120 min → 41 / 16

    Trois voies étaient possibles. 75 min donne le plus de détections
    mais la série dégradée y trouve PLUS d'événements que la série
    complète, ce qui ne peut pas être vrai : c'est la signature d'une
    fenêtre si large qu'elle fabrique des bascules à partir du bruit de
    rééchantillonnage. 60 min fixe marche partout, mais change le
    comportement des balises denses, qui sont les seules sur lesquelles
    quoi que ce soit ait été calibré — on paierait un recul certain sur
    les bonnes données pour un gain incertain sur les mauvaises.

    D'où la fenêtre ADAPTATIVE : `max(45 min, 1,5 × pas réel)`.

      · Sur une balise à 4 min de cadence : 1,5 × 4 min = 6 min < 45 min
        → 45 min, soit EXACTEMENT le comportement d'aujourd'hui. Aucun
        recul là où il y avait de la calibration.
      · Sur une série horaire : 1,5 × 60 = 90 min → deux pas de part et
        d'autre, donc une comparaison qui a un sens.

    Le facteur 1,5 est le plus petit qui garantisse au moins un pas
    entier de chaque côté après arrondi. Ce n'est pas un réglage de
    confort : c'est la condition minimale pour que les deux fenêtres
    comparées puissent contenir des valeurs différentes.

    ⚠️ CE CHOIX VIT ICI, PAS DANS `events.py`. `events.py` est le
    portage de `windEvents.ts` et un banc de parité les compare terme à
    terme ; y ajouter une règle sans jumeau TS casserait la garantie que
    ce banc existe pour tenir. Le choix du paramètre appartient à
    l'appelant, qui est le seul à connaître la cadence de la série.

    ⚠️ ET `reversal` N'EST TOUJOURS PAS PUBLIÉ. Cette fenêtre rend la
    détection possible sur les séries horaires ; elle ne prouve pas que
    ce qu'on détecte est juste. La calibration (`EVENTS_CALIBRATED`)
    reste à faire, et `EVENT_PUBLISHABLE_TYPES` reste inchangé.
    """
    step = median_step_ms(series)
    if step is None:
        return base
    return max(base, int(round(1.5 * step)))


def station_events(series, crest, utc_offset_s: int) -> list[EV.WindEvent]:
    """Tous les événements d'UNE série : E1-E3, plus `breeze_yield`.

    ⚠️ LA MÊME DÉTECTION DES DEUX CÔTÉS, observations comme prévisions.
    Détecter les bascules réelles avec un algorithme et les bascules
    prévues avec un autre mesurerait l'écart entre deux algorithmes, pas
    la qualité du modèle.

    ⚠️ `breeze_yield` reste un mécanisme SÉPARÉ (`detect_conflicts`), pas
    une famille de plus dans `detect_all` : il exige une entrée que
    `windEvents` n'a pas (le vent de crête) et un critère que les autres
    n'ont pas (la stabilité du flux). La conversion en `WindEvent` qui
    suit est une mise en forme pour passer par le même appariement, pas
    une fusion des deux détecteurs.
    """
    # ⚠️ LA MÊME FENÊTRE DES DEUX CÔTÉS. `adaptive_hold_ms` est appelé
    # sur la série qu'on détecte, observations comme prévisions — et les
    # deux n'ont PAS la même cadence (4 min contre 60). C'est voulu : ce
    # qu'on ajuste, c'est la résolution de l'instrument à la finesse de
    # sa matière, pas un seuil de sévérité. Imposer la fenêtre de
    # l'observation à la prévision rendrait le modèle aveugle ; imposer
    # celle de la prévision à l'observation lui ferait rater ce qu'elle
    # a vraiment vu.
    p = replace(EV.DEFAULT_DETECT, hold_ms=adaptive_hold_ms(series))
    out = EV.detect_all(series, EVENT_ONSET_KMH, p)
    if crest:
        out = out + EV.conflicts_as_events(
            EV.detect_conflicts(series, crest,
                                EV.conflict_params(utc_offset_s)))
    out.sort(key=lambda e: e.t)
    return out


def event_rows(day: datetime, snapshots: dict[int, list[dict]],
               obs_day: list[dict], zone_of: dict[str, dict],
               utc_offset_s: int):
    """Rend (lignes `model_verif_event`, bilan lisible du tri).

    ⚠️ TOUT SE JOUE À L'ÉCHELON DE LA CASE FINE (`zone_id`), et les
    événements y sont CONSOLIDÉS PAR LE RÉSEAU avant d'être appariés. On
    ne remonte JAMAIS la chaîne de repli pour consolider : fusionner les
    détections de deux vallées distantes de 200 km fabriquerait des
    « événements » qui n'ont eu lieu nulle part. Les échelons supérieurs
    se construisent plus tard, en SOMMANT DES COMPTEURS (ce qui est
    licite : les cases sont disjointes), jamais en fusionnant des
    détections.

    ⚠️ LE VENT DE CRÊTE VIENT D'UN SEUL MODÈLE DE RÉFÉRENCE, le même
    pour tout le monde — même raison que `day_regime` : si chaque modèle
    apportait son propre décor, il pourrait choisir les journées où on
    le juge sur `breeze_yield`.
    """
    day_start_ms = int(day.replace(tzinfo=timezone.utc).timestamp()) * 1000
    obs_by_st: dict[str, list[S.ObsSample]] = {}
    for r in obs_day:
        key = f"{r['source']}:{r['station_id']}"
        if key not in zone_of:
            continue
        obs_by_st[key] = [o for o in to_obs_samples(r)
                          if day_start_ms <= o.t < day_start_ms + DAY_MS]

    crest_by_st: dict[str, list[EV.CrestSample]] = {}
    for row in snapshots.get(0, []):
        if "aloft_speed" not in row:
            continue
        key = f"{row['source']}:{row['station_id']}"
        if key in obs_by_st and key not in crest_by_st:
            crest_by_st[key] = _series_of(row, day_start_ms, aloft=True)

    # ── 1. observé, consolidé par case fine ──
    obs_by_zone: dict[str, list[tuple[str, list[EV.WindEvent]]]] = defaultdict(list)
    for key, samples in obs_by_st.items():
        obs_by_zone[zone_of[key]["zone_id"]].append(
            (key, station_events(samples, crest_by_st.get(key), utc_offset_s)))
    observed = {zid: EV.consolidate_network(items, EVENT_MIN_STATIONS)
                for zid, items in obs_by_zone.items()}

    # ── 2. prévu, consolidé de la même façon, par modèle et échéance ──
    fcst: dict[tuple, list[tuple[str, list[EV.WindEvent]]]] = defaultdict(list)
    for offset, lead_h in LEAD_BY_OFFSET.items():
        for row in snapshots.get(offset, []):
            # ⛔ LOT L10 — LA CLASSE COURTE NE PRODUIT PAS D'ÉVÉNEMENTS,
            # et c'est un refus, pas un oubli. Les événements (`pod`,
            # `far`, `csi`, `timing_med_min`) se comptent sur une
            # JOURNÉE de prévision ; six heures autour d'un instant de
            # décision n'en font pas une. Les laisser entrer publierait
            # un taux de fausse alerte calculé sur un sixième de la
            # matière, sous le même nom que les autres.
            if row.get("lead_h") is not None:
                continue
            # ⛔ LOT L19 — UNE LIGNE SYNTHÉTIQUE (`synthese`) NE PRODUIT
            # PAS D'ÉVÉNEMENTS : une moyenne de modèles lisse les
            # bascules et les fronts par construction ; lui compter un
            # `far` ou un `pod` publierait un modèle « prudent » qui
            # n'est prudent que parce qu'il est flou.
            if row.get("synthese"):
                continue
            key = f"{row['source']}:{row['station_id']}"
            if key not in obs_by_st:
                continue
            series = _series_of(row, day_start_ms)
            if len(series) < MIN_HOURS_DAILY:
                continue
            fcst[(zone_of[key]["zone_id"], row["model"], lead_h)].append(
                (key, station_events(series, crest_by_st.get(key), utc_offset_s)))

    # ── 3. apparier et écrire une ligne PAR ÉVÉNEMENT ──
    rows: list[dict] = []
    for (zid, model, lead_h), items in sorted(fcst.items()):
        ob = observed.get(zid, [])
        fc = EV.consolidate_network(items, EVENT_MIN_STATIONS)
        if not ob and not fc:
            continue
        for m in EV.match_events(ob, fc):
            rows.append({
                "day": day.strftime("%Y-%m-%d"),
                "zone_id": zid, "model": model, "lead_h": lead_h,
                "event_type": m.type,
                "threshold_kmh": (None if m.threshold is None
                                  else int(round(m.threshold))),
                "outcome": m.outcome,
                "timing_err_min": m.timing_err_min,
                "obs_t": _iso(m.obs_t), "fcst_t": _iso(m.fcst_t),
            })

    solo = sum(1 for zid, items in obs_by_zone.items() if len(items) < EVENT_MIN_STATIONS)
    bilan = (f"{len(obs_by_st)} balises zonées, {len(obs_by_zone)} cases fines, "
             f"dont {solo} à moins de {EVENT_MIN_STATIONS} balises (aucun "
             f"événement retenu, faute de confirmation réseau)")
    return rows, bilan


def event_scores(events: list[dict], zone_of: dict[str, dict]):
    """Agrège `model_verif_event` en POD / FAR / décalage médian.

    ⚠️ ON SOMME DES COMPTEURS POUR REMONTER LA CHAÎNE DE REPLI, on ne
    refait aucune détection. Les cases fines sont disjointes, donc les
    hits, ratés et fausses alarmes de deux vallées d'un même massif
    s'additionnent sans double compte. C'est la seule opération licite
    pour changer d'échelon ici — refaire une consolidation réseau à
    l'échelle du massif fusionnerait des bascules qui n'ont rien à voir.

    ⚠️ POURQUOI PAS UN ACCUMULATEUR `model_character`. Les trois sommes
    de `S.Accumulator` décrivent une grandeur CONTINUE (une erreur, un
    ratio) : elles ne savent pas compter des succès et des ratés. Le
    schéma l'a d'ailleurs déjà prévu, en réservant `metric in
    ('timing','frequency')` avec un `event_type` — ce sont les deux
    seules grandeurs d'événement qui soient continues, et donc les deux
    seules qui aient leur place dans un accumulateur. Les compteurs de
    contingence, eux, se recomptent chaque nuit depuis les lignes
    brutes, exactement comme `rolling_scores` recompte depuis
    `model_verif_daily`. Le brancher sur les accumulateurs est un lot à
    part, pas un raccourci à prendre ici.

    ⚠️ QUORUM RESPECTÉ, ET LES REJETS SONT COMPTÉS. Une troncature
    silencieuse se lit comme « on a tout couvert » ; le nombre de
    combinaisons écartées faute d'événements part dans le JSON.
    """
    zone_by_id: dict[str, dict] = {}
    for z in zone_of.values():
        zone_by_id.setdefault(z["zone_id"], z)

    buckets: dict[tuple, list[EV.EventMatch]] = defaultdict(list)
    inconnues = 0
    non_publiables = 0
    for e in events:
        if e["event_type"] not in EVENT_PUBLISHABLE_TYPES:
            # Écrit en base, pas publié — cf. EVENT_PUBLISHABLE_TYPES.
            # Compté, jamais tu : une troncature silencieuse se lit comme
            # « on a tout couvert ».
            non_publiables += 1
            continue
        zone = zone_by_id.get(e["zone_id"])
        if zone is None:
            # Une zone présente en base mais plus rattachée à aucune
            # balise : ses lignes restent lisibles, on ne les invente pas
            # une chaîne de repli.
            inconnues += 1
            chain = [(e["zone_id"], "unknown")]
        else:
            chain = fallback_chain(zone)
        m = EV.EventMatch(type=e["event_type"], outcome=e["outcome"],
                          timing_err_min=e.get("timing_err_min"),
                          obs_t=None, fcst_t=None,
                          threshold=e.get("threshold_kmh"))
        for zid, level in chain:
            buckets[(zid, level, e["model"], e["lead_h"], e["event_type"],
                     e.get("threshold_kmh"))].append(m)

    out: list[dict] = []
    rejets = 0
    for (zid, level, model, lead_h, etype, thr), matches in sorted(
            buckets.items(), key=lambda kv: [str(x) for x in kv[0]]):
        sc = EV.score_events(matches)
        if sc.hits + sc.misses < EVENT_MIN_OCCURRENCES:
            rejets += 1
            continue
        out.append({
            "zone_id": zid, "agg_level": level, "model": model,
            "lead_h": lead_h, "event_type": etype, "threshold_kmh": thr,
            "hits": sc.hits, "misses": sc.misses, "false_alarms": sc.false_alarms,
            # `n` est le nombre d'événements RÉELS, seul dénominateur qui
            # ait un sens pour un POD. Il est publié à côté de chaque
            # chiffre, jamais sous-entendu.
            "n": sc.hits + sc.misses,
            "pod": _r(sc.pod), "far": _r(sc.far), "csi": _r(sc.csi),
            "frequency_bias": _r(sc.frequency_bias),
            "timing_err_med_min": sc.timing_err_med_min,
            "timing_iqr_min": sc.timing_iqr_min,
        })
    return out, rejets, inconnues, non_publiables


def _publish_events(st, rows: list[dict], as_of: datetime, rejets: int,
                    non_publiables: int, dry_run: bool):
    """Publie `model_events.json` — le JSON que lira la PWA.

    ⚠️ LE DRAPEAU `calibrated` EST DANS LE FICHIER, pas dans une note de
    session. Il voyage avec les données jusqu'à l'affichage, parce que
    c'est le seul endroit où il ne peut pas se perdre.

    Mêmes règles d'affichage que tout le chantier : pas de feu
    tricolore, pas de recommandation, chaque chiffre avec son n et son
    échelon d'agrégation.
    """
    body = {
        "as_of": as_of.strftime("%Y-%m-%d"),
        "window_days": ROLLING_DAYS,
        "min_occurrences": EVENT_MIN_OCCURRENCES,
        "min_stations": EVENT_MIN_STATIONS,
        "dropped_below_quorum": rejets,
        "published_types": list(EVENT_PUBLISHABLE_TYPES),
        "withheld_rows": non_publiables,
        # ⚠️ Un fichier doit dire ce qu'il NE contient PAS. Sans cette
        # ligne, un lecteur conclurait que les bascules n'ont jamais eu
        # lieu, alors qu'elles sont en base et que c'est le détecteur qui
        # ne sait pas les voir dans une série horaire.
        "withheld_note": (
            "`reversal` est détecté, apparié et stocké dans "
            "model_verif_event, mais PAS publié ici : le détecteur est "
            "structurellement aveugle aux bascules sur une série horaire "
            "(hold_ms = 45 min < pas horaire de 60 min). Mesuré le 08/08 : "
            "les mêmes balises réelles donnent 34 bascules à ~4 min de "
            "cadence et 0 dégradées à l'heure. Publier ce POD imputerait "
            "aux modèles une cécité qui est celle de l'outil. "
            "Voir EVENT_PUBLISHABLE_TYPES dans score.py."),
        "calibrated": EVENTS_CALIBRATED,
        "calibration_note": (
            "Seuils de détection RAISONNÉS, jamais mesurés : aucune journée "
            "étiquetée n'a encore servi à les régler. Les décalages de timing "
            "sont donc lisibles comme des ordres de grandeur, pas comme des "
            "valeurs calibrées. Décision assumée du 08/08 — voir events.py."),
        "events": rows,
    }
    if st is None or dry_run:
        print("  ⓘ publication R2 sautée (pas de storage, ou dry-run)")
        return
    from storage import CACHE_REECRIT             # type: ignore
    raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
    st.put("model_events.json", raw, cache_control=CACHE_REECRIT)
    print(f"  → model_events.json publié ({len(raw) / 1024:.0f} Ko)")


def _iso(ms) -> str | None:
    """Un instant en ms vers un `timestamptz`, ou None.

    La consolidation réseau prend la MÉDIANE des instants d'une grappe,
    qui peut tomber sur une demi-milliseconde quand la grappe est paire.
    On tronque : une demi-milliseconde sur une bascule de brise n'a
    aucun sens physique, et la garder ferait échouer le format ISO.
    """
    if ms is None:
        return None
    return datetime.fromtimestamp(int(ms) // 1000, timezone.utc).isoformat()


METRICS = ("errKmh", "speedRatio", "dirOffset", "mseModel", "msePersist")


def accumulator_updates(banded: list[dict], zone_of: dict[str, dict]):
    """Les MÉDIANES DU JOUR à envoyer à `bw_character_avance`.

    ⚠️ LA VALEUR INTÉGRÉE EST UNE MÉDIANE SUR LES BALISES DE LA ZONE,
    pas une valeur de balise. Une moyenne exponentielle de médianes
    reste robuste ; une moyenne exponentielle de valeurs brutes ne l'est
    pas, et une seule balise déréglée suffirait à écrire un caractère
    faux dans une mémoire de trois mois.

    ⛔ CE QUE CETTE FONCTION NE FAIT PLUS DEPUIS LE LOT S15, ET C'EST LE
    POINT DU LOT. Elle recevait l'état courant des 739 916
    accumulateurs, appliquait `scoring.accumulate` et rendait l'état
    ABSOLU. Pour ça il fallait relire la table entière chaque nuit :
    142–157 s le 25/08, et ce coût grandissait avec l'histoire, sans
    plafond. La récurrence vit maintenant dans `bw_accumulate`
    (step51) ; ici on ne calcule plus que la médiane du jour.

    ⚠️ L'IDEMPOTENCE A CHANGÉ DE CAMP AVEC ELLE. Cette fonction écartait
    les clés dont la journée était déjà intégrée (`day_ms <=
    acc.last_day`) ; elle ne le peut plus, puisqu'elle ne connaît plus
    l'état. C'est le `where … p_day > mc.last_day` de la RPC qui tient
    désormais cette propriété, et c'est le banc de double rejeu qui
    tient le `where`. **Un rejeu de nuit n'est plus neutre par
    construction ici : il l'est par construction là-bas.**

    ⓘ `scoring.accumulate` N'EST PAS SUPPRIMÉE pour autant : elle reste
    la référence du banc de parité, la seule chose qui puisse dire que
    le SQL calcule bien la même chose.
    """
    # (zone_id, model, lead, regime, band, metric) → valeurs des balises
    buckets: dict[tuple, list[float]] = defaultdict(list)
    #: ⚠️ Une liste d'un élément et pas un `int` : le compteur est
    #: incrémenté dans la boucle, et `nonlocal` n'existe pas ici.
    n_doublons = [0]
    for b in banded:
        z = zone_of.get(b["key"])
        if z is None or z.get("basin_uncertain"):
            # Une balise dont le bassin est indéterminé (§16.4, défaut
            # n°2) est EXCLUE, pas rangée de travers.
            continue
        if z.get("position_suspecte"):
            # Coordonnées contredites par une source indépendante du
            # lieu nommé (étape 42, 10/08 — inspection des 18 balises à
            # >300 m d'écart z_modele/z_nom). Même traitement que
            # `basin_uncertain` : EXCLUE, pas rangée de travers. Posé
            # UNIQUEMENT quand une source tierce situe le lieu ailleurs,
            # jamais sur le seul écart modèle/nom (14 des 18 grands
            # écarts inspectés étaient de vrais sommets rabotés par la
            # maille — cf. claude/inspection-18-balises-ecart-resultats-10-08.md).
            continue
        if est_doublon(z):
            # ⛔ LA MÉMOIRE LONGUE AUSSI, et ce n'est pas un doublon de
            # geste. `model_character` accumule sur une demi-vie de
            # 30 jours : un doublon non écarté ICI continuerait de
            # peser dans le caractère d'une zone pendant un mois APRÈS
            # que le classement a cessé de le compter — et personne ne
            # rapprocherait les deux.
            n_doublons[0] += 1
            continue
        for zid, _level in fallback_chain(z):
            for metric in METRICS:
                v = b.get(metric)
                if v is None or not S._finite(v):
                    continue
                # ⛔ LA CASE « TOUS RÉGIMES » D'ABORD, ET SANS CONDITION.
                # Une journée qu'on n'a pas su classer reste une journée
                # de vent MESURÉE : elle doit peser dans le score
                # général même si son régime est inconnu. Couper
                # l'entrée `banded` entière deux lignes plus bas ferait
                # perdre 10 647 journées par nuit (mesuré le 25/08) —
                # sans erreur, sans rouge, exactement le genre de défaut
                # qui coûte cher ici.
                buckets[(zid, b["model"], b["lead_h"], "all",
                         "all", metric)].append(float(v))
                # ⛔ LOT S15 — ON N'ACCUMULE PLUS `regime = 'unknown'`.
                # 45 569 lignes (6,2 % de la table) et 10 647 écritures
                # par nuit, mesurées le 25/08, que RIEN ne peut lire —
                # pour deux raisons indépendantes :
                #   · `_case_rows` le refuse explicitement (« unknown
                #     n'est pas un régime », plus bas dans ce fichier) ;
                #   · côté web, `CharacterTrait.regime` est typé
                #     `Regime`, soit les SIX valeurs de classification.
                # Un constat de régime inconnu n'est donc pas seulement
                # inutile : il est INEXPRIMABLE.
                if b["regime"] == "unknown":
                    continue
                buckets[(zid, b["model"], b["lead_h"], b["regime"],
                         b["band"], metric)].append(float(v))
                # La case « toutes tranches » vit à côté des tranches,
                # pas à leur place : c'est elle qui porte le score
                # général, elles qui portent le caractère.
                buckets[(zid, b["model"], b["lead_h"], b["regime"],
                         "all", metric)].append(float(v))

    if n_doublons[0]:
        # Pas de purge silencieuse : une exclusion qui ne se compte pas
        # devient un fait acquis que personne ne peut plus contester.
        print(f"  ⓘ accumulateurs : {n_doublons[0]} entrée(s) écartée(s) "
              f"— seconde inscription d'un capteur déjà noté "
              f"(`{COL_DOUBLON}`, lot L17)")
    out: list[dict] = []
    for key, values in buckets.items():
        if len(values) < 1:
            continue
        med = S.median(values)
        if med is None:
            continue
        zid, model, lead, regime, band, metric = key
        out.append({
            "zone_id": zid, "model": model, "lead_h": lead,
            "regime": regime, "band": band, "metric": metric,
            "x": med,
        })
    # ⓘ TRIÉ PAR LA CLÉ PRIMAIRE, et ce n'est pas de la cosmétique. Les
    # clés sortent d'un `dict`, donc dans un ordre arbitraire : chaque
    # ligne tomberait au hasard dans un index de 739 916 entrées. Triées,
    # les lignes d'un même lot attaquent une plage contiguë. Le tri coûte
    # moins d'une seconde sur 372 530 lignes.
    # ⬜ LE GAIN N'EST PAS MESURÉ — c'est une hypothèse de localité (le
    # banc de `RPC_LOT` du 25/08 ne portait qu'UNE zone). À vérifier au
    # premier run réel, et à retirer si elle ne rend rien.
    out.sort(key=lambda r: (r["zone_id"], r["model"], r["lead_h"],
                            r["regime"], r["band"], r["metric"]))
    return out


# ══════════════════════════════════════════════════════════════════
#  SCORES DE ZONE
# ══════════════════════════════════════════════════════════════════

def skill_contre(mse_modele, mse_reference):
    """`(skill, bat_la_référence)`, ou `(None, None)` sous le plancher.

    ⛔ LE `None` EST LA RÉPONSE, PAS UN ÉCHEC. Une référence dont
    l'erreur RMS tient sous 1 km/h n'est pas une référence : c'est une
    journée où le vent n'a pas bougé. Le rapport y devient énorme et
    arbitraire (−2 573 000 mesuré le 11/08), et il écrase toute médiane
    et toute échelle où il entre. On rend donc `None` pour les DEUX
    réponses — y compris `bat_la_référence`, parce qu'un `false` se
    lirait comme « ce modèle a perdu » alors que la question n'a pas eu
    lieu. Détail chiffré : `SKILL_MIN_REF_MSE`.
    """
    if mse_modele is None or mse_reference is None:
        return None, None
    if mse_reference < SKILL_MIN_REF_MSE:
        return None, None
    return _r(1 - mse_modele / mse_reference), mse_modele < mse_reference


def _case_rows(units: list[dict], zone_of: dict[str, dict], as_of: datetime,
               window_kind: str, regime: str, min_stations: int,
               level_of: dict[str, str] | None = None,
               with_ci: bool = True):
    """Le corps commun des deux chemins de score.

    ⚠️ UN SEUL CORPS POUR `rolling15` ET POUR `regime`, et c'est la
    correction de fond du lot G. Les deux chemins étaient deux codes
    différents : l'un lisait des balise-jours et savait donc calculer un
    décile et un intervalle, l'autre lisait des accumulateurs et ne le
    pouvait pas. D'où quatre colonnes nulles sur 10 250 lignes — pas un
    oubli d'écriture, une impossibilité arithmétique.

    Maintenant les deux lisent la même matière : des BALISE-JOURS. Le
    chemin régime ne diffère plus que par son filtre (les journées de CE
    régime, quelle que soit leur ancienneté) et par sa fenêtre.

    `units` : lignes de balise-jour portant `unit`, `day`, `model`,
    `lead_h`, `err_vec_med`, et facultativement `mse_model`/`mse_persist`.
    """
    acc: dict[tuple, dict] = defaultdict(
        lambda: {"by_day": defaultdict(list), "st": set(), "rows": [],
                 "mse_m": [], "mse_r": [], "mse_c": [], "mse_cb": [],
                 "n_hours": 0,
                 # ── lot S2 : la colonne corrigée, À CÔTÉ ─────────────
                 "err_corr": [], "mse_cc": [], "nd": [],
                 # ── lot L9a (28/08) : le compagnon WMO du score ──────
                 # Deux listes SÉPARÉES, et pas un couple : une
                 # balise-jour porte presque toujours son `bias_ratio`
                 # (il suffit d'heures appariées, que la ligne a par
                 # construction) et souvent PAS son `bias_dir_deg` (il
                 # faut une girouette des deux côtés ET plus de
                 # BIAS_MIN_WIND_KMH des deux côtés). Les mettre dans un
                 # même couple obligerait à jeter le premier quand le
                 # second manque.
                 "bias_ratio": [], "bias_dir": []})
    #: Balise-jours écartés parce que doublon d'inscription (lot L17).
    #: ⚠️ DÉCLARÉ ICI, avant la boucle qui l'incrémente — et pas à côté
    #: de `sous_plancher`, qui vit APRÈS elle.
    #:
    #: ⚠️ CE COMPTEUR NE COMPTE PAS « LES DOUBLONS EN BASE ». Il compte
    #: les balise-jours écartés PAR CE MOTIF-LÀ, parmi ceux qui avaient
    #: survécu aux exclusions précédentes (zone inconnue,
    #: `basin_uncertain`, `position_suspecte`). Mesuré sur la production
    #: le 27/08 : 9 066 ici contre 9 083 balise-jours de doublons dans
    #: la fenêtre — les 17 manquants étaient déjà écartés pour une autre
    #: raison. Les deux nombres sont justes ; comparer l'un à l'autre
    #: comme s'ils disaient la même chose ferait croire à une fuite.
    n_doublons = 0
    for d in units:
        z = zone_of.get(d["unit"])
        if z is None or z.get("basin_uncertain"):
            continue
        if z.get("position_suspecte"):
            # Même exclusion qu'accumulator_updates — voir le
            # commentaire là-bas (étape 42, 10/08).
            continue
        if est_doublon(z):
            # ⛔ LE GESTE DU LOT L17. Écarter la balise-jour ENTIÈRE,
            # et pas seulement son rang : c'est le QUORUM
            # (`MIN_STATIONS_ZONE`, plus bas) qui fabriquait 80 à
            # 92 cases n'existant que grâce à une seconde inscription.
            # Poser un `rank_reason` sur la ligne, comme le lot L2 le
            # fait pour `duplicate_chain`, ne servirait à rien ici :
            # `duplicate_chain` écarte un MODÈLE, qui a sa propre ligne
            # de score ; un doublon est une BALISE, et une balise n'a
            # pas de ligne — elle a un poids dans les cases.
            n_doublons += 1
            continue
        if d.get("err_vec_med") is None:
            continue
        for zid, level in fallback_chain(z):
            b = acc[(zid, d["model"], d["lead_h"], level)]
            b["by_day"][d["day"]].append(d["err_vec_med"])
            b["rows"].append(d)
            if d.get("mse_model") is not None and d.get("mse_persist") is not None:
                b["mse_m"].append(d["mse_model"])
                b["mse_r"].append(d["mse_persist"])
            if d.get("mse_model") is not None and d.get("mse_clim") is not None:
                b["mse_c"].append((d["mse_model"], d["mse_clim"]))
            # ── lot L9c : la référence combinée, appariée à SON témoin ─
            # ⛔ `mse_model_comb`, PAS `mse_model`. Le mélange n'existe
            # qu'aux heures où les deux références existent, et
            # `daily_rows` a recalculé le MSE du modèle sur CES
            # heures-là exprès. Reprendre `mse_model` ici referait le
            # défaut §2.5.a que la colonne existe pour éviter.
            if (d.get("mse_model_comb") is not None
                    and d.get("mse_comb") is not None):
                # ⛔ UN TRIPLET, PAS DEUX COUPLES (02/09/2026). Les deux
                # définitions du mélange partagent leurs heures ET leur
                # `mse_model_comb` ; les ramasser dans deux listes
                # séparées aurait permis à leurs médianes de reposer sur
                # deux sous-ensembles de balise-jours le jour où l'une
                # sort nulle et pas l'autre — le défaut §2.5.a, reproduit
                # par le lot qui existe pour le fermer.
                # ⓘ `mse_comb_vec` peut manquer sur un fichier de rejeu
                # d'avant ce lot : `None` alors, et le triplet reste
                # complet pour les deux premiers.
                b["mse_cb"].append((d["mse_model_comb"], d["mse_comb"],
                                    d.get("mse_comb_vec")))
            # ── lot S2 ────────────────────────────────────────────────
            # ⚠️ LA CLIMATOLOGIE N'EST PAS CORRIGÉE, ET C'EST LA QUESTION.
            # Elle est bâtie sur des OBSERVATIONS : elle porte déjà le
            # site en elle, c'est même pour ça qu'elle gagne dans les
            # Alpes. `skill_clim_corr` demande donc « une fois le site
            # retiré du MODÈLE, bat-il une référence qui, elle, l'a
            # gardé ». C'est l'exploit qui compte, et le corriger des
            # deux côtés reviendrait à comparer deux fois la même
            # soustraction.
            if d.get("err_vec_med_corr") is not None:
                b["err_corr"].append(d["err_vec_med_corr"])
                if d.get("bias_n_days") is not None:
                    b["nd"].append(d["bias_n_days"])
            if (d.get("mse_model_corr") is not None
                    and d.get("mse_clim") is not None):
                b["mse_cc"].append((d["mse_model_corr"], d["mse_clim"]))
            # ── lot L9a : le biais de vitesse, compagnon du score ─────
            # ⚠️ RAMASSÉ ICI, DANS LA MÊME BOUCLE QUE L'ERREUR, donc
            # sur EXACTEMENT la même population de balise-jours : les
            # mêmes exclusions (zone inconnue, `basin_uncertain`,
            # `position_suspecte`, doublon L17) s'appliquent d'elles-
            # mêmes. Un second passage ailleurs aurait été un second
            # chemin, avec un second jeu de filtres à tenir à jour.
            if S._finite(d.get("bias_ratio")):
                b["bias_ratio"].append(d["bias_ratio"])
            if S._finite(d.get("bias_dir_deg")):
                b["bias_dir"].append(d["bias_dir_deg"])
            b["st"].add(d["unit"])
            b["n_hours"] += d.get("n_hours") or 0

    rows: list[dict] = []
    #: [persistance, climatologie] — cases dont la référence est sous le
    #: plancher. Compté et DIT : une correction qui fait taire des
    #: colonnes doit annoncer combien, sinon c'est une purge silencieuse.
    sous_plancher = [0, 0]
    # Le classement se décide zone par zone et échéance par échéance :
    # comparer deux modèles sur des zones différentes n'a aucun sens.
    by_case: dict[tuple, list[dict]] = defaultdict(list)
    rows_by_case_model: dict[tuple, dict[str, list[dict]]] = defaultdict(dict)
    for (zid, model, lead, level), b in acc.items():
        if len(b["st"]) < min_stations:
            continue
        # ⚠️ `level_of` (= `model_zone.kind`, lu en base) prime sur
        # l'échelon déduit de la chaîne quand il est fourni : c'est la
        # leçon du reniflage de `zone_id` corrigé le 08/08. Une zone
        # absente de `model_zone` est sautée plutôt que publiée sous un
        # échelon inventé — un score anonyme sur sa précision ment.
        if level_of is not None:
            level = level_of.get(zid)
            if level is None:
                print(f"  ⚠️ zone inconnue de model_zone, score sauté : {zid}",
                      file=sys.stderr)
                continue
        values = [v for vs in b["by_day"].values() for v in vs]
        # ⚠️ `with_ci=False` SAUTE LE BOOTSTRAP UNAIRE, et seulement lui.
        # Mesuré le 09/08 à la taille réelle (647 balises × 10 modèles ×
        # 30 jours = 194 100 balise-jours) : le chemin régime complet
        # coûte 85,6 s, dont l'essentiel part dans ce rééchantillonnage —
        # 500 tirages par ligne, sur 5 360 lignes. Le rapport de
        # stabilité (G5) n'a besoin QUE des rangs, et les rangs viennent
        # du test APPARIÉ, pas de cet intervalle-là. Le calculer deux
        # fois de plus pour le jeter serait doubler la durée du run pour
        # rien.
        ci = (INF.block_median_ci(b["by_day"]) if with_ci
              else INF.DiffCI(S.median(values), None, None, len(values),
                              len(b["by_day"]), None, "not_computed"))
        mse_m = S.median(b["mse_m"])
        mse_r = S.median(b["mse_r"])
        # ⚠️ La climatologie s'apparie AVANT de se médianiser : comparer
        # la médiane des MSE du modèle à celle d'une climatologie
        # calculée sur une population de balise-jours différente
        # comparerait deux échantillons, pas deux prévisions.
        mse_cm = S.median([m for m, _ in b["mse_c"]])
        mse_cc = S.median([c for _, c in b["mse_c"]])
        skill, bat_persist = skill_contre(mse_m, mse_r)
        skill_clim, bat_clim = skill_contre(mse_cm, mse_cc)
        # ── lot L9c : la référence la plus dure des trois ─────────────
        # ⚠️ Même appariement AVANT médianisation que pour la
        # climatologie (« comparer la médiane des MSE du modèle à celle
        # d'une référence calculée sur une population différente
        # comparerait deux échantillons »), sauf qu'ici les deux membres
        # du couple viennent DÉJÀ des mêmes heures.
        mse_cbm = S.median([m for m, _, _ in b["mse_cb"]])
        mse_cbc = S.median([c for _, c, _ in b["mse_cb"]])
        skill_comb, bat_comb = skill_contre(mse_cbm, mse_cbc)
        # ── la seconde définition, sur les MÊMES balise-jours ─────────
        # ⚠️ MÉDIANÉE SUR LE SOUS-ENSEMBLE QUI LA PORTE, et son
        # numérateur avec elle. Un fichier de rejeu d'avant le 02/09 n'a
        # pas `mse_comb_vec` : prendre `mse_cbm` (calculé sur TOUS les
        # balise-jours) au numérateur d'un dénominateur calculé sur une
        # partie d'entre eux comparerait deux populations — la faute que
        # ce volet départage depuis trois sessions. Les deux membres
        # sortent donc du même filtre.
        trio_vec = [(m, v) for m, _, v in b["mse_cb"] if v is not None]
        mse_cbm_vec = S.median([m for m, _ in trio_vec])
        mse_cbc_vec = S.median([v for _, v in trio_vec])
        skill_comb_vec, bat_comb_vec = skill_contre(mse_cbm_vec, mse_cbc_vec)
        # ── lot S2 : la même arithmétique, sur le modèle corrigé ──────
        # ⚠️ Le quorum est CELUI DE LA CASE, pas un second : une case
        # publie son corrigé si et seulement si elle publie son brut.
        # Deux populations différentes sous deux colonnes voisines
        # inviteraient à les soustraire, et la différence ne voudrait
        # rien dire.
        corr_med = S.median(b["err_corr"]) if b["err_corr"] else None
        mse_ccm = S.median([m for m, _ in b["mse_cc"]])
        mse_ccc = S.median([c for _, c in b["mse_cc"]])
        skill_clim_corr, bat_clim_corr = skill_contre(mse_ccm, mse_ccc)
        # Le dénombrement se fait ICI, sur la référence, pas sur le
        # résultat : un skill nul parce que la référence manque et un
        # skill nul parce qu'elle est trop bonne sont deux choses, et
        # c'est la seconde qu'on veut voir grossir ou pas.
        if mse_r is not None and mse_r < SKILL_MIN_REF_MSE:
            sous_plancher[0] += 1
        if mse_cc is not None and mse_cc < SKILL_MIN_REF_MSE:
            sous_plancher[1] += 1
        ordered = sorted(values)
        row = {
            "as_of": as_of.strftime("%Y-%m-%d"), "zone_id": zid, "model": model,
            "lead_h": lead, "window_kind": window_kind, "regime": regime,
            "agg_level": level, "n_stations": len(b["st"]),
            "n_hours": b["n_hours"], "occurrences": len(values),
            "typical_err_kmh": _r(ci.median),
            # ── lot L9a (28/08/2026) : LE COMPAGNON WMO DU SCORE ──────
            # ⛔ POURQUOI ICI, COLLÉ À `typical_err_kmh`. Le standard WMO
            # exige le biais de VITESSE à côté de l'erreur vectorielle,
            # parce que l'erreur vectorielle les CONFOND : ‖V⃗p − V⃗o‖
            # vaut la même chose pour un modèle qui souffle 20 % trop
            # fort dans la bonne direction et pour un modèle juste en
            # force avec 12° d'écart de cap. Les deux se corrigent
            # autrement — le premier par une pente (lot S2), le second
            # pas du tout — et rien dans le score publié ne permettait
            # de les distinguer (audit §4.3, point 3 du « ce qui
            # manque »).
            #
            # `bias_ratio` = Σ(obs·prev)/Σ(prev²) par balise-jour
            # (`scoring.pente_moindres_carres`), MÉDIANÉ sur la case.
            # > 1 : le modèle SOUS-estime le vent ici. < 1 : il le
            # surestime. ⓘ La médiane d'un rapport n'a pas besoin d'être
            # prise en logarithme : la médiane commute avec toute
            # transformation monotone, donc med(r) = exp(med(log r)).
            # (Ce n'est PAS vrai de la moyenne — et c'est bien pour ça
            # que `prior_biais`, qui MOYENNE, le fait en log.)
            "bias_ratio": _r(S.median(b["bias_ratio"]), 3),
            # ⚠️ MOYENNE **CIRCULAIRE**, PAS MÉDIANE — voir le pavé de
            # `inference.circular_mean_deg`. Un écart de cap vit sur un
            # cercle : +179° et −179° décrivent le même désaccord et
            # leur médiane arithmétique vaut 0°, c'est-à-dire
            # « parfait ». C'est le seul champ de cette ligne qui ne
            # soit pas une médiane, et c'est pour ça qu'il le dit ici.
            "bias_dir_deg": _r(INF.circular_mean_deg(b["bias_dir"]), 1),
            # ⛔ LE DÉNOMINATEUR DE LA LIGNE PRÉCÉDENTE, ET IL EST
            # INDISPENSABLE (leçon `n_comparable` du lot L3 : publier un
            # numérateur seul, c'est publier un chiffre illisible).
            # `bias_ratio` repose sur ~toutes les `occurrences` de la
            # case ; `bias_dir_deg`, lui, ne repose que sur les
            # balise-jours où les DEUX côtés avaient une direction ET
            # plus de BIAS_MIN_WIND_KMH. Sur un site calme, ça peut être
            # une poignée sur deux cents — et l'écart de cap publié
            # serait alors celui des rares heures ventées, pas celui de
            # la case.
            "n_bias_dir": len(b["bias_dir"]),
            "worst_decile_kmh": _r(ordered[min(len(ordered) - 1,
                                               math.floor(len(ordered) * 0.9))])
            if len(ordered) >= 5 else None,
            "beats_persist": bat_persist,
            "skill": skill,
            "beats_clim": bat_clim,
            "skill_clim": skill_clim,
            # ── lot L9c : À CÔTÉ des deux autres, jamais à leur place ──
            # ⛔ `beats_persist` et `beats_clim` répondent à deux
            # questions de PILOTE (« mieux qu'hier ? », « mieux que
            # d'habitude ? ») ; `beats_comb` répond à une question de
            # MÉTHODE (« mieux que ce qu'on sait faire sans modèle ? »)
            # et c'est la plus dure des trois, par construction
            # (Murphy 1992 : la combinaison optimale domine chacune de
            # ses composantes). Un modèle peut battre les deux premières
            # et perdre celle-ci — c'est même le cas intéressant.
            # ⓘ Absent du fichier LÉGER, délibérément : la pastille
            # n'affiche pas de skill, et ces deux champs sur 8 180
            # lignes alourdiraient un objet servi à chaque ouverture de
            # fiche pour un chiffre de diagnostic.
            #
            # ⛔⛔ ET « PAR CONSTRUCTION » EST FAUX DEPUIS LE 31/08 —
            # LA DOMINANCE CI-DESSUS NE TIENT QUE SI LE MÉLANGE EST
            # CONVEXE DANS L'ESPACE OÙ L'ERREUR EST MESURÉE.
            # `combined_reference` mélange la force en scalaire et
            # `pair_error` mesure un vecteur : la borne de Jensen n'y
            # est tout simplement pas valable, et 568 lignes du 28/08
            # avaient `mse_comb > max(mse_persist, mse_clim)` — la
            # combinaison battue par CHACUNE de ses composantes, ce que
            # la phrase « domine par construction » interdit.
            # ⇒ `skill_comb`/`beats_comb` restent publiés (arbitrage de
            # Yann, 02/09) mais QUALIFIÉS : `meta.references_combinees`
            # du fichier dit sur quelle définition ils reposent et ce
            # qu'on sait d'elle. Publier sans la réserve, c'était laisser
            # 15 001 verdicts « bat la référence combinée » se lire comme
            # une propriété du modèle.
            "beats_comb": bat_comb,
            "skill_comb": skill_comb,
            # ── la seconde définition (02/09/2026) ────────────────────
            # ⛔ SOUS UN NOM NEUF, JAMAIS EN REMPLAÇANT L'AUTRE. Le
            # mélange fait dans l'espace de l'erreur (cf.
            # `INF.combined_reference_vec`) rend la borne de Jensen
            # valable — au prix d'une référence dont la force est
            # systématiquement ≤ celle de l'autre. Les deux se lisent
            # ENSEMBLE ou pas du tout : `skill_comb_vec` seul dirait
            # « meilleur skill », alors qu'il peut ne dire que
            # « référence plus faible ».
            "beats_comb_vec": bat_comb_vec,
            "skill_comb_vec": skill_comb_vec,
            # ⛔⛔ ET LES DEUX COMPTES AVEC EUX, PARCE QUE LES DEUX
            # COLONNES NE REPOSERONT PAS SUR LA MÊME MATIÈRE AVANT
            # QUINZE NUITS. `rolling15` est alimenté par
            # `model_verif_daily` (pas par le cache de rejeu) : les
            # lignes déjà en base n'ont pas `mse_comb_vec`, et il n'y a
            # AUCUN moyen de le leur donner — le rejeu ne lit pas la
            # climatologie, donc il ne sait recalculer ni l'une ni
            # l'autre des deux références. La colonne neuve se remplira
            # donc nuit après nuit, et pendant ce temps `skill_comb_vec`
            # reposera sur trois journées quand `skill_comb` en aura
            # quinze.
            # ⇒ Publier le second sans dire ça, c'est publier un
            # numérateur — le défaut que le lot L3 a fermé pour
            # `n_comparable`/`occurrences`, et que celui-ci refuse de
            # rouvrir dans sa propre colonne. Les deux comptes voyagent
            # donc avec les deux skills, et se lisent l'un contre
            # l'autre : `n_comb_vec` == `n_comb` dit « même matière » ;
            # `3` contre `15` dit que la comparaison n'est pas encore
            # posée.
            "n_comb": len(b["mse_cb"]),
            "n_comb_vec": len(trio_vec),
            # ── lot S2 : le corrigé, À CÔTÉ du brut, jamais à sa place ─
            # ⛔ Décision D intacte : `typical_err_kmh` reste LE score.
            # `n_corr` voyage avec, parce qu'une case peut publier son
            # brut sur 40 balise-jours et son corrigé sur 12 (les
            # balises dont l'antécédent n'a pas encore
            # `BIAIS_MIN_JOURS` journées), et comparer les deux
            # médianes sans le savoir serait comparer deux populations.
            "typical_err_kmh_corr": _r(corr_med),
            "beats_clim_corr": bat_clim_corr,
            "skill_clim_corr": skill_clim_corr,
            "n_corr": len(b["err_corr"]),
            "bias_n_days": _r(S.median(b["nd"]), 1) if b["nd"] else None,
            "ci_low": _r(ci.ci_low), "ci_high": _r(ci.ci_high),
            "rank": None, "rank_reason": None,
            # ── lot L3 (27/08/2026) : sur combien de balise-jours ce
            # modèle est-il COMPARABLE au premier de sa case ? ─────────
            # ⛔ Le complément indispensable de `occurrences`. Les rangs
            # 2..n sont un tri de `typical_err_kmh` calculé par chacun
            # SUR SA POPULATION (audit §2.5) : seule la marche du haut
            # est prouvée par un test apparié. Une case où un modèle
            # note 40 balise-jours et le premier 6 peut publier « 2ᵉ »
            # sans que rien ne dise que les deux chiffres ne portent pas
            # sur la même météo. `occurrences` seul ne le dit pas ;
            # `n_comparable` à côté le dit. Rempli par `_apply_rank`.
            "n_comparable": None,
            # ── colonnes du lot G ──
            # `err_sd` : dispersion des balise-jours de la case. Publiée
            # parce qu'elle est lisible en soi (« ce modèle est régulier
            # ici »), et parce que le rétrécissement du G3 en a besoin —
            # la déduire de la demi-largeur de l'IC marcherait quand
            # l'IC existe et donnerait `None` quand il manque,
            # c'est-à-dire précisément sur les cases maigres, celles qui
            # doivent emprunter le plus. Un estimateur qui se tait là où
            # il est le plus utile n'est pas un estimateur.
            "err_sd": _r(math.sqrt(INF.sample_variance(values))
                         if INF.sample_variance(values) is not None else None),
            "n_days": ci.n_days,
            "ci_kind": "block_day" if ci.reason == "ok" else None,
            "ci_reason": ci.reason,
            "block_days": ci.block_days,
            "pooled_err_kmh": None, "borrowed_weight": None,
        }
        rows.append(row)
        by_case[(zid, lead, level)].append(row)
        rows_by_case_model[(zid, lead, level)][model] = b["rows"]

    _apply_rank(by_case, rows_by_case_model)
    if n_doublons:
        print(f"  ⓘ {n_doublons} balise-jour(s) écarté(s) : seconde "
              f"inscription d'un capteur déjà noté (`{COL_DOUBLON}`, "
              f"lot L17) [{window_kind}/{regime}]")
    if sous_plancher[0] or sous_plancher[1]:
        print(f"  ⓘ skill nul sur {sous_plancher[0]} case(s) "
              f"(persistance) et {sous_plancher[1]} (climatologie) : "
              f"référence sous {SKILL_MIN_REF_MSE} (km/h)², soit une "
              f"erreur RMS < {math.sqrt(SKILL_MIN_REF_MSE):.0f} km/h — "
              f"le vent n'a pas bougé, la question n'a pas eu lieu "
              f"[{window_kind}/{regime}]")
    return rows


def rolling_scores(daily: list[dict], zone_of: dict[str, dict], as_of: datetime):
    """Le score « 15 jours glissants » du §8, depuis `model_verif_daily`.

    ⚠️ Le rééchantillonnage se fait par BLOCS DE JOURS CONSÉCUTIFS
    (lot G), et plus par balise-jour indépendante. La note précédente
    disait déjà qu'il ne fallait pas rééchantillonner à l'heure parce
    que deux heures consécutives ne sont pas indépendantes. C'était vrai
    et insuffisant : deux JOURNÉES consécutives ne le sont pas non plus,
    une situation synoptique durant environ trois jours. Un tirage
    i.i.d. sur les balise-jours fabriquait donc des intervalles trop
    étroits — mesuré sur données simulées à corrélation connue : 42 % de
    couverture réelle pour un intervalle annoncé à 95 % (cf.
    `test_inference.py`, section 4). C'est une fabrique de faux
    gagnants, pas une imprécision.
    """
    units = []
    for d in daily:
        r = dict(d)
        r["unit"] = f"{d['source']}:{d['station_id']}"
        units.append(r)
    return _case_rows(units, zone_of, as_of, "rolling15", "all",
                      MIN_STATIONS_ZONE)


def regime_scores(units: list[dict], as_of: datetime,
                  zone_of: dict[str, dict], kind_of: dict[str, str],
                  min_stations: int = 1):
    """Le score par régime du §16.1 — désormais depuis les BALISE-JOURS
    rejoués, et non plus depuis les accumulateurs.

    ⚠️ CE N'EST TOUJOURS PAS UNE FENÊTRE GLISSANTE, et c'est tout
    l'intérêt. « Les 15 derniers jours » mélange un flux de nord, deux
    jours de marin et trois jours de brise — la moyenne qui en sort
    n'est vraie aucun de ces jours. Ici on lit « les N dernières fois
    qu'on a eu CE régime ici », quelle que soit leur ancienneté ; la
    seule limite est la profondeur de l'archive rejouée.

    ⚠️ CE QUI A CHANGÉ AU LOT G, ET POURQUOI. Cette fonction lisait
    `model_character`, dont l'accumulateur ne porte que trois sommes.
    Elle publiait donc `worst_decile_kmh = None`, `ci_low = None`,
    `ci_high = None` et `skill = None` sur TOUTES ses lignes : 10 250
    sur 10 250, mesuré le 09/08. Ce n'était pas réparable dans
    l'accumulateur — un quantile demande la distribution, trois sommes
    ne la portent pas.

    Les accumulateurs ne disparaissent pas pour autant : ils restent la
    mémoire longue du CARACTÈRE (§15.4, « ce modèle sous-estime le vent
    fort dans cette vallée »), qui est une moyenne pondérée et qui, elle,
    tient parfaitement dans trois sommes. Ce sont deux questions
    différentes, et c'est de les avoir confondues que venait le trou.

    ⚠️ `min_stations` VAUT 1 ICI, à dessein. Le quorum du chemin régime
    est un nombre d'OCCURRENCES (`REGIME_MIN_OCCURRENCES`), appliqué au
    classement, pas un nombre de balises : une case fine peut n'avoir
    qu'une balise et beaucoup de journées de ce régime.
    """
    rows: list[dict] = []
    by_regime: dict[str, list[dict]] = defaultdict(list)
    for u in units:
        reg = u.get("regime")
        # « unknown » n'est pas un régime : une journée qu'on n'a pas su
        # classer ne doit pas être versée dans une case, surtout pas dans
        # la plus peuplée.
        if reg and reg != "unknown" and reg in S.REGIMES:
            by_regime[reg].append(u)
    for reg, us in sorted(by_regime.items()):
        rows += _case_rows(us, zone_of, as_of, "regime", reg,
                           min_stations, level_of=kind_of)
    return rows


def _duplicate_chain_excluded(rows: list[dict]) -> str | None:
    """Le modèle à ÉCARTER du classement d'une case (lot L2, 27/08/2026).

    ⛔ `meteofrance_arome_france_hd` (Open-Meteo) et `arome_r2` (nos
    tuiles `arome/sol` relues sur R2, lot S0.5) sont le MÊME modèle lu
    par deux chaînes — pas deux modèles. Décision de Yann (27/08) : au
    classement, une case n'en admet qu'UN — `AROME_HD_MODEL`
    prioritaire (la chaîne de référence, la plus ancienne), `AROME_R2_MODEL`
    écarté SEULEMENT quand les deux sont présents dans la MÊME case.
    Seul, `arome_r2` continue de concourir normalement — c'est le cas
    STRUCTUREL des balises hors Pioupiou que lui seul note (lot S0.5).

    ⓘ L'écarté garde toutes ses lignes et ses scores absolus
    (`typical_err_kmh`, `skill`, `beats_*`) : seul le rang lui est
    refusé. EN BASE les deux séries restent, pour le contrôle croisé
    du duel (lot L1, `duel.py`) qui a précisément besoin des deux pour
    mesurer l'écart de chaîne dans la durée.
    """
    present = {r["model"] for r in rows}
    if AROME_HD_MODEL in present and AROME_R2_MODEL in present:
        return AROME_R2_MODEL
    return None


#: Le motif propre à l'écarté d'une case à double chaîne AROME (lot L2,
#: 27/08/2026). ⛔ Comme `RANK_REASON_POPULATION_MIXTE`, il rejoint le
#: repli GÉNÉRIQUE de `_upsert_scores` (plus bas, `RANK_REASONS_STEP40`)
#: tant que le CHECK de `rank_reason` n'a pas été élargi côté base —
#: `.sql` préparé pour Yann (`supabase_step53_lot_l2_duplicate_chain.sql`),
#: jamais exécuté d'ici. Ce repli est GÉNÉRIQUE (`_upsert_scores` écrit
#: `null` pour TOUTE raison hors de l'ensemble connu, quelle qu'elle
#: soit) : aucune modification de `_upsert_scores` n'est donc
#: nécessaire pour que la nuit passe avant que le SQL soit joué.
RANK_REASON_DUPLICATE_CHAIN = "duplicate_chain"


#: ⛔ LOT L18 (30/08/2026) — UN SEUL AGRUME AU CLASSEMENT, ET C'EST LE
#: COMPOSITE. Décision de Yann : « il n'y a qu'un seul AGRUME, composé
#: d'AROME et d'AROME-PI ; on ne doit afficher que lui dans le scoring ».
#:
#: ⛔ POURQUOI IL FALLAIT UN SECOND MOT ET PAS `duplicate_chain`.
#: `arome_r2` et `meteofrance_arome_france_hd` sont le MÊME modèle lu
#: par deux chaînes : l'écart entre eux est du bruit de chaîne, et le
#: mot « doublon » est exact. `agrume` et `agrume_pi` ne sont PAS la
#: même chose lue deux fois — elles diffèrent par Δ (AROME-PI), et cet
#: écart est précisément ce que le duel apparié du L1 MESURE. Écrire
#: « duplicate_chain » sur le témoin dirait au lecteur que les deux
#: séries sont redondantes, ce qui est faux, et effacerait la seule
#: raison pour laquelle on les garde toutes les deux.
#: ⚠️ Comme `duplicate_chain` et `fdr`, ce motif n'est PAS dans le CHECK
#: de la base tant que `supabase_step61_lot_l18_agrume_unique.sql` n'a
#: pas été joué : il rejoint d'ici là le repli GÉNÉRIQUE d'`_upsert_scores`
#: (`RANK_REASONS_STEP40` / `RANK_REASONS_CORR_STEP52`), qui écrit
#: `null` en base pendant que le JSON publié garde la raison exacte.
RANK_REASON_SERIE_TEMOIN = "serie_temoin"


#: ⛔ LOT L10 (30/08/2026) — « NOTÉE, PAS CLASSÉE », et il fallait un
#: mot pour ça aussi. Les deux sous-séries de la classe courte ne sont
#: pas écartées parce qu'une autre série les remplace (`serie_temoin`),
#: ni parce qu'elles doublonnent une chaîne (`duplicate_chain`) : elles
#: sont écartées parce que LA QUESTION QU'ELLES POSENT N'EST PAS ENCORE
#: TRANCHÉE. Le tableau de fiabilité les compare pendant des semaines,
#: et le jour où le poids est choisi, la gagnante rejoint le classement
#: — ce motif disparaîtra de lui-même.
#: ⚠️ Réutiliser un des deux autres motifs aurait été plus court et
#: aurait menti sur les trois : « doublon », « témoin » et « en essai »
#: décrivent trois situations qu'un lecteur doit pouvoir distinguer.
RANK_REASON_SERIE_EN_ESSAI = "serie_en_essai"


def _agrume_temoin_excluded(rows: list[dict]) -> str | None:
    """L'AGRUME à écarter du classement d'une case (lot L18, 30/08/2026).

    ⛔ MESURÉ EN BASE AVANT D'ÉCRIRE UNE LIGNE (`as_of = 2026-08-30`) :
    `agrume` tenait **1 015 lignes, 9 rangs et UNE première place**,
    `agrume_pi` **869 lignes et 5 rangs**. Le tableau publiait donc DEUX
    AGRUME, et celui qui gagnait une case était l'AROME BRUT — le
    produit que l'écran ne sert à personne. `agrume_fcst.py` l'écrivait
    déjà en tête de fichier sans qu'on en tire la conséquence : « le
    score mesurait donc un produit qui n'est servi à personne ».

    ⛔ LA PRIORITÉ EST L'INVERSE DE CELLE DU L2, ET C'EST VOULU. Là-bas
    la chaîne la plus ANCIENNE garde le rang (`AROME_HD_MODEL`) : entre
    deux lectures du même modèle, l'ancienneté est le seul départage
    honnête. Ici l'ancienneté ne décide RIEN — le critère est « qui est
    le produit SERVI », et c'est le composite, né le 25/08. Le prix est
    réel et il est écrit : la fenêtre du composite ne portait que
    5 journées le 30/08 contre 15 au témoin, et elle n'est pleine qu'à
    l'as_of du 09/09/2026.

    ⓘ L'ÉCARTÉ GARDE TOUT SAUF LE RANG — ses lignes, `typical_err_kmh`,
    `skill`, `beats_*` — exactement comme `arome_r2` au L2. Le duel
    apparié du L1 (`duel.py`) a besoin des DEUX séries pour mesurer
    l'apport de Δ ; un témoin retiré de la base ne mesure plus rien.

    ⓘ SEUL, `agrume` CONTINUE DE CONCOURIR NORMALEMENT. Mesuré le
    30/08 : 146 cases ne portent que lui — la population du composite
    est un sous-ensemble strict de la sienne — et il n'y tenait aucun
    rang ce jour-là. La règle vaut quand même : elle est écrite pour
    les nuits suivantes, pas pour celle qu'on a sondée.
    """
    present = {r["model"] for r in rows}
    if AGRUME_MODEL in present and AGRUME_PI_MODEL in present:
        return AGRUME_MODEL
    return None


def _exclus_du_rang(rows: list[dict]) -> dict[str, str]:
    """Tous les modèles écartés du rang d'une case, motif par motif.

    ⛔ UN DICTIONNAIRE ET NON UNE VALEUR, parce qu'il y a désormais DEUX
    règles d'exclusion (L2 et L18) et qu'une même case peut parfaitement
    les déclencher toutes les deux : une case Pioupiou peut porter les
    deux chaînes AROME *et* les deux AGRUME. Rendre une seule valeur
    tairait la seconde exclusion sans que rien ne le signale — le podium
    reprendrait silencieusement un billet en trop, ce qui est exactement
    le défaut que le L2 a été écrit pour fermer.

    ⚠️ ET LES DEUX MOTIFS RESTENT DISTINCTS. Les fondre sous un mot
    unique (« doublon ») coûterait ce qui justifie chacun : l'un dit
    « la même prévision lue deux fois », l'autre « ce n'est pas le
    produit servi ». Ce ne sont pas les mêmes faits, et un lecteur qui
    les confond ne peut plus lire le duel du L1.
    """
    exclus: dict[str, str] = {}
    chaine = _duplicate_chain_excluded(rows)
    if chaine is not None:
        exclus[chaine] = RANK_REASON_DUPLICATE_CHAIN
    temoin = _agrume_temoin_excluded(rows)
    if temoin is not None:
        exclus[temoin] = RANK_REASON_SERIE_TEMOIN
    # ⛔ LOT L10 — les sous-séries en essai, TOUJOURS, sans condition de
    # présence d'une autre série. Les deux règles ci-dessus disent « pas
    # celle-ci PUISQUE celle-là est là » ; celle-ci dit « pas encore »,
    # et ça ne dépend de personne d'autre.
    # ⓘ LOT L11 : les trois sous-séries du quart d'heure rejoignent les
    # deux du L10 dans la même règle — dont le TÉMOIN `agrume_quart_w0`,
    # qui est de l'AROME interpolé, c'est-à-dire une valeur fabriquée.
    # Le classer contre le produit qu'il sert à juger n'aurait aucun
    # sens, et le publier au classement en aurait encore moins.
    # ⓘ LOT L19 : le mélange multi-modèle et son témoin uniforme sont
    # NOTÉS, PAS CLASSÉS, pour la même raison que les sous-séries du
    # L10 — la question (« le mélange bat-il le produit servi ? ») est
    # posée au duel L1, pas au classement. Décision de Yann du 04/09 :
    # « noté comme un modèle, sans rang ni écran ».
    for r in rows:
        if (r["model"] in MODELES_COURTS or r["model"] in MODELES_QUARTS
                or r["model"] in MX.MODELES_MELANGE):
            exclus[r["model"]] = RANK_REASON_SERIE_EN_ESSAI
    return exclus


#: Le motif d'un rang RETIRÉ par le contrôle de multiplicité (lot L3,
#: 27/08/2026). ⛔ Il ne dit PAS « les modèles se valent » et PAS « pas
#: assez de recul » : il dit que l'écart, réel et utile pris isolément,
#: n'a pas survécu au fait qu'on pose la même question à ~1 121 cases
#: chaque nuit. Comme `duplicate_chain`, il rejoint le repli générique
#: de `_upsert_scores` tant que le CHECK de `rank_reason` n'a pas été
#: élargi côté base (`.sql` préparé pour Yann, jamais joué d'ici).
RANK_REASON_FDR = "fdr"

#: Les deux clés PRIVÉES par lesquelles `_apply_rank` transmet à
#: `appliquer_fdr` la p-valeur de la case. ⛔ Elles ne doivent JAMAIS
#: atteindre le JSON publié (qui, lui, porte tout le reste sans filtre) :
#: `appliquer_fdr` les RETIRE des lignes, et c'est sa dernière
#: instruction. Le préfixe `_` n'est pas une protection, c'est un
#: signal — le retrait, lui, est bancé.
FDR_P_BRUT = "_fdr_p"
FDR_P_CORR = "_fdr_p_corr"


def _apply_rank(by_case: dict[tuple, list[dict]],
                rows_by_case_model: dict[tuple, dict[str, list[dict]]]):
    """Classe, ou refuse de classer — par TEST APPARIÉ (lot G2).

    ⚠️ `rank` NUL SUR TOUTES LES LIGNES est un résultat de première
    classe, et ce sera le cas le plus fréquent. Une colonne qui force un
    classement fabriquerait un gagnant là où il n'y en a pas — c'est le
    reproche fait au 🏆 du score actuel.

    ⚠️ UN SEUL MÉCANISME, PAS DEUX. Le verdict venait auparavant d'un
    écart relatif de 15 % sur l'erreur médiane, avec deux intervalles
    unaires publiés à côté — et un lecteur qui compare deux intervalles
    unaires croit faire un test sans en faire un. Le verdict vient
    maintenant de l'intervalle de la DIFFÉRENCE APPARIÉE, et l'écart
    relatif reste ce qu'il aurait toujours dû être : la question
    PRATIQUE (« est-ce que ça change une décision de vol »), distincte
    de la question statistique (« est-ce réel »). Il faut les deux.

    ⚠️ ET PAS DE REPLI. Quand la fenêtre est trop courte pour le test,
    on ne retombe pas sur l'écart relatif seul : ce serait remettre en
    service le mécanisme qu'on remplace, et publier sous le même nom
    `rank_reason` vaut alors
    `window_too_short`, et c'est la réponse honnête tant que l'archive
    ne porte que deux jours.

    ⛔ LOT L2 (27/08/2026) — UN SEUL AROME AU CLASSEMENT. Avant de
    construire les cases envoyées à `INF.rank_models`, le modèle que
    rend `_duplicate_chain_excluded` (`arome_r2`, quand
    `meteofrance_arome_france_hd` est aussi présent dans la case) est
    RETIRÉ de la compétition : ni « meilleur », ni « second », il ne
    peut donc plus prendre le second billet d'un podium qui n'est déjà
    QUE le sien (audit §2.2/PS2, +0,17 km/h médian de chaîne). Son rang
    est ensuite forcé à `None` avec `rank_reason = "duplicate_chain"`,
    EN PLUS de — jamais à la place de — la raison que le test rend pour
    les modèles admis. Ses scores absolus (`typical_err_kmh`, `skill`,
    `beats_*`) ne sont pas touchés : ils viennent de `_case_rows`, pas
    d'ici.

    ⛔ LOT L18 (30/08/2026) — UNE SECONDE EXCLUSION, MÊME MÉCANIQUE.
    `_exclus_du_rang` remplace l'appel direct à
    `_duplicate_chain_excluded` et rend un DICTIONNAIRE modèle → motif :
    une case peut porter les deux chaînes AROME *et* les deux AGRUME, et
    n'en écarter qu'un seul laisserait un billet de trop au podium. Le
    second motif est `serie_temoin` — `agrume` (AROME 10 m brut) écarté
    quand `agrume_pi` (le composite, le produit que l'écran SERT) est
    dans la même case. ⚠️ La priorité y est l'INVERSE du L2 : ce n'est
    pas la série la plus ANCIENNE qui garde le rang, c'est celle qui est
    SERVIE. La raison complète est dans `_agrume_temoin_excluded`.
    """
    for key, rows in by_case.items():
        exclus = _exclus_du_rang(rows)
        admis = [r for r in rows if r["model"] not in exclus]
        if not admis:
            # ⛔ LOT L10 — UNE CASE OÙ PLUS PERSONNE N'EST ADMIS, ET CE
            # N'EST PAS UN CAS TORDU : c'est le cas NORMAL de la classe
            # courte, dont les deux seules séries sont en essai. Sans ce
            # garde-fou, on demanderait à `rank_models` de classer une
            # liste VIDE — et ce qu'il en rendrait n'est pas une réponse
            # à une question posée. Les motifs d'exclusion sont déjà sur
            # les lignes (boucle plus bas) ; il n'y a rien d'autre à
            # écrire, et surtout pas une raison de classement inventée.
            for r in rows:
                r["rank"] = None
                r["rank_reason"] = exclus[r["model"]]
                r["rank_corr"] = None
                r["rank_reason_corr"] = exclus[r["model"]]
            continue
        cases = [{"model": r["model"], "typical_err_kmh": r["typical_err_kmh"],
                  "occurrences": r["occurrences"]} for r in admis]
        rbcm = rows_by_case_model.get(key, {})
        rbcm_admis = ({m: v for m, v in rbcm.items() if m not in exclus}
                      if exclus else rbcm)
        ranks, reason, verdict = INF.rank_models(cases, rbcm_admis)
        for r in admis:
            r["rank_reason"] = reason
            r["rank"] = ranks.get(r["model"])
        # ── lot L3 (a) : la p-valeur de la case, mise de côté ─────────
        # ⚠️ ELLE N'EST PAS UTILISÉE ICI, ET C'EST TOUT LE POINT. Le
        # contrôle de multiplicité ne peut pas se décider case par case :
        # il lui faut le TABLEAU de la nuit entière. `_apply_rank` est
        # appelé une fois par (fenêtre, régime) — il ne voit jamais plus
        # qu'un morceau. On dépose donc la p-valeur sur les lignes, et
        # `appliquer_fdr` tranche plus tard, quand tout est là.
        # ⓘ Déposée sur TOUTES les lignes admises (elle est la même pour
        # la case) plutôt que sur une seule : l'ordre des lignes n'est
        # garanti nulle part, et une case dont la p-valeur voyagerait sur
        # `rows[0]` serait le piège nº 8 une fois de plus.
        p_case = verdict.ci.p_value if (verdict is not None
                                        and verdict.ci is not None) else None
        for r in admis:
            r[FDR_P_BRUT] = p_case
        # ── lot L3 (b) : `n_comparable`, la population partagée ───────
        # La référence est le PREMIER de la case au sens de `rank_models`
        # (le plus petit `typical_err_kmh` parmi les admis qui passent le
        # quorum) — le même que celui qui reçoit le rang 1 quand un rang
        # est publié. Chaque ligne dit sur combien de balise-jours elle
        # partage la météo de ce premier-là.
        _poser_n_comparable(rows, rbcm, admis)
        # ⛔ APRÈS le test, jamais avant : la raison rendue par
        # `rank_models` vaut pour les ADMIS, et l'écarté porte la
        # sienne — EN PLUS d'elle, pas à sa place (même règle qu'au L2).
        for r in rows:
            motif = exclus.get(r["model"])
            if motif is not None:
                r["rank_reason"] = motif
                r["rank"] = None
        _apply_rank_corr(rows, rbcm, exclus)


def _jours_balises(rows_du_modele) -> set:
    """Les (jour, balise) où ce modèle porte une erreur vectorielle.

    ⚠️ `err_vec_med` FINIE, pas « la ligne existe ». C'est la MÊME
    condition que `INF.paired_differences`, et elle doit le rester : un
    `n_comparable` qui compterait des lignes vides annoncerait une
    population commune que le test, lui, n'a pas eue.
    """
    return {(r.get("day"), r.get("unit")) for r in (rows_du_modele or ())
            if S._finite(r.get("err_vec_med"))}


def _poser_n_comparable(rows: list[dict],
                        rows_by_model: dict[str, list[dict]],
                        admis: list[dict]) -> None:
    """Écrit `n_comparable` sur chaque ligne de la case (lot L3).

    ⭐ LA DÉFINITION, ET ELLE A ÉTÉ CHOISIE CONTRE UNE AUTRE. C'est
    l'INTERSECTION des balise-jours de TOUS les modèles admis et
    chiffrés de la case — le noyau commun — et non l'intersection avec
    le seul premier. Les deux étaient défendables ; celle-ci se lit,
    l'autre non. Avec le noyau commun, toutes les lignes admises portent
    le MÊME `n_comparable`, et le lecteur n'a qu'une comparaison à
    faire, ligne par ligne : `n_comparable` contre `occurrences`. Quand
    les deux coïncident, les rangs 2..n comparent bien la même météo ;
    quand `n_comparable` est plus petit, une part du chiffre de cette
    ligne repose sur des balise-jours que personne d'autre n'a vus, et
    le rang qui en découle mélange des populations (audit §2.5).
    Avec l'intersection au seul premier, la ligne du premier portait son
    propre total et n'informait que sur les autres.

    ⚠️ HOMONYME À NE PAS CONFONDRE : `stability_report` publie déjà un
    `n_comparable` dans `meta.stability` — c'est le nombre de CASES
    comparables entre deux fenêtres pour le tau de Kendall. Rien à voir
    avec celui-ci, qui est un nombre de BALISE-JOURS par ligne de score.
    Deux objets différents, deux endroits différents ; le nom vient de
    l'audit (§2.5, P5) et on le garde tel quel plutôt que d'en inventer
    un troisième.

    ⓘ La ligne ÉCARTÉE d'une double chaîne AROME reçoit sa valeur elle
    aussi, contre le même noyau : elle ne concourt pas, mais son chiffre
    est publié et se lit à côté des autres.
    """
    chiffres = [r for r in admis if r.get("typical_err_kmh") is not None]
    if not chiffres:
        return
    noyau = None
    for r in chiffres:
        j = _jours_balises(rows_by_model.get(r["model"]))
        noyau = j if noyau is None else (noyau & j)
    for r in rows:
        r["n_comparable"] = len(_jours_balises(rows_by_model.get(r["model"]))
                                & noyau)


#: Le motif de refus PROPRE au classement corrigé : la case mélange des
#: modèles corrigés et des modèles qui ne le sont pas.
#: ⛔ IL NE VOYAGE JAMAIS DANS `rank_reason` — seulement dans
#: `rank_reason_corr`, une colonne à part. Le CHECK de
#: `supabase_step40_lot_g.sql` porte sur la première, et lui ajouter une
#: valeur qu'il ne connaît pas ferait tomber une nuit entière.
#: ⓘ 27/08 : ce pavé renvoyait à un `_verifier_rank_reason` QUI N'EXISTE
#: PAS — le nom a changé sans que le commentaire suive. Le mécanisme
#: réel est `RANK_REASONS_STEP40` (plus bas) et le repli de
#: `_upsert_scores`, qui renvoie une fois avec la raison neuve à `null`
#: quand la base refuse EN NOMMANT sa contrainte. C'est LUI qu'une
#: raison neuve (`duplicate_chain` du lot L2, `fdr` du L3) doit
#: rejoindre. *Un renvoi vers un nom mort coûte une recherche à chaque
#: lecteur, et finit par en égarer un.*
RANK_REASON_POPULATION_MIXTE = "mixed_population"


def _apply_rank_corr(rows: list[dict],
                     rows_by_model: dict[str, list[dict]],
                     exclu: "str | dict[str, str] | None" = None) -> None:
    """Le MÊME test apparié, sur l'erreur corrigée du biais de site.

    ⭐ POURQUOI CETTE FONCTION EXISTE (25/08/2026). Depuis le S2 la
    colonne corrigée est publiée, et depuis le 25/08 l'écran sait s'en
    servir pour TRIER — mais pas pour AFFIRMER : `rank`/`rank_reason`
    sortaient du test joué sur le brut, et sur lui seul. Un classement
    corrigé restait donc muet, alors même qu'il change le premier dans
    70,6 % des cases (mesuré sur le fichier du 25/08). Cette fonction
    lui donne son propre verdict, avec le même appareil : différence
    appariée sur les mêmes balise-jours, bootstrap par blocs de jours,
    et les deux conditions « réel » ET « utile ».

    ⛔ LA POPULATION MIXTE EST REFUSÉE, ET C'EST LA RÈGLE CENTRALE. Si
    une seule ligne chiffrée de la case n'a pas de corrigé, on ne classe
    pas : ordonner un modèle rétréci contre un modèle qui ne l'est pas
    fabriquerait l'écart — l'interdit que le S2 s'impose mot pour mot
    (« seules les balise-jours qui portent LES DEUX colonnes sont
    comparées »). Mesuré le 25/08 : la moitié des cases sont dans ce
    cas, `arome_r2` n'ayant pas encore d'antécédent de biais.

    ⚠️ LE QUORUM SE COMPTE EN `n_corr`, PAS EN `occurrences`. Une case
    peut avoir 40 balise-jours notés et 6 corrigés ; passer le quorum
    sur les premiers pour tester les seconds classerait sur presque
    rien, en le disant nulle part.

    ⚠️ ET LE COÛT. Ce second passage ne tourne QUE sur les cases
    entièrement corrigées — 7,9 % d'entre elles le 25/08. Il croîtra
    avec la couverture du cache de rejeu, jusqu'à doubler au plus
    l'étape de classement (jamais la collecte, jamais le bootstrap des
    IC unaires, qui ne sont pas recalculés ici).

    ⛔ LOT L2 (27/08/2026) — MÊME ÉCARTÉ, MÊME RAISON, SUR CETTE COLONNE
    AUSSI. `exclu` est celui que `_apply_rank` a déjà calculé pour le
    brut (`_duplicate_chain_excluded`) : la MÊME case n'a pas le droit
    de dire « duplicate_chain » sur une colonne et « mixed_population »
    sur l'autre pour le MÊME modèle. Il est donc retiré du calcul AVANT
    le test de population mixte, jamais après — sa propre absence de
    corrigé (ou sa présence) ne doit pas décider si LES AUTRES peuvent
    être classés sur le corrigé.
    """
    # ⛔ LOT L18 — `exclu` accepte DEUX formes, et ce n'est pas une
    # complaisance : les bancs du L2 appellent cette fonction avec un
    # NOM DE MODÈLE (`J.AROME_R2_MODEL`) et doivent continuer à mesurer
    # exactement ce qu'ils mesuraient. Une chaîne vaut donc « écarté
    # pour `duplicate_chain` » ; un dictionnaire porte un motif par
    # modèle, ce que `_apply_rank` passe désormais.
    exclus = ({} if exclu is None
              else {exclu: RANK_REASON_DUPLICATE_CHAIN}
              if isinstance(exclu, str) else dict(exclu))
    admis = [r for r in rows if r["model"] not in exclus]
    chiffrees = [r for r in admis if r.get("typical_err_kmh") is not None]
    avec = [r for r in chiffrees if r.get("typical_err_kmh_corr") is not None]
    if not chiffrees or len(avec) != len(chiffrees):
        for r in admis:
            r["rank_corr"] = None
            r["rank_reason_corr"] = RANK_REASON_POPULATION_MIXTE
    else:
        cases = [{"model": r["model"],
                  "typical_err_kmh_corr": r["typical_err_kmh_corr"],
                  # `n_corr` peut manquer sur une ligne d'avant le S2 : son
                  # absence vaut zéro, donc sous le quorum, donc écartée —
                  # jamais un repli sur `occurrences`, qui compte autre chose.
                  "occurrences": r.get("n_corr") or 0} for r in chiffrees]
        rbm = ({m: v for m, v in rows_by_model.items() if m not in exclus}
               if exclus else rows_by_model)
        ranks, reason, verdict = INF.rank_models(
            cases, rbm,
            err_key="typical_err_kmh_corr", value_key="err_vec_med_corr")
        for r in admis:
            r["rank_reason_corr"] = reason
            r["rank_corr"] = ranks.get(r["model"])
        # ⛔ LOT L3 — UNE FAMILLE À PART, PAS LA MÊME QUE LE BRUT. Le
        # classement corrigé est un SECOND tableau publié, sur une autre
        # grandeur (`err_vec_med_corr`) : Benjamini-Hochberg s'y applique
        # pour la même raison, mais séparément. Les fondre ferait `m` le
        # double en comptant DEUX FOIS les mêmes données — la correction
        # deviendrait plus sévère sans qu'aucune répétition
        # supplémentaire ne le justifie. Contrôler le FDR table par
        # table est la lecture standard de « BH sur le tableau ».
        for r in admis:
            r[FDR_P_CORR] = (verdict.ci.p_value
                             if (verdict is not None
                                 and verdict.ci is not None) else None)
    for r in rows:
        motif = exclus.get(r["model"])
        if motif is not None:
            r["rank_corr"] = None
            r["rank_reason_corr"] = motif


def _cle_de_case(r: dict) -> tuple:
    """La case d'une ligne de score : zone × lead × fenêtre × régime ×
    échelon. C'est l'unité que `_apply_rank` classe, et donc l'unité
    qu'un contrôle de multiplicité doit compter — pas la LIGNE (une case
    de neuf modèles porte neuf lignes et n'a posé QU'UNE question).
    Confondre les deux ferait `m` neuf fois trop grand et tuerait tout.
    """
    return (r.get("zone_id"), r.get("lead_h"), r.get("window_kind"),
            r.get("regime"), r.get("agg_level"))


def appliquer_fdr(rows: list[dict], alpha: float = INF.ALPHA_FDR) -> dict:
    """Benjamini-Hochberg sur le TABLEAU de la nuit (lot L3, 27/08/2026).

    ⭐ LE DÉFAUT QU'ELLE FERME (audit §4.2, Wilks 2016). ~1 121 cases
    testées chaque nuit, aucun contrôle de la répétition : en régime
    permanent, environ 5 % des « gagnants » publiés seraient du bruit, et
    ils portaient jusqu'ici la MÊME phrase que les vrais (« un modèle se
    détache »). Un lecteur ne peut pas distinguer les deux ; le
    dispositif, lui, le peut — c'est le seul endroit du chantier où
    l'information existe.

    ⛔ ELLE DOIT VOIR LA NUIT ENTIÈRE, et c'est pourquoi elle vit ici et
    pas dans `_apply_rank`. `rolling_scores` et `regime_scores` classent
    chacun leur part ; la famille de tests, elle, est leur RÉUNION. Une
    correction appliquée deux fois sur deux moitiés ne contrôle pas le
    FDR de l'ensemble — elle le contrôle sur deux ensembles dont personne
    ne publie le tableau.

    ⚠️ ORDRE : AVANT `marquer_parties_manquantes`. Celle-ci ne requalifie
    que les rangs PUBLIÉS restés « ok » ; passer après elle laisserait
    échapper au contrôle exactement les cases d'une journée incomplète —
    celles qui ont le moins de raisons d'être crues.

    DEUX FAMILLES, deux corrections séparées : le brut (`rank`) et le
    corrigé (`rank_corr`) sont deux tableaux publiés, sur deux
    grandeurs — cf. le pavé de `_apply_rank_corr`.

    ⓘ Elle RETIRE les clés privées `FDR_P_*` en sortant : elles ont servi
    à transporter la p-valeur d'un bout à l'autre du run, et le JSON
    publié porte tout ce qui reste sur la ligne, sans filtre.

    Rend un rapport par famille : `m` (tests joués), `k` (survivants),
    `seuil`, `publies_avant`, `retrogrades`.
    """
    par_case: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        par_case[_cle_de_case(r)].append(r)

    rapport: dict[str, dict] = {}
    for famille, cle_p, cle_rank, cle_reason in (
            ("brut", FDR_P_BRUT, "rank", "rank_reason"),
            ("corrige", FDR_P_CORR, "rank_corr", "rank_reason_corr")):
        cles, ps = [], []
        for cle, lignes in par_case.items():
            # La p-valeur est la MÊME sur toutes les lignes admises de la
            # case ; on prend la première qui existe. Les lignes écartées
            # (`duplicate_chain`) ne l'ont pas — elles n'ont rien testé.
            p = next((l[cle_p] for l in lignes
                      if l.get(cle_p) is not None), None)
            if p is None:
                continue          # aucun test joué ici : hors famille
            cles.append(cle)
            ps.append(p)
        survivants, seuil, k = INF.benjamini_hochberg(ps, alpha)
        publies = retrogrades = 0
        for cle, vivant in zip(cles, survivants):
            lignes = par_case[cle]
            # ⚠️ « publiée » = la case a un rang, pas « la case a un p ».
            # `not_separable` et `tied` ONT un p (le test a eu lieu) et
            # n'ont rien affirmé : ils comptent dans `m`, jamais dans les
            # rétrogradations.
            if not any(l.get(cle_reason) == "ok" for l in lignes):
                continue
            publies += 1
            if vivant:
                continue
            retrogrades += 1
            for l in lignes:
                # ⛔ ON NE TOUCHE QUE LES LIGNES « ok ». La ligne écartée
                # d'une double chaîne AROME garde `duplicate_chain` : la
                # case dirait sinon que son AROME de secours a été retiré
                # par la multiplicité, ce qui est faux et effacerait au
                # passage le motif du lot L2.
                if l.get(cle_reason) == "ok":
                    l[cle_reason] = RANK_REASON_FDR
                    l[cle_rank] = None
        rapport[famille] = {"m": len(ps), "k": k, "seuil": seuil,
                            "publies_avant": publies,
                            "retrogrades": retrogrades,
                            "p_min": min(ps) if ps else None}

    for r in rows:
        r.pop(FDR_P_BRUT, None)
        r.pop(FDR_P_CORR, None)
    return rapport


#: La valeur que porte un rang publié sur une journée à laquelle il
#: manque une partie de collecte.
RANK_REASON_PARTIE_MANQUANTE = "partie_manquante"


def marquer_parties_manquantes(rows: list[dict], bilans: dict) -> int:
    """Qualifie les rangs PUBLIÉS quand une partie de collecte manque.

    ⛔ LA QUESTION QUE LE LOT S0.4 LAISSAIT OUVERTE, TRANCHÉE ICI.
    `_apply_rank` classe les modèles PRÉSENTS. Si la passe de surface a
    échoué, il en reste deux sur neuf, et il publie « 1ᵉʳ sur 2 » sans
    que rien ne dise que sept manquaient. Les deux issues instruites
    étaient : refuser de classer la journée, ou publier en le disant.

    ⇒ **On publie en le disant**, et la raison est celle du S0.4 : *un
    classement absent et un classement partiel se lisent pareil dans un
    écran, et le second au moins se dit.* Refuser de classer ferait
    disparaître la ligne — donc rendrait la nuit incomplète
    INDISTINGUABLE d'une nuit sous quorum, qui est le cas le plus
    fréquent et parfaitement normal.

    ⚠️ MAIS ON N'ÉCRASE QUE LES `ok`, ET C'EST LA MOITIÉ QUI COMPTE.
    `rank_reason` porte un verdict STATISTIQUE par case
    (`insufficient`, `window_too_short`, `not_separable`, `tied`,
    `too_few_pairs`, `single_model`). Le remplacer partout détruirait
    une information par case pour y mettre un fait par JOURNÉE — et sur
    ces cases-là il n'y a de toute façon aucun rang trompeur à
    qualifier, puisqu'il n'y a pas de rang du tout. On ne qualifie donc
    que ce qui, sans ça, mentirait : les rangs effectivement publiés.

    ⓘ LE FAIT PAR JOURNÉE, LUI, VA EN BASE, dans
    `model_verif_collect_part` — une table par (jour, flux), lisible
    telle quelle, qui porte le compte des parties et les modèles
    nommés. Les deux écritures sont complémentaires : celle-ci empêche
    un rang de mentir, celle-là permet au tableau de bord de dire
    pourquoi.

    Rend le nombre de lignes qualifiées.
    """
    incomplets = sorted(
        off for off, b in bilans.items()
        if b.get("etat") not in ("ok", "avant_partition"))
    if not incomplets:
        return 0
    n = 0
    for r in rows:
        if r.get("rank") is not None and r.get("rank_reason") == "ok":
            r["rank_reason"] = RANK_REASON_PARTIE_MANQUANTE
            n += 1
    return n


def collect_part_rows(day: datetime, bilans: dict) -> list[dict]:
    """Les lignes de `model_verif_collect_part` pour une journée notée.

    ⚠️ UNE LIGNE PAR (JOUR D'ÉMISSION, FLUX), pas par journée notée. Une
    nuit de notation lit TROIS journées d'émission (les trois offsets de
    `LEAD_BY_OFFSET`) : c'est chacune d'elles qui a pu perdre une
    partie, et les confondre ferait disparaître deux incidents sur
    trois. La clé primaire est donc `(day, flux)` où `day` est le jour
    D'ÉMISSION — le même que celui de la clé R2.
    """
    out = []
    for off, b in sorted(bilans.items()):
        emis = day - timedelta(days=off)
        out.append({
            "day": f"{emis:%Y-%m-%d}",
            "flux": b.get("flux", "fcst"),
            "parties_attendues": b.get("parties_attendues"),
            "parties_lues": b.get("parties_lues", 0),
            "modeles_manquants": list(b.get("modeles_manquants") or []),
            "etat": b.get("etat", "ok"),
        })
    return out


# ══════════════════════════════════════════════════════════════════
#  RÉTRÉCISSEMENT VERS LE PARENT (lot G3)
# ══════════════════════════════════════════════════════════════════

def apply_pooling(rows: list[dict], zones: list[dict]) -> int:
    """Rétrécit chaque case fine vers son parent, et publie l'emprunt.

    Le parent d'une zone est l'échelon SUIVANT de sa chaîne de repli —
    la même chaîne que celle qui sert déjà à agréger, donc aucune
    hiérarchie nouvelle à maintenir.

    ⚠️ LE QUORUM RESTE LE SEUIL D'AFFICHAGE (arbitrage du 09/08). Le
    pooling améliore l'ESTIMATION ; il ne fait apparaître aucune ligne
    qui n'existait pas. Le §16.3 parlait d'un « remplacement progressif
    du quorum sec » : un remplacement franc ferait apparaître des
    chiffres partout, y compris là où presque tout est emprunté au
    massif, c'est-à-dire ouvrirait la vanne au moment précis où l'on
    affirme la refermer.

    ⚠️ `borrowed_weight` EST PUBLIÉ À CÔTÉ DE CHAQUE CHIFFRE, et
    `typical_err_kmh` n'est PAS écrasé. Un score à 80 % emprunté au
    massif n'est pas un score de vallée : le remplacer en silence serait
    la même faute que le débiaisage silencieux du lot D. Le lecteur voit
    les deux et sait lequel il regarde.
    """
    parent_of: dict[str, str] = {}
    for z in zones:
        chain = fallback_chain(z)
        for i in range(len(chain) - 1):
            parent_of.setdefault(chain[i][0], chain[i + 1][0])

    par_famille: dict[tuple, dict[str, dict]] = defaultdict(dict)
    for r in rows:
        par_famille[(r["model"], r["lead_h"], r["window_kind"],
                     r["regime"])][r["zone_id"]] = r

    n = 0
    for famille in par_famille.values():
        # Fratries : les zones qui partagent le même parent.
        fratries: dict[str, list[dict]] = defaultdict(list)
        for zid, r in famille.items():
            p = parent_of.get(zid)
            if p and p in famille:
                fratries[p].append(r)
        for pid, enfants in fratries.items():
            parent = famille[pid]
            spread = [(e["typical_err_kmh"], e["occurrences"],
                       _within_var(e)) for e in enfants]
            tau2, sigma2 = INF.pooling_variances(
                [(v, k, s) for v, k, s in spread if v is not None and s is not None])
            for e in enfants:
                p = INF.pool_toward_parent(
                    e["typical_err_kmh"], e["occurrences"],
                    parent["typical_err_kmh"], tau2, sigma2)
                e["pooled_err_kmh"] = _r(p.value)
                e["borrowed_weight"] = _r(p.borrowed, 3)
                n += 1
    return n


# ══════════════════════════════════════════════════════════════════
#  CRITÈRE DE SORTIE (lot G5) — mesuré, pas décrété
# ══════════════════════════════════════════════════════════════════

def stability_report(units: list[dict], zone_of: dict[str, dict],
                     as_of: datetime, kind_of: dict[str, str],
                     half_days: int = ROLLING_DAYS) -> dict:
    """Les rangs tiennent-ils d'une période à la suivante ?

    C'est le chiffre qui devra décider, un jour, de sortir de l'atelier.
    Il n'est pas décrété : il se mesure, et il se mesure d'une façon
    précise.

    ⚠️ SUR DES FENÊTRES DISJOINTES, ET C'EST TOUT LE PIÈGE. La mesure
    naturelle — comparer la fenêtre glissante de 15 jours d'hier à celle
    d'aujourd'hui — est trompeuse : deux fenêtres glissantes décalées
    d'un jour partagent 14 jours sur 15. Leur accord serait proche de 1
    quoi qu'il arrive, et ce 1 dirait « les données sont les mêmes », pas
    « le classement est stable ». On coupe donc la fenêtre rejouée en
    deux moitiés SANS AUCUN JOUR COMMUN, et le rapport porte le nombre de
    jours partagés (0) pour que personne n'ait à le croire sur parole.

    ⚠️ Un `tau` élevé ne suffira pas à sortir de l'atelier : il dit que
    le classement se reproduit, pas qu'il est juste. Un détecteur
    systématiquement biaisé est parfaitement stable.
    """
    jours = sorted({u["day"] for u in units}, reverse=True)
    recents = set(jours[:half_days])
    anciens = set(jours[half_days:half_days * 2])
    if not anciens:
        return {"reason": "window_too_short", "shared_days": 0,
                "n_cases": 0, "n_comparable": 0,
                "kendall_tau": None, "top1_agreement": None,
                "covers": (f"{len(jours)} journées rejouées : il en faut "
                           f"{half_days * 2} pour comparer deux fenêtres "
                           f"disjointes de {half_days} jours")}

    def rangs(jeu: set[str]) -> dict[tuple, dict[str, int]]:
        rows = _case_rows([u for u in units if u["day"] in jeu],
                          zone_of, as_of, "rolling15", "all",
                          MIN_STATIONS_ZONE, level_of=kind_of, with_ci=False)
        out: dict[tuple, dict[str, int]] = defaultdict(dict)
        for r in rows:
            if r["rank"] is not None:
                out[(r["zone_id"], r["lead_h"])][r["model"]] = r["rank"]
        return out

    st = INF.rank_stability(rangs(recents), rangs(anciens), recents, anciens)
    return {"reason": st.reason, "shared_days": st.shared_days,
            "n_cases": st.n_cases, "n_comparable": st.n_comparable,
            "kendall_tau": _r(st.kendall_tau, 3),
            "top1_agreement": _r(st.top1_agreement, 3),
            "window_days": half_days, "covers": st.covers}


def _within_var(row: dict) -> float | None:
    """Variance interne d'une case — la dispersion de ses balise-jours.

    Lue directement dans `err_sd`, et non reconstituée depuis la
    demi-largeur de l'intervalle : l'intervalle manque exactement sur
    les cases maigres, qui sont celles qui doivent emprunter le plus.
    """
    sd = row.get("err_sd")
    return None if sd is None else float(sd) * float(sd)


# ══════════════════════════════════════════════════════════════════
#  S13.0 — LE FICHIER LÉGER ET LE RÉSUMÉ DES MANCHES (24/08/2026)
# ══════════════════════════════════════════════════════════════════
#
# ⛔ PRÉALABLE À LA PASTILLE CÔTÉ CARTE (S13.1+). `model_scores.json`
# pèse 26,9 Mo (mesuré le 23/08, lot S5 §3) — hors de question à
# l'ouverture d'un écran léger. `model_scores_light.json` publie le
# SOUS-ENSEMBLE exact dont une pastille a besoin : rien n'y est
# recalculé, chaque valeur est recopiée depuis la ligne du gros fichier
# (banc `test_score.py::test_light_est_un_sous_ensemble_exact`).

#: Les champs du verdict, et RIEN d'autre (prompt S13.0). L'ordre est
#: celui de la spec, pour qu'un diff de ce tuple se voie.
#: ⭐ LES TROIS CHAMPS DU S2 AJOUTÉS LE 25/08 — et ce qu'ils autorisent
#: EXACTEMENT, qui est moins que ce qu'on croit.
#:
#: L'écran léger (pastille, feuille « ici », Podium, Duels) ne portait
#: que `typical_err_kmh`, la colonne BRUTE. C'est elle qui fait remonter
#: les mailles larges — le S2 l'a mesuré (ECMWF 1ᵉʳ en brut, 5ᵉ en
#: corrigé au global), et l'écran n'avait pas de quoi le dire.
#:
#: ⛔ MAIS `rank`/`rank_reason` RESTENT CALCULÉS SUR LE BRUT. Le test
#: apparié (bootstrap par blocs de jours, `inference.py`) ne s'est jamais
#: rejoué sur `err_vec_med_corr`. Publier la colonne corrigée permet donc
#: de TRIER dessus, jamais d'AFFIRMER dessus : côté client, un classement
#: corrigé doit dire que le verdict, lui, porte sur le brut. Le jour où
#: le rang sera calculé sur la colonne corrigée, c'est ici qu'un
#: `rank_corr` viendra — et l'écran cessera d'avoir à le préciser.
#:
#: ⚠️ `bias_n_days` ET `n_corr` VOYAGENT AVEC, PAS DÉCORATIVEMENT : sans
#: eux, une case ne peut pas dire si son corrigé est mûr, et le lecteur
#: reprendrait à zéro le raisonnement du 25/08 (`arome_r2` : 1 008 lignes
#: notées, ZÉRO antécédent — donc des cases où la moitié des modèles est
#: corrigée et l'autre pas, où trier sur le corrigé comparerait deux
#: populations).
LIGHT_SCORE_FIELDS = (
    "zone_id", "agg_level", "lead_h", "model", "typical_err_kmh",
    "ci_low", "ci_high", "n_days", "n_hours", "rank", "rank_reason",
    "borrowed_weight",
    # ── lot L3 (27/08/2026) : la population partagée, ET son dénominateur ──
    # ⛔ Dans le LÉGER, pas seulement dans le gros fichier. C'est
    # l'écran léger (pastille, feuille « ici », Podium) qui montre les
    # rangs 2..n, donc lui qui a besoin de pouvoir dire sur quoi ils
    # reposent. Une colonne publiée dans le seul fichier lourd serait
    # une colonne que personne ne lit.
    #
    # ⚠️ ET `occurrences` ENTRE AVEC LUI, alors que le S13.0 l'avait
    # exclu exprès (« la pastille n'en a pas besoin »). C'est vrai de la
    # pastille et faux de ce couple-là : `n_comparable` SEUL ne veut
    # rien dire. « 90 balise-jours comparables » ne se lit que contre le
    # total de la ligne — 90 sur 90 dit « même population », 90 sur 180
    # dit « la moitié de ce chiffre vient de balises que personne
    # d'autre n'a vues ». Publier le premier sans le second, c'est
    # publier un numérateur.
    "n_comparable", "occurrences",
    # ── lot L9a (28/08/2026) : le compagnon WMO, DANS LE LÉGER ────────
    # ⛔ Dans le léger, et pas seulement dans le gros fichier, pour la
    # raison exacte du L3 : c'est l'écran LÉGER (pastille, feuille
    # « ici », Podium) qui affiche l'erreur d'un modèle. Un biais de
    # vitesse publié dans un fichier que cet écran ne lit pas serait un
    # compagnon que personne n'accompagne.
    #
    # ⚠️ ET `n_bias_dir` VOYAGE AVEC, même règle que `occurrences` avec
    # `n_comparable` : « le modèle est à −40° de cap ici » ne se lit pas
    # sans savoir si c'est mesuré sur 3 balise-jours ou sur 300.
    #
    # ⓘ PRIX MESURÉ (28/08, sur l'objet réel) : voir le journal du lot.
    # Trois champs sur 8 180 lignes — le seul poste de ce lot qui
    # alourdisse un fichier servi à chaque ouverture de fiche.
    "bias_ratio", "bias_dir_deg", "n_bias_dir",
    # ── lot S2, publiés dans le léger le 25/08 ──
    "typical_err_kmh_corr", "bias_n_days", "n_corr",
    # ── le verdict PROPRE à la colonne corrigée (25/08, `_apply_rank_corr`) ──
    # ⛔ Deux champs séparés, jamais fondus avec `rank`/`rank_reason` :
    # ce sont deux tests, sur deux grandeurs, et une case peut très bien
    # trancher sur l'une et pas sur l'autre.
    "rank_corr", "rank_reason_corr",
    # ── lot L16 (02/09/2026) : les mauvais jours, DANS LE LÉGER ─────────
    # ⛔ Même raison que L3 et L9a : c'est l'écran léger (le nouvel
    # atelier pilote ouvert depuis la coupe) qui répond à « et les
    # mauvais jours ? ». Un pire décile publié dans le seul fichier de
    # 27 Mo serait une carte que le téléphone d'un pilote ne charge
    # jamais. ⓘ Prix : un flottant par ligne, ~8 200 lignes.
    "worst_decile_kmh",
)


def light_score_rows(scores: list[dict]) -> list[dict]:
    """Le sous-ensemble EXACT de `scores` pour le fichier léger.

    Filtré à `window_kind == 'rolling15'` — la seule fenêtre qu'une
    pastille consulte (prompt S13 : « fenêtre rolling15 seule ») — et
    `variable == 'wind'` : aucune ligne `pres` n'y entre, même le jour
    où le S1 publiera la pression par zone (elle porte déjà `variable`
    explicitement sur chaque ligne, cf. plus bas dans `main()`).
    """
    out = []
    for r in scores:
        if r.get("window_kind") != "rolling15":
            continue
        if r.get("variable", "wind") != "wind":
            continue
        out.append({k: r.get(k) for k in LIGHT_SCORE_FIELDS})
    return out


def light_bascule_rows(ev_scores: list[dict]) -> list[dict]:
    """Résumé bascules par zone×modèle×lead, montées ET chutes ensemble.

    ⚠️ MÊME PÉRIMÈTRE QUE `BasculeColumn.tsx` (S4) : seuls `onset`
    (montée) et `drop` (chute) entrent ici. `ramp` et `breeze_yield`
    restent dans le gros fichier, pas dans le léger.

    ⚠️ `far` NUL ⟺ `hits + false_alarms == 0`, PAR CONSTRUCTION
    (`EV.score_events` divise par ce total pour rendre `far`) — ce
    n'est pas une coïncidence mesurée au S4 sur un fichier particulier,
    c'est la définition même du FAR. L'état « jamais annoncée » se
    dérive donc de `far is None`, et on revérifie quand même
    hits/false_alarms ici pour que le banc prouve l'équivalence plutôt
    que de la supposer.
    """
    by_key: dict[tuple, dict] = {}
    for r in ev_scores:
        if r["event_type"] not in ("onset", "drop"):
            continue
        key = (r["zone_id"], r["agg_level"], r["model"], r["lead_h"])
        row = by_key.setdefault(key, {
            "zone_id": r["zone_id"], "agg_level": r["agg_level"],
            "model": r["model"], "lead_h": r["lead_h"],
        })
        suffix = r["event_type"]  # "onset" | "drop"
        far_jamais_annoncee = (r["far"] is None
                               and r["hits"] + r["false_alarms"] == 0)
        row[f"pod_{suffix}"] = r["pod"]
        row[f"far_{suffix}"] = r["far"]
        row[f"far_{suffix}_etat"] = ("jamais_annoncee"
                                     if far_jamais_annoncee else None)
        row[f"n_{suffix}"] = r["n"]
    return list(by_key.values())


#: Où le compteur de « manches » range son état, sous `--out`. Un objet
#: JSON minuscule, relu et réécrit chaque nuit — même patron que
#: `tools/quota_openmeteo.py` (état local, pas une table Supabase : ce
#: sous-lot n'a aucun SQL à faire jouer par Yann).
ROUNDS_STATE_FILE = "rounds_wind_rolling15.json"


def update_rounds(root: pathlib.Path, day: datetime, scores: list[dict],
                  dry_run: bool = False) -> dict:
    """Fait avancer le compteur de « manches » (S13.0), et dit sa limite.

    ⛔⛔ CE N'EST PAS UN REJEU HISTORIQUE, ET C'EST UNE DÉCISION MESURÉE,
    PAS UN OUBLI. Le prompt demandait de vérifier CE QUE LE CACHE DE
    REJEU PERMET avant de promettre l'historique. Vérifié dans
    `inference.py` : `rank`/`rank_reason` viennent du test apparié par
    bloc, dont `MIN_BLOCK_DAYS = 3` — en dessous, il rend
    `window_too_short`, JAMAIS `ok`. Rejouer ce test sur la matière
    d'UNE SEULE journée du passé ne peut donc jamais produire de
    « manche gagnée » : ce n'est pas une limite du cache de rejeu
    (`REPLAY_SUBDIR`, qui ne sert de toute façon QUE le chemin régime,
    et ne porte aucune journée `wind`/`rolling15`), c'est une propriété
    du test statistique lui-même. Une vraie réponse rétroactive
    demanderait de rejouer une fenêtre glissante de 15 jours PAR JOUR
    du passé — environ 15× le coût d'une nuit de notation — hors
    périmètre de ce sous-lot.

    ⇒ **Le compteur démarre au déploiement, et le fichier publié le
    dit** (`rounds_since`) : chaque nuit où ce code tourne ajoute une
    observation par (zone, lead, modèle), à partir de son premier run.
    """
    path = root / ROUNDS_STATE_FILE
    state = {"since": day.strftime("%Y-%m-%d"), "nights": 0,
            "last_day": None, "wins": {}}
    if path.exists():
        try:
            lu = json.loads(path.read_text())
            if isinstance(lu, dict):
                state.update(lu)
        except (json.JSONDecodeError, OSError):
            pass
    if dry_run:
        # Lu, jamais écrit : un `--dry-run` sur le Mac ne doit pas faire
        # avancer le compteur de production.
        return state
    day_str = day.strftime("%Y-%m-%d")
    if state.get("last_day") == day_str:
        # Idempotent, même règle que le reste du job (cf. l'en-tête du
        # fichier) : rejouer la même journée ne compte pas deux fois.
        return state
    state["nights"] = state.get("nights", 0) + 1
    state["last_day"] = day_str
    wins = state.setdefault("wins", {})
    for r in scores:
        if r.get("window_kind") != "rolling15":
            continue
        if r.get("rank") == 1 and r.get("rank_reason") == "ok":
            key = f"{r['zone_id']}\x1f{r['lead_h']}\x1f{r['model']}"
            wins[key] = wins.get(key, 0) + 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, separators=(",", ":")))
    return state


def rounds_rows(state: dict) -> list[dict]:
    """Les lignes `rounds` du fichier léger, depuis l'état persisté."""
    out = []
    for key, wins in sorted(state.get("wins", {}).items()):
        zone_id, lead_h, model = key.split("\x1f")
        out.append({"zone_id": zone_id, "lead_h": int(lead_h),
                    "model": model, "wins": wins})
    return out


def _publish_light(st, scores: list[dict], ev_scores: list[dict],
                   rounds_state: dict, as_of: datetime, dry_run: bool,
                   duels: list[dict] | None = None,
                   temoin: dict | None = None):
    """Publie `model_scores_light.json` — le sous-ensemble pour la pastille.

    Même bucket, même clé stable, même cache court que
    `model_scores.json` (cf. `_publish`).

    ⚠️ AUCUNE RÈGLE CORS NEUVE À POSER — VÉRIFIÉ EN DIRECT LE 24/08, PAS
    SEULEMENT RAISONNÉ. Une règle CORS Cloudflare R2 se pose PAR BUCKET,
    jamais par objet : mesuré en interrogeant `pub-d8b18f1cf34c470dbb838
    ac4566311ba.r2.dev/model_scores_light.json` (la clé N'EXISTE PAS
    ENCORE) avec `Origin: https://balise-watch.vercel.app` — le bucket
    répond `404` ET porte quand même
    `Access-Control-Allow-Origin: https://balise-watch.vercel.app`,
    exactement comme `model_events.json`, qui existe. La règle mesurée
    au S4 (cette seule origine autorisée) couvre donc déjà toute clé
    future du bucket, y compris celle-ci, sans le moindre geste
    supplémentaire.
    """
    if st is None or dry_run:
        print("  ⓘ publication R2 (léger) sautée (pas de storage, ou dry-run)")
        return
    from storage import CACHE_REECRIT             # type: ignore
    body = json.dumps({
        "as_of": as_of.strftime("%Y-%m-%d"),
        "audience": "beta",
        "window_kind": "rolling15",
        "variable": "wind",
        "rounds_since": rounds_state.get("since"),
        "rounds_nights": rounds_state.get("nights"),
        "scores": light_score_rows(scores),
        "bascules": light_bascule_rows(ev_scores),
        "rounds": rounds_rows(rounds_state),
        # ⛔ LE DUEL VOYAGE ICI ET NULLE PART AILLEURS (lot L1). Il n'est
        # PAS un score de zone : ni `zone_id`, ni `rank`, ni `agg_level`.
        # Le fondre dans `scores` en ferait une colonne de classement au
        # premier écran qui les lit ensemble — et c'est exactement ce que
        # l'audit §2.4 interdit : le classement ne peut PAS trancher cette
        # question, c'est pour ça que le duel existe.
        "duels": list(duels or []),
        # ── lot L16 (02/09/2026) : LE TÉMOIN VOYAGE AVEC LE CORRIGÉ, ICI
        # AUSSI. Le léger publie `typical_err_kmh_corr` depuis le 25/08
        # sans son témoin placebo — c'est-à-dire exactement ce que le S2
        # interdisait pour le gros fichier (« qu'on ne puisse pas lire le
        # gain sans son témoin »). Même forme que `meta.bias_correction`
        # du gros fichier, réduite au seul champ que l'écran lit.
        "bias_correction": {"witness": temoin},
    }, separators=(",", ":")).encode("utf-8")
    st.put("model_scores_light.json", body, cache_control=CACHE_REECRIT)
    st.bilan()
    print(f"  → model_scores_light.json publié ({len(body) / 1024:.0f} Ko, "
          f"{len(gzip.compress(body)) / 1024:.0f} Ko gzippé)")


def _publish_murphy(st, par_modele: list[dict], par_balise: list[dict],
                    as_of: datetime, dry_run: bool):
    """Publie `model_murphy.json` — le diagnostic, PAS l'écran principal.

    ⛔ SON PROPRE OBJET, ET C'EST LE POINT. Le prompt du lot dit « une
    page/bloc de diagnostic, pas l'écran principal ». Trois raisons de
    ne pas le fondre dans les deux fichiers existants :

    1. La granularité n'est pas la même. `model_scores*.json` publient
       des CASES (zone × modèle × échéance) ; Murphy publie des
       BALISES. Les mettre côte à côte inviterait à les joindre, et une
       décomposition par balise n'est pas une propriété de sa zone.
    2. Le poids. Une ligne par (balise × modèle × échéance) sur ~1 250
       balises pèse plusieurs Mo — dans le fichier LÉGER, ce serait la
       fin du « léger » ; dans le gros, ce serait doubler un objet que
       l'écran charge à chaque ouverture de fiche.
    3. Personne ne le lit encore. Un objet séparé se sert à la demande,
       et le jour où un écran le lira, il ne paiera que lui.

    ⚠️ Même bucket, même clé stable, même cache court que les autres
    (cf. `_publish`) : aucune règle CORS neuve à poser — vérifié en
    direct au S13.0, la règle est POSÉE PAR BUCKET et couvre déjà toute
    clé future.
    """
    if st is None or dry_run:
        print("  ⓘ publication R2 (Murphy) sautée (pas de storage, ou dry-run)")
        return
    from storage import CACHE_REECRIT             # type: ignore
    body = json.dumps({
        "as_of": as_of.strftime("%Y-%m-%d"),
        "audience": "beta",
        "value_key": "speed_kmh",
        # ⛔ LA RÉFÉRENCE, ÉCRITE DANS L'EN-TÊTE **ET** SUR CHAQUE LIGNE.
        # `ss` n'est PAS `skill_clim` : l'identité de Murphy ne tient que
        # contre la climatologie d'ÉCHANTILLON (une constante), quand
        # `skill_clim` se mesure contre une climatologie HORAIRE, bien
        # plus dure. Un lecteur qui les comparerait conclurait que le
        # modèle s'est effondré ou envolé d'une colonne à l'autre.
        "ss_reference": MU.SS_REFERENCE,
        "identity": "ss = r2 - bc^2 - bs^2 (Murphy 1988, MWR 116:2417)",
        "min_pairs": MU.MURPHY_MIN_PAIRS,
        "min_days": MU.MURPHY_MIN_DAYS,
        "par_modele": par_modele,
        "par_balise": par_balise,
    }, separators=(",", ":")).encode("utf-8")
    st.put("model_murphy.json", body, cache_control=CACHE_REECRIT)
    st.bilan()
    print(f"  → model_murphy.json publié ({len(body) / 1024:.0f} Ko, "
          f"{len(gzip.compress(body)) / 1024:.0f} Ko gzippé)")


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def _purge_caractere(sb, today) -> None:
    """La purge des accumulateurs — comptée avant d'être lancée.

    Extraite de `main` pour être BANÇABLE : le geste tient en
    quatre lignes, mais c'est la branche « 0 ligne ⇒ on ne lance
    rien » qui doit être prouvée, et on ne prouve pas une branche
    enfouie dans un `main` de six étapes.
    """
    # ── LOT L13 (01/09/2026) — ON COMPTE AVANT DE SUPPRIMER ─────────
    # ⛔ CE QUE LA MESURE A DÉFAIT. L'audit tenait le HTTP 500 de
    # cette purge pour STRUCTUREL (« deux nuits d'affilée ⇒
    # structurel, pas transitoire »). Le journal du VPS, relu en
    # ENTIER le 01/09, dit autre chose : 500 les nuits des 26, 27 et
    # 29/08, RIEN les 28, 30, 31/08 ni le 01/09 — trois échecs sur
    # six runs complets, et plus un seul depuis le 30/08. Rejoué à
    # la main le 01/09 (même filtre, même clé, depuis le Mac), le
    # DELETE rend 204 en 1,3 s. C'est INTERMITTENT, et la cause
    # n'est donc PAS nommée : elle le sera à la prochaine
    # occurrence, par le corps d'erreur que `delete` lit désormais.
    #
    # ⓘ L'ARBITRAGE, ET POURQUOI PAS UN INDEX. Le filtre concerne
    # ZÉRO ligne (mesuré : `*/0`) et le restera jusqu'en mars 2027 —
    # la table a 25 jours pour une rétention de 180. Deux façons
    # d'empêcher le 500 : un index sur `last_day`, ou ne pas lancer
    # le DELETE. L'index se paierait sur CHAQUE écriture
    # d'accumulateur — 541 000 à 722 000 par nuit, mesurées dans le
    # journal — pour servir une requête par nuit qui ne supprime
    # rien. On le refuse. Le compte préalable, lui, coûte 3,0 s une
    # fois par nuit (mesuré sur 1 223 107 lignes) et n'a jamais
    # échoué.
    #
    # ⚠️ « JE NE SAIS PAS » N'EST PAS « ZÉRO ». Si le compte échoue
    # — ou en dry-run — il rend `None` et la purge PART quand même :
    # sauter une purge en silence serait pire que la voir échouer
    # bruyamment, puisque c'est exactement le silence qu'on répare.
    seuil_caractere = today - timedelta(days=RETENTION_CHARACTER_D)
    filtre_caractere = f"?last_day=lt.{seuil_caractere:%Y-%m-%d}"
    vieux_caractere = sb.compte("model_character", filtre_caractere)
    if vieux_caractere == 0:
        print(f"  ⓘ purge model_character : aucune ligne plus vieille "
              f"que {seuil_caractere:%Y-%m-%d} (rétention "
              f"{RETENTION_CHARACTER_D} j) — DELETE non lancé.")
    else:
        sb.delete("model_character", filtre_caractere)


#: Colonne → fichier `.sql` qui l'AJOUTE, par table (lot L13,
#: 01/09/2026).
#:
#: ⛔ POURQUOI CETTE TABLE EXISTE. Avant elle, `_pour_la_base` DÉDUISAIT
#: le nom du fichier par une cascade de sets qui finissait sur un
#: `else: step40`. Un `else` n'est pas une connaissance : c'est un
#: repli, et un repli qui NOMME un fichier précis se lit comme une
#: consigne. L'audit §2.5 l'a payé — « rejouer supabase_step40_lot_g.sql
#: » pour `rank_corr`, une colonne qu'aucun fichier ne portait encore.
#: Une table ne peut pas faire cette faute : ou bien la colonne y est,
#: ou bien la réponse est « migration à écrire ».
#:
#: ⚠️ EXTRAITE DES FICHIERS EUX-MÊMES, PAS ÉCRITE DE MÉMOIRE. Relevé le
#: 01/09/2026 sur `PWA/web/supabase_step*.sql`, en lisant chaque
#: `alter table … add column` et la table qu'il vise :
#:
#:     grep -inE 'alter table|add column' PWA/web/supabase_step*.sql
#:
#: ⓘ CE QUI N'Y EST PAS, ET POURQUOI. Les colonnes NÉES avec leur table
#: (`step35` pour les trois tables de vérification, `step41` pour
#: `model_verif_daily_pres`) n'y figurent pas, et c'est VOLONTAIRE :
#: `step35` est un `create table if not exists`, donc le rejouer
#: n'ajouterait rien à une table déjà là. Si la base servait un jour
#: une de ces tables SANS une de ses colonnes d'origine, la bonne
#: réponse serait « migration à écrire » — exactement ce que rend le
#: troisième cas. Les steps 42, 53, 58, 61, 62 et 63 n'y figurent pas —
#: ils n'ajoutent AUCUNE colonne, ils élargissent des CHECK ; le
#: mécanisme qui les nomme est ailleurs (`REPLIS_RANG`), et il ne peut
#: pas être fusionné ici : PostgREST ne dit jamais QUELLE valeur sa
#: contrainte a refusée, donc rien ne s'y déduit d'une colonne.
#:
#: ⚠️ À TENIR À JOUR AVEC CHAQUE `.sql` QUI AJOUTE UNE COLONNE. Oublier
#: une entrée ne casse rien et ne ment pas : la colonne tombe dans le
#: cas « migration À ÉCRIRE », qui dit « je ne sais pas » — bruyant,
#: mais vrai. C'est le sens du troisième cas.
_SQL_PAR_COLONNE: dict[str, dict[str, str]] = {
    "model_score_zone": {
        # supabase_step40_lot_g.sql (07/08) — lot G
        "n_days": "supabase_step40_lot_g.sql",
        "ci_kind": "supabase_step40_lot_g.sql",
        "ci_reason": "supabase_step40_lot_g.sql",
        "block_days": "supabase_step40_lot_g.sql",
        "err_sd": "supabase_step40_lot_g.sql",
        "pooled_err_kmh": "supabase_step40_lot_g.sql",
        "borrowed_weight": "supabase_step40_lot_g.sql",
        "skill_clim": "supabase_step40_lot_g.sql",
        "beats_clim": "supabase_step40_lot_g.sql",
        # supabase_step49_lot_s2_biais_corrige.sql — lot S2
        "typical_err_kmh_corr": "supabase_step49_lot_s2_biais_corrige.sql",
        "beats_clim_corr": "supabase_step49_lot_s2_biais_corrige.sql",
        "skill_clim_corr": "supabase_step49_lot_s2_biais_corrige.sql",
        "n_corr": "supabase_step49_lot_s2_biais_corrige.sql",
        "bias_n_days": "supabase_step49_lot_s2_biais_corrige.sql",
        # supabase_step52_rank_corr.sql — le classement corrigé
        "rank_corr": "supabase_step52_rank_corr.sql",
        "rank_reason_corr": "supabase_step52_rank_corr.sql",
        # supabase_step54_lot_l3_fdr.sql — lot L3
        "n_comparable": "supabase_step54_lot_l3_fdr.sql",
        # supabase_step57_lot_l9_compagnons.sql — lot L9
        "bias_ratio": "supabase_step57_lot_l9_compagnons.sql",
        "bias_dir_deg": "supabase_step57_lot_l9_compagnons.sql",
        "n_bias_dir": "supabase_step57_lot_l9_compagnons.sql",
        "skill_comb": "supabase_step57_lot_l9_compagnons.sql",
        "beats_comb": "supabase_step57_lot_l9_compagnons.sql",
        # supabase_step65_lot_l9c_melange_vectoriel.sql — lot L9(c), 02/09
        "skill_comb_vec": "supabase_step65_lot_l9c_melange_vectoriel.sql",
        "beats_comb_vec": "supabase_step65_lot_l9c_melange_vectoriel.sql",
        "n_comb": "supabase_step65_lot_l9c_melange_vectoriel.sql",
        "n_comb_vec": "supabase_step65_lot_l9c_melange_vectoriel.sql",
    },
    "model_verif_daily": {
        "mse_clim": "supabase_step40_lot_g.sql",
        "bias_slope": "supabase_step49_lot_s2_biais_corrige.sql",
        "err_vec_med_corr": "supabase_step49_lot_s2_biais_corrige.sql",
        "mse_model_corr": "supabase_step49_lot_s2_biais_corrige.sql",
        "bias_n_days": "supabase_step49_lot_s2_biais_corrige.sql",
        "mse_comb": "supabase_step57_lot_l9_compagnons.sql",
        "mse_model_comb": "supabase_step57_lot_l9_compagnons.sql",
        # supabase_step69_lot_l19_melange_biais_fin.sql — lot L19, 04/09
        "err_vec_med_corr_fin": "supabase_step69_lot_l19_melange_biais_fin.sql",
        "mse_model_corr_fin": "supabase_step69_lot_l19_melange_biais_fin.sql",
        "bias_fin_niveau": "supabase_step69_lot_l19_melange_biais_fin.sql",
        "bias_fin_n_days": "supabase_step69_lot_l19_melange_biais_fin.sql",
        "spread_kmh": "supabase_step69_lot_l19_melange_biais_fin.sql",
        "mix_n_models": "supabase_step69_lot_l19_melange_biais_fin.sql",
        # ⓘ Pas de `mse_model_comb_vec` : les deux définitions vivent sur
        # les mêmes heures, donc le MSE du modèle est le MÊME. Une
        # seconde colonne aurait laissé croire à deux populations.
        "mse_comb_vec": "supabase_step65_lot_l9c_melange_vectoriel.sql",
    },
    # ⓘ `model_verif_daily_pres` naît complète au step41 et n'a jamais
    # reçu de colonne depuis. L'entrée VIDE est délibérée : elle dit
    # « cette table est connue, et rien n'y a été ajouté », ce qui n'est
    # pas la même chose qu'une table oubliée.
    "model_verif_daily_pres": {},
}


def _rang_step(fichier: str) -> int:
    """Le numéro d'un `supabase_stepNN_…sql`, pour les citer dans l'ordre."""
    chiffres = "".join(c for c in fichier[len("supabase_step"):] if c.isdigit())
    return int(chiffres) if chiffres else 0


def _sql_a_jouer(table: str, absentes, correspondance: dict | None = None) -> str:
    """La phrase qui dit QUOI JOUER pour les colonnes qui manquent.

    Trois cas, et c'est le TROISIÈME qui justifie la fonction :

      1. toutes les colonnes absentes sont portées par des `.sql`
         connus → on les nomme, groupées par fichier, dans l'ordre des
         steps ;
      2. plusieurs fichiers sont concernés → on les nomme TOUS, au lieu
         d'en élire un et de taire les autres (la cascade d'avant
         s'arrêtait au premier set qui mordait) ;
      3. ⛔ aucune correspondance → « migration À ÉCRIRE », en toutes
         lettres, et surtout AUCUN nom de fichier. C'est le cas de
         `rank_corr` avant que le step52 existe, et c'est précisément
         celui où l'ancien code envoyait rejouer le step40.

    ⓘ `correspondance` s'injecte pour le banc : il rejoue l'état du
    schéma d'AVANT un fichier donné, ce qu'on ne peut pas obtenir en
    retirant des lignes du dictionnaire réel.
    """
    corr = (_SQL_PAR_COLONNE if correspondance is None
            else correspondance).get(table, {})
    par_fichier: dict[str, list[str]] = {}
    orphelines: list[str] = []
    for col in absentes:
        fichier = corr.get(col)
        if fichier:
            par_fichier.setdefault(fichier, []).append(col)
        else:
            orphelines.append(col)
    bouts = []
    for fichier in sorted(par_fichier, key=_rang_step):
        bouts.append(f"Lancer {fichier} pour "
                     f"{', '.join(sorted(par_fichier[fichier]))}.")
    if orphelines:
        bouts.append(f"⛔ AUCUN .sql connu n'ajoute "
                     f"{', '.join(sorted(orphelines))} à {table} : "
                     f"migration À ÉCRIRE — ne rejouer aucun step "
                     f"existant, aucun ne porte cette colonne.")
    return " ".join(bouts)


def _pour_la_base(sb, table: str, rows: list[dict]) -> list[dict]:
    """N'envoie que les colonnes que la table sait recevoir.

    ⚠️ LE SQL NE S'EXÉCUTE JAMAIS DEPUIS ICI — c'est Yann qui le lance,
    quand il le lance. Entre le déploiement de ce code et l'exécution de
    `supabase_step40_lot_g.sql`, un run qui enverrait `pooled_err_kmh` ou
    `mse_clim` recevrait un `PGRST204 — column … does not exist` et la
    nuit serait perdue pour une colonne d'agrément.

    Le jour où le SQL est passé, les colonnes apparaissent d'elles-mêmes.
    Aucun drapeau à basculer, donc aucun drapeau à oublier — et c'est le
    point : un `SCHEMA_LOT_G = True` à changer à la main aurait été une
    seconde chose à ne pas oublier, le lendemain d'une nuit blanche.
    """
    if not rows:
        return rows
    # ⛔ LES CLÉS PRIVÉES SORTENT D'ABORD, ET INCONDITIONNELLEMENT
    # (lot L9b, 28/08). Une clé qui commence par `_` est un champ de
    # TRANSPORT — `_murphy`, les six sommes de la décomposition, qui
    # voyagent dans le CACHE DE REJEU et n'ont rien à faire en base
    # (même patron que les `_fdr_p` du lot L3, popés avant publication).
    #
    # ⚠️ AVANT le `if not cols`, et c'est tout l'intérêt de l'ordre.
    # `sb.columns()` peut rendre `None` (schéma illisible) : la fonction
    # renvoie alors les lignes TELLES QUELLES. Une clé qui n'est jamais
    # une colonne transformerait donc cette panne bénigne — un envoi
    # complet tenté au hasard — en `PGRST204` certain, toutes les nuits.
    # Le filtre du bas (`k in cols`) ne s'exécute pas sur ce chemin-là.
    #
    # ⓘ Et elles ne sont pas SIGNALÉES : imprimer « colonnes pas encore
    # en base : _murphy — lancer supabase_step… » enverrait Yann jouer
    # un SQL pour une donnée qui n'a pas à exister en base, chaque nuit,
    # pour toujours.
    if any(k.startswith("_") for k in rows[0]):
        rows = [{k: v for k, v in r.items() if not k.startswith("_")}
                for r in rows]
    cols = sb.columns(table)
    if not cols:
        return rows
    absentes = sorted(set(rows[0]) - cols)
    if not absentes:
        return rows
    # ⚠️ LE NOM DU `.sql` NE SE DÉDUIT PLUS, IL SE LIT (lot L13,
    # 01/09/2026). La version d'avant tranchait par une cascade de sets
    # — `_L9`, sinon `_L3`, sinon `_S2`, SINON step40 — et ce dernier
    # « sinon » était un mensonge par défaut : toute colonne inconnue
    # renvoyait vers `supabase_step40_lot_g.sql`, un fichier passé
    # depuis le 07/08. C'est ce qui a fait écrire « rejouer step40 »
    # pour `rank_corr` (audit §2.5) alors qu'AUCUN fichier ne portait
    # cette colonne : il fallait l'ÉCRIRE, et c'est devenu le step52.
    # Une journée perdue à rejouer un fichier idempotent qui ne pouvait
    # rien changer.
    print(f"  ⓘ {table} : colonnes pas encore en base, non envoyées — "
          f"{', '.join(absentes)}. {_sql_a_jouer(table, absentes)}")
    out = [{k: v for k, v in r.items() if k in cols} for r in rows]

    # ⚠️ ET LE CAS QUI NE SE VOIT PAS. `model_score_zone.rank_reason`
    # porte un CHECK écrit dans step35 :
    #
    #     check (rank_reason in ('ok','insufficient','tied'))
    #
    # Le lot G en ajoute trois (`window_too_short`, `not_separable`,
    # `too_few_pairs`) et la contrainte les REFUSE — ce n'est plus une
    # colonne manquante qu'on peut omettre, c'est tout l'envoi qui part
    # en HTTP 400. Tant que le SQL du lot G n'est pas passé, on écrit
    # donc `null` en base plutôt que de perdre la nuit ; le JSON publié,
    # lui, garde la vraie raison, et c'est lui que lit l'écran.
    if table == "model_score_zone" and "ci_reason" in absentes:
        historiques = {"ok", "insufficient", "tied", None}
        nouvelles = {r.get("rank_reason") for r in out} - historiques
        if nouvelles:
            print(f"     ⚠️ rank_reason : {', '.join(sorted(nouvelles))} "
                  f"refusé(s) par le CHECK de step35 → écrit `null` en base "
                  f"cette nuit. Le JSON publié garde la raison exacte.")
            for r in out:
                if r.get("rank_reason") not in historiques:
                    r["rank_reason"] = None
    return out


#: Les `rank_reason` que le CHECK de `supabase_step40_lot_g.sql` admet.
#: `single_model` (lot S0.5) n'y est PAS : il vient avec
#: `supabase_step42_lot_s05.sql`.
#:
#: ⚠️ CE SET EST DEVENU UN GROS FILET (constat du lot L3, 27/08/2026 —
#: le journal du L2 demandait de le signaler si L3 rouvrait ce fichier).
#: SIX valeurs vivent aujourd'hui hors de lui : `single_model`
#: (step42), `partie_manquante` (step48), `duplicate_chain` (step53),
#: `fdr` (step54), `serie_temoin` (step61, lot L18) et `serie_en_essai`
#: (step62, lot L10). ⚠️ Les deux dernières ont beau être JOUÉES, elles
#: ne rejoignent pas ce set : voir `single_model`, joué depuis le step42
#: et absent d'ici lui aussi. Ce set est la BASELINE du step40, pas
#: l'état du schéma. Le repli de `_upsert_scores` ne se déclenche que si
#: la base nomme SA contrainte `rank_reason` — donc jamais pour une
#: raison sans rapport — mais quand il se déclenche, il met à `null`
#: les QUATRE, y compris celles que la base accepte parfaitement. On
#: perd alors plus d'information que le refus n'en concernait.
#: ⓘ Ce n'est pas réparable ici : PostgREST ne dit pas QUELLE valeur sa
#: contrainte a refusée. Le vrai correctif est celui de la dette nº 2 du
#: lot L13 — une table « colonne/valeur → fichier SQL » tenue à jour,
#: qui saurait dire quelles migrations sont jouées. À NE PAS bricoler en
#: attendant : élargir ce set à l'aveugle ferait tomber la nuit entière
#: le jour où l'une des quatre est vraiment refusée, ce qui est
#: exactement le contraire de ce que le repli existe pour éviter.
RANK_REASONS_STEP40 = {"ok", "insufficient", "tied", "not_separable",
                       "window_too_short", "too_few_pairs", None}

#: ⛔ LE SECOND CHECK, CELUI DU CLASSEMENT CORRIGÉ — et il a coûté une
#: nuit de plus que l'OOM. `supabase_step52_rank_corr.sql` admet, pour
#: `rank_reason_corr`, les raisons du step40, plus `single_model`
#: (step42) et `mixed_population`, qui lui est propre. NI
#: `duplicate_chain` (lot L2), NI `fdr` (lot L3), NI `serie_temoin`
#: (lot L18), NI `serie_en_essai` (lot L10) n'y sont — et les quatre
#: lots ÉCRIVENT pourtant dans cette colonne (`_apply_rank_corr` pose
#: `duplicate_chain` sur l'écarté, `appliquer_fdr` pose `fdr` sur la
#: famille « corrige »).
#:
#: ⚠️ MESURÉ LE 28/08, EN REJOUANT LA NUIT DU 27 : la base répond
#: `23514` en nommant `model_score_zone_rank_reason_corr_check`, et
#: c'est l'upsert ENTIER de `model_score_zone` qui tombe — donc LA
#: NUIT, pas la colonne. Le repli d'`_upsert_scores` ne regardait que
#: le CHECK de `rank_reason` : il a laissé passer l'autre et re-levé.
#: ⓘ Le pavé de `RANK_REASON_POPULATION_MIXTE` annonçait déjà que
#: `duplicate_chain` et `fdr` devaient « rejoindre ce repli ». Ils y
#: sont maintenant — des deux côtés.
RANK_REASONS_CORR_STEP52 = (RANK_REASONS_STEP40
                            | {"single_model", "mixed_population"})

#: Les deux CHECK de raison de `model_score_zone`, et de quoi désarmer
#: chacun : (nom de la contrainte, colonne à taire, raisons admises,
#: `.sql` à jouer pour que le repli redevienne inerte).
REPLIS_RANG = (
    ("model_score_zone_rank_reason_check", "rank_reason",
     RANK_REASONS_STEP40,
     "supabase_step42_lot_s05.sql (`single_model`), "
     "supabase_step48_lot_s06_collect_part.sql (`partie_manquante`), "
     "supabase_step53_lot_l2_duplicate_chain.sql (`duplicate_chain`), "
     "supabase_step54_lot_l3_fdr.sql (`fdr`) et/ou "
     "supabase_step61_lot_l18_agrume_unique.sql (`serie_temoin`) "
     "et/ou supabase_step62_lot_l10_classe_courte.sql "
     "(`serie_en_essai`, plus les deux `lead_h` négatifs)"),
    ("model_score_zone_rank_reason_corr_check", "rank_reason_corr",
     RANK_REASONS_CORR_STEP52,
     "supabase_step58_rank_reason_corr.sql "
     "(`duplicate_chain` et `fdr` sur la colonne CORRIGÉE) et/ou "
     "supabase_step61_lot_l18_agrume_unique.sql (`serie_temoin`, "
     "sur les DEUX colonnes) et/ou "
     "supabase_step62_lot_l10_classe_courte.sql (`serie_en_essai`)"),
)


#: Le CHECK que la classe courte franchit — et le `.sql` qui le désarme.
#: ⛔ POURQUOI CE REPLI EXISTE, ET IL A DEUX PRÉCÉDENTS EXACTS. Le lot G
#: a ajouté trois `rank_reason` que le CHECK refusait ; le lot L2 en a
#: ajouté un de plus dans la colonne CORRIGÉE. Les deux fois, un HTTP 400
#: sur un upsert a fait perdre LA NUIT ENTIÈRE — pas la colonne, la nuit.
#: Le lot L10 ajoute deux `lead_h` NÉGATIFS, et cette fois ce n'est même
#: pas une colonne annexe : `lead_h` est dans la CLÉ PRIMAIRE de
#: `model_verif_daily`.
#:
#: ⛔⛔ ET C'EST POURQUOI CE REPLI-CI ÉCARTE DES LIGNES AU LIEU DE TAIRE
#: UNE COLONNE. Le repli de `_upsert_scores` met la valeur refusée à
#: `null` ; ici c'est impossible — `lead_h` est `not null` et fait partie
#: de la clé. On ÉCARTE donc les lignes de la classe courte, et on
#: envoie les autres. Le prix est nommé : cette nuit-là, la classe
#: courte n'existe pas. C'est le bon prix — elle est en essai, les trois
#: classes d'échéance sont le produit.
REPLI_LEAD_DAILY = (
    "model_verif_daily_lead_h_check", "lead_h",
    "supabase_step62_lot_l10_classe_courte.sql (les deux `lead_h` "
    "négatifs de la classe courte) puis "
    "supabase_step63_lot_l11_classe_quart.sql (les deux du quart "
    "d'heure)")


REPLI_LEAD_SCORES = (
    "model_score_zone_lead_h_check", "lead_h",
    "supabase_step62_lot_l10_classe_courte.sql puis "
    "supabase_step63_lot_l11_classe_quart.sql (le CHECK de "
    "`model_score_zone` y est élargi avec celui de `model_verif_daily`)")


def _upsert_daily(sb, rows: list[dict]) -> int:
    """`model_verif_daily`, avec un repli sur le CHECK de `lead_h`.

    ⚠️ LES ÉCHÉANCES ADMISES SE LISENT SUR `LEAD_BY_OFFSET`, pas sur une
    liste recopiée : le jour où une quatrième classe d'horizon naîtra,
    elle sera admise ici sans que personne ait à y penser, et les seules
    lignes écartées resteront celles qui déclarent une échéance que la
    base ne connaît pas.
    """
    cle = "day,source,station_id,model,lead_h,fcst_src"
    try:
        return sb.upsert("model_verif_daily", rows, cle)
    except Abort as exc:
        nom, colonne, quoi_jouer = REPLI_LEAD_DAILY
        if nom not in str(exc):
            raise
        admises = set(LEAD_BY_OFFSET.values())
        gardees = [r for r in rows if r.get(colonne) in admises]
        refusees = sorted({str(r.get(colonne)) for r in rows
                           if r.get(colonne) not in admises})
        print(f"  ⚠️ {colonne} : {', '.join(refusees)} refusé(s) par le "
              f"CHECK en base → {len(rows) - len(gardees)} ligne(s) "
              f"ÉCARTÉE(S) cette nuit (la clé primaire porte `lead_h`, "
              f"on ne peut pas le taire). Jouer {quoi_jouer}.",
              file=sys.stderr)
        if not gardees:
            raise
        return sb.upsert("model_verif_daily", gardees, cle)


def _upsert_scores(sb, rows: list[dict]) -> int:
    """`model_score_zone`, avec un repli sur le CHECK de `rank_reason`.

    ⛔ POURQUOI CE REPLI EXISTE, ET IL A UN PRÉCÉDENT EXACT. Le lot G a
    ajouté trois valeurs à `rank_reason` ; le CHECK de step35 les
    refusait, et un HTTP 400 sur `model_score_zone` fait perdre LA NUIT
    ENTIÈRE — pas la colonne, la nuit. Le contournement d'alors
    (`_pour_la_base`, ci-dessus) devinait l'état du schéma par une
    colonne absente : un proxy, qui ne marche que pour ce lot-là.

    Le lot S0.5 ajoute `single_model` et n'ajoute AUCUNE colonne : il
    n'y a plus de proxy à lire. On fait donc la seule chose qui ne
    suppose rien — on envoie, et si la base refuse EN NOMMANT sa
    contrainte, on renvoie une fois avec la raison neuve mise à `null`.
    Le JSON publié, lui, garde la vraie raison, et c'est lui que lit
    l'écran (même règle qu'au lot G).

    ⇒ La nuit passe même si `supabase_step42_lot_s05.sql` n'a pas
    encore été joué, et ce repli devient inerte le jour où il l'est —
    sans qu'il faille penser à retirer quoi que ce soit.

    ⛔ ET DEPUIS LE 28/08, LES DEUX COLONNES DE RAISON, PAS UNE. Ce
    repli ne regardait que `model_score_zone_rank_reason_check`. Or les
    lots L2 et L3 écrivent AUSSI dans `rank_reason_corr`
    (`duplicate_chain`, `fdr`), dont le CHECK est un AUTRE objet
    (`supabase_step52_rank_corr.sql`) qui ne les connaît pas. Mesuré en
    rejouant la nuit du 27/08 : la base a nommé
    `model_score_zone_rank_reason_corr_check`, le `if` ne l'a pas
    reconnu, et la nuit est tombée à la toute dernière étape — après
    vingt-trois minutes de calcul, `model_events.json` déjà publié et
    `model_score_zone` intact. *Un repli qui ne couvre qu'une des deux
    colonnes d'une même famille n'est pas un repli, c'est une chance.*
    """
    cle = "as_of,zone_id,model,lead_h,window_kind,regime"
    # ⛔ UNE BOUCLE, ET PAS UN SECOND `try` : les deux CHECK peuvent
    # refuser l'un APRÈS l'autre. Désarmer `rank_reason`, renvoyer, et
    # se faire refuser sur `rank_reason_corr` est EXACTEMENT le cas
    # réel du 28/08 — un seul repli aurait rendu la main au premier
    # tour en croyant avoir tout réparé.
    desarmes: set[str] = set()
    while True:
        try:
            return sb.upsert("model_score_zone", rows, cle)
        except Abort as exc:
            # ⛔ `nom not in desarmes` N'EST PAS UN DÉTAIL. Sans lui, une
            # contrainte déjà désarmée qui refuse ENCORE (parce qu'elle
            # porte sur autre chose que la raison) ferait BOUCLER le run
            # à l'infini — un run qui ne finit pas est pire qu'un run
            # qui échoue, parce que personne ne reçoit rien.
            # ── ⛔ (02/09) LE CHECK DE `lead_h`, symétrique de celui de
            # `_upsert_daily`. La vérification de cohérence des lots a
            # trouvé que ce repli n'existait que pour `model_verif_daily`
            # alors que `regime_scores` lit la fenêtre rejouée NON
            # filtrée des échéances négatives : entre le déploiement
            # d'une classe nouvelle et l'exécution de son `.sql`, la
            # nuit ENTIÈRE tombait ici, après 38 minutes de calcul. Les
            # cases écartées se comptent et se nomment ; la nuit passe.
            nom_lead, col_lead, quoi_lead = REPLI_LEAD_SCORES
            if nom_lead in str(exc) and nom_lead not in desarmes:
                desarmes.add(nom_lead)
                admises_lead = set(LEAD_BY_OFFSET.values())
                gardees = [r for r in rows if r.get(col_lead) in admises_lead]
                refusees = sorted({str(r.get(col_lead)) for r in rows
                                   if r.get(col_lead) not in admises_lead})
                print(f"  ⚠️ {col_lead} : {', '.join(refusees)} refusé(s) "
                      f"par le CHECK en base → {len(rows) - len(gardees)} "
                      f"case(s) ÉCARTÉE(S) cette nuit (la clé primaire "
                      f"porte `lead_h`, on ne peut pas le taire). Jouer "
                      f"{quoi_lead}.", file=sys.stderr)
                if not gardees:
                    raise
                rows = gardees
                continue
            repli = next((p for p in REPLIS_RANG
                          if p[0] in str(exc) and p[0] not in desarmes),
                         None)
            if repli is None:
                raise
            nom, colonne, admises, quoi_jouer = repli
            desarmes.add(nom)
            neuves = sorted(str(x) for x in {r.get(colonne) for r in rows}
                            if x not in admises)
            print(f"  ⚠️ {colonne} : {', '.join(neuves)} refusé(s) par le "
                  f"CHECK en base → écrit `null` cette nuit. Jouer "
                  f"{quoi_jouer}. Le JSON publié garde la raison exacte.",
                  file=sys.stderr)
            for r in rows:
                if r.get(colonne) not in admises:
                    r[colonne] = None


# ══════════════════════════════════════════════════════════════════
#  CONTRÔLE N°1 — L'INJECTION (`--self-test`), lot S3, 23/08/2026
# ══════════════════════════════════════════════════════════════════
#
#  ⛔ POURQUOI CE MODE EXISTE. Le 22/08, le chantier a payé DEUX FOIS
#  en une journée le prix d'un scoring qui se trompait sans rien lever :
#  `rank_models` publiait « 1ᵉʳ sur 1 » avec la mention « un vainqueur,
#  prouvé et utile », et écrire `aloft_*` volait le régime de 13 795
#  lignes par nuit. Aucun des deux n'aurait fait rougir quoi que ce
#  soit. Un scoring qui ne sait pas échouer publie ses fautes avec le
#  même aplomb que ses résultats.
#
#  DEUX ÉPREUVES, sur des données FABRIQUÉES EN MÉMOIRE :
#
#    (a) parfaite  — la prévision EST l'observation
#                  → `err_vec_med` = 0 et `skill` = 1
#    (b) permutée  — chaque balise reçoit la prévision d'une AUTRE
#                  → une erreur DU MÊME ORDRE QUE LA CLIMATOLOGIE
#
#  ⛔ CE MODE NE TOUCHE RIEN. Pas de base, pas de R2, pas d'Open-Meteo,
#  pas de `/var/lib/bw-quota/openmeteo.json`, pas de cache de rejeu. Il
#  n'ouvre aucun fichier et n'ouvre aucune socket : il fabrique ses
#  données et il appelle `daily_rows` et `skill_contre`, c'est-à-dire
#  exactement le chemin que la nuit empruntera trente secondes plus
#  tard. `main()` sort AVANT de construire `Supabase` et `_storage`.
#
#  ⚠️ CE QU'IL NE COUVRE PAS, ET IL FAUT LE DIRE : le régime, le biais
#  de site et sa colonne corrigée, les événements, la pression, les
#  zones, le rang. Il couvre l'appariement, l'erreur vectorielle et les
#  TROIS références (persistance, climatologie, et depuis le lot L9c la
#  COMBINAISON optimale de Murphy 1992) — c'est-à-dire le tronc dont
#  tout le reste dérive.
#
#  ⚠️ ET UNE ASYMÉTRIE CONNUE, QU'IL NE MASQUE PAS. `replay_day`
#  (l. ~1745) appelle `daily_rows` SANS climatologie : sur tout le
#  chemin RÉGIME, `mse_clim` est nul depuis le lot G1 (trouvé au lot S2,
#  non corrigé). ⚠️ **`mse_comb` HÉRITE EXACTEMENT DE CETTE ASYMÉTRIE**
#  (lot L9c, 28/08) : il demande la climatologie ET le poids `k`, que
#  `replay_day` ne passe pas davantage. Ce n'est donc PAS une régression
#  du lot L9 — c'est la même asymétrie, sur une colonne de plus, et la
#  réparer demanderait de faire lire la climatologie au rejeu (trente
#  journées × un cache par journée), c'est-à-dire un lot à soi.
#  ⇒ En pratique : `skill_comb` existe sur le chemin GLISSANT
#  (`rolling15`, alimenté par `model_verif_daily`, écrit chaque nuit
#  AVEC la climatologie) et reste nul sur le chemin RÉGIME.
#  Le self-test, lui, injecte une climatologie ET un poids fabriqués :
#  il vérifie donc `skill_clim` et `skill_comb` sur le chemin NOCTURNE,
#  celui de `main()`. Il ne prétend pas couvrir l'autre, et le dire ici
#  vaut mieux que de laisser croire que « self-test vert » veut dire
#  « les deux chemins sont bons ».

#: Balises fabriquées. 24 suffit à ce que la médiane de la population
#: ait un sens, et le run entier tient en moins d'une seconde — ce qui
#: compte, puisqu'il s'ajoute DEVANT une notation déjà longue.
SELF_TEST_STATIONS = 24

#: Graine de la permutation de l'épreuve (b). FIXE : un contrôle dont
#: le verdict change d'une nuit à l'autre sans que le code ait bougé
#: n'est pas un contrôle, c'est un tirage.
SELF_TEST_GRAINE = 0x5EED

#: L'épreuve (a) est ARITHMÉTIQUE, pas statistique : la prévision est
#: l'observation, donc l'erreur est nulle au bit près. La tolérance ne
#: couvre que l'arrondi de `_r` (4 décimales) et le flottant.
SELF_TEST_ZERO_KMH = 1e-6

#: ⭐ LA BORNE DE L'ÉPREUVE (b), ET ELLE EST MESURÉE — pas choisie.
#:
#: « Du même ordre que la climatologie » a été chiffré le 23/08/2026 en
#: rejouant la permutation sur UNE JOURNÉE RÉELLE ARCHIVÉE (2026-08-21,
#: 13 795 balise-jours, 10 modèles, 570 balises Pioupiou, lecture seule
#: sur `/var/lib/bw-model-verif` + R2, aucune écriture — script jetable
#: `/tmp/mesure_permutation.py`, à réécrire plutôt qu'à citer dans six
#: mois). Permutation de Sattolo, la même que celle du code ci-dessous.
#:
#:   échéance │ err_méd honnête │ err_méd permutée │ rms perm / rms clim
#:   ─────────┼─────────────────┼──────────────────┼────────────────────
#:    +6 h    │  5,410 km/h     │  7,784 (×1,44)   │      1,46
#:   +24 h    │  5,588 km/h     │  7,700 (×1,38)   │      1,45
#:   +48 h    │  5,857 km/h     │  7,351 (×1,26)   │      1,41
#:
#: ⭐ Et le chiffre qui donne son nom à l'épreuve : rapporté à la
#: PERSISTANCE, le permuté vaut 1,05 / 1,04 / 1,01. Une prévision tirée
#: au hasard entre balises est donc, en production, exactement aussi
#: mauvaise que « comme hier à la même heure », et 41 à 46 % pire que la
#: climatologie horaire.
#:
#: ⛔ POURQUOI 1,0 EN BAS ET NON 1,4. La borne doit tenir sur une
#: population FABRIQUÉE de 24 balises, pas sur 570 balises réelles : la
#: exiger à 1,4 reviendrait à ajuster la fixture jusqu'à ce qu'elle
#: reproduise un chiffre de production, c'est-à-dire à tester la
#: fixture. 1,0 dit la seule chose qui soit vraie des deux côtés — « une
#: prévision permutée n'est jamais MEILLEURE que la climatologie » — et
#: garde 41 % de marge sur le chiffre mesuré.
SELF_TEST_PERM_RATIO_CLIM_MIN = 1.0

#: ⛔ ET UNE BORNE HAUTE, parce qu'une tolérance ouverte d'un seul côté
#: laisse passer la moitié des pannes. Un facteur d'unité (m/s ↔ km/h,
#: ×3,6) ou une direction lue en radians feraient EXPLOSER l'erreur
#: permutée — et une explosion passe tous les seuils bas du monde.
#: 3,0 est au-dessus du 1,46 mesuré (facteur 2 de marge) et SOUS le
#: 3,6 d'une confusion d'unité : c'est la seule valeur qui attrape les
#: deux fautes.
#:
#: ⓘ CE QUE LA FIXTURE REND VRAIMENT : **2,198** (mesuré le 23/08/2026,
#: valeur DÉTERMINISTE — la fabrique ne tire rien au hasard). C'est plus
#: que les 1,41-1,46 de la production, et c'est normal : 24 balises
#: fabriquées aux régimes délibérément distincts se ressemblent moins
#: que 570 balises réelles d'un même massif, qui partagent le flux
#: synoptique. L'écart va dans le sens qui rend l'épreuve (b) PLUS
#: sévère, pas moins. Marges restantes : ×2,2 sous la borne haute,
#: ÷2,2 au-dessus de la borne basse.
SELF_TEST_PERM_RATIO_CLIM_MAX = 3.0


class _SelfTestIndisponible(Exception):
    """Le self-test n'a pas pu tourner — pour une raison à LUI.

    ⛔ CE N'EST PAS « LE SCORING EST FAUX », ET LES DEUX NE DOIVENT PAS
    RENDRE LE MÊME CODE. Un garde-fou qui tue la nuit pour sa propre
    panne — un import, une fixture, un chemin — est un garde-fou qu'on
    désarme au bout de trois faux positifs, et il aura alors coûté
    exactement ce qu'il devait éviter. Verdict faux ⇒ code 2, bloquant.
    Panne du contrôle ⇒ code 3, bruyant mais NON bloquant.
    """


def _self_test_cycle(i: int, heure: float, decalage_h: float = 0.0) -> float:
    """Le cycle diurne fabriqué de la balise `i`, en km/h.

    Une brise : un socle, une bosse par jour, une phase propre à chaque
    balise. Rien d'aléatoire — la fixture doit être la même à Paris et
    sur le VPS, cette nuit et dans six mois.
    """
    socle = 6.0 + 2.0 * (i % 4)
    amplitude = 8.0 + 2.0 * (i % 5)
    pointe = 11.0 + (i % 6) + decalage_h
    return socle + amplitude * (
        0.5 + 0.5 * math.cos(2 * math.pi * (heure - pointe) / 24.0))


def _self_test_direction(i: int) -> float:
    """La direction fabriquée de la balise `i`, en degrés.

    ⚠️ ÉTALÉE, MAIS PAS SUR TOUTE LA ROSE. Des balises voisines d'un
    même massif partagent le flux synoptique : leur direction varie de
    quelques dizaines de degrés, pas de 360. Étaler sur la rose entière
    gonflerait artificiellement l'erreur permutée et rendrait la borne
    haute de l'épreuve (b) inatteignable — on aurait mesuré la fixture.
    """
    return 200.0 + 12.0 * (i % 7) - 36.0


def _self_test_fabrique(n: int = SELF_TEST_STATIONS):
    """Une journée entière fabriquée : observations, prévisions, clim.

    ⭐ TROIS RELEVÉS PAR HEURE, GROUPÉS À ±4 MIN DE LA MARQUE HORAIRE, et
    ce détail EST le dispositif. `pair_series` apparie à ±20 min et
    `mean_wind` moyenne VECTORIELLEMENT ce qu'elle trouve dans la
    fenêtre : avec une cadence régulière de 4 min, la fenêtre de l'heure
    h attraperait la queue de l'heure h−1 et la moyenne ne vaudrait plus
    la valeur de l'heure h. L'épreuve (a) rendrait alors une erreur
    petite mais non nulle, et il faudrait une tolérance — c'est-à-dire
    qu'on mesurerait `mean_wind` au lieu de mesurer l'agrégat. Groupés,
    les trois relevés de l'heure h sont les SEULS dans sa fenêtre : la
    moyenne vaut la valeur de l'heure, exactement, et « 0 » veut dire 0.

    ⚠️ `utc_offset_s = 0` dans tout le self-test : l'heure locale de la
    climatologie est alors l'heure UTC, et la fixture n'a pas à porter
    un fuseau qui ne prouve rien.
    """
    jour = datetime(2026, 1, 15, tzinfo=timezone.utc)
    jour_ms = int(jour.timestamp()) * 1000

    def releves(d: datetime, decalage_h: float):
        """Les lignes d'observation d'une journée, une par balise."""
        base = int(d.timestamp())
        lignes = []
        for i in range(n):
            t, sp = [], []
            for h in range(24):
                for dt_s in (-240, 0, 240):
                    t.append(base + h * 3600 + dt_s)
                    sp.append(_self_test_cycle(i, h, decalage_h))
            lignes.append({
                "station_id": f"st{i:02d}", "source": "pioupiou",
                "lat": 45.0 + 0.01 * i, "lon": 6.0 + 0.01 * i,
                "t": t, "speed": sp, "gust": [None] * len(t),
                "dir": [_self_test_direction(i)] * len(t),
            })
        return lignes

    # ⚠️ LA VEILLE EST DÉCALÉE DE CINQ HEURES, et c'est ce qui donne à la
    # persistance une erreur non nulle. Sans ce décalage, « comme hier à
    # la même heure » serait PARFAIT, `mse_persist` tomberait sous
    # `SKILL_MIN_REF_MSE` et `skill_contre` rendrait `None` — l'épreuve
    # (a) ne pourrait alors rien affirmer sur le skill, et elle le
    # dirait au lieu de le contourner (cf. le contrôle plus bas).
    obs_day = releves(jour, 0.0)
    obs_prev = releves(jour - timedelta(days=1), 5.0)

    # Les prévisions : la valeur de l'heure, à l'heure pile. Émises à
    # 03:19 UTC comme `collect.py` le fait, sur 72 h comme un snapshot.
    snapshots: dict[int, list[dict]] = {}
    for offset in LEAD_BY_OFFSET:
        emis = jour - timedelta(days=offset)
        t0 = int(emis.timestamp())
        lignes = []
        for i in range(n):
            speeds = []
            for k in range(72):
                t = t0 + k * 3600
                # L'heure de la journée notée que ce pas recouvre — hors
                # de cette journée, la valeur ne sera jamais appariée.
                h = (t - int(jour.timestamp())) / 3600.0
                speeds.append(_self_test_cycle(i, h, 0.0))
            lignes.append({
                "station_id": f"st{i:02d}", "source": "pioupiou",
                "lat": 45.0 + 0.01 * i, "lon": 6.0 + 0.01 * i,
                "model": "modele_fabrique",
                "fetched_at": emis.replace(hour=3, minute=19).isoformat(),
                "t0": t0, "step_s": 3600,
                "speed": speeds, "dir": [_self_test_direction(i)] * 72,
                "gust": [None] * 72,
            })
        snapshots[offset] = lignes

    # La climatologie fabriquée : « le vent habituel ici à cette
    # heure-ci », pris comme la MOYENNE JOURNALIÈRE de la balise. C'est
    # volontairement une climatologie PLATE — elle ignore le cycle
    # diurne, donc elle se trompe, donc `mse_clim` n'est pas nul et
    # l'épreuve (b) a un dénominateur.
    clim = {}
    for i in range(n):
        moyenne = sum(_self_test_cycle(i, h, 0.0) for h in range(24)) / 24.0
        clim[f"pioupiou:st{i:02d}"] = {
            h: (moyenne, _self_test_direction(i), CLIM_MIN_DAYS)
            for h in range(24)}
    return jour, snapshots, obs_day, obs_prev, clim


def self_test_permuter(snapshots: dict[int, list[dict]],
                       graine: int = SELF_TEST_GRAINE):
    """Chaque balise reçoit la prévision d'une AUTRE, modèle par modèle.

    ⭐ SATTOLO, PAS FISHER-YATES. Le tirage `j < i` STRICTEMENT rend un
    cycle unique, donc AUCUN point fixe. Avec un mélange ordinaire, une
    balise sur `n` garderait sa propre prévision par hasard : l'épreuve
    (b) porterait un témoin secret, et la moyenne qu'elle mesure serait
    tirée vers le bas d'autant.

    ⚠️ `S._XorShift`, comme le demande le §S3 — le même générateur que
    le bootstrap, donc le même à Paris, sur le VPS et en TypeScript.
    """
    out: dict[int, list[dict]] = {}
    for offset, lignes in snapshots.items():
        par_modele: dict[str, list[dict]] = defaultdict(list)
        for r in lignes:
            par_modele[r["model"]].append(r)
        neuf: list[dict] = []
        for modele, lot in par_modele.items():
            n = len(lot)
            ordre = list(range(n))
            # ⛔ PAS `hash(modele)` : le hachage des chaînes est
            # randomisé par processus (`PYTHONHASHSEED`), et le verdict
            # d'un contrôle ne doit pas changer entre deux lancements.
            empreinte = 0
            for c in modele:
                empreinte = (empreinte * 131 + ord(c)) & 0xFFFF
            rnd = S._XorShift(graine ^ empreinte)
            for i in range(n - 1, 0, -1):
                j = min(i - 1, int(rnd.next() * i))
                ordre[i], ordre[j] = ordre[j], ordre[i]
            for i, r in enumerate(lot):
                donneur = lot[ordre[i]]
                copie = dict(r)
                copie["speed"] = donneur["speed"]
                copie["dir"] = donneur["dir"]
                neuf.append(copie)
        out[offset] = neuf
    return out


def _med(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else (xs[m - 1] + xs[m]) / 2.0


def self_test_epreuves(permuter=self_test_permuter, n=SELF_TEST_STATIONS,
                       injecter=None):
    """Joue les deux épreuves. Rend `(verdict_ok, lignes, mesures)`.

    ⚠️ `permuter` ET `injecter` SONT DES PARAMÈTRES, et ce n'est pas de
    la souplesse pour la souplesse : c'est ce qui permet au banc de
    fabriquer l'échec de CHAQUE épreuve séparément — une permutation qui
    n'en est pas une (l'identité) pour (b), une prévision légèrement
    biaisée pour (a) — et d'exiger que le verdict soit ROUGE. Un
    garde-fou dont on ne peut pas fabriquer l'échec ne se prouve pas ;
    et sans `injecter`, la tolérance de (a) était un mutant survivant —
    la mettre à 1 km/h ne changeait RIEN au banc, puisque l'erreur
    parfaite vaut exactement 0. Trouvé par la campagne de mutations du
    23/08, pas en relisant le code.
    """
    jour, snapshots, obs_day, obs_prev, clim = _self_test_fabrique(n)
    if injecter is not None:
        snapshots = injecter(snapshots)
    lignes: list[str] = []
    mesures: dict = {}
    ok = True

    def dire(bon: bool, texte: str):
        nonlocal ok
        ok = ok and bon
        lignes.append(("     ✅ " if bon else "     ❌ ") + texte)

    # ── (a) la prévision EST l'observation ────────────────────────
    # ⚠️ `poids_comb` FABRIQUÉ ICI (lot L9c) : un demi-poids pour chaque
    # balise de la fixture, de façon que le contrôle nocturne exerce
    # AUSSI la troisième référence. Sans lui, `mse_comb` sortirait nul
    # et le self-test le laisserait passer — un garde-fou qui ne
    # regarde pas une colonne neuve laisse croire qu'il la couvre.
    # ⓘ 0,5 et pas 1 ni 0 : les deux bornes du mélange sont vérifiées
    # au banc (`test_score.py`), le self-test, lui, veut un mélange qui
    # mélange vraiment.
    poids_st = {u: 0.5 for u in (clim or {})}
    honnete, _ = daily_rows(jour, snapshots, obs_day, obs_prev, 0, clim,
                            poids_comb=poids_st)
    if not honnete:
        raise _SelfTestIndisponible(
            "l'épreuve (a) n'a produit AUCUNE ligne : la fixture ne "
            "s'apparie pas elle-même, ce n'est pas un verdict sur le "
            "scoring")
    mesures["n_lignes"] = len(honnete)
    pire = max(r["err_vec_med"] for r in honnete)
    dire(pire <= SELF_TEST_ZERO_KMH,
         f"(a) prévision = observation → err_vec_med max = {pire:.6f} km/h "
         f"(attendu ≤ {SELF_TEST_ZERO_KMH})")
    mesures["err_max_parfaite"] = pire

    mse_persist = _med([r["mse_persist"] for r in honnete])
    mse_clim = _med([r["mse_clim"] for r in honnete])
    # ⛔ SI LA FIXTURE NE DONNE PAS DE RÉFÉRENCE UTILISABLE, C'EST LA
    # FIXTURE QUI EST EN CAUSE, PAS LE SCORING. On sort en `code 3` au
    # lieu d'affirmer quoi que ce soit sur un skill qui n'existe pas —
    # `skill_contre` rend `None` sous `SKILL_MIN_REF_MSE`, et un `None`
    # lu comme un échec accuserait le scoring d'une faute de la fixture.
    if mse_persist is None or mse_persist < SKILL_MIN_REF_MSE:
        raise _SelfTestIndisponible(
            f"la persistance fabriquée est trop bonne "
            f"(mse_persist = {mse_persist}) : sous SKILL_MIN_REF_MSE "
            f"({SKILL_MIN_REF_MSE}), `skill` sort à None par CONCEPTION "
            f"et l'épreuve (a) ne peut rien affirmer")
    if mse_clim is None or mse_clim < SKILL_MIN_REF_MSE:
        raise _SelfTestIndisponible(
            f"la climatologie fabriquée est trop bonne "
            f"(mse_clim = {mse_clim}) : l'épreuve (b) n'aurait pas de "
            f"dénominateur")

    mse_modele = _med([r["mse_model"] for r in honnete])
    skill, bat = skill_contre(mse_modele, mse_persist)
    dire(skill is not None and abs(skill - 1.0) <= SELF_TEST_ZERO_KMH and bat,
         f"(a) skill contre la persistance = {skill} (attendu 1, et "
         f"`beats_persist` vrai) — mse_modèle {mse_modele}, "
         f"mse_persist {mse_persist:.3f}")
    skill_c, bat_c = skill_contre(mse_modele, mse_clim)
    dire(skill_c is not None and abs(skill_c - 1.0) <= SELF_TEST_ZERO_KMH
         and bat_c,
         f"(a) skill contre la climatologie = {skill_c} (attendu 1) — "
         f"mse_clim {mse_clim:.3f}")
    # ── lot L9c : la troisième référence, dans le contrôle nocturne ───
    # ⛔ SUR SON PROPRE `mse_model_comb`, jamais sur `mse_modele`. Le
    # mélange n'existe qu'aux heures où les deux références existent :
    # y opposer le MSE du modèle calculé sur la population de la
    # persistance referait ici, dans le garde-fou lui-même, le défaut
    # §2.5.a que la colonne existe pour éviter.
    mse_comb = _med([r["mse_comb"] for r in honnete])
    mse_mod_comb = _med([r["mse_model_comb"] for r in honnete])
    if mse_comb is not None and mse_comb >= SKILL_MIN_REF_MSE:
        skill_cb, bat_cb = skill_contre(mse_mod_comb, mse_comb)
        dire(skill_cb is not None and abs(skill_cb - 1.0) <= SELF_TEST_ZERO_KMH
             and bat_cb,
             f"(a) skill contre la référence COMBINÉE = {skill_cb} "
             f"(attendu 1) — mse_comb {mse_comb:.3f}")
        mesures["mse_comb"] = mse_comb
    else:
        # ⓘ Pas une épreuve rouge : la fixture peut rendre un mélange
        # trop bon (les deux références y sont fabriquées). On le DIT au
        # lieu de le taire — un contrôle silencieux sur une colonne
        # neuve se lit comme un contrôle réussi.
        lignes.append(f"     ⓘ (a) référence combinée non éprouvée : "
                      f"mse_comb = {mse_comb} (sous SKILL_MIN_REF_MSE)")
    # ── la SECONDE définition, éprouvée par la même passe (02/09) ─────
    # ⛔⛔ ET C'EST ICI QUE LA DIFFÉRENCE ENTRE LES DEUX SE VOIT OU NE SE
    # VOIT PAS. Un contrôle qui n'éprouverait que `mse_comb` laisserait
    # la colonne neuve arriver en production sans qu'une seule passe
    # nocturne l'ait regardée — exactement ce que le lot LD reproche à
    # un vérificateur taillé dans le patron de ce qu'il vérifie.
    # ⓘ Les deux MSE sortent de la MÊME boucle et de la même population :
    # ils se comparent directement, et l'écart entre eux EST la mesure
    # que ce lot publie. On l'imprime, même quand il est nul.
    mse_comb_vec = _med([r.get("mse_comb_vec") for r in honnete
                         if r.get("mse_comb_vec") is not None])
    if mse_comb_vec is not None and mse_comb_vec >= SKILL_MIN_REF_MSE:
        skill_cv, bat_cv = skill_contre(mse_mod_comb, mse_comb_vec)
        dire(skill_cv is not None and abs(skill_cv - 1.0) <= SELF_TEST_ZERO_KMH
             and bat_cv,
             f"(a) skill contre la combinée VECTORIELLE = {skill_cv} "
             f"(attendu 1) — mse_comb_vec {mse_comb_vec:.3f}")
        mesures["mse_comb_vec"] = mse_comb_vec
    else:
        lignes.append(f"     ⓘ (a) combinée vectorielle non éprouvée : "
                      f"mse_comb_vec = {mse_comb_vec} "
                      f"(sous SKILL_MIN_REF_MSE)")
    if mse_comb is not None and mse_comb_vec is not None:
        # ⚠️ INÉGALITÉ TRIANGULAIRE, PAS UNE PRÉFÉRENCE. La force du
        # mélange vectoriel est ≤ celle du mélange scalaire dès que les
        # deux caps diffèrent ; ce que ça fait au MSE dépend de
        # l'observation et n'est PAS déterminé. On imprime donc l'écart
        # sans en faire une épreuve — le jour où il change de signe,
        # c'est une mesure, pas une panne.
        lignes.append(f"     ⓘ (a) écart des deux mélanges : "
                      f"mse_comb {mse_comb:.3f} contre mse_comb_vec "
                      f"{mse_comb_vec:.3f} "
                      f"({100 * (mse_comb_vec - mse_comb) / mse_comb:+.2f} %)")
    mesures["skill_parfait"] = skill
    mesures["skill_clim_parfait"] = skill_c

    # ── (b) la prévision d'une AUTRE balise ───────────────────────
    permute, _ = daily_rows(jour, permuter(snapshots, SELF_TEST_GRAINE),
                            obs_day, obs_prev, 0, clim)
    if len(permute) != len(honnete):
        raise _SelfTestIndisponible(
            f"la permutation a changé le NOMBRE de lignes "
            f"({len(permute)} contre {len(honnete)}) : elle a déplacé "
            f"autre chose que des séries, la comparaison n'a plus d'objet")
    mse_perm = _med([r["mse_model"] for r in permute])
    err_perm = _med([r["err_vec_med"] for r in permute])
    if mse_perm is None:
        raise _SelfTestIndisponible("aucun `mse_model` permuté mesurable")
    rapport = math.sqrt(mse_perm) / math.sqrt(mse_clim)
    mesures["err_med_permutee"] = err_perm
    mesures["rapport_perm_clim"] = rapport
    dire(SELF_TEST_PERM_RATIO_CLIM_MIN <= rapport
         <= SELF_TEST_PERM_RATIO_CLIM_MAX,
         f"(b) prévision permutée → rms(perm)/rms(clim) = {rapport:.3f} "
         f"(attendu entre {SELF_TEST_PERM_RATIO_CLIM_MIN} et "
         f"{SELF_TEST_PERM_RATIO_CLIM_MAX} ; mesuré 1,41 à 1,46 sur la "
         f"journée réelle du 21/08) — err_vec_med médiane "
         f"{err_perm:.3f} km/h")
    skill_p, bat_p = skill_contre(mse_perm, mse_persist)
    # ⭐ MESURÉ LE 23/08 SUR LE 21/08 RÉEL : le permuté vaut 1,01 à 1,05
    # fois la persistance en RMS, donc un skill LÉGÈREMENT NÉGATIF. Une
    # prévision tirée au hasard entre balises ne bat pas « comme hier à
    # la même heure » — et si elle le battait, ce serait le scoring qui
    # aurait un problème, pas la permutation.
    dire(skill_p is not None and skill_p <= 0.0 and bat_p is False,
         f"(b) prévision permutée → skill contre la persistance = "
         f"{skill_p} (attendu ≤ 0, `beats_persist` faux)")
    mesures["skill_permute"] = skill_p
    return ok, lignes, mesures


#: Le verdict du contrôle n°1, en codes de sortie. ⛔ LES TROIS SONT
#: DIFFÉRENTS EXPRÈS — cf. `_SelfTestIndisponible`.
SELF_TEST_OK = 0
SELF_TEST_FAUX = 2
SELF_TEST_INDISPONIBLE = 3


def self_test() -> int:
    """Le mode `--self-test`. Rend 0, 2 ou 3 — jamais autre chose."""
    print("▶ self-test du scoring (contrôle n°1, lot S3) — "
          "aucune lecture réelle, aucune écriture")
    try:
        ok, lignes, mesures = self_test_epreuves()
    except _SelfTestIndisponible as exc:
        print(f"  ⛔ SELF-TEST INDISPONIBLE : {exc}", file=sys.stderr)
        print(f"  ⚠️ Ce n'est PAS un verdict sur le scoring. La notation "
              f"peut continuer ; le contrôle, lui, est DÉSARMÉ tant que "
              f"ceci n'est pas réparé.", file=sys.stderr)
        return SELF_TEST_INDISPONIBLE
    except Exception as exc:                            # noqa: BLE001
        print(f"  ⛔ SELF-TEST INDISPONIBLE : {type(exc).__name__} — {exc}",
              file=sys.stderr)
        print("  ⚠️ Ce n'est PAS un verdict sur le scoring.", file=sys.stderr)
        return SELF_TEST_INDISPONIBLE
    for ligne in lignes:
        print(ligne)
    print(f"     ⓘ {mesures['n_lignes']} balise-jours fabriqués sur "
          f"{SELF_TEST_STATIONS} balises × {len(LEAD_BY_OFFSET)} échéances")
    if ok:
        print("  ✅ self-test VERT — le scoring distingue une prévision "
              "juste d'une prévision qui n'a rien à voir.")
        return SELF_TEST_OK
    print("  ⛔ SELF-TEST ROUGE — LE SCORING EST FAUX. Rien ne doit être "
          "écrit en base cette nuit.", file=sys.stderr)
    return SELF_TEST_FAUX


# ══════════════════════════════════════════════════════════════════
#  ⛔⛔ UN REJEU DE VIEILLE JOURNÉE NE REPUBLIE PAS LE CLASSEMENT
#      (lot LR, 01/09/2026 — trouvé par l'oracle du lot L12)
# ══════════════════════════════════════════════════════════════════

def doit_republier(day: datetime, as_of: datetime,
                   forcer: bool = False) -> bool:
    """Ce run a-t-il le droit de republier `model_score_zone` et les
    objets R2 ? Vrai seulement si la journée notée est HIER ou plus
    récente.

    ⛔ LE DÉFAUT, MESURÉ ET NON DÉDUIT. Deux faits de ce fichier se
    combinent mal :

      · `as_of = datetime.now(timezone.utc)` — TOUJOURS aujourd'hui,
        quel que soit `--day` ;
      · la fenêtre glissante est lue par `?day=gte.{day − 14}`, **sans
        borne haute**.

    Rejouer la journée J publie donc, sous l'étiquette `rolling15` et
    l'`as_of` du jour, une fenêtre de **15 + (hier − J) jours**. Un jour
    d'ancienneté = un jour de trop.

    ⛔ CE QUE ÇA COÛTE, MESURÉ SUR LA PRODUCTION LE 01/09 (sonde du lot
    L12, lecture seule, `model_verif_daily` relu deux fois) pour un
    `--day 2026-08-13` lancé le 01/09 — 25 jours au lieu de 15 :

      · 9 929 cases au lieu de 9 535, dont **394 QUI N'EXISTENT QUE
        GRÂCE À LA FENÊTRE LARGE**. ⛔ Celles-là ne partent JAMAIS : un
        run correctif derrière ne les efface pas, l'upsert est en
        `merge-duplicates` et ne supprime rien ;
      · 4 587 cases déplacées de plus de 0,01 km/h, **3 742 de plus de
        0,10**, jusqu'à 3,832 km/h ;
      · ⛔⛔ **290 premières places sur 1 984 changent de titulaire** —
        une case sur sept, sur l'écran que lisent les pilotes.

    ⚠️ ET LE PRÉCÉDENT AVAIT RAISON PAR CHANCE. Le lot L0a a rejoué le
    25/08 le 26/08 au soir : la base s'arrêtait alors à la veille, donc
    `gte(11/08)` sans borne haute rendait EXACTEMENT 15 jours. Rien
    n'avait été pensé pour ça — c'est la date qui était clémente.

    ⛔ CE QUE LE REJEU CONTINUE DE FAIRE, et c'est tout ce qu'on lui
    demande : combler `model_verif_daily` (la journée manquante),
    écrire son archive, et jouer le duel. Ce qu'il ne fait plus :
    `model_score_zone` (glissant ET régime), les scores d'événement,
    Murphy, le rapport de stabilité et les objets R2 — c'est-à-dire
    tout ce qui est CLÉÉ PAR `as_of` alors que la fenêtre, elle, finit
    à `day`.

    ⚠️ ET IL NE RETIRE RIEN AU PASSAGE. `model_character` est mis à jour
    par une RPC dont le `where p_day > mc.last_day` refuse déjà toute
    journée plus vieille que la dernière intégrée (lot S15) : la
    contribution d'un vieux rejeu aux accumulateurs était REJETÉE avant
    ce garde-fou comme après. Le garde-fou ne fait pas perdre cette
    donnée-là ; elle était déjà perdue, et c'est une réserve du lot L12,
    pas une conséquence de celui-ci.

    `forcer` (`--publier-quand-meme`) rouvre la porte. Un seul usage
    légitime connu : rejouer une nuit qui vient d'échouer alors que la
    date a déjà basculé — la fenêtre est alors trop large d'un jour, et
    c'est un arbitrage qu'on prend en connaissance de cause, pas par
    défaut.
    """
    if forcer:
        return True
    hier = (as_of - timedelta(days=1)).date()
    return day.date() >= hier


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="/var/lib/bw-model-verif")
    ap.add_argument("--day", default=None, help="journée à noter (défaut : hier)")
    ap.add_argument("--utc-offset-h", type=float, default=2.0,
                    help="décalage local des sites, pour la fenêtre volable "
                         "(défaut : 2 = heure d'été française)")
    ap.add_argument("--no-purge", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    # ⛔ LOT LR : la porte de sortie du garde-fou de `doit_republier`.
    # Nommee en toutes lettres pour qu'on ne la tape pas par reflexe.
    ap.add_argument("--publier-quand-meme", action="store_true",
                    help="republier model_score_zone et les objets R2 "
                         "MEME si la journee notee est plus vieille "
                         "qu'hier. Voir doit_republier() : la fenetre "
                         "publiee sera alors plus large que 15 jours, "
                         "sous l'etiquette rolling15")
    # ⛔ LE CONTRÔLE N°1 DU LOT S3 — cf. le pavé `--self-test` ci-dessus.
    # Il sort AVANT tout le reste : ni Supabase, ni R2, ni archive.
    ap.add_argument("--self-test", action="store_true",
                    help="joue les deux épreuves d'injection sur des "
                         "données fabriquées et sort : 0 vert, 2 SCORING "
                         "FAUX (bloquant), 3 contrôle indisponible")
    ap.add_argument("--regime-days", type=int, default=REGIME_REPLAY_DAYS,
                    help="profondeur du rejeu d'archive pour le chemin régime")
    ap.add_argument("--replay-budget", type=int, default=3,
                    help="journées JAMAIS rejouées qu'une nuit peut rattraper. "
                         "Borne la durée du run : rejouer trente journées d'un "
                         "coup peut la multiplier par trente.")
    args = ap.parse_args()

    # ⛔ AVANT TOUT LE RESTE, ET C'EST LA PROPRIÉTÉ QUI COMPTE. Le
    # self-test sort ici, donc AVANT `Supabase(...)` (qui exige
    # `SUPABASE_URL`/`SUPABASE_SERVICE_KEY`) et AVANT `_storage()` (qui
    # ouvre R2). Il peut donc se jouer sur un poste nu, sans un seul
    # secret et sans un octet de réseau — ce qui est exactement ce
    # qu'on veut d'un garde-fou qu'on rejoue à la main un soir de doute.
    if args.self_test:
        return self_test()

    root = pathlib.Path(args.out)
    # ⚠️ AUCUN DATETIME NAÏF NE SORT D'ICI, et c'est délibéré. Ce qui
    # tenait debout jusqu'ici ne tenait que par accident : `utcnow()`
    # rend l'heure UTC mais SANS le dire, et `day.replace(tzinfo=utc)`
    # plus bas ne fait que rattraper cette omission. Les deux lignes ne
    # sont d'accord que tant que personne ne remplace `utcnow()` par
    # `now()` — auquel cas `.timestamp()` lirait 22 h la veille comme
    # minuit UTC, et TOUS les appariements glisseraient de deux heures
    # sans qu'aucun test ne tombe. Un décalage silencieux, pas un plantage.
    #
    # `utcnow()` est par ailleurs déprécié depuis Python 3.12 et le VPS
    # tourne en 3.13 : on l'entend déjà, on ne l'a pas encore payé.
    day = (datetime.strptime(args.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
           if args.day
           else datetime.now(timezone.utc) - timedelta(days=1)).replace(
               hour=0, minute=0, second=0, microsecond=0)
    as_of = datetime.now(timezone.utc)
    # ⛔ LOT LR (01/09/2026) — voir `doit_republier` pour le pourquoi et
    # les chiffres. Décidé ICI, une seule fois, à côté des deux dates
    # dont il dépend : le calculer plus bas obligerait à retrouver `day`
    # et `as_of` au milieu de six cents lignes.
    republier = doit_republier(day, as_of, args.publier_quand_meme)
    utc_offset_s = int(args.utc_offset_h * 3600)

    try:
        sb = Supabase(dry_run=args.dry_run)
    except Abort as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    st = _storage()

    print(f"▶ journée notée : {day:%Y-%m-%d}")

    # ── 1. relire l'archive ───────────────────────────────────────
    snapshots = {}
    # ⛔ LE BILAN DES PARTIES, PAR JOURNÉE D'ÉMISSION (lot S0.6). Il se
    # rend et se journalise TROIS FOIS par nuit — une par offset — parce
    # que ce sont trois nuits de collecte différentes, dont chacune a pu
    # perdre une partie. Un bilan unique en aurait caché deux sur trois.
    bilans_parties = {}
    for offset in LEAD_BY_OFFSET:
        emis = day - timedelta(days=offset)
        rows, bilan = snapshot_rows_et_bilan(root, emis, st)
        snapshots[offset] = rows
        bilans_parties[offset] = bilan
        n_ag = sum(1 for r in rows if r.get("model") == AGRUME_MODEL)
        # ⛔ LA SÉRIE COMPOSITE SE COMPTE À PART (26/08). `agrume_pi`
        # arrive dans le MÊME flux qu'`agrume` et sa population est un
        # SOUS-ENSEMBLE de la sienne (les balises couvertes par PI).
        # Sans son propre compte, une chute de couverture PI — un
        # domaine perdu, une ingestion muette — se lirait comme un
        # simple flottement du total, ou ne se lirait pas du tout.
        n_pi = sum(1 for r in rows if r.get("model") == AGRUME_PI_MODEL)
        # ⓘ Lot L20 (04/09) : les lignes SŒURS +24 h (heures 24-47 lues
        # dans arome_r2) se déclarent ; sans ce compte, le message
        # ci-dessous continuerait d'annoncer « AUCUNE ligne » à un offset
        # qui en donne désormais.
        n_h24 = sum(1 for r in rows if r.get("agrume_h24_copie"))
        # ⚠️ Le compte AGRUME se dit à chaque offset, y compris quand il
        # est destiné à ne rien produire. Une ligne « 0 » qui n'apparaît
        # jamais et une ligne qui manque se lisent pareil dans un
        # journal, et c'est la seconde qu'on cherche.
        print(f"  prévisions émises J-{offset} : {len(rows)} lignes "
              f"(classe +{LEAD_BY_OFFSET[offset]} h)"
              + (f" — dont {n_ag} AGRUME" if n_ag else "")
              + (f" et {n_pi} AGRUME+PI" if n_pi else
                 " et AUCUNE ligne AGRUME+PI" if n_ag else "")
              + (f", dont {n_h24} ligne(s) sœur(s) +24 h lue(s) dans "
                 f"arome_r2 (lot L20)" if n_h24 else "")
              + (f", qui ne donneront AUCUNE ligne : horizon 24 h, moins de "
                 f"{MIN_HOURS_DAILY} heures appariables à cet offset"
                 if n_ag and offset and not n_h24 else ""))
        # ⚠️ ET LA LIGNE QUI NOMME LE FLUX. « 1 partie sur 2 » sans son
        # flux se lit « il manque un flux sur trois » : `snapshot_rows`
        # en lit trois (`fcst`, `fcstagrume`, `fcstarome`) et seul
        # `fcst/` est partitionné.
        ligne = dire_bilan_parties(bilan, offset)
        print(f"     {ligne}",
              file=sys.stderr if ligne.startswith("⛔") else sys.stdout)

    jalon_memoire("la relecture de l'archive")

    # ── 1 ter. le mélange multi-modèle (lot L19) ──────────────────
    # ⛔ AVANT `daily_rows`, qui ne saura pas qu'il est là. Les poids
    # viennent du cache des jours < J (`prior_poids`) ; sans poids —
    # cache creux, ou moins de `MX.MIX_MIN_JOURS` journées par membre —
    # la balise n'a pas de `bw_mix` cette nuit, et le bilan le compte.
    t_mix = time.monotonic()
    poids_mix = prior_poids(root, day)
    snapshots, bilan_mix = MX.ajouter_melange(snapshots, poids_mix,
                                              LEAD_BY_OFFSET)
    print(f"  mélange multi-modèle : {len(poids_mix)} balise×échéance "
          f"avec poids sur {MX.MIX_PRIOR_JOURS} j de cache — "
          f"{MX.dire_bilan(bilan_mix, LEAD_BY_OFFSET)} "
          f"({time.monotonic() - t_mix:.1f} s)"
          + ("" if poids_mix else
             " — ⓘ aucun poids : le cache de rejeu est creux ou plus "
             "court que MIX_MIN_JOURS ; `bw_mix` n'existe pas cette nuit."))
    jalon_memoire("le mélange multi-modèle")

    # ── 1 bis. le bilan des parties EN BASE (lot S0.6) ────────────
    #
    # ⚠️ TOUT CE BLOC EST SOUS `try`, POUR LA MÊME RAISON QUE CELUI DE LA
    # PRESSION (S1) : la table est neuve, son SQL est exécuté par Yann et
    # pas par ce script, et une notation qui tomberait ENTIÈRE parce
    # qu'une ligne de DIAGNOSTIC n'a pas pu s'écrire serait le remède
    # pire que le mal. Le journal, lui, a déjà dit la même chose
    # ci-dessus : la base ajoute la lisibilité pour le tableau de bord,
    # elle n'est pas le seul endroit où le fait existe.
    #
    # ⓘ ORDRE DE DÉPLOIEMENT RECOMMANDÉ : la table AVANT le code. Mais
    # grâce à ce `try`, ce n'est plus une CONDITION — c'est un confort.
    # Un ordre de déploiement qu'il faut se rappeler est un ordre qu'on
    # oubliera un soir de fatigue.
    try:
        cp_rows = collect_part_rows(day, bilans_parties)
        n = sb.upsert("model_verif_collect_part", cp_rows, "day,flux")
        incidents = [r for r in cp_rows
                     if r["etat"] not in ("ok", "avant_partition")]
        print(f"  → model_verif_collect_part : {n} ligne(s)"
              + (f", dont {len(incidents)} INCIDENT(S)" if incidents else ""))
    except Exception as exc:                           # noqa: BLE001
        print(f"  ⚠️ model_verif_collect_part : {type(exc).__name__} — {exc}. "
              f"Le bilan des parties reste dans le journal ci-dessus ; la "
              f"notation n'est pas affectée. (Jouer "
              f"`supabase_step48_lot_s06_collect_part.sql`.)",
              file=sys.stderr)

    # ⚠️ TOUTES LES SOURCES DE VENT — cf. `all_obs_rows`, S0.2 (21/08).
    obs_day = all_obs_rows(root, day, st)
    obs_prev = all_obs_rows(root, day - timedelta(days=1), st)
    print(f"  observations du jour : {len(obs_day)} balises, "
          f"veille : {len(obs_prev)}")
    if not obs_day:
        print("❌ aucune observation pour cette journée — rien à noter.",
              file=sys.stderr)
        return 1
    if not obs_prev:
        # Ce n'est pas fatal, mais il faut le DIRE : sans la veille, la
        # persistance est incalculable et `beats_persist` restera nul.
        print("  ⚠️ pas d'observations de la veille : le skill contre la "
              "persistance ne sera pas calculable pour cette journée.")

    # ── 1 ter. LE GARDE-FOU DE POSITION (lot L15, 02/09/2026) ─────
    #
    # ⛔ POURQUOI ICI, ET PAS DANS UN TIMER DE PLUS. Ce contrôle a besoin
    # des positions que la chaîne a UTILISÉES ces dix derniers jours,
    # c'est-à-dire des lignes d'archive obs — dont deux journées sont
    # déjà en mémoire trois lignes plus haut. Un job séparé relirait les
    # mêmes objets pour rien, et il faudrait le surveiller (le lot LV a
    # mesuré ce que coûte une unité de plus qu'on ne sait pas lire).
    #
    # ⚠️ SOUS `try`, ET NON BLOQUANT, comme le bilan des parties : une
    # notation qui tomberait ENTIÈRE parce qu'un contrôle de DIAGNOSTIC
    # a levé serait le remède pire que le mal. Il ne touche à rien : il
    # lit, il écrit une ligne de journal, et il dépose au plus un
    # fichier de cri que `run.sh` enverra.
    try:
        # ⛔⛔ UNE JOURNÉE À LA FOIS, RÉDUITE TOUT DE SUITE. Tenir les
        # dix journées de lignes ensemble coûtait 906 Mo, mesurés sur le
        # VPS le 02/09 — sur un run qui culmine déjà à 1 474 Mo pour un
        # plafond de 2 800, et qui est mort à 2 820 la nuit du 28/08
        # (lot LM). Réduites, les dix journées ne pèsent plus que des
        # dictionnaires de couples (lat, lon).
        obs_pos = {day.strftime("%Y-%m-%d"): CP.positions_des_obs(obs_day),
                   (day - timedelta(days=1)).strftime("%Y-%m-%d"):
                   CP.positions_des_obs(obs_prev)}
        for _k in range(2, CP.SEUIL_PERSISTANCE_J):
            _d = day - timedelta(days=_k)
            _rows = all_obs_rows(root, _d, st)
            obs_pos[_d.strftime("%Y-%m-%d")] = CP.positions_des_obs(_rows)
            del _rows
        res_pos = CP.verifier(root, day, obs_pos)
        del obs_pos
        gc.collect()
        print(CP.texte_journal(res_pos),
              file=sys.stderr if res_pos["confirmees"] else sys.stdout)
        _texte = CP.cri(res_pos, root)
        if _texte:
            # ⓘ Le fichier EST la file d'attente : `run.sh` l'envoie puis
            # l'efface. S'il n'y arrive pas (run tué plus loin), il est
            # toujours là demain — bruyant, jamais muet.
            (root / "cri.position").write_text(_texte, encoding="utf-8")
            # ⛔ EN ATTENTE, pas posé : c'est `run.sh` qui le promeut,
            # après l'e-mail (02/09). Posé ici, un envoi raté rendait
            # le garde-fou muet pour toujours sur cet ensemble.
            CP.poser_jeton(res_pos, root, en_attente=True)
            print(f"  ⛔ position : {len(res_pos['confirmees'])} balise(s) "
                  f"CONFIRMÉE(S) — cri déposé pour envoi", file=sys.stderr)
    except Exception as exc:                           # noqa: BLE001
        print(f"  ⚠️ garde-fou de position : {type(exc).__name__} — {exc}. "
              f"La notation n'est pas affectée ; c'est le CONTRÔLE qui est "
              f"muet cette nuit, et c'est exactement ce qu'il surveille "
              f"chez les autres.", file=sys.stderr)
    jalon_memoire("le garde-fou de position")

    # ── 2-3. apparier et écrire l'agrégat quotidien ──────────────
    t_clim = time.monotonic()
    clim, poids_comb = climatology_by_station(root, day, st, utc_offset_s)
    print(f"  climatologie horaire : {len(clim)} balises "
          f"({time.monotonic() - t_clim:.1f} s)"
          + ("" if clim else " — archive trop courte, seconde référence "
                             "indisponible, `beats_clim` restera nul"))
    # ── lot L9c : le poids de la référence combinée ───────────────
    # ⛔ LE COMPTE EST DIT, ET IL EST DIT CONTRE `clim`. Une balise qui a
    # une climatologie mais pas de `k` (moins de cinq journées
    # consécutives appariables) n'aura PAS de `mse_comb` : sans cette
    # ligne, la colonne sortirait à moitié vide sans que rien ne dise
    # pourquoi, et on chercherait le défaut dans le mélange.
    if poids_comb:
        _ks = sorted(poids_comb.values())
        _med_k = _ks[len(_ks) // 2]
        print(f"  référence combinée : k estimé sur {len(poids_comb)} "
              f"balises / {len(clim)} climatologisées — médiane "
              f"k = {_med_k:.3f} (k = 1 → persistance pure, "
              f"k = 0 → climatologie pure)")
    else:
        print("  ⓘ référence combinée : aucun k estimable (archive trop "
              "courte) — `mse_comb` restera nul cette nuit.")
    # ── l'antécédent du biais de site (lot S2) ───────────────────
    t_prior = time.monotonic()
    prior = prior_biais(root, day)
    print(f"  antécédent du biais : {len(prior)} couples balise×modèle×échéance "
          f"sur {BIAIS_PRIOR_JOURS} j de cache ({time.monotonic() - t_prior:.1f} s)"
          + ("" if prior else
             f" — ⓘ vide : le cache de rejeu est creux ou vient de changer de "
             f"formule ({REPLAY_FORMULA}). Les colonnes corrigées resteront "
             f"nulles cette nuit ; `--replay-budget 30` comble d'un coup."))
    # ── lot L19 : l'antécédent FIN (secteur × tranche) ────────────
    prior_fin = prior_biais_fin(root, day)
    print(f"  antécédent fin du biais : {len(prior_fin)} couples "
          f"balise×modèle×échéance avec au moins une cellule qui parle"
          + ("" if prior_fin else " — ⓘ vide : le cache ne porte pas "
                                  "encore de sommes par cellule (écrites "
                                  "à partir de cette nuit)."))
    temoin: list = []
    temoin_fin: list = []
    rows, banded = daily_rows(day, snapshots, obs_day, obs_prev, utc_offset_s,
                              clim, bias_prior=prior, temoin=temoin,
                              poids_comb=poids_comb,
                              bias_prior_fin=prior_fin, temoin_fin=temoin_fin)
    print(f"  {len(rows)} agrégats quotidiens, {len(banded)} détails par tranche")
    part_temoin = bilan_temoin(temoin)
    if part_temoin:
        print(f"  ⛔ témoin du corrigé : {part_temoin['texte']}")
    # ── lot L19 : les trois témoins du lot, dans le journal ───────
    part_temoin_fin = BF.bilan_temoin_fin(temoin_fin)
    if part_temoin_fin:
        print(f"  ⛔ témoin du corrigé FIN : {part_temoin_fin['texte']}")
    else:
        print(f"  ⓘ témoin du corrigé fin : {len(temoin_fin)} échantillon(s), "
              f"moins de 30 — rien à dire cette nuit")
    part_mix = MX.bilan_melange(rows, poids_mix)
    n_mix_rows = sum(1 for r in rows if r["model"] == MX.MODEL_MIX)
    if part_mix:
        print(f"  ⛔ témoins du mélange : {part_mix['texte']}")
    else:
        print(f"  ⓘ témoins du mélange : {n_mix_rows} ligne(s) bw_mix, pas "
              f"assez de couples (≥ 30) pour un bilan cette nuit")
    if rows:
        n = _upsert_daily(sb, _pour_la_base(sb, "model_verif_daily", rows))
        print(f"  → model_verif_daily : {n} lignes")
    # ⚠️ Le cache de rejeu est alimenté PAR CE CALCUL-CI, pas par un
    # second. La journée notée ce soir entre donc dans la fenêtre du
    # chemin régime sans coûter une seule seconde de plus. C'est ce qui
    # rend le rejeu tenable en régime de croisière : le run ne rattrape
    # que le passé, et le passé se remplit une fois.
    replay_write(root, day, rows)
    jalon_memoire("l'agrégat quotidien (chemin J-0)")

    # ── 4-5. zones, accumulateurs, scores ────────────────────────
    # ⚠️ Chaque `select` passe la clé primaire de sa table en `order` :
    # c'est ce qui rend la pagination cohérente (cf. `Supabase.select`).
    # `station_zone` tenait sous les 1 000 lignes (647 le 08/08) et
    # n'était donc pas tronquée — mais rien ne garantit qu'elle y reste,
    # et un plafond qu'on ne franchit pas encore reste un plafond.
    zones_raw = sb.select("station_zone", order="source,station_id")
    zone_of = {f"{z['source']}:{z['station_id']}": z for z in zones_raw}

    # ── 3 bis. la pression (E6, lot S1) ───────────────────────────
    #
    # ⚠️ TOUT CE BLOC EST SOUS `try`, ET C'EST DÉLIBÉRÉ. La notation du
    # vent tourne depuis quatorze nuits ; la pression est neuve, sa
    # table peut ne pas encore exister (le SQL est exécuté par Yann,
    # pas par ce script), et ses archives commencent le 22/08. Une
    # exception ici ne doit JAMAIS emporter le run de vent avec elle —
    # ce serait échanger un chantier qui marche contre un chantier qui
    # démarre. Elle est journalisée en toutes lettres, pas avalée.
    #
    # ⓘ Placé APRÈS `station_zone` parce que l'appariement a besoin de
    # `dem_alt_m` — la seule altitude que les points Pioupiou possèdent,
    # et la seule qui soit sur la même échelle que celle des stations.
    try:
        pres_obs = pres_obs_rows(root, day, st)
        if not pres_obs:
            print("  ⓘ pression : aucune archive d'observation pour cette "
                  "journée — normal avant le 22/08 (flux S0.2 déployés le "
                  "21/08). Rien noté, rien écrit.")
        else:
            p_rows, p_bilan = pressure_rows(day, snapshots, pres_obs, zone_of)
            print(f"  pression : {p_bilan}")
            if p_rows:
                n = sb.upsert("model_verif_daily_pres",
                              _pour_la_base(sb, "model_verif_daily_pres", p_rows),
                              "day,source,station_id,model,lead_h,fcst_src")
                print(f"  → model_verif_daily_pres : {n} lignes")
    except Exception as exc:                       # noqa: BLE001
        print(f"  ⚠️ pression (S1) : {type(exc).__name__} — {exc}. "
              f"La notation du VENT n'est pas affectée.", file=sys.stderr)

    # ── L1 : LE DUEL APPARIÉ, HORS CLASSEMENT (27/08/2026) ────
    #
    # ⛔ POURQUOI UNE SECONDE LECTURE, ET POURQUOI ELLE EST PETITE.
    # La fenêtre glissante du run (`daily`, plus bas) couvre
    # `ROLLING_DAYS` = 15 jours ; le duel en veut 30 — l'écart
    # qu'il cherche (~0,03 km/h) demande 15 à 40 jours pour se voir
    # (audit §2.4). Mais il ne lit QUE quatre modèles, un lead et un
    # réseau, sur sept colonnes : quelques dizaines de milliers de
    # lignes contre les centaines de milliers de la fenêtre entière.
    #
    # ⛔ ET IL EST ICI, HORS DU `else: (zone_of non vide)` OÙ IL AVAIT
    # D'ABORD ÉTÉ ÉCRIT. Le duel ne connaît AUCUNE zone : il apparie des
    # balise-jours, pas des cases. L'avoir laissé sous ce `if` aurait
    # rendu son silence indistinguable d'un défaut de `station_zone` —
    # un couplage invisible, du genre qui se découvre le soir où la
    # table de zones est vide et où l'on cherche pourquoi le duel a
    # disparu.
    #
    # ⚠️ SOUS `try`, COMME LE BILAN DES PARTIES ET LA PRESSION. Le duel
    # est un DIAGNOSTIC : il ne décide d'aucun rang, d'aucune ligne de
    # `model_score_zone`. Une nuit de notation perdue parce qu'un bloc
    # d'observation n'a pas pu se calculer serait le remède pire que
    # le mal — et le journal, lui, dira ce qui s'est passé.
    duels_rows: list[dict] = []
    try:
        depuis_duel = (day - timedelta(days=DUEL.DUEL_DAYS - 1)
                       ).strftime("%Y-%m-%d")
        daily_duel = sb.select(
            "model_verif_daily", DUEL.query_duel(depuis_duel),
            order="day,source,station_id,model,lead_h,fcst_src")
        # ── lot L17 : les doublons d'inscription sortent du duel aussi ─
        #
        # ⛔ POURQUOI ICI ET PAS DANS `duel.py`. Le duel lit une requête
        # ÉTROITE (quatre colonnes, un lead, un réseau) et ne connaît
        # aucune zone : lui faire lire `station_zone` doublerait sa
        # requête pour trois paires. Le filtre vit donc chez l'appelant,
        # qui a déjà la table sous la main.
        #
        # ⚠️ ET IL DÉGRADE AU LIEU DE SE TAIRE. `station_zone` vide ⇒
        # aucun filtre, et le duel tourne QUAND MÊME — c'est l'arbitrage
        # nº 5 du lot L1 (« le duel ne connaît aucune zone ; l'y coupler
        # rendrait son silence indistinguable d'un défaut de
        # `station_zone` »). On ajoute un filtre, pas une dépendance.
        #
        # ⚠️ CE FILTRE FAIT UNE MARCHE DANS LA SÉRIE CUMULÉE, et c'est un
        # arbitrage assumé : mesuré le 27/08, il retire 24 balise-jours
        # sur 2 947 (0,8 %) et déplace la médiane de −0,0006 à −0,0008,
        # soit moins que la résolution du tirage. Mieux vaut une petite
        # marche aujourd'hui qu'un verdict à 40 jours (arbitrage nº 3 du
        # L1) construit sur des paires comptées deux fois.
        # ⓘ 02/09 : `unites_hors_notation` — doublon ET position
        # suspecte (lot L15), le même ensemble que Murphy. Le nom
        # `doublons_duel` reste pour que le journal ne change pas.
        doublons_duel = unites_hors_notation(zone_of)
        if doublons_duel:
            avant_duel = len(daily_duel)
            daily_duel = [r for r in daily_duel
                          if f"{r['source']}:{r['station_id']}"
                          not in doublons_duel]
            retires_duel = avant_duel - len(daily_duel)
        else:
            retires_duel = 0
        duels_rows = DUEL.duels(daily_duel)
        print(f"  duel apparié ({DUEL.DUEL_VALUE_KEY}, lead "
              f"{DUEL.DUEL_LEAD_H}, {DUEL.DUEL_SOURCE}) : "
              f"{len(daily_duel)} lignes lues depuis le {depuis_duel}"
              + (f" ({retires_duel} retirée(s) : doublon d'inscription"
                 f" ou position suspecte)"
                 if retires_duel else
                 ("" if doublons_duel else
                  " — ⓘ aucun doublon connu (`station_zone` vide ou "
                  "`doublon_de` jamais posé) : duel NON filtré")))
        for _d in duels_rows:
            print(DUEL.dire(_d))
            if _d["excluded_duplicates"]:
                print(f"     ⚠️ {_d['excluded_duplicates']} balise-jour(s) "
                      f"écartée(s) : deux `fcst_src` pour une même "
                      f"balise-jour (cf. duel.lignes_du_modele)",
                      file=sys.stderr)
            if _d["truncated_by_retention"]:
                print(f"     ⓘ cumul TRONQUÉ par la rétention "
                      f"({DUEL.DUEL_DAYS} j) : le « depuis la naissance "
                      f"de la paire » n'est plus vrai — cf. duel.DUEL_DAYS")
    except Exception as exc:                       # noqa: BLE001
        print(f"  ⚠️ duel apparié : {type(exc).__name__} — {exc}. La "
              f"notation continue, le bloc `duels` sera vide ce soir.",
              file=sys.stderr)

    if not zone_of:
        print("  ⓘ `station_zone` est vide : aucune balise n'est encore")
        print("     rattachée à son bassin-versant. Les accumulateurs et les")
        print("     scores de zone sont SAUTÉS — pas calculés au hasard.")
        print("     (l'affectation demande le relief ; elle n'est pas dans ce lot)")
        # ⛔ ET LA DÉCOMPOSITION DE MURPHY AVEC EUX, PARCE QU'ELLE MONTE
        # SUR LA MÊME FENÊTRE REJOUÉE (lot L9b). Elle ne connaît pourtant
        # aucune zone : c'est un COUPLAGE DE COÛT, pas de sens, assumé
        # pour ne pas relire trente journées d'archive une seconde fois.
        # Le dire ici est la contrepartie — sans cette ligne, un
        # `model_murphy.json` manquant se lirait comme une panne de
        # Murphy alors que c'est `station_zone` qui est vide (arbitrage
        # nº 5 du lot L1, appliqué à l'envers et à découvert).
        print("     ⚠️ `model_murphy.json` n'est donc pas republié non plus :")
        print("        il monte sur la fenêtre rejouée, qui n'est pas lue ici.")
    elif not republier:
        # ⛔⛔ LOT LR — LE REJEU D'UNE VIEILLE JOURNÉE S'ARRÊTE ICI.
        # `model_verif_daily` est écrit (c'était tout l'objet du rejeu),
        # l'archive est là, le duel a joué. Ce qui suit publierait le
        # classement DU JOUR sur une fenêtre qui finit à la journée
        # rejouée — 15 + (hier − day) jours sous l'étiquette
        # `rolling15`. Mesuré le 01/09 pour un rejeu du 13/08 : 290
        # premières places sur 1 984 changeaient de titulaire.
        # ⚠️ CE MESSAGE SORT À CHAQUE FOIS, et il DIT LE NOMBRE DE JOURS
        # de trop : un garde-fou muet a exactement l'allure d'une
        # fonctionnalité manquante, et c'est comme ça qu'on finit par le
        # retirer « parce qu'il ne sert à rien ».
        trop = (as_of - timedelta(days=1)).date() - day.date()
        print(f"  ⛔ JOURNÉE REJOUÉE ({day:%Y-%m-%d}) PLUS VIEILLE QU'HIER "
              f"de {trop.days} jour(s) : le classement du jour n'est PAS "
              f"republié.")
        print(f"     `model_verif_daily` est comblé, l'archive est lue, le "
              f"duel a joué — mais `model_score_zone`, les scores")
        print(f"     d'événement, Murphy et les objets R2 sont SAUTÉS : leur "
              f"fenêtre finirait à {day:%Y-%m-%d} alors que leur")
        print(f"     `as_of` dit {as_of:%Y-%m-%d}, soit "
              f"{15 + trop.days} jours publiés sous l'étiquette "
              f"`rolling15`. (lot LR — `--publier-quand-meme` pour")
        print(f"     passer outre en connaissance de cause.)")
    else:
        needed = zone_rows_needed(list(zone_of.values()))
        if needed:
            sb.upsert("model_zone", needed, "zone_id")

        # ⛔ LOT S15 — LA RELECTURE DES ACCUMULATEURS A DISPARU D'ICI, ET
        # C'ÉTAIT TOUT L'OBJET DU LOT. Le job lisait la table ENTIÈRE
        # chaque nuit (739 916 lignes, 142–157 s le 25/08) pour n'en
        # faire qu'une chose : appliquer une récurrence pure. Cette
        # récurrence vit maintenant dans `bw_accumulate` (step51), et le
        # job n'envoie plus que la MÉDIANE DU JOUR. Le seul des quatre
        # coûts de cette étape qui grandissait sans plafond — parce
        # qu'il grandissait avec l'HISTOIRE et non avec le travail du
        # jour — n'existe plus.
        #
        # ⚠️ ET L'IDEMPOTENCE A CHANGÉ DE CAMP AVEC LUI. Avant, elle
        # était ici : `accumulate` rendait l'accumulateur inchangé si la
        # journée était déjà intégrée, et le job envoyait un état
        # ABSOLU — rejouer une nuit réécrivait les mêmes valeurs.
        # Maintenant le job envoie un DELTA, et c'est le
        # `where … p_day > mc.last_day` de la RPC qui empêche une nuit
        # rejouée de compter DEUX FOIS. Le banc de double rejeu
        # (`test_score`) est ce qui tient cette propriété : qui retire
        # ce `where` fait rougir ce banc-là, et lui seul.
        #
        # ⓘ `select_par_cle` reste dans `Supabase` : elle sert encore
        # ailleurs, et elle est le chemin de repli si ce lot était
        # annulé.
        updates = accumulator_updates(banded, zone_of)
        if updates:
            n = sb.avance_caractere(updates, f"{day:%Y-%m-%d}")
            print(f"  → model_character : {n} accumulateurs avancés "
                  f"sur {len(updates)} envoyés")
            if n != len(updates):
                # ⓘ L'ÉCART N'EST PAS DU BRUIT, et il est normal : ce
                # sont les valeurs non finies écartées par la RPC, plus
                # les clés dont la journée était déjà intégrée (un
                # rejeu). Le dire à voix haute, parce que `sb.upsert`
                # comptait jusqu'ici ce qu'il ENVOYAIT — et c'est
                # exactement ce qui a rendu impossible, le 25/08, de
                # réconcilier les 3 615 845 « avancées » du journal avec
                # les 3 270 977 `days` de la table.
                print(f"     ⓘ {len(updates) - n} ligne(s) non appliquée(s) "
                      f"(valeur non finie, ou journée déjà intégrée)")

        # ── 4 bis. événements (lot F) ────────────────────────────
        # ⚠️ Après les zones, jamais avant : `model_verif_event.zone_id`
        # porte une clé étrangère, et un événement sans case fine n'a de
        # toute façon aucun sens — la confirmation réseau se fait entre
        # balises d'une MÊME case.
        ev_rows, bilan = event_rows(day, snapshots, obs_day, zone_of, utc_offset_s)
        print(f"  événements : {bilan}")
        # Purge d'abord : la table n'a pas de clé d'unicité (une ligne par
        # événement individuel), donc seule la réécriture complète de la
        # journée rend le run rejouable sans doubler les lignes.
        sb.delete("model_verif_event", f"?day=eq.{day:%Y-%m-%d}")
        if ev_rows:
            n = sb.insert("model_verif_event", ev_rows)
            par_type = defaultdict(int)
            for r in ev_rows:
                par_type[r["event_type"]] += 1
            detail = ", ".join(f"{k} {v}" for k, v in sorted(par_type.items()))
            print(f"  → model_verif_event : {n} lignes ({detail})")
        else:
            print("  → model_verif_event : aucune ligne (aucun événement "
                  "confirmé par le réseau cette journée)")

        # ══════════════════════════════════════════════════════════
        #  ⛔ L'OUBLI DU CHEMIN J-0 — LA CAUSE DE L'OOM DU 28/08
        # ══════════════════════════════════════════════════════════
        #
        # Tout ce que ce bloc relâche a fini son travail À LA LIGNE
        # PRÉCÉDENTE, et restait pourtant vivant jusqu'à la fin du run
        # — c'est-à-dire pendant les deux phases les plus lourdes de la
        # nuit (la fenêtre glissante, puis le rejeu d'archive). Python
        # ne libère rien tant qu'un nom du cadre pointe dessus, et
        # `main()` est un cadre unique de six cents lignes : ici, tout
        # ce qui a servi une fois survit jusqu'au `return`.
        #
        # ⚠️ CE N'EST PAS UNE MICRO-OPTIMISATION, C'EST MESURÉ. Le
        # 28/08, le processus est mort à 2 819 Mo dans `regime_scores`.
        # `daily` seul (relâché plus bas) pesait 497 Mo sondés sur la
        # production ; les snapshots des trois offsets, les
        # observations de deux journées, la climatologie de trente et
        # les agrégats du jour tiennent le même ordre de grandeur. Rien
        # de tout cela n'est relu après cette ligne — vérifié nom par
        # nom, c'est la seule chose qui rend ce bloc sûr.
        #
        # ⚠️ `= None` ET NON `del`, ET C'EST DÉLIBÉRÉ : `pres_obs`,
        # `p_rows` et `daily_duel` naissent dans des `try` qui ont le
        # droit de ne pas aboutir. `del` sur un nom jamais lié lèverait
        # `NameError` et ferait tomber la notation POUR AVOIR VOULU
        # ÉCONOMISER DE LA MÉMOIRE — le remède pire que le mal, une
        # fois de plus. Une affectation, elle, marche dans les deux cas.
        #
        # ⓘ Les deux comptes qui survivent (`n_prior`, `n_clim`) sont
        # lus par le `meta` de `_publish`, tout en bas. On garde le
        # NOMBRE, pas les tables : deux entiers contre quelques
        # centaines de Mo.
        n_prior, n_clim = len(prior), len(clim)
        n_prior_fin, n_poids_mix = len(prior_fin), len(poids_mix)   # L19, idem
        snapshots = obs_day = obs_prev = clim = poids_comb = prior = None
        rows = banded = temoin = zones_raw = None
        # Lot L19 : l'antécédent fin pèse jusqu'à 16 accumulateurs par
        # couple ; on n'en garde que le nombre, comme pour `prior`.
        prior_fin = poids_mix = temoin_fin = None
        pres_obs = p_rows = daily_duel = updates = ev_rows = None
        gc.collect()
        jalon_memoire("l'oubli du chemin J-0")

        since_ev = (day - timedelta(days=ROLLING_DAYS - 1)).strftime("%Y-%m-%d")
        # ⛔ `cle_unique` : `id` est la clé primaire — pagination par clé,
        # pas par décalage (mort à la page 782 le 02/09, voir `select`).
        ev_all = sb.select("model_verif_event", f"?day=gte.{since_ev}",
                           order="id", cle_unique=True)
        ev_scores, rejets, inconnues, retenues = event_scores(ev_all, zone_of)
        # ⓘ 15 jours de `model_verif_event`, dont plus rien ne se sert
        # dès que les scores d'événement sont calculés.
        ev_all = None
        if inconnues:
            print(f"  ⚠️ {inconnues} lignes d'événement sur une zone qui n'a "
                  f"plus aucune balise rattachée : publiées telles quelles, "
                  f"sans chaîne de repli.")
        if retenues:
            print(f"  ⓘ {retenues} lignes NON publiées (familles hors "
                  f"{', '.join(EVENT_PUBLISHABLE_TYPES)}) : elles restent en "
                  f"base et le JSON dit pourquoi.")
        print(f"  événements notés : {len(ev_scores)} combinaisons publiables, "
              f"{rejets} écartées sous le quorum de {EVENT_MIN_OCCURRENCES}")
        _publish_events(st, ev_scores, as_of, rejets, retenues, args.dry_run)

        since = (day - timedelta(days=ROLLING_DAYS - 1)).strftime("%Y-%m-%d")
        daily = sb.select("model_verif_daily", f"?day=gte.{since}",
                          order="day,source,station_id,model,lead_h,fcst_src")

        t_roll = time.monotonic()
        scores = rolling_scores(daily, zone_of, as_of)
        print(f"  score glissant : {len(scores)} lignes "
              f"({time.monotonic() - t_roll:.1f} s)")
        # ⛔ 497 Mo, SONDÉS SUR LA PRODUCTION LE 28/08 : `daily` porte
        # 332 307 lignes de `model_verif_daily` (15 jours × ~1 568
        # octets par ligne en mémoire). Plus une seule ligne ne le relit
        # après `rolling_scores` — et il restait pourtant vivant pendant
        # tout le chemin régime, qui est justement le plus gros
        # consommateur du run. C'est le plus lourd des blocs morts de
        # cette nuit-là, et le plus facile à relâcher.
        daily = None
        gc.collect()
        jalon_memoire("l'oubli de la fenêtre glissante")
        # `model_zone` est relue APRÈS l'upsert des échelons 2 et 4, pour
        # que `agg_level` soit littéralement le `kind` de la zone et non
        # une déduction faite sur la forme de son identifiant. Une table
        # de quelques centaines de lignes, une fois par nuit.
        kind_of = {r["zone_id"]: r["kind"]
                   for r in sb.select("model_zone", order="zone_id",
                                      cle_unique=True)}

        # ── chemin régime : archive rejouée, plus accumulateurs ───
        t_replay = time.monotonic()
        # ⚠️ L'accumulateur de Murphy se remplit PENDANT la lecture de la
        # fenêtre (lot L9b) : une seule passe, et la clé `_murphy` ne
        # survit pas à la ligne. Voir le pavé dans `replay_window`.
        murphy_acc: dict = {}
        # ⓘ 02/09 : Murphy sur la MÊME population que le classement et
        # le duel — sans les doublons (L17) ni les positions suspectes
        # (L15). Voir `unites_hors_notation`.
        murphy_exclus = unites_hors_notation(zone_of)
        units, bilan_replay = replay_window(
            root, day, st, utc_offset_s, args.regime_days,
            args.replay_budget, murphy_acc=murphy_acc,
            murphy_exclus=murphy_exclus)
        print(f"  rejeu d'archive : {bilan_replay} en "
              f"{time.monotonic() - t_replay:.1f} s")
        jalon_memoire("le rejeu d'archive")
        # ── lot L9b (28/08) : TIMING ou AMPLITUDE, par balise ─────────
        #
        # ⚠️ IL MONTE SUR LA FENÊTRE DÉJÀ REJOUÉE, ET C'EST UN ARBITRAGE
        # OPPOSÉ À CELUI DU DUEL. Le duel (L1) lit sa PROPRE requête,
        # étroite, pour rester hors du `else: (zone_of non vide)` — il
        # ne connaît aucune zone et son silence ne devait pas se
        # confondre avec un défaut de `station_zone`. Murphy, lui, a
        # besoin des MOMENTS de trente journées d'archive : les relire
        # par un second chemin doublerait le poste le plus cher du run
        # (85,6 s mesurées au lot G). Il vit donc ici, sur `units`, et
        # le prix est nommé : si `station_zone` est vide, le fichier
        # Murphy ne sort pas — c'est dit en toutes lettres dans la
        # branche `if not zone_of` ci-dessus.
        #
        # ⚠️ SOUS `try`, comme le duel et la pression : un diagnostic ne
        # fait pas tomber une nuit de notation.
        t_mur = time.monotonic()
        try:
            mur_balises = MU.par_balise_depuis_acc(murphy_acc)
            mur_modeles = MU.par_modele(mur_balises)
            n_ok = sum(1 for l in mur_balises if l["reason"] == "ok")
            print(f"  décomposition de Murphy : {len(mur_balises)} "
                  f"(balise × modèle × échéance), dont {n_ok} décomposées "
                  f"— {len(murphy_exclus)} balise(s) tenue(s) dehors "
                  f"(doublon ou position suspecte, comme le classement) "
                  f"({time.monotonic() - t_mur:.1f} s)")
            if not n_ok and mur_balises:
                # ⛔ ZÉRO DÉCOMPOSÉE N'EST PAS « TOUT VA BIEN ». C'est le
                # symptôme d'un cache de rejeu creux (formule qui vient
                # de changer) ou d'une fenêtre trop courte — et il faut
                # que le journal le crie, pas qu'il le taise.
                print(f"  ⚠️ Murphy : AUCUNE ligne décomposée. Cache de "
                      f"rejeu creux (formule {REPLAY_FORMULA} neuve ?) ou "
                      f"fenêtre sous {MU.MURPHY_MIN_DAYS} jours / "
                      f"{MU.MURPHY_MIN_PAIRS} heures.", file=sys.stderr)
            for l in mur_modeles:
                print(MU.dire(l))
            _publish_murphy(st, mur_modeles, mur_balises, as_of, args.dry_run)
        except Exception as exc:                     # noqa: BLE001
            print(f"  ⚠️ décomposition de Murphy : {type(exc).__name__} — "
                  f"{exc}. La notation continue, `model_murphy.json` n'est "
                  f"pas republié ce soir.", file=sys.stderr)

        t_reg = time.monotonic()
        reg_rows = regime_scores(units, as_of, zone_of, kind_of)
        scores += reg_rows
        # ⚠️ CHIFFRE À SURVEILLER. Mesuré le 09/08 sur un jeu synthétique
        # à la taille réelle (194 100 balise-jours, 30 jours) : 85,6 s.
        # C'est le poste le plus cher du lot G, et il grandit avec la
        # profondeur d'archive. Le jour où il déborde, la manette est
        # `--regime-days`, pas le timer.
        jalon_memoire("le score par régime")
        print(f"  score par régime : {len(reg_rows)} lignes "
              f"({time.monotonic() - t_reg:.1f} s)")

        # ⛔ UN RANG PUBLIÉ SUR UNE JOURNÉE INCOMPLÈTE DOIT LE DIRE
        # (lot S0.6). `_apply_rank` classe les modèles PRÉSENTS : si la
        # passe de surface a échoué, il publie « 1ᵉʳ sur 2 » sans que
        # rien ne dise que sept manquaient. On garde le classement — un
        # classement absent et un classement partiel se lisent pareil à
        # l'écran, et le second au moins se dit — mais on le QUALIFIE.
        # ⛔ LA MULTIPLICITÉ, SUR LE TABLEAU ENTIER (lot L3, 27/08/2026).
        # Ici et pas ailleurs : `scores` porte enfin la RÉUNION du
        # glissant et des régimes, c'est-à-dire la famille de tests que
        # la nuit publie. Et AVANT `marquer_parties_manquantes`, qui ne
        # requalifie que les rangs restés « ok » (cf. son pavé).
        rapport_fdr = appliquer_fdr(scores)
        for _fam, _b in rapport_fdr.items():
            if not _b["m"]:
                continue
            _seuil = ("aucun" if _b["seuil"] is None else f"{_b['seuil']:.5f}")
            print(f"  ⓘ FDR ({_fam}) : {_b['m']} test(s) joué(s), "
                  f"{_b['k']} survivant(s) à BH α={INF.ALPHA_FDR}, "
                  f"seuil p ≤ {_seuil} (p min observé "
                  f"{_b['p_min']:.5f}) — {_b['retrogrades']} rang(s) "
                  f"retiré(s) sur {_b['publies_avant']} publié(s) → "
                  f"`{'rank_reason' if _fam == 'brut' else 'rank_reason_corr'}"
                  f" = {RANK_REASON_FDR}`")
        n_marques = marquer_parties_manquantes(scores, bilans_parties)
        if n_marques:
            print(f"  ⛔ {n_marques} rang(s) publié(s) sur une journée "
                  f"d'émission INCOMPLÈTE → `rank_reason = "
                  f"{RANK_REASON_PARTIE_MANQUANTE}`", file=sys.stderr)
        n_pool = apply_pooling(scores, list(zone_of.values()))
        print(f"  rétrécissement vers le parent : {n_pool} cases fines "
              f"rapprochées de leur échelon supérieur (poids emprunté publié)")

        t_stab = time.monotonic()
        stabilite = stability_report(units, zone_of, as_of, kind_of)
        print(f"  ({time.monotonic() - t_stab:.1f} s)", end=" ")
        print(f"  stabilité des rangs : {stabilite['reason']}"
              + (f" · tau = {stabilite['kendall_tau']} sur "
                 f"{stabilite['n_comparable']} cases, "
                 f"{stabilite['shared_days']} jour(s) partagé(s)"
                 if stabilite["kendall_tau"] is not None else ""))
        print(f"     ⓘ {stabilite['covers']}")
        # ⓘ Dernier lecteur de la fenêtre rejouée : `units` porte
        # 405 486 balise-jours (mesuré le 28/08, ~1 598 octets par ligne
        # en mémoire, soit ~650 Mo), et la publication qui suit n'en lit
        # plus une seule. Même geste que pour `daily`, même raison.
        units = None
        gc.collect()
        jalon_memoire("l'oubli de la fenêtre rejouée")

        if scores:
            n = _upsert_scores(sb, _pour_la_base(sb, "model_score_zone",
                                                 scores))
            print(f"  → model_score_zone : {n} lignes")
            # Le JSON publié, lui, porte TOUT : il n'a pas de schéma à
            # respecter, et c'est lui que lira l'écran des bêta-testeurs.
            # ⚠️ `variable` EST ÉCRIT EXPLICITEMENT SUR CHAQUE LIGNE,
            # jamais déduit d'une absence (lot S1). L'écran ne doit
            # jamais additionner des hPa et des km/h ; « pas de champ »
            # se lit un jour comme « pas de valeur », et c'est la
            # deuxième moitié de ce garde-fou qui vit côté web (une
            # ligne sans `variable` y est traitée comme `wind`, pour
            # qu'un JSON servi par le CDN pendant l'heure de cache ne
            # fasse pas disparaître le tableau).
            for _s in scores:
                _s.setdefault("variable", "wind")
            _publish(st, scores, as_of, args.dry_run,
                     meta={"stability": stabilite,
                           "replay": bilan_replay,
                           "regime_days": args.regime_days,
                           # ⛔ Le témoin voyage AVEC le corrigé, dans le
                           # même objet, pour qu'on ne puisse pas lire
                           # l'un sans l'autre (lot S2).
                           "bias_correction": {
                               "prior_days": BIAIS_PRIOR_JOURS,
                               "half_life_days": BIAIS_DEMI_VIE_J,
                               "min_days": BIAIS_MIN_JOURS,
                               "estimator": "ls_slope_sum_of_over_sum_ff",
                               "pairs_with_prior": n_prior,
                               "witness": part_temoin,
                           },
                           "climatology_stations": n_clim,
                           # ── lot L19 (04/09) : le mélange, le fin et la
                           # dispersion voyagent avec LEURS témoins ────
                           "melange": {
                               "modeles": list(MX.MODELES_MELANGE),
                               "demi_vie_j": MX.MIX_DEMI_VIE_J,
                               "min_jours": MX.MIX_MIN_JOURS,
                               "min_membres": MX.MIX_MIN_MEMBRES,
                               "espace": "(u, v)",
                               "poids": "1 / EWMA(err_vec_rms^2), par balise "
                                        "x classe, normalise",
                               "familles": {k: list(v)
                                            for k, v in MX.FAMILLES.items()},
                               "balises_avec_poids": n_poids_mix,
                               "classe": "notee, pas classee "
                                         "(serie_en_essai) — decision de "
                                         "Yann du 04/09",
                               "witness": part_mix,
                           },
                           "bias_correction_fin": {
                               "cellule": "quadrant(direction PREVUE) x "
                                          "tranche locale (nuit/matin/aprem)",
                               "repli": list(BF.NIVEAUX),
                               "min_days": BF.FIN_MIN_JOURS,
                               "min_hours": BF.FIN_MIN_HEURES,
                               "pairs_with_prior": n_prior_fin,
                               "witness": part_temoin_fin,
                           },
                           "dispersion": MX.bilan_dispersion(units),
                           # ⛔⛔ LA RÉSERVE VOYAGE AVEC LES COLONNES
                           # QU'ELLE QUALIFIE (arbitrage de Yann,
                           # 02/09/2026, volet c du lot L9).
                           #
                           # `skill_comb`/`beats_comb` sont publiés
                           # depuis le 28/08 et lus par PERSONNE — zéro
                           # occurrence dans `PWA/web/src`, vérifié le
                           # 01/09. Ils n'en sont pas moins un objet
                           # PUBLIC : 33 068 lignes au 01/09, dont
                           # 15 001 `beats_comb = true`. La question
                           # posée à Yann était « les taire ou les
                           # qualifier » ; il a tranché QUALIFIER, et
                           # une réserve qui vivrait dans un rapport à
                           # côté ne qualifierait rien du tout. Elle est
                           # donc DANS le fichier, comme le témoin du
                           # S2 : pour qu'on ne puisse pas lire les
                           # colonnes sans elle.
                           #
                           # ⚠️ CE QU'ELLE DIT, ET CE QU'ELLE NE DIT
                           # PAS. Elle ne dit pas « ces chiffres sont
                           # faux » : le test tourne sur des heures
                           # réellement communes, et l'anomalie est
                           # INTERMITTENTE (`skill_comb > skill_clim`
                           # sur 12 modèles sur 12 le 29/08, sur 4 sur
                           # 12 le 31/08). Elle dit dans quel ESPACE le
                           # mélange est fait, et que la dominance de
                           # Murphy — l'argument qui justifie de publier
                           # un `beats_comb` du tout — n'est pas
                           # démontrée dans cet espace-là.
                           "references_combinees": {
                               "definition": "k*persistance + (1-k)*climatologie",
                               "poids_k": "autocorrelation 24 h de "
                                          "l'anomalie, bornee a [0, 1]",
                               "comb": {
                                   "melange": "force scalaire, cap circulaire",
                                   "colonnes": ["mse_comb", "skill_comb",
                                                "beats_comb"],
                                   "reserve":
                                       "le melange n'est PAS convexe dans "
                                       "l'espace ou pair_error mesure "
                                       "(vectoriel) : la borne de Jensen ne "
                                       "s'y applique pas, et la dominance de "
                                       "Murphy n'est donc pas garantie. "
                                       "Mesure du 28/08 (sonde_l9c_jensen) : "
                                       "568 balise-jours ont mse_comb > "
                                       "max(mse_persist, mse_clim). "
                                       "Intermittent : 351 le 29/08, 262 le "
                                       "30/08.",
                               },
                               "comb_vec": {
                                   "melange": "vecteurs (u, v) — l'espace "
                                              "de l'erreur",
                                   "colonnes": ["mse_comb_vec",
                                                "skill_comb_vec",
                                                "beats_comb_vec"],
                                   "reserve":
                                       "la borne de Jensen y tient par "
                                       "construction, mais la force du "
                                       "melange est systematiquement <= "
                                       "celle de l'autre des que les deux "
                                       "caps different : reference plus "
                                       "faible, donc skill plus flatteur. "
                                       "Ne se lit JAMAIS sans son n_comb_vec "
                                       "— la colonne est neuve le 02/09 et "
                                       "sa fenetre met quinze nuits a "
                                       "rejoindre celle de comb.",
                               },
                               "arbitrage":
                                   "les DEUX sont publiees cote a cote "
                                   "(Yann, 02/09/2026). Trois nuits de sonde "
                                   "ne tranchent pas une definition ; "
                                   "plusieurs semaines de production le "
                                   "feront, et l'une des deux disparaitra "
                                   "alors sous un verdict ecrit.",
                           },
                           "events_calibrated": EVENTS_CALIBRATED,
                           "audience": "beta"})

            # ── S13.0 : le fichier léger + le résumé des manches ──
            rounds_state = update_rounds(root, day, scores, args.dry_run)
            _publish_light(st, scores, ev_scores, rounds_state, as_of,
                           args.dry_run, duels_rows, temoin=part_temoin)
            print(f"  → manches : {rounds_state.get('nights', 0)} nuit(s) "
                  f"suivie(s) depuis le {rounds_state.get('since')}, "
                  f"{len(rounds_state.get('wins', {}))} case(s) "
                  f"zone×lead×modèle avec au moins une manche gagnée")

    # ── 6. purge ─────────────────────────────────────────────────
    if not args.no_purge:
        today = datetime.now(timezone.utc)
        sb.delete("model_verif_daily",
                  f"?day=lt.{(today - timedelta(days=RETENTION_DAILY_D)):%Y-%m-%d}")
        # Même rétention que sa sœur : la pression se rejoue depuis
        # l'archive R2 comme le vent, donc garder 30 jours en base
        # n'apporte rien de plus qu'à `model_verif_daily`.
        # ⓘ `Supabase.delete` journalise et continue sur un HTTP d'erreur
        # (cf. sa définition) : tant que le SQL du S1 n'est pas passé,
        # cette ligne écrit un ⚠️ dans le journal et ne casse rien.
        sb.delete("model_verif_daily_pres",
                  f"?day=lt.{(today - timedelta(days=RETENTION_DAILY_D)):%Y-%m-%d}")
        sb.delete("model_verif_event",
                  f"?day=lt.{(today - timedelta(days=RETENTION_EVENT_D)):%Y-%m-%d}")
        sb.delete("model_score_zone",
                  f"?as_of=lt.{(today - timedelta(days=RETENTION_SCORE_D)):%Y-%m-%d}")
        # ⛔ CETTE LIGNE A DIT LE CONTRAIRE DU 08/08 AU 25/08 : «
        # `model_character` ne se purge JAMAIS : c'est son intérêt ».
        # Elle était fausse, et pas seulement en principe — la table A
        # DÉJÀ ÉTÉ PURGÉE en vrai, le 22/08, par le `step50` (métrique
        # `speedRatio`, ~118 000 lignes). Le compte des `days` en porte
        # encore la trace : `speedRatio` plafonne à 3 quand les quatre
        # autres métriques sont à 18.
        #
        # ⚠️ CE QUI EST VRAI, C'EST AUTRE CHOSE, et c'est plus utile :
        # un accumulateur ne se périme pas par son ÂGE — il n'a pas
        # d'âge, il est mis à jour sur place — il se périme par son
        # SILENCE. À `RETENTION_CHARACTER_D` jours sans nouvelle, il
        # pèse 1,6 % d'une journée fraîche, et le jeter ne change aucun
        # chiffre affiché.
        #
        # ⓘ Mesuré le 25/08 : CETTE LIGNE NE SUPPRIME RIEN AUJOURD'HUI
        # (0 ligne concernée, la table a 18 jours). Elle est écrite pour
        # le régime permanent, et elle est ici pour que la question ne
        # se repose pas dans six mois. ⓘ Toujours vrai le 01/09
        # (1 223 107 lignes, 25 jours) — et c'est désormais MESURÉ à
        # chaque nuit plutôt que supposé : voir `_purge_caractere`, qui
        # compte avant de supprimer.
        #
        # ⓘ L'archive R2, elle, ne se purge toujours pas — ~544 Mo/an
        # mesurés, et c'est ce qui rend chaque amélioration de la
        # formule rejouable.
        _purge_caractere(sb, today)

    print(f"✅ terminé ({sb.ecritures} lignes écrites en base)")
    return 0


def _publish(st, scores: list[dict], as_of: datetime, dry_run: bool,
             meta: dict | None = None):
    """Publie le JSON que lira la PWA.

    Même patron que les packs de site : R2 sert le fichier, Supabase
    n'est pas sur le chemin de lecture. Zéro requête SQL par ouverture
    de fiche, zéro requête Open-Meteo côté pilote.
    """
    if st is None or dry_run:
        print("  ⓘ publication R2 sautée (pas de storage, ou dry-run)")
        return
    from storage import CACHE_REECRIT             # type: ignore
    # ⚠️ `audience: "beta"` VOYAGE AVEC LES CHIFFRES. Le garde de
    # l'écran est côté PWA (`isAdmin || isBetaTester`), et c'est lui qui
    # décide ; ce champ ne protège rien. Il sert à ce qu'un fichier
    # retrouvé seul, ou lu par un outil qu'on n'a pas encore écrit, dise
    # de lui-même qu'il n'est pas destiné aux pilotes. Un JSON qui ne
    # porte pas sa propre destination finit toujours par être servi à
    # quelqu'un d'autre.
    body = json.dumps({"as_of": as_of.strftime("%Y-%m-%d"),
                       **(meta or {}), "scores": scores},
                      separators=(",", ":")).encode("utf-8")
    # Clé STABLE, réécrite chaque nuit → cache court obligatoire. Un TTL
    # long laisserait un edge CDN servir un classement périmé bien après
    # le run, et le hard-refresh n'y pourrait rien (leçon des 23-24/07).
    st.put("model_scores.json", body, cache_control=CACHE_REECRIT)
    st.bilan()
    print(f"  → model_scores.json publié ({len(body) / 1024:.0f} Ko)")


if __name__ == "__main__":
    sys.exit(main())
