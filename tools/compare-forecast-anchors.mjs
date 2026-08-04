// ══════════════════════════════════════════════════════════════════
//  compare-forecast-anchors — combien le Δ PRÉVU change-t-il si on le
//  demande aux STATIONS plutôt qu'aux VILLES ?
//  (Lot 7, phase 3 — MESURE AVANT DÉCISION, 04/08/2026)
//
//  La question. `fetchFoehnDiffServer` demande à Open-Meteo la
//  pression MSL aux coordonnées des deux VILLES de l'axe. La fiche, et
//  désormais /phenomenon-delta, mesurent entre les deux STATIONS
//  d'ancrage. Deux couples de points différents : même en partageant
//  la physique, les deux Δ ne portent pas sur la même chose.
//
//  L'aligner paraît évident. Mais changer les points de mesure
//  RÉÉTALONNE tous les seuils curés d'un coup — un seuil de 2 hPa
//  calibré ville à ville ne veut plus la même chose station à station.
//  Sur un outil de sécurité, ça ne se fait pas à l'estime.
//
//  Ce script ne change RIEN. Il demande les deux séries et compare les
//  pics retenus, pour que la décision se prenne sur des chiffres.
//
//    node tools/compare-forecast-anchors.mjs
// ══════════════════════════════════════════════════════════════════
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, '..');
const P = createRequire(import.meta.url)(join(root, 'lib', 'pressure.cjs'));
const src = readFileSync(join(root, 'index.js'), 'utf8');
const OPEN_METEO_URL = src.match(/^const OPEN_METEO_URL = '([^']+)'/m)[1];
const HORIZON_MS = 36 * 3600 * 1000;

const env = {};
for (const line of readFileSync(join(root, '.env'), 'utf8').split('\n')) {
  const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)$/);
  if (m) env[m[1]] = m[2].trim().replace(/^["']|["']$/g, '');
}
const SB = { apikey: env.SUPABASE_SERVICE_KEY, Authorization: `Bearer ${env.SUPABASE_SERVICE_KEY}` };
const SERVEUR = process.env.BW_SERVER || 'https://balise-watch-server.onrender.com';

const j = async (u, o) => (await fetch(u, o)).json();

// Le référentiel, tel que le serveur le sert — donc exactement celui
// sur lequel /phenomenon-delta résout ses ancres.
const [ps, mf, ae, axes] = await Promise.all([
  j(`${SERVEUR}/pressure-stations`),
  j(`${SERVEUR}/meteofrance-stations`),
  j(`${SERVEUR}/aemet-stations`),
  j(`${env.SUPABASE_URL}/rest/v1/foehn_axes?select=*`, { headers: SB }),
]);
const referentiel = P.buildPressureReferential(ps.stations || [], mf.stations || [], ae.stations || []);
console.log(`\nRéférentiel : ${referentiel.length} stations de pression (${(ps.stations || []).length} METAR+SMN, ${(mf.stations || []).length} MF, ${(ae.stations || []).length} AEMET)`);

/** Δ prévu entre deux points quelconques, même requête que le serveur. */
async function diffEntre(aLat, aLon, bLat, bLon) {
  const url = `${OPEN_METEO_URL}?latitude=${aLat},${bLat}&longitude=${aLon},${bLon}`
    + `&hourly=pressure_msl&models=gfs_seamless&forecast_days=3&timezone=UTC`;
  try {
    const r = await j(url);
    if (!Array.isArray(r) || r.length < 2) return null;
    const times = (r[0]?.hourly?.time || []).map(t => new Date(`${t}Z`).getTime());
    const pa = r[0]?.hourly?.pressure_msl || [], pb = r[1]?.hourly?.pressure_msl || [];
    return { times, diff: times.map((_, i) => (pa[i] == null || pb[i] == null ? null : pa[i] - pb[i])) };
  } catch { return null; }
}

/** Pic retenu, mêmes règles que foehnServerPeak (sans le filtre pilote). */
function pic(d, ph) {
  if (!d) return null;
  const now = Date.now(), hi = now + HORIZON_MS;
  const allowNeg = ph.activeSign !== 'pos', allowPos = ph.activeSign !== 'neg';
  let best = null;
  for (let i = 0; i < d.times.length; i++) {
    const t = d.times[i], v = d.diff[i];
    if (v == null || t < now || t > hi) continue;
    if (v < 0 && !allowNeg) continue;
    if (v > 0 && !allowPos) continue;
    if (best === null || Math.abs(v) > Math.abs(best.diff)) best = { time: t, diff: v };
  }
  if (!best) return null;
  best.level = P.phenomenonLevel(best.diff, ph);
  return best;
}

const pad = (s, n) => String(s).padEnd(n).slice(0, n);
const rows = [];
let ancresOk = 0, sansAncre = 0;

for (const ax of axes.sort((a, b) => (a.label || '').localeCompare(b.label || '', 'fr'))) {
  const ph = P.phenomenonFromRow(ax);
  const anc = P.resolveAnchors(ph, referentiel);
  if (!anc.a || !anc.b) { sansAncre++; rows.push({ ph, sansAncre: true, anc }); continue; }
  ancresOk++;
  const [villes, stations] = await Promise.all([
    diffEntre(ax.a_lat, ax.a_lon, ax.b_lat, ax.b_lon),
    diffEntre(anc.a.station.lat, anc.a.station.lon, anc.b.station.lat, anc.b.station.lon),
  ]);

  // ── Le VRAI écart : convention de modèle contre convention de mesure
  // Δ MESURÉ maintenant (QFF de station, physique de la fiche) contre
  // Δ PRÉVU pour la même heure (MSLP de modèle). Déplacer les points ne
  // touche pas à cette différence-là.
  const stA = referentiel.find(s => s.id === anc.a.station.id);
  const stB = referentiel.find(s => s.id === anc.b.station.id);
  const ra = stA && P.readingFromStation(stA), rb = stB && P.readingFromStation(stB);
  const mesure = (ra && rb)
    ? P.pressureDelta(P.normalizePressure(ra), P.normalizePressure(rb)).delta
    : null;
  // Valeur prévue à l'heure la plus proche de maintenant.
  let prevuMaintenant = null;
  if (stations) {
    const now = Date.now();
    let meilleur = Infinity;
    for (let i = 0; i < stations.times.length; i++) {
      const e = Math.abs(stations.times[i] - now);
      if (e < meilleur && stations.diff[i] != null) { meilleur = e; prevuMaintenant = stations.diff[i]; }
    }
  }
  rows.push({ ph, anc, pv: pic(villes, ph), ps: pic(stations, ph), mesure, prevuMaintenant });
  await new Promise(r => setTimeout(r, 120));
}

console.log(`Ancres résolues sur ${ancresOk} axes ; ${sansAncre} sans station à portée.\n`);
console.log(`${pad('phénomène', 34)} ${pad('seuils', 7)} ${pad('Δ villes', 9)} ${pad('Δ stations', 10)} écart   niveau`);
console.log('─'.repeat(104));

let bascules = 0, ecarts = [];
for (const r of rows) {
  if (r.sansAncre) {
    console.log(`${pad(r.ph.label, 34)} ${pad(`${r.ph.thresholdHpa}/${r.ph.thresholdStrongHpa}`, 7)} — pas d'ancre (${r.anc.missing.length ? `déclarée introuvable : ${r.anc.missing.join(', ')}` : 'aucune station à portée'})`);
    continue;
  }
  const dv = r.pv ? r.pv.diff : null, ds = r.ps ? r.ps.diff : null;
  const lv = r.pv ? r.pv.level : 0, ls = r.ps ? r.ps.level : 0;
  const ecart = (dv != null && ds != null) ? ds - dv : null;
  if (ecart != null) ecarts.push(Math.abs(ecart));
  const bascule = lv !== ls;
  if (bascule) bascules++;
  console.log(
    `${pad(r.ph.label, 34)} ${pad(`${r.ph.thresholdHpa}/${r.ph.thresholdStrongHpa}`, 7)} ` +
    `${pad(dv == null ? '—' : dv.toFixed(2), 9)} ${pad(ds == null ? '—' : ds.toFixed(2), 10)} ` +
    `${pad(ecart == null ? '—' : (ecart >= 0 ? '+' : '') + ecart.toFixed(2), 7)} ` +
    `${lv} → ${ls}${bascule ? '   ⚠️ BASCULE' : ''}`,
  );
}

ecarts.sort((a, b) => a - b);
const med = ecarts.length ? ecarts[Math.floor(ecarts.length / 2)] : 0;
const max = ecarts.length ? ecarts[ecarts.length - 1] : 0;
const moy = ecarts.length ? ecarts.reduce((s, x) => s + x, 0) / ecarts.length : 0;

console.log('─'.repeat(104));
console.log(`\nÉcart |Δ stations − Δ villes| : médiane ${med.toFixed(2)} hPa, moyenne ${moy.toFixed(2)}, max ${max.toFixed(2)}.`);
console.log(`${bascules} phénomène(s) changeraient de NIVEAU aujourd'hui si on basculait sur les stations.`);
console.log('\nComment lire ça. Un écart petit devant les seuils (2 à 6 hPa) veut');
console.log('dire que basculer ne réétalonne PAS la curation, et que l\'alignement');
console.log('est gratuit. Un écart du même ordre que les seuils veut dire que les');
console.log('seuils curés ont été choisis pour les VILLES et qu\'il faudrait les');
console.log('revoir un par un avant de basculer — ce qui est un travail de');
console.log('curation, pas de code, et qui demande du retour de pilotes.');
// ══════════════════════════════════════════════════════════════════
//  L'écart QUI COMPTE : convention de modèle contre convention de mesure
// ══════════════════════════════════════════════════════════════════
console.log('\n\nÉCART ENTRE LE MESURÉ ET LE PRÉVU, À LA MÊME HEURE ET AUX MÊMES POINTS');
console.log('(le prévu est un MSLP de modèle, le mesuré un QFF de station —');
console.log(' déplacer les points ne touche pas à cette différence-là)\n');
console.log(`${pad('phénomène', 34)} ${pad('mesuré', 9)} ${pad('prévu', 9)} écart`);
console.log('─'.repeat(72));
const conv = [];
for (const r of rows) {
  if (r.sansAncre || r.mesure == null || r.prevuMaintenant == null) continue;
  const e = r.mesure - r.prevuMaintenant;
  conv.push(Math.abs(e));
  console.log(
    `${pad(r.ph.label, 34)} ${pad(r.mesure.toFixed(2), 9)} ${pad(r.prevuMaintenant.toFixed(2), 9)} ` +
    `${(e >= 0 ? '+' : '') + e.toFixed(2)}`,
  );
}
conv.sort((a, b) => a - b);
if (conv.length) {
  const m = conv[Math.floor(conv.length / 2)];
  console.log('─'.repeat(72));
  console.log(`\nÉcart |mesuré − prévu| : médiane ${m.toFixed(2)} hPa, max ${conv[conv.length - 1].toFixed(2)} hPa, sur ${conv.length} axes.`);
  console.log('\nÀ comparer aux seuils, qui vont de 2 à 6 hPa. Si cet écart-là est');
  console.log('du même ordre que les seuils, alors partager la physique ne suffit');
  console.log('pas : le prévu et le mesuré restent deux grandeurs différentes, et');
  console.log('la seule honnêteté est de les AFFICHER comme telles plutôt que de');
  console.log('prétendre les avoir réconciliées.');
}

console.log('\n⚠️ Un seul jour de mesure ne tranche rien : ce jour-ci est calme.');
console.log('   À relancer un jour de foehn avant de décider.\n');
