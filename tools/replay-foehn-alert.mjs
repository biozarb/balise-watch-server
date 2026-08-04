// ══════════════════════════════════════════════════════════════════
//  replay-foehn-alert — rejoue la chaîne d'alerte foehn sur les VRAIS
//  axes, avec les VRAIES prévisions, et imprime le pic retenu.
//
//  Ce que ça prouve : que la chaîne Open-Meteo → pic → seuil → niveau
//  répond aujourd'hui, et QUELS axes partiraient en alerte. C'est le
//  seul moyen de constater quelque chose sans attendre un jour de
//  foehn.
//
//  Ce que ça NE prouve PAS, et qu'il ne faut pas lui faire dire :
//  qu'une notification arrive sur un téléphone. Le script s'arrête
//  AVANT evaluateFwSignal (anti-répétition, préférences, souscription
//  push). Un push reçu reste la seule preuve d'un push reçu.
//
//  ═══ LECTURE SEULE ═══
//  Aucune écriture Supabase, aucun push, aucune ligne d'alerte créée.
//  Deux lectures seulement : foehn_axes, et Open-Meteo.
//
//  `fetchFoehnDiffServer` et `foehnServerPeak` sont EXTRAITS du texte
//  d'index.js et évalués tels quels, comme dans verify-foehn-peak.mjs :
//  un script qui recopierait les fonctions ne testerait que la copie.
//  index.js n'est jamais chargé (le require démarrerait le serveur).
//
//  Usage :
//    node tools/replay-foehn-alert.mjs              # les 27 axes
//    node tools/replay-foehn-alert.mjs maurienne    # filtre sur label
//    node tools/replay-foehn-alert.mjs --gap        # kind contenant gap
// ══════════════════════════════════════════════════════════════════
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');
const src = readFileSync(join(root, 'index.js'), 'utf8');

// ── .env, lu à la main (pas de dépendance dotenv sur ce dépôt) ──────
// Les valeurs ne sont JAMAIS imprimées : SUPABASE_SERVICE_KEY contourne
// la RLS, elle n'a rien à faire dans une sortie qu'on colle ailleurs.
const env = {};
for (const line of readFileSync(join(root, '.env'), 'utf8').split('\n')) {
  const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)$/);
  if (m) env[m[1]] = m[2].trim().replace(/^["']|["']$/g, '');
}
const SB_URL = env.SUPABASE_URL, SB_KEY = env.SUPABASE_SERVICE_KEY;
if (!SB_URL || !SB_KEY) {
  console.error("!! SUPABASE_URL ou SUPABASE_SERVICE_KEY absent de .env");
  process.exit(1);
}

// ── Extraction des deux fonctions, sur le même principe que le harnais
const cut = (needle) => {
  const start = src.indexOf(needle);
  if (start < 0) { console.error(`!! ${needle} introuvable dans index.js`); process.exit(1); }
  return src.slice(start, src.indexOf('\n}\n', start) + 3); // 1re accolade en colonne 0
};
const constOf = (name) => {
  const m = src.match(new RegExp(`^const ${name}\\s*=\\s*([^;]+);`, 'm'));
  if (!m) { console.error(`!! constante ${name} introuvable`); process.exit(1); }
  return eval(m[1]);
};

const OPEN_METEO_URL = src.match(/^const OPEN_METEO_URL = '([^']+)'/m)[1];
const FOEHN_CACHE_TTL_MS = constOf('FOEHN_CACHE_TTL_MS');
const FOEHN_FORECAST_HORIZON_MS = constOf('FOEHN_FORECAST_HORIZON_MS');
const FOEHN_HPA_VALLEY = constOf('FOEHN_HPA_VALLEY');
const FOEHN_HPA_PLAIN = constOf('FOEHN_HPA_PLAIN');

const mk = (names, body, ret) => new Function(...names, `${body}; return ${ret};`);
const fetchFoehnDiffServer = mk(
  ['foehnDiffCache', 'FOEHN_CACHE_TTL_MS', 'OPEN_METEO_URL'],
  cut('async function fetchFoehnDiffServer'), 'fetchFoehnDiffServer',
)(new Map(), FOEHN_CACHE_TTL_MS, OPEN_METEO_URL);
// Depuis le lot 7, foehnServerPeak appelle la règle de niveau de la
// fiche : on lui injecte le vrai module partagé.
const PRESSURE = createRequire(import.meta.url)(join(root, 'lib', 'pressure.cjs'));
const foehnServerPeak = mk(
  ['FOEHN_FORECAST_HORIZON_MS', 'PRESSURE'],
  cut('function foehnServerPeak'), 'foehnServerPeak',
)(FOEHN_FORECAST_HORIZON_MS, PRESSURE);

// ── La règle d'AVANT le 04/08, pour mesurer ce que le correctif change.
// ⚠️ Ce n'est PAS une deuxième version de la règle vivante : ce code a
// été SUPPRIMÉ d'index.js, il ne subsiste ici que comme témoin
// historique. S'il diverge, il n'y a rien à resynchroniser — c'est le
// passé. Ne jamais s'en servir pour décider d'une alerte.
function peakAncienneRegle(d, threshold, wantDir = 'both') {
  const now = Date.now(), hi = now + FOEHN_FORECAST_HORIZON_MS;
  let best = null;
  for (let i = 0; i < d.times.length; i++) {
    const t = d.times[i], v = d.diff[i];
    if (v == null || t < now || t > hi) continue;
    if (wantDir === 'toA' && v >= 0) continue;
    if (wantDir === 'toB' && v <= 0) continue;
    if (best === null || Math.abs(v) > Math.abs(best.diff)) best = { time: t, diff: v };
  }
  if (!best) return null;
  const mag = Math.abs(best.diff);
  best.level = mag >= FOEHN_HPA_PLAIN ? 3 : mag >= threshold ? 2 : 0;
  return best;
}

// ── Lecture des axes ────────────────────────────────────────────────
const arg = process.argv.slice(2).filter(a => a !== '--gap').join(' ').toLowerCase();
const gapOnly = process.argv.includes('--gap');

const r = await fetch(`${SB_URL}/rest/v1/foehn_axes?select=*`, {
  headers: { apikey: SB_KEY, Authorization: `Bearer ${SB_KEY}` },
});
let axes = await r.json();
if (!Array.isArray(axes)) { console.error('!! réponse Supabase inattendue'); process.exit(1); }
if (arg) axes = axes.filter(a => (a.label || '').toLowerCase().includes(arg));
if (gapOnly) axes = axes.filter(a => (a.kind || '').includes('gap'));
axes.sort((a, b) => (a.label || '').localeCompare(b.label || '', 'fr'));

if (!axes.length) { console.error('!! aucun axe ne correspond'); process.exit(1); }

const hhmm = (t) => new Date(t).toLocaleString('fr-FR', {
  weekday: 'short', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Paris',
});
const pad = (s, n) => String(s).padEnd(n).slice(0, n);

console.log(`\nRejeu du ${new Date().toLocaleString('fr-FR')} — ${axes.length} axe(s), fenêtre ${FOEHN_FORECAST_HORIZON_MS / 3600e3} h, GFS via Open-Meteo`);
console.log('LECTURE SEULE : aucun push, aucune écriture.\n');

let alertes = 0, changes = 0, muets = 0, morts = 0;
const lignes = [];

for (const ax of axes) {
  const dd = await fetchFoehnDiffServer(ax);
  if (!dd || !dd.times?.length) {
    console.log(`  ×  ${pad(ax.label, 34)} — pas de données Open-Meteo`);
    morts++;
    continue;
  }
  // Mêmes valeurs que le poll : seuil du phénomène (le seuil du compte
  // n'existe pas ici, on rejoue l'axe, pas un abonné), et active_sign.
  // Mapping par la fonction de la fiche : les replis de seuil sont
  // appliqués une seule fois, au même endroit, pour les deux moitiés.
  const ph = PRESSURE.phenomenonFromRow(ax);
  const thr = ph.thresholdHpa, strong = ph.thresholdStrongHpa;
  const p = foehnServerPeak(dd, ph, 'both');
  const avant = peakAncienneRegle(dd, FOEHN_HPA_VALLEY, 'both'); // repli global d'avant

  const lvl = p ? p.level : 0;
  const lvlAvant = avant ? avant.level : 0;
  const change = lvl !== lvlAvant;
  if (lvl >= 2) alertes++; else muets++;
  if (change) changes++;

  // Pourquoi le niveau a changé. Sans ça le tableau se lit à l'envers :
  // un « avant : niv 2 » devenu 0 ressemble à une alerte perdue, alors
  // que c'est le plus souvent une alerte qui partait sur le MAUVAIS
  // versant — Südföhn annoncé aux pilotes du Nordföhn, et l'inverse.
  let raison = '';
  if (change) {
    const sign = ph.activeSign;
    const versantInterdit = avant && ((avant.diff < 0 && sign === 'pos') || (avant.diff > 0 && sign === 'neg'));
    if (lvl < lvlAvant) {
      raison = versantInterdit
        ? 'fausse alerte supprimée (mauvais versant)'
        : `seuil du phénomène (${thr}) au lieu du global (${FOEHN_HPA_VALLEY})`;
    } else {
      raison = 'ARMÉ par le correctif (était sous-armé)';
    }
    if (lvl === 3 && lvlAvant === 2) raison = `niveau 3 sur ${strong} au lieu de ${FOEHN_HPA_PLAIN}`;
  }

  const marque = lvl >= 3 ? '!!!' : lvl >= 2 ? ' ! ' : '   ';
  const dPart = p ? `${p.diff >= 0 ? '+' : ''}${p.diff.toFixed(1)} hPa ${hhmm(p.time)}` : 'aucun pic retenu';
  lignes.push(
    `${marque}${pad(ax.label, 34)} ${pad(`${thr}/${strong}`, 7)} ${pad(ph.activeSign, 5)} ` +
    `niv ${lvl}  ${pad(dPart, 30)}${change ? `  ← niv ${lvlAvant} avant : ${raison}` : ''}`,
  );
  await new Promise(res => setTimeout(res, 150)); // courtoisie Open-Meteo
}

console.log(`${pad('', 3)}${pad('axe', 34)} ${pad('seuils', 7)} ${pad('sign', 5)} niveau  pic prévu`);
console.log('─'.repeat(104));
lignes.forEach(l => console.log(l));
console.log('─'.repeat(104));
console.log(`\n${alertes} axe(s) en alerte (niveau ≥ 2), ${muets} sous le seuil, ${morts} sans données.`);
console.log(`${changes} axe(s) où le correctif du 04/08 change le niveau.`);
console.log('\n⚠️  « sous le seuil » ne veut PAS dire « pas de vent ». Tous ces');
console.log('    vents sont un DANGER pour un parapentiste — vent fort, rafales,');
console.log('    rotors. Ce tableau dit ce que le serveur ALERTE, pas ce qu\'il');
console.log('    fait beau.\n');
