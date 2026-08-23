#!/usr/bin/env python3
"""test_collect.py — le témoin d'envoi R2, sa reprise, et la cadence.

    Écrit après le premier essai réel sur le VPS, où un `AccessDenied`
    sur `PutObject` a laissé le run sortir en 0 avec une archive qui
    n'existait que sur le disque local.

⚠️ CE QUE CE BANC VÉRIFIE, ET DANS QUELLE LANGUE. `rattraper()` et
`en_retard()` n'ont qu'UN appelant connu — `main()` de `collect.py`, qui
leur passe la racine `--out` et attend d'`upload_r2` une clé relative
en POSIX (`fcst/2026/08/fcst_2026-08-07.ndjson.gz`). Une partie des
assertions parle donc exactement cette langue-là : un banc qui
inventerait ses propres clés testerait la fonction et pas l'intégration,
et c'est précisément par une clé mal formée que l'archive irait se
ranger ailleurs sans que rien ne le dise.

    python3 test_collect.py
"""
from __future__ import annotations

import gzip
import pathlib
import sys
import tempfile
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import collect as C                                     # noqa: E402

ok = 0
ko: list[str] = []


def verifie(cond: bool, quoi: str) -> None:
    global ok
    if cond:
        ok += 1
    else:
        ko.append(quoi)


def archive(racine: pathlib.Path, cle: str, lignes: int = 1) -> pathlib.Path:
    """Une archive locale plausible, à la clé que `main()` emploierait."""
    p = racine / cle
    p.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(p, "wt", encoding="utf-8") as fh:
        for i in range(lignes):
            fh.write('{"n":%d}\n' % i)
    return p


# ── 1. le témoin se pose à côté, sans écraser l'objet ────────────────
with tempfile.TemporaryDirectory() as d:
    out = pathlib.Path(d)
    p = archive(out, "fcst/2026/08/fcst_2026-08-07.ndjson.gz")
    t = C.temoin(p)
    verifie(t.name == "fcst_2026-08-07.ndjson.gz.r2ok", "nom du témoin")
    verifie(t.parent == p.parent, "témoin dans le même dossier que l'objet")
    verifie(not t.exists(), "pas de témoin tant que rien n'est monté")

# ── 2. en_retard : ce qui n'est pas monté, et rien d'autre ───────────
with tempfile.TemporaryDirectory() as d:
    out = pathlib.Path(d)
    verifie(C.en_retard(out) == [], "répertoire vide → aucun retard")

    a = archive(out, "fcst/2026/08/fcst_2026-08-06.ndjson.gz")
    b = archive(out, "obs/2026/08/obs_2026-08-06.ndjson.gz")
    verifie(C.en_retard(out) == sorted([a, b]), "les deux archives sont en retard")

    C.temoin(a).write_text("2026-08-06T03:20:00Z\n", encoding="utf-8")
    verifie(C.en_retard(out) == [b], "l'archive témoignée sort de la liste")

    # ⚠️ Le témoin lui-même ne doit jamais être pris pour une archive :
    # `*.ndjson.gz.r2ok` ne se termine pas par `.ndjson.gz`, mais un
    # glob trop lâche (`*.gz*`) l'attraperait et le dispositif
    # essaierait d'envoyer ses propres témoins, indéfiniment.
    verifie(all(p.suffixes[-1] == ".gz" for p in C.en_retard(out)),
            "un témoin n'est pas une archive")

    # `stations.json` vit dans la même racine et n'est pas une archive.
    (out / "stations.json").write_text("[]", encoding="utf-8")
    verifie(C.en_retard(out) == [b], "stations.json n'est pas une archive")

# ── 3. rattraper() parle la langue de main() ─────────────────────────
with tempfile.TemporaryDirectory() as d:
    out = pathlib.Path(d)
    archive(out, "fcst/2026/08/fcst_2026-08-05.ndjson.gz")
    archive(out, "obs/2026/07/obs_2026-07-31.ndjson.gz")

    vus: list[tuple[str, str]] = []

    def _faux_upload(path: pathlib.Path, key: str) -> bool:
        vus.append((str(path), key))
        C.temoin(path).write_text("essai\n", encoding="utf-8")
        return True

    reel, C.upload_r2 = C.upload_r2, _faux_upload
    try:
        C.rattraper(out)
    finally:
        C.upload_r2 = reel

    cles = sorted(k for _, k in vus)
    verifie(cles == ["fcst/2026/08/fcst_2026-08-05.ndjson.gz",
                     "obs/2026/07/obs_2026-07-31.ndjson.gz"],
            f"clés relatives POSIX, telles que main() les construit — vu {cles}")
    verifie(all(not k.startswith("/") for _, k in vus),
            "aucune clé absolue (elle créerait un préfixe vide sur R2)")
    verifie(C.en_retard(out) == [], "plus rien en retard après un rattrapage réussi")

# ── 4. un envoi qui échoue ne pose pas de témoin ─────────────────────
with tempfile.TemporaryDirectory() as d:
    out = pathlib.Path(d)
    a = archive(out, "fcst/2026/08/fcst_2026-08-04.ndjson.gz")

    reel, C.upload_r2 = C.upload_r2, lambda p, k: False
    try:
        C.rattraper(out)
    finally:
        C.upload_r2 = reel

    verifie(C.en_retard(out) == [a],
            "l'archive reste en retard tant qu'elle n'est pas montée")
    verifie(a.exists(), "et surtout : le fichier local n'est PAS jeté")

# ── 4 bis. un témoin périmé ne couvre pas une archive réécrite ───────
# ⚠️ Le cas exact rencontré le 07/08 : l'essai à 5 points monte son
# archive et pose son témoin, puis le run complet RÉÉCRIT le même chemin
# avec 648 points. Si l'envoi de la nouvelle version échoue, un témoin
# resté en place affirmerait qu'elle est à l'abri. `upload_r2` doit donc
# supprimer le témoin AVANT de retenter, quoi qu'il arrive ensuite.
with tempfile.TemporaryDirectory() as d:
    out = pathlib.Path(d)
    a = archive(out, "fcst/2026/08/fcst_2026-08-07.ndjson.gz", lignes=3)
    C.temoin(a).write_text("2026-08-07T09:36:00Z\n", encoding="utf-8")
    verifie(C.en_retard(out) == [], "au départ, l'archive est réputée montée")

    # Le run complet réécrit le même chemin, avec 648 points.
    a = archive(out, "fcst/2026/08/fcst_2026-08-07.ndjson.gz", lignes=648)

    # On appelle le VRAI `upload_r2`, en le condamnant à échouer sans
    # toucher au réseau : `storage.py` refuse un `STORAGE_BACKEND`
    # inconnu dès la construction, avant toute requête. Un faux
    # `upload_r2` ne prouverait rien ici — c'est précisément le geste du
    # vrai qu'on veut vérifier.
    import os
    backend_avant = os.environ.get("STORAGE_BACKEND")
    os.environ["STORAGE_BACKEND"] = "banc-essai-inexistant"
    try:
        monte = C.upload_r2(a, "fcst/2026/08/fcst_2026-08-07.ndjson.gz")
    finally:
        if backend_avant is None:
            os.environ.pop("STORAGE_BACKEND", None)
        else:
            os.environ["STORAGE_BACKEND"] = backend_avant

    verifie(monte is False, "l'envoi condamné rend bien False")
    verifie(not C.temoin(a).exists(),
            "upload_r2 supprime le témoin périmé AVANT de tenter")
    verifie(C.en_retard(out) == [a],
            "la réécriture non montée est vue comme en retard")
    verifie(a.exists() and a.stat().st_size > 0,
            "et le fichier local de 648 points n'est pas touché")


# ── 5. le plafond borne, et le DIT ───────────────────────────────────
with tempfile.TemporaryDirectory() as d:
    out = pathlib.Path(d)
    for j in (1, 2, 3, 4):
        archive(out, f"fcst/2026/08/fcst_2026-08-0{j}.ndjson.gz")

    envoyes: list[str] = []

    def _compte(path: pathlib.Path, key: str) -> bool:
        envoyes.append(key)
        C.temoin(path).write_text("essai\n", encoding="utf-8")
        return True

    import io
    from contextlib import redirect_stdout
    tampon = io.StringIO()
    reel, C.upload_r2 = C.upload_r2, _compte
    try:
        with redirect_stdout(tampon):
            C.rattraper(out, plafond=2)
    finally:
        C.upload_r2 = reel

    sortie = tampon.getvalue()
    verifie(len(envoyes) == 2, f"le plafond borne l'envoi — {len(envoyes)} envoyé(s)")
    verifie(len(C.en_retard(out)) == 2, "les deux autres restent en retard")
    # ⚠️ « Pas de plafond silencieux » : un lot tronqué qui se tait a
    # exactement l'allure d'une reprise complète.
    verifie("2 laissée(s)" in sortie, f"le reste est annoncé — sortie : {sortie!r}")
    # Les plus anciennes d'abord : c'est la nuit la plus ancienne qui
    # risque le plus de disparaître avec le disque.
    verifie(envoyes == ["fcst/2026/08/fcst_2026-08-01.ndjson.gz",
                        "fcst/2026/08/fcst_2026-08-02.ndjson.gz"],
            f"les plus anciennes d'abord — vu {envoyes}")

# ── 6. rien à rattraper : pas un mot ─────────────────────────────────
with tempfile.TemporaryDirectory() as d:
    out = pathlib.Path(d)
    p = archive(out, "fcst/2026/08/fcst_2026-08-03.ndjson.gz")
    C.temoin(p).write_text("essai\n", encoding="utf-8")
    import io
    from contextlib import redirect_stdout
    tampon = io.StringIO()
    with redirect_stdout(tampon):
        C.rattraper(out)
    verifie(tampon.getvalue() == "", "un run sans retard ne dit rien")


# ── 7. le garde-fou de cadence ───────────────────────────────────────
# ⚠️ C'est le contrôle qui n'a PAS protégé le run du 07/08 : il comparait
# une cadence en requêtes brutes (240/min) à un plafond en appels
# PONDÉRÉS (600/min), donc il ne pouvait pas se déclencher. Les
# assertions ci-dessous parlent la langue de `main()` : 648 points,
# 3 jours de prévision, les 10 modèles réels.
import io                                               # noqa: E402
from contextlib import redirect_stdout                  # noqa: E402

with redirect_stdout(io.StringIO()) as tampon:
    total = C.quota_projete(648, 3)
sortie = tampon.getvalue()

# ⚠️ MIS À JOUR LE 22/08 (S0.4) : le poids d'un point ne vaut plus
# `len(_hourly_vars()) × len(MODELS)`, parce que la requête d'un point
# est découpée en groupes qui ne demandent pas les mêmes variables.
# `poids_par_point()` est la seule source — et le banc du bloc S0.4
# vérifie qu'elle est d'accord avec `quota_openmeteo.poids_url()`.
verifie(abs(total - 648 * C.poids_par_point()) < 1e-6,
        f"le total suit la pondération sans remise de jours — {total}")
verifie(total > 3000, f"648 points pèsent plus de 3000 pondérés, pas 694 — {total:.0f}")
verifie("fenêtre HORAIRE" in sortie,
        "l'encadré annonce la fenêtre HORAIRE — celle qui a tué le 09/08")
verifie(f"{C.QUOTA_HEURE}" in sortie, "et le plafond de l'heure, en clair")

# ⚠️ CE BANC A CHANGÉ DE NATURE LE 09/08, ET C'EST LE FOND DU LOT.
# Il vérifiait une CADENCE dérivée de deux constantes de pause. Ces
# constantes ont disparu : la cadence est maintenant tenue par le seau à
# jetons de `tools/quota_openmeteo.py`, qui la MESURE au lieu de
# l'espérer (son banc à lui, `tools/test_quota_openmeteo.py`, prouve
# qu'elle ne bouge plus quand la latence varie de 0,05 s à 0,40 s).
# Ce qu'aucun seau ne peut corriger, c'est un VOLUME qui ne tient pas
# dans une fenêtre — et c'est cela que ce banc surveille désormais.
verifie(total <= C.QUOTA_HEURE * 0.95,
        f"le run tient dans la fenêtre horaire — {total:.0f} / {C.QUOTA_HEURE}")

# ⚠️ LA CONFIGURATION DU 09/08 — ET CE BANC A CHANGÉ DE RÉPONSE LE
# 22/08. IL FAUT LE LIRE, PAS LE CROIRE.
#
# Le 09/08, la requête était UNIQUE : 8 variables × 10 modèles = 8,0
# pondérés par point, soit 5 184 pour 648 points — au-dessus des 5 000
# de l'heure. Le run s'était arrêté à 625 points collectés (5 000 à
# l'unité près) puis n'avait plus rien obtenu pendant 26 minutes, et
# ICON-CH1 avait été retiré pour faire tenir le reste.
#
# Depuis le S0.4, la requête est découpée : à 10 modèles elle pèse
# (2 × 8 + 8 × 6) / 10 = 6,4, soit 4 147 pour 648 points. ⭐ **La
# configuration du 09/08 TIENDRAIT aujourd'hui.** C'est un fait, pas
# une invitation : réintroduire ICON-CH1 est une décision de contenu
# (elle ramène la marge horaire de 818 à 742 points), et le pavé de
# `MODELS` dit ce qu'il faut remesurer avant d'y toucher.
#
# Ce banc tient donc deux choses distinctes :
#   1. la FORME du 09/08 (une requête, 8 vars × 10 modèles) dépasse
#      toujours l'heure — calculé par `poids_url`, l'autorité ;
#   2. le garde-fou refuse toujours quand le volume déborde vraiment —
#      vérifié par MUTATION, en ajoutant assez de modèles pour franchir
#      la ligne même avec le découpage.
import urllib.parse as _up_09                           # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tools"))
import quota_openmeteo as _QM09                         # noqa: E402

_url_09 = f"{C.FORECAST_API}?" + _up_09.urlencode({
    "latitude": "45.3193", "longitude": "6.5800",
    "hourly": ",".join(C._hourly_vars()),
    "models": ",".join(list(C.MODELS) + ["meteoswiss_icon_ch1"]),
    "forecast_days": "3", "wind_speed_unit": "kmh", "timeformat": "unixtime"})
verifie(648 * _QM09.poids_url(_url_09) > C.QUOTA_HEURE * 0.95,
        f"la FORME du 09/08 — une seule requête, 8 vars × 10 modèles — pèse "
        f"{648 * _QM09.poids_url(_url_09):.0f} et dépasse toujours l'heure")

modeles_avant = C.MODELS
C.MODELS = list(modeles_avant) + [f"modele_de_banc_{i}" for i in range(3)]
try:
    refuse = False
    try:
        with redirect_stdout(io.StringIO()):
            C.quota_projete(648, 3)
    except C.Abort as exc:
        refuse = True
        motif = str(exc)
    verifie(refuse,
            "MUTATION — douze modèles débordent l'heure MÊME découpés, et le "
            "garde-fou refuse encore : il n'a pas été rendu tolérant")
    verifie(refuse and "heure" in motif,
            "et le refus dit que c'est l'HEURE qui bloque, pas la cadence")
finally:
    C.MODELS = modeles_avant

# ⚠️ AUCUNE CONSTANTE DE LATENCE NE DOIT REVENIR. Le seau existe pour
# n'avoir plus à connaître la latence ; si quelqu'un en réintroduit une
# pour « affiner », c'est que le lot a été défait.
verifie(not hasattr(C, "LATENCE_S"),
        "plus aucune constante de latence dans collect.py")
verifie(not hasattr(C, "FCST_PAUSE_S"),
        "plus de pause fixe pour la passe prévisions — le seau la remplace")

# ⛔⛔ LE SEUIL JOURNALIER DE 60 % NE PEUT RIEN REFUSER QUE L'HORAIRE NE
# REFUSE DÉJÀ — trouvé en mutant ce banc le 22/08 (S0.4) : on a remplacé
# le `raise` journalier par un `if False`, et RIEN n'est devenu rouge.
# La raison est arithmétique et ne dépend d'aucune mesure :
#
#     QUOTA_HEURE × 0,95 = 4 750   <   QUOTA_JOUR × 0,60 = 6 000
#
# Tout run d'UNE passe qui franchit 6 000 franchit forcément 4 750. Le
# seuil journalier ne décidait donc pas SI le run est refusé, seulement
# QUEL MESSAGE sort — et il sortait le moins utile des deux, celui qui
# désigne la journée là où c'est l'heure qui ferme la porte.
#
# ⇒ Les deux gardes ont été INVERSÉES le 22/08 : l'heure parle d'abord.
# Le seuil journalier reste écrit, inerte, et redeviendra le seul
# garde-fou utile le jour où la collecte sera PARTITIONNÉE en plusieurs
# passes horaires — chaque passe tiendra alors sous 4 750 et c'est LEUR
# SOMME qui devra tenir sous le plafond du jour. Il devra alors comparer
# au budget MESURÉ (`Budget.etat()`), pas à 60 % d'un plafond brut.
# Entrée `BUGS.md` du 22/08.
verifie(C.QUOTA_HEURE * 0.95 < C.QUOTA_JOUR * 0.6,
        f"le seuil HORAIRE ({C.QUOTA_HEURE * 0.95:.0f}) est plus strict que le "
        f"seuil JOURNALIER ({C.QUOTA_JOUR * 0.6:.0f}) — c'est ce recouvrement "
        f"qui rend le second inerte à une passe. Si cette assertion tombe, "
        f"quelqu'un a touché une des deux constantes et le raisonnement du "
        f"pavé de `quota_projete` est à refaire.")
motif_1300 = ""
try:
    with redirect_stdout(io.StringIO()):
        C.quota_projete(1300, 3)
except C.Abort as exc:
    motif_1300 = str(exc)
verifie(motif_1300 and "l'heure n'en autorise" in motif_1300,
        f"⭐ 1300 points restent REFUSÉS, et le message nomme la fenêtre qui "
        f"ferme vraiment la porte : l'HEURE. Avant le 22/08 il annonçait "
        f"« 60 % du plafond journalier », ce qui envoyait chercher au mauvais "
        f"endroit — {motif_1300[:70]}")

# ── 7 bis. les variables d'E4/E6 sont bien demandées ─────────────────
# ⚠️ Ce n'est pas une assertion décorative : ces trois variables sont la
# seule chose de ce dépôt qu'on ne peut pas rattraper. Si quelqu'un les
# retire pour « alléger le quota », il faut que ce banc hurle le jour
# même, pas qu'on s'en aperçoive dans six mois devant une archive vide.
vars_demandees = C._hourly_vars()
for v in ("precipitation", "pressure_msl", "temperature_2m"):
    verifie(v in vars_demandees, f"`{v}` est demandée à Open-Meteo (E4/E6)")
verifie("surface_pressure" not in vars_demandees,
        "`surface_pressure` reste ÉCARTÉE — redondante avec `pressure_msl`, "
        "et 648 pondérés/nuit de plus")


# ── 7 ter. une clé pleine de nulls n'entre pas dans l'archive ────────
# ⚠️ SONDÉ LE 08/08 : AROME rend `pressure_msl_meteofrance_arome_france_hd`
# PRÉSENTE et intégralement nulle. Un `get` naïf archiverait 72 nulls
# par balise et par nuit, qui se reliraient dans un an comme une donnée.
_st = {"id": "42", "source": "pioupiou", "lat": 45.2, "lon": 6.42}
_hourly = {
    "time": [0, 3600, 7200],
    # deux modèles servent le point → suffixes présents, cas nominal
    "wind_speed_10m_gfs_global": [10.0, 11.0, 12.0],
    "wind_speed_10m_meteofrance_arome_france_hd": [9.0, 9.5, 10.0],
    # AROME : clé présente, tout nul — le cas réel
    "pressure_msl_meteofrance_arome_france_hd": [None, None, None],
    "precipitation_meteofrance_arome_france_hd": [0.0, 0.1, 0.0],
    # GFS : sert la pression
    "pressure_msl_gfs_global": [1013.0, 1012.5, 1012.0],
    # personne ne sert la température ici → clé absente des deux côtés
}
_lignes = {r["model"]: r for r in
           C.forecast_rows(_st, {"hourly": _hourly}, "2026-08-08T03:18:00+00:00")}
_arome = _lignes.get("meteofrance_arome_france_hd")
_gfs = _lignes.get("gfs_global")
verifie(_arome is not None and "pmsl" not in _arome,
        "AROME : `pressure_msl` toute nulle → champ ABSENT de la ligne, pas [null,…]")
verifie(_arome is not None and _arome.get("precip") == [0.0, 0.1, 0.0],
        "AROME : `precipitation` servie → archivée, y compris les 0.0")
verifie(_gfs is not None and _gfs.get("pmsl") == [1013.0, 1012.5, 1012.0],
        "GFS : `pressure_msl` servie → archivée")
verifie(_arome is not None and "t2m" not in _arome and _gfs is not None
        and "t2m" not in _gfs,
        "variable absente de la réponse → champ absent de la ligne")
# Et les champs historiques n'ont pas bougé — c'est une EXTENSION.
for _champ in ("station_id", "source", "lat", "lon", "model", "fetched_at",
               "t0", "step_s", "speed", "dir", "gust"):
    verifie(_champ in _gfs, f"le champ historique `{_champ}` est toujours là")


# ── 8. le 429 prend une pause franche, une seule fois ────────────────
# ⚠️ Trois réessais à 1-2-4 s sur une porte fermée une minute, c'est ce
# qui a transformé un ralentissement en 24 nuits perdues.
import urllib.error                                     # noqa: E402

appels = {"n": 0}
dormi: list[float] = []


def _toujours_429(url, timeout=None):
    appels["n"] += 1
    raise urllib.error.HTTPError(url, 429, "Too Many Requests", None, None)


get_avant, sleep_avant, pause_avant = C._get_json, time.sleep, C.PAUSE_429_S
C._get_json, time.sleep, C.PAUSE_429_S = _toujours_429, dormi.append, 65
try:
    with redirect_stdout(io.StringIO()):
        r = C._get_json_retry("https://exemple/x", "essai")
finally:
    C._get_json, time.sleep, C.PAUSE_429_S = get_avant, sleep_avant, pause_avant

verifie(r is None, "un 429 persistant finit par abandonner le point")
verifie(65 in dormi, f"une pause franche de 65 s a bien eu lieu — {dormi}")
verifie(dormi.count(65) == 1,
        f"UNE seule pause longue, pas une par réessai — {dormi}")
verifie(appels["n"] == C.MAX_RETRIES,
        f"le budget de réessais reste celui de MAX_RETRIES — {appels['n']}")


# ── 9. METAR : les conversions, et les deux façons d'être vide ───────
# ⚠️ Ce banc ne teste PAS qu'Iowa State répond — un banc qui appelle le
# réseau ment un jour sur dix. Il teste ce qui, ici, se trompe en
# silence : une unité mal convertie, un QNH lu dans la mauvaise colonne,
# une station vide archivée quand même.
_aeros = [
    {"id": "LFLS", "source": "metar", "network": "FR__ASOS",
     "lat": 45.3629, "lon": 5.3294, "elev": 384.0, "name": "Grenoble"},
    {"id": "LFMN", "source": "metar", "network": "FR__ASOS",
     "lat": 43.66, "lon": 7.21, "elev": 4.0, "name": "Nice"},
    {"id": "LFXX", "source": "metar", "network": "FR__ASOS",
     "lat": 45.0, "lon": 5.0, "elev": 0.0, "name": "Muette"},
]
_csv = "\n".join([
    "station,valid,lon,lat,drct,sknt,gust,alti,tmpf",
    # 10 kt = 18,52 km/h ; 29,92 inHg = 1013,21 hPa ; 68 °F = 20,0 °C
    "LFLS,2026-08-07 00:00,5.3294,45.3629,250.00,10.00,,29.92,68.00",
    # rafale absente (le cas à 99,6 %) et direction absente (17 %)
    "LFLS,2026-08-07 01:00,5.3294,45.3629,,3.00,,29.95,66.20",
    "LFMN,2026-08-07 00:00,7.21,43.66,90.00,5.00,25.00,30.00,77.00",
    # station connue du référentiel mais qui n'a rien mesuré
    "LFXX,2026-08-07 00:00,5.0,45.0,,,,,",
    # station INCONNUE du référentiel — doit être ignorée, pas devinée
    "EGLL,2026-08-07 00:00,-0.46,51.47,200.00,12.00,,29.80,60.00",
])
_texte_avant = C._get_text
try:
    C._get_text = lambda url, timeout=120: _csv
    _m = {r["station_id"]: r for r in C.metar_rows(_aeros, "2026-08-07")}
finally:
    C._get_text = _texte_avant

verifie(set(_m) == {"LFLS", "LFMN"},
        f"seules les stations du référentiel qui ont mesuré sont archivées — {sorted(_m)}")
verifie("LFXX" not in _m,
        "un aérodrome présent au référentiel mais muet n'entre PAS dans l'archive")
_l = _m.get("LFLS", {})
verifie(_l.get("speed") == [18.5, 5.6],
        f"les nœuds deviennent des km/h (10 kt → 18,5) — {_l.get('speed')}")
verifie(_l.get("qnh") == [1013.21, 1014.22],
        f"les pouces de mercure deviennent des hPa (29,92 → 1013,21) — {_l.get('qnh')}")
verifie(_l.get("t2m") == [20.0, 19.0],
        f"les °F deviennent des °C (68 → 20,0) — {_l.get('t2m')}")
verifie("precip" not in _l,
        "AUCUN champ de précipitation dans l'archive METAR — `p01i` vaut 0.00 "
        "partout en Europe (5 856 valeurs sondées, 0 non nulle), et un zéro "
        "faux se relit comme « il n'a pas plu »")
verifie(_l.get("gust") == [None, None],
        "une rafale non diffusée reste None — elle ne vaut PAS zéro")
verifie(_l.get("dir") == [250.0, None],
        f"une direction absente reste None — {_l.get('dir')}")
verifie(_l.get("t") == [1786060800, 1786064400],
        f"les horodatages sont lus en UTC — {_l.get('t')}")
verifie(_l.get("elev") == 384.0 and _l.get("network") == "FR__ASOS",
        "l'altitude du terrain et le réseau sont archivés (le QNH n'est pas du pressure_msl)")
verifie(_m.get("LFMN", {}).get("gust") == [46.3],
        f"une rafale diffusée est convertie (25 kt → 46,3) — {_m.get('LFMN', {}).get('gust')}")

# ⚠️ Un en-tête qui change de forme doit faire ABANDONNER, pas décaler.
try:
    C._get_text = lambda url, timeout=120: "station,valid,lon,lat,drct,sknt\nLFLS,x,1,2,3,4"
    with redirect_stdout(io.StringIO()):
        _vide = list(C.metar_rows(_aeros, "2026-08-07"))
finally:
    C._get_text = _texte_avant
verifie(_vide == [],
        "un en-tête inattendu → zéro ligne, pas des colonnes devinées")

# ⚠️ Et le flux ne doit jamais s'exécuter sur un référentiel vide.
verifie(list(C.metar_rows([], "2026-08-07")) == [],
        "référentiel METAR vide → aucune requête, aucune ligne")

verifie("alti" in C.METAR_CHAMPS and "mslp" not in C.METAR_CHAMPS,
        "on demande `alti` (100 % rempli) et PAS `mslp` (2 %) — sondé le 08/08")
verifie("p01i" not in C.METAR_CHAMPS,
        "on ne demande PAS `p01i` : servi à 100 % en Europe, nul à 100 % — "
        "la vérité terrain d'E4 passe par Météo-France, pas par le METAR")


# ── 10. WINDSMOBI : référentiel, historique, cadence nocturne ────────
# ⚠️ CES DEUX FIXTURES SONT DES RÉPONSES RÉELLES ENREGISTRÉES, pas
# fabriquées — capturées le 21/08/2026 avec le user-agent obligatoire
# (`WINDSMOBI_UA`), UN appel par endpoint, aucune rafale :
#   GET /stations/?provider=yvbeach&limit=0            (le référentiel)
#   GET /stations/yvbeach-yvbeach/historic/?duration=3600  (l'historique)
# yvbeach est un réseau à une seule balise : la réponse tient entière
# ici, sans troncature ni paraphrase.
import json                                             # noqa: E402

_WM_REFERENTIEL_YVBEACH = json.loads(
    '[{"_id":"yvbeach-yvbeach","alt":430,"loc":{"type":"Point",'
    '"coordinates":[6.714839,46.80541]},"name":"Yvonand plage",'
    '"peak":false,"pv-name":"yvbeach.com","short":"yvbeach",'
    '"status":"green","tz":"Europe/Zurich","last":{"_id":1787312400,'
    '"w-dir":253,"w-avg":7.6,"w-max":11.3,"temp":17.4}}]'
)
_WM_HISTORIC_YVBEACH = json.loads(
    '[{"_id":1787312400,"w-dir":253,"w-avg":7.6,"w-max":11.3,"temp":17.4},'
    '{"_id":1787311800,"w-dir":242,"w-avg":4.1,"w-max":9.7,"temp":17.1},'
    '{"_id":1787311500,"w-dir":228,"w-avg":4.8,"w-max":9.7,"temp":16.9},'
    '{"_id":1787310900,"w-dir":249,"w-avg":6.1,"w-max":9.7,"temp":16.4},'
    '{"_id":1787310600,"w-dir":245,"w-avg":6.1,"w-max":9.7,"temp":16.6},'
    '{"_id":1787310000,"w-dir":247,"w-avg":6.7,"w-max":9.7,"temp":16.6},'
    '{"_id":1787309700,"w-dir":247,"w-avg":6.8,"w-max":9.7,"temp":16.6},'
    '{"_id":1787309100,"w-dir":247,"w-avg":5.9,"w-max":8.0,"temp":16.4},'
    '{"_id":1787308800,"w-dir":247,"w-avg":5.7,"w-max":8.0,"temp":16.6}]'
)
# Tous les `_id` de l'historique tombent le 2026-08-21 UTC (11:40 → 10:40).

_wm_get_avant = C._get_json_windsmobi


def _wm_route(referentiel_par_provider, historic_par_id, echecs_historic=()):
    """Un faux `_get_json_windsmobi` qui distingue les deux formes
    d'URL EXACTEMENT comme collect.py les construit — un banc qui
    inventerait ses propres routes testerait le mock, pas l'appelant.
    """
    def _fake(path, timeout=60):
        if path.startswith("/stations/?provider="):
            provider = path.split("provider=", 1)[1].split("&", 1)[0]
            return referentiel_par_provider.get(provider, [])
        if "/historic/?duration=" in path:
            sid = path.split("/stations/", 1)[1].split("/historic/", 1)[0]
            if sid in echecs_historic:
                raise RuntimeError("HTTP 500 (simulé)")
            return historic_par_id.get(sid)
        raise AssertionError(f"route windsmobi inattendue dans le test : {path}")
    return _fake


# ── 10.1 le référentiel : un vrai réseau, plus deux cas fabriqués pour
#         couvrir les filtres (status, sans vent, hors BBOX) que la
#         réponse réelle, à elle seule, ne traverse pas.
_wm_extra = {
    "holfuy": [
        # station masquée : ne doit jamais entrer dans l'archive
        {"_id": "holfuy-1", "loc": {"coordinates": [6.0, 45.5]}, "alt": 1200,
         "status": "hidden", "last": {"_id": 1787312400, "w-avg": 3.0}},
        # station connue mais qui n'a jamais mesuré de vent
        {"_id": "holfuy-2", "loc": {"coordinates": [6.1, 45.6]}, "alt": 900,
         "status": "green", "last": {"_id": 1787312400, "w-avg": None}},
        # station hors BBOX de collect.py (BBOX lonMax = 11.0)
        {"_id": "holfuy-3", "loc": {"coordinates": [15.0, 45.6]}, "alt": 500,
         "status": "green", "last": {"_id": 1787312400, "w-avg": 5.0}},
    ],
}
try:
    C._get_json_windsmobi = _wm_route(
        {"yvbeach": _WM_REFERENTIEL_YVBEACH, **_wm_extra}, {})
    with tempfile.TemporaryDirectory() as d:
        _cache = pathlib.Path(d) / "windsmobi_stations.json"
        with redirect_stdout(io.StringIO()):
            _wm_stations = C.windsmobi_stations(_cache)
finally:
    C._get_json_windsmobi = _wm_get_avant

verifie({s["id"] for s in _wm_stations} == {"yvbeach-yvbeach"},
        f"masquée, sans vent et hors BBOX écartées, seule la vraie balise reste — {_wm_stations}")
_wm_st = _wm_stations[0]
verifie(_wm_st["network"] == "yvbeach" and _wm_st["source"] == "windsmobi",
        "réseau d'origine et source archivés sur la ligne du référentiel")
verifie(_wm_st["lat"] == 46.8054 and _wm_st["lon"] == 6.7148,
        f"coordonnées reprises de `loc.coordinates` (lon, lat), arrondies — {_wm_st}")
verifie(_wm_st["elev"] == 430, "altitude reprise du champ `alt`")

# ── 10.2 l'historique : tri croissant, aucune pression, cadence nocturne
try:
    C._get_json_windsmobi = _wm_route({}, {"yvbeach-yvbeach": _WM_HISTORIC_YVBEACH})
    with redirect_stdout(io.StringIO()):
        _wm_rows = list(C.windsmobi_rows(_wm_stations, "2026-08-21"))
finally:
    C._get_json_windsmobi = _wm_get_avant

verifie(len(_wm_rows) == 1, f"une balise, une ligne — {_wm_rows}")
_wr = _wm_rows[0]
verifie(_wr["t"] == sorted(_wr["t"]),
        f"winds.mobi rend le plus récent en premier — l'archive doit être croissante — {_wr['t']}")
verifie(_wr["t"][0] == 1787308800 and _wr["t"][-1] == 1787312400,
        f"les neuf points de la réponse réelle sont tous conservés — {_wr['t']}")
verifie(_wr["speed"] == [5.7, 5.9, 6.8, 6.7, 6.1, 6.1, 4.8, 4.1, 7.6],
        f"`w-avg` devient `speed`, réordonné avec `t` — {_wr['speed']}")
verifie(_wr["gust"] == [8.0, 8.0, 9.7, 9.7, 9.7, 9.7, 9.7, 9.7, 11.3],
        f"`w-max` devient `gust` — {_wr['gust']}")
verifie(_wr["dir"][0] == 247 and _wr["dir"][-1] == 253,
        f"`w-dir` devient `dir`, dans le même ordre que `t` — {_wr['dir']}")
verifie("pres_hpa" not in _wr and "pres_kind" not in _wr,
        "AUCUNE pression, jamais — le champ est OMIS, pas mis à None en boucle "
        "(mesuré au cadrage : les 16 réseaux windsmobi ne disent pas leur "
        "convention de réduction)")
verifie(_wr.get("elev") == 430 and _wr.get("network") == "yvbeach",
        "altitude et réseau d'origine reportés sur la ligne d'observation")

# ⚠️ La fenêtre nocturne filtre par JOURNÉE CIVILE, pas seulement par
# `WINDSMOBI_HISTORY_DURATION_S` : demander la même réponse réelle pour
# la VEILLE (2026-08-20) doit la vider entièrement, puisque les neuf
# points tombent tous le 21.
try:
    C._get_json_windsmobi = _wm_route({}, {"yvbeach-yvbeach": _WM_HISTORIC_YVBEACH})
    with redirect_stdout(io.StringIO()):
        _wm_rows_veille = list(C.windsmobi_rows(_wm_stations, "2026-08-20"))
finally:
    C._get_json_windsmobi = _wm_get_avant
verifie(_wm_rows_veille == [],
        "les points du 21 n'entrent pas dans l'archive du 20 — fenêtre glissante, "
        "pas un simple 'garder ce qu'on reçoit'")

# ⚠️ Un échec réseau sur UNE balise ne doit ni lever, ni polluer les
# autres — même filet que pour `fetch_forecast`/`fetch_archive`.
try:
    C._get_json_windsmobi = _wm_route(
        {}, {"yvbeach-yvbeach": _WM_HISTORIC_YVBEACH}, echecs_historic={"yvbeach-yvbeach"})
    with redirect_stdout(io.StringIO()):
        _wm_rows_echec = list(C.windsmobi_rows(_wm_stations, "2026-08-21"))
finally:
    C._get_json_windsmobi = _wm_get_avant
verifie(_wm_rows_echec == [],
        "une balise dont l'appel historique échoue est simplement absente de "
        "l'archive du jour — jamais une exception qui ferait tomber le run")

verifie(list(C.windsmobi_rows([], "2026-08-21")) == [],
        "référentiel windsmobi vide → aucune requête, aucune ligne")

verifie(C.WINDSMOBI_HISTORY_DURATION_S < 604800,
        "la durée par appel n'est plus les 7 jours pleins de la version "
        "hebdomadaire d'origine — cf. le commentaire de la constante")
verifie("windsmobi" not in {"pioupiou"},  # garde-fou trivial, documente l'intention
        "score.py ne doit JAMAIS tester `source == 'windsmobi'` — cf. all_obs_rows")


# ── 11. INFOCLIMAT : référentiel geojson, history.json, journée civile
# ⚠️ FIXTURES RÉELLES, capturées en direct le 21/08/2026 (deux stations
# du GeoJSON public data.gouv.fr + leurs quatre derniers points de
# `infoclimat/history.json`, notre propre objet R2 public) — même
# discipline que le §10 windsmobi. Les entrées synthétiques (hors BBOX,
# METEO-FRANCE, station hors référentiel, vent tout-None) couvrent les
# filtres que l'échantillon réel, à lui seul, ne traverse pas.
_IC_GEOJSON = {
    "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-0.96, 46.15]},
         "properties": {"id": "00001", "name": "Saint-Médard-d'Aunis", "elevation": 20,
                        "license": {"code": 1, "license": "CC BY",
                                    "url": "https://creativecommons.org/licenses/by/2.0/fr/",
                                    "source": "infoclimat.fr"}}},
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [6.17, 43.34]},
         "properties": {"id": "00003", "name": "Besse sur Issole", "elevation": 275,
                        "license": {"code": 2, "license": "NON-COMMERCIAL ONLY: CC BY NC",
                                    "url": "https://creativecommons.org/licenses/by-nc/2.0/fr/",
                                    "source": "infoclimat.fr"}}},
        # dans le référentiel, mais son vent du 21/08 sera tout-None.
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [3.0, 47.0]},
         "properties": {"id": "00005", "name": "Silencieuse", "elevation": 150,
                        "license": {"code": 1, "license": "CC BY", "url": "https://x",
                                    "source": "infoclimat.fr"}}},
        # hors BBOX de collect.py (BBOX lonMax = 11.0) — doit être écarté.
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [20.0, 45.0]},
         "properties": {"id": "99999", "name": "Hors BBOX", "elevation": 100,
                        "license": {"code": 1, "license": "CC BY", "url": "https://x",
                                    "source": "infoclimat.fr"}}},
        # une entrée MÉTÉO-FRANCE du même GeoJSON : jamais notre `mf`.
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [2.0, 46.0]},
         "properties": {"id": "07510", "name": "MF quelque part", "elevation": 50,
                        "license": {"source": "meteofrance"}}},
    ]
}
_IC_HISTORY = {
    "genere_le": "2026-08-21T16:05:35+00:00", "heures": 30,
    "historique": {
        "00001": {"t": [1787320200, 1787320800, 1787321400, 1787322000],
                  "moy": [25.8, 27.1, 26.1, 26.5],
                  "raf": [44.1, 44.1, 44.1, 44.1],
                  "dir": [251, 253, 251, 251],
                  "pres": [1014.9, 1014.9, 1014.7, 1014.7],
                  "temp": [24.6, 24.3, 24.2, 24.2]},
        "00003": {"t": [1787322000, 1787322600, 1787323200, 1787323800],
                  "moy": [20.9, 19.3, 20.9, 17.7],
                  "dir": [287, 307, 306, 263],
                  "pres": [1009.1, 1009.2, 1009.2, 1009.2],
                  "temp": [28.3, 28.2, 28.4, 28.5]},
        # dans le référentiel, mais aucune mesure de vent ce jour-là.
        "00005": {"t": [1787320200, 1787320800], "moy": [None, None],
                  "dir": [10, 12]},
        # dans l'historique, mais HORS référentiel (BBOX/GeoJSON) —
        # jamais dans l'archive, sans lever.
        "88888": {"t": [1787320200], "moy": [10.0]},
    },
}

_ic_get_avant = C._get_json_infoclimat


def _ic_route(par_url):
    def _fake(url, timeout=60):
        if url not in par_url:
            raise AssertionError(f"URL infoclimat inattendue dans le test : {url}")
        return par_url[url]
    return _fake


# ── 11.1 le référentiel : BBOX, licence par station, METEO-FRANCE écarté
try:
    C._get_json_infoclimat = _ic_route({C.INFOCLIMAT_STATIONS_GEOJSON: _IC_GEOJSON})
    with tempfile.TemporaryDirectory() as d:
        _ic_cache = pathlib.Path(d) / "infoclimat_stations.json"
        with redirect_stdout(io.StringIO()):
            _ic_stations = C.infoclimat_stations(_ic_cache)
finally:
    C._get_json_infoclimat = _ic_get_avant

verifie({s["id"] for s in _ic_stations} == {"00001", "00003", "00005"},
        f"hors BBOX et MÉTÉO-FRANCE écartés, les trois stations StatIC restent — {_ic_stations}")
_ic_st1 = next(s for s in _ic_stations if s["id"] == "00001")
verifie(_ic_st1["lat"] == 46.15 and _ic_st1["lon"] == -0.96,
        f"coordonnées reprises de `geometry.coordinates` (lon, lat) — {_ic_st1}")
verifie(_ic_st1["elev"] == 20 and _ic_st1["licence_code"] == 1,
        f"altitude et licence reprises du GeoJSON — {_ic_st1}")
verifie(next(s for s in _ic_stations if s["id"] == "00003")["licence_code"] == 2,
        "la licence varie par station (CC BY-NC ici, CC BY pour 00001)")

# ── 11.2 le référentiel injoignable : repli sur le cache disque ──────
_ic_cache_json = json.dumps([{"id": "x", "source": "infoclimat", "lat": 1.0,
                              "lon": 1.0, "elev": 1, "licence_code": 1}])
try:
    def _ic_boom(url, timeout=60):
        raise RuntimeError("HTTP 500 (simulé)")
    C._get_json_infoclimat = _ic_boom
    with tempfile.TemporaryDirectory() as d:
        _ic_cache2 = pathlib.Path(d) / "infoclimat_stations.json"
        _ic_cache2.write_text(_ic_cache_json, encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            _ic_fallback = C.infoclimat_stations(_ic_cache2)
finally:
    C._get_json_infoclimat = _ic_get_avant
verifie(_ic_fallback and _ic_fallback[0]["id"] == "x",
        "data.gouv.fr injoignable → repli sur le cache disque, comme metar/windsmobi")

# ── 11.3 les lignes : gust TOUJOURS présent, pres_kind constant, licence
try:
    C._get_json_infoclimat = _ic_route({C.INFOCLIMAT_HISTORY_URL: _IC_HISTORY})
    with redirect_stdout(io.StringIO()):
        _ic_rows = list(C.infoclimat_rows(_ic_stations, "2026-08-21"))
finally:
    C._get_json_infoclimat = _ic_get_avant

verifie({r["station_id"] for r in _ic_rows} == {"00001", "00003"},
        f"00005 (vent tout-None) et 88888 (hors référentiel) n'entrent pas — {_ic_rows}")
_ic_r1 = next(r for r in _ic_rows if r["station_id"] == "00001")
verifie(_ic_r1["gust"] == [44.1, 44.1, 44.1, 44.1],
        f"`raf` devient `gust`, présent sur cette station — {_ic_r1['gust']}")
verifie(_ic_r1["pres_hpa"] == [1014.9, 1014.9, 1014.7, 1014.7],
        f"`pres` devient `pres_hpa`, la mesure BRUTE, jamais convertie — {_ic_r1['pres_hpa']}")
verifie(_ic_r1["pres_kind"] == "qff", "pres_kind constant — mesuré au cadrage (§1.5)")
verifie(_ic_r1["licence_code"] == 1, "licence reportée depuis le référentiel")
verifie(_ic_r1["elev"] == 20 and _ic_r1["lat"] == 46.15,
        "position/altitude viennent du référentiel — history.json ne les porte pas")
verifie("temp" not in _ic_r1,
        "`temp` n'est pas dans le schéma d'archive (décision 1 du cadrage) — jamais recopié")

_ic_r3 = next(r for r in _ic_rows if r["station_id"] == "00003")
verifie(_ic_r3["gust"] == [None, None, None, None],
        f"pas de `raf` chez cette station — `gust` reste TOUJOURS présent, rempli de None, "
        f"jamais omis (mesuré : ~4 % du parc seulement publie une rafale) — {_ic_r3['gust']}")

# ── 11.4 journée civile UTC : les points du 21 n'entrent pas dans le 20
try:
    C._get_json_infoclimat = _ic_route({C.INFOCLIMAT_HISTORY_URL: _IC_HISTORY})
    with redirect_stdout(io.StringIO()):
        _ic_rows_veille = list(C.infoclimat_rows(_ic_stations, "2026-08-20"))
finally:
    C._get_json_infoclimat = _ic_get_avant
verifie(_ic_rows_veille == [],
        "les points du 21 n'entrent pas dans l'archive du 20 — filtre par journée civile UTC, "
        "pas un simple 'garder ce qu'on reçoit'")

verifie(list(C.infoclimat_rows([], "2026-08-21")) == [],
        "référentiel infoclimat vide → aucune requête, aucune ligne")

verifie(C.INFOCLIMAT_HISTORY_URL.endswith("/infoclimat/history.json")
        and "r2.dev" in C.INFOCLIMAT_HISTORY_URL,
        "lecture par l'URL PUBLIQUE r2.dev, la même qu'index.js — pas par tools/storage.py "
        "(qui subirait le R2_BUCKET=model-verif forcé par run.sh)")


# ── 12. MF (S0.2, session 3) ──────────────────────────────────────────
# ⚠️ FIXTURES RÉELLES, capturées en direct le 21/08/2026 depuis NOTRE
# PROPRE infrastructure publique (aucun identifiant nécessaire, ni pour
# `/meteofrance-stations` ni pour `mf_station_history` — sa policy RLS
# est `for select using (true)`, cf. supabase_step13) :
#   - `01014002` (ARBENT) — une vraie station AVEC vent, 6 points réels
#     du 21/08 (00h07-00h29 UTC) ;
#   - `66148001` (CAP BEAR) — LA station que le cadrage nommait déjà
#     comme l'exemple mesuré de pression-seule (§8 de la note de
#     cadrage) : 6 points réels du 21/08, `moy` strictement `None` sur
#     TOUTE la fenêtre de rétention (121 lignes vérifiées en direct,
#     0 avec du vent) — la confirmation en base de ce que le cadrage
#     avait mesuré côté serveur.
# Les entrées synthétiques (coordonnées absentes) couvrent un filtre
# que l'échantillon réel, à lui seul, ne traverse pas — même discipline
# que les §10/§11 windsmobi/infoclimat.
_MF_STATIONS_DOC = {
    "stations": [
        {"id": "01014002", "nom": "ARBENT", "lat": 46.278167, "lon": 5.669, "alt": 534,
         "dd": 300, "ff": 10.44, "raf10": 25.56, "ddraf10": 300,
         "pres": None, "pmer": None, "validityTime": "2026-08-21T16:42:00Z"},
        {"id": "66148001", "nom": "CAP BEAR", "lat": 42.516167, "lon": 3.133667, "alt": 72,
         "dd": None, "ff": None, "raf10": None, "ddraf10": None,
         "pres": 1004.5, "pmer": 1014.4, "validityTime": "2026-08-21T16:42:00Z"},
        # réelle, mais hors BBOX de collect.py (BBOX lonMin = -6.0) — Guadeloupe.
        {"id": "97101015", "nom": "LE RAIZET AERO", "lat": 16.264, "lon": -61.516333, "alt": 11,
         "dd": 100, "ff": 20.16, "raf10": 29.16, "ddraf10": 100,
         "pres": 1015.3, "pmer": 1016.2, "validityTime": "2026-08-21T16:42:00Z"},
        # synthétique : coordonnées absentes (forme dégradée jamais observée en
        # direct, mais que mfStationsPayload ne garantit pas d'exclure elle-même).
        {"id": "00000000", "nom": "Sans coordonnées", "lat": None, "lon": None, "alt": None,
         "dd": None, "ff": None, "raf10": None, "ddraf10": None,
         "pres": None, "pmer": None, "validityTime": None},
    ],
    "fetchedAt": 1787331507332,
}

# `t` en epoch MILLISECONDES (convention `mf_station_history`, PAS celle
# de l'archive) — journée civile UTC du 2026-08-21 : [1787270400000,
# 1787356800000). Les 6 points d'ARBENT capturés tombent tous dans la
# première demi-heure de cette fenêtre (00h07-00h29 UTC) ; ceux de CAP
# BEAR vers 05h05-05h35 UTC. `01034004` : une troisième station réelle,
# présente dans la même réponse Supabase, jamais ajoutée au référentiel
# ci-dessus — sert à couvrir « en historique mais hors référentiel ».
_MF_JOUR = "2026-08-21"
_MF_DEBUT_MS, _MF_FIN_MS = 1787270400000, 1787356800000
_MF_HISTORY_ROWS = [
    {"station_id": "01014002", "t": 1787270850904, "moy": 2.88, "raf": 7.2, "dir": 150, "pressure": None},
    {"station_id": "01014002", "t": 1787271109099, "moy": 3.6, "raf": 7.2, "dir": 100, "pressure": None},
    {"station_id": "01014002", "t": 1787271706960, "moy": 2.16, "raf": 6.12, "dir": 70, "pressure": None},
    {"station_id": "01014002", "t": 1787272007003, "moy": 1.8, "raf": 3.96, "dir": 350, "pressure": None},
    {"station_id": "01014002", "t": 1787272307097, "moy": 2.16, "raf": 4.68, "dir": 340, "pressure": None},
    {"station_id": "01014002", "t": 1787273368680, "moy": 1.8, "raf": 5.04, "dir": 70, "pressure": None},
    {"station_id": "66148001", "t": 1787288756035, "moy": None, "raf": None, "dir": None, "pressure": 1009.5},
    {"station_id": "66148001", "t": 1787289116150, "moy": None, "raf": None, "dir": None, "pressure": 1009.6},
    {"station_id": "66148001", "t": 1787289476936, "moy": None, "raf": None, "dir": None, "pressure": 1009.7},
    {"station_id": "66148001", "t": 1787289838143, "moy": None, "raf": None, "dir": None, "pressure": 1009.8},
    {"station_id": "66148001", "t": 1787290197641, "moy": None, "raf": None, "dir": None, "pressure": 1009.9},
    {"station_id": "66148001", "t": 1787290557244, "moy": None, "raf": None, "dir": None, "pressure": 1009.9},
    # hors référentiel (pas dans _MF_STATIONS_DOC) — doit être ignorée sans lever.
    {"station_id": "01034004", "t": 1787270850904, "moy": 5.04, "raf": 10.44, "dir": 310, "pressure": None},
]

_mf_get_avant = C._get_json_mf
_mf_select_avant = C._mf_history_select
_mf_select_appels: list[tuple[int, int]] = []


def _mf_select_fake(debut_ms, fin_ms):
    _mf_select_appels.append((debut_ms, fin_ms))
    return _MF_HISTORY_ROWS


# ── 12.1 le référentiel : BBOX, coordonnées absentes, source="mf" ────
try:
    def _mf_route(url, timeout=45):
        if url != C.MF_STATIONS_URL:
            raise AssertionError(f"URL MF inattendue dans le test : {url}")
        return _MF_STATIONS_DOC
    C._get_json_mf = _mf_route
    with tempfile.TemporaryDirectory() as d:
        _mf_cache = pathlib.Path(d) / "mf_stations.json"
        with redirect_stdout(io.StringIO()):
            _mf_stations = C.mf_stations(_mf_cache)
finally:
    C._get_json_mf = _mf_get_avant

verifie({s["id"] for s in _mf_stations} == {"01014002", "66148001"},
        f"hors BBOX (Guadeloupe) et coordonnées absentes écartés — {_mf_stations}")
_mf_arbent = next(s for s in _mf_stations if s["id"] == "01014002")
verifie(_mf_arbent["source"] == "mf" and _mf_arbent["lat"] == 46.2782 and _mf_arbent["elev"] == 534,
        f"source='mf', coordonnées et altitude reprises de notre route — {_mf_arbent}")

# ── 12.2 le référentiel injoignable : repli sur le cache disque ──────
_mf_cache_json = json.dumps([{"id": "x", "source": "mf", "lat": 1.0, "lon": 1.0, "elev": 1}])
try:
    def _mf_boom(url, timeout=45):
        raise RuntimeError("HTTP 500 (simulé)")
    C._get_json_mf = _mf_boom
    with tempfile.TemporaryDirectory() as d:
        _mf_cache2 = pathlib.Path(d) / "mf_stations.json"
        _mf_cache2.write_text(_mf_cache_json, encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            _mf_fallback = C.mf_stations(_mf_cache2)
finally:
    C._get_json_mf = _mf_get_avant
verifie(_mf_fallback and _mf_fallback[0]["id"] == "x",
        "notre serveur injoignable → repli sur le cache disque, comme metar/windsmobi/infoclimat")

# ── 12.3 les lignes : ms → s, pression-seule ÉCARTÉE, hors référentiel ignoré
try:
    C._mf_history_select = _mf_select_fake
    _mf_stats: dict = {}
    with redirect_stdout(io.StringIO()):
        _mf_rows = list(C.mf_rows(_mf_stations, _MF_JOUR, _mf_stats))
finally:
    C._mf_history_select = _mf_select_avant

verifie(_mf_select_appels == [(_MF_DEBUT_MS, _MF_FIN_MS)],
        f"bornes ms passées à `_mf_history_select` pour le {_MF_JOUR} — {_mf_select_appels}")
verifie({r["station_id"] for r in _mf_rows} == {"01014002"},
        f"CAP BEAR (pression-seule, moy toujours None) écartée, 01034004 (hors "
        f"référentiel) ignorée — {[r['station_id'] for r in _mf_rows]}")
_mf_r1 = next(r for r in _mf_rows if r["station_id"] == "01014002")
verifie(_mf_r1["t"][0] == 1787270850904 // 1000,
        f"`t` converti de MILLISECONDES en SECONDES — {_mf_r1['t'][0]}")
verifie(_mf_r1["speed"] == [2.88, 3.6, 2.16, 1.8, 2.16, 1.8],
        f"`moy` devient `speed`, dans l'ordre — {_mf_r1['speed']}")
verifie(_mf_r1["gust"][0] == 7.2 and _mf_r1["dir"][0] == 150,
        f"`raf` devient `gust`, `dir` inchangé — {_mf_r1}")
verifie(_mf_r1["pres_hpa"] == [None] * 6,
        f"pas de pression chez cette station — colonne présente, remplie de None — {_mf_r1['pres_hpa']}")
verifie(_mf_r1["pres_kind"] == "qff", "pres_kind constant — mesuré au cadrage (§1.5)")
verifie(_mf_r1["lat"] == 46.2782 and _mf_r1["elev"] == 534,
        "position/altitude viennent du référentiel — mf_station_history ne les porte pas")
verifie(_mf_stats.get("pression_seule_ecartees") == 1,
        f"UNE station écartée (CAP BEAR) — {_mf_stats}")
verifie(_mf_stats.get("stations_avec_donnees") == 2,
        f"deux stations avaient des lignes ce jour-là (ARBENT + CAP BEAR) — {_mf_stats}")

verifie(list(C.mf_rows([], _MF_JOUR)) == [],
        "référentiel mf vide → aucune requête, aucune ligne")

verifie(C.MF_STATIONS_URL.endswith("/meteofrance-stations")
        and "balise-watch-server" in C.MF_STATIONS_URL,
        "lecture par NOTRE propre route publique — jamais public-api.meteofrance.fr")


# ── 13. AEMET (S0.2, session 4 — le dernier du sous-lot) ──────────────
# ⚠️ FIXTURES RÉELLES, capturées en direct le 21/08/2026 depuis NOTRE
# PROPRE infrastructure publique (aucun identifiant nécessaire, ni pour
# `/aemet-stations` ni pour `aemet_station_history`, RLS publique en
# lecture comme MF) :
#   - `0016A` (REUS AEROPUERTO) — vraie station AVEC vent ET pression,
#     6 points réels du 21/08 (12h-17h UTC) ;
#   - `0009X` (ALFORJA) — vraie station AVEC vent, SANS pression (`pmer`
#     toujours `None`), 6 points réels du 21/08 ;
#   - `0002I` (VANDELLÓS) — réelle, et **hors BBOX de justesse** :
#     lat 40.95806 < BBOX latMin 41.0 (un near-miss réel, pas un cas
#     lointain comme la Guadeloupe côté MF) ;
#   - `4362X` (RETAMAL DE LLERENA) — réelle, présente dans l'historique,
#     jamais ajoutée au référentiel ci-dessous : couvre « en historique
#     mais hors référentiel », même rôle que `01034004` côté MF.
# Contrairement à MF, AUCUNE station pression-seule n'a été mesurée en
# direct cette session (0/756 sur 24h glissantes, cf. l'en-tête de
# section de `collect.py`) : `9999P` est donc SYNTHÉTIQUE, seule entrée
# de ce fichier à ne pas venir d'une réponse réelle — elle couvre le
# même filet de sécurité que CAP BEAR côté MF, jamais traversé en
# pratique ici.
_AEMET_STATIONS_DOC = {
    "stations": [
        {"id": "0016A", "nom": "REUS  AEROPUERTO", "lat": 41.145, "lon": 1.163611, "alt": 71,
         "dd": 100, "ff": 22.32, "raf10": 35.28, "ddraf10": 100,
         "pres": None, "pmer": 1012.4, "validityTime": "2026-08-21T17:00:00.000Z"},
        {"id": "0009X", "nom": "ALFORJA", "lat": 41.213892, "lon": 0.963335, "alt": 406,
         "dd": 282, "ff": 15.120000000000001, "raf10": 39.96, "ddraf10": 275,
         "pres": None, "pmer": None, "validityTime": "2026-08-21T16:00:00.000Z"},
        # réelle, mais hors BBOX de collect.py (BBOX latMin = 41.0) — un
        # near-miss réel à 40.958, pas un cas lointain.
        {"id": "0002I", "nom": "VANDELLÓS", "lat": 40.95806, "lon": 0.871385, "alt": 32,
         "dd": 327, "ff": 7.5600000000000005, "raf10": 19.44, "ddraf10": 306,
         "pres": None, "pmer": 1011.9, "validityTime": "2026-08-21T17:00:00.000Z"},
        # synthétique : station pression-seule — cf. en-tête de §13,
        # aucune ne traverse ce filtre en réalité cette session.
        {"id": "9999P", "nom": "Pression seule (synthétique)", "lat": 42.0, "lon": 1.5, "alt": 1200,
         "dd": None, "ff": None, "raf10": None, "ddraf10": None,
         "pres": None, "pmer": 1015.0, "validityTime": "2026-08-21T17:00:00.000Z"},
        # synthétique : coordonnées absentes (forme dégradée jamais
        # observée en direct — 0/756 stations sans lat/lon cette
        # session — mais qu'aemetStationsPayload ne garantit pas
        # d'exclure elle-même). Même discipline que le §12 MF.
        {"id": "0000S", "nom": "Sans coordonnées", "lat": None, "lon": None, "alt": None,
         "dd": None, "ff": None, "raf10": None, "ddraf10": None,
         "pres": None, "pmer": None, "validityTime": None},
    ],
    "fetchedAt": 1787333765015,
}

# `t` en epoch MILLISECONDES — vérifié en direct le 21/08 (Supabase réel,
# pas une hypothèse, cf. en-tête de section de `collect.py`) — journée
# civile UTC du 2026-08-21 : [1787270400000, 1787356800000), les mêmes
# bornes que la fixture MF puisque c'est le même jour calendaire.
_AEMET_JOUR = "2026-08-21"
_AEMET_DEBUT_MS, _AEMET_FIN_MS = 1787270400000, 1787356800000
_AEMET_HISTORY_ROWS = [
    {"station_id": "0016A", "t": 1787313600000, "moy": 10.44, "raf": 42.480000000000004, "dir": 150, "pressure": 1012},
    {"station_id": "0016A", "t": 1787317200000, "moy": 11.879999999999999, "raf": 27.720000000000002, "dir": 100, "pressure": 1011.9},
    {"station_id": "0016A", "t": 1787320800000, "moy": 15.48, "raf": 57.6, "dir": 250, "pressure": 1011.3},
    {"station_id": "0016A", "t": 1787324400000, "moy": 20.88, "raf": 38.88, "dir": 270, "pressure": 1011.3},
    {"station_id": "0016A", "t": 1787328000000, "moy": 24.12, "raf": 33.480000000000004, "dir": 100, "pressure": 1011.7},
    {"station_id": "0016A", "t": 1787331600000, "moy": 22.32, "raf": 35.28, "dir": 100, "pressure": 1012.4},
    {"station_id": "0009X", "t": 1787310000000, "moy": 16.2, "raf": 36, "dir": 269, "pressure": None},
    {"station_id": "0009X", "t": 1787313600000, "moy": 20.88, "raf": 37.440000000000005, "dir": 278, "pressure": None},
    {"station_id": "0009X", "t": 1787317200000, "moy": 14.4, "raf": 40.32, "dir": 260, "pressure": None},
    {"station_id": "0009X", "t": 1787320800000, "moy": 16.56, "raf": 33.12, "dir": 267, "pressure": None},
    {"station_id": "0009X", "t": 1787324400000, "moy": 17.28, "raf": 42.84, "dir": 261, "pressure": None},
    {"station_id": "0009X", "t": 1787328000000, "moy": 15.120000000000001, "raf": 39.96, "dir": 282, "pressure": None},
    # synthétique — cf. en-tête de §13 : `moy` toujours None, comme la
    # définition de "9999P" ci-dessus le promet.
    {"station_id": "9999P", "t": 1787328000000, "moy": None, "raf": None, "dir": None, "pressure": 1015.0},
    {"station_id": "9999P", "t": 1787331600000, "moy": None, "raf": None, "dir": None, "pressure": 1015.1},
    # hors référentiel (pas dans _AEMET_STATIONS_DOC) — doit être ignorée sans lever.
    {"station_id": "4362X", "t": 1787328000000, "moy": 11.16, "raf": 21.96, "dir": 227, "pressure": None},
]

_aemet_get_avant = C._get_json_aemet
_aemet_select_avant = C._aemet_history_select
_aemet_select_appels: list[tuple[int, int]] = []


def _aemet_select_fake(debut_ms, fin_ms):
    _aemet_select_appels.append((debut_ms, fin_ms))
    return _AEMET_HISTORY_ROWS


# ── 13.1 le référentiel : BBOX, coordonnées absentes, source="aemet" ──
try:
    def _aemet_route(url, timeout=45):
        if url != C.AEMET_STATIONS_URL:
            raise AssertionError(f"URL AEMET inattendue dans le test : {url}")
        return _AEMET_STATIONS_DOC
    C._get_json_aemet = _aemet_route
    with tempfile.TemporaryDirectory() as d:
        _aemet_cache = pathlib.Path(d) / "aemet_stations.json"
        with redirect_stdout(io.StringIO()):
            _aemet_stations = C.aemet_stations(_aemet_cache)
finally:
    C._get_json_aemet = _aemet_get_avant

verifie({s["id"] for s in _aemet_stations} == {"0016A", "0009X", "9999P"},
        f"hors BBOX (VANDELLÓS, near-miss réel) et coordonnées absentes écartés — {_aemet_stations}")
_aemet_reus = next(s for s in _aemet_stations if s["id"] == "0016A")
verifie(_aemet_reus["source"] == "aemet" and _aemet_reus["lat"] == 41.145 and _aemet_reus["elev"] == 71,
        f"source='aemet', coordonnées et altitude reprises de notre route — {_aemet_reus}")

# ── 13.2 le référentiel injoignable : repli sur le cache disque ──────
_aemet_cache_json = json.dumps([{"id": "x", "source": "aemet", "lat": 1.0, "lon": 1.0, "elev": 1}])
try:
    def _aemet_boom(url, timeout=45):
        raise RuntimeError("HTTP 500 (simulé)")
    C._get_json_aemet = _aemet_boom
    with tempfile.TemporaryDirectory() as d:
        _aemet_cache2 = pathlib.Path(d) / "aemet_stations.json"
        _aemet_cache2.write_text(_aemet_cache_json, encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            _aemet_fallback = C.aemet_stations(_aemet_cache2)
finally:
    C._get_json_aemet = _aemet_get_avant
verifie(_aemet_fallback and _aemet_fallback[0]["id"] == "x",
        "notre serveur injoignable → repli sur le cache disque, comme metar/windsmobi/infoclimat/mf")

# ── 13.3 les lignes : ms → s, pression-seule ÉCARTÉE, hors référentiel ignoré
try:
    C._aemet_history_select = _aemet_select_fake
    _aemet_stats: dict = {}
    with redirect_stdout(io.StringIO()):
        _aemet_rows = list(C.aemet_rows(_aemet_stations, _AEMET_JOUR, _aemet_stats))
finally:
    C._aemet_history_select = _aemet_select_avant

verifie(_aemet_select_appels == [(_AEMET_DEBUT_MS, _AEMET_FIN_MS)],
        f"bornes ms passées à `_aemet_history_select` pour le {_AEMET_JOUR} — {_aemet_select_appels}")
verifie({r["station_id"] for r in _aemet_rows} == {"0016A", "0009X"},
        f"9999P (pression-seule, moy toujours None) écartée, 4362X (hors "
        f"référentiel) ignorée — {[r['station_id'] for r in _aemet_rows]}")
_aemet_r1 = next(r for r in _aemet_rows if r["station_id"] == "0016A")
verifie(_aemet_r1["t"][0] == 1787313600000 // 1000,
        f"`t` converti de MILLISECONDES en SECONDES — {_aemet_r1['t'][0]}")
verifie(_aemet_r1["speed"] == [10.44, 11.879999999999999, 15.48, 20.88, 24.12, 22.32],
        f"`moy` devient `speed`, dans l'ordre — {_aemet_r1['speed']}")
verifie(_aemet_r1["gust"][0] == 42.480000000000004 and _aemet_r1["dir"][0] == 150,
        f"`raf` devient `gust`, `dir` inchangé — {_aemet_r1}")
verifie(_aemet_r1["pres_hpa"] == [1012, 1011.9, 1011.3, 1011.3, 1011.7, 1012.4],
        f"pression présente pour cette station — {_aemet_r1['pres_hpa']}")
_aemet_r2 = next(r for r in _aemet_rows if r["station_id"] == "0009X")
verifie(_aemet_r2["pres_hpa"] == [None] * 6,
        f"pas de pression chez ALFORJA — colonne présente, remplie de None — {_aemet_r2['pres_hpa']}")
verifie(_aemet_r1["pres_kind"] == "qff", "pres_kind constant — mesuré au cadrage (§1.5), pres_nmar")
verifie(_aemet_r1["lat"] == 41.145 and _aemet_r1["elev"] == 71,
        "position/altitude viennent du référentiel — aemet_station_history ne les porte pas")
verifie(_aemet_stats.get("pression_seule_ecartees") == 1,
        f"UNE station écartée (9999P, synthétique) — {_aemet_stats}")
verifie(_aemet_stats.get("stations_avec_donnees") == 3,
        f"trois stations avaient des lignes ce jour-là (0016A + 0009X + 9999P) — {_aemet_stats}")

verifie(list(C.aemet_rows([], _AEMET_JOUR)) == [],
        "référentiel aemet vide → aucune requête, aucune ligne")

verifie(C.AEMET_STATIONS_URL.endswith("/aemet-stations")
        and "balise-watch-server" in C.AEMET_STATIONS_URL,
        "lecture par NOTRE propre route publique — jamais opendata.aemet.es")


# ══════════════════════════════════════════════════════════════════
#  S0.4 (22/08/2026) — LA REQUÊTE D'UN POINT SE DÉCOUPE EN GROUPES
# ══════════════════════════════════════════════════════════════════
#
#  ⚠️ CE QUE CE BLOC DÉFEND, ET CONTRE QUOI.
#
#  Mesuré le 22/08 : la collecte payait 1 051,2 pondérés par nuit — 146
#  points de budget, 22 % du run — pour DEUX variables de 850 hPa
#  demandées aux NEUF modèles alors qu'un seul les archive
#  (`forecast_rows`, `if model == REGIME_REF_MODEL` ; vérifié sur
#  `fcst_2026-08-22.ndjson.gz` : 657 lignes portent `aloft_speed`,
#  toutes en `ecmwf_ifs025`, sur 5 595).
#
#  Le découpage en deux requêtes par point fait tomber le poids de 7,2 à
#  5,8. Ce n'est pas une optimisation de confort : à 7,2, le garde-fou
#  horaire de `quota_projete` refuse de démarrer au 660ᵉ point et le
#  référentiel en comptait 657 ce matin-là, avec un rafraîchissement
#  tous les 7 jours en AJOUT SEUL. À 5,8, il refuse au 819ᵉ.
#
#  Les trois propriétés qu'un banc doit tenir, et qu'une relecture
#  distraite casserait :
#    1. le CONTENU de l'archive ne bouge pas — deux groupes concaténés
#       doivent rendre exactement les lignes d'une requête unique ;
#    2. le garde-fou du suffixe compte les modèles DU GROUPE, pas ceux
#       de `MODELS` — sinon il se tait quand il devrait crier ;
#    3. `aloft_*` n'est jamais écrit à `null` : un champ absent dit la
#       vérité, un champ à `null` ment.

import json as _json                                    # noqa: E402

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "tools"))
import quota_openmeteo as _QM                           # noqa: E402

_G = C.groupes_requete()

verifie(len(_G) == 2, f"deux groupes de requête, pas plus — {len(_G)}")

# ⚠️ Dépliage DÉFENSIF : muter `groupes_requete` pour qu'il rende un
# seul groupe (l'état d'avant le S0.4) doit rendre ce banc ROUGE, pas le
# faire planter sur un `IndexError` — un banc qui explose au lieu
# d'échouer ne dit pas ce qui est cassé.
_g_alt, _v_alt = _G[0]
_g_surf, _v_surf = _G[1] if len(_G) > 1 else ([], [])

verifie(_g_alt == [C.REGIME_REF_MODEL, C.COMPAGNON_ALTITUDE],
        f"le groupe d'altitude porte le modèle de régime ET son compagnon "
        f"mondial, dans cet ordre — {_g_alt}")
verifie(len(_g_alt) == 2,
        "DEUX modèles dans le groupe d'altitude : un seul ferait rendre à "
        "Open-Meteo une réponse sans suffixe, et `forecast_rows` "
        "abandonnerait tous les points (piège du 08/08)")
verifie(sorted(_g_alt + _g_surf) == sorted(C.MODELS),
        "les groupes partitionnent MODELS : aucun modèle perdu, aucun en double")
verifie(not (set(_g_alt) & set(_g_surf)),
        "aucun modèle dans les deux groupes — il serait collecté et facturé deux fois")

verifie(all(v in _v_alt for v in C.ALOFT_VARS),
        f"le groupe d'altitude demande bien le 850 hPa — {_v_alt}")
verifie(not any(v in _v_surf for v in C.ALOFT_VARS),
        f"⭐ le groupe de surface NE demande PAS le 850 hPa — c'est là qu'est "
        f"toute l'économie du lot — {_v_surf}")
verifie(C.REGIME_REF_MODEL in _g_alt,
        "le modèle de régime est dans le groupe qui demande le 850 hPa — "
        "sinon `aloft_*` serait absent de toute l'archive")
verifie(set(_v_alt) == set(C._hourly_vars()),
        "`_hourly_vars()` reste l'union — un lecteur doit pouvoir lire "
        "d'un coup d'œil ce que l'archive peut contenir")

# ── Le poids, mesuré par le seau lui-même et pas recalculé à la main ──
#
# ⚠️ ON NE RECOPIE PAS 5,8. On construit les URL RÉELLES (jamais
# envoyées) et on demande son avis à `quota_openmeteo.poids_url()`, qui
# est l'autorité du projet sur cette arithmétique. Un banc qui recopie
# le chiffre qu'il vérifie ne vérifie rien — c'est la panne du 09/08
# transposée au banc.


def _url_de(groupe, variables):
    import urllib.parse as _up
    return f"{C.FORECAST_API}?" + _up.urlencode({
        "latitude": "45.3193", "longitude": "6.5800",
        "hourly": ",".join(variables), "models": ",".join(groupe),
        "forecast_days": "3", "wind_speed_unit": "kmh",
        "timeformat": "unixtime"})


_p_mesure = sum(_QM.poids_url(_url_de(m, v)) for m, v in _G)
verifie(abs(C.poids_par_point() - _p_mesure) < 1e-9,
        f"`poids_par_point()` est d'accord avec `poids_url` sur les URL "
        f"réellement construites — {C.poids_par_point()} vs {_p_mesure}")

_p_avant = _QM.poids_url(_url_de(C.MODELS, C._hourly_vars()))
verifie(C.poids_par_point() < _p_avant,
        f"le découpage COÛTE MOINS que la requête unique — "
        f"{C.poids_par_point()} < {_p_avant}")
verifie(abs(_p_avant - C.poids_par_point()
            - len(C.ALOFT_VARS) * (len(C.MODELS) - len(_g_alt)) / 10) < 1e-9,
        "l'économie vaut EXACTEMENT les variables d'altitude qu'on ne demande "
        "plus aux modèles qui ne les archivent pas — rien d'autre n'a changé")

# ── Ce que ça déplace sur le garde-fou horaire ────────────────────
_plafond_h = C.QUOTA_HEURE * 0.95
_max_avant = int(_plafond_h // _p_avant)
_max_apres = int(_plafond_h // C.poids_par_point())
verifie(_max_avant == 659,
        f"AVANT : l'heure autorisait {_max_avant} points (mesuré 657 le 22/08, "
        f"soit 2 de marge)")
verifie(_max_apres == 818,
        f"APRÈS : l'heure en autorise {_max_apres} — la marge passe de 2 à 161 points")

# ── Le garde-fou sait encore refuser ──────────────────────────────
#
# ⚠️ UN BANC DOIT SAVOIR ÉCHOUER. Celui-ci vérifie que le seuil n'a pas
# été « rendu tolérant » en passant à deux groupes : il refuse toujours,
# simplement plus loin. Sans cette assertion, quelqu'un pourrait
# supprimer le `raise` et tout le reste du fichier resterait vert.
try:
    C.quota_projete(_max_apres + 1, 3)
    verifie(False, "quota_projete DOIT lever Abort au-delà du plafond horaire")
except C.Abort as _exc:
    verifie("09/08" in str(_exc) and "PARTITIONNER" in str(_exc),
            f"le refus explique la panne qu'il évite ET les issues chiffrées — "
            f"{str(_exc)[:80]}")
try:
    C.quota_projete(_max_apres, 3)
    verifie(True, "quota_projete accepte pile au plafond")
except C.Abort:
    verifie(False, f"quota_projete refuse {_max_apres} points alors qu'ils tiennent")

# ⚠️ Et il refuse toujours pour la RAISON du 09/08 : un modèle ajouté
# sans regarder. On mute `MODELS` plutôt que de raisonner dessus.
_models_avant = C.MODELS
try:
    C.MODELS = C.MODELS + [f"modele_invente_{i}" for i in range(6)]
    try:
        C.quota_projete(657, 3)
        verifie(False, "six modèles ajoutés sans regarder DOIVENT faire refuser "
                       "le run — c'est ce que le seuil de 60 % attrape")
    except C.Abort:
        verifie(True, "six modèles ajoutés sans regarder font refuser le run")
finally:
    C.MODELS = _models_avant

# ⚠️ Et le groupe d'altitude refuse de se construire si son compagnon
# disparaît de MODELS — sans quoi la requête partirait à un seul modèle
# et l'API rendrait une réponse sans suffixe, pour toutes les balises.
_models_avant = C.MODELS
try:
    C.MODELS = [m for m in C.MODELS if m != C.COMPAGNON_ALTITUDE]
    try:
        C.groupes_requete()
        verifie(False, "`groupes_requete` DOIT lever Abort si le compagnon "
                       "mondial sort de MODELS")
    except C.Abort as _exc:
        verifie("suffixe" in str(_exc),
                f"le refus dit POURQUOI (la règle du suffixe) — {str(_exc)[:70]}")
finally:
    C.MODELS = _models_avant


# ══════════════════════════════════════════════════════════════════
#  Le CONTENU de l'archive ne bouge pas — deux groupes = une requête
# ══════════════════════════════════════════════════════════════════

_T0 = 1787270400
_ST = {"id": "42", "source": "pioupiou", "lat": 45.3193, "lon": 6.5800}


def _payload(modeles, variables, sert=None):
    """Une réponse Open-Meteo plausible, suffixée par modèle.

    `sert` limite les modèles qui répondent vraiment (les autres rendent
    une clé présente et pleine de `None` — le piège ERA5 du 06/08).

    ⚠️ Les valeurs sont dérivées du NOM du modèle, jamais de sa position
    dans la liste : sinon les deux formes comparées plus bas (une
    requête de neuf modèles / deux requêtes de deux et sept) ne
    porteraient pas les mêmes chiffres, et le banc « ligne pour ligne »
    testerait son propre échafaudage au lieu du code.
    """
    sert = sert if sert is not None else modeles
    h = {"time": [_T0, _T0 + 3600, _T0 + 7200]}
    for m in modeles:
        vide = m not in sert
        base = float(len(m))
        for v in variables:
            h[f"{v}_{m}"] = ([None] * 3 if vide
                             else [base, base + 1, base + 2])
    return {"hourly": h}


_lignes_1 = list(C.forecast_rows(_ST, _payload(C.MODELS, C._hourly_vars()),
                                 "2026-08-22T03:15:00Z", C.MODELS))
_lignes_2 = []
for _m, _v in _G:
    _lignes_2 += list(C.forecast_rows(_ST, _payload(_m, _v),
                                      "2026-08-22T03:15:00Z", _m))

verifie(len(_lignes_1) == len(C.MODELS) and len(_lignes_2) == len(C.MODELS),
        f"une ligne par modèle servi, dans les deux formes — "
        f"{len(_lignes_1)} et {len(_lignes_2)}")
verifie({r["model"] for r in _lignes_1} == {r["model"] for r in _lignes_2},
        "⭐ les deux groupes réunis couvrent exactement les mêmes modèles "
        "qu'une requête unique")

_par_modele_1 = {r["model"]: r for r in _lignes_1}
_par_modele_2 = {r["model"]: r for r in _lignes_2}
verifie(all(_json.dumps(_par_modele_1[m], sort_keys=True)
            == _json.dumps(_par_modele_2[m], sort_keys=True)
            for m in _par_modele_1),
        "⭐⭐ LIGNE POUR LIGNE, CHAMP POUR CHAMP, l'archive est identique — "
        "le découpage change le nombre de requêtes, jamais le contenu")

verifie(sum(1 for r in _lignes_2 if "aloft_speed" in r) == 1,
        f"UNE seule ligne porte le vent d'altitude — "
        f"{[r['model'] for r in _lignes_2 if 'aloft_speed' in r]}")
verifie(next(r for r in _lignes_2 if "aloft_speed" in r)["model"]
        == C.REGIME_REF_MODEL,
        "et c'est celle du modèle de régime")

# ⚠️ Le champ ne doit JAMAIS sortir à `null`. On simule le cas où le
# modèle de régime serait servi sans son 850 hPa — ce qui arriverait si
# quelqu'un le sortait du groupe d'altitude.
_sans_alt = _payload([C.REGIME_REF_MODEL, C.COMPAGNON_ALTITUDE],
                     C._surface_vars())
_l_sans = list(C.forecast_rows(_ST, _sans_alt, "2026-08-22T03:15:00Z",
                               [C.REGIME_REF_MODEL, C.COMPAGNON_ALTITUDE]))
verifie(len(_l_sans) == 2, f"les deux modèles sortent quand même — {len(_l_sans)}")
verifie(all("aloft_speed" not in r for r in _l_sans),
        "⭐ pas de 850 hPa dans la réponse ⇒ le champ est ABSENT, jamais "
        "`null` : un champ absent dit la vérité, un `null` mentirait")

# ── Le garde-fou du suffixe compte les modèles DU GROUPE ──────────
#
# Réponse sans suffixe = un seul des modèles demandés sert le point.
# Avant le S0.4 le test portait sur `len(MODELS) > 1`, ce qui restait
# vrai par accident ; il porte maintenant sur le groupe.
_nu = {"hourly": {"time": [_T0, _T0 + 3600, _T0 + 7200],
                  "wind_speed_10m": [10.0, 11.0, 12.0],
                  "wind_direction_10m": [180, 190, 200],
                  "wind_gusts_10m": [20.0, 21.0, 22.0]}}
import contextlib as _ctx                               # noqa: E402
_bruit = io.StringIO()
with _ctx.redirect_stderr(_bruit):
    _l_nu = list(C.forecast_rows(_ST, _nu, "x", _g_alt))
verifie(_l_nu == [],
        "⭐ réponse SANS suffixe sur un groupe de 2 modèles ⇒ zéro ligne — "
        "jamais une série attribuée au hasard (piège du 06/08)")
verifie("sans suffixe" in _bruit.getvalue()
        and f"{len(_g_alt)} modèles demandés" in _bruit.getvalue(),
        f"⭐ et ZÉRO LIGNE SE DIT : le garde-fou écrit sur stderr, en nommant "
        f"la balise et la taille du GROUPE. Sans cette assertion, remplacer "
        f"`len(models)` par `len(MODELS)` ne casserait rien de visible — "
        f"{_bruit.getvalue().strip()[:90]}")
verifie(list(C.forecast_rows(_ST, _nu, "x", ["un_seul"])) == [],
        "⛔ ET UN GROUPE À UN SEUL MODÈLE NE PRODUIT RIEN NON PLUS — le "
        "garde-fou ne se déclenche pas (il faut `len(models) > 1`), mais la "
        "boucle cherche `wind_speed_10m_un_seul`, que l'API ne peut pas "
        "écrire quand un seul modèle sert. Zéro ligne, EN SILENCE : c'est "
        "précisément pour ça que `COMPAGNON_ALTITUDE` existe et que le "
        "groupe d'altitude porte deux modèles.")

# ── Un modèle du groupe hors domaine : clé présente, pleine de None ──
_hors = _payload(_g_surf, _v_surf, sert=_g_surf[:2])
_l_hors = list(C.forecast_rows(_ST, _hors, "x", _g_surf))
verifie(len(_l_hors) == 2,
        f"les modèles servant `null` partout sont écartés, pas archivés — "
        f"{len(_l_hors)} lignes sur {len(_g_surf)} modèles demandés")


# ══════════════════════════════════════════════════════════════════
#  ⛔⛔ UN REFUS DE QUOTA NE DOIT PLUS EMPORTER LES OBSERVATIONS
# ══════════════════════════════════════════════════════════════════
#
#  Entrée `BUGS.md` du 22/08 (S0.3 §11.1). `quota_projete` levait
#  `Abort`, `main()` faisait `return 1` AVANT la passe observations : la
#  nuit du dépassement perdait aussi l'archive de vent des cinq réseaux,
#  dont trois n'ont que 30 à 48 h de rétention amont — c'est-à-dire pour
#  toujours. Or AUCUNE de ces passes ne consomme de quota Open-Meteo :
#  `fetch_archive` interroge Pioupiou (`PIOUPIOU_ARCHIVE`), les autres
#  interrogent Iowa State, winds.mobi, Infoclimat, MF et l'AEMET.
#
#  ⚠️ CE BANC SAIT ÉCHOUER : rejoué contre le `return 1`, il tombe sur
#  l'assertion « le fichier d'observations existe ».

_racine = pathlib.Path(tempfile.mkdtemp(prefix="s04-obs-"))
_avant = {n: getattr(C, n) for n in
          ("quota_projete", "load_stations", "fetch_archive", "upload_r2",
           "metar_stations", "windsmobi_stations", "infoclimat_stations",
           "mf_stations", "aemet_stations")}
_argv_avant = sys.argv


def _upload_bidon(path, key):
    C.temoin(path).write_text("ok", encoding="utf-8")
    return True


try:
    # ⚠️ `**kw` DEPUIS LE LOT S0.6 : `quota_projete` prend désormais
    # `groupes=` et `passe=`. Un faux à signature figée se serait mis à
    # lever `TypeError` au lieu d'`Abort`, et le banc aurait cru tester
    # le refus de quota alors qu'il testait sa propre doublure.
    C.quota_projete = lambda n, d, **kw: (_ for _ in ()).throw(
        C.Abort("4900 appels pondérés pour 680 points — banc S0.4"))
    C.load_stations = lambda p, max_age_days=7: [dict(_ST)]
    C.fetch_archive = lambda st, day: {
        "station_id": st["id"], "source": st["source"],
        "lat": st["lat"], "lon": st["lon"],
        "t": [_T0], "speed": [12.0], "gust": [20.0], "dir": [180]}
    C.upload_r2 = _upload_bidon
    for _n in ("metar_stations", "windsmobi_stations", "infoclimat_stations",
               "mf_stations", "aemet_stations"):
        setattr(C, _n, lambda cache: [])
    sys.argv = ["collect.py", "--out", str(_racine), "--obs-day", "2026-08-21"]
    _rc = C.main()
finally:
    for _n, _f in _avant.items():
        setattr(C, _n, _f)
    sys.argv = _argv_avant

_obs = _racine / "obs/2026/08/obs_2026-08-21.ndjson.gz"
_fcst = _racine / "fcst" / f"{C.datetime.now(C.timezone.utc):%Y/%m}"
verifie(_obs.exists(),
        "⭐⭐ le refus de quota N'EMPORTE PLUS les observations : le fichier "
        f"obs du 21/08 existe — {_obs}")
verifie(_obs.exists() and len(gzip.open(_obs, "rt").read().splitlines()) == 1,
        "et il porte bien la ligne de la balise, pas un fichier vide")
verifie(not _fcst.exists() or not any(_fcst.glob("fcst_*.ndjson.gz")),
        "la passe PRÉVISIONS, elle, n'a rien écrit — c'est elle qui débordait")
verifie(_rc == 1,
        f"⭐ et le run sort quand même en ERREUR pour que l'alerte parte "
        f"(run.sh, SEUIL_ALERTE=1) — code {_rc}")


# ══════════════════════════════════════════════════════════════════
#  LOT S0.6 — LA PARTITION EN PASSES HORAIRES
# ══════════════════════════════════════════════════════════════════

# ── 1. Les clés : la partie 1 garde la clé historique ───────────────
#
# ⛔ C'est la propriété qui permet de N'AVOIR AUCUNE DATE DE BASCULE
# dans le code. Si elle tombe, les 15 nuits déjà écrites deviennent
# illisibles sans un `if jour < X` — et un `if` daté est une ligne que
# personne ne relit.
_J = C.datetime(2026, 8, 23, 3, 15, 4, tzinfo=C.timezone.utc)
verifie(C.fcst_cle(_J, 1) == "fcst/2026/08/fcst_2026-08-23.ndjson.gz",
        f"⭐ la partie 1 rend EXACTEMENT la clé d'avant le lot — "
        f"{C.fcst_cle(_J, 1)}")
verifie(C.fcst_cle(_J) == C.fcst_cle(_J, 1),
        "et le défaut est la partie 1")
verifie(C.fcst_cle(_J, 2) == "fcst/2026/08/fcst_2026-08-23_p2.ndjson.gz",
        f"la partie 2 prend `_p2` — {C.fcst_cle(_J, 2)}")
verifie(C.manifeste_cle(_J) == "fcst/2026/08/fcst_2026-08-23.manifeste.json",
        "le manifeste est LATÉRAL — un objet à part, jamais une ligne")
try:
    C.fcst_cle(_J, 0)
    verifie(False, "une partie 0 doit lever, pas rendre une clé muette")
except C.Abort:
    verifie(True, "une partie 0 lève `Abort` plutôt que d'inventer une clé")

# ── 2. Le manifeste est DÉRIVÉ, jamais recopié ─────────────────────
_m = C.construire_manifeste(_J, 657)
_g = C.groupes_requete()
verifie(_m["parties"] == len(_g),
        f"le manifeste déclare autant de parties que `groupes_requete()` "
        f"en rend — {_m['parties']} / {len(_g)}")
verifie(_m["flux"] == "fcst",
        "⭐ il NOMME son flux : `snapshot_rows` en lit trois, un seul est "
        "partitionné")
verifie(abs(_m["poids_point_total"] - C.poids_par_point()) < 1e-9,
        f"son poids par point est celui de `poids_par_point()` — "
        f"{_m['poids_point_total']} / {C.poids_par_point()}")
verifie([d["cle"] for d in _m["detail"]]
        == [C.fcst_cle(_J, i) for i in range(1, len(_g) + 1)],
        "et chaque partie déclare la clé que la passe écrira vraiment")
verifie(_m["detail"][0]["modeles"] == [C.REGIME_REF_MODEL,
                                       C.COMPAGNON_ALTITUDE],
        f"⛔ la PARTIE 1 porte le modèle de régime — c'est elle qui garde "
        f"l'heure de 03:15, donc `{C.REGIME_REF_MODEL}` ne subit aucune "
        f"discontinuité de fraîcheur de run")

# ── 3. ⭐ L'ATTENTE BORNÉE — la passe DEMANDE, elle ne suppose pas ──
#
# ⛔ C'est le point que le S0.4 signale et ne résout pas : une passe 2
# lancée pendant que la passe 1 déborde encore se ferait refuser POINT
# PAR POINT (657 refus) là où UNE attente de douze minutes ramène toute
# la donnée.

class _BudgetFactice:
    def __init__(self, attente):
        self.attente = attente
        self.demande = []

    def attente_fenetre(self, poids, fenetre="heure"):
        self.demande.append((poids, fenetre))
        return self.attente


_dodos = []
_b = _BudgetFactice(0.0)
verifie(C.attendre_la_place(_b, 2759.4, 2, _dodos.append) == 0.0
        and not _dodos,
        "place libre : on ne dort pas, et on ne le dit pas non plus")
verifie(_b.demande == [(2759.4, "heure")],
        "⭐ et c'est bien la fenêtre HORAIRE qu'on interroge, pas la minute "
        "— la minute ne peut JAMAIS contenir le poids d'une passe entière, "
        "elle rendrait `inf` pour une question qui a une réponse")

_dodos = []
_att = C.attendre_la_place(_BudgetFactice(720.0), 2759.4, 2, _dodos.append)
verifie(_att == 720.0 and _dodos == [720.0],
        f"⭐⭐ UNE SEULE attente, de la durée EXACTE que le budget calcule "
        f"— {_dodos} (et non 657 refus)")

try:
    C.attendre_la_place(_BudgetFactice(C.ATTENTE_PASSE_MAX_S + 1), 2759.4, 2,
                        _dodos.append)
    verifie(False, "au-delà de la borne, la passe doit être SAUTÉE, pas dormir")
except C.Abort as _e:
    verifie("borne" in str(_e) and "passe 2" in str(_e),
            "au-delà de la borne : refus ARGUMENTÉ, qui nomme la passe et "
            "la borne — un trou déclaré, pas un run tué par le chien de garde")

try:
    C.attendre_la_place(_BudgetFactice(float("inf")), 99999.0, 2, _dodos.append)
    verifie(False, "un poids qui ne tient jamais doit lever")
except C.Abort as _e:
    verifie("volume" in str(_e),
            "⛔ et un poids qui ne tient JAMAIS dans une heure dit que c'est "
            "un VOLUME : il faut une passe de plus, pas une minute de plus")

verifie(C.attendre_la_place(None, 2759.4, 2, _dodos.append) == 0.0,
        "sans module de budget (mode dégradé), on part — un garde-fou qui "
        "empêche de tourner est pire que le risque qu'il couvre")

# ── 4. ⭐ LE SEUIL JOURNALIER JUGE LA SOMME DES PASSES ──────────────
#
# ⛔ Le mutant M7 du S0.4 (« le seuil journalier ne refuse rien ») était
# ÉQUIVALENT parce qu'une seule passe franchissait toujours l'heure
# avant la journée. Avec deux passes, ce n'est plus vrai — et c'est ici
# que ça se vérifie.
_alt, _surf = C.groupes_requete()
_pp_surf = len(_surf[0]) * len(_surf[1]) / 10          # 4,2 au 22/08
_pp_jour = C.poids_par_point()                        # 5,8 au 22/08
# Un nombre de points où la passe de SURFACE passe l'heure (< 4 750)
# mais où les DEUX passes réunies franchissent 60 % du jour (> 6 000).
_n = int(C.QUOTA_JOUR * 0.6 / _pp_jour) + 20
verifie(_n * _pp_surf < C.QUOTA_HEURE * 0.95,
        f"⚠️ le banc est bien dans le cas visé : {_n} points × {_pp_surf} = "
        f"{_n * _pp_surf:.0f} pondérés, sous les 4 750 de l'heure")
try:
    C.quota_projete(_n, 3, groupes=[_surf], passe=2)
    verifie(False, "⛔ le seuil JOURNALIER doit refuser la somme des passes")
except C.Abort as _e:
    verifie("JOURNÉE" in str(_e) and "SOMME" in str(_e),
            f"⭐⭐ le seuil journalier juge la SOMME des passes, pas celle "
            f"qui part — sans quoi deux passes de 4 700 passeraient l'heure "
            f"chacune et feraient 9 400 dans la journée")
_n_ok = int(C.QUOTA_JOUR * 0.6 / _pp_jour) - 20
_v = C.quota_projete(_n_ok, 3, groupes=[_surf], passe=2)
verifie(abs(_v - _n_ok * _pp_surf) < 1e-6,
        f"et il rend le poids de LA PASSE ({_v:.0f}), pas celui du jour — "
        f"c'est ce chiffre-là que le seau doit réserver")

# ── 4 bis. ⭐⭐ LA MARGE ANNONCE LE GARDE-FOU QUI MORD LE PREMIER ───
#
# ⛔ Dès qu'il y a deux passes, ce n'est plus l'heure qui ferme la porte,
# c'est le JOUR : à 5,80 pondéré/point, le seuil journalier refuse au
# 1 035ᵉ point quand la passe de surface tient l'heure jusqu'au 1 130ᵉ.
# Une ligne « MARGE AVANT REFUS » calculée sur la seule fenêtre horaire
# annoncerait donc 96 points de trop — et on découvrirait la vraie
# limite le matin où elle est franchie. C'est exactement la panne du
# 09/08 : un garde-fou qui annonce l'échéance d'un AUTRE garde-fou.
import io as _io                                          # noqa: E402
import contextlib as _cx                                  # noqa: E402


def _capte(*a, **k):
    _b = _io.StringIO()
    with _cx.redirect_stdout(_b):
        try:
            C.quota_projete(*a, **k)
        except C.Abort:
            pass
    return _b.getvalue()


_pmax_jour = int(C.QUOTA_JOUR * 0.6 // _pp_jour)
_pmax_heure_surf = int(C.QUOTA_HEURE * 0.95 // _pp_surf)
verifie(_pmax_jour < _pmax_heure_surf,
        f"⚠️ le banc est bien dans le cas visé : le jour plafonne à "
        f"{_pmax_jour} points, l'heure de la passe de surface à "
        f"{_pmax_heure_surf}")
_sortie = _capte(600, 3, groupes=[_surf], passe=2)
verifie("seuil JOURNALIER (60 %)" in _sortie,
        "⭐⭐ partitionné, la marge annonce le seuil JOURNALIER — c'est lui "
        "qui mord le premier, et la ligne le NOMME")
verifie(f"MARGE AVANT REFUS      : {_pmax_jour - 600} points" in _sortie,
        f"⭐ et elle compte jusqu'au bon plafond ({_pmax_jour}), pas "
        f"jusqu'à celui de l'heure ({_pmax_heure_surf})")
_sortie0 = _capte(657, 3)
verifie("fenêtre HORAIRE)" in _sortie0 and "MARGE AVANT REFUS      : 161" in _sortie0,
        "⛔ et SANS partition rien ne change : c'est toujours l'heure qui "
        "mord, et la marge vaut toujours 161 points à 657 points de "
        "référentiel")

# ── 5. ⭐⭐ LE MANIFESTE SURVIT À LA PERTE DES DONNÉES ──────────────
#
# ⛔ C'EST TOUTE LA RAISON D'ÊTRE DE LA FORME « MANIFESTE LATÉRAL ».
# On simule la nuit où la collecte ne ramène RIEN : pas une ligne. La
# déclaration, elle, a été écrite AVANT — donc la notation du lendemain
# saura qu'il manquait quelque chose. Un en-tête de ligne, lui, aurait
# disparu avec le fichier vide.
#
# ⚠️ CE BANC SAIT ÉCHOUER : déplacer l'écriture du manifeste APRÈS
# `write_ndjson_gz` le laisse vert ; la déplacer après le `if n:` ou la
# supprimer fait tomber les deux assertions ci-dessous.
_r2 = pathlib.Path(tempfile.mkdtemp(prefix="s06-manif-"))
_avant2 = {n: getattr(C, n) for n in
           ("load_stations", "fetch_forecast", "upload_r2", "charger_quota",
            "metar_stations", "windsmobi_stations", "infoclimat_stations",
            "mf_stations", "aemet_stations", "fetch_archive")}
_argv2 = sys.argv
try:
    C.load_stations = lambda p, max_age_days=7: [dict(_ST)]
    C.fetch_forecast = lambda *a, **k: None      # la nuit ne ramène RIEN
    C.upload_r2 = _upload_bidon
    C.charger_quota = lambda: None               # pas de seau : pas d'attente
    C.fetch_archive = lambda st, day: None
    for _n2 in ("metar_stations", "windsmobi_stations", "infoclimat_stations",
                "mf_stations", "aemet_stations"):
        setattr(C, _n2, lambda cache: [])
    sys.argv = ["collect.py", "--out", str(_r2), "--passe", "1",
                "--obs-day", "2026-08-21"]
    C.main()
finally:
    for _n2, _f2 in _avant2.items():
        setattr(C, _n2, _f2)
    sys.argv = _argv2

_aujd = C.datetime.now(C.timezone.utc)
_mp = _r2 / C.manifeste_cle(_aujd)
verifie(_mp.exists(),
        f"⭐⭐ le manifeste EXISTE alors que la collecte n'a rien ramené — "
        f"c'est ce qu'aucune des deux autres formes ne sait faire ({_mp})")
if _mp.exists():
    _mj = json.loads(_mp.read_text(encoding="utf-8"))
    verifie(_mj["parties"] == len(C.groupes_requete()),
            f"⭐ et il DÉCLARE {_mj['parties']} parties : la notation du "
            f"lendemain saura qu'il en manque, au lieu de noter la nuit sur "
            f"les modèles qu'elle trouve")
    verifie(_mj["flux"] == "fcst" and "modeles" in _mj["detail"][0],
            "il nomme son flux ET les modèles de chaque partie")

# ── 6. La passe 2 : sa propre clé, pas de manifeste, pas d'obs ──────
_r3 = pathlib.Path(tempfile.mkdtemp(prefix="s06-p2-"))
_argv3 = sys.argv
_vus = []
try:
    C.load_stations = lambda p, max_age_days=7: [dict(_ST)]
    C.fetch_forecast = lambda *a, **k: None
    C.upload_r2 = _upload_bidon
    C.charger_quota = lambda: None
    C.fetch_archive = lambda st, day: _vus.append(day)
    for _n3 in ("metar_stations", "windsmobi_stations", "infoclimat_stations",
                "mf_stations", "aemet_stations"):
        setattr(C, _n3, lambda cache: [])
    sys.argv = ["collect.py", "--out", str(_r3), "--passe", "2",
                "--obs-day", "2026-08-21"]
    C.main()
finally:
    for _n3, _f3 in _avant2.items():
        setattr(C, _n3, _f3)
    sys.argv = _argv3

verifie((_r3 / C.fcst_cle(_aujd, 2)).exists(),
        f"la passe 2 écrit SA clé `_p2` — {C.fcst_cle(_aujd, 2)}")
verifie(not (_r3 / C.fcst_cle(_aujd, 1)).exists(),
        "⛔ et elle ne touche PAS la clé historique — sinon elle écraserait "
        "la partie 1, qui est déjà partie une heure plus tôt")
verifie(not (_r3 / C.manifeste_cle(_aujd)).exists(),
        "⛔⛔ elle N'ÉCRIT PAS le manifeste : une clé R2 s'écrit UNE FOIS, "
        "et un manifeste que la passe 2 compléterait ne dirait plus rien le "
        "jour où c'est la passe 2 qui manque")
verifie(not _vus and not (_r3 / "obs").exists(),
        "⛔ et elle ne collecte AUCUNE observation — couper la passe "
        "observations en deux couperait l'archive Pioupiou en deux fichiers, "
        "pour une passe qui ne consomme aucun quota Open-Meteo")
# ── 7. ⛔ `en_retard()` CONNAÎT LES MANIFESTES ──────────────────────
#
# Un manifeste dont l'envoi R2 échoue et que `rattraper()` ne reprend
# jamais est PIRE qu'un manifeste absent : côté `score.py`, son absence
# sur R2 se lit « journée d'avant la partition », et la nuit est notée
# sur une partie sur deux, en silence. 300 octets qui manquent.
#
# ⚠️ On construit le cas à la main plutôt que de le déduire du run
# ci-dessus : là-bas `_upload_bidon` pose le témoin, donc il n'y a
# JAMAIS de retard et l'assertion serait vraie sans rien prouver.
_r4 = pathlib.Path(tempfile.mkdtemp(prefix="s06-retard-"))
_mk = C.manifeste_cle(_J)
(_r4 / _mk).parent.mkdir(parents=True, exist_ok=True)
(_r4 / _mk).write_text('{"version":1}', encoding="utf-8")
(_r4 / C.fcst_cle(_J, 1)).write_bytes(b"")
_retard = [p.relative_to(_r4).as_posix() for p in C.en_retard(_r4)]
verifie(_mk in _retard,
        f"⛔ un manifeste sans témoin est EN RETARD, donc rattrapable — "
        f"sinon son absence sur R2 se lira « journée d'avant la partition » "
        f"et la nuit sera notée sur une partie sur deux, en silence "
        f"(vu : {_retard})")
verifie(C.fcst_cle(_J, 1) in _retard,
        "et les archives restent rattrapables comme avant")
C.temoin(_r4 / _mk).write_text("ok", encoding="utf-8")
verifie(_mk not in [p.relative_to(_r4).as_posix() for p in C.en_retard(_r4)],
        "un manifeste avec témoin ne repart pas — le témoin marche à "
        "l'identique quel que soit le suffixe")


# ══════════════════════════════════════════════════════════════════
#  LOT S0.9 (23/08/2026) — LE MANIFESTE NE DOIT DÉCLARER QUE CE QU'IL
#  ÉCRIT VRAIMENT
# ══════════════════════════════════════════════════════════════════
#
# ⛔ LE DÉFAUT MESURÉ LE 23/08 À 05:30 UTC : en `--passe 0` (le mode de
# production d'aujourd'hui), `construire_manifeste` recevait TOUJOURS
# `groupes_requete()` — DEUX groupes — pour déclarer les parties, alors
# que CE RUN n'écrit qu'UNE SEULE clé (`partie = args.passe or 1`,
# toujours 1 en `--passe 0`). Le manifeste déclarait 2 parties ; R2 n'en
# a jamais porté qu'une. `score.py::fcst_parties` lisait donc
# « partie 2 MANQUANTE » — sept modèles nommés perdus — sur une nuit qui
# n'avait RIEN perdu, et qui a effectivement écrasé `rank_reason = 'ok'`
# par `'partie_manquante'` (arbitrage n°1 de la note du lot).
#
# ⚠️ LE DISCRIMINANT EST `args.passe`, JAMAIS `len(groupes_requete())` —
# qui vaut TOUJOURS 2, que la nuit soit partitionnée ou non.
#
# ⛔ M1 EST UN BANC DE BOUT EN BOUT, PAS UN TEST UNITAIRE SUR
# `construire_manifeste` SEULE — la leçon du S0.5 (mutation n°5) :
# « un banc qui teste deux gardes à la fois n'en teste qu'une ». Le
# défaut ne se voit qu'en faisant se rencontrer L'ÉCRIVAIN
# (`collect.py::main`, `--passe 0`) et LE LECTEUR
# (`score.py::fcst_parties`) — chacun pris séparément est irréprochable :
# `collect.py` écrit bien ses lignes, `score.py` lit bien le manifeste
# qu'on lui donne.
import score as J                                         # noqa: E402

# ── M1 : bout en bout, `--passe 0` (le mode de production d'aujourd'hui) ──
_r5 = pathlib.Path(tempfile.mkdtemp(prefix="s09-m1-"))
_argv5 = sys.argv
_avant5 = {n: getattr(C, n) for n in
           ("load_stations", "fetch_forecast", "upload_r2", "charger_quota",
            "metar_stations", "windsmobi_stations", "infoclimat_stations",
            "mf_stations", "aemet_stations", "fetch_archive")}
try:
    C.load_stations = lambda p, max_age_days=7: [dict(_ST)]
    C.fetch_forecast = lambda lat, lon, days, modeles, variables: _payload(
        modeles, variables)
    C.upload_r2 = _upload_bidon
    C.charger_quota = lambda: None
    C.fetch_archive = lambda st, day: None
    for _n5 in ("metar_stations", "windsmobi_stations", "infoclimat_stations",
                "mf_stations", "aemet_stations"):
        setattr(C, _n5, lambda cache: [])
    # ⛔ PAS DE `--passe` : c'est `--passe 0`, le défaut, le mode de
    # production d'aujourd'hui — celui qui portait le défaut.
    sys.argv = ["collect.py", "--out", str(_r5), "--obs-day", "2026-08-21"]
    C.main()
finally:
    for _n5, _f5 in _avant5.items():
        setattr(C, _n5, _f5)
    sys.argv = _argv5

_aujd5 = C.datetime.now(C.timezone.utc)
_rows5, _bilan5 = J.fcst_parties(_r5, _aujd5)
verifie(_bilan5.get("etat") == "ok",
        f"⭐⭐ M1 — bout en bout, `--passe 0` : la notation lit `ok`, JAMAIS "
        f"`partie_manquante` sur une nuit qui n'a rien perdu — {_bilan5}")
verifie(_bilan5.get("parties_attendues") == 1,
        f"⭐ et elle attendait 1 SEULE partie — pas les 2 que "
        f"`groupes_requete()` rend toujours, partitionné ou non — {_bilan5}")
verifie(_bilan5.get("manquantes") == [],
        f"rien n'est déclaré manquant — {_bilan5.get('manquantes')}")
verifie(len(_rows5) > 0,
        "et les lignes existent bien : ce n'est pas une perte de données, "
        "seulement une fausse déclaration qui vient d'être corrigée")

# ── M3 : la partie unique doit porter les NEUF modèles ──────────────
#
# ⛔ Piège facile à manquer : le manifeste sert à NOMMER ce qui manque.
# Une partie unique qui ne déclarerait que le groupe d'altitude
# mentirait le jour où la clé historique serait perdue — le journal
# annoncerait « 2 modèles perdus » au lieu de 9.
_mu = C.construire_manifeste(_aujd5, 657, partitionne=False)
verifie(_mu["parties"] == 1,
        f"le manifeste non partitionné déclare 1 SEULE partie — "
        f"{_mu['parties']}")
verifie(_mu["detail"][0]["cle"] == C.fcst_cle(_aujd5, 1),
        "et elle porte la clé HISTORIQUE — celle que ce run écrit vraiment")
verifie(set(_mu["detail"][0]["modeles"]) == set(C.MODELS),
        f"⭐⭐ M3 — la partie unique porte les NEUF modèles, PAS seulement "
        f"ceux d'un groupe — {_mu['detail'][0]['modeles']}")
verifie(_mu["detail"][0]["modeles"] == list(C.MODELS),
        "et dans l'ORDRE de `MODELS` — dérivé, jamais recopié")

# ── M4 : le poids de la partie unique est celui de LA CLÉ RÉELLE ────
#
# ⛔ Les deux groupes n'ont pas le même nombre de variables (8 et 6) : un
# champ scalaire ne peut pas porter les deux. `n_vars` doit rester la
# valeur qui reste vraie (l'union), et `poids_point` doit être celui
# effectivement dépensé pour CETTE clé — tous groupes confondus — pas
# celui d'un seul des deux groupes de la requête.
verifie(_mu["detail"][0]["n_vars"] == len(C._hourly_vars()),
        f"n_vars de la partie unique = l'UNION des variables, "
        f"{len(C._hourly_vars())} — {_mu['detail'][0]['n_vars']}")
verifie(abs(_mu["detail"][0]["poids_point"] - C.poids_par_point()) < 1e-9,
        f"⭐⭐ M4 — poids_point de la partie unique = `poids_par_point()` "
        f"({C.poids_par_point()}), PAS celui d'un seul groupe (1,6 ou 4,2) "
        f"— {_mu['detail'][0]['poids_point']}")
verifie(abs(_mu["poids_point_total"] - C.poids_par_point()) < 1e-9,
        "⚠️ et `poids_point_total` reste `poids_par_point()` dans CE mode "
        "aussi — le banc existant qui compare ce champ (section 2 "
        "ci-dessus) ne doit pas avoir besoin d'être modifié pour rester "
        "vert : s'il fallait le modifier, c'est que la correction serait "
        "fausse")

# ── M2 (rejouée à la main, cf. note de session) ─────────────────────
#
# ⛔ M2 — « le manifeste déclare 1 partie en `--passe 1` » — n'ajoute
# PAS de nouvelle assertion ici : c'est le banc DÉJÀ ÉCRIT à la section
# « 2. Le manifeste est DÉRIVÉ, jamais recopié » (plus haut dans ce
# fichier, et sans une ligne changée) et la section 5 ci-dessus
# (« LE MANIFESTE SURVIT À LA PERTE DES DONNÉES », qui fait tourner
# `--passe 1`) qui doivent rester verts SANS MODIFICATION et rougir si
# `partitionne` était figé à `False`. Rejoué à la main pendant cette
# session (source mutée puis restaurée, cf. note) : les deux tombent
# bien sous cette mutation, et aucune des deux n'a eu besoin d'être
# touchée pour rester verte avec le code corrigé.
verifie(True,
        "ⓘ M2 : voir section 2 et section 5 ci-dessus, rejouées à la main "
        "contre `partitionne=False` figé — cf. note de session pour le "
        "détail du rejeu")


print(f"\n{ok} assertions vertes, {len(ko)} en échec")
for m in ko:
    print(f"  ❌ {m}")
sys.exit(1 if ko else 0)
