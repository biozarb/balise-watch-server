// ══════════════════════════════════════════════════════════════════════
//  lib/cellule-convective.js — TROIS SOURCES QUI SE RECOUPENT
//                              DANS LE TEMPS               (09/09/2026)
//                              Lot « cellule qui approche », lot 3
//
//  ⛔ CE QUE CE MODULE AJOUTE, ET QU'AUCUNE SOURCE NE SAIT FAIRE SEULE.
//  Le lot 1 dit « de la pluie arrive à 11:40 ». Le lot 2 dit « une rafale
//  de 62 km/h arrive à 11:45 ». La foudre dit « douze impacts à 23 km, et
//  ils se rapprochent ». Chacune peut se tromper seule ; ensemble, elles
//  disent la même chose au même moment, et C'EST ÇA le signal.
//
//  ⛔⛔ LA RÈGLE EST LA CONCORDANCE DANS LE TEMPS (arbitrage Yann 09/09),
//  PAS UN COMPTE DE SOURCES. Deux sources qui parlent du même quart
//  d'heure décrivent un objet ; deux sources qui parlent de deux moments
//  différents décrivent deux objets, et les additionner fabriquerait une
//  cellule qui n'existe pas. L'observation du lot 1 le disait déjà : à
//  Ouessant, le 09/09 à 09:58 Z, le radar annonçait « ETA 22 min » et
//  PIAF « aside » — les sources divergeaient, et cette divergence était
//  l'information. Ici elle est CALCULÉE.
//
//  ── COMMENT ON FAIT CONCORDER DES CHOSES QUI N'ONT PAS LA MÊME
//     PRÉCISION ─────────────────────────────────────────────────────────
//  Chaque source rend un instant, mais aucune ne le connaît à la minute :
//
//      PIAF        tranche de  5 min → fenêtre ± 8 min
//      rafale PI   tranche de 15 min → fenêtre ± 20 min
//      foudre      observée, mais son ETA vient d'un déplacement estimé
//                  sur deux fenêtres de 15 min → ± 15 min
//
//  ⚠️ CES DEMI-LARGEURS NE SONT PAS L'INCERTITUDE DES MODÈLES, qui est
//  bien plus grande. Ce sont les GRANULARITÉS de ce qu'on lit : deux
//  sources dont les fenêtres se touchent parlent du même objet ; deux
//  sources séparées de plus que ça parlent d'autre chose. Un jour, un
//  rejeu d'orage réel dira si elles sont trop serrées. Elles sont dans
//  `DEFAUTS`, surchargeables, et le banc les sabote.
//
//  On cherche donc le plus grand groupe de sources dont les fenêtres
//  s'INTERSECTENT TOUTES DEUX À DEUX, et l'ETA du composite est le
//  milieu de cette intersection. ⛔ Pas une moyenne des ETA : une
//  moyenne accepterait 10 et 90 en rendant 50, c'est-à-dire un instant
//  qu'aucune source n'a jamais annoncé.
//
//  ── CE QUE LE COMPOSITE NE FAIT PAS ─────────────────────────────────
//  ⛔ Il ne fait taire personne. `precip`, `gust_pi` et `lightning`
//  gardent leurs pushes, leurs scopes et leurs seuils (arbitrage Yann
//  09/09 : « un quatrième signal, les autres inchangés »). Le pilote peut
//  donc recevoir deux messages pour le même orage — c'est assumé, et
//  c'est ce qu'il faudra regarder pendant la phase silencieuse.
//
//  ⛔ Il ne fabrique aucune source. Il reçoit les objets DÉJÀ calculés
//  par `piaf-eta.js` et `rafale-pi.js`, et les impacts bruts pour la
//  foudre. Il n'ouvre aucune connexion, ne lit aucun octet, n'a aucun
//  état entre deux appels — comme `gust-front.js`, et pour la même
//  raison : pouvoir être rejoué sur une archive.
//
//  ⛔ Il ne remplace pas `gust_front` (le front de rafales OBSERVÉ sur
//  RADOME). Celui-là constate un passage ; celui-ci annonce une arrivée.
//
//  ── CE QUE REND `celluleConvective()` ────────────────────────────────
//    { detected, niveau, etaMin, etaAtMs, fenetreMin: [a, b],
//      accord: ['piaf', 'rafale'], nSources, nDisponibles,
//      sources: { piaf: {...}, rafale: {...}, foudre: {...} },
//      desaccord, resume, attributions }
//  `niveau` ∈ 0 (rien) | 1 (une seule source) | 2 (deux d'accord)
//            | 3 (les trois d'accord)
//  ⚠️ `desaccord` est renseigné quand au moins deux sources parlent SANS
//  se recouper. C'est une information, pas un raté : c'est exactement le
//  cas d'Ouessant, et le taire ferait croire à un calme.
// ══════════════════════════════════════════════════════════════════════
'use strict';

const KM_PAR_DEG_LAT = 111.2;

const DEFAUTS = Object.freeze({
  // ── Les demi-largeurs de fenêtre, par source (min) ────────────────
  fenetrePiafMin: 8,        // tranche de 5 min + une marge
  fenetreRafaleMin: 20,     // tranche de 15 min + une marge
  fenetreFoudreMin: 15,     // déplacement estimé sur deux fenêtres de 15
  // ── L'horizon du composite ────────────────────────────────────────
  // ⚠️ Au-delà, une concordance n'aide plus personne à décider MAINTENANT
  // — et les trois sources n'ont pas le même horizon (PIAF 195 min,
  // AROME-PI 360, foudre ~0). Retenir 120 min, c'est rester dans la
  // portion où les trois peuvent réellement se croiser.
  horizonMin: 120,
  // ── La foudre ─────────────────────────────────────────────────────
  foudreRayonKm: 50,        // le même défaut que `lightning_radius_km`
  foudreFenetreMin: 15,     // la même que FW_LIGHTNING_WINDOW_MIN
  foudreMinImpacts: 3,      // ⚠️ TROIS, pas un. Le signal `lightning`
                            // pousse dès UN impact, et c'est son rôle :
                            // il alerte. Ici on veut CARACTÉRISER une
                            // cellule, et un impact isolé à 48 km ne
                            // caractérise rien. Le composite est plus
                            // exigeant que la somme de ses sources.
  foudreVitesseMinKmh: 5,   // en dessous, le « déplacement » est du bruit
  foudreVitesseMaxKmh: 90,  // au-dessus, ce ne sont pas les mêmes cellules
});

// ══════════════════════════════════════════════════════════════════════
//  LA FOUDRE — ce que le buffer sait et que personne ne lui demandait
//
//  ⛔ LE SERVEUR GARDE 60 MINUTES D'IMPACTS ET N'EN LIT QUE 15. Le signal
//  `lightning` compte ce qui tombe dans un rayon, point : pas de taux,
//  pas de centroïde, pas de vitesse (vérifié le 09/09 — `lightningStrikes`
//  n'est touché qu'en écriture, en purge, et par UNE boucle de
//  comptage). Toute la tendance est donc à écrire, mais la matière est
//  déjà là : on ne touche NI au WebSocket, NI à l'ingestion.
//
//  ⚠️⚠️ ET UNE LIMITE QU'IL FAUT DIRE : le `t` stocké est L'HEURE
//  D'ARRIVÉE au serveur (`Date.now()` à la réception), pas l'horodatage
//  Blitzortung, que l'ingestion jette. Sur des fenêtres de quinze
//  minutes c'est sans conséquence — la latence du flux est de l'ordre de
//  la seconde. Mais ça veut dire deux choses : un dédoublonnage sur
//  `(lat, lon, t)` ne verrait AUCUN doublon ici (deux copies du même
//  impact arrivent à deux instants différents), et un hoquet du flux
//  décalerait toute une bouffée d'impacts d'un coup. C'est pourquoi la
//  vitesse est bornée par `foudreVitesseMaxKmh` : au-dessus, on ne
//  mesure pas une cellule qui court, on mesure un rattrapage de flux.
// ══════════════════════════════════════════════════════════════════════
function repereLocal(lat0) {
  return { kx: KM_PAR_DEG_LAT * Math.cos(lat0 * Math.PI / 180), ky: KM_PAR_DEG_LAT };
}
/** Cap 0 = nord, 90 = est. */
function capDeg(dxKm, dyKm) {
  return (Math.atan2(dxKm, dyKm) * 180 / Math.PI + 360) % 360;
}
const NOMS_16 = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
function secteur16(deg) {
  if (deg == null || !Number.isFinite(deg)) return null;
  return NOMS_16[Math.round(((deg % 360) + 360) % 360 / 22.5) % 16];
}

/**
 * Ce que les impacts disent autour d'un point : combien, où, et vers où.
 *
 * @param {Array<{lat:number,lon:number,t:number}>} strikes  buffer brut
 * @param {number} lat @param {number} lon
 * @param {number} nowMs
 * @param {object} [opts]
 * @returns {{
 *   disponible: boolean, refus: string|null,
 *   nRecent: number, nPrecedent: number, tendance: 'hausse'|'stable'|'baisse'|null,
 *   dKm: number|null, secteur: string|null, capDeg: number|null,
 *   vitesseKmh: number|null, capDeplacementDeg: number|null,
 *   dansLeRayon: boolean, etaMin: number|null, rayonKm: number,
 * }}
 */
function foudreAutour(strikes, lat, lon, nowMs, opts) {
  const o = Object.assign({}, DEFAUTS, opts || {});
  const vide = {
    disponible: false, refus: 'pas-de-flux',
    nRecent: 0, nPrecedent: 0, tendance: null,
    dKm: null, secteur: null, capDeg: null,
    vitesseKmh: null, capDeplacementDeg: null,
    dansLeRayon: false, etaMin: null, rayonKm: o.foudreRayonKm,
  };
  if (!Array.isArray(strikes)) return vide;
  if (!(Number.isFinite(lat) && Number.isFinite(lon))) {
    return Object.assign({}, vide, { refus: 'point-inconnu' });
  }
  const { kx, ky } = repereLocal(lat);
  const fen = o.foudreFenetreMin * 60_000;
  const recents = [], precedents = [];
  for (let i = strikes.length - 1; i >= 0; i--) {
    const s = strikes[i];
    const age = nowMs - s.t;
    // ⛔ Le buffer est trié par arrivée : on s'arrête dès qu'on sort des
    // deux fenêtres, on ne parcourt jamais les 20 000 entrées.
    if (age > 2 * fen) break;
    const dxKm = (s.lon - lon) * kx, dyKm = (s.lat - lat) * ky;
    const dKm = Math.hypot(dxKm, dyKm);
    if (dKm > o.foudreRayonKm) continue;
    (age <= fen ? recents : precedents).push({ dxKm, dyKm, dKm });
  }
  // ⚠️ « Aucun impact » n'est pas « pas de flux ». Le premier est une
  // information (il ne se passe rien), le second un silence (on ne sait
  // pas). Le composite doit pouvoir les distinguer, sinon un WebSocket
  // coupé ressemblerait à un ciel bleu.
  const base = {
    disponible: true, refus: null,
    nRecent: recents.length, nPrecedent: precedents.length,
    tendance: null, dKm: null, secteur: null, capDeg: null,
    vitesseKmh: null, capDeplacementDeg: null,
    dansLeRayon: false, etaMin: null, rayonKm: o.foudreRayonKm,
  };
  if (!recents.length) return base;

  const proche = recents.reduce((a, b) => (b.dKm < a.dKm ? b : a));
  base.dKm = Math.round(proche.dKm * 10) / 10;
  base.capDeg = proche.dKm > 0 ? Math.round(capDeg(proche.dxKm, proche.dyKm)) : null;
  base.secteur = secteur16(base.capDeg);
  base.dansLeRayon = true;
  // Tendance : le taux de la fenêtre récente contre celui d'avant.
  // ⚠️ Sur de petits nombres, « 2 puis 3 » n'est pas une intensification.
  // Le seuil de `foudreMinImpacts` protège des deux côtés.
  if (recents.length >= o.foudreMinImpacts || precedents.length >= o.foudreMinImpacts) {
    const r = recents.length, p = precedents.length;
    base.tendance = r > p * 1.3 ? 'hausse' : r < p * 0.7 ? 'baisse' : 'stable';
  }

  // ── Le déplacement : centroïde d'avant → centroïde de maintenant ──
  // ⛔ Deux centroïdes, pas une régression : on n'a que deux fenêtres, et
  // une droite ajustée sur deux points n'apporte rien de plus qu'un
  // segment — sauf l'illusion de la précision.
  if (recents.length >= o.foudreMinImpacts && precedents.length >= o.foudreMinImpacts) {
    const cen = arr => ({
      x: arr.reduce((s, c) => s + c.dxKm, 0) / arr.length,
      y: arr.reduce((s, c) => s + c.dyKm, 0) / arr.length,
    });
    const c0 = cen(precedents), c1 = cen(recents);
    const dx = c1.x - c0.x, dy = c1.y - c0.y;
    const d = Math.hypot(dx, dy);
    const h = o.foudreFenetreMin / 60;
    const v = d / h;
    if (v >= o.foudreVitesseMinKmh && v <= o.foudreVitesseMaxKmh) {
      base.vitesseKmh = Math.round(v);
      base.capDeplacementDeg = Math.round(capDeg(dx, dy));
      // L'ETA : la distance du centroïde récent au site, projetée sur la
      // direction du déplacement. ⛔ Seulement si ça s'APPROCHE : un
      // produit scalaire positif entre (site − centroïde) et le
      // déplacement. Sinon `etaMin` reste null — un orage qui s'éloigne
      // n'a pas d'heure d'arrivée.
      const versSiteX = -c1.x, versSiteY = -c1.y;
      const norme = Math.hypot(versSiteX, versSiteY);
      const approche = norme > 0 ? (dx * versSiteX + dy * versSiteY) / (d * norme) : 0;
      if (approche > 0.3) {                    // ~72° de tolérance de cap
        const vApproche = v * approche;
        base.etaMin = vApproche > 0 ? Math.max(0, Math.round(norme / vApproche * 60)) : null;
      }
    }
  }
  // Déjà des impacts au-dessus du site : l'ETA est ZÉRO, quoi que dise
  // le déplacement. C'est une OBSERVATION, elle prime sur une estimation.
  if (base.dKm != null && base.dKm <= o.foudreRayonKm / 5) base.etaMin = 0;
  return base;
}

// ══════════════════════════════════════════════════════════════════════
//  LE COMPOSITE — le plus grand accord, et le désaccord quand il y en a
// ══════════════════════════════════════════════════════════════════════
/** Une source réduite à ce qui sert à la concordance. */
function voix(nom, { disponible, refus, parle, etaMin, demiFenetre, detail }) {
  return {
    nom, disponible: !!disponible, refus: refus ?? null, parle: !!parle,
    etaMin: parle ? etaMin : null,
    fenetreMin: parle ? [etaMin - demiFenetre, etaMin + demiFenetre] : null,
    detail: detail ?? null,
  };
}

/**
 * @param {{piaf: object|null, rafale: object|null, foudre: object|null}} src
 * @param {number} nowMs
 * @param {object} [opts] surcharge de DEFAUTS
 */
function celluleConvective(src, nowMs, opts) {
  const o = Object.assign({}, DEFAUTS, opts || {});
  const { piaf, rafale, foudre } = src || {};

  // ── 1. Chaque source, ramenée à « parle-t-elle, et de quand ? » ────
  // ⛔ `disponible` et `parle` sont DEUX choses. Une source indisponible
  // (kill switch, compte non autorisé, R2 muet) ne dit RIEN ; une source
  // disponible qui ne parle pas dit « je ne vois rien », ce qui est une
  // information. Les confondre ferait passer une chaîne coupée pour un
  // ciel calme — le défaut que ce projet pourchasse depuis le lot 1.
  const vPiaf = voix('piaf', {
    disponible: !!piaf,
    refus: piaf?.refus ?? (piaf ? null : 'indisponible'),
    parle: !!(piaf && !piaf.refus && piaf.hit && piaf.etaMin != null && piaf.etaMin <= o.horizonMin),
    etaMin: piaf?.etaMin,
    demiFenetre: o.fenetrePiafMin,
    detail: piaf ? { passe: piaf.passe, passeAgeMin: piaf.passeAgeMin, trend: piaf.trend, mmMax5: piaf.mmMax5, secteur: piaf.secteur, cpaKm: piaf.cpaKm } : null,
  });
  const vRafale = voix('rafale', {
    disponible: !!rafale,
    refus: rafale?.refus ?? (rafale ? null : 'indisponible'),
    // ⛔ `cellule`, pas `hit` : au lot 2, `hit` seul parlait à 41 % des
    // décollages un jour de tramontane. Le composite hérite de la
    // correction, il ne la refait pas.
    parle: !!(rafale && !rafale.refus && rafale.cellule && rafale.etaMin != null && rafale.etaMin <= o.horizonMin),
    etaMin: rafale?.etaMin,
    demiFenetre: o.fenetreRafaleMin,
    detail: rafale ? { run: rafale.run, runAgeMin: rafale.runAgeMin, gustKmh: rafale.gustKmh, regimeKmh: rafale.regimeKmh, sautHitKmh: rafale.sautHitKmh, seuilKmh: rafale.seuilKmh, secteur: rafale.secteur } : null,
  });
  const vFoudre = voix('foudre', {
    disponible: !!(foudre && foudre.disponible),
    refus: foudre?.refus ?? (foudre ? null : 'indisponible'),
    parle: !!(foudre && foudre.disponible && foudre.nRecent >= o.foudreMinImpacts
              && foudre.etaMin != null && foudre.etaMin <= o.horizonMin),
    etaMin: foudre?.etaMin,
    demiFenetre: o.fenetreFoudreMin,
    detail: foudre ? { nRecent: foudre.nRecent, nPrecedent: foudre.nPrecedent, tendance: foudre.tendance, dKm: foudre.dKm, secteur: foudre.secteur, vitesseKmh: foudre.vitesseKmh, rayonKm: foudre.rayonKm } : null,
  });
  const toutes = [vPiaf, vRafale, vFoudre];
  const sources = { piaf: vPiaf, rafale: vRafale, foudre: vFoudre };
  const disponibles = toutes.filter(v => v.disponible);
  const parlantes = toutes.filter(v => v.parle);

  const vide = {
    detected: false, niveau: 0, etaMin: null, etaAtMs: null,
    fenetreMin: null, accord: [], nSources: 0,
    nDisponibles: disponibles.length, nParlantes: parlantes.length,
    sources, desaccord: null, refus: null,
    resume: null, attributions: attributionsDe(disponibles),
  };

  // ⛔ MOINS DE DEUX SOURCES DISPONIBLES : PAS DE COMPOSITE, ET ON LE
  // DIT. Une concordance ne se calcule pas sur une seule voix ; rendre
  // « rien détecté » ferait croire à un calme là où il n'y a qu'un
  // silence. Le refus est NOMMÉ, comme partout ailleurs dans ce lot.
  if (disponibles.length < 2) {
    return Object.assign({}, vide, { refus: 'sources-insuffisantes' });
  }
  if (!parlantes.length) return vide;

  // ── 2. Le plus grand accord — le point couvert par le plus de
  //       fenêtres ────────────────────────────────────────────────────
  // ⛔ EN DIMENSION 1, DES INTERVALLES QUI S'INTERSECTENT DEUX À DEUX
  // ONT UN POINT COMMUN (propriété de Helly). Chercher le point le plus
  // couvert suffit donc, et évite d'énumérer les sous-ensembles.
  // ⚠️ On teste les BORNES GAUCHES : si un point est couvert par k
  // fenêtres, la plus grande de leurs bornes gauches l'est aussi.
  let meilleur = null;
  for (const v of parlantes) {
    const p = v.fenetreMin[0];
    const dedans = parlantes.filter(w => w.fenetreMin[0] <= p && p <= w.fenetreMin[1]);
    if (!meilleur || dedans.length > meilleur.length) meilleur = dedans;
  }
  const accord = meilleur || [];
  const a = Math.max(...accord.map(v => v.fenetreMin[0]));
  const b = Math.min(...accord.map(v => v.fenetreMin[1]));
  // ⛔ LE MILIEU DE L'INTERSECTION, PAS LA MOYENNE DES ETA. Une moyenne
  // de 10 et 90 rendrait 50 : un instant qu'aucune source n'a annoncé,
  // et qui aurait l'air d'un consensus.
  const etaMin = Math.max(0, Math.round((a + b) / 2));
  const niveau = accord.length;

  // ── 3. Le désaccord, quand il y en a — c'est une information ───────
  // ⚠️ Le cas d'Ouessant du lot 1, calculé : deux sources qui parlent et
  // qui ne se recoupent pas ne se contredisent pas « à cause d'un bug ».
  // Elles regardent deux choses. Le taire ferait croire à un calme.
  const dehors = parlantes.filter(v => !accord.includes(v));
  const desaccord = dehors.length ? {
    sources: dehors.map(v => v.nom),
    ecartMin: dehors.map(v => Math.round(v.etaMin - etaMin)),
    dire: `${dehors.map(v => v.nom).join(' et ')} ${dehors.length > 1 ? 'annoncent' : 'annonce'} un autre moment — deux objets, pas un.`,
  } : null;

  return {
    detected: niveau >= 2,
    niveau, etaMin,
    etaAtMs: nowMs + etaMin * 60_000,
    fenetreMin: [Math.max(0, Math.round(a)), Math.round(b)],
    accord: accord.map(v => v.nom),
    nSources: niveau,
    nDisponibles: disponibles.length, nParlantes: parlantes.length,
    sources, desaccord, refus: null,
    resume: resumeDe(accord, etaMin, sources),
    attributions: attributionsDe(disponibles),
  };
}

/** Une phrase qui NOMME les sources d'accord — jamais « le système ». */
function resumeDe(accord, etaMin, sources) {
  if (!accord.length) return null;
  const quoi = accord.map(v => {
    if (v.nom === 'piaf') return `pluie ${sources.piaf.detail?.mmMax5 != null ? `(${sources.piaf.detail.mmMax5} mm/5 min)` : ''}`.trim();
    if (v.nom === 'rafale') return `rafale ${sources.rafale.detail?.gustKmh ?? '?'} km/h`;
    return `foudre (${sources.foudre.detail?.nRecent ?? '?'} impacts à ${sources.foudre.detail?.dKm ?? '?'} km)`;
  });
  const quand = etaMin === 0 ? 'en ce moment' : `dans ~${etaMin} min`;
  return `${quoi.join(' + ')} ${quand}`;
}

/** ⛔ Une attribution PAR SOURCE DISPONIBLE, jamais une phrase générique.
 *  Les deux prévisions sont sous Licence Ouverte 2.0, qui EXIGE la
 *  mention ; Blitzortung est un réseau bénévole dont la donnée est
 *  indicative et non officielle, et le dire est une obligation morale
 *  autant que la première est juridique. */
function attributionsDe(disponibles) {
  const out = [];
  for (const v of disponibles) {
    if (v.nom === 'piaf') out.push('Source : Météo-France — prévision immédiate agrégée, Licence Ouverte 2.0');
    if (v.nom === 'rafale') out.push('Source : Météo-France — AROME-PI, Licence Ouverte 2.0');
    if (v.nom === 'foudre') out.push('Impacts : réseau bénévole Blitzortung — donnée indicative, non officielle');
  }
  return out;
}

module.exports = {
  DEFAUTS, foudreAutour, celluleConvective,
  capDeg, secteur16, repereLocal,
};
