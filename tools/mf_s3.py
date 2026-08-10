#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  tools/mf_s3.py — le miroir S3 public des paquets Météo-France, en un
#                   seul module                          (10/08/2026)
#
#  ⚠️ POURQUOI CE MODULE EXISTE. Le listing S3 et le calcul de couverture
#  d'un run étaient écrits dans `arome-wind/ingest.py`, et le lot H en a
#  besoin à son tour — le poller de run repose ENTIÈREMENT sur
#  `covered_steps()`, qui répond « ce run est-il publié ? » pour quelques
#  kilo-octets et sans télécharger un seul GRIB. La consigne du lot est
#  explicite : « ⓘ `covered_steps()` fait déjà l'essentiel. ÉTENDRE, NE
#  PAS RÉÉCRIRE. »
#
#  Le corps est donc déplacé ici À L'IDENTIQUE, et `arome-wind/ingest.py`
#  l'importe. Même motif que `tools/storage.py` le 03/08, qui a réuni
#  cinq copies de `sb_upload()`. Le projet s'est déjà fait mordre par la
#  duplication (`LEVELS` dupliqué entre les deux dépôts, cf. BUGS.md) :
#  deux copies d'un parseur de nom de fichier, ce serait le même piège.
#
#  ⚠️ CE MODULE NE PARLE PAS AU PORTAIL. Le miroir OVH est SANS CLÉ et
#  sans quota. Le portail (WCS, avec clé) est une autre route, avec ses
#  propres pièges — elle vit dans `agrume/portail.py`. Ne pas mélanger :
#  la clé Météo-France ne doit jamais approcher un chemin de code qui
#  n'en a pas besoin.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# Mesuré le 10/08 : débit 20,9 Mo/s sur un bundle de 818 Mo, rétention
# 118 runs en ligne soit ~14,7 jours (cinq fois celle du portail).
S3 = "https://meteofrance-pnt.s3.rbx.io.cloud.ovh.net"

# Modèles réellement publiés sous `pnt/{run}/`, relevés le 10/08 :
#   arome · arome-om · aromeifs · arpege · phealth · vague-surcote
# ⛔ AUCUN `aromepi` — vérifié. AROME-PI n'est PAS sur le miroir, et tous
# les runs du miroir sont aux heures synoptiques (00, 03, 06…), jamais
# horaires. C'est ce qui rend la route WCS OBLIGATOIRE pour PI.
# ⓘ `aromeifs` existe en 0025 avec la MÊME structure de paquets qu'AROME
# (HP1-3, IP1-5, SP1-3) — candidat naturel pour le « second avis »
# cherché du côté d'ICON-D2, à bien moindre coût. Non sondé, hors lot H.
MODELES_S3 = ("arome", "arome-om", "aromeifs", "arpege", "phealth",
              "vague-surcote")

UA = "balise-watch-arome/1"

# Deux nommages coexistent, et le code doit lire les deux :
#   grille 001  → UN FICHIER PAR HEURE          (`__06H__`)
#   grille 0025 → GROUPÉ PAR TRANCHES DE 6 h    (`__00H06H__`)
_RE_ECHEANCES = re.compile(r"__(\d+)H(?:(\d+)H)?__")


# ⚠️ LE MIROIR COUPE PARFOIS LA CONNEXION, ET C'EST MESURÉ, PAS SUPPOSÉ.
# Le 10/08/2026, un simple `ListObjectsV2` a rendu
# `URLError(ConnectionResetError(104))` en plein milieu d'une ingestion,
# sans rien d'autre d'anormal — la même requête relancée est passée du
# premier coup. Ce n'est ni un quota (le miroir n'en a pas) ni une panne :
# c'est du bruit de réseau ordinaire sur des objets de plusieurs centaines
# de mégaoctets.
#
# Sans reprise, ce bruit fait échouer un run entier — et pour la chaîne
# `arome-wind`, un run échoué signifie des tuiles qui restent celles du
# run précédent jusqu'au suivant. Trois essais avec une attente qui
# grandit suffisent largement ; au-delà, c'est une vraie panne et il faut
# qu'elle remonte.
ESSAIS = 3


def http_get(url, timeout=180, essais=ESSAIS, journal=None):
    dernier = None
    for essai in range(essais):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, urllib.error.HTTPError,
                TimeoutError, OSError) as e:
            dernier = e
            if essai == essais - 1:
                break
            if journal:
                journal(f"  ⟳ {type(e).__name__} sur le miroir S3 — "
                        f"essai {essai + 2}/{essais}")
            time.sleep(1.5 * (essai + 1))
    raise dernier


def s3_objets(prefix):
    """[(clé, taille en octets)] sous un préfixe (S3 ListObjectsV2).

    ⚠️ La taille vient du listing, donc AUCUN téléchargement : c'est ce
    qui a permis de mesurer les 2,87 Go de HP1 sur 0–24 h sans tirer un
    octet de GRIB. À préférer à `s3_keys` dès qu'on veut dimensionner.
    """
    url = f"{S3}/?list-type=2&prefix={urllib.parse.quote(prefix)}&max-keys=1000"
    root = ET.fromstring(http_get(url, 60))
    out = []
    for c in root.iter():
        if c.tag.split("}")[-1] != "Contents":
            continue
        cle = taille = None
        for e in c:
            t = e.tag.split("}")[-1]
            if t == "Key":
                cle = e.text
            elif t == "Size":
                taille = int(e.text)
        if cle is not None:
            out.append((cle, taille or 0))
    return out


def s3_keys(prefix):
    """Liste les clés d'objets sous un préfixe (S3 ListObjectsV2).

    Signature et comportement IDENTIQUES à la version qui vivait dans
    `arome-wind/ingest.py` — c'est volontaire, cette fonction est
    appelée par du code de production qui ne doit pas changer d'un iota.
    """
    return [k for k, _ in s3_objets(prefix)]


def bornes_echeances(cle):
    """(début, fin) des échéances couvertes par un fichier, ou None si le
    nom ne porte pas de motif d'échéance. Un fichier horaire a
    début == fin."""
    m = _RE_ECHEANCES.search(cle)
    if not m:
        return None
    start = int(m.group(1))
    return start, (int(m.group(2)) if m.group(2) else start)


def est_fichier_horaire(cle):
    """Le nom porte-t-il UNE seule échéance (`__06H__`) plutôt qu'une
    tranche (`__00H06H__`) ?

    ⚠️ Ce n'est PAS la même chose que « début == fin ». Un hypothétique
    `__06H06H__` serait une tranche d'une seule heure, et le distinguer
    compte : sur les fichiers horaires on peut ne tirer que les échéances
    retenues, sur une tranche on tire tout ou rien. Le test d'origine
    dans `files_for` portait bien sur la PRÉSENCE du second groupe ; on
    la conserve telle quelle plutôt que de la réinventer en comparant
    des entiers.
    """
    m = _RE_ECHEANCES.search(cle)
    return bool(m) and m.group(2) is None


def covered_steps(ref, pkg, grid, steps_needed, model="arome", lister=s3_keys):
    """Sous-ensemble de `steps_needed` réellement couvert par les fichiers
    DÉJÀ PUBLIÉS du paquet `pkg`/grille `grid` pour ce run.

    Simple listing S3 (quelques ko), AUCUN téléchargement — c'est ce qui
    rend `pick_run()` abordable, et c'est aussi ce qui rend le poller du
    lot H possible : interroger la disponibilité d'un run toutes les 2-3
    minutes ne coûte rien.

    `lister` est injectable pour les bancs de test hors-ligne.
    """
    want = set(steps_needed)
    covered = set()
    for k in lister(f"pnt/{ref}/{model}/{grid}/{pkg}/"):
        b = bornes_echeances(k)
        if b is None:
            continue
        start, end = b
        covered |= {h for h in want if start <= h <= end}
    return covered


def download_tmp(key, journal=print):
    """Télécharge un objet S3 (gros GRIB) vers un fichier temporaire et
    renvoie son chemin.

    ⚠️ L'APPELANT EST RESPONSABLE DE LA SUPPRESSION, et ce n'est pas une
    formalité : le disque du runner GitHub fait 14 Go, un run AGRUME
    complet tire 4,84 Go de GRIB (HP1 + HP2 sur 0–24 h) et la chaîne
    actuelle en tire déjà 4,4 — les deux ne tiennent pas ensemble. La
    consigne est de traiter BUNDLE PAR BUNDLE et de supprimer au fil de
    l'eau. La mémoire, elle, n'est pas un sujet : pic RSS mesuré à
    88,0 Mo pour digérer un fichier de 818 Mo.

    ⚠️ Une coupure EN COURS DE TÉLÉCHARGEMENT est le pire cas : elle
    laisse un fichier TRONQUÉ, qu'eccodes lira sans broncher jusqu'au
    dernier message complet. On aurait donc un run silencieusement
    incomplet plutôt qu'une erreur. La reprise repart donc de zéro sur un
    fichier neuf, et on compare la taille obtenue à celle annoncée par le
    listing quand elle est connue.
    """
    url = f"{S3}/{urllib.parse.quote(key)}"
    t0 = time.time()
    dernier = None
    for essai in range(ESSAIS):
        fd, path = tempfile.mkstemp(suffix=".grib2")
        os.close(fd)
        try:
            with urllib.request.urlopen(urllib.request.Request(
                    url, headers={"User-Agent": UA}), timeout=300) as r, \
                    open(path, "wb") as out:
                annonce = r.headers.get("Content-Length")
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
            recu = os.path.getsize(path)
            if annonce and int(annonce) != recu:
                raise OSError(f"téléchargement tronqué : {recu} octets reçus "
                              f"sur {annonce} annoncés")
            break
        except (urllib.error.URLError, urllib.error.HTTPError,
                TimeoutError, OSError) as e:
            dernier = e
            try:
                os.unlink(path)
            except OSError:
                pass
            if essai == ESSAIS - 1:
                raise
            if journal:
                journal(f"  ⟳ {type(e).__name__} en cours de téléchargement de "
                        f"{key.split('/')[-1]} — on repart de zéro "
                        f"(essai {essai + 2}/{ESSAIS})")
            time.sleep(2.0 * (essai + 1))
        except BaseException:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise
    else:                                          # pragma: no cover
        raise dernier
    mo = os.path.getsize(path) / (1 << 20)
    dt = time.time() - t0
    if journal:
        journal(f"  ↓ {key.split('/')[-1]} ({mo:.0f} Mo, {dt:.1f}s, "
                f"{mo / max(dt, 1e-6):.1f} Mo/s)")
    return path
