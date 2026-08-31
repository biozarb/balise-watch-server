// Auto-test du module `departements.js`.
//
// Vérifie deux choses, et pas une de plus :
//  1. que les contours embarqués répondent juste sur des points dont la
//     réponse est connue de tous (préfectures, mer, Corse) ;
//  2. que « quels départements ce couloir traverse-t-il » se comporte
//     comme il faut aux bords — couloir minuscule, couloir maritime,
//     couloir à cheval sur une frontière.
//
// Ce n'est pas une validation cartographique : les contours sont ceux de
// l'IGN, on ne les rejuge pas. C'est la garantie que le chargement, le
// ray casting et l'échantillonnage font ce qu'on croit — le préalable à
// afficher un numéro de département à un pilote qui décidera s'il plie.
//
//   node tools/departements-selftest.js

const dep = require('../departements');

let failures = 0;
function check(label, ok, detail) {
  console.log(`${ok ? '  ok  ' : ' FAIL '} ${label}${detail ? ` — ${detail}` : ''}`);
  if (!ok) failures++;
}

console.log('\nContours départementaux — auto-test\n');

const charges = dep.departementsCharges();
check('contours chargés', charges.count === 96,
  `${charges.count} départements${charges.error ? ` (erreur : ${charges.error})` : ''}`);

// ── Points connus ──────────────────────────────────────────────────
// Préfectures choisies pour couvrir les cas qui cassent : la Corse (deux
// codes non numériques), une île, un département enclavant (75 dans 92),
// et deux points hors France qu'il ne faut PAS attribuer.
const points = [
  ['Grenoble', 45.188, 5.724, '38'],
  ['Chambéry', 45.564, 5.917, '73'],
  ['Annecy', 45.899, 6.129, '74'],
  ['Perpignan', 42.698, 2.895, '66'],
  ['Ajaccio', 41.926, 8.736, '2A'],
  ['Bastia', 42.700, 9.450, '2B'],
  ['Brest', 48.390, -4.486, '29'],
  ['Strasbourg', 48.573, 7.752, '67'],
  ['Paris', 48.857, 2.352, '75'],
  ['Nanterre', 48.892, 2.207, '92'],
  ['Gap', 44.559, 6.079, '05'],
  ['Genève (CH)', 46.204, 6.143, null],
  ['Turin (IT)', 45.070, 7.687, null],
  ['Méditerranée', 42.500, 5.500, null],
];
for (const [nom, lat, lon, attendu] of points) {
  const d = dep.departementAt(lat, lon);
  const got = d ? d.code : null;
  check(`${nom}`, got === attendu,
    `${got ?? 'hors France'}${d ? ` (${d.nom})` : ''} — attendu ${attendu ?? 'hors France'}`);
}

check('latitude/longitude invalides ne renvoient rien',
  dep.departementAt(NaN, 5) === null && dep.departementAt(45, undefined) === null);

// ── Couloirs ───────────────────────────────────────────────────────
/** Petit rectangle lon/lat autour d'un point. */
function boite(lat, lon, dLat, dLon) {
  return [
    [lon - dLon, lat - dLat], [lon + dLon, lat - dLat],
    [lon + dLon, lat + dLat], [lon - dLon, lat + dLat], [lon - dLon, lat - dLat],
  ];
}

// Un couloir large sur la cuvette grenobloise : Isère en tête, et les
// deux Savoies présentes puisqu'il mord dessus.
const alpes = dep.departementsDuCouloir(boite(45.4, 5.9, 0.5, 0.6));
check('couloir alpin : l’Isère en tête',
  alpes.departements[0]?.code === '38',
  alpes.departements.slice(0, 5).map(d => d.code).join(' '));
check('couloir alpin : Savoie et Haute-Savoie présentes',
  ['73', '74'].every(c => alpes.departements.some(d => d.code === c)),
  `${alpes.departements.length} départements, couverture ${alpes.coverage}`);

// Un couloir MINUSCULE (5 km) ne contient aucun nœud de la grille
// d'échantillonnage : c'est l'échantillonnage du contour qui doit le
// sauver. Sans lui, un front court rendrait une liste vide.
const minuscule = dep.departementsDuCouloir(boite(45.188, 5.724, 0.02, 0.03));
check('couloir minuscule : liste non vide',
  minuscule.departements.length > 0 && minuscule.departements[0].code === '38',
  minuscule.departements.map(d => d.code).join(' ') || 'VIDE');

// Un couloir entièrement en mer : couverture nulle, et surtout AUCUN
// département inventé. C'est le cas réel d'un front corse qui part vers
// le large (deux épisodes en base les 21 et 24/08/2026).
const mer = dep.departementsDuCouloir(boite(41.5, 6.5, 0.4, 0.5));
check('couloir maritime : aucun département, couverture nulle',
  mer.departements.length === 0 && mer.coverage === 0);

// ── departementsConcernes : le couloir, complété par la mesure ──────
// Front corse partant vers la mer : le couloir ne rend rien, mais les
// stations qui l'ont mesuré sont bien en Haute-Corse. Sans ce
// complément, le bandeau retomberait à « quelque part en France ».
const corse = dep.departementsConcernes(
  boite(41.5, 6.5, 0.4, 0.5),
  [{ lat: 42.70, lon: 9.45 }, { lat: 42.55, lon: 9.48 }],
);
check('front parti en mer : la mesure rattrape la liste',
  corse.departements.length === 1 && corse.departements[0].code === '2B',
  `${corse.departements.map(d => d.code).join(' ')} — origine ${corse.origin}`);
check('un département hors couloir est marqué share = 0',
  corse.departements[0]?.share === 0);

// Cas nominal : couloir renseigné, stations dedans → rien à compléter.
const nominal = dep.departementsConcernes(
  boite(45.4, 5.9, 0.5, 0.6), [{ lat: 45.188, lon: 5.724 }]);
check('couloir renseigné : origine « couloir » seule',
  nominal.origin === 'couloir', nominal.origin);

// Entrées absurdes : on rend une liste vide, on ne jette pas.
check('anneau invalide rendu vide sans exception',
  dep.departementsDuCouloir(null).departements.length === 0
  && dep.departementsDuCouloir([[1, 2]]).departements.length === 0);
check('aucune mesure et aucun couloir : origine « aucun »',
  dep.departementsConcernes(null, []).origin === 'aucun');

// ── Coût ───────────────────────────────────────────────────────────
// Le détecteur tourne toutes les 6 min ; un couloir doit rester
// négligeable devant le cycle, sans quoi on aurait échangé une
// information contre une latence.
const grand = boite(46.5, 3.0, 3.5, 4.0);
const t0 = Date.now();
for (let i = 0; i < 20; i++) dep.departementsDuCouloir(grand);
const ms = (Date.now() - t0) / 20;
check('un grand couloir coûte moins de 50 ms', ms < 50, `${ms.toFixed(1)} ms`);

console.log(`\n${failures === 0 ? 'Tous les contrôles passent.' : `${failures} contrôle(s) en échec.`}\n`);
process.exit(failures === 0 ? 0 : 1);
