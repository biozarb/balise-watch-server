#!/usr/bin/env node
// ══════════════════════════════════════════════════════════════════════
//  banc_signaux_09-09.mjs — le registre des signaux est-il COMPLET ?
//  P1.1. Hors ligne. `node tools/banc_signaux_09-09.mjs`
//
//  Contrôles :
//   1. chaque `pref` du registre existe dans FW_DEFAULTS (index.js) ;
//   2. chaque `slug` a `flightwatch.settings.signals.<slug>.name` dans
//      les 8 locales du web ;
//   3. chaque signal appelé dans `evaluateFwSignal({ signal: '…' })` est
//      au registre, et réciproquement (sauf gust_front, table à part) ;
//   4. les copies client (`SIGNAL_SLUG*`) couvrent tous les signaux.
// ══════════════════════════════════════════════════════════════════════
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { createRequire } from 'node:module';

const ici = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const { SIGNAUX, COLONNES_PREFS } = require(join(ici, '..', 'lib', 'signaux.js'));
const index = readFileSync(join(ici, '..', 'index.js'), 'utf8');
const web = join(ici, '..', '..', 'web', 'src');

let ok = 0, ko = 0;
const check = (cond, msg) => { if (cond) { ok++; } else { ko++; console.log('  ✗', msg); } };

// 1. FW_DEFAULTS
const bloc = index.slice(index.indexOf('const FW_DEFAULTS'), index.indexOf('function fwPrefs'));
for (const c of COLONNES_PREFS) check(new RegExp(`\\b${c}\\s*:`).test(bloc), `FW_DEFAULTS sans ${c}`);

// 2. locales
const langs = ['fr', 'en', 'de', 'es', 'it', 'nl', 'pt', 'sl'];
for (const l of langs) {
  const p = join(web, 'locales', `${l}.json`);
  if (!existsSync(p)) { check(false, `locale ${l} introuvable`); continue; }
  const d = JSON.parse(readFileSync(p, 'utf8'));
  const s = d?.flightwatch?.settings?.signals ?? {};
  for (const [nom, def] of Object.entries(SIGNAUX)) check(typeof s[def.slug]?.name === 'string', `${l}.json sans flightwatch.settings.signals.${def.slug}.name (${nom})`);
}

// 3. appels ↔ registre
const appeles = new Set([...index.matchAll(/signal:\s*'([a-z_]+)'/g)].map(m => m[1]));
for (const s of appeles) check(!!SIGNAUX[s], `evaluateFwSignal appelé avec « ${s} », absent du registre`);
for (const s of Object.keys(SIGNAUX)) check(appeles.has(s) || s === 'gust_front' || s === 'convective_cell', `« ${s} » au registre mais jamais appelé`);

// 4. copies client
for (const f of ['components/watch/FlightModeView.tsx', 'contexts/AppContext.tsx', 'components/modals/ChartModal.tsx']) {
  const src = readFileSync(join(web, f), 'utf8');
  for (const [nom, def] of Object.entries(SIGNAUX)) check(src.includes(`${nom}: '${def.slug}'`), `${f} : SIGNAL_SLUG sans ${nom}`);
}

console.log(`\n${ok} contrôles verts, ${ko} rouges`);
process.exit(ko ? 1 : 0);
