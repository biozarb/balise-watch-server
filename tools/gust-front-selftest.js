// Auto-test du détecteur de front de rafales (gust-front.js).
//
// Fabrique un front SYNTHÉTIQUE de géométrie connue et vérifie que le
// détecteur retrouve bien la vitesse, le cap et les heures d'arrivée
// qu'on y a mis. Ce n'est PAS une validation météo (celle-ci passe par
// le rejeu de l'archive Météo-France 6 min, cf. §8.2 de la spec) —
// c'est la garantie que la géométrie et l'algèbre sont justes, ce qui
// est le préalable à toute calibration : régler des seuils au-dessus
// d'une régression fausse ne mènerait nulle part.
//
//   node tools/gust-front-selftest.js

const gf = require('../gust-front');

const STEP_MS = 6 * 60 * 1000;
const T0 = Date.UTC(2026, 6, 30, 15, 0, 0);

// Front visé : cap 090° (plein est), 60 km/h.
const TRUE_BEARING = 90;
const TRUE_SPEED = 60;

const KM_PER_DEG_LAT = 111.32;
const LAT0 = 45.5;
const KX = KM_PER_DEG_LAT * Math.cos((LAT0 * Math.PI) / 180);

// Grille de stations : 6 colonnes est-ouest × 4 rangées nord-sud.
const stations = [];
for (let i = 0; i < 6; i++) {
  for (let j = 0; j < 4; j++) {
    const xKm = i * 40;          // vers l'est
    const yKm = (j - 1.5) * 35;  // de part et d'autre
    stations.push({
      id: `S${i}${j}`,
      nom: `Station ${i}-${j}`,
      lat: LAT0 + yKm / KM_PER_DEG_LAT,
      lon: 4.5 + xKm / KX,
      xKm,
    });
  }
}

const meta = new Map(stations.map(s => [s.id, { lat: s.lat, lon: s.lon, nom: s.nom }]));

/** Heure de passage vraie : le front part de x=0 à T0 et file vers l'est. */
function passageT(xKm) { return T0 + (xKm / TRUE_SPEED) * 3600 * 1000; }

// 3 h d'observations au pas de 6 min.
for (let k = 0; k <= 30; k++) {
  const t = T0 - 60 * 60 * 1000 + k * STEP_MS;
  const obs = stations.map(s => {
    const tp = passageT(s.xKm);
    const after = t >= tp;
    const justAfter = after && t - tp < 30 * 60 * 1000;
    return {
      id: s.id,
      // Saut de pression net de +1,5 hPa au passage, puis palier.
      pmer: 1013 + (after ? 1.5 : 0),
      ff: after ? 35 : 8,
      raf: justAfter ? 75 : (after ? 45 : 14),
      // Bascule d'ouest (270°) à nord-ouest franc (315°) — 45°, au-dessus du seuil.
      dd: after ? 315 : 270,
      temp: 24 - (after ? 4 : 0),
    };
  });
  gf.gfRecordObs(obs, t);
}

// On se place 6 min après le passage de la 4e colonne : le front est
// détectable, il reste des colonnes en aval pour tester l'ETA.
const now = passageT(120) + STEP_MS;
const res = gf.gfDetect(meta, now, 0);

let failures = 0;
function check(label, ok, detail) {
  console.log(`${ok ? '  ok  ' : ' FAIL '} ${label}${detail ? ` — ${detail}` : ''}`);
  if (!ok) failures++;
}

console.log('\nDétecteur de front de rafales — auto-test géométrique\n');

if (!res.front) {
  console.log(` FAIL  aucun front détecté (raison : ${res.reason}, stations évaluées : ${res.evaluated})`);
  process.exit(1);
}

const f = res.front;
console.log(`  Front reconstruit sur ${f.stationCount} stations, R² = ${f.r2.toFixed(3)}\n`);

check('vitesse de propagation',
  Math.abs(f.speedKmh - TRUE_SPEED) < 5,
  `${f.speedKmh.toFixed(1)} km/h attendu ~${TRUE_SPEED}`);

const bearingErr = Math.abs(gf.angDiff(f.bearing, TRUE_BEARING));
check('cap de propagation',
  bearingErr < 8,
  `${f.bearing.toFixed(1)}° attendu ~${TRUE_BEARING}° (écart ${bearingErr.toFixed(1)}°)`);

// ETA sur une station encore en aval (colonne 5, x = 200 km).
const downstream = stations.find(s => s.xKm === 200);
const etaMs = f.etaFor(downstream.lat, downstream.lon);
const errMin = Math.abs(etaMs - passageT(200)) / 60000;
check('ETA sur une station en aval',
  errMin < 15,
  `erreur ${errMin.toFixed(1)} min (objectif de calibration : médiane < 20 min)`);

check("ETA d'une station en aval postérieure à maintenant",
  etaMs > now,
  new Date(etaMs).toISOString());

check('station en aval dans le couloir',
  f.contains(downstream.lat, downstream.lon) === true);

// Un point très au nord, hors emprise latérale, ne doit PAS être ciblé :
// c'est exactement le faux positif qui ruinerait la crédibilité du push.
check('point hors couloir non ciblé',
  f.contains(LAT0 + 3.5, downstream.lon) === false);

check('saut de pression maximal remonté',
  f.maxPressureJumpHpa >= 1.0,
  `${f.maxPressureJumpHpa?.toFixed(2)} hPa`);

check('rafale maximale remontée',
  f.maxGustKmh >= 45,
  `${f.maxGustKmh?.toFixed(0)} km/h`);

check('confiance dans les bornes',
  f.confidence > 0 && f.confidence <= 95,
  String(f.confidence));

check('trois positions prévues fournies',
  Array.isArray(f.forecastLines) && f.forecastLines.length === 3);

// ── Journée calme : le taux de faux positifs sur les jours SANS front
//    compte autant que la détection sur les jours avec (§8.2).
gf.gfReset();
for (let k = 0; k <= 30; k++) {
  const t = T0 - 60 * 60 * 1000 + k * STEP_MS;
  gf.gfRecordObs(stations.map(s => ({
    id: s.id,
    pmer: 1016 + Math.sin((k + s.xKm) / 7) * 0.25,  // respiration barométrique normale
    ff: 10 + Math.sin(k / 3) * 3,
    raf: 18 + Math.sin(k / 2) * 5,
    dd: 250 + Math.sin(k / 4) * 15,                 // brise qui oscille, pas de bascule
    temp: 26 + Math.sin(k / 5),
  })), t);
}
const calm = gf.gfDetect(meta, T0 + 60 * 60 * 1000, 0);
check('journée calme : aucun front détecté',
  calm.front === null,
  calm.front ? 'FAUX POSITIF' : `raison : ${calm.reason}`);

console.log(`\n${failures === 0 ? 'Tous les contrôles passent.' : `${failures} contrôle(s) en échec.`}\n`);
process.exit(failures === 0 ? 0 : 1);
