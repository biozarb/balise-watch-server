#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  verif/recalcul_balise_jour.py — le contrôle n°2 du lot S3 (23/08/2026)
#
#  ⛔⛔ CE FICHIER N'IMPORTE NI `score` NI `scoring`, ET C'EST TOUT
#  L'ENJEU. Un recalcul qui recopie la formule de `scoring.py` ne teste
#  rien : il teste que le presse-papier fonctionne. Celui-ci est écrit
#  DEPUIS LA DÉFINITION, recopiée mot pour mot ci-dessous, et il s'y
#  tient même quand c'est moins commode. `verif/test_recalcul_balise_jour.py`
#  rend ROUGE toute version qui importerait l'un ou l'autre — le contrôle
#  est statique (`ast`), comme `test_separation.py`.
#
# ═══ LA DÉFINITION, EN TOUTES LETTRES ═══
#
#  Pour une balise, une journée civile UTC, un modèle et une classe
#  d'échéance :
#
#  1. La classe d'échéance désigne le jour d'ÉMISSION de la prévision :
#     +6 h = émise le jour noté, +24 h = la veille, +48 h = l'avant-veille.
#  2. Les pas de la prévision valent `t0 + i × step_s` (secondes UTC).
#     On ne garde que ceux qui tombent DANS la journée notée.
#  3. Pour chaque pas conservé dont la vitesse prévue est finie, on
#     rassemble les relevés observés dont l'horodatage est à ±20 min du
#     pas. S'il n'y en a aucun, l'heure est ABSENTE — jamais comblée,
#     jamais interpolée.
#  4. L'observation de l'heure est la moyenne de ces relevés :
#     · la FORCE est la moyenne ARITHMÉTIQUE des forces finies ;
#     · la DIRECTION est la moyenne VECTORIELLE — somme des
#       (u, v) = (V·sin θ, V·cos θ) — des seuls relevés dont la force
#       atteint 5 km/h, puis atan2(Σu, Σv) ramené dans [0, 360[.
#       Sous ce seuil, la direction est du bruit : on garde la force et
#       on jette la direction.
#     · s'il n'y a aucune force finie, l'heure est ABSENTE.
#  5. L'erreur d'une heure est VECTORIELLE — ‖V⃗prévu − V⃗observé‖ —
#     dès que les DEUX côtés ont une direction ET que les DEUX forces
#     atteignent 5 km/h. Sinon, repli SCALAIRE : |Vprévu − Vobservé|.
#  6. `err_vec_med` est la MÉDIANE des erreurs horaires (valeur absolue),
#     et la journée n'est notée que si elle compte au moins 6 heures
#     appariées.
#
#  ⓘ Les quatre constantes de cette définition — ±20 min, 5 km/h,
#  6 heures, les trois classes d'échéance — sont REDÉCLARÉES ici, sous
#  leurs propres noms. C'est délibéré : une constante redéclarée est une
#  constante qui peut diverger, et cette divergence est EXACTEMENT ce
#  que ce détecteur existe pour voir. Un écart signalé après un
#  changement légitime de `scoring.py` n'est pas un faux positif, c'est
#  le contrôle qui fait son travail — il n'est pas bloquant.
#
# ═══ ⛔ CE QUE CE SCRIPT NE COUVRE PAS ═══
#
#  Il refait l'APPARIEMENT et l'ERREUR VECTORIELLE, rien d'autre. Il ne
#  couvre PAS :
#    · le régime (`day_regime`, 850 hPa du modèle de référence) ;
#    · le biais de site, sa pente, et la colonne corrigée du lot S2 ;
#    · les deux skills (persistance, climatologie) ;
#    · `lead_exact_h` — ⚠️ et il faut le dire, parce que cette colonne a
#      désormais TROIS origines dans la même unité : `fcst/` compte
#      depuis ~03:19, `fcstreduit/` depuis ~05:00, et `fcstarome/`
#      depuis 00 Z (son `fetched_at` EST l'heure du run). Comparer des
#      échéances exactes entre flux n'aurait pas de sens ; on ne le fait
#      donc pas, plutôt que de le faire mal ;
#    · les scores de zone, les événements, la pression.
#  Un détecteur qui laisse croire qu'il couvre l'appariement sans le
#  refaire serait pire que pas de détecteur — d'où l'arbitrage du §2.2
#  du prompt S3, tranché ici dans le sens fort : ON REFAIT
#  L'APPARIEMENT. Le prix est que le fichier fait plus de 50 lignes.
#
# ═══ CE QU'IL FAIT D'UNE NUIT ═══
#
#  Il tire 20 balise-jours au hasard — mais STRATIFIÉ par (flux ×
#  réseau) RÉELLEMENT PRÉSENTS ce jour-là, jamais uniformément : le
#  22/08, 2 925 balises sur 3 497 ne portaient qu'`arome_r2`, et un
#  tirage uniforme aurait mis ~84 % des tirages sur le chemin
#  mono-modèle sans presque jamais toucher le chemin à onze modèles des
#  Pioupiou. La graine est DÉRIVÉE DU JOUR, jamais de l'horloge : un
#  écart qu'on ne peut pas rejouer à l'identique n'est pas un
#  signalement, c'est du bruit.
#
#  Il compare à `model_verif_daily` par des requêtes CIBLÉES (une par
#  balise-jour tirée), jamais par un dump paginé. Un écart supérieur à
#  0,05 km/h est journalisé en ⚠️ et le script sort quand même 0 :
#  ⛔ CE CONTRÔLE N'EST PAS BLOQUANT. C'est un détecteur de dérive.
#
# ═══ ⚠️ UN ÉCART N'EST PAS TOUJOURS UNE FAUTE DE CALCUL ═══
#
#  Il peut aussi dire que le CODE A CHANGÉ APRÈS la notation de cette
#  journée-là. Cas réel, mesuré au premier essai le 23/08/2026 sur la
#  journée du 22/08 : deux aérodromes (`metar:EDDL`, `metar:LFBP`)
#  s'apparient ici sur 19 et 20 heures alors que la base ne porte
#  AUCUNE ligne pour eux. Ni le recalcul ni la notation n'ont tort :
#  `obsmetar_key` n'est entrée dans `score.OBS_KEY_FUNCS` que le 23/08
#  à 12:20 UTC (lot S0.11), c'est-à-dire APRÈS le run de notation du
#  22/08 (23/08, 03:58 UTC). L'écart est DATÉ, il se referme tout seul
#  à la notation suivante — mais il faut le lire, pas le taire.
#  ⇒ Dans le run de nuit, cette confusion n'existe pas : le recalcul
#  tourne sur la journée que la notation vient d'écrire, avec le code
#  qui vient de l'écrire.
#
#  ⛔ IL N'ÉCRIT RIEN : ni base, ni R2, ni cache. Lecture seule.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

# ── Les constantes de la définition, redéclarées (cf. l'en-tête) ──────

#: Demi-fenêtre d'appariement, en millisecondes. Miroir de
#: `scoring.OBS_HALF_WINDOW_MS` — volontairement non importé.
DEMI_FENETRE_MS = 20 * 60 * 1000

#: Sous cette force, la direction d'un relevé est du bruit : on garde la
#: force et on jette la direction. Miroir de `scoring.DIR_MIN_WIND_KMH`.
VENT_MIN_DIRECTION_KMH = 5.0

#: Heures appariées minimales pour qu'une balise-jour compte. Miroir de
#: `score.MIN_HOURS_DAILY`.
HEURES_MIN = 6

#: Classe d'échéance ← nombre de jours entre l'émission et la journée
#: notée. Miroir de `score.LEAD_BY_OFFSET`.
CLASSE_PAR_OFFSET = {0: 6, 1: 24, 2: 48}

#: L'écart à partir duquel on crie. 0,05 km/h, c'est-à-dire bien en
#: dessous de l'arrondi à 4 décimales de la base et bien au-dessus de ce
#: qu'un ordre d'opérations en flottants peut produire sur 24 heures.
#: ⓘ L'arrondi À L'ENTIER des tuiles AROME/R2 (`arome-wind/ingest.py`)
#: n'entre PAS ici : les deux chemins lisent la MÊME valeur arrondie
#: dans la MÊME archive, donc il ne peut créer aucun écart entre eux.
#: Vérifié plutôt que supposé — cf. la note du lot S3.
ECART_MAX_KMH = 0.05

#: Balise-jours tirés par nuit.
TIRAGES = 20

JOUR_MS = 86_400_000


# ══════════════════════════════════════════════════════════════════════
#  1. LES CLÉS D'ARCHIVE — réécrites, jamais importées
# ══════════════════════════════════════════════════════════════════════
#
#  ⚠️ Elles sont le miroir de celles de `score.py`. Les recopier est le
#  prix du contrôle : si l'une des deux dérive, ce script lira une clé
#  vide et le DIRA (« 0 ligne de prévision »), au lieu de comparer deux
#  chiffres issus du même code.
#
#  ⓘ `fcst/` est le seul flux PARTITIONNABLE (lot S0.6). On lit ses
#  parties tant qu'elles existent, sans manifeste : ce script n'a pas à
#  juger d'une partie manquante — c'est le travail de `fcst_parties`, et
#  le sien est de recalculer ce qui EST là.

FLUX_PREVISION = {
    "fcst": lambda d: f"fcst/{d:%Y/%m}/fcst_{d:%Y-%m-%d}.ndjson.gz",
    "fcstagrume": lambda d: f"fcstagrume/{d:%Y/%m}/fcstagrume_{d:%Y-%m-%d}.ndjson.gz",
    "fcstarome": lambda d: f"fcstarome/{d:%Y/%m}/fcstarome_{d:%Y-%m-%d}.ndjson.gz",
    "fcstreduit": lambda d: f"fcstreduit/{d:%Y/%m}/fcstreduit_{d:%Y-%m-%d}.ndjson.gz",
}

#: Les parties 2..n du flux `fcst/`, lues tant qu'elles répondent.
def cle_fcst_partie(d: datetime, partie: int) -> str:
    return f"fcst/{d:%Y/%m}/fcst_{d:%Y-%m-%d}_p{partie}.ndjson.gz"


FLUX_OBSERVATION = {
    "pioupiou": lambda d: f"obs/{d:%Y/%m}/obs_{d:%Y-%m-%d}.ndjson.gz",
    "windsmobi": lambda d: f"obswindsmobi/{d:%Y/%m}/obswindsmobi_{d:%Y-%m-%d}.ndjson.gz",
    "infoclimat": lambda d: f"obsinfoclimat/{d:%Y/%m}/obsinfoclimat_{d:%Y-%m-%d}.ndjson.gz",
    "mf": lambda d: f"obsmf/{d:%Y/%m}/obsmf_{d:%Y-%m-%d}.ndjson.gz",
    "aemet": lambda d: f"obsaemet/{d:%Y/%m}/obsaemet_{d:%Y-%m-%d}.ndjson.gz",
    "metar": lambda d: f"obsmetar/{d:%Y/%m}/obsmetar_{d:%Y-%m-%d}.ndjson.gz",
}


def _stockage():
    """R2, en RECOURS du disque local. Absent ⇒ `None`, et on le dira."""
    outils = pathlib.Path(__file__).resolve().parent.parent / "tools"
    if str(outils) not in sys.path:
        sys.path.insert(0, str(outils))
    try:
        from storage import Storage             # type: ignore
        return Storage("model-verif", bucket_env="MODEL_VERIF_BUCKET",
                       defaut="model-verif", plafond=10)
    except Exception:                           # noqa: BLE001
        return None


def lire_ndjson(racine: pathlib.Path, cle: str, stockage=None) -> list[dict]:
    """Le local d'abord, R2 ensuite. Un objet absent rend `[]`."""
    chemin = racine / cle
    brut = None
    if chemin.exists():
        brut = chemin.read_bytes()
    elif stockage is not None:
        try:
            brut = stockage.get(cle)
        except Exception:                       # noqa: BLE001
            brut = None
    if not brut:
        return []
    try:
        texte = gzip.decompress(brut).decode("utf-8")
    except OSError:
        texte = brut.decode("utf-8")
    return [json.loads(l) for l in texte.splitlines() if l.strip()]


# ══════════════════════════════════════════════════════════════════════
#  2. LE RECALCUL — écrit depuis la définition de l'en-tête
# ══════════════════════════════════════════════════════════════════════

def _fini(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) \
        and math.isfinite(x)


def moyenne_des_releves(releves):
    """Point 4 de la définition. Rend `(force, direction, n)`.

    Force : moyenne ARITHMÉTIQUE. Direction : moyenne VECTORIELLE des
    seuls relevés à ≥ 5 km/h. Aucune force finie ⇒ `(None, None, 0)`.
    """
    somme_force = 0.0
    n_force = 0
    su = sv = 0.0
    n_dir = 0
    for _, force, direction in releves:
        if not _fini(force):
            continue
        somme_force += force
        n_force += 1
        if not _fini(direction) or force < VENT_MIN_DIRECTION_KMH:
            continue
        rad = math.radians(direction)
        su += force * math.sin(rad)
        sv += force * math.cos(rad)
        n_dir += 1
    if n_force == 0:
        return None, None, 0
    dir_moy = ((math.degrees(math.atan2(su, sv)) + 360) % 360
               if n_dir else None)
    return somme_force / n_force, dir_moy, n_force


def erreur_horaire(f_force, f_dir, o_force, o_dir) -> float:
    """Point 5 de la définition : vectorielle si possible, sinon scalaire."""
    if (f_dir is not None and o_dir is not None
            and f_force >= VENT_MIN_DIRECTION_KMH
            and o_force >= VENT_MIN_DIRECTION_KMH):
        fr, orad = math.radians(f_dir), math.radians(o_dir)
        du = f_force * math.sin(fr) - o_force * math.sin(orad)
        dv = f_force * math.cos(fr) - o_force * math.cos(orad)
        return math.hypot(du, dv)
    return abs(f_force - o_force)


def mediane(valeurs) -> float | None:
    v = sorted(x for x in valeurs if _fini(x))
    if not v:
        return None
    m = len(v) // 2
    return v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2.0


def recalculer(ligne_prevision: dict, releves_obs, debut_jour_ms: int):
    """`err_vec_med` d'UNE balise-jour-modèle-échéance, ou `None`.

    `releves_obs` : la liste `(t_ms, force, direction)` de la balise, sur
    la journée notée, triée par `t`. Rend `(err_vec_med, n_heures)`.
    """
    vitesses = ligne_prevision.get("speed") or []
    directions = ligne_prevision.get("dir") or []
    t0 = int(ligne_prevision["t0"])
    pas = int(ligne_prevision["step_s"])

    erreurs = []
    bas = 0
    for i, force_prevue in enumerate(vitesses):
        t = (t0 + i * pas) * 1000
        # Point 2 : seuls les pas de la journée notée.
        if not (debut_jour_ms <= t < debut_jour_ms + JOUR_MS):
            continue
        if not _fini(force_prevue):
            continue
        # Point 3 : les relevés à ±20 min. La série est triée, donc on
        # avance un curseur au lieu de la reparcourir à chaque heure.
        while bas < len(releves_obs) and releves_obs[bas][0] < t - DEMI_FENETRE_MS:
            bas += 1
        fenetre = []
        j = bas
        while j < len(releves_obs) and releves_obs[j][0] <= t + DEMI_FENETRE_MS:
            fenetre.append(releves_obs[j])
            j += 1
        if not fenetre:
            continue
        o_force, o_dir, _ = moyenne_des_releves(fenetre)
        if o_force is None:
            continue
        f_dir = directions[i] if i < len(directions) else None
        erreurs.append(erreur_horaire(
            force_prevue, f_dir if _fini(f_dir) else None, o_force, o_dir))
    # Point 6.
    if len(erreurs) < HEURES_MIN:
        return None, len(erreurs)
    return mediane([abs(e) for e in erreurs]), len(erreurs)


# ══════════════════════════════════════════════════════════════════════
#  3. LE TIRAGE — stratifié, reproductible
# ══════════════════════════════════════════════════════════════════════

def graine_du_jour(jour: datetime) -> int:
    """Dérivée du JOUR, jamais de l'horloge.

    ⛔ C'est ce qui rend un signalement rejouable : « recalcul du 22/08,
    balise X » doit désigner exactement le même tirage demain qu'hier.
    Un `random.seed()` sans argument, ou un `time.time()`, aurait rendu
    tout écart signalé impossible à reproduire — donc impossible à
    corriger, donc ignoré au bout de la deuxième fois.
    """
    g = 0
    for c in jour.strftime("%Y-%m-%d"):
        g = (g * 131 + ord(c)) & 0xFFFFFFFF
    return g or 1


class Xorshift32:
    """Le même générateur que `scoring._XorShift` — réécrit, pas importé.

    ⓘ Il n'a pas à être bit-à-bit identique au sien pour que ce script
    fasse son travail : il doit être DÉTERMINISTE, c'est tout. Écrire
    « le même » aurait été un import déguisé.
    """

    def __init__(self, graine: int):
        self.s = graine & 0xFFFFFFFF or 0x9E3779B9

    def suivant(self) -> float:
        s = self.s
        s ^= (s << 13) & 0xFFFFFFFF
        s ^= s >> 17
        s ^= (s << 5) & 0xFFFFFFFF
        self.s = s & 0xFFFFFFFF
        return self.s / 0x1_0000_0000


def tirer_stratifie(candidats, n: int, graine: int):
    """`n` tirages répartis sur les strates PRÉSENTES, au tour à tour.

    ⛔ PAS UNIFORME, et la raison est chiffrée : le 22/08, 2 925 balises
    sur 3 497 ne portaient qu'`arome_r2`. Un tirage uniforme aurait mis
    ~84 % des tirages sur le chemin mono-modèle et n'aurait presque
    jamais touché le chemin à onze modèles des Pioupiou — celui où les
    fautes coûtent le plus cher.

    ⚠️ LES STRATES SONT DÉRIVÉES DE CE QUI EST LÀ, pas d'une liste
    écrite dans ce fichier : le nombre de flux est passé de 2 à 4 en
    seize jours, et le nombre de réseaux notés de 1 à 6 en deux.
    """
    strates: dict[tuple, list] = {}
    for c in candidats:
        strates.setdefault((c["flux"], c["source"]), []).append(c)
    noms = sorted(strates)
    tailles = {nom: len(strates[nom]) for nom in noms}
    rnd = Xorshift32(graine)
    for nom in noms:                       # ordre stable DANS la strate
        lot = strates[nom]
        for i in range(len(lot) - 1, 0, -1):
            j = int(rnd.suivant() * (i + 1))
            lot[i], lot[j] = lot[j], lot[i]
    choisis, k = [], 0
    while len(choisis) < n and any(strates[nom] for nom in noms):
        nom = noms[k % len(noms)]
        k += 1
        if strates[nom]:
            choisis.append(strates[nom].pop())
    return choisis, tailles


# ══════════════════════════════════════════════════════════════════════
#  4. LA BASE — une requête CIBLÉE par balise-jour, jamais un dump
# ══════════════════════════════════════════════════════════════════════
#
#  ⛔ ET SURTOUT PAS `score.Supabase(dry_run=True)`. Son `select()` fait
#  `if self.dry_run: return []` : toute sonde bâtie ainsi lit ZÉRO ligne
#  et ne le dit pas. Le S1 l'a payé le 22/08, le S0.11 le 23/08 (où
#  `score.py --dry-run` a imprimé « `station_zone` est vide » alors que
#  la table porte 4 019 lignes). Ici, pas de mode à blanc du tout : si
#  les secrets manquent, on le DIT et on sort.

def lire_base(url: str, cle: str, jour: str, unite: dict):
    """La ligne `model_verif_daily` d'un balise-jour, ou `None`."""
    params = (f"day=eq.{jour}&source=eq.{unite['source']}"
              f"&station_id=eq.{urllib.parse.quote(unite['station_id'])}"
              f"&model=eq.{unite['model']}&lead_h=eq.{unite['lead_h']}"
              f"&select=err_vec_med,n_hours,fcst_src")
    req = urllib.request.Request(f"{url}/rest/v1/model_verif_daily?{params}")
    req.add_header("apikey", cle)
    req.add_header("Authorization", f"Bearer {cle}")
    with urllib.request.urlopen(req, timeout=30) as r:
        lignes = json.loads(r.read().decode("utf-8"))
    return lignes[0] if lignes else None


# ══════════════════════════════════════════════════════════════════════
#  5. LE RUN
# ══════════════════════════════════════════════════════════════════════

def lire_prevision(racine, jour, stockage):
    """Toutes les lignes de prévision utiles, avec LEUR FLUX et LEUR CLASSE."""
    lignes = []
    for offset, classe in CLASSE_PAR_OFFSET.items():
        emis = jour - timedelta(days=offset)
        for flux, cle in FLUX_PREVISION.items():
            lot = lire_ndjson(racine, cle(emis), stockage)
            if flux == "fcst":
                # Les parties 2..n, tant qu'elles répondent (lot S0.6).
                partie = 2
                while True:
                    suite = lire_ndjson(racine, cle_fcst_partie(emis, partie),
                                        stockage)
                    if not suite:
                        break
                    lot += suite
                    partie += 1
            for r in lot:
                r = dict(r)
                r["_flux"] = flux
                r["_lead_h"] = classe
                lignes.append(r)
    return lignes


def lire_observations(racine, jour, stockage):
    """`{source:station_id: [(t_ms, force, direction), …]}`, trié."""
    out: dict[str, list] = {}
    for source, cle in FLUX_OBSERVATION.items():
        for r in lire_ndjson(racine, cle(jour), stockage):
            unite = f"{r['source']}:{r['station_id']}"
            t = r.get("t") or []
            sp = r.get("speed") or []
            di = r.get("dir") or []
            serie = [(int(ts) * 1000,
                      sp[i] if i < len(sp) else None,
                      di[i] if i < len(di) else None)
                     for i, ts in enumerate(t)]
            serie.sort(key=lambda x: x[0])
            out.setdefault(unite, []).extend(serie)
    for unite in out:
        out[unite].sort(key=lambda x: x[0])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="/var/lib/bw-model-verif")
    ap.add_argument("--day", default=None,
                    help="journée à recalculer (défaut : hier)")
    ap.add_argument("--tirages", type=int, default=TIRAGES)
    ap.add_argument("--sans-base", action="store_true",
                    help="recalcule et affiche, sans rien comparer "
                         "(pour un essai hors production)")
    args = ap.parse_args()

    jour = (datetime.strptime(args.day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if args.day
            else datetime.now(timezone.utc) - timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0)
    racine = pathlib.Path(args.out)
    debut_jour_ms = int(jour.timestamp()) * 1000
    jour_txt = jour.strftime("%Y-%m-%d")

    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    cle = os.environ.get("SUPABASE_SERVICE_KEY", "")
    if not args.sans_base and not (url and cle):
        print("⛔ SUPABASE_URL / SUPABASE_SERVICE_KEY absents — rien à "
              "comparer. (`--sans-base` pour recalculer seulement.)",
              file=sys.stderr)
        return 1

    stockage = _stockage()
    print(f"▶ recalcul indépendant — journée {jour_txt}"
          + ("" if stockage else "  ⚠️ R2 indisponible : disque local seul"))

    previsions = lire_prevision(racine, jour, stockage)
    observations = lire_observations(racine, jour, stockage)
    print(f"  {len(previsions)} lignes de prévision, "
          f"{len(observations)} balises observées")
    if not previsions or not observations:
        print("  ⚠️ archive absente ou vide pour cette journée — rien à "
              "recalculer. Ce n'est PAS un écart.", file=sys.stderr)
        return 0

    candidats = [
        {"flux": r["_flux"], "source": r["source"],
         "station_id": r["station_id"], "model": r["model"],
         "lead_h": r["_lead_h"], "_ligne": r}
        for r in previsions
        if f"{r['source']}:{r['station_id']}" in observations
    ]
    if not candidats:
        print("  ⚠️ aucune balise n'a À LA FOIS une prévision et des "
              "observations — rien à recalculer.", file=sys.stderr)
        return 0

    choisis, tailles = tirer_stratifie(candidats, args.tirages,
                                       graine_du_jour(jour))
    print(f"  strates présentes ({len(tailles)}) : "
          + " · ".join(f"{f}/{s} {n}" for (f, s), n in sorted(tailles.items())))
    compo: dict[tuple, int] = {}
    for c in choisis:
        compo[(c["flux"], c["source"])] = compo.get((c["flux"], c["source"]), 0) + 1
    print(f"  tirage ({len(choisis)}) : "
          + " · ".join(f"{f}/{s} ×{n}" for (f, s), n in sorted(compo.items()))
          + f"   [graine {graine_du_jour(jour)}]")
    return _comparer(choisis, observations, debut_jour_ms, jour_txt, url, cle,
                     args.sans_base)


def _comparer(choisis, observations, debut_jour_ms, jour_txt, url, cle,
              sans_base: bool) -> int:
    """Recalcule, compare, journalise. ⛔ Rend TOUJOURS 0 : non bloquant."""
    ecarts, compares, muets, injoignables = [], 0, 0, 0
    for c in choisis:
        unite = f"{c['source']}:{c['station_id']}"
        mien, n_heures = recalculer(c["_ligne"], observations[unite],
                                    debut_jour_ms)
        etiquette = (f"{c['flux']}/{unite} {c['model']} +{c['lead_h']}h")
        if mien is None:
            # Moins de 6 heures appariées : la définition dit que la
            # journée n'est pas notée. La base ne devrait rien porter
            # non plus — et si elle porte quelque chose, C'EST un écart.
            muets += 1
            if sans_base:
                continue
            try:
                sien = lire_base(url, cle, jour_txt, c)
            except (urllib.error.URLError, urllib.error.HTTPError) as exc:
                injoignables += 1
                print(f"    ⚠️ base injoignable pour {etiquette} : {exc}",
                      file=sys.stderr)
                continue
            if sien is not None:
                ecarts.append((etiquette, None, sien["err_vec_med"],
                               f"{n_heures} h appariées ici (< {HEURES_MIN}) "
                               f"mais la base porte une ligne"))
            continue
        if sans_base:
            print(f"    ⓘ {etiquette} : {mien:.4f} km/h sur {n_heures} h")
            continue
        try:
            sien = lire_base(url, cle, jour_txt, c)
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            injoignables += 1
            print(f"    ⚠️ base injoignable pour {etiquette} : {exc}",
                  file=sys.stderr)
            continue
        if sien is None:
            ecarts.append((etiquette, mien, None,
                           f"{n_heures} h appariées ici mais AUCUNE ligne "
                           f"en base"))
            continue
        compares += 1
        ref = sien.get("err_vec_med")
        if ref is None:
            ecarts.append((etiquette, mien, None, "`err_vec_med` nul en base"))
            continue
        delta = abs(mien - float(ref))
        if delta > ECART_MAX_KMH:
            ecarts.append((etiquette, mien, float(ref),
                           f"écart {delta:.4f} km/h "
                           f"({n_heures} h ici, {sien.get('n_hours')} en base)"))

    print(f"  {compares} balise-jours comparés, {muets} sous le seuil de "
          f"{HEURES_MIN} h"
          + (f", {injoignables} base injoignable" if injoignables else ""))
    if not ecarts:
        print(f"  ✅ aucun écart au-dessus de {ECART_MAX_KMH} km/h.")
        return 0
    # ⛔ ⚠️ ET PAS ❌ : ce contrôle est un DÉTECTEUR DE DÉRIVE, pas un
    # garde-fou. Il ne bloque rien, il ne fait pas rougir Healthchecks,
    # et il sort 0 — parce qu'un écart de 0,06 km/h sur une balise ne
    # justifie pas de perdre une nuit de notation, et qu'un contrôle qui
    # perdrait des nuits pour ça serait débranché avant la fin du mois.
    print(f"  ⚠️ {len(ecarts)} ÉCART(S) — le recalcul indépendant ne "
          f"retrouve pas la base :", file=sys.stderr)
    for etiquette, mien, sien, pourquoi in ecarts:
        print(f"    ⚠️ {etiquette} — ici {mien}, base {sien} : {pourquoi}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
