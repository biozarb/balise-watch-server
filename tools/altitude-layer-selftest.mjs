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
let isoU = null, isoV = null, ziso = null, iso = null;
let buf = null, fxStep = 0;
if (!(tampon && zsolF && manF)) {
  console.log('  ⚠️ --tampon / --zsol / --manifeste absents : NI le décodage '
    + 'du tampon réel NI la parité avec Python ne sont vérifiés.');
  echecs++;
} else {
  man = JSON.parse(readFileSync(manF, 'utf-8'));
  const octets = readFileSync(tampon);
  buf = octets.buffer.slice(octets.byteOffset,
    octets.byteOffset + octets.byteLength);
  const zo = readFileSync(zsolF);
  zsol = new Float32Array(zo.buffer.slice(zo.byteOffset,
    zo.byteOffset + zo.byteLength));

  verifier('le tampon fait exactement la taille annoncée par le manifeste',
    buf.byteLength === man.service.octets_par_echeance,
    `${buf.byteLength} octets`);

  // ⚠️ 12/08 — LE RANGE DU CALQUE NE S'ARRÊTE PLUS À `v`. Il lui faut
  // aussi les isobares (`iso_u`, `iso_v`) et leur axe (`ziso`), sans
  // quoi son plafond reste collé au relief. `ORDRE_TAMPON` côté Python
  // range les cinq d'un seul tenant EN TÊTE — un Range est une plage
  // CONTINUE, donc l'ordre n'est pas cosmétique.
  const CLES = [...L.PARAMS_CALQUE];
  const tr = CLES.map(c => {
    const t = man.service.tranches[c];
    if (!t) throw new Error(`tranche « ${c} » absente du manifeste`);
    return t;
  });
  let contigu = tr[0].offset === 0;
  for (let k = 1; k < tr.length; k++) {
    if (tr[k].offset !== tr[k - 1].offset + tr[k - 1].octets) contigu = false;
  }
  verifier('⚠️ tout ce que le calque lit est CONTIGU et EN TÊTE — u, v, '
    + 'iso_u, iso_v, ziso', contigu,
    CLES.map((c, k) => `${c}@${tr[k].offset}`).join(' '));

  // Le Range que le navigateur demande réellement.
  const debut = tr[0].offset;
  const fin = tr[tr.length - 1].offset + tr[tr.length - 1].octets;
  const partiel = buf.slice(debut, fin);
  verifier('le Range du calque tire moins de la moitié de l\'objet',
    partiel.byteLength / buf.byteLength < 0.5,
    `${(partiel.byteLength / 1e3).toFixed(0)} Ko sur `
    + `${(buf.byteLength / 1e3).toFixed(0)} Ko`);

  u = L.decoderTranche(partiel, man.service.tranches.u, debut);
  v = L.decoderTranche(partiel, man.service.tranches.v, debut);
  isoU = L.decoderTranche(partiel, man.service.tranches.iso_u, debut);
  isoV = L.decoderTranche(partiel, man.service.tranches.iso_v, debut);
  ziso = L.decoderTranche(partiel, man.service.tranches.ziso, debut);
  const nbCol0 = man.axes.nb_lat * man.axes.nb_lon;
  iso = { u: isoU, v: isoV, ziso, nbNiveaux: man.niveaux_hpa.length };
  verifier('décodé depuis le Range, u a la bonne longueur',
    u.length === man.niveaux_m_sol.length * nbCol0);

  // ⛔⛔ LE PIÈGE DU LOT 12 : `ziso` est en float32 AU MILIEU de float16.
  // Un lecteur qui supposerait float16 partout obtiendrait deux fois
  // trop de valeurs — et elles seraient toutes FINIES. Aucune erreur,
  // aucun trou, juste un axe vertical inventé.
  verifier('⛔ `ziso` est annoncé float32 et décodé comme tel — deux fois '
    + 'moins de valeurs qu\'une lecture float16 en aurait tirées',
    man.service.tranches.ziso.dtype === 'float32'
    && ziso.length === man.niveaux_hpa.length * nbCol0
    && ziso.length * 2 === man.service.tranches.ziso.octets / 2,
    `${ziso.length} valeurs`);
  let croissant = true, nFini = 0;
  for (let c = 0; c < nbCol0 && croissant; c++) {
    for (let n = 1; n < iso.nbNiveaux; n++) {
      const bas = ziso[(n - 1) * nbCol0 + c], haut = ziso[n * nbCol0 + c];
      if (!Number.isFinite(bas) || !Number.isFinite(haut)) continue;
      nFini++;
      if (haut <= bas) croissant = false;
    }
  }
  // ⚠️ Ce contrôle a une référence INDÉPENDANTE du décodeur : la
  // pression décroît de 1000 à 400 hPa, donc l'altitude ne peut que
  // croître. Un décalage d'un octet, une endianness inversée ou une
  // lecture float16 casseraient cette monotonie — et rien d'autre ne le
  // dirait, puisque les valeurs resteraient finies.
  verifier('⛔ l\'axe isobare décodé est STRICTEMENT croissant (1000 → 400 '
    + 'hPa) — c\'est ce qui attrape une lecture décalée d\'un octet',
    croissant && nFini > 0, `${nFini} paires vérifiées`);

  // ⚠️ Décoder l'objet ENTIER doit donner la même chose que décoder le
  // Range : c'est le contrôle qui attrape un `offsetBase` oublié.
  const uEntier = L.decoderTranche(buf, man.service.tranches.u, 0);
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
  fxStep = fx.echeanceH;
  const niveaux = fx.niveaux_m_sol;
  const nbLon = man.axes.nb_lon, nbCol = man.axes.nb_lat * nbLon;
  let pireU = 0, pireV = 0, pireW = 0, nServis = 0, nMasq = 0;
  let desaccordMasque = 0, desaccordK = 0, pireZsol = 0, premier = null;
  let nIso = 0;
  // Étape 13 : le mélange. `nMix` compte, `pireWh` mesure l'écart de
  // rampe, `desaccordMix` compte les cas où les deux implémentations ont
  // divergé sur le CHEMIN et pas sur la valeur.
  let nMix = 0, pireWh = 0, desaccordMix = 0;

  for (const c of fx.cas) {
    const idx = c.j * nbLon + c.i;
    pireZsol = Math.max(pireZsol, Math.abs(zsol[idx] - c.zsol));
    const h = c.altitudeASLM - zsol[idx];
    // ── Étape 12 : au-dessus du plafond hauteur, l'axe change ────────
    // ⚠️ Le cas porte `source`, et le banc le SUIT plutôt que de le
    // deviner : deviner reviendrait à réimplémenter la règle qu'on
    // vérifie, et un banc qui réimplémente sa propre règle ne vérifie
    // rien (déjà payé le 12/08 sur `test_freeze_balises.py`).
    const parIso = c.source === 'isobare';
    let servable = h >= niveaux[0] && h <= niveaux[niveaux.length - 1];
    let k = 0, w = 0;
    if (parIso) {
      const e = L.encadrerIsobares(ziso, nbCol, iso.nbNiveaux, idx, c.altitudeASLM);
      servable = e.dispo;
      k = e.k; w = e.w;
      nIso++;
    } else if (servable) {
      const e = L.encadrer(niveaux, h);
      k = e.k; w = e.w;
    }
    if (c.u === null) {
      nMasq++;
      if (servable) { desaccordMasque++; premier = premier || c; }
      continue;
    }
    if (!servable) { desaccordMasque++; premier = premier || c; continue; }
    if (k !== c.k) { desaccordK++; premier = premier || c; }
    pireW = Math.max(pireW, Math.abs(w - c.w));
    const pu = parIso ? isoU : u, pv = parIso ? isoV : v;
    let gu = L.melanger(pu[k * nbCol + idx], pu[(k + 1) * nbCol + idx], w);
    let gv = L.melanger(pv[k * nbCol + idx], pv[(k + 1) * nbCol + idx], w);

    // ── ÉTAPE 13 : LE MÉLANGE, rejoué du côté JS ─────────────────────
    // ⛔ Le cas porte `source: 'melange'` ET `poidsHauteur`. Le banc SUIT
    // les deux plutôt que de redécider quand mélanger : redécider serait
    // réimplémenter la règle qu'on vérifie. Mais il RECALCULE le poids
    // par `L.poidsHauteur(man, h)` et compare — c'est ce qui attrape une
    // rampe qui aurait divergé d'un côté du pont.
    if (c.source === 'melange') {
      nMix++;
      const wh = L.poidsHauteur(man, h);
      pireWh = Math.max(pireWh, Math.abs(wh - c.poidsHauteur));
      const e = L.encadrerIsobares(ziso, nbCol, iso.nbNiveaux, idx, c.altitudeASLM);
      if (!e.dispo) { desaccordMix++; premier = premier || c; continue; }
      const iu = L.melanger(isoU[e.k * nbCol + idx], isoU[(e.k + 1) * nbCol + idx], e.w);
      const iv = L.melanger(isoV[e.k * nbCol + idx], isoV[(e.k + 1) * nbCol + idx], e.w);
      // ⚠️ MÊME ORDRE DES TERMES QUE PYTHON. `w*a + (1-w)*b` et
      // `b + w*(a-b)` sont égaux en algèbre et pas en virgule flottante,
      // et ce banc exige l'écart NUL, pas « petit ».
      gu = wh * gu + (1 - wh) * iu;
      gv = wh * gv + (1 - wh) * iv;
    } else if (!parIso) {
      // ⛔ ET LA RÉCIPROQUE, qui est la moitié qui manquerait. Si Python
      // dit « hauteur » là où le TypeScript mélangerait, les valeurs
      // divergeraient — mais si le banc ne testait QUE les cas étiquetés
      // `melange`, il ne le verrait jamais. On vérifie donc aussi que le
      // poids vaut bien 1 partout où Python n'a PAS mélangé.
      const wh = L.poidsHauteur(man, h);
      if (wh < 1) {
        const e = L.encadrerIsobares(ziso, nbCol, iso.nbNiveaux, idx, c.altitudeASLM);
        // Python n'a pas mélangé : soit l'axe isobare ne dit rien ici,
        // soit le poids vaut 1. Si les deux sont faux, les deux
        // implémentations ont divergé sur le CHEMIN, pas sur la valeur.
        if (e.dispo) {
          const iu = L.melanger(isoU[e.k * nbCol + idx], isoU[(e.k + 1) * nbCol + idx], e.w);
          if (Number.isFinite(iu)) { desaccordMix++; premier = premier || c; }
        }
      }
    }
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
  // ── ÉTAPE 13 : la bande de mélange, des deux côtés du pont ────────
  verifier('⛔ la fixture porte des cas MÉLANGÉS — sans eux, la bande '
    + 'zsol+1000 → zsol+3000 ne serait comparée nulle part, et c\'est '
    + 'exactement la tranche où vole un parapentiste',
    nMix > 0, `${nMix} cas mélangés`);
  verifier('⛔ la RAMPE est la même des deux côtés, à l\'octet près — deux '
    + 'rampes qui se ressemblent, c\'est le défaut que le §8 a corrigeait',
    pireWh === 0, `écart max ${pireWh}`);
  verifier('⛔ et les deux implémentations mélangent aux MÊMES ENDROITS : '
    + 'aucune ne mélange là où l\'autre sert la hauteur seule',
    desaccordMix === 0, `${desaccordMix} désaccord(s) de chemin`);
  verifier('la fixture porte des cas servis ET des cas masqués',
    nServis > 0 && nMasq > 0, `${nServis} servis · ${nMasq} masqués`);
  // ⛔ Sans ce contrôle, la moitié HAUTE du calque ne serait vérifiée
  // NULLE PART — et c'est celle dont l'axe varie en chaque point, donc
  // celle où une divergence Python/TypeScript est la plus facile.
  verifier('⛔ …et des cas servis par les ISOBARES, sans quoi la moitié '
    + 'haute du calque n\'est comparée nulle part',
    nIso > 0, `${nIso} cas isobares`);
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
  // ⚠️ CE CONTRÔLE-CI PORTE SUR `encadrer` + `melanger`, pas sur le
  // calque entier — et c'est ce qui lui permet de survivre intact à
  // l'étape 13. L'interpolation VERTICALE rend toujours le niveau brut
  // sur un niveau ; ce qui a changé, c'est ce que le calque en fait
  // ensuite (cf. le contrôle retourné plus bas).
  verifier('altitude tombant sur un niveau → l\'interpolation verticale rend '
    + 'le niveau BRUT, écart nul',
    pire === 0, `${cas} cas · écart max ${pire}`);

  console.log('\n     couverture calculée par le TypeScript :');
  console.log('       altitude   servi   relief  plafond  bande basse  par isobares   mélangé');
  for (const A of [1000, 2000, 3000, 4000, 5000, 7000]) {
    const c = L.calculerCalque(man, u, v, zsol, A, iso).couverture;
    console.log(`       ${String(A).padStart(5)} m  `
      + `${(100 * c.servi).toFixed(1).padStart(6)} % `
      + `${(100 * c.relief).toFixed(1).padStart(6)} % `
      + `${(100 * c.auDessusDuPlafond).toFixed(1).padStart(6)} % `
      + `${(100 * c.sousPremierNiveau).toFixed(2).padStart(10)} % `
      + `${(100 * c.parIsobares).toFixed(1).padStart(11)} % `
      + `${(100 * c.parMelange).toFixed(1).padStart(8)} %`);
  }

  // ⛔ LE CRITÈRE DU LOT 12, rejoué côté navigateur. Sans les isobares
  // le plafond SUIT le relief ; avec, il ne le suit plus. On compare les
  // deux appels — un même code, une seule différence.
  const A5 = 5000;
  const sans = L.calculerCalque(man, u, v, zsol, A5).couverture;
  const avec = L.calculerCalque(man, u, v, zsol, A5, iso).couverture;
  verifier('⛔ à 5 000 m, le relais isobare supprime les colonnes trouées '
    + 'par le plafond', avec.auDessusDuPlafond === 0 && sans.auDessusDuPlafond > 0,
    `sans : ${(100 * sans.auDessusDuPlafond).toFixed(1)} % · `
    + `avec : ${(100 * avec.auDessusDuPlafond).toFixed(1)} %`);
  verifier('…et il DIT quelles colonnes il sert, pour que l\'écran puisse '
    + 'prévenir que le haut vaut moins que le bas',
    avec.parIsobares > 0
    && Math.abs(avec.parIsobares - sans.auDessusDuPlafond) < 1e-9,
    `${(100 * avec.parIsobares).toFixed(1)} % par isobares`);
  // ── ⛔ ÉTAPE 13 : CE CONTRÔLE A ÉTÉ RETOURNÉ, ET IL FAUT LE DIRE ──
  //
  // Jusqu'au 13/08 il vérifiait « sous zsol + 3000 m, ajouter les
  // isobares ne change RIEN » — et il était juste, parce que le calque
  // basculait net. Yann a tranché le §8 a : le calque MÉLANGE désormais
  // comme `profil.py`, donc ajouter les isobares CHANGE la valeur dans
  // la bande, et c'est le but.
  //
  // ⚠️ Le supprimer aurait été le pire choix. Un contrôle qui disparaît
  // ne laisse aucune trace de ce qui a cessé d'être vrai ; il est donc
  // RETOURNÉ, et il vérifie maintenant les deux moitiés de la nouvelle
  // règle — que ça change dans la bande, et que ça ne change PAS
  // en dessous.
  const raccord = man.raccord;
  const cmp = (A) => {
    const s = L.calculerCalque(man, u, v, zsol, A);
    const a = L.calculerCalque(man, u, v, zsol, A, iso);
    let n = 0;
    for (let c = 0; c < s.u.length; c++) {
      const x = s.u[c], y = a.u[c];
      if (!(x === y || (Number.isNaN(x) && Number.isNaN(y)))) n++;
    }
    return { n, avec: a };
  };
  // Une altitude franchement DANS la bande pour la plupart des colonnes :
  // le sol médian du domaine tourne autour de 1 370 m, donc 3 000 m
  // tombe à ~1 630 m au-dessus du sol — au cœur de la rampe.
  const dans = cmp(3000);
  verifier('⛔ DANS la bande, ajouter les isobares CHANGE la valeur — '
    + 'c\'est le §8 a tranché, et c\'est ce que la coupe fait depuis '
    + 'toujours', dans.n > 0,
    `${dans.n} colonnes changées · ${(100 * dans.avec.couverture.parMelange).toFixed(1)} % mélangées`);
  // ⚠️ Et SOUS le raccord bas, rien ne doit bouger : l'invariant de
  // l'étape 11 tient encore là, et c'est la moitié de la colonne qui
  // décide d'un décollage.
  const sousBas = cmp(raccord ? raccord.bas_m - 100 : 900);
  verifier('⛔ …mais SOUS le raccord bas, rien ne change : l\'invariant de '
    + 'l\'étape 11 tient encore là, et c\'est la tranche du décollage',
    sousBas.n === 0 && sousBas.avec.couverture.parMelange === 0,
    `${sousBas.n} colonne(s) changée(s)`);
}

// ══════════════════════════════════════════════════════════════════════
// ══════════════════════════════════════════════════════════════════════
console.log('\n── 8 bis. LA COLONNE, et les DEUX dispositions ──');
// ⛔ CE QUE CE BLOC PROTÈGE. Depuis l'étape 12 le produit publie la même
// donnée DEUX FOIS : param-majeure pour le calque, colonne-majeure pour
// la vue de coupe. Rien ne les force à s'accorder — deux dispositions
// qui divergeraient ne lèveraient aucune exception, elles rendraient
// deux vents différents pour le même point, sur deux écrans que
// personne ne regarde en même temps.
//
// Le banc Python (`test_grille.py` §7) le vérifie côté encodeur ; ici on
// le vérifie côté DÉCODEUR, avec le code que le navigateur exécute.
const colF = arg('colonnes');
if (!(man && colF)) {
  console.log('  ⚠️ --colonnes absent : la route de lecture de la vue de '
    + 'coupe n\'est PAS vérifiée.');
  echecs++;
} else {
  const co = readFileSync(colF);
  const bufCol = co.buffer.slice(co.byteOffset, co.byteOffset + co.byteLength);
  const pas = man.service.colonnes.octets_par_colonne;
  const nbLat = man.axes.nb_lat, nbLon2 = man.axes.nb_lon;
  const nbCol2 = nbLat * nbLon2;
  const nbEch = man.echeances.length;

  verifier('l\'objet colonnes fait `octets_par_colonne` × nb de colonnes',
    bufCol.byteLength === pas * nbCol2,
    `${bufCol.byteLength} o = ${pas} × ${nbCol2}`);
  // ⛔ Sans ce multiple de 4, `ziso` (float32) commencerait à un
  // décalage impair-en-mots une colonne sur deux.
  verifier('⛔ le pas d\'une colonne est multiple de 4', pas % 4 === 0);

  // La colonne du milieu, et les deux coins : `colonneLaPlusProche` doit
  // retomber sur le bon (j, i) MALGRÉ le pas de latitude NÉGATIF.
  const a2 = man.axes;
  let bonsIndices = 0;
  for (const [jv, iv] of [[0, 0], [nbLat - 1, nbLon2 - 1],
                          [Math.floor(nbLat / 2), Math.floor(nbLon2 / 2)]]) {
    const dLat = (a2.lat_dernier - a2.lat_premier) / (nbLat - 1);
    const dLon = (a2.lon_dernier - a2.lon_premier) / (nbLon2 - 1);
    const p = L.colonneLaPlusProche(man, a2.lat_premier + jv * dLat,
      a2.lon_premier + iv * dLon);
    if (p.j === jv && p.i === iv) bonsIndices++;
  }
  verifier('⚠️ `colonneLaPlusProche` retombe sur le bon (j, i) malgré le pas '
    + 'de latitude NÉGATIF — une carte symétrique ressemble à une carte',
    bonsIndices === 3, `${bonsIndices}/3`);

  // ⛔ LE TEST : la colonne lue dans `colonnes.bin` est-elle la même que
  // celle lue dans le tampon d'échéance ?
  let desaccords = 0, compares = 0;
  const iEch = man.echeances.indexOf(fxStep);
  for (let j = 0; j < nbLat; j += Math.max(1, Math.floor(nbLat / 7))) {
    for (let i = 0; i < nbLon2; i += Math.max(1, Math.floor(nbLon2 / 7))) {
      const pos = L.colonneLaPlusProche(man,
        a2.lat_premier + j * ((a2.lat_dernier - a2.lat_premier) / (nbLat - 1)),
        a2.lon_premier + i * ((a2.lon_dernier - a2.lon_premier) / (nbLon2 - 1)));
      const col = L.decoderColonne(man, bufCol, pos, zsol[j * nbLon2 + i], 0);
      for (const [cle, t] of Object.entries(man.service.tranches)) {
        const via = col.tranches[cle];
        const pile = L.decoderTranche(buf, t, 0);
        for (let n = 0; n < t.niveaux; n++) {
          const x = via[n * nbEch + iEch];
          const y = pile[n * nbCol2 + j * nbLon2 + i];
          compares++;
          if (!(x === y || (Number.isNaN(x) && Number.isNaN(y)))) desaccords++;
        }
      }
    }
  }
  verifier('⛔ la colonne lue dans `colonnes.bin` est identique à celle lue '
    + 'dans le tampon d\'échéance — les deux dispositions ne divergent pas',
    desaccords === 0, `${compares - desaccords}/${compares} valeurs`);
  verifier('⚠️ et un Range de la SEULE colonne suffit (offsetBase honoré)',
    (() => {
      const pos = L.colonneLaPlusProche(man, a2.lat_premier, a2.lon_premier);
      const tranche = bufCol.slice(pos.offset, pos.offset + pas);
      const c1 = L.decoderColonne(man, tranche, pos, 0, pos.offset);
      const c2 = L.decoderColonne(man, bufCol, pos, 0, 0);
      return Object.keys(c1.tranches).every(k => {
        const a3 = c1.tranches[k], b3 = c2.tranches[k];
        return a3.length === b3.length && a3.every((x, n) =>
          x === b3[n] || (Number.isNaN(x) && Number.isNaN(b3[n])));
      });
    })(),
    `${pas} octets par colonne`);
}

// ══════════════════════════════════════════════════════════════════════
console.log('\n── 8 ter. LA PRESSION DÉRIVÉE, et ce qu\'elle a le droit de dire ──');
// ⛔ CE QUE CE BLOC PROTÈGE. Les 25 niveaux hauteur d'AGRUME n'ont pas de
// pression ; l'émagramme « brut » en fait pourtant son ORDONNÉE. On la
// dérive donc — arbitrage du 13/08 — et une valeur dérivée servie sur un
// axe que l'écran affiche comme une mesure doit être exacte là où elle
// peut l'être, et se dire partout ailleurs.
{
  const NIV = [1000, 950, 925, 900, 850, 800, 700, 500, 400];
  const NECH = 2, ECH = 1;
  const zsol = 1368, psol = 855.4;
  //             1000  950  925  900  850  800   700   500   400  hPa
  const alt =   [ 194, 635, 865, 1101, 1597, 2119, 3243, 5931, 7622];
  const ziso = new Float32Array(NIV.length * NECH);
  NIV.forEach((_, k) => { ziso[k * NECH + ECH] = alt[k]; });

  const anc = L.ancresPression(zsol, psol, ziso, NIV, ECH, NECH);
  verifier('⛔ les niveaux SOUS le sol sont écartés des ancres — sinon la '
    + 'pression croîtrait en montant', anc.length === NIV.length - 4 + 1
    && anc[0].alt === zsol && anc[1].hPa === 850,
    `${anc.length} ancres, la 1re au sol (${psol} hPa), la 2e à ${anc[1].hPa} hPa`);
  verifier('⚠️ l\'ancre basse est le SOL, pas le premier isobare — sans '
    + 'elle les 229 premiers mètres seraient extrapolés',
    anc[0].alt === zsol && anc[0].niveau === false,
    `${(anc[1].alt - zsol).toFixed(0)} m entre le sol et 850 hPa`);

  // ⛔ Sur un niveau isobare, la pression EST celle du niveau.
  let exact = 0;
  for (const a of anc.filter(x => x.niveau)) {
    const p = L.pressionA(anc, a.alt);
    if (p && p.hPa === a.hPa && p.source === 'modele') exact++;
  }
  verifier('⛔ sur un niveau isobare, la pression rendue est EXACTEMENT '
    + 'celle du niveau, et elle se dit « modele »',
    exact === anc.filter(x => x.niveau).length,
    `${exact}/${anc.filter(x => x.niveau).length}`);
  const pSol = L.pressionA(anc, zsol);
  verifier('…et au sol, exactement `psol`',
    pSol !== null && pSol.hPa === psol);

  // ⚠️ Entre deux ancres : dérivée, monotone, et dans les bornes.
  let mono = true, dites = 0, n = 0, prev = Infinity;
  for (let z = zsol; z <= alt[alt.length - 1]; z += 7) {
    const p = L.pressionA(anc, z);
    if (!p) { mono = false; break; }
    if (p.hPa > prev + 1e-9) mono = false;
    prev = p.hPa; n++;
    if (p.source === 'derivee') dites++;
  }
  verifier('⛔ la pression décroît STRICTEMENT en montant, du sol au '
    + 'dernier isobare — une ancre souterraine oubliée casserait ça',
    mono, `${n} altitudes balayées`);
  verifier('⚠️ et tout ce qui n\'est pas un niveau se dit « derivee » — '
    + 'servir un calcul sans le dire, sur l\'axe d\'un émagramme, c\'est '
    + 'le défaut que ce lot corrige ailleurs', dites > 0 && dites <= n,
    `${dites}/${n}`);

  verifier('⛔ aucune extrapolation : sous le sol et au-dessus du dernier '
    + 'isobare, on rend null plutôt qu\'une pression inventée',
    L.pressionA(anc, zsol - 1) === null
    && L.pressionA(anc, alt[alt.length - 1] + 1) === null);

  // ⓘ CE QUE LA DÉRIVATION COÛTE — ET LE BANC S'EST TROMPÉ DEUX FOIS.
  //
  // 1re version : 17,4 hPa. C'était le BANC qui était faux — il comparait
  //   des ancres inventées à la main (855,4 hPa au sol sous 850 hPa à
  //   229 m, physiquement incohérent) à une atmosphère standard qui ne
  //   les respectait pas.
  // 2e version : 1,603 hPa, soit 13,5 m — vrai, mais mesuré sur l'écart
  //   500 → 400 hPa, large de 2 562 m. ⚠️ AUCUN NIVEAU HAUTEUR N'Y VIT :
  //   ils s'arrêtent à zsol + 3 000 m, et cet écart-là commence vers
  //   5 900 m. Le chiffre était juste et ne décrivait rien.
  //
  // ⛔ La question n'est donc pas « quelle est l'erreur maximale de
  // l'interpolation » mais « quelle est-elle LÀ OÙ IL Y A DES NIVEAUX
  // HAUTEUR À DATER » — c'est-à-dire entre le sol et zsol + 3 000 m.
  {
    const G = 9.80665, R = 287.05, gam = 0.0065, T0 = 288.15, P0 = 1013.25;
    const pDeZ = (z) => P0 * Math.pow(1 - gam * z / T0, G / (R * gam));
    const zDeP = (p) => (T0 / gam) * (1 - Math.pow(p / P0, R * gam / G));
    const zs = 1368;                       // colonne médiane du domaine
    const ancH = [{ alt: zs, hPa: pDeZ(zs), niveau: false }];
    for (const hpa of [850, 800, 750, 700, 650, 600, 550, 500, 400]) {
      const z = zDeP(hpa);
      if (z > zs) ancH.push({ alt: z, hPa: hpa, niveau: true });
    }
    const mesure = (zMin, zMax) => {
      let pire = 0, ou = 0;
      for (let z = zMin; z <= zMax; z += 5) {
        const p = L.pressionA(ancH, z);
        if (!p) continue;
        const d = Math.abs(p.hPa - pDeZ(z));
        if (d > pire) { pire = d; ou = z; }
      }
      return { pire, ou };
    };
    const bas = mesure(zs, zs + 3000);          // là où vivent les niveaux
    const tout = mesure(zs, ancH[ancH.length - 1].alt);
    console.log(`  ⓘ écart à la loi hydrostatique (6,5 K/km), colonne à `
      + `zsol = ${zs} m :`);
    console.log(`       sol → zsol+3000 m (où vivent les niveaux hauteur) : `
      + `${bas.pire.toFixed(3)} hPa ≈ ${(bas.pire * 8.4).toFixed(2)} m, `
      + `vers ${bas.ou.toFixed(0)} m`);
    console.log(`       sol → 400 hPa (toute la colonne)                  : `
      + `${tout.pire.toFixed(3)} hPa ≈ ${(tout.pire * 8.4).toFixed(2)} m, `
      + `vers ${tout.ou.toFixed(0)} m`);
    verifier('⛔ dans la tranche où il y a des niveaux hauteur à dater, la '
      + 'dérivation coûte moins que les 2,00 m du float16 sur l\'axe '
      + 'd\'altitude — au-dessus, les isobares se datent eux-mêmes',
      bas.pire * 8.4 < 2.0, `${(bas.pire * 8.4).toFixed(2)} m`);
    verifier('⚠️ et l\'écart entre deux ancres reste petit là où ça compte : '
      + 'le sol et le premier isobare émergé se touchent',
      ancH[1].alt - ancH[0].alt < 300,
      `${(ancH[1].alt - ancH[0].alt).toFixed(0)} m`);
  }
}

// ══════════════════════════════════════════════════════════════════════
console.log('\n── 9. ⛔ RIEN N\'EST CODÉ EN DUR CÔTÉ CLIENT ──');
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
    // ⚠️ 12/08 — un manifeste SANS isobares reste un manifeste valide.
    // Le calque doit alors se comporter EXACTEMENT comme avant l'étape
    // 12 : plafond collé au relief, aucune erreur. Un module qui
    // exigerait `iso` casserait sur un run d'avant, ou sur un domaine
    // que Météo-France servirait sans IP1.
    niveaux_hpa: [],
    parametres_isobares: [],
    // ⛔ UN RACCORD QUI N'EST PAS CELUI DE LA PRODUCTION (200 → 700 m au
    // lieu de 1 000 → 3 000). Le module doit OBÉIR à ces bornes-là.
    // ⚠️ Ce manifeste ne porte AUCUN isobare, donc rien ne sera mélangé
    // ici : ce qu'on vérifie plus bas, c'est que la rampe elle-même suit
    // le manifeste — un `poidsHauteur` codé en dur rendrait 1 à 400 m,
    // là où ce manifeste-ci exige 0,6.
    raccord: { bas_m: 200, haut_m: 700 },
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
      cle_colonnes: 'x/{domaine}/{run}/colonnes.bin',
      tranches: {
        v: { offset: 0, octets: octetsParParam, dtype: 'float16',
             niveaux: NIV2.length, bloc: 'hauteur' },
        u: { offset: octetsParParam, octets: octetsParParam, dtype: 'float16',
             niveaux: NIV2.length, bloc: 'hauteur' },
      },
      octets_par_echeance: 2 * octetsParParam,
      colonnes: {
        disposition: 'un enregistrement par colonne', octets_par_colonne: 12,
        offset: '(j * nb_lon + i) * octets_par_colonne', tranches: {}, note: '',
      },
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

  // ── ⛔ ET LE RACCORD AUSSI (étape 13) ────────────────────────────
  // Le raccord décide d'une VALEUR servie, pas d'un affichage : c'est
  // la constante qu'il aurait été le plus tentant de recopier côté
  // client, et la plus coûteuse. Ce manifeste-ci dit 200 → 700 m ; un
  // `poidsHauteur` figé sur la production rendrait 1 à h = 400 m.
  verifier('⛔ la RAMPE DU RACCORD suit le manifeste (200 → 700 m ici, pas '
    + '1000 → 3000) — c\'est la constante qu\'il aurait été le plus '
    + 'tentant de recopier',
    L.poidsHauteur(man2, 400) === 0.6
    && L.poidsHauteur(man2, 200) === 1 && L.poidsHauteur(man2, 700) === 0,
    `w(400 m) = ${L.poidsHauteur(man2, 400)}`);
  verifier('⛔ et un manifeste SANS raccord LÈVE plutôt que de mélanger '
    + 'selon des bornes que le producteur n\'a jamais annoncées',
    (() => {
      try { L.poidsHauteur({ ...man2, raccord: undefined }, 400); return false; }
      catch { return true; }
    })());

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

// ══════════════════════════════════════════════════════════════════════
console.log('\n── 10. ⛔ LA COLONNE DEVIENT UN PROFIL — les deux verticales '
  + 'dans UNE liste ──');
// ⛔ CE QUE CETTE SECTION PROTÈGE, ET QUE RIEN D'AUTRE NE VOIT.
// `colonneVersProfil` fusionne 25 niveaux HAUTEUR et 14 niveaux ISOBARES
// dans un seul `levels`. Quatre façons de casser en silence, une par
// bloc de vérifications :
//   1. les isobares SOUTERRAINS servis — un vent « au sol » inventé par
//      l'extrapolation du modèle, parfaitement lisse et parfaitement
//      faux ;
//   2. les m/s servis comme des km/h — un vent 3,6 fois trop faible, et
//      aucune courbe ne le dit ;
//   3. la pression d'un niveau hauteur FIGÉE sur une seule heure, alors
//      qu'elle bouge avec `psol` ;
//   4. `prmsl` servi sans défaire son décalage — −13 hPa au lieu de 987.
{
  const A = await import(process.env.BW_AGRUME_MODULE
    || join(ici, '..', '..', 'web', 'src', 'lib', 'agrumeProfile.ts'));

  // Une colonne fabriquée à la main : 3 échéances, 2 niveaux hauteur
  // (10 et 500 m), 3 niveaux isobares dont UN sous le sol.
  const NECH = 3, ZSOL = 1000;
  const s = (...v) => Float32Array.from(v);
  const col = {
    j: 0, i: 0, lat: 45, lon: 6, zsolM: ZSOL,
    echeances: [0, 1, 2],
    niveauxMSol: [10, 500],
    niveauxHPa: [1000, 900, 800],
    tranches: {
      // (niveau, échéance)
      u: s(10, 10, 10, /* 500 m */ 0, 0, 0),
      v: s(0, 0, 0, -10, -10, -10),
      t: s(15, 16, 17, 12, 13, 14),
      r: s(80, 80, 80, 60, 60, 60),
      iso_u: s(1, 1, 1, 2, 2, 2, 3, 3, 3),
      iso_v: s(0, 0, 0, 0, 0, 0, 0, 0, 0),
      iso_t: s(14, 14, 14, 8, 8, 8, 2, 2, 2),
      iso_r: s(70, 70, 70, 50, 50, 50, 30, 30, 30),
      iso_cc: s(NaN, 20, 20, NaN, 40, 40, NaN, 60, 60),
      // ⚠️ FIXTURE PHYSIQUEMENT COHÉRENTE, et ça compte ici : 1000 hPa
      // est SOUS le sol (100 m < zsol = 1000 m), puis la pression DÉCROÎT
      // en montant — 910 hPa au sol, 900 à 1 500 m, 800 à 2 500 m. Une
      // première version avait mis `psol = 900` avec le niveau 900 hPa à
      // 1 500 m : les deux ancres portaient alors la MÊME pression, la
      // dérivation rendait une constante, et le banc a eu raison de
      // refuser — c'est exactement l'ancre incohérente qu'il surveille.
      ziso: s(100, 100, 100, 1500, 1510, 1520, 2500, 2500, 2500),
      psol: s(910, 908, 906),
      t2m: s(18, 19, 20),
      td2m: s(10, 10, 10),
      rafale: s(NaN, 10, 20),
      pression_mer: s(13.5, 12.5, 11.5),   // = 1013,5 hPa − 1000
      precipitation: s(NaN, 0.5, 1.5),
    },
  };
  // ⚠️ TOUTES les séries de surface déclarées, pas seulement `prmsl`
  // (audit du 13/08). Le client défait désormais `decalage_precision`
  // pour CHAQUE série — le contrat du manifeste l'a toujours exigé
  // (« celui qui ne le lit pas doit REFUSER de servir la valeur »), et
  // le producteur publie le champ pour toutes (défaut 0.0). Une série
  // absente de cette liste doit sortir VIDE, et c'est vérifié plus bas.
  const surf = (nom, dec = 0) => ({
    nom, unite: 'x', paquet: 'SP1', pas_de_temps: 'instant',
    absent_a_tau0: false, decalage_precision: dec,
  });
  const man = {
    run: '2026-08-13T00:00:00Z',
    parametres_surface: [
      surf('t2m'), surf('td2m'), surf('rafale'), surf('nuages_bas'),
      surf('nuages_moyens'), surf('nuages_hauts'), surf('cape'),
      surf('couche_limite'), surf('rayonnement'), surf('precipitation'),
      surf('psol'), surf('pression_mer', -1000),
    ],
  };
  const p = A.colonneVersProfil(man, col);

  verifier('les échéances deviennent des timestamps ancrés sur le run',
    p.times.length === NECH
    && p.times[0] === Date.parse('2026-08-13T00:00:00Z')
    && p.times[2] - p.times[0] === 2 * 3600e3);
  verifier('le sol du profil est le zsol de la colonne, pas une élévation '
    + 'demandée ailleurs', p.elevation === ZSOL);

  // ── 1. Le masque sous le sol ──────────────────────────────────────
  const iso1000 = p.levels.find(l => l.pressure === 1000);
  verifier('⛔ le niveau isobare SOUS le sol sort avec une altitude nulle — '
    + 'sinon on servirait un vent « au sol » inventé par l\'extrapolation',
    iso1000 && iso1000.altitude.every(a => a === null),
    `ziso = 900 m, zsol = ${ZSOL} m`);
  const iso900 = p.levels.find(l => l.pressure === 900);
  verifier('…et celui qui ÉMERGE est servi, avec son altitude variable '
    + 'dans le temps',
    iso900 && iso900.altitude[0] === 1500 && iso900.altitude[2] === 1520);

  // ── 2. Les unités ─────────────────────────────────────────────────
  const h10 = p.levels.find(l => l.altitude[0] === ZSOL + 10);
  verifier('⛔ u = +10 m/s au niveau 10 m ressort à 36 km/h et 270° — servir '
    + 'des m/s donnerait un vent 3,6 fois trop faible, sans une erreur',
    h10 && Math.abs(h10.windSpeed[0] - 36) < 1e-9
    && Math.abs(h10.windDir[0] - 270) < 1e-9,
    h10 ? `${h10.windSpeed[0].toFixed(2)} km/h · ${h10.windDir[0].toFixed(0)}°` : '');
  verifier('⚠️ la rafale aussi (max_i10fg est en m/s, windGust10m en km/h)',
    Math.abs(p.surface.windGust10m[1] - 36) < 1e-9,
    `${p.surface.windGust10m[1]} km/h`);
  verifier('⛔ le vent « 10 m » de la ligne de surface EST le niveau 10 m — '
    + 'la colonne d\'air et la ligne de surface ne peuvent pas se contredire',
    p.surface.windSpeed10m[0] === h10.windSpeed[0]
    && p.surface.windDir10m[0] === h10.windDir[0]);

  // ── 3. La pression heure par heure ────────────────────────────────
  verifier('⛔ un niveau HAUTEUR porte une pression PAR HEURE, et elle bouge '
    + 'avec psol — un seul nombre ne pouvait pas dire les deux',
    h10.pressureByHour && h10.pressureByHour[0] !== h10.pressureByHour[2]
    // Strictement SOUS psol (on est 10 m plus haut) et au-dessus du
    // premier isobare émergé : la valeur est encadrée, jamais extrapolée.
    && h10.pressureByHour.every((v, e) => v < col.tranches.psol[e] && v > 900),
    h10.pressureByHour
      ? h10.pressureByHour.map(v => v.toFixed(2)).join(' → ') : 'absente');
  verifier('⚠️ et elle se dit dérivée — le 10 m ne tombe sur aucun niveau '
    + 'isobare',
    h10.pressureSource.every(s => s === 'derivee'));
  verifier('⛔ un niveau ISOBARE ne porte PAS de série : sa pression est '
    + 'exacte et ne bouge pas',
    iso900.pressureByHour === undefined);
  verifier('⚠️ `pressure` d\'un niveau hauteur est la MÉDIANE des heures, '
    + 'pas la première — τ = 0 est l\'échéance la plus trouée du produit',
    Math.abs(h10.pressure - h10.pressureByHour[1]) < 1e-9,
    `${h10.pressure.toFixed(3)} hPa`);

  // ── 4. Le décalage de précision ───────────────────────────────────
  verifier('⛔ `prmsl` est archivé en hPa − 1000 et le manifeste le dit — '
    + 'on le défait EN LE LISANT, jamais de tête',
    Math.abs(p.surface.pressureMsl[0] - 1013.5) < 1e-6,
    `${p.surface.pressureMsl[0]} hPa`);
  verifier('⛔ …et le décalage se défait pour CHAQUE série, pas pour prmsl '
    + 'seul — un `t2m` décalé de −10 doit ressortir juste',
    (() => {
      const dec10 = A.colonneVersProfil({
        ...man,
        parametres_surface: man.parametres_surface.map(q =>
          q.nom === 't2m' ? { ...q, decalage_precision: -10 } : q),
      }, { ...col, tranches: { ...col.tranches, t2m: s(8, 9, 10) } });
      return Math.abs(dec10.surface.temp2m[0] - 18) < 1e-6;
    })(),
    'archivé 8 (= 18 − 10) → rendu 18 °C');
  const sansDec = A.colonneVersProfil({ ...man, parametres_surface: [] }, col);
  verifier('⚠️ et SANS le champ dans le manifeste, la série sort vide plutôt '
    + 'que fausse — une ligne absente se voit, −986 hPa se lit comme une '
    + 'donnée',
    sansDec.surface.pressureMsl.every(v => v === null)
    && sansDec.surface.temp2m.every(v => v === null));

  // ── L'ordre, et les NaN ───────────────────────────────────────────
  const alts = p.levels.map(l => l.altitude.find(a => a != null) ?? Infinity);
  verifier('les niveaux sortent du bas vers le haut, les deux familles '
    + 'entrelacées sur l\'ALTITUDE',
    alts.slice(0, -1).every((a, k) => a <= alts[k + 1]),
    alts.filter(a => Number.isFinite(a)).join(' < '));
  verifier('⛔ un NaN archivé devient `null`, pas un NaN qui contaminerait '
    + 'chaque calcul en aval sans lever',
    iso900.cloud[0] === null && iso900.cloud[1] === 40
    && p.surface.precipitation[0] === null);
  verifier('⚠️ un niveau HAUTEUR n\'a pas de nébulosité — `cc` n\'existe que '
    + 'sur les isobares, et un zéro aurait affirmé « ciel clair »',
    h10.cloud.every(c => c === null));
  verifier('le modèle du profil se nomme, et ce n\'est pas une clé '
    + 'Open-Meteo empruntée', p.model === 'agrume');
  verifier('⛔ `runInfo` porte le run EXACT — AGRUME est le seul modèle dont '
    + 'on maîtrise la chaîne, rendre `null` aurait masqué sa fraîcheur',
    p.runInfo && p.runInfo.lastRun === Date.parse('2026-08-13T00:00:00Z')
    && p.runInfo.dataEndMs === p.times[NECH - 1]
    && p.runInfo.lastProcessingDelaySec === null);
}

// ══════════════════════════════════════════════════════════════════════
console.log('\n── 11. ⛔ LE COUPLE (MANIFESTE, OCTETS) — deux générations '
  + 'd\'un même run ──');
// ⛔ CE QUE CETTE SECTION PROTÈGE, ET POURQUOI ELLE EXISTE (14/08/2026).
//
// Depuis la rallonge du 13/08, un run est publié DEUX fois sous les
// mêmes clés : 25 échéances puis 52. L'échéance étant l'axe INTERNE d'un
// enregistrement de colonne, `octets_par_colonne` passe de 11 800 à
// 24 544 et `colonnes.bin` de 61,2 à 127,3 Mo. Le manifeste et les
// octets ont donc une GÉNÉRATION, et un cache peut les dépareiller.
//
// Les deux appariements ne cassent PAS pareil, et c'est tout l'enjeu :
//
//   manifeste NEUF + octets VIEUX → Range au-delà de la fin → 416.
//     Bruyant. Vu à l'écran le 13/08, et le message accusait la
//     rétention — le mauvais coupable, sur un run parfaitement intact.
//   manifeste VIEUX + octets NEUFS → le Range tombe DANS l'objet, 206,
//     la bonne LONGUEUR, au mauvais ENDROIT. **Silencieux.** Une colonne
//     d'air plausible et fausse, et rien pour le dire.
//
// Un banc qui ne vérifierait que le premier laisserait passer celui qui
// coûte cher. Les deux sont ici.
{
  const RUN = '2026-08-13T15:00:00Z', DOM = 'nord-alpes';
  const CLE_COL = `agrume/grille/${DOM}/${RUN}/colonnes.bin`;
  const NECH = 2, PAS = 48, NB_LAT = 2, NB_LON = 2;
  const TOTAL = NB_LAT * NB_LON * PAS;

  // ⚠️ Fixture en float32 de bout en bout : le dtype se LIT dans le
  // manifeste, donc rien n'oblige cette fixture à imiter le float16 de
  // la production — et l'écrire à la main n'aurait vérifié que la
  // fixture elle-même.
  const tr = (offset, octets) => ({ offset, octets, dtype: 'float32' });
  const manifeste = (nbEch) => ({
    run: RUN, domaine: DOM,
    echeances: Array.from({ length: nbEch }, (_, k) => k),
    niveaux_m_sol: [10], niveaux_hpa: [900],
    bornes: { latmin: 45, latmax: 46, lonmin: 6, lonmax: 7 },
    axes: {
      nb_lat: NB_LAT, nb_lon: NB_LON, lat_premier: 46, lat_dernier: 45,
      lon_premier: 6, lon_dernier: 7, sens: 'lats DÉCROISSANTES',
    },
    retention_runs: 3,
    parametres_surface: [],
    service: {
      cle_echeance: `agrume/grille/{domaine}/{run}/e{step:02d}.bin`,
      cle_zsol: `agrume/grille/{domaine}/{run}/zsol.bin`,
      cle_colonnes: `agrume/grille/{domaine}/{run}/colonnes.bin`,
      disposition_tampon: '', encodage: 'float32', tranches: {},
      octets_par_echeance: 64,
      colonnes: {
        disposition: '', offset: '', note: '',
        // ⚠️ LA TAILLE SUIT LE NOMBRE D'ÉCHÉANCES, exactement comme en
        // production : c'est CE lien qui fabrique le bug.
        octets_par_colonne: 24 * nbEch,
        tranches: {
          ziso: tr(0, 4 * nbEch), psol: tr(4 * nbEch, 4 * nbEch),
          u: tr(8 * nbEch, 4 * nbEch), v: tr(12 * nbEch, 4 * nbEch),
          iso_u: tr(16 * nbEch, 4 * nbEch), iso_v: tr(20 * nbEch, 4 * nbEch),
        },
      },
    },
  });
  const MAN = manifeste(NECH);          // la génération EN LIGNE
  const MAN_VIEUX = manifeste(1);       // celle qu'un cache retiendrait

  // L'objet de la génération en ligne : 4 colonnes × 48 o.
  const octets = new ArrayBuffer(TOTAL);
  {
    const vue = new DataView(octets);
    for (let c = 0; c < NB_LAT * NB_LON; c++) {
      const b = c * PAS;
      for (let e = 0; e < NECH; e++) {
        vue.setFloat32(b + 4 * e, 1500, true);              // ziso
        vue.setFloat32(b + 8 + 4 * e, 910, true);           // psol
        vue.setFloat32(b + 16 + 4 * e, 10 + c, true);       // u : marque
        vue.setFloat32(b + 24 + 4 * e, 0, true);            // v
        vue.setFloat32(b + 32 + 4 * e, 1, true);            // iso_u
        vue.setFloat32(b + 40 + 4 * e, 0, true);            // iso_v
      }
    }
  }
  const ZSOL = Float32Array.from([1000, 1000, 1000, 1000]);

  // ⚠️ UN VRAI SERVEUR DE RANGE, pas un stub qui rend toujours la même
  // chose : c'est le comportement du 416 et du rabotage de fin d'objet
  // qu'on veut éprouver, et il se joue dans ces trois lignes.
  const servir = (corps, { exposeTotal = true } = {}) => async (url, init) => {
    const m = /bytes=(\d+)-(\d+)/.exec(init?.headers?.Range ?? '');
    if (!m) return new Response(corps, { status: 200 });
    const [d, f] = [Number(m[1]), Number(m[2])];
    if (d >= corps.byteLength) return new Response(null, { status: 416 });
    const fin = Math.min(f, corps.byteLength - 1);
    return new Response(corps.slice(d, fin + 1), {
      status: 206,
      headers: exposeTotal
        ? { 'Content-Range': `bytes ${d}-${fin}/${corps.byteLength}` }
        : {},
    });
  };
  const prendre = async (p) => { try { await p; return null; } catch (e) { return e; } };

  // ── a. L'index sait la génération, et c'est GRATUIT ────────────────
  const idx = {
    runs: [{
      run: RUN, domaine: DOM,
      cles: [`agrume/grille/${DOM}/${RUN}/e00.bin`,
             `agrume/grille/${DOM}/${RUN}/e01.bin`,
             CLE_COL, `agrume/grille/${DOM}/${RUN}/manifest.json`],
    }],
    // ⚠️ L'horodatage de l'index amorce la chaîne de jetons : il est le
    // seul que ni un navigateur ni un CDN ne peut avoir périmé.
    ecrit_le: '2026-08-13T23:36:02Z',
  };
  verifier('l\'index compte les échéances par ses clés `e{step}.bin` — sans '
    + 'une requête de plus', L.echeancesDansIndex(idx, RUN, DOM) === NECH);
  verifier('⚠️ un index d\'avant l\'étape 12 (entrée sans `cles`) rend `null` '
    + '— on ne conclut pas d\'une absence',
    L.echeancesDansIndex({ runs: [{ run: RUN, domaine: DOM }] }, RUN, DOM)
      === null);
  verifier('le manifeste de la BONNE génération passe',
    L.verifierGeneration(idx, MAN) === undefined);
  {
    const e = (() => { try { L.verifierGeneration(idx, MAN_VIEUX); return null; }
                       catch (x) { return x; } })();
    verifier('⛔⛔ LE CAS SILENCIEUX : un manifeste PÉRIMÉ est démasqué par '
      + 'l\'index, alors que les octets, eux, passeraient sans broncher',
      e instanceof L.GenerationIncoherente && e.quoi === 'manifeste',
      e ? e.message.slice(0, 60) + '…' : 'RIEN LEVÉ');
  }

  // ── b. Manifeste neuf + octets vieux → 416, et le BON message ──────
  const vieuxOctets = octets.slice(0, 4 * 24);   // l'objet de la 1ʳᵉ passe
  {
    // La colonne (1,1) est au-delà de la fin de l'ancien objet : c'est
    // exactement le point de Yann, au sud de 45,575 N sur la vraie
    // grille.
    const e = await prendre(L.chargerColonne(
      '', MAN, 45, 7, ZSOL, servir(vieuxOctets)));
    verifier('⛔ manifeste NEUF + octets VIEUX → 416 typé, pas une erreur nue',
      e instanceof L.GenerationIncoherente && e.quoi === 'octets');
    verifier('⛔ …et le message n\'accuse PLUS la rétention : le run est là, '
      + 'entier, c\'est le cache qui est vieux',
      !!e && !/DÉFINITIVEMENT parti/.test(e.message)
      && /cache/.test(e.message), e ? '' : 'RIEN LEVÉ');
    // ⚠️ `exposeTotal: false` = la production d'aujourd'hui : le bucket
    // n'expose PAS `Content-Range` (il n'est pas dans la liste blanche
    // CORS). C'est ce qui rend ce cas-ci invisible côté client, et c'est
    // exactement pour ça que le fix de FOND est côté serveur.
    verifier('⚠️ …et le NORD de la même grille passe encore sans broncher — '
      + 'c\'est ce qui fait ressembler le bug à « certains afficheurs » '
      + 'plutôt qu\'à une panne',
      (await prendre(L.chargerColonne(
        '', MAN, 46, 6, ZSOL, servir(vieuxOctets, { exposeTotal: false }))))
        === null,
      'colonne 0 : offset 0 < 96 o, le Range tombe dans l\'ancien objet');
  }

  // ── c. Un 404, lui, EST la rétention ───────────────────────────────
  {
    const e = await prendre(L.chargerColonne('', MAN, 45, 7, ZSOL,
      async () => new Response(null, { status: 404 })));
    verifier('⚠️ un 404 garde le message de la rétention — trois statuts, '
      + 'trois causes, trois réparations',
      !!e && /DÉFINITIVEMENT parti/.test(e.message)
      && !(e instanceof L.GenerationIncoherente));
  }

  // ── d. Le voisin du 416 : la colonne à cheval sur la fin ───────────
  {
    // 3 colonnes et demie : le début du Range de la 4ᵉ est valide, la fin
    // déborde, le serveur RABOTE et rend 206.
    const e = await prendre(L.chargerColonne(
      '', MAN, 45, 7, ZSOL, servir(octets.slice(0, TOTAL - 8),
        { exposeTotal: false })));
    verifier('⛔ un 206 RABOTÉ est refusé lui aussi — sans ça il finirait en '
      + '« tranche hors du tampon », à trois fonctions de sa cause',
      e instanceof L.GenerationIncoherente && /plus court/.test(e.message));
  }

  // ── e. Content-Range, quand le bucket l'expose ─────────────────────
  {
    const long = new ArrayBuffer(TOTAL * 2);
    new Uint8Array(long).set(new Uint8Array(octets));
    const e = await prendre(L.chargerColonne('', MAN, 46, 6, ZSOL,
      servir(long)));
    verifier('⚠️ un objet TROP LONG pour ce manifeste est vu quand le bucket '
      + 'expose `Content-Range` — le seul contrôle qui voie les DEUX sens',
      e instanceof L.GenerationIncoherente && /le manifeste en décrit/.test(e.message));
    const ok = await prendre(L.chargerColonne('', MAN, 46, 6, ZSOL,
      servir(long, { exposeTotal: false })));
    verifier('…et son absence ne fabrique pas de faux positif : sans l\'en-tête '
      + 'CORS, la longueur reçue reste juste et la colonne est servie',
      ok === null);
  }

  // ── f. Le cas nominal passe toujours ───────────────────────────────
  {
    const col = await L.chargerColonne('', MAN, 45, 7, ZSOL, servir(octets));
    verifier('le cas nominal est servi, et c\'est la BONNE colonne',
      col.j === 1 && col.i === 1 && col.tranches.u[0] === 13,
      `u = ${col.tranches.u[0]} (marque de la colonne 3)`);
  }

  // ── f bis. LE JETON D'URL — parce que le rejeu n'a pas suffi ───────
  // ⛔ CONSTATÉ À L'ÉCRAN LE 14/08 : `cache: 'reload'` n'a PAS débloqué
  // l'appareil, pendant que `curl` obtenait un 206 sur l'offset exact,
  // à la seconde près. Un `reload` ne bat que le cache HTTP du
  // navigateur — ni un cache d'entité partielle (Chrome rend un 416
  // depuis la taille qu'il croit connaître, sans requête), ni un
  // intermédiaire qui ignore le `no-cache` d'un client. Une URL
  // différente, elle, est une clé différente pour TOUS les caches.
  {
    verifier('le jeton se colle sur l\'URL, et il est encodé',
      L.avecJeton('https://x/colonnes.bin', '2026-08-13T23:33:00Z')
        === 'https://x/colonnes.bin?g=2026-08-13T23%3A33%3A00Z');
    verifier('⚠️ deux générations du même run donnent deux URL — c\'est TOUT '
      + 'ce qu\'il faut pour qu\'un cache empoisonné devienne inatteignable',
      L.avecJeton('u', 'A') !== L.avecJeton('u', 'B'));
    verifier('⚠️ un manifeste sans `genere_le` (produit d\'avant le 14/08) '
      + 'laisse l\'URL intacte plutôt que de fabriquer un `?g=undefined`',
      L.avecJeton('u', undefined) === 'u' && L.avecJeton('u', null) === 'u');
    let vue = null;
    await L.chargerColonne('', { ...MAN, genere_le: '2026-08-13T23:33:00Z' },
      46, 6, ZSOL, async (url, init) => { vue = url; return servir(octets)(url, init); });
    verifier('⛔ `chargerColonne` demande bien l\'URL JETONNÉE — sans ça tout '
      + 'le reste de cette section ne protège rien',
      /\?g=2026-08-13T23%3A33%3A00Z$/.test(vue), vue);
  }

  // ── g. Le rejeu qui débloque un appareil empoisonné ────────────────
  // ⛔ C'EST LA VÉRIFICATION QUI COMPTE POUR L'UTILISATEUR. Le fix
  // serveur empêche que ça recommence ; celui-ci répare les appareils
  // DÉJÀ empoisonnés sans attendre l'expiration des 6 h.
  {
    const A = await import(process.env.BW_AGRUME_MODULE
      || join(ici, '..', '..', 'web', 'src', 'lib', 'agrumeProfile.ts'));
    let reloads = 0, passes = 0, urlMan = null;
    const cache = async (url, init) => {
      const frais = init?.cache === 'reload';
      if (frais) reloads++;
      if (url.endsWith('index.json')) return Response.json(idx);
      // ⚠️ `includes` et pas `endsWith` : l'URL du manifeste porte
      // maintenant le jeton de l'index en paramètre de requête.
      if (url.includes('manifest.json')) {
        urlMan = url;
        passes++;
        // ⚠️ Le cache rend le VIEUX manifeste tant qu'on ne force pas la
        // revalidation : c'est le comportement exact d'un `max-age` non
        // expiré, et c'est ce que le rejeu doit vaincre.
        return Response.json(frais ? MAN : MAN_VIEUX);
      }
      if (url.endsWith('zsol.bin')) return new Response(ZSOL.buffer);
      return servir(octets)(url, init);
    };
    const r = await A.chargerProfilAgrume('', 45.5, 6.5, cache);
    verifier('⛔ un appareil empoisonné se répare TOUT SEUL, en une relecture '
      + 'forcée, sans attendre les 6 h de cache',
      r.profil.times.length === NECH && reloads > 0 && passes === 2,
      `${passes} lectures du manifeste, ${reloads} en \`cache: reload\``);
    verifier('⛔ …et l\'URL du manifeste porte le jeton de l\'INDEX — la seule '
      + 'pièce qu\'aucun cache ne peut avoir périmée',
      /\?g=2026-08-13T23%3A36%3A02Z$/.test(urlMan ?? ''), urlMan);
    verifier('⚠️ et UN SEUL rejeu : une incohérence qui persiste doit rester '
      + 'visible, pas devenir lente',
      await (async () => {
        let n = 0;
        const toujours = async (url, init) => {
          if (url.includes('manifest.json')) { n++; return Response.json(MAN_VIEUX); }
          return cache(url, init);
        };
        const e = await prendre(A.chargerProfilAgrume('', 45.5, 6.5, toujours));
        return e instanceof L.GenerationIncoherente && n === 2;
      })());
  }
}

console.log('\n── 12. ⛔ LE RECOLLEMENT DU RUN PRÉCÉDENT (A25) ──');
// ══════════════════════════════════════════════════════════════════════
//  La coupe d'AGRUME commençait à l'heure du RUN, pas à l'heure du JOUR :
//  un run 09 Z ouvrait la journée à 11:00 locales et le matin de vol
//  n'existait pas. A25 va relire, dans les runs antérieurs encore en
//  ligne, l'échéance qui tombe sur chaque heure manquante.
//
//  ⛔ LE DÉFAUT QUE CETTE SECTION EXISTE POUR ATTRAPER : indexer la
//  colonne recollée par le RANG de l'heure dans la frise au lieu de
//  l'INDICE DE SON ÉCHÉANCE dans le run antérieur. Un run de 08:00 qui
//  sert 10:00 le sert à son échéance 2 ; une couture par rang lirait son
//  échéance 0 — la bonne heure affichée, la mauvaise prévision dedans,
//  et pas une requête en échec.
//
//  ⛔ ET LE SECOND : préférer le run le plus RÉCENT sans regarder τ. À
//  τ = 0 le produit n'archive ni pluie, ni rafale, ni nébulosité
//  (`absent_a_tau0`) — servir l'échéance 0 du run précédent aurait troué
//  la ligne « Précipitation » à l'heure pile où ce run démarre.
{
  const A = await import(process.env.BW_AGRUME_MODULE
    || join(ici, '..', '..', 'web', 'src', 'lib', 'agrumeProfile.ts'));

  const H = 3_600_000;
  const DOM = 'nord-alpes';
  const NB_LAT = 2, NB_LON = 2;
  // Les sept tranches : six de colonne + `precipitation`, qui est une
  // tranche de surface à UN niveau (c'est ainsi que `serieSurf` la lit).
  const CLES = ['ziso', 'psol', 'u', 'v', 'iso_u', 'iso_v', 'precipitation'];

  // ⚠️ L'HEURE DE RÉFÉRENCE EST DÉRIVÉE DE `debutJourneeLocale`, pas
  // écrite en dur : le banc doit rendre le même verdict sur le Mac de
  // Yann (Europe/Paris) et sur un runner en UTC. Écrire « 05:00 Z »
  // aurait fait un banc vert chez l'un et rouge chez l'autre — c'est-à-
  // dire un banc qu'on finit par désactiver.
  const MAINTENANT = Date.UTC(2026, 7, 20, 9, 30);
  const BORNE = A.debutJourneeLocale(MAINTENANT, 7);   // 07:00 locales
  const iso = (t) => new Date(t).toISOString();
  const R_COURANT = iso(BORNE + 4 * H);   // ouvre la journée à borne+4
  const R_PREC = iso(BORNE + 1 * H);
  const R_VIEUX = iso(BORNE - 2 * H);

  const tr = (offset, octets) => ({ offset, octets, dtype: 'float32' });
  const manifeste = (run, nbEch, opts = {}) => ({
    run, domaine: opts.domaine ?? DOM,
    echeances: Array.from({ length: nbEch }, (_, k) => k),
    niveaux_m_sol: [10], niveaux_hpa: [900],
    bornes: { latmin: 45, latmax: 46, lonmin: 6, lonmax: 7 },
    axes: {
      nb_lat: NB_LAT, nb_lon: opts.nbLon ?? NB_LON,
      lat_premier: 46, lat_dernier: 45,
      lon_premier: 6, lon_dernier: 7, sens: 'lats DÉCROISSANTES',
    },
    retention_runs: 3,
    parametres_surface: [
      { nom: 'psol', unite: 'hPa', paquet: 'SP1', pas_de_temps: 'instant',
        absent_a_tau0: false, decalage_precision: 0 },
      { nom: 'precipitation', unite: 'mm', paquet: 'SP1',
        pas_de_temps: 'cumul', absent_a_tau0: true,
        decalage_precision: opts.decPrecip ?? 0 },
    ],
    service: {
      cle_echeance: `agrume/grille/{domaine}/{run}/e{step:02d}.bin`,
      cle_zsol: `agrume/grille/{domaine}/{run}/zsol.bin`,
      cle_colonnes: `agrume/grille/{domaine}/{run}/colonnes.bin`,
      disposition_tampon: '', encodage: 'float32', tranches: {},
      octets_par_echeance: 64,
      colonnes: {
        disposition: '', offset: '', note: '',
        octets_par_colonne: CLES.length * 4 * nbEch,
        tranches: Object.fromEntries(
          CLES.map((c, k) => [c, tr(k * 4 * nbEch, 4 * nbEch)])),
      },
    },
  });

  // La marque d'une valeur : `1000 × rang du run + τ`. Elle dit à la fois
  // DE QUEL RUN et DE QUELLE ÉCHÉANCE vient chaque case — c'est tout ce
  // qu'il faut pour prendre une couture par rang la main dans le sac.
  const octetsDe = (nbEch, rang) => {
    const pas = CLES.length * 4 * nbEch;
    const buf = new ArrayBuffer(NB_LAT * NB_LON * pas);
    const vue = new DataView(buf);
    for (let c = 0; c < NB_LAT * NB_LON; c++) {
      for (let k = 0; k < CLES.length; k++) {
        for (let e = 0; e < nbEch; e++) {
          const o = c * pas + k * 4 * nbEch + 4 * e;
          if (CLES[k] === 'ziso') vue.setFloat32(o, 1500, true);
          else if (CLES[k] === 'psol') vue.setFloat32(o, 910, true);
          else vue.setFloat32(o, 1000 * rang + e, true);
        }
      }
    }
    return buf;
  };

  const MAN = {
    [R_COURANT]: manifeste(R_COURANT, 4),
    [R_PREC]: manifeste(R_PREC, 7),
    [R_VIEUX]: manifeste(R_VIEUX, 10),
  };
  const OCTETS = {
    [R_COURANT]: octetsDe(4, 0),
    [R_PREC]: octetsDe(7, 1),
    [R_VIEUX]: octetsDe(10, 2),
  };
  const ZSOL = Float32Array.from([1000, 1000, 1000, 1000]);
  const IDX = {
    runs: [R_COURANT, R_PREC, R_VIEUX].map(run => ({ run, domaine: DOM })),
    ecrit_le: '2026-08-20T09:31:00Z',
  };

  const serveur = (mans = MAN) => async (url, init) => {
    const chemin = String(url).split('?')[0];
    if (chemin.endsWith('index.json')) return Response.json(IDX);
    const m = /\/grille\/[^/]+\/([^/]+)\/([^/]+)$/.exec(chemin);
    if (!m) return new Response(null, { status: 404 });
    const [, run, objet] = m;
    if (objet === 'manifest.json') {
      return mans[run]
        ? Response.json(mans[run]) : new Response(null, { status: 404 });
    }
    if (objet === 'zsol.bin') return new Response(ZSOL.buffer);
    const corps = OCTETS[run];
    if (!corps) return new Response(null, { status: 404 });
    const r = /bytes=(\d+)-(\d+)/.exec(init?.headers?.Range ?? '');
    if (!r) return new Response(corps, { status: 200 });
    const [d, f] = [Number(r[1]), Number(r[2])];
    if (d >= corps.byteLength) return new Response(null, { status: 416 });
    const fin = Math.min(f, corps.byteLength - 1);
    return new Response(corps.slice(d, fin + 1), {
      status: 206,
      headers: { 'Content-Range': `bytes ${d}-${fin}/${corps.byteLength}` },
    });
  };

  // ── a. Les runs antérieurs, et l'ordre ─────────────────────────────
  verifier('les runs antérieurs sortent du plus RÉCENT au plus ancien, et '
    + 'le run courant n\'en fait pas partie',
    A.runsAnterieurs(IDX, DOM, R_COURANT).join() === [R_PREC, R_VIEUX].join());
  verifier('⚠️ un autre domaine ne se glisse pas dans la liste — une '
    + 'colonne prise sur une autre grille serait une coupe plausible au '
    + 'mauvais endroit',
    A.runsAnterieurs(
      { runs: [{ run: R_PREC, domaine: 'pyrenees' }] }, DOM, R_COURANT,
    ).length === 0);

  // ── b. LE PLAN : quelle heure, quel run, quelle échéance ───────────
  const plan = A.planRecollement(BORNE + 4 * H,
    [MAN[R_PREC], MAN[R_VIEUX]], MAINTENANT, 7);
  verifier('le plan couvre les QUATRE heures qui manquent, et pas une de '
    + 'plus : on ne remonte pas avant la première heure affichable',
    plan.length === 4
      && plan[0].instant === BORNE && plan[3].instant === BORNE + 3 * H,
    plan.map(c => new Date(c.instant).toISOString()).join(' '));
  verifier('⛔ L\'INDICE EST CELUI DE L\'ÉCHÉANCE, PAS LE RANG DE L\'HEURE : '
    + 'borne+3 est servie par le run de borne+1 à son échéance 2',
    plan[3].run === R_PREC && plan[3].tau === 2 && plan[3].e === 2,
    `${plan[3].run} τ=${plan[3].tau} e=${plan[3].e}`);
  verifier('⛔ ET L\'ÉCHÉANCE 0 EST ÉVITÉE : borne+1 est l\'échéance 0 du run '
    + 'de borne+1 (ni pluie, ni rafale, ni nébulosité) — c\'est le run '
    + 'PLUS ANCIEN qui la sert, à τ = 3',
    plan[1].run === R_VIEUX && plan[1].tau === 3,
    `${plan[1].run} τ=${plan[1].tau}`);
  verifier('…et aucune des quatre heures ne tombe sur un τ = 0',
    plan.every(c => c.tau > 0));
  {
    // Le run le plus ancien retiré : il ne reste que celui qui commence à
    // borne+1. Deux heures deviennent inatteignables, et la troisième ne
    // peut plus être servie qu'à τ = 0 — ce qui doit se DIRE.
    const seul = A.planRecollement(BORNE + 4 * H, [MAN[R_PREC]], MAINTENANT, 7);
    verifier('⚠️ faute de mieux, τ = 0 est accepté — mais il reste '
      + 'identifiable, et l\'écran le dit',
      seul.length === 3 && seul[0].tau === 0 && seul[0].instant === BORNE + H,
      seul.map(c => `τ=${c.tau}`).join(' '));
  }
  verifier('⚠️ un run courant qui ouvre lui-même la journée ne demande rien',
    A.planRecollement(BORNE, [MAN[R_PREC], MAN[R_VIEUX]], MAINTENANT, 7)
      .length === 0);

  // ── c. LA COUTURE, et la version naïve qui doit échouer ────────────
  const colDe = async (run) => L.chargerColonne(
    '', MAN[run], 45.5, 6.5, ZSOL, serveur());
  {
    const courant = await colDe(R_COURANT);
    const morceaux = [];
    for (const c of plan) morceaux.push({ choix: c, col: await colDe(c.run) });
    const { colonne, runs, tau0 } = A.coudreColonnes(
      MAN[R_COURANT], courant, morceaux);
    verifier('la colonne cousue porte les 4 heures recollées PUIS les 4 du '
      + 'run courant, et les échéances deviennent négatives devant',
      colonne.echeances.join() === '-4,-3,-2,-1,0,1,2,3',
      colonne.echeances.join());
    // ⛔ LE CONTRÔLE QUI COMPTE. `u` vaut `1000 × rang + τ` : la valeur
    // dit d'où elle vient. Attendu, dans l'ordre :
    //   borne+0 ← vieux τ=2 → 2002   borne+1 ← vieux τ=3 → 2003
    //   borne+2 ← préc  τ=1 → 1001   borne+3 ← préc  τ=2 → 1002
    const lus = Array.from(colonne.tranches.u.slice(0, 4));
    verifier('⛔ CHAQUE HEURE RECOLLÉE PORTE LA VALEUR DE SON ÉCHÉANCE, pas '
      + 'celle de son rang dans la frise',
      lus.join() === '2002,2003,1001,1002', lus.join());
    // …et la preuve que le banc sait échouer : la couture NAÏVE, celle
    // qui indexe par le rang `p` au lieu de `choix.e`.
    const naif = plan.map((c, p) => morceaux[p].col.tranches.u[p]);
    verifier('⚠️ …et la couture par RANG donne autre chose — le banc sait '
      + 'donc échouer sur exactement ce défaut',
      naif.join() !== lus.join(), `naïf = ${naif.join()}`);
    verifier('le run courant n\'est pas touché : ses 4 échéances restent en '
      + 'place, à la suite',
      Array.from(colonne.tranches.u.slice(4)).join() === '0,1,2,3');
    verifier('la provenance par instant est indexée comme la colonne — '
      + '4 heures nommées, puis `null` sur tout le run courant',
      runs.length === 8 && runs[0] === R_VIEUX && runs[3] === R_PREC
        && runs.slice(4).every(r => r === null));
    verifier('…et aucune des quatre n\'est marquée τ = 0',
      tau0.length === 8 && tau0.every(x => x === false));
  }

  // ── d. `memeDecoupage` — ce qu'on refuse de coudre ─────────────────
  verifier('deux runs du même produit se cousent, même avec un nombre '
    + 'd\'échéances DIFFÉRENT (25 contre 52 en production)',
    A.memeDecoupage(MAN[R_COURANT], MAN[R_PREC]) === null);
  verifier('⛔ un run dont un `decalage_precision` diffère est ÉCARTÉ — '
    + 'c\'est le seul écart qui donnerait une valeur finie et FAUSSE',
    /décalage de précision/.test(
      A.memeDecoupage(MAN[R_COURANT],
        manifeste(R_PREC, 7, { decPrecip: -1000 })) ?? ''));
  verifier('⛔ …et un run dont la grille a bougé aussi',
    /axes différents/.test(
      A.memeDecoupage(MAN[R_COURANT],
        manifeste(R_PREC, 7, { nbLon: 3 })) ?? ''));
  verifier('⛔ …et un run d\'un autre domaine',
    /domaine/.test(
      A.memeDecoupage(MAN[R_COURANT],
        manifeste(R_PREC, 7, { domaine: 'pyrenees' })) ?? ''));

  // ── e. LE DÉCALAGE DU RAFRAÎCHISSEMENT ────────────────────────────
  // ⛔ `provenance`/`ajoutee` sont indexés comme `profil.times`. Coudre
  // 4 heures devant SANS les décaler attribuerait à 07:00 la provenance
  // de 11:00 — et l'écran refuserait même de l'afficher, puisqu'il
  // compare les longueurs.
  {
    const raf = {
      etat: 'applique',
      provenance: [{ modele: 'arome+pi', poids_pi: 1, regime_temporel: 'x' }, null],
      ajoutee: [true, false],
      runPi: 'x', runB: 'y', ajoutees: 1, remplacees: 1, total: 2,
      octets: 0, interpolees: [],
    };
    const d = A.decalerRafraichissement(raf, 4);
    verifier('⛔ le rafraîchissement est décalé de 4, et le poids PI reste '
      + 'sur SON instant — pas sur celui d\'à côté',
      d.provenance.length === 6 && d.ajoutee.length === 6
        && d.provenance.slice(0, 4).every(p => p === null)
        && d.provenance[4]?.poids_pi === 1 && d.ajoutee[4] === true);
    verifier('⚠️ zéro heure cousue = l\'objet d\'origine, intact',
      A.decalerRafraichissement(raf, 0) === raf);
    verifier('⚠️ et un rafraîchissement ABSENT ne se décale pas — il n\'a '
      + 'pas de tableau à décaler',
      A.decalerRafraichissement({ etat: 'absent', raison: 'x', texte: 'y' }, 4)
        .etat === 'absent');
  }

  // ── f. LE CHEMIN COMPLET, de l'index au profil ────────────────────
  {
    const r = await A.chargerProfilAgrume('', 45.5, 6.5, serveur(),
      { maintenant: MAINTENANT, heureDebut: 7 });
    verifier('⛔ la journée commence à 07:00 locales, pas à l\'heure du run',
      r.profil.times[0] === BORNE,
      `${new Date(r.profil.times[0]).toISOString()} contre ${iso(BORNE)}`);
    verifier('le recollement est appliqué et NOMME ses runs, du plus récent '
      + 'au plus ancien',
      r.recol.etat === 'applique'
        && r.recol.detail.map(d => `${d.run}:${d.heures}`).join()
          === `${R_PREC}:2,${R_VIEUX}:2`,
      JSON.stringify(r.recol.detail));
    verifier('⛔ les tableaux de provenance ont EXACTEMENT la longueur de '
      + '`times` — c\'est ce que l\'écran vérifie avant d\'afficher un '
      + 'liseré, et une longueur fausse le ferait disparaître en silence',
      r.recol.runs.length === r.profil.times.length
        && r.recol.tau0.length === r.profil.times.length);
    // La précipitation porte la même marque que `u` : elle prouve que la
    // ligne de surface suit la couture, et pas seulement la colonne d'air.
    const p = r.profil.surface.precipitation.slice(0, 4);
    verifier('⚠️ la ligne de SURFACE suit la couture elle aussi — la pluie '
      + 'des heures recollées vient de la bonne échéance du bon run',
      p.join() === '2002,2003,1001,1002', p.join());
    verifier('le vent des heures recollées est bien du vent, pas des `null` '
      + 'polis', r.profil.levels[0].windSpeed.slice(0, 4).every(v => v != null));
  }

  // ── g. QUAND ON NE RECOLLE PAS, ON DIT POURQUOI ───────────────────
  {
    const seul = { runs: [{ run: R_COURANT, domaine: DOM }], ecrit_le: IDX.ecrit_le };
    const srv = async (url, init) => (String(url).includes('index.json')
      ? Response.json(seul) : serveur()(url, init));
    const r = await A.chargerProfilAgrume('', 45.5, 6.5, srv,
      { maintenant: MAINTENANT, heureDebut: 7 });
    verifier('⛔ aucun run antérieur en ligne : la coupe reste servie, et la '
      + 'raison est NOMMÉE — jamais un silence',
      r.recol.etat === 'absent' && r.recol.raison === 'aucun-run-anterieur'
        && r.profil.times.length === 4,
      r.recol.texte);
  }
  {
    // Le run précédent a changé de découpe : on l'écarte, on le DIT, et
    // le plus ancien prend le relais sur les heures qu'il sait dire.
    const mans = { ...MAN, [R_PREC]: manifeste(R_PREC, 7, { decPrecip: -1000 }) };
    const r = await A.chargerProfilAgrume('', 45.5, 6.5, serveur(mans),
      { maintenant: MAINTENANT, heureDebut: 7 });
    verifier('⛔ un run d\'une autre génération est ÉCARTÉ NOMMÉMENT, et le '
      + 'plus ancien prend le relais',
      r.recol.etat === 'applique'
        && r.recol.ecartes.length === 1 && r.recol.ecartes[0].run === R_PREC
        && r.recol.detail.every(d => d.run === R_VIEUX),
      JSON.stringify(r.recol.ecartes));
    // ⚠️ ET LE MATIN N'EST PAS PERDU POUR AUTANT : le run le plus ancien
    // couvre les quatre heures, toutes à τ ≥ 1. C'est précisément ce que
    // la rétention à trois runs achète — le premier repli existe.
    verifier('⚠️ …et le plus ancien couvre les QUATRE heures à lui seul : '
      + 'la journée commence quand même à 07:00',
      r.recol.detail.length === 1 && r.recol.detail[0].heures === 4
        && r.profil.times[0] === BORNE,
      JSON.stringify(r.recol.detail));
  }
  {
    // Le run courant ouvre lui-même la journée : il n'y a rien à recoller,
    // et ce n'est pas un incident. ⚠️ Aucun manifeste antérieur n'est
    // même lu — un Range pour rien est un coût sans question.
    let lus = 0;
    const compte = async (url, init) => {
      if (String(url).includes('manifest.json')) lus++;
      return serveur()(url, init);
    };
    const r = await A.chargerProfilAgrume('', 45.5, 6.5, compte,
      { maintenant: MAINTENANT, heureDebut: 12 });
    verifier('⚠️ « rien à recoller » ne coûte AUCUNE requête de plus — un '
      + 'seul manifeste lu, celui du run affiché',
      r.recol.etat === 'absent' && r.recol.raison === 'rien-a-recoller'
        && lus === 1, `${lus} manifeste(s) lu(s)`);
  }
}

console.log(`\n  calque altitude (JS) : ${echecs ? `ÉCHEC (${echecs})` : 'OK'}`);
process.exit(echecs ? 1 : 0);
