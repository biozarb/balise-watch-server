#!/usr/bin/env python3
"""Rejoue le banc de `score.py` contre des variantes CASSEES des deux
gestes du lot L13 — le corps d'erreur de la purge, et la table
colonne -> fichier `.sql`.

⛔ UN BANC VERT NE PROUVE RIEN TANT QU'ON N'A PAS VU CE QUI LE FAIT
ROUGIR. Les deux gestes de ce lot cassent en SILENCE, et pas de la
meme facon :

  · la purge, cote DIAGNOSTIC : reperdre le corps de l'erreur ne casse
    aucune nuit — le run finit vert, le journal dit « HTTP 500 », et on
    repart pour cinq jours d'hypothese non tranchee. C'est l'etat
    d'AVANT le lot, et il a l'air normal ;
  · la purge, cote GESTE : compter puis supprimer QUAND MEME (ou pire,
    prendre « je ne sais pas » pour « zero » et ne plus jamais purger)
    ne se voit pas non plus. Le second ne se verrait qu'en mars 2027,
    quand la table cesserait de maigrir ;
  · la table colonne -> `.sql`, cote MENSONGE : remettre un repli
    « sinon step40 » redonne un message PLAUSIBLE et FAUX — celui qui a
    coute la session de l'audit §2.5. Rien ne rougit : un fichier
    existe, son nom s'imprime, et Yann le rejoue pour rien ;
  · la table, cote MUTISME : ne nommer que le PREMIER fichier concerne
    (la cascade d'avant) laisse une migration en attente sans que
    personne la voie.

Restauration en `finally` : les fichiers reviennent a leur etat
d'origine meme si l'on interrompt.

    python3 model-verif/mutations_l13_ops.py
"""
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent

# ⛔ (02/09/2026) copie d'origine sur le disque + sha256 + purge du
# bytecode, pour TOUS les harnais — voir `model-verif/harnais.py`.
sys.path.insert(0, str(ICI))
import harnais as HARNAIS  # noqa: E402
SCORE = ICI / "score.py"
BANC = "test_score.py"

MUTATIONS = [
    # ══ geste 1a : le corps de l'erreur ═════════════════════════════
    ("⛔⛔ `delete` reperd le corps de l'erreur — c'est l'etat d'avant "
     "le lot L13 : trois nuits de HTTP 500 et pas un mot de plus",
     SCORE,
     '            print(f"  ⚠️ purge {table} : HTTP {e.code} — "\n'
     '                  f"{_detail_erreur(e.read(ERREUR_OCTETS))}", file=sys.stderr)',
     '            print(f"  ⚠️ purge {table} : HTTP {e.code}", file=sys.stderr)'),

    ("⛔ le corps est lu mais TRONQUE a 40 octets : `57014` tombe apres "
     "le `code`, et le message utile disparait comme avant le 28/08",
     SCORE,
     '            print(f"  ⚠️ purge {table} : HTTP {e.code} — "\n'
     '                  f"{_detail_erreur(e.read(ERREUR_OCTETS))}", file=sys.stderr)',
     '            print(f"  ⚠️ purge {table} : HTTP {e.code} — "\n'
     '                  f"{e.read(40)}", file=sys.stderr)'),

    ("⛔ `delete` LEVE au lieu de journaliser : la purge est la derniere "
     "etape du run, un run entierement ecrit tomberait pour du menage "
     "qui ne concerne aucune ligne",
     SCORE,
     '            print(f"  ⚠️ purge {table} : HTTP {e.code} — "\n'
     '                  f"{_detail_erreur(e.read(ERREUR_OCTETS))}", file=sys.stderr)',
     '            raise Abort(f"purge {table} : HTTP {e.code}") from e'),

    # ══ geste 1b : compter avant de supprimer ═══════════════════════
    ("⛔⛔ le compte est fait puis IGNORE : le DELETE repart chaque nuit "
     "contre 1 223 107 lignes sans index, pour zero ligne a jeter",
     SCORE,
     '    if vieux_caractere == 0:',
     '    if False:'),

    ("⛔⛔ « je ne sais pas » devient « zero » : un compte qui echoue "
     "annule la purge EN SILENCE, et plus rien ne se purge jamais",
     SCORE,
     '    if vieux_caractere == 0:',
     '    if not vieux_caractere:'),

    ("⛔ le compte porte sur la table ENTIERE (filtre perdu) : il rend "
     "1 223 107, donc jamais zero, donc le DELETE part toujours",
     SCORE,
     '    vieux_caractere = sb.compte("model_character", filtre_caractere)',
     '    vieux_caractere = sb.compte("model_character")'),

    ("⛔ `compte` prend un refus du serveur pour un zero : meme effet "
     "que la mutation precedente, un cran plus bas",
     SCORE,
     '            print(f"  ⚠️ compte {table} : HTTP {e.code} — "\n'
     '                  f"{_detail_erreur(e.read(ERREUR_OCTETS))}", file=sys.stderr)\n'
     '            return None',
     '            print(f"  ⚠️ compte {table} : HTTP {e.code}", file=sys.stderr)\n'
     '            return 0'),

    ("⛔ `compte` lit le mauvais bout du `content-range` : `0-0/1223107` "
     "rendrait 0 (le debut de la plage) au lieu du total",
     SCORE,
     '        total = entete.rsplit("/", 1)[-1]',
     '        total = entete.split("-", 1)[0]'),

    # ══ geste 2 : la table colonne -> fichier ═══════════════════════
    ("⛔⛔ le repli « sinon step40 » revient : une colonne qu'AUCUN "
     "fichier ne porte renvoie vers un `.sql` passe le 07/08 — la faute "
     "exacte de l'audit §2.5, plausible et fausse",
     SCORE,
     '        bouts.append(f"⛔ AUCUN .sql connu n\'ajoute "',
     '        return "Lancer supabase_step40_lot_g.sql pour les activer."\n'
     '    if orphelines:\n'
     '        bouts.append(f"⛔ AUCUN .sql connu n\'ajoute "'),

    ("⛔ le cas « migration a ecrire » se tait : les colonnes orphelines "
     "ne sont plus nommees du tout, et l'absence passe pour un schema "
     "a jour",
     SCORE,
     '    if orphelines:\n'
     '        bouts.append(f"⛔ AUCUN .sql connu n\'ajoute "',
     '    if False:\n'
     '        bouts.append(f"⛔ AUCUN .sql connu n\'ajoute "'),

    ("⛔ seul le PREMIER fichier concerne est nomme (la cascade d'avant) "
     ": deux migrations en attente, une seule annoncee",
     SCORE,
     '    for fichier in sorted(par_fichier, key=_rang_step):',
     '    for fichier in sorted(par_fichier, key=_rang_step)[:1]:'),

    ("⛔ la table perd l'entree `rank_corr` : la colonne du step52 "
     "redevient orpheline, et le banc doit le voir",
     SCORE,
     '        "rank_corr": "supabase_step52_rank_corr.sql",',
     '        "rank_corr": "supabase_step40_lot_g.sql",'),

    ("⛔ les fichiers sont cites dans l'ordre alphabetique inverse : "
     "step57 avant step40, l'ordre des migrations n'est plus l'ordre "
     "dans lequel les jouer",
     SCORE,
     '    for fichier in sorted(par_fichier, key=_rang_step):',
     '    for fichier in sorted(par_fichier, key=_rang_step, reverse=True):'),
]


def jouer(banc: str) -> bool:
    r = subprocess.run([sys.executable, str(ICI / banc)],
                       capture_output=True, text=True, cwd=str(ICI),
                       env=HARNAIS.env_banc(ICI))
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
                sauvegardes[fichier] = HARNAIS.garder(fichier)
            src = sauvegardes[fichier]
            if avant not in src:
                print(f"{i:2}. ⛔ MOTIF INTROUVABLE : {titre}")
                survivantes.append(titre)
                continue
            fichier.write_text(src.replace(avant, apres, 1), encoding="utf-8")
            try:
                passe = jouer(BANC)
            finally:
                fichier.write_text(src, encoding="utf-8")
            if passe:
                print(f"{i:2}. ❌ SURVIT : {titre}")
                survivantes.append(titre)
            else:
                print(f"{i:2}. ✅ tuee : {titre}")
    finally:
        for fichier, src in sauvegardes.items():
            HARNAIS.rendre(fichier, src)
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
