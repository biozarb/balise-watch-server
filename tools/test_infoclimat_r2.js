#!/usr/bin/env node
/**
 * test_infoclimat_r2.js — éprouver la lecture des objets R2 Infoclimat
 * SUR LE VRAI SOURCE (03/08/2026).
 *
 * Remplace `test_infoclimat_fusion.js`, écrit quelques heures plus tôt
 * le même jour : il éprouvait la fusion du cache d'observations, qui
 * vivait alors dans `refreshInfoclimatObs`. Cette logique a DÉMÉNAGÉ
 * dans le poller Python du VPS — ce serveur ne poll plus, il lit.
 * L'ancien test n'avait plus de sujet ; le garder aurait fait croire à
 * une couverture qui n'existait plus.
 *
 * ┌─ POURQUOI CE HARNAIS DÉCOUPE LE SOURCE ───────────────────────────┐
 * │ Le serveur n'a pas de tests, et `index.js` appelle `app.listen`    │
 * │ dès l'import : impossible de le `require`. Recopier la logique     │
 * │ dans le test aurait testé ma copie — le pire des faux positifs.    │
 * │ On découpe donc le bloc réel et on l'évalue avec `fetch` bouchonné.│
 * │ Si les bornes bougent, le test REFUSE de tourner plutôt que de     │
 * │ passer à côté.                                                     │
 * └────────────────────────────────────────────────────────────────────┘
 *
 * Ce qu'on éprouve, et pourquoi ça compte :
 *  1. `t` arrive en SECONDES (convention Python du poller) et doit
 *     ressortir en MILLISECONDES — un facteur 1000 passerait inaperçu
 *     jusqu'à ce qu'un graphe affiche 1970 ;
 *  2. un relevé de plus de 90 min est écarté À LA LECTURE. C'est le
 *     garde-fou qui compte : si le VPS meurt, `latest.json` se fige, et
 *     sans ce filtre on servirait un vent d'il y a six heures comme
 *     courant — pour une app de sécurité en vol, pire que rien ;
 *  3. un objet périmé laisse une trace exploitable (poller arrêté) ;
 *  4. une panne réseau ne VIDE PAS le cache précédent ;
 *  5. l'historique colonnaire se déplie aligné, série manquante = nulls ;
 *  6. la licence de CHAQUE station arrive jusqu'au client.
 *
 * Usage : node tools/test_infoclimat_r2.js
 */

const fs = require('fs');
const path = require('path');

const SRC = path.join(__dirname, '..', 'index.js');
const DEBUT = "const INFOCLIMAT_R2_BASE = process.env.INFOCLIMAT_R2_BASE";
const FIN = "// ── AEMET (Espagne) : stations vent+pression";

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

const journal = [];
const consoleMuette = {
  log: (...a) => journal.push(['log', a.join(' ')]),
  error: (...a) => journal.push(['error', a.join(' ')]),
};

// Bouchon de `fetch` : `reponse` est réassignée avant chaque scénario.
let reponse = () => ({ ok: true, corps: {} });
const fetchBouchon = async () => {
  const r = reponse();
  if (r.boom) throw new Error(r.boom);
  return {
    ok: r.ok !== false,
    status: r.status ?? (r.ok === false ? 500 : 200),
    json: async () => r.corps,
  };
};

const M = new Function('fetch', 'console', `
  ${bloc}
  return {
    refreshInfoclimatObs, refreshInfoclimatHistory,
    etat: () => ({
      liste: infoclimatStationsList,
      parId: infoclimatStationsById,
      obs: infoclimatObsCache,
      hist: infoclimatHistory,
      erreur: infoclimatLastError,
    }),
  };
`)(fetchBouchon, consoleMuette);

const secondes = ms => Math.floor(ms / 1000);
const META = { nom: 'Alpha', lat: 45.3, lon: 5.8, alt: 900,
               licence_code: 2, licence: 'NON-COMMERCIAL ONLY: CC BY NC',
               licence_url: 'https://example.org/by-nc' };

let echecs = 0;
function verifier(titre, condition, detail) {
  const ok = !!condition;
  if (!ok) echecs++;
  console.log(`${ok ? '✅' : '❌'} ${titre}`);
  if (!ok && detail) console.log(`      ${detail}`);
}

(async () => {
  const now = Date.now();
  console.log('═══ lecture R2 Infoclimat — sur le source réel ═══\n');

  // 1 — conversion secondes → millisecondes, et licence transportée.
  reponse = () => ({ corps: {
    genere_le: new Date(now).toISOString(),
    stations: { A: META },
    obs: { A: { t: secondes(now - 5 * 60000), moy: 12.6, raf: null,
                dir: 180, pres: 1013.2, temp: 22.4 } },
  } });
  await M.refreshInfoclimatObs();
  const a = M.etat().obs.get('A');
  verifier('`t` en secondes → millisecondes',
    a && Math.abs(a.t - (now - 5 * 60000)) < 1500,
    `t = ${a && a.t} (attendu ~${now - 5 * 60000})`);
  verifier('`pres` → `pressure`, champs de vent conservés',
    a && a.pressure === 1013.2 && a.moy === 12.6 && a.dir === 180);
  const meta = M.etat().parId.get('A');
  verifier('la licence de la station arrive jusqu\'au client',
    meta && meta.licenseCode === 2
    && meta.licenseLabel === 'NON-COMMERCIAL ONLY: CC BY NC'
    && meta.licenseUrl === 'https://example.org/by-nc',
    JSON.stringify(meta));

  // 2 — péremption À LA LECTURE : le garde-fou qui compte.
  reponse = () => ({ corps: {
    genere_le: new Date(now).toISOString(),
    stations: { A: META, B: { ...META, nom: 'Bravo' } },
    obs: {
      A: { t: secondes(now - 10 * 60000), moy: 12 },
      B: { t: secondes(now - 6 * 3600 * 1000), moy: 40 },  // 6 h : périmée
    },
  } });
  await M.refreshInfoclimatObs();
  verifier('un relevé de 6 h est écarté à la lecture',
    M.etat().obs.size === 1 && !M.etat().obs.has('B'),
    `cache = ${[...M.etat().obs.keys()].join(',')}`);

  // 3 — objet périmé : le poller du VPS est mort, il faut le dire.
  reponse = () => ({ corps: {
    genere_le: new Date(now - 3 * 3600 * 1000).toISOString(),
    stations: { A: META },
    obs: { A: { t: secondes(now - 10 * 60000), moy: 12 } },
  } });
  await M.refreshInfoclimatObs();
  verifier('objet périmé → trace exploitable',
    /périmé/.test(M.etat().erreur || ''),
    `lastError = ${M.etat().erreur}`);

  // 4 — panne réseau : on GARDE l'état précédent.
  const avant = M.etat().obs.size;
  reponse = () => ({ boom: 'ECONNRESET' });
  await M.refreshInfoclimatObs();
  verifier('panne réseau — le cache précédent est conservé',
    M.etat().obs.size === avant && /ECONNRESET/.test(M.etat().erreur || ''),
    `taille ${M.etat().obs.size} (avant ${avant})`);

  // 5 — objet absent (poller jamais lancé) : dégradation silencieuse.
  reponse = () => ({ ok: false, status: 404 });
  await M.refreshInfoclimatObs();
  verifier('objet absent (404) → message explicite, pas de crash',
    /pas encore écrit/.test(M.etat().erreur || ''),
    `lastError = ${M.etat().erreur}`);

  // 6 — historique colonnaire : dépliage aligné.
  reponse = () => ({ corps: {
    genere_le: new Date(now).toISOString(),
    historique: {
      A: { t: [secondes(now - 3600000), secondes(now - 1800000), secondes(now)],
           moy: [10, null, 14],
           dir: [180, 190, 200] },   // pas de `raf` ni `pres` : tout nul
    },
  } });
  await M.refreshInfoclimatHistory();
  const h = M.etat().hist.get('A');
  verifier('historique colonnaire déplié, 3 points',
    h && h.length === 3, `${h && h.length} point(s)`);
  verifier('séries alignées sur `t`, trou = null à sa position',
    h && h[0].avg === 10 && h[1].avg === null && h[2].avg === 14
      && h[1].dir === 190,
    JSON.stringify(h));
  verifier('série absente → null partout, jamais 0',
    h && h.every(p => p.max === null && p.pressure === null),
    JSON.stringify(h && h.map(p => p.max)));
  verifier('`t` de l\'historique aussi en millisecondes',
    h && Math.abs(h[2].t - now) < 1500);
  verifier('`min` toujours null (pas de minimum glissant chez Infoclimat)',
    h && h.every(p => p.min === null));

  // 7 — historique vide : ne pas écraser ce qu'on avait.
  reponse = () => ({ corps: { genere_le: new Date(now).toISOString(),
                              historique: {} } });
  await M.refreshInfoclimatHistory();
  verifier('historique vide — l\'ancien est conservé',
    M.etat().hist.size === 1 && M.etat().hist.get('A').length === 3);

  console.log(`\n${echecs === 0 ? '✅ tout passe' : `❌ ${echecs} échec(s)`}`);
  process.exit(echecs ? 1 : 0);
})();
