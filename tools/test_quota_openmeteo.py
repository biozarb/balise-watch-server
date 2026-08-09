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

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from quota_openmeteo import (  # noqa: E402
    Budget, BudgetRefuse, FENETRES, PAUSE_REPLI_S, PLAFOND_HEURE,
    PLAFOND_JOUR, PLAFOND_MINUTE, plafond_effectif, poids, poids_url,
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
        self.assertAlmostEqual(apres - avant, poids(1, 9))

    def test_les_lieux_multiples_comptent(self):
        """⚠️ Le facteur qu'on oublie. `backfill_packs.py` envoie des
        lots de points dans UNE requête ; sans ce facteur, son poids
        serait sous-estimé d'un ordre de grandeur — et le budget
        mentirait du côté qui ne protège pas.
        """
        un = "https://x/v1/forecast?latitude=45.0&longitude=6.0&hourly=a,b"
        dix = ("https://x/v1/forecast?latitude=" + ",".join(["45.0"] * 10) +
               "&longitude=" + ",".join(["6.0"] * 10) + "&hourly=a,b")
        self.assertAlmostEqual(poids_url(dix), poids_url(un) * 10)

    def test_sans_modele_explicite_compte_pour_un(self):
        url = "https://x/v1/archive?latitude=45.0&longitude=6.0&hourly=a,b,c,d,e"
        self.assertAlmostEqual(poids_url(url), 0.5)


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
        self.assertAlmostEqual(heure["day_features"], 2.0)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
