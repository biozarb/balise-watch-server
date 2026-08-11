// Banc de contrôle — ingestion Météo-France multi-créneaux (11/08/2026)
//
// À lancer à la main depuis PWA/balise-watch-server/ :
//     node tools/test_mf_slots.mjs
// (lit METEOFRANCE_API_KEY dans .env, aucun secret en dur, aucune écriture)
//
// Ce qu'il vérifie, sur des données MF RÉELLES du moment :
//   1. le paquet infrahoraire-6m se remplit après son heure de validité —
//      donc lire un seul créneau à +12 min sous-compte les stations ;
//   2. la lecture de MF_PAQUET_SLOTS créneaux consécutifs rattrape l'écart ;
//   3. l'arbitrage par validityTime ne fait jamais reculer une station
//      (propriété testée en premier, comme pour test_windsmobi_selfdedup) :
//      le résultat est identique quel que soit l'ordre de lecture des
//      créneaux.
import { readFileSync } from 'node:fs';

const MF_PAQUET_SLOTS = 3;
const KEY = (readFileSync('.env', 'utf8').match(/^METEOFRANCE_API_KEY\s*=\s*(.+)$/m) || [])[1]?.trim();
if (!KEY) { console.error('METEOFRANCE_API_KEY absente de .env'); process.exit(1); }

const URL_BASE = 'https://public-api.meteofrance.fr/public/DPPaquetObs/v2/paquet/stations/infrahoraire-6m';

function slotParams(n) {
  const base = new Date(Date.now() - 12 * 60 * 1000);
  base.setUTCMinutes(Math.floor(base.getUTCMinutes() / 6) * 6, 0, 0);
  const out = [];
  for (let k = n - 1; k >= 0; k--) out.push(new Date(base.getTime() - k * 6 * 60 * 1000).toISOString().replace(/\.\d{3}Z$/, 'Z'));
  return out;
}

async function slot(dateParam) {
  const r = await fetch(`${URL_BASE}?date=${dateParam}&format=json`, { headers: { apikey: KEY } });
  if (!r.ok) return [];
  const d = await r.json();
  return Array.isArray(d) ? d : [];
}

const vt = o => (o?.validity_time ? Date.parse(o.validity_time) : 0) || 0;

/** Même arbitrage que refreshMfObs : le validityTime le plus récent gagne. */
function merge(slots) {
  const out = new Map();
  for (const rows of slots) {
    for (const s of rows) {
      const id = s?.geo_id_insee;
      if (!id) continue;
      const prev = out.get(id);
      if (prev && vt(s) <= vt(prev)) continue;
      out.set(id, s);
    }
  }
  return out;
}

const withWind = m => [...m.values()].filter(s => s.ff != null).length;

const params = slotParams(MF_PAQUET_SLOTS);
console.log(`Créneaux lus (du plus ancien au plus récent) : ${params.join(' → ')}\n`);
const slots = [];
for (const p of params) {
  const rows = await slot(p);
  slots.push(rows);
  console.log(`  ${p}  ${String(rows.length).padStart(5)} entrées, ${String(rows.filter(s => s.ff != null).length).padStart(4)} avec vent`);
}

const merged = merge(slots);
const single = merge([slots[slots.length - 1]]); // ancien comportement : le créneau le plus frais seul
console.log(`\n1 créneau  (ancien) : ${single.size} stations, ${withWind(single)} avec vent`);
console.log(`${MF_PAQUET_SLOTS} créneaux (nouveau) : ${merged.size} stations, ${withWind(merged)} avec vent`);
const gained = withWind(merged) - withWind(single);
console.log(`→ ${gained} station(s) de vent rattrapée(s) (${(100 * gained / Math.max(1, withWind(merged))).toFixed(1)} % du réseau)`);

// Propriété 3 — l'ordre de lecture ne doit rien changer.
const reversed = merge([...slots].reverse());
let drift = 0;
for (const [id, o] of merged) if (vt(reversed.get(id)) !== vt(o)) drift++;
console.log(`\nOrdre inversé : ${reversed.size} stations, ${drift} divergence(s) de validityTime`);
console.log(drift === 0 && reversed.size === merged.size
  ? '✅ arbitrage stable — le résultat ne dépend pas de l\'ordre de lecture'
  : '❌ arbitrage INSTABLE — un marqueur pourrait changer de valeur d\'un cycle à l\'autre');

// Propriété 2 bis — aucune station ne doit reculer dans le temps.
let back = 0;
for (const rows of slots) for (const s of rows) { const id = s?.geo_id_insee; if (id && vt(merged.get(id)) < vt(s)) back++; }
console.log(back === 0 ? '✅ aucune observation retenue n\'est plus vieille qu\'une observation lue' : `❌ ${back} régression(s) temporelle(s)`);

// ── Propriété 4 — la FUSION du cache (le cœur du correctif) ────────
// Rejoue ce que fait refreshMfObs : un cycle normal, puis un cycle où
// une station a cessé d'émettre. Avant le 11/08 (`mfObsCache = next`)
// elle disparaissait de la carte ; elle doit maintenant y rester avec
// son dernier relevé, jusqu'à la purge à 12 h.
const RETENTION_MS = 12 * 60 * 60 * 1000;
function cycle(cache, lues, now) {
  for (const [id, o] of lues) {
    const prev = cache.get(id);
    if (prev && vt(o) <= vt(prev)) continue;
    cache.set(id, o);
  }
  for (const [id, o] of cache) if (vt(o) > 0 && vt(o) < now - RETENTION_MS) cache.delete(id);
  return cache;
}
const cache = cycle(new Map(), merged, Date.now());
const avant = cache.size;
const muette = [...cache.keys()][0];
const sansElle = new Map([...merged].filter(([id]) => id !== muette));
cycle(cache, sansElle, Date.now());
console.log(`\nFusion — cycle 1 : ${avant} stations ; cycle 2 sans « ${muette} » : ${cache.size}`);
console.log(cache.has(muette)
  ? `✅ la station muette reste servie avec son relevé de ${cache.get(muette).validity_time} (le client la grisera)`
  : '❌ la station muette a disparu du cache — c\'est le bug du 11/08, réintroduit');
// Et elle doit finir par sortir : même cache, mais 13 h plus tard.
cycle(cache, sansElle, Date.now() + 13 * 60 * 60 * 1000);
console.log(cache.has(muette) ? '❌ la purge à 12 h ne s\'applique pas' : '✅ purgée au-delà de 12 h — pas de fantôme éternel sur la carte');
