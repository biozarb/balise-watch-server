// ══════════════════════════════════════════════════════════════════════
//  lib/rafale-pi.js — la RAFALE à venir, LUE dans AROME-PI  (09/09/2026)
//                     Lot « cellule qui approche », lot 2
//
//  ⛔ CE MODULE NE PARLE QUE D'UNE SOURCE : AROME-PI, la prévision
//  immédiate de Météo-France, telle qu'`agrume/ingest_pi_rafale.py` la
//  publie sur R2 (`agrume/pi-rafale/{run}/carte.bin`, float16, maille
//  0,02°, MAXIMUM des 4 points natifs, lats DÉCROISSANTES). Il ne
//  fabrique rien : il lit une tranche, la compare à un seuil, et NOMME
//  le run qui a parlé. Là où il ne peut pas parler (hors emprise, run
//  trop vieux, rien en ligne), il rend un REFUS nommé — jamais une
//  rafale calculée sur une donnée qu'il n'a pas.
//
//  ⛔⛔ CE MODULE N'EST PAS `gust-front.js`, ET LA CONFUSION COÛTERAIT
//  UNE ALERTE SUR DEUX. `gust-front.js` CONSTATE un front de rafales
//  sur le réseau d'observation RADOME et porte le signal `gust_front`,
//  scope `gust_front:<event.id>`. Celui-ci PRÉVOIT sur un modèle et
//  porte le signal `gust_pi`, scope `<beacon_id>`. La clé de dédup est
//  `(user_id, scope, signal)` : deux signaux distincts, deux lignes
//  distinctes, et c'est voulu. Les deux peuvent parler du même orage
//  sans se contredire — l'un dit « c'est passé sur Narbonne il y a
//  12 min », l'autre « ça arrive sur Bugarach dans 40 ».
//
//  ── LES QUATRE PIÈGES, DANS L'ORDRE OÙ ILS MORDENT ───────────────────
//   1. ⛔ LES OCTETS SONT EN MÈTRES PAR SECONDE. Tout ce qui SORT d'ici
//      est en km/h, parce que c'est la langue du pilote et celle du
//      reste de l'app. La conversion se fait UNE fois, à la frontière,
//      et jamais deux fois : un facteur 3,6 appliqué en double donnerait
//      144 km/h là où il y en a 40, et 40 est précisément le seuil.
//   2. ⛔ L'instant nommé d'une échéance est la FIN de sa tranche : le
//      rang k couvre ]run + 15k ; run + 15(k+1)] minutes, et la valeur
//      est le MAXIMUM sur cette tranche. L'ETA se calcule sur la FIN.
//   3. ⛔ LE RUN EST VIEUX PAR CONSTRUCTION, et ça change tout par
//      rapport au lot 1. PIAF sort une passe toutes les 5 min avec 12
//      min de latence ; AROME-PI sort un run par HEURE avec 47 à 68 min
//      de latence (mesuré le 09/09). Un run « frais » a donc déjà une
//      heure. Les seuils d'âge ci-dessous n'ont RIEN à voir avec les 25
//      / 35 min de PIAF, et les recopier ferait refuser tous les runs,
//      tout le temps.
//   4. ⚠️ TRONQUER, PAS ARRONDIR, l'indice de maille : la coordonnée
//      publiée est le coin NORD-OUEST du bloc. Un `Math.round`
//      décalerait d'une maille la moitié des sites.
//
//  ⚠️ CE MODULE N'IMPORTE RIEN DU DÉPÔT WEB, ni `lib/piaf-eta.js`. La
//  tentation était forte : la géométrie est la même, et les deux calques
//  sont même superposables maille pour maille (c'est écrit dans le
//  manifeste). Mais les partager créerait un module dont un changement
//  de seuil de pluie déplacerait une alerte de rafale. Le seul partage
//  est le FORMAT, décrit par les manifestes — pas par du code.
//
//  ── CE QUE REND `rafalePi()` (tous les nombres en unités nommées) ────
//    { source: 'pi-rafale', run, runAgeMin, fraicheur, refus, seuilKmh,
//      hit, cellule, rang, etaMin, etaAtMs, gustKmh, sautHitKmh, sautMinKmh,
//      picKmh, picRang, picAtMs, picDansMin, baseKmh, regimeKmh, sautKmh,
//      trend, cpaKm, bearingDeg, secteur, moveDirDeg, moveSpeedKmh,
//      attribution }
//  `refus` ∈ null | 'hors-emprise' | 'run-trop-vieux' | 'indisponible'
//  `fraicheur` ∈ 'fraiche' (≤ ageAncienMin) | 'ancienne' (≤ ageRefusMin)
//  `trend` ∈ 'onsite' | 'approaching' | 'aside' | 'away' | 'none'
//    — MÊME vocabulaire que `piaf-eta.js` et que RainViewer, pour que le
//    client n'ait pas trois grammaires.
//
//  ⛔⛔ LE SEUIL N'EST PAS DANS CE MODULE — IL VIENT DE LA SURVEILLANCE.
//  `rafalePi(carte, lat, lon, nowMs, { seuilKmh })` applique le seuil
//  qu'on lui donne : `user_watched.seuil_rafale`, celui que le pilote a
//  réglé pour cette balise ou ce site. `DEFAUTS.seuilKmh` n'est qu'un
//  repli. Et le point de lecture suit la même logique : pour une ligne
//  née d'un geste « Surveiller ce site », `index.js` lit AU DÉCOLLAGE
//  (`origin_site` EST sa coordonnée), pas aux balises qui l'entourent —
//  trois balises d'un même déco tombent dans la même maille de 2 km.
//
//  ⛔ DEUX LECTURES DANS LE MÊME OBJET, ET ELLES NE DISENT PAS LA MÊME
//  CHOSE (arbitrage Yann du 09/09) :
//    • `pic*` est le MAXIMUM au-dessus du site sur tout l'horizon — il
//      répond à « qu'est-ce qui m'attend aujourd'hui ». Il existe même
//      quand rien ne franchit le seuil.
//    • `hit`/`rang`/`etaMin`/`gustKmh` décrivent la CELLULE qui arrive :
//      une tache d'au moins `maillesMin` mailles contiguës au-dessus du
//      seuil, dans `rayonKm`. C'est elle qui déclenche le push.
//    Un pic à 42 km/h isolé sur une seule maille donne donc `picKmh =
//    42` et `hit = false` — et c'est le comportement voulu : une maille
//    seule, dans un calque déjà élargi par le maximum, ne fait pas une
//    ligne de grains.
// ══════════════════════════════════════════════════════════════════════
'use strict';

// ── Les seuils — POINTS DE DÉPART, à calibrer sur un épisode réel.
// Chaque chiffre non mesuré est une estimation, et le module les expose
// pour que la note du lot puisse dire lesquels ont été essayés.
const DEFAUTS = Object.freeze({
  // ⛔⛔ `seuilKmh` EST UN REPLI, PAS LE SEUIL. Correction du 09/09 après
  // mesure : un nombre global ne veut rien dire. À 40 km/h, sur le run
  // 15:00 Z d'une journée de tramontane ordinaire, 325 décollages sur
  // 2 066 étaient en alerte — 15,7 %. Le chiffre n'était pas faux
  // (40 km/h de rafale EST sérieux) ; il était inutile, parce qu'il ne
  // distingue pas un site de Chartreuse d'un site de Corbières.
  //
  // Le seuil qui décide est celui de la SURVEILLANCE, passé en `opts` par
  // l'appelant : `user_watched.seuil_rafale`, en km/h, réglé par CE
  // pilote pour CETTE balise ou CE site — « au-delà, je ne veux plus être
  // là ». Ce module n'en fabrique aucun ; il applique celui qu'on lui
  // donne, et le REND dans son résultat (`seuilKmh`) pour que le push
  // puisse le nommer.
  //
  // ⚠️ Ce seuil a été réglé pour du vent MESURÉ par un anémomètre. Ici il
  // juge une rafale PRÉVUE, sur une maille de 2 km réduite par MAXIMUM —
  // ce n'est pas la même grandeur, et le push le dit. Mais c'est le seul
  // nombre au monde qui exprime la limite de ce pilote sur ce site, et en
  // inventer un autre serait pire.
  seuilKmh: 40,         // repli quand la surveillance n'en porte pas
  // ⛔⛔ LA SECONDE CONDITION, ET ELLE EST INDISPENSABLE — mesurée le
  // 09/09. Ancrer le seuil sur la surveillance ne suffit PAS, parce que
  // le seuil que les pilotes ont réglé l'a été pour du vent MESURÉ par
  // un anémomètre, à un point précis. Ici on lit un MAXIMUM de modèle
  // sur une maille de 2 km, elle-même réduite par MAXIMUM de quatre
  // points : la valeur est systématiquement plus haute que ce que
  // l'anémomètre du site lira. Appliquée telle quelle, elle sur-déclenche.
  //
  // Les chiffres, sur le run 15:00 Z du 09/09 (2 066 décollages dans
  // l'emprise) :
  //     seuil 30 km/h — celui que « Surveiller ce site » pose EN DUR —
  //                     857 sites en alerte, 41,5 %
  //     seuil 40 km/h : 314 sites, 15,2 %
  //     seuil 50 km/h : 125 sites,  6,1 %
  // Un signal qui parle à 41 % des sites un jour venté ordinaire n'est
  // pas une alerte, c'est un bruit de fond — et un pilote qui apprend à
  // l'ignorer ne le regardera plus le jour où il compte.
  //
  // D'où le SAUT : la rafale annoncée doit dépasser le fond du moment
  // d'au moins `sautMinKmh`. C'est ce qui distingue une CELLULE d'un
  // RÉGIME venté, et le seuil absolu ne peut pas le faire. Un jour de
  // tramontane à 45 km/h continus, `hit` est vrai partout et `cellule`
  // est faux partout — ce qui est exactement juste : il n'y a pas de
  // cellule, il y a du vent, et le pilote le sait déjà.
  //
  // ⚠️ 15 km/h est un POINT DE DÉPART, pas une mesure. À trancher sur un
  // orage réel rejoué (tools/calibrer_gust_pi.mjs --saut N).
  sautMinKmh: 15,
  maillesMin: 3,        // mailles 0,02° CONTIGUËS (8-connexité) ≥ seuil
  rayonKm: 3,           // l'échelle d'un site de vol
  rechercheKm: 60,      // où l'on cherche la rafale la plus proche (cpa, cap)
  centroideKm: 40,      // fenêtre du centroïde pour le vecteur de déplacement
  // ⛔⛔ LES DEUX SEULS CHIFFRES QUI NE SE RECOPIENT PAS DE PIAF.
  // Un run AROME-PI naît vieux : 47 à 68 min de latence, un run par
  // heure. Les 25/35 min de PIAF refuseraient TOUS les runs.
  //   120 min = le run suivant aurait dû arriver. On parle encore, mais
  //             on dit « run ancien » et on donne l'âge.
  //   210 min = deux runs entiers manqués, et 14 des 24 échéances déjà
  //             passées. Au-delà, la moitié du ruban décrit le passé :
  //             annoncer une rafale « dans 20 min » sur un run de 3 h 30
  //             serait un chiffre juste sur une carte périmée.
  ageAncienMin: 120,
  ageRefusMin: 210,
});

const PAS_MIN = 15;
const NB_ECHEANCES = 24;
const KM_PAR_DEG_LAT = 111.2;
const MS_VERS_KMH = 3.6;

const ATTRIBUTION = 'Source : Météo-France — AROME-PI, Licence Ouverte 2.0';

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
//  LA CARTE — un run en RAM, tel que R2 le sert
// ══════════════════════════════════════════════════════════════════════
/**
 * @param {object} p
 * @param {string} p.run            ISO Z du run (`manifest.run`)
 * @param {number} p.nbLat @param {number} p.nbLon
 * @param {number} p.pasDeg         0,02 (`service.calque.pas_deg`)
 * @param {number} p.latPremier     coin NW de la première ligne (NORD)
 * @param {number} p.lonPremier
 * @param {number} p.nbEcheances    24
 * @param {Uint8Array|Buffer} p.octets  carte.bin brut, (echeance, lat, lon) <f2
 */
class CarteRafale {
  constructor(p) {
    this.run = p.run;
    this.runMs = Date.parse(p.run);
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
    if (!Number.isFinite(this.runMs)) throw new Error(`run illisible : ${p.run}`);
  }

  /** ⛔ Rafale en MÈTRES PAR SECONDE — l'unité des octets. Personne
   *  d'autre que `kmh()` n'a le droit de lire ça sans le savoir. */
  ms(k, j, i) { return f16(this.u16[k * this.parEcheance + j * this.nbLon + i]); }

  /** Rafale en km/h. ⚠️ LE SEUL point de conversion du module. */
  kmh(k, j, i) { return this.ms(k, j, i) * MS_VERS_KMH; }

  /** Fin de la tranche du rang k, en ms epoch — ENTIER. */
  finMs(k) { return this.runMs + (k + 1) * PAS_MIN * 60_000; }

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
/** Le nom du secteur d'où VIENT la rafale, pour un push (« par le SW »). */
function secteur16(deg) {
  if (deg == null || !Number.isFinite(deg)) return null;
  return NOMS_16[Math.round(((deg % 360) + 360) % 360 / 22.5) % 16];
}

/** Les mailles à ≤ rayonKm du site : [{ j, i, dKm, dxKm, dyKm }]. */
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

/** Taille de la plus grande composante 8-connexe parmi `sel`. Le test
 *  « ≥ maillesMin mailles CONTIGUËS » refuse une maille isolée — qui,
 *  dans un calque déjà élargi par le maximum, ne fait pas une ligne de
 *  grains — et accepte une vraie cellule. */
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
//  LA LECTURE — le pic au-dessus du site, ET la cellule qui arrive
// ══════════════════════════════════════════════════════════════════════
function refus(carte, nowMs, raison, seuilKmh, sautMinKmh, extra) {
  const ageMin = carte ? (nowMs - carte.runMs) / 60_000 : null;
  return Object.assign({
    source: 'pi-rafale', run: carte?.run ?? null,
    runAgeMin: ageMin == null ? null : Math.round(ageMin),
    fraicheur: null, refus: raison, seuilKmh,
    hit: false, rang: null, etaMin: null, etaAtMs: null, gustKmh: null,
    regimeKmh: null, sautHitKmh: null, cellule: false, sautMinKmh,
    picKmh: null, picRang: null, picAtMs: null, picDansMin: null,
    baseKmh: null, sautKmh: null,
    trend: null, cpaKm: null, bearingDeg: null, secteur: null,
    moveDirDeg: null, moveSpeedKmh: null,
    attribution: ATTRIBUTION,
  }, extra || {});
}

/**
 * @param {CarteRafale|null} carte
 * @param {number} lat @param {number} lon
 * @param {number} nowMs
 * @param {object} [opts]  surcharge de DEFAUTS
 */
function rafalePi(carte, lat, lon, nowMs, opts) {
  const o = Object.assign({}, DEFAUTS, opts || {});
  if (!carte) return refus(null, nowMs, 'indisponible', o.seuilKmh, o.sautMinKmh);
  const ageMin = (nowMs - carte.runMs) / 60_000;
  if (ageMin > o.ageRefusMin) return refus(carte, nowMs, 'run-trop-vieux', o.seuilKmh, o.sautMinKmh);
  if (!(lat != null && lon != null) || !carte.dansEmprise(lat, lon)) return refus(carte, nowMs, 'hors-emprise', o.seuilKmh, o.sautMinKmh);
  const fraicheur = ageMin <= o.ageAncienMin ? 'fraiche' : 'ancienne';

  // La tranche qui contient MAINTENANT. Une horloge en avance sur le run
  // (âge négatif) tombe au rang 0, pas en dehors du tableau.
  // ⚠️ Et l'âge d'un run frais vaut DÉJÀ ~60 min, soit kNow ≈ 4 : les
  // quatre premières échéances d'un run sont du passé avant même qu'on
  // les lise. C'est normal, c'est la latence du producteur, et c'est
  // pourquoi l'horizon utile est de 6 h et non de 6 h moins rien.
  const nb = carte.nbEcheances;
  const kNow = Math.min(nb - 1, Math.max(0, Math.floor(ageMin / PAS_MIN)));

  const large = fenetre(carte, lat, lon, o.rechercheKm);
  const proche = large.filter(c => c.dKm <= o.rayonKm);

  // ── 1. LE PIC AU-DESSUS DU SITE, sur tout l'horizon restant ────────
  // ⛔ Il existe même quand rien ne franchit le seuil : c'est la réponse
  // à « qu'est-ce qui m'attend », et un site où la rafale monte à 35
  // km/h doit pouvoir le dire sans déclencher d'alerte.
  let picKmh = null, picRang = null, baseKmh = null;
  const parTranche = [];
  for (let k = kNow; k < nb; k++) {
    let mx = null;
    for (const c of proche) {
      const v = carte.kmh(k, c.j, c.i);
      if (!(v >= 0)) continue;   // NaN = maille non renseignée : ni vent ni calme
      if (mx == null || v > mx) mx = v;
    }
    if (mx == null) continue;
    parTranche.push(mx);
    if (k === kNow) baseKmh = mx;
    if (picKmh == null || mx > picKmh) { picKmh = mx; picRang = k; }
  }

  // ── 1 bis. LE RÉGIME DU SITE — la MÉDIANE DE SA PROPRE JOURNÉE ─────
  // ⛔⛔ CE CHIFFRE A ÉTÉ REDÉFINI DEUX FOIS LE 09/09, ET LES DEUX RATÉS
  // VALENT D'ÊTRE ÉCRITS.
  //
  //  1ʳᵉ version — le maximum AU-DESSUS DU SITE dans la tranche
  //    courante. Faux : quand la cellule est DÉJÀ là, ce maximum EST la
  //    cellule, le saut vaut zéro, et le signal se tait au pire moment.
  //    Attrapé par le banc (§6 ter).
  //  2ᵉ version — la médiane SPATIALE sur les 60 km alentour. Moins
  //    faux, mais elle mêle des plaines et des crêtes : un site de crête
  //    dépasse la médiane régionale tous les jours de l'année. Mesuré :
  //    207 décollages sur 2 066 déclaraient une « cellule » au seuil de
  //    30 km/h, un jour sans orage.
  //
  //  3ᵉ version, celle-ci — la médiane TEMPORELLE de ce site sur son
  //  propre horizon. C'est « le vent que ce site aura aujourd'hui »,
  //  vu par le même modèle, à la même maille, au même endroit : le
  //  relief s'annule, puisqu'il est des deux côtés de la soustraction.
  //  Une cellule occupe deux ou trois tranches sur vingt — elle ne
  //  déplace pas la médiane ; un régime venté la déplace tout entière.
  //
  //  ⚠️ Médiane et non moyenne : une ligne de grains à 90 km/h tirerait
  //  une moyenne vers le haut et masquerait son propre saut.
  //  ⚠️ Et il faut au moins 6 tranches pour qu'une médiane veuille dire
  //  quelque chose. En fin de run (kNow proche de 24), il n'y en a plus
  //  assez : `regimeKmh` devient null, `cellule` est faux, et le refus
  //  est NOMMÉ par `regimeKmh: null` plutôt que fabriqué.
  let regimeKmh = null;
  if (parTranche.length >= 6) {
    const tri = parTranche.slice().sort((x, y) => x - y);
    regimeKmh = tri[tri.length >> 1];
  }

  // ── 2. LA CELLULE QUI ARRIVE — première tranche où une TACHE d'au
  //       moins `maillesMin` mailles contiguës touche le site ─────────
  let rang = null, gustKmh = null;
  for (let k = kNow; k < nb; k++) {
    const sel = []; let mx = 0;
    for (const c of proche) {
      const v = carte.kmh(k, c.j, c.i);
      if (!(v >= 0)) continue;
      if (v > mx) mx = v;
      if (v >= o.seuilKmh) sel.push(c);
    }
    if (sel.length >= o.maillesMin && plusGrandeComposante(sel) >= o.maillesMin) {
      rang = k; gustKmh = Math.round(mx); break;
    }
  }

  // ── 3. La rafale la plus proche MAINTENANT (cpa, cap d'où ça vient),
  //       et la distance minimale qu'elle atteindra sur l'horizon ──────
  let dNow = null, bearingDeg = null, dFutur = null;
  for (let k = kNow; k < nb; k++) {
    let dmin = null, best = null;
    for (const c of large) {
      if (carte.kmh(k, c.j, c.i) >= o.seuilKmh && (dmin == null || c.dKm < dmin)) { dmin = c.dKm; best = c; }
    }
    if (k === kNow) {
      dNow = dmin;
      if (best && dmin > 0) bearingDeg = Math.round(capDeg(best.dxKm, best.dyKm));
    } else if (dmin != null && (dFutur == null || dmin < dFutur)) dFutur = dmin;
  }

  // ── 4. Le vecteur de déplacement : centroïde des mailles ventées à
  //       ≤ centroideKm maintenant, et à l'échéance de référence ──────
  // ⚠️ `kNow + 2` (30 min) et non `+ 6` comme pour la pluie : le pas est
  // ici de 15 min, pas de 5. Garder 6 mesurerait un déplacement sur
  // 1 h 30, pendant laquelle une cellule change de forme autant que de
  // place — la « vitesse » obtenue serait celle d'un objet qui n'existe
  // plus.
  const kRef = rang != null ? rang : Math.min(nb - 1, kNow + 2);
  const centroide = k => {
    let sx = 0, sy = 0, n = 0;
    for (const c of large) {
      if (c.dKm > o.centroideKm) continue;
      if (carte.kmh(k, c.j, c.i) >= o.seuilKmh) { sx += c.dxKm; sy += c.dyKm; n++; }
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

  // ── 5. Le verdict — MÊME vocabulaire que `piaf-eta.js` ─────────────
  let trend;
  if (rang != null) trend = rang === kNow ? 'onsite' : 'approaching';
  else if (dNow == null && dFutur == null) trend = 'none';
  else if (dNow == null) trend = 'aside';                 // arrive dans la fenêtre, sans toucher
  else if (dFutur != null && dFutur < dNow - 2) trend = 'aside';
  else trend = 'away';

  const etaAtMs = rang != null ? carte.finMs(rang) : null;
  const etaMin = rang == null ? null : rang === kNow ? 0 : Math.max(1, Math.round((etaAtMs - nowMs) / 60_000));
  const picAtMs = picRang == null ? null : carte.finMs(picRang);
  return {
    source: 'pi-rafale', run: carte.run, runAgeMin: Math.round(ageMin), fraicheur, refus: null,
    seuilKmh: o.seuilKmh,
    hit: rang != null, rang, etaMin, etaAtMs, gustKmh,
    // ⛔ `hit` dit « ça dépasse ton seuil ». `cellule` dit « et ça se
    // détache du fond » — c'est CELUI-LÀ qui pousse. Les deux sont
    // publiés : un jour de tramontane, `hit` vrai et `cellule` faux est
    // une information utile, pas un raté.
    // ⛔ Le saut se mesure contre le RÉGIME du secteur, pas contre le
    // maximum au-dessus du site — qui contient déjà la cellule quand
    // elle est arrivée.
    regimeKmh: regimeKmh == null ? null : Math.round(regimeKmh),
    sautHitKmh: (gustKmh == null || regimeKmh == null) ? null : Math.round(gustKmh - regimeKmh),
    cellule: rang != null && regimeKmh != null && (gustKmh - regimeKmh) >= o.sautMinKmh,
    sautMinKmh: o.sautMinKmh,
    picKmh: picKmh == null ? null : Math.round(picKmh),
    picRang, picAtMs,
    picDansMin: picAtMs == null ? null : Math.max(0, Math.round((picAtMs - nowMs) / 60_000)),
    baseKmh: baseKmh == null ? null : Math.round(baseKmh),
    // Le saut du PIC, contre le régime — utile pour la fiche de site,
    // qui parle de la journée et pas d'un déclenchement.
    sautKmh: (picKmh == null || regimeKmh == null) ? null : Math.round(picKmh - regimeKmh),
    trend, cpaKm: dNow == null ? null : Math.round(dNow * 10) / 10,
    bearingDeg, secteur: secteur16(bearingDeg), moveDirDeg, moveSpeedKmh,
    attribution: ATTRIBUTION,
  };
}

// ══════════════════════════════════════════════════════════════════════
//  LE LECTEUR — le run en ligne, par `dernier.run` et JAMAIS par `runs`
//  (agrume/pi_rafale.py : `dernier` n'avance qu'après TOUTES les
//  écritures ; `runs` peut désigner un run à moitié publié).
//
//  Coût : index.json (~1 ko) au plus toutes les `indexMinMs` ; le
//  manifeste (~8 ko) et carte.bin (16,1 Mo) UNE fois par run nouveau.
//  À 24 runs/jour, c'est ~11,6 Go/mois sortants de R2 (sortie gratuite
//  chez Cloudflare).
//
//  ⚠️ `indexMinMs` vaut 5 min ici, contre 1 min pour PIAF, et c'est
//  proportionné : le producteur ne sort qu'un run par heure. Interroger
//  l'index toutes les minutes ferait 60 requêtes pour apprendre 1 fois
//  qu'il a bougé.
//
//  ⚠️ Un échec quelconque GARDE le run précédent en RAM : `rafalePi()`
//  le jugera sur son ÂGE, et refusera de lui-même passé 210 min. Le
//  lecteur ne fabrique pas de silence, il laisse la donnée vieillir à
//  découvert.
// ══════════════════════════════════════════════════════════════════════
class LecteurRafale {
  /** @param {{ baseUrl: string, fetch: Function, journal?: Function, indexMinMs?: number }} p */
  constructor(p) {
    this.baseUrl = p.baseUrl.replace(/\/$/, '');
    this.fetch = p.fetch;
    this.journal = p.journal || (() => {});
    this.indexMinMs = p.indexMinMs ?? 300_000;
    this.carte = null;
    this.derniereVerifMs = 0;
    this.enCours = null;
    this.dernierEchec = null;
  }

  courante() { return this.carte; }

  etat(nowMs = Date.now()) {
    return {
      run: this.carte?.run ?? null,
      runAgeMin: this.carte ? Math.round((nowMs - this.carte.runMs) / 60_000) : null,
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
      const ri = await this.fetch(`${this.baseUrl}/agrume/pi-rafale/index.json?t=${nowMs}`);
      if (!ri.ok) throw new Error(`index.json HTTP ${ri.status}`);
      const idx = await ri.json();
      const run = idx?.dernier?.run;
      if (!run) throw new Error('index.json sans dernier.run');
      if (this.carte && this.carte.run === run) { this.dernierEchec = null; return this.carte; }

      const jeton = encodeURIComponent(idx.ecrit_le || nowMs);
      const rm = await this.fetch(`${this.baseUrl}/agrume/pi-rafale/${run}/manifest.json?v=${jeton}`);
      if (!rm.ok) throw new Error(`manifest ${run} HTTP ${rm.status}`);
      const man = await rm.json();
      const c = man?.service?.calque;
      if (!c?.cle || !c.nb_lat || !c.nb_lon || !c.pas_deg) throw new Error(`manifest ${run} sans service.calque`);
      if (man.run !== run) throw new Error(`manifest ${run} porte run=${man.run} (objets d'un autre run)`);
      const nbEch = Array.isArray(man.echeances) ? man.echeances.length : 0;
      if (nbEch < 1) throw new Error(`manifest ${run} sans échéances`);
      // ⛔ L'UNITÉ EST VÉRIFIÉE À LA LECTURE, PAS SUPPOSÉE. Tout ce
      // module multiplie par 3,6 ; le jour où l'ingestion publierait des
      // km/h, chaque rafale serait affichée à 144 là où il y en a 40 —
      // au-dessus du seuil, donc en push, et parfaitement plausible.
      if (man?.parametre?.unite !== 'm/s') throw new Error(`manifest ${run} annonce l'unité ${man?.parametre?.unite} (attendu m/s)`);

      const rc = await this.fetch(`${this.baseUrl}/${c.cle}?v=${jeton}`);
      if (!rc.ok) throw new Error(`carte.bin ${run} HTTP ${rc.status}`);
      const octets = typeof rc.buffer === 'function' ? await rc.buffer() : Buffer.from(await rc.arrayBuffer());
      const carte = new CarteRafale({
        run, nbLat: c.nb_lat, nbLon: c.nb_lon, pasDeg: c.pas_deg,
        latPremier: c.lat_premier, lonPremier: c.lon_premier,
        nbEcheances: nbEch, octets,
      });
      this.carte = carte;
      this.dernierEchec = null;
      this.journal(`💨 rafale AROME-PI : run ${run} en RAM (${(octets.byteLength / 1048576).toFixed(1)} Mo, âge ${Math.round((nowMs - carte.runMs) / 60_000)} min)`);
      return carte;
    } catch (err) {
      this.dernierEchec = { quand: nowMs, message: String(err?.message || err) };
      this.journal(`⚠️ rafale AROME-PI : rafraîchissement raté — ${this.dernierEchec.message} (run en RAM : ${this.carte?.run ?? 'aucun'})`);
      return this.carte;
    }
  }
}

module.exports = {
  DEFAUTS, PAS_MIN, NB_ECHEANCES, MS_VERS_KMH, ATTRIBUTION,
  f16, CarteRafale, LecteurRafale, rafalePi,
  fenetre, plusGrandeComposante, capDeg, secteur16,
};
