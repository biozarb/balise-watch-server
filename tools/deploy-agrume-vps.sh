#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  tools/deploy-agrume-vps.sh — la procédure manuelle du 13/08,
#                                figée en une commande         (13/08/2026)
#
#  Lot P. Jusqu'ici : rsync à la main, sha256 des deux côtés à la main,
#  bancs relancés à la main sur le VPS, `systemctl restart` à la main —
#  quatre étapes, quatre occasions d'en sauter une. « Le rsync à la main
#  a déjà laissé le VPS figé 2 lots » (§9 de la note de priorités du
#  13/08). Ce script ne fait rien de nouveau : il ENCHAÎNE ce qui était
#  déjà tapé, dans le même ordre, et s'ARRÊTE au premier échec — jamais
#  de restart sur un code dont les bancs n'ont pas confirmé qu'il tient.
#
#  ⚠️ APPELÉ DEPUIS LE MAC, PAS DEPUIS LE CONTAINER CLOUD. `ssh`/`rsync`
#  vers le VPS passent par Desktop Commander sur ce poste — jamais par
#  `device_bash` (cf. la roadmap AGRUME, plomberie §0). Lancer ce script
#  suppose donc une session avec le dépôt du Mac déjà en main.
#
#  Usage :  ./tools/deploy-agrume-vps.sh              # depuis la racine du dépôt serveur
#           ./tools/deploy-agrume-vps.sh --sans-bancs # rsync + sha256 seulement (déboguer)
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

VPS="${BW_VPS_HOST:-debian@51.91.102.146}"
DISTANT="${BW_VPS_CODE:-~/balise-watch/balise-watch-server}"
ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SANS_BANCS=0
[ "${1:-}" = "--sans-bancs" ] && SANS_BANCS=1
# ⓘ 31/08 (lot LD) — `--controle-unites` joue le §2 bis SEUL, en lecture
# pure : ni rsync, ni bancs, ni restart, ni sudo. C'est la commande à
# taper quand on veut juste savoir ce qui est réellement installé sur la
# machine, et elle sert aussi de répétition avant un vrai déploiement.
CONTROLE_SEUL=0
[ "${1:-}" = "--controle-unites" ] && CONTROLE_SEUL=1

cd "$ICI" || { echo "❌ dépôt introuvable : $ICI" >&2; exit 1; }

dire()  { printf '\n▶ %s\n' "$*"; }
# ⓘ L'inventaire des variables de canal (lot LV, 01/09) — DÉRIVÉ DU CODE,
# et partagé avec le banc `tools/test_alertes.sh`. Deux énumérations
# séparées divergeraient, et celle du contrôle serait toujours la plus
# vieille : c'est la faute du lot LD, transposée aux alertes.
# shellcheck source=/dev/null
. "$ICI/tools/bw_inventaire_alertes.sh"
echec() { printf '\n❌ %s\n' "$*" >&2; exit 1; }

# ══════════════════════════════════════════════════════════════════════
# 0. LE PÉRIMÈTRE ET LES EXCLUSIONS — ÉCRITS UNE SEULE FOIS, ICI.
#
#  ⛔⛔ LOT LD, 31/08/2026 — LA FAUTE QUE CE BLOC EXISTE POUR EMPÊCHER.
#  Jusqu'à ce jour, le TRANSPORT (§1) et le CONTRÔLE (§2) avaient chacun
#  LEUR filtre, et celui du contrôle était le plus étroit des deux :
#  `*.py` et `*.sh`. Un vérificateur qui hérite de l'angle mort de ce
#  qu'il vérifie ne peut pas, PAR CONSTRUCTION, attraper la faute qu'il
#  existe pour attraper. Mesuré ce jour-là en lecture seule, avant de
#  toucher à quoi que ce soit : le §2 rendait « ✅ identique des deux
#  côtés » sur 162 fichiers pendant que DIX fichiers manquaient sur le
#  VPS — six unités systemd (lots L8, L10, L11), trois fichiers de
#  `model-verif/latence/`, et `traces/sonde_rafale_infoclimat.py` — et
#  que CINQ fichiers de code de `traces/` avaient un mois de retard,
#  dont celui qui a rendu l'alerting du poller Infoclimat MUET pendant
#  28 jours (voir le §4 du rapport de sonde).
#
#  ⇒ IL N'Y A PLUS QU'UNE SEULE LISTE, ET LES DEUX LA LISENT. Le §1
#  construit ses `--exclude` avec, le §2 construit ses prédicats `find`
#  avec. Si l'un se met à ignorer un fichier, l'AUTRE LE VOIT — c'est
#  toute la propriété qu'on achète ici, et elle se perd à la seconde où
#  quelqu'un recopie un filtre au lieu de lire celui-ci.
#
#  ⚠️ `traces/` ENTRE DANS LE PÉRIMÈTRE (décision de Yann, 31/08). Il
#  n'était déployé par RIEN — ni par ce script, ni par un cron (il n'y
#  en a pas sur le VPS), ni par un checkout (git n'est même pas installé
#  là-bas). Sa copie distante datait du 03/08.
# ══════════════════════════════════════════════════════════════════════
BW_DOSSIERS=(agrume verif tools model-verif traces)

# ⚠️ QUI EST TRANSPORTÉ COMMENT — déclaré ICI, pas en dur dans le §1, pour
# que le banc puisse vérifier LA propriété qui compte : *tout ce qui est
# CONTRÔLÉ est TRANSPORTÉ, et réciproquement.* Le 31/08, `traces/` était
# dans aucune des deux listes ; le 26/08, `model-verif/` était contrôlé
# sans être transporté. Deux fois la même faute, deux listes qui ne se
# regardaient pas.
BW_TRANSPORT_PERMS=(agrume verif tools traces)   # rsync -av
BW_TRANSPORT_SANS_PERMS=(model-verif)            # rsync -rtv

# ⛔ CHAQUE EXCLUSION PORTE SON MOTIF. Une exclusion sans raison écrite
# est un futur trou de six fichiers — c'est littéralement comme ça que
# celui-ci est né (le `--exclude '*'` de la ligne 72, sans un mot).
BW_EXCLUS=(
  '__pycache__'          # caches Python, régénérés des deux côtés
  '*.pyc'                # idem
  '_to_delete'           # convention du projet : mis de côté, ne compte plus
                         # (26/08, sur un sonde_budget.py orphelin du 09/08)
  '.DS_Store'            # macOS. ⓘ Il y en a DÉJÀ un dans agrume/ sur le VPS,
                         # transporté avant que cette ligne existe.
  '*.bak'                # points de retour locaux
  '*.bak-*'              # ⚠️ `*.bak` NE SUFFIT PAS, et c'est mesuré : le VPS
                         # porte `score.py.bak-pre-lotG` et
                         # `test_score.py.bak-pre-lotG`, que `*.bak` ne couvre
                         # pas, que rsync (sans --delete) n'enlèvera jamais, et
                         # qui feraient rougir le §2 à CHAQUE déploiement. Un
                         # contrôle qui rougit pour rien finit désarmé.
  '*.npz.tmp'            # écriture atomique en cours
  'traces_cache'         # ⛔ ÉTAT D'EXÉCUTION, PAS DU CODE. `backfill_packs.log`
                         # et `packs_checkpoint.json` sont réécrits par la
                         # production (mesuré le 31/08 : mtime du JOUR côté VPS,
                         # là où tout le reste porte des mtime venus du Mac).
                         # Les transporter écraserait l'état de la machine ; les
                         # contrôler ferait rougir toutes les nuits.
)

# ⛔⛔ AUCUN MOTIF NE CONTIENT DE `/`, ET CE N'EST PAS UNE COQUETTERIE.
# Écrit `traces/traces_cache`, le motif est INERTE côté rsync et ACTIF
# côté find — parce que la racine de rsync est le dossier qu'on lui
# passe (`traces/`), pas la racine du dépôt. Trouvé par le banc, pas par
# la relecture : `bw_rsync_perms traces …` transportait tout le cache.
# ⇒ Un motif est un NOM, écarté à n'importe quelle profondeur, et les
# deux filtres en font la même chose. Le garde ci-dessous refuse tout
# retour en arrière, plutôt que de le laisser passer en silence — ce
# lot entier est né d'un filtre silencieux.
for _m in "${BW_EXCLUS[@]}"; do
  case "$_m" in */*)
    echo "❌ BW_EXCLUS : « $_m » contient un '/'. Un motif doit être un NOM :" >&2
    echo "   la racine de rsync (le dossier transféré) n'est pas celle de find" >&2
    echo "   (la racine du dépôt) — un motif à chemin n'agirait que d'un côté." >&2
    exit 1 ;;
  esac
done
unset _m

# Les `--exclude` du transport, construits DEPUIS la liste ci-dessus.
BW_RSYNC_EXCLUDE=()
for _e in "${BW_EXCLUS[@]}"; do BW_RSYNC_EXCLUDE+=(--exclude "$_e"); done
unset _e

# Les prédicats `find` du contrôle, construits DEPUIS LA MÊME LISTE.
# ⚠️ Tous les motifs sont des NOMS (le garde ci-dessus l'impose), écartés
# où qu'ils se trouvent dans l'arborescence — exactement comme rsync les
# traite. C'est ce qui garantit que les deux filtres écartent le MÊME
# ensemble, et c'est toute la propriété que le §0 achète.
bw_find_filtre() {
  local m out=''
  for m in "${BW_EXCLUS[@]}"; do
    # ⚠️ DEUX prédicats par motif, et il faut les deux : `-name` écarte le
    # fichier (ou le dossier) lui-même, `-path '*/m/*'` écarte ce qu'il
    # CONTIENT. `-name '__pycache__'` seul laisserait passer les `.pyc`
    # qui sont dedans.
    out+=" ! -name '$m' ! -path '*/$m/*'"
  done
  printf '%s' "$out"
}

# La commande `find` du manifeste — LA MÊME CHAÎNE est jouée ici et sur
# le VPS. C'est volontaire : deux `find` écrits séparément, c'est deux
# filtres qui divergent, c'est-à-dire le bug de ce lot une couche plus
# haut.
bw_trouve() { printf "find %s -type f%s -print0" "${BW_DOSSIERS[*]}" "$(bw_find_filtre)"; }

# ⚠️ DEUX RSYNC, ET LA DIFFÉRENCE EST MESURÉE, PAS ESTHÉTIQUE.
#  · `bw_rsync_perms` (-av) pour agrume/, verif/, tools/ et traces/ : les
#    permissions du Mac et celles du VPS y sont IDENTIQUES fichier par
#    fichier (relevé le 31/08, y compris les 600 d'agrume/ et verif/ et
#    les `-rwx--x--x` de traces/entretien/entretien.sh et
#    traces/infoclimat/poller.sh) — `-p` ne change donc rien, et il garde
#    le bit +x dont dépend l'ExecStart du poller Infoclimat.
#  · `bw_rsync_sans_perms` (-rtv) pour model-verif/ SEULEMENT : là, les
#    permissions DIVERGENT pour de vrai (`score.py` est 644 sur le Mac et
#    600 sur le VPS, mesuré). `-a` embarque `-p` et écraserait le 600.
bw_rsync_perms()      { rsync -av  "${BW_RSYNC_EXCLUDE[@]}" "$1/" "$2/"; }
bw_rsync_sans_perms() { rsync -rtv "${BW_RSYNC_EXCLUDE[@]}" "$1/" "$2/"; }
# ⛔⛔ CE QUI N'EST PLUS ÉCRIT SUR LA LIGNE CI-DESSUS, ET POURQUOI.
# Jusqu'au 31/08 elle portait, en plus :
#     --include '*/' --include '*.py' --include '*.sh' --exclude '*'
# Un `.service`, un `.timer`, un `.conf`, un `.md`, un `.json` NE PARTAIT
# JAMAIS, en silence, pendant que le script annonçait « tout est vert ».
# ⇒ Le banc `tools/test_deploiement.sh` remet ce filtre et EXIGE qu'un
# `.timer` n'arrive pas : c'est la mutation centrale du lot. Si vous
# rétablissez ce filtre, le banc doit ROUGIR. S'il reste vert, c'est le
# banc qu'il faut réparer, pas le filtre qu'il faut croire.

# Les cibles du contrôle « dépôt ↔ /etc » (§2 bis) : toute unité du dépôt
# et toute surcharge `.d/*.conf`, avec le nom qu'elle porte dans
# /etc/systemd/system.
#   sortie : <chemin dans le dépôt>|<chemin sous /etc/systemd/system>
bw_cibles_etc() {
  eval "find ${BW_DOSSIERS[*]} -type f \\( -name '*.service' -o -name '*.timer' \\
        -o -path '*.service.d/*.conf' -o -path '*.timer.d/*.conf' \\)$(bw_find_filtre)" \
  | sort | while IFS= read -r f; do
      case "$f" in
        *.d/*.conf) printf '%s|%s/%s\n' "$f" "$(basename "$(dirname "$f")")" "$(basename "$f")" ;;
        *)          printf '%s|%s\n'    "$f" "$(basename "$f")" ;;
      esac
    done
}

# ⚠️ TROIS OUTILS PORTABLES — macOS (BSD) et Debian (GNU) ne les écrivent
# PAS pareil, et ce script tourne des deux côtés (le banc du lot LD est
# rejoué sur le VPS au §3). Une seule définition, choisie une fois.
if command -v shasum >/dev/null 2>&1; then
  bw_sha()   { shasum -a 256 "$1" | cut -d' ' -f1; }
else
  bw_sha()   { sha256sum "$1" | cut -d' ' -f1; }
fi
if stat -f '%m' . >/dev/null 2>&1; then
  bw_mtime() { stat -f '%m' "$1"; }          # BSD / macOS
else
  bw_mtime() { stat -c '%Y' "$1"; }          # GNU / Debian
fi
# ⚠️ La TAILLE se lit sans DROIT DE LECTURE sur le fichier (les
# métadonnées suffisent) — c'est ce qui permet, depuis le lot LV, de
# dire quelque chose des unités en 0600 root sans jamais appeler sudo.
# ⛔ `wc -c < f` ne marcherait PAS : la redirection, elle, exige le droit
# de lecture. C'est `stat` qu'il faut, et il ne s'écrit pas pareil des
# deux côtés.
if stat -f '%z' . >/dev/null 2>&1; then
  bw_taille() { stat -f '%z' "$1" 2>/dev/null; }   # BSD / macOS
else
  bw_taille() { stat -c '%s' "$1" 2>/dev/null; }   # GNU / Debian
fi
if stat -f '%Lp' . >/dev/null 2>&1; then
  bw_mode()  { stat -f '%Lp' "$1" 2>/dev/null; }   # BSD / macOS
else
  bw_mode()  { stat -c '%a'  "$1" 2>/dev/null; }   # GNU / Debian
fi
if date -u -r 0 '+%Y' >/dev/null 2>&1; then
  bw_date()  { date -u -r "$1" '+%d/%m/%Y %H:%M'; }   # BSD : -r prend une époque
else
  bw_date()  { date -u -d "@$1" '+%d/%m/%Y %H:%M'; }  # GNU : -r prend un FICHIER
fi

# ⚠️ LE VERDICT D'UNE CIBLE, ISOLÉ DANS UNE FONCTION — ET C'EST DÉLIBÉRÉ.
# Toute la logique du §2 bis tient ici, sans `ssh` : le banc peut donc la
# jouer sur des fichiers jetables, y compris les cas qu'on ne sait pas
# fabriquer sur le VPS (une unité NEUVE, un 0600 qu'on n'a pas le droit
# de créer). Si cette logique restait en ligne dans le §2 bis, le banc
# devrait la RECOPIER — et une copie qui diverge de l'original est
# exactement la faute que ce lot répare.
#   $1 chemin dans le dépôt · $2 ABSENT|ILLISIBLE|LU
#   $3 mtime dans /etc (époque, vide si ABSENT) · $4 sha256 dans /etc
#   $5 TAILLE dans /etc (lot LV, 01/09) — vide si non relevée.
bw_verdict_unite() {
  local depot="$1" etat="$2" mt="$3" sha="$4" taille="${5:-}" marque=0
  head -30 "$depot" | grep -q '^# bw-deploy: ne-pas-installer' && marque=1
  if [ "$marque" = 1 ]; then
    # ⛔ LE MARQUEUR NE VAUT QUE POUR UNE ABSENCE. S'il est posé sur une
    # unité qui EST installée, c'est qu'on l'a installée sans retirer la
    # ligne — le marqueur ment, et un marqueur qui ment est pire que pas
    # de marqueur : il éteint le contrôle sur une unité vivante.
    [ "$etat" = "ABSENT" ] && { printf 'VOULUE'; return 0; }
    printf 'MARQUEUR_PERIME'; return 0
  fi
  case "$etat" in
    ABSENT)    printf 'MANQUANTE' ;;
    # ⭐⭐ LOT LV, 01/09 — CE QU'ON PEUT DIRE D'UN FICHIER QU'ON N'A PAS
    # LE DROIT DE LIRE. La taille, elle, se lit sans sudo. Ce n'est pas
    # l'égalité des octets, et ce fichier ne prétend pas le contraire :
    # un `NON_VERIFIABLE_TAILLE_OK` reste compté dans la RÉSERVE, jamais
    # dans les verts (règle du lot L8 : ce qu'on ne peut pas lire n'est
    # pas vert, il est inconnu). Mais une taille ÉGALE à celle du dépôt
    # transforme « je ne sais rien » en « très probablement conforme »,
    # et une taille DIFFÉRENTE nomme un écart réel que la seule date ne
    # prouvait pas.
    # ⓘ Mesuré le 01/09 sur les cinq unités en 0600 du VPS : quatre
    # collent au dépôt à l'octet près ; la cinquième,
    # `balise-entretien.service`, fait 3 542 o contre 4 084 dans le
    # dépôt — et 3 542 est EXACTEMENT la taille du blob git au commit
    # 7c49711 (09/08 10:49:43), installé 3 min 14 s plus tard. Le seul
    # commit depuis ne touche que des lignes de commentaire.
    ILLISIBLE) if [ -n "$taille" ] && [ "$taille" = "$(bw_taille "$depot")" ]; then
                 printf 'NON_VERIFIABLE_TAILLE_OK'
               elif [ -n "$taille" ]; then
                 printf 'NON_VERIFIABLE_ECART'
               elif [ -n "$mt" ] && [ "$mt" -lt "$(bw_mtime "$depot")" ] 2>/dev/null; then
                 printf 'NON_VERIFIABLE_ANCIENNE'
               else printf 'NON_VERIFIABLE'; fi ;;
    LU)        if [ "$sha" = "$(bw_sha "$depot")" ]; then printf 'IDENTIQUE'
               else printf 'DIVERGENTE'; fi ;;
    *)         printf 'INCONNU' ;;
  esac
}

# ══════════════════════════════════════════════════════════════════════
#  §2 TER — LES CANAUX D'ALERTE : CE QUE LE CODE LIT ↔ CE QUE LA MACHINE
#  DÉFINIT.                                        (lot LV, 01/09/2026)
#
#  ⛔⛔ POURQUOI. Le 01/09, sur les 29 jours de journal du VPS :
#  `BW_AGRUME_CONFRONTATION_PING_URL` avait crié « PERSONNE NE SURVEILLE
#  CETTE CHAÎNE » VINGT JOURS D'AFFILÉE, dès la première passe de son
#  unité, sans que rien ne remonte. Plusieurs déploiements ont eu lieu
#  pendant ces vingt jours, tous verts : le déploiement ne regardait pas
#  la configuration, seulement le code.
#
#  ⚠️ IL NE LIT QUE DES NOMS, JAMAIS DES VALEURS, ET C'EST ÉCRIT ICI
#  NOIR SUR BLANC. La commande distante ci-dessous ne rend que la partie
#  gauche des affectations : une URL de check ou une adresse ne remonte
#  jamais dans ce terminal, ni dans les journaux de ce script.
#
#  ⛔ ET IL NE REFUSE PAS, contrairement au §2 bis. Deux raisons :
#    · le trou n'est pas causé par le déploiement — refuser de déployer
#      LE CORRECTIF parce que la chose à corriger n'est pas corrigée est
#      un piège d'amorçage, et il bloquerait tout le reste ;
#    · l'exécution, désormais, est ailleurs : depuis ce lot chaque runner
#      concerné envoie un e-mail et un push PAR JOUR tant que sa variable
#      manque (`tools/bw_avertir_config.sh`). Le §2 ter donne la vue
#      d'ensemble au moment du déploiement ; c'est le runner qui insiste.
# ══════════════════════════════════════════════════════════════════════
bw_controle_config_alertes() {
  dire "canaux d'alerte : ce que le code LIT ↔ ce que le VPS DÉFINIT (noms seuls)"
  LUES=$(bw_inv_lues "$ICI")
  [ -n "$LUES" ] || echec "aucune variable de canal trouvée dans le code — l'inventaire est cassé"

  # ⚠️ NOMS SEULS. `grep -o` sur la partie gauche du `=`, rien d'autre.
  DEFINIES=$(ssh "$VPS" '
    F="${BW_ALERTES_FILE:-$HOME/.balise-watch-alertes.env}"
    [ -r "$F" ] || exit 0
    grep -oE "^[[:space:]]*(export[[:space:]]+)?BW_[A-Z0-9_]+=" "$F" \
      | grep -oE "BW_[A-Z0-9_]+" | sort -u') \
    || echec "lecture des NOMS du fichier d'alertes impossible"

  TROUS=""; N_TROU=0; N_SANS_JOB=0; MORTES=""; N_MORTE=0
  while IFS= read -r V; do
    [ -n "$V" ] || continue
    printf '%s\n' "$DEFINIES" | grep -qxF "$V" && continue
    # ⛔ NE PAS CRIER AU LOUP : `collect-p2` et `tau` sont des modes réels
    # dont l'unité porte « ne-pas-installer ». Leur variable n'est pas un
    # trou, c'est un mode sans job. Un contrôle qui rougit deux fois à
    # chaque passage finit ignoré — piège nº 4 du lot LD.
    MODE=$(printf '%s' "$V" | sed -n 's/^BW_MODEL_\(.*\)_PING_URL$/\1/p' \
           | tr '[:upper:]_' '[:lower:]-')
    if [ -n "$MODE" ] && ! bw_inv_mode_installable "$ICI" "$MODE"; then
      N_SANS_JOB=$((N_SANS_JOB+1)); continue
    fi
    N_TROU=$((N_TROU+1)); TROUS="$TROUS
      ⛔ TROU  $V — lue par un runner, ABSENTE du fichier d'alertes du VPS.
         Le job tourne et il est INVISIBLE. Il le dira par e-mail une fois par jour."
  done <<< "$LUES"

  while IFS= read -r V; do
    [ -n "$V" ] || continue
    printf '%s\n' "$LUES" | grep -qxF "$V" && continue
    N_MORTE=$((N_MORTE+1)); MORTES="$MORTES
      ⚠️ MORTE $V — définie sur le VPS, lue par AUCUN runner.
         Une variable morte donne l'illusion d'une surveillance qui n'existe pas."
  done <<< "$DEFINIES"

  echo "  ✓ $(printf '%s\n' "$LUES" | wc -l | tr -d ' ') variables lues par le code  ·  $(printf '%s\n' "$DEFINIES" | wc -l | tr -d ' ') définies sur le VPS  ·  ⓘ $N_SANS_JOB mode(s) sans job installé"
  if [ -n "$TROUS" ]; then
    printf '%s\n' "$TROUS"
    echo "      ⓘ Geste : créer le check chez Healthchecks, puis ajouter la ligne
         dans ~/.balise-watch-alertes.env. Rien ici ne peut le faire à votre place :
         ce script ne lit que des NOMS, et n'écrit jamais dans ce fichier."
  else
    echo "  ✓ aucun trou : toute variable lue par un job installé est définie"
  fi
  [ -n "$MORTES" ] && printf '%s\n' "$MORTES"
  return 0
}

bw_controle_unites() {
  dire "dépôt ↔ /etc/systemd/system (lecture seule, sans sudo)"
  CIBLES="$(bw_cibles_etc)"
  [ -n "$CIBLES" ] || echec "aucune unité trouvée dans le dépôt — le filtre du §0 est cassé"

  # ⛔⛔ LOT LV, 01/09 — TARIR LA SOURCE DES UNITÉS ILLISIBLES.
  # Cinq unités installées sont en 0600 root, donc non comparables. La
  # sonde du 01/09 a établi que ce mode ne protège RIEN : aucune ne porte
  # d'`Environment=` ni d'`EnvironmentFile=`, et aucun secret dans son
  # `ExecStart`. Il n'est pas choisi, il est SUBI — `cp` crée le fichier
  # avec le mode de la SOURCE masqué par l'umask, et la preuve tient en
  # une ligne : `balise-entretien.service` (0600) et
  # `bw-model-collect.service` (0644) portent dans /etc la MÊME mtime À
  # LA NANOSECONDE (2026-08-09 10:52:57.703437985) — une seule commande,
  # deux modes, donc deux sources de modes différents.
  # ⇒ Le dépôt portait encore HUIT fichiers d'unité en 600 le 01/09. Tant
  #   qu'ils y sont, la prochaine installation FABRIQUE une nouvelle
  #   unité illisible : le stock de cinq grandit tout seul. On refuse
  #   ici, parce qu'un avertissement de plus serait un avertissement de
  #   plus que personne ne lit — c'est le sujet même de ce lot.
  MODES_ANORMAUX=$(printf '%s\n' "$CIBLES" | cut -d'|' -f1 | while IFS= read -r f; do
      [ -n "$f" ] || continue
      m=$(bw_mode "$f")
      [ "$m" = "644" ] || printf '      ⛔ %s est en %s dans le dépôt\n' "$f" "$m"
    done)
  if [ -n "$MODES_ANORMAUX" ]; then
    printf '%s\n' "$MODES_ANORMAUX"
    echec "des fichiers d'unité du dépôt ne sont pas en 644.
      Une unité installée depuis une source en 600 devient illisible sans sudo,
      et sort définitivement du contrôle « dépôt ↔ /etc » (cinq y sont déjà).
      Geste : chmod 644 sur les fichiers nommés ci-dessus, puis relancer."
  fi

  # Une seule connexion : pour chaque cible, l'état vu depuis le VPS.
  #   <nom sous /etc>|ABSENT|| · |ILLISIBLE|<mtime>| · |LU|<mtime>|<sha256>
  ETAT_ETC=$(printf '%s\n' "$CIBLES" | cut -d'|' -f2 | ssh "$VPS" '
    cd /etc/systemd/system || exit 1
    while IFS= read -r c; do
      [ -n "$c" ] || continue
      if   [ ! -e "$c" ]; then printf "%s|ABSENT|||\n" "$c"
      elif [ ! -r "$c" ]; then printf "%s|ILLISIBLE|%s||%s\n" "$c" "$(date -u -r "$c" +%s)" "$(stat -c "%s" "$c" 2>/dev/null)"
      else printf "%s|LU|%s|%s|%s\n" "$c" "$(date -u -r "$c" +%s)" "$(sha256sum "$c" | cut -d" " -f1)" "$(stat -c "%s" "$c" 2>/dev/null)"
      fi
    done') || echec "lecture de /etc/systemd/system impossible"

  N_OK=0; N_VOULUE=0; N_RESERVE=0
  ROUGE=""; RESERVE=""; VOULUES=""
  while IFS='|' read -r DEPOT NOM; do
    [ -n "$DEPOT" ] || continue
    LIGNE=$(printf '%s\n' "$ETAT_ETC" | awk -F'|' -v n="$NOM" '$1==n {print; exit}')
    ETAT=$(printf '%s' "$LIGNE" | cut -d'|' -f2)
    MT=$(printf '%s'   "$LIGNE" | cut -d'|' -f3)
    SHA=$(printf '%s'  "$LIGNE" | cut -d'|' -f4)
    TAILLE=$(printf '%s' "$LIGNE" | cut -d'|' -f5)
    case "$(bw_verdict_unite "$DEPOT" "$ETAT" "$MT" "$SHA" "$TAILLE")" in
      IDENTIQUE) N_OK=$((N_OK+1)) ;;
      VOULUE)    N_VOULUE=$((N_VOULUE+1)); VOULUES="$VOULUES
      ⓘ $NOM — absente de /etc, ET C'EST LA DÉCISION (marqueur dans son en-tête)" ;;
      MANQUANTE) ROUGE="$ROUGE
      ⛔ MANQUANTE       $NOM   (dépôt : $DEPOT) — jamais installée" ;;
      DIVERGENTE) ROUGE="$ROUGE
      ⛔ DIVERGENTE      $NOM   (dépôt : $DEPOT) — installée le $(bw_date "$MT"), dépôt du $(bw_date "$(bw_mtime "$DEPOT")")" ;;
      MARQUEUR_PERIME) N_RESERVE=$((N_RESERVE+1)); RESERVE="$RESERVE
      ⚠️ MARQUEUR PÉRIMÉ $NOM — porte « ne-pas-installer » alors qu'elle EST installée.
         Retirer la ligne de $DEPOT : un marqueur qui ment éteint le contrôle sur une unité vivante." ;;
      NON_VERIFIABLE_TAILLE_OK) N_RESERVE=$((N_RESERVE+1)); RESERVE="$RESERVE
      ⚠️ NON VÉRIFIABLE  $NOM — installée en 0600 root, MAIS taille identique au dépôt ($TAILLE o).
         Très probablement conforme ; l'égalité des octets reste hors de portée sans sudo." ;;
      NON_VERIFIABLE_ECART) N_RESERVE=$((N_RESERVE+1)); RESERVE="$RESERVE
      ⛔ NON VÉRIFIABLE  $NOM — illisible sans sudo, ET LA TAILLE DIFFÈRE :
         $TAILLE o installés contre $(bw_taille "$DEPOT") o dans le dépôt (installée le $(bw_date "$MT"),
         dépôt du $(bw_date "$(bw_mtime "$DEPOT")")). L'écart est RÉEL, sa nature est inconnue.
         ⓘ Avant d'écraser : chercher la taille dans l'historique git du fichier
            (git log --format=%h -- <dépôt> puis git show <sha>:<chemin> | wc -c).
            Si elle tombe sur un commit connu, l'écart est daté et le diff se lit sans sudo." ;;
      NON_VERIFIABLE) N_RESERVE=$((N_RESERVE+1)); RESERVE="$RESERVE
      ⚠️ NON VÉRIFIABLE  $NOM — installée en 0600 root, illisible sans sudo. Ni verte, ni rouge : INCONNUE." ;;
      NON_VERIFIABLE_ANCIENNE) N_RESERVE=$((N_RESERVE+1)); RESERVE="$RESERVE
      ⚠️ NON VÉRIFIABLE  $NOM — illisible sans sudo, ET PLUS ANCIENNE QUE LE DÉPÔT
         (installée le $(bw_date "$MT"), dépôt du $(bw_date "$(bw_mtime "$DEPOT")")) — probablement périmée.
         ⓘ On le DIT sans refuser : la date est un indice, les octets sont hors de portée." ;;
      *)         ROUGE="$ROUGE
      ⛔ ÉTAT INCONNU    $NOM — le VPS n'a rien répondu pour cette cible" ;;
    esac
  done <<< "$CIBLES"

  echo "  ✓ $N_OK identiques  ·  ⓘ $N_VOULUE non installées VOLONTAIREMENT  ·  ⚠️ $N_RESERVE non vérifiables"
  [ -n "$VOULUES" ] && printf '%s\n' "$VOULUES"
  [ -n "$RESERVE" ] && printf '%s\n' "$RESERVE"
  if [ -n "$ROUGE" ]; then
    printf '%s\n' "$ROUGE"
    echec "des unités du dépôt ne sont pas celles de /etc/systemd/system.
      Rien n'a été écrit, rien n'a été redémarré. Deux gestes possibles, tous
      deux À LA MAIN et avec accord explicite :
        · installer   : sudo cp <dépôt> /etc/systemd/system/<nom> && sudo systemctl daemon-reload
        · ou marquer  : ajouter '# bw-deploy: ne-pas-installer' dans l'en-tête,
                        AVEC la raison — si l'absence est la décision."
  fi
}

# ⓘ MODE BIBLIOTHÈQUE — pour le banc, et pour lui seul.
# `BW_DEPLOY_LIB=1 . tools/deploy-agrume-vps.sh` définit les listes et
# les fonctions SANS rien déployer. Le banc joue alors le VRAI rsync et
# le VRAI filtre contre des dossiers jetables, au lieu d'en recopier la
# logique — une copie qui diverge de l'original est exactement la faute
# que ce lot répare, et elle se referait ici en un mois.
[ "${BW_DEPLOY_LIB:-0}" = "1" ] && return 0 2>/dev/null

if [ "$CONTROLE_SEUL" -eq 1 ]; then
  bw_controle_unites
  bw_controle_config_alertes
  dire "✅ contrôle des unités ET des canaux terminé — RIEN n'a été transporté, écrit ni redémarré"
  exit 0
fi

# ══════════════════════════════════════════════════════════════════════
# 1. RSYNC — CINQ dossiers, jamais un seul. ⚠️ Le piège déjà payé une
#    fois côté model-verif : rsyncer seulement le paquet « métier »
#    laisse `tools/` en retard, et ça ne se voit qu'au premier import
#    qui échoue en production.
# ══════════════════════════════════════════════════════════════════════
dire "rsync ${BW_TRANSPORT_PERMS[*]} → $VPS:$DISTANT/"
for D in "${BW_TRANSPORT_PERMS[@]}"; do
  bw_rsync_perms "$D" "$VPS:$DISTANT/$D" || echec "rsync de $D/ a échoué"
done

# ⛔⛔ MODEL-VERIF, À PART, ET C'EST VOULU. Trouvé le 26/08 : ce script
# n'a JAMAIS synchronisé `model-verif/` — le lot AROME-PI y a dormi
# poussé sur GitHub mais absent du VPS pendant que ce script annonçait
# un déploiement réussi (rsync + bancs + restart, tous verts, sur les
# trois AUTRES dossiers). Une nouvelle entrée `agrume_pi` sans elle
# aurait tourné toute une nuit avec le vieux code, silencieusement.
#
# ⚠️ PAS de `-av` ici : certains fichiers de `model-verif/` sont en
# 600 sur le VPS (`score.py`, `collect.py`…), délibérément plus
# restreints que le 644 par défaut d'un checkout local. `-av` embarque
# `-p` et écraserait ces permissions avec celles du Mac. `-t` seul
# laisse les permissions déjà en place sur les fichiers existants — un
# fichier tout neuf hérite du umask distant, pas du nôtre.
dire "rsync model-verif/ → $VPS:$DISTANT/model-verif/ (permissions distantes préservées)"
# ⛔⛔ `-rtv`, ET LE `r` A COÛTÉ UNE JOURNÉE (26/08, le soir même).
# La version d'origine écrivait `-tv` : en retirant `-a` pour protéger
# les permissions 600, elle a retiré `-r` AVEC — `-a` vaut `-rlptgoD`.
# rsync a donc répondu « skipping directory model-verif/. », copié
# ZÉRO fichier, et **rendu 0**. Le script annonçait un rsync réussi ;
# seul le contrôle sha256 du §2 a dit la vérité.
# ⚠️ C'est la MÊME leçon que le matin, d'un cran plus bas : le 26/08 au
# matin, `model-verif/` n'était pas dans le rsync du tout ; le fix qui
# l'y a mis ne copiait rien. *Un correctif se vérifie par son EFFET, pas
# par sa présence dans le diff.*
# ⛔⛔⛔ ET LE 31/08, LA MÊME LEÇON UNE TROISIÈME FOIS, UN CRAN PLUS HAUT :
# le rsync copiait bien, mais son FILTRE jetait tout ce qui n'était ni
# `.py` ni `.sh` — et le contrôle du §2 portait le même filtre, donc ne
# pouvait pas le dire. *Un correctif se vérifie par son effet ; encore
# faut-il que le contrôle qui mesure l'effet regarde plus large que le
# geste qu'il contrôle.*
for D in "${BW_TRANSPORT_SANS_PERMS[@]}"; do
  bw_rsync_sans_perms "$D" "$VPS:$DISTANT/$D" || echec "rsync de $D/ a échoué"
done

# ══════════════════════════════════════════════════════════════════════
# 2. SHA256 DES DEUX CÔTÉS — le md5/sha256 « avant d'appliquer » de la
#    roadmap, ici après l'envoi : rsync affirme avoir copié, ce qui n'est
#    pas la même chose que « le VPS a exactement ces octets ».
#
#    ⛔⛔ 31/08 (lot LD) — CE CONTRÔLE NE REGARDE PLUS `*.py` ET `*.sh`,
#    IL REGARDE TOUT. C'est LE geste du lot. Le périmètre et les
#    exclusions viennent du §0, les mêmes que le transport, et rien
#    d'autre n'est écarté. Un `.service`, un `.timer`, un `.conf`, un
#    `.md`, un `.json` divergent désormais ROUGISSENT.
#    ⓘ Ce que ça change, mesuré le 31/08 avant correction : l'ancien
#    contrôle comparait 162 fichiers et rendait vert ; le nouveau en
#    compare ~275 et aurait rougi sur dix absents.
# ══════════════════════════════════════════════════════════════════════
dire "sha256 local vs distant, fichier par fichier (TOUS les fichiers des 5 dossiers)"
# ⚠️ macOS n'a que `shasum -a 256` ; le VPS (Debian) n'a que `sha256sum`
# (coreutils GNU) — même sortie « hash  chemin », deux commandes.
# ⚠️ `_to_delete/` est écarté des DEUX côtés (§0). C'est la convention du
# projet pour mettre un fichier de côté sans le supprimer ; le laisser
# dans le contrôle ferait diverger le sha256 pour un fichier dont on a
# justement décidé qu'il ne compte plus. Trouvé le 26/08 sur un
# `sonde_budget.py` orphelin du 09/08, jamais suivi par git.
BW_TROUVE="$(bw_trouve)"
LOCAL_SUM=$(eval "$BW_TROUVE" | sort -z | xargs -0 shasum -a 256)
DISTANT_SUM=$(ssh "$VPS" "cd $DISTANT && $BW_TROUVE | sort -z | xargs -0 sha256sum")

if [ "$LOCAL_SUM" != "$DISTANT_SUM" ]; then
  echo "$LOCAL_SUM" > /tmp/deploy-agrume-local.sha256
  echo "$DISTANT_SUM" > /tmp/deploy-agrume-distant.sha256
  diff /tmp/deploy-agrume-local.sha256 /tmp/deploy-agrume-distant.sha256
  echec "sha256 divergent — voir le diff ci-dessus. RIEN N'A ÉTÉ REDÉMARRÉ."
fi
echo "  ✓ identique des deux côtés ($(printf '%s\n' "$LOCAL_SUM" | wc -l | tr -d ' ') fichiers)"

# ══════════════════════════════════════════════════════════════════════
# 2 bis. LE DÉPÔT CONTRE /etc/systemd/system — QUATRE VERDICTS, ET AUCUN
#        N'ÉCRIT QUOI QUE CE SOIT.
#
#  ⛔ CE QUE CE BLOC NE FAIT PAS, ET C'EST LA DÉCISION DE YANN DU 31/08
#  (question Q2 du lot LD) : il n'INSTALLE rien, ne fait pas de
#  `daemon-reload`, et n'appelle jamais `sudo`. Installer une unité reste
#  un geste humain — parce que l'installer est souvent une DÉCISION et
#  pas une copie (voir `bw-model-collect-p2`, dont l'installation déplace
#  sept modèles de 03:19 à 04:35 UTC). Automatiser un geste rare qui
#  contient un arbitrage, c'est le mécanisme même par lequel les
#  arbitrages s'effacent. Ce bloc ne fait qu'une chose : IL LE DIT.
#
#  ⚠️ QUATRE VERDICTS, PARCE QUE TROIS NE SUFFISENT PAS :
#   · IDENTIQUE   — rien à dire.
#   · VOULUE      — l'unité porte `# bw-deploy: ne-pas-installer` dans son
#                   en-tête. Son absence de /etc EST la décision, elle est
#                   écrite dans le fichier, et le contrôle se tait. ⛔ Sans
#                   ce marqueur, le contrôle rougirait QUATRE FOIS dès son
#                   premier passage (`bw-model-collect-p2` ×2,
#                   `bw-model-tau` ×2) — et un contrôle qui crie au loup à
#                   chaque déploiement se fait ignorer, ce qui est
#                   exactement le silence dans lequel six unités ont
#                   disparu.
#   · MANQUANTE / DIVERGENTE — ROUGE, nommée, et le script s'arrête. C'est
#                   la réponse à Q3 : refuser et le DIRE, l'humain tranche.
#                   ⭐ MANQUANTE couvre le cas qui a produit ce lot — une
#                   unité NEUVE, jamais déployée (les `.timer` des L10 et
#                   L11, qu'il a fallu trouver par hasard).
#   · NON VÉRIFIABLE — cinq unités installées sont en `-rw------- root`
#                   (balise-entretien.{service,timer},
#                   bw-agrume-ingest-pi.{service,timer},
#                   bw-agrume-poller.service) : ILLISIBLES sans sudo, donc
#                   NON COMPARABLES. ⛔ Elles ne sont JAMAIS comptées
#                   vertes — la réserve est nommée à chaque passage, jamais
#                   fondue dans le « tout est vert ». C'est la règle du lot
#                   L8 : quand on ne peut pas savoir, on le dit, on ne
#                   dégrade pas en silence.
#                   ⚠️ Et quand l'unité installée est PLUS ANCIENNE que
#                   celle du dépôt, on le signale bruyamment SANS refuser :
#                   la date est un indice, pas une preuve, et refuser sur
#                   un indice bloquerait tous les déploiements jusqu'à un
#                   `sudo cp` qu'on n'a pas le droit de faire ici.
#                   ⓘ C'est le cas de `balise-entretien.service` au 31/08 :
#                   installée le 09/08, dépôt du 22/08 (lot S0.4).
# ══════════════════════════════════════════════════════════════════════
bw_controle_unites
bw_controle_config_alertes

# ══════════════════════════════════════════════════════════════════════
# 3. LES BANCS, SUR LE VPS — pas seulement sur le Mac. Le VPS a son
#    propre venv (`~/venv-balise`, `boto3` n'est pas dans le python3
#    système, cf. model-verif/README.md) : ils peuvent diverger.
# ══════════════════════════════════════════════════════════════════════
if [ "$SANS_BANCS" -eq 1 ]; then
  dire "⚠️ --sans-bancs : bancs et redémarrage SAUTÉS, à la demande"
  exit 0
fi

dire "bancs hors-ligne sur le VPS ($DISTANT)"
ssh "$VPS" bash -s <<EOF
set -e
# ⚠️ PAS de guillemets autour de \$DISTANT ici : "~/…" entre guillemets
# ne s'étend JAMAIS (le tilde n'est développé que hors quotes) — bug vu
# le 13/08, la commande échouait avec « No such file or directory »
# alors que le même \$DISTANT non quoté fonctionne très bien à l'étape 2.
cd $DISTANT
PY="\${BW_PYTHON:-\$HOME/venv-balise/bin/python3}"
[ -x "\$PY" ] || PY=python3
# ⚠️ \`tools/test_audit_r2.py\` AJOUTÉ LE 16/08 : la jauge R2 est le seul
# de ces modules qui envoie un MAIL, et c'était le seul dont le banc ne
# tournait pas au déploiement. Trois fausses alertes en une semaine, et
# à chaque fois le correctif partait sur le Mac sans que rien ne le
# revérifie sur le VPS.
for B in tools/test_mf_s3.py tools/test_audit_r2.py agrume/test_orographie.py \\
         verif/test_colonnes.py verif/test_separation.py verif/test_purge.py \\
         verif/test_confronter_quotidien.py agrume/test_grille.py \\
         agrume/test_profil.py agrume/test_radiosondage.py agrume/test_transect.py \\
         agrume/test_ingest_pi.py agrume/test_composite.py \\
         agrume/test_rafraichissement.py agrume/test_piaf.py \\
         agrume/test_freeze_balises.py agrume/test_calque.py \\
         agrume/test_front_altitude.py agrume/test_portail.py; do
  echo "  · \$B"
  "\$PY" "\$B" || exit 1
done
echo "  ✓ 19/19 bancs Python verts sur le VPS"

# ⛔ 27/08 — ET LES BANCS DE \`model-verif/\`, QUI N'AVAIENT JAMAIS
# TOURNÉ ICI. Le 26/08 au soir, ce script ne SYNCHRONISAIT même pas
# \`model-verif/\` (entrée BUGS.md : « le déploiement annonçait tout est
# vert sur un tiers du lot manquant ») ; le rsync a été ajouté, la
# VÉRIFICATION non. Le code de tout le scoring partait donc sur le VPS
# — \`score.py\`, \`inference.py\`, \`agrume_fcst.py\` — sans qu'une seule
# de ses ~1 100 assertions n'y soit rejouée. *Un rsync vérifié au
# sha256 prouve que les octets sont arrivés, jamais qu'ils tournent.*
# ⚠️ Mesuré le 27/08 : ces bancs prennent ~25 s de plus sur le VPS.
# C'est le prix, et il est écrit ici pour qu'il ne surprenne personne.
# ⚠️ 28/08 (lot L9) — CETTE LISTE EST ÉCRITE À LA MAIN, DONC ELLE SE
# PÉRIME. Le lot L9 y ajoute \`test_murphy.py\` ; au passage, trois bancs
# écrits depuis le 27/08 n'y sont TOUJOURS PAS —
# \`test_controle_tau.py\` et \`test_fraicheur.py\` (lot L8),
# ⓘ 30/08 — le lot L10 a ajouté le SIEN (\`test_agrume_court.py\`) plutôt
# que de laisser la liste se périmer d'un cran de plus. La dette de fond
# (une liste écrite à la main) reste entière ; elle est juste moins
# grande d'un banc.
# ⓘ 31/08 — le lot L11 fait de même avec \`test_agrume_quart.py\`. ⛔ Et
# ce banc-ci a une raison de plus d'être joué ICI : il contient la
# NON-RÉGRESSION de la demi-fenêtre et du plancher de l'heure ronde
# (\`scoring.demi_fenetre(3600)\` = ±20 min, \`plancher_du_pas(3600)\` = 6).
# Une divergence entre le venv du VPS et celui du Mac sur ces deux
# valeurs changerait la population de TOUTES les séries en silence — et
# c'est exactement le genre de chose qu'un sha256 ne voit pas.
# \`test_sonde_representativite.py\` / \`test_sonde_doublons.py\` /
# \`test_sonde_chaine_arome.py\` (lots L4/L6/L16, encore hors dépôt).
# ⭐ 31/08 — LA DETTE EST RÉGLÉE À MOITIÉ, SUR DÉCISION DE YANN, et la
# moitié qui reste a une raison PRÉCISE, pas un oubli de plus :
#   · \`test_controle_tau.py\` (112 assertions) et \`test_fraicheur.py\`
#     (51) sont AJOUTÉS. Les deux ont été rejoués verts avant l'ajout —
#     on n'ajoute pas un banc à la liste du déploiement sans l'avoir vu
#     passer, sinon le premier déploiement d'après casse pour une raison
#     sans rapport, exactement ce que l'alinéa ci-dessus redoutait.
#   · ⛔ \`test_sonde_representativite.py\`, \`test_sonde_doublons.py\` et
#     \`test_sonde_chaine_arome.py\` NE SONT PAS ajoutés, et pas par
#     prudence : **ils ne sont pas dans le dépôt**, non plus que les
#     sondes qu'ils testent (lots L4/L6/L16, \`git ls-files\` le dit).
#     Les mettre dans cette liste ferait dépendre le déploiement de
#     fichiers que seul le Mac possède — un déploiement qui passe chez
#     soi et casse chez le suivant. Il faut d'abord les COMMITER ; c'est
#     un geste des lots L4/L6/L16, pas de celui-ci.
# ⇒ reste ouvert : remplacer cette liste par un
# \`for B in model-verif/test_*.py\` — elle ne se périmerait plus, mais
# elle embarquerait tout ce qui ressemble à un banc, y compris ce qui
# n'y est pas prêt.
for B in model-verif/test_score.py model-verif/test_inference.py \\
         model-verif/test_duel.py model-verif/test_murphy.py \\
         model-verif/test_collect.py \\
         model-verif/test_collect_reduit.py model-verif/test_events.py \\
         model-verif/test_geopair.py model-verif/test_run_selftest.py \\
         model-verif/test_agrume_fcst.py model-verif/test_agrume_pi_fcst.py \\
         model-verif/test_arome_fcst.py model-verif/test_sonde_delta_10m.py \\
         model-verif/test_agrume_court.py \\
         model-verif/test_agrume_quart.py \\
         model-verif/test_controle_tau.py \\
         model-verif/test_fraicheur.py; do
  echo "  · \$B"
  "\$PY" "\$B" || exit 1
done
# ⚠️ \`test_scoring.py\` À PART, ET IL FAUT DIRE EXACTEMENT POURQUOI.
# Sa moitié la plus précieuse compare \`scoring.py\` à son JUMEAU
# TypeScript (\`src/lib/verifScore.ts\`) — le seul garde-fou contre une
# duplication qui diverge. Elle exige un \`--ts-results\` produit en
# TROIS ÉTAPES À LA MAIN (voir l'en-tête de \`test_scoring.py\` :
# \`--emit-fixtures\`, puis \`node parity-scoring.js\`, puis comparer), et
# \`node\` n'est de toute façon PAS sur ce VPS (vérifié le 27/08).
# ⛔ DONC : la parité N'EST JOUÉE NULLE PART AUTOMATIQUEMENT — ni ici,
# ni sur le Mac au déploiement (vérifié le 27/08 : \`test_scoring.py\`
# sans argument ÉCHOUE aussi sur le Mac, faute du fichier TS). C'est un
# TROU CONNU, pas une case cochée, et l'écrire ici est le minimum : un
# \`vert\` qui couvre 66 assertions et zéro comparaison TS serait
# exactement le motif que cette section entière corrige.
echo "  · model-verif/test_scoring.py --unit-only"
echo "    ⚠️ parité TypeScript NON jouée (procédure manuelle, cf. en-tête du banc)"
"\$PY" model-verif/test_scoring.py --unit-only || exit 1
echo "  ✓ 14/14 bancs model-verif verts sur le VPS"

# ⛔ 27/08 — CELUI-CI N'EST PAS EN PYTHON, ET C'EST PRÉCISÉMENT
# POURQUOI IL EST ICI. Ce qui a rempli la boîte de Yann la nuit du 26
# au 27 n'était pas un calcul : c'était un \`case\` de shell qui pinguait
# \`/fail\` dès la première passe perdue. Une boucle qui ne sait lancer
# que du \`.py\` n'aurait jamais rien vu.
# ⚠️ Et il tourne ICI plutôt que seulement sur le Mac parce que \`flock\`
# n'existe pas sur macOS : sur le Mac, le banc pose une doublure et ne
# teste PAS le verrou. Sur le VPS, il le teste pour de vrai.
echo "  · agrume/test-voyant-piaf.sh"
bash agrume/test-voyant-piaf.sh || exit 1

# ⛔ 31/08 (lot LD) — LE BANC DU DÉPLOIEMENT LUI-MÊME, ET IL TOURNE ICI
# POUR UNE RAISON PRÉCISE. Il joue le VRAI `rsync` de ce script (mode
# bibliothèque, cf. §0) contre des dossiers jetables, et vérifie qu'un
# `.service`, un `.timer` et un `.conf` ARRIVENT. `rsync` n'a pas la même
# version des deux côtés ; un filtre qui se comporte bien sur le Mac et
# mal ici laisserait passer exactement la faute du 31/08. ⚠️ Il ne touche
# ni au VPS, ni à /etc : uniquement des dossiers temporaires.
echo "  · tools/test_deploiement.sh"
bash tools/test_deploiement.sh || exit 1

# ⛔ 01/09 (lot LV) — LE BANC DES CANAUX, ET IL TOURNE ICI POUR DEUX
# RAISONS QUE LE MAC NE PEUT PAS COUVRIR.
#   · ses assertions E1/E2 lisent des PERMISSIONS, et les permissions qui
#     comptent sont celles de la copie D'ICI : c'est elle qu'un
#     `sudo cp` installerait dans /etc. ⚠️ `model-verif/` est transporté
#     en `-rtv` (sans `-p`, pour protéger le 600 délibéré de `score.py`),
#     donc un mode corrigé sur le Mac N'ARRIVE PAS ici : la seule façon
#     de savoir que cette copie est saine est de le vérifier ici ;
#   · `bw_avertir_config` s'appuie sur `msmtp`, `curl` et `systemd-cat`,
#     qui n'existent pas pareil des deux côtés. Le banc les remplace par
#     des faux, mais c'est ici que le chien devra aboyer pour de vrai.
echo "  · tools/test_alertes.sh"
bash tools/test_alertes.sh || exit 1
EOF
[ $? -eq 0 ] || echec "un banc a échoué sur le VPS — RIEN N'A ÉTÉ REDÉMARRÉ"

# ══════════════════════════════════════════════════════════════════════
# 4. REDÉMARRAGE — SEULEMENT les services PERSISTANTS (`--boucle`), qui
#    gardent le VIEUX code en mémoire tant qu'ils ne sont pas relancés.
#    ⛔ PAS les timers oneshot (`bw-agrume-ingest-pi`,
#    `bw-agrume-confronter-quotidien`) : chaque déclenchement relit déjà
#    le script à froid, un restart ne changerait rien et couperait un
#    run en cours pour rien.
#    ⓘ 31/08 — `traces/` entre dans le rsync, et ses deux jobs
#    (`balise-infoclimat`, `balise-entretien`) sont eux aussi des timers
#    oneshot : rien à redémarrer là non plus. Le poller Infoclimat relit
#    `poller.sh` à chaque passage, ce qui est précisément pourquoi le
#    TRANSPORT seul suffit à réparer son alerting (Q2, 31/08).
# ══════════════════════════════════════════════════════════════════════
dire "daemon-reload + redémarrage des services persistants"
ssh "$VPS" '
  sudo systemctl daemon-reload
  for S in bw-agrume-poller bw-agrume-poller-paquets bw-agrume-poller-rallonge; do
    if systemctl is-enabled --quiet "$S" 2>/dev/null; then
      sudo systemctl restart "$S" && echo "  ✓ $S redémarré"
    else
      echo "  ⓘ $S non installé ou non activé — ignoré"
    fi
  done
' || echec "le redémarrage a échoué — vérifier journalctl sur le VPS"

# ══════════════════════════════════════════════════════════════════════
# ⚠️ CE QUE CE SCRIPT NE FAIT TOUJOURS PAS, ET C'EST UN CHOIX DATÉ.
# Il TRANSPORTE désormais les unités systemd et les surcharges `.d/`
# jusqu'au dépôt distant, et il COMPARE au §2 bis ce qui est réellement
# installé dans /etc/systemd/system — mais il n'INSTALLE rien, n'active
# rien, et n'appelle `sudo` que pour le `daemon-reload` et les trois
# restarts du §4, qui existaient déjà.
# ⇒ Décision de Yann, 31/08/2026 (question Q2 du lot LD) : « transporter
#   et signaler, pas installer ». Deux raisons mesurées ce jour-là :
#     · le transport SUFFIT pour ce qui coûtait le plus cher — le poller
#       Infoclimat lit son fichier dans le dépôt distant à chaque
#       passage, donc son correctif du 03/08 arrive sans toucher à /etc ;
#     · installer est un geste RARE (trois unités en trois semaines) et
#       il porte souvent une décision, pas une copie — `bw-model-collect-p2`
#       le dit dans son en-tête. Automatiser un geste rare qui contient
#       un arbitrage, c'est le mécanisme par lequel les arbitrages
#       s'effacent, et ce lot est né d'un effacement.
# ⓘ Installer reste donc une action de Yann, à la main, une fois — mais
#   elle n'est plus INVISIBLE : le §2 bis nomme chaque unité qui manque.
# ══════════════════════════════════════════════════════════════════════
BILAN="✅ déploiement terminé — code ET unités à jour sur le VPS, bancs verts, services redémarrés"
if [ -n "$RESERVE" ]; then
  BILAN="$BILAN
   ⚠️ AVEC RÉSERVE : $N_RESERVE unité(s) installée(s) n'ont PAS pu être comparées (0600 root,
      illisibles sans sudo). Elles ne sont pas vertes ; elles sont inconnues. Voir le §2 bis."
fi
# ⛔ LOT LV — LE TROU DE CONFIGURATION EST LA DERNIÈRE LIGNE DE L'ÉCRAN,
# pas une ligne au milieu d'un rsync de 200 fichiers. C'est tout ce qui
# distingue un avertissement lu d'un avertissement émis, et vingt jours
# de cris ont prouvé que la distinction n'est pas rhétorique.
if [ "${N_TROU:-0}" -gt 0 ]; then
  BILAN="$BILAN
   ⛔ ET $N_TROU JOB(S) TOURNENT SANS SURVEILLANCE : une variable de canal lue par
      un runner installé n'est pas définie sur le VPS. Voir le §2 ter ci-dessus.
      Tant qu'elle manque, le job envoie un e-mail par jour — et rien d'autre ne
      dira qu'il s'est arrêté."
fi
dire "$BILAN"
