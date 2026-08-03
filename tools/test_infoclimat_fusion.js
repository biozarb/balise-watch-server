#!/usr/bin/env node
/**
 * test_infoclimat_fusion.js — éprouver la fusion du cache d'observations
 * Infoclimat SUR LE VRAI SOURCE, pas sur une copie (03/08/2026).
 *
 * ┌─ POURQUOI CE HARNAIS ─────────────────────────────────────────────┐
 * │ Le serveur n'a pas de tests, et `index.js` appelle `app.listen`    │
 * │ dès l'import : impossible de le `require` pour vérifier une        │
 * │ fonction. Récrire la logique dans le test aurait testé ma copie,   │
 * │ pas le code qui tourne — le pire des faux positifs.                │
 * │                                                                    │
 * │ Ce harnais DÉCOUPE le bloc Infoclimat d'`index.js` (des constantes │
 * │ à `refreshInfoclimatData`) et l'évalue avec un `fetch` bouchonné.  │
 * │ Si quelqu'un casse la fusion dans `index.js`, ce test le voit.     │
 * │ Si quelqu'un DÉPLACE le bloc, le test refuse de tourner plutôt     │
 * │ que de passer à côté — d'où les deux bornes vérifiées ci-dessous.  │
 * └────────────────────────────────────────────────────────────────────┘
 *
 * Ce qu'on éprouve, et pourquoi ça compte :
 *  1. minuit UTC — la fenêtre du jour est vide, le cache doit SURVIVRE
 *     (c'est la panne qui éteignait les calques toutes les nuits) ;
 *  2. une station absente d'un cycle garde sa dernière valeur ;
 *  3. un relevé PLUS ANCIEN ne remplace pas un plus récent ;
 *  4. au-delà de 90 min, la valeur est périmée et sort du cache ;
 *  5. tous les lots en échec → l'état précédent est conservé intact ;
 *  6. `status:"OK"` sans clé `hourly` est traité comme un ÉCHEC et
 *     laisse une trace (le troisième échec silencieux de cette API).
 *
 * Usage : node tools/test_infoclimat_fusion.js
 */

const fs = require('fs');
const path = require('path');

const SRC = path.join(__dirname, '..', 'index.js');
const DEBUT = "const INFOCLIMAT_API_KEY = process.env.INFOCLIMAT_API_KEY;";
const FIN = "// ── AEMET (Espagne)";

const source = fs.readFileSync(SRC, 'utf8');
const i = source.indexOf(DEBUT);
const j = source.indexOf(FIN);
if (i < 0 || j < 0 || j <= i) {
  console.error("❌ Bloc Infoclimat introuvable dans index.js — le test ne");
  console.error("   peut pas prétendre l'avoir vérifié. Bornes attendues :");
  console.error(`   début « ${DEBUT} »`);
  console.error(`   fin   « ${FIN} »`);
  process.exit(2);
}
const bloc = source.slice(i, j);

// Le bloc est autoportant : il embarque `chunkArray`,
// `parseInfoclimatPoint` et ses propres constantes. Ses seules
// dépendances extérieures sont `fetch` et `console`, tous deux injectés.
process.env.INFOCLIMAT_API_KEY = 'cle-de-test';

const fabrique = new Function('fetch', 'console', `
  ${bloc}
  return {
    refreshInfoclimatObs,
    etat: () => ({
      cache: infoclimatObsCache,
      fetchedAt: infoclimatObsCacheFetchedAt,
      lastError: infoclimatLastError,
    }),
    amorcer: (stations, obs) => {
      infoclimatStationsList = stations;
      infoclimatObsCache = new Map(obs);
    },
    MAX_AGE: INFOCLIMAT_OBS_MAX_AGE_MS,
  };
`);

// ── Bouchons ────────────────────────────────────────────────────────
let reponseCourante = () => ({ status: 'OK', hourly: {} });
const journal = [];
const consoleMuette = {
  log: (...a) => journal.push(['log', a.join(' ')]),
  error: (...a) => journal.push(['error', a.join(' ')]),
};
const fetchBouchon = async () => {
  const corps = JSON.stringify(reponseCourante());
  return { ok: true, status: 200, text: async () => corps };
};

const M = fabrique(fetchBouchon, consoleMuette);

const STATIONS = [
  { id: 'A', nom: 'Alpha' }, { id: 'B', nom: 'Bravo' }, { id: 'C', nom: 'Charlie' },
];
const iso = ms => new Date(ms).toISOString().slice(0, 19).replace('T', ' ');
const pt = ms => ({ dh_utc: iso(ms), vent_moyen: '12', vent_direction: '180' });

let echecs = 0;
function verifier(titre, condition, detail) {
  const ok = !!condition;
  if (!ok) echecs++;
  console.log(`${ok ? '✅' : '❌'} ${titre}`);
  if (!ok && detail) console.log(`      ${detail}`);
}

(async () => {
  const maintenant = Date.now();
  console.log('═══ fusion du cache Infoclimat — sur le source réel ═══\n');

  // 1 — minuit UTC : la journée est vide, le cache doit survivre.
  M.amorcer(STATIONS, [
    ['A', { t: maintenant - 10 * 60000, moy: 12 }],
    ['B', { t: maintenant - 20 * 60000, moy: 8 }],
  ]);
  reponseCourante = () => ({ status: 'OK', hourly: {} });
  await M.refreshInfoclimatObs();
  verifier('minuit UTC — le cache survit à une journée vide',
    M.etat().cache.size === 2,
    `attendu 2 stations, obtenu ${M.etat().cache.size}`);

  // 2 — station absente du cycle : sa dernière valeur est gardée.
  reponseCourante = () => ({ status: 'OK', hourly: { A: [pt(maintenant)] } });
  await M.refreshInfoclimatObs();
  verifier('station absente d\'un cycle — valeur précédente conservée',
    M.etat().cache.size === 2 && M.etat().cache.get('B').moy === 8,
    `B = ${JSON.stringify(M.etat().cache.get('B'))}`);
  verifier('station présente — valeur mise à jour',
    Math.abs(M.etat().cache.get('A').t - maintenant) < 60000);

  // 3 — un relevé plus ancien ne doit pas faire reculer le cache.
  const avant = M.etat().cache.get('A').t;
  reponseCourante = () => ({ status: 'OK', hourly: { A: [pt(maintenant - 30 * 60000)] } });
  await M.refreshInfoclimatObs();
  verifier('relevé plus ancien — le cache ne recule pas',
    M.etat().cache.get('A').t === avant,
    `t passé de ${avant} à ${M.etat().cache.get('A').t}`);

  // 4 — péremption au-delà de 90 min.
  M.amorcer(STATIONS, [
    ['A', { t: maintenant - 5 * 60000, moy: 12 }],
    ['B', { t: maintenant - 200 * 60000, moy: 8 }],   // périmée
  ]);
  reponseCourante = () => ({ status: 'OK', hourly: { A: [pt(maintenant)] } });
  await M.refreshInfoclimatObs();
  verifier('au-delà de 90 min — la valeur est périmée et sort',
    M.etat().cache.size === 1 && !M.etat().cache.has('B'),
    `cache = ${[...M.etat().cache.keys()].join(',')}`);

  // 5 — tous les lots en échec : l'état précédent est intact.
  M.amorcer(STATIONS, [['A', { t: maintenant, moy: 12 }]]);
  const avantEchec = M.etat().fetchedAt;
  reponseCourante = () => ({ status: 'KO', errors: ['boom'] });
  await M.refreshInfoclimatObs();
  verifier('tous les lots en échec — cache et horodatage intacts',
    M.etat().cache.size === 1 && M.etat().fetchedAt === avantEchec);

  // 6 — `status:"OK"` sans `hourly` : échec, et une trace.
  journal.length = 0;
  M.amorcer(STATIONS, [['A', { t: maintenant, moy: 12 }]]);
  reponseCourante = () => ({ status: 'OK', errors: [], data: [] });
  await M.refreshInfoclimatObs();
  verifier('status OK sans « hourly » — traité comme un échec',
    M.etat().cache.size === 1);
  verifier('status OK sans « hourly » — laisse une trace exploitable',
    /hourly/.test(M.etat().lastError || '') &&
    journal.some(([n, t]) => n === 'error' && /hourly/.test(t)),
    `lastError = ${M.etat().lastError}`);

  console.log(`\n${echecs === 0 ? '✅ tout passe' : `❌ ${echecs} échec(s)`}`);
  process.exit(echecs ? 1 : 0);
})();
