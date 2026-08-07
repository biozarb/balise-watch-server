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
verifie("pondérés/min" in sortie, "l'encadré annonce la cadence PONDÉRÉE par minute")
verifie("durée estimée" in sortie, "et la durée, qui décide du TimeoutStartSec")

# La cadence en vigueur doit passer, avec de la marge.
cadence_reelle = 60 / (C.BATCH_PAUSE_S + C.LATENCE_S)
par_min = cadence_reelle * n_vars / 10
verifie(par_min <= C.QUOTA_MINUTE * 0.9,
        f"la cadence en vigueur reste sous 90 % du plafond — {par_min:.0f}/min")
verifie(cadence_reelle < 120,
        f"et sous les ~120 req/min où la porte s'est fermée le 07/08 — "
        f"{cadence_reelle:.0f}/min")

# ⚠️ Et surtout : l'ANCIENNE valeur doit être REFUSÉE. Un garde-fou qui
# laisse passer ce qui a déjà cassé ne garde rien.
pause_avant = C.BATCH_PAUSE_S
C.BATCH_PAUSE_S = 0.25
try:
    refuse = False
    try:
        with redirect_stdout(io.StringIO()):
            C.quota_projete(648, 3)
    except C.Abort:
        refuse = True
    verifie(refuse, "0,25 s — la cadence qui a coûté 24 points — est REFUSÉE")
finally:
    C.BATCH_PAUSE_S = pause_avant


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


print(f"\n{ok} assertions vertes, {len(ko)} en échec")
for m in ko:
    print(f"  ❌ {m}")
sys.exit(1 if ko else 0)
