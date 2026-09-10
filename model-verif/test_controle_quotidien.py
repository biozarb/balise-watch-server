#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  test_controle_quotidien.py — le banc du registre et du contrôle de
#  pente (10/09/2026)
#
#  ⚠️ CE BANC RÉPOND À UNE QUESTION PRÉCISE : le contrôle, calculé le
#  04/09 sur les nuits réelles, aurait-il ANNONCÉ le 09/09 (mémoire
#  au-dessus du seuil) et le 11/09 (garde de 3 900 s franchi) ? S'il ne
#  l'annonce pas, il ne sert à rien — un contrôle qui constate après
#  coup ne vaut pas mieux que quatre nuits de journal lues à la main.
#
#  Et les cinq mutations que le prompt exige de VOIR :
#    · une pente calculée sur des relevés NON comparables (rejeu diurne) ;
#    · un jalon absent traité comme un ZÉRO ;
#    · un run en ÉCHEC compté comme une nuit normale ;
#    · le seuil lu EN DUR au lieu de `MAX_RSS_MO` ;
#    · le contrôle qui CRIE alors que la pente est négative.
#
#  Lancement :  python3 model-verif/test_controle_quotidien.py
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import io
import json
import pathlib
import re
import sys
import tempfile
import unittest
from datetime import date, timedelta

ICI = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))

import controle_quotidien as C  # noqa: E402
import registre_nuit as R  # noqa: E402
import score as J  # noqa: E402

T0 = date(2026, 9, 1)


def rel(j: int, duree: int, jalon=None, lancement="timer", result="success",
        code=0, garde=3900, **extra) -> dict:
    """Une ligne du registre, telle que `registre_nuit.releve` l'écrit."""
    r = {"jour": (T0 + timedelta(days=j)).isoformat(), "duree_s": duree,
         "exec_status": code, "result": result, "lancement": lancement,
         "garde_s": garde, "marge_s": garde - duree}
    if jalon is not None:
        r["jalon_max_mo"] = jalon
    r.update(extra)
    return r


# ══════════════════════════════════════════════════════════════════════
#  LES NUITS RÉELLES, lues dans journald le 10/09 (voir enquete-pente-10-09)
# ══════════════════════════════════════════════════════════════════════
#: (jour, durée s, jalon max Mo, lancement, result, code, garde s)
REEL = [
    ("2026-08-21", 635, None, "timer", "success", 0, 1500),
    ("2026-08-22", 757, None, "timer", "success", 0, 1500),
    ("2026-08-23", 810, None, "timer", "success", 0, 1500),
    ("2026-08-24", 894, None, "timer", "success", 0, 2400),
    ("2026-08-25", 306, None, "timer", "exit-code", 1, 2400),
    ("2026-08-25", 1144, None, "manuel", "success", 0, 2400),
    ("2026-08-26", 1192, None, "timer", "success", 0, 2400),
    ("2026-08-27", 1432, None, "timer", "success", 0, 2400),
    ("2026-08-28", 1369, None, "timer", "oom-kill", None, 2400),
    ("2026-08-29", 1885, 1474, "timer", "success", 0, 2400),
    ("2026-08-30", 1834, 1500, "timer", "success", 0, 2400),
    ("2026-08-31", 1893, 1562, "timer", "success", 0, 2400),
    ("2026-09-01", 2116, 1705, "timer", "success", 0, 2400),
    ("2026-09-02", 2294, 1895, "timer", "exit-code", 1, 2400),
    ("2026-09-02", 2257, 1868, "manuel", "success", 0, 2400),
    ("2026-09-03", 2400, 2006, "timer", "exit-code", 124, 2400),
    ("2026-09-03", 2203, 2009, "manuel", "success", 0, 2400),
    ("2026-09-04", 2398, 2157, "timer", "success", 0, 3900),
    ("2026-09-05", 1551, 1751, "timer", "exit-code", 1, 3900),
    ("2026-09-06", 1789, 1760, "timer", "exit-code", 1, 3900),
    ("2026-09-07", 1660, 1760, "timer", "exit-code", 1, 3900),
    ("2026-09-07", 3178, 2638, "manuel", "success", 0, 3900),
    ("2026-09-08", 3383, 2764, "timer", "success", 0, 3900),
    ("2026-09-09", 3671, 2900, "timer", "success", 0, 3900),
    ("2026-09-10", 3860, 2897, "timer", "success", 0, 5400),
]


def reel_jusqu_au(jour: str) -> list[dict]:
    out = []
    for j, d, m, lanc, res, code, garde in REEL:
        if j > jour:
            break
        r = {"jour": j, "duree_s": d, "lancement": lanc, "result": res,
             "garde_s": garde, "marge_s": garde - d,
             "swap_peak_mo": 2048.0 if j == "2026-09-10" else None}
        # ⚠️ Absent, pas None ni 0 : les jalons n'existent que depuis le
        # 29/08, et l'OOM du 28/08 n'a pas rendu de code.
        if m is not None:
            r["jalon_max_mo"] = m
        if code is not None:
            r["exec_status"] = code
        out.append(r)
    return out


class LeCasDuLot(unittest.TestCase):
    """⛔ La raison d'être du fichier : le 04/09, le contrôle aurait parlé."""

    def test_le_04_09_il_annonce_le_seuil_memoire_AVANT_le_09_09(self):
        cs = {c["motif"]: c for c in C.constats(reel_jusqu_au("2026-09-04"),
                                                 date(2026, 9, 4))}
        self.assertIn(C.MOTIF_MEMOIRE, cs, "le contrôle s'est tu le 04/09")
        c = cs[C.MOTIF_MEMOIRE]
        # Réel : 2 900 Mo le 09/09. La date la plus proche doit être AVANT
        # ou LE 09/09, la plus lointaine dans le mois.
        self.assertLessEqual(c["date"], "2026-09-09", c["texte"])
        self.assertLessEqual(c["date_tard"], "2026-10-04", c["texte"])
        self.assertEqual(c["cible"], J.MAX_RSS_MO)

    def test_le_04_09_il_annonce_le_garde_de_3900_s_AVANT_le_11_09(self):
        cs = {c["motif"]: c for c in C.constats(reel_jusqu_au("2026-09-04"),
                                                 date(2026, 9, 4))}
        self.assertIn(C.MOTIF_DUREE, cs, "le contrôle s'est tu le 04/09")
        c = cs[C.MOTIF_DUREE]
        self.assertEqual(c["cible"], 3900, "le garde APPLIQUÉ le 04/09 était 65 min")
        # Réel : 3 671 s le 09/09, 3 860 le 10/09 ⇒ 3 900 franchi le 11/09.
        self.assertLessEqual(c["date"], "2026-09-11", c["texte"])
        self.assertIn("entre le", c["texte"])

    def test_le_10_09_la_ligne_ressemble_a_celle_du_prompt(self):
        cs = {c["motif"]: c for c in C.constats(reel_jusqu_au("2026-09-10"),
                                                 date(2026, 9, 10))}
        c = cs[C.MOTIF_DUREE]
        self.assertTrue(c["texte"].startswith(f"durée {C._n(3860)} s, +"), c["texte"])
        self.assertIn(f"({C._n(5400)} s)", c["texte"])
        self.assertLess(c["date"], "2026-09-25", "8 nuits de marge au plus")
        m = cs[C.MOTIF_MEMOIRE]
        self.assertIn(f"AU-DESSUS du seuil ({C._n(2800)} Mo) depuis le 09/09", m["texte"])
        self.assertIn(f"{C._n(2048)} Mo de swap", m["texte"], "la colonne qui manquait")

    def test_les_trois_motifs_sont_ceux_des_labels_jira(self):
        self.assertEqual(C.MOTIF_DUREE, "bw-pente-duree")
        self.assertEqual(C.MOTIF_MEMOIRE, "bw-pente-memoire")
        self.assertEqual(C.MOTIF_PURGE, "bw-purge-57014")

    def test_la_purge_ratee_de_cette_nuit_est_un_constat(self):
        # ⛔ Un fait, pas une pente : une purge ratée double la suivante.
        serie = reel_jusqu_au("2026-09-10")
        serie[-1]["incidents"] = ["⚠️ purge model_score_zone : HTTP 500",
                                  "⚠️ purge model_character : HTTP 500"]
        cs = {c["motif"]: c for c in C.constats(serie, date(2026, 9, 10))}
        self.assertIn(C.MOTIF_PURGE, cs)
        self.assertIn("model_score_zone, model_character", cs[C.MOTIF_PURGE]["texte"])
        # … mais pas le lendemain, si la nuit suivante n'a rien dit.
        serie.append(rel(0, 3900, 2800, garde=5400, jour="2026-09-11", incidents=[]))
        cs = {c["motif"]: c for c in C.constats(serie, date(2026, 9, 11))}
        self.assertNotIn(C.MOTIF_PURGE, cs)
        # … ni sur le relevé d'hier lu ce matin (le run de la nuit a manqué).
        cs = {c["motif"]: c for c in C.constats(serie[:-1], date(2026, 9, 11))}
        self.assertNotIn(C.MOTIF_PURGE, cs)


class Silence(unittest.TestCase):
    """⛔ Un contrôle bavard est un contrôle mort."""

    def test_pente_plate_rien(self):
        serie = [rel(j, 3000, 2000) for j in range(8)]
        self.assertEqual(C.constats(serie, T0 + timedelta(days=8)), [])

    def test_pente_negative_rien_MEME_au_dessus_du_seuil(self):
        # Le run se range (correctif déployé) : mémoire 2 950 → 2 850,
        # toujours au-dessus des 2 800. Crier ici, c'est crier sur un
        # projet en train de se réparer — et le run le dit déjà lui-même.
        serie = [rel(j, 3900 - 40 * j, 2950 - 20 * j) for j in range(8)]
        self.assertEqual(C.constats(serie, T0 + timedelta(days=8)), [])

    def test_moins_de_cinq_releves_rien(self):
        serie = [rel(j, 3000 + 300 * j, 2000 + 200 * j) for j in range(4)]
        self.assertEqual(C.constats(serie, T0 + timedelta(days=4)), [])

    def test_hors_horizon_rien(self):
        # +5 s/nuit vers 3 900 depuis 3 000 : 180 nuits. Pas une nouvelle.
        serie = [rel(j, 3000 + 5 * j, 2000) for j in range(8)]
        self.assertEqual(C.constats(serie, T0 + timedelta(days=8), horizon_j=30), [])
        # … mais avec un horizon d'un an, si.
        self.assertEqual(len(C.constats(serie, T0 + timedelta(days=8),
                                        horizon_j=400)), 1)

    def test_oscillation_sans_tendance_rien(self):
        serie = [rel(j, 3000 + (200 if j % 2 else -200), 2000) for j in range(10)]
        self.assertEqual(C.constats(serie, T0 + timedelta(days=10)), [])

    def test_une_marche_isolee_ne_fait_pas_parler(self):
        # Un lot ajoute une série : +600 s d'un coup, puis plateau. Le
        # 25e centile l'ignore — c'est le piège nº 1 de la jauge R2.
        serie = [rel(j, 2000 if j < 4 else 2600, 2000) for j in range(9)]
        self.assertEqual(C.constats(serie, T0 + timedelta(days=9)), [])

    def test_deux_marches_dans_la_fenetre_non_plus(self):
        durees = [2000, 2000, 2000, 2400, 2400, 2900, 2900, 2900, 2900]
        serie = [rel(j, d, 2000) for j, d in enumerate(durees)]
        self.assertEqual(C.constats(serie, T0 + timedelta(days=9)), [])


class Parle(unittest.TestCase):
    def test_une_vraie_pente_parle_avec_une_date(self):
        # +150 s/nuit depuis 3 000 vers 3 900 : franchi dans 6 nuits.
        serie = [rel(j, 3000 + 150 * j, 2000) for j in range(6)]
        cs = C.constats(serie, T0 + timedelta(days=5))
        self.assertEqual([c["motif"] for c in cs], [C.MOTIF_DUREE])
        # 3 750 s le 5e jour, +150/nuit : 3 900 le 6e.
        self.assertEqual(cs[0]["date"], (T0 + timedelta(days=6)).isoformat())
        self.assertIn(f"franchit le garde ({C._n(3900)} s) le", cs[0]["texte"])

    def test_deja_au_dessus_et_qui_monte_encore_dit_depuis_quand(self):
        serie = [rel(j, 3000, 2700 + 50 * j) for j in range(8)]
        cs = C.constats(serie, T0 + timedelta(days=8))
        self.assertEqual([c["motif"] for c in cs], [C.MOTIF_MEMOIRE])
        self.assertIn("AU-DESSUS du seuil", cs[0]["texte"])
        self.assertIn(f"depuis le {(T0 + timedelta(days=2)):%d/%m}", cs[0]["texte"])

    def test_le_garde_est_celui_de_la_DERNIERE_nuit(self):
        # Remonté hier de 3 900 à 5 400 : c'est 5 400 qu'on vise, pas
        # 3 900 — sinon on annoncerait un franchissement déjà réglé.
        serie = [rel(j, 3000 + 150 * j, 2000, garde=3900) for j in range(6)]
        serie[-1]["garde_s"] = 5400
        cs = C.constats(serie, T0 + timedelta(days=5))
        self.assertEqual(cs[0]["cible"], 5400)

    def test_la_fourchette_donne_la_date_proche_ET_la_lointaine(self):
        # Série qui accélère : +50, +50, +100, +200, +300.
        durees = [3000, 3050, 3100, 3200, 3400, 3700]
        serie = [rel(j, d, 2000) for j, d in enumerate(durees)]
        cs = C.constats(serie, T0 + timedelta(days=5))
        self.assertEqual(len(cs), 1)
        self.assertLess(cs[0]["date"], cs[0]["date_tard"])
        self.assertIn("entre le", cs[0]["texte"])


class Comparables(unittest.TestCase):
    """⛔ Les pièges de la jauge R2, transposés."""

    def test_un_rejeu_diurne_ne_compte_pas(self):
        # Sept nuits plates à 3 000 s, plus un rejeu à la main à 1 500 s
        # (cache chaud, machine vide) le dernier jour : SANS ce filtre, la
        # série finirait par une chute et la pente serait négative — ou,
        # à l'inverse, un rejeu lent fabriquerait une pente.
        serie = [rel(j, 3000 + 100 * j, 2000) for j in range(7)]
        serie.append(rel(6, 1500, 900, lancement="manuel"))
        cs = C.constats(serie, T0 + timedelta(days=7))
        self.assertEqual(len(cs), 1, "le rejeu a fait taire le contrôle")
        self.assertEqual(cs[0]["valeur"], 3600, "la valeur est celle de la NUIT")

    def test_un_run_en_echec_ne_compte_pas(self):
        # La nuit du 03/09 est morte à 2 400 s (code 124) : ce n'est pas
        # une durée, c'est l'instant du garde. La compter ferait un
        # plateau à 2 400 dans une série qui montait.
        serie = [rel(j, 2000 + 150 * j, 2000) for j in range(6)]
        serie.append(rel(6, 2400, 2100, result="exit-code", code=124))
        serie.append(rel(7, 3050, 2000))
        cs = C.constats(serie, T0 + timedelta(days=7))
        self.assertEqual(len(cs), 1)
        self.assertGreaterEqual(cs[0]["pente"], 140, cs[0]["texte"])

    def test_un_oom_ne_compte_pas(self):
        serie = [rel(j, 2000 + 150 * j, 2000) for j in range(6)]
        serie.append(rel(6, 1369, None, result="oom-kill", code=None, oom=1))
        del serie[-1]["exec_status"]
        self.assertFalse(C.comparable(serie[-1]))

    def test_un_jalon_absent_n_est_PAS_un_zero(self):
        # Sept nuits où la mémoire monte de 100 Mo, dont une (tuée avant
        # le régime) SANS jalon. Lue comme 0, cette nuit ferait une chute
        # de 2 000 Mo puis une remontée : deux différences énormes, le
        # quantile bas s'effondre et le contrôle se tait.
        serie = [rel(j, 3000, 2200 + 100 * j) for j in range(7)]
        del serie[3]["jalon_max_mo"]
        cs = {c["motif"]: c for c in C.constats(serie, T0 + timedelta(days=7))}
        self.assertIn(C.MOTIF_MEMOIRE, cs, "le jalon absent a fait taire le contrôle")
        self.assertAlmostEqual(cs[C.MOTIF_MEMOIRE]["pente"], 100.0, delta=1.0)

    def test_deux_releves_le_meme_jour_le_dernier_compte(self):
        # Deux jours portent d'abord un relevé aberrant (100) puis le bon :
        # comptés tous les deux, ils font deux différences à −99 et la
        # pente basse devient négative — le contrôle se tairait.
        pts = [(T0, 100.0), (T0, 1.0), (T0 + timedelta(days=1), 100.0),
               (T0 + timedelta(days=1), 2.0), (T0 + timedelta(days=2), 3.0),
               (T0 + timedelta(days=3), 4.0), (T0 + timedelta(days=4), 5.0)]
        self.assertAlmostEqual(C.pente_par_nuit(pts), 1.0)

    def test_un_trou_de_deux_jours_est_divise_par_deux_jours(self):
        pts = [(T0 + timedelta(days=j), 100.0 * j) for j in (0, 1, 2, 4, 5)]
        self.assertAlmostEqual(C.pente_par_nuit(pts), 100.0)


class LeSeuil(unittest.TestCase):
    def test_le_seuil_est_celui_du_run_pas_une_copie(self):
        # ⛔ Importé, pas recopié : le jour où `MAX_RSS_MO` change dans
        # score.py, le contrôle doit suivre sans qu'on y pense.
        src = pathlib.Path(C.__file__).read_text(encoding="utf-8")
        code = "\n".join(l.split("#")[0] for l in src.splitlines())
        self.assertIn("from score import MAX_RSS_MO", code)
        self.assertNotRegex(code, r"seuil_mo[^\n]*=\s*2\s?800\b",
                            "un 2800 en dur, c'est une copie qui mentira")
        serie = [rel(j, 3000, 2500 + 100 * j) for j in range(6)]
        cs = C.constats(serie, T0 + timedelta(days=6))
        self.assertEqual(cs[0]["cible"], J.MAX_RSS_MO)

    def test_le_seuil_peut_etre_passe_pour_un_banc(self):
        serie = [rel(j, 3000, 2500 + 100 * j) for j in range(6)]
        cs = C.constats(serie, T0 + timedelta(days=6), seuil_mo=10_000)
        self.assertEqual(cs, [], "à 10 Go, rien n'est atteignable sous 30 j")


class NeToucheARien(unittest.TestCase):
    """⛔ Il ne remonte JAMAIS le chien de garde tout seul."""

    def test_aucune_ecriture_aucun_systemctl_dans_le_code(self):
        src = pathlib.Path(C.__file__).read_text(encoding="utf-8")
        code = "\n".join(l.split("#")[0] for l in src.splitlines())
        for interdit in ("subprocess", "os.system", "write_text", "open(",
                         "systemctl daemon-reload\"", "Environment=BW_MODEL_VERIF_MAX_MINUTES="):
            # Les commandes n'apparaissent QUE dans une chaîne proposée,
            # jamais exécutées : pas d'import, pas d'appel.
            self.assertNotIn(interdit, code.replace("sudo cp", "").replace(
                "&& sudo systemctl daemon-reload", ""), interdit)

    def test_la_proposition_nomme_le_drop_in_et_la_mesure(self):
        serie = [rel(j, 3000 + 150 * j, 2000, garde=5400) for j in range(6)]
        c = C.constats(serie, T0 + timedelta(days=5))[0]
        p = C.proposition(c)
        self.assertIn("10-timeout-s3.conf", p)
        self.assertIn("ÉCRIVANT", p)
        self.assertIn("90 →", p)
        self.assertIn("Yann", p)


# ══════════════════════════════════════════════════════════════════════
#  LE REGISTRE — lu sur des lignes RÉELLES de journald (10/09)
# ══════════════════════════════════════════════════════════════════════
JOURNAL = """\
2026-09-10T05:58:46+02:00 vps run.sh[645613]: ▶ self-test du scoring (contrôle n°1, lot S3)
2026-09-10T05:58:47+02:00 vps run.sh[645613]: 2026-09-10T03:58:47Z ▶ score — bucket R2 « model-verif », python /home/debian/venv-balise/bin/python3
2026-09-10T05:58:53+02:00 vps run.sh[645613]:   ⓘ mémoire après la relecture de l'archive : 809 Mo
2026-09-10T06:10:50+02:00 vps run.sh[645613]:   → model_verif_daily : 70412 lignes
2026-09-10T06:11:57+02:00 vps run.sh[645613]:      ⚠️ rpc/bw_character_avance : HTTP 500 {"code":"57014","message":"canceling statement due to statement timeout"} — reprise 1/2
2026-09-10T06:42:23+02:00 vps run.sh[645613]:   score glissant : 10897 lignes (802.5 s)
2026-09-10T06:42:24+02:00 vps run.sh[645613]:   ⓘ mémoire après l'oubli de la fenêtre glissante : 1725 Mo
2026-09-10T06:43:06+02:00 vps run.sh[645613]:   rejeu d'archive : 1253232 balise-jours sur 30 journées (0 rejouée(s) cette nuit, 0 vide(s)) en 42.5 s
2026-09-10T06:58:43+02:00 vps run.sh[645613]:   ⛔ mémoire après le score par régime : 2897 Mo — AU-DESSUS DU SEUIL DE 2800 Mo. Le noyau tue le plus gros processus sans prévenir : c'est ce qui a emporté la nuit du 28/08.
2026-09-10T06:58:43+02:00 vps run.sh[645613]:   score par régime : 111794 lignes (932.0 s)
2026-09-10T07:01:15+02:00 vps run.sh[645613]:   (150.0 s)   stabilité des rangs : ok · tau = 0.606 sur 24 cases, 0 jour(s) partagé(s)
2026-09-10T07:01:21+02:00 vps run.sh[645613]:   ⓘ mémoire après l'oubli de la fenêtre rejouée : 2795 Mo
2026-09-10T07:02:30+02:00 vps run.sh[645613]:   → model_score_zone : 122691 lignes
2026-09-10T07:02:47+02:00 vps run.sh[645613]:   ⚠️ purge model_score_zone : HTTP 500 — {"code":"57014", "message":"canceling statement due to statement timeout"}
2026-09-10T07:03:16+02:00 vps run.sh[646476]: 2026-09-10T05:03:16Z run score OK en 3860s
2026-09-10T07:03:16+02:00 vps systemd[1]: bw-model-score.service: Deactivated successfully.
2026-09-10T07:03:16+02:00 vps systemd[1]: bw-model-score.service: Consumed 49min 18.943s CPU time, 3.3G memory peak, 2G memory swap peak.
"""

OOM = """\
2026-08-28T05:57:51+02:00 vps run.sh[1]: 2026-08-28T03:57:51Z ▶ score — bucket R2 « model-verif », python p
2026-08-28T06:10:00+02:00 vps run.sh[1]:   ⓘ mémoire après l'oubli du chemin J-0 : 900 Mo
2026-08-28T06:20:40+02:00 vps systemd[1]: bw-model-score.service: Main process exited, code=killed, status=15/TERM
2026-08-28T06:20:40+02:00 vps systemd[1]: bw-model-score.service: Failed with result 'oom-kill'.
2026-08-28T06:20:40+02:00 vps systemd[1]: bw-model-score.service: Consumed 14min 40.045s CPU time, 2.7G memory peak.
"""


class Registre(unittest.TestCase):
    def releve(self, texte=JOURNAL, **kw):
        runs = R.decouper(io.StringIO(texte))
        self.assertEqual(len(runs), 1)
        return R.releve(runs[0], **kw)

    def test_la_nuit_du_10_09_telle_que_le_prompt_l_a_lue(self):
        r = self.releve()
        self.assertEqual(r["jour"], "2026-09-10")
        self.assertEqual((r["debut"], r["fin"]), ("05:58:47", "07:03:16"))
        self.assertEqual(r["duree_s"], 3860)
        self.assertEqual(r["exec_status"], 0)
        self.assertEqual(r["result"], "success")
        self.assertEqual(r["garde_s"], 5400)
        self.assertEqual(r["marge_s"], 1540)
        self.assertEqual(r["jalon_max_mo"], 2897)
        self.assertEqual(r["jalon_max_etiquette"], "le score par régime")
        self.assertEqual(r["seuil_mo"], 2800)
        self.assertEqual(r["swap_peak_mo"], 2048.0)
        self.assertEqual(r["mem_peak_go"], 3.3)
        self.assertEqual(r["cpu_s"], 2958.9)
        self.assertEqual(r["lignes_glissant"], 10897)
        self.assertEqual(r["lignes_regime"], 111794)
        self.assertEqual(r["lignes_score_zone"], 122691)
        self.assertEqual(r["balise_jours_rejeu"], 1253232)
        self.assertEqual(r["etapes_s"], {"glissant": 802.5, "regime": 932.0,
                                         "rejeu": 42.5, "stabilite": 150.0})
        self.assertTrue(r["chevauchement_reduit"])
        self.assertEqual(r["lancement"], "timer")
        self.assertEqual(r["n_57014"], 2)
        self.assertIn("⚠️ purge model_score_zone : HTTP 500", r["incidents"])

    def test_le_garde_passe_par_run_sh_l_emporte_sur_l_historique(self):
        self.assertEqual(self.releve(garde_s=2400)["garde_s"], 2400)

    def test_une_nuit_oom_est_une_ligne_SANS_code_et_SANS_jalon_regime(self):
        r = self.releve(OOM)
        self.assertEqual(r["result"], "oom-kill")
        self.assertEqual(r["oom"], 1)
        self.assertNotIn("exec_status", r)
        self.assertEqual(r["duree_s"], 22 * 60 + 49)
        self.assertNotIn("swap_peak_mo", r, "pas de swap le 28/08 : absent, pas 0")
        self.assertEqual(r["jalons_mo"], {"l'oubli du chemin J-0": 900})
        self.assertFalse(C.comparable(r))

    def test_le_garde_retro_est_celui_de_la_nuit_pas_du_jour_du_deploiement(self):
        self.assertEqual(R.garde_retro(date(2026, 9, 3)), 40 * 60,
                         "la nuit du 03/09 est morte SOUS 40 min")
        self.assertEqual(R.garde_retro(date(2026, 9, 4)), 65 * 60)
        self.assertEqual(R.garde_retro(date(2026, 9, 9)), 65 * 60)
        self.assertEqual(R.garde_retro(date(2026, 9, 10)), 90 * 60)
        self.assertEqual(R.garde_retro(date(2026, 8, 10)), 25 * 60)

    def test_les_unites_de_systemd_sont_en_1024(self):
        self.assertEqual(R._mo_systemd("2G"), 2048.0)
        self.assertEqual(R._mo_systemd("269M"), 269.0)
        self.assertEqual(R._mo_systemd("564K"), 0.6)
        self.assertEqual(R._secondes_systemd("49min 18.943s"), 2958.9)
        self.assertEqual(R._secondes_systemd("21min 704ms"), 1260.7)
        self.assertEqual(R._secondes_systemd("1.647s"), 1.6)

    def test_un_rejeu_de_l_apres_midi_est_manuel_et_ne_croise_pas_reduit(self):
        t = JOURNAL.replace("T05:58:47+02:00", "T14:33:46+02:00") \
                   .replace("03:58:47Z", "12:33:46Z") \
                   .replace("T07:03:16+02:00", "T15:10:00+02:00") \
                   .replace("05:03:16Z", "13:10:00Z")
        r = self.releve(t)
        self.assertEqual(r["lancement"], "manuel")
        self.assertFalse(r["chevauchement_reduit"])

    def test_le_score_log_de_run_sh_se_lit_aussi(self):
        # Sans horodatage journald, et sans les lignes systemd : c'est ce
        # que `--fin-de-run` lit. Les horodatages viennent des `dire`.
        log = "\n".join(l.split("]: ", 1)[1] for l in JOURNAL.splitlines()
                        if "systemd" not in l)
        r = self.releve(log, source="run.sh")
        self.assertEqual(r["duree_s"], 3860)
        self.assertEqual(r["jalon_max_mo"], 2897)
        self.assertNotIn("swap_peak_mo", r, "le log ne porte pas le cgroup")
        self.assertEqual(r["source"], "run.sh")

    def test_ajouter_ne_double_jamais_un_run(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / "h.jsonl"
            r = self.releve()
            self.assertEqual(R.ajouter(p, [r]), 1)
            self.assertEqual(R.ajouter(p, [r]), 0, "rétro joué deux fois")
            p.write_text(p.read_text() + "pas du json\n", encoding="utf-8")
            self.assertEqual(len(R.charger(p)), 1, "une ligne corrompue s'ignore")

    def test_un_journal_vide_ne_rend_rien(self):
        self.assertEqual(R.decouper(io.StringIO("")), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
