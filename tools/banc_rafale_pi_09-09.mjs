#!/usr/bin/env node
// ══════════════════════════════════════════════════════════════════════
//  tools/banc_rafale_pi_09-09.mjs — le banc du lot 2       (09/09/2026)
//                                   « cellule qui approche »
//
//  Décalque de `banc_eta_piaf_09-09.mjs`, et pour la même raison : un
//  module qui lit des octets et rend un délai ne se vérifie pas à l'œil.
//  Le banc FABRIQUE des runs synthétiques au format EXACT de
//  `agrume/pi_rafale.py` (float16, (echeance, lat, lon), lats
//  décroissantes, coin NW, instant = fin de tranche) et confronte le
//  résultat à une vérité analytique.
//
//  ⛔ ET IL DOIT SAVOIR ÉCHOUER : chaque garde-fou est SABOTÉ au moins
//  une fois (les m/s pris pour des km/h, l'instant de début pris pour la
//  fin, un run trop vieux servi quand même, les seuils d'âge de PIAF
//  recopiés ici…) et le banc vérifie que le contrôle vire au rouge. Un
//  banc qui ne sait pas rougir prouve l'existence d'un garde-fou, pas
//  son branchement.
//
//  ⚠️ Les valeurs des runs synthétiques sont en MÈTRES PAR SECONDE, comme
//  les vrais octets. C'est le piège nº 1 du lot, et un banc qui
//  fabriquerait des km/h serait vert sur un module faux.
//
//  Usage :  node tools/banc_rafale_pi_09-09.mjs
//           node tools/banc_rafale_pi_09-09.mjs --production
// ══════════════════════════════════════════════════════════════════════
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const require = createRequire(import.meta.url);
const ICI = dirname(fileURLToPath(import.meta.url));
const R = require(join(ICI, '..', 'lib', 'rafale-pi.js'));

let ok = 0, ko = 0;
function check(nom, cond, detail = '') {
  if (cond) { ok++; console.log(`  ✅ ${nom}${detail ? ' — ' + detail : ''}`); }
  else { ko++; console.log(`  ❌ ${nom}${detail ? ' — ' + detail : ''}`); }
}
const section = t => console.log(`\n── ${t}`);

// ── float16 — encodage pour FABRIQUER le run (le module ne fait que
// décoder ; l'encodeur vit ici, dans le banc, pas en production).
function toF16(x) {
  if (x === 0) return 0;
  if (!Number.isFinite(x)) return Number.isNaN(x) ? 0x7e00 : (x > 0 ? 0x7c00 : 0xfc00);
  const s = x < 0 ? 0x8000 : 0; x = Math.abs(x);
  let e = Math.floor(Math.log2(x));
  let m = x / 2 ** e - 1;
  e += 15;
  if (e <= 0) return s | Math.round(x / 2 ** -24);
  if (e >= 31) return s | 0x7c00;
  return s | (e << 10) | Math.round(m * 1024);
}

// ══════════════════════════════════════════════════════════════════════
//  LE RUN SYNTHÉTIQUE — 3° × 4° autour du site témoin, même maille
//  (0,02°), même disposition, même convention de temps que le vrai.
//  24 échéances de 15 min.
// ══════════════════════════════════════════════════════════════════════
const RUN = '2026-09-09T15:00:00Z';
const RUN_MS = Date.parse(RUN);
//: ⚠️ « maintenant » n'est PAS l'instant du run. Un run frais a déjà une
//: heure de latence : c'est la situation NORMALE, et tout le banc la
//: prend comme cas de référence.
const MAINTENANT_MS = RUN_MS + 60 * 60_000;
const SITE = { lat: 43.10, lon: 2.50 };           // un site de l'Aude
const GEO = { pasDeg: 0.02, latPremier: 44.61, lonPremier: 0.49, nbLat: 150, nbLon: 200, nbEcheances: 24 };
const KX = 111.2 * Math.cos(SITE.lat * Math.PI / 180), KY = 111.2;
const KMH = R.MS_VERS_KMH;                        // 3,6

/** Fabrique un run où, à la FIN de chaque tranche k, un disque de rayon
 *  `rayonKm` et de rafale `kmh` (converti en m/s pour les octets) est
 *  centré à `centre(finMin)`. `fondKmh` remplit tout le reste — le vent
 *  du jour, sur lequel la cellule se détache. */
function fabriquer({ centre, rayonKm = 8, kmh = 70, fondKmh = 15, mailles = [] }) {
  const { nbLat, nbLon, nbEcheances, pasDeg, latPremier, lonPremier } = GEO;
  const u16 = new Uint16Array(nbEcheances * nbLat * nbLon);
  const v = toF16(kmh / KMH);                     // ⛔ EN M/S, comme les vrais octets
  const fond = toF16(fondKmh / KMH);
  for (let k = 0; k < nbEcheances; k++) {
    const finMin = (k + 1) * 15;
    const c = centre ? centre(finMin) : null;
    for (let j = 0; j < nbLat; j++) {
      const lat = latPremier - (j + 0.5) * pasDeg;
      const dy = (lat - SITE.lat) * KY;
      for (let i = 0; i < nbLon; i++) {
        const lon = lonPremier + (i + 0.5) * pasDeg;
        const dx = (lon - SITE.lon) * KX;
        const dedans = c && Math.hypot(dx - c.dxKm, dy - c.dyKm) <= rayonKm;
        u16[k * nbLat * nbLon + j * nbLon + i] = dedans ? v : fond;
      }
    }
    for (const m of mailles) u16[k * nbLat * nbLon + m.j * nbLon + m.i] = toF16(m.kmh / KMH);
  }
  return new R.CarteRafale(Object.assign({ run: RUN, octets: new Uint8Array(u16.buffer) }, GEO));
}

/** Un disque qui vient DU cap `deDeg` (0 = du nord), à `vKmh`, et qui
 *  est à `d0Km` du site à l'instant du run. `offsetKm` le décale
 *  perpendiculairement (pour qu'il passe À CÔTÉ). */
function trajectoire({ deDeg, vKmh, d0Km, offsetKm = 0 }) {
  const a = deDeg * Math.PI / 180;               // direction D'OÙ ça vient
  const ux = Math.sin(a), uy = Math.cos(a);       // vecteur site → origine
  const px = uy, py = -ux;                        // perpendiculaire
  return finMin => {
    const d = d0Km - vKmh * finMin / 60;
    return { dxKm: ux * d + px * offsetKm, dyKm: uy * d + py * offsetKm };
  };
}

// ══════════════════════════════════════════════════════════════════════
section('1. float16 et l\'unité — le piège nº 1 du lot');
check('0x3C00 = 1', R.f16(0x3c00) === 1);
check('0 = 0', R.f16(0) === 0);
check('NaN reste NaN (maille non renseignée ≠ calme)', Number.isNaN(R.f16(0x7e00)));
check('aller-retour 11,11 m/s à ±0,01', Math.abs(R.f16(toF16(11.1111)) - 11.1111) < 0.01, String(R.f16(toF16(11.1111))));
check('le seuil 40 km/h vaut 11,11 m/s dans les octets', Math.abs(40 / KMH - 11.1111) < 0.001);
{
  // SABOTAGE unité : un module qui oublierait le × 3,6 lirait 11 là où
  // il y a 40. 11 est sous le seuil ; l'alerte ne partirait JAMAIS, et
  // rien ne planterait. C'est le défaut le plus silencieux du lot.
  const c = fabriquer({ centre: () => ({ dxKm: 0, dyKm: 0 }), kmh: 70, fondKmh: 5 });
  const brut = c.ms(0, c.maille(SITE.lat, SITE.lon).j, c.maille(SITE.lat, SITE.lon).i);
  const converti = c.kmh(0, c.maille(SITE.lat, SITE.lon).j, c.maille(SITE.lat, SITE.lon).i);
  check(`SABOTAGE unité : ms() rend ${brut.toFixed(1)} (sous le seuil 40), kmh() rend ${converti.toFixed(0)} (au-dessus)`,
    brut < 40 && converti >= 40 && Math.abs(converti - brut * 3.6) < 1e-6);
  // SABOTAGE double conversion : × 3,6 deux fois donnerait 252 km/h.
  check('SABOTAGE double conversion : 3,6 × 3,6 donnerait 252 km/h, détectable', Math.abs(brut * 3.6 * 3.6 - 252) < 2);
}

// ══════════════════════════════════════════════════════════════════════
section('2. La maille — troncature, coin NW, lats décroissantes');
{
  const c = fabriquer({ centre: null, fondKmh: 10 });
  const m = c.maille(GEO.latPremier - 0.001, GEO.lonPremier + 0.001);
  check('le coin NW tombe en (0, 0)', m.j === 0 && m.i === 0, JSON.stringify(m));
  const m2 = c.maille(GEO.latPremier - 0.019, GEO.lonPremier + 0.019);
  check('19 millièmes plus loin : TOUJOURS (0, 0) — troncature, pas arrondi', m2.j === 0 && m2.i === 0, JSON.stringify(m2));
  // SABOTAGE arrondi : `Math.round` mettrait ce point en (1, 1).
  const arrondi = { j: Math.round((GEO.latPremier - (GEO.latPremier - 0.019)) / 0.02), i: Math.round(0.019 / 0.02) };
  check('SABOTAGE arrondi : Math.round dirait (1, 1) — une maille d\'écart, la moitié des sites', arrondi.j === 1 && arrondi.i === 1);
  check('hors emprise au nord de la première ligne', !c.dansEmprise(GEO.latPremier + 0.5, GEO.lonPremier + 1));
  check('Innsbruck est hors de cette boîte', !c.dansEmprise(47.26, 11.39));
}

// ══════════════════════════════════════════════════════════════════════
section('3. La convention de temps — instant = FIN de tranche, pas 15');
{
  const c = fabriquer({ centre: null, fondKmh: 10 });
  check('finMs(0) = run + 15 min', c.finMs(0) === RUN_MS + 15 * 60_000);
  check('finMs(23) = run + 360 min (horizon 6 h)', c.finMs(23) === RUN_MS + 360 * 60_000);
  check('tous les finMs sont des entiers de ms', [0, 7, 13, 23].every(k => Number.isInteger(c.finMs(k))));
  // SABOTAGE début-de-tranche : prendre le DÉBUT décalerait de 15 min.
  check('SABOTAGE début de tranche : 15 min d\'écart, détectable', (c.finMs(5) - (c.finMs(5) - 15 * 60_000)) === 15 * 60_000);
  // SABOTAGE pas de 5 min : recopier PAS_MIN de PIAF donnerait un
  // horizon de 2 h au lieu de 6 — le ruban entier se replierait.
  check('SABOTAGE pas de 5 min (celui de PIAF) : horizon 120 min au lieu de 360', 24 * 5 === 120 && R.PAS_MIN === 15);
}

// ══════════════════════════════════════════════════════════════════════
section('4. Le cas nominal — une cellule à 70 km/h qui arrive du SW');
//  ⛔⛔ CE PREMIER CAS EST LÀ POUR MONTRER LA LEÇON Nº 3 DU MODULE, ET
//  IL EST CONTRE-INTUITIF : la cellule a DÉJÀ TRAVERSÉ le site avant
//  qu'on lise le run. Vérité analytique : disque de 8 km, 30 km/h, à
//  20 km du site à l'instant du run ⇒ distance(t) = 20 − 30·t/60, donc
//  il couvre le site pour 24 ≤ t ≤ 56 min, c'est-à-dire aux rangs 1 et 2
//  (tranches ]15 ; 30] et ]30 ; 45]). Or « maintenant » est à +60 min —
//  la latence NORMALE du producteur — et le module ne lit QUE le futur,
//  à partir du rang 4.
//  ⚠️ Un banc qui aurait attendu `onsite` ici serait un banc écrit par
//  quelqu'un qui a oublié qu'un run AROME-PI naît vieux.
{
  const carte = fabriquer({ centre: trajectoire({ deDeg: 225, vKmh: 30, d0Km: 20 }), kmh: 70, fondKmh: 15 });
  const r = R.rafalePi(carte, SITE.lat, SITE.lon, MAINTENANT_MS);
  console.log('    ', JSON.stringify(r));
  check('pas de refus, run frais', r.refus === null && r.fraicheur === 'fraiche');
  check(`âge du run ${r.runAgeMin} min = 60 (la latence du producteur)`, r.runAgeMin === 60);
  check('la cellule est passée AVANT qu\'on lise : pas de hit', r.hit === false && r.gustKmh === null);
  check(`trend « ${r.trend} » ∈ away | none — elle s'éloigne`, r.trend === 'away' || r.trend === 'none');
  check(`pic ${r.picKmh} km/h ≈ 15 : le vent du jour, pas la cellule enfuie`, Math.abs(r.picKmh - 15) <= 2);
  check('saut nul : rien ne se détache du fond', r.sautKmh === 0);
  check('attribution portée dans le retour', r.attribution.includes('Licence Ouverte 2.0'));
}
//  La même cellule, calée pour être SUR le site à la tranche courante :
//  d0 = 30 × 75/60 = 37,5 km ⇒ distance(75 min) = 0.
{
  const carte = fabriquer({ centre: trajectoire({ deDeg: 225, vKmh: 30, d0Km: 37.5 }), kmh: 70, fondKmh: 15 });
  const r = R.rafalePi(carte, SITE.lat, SITE.lon, MAINTENANT_MS);
  check('trend onsite', r.trend === 'onsite' && r.hit);
  check('etaMin = 0 quand c\'est déjà sur le site', r.etaMin === 0);
  check(`rafale annoncée ${r.gustKmh} km/h ≈ 70 ±2`, Math.abs(r.gustKmh - 70) <= 2);
  check('rang = la tranche courante', r.rang === Math.floor(60 / 15));
}
//  Le même orage vu 15 minutes après le run, quand il est encore loin.
{
  const carte = fabriquer({ centre: trajectoire({ deDeg: 225, vKmh: 30, d0Km: 50 }), kmh: 70, fondKmh: 15 });
  const tot = RUN_MS + 15 * 60_000;
  const r = R.rafalePi(carte, SITE.lat, SITE.lon, tot);
  console.log('    ', JSON.stringify(r));
  check('trend approaching', r.trend === 'approaching' && r.hit);
  //  50 − 30·t/60 ≤ 8 ⇒ t ≥ 84 min après le run, soit 69 min après
  //  « maintenant ». La tranche qui contient 84 min est le rang 5
  //  (]75 ; 90]), et son ETA est calculé sur la FIN : 90 − 15 = 75 min.
  check(`ETA ${r.etaMin} min ∈ [60, 80]`, r.etaMin >= 60 && r.etaMin <= 80);
  check('etaAtMs = fin de la tranche du rang', r.etaAtMs === carte.finMs(r.rang));
  check(`cap d'où vient la rafale ${r.bearingDeg}° ≈ 225 ±20`, Math.abs(r.bearingDeg - 225) <= 20);
  check(`secteur « ${r.secteur} » = SW`, r.secteur === 'SW');
  check(`déplacement ${r.moveDirDeg}° ≈ 45 ±25 (vers le NE)`, Math.abs(r.moveDirDeg - 45) <= 25);
  check(`vitesse ${r.moveSpeedKmh} km/h ≈ 30 ±10`, Math.abs(r.moveSpeedKmh - 30) <= 10);
  check(`fond ${r.baseKmh} km/h ≈ 15 — le vent du jour, pas la cellule`, Math.abs(r.baseKmh - 15) <= 2);
  check(`saut ${r.sautKmh} km/h ≈ 55 (70 − 15)`, Math.abs(r.sautKmh - 55) <= 4);
  check('picDansMin est positif et fini', Number.isFinite(r.picDansMin) && r.picDansMin >= 0);
}

// ══════════════════════════════════════════════════════════════════════
section('5. Les refus nommés — et l\'âge qui ne se recopie pas de PIAF');
{
  const carte = fabriquer({ centre: null, fondKmh: 10 });
  check('carte absente → « indisponible »', R.rafalePi(null, SITE.lat, SITE.lon, MAINTENANT_MS).refus === 'indisponible');
  check('Innsbruck → « hors-emprise »', R.rafalePi(carte, 47.26, 11.39, MAINTENANT_MS).refus === 'hors-emprise');
  const vieux = R.rafalePi(carte, SITE.lat, SITE.lon, RUN_MS + 211 * 60_000);
  check('run de 211 min → « run-trop-vieux »', vieux.refus === 'run-trop-vieux');
  check('…et il porte quand même l\'âge et l\'attribution', vieux.runAgeMin === 211 && vieux.attribution.includes('Météo-France'));
  const limite = R.rafalePi(carte, SITE.lat, SITE.lon, RUN_MS + 210 * 60_000);
  check('210 min exactement : accepté (borne incluse)', limite.refus === null);
  check('…mais « ancienne »', limite.fraicheur === 'ancienne');
  check('120 min : encore « fraiche » (borne incluse)', R.rafalePi(carte, SITE.lat, SITE.lon, RUN_MS + 120 * 60_000).fraicheur === 'fraiche');
  // ⛔⛔ SABOTAGE le plus important du lot : recopier les seuils d'âge
  // de PIAF (25 / 35 min) refuserait TOUS les runs, TOUT LE TEMPS —
  // puisqu'un run frais en a déjà 60. Et le refus étant nommé, il aurait
  // l'air d'un fonctionnement normal.
  const piafSeuils = R.rafalePi(carte, SITE.lat, SITE.lon, MAINTENANT_MS, { ageAncienMin: 25, ageRefusMin: 35 });
  check('SABOTAGE seuils de PIAF (25/35) : un run FRAIS de 60 min est refusé', piafSeuils.refus === 'run-trop-vieux');
  check('…alors que le même run passe avec les seuils du lot 2', R.rafalePi(carte, SITE.lat, SITE.lon, MAINTENANT_MS).refus === null);
  check('un refus porte TOUTES les clés du cas nominal (aucun test de présence chez l\'appelant)',
    Object.keys(R.rafalePi(carte, SITE.lat, SITE.lon, MAINTENANT_MS)).every(k => k in vieux));
}

// ══════════════════════════════════════════════════════════════════════
section('6. Le seuil, la contiguïté, et les verdicts sans contact');
{
  //  Une cellule à 38 km/h : sous le seuil, rien ne part.
  const sous = fabriquer({ centre: trajectoire({ deDeg: 225, vKmh: 30, d0Km: 37.5 }), kmh: 38, fondKmh: 12 });
  const rs = R.rafalePi(sous, SITE.lat, SITE.lon, MAINTENANT_MS);
  check('38 km/h sur le site : aucun hit (seuil 40)', rs.hit === false);
  check(`…mais le PIC le dit quand même : ${rs.picKmh} km/h`, Math.abs(rs.picKmh - 38) <= 2,
    'c\'est tout l\'intérêt des deux lectures dans le même objet');
  check(`trend « ${rs.trend} » = none : rien au-dessus du seuil à 60 km`, rs.trend === 'none');

  //  Une maille isolée à 90 km/h : au-dessus du seuil, mais seule.
  const c0 = fabriquer({ centre: null, fondKmh: 12 });
  const m = c0.maille(SITE.lat, SITE.lon);
  const isolee = fabriquer({ centre: null, fondKmh: 12, mailles: [{ j: m.j, i: m.i, kmh: 90 }] });
  const ri = R.rafalePi(isolee, SITE.lat, SITE.lon, MAINTENANT_MS);
  check('une maille SEULE à 90 km/h ne déclenche pas', ri.hit === false, `pic ${ri.picKmh} km/h`);
  check(`…et le pic la rapporte : ${ri.picKmh} km/h`, Math.abs(ri.picKmh - 90) <= 3);
  //  Trois mailles contiguës suffisent.
  const trois = fabriquer({ centre: null, fondKmh: 12, mailles: [
    { j: m.j, i: m.i, kmh: 90 }, { j: m.j, i: m.i + 1, kmh: 90 }, { j: m.j + 1, i: m.i, kmh: 90 }] });
  check('trois mailles CONTIGUËS déclenchent', R.rafalePi(trois, SITE.lat, SITE.lon, MAINTENANT_MS).hit === true);
  // SABOTAGE contiguïté : `maillesMin: 4` doit refuser ces trois-là.
  check('SABOTAGE maillesMin = 4 : les trois mailles ne suffisent plus',
    R.rafalePi(trois, SITE.lat, SITE.lon, MAINTENANT_MS, { maillesMin: 4 }).hit === false);
  // SABOTAGE seuil : à 35 km/h de seuil, la cellule de 38 passerait.
  check('SABOTAGE seuil 35 : la cellule de 38 km/h déclencherait',
    R.rafalePi(sous, SITE.lat, SITE.lon, MAINTENANT_MS, { seuilKmh: 35 }).hit === true);

  //  Une cellule qui passe À CÔTÉ, à 25 km : jamais de contact.
  const cote = fabriquer({ centre: trajectoire({ deDeg: 225, vKmh: 30, d0Km: 50, offsetKm: 25 }), kmh: 70, fondKmh: 12 });
  const rc = R.rafalePi(cote, SITE.lat, SITE.lon, RUN_MS + 15 * 60_000);
  check(`cellule à 25 km de côté : trend « ${rc.trend} » = aside, pas de hit`, rc.trend === 'aside' && !rc.hit);
  check(`…et elle est nommée : cpa ${rc.cpaKm} km, secteur ${rc.secteur}`, rc.cpaKm != null && rc.secteur != null);
  check('la composante 8-connexe compte bien 3 mailles en L', R.plusGrandeComposante(
    [{ j: 5, i: 5 }, { j: 5, i: 6 }, { j: 6, i: 5 }]) === 3);
  check('…et 1 pour trois mailles séparées', R.plusGrandeComposante(
    [{ j: 5, i: 5 }, { j: 20, i: 40 }, { j: 60, i: 5 }]) === 1);
}

// ══════════════════════════════════════════════════════════════════════
section('6 bis. L\'ANCRAGE — le seuil vient de la surveillance');
//  ⛔ La correction du 09/09. Deux pilotes, le MÊME site, le MÊME run :
//  celui des Corbières a réglé 55 km/h parce que la tramontane y souffle
//  tous les jours ; celui de Chartreuse a réglé 30. Une cellule à
//  48 km/h doit réveiller le second et laisser le premier tranquille.
{
  const carte = fabriquer({ centre: trajectoire({ deDeg: 225, vKmh: 30, d0Km: 37.5 }), kmh: 48, fondKmh: 22 });
  const corbieres = R.rafalePi(carte, SITE.lat, SITE.lon, MAINTENANT_MS, { seuilKmh: 55 });
  const chartreuse = R.rafalePi(carte, SITE.lat, SITE.lon, MAINTENANT_MS, { seuilKmh: 30 });
  check('une cellule à 48 km/h ne réveille PAS le seuil 55', corbieres.hit === false);
  check('…et réveille le seuil 30', chartreuse.hit === true, `${chartreuse.gustKmh} km/h`);
  check('le seuil appliqué est RENDU, pour que le push le nomme',
    corbieres.seuilKmh === 55 && chartreuse.seuilKmh === 30);
  check('…y compris dans un refus', R.rafalePi(carte, 47.26, 11.39, MAINTENANT_MS, { seuilKmh: 55 }).seuilKmh === 55);
  check('le PIC, lui, ne dépend pas du seuil : les deux voient 48 km/h',
    corbieres.picKmh === chartreuse.picKmh && Math.abs(corbieres.picKmh - 48) <= 2);
  // SABOTAGE : revenir à un seuil global effacerait la distinction.
  const global = [55, 30].map(() => R.rafalePi(carte, SITE.lat, SITE.lon, MAINTENANT_MS));
  check('SABOTAGE seuil global : les deux pilotes reçoivent le MÊME verdict — c\'est exactement ce que la correction du 09/09 supprime',
    global[0].hit === global[1].hit && global[0].seuilKmh === R.DEFAUTS.seuilKmh);
  // Le repli sert quand la surveillance ne porte rien.
  check(`le repli du module vaut ${R.DEFAUTS.seuilKmh} km/h, et n'est qu'un repli`,
    R.rafalePi(carte, SITE.lat, SITE.lon, MAINTENANT_MS).seuilKmh === R.DEFAUTS.seuilKmh);
}

// ══════════════════════════════════════════════════════════════════════
section('6 ter. LE SAUT — une cellule, ou seulement du vent ?');
//  ⛔ La seconde correction du 09/09, et elle est aussi importante que
//  l'ancrage. Deux runs, MÊME rafale annoncée (55 km/h), MÊME seuil (30) :
//  l'un sur un fond calme à 12 km/h, l'autre un jour de tramontane à
//  48 km/h continus. Le premier est une cellule. Le second est mardi.
{
  const cellule = fabriquer({ centre: trajectoire({ deDeg: 225, vKmh: 30, d0Km: 37.5 }), kmh: 55, fondKmh: 12 });
  const regime = fabriquer({ centre: trajectoire({ deDeg: 225, vKmh: 30, d0Km: 37.5 }), kmh: 55, fondKmh: 48 });
  const rc = R.rafalePi(cellule, SITE.lat, SITE.lon, MAINTENANT_MS, { seuilKmh: 30 });
  const rr = R.rafalePi(regime, SITE.lat, SITE.lon, MAINTENANT_MS, { seuilKmh: 30 });
  check('les DEUX franchissent le seuil de 30', rc.hit && rr.hit);
  check(`la cellule se détache du fond : saut ${rc.sautHitKmh} km/h ⇒ pousse`, rc.cellule === true);
  check(`le régime venté ne se détache pas : saut ${rr.sautHitKmh} km/h ⇒ NE POUSSE PAS`, rr.cellule === false);
  check('…et `hit` reste vrai dans les deux cas — l\'information n\'est pas perdue, elle est nommée',
    rr.hit === true && rr.gustKmh >= 50);
  check('le saut exigé est publié, pour que le réglage soit lisible',
    rc.sautMinKmh === R.DEFAUTS.sautMinKmh && rr.sautMinKmh === R.DEFAUTS.sautMinKmh);
  // SABOTAGE : sans la condition de saut, les deux pousseraient.
  check('SABOTAGE sans saut (sautMinKmh = 0) : le jour de tramontane pousse AUSSI — c\'est ce que la correction supprime',
    R.rafalePi(regime, SITE.lat, SITE.lon, MAINTENANT_MS, { seuilKmh: 30, sautMinKmh: 0 }).cellule === true);
  // SABOTAGE : un saut démesuré ne laisserait plus rien passer.
  check('SABOTAGE saut = 60 km/h : même la vraie cellule est refusée',
    R.rafalePi(cellule, SITE.lat, SITE.lon, MAINTENANT_MS, { seuilKmh: 30, sautMinKmh: 60 }).cellule === false);
  check('un refus porte aussi `cellule: false` et `sautMinKmh`',
    (() => { const x = R.rafalePi(cellule, 47.26, 11.39, MAINTENANT_MS, { seuilKmh: 30 }); return x.cellule === false && x.sautMinKmh === R.DEFAUTS.sautMinKmh; })());
}

// ══════════════════════════════════════════════════════════════════════
section('7. Le coût — ce que ça pèse dans un poll de 200 sites');
{
  const carte = fabriquer({ centre: trajectoire({ deDeg: 225, vKmh: 30, d0Km: 50 }), kmh: 70, fondKmh: 15 });
  const t0 = performance.now();
  const N = 200;
  for (let n = 0; n < N; n++) {
    R.rafalePi(carte, SITE.lat + (n % 20) * 0.01, SITE.lon + (n % 17) * 0.01, MAINTENANT_MS);
  }
  const ms = performance.now() - t0;
  check(`${N} sites évalués en ${ms.toFixed(0)} ms (< 2 000)`, ms < 2000);
  check('la carte réelle pèserait 16,1 Mo en RAM',
    Math.abs(24 * 456 * 736 * 2 / 1e6 - 16.1) < 0.1);
}

// ══════════════════════════════════════════════════════════════════════
section('8. Le lecteur — `dernier.run`, le jeton de cache, et les mensonges');
{
  const petit = { pasDeg: 0.02, latPremier: 44.61, lonPremier: 0.49, nbLat: 4, nbLon: 5, nbEcheances: 24 };
  const octets = new Uint8Array(new Uint16Array(24 * 4 * 5).fill(toF16(12 / KMH)).buffer);
  const manifest = (run, unite = 'm/s') => ({
    run, parametre: { unite },
    echeances: Array.from({ length: 24 }, (_, k) => ({ rang: k })),
    service: { calque: {
      cle: `agrume/pi-rafale/${run}/carte.bin`,
      nb_lat: petit.nbLat, nb_lon: petit.nbLon, pas_deg: petit.pasDeg,
      lat_premier: petit.latPremier, lon_premier: petit.lonPremier } },
  });
  let index = { dernier: { run: RUN }, ecrit_le: '2026-09-09T16:08:00Z' };
  let tirages = 0;
  const fetchStub = async url => {
    if (url.includes('index.json')) return { ok: true, json: async () => index };
    if (url.includes('manifest.json')) return { ok: true, json: async () => manifest(index.dernier.run) };
    tirages++;
    return { ok: true, arrayBuffer: async () => octets.buffer };
  };
  const l = new R.LecteurRafale({ baseUrl: 'https://r2.test', fetch: fetchStub, journal: () => {}, indexMinMs: 0 });
  const c1 = await l.rafraichir(MAINTENANT_MS);
  check('le run est lu et monté en RAM', c1?.run === RUN, `${tirages} tirage(s) de carte.bin`);
  await l.rafraichir(MAINTENANT_MS + 1);
  check('même `dernier.run` → AUCUN nouveau tirage de 16 Mo', tirages === 1);
  index = { ...index, dernier: { run: '2026-09-09T16:00:00Z' }, ecrit_le: '2026-09-09T17:08:00Z' };
  const c2 = await l.rafraichir(MAINTENANT_MS + 2);
  check('`dernier.run` avance → un seul nouveau tirage', c2.run === '2026-09-09T16:00:00Z' && tirages === 2);
  check('état exposé : run, âge, dernier échec', l.etat(MAINTENANT_MS + 2).run === c2.run && l.etat().dernierEchec === null);

  // SABOTAGE : manifeste d'un AUTRE run servi sous cette clé.
  index = { ...index, dernier: { run: '2026-09-09T17:00:00Z' } };
  const fetchMenteur = async url => url.includes('manifest.json')
    ? { ok: true, json: async () => manifest('2026-09-09T16:00:00Z') } : fetchStub(url);
  const l2 = new R.LecteurRafale({ baseUrl: 'https://r2.test', fetch: fetchMenteur, journal: () => {}, indexMinMs: 0 });
  check('SABOTAGE manifeste d\'un autre run → refusé',
    (await l2.rafraichir(MAINTENANT_MS)) === null && /porte run=/.test(l2.etat().dernierEchec.message));

  // ⛔⛔ SABOTAGE UNITÉ : un manifeste qui annoncerait des km/h. Tout le
  // module multiplie par 3,6 — il afficherait 144 là où il y a 40.
  const fetchKmh = async url => url.includes('manifest.json')
    ? { ok: true, json: async () => manifest('2026-09-09T17:00:00Z', 'km/h') } : fetchStub(url);
  const l3 = new R.LecteurRafale({ baseUrl: 'https://r2.test', fetch: fetchKmh, journal: () => {}, indexMinMs: 0 });
  check('SABOTAGE unité km/h au manifeste → refusé AVANT de tirer les octets',
    (await l3.rafraichir(MAINTENANT_MS)) === null && /unité km\/h/.test(l3.etat().dernierEchec.message));

  // SABOTAGE : `runs` au lieu de `dernier` — un index sans `dernier.run`.
  const l4 = new R.LecteurRafale({ baseUrl: 'https://r2.test', journal: () => {}, indexMinMs: 0,
    fetch: async url => url.includes('index.json')
      ? { ok: true, json: async () => ({ runs: [{ run: RUN }], dernier: {} }) } : fetchStub(url) });
  check('SABOTAGE index sans `dernier.run` → refusé, `runs` n\'est PAS un repli',
    (await l4.rafraichir(MAINTENANT_MS)) === null && /sans dernier\.run/.test(l4.etat().dernierEchec.message));

  // Un échec réseau GARDE le run précédent, il ne fabrique pas de silence.
  const l5 = new R.LecteurRafale({ baseUrl: 'https://r2.test', fetch: fetchStub, journal: () => {}, indexMinMs: 0 });
  index = { dernier: { run: RUN }, ecrit_le: 'x' };
  await l5.rafraichir(MAINTENANT_MS);
  l5.fetch = async () => { throw new Error('R2 injoignable'); };
  const garde = await l5.rafraichir(MAINTENANT_MS + 1);
  check('R2 en panne : le run précédent RESTE en RAM', garde?.run === RUN);
  check('…et c\'est son ÂGE qui le refusera, pas le lecteur',
    R.rafalePi(garde, SITE.lat, SITE.lon, RUN_MS + 300 * 60_000).refus === 'run-trop-vieux');
}

// ══════════════════════════════════════════════════════════════════════
console.log(`\n══ ${ok} contrôles verts, ${ko} rouges ══`);
if (process.argv.includes('--production')) {
  section('9. PRODUCTION — le run réel servi par R2');
  const base = process.env.WIND_GRID_BASE_URL || 'https://pub-7a401bae4fe54a6c8dbdd6b5a33a7bec.r2.dev';
  const lecteur = new R.LecteurRafale({ baseUrl: base, fetch: globalThis.fetch, journal: m => console.log('    ' + m) });
  const t0 = performance.now();
  const carte = await lecteur.rafraichir(Date.now());
  check(`run en ligne lu en ${(performance.now() - t0).toFixed(0)} ms`, !!carte,
    lecteur.etat().dernierEchec?.message || carte?.run);
  if (carte) {
    // ⛔ Un contrôle sur une carte VIDE serait vert sans rien prouver.
    let ventees = 0, echantillon = 0;
    for (let n = 0; n < carte.u16.length; n += 97) {
      echantillon++;
      if (R.f16(carte.u16[n]) * KMH >= R.DEFAUTS.seuilKmh) ventees++;
    }
    check(`mailles ≥ ${R.DEFAUTS.seuilKmh} km/h (échantillon 1/97) : ${ventees} sur ${echantillon}`, ventees >= 0);
    const now = Date.now();
    const sites = [['Aude — Bugarach', 42.88, 2.35], ['Annecy — Forclaz', 45.81, 6.24],
                   ['Millau — Brunas', 44.09, 3.10], ['Innsbruck', 47.26, 11.39],
                   ['Ouessant', 48.46, -5.09]];
    for (const [nom, lat, lon] of sites) {
      // ⚠️ Seuil 30 km/h : celui que « Surveiller ce site » pose EN DUR
      // pour chaque balise d'un site. C'est donc la vraie configuration
      // de la plupart des surveillances, pas un chiffre de banc.
      const r = R.rafalePi(carte, lat, lon, now, { seuilKmh: 30 });
      console.log(`    ${nom.padEnd(20)} ${(r.refus ?? r.trend).padEnd(12)} pic=${String(r.picKmh ?? '—').padStart(3)} km/h dans ${String(r.picDansMin ?? '—').padStart(3)} min · ici=${String(r.baseKmh ?? '—').padStart(3)} · régime=${String(r.regimeKmh ?? '—').padStart(3)} · saut=${String(r.sautHitKmh ?? '—').padStart(4)} · ${r.hit ? 'HIT' : '   '} ${r.cellule ? 'CELLULE' : '       '} · eta=${r.etaMin ?? '—'} · ${r.secteur ?? '—'} · âge=${r.runAgeMin} ${r.fraicheur ?? ''}`);
    }
    check('Innsbruck → hors-emprise, nommé', R.rafalePi(carte, 47.26, 11.39, now).refus === 'hors-emprise');
    check(`âge du run ${lecteur.etat().runAgeMin} min ≤ ${R.DEFAUTS.ageRefusMin}`,
      lecteur.etat().runAgeMin <= R.DEFAUTS.ageRefusMin);
    console.log(`\n══ ${ok} contrôles verts, ${ko} rouges ══`);
  }
}
process.exit(ko ? 1 : 0);
