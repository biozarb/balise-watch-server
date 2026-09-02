#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/sonde_position_l15.py — LA POSITION QUE LA CHAÎNE UTILISE
#                                      VRAIMENT      (Lot L15, 02/09/2026)
#
#  PONCTUELLE, LECTURE SEULE. N'écrit rien, ne publie rien, n'entre dans
#  aucun timer. Elle lit le gel, les référentiels vivants et les archives
#  d'observation, et rend un rapport.
#
#  ═══ CE QU'ELLE DOIT TRANCHER, ET POURQUOI CE N'EST PAS ÉVIDENT ═══
#
#  Le lot L15 demande un garde-fou nocturne qui crie quand la position
#  GELÉE et la position VIVANTE d'une balise s'éloignent, « avec une
#  exigence de PERSISTANCE sur N jours, N à proposer, MESURÉ sur
#  l'historique disponible, pas choisi ». Cette sonde mesure ce qu'il
#  faut pour proposer N — et d'abord si N a un sens.
#
#  ⚠️ LA QUESTION QUI DÉCIDE, ET QUE LE LOT NE POSE PAS : sur quoi la
#  persistance se compte-t-elle ? Le lot L4 a mesuré les 22 « positions
#  transitoires » en opposant `stations.json` au catalogue LIVE de
#  Pioupiou. Mais `collect.py::load_stations` ne rafraîchit son
#  référentiel que si le fichier a plus de `max_age_days = 7` jours :
#  entre deux rafraîchissements, la position vivante NE PEUT PAS bouger,
#  et « N jours d'affilée » ne mesurerait alors que le calendrier du
#  rafraîchissement. C'est mesurable, et c'est mesuré ici (§2).
#
#  ⭐ CE QUE LA SONDE COMPARE, ET POURQUOI C'EST CE COUPLE-LÀ. Ce qui
#  abîme un score n'est pas qu'une balise ait déménagé : c'est que la
#  PRÉVISION et l'OBSERVATION d'une même ligne ne parlent plus du même
#  endroit. AGRUME lit sa colonne à la position GELÉE (`ingest_colonnes`
#  → `index_plats`), l'observation arrive à la position du RÉFÉRENTIEL
#  (`collect.py`, recopiée dans chaque ligne d'archive obs). L'écart
#  entre ces deux positions-là EST le défaut, quelle que soit celle qui
#  a raison. Le catalogue live est un TROISIÈME avis, utile pour
#  arbitrer un cas, jamais pour déclencher l'alarme : personne ne le lit
#  dans la chaîne.
#
#  ⭐ ET LE CRITÈRE EST LE NŒUD, PAS LA DISTANCE — vérifié, pas supposé.
#  `quantification.index_plats` calcule l'indice plat depuis le meta de
#  l'orographie figée : `i = round((lon − lon0)/di)`. Les artefacts des
#  trois domaines portent le MÊME meta national (lat0 55,4 · lon0 −12,0
#  · di 0,01 et 0,025) — la sonde le RELIT et refuse de tourner s'ils
#  divergent. Deux positions dans le même nœud rendent donc exactement
#  la même colonne : le déplacement ne change rien à ce qui est noté.
#  Le vent à 10 m — la grandeur notée — vient de la maille FINE
#  (`001/SP1`) ; le profil vient de la 0,025°. Les deux nœuds sont
#  publiés, la fine décide.
#
#  ═══ USAGE ═══
#
#      # sur le VPS (les archives obs et les référentiels n'existent que là)
#      ssh debian@51.91.102.146
#      cd ~/balise-watch/balise-watch-server/model-verif
#      ~/venv-balise/bin/python3 sonde_position_l15.py --jours 30
#      ~/venv-balise/bin/python3 sonde_position_l15.py --catalogue  # 3e avis
#      ~/venv-balise/bin/python3 sonde_position_l15.py --json
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agrume"))

import score as SC                                          # noqa: E402
from freeze_balises import (ARTEFACT, PIOUPIOU_LIVE,        # noqa: E402
                            REFERENTIELS_RESEAUX,
                            SEUIL_DEPLACEMENT_M, distance_m,
                            depuis_referentiels)

RACINE_DEFAUT = "/var/lib/bw-model-verif"
DATA = pathlib.Path(__file__).resolve().parent.parent / "agrume" / "data"

#: Les N candidats. On ne choisit pas dans cette liste : on publie la
#: courbe complète, et le lot tranche devant les chiffres.
N_CANDIDATS = (1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14)

#: LES DEUX CRITÈRES, mis côte à côte parce qu'ils ne disent pas la même
#: chose et que le lot doit choisir en le sachant.
#:
#: ⚠️ « nœud seul » attrape une balise qui n'a pas bougé : mesuré le
#: 02/09, `pioupiou:1588` change de nœud pour **14 m**, parce que sa
#: position tombe sur un bord de maille. Le vent servi change bel et
#: bien de colonne — mais la balise n'a pas déménagé, et la suspendre du
#: classement pour un tremblement de 14 m coûterait une balise-jour pour
#: rien.
#: ⚠️ « distance seule » attrape l'inverse : 500 m dans la même maille ne
#: changent pas d'un chiffre ce qui est noté (3 des 11 déménagements du
#: 27/08 sont dans ce cas).
#: ⇒ La conjonction est la seule qui décrive le défaut : la balise a
#: VRAIMENT bougé (> SEUIL_DEPLACEMENT_M, la constante du projet) ET le
#: modèle sert désormais une AUTRE colonne.
CRITERES = {
    "noeud": lambda d, n001: n001,
    "noeud_et_seuil": lambda d, n001: n001 and d > SEUIL_DEPLACEMENT_M,
}


# ══════════════════════════════════════════════════════════════════
#  LE NŒUD — la seule chose qui décide si un déplacement compte
# ══════════════════════════════════════════════════════════════════

def metas_grilles(data=DATA):
    """Le meta de chaque maille, RELU dans les artefacts d'orographie.

    ⛔ Ne PAS écrire 55,4 / −12,0 / 0,01 en dur ici. Ces trois nombres
    viennent du GRIB de Météo-France ; le jour où le coin de grille
    bouge, `verifier_grille` (quantification) le voit côté production et
    cette sonde, elle, mentirait sans le savoir. On relit, et on refuse
    de tourner si les domaines ne s'accordent pas.
    """
    metas: dict[str, dict] = {}
    vus = defaultdict(set)
    for f in sorted(data.glob("orographie-*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for grille, v in (d.get("grilles") or {}).items():
            m = v.get("meta") or {}
            cle = (m.get("lat0"), m.get("lon0"), m.get("di"), m.get("dj"),
                   m.get("Ni"), m.get("Nj"), m.get("jScan"))
            vus[grille].add(cle)
            metas.setdefault(grille, m)
    for grille, cles in vus.items():
        if len(cles) > 1:
            raise SystemExit(
                f"⛔ les artefacts d'orographie ne s'accordent pas sur le "
                f"meta de la grille {grille} : {cles}. Le nœud n'est pas "
                f"définissable, la sonde s'arrête.")
    return metas


def noeud(meta, lat, lon):
    """(i, j) du plus proche voisin — LA MÊME arithmétique que
    `quantification.index_plats`, recopiée ici pour une seule raison :
    `index_plats` veut numpy et une liste de balises, alors qu'on
    l'appelle ici deux fois par balise sur deux mailles. La formule est
    identique, et `test_sonde_position_l15` la confronte à
    `index_plats` sur des cas réels pour que la copie ne dérive pas."""
    i = round((lon - meta["lon0"]) / meta["di"])
    j = (round((meta["lat0"] - lat) / meta["dj"]) if meta.get("jScan") != 1
         else round((lat - meta["lat0"]) / meta["dj"]))
    return (i, j)


# ══════════════════════════════════════════════════════════════════
#  LES TROIS SOURCES
# ══════════════════════════════════════════════════════════════════

def charger_gel(chemin=ARTEFACT):
    d = json.loads(pathlib.Path(chemin).read_text(encoding="utf-8"))
    gel = {}
    for b in d["balises"]:
        gel[(b.get("source") or "pioupiou", str(b["id"]))] = b
    return d, gel


def charger_vivant(racine):
    """Le référentiel que la chaîne utilise — celui que `collect.py`
    écrit et que chaque ligne d'archive obs recopie."""
    vivant = {}
    for c in depuis_referentiels(racine):
        vivant[(c["source"], str(c["id"]))] = c
    return vivant


def catalogue_live():
    """Le TROISIÈME avis. Personne ne le lit dans la chaîne : il ne
    déclenche rien, il arbitre."""
    req = urllib.request.Request(
        PIOUPIOU_LIVE, headers={"User-Agent": "balise-watch-sonde-l15/1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        payload = json.loads(r.read().decode("utf-8"))
    out = {}
    for d in payload.get("data", []):
        loc = d.get("location") or {}
        if loc.get("latitude") is None or loc.get("longitude") is None:
            continue
        out[("pioupiou", str(d["id"]))] = (round(float(loc["latitude"]), 4),
                                           round(float(loc["longitude"]), 4))
    return out


def positions_par_jour(root, fin, jours, storage=None, crier=print):
    """{jour: {(source, id): (lat, lon)}} — la position que la chaîne a
    RÉELLEMENT utilisée ce jour-là, relue dans les lignes d'archive.

    ⚠️ Une balise peut apparaître plusieurs fois dans une journée (une
    ligne par réseau republiant le même capteur, cf. L16). On garde la
    PREMIÈRE vue et on compte les désaccords intra-journée : deux
    positions différentes sous la même clé le même jour seraient un
    défaut d'un autre genre, et il vaut mieux le voir que le moyenner.
    """
    par_jour, desaccords = {}, 0
    for k in range(jours):
        d = fin - timedelta(days=k)
        vues = {}
        for r in SC.all_obs_rows(root, d, storage):
            lat, lon = r.get("lat"), r.get("lon")
            if lat is None or lon is None:
                continue
            cle = (r.get("source") or "pioupiou", str(r.get("station_id")))
            p = (round(float(lat), 4), round(float(lon), 4))
            if cle in vues:
                if vues[cle] != p:
                    desaccords += 1
                continue
            vues[cle] = p
        if vues:
            par_jour[d.strftime("%Y-%m-%d")] = vues
        crier(f"  · {d:%Y-%m-%d} : {len(vues)} balises vues")
    return par_jour, desaccords


# ══════════════════════════════════════════════════════════════════
#  LA MESURE
# ══════════════════════════════════════════════════════════════════

def ecart(gel_b, pos, metas):
    """Ce qui sépare la position gelée d'une position vivante."""
    d = distance_m((gel_b["lat"], gel_b["lon"]), pos)
    n001 = noeud(metas["001"], *pos) != noeud(metas["001"], gel_b["lat"],
                                              gel_b["lon"])
    n0025 = noeud(metas["0025"], *pos) != noeud(metas["0025"], gel_b["lat"],
                                                gel_b["lon"])
    return d, n001, n0025


def sonder(root, fin, jours, storage=None, avec_catalogue=False, crier=print):
    metas = metas_grilles()
    entete, gel = charger_gel()
    vivant = charger_vivant(root)
    crier(f"▶ archives obs ({jours} j, fin {fin:%Y-%m-%d})")
    par_jour, desaccords = positions_par_jour(root, fin, jours, storage, crier)
    jours_tries = sorted(par_jour)

    # ── §1 l'état du jour : gel ↔ référentiel vivant ──────────────────
    aujourdhui = []
    for cle, b in gel.items():
        v = vivant.get(cle)
        if v is None:
            continue
        d, n001, n0025 = ecart(b, (v["lat"], v["lon"]), metas)
        if d > SEUIL_DEPLACEMENT_M or n001:
            aujourdhui.append(dict(source=cle[0], id=cle[1],
                                   name=b.get("name") or v.get("name") or "",
                                   d=round(d), noeud_001=n001,
                                   noeud_0025=n0025,
                                   vue_le=b.get("vue_le")))
    aujourdhui.sort(key=lambda x: -x["d"])

    # ── §2 le référentiel bouge-t-il, et à quel rythme ? ──────────────
    #  Sans cette mesure, « N jours d'affilée » pourrait n'être qu'une
    #  façon compliquée de dire « le rafraîchissement n'a pas encore eu
    #  lieu ». On compte les jours où la position vue CHANGE.
    changements = defaultdict(list)     # cle -> [(jour, d_metres)]
    for a, b in zip(jours_tries, jours_tries[1:]):
        va, vb = par_jour[a], par_jour[b]
        for cle, pa in va.items():
            pb = vb.get(cle)
            if pb is None or pb == pa:
                continue
            changements[cle].append((b, round(distance_m(pa, pb))))
    jours_avec_changement = Counter()
    for cle, lst in changements.items():
        for j, _d in lst:
            jours_avec_changement[j] += 1

    # ── §3 la persistance : depuis combien de jours ça diverge ────────
    #  Pour chaque balise et chaque jour d'archive, « la position vue ce
    #  jour-là déclenche-t-elle le critère ? ». La longueur du run qui se
    #  termine au dernier jour EST la persistance.
    def run_final(flags):
        """Nombre de jours VUS et divergents d'affilée jusqu'au dernier
        jour vu. Un jour non vu n'interrompt pas le run — il ne dit rien.
        ⚠️ Arbitrage écrit : traiter une absence comme une non-divergence
        remettrait le compteur à zéro chaque fois qu'une balise passe une
        nuit hors ligne, et une balise déménagée est justement une balise
        qui s'éteint souvent."""
        n = 0
        for f in reversed(flags):
            if f is None:
                continue
            if not f:
                break
            n += 1
        return n

    dernier = jours_tries[-1] if jours_tries else None
    vus_dernier = set(par_jour.get(dernier, {}))
    mesures = {}
    for nom, crit in CRITERES.items():
        series = {}
        for cle, b in gel.items():
            flags = []
            for j in jours_tries:
                p = par_jour[j].get(cle)
                if p is None:
                    flags.append(None)          # pas vue : ni oui ni non
                    continue
                d, n001, _ = ecart(b, p, metas)
                flags.append(bool(crit(d, n001)))
            if any(f for f in flags if f):
                series[cle] = flags
        persistances = {cle: run_final(f) for cle, f in series.items()}

        # ── §4 les allers-retours : la fausse alarme, mesurée ─────────
        #  Une balise qui diverge, revient, rediverge est le cas que la
        #  persistance doit rejeter. On mesure la durée de leurs épisodes
        #  REFERMÉS : c'est cette distribution qui donne N. Le dernier
        #  épisode n'y entre pas s'il touche le bord — il n'est pas
        #  revenu, on ne sait pas encore s'il reviendra.
        episodes = []
        for cle, flags in series.items():
            vus = [f for f in flags if f is not None]
            courant = 0
            for f in vus:
                if f:
                    courant += 1
                else:
                    if courant:
                        episodes.append((cle, courant))
                    courant = 0

        courbe = {}
        for N in N_CANDIDATS:
            retenues = [cle for cle, n in persistances.items() if n >= N]
            courbe[N] = dict(
                retenues=len(retenues),
                faux_positifs_historiques=sum(
                    1 for _c, lg in episodes if lg >= N),
                suspendues=len([c for c in retenues if c in vus_dernier]),
                balises=sorted(f"{s_}:{i_}" for s_, i_ in retenues))
        mesures[nom] = dict(
            persistances={f"{s_}:{i_}": n
                          for (s_, i_), n in sorted(persistances.items(),
                                                    key=lambda x: -x[1])},
            episodes=[(f"{s_}:{i_}", n) for (s_, i_), n in episodes],
            courbe=courbe)

    cata = {}
    if avec_catalogue:
        crier("▶ catalogue live Pioupiou (3e avis)")
        try:
            live = catalogue_live()
        except Exception as e:                       # noqa: BLE001
            crier(f"  ⚠️ catalogue injoignable : {e}")
            live = {}
        for x in aujourdhui:
            cle = (x["source"], x["id"])
            p = live.get(cle)
            if p is None:
                continue
            b = gel[cle]
            v = vivant[cle]
            dg = round(distance_m((b["lat"], b["lon"]), p))
            dv = round(distance_m((v["lat"], v["lon"]), p))
            # ⭐ LE TROISIÈME AVIS NE SERT PAS À DÉCLENCHER, IL SERT À
            # DÉSIGNER LE FAUTIF. Deux sources qui se contredisent ne
            # disent pas laquelle a tort ; la troisième, oui — et le
            # verdict change ce qu'on écrira dans `position_note`, donc
            # ce que Yann aura à trancher balise par balise.
            if dg <= SEUIL_DEPLACEMENT_M < dv:
                verdict = "REFERENTIEL FAUX (le gel a raison)"
            elif dv <= SEUIL_DEPLACEMENT_M < dg:
                verdict = "DEMENAGEMENT (le gel est perime)"
            elif dg > SEUIL_DEPLACEMENT_M and dv > SEUIL_DEPLACEMENT_M:
                verdict = "LES TROIS SE CONTREDISENT"
            else:
                verdict = "les trois d'accord (ecart sous le seuil)"
            cata[f"{cle[0]}:{cle[1]}"] = dict(
                gel_cata=dg, vivant_cata=dv, verdict=verdict,
                gel_vivant=x["d"], noeud_001=x["noeud_001"])

    return dict(
        gel=dict(ecrit_le=entete.get("ecrit_le"), n=entete.get("n"),
                 par_source=dict(Counter(s for s, _ in gel))),
        vivant=dict(n=len(vivant),
                    par_source=dict(Counter(s for s, _ in vivant))),
        archives=dict(jours=jours_tries, n_jours=len(jours_tries),
                      desaccords_intra_jour=desaccords),
        aujourdhui=aujourdhui,
        changements=dict(
            n_balises=len(changements),
            n_changements=sum(len(v) for v in changements.values()),
            par_jour=dict(sorted(jours_avec_changement.items())),
            plus_grands=sorted(
                ((f"{s}:{i}", j, d) for (s, i), lst in changements.items()
                 for j, d in lst), key=lambda x: -x[2])[:15]),
        mesures=mesures, derniere_nuit=dernier, catalogue=cata)


# ══════════════════════════════════════════════════════════════════
#  LE RAPPORT
# ══════════════════════════════════════════════════════════════════

def rapport(r):
    L = []
    A = L.append
    A("RAPPORT — la POSITION des balises (lot L15) — "
      f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} Z")
    A("")
    A("LECTURE SEULE : aucun fichier écrit, aucun gel rejoué, aucun SQL.")
    A("Les fonctions appelées sont celles du projet (freeze_balises."
      "distance_m,")
    A("depuis_referentiels, SEUIL_DEPLACEMENT_M ; score.all_obs_rows ; le "
      "meta")
    A("des grilles relu dans les artefacts d'orographie).")
    A("")
    g, v = r["gel"], r["vivant"]
    A(f"gel      : {g['n']} balises, figé le {g['ecrit_le']}")
    A(f"           {g['par_source']}")
    A(f"vivant   : {v['n']} points aux référentiels de collect.py")
    A(f"           {v['par_source']}")
    a = r["archives"]
    A(f"archives : {a['n_jours']} jours d'obs, du {a['jours'][0]} au "
      f"{a['jours'][-1]}")
    if a["desaccords_intra_jour"]:
        A(f"           ⚠️ {a['desaccords_intra_jour']} désaccords de position "
          f"DANS une même journée")
    A("")
    A("=== §1 — L'ÉTAT DU JOUR : gel ↔ référentiel vivant ===")
    A("")
    aj = r["aujourdhui"]
    n_noeud = sum(1 for x in aj if x["noeud_001"])
    n_0025 = sum(1 for x in aj if x["noeud_0025"])
    A(f"{len(aj)} balise(s) au-delà de {SEUIL_DEPLACEMENT_M:.0f} m ou "
      f"changeant de nœud")
    A(f"   dont {n_noeud} changent le nœud 0,01° (le vent à 10 m noté "
      f"change de colonne)")
    A(f"   dont {n_0025} changent aussi le nœud 0,025° (le profil change)")
    n_conj = sum(1 for x in aj if x["noeud_001"]
                 and x["d"] > SEUIL_DEPLACEMENT_M)
    A(f"   dont {n_conj} changent le nœud 0,01° ET ont bougé de plus de "
      f"{SEUIL_DEPLACEMENT_M:.0f} m")
    A(f"   ⓘ {n_noeud - n_conj} changent de nœud SANS avoir bougé de "
      f"{SEUIL_DEPLACEMENT_M:.0f} m : leur position tombe sur un bord de "
      f"maille.")
    A("")
    A(f"{'id':>22}  {'m':>7}  {'0,01':>5} {'0,025':>5}  {'gelée le':>10}  nom")
    for x in aj[:40]:
        A(f"{x['source']+':'+x['id']:>22}  {x['d']:>7}  "
          f"{'CHANGE' if x['noeud_001'] else '  même':>5} "
          f"{'CHANGE' if x['noeud_0025'] else '  même':>5}  "
          f"{str(x['vue_le']):>10}  {x['name'][:34]}")
    if len(aj) > 40:
        A(f"   … {len(aj) - 40} de plus")
    A("")
    A("=== §2 — LE RÉFÉRENTIEL BOUGE-T-IL, ET QUAND ? ===")
    A("")
    c = r["changements"]
    A(f"{c['n_balises']} balise(s) ont changé de position au moins une fois "
      f"dans les archives")
    A(f"{c['n_changements']} changement(s) en tout")
    A("jours où au moins une position a changé :")
    for j, n in c["par_jour"].items():
        A(f"   {j} : {n:>5} balise(s)")
    if not c["par_jour"]:
        A("   AUCUN — la position vue n'a pas bougé d'un mètre sur la "
          "fenêtre.")
    A("")
    A("les plus grands sauts (id, jour, mètres) :")
    for i, j, d in c["plus_grands"]:
        A(f"   {i:>22}  {j}  {d:>9}")
    A("")
    A("=== §3 — LA PERSISTANCE, ET LA COURBE N ===")
    A("")
    A("Deux critères, côte à côte. « nœud » = la colonne servie change ;")
    A("« nœud+seuil » = elle change ET la balise a vraiment bougé de plus")
    A(f"de {SEUIL_DEPLACEMENT_M:.0f} m. Un épisode REFERMÉ (la balise est "
      f"revenue) est une")
    A("fausse alarme qu'un N bien choisi doit rejeter.")
    for nom, m in r["mesures"].items():
        A("")
        A(f"--- critère « {nom} » ---")
        A(f"{len(m['persistances'])} balise(s) ont déclenché au moins un "
          f"jour · {len(m['episodes'])} épisode(s) refermé(s)")
        if m["episodes"]:
            lg = sorted(n for _c, n in m["episodes"])
            A(f"   durée des épisodes refermés : min {lg[0]} j · médiane "
              f"{lg[len(lg)//2]} j · max {lg[-1]} j")
        A("")
        A(f"{'N':>4}  {'retenues':>9}  {'épisodes refermés >= N':>23}"
          f"  {'suspendues la dernière nuit':>28}")
        for N in N_CANDIDATS:
            k = m["courbe"][N]
            A(f"{N:>4}  {k['retenues']:>9}  "
              f"{k['faux_positifs_historiques']:>23}  {k['suspendues']:>28}")
        A("")
        A("   persistance par balise (jours d'affilée jusqu'au dernier "
          "jour vu) :")
        ligne = []
        for i, n in m["persistances"].items():
            ligne.append(f"{i}={n}")
        for k in range(0, len(ligne), 5):
            A("     " + "  ".join(ligne[k:k + 5]))
    A("")
    A(f"(« suspendues la dernière nuit » = balises retenues ET vues le "
      f"{r['derniere_nuit']})")
    A("")
    if r["catalogue"]:
        A("=== §4 — LE TROISIÈME AVIS, ET QUI A TORT ===")
        A("")
        A("Le catalogue live de Pioupiou n'est lu par AUCUNE chaîne : il ne")
        A("déclenche rien. Il sert à dire LAQUELLE des deux positions est")
        A("fausse — ce que deux sources qui se contredisent ne peuvent pas")
        A("dire, et ce que `position_note` devra écrire.")
        A("")
        pers = r["mesures"]["noeud_et_seuil"]["persistances"]
        A(f"{'id':>22}  {'gel↔viv':>8} {'gel↔cata':>9} {'viv↔cata':>9}"
          f"  {'nœud':>6} {'pers.':>5}  verdict")
        ordre = {"DEMENAGEMENT (le gel est perime)": 0,
                 "LES TROIS SE CONTREDISENT": 1,
                 "REFERENTIEL FAUX (le gel a raison)": 2}
        for i, d in sorted(r["catalogue"].items(),
                           key=lambda x: (ordre.get(x[1]["verdict"], 9),
                                          -x[1]["gel_cata"])):
            A(f"{i:>22}  {d['gel_vivant']:>8} {d['gel_cata']:>9} "
              f"{d['vivant_cata']:>9}  "
              f"{'CHANGE' if d['noeud_001'] else 'même':>6} "
              f"{pers.get(i, 0):>5}  {d['verdict']}")
        A("")
        compte = Counter(d["verdict"] for d in r["catalogue"].values())
        for k, n in compte.most_common():
            A(f"   {n:>3}  {k}")
        A("")
        A("(« pers. » = jours d'affilée de divergence, critère nœud+seuil)")
        A("")
    return "\n".join(L)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", default=RACINE_DEFAUT)
    p.add_argument("--fin", default=None, help="dernier jour (YYYY-MM-DD)")
    p.add_argument("--jours", type=int, default=30)
    p.add_argument("--catalogue", action="store_true",
                   help="interroger le catalogue live Pioupiou (3e avis)")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    fin = (datetime.strptime(a.fin, "%Y-%m-%d") if a.fin
           else datetime.now(timezone.utc).replace(tzinfo=None)
           - timedelta(days=1))
    fin = fin.replace(hour=0, minute=0, second=0, microsecond=0)
    crier = (lambda *_a, **_k: None) if a.json else print

    storage = None
    try:
        import storage as ST                        # noqa: PLC0415
        storage = ST.make_storage()
    except Exception:                               # noqa: BLE001
        storage = None                              # archives locales seules

    r = sonder(pathlib.Path(a.root), fin, a.jours, storage=storage,
               avec_catalogue=a.catalogue, crier=crier)
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json
          else rapport(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
