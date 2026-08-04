// ══════════════════════════════════════════════════════════════════
//  phenomenon-delta-selftest — la route B, sans démarrer le serveur
//  (Lot 7, 04/08/2026)
//
//  Vérifie `computePhenomenonDelta` sur un référentiel synthétique :
//  ancres résolues, Δ, niveau, courbe, et surtout les REFUS — les cas
//  où le module doit rendre `null` plutôt qu'un chiffre. Sur un outil
//  de sécurité, savoir se taire est une fonctionnalité.
//
//  Aucun réseau, aucune base, index.js n'est pas chargé.
//
//    node tools/phenomenon-delta-selftest.mjs
// ══════════════════════════════════════════════════════════════════
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const req = createRequire(import.meta.url);
const { computePhenomenonDelta } = req(join(here, '..', 'lib', 'phenomenon-delta.js'));
const P = req(join(here, '..', 'lib', 'pressure.cjs'));

const T = Date.now();
let ok = 0, ko = 0;
const check = (label, got, want) => {
  const hit = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${hit ? 'ok  ' : 'ÉCHEC'} ${label}${hit ? '' : `  → ${JSON.stringify(got)} au lieu de ${JSON.stringify(want)}`}`);
  hit ? ok++ : ko++;
};

const st = (o) => ({
  source: 'metar', code: 'X', nom: 'Station', reduction: 'qnh', resolutionHpa: 1,
  tempC: 15, dd: null, ff: null, raf: null, t: T, ...o,
});
// Chambéry et Aoste : le vrai axe du foehn de Maurienne, à 5 km près.
const CHAMBERY = st({ id: 'metar:LFLB', nom: 'Chambéry', lat: 45.638, lon: 5.880, alt: 235, pressure: 1016 });
const AOSTE = st({ id: 'metar:LIMW', nom: 'Aoste', lat: 45.738, lon: 7.368, alt: 545, pressure: 1010, tempC: 24 });

const ligne = (o = {}) => ({
  id: 'ph1', user_id: null, kind: 'crest_foehn', label: 'Axe de contrôle',
  a_name: 'Chambéry', a_lat: 45.638, a_lon: 5.880,
  b_name: 'Aoste', b_lat: 45.738, b_lon: 7.368,
  station_a: null, station_b: null, gap_name: null, gap_lat: null, gap_lon: null,
  gap_alt: null, bearing: null, threshold_hpa: 2, threshold_strong_hpa: 4,
  active_sign: 'both', span_km: null, notes: null, local_names: null, ...o,
});

const vide = async () => [];
const run = (row, referential, historyFor = vide) =>
  computePhenomenonDelta({ row, referential, historyFor });

console.log('\nappariement des ancres');
const r1 = await run(ligne(), [CHAMBERY, AOSTE]);
check('les deux ancres sont trouvées par proximité', [r1.anchors.a?.nom, r1.anchors.b?.nom], ['Chambéry', 'Aoste']);
check('appariement par distance → forced = false', [r1.anchors.a.forced, r1.anchors.b.forced], [false, false]);
check('aucune ancre déclarée manquante', r1.anchors.missing, []);

const r2 = await run(ligne({ station_a: 'metar:LFLB', station_b: 'metar:LIMW' }), [CHAMBERY, AOSTE]);
check('ancres déclarées → forced = true', [r2.anchors.a.forced, r2.anchors.b.forced], [true, true]);

const r3 = await run(ligne({ station_a: 'metar:FAUTE-DE-FRAPPE' }), [CHAMBERY, AOSTE]);
check('ancre déclarée introuvable → signalée, pas remplacée', r3.anchors.missing, ['metar:FAUTE-DE-FRAPPE']);
check('… et la cause est nommée', r3.reason, 'ancre-declaree-introuvable');
check('… sans Δ inventé', r3.measured, null);

const r4 = await run(ligne(), [CHAMBERY]); // Aoste absente du référentiel
check('aucune station à portée → cause distincte', r4.reason, 'aucune-station-a-portee');

console.log('\nle Δ, et les cas où il faut refuser de le donner');
// Les deux relevés sont en QNH avec leur température : conversion
// possible, donc un Δ existe. On le compare à la physique appelée
// directement — la route ne doit rien ajouter au passage.
const attendu = P.pressureDelta(
  P.normalizePressure(P.readingFromStation(CHAMBERY)),
  P.normalizePressure(P.readingFromStation(AOSTE)),
);
check('Δ identique à la physique appelée directement',
  r1.measured.delta, Math.round(attendu.delta * 100) / 100);
check('incertitude transmise, pas recalculée',
  r1.measured.uncertaintyHpa, Math.round(attendu.uncertaintyHpa * 100) / 100);
check('le QNH a bien été converti aux deux bouts',
  [r1.measured.convertedA, r1.measured.convertedB], [true, true]);

const sansTemp = await run(ligne(), [CHAMBERY, { ...AOSTE, tempC: null }]);
check('QNH sans température → Δ refusé plutôt que faux', sansTemp.measured.delta, null);
check('… et la cause est dite', sansTemp.reason, 'no-temp');

const perchee = await run(ligne(), [CHAMBERY, { ...AOSTE, alt: 2400 }]);
check('station au-dessus de PRESSURE_MAX_ALT → écartée',
  perchee.reason, 'aucune-station-a-portee');

const sansPression = await run(ligne(), [CHAMBERY, { ...AOSTE, pressure: null }]);
check('ancre bonne mais relevé absent → cause distincte',
  sansPression.reason, 'releve-indisponible');

console.log('\nle niveau — la même règle que la fiche');
const fort = await run(ligne({ threshold_hpa: 2, threshold_strong_hpa: 4 }), [CHAMBERY, AOSTE]);
// Δ = +8,60 hPa : Chambéry 1015,85 QFF contre Aoste 1007,25 QFF. Le
// QNH brut ne donnait que +6,00 — les 2,6 hPa d'écart sont l'artefact
// d'altitude et de température que la conversion QFF supprime, et c'est
// tout le propos du §3 du document de conception.
check('Δ = +8,60 sur un seuil 2/4 → niveau 3', fort.measured.level, 3);
check('… et le Δ vaut bien +8,6', fort.measured.delta, 8.6);
check('… vers B (Δ positif)', fort.measured.direction, 'toB');
const doux = await run(ligne({ threshold_hpa: 5, threshold_strong_hpa: 10 }), [CHAMBERY, AOSTE]);
check('le même Δ sur 5/10 → niveau 2', doux.measured.level, 2);
const sourd = await run(ligne({ threshold_hpa: 9, threshold_strong_hpa: 18 }), [CHAMBERY, AOSTE]);
check('le même Δ sur 9/18 → rien', sourd.measured.level, 0);
const versant = await run(ligne({ active_sign: 'neg' }), [CHAMBERY, AOSTE]);
check('bon module, versant interdit par le phénomène → niveau 0', versant.measured.level, 0);
check('… mais le Δ reste affiché, il n\'est pas faux', versant.measured.delta, fort.measured.delta);

console.log('\nla simultanéité des deux relevés');
// Deux relevés à la même heure : rien à signaler.
check('relevés simultanés → dans la tolérance', [r1.measured.pairSpanMin, r1.measured.beyondTolerance], [0, false]);
check('deux METAR → sources homogènes', r1.measured.mixedSources, false);
// Deux heures d'écart : le Δ est rendu, mais l'écart est DIT. C'est la
// situation réelle de 16 des 27 phénomènes au 04/08.
const decale = await run(ligne(), [CHAMBERY, { ...AOSTE, t: T - 2 * 3_600_000 }]);
check('2 h d\'écart → signalé hors tolérance', decale.measured.beyondTolerance, true);
check('… avec l\'écart en minutes', decale.measured.pairSpanMin, 120);
check('… mais le Δ est rendu, pas escamoté', decale.measured.delta, r1.measured.delta);
// L'âge ne fait pas la simultanéité : deux relevés vieux mais synchrones
// donnent une mesure valable.
const vieux = await run(ligne(), [{ ...CHAMBERY, t: T - 3 * 3_600_000 }, { ...AOSTE, t: T - 3 * 3_600_000 }]);
check('vieux mais simultanés → dans la tolérance', vieux.measured.beyondTolerance, false);
check('… et leur âge est rapporté à part', vieux.measured.ageMinA, 180);
const mixte = await run(ligne(), [CHAMBERY, { ...AOSTE, id: 'mf:12345', source: 'meteofrance' }]);
check('METAR + Météo-France → sources mixtes signalées', mixte.measured.mixedSources, true);

console.log('\nles seuils rendus sont ceux de la règle, replis appliqués');
const nus = await run(ligne({ threshold_hpa: null, threshold_strong_hpa: null }), [CHAMBERY, AOSTE]);
check('seuils absents → replis 4 et 8', [nus.thresholds.hpa, nus.thresholds.strongHpa], [4, 8]);
check('active_sign absent → both', nus.thresholds.activeSign, 'both');

console.log('\nla courbe des 36 h');
const H = 3_600_000;
const histA = [0, 1, 2, 3].map(i => ({ t: T - i * H, p: 1016 - i * 0.5, tempC: 15 }));
const histB = [0, 1, 2, 3].map(i => ({ t: T - i * H + 6 * 60_000, p: 1010 + i * 0.4, tempC: 24 }));
const parId = { 'metar:LFLB': histA, 'metar:LIMW': histB };
const avecCourbe = await run(ligne(), [CHAMBERY, AOSTE], async (s) => parId[s.id] || []);
check('4 points appariés', avecCourbe.series.length, 4);
check('le dernier point vaut le Δ instantané',
  avecCourbe.series[avecCourbe.series.length - 1].delta, avecCourbe.measured.delta);

// B décalé de 3 h : seul le point le plus ancien de A retrouve un
// partenaire dans la tolérance de 45 min. Les trois autres sont REFUSÉS
// plutôt qu'interpolés — un trou dans la courbe se voit et s'interprète,
// un point interpolé se croit.
const desync = await run(ligne(), [CHAMBERY, AOSTE],
  async (s) => (s.id === 'metar:LFLB' ? histA : histB.map(p => ({ ...p, t: p.t - 3 * H }))));
check('séries décalées → seules les paires dans la tolérance survivent', desync.series.length, 1);
// Et si l'écart dépasse la tolérance partout, il ne reste rien.
const jamais = await run(ligne(), [CHAMBERY, AOSTE],
  async (s) => (s.id === 'metar:LFLB' ? histA : histB.map(p => ({ ...p, t: p.t - 12 * H }))));
check('séries sans recouvrement → aucune paire, jamais d\'interpolation', jamais.series.length, 0);

const casse = await run(ligne(), [CHAMBERY, AOSTE], async () => { throw new Error('supabase HS'); });
check('historique en panne → Δ rendu quand même', casse.measured.delta, fort.measured.delta);
check('… et la panne est signalée', casse.seriesError, true);

console.log(`\n${ok} contrôles au vert, ${ko} au rouge.`);
process.exit(ko ? 1 : 0);
