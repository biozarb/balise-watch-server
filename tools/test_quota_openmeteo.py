#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  test_quota_openmeteo.py — le banc du budget partagé (09/08/2026)
#
#  ⚠️ CE BANC EXISTE POUR RÉPONDRE À UNE QUESTION PRÉCISE : le seau
#  ASSERVIT-IL, ou DÉCORE-T-IL ? Un compteur qu'on n'a testé qu'à
#  latence nominale et à un seul consommateur n'est pas un budget
#  partagé, c'est une jolie trace. Les quatre épreuves qui comptent :
#
#    · la cadence pondérée obtenue ne doit pas bouger quand la latence
#      varie de 0,05 s à 0,40 s (sinon le seau n'asservit rien) ;
#    · deux processus concurrents ne doivent jamais tirer le même jeton ;
#    · un fichier d'état corrompu ne doit pas arrêter la collecte ;
#    · la nuit du 09/08, rejouée, doit produire un TROU DÉCLARÉ et non
#      un run tué.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import quota_openmeteo as qo                             # noqa: E402
from quota_openmeteo import (  # noqa: E402
    Budget, BudgetRefuse, FENETRES, PAUSE_REPLI_S, PLAFOND_HEURE,
    PLAFOND_JOUR, PLAFOND_MINUTE, PLAFOND_MOIS, plafond_effectif,
    plafond_mois_effectif, poids, poids_url,
)


class Horloge:
    """Temps simulé : `dormir` avance la montre, rien n'attend vraiment.

    ⚠️ Sans elle, un banc qui vérifie une fenêtre d'une heure durerait
    une heure. Avec elle il dure 20 ms — et c'est la seule raison pour
    laquelle le cas « heure » est réellement testé plutôt que raisonné.
    """

    def __init__(self, t0: float = 1_000_000.0) -> None:
        self.t = t0

    def maintenant(self) -> float:
        return self.t

    def dormir(self, s: float) -> None:
        self.t += s

    def avancer(self, s: float) -> None:
        self.t += s


class BaseBudget(unittest.TestCase):

    def setUp(self) -> None:
        self.dossier = tempfile.TemporaryDirectory()
        self.chemin = Path(self.dossier.name) / "openmeteo.json"
        self.horloge = Horloge()
        self.muet = open(os.devnull, "w")

    def tearDown(self) -> None:
        self.muet.close()
        self.dossier.cleanup()

    def budget(self, nom="essai", **kw) -> Budget:
        kw.setdefault("attente_max_s", 300.0)
        return Budget(nom, chemin=self.chemin,
                      horloge=self.horloge.maintenant,
                      dormir=self.horloge.dormir,
                      journal=self.muet, **kw)


# ══════════════════════════════════════════════════════════════════
#  1. LE POIDS EST CALCULÉ, PAS RECOPIÉ
# ══════════════════════════════════════════════════════════════════

class TestPoids(BaseBudget):

    def test_poids_du_09_08(self):
        """8 variables × 10 modèles = 8,0 — la valeur du run qui a cassé."""
        self.assertAlmostEqual(poids(8, 10), 8.0)

    def test_poids_du_08_08(self):
        """5 variables × 10 modèles = 5,0 — la veille, qui passait."""
        self.assertAlmostEqual(poids(5, 10), 5.0)

    def test_une_variable_de_plus_change_le_poids(self):
        """⚠️ LE BANC QUI ATTRAPE LA PANNE DU 09/08 AVANT QU'ELLE ARRIVE.

        Si quelqu'un ajoute une variable, le poids DOIT bouger. Un `8`
        en dur passerait ce test sans broncher — c'est pour ça qu'il
        n'y a pas de `8` en dur.
        """
        self.assertGreater(poids(9, 10), poids(8, 10))

    def test_refuse_l_absurde(self):
        with self.assertRaises(ValueError):
            poids(0, 10)


class TestPlancher(BaseBudget):
    """⭐⭐ LE PLANCHER D'UN APPEL — LE BANC QUI MANQUAIT LE 23/08.

    Le lot S0.11 avait un banc VERT qui affirmait « 1,40 pondéré par
    point, mesuré sur l'URL RÉELLE ». Il mesurait l'accord du code avec
    lui-même. Open-Meteo, lui, facture AU MINIMUM UN APPEL par requête :
    les deux requêtes de la passe candidates pesaient 0,8 et 0,6, le
    compteur disait 1,40, le serveur comptait 2,00, et le run a heurté
    le plafond horaire au point ~2 500 — à l'unité près.

    Ces épreuves-ci ne peuvent pas être vertes par construction : elles
    disent ce que le SERVEUR fait, et elles auraient été rouges le
    23/08.
    """

    def test_une_requete_minuscule_coute_un_appel(self):
        """0,8 et 0,6 pondérés — les deux requêtes qui ont tué le run."""
        self.assertAlmostEqual(poids(4, 2), 1.0)     # 2 modèles × 4 vars
        self.assertAlmostEqual(poids(2, 3), 1.0)     # 3 modèles × 2 vars

    def test_la_plus_petite_requete_possible_coute_un_appel(self):
        self.assertAlmostEqual(poids(1, 1), 1.0)

    def test_au_dessus_du_plancher_la_formule_est_intacte(self):
        """⚠️ Le plancher ne doit RIEN changer au-dessus de 1.

        C'est ce qui garantit que la passe Pioupiou (1,6 et 4,2) n'a pas
        bougé d'un pondéré, et que les chiffres des lots précédents
        restent lisibles.
        """
        self.assertAlmostEqual(poids(8, 2), 1.6)
        self.assertAlmostEqual(poids(6, 7), 4.2)
        self.assertAlmostEqual(poids(8, 10), 8.0)

    def test_deux_requetes_sous_le_plancher_coutent_deux_appels(self):
        """⛔ LE CHIFFRE EXACT DE LA NUIT DU 23 AU 24/08.

        Découper une requête en deux ne divise pas son coût quand les
        deux moitiés tombent sous le plancher : 0,8 + 0,6 = 1,4 en
        arithmétique, 1 + 1 = 2 en appels facturés. C'est la ligne qui
        rend le découpage visiblement inutile.
        """
        decoupe = poids(4, 2) + poids(2, 3)
        fusionne = poids(4, 5)                       # 5 modèles × 4 vars
        self.assertAlmostEqual(decoupe, 2.0)
        self.assertAlmostEqual(fusionne, 2.0)
        self.assertAlmostEqual(decoupe, fusionne)

    def test_le_plancher_se_dissout_dans_un_lot_de_lieux(self):
        """⭐ La propriété qui ouvrira la porte aux lots de points.

        Open-Meteo compte les LIEUX comme un multiplicateur. Cent points
        envoyés un par un coûtent 100 × max(1 ; 0,2) = 100 appels ; les
        mêmes cent dans une seule requête pèsent 100 × 0,2 = 20. Le
        plancher ne disparaît pas — il cesse simplement de mordre.
        """
        un_par_un = 100 * poids(2, 1)
        en_lot = poids(2, 100)                       # 100 lieux, 2 vars
        self.assertAlmostEqual(un_par_un, 100.0)
        self.assertAlmostEqual(en_lot, 20.0)
        self.assertLess(en_lot, un_par_un)


class TestPoidsUrl(BaseBudget):
    """Le poids lu sur l'URL — la forme qui ne peut pas dériver."""

    URL_COLLECT = ("https://api.open-meteo.com/v1/forecast?latitude=45.0000"
                   "&longitude=6.0000&hourly=wind_speed_10m,wind_direction_10m,"
                   "wind_gusts_10m,precipitation,pressure_msl,temperature_2m,"
                   "wind_speed_700hPa,wind_direction_700hPa&models=a,b,c,d,e,"
                   "f,g,h,i&forecast_days=3")

    def test_l_url_de_collect_pese_ce_qu_elle_pese(self):
        """8 variables × 9 modèles × 1 lieu = 7,2 — le run d'après lot."""
        self.assertAlmostEqual(poids_url(self.URL_COLLECT), 7.2)

    def test_une_variable_ajoutee_a_l_url_change_le_poids(self):
        """⚠️ L'ÉPREUVE QUI REND LA PANNE DU 09/08 IMPOSSIBLE À REJOUER.

        Personne n'a à recompter : l'URL parle.
        """
        avant = poids_url(self.URL_COLLECT)
        apres = poids_url(self.URL_COLLECT.replace(
            "&models=", ",cape&models=", 1))       # une variable de plus
        self.assertGreater(apres, avant)
        # ⚠️ L'écart est 1 × 9 / 10 = 0,9, PAS `poids(1, 9)` — qui vaut
        # 1,0 depuis que le plancher existe (24/08). Un plancher se
        # compare à un TOTAL de requête, jamais à un écart entre deux
        # totaux : les deux requêtes ici pèsent 7,2 et 8,1, toutes deux
        # bien au-dessus, donc aucune des deux n'est planchée et la
        # différence est purement arithmétique.
        self.assertAlmostEqual(apres - avant, 0.9)

    def test_les_lieux_multiples_comptent(self):
        """⚠️ Le facteur qu'on oublie. `backfill_packs.py` envoie des
        lots de points dans UNE requête ; sans ce facteur, son poids
        serait sous-estimé d'un ordre de grandeur — et le budget
        mentirait du côté qui ne protège pas.

        ⚠️ **LA PROPORTIONNALITÉ SE MESURE AU-DESSUS DU PLANCHER**
        (24/08). Avec deux variables, une requête à un lieu pèse 0,2 et
        se fait plancher à 1,0 : comparer 10 lieux (2,0) à 10 fois un
        lieu (10,0) ne mesurerait plus le facteur `lieux`, mais le
        plancher. On prend donc une requête déjà au-dessus de 1.
        """
        vars_ = ",".join(f"v{i}" for i in range(12))    # 12 vars → 1,2
        un = f"https://x/v1/forecast?latitude=45.0&longitude=6.0&hourly={vars_}"
        dix = ("https://x/v1/forecast?latitude=" + ",".join(["45.0"] * 10) +
               "&longitude=" + ",".join(["6.0"] * 10) + f"&hourly={vars_}")
        self.assertAlmostEqual(poids_url(un), 1.2)
        self.assertAlmostEqual(poids_url(dix), poids_url(un) * 10)

    def test_sans_modele_explicite_compte_pour_un(self):
        """5 variables, 1 modèle implicite, 1 lieu = 0,5 pondéré —
        **et 1,0 facturé**, parce qu'un appel HTTP ne coûte jamais moins
        d'un appel (débug du 24/08). L'ancienne attente, 0,5, décrivait
        l'arithmétique et non le serveur.
        """
        url = "https://x/v1/archive?latitude=45.0&longitude=6.0&hourly=a,b,c,d,e"
        self.assertAlmostEqual(poids_url(url), 1.0)


# ══════════════════════════════════════════════════════════════════
#  2. LE SEAU ASSERVIT — LA LATENCE SORT DE L'ÉQUATION
# ══════════════════════════════════════════════════════════════════

class TestAsservissement(BaseBudget):

    def _duree_pour(self, latence_s: float, n: int = 300) -> float:
        """Temps mis pour `n` points, à une latence SIMULÉE donnée.

        ⚠️ ON MESURE UNE DURÉE, PAS UNE « CADENCE MOYENNE », ET C'EST
        UNE CORRECTION DE CE BANC, PAS UNE FACILITÉ. La première version
        divisait le poids total par la durée totale et trouvait 778
        pondérés/min sur un plafond de 540 — de quoi croire le seau
        cassé. Il ne l'était pas : sur une fenêtre GLISSANTE partie
        vide, les 67 premiers points passent d'un coup, et aucune
        fenêtre de 60 s ne dépasse jamais la ligne (c'est ce que vérifie
        `test_la_minute_n_est_jamais_franchie`). C'est la moyenne qui
        mentait, en étalant ce démarrage sur toute la durée.

        La bonne question n'est donc pas « quelle moyenne ? » mais
        « la latence change-t-elle quoi que ce soit ? ». Réponse
        attendue : non, à la latence près elle-même.
        """
        b = self.budget("collect")
        p = poids(8, 10)
        t0 = self.horloge.maintenant()
        for _ in range(n):
            b.demander(p)
            self.horloge.avancer(latence_s)     # l'aller-retour réseau
        return self.horloge.maintenant() - t0

    def test_latence_rapide_et_lente_donnent_la_meme_cadence(self):
        """⚠️ L'ÉPREUVE CENTRALE DU LOT.

        Le 09/08, la latence est tombée de 0,22 s à 0,06 s et la cadence
        est montée de 522 à 631 pondérés/min — un réseau plus rapide
        faisait DÉPASSER le plafond. Ici, les deux latences doivent
        donner la même durée à quelques secondes près : c'est le seau
        qui commande, plus le réseau. Si ce test échoue, le seau décore
        au lieu d'asservir.
        """
        n = 300
        rapide = self._duree_pour(0.05, n)
        self.tearDown()          # état neuf entre les deux latences
        self.setUp()
        lente = self._duree_pour(0.40, n)
        # L'écart ne peut venir que de la latence elle-même, et encore :
        # elle est absorbée par l'attente, pas ajoutée à elle.
        self.assertAlmostEqual(rapide, lente, delta=n * 0.40,
                               msg="la latence commande encore la cadence")
        # Et le débit soutenu — hors remplissage initial — tient la ligne.
        p = poids(8, 10)
        soutenu = (n * p) / (max(rapide, lente) / 60.0)
        self.assertLessEqual(soutenu, plafond_effectif("minute") * 1.25)

    def test_aucune_constante_de_latence_dans_le_module(self):
        """⚠️ Piège n°2 du prompt : « si le code contient encore une
        constante de latence après ce lot, c'est qu'il n'a pas été fait ».
        """
        source = (Path(__file__).resolve().parent / "quota_openmeteo.py").read_text()
        code = "\n".join(l for l in source.splitlines()
                         if not l.lstrip().startswith("#"))
        self.assertNotIn("LATENCE", code)

    def test_la_minute_n_est_jamais_franchie(self):
        b = self.budget("collect")
        p = poids(8, 10)
        for _ in range(300):
            b.demander(p)
            self.horloge.avancer(0.05)
        evenements = json.loads(self.chemin.read_text())["evenements"]
        fin = self.horloge.maintenant()
        for borne in range(0, 400, 5):
            t = 1_000_000.0 + borne
            if t > fin:
                break
            fenetre = sum(w for ts, w, _ in evenements if t - 60 < ts <= t)
            self.assertLessEqual(fenetre, PLAFOND_MINUTE)


# ══════════════════════════════════════════════════════════════════
#  3. L'HEURE — LA FENÊTRE QUI MANQUAIT
# ══════════════════════════════════════════════════════════════════

class TestFenetreHoraire(BaseBudget):

    def test_la_nuit_du_09_08_rejouee(self):
        """648 points à 8,0 : le seau doit tenir, pas se faire tuer.

        ⚠️ CE TEST NE VÉRIFIE PAS QUE TOUT PASSE — il vérifie que ce qui
        ne passe pas est DÉCLARÉ. 5 184 pondérés ne tiennent pas sous
        5 000/heure : c'est de l'arithmétique, aucun code ne la contourne.
        Ce qui change, c'est qu'on obtient des trous nommés au lieu d'un
        run tué à 2 400 s.
        """
        b = self.budget("collect", attente_max_s=300.0)
        p = poids(8, 10)
        collectes = trous = 0
        for _ in range(648):
            try:
                b.demander(p)
                collectes += 1
            except BudgetRefuse:
                trous += 1
            self.horloge.avancer(0.06)          # la latence du 09/08

        self.assertEqual(collectes + trous, 648)
        self.assertGreater(trous, 0, "l'heure devrait mordre — sinon le "
                                     "plafond horaire n'est pas modélisé")
        # Ce qui passe doit rester sous le plafond horaire effectif.
        plafond = plafond_effectif("heure")
        self.assertLessEqual(collectes * p, plafond + p)

    def test_le_plafond_horaire_est_bien_modelise(self):
        noms = [nom for nom, _d, _p in FENETRES]
        self.assertIn("heure", noms)
        self.assertEqual(
            dict((n, pl) for n, _d, pl in FENETRES),
            {"minute": PLAFOND_MINUTE, "heure": PLAFOND_HEURE,
             "jour": PLAFOND_JOUR})

    def test_la_fenetre_glisse_et_libere(self):
        """Après une heure pleine, les jetons doivent revenir."""
        b = self.budget("collect")
        p = poids(8, 10)
        passes = 0
        while passes < 700:
            try:
                b.demander(p)
                passes += 1
            except BudgetRefuse:
                break
            self.horloge.avancer(0.06)
        bloques = passes
        self.horloge.avancer(3700)              # l'heure s'est vidée
        b.demander(p)                           # doit repasser sans lever
        self.assertGreater(bloques, 500)


# ══════════════════════════════════════════════════════════════════
#  4. L'ATTENTE EST BORNÉE, ET LE TROU EST NOMMÉ
# ══════════════════════════════════════════════════════════════════

class TestAttenteBornee(BaseBudget):

    def test_refus_plutot_qu_attente_infinie(self):
        """⚠️ Piège n°5 : un seau qui fait patienter sans limite
        transforme un dépassement de quota en run tué par le chien de
        garde — le symptôme exact qu'on veut supprimer.
        """
        b = self.budget("collect", attente_max_s=10.0)
        p = poids(8, 10)
        with self.assertRaises(BudgetRefuse) as ctx:
            for _ in range(700):
                b.demander(p, etiquette="45.000,6.000")
                self.horloge.avancer(0.06)
        message = str(ctx.exception)
        self.assertIn("collect", message)
        self.assertIn("trou déclaré", message)
        self.assertIn("45.000,6.000", message)

    def test_l_attente_bornee_n_est_pas_depassee(self):
        b = self.budget("collect", attente_max_s=30.0)
        p = poids(8, 10)
        t0 = self.horloge.maintenant()
        try:
            for _ in range(700):
                b.demander(p)
        except BudgetRefuse:
            pass
        # Chaque `demander` borne SON attente ; aucune ne doit avoir
        # dormi au-delà de la borne.
        self.assertLess(b.attendu_s, 30.0 * 700)

    def test_requete_plus_lourde_que_le_plafond(self):
        b = self.budget("collect")
        with self.assertRaises(BudgetRefuse) as ctx:
            b.demander(poids(800, 10))          # 800 pondérés > 600/min
        self.assertIn("variables", str(ctx.exception))


# ══════════════════════════════════════════════════════════════════
#  5. LE BUDGET N'EST PAS UN POINT DE PANNE
# ══════════════════════════════════════════════════════════════════

class TestAttenteFenetre(BaseBudget):
    """⭐ `attente_fenetre` — le lot S0.6 (22/08/2026).

    ⛔ CE QU'ELLE RÉPARE. Une passe de collecte lancée pendant que la
    précédente déborde encore se faisait refuser POINT PAR POINT jusqu'à
    `ATTENTE_MAX_S` : 657 refus, 657 trous déclarés, là où UNE attente
    de douze minutes ramène toute la donnée. `_quand_possible` savait
    déjà calculer l'instant exact où la place se libère — il n'était
    exposé nulle part.
    """

    def _remplir(self, consommateur, poids_total, par_requete=5.0):
        b = self.budget(consommateur)
        n = int(poids_total / par_requete)
        for _ in range(n):
            b.demander(par_requete)
            self.horloge.avancer(0.06)
        return b

    def test_place_libre_rend_zero(self):
        b = self.budget("collect")
        self.assertEqual(b.attente_fenetre(2759.4, "heure"), 0.0)

    def test_dit_QUAND_la_place_se_libere_a_la_seconde(self):
        """L'attente rendue est l'instant EXACT, ni avant ni après.

        ⚠️ LA PROPRIÉTÉ EST VÉRIFIÉE, PAS RECALCULÉE À LA MAIN. Un banc
        qui recopierait l'arithmétique de la fonction validerait sa
        propre copie : il faut assez de poids POUR CETTE DEMANDE-CI qui
        sorte de la fenêtre, ce qui n'est presque jamais le premier
        événement. On teste donc les deux bords — une seconde avant,
        la place n'est pas là ; à l'instant dit, elle l'est.
        """
        self._remplir("passe1", 4500.0)          # l'heure est presque pleine
        b = self.budget("passe2")
        attente = b.attente_fenetre(1000.0, "heure")
        self.assertGreater(attente, 0.0)

        self.horloge.avancer(attente - 1.0)
        self.assertGreater(b.attente_fenetre(1000.0, "heure"), 0.0,
                           "une seconde trop tôt, la place n'est pas là")
        self.horloge.avancer(1.0)
        self.assertEqual(b.attente_fenetre(1000.0, "heure"), 0.0,
                         "à l'instant annoncé, la place EST là")

    def test_UNE_attente_remplace_657_refus(self):
        """⭐⭐ La propriété du lot, mesurée plutôt que raisonnée."""
        self._remplir("passe1", 4700.0)
        b = self.budget("passe2")
        attente = b.attente_fenetre(2000.0, "heure")
        self.assertGreater(attente, 0.0)
        # On dort UNE fois, puis les points passent — et aucun n'est
        # refusé. Sans l'attente, chacun aurait pris son propre refus.
        self.horloge.dormir(attente)
        refuses = 0
        for _ in range(50):
            try:
                b.demander(4.2)
            except BudgetRefuse:
                refuses += 1
            self.horloge.avancer(0.06)
        self.assertEqual(refuses, 0)

    def test_la_MINUTE_n_est_pas_interrogee(self):
        """⛔ C'est toute la différence avec `_quand_possible`.

        Le poids d'une passe entière (2 759) dépasse à lui seul le
        plafond de la minute (600). `_quand_possible`, qui interroge
        TOUTES les fenêtres, rendrait donc `inf` — une réponse fausse à
        une question qui en a une bonne.
        """
        b = self.budget("passe2")
        self.assertEqual(b.attente_fenetre(2759.4, "heure"), 0.0)
        self.assertEqual(b.attente_fenetre(2759.4, "minute"), float("inf"))

    def test_un_poids_qui_ne_tient_jamais_rend_inf(self):
        b = self.budget("passe2")
        self.assertEqual(b.attente_fenetre(PLAFOND_HEURE + 1, "heure"),
                         float("inf"))

    def test_ne_reserve_RIEN(self):
        """⚠️ C'est un CONSEIL, pas un droit : la réservation reste
        celle de `demander()`, sous verrou, point par point.

        ⛔ LES DEUX CHEMINS SONT ÉPROUVÉS, ET LA PREMIÈRE VERSION DE CE
        BANC N'EN ÉPROUVAIT QU'UN. Trouvé par mutation (M12, 22/08) :
        ajouter `self.consomme += poids_total` sur le chemin « fenêtre
        pleine » ne rendait AUCUNE assertion rouge, parce que le banc
        n'interrogeait qu'une fenêtre vide et sortait avant d'y arriver.
        Un mutant qui survit dit toujours quelque chose — ici, que la
        moitié de la fonction n'était pas couverte.
        """
        # ── chemin « il y a la place » ──
        b = self.budget("passe2")
        avant = self.chemin.read_text() if self.chemin.exists() else ""
        for _ in range(20):
            b.attente_fenetre(100.0, "heure")
        apres = self.chemin.read_text() if self.chemin.exists() else ""
        self.assertEqual(avant, apres, "fenêtre libre : aucune écriture")
        self.assertEqual(b.consomme, 0.0)

        # ── chemin « la fenêtre est pleine », celui qui calcule ──
        self._remplir("passe1", 4700.0)
        b2 = self.budget("passe2")
        avant2 = self.chemin.read_text()
        for _ in range(20):
            self.assertGreater(b2.attente_fenetre(2000.0, "heure"), 0.0)
        self.assertEqual(self.chemin.read_text(), avant2,
                         "fenêtre pleine : toujours aucune écriture")
        self.assertEqual(b2.consomme, 0.0,
                         "et rien n'est décompté — ce n'est pas une "
                         "réservation, c'est une question")

    def test_fenetre_inconnue_leve(self):
        b = self.budget("passe2")
        with self.assertRaises(KeyError):
            b.attente_fenetre(10.0, "semaine")


class TestDegradation(BaseBudget):

    def test_fichier_corrompu_la_collecte_tourne_quand_meme(self):
        """⚠️ Piège n°4 : un garde-fou qui empêche de tourner est pire
        que le risque qu'il couvre.
        """
        self.chemin.write_text('{"version":1,"evenements":[[1,2,')  # tronqué
        b = self.budget("collect")
        attente = b.demander(poids(8, 10))
        self.assertTrue(b.degrade)
        self.assertAlmostEqual(attente, PAUSE_REPLI_S)

    def test_le_degrade_se_dit(self):
        import io
        self.chemin.write_text("ceci n'est pas du JSON")
        journal = io.StringIO()
        b = Budget("collect", chemin=self.chemin,
                   horloge=self.horloge.maintenant,
                   dormir=self.horloge.dormir, journal=journal)
        b.demander(poids(8, 10))
        b.demander(poids(8, 10))
        trace = journal.getvalue()
        self.assertIn("repli", trace)
        self.assertEqual(trace.count("repli"), 1, "une fois, pas à chaque point")

    def test_dossier_absent_ne_leve_pas(self):
        b = Budget("collect", chemin=Path("/proc/interdit/openmeteo.json"),
                   horloge=self.horloge.maintenant,
                   dormir=self.horloge.dormir,
                   journal=self.muet)
        attente = b.demander(poids(8, 10))
        self.assertTrue(b.degrade)
        self.assertAlmostEqual(attente, PAUSE_REPLI_S)


# ══════════════════════════════════════════════════════════════════
#  6. LE BUDGET NOMME SES CONSOMMATEURS
# ══════════════════════════════════════════════════════════════════

class TestNommage(BaseBudget):

    def test_etat_dit_qui_a_consomme_quoi(self):
        collect = self.budget("collect")
        features = self.budget("day_features")
        for _ in range(10):
            collect.demander(poids(8, 10))
            self.horloge.avancer(0.1)
        for _ in range(5):
            features.demander(poids(4, 1))
            self.horloge.avancer(0.1)

        vue = collect.etat()
        heure = vue["fenetres"]["heure"]["par_consommateur"]
        self.assertAlmostEqual(heure["collect"], 80.0)
        # ⚠️ 5 × poids(4, 1) = 5 × **1,0** = 5,0, et non 5 × 0,4 = 2,0
        # (débug du 24/08) : `day_features` envoie de petites requêtes,
        # et une petite requête coûte quand même un appel. C'est
        # exactement la classe de consommateur que l'ancien compteur
        # sous-estimait — et il y en a trois qui partagent cette IP.
        self.assertAlmostEqual(heure["day_features"], 5.0)

    def test_resume_lisible(self):
        b = self.budget("collect")
        b.demander(poids(8, 10))
        ligne = b.resume()
        self.assertIn("minute", ligne)
        self.assertIn("heure", ligne)
        self.assertIn("jour", ligne)
        self.assertIn("collect", ligne)

    def test_consommateur_anonyme_refuse(self):
        with self.assertRaises(ValueError):
            Budget("")


# ══════════════════════════════════════════════════════════════════
#  7. DEUX PROCESSUS CONCURRENTS — LE VRAI TEST D'UN BUDGET PARTAGÉ
# ══════════════════════════════════════════════════════════════════

ENFANT = r"""
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from quota_openmeteo import Budget, BudgetRefuse, poids
b = Budget(sys.argv[2], chemin=Path(sys.argv[3]), attente_max_s=1.0)
pris = 0
for _ in range(int(sys.argv[4])):
    try:
        b.demander(poids(10, 1))     # 1,0 pondéré par tour
        pris += 1
    except BudgetRefuse:
        break
print(pris)
"""


class TestConcurrence(BaseBudget):

    def test_deux_scripts_ne_tirent_pas_le_meme_jeton(self):
        """⚠️ « Un budget partagé qu'on n'a testé qu'à un seul
        consommateur n'est pas un budget partagé. » Deux processus RÉELS,
        vrai `flock`, vraie horloge — et l'invariant se vérifie sur le
        fichier, pas sur ce que les enfants racontent.
        """
        script = Path(self.dossier.name) / "enfant.py"
        script.write_text(ENFANT)
        ici = str(Path(__file__).resolve().parent)

        enfants = [
            subprocess.Popen([sys.executable, str(script), ici,
                              nom, str(self.chemin), "260"],
                             stdout=subprocess.PIPE, text=True)
            for nom in ("collect", "backfill")
        ]
        sorties = [int(e.communicate()[0].strip() or 0) for e in enfants]
        for e in enfants:
            self.assertEqual(e.returncode, 0)

        evenements = json.loads(self.chemin.read_text())["evenements"]
        # ⚠️ L'INVARIANT : sur TOUTE fenêtre d'une minute, la somme des
        # poids des DEUX consommateurs reste sous le plafond.
        limite = plafond_effectif("minute")
        for t, _w, _q in evenements:
            fenetre = sum(w for ts, w, _ in evenements if t - 60 < ts <= t)
            self.assertLessEqual(fenetre, limite + 1e-6,
                                 "deux processus ont tiré le même jeton")
        self.assertEqual(len(evenements), sum(sorties),
                         "des jetons ont été perdus ou comptés deux fois")
        self.assertGreater(sum(sorties), 400)
        qui = {q for _t, _w, q in evenements}
        self.assertEqual(qui, {"collect", "backfill"})


# ══════════════════════════════════════════════════════════════════
#  8. LE QUATRIÈME PLAFOND — 300 000/MOIS (lot S0.7, 22/08/2026)
# ══════════════════════════════════════════════════════════════════

class TestVersionNaiveEstRouge(BaseBudget):
    """⛔⛔ L'ASSERTION CENTRALE DU LOT S0.7.

    Le S0.3 a écrit deux fois que « l'ajouter à FENETRES est une
    ligne ». C'est faux : `_reserver` élague les événements à 86 400 s
    EN DUR, et cette ligne ne bouge pas dans ce lot (cf. l'en-tête de
    `quota_openmeteo.py`). Ce test REPRODUIT la version naïve — l'ajout
    littéral d'une ligne `("mois", 2_592_000, 300_000)` à FENETRES,
    combiné à l'élagage inchangé — et PROUVE qu'elle ne se déclenche
    JAMAIS, même quand 300 000 pondérés ont déjà été consommés. C'est
    pire que l'absence du garde-fou, parce qu'on croirait le plafond
    couvert.
    """

    def test_lajout_naif_a_FENETRES_ne_se_declenche_jamais(self):
        maintenant = self.horloge.maintenant()
        # 300 000 pondérés déjà consommés, mais VIEUX de plus de 24h —
        # ce qu'un mois réel contient la plupart du temps.
        vieux = [(maintenant - 86400.0 - 3600.0 * i, 5_000.0, "collect")
                 for i in range(60)]                       # 60 × 5000 = 300 000
        recent = [(maintenant - 10.0, 1.0, "collect")]      # dans les 24h

        FENETRES_NAIVES = qo.FENETRES + (
            ("mois", 2_592_000.0, qo.PLAFOND_MOIS),)
        with mock.patch.object(qo, "FENETRES", FENETRES_NAIVES):
            # La ligne EN DUR de `_reserver`, reproduite à l'identique —
            # ⛔ elle ne bouge pas dans ce lot, cf. son en-tête.
            elagues = [e for e in (vieux + recent)
                      if e[0] > maintenant - 86400.0]
            attente = qo.Budget._quand_possible(elagues, 1.0, maintenant)

        self.assertEqual(elagues, recent,
                         "l'élagage a bien jeté les 300 000 pondérés vieux "
                         "de plus de 24h — c'est ce qui rend la version "
                         "naïve muette")
        self.assertEqual(attente, 0.0,
            "⛔ LA VERSION NAÏVE NE VOIT JAMAIS LES 300 000 PONDÉRÉS : le "
            "garde-fou mensuel qu'elle prétend ajouter ne se déclenche "
            "JAMAIS. C'est pour ça que ce lot n'ajoute PAS à FENETRES — "
            "cf. la fenêtre `jours` agrégée à part.")

    def test_FENETRES_reste_a_trois_fenetres(self):
        """Garde-fou jumeau : la vraie FENETRES (pas une copie patchée)
        n'a PAS gagné de quatrième élément — le mensuel vit ailleurs.
        """
        noms = [nom for nom, _d, _p in qo.FENETRES]
        self.assertEqual(noms, ["minute", "heure", "jour"])


class TestPlafondMensuel(BaseBudget):
    """⭐ Le vrai garde-fou mensuel, en seaux journaliers agrégés."""

    def _remplir_mois(self, nom_budget: str, pondere_total: float,
                      jours_repartis: int = 30) -> Budget:
        """Pose `pondere_total` pondérés étalés sur `jours_repartis`
        jours, en écrivant l'état directement — poser 280 000 pondérés
        un par un via `demander()` serait beaucoup trop lent pour un banc.
        """
        b = self.budget(nom_budget)
        maintenant = self.horloge.maintenant()
        jours: dict = {}
        par_jour = pondere_total / jours_repartis
        for i in range(jours_repartis):
            cle = qo._cle_jour(maintenant - i * 86400.0)
            jours[cle] = jours.get(cle, 0.0) + par_jour
        b._ecrire([], jours)
        return b

    def test_mois_plein_refuse_avec_le_mot_mois_dans_le_message(self):
        self._remplir_mois("collect", plafond_mois_effectif() - 100.0)
        b = self.budget("collect")
        with self.assertRaises(BudgetRefuse) as ctx:
            b.demander(500.0)
        message = str(ctx.exception)
        self.assertIn("mois", message)
        self.assertIn("collect", message)

    def test_mois_a_l_aise_ne_refuse_pas(self):
        self._remplir_mois("collect", 100_000.0)
        b = self.budget("collect")
        b.demander(poids(8, 10))          # ne doit pas lever

    def test_le_refus_mensuel_n_attend_pas(self):
        """⭐ Question 2 du prompt : attendre n'a aucun sens — VÉRIFIÉ,
        pas supposé. Un `attente_max_s` généreux (une heure) ne doit
        RIEN changer : le refus tombe immédiatement, sans dormir.
        """
        self._remplir_mois("collect", plafond_mois_effectif() - 100.0)
        b = self.budget("collect", attente_max_s=3600.0)
        t0 = self.horloge.maintenant()
        with self.assertRaises(BudgetRefuse):
            b.demander(500.0)
        self.assertEqual(self.horloge.maintenant(), t0,
                         "le refus mensuel a dormi — il ne devrait jamais")

    def test_une_requete_qui_depasse_seule_le_plafond_mensuel(self):
        b = self.budget("collect")
        with self.assertRaises(BudgetRefuse) as ctx:
            b.demander(PLAFOND_MOIS + 1.0)
        self.assertIn("mois", str(ctx.exception))


class TestMigrationVersion1(BaseBudget):
    """⚠️ Un fichier version 1 (avant le S0.7) n'a pas de compteur
    mensuel — il doit se lire SANS ERREUR et sans repartir de zéro EN
    SILENCE (Livrable attendu du lot).
    """

    def test_lit_un_fichier_version_1_sans_lever_et_le_dit_une_fois(self):
        self.chemin.write_text(json.dumps(
            {"version": 1,
             "evenements": [[self.horloge.maintenant() - 10, 5.0, "collect"]]}))
        journal = io.StringIO()
        b = Budget("collect", chemin=self.chemin,
                   horloge=self.horloge.maintenant, dormir=self.horloge.dormir,
                   journal=journal)
        b.demander(poids(8, 10))
        b.demander(poids(8, 10))          # un second appel : toujours une fois
        trace = journal.getvalue()
        self.assertIn("version 1", trace)
        self.assertIn("mensuel", trace)
        self.assertEqual(trace.count("migration"), 1,
                         "dit une fois, pas à chaque point — même "
                         "discipline que le pavé dégradé")

    def test_rien_ne_se_perd_a_la_migration(self):
        """L'ancien événement (minute/heure/jour) survit à la migration —
        seul le compteur MENSUEL, qui n'existait pas avant, démarre à 0.
        """
        ancien = self.horloge.maintenant() - 10
        self.chemin.write_text(json.dumps(
            {"version": 1, "evenements": [[ancien, 5.0, "collect"]]}))
        b = self.budget("collect")
        b.demander(1.0)
        brut = json.loads(self.chemin.read_text())
        self.assertEqual(len(brut["evenements"]), 2,
                         "l'ancien événement plus le nouveau")
        self.assertEqual(brut["version"], 2,
                         "réécrit en version 2 après le premier passage")
        self.assertIn("jours", brut)


class TestElagageJours(BaseBudget):
    """Les seaux journaliers ne grossissent pas sans fin (cf. l'élagage
    naïf qui, lui, ne protège rien — `TestVersionNaiveEstRouge`)."""

    def test_jours_elagues_a_31_jours(self):
        maintenant = self.horloge.maintenant()
        jours = {qo._cle_jour(maintenant - i * 86400.0): 100.0
                 for i in range(40)}
        elagues = qo._jours_elagues(jours, maintenant)
        self.assertLessEqual(len(elagues), 32)     # 31 jours + marge d'arrondi
        self.assertIn(qo._cle_jour(maintenant), elagues)
        self.assertNotIn(qo._cle_jour(maintenant - 39 * 86400.0), elagues)


class TestAnnonceMensuelle(BaseBudget):
    """⭐ Question 3 du prompt : annoncer avant de mordre — dans
    `etat()`/`resume()`, jamais dans `model-verif/collect.py`, qui les
    imprime déjà pour les cinq appelants (cf. l'en-tête du module).
    """

    def test_etat_expose_le_mois(self):
        b = self.budget("collect")
        b.demander(poids(8, 10))
        vue = b.etat()
        self.assertIn("mois", vue)
        self.assertEqual(vue["mois"]["plafond"], PLAFOND_MOIS)
        self.assertGreater(vue["mois"]["consomme"], 0.0)

    def test_resume_annonce_le_mois_et_sa_projection(self):
        b = self.budget("collect")
        maintenant = self.horloge.maintenant()
        jours = {qo._cle_jour(maintenant - i * 86400.0): 10_000.0
                 for i in range(10)}
        b._ecrire([], jours)
        ligne = b.resume()
        self.assertIn("mois", ligne)
        self.assertIn("plein le", ligne)


class TestCoutEntreesSorties(BaseBudget):
    """⚠️ QUESTION 4 DU PROMPT S0.7 : le coût en E/S, MESURÉ — pas
    estimé. Le fichier est réécrit 1 524 fois par nuit ; toute forme
    qui le fait grossir se paie 1 524 fois (cf. l'en-tête du module).
    """

    def test_taille_mesuree_reste_bornee(self):
        # État réaliste : ~1 077 événements sur 24h (chiffre mesuré sur
        # le VPS le 22/08 à 12h UTC, cf. le pavé S0.7) plus 31 seaux
        # journaliers.
        maintenant = self.horloge.maintenant()
        evenements = [(maintenant - i * 80.0, 3.8, "collect")
                     for i in range(1077)]
        jours = {qo._cle_jour(maintenant - i * 86400.0): 3810.6
                for i in range(31)}

        avec_jours = json.dumps(
            {"version": 2, "evenements": evenements, "jours": jours},
            separators=(",", ":"))
        sans_jours = json.dumps(
            {"version": 2, "evenements": evenements, "jours": {}},
            separators=(",", ":"))
        taille_totale = len(avec_jours.encode("utf-8"))
        cout_jours = taille_totale - len(sans_jours.encode("utf-8"))

        # Mesuré le 22/08 : 40 367 octets pour 1 077 événements sans le
        # compteur mensuel. Les 31 seaux journaliers ajoutent l'essentiel
        # de l'écart mesuré ci-dessous — sans commune mesure avec le
        # ~1,7 Mo qu'aurait coûté le suivi événement par événement sur un
        # mois entier (~45 700 événements projetés, cf. l'en-tête).
        self.assertLess(cout_jours, 1200,
            f"31 seaux journaliers coûtent {cout_jours} octets mesurés — "
            f"devrait rester de l'ordre du kilo-octet")
        self.assertLess(taille_totale, 60_000,
            f"état complet mesuré à {taille_totale} octets — loin des "
            f"~1,7 Mo qu'aurait coûté l'option naïve")


if __name__ == "__main__":
    unittest.main(verbosity=2)
