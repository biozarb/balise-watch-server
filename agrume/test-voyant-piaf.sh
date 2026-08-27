#!/usr/bin/env bash
# ══════════════════════════════════════════════════════════════════════
#  agrume/test-voyant-piaf.sh — le banc du voyant          (27/08/2026)
#
#  ⛔ Il ne vérifie pas que l'ingestion marche : il vérifie QUAND le
#  voyant crie. C'est la seule chose qui a mal tourné la nuit du 26 au
#  27/08 — six passes perdues, jamais deux d'affilée, douze mails.
#
#  Quatre façons de se tromper, toutes tenues ici :
#   1. crier dès la PREMIÈRE passe perdue (le bug d'origine) ;
#   2. ne plus jamais crier (le remède pire que le mal) ;
#   3. compter des échecs SÉPARÉS PAR UNE RÉUSSITE comme une panne ;
#   4. laisser le code 3 (« rien à faire ») effacer une panne en cours.
#
#  ⚠️ Sans réseau, sans clé, sans R2 : `python` et `curl` sont remplacés
#  par des scripts de deux lignes.
#      bash agrume/test-voyant-piaf.sh
# ══════════════════════════════════════════════════════════════════════
set -uo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BAC="$(mktemp -d)"
trap 'rm -rf "$BAC"' EXIT
ECHECS=0

verifier() {  # verifier "attendu" "obtenu" "quoi"
  if [ "$1" = "$2" ]; then
    printf '  ✅ %s\n' "$3"
  else
    printf '  ❌ %s\n     attendu : %s\n     obtenu  : %s\n' "$3" "$1" "$2"
    ECHECS=$((ECHECS + 1))
  fi
}

# ── Les doublures ─────────────────────────────────────────────────────
mkdir -p "$BAC/bin"
# `curl` note le SUFFIXE pingué au lieu d'appeler quoi que ce soit.
# ⚠️ Le succès s'écrit « OK » et non la chaîne vide : sans ça, « un ping
# de succès » et « aucun ping du tout » se ressembleraient — et c'est
# exactement la distinction que ce banc doit tenir.
cat > "$BAC/bin/curl" <<'EOF'
#!/usr/bin/env bash
for a in "$@"; do
  case "$a" in http*) s="${a#http://voyant}"; echo "${s:-OK}" ;; esac
done >> "$BW_BANC_PINGS"
exit 0
EOF
chmod +x "$BAC/bin/curl"

# ⚠️ macOS n'a PAS `flock` (util-linux). Sans doublure, le script prend
# la branche « une ingestion est déjà en cours » et le banc vérifie le
# vide en silence — c'est arrivé à la première exécution de ce fichier.
# Le VPS et le runner de CI, eux, l'ont : la doublure ne sert qu'ici, et
# elle le DIT.
if ! command -v flock >/dev/null 2>&1; then
  echo "ⓘ pas de flock sur cette machine — doublure posée (le verrou" \
       "lui-même n'est donc PAS testé ici ; il l'est sur Linux)"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$BAC/bin/flock"
  chmod +x "$BAC/bin/flock"
fi
export PATH="$BAC/bin:$PATH"

# Les trois fichiers d'environnement que `charger` exige.
for f in mf r2 agrume; do echo "# vide" > "$BAC/$f.env"; done
echo "# vide" > "$BAC/alertes.env"

# `python` rend le code demandé par $BW_BANC_CODE.
cat > "$BAC/faux-python" <<'EOF'
#!/usr/bin/env bash
exit "${BW_BANC_CODE:-0}"
EOF
chmod +x "$BAC/faux-python"

passe() {  # passe <code de sortie du python>
  BW_BANC_CODE="$1" \
  BW_PYTHON="$BAC/faux-python" \
  BW_ALERTES_ENV="$BAC/alertes.env" \
  BW_MF_ENV="$BAC/mf.env" \
  BW_R2_ENV="$BAC/r2.env" \
  BW_AGRUME_R2_ENV="$BAC/agrume.env" \
  BW_AGRUME_PIAF_PING_URL="http://voyant" \
  BW_PIAF_VERROU="$BAC/verrou" \
  BW_PIAF_COMPTEUR="$BAC/compteur" \
  BW_BANC_PINGS="$BAC/pings" \
    bash "$ICI/run-ingest-piaf.sh" >/dev/null 2>&1
}

pings() { tr '\n' ' ' < "$BAC/pings" 2>/dev/null | sed 's/ $//'; }
raz()   { : > "$BAC/pings"; rm -f "$BAC/compteur"; }

echo "══════════════════════════════════════════════════════════════"
echo "  BANC DU VOYANT — six passes perdues ne font pas une panne"
echo "══════════════════════════════════════════════════════════════"

# ── 1. UNE passe perdue ne réveille personne ──────────────────────────
echo
echo "1. une passe perdue, puis la suivante réussit"
raz
passe 1
verifier "" "$(pings)" "aucun ping après le PREMIER échec"
passe 0
verifier "OK" "$(pings)" "un seul ping, de SUCCÈS, après la reprise"
verifier "0" "$(cat "$BAC/compteur")" "le compteur est remis à zéro"

# ── 2. le clignotement de la nuit du 26/08, rejoué ────────────────────
echo
echo "2. échec / succès / échec / succès — le motif de la nuit"
raz
passe 1; passe 0; passe 1; passe 0; passe 1; passe 0
verifier "OK OK OK" "$(pings)" \
  "trois succès pingués, ZÉRO /fail — douze mails devenus zéro"

# ── 3. mais une vraie panne tombe ─────────────────────────────────────
echo
echo "3. trois échecs CONSÉCUTIFS"
raz
passe 1
passe 1
verifier "" "$(pings)" "toujours muet au deuxième"
passe 1
verifier "/fail" "$(pings)" "le voyant tombe au TROISIÈME — pas plus tard"
passe 1
verifier "/fail /fail" "$(pings)" "et il reste tombé au quatrième"

# ── 4. le code 3 ne remet rien à zéro ─────────────────────────────────
echo
echo "4. « rien à faire » (code 3) au milieu d'une panne"
raz
passe 1; passe 1
passe 3
verifier "" "$(pings)" "le code 3 ne pingue rien"
verifier "2" "$(cat "$BAC/compteur")" "et n'efface pas les deux échecs"
passe 1
verifier "/fail" "$(pings)" "le troisième échec fait bien tomber le voyant"

# ── 5. une panne de configuration crie tout de suite ──────────────────
echo
echo "5. fichier d'environnement illisible"
raz
BW_PYTHON="$BAC/faux-python" \
BW_ALERTES_ENV="$BAC/alertes.env" \
BW_MF_ENV="$BAC/absent.env" \
BW_AGRUME_PIAF_PING_URL="http://voyant" \
BW_PIAF_VERROU="$BAC/verrou" \
BW_PIAF_COMPTEUR="$BAC/compteur" \
BW_BANC_PINGS="$BAC/pings" \
  bash "$ICI/run-ingest-piaf.sh" >/dev/null 2>&1
verifier "/fail" "$(pings)" \
  "/fail IMMÉDIAT : une config cassée ne se rattrape pas en 10 min"

echo
echo "══════════════════════════════════════════════════════════════"
if [ "$ECHECS" -gt 0 ]; then
  echo "❌ banc du voyant : $ECHECS vérification(s) en échec"
  exit 1
fi
echo "✅ banc du voyant : tout passe"
