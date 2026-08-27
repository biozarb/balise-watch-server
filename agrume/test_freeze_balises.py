#!/usr/bin/env python3
"""
test_freeze_balises.py — banc de l'axe des balises, HORS-LIGNE.

    python3 agrume/test_freeze_balises.py

⚠️⚠️ CE BANC EXISTE À CAUSE D'UNE PANNE DE PRODUCTION, LE 12/08/2026.

Le manifeste de l'axe est passé de `domaine` (un domaine) à `domaines`
(deux) avec l'entrée des Pyrénées. `charger_artefact()` a été rendu
tolérant aux deux formes — soigneusement, avec un commentaire de sept
lignes expliquant pourquoi. Et `main(--verifier)`, dix lignes plus bas,
est resté au singulier :

    KeyError: 'domaine'

sur un artefact parfaitement valide, dans une vérification qui ne
vérifiait plus rien puisqu'elle levait avant d'avoir vérifié quoi que ce
soit.

⛔ CE QUI L'A LAISSÉ PASSER N'EST PAS L'INATTENTION. `--verifier` ne
tourne que dans le workflow d'ingestion ; le workflow n'a pas été
relancé entre le renommage et le soir. Il n'existait AUCUN banc sur ce
fichier — ni sur le gel, ni sur la relecture, ni sur la vérification.
Le README dit « un banc qu'on ne lance jamais cesse de protéger » ;
celui-ci n'existait même pas.

Cinq façons de casser en silence, une par section :

  1. **Une clé de manifeste renommée à moitié.** Le défaut ci-dessus.
  2. **Un artefact d'une AUTRE époque refusé.** Entre le déploiement du
     code et le regel, l'ancienne forme circule : la refuser ferait
     échouer tous les runs de l'intervalle, y compris pour les domaines
     qui n'ont rien demandé.
  3. **Un axe figé sur des bornes qui ne sont plus celles du code.** Ça,
     il FAUT le refuser : l'archive est disposée par indice de balise.
  4. **Un total qui ne dit rien.** 203 balises ne dit pas si les
     Pyrénées sont dedans. Le compte par domaine, si.
  5. **Une balise perdue.** L'axe est en AJOUT SEUL : une balise hors
     ligne ne doit jamais disparaître, sinon l'archive se décale.

Aucun réseau, aucune clé — l'artefact commité suffit.
"""
from __future__ import annotations

import io
import json
import os
import sys
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

import freeze_balises as F  # noqa: E402
from domaine import DOMAINE, DOMAINES  # noqa: E402

echecs = []


def verifier(nom, condition, detail=""):
    print(f"  {'✓' if condition else '✗'} {nom}"
          + (f"   {detail}" if detail else ""))
    if not condition:
        echecs.append(nom)


def main(argv=None):
    print("── 1. `--verifier` sur l'artefact COMMITÉ ──")
    # ⛔ LE CHEMIN EXACT QUI A CASSÉ. On l'exécute, on capture sa sortie,
    # et on exige 0. Un `KeyError` ici referait tomber l'ingestion.
    sortie = io.StringIO()
    try:
        with redirect_stdout(sortie):
            code = F.main(["--verifier"])
        leve = None
    except Exception as e:                                   # noqa: BLE001
        code, leve = 1, f"{type(e).__name__}: {e}"
    txt = sortie.getvalue()
    verifier("il ne lève pas et rend 0", leve is None and code == 0,
             leve or "")
    verifier("il nomme TOUS les domaines figés, pas seulement le premier",
             all(d in txt for d in DOMAINES),
             " ".join(l.strip() for l in txt.splitlines()[:1]))
    verifier("il publie le compte PAR DOMAINE — un total de 203 ne dit pas "
             "si les Pyrénées sont dedans",
             any(f"{d} :" in txt for d in DOMAINES))

    print("\n── 2. Les DEUX formes de manifeste sont acceptées ──")
    balises, man = F.charger_artefact()
    verifier("l'artefact commité porte bien la forme au PLURIEL",
             "domaines" in man and isinstance(man["domaines"], dict),
             ", ".join(sorted(man.get("domaines") or {})))
    # L'ancienne forme, telle qu'un artefact figé avant le 12/08 la porte.
    ancien = {k: v for k, v in man.items() if k != "domaines"}
    ancien["domaine"] = DOMAINE
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "axe.json"
        p.write_text(json.dumps(ancien, ensure_ascii=False), encoding="utf-8")
        try:
            F.charger_artefact(p)
            passe = True
            err = ""
        except Exception as e:                               # noqa: BLE001
            passe, err = False, str(e)[:120]
    verifier("⚠️ un artefact à l'ANCIENNE forme est encore relu — sinon tout "
             "run lancé entre le déploiement et le regel échouerait, y "
             "compris pour les domaines qui n'ont rien demandé", passe, err)

    print("\n── 3. Mais un axe figé sur d'AUTRES bornes est refusé ──")
    faux = {k: v for k, v in man.items()}
    faux["domaines"] = {"nord-alpes": dict(DOMAINE, latmax=DOMAINE["latmax"] + 1)}
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "axe.json"
        p.write_text(json.dumps(faux, ensure_ascii=False), encoding="utf-8")
        try:
            F.charger_artefact(p)
            refuse = False
        except Exception:                                    # noqa: BLE001
            refuse = True
    verifier("⛔ un domaine élargi fait LEVER — l'archive est disposée par "
             "indice de balise, un axe qui bouge la décale en silence",
             refuse)

    print("\n── 4. L'axe est complet et cohérent ──")
    par = man.get("n_par_domaine") or {}
    verifier("le total annoncé est celui de la liste",
             man["n"] == len(balises), f"{man['n']} contre {len(balises)}")
    somme = sum(par.values())
    verifier("la somme des comptes par domaine retombe sur le total",
             somme == man["n"], f"{somme} contre {man['n']}")
    ids = [b.get("id") for b in balises]
    # ⚠️ LOT L7 (27/08) — l'invariant n'est PLUS « id unique » mais
    # « (source, id) unique » : depuis que l'axe accueille d'autres
    # réseaux, deux candidats de réseaux différents PEUVENT partager le
    # même id brut sans être la même balise (cf. `F._identite`). Sur
    # l'artefact commité actuel (pioupiou + radiosondage seulement), les
    # deux invariants coïncident encore — mais c'est le second qui doit
    # rester vrai après un `--referentiels`.
    identites = [F._identite(b) for b in balises]
    verifier("aucune identité (source, id) en double — un doublon "
             "décalerait tout ce qui suit dans l'archive",
             len(identites) == len(set(identites)),
             f"{len(identites) - len(set(identites))} doublon(s)")
    verifier("(héritage) aucun id brut en double sur l'artefact ACTUEL — "
             "pioupiou + radiosondage seulement, donc encore vrai ; ce "
             "contrôle cessera d'être significatif dès le premier "
             "`--referentiels` et c'est attendu, pas une régression",
             len(ids) == len(set(ids)),
             f"{len(ids) - len(set(ids))} doublon(s)")
    # ⚠️ ON COMPARE À `_rang`, PAS À UN TRI QU'ON DEVINE. Ma première
    # version de ce contrôle exigeait `sorted(ids)` — et elle échouait,
    # à juste titre : `_rang` fait passer les points de RADIOSONDAGE
    # après toutes les balises, quel que soit leur identifiant. Un banc
    # qui réimplémente la règle qu'il vérifie ne vérifie que
    # lui-même — et ici il aurait fait rouge sur un axe parfaitement bon.
    verifier("l'axe est trié par `_rang` — radiosondages en dernier, puis "
             "par identifiant",
             [b.get("id") for b in sorted(balises, key=F._rang)] == ids)

    print("\n── 5. LOT L7 — plusieurs réseaux dans l'axe ──")
    # Deux candidats de réseaux DIFFÉRENTS portant le MÊME id brut :
    # exactement le cas qui aurait fusionné en silence avant le lot L7
    # (`connues` indexé par `id` seul). Un point dans le domaine
    # (nord-alpes) pour que `fusionner` ne les écarte pas hors-boîte.
    lat0, lon0 = DOMAINE["latmin"] + 0.05, DOMAINE["lonmin"] + 0.05
    candidats_collision = [
        dict(id="999", source="pioupiou", lat=lat0, lon=lon0, name="P-999"),
        dict(id="999", source="windsmobi", lat=lat0 + 0.01, lon=lon0,
             name="W-999"),
    ]
    fusion, ajouts, _ = F.fusionner([], candidats_collision)
    verifier("deux candidats de réseaux différents partageant le même id "
             "brut restent DEUX balises distinctes — pas une écrasée par "
             "l'autre", len(fusion) == 2 and ajouts == 2,
             f"{len(fusion)} balise(s), {ajouts} ajout(s)")
    sources_vues = sorted(b["source"] for b in fusion)
    verifier("les deux sources sont bien représentées",
             sources_vues == ["pioupiou", "windsmobi"], str(sources_vues))

    # Rejouer la fusion une SECONDE fois (comme un regel qui reverrait
    # les deux mêmes candidats) : ajouts doit retomber à 0, pas créer
    # de troisième entrée — la discipline d'ajout seul doit continuer à
    # dédupliquer PAR (source, id), pas fusionner les deux réseaux entre
    # eux sous prétexte qu'ils partagent l'id brut.
    fusion2, ajouts2, _ = F.fusionner(fusion, candidats_collision)
    verifier("regeler sur les mêmes candidats ne duplique rien et n'écrase "
             "rien", len(fusion2) == 2 and ajouts2 == 0,
             f"{len(fusion2)} balise(s), {ajouts2} ajout(s)")

    print("\n── 6. LOT L7 — `depuis_referentiels()` combine les six fichiers ──")
    import tempfile
    from pathlib import Path as _P
    with tempfile.TemporaryDirectory() as d:
        rep = _P(d)
        # windsmobi porte un `name` ; mf n'en écrit jamais (cf. collect.py)
        # — le repli synthétique de `depuis_referentiels` doit couvrir
        # l'absence, pas seulement le cas confortable.
        (rep / "stations.json").write_text(json.dumps([
            {"id": "70", "source": "pioupiou", "lat": lat0, "lon": lon0,
             "name": "Salève"}]), encoding="utf-8")
        (rep / "windsmobi_stations.json").write_text(json.dumps([
            {"id": "70", "source": "windsmobi", "lat": lat0, "lon": lon0,
             "name": "Un homonyme windsmobi"}]), encoding="utf-8")
        (rep / "mf_stations.json").write_text(json.dumps([
            {"id": "07510", "source": "mf", "lat": lat0, "lon": lon0}
            # ⚠️ pas de "name" — c'est le cas réel de mf_stations().
        ]), encoding="utf-8")
        # infoclimat_stations.json, aemet_stations.json, metar_stations.json
        # : absents du dossier — simule un collect.py lancé avec
        # --skip-infoclimat --skip-aemet --skip-metar, ou une panne.
        candidats = F.depuis_referentiels(rep)
    verifier("les trois référentiels présents entrent, les trois absents "
             "sont juste signalés (pas d'erreur)", len(candidats) == 3,
             f"{len(candidats)} candidat(s)")
    par_source = {c["source"]: c for c in candidats}
    verifier("les sources sont celles des fichiers, pas un défaut unique",
             sorted(par_source) == ["mf", "pioupiou", "windsmobi"],
             str(sorted(par_source)))
    verifier("un candidat SANS `name` dans sa source (mf) reçoit un repli, "
             "pas une clé absente", bool(par_source["mf"].get("name")),
             repr(par_source["mf"].get("name")))
    verifier("le même id brut sur deux réseaux (pioupiou/windsmobi ici) "
             "n'est PAS aplati en un seul candidat par `depuis_referentiels`"
             " — c'est `fusionner()` (test 5) qui décide, ce chargeur ne "
             "doit rien trancher lui-même",
             sum(1 for c in candidats if c["id"] == "70") == 2)
    fusion3, ajouts3, _ = F.fusionner([], candidats)
    verifier("et une fois passés par fusionner(), les deux `70` de réseaux "
             "différents restent deux balises", len(fusion3) == 3
             and ajouts3 == 3, f"{len(fusion3)} balise(s), {ajouts3} ajout(s)")

    print("\n  freeze_balises :", "OK" if not echecs else f"ÉCHEC ({len(echecs)})")
    return 0 if not echecs else 1


if __name__ == "__main__":
    sys.exit(main())
