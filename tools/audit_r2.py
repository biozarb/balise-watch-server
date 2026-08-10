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
    for bucket, cle, taille in objets:
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


def pente_go_par_mois(historique) -> float | None:
    """Moindres carrés sur (jours, Go) de l'historique.

    ⚠️ Une simple différence entre le premier et le dernier point serait
    fausse ici : le volume oscille d'un run à l'autre (une chaîne à
    rétention courte écrit puis purge). C'est la TENDANCE qu'on veut, et
    deux points suffisent à la calculer mais pas à la croire — d'où le
    `None` sous trois points, qui vaut mieux qu'une pente inventée sur
    une oscillation.
    """
    pts = [(datetime.fromisoformat(h["t"]), h["octets"] / GO)
           for h in historique if h.get("t") and h.get("octets") is not None]
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
            couverture_partielle: bool = False) -> dict:
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
    return {"alerte": bool(motifs), "motifs": motifs,
            "go": go, "pente_go_mois": pente_mois,
            "jours_avant_palier": j_palier,
            "couverture_partielle": couverture_partielle}


def rendre(inventaire: dict, pente_mois, v: dict, class_a_consommees: int,
           log=print) -> None:
    """Le rapport lisible. Trié par poids décroissant : la première
    ligne est toujours celle sur laquelle agir."""
    go = inventaire["octets"] / GO
    log("┌─ JAUGE R2 (lecture seule) ───────────────────────────────────")
    log(f"│ total compte              : {go:8.3f} Go   "
        f"({go / PALIER_STOCKAGE_GO * 100:5.1f} % du palier {PALIER_STOCKAGE_GO:.0f} Go)")
    log(f"│ objets                    : {inventaire['objets']:8d}")
    if pente_mois is None:
        log("│ pente                     :        —     (moins de 3 relevés)")
    else:
        log(f"│ pente mesurée             : {pente_mois:+8.3f} Go/mois")
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
    for nom, e in sorted(inventaire["par_prefixe"].items(),
                         key=lambda kv: -kv[1]["octets"])[:20]:
        log(f"│ {nom:38s} {e['octets'] / GO:8.3f} Go  {e['objets']:7d} objets")
    log("├─ coût de cet audit ──────────────────────────────────────────")
    # ⚠️ Un audit qui surveille un quota et le consomme sans le dire est
    # une jauge malhonnête. `ListObjectsV2` EST une opération classe A.
    log(f"│ {class_a_consommees} opérations classe A consommées par ce listing "
        f"({class_a_consommees * 30 / PALIER_CLASS_A_MOIS * 100:.2f} % "
        f"du palier si nocturne)")
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
                objets.append((bucket, o["Key"], int(o.get("Size", 0))))
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
    except Abort as e:
        print(f"❌ {e}", file=sys.stderr)
        return 2

    inv = agreger(objets)
    hist_path = Path(a.out) / "audit_r2.jsonl"
    historique = charger_historique(hist_path)

    releve = {"t": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "octets": inv["octets"], "objets": inv["objets"],
              "buckets": {k: v["octets"] for k, v in inv["par_bucket"].items()},
              "couverture_complete": couverture_complete}
    # On écrit AVANT de juger : si le verdict lève, le relevé du jour est
    # quand même dans l'historique, et la pente de demain reste juste.
    if not a.sans_historique:
        try:
            ajouter_historique(hist_path, releve)
        except OSError as e:
            print(f"⚠️ historique non écrit ({e}) — pente indisponible demain",
                  file=sys.stderr)

    pente = pente_go_par_mois(historique + [releve])
    v = verdict(inv, pente, a.seuil_go, a.horizon_jours,
                couverture_partielle=not couverture_complete)

    if a.json:
        print(json.dumps({"releve": releve, "verdict": v,
                          "par_prefixe": inv["par_prefixe"],
                          "class_a": requetes}, ensure_ascii=False, indent=2))
    else:
        rendre(inv, pente, v, requetes)

    return 1 if v["alerte"] else 0


if __name__ == "__main__":
    sys.exit(main())
