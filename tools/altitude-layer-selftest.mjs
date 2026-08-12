#!/usr/bin/env node
// ══════════════════════════════════════════════════════════════════════
//  tools/altitude-layer-selftest.mjs — LE BANC DE PARITÉ Python ↔ TypeScript
//                                                          (12/08/2026)
//
//      node --experimental-strip-types tools/altitude-layer-selftest.mjs \
//           --fixture /tmp/fixture-calque.json \
//           [--tampon /tmp/e03.bin --zsol /tmp/zsol.bin \
//            --manifeste /tmp/manifest-e.json]
//
//  ⚠️⚠️ CE BANC EXISTE PARCE QU'IL Y A DEUX IMPLÉMENTATIONS DE LA MÊME
//  INTERPOLATION, ET QUE C'EST INÉVITABLE. Le calque s'interpole dans le
//  navigateur — c'est ce qui rend le curseur d'altitude gratuit — donc
//  `agrume/calque.py` et `web/src/lib/altitudeLayer.ts` calculent la
//  même chose, séparément.
//
//  Le README d'AGRUME dit ce que ça coûte quand on laisse deux
//  implémentations vivre côte à côte : « Deux implémentations d'un même
//  fit divergeraient — c'est le défaut payé deux fois le 10/08 » avec
//  `gfDetectModel`. La réponse retenue là-bas était de n'en écrire
//  qu'une. Ici c'est impossible. La réponse est donc de MESURER l'écart
//  à chaque banc plutôt que de faire confiance :
//
//      Python (agrume/calque.py::fixture) ──▶ vecteurs de référence
//                                              │
//      TypeScript (altitudeLayer.ts) ──────────┴──▶ écart EXIGÉ NUL
//
//  ⓘ Sans `--tampon`, seule l'interpolation est vérifiée. Avec, on
//  vérifie AUSSI le décodage float16 et le Range — c'est-à-dire tout le
//  chemin qu'un navigateur parcourt réellement.
// ══════════════════════════════════════════════════════════════════════
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ici = dirname(fileURLToPath(import.meta.url));
const MOD = join(ici, '..', '..', 'web', 'src', 'lib', 'altitudeLayer.ts');

const L = await import(process.env.BW_LAYER_MODULE || MOD);

const arg = (n, d = null) => {
  const k = process.argv.indexOf(`--${n}`);
  return k > 0 && process.argv[k + 1] ? process.argv[k + 1] : d;
};

let echecs = 0;
const verifier = (nom, ok, detail = '') => {
  console.log(`  ${ok ? '✓' : '✗'} ${nom}${detail ? `   ${detail}` : ''}`);
  if (!ok) echecs++;
};

// ══════════════════════════════════════════════════════════════════════
console.log('── 1. Le décodage float16, sur les valeurs qui cassent ──');
// ⚠️ Ces cas ne sont pas décoratifs : chacun est une façon de rendre un
// nombre plausible. Un décodeur qui rate les sous-normaux rend 0 — du
// vent nul, parfaitement crédible sur une carte.
const CAS16 = [
  [0x0000, 0, 'zéro'],
  [0x8000, -0, 'zéro négatif'],
  [0x3c00, 1, 'un'],
  [0xbc00, -1, 'moins un'],
  [0x3555, 0.333251953125, '1/3 arrondi au float16 le plus proche'],
  [0x4900, 10, 'dix'],
  [0x0001, 5.960464477539063e-8, '⚠️ le plus petit SOUS-NORMAL'],
  [0x03ff, 6.097555160522461e-5, '⚠️ le plus grand sous-normal'],
  [0x0400, 6.103515625e-5, 'le plus petit normal'],
  [0x7bff, 65504, 'le plus grand fini'],
];
for (const [bits, attendu, quoi] of CAS16) {
  const got = L.decodeFloat16(bits);
  verifier(`0x${bits.toString(16).padStart(4, '0')} → ${quoi}`, got === attendu,
    got === attendu ? '' : `${got} au lieu de ${attendu}`);
}
verifier('⛔ NaN reste NaN (c\'est lui qui porte « ce niveau n\'existe pas »)',
  Number.isNaN(L.decodeFloat16(0x7e00)));
verifier('l\'infini reste l\'infini, il ne devient pas 65504',
  L.decodeFloat16(0x7c00) === Infinity);

// ══════════════════════════════════════════════════════════════════════
console.log('\n── 2. L\'encadrement, et la borne haute que JS ne signale pas ──');
const NIV = [10, 20, 35, 50, 75, 100, 150, 200, 250, 375, 500, 625, 750, 875,
  1000, 1125, 1250, 1375, 1500, 1750, 2000, 2250, 2500, 2750, 3000];
let tousZero = true;
for (let k = 0; k < NIV.length - 1; k++) {
  const r = L.encadrer(NIV, NIV[k]);
  if (r.k !== k || r.w !== 0) tousZero = false;
}
verifier('sur CHAQUE niveau, l\'indice est le bon et le poids vaut 0',
  tousZero);
const haut = L.encadrer(NIV, 3000);
verifier('⚠️ h = 3000 (le dernier niveau) ne sort PAS du tableau — sans la '
  + 'borne, JS rendrait undefined puis NaN, sans un mot',
  haut.k === NIV.length - 2 && haut.w === 1, `k=${haut.k} w=${haut.w}`);
const mid = L.encadrer(NIV, 15);
verifier('au milieu de 10 et 20, le poids vaut 0,5',
  mid.k === 0 && mid.w === 0.5);

console.log('\n── 3. Le mélange ne se laisse pas contaminer par NaN ──');
verifier('w = 0 et niveau supérieur ABSENT → le niveau inférieur est servi',
  L.melanger(7.5, NaN, 0) === 7.5);
verifier('w = 1 et niveau inférieur ABSENT → le supérieur est servi',
  L.melanger(NaN, 7.5, 1) === 7.5);
verifier('mais ENTRE les deux, le trou reste un trou',
  Number.isNaN(L.melanger(7.5, NaN, 0.5)));

console.log('\n── 4. La convention de direction, clouée par une VALEUR ──');
verifier('u = +10 m/s → 270° (le vent vient de l\'ouest)',
  Math.abs(L.direction(10, 0) - 270) < 1e-9);
verifier('v = +10 m/s → 180°', Math.abs(L.direction(0, 10) - 180) < 1e-9);
// ⛔ Le cas qui justifie l'interpolation par composantes.
const a = { u: 10 * Math.cos((Math.PI / 180) * (270 - 350)), v: 10 * Math.sin((Math.PI / 180) * (270 - 350)) };
const b = { u: 10 * Math.cos((Math.PI / 180) * (270 - 10)), v: 10 * Math.sin((Math.PI / 180) * (270 - 10)) };
const dMil = L.direction(L.melanger(a.u, b.u, 0.5), L.melanger(a.v, b.v, 0.5));
verifier('⛔ 350° et 010° donnent 0° au milieu, PAS 180° — c\'est POURQUOI '
  + 'on interpole u et v et jamais l\'angle',
  Math.min(Math.abs(dMil), Math.abs(dMil - 360)) < 1e-6, `${dMil.toFixed(3)}°`);

// ══════════════════════════════════════════════════════════════════════
console.log('\n── 5. LE CHEMIN COMPLET : tampon brut → Range → décodage ──');
const tampon = arg('tampon'), zsolF = arg('zsol'), manF = arg('manifeste');
let man = null, u = null, v = null, zsol = null;
if (!(tampon && zsolF && manF)) {
  console.log('  ⚠️ --tampon / --zsol / --manifeste absents : NI le décodage '
    + 'du tampon réel NI la parité avec Python ne sont vérifiés.');
  echecs++;
} else {
  man = JSON.parse(readFileSync(manF, 'utf-8'));
  const octets = readFileSync(tampon);
  const buf = octets.buffer.slice(octets.byteOffset,
    octets.byteOffset + octets.byteLength);
  const zo = readFileSync(zsolF);
  zsol = new Float32Array(zo.buffer.slice(zo.byteOffset,
    zo.byteOffset + zo.byteLength));

  verifier('le tampon fait exactement la taille annoncée par le manifeste',
    buf.byteLength === man.service.octets_par_echeance,
    `${buf.byteLength} octets`);

  const tU = man.service.tranches.u, tV = man.service.tranches.v;
  verifier('⚠️ u et v sont CONTIGUS et EN TÊTE — c\'est ce qui rend le Range '
    + 'utile', tU.offset === 0 && tV.offset === tU.octets,
    `u@${tU.offset} v@${tV.offset}, Range = bytes=0-${tV.offset + tV.octets - 1}`);

  // Le Range que le navigateur demande réellement.
  const debut = tU.offset, fin = tV.offset + tV.octets;
  const partiel = buf.slice(debut, fin);
  verifier('le Range u+v ne tire que 40 % de l\'objet',
    partiel.byteLength / buf.byteLength < 0.45,
    `${(partiel.byteLength / 1e3).toFixed(0)} Ko sur `
    + `${(buf.byteLength / 1e3).toFixed(0)} Ko`);

  u = L.decoderTranche(partiel, tU, debut);
  v = L.decoderTranche(partiel, tV, debut);
  verifier('décodé depuis le Range, u a la bonne longueur',
    u.length === man.niveaux_m_sol.length * man.axes.nb_lat * man.axes.nb_lon);

  // ⚠️ Décoder l'objet ENTIER doit donner la même chose que décoder le
  // Range : c'est le contrôle qui attrape un `offsetBase` oublié.
  const uEntier = L.decoderTranche(buf, tU, 0);
  let identique = u.length === uEntier.length;
  for (let k = 0; identique && k < u.length; k++) {
    if (!(u[k] === uEntier[k]
      || (Number.isNaN(u[k]) && Number.isNaN(uEntier[k])))) identique = false;
  }
  verifier('⛔ Range et objet entier donnent le MÊME tableau (un offsetBase '
    + 'oublié rendrait une carte décalée, pas une erreur)', identique);
}

// ══════════════════════════════════════════════════════════════════════
console.log('\n── 6. PARITÉ avec Python, sur les vecteurs de référence ──');
const chemin = arg('fixture');
if (!chemin || !man) {
  console.log('  ⚠️ pas de --fixture (ou pas de tampon) : LA PARITÉ N\'A PAS '
    + 'ÉTÉ VÉRIFIÉE. Générer les vecteurs avec agrume/calque.py::fixture(). '
    + 'Ne PAS lire l\'absence d\'échec comme un succès.');
  echecs++;
} else {
  const fx = JSON.parse(readFileSync(chemin, 'utf-8'));
  const niveaux = fx.niveaux_m_sol;
  const nbLon = man.axes.nb_lon, nbCol = man.axes.nb_lat * nbLon;
  let pireU = 0, pireV = 0, pireW = 0, nServis = 0, nMasq = 0;
  let desaccordMasque = 0, desaccordK = 0, pireZsol = 0, premier = null;

  for (const c of fx.cas) {
    const idx = c.j * nbLon + c.i;
    pireZsol = Math.max(pireZsol, Math.abs(zsol[idx] - c.zsol));
    const h = c.altitudeASLM - zsol[idx];
    const servable = h >= niveaux[0] && h <= niveaux[niveaux.length - 1];
    if (c.u === null) {
      nMasq++;
      if (servable) { desaccordMasque++; premier = premier || c; }
      continue;
    }
    if (!servable) { desaccordMasque++; premier = premier || c; continue; }
    const { k, w } = L.encadrer(niveaux, h);
    if (k !== c.k) { desaccordK++; premier = premier || c; }
    pireW = Math.max(pireW, Math.abs(w - c.w));
    const gu = L.melanger(u[k * nbCol + c.i + c.j * nbLon],
      u[(k + 1) * nbCol + c.i + c.j * nbLon], w);
    const gv = L.melanger(v[k * nbCol + c.i + c.j * nbLon],
      v[(k + 1) * nbCol + c.i + c.j * nbLon], w);
    pireU = Math.max(pireU, Math.abs(gu - c.u));
    pireV = Math.max(pireV, Math.abs(gv - c.v));
    nServis++;
  }

  verifier('le zsol décodé côté JS est celui que Python a utilisé',
    pireZsol === 0, `écart max ${pireZsol}`);
  verifier('les deux implémentations masquent EXACTEMENT les mêmes colonnes',
    desaccordMasque === 0,
    `${nMasq} masqués côté Python · ${desaccordMasque} désaccord(s)`
    + (premier ? ` · 1er : j=${premier.j} i=${premier.i} A=${premier.altitudeASLM}` : ''));
  verifier('elles encadrent avec le MÊME niveau inférieur',
    desaccordK === 0, `${desaccordK} désaccord(s) sur ${nServis}`);
  verifier('et avec le MÊME poids, à l\'octet près',
    pireW === 0, `écart max ${pireW}`);
  verifier(`⛔ LA PARITÉ : u et v identiques sur les ${nServis} cas servis`,
    pireU === 0 && pireV === 0, `écart max u ${pireU} · v ${pireV}`);
  verifier('la fixture porte des cas servis ET des cas masqués',
    nServis > 0 && nMasq > 0, `${nServis} servis · ${nMasq} masqués`);
  console.log(`  ⓘ fixture du run ${fx.run}, échéance ${fx.echeanceH} h`);
}

// ══════════════════════════════════════════════════════════════════════
console.log('\n── 7. L\'INVARIANT DU LOT, rejoué en JavaScript ──');
if (!man) {
  console.log('  ⚠️ pas de tampon : invariant NON vérifié.');
  echecs++;
} else {
  const niveaux = man.niveaux_m_sol;
  const nbCol = man.axes.nb_lat * man.axes.nb_lon;
  let pire = 0, cas = 0;
  for (let k = 0; k < niveaux.length; k++) {
    for (let c = 0; c < nbCol; c++) {
      const h = niveaux[k];                       // A = zsol[c] + niveau
      const { k: kk, w } = L.encadrer(niveaux, h);
      const got = L.melanger(u[kk * nbCol + c], u[(kk + 1) * nbCol + c], w);
      const brut = u[k * nbCol + c];
      if (Number.isFinite(brut)) { pire = Math.max(pire, Math.abs(got - brut)); cas++; }
    }
  }
  verifier('altitude tombant sur un niveau → le niveau BRUT, écart nul',
    pire === 0, `${cas} cas · écart max ${pire}`);

  console.log('\n     couverture calculée par le TypeScript :');
  for (const A of [1000, 2000, 3000, 4000]) {
    const c = L.calculerCalque(man, u, v, zsol, A).couverture;
    console.log(`       ${String(A).padStart(5)} m : servi `
      + `${(100 * c.servi).toFixed(1).padStart(5)} %  ·  relief `
      + `${(100 * c.relief).toFixed(1).padStart(5)} %  ·  plafond `
      + `${(100 * c.auDessusDuPlafond).toFixed(1).padStart(5)} %  ·  bande basse `
      + `${(100 * c.sousPremierNiveau).toFixed(2)} %`);
  }
}

console.log(`\n  calque altitude (JS) : ${echecs ? `ÉCHEC (${echecs})` : 'OK'}`);
process.exit(echecs ? 1 : 0);
