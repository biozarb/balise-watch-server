#!/usr/bin/env node
// ══════════════════════════════════════════════════════════════════════
//  tools/rafraichissement-client-selftest.mjs — LE BANC DU LOT L3a
//                                                          (17/08/2026)
//
//      node --experimental-strip-types \
//           tools/rafraichissement-client-selftest.mjs [--production]
//
//  Il vérifie le CÔTÉ CLIENT du rafraîchissement PI : la découverte par
//  le manifeste du produit B, le contrôle des axes, le calcul de
//  l'échéance par INSTANTS, le Range à offsets relatifs, la préséance
//  u/v et la phrase « nourri par ».
//
//  ⛔⛔ CE BANC EXISTE POUR LES QUATRE FAÇONS DE MENTIR SANS ERREUR, et
//  chacune a déjà été payée ailleurs dans ce projet :
//
//    1. lire `echeances_min[echeanceH]` au lieu de chercher l'INSTANT —
//       juste une fois sur huit (quand les deux runs coïncident), et le
//       reste du temps une carte lisse portant six heures de dérive de
//       modèle. C'est le défaut que le Lot L2 a trouvé côté serveur, le
//       matin même, dans son propre cahier des charges ;
//    2. lire les offsets de tranche comme ABSOLUS alors que le manifeste
//       les publie relatifs au bloc d'échéance — `v` décodé à la place
//       de `u`, donc un vent tourné de 90°, sans une seule exception ;
//    3. écraser le produit B avec une grille aux axes VOISINS — une
//       colonne vaut 1,95 km, et les deux chaînes ont déjà différé d'une
//       colonne le 10/08 ;
//    4. affirmer « PI » sur une échéance dont `poids_pi` vaut 0 — à 6 h
//       la rampe d'horizon a éteint Δ et il n'y a plus une trace de PI
//       nulle part, y compris à 20 m.
//
//  ⚠️ ET IL DOIT SAVOIR ÉCHOUER. Le Lot L2 a découvert le 17/08 qu'un
//  banc peut prouver l'EXISTENCE d'un garde-fou sans prouver son
//  BRANCHEMENT : quatre contrôles au vert avec l'appel retiré du
//  pipeline. Les sections 3 et 5 passent donc par la chaîne entière
//  (`chargerRafraichissement`, `chargerBloc`) et pas par la fonction
//  isolée. La table des sabotages rejoués est dans la note de session.
//
//  ⓘ `--production` ajoute la seule vérification qui compte vraiment :
//  les OCTETS SERVIS. Sans réseau, tout le reste tourne hors ligne.
// ══════════════════════════════════════════════════════════════════════
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const ici = dirname(fileURLToPath(import.meta.url));
const MOD = join(ici, '..', '..', 'web', 'src', 'lib', 'rafraichissement.ts');
const R = await import(process.env.BW_RAF_MODULE || MOD);

const PROD = process.argv.includes('--production');
const BASE = process.env.BW_R2_BASE
  || 'https://pub-7a401bae4fe54a6c8dbdd6b5a33a7bec.r2.dev';

let echecs = 0;
const rouges = [];
const verifier = (nom, ok, detail = '') => {
  console.log(`  ${ok ? '✓' : '✗'} ${nom}${detail ? `   ${detail}` : ''}`);
  if (!ok) { echecs++; rouges.push(nom); }
};
// ⚠️ CHAQUE SECTION EST ISOLÉE. Le Lot L2 a trouvé qu'un banc qui MEURT
// ne dit pas ce qui a cédé : deux sabotages sortaient bien en 1, mais par
// exception non rattrapée, sans jamais imprimer la liste des rouges.
const section = async (titre, fn) => {
  console.log(`\n── ${titre} ──`);
  try { await fn(); } catch (e) {
    verifier(`${titre} — exception non rattrapée`, false, String(e.message || e));
  }
};

// ══════════════════════════════════════════════════════════════════════
//  Les fixtures — deux manifestes qui se correspondent, et le décalage
//  RÉEL mesuré le 17/08 : produit B 03 Z, PI 09 Z, donc 360 min.
// ══════════════════════════════════════════════════════════════════════
const NBLAT = 3, NBLON = 4, NBNIV = 2, NBCOL = NBLAT * NBLON;
const NIVEAUX = [10, 20];
const ECH_MIN = [0, 15, 30, 45, 60, 75, 90];   // 0 → 90 min, pas de 15
const RUN_B = '2026-08-17T03:00:00Z';
const RUN_PI = '2026-08-17T09:00:00Z';
const OCTETS_TRANCHE = NBNIV * NBCOL * 2;
const OCTETS_ECH = 2 * OCTETS_TRANCHE;

const POURQUOI = 'AROME-PI n’est ingéré que sur la boîte nord-alpes '
  + '(mesuré le 17/08/2026 : 207 balises servies sur les 288 de '
  + 'l’archive). Le domaine pyrenees n’en reçoit aucun champ — ce n’est '
  + 'pas une panne ni un trou de données, c’est la portée actuelle de '
  + 'l’ingestion.';

const pointeur = () => ({
  gabarit_cle: 'agrume/pi/rafraichissement/{domaine}/{run_pi}/{objet}',
  cle_index: 'agrume/pi/rafraichissement/index.json',
  blocs_concernes: ['hauteur'],
  parametres_concernes: ['u', 'v'],
  horizon_min: 90,
  echeances_min: [...ECH_MIN],
  preseance: 'u et v du bloc hauteur seulement',
});

const manB = (extra = {}) => ({
  run: RUN_B, domaine: 'nord-alpes', grille: '0025',
  echeances: [0, 1, 2, 3, 4, 5, 6, 7, 8],
  niveaux_m_sol: [...NIVEAUX], niveaux_hpa: [], parametres: [],
  parametres_isobares: [], retention_runs: 3,
  axes: {
    nb_lat: NBLAT, nb_lon: NBLON, lat_premier: 46.45, lat_dernier: 46.4,
    lon_premier: 5, lon_dernier: 5.075, sens: 'lats décroissantes',
  },
  provenance: {
    granularite: 'echeance x bloc', blocs: ['hauteur'], par_echeance: [],
    arome_pi: {
      disponible: true, domaines_couverts: ['nord-alpes'],
      pourquoi: null, rafraichissement: pointeur(),
    },
  },
  service: {
    cle_echeance: 'agrume/grille/{domaine}/{run}/e{step:02d}.bin',
    cle_zsol: '', cle_colonnes: '', disposition_tampon: '', encodage: '',
    tranches: {}, octets_par_echeance: 0,
    colonnes: { disposition: '', octets_par_colonne: 0, offset: '', tranches: {}, note: '' },
  },
  ...extra,
});

const manRaf = (extra = {}) => ({
  run_pi: RUN_PI, run_produit_b: RUN_B, domaine: 'nord-alpes',
  decalage_min: 360,
  echeances_produit_b_lues: [6, 7, 8],
  echeances_min: [...ECH_MIN], horizon_min: 90,
  niveaux_m_sol: [...NIVEAUX],
  axes: {
    nb_lat: NBLAT, nb_lon: NBLON, lat_premier: 46.45, lat_dernier: 46.4,
    lon_premier: 5, lon_dernier: 5.075, sens: 'lats décroissantes',
  },
  service: {
    cle_carte: `agrume/pi/rafraichissement/nord-alpes/${RUN_PI}/carte.bin`,
    cle_colonnes: `agrume/pi/rafraichissement/nord-alpes/${RUN_PI}/colonnes.bin`,
    cle_index: 'agrume/pi/rafraichissement/index.json',
    carte: {
      disposition: '(echeance, tranche, niveau, lat, lon)',
      octets_par_echeance: OCTETS_ECH,
      offset: 'index × octets_par_echeance',
      tranches: {
        u: { offset: 0, octets: OCTETS_TRANCHE, dtype: 'float16', niveaux: NBNIV, bloc: 'hauteur' },
        v: { offset: OCTETS_TRANCHE, octets: OCTETS_TRANCHE, dtype: 'float16', niveaux: NBNIV, bloc: 'hauteur' },
      },
    },
    colonnes: { disposition: '', octets_par_colonne: 0, offset: '', tranches: {} },
  },
  niveaux: NIVEAUX.map(z => ({
    niveauMSol: z, resolutionTemporelleMin: 15,
    regime: 'observée (PI)', erreurInterpolationMs: 0,
  })),
  niveaux_valables_si: 'à poids_pi = 1',
  poids_pi: ECH_MIN.map((_, k) => (k < 5 ? 1 : 1 - (k - 4) * 0.5)),
  provenance: {
    granularite: 'echeance x bloc', blocs: ['hauteur'],
    modeles: {
      arome: { nom: 'AROME 0,025°', runs_par_jour: 8, resolution_temporelle_min: 60, run: RUN_B },
      arome_pi: { nom: 'AROME-PI 0,025°', runs_par_jour: 24, resolution_temporelle_min: 15, run: RUN_PI },
    },
    par_echeance: ECH_MIN.map((m, k) => {
      const w = k < 5 ? 1 : Math.max(0, 1 - (k - 4) * 0.5);
      return {
        echeance_min: m,
        blocs: {
          hauteur: w > 0
            ? { modele: 'arome+pi', run: RUN_B, run_pi: RUN_PI, poids_pi: w,
                regime_temporel: 'PI seul maître sous 500 m/sol' }
            : { modele: 'arome', run: RUN_B, poids_pi: 0,
                regime_temporel: 'au-delà de l’horizon utile de PI' },
        },
      };
    }),
  },
  preseance: 'u et v du bloc hauteur seulement',
  retention_runs: 3,
  remplissage: { u: 1, v: 1 },
  ...extra,
});

// ── Les octets de la fixture ──────────────────────────────────────────
// ⚠️ Des valeurs EXACTEMENT représentables en float16 (entiers), pour que
// le banc mesure la préséance et pas l'arrondi. Une case est NaN : c'est
// le « rien à en dire » qui doit retomber sur le produit B.
function enc16(x) {
  if (Number.isNaN(x)) return 0x7e00;
  const d = new DataView(new ArrayBuffer(4));
  d.setFloat32(0, x, true);
  const b = d.getUint32(0, true);
  const s = (b >>> 31) & 1;
  let e = (b >>> 23) & 0xff;
  const m = b & 0x7fffff;
  if (e === 0) return s << 15;
  e = e - 127 + 15;
  if (e >= 31) return (s << 15) | 0x7c00;
  if (e <= 0) return s << 15;
  return (s << 15) | (e << 10) | (m >>> 13);
}
/** u = 1000·(k+1) + 10·niveau + colonne, v = −u. La case (k, u, niveau 0,
 *  colonne 3) est NaN. Chaque octet dit donc d'où il vient. */
const CASE_NAN = 3;
function carteBin() {
  const buf = new ArrayBuffer(ECH_MIN.length * OCTETS_ECH);
  const vue = new DataView(buf);
  let o = 0;
  for (let k = 0; k < ECH_MIN.length; k++) {
    for (const signe of [1, -1]) {
      for (let n = 0; n < NBNIV; n++) {
        for (let c = 0; c < NBCOL; c++) {
          const nan = n === 0 && c === CASE_NAN;
          const val = nan ? NaN : signe * (1000 * (k + 1) + 10 * n + c);
          vue.setUint16(o, enc16(val), true);
          o += 2;
        }
      }
    }
  }
  return buf;
}
const CARTE = carteBin();

/** Un serveur de fixture : JSON pour l'index et le manifeste, Range sur
 *  `carte.bin`. ⚠️ Il ENREGISTRE le Range demandé — c'est ce qu'on veut
 *  vérifier, pas seulement ce qu'on décode. */
function serveur({ index, man, carte = CARTE }) {
  const vus = [];
  const fetchFn = async (url, init) => {
    const u = String(url).split('?')[0];
    const cle = u.replace(/^https?:\/\/[^/]+\//, '');
    vus.push({ cle, range: init?.headers?.Range ?? null });
    if (cle.endsWith('index.json')) {
      return { ok: true, status: 200, json: async () => index };
    }
    if (cle.endsWith('manifest.json')) {
      if (!man) return { ok: false, status: 404, json: async () => ({}) };
      return { ok: true, status: 200, json: async () => man };
    }
    if (cle.endsWith('carte.bin')) {
      const m = /bytes=(\d+)-(\d+)/.exec(init?.headers?.Range || '');
      if (!m) return { ok: true, status: 200, arrayBuffer: async () => carte };
      const a = Number(m[1]), b = Number(m[2]);
      return {
        ok: true, status: 206,
        headers: { get: () => `bytes ${a}-${b}/${carte.byteLength}` },
        arrayBuffer: async () => carte.slice(a, b + 1),
      };
    }
    return { ok: false, status: 404, json: async () => ({}) };
  };
  return { fetchFn, vus };
}
const INDEX = { dernier: { 'nord-alpes': RUN_PI }, runs: [], retention_runs: 3 };

// ══════════════════════════════════════════════════════════════════════
//  Lot L3b — le jumeau COLONNE, et la densification de l'axe
// ══════════════════════════════════════════════════════════════════════
//  ⚠️ `colonnes.bin` a une disposition (niveau, échéance) PAR COLONNE, et
//  un pas qui N'EST PAS celui du produit B. C'est le piège principal du
//  lot : le couple (j, i) est le même, la taille de l'enregistrement ne
//  l'est pas.
const OCT_TR_COL = NBNIV * ECH_MIN.length * 2;
const OCT_PAR_COL = 2 * OCT_TR_COL;

const colonnesRaf = (extra = {}) => ({
  disposition: 'un enregistrement par colonne, ordre (lat, lon)',
  octets_par_colonne: OCT_PAR_COL,
  offset: '(j * nb_lon + i) * octets_par_colonne',
  tranches: {
    u: { offset: 0, octets: OCT_TR_COL, dtype: 'float16', niveaux: NBNIV,
         echeances: ECH_MIN.length, bloc: 'hauteur' },
    v: { offset: OCT_TR_COL, octets: OCT_TR_COL, dtype: 'float16',
         niveaux: NBNIV, echeances: ECH_MIN.length, bloc: 'hauteur' },
  },
  ...extra,
});

/** `u = 400 + 100·colonne + 10·niveau + k`, `v = −u`. Chaque octet dit
 *  d'où il vient : la colonne, le niveau ET l'échéance.
 *
 *  ⛔⛔ ET LES VALEURS TIENNENT SOUS 2048, PARCE QUE C'EST UNE CONTRAINTE
 *  DU FORMAT, PAS UNE COQUETTERIE. Ce banc a été écrit une première fois
 *  avec une base à 7000 : au-dessus de 4096, le pas du float16 vaut 4, et
 *  7613 s'écrit 7612. Trois contrôles sont partis au rouge en accusant le
 *  code — qui était juste. L'en-tête de ce fichier le disait déjà (« des
 *  valeurs EXACTEMENT représentables en float16 ») ; je l'ai enfreint en
 *  ajoutant une fixture. ⚠️ Un banc qui mesure l'arrondi au lieu de la
 *  préséance est pire qu'un banc absent : il envoie chercher un défaut
 *  là où il n'y en a pas. Sous 2048, le pas vaut 1 et les entiers sont
 *  exacts. */
function colonnesBin({ nanTout = [], nanV = [] } = {}) {
  const buf = new ArrayBuffer(NBCOL * OCT_PAR_COL);
  const vue = new DataView(buf);
  let o = 0;
  for (let c = 0; c < NBCOL; c++) {
    for (const signe of [1, -1]) {
      for (let n = 0; n < NBNIV; n++) {
        for (let k = 0; k < ECH_MIN.length; k++) {
          // `nanTout` : l'échéance est vide À TOUS LES NIVEAUX → aucune
          // colonne ne doit s'ouvrir. `nanV` : seul `v` manque → u ET v
          // ensemble, donc on ne remplace RIEN.
          const vide = nanTout.includes(k) || (signe < 0 && nanV.includes(k));
          const val = vide ? NaN : signe * (400 + 100 * c + 10 * n + k);
          vue.setUint16(o, enc16(val), true);
          o += 2;
        }
      }
    }
  }
  return buf;
}

/** La colonne du produit B : 9 échéances horaires, `u`/`v` hauteur plus
 *  une tranche `t` — celle qui doit rester VIDE aux instants neufs. */
function colonneB() {
  const nB = 9;
  const platSurf = (base) => {
    const a = new Float32Array(nB);
    for (let e = 0; e < nB; e++) a[e] = base + e;
    return a;
  };
  const plat = (base, signe = 1) => {
    const a = new Float32Array(NBNIV * nB);
    for (let n = 0; n < NBNIV; n++) {
      for (let e = 0; e < nB; e++) a[n * nB + e] = signe * (base + 10 * n + e);
    }
    return a;
  };
  return {
    echeances: [0, 1, 2, 3, 4, 5, 6, 7, 8],
    // ⚠️ `v` est l'OPPOSÉ de `u`, pas « u avec une base négative ». La
    // première version écrivait `plat(-100)`, soit −100 + 10n + e — donc
    // −94 là où le contrôle attendait −106. Un contrôle faux ne dit rien
    // du code qu'il prétend mesurer.
    // `pression_mer` est dans la LISTE BLANCHE, `t` et `tke` n'y sont
    // pas : c'est le couple qui rend la section 13 discriminante.
    tranches: { u: plat(100), v: plat(100, -1), t: plat(200),
                pression_mer: platSurf(1000), tke: platSurf(5) },
  };
}

/** Un serveur pour `colonnes.bin` seul — le reste n'est pas sollicité. */
function serveurColonnes(octets) {
  return async (url, init) => {
    const m = /bytes=(\d+)-(\d+)/.exec(init?.headers?.Range || '');
    if (!m) return { ok: true, status: 200, arrayBuffer: async () => octets };
    const a = Number(m[1]), b = Number(m[2]);
    return {
      ok: true, status: 206,
      headers: { get: () => `bytes ${a}-${b}/${octets.byteLength}` },
      arrayBuffer: async () => octets.slice(a, b + 1),
    };
  };
}

// ══════════════════════════════════════════════════════════════════════
await section('1. La découverte passe par le manifeste du produit B', () => {
  const sans = R.pointeurDe(manB({ provenance: undefined }));
  verifier('manifeste sans provenance → raison nommée',
    sans.raison === 'manifeste-sans-provenance', sans.raison);
  verifier('…et AUCUNE clé n’est inventée pour compenser',
    !('cle_index' in sans) && /prochaine ingestion/.test(sans.texte));

  const pyr = R.pointeurDe(manB({
    domaine: 'pyrenees',
    provenance: {
      granularite: 'echeance x bloc', blocs: ['hauteur'], par_echeance: [],
      arome_pi: {
        disponible: false, domaines_couverts: ['nord-alpes'],
        pourquoi: POURQUOI, rafraichissement: null,
      },
    },
  }));
  verifier('domaine sans PI → raison « domaine-sans-pi »',
    pyr.raison === 'domaine-sans-pi');
  // ⛔ VERBATIM. `pourquoi` est écrit côté serveur POUR être affiché tel
  // quel (arbitrage A9) ; le reformuler ferait deux vérités.
  verifier('…et le texte du producteur est repris MOT POUR MOT',
    pyr.texte === POURQUOI);

  const ok = R.pointeurDe(manB());
  verifier('manifeste complet → le pointeur, pas une raison',
    !('raison' in ok) && ok.cle_index === 'agrume/pi/rafraichissement/index.json');
});

// ══════════════════════════════════════════════════════════════════════
await section('2. Les axes se vérifient (une colonne = 1,95 km)', () => {
  let leve = false;
  try { R.verifierAxes(manB(), manRaf()); } catch { leve = true; }
  verifier('cas nominal : rien ne lève', !leve);

  const cas = [
    ['une colonne de trop', { axes: { ...manRaf().axes, nb_lon: NBLON + 1 } }],
    ['fenêtre décalée', { axes: { ...manRaf().axes, lon_premier: 5.025 } }],
    ['niveaux différents', { niveaux_m_sol: [10, 30] }],
  ];
  for (const [nom, extra] of cas) {
    let msg = null;
    try { R.verifierAxes(manB(), manRaf(extra)); } catch (e) { msg = e.message; }
    verifier(`${nom} → refus`, !!msg && /ne décrit PAS la même grille/.test(msg));
  }
  // ⚠️ Un refus pour une raison FAUSSE coûte autant qu'une acceptation
  // fausse : les bornes sont publiées arrondies des deux côtés.
  let leveArrondi = false;
  try {
    R.verifierAxes(manB(), manRaf({ axes: { ...manRaf().axes, lat_premier: 46.45001 } }));
  } catch { leveArrondi = true; }
  verifier('un arrondi de sérialisation (1e-5) ne fait PAS refuser', !leveArrondi);
});

// ══════════════════════════════════════════════════════════════════════
await section('3. ⛔ LE BRANCHEMENT — par la chaîne entière, pas la fonction', async () => {
  // ⛔ C'est la leçon du Lot L2 : un banc peut prouver l'EXISTENCE d'un
  // garde-fou sans prouver son APPEL. Ces contrôles-ci passent tous par
  // `chargerRafraichissement`, donc par le pipeline réel.
  const nominal = serveur({ index: INDEX, man: manRaf() });
  const r1 = await R.chargerRafraichissement('https://x', manB(), nominal.fetchFn);
  verifier('nominal → un rafraîchissement, avec son jeton',
    !('raison' in r1) && r1.man.run_pi === RUN_PI && !!r1.jeton);
  verifier('…et l’index a bien été lu AVANT le manifeste',
    nominal.vus[0].cle.endsWith('index.json')
    && nominal.vus[1].cle.endsWith('manifest.json'));

  const axes = serveur({
    index: INDEX, man: manRaf({ axes: { ...manRaf().axes, nb_lon: NBLON + 1 } }),
  });
  const r2 = await R.chargerRafraichissement('https://x', manB(), axes.fetchFn);
  verifier('axes différents → refus REMONTÉ par la chaîne',
    r2.raison === 'axes-differents');

  const autre = serveur({ index: INDEX, man: manRaf({ run_produit_b: '2026-08-17T00:00:00Z' }) });
  const r3 = await R.chargerRafraichissement('https://x', manB(), autre.fetchFn);
  verifier('composé sur un AUTRE run AROME → on n’applique pas',
    r3.raison === 'autre-run-produit-b');

  const vide = serveur({ index: { dernier: {} }, man: manRaf() });
  const r4 = await R.chargerRafraichissement('https://x', manB(), vide.fetchFn);
  verifier('index sans `dernier[domaine]` → « aucun-run-pi »',
    r4.raison === 'aucun-run-pi');

  const menteur = serveur({ index: INDEX, man: manRaf({ run_pi: '2026-08-17T08:00:00Z' }) });
  const r5 = await R.chargerRafraichissement('https://x', manB(), menteur.fetchFn);
  verifier('manifeste d’un AUTRE run que celui de l’index → refus',
    r5.raison === 'aucun-run-pi');
});

// ══════════════════════════════════════════════════════════════════════
await section('4. ⛔ L’échéance se cherche en INSTANTS, jamais par indice', () => {
  const m = manRaf();
  verifier('+6 h (décalage 360 min) → bloc 0', R.indexEcheance(m, RUN_B, 6) === 0);
  verifier('+7 h → bloc 4 (60 min après le run PI)', R.indexEcheance(m, RUN_B, 7) === 4);
  verifier('+8 h → hors horizon (120 min > 90) → null',
    R.indexEcheance(m, RUN_B, 8) === null);
  verifier('+5 h → AVANT le run PI → null', R.indexEcheance(m, RUN_B, 5) === null);

  // ⛔⛔ LE SABOTAGE QUE CE PROJET A DÉJÀ PAYÉ CE MATIN, côté serveur :
  // « les échéances 0→7 » du cahier des charges, vrai une fois sur huit.
  // La version naïve `echeances_min[echeanceH]` rendrait ici le bloc 6
  // (90 min) pour +6 h — six blocs plus loin, même forme, aucune erreur.
  const naif = 6;
  verifier('la version naïve (indice = échéance) désignerait un AUTRE bloc',
    R.indexEcheance(m, RUN_B, 6) !== naif);

  let msg = null;
  try { R.indexEcheance(manRaf({ decalage_min: 120 }), RUN_B, 6); }
  catch (e) { msg = e.message; }
  verifier('manifeste qui se contredit (decalage_min ≠ écart des runs) → lève',
    !!msg && /se contredit/.test(msg));

  let msg2 = null;
  try { R.indexEcheance(m, 'pas-une-date', 6); } catch (e) { msg2 = e.message; }
  verifier('run illisible → lève au lieu de deviner un instant', !!msg2);
});

// ══════════════════════════════════════════════════════════════════════
await section('5. ⛔ Les offsets sont RELATIFS au bloc d’échéance', async () => {
  const s = serveur({ index: INDEX, man: manRaf() });
  const etat = await R.chargerRafraichissement('https://x', manB(), s.fetchFn);
  const k = 4;                                     // +7 h → 60 min
  const bloc = await R.chargerBloc('https://x', etat.man, k, etat.jeton, s.fetchFn);

  const range = s.vus[s.vus.length - 1].range;
  verifier('le Range demandé part de k × octets_par_echeance',
    range === `bytes=${k * OCTETS_ECH}-${(k + 1) * OCTETS_ECH - 1}`, range);

  // u = 1000·(k+1) + 10·niveau + colonne
  verifier('u décodé = la valeur du BON bloc (niveau 0, colonne 0)',
    bloc.u[0] === 1000 * (k + 1));
  verifier('…et au niveau 1, colonne 2', bloc.u[NBCOL + 2] === 1000 * (k + 1) + 12);
  verifier('v est bien v, et pas u (signe opposé)',
    bloc.v[0] === -1000 * (k + 1));
  // ⛔ LA CONTRE-ÉPREUVE : des offsets lus comme ABSOLUS auraient décodé
  // le bloc 0. Le tableau aurait la bonne longueur, des valeurs finies,
  // et une carte plausible d'une heure et quart trop tôt.
  verifier('des offsets lus comme absolus auraient rendu autre chose',
    bloc.u[0] !== 1000 * 1);
  verifier('le NaN publié survit au décodage (« rien à en dire »)',
    Number.isNaN(bloc.u[CASE_NAN]));
});

// ══════════════════════════════════════════════════════════════════════
await section('6. La préséance : u ET v ensemble, ou aucun des deux', () => {
  const f = (...v) => Float32Array.from(v);
  const uB = f(1, 2, 3, 4), vB = f(-1, -2, -3, -4);
  const uR = f(10, NaN, 30, 40), vR = f(-10, -20, NaN, -40);
  const p = R.appliquerPreseance(uB, vB, uR, vR);
  verifier('valeur finie des deux côtés → PI gagne', p.u[0] === 10 && p.v[0] === -10);
  verifier('u non fini → on garde le produit B, u ET v',
    p.u[1] === 2 && p.v[1] === -2);
  // ⛔ Prendre u de PI et v du produit B donnerait une vitesse plausible
  // et une DIRECTION fausse — le pire des deux mondes.
  verifier('v non fini → on garde le produit B, u ET v',
    p.u[2] === 3 && p.v[2] === -3);
  verifier('le compte des mailles remplacées est juste',
    p.remplacees === 2 && p.total === 4);
  verifier('les tableaux d’entrée ne sont PAS modifiés',
    uB[0] === 1 && vB[0] === -1);

  let msg = null;
  try { R.appliquerPreseance(uB, vB, f(1, 2, 3), f(1, 2, 3)); }
  catch (e) { msg = e.message; }
  verifier('tailles différentes → lève (un décalage d’une case suffit)',
    !!msg && /ne se superposent pas/.test(msg));
});

// ══════════════════════════════════════════════════════════════════════
await section('7. Ce que l’écran a le droit de dire, échéance par échéance', () => {
  const m = manRaf();
  const p0 = R.provenanceEcheance(m, 0);
  verifier('bloc 0 : arome+pi à poids 1', p0.modele === 'arome+pi' && p0.poids_pi === 1);
  const p6 = R.provenanceEcheance(m, 6);
  verifier('dernier bloc : arome SEUL, poids 0', p6.modele === 'arome' && p6.poids_pi === 0);

  let msg = null;
  try {
    R.provenanceEcheance(manRaf({
      provenance: { ...m.provenance, par_echeance: m.provenance.par_echeance.slice(1) },
    }), 0);
  } catch (e) { msg = e.message; }
  verifier('provenance décalée d’un cran → lève au lieu de décrire la voisine',
    !!msg && /provenance de l’échéance/.test(msg));

  const MAINTENANT = Date.parse('2026-08-17T10:44:00Z');
  const phrase1 = R.phraseNourriPar({
    source: 'rafraichissement', prov: p0, runPi: RUN_PI, runB: RUN_B,
    partMailles: 1, octets: OCTETS_ECH,
  }, MAINTENANT);
  verifier('poids 1 → la phrase nomme les DEUX modèles et leurs runs',
    /AROME 03 Z/.test(phrase1) && /AROME-PI 09 Z/.test(phrase1), phrase1);
  verifier('…et l’âge est CALCULÉ à l’écran (jamais publié)',
    /il y a 1 h 44/.test(phrase1));

  // ⛔ LE CONTRÔLE LE PLUS IMPORTANT DU BANC. À poids 0 il n'y a plus une
  // trace de PI, à AUCUN niveau, 20 m compris. Une phrase qui dirait « PI »
  // ici serait fausse — et personne à l'écran ne pourrait le savoir.
  const phrase0 = R.phraseNourriPar({
    source: 'rafraichissement', prov: p6, runPi: RUN_PI, runB: RUN_B,
    partMailles: 1, octets: OCTETS_ECH,
  }, MAINTENANT);
  verifier('poids 0 → la phrase ne dit JAMAIS « PI »', !/PI 09 Z|AROME-PI/.test(phrase0), phrase0);
  verifier('…et elle dit « AROME seul », avec son régime',
    /seul/.test(phrase0) && /horizon/.test(phrase0));

  const phraseB = R.phraseNourriPar({
    source: 'produit-b', runB: RUN_B, raison: 'domaine-sans-pi', texte: POURQUOI,
  }, MAINTENANT);
  verifier('domaine sans PI → l’absence est une PHRASE, pas un blanc',
    phraseB.includes(POURQUOI) && /AROME 03 Z seul/.test(phraseB));

  const partielle = R.phraseNourriPar({
    source: 'rafraichissement', prov: p0, runPi: RUN_PI, runB: RUN_B,
    partMailles: 0.8, octets: OCTETS_ECH,
  }, MAINTENANT);
  verifier('20 % de mailles non servies par PI → c’est DIT',
    /20 % des mailles retombent/.test(partielle), partielle);
});

// ══════════════════════════════════════════════════════════════════════
await section('8. ⛔ L’âge n’est publié nulle part — il périme à la lecture', () => {
  const plat = JSON.stringify(manRaf());
  // ⚠️ On cherche une CLÉ d'âge, pas la suite de lettres « age » : la
  // première version de ce contrôle est partie au rouge sur
  // `decalage_min`, ce qui est exactement le genre de faux positif qui
  // apprend à ignorer un banc.
  verifier('aucun champ d’âge dans le manifeste',
    !/"(age|age_min|age_minutes|anciennete|fraicheur)[a-z_]*"\s*:/i.test(plat));
  verifier('ageMinutes rend null sur un horodatage illisible',
    R.ageMinutes('jamais') === null);
  verifier('ageTexte : 0 min, 59 min, 60 min, 104 min',
    R.ageTexte(0) === 'il y a 0 min' && R.ageTexte(59) === 'il y a 59 min'
    && R.ageTexte(60) === 'il y a 1 h' && R.ageTexte(104) === 'il y a 1 h 44');
});

// ══════════════════════════════════════════════════════════════════════
//  Lot L3b — LA COLONNE, ET LES 18 QUARTS D'HEURE
// ══════════════════════════════════════════════════════════════════════
await section('10. ⛔ Le PAS de la colonne n’est PAS celui du produit B', async () => {
  const man = manRaf();
  man.service.colonnes = colonnesRaf();
  // Sur la fixture : 3 × 4 colonnes, pas de 28 o. La colonne (j=1, i=2)
  // commence donc à (1×4 + 2) × 28 = 168.
  const pos = R.colonneDuRafraichissement(man, 46.425, 5.05);
  verifier('⛔ l’offset se calcule avec le pas DU RAFRAÎCHISSEMENT — le '
    + 'couple (j, i) est le même que dans le produit B, le PAS ne l’est pas',
    pos.j === 1 && pos.i === 2 && pos.offset === 6 * OCT_PAR_COL,
    `j=${pos.j} i=${pos.i} offset=${pos.offset} (attendu ${6 * OCT_PAR_COL})`);
  verifier('…et le pas de latitude NÉGATIF est dérivé des bornes, pas supposé',
    Math.abs(pos.lat - 46.425) < 1e-9, String(pos.lat));

  const oct = colonnesBin();
  const col = await R.chargerColonneRafraichissement(
    'http://x', man, 46.425, 5.05, 'jeton', serveurColonnes(oct));
  verifier('un SEUL Range suffit à toute la colonne (u, v, 2 niveaux, 7 échéances)',
    col.octets === OCT_PAR_COL, `${col.octets} o`);
  // u = 400 + 100·colonne + 10·niveau + k, colonne 6, niveau 1, k = 3
  verifier('⛔ les octets décodés sont ceux de CETTE colonne-là, pas d’une voisine',
    col.u[1 * ECH_MIN.length + 3] === 400 + 600 + 10 + 3
    && col.v[1 * ECH_MIN.length + 3] === -(400 + 600 + 10 + 3),
    `u=${col.u[1 * ECH_MIN.length + 3]}`);
});

await section('11. ⛔⛔ La densification : 18 quarts d’heure, et RIEN d’interpolé', async () => {
  const man = manRaf();
  man.service.colonnes = colonnesRaf();
  const colR = await R.chargerColonneRafraichissement(
    'http://x', man, 46.45, 5, 'jeton', serveurColonnes(colonnesBin()));
  const b = colonneB();
  const d = R.densifierColonne(manB(), b, man, colR);

  // Décalage 360 min : les instants PI tombent à 360, 375, 390, 405, 420,
  // 435, 450 min — soit 6 h, 6.25, 6.5, 6.75, 7 h, 7.25, 7.5. Deux
  // coïncident avec une heure ronde du produit B (6 h et 7 h), CINQ sont
  // neufs. 9 + 5 = 14.
  verifier('⛔ l’axe est densifié en INSTANTS : 9 heures + 5 quarts d’heure',
    d.echeances.length === 14 && d.ajoutees === 5,
    `${d.echeances.length} instants, ${d.ajoutees} neufs`);
  verifier('…et les échéances neuves sont FRACTIONNAIRES, à leur place',
    JSON.stringify(d.echeances)
      === JSON.stringify([0, 1, 2, 3, 4, 5, 6, 6.25, 6.5, 6.75, 7, 7.25, 7.5, 8]),
    JSON.stringify(d.echeances));
  const p625 = d.echeances.indexOf(6.25);
  const p6 = d.echeances.indexOf(6);
  const p8 = d.echeances.indexOf(8);

  // ⛔ LE CONTRÔLE QUI COMPTE : rien n'est inventé aux instants neufs.
  const n2 = d.echeances.length;
  verifier('⛔⛔ à un instant NEUF, la tranche `t` du produit B est NaN — '
    + 'RIEN n’a été interpolé pour remplir la colonne',
    Number.isNaN(d.tranches.t[0 * n2 + p625])
    && Number.isNaN(d.tranches.t[1 * n2 + p625]));
  verifier('…alors qu’elle est bien PRÉSERVÉE aux heures du produit B',
    d.tranches.t[0 * n2 + p6] === 206 && d.tranches.t[1 * n2 + p8] === 218,
    `${d.tranches.t[0 * n2 + p6]} / ${d.tranches.t[1 * n2 + p8]}`);
  verifier('⛔ à un instant NEUF, u/v viennent de PI et de personne d’autre',
    d.tranches.u[0 * n2 + p625] === 401 && d.tranches.v[0 * n2 + p625] === -401,
    `u=${d.tranches.u[0 * n2 + p625]}`);
  verifier('⛔ à une heure COUVERTE par PI, la préséance a écrasé le produit B',
    d.tranches.u[0 * n2 + p6] === 400 && d.tranches.u[0 * n2 + p6] !== 106,
    `u=${d.tranches.u[0 * n2 + p6]} (produit B : 106)`);
  verifier('⚠️ …et à une heure HORS de la fenêtre PI, le produit B reste maître',
    d.tranches.u[0 * n2 + p8] === 108, `u=${d.tranches.u[0 * n2 + p8]}`);
  verifier('la provenance est posée sur les instants COUVERTS, et nulle part ailleurs',
    d.provenance[p6]?.modele === 'arome+pi' && d.provenance[p625]?.modele === 'arome+pi'
    && d.provenance[p8] === null);
  verifier('`ajoutee` distingue le quart d’heure neuf de l’heure du produit B',
    d.ajoutee[p625] === true && d.ajoutee[p6] === false && d.ajoutee[p8] === false);
});

await section('12. ⛔ Ce que la densification REFUSE de faire', async () => {
  const man = manRaf();
  man.service.colonnes = colonnesRaf();
  const b = colonneB();

  // a) Une échéance PI vide à tous les niveaux n'ouvre PAS de colonne.
  const vide = await R.chargerColonneRafraichissement(
    'http://x', man, 46.45, 5, 'j', serveurColonnes(colonnesBin({ nanTout: [1] })));
  const dv = R.densifierColonne(manB(), b, man, vide);
  verifier('⛔ un quart d’heure sans AUCUN couple (u, v) fini n’ouvre pas de '
    + 'colonne — une grille vide se lit comme un modèle qui a échoué',
    dv.ajoutees === 4 && dv.echeances.indexOf(6.25) === -1,
    `${dv.ajoutees} neufs, 6.25 ${dv.echeances.includes(6.25) ? 'présent' : 'absent'}`);

  // b) `u` seul ne remplace RIEN.
  const sansV = await R.chargerColonneRafraichissement(
    'http://x', man, 46.45, 5, 'j', serveurColonnes(colonnesBin({ nanV: [0] })));
  const ds = R.densifierColonne(manB(), b, man, sansV);
  const n2 = ds.echeances.length;
  const q6 = ds.echeances.indexOf(6);
  verifier('⛔⛔ `v` absent à l’échéance 6 h → `u` de PI n’est PAS pris : le '
    + 'produit B reste maître. Une vitesse plausible et une direction '
    + 'fausse est le pire des deux mondes',
    ds.tranches.u[0 * n2 + q6] === 106 && ds.tranches.v[0 * n2 + q6] === -106,
    `u=${ds.tranches.u[0 * n2 + q6]}`);

  // c) Un décalage qui contredit le manifeste fait REFUSER, pas deviner.
  const menteur = manRaf({ decalage_min: 120 });
  menteur.service.colonnes = colonnesRaf();
  let leve = false, msg = '';
  try {
    R.densifierColonne(manB(), b, menteur, vide);
  } catch (e) { leve = true; msg = String(e.message); }
  verifier('⛔ un `decalage_min` contredit par les deux horodatages fait '
    + 'REFUSER — un décalage faux place les colonnes neuves à côté de leur '
    + 'instant, et la coupe reste parfaitement lisse',
    leve && /se contredit/.test(msg), msg.slice(0, 90));

  // d) Un instant PI hors des bornes du produit B n'allonge pas l'horizon.
  const court = { echeances: [6, 7], tranches: {
    u: new Float32Array([1, 2, 11, 12]), v: new Float32Array([-1, -2, -11, -12]),
  } };
  const manCourt = manB({ echeances: [6, 7] });
  const dc = R.densifierColonne(manCourt, court, man,
    await R.chargerColonneRafraichissement(
      'http://x', man, 46.45, 5, 'j', serveurColonnes(colonnesBin())));
  verifier('⛔ un instant PI au-delà de la dernière échéance du produit B '
    + 'n’ouvre pas de colonne : l’horizon ne grandit pas parce que le vent, '
    + 'lui, est connu plus loin',
    Math.max(...dc.echeances) === 7 && dc.echeances.length === 5,
    JSON.stringify(dc.echeances));
});

await section('13. ⛔ L’interpolation : LISTE BLANCHE, et rien d’autre', async () => {
  const man = manRaf();
  man.service.colonnes = colonnesRaf();
  const colR = await R.chargerColonneRafraichissement(
    'http://x', man, 46.45, 5, 'j', serveurColonnes(colonnesBin()));
  const d = R.densifierColonne(manB(), colonneB(), man, colR);
  const n2 = d.echeances.length;
  const p625 = d.echeances.indexOf(6.25);
  const p65 = d.echeances.indexOf(6.5);

  // `pression_mer` vaut 1000 + heure : 1006 à 6 h, 1007 à 7 h.
  verifier('⛔ `pression_mer` est interpolée LINÉAIREMENT entre les deux '
    + 'heures qui l’encadrent — 1006 et 1007 donnent 1006,25 à 6 h 15',
    Math.abs(d.tranches.pression_mer[p625] - 1006.25) < 1e-4
    && Math.abs(d.tranches.pression_mer[p65] - 1006.5) < 1e-4,
    `${d.tranches.pression_mer[p625]} / ${d.tranches.pression_mer[p65]}`);
  verifier('⛔⛔ …alors que `tke` reste VIDE : elle saute de ×5 en une '
    + 'heure, et c’est la ligne que le pilote lit pour le rotor',
    Number.isNaN(d.tranches.tke[p625]) && Number.isNaN(d.tranches.tke[p65]));
  verifier('⛔ …et `t` aussi : elle n’est pas dans la liste blanche, donc '
    + 'elle n’y entre pas « parce qu’on pourrait »',
    Number.isNaN(d.tranches.t[0 * n2 + p625]));
  verifier('`interpolees` NOMME ce qui a été touché, et rien de plus — '
    + 'sans quoi l’écran ne saurait pas quoi distinguer',
    d.interpolees.includes('pression_mer')
    && !d.interpolees.includes('tke') && !d.interpolees.includes('t'),
    JSON.stringify(d.interpolees));
  // ── ⛔ ON N'EXTRAPOLE PAS AU BORD ────────────────────────────────
  // ⚠️ Ce contrôle a été AJOUTÉ APRÈS COUP : le sabotage « extrapoler au
  // lieu de refuser » passait au vert, parce qu'aucune fixture n'avait de
  // trou au bord. Or le produit B EN A (`cc`, `tke`, la pluie et la
  // rafale sont NaN à τ = 0). Un banc qui ne peut pas rencontrer le cas
  // ne le protège pas.
  const trou = colonneB();
  // NaN à la SEULE dernière heure : 6h15 reste encadré (6 h et 7 h),
  // 7h15 et 7h30 ne le sont plus à droite.
  trou.tranches.pression_mer[8] = NaN;
  const dt = R.densifierColonne(manB(), trou, man, colR);
  const q7 = dt.echeances.indexOf(7.25);
  const q6 = dt.echeances.indexOf(6.25);
  verifier('⛔⛔ sans encadrant À DROITE, on ne sert RIEN — prolonger la '
    + 'dernière valeur connue serait une tendance que personne n’a mesurée',
    Number.isNaN(dt.tranches.pression_mer[q7]),
    String(dt.tranches.pression_mer[q7]));
  verifier('…alors qu’un instant CORRECTEMENT encadré, lui, est bien servi',
    Math.abs(dt.tranches.pression_mer[q6] - 1006.25) < 1e-4,
    String(dt.tranches.pression_mer[q6]));

  verifier('⛔ chaque entrée de la liste blanche porte SA RAISON, en clair',
    Object.values(R.TRANCHES_INTERPOLABLES).every(v => typeof v === 'string'
      && v.length > 30), JSON.stringify(Object.keys(R.TRANCHES_INTERPOLABLES)));
});

// ══════════════════════════════════════════════════════════════════════
//  9. LES OCTETS SERVIS — la seule vérification qui prouve quelque chose
// ══════════════════════════════════════════════════════════════════════
if (PROD) {
  await section('9. En production, sur les octets SERVIS', async () => {
    const L = await import(join(ici, '..', '..', 'web', 'src', 'lib', 'altitudeLayer.ts'));
    const idxB = await L.lireJson(`${BASE}/agrume/grille/index.json`);
    const domaine = 'nord-alpes';
    const runB = L.dernierRun(idxB, domaine);
    const man = await L.lireJson(L.avecJeton(
      `${BASE}/agrume/grille/${domaine}/${runB}/manifest.json`, idxB.ecrit_le));
    verifier(`produit B en ligne : ${runB}`, !!runB);

    // ⚠️ ICI, ET SEULEMENT ICI, le banc a le droit de connaître une clé :
    // il vérifie la chaîne, il ne la parcourt pas à la place du client.
    // Tant que le manifeste du produit B en ligne date d'avant le Lot L1,
    // le pointeur est INJECTÉ — et c'est dit en toutes lettres, parce
    // qu'un banc qui compense un manque en silence est un banc qui ment.
    let manB2 = man;
    if (!man.provenance?.arome_pi?.rafraichissement) {
      console.log('  ⓘ le manifeste du produit B en ligne ne publie pas encore '
        + 'sa provenance (run ingéré avant le Lot L1) : le pointeur est '
        + 'INJECTÉ pour vérifier la suite de la chaîne.');
      manB2 = {
        ...man,
        provenance: {
          granularite: 'echeance x bloc', blocs: ['hauteur'], par_echeance: [],
          arome_pi: {
            disponible: true, domaines_couverts: [domaine], pourquoi: null,
            rafraichissement: {
              gabarit_cle: 'agrume/pi/rafraichissement/{domaine}/{run_pi}/{objet}',
              cle_index: 'agrume/pi/rafraichissement/index.json',
              blocs_concernes: ['hauteur'], parametres_concernes: ['u', 'v'],
              horizon_min: 360, echeances_min: [], preseance: '(injecté)',
            },
          },
        },
      };
    }

    const etat = await R.chargerRafraichissement(BASE, manB2);
    if ('raison' in etat) {
      // ⚠️ Ce n'est PAS forcément un échec : « composé sur un autre run
      // AROME » est un état normal du produit pendant l'heure qui suit
      // une ingestion. On le DIT, et on s'arrête là.
      console.log(`  ⓘ pas de rafraîchissement applicable : ${etat.raison} — `
        + `${etat.texte.slice(0, 160)}`);
      verifier('la raison est nommée, pas muette', !!etat.raison && !!etat.texte);
      return;
    }
    verifier(`rafraîchissement en ligne : ${etat.man.run_pi} sur AROME `
      + `${etat.man.run_produit_b} (décalage ${etat.man.decalage_min} min)`, true);

    const hDebut = etat.man.decalage_min / 60;
    const hFin = (etat.man.decalage_min + etat.man.horizon_min) / 60;
    verifier('l’échéance +' + hDebut + ' h tombe sur le bloc 0',
      R.indexEcheance(etat.man, man.run, hDebut) === 0);

    const lire = async (h) => {
      const { buf, offsetBase } = await L.chargerTranches(BASE, man, h, ['u', 'v']);
      const tr = man.service.tranches;
      return {
        u: L.decoderTranche(buf, tr.u, offsetBase),
        v: L.decoderTranche(buf, tr.v, offsetBase),
      };
    };
    const stats = (a, b) => {
      const d = [];
      for (let c = 0; c < a.length; c++) {
        if (Number.isFinite(a[c]) && Number.isFinite(b[c])) d.push(Math.abs(a[c] - b[c]));
      }
      d.sort((x, y) => x - y);
      return { n: d.length, med: d[Math.floor(d.length / 2)] ?? NaN, max: d[d.length - 1] ?? NaN };
    };

    // ── a. À l'horizon (poids_pi = 0), le composite EST l'AROME du nœud
    // ⛔ C'est l'invariant le plus fort disponible sans refaire le calcul :
    // à `w_PI = 0` la rampe a éteint Δ, et l'instant tombe PILE sur une
    // échéance horaire du produit B. Les deux doivent donc coïncider à
    // l'arrondi de publication près. S'ils diffèrent, c'est que l'adresse
    // est fausse — offsets, bloc, ou échéance.
    const kFin = etat.man.echeances_min.length - 1;
    const provFin = R.provenanceEcheance(etat.man, kFin);
    const blocFin = await R.chargerBloc(BASE, etat.man, kFin, etat.jeton);
    const bFin = await lire(hFin);
    const sFin = stats(blocFin.u, bFin.u);
    verifier(`à +${hFin} h (poids_pi = ${provFin.poids_pi}) le composite EST `
      + `l’AROME du nœud`, sFin.max <= 0.01,
      `n = ${sFin.n}, médiane ${sFin.med.toFixed(4)}, max ${sFin.max.toFixed(4)} m/s`);
    verifier('…et la provenance le dit : modèle « arome », sans PI',
      provFin.modele === 'arome' && provFin.poids_pi === 0);

    // ── b. À l'échéance 0 (poids_pi = 1), PI a VRAIMENT corrigé
    // ⚠️ Sans ce contrôle, une préséance qui n'écraserait rien du tout
    // passerait tous les autres : le calque serait identique au produit B
    // et le panneau afficherait quand même « nourri par PI ».
    const bloc0 = await R.chargerBloc(BASE, etat.man, 0, etat.jeton);
    const b0 = await lire(hDebut);
    const s0 = stats(bloc0.u, b0.u);
    verifier('à l’échéance 0, PI a réellement corrigé le produit B',
      s0.max > 0.05,
      `n = ${s0.n}, médiane ${s0.med.toFixed(3)}, max ${s0.max.toFixed(3)} m/s`);

    const p = R.appliquerPreseance(b0.u, b0.v, bloc0.u, bloc0.v);
    verifier('la préséance remplace les mailles annoncées par `remplissage`',
      Math.abs(p.remplacees / p.total - Math.min(etat.man.remplissage.u,
        etat.man.remplissage.v)) < 0.001,
      `${(100 * p.remplacees / p.total).toFixed(2)} % remplacées`);
    verifier('le bloc lu pèse bien un bloc d’échéance',
      bloc0.octets === etat.man.service.carte.octets_par_echeance,
      `${(bloc0.octets / 1024).toFixed(0)} Ko`);
    console.log(`  ⓘ phrase servie : ${R.phraseNourriPar({
      source: 'rafraichissement', prov: R.provenanceEcheance(etat.man, 0),
      runPi: etat.man.run_pi, runB: man.run,
      partMailles: p.remplacees / p.total, octets: bloc0.octets })}`);

    // ── c. ⛔⛔ LES DEUX JUMEAUX DISENT-ILS LE MÊME VENT ? (Lot L3b)
    //
    // `carte.bin` nourrit le calque, `colonnes.bin` la coupe. Ils sont
    // écrits ENSEMBLE ou pas du tout, mais rien ne garantissait jusqu'ici
    // qu'ils portent les mêmes valeurs UNE FOIS SERVIS : le serveur le
    // vérifie sur ses tableaux en mémoire, pas sur les octets sortis de
    // R2 par deux dispositions différentes ((échéance, tranche, niveau,
    // lat, lon) d'un côté, (colonne, tranche, niveau, échéance) de
    // l'autre). ⚠️ S'ils divergent, le MÊME vent au MÊME instant a deux
    // valeurs selon l'écran regardé — et personne ne compare jamais les
    // deux écrans côte à côte.
    const a = etat.man.axes;
    // Un point franchement à l'intérieur, pas un bord : les deux
    // arrondis d'indice (lat décroissante, lon croissante) doivent
    // tomber sur la MÊME colonne, et un bord masquerait un décalage
    // en le saturant.
    const latMi = (a.lat_premier + a.lat_dernier) / 2;
    const lonMi = (a.lon_premier + a.lon_dernier) / 2;
    const pos = R.colonneDuRafraichissement(etat.man, latMi, lonMi);
    const colR = await R.chargerColonneRafraichissement(
      BASE, etat.man, latMi, lonMi, etat.jeton);
    verifier('la colonne du rafraîchissement tient dans UN Range',
      colR.octets === etat.man.service.colonnes.octets_par_colonne,
      `${colR.octets} o (contre ${(bloc0.octets / 1024).toFixed(0)} Ko pour `
      + `UNE échéance de carte.bin)`);

    const nEch = etat.man.echeances_min.length;
    const nNiv = etat.man.niveaux_m_sol.length;
    const iCol = pos.j * a.nb_lon + pos.i;
    let pire = 0, comptees = 0, dep = 0;
    for (let k = 0; k < nEch; k++) {
      const blocK = k === 0 ? bloc0
        : (k === kFin ? blocFin : await R.chargerBloc(BASE, etat.man, k, etat.jeton));
      for (let L = 0; L < nNiv; L++) {
        const carte = blocK.u[L * a.nb_lat * a.nb_lon + iCol];
        const colonne = colR.u[L * nEch + k];
        const fCarte = Number.isFinite(carte), fCol = Number.isFinite(colonne);
        // ⛔ Une case finie d'un côté et non finie de l'autre est une
        // divergence à part entière : le calque dessinerait une flèche
        // là où la coupe ne montrerait rien.
        if (fCarte !== fCol) { dep++; continue; }
        if (!fCarte) continue;
        comptees++;
        pire = Math.max(pire, Math.abs(carte - colonne));
      }
    }
    verifier('⛔⛔ `carte.bin` et `colonnes.bin` disent le MÊME vent à la '
      + 'même colonne, au même niveau, à la même échéance — deux '
      + 'dispositions, une seule vérité',
      dep === 0 && pire === 0,
      `n = ${comptees}, écart max ${pire.toExponential(3)} m/s, `
      + `${dep} case(s) dépareillée(s)`);
  });
}

// ══════════════════════════════════════════════════════════════════════
console.log(`\n${echecs ? '✗' : '✓'} ${echecs} contrôle(s) au rouge`
  + `${echecs ? ` : ${rouges.join(' · ')}` : ''}`);
process.exit(echecs ? 1 : 0);
