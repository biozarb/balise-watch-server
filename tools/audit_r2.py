#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  audit_r2.py — la jauge R2 : ce qu'il y a VRAIMENT dans les buckets
#                                                        (10/08/2026)
#
#  ⚠️ POURQUOI CE FICHIER EXISTE, ALORS QUE `verifier_dimensionnement`
#     EXISTE DÉJÀ.
#
#  `storage.py::verifier_dimensionnement` est un garde-fou **a priori** :
#  il chiffre ce qu'une chaîne s'apprête à écrire et refuse de démarrer
#  si la projection dépasse un seuil. Excellent, et ça reste la première
#  ligne de défense.
#
#  Mais il ne peut pas voir ce qui a déjà été écrit et jamais effacé.
#  Or c'est exactement ce qui a cassé le projet deux fois le 30/07 :
#  « aucune des 4 chaînes d'ingestion ne contient un seul `delete` »
#  (audit_storage.py). Une projection juste et une réalité qui dérive
#  ne se contredisent pas — elles ne parlent pas de la même chose.
#
#  Et surtout : les deux dépassements ont été découverts par un MAIL DU
#  FOURNISSEUR, pas par le projet. R2 n'a pas de coupe-circuit — dépasser
#  le palier ne bloque rien, ça facture. La seule protection est une
#  jauge qu'on pose soi-même.
#
#  Ce script est cette jauge. Il répond à trois questions :
#     1. combien pèse le compte AUJOURD'HUI, par bucket et par préfixe ?
#     2. à quelle VITESSE ça monte (Go/mois, mesuré, pas estimé) ?
#     3. à ce rythme, QUAND touche-t-on le palier ?
#
#  La question 3 est la seule qui serve vraiment : elle alerte AVANT le
#  dépassement, pas pendant. Un seuil seul dit « trop tard » ; une pente
#  dit « dans 47 jours ».
#
#  ⚠️ LA PENTE EST LA SOMME DES PENTES PAR PRÉFIXE, et chaque pente est
#     un QUANTILE BAS DE DIFFÉRENCES (25e centile), jamais des moindres
#     carrés. QUATRE marches réelles ont chacune fabriqué une fausse
#     échéance, et les trois premières un cran plus bas que la
#     précédente : un BUCKET apparu le 10/08, un PRODUIT le 13/08 dans un
#     bucket déjà connu, un DOMAINE le 16/08 dans un préfixe déjà connu,
#     puis le 17/08 DEUX marches dans la même fenêtre.
#
#     Les deux premiers correctifs ont déplacé la granularité ; le
#     troisième a montré que c'était la mauvaise question. Descendre
#     encore (profondeur 3) met 3,39 Go sur 3,41 « hors échéance »
#     — mesuré le 16/08 sur le compte réel. Ce qui manquait n'était pas
#     de la finesse mais un calcul qui ne confonde pas une MARCHE avec
#     une PENTE ; le quatrième a montré qu'ignorer UNE marche ne suffit
#     pas, il faut en ignorer plusieurs. Voir `_pente_basse` et
#     `MINI_RELEVES`.
#
#  ⚠️ ET UN OBJET NON RÉCLAMÉ N'EST PAS FORCÉMENT UN ORPHELIN : pendant
#     la publication d'un run, les objets existent et l'index ne les
#     déclare pas encore. C'est ce qui a fait partir le second faux mail
#     du 17/08. La frontière est l'ÂGE, jamais un nombre toléré — voir
#     `GRACE_EN_VOL_H`.
#
#  ⛔ ET LA PENTE NE SUFFIT PAS. Elle répond à « ça monte ? » ; elle ne
#     répondra jamais à « ce qui est là est-il légitime ? ». Une jauge
#     qui n'a que la pente est aveugle à une croissance faite UNIQUEMENT
#     de marches — un domaine de plus, une boîte élargie, et rien n'a de
#     tendance. Pour les produits qui publient un index (`agrume/grille`,
#     `agrume/pi/grille`), la jauge confronte donc l'index au bucket :
#     tout objet présent doit être RÉCLAMÉ par quelqu'un. Un agrandissement
#     ne crée aucun orphelin ; une purge qui cesse de mordre en crée dès
#     la nuit suivante. Voir `PRODUITS_INDEXES` et `rapprocher`.
#
#  ⚠️ LECTURE SEULE. Ce script ne supprime RIEN, jamais, sous aucune
#     option. Les purges sont ailleurs et séparées exprès
#     (`purge_isobars_orphans.py`, `purge_windgrid_orphans.py`).
#
#  ⚠️ LE PALIER GRATUIT EST PAR COMPTE, PAS PAR BUCKET. C'est la raison
#     pour laquelle ce script énumère TOUS les buckets et somme. Auditer
#     `balise-watch-grids` seul aurait dit « 825 Mo, tout va bien » en
#     ignorant `model-verif` et `balise-watch-packs`.
#
#  Usage :
#      run.sh garde-fou-r2                  # nominal, via systemd
#      python3 tools/audit_r2.py --out /tmp # à la main, sans historique
#      python3 tools/audit_r2.py --json     # sortie machine
#
#  Environnement : R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY
#      (dans ~/.balise-watch-r2.env, format `export VAR=…`)
#  Optionnel : BW_R2_BUCKETS  — liste de repli, séparée par des virgules,
#      si le jeton n'a pas le droit `ListBuckets` (voir §buckets).
#      BW_R2_SEUIL_GO — seuil d'alerte, défaut 7,0.
#
#  Code de sortie : 0 tout va bien · 1 seuil franchi ou échéance proche
#  · 2 erreur d'exécution. C'est `run.sh` qui transforme le 1 en ping
#  d'échec Healthchecks et en e-mail — ce script ne sait qu'alerter en
#  rendant non nul, comme `collect.py` et `score.py`.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# ⚠️ Importés, PAS recopiés. La leçon de `LEVELS` dupliqué entre
# `arome-wind/ingest.py` et `web/src/lib/config.ts` (404 silencieux le
# jour où les deux listes divergent) vaut aussi pour des seuils : deux
# copies d'un palier, c'est un jour où l'une des deux ment.
from storage import (  # noqa: E402
    PALIER_CLASS_A_MOIS,
    PALIER_STOCKAGE_GO,
    SEUIL_STOCKAGE_GO,
)

# Seuil d'ALERTE, distinct du seuil d'arrêt de `verifier_dimensionnement`
# (5 Go). Celui-ci est plus haut exprès : 5 Go arrête une chaîne AVANT
# qu'elle n'écrive ; 7 Go prévient un humain qu'il reste de la marge mais
# plus beaucoup. Deux rôles, deux valeurs — les confondre ferait soit
# alerter trop tôt (et on cesserait de lire), soit arrêter trop tard.
SEUIL_ALERTE_GO = float(os.environ.get("BW_R2_SEUIL_GO", "7.0"))

# On alerte AUSSI si la pente amène au palier avant cette échéance, même
# si le total du jour est bas. 60 jours : de quoi voir venir et décider
# posément (purge ? float16 ? restriction du périmètre ?) plutôt que
# dans l'urgence d'un mail de facturation.
HORIZON_ALERTE_JOURS = int(os.environ.get("BW_R2_HORIZON_JOURS", "60"))

# Profondeur de regroupement des clés. 2 = `arome/sol`, `arome/alt`,
# `agrume/cube`… C'est le niveau où les décisions se prennent (une
# chaîne, un produit) ; à 1 tout serait « arome », à 3 on noierait le
# tableau sous les échéances.
PROFONDEUR_PREFIXE = int(os.environ.get("BW_R2_PROFONDEUR", "2"))

# ⚠️ CINQ RELEVÉS, PAS QUATRE — LA LEÇON DU 17/08, qui corrige celle du
# 16/08 sans l'effacer. Le 16/08 disait : quatre relevés font TROIS
# différences, et la médiane de trois valeurs ignore toujours l'extrême,
# donc une marche ISOLÉE ne peut plus être la médiane. C'était vrai — et
# le mot qui coûtait était ISOLÉE.
#
# Dans la nuit du 16 au 17/08, la série de `agrume/grille` valait
# 2,002 · 2,002 · 2,422 · 4,054 Go : DEUX marches consécutives
# (tarn-aveyron-hérault le 15, la boîte élargie des Alpes le 16) pour
# trois différences — 0 · +0,420 · +1,632. La médiane est tombée PILE
# sur la première marche : +11,12 Go/mois pour ce préfixe, « palier
# atteint dans 12 jours », et le mail est parti sur un compte à 4,4 Go
# sur 10 dont le plateau mesuré valait 3,375 Go et l'index 0 orphelin.
#
# ⛔ Le motif est celui écrit dans BUGS.md le 16/08 au soir : corriger
# UNE cause laisse en place le mécanisme qui transforme cette cause en
# dégât. Le dégât, ici, c'est qu'une différence entre deux relevés
# serve d'estimateur de tendance ; une marche n'en est qu'un
# déclencheur, et rien n'a jamais promis qu'il n'y en aurait qu'une par
# fenêtre.
#
# D'où le 25e CENTILE plutôt que la médiane. Sur n différences il ignore
# les trois quarts les plus grandes : quatre différences (donc CINQ
# relevés) rendent l'estimateur insensible aux DEUX plus grandes, cinq
# différences aux TROIS plus grandes. Ajouter un domaine ne peut donc
# plus faire partir un mail, quel qu'en soit le nombre dans la fenêtre.
#
# ⚠️ ET LE PRIX, DIT PLUTÔT QUE DÉCOUVERT. Une fuite reste vue parce que
# TOUTES ses différences sont positives : un quantile bas sur une série
# de fuite vaut le débit de la fuite (`test_une_vraie_fuite_reste_vue`).
# Ce qui se paie, c'est la croissance en ESCALIER, désormais
# sous-estimée plus fort qu'avec la médiane. C'est le contrat de
# comptabilité (`PRODUITS_INDEXES`) qui couvre ce trou pour les produits
# à rétention — et il le couvre mieux qu'une pente ne l'a jamais fait.
MINI_RELEVES = int(os.environ.get("BW_R2_MINI_RELEVES", "5"))

# Le quantile pris sur les différences. 0,25 : assez bas pour ignorer
# deux marches sur quatre différences, assez haut pour ne pas se réduire
# au MINIMUM — un minimum ferait taire la jauge dès qu'une seule nuit est
# plate, ce qu'une purge à cadence irrégulière produit toute seule.
QUANTILE_PENTE = float(os.environ.get("BW_R2_QUANTILE_PENTE", "0.25"))

# ⚠️ Deux relevés à 24 SECONDES d'intervalle ne mesurent pas une vitesse.
# L'historique réel en contient : le 10/08, la jauge a tourné six fois
# en une heure (déploiement, puis arrivée du jeton d'audit). Une
# différence divisée par 24 s vaut des milliers de Go/mois — les
# moindres carrés noyaient ça dans la masse, une médiane de différences
# pourrait la prendre pour la valeur centrale. Les relevés plus
# rapprochés que ce pas sont donc REGROUPÉS, et c'est le plus récent du
# groupe qui compte : le 10/08, c'est celui qui voyait enfin les trois
# buckets.
ESPACEMENT_MINI_JOURS = float(os.environ.get("BW_R2_ESPACEMENT_MINI", "0.25"))

# ⚠️ LES PRODUITS INDEXÉS — LE CONTRAT DE COMPTABILITÉ (16/08).
#
# La pente répond à « ça monte ? ». Elle ne répond PAS à « ce qui est là
# est-il légitime ? », et c'est une autre question — celle qui compte
# pour un produit à rétention, dont le poids est censé être un plateau.
#
# Ces produits publient un `index.json` qui déclare, CLÉ PAR CLÉ, tout
# ce qui doit exister sous leur préfixe (c'est ce qui leur permet de
# purger sans jamais faire de ListObjects). Le rapprochement est donc
# gratuit ici : le listing est déjà fait pour la jauge, il ne manque que
# la lecture de l'index — 1 opération classe B par produit.
#
# ⛔ CE QUE ÇA CHANGE : un octet de plus ne dit rien, un objet que
# personne ne réclame dit tout. Agrandir une boîte augmente le poids
# sans créer un seul orphelin ; une purge qui cesse de mordre en crée
# immédiatement. La marche et la fuite, que la pente confond par
# construction, sont ici SÉPARÉES — et la fuite se voit dès la nuit
# suivante au lieu de trois jours plus tard.
#
# ⚠️ Contrôle du 16/08 avant d'écrire une ligne de ce code : 496 clés
# réclamées / 496 présentes pour `agrume/grille` (0 orphelin, la
# rétention mord), et 7 réclamées / 25 présentes pour `agrume/pi/grille`
# — soit les 18 orphelins du `TypeError` de `purger()` des 12-13/08,
# trouvés à la main ce jour-là et TOUJOURS là. Ce mécanisme les aurait
# nommés le lendemain matin.
#
# ⛔ 17/08 (Lot L2) — LE RAFRAÎCHISSEMENT PI ENTRE ICI DANS LE MÊME
# COMMIT QUE SA PUBLICATION, et pas « au prochain passage ». C'est le
# produit le plus exposé des trois : il s'écrit 24 fois par jour (contre
# 8), il pèse 58,3 Mo par run, et ses deux jumeaux peuvent rester
# DÉPAREILLÉS si une écriture casse au milieu — auquel cas
# `rafraichissement.ecrire()` inscrit quand même les clés déjà écrites
# dans l'index pour qu'elles soient purgées. Sans cette ligne-ci, une
# purge qui cesserait de mordre ferait croître le bucket de 1,4 Go par
# jour sans qu'aucun voyant ne s'allume : `ListObjects` n'est pas une
# route de production, et la pente confondrait la fuite avec une marche.
PRODUITS_INDEXES = (
    ("balise-watch-grids", "agrume/grille/index.json", "agrume/grille/"),
    ("balise-watch-grids", "agrume/pi/grille/index.json", "agrume/pi/grille/"),
    ("balise-watch-grids", "agrume/pi/rafraichissement/index.json",
     "agrume/pi/rafraichissement/"),
    # ⛔ 20/08 (Lot Q2) — LA PLUIE À VENIR ENTRE ICI DANS LE MÊME COMMIT
    # QUE SA PUBLICATION, et c'est le produit le plus exposé des quatre :
    # il s'écrit **144 fois par jour** (contre 24 pour le rafraîchissement
    # et 8 pour le produit B) et pèse 28,8 Mo par passe.
    #
    # Le calcul qui décide de cette ligne : si la purge cessait de mordre,
    # ce produit ajouterait **4,1 Go par jour**. La jauge était à 4,4 Go
    # sur 10 le 17/08 — le palier serait donc franchi en un peu plus de
    # VINGT-QUATRE HEURES. Une pente ne verrait rien avant trois relevés,
    # c'est-à-dire trois nuits ; le rapprochement index/bucket, lui, nomme
    # l'orphelin dès le lendemain matin.
    #
    # ⚠️ Et le délai de grâce joue en notre faveur ici : une passe se
    # publie en quelques secondes, très loin des 3 h de `GRACE_EN_VOL_H`.
    # Un objet non réclamé sous ce préfixe est donc un vrai orphelin, pas
    # une publication en vol — contrairement au produit B, dont la
    # publication dure une heure.
    ("balise-watch-grids", "agrume/piaf/index.json", "agrume/piaf/"),
)

# ⚠️ LE DÉLAI DE GRÂCE — LA COURSE DU 17/08, ET POURQUOI ELLE N'EST PAS
# UNE ERREUR DE L'ORDRE D'ÉCRITURE.
#
# La publication d'un run écrit les OBJETS d'abord, l'INDEX ensuite (voir
# `grille.py` : l'inverse laisserait, en cas de panne, des objets que
# rien ne sait plus nommer — une fuite invisible plutôt qu'un 404
# visible). Entre les deux, ces objets sont présents et réclamés par
# personne : ils ressemblent trait pour trait à un orphelin.
#
# Mesuré la nuit du 17/08 : l'audit de 04:32 UTC est tombé PILE dedans —
# les 55 clés de `nord-alpes/2026-08-17T00:00:00Z` et 27 des 55 de
# `pyrenees/…`, soit 82 objets, 0,679 Go. L'index les a réclamées à
# 05:29, une heure plus tard. Le mail est parti sur « la purge de ce
# produit ne mord plus » alors qu'elle mordait : contrôlé le même matin,
# 496 présentes / 496 réclamées, 0 orphelin, plateau à 3,375 Go.
#
# ⛔ Lire l'index APRÈS le listing (ce que `main` fait déjà) ne suffit
# pas : la fenêtre à couvrir n'est pas la durée de l'audit (3 s) mais
# celle de la publication (une heure).
#
# Ce qui sépare vraiment les deux, c'est l'ÂGE, et le listing le donne
# gratuitement (`LastModified`) : un run en vol vient d'être écrit, un
# orphelin, lui, ne rajeunit jamais — les 18 du `TypeError` du 12/08
# avaient trois jours quand on les a trouvés. Un objet non réclamé plus
# jeune que ce délai est donc compté « en vol » : dit dans le rapport,
# jamais fatal. S'il est encore là demain matin, il a vieilli, et il
# crie.
#
# 3 h = LE PAS ENTRE DEUX RÉSEAUX AROME. Une publication qui n'a pas
# fini de se déclarer avant le réseau suivant n'est plus « en cours » :
# c'est une anomalie, et elle doit crier.
GRACE_EN_VOL_H = float(os.environ.get("BW_R2_GRACE_EN_VOL_H", "3.0"))

GO = 1_000_000_000  # R2 facture en Go décimaux, pas en Gio — ne pas
                    # « corriger » en 1024³ : ça sous-estimerait de 7 %
                    # et le palier est justement ce qu'on frôle.


class Abort(Exception):
    """Erreur d'exécution — code de sortie 2. Distincte d'un seuil
    franchi (code 1), qui n'est pas un bug mais un résultat."""


# ══════════════════════════════════════════════════════════════════════
#  PARTIE PURE  —  aucune E/S, donc testable sans réseau
# ══════════════════════════════════════════════════════════════════════
def prefixe_de(cle: str, profondeur: int = PROFONDEUR_PREFIXE) -> str:
    """`arome/sol/2026/tuile-3.json` → `arome/sol`.

    Une clé sans slash (`manifest.json` à la racine) rend `(racine)`, et
    pas la clé elle-même : sinon un bucket plat produirait une ligne de
    tableau par objet, et le rapport deviendrait illisible au moment
    précis où on en aurait besoin.
    """
    morceaux = [m for m in cle.split("/") if m]
    if len(morceaux) <= 1:
        return "(racine)"
    return "/".join(morceaux[:profondeur])


def agreger(objets) -> dict:
    """`objets` = itérable de (bucket, cle, taille_octets).

    Rend un inventaire {total, par_bucket, par_prefixe, nb_objets}.
    Séparé de la lecture réseau EXPRÈS : c'est ce qui permet au banc de
    rejouer un compte de 12 Go sans jamais toucher Cloudflare.
    """
    total = 0
    nb = 0
    par_bucket: dict[str, dict] = {}
    par_prefixe: dict[str, dict] = {}
    # ⚠️ Déballage par INDEX et pas par motif : depuis le 17/08, les
    #    tuples portent une quatrième valeur (`LastModified`, dont
    #    `rapprocher` a besoin pour l'âge). L'inventaire n'en a que faire,
    #    et les bancs écrits avant cette date passent des triplets — les
    #    deux formes doivent vivre côte à côte.
    for o in objets:
        bucket, cle, taille = o[0], o[1], o[2]
        total += taille
        nb += 1
        b = par_bucket.setdefault(bucket, {"octets": 0, "objets": 0})
        b["octets"] += taille
        b["objets"] += 1
        p = f"{bucket}:{prefixe_de(cle)}"
        e = par_prefixe.setdefault(p, {"octets": 0, "objets": 0})
        e["octets"] += taille
        e["objets"] += 1
    return {"octets": total, "objets": nb,
            "par_bucket": par_bucket, "par_prefixe": par_prefixe}


def meme_perimetre(releve: dict, perimetre) -> bool:
    """Ce relevé porte-t-il sur exactement les mêmes buckets ?

    ⚠️ AJOUTÉ APRÈS COUP, LE 10/08, PARCE QUE ÇA A MENTI EN VRAI. Le
    matin, la jauge tournait en couverture PARTIELLE (2 buckets, 0,031 Go).
    À midi, le jeton d'audit est arrivé et elle a vu les 3 buckets
    (0,815 Go). Les deux relevés sont allés dans le même historique, et
    la régression y a lu une marche de +0,78 Go en trente minutes :
    **+587 Go/mois, palier atteint dans 0 jours**. Alerte parfaitement
    absurde, et elle serait partie par mail.

    Une marche due à un changement de PÉRIMÈTRE n'est pas une croissance.
    La pente ne se calcule donc qu'entre relevés comparables : mêmes
    buckets, même couverture. Un bucket ajouté demain remettra le
    compteur à zéro — c'est voulu, mieux vaut « pas de pente » que « une
    pente fausse ».
    """
    if perimetre is None:
        return True
    b = releve.get("buckets")
    return b is not None and frozenset(b.keys()) == perimetre


def _moindres_carres(pts) -> float | None:
    """Pente en Go/mois d'une série de (datetime, Go).

    ⚠️ CE N'EST PLUS LE CALCUL DE PRODUCTION depuis le 16/08 — voir
    `_pente_basse`. Gardé parce qu'il reste le CONTRE-EXEMPLE des
    bancs : c'est lui qui rejoue, sur les trois marches réelles, le faux
    qu'on a corrigé. Le supprimer effacerait la démonstration en même
    temps que le code.

    ⚠️ Une simple différence entre le premier et le dernier point serait
    fausse ici : le volume oscille d'un run à l'autre (une chaîne à
    rétention courte écrit puis purge). C'est la TENDANCE qu'on veut, et
    deux points suffisent à la calculer mais pas à la croire — d'où le
    `None` sous trois points, qui vaut mieux qu'une pente inventée sur
    une oscillation.
    """
    if len(pts) < 3:
        return None
    t0 = pts[0][0]
    xs = [(t - t0).total_seconds() / 86400.0 for t, _ in pts]
    ys = [go for _, go in pts]
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom <= 0:            # tous les points le même jour
        return None
    a = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denom
    return a * 30.0


def _degrouper(pts, mini: float = ESPACEMENT_MINI_JOURS):
    """Une rafale de relevés rapprochés ne compte que pour UN point.

    Voir `ESPACEMENT_MINI_JOURS`. On garde le plus RÉCENT de chaque
    groupe, pas le premier : le 10/08, c'est le dernier de la rafale qui
    portait enfin la couverture complète.
    """
    garde: list = []
    for t, y in sorted(pts, key=lambda p: p[0]):
        if garde and (t - garde[-1][0]).total_seconds() / 86400.0 < mini:
            garde[-1] = (t, y)
            continue
        garde.append((t, y))
    return garde


def _quantile(valeurs, q: float) -> float:
    """Le quantile `q` par interpolation linéaire entre rangs — la
    définition usuelle (celle de `numpy.percentile`), écrite ici parce
    que `statistics.quantiles` découpe en classes et ne rend pas la même
    chose sur quatre valeurs.

    ⚠️ Interpolation et pas rang le plus proche : sur quatre différences,
    le rang le plus proche du 25e centile EST le minimum, et un minimum
    est justement ce qu'on ne veut pas (voir `QUANTILE_PENTE`).
    """
    s = sorted(valeurs)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    bas = int(pos)
    haut = min(bas + 1, len(s) - 1)
    return s[bas] + (s[haut] - s[bas]) * (pos - bas)


def _pente_basse(pts) -> float | None:
    """Pente en Go/mois : le 25e CENTILE des vitesses entre relevés
    consécutifs. C'est le calcul de production depuis le 17/08 — il
    remplace la médiane du 16/08, qui ne survivait pas à DEUX marches
    dans la même fenêtre (voir `MINI_RELEVES`, où l'incident est chiffré).

    La propriété visée, et elle est plus forte que celle de la médiane :
    un quantile bas ignore les grandes différences *en nombre*, pas
    seulement l'extrême. Quatre différences en absorbent deux, cinq en
    absorbent trois — donc ajouter un domaine, ou deux, ou une boîte
    élargie par-dessus, ne fabrique plus de pente.

    ⚠️ LE PRIX, DIT PLUTÔT QUE DÉCOUVERT : une croissance réellement EN
    ESCALIER est sous-estimée, et plus fort qu'avant. Une fuite, elle,
    est continue — toutes ses différences valent le débit, donc un
    quantile bas le rend aussi — c'est le cas qu'on surveille, et
    `test_une_vraie_fuite_reste_vue` le cloue pour que ce compromis
    reste un compromis et ne devienne pas un trou.
    """
    pts = _degrouper(pts)
    if len(pts) < MINI_RELEVES:
        return None
    # `_degrouper` garantit un écart ≥ ESPACEMENT_MINI_JOURS entre deux
    # points consécutifs : la division ne peut pas être par zéro.
    vitesses = [(y1 - y0) / ((t1 - t0).total_seconds() / 86400.0)
                for (t0, y0), (t1, y1) in zip(pts, pts[1:])]
    return _quantile(vitesses, QUANTILE_PENTE) * 30.0


def pente_go_par_mois(historique, perimetre=None) -> float | None:
    """Moindres carrés sur le TOTAL du compte, à périmètre de buckets
    constant (voir `meme_perimetre`).

    ⚠️ CE N'EST PLUS CE QUE LA PRODUCTION UTILISE. La pente du compte est
    désormais la somme des pentes par préfixe (`pentes_des_prefixes`) —
    la marche du 13/08 a montré qu'un filtre par bucket ne suffit pas,
    et celle du 16/08 que les moindres carrés eux-mêmes devaient partir.
    Gardé parce qu'il reste le calcul de RÉFÉRENCE des bancs : c'est lui
    qui rejoue, sur les trois marches réelles, le faux qu'on a corrigé.
    Le supprimer effacerait la démonstration en même temps que le code.
    """
    pts = [(datetime.fromisoformat(h["t"]), h["octets"] / GO)
           for h in historique
           if h.get("t") and h.get("octets") is not None
           and meme_perimetre(h, perimetre)]
    return _moindres_carres(pts)


def pente_du_prefixe(historique, nom: str) -> float | None:
    """La pente d'UN préfixe, sur les seuls relevés qui le contiennent.

    ⚠️ Un relevé où le préfixe est absent n'est pas un zéro, c'est un
    SILENCE : produit pas encore né, ou couverture partielle ce jour-là.
    Le compter comme 0 fabriquerait une marche — exactement l'erreur que
    cette fonction existe pour supprimer. Et ça compterait un relevé de
    plus, donc sortirait le préfixe de `jeunes` un jour trop tôt.
    """
    pts = []
    for h in historique:
        p = h.get("prefixes")
        if not h.get("t") or not isinstance(p, dict) or p.get(nom) is None:
            continue
        pts.append((datetime.fromisoformat(h["t"]), p[nom] / GO))
    return _pente_basse(pts)


def pentes_des_prefixes(historique, prefixes_courants) -> dict:
    """La pente du compte = la SOMME des pentes de ses préfixes.

    ⚠️ AJOUTÉ APRÈS COUP, LE 13/08, PARCE QUE ÇA A REMENTI EN VRAI — un
    cran plus bas que le 10/08. Ce jour-là c'était un BUCKET qui venait
    d'apparaître, et `meme_perimetre` a été écrit pour ça. Le 13/08,
    c'est un PRODUIT qui apparaît — la grille AGRUME, +1,03 Go en une
    nuit — **à l'intérieur d'un bucket déjà connu**. L'ensemble des
    buckets n'avait pas bougé d'un iota : le filtre du 10/08 n'a rien vu,
    les moindres carrés sur le total ont lu +9,10 Go/mois, et le mail
    « palier atteint dans 27 jours » est parti. Or la grille était déjà
    à son plateau (rétention 3 runs, 0 orphelin vérifié) et le compte à
    2,0 Go sur 10.

    Sommer les pentes par préfixe traite les deux marches d'un coup, et
    sans filtre : un produit qui naît n'a pas encore de pente, il pèse
    donc 0 dans l'échéance au lieu de la faire exploser ; un produit qui
    meurt sort de la somme ; un bucket entier qui apparaît n'est qu'un
    paquet de préfixes neufs. ⓘ Et la pente devient ATTRIBUABLE : le
    rapport dit QUI monte, ce qu'un total ne dira jamais — c'est ce que
    la note du Lot J appelait « le détecteur de fuite », qui n'existait
    en fait pas, faute d'avoir jamais historisé autre chose que le total.

    ⚠️ ET ÇA N'A PAS SUFFI : le 16/08, la marche est descendue encore
    d'un cran — un DOMAINE neuf à l'intérieur de `agrume/grille`, un
    préfixe qui, lui, avait ses trois relevés. Le mécanisme ci-dessous
    n'a rien pu faire, parce que le problème n'était plus la
    granularité mais le CALCUL : sur trois points, les moindres carrés
    ne savent pas séparer une marche d'une pente. C'est `_pente_basse`
    qui répond à ça, et il répond pour toutes les granularités à la fois
    — puis le 17/08 pour plusieurs marches à la fois.

    ⚠️ LE PRIX, ET IL EST RÉEL : pendant ses 4 premiers relevés (3 avant
    le 16/08), un produit ne compte PAS dans l'échéance. Une chaîne qui
    déborderait dès sa naissance ne serait vue qu'au quatrième jour.
    D'où `jeunes`, rendu ET journalisé : une échéance qui ne couvre pas
    tout doit le dire, sinon elle se lit comme un feu vert.
    """
    connues, jeunes = {}, []
    for nom in prefixes_courants:
        p = pente_du_prefixe(historique, nom)
        if p is None:
            jeunes.append(nom)
        else:
            connues[nom] = p
    return {"total": sum(connues.values()) if connues else None,
            "par_prefixe": connues, "jeunes": sorted(jeunes)}


def rapprocher(index, cle_index: str, prefixe: str, objets,
               maintenant=None, grace_h: float = GRACE_EN_VOL_H) -> dict:
    """Confronte l'index d'un produit à ce que le bucket contient
    VRAIMENT. `objets` = itérable de (bucket, cle, taille[, ecrit_le])
    déjà filtré sur le bon bucket.

    ORPHELIN  : présent dans R2, réclamé par personne, et ASSEZ VIEUX
                pour que ce ne soit pas une publication en cours — de la
                place payée pour rien, et le symptôme d'une purge qui ne
                mord plus (les 18 du `TypeError` du 12/08).
    EN VOL    : présent, réclamé par personne, mais écrit il y a moins de
                `grace_h` — les objets d'un run dont l'index n'est pas
                encore publié (voir `GRACE_EN_VOL_H` : la course du
                17/08). Dit, jamais fatal, et devenu orphelin demain s'il
                est encore là.
    MANQUANT  : déclaré par l'index, absent du bucket — plus grave dans
                l'autre sens : le produit servi a des trous, et c'est
                l'index qui ment.
    RESTE     : suppression ratée, déjà connue de l'index et reprise au
                run suivant. Présent, réclamé, mais pas légitime pour
                autant — compté à part plutôt que noyé dans l'un ou
                l'autre.

    ⚠️ Un index ILLISIBLE ne rend pas « 0 orphelin ». Il rend
    `lu=False`, et c'est à l'appelant d'en faire un motif : même piège
    que `couverture_partielle`, un rapprochement qui n'a pas eu lieu ne
    doit jamais se lire comme un rapprochement réussi.
    """
    if not isinstance(index, dict):
        return {"prefixe": prefixe, "lu": False,
                "raison": "index absent ou illisible"}

    reclamees = {cle_index}
    for e in index.get("runs") or []:
        reclamees.update(e.get("cles") or [])
    restes = set(index.get("restes") or [])

    presentes = {o[1]: o[2] for o in objets if o[1].startswith(prefixe)}
    ecrit_le = {o[1]: (o[3] if len(o) > 3 else None) for o in objets
                if o[1].startswith(prefixe)}

    # ⚠️ SANS DATE, UN OBJET EST JUGÉ ANCIEN — donc orphelin s'il n'est
    #    réclamé par personne. C'est le même principe que `lu=False` :
    #    une vérification qui n'a pas pu avoir lieu ne doit jamais se
    #    lire comme une vérification réussie. Un `LastModified` absent
    #    ferait taire la jauge s'il valait grâce.
    maintenant = maintenant or datetime.now(timezone.utc)
    limite = maintenant - timedelta(hours=grace_h)

    def en_vol(cle: str) -> bool:
        t = ecrit_le.get(cle)
        return t is not None and t > limite

    non_reclamees = set(presentes) - reclamees - restes
    orphelins = sorted(c for c in non_reclamees if not en_vol(c))
    vol = sorted(c for c in non_reclamees if en_vol(c))
    return {
        "prefixe": prefixe, "lu": True,
        "runs": len(index.get("runs") or []),
        "retention": index.get("retention_runs"),
        "reclamees": len(reclamees),
        "presentes": len(presentes),
        "orphelins": orphelins,
        "octets_orphelins": sum(presentes[c] for c in orphelins),
        "en_vol": vol,
        "octets_en_vol": sum(presentes[c] for c in vol),
        "grace_h": grace_h,
        "manquants": sorted(reclamees - set(presentes)),
        "restes_presents": sorted(restes & set(presentes)),
        "octets": sum(presentes.values()),
    }


def jours_avant(total_octets: int, pente_mois: float | None,
                cible_go: float) -> float | None:
    """Combien de jours avant d'atteindre `cible_go` à cette pente.

    Rend `None` si la pente est nulle, négative ou inconnue — un volume
    qui décroît n'a pas d'échéance, et prétendre le contraire ferait
    alerter sur un projet en train de se ranger.
    """
    if not pente_mois or pente_mois <= 0:
        return None
    reste = cible_go - total_octets / GO
    if reste <= 0:
        return 0.0
    return reste / (pente_mois / 30.0)


def verdict(inventaire: dict, pente_mois: float | None,
            seuil_go: float = SEUIL_ALERTE_GO,
            horizon: int = HORIZON_ALERTE_JOURS,
            couverture_partielle: bool = False,
            rapprochements=None) -> dict:
    """Décide, et dit POURQUOI. Le motif compte autant que le booléen :
    c'est lui qui part dans le mail, et un mail qui dit seulement
    « seuil dépassé » oblige à rouvrir un terminal pour savoir quoi
    faire.

    ⚠️ `couverture_partielle` n'est PAS un détail de journal. Un total
    calculé sur une partie des buckets est un total FAUX, et un total
    faux comparé à un palier donne un feu vert qui ne vaut rien. Quand
    la couverture est partielle, ça devient un motif à part entière :
    le rapport ne peut alors jamais ressembler à un bilan propre.
    """
    go = inventaire["octets"] / GO
    j_palier = jours_avant(inventaire["octets"], pente_mois, PALIER_STOCKAGE_GO)
    motifs = []
    if couverture_partielle:
        motifs.append(f"COUVERTURE PARTIELLE — les {go:.2f} Go mesurés ne "
                      f"couvrent pas tout le compte ; le palier peut être "
                      f"franchi sans que ce job le voie")
    if go >= PALIER_STOCKAGE_GO:
        motifs.append(f"palier gratuit DÉPASSÉ : {go:.2f} Go sur "
                      f"{PALIER_STOCKAGE_GO:.0f} Go — R2 facture déjà")
    elif go >= seuil_go:
        motifs.append(f"seuil d'alerte franchi : {go:.2f} Go ≥ {seuil_go:.1f} Go "
                      f"({go / PALIER_STOCKAGE_GO * 100:.0f} % du palier)")
    if j_palier is not None and j_palier <= horizon and go < PALIER_STOCKAGE_GO:
        motifs.append(f"au rythme mesuré (+{pente_mois:.2f} Go/mois), palier "
                      f"atteint dans {j_palier:.0f} jours")
    # ⛔ Le contrat de comptabilité, indépendant du poids et de la pente.
    # Un orphelin n'est pas une croissance : c'est de la place payée que
    # plus personne ne réclame, et un seul suffit à dire que la purge du
    # produit ne mord plus. On ne tolère donc pas « un peu » d'orphelins
    # — un seuil de tolérance ici, c'est une fuite qu'on autorise.
    #
    # ⚠️ `en_vol` N'EST PAS UN MOTIF, ET CE N'EST PAS UN SEUIL DE
    # TOLÉRANCE DÉGUISÉ : la frontière est l'ÂGE, pas le nombre. Zéro
    # objet non réclamé de plus de `GRACE_EN_VOL_H` reste la règle, et un
    # objet en vol qui ne se déclare pas devient orphelin tout seul en
    # vieillissant (voir `GRACE_EN_VOL_H`, la course du 17/08).
    for r in rapprochements or []:
        if not r.get("lu"):
            motifs.append(f"RAPPROCHEMENT IMPOSSIBLE pour « {r['prefixe']} » "
                          f"({r.get('raison', 'raison inconnue')}) — les "
                          f"orphelins de ce produit ne sont PAS couverts "
                          f"par ce bilan")
            continue
        if r["orphelins"]:
            motifs.append(
                f"{len(r['orphelins'])} objet(s) ORPHELIN(S) sous "
                f"« {r['prefixe']} » ({r['octets_orphelins'] / GO:.3f} Go) : "
                f"présents dans le bucket, réclamés par aucun index — la "
                f"purge de ce produit ne mord plus")
        if r["manquants"]:
            motifs.append(
                f"{len(r['manquants'])} clé(s) déclarée(s) par l'index de "
                f"« {r['prefixe']} » sont ABSENTES du bucket — le produit "
                f"servi a des trous")
    return {"alerte": bool(motifs), "motifs": motifs,
            "go": go, "pente_go_mois": pente_mois,
            "jours_avant_palier": j_palier,
            "couverture_partielle": couverture_partielle,
            "rapprochements": rapprochements or []}


def rendre(inventaire: dict, pente_mois, v: dict, class_a_consommees: int,
           log=print, pentes: dict | None = None) -> None:
    """Le rapport lisible. Trié par poids décroissant : la première
    ligne est toujours celle sur laquelle agir."""
    go = inventaire["octets"] / GO
    log("┌─ JAUGE R2 (lecture seule) ───────────────────────────────────")
    log(f"│ total compte              : {go:8.3f} Go   "
        f"({go / PALIER_STOCKAGE_GO * 100:5.1f} % du palier {PALIER_STOCKAGE_GO:.0f} Go)")
    log(f"│ objets                    : {inventaire['objets']:8d}")
    if pente_mois is None:
        log(f"│ pente                     :        —     "
            f"(moins de {MINI_RELEVES} relevés)")
    else:
        log(f"│ pente mesurée             : {pente_mois:+8.3f} Go/mois"
            f"   (somme des préfixes, 25e centile des différences)")
    # ⚠️ Ce que l'échéance NE couvre pas doit se lire à côté d'elle, pas
    #    dans une note de bas de page : un produit trop jeune pour avoir
    #    une pente pèse 0 dans le calcul, et son poids réel est là.
    jeunes = (pentes or {}).get("jeunes") or []
    if jeunes:
        poids = sum(inventaire["par_prefixe"][n]["octets"] for n in jeunes
                    if n in inventaire["par_prefixe"])
        log(f"│ dont trop jeunes          : {len(jeunes):8d} préfixe(s) · "
            f"{poids / GO:.3f} Go hors échéance")
    if v["jours_avant_palier"] is not None:
        cible = datetime.now(timezone.utc) + timedelta(days=v["jours_avant_palier"])
        log(f"│ palier atteint dans       : {v['jours_avant_palier']:8.0f} j "
            f"(~{cible:%Y-%m-%d})")
    log(f"│ seuil d'alerte            : {SEUIL_ALERTE_GO:8.1f} Go   "
        f"· seuil d'arrêt chaîne {SEUIL_STOCKAGE_GO:.0f} Go")
    log("│ couverture                : "
        + ("PARTIELLE ⚠️  (total sous-estimé)" if v.get("couverture_partielle")
           else "complète (tous les buckets du compte)"))
    log("├─ par bucket ─────────────────────────────────────────────────")
    for nom, e in sorted(inventaire["par_bucket"].items(),
                         key=lambda kv: -kv[1]["octets"]):
        log(f"│ {nom:38s} {e['octets'] / GO:8.3f} Go  {e['objets']:7d} objets")
    log("├─ par préfixe ────────────────────────────────────────────────")
    # ⓘ La colonne de pente est la seule qui sépare un produit qui
    #   RESPIRE (rétention courte, poids stable) d'un produit qui FUIT.
    #   Un poids seul ne le dit pas : 40 Mo peuvent être un plateau ou
    #   le début d'une dérive, et c'est justement ce qu'il fallait
    #   trancher le 13/08.
    pentes_pref = (pentes or {}).get("par_prefixe") or {}
    for nom, e in sorted(inventaire["par_prefixe"].items(),
                         key=lambda kv: -kv[1]["octets"])[:20]:
        p = pentes_pref.get(nom)
        col = (f" {p:+8.3f} Go/mois" if p is not None
               else ("       (trop jeune)" if pentes else ""))
        log(f"│ {nom:38s} {e['octets'] / GO:8.3f} Go  "
            f"{e['objets']:7d} objets{col}")
    # ⛔ Le contrat de comptabilité. Distinct du poids et de la pente :
    #    il ne dit pas « combien » mais « est-ce que tout ce qui est là
    #    est réclamé par quelqu'un ». C'est la seule ligne qui sépare un
    #    plateau légitime d'une purge qui a cessé de mordre.
    rapp = v.get("rapprochements") or []
    if rapp:
        log("├─ produits indexés : tout est-il réclamé ? ───────────────────")
        for r in rapp:
            if not r.get("lu"):
                log(f"│ {r['prefixe']:38s} ⚠️  NON RAPPROCHÉ "
                    f"({r.get('raison', '?')})")
                continue
            etat = ("✓ tout est réclamé" if not r["orphelins"]
                    else f"⛔ {len(r['orphelins'])} orphelin(s) · "
                         f"{r['octets_orphelins'] / GO:.3f} Go")
            log(f"│ {r['prefixe']:38s} {r['presentes']:4d} présentes / "
                f"{r['reclamees']:4d} réclamées   {etat}")
            if r["restes_presents"]:
                log(f"│ {'':38s} ⓘ {len(r['restes_presents'])} suppression(s) "
                    f"ratée(s), reprise(s) au prochain run")
            # ⓘ Dit, et pas tu : c'est la ligne qui explique un écart
            #   entre « présentes » et « réclamées » sans orphelin, et
            #   qui aurait fait comprendre le mail du 17/08 en un
            #   coup d'œil au lieu d'un audit à la main.
            if r.get("en_vol"):
                log(f"│ {'':38s} ⏳ {len(r['en_vol'])} objet(s) en vol "
                    f"({r['octets_en_vol'] / GO:.3f} Go) — écrits depuis "
                    f"moins de {r.get('grace_h', GRACE_EN_VOL_H):.0f} h, "
                    f"index pas encore publié")
            for cle in r["orphelins"][:3]:
                log(f"│    ↳ {cle}")
            if len(r["orphelins"]) > 3:
                log(f"│    ↳ … (+{len(r['orphelins']) - 3})")
    log("├─ coût de cet audit ──────────────────────────────────────────")
    # ⚠️ Un audit qui surveille un quota et le consomme sans le dire est
    # une jauge malhonnête. `ListObjectsV2` EST une opération classe A.
    log(f"│ {class_a_consommees} opérations classe A consommées par ce listing "
        f"({class_a_consommees * 30 / PALIER_CLASS_A_MOIS * 100:.2f} % "
        f"du palier si nocturne)")
    if rapp:
        # Les GetObject des index sont de la classe B (palier séparé,
        # 10 M/mois) — négligeable, mais le dire fait partie du contrat.
        log(f"│ {len(rapp)} opérations classe B (lecture des index) — palier "
            f"séparé de 10 M/mois")
    log("└──────────────────────────────────────────────────────────────")
    for m in v["motifs"]:
        log(f"⚠️  {m}")


# ══════════════════════════════════════════════════════════════════════
#  PARTIE E/S
# ══════════════════════════════════════════════════════════════════════
def client():
    """⚠️ Un jeu d'identifiants DÉDIÉ À L'AUDIT est préféré s'il existe.

    Relevé le 10/08/2026 au déploiement : le jeton R2 du VPS ne peut lire
    que `model-verif` et `balise-watch-packs`. `balise-watch-grids` — le
    plus gros, écrit par les GitHub Actions avec un autre jeton — lui rend
    AccessDenied. Un audit avec ce jeton-là ne peut pas voir le compte.

    La bonne réponse n'est pas d'élargir le jeton d'ÉCRITURE du VPS (on
    ajouterait du pouvoir de nuire pour un besoin de lecture), mais un
    second jeton **lecture seule, portée compte, avec ListBuckets**.
    D'où ces trois variables séparées, qui retombent sur les `R2_*` tant
    qu'elles n'existent pas.
    """
    try:
        import boto3  # noqa: PLC0415
    except ImportError:
        raise Abort("boto3 absent — lancer avec BW_PYTHON "
                    "(/home/debian/venv-balise/bin/python3)")

    def var(nom):
        return (os.environ.get("BW_R2_AUDIT_" + nom)
                or os.environ.get("R2_" + nom) or "")

    manque = [n for n in ("ACCOUNT_ID", "ACCESS_KEY_ID", "SECRET_ACCESS_KEY")
              if not var(n)]
    if manque:
        raise Abort("identifiants R2 absents (" + ", ".join(manque) + ") — "
                    "`set -a; . ~/.balise-watch-r2.env; set +a`")
    return boto3.client(
        "s3",
        endpoint_url="https://%s.r2.cloudflarestorage.com" % var("ACCOUNT_ID"),
        aws_access_key_id=var("ACCESS_KEY_ID"),
        aws_secret_access_key=var("SECRET_ACCESS_KEY"),
        region_name="auto")


def lister_buckets(c, log=print) -> tuple[list[str], bool]:
    """Tous les buckets du compte — parce que le palier est par compte.

    ⚠️ Un jeton R2 peut être limité à un bucket : `ListBuckets` rend
    alors AccessDenied. On ne fait PAS semblant que le compte est vide :
    on retombe sur `BW_R2_BUCKETS` et on le DIT, parce qu'un audit qui
    liste 1 bucket sur 3 en croyant les avoir tous est pire que pas
    d'audit du tout — il rassure à tort.
    """
    try:
        r = c.list_buckets()
        noms = sorted(b["Name"] for b in r.get("Buckets", []))
        if noms:
            return noms, True
        raise Abort("le compte ne rend aucun bucket — jeton sur le mauvais compte ?")
    except Abort:
        raise
    except Exception as e:  # noqa: BLE001 — on veut le repli quelle que soit la cause
        repli = [b.strip() for b in os.environ.get("BW_R2_BUCKETS", "").split(",")
                 if b.strip()]
        if not repli:
            raise Abort(
                f"ListBuckets refusé ({type(e).__name__}) et BW_R2_BUCKETS "
                f"absente. Le palier gratuit étant PAR COMPTE, auditer un "
                f"seul bucket ne prouve rien : renseigner "
                f"BW_R2_BUCKETS=\"balise-watch-grids,model-verif,"
                f"balise-watch-packs\" dans ~/.balise-watch-r2.env, ou donner "
                f"le droit ListBuckets au jeton.")
        log(f"⚠️ ListBuckets refusé ({type(e).__name__}) — repli sur "
            f"BW_R2_BUCKETS : {', '.join(repli)}. Cet audit ne couvre QUE "
            f"ces buckets ; un bucket créé plus tard passerait inaperçu.")
        return repli, False


def parcourir(c, buckets, log=print):
    """Rend (objets, nb_requetes). `objets` est une liste de tuples —
    et pas un générateur : on veut pouvoir la compter, la rejouer et la
    journaliser, et 100 000 tuples tiennent sans problème en mémoire."""
    objets = []
    requetes = 0
    for bucket in buckets:
        jeton = None
        while True:
            kw = {"Bucket": bucket, "MaxKeys": 1000}
            if jeton:
                kw["ContinuationToken"] = jeton
            try:
                r = c.list_objects_v2(**kw)
            except Exception as e:  # noqa: BLE001
                raise Abort(f"listing de « {bucket} » impossible : "
                            f"{type(e).__name__} {e}")
            requetes += 1
            for o in r.get("Contents", []):
                # ⓘ `LastModified` est déjà dans la réponse du listing :
                #   le porter ne coûte pas une opération de plus, et
                #   c'est lui qui sépare un run en vol d'un orphelin
                #   (voir `GRACE_EN_VOL_H`).
                objets.append((bucket, o["Key"], int(o.get("Size", 0)),
                               o.get("LastModified")))
            if not r.get("IsTruncated"):
                break
            jeton = r.get("NextContinuationToken")
            if not jeton:
                # Truncated sans jeton : anomalie côté API. On s'arrête
                # en le disant, plutôt que de boucler ou de rendre un
                # total silencieusement incomplet.
                log(f"⚠️ « {bucket} » tronqué sans jeton de suite — "
                    f"total partiel, ne pas se fier au chiffre")
                break
    return objets, requetes


def lire_index(c, bucket: str, cle: str):
    """L'index d'un produit — 1 GetObject, classe B.

    ⚠️ Rend `None` quand il ne peut PAS être lu, quelle qu'en soit la
    cause. Surtout pas `{}` : un index vide est une information (le
    produit a perdu son index, tout devient orphelin — c'est l'incident
    des 12-13/08), un index illisible en est une autre (le
    rapprochement n'a pas eu lieu). Les confondre transformerait une
    panne de lecture en accusation, ou l'inverse.
    """
    try:
        return json.loads(c.get_object(Bucket=bucket, Key=cle)["Body"].read())
    except Exception:  # noqa: BLE001 — NoSuchKey, réseau, JSON cassé : idem
        return None


def charger_historique(chemin: Path, maxi: int = 400) -> list[dict]:
    """JSONL, une ligne par relevé. Format choisi pour être appendable
    sans relire (un relevé nocturne ne doit jamais réécrire l'historique
    qu'il lit) et lisible à la main le soir où ça casse.

    Une ligne corrompue est IGNORÉE, pas fatale : la leçon du budget
    Open-Meteo (« un fichier d'état corrompu ne doit pas arrêter la
    collecte ») vaut ici — un historique abîmé ne doit pas empêcher de
    mesurer le présent.
    """
    if not chemin.exists():
        return []
    lignes = []
    for ligne in chemin.read_text(encoding="utf-8").splitlines()[-maxi:]:
        ligne = ligne.strip()
        if not ligne:
            continue
        try:
            lignes.append(json.loads(ligne))
        except (ValueError, TypeError):
            continue
    return lignes


def ajouter_historique(chemin: Path, releve: dict) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with chemin.open("a", encoding="utf-8") as f:
        f.write(json.dumps(releve, ensure_ascii=False) + "\n")


# ══════════════════════════════════════════════════════════════════════
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Jauge R2 — lecture seule.")
    p.add_argument("--out", default=os.environ.get("BW_MODEL_VERIF_ETAT",
                                                   "/var/lib/bw-model-verif"),
                   help="répertoire d'état (historique JSONL)")
    p.add_argument("--seuil-go", type=float, default=SEUIL_ALERTE_GO)
    p.add_argument("--horizon-jours", type=int, default=HORIZON_ALERTE_JOURS)
    p.add_argument("--json", action="store_true", help="sortie machine")
    p.add_argument("--sans-historique", action="store_true",
                   help="ne pas écrire de relevé (essai à blanc)")
    a = p.parse_args(argv)

    try:
        c = client()
        buckets, couverture_complete = lister_buckets(c)
        objets, requetes = parcourir(c, buckets)
        # ⛔ Le rapprochement ne coûte QUE la lecture de l'index : le
        # listing vient d'être fait pour la jauge. C'est ce qui permet
        # de poser un contrat de comptabilité sans nouvelle dépense.
        # Un produit dont le bucket n'est pas dans la couverture du jour
        # est écarté — l'accuser d'avoir 100 % d'orphelins parce qu'on
        # n'a pas pu le lister serait le pire des faux positifs.
        # ⚠️ `maintenant` est pris UNE fois et passé : deux produits
        # rapprochés à deux instants différents n'auraient pas la même
        # frontière d'âge, et un objet à la seconde près pourrait être
        # « en vol » pour l'un et orphelin pour l'autre.
        maintenant = datetime.now(timezone.utc)
        rapprochements = [
            rapprocher(lire_index(c, b, cle), cle, prefixe,
                       [o for o in objets if o[0] == b],
                       maintenant=maintenant)
            for b, cle, prefixe in PRODUITS_INDEXES if b in buckets]
    except Abort as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2

    inv = agreger(objets)
    hist_path = Path(a.out) / "audit_r2.jsonl"
    historique = charger_historique(hist_path)

    # ⚠️ `prefixes` AJOUTÉ LE 13/08. Sans lui, l'historique ne savait que
    # le total et les buckets : impossible de dire, le lendemain matin,
    # si +1 Go venait d'un produit nouveau ou d'une fuite. Le champ ne
    # coûte aucune opération R2 — l'inventaire est déjà calculé — et
    # c'est ce qui manquait à la « pente par préfixe » que la note du
    # Lot J croyait déjà avoir.
    releve = {"t": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "octets": inv["octets"], "objets": inv["objets"],
              "buckets": {k: v["octets"] for k, v in inv["par_bucket"].items()},
              "prefixes": {k: v["octets"]
                           for k, v in inv["par_prefixe"].items()},
              "couverture_complete": couverture_complete}
    # On écrit AVANT de juger : si le verdict lève, le relevé du jour est
    # quand même dans l'historique, et la pente de demain reste juste.
    if not a.sans_historique:
        try:
            ajouter_historique(hist_path, releve)
        except OSError as e:
            print(f"⚠️ historique non écrit ({e}) — pente indisponible demain",
                  file=sys.stderr)

    serie = historique + [releve]
    pentes = pentes_des_prefixes(serie, inv["par_prefixe"].keys())
    pente = pentes["total"]
    if pentes["jeunes"]:
        # Journalisé même quand tout va bien : c'est le seul endroit où
        # se lit le trou de couverture de l'échéance du jour.
        apercu = ", ".join(pentes["jeunes"][:5])
        if len(pentes["jeunes"]) > 5:
            apercu += f" … (+{len(pentes['jeunes']) - 5})"
        # ⚠️ Sur stderr en mode `--json` : sinon cette ligne se retrouve
        # AVANT l'objet sur stdout et casse tout lecteur machine — vu en
        # vrai le 16/08 en voulant relire les orphelins en JSON.
        print(f"  ⓘ {len(pentes['jeunes'])} préfixe(s) sans pente (moins de "
              f"{MINI_RELEVES} relevés) — hors échéance : {apercu}",
              file=sys.stderr if a.json else sys.stdout)
    v = verdict(inv, pente, a.seuil_go, a.horizon_jours,
                couverture_partielle=not couverture_complete,
                rapprochements=rapprochements)

    if a.json:
        print(json.dumps({"releve": releve, "verdict": v,
                          "par_prefixe": inv["par_prefixe"],
                          "pentes": pentes,
                          "class_a": requetes,
                          "class_b": len(rapprochements)},
                         ensure_ascii=False, indent=2))
    else:
        rendre(inv, pente, v, requetes, pentes=pentes)

    return 1 if v["alerte"] else 0


if __name__ == "__main__":
    sys.exit(main())
