// ══════════════════════════════════════════════════════════════════
//  Fabrique `perimetre/departements-fr.json` — les contours des 96
//  départements métropolitains, sous une forme faite pour être LUE au
//  démarrage du serveur et interrogée des milliers de fois par cycle.
//
//  ── POURQUOI UN FICHIER EMBARQUÉ, ET PAS UN SERVICE ──────────────
//  Même raison que `traces/perimetre/` (cf. backfill_packs.py) : le
//  détecteur de front tourne toutes les 6 min et doit pouvoir dire OÙ
//  est le front sans dépendre d'un tiers. Un géocodeur inverse (Photon,
//  Nominatim) serait une dépendance réseau, un quota, et une latence —
//  pour une question dont la réponse ne change jamais.
//
//  ── SOURCE ───────────────────────────────────────────────────────
//  https://github.com/gregoiredavid/france-geojson
//  `departements-version-simplifiee.geojson` — contours officiels IGN
//  (ADMIN-EXPRESS), redistribués. Licence ouverte / Etalab.
//  ⚠️ Version SIMPLIFIÉE volontairement : on répond à « quels
//  départements ce couloir traverse-t-il », pas à « ce point est-il du
//  bon côté de la limite ». La version pleine résolution pèse 7 Mo pour
//  une précision dont personne n'a l'usage ici.
//
//  ── CE QUE LE SCRIPT AJOUTE ──────────────────────────────────────
//  · coordonnées arrondies à 4 décimales (~11 m) ;
//  · une bbox par département — c'est elle qui fait tout le travail à
//    l'exécution : elle écarte 95 départements sur 96 avant le moindre
//    ray casting ;
//  · une structure plate (polys → rings) au lieu du Polygon /
//    MultiPolygon de GeoJSON, pour que le lecteur n'ait pas à
//    distinguer les deux cas à chaque appel.
//
//  Usage :
//    curl -sSL -o /tmp/dep.geojson \
//      https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements-version-simplifiee.geojson
//    node tools/build-departements.mjs /tmp/dep.geojson
// ══════════════════════════════════════════════════════════════════

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ICI = dirname(fileURLToPath(import.meta.url));
const SORTIE = resolve(ICI, '..', 'perimetre', 'departements-fr.json');

const src = process.argv[2];
if (!src) {
  console.error('usage : node tools/build-departements.mjs <departements-version-simplifiee.geojson>');
  process.exit(1);
}

const brut = JSON.parse(readFileSync(src, 'utf8'));
if (brut.type !== 'FeatureCollection') {
  console.error(`fichier inattendu : type = ${brut.type}`);
  process.exit(1);
}

const r4 = n => Math.round(n * 1e4) / 1e4;

const features = [];
for (const f of brut.features) {
  const code = f.properties?.code;
  const nom = f.properties?.nom;
  if (!code || !nom) { console.error(`feature sans code/nom, ignorée`); continue; }

  const g = f.geometry;
  // Polygon = un polygone (anneau extérieur + trous) ;
  // MultiPolygon = plusieurs. On aplatit vers la même forme.
  const polys = g.type === 'Polygon' ? [g.coordinates]
    : g.type === 'MultiPolygon' ? g.coordinates
      : null;
  if (!polys) { console.error(`${code} : géométrie ${g.type} non gérée`); continue; }

  let minLon = Infinity, minLat = Infinity, maxLon = -Infinity, maxLat = -Infinity;
  const propres = polys.map(poly => poly.map(ring => ring.map(([lon, lat]) => {
    const x = r4(lon), y = r4(lat);
    if (x < minLon) minLon = x;
    if (x > maxLon) maxLon = x;
    if (y < minLat) minLat = y;
    if (y > maxLat) maxLat = y;
    return [x, y];
  })));

  features.push({ code, nom, bbox: [minLon, minLat, maxLon, maxLat], polys: propres });
}

features.sort((a, b) => a.code.localeCompare(b.code));

const sortie = {
  _source: 'gregoiredavid/france-geojson — departements-version-simplifiee.geojson (contours IGN ADMIN-EXPRESS, Licence ouverte / Etalab)',
  _genere_par: 'tools/build-departements.mjs',
  _precision_deg: 1e-4,
  features,
};

mkdirSync(dirname(SORTIE), { recursive: true });
writeFileSync(SORTIE, JSON.stringify(sortie));

const points = features.reduce(
  (n, f) => n + f.polys.reduce((m, p) => m + p.reduce((k, r) => k + r.length, 0), 0), 0);
console.log(`${features.length} départements, ${points} points → ${SORTIE}`);
console.log(`${(readFileSync(SORTIE).length / 1024).toFixed(0)} Ko`);
