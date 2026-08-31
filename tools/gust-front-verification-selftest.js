// Auto-test de la COMPTABILITÉ prévu ↔ mesuré (Lot 3, 31/08/2026).
//
// Ce que ces contrôles protègent : deux taux que Yann lira pour juger le
// détecteur, et qu'il est très facile de rendre faux dans le sens
// flatteur — apparier trop large, compter les saisies manuelles, ou
// juger un épisode encore vivant. Chacun de ces trois pièges a son
// contrôle ici.
//
//   node tools/gust-front-verification-selftest.js

const gf = require('../gust-front');

let failures = 0;
function check(label, ok, detail) {
  console.log(`${ok ? '  ok  ' : ' FAIL '} ${label}${detail ? ` — ${detail}` : ''}`);
  if (!ok) failures++;
}

const H = 3600 * 1000;
const T0 = Date.UTC(2026, 7, 20, 12, 0, 0);
const iso = ms => new Date(ms).toISOString();

/** Rectangle lon/lat, comme un couloir d'impact. */
function boite(lon, lat, dLon = 0.8, dLat = 0.5) {
  return [
    [lon - dLon, lat - dLat], [lon + dLon, lat - dLat],
    [lon + dLon, lat + dLat], [lon - dLon, lat + dLat], [lon - dLon, lat - dLat],
  ];
}

function ep(id, source, opts = {}) {
  const debut = opts.debutH == null ? 0 : opts.debutH;
  return {
    id, source,
    status: opts.status ?? 'passed',
    is_manual: opts.is_manual ?? false,
    created_at: iso(T0 + debut * H),
    updated_at: iso(T0 + (opts.finH ?? debut + 1) * H),
    eta_start: null, eta_end: null,
    corridor: opts.corridor ?? boite(5, 45),
    verdict: opts.verdict ?? null,
    announced_event_id: opts.announced_event_id ?? null,
    confirmed_at: opts.confirmed_at ?? null,
  };
}

console.log('\nComptabilité prévu ↔ mesuré — auto-test\n');

// ── Recouvrement des couloirs ──────────────────────────────────────
check('deux couloirs qui se superposent se reconnaissent',
  gf.gfRingsOverlap(boite(5, 45), boite(5.4, 45.2)) === true);
check('deux couloirs éloignés ne se reconnaissent pas',
  gf.gfRingsOverlap(boite(5, 45), boite(9, 45)) === false);
// Le cas que l'échantillonnage raterait : deux couloirs en croix, aucun
// sommet de l'un dans l'autre, mais des arêtes qui se croisent. C'est la
// géométrie d'une veille et d'une mesure qui se rejoignent
// perpendiculairement — exactement ce qu'on cherche à apparier.
check('deux couloirs croisés en X se reconnaissent (aucun sommet dedans)',
  gf.gfRingsOverlap(boite(5, 45, 3.0, 0.2), boite(5, 45, 0.2, 3.0)) === true);
check('un anneau dégénéré ne fait pas d’appariement',
  gf.gfRingsOverlap(boite(5, 45), [[5, 45], [5, 46]]) === false);

// ── Rattachement d'un front à un épisode suivi ─────────────────────
// C'est le mécanisme qui remplace le singleton `gfActiveEvent` : à
// chaque cycle, chaque front reconstruit prolonge un épisode existant ou
// en ouvre un nouveau. Une erreur ici, et deux orages sans rapport
// repartagent le même événement — exactement le défaut qu'on corrige.
{
  const alpes = { id: 'ALPES', status: 'confirmed', corridor: boite(6, 45.3) };
  const aquitaine = { id: 'AQUI', status: 'confirmed', corridor: boite(-0.5, 44.2) };
  const eps = [alpes, aquitaine];

  check('un front alpin retrouve l’épisode alpin',
    gf.gfPickEpisodeFrom(eps, boite(6.2, 45.4))?.id === 'ALPES');
  check('un front aquitain retrouve l’épisode aquitain',
    gf.gfPickEpisodeFrom(eps, boite(-0.3, 44.3))?.id === 'AQUI');
  // LE cas qui motivait tout : avant le 31/08, ce front breton aurait
  // « raffiné » le seul épisode existant, en écrasant sa géométrie.
  check('un front breton n’en retrouve aucun et ouvrira le sien',
    gf.gfPickEpisodeFrom(eps, boite(-2.5, 48.2)) === null);

  // Deux fronts du même cycle ne peuvent pas revendiquer le même
  // épisode : le second doit en ouvrir un nouveau.
  const pris = new Set(['ALPES']);
  check('un épisode déjà revendiqué ce cycle n’est pas réattribué',
    gf.gfPickEpisodeFrom(eps, boite(6.2, 45.4), { claimed: pris }) === null);

  // Le filtre sert à distinguer promotion (une veille) et cohabitation
  // (un épisode déjà mesuré, que le modèle ne doit pas rétrograder).
  const veille = { id: 'VEILLE', status: 'watch', corridor: boite(3, 47) };
  const mesure = { id: 'MESURE', status: 'confirmed', corridor: boite(3, 47) };
  check('le filtre « veille » ne rend que la veille',
    gf.gfPickEpisodeFrom([veille, mesure], boite(3, 47),
      { filter: e => e.status === 'watch' })?.id === 'VEILLE');
  check('le filtre « déjà mesuré » ne rend que la mesure',
    gf.gfPickEpisodeFrom([veille, mesure], boite(3, 47),
      { filter: e => e.status !== 'watch' })?.id === 'MESURE');

  // Deux épisodes recouvrent le front : le plus proche gagne, sinon le
  // rattachement dépendrait de l'ordre de la liste.
  const proche = { id: 'PROCHE', status: 'confirmed', corridor: boite(5.1, 45) };
  const loin = { id: 'LOIN', status: 'confirmed', corridor: boite(4.0, 45) };
  check('à recouvrement égal, l’épisode le plus proche gagne',
    gf.gfPickEpisodeFrom([loin, proche], boite(5.2, 45))?.id === 'PROCHE');

  check('un épisode sans couloir ne capte rien',
    gf.gfPickEpisodeFrom([{ id: 'X', corridor: null }], boite(5, 45)) === null);
}

// ── Appariement ────────────────────────────────────────────────────
// Nominal : une veille, puis une mesure au même endroit deux heures
// après. Elle s'est produite.
{
  const evs = [
    ep('A', 'model', { debutH: 0, finH: 1 }),
    ep('M', 'mf_network', { debutH: 3, finH: 4 }),
  ];
  const u = gf.gfMatchEpisodes(evs);
  const byId = Object.fromEntries(u.map(x => [x.id, x]));
  check('veille suivie d’une mesure au même endroit : réalisée',
    byId.A?.verdict === 'realise', byId.A?.verdict);
  check('la mesure pointe sur la veille qui l’avait annoncée',
    byId.M?.verdict === 'realise' && byId.M?.announced_event_id === 'A',
    `${byId.M?.verdict} → ${byId.M?.announced_event_id}`);
}

// Trop loin dans le temps : la tolérance est de ±2 h autour de la
// fenêtre, une mesure 12 h plus tard n'est pas la réalisation de cette
// veille-là.
{
  const u = gf.gfMatchEpisodes([
    ep('A', 'model', { debutH: 0, finH: 1 }),
    ep('M', 'mf_network', { debutH: 12, finH: 13 }),
  ]);
  const byId = Object.fromEntries(u.map(x => [x.id, x]));
  check('mesure 12 h plus tard : la veille reste non réalisée',
    byId.A?.verdict === 'non_realise', byId.A?.verdict);
  check('et cette mesure est comptée comme non prévue',
    byId.M?.verdict === 'non_prevu', byId.M?.verdict);
}

// Trop loin dans l'espace : bon horaire, mauvais endroit. C'est
// littéralement le défaut du 31/08 (promotion sans contrôle
// géographique) qu'on refuse de réintroduire ici.
{
  const u = gf.gfMatchEpisodes([
    ep('A', 'model', { debutH: 0, finH: 1, corridor: boite(-1, 48) }),
    ep('M', 'mf_network', { debutH: 2, finH: 3, corridor: boite(7, 43) }),
  ]);
  const byId = Object.fromEntries(u.map(x => [x.id, x]));
  check('même heure, 700 km plus loin : aucun appariement',
    byId.A?.verdict === 'non_realise' && byId.M?.verdict === 'non_prevu',
    `${byId.A?.verdict} / ${byId.M?.verdict}`);
}

// Une prévision parle AVANT. Une veille écrite après coup, au même
// endroit et dans la même fenêtre, n'a rien anticipé — c'est le cas réel
// trouvé en rejouant l'archive : veille de 00:05 contre front mesuré à
// 19:41 la veille, appariés parce que leurs fenêtres élargies de ±2 h
// finissaient par se toucher.
{
  const u = gf.gfMatchEpisodes([
    ep('A', 'model', { debutH: 5, finH: 6 }),
    ep('M', 'mf_network', { debutH: 0, finH: 5 }),
  ]);
  const byId = Object.fromEntries(u.map(x => [x.id, x]));
  check('une veille postérieure au front mesuré n’anticipe rien',
    byId.A?.verdict === 'non_realise' && byId.M?.verdict === 'non_prevu',
    `${byId.A?.verdict} / ${byId.M?.verdict}`);
}

// Promotion sur place : la veille et sa confirmation sont la même ligne.
{
  const u = gf.gfMatchEpisodes([ep('X', 'merged', { debutH: 0, finH: 2 })]);
  check('un épisode promu sur place est réalisé et pointe sur lui-même',
    u[0]?.verdict === 'realise' && u[0]?.announced_event_id === 'X',
    `${u[0]?.verdict} → ${u[0]?.announced_event_id}`);
}

// Un épisode encore VIVANT n'a pas de verdict.
{
  const u = gf.gfMatchEpisodes([
    ep('A', 'model', { status: 'watch' }),
    ep('M', 'mf_network', { status: 'confirmed' }),
  ]);
  check('un épisode encore vivant n’est pas jugé', u.length === 0,
    `${u.length} verdict(s)`);
}

// Les saisies manuelles sont hors comptabilité — elles flatteraient les
// deux taux, et ce ne sont pas des sorties de détecteur.
{
  const u = gf.gfMatchEpisodes([
    ep('H', 'manual', { is_manual: true }),
    ep('H2', 'mf_network', { is_manual: true }),
  ]);
  check('les épisodes manuels sont écartés', u.length === 0, `${u.length} verdict(s)`);
}

// Idempotence : repasser sur des épisodes déjà jugés ne réécrit rien.
// La réconciliation tourne en boucle ; sans ça elle repatcherait
// l'historique entier toutes les heures.
{
  const evs = [
    ep('A', 'model', { debutH: 0, finH: 1, verdict: 'realise' }),
    ep('M', 'mf_network', { debutH: 3, finH: 4, verdict: 'realise', announced_event_id: 'A' }),
  ];
  check('un historique déjà jugé ne produit aucune écriture',
    gf.gfMatchEpisodes(evs).length === 0);
}

// Un verdict peut CHANGER : une veille jugée non réalisée hier, parce
// que la mesure n'était pas encore close, doit devenir réalisée
// aujourd'hui. C'est la raison pour laquelle la réconciliation relit
// aussi les épisodes déjà jugés.
{
  const evs = [
    ep('A', 'model', { debutH: 0, finH: 1, verdict: 'non_realise' }),
    ep('M', 'mf_network', { debutH: 3, finH: 4 }),
  ];
  const byId = Object.fromEntries(gf.gfMatchEpisodes(evs).map(x => [x.id, x]));
  check('un verdict erroné se corrige au passage suivant',
    byId.A?.verdict === 'realise', byId.A?.verdict);
}

// ── Les deux taux ──────────────────────────────────────────────────
{
  const evs = [
    // 4 annoncés : 1 réalisé (merged), 1 réalisé (apparié), 2 non réalisés
    ep('A1', 'merged', { verdict: 'realise', announced_event_id: 'A1',
      confirmed_at: iso(T0 + 3 * H) }),
    ep('A2', 'model', { verdict: 'realise' }),
    ep('A3', 'model', { verdict: 'non_realise' }),
    ep('A4', 'model', { verdict: 'non_realise' }),
    // 4 mesurés : A1 (merged) + M1 (apparié à A2) + 2 non prévus
    ep('M1', 'mf_network', { verdict: 'realise', announced_event_id: 'A2' }),
    ep('M2', 'mf_network', { verdict: 'non_prevu' }),
    ep('M3', 'mf_network', { verdict: 'non_prevu' }),
    // Un manuel, qui ne doit compter nulle part
    ep('H', 'manual', { is_manual: true, verdict: 'non_prevu' }),
    // Un clos jamais jugé : compté dans `pending`, pas dans les taux
    ep('Z', 'mf_network', { verdict: null }),
  ];
  const r = gf.gfVerificationRates(evs);
  check('taux de réalisation : 2 annoncés réalisés sur 4',
    r.announced.total === 4 && r.announced.realised === 2 && r.announced.rate === 50,
    `${r.announced.realised}/${r.announced.total} = ${r.announced.rate} %`);
  check('taux d’anticipation : 2 mesurés anticipés sur 4',
    r.measured.total === 4 && r.measured.anticipated === 2 && r.measured.rate === 50,
    `${r.measured.anticipated}/${r.measured.total} = ${r.measured.rate} %`);
  check('le manuel ne compte dans aucun des deux',
    r.announced.total + r.measured.total === 8);
  check('un épisode clos non jugé est signalé, pas dilué dans les taux',
    r.pending === 1, `${r.pending} en attente`);
  check('préavis réellement offert remonté',
    r.leadTimeMin.count === 1 && r.leadTimeMin.median === 180,
    `${r.leadTimeMin.median} min sur ${r.leadTimeMin.count}`);
}

// Zéro épisode : des taux nuls, pas une division par zéro déguisée en 0 %.
{
  const r = gf.gfVerificationRates([]);
  check('aucun épisode : taux null et non 0 %',
    r.announced.rate === null && r.measured.rate === null);
}

console.log(`\n${failures === 0 ? 'Tous les contrôles passent.' : `${failures} contrôle(s) en échec.`}\n`);
process.exit(failures === 0 ? 0 : 1);
