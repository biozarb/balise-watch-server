// Banc de vérification du dédoublonnage inter-réseaux winds.mobi
// (index.js, windsmobiSelfDuplicates — session 10/08/2026).
//
// Rejoue la logique sur un jeu de données figé, dont le cas réel remonté
// par Yann : Tarerach servie par ffvl-5065 ET iweathar-1081, 22 m
// d'écart. Ce qu'on vérifie, dans l'ordre d'importance :
//   1. le doublon disparaît, et c'est le réseau de vol libre qui reste ;
//   2. deux vraies balises voisines (> 180 m) ne sont PAS fusionnées ;
//   3. le résultat ne dépend pas de l'ordre d'insertion dans le cache —
//      c'est LA propriété qui protège `user_watched.beacon_id`.
//
//   node tools/test_windsmobi_selfdedup.mjs

const WINDSMOBI_PROVIDERS_FAST = ['holfuy', 'ffvl'];
const WINDSMOBI_PROVIDERS_SLOW = [
  'slf', 'meteoswiss', 'windspots', 'aletsch', 'windball', 'windline',
  'iweathar', 'pgsonda', 'gxaircom', 'pdcs', 'yvbeach', 'thunerwetter',
  'kachelmannwetter', 'wunderground',
];
const WINDSMOBI_DEDUP_M = 180;
const RANK = new Map([...WINDSMOBI_PROVIDERS_FAST, ...WINDSMOBI_PROVIDERS_SLOW].map((p, i) => [p, i]));

// Copie conforme de fwHaversineKm (index.js).
function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371, toRad = d => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1), dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function selfDuplicates(cache) {
  const grid = new Map(), drop = new Set();
  const entries = [...cache.entries()].sort((a, b) => {
    const ra = RANK.get(a[1].reseau) ?? 99, rb = RANK.get(b[1].reseau) ?? 99;
    if (ra !== rb) return ra - rb;
    return a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0;
  });
  for (const [id, o] of entries) {
    if (!Number.isFinite(o.lat) || !Number.isFinite(o.lon)) continue;
    const clat = Math.round(o.lat * 10), clon = Math.round(o.lon * 10);
    let dup = false;
    for (let dlat = -1; dlat <= 1 && !dup; dlat++) {
      for (let dlon = -1; dlon <= 1 && !dup; dlon++) {
        const cell = grid.get(`${clat + dlat},${clon + dlon}`);
        if (!cell) continue;
        for (const [klat, klon] of cell) {
          if (haversineKm(o.lat, o.lon, klat, klon) * 1000 < WINDSMOBI_DEDUP_M) { dup = true; break; }
        }
      }
    }
    if (dup) { drop.add(id); continue; }
    const key = `${clat},${clon}`;
    let cell = grid.get(key);
    if (!cell) { cell = []; grid.set(key, cell); }
    cell.push([o.lat, o.lon]);
  }
  return drop;
}

// ── Jeu d'essai ────────────────────────────────────────────────────
const FIXTURE = [
  // Le cas réel (coordonnées relevées sur l'API winds.mobi le 10/08).
  ['ffvl-5065',      { reseau: 'ffvl',      lat: 42.6872, lon: 2.48804 }],
  ['iweathar-1081',  { reseau: 'iweathar',  lat: 42.687,  lon: 2.488   }],
  // Deux balises distinctes du même massif, ~1,2 km : ne doivent PAS
  // fusionner.
  ['holfuy-1235',    { reseau: 'holfuy',    lat: 45.9000, lon: 6.1000  }],
  ['holfuy-1236',    { reseau: 'holfuy',    lat: 45.9100, lon: 6.1000  }],
  // Cas limite volontaire : 150 m, donc SOUS le rayon → fusion attendue,
  // et c'est holfuy (rang 0) qui doit rester face à slf (rang 2).
  ['slf-77',         { reseau: 'slf',       lat: 46.5013, lon: 7.2000  }],
  ['holfuy-99',      { reseau: 'holfuy',    lat: 46.5000, lon: 7.2000  }],
  // Coordonnées absentes : ignorées sans planter.
  ['pdcs-1',         { reseau: 'pdcs',      lat: null,    lon: null    }],
];

function run(entries) {
  return [...selfDuplicates(new Map(entries))].sort();
}

let failures = 0;
const check = (label, ok, detail) => {
  console.log(`${ok ? '✅' : '❌'} ${label}${detail ? ` — ${detail}` : ''}`);
  if (!ok) failures++;
};

const dropped = run(FIXTURE);
console.log(`Masqués : ${JSON.stringify(dropped)}\n`);

check('Tarerach ne sort qu\'une fois', dropped.includes('iweathar-1081'));
check('C\'est la FFVL qui reste, pas le relais iweathar', !dropped.includes('ffvl-5065'));
check('Deux balises à 1,2 km restent distinctes',
  !dropped.includes('holfuy-1235') && !dropped.includes('holfuy-1236'));
check('À 150 m, le réseau de vol libre l\'emporte sur slf',
  dropped.includes('slf-77') && !dropped.includes('holfuy-99'));
check('Une balise sans coordonnées ne fait rien planter', !dropped.includes('pdcs-1'));

// Propriété la plus importante : indépendance à l'ordre des polls.
const shuffles = [
  [...FIXTURE].reverse(),
  [FIXTURE[1], FIXTURE[5], FIXTURE[0], FIXTURE[4], FIXTURE[3], FIXTURE[6], FIXTURE[2]],
  [FIXTURE[6], FIXTURE[4], FIXTURE[2], FIXTURE[0], FIXTURE[5], FIXTURE[3], FIXTURE[1]],
];
const stable = shuffles.every(s => JSON.stringify(run(s)) === JSON.stringify(dropped));
check('Résultat identique quel que soit l\'ordre d\'insertion', stable,
  'c\'est ce qui garantit qu\'une balise surveillée ne clignote pas');

console.log(failures ? `\n${failures} test(s) en échec.` : '\nTous les tests passent.');
process.exit(failures ? 1 : 0);
