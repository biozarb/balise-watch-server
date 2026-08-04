// ══════════════════════════════════════════════════════════════════
//  verify-pressure-sync — le serveur et la fiche calculent-ils encore
//  le MÊME Δ ?
//  (Lot 7, route B, 04/08/2026)
//
//  Deux contrôles, et le second est le vrai :
//
//   1. BYTE À BYTE — lib/pressure.cjs est-il bien ce que le générateur
//      produit à partir des sources d'aujourd'hui ? Détecte une
//      édition à la main du fichier dérivé, et une modification de
//      pressure.ts qu'on aurait oublié de reporter.
//
//   2. DIFFÉRENTIEL — on fait passer les mêmes entrées dans le module
//      TypeScript et dans le portable, et on compare les sorties.
//      C'est ce qui prouve que le strip n'a pas changé un comportement,
//      pas seulement un texte. Aucune valeur attendue n'est écrite à la
//      main ici : un contrôle qui invente ses propres réponses ne
//      vérifie que l'imagination de celui qui l'a écrit.
//
//  Hors machine de développement (sur Render), le dépôt web est absent :
//  le script le dit et sort en 0 plutôt que de faire échouer un
//  déploiement pour une vérification qu'il ne peut pas mener.
//
//    node tools/verify-pressure-sync.mjs
// ══════════════════════════════════════════════════════════════════
import { existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const serveur = join(here, '..');
const web = join(serveur, '..', 'web');
const tsPath = join(web, 'src', 'lib', 'pressure.ts');
const generateur = join(web, 'scripts', 'build-pressure-portable.mjs');

if (!existsSync(tsPath) || !existsSync(generateur)) {
  console.log('\n— dépôt web absent : contrôle de synchronisation non mené.');
  console.log('  (normal sur Render ; lancer ce script depuis le Mac de Yann)\n');
  process.exit(0);
}

// ── Ré-exécution avec les crochets de résolution du dépôt web ────────
// `phenomena.ts` importe './utils' et '@/types/database' : sans les
// crochets, Node ne résout ni l'extension manquante ni l'alias, et le
// différentiel ne pourrait comparer que la moitié des fonctions. Les
// crochets existent déjà pour verify-phenomena.mjs — on s'en sert au
// lieu d'en écrire une deuxième version.
const hook = join(web, 'scripts', 'node-hooks', 'register.mjs');
if (!process.env.__SYNC_HOOKED && existsSync(hook)) {
  try {
    execFileSync(process.execPath, ['--import', hook, fileURLToPath(import.meta.url)], {
      stdio: 'inherit', env: { ...process.env, __SYNC_HOOKED: '1' },
    });
    process.exit(0);
  } catch (e) { process.exit(e.status ?? 1); }
}

// ── 1. Byte à byte ──────────────────────────────────────────────────
console.log('\n1. le portable correspond-il à la source ?');
try {
  const out = execFileSync(process.execPath, [generateur, '--check'], {
    cwd: web, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'],
  });
  console.log(`  ok   ${out.trim()}`);
} catch (e) {
  console.error(e.stderr || e.message);
  process.exit(1);
}

// ── 2. Différentiel TypeScript ↔ portable ───────────────────────────
const pressureNs = await import(pathToFileURL(tsPath).href);
// Les deux fonctions d'appariement vivent dans phenomena.ts et
// haversineKm dans utils.ts — c'est précisément la frontière du §2 :
// la physique n'a pas de dépendance, l'appariement en a une.
const utilsNs = await import(pathToFileURL(join(web, 'src', 'lib', 'utils.ts')).href);
const phenoNs = await import(pathToFileURL(join(web, 'src', 'lib', 'phenomena.ts')).href);
const ts = {
  ...pressureNs,
  haversineKm: utilsNs.haversineKm,
  pickStationFor: phenoNs.pickStationFor,
  resolveAnchors: phenoNs.resolveAnchors,
};
const cjs = createRequire(import.meta.url)(join(serveur, 'lib', 'pressure.cjs'));

let ok = 0, ko = 0;
const compare = (label, a, b) => {
  // JSON ne distingue pas -0 de 0 ni NaN d'un null : on compare la
  // forme LISIBLE, en gardant ces cas explicites.
  const norme = (v) => JSON.stringify(v, (_k, x) =>
    typeof x === 'number' && !Number.isFinite(x) ? `#${String(x)}` : (Object.is(x, -0) ? '#-0' : x));
  const hit = norme(a) === norme(b);
  console.log(`  ${hit ? 'ok  ' : 'ÉCHEC'} ${label}${hit ? '' : `\n        ts  : ${norme(a)}\n        cjs : ${norme(b)}`}`);
  hit ? ok++ : ko++;
};

/** Applique la même fonction des deux côtés et compare. */
const duel = (nom, ...args) => {
  if (typeof ts[nom] !== 'function') { compare(`${nom} (absent côté ts)`, 'fonction', undefined); return; }
  if (typeof cjs[nom] !== 'function') { compare(`${nom} (absent du portable)`, 'fonction', undefined); return; }
  const run = (f) => { try { return f(...args); } catch (e) { return `#throw:${e.message}`; } };
  compare(`${nom}(${args.map(a => JSON.stringify(a)).join(', ').slice(0, 60)}…)`,
    run(ts[nom]), run(cjs[nom]));
};

console.log('\n2. les constantes');
for (const k of Object.keys(pressureNs)) {
  if (typeof ts[k] === 'function') continue;
  compare(`${k}`, ts[k], cjs[k]);
}

// Aucune fonction ne doit manquer au portable : un oubli d'extraction
// ne se verrait qu'au moment où le serveur l'appellerait, en production.
console.log('\n2 bis. rien ne manque au portable');
for (const k of Object.keys(ts)) {
  if (typeof ts[k] !== 'function') continue;
  compare(`${k} présent`, 'fonction', typeof cjs[k] === 'function' ? 'fonction' : `#${typeof cjs[k]}`);
}

console.log('\n3. la physique, mêmes entrées des deux côtés');
// Cas réels et cas limites : l'altitude qui écarte une station, la
// température manquante qui doit rendre null plutôt qu'un chiffre faux.
duel('qnhToStation', 1013.25, 500);
duel('stationToQff', 955.1, 500, 12.4);
duel('qnhToQff', 1013, 500, 12.4);
duel('qnhToQff', 1013, 0, -8);
const lecture = (raw, red, elev, tempC, res) => ({ raw, reduction: red, elev, tempC, resolutionHpa: res, t: 1_754_300_000_000 });
duel('normalizePressure', lecture(1016.2, 'qff', 420, null, 0.1));
duel('normalizePressure', lecture(1013, 'qnh', 420, 14.2, 1));
duel('normalizePressure', lecture(1013, 'qnh', 420, null, 1));   // pas de température → null
duel('normalizePressure', lecture(1013, 'qnh', 2400, 3, 1));     // trop haut → écartée
duel('pressureDelta',
  { qff: 1016.2, uncertaintyHpa: 0.05, converted: false },
  { qff: 1010.8, uncertaintyHpa: 0.5, converted: true });
duel('pressureDelta',
  { qff: null, uncertaintyHpa: 0.5, converted: false },
  { qff: 1010.8, uncertaintyHpa: 0.5, converted: true });
duel('smoothPressureSeries', [1013, null, 1014, 1015, null, 1011], 3);
duel('readingFromQff', 1016.2, 420, 1_754_300_000_000);
duel('readingFromMetar', 1013, 420, 14.2, 1_754_300_000_000);
duel('readingFromStation', {
  id: 'metar:LFLB', source: 'metar', code: 'LFLB', nom: 'Chambéry',
  lat: 45.638, lon: 5.88, alt: 235, reduction: 'qnh', resolutionHpa: 1,
  pressure: 1013, tempC: 21.5, dd: 190, ff: 8, raf: null, t: 1_754_300_000_000,
});
duel('readingFromStation', { pressure: null, alt: 235, reduction: 'qnh', resolutionHpa: 1, tempC: null, t: 0 });
duel('haversineKm', 45.638, 5.88, 45.735, 7.313);

console.log('\n4. les séries et l\'appariement');
const T = 1_754_300_000_000, H = 3_600_000;
const serieA = [0, 1, 2, 3].map(i => lecture(1016.2 - i * 0.4, 'qff', 420, null, 0.1));
const serieB = [0, 1, 2, 3].map(i => lecture(1010.8 + i * 0.3, 'qnh', 545, 18 - i, 1));
serieA.forEach((r, i) => { r.t = T + i * H; });
serieB.forEach((r, i) => { r.t = T + i * H + 12 * 60_000; }); // décalés de 12 min
duel('deltaSeries', serieA, serieB);
duel('deltaSeries', serieA, serieB, 5 * 60_000);  // tolérance trop courte → rien n'apparie
duel('deltaSeries', [], serieB);

const stations = [
  { id: 'metar:LFLB', source: 'metar', code: 'LFLB', nom: 'Chambéry', lat: 45.638, lon: 5.88, alt: 235, reduction: 'qnh', resolutionHpa: 1, pressure: 1013, tempC: 21.5, dd: null, ff: null, raf: null, t: T },
  { id: 'smn:VIS', source: 'smn', code: 'VIS', nom: 'Visp', lat: 46.303, lon: 7.843, alt: 639, reduction: 'qff', resolutionHpa: 0.1, pressure: 1015.4, tempC: null, dd: null, ff: null, raf: null, t: T },
  { id: 'metar:LIMW', source: 'metar', code: 'LIMW', nom: 'Aoste', lat: 45.738, lon: 7.368, alt: 545, reduction: 'qnh', resolutionHpa: 1, pressure: 1010, tempC: 24, dd: null, ff: null, raf: null, t: T },
  { id: 'smn:HAUT', source: 'smn', code: 'HAUT', nom: 'Station perchée', lat: 45.74, lon: 7.37, alt: 2400, reduction: 'qff', resolutionHpa: 0.1, pressure: 760, tempC: null, dd: null, ff: null, raf: null, t: T },
];
duel('pickStationFor', 45.735, 7.313, stations);                       // Aoste, proche
duel('pickStationFor', 45.735, 7.313, stations, { maxKm: 2 });         // trop loin → null
duel('pickStationFor', 45.74, 7.37, stations, { maxAlt: 3000 });       // la perchée redevient éligible
duel('pickStationFor', 0, 0, stations);                                 // nulle part → null
const ph = (stationA, stationB) => ({ stationA, stationB, aLat: 45.638, aLon: 5.88, bLat: 45.735, bLon: 7.313 });
duel('resolveAnchors', ph(null, null), stations);                      // appariement par proximité
duel('resolveAnchors', ph('metar:LFLB', 'metar:LIMW'), stations);      // ancres déclarées
duel('resolveAnchors', ph('metar:INEXISTANT', null), stations);        // ancre fausse → missing
duel('buildPressureReferential', stations.slice(0, 2), [
  { id: '73329001', nom: 'Bourg-Saint-Maurice', lat: 45.62, lon: 6.76, alt: 865, pmer: 1014.2, dd: 200, ff: 4, validityTime: '2026-08-04T16:00:00Z' },
  { id: 'sans-alt', nom: 'Sans altitude', lat: 45, lon: 6, alt: null, pmer: 1013, dd: null, ff: null, validityTime: null },
], []);

console.log(`\n${ok} contrôles au vert, ${ko} au rouge.`);
if (ko) console.error('\n!! La fiche et le serveur ne calculent PAS le même Δ.\n');
process.exit(ko ? 1 : 0);
