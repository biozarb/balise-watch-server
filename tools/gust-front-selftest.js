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

// ══════════════════════════════════════════════════════════════════
//  REGROUPEMENT SPATIAL (31/08/2026)
//
//  Ce que ces contrôles protègent : jusqu'au 31/08/2026 le
//  regroupement était purement temporel, et deux orages sans rapport à
//  600 km l'un de l'autre étaient ajustés par un SEUL plan. En base, ça
//  donnait des « fronts » dont les stations tombaient en Corse, à Nice
//  et en Alsace — et un bandeau incapable de dire où était le front,
//  pour la bonne raison que l'objet n'était nulle part.
// ══════════════════════════════════════════════════════════════════

console.log('\nRegroupement spatial\n');

// ── Liaison simple : une ligne s'étire, un vide sépare ─────────────
const chaîne = [];
for (let i = 0; i < 7; i++) chaîne.push({ lat: 45, lon: 4 + (i * 100) / KX });
check('une ligne continue de 600 km reste un seul groupe',
  gf.gfClusterSpatial(chaîne, 150).length === 1,
  `${gf.gfClusterSpatial(chaîne, 150).length} groupe(s)`);

const deuxTas = [
  { lat: 45, lon: 4 }, { lat: 45, lon: 4 + 60 / KX }, { lat: 45.4, lon: 4 + 30 / KX },
  { lat: 45, lon: 4 + 500 / KX }, { lat: 45, lon: 4 + 560 / KX },
];
check('un vide de 440 km coupe en deux groupes',
  gf.gfClusterSpatial(deuxTas, 150).length === 2,
  `${gf.gfClusterSpatial(deuxTas, 150).length} groupe(s)`);

/** Enregistre 3 h d'observations pour un jeu de stations donné.
 *  `sig(s)` rend la signature voulue pour la station. */
function rejoue(stations, sig, fin) {
  gf.gfReset();
  for (let t = T0 - 60 * 60 * 1000; t <= fin; t += STEP_MS) {
    gf.gfRecordObs(stations.map(s => ({ id: s.id, ...sig(s, t) })), t);
  }
}

/** Signature de front franche (score 100) au passage à `s.tp`. */
function signatureFranche(s, t) {
  const after = t >= s.tp;
  const justAfter = after && t - s.tp < 30 * 60 * 1000;
  return {
    pmer: 1013 + (after ? 1.5 : 0),
    ff: after ? 35 : 8,
    raf: justAfter ? 75 : (after ? 45 : 14),
    dd: after ? 315 : 270,
    temp: 24 - (after ? 4 : 0),
  };
}

// ── Deux fronts simultanés à 620 km : deux objets, pas une moyenne ──
const gauche = [], droite = [];
for (let i = 0; i < 6; i++) {
  for (let j = 0; j < 4; j++) {
    const xKm = i * 40, yKm = (j - 1.5) * 35;
    const commun = { lat: LAT0 + yKm / KM_PER_DEG_LAT, tp: passageT(xKm), xKm };
    gauche.push({ id: `G${i}${j}`, lon: 4.5 + xKm / KX, ...commun });
    droite.push({ id: `D${i}${j}`, lon: 4.5 + 8 + xKm / KX, ...commun });
  }
}
const deuxFronts = [...gauche, ...droite];
const metaDeux = new Map(deuxFronts.map(s => [s.id, { lat: s.lat, lon: s.lon, nom: s.id }]));
const finDeux = passageT(120) + STEP_MS;
rejoue(deuxFronts, signatureFranche, finDeux);
const resDeux = gf.gfDetect(metaDeux, finDeux, 0);

check('deux orages à 620 km donnent deux fronts distincts',
  resDeux.fronts.length === 2,
  `${resDeux.fronts.length} front(s), ${resDeux.groupCount} groupe(s)`);
check("aucun des deux ne s'étale sur les deux zones",
  resDeux.fronts.every(x => x.spanKm < 300),
  resDeux.fronts.map(x => `${Math.round(x.spanKm)} km`).join(' / '));
check('le couloir du front ouest ne cible pas les stations de l’est',
  resDeux.fronts.length === 2 &&
    !resDeux.fronts.some(x => droite.every(s => x.contains(s.lat, s.lon))
                           && gauche.every(s => x.contains(s.lat, s.lon))));

// ── Noyau de 3 + une station lointaine : on refuse, on n'invente pas ─
// C'était LE cas majoritaire en base : 8 des 10 épisodes les plus
// dispersés avaient un noyau cohérent de 3 stations plus une station
// isolée à 300–700 km. Cette quatrième station ne validait rien, elle
// donnait la vitesse, le cap et toutes les ETA.
const noyau = [
  { id: 'N0', lat: LAT0, lon: 4.5, tp: passageT(0) },
  { id: 'N1', lat: LAT0 + 0.35, lon: 4.5 + 30 / KX, tp: passageT(30) },
  { id: 'N2', lat: LAT0 - 0.30, lon: 4.5 + 60 / KX, tp: passageT(60) },
  { id: 'LOIN', lat: LAT0, lon: 4.5 + 8, tp: passageT(45) },
];
const metaNoyau = new Map(noyau.map(s => [s.id, { lat: s.lat, lon: s.lon, nom: s.id }]));
const finNoyau = passageT(78) + STEP_MS;
rejoue(noyau, signatureFranche, finNoyau);
const resNoyau = gf.gfDetect(metaNoyau, finNoyau, 0);

check('un noyau de 3 + une station à 620 km ne fabrique plus de front',
  resNoyau.front === null,
  resNoyau.front
    ? `FAUX POSITIF, emprise ${Math.round(resNoyau.front.spanKm)} km`
    : `raison : ${resNoyau.reason}`);
check('le refus est nommé « dispersé », pas « pas assez de stations »',
  resNoyau.reason === 'scattered',
  resNoyau.reason);

// ── Repêchage local : le noyau de 3 récupère son voisin ─────────────
// Le voisin n'a QU'UN saut de pression (score 40) : hors contexte on ne
// le retiendrait pas. À 50 km de trois stations qui viennent de montrer
// une signature franche dans la même fenêtre, on le retient.
const avecVoisin = [
  { id: 'R0', lat: LAT0, lon: 4.5, tp: passageT(0), faible: false },
  { id: 'R1', lat: LAT0 + 0.36, lon: 4.5 + 25 / KX, tp: passageT(25), faible: false },
  { id: 'R2', lat: LAT0 - 0.31, lon: 4.5 + 50 / KX, tp: passageT(50), faible: false },
  { id: 'R3', lat: LAT0 + 0.09, lon: 4.5 + 70 / KX, tp: passageT(70), faible: true },
];
const metaVoisin = new Map(avecVoisin.map(s => [s.id, { lat: s.lat, lon: s.lon, nom: s.id }]));
const finVoisin = passageT(78);
rejoue(avecVoisin, (s, t) => {
  if (!s.faible) return signatureFranche(s, t);
  const after = t >= s.tp;
  // Saut de pression seul : pas de bascule de direction, pas de saut de
  // rafale au-dessus du seuil, pas de chute de température → score 40.
  return {
    pmer: 1013 + (after ? 1.5 : 0),
    ff: after ? 26 : 20,
    raf: after ? 46 : 30,
    dd: 270,
    temp: 24,
  };
}, finVoisin);
const resVoisin = gf.gfDetect(metaVoisin, finVoisin, 0);

check('le voisin au signal partiel est repêché',
  resVoisin.rescuedCount === 1,
  `${resVoisin.rescuedCount} station(s) repêchée(s)`);
check('le front local existe grâce à lui',
  !!resVoisin.front && resVoisin.front.stationCount === 4,
  resVoisin.front ? `${resVoisin.front.stationCount} stations, emprise ${Math.round(resVoisin.front.spanKm)} km`
                  : `aucun front — raison : ${resVoisin.reason}`);
check('et il reste un front LOCAL',
  !!resVoisin.front && resVoisin.front.spanKm < 150,
  resVoisin.front ? `${Math.round(resVoisin.front.spanKm)} km` : '—');
check('la confiance paie le repêchage',
  !!resVoisin.front && resVoisin.front.rescuedCount === 1
    && resVoisin.front.confidence < 70,
  resVoisin.front ? String(resVoisin.front.confidence) : '—');

console.log(`\n${failures === 0 ? 'Tous les contrôles passent.' : `${failures} contrôle(s) en échec.`}\n`);
process.exit(failures === 0 ? 0 : 1);
