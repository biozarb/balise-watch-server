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


print(f"\n{ok} assertions vertes, {len(ko)} en échec")
for m in ko:
    print(f"  ❌ {m}")
sys.exit(1 if ko else 0)
