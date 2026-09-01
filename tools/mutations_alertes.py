#!/usr/bin/env python3
"""Rejoue les bancs des CANAUX D'ALERTE contre des variantes cassées
(lot LV, 01/09/2026).

⛔ POURQUOI CE FICHIER EXISTE, EN UNE PHRASE. Cinq runners portaient
déjà le garde-fou « PERSONNE NE SURVEILLE », il a crié 315 fois en
29 jours — dont VINGT JOURS D'AFFILÉE pour la confrontation — et rien
n'a jamais rougi : ni un banc, ni le déploiement, ni personne. *Un banc
écrit après coup ne vaut rien tant qu'on n'a pas vu la faute d'origine
le faire rougir.*

⭐ LA MUTATION CENTRALE EST LA nº 1 : retirer une variable LUE par un
runner dont le nom est CONSTRUIT. Onze des dix-neuf variables ne se
grepent pas — `model-verif/run.sh` les fabrique à partir du mode. Un
banc qui chercherait des noms littéraux resterait vert en ratant onze
variables sur dix-neuf, ce qui est exactement ce qui est arrivé à la
sonde du 31/08.

⚠️ Harnais : même forme que `tools/mutations_deploiement.py`
(restauration en `finally`, contrôle d'intégrité du motif `avant`), avec
deux ajouts que ce lot rendait nécessaires :
  · chaque mutation nomme SON banc — certaines propriétés vivent dans
    `test_alertes.sh`, d'autres dans `test_deploiement.sh` ;
  · une mutation peut être un CHANGEMENT DE MODE et pas de texte
    (`("MODE", 0o600)`) : la faute Q4 du lot est une permission, pas une
    ligne, et une mutation qui ne sait muter que du texte ne l'aurait
    jamais vue.
⚠️ Vérifier qu'aucune campagne PARALLÈLE ne tourne (piège nº 7 du 28/08).

    python3 tools/mutations_alertes.py
"""
import pathlib
import subprocess
import sys

ICI = pathlib.Path(__file__).resolve().parent
RACINE = ICI.parent
INV = ICI / "bw_inventaire_alertes.sh"
AVERTIR = ICI / "bw_avertir_config.sh"
DEPLOY = ICI / "deploy-agrume-vps.sh"
RUN = RACINE / "model-verif/run.sh"
EXEMPLE = RACINE / "traces/entretien/balise-watch-alertes.env.exemple"
TAU = RACINE / "model-verif/systemd/bw-model-tau.service"
SCORE_TIMER = RACINE / "model-verif/systemd/bw-model-score.timer"

ALERTES = ["bash", str(ICI / "test_alertes.sh")]
DEPLOIEMENT = ["bash", str(ICI / "test_deploiement.sh")]

MUTATIONS = [
    # ══ LES DEUX CENTRALES : RETIRER UNE VARIABLE LUE ════════════════
    ("⛔⛔ UNE VARIABLE LUE DISPARAÎT, ET SON NOM EST CONSTRUIT : le mode "
     "`agrume-quart` sort du `case` de run.sh. C'est LA mutation du lot — "
     "un banc qui grepperait des noms littéraux resterait vert en ratant "
     "onze variables sur dix-neuf (la sonde du 31/08 l'a fait)",
     ALERTES, RUN,
     "collect|collect-p2|collect-reduit|score|garde-fou-r2|agrume|agrume-court|agrume-quart|arome|tau|filet-arome) ;;",
     "collect|collect-p2|collect-reduit|score|garde-fou-r2|agrume|agrume-court|arome|tau|filet-arome) ;;"),

    ("⛔⛔ UNE VARIABLE LUE LITTÉRALEMENT DISPARAÎT : la confrontation lit "
     "un autre nom que celui qu'elle annonce — c'est le défaut EXACT du "
     "03/08 sur le poller (`BW_PING_FAIL_URL`, `BW_MAIL_TO`), qui a rendu "
     "l'alerting muet pendant 28 jours",
     ALERTES, RACINE / "verif/run-confronter-quotidien.sh",
     'PING="${BW_AGRUME_CONFRONTATION_PING_URL:-}"',
     'PING="${BW_CONFRONTATION_URL:-}"'),

    # ══ L'INVENTAIRE ══════════════════════════════════════════════════
    ("⛔ L'INVENTAIRE REDEVIENT LITTÉRAL : les noms construits ne sont plus "
     "reconstitués. C'est la cécité du 31/08, remise telle quelle",
     ALERTES, INV,
     "  { bw_inv_litterales \"$racine\"; bw_inv_construites \"$racine\"; } | sort -u",
     "  bw_inv_litterales \"$racine\" | sort -u"),

    ("⛔ LA TRANSLITTÉRATION PERD LES TIRETS : `garde-fou-r2` rendrait "
     "`BW_MODEL_GARDE-FOU-R2_PING_URL`, qui n'est pas un nom de variable "
     "shell valide — l'expansion rendrait vide et le job aurait "
     "exactement l'allure d'un job surveillé (défaut du 10/08)",
     ALERTES, INV,
     "\"$(printf '%s' \"$m\" | tr '[:lower:]-' '[:upper:]_')\"",
     "\"$(printf '%s' \"$m\" | tr '[:lower:]' '[:upper:]')\""),

    ("⛔ LES COMMENTAIRES REDEVIENNENT DU CODE : `BW_PING_FAIL_URL` et "
     "`BW_MAIL_TO`, cités dans le pavé du 03/08 qui explique qu'ils "
     "N'EXISTENT PAS, entreraient dans l'inventaire — deux faux trous "
     "permanents, donc deux raisons d'ignorer le contrôle",
     ALERTES, INV,
     "    sed 's/^[[:space:]]*#.*$//' \"$racine/$f\" \\",
     "    cat \"$racine/$f\" \\"),

    ("⛔ UN RUNNER SORT DE LA LISTE : la confrontation n'est plus inventoriée. "
     "C'est le trou par lequel une variable s'échapperait à la fois du banc "
     "ET du déploiement — invisible des deux côtés à la fois",
     ALERTES, INV,
     "verif/run-confronter-quotidien.sh",
     "verif/run-confronter-quotidien-ABSENT.sh"),

    ("⛔ LE MARQUEUR « ne-pas-installer » DISPARAÎT de bw-model-tau.service : "
     "le contrôle compterait `BW_MODEL_TAU_PING_URL` comme un TROU alors "
     "que le job n'existe pas — un contrôle qui crie au loup finit ignoré "
     "(piège nº 4 du lot LD)",
     ALERTES, TAU,
     "# bw-deploy: ne-pas-installer",
     "# bw-deploy: (marqueur retire par la mutation)"),

    # ══ L'EXEMPLE VERSIONNÉ ═══════════════════════════════════════════
    ("⛔ L'EXEMPLE REPERD UNE VARIABLE : `BW_AGRUME_CONFRONTATION_PING_URL` "
     "n'y est plus annoncée. C'est l'état d'avant ce lot — 4 noms annoncés "
     "pour 19 lus — et c'est ce qui a laissé la confrontation naître muette",
     ALERTES, EXEMPLE,
     "# export BW_AGRUME_CONFRONTATION_PING_URL=",
     "# (retiree par la mutation) BW_AGRUME_CONFRONTATION_PING_URL_ABSENTE="),

    ("⛔ LA DOCTRINE PÉRIMÉE REVIENT : « une variable absente = canal ignoré "
     "en silence ». Elle était vraie le 03/08 et fausse depuis ; une "
     "doctrine écrite qui ne décrit plus le code ferme un dossier pour un "
     "mois (piège du 24/08)",
     ALERTES, EXEMPLE,
     "# ⇒ LA RÈGLE D'AUJOURD'HUI :",
     "# Une variable absente = canal ignoré en silence.\n# ⇒ LA RÈGLE D'AUJOURD'HUI :"),

    ("⚠️ UNE VALEUR RÉELLE SE GLISSE DANS L'EXEMPLE VERSIONNÉ — un UUID de "
     "check dans un fichier suivi par git",
     ALERTES, EXEMPLE,
     '# export BW_PING_OK_URL="https://hc-ping.com/xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"',
     '# export BW_PING_OK_URL="https://hc-ping.com/3f77fdd9-1c2b-4a5e-9f01-2b3c4d5e6f70"'),

    # ══ LE CHIEN DE GARDE ═════════════════════════════════════════════
    ("⛔⛔ LE JETON DEVIENT PERMANENT : un job qui crie tous les jours "
     "n'envoie plus qu'UN SEUL message, le premier. C'EST LE CAS QUI A "
     "PRODUIT LE LOT — la confrontation a crié 20 jours et personne n'a "
     "rien reçu",
     ALERTES, AVERTIR,
     '     && [ "$(cat "$bw_ac_jeton" 2>/dev/null)" = "$bw_ac_jour" ]; then',
     '     ; then'),

    ("⛔⛔ LE DISPOSITIF ÉCHOUE FERMÉ : le jeton s'écrit AVANT l'envoi, donc "
     "un état d'alerte cassé rend le dispositif MUET. Un dispositif "
     "d'alerte ne doit pas dépendre de ce qu'il surveille — ni de "
     "lui-même",
     ALERTES, AVERTIR,
     "  # ── 1. journald, en ERREUR — pas en info ────────────────────────────",
     "  mkdir -p \"$bw_ac_dir\" 2>/dev/null || return 0\n"
     "  printf '%s\\n' \"$bw_ac_jour\" > \"$bw_ac_jeton\" 2>/dev/null || true\n"
     "  # ── 1. journald, en ERREUR — pas en info ────────────────────────────"),

    ("⛔ LE CANAL E-MAIL DISPARAÎT : l'avertissement retombe dans le journal, "
     "que RIEN ne lit sur cette machine (0 logcheck, 0 crontab, OnFailure= "
     "sur 0 des 31 unités, mesuré le 01/09)",
     ALERTES, AVERTIR,
     '  if [ -n "${BW_ALERTE_MAIL:-}" ] && command -v msmtp >/dev/null 2>&1; then',
     '  if false; then'),

    ("⛔ L'AVERTISSEMENT PINGUE LE CHECK D'UN AUTRE JOB : le check "
     "« entretien packs » passerait au rouge pour la faute du poller — la "
     "règle « deux jobs, deux checks » de balise-infoclimat.service",
     ALERTES, AVERTIR,
     "  # ── 3. E-mail via msmtp ─────────────────────────────────────────────",
     "  curl -fsS -m 5 \"https://hc-ping.com/partage/fail\" >/dev/null 2>&1 || true\n"
     "  # ── 3. E-mail via msmtp ─────────────────────────────────────────────"),

    ("⛔ LE NOM DE LA VARIABLE SORT DU MESSAGE : on reçoit « configuration "
     "incomplète » sans savoir LAQUELLE — un avertissement qu'on ne peut "
     "pas suivre est un avertissement qu'on classe",
     ALERTES, AVERTIR,
     '  bw_ac_sujet="configuration incomplete : $bw_ac_var absente"',
     '  bw_ac_sujet="configuration incomplete"'),

    # ══ LE VERDICT TAILLE (réponse Q4) ════════════════════════════════
    ("⛔⛔ UN FICHIER ILLISIBLE DE MÊME TAILLE EST DÉCLARÉ IDENTIQUE : la "
     "réserve du lot L8 s'effondre — « ce qu'on ne peut pas lire n'est pas "
     "vert, il est INCONNU ». La taille allège la réserve, elle ne la lève "
     "jamais",
     DEPLOIEMENT, DEPLOY,
     "    ILLISIBLE) if [ -n \"$taille\" ] && [ \"$taille\" = \"$(bw_taille \"$depot\")\" ]; then\n"
     "                 printf 'NON_VERIFIABLE_TAILLE_OK'",
     "    ILLISIBLE) if [ -n \"$taille\" ] && [ \"$taille\" = \"$(bw_taille \"$depot\")\" ]; then\n"
     "                 printf 'IDENTIQUE'"),

    ("⛔ UN ÉCART DE TAILLE SUR UN FICHIER ILLISIBLE PASSE POUR CONFORME — "
     "c'est le cas `balise-entretien.service` (3 542 o installés contre "
     "4 084 dans le dépôt), qui redeviendrait invisible",
     DEPLOIEMENT, DEPLOY,
     "               elif [ -n \"$taille\" ]; then\n"
     "                 printf 'NON_VERIFIABLE_ECART'",
     "               elif [ -n \"$taille\" ]; then\n"
     "                 printf 'NON_VERIFIABLE_TAILLE_OK'"),

    # ══ LE MODE DES UNITÉS (réponse Q4) — UNE MUTATION DE PERMISSION ══
    ("⛔⛔ UNE UNITÉ DU DÉPÔT REPASSE EN 600 : installée depuis cette "
     "source, elle deviendrait illisible sans sudo et sortirait "
     "DÉFINITIVEMENT du contrôle « dépôt ↔ /etc ». C'est ainsi que cinq "
     "unités y sont déjà — le mode n'est pas choisi, il est hérité de la "
     "source par `cp`",
     ALERTES, SCORE_TIMER, ("MODE", 0o600), None),
]


def joue() -> int:
    rouges = 0
    for i, (nom, banc, fichier, avant, apres) in enumerate(MUTATIONS, 1):
        mode_mutation = isinstance(avant, tuple) and avant[0] == "MODE"
        if mode_mutation:
            origine_mode = fichier.stat().st_mode & 0o7777
            origine = None
        else:
            origine = fichier.read_text(encoding="utf-8")
            if avant not in origine:
                print(f"  ⛔ {i:>2}. {nom}\n       MOTIF INTROUVABLE dans "
                      f"{fichier.name} — la mutation n'a rien muté, donc elle "
                      f"n'a rien prouvé. (Le code a bougé : réécrire ce motif.)")
                rouges += 1
                continue
        try:
            if mode_mutation:
                fichier.chmod(avant[1])
            else:
                fichier.write_text(origine.replace(avant, apres, 1), encoding="utf-8")
            r = subprocess.run(banc, capture_output=True, text=True, cwd=RACINE)
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
            if mode_mutation:
                fichier.chmod(origine_mode)
            else:
                fichier.write_text(origine, encoding="utf-8")
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations du lot LV (les canaux d'alerte) — chaque ligne doit être "
          "VERTE,\n  c'est-à-dire : le banc a bien ROUGI sur la faute.\n")
    n = joue()
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
