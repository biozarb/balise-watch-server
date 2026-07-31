// Mesure du coût réel du détecteur de front de rafales :
// CPU par cycle, mémoire du buffer, et taille de la charge utile servie
// aux clients. Objectif : savoir si on tient dans les tiers gratuits
// plutôt que de l'estimer.
//
//   node tools/gust-front-bench.js

const gf = require('../gust-front');

const N_STATIONS = 780;   // taille réelle mesurée du paquet infrahoraire-6m
const STEP_MS = 6 * 60 * 1000;
const CYCLES = 30;        // 3 h d'historique, la profondeur du buffer
const T0 = Date.UTC(2026, 6, 30, 15, 0, 0);

const KM_PER_DEG_LAT = 111.32;
const stations = [];
for (let i = 0; i < N_STATIONS; i++) {
  // Semis pseudo-aléatoire déterministe sur l'emprise France.
  const a = Math.sin(i * 12.9898) * 43758.5453;
  const b = Math.sin(i * 78.233) * 43758.5453;
  const rx = a - Math.floor(a), ry = b - Math.floor(b);
  stations.push({
    id: `ST${String(i).padStart(4, '0')}`,
    nom: `Station ${i}`,
    lat: 42.5 + ry * 8.5,
    lon: -3.5 + rx * 12.0,
  });
}
const meta = new Map(stations.map(s => [s.id, { lat: s.lat, lon: s.lon, nom: s.nom }]));

// Front réel traversant la France d'ouest en est à 60 km/h.
const FRONT_SPEED = 60;
function passageT(lon) {
  const xKm = (lon + 3.5) * KM_PER_DEG_LAT * Math.cos(45.5 * Math.PI / 180);
  return T0 + (xKm / FRONT_SPEED) * 3600 * 1000;
}

const memBefore = process.memoryUsage().heapUsed;

let ingestMs = 0;
for (let k = 0; k <= CYCLES; k++) {
  const t = T0 - 60 * 60 * 1000 + k * STEP_MS;
  const obs = stations.map(s => {
    const tp = passageT(s.lon);
    const after = t >= tp;
    const justAfter = after && t - tp < 30 * 60 * 1000;
    return {
      id: s.id,
      pmer: 1013 + (after ? 1.5 : 0),
      ff: after ? 35 : 8,
      raf: justAfter ? 75 : (after ? 45 : 14),
      dd: after ? 315 : 270,
      temp: 24 - (after ? 4 : 0),
    };
  });
  const t0 = process.hrtime.bigint();
  gf.gfRecordObs(obs, t);
  ingestMs += Number(process.hrtime.bigint() - t0) / 1e6;
}

const memAfter = process.memoryUsage().heapUsed;
const now = T0 + 2 * 3600 * 1000;

// Plusieurs passes pour lisser le JIT.
let detectMs = 0, res = null;
for (let r = 0; r < 5; r++) {
  const t0 = process.hrtime.bigint();
  res = gf.gfDetect(meta, now, 8 * 60 * 1000);
  detectMs += Number(process.hrtime.bigint() - t0) / 1e6;
}
detectMs /= 5;

console.log('\n═══ Coût du détecteur de front de rafales ═══\n');
console.log(`Stations suivies            : ${N_STATIONS}`);
console.log(`Profondeur du buffer        : ${CYCLES} cycles (3 h)`);
console.log(`Mémoire du buffer           : ${((memAfter - memBefore) / 1024 / 1024).toFixed(1)} Mo`);
console.log(`Ingestion (total ${CYCLES + 1} cycles) : ${ingestMs.toFixed(0)} ms  → ${(ingestMs / (CYCLES + 1)).toFixed(1)} ms/cycle`);
console.log(`Détection (moyenne 5 passes): ${detectMs.toFixed(0)} ms/cycle`);

if (!res.front) {
  console.log(`\n⚠️ Aucun front détecté (${res.reason}) — le calcul de charge utile est sauté.`);
  process.exit(0);
}

const f = res.front;
console.log(`\nFront reconstruit           : ${f.stationCount} stations, ${f.speedKmh.toFixed(0)} km/h`);

// Charge utile servie par /gust-front/active, telle qu'un client la reçoit.
const detections = res.detections.map(d => ({
  event_id: '00000000-0000-0000-0000-000000000000',
  source: 'mf_station', station_id: d.id, station_name: d.nom,
  lat: d.lat, lon: d.lon, detected_at: new Date(d.t).toISOString(),
  delta_pressure_hpa: d.deltaPressureHpa, delta_speed_kmh: d.deltaSpeedKmh,
  delta_heading_deg: d.deltaHeadingDeg, delta_temp_c: d.deltaTempC,
  gust_kmh: d.gustKmh, score: d.score,
}));

// Toutes les positions du couloir = les cibles écrites en base ET
// renvoyées au client. C'est le poste qui peut déraper.
const targets = [];
for (const s of stations) {
  if (!f.contains(s.lat, s.lon)) continue;
  targets.push({
    event_id: '00000000-0000-0000-0000-000000000000',
    station_id: s.id, station_name: s.nom, source: 'meteofrance',
    lat: s.lat, lon: s.lon,
    eta_at: new Date(f.etaFor(s.lat, s.lon)).toISOString(),
    eta_window_minutes: 15, expected_gust_kmh: f.maxGustKmh, passed_at: null,
  });
}

const payload = JSON.stringify({ events: [{
  id: '00000000-0000-0000-0000-000000000000',
  axis: { type: 'LineString', coordinates: [[1, 45], [2, 46]] },
  corridor: { type: 'Polygon', coordinates: [f.corridor] },
  detections, targets,
}] });

const kb = payload.length / 1024;
console.log(`\nCibles dans le couloir      : ${targets.length}  (sur ${N_STATIONS} stations MF seules)`);
console.log(`Charge utile /gust-front/active : ${kb.toFixed(0)} Ko par réponse`);

// Ce que ça donne côté quota, à raison d'un poll client toutes les 6 min.
for (const pilots of [10, 50, 200]) {
  const perDay = pilots * (24 * 60 / 6) * kb / 1024; // Mo/jour
  console.log(`  ${String(pilots).padStart(3)} pilotes, épisode actif : ${perDay.toFixed(1)} Mo/jour d'egress`);
}
console.log('');
