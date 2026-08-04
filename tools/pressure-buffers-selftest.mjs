// ═══════════════════════════════════════════════════════════════════
// Selftest des buffers de pression — 04/08/2026
//
//   node tools/pressure-buffers-selftest.mjs
//
// Même esprit que gust-front-selftest.js : aucun réseau, aucune clé,
// aucun serveur à démarrer. Les fonctions testées sont EXTRAITES DU
// SOURCE RÉEL (index.js) et non recopiées ici — une copie ne testerait
// que la copie, et c'est exactement le genre de test qui reste vert
// pendant que la prod dérive.
//
// ── Ce qu'on protège ────────────────────────────────────────────────
// Le 04/08/2026 le buffer d'historique servait ~5 h au lieu de 30 h sur
// TOUTES les ancres, sans le moindre message d'erreur. Cause : l'API
// aviationweather plafonne le nombre total d'enregistrements d'une
// réponse (~400, mesuré) et, une fois le plafond atteint, rabote par le
// TEMPS au lieu d'échouer. Demander les 43 ancres en une requête à
// `hours=30` ne pouvait pas rendre 30 h.
//
// Mesures en direct qui fondent METAR_ROW_BUDGET, toutes à hours=30 :
//     2 ancres → 29,7 h ✅      20 ancres → 11,4 h ❌
//     6 ancres → 29,7 h ✅      43 ancres →  5,5 h ❌
// Et à hours=3 (régime de croisière), 20 ancres rendent bien 3 h — donc
// les 43 en une requête restent légitimes, ce que le test vérifie.
//
// Le vrai piège n'est pas la panne, c'est le silence : un Δ calculé sur
// une courbe tronquée reste un nombre plausible. Rien à l'écran ne le
// distingue d'un bon. D'où ce test.
// ═══════════════════════════════════════════════════════════════════
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ICI = dirname(fileURLToPath(import.meta.url));
const SRC = readFileSync(join(ICI, '..', 'index.js'), 'utf8');

/** Découpe une déclaration `function nom(...) { ... }` du source. */
function extraire(nom) {
  const i = SRC.indexOf(`function ${nom}(`);
  if (i < 0) throw new Error(`introuvable dans index.js : ${nom}`);
  let depth = 0;
  for (let k = SRC.indexOf('{', i); k < SRC.length; k++) {
    if (SRC[k] === '{') depth++;
    else if (SRC[k] === '}' && --depth === 0) return SRC.slice(i, k + 1);
  }
  throw new Error(`accolade non fermée : ${nom}`);
}

// Le budget est relu DANS le source lui aussi : si quelqu'un le change
// sans mesurer, les seuils ci-dessous doivent bouger avec.
const BUDGET = Number(/const METAR_ROW_BUDGET = (\d+)/.exec(SRC)?.[1]);
if (!Number.isFinite(BUDGET)) throw new Error('METAR_ROW_BUDGET introuvable dans index.js');

const NOMS = ['metarBatches', 'pressureHistoryPush', 'pressureHistorySpanH'];
const { metarBatches, pressureHistoryPush, pressureHistorySpanH } = new Function(
  `const METAR_ROW_BUDGET = ${BUDGET}; ${NOMS.map(extraire).join('\n')}
   return { ${NOMS.join(', ')} };`
)();

let ko = 0;
const ok = (cond, label, detail = '') => {
  console.log(`${cond ? '  ok  ' : '  KO  '} ${label}${detail ? ' — ' + detail : ''}`);
  if (!cond) ko++;
};

console.log(`\nSelftest buffers de pression (METAR_ROW_BUDGET = ${BUDGET})`);

console.log('\n1) Découpage en lots');
const A43 = Array.from({ length: 43 }, (_, i) => 'A' + i);
const croisiere = metarBatches(A43, 3);
const profond = metarBatches(A43, 30);
ok(croisiere.length === 1,
   'hours=3 : UNE seule requête — la croisière ne change pas', `${croisiere.length} lot(s)`);
ok(profond.length > 1,
   'hours=30 : découpé', `${profond.length} lots de ${profond.map(l => l.length).join(',')}`);
ok(profond.flat().length === A43.length && new Set(profond.flat()).size === A43.length,
   'aucune ancre perdue ni doublée par le découpage');
ok(profond.every(l => l.length * 30 * 2 <= BUDGET),
   'chaque lot tient dans le budget de lignes');
// 6 ancres × 30 h ont rendu 29,7 h en direct le 04/08 ; 20 n'ont rendu
// que 11,4 h. Un lot de plus de 6 sortirait de la zone MESURÉE.
ok(Math.max(...profond.map(l => l.length)) <= 6,
   'lot le plus gros dans la zone vérifiée en direct (≤ 6 ancres)');
// Garde-fou sur la croisière : 43 × 3 h × 2 doit rester sous le budget,
// sinon ajouter une ancre casserait silencieusement le poll de 20 min.
ok(A43.length * 3 * 2 <= BUDGET,
   'croisière : 43 ancres × 3 h tiennent dans le budget', `${A43.length * 3 * 2} lignes`);

console.log('\n2) Insertion dans le buffer');
const H = 3600000, now = Date.now(), m = new Map();
pressureHistoryPush(m, 'X', { t: now - 2 * H, p: 1010 }, 36 * H);
pressureHistoryPush(m, 'X', { t: now,         p: 1012 }, 36 * H);
pressureHistoryPush(m, 'X', { t: now - 1 * H, p: 1011 }, 36 * H); // hors ordre
ok(m.get('X').map(p => p.p).join() === '1010,1011,1012',
   'point inséré hors ordre reclassé par t');
pressureHistoryPush(m, 'X', { t: now - 1 * H, p: 999 }, 36 * H);  // doublon
ok(m.get('X').length === 3 && m.get('X')[1].p === 999,
   'doublon de t remplacé et non ajouté (les fenêtres se recouvrent d\'un poll à l\'autre)');
pressureHistoryPush(m, 'X', { t: now - 40 * H, p: 900 }, 36 * H); // hors rétention
ok(!m.get('X').some(p => p.p === 900),
   'point au-delà de la rétention élagué');

console.log('\n3) Étendue (la grandeur que surveille /pressure-diag)');
ok(Math.abs(pressureHistorySpanH(m, 'X') - 2) < 0.01,
   'étendue de X = 2 h', String(pressureHistorySpanH(m, 'X')));
ok(pressureHistorySpanH(m, 'ABSENTE') === null,
   'ancre absente → null, et surtout PAS 0 (0 se noierait dans une moyenne)');
const m1 = new Map();
pressureHistoryPush(m1, 'Y', { t: now, p: 1000 }, 36 * H);
ok(pressureHistorySpanH(m1, 'Y') === null,
   'point unique → null : un point n\'a pas d\'étendue');

console.log(ko ? `\n❌ ${ko} contrôle(s) en échec\n` : '\n✅ tout conforme\n');
process.exit(ko ? 1 : 0);
