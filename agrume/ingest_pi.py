#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/ingest_pi.py — étape 8 bis : l'ingestion d'AROME-PI
#                                                        (10/08/2026)
#
#  L'étape qui manquait à la séquence. Le poller DATE les runs PI depuis
#  ce matin ; personne ne les ARCHIVE. Sans ce fichier, l'étape 9 —
#  le composite temporel — n'a pas de matière première.
#
#  ── CE QUI DISTINGUE CETTE CHAÎNE DE CELLE D'AROME, EN UNE LIGNE ─────
#  AROME est limité par le RÉSEAU (7,4 Go, 2 requêtes) ; PI est limité
#  par le QUOTA (2,4 Mo, 300 requêtes). Ce ne sont pas les mêmes
#  contraintes, donc ce ne sont pas les mêmes machines :
#
#      produit A/B (AROME) → runner GitHub : bande passante, 14 Go de
#                            disque, 4 vCores, et AUCUNE clé.
#      PI (ce fichier)     → LE VPS : c'est là que vit la clé
#                            Météo-France, et elle n'en sort pas.
#
#  ⚠️ Ce n'est pas une préférence, c'est écrit dans le message d'erreur
#  de `portail.py` lui-même : « lancer les requêtes portail DEPUIS le
#  VPS, jamais en rapatriant la clé ».
#
#  ── LE BUDGET, MESURÉ ────────────────────────────────────────────────
#      2 paramètres × 6 niveaux × 25 échéances = 300 requêtes
#      ~7 957 octets par champ, constant quel que soit le niveau
#      → ~2,4 Mo par run, ~3,2 min (le quota, pas le réseau, fixe la durée)
#      × 24 runs/jour = 7 200 requêtes et 57 Mo par jour
#
#  ⚠️ **Ce n'est pas le volume qui gêne, c'est l'OCCUPATION PERMANENTE
#  DU QUOTA.** À 95 requêtes/min utilisables, un run de PI occupe la
#  fenêtre 3 minutes sur 60. Le reste du temps elle est libre — mais si
#  un jour une autre chaîne veut le portail, c'est ici qu'il faudra
#  regarder en premier.
#
#  ── L'ORDRE D'ÉCRITURE EST UN CONTRAT ────────────────────────────────
#  Les colonnes sont DÉFINITIVES, la grille est jetable. Les colonnes
#  s'écrivent donc d'ABORD, et un échec de la grille ne fait PAS échouer
#  le run : faire tomber le voyant pour un produit régénéré au réseau
#  suivant apprendrait à l'ignorer. Même contrat que `ingest_colonnes.py`.
#
#  Usage :
#      python3 agrume/ingest_pi.py                     # dernier run publié
#      python3 agrume/ingest_pi.py --run 2026-08-10T16:00:00Z
#      python3 agrume/ingest_pi.py --sans-ecriture --limite-champs 12
#      python3 agrume/ingest_pi.py --tke               # +50 % de requêtes
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

from colonnes import balises_du_domaine  # noqa: E402
from domaine import DOMAINE, GRID_3D  # noqa: E402
from freeze_balises import charger_artefact as charger_balises  # noqa: E402
from grille import (axes_depuis_orographie, index_apres,  # noqa: E402
                    index_apres_purge, verifier_prefixe)
from orographie import charger_artefact, norm_lon  # noqa: E402
from pi import (CLE_INDEX_GRILLE, ECHEANCES_MIN, NIVEAUX_PI,  # noqa: E402
                PREFIXE_GRILLE, RETENTION_RUNS, Abort, ColonnesPI, GrillePI,
                aligner_sur_axes, cles_du_run_colonnes, cles_du_run_grille,
                instants_du_run, json_octets, params_actifs)
from portail import (SERVICE_AROMEPI, CouvertureAbsente,  # noqa: E402
                     ErreurPortail, Portail)

# ⚠️ Alerte de durée. Le budget mesuré est de ~3,2 min ; à 12 min, ce
# n'est pas « un peu long », c'est que le quota est partagé avec autre
# chose ou que le portail rame. Un budget qu'on ne mesure pas n'est pas
# un budget.
ALERTE_MINUTES = 12


def crier(msg=""):
    print(msg, flush=True)


# ══════════════════════════════════════════════════════════════════════
#  Décodage — la seule dépendance eccodes de la chaîne PI
# ══════════════════════════════════════════════════════════════════════
def lire_grib_2d(octets):
    """Un GRIB2 d'UN message → (champ 2D, meta). Lève sinon.

    ⚠️ On exige UN message et un seul. Le WCS ne peut de toute façon
    rendre qu'une couverture 2D (« Slicing on height/time is
    mandatory »), donc deux messages signifieraient que le serveur a
    changé de comportement — et prendre le premier en silence
    laisserait passer ce changement pendant des semaines.
    """
    from eccodes import (codes_get, codes_get_values,
                         codes_grib_new_from_file, codes_release)
    with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as f:
        f.write(octets)
        chemin = f.name
    try:
        with open(chemin, "rb") as f:
            gid = codes_grib_new_from_file(f)
            if gid is None:
                raise Abort("GRIB sans message — le portail a répondu 200 "
                            "avec un corps qui n'est pas un GRIB")
            try:
                meta = dict(
                    Ni=codes_get(gid, "Ni"), Nj=codes_get(gid, "Nj"),
                    lat0=codes_get(gid, "latitudeOfFirstGridPointInDegrees"),
                    lon0=norm_lon(codes_get(
                        gid, "longitudeOfFirstGridPointInDegrees")),
                    di=codes_get(gid, "iDirectionIncrementInDegrees"),
                    dj=codes_get(gid, "jDirectionIncrementInDegrees"),
                    jScan=codes_get(gid, "jScansPositively"))
                vals = codes_get_values(gid).reshape(meta["Nj"], meta["Ni"])
            finally:
                codes_release(gid)
            if codes_grib_new_from_file(f) is not None:
                raise Abort("le GetCoverage a rendu PLUSIEURS messages — le "
                            "serveur a changé de comportement, ne pas "
                            "prendre le premier en silence")
        return vals.astype(np.float64), meta
    finally:
        os.unlink(chemin)


# ══════════════════════════════════════════════════════════════════════
#  Détection du run
# ══════════════════════════════════════════════════════════════════════
def run_complet(portail, champ, run, niveau_sonde=100):
    """⚠️⚠️ LE RUN EST-IL COMPLET, ET PAS SEULEMENT « PUBLIÉ » ?

    **MESURÉ LE 10/08, ET C'EST LE DÉFAUT QUI A FAILLI PASSER.** À
    17:23:51 UTC, le run `2026-08-10T17:00:00Z` répondait au
    `DescribeCoverage` — donc « publié » — et servait ses échéances 0 et
    90 min. **Les échéances 180, 270 et 360 min n'existaient pas.** Les
    runs 16 Z et 15 Z, eux, étaient complets sur les cinq sondes.

    Mieux : en ingérant ce run 17 Z, le compte de champs obtenus MONTAIT
    d'un niveau à l'autre — 6, 6, 6, 6, 8, 8, 8, 9. **PI publie ses
    échéances au fil de l'eau**, à peu près une toutes les 40 s, et
    l'ingestion courait après.

    Conséquences, dans l'ordre de gravité :
    ⛔ Les colonnes sont **DÉFINITIVES**. Archiver un run à 24 %, écrire
       son entrée dans l'index et passer au suivant, c'est perdre 76 %
       d'un run pour toujours — la rétention du portail est de 4,25 jours.
    ⛔ Et le produit serait **DENTELÉ, pas seulement tronqué** : les
       niveaux ingérés en premier auraient moins d'échéances que les
       derniers. Un trou franc se voit ; un trou en escalier ressemble à
       de la donnée.
    ⚠️ Accessoirement, chaque échéance absente coûte quand même une
       requête : 228 requêtes de quota brûlées pour rien.

    On sonde donc **la DERNIÈRE échéance**, celle qui arrive en dernier.
    Une requête de 8 ko décide de 300.

    ⓘ C'est mot pour mot ce que `covered_steps()` fait pour AROME sur le
    miroir S3, et ce que le poller applique déjà : « le dispatch n'a lieu
    que quand TOUS les paquets sont là ». Le portail n'a pas de listing,
    donc on sonde au lieu de lister.
    """
    dernier = instants_du_run(run)[-1]
    try:
        portail.get_coverage(champ, run, dernier, niveau_sonde, DOMAINE)
        return True
    except (ErreurPortail, CouvertureAbsente):
        return False


def dernier_run_utile(portail, champ, deja=(), maintenant=None, recul_max=8,
                      journal=crier):
    """Le run le plus récent qui soit COMPLET et pas déjà archivé.

    Renvoie `(run, recul)`, ou `(None, None)` s'il n'y a rien à faire.

    ⚠️ PI tourne TOUTES LES HEURES (24 runs/jour contre 8 pour AROME) et
    aucune heure de mise à disposition n'est codée en dur — la doc se
    contredit elle-même et ne dit même pas si ses heures sont UTC ou
    légales. On redescend heure par heure.

    ⚠️ On s'arrête au premier run DÉJÀ ARCHIVÉ : tout ce qui est plus
    ancien l'est aussi, et continuer coûterait du quota pour rien.

    ⚠️ `valider_champ` est appelé AVANT par l'appelant : sans lui, un nom
    de champ faux rendrait exactement le même `NoSuchCoverage` qu'un run
    absent, et cette boucle conclurait « rien n'est publié » pour
    toujours.
    """
    t = (maintenant or dt.datetime.now(dt.timezone.utc)).replace(
        minute=0, second=0, microsecond=0)
    for recul in range(recul_max):
        run = (t - dt.timedelta(hours=recul)).strftime("%Y-%m-%dT%H:00:00Z")
        if run in deja:
            journal(f"  ⓘ {run} est déjà archivé — rien de plus récent à "
                    f"prendre.")
            return None, None
        if not portail.existe(champ, run):
            continue
        if not run_complet(portail, champ, run):
            # ⓘ Ce n'est PAS une anomalie : c'est le cas NORMAL dans la
            # première demi-heure d'un run. On le journalise quand même,
            # parce que c'est la mesure de la latence de complétion — et
            # que si ça durait une heure, il faudrait le savoir.
            journal(f"  ⏳ {run} est publié mais INCOMPLET (la dernière "
                    f"échéance manque) — on regarde le précédent.")
            continue
        return run, recul
    raise Abort(f"aucun run PI COMPLET dans les {recul_max} dernières heures. "
                f"⚠️ Si le champ vient d'être validé, ce n'est PAS un nom "
                f"faux : c'est le portail ou la chaîne PI qui est muette.")


# ══════════════════════════════════════════════════════════════════════
#  Le corps
# ══════════════════════════════════════════════════════════════════════
def ingerer(run, params, orog, balises, portail, limite_champs=None,
            journal=crier):
    """Remplit les deux produits. Renvoie (colonnes, grille, bilan)."""
    lats, lons = axes_depuis_orographie(orog)
    ji = [orog.indices(b["lat"], b["lon"]) for b in balises]
    hors = [b["id"] for b, x in zip(balises, ji) if x is None]

    colonnes = ColonnesPI(run, params, balises, ji)
    grille = GrillePI(run, params, lats, lons, orog.z)

    journal(f"  fenêtre : {len(lats)} × {len(lons)} = {len(lats) * len(lons)} "
            f"points · {len(balises)} balises"
            + (f" dont {len(hors)} HORS fenêtre" if hors else ""))

    instants = instants_du_run(run)
    attendus = len(params) * len(NIVEAUX_PI) * len(ECHEANCES_MIN)
    journal(f"  {attendus} champs à demander "
            f"({len(params)} paramètres × {len(NIVEAUX_PI)} niveaux × "
            f"{len(ECHEANCES_MIN)} échéances)")

    faits = 0
    t0 = time.monotonic()
    for param in params:
        axe = portail.axe_vertical(param["wcs"], run)
        for niveau in NIVEAUX_PI:
            for minute, instant in zip(ECHEANCES_MIN, instants):
                if limite_champs is not None and faits >= limite_champs:
                    journal(f"  ⓘ arrêt sur --limite-champs={limite_champs}")
                    return colonnes, grille, _bilan(t0, faits, attendus, hors)
                try:
                    octets = portail.get_coverage(
                        param["wcs"], run, instant, niveau, DOMAINE, axe=axe)
                    champ, meta = lire_grib_2d(octets)
                except (ErreurPortail, CouvertureAbsente, Abort) as e:
                    # ⚠️ UN CHAMP MANQUANT DOIT DISPARAÎTRE, PAS ÊTRE
                    # COMBLÉ. On le note et on continue : c'est exactement
                    # ce qui arrivera au 10 m si PI ne le sert pas, et le
                    # manifeste doit dire lequel manque plutôt que de
                    # publier une valeur inventée.
                    colonnes.manquants.append(
                        dict(param=param["nom"], niveau=niveau, minute=minute,
                             cause=f"{type(e).__name__}: {e}"[:200]))
                    continue
                aligne = aligner_sur_axes(champ, meta, lats, lons)
                grille.poser(param, niveau, minute, aligne)
                colonnes.poser_depuis_champ(param, niveau, minute, aligne)
                faits += 1
            journal(f"    {param['nom']} · {niveau:>4} m : "
                    f"{faits}/{attendus} champs "
                    f"({time.monotonic() - t0:.0f} s)")
    grille.manquants = colonnes.manquants
    return colonnes, grille, _bilan(t0, faits, attendus, hors)


def _bilan(t0, faits, attendus, hors):
    return dict(secondes=round(time.monotonic() - t0, 1), champs=faits,
                champs_attendus=attendus, balises_hors_fenetre=hors)


# ══════════════════════════════════════════════════════════════════════
#  Écriture
# ══════════════════════════════════════════════════════════════════════
def ecrire(colonnes, grille, bilan, journal=crier):
    """Colonnes d'abord (définitif), grille ensuite (sous filet), purge.

    ⚠️ L'ordre EST le contrat. Une grille qui échoue laisse le run VERT ;
    des colonnes qui échouent le font tomber.
    """
    from storage import Storage

    st = Storage("agrume-pi", "AGRUME_BUCKET", "wind-grid")

    # ── 1. Colonnes — DÉFINITIF ───────────────────────────────────────
    c_npz, c_man = cles_du_run_colonnes(colonnes.run)
    extra = dict(bilan=bilan, manquants=colonnes.manquants[:50],
                 nb_manquants=len(colonnes.manquants),
                 # ⓘ La réponse à la question laissée ouverte par la note
                 # d'étape 9 : PI sert-il u/v à 10 m ? Mesurée, pas
                 # supposée.
                 niveau_10m_servi=bool(
                     colonnes.remplissage_par_niveau().get(10, 0) > 0))
    st.put(c_npz, colonnes.npz(), cache_control="public, max-age=31536000",
           content_type="application/octet-stream")
    st.put(c_man, json_octets(colonnes.manifeste(extra)),
           cache_control="public, max-age=31536000",
           content_type="application/json")
    journal(f"  ✅ colonnes écrites : {c_npz} ({colonnes.octets() / 1024:.0f} ko)")

    # ── 2. Grille — JETABLE, sous filet ───────────────────────────────
    try:
        g_npz, g_man = cles_du_run_grille(grille.run)
        st.put(g_npz, grille.npz(), cache_control="public, max-age=3600",
               content_type="application/octet-stream")
        st.put(g_man, json_octets(grille.manifeste(dict(bilan=bilan))),
               cache_control="public, max-age=3600",
               content_type="application/json")
        journal(f"  ✅ grille écrite : {g_npz} "
                f"({grille.octets() / 1e6:.1f} Mo en mémoire)")
        purger(st, grille.run, [g_npz, g_man], journal=journal)
    except Exception as e:                                   # noqa: BLE001
        journal(f"  ⚠️ grille NON écrite ({type(e).__name__}: {e}) — le run "
                f"reste VERT : elle est régénérée au réseau suivant, "
                f"l'archive des colonnes ne l'est pas.")
    st.bilan(log=journal)


def purger(st, run, cles, journal=crier):
    """Index d'abord, suppression ensuite. ⚠️ L'ordre évite les orphelins
    invisibles — c'est la démonstration du §« purge » de `grille.py`, et
    elle s'applique mot pour mot ici."""
    index = st.get_json(CLE_INDEX_GRILLE) or dict(
        produit="AGRUME PI — index des grilles en ligne",
        retention_runs=RETENTION_RUNS, runs=[], restes=[])
    nouveau, a_supprimer = index_apres(index, run, cles,
                                       retention=RETENTION_RUNS)
    # ⚠️ LE GARDE-FOU QUI EMPÊCHE LA PURGE DE DÉBORDER : les colonnes PI
    # sont DÉFINITIVES et vivent dans le même bucket, sous
    # `agrume/pi/colonnes/`. Une purge qui s'y égarerait détruirait une
    # archive irremplaçable — la rétention du portail est de 4,25 jours.
    verifier_prefixe(a_supprimer, prefixe=PREFIXE_GRILLE)
    st.put(CLE_INDEX_GRILLE, json_octets(nouveau),
           cache_control="no-store", content_type="application/json")
    echecs = []
    for cle in a_supprimer:
        try:
            st.delete(cle)
        except Exception:                                    # noqa: BLE001
            echecs.append(cle)
    if a_supprimer:
        journal(f"  purge : {len(a_supprimer) - len(echecs)} clés supprimées"
                + (f", {len(echecs)} échecs (réessayés au run suivant)"
                   if echecs else ""))
        st.put(CLE_INDEX_GRILLE, json_octets(index_apres_purge(nouveau, echecs)),
               cache_control="no-store", content_type="application/json")


def runs_archives():
    """Les runs déjà en ligne, lus dans l'INDEX.

    ⚠️ L'index ne connaît que les runs encore SOUS RÉTENTION (3). Un run
    de plus de 3 heures en est sorti — mais `dernier_run_utile()` ne
    remonte jamais assez loin pour le rencontrer, et le raccourci s'arrête
    au premier run archivé de toute façon. ⓘ Si la rétention descendait
    à 1, il faudrait un second index pour les colonnes définitives.
    """
    from storage import Storage
    st = Storage("agrume-pi", "AGRUME_BUCKET", "wind-grid")
    index = st.get_json(CLE_INDEX_GRILLE) or {}
    return {e.get("run") for e in (index.get("runs") or []) if e.get("run")}


# ══════════════════════════════════════════════════════════════════════
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", default=None,
                   help="run PI visé (ex. 2026-08-10T16:00:00Z) ; "
                        "par défaut le dernier publié")
    p.add_argument("--tke", action="store_true",
                   help="ajoute la TKE : +50 %% de requêtes, inutile à "
                        "l'étape 9, utile au §5.2.c (rotor, rabattant)")
    p.add_argument("--sans-ecriture", action="store_true",
                   help="tout faire sauf écrire sur R2")
    p.add_argument("--limite-champs", type=int, default=None,
                   help="s'arrêter après N champs (mise au point)")
    p.add_argument("--forcer", action="store_true",
                   help="réingérer même si le run est déjà dans l'index")
    p.add_argument("--stations", default=None,
                   help="chemin du stations.json (défaut : artefact figé)")
    p.add_argument("--suspectes", default=None,
                   help="JSON des identifiants à position suspecte — "
                        "⚠️ MARQUÉS dans l'archive, jamais retirés")
    a = p.parse_args(argv)

    debut = time.monotonic()
    params = params_actifs(a.tke)
    crier(f"AGRUME PI — étape 8 bis · {len(params)} paramètres "
          f"({', '.join(x['nom'] for x in params)})")

    # ── Ce qui est déjà archivé, lu UNE fois ──────────────────────────
    # ⚠️ Par l'INDEX, jamais par `exists` : `HeadObject` et `ListObjects`
    # sont facturés Class A chez R2, et `storage.py::_R2.exists` lève
    # plutôt que de les laisser passer. Le timer repasse toutes les 10
    # min ; sonder par `exists` coûterait 144 opérations Class A par jour
    # pour une réponse que l'index donne en une lecture Class B.
    deja = set() if (a.forcer or a.sans_ecriture) else runs_archives()

    portail = Portail(SERVICE_AROMEPI, "0025", journal=lambda m: crier(f"   {m}"))

    # ⚠️ VALIDER LE CHAMP AVANT DE CHERCHER LE RUN. Sans ça, un nom de
    # champ faux et un run non publié rendent EXACTEMENT la même chose —
    # HTTP 404, `NoSuchCoverage` — et la boucle de détection conclurait
    # « rien n'est publié » en attendant pour toujours.
    hier = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    temoins = [(hier + dt.timedelta(hours=h)).strftime("%Y-%m-%dT%H:00:00Z")
               for h in (0, 1, 2)]
    for param in params:
        portail.valider_champ(param["wcs"], temoins)
    crier(f"  ✅ {len(params)} champs validés sur un run témoin")

    if a.run:
        run, recul = a.run, None
        # ⚠️ Même forcé à la main, on vérifie la complétude : archiver un
        # run partiel dans une archive DÉFINITIVE est irréversible.
        if not a.forcer and not run_complet(portail, params[0]["wcs"], run):
            crier(f"  ⛔ {run} est publié mais INCOMPLET — refusé. "
                  f"`--forcer` passe outre, en connaissance de cause.")
            return 1
    else:
        run, recul = dernier_run_utile(portail, params[0]["wcs"], deja=deja)
        if run is None:
            crier(f"  {portail.bilan()}")
            return 0
    crier(f"  run retenu : {run}"
          + (f" (COMPLET, {recul} h de recul)" if recul is not None else ""))

    # ⚠️ `charger_artefact()` rend la PAIRE d'orographies (0,01° et
    # 0,025°), pas une seule. PI vit en 0,025° et rien d'autre : prendre
    # la mauvaise décalerait toute la colonne verticalement, en silence,
    # de 30 m en médiane et jusqu'à 643 m (19 % des balises au-delà de
    # 100 m — mesuré le 10/08).
    paire, man_orog = charger_artefact()
    orog = paire[GRID_3D]
    crier(f"  orographie figée du run {man_orog['run_source']} · "
          f"grille {GRID_3D} retenue (sur {', '.join(sorted(paire))})")

    suspectes = (json.loads(Path(a.suspectes).read_text(encoding="utf-8"))
                 if a.suspectes else [])
    if a.stations:
        stations = json.loads(Path(a.stations).read_text(encoding="utf-8"))
        balises = balises_du_domaine(stations, suspectes)
        origine = f"référentiel {Path(a.stations).name}"
    else:
        figees, man_bal = charger_balises()
        balises = balises_du_domaine(figees, suspectes)
        origine = f"axe figé du {man_bal['ecrit_le'][:10]}"
    if not balises:
        raise Abort("aucune balise ne tombe dans le domaine Nord-Alpes")
    marquees = sum(1 for b in balises if b["position_suspecte"])
    crier(f"  {len(balises)} balises — {origine}"
          + (f", dont {marquees} à position suspecte (marquées, pas "
             f"retirées)" if marquees else ""))

    colonnes, grille, bilan = ingerer(run, params, orog, balises, portail,
                                      limite_champs=a.limite_champs)

    crier()
    crier(f"  champs obtenus : {bilan['champs']}/{bilan['champs_attendus']}")
    crier(f"  remplissage par paramètre : {colonnes.remplissage_par_parametre()}")
    crier(f"  remplissage par niveau    : {colonnes.remplissage_par_niveau()}")
    if colonnes.manquants:
        vus = sorted({(m["param"], m["niveau"]) for m in colonnes.manquants})
        crier(f"  ⚠️ {len(colonnes.manquants)} champs manquants, sur "
              f"{len(vus)} couples (paramètre, niveau) : {vus[:8]}")
    crier(f"  {portail.bilan()}")
    crier(f"  octets reçus : {portail.compteur['octets'] / 1e6:.2f} Mo")

    if a.sans_ecriture:
        crier("  ⓘ --sans-ecriture : rien n'a été écrit.")
    else:
        ecrire(colonnes, grille, bilan)

    minutes = (time.monotonic() - debut) / 60
    crier(f"  durée totale : {minutes:.1f} min")
    if minutes > ALERTE_MINUTES:
        crier(f"  ⚠️ AU-DELÀ DE {ALERTE_MINUTES} min — le budget mesuré est "
              f"de 3,2 min. Ce n'est pas « un peu long », c'est que le "
              f"quota est partagé ou que le portail rame.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
