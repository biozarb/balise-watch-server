#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  model-verif/reparer_archive.py — SAUVER CE QU'UN `TERM` A LAISSÉ
#                                          (Lot S, débug du 24/08/2026)
#
#  Un flux gzip que personne n'a fermé n'est PAS un fichier gzip : il
#  lui manque son pied (CRC + taille), et `gunzip -t` sort en erreur
#  « unexpected end of file ». Les octets, eux, sont là — la
#  décompression rend toutes les lignes complètes avant la coupure, et
#  s'arrête sur la dernière, tronquée au milieu.
#
#  ⛔ CE SCRIPT NE RÉPARE RIEN, IL SAUVE. Il ne fabrique aucune ligne :
#  il relit ce qui est lisible, JETTE la ligne coupée, et réécrit un
#  gzip valide qui contient EXACTEMENT ce que le run avait eu le temps
#  d'écrire. Une archive préfère un trou signalé à une ligne fausse.
#
#  ⚠️ ET IL NE TOUCHE PAS AU MANIFESTE TOUT SEUL. Un manifeste qui
#  déclare 2 905 points devant une archive qui en porte 2 471 est un
#  mensonge, mais le corriger est un ARBITRAGE (le S0.9 dit qu'un
#  manifeste ne se réécrit pas) : il faut le demander explicitement,
#  avec `--manifeste`, et le manifeste écrit DIT alors qu'il corrige,
#  ce qu'il corrige, et pourquoi.
#
#  ⓘ L'origine : la nuit du 23 au 24/08/2026. `collect_reduit.py`, à sa
#  première mise à feu, a heurté le plafond HORAIRE d'Open-Meteo, puis
#  le chien de garde de 40 min de `run.sh` lui a envoyé `TERM` en pleine
#  écriture. 2,7 Mo sur le disque, `gunzip -t` en erreur, et le
#  rattrapage du lendemain qui s'apprêtait à monter ça sur R2 tel quel.
#
#      python3 reparer_archive.py CHEMIN.ndjson.gz --dry-run
#      python3 reparer_archive.py CHEMIN.ndjson.gz
#      python3 reparer_archive.py CHEMIN.ndjson.gz --manifeste CHEMIN.manifeste.json
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import gzip
import json
import pathlib
import sys
import zlib
from datetime import datetime, timezone

SUFFIXE_ORIGINAL = ".tronque"
R2OK_SUFFIXE = ".r2ok"


def lire_tolerant(path: pathlib.Path) -> tuple[list[bytes], dict]:
    """Les lignes COMPLÈTES d'un `.gz` éventuellement tronqué.

    ⛔ **`zlib.decompressobj`, PAS `gzip.open`, ET L'ÉCART SE COMPTE EN
    CENTAINES DE LIGNES.** `gzip.open(...).read(n)` lève son `EOFError`
    en cherchant le pied du flux, et il l'emporte AVEC les octets déjà
    décompressés du bloc en cours : mesuré sur l'archive du 24/08, une
    lecture par blocs de 1 Mio rendait 10 610 lignes là où le flux en
    contient 10 985 — **375 lignes perdues par l'OUTIL DE SAUVETAGE**,
    en silence, et d'autant plus grand que le bloc est gros.
    `decompressobj(wbits=31)` (31 = 15 + 16, « en-tête gzip ») rend tout
    ce qui est décodable et ne réclame simplement jamais son pied.

    ⚠️ LA DERNIÈRE LIGNE EST JETÉE SI ELLE NE FINIT PAS PAR `\\n`, même
    si elle est du JSON valide : un `{...}` qui se termine par hasard
    sur une accolade fermante peut être un objet AMPUTÉ de ses derniers
    champs et rester parsable. On ne garde que ce qui est terminé.
    """
    jrn = {"tronque": False, "octets_perdus": 0, "illisibles": 0}
    morceaux: list[bytes] = []
    d = zlib.decompressobj(31)
    try:
        with open(path, "rb") as fh:
            while True:
                bloc = fh.read(1 << 20)
                if not bloc:
                    break
                morceaux.append(d.decompress(bloc))
        morceaux.append(d.flush())
        if not d.eof:
            jrn["tronque"] = True
            jrn["motif"] = ("flux gzip jamais terminé (pied CRC/taille "
                            "absent) — le processus a été tué en écrivant")
    except (zlib.error, OSError) as exc:
        jrn["tronque"] = True
        jrn["motif"] = f"{type(exc).__name__}: {exc}"

    brut = b"".join(morceaux)
    fin_nette = brut.rfind(b"\n")
    if fin_nette == -1:
        return [], {**jrn, "octets_perdus": len(brut)}
    jrn["octets_perdus"] = len(brut) - fin_nette - 1
    lignes = [l for l in brut[:fin_nette].split(b"\n") if l]

    gardees: list[bytes] = []
    for l in lignes:
        try:
            json.loads(l)
        except Exception:                                    # noqa: BLE001
            jrn["illisibles"] += 1
            continue
        gardees.append(l)
    return gardees, jrn


def bilan(lignes: list[bytes]) -> dict:
    """Ce que l'archive sauvée porte VRAIMENT — c'est ce chiffre-là, et
    aucun autre, qui a le droit d'entrer dans un manifeste corrigé."""
    stations: set[str] = set()
    par_modele: dict[str, int] = {}
    par_source: dict[str, int] = {}
    avec_aloft: dict[str, int] = {}
    for l in lignes:
        r = json.loads(l)
        stations.add(f"{r.get('source')}:{r.get('station_id')}")
        m = r.get("model", "?")
        par_modele[m] = par_modele.get(m, 0) + 1
        s = r.get("source", "?")
        par_source[s] = par_source.get(s, 0) + 1
        if "aloft_speed" in r:
            avec_aloft[m] = avec_aloft.get(m, 0) + 1
    return {"lignes": len(lignes), "points": len(stations),
            "par_modele": dict(sorted(par_modele.items())),
            "par_source": dict(sorted(par_source.items())),
            "aloft_par_modele": dict(sorted(avec_aloft.items()))}


def corriger_manifeste(m_path: pathlib.Path, b: dict, cause: str) -> dict:
    """Le manifeste corrigé DIT qu'il corrige, et ce qu'il corrigeait.

    ⛔ LE S0.9 DIT QU'UN MANIFESTE NE SE RÉÉCRIT PAS, et il a raison :
    un lecteur qui a déjà lu la première version doit pouvoir s'y fier.
    On ne passe outre que parce que la première version est FAUSSE et
    que la laisser coûterait plus cher que la corriger — et on paye ce
    passage en écrivant, DANS le manifeste, le chiffre d'origine, le
    chiffre juste, la cause, et la date de la correction. Un manifeste
    qui se corrige en silence serait pire que celui qu'il remplace.

    ⓘ `n_points` reste le nombre de POINTS (balises distinctes) dans
    l'archive, jamais le nombre de lignes : c'est ce que le champ
    voulait dire dans la première version, et changer le sens d'un
    champ en corrigeant sa valeur ferait deux erreurs au lieu d'une.
    """
    m = json.loads(m_path.read_text("utf-8"))
    avant = m.get("n_points")
    m["n_points"] = b["points"]
    m["corrige"] = {
        "corrige_le": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "par": "reparer_archive.py",
        "n_points_declare_initialement": avant,
        "n_points_reel": b["points"],
        "n_lignes_reel": b["lignes"],
        "cause": cause,
        "avertissement": (
            "Run TRONQUÉ : ce manifeste a d'abord déclaré ce que le run "
            "COMPTAIT écrire, puis le run est mort avant la fin. L'archive "
            "porte moins de points que la déclaration initiale, et les "
            "points qu'elle porte ne sont pas un échantillon au hasard : "
            "l'ordre de collecte est celui de l'éviction (altitude "
            "DÉCROISSANTE), donc ce sont les balises LES PLUS HAUTES qui "
            "sont là et les plus basses qui manquent."),
        "lignes_par_modele": b["par_modele"],
        "lignes_par_source": b["par_source"],
    }
    return m


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("gz", help="l'archive .ndjson.gz tronquée")
    ap.add_argument("--manifeste", default=None,
                    help="manifeste à corriger (n_points réel + bloc "
                         "`corrige` qui DIT qu'il corrige)")
    ap.add_argument("--cause", default="run tué par SIGTERM en pleine "
                                       "écriture (chien de garde de run.sh)")
    ap.add_argument("--dry-run", action="store_true",
                    help="tout compter, ne rien écrire")
    args = ap.parse_args()

    path = pathlib.Path(args.gz)
    if not path.exists():
        print(f"❌ {path} n'existe pas", file=sys.stderr)
        return 1

    lignes, jrn = lire_tolerant(path)
    if not lignes:
        print(f"❌ aucune ligne complète dans {path} — il n'y a rien à "
              f"sauver ({jrn.get('motif', 'fichier vide')})", file=sys.stderr)
        return 1
    b = bilan(lignes)

    print("┌─ CE QUE L'ARCHIVE PORTE VRAIMENT ────────────────────────────")
    print(f"│ fichier            : {path}")
    print(f"│ flux gzip fermé ?  : {'NON — tronqué' if jrn['tronque'] else 'oui'}"
          + (f"  ({jrn['motif']})" if jrn.get("motif") else ""))
    print(f"│ lignes complètes   : {b['lignes']}")
    print(f"│ octets jetés (ligne coupée) : {jrn['octets_perdus']}")
    if jrn["illisibles"]:
        print(f"│ ⚠️ lignes illisibles JETÉES : {jrn['illisibles']}")
    print(f"│ points (balises)   : {b['points']}")
    print("│ lignes par modèle  : "
          + " · ".join(f"{k} {v}" for k, v in b["par_modele"].items()))
    print("│ lignes par source  : "
          + " · ".join(f"{k} {v}" for k, v in b["par_source"].items()))
    print("│ aloft_* par modèle : "
          + (" · ".join(f"{k} {v}" for k, v in b["aloft_par_modele"].items())
             or "aucun"))
    print("└──────────────────────────────────────────────────────────────")

    if args.dry_run:
        print("  (dry-run : aucun octet écrit)")
        return 0

    # ⚠️ L'ORIGINAL EST GARDÉ, JAMAIS ÉCRASÉ. Tant que personne n'a
    # relu le fichier sauvé, l'original tronqué est la seule copie des
    # octets bruts — et une sauvegarde qui détruit sa source n'est pas
    # une sauvegarde.
    original = path.with_suffix(path.suffix + SUFFIXE_ORIGINAL)
    if original.exists():
        print(f"❌ {original} existe déjà — ce fichier a déjà été sauvé. "
              f"Rien n'est touché.", file=sys.stderr)
        return 1
    path.rename(original)

    with gzip.open(path, "wb") as fh:
        for l in lignes:
            fh.write(l + b"\n")

    # Contrôle : on relit ce qu'on vient d'écrire, ET ON LE COMPTE.
    relues, jrn2 = lire_tolerant(path)
    if jrn2["tronque"] or len(relues) != b["lignes"]:
        print(f"❌ l'archive réécrite ne se relit pas ({len(relues)} lignes, "
              f"tronqué={jrn2['tronque']}) — l'original est en {original}",
              file=sys.stderr)
        return 1

    # ⛔ LE TÉMOIN MEURT. L'objet a changé : un témoin d'un envoi
    # précédent affirmerait que CE contenu-ci est parti sur R2.
    temoin = pathlib.Path(str(path) + R2OK_SUFFIXE)
    temoin.unlink(missing_ok=True)

    print(f"✅ archive sauvée : {b['lignes']} lignes, {b['points']} points, "
          f"{path.stat().st_size / 1024:.0f} Ko — l'original tronqué est "
          f"conservé en {original.name}")
    print(f"   témoin retiré (s'il existait) : le prochain `rattraper()` "
          f"montera CETTE version-ci sur R2")

    if args.manifeste:
        m_path = pathlib.Path(args.manifeste)
        if not m_path.exists():
            print(f"❌ manifeste {m_path} introuvable", file=sys.stderr)
            return 1
        m = corriger_manifeste(m_path, b, args.cause)
        m_path.write_text(json.dumps(m, ensure_ascii=False, indent=1) + "\n",
                          encoding="utf-8")
        pathlib.Path(str(m_path) + R2OK_SUFFIXE).unlink(missing_ok=True)
        print(f"✅ manifeste corrigé : n_points "
              f"{m['corrige']['n_points_declare_initialement']} → "
              f"{m['n_points']}, bloc `corrige` posé, témoin retiré "
              f"(il sera RÉÉCRIT sur R2 au prochain rattrapage)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
