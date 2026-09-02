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

# ⛔ (02/09/2026) copie d'origine sur le disque + sha256 + purge du
# bytecode, pour TOUS les harnais — voir `model-verif/harnais.py`.
sys.path.insert(0, str(ICI.parent / "model-verif"))
import harnais as HARNAIS  # noqa: E402
RACINE = ICI.parent
INV = ICI / "bw_inventaire_alertes.sh"
AVERTIR = ICI / "bw_avertir_config.sh"
DEPLOY = ICI / "deploy-agrume-vps.sh"
RUN = RACINE / "model-verif/run.sh"
EXEMPLE = RACINE / "traces/entretien/balise-watch-alertes.env.exemple"
#: L'exemple versionné de ~/.msmtprc (lot LE, 02/09/2026).
EXEMPLE_MSMTP = RACINE / "traces/entretien/msmtprc.exemple"
TAU = RACINE / "model-verif/systemd/bw-model-tau.service"
SCORE_TIMER = RACINE / "model-verif/systemd/bw-model-score.timer"
#: Le banc qui lance le VRAI `run.sh` dans un bac (lot du 02/09).
SELFTEST = RACINE / "model-verif/test_run_selftest.py"

ALERTES = ["bash", str(ICI / "test_alertes.sh")]
DEPLOIEMENT = ["bash", str(ICI / "test_deploiement.sh")]

MUTATIONS = [
    # ══ LES DEUX CENTRALES : RETIRER UNE VARIABLE LUE ════════════════
    ("⛔⛔ UNE VARIABLE LUE DISPARAÎT, ET SON NOM EST CONSTRUIT : le mode "
     "`agrume-quart` sort du `case` de run.sh. C'est LA mutation du lot — "
     "un banc qui grepperait des noms littéraux resterait vert en ratant "
     "onze variables sur dix-neuf (la sonde du 31/08 l'a fait)",
     ALERTES, RUN,
     # ⚠️ MOTIF RÉÉCRIT LE 01/09 (lot L12) : la ligne du `case`
     # s'est allongée d'un mode (`oracle`), et cette mutation a
     # cessé de mordre — le runner l'a dit lui-même (« MOTIF
     # INTROUVABLE : le code a bougé »). ⛔ On ne recopie donc PLUS
     # la ligne entière : on retire `|agrume-quart` là où il est,
     # ce qui survivra au douzième mode comme au treizième. Un
     # motif de mutation qui se périme à chaque mode ajouté est un
     # motif qui finira par dormir sans que personne ne le voie.
     "|agrume-quart|arome|tau|",
     "|arome|tau|"),

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
     # ⚠️ MOTIF RÉÉCRIT LE 02/09 : la condition a gagné le garde
     # `[ -z "$bw_ac_banc" ]` (un banc n'alerte pas la production) et
     # s'est coupée en deux lignes. Le runner l'a dit lui-même
     # (« MOTIF INTROUVABLE : le code a bougé »), et c'est exactement ce
     # que ce contrôle existe pour attraper — une mutation dont le motif
     # a vieilli ne prouve plus rien, mais elle reste VERTE si personne
     # ne vérifie qu'elle a mordu.
     '  if [ -n "${BW_ALERTE_MAIL:-}" ] && [ -z "$bw_ac_banc" ] \\\n'
     '     && command -v msmtp >/dev/null 2>&1; then',
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

    ("⛔⛔ LE DOSSIER D'ÉTAT REDEVIENT LE DÉFAUT (`$HOME`) : sous "
     "`ProtectHome=read-only`, le jeton ne s'écrit plus et le poller "
     "pousse une alerte TOUTES LES 5 MINUTES — 288 par jour. C'est la "
     "faute que la PRODUCTION a trouvée une heure après le déploiement "
     "du 01/09, et qu'aucun banc ne voyait",
     ALERTES, AVERTIR,
     '  bw_ac_dir="${5:-${BW_ETAT_ALERTES:-$HOME/.balise-watch-etat-alertes}}"',
     '  bw_ac_dir="${BW_ETAT_ALERTES:-$HOME/.balise-watch-etat-alertes}"'),

    ("⛔ LE POLLER NE PASSE PLUS SON DOSSIER D'ÉTAT : même effet, vu du "
     "côté de l'appelant. Le durcissement systemd d'une unité ne se lit "
     "pas dans le script qu'elle lance — c'est pour ça que l'argument "
     "doit être EXPLICITE, et bancé",
     ALERTES, RACINE / "traces/infoclimat/poller.sh",
     'bw_avertir_config BW_INFOCLIMAT_PING_URL "$ALERTES_FILE" balise-infoclimat "CE POLLER" "$ETAT"',
     'bw_avertir_config BW_INFOCLIMAT_PING_URL "$ALERTES_FILE" balise-infoclimat "CE POLLER"'),

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

    # ══════════════════════════════════════════════════════════════════
    #  UN BANC N'ALERTE PAS LA PRODUCTION (02/09/2026)
    #
    #  ⛔ La faute qu'on craint : un drapeau qui, au lieu d'isoler un
    #  banc, DÉSARME le dispositif — ou qui ne l'isole qu'à moitié.
    # ══════════════════════════════════════════════════════════════════
    ("⛔⛔ le drapeau de banc rend MUET au lieu de renommer : posé par "
     "erreur en production, il effacerait le dispositif entier",
     ALERTES, AVERTIR,
     '  bw_ac_banc="${BW_AVERTIR_CONFIG_BANC:-}"\n'
     '  if [ -n "$bw_ac_banc" ]; then\n'
     '    bw_ac_etiq="banc-$bw_ac_etiq"\n'
     '  fi',
     '  bw_ac_banc="${BW_AVERTIR_CONFIG_BANC:-}"\n'
     '  if [ -n "$bw_ac_banc" ]; then\n'
     '    return 0\n'
     '  fi'),

    ("⭐ le webhook part QUAND MEME depuis un banc — le telephone sonne "
     "pour un banc, et on apprend a ignorer le dispositif",
     ALERTES, AVERTIR,
     '  if [ -n "${BW_WEBHOOK_URL:-}" ] && [ -z "$bw_ac_banc" ]; then',
     '  if [ -n "${BW_WEBHOOK_URL:-}" ]; then'),

    ("l'e-mail part quand meme depuis un banc",
     ALERTES, AVERTIR,
     '  if [ -n "${BW_ALERTE_MAIL:-}" ] && [ -z "$bw_ac_banc" ] \\\n'
     '     && command -v msmtp >/dev/null 2>&1; then',
     '  if [ -n "${BW_ALERTE_MAIL:-}" ] && command -v msmtp >/dev/null 2>&1; then'),

    ("⭐⭐ l'etiquette journald reste celle de la PRODUCTION : le cri du "
     "banc redevient indiscernable, et `grep -c` rend un chiffre faux a "
     "54 % (mesure du 02/09 : 50 cris de banc sur 93)",
     ALERTES, AVERTIR,
     '    bw_ac_etiq="banc-$bw_ac_etiq"',
     '    bw_ac_etiq="$bw_ac_etiq"'),

    ("le corps ne dit plus que le cri vient d'un banc, ni lequel",
     ALERTES, AVERTIR,
     '⛔ ÉMIS PAR UN BANC ($bw_ac_banc) — ce n\'est PAS un job de production.',
     '(cri de banc)'),

    ("⛔ le drapeau s'applique meme quand il est VIDE : une variable "
     "definie a la chaine vide isolerait la production sans le dire",
     ALERTES, AVERTIR,
     '  if [ -n "$bw_ac_banc" ]; then\n'
     '    bw_ac_etiq="banc-$bw_ac_etiq"',
     '  if [ -z "$bw_ac_banc" ]; then\n'
     '    bw_ac_etiq="banc-$bw_ac_etiq"'),

    ("⭐ le banc qui a produit ce lot ne declare plus son bac : le "
     "correctif vit dans bw_avertir_config et personne ne l'appelle",
     ALERTES, SELFTEST,
     '        "BW_AVERTIR_CONFIG_BANC": "test_run_selftest.py",',
     '        "BW_AVERTIR_CONFIG_BANC_INACTIF": "test_run_selftest.py",'),

    # ══ LOT LE (02/09/2026) — LE CANAL E-MAIL ET SA TRACE ════════════
    # ⛔⛔ CE QUE CES MUTATIONS NE FONT PAS, ET IL FAUT LE LIRE. Le lot
    # LE prescrivait « rendre le chemin de log NON INSCRIPTIBLE et
    # exiger que le banc rougisse ». Mesuré le 02/09 contre un puits
    # SMTP local : un journal inécrivable N'EMPÊCHE PAS L'ENVOI (msmtp
    # livre d'abord, journalise ensuite, EXIT=0), et les trois
    # avertissements du 01/09 émis par une unité DURCIE sont ARRIVÉS.
    # La mutation prescrite n'aurait donc rien mordu — non par
    # faiblesse du banc, mais parce que la faute supposée n'était pas
    # la faute. Ce qui se défend ici est la TRACE, pas l'envoi.
    ("⛔⛔ `logfile` REVIENT DANS L'EXEMPLE : les treize unités durcies "
     "renvoient alors sans accusé de livraison, et on ne peut plus "
     "distinguer un e-mail arrivé d'un e-mail perdu",
     ALERTES, EXEMPLE_MSMTP,
     "syslog         on",
     "syslog         on\nlogfile        ~/.msmtp.log"),

    ("⛔ `syslog` DISPARAÎT DE L'EXEMPLE : plus aucune trace des envois, "
     "nulle part",
     ALERTES, EXEMPLE_MSMTP,
     "syslog         on",
     "# syslog       on"),

    ("⚠️ UNE VRAIE ADRESSE SE GLISSE DANS L'EXEMPLE VERSIONNÉ — même "
     "faute que l'UUID de check du lot LV, sur le fichier qui porte un "
     "mot de passe",
     ALERTES, EXEMPLE_MSMTP,
     "from           <expediteur@exemple.invalid>",
     "from           alertes@balise.watch"),

    ("⛔⛔ L'EXTRACTION REND LA LIGNE ENTIÈRE au lieu du premier mot : le "
     "mot de passe d'application de ~/.msmtprc remonte dans le terminal "
     "du déploiement ET dans ses journaux",
     ALERTES, INV,
     "  sed 's/#.*$//' \"$1\" | awk 'NF {print $1}' | sort -u",
     "  sed 's/#.*$//' \"$1\" | awk 'NF {print $0}' | sort -u"),

    ("⛔⛔ LE CONTRÔLE AVEUGLE REDIT « OUI » : la garde « aucune unité "
     "lue = non » saute, et le jour où la recherche d'unités casse, "
     "tout chemin devient couvert — piège nº 3 du lot LD",
     ALERTES, INV,
     '  [ "$n" -gt 0 ] || return 1\n  return 0',
     '  return 0'),

    ("⛔ LA COMPARAISON DE PRÉFIXE PERD SON `/` : "
     "/var/lib/bw-model-verif-bis passerait pour couvert par "
     "/var/lib/bw-model-verif",
     ALERTES, INV,
     '      case "$chemin" in "$p"|"$p"/*) ok=1 ;; esac',
     '      case "$chemin" in "$p"*) ok=1 ;; esac'),

    ("⛔⛔ TOUT CHEMIN DEVIENT COUVERT : la couverture ne regarde plus "
     "les ReadWritePaths du tout. C'est la faute d'origine du lot — une "
     "unité durcie dont le canal d'alerte écrit hors de ses chemins",
     ALERTES, INV,
     '      case "$chemin" in "$p"|"$p"/*) ok=1 ;; esac',
     '      ok=1'),

    ("⛔ LE PÉRIMÈTRE DES UNITÉS FOND À ZÉRO (une lettre dans `-name`) : "
     "un contrôle qui ne lit aucune unité ne doit pas passer pour vert",
     ALERTES, INV,
     "  find \"$racine\" -name '*.service' \\\n       -not -path '*/node_modules/*' -not -path '*/_to_delete/*' \\\n       -exec grep -l '^ProtectHome=read-only' {} + 2>/dev/null | sort",
     "  find \"$racine\" -name '*.sevice' \\\n       -not -path '*/node_modules/*' -not -path '*/_to_delete/*' \\\n       -exec grep -l '^ProtectHome=read-only' {} + 2>/dev/null | sort"),

    ("⛔ LE DÉPLOIEMENT N'APPELLE PLUS LE CONTRÔLE DU CANAL E-MAIL : il "
     "est défini et jamais appelé — la faute exacte du lot LV, où "
     "`alerter` était dans le fichier dix lignes plus haut",
     ALERTES, DEPLOY,
     "bw_controle_config_alertes\nbw_controle_config_msmtp\nbw_controle_swap",
     "bw_controle_config_alertes\nbw_controle_swap"),
]


def joue() -> int:
    rouges = 0
    for i, (nom, banc, fichier, avant, apres) in enumerate(MUTATIONS, 1):
        mode_mutation = isinstance(avant, tuple) and avant[0] == "MODE"
        if mode_mutation:
            origine_mode = fichier.stat().st_mode & 0o7777
            origine = None
            # ⛔⛔ GARDE AJOUTÉE LE 02/09/2026 (lot LE), APRÈS QUE CE
            # HARNAIS A CASSÉ LE DÉPÔT LUI-MÊME. Joué depuis une session
            # Cowork, `stat` traverse un MONTAGE qui rapporte 600 pour
            # tout : `origine_mode` valait donc 600, la mutation ne
            # mutait rien — et la RESTAURATION du `finally` écrivait 600
            # sur le vrai fichier du Mac. `model-verif/bw-model-score.timer`
            # est resté en 600, et git ne suit pas ce bit : rien ne
            # l'aurait dit. *Un harnais qui lit un montage écrit le
            # verdict du montage dans le dépôt.*
            # ⇒ Une mutation de MODE dont l'origine EST DÉJÀ le mode muté
            #   ne prouve rien et ne doit RIEN toucher.
            if origine_mode == avant[1]:
                print(f"  ⛔ {i:>2}. {nom}\n       MODE DÉJÀ CELUI DE LA "
                      f"MUTATION ({oct(origine_mode)}) — rien à muter, et la "
                      f"restauration écrirait ce mode dans le dépôt. "
                      f"(Session Cowork ? ce harnais se joue sur un VRAI "
                      f"système de fichiers, pas à travers un montage.)")
                rouges += 1
                continue
        else:
            origine = HARNAIS.garder(fichier)
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
            r = subprocess.run(banc, capture_output=True, text=True, cwd=RACINE,
                               env=HARNAIS.env_banc(RACINE))
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
                HARNAIS.rendre(fichier, origine)
    return rouges


if __name__ == "__main__":
    print("\n▶ mutations du lot LV (les canaux d'alerte) — chaque ligne doit être "
          "VERTE,\n  c'est-à-dire : le banc a bien ROUGI sur la faute.\n")
    n = joue()
    print(f"\n{'✅ toutes les mutations sont vues.' if n == 0 else f'❌ {n} mutation(s) NON vue(s) — banc à renforcer.'}\n")
    sys.exit(1 if n else 0)
