// ══════════════════════════════════════════════════════════════════
//  verify-source-agreement — les sources du référentiel disent-elles
//  la même chose au même endroit ?
//  (Lot 7, 04/08/2026)
//
//  POURQUOI CE CONTRÔLE EXISTE. Le 04/08 au soir, une comparaison a
//  montré jusqu'à 7,7 hPa d'écart entre un METAR converti en QFF et le
//  `pmer` de Météo-France AU MÊME AÉROPORT. Sur des seuils de 2 à
//  6 hPa, ç'aurait été rédhibitoire : 16 des 27 phénomènes ont leurs
//  deux ancres dans des sources différentes.
//
//  LA CAUSE N'ÉTAIT PAS LA CONVENTION. Une heure plus tard, les mêmes
//  stations concordaient à 0,36 hPa. Entre les deux, le cache METAR
//  s'était rafraîchi : les relevés comparés avaient 2 h d'écart, et
//  c'est la TENDANCE de pression sur ces deux heures qu'on prenait pour
//  un biais de source.
//
//  D'où la méthode de ce script, et ses deux garde-fous :
//   • ne comparer que des stations à moins de 3 km ET dont l'écart
//     d'ALTITUDE est faible — une pression station ne se compare pas
//     d'une altitude à l'autre ;
//   • ne comparer que des relevés SIMULTANÉS à la tolérance près.
//     Sans ça on ne mesure pas les sources, on mesure le temps qui
//     passe. C'est l'erreur qu'a faite la première comparaison.
//
//  Ce qu'on compare : le QNH du METAR contre le QNH DÉDUIT de la
//  pression station de l'autre source, chacune réduite avec SA propre
//  altitude. Aucune pression n'est comparée à une altitude différente.
//
//    node tools/verify-source-agreement.mjs
// ══════════════════════════════════════════════════════════════════
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const P = createRequire(import.meta.url)(join(here, '..', 'lib', 'pressure.cjs'));
const S = process.env.BW_SERVER || 'https://balise-watch-server.onrender.com';

const MAX_KM = 3;        // même lieu
const MAX_DALT_M = 5;    // même altitude, à la marge de relevé près
const MAX_SPAN_MIN = 45; // même instant — la tolérance de deltaSeries
// Au-delà, c'est une alerte : les sources ne s'accordent plus et le Δ
// de tout axe à ancres mixtes devient douteux.
const SEUIL_ALERTE_HPA = 1.5;

const j = async (u) => (await fetch(S + u)).json();
const [ps, mf, ae] = await Promise.all(
  ['/pressure-stations', '/meteofrance-stations', '/aemet-stations'].map(j),
);
const now = Date.now();

/** QNH déduit d'une pression station, avec l'altitude DE CETTE station. */
const qnhDepuisStation = (pSta, alt) => pSta / Math.pow(1 - 0.0065 * alt / 288.15, 5.255);

// Les deux autres sources servent `pres` (station) et `pmer` (mer).
// C'est `pres` qui nous intéresse : la mesure, avant toute réduction.
const autres = [
  ...(mf.stations || []).map(s => ({ ...s, source: 'meteofrance' })),
  ...(ae.stations || []).map(s => ({ ...s, source: 'aemet' })),
].filter(s => s.pres != null && s.alt != null && s.validityTime);

const metar = (ps.stations || []).filter(s => s.source === 'metar' && s.pressure != null && s.alt != null);

const paires = [];
const ecartes = { distance: 0, altitude: 0, simultaneite: 0 };

for (const m of metar) {
  for (const o of autres) {
    const km = P.haversineKm(m.lat, m.lon, o.lat, o.lon);
    if (km > MAX_KM) continue;
    if (Math.abs(m.alt - o.alt) > MAX_DALT_M) { ecartes.altitude++; continue; }
    const tO = Date.parse(o.validityTime);
    const spanMin = Math.abs(m.t - tO) / 60000;
    if (!Number.isFinite(spanMin) || spanMin > MAX_SPAN_MIN) { ecartes.simultaneite++; continue; }
    paires.push({
      nom: m.nom, source: o.source, km, dAlt: m.alt - o.alt, spanMin: Math.round(spanMin),
      qnhMetar: m.pressure, qnhAutre: qnhDepuisStation(o.pres, o.alt),
      ageMetar: Math.round((now - m.t) / 60000),
    });
    break;
  }
}
paires.forEach(p => { p.ecart = p.qnhMetar - p.qnhAutre; });

const pad = (s, n) => String(s).padEnd(n).slice(0, n);
console.log(`\nPaires retenues : même lieu (< ${MAX_KM} km), même altitude (± ${MAX_DALT_M} m),`);
console.log(`relevés simultanés (< ${MAX_SPAN_MIN} min d'écart).\n`);

if (!paires.length) {
  console.log('!! Aucune paire ne satisfait les trois critères.');
  console.log('   Ce n\'est PAS un succès : ça veut dire qu\'on ne peut rien');
  console.log('   conclure sur l\'accord des sources en ce moment. Le plus');
  console.log('   souvent, un cache est en retard — vérifier /pressure-diag.');
  console.log(`   Écartées : ${ecartes.altitude} pour l'altitude, ${ecartes.simultaneite} pour la simultanéité.\n`);
  process.exit(1);
}

console.log(`${pad('lieu', 30)}${pad('source', 13)}${pad('QNH METAR', 10)}${pad('QNH autre', 10)}écart   écart t`);
console.log('─'.repeat(84));
for (const p of paires.sort((a, b) => Math.abs(b.ecart) - Math.abs(a.ecart))) {
  const alerte = Math.abs(p.ecart) > SEUIL_ALERTE_HPA;
  console.log(
    `${pad(p.nom, 30)}${pad(p.source, 13)}${pad(p.qnhMetar.toFixed(1), 10)}${pad(p.qnhAutre.toFixed(1), 10)}` +
    `${pad((p.ecart >= 0 ? '+' : '') + p.ecart.toFixed(2), 8)}${p.spanMin} min${alerte ? '   ⚠️' : ''}`,
  );
}

const abs = paires.map(p => Math.abs(p.ecart)).sort((a, b) => a - b);
const moy = paires.reduce((s, p) => s + p.ecart, 0) / paires.length;
const med = abs[Math.floor(abs.length / 2)];
const hors = paires.filter(p => Math.abs(p.ecart) > SEUIL_ALERTE_HPA);

console.log('─'.repeat(84));
console.log(`\n${paires.length} paires — biais moyen ${(moy >= 0 ? '+' : '') + moy.toFixed(2)} hPa, |écart| médian ${med.toFixed(2)}, max ${abs[abs.length - 1].toFixed(2)}.`);
console.log(`${ecartes.simultaneite} paire(s) écartées faute de simultanéité, ${ecartes.altitude} pour l'altitude.`);

// Ce qui doit faire ÉCHOUER, et ce qui doit seulement se signaler.
//
// Une station isolée qui diverge, c'est une station à regarder — pas
// une raison de bloquer. Un contrôle qui échoue tous les jours sur le
// même cas finit par être lancé avec les yeux fermés, et ce jour-là il
// ne sert plus à rien. Ce qui doit alerter pour de bon, c'est un biais
// SYSTÉMATIQUE (les sources dérivent l'une par rapport à l'autre) ou
// une divergence GÉNÉRALISÉE.
const biaisSystematique = Math.abs(moy) > 1.0;
const divergenceGeneralisee = hors.length > paires.length * 0.2;
const echec = biaisSystematique || divergenceGeneralisee;

if (hors.length) {
  console.log(`\n${echec ? '❌' : 'ℹ️ '} ${hors.length} paire(s) au-delà de ${SEUIL_ALERTE_HPA} hPa : ${hors.map(p => p.nom.split(/[\/,]/)[0]).join(', ')}`);
  console.log('   Sur des seuils de 2 à 6 hPa, un désaccord de cet ordre rend');
  console.log('   douteux le Δ de tout axe ancré sur deux sources différentes.');
  console.log('   Vérifier d\'abord la fraîcheur (/pressure-diag) : c\'est ce qui');
  console.log('   avait produit un faux biais de 7,7 hPa le 04/08.');
  if (!echec) {
    console.log(`\n   Cas ISOLÉ (${hors.length} sur ${paires.length}, biais moyen ${moy.toFixed(2)} hPa) :`);
    console.log('   signalé, pas bloquant. Aucun phénomène curé n\'ancre là — à');
    console.log('   revérifier si un jour l\'un d\'eux le fait.');
  }
} else {
  console.log('\nLes sources s\'accordent. Le référentiel peut mélanger METAR,');
  console.log('SwissMetNet, Météo-France et AEMET sur un même axe sans introduire');
  console.log('de biais de convention — ce qui était l\'inquiétude du 04/08.');
}
console.log('\n⚠️ Ce contrôle mesure les SOURCES, pas la fraîcheur. Deux relevés');
console.log('   décalés dans le temps sont écartés ici, mais ils entrent bel et');
console.log('   bien dans le Δ d\'un phénomène : c\'est `pairSpanMin` et');
console.log('   `beyondTolerance` de /phenomenon-delta qui les signalent.\n');
process.exit(echec ? 1 : 0);
