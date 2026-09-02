#!/usr/bin/env python3
"""test_controle_position.py — banc du GARDE-FOU DE POSITION
                               (lot L15, 02/09/2026).

Ce que ce banc tient, et pourquoi chaque propriété vaut son assertion :

  1. ⭐⭐ **La constante et la distance RECOPIÉES ne peuvent pas
     dériver.** `controle_position` ne peut pas importer
     `agrume/freeze_balises` (`score.py` ne doit dépendre ni de numpy ni
     du paquet `agrume/`), donc il recopie `SEUIL_DEPLACEMENT_M` et
     utilise `geopair.distance_km` au lieu de `freeze_balises.distance_m`.
     Une copie sans gardien dérive : le banc, LUI, importe les deux et
     les confronte. C'est le seul endroit du dépôt où les deux jumeaux
     se regardent.
  2. ⭐ **`noeud()` rend exactement ce que `quantification.index_plats`
     rendrait** — sur les balises RÉELLES du gel, pas sur trois cas
     inventés. Si les deux divergeaient, le contrôle suspendrait des
     balises que le produit sert au même endroit, et laisserait passer
     celles qu'il sert ailleurs.
  3. **Le critère est une CONJONCTION.** 14 m qui changent de nœud (bord
     de maille) ne déclenchent pas ; 500 m dans le même nœud non plus.
     Les deux cas existent en production, mesurés le 02/09.
  4. **Une nuit sans la balise n'interrompt PAS la persistance**, un
     retour à la normale SI. Une balise déménagée est justement une
     balise qu'on débranche : remettre le compteur à zéro à chaque nuit
     hors ligne rendrait le seuil inatteignable.
  5. **Le cri ne repart pas si l'ensemble n'a pas changé**, et il repart
     dès qu'une balise ENTRE ou SORT.
  6. ⛔ **Il ÉCHOUE OUVERT** : jeton illisible ⇒ on crie quand même. Un
     dispositif d'alerte ne doit pas se taire parce que son propre état
     est cassé (leçon du lot LV, payée deux fois).
  7. **Le `.sql` échappe les apostrophes** — les notes sont en français,
     avec des « l'archive » partout — et n'écrit QUE les confirmées.
  8. **Le journal écrit une ligne même quand tout va bien.** Un contrôle
     dont on ne voit la ligne que les jours de panne est indistinguable
     d'un contrôle qui ne tourne plus (règle du lot LD).
  9. **Un artefact d'orographie qui contredit les autres LÈVE** au lieu
     de choisir un meta au hasard.

Aucun réseau, aucune archive : les lignes d'obs sont fabriquées ici.

Usage :
    python3 test_controle_position.py
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "agrume"))

import controle_position as CP  # noqa: E402
import geopair as GP  # noqa: E402

OK = 0
KO = 0


def check(label: str, cond: bool, detail: str = ""):
    global OK, KO
    if cond:
        OK += 1
    else:
        KO += 1
        print(f"  ❌ {label}" + (f"\n       {detail}" if detail else ""))


METAS = CP.metas_grilles()


def obs(cle, lat, lon):
    return {"station_id": cle[1], "source": cle[0], "lat": lat, "lon": lon}


def balise(lat, lon, nom="banc", source="pioupiou", ident="1"):
    return {"id": ident, "source": source, "lat": lat, "lon": lon,
            "name": nom, "vue_le": "2026-08-10"}


def gel_temporaire(balises):
    """Un artefact de gel jetable — même forme que celui d'`agrume`."""
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                    encoding="utf-8")
    json.dump({"produit": "banc", "ecrit_le": "2026-08-28T00:00:00Z",
               "n": len(balises), "balises": balises}, f, ensure_ascii=False)
    f.close()
    return pathlib.Path(f.name)


# ══════════════════════════════════════════════════════════════════
#  1. LES JUMEAUX — la constante et la distance recopiées
# ══════════════════════════════════════════════════════════════════
import freeze_balises as FB  # noqa: E402

check("⭐⭐ SEUIL_DEPLACEMENT_M recopié == celui de freeze_balises",
      CP.SEUIL_DEPLACEMENT_M == FB.SEUIL_DEPLACEMENT_M,
      f"{CP.SEUIL_DEPLACEMENT_M} vs {FB.SEUIL_DEPLACEMENT_M}")

_cas = [((45.10, 5.70), (45.11, 5.71)), ((43.90, 1.20), (43.9005, 1.2007)),
        ((46.40, 7.50), (46.40, 7.52)), ((44.00, 6.00), (45.30, 5.10))]
_pires = 0.0
for a, b in _cas:
    d_fb = FB.distance_m(a, b)
    d_gp = GP.distance_km(a[0], a[1], b[0], b[1]) * 1000.0
    _pires = max(_pires, abs(d_fb - d_gp) / max(d_fb, 1e-9))
check("⭐ la haversine de geopair et l'équirectangulaire de freeze_balises "
      "s'accordent à mieux que 1 % sur la BBOX",
      _pires < 0.01, f"écart relatif max {_pires:.4%}")

# ══════════════════════════════════════════════════════════════════
#  2. LE NŒUD — confronté à index_plats, sur les balises RÉELLES
# ══════════════════════════════════════════════════════════════════
try:
    from quantification import index_plats  # noqa: E402

    _reelles = json.loads(CP.GEL.read_text(encoding="utf-8"))["balises"][:400]
    for _grille in ("001", "0025"):
        _m = dict(METAS[_grille])
        # `index_plats` a besoin des bornes ; le meta de l'artefact les
        # porte déjà (Ni/Nj). On lui donne le meta tel quel.
        _idx, _ = index_plats(_m, _reelles)
        _bon = all(
            int(_idx[k]) == -1
            or int(_idx[k]) == (CP.noeud(_m, b["lat"], b["lon"])[1] * _m["Ni"]
                                + CP.noeud(_m, b["lat"], b["lon"])[0])
            for k, b in enumerate(_reelles))
        check(f"⭐ noeud() == index_plats sur {len(_reelles)} balises réelles "
              f"(grille {_grille})", _bon)
except ImportError as _e:                                  # noqa: BLE001
    check("⚠️ quantification indisponible (numpy ?) — confrontation du nœud "
          "NON FAITE", False, str(_e))

# ══════════════════════════════════════════════════════════════════
#  3. LE CRITÈRE EST UNE CONJONCTION
# ══════════════════════════════════════════════════════════════════
_b = balise(45.0000, 5.0000)
# un pas de 0,01° en longitude = un nœud plein, ~785 m à cette latitude
_d, _n1, _n2, _decl = CP.diverge(_b, (45.0000, 5.0100), METAS)
check("un vrai déplacement d'un nœud déclenche",
      _decl and _n1 and _d > 200, f"d={_d:.0f} n001={_n1}")

# bord de maille : 14 m suffisent à changer de nœud si l'on est dessus
_bord = balise(45.0000, 5.00499)
_d, _n1, _n2, _decl = CP.diverge(_bord, (45.0000, 5.00501), METAS)
check("⭐ 2 m qui changent de nœud (bord de maille) ne déclenchent PAS",
      _n1 and not _decl, f"d={_d:.1f} n001={_n1} decl={_decl}")

_meme = balise(45.0000, 5.0000)
_d, _n1, _n2, _decl = CP.diverge(_meme, (45.0030, 5.0000), METAS)
check("⭐ 333 m qui restent dans le même nœud ne déclenchent PAS",
      (not _n1) and _d > 200 and not _decl, f"d={_d:.0f} n001={_n1}")

check("le nœud 0,025° est rendu à part et ne décide de rien",
      CP.diverge(_b, (45.0000, 5.0100), METAS)[2] is False)

# ══════════════════════════════════════════════════════════════════
#  3 bis. LE SEUIL LUI-MÊME, ET LA PREMIÈRE POSITION VUE
#
#  ⚠️ CES DEUX ASSERTIONS SONT NÉES D'UNE MUTATION MUETTE (02/09). Le
#  banc appelle `verifier(seuil_jours=10)` explicitement : abaisser la
#  CONSTANTE à 5 ne faisait donc rougir personne, alors que c'est elle
#  que la production utilise — et 5 est sous le cycle de rafraîchissement
#  de 7 jours de `collect.py`, c'est-à-dire un seuil qui ne filtre plus
#  rien. Même chose pour `setdefault` : remplacé par une affectation
#  directe, il gardait la DERNIÈRE position vue au lieu de la première,
#  sans qu'une seule ligne ne bouge.
# ══════════════════════════════════════════════════════════════════
check("⭐ le seuil de production reste AU-DESSUS du cycle de "
      "rafraîchissement de collect.py (7 j) — sous 8, il ne filtre plus "
      "les épisodes transitoires (mesuré : max 8 j)",
      CP.SEUIL_PERSISTANCE_J >= 8, f"SEUIL_PERSISTANCE_J = "
      f"{CP.SEUIL_PERSISTANCE_J}")

_deux = CP.positions_des_obs([obs(CLE_A := ("pioupiou", "7"), 45.0, 5.0),
                              obs(CLE_A, 46.0, 6.0)])
check("⭐ deux positions sous la MÊME clé le même jour : on garde la "
      "PREMIÈRE, on ne moyenne pas et on n'écrase pas",
      _deux[CLE_A] == (45.0, 5.0), f"{_deux}")

# ══════════════════════════════════════════════════════════════════
#  4. LA PERSISTANCE
# ══════════════════════════════════════════════════════════════════
CLE = ("pioupiou", "1")
GEL_B = {CLE: balise(45.0000, 5.0000)}
LOIN = (45.0000, 5.0200)
PRES = (45.0000, 5.0000)
JOURS = [f"2026-08-{d:02d}" for d in range(20, 30)]


def _serie(vals):
    """vals : liste alignée sur JOURS, None = balise non vue."""
    return {j: ({CLE: v} if v else {}) for j, v in zip(JOURS, vals)}


check("dix jours de divergence d'affilée comptent dix",
      CP.persistances(GEL_B, _serie([LOIN] * 10), METAS, JOURS).get(CLE) == 10)
check("⭐ une nuit SANS la balise n'interrompt pas le compte",
      CP.persistances(GEL_B, _serie([LOIN] * 4 + [None] + [LOIN] * 5),
                      METAS, JOURS).get(CLE) == 9)
check("⭐ un retour à la bonne position, LUI, remet à zéro",
      CP.persistances(GEL_B, _serie([LOIN] * 5 + [PRES] + [LOIN] * 4),
                      METAS, JOURS).get(CLE) == 4)
check("une balise qui ne diverge jamais n'est pas dans le résultat",
      CP.persistances(GEL_B, _serie([PRES] * 10), METAS, JOURS) == {})

# ══════════════════════════════════════════════════════════════════
#  5. verifier() — la confirmation au seuil
# ══════════════════════════════════════════════════════════════════
_gel_f = gel_temporaire([balise(45.0000, 5.0000, "Banc du L15")])
_obs = {j: CP.positions_des_obs([obs(CLE, *LOIN)]) for j in JOURS}
_r = CP.verifier(None, JOURS[-1], _obs, gel_chemin=_gel_f, metas=METAS,
                 seuil_jours=10)
check("verifier() confirme une divergence de 10 jours au seuil 10",
      _r["confirmees"] == ["pioupiou:1"], f"{_r['confirmees']}")
check("… et la ligne porte les DEUX positions et la durée",
      _r["lignes"][0]["gel"] == (45.0, 5.0)
      and _r["lignes"][0]["vivante"] == LOIN
      and _r["lignes"][0]["jours"] == 10, f"{_r['lignes'][0]}")
_r9 = CP.verifier(None, JOURS[-1], {j: v for j, v in list(_obs.items())[1:]},
                  gel_chemin=_gel_f, metas=METAS, seuil_jours=10)
check("⭐ neuf jours ne confirment pas — le seuil n'est pas décoratif",
      _r9["confirmees"] == [] and _r9["lignes"][0]["jours"] == 9,
      f"{_r9['lignes']}")

# ══════════════════════════════════════════════════════════════════
#  6. LE CRI — anti-répétition, et l'échec OUVERT
# ══════════════════════════════════════════════════════════════════
with tempfile.TemporaryDirectory() as _etat:
    _t1 = CP.cri(_r, _etat)
    check("premier passage : le cri part", _t1 and "pioupiou:1" in _t1)
    CP.poser_jeton(_r, _etat)
    check("second passage, même ensemble : SILENCE",
          CP.cri(_r, _etat) is None)

    _r2 = CP.verifier(None, JOURS[-1], _obs, gel_chemin=_gel_f, metas=METAS,
                      seuil_jours=10)
    _r2["confirmees"] = []
    _t2 = CP.cri(_r2, _etat)
    check("⭐ une balise qui SORT de l'ensemble fait repartir le cri",
          _t2 and "rentree dans l'ordre" in _t2, str(_t2))

    CP.jeton(_etat).write_text("{ceci n'est pas du json", encoding="utf-8")
    check("⛔ jeton illisible ⇒ ON CRIE QUAND MÊME (échec ouvert)",
          CP.cri(_r, _etat) is not None)

    # inécrivable : poser_jeton ne doit pas lever
    CP.poser_jeton(_r, "/proc/pas/de/chemin/ici")
    check("un jeton inécrivable ne fait pas tomber le run", True)

with tempfile.TemporaryDirectory() as _etat:
    # ── ⛔ (02/09) LE JETON EN ATTENTE N'EST PAS UN JETON ─────────────
    # `score.py` dépose le jeton en attente ; tant que `run.sh` ne l'a
    # pas promu (après l'e-mail), l'ensemble n'est PAS « connu » et le
    # cri repart. Posé directement, un envoi raté rendait le garde-fou
    # muet pour toujours.
    CP.poser_jeton(_r, _etat, en_attente=True)
    check("⛔ `en_attente=True` écrit le fichier `.attente`, pas le jeton",
          CP.jeton_en_attente(_etat).exists()
          and not CP.jeton(_etat).exists())
    check("⛔⛔ un jeton EN ATTENTE ne fait pas taire le cri : on "
          "recrie tant que l'envoi n'est pas confirmé",
          CP.cri(_r, _etat) is not None)
    check("⛔ et `score.py` DÉPOSE bien en attente — c'est une lecture "
          "de source, comme les six lignes de run.sh : rien d'autre "
          "ne tient cette ligne",
          "CP.poser_jeton(res_pos, root, en_attente=True)"
          in (pathlib.Path(__file__).resolve().parent / "score.py")
          .read_text(encoding="utf-8"))
    check("… son contenu est celui du jeton (run.sh ne fait que le "
          "renommer)",
          json.loads(CP.jeton_en_attente(_etat).read_text())["balises"]
          == sorted(_r["confirmees"]))

# ══════════════════════════════════════════════════════════════════
#  7. LE .SQL
# ══════════════════════════════════════════════════════════════════
_sql = CP.sql_suspension(_r)
check("une ligne update par balise confirmée, et une seule",
      _sql.count("update station_zone") == 1, _sql)
check("⭐ les apostrophes de la note sont doublées",
      "''" in _sql or "'" not in _sql.split("position_note = ")[1][1:-1],
      _sql)
check("la note écrit les deux positions, l'écart et la durée",
      all(m in _sql for m in ("45.0000", "5.0200", "10 jours")), _sql)
check("le .sql ne suspend PAS l'archivage, et l'écrit dans son en-tête",
      "PAS L'ARCHIVAGE" in _sql and "n'est PAS marqué" in _sql, _sql[:600])
check("⭐ et dans la NOTE, la même phrase ressort ÉCHAPPÉE (« l''archivage ») "
      "— c'est la preuve que _lit() a bien mordu sur du texte français",
      "pas de l''archivage" in _sql, _sql)
check("aucune ligne pour une divergence non confirmée",
      "update station_zone" not in CP.sql_suspension(_r9))
check("⭐ le verdict du troisième avis, quand il existe, entre dans la note "
      "— sans lui, personne ne saura dans six mois QUI des deux avait tort",
      "REFERENTIEL FAUX" in CP.sql_suspension(
          _r, {"pioupiou:1": {"verdict": "REFERENTIEL FAUX (le gel a raison)"}}))

# ══════════════════════════════════════════════════════════════════
#  8. LE JOURNAL PARLE MÊME QUAND TOUT VA BIEN
# ══════════════════════════════════════════════════════════════════
_vide = CP.verifier(None, JOURS[-1],
                    {j: CP.positions_des_obs([obs(CLE, *PRES)])
                     for j in JOURS},
                    gel_chemin=_gel_f, metas=METAS, seuil_jours=10)
_tj = CP.texte_journal(_vide)
check("⭐ le journal écrit une ligne « position » même à zéro divergence",
      "position :" in _tj and "0 balise" in _tj, _tj)
check("… et le cas plein nomme chaque balise avec sa durée",
      "10 j" in CP.texte_journal(_r), CP.texte_journal(_r))

# ══════════════════════════════════════════════════════════════════
#  9. UN META D'OROGRAPHIE QUI CONTREDIT LES AUTRES LÈVE
# ══════════════════════════════════════════════════════════════════
with tempfile.TemporaryDirectory() as _d2:
    for i, lon0 in enumerate((-12.0, -11.0)):
        pathlib.Path(_d2, f"orographie-x{i}.json").write_text(json.dumps(
            {"grilles": {"001": {"meta": {"lat0": 55.4, "lon0": lon0,
                                          "di": 0.01, "dj": 0.01,
                                          "Ni": 10, "Nj": 10,
                                          "jScan": 0}}}}), encoding="utf-8")
    try:
        CP.metas_grilles(_d2)
        check("⛔ deux metas contradictoires doivent LEVER", False)
    except ValueError as e:
        check("⛔ deux metas contradictoires LÈVENT au lieu d'en choisir un",
              "ne s'accordent pas" in str(e), str(e))

_gel_f.unlink(missing_ok=True)

# ══════════════════════════════════════════════════════════════════
print(f"\n{'✅' if KO == 0 else '❌'} {OK} assertions vertes, {KO} rouges.\n")
sys.exit(1 if KO else 0)
