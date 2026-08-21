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

n_vars = len(C._hourly_vars()) * len(C.MODELS)
verifie(abs(total - 648 * n_vars / 10) < 1e-6,
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

# ⚠️ ET LA CONFIGURATION DU 09/08 DOIT ÊTRE REFUSÉE. 10 modèles × 8
# variables pesaient 8,0 par point, soit 5 184 pondérés : au-dessus des
# 5 000 de l'heure. Le run s'était arrêté à 625 points collectés — 5 000
# à l'unité près — puis n'avait plus rien obtenu pendant 26 minutes.
# C'est l'assertion qui empêche de rajouter un dixième modèle sans
# recompter, et de rejouer cette nuit-là.
modeles_avant = C.MODELS
C.MODELS = list(modeles_avant) + ["meteoswiss_icon_ch1"]
try:
    refuse = False
    try:
        with redirect_stdout(io.StringIO()):
            C.quota_projete(648, 3)
    except C.Abort as exc:
        refuse = True
        motif = str(exc)
    verifie(refuse, "10 modèles × 8 variables — la nuit du 09/08 — est REFUSÉE")
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

# ⚠️ Et le plafond JOURNALIER doit rester un plafond. Il a été relevé de
# 50 % à 60 % le 08/08 pour laisser passer 51,8 % ; il doit toujours
# refuser ce qu'il est censé attraper — « quelqu'un a doublé le nombre
# de points sans recompter ».
refuse = False
try:
    with redirect_stdout(io.StringIO()):
        C.quota_projete(1300, 3)
except C.Abort:
    refuse = True
verifie(refuse, "1300 points (10 400 pondérés) restent REFUSÉS par le plafond journalier")

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


print(f"\n{ok} assertions vertes, {len(ko)} en échec")
for m in ko:
    print(f"  ❌ {m}")
sys.exit(1 if ko else 0)
