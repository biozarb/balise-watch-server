# ══════════════════════════════════════════════════════════════════════
#  bw_inventaire_alertes.sh — QUELLES VARIABLES DE CANAL LE CODE LIT-IL ?
#  Lot LV, 01/09/2026.  ⛔ FICHIER SOURCÉ, JAMAIS EXÉCUTÉ.
#
#  ⛔⛔ UNE SEULE DÉFINITION, LUE PAR LE BANC ET PAR LE DÉPLOIEMENT.
#  C'est la leçon du lot LD, à un étage de plus : là-bas, le contrôle
#  sha256 et le transport avaient chacun leur filtre, et le contrôle
#  certifiait sa propre cécité. Ici, si le banc énumérait les variables
#  d'un côté et le déploiement de l'autre, les deux listes divergeraient
#  — et celle du contrôle serait toujours la plus vieille.
#
#  ⛔ ET SURTOUT : LA LISTE N'EST PAS ÉCRITE, ELLE EST DÉRIVÉE DU CODE.
#  Une liste écrite à la main est un troisième inventaire à tenir à jour,
#  c'est-à-dire un quatrième endroit où diverger. On lit donc les
#  runners eux-mêmes.
#
#  ⚠️ LE PIÈGE QUI A COÛTÉ LA SONDE DU 31/08 : `model-verif/run.sh`
#  CONSTRUIT le nom de sa variable (l. ~320) :
#      PING_VAR="BW_MODEL_$(printf '%s' "$MODE" | tr '[:lower:]-' '[:upper:]_')_PING_URL"
#  Grepper des noms littéraux en rate ONZE d'un coup. On énumère donc
#  les MODES déclarés dans son `case` d'usage, et on rejoue exactement
#  la même translittération.
#
#  ⚠️ ET LES COMMENTAIRES NE COMPTENT PAS. `poller.sh` cite
#  `BW_PING_FAIL_URL` et `BW_MAIL_TO` dans le pavé du 03/08 qui explique
#  qu'ils n'existent nulle part. Les prendre pour des variables lues
#  fabriquerait deux faux trous permanents — donc on retire les lignes
#  de commentaire AVANT de chercher.
# ══════════════════════════════════════════════════════════════════════

# Les cinq runners qui portent un canal d'alerte, relatifs à la racine du
# dépôt serveur. ⚠️ Ajouter un runner ici est le SEUL geste manuel de ce
# fichier ; le banc `test_alertes.sh` vérifie qu'aucun autre script du
# dépôt ne lit un `*_PING_URL` sans figurer dans cette liste.
BW_RUNNERS_ALERTE="model-verif/run.sh
traces/infoclimat/poller.sh
traces/entretien/entretien.sh
agrume/run-ingest-pi.sh
agrume/run-ingest-piaf.sh
verif/run-confronter-quotidien.sh"

# ── Les modes de model-verif/run.sh, lus dans son `case` d'usage ──────
bw_inv_modes() {
  local racine="${1:-.}"
  sed -n 's/^  \(collect[^)]*\)) ;;$/\1/p' "$racine/model-verif/run.sh" \
    | head -1 | tr '|' '\n' | sed '/^$/d'
}

# ── Les noms CONSTRUITS par model-verif/run.sh ───────────────────────
# ⛔ La translittération est recopiée à l'identique de la l. 320. Si elle
# change là-bas et pas ici, le banc `test_alertes.sh` le voit : il
# compare cette sortie au nom que le script CALCULE réellement pour
# chaque mode, en le faisant calculer par `run.sh` lui-même.
bw_inv_construites() {
  local racine="${1:-.}" m
  bw_inv_modes "$racine" | while IFS= read -r m; do
    [ -n "$m" ] || continue
    printf 'BW_MODEL_%s_PING_URL\n' \
      "$(printf '%s' "$m" | tr '[:lower:]-' '[:upper:]_')"
  done
}

# ── Les noms LITTÉRAUX lus par les runners ───────────────────────────
# La règle est une règle de FORME, pas une liste de noms : tout ce qui
# finit par `_PING_URL`, plus les trois canaux partagés et
# l'interrupteur du self-test. Ajouter demain un `BW_X_PING_URL` dans un
# runner suffit à le faire entrer dans l'inventaire — c'est le point.
bw_inv_litterales() {
  local racine="${1:-.}" f
  printf '%s\n' "$BW_RUNNERS_ALERTE" | while IFS= read -r f; do
    [ -f "$racine/$f" ] || continue
    # ⚠️ On retire les lignes de commentaire AVANT de chercher.
    sed 's/^[[:space:]]*#.*$//' "$racine/$f" \
      | grep -oE '\$\{?!?(BW_[A-Z0-9_]*_PING_URL|BW_ALERTE_MAIL|BW_WEBHOOK_URL|BW_PING_OK_URL|BW_MODEL_SELF_TEST_BLOQUANT)' \
      | grep -oE 'BW_[A-Z0-9_]+'
  done
}

# ── L'INVENTAIRE A : tout ce que le code lit, trié, dédoublonné ──────
bw_inv_lues() {
  local racine="${1:-.}"
  { bw_inv_litterales "$racine"; bw_inv_construites "$racine"; } | sort -u
}

# ── L'INVENTAIRE C : ce que l'exemple versionné annonce ──────────────
# On accepte la ligne active comme la ligne commentée (`# export …`) :
# l'exemple ne doit jamais porter de valeur, donc tout y est commenté.
BW_EXEMPLE_ALERTES="traces/entretien/balise-watch-alertes.env.exemple"
bw_inv_exemple() {
  local racine="${1:-.}"
  [ -f "$racine/$BW_EXEMPLE_ALERTES" ] || return 0
  grep -oE '^#?[[:space:]]*export[[:space:]]+BW_[A-Z0-9_]+' "$racine/$BW_EXEMPLE_ALERTES" \
    | grep -oE 'BW_[A-Z0-9_]+' | sort -u
}

# ── Quelles unités sont RÉELLEMENT installées pour un mode donné ─────
# ⛔ Sert à ne pas crier au loup : `collect-p2` et `tau` sont des modes
# réels dont l'unité porte « # bw-deploy: ne-pas-installer ». Leur
# variable n'est pas un trou, c'est un mode sans job. Confondre les deux
# ferait rougir le contrôle deux fois à chaque passage — et un contrôle
# qui crie au loup finit ignoré (piège nº 4 du lot LD).
bw_inv_mode_installable() {
  local racine="${1:-.}" mode="$2"
  local u="$racine/model-verif/systemd/bw-model-$mode.service"
  [ -f "$u" ] || return 0          # pas d'unité connue : on ne tranche pas
  head -30 "$u" | grep -q '^# bw-deploy: ne-pas-installer' && return 1
  return 0
}
