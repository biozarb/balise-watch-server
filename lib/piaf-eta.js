// ══════════════════════════════════════════════════════════════════════
//  lib/piaf-eta.js — l'ETA de la pluie LU dans la prévision   (09/09/2026)
//                    Lot « cellule qui approche », lot 1
//                    (cadrage-piaf-pluie-20-08 §9.1, enfin codé)
//
//  ⛔ CE MODULE NE PARLE QUE D'UNE SOURCE : la prévision immédiate
//  agrégée de Météo-France (PIAF), telle qu'`agrume/ingest_piaf.py`
//  la publie sur R2 (`agrume/piaf/{passe}/carte.bin`, float16, maille
//  0,02°, MAXIMUM des 4 points natifs, lats DÉCROISSANTES). Il ne
//  fabrique rien : il lit une tranche, la compare à un seuil, et NOMME
//  la passe qui a parlé. Là où il ne peut pas parler (hors emprise,
//  passe trop vieille, rien en ligne), il rend un REFUS nommé — jamais
//  un ETA calculé sur une donnée qu'il n'a pas.
//
//  ⛔ LES TROIS PIÈGES DU CADRAGE, DANS L'ORDRE OÙ ILS MORDENT :
//    1. PIAF est un CUMUL (mm sur 5 min), pas un taux. On ne divise rien.
//       Le seuil « 0,5 mm / 5 min » est ~6 mm/h, une averse franche.
//    2. L'instant nommé d'une échéance est la FIN de sa tranche : le rang
//       k couvre ]passe + 5k ; passe + 5(k+1)] minutes. L'ETA se calcule
//       sur la FIN. Un calcul sur le début est faux de 5 min partout.
//    3. Le pas de 5 min casse l'arithmétique d'epoch en heures
//       (t0 + m/60 × 3 600 000 rend des non-entiers). Ici tout est en
//       MINUTES entières et `passeMs + m * 60_000`.
//
//  ⚠️ TRONQUER, PAS ARRONDIR, l'indice de maille (banc du lot Q3,
//  mensonge nº 3) : la coordonnée publiée est le coin NORD-OUEST du
//  bloc. Un `Math.round` décalerait d'une maille la moitié des sites.
//
//  ⚠️ CE MODULE N'IMPORTE RIEN DU DÉPÔT WEB. La CI AGRUME a cassé deux
//  fois en septembre parce qu'un banc serveur importait un module web
//  que le garde-fou d'imports ne connaissait pas. Le seul partage
//  possible est le FORMAT, et il est décrit par le manifeste PIAF, pas
//  par du code.
//
//  Ce que rend `etaPiaf()` (tous les nombres en unités nommées) :
//    { source: 'piaf', passe, passeAgeMin, fraicheur, refus,
//      hit, rang, etaMin, etaAtMs, mmMax5,
//      trend, cpaKm, bearingDeg, moveDirDeg, moveSpeedKmh,
//      attribution }
//  `refus` ∈ null | 'hors-emprise' | 'passe-trop-vieille' | 'indisponible'
//  `fraicheur` ∈ 'fraiche' (≤ ageAncienMin) | 'ancienne' (≤ ageRefusMin)
//  `trend` ∈ 'onsite' | 'approaching' | 'aside' | 'away' | 'none'
//    — le vocabulaire RainViewer ('approaching'/'aside'/'away') est
//    repris à l'identique pour que le client n'ait pas deux grammaires ;
//    'onsite' (pluie sur le site dans la tranche courante) et 'none'
//    (rien au-dessus du seuil à rechercheKm sur tout l'horizon) sont
//    propres à la prévision, qui SAIT quand il n'y a rien.
// ══════════════════════════════════════════════════════════════════════
'use strict';

// ── Les seuils — POINTS DE DÉPART (§3 du prompt), à calibrer sur un
// épisode réel. Chaque chiffre non mesuré est une estimation, et le
// module les expose pour que la note du lot puisse dire lesquels ont
// été essayés.
const DEFAUTS = Object.freeze({
  seuilMm5: 0.5,        // mm / 5 min — « pluie qui compte » (≈ 6 mm/h)
  maillesMin: 3,        // mailles 0,02° CONTIGUËS (8-connexité) ≥ seuil
  rayonKm: 3,           // l'échelle d'un site de vol
  rechercheKm: 60,      // où l'on cherche l'écho le plus proche (cpa, cap)
  centroideKm: 40,      // fenêtre du centroïde pour le vecteur de déplacement
  ageAncienMin: 25,     // au-delà : PIAF parle encore, mais « passe ancienne »
  ageRefusMin: 35,      // au-delà : refus nommé (7 échéances déjà passées,
                        // deux créneaux d'ingestion sautés — arbitrage Yann 09/09)
});

const PAS_MIN = 5;
const KM_PAR_DEG_LAT = 111.2;

const ATTRIBUTION = 'Source : Météo-France — prévision immédiate agrégée, Licence Ouverte 2.0';

// ── float16 → number. Pas de Float16Array garanti sur Node 18/20 : on
// décode à la main (IEEE 754 binary16, little-endian déjà lu en u16).
function f16(u) {
  const s = (u & 0x8000) ? -1 : 1;
  const e = (u >> 10) & 0x1f;
  const m = u & 0x3ff;
  if (e === 0) return s * m * 2 ** -24;                // dénormalisé (ou ±0)
  if (e === 0x1f) return m ? NaN : s * Infinity;
  return s * (1 + m / 1024) * 2 ** (e - 15);
}

// ══════════════════════════════════════════════════════════════════════
//  LA CARTE — une passe en RAM, telle que R2 la sert
// ══════════════════════════════════════════════════════════════════════
/**
 * @param {object} p
 * @param {string} p.passe          ISO Z de la passe (`manifest.passe`)
 * @param {number} p.nbLat @param {number} p.nbLon
 * @param {number} p.pasDeg         0,02 (`service.calque.pas_deg`)
 * @param {number} p.latPremier     coin NW de la première ligne (NORD)
 * @param {number} p.lonPremier
 * @param {number} p.nbEcheances    39
 * @param {Uint8Array|Buffer} p.octets  carte.bin brut, (echeance, lat, lon) <f2
 */
class CartePiaf {
  constructor(p) {
    this.passe = p.passe;
    this.passeMs = Date.parse(p.passe);
    this.nbLat = p.nbLat; this.nbLon = p.nbLon;
    this.pasDeg = p.pasDeg;
    this.latPremier = p.latPremier; this.lonPremier = p.lonPremier;
    this.nbEcheances = p.nbEcheances;
    const attendu = p.nbEcheances * p.nbLat * p.nbLon * 2;
    if (p.octets.byteLength !== attendu) {
      throw new Error(`carte.bin : ${p.octets.byteLength} octets, attendu ${attendu} (${p.nbEcheances} × ${p.nbLat} × ${p.nbLon} × 2)`);
    }
    // Vue u16 SANS copie quand l'offset le permet (Buffer de node-fetch :
    // souvent une tranche d'un pool, offset impair possible → copie).
    const o = p.octets;
    this.u16 = (o.byteOffset % 2 === 0)
      ? new Uint16Array(o.buffer, o.byteOffset, o.byteLength / 2)
      : new Uint16Array(new Uint8Array(o).slice().buffer);
    this.parEcheance = p.nbLat * p.nbLon;
    if (!Number.isFinite(this.passeMs)) throw new Error(`passe illisible : ${p.passe}`);
  }

  /** Cumul (mm / 5 min) au rang k, ligne j (0 = nord), colonne i. */
  mm(k, j, i) { return f16(this.u16[k * this.parEcheance + j * this.nbLon + i]); }

  /** Fin de la tranche du rang k, en ms epoch — ENTIER (piège nº 3). */
  finMs(k) { return this.passeMs + (k + 1) * PAS_MIN * 60_000; }

  /** Indices (j, i) de la maille qui CONTIENT (lat, lon) — troncature. */
  maille(lat, lon) {
    const j = Math.floor((this.latPremier - lat) / this.pasDeg + 1e-9);
    const i = Math.floor((lon - this.lonPremier) / this.pasDeg + 1e-9);
    return { j, i };
  }

  dansEmprise(lat, lon) {
    const { j, i } = this.maille(lat, lon);
    return j >= 0 && j < this.nbLat && i >= 0 && i < this.nbLon;
  }

  /** Centre de la maille (j, i) — la coordonnée publiée est le coin NW. */
  centre(j, i) {
    return { lat: this.latPremier - (j + 0.5) * this.pasDeg, lon: this.lonPremier + (i + 0.5) * this.pasDeg };
  }
}

// ══════════════════════════════════════════════════════════════════════
//  GÉOMÉTRIE LOCALE — équirectangulaire autour du site. À 60 km l'écart
//  avec le grand cercle est < 0,1 % : très en dessous d'une maille.
// ══════════════════════════════════════════════════════════════════════
function repereLocal(lat0) {
  const kx = KM_PAR_DEG_LAT * Math.cos(lat0 * Math.PI / 180);
  return { kx, ky: KM_PAR_DEG_LAT };
}
/** Cap 0 = nord, 90 = est, DEPUIS (lat0, lon0) VERS (lat, lon). */
function capDeg(dxKm, dyKm) {
  return (Math.atan2(dxKm, dyKm) * 180 / Math.PI + 360) % 360;
}
const NOMS_16 = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
/** Le nom du secteur d'où VIENT la pluie, pour un push (« par le SW »). */
function secteur16(deg) {
  if (deg == null || !Number.isFinite(deg)) return null;
  return NOMS_16[Math.round(((deg % 360) + 360) % 360 / 22.5) % 16];
}

/** Les mailles à ≤ rayonKm du site : [{ j, i, dKm, dxKm, dyKm }], et les
 *  bornes de la fenêtre. Calculées UNE fois par (site, rayon) : la
 *  géométrie ne dépend pas de l'échéance. */
function fenetre(carte, lat, lon, rayonKm) {
  const { kx, ky } = repereLocal(lat);
  const dj = Math.ceil(rayonKm / (carte.pasDeg * ky)) + 1;
  const di = Math.ceil(rayonKm / (carte.pasDeg * kx)) + 1;
  const { j: j0, i: i0 } = carte.maille(lat, lon);
  const cellules = [];
  for (let j = Math.max(0, j0 - dj); j <= Math.min(carte.nbLat - 1, j0 + dj); j++) {
    for (let i = Math.max(0, i0 - di); i <= Math.min(carte.nbLon - 1, i0 + di); i++) {
      const c = carte.centre(j, i);
      const dxKm = (c.lon - lon) * kx, dyKm = (c.lat - lat) * ky;
      const dKm = Math.hypot(dxKm, dyKm);
      if (dKm <= rayonKm) cellules.push({ j, i, dKm, dxKm, dyKm });
    }
  }
  return cellules;
}

/** Taille de la plus grande composante 8-connexe parmi `sel` (mailles
 *  au-dessus du seuil). Le test « ≥ maillesMin mailles CONTIGUËS »
 *  refuse trois gouttes isolées et accepte une averse. */
function plusGrandeComposante(sel) {
  if (!sel.length) return 0;
  const cle = (j, i) => j * 100000 + i;
  const reste = new Map(sel.map(c => [cle(c.j, c.i), c]));
  let best = 0;
  while (reste.size) {
    const [k0, c0] = reste.entries().next().value;
    reste.delete(k0);
    const pile = [c0]; let n = 0;
    while (pile.length) {
      const c = pile.pop(); n++;
      for (let dj = -1; dj <= 1; dj++) for (let di = -1; di <= 1; di++) {
        if (!dj && !di) continue;
        const k = cle(c.j + dj, c.i + di);
        const v = reste.get(k);
        if (v) { reste.delete(k); pile.push(v); }
      }
    }
    if (n > best) best = n;
  }
  return best;
}

// ══════════════════════════════════════════════════════════════════════
//  L'ETA — la première tranche où la pluie « qui compte » touche le site
// ══════════════════════════════════════════════════════════════════════
function refus(carte, nowMs, raison, extra) {
  const ageMin = carte ? (nowMs - carte.passeMs) / 60_000 : null;
  return Object.assign({
    source: 'piaf', passe: carte?.passe ?? null,
    passeAgeMin: ageMin == null ? null : Math.round(ageMin),
    fraicheur: null, refus: raison,
    hit: false, rang: null, etaMin: null, etaAtMs: null, mmMax5: null,
    trend: null, cpaKm: null, bearingDeg: null, secteur: null,
    moveDirDeg: null, moveSpeedKmh: null,
    attribution: ATTRIBUTION,
  }, extra || {});
}

/**
 * @param {CartePiaf|null} carte
 * @param {number} lat @param {number} lon
 * @param {number} nowMs
 * @param {object} [opts]  surcharge de DEFAUTS
 */
function etaPiaf(carte, lat, lon, nowMs, opts) {
  const o = Object.assign({}, DEFAUTS, opts || {});
  if (!carte) return refus(null, nowMs, 'indisponible');
  const ageMin = (nowMs - carte.passeMs) / 60_000;
  if (ageMin > o.ageRefusMin) return refus(carte, nowMs, 'passe-trop-vieille');
  if (!(lat != null && lon != null) || !carte.dansEmprise(lat, lon)) return refus(carte, nowMs, 'hors-emprise');
  const fraicheur = ageMin <= o.ageAncienMin ? 'fraiche' : 'ancienne';

  // La tranche qui contient MAINTENANT. Une horloge en avance sur la
  // passe (âge négatif) tombe au rang 0, pas en dehors du tableau.
  const nb = carte.nbEcheances;
  const kNow = Math.min(nb - 1, Math.max(0, Math.floor(ageMin / PAS_MIN)));

  const large = fenetre(carte, lat, lon, o.rechercheKm);
  const proche = large.filter(c => c.dKm <= o.rayonKm);

  // ── 1. La première tranche qui touche le site ──────────────────────
  let rang = null, mmMax5 = null;
  for (let k = kNow; k < nb; k++) {
    const sel = []; let mx = 0;
    for (const c of proche) {
      const v = carte.mm(k, c.j, c.i);
      if (!(v >= 0)) continue; // NaN = maille non renseignée : ni pluie ni sec
      if (v > mx) mx = v;
      if (v >= o.seuilMm5) sel.push(c);
    }
    if (sel.length >= o.maillesMin && plusGrandeComposante(sel) >= o.maillesMin) {
      rang = k; mmMax5 = Math.round(mx * 100) / 100; break;
    }
  }

  // ── 2. L'écho le plus proche MAINTENANT (cpa, cap d'où ça vient), et
  //       la distance minimale qu'il atteindra sur l'horizon ───────────
  let dNow = null, bearingDeg = null, dFutur = null;
  for (let k = kNow; k < nb; k++) {
    let dmin = null, best = null;
    for (const c of large) {
      if (carte.mm(k, c.j, c.i) >= o.seuilMm5 && (dmin == null || c.dKm < dmin)) { dmin = c.dKm; best = c; }
    }
    if (k === kNow) {
      dNow = dmin;
      if (best && dmin > 0) bearingDeg = Math.round(capDeg(best.dxKm, best.dyKm));
    } else if (dmin != null && (dFutur == null || dmin < dFutur)) dFutur = dmin;
  }

  // ── 3. Le vecteur de déplacement : centroïde des échos à ≤ centroideKm
  //       maintenant, et à l'échéance de référence ───────────────────
  const kRef = rang != null ? rang : Math.min(nb - 1, kNow + 6);
  const centroide = k => {
    let sx = 0, sy = 0, n = 0;
    for (const c of large) {
      if (c.dKm > o.centroideKm) continue;
      if (carte.mm(k, c.j, c.i) >= o.seuilMm5) { sx += c.dxKm; sy += c.dyKm; n++; }
    }
    return n >= o.maillesMin ? { x: sx / n, y: sy / n } : null;
  };
  let moveDirDeg = null, moveSpeedKmh = null;
  if (kRef > kNow) {
    const c0 = centroide(kNow), c1 = centroide(kRef);
    if (c0 && c1) {
      const dx = c1.x - c0.x, dy = c1.y - c0.y, d = Math.hypot(dx, dy);
      const h = (kRef - kNow) * PAS_MIN / 60;
      moveDirDeg = Math.round(capDeg(dx, dy));
      moveSpeedKmh = Math.round(d / h);
    }
  }

  // ── 4. Le verdict — même vocabulaire que RainViewer ───────────────
  let trend;
  if (rang != null) trend = rang === kNow ? 'onsite' : 'approaching';
  else if (dNow == null && dFutur == null) trend = 'none';
  else if (dNow == null) trend = 'aside';                 // arrive dans la fenêtre, sans toucher
  else if (dFutur != null && dFutur < dNow - 2) trend = 'aside';
  else trend = 'away';

  const etaAtMs = rang != null ? carte.finMs(rang) : null;
  const etaMin = rang == null ? null : rang === kNow ? 0 : Math.max(1, Math.round((etaAtMs - nowMs) / 60_000));
  return {
    source: 'piaf', passe: carte.passe, passeAgeMin: Math.round(ageMin), fraicheur, refus: null,
    hit: rang != null, rang, etaMin, etaAtMs, mmMax5,
    trend, cpaKm: dNow == null ? null : Math.round(dNow * 10) / 10,
    bearingDeg, secteur: secteur16(bearingDeg), moveDirDeg, moveSpeedKmh,
    attribution: ATTRIBUTION,
  };
}

// ══════════════════════════════════════════════════════════════════════
//  LE LECTEUR — la passe en ligne, par `dernier.passe` et JAMAIS par
//  `runs` (agrume/piaf.py : `dernier` n'avance qu'après TOUTES les
//  écritures ; `runs` peut désigner une passe à moitié publiée).
//
//  Coût : index.json (~1 ko) au plus toutes les `indexMinMs` ; le
//  manifeste (~6 ko) et carte.bin (~26 Mo) UNE fois par passe nouvelle.
//  À 144 passes/jour côté producteur et 10 min de cadence d'ingestion,
//  c'est ~3,7 Go/mois sortants de R2 (sortie gratuite chez Cloudflare).
//  ⚠️ Un échec quelconque GARDE la passe précédente en RAM : `etaPiaf`
//  la jugera sur son ÂGE, et refusera de lui-même passé 35 min. Le
//  lecteur ne fabrique pas de silence, il laisse la donnée vieillir à
//  découvert.
// ══════════════════════════════════════════════════════════════════════
class LecteurPiaf {
  /** @param {{ baseUrl: string, fetch: Function, journal?: Function, indexMinMs?: number }} p */
  constructor(p) {
    this.baseUrl = p.baseUrl.replace(/\/$/, '');
    this.fetch = p.fetch;
    this.journal = p.journal || (() => {});
    this.indexMinMs = p.indexMinMs ?? 60_000;
    this.carte = null;
    this.derniereVerifMs = 0;
    this.enCours = null;
    this.dernierEchec = null;
  }

  /** La carte en RAM (peut être vieille : c'est `etaPiaf` qui juge). */
  courante() { return this.carte; }

  etat(nowMs = Date.now()) {
    return {
      passe: this.carte?.passe ?? null,
      passeAgeMin: this.carte ? Math.round((nowMs - this.carte.passeMs) / 60_000) : null,
      derniereVerifMs: this.derniereVerifMs || null,
      dernierEchec: this.dernierEchec,
    };
  }

  /** Idempotent et réentrant : deux appelants pendant un téléchargement
   *  attendent le MÊME téléchargement. */
  async rafraichir(nowMs = Date.now()) {
    if (this.enCours) return this.enCours;
    if (nowMs - this.derniereVerifMs < this.indexMinMs) return this.carte;
    this.enCours = this._rafraichir(nowMs).finally(() => { this.enCours = null; });
    return this.enCours;
  }

  async _rafraichir(nowMs) {
    this.derniereVerifMs = nowMs;
    try {
      const ri = await this.fetch(`${this.baseUrl}/agrume/piaf/index.json?t=${nowMs}`);
      if (!ri.ok) throw new Error(`index.json HTTP ${ri.status}`);
      const idx = await ri.json();
      const passe = idx?.dernier?.passe;
      if (!passe) throw new Error('index.json sans dernier.passe');
      if (this.carte && this.carte.passe === passe) { this.dernierEchec = null; return this.carte; }

      const jeton = encodeURIComponent(idx.ecrit_le || nowMs);
      const rm = await this.fetch(`${this.baseUrl}/agrume/piaf/${passe}/manifest.json?v=${jeton}`);
      if (!rm.ok) throw new Error(`manifest ${passe} HTTP ${rm.status}`);
      const man = await rm.json();
      const c = man?.service?.calque;
      if (!c?.cle || !c.nb_lat || !c.nb_lon || !c.pas_deg) throw new Error(`manifest ${passe} sans service.calque`);
      if (man.passe !== passe) throw new Error(`manifest ${passe} porte passe=${man.passe} (objets d'une autre passe)`);
      const nbEch = Array.isArray(man.echeances) ? man.echeances.length : 0;
      if (nbEch < 1) throw new Error(`manifest ${passe} sans échéances`);

      const rc = await this.fetch(`${this.baseUrl}/${c.cle}?v=${jeton}`);
      if (!rc.ok) throw new Error(`carte.bin ${passe} HTTP ${rc.status}`);
      const octets = typeof rc.buffer === 'function' ? await rc.buffer() : Buffer.from(await rc.arrayBuffer());
      const carte = new CartePiaf({
        passe, nbLat: c.nb_lat, nbLon: c.nb_lon, pasDeg: c.pas_deg,
        latPremier: c.lat_premier, lonPremier: c.lon_premier,
        nbEcheances: nbEch, octets,
      });
      this.carte = carte;
      this.dernierEchec = null;
      this.journal(`🌧️ PIAF : passe ${passe} en RAM (${(octets.byteLength / 1048576).toFixed(1)} Mo, âge ${Math.round((nowMs - carte.passeMs) / 60_000)} min)`);
      return carte;
    } catch (err) {
      this.dernierEchec = { quand: nowMs, message: String(err?.message || err) };
      this.journal(`⚠️ PIAF : rafraîchissement raté — ${this.dernierEchec.message} (passe en RAM : ${this.carte?.passe ?? 'aucune'})`);
      return this.carte;
    }
  }
}

module.exports = {
  DEFAUTS, PAS_MIN, ATTRIBUTION,
  f16, CartePiaf, LecteurPiaf, etaPiaf,
  fenetre, plusGrandeComposante, capDeg, secteur16,
};
