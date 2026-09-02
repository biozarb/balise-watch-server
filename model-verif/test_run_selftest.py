#!/usr/bin/env python3
"""test_run_selftest.py — le banc du CHEMIN D'APPEL du contrôle n°1.

    Lot S3, session du 23/08/2026.

⛔ POURQUOI CE BANC EXISTE, ET POURQUOI IL EST À PART. La mutation n°6
du §3 du prompt S3 dit : « `--self-test` en échec N'EMPÊCHE PAS
l'écriture en base ⇒ le banc de `run.sh` / du chemin d'appel doit
rougir ». Or aucun banc Python ne voit `run.sh` : le garde-fou le plus
important du lot vit dans du shell, et un garde-fou que personne
n'éprouve est une décoration.

⚠️ ET IL EST DANS SON PROPRE FICHIER, pas dans `test_score.py` — leçon
du S0.5 : *un banc qui teste deux gardes à la fois n'en teste qu'une*.
Ici on n'éprouve QUE l'enchaînement : self-test → notation, ou
self-test → arrêt.

CE QU'IL FAIT : il monte un bac à sable complet (faux `python`, faux
`.env`, `ETAT` jetable), lance `run.sh score` pour de vrai, et regarde
CE QUI A ÉTÉ APPELÉ. Rien ne sort du bac : aucun réseau, aucune base,
aucun R2 — le faux python n'exécute jamais `score.py`.
"""
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ICI = pathlib.Path(__file__).resolve().parent
RUN_SH = ICI / "run.sh"

OK = KO = 0


def check(label, got, want):
    global OK, KO
    if got == want:
        OK += 1
    else:
        KO += 1
        print(f"  ❌ {label}\n       obtenu  : {got!r}\n       attendu : {want!r}")


FAUX_PYTHON = """#!/bin/bash
# Faux interpréteur : il TRACE ce qu'on lui demande et ne lance rien.
echo "$@" >> "$TRACE"
for a in "$@"; do
  [[ "$a" == "-c" ]] && exit 0              # le contrôle `import boto3`
  [[ "$a" == "--self-test" ]] && exit "${CODE_SELF_TEST:-0}"
done
exit "${CODE_NOTATION:-0}"
"""


def _bac(run_sh: pathlib.Path):
    """Un bac à sable jetable. Rend `(env, dossier)`."""
    d = pathlib.Path(tempfile.mkdtemp(prefix="s3_run_"))
    (d / "etat").mkdir()
    (d / "r2.env").write_text(
        "export R2_ACCOUNT_ID=x\nexport R2_ACCESS_KEY_ID=x\n"
        "export R2_SECRET_ACCESS_KEY=x\n")
    (d / "supa.env").write_text(
        "export SUPABASE_URL=http://exemple.invalide\n"
        "export SUPABASE_SERVICE_KEY=x\n")
    # ⚠️ VIDE, ET C'EST VOULU : le banc ne teste pas les canaux d'alerte,
    # il teste l'enchaînement.
    # ⛔⛔ MAIS « VIDE » NE VEUT PLUS DIRE « MUET » DEPUIS LE LOT LV.
    # Le commentaire d'origine disait « sans BW_ALERTE_MAIL ni ping,
    # `alerter` se contente d'écrire dans le journal ». C'était vrai le
    # 23/08 et faux depuis le 01/09 : un fichier d'alertes vide veut dire
    # « aucune variable de ping définie », donc « PERSONNE NE SURVEILLE »,
    # donc un cri de `bw_avertir_config` — canaux compris. Mesuré sur le
    # journal du VPS le 02/09 : **50 cris venus d'un bac `/tmp/s3_run_*`
    # en 18 heures, 54 % du total**, tous estampillés de l'identifiant de
    # PRODUCTION. *Un banc qui déclenche le dispositif d'alerte de la
    # production apprend à tout le monde à l'ignorer.*
    # ⚠️ Et rien n'est parti chez Yann uniquement parce que ce fichier
    # vide laisse `BW_WEBHOOK_URL`/`BW_ALERTE_MAIL` indéfinis — or
    # `env = dict(os.environ)` juste en dessous hérite du shell appelant.
    # La propriété était vraie GRATUITEMENT.
    # ⇒ Le banc se DÉCLARE (`BW_AVERTIR_CONFIG_BANC`), et le cri reste
    # visible dans le journal sous `banc-…` : on ne le fait pas taire,
    # on le rend reconnaissable.
    (d / "alertes.env").write_text("")
    faux = d / "faux_python"
    faux.write_text(FAUX_PYTHON)
    faux.chmod(0o755)
    env = dict(os.environ)
    env.update({
        "BW_ENV_FILE": str(d / "r2.env"),
        "BW_MODEL_VERIF_ENV_FILE": str(d / "supa.env"),
        "BW_ALERTES_FILE": str(d / "alertes.env"),
        "BW_MODEL_VERIF_ETAT": str(d / "etat"),
        "BW_PYTHON": str(faux),
        "TRACE": str(d / "trace"),
        # cf. le pavé ci-dessus — le nom du banc voyage dans le message.
        "BW_AVERTIR_CONFIG_BANC": "test_run_selftest.py",
    })
    return env, d


def _jouer(code_self_test: int, run_sh: pathlib.Path = RUN_SH,
           mode: str = "score", bloquant: str | None = None):
    """Lance `run.sh <mode>` et rend `(code, appels, journal)`."""
    env, d = _bac(run_sh)
    env["CODE_SELF_TEST"] = str(code_self_test)
    if bloquant is not None:
        env["BW_MODEL_SELF_TEST_BLOQUANT"] = bloquant
    else:
        env.pop("BW_MODEL_SELF_TEST_BLOQUANT", None)
    try:
        p = subprocess.run(["bash", str(run_sh), mode], env=env,
                           capture_output=True, text=True, timeout=120)
        trace = (d / "trace")
        appels = trace.read_text().splitlines() if trace.exists() else []
        journal = (d / "etat" / f"{mode}.log")
        return (p.returncode, appels,
                journal.read_text() if journal.exists() else "")
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _est_notation(ligne: str) -> bool:
    """Un appel qui LANCE la notation — donc qui écrirait en base."""
    return "score.py" in ligne and "--self-test" not in ligne


def test_chemin_dappel():
    print("\n── lot S3 : le chemin d'appel du self-test ──")

    # ── self-test VERT ⇒ la nuit continue ──
    code, appels, _ = _jouer(0)
    check("self-test vert : `run.sh score` sort 0", code, 0)
    check("… le self-test a bien été appelé",
          sum(1 for a in appels if "--self-test" in a), 1)
    check("… ET la notation a tourné",
          sum(1 for a in appels if _est_notation(a)), 1)
    check("… ET le contrôle n°2 (recalcul indépendant) a suivi",
          sum(1 for a in appels if "recalcul_balise_jour.py" in a), 1)

    # ── ⛔ MUTATION 6 — self-test ROUGE ⇒ RIEN ne doit s'écrire ──
    code, appels, journal = _jouer(2)
    check("⛔ self-test rouge : `run.sh score` sort 2", code, 2)
    check("⛔⛔ … et LA NOTATION N'A PAS TOURNÉ — c'est la propriété "
          "que la mutation n°6 attaque",
          sum(1 for a in appels if _est_notation(a)), 0)
    check("⛔ … ni le contrôle n°2 : on ne recalcule pas une nuit qui "
          "n'a pas été écrite",
          sum(1 for a in appels if "recalcul_balise_jour.py" in a), 0)
    check("… le journal dit pourquoi", "ARRÊTÉ par le self-test" in journal,
          True)
    check("⭐ … et il alerte DÈS LE PREMIER, sans attendre "
          "`SEUIL_ALERTE=2` : un self-test rouge est une certitude, pas "
          "un aléa de réseau qui se répare tout seul la nuit suivante",
          "ALERTE" in journal, True)

    # ── self-test INDISPONIBLE (code 3) ⇒ la nuit continue quand même ──
    code, appels, journal = _jouer(3)
    check("⛔ self-test indisponible : la notation tourne QUAND MÊME",
          sum(1 for a in appels if _est_notation(a)), 1)
    check("… et `run.sh` sort 0 (la nuit est notée)", code, 0)
    check("… mais il alerte : un contrôle désarmé ne se distingue pas "
          "d'un contrôle vert dans un journal que personne n'ouvre",
          "SELF-TEST INDISPONIBLE" in journal, True)

    # ── ⛔ L'INTERRUPTEUR — arbitré par Yann pour la PREMIÈRE nuit ──
    # `BW_MODEL_SELF_TEST_BLOQUANT=0` : le verdict rouge alerte aussi
    # fort, mais la nuit est notée quand même.
    code, appels, journal = _jouer(2, bloquant="0")
    check("⛔ désarmé : un self-test ROUGE laisse la notation tourner",
          sum(1 for a in appels if _est_notation(a)), 1)
    check("… et `run.sh` sort 0", code, 0)
    check("… mais l'alerte part QUAND MÊME, en disant que les lignes "
          "écrites sont suspectes",
          "SELF-TEST ROUGE, MAIS DESARME" in journal, True)
    check("⭐ … et le désarmement s'annonce à CHAQUE run, pas seulement "
          "le jour où ça casse — un garde-fou oublié en position "
          "ouverte a l'allure d'un garde-fou armé",
          "SELF-TEST NON BLOQUANT" in journal, True)
    # ⚠️ Vert + désarmé : la ligne d'annonce sort quand même.
    _, _, journal = _jouer(0, bloquant="0")
    check("… y compris quand le self-test est VERT",
          "SELF-TEST NON BLOQUANT" in journal, True)
    # ⛔ Et le DÉFAUT est bien « bloquant » : sans la variable, on bloque.
    code, appels, journal = _jouer(2)
    check("⛔ sans la variable, le défaut est BLOQUANT", code, 2)
    check("… et la ligne de désarmement n'apparaît pas",
          "SELF-TEST NON BLOQUANT" in journal, False)
    check("⛔ et une valeur inattendue (« oui ») ne vaut PAS 1 : tout ce "
          "qui n'est pas exactement 1 désarme, il n'y a pas de zone grise",
          _jouer(2, bloquant="oui")[0], 0)

    # ── le self-test ne s'invite QUE dans le mode `score` ──
    code, appels, _ = _jouer(2, mode="agrume")
    check("⛔ le mode `agrume` n'appelle PAS le self-test",
          sum(1 for a in appels if "--self-test" in a), 0)
    check("… et son job tourne normalement", code, 0)


def test_la_mutation_sapplique_vraiment():
    """⛔ ET ON MUTE `run.sh` POUR DE VRAI.

    Leçon (a) du S0.11 : *un `str.replace` qui ne trouve pas sa cible
    rend la chaîne inchangée* — le banc reste vert et on croit avoir
    mesuré « le banc ne sait pas échouer » alors qu'on a mesuré « je
    n'ai pas muté le code ». On vérifie donc que la mutation S'EST
    APPLIQUÉE avant de conclure quoi que ce soit de son résultat.
    """
    print("\n── ⛔ MUTATION 6, appliquée pour de vrai à `run.sh` ──")
    texte = RUN_SH.read_text(encoding="utf-8")
    cible = '    dire "run $MODE ARRÊTÉ par le self-test (code 2) — rien écrit"\n    exit 2\n'
    check("la cible de la mutation existe, et une seule fois",
          texte.count(cible), 1)
    mute = texte.replace(
        cible,
        '    dire "run $MODE ARRÊTÉ par le self-test (code 2) — rien écrit"\n')
    check("… et la mutation a changé le texte (elle s'est APPLIQUÉE)",
          mute != texte, True)

    d = pathlib.Path(tempfile.mkdtemp(prefix="s3_mut_"))
    try:
        faux_run = d / "run.sh"
        faux_run.write_text(mute)
        faux_run.chmod(0o755)
        # ⚠️ `run.sh` déduit `SCRIPT` de SON PROPRE dossier : la copie
        # mutée doit voir `score.py` à côté d'elle, sinon elle sortirait
        # sur « job introuvable » et on aurait mesuré autre chose.
        (d / "score.py").write_text("# leurre, jamais exécuté\n")
        code, appels, _ = _jouer(2, run_sh=faux_run)
        check("⛔⛔ SANS le `exit 2`, la notation TOURNE malgré un "
              "self-test rouge — c'est exactement ce que la mutation "
              "n°6 décrit, et l'assertion qui rougit est « LA NOTATION "
              "N'A PAS TOURNÉ » ci-dessus",
              sum(1 for a in appels if _est_notation(a)), 1)
        check("… et `run.sh` sortirait 0, comme une nuit réussie", code, 0)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main() -> int:
    if not RUN_SH.exists():
        print(f"❌ {RUN_SH} introuvable")
        return 1
    for fn in (test_chemin_dappel, test_la_mutation_sapplique_vraiment):
        fn()
    print(f"\n{OK} assertions vertes, {KO} rouges.")
    return 1 if KO else 0


if __name__ == "__main__":
    sys.exit(main())
