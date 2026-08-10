// ═══════════════════════════════════════════════════════════════════
//  tools/gust-front-altitude-replay.js — étape 10 du lot H
//
//  Rejoue le détecteur de front DU DÉPÔT (`gfDetectModel`, aucune copie,
//  aucune réécriture) sur des grilles fabriquées par
//  `agrume/front_altitude.py`, une par niveau AGL, et met les résultats
//  côte à côte.
//
//  ── L'HYPOTHÈSE TESTÉE, EN UNE PHRASE ────────────────────────────────
//  « Le signal de front est plus propre au-dessus de la couche limite » —
//  donc le MÊME détecteur, sur le MÊME run et les MÊMES points, devrait
//  mieux ajuster son plan spatio-temporel à 1 000 m/sol qu'à 10 m.
//  Le juge est le R² du plan ; le reste (nombre de points, vitesse, cap)
//  est là pour empêcher de lire un R² hors de son contexte.
//
//  ⚠️ CE QUE CE REJEU NE DIT PAS. Le domaine du produit B fait
//  165 × 165 km : un R² mesuré ici n'est PAS comparable au R² ≈ 0,17-0,19
//  obtenu le 09/08 sur la France entière. Seule la colonne « 10 m »
//  contre la colonne « 1 000 m » du même tableau a un sens.
//
//  ⚠️ ET IL NE JUGE QUE LE RUN QU'ON LUI DONNE. Un R² sur une journée
//  sans front ne dit rien de la journée avec front : quand aucun point ne
//  franchit les seuils, ce tableau mesure l'absence d'événement, pas la
//  qualité du niveau.
//
//  Usage :
//      node tools/gust-front-altitude-replay.js /tmp/lot10/grid-*.json
// ═══════════════════════════════════════════════════════════════════

'use strict';

const fs = require('fs');
const path = require('path');
const { gfDetectModel } = require('../gust-front');

const files = process.argv.slice(2);
if (!files.length) {
  console.error('usage : node tools/gust-front-altitude-replay.js <grid-*.json…>');
  process.exit(2);
}

// Les deux variantes du verrou rafale. ⛔ La rafale n'existe qu'à 10 m :
// à 1 000 m elle vient forcément de la surface. Publier les deux évite
// qu'un écart de R² entre niveaux soit en réalité un écart de POPULATION
// de points candidats.
const VARIANTES = [
  { nom: 'verrou rafale ≥ 45 km/h', opts: {} },
  { nom: 'sans verrou rafale', opts: { gustMinKmh: 0 } },
];

const lignes = [];
for (const f of files) {
  const grid = JSON.parse(fs.readFileSync(f, 'utf8'));
  // `now` = l'instant du run. Toutes les échéances sont alors « à venir »,
  // donc les deux niveaux voient exactement la même fenêtre — ce que le
  // temps réel ne garantirait pas d'une exécution à l'autre.
  const now = Date.parse(grid.run);
  if (!Number.isFinite(now)) {
    console.error(`${f} : run illisible (${grid.run})`);
    process.exit(1);
  }
  for (const v of VARIANTES) {
    const t0 = Date.now();
    const res = gfDetectModel(grid, now, v.opts);
    const ms = Date.now() - t0;
    lignes.push({
      fichier: path.basename(f),
      niveau: grid.niveau_m_sol,
      variante: v.nom,
      candidats: res.front ? res.front.stationCount : (res.candidates || []).length,
      retenus: res.front ? res.front.stationCount : (res.count ?? 0),
      r2: res.front ? res.front.r2 : res.r2,
      vitesse: res.front ? res.front.speedKmh : null,
      cap: res.front ? res.front.bearing : null,
      type: res.front ? res.front.kind : null,
      raison: res.reason,
      ms,
    });
  }
}

const nb = (x, d = 2) => (x == null ? '—' : Number(x).toFixed(d));
const pad = (s, n) => String(s).padEnd(n);
const padL = (s, n) => String(s).padStart(n);

console.log('\nÉTAPE 10 — le même détecteur, deux niveaux\n');
console.log(pad('niveau', 10) + pad('variante', 24) + padL('candidats', 10) +
            padL('R²', 8) + padL('km/h', 8) + padL('cap', 6) + '  ' +
            pad('type', 12) + 'raison');
console.log('─'.repeat(96));
for (const l of lignes) {
  console.log(
    pad(`${l.niveau} m`, 10) + pad(l.variante, 24) + padL(l.candidats, 10) +
    padL(nb(l.r2, 3), 8) + padL(nb(l.vitesse, 0), 8) +
    padL(nb(l.cap, 0), 6) + '  ' + pad(l.type ?? '—', 12) +
    (l.raison ?? 'front annoncé'));
}

// ── La lecture, écrite ici plutôt que laissée au lecteur ─────────────
// ⚠️ Un tableau de R² se lit de travers avec une facilité déconcertante :
// `not_enough_stations` n'est PAS un R² faible, c'est l'absence d'un
// R². Les deux lignes ci-dessous existent pour qu'on ne confonde pas un
// détecteur qui refuse d'ajuster avec un détecteur qui ajuste mal.
console.log('');
const avecR2 = lignes.filter(l => l.r2 != null);
if (!avecR2.length) {
  console.log('⛔ AUCUN R² : aucune variante n\'a réuni les ' +
              'points nécessaires au plan spatio-temporel.');
  console.log('   Ce run ne dit donc RIEN sur le niveau — il dit qu\'il ' +
              'n\'y a pas d\'événement à ajuster.');
} else {
  for (const l of avecR2) {
    console.log(`  ${l.niveau} m / ${l.variante} : R² = ${nb(l.r2, 3)} ` +
                `sur ${l.retenus} points (${l.raison ?? 'front annoncé'})`);
  }
}
const parNiveau = new Map();
for (const l of lignes) {
  if (l.r2 == null) continue;
  const cle = l.variante;
  if (!parNiveau.has(cle)) parNiveau.set(cle, []);
  parNiveau.get(cle).push(l);
}
for (const [variante, ls] of parNiveau) {
  if (ls.length < 2) continue;
  const bas = ls.reduce((a, b) => (a.niveau <= b.niveau ? a : b));
  const haut = ls.reduce((a, b) => (a.niveau >= b.niveau ? a : b));
  const d = haut.r2 - bas.r2;
  console.log(`\n  ${variante} : R² ${nb(bas.r2, 3)} à ${bas.niveau} m → ` +
              `${nb(haut.r2, 3)} à ${haut.niveau} m (${d >= 0 ? '+' : ''}` +
              `${nb(d, 3)})`);
  // ⚠️ Un écart de R² entre deux populations de points différentes n'est
  // pas un écart de qualité d'ajustement. On le dit, on ne le corrige pas.
  if (bas.retenus !== haut.retenus) {
    console.log(`     ⚠️ populations différentes : ${bas.retenus} points ` +
                `contre ${haut.retenus} — l'écart de R² mélange la qualité ` +
                `du fit et le nombre de points ajustés.`);
  }
}
console.log('');

// ═══════════════════════════════════════════════════════════════════
//  Le balayage de seuil — sans lui, le tableau ci-dessus est ambigu
//
//  ⚠️ À 1 000 m/sol le vent est plus fort qu'à 10 m. Un seuil de saut
//  FIXÉ EN KM/H s'y franchit donc plus souvent, à organisation du champ
//  rigoureusement identique. Un « plus de points candidats en altitude »
//  lu sans ce balayage confondrait « le signal est mieux organisé » avec
//  « le vent est plus fort » — deux conclusions opposées pour le même
//  chiffre. C'est la leçon de l'étape 7 (écart absolu contre écart
//  relatif) appliquée telle quelle.
// ═══════════════════════════════════════════════════════════════════

function medianeVent(grid) {
  const v = [];
  for (const pas of grid.vars.spd) {
    for (const x of pas) if (x != null) v.push(x);
  }
  if (!v.length) return null;
  v.sort((a, b) => a - b);
  const m = v.length >> 1;
  return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
}

const SEUILS = [10, 15, 20, 25, 30, 40];
console.log('Balayage du seuil de saut de vent (verrou rafale retiré des deux côtés)\n');
const medianes = new Map();
for (const f of files) {
  const grid = JSON.parse(fs.readFileSync(f, 'utf8'));
  medianes.set(grid.niveau_m_sol, medianeVent(grid));
}
console.log('  |V| médian sur tout le champ : ' +
            [...medianes.entries()].map(([n, m]) => `${n} m → ${nb(m, 1)} km/h`).join('   '));
console.log('');
console.log(pad('niveau', 10) + SEUILS.map(s => padL(`Δ≥${s}`, 12)).join(''));
console.log('─'.repeat(10 + 12 * SEUILS.length));
for (const f of files) {
  const grid = JSON.parse(fs.readFileSync(f, 'utf8'));
  const now = Date.parse(grid.run);
  const cases = SEUILS.map(seuil => {
    const r = gfDetectModel(grid, now, { gustMinKmh: 0, dvMinKmh: seuil });
    const n = r.front ? r.front.stationCount : (r.candidates || []).length;
    const r2 = r.front ? r.front.r2 : r.r2;
    return padL(`${n}${r2 == null ? '' : ` / ${nb(r2, 2)}`}`, 12);
  });
  console.log(pad(`${grid.niveau_m_sol} m`, 10) + cases.join(''));
}
console.log('\n  lecture : « points candidats / R² » — le R² est absent quand ' +
            'le détecteur\n  refuse d\'ajuster (moins de 12 points), ce qui ' +
            'n\'est PAS un R² nul.\n');

// ═══════════════════════════════════════════════════════════════════
//  Le détail des cas où le détecteur AJUSTE — et l'étalement en temps
//
//  ⚠️ UN R² ÉLEVÉ NE SUFFIT PAS À DIRE « FRONT ». Le plan spatio-temporel
//  s'ajuste très bien sur n'importe quelle structure qui traverse le
//  domaine à vitesse à peu près constante — un cycle de brise de vallée
//  en fait partie, et il n'a rien d'un front. Ce qui sépare un épisode
//  d'un bruit corrélé, c'est le nombre d'HEURES DISTINCTES sur lesquelles
//  les points se répartissent : des points étalés sur toute la journée
//  sont du bruit, des points groupés sur quelques heures sont un passage.
//  On l'imprime donc systématiquement, à côté du R².
// ═══════════════════════════════════════════════════════════════════

function detail(points) {
  if (!points || !points.length) return null;
  const ts = points.map(p => p.t).sort((a, b) => a - b);
  const lats = points.map(p => p.lat), lons = points.map(p => p.lon);
  const dv = points.map(p => p.deltaSpeedKmh).filter(x => x != null).sort((a, b) => a - b);
  const dth = points.map(p => Math.abs(p.deltaHeadingDeg)).filter(x => x != null).sort((a, b) => a - b);
  return {
    n: points.length,
    etalementH: (ts[ts.length - 1] - ts[0]) / 3600000,
    heuresDistinctes: new Set(ts).size,
    lat: [Math.min(...lats), Math.max(...lats)],
    lon: [Math.min(...lons), Math.max(...lons)],
    dvMed: dv.length ? dv[dv.length >> 1] : null,
    dthMed: dth.length ? dth[dth.length >> 1] : null,
  };
}

console.log('Détail des ajustements, seuil de saut de vent balayé\n');
for (const f of files) {
  const grid = JSON.parse(fs.readFileSync(f, 'utf8'));
  const now = Date.parse(grid.run);
  for (const seuil of SEUILS) {
    const r = gfDetectModel(grid, now, { gustMinKmh: 0, dvMinKmh: seuil });
    const r2 = r.front ? r.front.r2 : r.r2;
    if (r2 == null) continue;
    const d = detail(r.front ? r.front._internal.used : r.candidates);
    const verdict = r.front
      ? `⛔ FRONT ANNONCÉ — ${nb(r.front.speedKmh, 0)} km/h, cap ` +
        `${nb(r.front.bearing, 0)}°, typé ${r.front.kind}, confiance ${r.front.confidence}`
      : `refusé (${r.reason})`;
    console.log(`  ${grid.niveau_m_sol} m, Δ≥${seuil} : R² = ${nb(r2, 3)} sur ${d.n} points`);
    console.log(`      ${verdict}`);
    console.log(`      étalés sur ${nb(d.etalementH, 1)} h / ${d.heuresDistinctes} ` +
                `heures distinctes, Δ|V| méd ${d.dvMed} km/h, Δθ méd ${Math.round(d.dthMed)}°`);
  }
}
console.log('');
