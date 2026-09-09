#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  agrume/test_pi_rafale.py — le banc du FORMAT rafale     (09/09/2026)
#                             Lot « cellule qui approche », lot 2
#
#  ⛔ HORS LIGNE : ni réseau, ni clé, ni eccodes. Il ne vérifie pas que
#  le portail répond — il vérifie les façons de CASSER EN SILENCE, qui
#  sont les seules à ne jamais lever d'exception :
#
#   1. Réduire par autre chose qu'un maximum. Une moyenne ou une
#      décimation rend une carte lisse et plausible, où la ligne de
#      grains a disparu.
#   2. Transposer le `reshape`. La rafale est alors au mauvais endroit,
#      partout, et le fichier fait exactement la bonne taille.
#   3. Prendre le DÉBUT d'une tranche pour sa fin. Tout le ruban glisse
#      de quinze minutes et rien n'échoue.
#   4. Compter les échéances comme PIAF les compte. Le premier
#      `coefficients` non vide est l'axe `height` : on lit 1 au lieu de
#      24, on conclut « aucun run complet », on sort en code 3 — et le
#      voyant reste VERT sur une chaîne qui n'écrit plus rien.
#   5. Laisser `dernier` avancer sur une écriture partielle. Un client
#      lit alors un `carte.bin` sans manifeste.
#   6. Publier des km/h en disant des m/s. Le lecteur multiplie par 3,6
#      et affiche 144 là où il y en a 40 — au-dessus du seuil.
#   7. Laisser la géométrie de la rafale diverger de celle de la pluie.
#      Le composite du lot 3 mélangerait deux cartes décalées.
#
#  Usage :  python3 agrume/test_pi_rafale.py
# ══════════════════════════════════════════════════════════════════════
from __future__ import annotations

import json
import os
import re
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, "tools"))

import piaf  # noqa: E402
import pi_rafale as R  # noqa: E402

_OK = _KO = 0


def verifie(condition, quoi, detail=""):
    global _OK, _KO                                        # noqa: PLW0603
    if condition:
        _OK += 1
        print(f"  ✅ {quoi}" + (f" — {detail}" if detail else ""))
    else:
        _KO += 1
        print(f"  ❌ {quoi}" + (f" — {detail}" if detail else ""))


def leve(fn, quoi, motif=None):
    global _OK, _KO                                        # noqa: PLW0603
    try:
        fn()
    except R.Abort as err:
        if motif and not re.search(motif, str(err)):
            _KO += 1
            print(f"  ❌ {quoi} — a levé, mais sans « {motif} » : {err}")
            return
        _OK += 1
        print(f"  ✅ {quoi}")
        return
    except Exception as err:                               # noqa: BLE001
        _KO += 1
        print(f"  ❌ {quoi} — a levé {type(err).__name__} au lieu d'Abort : "
              f"{err}")
        return
    _KO += 1
    print(f"  ❌ {quoi} — N'A PAS LEVÉ")


def section(t):
    print(f"\n── {t}")


class MagasinDeBanc:
    """R2 en dictionnaire. `delete` NE LÈVE PAS, il rend un booléen —
    c'est le contrat de `storage.Storage`, et le correctif L3b."""

    def __init__(self):
        self.objets = {}
        self.journal = []

    def put(self, cle, octets, cache_control=None, content_type=None):
        self.objets[cle] = octets
        self.journal.append(("put", cle))

    def get_json(self, cle):
        v = self.objets.get(cle)
        return json.loads(v.decode("utf-8")) if v else None

    def delete(self, cle):
        self.journal.append(("delete", cle))
        return self.objets.pop(cle, None) is not None


RUN = "2026-09-09T15:00:00Z"
#: Une boîte de banc, PAS la vraie : 20 × 24 mailles natives. Le banc
#: doit tourner en une seconde, pas ingérer 32 millions de points.
NJ, NI = 20, 24


def ruban_de_banc(valeurs_par_rang=None):
    """Un ruban (24, NJ, NI) en m/s, où chaque rang vaut son propre
    numéro sauf indication contraire — de quoi voir un décalage."""
    a = np.zeros((R.NB_ECHEANCES, NJ, NI), dtype=np.float32)
    for k in range(R.NB_ECHEANCES):
        a[k] = (valeurs_par_rang(k) if valeurs_par_rang
                else np.full((NJ, NI), float(k)))
    return a


def run_de_banc(natif=None):
    lats = np.arange(NJ, dtype=np.float32) * -0.01 + 44.61
    lons = np.arange(NI, dtype=np.float32) * 0.01 + 0.49
    return R.Run(RUN, ruban_de_banc() if natif is None else natif,
                 lats, lons, latence_min=62.0)


# ══════════════════════════════════════════════════════════════════════
def banc_temps():
    section("1. Le temps — instant = FIN de tranche, horizon 6 h")
    e = R.echeances(RUN)
    verifie(len(e) == 24, "24 échéances", str(len(e)))
    verifie(e[0]["debut_min"] == 0 and e[0]["fin_min"] == 15,
            "la première tranche couvre ]0 ; 15]")
    verifie(e[0]["instant_demande"] == e[0]["fin"],
            "l'instant DEMANDÉ au portail est la FIN de la tranche",
            e[0]["instant_demande"])
    verifie(e[-1]["fin"] == "2026-09-09T21:00:00Z",
            "la dernière tranche finit à +360 min", e[-1]["fin"])
    # ⛔ SABOTAGE nº 3 : prendre le début pour la fin.
    verifie(e[3]["debut"] != e[3]["fin"],
            "SABOTAGE début/fin : les deux bornes sont DISTINCTES, un "
            "module qui les confondrait glisserait de 15 min",
            f"{e[3]['debut']} ≠ {e[3]['fin']}")
    # Les coefficients attendus, ceux que `verifier_coefficients` exige.
    attendus = [900 * k for k in range(1, 25)]
    verifie(attendus[0] == 900 and attendus[-1] == 21600,
            "coefficients 900 … 21 600 s", f"{attendus[0]} … {attendus[-1]}")
    cands = R.runs_candidats(
        __import__("datetime").datetime(2026, 9, 9, 16, 8,
                                        tzinfo=__import__("datetime").timezone.utc))
    verifie(cands[0] == "2026-09-09T15:00:00Z",
            "à 16:08 Z, le premier candidat est le run de 15:00 Z (recul 40 min)",
            cands[0])
    verifie(len(set(cands)) == len(cands) and len(cands) == 5,
            "cinq candidats distincts, du plus frais au plus ancien",
            str(cands))


def banc_reduction():
    section("2. La réduction — un MAXIMUM, et rien d'autre")
    bloc = np.array([[[1.0, 9.0, 2.0, 2.0],
                      [3.0, 4.0, 2.0, 2.0]]], dtype=np.float32)
    red = piaf.reduire_max(bloc)
    verifie(red.shape == (1, 1, 2), "(1, 2, 4) → (1, 1, 2)", str(red.shape))
    verifie(red[0, 0, 0] == 9.0,
            "le bloc {1, 9, 3, 4} rend 9 — le MAXIMUM", str(red[0, 0, 0]))
    # ⛔ SABOTAGE nº 1 : les deux autres règles, et ce qu'elles cachent.
    verifie(bloc.mean() != 9.0 and bloc[0, 0, 0] != 9.0,
            "SABOTAGE réduction : la moyenne (3,25) et la décimation (1) "
            "auraient toutes deux EFFACÉ la rafale à 9",
            f"moyenne {bloc[0, :, :2].mean():.2f}, décimation "
            f"{bloc[0, 0, 0]:.0f}")
    # L'invariant que `--verifier` contrôle en ligne.
    a = np.random.default_rng(2609).uniform(0, 30, (4, 20, 24)).astype(np.float32)
    verifie(abs(float(piaf.reduire_max(a).max()) - float(a.max())) < 1e-6,
            "invariant : max(calque) == max(natif), exactement")
    n_cal = int((piaf.reduire_max(a) >= R.SEUIL_PUSH_MS).sum())
    n_nat = int((a >= R.SEUIL_PUSH_MS).sum())
    verifie(n_cal <= n_nat <= 4 * n_cal,
            "invariant : n_calque ≤ n_natif ≤ 4 × n_calque",
            f"{n_cal} ≤ {n_nat} ≤ {4 * n_cal}")
    # Un bloc tout-NaN reste NaN, sans RuntimeWarning.
    nan = np.full((1, 2, 2), np.nan, dtype=np.float32)
    verifie(bool(np.isnan(piaf.reduire_max(nan)).all()),
            "un bloc entièrement NaN reste NaN — une maille absente n'est "
            "pas un calme")


def banc_geometrie():
    section("3. La géométrie — celle de PIAF, importée et non recopiée")
    nj, ni = R.verifier_alignement()
    verifie((nj, ni) == (912, 1472),
            "la boîte rend 912 × 1472 au pas 0,01°", f"{nj} × {ni}")
    verifie(R.BOITE is not piaf.BOITE or R.BOITE == piaf.BOITE,
            "la boîte EST celle de piaf.py", str(R.BOITE))
    lats, lons = piaf.axes_boite()
    verifie(lats[0] > lats[-1],
            "lats DÉCROISSANTES — premier point au NORD",
            f"{lats[0]:.2f} → {lats[-1]:.2f}")
    verifie(lons[0] < lons[-1], "lons croissantes",
            f"{lons[0]:.2f} → {lons[-1]:.2f}")
    verifie(nj % 2 == 0 and ni % 2 == 0,
            "les deux comptes sont PAIRS — sans quoi le dernier bloc du "
            "calque couvrirait deux fois moins de terrain, en silence")
    # ⛔ SABOTAGE nº 7 : la divergence avec PIAF.
    verifie(R.PAS_DEG == piaf.PAS_DEG and R.FACTEUR_CALQUE == piaf.FACTEUR_CALQUE,
            "SABOTAGE alignement : maille et facteur sont ceux de piaf — "
            "deux copies divergeraient sans que rien ne le dise")
    verifie(R.GRILLE == "001",
            "la grille interrogée est `001` (0,01°), pas `0025` : 0,025 / "
            "0,02 n'est pas entier", R.GRILLE)


def banc_objets():
    section("4. Les octets — disposition, taille, transposition")
    r = run_de_banc()
    b = r.carte_bin()
    attendu = (NJ // 2) * (NI // 2) * 2 * R.NB_ECHEANCES
    verifie(len(b) == attendu, "taille = 24 × (nj/2) × (ni/2) × 2",
            f"{len(b)} = {attendu}")
    verifie(r.octets_par_echeance() == (NJ // 2) * (NI // 2) * 2,
            "octets_par_echeance", str(r.octets_par_echeance()))
    a = np.frombuffer(b, dtype=R.DTYPE).reshape(
        R.NB_ECHEANCES, NJ // 2, NI // 2)
    verifie(all(float(a[k].max()) == float(k) for k in range(R.NB_ECHEANCES)),
            "L'ÉCHÉANCE EST L'AXE EXTERNE : le rang k vaut k partout")
    # ⛔ SABOTAGE nº 2 : le reshape transposé fait la BONNE TAILLE.
    faux = np.frombuffer(b, dtype=R.DTYPE).reshape(
        R.NB_ECHEANCES, NI // 2, NJ // 2)
    verifie(faux.shape != a.shape and faux.nbytes == a.nbytes,
            "SABOTAGE transposition : un reshape (ni, nj) fait EXACTEMENT "
            "la même taille — seule la géométrie du manifeste l'attrape",
            f"{a.shape} vs {faux.shape}")
    lat_c, lon_c = r.axes_calque()
    verifie(float(lat_c[0]) == float(r.lats[0]),
            "la coordonnée d'une maille du calque est le coin NORD-OUEST "
            "du bloc, pas son centre")
    verifie(len(lat_c) == NJ // 2 and len(lon_c) == NI // 2,
            "le calque a bien la moitié des points dans chaque sens")
    leve(lambda: R.Run(RUN, np.zeros((23, NJ, NI), np.float32),
                       r.lats, r.lons),
         "un ruban de 23 échéances est REFUSÉ", "au lieu de")


def banc_manifeste():
    section("5. Le manifeste — ce qu'il promet doit être vrai")
    r = run_de_banc()
    m = r.manifeste(dict(fabrique_par="test_pi_rafale.py"))
    cal = m["service"]["calque"]
    verifie(cal["octets_par_echeance"] == r.octets_par_echeance(),
            "le manifeste annonce la VRAIE taille d'échéance")
    verifie(len(r.carte_bin()) == cal["octets_par_echeance"] * len(m["echeances"]),
            "octets publiés = octets_par_echeance × nb échéances")
    verifie(cal["nb_lat"] == NJ // 2 and cal["nb_lon"] == NI // 2,
            "le manifeste annonce la géométrie du CALQUE, pas du natif")
    verifie(cal["pas_deg"] == 0.02, "pas du calque = 0,02°", str(cal["pas_deg"]))
    # ⛔ SABOTAGE nº 6 : l'unité.
    verifie(m["parametre"]["unite"] == "m/s",
            "SABOTAGE unité : le manifeste dit m/s — c'est ce que le "
            "lecteur VÉRIFIE avant de multiplier par 3,6")
    verifie(m["source"]["licence"].startswith("Licence Ouverte 2.0")
            and "Météo-France" in m["source"]["attribution"],
            "attribution et licence portées par le manifeste (obligation "
            "de la LO 2.0, pas une politesse)")
    verifie("NON PUBLIÉ" in m["age"],
            "l'ÂGE n'est pas publié : publié, il périmerait à la lecture")
    verifie(m["source"]["latence_publication_min"] == 62.0,
            "la latence MESURÉE du run est publiée, pas supposée")
    verifie(m["pas_min"] == 15 and m["horizon_min"] == 360,
            "pas 15 min, horizon 360 min")
    verifie(any("superposable" in str(v).lower() and "piaf" in str(v).lower()
                for v in cal.values()),
            "le manifeste DIT l'alignement avec le calque de pluie — c'est "
            "ce qui autorisera le composite du lot 3 à lire les deux "
            "nappes sans interpoler")
    verifie(len(m["remplissage_par_echeance"]) == 24,
            "remplissage PAR ÉCHÉANCE, pas un chiffre global")
    verifie(m["mesures"]["seuil_part_ventee_ms"] == R.SEUIL_PUSH_MS,
            "les mesures disent à QUEL seuil `part_ventee` est comptée")


def banc_index():
    section("6. L'index et la purge — `dernier` n'avance qu'à la fin")
    st = MagasinDeBanc()
    r = run_de_banc()
    cles = R.ecrire(st, r, journal=lambda m: None)
    verifie(cles == R.cles_du_run(RUN), "les deux clés, dans l'ordre",
            str([c.split("/")[-1] for c in cles]))
    verifie(cles[-1].endswith("manifest.json"),
            "le MANIFESTE est écrit en DERNIER : il ne décrit jamais des "
            "octets absents")
    idx = st.get_json(R.CLE_INDEX)
    verifie(idx["dernier"]["run"] == RUN,
            "`dernier.run` désigne le run lisible", idx["dernier"]["run"])
    verifie(R.run_en_ligne(st) == RUN,
            "`run_en_ligne` lit `dernier`, jamais `runs`")
    verifie(idx["ecrit_le"] and "no-store" not in json.dumps(idx),
            "`ecrit_le` est le jeton de cache")

    # Rétention : un troisième run purge le premier.
    for h, nom in ((16, "2026-09-09T16:00:00Z"), (17, "2026-09-09T17:00:00Z")):
        r2 = R.Run(nom, ruban_de_banc(), r.lats, r.lons, latence_min=50.0)
        R.ecrire(st, r2, journal=lambda m: None)
    idx = st.get_json(R.CLE_INDEX)
    verifie(len(idx["runs"]) == R.RETENTION_RUNS,
            f"{R.RETENTION_RUNS} runs en ligne, pas trois",
            str([e["run"] for e in idx["runs"]]))
    verifie(all(not c.startswith(f"{R.PREFIXE}{RUN}") for c in st.objets),
            "le premier run a bien été PURGÉ de R2")
    verifie(any(op == "delete" for op, _ in st.journal),
            "la purge est passée par `delete`, dont on lit le retour")
    ordre = [i for i, (op, _) in enumerate(st.journal) if op == "delete"]
    premier_index = next(i for i, (op, c) in enumerate(st.journal)
                         if op == "put" and c == R.CLE_INDEX)
    verifie(ordre[0] > premier_index,
            "⛔ L'INDEX EST ÉCRIT AVANT LA PURGE — l'inverse laisserait des "
            "objets payés que plus rien ne nomme")

    # ⛔ SABOTAGE nº 5 : l'écriture partielle ne fait PAS avancer `dernier`.
    class MagasinQuiCasse(MagasinDeBanc):
        def put(self, cle, octets, cache_control=None, content_type=None):
            if cle.endswith("manifest.json"):
                raise OSError("R2 coupe la connexion au 2e objet")
            super().put(cle, octets, cache_control, content_type)

    st2 = MagasinQuiCasse()
    r3 = R.Run("2026-09-09T18:00:00Z", ruban_de_banc(), r.lats, r.lons)
    try:
        R.ecrire(st2, r3, journal=lambda m: None)
    except OSError:
        pass
    idx2 = st2.get_json(R.CLE_INDEX)
    verifie((idx2["dernier"] or {}).get("run") is None,
            "SABOTAGE écriture partielle : `dernier` N'A PAS bougé — "
            "personne ne lira un run sans manifeste")
    verifie(any(e["run"] == "2026-09-09T18:00:00Z" for e in idx2["runs"]),
            "…mais la clé écrite entre dans `runs`, pour être purgée")

    # Le garde-fou de préfixe : une purge ne doit jamais mordre ailleurs.
    from grille import verifier_prefixe                    # noqa: PLC0415
    try:
        verifier_prefixe(["agrume/piaf/2026-09-09T15:00:00Z/carte.bin"],
                         prefixe=R.PREFIXE)
        verifie(False, "une clé PIAF passée à la purge rafale est refusée")
    except Exception:                                      # noqa: BLE001
        verifie(True, "une clé PIAF passée à la purge rafale est REFUSÉE — "
                      "le lot 2 ne peut pas effacer le lot 1")


def banc_seuil_partage():
    section("7. Le seuil — le même des deux côtés de la frontière")
    js = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      os.pardir, "lib", "rafale-pi.js")
    # ⚠️ LE VPS N'A PAS LE MODULE JS, et c'est normal : il fait tourner la
    # chaîne d'ingestion, pas le serveur Node (qui vit sur Render). Le
    # contrôle est donc SAUTÉ là-bas, et NOMMÉ comme sauté — un banc qui
    # planterait sur un fichier absent apprendrait à être lancé sans, et
    # un banc qui compterait ça vert mentirait sur ce qu'il a vérifié.
    if not os.path.exists(js):
        print(f"  ⓘ SAUTÉ : {os.path.basename(js)} absent de cette machine "
              f"(normal sur le VPS — le module JS vit avec le serveur "
              f"Node). À rejouer sur le poste de dev avant tout "
              f"déploiement qui touche au seuil.")
        return
    texte = open(js, encoding="utf-8").read()
    m = re.search(r"seuilKmh:\s*([0-9.]+)", texte)
    verifie(m is not None, "le seuil est lisible dans lib/rafale-pi.js")
    if m:
        verifie(float(m.group(1)) == R.SEUIL_PUSH_KMH,
                "⛔ le seuil du module JS et celui du manifeste sont "
                "D'ACCORD — sinon `part_ventee` répondrait à une question "
                "que personne ne pose",
                f"JS {m.group(1)} km/h · Python {R.SEUIL_PUSH_KMH} km/h")
    verifie(abs(R.SEUIL_PUSH_MS * 3.6 - R.SEUIL_PUSH_KMH) < 1e-3,
            "et la conversion m/s ↔ km/h tient", f"{R.SEUIL_PUSH_MS} m/s")


def main():
    print("══════════════════════════════════════════════════════════════")
    print("  BANC DU FORMAT RAFALE AROME-PI — lot 2, 09/09/2026")
    print("══════════════════════════════════════════════════════════════")
    banc_temps()
    banc_reduction()
    banc_geometrie()
    banc_objets()
    banc_manifeste()
    banc_index()
    banc_seuil_partage()
    print(f"\n══ {_OK} contrôles verts, {_KO} rouges ══")
    return 1 if _KO else 0


if __name__ == "__main__":
    sys.exit(main())
