#!/usr/bin/env python3
# ══════════════════════════════════════════════════════════════════════
#  controle_quotidien.py — LE CONTRÔLE DE PENTE DE LA NOTATION (10/09/2026)
#
#  Il ne rend qu'une chose, et seulement quand elle est due :
#
#      durée 3 860 s, +197 s/nuit → franchit le garde (5 400 s) le 18/09
#
#  Une DATE DE FRANCHISSEMENT, pour la durée et pour la mémoire. C'est
#  le chiffre qui, calculé le 04/09, aurait annoncé le 10/09 — et
#  personne n'aurait eu à relire quatre nuits de journal à la main.
#  C'est la transposition d'`audit_r2.py` (la jauge R2) au registre des
#  nuits (`registre_nuit.py`, `historique.jsonl`), avec ses pièges déjà
#  payés là-bas :
#
#    · LA PENTE EST UN QUANTILE BAS DE DIFFÉRENCES (25e centile), jamais
#      des moindres carrés et jamais « dernier moins premier ». Quatre
#      marches réelles ont fabriqué quatre fausses échéances sur R2 ; ici
#      la marche a un nom — un lot qui ajoute une série (L19, L20, L22a),
#      un cache de rejeu réchauffé, un chien de garde remonté.
#    · SEULS LES RELEVÉS COMPARABLES COMPTENT : les runs du TIMER, finis
#      en succès. Un rejeu à la main de l'après-midi tourne sur une
#      autre machine (cache chaud, pas de piaf, pas de reduit) ; un run
#      mort n'a pas de durée, il a un instant de mort.
#    · UN JALON ABSENT N'EST PAS UN ZÉRO. Un run tué avant le régime n'a
#      pas de jalon régime ; le lire à 0 ferait une chute de 2 900 Mo
#      dans la série, donc une pente négative, donc le silence — la nuit
#      précisément où il faudrait parler.
#
#  ⛔ IL SE TAIT QUAND LA PENTE EST PLATE OU NÉGATIVE, et quand l'échéance
#  est au-delà de l'horizon. Le rapport du 09/09 (⚠️ 3) : « un détecteur
#  de dérive qui crie tous les matins pour une raison connue devient un
#  détecteur qu'on ne lit plus ». Un contrôle bavard est un contrôle mort.
#
#  ⛔ IL NE REMONTE JAMAIS LE CHIEN DE GARDE. Chaque remontée (40 → 65 →
#  90) est un constat ÉCRIT dans l'en-tête de `10-timeout-s3.conf`, avec
#  la mesure qui l'a justifiée. Un script qui monterait ça en silence
#  effacerait la trace qui rend la panne compréhensible six mois plus
#  tard, et masquerait une fuite au lieu de la révéler. Il PROPOSE la
#  commande exacte, dans son texte ; Yann la lance.
#
#  Usage :   controle_quotidien.py [--out /var/lib/bw-model-verif]
#                                  [--jour AAAA-MM-JJ] [--horizon-j 30]
#                                  [--machine]
#  Sortie :  rien (code 0) · une ligne par constat (code 1) · erreur (2)
#  `--machine` : une ligne `motif<TAB>texte` par constat, pour le canal
#  (Jira, lot C) — le motif est le label de déduplication du ticket.
# ══════════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# ⚠️ IMPORTÉ, PAS RECOPIÉ. Le seuil mémoire est celui que le run crie
# lui-même (`score.py`, `MAX_RSS_MO`, 2 800 Mo au 10/09). Une copie ici
# serait le jour où l'un des deux ment — leçon de `LEVELS`, reprise par
# `audit_r2.py` pour ses paliers.
from score import MAX_RSS_MO  # noqa: E402

from registre_nuit import NOM_REGISTRE, charger  # noqa: E402

#: Cinq relevés, comme `audit_r2.MINI_RELEVES` : quatre différences, dont
#: le 25e centile ignore les DEUX plus grandes. Une remontée de série (un
#: lot) et un réchauffage de cache dans la même semaine ne font pas une
#: pente. Réglable — `BW_CONTROLE_MINI_RELEVES` — pour le rétro-remplissage
#: des premiers jours seulement.
MINI_RELEVES = int(os.environ.get("BW_CONTROLE_MINI_RELEVES", "5"))
QUANTILE_PENTE = float(os.environ.get("BW_CONTROLE_QUANTILE", "0.25"))

#: ⚠️ DEUX PENTES, ET C'EST LA DIFFÉRENCE AVEC R2. Là-bas, le danger
#: était le FAUX POSITIF (une marche lue comme une fuite) : le quantile
#: bas suffit. Ici, la série ACCÉLÈRE (+205, +288, +189 s sur les trois
#: dernières nuits du 10/09, contre +59 la semaine d'avant) : le quantile
#: bas seul aurait annoncé, le 04/09, un franchissement « le 30/09 » —
#: la nuit du 09/09 a fini à 229 s du garde. Le 25e centile décide donc
#: SI ça monte (le silence reste protégé des marches) ; le 75e donne la
#: date la plus PROCHE, et la ligne rend les deux : « entre le 18/09 et
#: le 27/09 ». Une fourchette honnête vaut mieux qu'une date optimiste.
QUANTILE_HAUT = float(os.environ.get("BW_CONTROLE_QUANTILE_HAUT", "0.75"))

#: Au-delà de cet horizon, un franchissement n'est pas une nouvelle : à
#: +10 s/nuit, 5 400 s sont à cinq mois, et le dire chaque matin userait
#: le canal. 30 jours = le temps de lire, de décider, et de déployer.
HORIZON_J = int(os.environ.get("BW_CONTROLE_HORIZON_J", "30"))

#: Les relevés lus pour la pente : les N derniers comparables. Assez pour
#: absorber deux marches, pas assez pour qu'une pente d'il y a trois
#: semaines pèse encore sur l'échéance d'aujourd'hui.
FENETRE_RELEVES = int(os.environ.get("BW_CONTROLE_FENETRE", "10"))

MOTIF_DUREE = "bw-pente-duree"
MOTIF_MEMOIRE = "bw-pente-memoire"
MOTIF_PURGE = "bw-purge-57014"


# ══════════════════════════════════════════════════════════════════════
#  PARTIE PURE
# ══════════════════════════════════════════════════════════════════════
def comparable(r: dict) -> bool:
    """Un relevé qui peut entrer dans une pente : lancé par le TIMER,
    fini en SUCCÈS, avec une durée. Tout le reste est un silence."""
    return (r.get("lancement") == "timer"
            and r.get("result") == "success"
            and r.get("exec_status") == 0
            and isinstance(r.get("duree_s"), (int, float))
            and r.get("jour") is not None)


def _quantile(valeurs, q: float) -> float:
    """Même définition qu'`audit_r2._quantile` (interpolation linéaire
    entre rangs) — sur quatre valeurs, le rang le plus proche du 25e
    centile serait le MINIMUM, qu'on ne veut pas."""
    s = sorted(valeurs)
    if len(s) == 1:
        return s[0]
    pos = q * (len(s) - 1)
    bas = int(pos)
    haut = min(bas + 1, len(s) - 1)
    return s[bas] + (s[haut] - s[bas]) * (pos - bas)


def pente_par_nuit(pts, mini: int = MINI_RELEVES,
                   q: float = QUANTILE_PENTE) -> float | None:
    """`pts` = [(date, valeur)] déjà comparables, une valeur par nuit.
    Rend le 25e centile des vitesses entre relevés consécutifs, en
    unité/nuit — ou `None` sous `mini` relevés (mieux vaut « pas de
    pente » qu'une pente sur trois points, où une marche et une
    croissance se ressemblent)."""
    pts = sorted(pts, key=lambda p: p[0])
    # Deux relevés le même jour (rejeu + timer) : le dernier compte.
    vus: dict = {}
    for d, v in pts:
        vus[d] = v
    pts = sorted(vus.items())
    if len(pts) < mini:
        return None
    vitesses = [(v1 - v0) / max(1, (d1 - d0).days)
                for (d0, v0), (d1, v1) in zip(pts, pts[1:])]
    return _quantile(vitesses, q)


def franchissement(dernier: float, pente: float | None, cible: float,
                   jour: date) -> date | None:
    """La date où la série, partie de `dernier` le `jour`, atteint
    `cible` à cette pente. `None` si la pente est nulle, négative ou
    inconnue : une série qui descend n'a pas d'échéance, et prétendre le
    contraire ferait crier sur un run en train de se ranger."""
    if pente is None or pente <= 0:
        return None
    if dernier >= cible:
        return jour
    return jour + timedelta(days=int((cible - dernier) / pente + 0.999999))


def premier_depassement(pts, cible: float) -> date | None:
    """La première nuit (parmi les comparables) où la série a dépassé
    `cible` — pour dire « au-dessus depuis le … » plutôt qu'une date
    dans le passé qui se lirait comme une erreur."""
    for d, v in sorted(pts, key=lambda p: p[0]):
        if v >= cible:
            return d
    return None


def _serie(releves, cle: str):
    """[(date, valeur)] des relevés comparables qui PORTENT la clé.
    ⚠️ `r.get(cle) is None` ⇒ la nuit est SAUTÉE, pas comptée à 0."""
    out = []
    for r in releves:
        if not comparable(r) or r.get(cle) is None:
            continue
        out.append((date.fromisoformat(r["jour"]), float(r[cle])))
    return out[-FENETRE_RELEVES:] if FENETRE_RELEVES else out


def constats(releves: list[dict], jour: date, horizon_j: int = HORIZON_J,
             seuil_mo: float = MAX_RSS_MO) -> list[dict]:
    """Les constats du matin : au plus un pour la durée, un pour la
    mémoire, et AUCUN quand rien ne monte vers rien d'atteignable.

    Chaque constat porte `motif` (le label de déduplication du canal),
    `texte` (la ligne lisible), `date` (le franchissement) et les chiffres.
    """
    out: list[dict] = []
    comparables = [r for r in releves if comparable(r)]
    if not comparables:
        return out
    dernier = comparables[-1]

    # ── la durée, contre le chien de garde APPLIQUÉ la dernière nuit ──
    garde = dernier.get("garde_s")
    if garde:
        c = _constat(_serie(releves, "duree_s"), garde, jour, horizon_j,
                     MOTIF_DUREE, "durée", "s", "le garde")
        if c:
            out.append(c)

    # ── la mémoire, contre le seuil que le run crie lui-même ──
    swap = dernier.get("swap_peak_mo")
    c = _constat(_serie(releves, "jalon_max_mo"), seuil_mo, jour, horizon_j,
                 MOTIF_MEMOIRE, "mémoire", "Mo", "le seuil",
                 plancher=(f" (plancher : {_n(swap)} Mo de swap au pic)"
                           if swap else ""))
    if c:
        out.append(c)

    # ── la purge qui ne mord plus (le 57014 du 10/09) ──
    # ⛔ Pas une pente : un FAIT, et il s'auto-amplifie — une purge ratée
    # double la suivante (enquete-pente-10-09.md §1.4). Il est dit chaque
    # matin où il se produit ; c'est le canal (un commentaire par jour
    # sur le même ticket) qui empêche le bruit, pas le silence.
    releve_nuit = releves[-1] if releves else {}
    purges = [i for i in (releve_nuit.get("incidents") or [])
              if i.startswith("⚠️ purge ") and "HTTP" in i]
    if purges and releve_nuit.get("jour") == jour.isoformat():
        tables = ", ".join(i.split(" ")[2] for i in purges)
        out.append({"motif": MOTIF_PURGE, "date": jour.isoformat(),
                    "valeur": len(purges), "pente": None, "cible": None,
                    "texte": (f"purge en échec cette nuit ({tables}) : "
                              f"{'; '.join(purges)} — chaque nuit ratée "
                              f"double la suivante")})
    return out


def _constat(serie, cible: float, jour: date, horizon_j: int, motif: str,
             nom: str, unite: str, quoi: str, plancher: str = "") -> dict | None:
    """Un constat, ou `None` — le silence.

    ⛔ LE SILENCE SE DÉCIDE SUR LA PENTE BASSE (25e centile) : une série
    qui ne monte pas au sens robuste ne fait pas parler, quelles que
    soient ses deux plus grandes différences. LA DATE LA PLUS PROCHE se
    calcule sur la pente haute (75e) : c'est celle qu'un chien de garde
    doit craindre. Les deux dates sont rendues.
    """
    if not serie:
        return None
    p_basse = pente_par_nuit(serie)
    p_haute = pente_par_nuit(serie, q=QUANTILE_HAUT)
    d, v = serie[-1]
    f_tard = franchissement(v, p_basse, cible, d)
    if f_tard is None or (f_tard - jour).days > horizon_j:
        return None
    f_tot = franchissement(v, p_haute, cible, d) or f_tard
    if v >= cible:
        quand = (f"AU-DESSUS {quoi.replace('le ', 'du ', 1)} ({_n(cible)} "
                 f"{unite}) depuis le {premier_depassement(serie, cible):%d/%m}")
    elif f_tot == f_tard:
        quand = f"franchit {quoi} ({_n(cible)} {unite}) le {f_tot:%d/%m}"
    else:
        quand = (f"franchit {quoi} ({_n(cible)} {unite}) entre le "
                 f"{f_tot:%d/%m} et le {f_tard:%d/%m}")
    pente_txt = (f"{p_basse:+.0f} {unite}/nuit" if abs(p_haute - p_basse) < 0.5
                 else f"{p_basse:+.0f} à {p_haute:+.0f} {unite}/nuit")
    return {"motif": motif, "date": f_tot.isoformat(),
            "date_tard": f_tard.isoformat(), "valeur": v,
            "pente": p_basse, "pente_haute": p_haute, "cible": cible,
            "texte": f"{nom} {_n(v)} {unite}{plancher}, {pente_txt} → {quand}"}


def _n(v) -> str:
    """3860 → « 3 860 ». Espace ORDINAIRE, pas l'insécable fine des
    rapports : la ligne devient un titre de ticket Jira après un
    `iconv … ASCII//TRANSLIT`, et l'insécable y fait tomber le reste de
    la ligne (vu sur macOS le 10/09 : « dur'ee 3 » et plus rien)."""
    return f"{int(round(float(v))):,}".replace(",", " ")


def proposition(c: dict) -> str:
    """Ce que le contrôle PROPOSE — jamais ce qu'il fait. Pour la durée,
    la commande exacte de la remontée, à condition que la mesure soit
    écrite dans l'en-tête du drop-in ; pour la mémoire, le remède
    mesuré le 10/09 (élaguer `units`, enquete-pente-10-09.md §2.5)."""
    if c["motif"] == MOTIF_PURGE:
        return ("   → à décider par Yann : depuis le 10/09 la purge va par tranches "
                "(`delete_par_tranches`, 20 000 lignes, comptées) et le rattrapage "
                "est `score.py --purge-seule` ;\n     si ça expire ENCORE, ce n'est "
                "plus la taille du retard, c'est la base (enquete-pente-10-09.md "
                "§1.6, §5). Ce script ne joue aucun SQL.")
    if c["motif"] == MOTIF_DUREE:
        minutes = int(c["cible"] // 60)
        # Dix nuits de pente HAUTE, arrondies aux 5 min au-dessus : c'est
        # l'ordre de grandeur des trois remontées faites à la main
        # (+15, +25, +25 min), et dix nuits est le délai qu'un lot met à
        # sortir. Une proposition, pas une consigne.
        cible = minutes + int((c["pente_haute"] * 10) // 60 // 5 * 5 + 5)
        return (
            "   → à décider par Yann, pas par ce script : soit alléger le run "
            "(enquete-pente-10-09.md §2.5, §4), soit remonter le chien de garde\n"
            f"     en ÉCRIVANT cette mesure dans l'en-tête de "
            f"model-verif/systemd/bw-model-score.service.d/10-timeout-s3.conf "
            f"({minutes} → {cible} min, TimeoutStartSec au-dessus), puis :\n"
            "     sudo cp model-verif/systemd/bw-model-score.service.d/10-timeout-s3.conf "
            "/etc/systemd/system/bw-model-score.service.d/ && sudo systemctl daemon-reload\n"
            "     systemctl show bw-model-score.service -p Environment -p TimeoutStartUSec")
    return (
        "   → à décider par Yann : le porteur était `units` (fenêtre rejouée, "
        "≈ 3 070 Mo le 10/09), élaguée à 22 clés depuis le 10/09 (`CLES_REJEU`, "
        "≈ −1 500 Mo).\n     Si ça remonte encore : `--regime-days` (30), ou la "
        "structure par case (enquete-pente-10-09.md §2.5). Ce script ne touche "
        "ni au seuil ni au swap.")


# ══════════════════════════════════════════════════════════════════════
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Contrôle de pente de la notation.")
    p.add_argument("--out", default=os.environ.get("BW_MODEL_VERIF_ETAT",
                                                   "/var/lib/bw-model-verif"))
    p.add_argument("--jour", help="AAAA-MM-JJ (défaut : aujourd'hui)")
    p.add_argument("--horizon-j", type=int, default=HORIZON_J)
    p.add_argument("--machine", action="store_true",
                   help="une ligne `motif<TAB>texte` par constat")
    p.add_argument("--verbeux", action="store_true",
                   help="dit aussi ce qui se tait, et pourquoi")
    a = p.parse_args(argv)

    jour = date.fromisoformat(a.jour) if a.jour else date.today()
    registre = Path(a.out) / NOM_REGISTRE
    releves = charger(registre)
    if not releves:
        print(f"⚠️ registre absent ou vide : {registre} — rien à mesurer "
              f"(rétro-remplissage : registre_nuit.py --retro)", file=sys.stderr)
        return 2

    cs = constats(releves, jour, a.horizon_j)
    if a.verbeux:
        n_comp = sum(1 for r in releves if comparable(r))
        s_d, s_m = _serie(releves, "duree_s"), _serie(releves, "jalon_max_mo")
        pd, pm = pente_par_nuit(s_d), pente_par_nuit(s_m)
        print(f"ⓘ {len(releves)} relevé(s), {n_comp} comparable(s) ; "
              f"durée : {len(s_d)} points, pente "
              f"{'—' if pd is None else f'{pd:+.0f} s/nuit'} ; "
              f"mémoire : {len(s_m)} points, pente "
              f"{'—' if pm is None else f'{pm:+.0f} Mo/nuit'} ; "
              f"horizon {a.horizon_j} j ; seuil {MAX_RSS_MO:.0f} Mo")
        if not cs:
            print("ⓘ rien à dire : pente plate/négative, ou échéance hors horizon")
    if not cs:
        return 0
    for c in cs:
        if a.machine:
            print(f"{c['motif']}\t{c['texte']}")
        else:
            print(c["texte"])
            print(proposition(c))
    return 1


if __name__ == "__main__":
    sys.exit(main())
