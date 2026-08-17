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
#    · ⛔ une MARCHE n'est pas une pente. Trois fois de suite, un volume
#      né à son plateau a été lu comme une croissance et un mail est
#      parti : un bucket le 10/08, un produit le 13/08, un domaine le
#      16/08. Les trois sont rejoués ici AVEC LEURS VRAIS CHIFFRES, et
#      le calcul fautif est gardé à côté en contre-exemple — sans lui,
#      le banc pourrait passer sur les deux implémentations et ne rien
#      vérifier du tout ;
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
    prefixe_de, rapprocher, verdict,
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

    def test_la_jauge_parle_ENCORE_avec_le_calcul_du_16_08(self):
        """⛔ Le contrat du fichier, rejoué contre le calcul de
        PRODUCTION. Faire taire trois marches ne doit pas avoir fait
        taire les fuites : c'est la moitié du travail qu'on risque de
        casser en corrigeant l'autre."""
        PENTE, DEPART = 1.9, 0.85
        serie, premiere = [], None
        for j in range(0, 180, 3):
            serie.append(rel(j, {"grids:fuite": DEPART + PENTE * (j / 30.0)}))
            inv = {"octets": serie[-1]["octets"], "objets": 0,
                   "par_bucket": {}, "par_prefixe": {}}
            juste = pentes_des_prefixes(serie, ["grids:fuite"])["total"]
            if verdict(inv, juste, seuil_go=7.0, horizon=60)["alerte"]:
                premiere = serie[-1]
                break

        self.assertIsNotNone(premiere, "la jauge n'a jamais parlé")
        go = premiere["octets"] / GO
        # Comme pour les moindres carrés : c'est la PENTE qui doit
        # déclencher, pas le niveau, et il doit rester de quoi décider.
        self.assertLess(go, 7.0)
        marge = (PALIER_STOCKAGE_GO - go) / (PENTE / 30.0)
        self.assertGreaterEqual(marge, 55, f"seulement {marge:.0f} j de marge")


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
        # ⚠️ DEPUIS LE 17/08, la réponse est encore plus tranchée qu'en
        # août : le socle lui-même n'a que quatre relevés ce matin-là, et
        # il en faut cinq. Le 13/08 au matin, ce code ne rend donc pas
        # « une pente plus juste » mais PAS DE PENTE DU TOUT — et il le
        # dit dans `jeunes`. C'est la même honnêteté que le 16/08 : mieux
        # vaut refuser de calculer que trancher sur trop peu de points.
        p = pentes_des_prefixes(self.serie(), [self.SOCLE, self.NEUF])
        self.assertIn(self.NEUF, p["jeunes"], "un produit d'un seul relevé "
                                              "n'a pas de pente")
        self.assertIsNone(p["total"], "quatre relevés ne font plus une pente")

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
        # champ que `rendre()` et `main()` journalisent. Le 13/08 au
        # matin, avec la règle des cinq relevés, ce sont les DEUX
        # préfixes qui sont hors échéance — et le rapport l'écrit.
        p = pentes_des_prefixes(self.serie(), [self.SOCLE, self.NEUF])
        self.assertEqual(p["jeunes"], sorted([self.SOCLE, self.NEUF]))


class MarcheDeBucket(unittest.TestCase):
    """La panne du 10/08 relue à travers les mécanismes qui ont suivi :
    un bucket entier qui apparaît n'est qu'un paquet de préfixes neufs.
    C'est ce qui autorise `meme_perimetre` à ne plus servir qu'aux
    bancs."""

    VIEUX = "mv:fcst/2026"
    NEUF = "grids:arome/sol"

    def test_la_rafale_du_matin_ne_vaut_qu_un_point(self):
        # ⚠️ Les six relevés du 10/08 tenaient dans l'heure — deux d'entre
        # eux à 24 secondes d'écart. Ils ne comptent que pour UN point :
        # rien n'est mesurable ce matin-là, et c'est le bon résultat.
        vieux = {self.VIEUX: 0.031}
        serie = [rel(0, vieux), rel(0.01, vieux), rel(0.02, vieux),
                 rel(0.03, {**vieux, self.NEUF: 0.785})]
        p = pentes_des_prefixes(serie, [self.VIEUX, self.NEUF])
        self.assertEqual(p["jeunes"], sorted([self.VIEUX, self.NEUF]))
        self.assertIsNone(p["total"], "aucune pente n'est mesurable ici")

    def test_et_les_jours_suivants_le_bucket_apparu_est_plat(self):
        vieux = {self.VIEUX: 0.031}
        tous = {**vieux, self.NEUF: 0.785}
        serie = [rel(0, vieux), rel(0.01, vieux), rel(0.02, vieux),
                 rel(0.03, tous), rel(1, tous), rel(2, tous), rel(3, tous),
                 rel(4, tous)]
        p = pentes_des_prefixes(serie, [self.VIEUX, self.NEUF])
        self.assertAlmostEqual(p["par_prefixe"][self.NEUF], 0.0, places=6,
                               msg="0,78 Go apparus ne sont pas 0,78 Go "
                                   "de croissance")
        self.assertAlmostEqual(p["total"], 0.0, places=6)


class MarcheDeDomaine(unittest.TestCase):
    """⚠️ LA PANNE DU 16/08, REJOUÉE AVEC SES VRAIS CHIFFRES. Troisième
    marche, troisième granularité : le domaine tarn-aveyron-hérault est
    entré en production le 15/08, et `agrume/grille` est passé de 2,0016
    à 2,4223 Go en une nuit. +0,4207 Go, soit EXACTEMENT le poids du
    domaine neuf — déjà à son plateau (165 objets, comme ses deux
    voisins ; contrôle croisé : 1,238 / 0,764 = 1,62 comme le rapport
    des tailles de maille Pyrénées/Alpes).

    Mais il naît À L'INTÉRIEUR d'un préfixe déjà connu, qui avait donc
    ses trois relevés : le mécanisme du 13/08 ne pouvait rien voir, les
    moindres carrés sur trois points ont lu +6,31 Go/mois, et « palier
    dans 27 jours » est parti sur un compte à 3,40 Go sur 10.

    ⛔ Descendre encore d'un cran (profondeur 3) ne corrigeait rien :
    mesuré le 16/08 sur le compte réel, ça met 3,39 Go sur 3,41 « hors
    échéance » — un préfixe par run de `agrume/colonnes`, dont aucun
    n'atteindra jamais quatre relevés. La réponse n'était pas la
    granularité, c'était de ne plus confondre une marche avec une
    pente."""

    GRILLE = "grids:agrume/grille"
    SOCLE = "grids:socle"

    def serie(self, jours=4):
        """Les relevés réels des 14, 15 et 16/08, puis la suite au
        plateau. Le socle est constant : on isole la marche."""
        poids = [2.0016, 2.0016, 2.4223] + [2.4223] * (jours - 3)
        return [rel(j, {self.SOCLE: 0.98, self.GRILLE: p})
                for j, p in enumerate(poids)]

    def test_les_moindres_carres_explosent_bien(self):
        # Le contre-exemple, gardé : sans lui, les tests suivants
        # pourraient passer sur les deux implémentations, donc ne rien
        # vérifier. 6,31 est le chiffre qui est parti dans le mail.
        self.assertAlmostEqual(pente_go_par_mois(self.serie(3)), 6.31,
                               delta=0.05)

    def test_au_troisieme_jour_il_n_y_a_PLUS_de_pente_du_tout(self):
        # ⛔ Ce que le matin du 16/08 aurait donné avec ce code : pas une
        # pente plus juste, PAS DE PENTE. Trois points ne suffisent pas à
        # distinguer une marche d'une croissance — le dire est plus
        # honnête que trancher.
        p = pentes_des_prefixes(self.serie(3), [self.SOCLE, self.GRILLE])
        self.assertEqual(p["jeunes"], sorted([self.SOCLE, self.GRILLE]))
        self.assertIsNone(p["total"])

    def test_au_cinquieme_jour_la_marche_est_ignoree(self):
        # ⛔ Et deux jours après, quand la pente redevient calculable,
        # elle vaut ZÉRO : un domaine né à son plateau ne monte pas.
        # ⚠️ CINQUIÈME et plus quatrième depuis le 17/08 : le quantile
        # bas coûte un relevé de plus, et c'est ce qui lui permet
        # d'ignorer DEUX marches au lieu d'une.
        p = pentes_des_prefixes(self.serie(5), [self.SOCLE, self.GRILLE])
        self.assertAlmostEqual(p["par_prefixe"][self.GRILLE], 0.0, places=6)
        self.assertAlmostEqual(p["par_prefixe"][self.SOCLE], 0.0, places=6)

    def test_et_le_mail_ne_part_plus(self):
        inv = {"octets": int(3.4049 * GO), "objets": 1913,
               "par_bucket": {}, "par_prefixe": {}}
        juste = pentes_des_prefixes(self.serie(5),
                                    [self.SOCLE, self.GRILLE])["total"]
        self.assertTrue(verdict(inv, pente_go_par_mois(self.serie(3)),
                                seuil_go=7.0, horizon=60)["alerte"],
                        "le 16/08 au matin, l'alerte est bien partie")
        self.assertFalse(verdict(inv, juste, seuil_go=7.0,
                                 horizon=60)["alerte"],
                         "et elle ne doit plus partir")


class PenteRobuste(unittest.TestCase):
    """Les propriétés du calcul du 16/08, isolées de tout contexte."""

    def test_moins_de_cinq_releves_pas_de_pente(self):
        serie = [rel(j, {"a": 1.0 + j}) for j in (0, 1, 2, 3)]
        self.assertIsNone(pente_du_prefixe(serie, "a"))

    def test_cinq_releves_suffisent(self):
        serie = [rel(j, {"a": 1.0 + j}) for j in (0, 1, 2, 3, 4)]
        self.assertAlmostEqual(pente_du_prefixe(serie, "a"), 30.0, places=6)

    def test_une_marche_isolee_ne_peut_pas_etre_la_pente(self):
        # ⛔ La propriété du 16/08, rejouée sur le calcul du 17/08 : une
        # marche unique, où qu'elle tombe dans la série, ne fabrique
        # aucune pente. Cinq relevés au lieu de quatre — c'est le prix
        # du quantile bas, et il est payé une fois pour toutes.
        for rang in range(4):
            poids = [1.0 if k <= rang else 6.0 for k in range(5)]
            serie = [rel(j, {"a": p}) for j, p in enumerate(poids)]
            self.assertAlmostEqual(
                pente_du_prefixe(serie, "a"), 0.0, places=6,
                msg=f"marche au rang {rang} : {poids}")

    def test_DEUX_marches_dans_la_fenetre_ne_font_pas_de_pente(self):
        # ⛔ LA PANNE DU 17/08, réduite à sa loi. La médiane du 16/08
        # tenait à ce qu'il n'y ait qu'UNE marche parmi trois
        # différences ; deux marches consécutives et elle tombe dessus.
        # Le 25e centile de quatre différences ignore les DEUX plus
        # grandes — c'est exactement ce qu'il fallait.
        for a in range(4):
            for b in range(a + 1, 4):
                poids = [1.0] * 5
                for k in range(5):
                    poids[k] += (2.0 if k > a else 0.0) + (3.0 if k > b else 0.0)
                serie = [rel(j, {"a": p}) for j, p in enumerate(poids)]
                self.assertAlmostEqual(
                    pente_du_prefixe(serie, "a"), 0.0, places=6,
                    msg=f"marches aux rangs {a} et {b} : {poids}")

    def test_les_vrais_chiffres_de_la_nuit_du_17_08(self):
        # ⛔ Les relevés RÉELS de `agrume/grille` des 14, 15, 16 et 17/08
        # (2,0016 · 2,0016 · 2,4223 · 4,0540 Go), plus la nuit suivante.
        # La médiane du 16/08 a lu +11,12 Go/mois sur les quatre premiers
        # et le mail est parti alors que l'index réclamait 496 clés sur
        # 496 et que le plateau valait 3,375 Go.
        #
        # ⚠️ Deux cinquièmes relevés possibles, et AUCUN ne doit faire
        # partir d'échéance : le plateau propre (3,375 — la purge a mordu
        # avant l'audit) et le plateau + un run en vol (4,054 — l'audit
        # est retombé dans la fenêtre de publication). Le second est le
        # cas gênant : il ne DÉCROÎT pas, il stagne à une valeur haute.
        for cinquieme in (3.3750, 4.0540):
            reel = [2.0016, 2.0016, 2.4223, 4.0540, cinquieme]
            serie = [rel(j, {"a": p}) for j, p in enumerate(reel)]
            pente = pente_du_prefixe(serie, "a")
            self.assertLessEqual(pente, 1e-6, f"5e relevé = {cinquieme}")
            inv = {"octets": int(4.4 * GO), "objets": 1969,
                   "par_bucket": {}, "par_prefixe": {}}
            self.assertFalse(
                verdict(inv, pente, seuil_go=7.0, horizon=60)["alerte"],
                f"le mail du 17/08 ne doit plus partir ({cinquieme})")

    def test_deux_releves_a_24_secondes_ne_font_pas_une_vitesse(self):
        # ⚠️ Le piège que la médiane INTRODUIT et que les moindres carrés
        # noyaient : 0,784 Go divisés par 24 secondes valent 2,8 millions
        # de Go/mois. Sur une série courte, cette valeur pourrait très
        # bien être la médiane. D'où le regroupement.
        rafale = [rel(0.0, {"a": 0.031}), rel(24 / 86400, {"a": 0.031}),
                  rel(0.02, {"a": 0.815}), rel(0.03, {"a": 0.815})]
        self.assertIsNone(pente_du_prefixe(rafale, "a"),
                          "une rafale d'une heure ne vaut qu'un point")

    def test_la_rafale_ne_pollue_pas_une_vraie_serie(self):
        serie = [rel(0.0, {"a": 1.0}), rel(0.01, {"a": 1.0}),
                 rel(0.02, {"a": 1.0}), rel(1, {"a": 1.0}),
                 rel(2, {"a": 1.0}), rel(3, {"a": 1.0}), rel(4, {"a": 1.0})]
        self.assertAlmostEqual(pente_du_prefixe(serie, "a"), 0.0, places=6)

    def test_une_decroissance_reste_une_decroissance(self):
        # Un produit qui se range doit se lire comme tel, sinon la purge
        # qui mord ressemblerait à un plateau.
        serie = [rel(j, {"a": 4.0 - j}) for j in (0, 1, 2, 3, 4)]
        self.assertAlmostEqual(pente_du_prefixe(serie, "a"), -30.0, places=6)


class PenteParPrefixe(unittest.TestCase):
    def test_absence_n_est_pas_zero(self):
        # ⚠️ Le piège central. Un préfixe absent d'un relevé est un
        # SILENCE (produit pas né, ou couverture partielle ce jour-là).
        # Le lire comme 0 fabriquerait la marche qu'on vient de tuer.
        serie = [rel(0, {"a": 1.0}), rel(1, {"a": 1.0}),
                 rel(2, {"a": 1.0, "b": 1.0}),
                 rel(3, {"a": 1.0, "b": 2.0}),
                 rel(4, {"a": 1.0, "b": 3.0}),
                 rel(5, {"a": 1.0, "b": 4.0}),
                 rel(6, {"a": 1.0, "b": 5.0})]
        self.assertAlmostEqual(pente_du_prefixe(serie, "b"), 30.0, places=6)

    def test_absence_ne_compte_pas_comme_un_releve(self):
        # ⚠️ La seconde moitié du même piège, et celle qui reste mordante
        # depuis le 16/08 : compter les absences comme des zéros
        # donnerait 4 relevés à « b » là où il n'en a que 2, et le
        # sortirait de `jeunes` deux jours trop tôt — c'est-à-dire au
        # moment précis où sa marche de naissance est encore dans la
        # série.
        serie = [rel(0, {"a": 1.0}), rel(1, {"a": 1.0}),
                 rel(2, {"a": 1.0, "b": 1.0}),
                 rel(3, {"a": 1.0, "b": 1.0}),
                 rel(4, {"a": 1.0}), rel(5, {"a": 1.0})]
        p = pentes_des_prefixes(serie, ["a", "b"])
        self.assertEqual(p["jeunes"], ["b"])
        self.assertAlmostEqual(p["total"], 0.0, places=6)

    def test_la_somme_fait_le_total(self):
        serie = [rel(j, {"a": 1.0 + j, "b": 2.0 + 2 * j})
                 for j in (0, 1, 2, 3, 4)]
        p = pentes_des_prefixes(serie, ["a", "b"])
        self.assertAlmostEqual(p["par_prefixe"]["a"], 30.0, places=6)
        self.assertAlmostEqual(p["par_prefixe"]["b"], 60.0, places=6)
        self.assertAlmostEqual(p["total"], 90.0, places=6)

    def test_un_prefixe_disparu_ne_compte_plus(self):
        # Une chaîne qu'on arrête laisse sa pente dans l'historique. La
        # compter encore projetterait une croissance qui n'existe plus.
        serie = [rel(j, {"a": 1.0, "mort": float(j)})
                 for j in (0, 1, 2, 3, 4)]
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


class Rapprochement(unittest.TestCase):
    """⛔ LE CONTRAT DE COMPTABILITÉ, et la raison pour laquelle la pente
    ne peut pas le remplacer.

    Une jauge qui n'a que la pente est aveugle à une croissance faite
    UNIQUEMENT de marches : un domaine de plus, une boîte élargie, et
    aucune tendance n'apparaît jamais. Or ces produits publient un index
    qui déclare, clé par clé, tout ce qui doit exister — la vraie
    question n'est donc pas « combien ça pèse » mais **« est-ce que tout
    ce qui est là est réclamé par quelqu'un »**.

    Chiffres du 16/08, mesurés sur R2 avant d'écrire le code :
    `agrume/grille` 496 présentes / 496 réclamées (0 orphelin) et
    `agrume/pi/grille` 25 présentes / 7 réclamées — les 18 orphelins du
    `TypeError` de `purger()` des 12-13/08, toujours là."""

    CLE = "agrume/grille/index.json"
    PREF = "agrume/grille/"

    def index(self, *runs, restes=()):
        return {"produit": "agrume-grille", "retention_runs": 3,
                "runs": [{"run": r, "domaine": d, "cles": list(c)}
                         for r, d, c in runs],
                "restes": list(restes)}

    def objets(self, *cles):
        return [("grids", c, 1_000_000) for c in cles]

    def test_tout_est_reclame(self):
        idx = self.index(("R1", "alpes", [self.PREF + "alpes/R1/e00.bin"]))
        r = rapprocher(idx, self.CLE, self.PREF,
                       self.objets(self.PREF + "alpes/R1/e00.bin", self.CLE))
        self.assertEqual(r["orphelins"], [])
        self.assertEqual(r["manquants"], [])
        self.assertEqual(r["presentes"], 2)

    def test_l_index_se_reclame_lui_meme(self):
        # Sinon `index.json` serait éternellement son propre orphelin.
        r = rapprocher(self.index(), self.CLE, self.PREF,
                       self.objets(self.CLE))
        self.assertEqual(r["orphelins"], [])

    def test_un_objet_que_personne_ne_reclame_est_un_orphelin(self):
        # ⛔ Le cas des 12-13/08 : `purger()` lève, les clés restent, et
        # rien dans le poids ne le dit — 24 Mo sur un compte de 3,4 Go.
        idx = self.index(("R2", "alpes", [self.PREF + "alpes/R2/e00.bin"]))
        r = rapprocher(idx, self.CLE, self.PREF, self.objets(
            self.CLE, self.PREF + "alpes/R2/e00.bin",
            self.PREF + "alpes/R1/e00.bin", self.PREF + "alpes/R1/e01.bin"))
        self.assertEqual(len(r["orphelins"]), 2)
        self.assertEqual(r["octets_orphelins"], 2_000_000)
        self.assertIn(self.PREF + "alpes/R1/e00.bin", r["orphelins"])

    def test_une_cle_declaree_mais_absente_est_un_MANQUANT(self):
        # L'autre sens, plus grave : le produit servi a des trous et
        # c'est l'index qui ment. Ne pas confondre les deux.
        idx = self.index(("R1", "alpes", [self.PREF + "alpes/R1/e00.bin",
                                          self.PREF + "alpes/R1/e01.bin"]))
        r = rapprocher(idx, self.CLE, self.PREF,
                       self.objets(self.CLE, self.PREF + "alpes/R1/e00.bin"))
        self.assertEqual(r["manquants"], [self.PREF + "alpes/R1/e01.bin"])
        self.assertEqual(r["orphelins"], [])

    def test_un_reste_n_est_pas_un_orphelin_mais_est_compte(self):
        # Une suppression ratée est DÉJÀ connue de l'index et reprise au
        # run suivant. L'accuser d'orphelinat ferait crier sur un
        # mécanisme qui fonctionne — mais la taire ferait disparaître de
        # la place payée pour rien.
        mort = self.PREF + "alpes/R0/e00.bin"
        idx = self.index(("R1", "alpes", [self.PREF + "alpes/R1/e00.bin"]),
                         restes=[mort])
        r = rapprocher(idx, self.CLE, self.PREF, self.objets(
            self.CLE, self.PREF + "alpes/R1/e00.bin", mort))
        self.assertEqual(r["orphelins"], [])
        self.assertEqual(r["restes_presents"], [mort])

    def test_un_autre_prefixe_n_est_pas_concerne(self):
        # `agrume/colonnes` n'a pas d'index (il se purge par
        # arithmétique) : le rapprochement ne doit pas le regarder, et
        # surtout pas le déclarer orphelin en bloc.
        idx = self.index(("R1", "alpes", [self.PREF + "alpes/R1/e00.bin"]))
        r = rapprocher(idx, self.CLE, self.PREF, self.objets(
            self.CLE, self.PREF + "alpes/R1/e00.bin",
            "agrume/colonnes/R1/colonnes.npz"))
        self.assertEqual(r["orphelins"], [])
        self.assertEqual(r["presentes"], 2)

    def test_un_index_VIDE_rend_tout_orphelin(self):
        # ⛔ C'est une information, pas une panne : un produit qui perd
        # son index ne sait plus rien purger (incident des 12-13/08). Ça
        # DOIT crier.
        r = rapprocher(self.index(), self.CLE, self.PREF, self.objets(
            self.CLE, self.PREF + "alpes/R1/e00.bin"))
        self.assertEqual(len(r["orphelins"]), 1)

    def test_un_index_ILLISIBLE_ne_rend_pas_zero_orphelin(self):
        # ⚠️ Le piège central, jumeau de `couverture_partielle` : un
        # rapprochement qui n'a pas eu lieu ne doit jamais se lire comme
        # un rapprochement réussi.
        r = rapprocher(None, self.CLE, self.PREF, self.objets(self.CLE))
        self.assertFalse(r["lu"])
        self.assertNotIn("orphelins", r)

    # ── ce que le verdict en fait ────────────────────────────────────
    def inv(self, go=3.4):
        return {"octets": int(go * GO), "objets": 1,
                "par_bucket": {}, "par_prefixe": {}}

    def test_un_orphelin_suffit_a_declencher(self):
        # ⛔ Pas de seuil de tolérance : un seuil ici serait une fuite
        # qu'on autorise. Et le niveau (3,4 Go) comme la pente (0) sont
        # parfaitement calmes — c'est bien le rapprochement qui parle.
        idx = self.index()
        r = rapprocher(idx, self.CLE, self.PREF,
                       self.objets(self.CLE, self.PREF + "alpes/R1/e00.bin"))
        v = verdict(self.inv(), 0.0, rapprochements=[r])
        self.assertTrue(v["alerte"])
        self.assertIn("ORPHELIN", v["motifs"][0])

    def test_le_motif_NOMME_le_produit_et_le_poids(self):
        # Un mail qui dit « orphelins » sans dire lesquels oblige à
        # rouvrir un terminal pour savoir quoi faire.
        r = rapprocher(self.index(), self.CLE, self.PREF,
                       self.objets(self.CLE, self.PREF + "alpes/R1/e00.bin"))
        m = verdict(self.inv(), 0.0, rapprochements=[r])["motifs"][0]
        self.assertIn(self.PREF, m)
        self.assertIn("0.001 Go", m)

    def test_un_rapprochement_impossible_est_un_motif(self):
        v = verdict(self.inv(), 0.0,
                    rapprochements=[rapprocher(None, self.CLE, self.PREF, [])])
        self.assertTrue(v["alerte"])
        self.assertIn("RAPPROCHEMENT IMPOSSIBLE", v["motifs"][0])

    def test_tout_propre_ne_dit_rien(self):
        # L'autre moitié : pas de cri au loup. Un produit à son plateau,
        # même gros, même après un agrandissement, reste silencieux.
        idx = self.index(("R1", "alpes", [self.PREF + "alpes/R1/e00.bin"]))
        r = rapprocher(idx, self.CLE, self.PREF,
                       self.objets(self.CLE, self.PREF + "alpes/R1/e00.bin"))
        v = verdict(self.inv(), 0.0, rapprochements=[r])
        self.assertFalse(v["alerte"], f"faux positif : {v['motifs']}")

    def test_sans_rapprochement_le_verdict_est_celui_d_avant(self):
        # Compatibilité : appelé sans l'argument, rien ne change.
        self.assertFalse(verdict(self.inv(), 0.0)["alerte"])


class MarcheEtOrphelin(unittest.TestCase):
    """⛔ LA QUESTION DE YANN, LE 16/08 : « si j'agrandis la boîte des
    Alpes, on risque d'avoir la même chose — mais il ne faut pas non
    plus qu'elle ne fasse plus son travail. »

    Les deux moitiés, sur le MÊME jeu : un agrandissement (le poids
    double, l'index suit) doit être MUET, et une purge qui cesse de
    mordre (le poids double, l'index ne suit pas) doit CRIER. C'est
    précisément ce qu'une pente, quelle qu'elle soit, ne peut pas
    distinguer — les deux séries de poids sont identiques."""

    CLE = "agrume/grille/index.json"
    PREF = "agrume/grille/"

    def cles(self, run, n=4):
        return [f"{self.PREF}alpes/{run}/e{i:02d}.bin" for i in range(n)]

    def test_agrandir_la_boite_ne_cree_AUCUN_orphelin(self):
        # Même nombre d'objets, deux fois plus lourds : l'index déclare
        # exactement les mêmes clés. Rien à signaler.
        idx = {"runs": [{"cles": self.cles("R1")}], "restes": []}
        gros = [("grids", c, 2_000_000) for c in self.cles("R1")]
        r = rapprocher(idx, self.CLE, self.PREF,
                       gros + [("grids", self.CLE, 500)])
        self.assertEqual(r["orphelins"], [])
        self.assertFalse(verdict({"octets": int(4.9 * GO), "objets": 1,
                                  "par_bucket": {}, "par_prefixe": {}},
                                 0.0, rapprochements=[r])["alerte"])

    def test_une_purge_qui_ne_mord_plus_CRIE_des_la_nuit_suivante(self):
        # Poids identique au cas précédent (2 runs légers = 1 run gros),
        # mais un run que l'index ne réclame plus. La pente ne peut PAS
        # les distinguer ; le rapprochement, si — et tout de suite.
        idx = {"runs": [{"cles": self.cles("R2")}], "restes": []}
        objets = [("grids", c, 1_000_000)
                  for c in self.cles("R1") + self.cles("R2")]
        r = rapprocher(idx, self.CLE, self.PREF,
                       objets + [("grids", self.CLE, 500)])
        self.assertEqual(len(r["orphelins"]), 4)
        v = verdict({"octets": int(4.9 * GO), "objets": 1,
                     "par_bucket": {}, "par_prefixe": {}},
                    0.0, rapprochements=[r])
        self.assertTrue(v["alerte"])

    def test_les_deux_cas_pesent_PAREIL(self):
        # ⛔ Le contrôle qui donne son sens aux deux précédents : si les
        # poids différaient, on n'aurait pas prouvé que le poids ne
        # suffit pas.
        gros = sum(2_000_000 for _ in self.cles("R1"))
        deux_runs = sum(1_000_000 for _ in self.cles("R1") + self.cles("R2"))
        self.assertEqual(gros, deux_runs)


class PublicationEnVol(unittest.TestCase):
    """⛔ LA COURSE DU 17/08, ET LA MOITIÉ QU'ELLE NE DOIT PAS EMPORTER.

    L'audit de 04:32 UTC est tombé dans la fenêtre de publication du
    réseau 00 Z : 82 objets écrits (les 55 clés de `nord-alpes/00Z` et 27
    des 55 de `pyrenees/00Z`, 0,679 Go), index pas encore réécrit — il
    l'a été à 05:29. Le mail a dit « la purge de ce produit ne mord
    plus » alors que le contrôle du même matin donnait 496 présentes /
    496 réclamées, 0 orphelin, plateau 3,375 Go.

    Les deux moitiés du contrat, sur le MÊME jeu de clés : un run en vol
    doit être MUET, et les mêmes clés encore là demain matin doivent
    CRIER. La seule chose qui les sépare est l'ÂGE — et c'est ce qui
    interdit de lire ce mécanisme comme un seuil de tolérance."""

    CLE = "agrume/grille/index.json"
    PREF = "agrume/grille/"
    T = datetime(2026, 8, 17, 4, 32, tzinfo=timezone.utc)

    def index(self, *cles):
        return {"retention_runs": 3, "runs": [{"cles": list(cles)}],
                "restes": []}

    def run_00z(self, n=82):
        """Les 82 clés du run en cours de publication, telles que le
        listing les a rendues : avec leur `LastModified`."""
        return [(f"{self.PREF}nord-alpes/2026-08-17T00:00:00Z/e{i:02d}.bin",
                 8_280_000) for i in range(n)]

    def objets(self, cles, minutes_avant):
        # ⓘ `index.json` est TOUJOURS dans le listing — l'oublier ferait
        #   crier « clé déclarée mais absente », qui est l'autre moitié du
        #   rapprochement et un autre bug que celui qu'on teste ici.
        ecrit = self.T - timedelta(minutes=minutes_avant)
        return ([("grids", c, t, ecrit) for c, t in cles]
                + [("grids", self.CLE, 500, ecrit)])

    def inv(self):
        return {"octets": int(5.096 * GO), "objets": 2045,
                "par_bucket": {}, "par_prefixe": {}}

    def test_un_run_en_vol_n_est_PAS_un_orphelin(self):
        r = rapprocher(self.index(), self.CLE, self.PREF,
                       self.objets(self.run_00z(), minutes_avant=8),
                       maintenant=self.T)
        self.assertEqual(r["orphelins"], [], "82 faux orphelins, le 17/08")
        self.assertEqual(len(r["en_vol"]), 82)
        self.assertEqual(r["octets_en_vol"], 82 * 8_280_000)

    def test_et_le_mail_ne_part_plus(self):
        r = rapprocher(self.index(), self.CLE, self.PREF,
                       self.objets(self.run_00z(), minutes_avant=8),
                       maintenant=self.T)
        v = verdict(self.inv(), None, rapprochements=[r])
        self.assertFalse(v["alerte"], f"faux positif : {v['motifs']}")

    def test_les_MEMES_cles_le_lendemain_matin_CRIENT(self):
        # ⛔ L'autre moitié, et celle qui fait que ce n'est pas un
        # bâillon : une publication qui ne s'est jamais déclarée est une
        # vraie fuite, et elle est nommée à l'audit suivant.
        r = rapprocher(self.index(), self.CLE, self.PREF,
                       self.objets(self.run_00z(), minutes_avant=24 * 60),
                       maintenant=self.T)
        self.assertEqual(len(r["orphelins"]), 82)
        self.assertEqual(r["en_vol"], [])
        self.assertTrue(verdict(self.inv(), None,
                                rapprochements=[r])["alerte"])

    def test_la_frontiere_est_le_delai_pas_le_nombre(self):
        # Un SEUL objet non réclamé, mais vieux de quatre heures : ça
        # crie. Le mécanisme ne tolère aucun orphelin — il attend
        # seulement que la publication ait eu le temps de se déclarer.
        r = rapprocher(self.index(), self.CLE, self.PREF,
                       self.objets(self.run_00z(1), minutes_avant=4 * 60),
                       maintenant=self.T)
        self.assertEqual(len(r["orphelins"]), 1)
        self.assertTrue(verdict(self.inv(), None,
                                rapprochements=[r])["alerte"])

    def test_les_18_orphelins_du_12_08_crient_toujours(self):
        # La non-régression qui compte : le cas réel que ce contrôle
        # existe pour attraper avait TROIS JOURS d'âge.
        r = rapprocher(self.index(), self.CLE, self.PREF,
                       self.objets(self.run_00z(18), minutes_avant=3 * 24 * 60),
                       maintenant=self.T)
        self.assertEqual(len(r["orphelins"]), 18)

    def test_sans_date_un_objet_est_juge_ANCIEN(self):
        # ⚠️ Le même principe que `lu=False` : une vérification qui n'a
        # pas pu avoir lieu ne doit jamais se lire comme une vérification
        # réussie. Si l'absence de date valait grâce, un listing qui
        # cesse de rendre `LastModified` bâillonnerait la jauge en
        # silence — et c'est aussi ce qui garde valables les bancs
        # d'avant le 17/08, écrits avec des triplets.
        r = rapprocher(self.index(), self.CLE, self.PREF,
                       [("grids", c, t) for c, t in self.run_00z(3)]
                       + [("grids", self.CLE, 500)],
                       maintenant=self.T)
        self.assertEqual(len(r["orphelins"]), 3)
        self.assertEqual(r["en_vol"], [])

    def test_un_objet_reclame_ne_regarde_pas_l_age(self):
        # Un objet réclamé par l'index est légitime, neuf ou vieux : la
        # grâce ne s'applique qu'à ce que personne ne réclame.
        cles = self.run_00z(4)
        r = rapprocher(self.index(*[c for c, _ in cles]),
                       self.CLE, self.PREF,
                       self.objets(cles, minutes_avant=5 * 24 * 60),
                       maintenant=self.T)
        self.assertEqual(r["orphelins"], [])
        self.assertEqual(r["en_vol"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
