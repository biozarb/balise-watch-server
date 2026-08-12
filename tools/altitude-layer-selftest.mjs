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

// ══════════════════════════════════════════════════════════════════════
console.log('\n── 8. ⛔ RIEN N\'EST CODÉ EN DUR CÔTÉ CLIENT ──');
// ⚠️ CE TEST EST BEHAVIOURAL, PAS UN grep. On donne au module un
// manifeste DÉLIBÉRÉMENT DIFFÉRENT — 3 niveaux au lieu de 25, une grille
// 2×3 au lieu de 61×85, des paramètres dans un autre ORDRE — et on exige
// qu'il le suive. Si la liste des niveaux, la taille de la grille ou
// l'offset de `v` étaient écrits en dur ici, ce bloc casserait.
//
// C'est la leçon de LEVELS, dupliqué entre arome-wind/ingest.py et
// config.ts : « les deux listes doivent bouger ensemble, sinon le
// sélecteur d'altitude propose des paliers dont les tuiles n'existent
// plus (404 silencieux, calque vide) ». Un grep sur le source dirait
// seulement que le chiffre n'y est pas écrit ; celui-ci dit que le
// module OBÉIT au manifeste.
{
  const NIV2 = [5, 50, 500];                 // ni 10, ni 3000
  const NJ = 2, NI = 3, NC = NJ * NI;
  const octetsParParam = NIV2.length * NC * 2;
  // ⛔ v EN PREMIER, u en second : l'ordre inverse du produit réel.
  const man2 = {
    run: '2026-01-01T00:00:00Z', domaine: 'banc', grille: '0025',
    echeances: [0], niveaux_m_sol: NIV2,
    parametres: [{ nom: 'v' }, { nom: 'u' }],
    axes: {
      nb_lat: NJ, nb_lon: NI,
      lat_premier: 46, lat_dernier: 45,       // DÉCROISSANTES, comme AROME
      lon_premier: 5, lon_dernier: 7, sens: 'lats DÉCROISSANTES',
    },
    retention_runs: 3,
    service: {
      cle_echeance: 'x/{domaine}/{run}/e{step:02d}.bin',
      cle_zsol: 'x/{domaine}/{run}/zsol.bin',
      disposition_tampon: '(parametre, niveau, lat, lon) float16',
      encodage: 'aucun',
      tranches: {
        v: { offset: 0, octets: octetsParParam },
        u: { offset: octetsParParam, octets: octetsParParam },
      },
      octets_par_echeance: 2 * octetsParParam,
    },
  };
  // zsol volontairement étalé : 0 m et 400 m.
  const zsol2 = new Float32Array([0, 0, 0, 400, 400, 400]);
  // u = 10 partout au niveau 500 m, 0 aux deux autres. v = 0 partout.
  const u2 = new Float32Array(NIV2.length * NC);
  const v2 = new Float32Array(NIV2.length * NC);
  u2.fill(0); v2.fill(0);
  for (let c = 0; c < NC; c++) u2[2 * NC + c] = 10;   // niveau 500 m

  const b = L.bornesAltitude(man2, zsol2);
  verifier('les bornes du sélecteur SUIVENT le manifeste (5 → 900 m ici, '
    + 'pas 10 → 3000)', b.minM === 5 && b.maxM === 900 && b.pleinM === 500,
    `min ${b.minM} · plein ${b.pleinM} · max ${b.maxM}`);

  // À 500 m ASL : les colonnes de sol 0 sont pile sur le niveau 500 →
  // u = 10. Celles de sol 400 sont à h = 100, entre 50 et 500 → u = 10 ×
  // (100−50)/(500−50) = 1,111…
  const c500 = L.calculerCalque(man2, u2, v2, zsol2, 500);
  // ⚠️ `Math.fround` ET PAS UNE TOLÉRANCE. `calculerCalque` écrit dans un
  // Float32Array — exactement comme `calque()` côté Python fait
  // `.astype(np.float32)`. Comparer à la valeur float64 avec un « à peu
  // près » masquerait le jour où l'un des deux cesserait de narrower.
  // Le §6 vérifie la parité en float64 (sur `melanger`) ; celui-ci
  // vérifie que le narrowing final est le même des deux côtés.
  const attendu = Math.fround(10 * (100 - 50) / (500 - 50));
  verifier('sur le niveau haut du manifeste, la valeur brute est rendue',
    c500.u[0] === 10 && c500.u[1] === 10 && c500.u[2] === 10);
  verifier('et ailleurs elle est interpolée SUR CE manifeste, pas sur les '
    + '25 niveaux du produit réel — au float32 près, exactement comme Python',
    c500.u[3] === attendu, `${c500.u[3]} attendu ${attendu}`);
  verifier('la grille rendue fait 2×3, pas 61×85',
    c500.nbLat === NJ && c500.nbLon === NI && c500.couverture.nbColonnes === NC);

  // Au-dessus du plafond de la colonne basse (0 + 500) mais sous celui de
  // la haute (400 + 500) : masquage MIXTE, qui n'existe que si le module
  // lit vraiment `niveaux_m_sol`.
  const c700 = L.calculerCalque(man2, u2, v2, zsol2, 700);
  verifier('⛔ le plafond suit le relief SELON CE manifeste : colonnes '
    + 'basses au-dessus du plafond, hautes encore servies',
    c700.masque[0] === L.MASQUE.PLAFOND && c700.masque[3] === L.MASQUE.SERVI,
    `${c700.masque[0]} / ${c700.masque[3]}`);
  const c2 = L.calculerCalque(man2, u2, v2, zsol2, 2);
  verifier('et le premier niveau aussi (2 m < 5 m → bande basse)',
    c2.masque[0] === L.MASQUE.BAS);

  // Le Range doit suivre l'ORDRE PUBLIÉ : ici v est en tête.
  let urlVue = null, headersVus = null;
  const faux = async (url, opts) => {
    urlVue = url; headersVus = opts.headers;
    return { ok: true, status: 206, arrayBuffer: async () => new ArrayBuffer(2 * octetsParParam) };
  };
  await L.chargerTranches('https://exemple', man2, 3, ['u', 'v'], faux);
  verifier('⛔ le Range couvre les deux tranches DANS L\'ORDRE DU '
    + 'MANIFESTE (v@0, u@' + octetsParParam + ')',
    headersVus.Range === `bytes=0-${2 * octetsParParam - 1}`,
    headersVus.Range);
  verifier('et la clé est construite depuis `service.cle_echeance`, avec '
    + 'l\'échéance sur 2 chiffres',
    urlVue === 'https://exemple/x/banc/2026-01-01T00:00:00Z/e03.bin', urlVue);

  // L'adaptateur vers WindGridLayer.
  const wg = L.versWindGrid(man2, c500, 0);
  verifier('l\'adaptateur rend un point par colonne, sans en inventer',
    wg.points.length === NC);
  verifier('⚠️ et il respecte le SENS DÉCROISSANT des latitudes — une '
    + 'carte retournée ressemble toujours à une carte',
    wg.points[0].lat === 46 && wg.points[NI].lat === 45,
    `${wg.points[0].lat} puis ${wg.points[NI].lat}`);
  verifier('une colonne masquée sort en null, pas en vent nul',
    L.versWindGrid(man2, c700, 0).points[0].speed[0] === null);
  verifier('u = +10 m/s ressort à 270° et 36 km/h',
    Math.abs(wg.points[0].dir[0] - 270) < 1e-9
    && Math.abs(wg.points[0].speed[0] - 36) < 1e-9,
    `${wg.points[0].dir[0].toFixed(2)}° · ${wg.points[0].speed[0].toFixed(2)} km/h`);
}

console.log(`\n  calque altitude (JS) : ${echecs ? `ÉCHEC (${echecs})` : 'OK'}`);
process.exit(echecs ? 1 : 0);
