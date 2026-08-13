#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  test_audit_r2.py — le banc de la jauge R2 (10/08/2026)
#
#  ⚠️ CE BANC EXISTE POUR RÉPONDRE À UNE QUESTION PRÉCISE : la jauge
#  PRÉVIENT-ELLE, ou CONSTATE-T-ELLE ? Une jauge qui n'alerte qu'au
#  moment du dépassement ne vaut pas mieux que le mail de facturation
#  qu'elle est censée devancer — c'est exactement ce qui s'est passé
#  le 30/07 sur Supabase, deux fois.
#
#  Les épreuves qui comptent :
#
#    · un compte à 3 Go qui monte de 2 Go/mois doit ALERTER, alors qu'il
#      est très loin du seuil — parce qu'il touchera le palier dans
#      ~105 jours et qu'on veut le savoir avant ;
#    · une pente calculée sur un volume qui OSCILLE (chaîne à rétention
#      courte : écrit puis purge) ne doit pas être la différence entre
#      le premier et le dernier point ;
#    · un historique corrompu ne doit pas empêcher de mesurer le présent ;
#    · le palier se compte en Go DÉCIMAUX. Le « corriger » en 1024³
#      sous-estimerait de 7 % au moment précis où on frôle la ligne ;
#    · la nuit du 30/07 rejouée (accumulation sans aucun `delete`) doit
#      déclencher LARGEMENT avant les 10 Go.
#
#  Lancement :  python3 tools/test_audit_r2.py
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from audit_r2 import (  # noqa: E402
    GO, PALIER_STOCKAGE_GO, agreger, charger_historique, jours_avant,
    meme_perimetre, pente_du_prefixe, pente_go_par_mois, pentes_des_prefixes,
    prefixe_de, verdict,
)

T0 = datetime(2026, 8, 1, 3, 0, tzinfo=timezone.utc)


def hist(*paires):
    """(jour, Go) → relevés au format de l'historique."""
    return [{"t": (T0 + timedelta(days=j)).isoformat(timespec="seconds"),
             "octets": int(go * GO)} for j, go in paires]


def rel(jour, prefixes, bucket="grids"):
    """(jour, {préfixe: Go}) → relevé complet, au format écrit depuis le
    13/08 : total, buckets ET préfixes.

    ⚠️ Le bucket est le MÊME partout par défaut, et c'est le cœur des
    bancs qui suivent : le périmètre de buckets ne bouge pas, donc le
    filtre du 10/08 laisse passer — il faut celui du 13/08 pour voir la
    marche.
    """
    return {"t": (T0 + timedelta(days=jour)).isoformat(timespec="seconds"),
            "octets": int(sum(prefixes.values()) * GO),
            "buckets": {bucket: int(sum(prefixes.values()) * GO)},
            "prefixes": {k: int(v * GO) for k, v in prefixes.items()},
            "couverture_complete": True}


# ══════════════════════════════════════════════════════════════════════
class Prefixes(unittest.TestCase):
    def test_deux_niveaux(self):
        self.assertEqual(prefixe_de("arome/sol/2026/t-3.json"), "arome/sol")

    def test_racine_nommee_pas_la_cle(self):
        # Sinon un bucket plat produirait une ligne de tableau par objet,
        # et le rapport deviendrait illisible au moment d'en avoir besoin.
        self.assertEqual(prefixe_de("manifest.json"), "(racine)")

    def test_slash_en_trop_ignores(self):
        self.assertEqual(prefixe_de("/arome//alt/x.json"), "arome/alt")

    def test_profondeur_reglable(self):
        self.assertEqual(prefixe_de("a/b/c/d", profondeur=3), "a/b/c")


class Agregation(unittest.TestCase):
    def setUp(self):
        self.objets = [
            ("grids", "arome/sol/a.json", 100),
            ("grids", "arome/sol/b.json", 200),
            ("grids", "arome/alt/c.json", 700),
            ("model-verif", "fcst/2026/x.gz", 1000),
        ]

    def test_total(self):
        self.assertEqual(agreger(self.objets)["octets"], 2000)

    def test_compte_objets(self):
        self.assertEqual(agreger(self.objets)["objets"], 4)

    def test_par_bucket(self):
        pb = agreger(self.objets)["par_bucket"]
        self.assertEqual(pb["grids"]["octets"], 1000)
        self.assertEqual(pb["model-verif"]["octets"], 1000)
        self.assertEqual(pb["grids"]["objets"], 3)

    def test_prefixe_porte_son_bucket(self):
        # Deux buckets peuvent avoir le même préfixe. Sans le nom du
        # bucket dans la clé, leurs volumes se mélangeraient en silence.
        pp = agreger(self.objets)["par_prefixe"]
        self.assertIn("grids:arome/sol", pp)
        self.assertIn("model-verif:fcst/2026", pp)
        self.assertEqual(pp["grids:arome/sol"]["octets"], 300)

    def test_vide(self):
        inv = agreger([])
        self.assertEqual(inv["octets"], 0)
        self.assertEqual(inv["objets"], 0)


class Pente(unittest.TestCase):
    def test_moins_de_trois_points_pas_de_pente(self):
        # Deux points suffisent à calculer une pente, pas à la croire.
        self.assertIsNone(pente_go_par_mois(hist((0, 1.0), (30, 3.0))))

    def test_croissance_lineaire(self):
        p = pente_go_par_mois(hist((0, 1.0), (15, 2.0), (30, 3.0)))
        self.assertAlmostEqual(p, 2.0, places=6)

    def test_oscillation_rend_la_tendance_pas_le_delta(self):
        # ⚠️ L'épreuve centrale. Volume qui monte de 1 Go/mois en dents
        # de scie (rétention courte). Une simple différence premier↔dernier
        # rendrait 0,0 ici et la jauge dormirait pendant que ça monte.
        points = hist((0, 2.0), (10, 2.9), (20, 2.4), (30, 3.4),
                      (40, 2.9), (50, 3.9), (60, 3.4))
        p = pente_go_par_mois(points)
        delta_naif = (3.4 - 2.0) / 60 * 30
        self.assertGreater(p, 0.5)
        self.assertNotAlmostEqual(p, 0.0, places=2)
        # et la tendance doit rester du bon ordre de grandeur
        self.assertLess(abs(p - delta_naif), 0.6)

    def test_decroissance(self):
        p = pente_go_par_mois(hist((0, 5.0), (15, 4.0), (30, 3.0)))
        self.assertLess(p, 0)

    def test_tous_le_meme_jour(self):
        self.assertIsNone(pente_go_par_mois(hist((0, 1.0), (0, 2.0), (0, 3.0))))

    def test_releves_incomplets_ignores(self):
        h = hist((0, 1.0), (15, 2.0), (30, 3.0))
        h.insert(1, {"t": None, "octets": 99})
        h.insert(2, {"octets": None, "t": T0.isoformat()})
        self.assertAlmostEqual(pente_go_par_mois(h), 2.0, places=6)


class Echeance(unittest.TestCase):
    def test_pente_inconnue(self):
        self.assertIsNone(jours_avant(int(3 * GO), None, 10.0))

    def test_pente_negative_pas_decheance(self):
        # Un volume qui décroît n'a pas d'échéance. Prétendre le
        # contraire ferait alerter sur un projet en train de se ranger.
        self.assertIsNone(jours_avant(int(3 * GO), -1.0, 10.0))

    def test_cible_deja_franchie(self):
        self.assertEqual(jours_avant(int(12 * GO), 1.0, 10.0), 0.0)

    def test_calcul(self):
        # 3 Go, +2 Go/mois, cible 10 Go → 7 Go à faire → 105 jours
        j = jours_avant(int(3 * GO), 2.0, 10.0)
        self.assertAlmostEqual(j, 105.0, places=3)


class Verdict(unittest.TestCase):
    def inv(self, go):
        return {"octets": int(go * GO), "objets": 1,
                "par_bucket": {}, "par_prefixe": {}}

    def test_calme(self):
        v = verdict(self.inv(1.0), 0.05, seuil_go=7.0, horizon=60)
        self.assertFalse(v["alerte"])
        self.assertEqual(v["motifs"], [])

    def test_seuil_franchi(self):
        v = verdict(self.inv(7.5), None, seuil_go=7.0)
        self.assertTrue(v["alerte"])
        self.assertIn("seuil d'alerte", v["motifs"][0])

    def test_palier_depasse_dit_qu_on_facture(self):
        v = verdict(self.inv(11.0), None, seuil_go=7.0)
        self.assertTrue(v["alerte"])
        self.assertIn("facture", v["motifs"][0])

    def test_alerte_AVANT_le_seuil_grace_a_la_pente(self):
        # ⚠️ LA raison d'être de ce fichier. 3 Go seulement — très loin
        # du seuil de 7 — mais +2 Go/mois : palier dans 105 jours… non,
        # dans l'horizon si on le règle à 120. On veut que la pente
        # puisse déclencher seule.
        v = verdict(self.inv(3.0), 2.0, seuil_go=7.0, horizon=120)
        self.assertTrue(v["alerte"])
        self.assertTrue(any("rythme mesuré" in m for m in v["motifs"]))

    def test_pente_lointaine_ne_declenche_pas(self):
        # +0,1 Go/mois depuis 3 Go = ~2 100 jours. Alerter là-dessus
        # apprendrait à ignorer les alertes.
        v = verdict(self.inv(3.0), 0.1, seuil_go=7.0, horizon=60)
        self.assertFalse(v["alerte"])

    def test_pas_de_double_motif_quand_deja_depasse(self):
        # Au-delà du palier, l'échéance n'a plus de sens : un seul motif.
        v = verdict(self.inv(12.0), 3.0, seuil_go=7.0, horizon=60)
        self.assertEqual(len(v["motifs"]), 1)


class Perimetre(unittest.TestCase):
    """⚠️ LA PANNE DU 10/08, REJOUÉE. Le matin la jauge voyait 2 buckets
    (0,031 Go) ; à midi le jeton d'audit est arrivé et elle en a vu 3
    (0,815 Go). Dans un historique commun, la régression y lisait
    +587 Go/mois et annonçait le palier « dans 0 jours ». Une marche de
    périmètre n'est pas une croissance."""

    def rel(self, jour, go, buckets):
        return {"t": (T0 + timedelta(days=jour)).isoformat(timespec="seconds"),
                "octets": int(go * GO),
                "buckets": {b: 0 for b in buckets}}

    def test_la_marche_de_perimetre_ne_fabrique_plus_de_pente(self):
        deux, trois = ("a", "b"), ("a", "b", "c")
        serie = [self.rel(0, 0.031, deux), self.rel(0.01, 0.031, deux),
                 self.rel(0.02, 0.031, deux), self.rel(0.03, 0.815, trois)]
        p_naif = pente_go_par_mois(serie)                    # sans filtre
        p_filtre = pente_go_par_mois(serie, frozenset(trois))
        self.assertGreater(p_naif, 100, "le cas de la panne doit bien exploser")
        self.assertIsNone(p_filtre, "un seul relevé comparable => pas de pente")

    def test_pente_juste_une_fois_le_perimetre_stable(self):
        trois = ("a", "b", "c")
        serie = [self.rel(0, 1.0, trois), self.rel(15, 2.0, trois),
                 self.rel(30, 3.0, trois)]
        self.assertAlmostEqual(pente_go_par_mois(serie, frozenset(trois)),
                               2.0, places=6)

    def test_sans_perimetre_rien_ne_change(self):
        # Compatibilité : appelé sans périmètre, le calcul est l'ancien.
        self.assertAlmostEqual(pente_go_par_mois(hist((0, 1.0), (15, 2.0),
                                                      (30, 3.0))), 2.0, places=6)

    def test_releve_sans_buckets_est_ecarte(self):
        # Les relevés d'avant l'ajout du champ ne doivent pas polluer.
        self.assertFalse(meme_perimetre({"t": "x", "octets": 1},
                                        frozenset(("a",))))


class CouverturePartielle(unittest.TestCase):
    """⚠️ Relevé au déploiement du 10/08 : le jeton R2 du VPS ne lit que
    2 buckets sur 3, et pas le plus gros. Un total partiel comparé à un
    palier donne un feu vert qui ne vaut rien — il doit donc alerter,
    même quand tous les chiffres sont bas."""

    def inv(self, go):
        return {"octets": int(go * GO), "objets": 1,
                "par_bucket": {}, "par_prefixe": {}}

    def test_couverture_partielle_alerte_meme_a_vide(self):
        v = verdict(self.inv(0.2), 0.0, couverture_partielle=True)
        self.assertTrue(v["alerte"])
        self.assertIn("COUVERTURE PARTIELLE", v["motifs"][0])

    def test_couverture_complete_ne_dit_rien(self):
        v = verdict(self.inv(0.2), 0.0, couverture_partielle=False)
        self.assertFalse(v["alerte"])

    def test_le_drapeau_est_dans_le_verdict(self):
        # Il doit ressortir en JSON : c'est ce que relit le lendemain
        # celui qui se demande si le chiffre d'hier valait quelque chose.
        self.assertTrue(verdict(self.inv(1), None,
                                couverture_partielle=True)["couverture_partielle"])

    def test_partielle_n_efface_pas_les_autres_motifs(self):
        v = verdict(self.inv(11.0), None, couverture_partielle=True)
        self.assertEqual(len(v["motifs"]), 2)
        self.assertIn("COUVERTURE PARTIELLE", v["motifs"][0])
        self.assertIn("facture", v["motifs"][1])


class Historique(unittest.TestCase):
    def test_fichier_absent(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(charger_historique(Path(d) / "rien.jsonl"), [])

    def test_ligne_corrompue_ignoree_pas_fatale(self):
        # Leçon du budget Open-Meteo : un état abîmé ne doit pas
        # empêcher de mesurer le présent.
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "audit_r2.jsonl"
            p.write_text('{"t":"2026-08-01T03:00:00+00:00","octets":1}\n'
                         'ceci n est pas du json\n'
                         '{"t":"2026-08-02T03:00:00+00:00","octets":2}\n',
                         encoding="utf-8")
            h = charger_historique(p)
            self.assertEqual(len(h), 2)
            self.assertEqual(h[1]["octets"], 2)

    def test_borne_aux_derniers_releves(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.jsonl"
            p.write_text("".join(
                json.dumps({"t": T0.isoformat(), "octets": i}) + "\n"
                for i in range(50)), encoding="utf-8")
            self.assertEqual(len(charger_historique(p, maxi=10)), 10)


class Unites(unittest.TestCase):
    def test_go_decimal_et_pas_gibi(self):
        # ⚠️ Régression volontaire : R2 facture en Go décimaux. Passer en
        # 1024³ sous-estimerait de 7 % — au moment précis où on frôle la
        # ligne, donc au pire moment possible.
        self.assertEqual(GO, 1_000_000_000)

    def test_palier_importe_de_storage(self):
        # Pas de seuil recopié : la leçon de LEVELS dupliqué.
        self.assertEqual(PALIER_STOCKAGE_GO, 10.0)


class NuitDu30Juillet(unittest.TestCase):
    """La panne réelle, rejouée : quatre chaînes qui écrivent et aucune
    qui efface. On veut savoir COMBIEN DE JOURS AVANT le dépassement la
    jauge aurait parlé."""

    def test_la_jauge_aurait_parle_des_le_debut(self):
        # Accumulation régulière de ~1,9 Go/mois (le rythme projeté de
        # l'archive AGRUME), départ à 0,85 Go — l'occupation réelle.
        PENTE = 1.9          # Go/mois — le rythme projeté de l'archive AGRUME
        DEPART = 0.85        # Go — l'occupation R2 réelle au 10/08/2026
        releves = []
        for j in range(0, 180, 3):
            go = DEPART + PENTE * (j / 30.0)
            releves.append({"t": (T0 + timedelta(days=j)).isoformat(),
                            "octets": int(go * GO)})

        premiere_alerte = None
        for i in range(3, len(releves) + 1):
            fenetre = releves[:i]
            inv = {"octets": fenetre[-1]["octets"], "objets": 0,
                   "par_bucket": {}, "par_prefixe": {}}
            v = verdict(inv, pente_go_par_mois(fenetre), seuil_go=7.0, horizon=60)
            if v["alerte"]:
                premiere_alerte = fenetre[-1]
                break

        self.assertIsNotNone(premiere_alerte, "la jauge n'a jamais parlé")
        go_alerte = premiere_alerte["octets"] / GO
        # Elle doit parler avant le palier ET avant le seuil de niveau :
        # c'est la PENTE qui déclenche, pas le niveau. Si un jour ce test
        # ne passe plus qu'au seuil, la jauge est redevenue un constat.
        self.assertLess(go_alerte, PALIER_STOCKAGE_GO)
        self.assertLess(go_alerte, 7.0)
        # Et il doit rester assez de marge pour décider posément.
        marge_jours = (PALIER_STOCKAGE_GO - go_alerte) / (PENTE / 30.0)
        self.assertGreaterEqual(marge_jours, 55,
                                f"seulement {marge_jours:.0f} j de marge")

    def test_un_compte_stable_ne_declenche_jamais(self):
        # L'autre moitié du contrat : pas de cri au loup. Une grille à
        # rétention courte oscille sans tendance — elle ne doit rien
        # déclencher, sinon on cesserait de lire les alertes.
        releves = []
        for j in range(0, 90, 3):
            go = 3.0 + (0.25 if (j // 3) % 2 else -0.25)
            releves.append({"t": (T0 + timedelta(days=j)).isoformat(),
                            "octets": int(go * GO)})
        inv = {"octets": releves[-1]["octets"], "objets": 0,
               "par_bucket": {}, "par_prefixe": {}}
        v = verdict(inv, pente_go_par_mois(releves), seuil_go=7.0, horizon=60)
        self.assertFalse(v["alerte"], f"faux positif : {v['motifs']}")


class MarcheDeProduit(unittest.TestCase):
    """⚠️ LA PANNE DU 13/08, REJOUÉE AVEC SES VRAIS CHIFFRES. Le produit B
    (grille AGRUME) est arrivé dans la nuit du 12 au 13 : +1,03 Go d'un
    coup, **à l'intérieur d'un bucket déjà connu**. Le filtre du 10/08 ne
    regarde que l'ensemble des BUCKETS — il n'a rien vu. Les moindres
    carrés sur le total ont lu +9,1 Go/mois et annoncé le palier « dans
    27 jours », alors que la grille était à son plateau (rétention 3
    runs, 0 orphelin) et le compte à 2,0 Go sur 10.

    Relevés réels : 0,816 · 0,894 · 0,915 · 1,946 Go."""

    SOCLE = "grids:socle"
    NEUF = "grids:agrume/grille"

    def serie(self):
        return [rel(0, {self.SOCLE: 0.816}),
                rel(1, {self.SOCLE: 0.894}),
                rel(2, {self.SOCLE: 0.915}),
                rel(3, {self.SOCLE: 0.873, self.NEUF: 1.073})]

    def test_le_calcul_sur_le_total_explose_bien(self):
        # Le contre-exemple, gardé : sans lui, le test suivant pourrait
        # passer sur les deux implémentations, donc ne rien vérifier.
        serie = self.serie()
        naif = pente_go_par_mois(serie)
        naif_filtre_1008 = pente_go_par_mois(serie, frozenset(("grids",)))
        self.assertGreater(naif, 8.0, "le cas de la panne doit bien exploser")
        self.assertAlmostEqual(naif_filtre_1008, naif, places=6,
                               msg="le filtre du 10/08 ne voit PAS cette "
                                   "marche-là — c'est tout le problème")

    def test_la_somme_des_prefixes_ne_fabrique_plus_la_marche(self):
        p = pentes_des_prefixes(self.serie(), [self.SOCLE, self.NEUF])
        self.assertIn(self.NEUF, p["jeunes"], "un produit d'un seul relevé "
                                              "n'a pas de pente")
        self.assertLess(p["total"], 1.0)
        self.assertGreater(p["total"], 0.0)

    def test_et_le_mail_ne_part_plus(self):
        serie = self.serie()
        inv = {"octets": serie[-1]["octets"], "objets": 1426,
               "par_bucket": {}, "par_prefixe": {}}
        naif = pente_go_par_mois(serie)
        juste = pentes_des_prefixes(serie, [self.SOCLE, self.NEUF])["total"]
        self.assertTrue(verdict(inv, naif, seuil_go=7.0, horizon=60)["alerte"],
                        "le 13/08 au matin, l'alerte est bien partie")
        self.assertFalse(verdict(inv, juste, seuil_go=7.0, horizon=60)["alerte"],
                         "et elle ne doit plus partir")

    def test_le_prix_est_rendu_pas_tu(self):
        # Une échéance qui ne couvre pas tout doit le dire : c'est ce
        # champ que `rendre()` et `main()` journalisent.
        p = pentes_des_prefixes(self.serie(), [self.SOCLE, self.NEUF])
        self.assertEqual(p["jeunes"], [self.NEUF])


class MarcheDeBucket(unittest.TestCase):
    """La panne du 10/08 relue à travers le mécanisme du 13/08 : un
    bucket entier qui apparaît n'est qu'un paquet de préfixes neufs. Le
    nouveau filtre couvre donc les DEUX marches — c'est ce qui autorise
    `meme_perimetre` à ne plus servir qu'aux bancs."""

    def test_le_bucket_apparu_ne_fabrique_pas_de_pente(self):
        vieux = {"mv:fcst/2026": 0.031}
        serie = [rel(0, vieux), rel(0.01, vieux), rel(0.02, vieux),
                 rel(0.03, {**vieux, "grids:arome/sol": 0.785})]
        p = pentes_des_prefixes(serie, ["mv:fcst/2026", "grids:arome/sol"])
        self.assertIn("grids:arome/sol", p["jeunes"])
        self.assertLess(abs(p["total"]), 0.5,
                        "0,78 Go apparus ne sont pas 0,78 Go de croissance")


class PenteParPrefixe(unittest.TestCase):
    def test_absence_n_est_pas_zero(self):
        # ⚠️ Le piège central. Un préfixe absent d'un relevé est un
        # SILENCE (produit pas né, ou couverture partielle ce jour-là).
        # Le lire comme 0 fabriquerait la marche qu'on vient de tuer.
        serie = [rel(0, {"a": 1.0}), rel(1, {"a": 1.0}),
                 rel(2, {"a": 1.0, "b": 1.0}),
                 rel(3, {"a": 1.0, "b": 2.0}),
                 rel(4, {"a": 1.0, "b": 3.0})]
        self.assertAlmostEqual(pente_du_prefixe(serie, "b"), 30.0, places=6)
        # Et la valeur qu'on aurait eue en comptant les absences comme 0,
        # gardée en clair pour que l'écart soit lisible :
        self.assertNotAlmostEqual(pente_du_prefixe(serie, "b"), 24.0, places=1)

    def test_la_somme_fait_le_total(self):
        serie = [rel(j, {"a": 1.0 + j, "b": 2.0 + 2 * j}) for j in (0, 15, 30)]
        p = pentes_des_prefixes(serie, ["a", "b"])
        self.assertAlmostEqual(p["par_prefixe"]["a"], 30.0, places=6)
        self.assertAlmostEqual(p["par_prefixe"]["b"], 60.0, places=6)
        self.assertAlmostEqual(p["total"], 90.0, places=6)

    def test_un_prefixe_disparu_ne_compte_plus(self):
        # Une chaîne qu'on arrête laisse sa pente dans l'historique. La
        # compter encore projetterait une croissance qui n'existe plus.
        serie = [rel(j, {"a": 1.0, "mort": float(j)}) for j in (0, 15, 30)]
        p = pentes_des_prefixes(serie, ["a"])   # « mort » n'est plus courant
        self.assertNotIn("mort", p["par_prefixe"])
        self.assertAlmostEqual(p["total"], 0.0, places=6)

    def test_aucune_pente_connue_rend_none(self):
        # Mieux vaut « pas d'échéance » qu'une échéance sur une somme
        # vide, qui vaudrait 0 et se lirait comme « rien ne monte ».
        p = pentes_des_prefixes([rel(0, {"a": 1.0})], ["a"])
        self.assertIsNone(p["total"])
        self.assertEqual(p["jeunes"], ["a"])

    def test_releves_d_avant_le_13_08_sont_ignores(self):
        # L'historique existant n'a pas le champ `prefixes`. Il ne doit
        # ni planter ni compter : la pente repart proprement de zéro.
        vieux = hist((0, 1.0), (1, 2.0), (2, 3.0))
        self.assertIsNone(pente_du_prefixe(vieux, "a"))

    def test_une_vraie_fuite_reste_vue(self):
        # ⛔ L'autre moitié du contrat. Le but n'est pas de faire taire la
        # jauge : un préfixe qui monte pour de bon doit toujours
        # déclencher, marche ou pas ailleurs.
        serie = [rel(j, {"stable": 2.0, "fuite": 0.1 * j}) for j in range(0, 12)]
        p = pentes_des_prefixes(serie, ["stable", "fuite"])
        self.assertAlmostEqual(p["total"], 3.0, places=2)
        inv = {"octets": serie[-1]["octets"], "objets": 1,
               "par_bucket": {}, "par_prefixe": {}}
        # À j=11 : 3,1 Go, +3 Go/mois → palier dans 69 j, hors horizon.
        # À j=22 : 4,2 Go, même pente → 58 j, et là ça doit crier. Le
        # niveau (4,2 Go) est toujours SOUS le seuil de 7 : c'est bien la
        # pente qui déclenche, pas le seuil — le contrat du fichier.
        serie += [rel(j, {"stable": 2.0, "fuite": 0.1 * j})
                  for j in range(12, 23)]
        p2 = pentes_des_prefixes(serie, ["stable", "fuite"])
        inv2 = {"octets": serie[-1]["octets"], "objets": 1,
                "par_bucket": {}, "par_prefixe": {}}
        self.assertTrue(verdict(inv2, p2["total"], seuil_go=7.0,
                                horizon=60)["alerte"],
                        f"une fuite de {p2['total']:.2f} Go/mois doit crier")
        self.assertFalse(verdict(inv, p["total"], seuil_go=7.0,
                                 horizon=60)["alerte"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
