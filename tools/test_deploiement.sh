#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  tools/test_deploiement.sh — le banc du CHEMIN DE DÉPLOIEMENT
#                                              (lot LD, 31/08/2026)
#
#  ⛔ POURQUOI CE BANC EXISTE. Le 31/08, six fichiers d'unité systemd
#  n'étaient jamais arrivés sur le VPS, et RIEN NE ROUGISSAIT — ni le
#  rsync (qui les jetait par filtre, en silence), ni le contrôle sha256
#  (qui portait LE MÊME filtre, et ne pouvait donc pas les voir), ni le
#  message final (« déploiement terminé »). Trois voyants verts sur une
#  faute de trois semaines.
#
#  ⭐ LE CONTRÔLE QUI COMPTE N'EST PAS « l'option rsync est corrigée ».
#  C'est : *une unité modifiée sur le Mac ARRIVE, et le script le DIT.*
#  Ce banc joue donc le VRAI `rsync` et le VRAI filtre `find` de
#  `deploy-agrume-vps.sh` (mode bibliothèque, §0 de ce script) contre des
#  dossiers jetables — jamais une recopie de leur logique, qui divergerait
#  en un mois et rendrait ce banc décoratif.
#
#  ⚠️ IL NE TOUCHE NI AU VPS, NI À /etc, NI AU DÉPÔT. Uniquement des
#  dossiers temporaires et des lectures du dépôt.
#
#  Usage :  bash tools/test_deploiement.sh      # depuis la racine du dépôt
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail
cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)" || exit 1

BW_DEPLOY_LIB=1 . tools/deploy-agrume-vps.sh || { echo "❌ impossible de sourcer le script"; exit 1; }

VERTS=0; ROUGES=0
check() {  # $1 libellé · $2 obtenu · $3 attendu
  if [ "$2" = "$3" ]; then VERTS=$((VERTS+1))
  else ROUGES=$((ROUGES+1)); printf '  ❌ %s\n     obtenu  : %s\n     attendu : %s\n' "$1" "$2" "$3"; fi
}
present() { # $1 libellé · $2 fichier attendu PRÉSENT
  if [ -e "$2" ]; then VERTS=$((VERTS+1)); else ROUGES=$((ROUGES+1)); printf '  ❌ %s — ABSENT : %s\n' "$1" "$2"; fi
}
absent() {  # $1 libellé · $2 fichier attendu ABSENT
  if [ ! -e "$2" ]; then VERTS=$((VERTS+1)); else ROUGES=$((ROUGES+1)); printf '  ❌ %s — PRÉSENT alors qu'"'"'il devait être écarté : %s\n' "$1" "$2"; fi
}

TMP=$(mktemp -d "${TMPDIR:-/tmp}/bw-banc-deploy.XXXXXX") || exit 1
trap 'rm -rf "$TMP"' EXIT

# ══════════════════════════════════════════════════════════════════════
# A. LE TRANSPORT — un faux `model-verif/` qui porte un exemplaire de
#    CHAQUE extension que la faute du 31/08 jetait.
# ══════════════════════════════════════════════════════════════════════
SRC="$TMP/src"; DST="$TMP/dst"
mkdir -p "$SRC/systemd/bw-faux.service.d" "$SRC/latence" "$SRC/__pycache__" \
         "$SRC/_to_delete" "$DST"
echo 'code'                    > "$SRC/score.py"
echo 'shell'                   > "$SRC/run.sh"
echo '[Unit]'                  > "$SRC/systemd/bw-faux.service"      # ⭐ le cas du lot
echo '[Timer]'                 > "$SRC/systemd/bw-faux.timer"        # ⭐ le cas du lot
echo '[Service]'               > "$SRC/systemd/bw-faux.service.d/20-oom.conf"   # ⭐ la surcharge
echo 'doc'                     > "$SRC/latence/README.md"
echo '{}'                      > "$SRC/latence/runs_actions.json"
echo 'x'                       > "$SRC/latence/agrume_latence.ndjson"
echo 'cache'                   > "$SRC/__pycache__/score.cpython-310.pyc"
echo 'ecarte'                  > "$SRC/_to_delete/vieux.py"
echo 'mac'                     > "$SRC/.DS_Store"
echo 'retour'                  > "$SRC/score.py.bak"
echo 'retour2'                 > "$SRC/score.py.bak-pre-lotG"
echo 'tmp'                     > "$SRC/orographie.npz.tmp"

echo "▶ A. le transport de model-verif/ (bw_rsync_sans_perms)"
bw_rsync_sans_perms "$SRC" "$DST" >/dev/null 2>&1

# ⭐⭐ LA MUTATION CENTRALE DU LOT EST ICI. Remettre dans
# `bw_rsync_sans_perms` le filtre d'origine
#     --include '*/' --include '*.py' --include '*.sh' --exclude '*'
# doit faire rougir CES CINQ lignes-ci. Au 31/08, rien ne rougissait :
# c'était tout le problème.
present "A1  un .service ARRIVE"                 "$DST/systemd/bw-faux.service"
present "A2  un .timer ARRIVE"                   "$DST/systemd/bw-faux.timer"
present "A3  une surcharge .d/*.conf ARRIVE"     "$DST/systemd/bw-faux.service.d/20-oom.conf"
present "A4  un .md ARRIVE"                      "$DST/latence/README.md"
present "A5  un .json et un .ndjson ARRIVENT"    "$DST/latence/runs_actions.json"
present "A6  (rappel) un .py ARRIVE toujours"    "$DST/score.py"
present "A7  (rappel) un .sh ARRIVE toujours"    "$DST/run.sh"

absent  "A8  __pycache__ écarté"                 "$DST/__pycache__"
absent  "A9  _to_delete écarté"                  "$DST/_to_delete"
absent  "A10 .DS_Store écarté"                   "$DST/.DS_Store"
absent  "A11 *.bak écarté"                       "$DST/score.py.bak"
absent  "A12 *.bak-* écarté (score.py.bak-pre-lotG existe SUR LE VPS)" "$DST/score.py.bak-pre-lotG"
absent  "A13 *.npz.tmp écarté"                   "$DST/orographie.npz.tmp"

# ⛔ LE CAS QUI A PRODUIT LE LOT : une unité NEUVE, jamais déployée.
# C'est celui que six fichiers ont raté — un `.timer` qui n'existe pas
# encore de l'autre côté, donc qu'aucune comparaison de contenu ne peut
# signaler, et qu'un filtre muet fait disparaître sans une ligne de log.
echo "▶ A bis. une unité NEUVE, jamais déployée"
echo '[Timer]' > "$SRC/systemd/bw-tout-neuf.timer"
absent  "A14 avant transport, la neuve n'est pas là" "$DST/systemd/bw-tout-neuf.timer"
bw_rsync_sans_perms "$SRC" "$DST" >/dev/null 2>&1
present "A15 ⭐ une unité NEUVE ARRIVE (le cas des L8/L10/L11)" "$DST/systemd/bw-tout-neuf.timer"

# ⚠️ TÉMOIN — il prouve que les assertions ci-dessus DISCRIMINENT.
# On rejoue le MÊME rsync avec le filtre d'ORIGINE, à la main : si le
# `.timer` arrivait quand même, A1-A5 seraient vraies pour une raison qui
# n'a rien à voir avec le correctif, et ce banc ne prouverait rien.
echo "▶ A ter. témoin : le filtre d'origine, rejoué à la main"
DST2="$TMP/dst-filtre-origine"; mkdir -p "$DST2"
rsync -rtv --exclude '__pycache__' --exclude '*.pyc' --exclude '*.bak' \
      --include '*/' --include '*.py' --include '*.sh' --exclude '*' \
      "$SRC/" "$DST2/" >/dev/null 2>&1
absent  "A16 ⭐ TÉMOIN : avec le filtre d'origine, le .timer N'ARRIVE PAS" "$DST2/systemd/bw-faux.timer"
present "A17 TÉMOIN : avec le filtre d'origine, le .py arrive (le rsync marchait)" "$DST2/score.py"

# ══════════════════════════════════════════════════════════════════════
# B. LE TRANSPORT AVEC PERMISSIONS (agrume/ verif/ tools/ traces/)
#    ⛔ Le bit +x compte : `balise-infoclimat.service` a son ExecStart
#    directement sur `traces/infoclimat/poller.sh`. Un poller transporté
#    sans son +x, c'est un service qui ne démarre plus.
# ══════════════════════════════════════════════════════════════════════
echo "▶ B. le transport avec permissions"
SRC2="$TMP/src-traces"; DST3="$TMP/dst-traces"
mkdir -p "$SRC2/infoclimat" "$SRC2/traces_cache/packs" "$DST3"
echo '#!/bin/bash' > "$SRC2/infoclimat/poller.sh"; chmod 755 "$SRC2/infoclimat/poller.sh"
echo '[Unit]'      > "$SRC2/infoclimat/balise-infoclimat.service"
echo 'etat'        > "$SRC2/traces_cache/packs_checkpoint.json"
echo 'log'         > "$SRC2/traces_cache/backfill_packs.log"
# ⛔ LE CAS QUI COMPTE EST LE FICHIER **DÉJÀ PRÉSENT**, ET C'EST LE BANC
# QUI L'A APPRIS (31/08, mutation nº 16 restée verte). Un fichier NEUF
# garde son +x même sans `-p` : rsync applique l'umask, pas un 644. La
# différence entre `-av` et `-rtv` ne se voit QUE sur un fichier qui
# existe déjà de l'autre côté — c'est-à-dire sur le VPS, tous les jours.
mkdir -p "$DST3/infoclimat"
echo 'vieux' > "$DST3/infoclimat/poller.sh"; chmod 644 "$DST3/infoclimat/poller.sh"
bw_rsync_perms "$SRC2" "$DST3" >/dev/null 2>&1
present "B1  le poller arrive"                    "$DST3/infoclimat/poller.sh"
check   "B2  ⭐ un poller DÉJÀ présent en 644 repasse en +x" "$([ -x "$DST3/infoclimat/poller.sh" ] && echo oui || echo non)" "oui"
# ⚠️ NON-RÉGRESSION DE L'ARBITRAGE DU 26/08, dans l'autre sens : pour
# `model-verif/`, les permissions du VPS (600 sur score.py, collect.py…)
# sont DÉLIBÉRÉMENT plus restreintes que celles du Mac. `bw_rsync_sans_perms`
# ne doit JAMAIS les remonter à 644.
DST4="$TMP/dst-mv-perms"; mkdir -p "$DST4"
echo 'ancien' > "$DST4/score.py"; chmod 600 "$DST4/score.py"
bw_rsync_sans_perms "$SRC" "$DST4" >/dev/null 2>&1
check   "B2 bis ⭐ model-verif/ NE touche PAS aux permissions distantes (600 gardé)" \
        "$(ls -l "$DST4/score.py" | cut -c1-10)" "-rw-------"
check   "B2 ter  …tout en ayant bien transporté le contenu" \
        "$(cat "$DST4/score.py")" "code"
present "B3  l'unité de traces/ arrive"           "$DST3/infoclimat/balise-infoclimat.service"
absent  "B4  ⭐ traces_cache/ (état d'exécution) EXCLU du transport" "$DST3/traces_cache"

# ══════════════════════════════════════════════════════════════════════
# C. LE CONTRÔLE — le manifeste `find` doit voir PLUS LARGE que le
#    transport, jamais moins. C'est la leçon du 31/08 : le vérificateur
#    portait l'angle mort de ce qu'il vérifiait.
# ══════════════════════════════════════════════════════════════════════
echo "▶ C. le périmètre du contrôle (sur le VRAI dépôt, lecture seule)"
MANIFESTE=$(eval "$(bw_trouve)" | tr '\0' '\n')
voit() { printf '%s\n' "$MANIFESTE" | grep -qxF "$1" && echo oui || echo non; }

check "C1  ⭐ le contrôle voit bw-model-agrume-quart.timer (L11)" \
      "$(voit model-verif/systemd/bw-model-agrume-quart.timer)" "oui"
check "C2  ⭐ le contrôle voit bw-model-agrume-court.service (L10)" \
      "$(voit model-verif/systemd/bw-model-agrume-court.service)" "oui"
check "C3  ⭐ le contrôle voit bw-model-tau.timer (L8)" \
      "$(voit model-verif/systemd/bw-model-tau.timer)" "oui"
check "C4  ⭐ le contrôle voit une surcharge .d/*.conf" \
      "$(voit model-verif/systemd/bw-model-score.service.d/20-oom.conf)" "oui"
check "C5  ⭐ le contrôle voit traces/ (déployé par RIEN avant le 31/08)" \
      "$(voit traces/infoclimat/poller.sh)" "oui"
check "C6  le contrôle voit model-verif/latence/README.md" \
      "$(voit model-verif/latence/README.md)" "oui"
check "C7  traces_cache/ hors du contrôle (sinon il rougit toutes les nuits)" \
      "$(voit traces/traces_cache/packs_checkpoint.json)" "non"
check "C8  _to_delete/ hors du contrôle" \
      "$(printf '%s\n' "$MANIFESTE" | grep -c '_to_delete/' | tr -d ' ')" "0"
check "C9  __pycache__/ hors du contrôle" \
      "$(printf '%s\n' "$MANIFESTE" | grep -c '__pycache__/' | tr -d ' ')" "0"

# ⚠️ TÉMOIN DE RÉGRESSION — l'ancien périmètre, écrit à la main, et la
# preuve chiffrée qu'il était AVEUGLE. S'il voyait les unités, C1-C5 ne
# prouveraient rien.
ANCIEN=$(find "${BW_DOSSIERS[@]}" -type f \( -name '*.py' -o -name '*.sh' \) \
         ! -path '*/__pycache__/*' ! -path '*/_to_delete/*' 2>/dev/null)
check "C10 ⭐ TÉMOIN : l'ANCIEN périmètre ne voyait AUCUNE unité systemd" \
      "$(printf '%s\n' "$ANCIEN" | grep -cE '\.(service|timer)$' | tr -d ' ')" "0"
check "C11 ⭐ TÉMOIN : le nouveau en voit, lui" \
      "$( [ "$(printf '%s\n' "$MANIFESTE" | grep -cE '\.(service|timer)$' | tr -d ' ')" -ge 35 ] && echo oui || echo non)" "oui"

# ⛔ PROPRIÉTÉ, PAS ÉNUMÉRATION : les DEUX filtres viennent de la même
# liste. On le vérifie motif par motif au lieu de l'affirmer — le jour où
# quelqu'un ajoute une exclusion d'un seul côté, cette boucle le dit.
# ⛔ AUCUN MOTIF À CHEMIN : trouvé par ce banc le 31/08 (B4 rouge). Un
# motif avec un `/` n'agit QUE côté find — la racine de rsync est le
# dossier transféré, pas celle du dépôt — et le cache d'exécution de
# traces/ partait en entier vers le VPS pendant que le contrôle, lui,
# l'ignorait. Deux filtres qui divergent : la faute du lot, refaite.
for M in "${BW_EXCLUS[@]}"; do
  case "$M" in */*) check "C0  ⛔ motif « $M » sans '/'" "avec-slash" "sans-slash" ;;
                 *) VERTS=$((VERTS+1)) ;; esac
done

for M in "${BW_EXCLUS[@]}"; do
  DANS_RSYNC=non
  for A in "${BW_RSYNC_EXCLUDE[@]}"; do [ "$A" = "$M" ] && DANS_RSYNC=oui; done
  DANS_FIND=non
  case "$(bw_find_filtre)" in *"! -name '$M'"*) DANS_FIND=oui ;; esac
  check "C12 exclusion « $M » présente des DEUX côtés" "$DANS_RSYNC/$DANS_FIND" "oui/oui"
done

# ⛔⛔ LA PROPRIÉTÉ QUI MANQUAIT LES DEUX FOIS : contrôlé ⇔ transporté.
# Le 26/08, `model-verif/` était contrôlé sans être transporté (rsync
# absent) ; le 31/08, `traces/` n'était NI l'un NI l'autre. Deux listes
# qui ne se regardaient pas, deux pannes. On les compare, une fois.
TRANSPORTES=$(printf '%s\n' "${BW_TRANSPORT_PERMS[@]}" "${BW_TRANSPORT_SANS_PERMS[@]}" | sort)
CONTROLES=$(printf '%s\n' "${BW_DOSSIERS[@]}" | sort)
check "C13 ⭐ tout dossier CONTRÔLÉ est TRANSPORTÉ, et l'inverse" \
      "$TRANSPORTES" "$CONTROLES"
check "C14 ⭐ traces/ est dans le transport (il n'y était pas avant le 31/08)" \
      "$(printf '%s\n' "${BW_TRANSPORT_PERMS[@]}" | grep -cx traces | tr -d ' ')" "1"

# ══════════════════════════════════════════════════════════════════════
# D. LES VERDICTS dépôt ↔ /etc — les six cas, sur des fichiers jetables.
# ══════════════════════════════════════════════════════════════════════
echo "▶ D. les verdicts dépôt ↔ /etc"
U="$TMP/unites"; mkdir -p "$U"
printf '[Unit]\nDescription=x\n'                                   > "$U/normale.service"
printf '[Unit]\n# bw-deploy: ne-pas-installer\nDescription=x\n'     > "$U/marquee.service"
SHA_N=$(bw_sha "$U/normale.service")

check "D1  ⭐ ABSENTE + pas de marqueur → MANQUANTE (unité NEUVE)" \
      "$(bw_verdict_unite "$U/normale.service" ABSENT '' '')" "MANQUANTE"
check "D2  ABSENTE + marqueur → VOULUE (silencieuse)" \
      "$(bw_verdict_unite "$U/marquee.service" ABSENT '' '')" "VOULUE"
check "D3  installée, même sha → IDENTIQUE" \
      "$(bw_verdict_unite "$U/normale.service" LU 1750000000 "$SHA_N")" "IDENTIQUE"
check "D4  installée, sha différent → DIVERGENTE" \
      "$(bw_verdict_unite "$U/normale.service" LU 1750000000 deadbeef)" "DIVERGENTE"
check "D5  ⛔ marqueur MAIS installée → MARQUEUR_PERIME (le marqueur ment)" \
      "$(bw_verdict_unite "$U/marquee.service" LU 1750000000 "$SHA_N")" "MARQUEUR_PERIME"
check "D6  illisible (0600) → NON_VERIFIABLE" \
      "$(bw_verdict_unite "$U/normale.service" ILLISIBLE 99999999999 '')" "NON_VERIFIABLE"
check "D7  ⭐ illisible ET plus ancienne que le dépôt → NON_VERIFIABLE_ANCIENNE" \
      "$(bw_verdict_unite "$U/normale.service" ILLISIBLE 1 '')" "NON_VERIFIABLE_ANCIENNE"
check "D8  ⛔ un illisible n'est JAMAIS compté IDENTIQUE" \
      "$( [ "$(bw_verdict_unite "$U/normale.service" ILLISIBLE 1 "$SHA_N")" = IDENTIQUE ] && echo faute || echo non)" "non"
check "D9  état inconnu → INCONNU (jamais silencieux)" \
      "$(bw_verdict_unite "$U/normale.service" '' '' '')" "INCONNU"

# ⭐⭐ LOT LV, 01/09 — CE QU'ON PEUT DIRE D'UN FICHIER ILLISIBLE.
# La taille se lit sans le droit de lecture ; le sha256, non. Ces quatre
# assertions gardent la frontière : la taille ALLÈGE la réserve, elle ne
# la lève pas — un illisible n'entre jamais dans les verts.
TL_N=$(bw_taille "$U/normale.service")
check "D10 ⭐ illisible + taille IDENTIQUE au dépôt → NON_VERIFIABLE_TAILLE_OK" \
      "$(bw_verdict_unite "$U/normale.service" ILLISIBLE 99999999999 '' "$TL_N")" "NON_VERIFIABLE_TAILLE_OK"
check "D11 ⭐ illisible + taille DIFFÉRENTE → NON_VERIFIABLE_ECART (l'écart est réel)" \
      "$(bw_verdict_unite "$U/normale.service" ILLISIBLE 99999999999 '' "$((TL_N+542))")" "NON_VERIFIABLE_ECART"
check "D12 ⛔ taille identique ne vaut PAS identique : ça reste une réserve" \
      "$( [ "$(bw_verdict_unite "$U/normale.service" ILLISIBLE 1 '' "$TL_N")" = IDENTIQUE ] && echo faute || echo non)" "non"
check "D13 ⓘ sans taille relevée, on retombe sur l'ancien verdict (rétro-compatible)" \
      "$(bw_verdict_unite "$U/normale.service" ILLISIBLE 1 '')" "NON_VERIFIABLE_ANCIENNE"
check "D14 ⛔ une taille DIFFÉRENTE prime sur la date : elle prouve plus" \
      "$(bw_verdict_unite "$U/normale.service" ILLISIBLE 1 '' "$((TL_N+1))")" "NON_VERIFIABLE_ECART"

# ⭐ D15 — LE CAS RÉEL, REJOUÉ SUR LE VRAI FICHIER. `balise-entretien.service`
# installée fait 3 542 o ; c'est EXACTEMENT la taille du blob git au commit
# 7c49711 (09/08 10:49:43), et l'unité a été installée à 10:52:57. Le seul
# commit depuis ne touche que des commentaires. Le contrôle doit donc
# NOMMER l'écart, pas le taire — et ne pas le confondre avec un identique.
check "D15 ⭐ le cas balise-entretien.service (3 542 o installés) → ECART nommé" \
      "$(bw_verdict_unite "traces/entretien/balise-entretien.service" ILLISIBLE 1754729577 '' 3542)" \
      "NON_VERIFIABLE_ECART"

# ══════════════════════════════════════════════════════════════════════
# E. LES CIBLES — le nom que porte chaque fichier DANS /etc.
# ══════════════════════════════════════════════════════════════════════
echo "▶ E. les cibles du contrôle /etc (VRAI dépôt)"
CIB=$(bw_cibles_etc)
cible() { printf '%s\n' "$CIB" | grep -qxF "$1" && echo oui || echo non; }
check "E1  une unité vise son basename" \
      "$(cible 'model-verif/systemd/bw-model-agrume-quart.timer|bw-model-agrume-quart.timer')" "oui"
check "E2  ⭐ une surcharge vise <unité>.d/<fichier>" \
      "$(cible 'model-verif/systemd/bw-model-score.service.d/20-oom.conf|bw-model-score.service.d/20-oom.conf')" "oui"
check "E3  ⭐ la surcharge OOM de la passe piaf est une cible" \
      "$(cible 'verif/systemd/bw-agrume-piaf.service.d/10-oom.conf|bw-agrume-piaf.service.d/10-oom.conf')" "oui"
check "E4  ⭐ les unités de traces/ sont des cibles" \
      "$(cible 'traces/entretien/balise-entretien.service|balise-entretien.service')" "oui"
check "E5  les 3 surcharges du dépôt sont TOUTES des cibles" \
      "$(printf '%s\n' "$CIB" | grep -c '\.d/.*\.conf|' | tr -d ' ')" "3"
# ⭐ 01/09 (lot L12) : elles sont passées de 4 à 6 le matin, et SONT
# REVENUES À 4 le soir — `bw-model-oracle.{service,timer}` a été proposé
# marqué, puis installé pour de vrai une fois son check Healthchecks
# créé, donc démarqué. Le va-et-vient est le comportement NORMAL de ce
# compteur : il suit les décisions, il ne les précède pas.
# ⚠️ Ces deux compteurs se tiennent l'un l'autre : E6 exige que les
# quatre PORTENT le marqueur, E7 qu'AUCUNE AUTRE ne le porte. Un
# marqueur posé par erreur sur une unité vivante l'effacerait du
# contrôle « dépôt ↔ /etc » — c'est-à-dire qu'on cesserait de voir sa
# disparition, la panne exacte du lot LD. Un marqueur OUBLIÉ sur une
# unité qu'on vient d'installer fait la même chose, en silence : c'est
# E7 qui l'attrape, et c'est pour ça qu'il compte les DEUX sens.
check "E6  ⭐ les 4 unités volontairement non installées portent le marqueur" \
      "$(for f in model-verif/systemd/bw-model-collect-p2.service model-verif/systemd/bw-model-collect-p2.timer \
                  model-verif/systemd/bw-model-tau.service model-verif/systemd/bw-model-tau.timer; do
           head -30 "$f" | grep -q '^# bw-deploy: ne-pas-installer' && echo x; done | wc -l | tr -d ' ')" "4"
check "E7  ⛔ et AUCUNE autre unité ne le porte (un marqueur de trop éteint un contrôle)" \
      "$(printf '%s\n' "$CIB" | cut -d'|' -f1 | while IFS= read -r f; do
           head -30 "$f" | grep -q '^# bw-deploy: ne-pas-installer' && echo x; done | wc -l | tr -d ' ')" "4"

# ══════════════════════════════════════════════════════════════════════
echo
if [ "$ROUGES" -eq 0 ]; then
  echo "  ✓ $VERTS assertions vertes, 0 rouge — le chemin de déploiement tient"
  exit 0
fi
echo "  ❌ $ROUGES assertion(s) rouge(s) sur $((VERTS+ROUGES))"
exit 1
