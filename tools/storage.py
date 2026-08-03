#!/usr/bin/env python3
"""
storage.py — LE module d'upload des 5 chaînes d'ingestion (03/08/2026).

Avant ce fichier, `sb_upload()` existait en **cinq exemplaires quasi
identiques** (`arome-wind`, `arome-thermal`, `arpege-thermal`,
`arome-gustfront`, `arpege-isobars`), chacun avec sa propre copie de la
leçon `Cache-Control` des 23-24/07 recopiée en docstring. Même motif de
dette que les 4 copies du calcul de features. La migration vers R2
demandait une sixième copie : c'est ce qui a déclenché la factorisation.

┌─ CE QUE CE MODULE EST ──────────────────────────────────────────────┐
│ Une seule signature, DEUX implémentations derrière (Supabase        │
│ Storage / Cloudflare R2), choisies par variable d'environnement.     │
│ Ça permet de basculer UNE CHAÎNE À LA FOIS, et de revenir en         │
│ arrière sans toucher au code — seulement à un secret GitHub.        │
│                                                                     │
│ Ce n'est PAS une couche d'abstraction générale. Elle ne connaît que  │
│ ce dont les 5 chaînes ont besoin : écrire un objet, le relire, le    │
│ supprimer, et compter ce que ça coûte.                              │
└─────────────────────────────────────────────────────────────────────┘

    STORAGE_BACKEND = supabase   (défaut — comportement d'avant, inchangé)
                    | r2
                    | both       (double écriture, cf. §3 ci-dessous)

⚠️ GARDE-FOU N°1 — R2 N'A PAS DE PLAFOND : DÉPASSER = PAYER.
   Cloudflare ne propose aucun hard cap ; tout dépassement du palier
   gratuit est facturé automatiquement. D'où, ici :
     · un plafond DUR d'écritures par run (`MAX_CLASS_A_RUN`), qui
       provoque un abort net et jamais une boucle de réessai — une
       boucle de retry est LE scénario qui crame 1 M d'opérations ;
     · un refus de démarrer si la projection mensuelle dépasse le seuil
       (`verifier_dimensionnement`), et le compte journalisé À CHAQUE
       RUN. Sans ça, remonter `MAX_HOURS` ou élargir une BBOX ferait
       grimper les écritures sans que personne ne le voie ;
     · `exists()` REFUSÉ sur R2 : `HeadObject` est facturé Class A.
       Voir la docstring de la méthode pour ce qu'il faut faire à la
       place (relire le manifest — 1 Class B, pas N Class A) ;
     · aucun `ListObjects` nulle part. La purge se fait par comparaison
       à un état connu (le manifest), comme le worker de packs le fait
       avec son checkpoint.
   Palier gratuit (page pricing R2, vérifiée le 01/08/2026) :
   10 Go-mois · 1 M Class A/mois · 10 M Class B/mois · egress GRATUIT.
   `DeleteObject` et `AbortMultipartUpload` sont gratuites.

⚠️ LE `cache_control` EST UN ARGUMENT OBLIGATOIRE, ET C'EST VOULU.
   C'est la leçon des 23-24/07, et elle est indissociable du choix de
   clé d'objet — les deux moitiés de l'arbitrage ne se séparent pas :
     · clé STABLE, réécrite en place (wind, thermal, gustfront,
       manifests) → cache court obligatoire. Un TTL long laisse un
       navigateur ou un edge CDN servir une grille périmée bien après
       un nouveau run, et le hard-refresh n'y peut rien.
     · clé HORODATÉE, immuable (géojson isobares) → cache long possible,
       mais **purge explicite obligatoire dans le même commit**, sinon
       le bucket croît linéairement et sans fin. C'est exactement ce qui
       a causé le dépassement du 30/07 (bucket `isobars` à 2,1 Go).
   Pas de valeur par défaut : à chaque appel, l'appelant doit avoir
   tranché. Une constante `CACHE_*` ci-dessous nomme les deux cas.

⚠️ `r2.dev` N'EST PAS MIS EN CACHE PAR LE CDN CLOUDFLARE (vérifié au
   curl le 01/08 : aucun `cf-cache-status` dans la réponse). Sans
   conséquence pour les objets en `no-cache` — mais pour les géojson
   isobares en `max-age=21600`, le domaine personnalisé prend ici une
   vraie valeur. Il était déjà noté comme prérequis de sortie de bêta
   (CHECKLIST_CLOUDFLARE_R2.md §0, chemins B et C).

§3 — POURQUOI LE MODE `both` EXISTE
   Les clés isobares sont horodatées : au moment de la bascule, le
   nouveau bucket est VIDE, et le manifest liste des échéances qui
   n'existent que dans l'ancien. Écrire des deux côtés pendant
   `PAST_RETENTION_H` (72 h, soit 12 runs ARPEGE) laisse le nouveau
   bucket se remplir tout seul, puis on bascule le client sans coupure.
   Coût doublé pendant trois jours, et c'est tout.
   Les buckets à clés stables (`wind-grid`) n'ont pas ce problème :
   8 runs suffisent à repeupler entièrement, soit une journée — pour
   eux, `both` est inutile.

Usage :
    from storage import Storage, verifier_dimensionnement, CACHE_REECRIT

    plafond = verifier_dimensionnement("arome-wind", objets_par_run=504,
                                       runs_par_jour=8, mo_par_run=73)
    st = Storage("arome-wind", bucket_env="WIND_GRID_BUCKET",
                 defaut="wind-grid", plafond=plafond)
    st.put("arome/sol/44_6.json", body, cache_control=CACHE_REECRIT)
    ...
    st.bilan()          # à appeler en fin de run : c'est la journalisation
                        # qui rend une dérive visible AVANT la facture
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

# ══════════════════════════════════════════════════════════════════════
#  POLITIQUES DE CACHE  —  les deux seules valeurs légitimes
# ══════════════════════════════════════════════════════════════════════
# Objet RÉÉCRIT EN PLACE à chaque run (tuiles, manifests). Revalidation
# conditionnelle systématique via ETag — ce n'est pas un aller-retour
# plein à chaque fois, c'est un 304 quand rien n'a bougé.
CACHE_REECRIT = "no-cache, must-revalidate"

# Objet IMMUABLE une fois écrit (géojson isobares, clés horodatées).
# 6 h = la cadence des runs ARPEGE. Va de pair avec une purge explicite.
CACHE_IMMUABLE = "max-age=21600"

# ══════════════════════════════════════════════════════════════════════
#  SEUILS  —  refuser de démarrer plutôt que de payer
# ══════════════════════════════════════════════════════════════════════
# Marge ×2 sur tout, comme dans `backfill_packs.py`. Ces seuils ne sont
# pas des prévisions : ce sont des lignes au-delà desquelles on veut
# être ARRÊTÉ et forcé de comprendre.
SEUIL_ECRITURES_MOIS = 500_000        # 50 % du palier Class A (1 M/mois)
SEUIL_STOCKAGE_GO = 5.0               # 50 % du palier stockage (10 Go)
PALIER_CLASS_A_MOIS = 1_000_000
PALIER_STOCKAGE_GO = 10.0

# Plafond dur d'écritures par run, toutes chaînes confondues. La plus
# grosse (arome-wind) en fait 504 : 2 000 laisse largement la place à
# une croissance normale tout en arrêtant net une boucle.
MAX_CLASS_A_RUN = int(os.environ.get("MAX_CLASS_A_RUN", "2000"))

# ⚠️ `or` et pas un défaut de `get()` : une variable GitHub Actions non
# définie arrive comme chaîne VIDE, pas absente. Avec `get(x, "supabase")`
# on obtiendrait "" et un Abort au premier run de chaque chaîne non encore
# basculée — c'est-à-dire toutes.
BACKEND = (os.environ.get("STORAGE_BACKEND") or "supabase").strip().lower()
DRY_RUN = os.environ.get("DRY_RUN") == "1"

_BACKENDS_VALIDES = ("supabase", "r2", "both")


class Abort(Exception):
    """Arrêt net et volontaire. Jamais rattrapée pour réessayer — c'est
    tout l'intérêt : le run s'arrête, le précédent reste servi, et on
    reprend au run suivant une fois la cause comprise."""


# ══════════════════════════════════════════════════════════════════════
#  DIMENSIONNEMENT  —  à appeler AVANT la première écriture
# ══════════════════════════════════════════════════════════════════════
def verifier_dimensionnement(chaine, objets_par_run, runs_par_jour,
                             mo_par_run=None, log=print):
    """Chiffre le run AVANT de l'écrire, journalise, et refuse de
    démarrer si la projection dépasse un seuil. Renvoie le plafond dur
    d'écritures à passer à `Storage`.

    ⚠️ CETTE FONCTION EST LE GARDE-FOU, PAS UNE JOLIE TRACE. Sans elle,
    remonter `MAX_HOURS`, ajouter un niveau à `LEVELS` ou élargir une
    BBOX multiplierait les écritures **sans que personne ne le voie** —
    R2 les facturerait en silence. La ligne journalisée à chaque run est
    la seule chose qui rend une dérive visible avant la facture.

    Chiffres relevés le 03/08/2026 par `audit_storage.py` (comptes RÉELS
    du bucket, pas des estimations), avec les cadences lues dans les 5
    workflows GitHub Actions :

        arome/sol       63 obj × 8 runs =   504/j
        arome/alt      441 obj × 8 runs = 3 528/j   (63 tuiles × 7 niveaux)
        arome/thermal   64 obj × 8 runs =   512/j
        arpege/thermal 229 obj × 4 runs =   916/j
        gustfront        1 obj × 8 runs =     8/j
        isobars     (skip-if-exists)    =   ~64/j
                                  TOTAL ≈ 5 530/jour → ~168 000/mois → 17 %

    ⚠️ Le prompt de reprise du 02/08 projetait ~250 000 Class A/mois.
    Ce chiffre supposait `arpege-thermal` sur 962 tuiles (BBOX Europe
    d'origine) — or la BBOX a été réduite le 30/07 et l'audit n'en
    compte plus que 229. L'arbitrage « réduire arpege-thermal avant de
    migrer, ça diviserait la facture par deux » est donc SANS OBJET :
    c'est déjà fait, et cette chaîne pèse 17 % du total, pas 45 %.
    Leçon : re-mesurer avant de trancher sur un chiffre écrit la veille.
    """
    ecr_jour = objets_par_run * runs_par_jour
    ecr_mois = ecr_jour * 30
    marge = PALIER_CLASS_A_MOIS / max(ecr_mois, 1)

    log("┌─ DIMENSIONNEMENT PROJETÉ ────────────────────────────────────")
    log(f"│ chaîne                    : {chaine}   (backend {BACKEND}"
        f"{', DRY_RUN' if DRY_RUN else ''})")
    log(f"│ objets par run            : {objets_par_run} × {runs_par_jour} run(s)/jour")
    log(f"│ écritures                 : {ecr_jour}/jour → {ecr_mois}/mois "
        f"(seuil d'arrêt {SEUIL_ECRITURES_MOIS})")
    log(f"│   palier gratuit Class A  : 1 M/mois → {ecr_mois/PALIER_CLASS_A_MOIS*100:.1f} % "
        f"du palier, marge ×{marge:.0f}")
    log(f"│ plafond dur par run       : {MAX_CLASS_A_RUN} Class A (abort net)")
    if mo_par_run is not None:
        go = mo_par_run / 1000
        log(f"│ stockage stationnaire     : {mo_par_run:.0f} Mo "
            f"(seuil d'arrêt {SEUIL_STOCKAGE_GO*1000:.0f} Mo)")
        log(f"│   palier gratuit stockage : 10 Go-mois → marge ×{PALIER_STOCKAGE_GO/max(go,1e-9):.0f}")
        if go > SEUIL_STOCKAGE_GO:
            raise Abort(f"stockage projeté {go:.2f} Go > seuil {SEUIL_STOCKAGE_GO} Go")
    log("└──────────────────────────────────────────────────────────────")

    if ecr_mois > SEUIL_ECRITURES_MOIS:
        raise Abort(f"écritures projetées {ecr_mois}/mois > seuil "
                    f"{SEUIL_ECRITURES_MOIS} — comprendre AVANT de forcer "
                    f"(MAX_HOURS ? LEVELS ? BBOX ?)")
    if objets_par_run > MAX_CLASS_A_RUN:
        raise Abort(f"{objets_par_run} objets par run > plafond dur "
                    f"{MAX_CLASS_A_RUN} — le run s'arrêterait en cours de "
                    f"route et laisserait un état partiel. Relever "
                    f"MAX_CLASS_A_RUN sciemment, ou réduire le périmètre.")
    return MAX_CLASS_A_RUN


# ══════════════════════════════════════════════════════════════════════
#  BACKEND SUPABASE  —  le code d'avant, déplacé sans être modifié
# ══════════════════════════════════════════════════════════════════════
class _Supabase:
    """Reprend mot pour mot la logique des 5 `sb_upload()` d'origine,
    y compris le POST-puis-PUT du débogage du 19/07/2026 : selon les
    versions de storage-api, un upsert refusé remonte un 400 plutôt
    qu'un 409, et le PUT passe alors sans ambiguïté. Ne pas « nettoyer »
    ça sans relire BUGS.md."""

    nom = "supabase"

    def __init__(self, bucket):
        self.bucket = bucket
        self.url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        self.key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if not DRY_RUN and not (self.url and self.key):
            raise Abort("SUPABASE_URL / SUPABASE_SERVICE_KEY manquants")

    def _req(self, path, method, data=None, headers=None):
        return urllib.request.Request(
            f"{self.url}/storage/v1/object/{self.bucket}/{path}",
            data=data, method=method,
            headers={"Authorization": f"Bearer {self.key}",
                     "apikey": self.key, **(headers or {})})

    def put(self, path, body, cache_control, content_type, content_encoding,
            tries=3):
        last = None
        for attempt in range(tries):
            hdrs = {"Content-Type": content_type, "x-upsert": "true",
                    "Cache-Control": cache_control}
            if content_encoding:
                hdrs["Content-Encoding"] = content_encoding
            req = self._req(path, "POST" if attempt == 0 else "PUT",
                            data=body, headers=hdrs)
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    return r.status
            except urllib.error.HTTPError as e:
                try:
                    detail = e.read()[:300].decode("utf-8", "replace")
                except Exception:
                    detail = ""
                last = f"HTTP {e.code} — {detail}"
            except Exception as e:                       # réseau, timeout…
                last = f"{type(e).__name__}: {e}"
            print(f"  ⚠️ upload {path} tentative {attempt + 1}/{tries} : {last}",
                  file=sys.stderr)
            time.sleep(1 + 2 * attempt)
        raise Abort(f"upload {path} : échec après {tries} tentatives — {last}")

    def get(self, path):
        try:
            with urllib.request.urlopen(self._req(path, "GET"), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def exists(self, path):
        """HEAD. Gratuit chez Supabase — c'est ce qui permettait au
        `skip-if-exists` des isobares d'être écrit comme il l'est."""
        try:
            urllib.request.urlopen(
                urllib.request.Request(
                    f"{self.url}/storage/v1/object/info/{self.bucket}/{path}",
                    headers={"Authorization": f"Bearer {self.key}",
                             "apikey": self.key}), timeout=15)
            return True
        except Exception:
            return False

    def delete(self, path):
        try:
            urllib.request.urlopen(self._req(path, "DELETE"), timeout=60)
            return True
        except urllib.error.HTTPError as e:
            return e.code == 404


# ══════════════════════════════════════════════════════════════════════
#  BACKEND R2
# ══════════════════════════════════════════════════════════════════════
class _R2:
    """boto3, `max_attempts=1`. Aucun réessai automatique de botocore :
    une boucle de réessai est LE scénario qui crame 1 M d'opérations.
    On préfère un échec visible, repris au run suivant."""

    nom = "r2"

    def __init__(self, bucket):
        self.bucket = bucket
        self.client = None
        if DRY_RUN:
            return
        try:
            import boto3                              # noqa: PLC0415
            from botocore.config import Config        # noqa: PLC0415
        except ImportError:
            raise Abort("boto3 absent — `pip3 install boto3` "
                        "(ou lancer avec DRY_RUN=1)")
        for v in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY"):
            if not os.environ.get(v):
                raise Abort(f"variable d'environnement {v} manquante")
        self.client = boto3.client(
            "s3",
            endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
            config=Config(retries={"max_attempts": 1, "mode": "standard"}),
        )

    def put(self, path, body, cache_control, content_type, content_encoding,
            tries=1):
        kw = dict(Bucket=self.bucket, Key=path, Body=body,
                  ContentType=content_type, CacheControl=cache_control)
        if content_encoding:
            kw["ContentEncoding"] = content_encoding
        self.client.put_object(**kw)
        return 200

    def get(self, path):
        """`GetObject` sur une clé CONNUE — facturé Class B (10 M/mois),
        pas Class A. Ne pas confondre avec l'interdiction du garde-fou
        n°1, qui vise `ListObjects`/`HeadObject` pour reconstituer un
        état de reprise. Relire un manifest dont on connaît le chemin,
        c'est 1 Class B par run et par grille : 0,0002 % du palier."""
        try:
            return self.client.get_object(Bucket=self.bucket, Key=path)["Body"].read()
        except self.client.exceptions.NoSuchKey:
            return None

    def exists(self, path):
        raise Abort(
            "exists() est INTERDIT sur R2 : `HeadObject` est facturé en "
            "Class A, et un skip-if-exists en boucle sur N échéances "
            "dépenserait N opérations par run pour ne rien écrire.\n"
            "  → À la place : relire le manifest précédent (1 seul "
            "GetObject, Class B) et en déduire les échéances déjà "
            "produites. Le manifest est déjà la liste que le frontend "
            "lit ; c'est aussi l'état de reprise, exactement comme le "
            "checkpoint local du worker de packs.")

    def delete(self, path):
        """`DeleteObject` est GRATUITE chez R2 (page pricing, 01/08).
        Aucune raison de rogner sur la purge — c'est l'absence de purge
        qui a coûté 2,1 Go le 30/07, pas son coût."""
        self.client.delete_object(Bucket=self.bucket, Key=path)
        return True


# ══════════════════════════════════════════════════════════════════════
#  FAÇADE
# ══════════════════════════════════════════════════════════════════════
class Storage:
    """Une signature, un compteur, un plafond dur.

    `chaine` ne sert qu'à la journalisation. `bucket_env`/`defaut`
    reprennent la convention d'avant (`WIND_GRID_BUCKET` défaut
    `wind-grid`, `ISOBARS_BUCKET` défaut `isobars`) pour Supabase ;
    côté R2, `R2_BUCKET` prime s'il est défini, sinon le même nom.
    """

    def __init__(self, chaine, bucket_env, defaut, plafond=None):
        if BACKEND not in _BACKENDS_VALIDES:
            raise Abort(f"STORAGE_BACKEND={BACKEND!r} inconnu — attendu "
                        f"l'un de {_BACKENDS_VALIDES}")
        self.chaine = chaine
        self.plafond = plafond if plafond is not None else MAX_CLASS_A_RUN
        self.ecritures = 0
        self.suppressions = 0
        self.lectures = 0
        self.octets = 0

        bucket_sb = os.environ.get(bucket_env) or defaut
        bucket_r2 = os.environ.get("R2_BUCKET") or defaut
        self.cibles = []
        if BACKEND in ("supabase", "both"):
            self.cibles.append(_Supabase(bucket_sb))
        if BACKEND in ("r2", "both"):
            self.cibles.append(_R2(bucket_r2))
        # En mode `both`, Supabase reste l'AUTORITÉ pour les lectures et
        # le skip-if-exists : c'est lui qui contient l'historique, R2 se
        # remplit. La bascule du client vient après, pas avant.
        self.autorite = self.cibles[0]

    # ── écriture ──────────────────────────────────────────────────────
    def put(self, path, body, *, cache_control, content_type="application/json",
            content_encoding=None):
        """`cache_control` est OBLIGATOIRE et nommé — cf. l'en-tête du
        module. Utiliser `CACHE_REECRIT` ou `CACHE_IMMUABLE`, jamais une
        chaîne littérale écrite sur place."""
        if self.ecritures + 1 > self.plafond:
            raise Abort(
                f"[{self.chaine}] plafond d'écritures atteint "
                f"({self.plafond}) — arrêt net, aucun réessai. Le run "
                f"précédent reste servi ; reprise au prochain run.")
        self.ecritures += 1
        self.octets += len(body)
        if DRY_RUN:
            return 0
        statut = 0
        for cible in self.cibles:
            statut = cible.put(path, body, cache_control, content_type,
                               content_encoding)
        return statut

    # ── lecture ───────────────────────────────────────────────────────
    def get(self, path):
        """Renvoie les octets, ou None si absent. Class B côté R2."""
        self.lectures += 1
        if DRY_RUN:
            return None
        return self.autorite.get(path)

    def get_json(self, path):
        brut = self.get(path)
        if brut is None:
            return None
        try:
            return json.loads(brut)
        except ValueError:
            return None

    def exists(self, path):
        """⚠️ Lève sur R2 (Class A). Voir `_R2.exists` pour l'alternative."""
        if DRY_RUN:
            return False
        return self.autorite.exists(path)

    # ── suppression ───────────────────────────────────────────────────
    def delete(self, path):
        """Gratuite chez R2, gratuite chez Supabase. Une purge ne doit
        JAMAIS être bloquante : elle journalise son échec et laisse le
        run réussi intact (correctif du 30/07, `purge_stale`)."""
        self.suppressions += 1
        if DRY_RUN:
            return True
        ok = True
        for cible in self.cibles:
            try:
                cible.delete(path)
            except Exception as e:
                print(f"  ⚠️ purge {path} ({cible.nom}) : {e}", file=sys.stderr)
                ok = False
        return ok

    # ── journalisation ────────────────────────────────────────────────
    def bilan(self, log=print):
        """À appeler en FIN DE RUN, systématiquement. C'est cette ligne
        qui permettra de comparer les volumes réels aux projections, et
        de voir une dérive au run près plutôt qu'au relevé mensuel."""
        cibles = "+".join(c.nom for c in self.cibles)
        log(f"[compteurs {self.chaine}] backend={cibles} "
            f"écritures={self.ecritures} (plafond {self.plafond}) "
            f"lectures={self.lectures} suppressions={self.suppressions} "
            f"octets={self.octets/1e6:.1f} Mo"
            + ("  [DRY_RUN — rien n'a été écrit]" if DRY_RUN else ""))
        if self.ecritures >= self.plafond:
            log(f"⚠️ [{self.chaine}] le plafond a été ATTEINT — le run est "
                f"incomplet. Comprendre pourquoi avant de relever le seuil.")
        return {"backend": cibles, "ecritures": self.ecritures,
                "lectures": self.lectures, "suppressions": self.suppressions,
                "octets": self.octets}
