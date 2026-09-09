#!/usr/bin/env node
// ══════════════════════════════════════════════════════════════════════
//  tools/banc_cellule_09-09.mjs — le banc du lot 3         (09/09/2026)
//                                 « cellule qui approche »
//
//  ⛔ CE QU'IL VÉRIFIE, ET QUI NE SE VOIT PAS À L'ŒIL : qu'un composite
//  qui additionne des sources SANS regarder l'heure fabrique des cellules
//  qui n'existent pas. C'est la seule chose que ce lot apporte, et c'est
//  la seule qu'un test peut prouver.
//
//  ⛔ ET IL DOIT SAVOIR ÉCHOUER : chaque garde-fou est SABOTÉ (le compte
//  de sources sans concordance, une source indisponible prise pour un
//  calme, la moyenne des ETA au lieu du milieu de l'intersection, un
//  impact isolé pris pour une cellule…) et le banc vérifie que le
//  contrôle vire au rouge.
//
//  ⚠️ Les impacts synthétiques portent un `t` en HEURE D'ARRIVÉE, comme
//  le vrai buffer — pas l'horodatage Blitzortung, que l'ingestion jette.
//  Un banc qui fabriquerait des horodatages source testerait un code qui
//  n'existe pas.
//
//  Usage :  node tools/banc_cellule_09-09.mjs
// ══════════════════════════════════════════════════════════════════════
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const require = createRequire(import.meta.url);
const ICI = dirname(fileURLToPath(import.meta.url));
const C = require(join(ICI, '..', 'lib', 'cellule-convective.js'));

let ok = 0, ko = 0;
function check(nom, cond, detail = '') {
  if (cond) { ok++; console.log(`  ✅ ${nom}${detail ? ' — ' + detail : ''}`); }
  else { ko++; console.log(`  ❌ ${nom}${detail ? ' — ' + detail : ''}`); }
}
const section = t => console.log(`\n── ${t}`);

const NOW = Date.parse('2026-09-09T16:30:00Z');
const SITE = { lat: 43.10, lon: 2.50 };
const KX = 111.2 * Math.cos(SITE.lat * Math.PI / 180), KY = 111.2;

/** Des impacts à `dKm` du site dans la direction `deDeg`, étalés au
 *  hasard sur `rayonKm`, tombés il y a `ageMin` minutes. */
function impacts({ n, deDeg, dKm, ageMin, etaleKm = 5, graine = 1 }) {
  const a = deDeg * Math.PI / 180;
  const cx = Math.sin(a) * dKm, cy = Math.cos(a) * dKm;
  let s = graine;
  const rnd = () => (s = (s * 1103515245 + 12345) % 2147483648) / 2147483648 - 0.5;
  return Array.from({ length: n }, () => {
    const x = cx + rnd() * 2 * etaleKm, y = cy + rnd() * 2 * etaleKm;
    return { lat: SITE.lat + y / KY, lon: SITE.lon + x / KX, t: NOW - ageMin * 60_000 };
  });
}
const piafDit = etaMin => ({ refus: null, hit: etaMin != null, etaMin, passe: '2026-09-09T16:20:00Z', passeAgeMin: 10, trend: 'approaching', mmMax5: 2.1, secteur: 'SW', cpaKm: 14 });
const rafaleDit = etaMin => ({ refus: null, cellule: etaMin != null, etaMin, run: '2026-09-09T15:00:00Z', runAgeMin: 90, gustKmh: 62, regimeKmh: 18, sautHitKmh: 44, seuilKmh: 30, secteur: 'SW' });

// ══════════════════════════════════════════════════════════════════════
section('1. La foudre — ce que le buffer sait et qu\'on ne lui demandait pas');
{
  const vide = C.foudreAutour([], SITE.lat, SITE.lon, NOW);
  check('buffer vide : disponible, mais rien vu', vide.disponible === true && vide.nRecent === 0 && vide.etaMin === null);
  check('⛔ « aucun impact » ≠ « pas de flux » : le premier est disponible', vide.refus === null);
  const pasDeFlux = C.foudreAutour(null, SITE.lat, SITE.lon, NOW);
  check('flux absent : NON disponible, refus nommé', pasDeFlux.disponible === false && pasDeFlux.refus === 'pas-de-flux');

  // Un orage à 30 km au SW, qui se rapproche à ~40 km/h.
  const f = C.foudreAutour([
    ...impacts({ n: 6, deDeg: 225, dKm: 40, ageMin: 22, graine: 3 }),
    ...impacts({ n: 14, deDeg: 225, dKm: 30, ageMin: 5, graine: 7 }),
  ], SITE.lat, SITE.lon, NOW);
  console.log('    ', JSON.stringify(f));
  check(`14 impacts récents, 6 avant : tendance « ${f.tendance} »`, f.tendance === 'hausse');
  check(`le plus proche à ${f.dKm} km`, f.dKm > 20 && f.dKm < 40);
  check(`il vient du ${f.secteur}`, f.secteur === 'SW' || f.secteur === 'SSW' || f.secteur === 'WSW');
  check(`déplacement mesuré : ${f.vitesseKmh} km/h`, f.vitesseKmh >= 5 && f.vitesseKmh <= 90);
  check(`ETA estimée : ${f.etaMin} min`, f.etaMin != null && f.etaMin > 0 && f.etaMin < 120);

  // Un orage qui S'ÉLOIGNE n'a pas d'heure d'arrivée.
  const loin = C.foudreAutour([
    ...impacts({ n: 10, deDeg: 45, dKm: 15, ageMin: 22, graine: 3 }),
    ...impacts({ n: 10, deDeg: 45, dKm: 35, ageMin: 5, graine: 7 }),
  ], SITE.lat, SITE.lon, NOW);
  check('un orage qui s\'éloigne : pas d\'ETA', loin.etaMin === null, `${loin.nRecent} impacts, ${loin.vitesseKmh} km/h`);
  check('…mais il est quand même COMPTÉ et NOMMÉ', loin.nRecent >= 3 && loin.dKm != null);

  // SABOTAGE : un impact isolé n'est pas une cellule.
  const isole = C.foudreAutour(impacts({ n: 1, deDeg: 180, dKm: 45, ageMin: 3 }), SITE.lat, SITE.lon, NOW);
  check('SABOTAGE impact isolé : compté (1), mais ni tendance ni déplacement',
    isole.nRecent === 1 && isole.tendance === null && isole.vitesseKmh === null);
  check('…et le signal `lightning` pousserait dessus dès 1 impact — le composite, non',
    isole.nRecent > 0 && isole.nRecent < C.DEFAUTS.foudreMinImpacts);

  // SABOTAGE : une bouffée de rattrapage de flux donne une vitesse absurde.
  const bouffee = C.foudreAutour([
    ...impacts({ n: 8, deDeg: 225, dKm: 48, ageMin: 20, graine: 3 }),
    ...impacts({ n: 8, deDeg: 45, dKm: 48, ageMin: 2, graine: 9 }),
  ], SITE.lat, SITE.lon, NOW);
  check(`SABOTAGE bouffée de flux : ~380 km/h rejeté (vitesse null), pas publié comme un déplacement`,
    bouffee.vitesseKmh === null);
  check('…mais les impacts restent comptés', bouffee.nRecent === 8);
}

// ══════════════════════════════════════════════════════════════════════
section('2. La concordance — deux sources sur le MÊME créneau');
{
  const foudre = C.foudreAutour([
    ...impacts({ n: 6, deDeg: 225, dKm: 40, ageMin: 22, graine: 3 }),
    ...impacts({ n: 14, deDeg: 225, dKm: 30, ageMin: 5, graine: 7 }),
  ], SITE.lat, SITE.lon, NOW);

  const r3 = C.celluleConvective({ piaf: piafDit(25), rafale: rafaleDit(30), foudre }, NOW);
  console.log('    ', r3.resume, '·', JSON.stringify(r3.fenetreMin), '·', r3.accord.join('+'));
  check('trois sources qui se recoupent : niveau 3', r3.niveau === 3 && r3.detected);
  check(`ETA ${r3.etaMin} min — le MILIEU de l'intersection [${r3.fenetreMin}]`,
    r3.etaMin >= r3.fenetreMin[0] && r3.etaMin <= r3.fenetreMin[1]);
  check('chaque source est nommée dans le résumé',
    /pluie/.test(r3.resume) && /rafale/.test(r3.resume) && /foudre/.test(r3.resume));
  check('pas de désaccord', r3.desaccord === null);
  check('une attribution PAR SOURCE, jamais une phrase générique',
    r3.attributions.length === 3 && r3.attributions.some(a => /Licence Ouverte 2\.0/.test(a)) && r3.attributions.some(a => /Blitzortung/.test(a)));

  const r2 = C.celluleConvective({ piaf: piafDit(25), rafale: rafaleDit(30), foudre: C.foudreAutour([], SITE.lat, SITE.lon, NOW) }, NOW);
  check('deux sources d\'accord, la troisième muette : niveau 2, détecté', r2.niveau === 2 && r2.detected);
  check('…et la foudre est DISPONIBLE et silencieuse, pas absente',
    r2.sources.foudre.disponible === true && r2.sources.foudre.parle === false && r2.sources.foudre.refus === null);

  const r1 = C.celluleConvective({ piaf: piafDit(25), rafale: rafaleDit(null), foudre: C.foudreAutour([], SITE.lat, SITE.lon, NOW) }, NOW);
  check('une seule source qui parle : niveau 1, PAS détecté', r1.niveau === 1 && r1.detected === false);
  check('⛔ une source seule est déjà couverte par son propre signal — le composite n\'ajoute rien', r1.detected === false);
}

// ══════════════════════════════════════════════════════════════════════
section('3. ⛔ LE DÉSACCORD — deux sources, deux objets, et on le DIT');
//  Le cas d'Ouessant du lot 1, calculé : le 09/09 à 09:58 Z, le radar
//  disait « ETA 22 min » et PIAF « aside ». Deux sources qui parlent de
//  deux moments ne décrivent pas une cellule — elles en décrivent deux.
{
  const d = C.celluleConvective({ piaf: piafDit(10), rafale: rafaleDit(95), foudre: C.foudreAutour([], SITE.lat, SITE.lon, NOW) }, NOW);
  console.log('    ', JSON.stringify({ niveau: d.niveau, eta: d.etaMin, accord: d.accord, desaccord: d.desaccord }));
  check('pluie à 10 min et rafale à 95 min : niveau 1, PAS détecté', d.niveau === 1 && d.detected === false);
  check('…et le désaccord est NOMMÉ, pas tu', d.desaccord !== null && d.desaccord.sources.length === 1);
  check('il dit combien de minutes séparent les deux', Array.isArray(d.desaccord.ecartMin) && Math.abs(d.desaccord.ecartMin[0]) > 60);
  check('la phrase parle de DEUX OBJETS', /deux objets/.test(d.desaccord.dire));

  // ⛔⛔ LE SABOTAGE CENTRAL DU LOT. Un composite qui compterait les
  // sources sans regarder l'heure verrait DEUX sources actives, et
  // conclurait « cellule confirmée » sur deux phénomènes distincts
  // séparés d'une heure et demie.
  const naif = [piafDit(10), rafaleDit(95)].filter(x => x.hit || x.cellule).length;
  check('SABOTAGE compte de sources : un composite naïf dirait « 2 sources ⇒ cellule »',
    naif === 2 && d.detected === false,
    'c\'est exactement ce que la concordance temporelle empêche');

  // SABOTAGE : élargir les fenêtres jusqu'à tout faire concorder.
  const large = C.celluleConvective({ piaf: piafDit(10), rafale: rafaleDit(95), foudre: C.foudreAutour([], SITE.lat, SITE.lon, NOW) }, NOW,
    { fenetrePiafMin: 60, fenetreRafaleMin: 60 });
  check('SABOTAGE fenêtres à ±60 min : tout concorde, y compris ce qui n\'a rien à voir',
    large.niveau === 2 && large.detected === true,
    'les demi-largeurs sont des GRANULARITÉS, pas un réglage de sensibilité');

  // SABOTAGE : la moyenne des ETA au lieu du milieu de l'intersection.
  const r = C.celluleConvective({ piaf: piafDit(25), rafale: rafaleDit(35), foudre: C.foudreAutour([], SITE.lat, SITE.lon, NOW) }, NOW);
  const moyenne = (25 + 35) / 2;
  check(`SABOTAGE moyenne des ETA : ici elle vaut ${moyenne}, le milieu de l'intersection vaut ${r.etaMin} — et sur 10 et 90 la moyenne rendrait 50, un instant qu'aucune source n'a annoncé`,
    r.etaMin >= r.fenetreMin[0] && r.etaMin <= r.fenetreMin[1]);
}

// ══════════════════════════════════════════════════════════════════════
section('4. Les silences — une source coupée n\'est pas un ciel calme');
{
  const foudreVide = C.foudreAutour([], SITE.lat, SITE.lon, NOW);
  const rien = C.celluleConvective({ piaf: null, rafale: null, foudre: null }, NOW);
  check('aucune source disponible : refus nommé « sources-insuffisantes »',
    rien.refus === 'sources-insuffisantes' && rien.detected === false);
  check('⛔ et surtout PAS « rien détecté » — un silence n\'est pas un calme', rien.niveau === 0 && rien.refus !== null);

  const une = C.celluleConvective({ piaf: piafDit(25), rafale: null, foudre: null }, NOW);
  check('une seule source disponible : pas de composite possible, refus nommé', une.refus === 'sources-insuffisantes');

  const horsEmprise = C.celluleConvective({
    piaf: { refus: 'hors-emprise', hit: false, etaMin: null },
    rafale: { refus: 'hors-emprise', cellule: false, etaMin: null },
    foudre: foudreVide,
  }, NOW);
  check('deux refus + la foudre disponible : le composite tourne, et NOMME les refus',
    horsEmprise.refus === null && horsEmprise.sources.piaf.refus === 'hors-emprise' && horsEmprise.sources.rafale.refus === 'hors-emprise');
  check('…et il ne détecte rien, sans mentir sur pourquoi', horsEmprise.detected === false && horsEmprise.nParlantes === 0);

  const vieux = C.celluleConvective({
    piaf: { refus: 'passe-trop-vieille', hit: false, etaMin: null },
    rafale: rafaleDit(30), foudre: foudreVide,
  }, NOW);
  check('une passe périmée ne vote pas, mais son refus est publié',
    vieux.sources.piaf.parle === false && vieux.sources.piaf.refus === 'passe-trop-vieille' && vieux.niveau === 1);

  // SABOTAGE : confondre `disponible` et `parle`.
  check('SABOTAGE disponible ≠ parle : la foudre vide est disponible (true) et muette (false) — les confondre ferait passer un WebSocket coupé pour un ciel bleu',
    foudreVide.disponible === true && C.celluleConvective({ piaf: piafDit(25), rafale: rafaleDit(30), foudre: foudreVide }, NOW).sources.foudre.parle === false);
}

// ══════════════════════════════════════════════════════════════════════
section('5. L\'horizon et le coût');
{
  const foudreVide = C.foudreAutour([], SITE.lat, SITE.lon, NOW);
  const loin = C.celluleConvective({ piaf: piafDit(150), rafale: rafaleDit(155), foudre: foudreVide }, NOW);
  check(`au-delà de ${C.DEFAUTS.horizonMin} min, les sources ne votent plus`, loin.niveau === 0 && loin.detected === false);
  const dedans = C.celluleConvective({ piaf: piafDit(110), rafale: rafaleDit(115), foudre: foudreVide }, NOW);
  check('à 110 et 115 min, elles votent encore', dedans.niveau === 2 && dedans.detected);

  const buffer = Array.from({ length: 4000 }, (_, i) => ({
    lat: 43 + (i % 100) * 0.02, lon: 2 + (i % 97) * 0.02, t: NOW - (i % 90) * 60_000,
  }));
  const t0 = performance.now();
  for (let n = 0; n < 200; n++) {
    const f = C.foudreAutour(buffer, 43.1 + (n % 20) * 0.01, 2.5, NOW);
    C.celluleConvective({ piaf: piafDit(25), rafale: rafaleDit(30), foudre: f }, NOW);
  }
  const ms = performance.now() - t0;
  check(`200 sites (buffer de 4 000 impacts) en ${ms.toFixed(0)} ms (< 1 000)`, ms < 1000);
}

console.log(`\n══ ${ok} contrôles verts, ${ko} rouges ══`);
process.exit(ko ? 1 : 0);
