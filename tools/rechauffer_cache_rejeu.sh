#!/usr/bin/env bash
# Réchauffe le cache de rejeu (formule 6) en journée, du plus ancien au
# plus récent, UN processus par journée — la mémoire ne s'empile pas.
# Usage : rechauffer_cache.sh 2026-08-06 2026-09-03
set -uo pipefail
cd ~/balise-watch/balise-watch-server/model-verif || exit 1
set -a; . ~/.balise-watch-r2.env; . ~/.balise-watch-model-verif.env; set +a
export STORAGE_BACKEND=r2 R2_BUCKET=model-verif MODEL_VERIF_BUCKET=model-verif PYTHONUNBUFFERED=1
d="$1"; fin="$2"
while [[ "$d" < "$fin" || "$d" == "$fin" ]]; do
  t=$(date +%s)
  ~/venv-balise/bin/python3 - "$d" <<'EOF'
import sys, pathlib, time, resource
from datetime import datetime
import score as J
day = datetime.strptime(sys.argv[1], "%Y-%m-%d")
root = pathlib.Path("/var/lib/bw-model-verif")
st = J._storage()
p = J.replay_path(root, day)
avant = J.replay_read(root, day)
if avant is not None:
    print(f"{day:%Y-%m-%d} : cache déjà en formule {J.REPLAY_FORMULA} ({len(avant)} lignes) — rien à faire")
    sys.exit(0)
rows = J.replay_day(root, day, st, 7200)
n_mix = sum(1 for r in rows if r.get("model") == "bw_mix")
n_h24 = sum(1 for r in rows if r.get("model") in ("agrume", "agrume_pi") and r.get("lead_h") == 24)
n_fin = sum(1 for r in rows if r.get("err_vec_med_corr_fin") is not None)
rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024
print(f"{day:%Y-%m-%d} : {len(rows)} balise-jours, {n_mix} bw_mix, {n_h24} AGRUME +24 h, {n_fin} corrigés fin, pic {rss} Mo")
EOF
  echo "   ($(( $(date +%s) - t )) s)"
  d=$(date -u -d "$d + 1 day" +%Y-%m-%d)
done
echo "✅ réchauffage terminé"
