// ══════════════════════════════════════════════════════════════════
//  phenomenon-delta — le Δ MESURÉ d'un phénomène, calculé côté serveur
//  (Lot 7, route B, 04/08/2026)
//
//  ⚠️ CE MODULE NE CALCULE QUE LE MESURÉ. Le Δ PRÉVU (Open-Meteo, pic
//  à venir, ce qui déclenche l'alerte) vit dans index.js et n'a rien à
//  faire ici. Les confondre est l'erreur que ce module existe pour
//  rendre impossible : le mesuré dit ce qu'il se passe MAINTENANT, le
//  prévu dit ce qui est attendu dans les 36 h. Une fiche qui affiche
//  l'un en croyant l'autre ment à un pilote sur un outil de sécurité.
//
//  Toute la physique vient de ./pressure.cjs, qui est GÉNÉRÉ depuis
//  le dépôt web (cf. son en-tête). Rien n'est recalculé ici : ce
//  fichier n'est que de la plomberie — il va chercher les relevés que
//  le serveur a déjà en mémoire, les met dans la forme que la physique
//  attend, et rend le résultat.
//
//  Convention de nommage du dossier : `.cjs` = fichier généré,
//  `.js` = écrit à la main.
// ══════════════════════════════════════════════════════════════════
'use strict';

const P = require('./pressure.cjs');

/** Fenêtre de la courbe observée, alignée sur celle de la fiche. */
const OBSERVED_HOURS = 36;

/**
 * Écart de temps maximal toléré entre les deux relevés d'un même Δ.
 *
 * ⚠️ MÊME VALEUR QUE LA TOLÉRANCE DE `deltaSeries` (45 min), et ce
 * n'est pas une coïncidence : c'est une INCOHÉRENCE DU MODULE qu'on
 * ferme ici. La COURBE refuse depuis toujours d'apparier deux points
 * distants de plus de 45 min — « un Δ calculé entre deux instants
 * éloignés n'est pas une mesure bruitée, c'est une mesure d'autre
 * chose ». Le Δ INSTANTANÉ, lui, soustrayait les deux derniers relevés
 * sans jamais regarder leur écart d'âge.
 *
 * Constaté le 04/08/2026 : sur 27 phénomènes, 16 ont leurs deux ancres
 * dans des sources différentes, avec 54 à 124 MINUTES d'écart entre les
 * deux relevés. Le point le plus à droite de la courbe pouvait donc être
 * refusé par deltaSeries pendant que le chiffre affiché juste à côté,
 * lui, était calculé — deux règles contradictoires dans le même panneau.
 *
 * On ne SUPPRIME pas le Δ pour autant : ce serait taire l'information
 * sur 16 axes d'un coup, et c'est une décision de produit, pas de code.
 * On la RAPPORTE (`pairSpanMin`, `beyondTolerance`), pour que la fiche
 * puisse la dire au pilote et que la question se tranche sur pièces.
 */
const PAIR_TOLERANCE_MS = 45 * 60 * 1000;

/**
 * Points bruts d'historique → relevés que la physique sait normaliser.
 *
 * Reproduit `fetchPressureHistory` d'AppContext, et c'est volontaire
 * qu'on le reproduise ICI plutôt que d'inventer autre chose : METAR et
 * SwissMetNet servent `{ t, p, reduction?, tempC }` et portent leur
 * convention point par point (Visp et St-Gall sont en repli QNH au
 * milieu d'une source QFF) ; Météo-France et AEMET servent un `pmer`
 * qui est du QFF NATIF, déjà réduit avec la température réelle, et
 * qu'il ne faut donc surtout pas reconvertir.
 */
function readingsFromHistory(station, points) {
  const src = String(station.id).split(':')[0];
  const out = [];
  if (src === 'metar' || src === 'smn') {
    for (const p of points || []) {
      if (!Number.isFinite(p.t) || p.p == null) continue;
      out.push({
        raw: p.p,
        reduction: p.reduction || station.reduction,
        elev: station.alt,
        tempC: p.tempC == null ? null : p.tempC,
        resolutionHpa: station.resolutionHpa,
        t: p.t,
      });
    }
    return out;
  }
  for (const p of points || []) {
    const v = p.pressure != null ? p.pressure : p.pmer;
    if (v == null || !Number.isFinite(p.t)) continue;
    out.push(P.readingFromQff(v, station.alt, p.t, station.resolutionHpa));
  }
  return out;
}

/** Résumé d'une ancre, tel que la fiche a besoin de l'afficher. */
function anchorPayload(match, referential, now) {
  if (!match) return null;
  const st = referential.find(s => s.id === match.station.id) || match.station;
  return {
    id: st.id, nom: st.nom, source: st.source, code: st.code,
    lat: st.lat, lon: st.lon, alt: st.alt,
    reduction: st.reduction,
    km: Math.round(match.km * 10) / 10,
    // `forced` = ancre DÉCLARÉE sur le phénomène (station_a/station_b),
    // par opposition à un appariement par proximité. La distinction
    // compte : une ancre curée engage le jugement de Yann, une ancre
    // trouvée par distance n'engage que la géométrie.
    forced: !!match.forced,
    t: st.t || null,
    ageMin: st.t ? Math.round((now - st.t) / 60000) : null,
  };
}

/**
 * Le Δ mesuré d'un phénomène, et de quoi le justifier à l'écran.
 *
 * @param row          ligne brute de `foehn_axes` (snake_case).
 * @param referential  sortie de `buildPressureReferential`.
 * @param historyFor   (station) => points bruts, ou [] si indisponible.
 * @param userOverride seuil du compte, s'il en a un. `null` sinon.
 */
async function computePhenomenonDelta({ row, referential, historyFor, userOverride = null }) {
  const now = Date.now();
  const ph = P.phenomenonFromRow(row);
  const anchors = P.resolveAnchors(ph, referential);

  const base = {
    id: ph.id,
    label: ph.label,
    kind: ph.kind,
    // Les seuils tels que la RÈGLE les voit, pas tels que la base les
    // stocke : `phenomenonFromRow` a déjà appliqué ses replis.
    thresholds: {
      hpa: ph.thresholdHpa,
      strongHpa: ph.thresholdStrongHpa,
      activeSign: ph.activeSign,
      userOverride,
    },
    anchors: {
      a: anchorPayload(anchors.a, referential, now),
      b: anchorPayload(anchors.b, referential, now),
      missing: anchors.missing,
    },
    measured: null,
    series: [],
    reason: null,
  };

  if (!anchors.a || !anchors.b) {
    // Distinguer les deux causes : une ancre DÉCLARÉE introuvable est un
    // problème de curation (faute de frappe dans station_a), une absence
    // d'appariement est un problème de couverture (pas de station de
    // pression à moins de PRESSURE_MAX_KM). Le remède n'est pas le même.
    base.reason = anchors.missing.length ? 'ancre-declaree-introuvable' : 'aucune-station-a-portee';
    return base;
  }

  // ── Le Δ maintenant ───────────────────────────────────────────────
  const stA = referential.find(s => s.id === anchors.a.station.id);
  const stB = referential.find(s => s.id === anchors.b.station.id);
  const ra = stA ? P.readingFromStation(stA) : null;
  const rb = stB ? P.readingFromStation(stB) : null;
  if (!ra || !rb) {
    // Station appariée mais sans pression exploitable à cet instant :
    // l'ancre est bonne, c'est le relevé qui manque. Dire « pas de
    // station » ici enverrait chercher au mauvais endroit.
    base.reason = 'releve-indisponible';
    return base;
  }

  const na = P.normalizePressure(ra), nb = P.normalizePressure(rb);
  const d = P.pressureDelta(na, nb);
  if (d.delta == null) {
    // normalizePressure a REFUSÉ de convertir — température manquante
    // sur un QNH, ou station au-dessus de PRESSURE_MAX_ALT. Refuser est
    // le comportement voulu : un Δ faux est pire qu'un Δ absent.
    base.reason = na.reason || nb.reason || 'conversion-impossible';
    base.measured = {
      delta: null, uncertaintyHpa: d.uncertaintyHpa,
      level: 0, direction: 'none',
      convertedA: na.converted, convertedB: nb.converted,
      tA: ra.t || null, tB: rb.t || null,
    };
    return base;
  }

  base.measured = {
    delta: Math.round(d.delta * 100) / 100,
    uncertaintyHpa: Math.round(d.uncertaintyHpa * 100) / 100,
    // ⚠️ Niveau du Δ MESURÉ. Ce n'est PAS le niveau qui déclenche le
    // push — celui-là se calcule sur le pic PRÉVU, dans index.js. Les
    // deux peuvent différer, et c'est normal : la mesure dit le présent,
    // la prévision dit les 36 h à venir.
    level: P.phenomenonLevel(d.delta, ph, userOverride),
    direction: P.phenomenonDirection(d.delta, ph, userOverride),
    convertedA: na.converted, convertedB: nb.converted,
    tA: ra.t || null, tB: rb.t || null,
    ageMinA: ra.t ? Math.round((now - ra.t) / 60000) : null,
    ageMinB: rb.t ? Math.round((now - rb.t) / 60000) : null,
    // Écart de temps ENTRE LES DEUX relevés — à ne pas confondre avec
    // leur âge. Deux relevés vieux de 2 h mais simultanés donnent un Δ
    // parfaitement valable ; deux relevés frais mais distants de 2 h,
    // non. C'est la simultanéité qui fait la mesure, pas la fraîcheur.
    pairSpanMin: (ra.t && rb.t) ? Math.round(Math.abs(ra.t - rb.t) / 60000) : null,
    beyondTolerance: (ra.t && rb.t) ? Math.abs(ra.t - rb.t) > PAIR_TOLERANCE_MS : null,
    // Les deux ancres viennent-elles de la même source ? Deux sources
    // au MÊME aéroport ne rendent pas le même nombre (constaté le
    // 04/08 : jusqu'à 5 hPa d'écart entre le METAR converti et le
    // `pmer` de Météo-France, sur des seuils de 2 à 6 hPa). Sur des
    // ancres homogènes, ce biais se compense dans la soustraction ;
    // sur des ancres mixtes, il entre entier dans le Δ.
    mixedSources: stA.source !== stB.source,
  };

  // ── La courbe des 36 dernières heures ─────────────────────────────
  try {
    const [ha, hb] = await Promise.all([historyFor(stA), historyFor(stB)]);
    base.series = P.deltaSeries(readingsFromHistory(stA, ha), readingsFromHistory(stB, hb))
      .map(p => ({
        t: p.t,
        delta: Math.round(p.delta * 100) / 100,
        uncertaintyHpa: Math.round(p.uncertaintyHpa * 100) / 100,
      }));
  } catch {
    // La courbe est un confort, le Δ instantané est l'essentiel : on
    // rend ce qu'on a plutôt que de faire échouer toute la route.
    base.series = [];
    base.seriesError = true;
  }
  return base;
}

module.exports = { computePhenomenonDelta, readingsFromHistory, OBSERVED_HOURS, PAIR_TOLERANCE_MS };
