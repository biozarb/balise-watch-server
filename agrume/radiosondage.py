#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/radiosondage.py — confronter le profil AGRUME à un vrai ballon
#                                                        (10/08/2026)
#
#  Étape 5 bis du lot H. Jusqu'ici le profil n'était vérifié que CONTRE
#  LUI-MÊME : `ecart_recouvrement()` mesure si les deux sources d'AROME
#  se contredisent dans la zone de mélange. C'est un excellent détecteur
#  de conversion fausse, et c'est tout ce qu'il est. Deux sources du même
#  modèle qui s'accordent ne prouvent pas que le modèle a raison.
#
#  Un radiosondage, lui, est une mesure. Le §6 du lot proposait des
#  grappes de balises étagées en reconnaissant la limite : « chacune
#  mesure dans sa propre couche de surface locale, pas l'air libre. Ce
#  n'est PAS un radiosondage. » Or le serveur en sert déjà — route
#  `/sounding`, université du Wyoming — et deux stations sont à quelques
#  dixièmes de degré du domaine.
#
#  ── ⚠️ CE QUE CETTE COMPARAISON NE PROUVERA PAS, ÉCRIT D'AVANCE ──────
#
#  1. **Les stations sont en plaine.** Payerne est sur le plateau suisse
#     (sol 491 m), Cameri dans la plaine du Pô (~211 m). Elles vérifient
#     l'AIR LIBRE et le RACCORD, pas la couche limite de montagne — qui
#     est justement ce qu'AGRUME apporte. Un bon accord à Payerne ne dit
#     RIEN du profil au-dessus d'un décollage à 2 000 m.
#
#  2. **Le ballon dérive.** Il part avec le vent ; la colonne du modèle,
#     elle, est verticale. `derive()` chiffre l'écart, run par run, au
#     lieu de l'agiter comme une objection de principe. ⓘ Mesuré sur les
#     deux profils de Payerne du 10/08 (ascension SUPPOSÉE 5 m/s, non
#     mesurée) : 1,0 km à 2 000 m, 2,6 km à 4 000, 4,6 km à 6 000. C'est
#     sous la maille 0,025° (2,8 km) jusqu'à 2 000 m, donc bien plus
#     petit que les « dizaines de kilomètres » redoutées — mais c'était
#     un jour de VENT FAIBLE (21 m/s au maximum, à 300 hPa). Par vent
#     fort la dérive sera plusieurs fois plus grande, et c'est pour ça
#     qu'elle est publiée avec chaque comparaison et jamais supposée.
#
#  3. **n sera petit.** Deux stations × deux lâchers par jour. Une
#     semaine donne 28 profils, et encore : Cameri n'est pas en haute
#     résolution. Tout chiffre sorti d'ici porte son `n`.
#
#  4. **L'heure du ballon et l'échéance du modèle doivent coïncider.**
#     Le ballon part à 00 et 12 Z ; AROME sort à 00, 03, 06… On compare
#     l'échéance qui TOMBE sur l'heure du lâcher, et la réponse dit
#     toujours laquelle — un décalage d'une heure sur un profil de vent,
#     c'est une erreur qu'on prendrait pour un défaut du modèle.
#
#  ── ⚠️ L'UNITÉ NE SE DEVINE PAS ─────────────────────────────────────
#  Le 10/08, `index.js` rangeait la colonne de vitesse dans `speedKt` en
#  supposant des nœuds. Wyoming publie `SPED` en **m/s** sur l'endpoint
#  `wsgi/sounding`, et l'écrit dans la ligne d'unités que le parseur
#  sautait : les vents affichés aux pilotes valaient 0,514 fois la
#  réalité. Ce module LIT la ligne d'unités et REFUSE de parser un
#  format qu'il ne reconnaît pas. Mieux vaut pas de sondage qu'un
#  sondage à moitié vitesse.
#
#  ⓘ **Duplication assumée.** Le parsing existe désormais en JS
#  (`index.js::parseWyomingSounding`, pour le site) et ici en Python
#  (pour la confrontation hors ligne). Le projet a déjà payé une
#  duplication de ce genre avec `LEVELS`. Elle est assumée ici parce que
#  les deux consommateurs n'ont ni le même runtime ni le même cycle de
#  vie, et elle est bornée par la même discipline des deux côtés :
#  l'unité est lue, jamais supposée. `test_radiosondage.py` fige un
#  extrait réel et vérifie les deux comportements sur lui.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import math
import re
import urllib.request
from datetime import datetime, timedelta, timezone

# ── Les stations, et pourquoi celles-là ───────────────────────────────
# ⚠️ `active` n'est pas décoratif et `mesure` dit POURQUOI. Cuneo était
# la seconde station du plan ; interrogée le 10/08 sur huit couples
# date/heure répartis sur deux mois, elle a rendu 404 à chaque fois. Elle
# reste dans la table, désactivée et datée, plutôt que supprimée : une
# station retirée sans trace, c'est quelqu'un qui la repropose dans six
# mois. (Elle est aussi offerte aux pilotes dans `SOUNDING_STATIONS` de
# `index.js` — à traiter à part, c'est le produit, pas le lot.)
STATIONS = (
    dict(wmo="06610", nom="Payerne", pays="CH", lat=46.813, lon=6.943,
         sol_station_m=491, active=True, resolution="haute",
         mesure="10/08 : 3 242 niveaux, sol 491 m. 0,51° au nord de latmax."),
    dict(wmo="16064", nom="Cameri (Novara)", pays="IT", lat=45.52, lon=8.65,
         sol_station_m=211, active=True, resolution="standard",
         mesure="10/08 : 115 niveaux seulement (niveaux significatifs). "
                "1,05° à l'est de lonmax, plaine du Pô."),
    dict(wmo="16117", nom="Cuneo-Levaldigi", pays="IT", lat=44.547, lon=7.623,
         sol_station_m=386, active=False, resolution=None,
         mesure="10/08 : 404 sur 8 couples date/heure du 01/06 au 10/08. "
                "AUCUNE donnée. C'était la station du plan initial."),
    dict(wmo="11120", nom="Innsbruck-Flughafen", pays="AT", lat=47.260, lon=11.355,
         sol_station_m=579, active=True, resolution="haute",
         mesure="13/08 : sondée sur 12 couples date/heure du 01/06 au "
                "03/08 (le code réel de ce module, pas une estimation) — "
                "6/6 à 00Z (4 500 à 5 100 niveaux), 0/6 à 12Z (HTTP 400 "
                "systématique, PAS un timeout : la station ne publie "
                "qu'UN lâcher par jour). ⚠️ Le 'flaky' rapporté avant "
                "(2 timeouts sur 3) mélangeait probablement les deux "
                "heures. C'est la station de VALLÉE ALPINE qui manquait "
                "(579 m, encaissée dans l'Inn) — mais elle est à 0,96° "
                "au nord de latmax et 3,76° à l'est de lonmax du domaine "
                "Nord-Alpes, bien plus loin que Payerne ou Cameri : la "
                "confrontation y vérifie AROME en général, encore moins "
                "la couche limite DU domaine surveillé."),
)

URL_WYOMING = ("https://weather.uwyo.edu/wsgi/sounding"
               "?datetime={date}%20{heure}:00:00&id={wmo}&type=TEXT:LIST")

# Facteur de conversion vers les m/s, par unité déclarée dans l'en-tête.
# ⚠️ Une unité absente de cette table fait ÉCHOUER le parsing.
MS_PAR_UNITE = {"m/s": 1.0, "knot": 0.514444, "knots": 0.514444,
                "kt": 0.514444, "kts": 0.514444}

# Vitesse d'ascension par défaut d'une radiosonde, en m/s. ⚠️ C'est une
# VALEUR CONVENTIONNELLE, pas une mesure : Wyoming ne publie ni la
# position du ballon ni son heure niveau par niveau. Elle n'entre que
# dans `derive()`, dont le résultat est donc une estimation étiquetée
# comme telle, jamais un chiffre de comparaison.
ASCENSION_MS = 5.0


class Abort(Exception):
    pass


def station(wmo):
    for s in STATIONS:
        if s["wmo"] == str(wmo):
            return s
    raise Abort(f"station {wmo!r} inconnue — connues : "
                + ", ".join(f"{s['wmo']} ({s['nom']})" for s in STATIONS))


# ══════════════════════════════════════════════════════════════════════
#  Lecture du sondage
# ══════════════════════════════════════════════════════════════════════
def parse_wyoming(texte):
    """Le bloc <PRE> de Wyoming → liste de niveaux, du bas vers le haut.

    ⚠️ L'unité de la vitesse est LUE dans l'en-tête, jamais supposée : un
    format non reconnu lève. Cf. l'en-tête du module — c'est exactement
    cette supposition qui a divisé par deux les vents affichés aux
    pilotes pendant des semaines.

    Chaque niveau porte `u`/`v` en m/s (convention météo : le vent va VERS
    dir+180°, donc u = -V·sin(dir), v = -V·cos(dir)) — parce que tout ce
    qui suit se compare par composantes et jamais par l'angle.
    """
    blocs = re.findall(r"<PRE>([\s\S]*?)</PRE>", texte, re.I)
    if not blocs:
        raise Abort("aucun bloc <PRE> dans la réponse Wyoming "
                    f"({len(texte)} octets) — station ou créneau sans donnée ?")
    lignes = blocs[0].split("\n")

    i_vitesse = facteur = None
    for k in range(len(lignes) - 1):
        noms = lignes[k].split()
        if "PRES" not in noms or "HGHT" not in noms:
            continue
        iv = next((n for n, x in enumerate(noms) if x in ("SPED", "SKNT")), None)
        if iv is None:
            break
        unites = lignes[k + 1].split()
        u = (unites[iv] if iv < len(unites) else "").lower()
        if u not in MS_PAR_UNITE:
            raise Abort(
                f"unité de vitesse non reconnue dans l'en-tête Wyoming : "
                f"{u!r}. ⚠️ NE PAS deviner — le 10/08, supposer des nœuds là "
                f"où le fichier disait m/s a divisé par deux tous les vents "
                f"affichés. Ajouter l'unité à MS_PAR_UNITE si elle est "
                f"légitime.")
        i_vitesse, facteur = iv, MS_PAR_UNITE[u]
        break
    if i_vitesse is None:
        raise Abort("en-tête Wyoming introuvable (ni PRES/HGHT, ni colonne "
                    "SPED/SKNT) — le format a changé, ne rien parser")

    niveaux = []
    for ligne in lignes:
        cols = ligne.split()
        if len(cols) < 8:
            continue
        try:
            n = [float(x) for x in cols]
        except ValueError:
            continue                       # en-tête, séparateurs
        vitesse = n[i_vitesse] * facteur
        d = n[6]
        niveaux.append(dict(
            pHPa=n[0], altitudeM=n[1], tC=n[2], tdC=n[3], hr=n[4],
            directionDeg=d, vitesseMs=vitesse,
            u=-vitesse * math.sin(math.radians(d)),
            v=-vitesse * math.cos(math.radians(d))))
    if len(niveaux) < 10:
        raise Abort(f"sondage trop court ({len(niveaux)} niveaux) — "
                    f"probablement un créneau sans lâcher")
    return niveaux


def telecharger(wmo, date, heure, ouvrir=None):
    """Le sondage brut. `ouvrir` est injecté pour les bancs (pas de réseau)."""
    url = URL_WYOMING.format(date=date, heure=str(heure).zfill(2), wmo=wmo)
    if ouvrir is not None:
        return ouvrir(url)
    req = urllib.request.Request(url, headers={"User-Agent": "balise-watch-agrume/1"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:                 # noqa: BLE001
        raise Abort(f"Wyoming injoignable pour {wmo} {date} {heure}Z : {e}")


# ══════════════════════════════════════════════════════════════════════
#  La dérive du ballon — estimée, et étiquetée comme telle
# ══════════════════════════════════════════════════════════════════════
def derive(niveaux, ascension_ms=ASCENSION_MS):
    """Déplacement horizontal cumulé du ballon, altitude par altitude.

    Intègre le vent du sondage lui-même : dx = u · dz / w. Renvoie une
    liste [(altitudeM, deriveKm)] alignée sur les niveaux.

    ⚠️ `w` est CONVENTIONNEL (5 m/s), pas mesuré : Wyoming ne publie ni
    position ni horodatage par niveau. La dérive est donc inversement
    proportionnelle à une valeur supposée — un ballon qui monterait à
    4 m/s dériverait 25 % plus loin. C'est pourquoi ce chiffre sert à
    BORNER l'interprétation d'un écart, jamais à corriger une valeur.
    """
    x = y = 0.0
    precedent = None
    trace = []
    for n in niveaux:
        if precedent is not None:
            dz = n["altitudeM"] - precedent["altitudeM"]
            if dz > 0:
                x += (n["u"] + precedent["u"]) / 2 * dz / ascension_ms
                y += (n["v"] + precedent["v"]) / 2 * dz / ascension_ms
        precedent = n
        trace.append((n["altitudeM"], math.hypot(x, y) / 1000.0))
    return trace


def derive_a(trace, altitude):
    """Dérive estimée (km) à cette altitude, ou None si hors du sondage."""
    candidats = [d for z, d in trace if z <= altitude]
    return round(candidats[-1], 2) if candidats else None


# ══════════════════════════════════════════════════════════════════════
#  La confrontation
# ══════════════════════════════════════════════════════════════════════
def interpoler(niveaux, altitude):
    """Le sondage interpolé linéairement à cette altitude-mer.

    ⚠️ On interpole le SONDAGE vers les altitudes d'AGRUME, et jamais
    l'inverse : le sondage a des milliers de niveaux, la colonne du
    modèle en a une trentaine. Interpoler la source dense vers la source
    creuse n'invente rien ; l'inverse fabriquerait de la structure
    verticale que le modèle n'a pas.

    ⚠️ u et v par composantes. Interpoler une direction en degrés entre
    359° et 001° donnerait 180°, soit l'inverse exact du vent.

    Renvoie None hors des bornes du sondage, plutôt que d'extrapoler.
    """
    if len(niveaux) < 2:
        return None
    if altitude < niveaux[0]["altitudeM"] or altitude > niveaux[-1]["altitudeM"]:
        return None
    k = 0
    while k + 1 < len(niveaux) - 1 and niveaux[k + 1]["altitudeM"] < altitude:
        k += 1
    a, b = niveaux[k], niveaux[k + 1]
    span = b["altitudeM"] - a["altitudeM"]
    f = 0.0 if span <= 0 else (altitude - a["altitudeM"]) / span
    out = {}
    for cle in ("u", "v", "tC", "hr"):
        va, vb = a.get(cle), b.get(cle)
        out[cle] = None if va is None or vb is None else va + f * (vb - va)
    return out


def _stats(valeurs):
    """médiane / d9 / max / n, sur une liste éventuellement vide.

    d9 et pas seulement la médiane : c'est la queue qui dit si un profil
    est bon partout ou bon en moyenne. `n` est toujours porté."""
    v = sorted(x for x in valeurs if x is not None and math.isfinite(x))
    if not v:
        return dict(n=0, mediane=None, d9=None, max=None)
    return dict(n=len(v),
                mediane=round(v[len(v) // 2], 3),
                d9=round(v[min(len(v) - 1, int(0.9 * len(v)))], 3),
                max=round(v[-1], 3))


def _mediane(valeurs):
    v = sorted(x for x in valeurs if x is not None and math.isfinite(x))
    return None if not v else round(v[len(v) // 2], 2)


LIBELLE_SOURCE = {"hauteur": "hauteur seule", "melange": "MÉLANGE (raccord)",
                  "isobare": "isobares seules"}


def confronter(reponse, niveaux, ascension_ms=ASCENSION_MS):
    """Le profil AGRUME contre le ballon, tranche par tranche.

    ⚠️ DEUX DÉCOUPAGES, ET C'EST VOULU.

    Par SOURCE (`hauteur` / `melange` / `isobare`) : c'est la question du
    lot. Si la zone de mélange `z_s+1000 → z_s+3000` se comporte moins
    bien que les tranches pures, le raccord AJOUTE de l'erreur au lieu
    d'en absorber — et ce serait un résultat, pas un détail. Le seul test
    dont on disposait jusqu'ici (`ecart_recouvrement`) compare AROME à
    AROME : il ne peut pas voir ça.

    Par TRANCHE D'ALTITUDE de 1 000 m : c'est la lecture du pilote, et
    c'est aussi là que se lit la dérive, qui croît avec l'altitude.

    Un écart global unique n'aurait dit ni l'un ni l'autre.
    """
    z_s = reponse["solModeleM"]["grille_0025"]
    if z_s is None:
        raise Abort("colonne sans sol modèle : rien à confronter. Le point "
                    "est-il couvert par l'orographie figée ?")
    trace = derive(niveaux, ascension_ms)

    points = []
    for p in reponse["profil"]:
        s = interpoler(niveaux, p["altitudeM"])
        if s is None or s["u"] is None:
            continue
        du, dv = p["u"] - s["u"], p["v"] - s["v"]
        v_agrume = math.hypot(p["u"], p["v"])
        v_ballon = math.hypot(s["u"], s["v"])
        points.append(dict(
            altitudeM=p["altitudeM"], source=p["source"],
            poidsHauteur=p.get("poidsHauteur"),
            ecartVentMs=math.hypot(du, dv),
            biaisVitesseMs=v_agrume - v_ballon,
            vitesseAgrumeMs=v_agrume, vitesseBallonMs=v_ballon,
            ecartTC=(None if p["t"] is None or s["tC"] is None
                     else p["t"] - s["tC"]),
            ecartHR=(None if p["hr"] is None or s["hr"] is None
                     else p["hr"] - s["hr"]),
            deriveKm=derive_a(trace, p["altitudeM"])))

    def bloc(sel, libelle, z0=None, z1=None):
        pts = [p for p in points if sel(p)]
        return dict(
            libelle=libelle, zMinM=z0, zMaxM=z1, n=len(pts),
            ecartVentMs=_stats([p["ecartVentMs"] for p in pts]),
            biaisVitesseMs=_mediane([p["biaisVitesseMs"] for p in pts]),
            ecartTC=_mediane([p["ecartTC"] for p in pts]),
            ecartHR=_mediane([p["ecartHR"] for p in pts]),
            deriveKmMax=max([p["deriveKm"] for p in pts
                             if p["deriveKm"] is not None], default=None))

    par_source = [bloc(lambda p, s=s: p["source"] == s, LIBELLE_SOURCE[s])
                  for s in ("hauteur", "melange", "isobare")]

    par_tranche = []
    if points:
        haut = max(p["altitudeM"] for p in points)
        z = math.floor(z_s / 1000.0) * 1000.0
        while z < haut:
            par_tranche.append(bloc(
                lambda p, a=z, b=z + 1000: a <= p["altitudeM"] < b,
                f"{z / 1000:.0f}–{(z + 1000) / 1000:.0f} km", z, z + 1000))
            z += 1000

    return dict(
        run=reponse["run"], echeanceH=reponse["echeanceH"],
        solModeleM=z_s,
        ascensionSupposeeMs=ascension_ms,
        nPointsCompares=len(points),
        nNiveauxSondage=len(niveaux),
        # ⚠️ Le sommet du sondage dépasse toujours celui d'AGRUME (16 km
        # contre ~7,5) : la comparaison s'arrête au plafond du modèle, pas
        # à celui du ballon. Ce n'est pas une donnée perdue, c'est le
        # domaine de validité du produit.
        plafondCompareM=(max((p["altitudeM"] for p in points), default=None)),
        global_=bloc(lambda p: True, "tout le profil"),
        parSource=par_source,
        parTranche=par_tranche,
        points=points,
        avertissement=(
            "Station de PLAINE : vérifie l'air libre et le raccord, PAS la "
            "couche limite de montagne. La dérive du ballon est estimée avec "
            f"une ascension SUPPOSÉE de {ascension_ms} m/s, non mesurée. "
            "Un profil = n = 1."))


# ══════════════════════════════════════════════════════════════════════
#  Quel run, quelle échéance
# ══════════════════════════════════════════════════════════════════════
def instant_ballon(date, heure):
    return datetime.strptime(f"{date} {str(heure).zfill(2)}", "%Y-%m-%d %H") \
        .replace(tzinfo=timezone.utc)


def runs_pour(date, heure, max_heures=24):
    """[(run ISO, échéance h)] dont l'échéance TOMBE sur l'heure du lâcher,
    du plus récent au plus ancien.

    ⚠️ On ne compare jamais une échéance voisine. Le ballon part à une
    heure ronde et AROME sort toutes les 3 h : il existe TOUJOURS une
    échéance exacte (0, 3, 6, 9, 12…). Accepter un décalage d'une heure
    ferait passer une erreur d'horodatage pour un défaut du modèle — et
    c'est le genre d'écart qu'on ne retrouve plus une fois publié.

    ⓘ Le plus récent n'est pas forcément le meilleur choix : l'échéance 0
    est une ANALYSE, qui a déjà assimilé des observations. La confronter
    à un ballon dit surtout ce que l'assimilation a fait ; les échéances
    6, 12, 24 disent ce que la PRÉVISION vaut. Le CLI laisse choisir et
    la réponse porte toujours l'échéance.
    """
    t = instant_ballon(date, heure)
    out = []
    for ech in range(0, max_heures + 1):
        run = t - timedelta(hours=ech)
        if run.hour % 3 == 0:
            out.append((run.strftime("%Y-%m-%dT%H:00:00Z"), ech))
    return out


# ══════════════════════════════════════════════════════════════════════
#  Affichage
# ══════════════════════════════════════════════════════════════════════
def _ligne(b, crier):
    """Une ligne du tableau. Les cellules absentes s'écrivent « — » : une
    case vide et un zéro ne doivent jamais se ressembler."""
    if not b["n"]:
        crier(f"  {b['libelle']:<18}   0  (aucun point comparable)")
        return
    e = b["ecartVentMs"]
    biais = "     —" if b["biaisVitesseMs"] is None else f"{b['biaisVitesseMs']:>+6.2f}"
    dt = "    —" if b["ecartTC"] is None else f"{b['ecartTC']:>+5.1f}"
    dhr = "    —" if b["ecartHR"] is None else f"{b['ecartHR']:>+5.0f}"
    der = "   —" if b["deriveKmMax"] is None else f"{b['deriveKmMax']:>4.1f}"
    crier(f"  {b['libelle']:<18} {b['n']:>3}  "
          f"{e['mediane']:>6.2f} {e['d9']:>6.2f} {e['max']:>6.2f}  "
          f"{biais}  {dt}  {dhr}  {der}")


def afficher(c, st, sondage_date, sondage_heure, crier=print):
    crier(f"\n══ {st['nom']} ({st['wmo']}, {st['pays']}) — ballon du "
          f"{sondage_date} {sondage_heure}Z ══")
    crier(f"  AROME run {c['run']} + {c['echeanceH']} h  ·  sol modèle "
          f"{c['solModeleM']:.0f} m  ·  sol station {st['sol_station_m']} m "
          f"(écart {c['solModeleM'] - st['sol_station_m']:+.0f} m)")
    crier(f"  {c['nNiveauxSondage']} niveaux au ballon, "
          f"{c['nPointsCompares']} points d'AGRUME comparables "
          f"(plafond {c['plafondCompareM']:.0f} m)")
    crier(f"\n  {'tranche':<18} {'n':>3}  {'méd':>6} {'d9':>6} {'max':>6}  "
          f"{'biais':>6}  {'ΔT°C':>5}  {'ΔHR%':>5}  {'dér.':>4}")
    crier(f"  {'':<18} {'':>3}  {'— écart vent m/s —':^20}  "
          f"{'A−B':>6}  {'A−B':>5}  {'A−B':>5}  {'km':>4}")
    crier("  " + "─" * 74)
    for b in c["parSource"]:
        _ligne(b, crier)
    crier("  " + "─" * 74)
    for b in c["parTranche"]:
        _ligne(b, crier)
    crier("  " + "─" * 74)
    _ligne(dict(c["global_"], libelle="TOUT LE PROFIL"), crier)
    crier(f"\n  ⚠️ {c['avertissement']}")
