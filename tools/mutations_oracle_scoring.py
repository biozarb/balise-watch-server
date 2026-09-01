#!/usr/bin/env python3
"""Rejoue le banc de l'oracle L12 contre des variantes CASSEES.

⛔ UN BANC VERT NE PROUVE RIEN TANT QU'ON N'A PAS VU CE QUI LE FAIT
ROUGIR — et pour un ORACLE, moins qu'ailleurs encore. Un oracle qui se
trompe ne plante pas : il rend ✅ tous les mois, et sa seule trace est
un rapport que personne ne relit parce qu'il n'a jamais rien dit. La
mutation nº 1 est exactement celle-la : on retire le garde-fou
d'independance, l'oracle se met a importer la chaine, et il approuve
n'importe quoi.

Restauration en `finally` : les fichiers reviennent a leur etat
d'origine meme si l'on interrompt.

    python3 tools/mutations_oracle_scoring.py
"""
import pathlib
import shutil
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
ORACLE = ICI / "oracle_scoring.py"
BANC = "test_oracle_scoring.py"

MUTATIONS = [
    # ── ⛔⛔ LA FAUTE CENTRALE ────────────────────────────────────────
    ("⛔⛔ le garde-fou d'independance est retire : l'oracle peut "
     "importer la chaine, donc comparer la faute a elle-meme — et rendre "
     "✅ la nuit ou l'EWMA repart de zero",
     ORACLE,
     '_INTERDITS = ("scoring", "score", "inference", "murphy", "duel", "collect")',
     '_INTERDITS = ()'),

    # ── l'appariement ───────────────────────────────────────────────
    ("la demi-fenetre passe a ±25 min : deux echeances partagent des "
     "releves, l'oracle mesure une autre population que la chaine",
     ORACLE,
     'DEMI_FENETRE_MS = {3600: 20 * 60 * 1000, 900: 7 * 60 * 1000}',
     'DEMI_FENETRE_MS = {3600: 25 * 60 * 1000, 900: 7 * 60 * 1000}'),

    ("±30 min a l'heure ronde : 2×demi = pas, l'invariant tombe — et "
     "il doit tomber A L'IMPORT, pas au premier appel",
     ORACLE,
     'DEMI_FENETRE_MS = {3600: 20 * 60 * 1000, 900: 7 * 60 * 1000}',
     'DEMI_FENETRE_MS = {3600: 30 * 60 * 1000, 900: 7 * 60 * 1000}'),

    ("la fenetre d'agregation est fermee a droite en exclusif : le "
     "releve pose exactement a t+demi est jete",
     ORACLE,
     '        d = int(np.searchsorted(t_obs, t + demi_ms, side="right"))',
     '        d = int(np.searchsorted(t_obs, t + demi_ms, side="left"))'),

    ("le plancher tombe a 2 heures : une mediane sur deux points est "
     "publiee comme un score",
     ORACLE,
     'PLANCHER_PAR_PAS = {3600: 6, 900: 13}',
     'PLANCHER_PAR_PAS = {3600: 2, 900: 13}'),

    ("la journee n'est plus bornee a droite : les echeances de J+1 "
     "entrent dans la note de J",
     ORACLE,
     '        if t < debut_ms or t >= fin_ms:',
     '        if t < debut_ms:'),

    # ── le vent ─────────────────────────────────────────────────────
    ("⛔ la direction observee est une moyenne ARITHMETIQUE : 350° et "
     "10° donnent plein sud, et l'erreur double sans rien casser",
     ORACLE,
     '            obs_dir = (math.degrees(math.atan2(u, v)) + 360.0) % 360.0',
     '            obs_dir = float(dw[avec_dir].mean())'),

    ("les releves sous le seuil entrent dans le vecteur : du bruit "
     "uniforme tire la direction moyenne vers zero",
     ORACLE,
     '        avec_dir = avec_vitesse & ~np.isnan(dw) & (sw >= VENT_MIN_DIR_KMH)',
     '        avec_dir = avec_vitesse & ~np.isnan(dw)'),

    ("le seuil de girouette passe a 0 : on note un cap la ou il n'y a "
     "que du bruit",
     ORACLE,
     'VENT_MIN_DIR_KMH = 5.0',
     'VENT_MIN_DIR_KMH = 0.0'),

    ("le RMS devient une moyenne d'erreurs : la sensibilite aux "
     "queues disparait, et c'est elle qu'on publie",
     ORACLE,
     '                    "rms": (math.sqrt(float((a * a).mean()))',
     '                    "rms": (float(a.mean())'),

    # ── les etiquettes ──────────────────────────────────────────────
    ("le `lead_h` declare par la ligne est ignore : les classes courte "
     "et au quart d'heure atterrissent sous `lead_h = 6`",
     ORACLE,
     '                lead = ligne.get("lead_h")\n'
     '                lead = LEAD_PAR_OFFSET[offset] if lead is None else int(lead)',
     '                lead = LEAD_PAR_OFFSET[offset]'),

    # ── l'enumeration du disque ─────────────────────────────────────
    ("l'enumeration prend TOUS les fichiers du dossier : les jumeaux "
     "`.r2ok` et les manifestes sont ouverts comme des archives",
     ORACLE,
     '            f"{jour:%Y/%m}/{nom}_{jour:%Y-%m-%d}*.ndjson.gz"))',
     '            f"{jour:%Y/%m}/{nom}_{jour:%Y-%m-%d}*"))'),

    ("l'enumeration exige le nom exact : la partie 2 de `fcst/` n'est "
     "plus lue, et sept modeles disparaissent en silence",
     ORACLE,
     '            f"{jour:%Y/%m}/{nom}_{jour:%Y-%m-%d}*.ndjson.gz"))',
     '            f"{jour:%Y/%m}/{nom}_{jour:%Y-%m-%d}.ndjson.gz"))'),

    # ── les cases ───────────────────────────────────────────────────
    ("le quorum tombe a une balise : un score de zone qui est celui "
     "d'une seule balise",
     ORACLE,
     'MIN_BALISES_CASE = 3',
     'MIN_BALISES_CASE = 1'),

    ("l'exclusion des doublons d'inscription (lot L17) saute : des "
     "cases n'existent que grace a une seconde inscription du meme "
     "capteur",
     ORACLE,
     '            if z.get("doublon_de"):',
     '            if False:'),

    ("la case publie une MOYENNE la ou la chaine publie une mediane — "
     "un chiffre plausible, faux, et qui ne rougit nulle part",
     ORACLE,
     '                "med": float(np.median(np.asarray(b["v"], dtype=float))),',
     '                "med": float(np.mean(np.asarray(b["v"], dtype=float))),'),

    ("la chaine de repli met le MASSIF avant la FORME : un fond de "
     "vallee encaisse est compare a une crete du meme massif",
     ORACLE,
     '    chaine.append((f"*:{forme}", "landform"))\n'
     '    if massif:\n'
     '        chaine.append((f"{massif}:*", "massif"))',
     '    if massif:\n'
     '        chaine.append((f"{massif}:*", "massif"))\n'
     '    chaine.append((f"*:{forme}", "landform"))'),

    # ── la confrontation ────────────────────────────────────────────
    ("la confrontation ne regarde qu'un sens : une nuit qui n'ecrit "
     "rien ne produit aucun ecart, donc aucune alerte",
     ORACLE,
     '        if cle not in oracle:\n'
     '            res["base_seule"].append((cle, b))',
     '        if False:\n'
     '            res["base_seule"].append((cle, b))'),

    ("le seuil de nommage passe a 1 km/h : l'oracle se tait sur tout "
     "ce qui compte, et son rapport reste vert",
     ORACLE,
     'SEUIL_ECART_KMH = 0.01',
     'SEUIL_ECART_KMH = 1.0'),

    ("PAGE depasse le plafond serveur : la premiere page plafonnee "
     "passe pour la fin de la table, et l'oracle confronte une base "
     "tronquee (defaut du 08/08)",
     ORACLE,
     '    PAGE = 1000',
     '    PAGE = 10000'),
]


def jouer(banc: str) -> bool:
    """Vrai si le banc PASSE."""
    r = subprocess.run([sys.executable, str(ICI / banc)],
                       capture_output=True, text=True, cwd=str(ICI))
    return r.returncode == 0


def main() -> int:
    if not jouer(BANC):
        print("⛔ le banc est DEJA rouge sans mutation : rien a prouver.")
        return 2
    print(f"✅ banc de reference vert ({BANC})\n")
    sauvegardes = {}
    survivantes = []
    try:
        for i, (titre, fichier, avant, apres) in enumerate(MUTATIONS, 1):
            if fichier not in sauvegardes:
                sauvegardes[fichier] = fichier.read_text(encoding="utf-8")
            src = sauvegardes[fichier]
            if avant not in src:
                print(f"{i:2}. ⛔ MOTIF INTROUVABLE — la mutation ne "
                      f"s'applique plus : {titre}")
                survivantes.append(titre)
                continue
            fichier.write_text(src.replace(avant, apres, 1), encoding="utf-8")
            try:
                passe = jouer(BANC)
            finally:
                fichier.write_text(src, encoding="utf-8")
            if passe:
                print(f"{i:2}. ❌ SURVIT — le banc ne la voit pas : {titre}")
                survivantes.append(titre)
            else:
                print(f"{i:2}. ✅ tuee : {titre}")
    finally:
        for fichier, src in sauvegardes.items():
            fichier.write_text(src, encoding="utf-8")
    print("\n" + "═" * 66)
    print(f"  {len(MUTATIONS) - len(survivantes)}/{len(MUTATIONS)} mutations tuees")
    if survivantes:
        print("❌ mutations SURVIVANTES :")
        for s in survivantes:
            print(f"   · {s}")
        return 1
    print("✅ toutes les mutations sont tuees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
