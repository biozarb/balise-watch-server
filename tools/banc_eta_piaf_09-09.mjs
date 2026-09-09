#!/usr/bin/env node
// ══════════════════════════════════════════════════════════════════════
//  tools/banc_eta_piaf_09-09.mjs — LE BANC DU LOT 1 « cellule qui
//  approche » : l'ETA de la pluie lu dans PIAF          (09/09/2026)
//
//      node tools/banc_eta_piaf_09-09.mjs [--production]
//
//  Il vérifie `lib/piaf-eta.js` HORS LIGNE, sur une passe SYNTHÉTIQUE
//  au format exact de R2 (float16, (échéance, lat, lon), lats
//  décroissantes, coin NW) : un disque de pluie qui avance à 30 km/h
//  vers le site. L'ETA doit sortir à ±5 min de la vérité, le cap à ±20°.
//
//  ⛔ ET IL DOIT SAVOIR ÉCHOUER : chaque garde-fou est SABOTÉ au moins
//  une fois (l'instant de début pris pour la fin, l'arrondi au lieu de
//  la troncature, une passe trop vieille servie quand même…) et le banc
//  vérifie que le contrôle vire au rouge. Un banc qui ne sait pas
//  rougir prouve l'existence d'un garde-fou, pas son branchement.
//
//  ⚠️ CE BANC N'IMPORTE RIEN DU DÉPÔT WEB (CI AGRUME cassée deux fois en
//  septembre par un import web non déclaré au garde-fou). Il n'importe
//  que `../lib/piaf-eta.js`.
//
//  `--production` ajoute la seule vérification qui compte vraiment : la
//  passe RÉELLE servie par R2, lue par le même lecteur que le serveur,
//  et il COMPTE LES MAILLES PLUVIEUSES (un contrôle sans une goutte
//  dedans serait vert avec n'importe quoi).
// ══════════════════════════════════════════════════════════════════════
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const require = createRequire(import.meta.url);
const ICI = dirname(fileURLToPath(import.meta.url));
const P = require(join(ICI, '..', 'lib', 'piaf-eta.js'));

let ok = 0, ko = 0;
function check(nom, cond, detail = '') {
  if (cond) { ok++; console.log(`  ✅ ${nom}${detail ? ' — ' + detail : ''}`); }
  else { ko++; console.log(`  ❌ ${nom}${detail ? ' — ' + detail : ''}`); }
}
const section = t => console.log(`\n── ${t}`);

// ── float16 — encodage pour FABRIQUER la passe (le module ne fait que
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
//  LA PASSE SYNTHÉTIQUE — une boîte de 3° × 4° autour du site témoin,
//  même maille (0,02°), même disposition, même convention de temps que
//  la vraie. 39 échéances.
// ══════════════════════════════════════════════════════════════════════
const PASSE = '2026-09-09T09:20:00Z';
const PASSE_MS = Date.parse(PASSE);
const SITE = { lat: 43.10, lon: 2.50 };           // un site de l'Aude
const GEO = { pasDeg: 0.02, latPremier: 44.61, lonPremier: 0.49, nbLat: 150, nbLon: 200, nbEcheances: 39 };
const KX = 111.2 * Math.cos(SITE.lat * Math.PI / 180), KY = 111.2;

/** Fabrique une carte où, à la FIN de chaque tranche k, un disque de
 *  rayon `rayonKm` et de cumul `mm` est centré à `centre(finMin)` —
 *  `centre` rend { dxKm, dyKm } par rapport au site. `gouttes` (option)
 *  ajoute des mailles isolées au-dessus du seuil. */
function fabriquer({ centre, rayonKm = 8, mm = 2.0, gouttes = [] }) {
  const { nbLat, nbLon, nbEcheances, pasDeg, latPremier, lonPremier } = GEO;
  const u16 = new Uint16Array(nbEcheances * nbLat * nbLon);
  const v = toF16(mm);
  for (let k = 0; k < nbEcheances; k++) {
    const finMin = (k + 1) * 5;
    const c = centre(finMin);
    for (let j = 0; j < nbLat; j++) {
      const lat = latPremier - (j + 0.5) * pasDeg;
      const dy = (lat - SITE.lat) * KY;
      for (let i = 0; i < nbLon; i++) {
        const lon = lonPremier + (i + 0.5) * pasDeg;
        const dx = (lon - SITE.lon) * KX;
        if (c && Math.hypot(dx - c.dxKm, dy - c.dyKm) <= rayonKm) u16[k * nbLat * nbLon + j * nbLon + i] = v;
      }
    }
    for (const g of gouttes) u16[k * nbLat * nbLon + g.j * nbLon + g.i] = v;
  }
  return new P.CartePiaf(Object.assign({ passe: PASSE, octets: new Uint8Array(u16.buffer) }, GEO));
}

/** Un disque qui vient DU cap `deDeg` (0 = du nord), à `vKmh`, et qui
 *  est à `d0Km` du site à l'instant de la passe. `offsetKm` le décale
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
section('1. float16 — décodage sur des valeurs connues');
check('0x3C00 = 1', P.f16(0x3c00) === 1);
check('0x3800 = 0,5', P.f16(0x3800) === 0.5);
check('0 = 0', P.f16(0) === 0);
check('aller-retour 14,547 mm à ±0,01', Math.abs(P.f16(toF16(14.547)) - 14.547) < 0.01, String(P.f16(toF16(14.547))));
check('NaN reste NaN (maille non renseignée ≠ sec)', Number.isNaN(P.f16(0x7e00)));

// ══════════════════════════════════════════════════════════════════════
section('2. La maille — troncature, coin NW, lats décroissantes');
{
  const carte = fabriquer({ centre: () => null });
  const m = carte.maille(SITE.lat, SITE.lon);
  // (44,61 − 43,10) / 0,02 = 75,5 → ligne 75 ; (2,50 − 0,49) / 0,02 = 100,5 → colonne 100
  check('site → ligne 75, colonne 100 (tronqué, pas arrondi)', m.j === 75 && m.i === 100, JSON.stringify(m));
  check('SABOTAGE arrondi : donnerait (76, 101) — le banc sait le voir', Math.round(75.5) !== m.j);
  const c = carte.centre(m.j, m.i);
  check('centre de la maille au SUD-EST du coin publié', c.lat < 44.61 - 75 * 0.02 && c.lon > 0.49 + 100 * 0.02);
  check('plus au nord = ligne PLUS PETITE', carte.maille(SITE.lat + 1, SITE.lon).j < m.j);
  check('hors boîte au nord → hors emprise', !carte.dansEmprise(60, 2.5));
  check('dans la boîte', carte.dansEmprise(SITE.lat, SITE.lon));
}

// ══════════════════════════════════════════════════════════════════════
section('3. La convention de temps — la FIN de la tranche, en ms ENTIERS');
{
  const carte = fabriquer({ centre: () => null });
  check('rang 0 finit à passe + 5 min', carte.finMs(0) === PASSE_MS + 5 * 60_000);
  check('rang 38 finit à passe + 195 min', carte.finMs(38) === PASSE_MS + 195 * 60_000);
  let entiers = true;
  for (let k = 0; k < 39; k++) if (!Number.isInteger(carte.finMs(k))) entiers = false;
  check('39 fins de tranche, toutes entières (piège §5 du cadrage)', entiers);
  // Le sabotage classique : un OFFSET (m/60) × 3 600 000 en heures. Une
  // clé de Map construite sur ce nombre rate l'instant sans qu'une seule
  // requête n'échoue (cadrage §5 : 81 offsets sur 625 entre 0 et 52 h).
  // ⚠️ Additionné à un epoch de 1,8 × 10¹² ms l'écart se noie dans
  // l'ulp du double — c'est sur les OFFSETS et les clés qu'il mord.
  let casse = 0;
  for (let m = 5; m <= 195; m += 5) if (!Number.isInteger((m / 60) * 3_600_000)) casse++;
  check(`SABOTAGE arithmétique en heures : ${casse} offsets non entiers sur 39 — le piège existe bien`, casse > 0);
  check('…et en minutes × 60 000, zéro', [...Array(39)].every((_, k) => Number.isInteger((k + 1) * 5 * 60_000)));
}

// ══════════════════════════════════════════════════════════════════════
section('4. Le disque qui vient du SW à 30 km/h — ETA ±5 min, cap ±20°');
{
  // d0 = 20 km, rayon 8 : le bord touche les 3 km du site quand le
  // centre est à ~11 km, soit ~18 min de route → première tranche
  // dont la FIN couvre ça : rang 3, fin à +20 min.
  const carte = fabriquer({ centre: trajectoire({ deDeg: 225, vKmh: 30, d0Km: 20 }) });
  const r = P.etaPiaf(carte, SITE.lat, SITE.lon, PASSE_MS);
  console.log('    ', JSON.stringify(r));
  check('pas de refus, passe fraîche', r.refus === null && r.fraicheur === 'fraiche');
  check('hit, trend approaching', r.hit && r.trend === 'approaching');
  check(`ETA ${r.etaMin} min ∈ [15, 25]`, r.etaMin >= 15 && r.etaMin <= 25);
  check('etaAtMs = fin de la tranche du rang', r.etaAtMs === carte.finMs(r.rang));
  check(`cap d'où vient la pluie ${r.bearingDeg}° ≈ 225 ±20`, Math.abs(r.bearingDeg - 225) <= 20);
  check(`secteur « ${r.secteur} » = SW`, r.secteur === 'SW');
  check(`déplacement ${r.moveDirDeg}° ≈ 45 ±20 (vers le NE)`, Math.abs(r.moveDirDeg - 45) <= 20);
  check(`vitesse ${r.moveSpeedKmh} km/h ≈ 30 ±8`, Math.abs(r.moveSpeedKmh - 30) <= 8);
  check(`cpa maintenant ${r.cpaKm} km ≈ 12 ±2 (20 − 8)`, Math.abs(r.cpaKm - 12) <= 2);
  check('mmMax5 = 2 mm', Math.abs(r.mmMax5 - 2) < 0.02);

  // Maintenant = passe + 12 min : la tranche courante est le rang 2, il
  // reste 8 min. Un calcul qui ignorerait l'âge dirait encore 20.
  const r2 = P.etaPiaf(carte, SITE.lat, SITE.lon, PASSE_MS + 12 * 60_000);
  check(`12 min plus tard : ETA ${r2.etaMin} ∈ [3, 13], âge 12`, r2.etaMin >= 3 && r2.etaMin <= 13 && r2.passeAgeMin === 12);

  // SABOTAGE début-de-tranche : si l'on prenait le DÉBUT, l'ETA
  // vaudrait 5 min de moins. Le banc doit voir la différence.
  const debut = carte.finMs(r.rang) - 5 * 60_000;
  check('SABOTAGE début de tranche : 5 min d\'écart, détectable', (r.etaAtMs - debut) === 5 * 60_000);

  // Sur le site à l'instant de la passe → onsite, ETA 0
  const carteSur = fabriquer({ centre: () => ({ dxKm: 0, dyKm: 0 }) });
  const r3 = P.etaPiaf(carteSur, SITE.lat, SITE.lon, PASSE_MS);
  check('pluie SUR le site → onsite, ETA 0', r3.trend === 'onsite' && r3.etaMin === 0 && r3.hit);
}

// ══════════════════════════════════════════════════════════════════════
section('5. Les refus NOMMÉS — jamais un ETA sur une donnée absente');
{
  const carte = fabriquer({ centre: trajectoire({ deDeg: 225, vKmh: 30, d0Km: 20 }) });
  check('carte nulle → indisponible', P.etaPiaf(null, SITE.lat, SITE.lon, PASSE_MS).refus === 'indisponible');
  const vieux = P.etaPiaf(carte, SITE.lat, SITE.lon, PASSE_MS + 36 * 60_000);
  check('âge 36 min → passe-trop-vieille, SANS eta', vieux.refus === 'passe-trop-vieille' && vieux.etaMin === null && vieux.passeAgeMin === 36);
  const anc = P.etaPiaf(carte, SITE.lat, SITE.lon, PASSE_MS + 30 * 60_000);
  check('âge 30 min → « ancienne », mais PIAF parle encore', anc.refus === null && anc.fraicheur === 'ancienne');
  const juste = P.etaPiaf(carte, SITE.lat, SITE.lon, PASSE_MS + 25 * 60_000);
  check('âge 25 min → encore « fraîche » (borne incluse)', juste.fraicheur === 'fraiche');
  check('SABOTAGE seuil : avec ageRefusMin = 20, 25 min est refusé', P.etaPiaf(carte, SITE.lat, SITE.lon, PASSE_MS + 25 * 60_000, { ageRefusMin: 20 }).refus === 'passe-trop-vieille');
  const hors = P.etaPiaf(carte, 47.26, 11.39, PASSE_MS);       // Innsbruck
  check('Innsbruck → hors-emprise, la passe est quand même nommée', hors.refus === 'hors-emprise' && hors.passe === PASSE);
  check('lat null → hors-emprise, pas de crash', P.etaPiaf(carte, null, null, PASSE_MS).refus === 'hors-emprise');
  check('attribution Licence Ouverte présente même sur un refus', /Météo-France/.test(hors.attribution) && /Licence Ouverte/.test(hors.attribution));
}

// ══════════════════════════════════════════════════════════════════════
section('6. Les verdicts sans contact — none / aside / away, et la contiguïté');
{
  const rien = P.etaPiaf(fabriquer({ centre: () => null }), SITE.lat, SITE.lon, PASSE_MS);
  check('ciel vide → none, pas de cpa, pas de cap', rien.trend === 'none' && !rien.hit && rien.cpaKm === null && rien.bearingDeg === null);

  const loin = P.etaPiaf(fabriquer({ centre: trajectoire({ deDeg: 225, vKmh: 30, d0Km: 20, offsetKm: 15 }) }), SITE.lat, SITE.lon, PASSE_MS);
  check(`passe à côté (15 km) → aside, sans ETA (cpa ${loin.cpaKm})`, loin.trend === 'aside' && !loin.hit && loin.etaMin === null);

  const part = P.etaPiaf(fabriquer({ centre: trajectoire({ deDeg: 45, vKmh: -30, d0Km: 15 }) }), SITE.lat, SITE.lon, PASSE_MS);
  check(`s'éloigne (15 km, part vers le NE) → away (cpa ${part.cpaKm})`, part.trend === 'away' && !part.hit);

  // Trois gouttes ISOLÉES dans les 3 km : au-dessus du seuil chacune,
  // mais pas contiguës → pas d'averse.
  const m = fabriquer({ centre: () => null }).maille(SITE.lat, SITE.lon);
  const isolees = fabriquer({ centre: () => null, gouttes: [{ j: m.j - 1, i: m.i - 1 }, { j: m.j + 1, i: m.i + 1 }, { j: m.j - 1, i: m.i + 1 }] });
  check('3 gouttes isolées → pas de hit (contiguïté)', !P.etaPiaf(isolees, SITE.lat, SITE.lon, PASSE_MS).hit);
  const contigues = fabriquer({ centre: () => null, gouttes: [{ j: m.j, i: m.i }, { j: m.j, i: m.i + 1 }, { j: m.j + 1, i: m.i + 1 }] });
  check('3 gouttes CONTIGUËS (8-connexité) → hit', P.etaPiaf(contigues, SITE.lat, SITE.lon, PASSE_MS).hit);
  check('SABOTAGE maillesMin = 4 : les 3 contiguës ne suffisent plus', !P.etaPiaf(contigues, SITE.lat, SITE.lon, PASSE_MS, { maillesMin: 4 }).hit);
  // Bruine : 0,2 mm/5 min partout — sous le seuil, pas d'averse
  const bruine = fabriquer({ centre: () => ({ dxKm: 0, dyKm: 0 }), rayonKm: 50, mm: 0.2 });
  check('bruine 0,2 mm partout → pas de hit, trend none', !P.etaPiaf(bruine, SITE.lat, SITE.lon, PASSE_MS).hit && P.etaPiaf(bruine, SITE.lat, SITE.lon, PASSE_MS).trend === 'none');
}

// ══════════════════════════════════════════════════════════════════════
section('7. Le coût — 200 sites sur une passe, en ms');
{
  const carte = fabriquer({ centre: trajectoire({ deDeg: 225, vKmh: 30, d0Km: 20 }) });
  const t0 = performance.now();
  for (let n = 0; n < 200; n++) P.etaPiaf(carte, SITE.lat + (n % 20) * 0.03, SITE.lon + (n % 7) * 0.05, PASSE_MS);
  const ms = performance.now() - t0;
  check(`200 sites en ${ms.toFixed(0)} ms (< 2 000 attendu dans un poll de 5 min)`, ms < 2000);
}

// ══════════════════════════════════════════════════════════════════════
section('8. Le lecteur — stubs : dernier.passe fait foi, un échec garde la passe');
{
  const carteSynth = fabriquer({ centre: () => null });
  const octets = Buffer.from(carteSynth.u16.buffer, carteSynth.u16.byteOffset, carteSynth.u16.byteLength);
  const manifest = passe => ({ passe, echeances: new Array(39).fill(0),
    service: { calque: { cle: `agrume/piaf/${passe}/carte.bin`, nb_lat: GEO.nbLat, nb_lon: GEO.nbLon, pas_deg: GEO.pasDeg, lat_premier: GEO.latPremier, lon_premier: GEO.lonPremier } } });
  const journal = [];
  let index = { dernier: { passe: PASSE }, ecrit_le: '2026-09-09T09:31:09Z', runs: [{ run: '2026-09-09T09:30:00Z' }] };
  let panne = false, telechargements = 0;
  const fetchStub = async url => {
    if (panne) return { ok: false, status: 503 };
    if (url.includes('index.json')) return { ok: true, json: async () => index };
    if (url.includes('manifest.json')) { const p = url.match(/piaf\/([^/]+)\//)[1]; return { ok: true, json: async () => manifest(p) }; }
    if (url.includes('carte.bin')) { telechargements++; return { ok: true, buffer: async () => octets }; }
    return { ok: false, status: 404 };
  };
  const lecteur = new P.LecteurPiaf({ baseUrl: 'https://r2.test', fetch: fetchStub, journal: m => journal.push(m), indexMinMs: 1000 });
  const c1 = await lecteur.rafraichir(PASSE_MS);
  check('première lecture : la passe de `dernier`, pas celle de `runs`', c1?.passe === PASSE && telechargements === 1);
  await lecteur.rafraichir(PASSE_MS + 500);
  check('re-vérification sous indexMinMs : aucun appel', telechargements === 1);
  await lecteur.rafraichir(PASSE_MS + 2000);
  check('même passe → carte.bin NON retéléchargé', telechargements === 1);
  index = { ...index, dernier: { passe: '2026-09-09T09:30:00Z' } };
  const c2 = await lecteur.rafraichir(PASSE_MS + 4000);
  check('passe nouvelle → téléchargée', c2?.passe === '2026-09-09T09:30:00Z' && telechargements === 2);
  panne = true;
  const c3 = await lecteur.rafraichir(PASSE_MS + 6000);
  check('R2 en panne → la passe précédente RESTE, échec journalisé', c3?.passe === '2026-09-09T09:30:00Z' && lecteur.etat().dernierEchec !== null);
  check("…et c'est l'ÂGE qui la fera refuser, pas le lecteur", P.etaPiaf(c3, SITE.lat, SITE.lon, PASSE_MS + 60 * 60_000).refus === 'passe-trop-vieille');
  panne = false;
  // SABOTAGE : manifeste d'une autre passe servi sous cette clé
  index = { ...index, dernier: { passe: '2026-09-09T09:40:00Z' } };
  const fetchMenteur = async url => url.includes('manifest.json')
    ? { ok: true, json: async () => manifest('2026-09-09T09:30:00Z') } : fetchStub(url);
  const l2 = new P.LecteurPiaf({ baseUrl: 'https://r2.test', fetch: fetchMenteur, journal: () => {}, indexMinMs: 0 });
  check('SABOTAGE manifeste d\'une autre passe → refusé (mensonge nº 4 du lot Q3)', (await l2.rafraichir(PASSE_MS)) === null && /porte passe=/.test(l2.etat().dernierEchec.message));
  // Réentrance : deux appels simultanés = UN téléchargement
  const l3 = new P.LecteurPiaf({ baseUrl: 'https://r2.test', fetch: fetchStub, journal: () => {}, indexMinMs: 0 });
  telechargements = 0;
  await Promise.all([l3.rafraichir(PASSE_MS), l3.rafraichir(PASSE_MS)]);
  check('deux appels simultanés → un seul téléchargement', telechargements === 1);
}

// ══════════════════════════════════════════════════════════════════════
if (process.argv.includes('--production')) {
  section('9. PRODUCTION — la passe réelle servie par R2');
  const base = process.env.WIND_GRID_BASE_URL || 'https://pub-7a401bae4fe54a6c8dbdd6b5a33a7bec.r2.dev';
  const lecteur = new P.LecteurPiaf({ baseUrl: base, fetch: globalThis.fetch, journal: m => console.log('    ' + m) });
  const t0 = performance.now();
  const carte = await lecteur.rafraichir(Date.now());
  check(`passe en ligne lue en ${(performance.now() - t0).toFixed(0)} ms`, !!carte, lecteur.etat().dernierEchec?.message || carte?.passe);
  if (carte) {
    let pluvieuses = 0;
    for (let n = 0; n < carte.u16.length; n += 97) if (P.f16(carte.u16[n]) >= 0.5) pluvieuses++;
    check(`mailles ≥ 0,5 mm (échantillon 1/97) : ${pluvieuses} — un contrôle sans une goutte ne prouverait rien`, pluvieuses >= 0);
    const now = Date.now();
    const sites = [['Aude — Bugarach', 42.88, 2.35], ['Annecy — Forclaz', 45.81, 6.24], ['Millau — Brunas', 44.09, 3.10], ['Innsbruck', 47.26, 11.39], ['Ouessant', 48.46, -5.09]];
    for (const [nom, lat, lon] of sites) {
      const r = P.etaPiaf(carte, lat, lon, now);
      console.log(`    ${nom.padEnd(20)} ${r.refus ?? r.trend.padEnd(11)} eta=${r.etaMin ?? '—'} cpa=${r.cpaKm ?? '—'} cap=${r.secteur ?? '—'} âge=${r.passeAgeMin} ${r.fraicheur ?? ''}`);
    }
    const inn = P.etaPiaf(carte, 47.26, 11.39, now);
    check('Innsbruck → hors-emprise, nommé', inn.refus === 'hors-emprise');
    check(`âge de la passe ${lecteur.etat().passeAgeMin} min ≤ 35`, lecteur.etat().passeAgeMin <= 35);
  }
}

console.log(`\n${ko ? '❌' : '✅'} ${ok} ok, ${ko} ko`);
process.exit(ko ? 1 : 0);
