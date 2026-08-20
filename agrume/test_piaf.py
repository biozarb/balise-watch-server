#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/test_piaf.py — le banc de la pluie à venir       (20/08/2026)
#
#  ⛔ Il ne vérifie PAS que le code « marche ». Il vérifie les SEPT
#  façons qu'il aurait de casser en silence — celles qui ne lèvent
#  jamais, ne rougissent rien, et se lisent comme de la météo :
#
#   1. DÉCALER LE RUBAN DE 5 MINUTES, parce que l'instant nommé par le
#      producteur est la FIN de la tranche et pas son début ;
#   2. PERDRE UNE CELLULE D'AVERSE à la réduction du calque — une
#      décimation ou une moyenne l'effacent, et il ne reste rien à
#      l'écran pour dire qu'il pleut ;
#   3. COMPTER UNE HEURE INCOMPLÈTE comme entière : 40 minutes de pluie
#      affichées sous une colonne intitulée « heure » ;
#   4. DÉCALER LA FENÊTRE D'UN DOMAINE, ou la publier tronquée quand la
#      boîte ne le contient pas — une carte juste, posée à côté du
#      terrain ;
#   5. FAIRE DIVERGER LES DEUX JEUX : le calque et la coupe montrant
#      deux pluies différentes au même instant ;
#   6. LAISSER PASSER UNE VALEUR ABSURDE, parce que le plafond hérité de
#      `precipitation` (2 000 mm, taillé pour 51 h de cumul) ne dit rien
#      d'une tranche de 5 minutes ;
#   7. PURGER HORS DU PRÉFIXE, ou faire avancer `dernier` sur une
#      écriture partielle.
#
#  ⚠️ Sans réseau, sans clé, sans R2. Le magasin est un dictionnaire.
#      python3 agrume/test_piaf.py
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

import piaf  # noqa: E402
from piaf import (Abort, Passe, axes_boite, cles_de_la_passe,  # noqa: E402
                  echeances, fenetre_domaine, heures_entieres,
                  passes_candidates, reduire_max, verifier_parite)
from quantification import PARAM_PLUIE_IMMEDIATE, quantifier  # noqa: E402

_OK = _KO = 0


def verifie(condition, quoi, detail=""):
    global _OK, _KO
    if condition:
        _OK += 1
        print(f"  ✅ {quoi}")
    else:
        _KO += 1
        print(f"  ⛔ {quoi}" + (f"\n       {detail}" if detail else ""))


def leve(fn, quoi, motif=None):
    global _OK, _KO
    try:
        fn()
    except Abort as e:
        if motif and motif not in str(e):
            _KO += 1
            print(f"  ⛔ {quoi} — lève, mais pas pour la bonne raison :\n"
                  f"       {e}")
            return
        _OK += 1
        print(f"  ✅ {quoi}")
        return
    except Exception as e:                                  # noqa: BLE001
        _KO += 1
        print(f"  ⛔ {quoi} — lève {type(e).__name__} et non Abort : {e}")
        return
    _KO += 1
    print(f"  ⛔ {quoi} — N'A PAS LEVÉ")


# ══════════════════════════════════════════════════════════════════════
#  1. LE TEMPS
# ══════════════════════════════════════════════════════════════════════
def banc_temps():
    print("\n── 1. le ruban, et le décalage de 5 minutes ──")
    ech = echeances("2026-08-20T05:50:00Z")
    verifie(len(ech) == piaf.NB_ECHEANCES,
            f"{piaf.NB_ECHEANCES} tranches", f"{len(ech)}")
    # ⛔ Mesuré sur les octets : l'échéance demandée à passe + 5 min porte
    # `stepRange = 0m-5m`. La tranche COMMENCE à la passe.
    verifie(ech[0]["debut"] == "2026-08-20T05:50:00Z"
            and ech[0]["fin"] == "2026-08-20T05:55:00Z"
            and ech[0]["instant_demande"] == ech[0]["fin"],
            "la première tranche couvre ]passe, passe+5] et se DEMANDE "
            "par sa fin", str(ech[0]))
    verifie(ech[-1]["fin_min"] == piaf.HORIZON_MIN
            and ech[-1]["fin"] == "2026-08-20T09:05:00Z",
            f"la dernière tranche finit à +{piaf.HORIZON_MIN} min",
            str(ech[-1]))
    verifie(all(b["debut_min"] == a["fin_min"] for a, b in zip(ech, ech[1:])),
            "les tranches sont JOINTIVES et disjointes — c'est ce qui rend "
            "leur somme exacte")

    print("\n── 2. les heures rondes entières ──")
    for passe, attendu in (("2026-08-20T06:00:00Z", 3),
                           ("2026-08-20T05:55:00Z", 3),
                           ("2026-08-20T06:05:00Z", 2),
                           ("2026-08-20T06:35:00Z", 2)):
        h = heures_entieres(passe)
        t0 = piaf._instant(passe)
        bornes_ok = all(
            e["fin_min"] <= piaf.HORIZON_MIN
            and e["fin_min"] - e["debut_min"] == 60
            and len(e["rangs"]) == 12
            and piaf._instant(e["heure"]).minute == 0
            for e in h)
        verifie(len(h) == attendu and bornes_ok,
                f"passe {passe[11:16]} → {attendu} heure(s) entière(s)",
                f"obtenu {len(h)} : {[e['heure'] for e in h]}")
        # ⛔ Le contrôle qui compte : les 12 rangs désignés doivent
        # RECOUVRIR EXACTEMENT l'heure, sans déborder ni laisser de trou.
        ech = echeances(passe)
        for e in h:
            tr = [ech[r] for r in e["rangs"]]
            verifie(tr[0]["debut"] == e["heure"]
                    and tr[-1]["fin_min"] == e["fin_min"]
                    and all(b["debut_min"] == a["fin_min"]
                            for a, b in zip(tr, tr[1:])),
                    f"  {e['heure'][11:16]} : les 12 rangs pavent l'heure "
                    f"exactement",
                    f"{tr[0]['debut']} → {tr[-1]['fin']}")

    print("\n── 3. les passes candidates ──")
    import datetime as dt
    t = dt.datetime(2026, 8, 20, 7, 52, 13, tzinfo=dt.timezone.utc)
    c = passes_candidates(maintenant=t)
    verifie(c[0] == "2026-08-20T07:40:00Z",
            "la première candidate recule de la latence mesurée (12,6 min) "
            "et tombe sur un multiple de 5 min", c[0])
    verifie(all(piaf._instant(x).minute % piaf.PAS_MIN == 0
                and piaf._instant(x).second == 0 for x in c),
            "toutes les candidates sont des multiples de 5 min pile")
    verifie(c == sorted(c, reverse=True),
            "elles vont de la plus FRAÎCHE à la plus ancienne — sans quoi "
            "l'arrêt sur « déjà ingérée » réingérerait du passé")


# ══════════════════════════════════════════════════════════════════════
#  2. LA RÉDUCTION DU CALQUE — l'averse qui disparaît
# ══════════════════════════════════════════════════════════════════════
def banc_reduction():
    print("\n── 4. le calque : maximum, et pourquoi pas les deux autres ──")
    g = np.zeros((1, 8, 8), dtype=np.float32)
    # Une cellule d'averse d'UNE maille, posée en (3, 5) : indices
    # IMPAIRS tous les deux, donc exactement ce qu'une décimation
    # « un point sur deux » saute.
    g[0, 3, 5] = 9.0
    red = reduire_max(g)
    verifie(red.shape == (1, 4, 4), "la grille réduite fait nj/2 × ni/2",
            str(red.shape))
    verifie(float(red[0, 1, 2]) == 9.0,
            "⛔ l'averse d'UNE maille survit à la réduction, à sa place",
            str(red[0]))
    verifie(float(red.sum()) == 9.0,
            "et elle n'est pas dupliquée sur les blocs voisins")
    # Les deux règles écartées, mesurées ici pour que le choix reste
    # lisible dans dix mois.
    decime = g[:, ::2, ::2]
    moyenne = g.reshape(1, 4, 2, 4, 2).mean(axis=(2, 4))
    verifie(float(decime.max()) == 0.0,
            "⛔ une DÉCIMATION aurait effacé l'averse : max 0,0 mm sur une "
            "maille qui en portait 9")
    verifie(abs(float(moyenne.max()) - 2.25) < 1e-6,
            "⛔ une MOYENNE l'aurait ramenée de 9,0 à 2,25 mm — invisible à "
            "l'écran alors qu'elle mouille", str(moyenne.max()))
    # Le NaN ne doit pas empoisonner le bloc.
    g2 = np.array([[[np.nan, 2.0], [1.0, np.nan]]], dtype=np.float32)
    verifie(float(reduire_max(g2)[0, 0, 0]) == 2.0,
            "un NaN dans le bloc n'empoisonne pas le maximum")
    g3 = np.full((1, 2, 2), np.nan, dtype=np.float32)
    verifie(not np.isfinite(reduire_max(g3)[0, 0, 0]),
            "un bloc ENTIÈREMENT non fini reste non fini — un trou reste "
            "un trou, il ne devient pas zéro")
    leve(lambda: reduire_max(np.zeros((1, 7, 8), dtype=np.float32)),
         "un compte IMPAIR de lignes est refusé", "divisible")


# ══════════════════════════════════════════════════════════════════════
#  3. LA GÉOMÉTRIE
# ══════════════════════════════════════════════════════════════════════
def banc_geometrie():
    print("\n── 5. la boîte, sa parité, et les domaines qui débordent ──")
    lats, lons = axes_boite()
    verifie(abs(float(lats[0]) - piaf.BOITE["latmax"]) < 1e-4
            and abs(float(lats[-1]) - piaf.BOITE["latmin"]) < 1e-4,
            "les latitudes vont du NORD au sud et touchent les deux bornes",
            f"{lats[0]} → {lats[-1]}")
    verifie(abs(float(lons[0]) - piaf.BOITE["lonmin"]) < 1e-4
            and abs(float(lons[-1]) - piaf.BOITE["lonmax"]) < 1e-4,
            "les longitudes vont d'ouest en est et touchent les deux bornes")
    verifie(len(lats) % 2 == 0 and len(lons) % 2 == 0,
            f"les deux comptes sont PAIRS ({len(lats)} × {len(lons)}) — "
            "sinon la dernière maille du calque couvrirait deux fois moins "
            "de terrain, en silence")
    verifie(verifier_parite() is True, "`verifier_parite` accepte la boîte")
    leve(lambda: verifier_parite(dict(piaf.BOITE, latmax=50.00)),
         "une boîte à compte impair est REFUSÉE", "IMPAIR")

    # ⛔ LE DÉFAUT DU CADRAGE, transformé en banc. A19 écrivait
    # `lonmin = −1,0` ; le domaine Pyrénées descend à −1,80.
    a19_ecrit = dict(latmin=42.0, latmax=50.0, lonmin=-1.0, lonmax=9.5)
    leve(lambda: fenetre_domaine("pyrenees", a19_ecrit),
         "⛔ la boîte A19 TELLE QU'ÉCRITE est refusée : elle tronque les "
         "Pyrénées de 80 colonnes", "déborde")
    for nom in piaf.DOMAINES_COUPE:
        j0, j1, i0, i1 = fenetre_domaine(nom)
        d = piaf.DOMAINES[nom]
        nj, ni = j1 - j0 + 1, i1 - i0 + 1
        attendu_j = round((d["latmax"] - d["latmin"]) / piaf.PAS_DEG) + 1
        attendu_i = round((d["lonmax"] - d["lonmin"]) / piaf.PAS_DEG) + 1
        verifie((nj, ni) == (attendu_j, attendu_i),
                f"{nom} : fenêtre {nj} × {ni} conforme à ses bornes",
                f"attendu {attendu_j} × {attendu_i}")
        verifie(abs(float(lats[j0]) - d["latmax"]) < 1e-4
                and abs(float(lons[i0]) - d["lonmin"]) < 1e-4,
                f"{nom} : le coin nord-ouest tombe PILE sur la borne du "
                f"domaine — une maille d'écart vaut ~750 m",
                f"{lats[j0]} / {lons[i0]}")


# ══════════════════════════════════════════════════════════════════════
#  4. LA QUANTIFICATION — le plafond qui ne peut pas être celui d'AROME
# ══════════════════════════════════════════════════════════════════════
def banc_quantification():
    print("\n── 6. la sentinelle, et le plafond de 5 minutes ──")
    from quantification import PLAFOND_PHYSIQUE
    verifie(PLAFOND_PHYSIQUE["pluie_5min"] < PLAFOND_PHYSIQUE["precipitation"],
            "le plafond de la tranche de 5 min est BIEN plus bas que celui "
            "du cumul de run (2 000 mm, taillé pour 51 h)",
            f"{PLAFOND_PHYSIQUE['pluie_5min']} vs "
            f"{PLAFOND_PHYSIQUE['precipitation']}")
    a = np.array([0.0, 0.15, 11.16, 9999.0, 1500.0, np.nan])
    q = quantifier(a, PARAM_PLUIE_IMMEDIATE).astype(np.float32)
    verifie(float(q[0]) == 0.0 and abs(float(q[2]) - 11.16) < 0.01,
            "les valeurs réelles traversent (0,15 et 11,16 mm — le maximum "
            "mesuré le 20/08)", str(q))
    verifie(not np.isfinite(q[3]),
            "⛔ la sentinelle 9999 devient NaN, jamais 0 — zéro serait une "
            "valeur de pluie parfaitement crédible")
    verifie(not np.isfinite(q[4]),
            "⛔ 1 500 mm en 5 minutes est REFUSÉ ; avec le plafond hérité "
            "d'AROME il serait passé, et une erreur de facteur 1 000 "
            "s'afficherait comme un déluge plausible")
    verifie(not np.isfinite(q[5]), "un NaN d'entrée reste un NaN")
    # ⛔ La précision : la quantification ne doit pas coûter plus que
    # l'affichage ne montre.
    from quantification import erreur_quantification
    reel = np.linspace(0.0, 15.0, 20000)
    err = erreur_quantification(reel, PARAM_PLUIE_IMMEDIATE)
    verifie(err < 0.01,
            f"l'erreur de quantification vaut {err:.4f} mm sur 0 → 15 mm — "
            f"très en dessous de ce qu'un écran distingue")


# ══════════════════════════════════════════════════════════════════════
#  5. LES DEUX JEUX — décodés PAR LES RÈGLES DU MANIFESTE
# ══════════════════════════════════════════════════════════════════════
#: ⚠️ Une boîte de banc, minuscule. La vraie fait 802 × 1136 × 39, soit
#: 142 Mo de float32 — un banc n'a pas à peser ça pour prouver une
#: disposition d'octets.
BOITE_BANC = dict(latmin=44.00, latmax=44.09, lonmin=5.00, lonmax=5.09)
DOMAINE_BANC = dict(latmin=44.02, latmax=44.06, lonmin=5.01, lonmax=5.05)


def _passe_de_banc():
    piaf.DOMAINES = dict(piaf.DOMAINES, banc=DOMAINE_BANC)
    lats, lons = axes_boite(BOITE_BANC)
    rng = np.random.default_rng(20260820)
    natif = rng.gamma(0.4, 2.0, size=(piaf.NB_ECHEANCES, len(lats),
                                      len(lons))).astype(np.float32)
    # Une averse franche, sur un point d'indices impairs (celui qu'une
    # décimation saute), à une seule échéance.
    natif[7, 5, 7] = 23.5
    p = Passe("2026-08-20T05:50:00Z", natif, lats, lons, boite=BOITE_BANC,
              domaines=("banc",), latence_min=12.6)
    return p, natif, lats, lons


def banc_objets():
    print("\n── 7. les deux jeux, relus par les règles du manifeste ──")
    p, natif, lats, lons = _passe_de_banc()
    man = p.manifeste()
    carte = p.carte_bin()
    colonnes = p.colonnes_bin("banc")

    cal, cou = man["service"]["calque"], man["service"]["coupe"]
    verifie(len(carte) == cal["octets_par_echeance"] * piaf.NB_ECHEANCES,
            "`carte.bin` fait exactement ce que le manifeste annonce",
            f"{len(carte)} vs "
            f"{cal['octets_par_echeance'] * piaf.NB_ECHEANCES}")
    d = cou["domaines"]["banc"]
    verifie(len(colonnes)
            == d["nb_lat"] * d["nb_lon"] * cou["octets_par_colonne"],
            "`colonnes-banc.bin` aussi",
            f"{len(colonnes)} vs {d['nb_lat'] * d['nb_lon'] * cou['octets_par_colonne']}")

    # ── La coupe, lue comme le client la lira ────────────────────────
    j0, j1, i0, i1 = fenetre_domaine("banc", BOITE_BANC)
    attendu = quantifier(natif[:, j0:j1 + 1, i0:i1 + 1],
                         PARAM_PLUIE_IMMEDIATE).astype(np.float32)
    pires = []
    for j in range(d["nb_lat"]):
        for i in range(d["nb_lon"]):
            o = (j * d["nb_lon"] + i) * cou["octets_par_colonne"]
            serie = np.frombuffer(colonnes, dtype="<f2", offset=o,
                                  count=piaf.NB_ECHEANCES).astype(np.float32)
            pires.append(float(np.nanmax(np.abs(serie - attendu[:, j, i]))))
    verifie(max(pires) == 0.0,
            f"⛔ les {d['nb_lat'] * d['nb_lon']} colonnes se relisent à "
            f"l'octet près par `(j × nb_lon + i) × octets_par_colonne`",
            f"écart max {max(pires)}")

    # ── Le calque, lu comme le client le lira ────────────────────────
    pas_e, njc, nic = (cal["octets_par_echeance"], cal["nb_lat"],
                       cal["nb_lon"])
    lat_c, lon_c = p.axes_calque()
    verifie((njc, nic) == (len(lat_c), len(lon_c))
            and abs(cal["lat_premier"] - float(lat_c[0])) < 1e-4
            and abs(cal["lon_dernier"] - float(lon_c[-1])) < 1e-4,
            "les axes du calque publiés collent aux axes servis")
    verifie(abs(cal["pas_deg"] - 2 * man["axes"]["pas_deg"]) < 1e-9,
            "le pas du calque est un multiple ENTIER du pas natif — "
            "c'est ce que 0,025° ne pouvait pas être")

    # ⛔ L'INVARIANT QUI TIENT TOUT LE LOT : le calque MAJORE la coupe,
    # partout. S'il lui était inférieur quelque part, le pilote verrait
    # moins de pluie sur la carte que dans sa coupe, au même instant.
    manques, ecarts = 0, []
    for rang in range(piaf.NB_ECHEANCES):
        bloc = np.frombuffer(carte, dtype="<f2", offset=rang * pas_e,
                             count=njc * nic).astype(np.float32).reshape(
                                 njc, nic)
        for j in range(d["nb_lat"]):
            for i in range(d["nb_lon"]):
                bj, bi = (j0 + j) // 2, (i0 + i) // 2
                c, v = float(attendu[rang, j, i]), float(bloc[bj, bi])
                if np.isfinite(c) and c - v > 0:
                    manques += 1
                    ecarts.append(c - v)
    verifie(manques == 0,
            f"⛔ le calque majore la coupe sur les "
            f"{piaf.NB_ECHEANCES * d['nb_lat'] * d['nb_lon']} mailles "
            f"confrontées",
            f"{manques} mailles où la carte montre MOINS que la coupe, "
            f"pire écart {max(ecarts) if ecarts else 0}")

    # ⛔ Et l'averse d'une maille est bien là, à l'échéance 7.
    bloc7 = np.frombuffer(carte, dtype="<f2", offset=7 * pas_e,
                          count=njc * nic).astype(np.float32).reshape(njc, nic)
    verifie(abs(float(bloc7[5 // 2, 7 // 2]) - 23.5) < 0.02,
            "⛔ l'averse de 23,5 mm posée sur un point d'indices impairs "
            "est SUR LE CALQUE, à sa maille",
            str(float(bloc7[5 // 2, 7 // 2])))

    # ── Le manifeste dit-il ce qu'il faut ? ──────────────────────────
    verifie(man["source"]["licence"].startswith("Licence Ouverte"),
            "l'attribution de la source est publiée — c'est une obligation "
            "de la licence, pas une politesse")
    verifie(any(r["quoi"] == "qualité radar" for r in man["refus"]),
            "⛔ le refus « qualité radar » est nommé, avec le fait qu'elle "
            "n'est PAS publiée — le silence ne vaut pas « qualité bonne »")
    verifie(len(man["remplissage_par_echeance"]) == piaf.NB_ECHEANCES,
            "le remplissage est publié PAR ÉCHÉANCE, jamais en un chiffre "
            "global qui masquerait une tranche morte")
    verifie(man["octets_publies"] == len(carte) + len(colonnes),
            "`octets_publies` compte ce qui est réellement écrit",
            f"{man['octets_publies']} vs {len(carte) + len(colonnes)}")


# ══════════════════════════════════════════════════════════════════════
#  6. L'INDEX ET LA PURGE — sur un magasin qui n'est qu'un dictionnaire
# ══════════════════════════════════════════════════════════════════════
class MagasinDeBanc:
    """Le strict nécessaire, plus le pouvoir d'ÉCHOUER sur commande.

    ⚠️ `delete` rend `False` sans lever — c'est le comportement RÉEL de
    `storage.Storage.delete`, et c'est précisément ce qui a fabriqué 18
    orphelins les 12-13/08 : un `try/except` autour n'attrape rien.
    """

    def __init__(self, casser_a=None, purge_muette=False):
        self.objets, self.ecritures, self.supprimees = {}, 0, []
        self.casser_a, self.purge_muette = casser_a, purge_muette

    def put(self, cle, corps, *, cache_control, content_type=None,
            content_encoding=None):
        self.ecritures += 1
        if self.casser_a is not None and self.ecritures == self.casser_a:
            raise OSError("écriture cassée par le banc")
        self.objets[cle] = bytes(corps)

    def get(self, cle):
        return self.objets.get(cle)

    def get_json(self, cle):
        import json
        brut = self.objets.get(cle)
        return json.loads(brut) if brut else None

    def get_range(self, cle, debut, octets):
        brut = self.objets.get(cle)
        return None if brut is None else brut[debut:debut + octets]

    def delete(self, cle):
        if self.purge_muette:
            return False
        self.supprimees.append(cle)
        self.objets.pop(cle, None)
        return True


def banc_index():
    print("\n── 8. l'index, la rétention et la purge ──")
    p, _n, _a, _o = _passe_de_banc()
    st = MagasinDeBanc()
    passes = ["2026-08-20T05:%02d:00Z" % m for m in (30, 40, 50)]
    for x in passes:
        p.passe = x
        p.echeances = echeances(x)
        p.heures = heures_entieres(x)
        piaf.ecrire(st, p, journal=lambda _m: None)
    idx = st.get_json(piaf.CLE_INDEX)
    verifie(idx["dernier"][piaf.FLUX] == passes[-1],
            "`dernier` désigne la passe la plus fraîche", str(idx["dernier"]))
    verifie(len(idx["runs"]) == piaf.RETENTION_PASSES,
            f"{piaf.RETENTION_PASSES} passes gardées en ligne",
            str(len(idx["runs"])))
    verifie(all(c in st.supprimees
                for c in cles_de_la_passe(passes[0], ("banc",))),
            "⛔ les clés de la passe la plus ancienne ont été SUPPRIMÉES — "
            "une purge comptée, pas déclarée")
    reste = {c for c in st.objets if c != piaf.CLE_INDEX}
    reclamees = {c for e in idx["runs"] for c in e["cles"]}
    verifie(reste == reclamees,
            "⛔ tout objet en ligne est RÉCLAMÉ par l'index — c'est le "
            "contrat que `tools/audit_r2.py` vérifiera chaque nuit",
            f"en trop : {sorted(reste - reclamees)}")
    verifie(idx["produit"].startswith("AGRUME — index des passes"),
            "l'index dit ce qu'il indexe (et non « produit B », que "
            "`grille.index_apres` y mettrait)", idx["produit"])

    print("\n── 9. l'écriture PARTIELLE ──")
    # La 3ᵉ écriture casse : `carte.bin` et `colonnes-banc.bin` sont
    # partis, le manifeste non.
    st2 = MagasinDeBanc(casser_a=3)
    p.passe = passes[0]
    p.echeances, p.heures = echeances(passes[0]), heures_entieres(passes[0])
    try:
        piaf.ecrire(st2, p, journal=lambda _m: None)
    except OSError:
        pass
    idx2 = st2.get_json(piaf.CLE_INDEX) or {}
    verifie(not (idx2.get("dernier") or {}).get(piaf.FLUX),
            "⛔ `dernier` N'A PAS AVANCÉ — personne ne lira une passe "
            "dépareillée", str(idx2.get("dernier")))
    inscrites = {c for e in (idx2.get("runs") or []) for c in e["cles"]}
    en_ligne = {c for c in st2.objets if c != piaf.CLE_INDEX}
    verifie(en_ligne and en_ligne <= inscrites,
            "⛔ …mais les objets déjà écrits SONT dans l'index, donc "
            "purgeables. Hors index, ils seraient invisibles et "
            "définitivement payés — `ListObjects` n'est pas une route de "
            "ce projet", f"en ligne {sorted(en_ligne)}")

    print("\n── 10. la purge qui ne mord plus, et celle qui déborde ──")
    st3 = MagasinDeBanc(purge_muette=True)
    for x in passes:
        p.passe = x
        p.echeances, p.heures = echeances(x), heures_entieres(x)
        piaf.ecrire(st3, p, journal=lambda _m: None)
    idx3 = st3.get_json(piaf.CLE_INDEX)
    verifie(len(idx3["restes"])
            == len(cles_de_la_passe(passes[0], ("banc",))),
            "⛔ une purge qui rend `False` sans lever laisse ses clés dans "
            "`restes` — elles seront réessayées. C'est la ligne exacte qui "
            "manquait le 12/08 et qui a coûté 18 orphelins",
            str(idx3["restes"]))
    from grille import verifier_prefixe
    try:
        verifier_prefixe(["agrume/colonnes/2026-08-20/colonnes.npz"],
                         prefixe=piaf.PREFIXE)
        verifie(False, "une clé HORS PRÉFIXE doit arrêter la purge entière")
    except ValueError:
        verifie(True,
                "⛔ une clé hors préfixe arrête la purge ENTIÈRE — le "
                "produit A est définitif et vit dans le même bucket")


def main():
    print("═" * 66)
    print(" banc — AGRUME, la pluie à venir (Lot Q2)")
    print("═" * 66)
    banc_temps()
    banc_reduction()
    banc_geometrie()
    banc_quantification()
    banc_objets()
    banc_index()
    print("\n" + "═" * 66)
    print(f" {_OK} contrôles verts, {_KO} rouges")
    print("═" * 66)
    return 1 if _KO else 0


if __name__ == "__main__":
    sys.exit(main())
