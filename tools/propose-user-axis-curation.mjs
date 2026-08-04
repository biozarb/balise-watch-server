// ══════════════════════════════════════════════════════════════════
//  propose-user-axis-curation — les axes créés par des pilotes n'ont
//  aucune curation, et le correctif du 04/08 ne les atteint donc pas.
//  (Lot 7, phase 4, 04/08/2026)
//
//  LE PROBLÈME. Huit axes de foehn_axes portent un `user_id` : ils ont
//  été créés depuis l'app, du temps où l'on pouvait tracer son propre
//  axe. Ils n'ont ni `station_a`/`station_b`, ni `threshold_hpa`, ni
//  `active_sign`. Ils retombent donc sur les replis 4/8/both — c'est
//  très exactement le comportement d'AVANT le correctif du 04/08, gardé
//  non pas par le code mais par l'absence de données. Cinq veilles
//  actives sont dessus, sur huit comptes différents.
//
//  CE QUE FAIT CE SCRIPT. Il propose, pour chaque axe utilisateur, le
//  phénomène CURÉ qui couvre le même couloir, et écrit un fichier .sql
//  d'héritage. Il ne décide rien : il rapproche et il argumente.
//
//  ⚠️ IL N'EXÉCUTE AUCUN SQL, ET N'ÉCRIT RIEN EN BASE. Le fichier
//  produit est à relire par Yann, puis à exécuter par lui dans l'éditeur
//  Supabase. C'est la règle du chantier, et elle vaut doublement ici :
//  ces lignes règlent le seuil d'alerte de pilotes réels.
//
//    node tools/propose-user-axis-curation.mjs
// ══════════════════════════════════════════════════════════════════
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');
const P = createRequire(import.meta.url)(join(root, 'lib', 'pressure.cjs'));

const env = {};
for (const line of readFileSync(join(root, '.env'), 'utf8').split('\n')) {
  const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)$/);
  if (m) env[m[1]] = m[2].trim().replace(/^["']|["']$/g, '');
}
const H = { apikey: env.SUPABASE_SERVICE_KEY, Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}` };
const get = async (q) => (await fetch(`${env.SUPABASE_URL}/rest/v1/${q}`, { headers: H })).json();

const axes = await get('foehn_axes?select=*');
const watches = await get('user_foehn_watch?select=axis_id,active');
const veilleurs = new Map();
for (const w of watches) if (w.active) veilleurs.set(w.axis_id, (veilleurs.get(w.axis_id) || 0) + 1);

const users = axes.filter(a => a.user_id);
const cures = axes.filter(a => !a.user_id);

/**
 * À quel point deux axes décrivent-ils le même écoulement ?
 *
 * On compare les deux extrémités, dans les DEUX sens : « Aoste –
 * Moutiers » et « Moutiers – Aoste » sont le même couloir décrit à
 * l'envers, et trois des huit axes utilisateurs sont dans ce cas. La
 * distance retenue est celle du meilleur appariement, et `flipped` dit
 * si le sens est inversé — ce qui INVERSE aussi le signe du Δ, donc
 * l'`active_sign` à hériter. Se tromper là-dessus reviendrait à
 * prévenir les pilotes du mauvais versant, c'est-à-dire à refaire le
 * bug qu'on vient de corriger.
 */
function proximite(u, c) {
  const d = (aLat, aLon, bLat, bLon) => P.haversineKm(aLat, aLon, bLat, bLon);
  const direct = Math.max(d(u.a_lat, u.a_lon, c.a_lat, c.a_lon), d(u.b_lat, u.b_lon, c.b_lat, c.b_lon));
  const inverse = Math.max(d(u.a_lat, u.a_lon, c.b_lat, c.b_lon), d(u.b_lat, u.b_lon, c.a_lat, c.a_lon));
  return direct <= inverse
    ? { km: direct, flipped: false }
    : { km: inverse, flipped: true };
}

/** Au-delà, on ne prétend pas que c'est le même couloir. */
const RAPPROCHEMENT_MAX_KM = 40;

const inverseSign = (s) => (s === 'neg' ? 'pos' : s === 'pos' ? 'neg' : 'both');

const lignes = [];
const sansMatch = [];

for (const u of users) {
  let best = null;
  for (const c of cures) {
    const p = proximite(u, c);
    if (!best || p.km < best.km) best = { ...p, c };
  }
  const n = veilleurs.get(u.id) || 0;
  if (!best || best.km > RAPPROCHEMENT_MAX_KM) { sansMatch.push({ u, best, n }); continue; }
  const ph = P.phenomenonFromRow(best.c);
  lignes.push({
    u, c: best.c, km: best.km, flipped: best.flipped, n,
    thresholdHpa: ph.thresholdHpa,
    thresholdStrongHpa: ph.thresholdStrongHpa,
    activeSign: best.flipped ? inverseSign(ph.activeSign) : ph.activeSign,
    kind: ph.kind,
  });
}

const pad = (s, n) => String(s).padEnd(n).slice(0, n);
console.log(`\n${users.length} axes utilisateurs, ${cures.length} phénomènes curés.\n`);
console.log(`${pad('axe utilisateur', 32)} ${pad('phénomène curé le plus proche', 36)} écart  sens  hérite  veille`);
console.log('─'.repeat(112));
for (const l of lignes) {
  console.log(
    `${pad(l.u.label, 32)} ${pad(l.c.label, 36)} ${pad(`${l.km.toFixed(0)} km`, 6)} ` +
    `${pad(l.flipped ? 'INVERSÉ' : 'direct', 7)} ${pad(`${l.thresholdHpa}/${l.thresholdStrongHpa} ${l.activeSign}`, 12)} ${l.n || '—'}`,
  );
}
for (const s of sansMatch) {
  // On nomme quand même le plus proche : « rien à moins de 40 km » ne
  // dit pas si on est à 41 ou à 200, et c'est toute la différence entre
  // « à vérifier » et « sans rapport ».
  console.log(
    `${pad(s.u.label, 32)} ${pad(s.best ? `(${s.best.c.label})` : '(aucun)', 36)} ` +
    `${pad(s.best ? `${s.best.km.toFixed(0)} km` : '', 6)} ${pad('TROP LOIN', 7)} ${pad('— à curer —', 12)} ${s.n || '—'}`,
  );
}

// ── Le fichier SQL, à relire puis exécuter par Yann ──────────────────
const sql = [];
sql.push('-- ═══════════════════════════════════════════════════════════════');
sql.push('-- Héritage de curation pour les axes créés par des pilotes');
sql.push('-- Lot 7, phase 4. GÉNÉRÉ par tools/propose-user-axis-curation.mjs');
sql.push('--');
sql.push('-- ⚠️ NE PAS EXÉCUTER PAR CLAUDE. À relire, puis à passer par Yann');
sql.push('--    dans l\'éditeur SQL Supabase.');
sql.push('--');
sql.push('-- CE QUE ÇA CHANGE, ET POUR QUI : ces huit axes tournent');
sql.push('-- aujourd\'hui sur les replis 4/8/both, c\'est-à-dire le');
sql.push('-- comportement d\'avant le correctif du 04/08 — fausses alertes de');
sql.push('-- versant comprises. Cinq d\'entre eux sont sous veille active.');
sql.push('--');
sql.push('-- CE QUE ÇA NE FAIT PAS : aucune ancre de pression n\'est');
sql.push('-- écrite. `resolveAnchors` apparie déjà ces axes par proximité,');
sql.push('-- et une ancre DÉCLARÉE engage un jugement que ce script n\'a pas');
sql.push('-- à prendre pour toi. On hérite du seuil et du sens, pas des');
sql.push('-- stations.');
sql.push('--');
sql.push('-- ⚠️ LES SENS INVERSÉS. Un axe saisi B→A porte un Δ de signe');
sql.push('-- opposé à celui du phénomène curé. L\'active_sign hérité est');
sql.push('-- donc INVERSÉ dans ces cas, et ils sont signalés ligne à ligne.');
sql.push('-- C\'est le point à relire en priorité : se tromper ici prévient');
sql.push('-- les pilotes du mauvais versant, exactement le bug corrigé le');
sql.push('-- 04/08.');
sql.push('-- ═══════════════════════════════════════════════════════════════');
sql.push('');
sql.push('begin;');
sql.push('');
for (const l of lignes) {
  sql.push(`-- ${l.u.label}`);
  sql.push(`--   hérite de : ${l.c.label}`);
  sql.push(`--   extrémités à ${l.km.toFixed(1)} km, sens ${l.flipped ? 'INVERSÉ (signe du Δ opposé)' : 'direct'}`);
  sql.push(`--   veilleurs actifs : ${l.n || 0}`);
  sql.push(`update public.foehn_axes set`);
  sql.push(`  threshold_hpa        = ${l.thresholdHpa},`);
  sql.push(`  threshold_strong_hpa = ${l.thresholdStrongHpa},`);
  sql.push(`  active_sign          = '${l.activeSign}',`);
  sql.push(`  kind                 = '${l.kind}'`);
  sql.push(`where id = '${l.u.id}';`);
  sql.push('');
}
if (sansMatch.length) {
  sql.push('-- ═══════════════════════════════════════════════════════════════');
  sql.push(`-- ${sansMatch.length} AXE(S) SANS ÉQUIVALENT CURÉ — RIEN N'EST PROPOSÉ POUR EUX.`);
  sql.push('--');
  sql.push('-- Leur extrémité la plus éloignée dépasse 40 km du phénomène curé');
  sql.push('-- le plus proche. Les vallées de Tarentaise et de Maurienne vers');
  sql.push('-- Aoste sont des couloirs LONGS, décrits de ville à ville par les');
  sql.push('-- pilotes, là où la curation décrit des cols. Ce ne sont pas les');
  sql.push('-- mêmes objets géométriques, et rapprocher à 55 ou 70 km');
  sql.push('-- reviendrait à DEVINER une curation — ce que la règle du');
  sql.push('-- chantier interdit (« Ne jamais les deviner »).');
  sql.push('--');
  sql.push('-- Ces axes gardent donc les replis 4/8/both, c\'est-à-dire le');
  sql.push('-- comportement d\'avant le correctif du 04/08. Trois d\'entre eux');
  sql.push('-- sont sous veille active. C\'est un arbitrage à prendre, pas un');
  sql.push('-- oubli :');
  sql.push('--   • les curer à la main (tu connais ces vallées) ;');
  sql.push('--   • ou décider d\'un défaut plus sûr que 4/8/both.');
  sql.push('--');
  for (const s of sansMatch) {
    sql.push(`--   ${s.u.label}  —  plus proche : ${s.best ? `${s.best.c.label} à ${s.best.km.toFixed(0)} km` : 'aucun'}  —  veilleurs : ${s.n || 0}`);
  }
  sql.push('-- ═══════════════════════════════════════════════════════════════');
  sql.push('');
}
sql.push('-- ── Vérification AVANT de valider ──────────────────────────────');
sql.push('select label, threshold_hpa, threshold_strong_hpa, active_sign, kind');
sql.push('from public.foehn_axes where user_id is not null order by label;');
sql.push('');
sql.push('-- commit;    -- ← à décommenter une fois la sélection relue');
sql.push('-- rollback;  -- ← en cas de doute, celui-ci');
sql.push('');

const cible = join(root, '..', 'web', 'supabase_lot7_user_axes_curation.sql');
writeFileSync(cible, sql.join('\n'), 'utf8');
console.log(`\nÉcrit : PWA/web/supabase_lot7_user_axes_curation.sql`);
console.log('⚠️  NE PAS EXÉCUTER PAR CLAUDE — à relire, puis à passer par Yann.');
console.log('    Le fichier ouvre une transaction et ne la valide PAS :');
console.log('    le commit est commenté, à décommenter après relecture.\n');
