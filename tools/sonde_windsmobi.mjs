#!/usr/bin/env node
// ═══════════════════════════════════════════════════════════════════
//  sonde_windsmobi.mjs — que ramène VRAIMENT le collecteur winds.mobi ?
// ═══════════════════════════════════════════════════════════════════
//
//  MESURE, PAS DÉCISION. Même esprit que sonde_r2.py / sonde_cadence.py
//  côté model-verif : rejouer à l'identique les filtres du collecteur
//  (boîte géographique, garde-fraîcheur, dédoublonnage 180 m) sur la
//  VRAIE donnée, et rendre les chiffres — plutôt que de croire sur
//  parole une constante écrite dans index.js.
//
//  Ce qu'elle NE vérifie PAS, et qu'il ne faut pas lui faire dire :
//  elle réplique la logique, elle ne l'importe pas. Si quelqu'un change
//  WINDSMOBI_BOX dans index.js sans toucher ce fichier, la sonde
//  continuera d'afficher des chiffres justes… pour l'ancienne boîte.
//  C'est le prix d'un index.js non modulaire ; le dire vaut mieux que
//  de laisser croire à une garantie.
//
//  Usage :  node tools/sonde_windsmobi.mjs
//           node tools/sonde_windsmobi.mjs --serveur https://…  (défaut : prod)

const SERVEUR = (() => {
  const i = process.argv.indexOf('--serveur');
  return i > -1 ? process.argv[i + 1] : 'https://balise-watch-server.onrender.com';
})();

const UA = 'balise-watch.app (biozarb@gmail.com)';
const API = 'https://winds.mobi/api/2';
const PIOU = 'https://api.pioupiou.fr/v1/live-with-meta/all';

// ⚠️ Copies des constantes d'index.js — cf. l'avertissement en tête.
const PROVIDERS_FAST = ['holfuy', 'ffvl'];
const PROVIDERS_SLOW = [
  'slf', 'meteoswiss', 'windspots', 'aletsch', 'windball', 'windline',
  'iweathar', 'pgsonda', 'gxaircom', 'pdcs', 'yvbeach', 'thunerwetter',
  'kachelmannwetter', 'wunderground',
];
const BOX = { latMin: 41.2, latMax: 51.6, lonMin: -5.5, lonMax: 10.2 };
const MAX_AGE_MS = 60 * 60 * 1000;
const DEDUP_M = 180;

function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371, toRad = d => d * Math.PI / 180;
  const dLat = toRad(lat2 - lat1), dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

async function j(url, headers) {
  const r = await fetch(url, headers ? { headers } : undefined);
  if (!r.ok) throw new Error(`HTTP ${r.status} sur ${url}`);
  return r.json();
}

// ── Le référentiel « ce que l'app connaît déjà » ───────────────────
// Six sources, exactement celles de windsmobiKnownGrid().
async function referentiel() {
  const pts = [];
  const push = (lat, lon) => { if (Number.isFinite(lat) && Number.isFinite(lon)) pts.push([lat, lon]); };
  const compte = {};
  const piou = await j(PIOU);
  (piou.data || []).forEach(b => push(b.location?.latitude, b.location?.longitude));
  compte.pioupiou = pts.length;
  for (const [route, nom] of [
    ['/meteofrance-stations', 'meteofrance'],
    ['/aemet-stations', 'aemet'],
    ['/infoclimat-stations', 'infoclimat'],
    ['/pressure-stations', 'metar+smn'],
  ]) {
    const avant = pts.length;
    try {
      const d = await j(`${SERVEUR}${route}`);
      (d.stations ?? d).forEach(s => push(s.lat, s.lon));
    } catch (e) {
      console.error(`  ⚠️ ${route} injoignable (${e.message}) — le référentiel est INCOMPLET, les « nouvelles » seront surestimées`);
    }
    compte[nom] = pts.length - avant;
  }
  return { pts, compte };
}

// Même grille 0,1° que le collecteur : ce n'est pas une optimisation
// cosmétique, c'est ce qui rend le test praticable sur ~3 000 points.
function grille(pts) {
  const g = new Map();
  for (const [lat, lon] of pts) {
    const k = `${Math.round(lat * 10)},${Math.round(lon * 10)}`;
    if (!g.has(k)) g.set(k, []);
    g.get(k).push([lat, lon]);
  }
  return g;
}

function estDoublon(g, lat, lon) {
  const cl = Math.round(lat * 10), co = Math.round(lon * 10);
  for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) {
    for (const [kl, ko] of g.get(`${cl + a},${co + b}`) ?? []) {
      if (haversineKm(lat, lon, kl, ko) * 1000 < DEDUP_M) return true;
    }
  }
  return false;
}

const mediane = xs => { const s = [...xs].sort((a, b) => a - b); return s.length ? s[s.length >> 1] : NaN; };

(async () => {
  console.log(`Sonde winds.mobi — serveur de référence : ${SERVEUR}\n`);

  const { pts, compte } = await referentiel();
  console.log('Référentiel de dédoublonnage (ce que l\'app connaît déjà) :');
  for (const [k, v] of Object.entries(compte)) console.log(`   ${k.padEnd(14)} ${String(v).padStart(5)}`);
  console.log(`   ${'TOTAL'.padEnd(14)} ${String(pts.length).padStart(5)}\n`);
  const g = grille(pts);

  const now = Date.now();
  let totalRetenu = 0, totalDoublon = 0, totalVieux = 0, totalSansVent = 0;
  console.log(`${'réseau'.padEnd(18)}${'boîte'.padStart(7)}${'doublon'.padStart(9)}${'périmé'.padStart(8)}${'s.vent'.padStart(8)}${'RETENU'.padStart(8)}${'âge méd.'.padStart(10)}`);

  for (const p of [...PROVIDERS_FAST, ...PROVIDERS_SLOW]) {
    let rows;
    try {
      rows = await j(`${API}/stations/?provider=${p}&limit=0`, { 'user-agent': UA });
    } catch (e) { console.log(`${p.padEnd(18)}  ERREUR ${e.message}`); continue; }

    let boite = 0, dbl = 0, vieux = 0, sansVent = 0, retenu = 0;
    const ages = [];
    for (const s of rows) {
      const c = s?.loc?.coordinates;
      if (!Array.isArray(c) || c.length < 2) continue;
      const [lon, lat] = c;
      if (lat < BOX.latMin || lat > BOX.latMax || lon < BOX.lonMin || lon > BOX.lonMax) continue;
      if (s.status === 'red' || s.status === 'hidden') continue;
      boite++;
      const last = s.last;
      if (!last || !Number.isFinite(last._id) || last['w-avg'] == null) { sansVent++; continue; }
      if (estDoublon(g, lat, lon)) { dbl++; continue; }
      const age = now - last._id * 1000;
      if (age > MAX_AGE_MS) { vieux++; continue; }
      ages.push(age);
      retenu++;
    }
    totalRetenu += retenu; totalDoublon += dbl; totalVieux += vieux; totalSansVent += sansVent;
    const am = ages.length ? (mediane(ages) / 60000).toFixed(1) + ' min' : '—';
    console.log(`${p.padEnd(18)}${String(boite).padStart(7)}${String(dbl).padStart(9)}${String(vieux).padStart(8)}${String(sansVent).padStart(8)}${String(retenu).padStart(8)}${am.padStart(10)}`);
  }

  console.log(`\n${'TOTAL'.padEnd(18)}${''.padStart(7)}${String(totalDoublon).padStart(9)}${String(totalVieux).padStart(8)}${String(totalSansVent).padStart(8)}${String(totalRetenu).padStart(8)}`);
  console.log(`\n${totalRetenu} balises entreraient dans \`releves\`.`);
  console.log(`${totalDoublon} écartées comme doublons — si ce nombre tombe à 0, le référentiel n'a pas été chargé : suspecter le serveur, pas winds.mobi.`);

  // Contrôle d'unité : winds.mobi doit rendre des km/h, comme Pioupiou.
  // Vérifié en comparant une balise Pioupiou vue des deux côtés, à
  // horodatage IDENTIQUE (sinon on compare deux instants, pas deux
  // conventions). Silencieux si aucune paire simultanée n'est trouvée.
  try {
    const piou = await j(PIOU);
    const avecVent = (piou.data || []).filter(b => b.measurements?.wind_speed_avg != null).slice(0, 40);
    const ids = avecVent.map(b => `ids=pioupiou-${b.id}`).join('&');
    const wm = await j(`${API}/stations/?${ids}`, { 'user-agent': UA });
    const parId = new Map(wm.map(s => [s._id, s]));
    let paires = 0, ecarts = 0;
    for (const b of avecVent) {
      const s = parId.get(`pioupiou-${b.id}`);
      if (!s?.last) continue;
      if (Math.abs(Date.parse(b.measurements.date) - s.last._id * 1000) > 1000) continue;
      paires++;
      if (Math.abs(b.measurements.wind_speed_avg - s.last['w-avg']) > 0.6) ecarts++;
    }
    if (!paires) console.log('\nContrôle d\'unité : aucune paire simultanée trouvée, non concluant.');
    else if (ecarts) console.log(`\n⛔ CONTRÔLE D'UNITÉ ÉCHOUÉ : ${ecarts}/${paires} paires divergent — winds.mobi ne sert peut-être plus des km/h.`);
    else console.log(`\n✅ Contrôle d'unité : ${paires} paires simultanées, vent identique au dixième. winds.mobi est bien en km/h.`);
  } catch { /* le contrôle d'unité est un bonus, jamais un bloquant */ }
})();
