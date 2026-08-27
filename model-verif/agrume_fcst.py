#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/agrume_fcst.py — AGRUME entre dans le scoring
#                                            (Lot I, 13/08/2026)
#
#  Un COLLECTEUR, pas un scoreur. Il lit le produit A d'AGRUME (les
#  colonnes verticales aux balises, archivées sur R2) et en écrit le
#  vent à 10 m dans une archive NDJSON gzip, au format EXACT que
#  `collect.py` produit pour les modèles Open-Meteo. `score.py` relit
#  ce flux à côté du sien et n'a rien à savoir d'AGRUME.
#
#  ⛔ POURQUOI CE FICHIER EST DANS `model-verif/` ET PAS DANS `agrume/`.
#  AGRUME est une ENTRÉE du module de scoring, pas un module qui se
#  score lui-même (`c16bb49` a déjà retiré de l'app les champs de score
#  qu'AGRUME déclarait sans les avoir). Et la frontière du §« Séparer
#  collecte et notation » tient : un bug de formule ne doit jamais
#  pouvoir corrompre une archive irremplaçable.
#
#  ⛔ CE QUE CE FLUX NE CONSOMME PAS : le quota Open-Meteo. Il lit R2.
#  C'est structurellement le seul modèle supplémentaire qui puisse
#  entrer sans qu'un autre sorte — la fenêtre horaire d'Open-Meteo est
#  prise à 93,3 % depuis le 09/08, et c'est elle qui a tué la nuit du
#  09/08. Un lecteur pressé refera le calcul du tableau du README et
#  conclura qu'il n'y a plus de place : il y en a, elle n'est pas là.
#
#  ═══ LES TROIS DÉCISIONS DE YANN, 13/08/2026 ═══
#
#  1. ⛔ **Lead +6 h SEUL.** `LEAD_BY_OFFSET = {0: 6, 1: 24, 2: 48}`
#     classe une ligne par l'écart en JOURS entre le fichier de
#     snapshot et la journée notée, et `MIN_HOURS_DAILY` vaut 6.
#     L'archive AGRUME s'arrête à +24 h : le run 00 Z de J ne touche la
#     journée J+1 que par l'heure 00 (1 paire appariable), le run 03 Z
#     par 4. Sous le plancher de 6, donc AUCUNE ligne. Le +24 h ne
#     manque pas par oubli : il s'auto-élimine, et le banc le prouve
#     (`test_lead_24_ne_sort_aucune_ligne`). On l'ÉCRIT plutôt que de
#     le laisser lire comme un trou de données.
#     ⚠️ La variante écartée : prendre pour chaque heure le run le plus
#     VIEUX qui l'atteint encore (leads 22-24 h, journée entière). Elle
#     marche, mais AGRUME serait alors ~10 h plus frais que les autres
#     sous le même intitulé « +24 h » — un avantage silencieux.
#
#  2. ⛔ **Maille 0,01°** (`c001`). C'est la maille la plus proche du
#     site (1,1 km contre 2,8) et l'analogue direct de
#     `meteofrance_arome_france_hd`. Le vent 10 m y vient des champs
#     DÉDIÉS `10u`/`10v` (paquet SP1), pas d'un niveau hauteur — u/v
#     n'existent qu'à partir de 20 m. `--maille 0025` reste possible
#     pour mesurer l'écart, il ne change pas le nom du modèle : à
#     n'utiliser qu'à la main, jamais dans le timer.
#
#  3. ⛔ **AGRUME seul.** AROME-PI est archivé à part
#     (`agrume/pi/colonnes/`, 24 runs/jour, 10 m servi et vérifié) et
#     pourra devenir une seconde entrée. Il n'est PAS dans ce flux.
#     ⛔⛔ **LEVÉE LE 26/08/2026 — voir `MODEL_PI` ci-dessous.** PI est
#     devenu une SECONDE SÉRIE (`agrume_pi`), pas une correction
#     d'`agrume`. La décision 1 (lead +6 h) et la décision 2 (maille
#     0,01° pour la base) ne bougent pas d'une ligne.
#
#  ═══ CE QUE LA SÉRIE `agrume_pi` A CORRIGÉ, ET CE QU'ELLE N'A PAS ═══
#
#  ⛔ **Ce flux notait autre chose que ce que l'app sert.** L'écran sert
#  le composite (`agrume/composite.py` : AROME + Δ AROME-PI, avec Δ(20 m)
#  étendu constant jusqu'au 10 m). Ce collecteur, lui, lisait le vent
#  10 m BRUT du produit A et rien d'autre — il court-circuitait le
#  composite entièrement. Le score mesurait donc un produit qui n'est
#  servi à personne. C'est ce que le 26/08 répare.
#
#  ⚠️ **Et il ne répare que ça.** Δ n'est mesuré qu'au 20 m puis étendu
#  au 10 m : c'est une EXTENSION, pas une mesure (`etendre_delta` le dit
#  déjà). Si `agrume_pi` gagne, on ne saura pas encore si c'est PI ou
#  l'extension. Le vrai Δ(10 m) — `PI₁₀ − AROME 10u/10v`, deux familles
#  de champs dont rien ne dit qu'elles portent le même diagnostic —
#  reste à MESURER avant d'être câblé.
#
#  ⚠️ **L'effet attendu est petit, et ce n'est pas une déception.** PI
#  porte 6 h ; la classe « +6 h » note les 24 heures du run. Au mieux 6
#  heures sur 24 sont touchées, dont la dernière à demi (la rampe). Un
#  écart médian faible sera donc le résultat NORMAL — ce qu'on lit ici,
#  c'est le signe et l'amplitude de Δ, pas un verdict sur AROME-PI.
#
#  ═══ CE QUE CE LOT MESURE VRAIMENT, ET CE QU'IL NE MESURE PAS ═══
#
#  ⚠️ Le vent 10 m du produit A, ce sont les champs `10u`/`10v`
#  d'AROME lus par NOTRE chaîne. `composite.py` exclut explicitement le
#  10 m du Δ AROME-PI (`NIVEAUX_DELTA` retire le niveau hors HP1 :
#  « rien ne dit que ce soit le même diagnostic — une question à
#  mesurer, pas à trancher »). Le score AGRUME sortira donc TRÈS PROCHE
#  de `meteofrance_arome_france_hd`, et c'est attendu : ce lot mesure
#  notre chaîne de lecture (GRIB, plus proche voisin, coordonnées de
#  balises) contre celle d'Open-Meteo, et pose les rails. Il ne dira
#  pas encore « AGRUME est meilleur ». Un écart LARGE entre les deux
#  serait un défaut de l'une des deux chaînes, pas une nouvelle.
#
#  ⚠️ `fetched_at` porte l'heure du RUN du modèle, pas l'heure d'un
#  appel d'API — AGRUME n'en fait pas. Conséquence sur la SEULE colonne
#  qui en dépend, `lead_exact_h` : celle d'AGRUME se compte depuis le
#  run, celle des modèles Open-Meteo depuis notre appel de 03:15. Pour
#  un même run 00 Z, AGRUME affichera ~2,6 h de PLUS. Les scores
#  eux-mêmes (`err_vec_*`, `mse_*`, `bias_*`) ne dépendent pas de
#  `fetched_at` : seule la colonne de diagnostic est asymétrique, et
#  elle est asymétrique DANS LE SENS DÉFAVORABLE à AGRUME.
#
#      python3 agrume_fcst.py                      # hier, run 00 Z
#      python3 agrume_fcst.py --day 2026-08-11
#      python3 agrume_fcst.py --day 2026-08-11 --dry-run
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import io
import json
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone

# ⚠️ On APPEND `agrume/` au sys.path, on ne l'insère pas en tête : les
# deux paquets ont chacun un `sonde_r2.py`, et une insertion en tête
# ferait masquer celui de `model-verif/` dans tout processus qui
# importerait ce module. C'est aussi pourquoi on ne passe PAS par
# `agrume/sonder.py::depuis_r2`, qui fait `sys.path.insert(0, …)` à
# l'import : la clé et l'appel `Storage` tiennent en six lignes, le
# sys.path global est le vrai coût.
_ICI = pathlib.Path(__file__).resolve().parent
for _p in (_ICI.parent / "agrume", _ICI.parent / "verif",
           _ICI.parent / "tools"):
    if str(_p) not in sys.path:
        sys.path.append(str(_p))

import numpy as np                                          # noqa: E402

from collect import temoin, upload_r2, write_ndjson_gz      # noqa: E402
from colonnes import Colonnes                               # noqa: E402
# ⛔ LA RAMPE `w_PI(τ)`, LE FACTEUR DE CISAILLEMENT ET LE CHEMIN DES
# COLONNES PI S'IMPORTENT, ILS NE SE RECOPIENT PAS. Ce sont les MÊMES
# fonctions que celles du composite servi à l'écran : si un jour la
# rampe change (elle a déjà été corrigée deux fois — elle finissait à
# 7 h alors que PI s'arrête à 6 h, puis elle plafonnait à 1 alors que
# le composite doit MÉLANGER), le score suivra sans qu'on ait à y
# penser. Une seconde copie ferait exactement l'inverse : un écran et
# un score qui divergent lentement, sans qu'une ligne ne le dise.
#
# ⚠️⚠️ ET C'EST ARRIVÉ, LE 26/08 AU SOIR, DANS CE FICHIER MÊME. Le
# facteur de cisaillement a d'abord été câblé dans `etendre_delta`
# seul : l'écran l'a reçu, ce flux-ci NON — il étend Δ au 10 m par son
# propre chemin, sans passer par `etendre_delta`. Deux « AGRUME » se
# remettaient à diverger, exactement comme le matin même. C'est un banc
# qui l'a dit, pas une relecture.
from composite import facteur_cisaillement, poids_pi        # noqa: E402
from pi import cles_du_run_colonnes                         # noqa: E402
from profil import decorer_vent                             # noqa: E402
from score import fcst_agrume_key                           # noqa: E402

# ══════════════════════════════════════════════════════════════════
#  CONSTANTES
# ══════════════════════════════════════════════════════════════════

#: Le nom du modèle dans `model_verif_daily`. La colonne est du `text`
#: libre (seul CHECK : `not like '%\\_seamless'`), il n'y a ni enum ni
#: clé étrangère à migrer. Le libellé lisible vit dans
#: `src/lib/stationScore.ts::STATION_MODEL_LABELS`.
MODEL = "agrume"

#: ⛔⛔ LE COMPOSITE AROME + AROME-PI, ET POURQUOI C'EST UN SECOND NOM
#: ET PAS UNE CORRECTION D'`agrume` (arbitrage de Yann, 26/08/2026).
#:
#: Muter la série `agrume` en place introduirait une rupture de
#: DÉFINITION au milieu d'une fenêtre glissante de 14 et 30 jours : le
#: classement moyennerait de l'AROME brut d'avant-hier avec du composite
#: d'aujourd'hui, sous un seul nom, sans qu'une seule ligne ne le dise.
#: C'est exactement la classe de défaut que le lot G a été écrit pour
#: refuser — un chiffre qui reste lisse et crédible pendant que la chose
#: qu'il mesure a changé.
#:
#: ✅ ET LE SECOND NOM DONNE LA MESURE GRATUITEMENT. Les deux séries
#: portent les MÊMES balises, les MÊMES 24 heures, le MÊME run, la MÊME
#: maille pour la base. Elles ne diffèrent QUE par Δ, et seulement sur
#: les heures 0 à 5. L'écart de score entre `agrume` et `agrume_pi`
#: EST l'apport d'AROME-PI, et rien d'autre : c'est un contrôle apparié,
#: pas une comparaison entre deux populations.
MODEL_PI = "agrume_pi"

#: Le niveau où Δ = PI − AROME est MESURÉ (le plus bas des niveaux
#: communs), et celui où il est APPLIQUÉ.
#:
#: ⚠️ Ce n'est pas le même, et ce n'est pas un oubli : `composite.py`
#: étend Δ(20 m) constant sous 20 m parce qu'AROME n'a `u`/`v` qu'à
#: partir de 20 m dans `HP1`. Le 10 m d'AROME vient des champs dédiés
#: `10u`/`10v`, une AUTRE famille de champ — « rien ne dit que ce soit
#: le même diagnostic ». On reproduit donc ICI le geste que l'écran
#: fait DÉJÀ, pour que le score note le produit servi et pas une
#: variante inventée pour l'occasion.
#:
#: ⚠️⚠️ CONSÉQUENCE À NE PAS TAIRE : si `agrume_pi` gagne, on ne saura
#: pas encore si c'est PI ou l'extension. Un vrai Δ(10 m)
#: (`PI₁₀ − AROME 10u/10v`) est l'étape suivante, et elle se mesure
#: avant de se câbler.
NIVEAU_DELTA_MESURE = 20
NIVEAU_DELTA_APPLIQUE = 10

#: ⛔ LA GRILLE DE Δ EST LA MÊME DES DEUX CÔTÉS, ET C'EST LE PIÈGE
#: PRINCIPAL DE CE FLUX. PI vit en 0,025°. Calculer
#: `PI(0,025°) − AROME(0,01°)` ferait entrer l'écart de RÉSOLUTION dans
#: Δ — deux orographies différentes, deux plus proches voisins
#: différents — et on créditerait AROME-PI d'une différence de maille.
#: Δ se mesure donc en 0,025° contre 0,025°, puis s'applique à la base
#: 0,01° du score (décision 2 du lot I, inchangée).
MAILLE_DELTA = "0025"

#: ⛔ LOT L7 (27/08) — ÉLARGI DE `"pioupiou"` (une chaîne) À UN ENSEMBLE.
#: Avant ce lot, une seule source notait : la comparaison `== SOURCE_NOTEE`
#: et l'écriture `"source": SOURCE_NOTEE` étaient donc équivalentes à
#: écrire la source RÉELLE de la balise. Ce n'est plus vrai — `in` pour
#: filtrer, et `b.get("source")` (jamais `SOURCE_NOTEE` lui-même) pour
#: écrire la source de CHAQUE ligne : voir `lignes()`, où stamper
#: `SOURCE_NOTEE` tel quel aurait fait écrire "un membre quelconque de
#: l'ensemble" sur des lignes windsmobi/mf/aemet — un mensonge crédible,
#: silencieux, et qui n'aurait rougi aucun banc écrit AVANT ce lot (ils
#: ne connaissaient qu'une seule source, donc ne pouvaient pas distinguer
#: « la bonne source » de « une source »).
#:
#: `metar` est l'absent DÉLIBÉRÉ de cet ensemble : il a bien une colonne
#: dans l'axe (`freeze_balises.REFERENTIELS_RESEAUX`) depuis ce même lot,
#: mais aucun score AGRUME — `obsmetar` sert le tau inter-populations
#: (L8), pas ce flux. Les 2 radiosondages de l'axe (`RS-06610`,
#: `RS-16064`) ne sont dans AUCUN cas notés : le profil les confronte au
#: ballon, ils n'ont pas d'anémomètre au sol, et une prévision de vent
#: 10 m au-dessus d'une station de lâcher ne s'apparie à rien — ils
#: portent `source = "radiosondage"`, absent de l'ensemble par
#: construction, pas par un filtre séparé.
SOURCE_NOTEE = frozenset({"pioupiou", "windsmobi", "infoclimat", "mf",
                          "aemet"})

#: Maille par défaut du vent 10 m (décision 2 ci-dessus).
MAILLE_DEFAUT = "001"

#: L'archive est horaire, et `t0`/`step_s` est le contrat de
#: `score.fcst_times_ms`.
STEP_S = 3600

#: ⛔ LES SEULS RUNS ADMIS COMME « SNAPSHOT DU JOUR », ET LA BORNE EST
#: LE POINT DE COMPARABILITÉ. Le run 00 Z couvre les 24 heures de la
#: journée à +0…+23 h (moyenne 11,5 h) ; le 03 Z en couvre 21 à
#: +0…+20 h. Un run de 15 Z couvrirait encore 9 heures — à +0…+8 h,
#: soit un avantage de fraîcheur de dix heures sur les autres modèles,
#: sous le même intitulé « +6 h ». On préfère une journée SANS ligne
#: AGRUME à une journée où AGRUME gagne par l'horaire.
RUNS_ADMIS = (0, 3)

#: Bucket R2 du produit A. ⚠️ CE N'EST PAS CELUI DU MODULE DE SCORING,
#: et ce n'est pas non plus « wind-grid » : `wind-grid` est le nom du
#: DOS SUPABASE (`bucket_env`), le bucket R2 réel s'appelle
#: `balise-watch-grids`. Le nom de variable et le défaut sont copiés
#: mot pour mot sur `agrume/run-ingest-pi.sh` (`AGRUME_R2_BUCKET`), qui
#: fait déjà exactement ce geste — deux noms pour une seule notion,
#: c'est ainsi qu'on écrit dans le mauvais bucket sans s'en apercevoir.
BUCKET_R2_ENV = "AGRUME_R2_BUCKET"
BUCKET_R2_DEFAUT = "balise-watch-grids"
BUCKET_SUPABASE_ENV = "AGRUME_BUCKET"
BUCKET_SUPABASE_DEFAUT = "wind-grid"
PREFIXE_COLONNES = "agrume/colonnes/"

#: ⛔ LE JETON R2 ORDINAIRE DU VPS ÉCRIT SUR `balise-watch-grids` MAIS NE
#: LE LIT PAS, et c'est `prefixe_lecture()` qui choisit le bon jeu
#: d'identifiants. ⚠️ CES DEUX FONCTIONS ONT DÉMÉNAGÉ LE 22/08 (lot
#: S0.5) dans `tools/r2_lecture.py`, À L'IDENTIQUE, corps et
#: commentaires : `model-verif/arome_fcst.py` lit le MÊME bucket avec le
#: MÊME jeton contre le MÊME piège, et le chantier a déjà payé cinq
#: copies de `sb_upload`. La raison de chaque ligne est là-bas.
#:
#: Elles restent des attributs de CE module — `A.bucket_r2(...)` et
#: `A.prefixe_lecture()` du banc continuent de fonctionner sans une
#: ligne de changement.
from r2_lecture import (PREFIXES_LECTURE, bucket_r2,      # noqa: E402,F401
                        prefixe_lecture)


class Abort(Exception):
    pass


# ══════════════════════════════════════════════════════════════════
#  LIRE LE PRODUIT A — et le piège des deux buckets
# ══════════════════════════════════════════════════════════════════


def _lire_paire_r2(base: str, crier=print, quoi="produit A"):
    """`(manifeste_brut, npz_brut)` sous un préfixe R2, ou `None`.

    ⚠️ `None` veut dire « cette archive n'a pas été publiée », pas
    « erreur » — voir `lire_run`, dont c'est la règle depuis le lot I.

    ⓘ POURQUOI CETTE FONCTION EXISTE (26/08). Le produit A et les
    colonnes PI vivent dans le MÊME bucket, sous le MÊME jeton de
    lecture, avec les MÊMES deux noms de fichiers (`manifest.json` +
    `colonnes.npz`) et le MÊME piège de 403. En recopier le corps aurait
    fait une sixième copie du geste dont ce dépôt a déjà payé cinq
    exemplaires (`sb_upload`) — et une copie, c'est un endroit où la
    correction suivante n'ira pas.
    """
    from storage import Storage                              # noqa: PLC0415

    bucket = os.environ.get(BUCKET_R2_ENV) or BUCKET_R2_DEFAUT
    prefixe = prefixe_lecture()
    with bucket_r2(bucket, prefixe):
        try:
            store = Storage("agrume-verif", BUCKET_SUPABASE_ENV,
                            BUCKET_SUPABASE_DEFAUT)
        except Exception as exc:                             # noqa: BLE001
            # ⚠️ Sans `STORAGE_BACKEND=r2`, `storage.py` retombe sur le
            # dos Supabase et lève sur des variables que ce job n'a
            # aucune raison d'avoir — le défaut du 03/08 sur le poller
            # Infoclimat, puis du 07/08 ici. `run.sh` impose la
            # variable ; à la main, on le DIT au lieu de rendre une
            # trace d'import.
            raise Abort(
                f"lecture du produit A impossible ({exc}) — ce job veut "
                f"STORAGE_BACKEND=r2 et les R2_* : passer par "
                f"`run.sh agrume`, ou sourcer ~/.balise-watch-r2.env") from exc
        crier(f"  lecture du {quoi} : bucket « {bucket} », "
              f"identifiants {prefixe}* — {base}")
        try:
            brut_man = store.get(f"{base}/manifest.json")
            if not brut_man:
                return None
            brut_npz = store.get(f"{base}/colonnes.npz")
        except Exception as exc:                             # noqa: BLE001
            code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
            if code not in ("AccessDenied", "403", "InvalidAccessKeyId",
                            "SignatureDoesNotMatch"):
                raise
            # ⛔ « UN CODE D'ERREUR D'API N'EST PAS UN DIAGNOSTIC », et
            # ce projet l'a déjà payé le 10/08 : une sonde d'écriture sur
            # un bucket INEXISTANT rendait `AccessDenied`, exactement
            # comme un refus de droits. Ici c'est le symétrique, et il
            # est pire : sans `ListBucket`, S3 rend 403 pour une clé
            # ABSENTE aussi bien que pour un refus. Traiter ce 403 comme
            # « run absent » donnerait un job vert, tous les soirs, sans
            # une seule ligne AGRUME. On s'arrête, et on nomme la
            # variable à poser.
            raise Abort(
                f"{base} : lecture REFUSÉE (HTTP 403) avec les "
                f"identifiants {prefixe}*. Ce n'est pas « run absent » : "
                f"sans ListBucket, R2 rend 403 pour les deux. Poser "
                f"AGRUME_R2_READ_ACCESS_KEY_ID / "
                f"AGRUME_R2_READ_SECRET_ACCESS_KEY (jeton lecture sur "
                f"{bucket}) dans ~/.balise-watch-r2.env.") from exc
        if not brut_npz:
            # Le manifeste sans les données : ce n'est pas « absent »,
            # c'est incohérent. On le DIT au lieu de le lire comme un
            # run manquant de plus.
            raise Abort(f"{base} : manifeste présent, colonnes.npz absent")
    return brut_man, brut_npz


def lire_run(run: str, crier=print):
    """Rend `(Colonnes, manifeste)` d'un run du produit A, ou `None`.

    ⚠️ `None` veut dire « ce run n'a pas été publié », pas « erreur ».
    L'ingestion n'écrit un run que si les 8 paquets le couvrent : il
    manque des runs, c'est prévu, et un run manquant ne doit jamais se
    transformer en série de zéros.
    """
    lu = _lire_paire_r2(f"{PREFIXE_COLONNES}{run}", crier=crier,
                        quoi="produit A")
    if lu is None:
        return None
    brut_man, brut_npz = lu
    man = json.loads(brut_man.decode("utf-8"))
    return Colonnes.lire_npz(io.BytesIO(brut_npz), man)


def runs_du_jour(day: datetime) -> list[str]:
    return [f"{day:%Y-%m-%d}T{h:02d}:00:00Z" for h in RUNS_ADMIS]


def choisir_run(day: datetime, crier=print):
    """Le premier run admis qui existe. Rend `(run, col, manifeste)`."""
    for run in runs_du_jour(day):
        lu = lire_run(run, crier=crier)
        if lu is not None:
            return run, lu[0], lu[1]
        crier(f"  run {run} : absent")
    return None, None, None


# ══════════════════════════════════════════════════════════════════
#  LE VENT 10 M → LES LIGNES D'ARCHIVE
# ══════════════════════════════════════════════════════════════════

def _bloc_maille(col, maille: str):
    """`(tableau, index des niveaux, index des paramètres)` d'une maille.

    ⛔⛔ LE TABLEAU ET SES DEUX INDEX SORTENT D'ICI ENSEMBLE, ET C'EST
    TOUT L'INTÉRÊT DE CETTE FONCTION. Prendre l'index d'une maille et
    les valeurs de l'autre ne lèverait pas : `i_niveau_001[20]` et
    `i_niveau_0025[20]` valent **tous les deux 1** aujourd'hui, et les
    index de `u`/`v` coïncident aussi. La faute serait donc STRICTEMENT
    INVISIBLE — jusqu'au jour où l'une des deux listes de niveaux gagne
    une entrée, et où toutes les valeurs se décalent d'un cran sans
    qu'une seule ligne ne le dise.
    ⓘ Trouvé le 26/08 en rejouant le banc contre une variante cassée :
    la mutation « Δ pris en 0,01° » restait VERTE parce qu'elle ne
    changeait rien — la preuve qu'il y avait là un couplage à supprimer
    plutôt qu'une vérification à ajouter.
    """
    if maille == "001":
        return col.c001, col.i_niveau_001, col.i_param_001
    if maille == "0025":
        return col.c0025, col.i_niveau_0025, col.i_param_0025
    raise Abort(f"maille inconnue : {maille!r} (attendu 001 ou 0025)")


def _u_v_10m(col, maille: str):
    """Les deux tableaux `(balise, échéance)` du vent 10 m, en float32.

    ⚠️ La conversion en float32 n'est pas cosmétique : les opérations
    numpy en float16 arrondissent là où on ne s'y attend pas, et
    `isfinite` sur un float16 se comporte bien mais tout ce qui suit,
    non. `profil.py` fait le même geste, pour la même raison.
    """
    bloc, i_niv, i_par = _bloc_maille(col, maille)
    j10 = i_niv[10]
    return (bloc[:, i_par["u"], j10, :].astype(np.float32),
            bloc[:, i_par["v"], j10, :].astype(np.float32))


# ══════════════════════════════════════════════════════════════════
#  AROME-PI — Δ, et la série `agrume_pi`
# ══════════════════════════════════════════════════════════════════

def lire_run_pi(run: str, crier=print):
    """Rend `(donnees, manifeste)` des colonnes PI d'un run, ou `None`.

    ⚠️⚠️ `donnees` est `(paramètre, niveau, échéance, balise)`. Le
    produit A, lui, est `(balise, paramètre, niveau, échéance)`. Les
    deux archives ont été écrites par deux chantiers différents et rien
    ne les a jamais obligées à coïncider. Confondre les deux ordres ne
    lèverait pas : sur des comptes voisins, numpy rendrait des valeurs
    finies, plausibles, et prises sur la mauvaise balise.

    ⚠️ `None` veut dire « ce run PI n'a pas été publié ». PI sort 24
    fois par jour et l'ingestion en manque : une journée sans run PI se
    lit comme une journée sans ligne `agrume_pi`, jamais comme un
    `agrume_pi` égal à `agrume`.
    """
    # ⓘ Le chemin des colonnes PI n'est écrit qu'à UN endroit du dépôt
    # (`pi.cles_du_run_colonnes`, qui le dit lui-même), et on le lit de
    # là plutôt que de le recomposer ici. Deux écritures d'une même
    # convention, c'est ainsi qu'on finit par lire un préfixe que plus
    # personne n'alimente — la panne du 12/08 sur l'index de grille.
    cle_npz, _ = cles_du_run_colonnes(run)
    base = cle_npz.rsplit("/", 1)[0]
    lu = _lire_paire_r2(base, crier=crier, quoi="colonnes AROME-PI")
    if lu is None:
        return None
    brut_man, brut_npz = lu
    man = json.loads(brut_man.decode("utf-8"))
    with np.load(io.BytesIO(brut_npz)) as z:
        donnees = np.asarray(z["donnees"], dtype=np.float32)
        ids_npz = [str(x) for x in z["balises"]]
    # ⛔⛔ LE GARDE-FOU QUI TIENT TOUT LE RESTE. L'axe des balises est
    # écrit DEUX FOIS — dans le `.npz` et dans le manifeste — et c'est
    # le manifeste qu'on indexe (il porte `id`, `servie`, `domaine_pi`).
    # Si les deux ordres divergeaient, chaque Δ partirait sur la
    # mauvaise balise, en rendant des valeurs parfaitement crédibles.
    # On ne suppose pas qu'ils coïncident : on le VÉRIFIE, et on
    # s'arrête sinon.
    ids_man = [str(b["id"]) for b in man.get("balises", [])]
    if ids_npz != ids_man:
        raise Abort(
            f"{base} : l'axe des balises du .npz ({len(ids_npz)}) ne "
            f"coïncide pas avec celui du manifeste ({len(ids_man)}) — "
            f"refus de lire, chaque Δ partirait sur la mauvaise balise")
    return donnees, man


def delta_20m(col, pi_donnees, pi_man, crier=print):
    """Δ pondéré, par balise du produit A et par HEURE RONDE.

    Rend `{k_balise_produit_A: {heure: (w·Δu, w·Δv)}}`, en m/s.

    ── LES QUATRE RÈGLES, ET CHACUNE A SA RAISON ──────────────────────

    1. ⛔ **Même run des deux côtés.** L'appelant passe les colonnes PI
       du run AROME retenu (00 Z ou 03 Z), jamais « le PI le plus
       frais ». Prendre un PI de 05 Z sur un AROME de 00 Z donnerait à
       `agrume_pi` cinq heures de fraîcheur que les autres modèles n'ont
       pas, sous le même intitulé « +6 h » — c'est le refus du lot I
       (§ `RUNS_ADMIS`), pris par l'autre bout.

    2. ⛔ **Δ se mesure en 0,025° contre 0,025°** (`MAILLE_DELTA`), même
       si la BASE du score est en 0,01°. Voir la constante : mélanger
       les mailles ferait entrer l'écart de résolution dans Δ.

    3. ⛔ **Heures rondes SEULEMENT, par leur valeur.** PI est au pas de
       15 min, l'archive du score est horaire. On prend les échéances
       dont la minute est un multiple de 60 et on les cherche par leur
       VALEUR dans `echeances_min` — jamais par position. Conséquence
       heureuse : aucune interpolation n'est nécessaire, donc
       `composite.arome_interpole` n'est pas appelé et ne peut RIEN
       fabriquer ici. Le seul chiffre fabriqué de ce flux est
       l'extension de Δ(20 m) vers le 10 m, et elle est nommée.

    4. ⛔ **Un NaN d'un côté ou de l'autre ne donne pas de Δ.** L'heure
       retombe alors sur AROME seul — c'est un repli, pas un zéro, et il
       est compté dans le journal. Mettre 0 dirait « PI ne corrige
       rien ici », ce qui est une affirmation ; ne rien poser dit « on
       ne sait pas », ce qui est vrai.
    """
    if MAILLE_DELTA != "0025":
        raise Abort(f"maille de Δ inattendue : {MAILLE_DELTA!r}")

    # ── Les index du côté PI, LUS DANS LE MANIFESTE ────────────────────
    # ⚠️ Pas depuis `pi.NIVEAUX_PI`/`PARAMS_PI` : le manifeste décrit
    # l'archive QU'ON A EN MAIN, les constantes décrivent celle qu'on
    # écrirait aujourd'hui. Le jour où l'une des deux bouge, c'est
    # l'archive qui a raison, et ce code doit s'arrêter plutôt que de
    # lire une tranche pour une autre.
    try:
        pi_par = {p["nom"]: k for k, p in enumerate(pi_man["parametres"])}
        pi_niv = list(pi_man["niveaux_m_sol"])
        pi_min = list(pi_man["echeances_min"])
        j_pi = pi_niv.index(NIVEAU_DELTA_MESURE)
        iu_pi, iv_pi = pi_par["u"], pi_par["v"]
    except (KeyError, ValueError) as exc:
        raise Abort(
            f"le manifeste PI ne décrit pas le niveau "
            f"{NIVEAU_DELTA_MESURE} m ou les champs u/v ({exc}) — "
            f"refus de deviner la tranche") from exc

    # ── Les index du côté AROME, ET SON TABLEAU, pris ENSEMBLE ─────────
    # ⛔ `_bloc_maille` rend les trois d'un coup — voir sa docstring :
    # les séparer rendrait la faute invisible aujourd'hui et fatale
    # demain.
    bloc_ar, i_niv_ar, i_par_ar = _bloc_maille(col, MAILLE_DELTA)
    try:
        j_ar = i_niv_ar[NIVEAU_DELTA_MESURE]
        iu_ar, iv_ar = i_par_ar["u"], i_par_ar["v"]
    except KeyError as exc:
        raise Abort(
            f"le produit A n'a pas le niveau {NIVEAU_DELTA_MESURE} m en "
            f"0,025° ({exc}) — Δ est incalculable, et un Δ nul serait "
            f"un mensonge crédible") from exc

    # ── L'appariement des balises : PAR IDENTIFIANT, JAMAIS PAR RANG ──
    # ⛔ Les deux axes viennent de deux artefacts différents
    # (`quantification.balises_du_domaine()` pour PI, l'axe du produit A
    # pour l'autre). Ils se ressemblent aujourd'hui. Se fier au rang,
    # c'est se donner rendez-vous avec une balise décalée le jour où
    # l'un des deux gagne ou perd un point — et une prévision prise
    # 40 km plus loin reste finie, plausible, et fausse.
    ix_pi = {str(b["id"]): k for k, b in enumerate(pi_man.get("balises", []))
             if b.get("servie", True)}

    out: dict[int, dict[int, tuple[float, float]]] = {}
    n_hors_pi = n_repli = 0
    heures = sorted({m // 60 for m in pi_min if m % 60 == 0})

    for k, b in enumerate(col.balises):
        if b.get("source") not in SOURCE_NOTEE:
            continue
        kpi = ix_pi.get(str(b["id"]))
        if kpi is None:
            n_hors_pi += 1
            continue
        par_heure: dict[int, tuple[float, float]] = {}
        for h in heures:
            w = poids_pi(h * 60)
            if w <= 0.0:
                # τ = 6 h : la rampe est arrivée à zéro. Δ y serait
                # multiplié par 0 — autant ne pas le calculer, et
                # surtout ne pas laisser croire que PI porte cette heure.
                continue
            i_step = col.i_step.get(h)
            if i_step is None:
                continue                       # AROME n'a pas cette heure
            i_min = pi_min.index(h * 60)
            u_pi = float(pi_donnees[iu_pi, j_pi, i_min, kpi])
            v_pi = float(pi_donnees[iv_pi, j_pi, i_min, kpi])
            u_ar = float(bloc_ar[k, iu_ar, j_ar, i_step])
            v_ar = float(bloc_ar[k, iv_ar, j_ar, i_step])
            if not all(np.isfinite(x) for x in (u_pi, v_pi, u_ar, v_ar)):
                n_repli += 1
                continue
            # ⛔ DEUX facteurs, et ils répondent à deux questions
            # différentes — les confondre est ce qui a fait servir « PI
            # seul maître » pendant deux semaines :
            #   · `w`  = disponibilité × confiance (`poids_pi`) ;
            #   · `kz` = remise à l'échelle de Δ, mesuré à 20 m et
            #            appliqué à 10 m. Δ est une différence de vents,
            #            son amplitude suit celle du vent : le servir
            #            tel quel au 10 m applique une correction
            #            calibrée pour un vent 30 % plus fort.
            # ⚠️ `kz` est IMPORTÉ de `composite`, jamais recopié : c'est
            # la même règle que l'écran, et la note d'import ci-dessus
            # raconte ce qui arrive quand on l'oublie.
            f = w * facteur_cisaillement(NIVEAU_DELTA_APPLIQUE)
            par_heure[h] = (f * (u_pi - u_ar), f * (v_pi - v_ar))
        if par_heure:
            out[k] = par_heure

    crier(f"  Δ(20 m) PI−AROME : {len(out)} balises appariées, "
          f"{n_hors_pi} hors couverture PI, {n_repli} heures repliées "
          f"sur AROME faute d'une valeur des deux côtés")
    return out


def lignes(col, man: dict, maille: str = MAILLE_DEFAUT, *,
           model: str = MODEL, delta=None, extra: dict | None = None):
    """Une ligne d'archive par balise notable, au format de `collect.py`.

    ── LES DEUX SÉRIES PASSENT PAR ICI, ET C'EST VOULU ────────────────
    `delta=None` produit `agrume` : le vent 10 m du produit A, brut.
    `delta` non nul produit `agrume_pi` : le MÊME vent, plus Δ là où PI
    en donne un. ⛔ Un second corps de boucle aurait été une seconde
    occasion de se tromper de convention de direction — le défaut le
    plus coûteux du lot I, celui qui rend 180° d'écart et un score
    parfaitement crédible. Une seule boucle, un seul `decorer_vent`.

    ⛔ **Δ S'AJOUTE SUR u ET v, JAMAIS SUR LA VITESSE NI SUR L'ANGLE**,
    et AVANT `decorer_vent`. Ajouter un Δ à une vitesse déjà scalaire
    perdrait la direction ; l'ajouter à un angle donnerait 180° au
    passage de 350° à 010°. C'est la règle du composite, et elle vaut
    ici mot pour mot.

    ⚠️ **Une balise sans le moindre Δ ne sort PAS dans la série PI.**
    Elle sortirait identique à `agrume`, et gonflerait la population de
    `agrume_pi` de lignes où PI n'a rien fait — le score absolu de
    `agrume_pi` se lirait alors comme « PI n'apporte presque rien »
    alors qu'il dirait « PI n'était pas là ». La population de la série
    PI est donc un sous-ensemble de celle d'`agrume`, et c'est ce qui
    garde le contrôle apparié honnête.

    ⛔ LES ÉCHÉANCES SE RANGENT PAR LEUR VALEUR, PAS PAR LEUR POSITION.
    `score.fcst_times_ms` reconstitue les heures par `t0 + i × step_s` :
    une série écrite dans l'ordre du tableau, sur un run dont les
    échéances ne seraient pas contiguës, décalerait TOUTES les heures
    d'après le trou — silencieusement, et du bon ordre de grandeur pour
    passer inaperçu. C'est exactement le défaut de dé-accumulation
    positionnelle trouvé à l'audit du 13/08. Ici : on alloue
    `max(échéances) + 1` cases et on pose chaque valeur à SON heure ;
    les trous restent `None`.
    """
    u10, v10 = _u_v_10m(col, maille)
    steps = [int(s) for s in col.steps]
    if not steps:
        return
    n = max(steps) + 1
    run_dt = datetime.strptime(man["run"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc)
    t0 = int(run_dt.timestamp())

    for k, b in enumerate(col.balises):
        if b.get("source") not in SOURCE_NOTEE:
            continue
        d_balise = None if delta is None else delta.get(k)
        if delta is not None and not d_balise:
            # Aucune heure corrigée : cette balise n'appartient pas à la
            # série PI. Voir la docstring — ce n'est pas une omission.
            continue
        speed: list[float | None] = [None] * n
        direction: list[float | None] = [None] * n
        for i, step in enumerate(steps):
            u, v = float(u10[k, i]), float(v10[k, i])
            if not (np.isfinite(u) and np.isfinite(v)):
                # ⛔ Une absence reste une absence. Un 0 serait une
                # valeur de vent parfaitement crédible, et le scoring
                # noterait « le modèle annonçait calme » sur une case
                # que le modèle n'a jamais remplie.
                continue
            if d_balise is not None:
                # ⚠️ `.get(step)`, pas `.get(i)` : `delta` est indexé par
                # l'HEURE d'échéance, `u10` par la POSITION dans le
                # tableau. Sur un run contigu les deux coïncident, et
                # c'est précisément pourquoi la confusion passerait
                # inaperçue jusqu'au premier run troué.
                d = d_balise.get(step)
                if d is not None:
                    u, v = u + d[0], v + d[1]
            p = decorer_vent({"u": u, "v": v})
            speed[step] = p["vitesseKmh"]
            direction[step] = p["directionDeg"]
        # Même règle que `collect.py` : une balise sans une seule valeur
        # ne rentre pas dans l'archive sous forme de nulls.
        if all(s is None for s in speed):
            continue
        ligne = {
            "station_id": str(b["id"]),
            # ⛔ `b.get("source")`, JAMAIS `SOURCE_NOTEE` — cf. l'arbitrage
            # sur SOURCE_NOTEE ci-dessus. Un ensemble n'est pas une valeur.
            "source": b.get("source"),
            "lat": b.get("lat"), "lon": b.get("lon"),
            "model": model,
            # L'heure du RUN, pas celle d'un appel d'API — cf. l'en-tête.
            "fetched_at": run_dt.isoformat(),
            "t0": t0, "step_s": STEP_S,
            "speed": speed, "dir": direction,
            # Deux champs de traçabilité que `score.py` ignore : sans
            # eux, l'archive ne dirait pas de quel run ni de quelle
            # maille elle sort, et le jour où l'on change l'un des deux
            # les séries d'avant et d'après seraient indistinguables.
            "agrume_run": man["run"],
            "agrume_maille": maille,
        }
        if extra:
            # ⓘ La traçabilité de la série PI : le run PI, et les deux
            # niveaux (celui où Δ a été MESURÉ, celui où il a été
            # APPLIQUÉ). Sans eux, une archive d'avant et une archive
            # d'après un changement de convention seraient
            # indistinguables.
            ligne.update(extra)
        if delta is not None:
            # ⛔ CE COMPTE APPARTIENT À LA SÉRIE, PAS À `extra`. Une
            # ligne PI dont une seule heure aurait été corrigée est
            # indistinguable d'une ligne pleinement composite sans lui —
            # et c'est exactement la nuance qui expliquera un écart de
            # score faible. Le laisser dépendre d'un argument optionnel,
            # c'est se donner un chemin où il manque.
            ligne["agrume_pi_heures"] = len(d_balise or {})
        yield ligne


# ══════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="/var/lib/bw-model-verif")
    ap.add_argument("--day", default=None,
                    help="journée à archiver (défaut : hier, comme score.py)")
    ap.add_argument("--maille", default=MAILLE_DEFAUT, choices=("001", "0025"),
                    help="⚠️ à la main seulement : le nom du modèle ne change "
                         "pas, deux mailles dans la même archive seraient "
                         "deux séries sous un seul nom")
    ap.add_argument("--run", default=None,
                    help="forcer un run précis (2026-08-13T00:00:00Z)")
    ap.add_argument("--sans-pi", action="store_true",
                    help="ne produire que la série `agrume` (sans AROME-PI). "
                         "⚠️ À la main seulement : dans le timer, une "
                         "journée sans agrume_pi doit venir d'un run PI "
                         "absent, pas d'un drapeau qu'on a oublié d'enlever")
    ap.add_argument("--dry-run", action="store_true",
                    help="tout lire, tout compter, n'écrire ni fichier ni R2")
    args = ap.parse_args()

    root = pathlib.Path(args.out)
    day = (datetime.strptime(args.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
           if args.day
           else datetime.now(timezone.utc) - timedelta(days=1)).replace(
               hour=0, minute=0, second=0, microsecond=0)
    print(f"▶ journée archivée : {day:%Y-%m-%d} — flux AGRUME, maille "
          f"0,{'01' if args.maille == '001' else '025'}°")

    try:
        if args.run:
            lu = lire_run(args.run)
            run, col, man = (args.run, lu[0], lu[1]) if lu else (None, None, None)
        else:
            run, col, man = choisir_run(day)
    except Abort as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1

    if col is None:
        # ⚠️ Ce n'est pas une erreur : ni au démarrage, ni le jour où
        # l'ingestion a manqué ses 8 paquets. Mais ça se DIT, sinon une
        # journée sans AGRUME se lirait comme une journée où AGRUME
        # n'avait rien à dire.
        print(f"  aucun run admis pour {day:%Y-%m-%d} "
              f"({', '.join(runs_du_jour(day))}) — aucune ligne AGRUME "
              f"cette journée-là.")
        return 0

    rows = list(lignes(col, man, args.maille))
    n_pas = len(col.steps)
    horizon = max(int(s) for s in col.steps) if col.steps else 0
    n_axe = len(col.balises)
    print(f"  run retenu : {run} — {n_axe} points d'archive, "
          f"{n_pas} échéances (0 → {horizon} h)")
    print(f"  {len(rows)} balises ({', '.join(sorted(SOURCE_NOTEE))}) avec "
          f"au moins une valeur de vent 10 m")

    # ── La seconde série : AGRUME + AROME-PI ──────────────────────────
    # ⛔ ELLE S'AJOUTE, ELLE NE REMPLACE PAS. Et son absence n'est JAMAIS
    # une erreur du job : PI peut manquer (24 runs/jour, l'ingestion en
    # rate), et une journée sans `agrume_pi` doit se lire comme telle,
    # pas comme un `agrume_pi` silencieusement égal à `agrume`.
    rows_pi: list[dict] = []
    if args.sans_pi:
        print("  (--sans-pi) série agrume_pi non produite")
    else:
        try:
            lu_pi = lire_run_pi(run)
        except Abort as exc:
            # ⚠️ On NE fait PAS tomber le job : la série `agrume` est
            # déjà calculée et son archive est le produit principal.
            # Mais on le DIT sur stderr, et le code de sortie le portera.
            print(f"⚠️  colonnes PI illisibles ({exc}) — série agrume_pi "
                  f"absente cette journée-là", file=sys.stderr)
            lu_pi = None
        if lu_pi is None:
            print(f"  aucune colonne AROME-PI pour le run {run} — "
                  f"aucune ligne {MODEL_PI} cette journée-là.")
        else:
            pi_donnees, pi_man = lu_pi
            d = delta_20m(col, pi_donnees, pi_man)
            rows_pi = list(lignes(
                col, man, args.maille, model=MODEL_PI, delta=d,
                extra={"agrume_pi_run": pi_man["run"],
                       "agrume_delta_mesure_m": NIVEAU_DELTA_MESURE,
                       "agrume_delta_applique_m": NIVEAU_DELTA_APPLIQUE,
                       "agrume_delta_maille": MAILLE_DELTA}))
            n_h = sum(r["agrume_pi_heures"] for r in rows_pi)
            print(f"  {len(rows_pi)} balises {MODEL_PI}, "
                  f"{n_h} heures corrigées par PI "
                  f"({n_h / max(1, len(rows_pi)):.1f} par balise sur "
                  f"{n_pas} échéances)")
            rows = rows + rows_pi

    if not rows:
        print("❌ le run existe mais aucune balise n'a de vent 10 m — "
              "ce n'est pas un run vide, c'est un run cassé.", file=sys.stderr)
        return 1

    key = fcst_agrume_key(day)
    if args.dry_run:
        exemple = rows[0]
        n_val = sum(1 for s in exemple["speed"] if s is not None)
        print(f"  (dry-run) {key} — exemple : balise {exemple['station_id']}, "
              f"{n_val} heures servies sur {len(exemple['speed'])}")
        return 0

    path = root / key
    n = write_ndjson_gz(path, rows)
    ko = path.stat().st_size / 1024
    print(f"  écrit : {path} ({n} lignes, {ko:.1f} Ko)")

    if not upload_r2(path, key):
        # Même politique que `collect.py` : le local reste, le témoin
        # n'est pas posé, `rattraper()` réessaiera — et le run SORT EN
        # ERREUR plutôt que d'annoncer un succès sur une archive qui
        # n'existe que sur le disque d'une machine que personne ne
        # sauvegarde.
        print("❌ archive AGRUME non montée sur R2 (conservée localement)",
              file=sys.stderr)
        return 2
    print(f"  témoin posé : {temoin(path).name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
