'use strict';
// ══════════════════════════════════════════════════════════════════════
//  lib/signaux.js — LE REGISTRE des signaux de veille        (09/09/2026)
//                   P1.1 de la revue d'intégration
//
//  ⛔ UNE SEULE LISTE. Avant ce fichier, chaque signal avait son niveau,
//  sa fenêtre de rappel, son tag, sa préférence `sig_*` et son kill
//  switch écrits INLINE dans neuf blocs de `pollAndNotify`, et le client
//  tenait trois listes parallèles. Les deux bugs du P0 (colonne oubliée
//  dans le `select=`, scope `site:` ignoré par le client) viennent de là :
//  ajouter un signal = toucher six endroits, et en oublier un.
//
//  Module PUR : zéro import, zéro effet. `index.js` en DÉRIVE le select
//  des préférences (`COLONNES_PREFS`) et sert le registre au client
//  (`GET /signals/catalog`). Le banc `tools/banc_signaux_09-09.mjs`
//  vérifie que chaque signal a sa clé dans les 8 locales et sa colonne
//  dans `FW_DEFAULTS`.
//
//  CE QUE LE REGISTRE DÉCRIT : le CONTRAT DE LIVRAISON d'un signal (à
//  quel niveau, à quel rythme, sous quel tag, gouverné par quelle
//  préférence et quel interrupteur). CE QU'IL NE DÉCRIT PAS : la
//  détection — seuils, fenêtres, physique — qui reste dans les modules.
//
//  `famille` : mesure (une balise a vu) · observe (un réseau tiers a vu :
//  foudre, radar, RADOME) · modele (une prévision) · composite.
//  `scopes`  : les familles de scope que ce signal écrit en base —
//  `beacon` = `<beacon_id>` nu, les autres sont préfixés (`site:`,
//  `zone:`, `dept:`, `axis:`, `gust_front:`).
// ══════════════════════════════════════════════════════════════════════

const SIGNAUX = Object.freeze({
  wind_threshold: Object.freeze({
    slug: 'windThreshold', famille: 'mesure', niveau: 2,
    rappelMs: null, // repeat_interval_min, le plus court du groupe (lot 5)
    ackable: true, voix: false, kind: 'siteWatch',
    pref: null, interrupteur: null,
    scopes: ['site'],
    tag: scope => `alert-site-${scope.replace(/^site:/, '')}`,
  }),
  wind_surge: Object.freeze({
    slug: 'windSurge', famille: 'mesure', niveau: 3,
    rappelMs: 15 * 60_000, ackable: true, voix: true, kind: 'flightwatch',
    pref: 'sig_wind_surge', interrupteur: null,
    scopes: ['beacon'],
    tag: scope => `fw-wind_surge-${scope}`,
  }),
  breeze_reversal: Object.freeze({
    slug: 'breezeReversal', famille: 'mesure', niveau: 2,
    rappelMs: 15 * 60_000, ackable: true, voix: false, kind: 'flightwatch',
    pref: 'sig_breeze_reversal', interrupteur: null,
    scopes: ['zone', 'beacon'],
    tag: scope => `fw-breeze_reversal-${scope}`,
  }),
  pressure_drop: Object.freeze({
    slug: 'pressureDrop', famille: 'mesure', niveau: 2,
    rappelMs: 15 * 60_000, ackable: true, voix: false, kind: 'flightwatch',
    pref: 'sig_pressure_drop', interrupteur: null,
    scopes: ['beacon'],
    tag: scope => `fw-pressure_drop-${scope}`,
  }),
  convection: Object.freeze({
    slug: 'convection', famille: 'modele', niveau: 2,
    rappelMs: 15 * 60_000, ackable: true, voix: false, kind: 'flightwatch',
    pref: 'sig_convection', interrupteur: null,
    scopes: ['beacon'],
    tag: scope => `fw-convection-${scope}`,
  }),
  vigilance: Object.freeze({
    slug: 'vigilance', famille: 'observe', niveau: 2, // 3 si rouge
    rappelMs: 15 * 60_000, ackable: true, voix: true, kind: 'flightwatch',
    pref: 'sig_vigilance', interrupteur: 'FW_VIGILANCE_ENABLED',
    scopes: ['dept'],
    tag: scope => `fw-vigilance-${scope}`,
  }),
  lightning: Object.freeze({
    slug: 'lightning', famille: 'observe', niveau: 3,
    rappelMs: 10 * 60_000, ackable: true, voix: true, kind: 'flightwatch',
    pref: 'sig_lightning', interrupteur: 'FW_LIGHTNING_ENABLED',
    scopes: ['beacon'],
    tag: scope => `fw-lightning-${scope}`,
  }),
  precip: Object.freeze({
    slug: 'precip', famille: 'observe+modele', niveau: 2,
    rappelMs: 15 * 60_000, ackable: true, voix: false, kind: 'flightwatch',
    pref: 'sig_precip', interrupteur: 'FW_PRECIP_ENABLED',
    scopes: ['beacon'],
    tag: scope => `fw-precip-${scope}`,
  }),
  gust_pi: Object.freeze({
    slug: 'gustPi', famille: 'modele', niveau: 2,
    rappelMs: 15 * 60_000, ackable: true, voix: false, kind: 'flightwatch',
    pref: 'sig_gust_pi', interrupteur: 'PI_RAFALE_ENABLED',
    scopes: ['site', 'beacon'],
    tag: scope => scope.startsWith('site:') ? `fw-gust_pi-site-${scope.slice(5)}` : `fw-gust_pi-${scope}`,
  }),
  convective_cell: Object.freeze({
    slug: 'convectiveCell', famille: 'composite', niveau: 2,
    rappelMs: 15 * 60_000, ackable: true, voix: false, kind: 'flightwatch',
    pref: 'sig_convective_cell', interrupteur: 'CELLULE_ENABLED',
    scopes: ['site', 'beacon'],
    tag: scope => `fw-cellule-${scope}`,
  }),
  foehn: Object.freeze({
    slug: 'foehn', famille: 'modele', niveau: 2, // 3 au pic fort
    rappelMs: null, // FOEHN_ALERT_REPEAT_MS
    ackable: true, voix: true, kind: 'flightwatch',
    pref: null, interrupteur: 'FOEHN_REQUIRE_ARMED',
    scopes: ['axis'],
    tag: scope => `fw-foehn-${scope.replace(/^axis:/, '')}`,
  }),
  gust_front: Object.freeze({
    slug: 'gustFront', famille: 'observe', niveau: 2,
    rappelMs: null, ackable: false, voix: false, kind: 'flightwatch',
    pref: 'sig_gust_front', interrupteur: 'GUST_FRONT_SHADOW',
    scopes: ['event'], table: 'gust_front_events',
    tag: scope => `fw-gust_front-${scope}`,
  }),
});

/** Les colonnes `sig_*` de `user_surveillance` que le poll doit lire —
 *  DÉRIVÉES du registre, plus jamais tapées à la main (le bug P0.1). */
const COLONNES_PREFS = Object.freeze(
  [...new Set(Object.values(SIGNAUX).map(s => s.pref).filter(Boolean))]
);

/** `scope` → sa famille : `beacon` pour un id nu, sinon le préfixe. */
function familleDeScope(scope) {
  const s = String(scope);
  const i = s.indexOf(':');
  return i < 0 ? 'beacon' : s.slice(0, i);
}

/** Un scope est-il légitime pour ce signal ? (banc + garde-fou d'écriture) */
function scopeValide(signal, scope) {
  const d = SIGNAUX[signal];
  return !!d && d.scopes.includes(familleDeScope(scope));
}

/** Le registre tel qu'il est SERVI au client : sans les fonctions. */
function catalogue() {
  const out = {};
  for (const [nom, d] of Object.entries(SIGNAUX)) {
    out[nom] = {
      slug: d.slug, famille: d.famille, niveau: d.niveau, rappelMs: d.rappelMs,
      ackable: d.ackable, voix: d.voix, kind: d.kind, pref: d.pref,
      interrupteur: d.interrupteur, scopes: d.scopes,
    };
  }
  return out;
}

module.exports = { SIGNAUX, COLONNES_PREFS, familleDeScope, scopeValide, catalogue };
