// ══════════════════════════════════════════════════════════════════
//  departements.js — « ce point est dans quel département ? », et
//  surtout « ce couloir traverse quels départements ? ».
//
//  ── POURQUOI CE MODULE EXISTE (31/08/2026) ───────────────────────
//  Retour Yann : « quand on annonce un front, on crée une alerte qui
//  est sur la France mais qui ne dit pas où. Beaucoup de pilotes
//  pensent que c'est proche d'eux, mais ne le voient pas. »
//
//  Le bandeau de front de rafales annonçait une nature, une heure et
//  une rafale — jamais un lieu. Un pilote ne pouvait donc pas décider
//  en un coup d'œil si ça le concernait, et devait ouvrir la carte pour
//  le savoir. Ce module fournit la seule information qui manquait, et
//  dans le vocabulaire que les pilotes emploient entre eux : le NUMÉRO
//  de département.
//
//  ── CE QU'ON CALCULE, ET CE QU'ON NE CALCULE PAS ─────────────────
//  On répond sur le COULOIR D'IMPACT (la ligne de front actuelle
//  extrudée sur 3 h de trajet), pas sur les stations qui ont détecté le
//  passage. Les stations disent où le front EST PASSÉ ; le couloir dit
//  où il VA. À la question « est-ce que ça me concerne ? », c'est la
//  seconde qui répond.
//
//  ── PRÉCISION ────────────────────────────────────────────────────
//  Contours IGN SIMPLIFIÉS (~11 m d'arrondi, mais des limites lissées à
//  l'échelle du km). C'est délibéré : la question est « le couloir
//  touche-t-il l'Isère ? », pas « ce point précis est-il isérois ? ».
//  Un couloir fait des dizaines de kilomètres de large ; une limite
//  départementale approchée au kilomètre ne change aucun résultat.
//  ⚠️ Ne pas réutiliser ce module pour un usage qui exigerait la limite
//  exacte (fiscalité, réglementation, espace aérien).
// ══════════════════════════════════════════════════════════════════

'use strict';

const { readFileSync } = require('node:fs');
const path = require('node:path');

const FICHIER = path.join(__dirname, 'perimetre', 'departements-fr.json');

/** Chargé au PREMIER appel et jamais rechargé. 246 Ko de JSON, ~14 000
 *  points : le lire au démarrage retarderait le boot pour une donnée
 *  dont on n'a besoin que s'il y a un front. */
let _deps = null;
let _erreur = null;

function charger() {
  if (_deps || _erreur) return _deps;
  try {
    const brut = JSON.parse(readFileSync(FICHIER, 'utf8'));
    _deps = Array.isArray(brut?.features) ? brut.features : [];
    if (!_deps.length) throw new Error('fichier vide');
  } catch (e) {
    // Panne assumée SILENCIEUSE côté pilote : sans contours, le bandeau
    // s'affiche comme avant, sans départements. Une alerte de front
    // sans son numéro de département reste une alerte utile ; refuser
    // d'alerter parce qu'un fichier manque ne le serait pas.
    _erreur = e.message;
    _deps = [];
    console.error(`départements : contours illisibles (${e.message}) — les fronts s'afficheront sans numéro`);
  }
  return _deps;
}

/** Diagnostic, pour /gust-front/health. */
function departementsCharges() {
  charger();
  return { count: _deps.length, error: _erreur };
}

/** Ray casting sur un anneau [lon, lat]. Un point exactement sur une
 *  arête tombe d'un côté arbitraire — sans conséquence ici, cf. l'en-tête. */
function dansAnneau(lon, lat, anneau) {
  let dedans = false;
  for (let i = 0, j = anneau.length - 1; i < anneau.length; j = i++) {
    const [xi, yi] = anneau[i];
    const [xj, yj] = anneau[j];
    if ((yi > lat) !== (yj > lat)
      && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) dedans = !dedans;
  }
  return dedans;
}

/** Un polygone = anneau extérieur + trous (enclaves). */
function dansPolygone(lon, lat, rings) {
  if (!dansAnneau(lon, lat, rings[0])) return false;
  for (let k = 1; k < rings.length; k++) {
    if (dansAnneau(lon, lat, rings[k])) return false;
  }
  return true;
}

/**
 * Département contenant un point, ou null (mer, étranger, contours
 * indisponibles).
 *
 * La bbox fait tout le travail : elle écarte 95 départements sur 96
 * avant le premier ray casting, ce qui rend l'appel assez bon marché
 * pour être fait quelques milliers de fois par cycle de détection.
 */
function departementAt(lat, lon) {
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  for (const d of charger()) {
    const [minLon, minLat, maxLon, maxLat] = d.bbox;
    if (lon < minLon || lon > maxLon || lat < minLat || lat > maxLat) continue;
    for (const polys of d.polys) {
      if (dansPolygone(lon, lat, polys)) return { code: d.code, nom: d.nom };
    }
  }
  return null;
}

const KM_PAR_DEG_LAT = 111.32;

/** Enveloppe d'un anneau [lon, lat]. */
function bboxDe(ring) {
  let minLon = Infinity, minLat = Infinity, maxLon = -Infinity, maxLat = -Infinity;
  for (const [lon, lat] of ring) {
    if (lon < minLon) minLon = lon;
    if (lon > maxLon) maxLon = lon;
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
  }
  return [minLon, minLat, maxLon, maxLat];
}

/** Points régulièrement espacés le long du contour d'un anneau. */
function pointsDuContour(ring, pasDegLat, pasDegLon) {
  const out = [];
  for (let i = 0; i < ring.length; i++) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[(i + 1) % ring.length];
    out.push([x1, y1]);
    const n = Math.ceil(Math.max(
      Math.abs(x2 - x1) / pasDegLon, Math.abs(y2 - y1) / pasDegLat));
    for (let k = 1; k < n; k++) {
      out.push([x1 + ((x2 - x1) * k) / n, y1 + ((y2 - y1) * k) / n]);
    }
  }
  return out;
}

/** Nombre maximal de points échantillonnés. Un couloir de 1 500 km au
 *  pas de 10 km en demanderait 22 500 : on élargit le pas plutôt que de
 *  faire payer au cycle de détection une précision qui n'ajoute aucun
 *  département à la liste. */
const MAX_ECHANTILLONS = 4000;
const PAS_KM_DEFAUT = 10;

/**
 * Départements traversés par un couloir, du plus concerné au moins
 * concerné.
 *
 * `ring` : anneau GeoJSON [[lon, lat], …] (le couloir d'impact).
 *
 * Rend `{ departements: [{ code, nom, share }], coverage, samples }` :
 *  · `share` = part des points échantillonnés qui tombent dans ce
 *    département — c'est ce qui met le département le plus balayé en
 *    tête, plutôt qu'un ordre alphabétique qui ne dirait rien ;
 *  · `coverage` = part des points qui tombent en France. Un couloir qui
 *    part sur la mer ou passe la frontière a une couverture faible, et
 *    l'appelant doit pouvoir le savoir plutôt que de présenter une
 *    liste partielle comme si elle était complète.
 *
 * On échantillonne le CONTOUR **et** l'intérieur : un couloir étroit
 * (front court, peu de largeur latérale) peut ne contenir aucun nœud de
 * la grille, et rendrait alors une liste vide alors qu'il traverse bien
 * deux ou trois départements.
 */
function departementsDuCouloir(ring, opts = {}) {
  const vide = { departements: [], coverage: 0, samples: 0 };
  if (!Array.isArray(ring) || ring.length < 3) return vide;
  if (!charger().length) return vide;

  const [minLon, minLat, maxLon, maxLat] = bboxDe(ring);
  const latMoy = (minLat + maxLat) / 2;
  const kmParDegLon = KM_PAR_DEG_LAT * Math.cos((latMoy * Math.PI) / 180) || KM_PAR_DEG_LAT;

  let pasKm = opts.pasKm ?? PAS_KM_DEFAUT;
  // Élargit le pas jusqu'à tenir dans le budget d'échantillons.
  for (let garde = 0; garde < 12; garde++) {
    const nx = Math.ceil(((maxLon - minLon) * kmParDegLon) / pasKm) + 1;
    const ny = Math.ceil(((maxLat - minLat) * KM_PAR_DEG_LAT) / pasKm) + 1;
    if (nx * ny <= MAX_ECHANTILLONS) break;
    pasKm *= 1.5;
  }
  const pasDegLat = pasKm / KM_PAR_DEG_LAT;
  const pasDegLon = pasKm / kmParDegLon;

  const echantillons = pointsDuContour(ring, pasDegLat, pasDegLon);
  for (let lat = minLat; lat <= maxLat; lat += pasDegLat) {
    for (let lon = minLon; lon <= maxLon; lon += pasDegLon) {
      if (dansAnneau(lon, lat, ring)) echantillons.push([lon, lat]);
    }
  }
  if (!echantillons.length) return vide;

  const compte = new Map();
  let dedans = 0;
  for (const [lon, lat] of echantillons) {
    const d = departementAt(lat, lon);
    if (!d) continue;
    dedans++;
    const e = compte.get(d.code);
    if (e) e.n++;
    else compte.set(d.code, { code: d.code, nom: d.nom, n: 1 });
  }
  if (!dedans) return { departements: [], coverage: 0, samples: echantillons.length };

  const departements = [...compte.values()]
    .sort((a, b) => (b.n - a.n) || a.code.localeCompare(b.code))
    .map(e => ({ code: e.code, nom: e.nom, share: Math.round((e.n / dedans) * 100) / 100 }));

  return {
    departements,
    coverage: Math.round((dedans / echantillons.length) * 100) / 100,
    samples: echantillons.length,
  };
}

/**
 * Départements d'une liste de points ({ lat, lon }), ordonnés du plus
 * représenté au moins représenté. Sert pour les stations qui ont
 * réellement vu passer le front (ou les points de grille d'une veille).
 */
function departementsDePoints(points) {
  if (!Array.isArray(points) || !points.length) return [];
  const compte = new Map();
  for (const p of points) {
    const d = departementAt(p?.lat, p?.lon);
    if (!d) continue;
    const e = compte.get(d.code);
    if (e) e.n++;
    else compte.set(d.code, { code: d.code, nom: d.nom, n: 1 });
  }
  const total = [...compte.values()].reduce((n, e) => n + e.n, 0);
  if (!total) return [];
  return [...compte.values()]
    .sort((a, b) => (b.n - a.n) || a.code.localeCompare(b.code))
    .map(e => ({ code: e.code, nom: e.nom, share: Math.round((e.n / total) * 100) / 100 }));
}

/**
 * Ce qu'on affiche au pilote : les départements CONCERNÉS par un
 * épisode, dans l'ordre où ils lui sont utiles.
 *
 * D'abord le couloir — là où le front VA, c'est-à-dire la réponse à
 * « est-ce que ça va me tomber dessus ». Puis, à la suite, les
 * départements où il a été MESURÉ et qui ne sont pas déjà dans la
 * liste : un pilote qui est là où le front vient de passer est
 * évidemment concerné, même si le couloir ne pointe plus chez lui.
 *
 * Ce complément n'est pas cosmétique. Sur un front corse remontant vers
 * la mer, le couloir est entièrement maritime : sans lui, la liste
 * serait VIDE pour un front pourtant mesuré sur des stations bien
 * réelles, et le bandeau retomberait à « quelque part en France ».
 *
 * `coverage` (part des points du couloir tombant en France) est rendue
 * telle quelle : une liste tirée d'un couloir à moitié maritime est
 * vraie mais partielle, et l'appelant doit pouvoir le dire.
 */
function departementsConcernes(ring, pointsMesures) {
  const couloir = departementsDuCouloir(ring);
  const mesures = departementsDePoints(pointsMesures);

  const vus = new Set(couloir.departements.map(d => d.code));
  const complement = mesures
    .filter(d => !vus.has(d.code))
    // `share: 0` dit explicitement « pas dans le couloir » — ce n'est
    // pas un arrondi à zéro, c'est une provenance différente.
    .map(d => ({ code: d.code, nom: d.nom, share: 0 }));

  return {
    departements: [...couloir.departements, ...complement],
    coverage: couloir.coverage,
    samples: couloir.samples,
    /** D'où vient la liste — utile pour lire un cas dégénéré en base. */
    origin: couloir.departements.length
      ? (complement.length ? 'couloir+mesure' : 'couloir')
      : (complement.length ? 'mesure' : 'aucun'),
  };
}

module.exports = {
  departementAt,
  departementsDuCouloir,
  departementsDePoints,
  departementsConcernes,
  departementsCharges,
  // Exportés pour l'auto-test.
  dansAnneau,
};
