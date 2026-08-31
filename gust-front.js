// ═══════════════════════════════════════════════════════════════════
//  gust-front.js — Détection d'un FRONT DE RAFALES sur le réseau
//  d'observation Météo-France (RADOME, paquet infrahoraire 6 min).
//
//  Cf. PROMPT_REPRISE_FRONT_RAFALES.md (§2 physique, §4.2 algorithme).
//
//  ── Pourquoi un module séparé du monolithe index.js ──────────────
//  Ce fichier ne fait AUCUNE I/O : ni réseau, ni Supabase, ni push. Il
//  reçoit des observations déjà converties en unités de l'app et rend
//  un objet « front » ou null. C'est ce qui permettra de le rejouer sur
//  l'archive Météo-France 6 min du 30/07/2026 (§8.2 de la spec) pour
//  calibrer les seuils, sans toucher au réseau ni à la prod.
//  L'ingestion, la persistance et le push restent dans index.js.
//
//  ── Pourquoi la pression pèse le plus lourd ──────────────────────
//  Le saut de pression (mesohigh) est le seul des quatre signaux qui ne
//  dépende quasiment pas de l'exposition de la station ni du relief
//  local : une station de fond de vallée abritée ne verra peut-être pas
//  la rafale, mais elle verra le saut de pression. Historiquement, les
//  premiers détecteurs opérationnels de fronts de rafales étaient des
//  réseaux de barographes (pressure jump array de Dulles).
//
//  ── Historique en RAM, pas en base ───────────────────────────────
//  ~780 stations × 10 relevés/h = ~24 000 lignes/h qu'aucun client ne
//  lit jamais. Même philosophie que beaconHistory. Contrepartie
//  assumée : après un redémarrage Render, il faut ~40 min pour
//  reconstituer une ligne de base — exposé dans gfHealth().warmup,
//  jamais silencieux (un détecteur muet EN PANNE est indiscernable
//  d'un détecteur muet qui n'a rien à signaler : c'est LE risque
//  principal de ce type de système).
// ═══════════════════════════════════════════════════════════════════

'use strict';

// ── Fenêtres temporelles ───────────────────────────────────────────
/** Profondeur de l'historique conservé par station. */
const GF_HISTORY_MAX_AGE_MS = 3 * 60 * 60 * 1000;
/** Écart sur lequel on mesure le saut de pression et la chute de température. */
const GF_JUMP_WINDOW_MIN = 18;
/** Fenêtre de référence (« avant le front ») pour le vent et la direction. */
const GF_BASE_FROM_MIN = 36;
const GF_BASE_TO_MIN = 12;
/** Regroupement des passages de stations en un même épisode. */
const GF_CLUSTER_WINDOW_MIN = 90;

// ── Seuils de passage par station (§4.2) ───────────────────────────
//  ⚠️ NON VALIDÉS. Points de départ issus de la littérature, à calibrer
//  sur l'archive MF 6 min (§8.2). Toute modification doit s'accompagner
//  d'un incrément de GF_THRESHOLDS_VERSION, sans quoi deux campagnes de
//  calibration ne sont plus comparables entre elles.
// v2 (31/08/2026) : ajout du regroupement SPATIAL et du repêchage local.
// Aucun seuil de station n'a bougé, mais l'ENSEMBLE des stations retenues
// pour un front change — donc les épisodes v1 et v2 ne sont pas
// comparables, et c'est précisément ce que cette version sert à dire.
const GF_THRESHOLDS_VERSION = 'v2-2026-08-31';
const GF_DP_HPA = 0.7;      // saut de pression sur GF_JUMP_WINDOW_MIN
const GF_DTHETA_DEG = 40;   // bascule de direction
const GF_DFF_KMH = 20;      // saut de rafale
const GF_DT_C = -2.0;       // chute de température
const GF_SCORE_MIN = 65;    // impose AU MOINS deux signaux concordants
/** Seuil abaissé DANS le couloir d'une veille modèle en cours (Lot A) :
 *  un saut de pression seul (40) y suffit alors, parce qu'on l'attendait
 *  précisément là et à peu près à cette heure. Hors couloir, il faut
 *  toujours deux signaux. */
const GF_SCORE_MIN_PRIOR = 40;
const GF_GUST_MIN_KMH = 45; // un front de rafales sans rafale n'existe pas

// ── Garde-fous sur le front reconstruit ────────────────────────────
/** En deçà, ce n'est pas une ligne cohérente mais du bruit corrélé. */
const GF_MIN_STATIONS = 4;

// ── Regroupement SPATIAL (31/08/2026) ──────────────────────────────
//  ⚠️ Défaut trouvé le 31/08/2026, en cherchant pourquoi le bandeau ne
//  dit jamais OÙ est le front (retour Yann : « beaucoup de pilotes
//  pensent que c'est proche d'eux »).
//
//  Le regroupement des passages était UNIQUEMENT TEMPOREL : toutes les
//  stations franchies dans GF_CLUSTER_WINDOW_MIN étaient ajustées par un
//  SEUL plan spatio-temporel, où qu'elles soient en France. Relevé sur
//  les 30 épisodes mesurés du 31/07 au 30/08 : emprise médiane 203 km,
//  maximum 742 km, et des épisodes dont les stations tombaient en Corse,
//  à Nice ET en Alsace. Le bandeau ne pouvait pas dire où était le front
//  pour une raison simple : l'objet lui-même n'était nulle part.
//
//  Pire que l'affichage : dans 8 des 10 cas les plus dispersés, il y
//  avait un noyau cohérent de 3 stations PLUS une station isolée à
//  300–700 km. Comme il faut 4 points pour qu'un plan ait un degré de
//  liberté, c'est cette station lointaine qui faisait franchir le
//  minimum — donc qui donnait la vitesse, le cap et toutes les ETA. Elle
//  ne validait rien, elle corrompait la géométrie.
//
//  D'où : on regroupe d'abord dans l'ESPACE (liaison simple), puis on
//  ajuste un plan PAR groupe. Un front réellement continu — une ligne
//  d'orages, un front froid synoptique de 1 500 km — reste un seul
//  groupe, parce que ses points se touchent de proche en proche. Deux
//  orages sans rapport ne se rejoignent plus jamais.
/** Distance de liaison de proche en proche. 150 km : le réseau MF est
 *  au pas de ~30 km, une ligne d'orages réelle est donc chaînée sans
 *  peine, alors que Corse↔continent (~180 km), Nice↔Alsace (~500 km) ou
 *  Rennes↔Landes (~500 km) sont séparés. */
const GF_CLUSTER_RADIUS_KM = 150;
/** Un noyau de cette taille est cohérent mais insuffisant pour ajuster
 *  un plan vérifiable : il ouvre droit au REPÊCHAGE ci-dessous. */
const GF_RESCUE_MIN_CORE = 3;
/** Voisinage dans lequel on relit les stations au seuil abaissé quand un
 *  noyau incomplet existe. Même raisonnement que le couloir d'une veille
 *  modèle (GF_SCORE_MIN_PRIOR) : à 100 km de trois stations qui viennent
 *  de montrer une signature franche, dans la même fenêtre de 90 min, une
 *  signature partielle est bien moins susceptible d'être une
 *  coïncidence qu'ailleurs. On récupère ainsi le front local au lieu de
 *  le perdre — sans jamais aller chercher le point à 400 km qui, lui,
 *  n'est probablement pas le même front. */
const GF_RESCUE_RADIUS_KM = 100;
/** Vitesses physiquement plausibles pour un outflow (§2). */
const GF_SPEED_MIN_KMH = 20;
const GF_SPEED_MAX_KMH = 110;
/** Qualité minimale de l'ajustement spatio-temporel. */
const GF_MIN_R2 = 0.5;
/** Marge latérale du couloir d'impact, de part et d'autre du front. */
const GF_CORRIDOR_MARGIN_KM = 20;
/** Profondeur temporelle du couloir d'impact. */
const GF_CORRIDOR_HOURS = 3;
/** Nombre minimal d'échantillons pour qu'une station soit exploitable. */
const GF_MIN_SAMPLES = 10;
/** Une station muette depuis plus longtemps est écartée du calcul. */
const GF_STATION_STALE_MS = 20 * 60 * 1000;

const KM_PER_DEG_LAT = 111.32;

// ═══════════════════════════════════════════════════════════════════
//  Historique glissant
// ═══════════════════════════════════════════════════════════════════

/** id station → [{ t, pmer, ff, raf, dd, temp }] trié par t croissant. */
const gfHistory = new Map();
/** Instant du premier échantillon jamais enregistré (mesure du warmup). */
let gfFirstSampleAt = 0;

/**
 * Enregistre un cycle d'observations. Appelé par index.js après chaque
 * refreshMfObs (6 min), avec les valeurs DÉJÀ converties en unités de
 * l'app (km/h, hPa, °C) — la conversion depuis les unités SI de
 * Météo-France reste centralisée dans refreshMfObs, une seule fois,
 * comme le veut le §10 de la spec (« erreur classique et invisible en
 * production »).
 *
 * @param {Array<{id:string,pmer:number|null,ff:number|null,raf:number|null,dd:number|null,temp:number|null}>} obs
 * @param {number} t epoch ms
 */
function gfRecordObs(obs, t) {
  if (!Array.isArray(obs) || !obs.length) return;
  if (!gfFirstSampleAt) gfFirstSampleAt = t;
  const cutoff = t - GF_HISTORY_MAX_AGE_MS;

  for (const o of obs) {
    if (!o || !o.id) continue;
    // Une station sans pression NI rafale n'apporte rien au détecteur :
    // ne pas la stocker évite de gonfler la RAM avec du vide.
    if (o.pmer == null && o.raf == null) continue;
    let arr = gfHistory.get(o.id);
    if (!arr) { arr = []; gfHistory.set(o.id, arr); }
    // Le paquet MF peut être rejoué à l'identique si le pipeline amont a
    // pris du retard (même validity_time servi deux fois) : on ne
    // duplique pas un échantillon déjà enregistré au même instant.
    if (arr.length && arr[arr.length - 1].t >= t) continue;
    arr.push({
      t,
      pmer: o.pmer ?? null,
      ff: o.ff ?? null,
      raf: o.raf ?? null,
      dd: o.dd ?? null,
      temp: o.temp ?? null,
    });
    while (arr.length && arr[0].t < cutoff) arr.shift();
  }

  // Purge des stations qui ont totalement disparu du paquet (station
  // démontée, panne longue) — sinon la Map ne décroît jamais.
  for (const [id, arr] of gfHistory) {
    if (!arr.length || arr[arr.length - 1].t < cutoff) gfHistory.delete(id);
  }
}

// ═══════════════════════════════════════════════════════════════════
//  Utilitaires
// ═══════════════════════════════════════════════════════════════════

/** Écart angulaire signé ramené à ±180°. */
function angDiff(a, b) {
  let d = ((a - b + 540) % 360) - 180;
  return d;
}

/** Moyenne circulaire d'un jeu de directions (deg). */
function circularMean(degs) {
  if (!degs.length) return null;
  let sx = 0, sy = 0;
  for (const d of degs) {
    const r = (d * Math.PI) / 180;
    sx += Math.cos(r); sy += Math.sin(r);
  }
  if (sx === 0 && sy === 0) return null;
  return ((Math.atan2(sy, sx) * 180) / Math.PI + 360) % 360;
}

function median(nums) {
  if (!nums.length) return null;
  const s = [...nums].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}

/**
 * Valeur d'un champ au plus proche d'un instant cible, à condition
 * qu'un échantillon existe dans une tolérance raisonnable. Renvoie null
 * plutôt que d'extrapoler — on ne fabrique jamais de donnée (règle
 * projet « aucune donnée inventée »).
 */
function valueAt(arr, targetT, field, toleranceMs = 9 * 60 * 1000) {
  let best = null, bestDt = Infinity;
  for (const s of arr) {
    if (s[field] == null) continue;
    const dt = Math.abs(s.t - targetT);
    if (dt < bestDt) { bestDt = dt; best = s[field]; }
  }
  return bestDt <= toleranceMs ? best : null;
}

function samplesBetween(arr, fromT, toT, field) {
  const out = [];
  for (const s of arr) {
    if (s.t >= fromT && s.t <= toT && s[field] != null) out.push(s[field]);
  }
  return out;
}

function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = ((lat2 - lat1) * Math.PI) / 180;
  const dLon = ((lon2 - lon1) * Math.PI) / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

/**
 * Projection locale plane (km) autour d'une origine. Suffisante ici :
 * l'emprise d'un front suivi fait quelques centaines de km, l'erreur de
 * la projection équirectangulaire y est très inférieure à l'incertitude
 * de la détection elle-même.
 */
function makeProjector(lat0, lon0) {
  const kx = KM_PER_DEG_LAT * Math.cos((lat0 * Math.PI) / 180);
  return {
    toXY: (lat, lon) => ({ x: (lon - lon0) * kx, y: (lat - lat0) * KM_PER_DEG_LAT }),
    toLatLon: (x, y) => ({ lat: lat0 + y / KM_PER_DEG_LAT, lon: lon0 + x / kx }),
  };
}

// ═══════════════════════════════════════════════════════════════════
//  Étage 1 — score de passage par station
// ═══════════════════════════════════════════════════════════════════

/**
 * Évalue la signature de front sur l'échantillon d'indice `i` d'une
 * station.
 *
 * ⚠️ Point de conception non évident, découvert à l'auto-test : il faut
 * scorer CHAQUE échantillon, pas seulement le dernier. Le saut de
 * pression est une DÉRIVÉE sur 18 min — une fois le front passé, la
 * pression se stabilise en palier et la dérivée retombe à zéro. Une
 * station n'est donc « en passage » que pendant une fenêtre de quelques
 * minutes. En ne regardant que le dernier relevé, on n'aurait jamais eu
 * qu'une seule station détectée à la fois, toutes horodatées à l'instant
 * du poll : impossible d'en tirer une vitesse de propagation (le plan
 * spatio-temporel devenait dégénéré, faute de variance en temps).
 *
 * Balayer l'historique donne à chaque station son HEURE DE PASSAGE
 * réelle, ce qui est précisément la quantité dont le §4.2 a besoin. Et
 * ça marche à l'identique en direct et en rejeu d'archive.
 */
function gfScoreAtSample(arr, i) {
  const last = arr[i];
  const t = last.t;
  const jumpT = t - GF_JUMP_WINDOW_MIN * 60 * 1000;
  const baseFrom = t - GF_BASE_FROM_MIN * 60 * 1000;
  const baseTo = t - GF_BASE_TO_MIN * 60 * 1000;

  // Δp — le signal directeur.
  let dP = null;
  if (last.pmer != null) {
    const prev = valueAt(arr, jumpT, 'pmer');
    if (prev != null) dP = last.pmer - prev;
  }

  // Δrafale, contre la médiane de la fenêtre de référence (médiane et
  // non moyenne : une rafale isolée dans la fenêtre de base ne doit pas
  // relever artificiellement la référence et masquer le vrai saut).
  let dFf = null;
  if (last.raf != null) {
    const base = median(samplesBetween(arr, baseFrom, baseTo, 'raf'));
    if (base != null) dFf = last.raf - base;
  }

  // Δdirection, contre la moyenne circulaire de la fenêtre de référence.
  let dTheta = null;
  if (last.dd != null) {
    const baseDir = circularMean(samplesBetween(arr, baseFrom, baseTo, 'dd'));
    if (baseDir != null) dTheta = angDiff(last.dd, baseDir);
  }

  // ΔT — bonus seulement : par air sec la chute peut être faible alors
  // que le front est bien réel.
  let dT = null;
  if (last.temp != null) {
    const prev = valueAt(arr, jumpT, 'temp');
    if (prev != null) dT = last.temp - prev;
  }

  let score = 0;
  if (dP != null && dP >= GF_DP_HPA) score += 40;
  if (dTheta != null && Math.abs(dTheta) >= GF_DTHETA_DEG) score += 25;
  if (dFf != null && dFf >= GF_DFF_KMH) score += 25;
  if (dT != null && dT <= GF_DT_C) score += 10;

  const gust = last.raf ?? last.ff ?? 0;
  const passed = score >= GF_SCORE_MIN && gust >= GF_GUST_MIN_KMH;

  return {
    t, score, passed,
    deltaPressureHpa: dP,
    deltaSpeedKmh: dFf,
    deltaHeadingDeg: dTheta,
    deltaTempC: dT,
    gustKmh: last.raf ?? null,
  };
}

/**
 * Heure de passage du front sur une station, cherchée dans la fenêtre
 * d'épisode courante. Renvoie null si la station n'est pas exploitable
 * (muette, historique trop court) — un « pas de détection » sur une
 * station sans données n'est PAS une absence de front, et ne doit
 * jamais être compté comme telle.
 */
function gfStationPassage(id, arr, now, scoreMin = GF_SCORE_MIN) {
  if (!arr || arr.length < GF_MIN_SAMPLES) return null;
  const newest = arr[arr.length - 1];
  if (now - newest.t > GF_STATION_STALE_MS) return null;

  const from = now - GF_CLUSTER_WINDOW_MIN * 60 * 1000;
  let best = null;
  for (let i = 0; i < arr.length; i++) {
    if (arr[i].t < from) continue;
    const s = gfScoreAtSample(arr, i);
    // `scoreMin` peut être abaissé dans le couloir d'une veille modèle
    // (cf. gfDetect) : une signature partielle y est bien moins
    // susceptible d'être une coïncidence.
    const passed = s.score >= scoreMin && (s.gustKmh ?? 0) >= GF_GUST_MIN_KMH;
    if (!passed) continue;
    // Le meilleur score marque le cœur du passage ; à score égal, le
    // plus ancien (le front arrive, il ne repart pas).
    if (!best || s.score > best.score) best = s;
  }
  return best ? { id, ...best } : null;
}

// ═══════════════════════════════════════════════════════════════════
//  Étage 2 — reconstruction du front
// ═══════════════════════════════════════════════════════════════════

/** Distance approchée entre deux points (km), projection plane locale.
 *  Suffisante ici : on compare des distances à un seuil de 150 km, pas
 *  de navigation à faire. */
function gfDistKm(a, b) {
  const dLat = (b.lat - a.lat) * KM_PER_DEG_LAT;
  const dLon = (b.lon - a.lon) * KM_PER_DEG_LAT
    * Math.cos(((a.lat + b.lat) / 2 * Math.PI) / 180);
  return Math.hypot(dLat, dLon);
}

/**
 * Regroupement spatial par LIAISON SIMPLE (single-link) : deux points
 * appartiennent au même groupe s'il existe une chaîne de points
 * successivement distants de moins de `radiusKm`.
 *
 * Le choix de la liaison simple n'est pas un détail d'implémentation,
 * c'est la propriété qu'on veut : un front est un objet ALLONGÉ. Un
 * critère de compacité (k-means, diamètre maximal) couperait en deux une
 * ligne d'orages de 400 km, qui est pourtant un seul front. La liaison
 * simple, elle, suit la ligne aussi loin qu'elle se prolonge et ne
 * franchit jamais un vide de plus de `radiusKm`.
 *
 * Groupes rendus triés du plus fourni au moins fourni.
 */
function gfClusterSpatial(points, radiusKm = GF_CLUSTER_RADIUS_KM) {
  const n = points.length;
  if (n === 0) return [];
  if (!(radiusKm > 0)) return [points.slice()];

  const label = new Array(n).fill(-1);
  const groups = [];
  for (let i = 0; i < n; i++) {
    if (label[i] >= 0) continue;
    const g = groups.length;
    label[i] = g;
    const group = [points[i]];
    const queue = [i];
    while (queue.length) {
      const k = queue.pop();
      for (let j = 0; j < n; j++) {
        if (label[j] >= 0) continue;
        if (gfDistKm(points[k], points[j]) > radiusKm) continue;
        label[j] = g;
        group.push(points[j]);
        queue.push(j);
      }
    }
    groups.push(group);
  }
  return groups.sort((a, b) => b.length - a.length);
}

/**
 * Ajuste le PLAN spatio-temporel t = a + b·x + c·y sur les stations
 * franchies (moindres carrés ordinaires).
 *
 * Ce plan est plus qu'un intermédiaire de calcul : il EST le modèle du
 * front. Le gradient (b, c) est le vecteur de lenteur — sa norme donne
 * l'inverse de la vitesse de propagation, sa direction celle du
 * déplacement. Et surtout, évaluer le plan en un point quelconque donne
 * directement l'heure d'arrivée en ce point : l'ETA par balise ne
 * demande aucune géométrie supplémentaire.
 */
function fitPlane(points) {
  const n = points.length;
  let sx = 0, sy = 0, st = 0;
  for (const p of points) { sx += p.x; sy += p.y; st += p.t; }
  const mx = sx / n, my = sy / n, mt = st / n;

  let sxx = 0, sxy = 0, syy = 0, sxt = 0, syt = 0, stt = 0;
  for (const p of points) {
    const dx = p.x - mx, dy = p.y - my, dt = p.t - mt;
    sxx += dx * dx; sxy += dx * dy; syy += dy * dy;
    sxt += dx * dt; syt += dy * dt; stt += dt * dt;
  }

  const det = sxx * syy - sxy * sxy;
  // Déterminant quasi nul = stations alignées sur une droite parfaite
  // (ou confondues) : le plan est indéterminé dans la direction
  // perpendiculaire. On refuse plutôt que de rendre un résultat instable.
  if (!Number.isFinite(det) || Math.abs(det) < 1e-6) return null;

  const b = (sxt * syy - syt * sxy) / det;
  const c = (syt * sxx - sxt * sxy) / det;
  const a = mt - b * mx - c * my;

  let ssRes = 0;
  for (const p of points) {
    const pred = a + b * p.x + c * p.y;
    ssRes += (p.t - pred) ** 2;
  }
  const r2 = stt > 0 ? 1 - ssRes / stt : 0;

  return { a, b, c, r2, mx, my, mt };
}

/**
 * Reconstruit un front à partir des passages détectés.
 * `stations` : [{ id, nom, lat, lon, t, ... }] déjà filtrés « passed ».
 * Renvoie null si la géométrie n'est pas convaincante — le refus est le
 * comportement par défaut, un faux positif coûtant beaucoup plus cher
 * qu'un ratage (§8).
 */
function buildFront(stations, now, opts = {}) {
  // `anchor` : 'newest' pour la MESURE (on regarde l'épisode qui vient de
  // se produire), 'earliest' pour le MODÈLE (on regarde le prochain
  // épisode annoncé). `clusterWindowMin` : large pour le modèle, où un
  // front met ~8 h à traverser la France et où toutes ces heures
  // appartiennent bien au MÊME front — c'est justement ce que le plan
  // spatio-temporel est fait pour représenter.
  const {
    clusterWindowMin = GF_CLUSTER_WINDOW_MIN,
    anchor = 'newest',
    minPoints = GF_MIN_STATIONS,
  } = opts;

  if (stations.length < minPoints) {
    return { front: null, reason: 'not_enough_stations', count: stations.length };
  }

  const times = stations.map(s => s.t);
  const ref = anchor === 'earliest' ? Math.min(...times) : Math.max(...times);
  const used = stations.filter(s => Math.abs(s.t - ref) <= clusterWindowMin * 60 * 1000);
  if (used.length < minPoints) {
    return { front: null, reason: 'not_enough_in_window', count: used.length };
  }
  const newest = Math.max(...used.map(s => s.t));

  const lat0 = used.reduce((a, s) => a + s.lat, 0) / used.length;
  const lon0 = used.reduce((a, s) => a + s.lon, 0) / used.length;
  const proj = makeProjector(lat0, lon0);

  // Temps en minutes depuis `newest` : garde les nombres petits et
  // rend les coefficients directement lisibles (min/km).
  const pts = used.map(s => {
    const { x, y } = proj.toXY(s.lat, s.lon);
    return { x, y, t: (s.t - newest) / 60000, ref: s };
  });

  const plane = fitPlane(pts);
  if (!plane) return { front: null, reason: 'degenerate_geometry', count: used.length };
  if (plane.r2 < (opts.minR2 ?? GF_MIN_R2)) {
    return { front: null, reason: 'poor_fit', r2: plane.r2, count: used.length };
  }

  // Vecteur de lenteur (min/km) → vitesse et cap de propagation.
  const slowness = Math.hypot(plane.b, plane.c);
  if (!Number.isFinite(slowness) || slowness < 1e-9) {
    return { front: null, reason: 'no_propagation', count: used.length };
  }
  const speedKmh = (1 / slowness) * 60;
  if (speedKmh < GF_SPEED_MIN_KMH || speedKmh > GF_SPEED_MAX_KMH) {
    return { front: null, reason: 'implausible_speed', speedKmh, count: used.length };
  }

  // Direction de déplacement = sens des temps croissants. En repère
  // (x = est, y = nord), le cap géographique se lit atan2(est, nord).
  const ux = plane.b / slowness, uy = plane.c / slowness;
  const bearing = ((Math.atan2(ux, uy) * 180) / Math.PI + 360) % 360;

  return {
    front: { plane, proj, newest, speedKmh, bearing, ux, uy, used, lat0, lon0, r2: plane.r2 },
    reason: null,
    count: used.length,
  };
}

/**
 * Reconstruction MULTI-GROUPES : regroupe d'abord dans l'espace, puis
 * ajuste un plan indépendant par groupe.
 *
 * Deux orages sans rapport donnent donc deux fronts (ou aucun), jamais
 * un front moyen qui ne serait chez personne. Les groupes trop petits
 * pour un ajustement vérifiable sont rendus à part dans `orphans` : ils
 * ne sont PAS jetés silencieusement — c'est là que se trouvent les
 * noyaux de 3 stations qu'on cherche à repêcher (cf.
 * GF_RESCUE_RADIUS_KM), et c'est aussi la statistique qui dira si le
 * rayon de liaison est bien réglé.
 *
 * Rendu trié : le front le plus étayé d'abord (nombre de stations, puis
 * qualité de l'ajustement).
 */
function buildFronts(stations, now, opts = {}) {
  const minPoints = opts.minPoints ?? GF_MIN_STATIONS;
  const radiusKm = opts.clusterRadiusKm ?? GF_CLUSTER_RADIUS_KM;
  const groups = gfClusterSpatial(stations, radiusKm);

  const fronts = [];
  const orphans = [];
  const reasons = [];
  for (const g of groups) {
    if (g.length < minPoints) { orphans.push(g); continue; }
    const built = buildFront(g, now, opts);
    if (built.front) fronts.push(built.front);
    else { orphans.push(g); reasons.push(built.reason); }
  }
  fronts.sort((a, b) => (b.used.length - a.used.length) || (b.r2 - a.r2));

  // `scattered` est un motif de silence À PART ENTIÈRE, distinct de
  // `not_enough_stations` : il dit qu'il y avait bien assez de stations
  // franchies, mais qu'aucune ne formait un ensemble cohérent. Les
  // confondre masquerait exactement le défaut qu'on vient de corriger.
  const reason = fronts.length ? null
    : (reasons[0] ?? (groups.length > 1 ? 'scattered' : 'not_enough_stations'));

  return { fronts, orphans, groups: groups.length, reason };
}

/**
 * Heure d'arrivée estimée (epoch ms) du front en un point, par
 * évaluation du plan ajusté. `publicationLatencyMs` (§3.2 de la spec)
 * est ajoutée telle quelle : la latence entre la mesure et sa
 * disponibilité API se soustrait directement du préavis réel, l'ignorer
 * reviendrait à promettre un préavis qu'on n'a pas.
 */
function etaAt(front, lat, lon, publicationLatencyMs = 0) {
  const { x, y } = front.proj.toXY(lat, lon);
  const tMin = front.plane.a + front.plane.b * x + front.plane.c * y;
  return front.newest + tMin * 60000 + publicationLatencyMs;
}

/**
 * Ligne de front à un instant donné : segment de la droite d'iso-temps,
 * borné par l'emprise latérale des stations franchies (+ marge).
 */
function frontLineAt(front, tMs) {
  const { plane, proj, ux, uy } = front;
  const tMin = (tMs - front.newest) / 60000;

  // Point de la droite d'iso-temps le plus proche du barycentre : on
  // part du barycentre et on avance le long de la propagation de la
  // distance qui correspond à l'écart de temps demandé.
  const slowness = Math.hypot(plane.b, plane.c);
  const cx = plane.mx, cy = plane.my;
  const tHere = plane.a + plane.b * cx + plane.c * cy;
  const shiftKm = (tMin - tHere) / slowness;
  const px = cx + ux * shiftKm;
  const py = cy + uy * shiftKm;

  // Perpendiculaire à la direction de propagation.
  const vx = -uy, vy = ux;
  let minS = Infinity, maxS = -Infinity;
  for (const p of front.used) {
    const { x, y } = proj.toXY(p.lat, p.lon);
    const s = (x - cx) * vx + (y - cy) * vy;
    if (s < minS) minS = s;
    if (s > maxS) maxS = s;
  }
  minS -= GF_CORRIDOR_MARGIN_KM;
  maxS += GF_CORRIDOR_MARGIN_KM;

  const A = proj.toLatLon(px + vx * minS, py + vy * minS);
  const B = proj.toLatLon(px + vx * maxS, py + vy * maxS);
  return { a: A, b: B, minS, maxS, px, py, vx, vy };
}

/**
 * Couloir d'impact : la ligne de front actuelle extrudée le long du
 * vecteur de propagation sur GF_CORRIDOR_HOURS. C'est ce polygone qui
 * décide QUI est prévenu (§5.4) — donc il est volontairement borné dans
 * le temps : au-delà de 3 h, l'extrapolation d'un outflow n'a plus de
 * sens physique et prévenir un pilote à 400 km serait du bruit.
 */
function corridorPolygon(front, nowMs) {
  const now = frontLineAt(front, nowMs);
  const later = frontLineAt(front, nowMs + GF_CORRIDOR_HOURS * 3600 * 1000);
  return [
    [now.a.lon, now.a.lat],
    [now.b.lon, now.b.lat],
    [later.b.lon, later.b.lat],
    [later.a.lon, later.a.lat],
    [now.a.lon, now.a.lat],
  ];
}

/** Test point-dans-polygone (ray casting) sur un anneau [lon, lat]. */
function pointInRing(lon, lat, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0], yi = ring[i][1];
    const xj = ring[j][0], yj = ring[j][1];
    const hit = (yi > lat) !== (yj > lat) &&
      lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi;
    if (hit) inside = !inside;
  }
  return inside;
}

/**
 * Confiance 0–100. Volontairement conservatrice : elle plafonne à 95,
 * parce qu'une mesure de réseau reste une inférence sur ce qui va se
 * passer ailleurs et plus tard, jamais une certitude.
 */
function confidenceOf(front, stationCount) {
  const nScore = Math.min(1, (stationCount - GF_MIN_STATIONS) / 8);
  const r2Score = Math.max(0, Math.min(1, (front.r2 - GF_MIN_R2) / (1 - GF_MIN_R2)));
  const raw = 45 + 25 * nScore + 25 * r2Score;
  return Math.round(Math.max(0, Math.min(95, raw)));
}

// ═══════════════════════════════════════════════════════════════════
//  Point d'entrée
// ═══════════════════════════════════════════════════════════════════

/**
 * Passe complète de détection.
 *
 * @param {Map<string,{lat:number,lon:number,nom?:string}>} stationMeta
 * @param {number} now epoch ms
 * @param {number} publicationLatencyMs latence de publication MF mesurée
 * @returns {{front:object|null, detections:Array, reason:string|null, evaluated:number}}
 */
function gfDetect(stationMeta, now, publicationLatencyMs = 0, opts = {}) {
  const detections = [];
  let evaluated = 0;
  let loweredCount = 0;

  // `priorCorridor` : le couloir d'une veille modèle en cours. À
  // l'intérieur, on abaisse le seuil de passage.
  //
  // C'est la vraie valeur du Lot A, et elle n'est pas d'« activer » quoi
  // que ce soit : le réseau est déjà interrogé en continu. Elle est de
  // fournir un A PRIORI. Dans un couloir et une fenêtre annoncés, deux
  // signaux concordants sur une station sont bien moins susceptibles
  // d'être une coïncidence qu'ailleurs — on peut donc y être plus
  // sensible sans devenir crédule partout.
  const prior = typeof opts.priorCorridor === 'function' ? opts.priorCorridor : null;
  const loweredMin = opts.priorScoreMin ?? GF_SCORE_MIN_PRIOR;

  for (const [id, arr] of gfHistory) {
    const meta = stationMeta.get(id);
    // Sans coordonnées valides, une détection ne peut entrer dans aucun
    // calcul géométrique — écartée, comme le veut le §4.2.
    if (!meta || !Number.isFinite(meta.lat) || !Number.isFinite(meta.lon)) continue;
    evaluated++;
    let scoreMin = GF_SCORE_MIN;
    if (prior && prior(meta.lat, meta.lon)) { scoreMin = loweredMin; loweredCount++; }
    const s = gfStationPassage(id, arr, now, scoreMin);
    if (s) detections.push({ ...s, lat: meta.lat, lon: meta.lon, nom: meta.nom || id });
  }

  // ── Repêchage local (31/08/2026) ─────────────────────────────────
  // Un noyau de 3 stations cohérentes est une information, pas du
  // bruit : c'est simplement un point de trop peu pour qu'un plan soit
  // vérifiable. Plutôt que de le jeter — ou pire, de le compléter avec
  // la première station franchie à 400 km, ce que faisait l'ancien
  // regroupement purement temporel — on relit son VOISINAGE au seuil
  // abaissé. Même raisonnement que le couloir d'une veille modèle.
  const rescued = gfRescueNeighbours(detections, stationMeta, now, opts);
  for (const r of rescued) detections.push(r);

  const built = buildFronts(detections, now, opts);
  if (!built.fronts.length) {
    return {
      front: null, fronts: [], detections, reason: built.reason, evaluated,
      loweredCount, rescuedCount: rescued.length,
      groupCount: built.groups, orphanCount: built.orphans.length,
    };
  }

  const fronts = built.fronts.map(f => packMeasuredFront(f, now, publicationLatencyMs));

  return {
    // `front` reste le front le plus étayé : les appelants qui n'en
    // traitent qu'un seul gardent le comportement le plus défendable.
    front: fronts[0],
    fronts,
    detections: built.fronts[0].used,
    reason: null,
    evaluated,
    loweredCount,
    rescuedCount: rescued.length,
    groupCount: built.groups,
    orphanCount: built.orphans.length,
  };
}

/**
 * Relit les stations VOISINES d'un noyau incomplet, au seuil abaissé.
 *
 * Ne s'applique qu'aux groupes qui ont déjà GF_RESCUE_MIN_CORE stations
 * franchies au seuil plein et qui n'atteignent pas le minimum : ailleurs,
 * abaisser le seuil serait de la crédulité pure. Ici, l'a priori est
 * local et daté — trois stations à moins de 150 km les unes des autres
 * viennent de montrer une signature franche dans la même fenêtre de
 * 90 min — et c'est exactement la situation où une signature partielle
 * chez le voisin cesse d'être une coïncidence plausible.
 *
 * Les stations ainsi récupérées sont marquées `rescued: true` : elles
 * pèsent sur la confiance (cf. packMeasuredFront) et restent traçables.
 */
function gfRescueNeighbours(detections, stationMeta, now, opts = {}) {
  if (!detections.length) return [];
  const radiusKm = opts.rescueRadiusKm ?? GF_RESCUE_RADIUS_KM;
  const minCore = opts.rescueMinCore ?? GF_RESCUE_MIN_CORE;
  const minPoints = opts.minPoints ?? GF_MIN_STATIONS;
  const scoreMin = opts.rescueScoreMin ?? GF_SCORE_MIN_PRIOR;
  if (!(radiusKm > 0) || minCore >= minPoints) return [];

  const cores = gfClusterSpatial(detections, opts.clusterRadiusKm ?? GF_CLUSTER_RADIUS_KM)
    .filter(g => g.length >= minCore && g.length < minPoints);
  if (!cores.length) return [];

  const known = new Set(detections.map(d => d.id));
  const found = [];
  for (const [id, arr] of gfHistory) {
    if (known.has(id)) continue;
    const meta = stationMeta.get(id);
    if (!meta || !Number.isFinite(meta.lat) || !Number.isFinite(meta.lon)) continue;
    if (!cores.some(g => g.some(p => gfDistKm(p, meta) <= radiusKm))) continue;
    const s = gfStationPassage(id, arr, now, scoreMin);
    if (!s) continue;
    known.add(id);
    found.push({ ...s, lat: meta.lat, lon: meta.lon, nom: meta.nom || id, rescued: true });
  }
  return found;
}

/** Met un front mesuré reconstruit sous la forme attendue par index.js. */
function packMeasuredFront(f, now, publicationLatencyMs = 0) {
  const maxGust = Math.max(...f.used.map(s => s.gustKmh || 0));
  const maxJump = Math.max(...f.used.map(s => s.deltaPressureHpa || 0));
  // Calculé UNE fois : `contains` est appelé une fois par balise
  // favorite de chaque compte, recalculer le polygone à chaque appel
  // serait gratuit en résultat et coûteux en CPU sur le poll.
  const ring = corridorPolygon(f, now);
  const rescuedCount = f.used.filter(s => s.rescued).length;

  return {
    speedKmh: f.speedKmh,
    bearing: f.bearing,
    // Un front qui ne tient debout que grâce à des stations repêchées au
    // seuil abaissé est réel, mais moins établi : −8 par station
    // repêchée. On ne cache pas d'où vient le quatrième point.
    confidence: Math.max(40, confidenceOf(f, f.used.length) - 8 * rescuedCount),
    stationCount: f.used.length,
    rescuedCount,
    spanKm: f.used.reduce((m, a) => Math.max(
      m, ...f.used.map(b => gfDistKm(a, b))), 0),
    r2: f.r2,
    maxGustKmh: Number.isFinite(maxGust) ? maxGust : null,
    maxPressureJumpHpa: Number.isFinite(maxJump) ? maxJump : null,
    line: frontLineAt(f, now),
    corridor: ring,
    // Positions successives à +30 / +60 / +90 min — la carte les
    // affiche en traits atténués (§5.2) : c'est ce qui permet au
    // pilote de voir venir, plutôt que de lire une heure abstraite.
    forecastLines: [30, 60, 90].map(min => ({
      offsetMin: min,
      line: frontLineAt(f, now + min * 60000),
    })),
    thresholdsVersion: GF_THRESHOLDS_VERSION,
    publicationLatencyMs,
    detections: f.used,
    // Conservé pour permettre à index.js de calculer les ETA sans
    // refaire de géométrie.
    _internal: f,
    etaFor: (lat, lon) => etaAt(f, lat, lon, publicationLatencyMs),
    contains: (lat, lon) => pointInRing(lon, lat, ring),
  };
}

// ═══════════════════════════════════════════════════════════════════
//  LOT A — veille sur le MODÈLE (AROME)
//
//  Même charpente que la détection sur mesure, appliquée à une grille de
//  prévision : on cherche, en chaque point de grille, l'échéance à
//  laquelle la signature de front apparaît, puis on ajuste le MÊME plan
//  spatio-temporel. Le modèle et la mesure produisent donc des objets de
//  même nature, ce qui rend la fusion (§4.4) triviale.
//
//  Ce que le Lot A apporte, et qu'il n'apporte PAS. Il apporte du
//  préavis : 3 à 24 h au lieu de 1 à 3 h. Il n'apporte PAS de certitude —
//  AROME se trompe couramment d'une à deux heures sur le déclenchement
//  convectif. C'est pourquoi un événement issu du modèle reste au statut
//  `watch` et ne déclenche AUCUN push : bandeau in-app seulement. Le push
//  est réservé au front mesuré.
// ═══════════════════════════════════════════════════════════════════

/** Seuils modèle (§4.1) — distincts de ceux de la mesure, et pour cause :
 *  une maille de 28 km lisse les extrêmes, un seuil calé sur une station
 *  ponctuelle n'y déclencherait jamais. */
const GF_MODEL_DV_KMH = 15;       // saut de vent moyen
const GF_MODEL_DTHETA_DEG = 40;   // bascule de direction
const GF_MODEL_GUST_KMH = 45;     // rafale prévue
const GF_MODEL_DP_HPA = 0.8;      // bonus : saut de pression horaire
const GF_MODEL_DT_C = -2.0;       // bonus : chute de température
/** Une ligne de front sur grille, c'est beaucoup de points — en exiger
 *  peu ne coûte rien et exclut le bruit isolé. */
const GF_MODEL_MIN_POINTS = 12;
/** Un front met ~8 h à traverser la France : la fenêtre de regroupement
 *  doit couvrir ça, sans quoi on découperait un seul front en morceaux. */
const GF_MODEL_CLUSTER_MIN = 12 * 60;
/** Rayon de liaison spatiale sur la grille (31/08/2026). La grille est
 *  au pas de 0,25° (~28 km en latitude, ~19 km en longitude à 46°N) :
 *  100 km tolère donc un trou de 3 à 5 mailles. Un front réel — même un
 *  front froid synoptique de 1 500 km — est une ligne CONTINUE de points
 *  déclenchés, il reste un seul groupe. Deux foyers convectifs séparés
 *  par 300 km de rien ne sont plus ajustés par le même plan : c'est
 *  exactement ce qui produisait les veilles de 1 500 km d'axe relevées
 *  en base entre le 31/07 et le 30/08/2026. */
const GF_MODEL_CLUSTER_RADIUS_KM = 100;
/** Garde-fou convectif (§4.1) : sans instabilité ni pluie, ce n'est pas
 *  un outflow d'orage mais probablement un front froid synoptique. */
const GF_MODEL_CAPE_MIN = 300;
const GF_MODEL_PRECIP_MIN = 1.0;
/** Au-delà, l'incertitude sur le déclenchement rend l'ETA inexploitable. */
const GF_MODEL_HORIZON_H = 24;

function med3(a, b, c) {
  const v = [a, b, c].filter(x => x != null);
  return v.length ? median(v) : null;
}

/**
 * Cherche, pour chaque point de grille, la PREMIÈRE échéance à venir où
 * la signature de front apparaît.
 *
 * @param {{lats:number[],lons:number[],times:string[],vars:object}} grid
 * @param {number} now epoch ms
 */
function gfDetectModel(grid, now, opts = {}) {
  if (!grid || !Array.isArray(grid.times) || !grid.times.length) {
    return { front: null, reason: 'no_grid', candidates: [] };
  }
  // ⚠️ ÉTAPE 10 du lot H — le verrou rafale est un SEUIL, pas une donnée.
  // Il est surchargeable parce que la rafale n'existe QU'À 10 m (mesuré,
  // partout) : rejouer ce détecteur sur le vent à 1 000 m/sol demande de
  // pouvoir dire « ne me bloque pas sur un champ que ce niveau ne porte
  // pas ». Le défaut est INCHANGÉ et aucun appelant de production ne
  // passe `opts` ; `tools/gust-front-model-selftest.js` le vérifie.
  const gustMin = opts.gustMinKmh ?? GF_MODEL_GUST_KMH;
  // ⚠️ ET LE MÊME RAISONNEMENT POUR LE SAUT DE VENT, qui est le piège de
  // l'étape 10 : à 1 000 m/sol le vent est plus fort qu'à 10 m, donc un
  // seuil ABSOLU de 15 km/h s'y franchit plus souvent — à organisation
  // du champ strictement identique. Sans pouvoir balayer ce seuil, on
  // lirait « le signal est plus propre en altitude » là où il n'y aurait
  // que « le vent y est plus fort ». C'est la leçon de l'étape 7, écart
  // ABSOLU contre écart RELATIF, appliquée ici.
  const dvMin = opts.dvMinKmh ?? GF_MODEL_DV_KMH;
  const dthetaMin = opts.dthetaMinDeg ?? GF_MODEL_DTHETA_DEG;
  const { lats, lons, times, vars } = grid;
  const nLon = lons.length;
  const stepMs = times.map(t => Date.parse(t));
  const horizon = now + GF_MODEL_HORIZON_H * 3600 * 1000;

  // ⚠️ Correction du BIAIS DE QUANTIFICATION, trouvée à l'auto-test :
  // sans elle, l'ETA modèle sortait systématiquement ~34 min trop tard.
  //
  // Le modèle est horaire. On retient, pour chaque point, la PREMIÈRE
  // échéance où la signature apparaît — mais le front y est en réalité
  // passé à un instant quelconque de l'heure PRÉCÉDENTE. Chaque point est
  // donc en retard d'une demi-heure en moyenne, et comme tous le sont de
  // la même façon, ça ne se voit pas dans le R² : l'ajustement est
  // excellent, simplement décalé en bloc.
  //
  // C'est un biais, pas du bruit : il se corrige en retranchant une
  // demi-échéance. Ce qui reste ensuite est de l'incertitude vraie.
  const stepIntervalMs = stepMs.length > 1 && Number.isFinite(stepMs[1] - stepMs[0])
    ? stepMs[1] - stepMs[0]
    : 3600 * 1000;
  const quantBiasMs = stepIntervalMs / 2;

  const candidates = [];
  const nPts = lats.length * lons.length;

  for (let k = 0; k < nPts; k++) {
    for (let s = 3; s < times.length; s++) {
      const tMs = stepMs[s];
      // On ne s'intéresse qu'à ce qui est ENCORE À VENIR : une échéance
      // déjà passée relève de la mesure, qui est plus fiable.
      if (!Number.isFinite(tMs) || tMs <= now || tMs > horizon) continue;

      const spd = vars.spd[s]?.[k];
      const dir = vars.dir[s]?.[k];
      const gust = vars.gust[s]?.[k];
      if (spd == null || dir == null || gust == null) continue;
      if (gust < gustMin) continue;

      const base = med3(vars.spd[s - 1]?.[k], vars.spd[s - 2]?.[k], vars.spd[s - 3]?.[k]);
      const prevDir = vars.dir[s - 1]?.[k];
      if (base == null || prevDir == null) continue;

      const dV = spd - base;
      const dTheta = angDiff(dir, prevDir);
      if (dV < dvMin || Math.abs(dTheta) < dthetaMin) continue;

      // Bonus non bloquants — ils ne conditionnent pas la détection, ils
      // renseignent la confiance et le typage.
      const p = vars.pres[s]?.[k], pPrev = vars.pres[s - 1]?.[k];
      const dP = (p != null && pPrev != null) ? p - pPrev : null;
      const tC = vars.temp[s]?.[k], tPrev = vars.temp[s - 1]?.[k];
      const dT = (tC != null && tPrev != null) ? tC - tPrev : null;

      // Garde-fou convectif évalué SUR PLACE, dans les 4 h précédentes.
      let convective = false;
      for (let b = Math.max(0, s - 4); b <= s; b++) {
        if ((vars.cape[b]?.[k] ?? 0) >= GF_MODEL_CAPE_MIN) { convective = true; break; }
        if ((vars.precip[b]?.[k] ?? 0) >= GF_MODEL_PRECIP_MIN) { convective = true; break; }
      }

      candidates.push({
        id: `g${k}`,
        nom: null,
        lat: lats[Math.floor(k / nLon)],
        lon: lons[k % nLon],
        t: tMs - quantBiasMs,   // cf. correction du biais de quantification
        score: 100,
        gustKmh: gust,
        deltaSpeedKmh: dV,
        deltaHeadingDeg: dTheta,
        deltaPressureHpa: dP,
        deltaTempC: dT,
        convective,
      });
      break; // première échéance concernée pour ce point, on passe au suivant
    }
  }

  const built = buildFronts(candidates, now, {
    clusterWindowMin: GF_MODEL_CLUSTER_MIN,
    anchor: 'earliest',
    minPoints: GF_MODEL_MIN_POINTS,
    clusterRadiusKm: opts.clusterRadiusKm ?? GF_MODEL_CLUSTER_RADIUS_KM,
  });
  if (!built.fronts.length) {
    // `r2` est remonté même en échec : c'est LE chiffre que l'étape 10
    // compare d'un niveau à l'autre, et un `poor_fit` sans son R² ne dit
    // pas si le fit a raté de peu ou de tout. Le plus gros groupe est
    // rejoué SANS regroupement pour que ce R² reste comparable d'une
    // campagne à l'autre — il documente le refus, il ne l'annule pas.
    const biggest = built.orphans[0] || candidates;
    const probe = buildFront(biggest, now, {
      clusterWindowMin: GF_MODEL_CLUSTER_MIN,
      anchor: 'earliest',
      minPoints: 4,
    });
    return { front: null, fronts: [], reason: built.reason, candidates,
             count: probe.count ?? built.orphans.length,
             r2: probe.front ? probe.front.r2 : (probe.r2 ?? null),
             groupCount: built.groups };
  }

  const fronts = built.fronts.map(f => packModelFront(f, now));
  return {
    // Comme pour la mesure : `front` reste la veille la plus étayée,
    // `fronts` porte toutes celles qui tiennent debout séparément.
    front: fronts[0],
    fronts,
    candidates: built.fronts[0].used,
    reason: null,
    groupCount: built.groups,
    orphanCount: built.orphans.length,
  };
}

/** Met une veille modèle reconstruite sous la forme attendue par index.js. */
function packModelFront(f, now) {
  const maxGust = Math.max(...f.used.map(s => s.gustKmh || 0));
  const convectiveShare = f.used.filter(s => s.convective).length / f.used.length;
  // Typage : si la majorité des points franchis n'a ni instabilité ni
  // pluie en amont, c'est un front froid synoptique — réel, mais plus
  // lent, annoncé de longue date, et nettement moins piégeux qu'un
  // outflow. Le libellé et l'urgence en dépendent (§4.1).
  const kind = convectiveShare >= 0.5 ? 'outflow' : 'synoptique';

  const ring = corridorPolygon(f, now);
  return {
    speedKmh: f.speedKmh,
    bearing: f.bearing,
    // Confiance plafonnée : c'est une PRÉVISION. Même parfaitement
    // ajustée, elle ne peut pas prétendre au même crédit qu'une mesure.
    confidence: Math.min(60, confidenceOf(f, f.used.length)),
    stationCount: f.used.length,
    spanKm: f.used.reduce((m, a) => Math.max(
      m, ...f.used.map(b => gfDistKm(a, b))), 0),
    r2: f.r2,
    kind,
    maxGustKmh: Number.isFinite(maxGust) ? maxGust : null,
    maxPressureJumpHpa: null,
    line: frontLineAt(f, now),
    corridor: ring,
    forecastLines: [60, 120, 180].map(min => ({
      offsetMin: min,
      line: frontLineAt(f, now + min * 60000),
    })),
    thresholdsVersion: GF_THRESHOLDS_VERSION,
    detections: f.used,
    _internal: f,
    etaFor: (lat, lon) => etaAt(f, lat, lon, 0),
    contains: (lat, lon) => pointInRing(lon, lat, ring),
  };
}

// ═══════════════════════════════════════════════════════════════════
//  LOT 3 — COMPTABILITÉ PRÉVU ↔ MESURÉ (31/08/2026)
//
//  Question Yann : « combien de fronts qui ont été prévus par les
//  modèles se sont passés, et combien de fronts qui ont été mesurés
//  avaient été prévus ? »
//
//  Deux taux, et ils ne sont PAS l'inverse l'un de l'autre :
//   · RÉALISATION  — annoncés qui ont été mesurés / annoncés. Mesure les
//     fausses alertes du modèle.
//   · ANTICIPATION — mesurés qui avaient été annoncés / mesurés. Mesure
//     les fronts que le modèle n'a pas vus venir.
//  Un détecteur peut être excellent sur l'un et mauvais sur l'autre.
//
//  ⚠️ Tout ce qui suit est PUR : aucune I/O, aucune notion de Supabase.
//  C'est délibéré, et ce n'est pas de l'esthétique — l'appariement était
//  jusqu'ici implicite, fait en RAM par `gfActiveEvent`, donc perdu à
//  chaque redémarrage du free tier Render et invérifiable. Écrit ici, il
//  se rejoue sur l'archive et se teste sans base.
// ═══════════════════════════════════════════════════════════════════

/** Deux segments [p1,p2] et [p3,p4] se croisent-ils ? */
function segmentsCroisent(p1, p2, p3, p4) {
  const d = (a, b, c) => (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
  const d1 = d(p3, p4, p1), d2 = d(p3, p4, p2);
  const d3 = d(p1, p2, p3), d4 = d(p1, p2, p4);
  return ((d1 > 0) !== (d2 > 0)) && ((d3 > 0) !== (d4 > 0));
}

/**
 * Deux couloirs se recouvrent-ils ?
 *
 * Test exact pour des polygones simples, et non un échantillonnage :
 * un sommet de l'un dans l'autre, ou deux arêtes qui se croisent. Un
 * échantillonnage raterait le cas où deux couloirs se croisent en X sans
 * qu'aucun sommet ne tombe dans l'autre — c'est-à-dire exactement la
 * situation d'un front annoncé et d'un front mesuré qui se rejoignent
 * perpendiculairement, celle qu'on cherche à reconnaître.
 */
function gfRingsOverlap(a, b) {
  if (!Array.isArray(a) || !Array.isArray(b) || a.length < 3 || b.length < 3) return false;
  for (const [x, y] of a) if (pointInRing(x, y, b)) return true;
  for (const [x, y] of b) if (pointInRing(x, y, a)) return true;
  for (let i = 0; i < a.length; i++) {
    const a1 = a[i], a2 = a[(i + 1) % a.length];
    for (let j = 0; j < b.length; j++) {
      if (segmentsCroisent(a1, a2, b[j], b[(j + 1) % b.length])) return true;
    }
  }
  return false;
}

// ── Rattachement d'un front à un épisode déjà suivi (31/08/2026) ────
//  Le serveur peut suivre plusieurs épisodes à la fois depuis la levée
//  du singleton `gfActiveEvent`. À chaque cycle il faut donc décider, pour
//  chaque front reconstruit, s'il PROLONGE un épisode existant ou s'il en
//  ouvre un nouveau.
//
//  Pur, et rangé ici et non dans index.js, pour deux raisons : c'est
//  testable sans base, et surtout c'est LE MÊME test de recouvrement que
//  celui de la comptabilité (`gfRingsOverlap`). Deux façons différentes
//  de décider « est-ce le même front ? » finiraient par diverger, et
//  l'écart se lirait comme une incohérence des chiffres.

/** Centre approximatif d'un anneau — départage deux épisodes qui
 *  recouvrent tous les deux le front qu'on cherche à rattacher. */
function gfRingCenter(ring) {
  if (!Array.isArray(ring) || !ring.length) return null;
  let x = 0, y = 0;
  for (const [lon, lat] of ring) { x += lon; y += lat; }
  return { lon: x / ring.length, lat: y / ring.length };
}

/**
 * L'épisode de `episodes` que ce couloir prolonge, ou null.
 *
 * Rattachement par RECOUVREMENT DES COULOIRS, et non par proximité d'un
 * point : un front est une ligne qui avance, sa géométrie à t et à
 * t+6 min se recouvre largement alors que son barycentre s'est déplacé
 * de plusieurs kilomètres. Comparer des centres perdrait le suivi d'un
 * front rapide, et le couperait en deux épisodes.
 *
 * `claimed` : les épisodes déjà rattachés à un autre front DU MÊME
 * CYCLE. Sans ce jeu, deux fronts voisins pourraient revendiquer le même
 * épisode et se réécrire l'un l'autre — le défaut du singleton, en plus
 * petit.
 */
function gfPickEpisodeFrom(episodes, ring, opts = {}) {
  const claimed = opts.claimed ?? new Set();
  const filtre = opts.filter ?? null;
  const centre = gfRingCenter(ring);
  let best = null, bestDist = Infinity;
  for (const ep of episodes || []) {
    if (!ep || claimed.has(ep.id)) continue;
    if (filtre && !filtre(ep)) continue;
    if (!gfRingsOverlap(ring, ep.corridor)) continue;
    const c = gfRingCenter(ep.corridor);
    const d = (centre && c) ? Math.hypot(centre.lon - c.lon, centre.lat - c.lat) : 0;
    if (d < bestDist) { best = ep; bestDist = d; }
  }
  return best;
}

/** Un épisode issu (au moins en partie) d'une annonce modèle. */
function gfEstAnnonce(e) { return e.source === 'model' || e.source === 'merged'; }
/** Un épisode réellement observé par un réseau de mesure. */
function gfEstMesure(e) {
  return e.source === 'mf_network' || e.source === 'merged' || e.source === 'pioupiou';
}

/**
 * Tolérance sur le calage horaire, dans les deux sens.
 *
 * 2 h, et ce n'est pas un réglage libre : c'est le chiffre que la spec
 * du Lot A écrit déjà noir sur blanc (« AROME se trompe couramment d'une
 * à deux heures sur le déclenchement convectif »), et c'est la raison
 * pour laquelle une veille modèle ne déclenche AUCUN push. Apparier plus
 * serré reviendrait à compter comme « non réalisé » un front qui s'est
 * bel et bien produit, avec le retard qu'on savait d'avance.
 */
const GF_MATCH_TOLERANCE_MS = 2 * 60 * 60 * 1000;

/** Fenêtre pendant laquelle un épisode peut être apparié. */
function gfFenetre(e, toleranceMs) {
  const t = v => (v == null ? null : (typeof v === 'number' ? v : Date.parse(v)));
  const debuts = [t(e.eta_start), t(e.created_at)].filter(Number.isFinite);
  const fins = [t(e.eta_end), t(e.updated_at)].filter(Number.isFinite);
  if (!debuts.length || !fins.length) return null;
  return [Math.min(...debuts) - toleranceMs, Math.max(...fins) + toleranceMs];
}

/**
 * Apparie les épisodes ANNONCÉS et MESURÉS, et rend le verdict de
 * chacun. Fonction pure : on lui donne des épisodes, elle rend la liste
 * des changements à écrire.
 *
 * Vocabulaire du verdict, volontairement unique pour les deux
 * populations — `realise` veut TOUJOURS dire « l'annonce et la mesure se
 * sont rejointes » :
 *  · `realise`     — annoncé puis mesuré (des deux côtés de la paire) ;
 *  · `non_realise` — annoncé, jamais mesuré → fausse alerte du modèle ;
 *  · `non_prevu`   — mesuré sans annonce → le modèle ne l'a pas vu venir.
 *
 * Un épisode `merged` est les deux à la fois : il a été promu sur place,
 * l'appariement n'a rien à retrouver.
 *
 * ⚠️ Les épisodes MANUELS sont écartés : ce sont des saisies humaines,
 * pas des sorties de détecteur. Les compter fausserait les deux taux —
 * dans le sens flatteur, en plus.
 */
function gfMatchEpisodes(events, opts = {}) {
  const tol = opts.toleranceMs ?? GF_MATCH_TOLERANCE_MS;
  const clos = new Set(opts.closedStatuses ?? ['passed', 'expired', 'cancelled']);

  const utiles = (events || []).filter(e => e && !e.is_manual && e.source !== 'manual');
  const annonces = utiles.filter(gfEstAnnonce);
  const mesures = utiles.filter(gfEstMesure);

  const updates = new Map();
  const poser = (id, champs) => {
    updates.set(id, { ...(updates.get(id) || { id }), ...champs });
  };

  for (const a of annonces) {
    // Un épisode encore vivant n'a pas de verdict : le rendre
    // maintenant serait faux une fois sur deux.
    if (!clos.has(a.status)) continue;

    if (a.source === 'merged') {
      // Promu sur place : l'annonce et la mesure sont la même ligne.
      poser(a.id, { verdict: 'realise', announced_event_id: a.id });
      continue;
    }

    const fa = gfFenetre(a, tol);
    const debutA = Date.parse(a.created_at);
    const trouve = fa && mesures.find(m => {
      if (m.id === a.id) return false;
      const fm = gfFenetre(m, 0);
      if (!fm) return false;
      // ⚠️ UNE PRÉVISION PARLE AVANT. Trouvé en rejouant les 48 épisodes
      // du 31/07 au 30/08 : sans cette ligne, une veille écrite à 00:05
      // était comptée comme la « réalisation » d'un front mesuré à
      // 19:41 la veille — parce que les deux fenêtres, élargies de ±2 h,
      // finissaient par se toucher. Un modèle qui annonce ce que le
      // réseau a déjà vu n'a rien anticipé du tout, et le compter
      // gonflerait le taux de réalisation dans le sens flatteur.
      // Contrainte volontairement stricte : elle ne peut que baisser les
      // deux taux, jamais les monter.
      if (!(debutA < Date.parse(m.created_at))) return false;
      // Recouvrement des fenêtres, puis des géométries. L'ordre compte :
      // le test temporel est deux comparaisons, le test géométrique est
      // quadratique sur les sommets.
      if (fm[1] < fa[0] || fm[0] > fa[1]) return false;
      return gfRingsOverlap(a.corridor, m.corridor);
    });

    if (trouve) {
      poser(a.id, { verdict: 'realise' });
      // Le lien va du MESURÉ vers l'ANNONCÉ : c'est le sens qui permet
      // de répondre « ce front, l'avait-on vu venir ? » sans jointure
      // inverse.
      poser(trouve.id, { verdict: 'realise', announced_event_id: a.id });
    } else {
      poser(a.id, { verdict: 'non_realise' });
    }
  }

  for (const m of mesures) {
    if (!clos.has(m.status)) continue;
    if (m.source === 'merged') continue;              // déjà traité ci-dessus
    if (updates.has(m.id)) continue;                  // apparié à l'instant
    if (m.announced_event_id) {                       // apparié lors d'un passage précédent
      poser(m.id, { verdict: 'realise' });
      continue;
    }
    poser(m.id, { verdict: 'non_prevu' });
  }

  // On ne réécrit que ce qui change réellement : la réconciliation
  // tourne en boucle, et repatcher 500 lignes identiques toutes les
  // heures serait du bruit en base comme dans les journaux.
  const avant = new Map(utiles.map(e => [e.id, e]));
  return [...updates.values()].filter(u => {
    const e = avant.get(u.id);
    if (!e) return false;
    const memeVerdict = e.verdict === u.verdict;
    const memeLien = u.announced_event_id === undefined
      || e.announced_event_id === u.announced_event_id;
    return !(memeVerdict && memeLien);
  });
}

/**
 * Les deux taux, calculés sur une liste d'épisodes déjà jugés.
 *
 * Rend les EFFECTIFS avec les taux, et jamais un pourcentage seul :
 * « 22 % » sur 18 épisodes et « 22 % » sur 1 800 ne se lisent pas de la
 * même façon, et le premier ne se lit pas du tout.
 */
function gfVerificationRates(events) {
  const utiles = (events || []).filter(e => e && !e.is_manual && e.source !== 'manual');

  const annonces = utiles.filter(e => gfEstAnnonce(e) && e.verdict);
  const realises = annonces.filter(e => e.verdict === 'realise');

  const mesures = utiles.filter(e => gfEstMesure(e) && e.verdict);
  const anticipes = mesures.filter(e => e.announced_event_id);

  const taux = (n, d) => (d ? Math.round((n / d) * 1000) / 10 : null);

  // Préavis réellement offert : de l'annonce à la première confirmation.
  const preavis = utiles
    .map(e => {
      if (!e.confirmed_at || !e.created_at) return null;
      const c = typeof e.created_at === 'number' ? e.created_at : Date.parse(e.created_at);
      const k = typeof e.confirmed_at === 'number' ? e.confirmed_at : Date.parse(e.confirmed_at);
      const min = Math.round((k - c) / 60000);
      return Number.isFinite(min) && min >= 0 ? min : null;
    })
    .filter(v => v != null)
    .sort((a, b) => a - b);

  return {
    announced: { total: annonces.length, realised: realises.length,
                 rate: taux(realises.length, annonces.length) },
    measured: { total: mesures.length, anticipated: anticipes.length,
                rate: taux(anticipes.length, mesures.length) },
    leadTimeMin: {
      count: preavis.length,
      median: preavis.length ? preavis[Math.floor(preavis.length / 2)] : null,
      max: preavis.length ? preavis[preavis.length - 1] : null,
    },
    /** Épisodes clos pas encore jugés — non nul durablement = la
     *  réconciliation ne tourne pas. */
    pending: utiles.filter(e => !e.verdict
      && ['passed', 'expired', 'cancelled'].includes(e.status)).length,
  };
}

/** État de santé du détecteur — consommé par /gust-front/health. */
function gfHealth(now = Date.now()) {
  let samples = 0, newest = 0;
  for (const arr of gfHistory.values()) {
    samples += arr.length;
    if (arr.length && arr[arr.length - 1].t > newest) newest = arr[arr.length - 1].t;
  }
  const spanMs = gfFirstSampleAt ? now - gfFirstSampleAt : 0;
  return {
    stations: gfHistory.size,
    samples,
    lastSampleAt: newest || null,
    lastSampleAgeMin: newest ? Math.round((now - newest) / 60000) : null,
    // Le détecteur n'est pas fiable tant qu'il n'a pas la profondeur
    // d'historique que réclament ses propres fenêtres.
    warmup: spanMs < GF_BASE_FROM_MIN * 60 * 1000,
    historySpanMin: Math.round(spanMs / 60000),
    thresholdsVersion: GF_THRESHOLDS_VERSION,
  };
}

/** Remise à zéro — utilisée par le rejeu hors ligne (§8.2). */
function gfReset() {
  gfHistory.clear();
  gfFirstSampleAt = 0;
}

module.exports = {
  gfRecordObs,
  gfDetect,
  gfDetectModel,
  gfHealth,
  gfReset,
  // Exportés pour le rejeu / les tests unitaires de calibration.
  gfScoreAtSample,
  gfStationPassage,
  buildFront,
  buildFronts,
  gfClusterSpatial,
  gfDistKm,
  gfRingsOverlap,
  gfRingCenter,
  gfPickEpisodeFrom,
  gfMatchEpisodes,
  gfVerificationRates,
  GF_MATCH_TOLERANCE_MS,
  etaAt,
  pointInRing,
  angDiff,
  circularMean,
  GF_THRESHOLDS_VERSION,
  GF_CORRIDOR_HOURS,
  GF_MIN_STATIONS,
  GF_CLUSTER_RADIUS_KM,
  GF_MODEL_CLUSTER_RADIUS_KM,
  GF_RESCUE_RADIUS_KM,
  GF_RESCUE_MIN_CORE,
};
