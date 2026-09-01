#!/usr/bin/env python3
"""Rejoue `tools/test_deploiement.sh` contre des variantes CASSÉES du
chemin de déploiement (lot LD, 31/08/2026).

⛔ POURQUOI CE FICHIER EXISTE, EN UNE PHRASE. Le 31/08, six fichiers
d'unité systemd n'étaient jamais arrivés sur le VPS depuis trois
semaines, et TOUT ÉTAIT VERT : le rsync (qui les jetait par filtre), le
contrôle sha256 (qui portait le même filtre, donc ne pouvait pas les
voir), et le message final. *Rien ne rougissait — c'était tout le
problème.* Un banc écrit après coup ne vaut donc rien tant qu'on n'a pas
vu la faute d'origine le faire rougir.

⭐ LA MUTATION CENTRALE EST LA nº 1 : remettre le filtre `--include
'*.py' --include '*.sh' --exclude '*'` de la ligne 72 d'avant. Si le banc
reste vert avec ce filtre, c'est le banc qu'il faut jeter.

⚠️ Harnais : même forme que `model-verif/mutations_pas_15min.py`
(restauration en `finally`, contrôle d'intégrité du motif `avant`). Pas
de ménage de `__pycache__` ici — les cibles sont du bash et des unités
systemd, il n'y a pas de bytecode à recharger.
⚠️ `bash` ne relit pas de cache : la seule chose qui puisse mentir ici
est une campagne PARALLÈLE (piège nº 7 du 28/08, lot L9). Vérifier
qu'aucune ne tourne avant d'en lancer une.

    python3 tools/mutations_deploiement.py
"""
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
RACINE = ICI.parent
DEPLOY = ICI / "deploy-agrume-vps.sh"
BANC = ["bash", str(ICI / "test_deploiement.sh")]
QUART_TIMER = RACINE / "model-verif/systemd/bw-model-agrume-quart.timer"

MUTATIONS = [
    # ── ⛔⛔ LA FAUTE D'ORIGINE, REMISE TELLE QUELLE ──────────────────
    ("⛔⛔ LE FILTRE DU 13/08 EST REMIS : model-verif/ ne transporte que "
     "*.py et *.sh — les six unités des L8/L10/L11 repartent au néant, "
     "en silence, pendant que le script annonce « tout est vert »",
     DEPLOY,
     'bw_rsync_sans_perms() { rsync -rtv "${BW_RSYNC_EXCLUDE[@]}" "$1/" "$2/"; }',
     'bw_rsync_sans_perms() { rsync -rtv "${BW_RSYNC_EXCLUDE[@]}" '
     "--include '*/' --include '*.py' --include '*.sh' --exclude '*' "
     '"$1/" "$2/"; }'),

    ("⛔⛔ LE CONTRÔLE REPREND LE FILTRE DU TRANSPORT : `find` ne regarde "
     "que *.py et *.sh — c'est l'angle mort qui rendait ✅ VERT sur 162 "
     "fichiers pendant que dix manquaient",
     DEPLOY,
     'bw_trouve() { printf "find %s -type f%s -print0" "${BW_DOSSIERS[*]}" "$(bw_find_filtre)"; }',
     'bw_trouve() { printf "find %s -type f \\\\( -name \'*.py\' -o -name \'*.sh\' \\\\)%s -print0" '
     '"${BW_DOSSIERS[*]}" "$(bw_find_filtre)"; }'),

    # ── le périmètre ────────────────────────────────────────────────
    ("⛔ `traces/` ressort du CONTRÔLE — l'alerte morte du poller "
     "Infoclimat redevient invisible",
     DEPLOY,
     'BW_DOSSIERS=(agrume verif tools model-verif traces)',
     'BW_DOSSIERS=(agrume verif tools model-verif)'),

    ("⛔ `traces/` ressort du TRANSPORT — il est contrôlé mais plus "
     "envoyé : exactement l'état de `model-verif/` le 26/08",
     DEPLOY,
     'BW_TRANSPORT_PERMS=(agrume verif tools traces)',
     'BW_TRANSPORT_PERMS=(agrume verif tools)'),

    # ── les exclusions, et le piège des deux racines ────────────────
    ("⛔ `traces_cache` redevient un motif à CHEMIN — inerte côté rsync, "
     "actif côté find : le cache d'exécution part sur le VPS et le "
     "contrôle ne le voit pas. Les deux filtres divergent à nouveau",
     DEPLOY,
     "  'traces_cache'         # ⛔ ÉTAT D'EXÉCUTION",
     "  'traces/traces_cache'  # ⛔ ÉTAT D'EXÉCUTION"),

    ("l'exclusion `traces_cache` disparaît : le contrôle rougira toutes "
     "les nuits sur un log réécrit par la production, et finira désarmé",
     DEPLOY,
     "  'traces_cache'         # ⛔ ÉTAT D'EXÉCUTION",
     "  'inutilise_xyz'        # ⛔ ÉTAT D'EXÉCUTION"),

    ("`*.bak-*` disparaît : les deux `.bak-pre-lotG` DÉJÀ PRÉSENTS sur "
     "le VPS feraient rougir chaque déploiement pour deux fichiers morts",
     DEPLOY,
     "  '*.bak-*'              # ⚠️ `*.bak` NE SUFFIT PAS",
     "  '*.bakXXX'             # ⚠️ `*.bak` NE SUFFIT PAS"),

    ("⛔ le filtre `find` perd son prédicat de CHEMIN : `__pycache__` est "
     "écarté mais pas les `.pyc` qu'il contient — le contrôle rougirait "
     "sur du bytecode",
     DEPLOY,
     "    out+=\" ! -name '$m' ! -path '*/$m/*'\"",
     "    out+=\" ! -name '$m'\""),

    # ── les verdicts dépôt ↔ /etc ───────────────────────────────────
    ("⛔⛔ UNE UNITÉ NEUVE, JAMAIS DÉPLOYÉE, DEVIENT MUETTE — c'est le "
     "cas EXACT qui a produit ce lot, et que six fichiers ont raté",
     DEPLOY,
     "    ABSENT)    printf 'MANQUANTE' ;;",
     "    ABSENT)    printf 'IDENTIQUE' ;;"),

    ("⛔ une unité ILLISIBLE (0600 root) est comptée VERTE — on affirme "
     "identique ce qu'on n'a pas pu lire ; la réserve du L8 tombe",
     DEPLOY,
     "    ILLISIBLE) if [ -n \"$taille\" ]",
     "    ILLISIBLE) printf 'IDENTIQUE'; return 0\n               if [ -n \"$taille\" ]"),
    # ⓘ 01/09 (lot LV) — LE MOTIF A DÛ ÊTRE RÉÉCRIT, et c'est le garde
    # « MOTIF INTROUVABLE » qui l'a exigé : la branche ILLISIBLE teste
    # désormais la TAILLE avant la date. Une mutation dont le motif ne
    # mord plus ne prouve rien ; elle doit rougir bruyamment, pas passer.

    ("⛔ une unité installée qui DIFFÈRE du dépôt passe pour identique",
     DEPLOY,
     "               else printf 'DIVERGENTE'; fi ;;",
     "               else printf 'IDENTIQUE'; fi ;;"),

    ("⛔ le marqueur `ne-pas-installer` éteint le contrôle même sur une "
     "unité VIVANTE — un marqueur oublié rendrait une unité intouchable",
     DEPLOY,
     '    [ "$etat" = "ABSENT" ] && { printf \'VOULUE\'; return 0; }',
     "    printf 'VOULUE'; return 0"),

    ("un état inconnu passe en silence au lieu de rougir",
     DEPLOY,
     "    *)         printf 'INCONNU' ;;",
     "    *)         printf 'IDENTIQUE' ;;"),

    # ── les cibles ──────────────────────────────────────────────────
    ("⛔⛔ LES SURCHARGES `.d/*.conf` SORTENT DES CIBLES — l'arbitrage OOM "
     "du 28/08 et le chien de garde S3 redeviennent invisibles, c'est-à-"
     "dire effaçables sans que rien ne le dise",
     DEPLOY,
     "        -o -path '*.service.d/*.conf' -o -path '*.timer.d/*.conf' \\\\)",
     "        \\\\)"),

    ("une surcharge vise son seul basename : `20-oom.conf` au lieu de "
     "`bw-model-score.service.d/20-oom.conf` — le contrôle chercherait "
     "au mauvais endroit et crierait MANQUANTE sur un fichier présent",
     DEPLOY,
     '        *.d/*.conf) printf \'%s|%s/%s\\n\' "$f" "$(basename "$(dirname "$f")")" "$(basename "$f")" ;;',
     '        *.d/*.conf) printf \'%s|%s\\n\' "$f" "$(basename "$f")" ;;'),

    # ── les permissions ─────────────────────────────────────────────
    ("⛔ `traces/` transporté sans `-p` : un `poller.sh` DÉJÀ présent sur "
     "le VPS en 644 y RESTE en 644 alors que le dépôt le porte en 755 — et "
     "`balise-infoclimat.service`, dont l'ExecStart pointe droit dessus, ne "
     "démarre plus. ⓘ Un fichier NEUF, lui, garde son +x même sans `-p` "
     "(rsync applique l'umask, pas 644) : c'est pour ça que le banc doit "
     "tester le cas EXISTANT, mesuré le 31/08 après une première version "
     "du banc qui restait verte sur cette mutation",
     DEPLOY,
     'bw_rsync_perms()      { rsync -av  "${BW_RSYNC_EXCLUDE[@]}" "$1/" "$2/"; }',
     'bw_rsync_perms()      { rsync -rtv "${BW_RSYNC_EXCLUDE[@]}" "$1/" "$2/"; }'),

    # ── le marqueur, posé là où il ne faut pas ───────────────────────
    ("⛔ UN MARQUEUR DE TROP : `bw-model-agrume-quart.timer` (installée, "
     "vivante, tirée pour de vrai le 31/08) est déclarée « ne-pas-"
     "installer » — un seul marqueur mal posé éteint le contrôle sur une "
     "unité de production",
     QUART_TIMER,
     '[Unit]\n',
     '[Unit]\n# bw-deploy: ne-pas-installer\n'),
]


def joue() -> int:
    rouges = 0
    for i, (nom, fichier, avant, apres) in enumerate(MUTATIONS, 1):
        origine = fichier.read_text(encoding="utf-8")
        if avant not in origine:
            print(f"  ⛔ {i:>2}. {nom}\n       MOTIF INTROUVABLE dans "
                  f"{fichier.name} — la mutation n'a rien muté, donc elle "
                  f"n'a rien prouvé. (Le code a bougé : réécrire ce motif.)")
            rouges += 1
            continue
        try:
            fichier.write_text(origine.replace(avant, apres, 1), encoding="utf-8")
            r = subprocess.run(BANC, capture_output=True, text=True, cwd=RACINE)
            if r.returncode == 0:
                print(f"  ❌ {i:>2}. {nom}\n       LE BANC RESTE VERT — il ne "
                      f"tient pas cette propriété.")
                rouges += 1
            else:
                lignes = [l.strip() for l in r.stdout.splitlines()
                          if l.strip().startswith("❌")]
                if not lignes:
                    lignes = [l.strip() for l in
                              (r.stdout + r.stderr).splitlines()[-3:] if l.strip()]
                print(f"  ✅ {i:>2}. {nom}\n       {lignes[0] if lignes else 'banc rouge'}"
                      + (f" (+{len(lignes) - 1} autres)" if len(lignes) > 1 else ""))
        finally:
            fichier.write_text(origine, encoding="utf-8")
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations du lot LD (le chemin de déploiement) — chaque ligne doit "
          "être VERTE,\n  c'est-à-dire : le banc a bien ROUGI sur la faute.\n")
    n = joue()
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
