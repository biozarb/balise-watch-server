// Auto-test du détecteur MODÈLE (Lot A) et de l'a priori qu'il fournit
// à la détection mesurée.
//
// Comme pour l'auto-test mesure : ce n'est pas une validation météo,
// c'est la garantie que la géométrie et l'algèbre sont justes. Régler
// des seuils au-dessus d'une régression fausse ne mènerait nulle part.
//
//   node tools/gust-front-model-selftest.js

const gf = require('../gust-front');

const KM_PER_DEG_LAT = 111.32;
const LAT0 = 45.5;
const KX = KM_PER_DEG_LAT * Math.cos((LAT0 * Math.PI) / 180);

// Front annoncé : cap 090° (plein est), 55 km/h, arrivant dans 4 h sur
// le bord ouest du domaine.
const TRUE_BEARING = 90;
const TRUE_SPEED = 55;
const NOW = Date.UTC(2026, 6, 30, 12, 0, 0);
const T_START = NOW + 4 * 3600 * 1000;   // le front entre dans le domaine

// Grille modèle : 0,25° sur une emprise réduite (suffit à l'algèbre).
const lats = [];
for (let v = 44.0; v <= 47.0 + 1e-9; v += 0.25) lats.push(Math.round(v * 100) / 100);
const lons = [];
for (let v = 1.0; v <= 7.0 + 1e-9; v += 0.25) lons.push(Math.round(v * 100) / 100);
const nLon = lons.length;

// 24 échéances horaires.
const times = [];
for (let h = 1; h <= 24; h++) times.push(new Date(NOW + h * 3600 * 1000).toISOString());

function passageMs(lon) {
  const xKm = (lon - lons[0]) * KX;
  return T_START + (xKm / TRUE_SPEED) * 3600 * 1000;
}

const vars = { gust: [], spd: [], dir: [], pres: [], cape: [], precip: [], temp: [] };
for (let s = 0; s < times.length; s++) {
  const t = Date.parse(times[s]);
  const gust = [], spd = [], dir = [], pres = [], cape = [], precip = [], temp = [];
  for (let i = 0; i < lats.length; i++) {
    for (let j = 0; j < nLon; j++) {
      const tp = passageMs(lons[j]);
      const after = t >= tp;
      const justAfter = after && t - tp < 90 * 60 * 1000;
      gust.push(justAfter ? 80 : (after ? 50 : 20));
      spd.push(after ? 38 : 10);
      dir.push(after ? 320 : 265);
      pres.push(1010 + (after ? 1.6 : 0));
      // Instabilité en amont : garantit le typage `outflow`.
      cape.push(after ? 200 : 800);
      precip.push(justAfter ? 2.5 : 0);
      temp.push(25 - (after ? 5 : 0));
    }
  }
  vars.gust.push(gust); vars.spd.push(spd); vars.dir.push(dir);
  vars.pres.push(pres); vars.cape.push(cape); vars.precip.push(precip);
  vars.temp.push(temp);
}

const grid = { lats, lons, times, vars };

let failures = 0;
function check(label, ok, detail) {
  console.log(`${ok ? '  ok  ' : ' FAIL '} ${label}${detail ? ` — ${detail}` : ''}`);
  if (!ok) failures++;
}

console.log('\nDétecteur MODÈLE (Lot A) — auto-test géométrique\n');

const res = gf.gfDetectModel(grid, NOW);
if (!res.front) {
  console.log(` FAIL  aucun front annoncé détecté (raison : ${res.reason}, candidats : ${res.candidates.length})`);
  process.exit(1);
}
const f = res.front;
console.log(`  Front annoncé reconstruit sur ${f.stationCount} points de grille, R² = ${f.r2.toFixed(3)}\n`);

check('vitesse de propagation',
  Math.abs(f.speedKmh - TRUE_SPEED) < 6,
  `${f.speedKmh.toFixed(1)} km/h attendu ~${TRUE_SPEED}`);

const bErr = Math.abs(gf.angDiff(f.bearing, TRUE_BEARING));
check('cap de propagation', bErr < 8,
  `${f.bearing.toFixed(1)}° attendu ~${TRUE_BEARING}° (écart ${bErr.toFixed(1)}°)`);

check('typé outflow (garde-fou convectif satisfait)',
  f.kind === 'outflow', f.kind);

check('confiance plafonnée à 60 (c\'est une prévision)',
  f.confidence <= 60, String(f.confidence));

// ETA sur un point encore loin en aval.
const lonDown = lons[nLon - 2];
const etaMs = f.etaFor(LAT0, lonDown);
const errMin = Math.abs(etaMs - passageMs(lonDown)) / 60000;
check('ETA sur un point en aval', errMin < 25,
  `erreur ${errMin.toFixed(1)} min`);

check('ETA dans le futur', etaMs > NOW, new Date(etaMs).toISOString());

check('rafale maximale annoncée remontée',
  (f.maxGustKmh ?? 0) >= 50, `${f.maxGustKmh} km/h`);

// ── Journée sans front annoncé : rien ne doit sortir ────────────────
const calm = { lats, lons, times, vars: { gust: [], spd: [], dir: [], pres: [], cape: [], precip: [], temp: [] } };
for (let s = 0; s < times.length; s++) {
  const n = lats.length * nLon;
  calm.vars.gust.push(Array.from({ length: n }, (_, k) => 22 + ((k + s) % 5)));
  calm.vars.spd.push(Array.from({ length: n }, (_, k) => 12 + ((k + s) % 4)));
  calm.vars.dir.push(Array.from({ length: n }, (_, k) => 250 + ((k + s) % 12)));
  calm.vars.pres.push(Array.from({ length: n }, () => 1016));
  calm.vars.cape.push(Array.from({ length: n }, () => 50));
  calm.vars.precip.push(Array.from({ length: n }, () => 0));
  calm.vars.temp.push(Array.from({ length: n }, () => 24));
}
const calmRes = gf.gfDetectModel(calm, NOW);
check('journée calme : aucun front annoncé',
  calmRes.front === null,
  calmRes.front ? 'FAUX POSITIF' : `raison : ${calmRes.reason}`);

// ── Front froid synoptique : détecté, mais typé différemment ────────
const syn = JSON.parse(JSON.stringify({ lats, lons, times, vars }));
for (let s = 0; s < times.length; s++) {
  syn.vars.cape[s] = syn.vars.cape[s].map(() => 20);    // pas d'instabilité
  syn.vars.precip[s] = syn.vars.precip[s].map(() => 0); // pas de pluie
}
const synRes = gf.gfDetectModel(syn, NOW);
check('front sans convection typé synoptique',
  synRes.front != null && synRes.front.kind === 'synoptique',
  synRes.front ? synRes.front.kind : 'non détecté');

// ── Les seuils surchargeables (étape 10) NE CHANGENT RIEN par défaut ─
//  ⚠️ C'est le seul contrôle qui protège la PRODUCTION du travail de
//  l'étape 10. `gfDetectModel` accepte désormais un troisième argument
//  pour rejouer le détecteur sur un niveau où la rafale n'existe pas.
//  Un défaut qui aurait glissé ne se verrait nulle part : le détecteur
//  continuerait de tourner, en détectant simplement autre chose.
const memeQueDefaut = gf.gfDetectModel(grid, NOW, {});
check('opts vide = comportement par défaut, au R² près',
  memeQueDefaut.front != null && Math.abs(memeQueDefaut.front.r2 - f.r2) < 1e-12,
  memeQueDefaut.front ? memeQueDefaut.front.r2.toFixed(6) : 'non détecté');
check('les trois seuils par défaut valent ceux du module',
  (() => {
    const a = gf.gfDetectModel(grid, NOW,
      { gustMinKmh: 45, dvMinKmh: 15, dthetaMinDeg: 40 });
    return a.front != null && a.front.stationCount === f.stationCount;
  })(), `${f.stationCount} points`);
// Et la surcharge doit VRAIMENT agir, sinon le contrôle ci-dessus
// passerait aussi pour un paramètre ignoré.
const verrouille = gf.gfDetectModel(grid, NOW, { gustMinKmh: 10000 });
check('un verrou rafale inatteignable éteint la détection',
  verrouille.front === null, `raison : ${verrouille.reason}`);
// ⓘ Les trois seuils ensemble : la journée calme du contrôle précédent
// est sous les 45 km/h de rafale PARTOUT, donc ouvrir les seuls seuils
// de vent ne changerait rien — le verrou rafale bloquerait d'abord, et
// ce contrôle passerait au vert sans rien avoir prouvé.
const ouvert = gf.gfDetectModel(calm, NOW,
  { gustMinKmh: 0, dvMinKmh: 0, dthetaMinDeg: 0 });
check('des seuils nuls ouvrent la détection là où le défaut refusait',
  (ouvert.candidates || []).length > (calmRes.candidates || []).length,
  `${(calmRes.candidates || []).length} → ${(ouvert.candidates || []).length} candidats`);

console.log(`\n${failures === 0 ? 'Tous les contrôles passent.' : `${failures} contrôle(s) en échec.`}\n`);
process.exit(failures === 0 ? 0 : 1);
