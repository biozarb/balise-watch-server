#!/usr/bin/env node
// ══════════════════════════════════════════════════════════════════════
//  tools/calibrer_gust_pi.mjs — combien de sites parleraient ? (09/09/2026)
//                               Lot « cellule qui approche », lot 2, §5
//
//  ⛔ CE QUI MANQUE POUR OUVRIR LES PUSH, ET QUE CE FICHIER FOURNIT.
//  Un seuil ne se juge pas sur une carte : il se juge sur le NOMBRE DE
//  GENS QU'IL RÉVEILLE. Ce script prend le run réellement en ligne, le
//  passe sur les 3 569 décollages de `decos.json` — les vrais sites, pas
//  cinq témoins choisis — et compte, seuil par seuil, combien
//  déclencheraient `gust_pi`.
//
//  ⚠️ UN CHIFFRE PAR JOUR NE SUFFIT PAS. Il faut le rejouer sur trois
//  jours CALMES (faux positifs) et sur un ORAGE réel (rattrapage). Le
//  09/09, journée de tramontane, il donnait :
//      seuil  40 km/h :  325 sites sur 2 066 dans l'emprise (15,7 %)
//      seuil  50 km/h :  128 sites (6,2 %)
//      seuil  55 km/h :   67 sites (3,2 %)
//      seuil  60 km/h :   39 sites (1,9 %)
//      seuil  70 km/h :    7 sites (0,3 %)
//  ⛔ 325 pushes un jour venté ordinaire, ce n'est pas une alerte, c'est
//  un bruit de fond — et un pilote qui apprend à ignorer un signal ne le
//  regardera plus le jour où il compte. C'est pour ça que
//  `PI_RAFALE_ENABLED` est OFF par défaut.
//
//  ⚠️ Et ce comptage NE DIT PAS si les 325 avaient tort. Un jour de
//  tramontane, 40 km/h de rafale sur 325 décollages est peut-être
//  parfaitement exact — le problème n'est pas la justesse, c'est
//  l'utilité. La suite de la calibration doit donc regarder le SAUT
//  (`sautKmh`, déjà calculé par le module) autant que la valeur absolue.
//
//  Usage :  node tools/calibrer_gust_pi.mjs
//           node tools/calibrer_gust_pi.mjs --seuils 40,45,50,55
//           node tools/calibrer_gust_pi.mjs --saut 20   (ne compte que
//               les sites où la rafale se DÉTACHE du fond de ≥ 20 km/h)
// ══════════════════════════════════════════════════════════════════════
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const require = createRequire(import.meta.url);
const ICI = dirname(fileURLToPath(import.meta.url));
const R = require(join(ICI, '..', 'lib', 'rafale-pi.js'));
const decos = require(join(ICI, '..', '..', 'web', 'public', 'data', 'decos.json'));

const arg = (nom, defaut) => {
  const i = process.argv.indexOf(nom);
  return i > 0 && process.argv[i + 1] ? process.argv[i + 1] : defaut;
};
const SEUILS = arg('--seuils', '40,50,55,60,70').split(',').map(Number);
const SAUT_MIN = Number(arg('--saut', String(R.DEFAUTS.sautMinKmh)));
const ETA_MAX = Number(arg('--eta', '120'));

const base = process.env.WIND_GRID_BASE_URL || 'https://pub-7a401bae4fe54a6c8dbdd6b5a33a7bec.r2.dev';
const lecteur = new R.LecteurRafale({ baseUrl: base, fetch: globalThis.fetch, journal: m => console.log(m) });
const carte = await lecteur.rafraichir(Date.now());
if (!carte) {
  console.error('⛔ aucun run lisible :', lecteur.etat().dernierEchec?.message);
  process.exit(1);
}
const now = Date.now();
// ⚠️ `decos.json` est un tableau de TUPLES : [lat, lon, nom, altM, secteurs].
const sites = decos.filter(d => Array.isArray(d) && Number.isFinite(d[0]) && Number.isFinite(d[1]));
console.log(`\nrun ${carte.run} · âge ${lecteur.etat().runAgeMin} min · ${sites.length} décollages dans decos.json`);
console.log(`saut exigé pour une CELLULE : ≥ ${SAUT_MIN} km/h au-dessus du fond du moment`);

for (const seuil of SEUILS) {
  let dedans = 0, hit = 0, cell = 0, sousEta = 0;
  const pics = [];
  for (const [lat, lon] of sites) {
    const r = R.rafalePi(carte, lat, lon, now, { seuilKmh: seuil, sautMinKmh: SAUT_MIN });
    if (r.refus) continue;
    dedans++;
    if (r.picKmh != null) pics.push(r.picKmh);
    if (!r.hit) continue;
    hit++;
    // ⛔ `cellule` = franchit le seuil ET se détache du fond. C'est ce
    // qui pousse ; `hit` seul est ce qui parlerait à 41 % des sites un
    // jour de tramontane.
    if (r.cellule) cell++;
    if (r.cellule && r.etaMin <= ETA_MAX) sousEta++;
  }
  pics.sort((a, b) => a - b);
  const q = p => pics[Math.min(pics.length - 1, Math.floor(pics.length * p))];
  console.log(
    `seuil ${String(seuil).padStart(3)} km/h : ${String(hit).padStart(4)} franchissements (${(100 * hit / Math.max(1, dedans)).toFixed(1)} %)`
    + ` · ${String(cell).padStart(4)} CELLULES (${(100 * cell / Math.max(1, dedans)).toFixed(1)} %)`
    + ` · ${sousEta} à ETA ≤ ${ETA_MAX} min`
    + (seuil === SEUILS[0] ? `  · sur ${dedans} décollages dans l'emprise · pic médian ${q(0.5)} km/h, p90 ${q(0.9)}, max ${pics[pics.length - 1]}` : ''));
}
console.log('\n⚠️ À rejouer sur trois jours CALMES et sur un orage réel avant de poser PI_RAFALE_ENABLED=1.\n');
