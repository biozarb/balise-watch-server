// ══════════════════════════════════════════════════════════════════
//  verify-foehn-peak — contrôle la composition active_sign × direction
//  et les deux seuils, sur le VRAI code d'index.js.
//
//  Le corps de `foehnServerPeak` est extrait du fichier et évalué tel
//  quel : un test qui recopierait la fonction ne testerait que la
//  copie. Aucun réseau, aucune base, index.js n'est PAS exécuté (le
//  charger démarrerait le serveur).
//
//  node tools/verify-foehn-peak.mjs
// ══════════════════════════════════════════════════════════════════
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, '..', 'index.js'), 'utf8');

const start = src.indexOf('function foehnServerPeak');
if (start < 0) { console.error('!! foehnServerPeak introuvable dans index.js'); process.exit(1); }
// Fin = la première ligne qui ferme la fonction en colonne 0.
const end = src.indexOf('\n}\n', start) + 3;
const body = src.slice(start, end);

const FOEHN_FORECAST_HORIZON_MS = 36 * 3600 * 1000;
const foehnServerPeak = new Function(
  'FOEHN_FORECAST_HORIZON_MS',
  `${body}; return foehnServerPeak;`,
)(FOEHN_FORECAST_HORIZON_MS);

// Série synthétique : un pic à −6 hPa et un pic à +5 hPa, tous deux
// dans la fenêtre. De quoi séparer proprement les deux versants.
const now = Date.now();
const d = {
  times: [now + 3600e3, now + 7200e3, now + 10800e3],
  diff: [-6, 5, -1],
};

let ok = 0, ko = 0;
const check = (label, got, want) => {
  const hit = JSON.stringify(got) === JSON.stringify(want);
  console.log(`  ${hit ? 'ok  ' : 'ÉCHEC'} ${label}${hit ? '' : `  → ${JSON.stringify(got)} au lieu de ${JSON.stringify(want)}`}`);
  hit ? ok++ : ko++;
};
const peak = (thr, strong, dir, sign) => {
  const p = foehnServerPeak(d, thr, strong, dir, sign);
  return p ? { diff: p.diff, level: p.level, direction: p.direction } : null;
};

console.log("\nactive_sign filtre le versant que le phénomène interdit");
check("'neg' ne retient que le Δ négatif", peak(2, 4, 'both', 'neg'), { diff: -6, level: 3, direction: 'toA' });
check("'pos' ne retient que le Δ positif", peak(2, 4, 'both', 'pos'), { diff: 5, level: 3, direction: 'toB' });
check("'both' prend le plus fort des deux", peak(2, 4, 'both', 'both'), { diff: -6, level: 3, direction: 'toA' });

console.log("\nle sens surveillé par le pilote se COMPOSE avec active_sign");
check("pilote toB sur un phénomène 'neg' → rien", peak(2, 4, 'toB', 'neg'), null);
check("pilote toA sur un phénomène 'neg' → le pic négatif", peak(2, 4, 'toA', 'neg'), { diff: -6, level: 3, direction: 'toA' });
check("pilote toA sur un phénomène 'pos' → rien", peak(2, 4, 'toA', 'pos'), null);

console.log("\nles deux seuils sont ceux du phénomène, plus les constantes globales");
check("2/4 : −6 hPa est un niveau 3", peak(2, 4, 'both', 'neg'), { diff: -6, level: 3, direction: 'toA' });
check("5/10 : le même −6 n'est qu'un niveau 2", peak(5, 10, 'both', 'neg'), { diff: -6, level: 2, direction: 'toA' });
check("8/16 : le même −6 ne déclenche rien", peak(8, 16, 'both', 'neg'), { diff: -6, level: 0, direction: 'none' });

console.log("\nhors fenêtre d'anticipation");
const old = { times: [now - 7200e3], diff: [-9] };
check("un pic passé est ignoré", foehnServerPeak(old, 2, 4, 'both', 'neg'), null);
const far = { times: [now + 72 * 3600e3], diff: [-9] };
check("un pic au-delà de 36 h est ignoré", foehnServerPeak(far, 2, 4, 'both', 'neg'), null);

console.log(`\n${ok} contrôles au vert, ${ko} au rouge.`);
process.exit(ko ? 1 : 0);
