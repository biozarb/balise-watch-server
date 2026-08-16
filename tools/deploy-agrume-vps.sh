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

cd "$ICI" || { echo "❌ dépôt introuvable : $ICI" >&2; exit 1; }

dire()  { printf '\n▶ %s\n' "$*"; }
echec() { printf '\n❌ %s\n' "$*" >&2; exit 1; }

# ══════════════════════════════════════════════════════════════════════
# 1. RSYNC — trois dossiers, jamais un seul. ⚠️ Le piège déjà payé une
#    fois côté model-verif : rsyncer seulement le paquet « métier »
#    laisse `tools/` en retard, et ça ne se voit qu'au premier import
#    qui échoue en production.
# ══════════════════════════════════════════════════════════════════════
dire "rsync agrume/ verif/ tools/ → $VPS:$DISTANT/"
for D in agrume verif tools; do
  rsync -av --exclude '__pycache__' --exclude '*.pyc' --exclude 'data/*.npz.tmp' \
        "$D/" "$VPS:$DISTANT/$D/" || echec "rsync de $D/ a échoué"
done

# ══════════════════════════════════════════════════════════════════════
# 2. SHA256 DES DEUX CÔTÉS — le md5/sha256 « avant d'appliquer » de la
#    roadmap, ici après l'envoi : rsync affirme avoir copié, ce qui n'est
#    pas la même chose que « le VPS a exactement ces octets ».
# ══════════════════════════════════════════════════════════════════════
dire "sha256 local vs distant, fichier par fichier"
# ⚠️ macOS n'a que `shasum -a 256` ; le VPS (Debian) n'a que `sha256sum`
# (coreutils GNU) — même sortie « hash  chemin », deux commandes.
LOCAL_SUM=$(find agrume verif tools -type f \( -name '*.py' -o -name '*.sh' \) \
            ! -path '*/__pycache__/*' -print0 | sort -z | xargs -0 shasum -a 256)
DISTANT_SUM=$(ssh "$VPS" \
  "cd $DISTANT && find agrume verif tools -type f \( -name '*.py' -o -name '*.sh' \) \
   ! -path '*/__pycache__/*' -print0 | sort -z | xargs -0 sha256sum")

if [ "$LOCAL_SUM" != "$DISTANT_SUM" ]; then
  echo "$LOCAL_SUM" > /tmp/deploy-agrume-local.sha256
  echo "$DISTANT_SUM" > /tmp/deploy-agrume-distant.sha256
  diff /tmp/deploy-agrume-local.sha256 /tmp/deploy-agrume-distant.sha256
  echec "sha256 divergent — voir le diff ci-dessus. RIEN N'A ÉTÉ REDÉMARRÉ."
fi
echo "  ✓ identique des deux côtés"

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
         agrume/test_freeze_balises.py agrume/test_calque.py agrume/test_front_altitude.py; do
  echo "  · \$B"
  "\$PY" "\$B" || exit 1
done
echo "  ✓ 16/16 bancs verts sur le VPS"
EOF
[ $? -eq 0 ] || echec "un banc a échoué sur le VPS — RIEN N'A ÉTÉ REDÉMARRÉ"

# ══════════════════════════════════════════════════════════════════════
# 4. REDÉMARRAGE — SEULEMENT les services PERSISTANTS (`--boucle`), qui
#    gardent le VIEUX code en mémoire tant qu'ils ne sont pas relancés.
#    ⛔ PAS les timers oneshot (`bw-agrume-ingest-pi`,
#    `bw-agrume-confronter-quotidien`) : chaque déclenchement relit déjà
#    le script à froid, un restart ne changerait rien et couperait un
#    run en cours pour rien.
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
# ⚠️ CE QUE CE SCRIPT NE FAIT PAS. Il ne COPIE ni n'ACTIVE aucune unité
# systemd nouvelle (agrume/systemd/*, verif/systemd/*) : installer un
# timer inédit reste une action de Yann, à la main, une fois — cf.
# l'en-tête de chaque .service. Ce script ne fait que redéployer du code
# derrière des unités DÉJÀ installées.
# ══════════════════════════════════════════════════════════════════════
dire "✅ déploiement terminé — code sur R2/VPS à jour, bancs verts, services redémarrés"
