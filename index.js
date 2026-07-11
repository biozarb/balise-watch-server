const express  = require('express');
const webpush  = require('web-push');
const fetch    = require('node-fetch');
const rateLimit = require('express-rate-limit');
const WebSocket = require('ws'); // Étape 10 Lot 5 : flux foudre Blitzortung (WebSocket temps réel)

const PORT         = process.env.PORT || 3000;
const VAPID_PUB    = process.env.VAPID_PUBLIC_KEY;
const VAPID_PRIV   = process.env.VAPID_PRIVATE_KEY;
const VAPID_EMAIL  = process.env.VAPID_EMAIL || 'mailto:admin@balise-watch.fr';
const SB_URL       = process.env.SUPABASE_URL;
const SB_KEY       = process.env.SUPABASE_SERVICE_KEY;
// Traduction : Azure Translator, palier gratuit F0 — préféré à DeepL
// (revu le 08/07 : le plan "API Free" DeepL n'existe plus pour les
// nouveaux comptes, remplacé par "Developer" = 1M caractères UNIQUES,
// pas renouvelés, puis payant. Azure F0 = 2M caractères/mois,
// renouvelé indéfiniment, gratuit à vie — seul choix compatible avec
// la contrainte "jamais de facture possible, zéro budget").
const AZURE_TRANSLATOR_KEY    = process.env.AZURE_TRANSLATOR_KEY;
const AZURE_TRANSLATOR_REGION = process.env.AZURE_TRANSLATOR_REGION; // ex. 'westeurope'
const AZURE_TRANSLATOR_URL    = 'https://api.cognitive.microsofttranslator.com';
// Palier F0, cf. learn.microsoft.com/azure/ai-services/translator/service-limits
// (vérifié 08/07/2026). Pas d'endpoint "usage restant" côté Azure
// (contrairement à DeepL /v2/usage) — on compte nous-mêmes les
// caractères envoyés, par mois, dans translation_usage_monthly.
const AZURE_MONTHLY_CHAR_LIMIT = 2_000_000;
const POLL_MS      = 5 * 60 * 1000;
const API_ALL      = 'https://api.pioupiou.fr/v1/live-with-meta/all';
// Étape 10 (flightwatch), Lot 2 : Open-Meteo, gratuit non-commercial —
// clause revérifiée le 11/07/2026 (open-meteo.com/en/terms) : palier
// libre = usages sans abonnement ni pub, ce qui correspond à Balise
// Watch ("No ads, no tracking", cf. CLAUDE.md). Limites 600/min,
// 5000/h, 10000/j — très largement suffisant vu le nombre de balises
// surveillées par l'app. `models=meteofrance_seamless` : AROME MF
// 1,5 km HD, même modèle que les prévisions client existantes
// (cohérence de source), avec repli automatique modèle global hors
// couverture France (comportement "_seamless" documenté Open-Meteo).
const OPEN_METEO_URL = 'https://api.open-meteo.com/v1/forecast';

// ── Étape 10 (flightwatch), Lot 4 : Vigilance Météo-France ─────────
// Source OFFICIELLE (contrairement à Open-Meteo, gratuite mais PAS sans
// compte) : portail-api.meteofrance.fr, produit « Bulletin Vigilance ».
// Vérifié le 11/07/2026 (confluence-meteofrance.atlassian.net, guide de
// démarrage rapide) : compte requis + abonnement gratuit à l'API +
// génération d'un « Application ID » (valeur Basic prête à l'emploi,
// PAS à ré-encoder). Flux OAuth2 client_credentials :
//   1) POST METEOFRANCE_TOKEN_URL, Authorization: Basic <APP_ID>,
//      body grant_type=client_credentials -> access_token (~1h, mis en
//      cache ci-dessous, jamais persisté en base).
//   2) GET METEOFRANCE_VIGILANCE_URL, Authorization: Bearer <token>.
// Quota 60 req/min (documenté) — un seul appel vigilance PAR POLL (carte
// nationale en un coup, pas par département) + un renouvellement de
// token toutes les ~heure : très loin du quota.
// ⚠️ Si METEOFRANCE_APP_ID n'est pas configuré (Yann n'a pas encore créé
// de compte/abonnement), toute la chaîne se dégrade en douceur : aucun
// token -> aucune donnée -> signal vigilance simplement pas évalué,
// jamais de crash (même politique que AZURE_TRANSLATOR_KEY absent).
// ⚠️ Forme JSON de la réponse `cartevigilance/encours` reconstituée à
// partir de la documentation et d'intégrations tierces publiées
// (meteofrance-api, jeedom, Home Assistant) — PAS vérifiée en direct
// dans cette session (nécessite un compte que je n'ai pas). À
// reconfirmer par Yann avec un vrai token avant mise en prod (cf. le
// point signalé en fin de Lot 4 dans ROADMAP.md).
const METEOFRANCE_APP_ID       = process.env.METEOFRANCE_APP_ID;
const METEOFRANCE_TOKEN_URL    = 'https://portail-api.meteofrance.fr/token';
const METEOFRANCE_VIGILANCE_URL = 'https://public-api.meteofrance.fr/public/DPVigilance/v1/cartevigilance/encours';

// ── Étape 11 : Données d'observation Météo-France (stations réelles) ───
// Abonnement séparé de Vigilance (produits "Données d'observation"
// v1/v2 + "Package Observations" v2, sur portail-api.meteofrance.fr),
// vérifié en direct le 11/07/2026. Auth par **clé API statique** (type
// "API Key" du portail, PAS OAuth2) : un JWT généré une fois avec une
// durée choisie (plafonnée à 3 ans par le portail), envoyé tel quel en
// header `apikey` sur CHAQUE requête — aucun échange de token, aucun
// cache/renouvellement nécessaire (contraste avec Vigilance ci-dessus).
// Couvre les 3 produits abonnés au moment de sa génération.
const METEOFRANCE_API_KEY = process.env.METEOFRANCE_API_KEY;
const MF_PAQUET_URL = 'https://public-api.meteofrance.fr/public/DPPaquetObs/v2/paquet/stations/infrahoraire-6m';
const MF_LISTE_STATIONS_URL = 'https://public-api.meteofrance.fr/public/DPPaquetObs/v2/liste-stations';
// Cadence native des données (6 min) — inutile de poller plus vite,
// la source ne se met à jour qu'à ce rythme.
const MF_OBS_POLL_MS = 6 * 60 * 1000;
// La liste des stations (id/nom/coordonnées) change rarement — un
// rafraîchissement quotidien suffit largement (contraste avec le
// paquet d'observations, qui lui doit suivre la cadence 6 min).
const MF_STATIONS_LIST_REFRESH_MS = 24 * 60 * 60 * 1000;
// Vigilance MF RETIRÉE des alertes (demande de Yann, 11/07/2026) : les pilotes
// connaissent déjà la vigilance orange/rouge officielle. On CONSERVE tout le
// code Lot 4 (token, fetch, mapping département) mais on ne l'ÉVALUE plus dans
// le poll — repasser ce flag à true pour réactiver le signal vigilance.
const FW_VIGILANCE_ENABLED = false;

// Mapping balise -> département (Lot 4) : API Découpage administratif
// (geo.api.gouv.fr, Etalab/IGN), officielle, gratuite, SANS clé — aucune
// contrainte d'usage commerciale contrairement à Open-Meteo. Un beacon a
// des coordonnées FIXES (station météo immobile) : le département ne
// change jamais -> résolu UNE SEULE FOIS par balise puis mis en cache en
// RAM pour le reste de la vie du process (pas un cache par poll comme
// beaconHistory/weatherByBeacon), cf. getBeaconDepartment plus bas.
const GEO_COMMUNES_URL = 'https://geo.api.gouv.fr/communes';

// ── Étape 8 (i18n), Lot 3 : dictionnaire de push traduits ──────────
// Seuls fr (référence) et en (fallback) sont remplis pour l'instant —
// même état que les fichiers src/locales/ côté client : les 6 autres
// langues sont préparées (Lot 3, mécanique) mais pas encore traduites
// (Lot 4, relecture native requise avant d'y mettre du texte de
// sécurité). PUSH_LABELS[lang] absent → repli sur 'en', jamais de
// texte manquant ni de crash. « km/h » n'est pas dans ce dictionnaire :
// symbole d'unité international, identique dans toutes les langues
// (même convention que nativeName côté client, cf. i18n.ts).
// Lot 1 flightwatch (10/07) : sous-objet `flightwatch` par langue, même
// convention (fr rempli en référence + en de secours, cf. §4
// FLIGHTWATCH_LOT0.md — on ne sème pas les 6 autres langues tant qu'elles
// n'ont pas de relecture native, texte de sécurité oblige).
const PUSH_LABELS = {
  fr: {
    avg: 'Moy.', gust: 'Rafale',
    flightwatch: {
      windSurge: {
        body: (nowKmh, baseKmh, windowMin) =>
          `Vent en forte hausse : ${nowKmh} km/h (${baseKmh} km/h il y a ${windowMin} min)`,
      },
      breezeReversal: {
        title: '🔄 Bascule de brise',
        body: names => `Changement de direction du vent détecté sur plusieurs balises voisines : ${names}`,
      },
      pressureDrop: {
        body: (rateAbs, windowH) => `Chute de pression : ${rateAbs} hPa/h (tendance sur ${windowH}h)`,
      },
      convection: {
        body: (capeNow, cloudPct, freezingM) =>
          `Risque de développement convectif : CAPE ${capeNow} J/kg en hausse, nébulosité basse/moyenne ${cloudPct}%` +
          (freezingM != null ? `, iso 0°C ${freezingM} m` : ''),
      },
      vigilance: {
        title: (level, dept) => `${level === 3 ? '🔴 Vigilance rouge' : '🟠 Vigilance orange'} — département ${dept}`,
        body: names => `Vigilance météo officielle en cours sur : ${names}. Recroise ta propre météo avant de voler.`,
      },
      lightning: {
        body: (count, radiusKm, windowMin) =>
          `${count} impact${count > 1 ? 's' : ''} de foudre détecté${count > 1 ? 's' : ''} à moins de ${radiusKm} km (${windowMin} dernières min) — donnée indicative Blitzortung, non officielle`,
      },
    },
  },
  en: {
    avg: 'Avg.', gust: 'Gust',
    flightwatch: {
      windSurge: {
        body: (nowKmh, baseKmh, windowMin) =>
          `Wind rising sharply: ${nowKmh} km/h (${baseKmh} km/h ${windowMin} min ago)`,
      },
      breezeReversal: {
        title: '🔄 Wind shift',
        body: names => `Wind direction shift detected across nearby beacons: ${names}`,
      },
      pressureDrop: {
        body: (rateAbs, windowH) => `Pressure falling: ${rateAbs} hPa/h (${windowH}h trend)`,
      },
      convection: {
        body: (capeNow, cloudPct, freezingM) =>
          `Convective development risk: CAPE ${capeNow} J/kg rising, low/mid cloud cover ${cloudPct}%` +
          (freezingM != null ? `, freezing level ${freezingM} m` : ''),
      },
      vigilance: {
        title: (level, dept) => `${level === 3 ? '🔴 Red weather warning' : '🟠 Orange weather warning'} — department ${dept}`,
        body: names => `Official weather warning in effect for: ${names}. Double-check your own forecast before flying.`,
      },
      lightning: {
        body: (count, radiusKm, windowMin) =>
          `${count} lightning strike${count > 1 ? 's' : ''} detected within ${radiusKm} km (last ${windowMin} min) — indicative Blitzortung data, unofficial`,
      },
    },
  },
};
function pushLabels(lang) { return PUSH_LABELS[lang] || PUSH_LABELS.en; }

// ── Étape 10 (flightwatch), Lot 1 : préférences de veille météo ────
// user_surveillance porte désormais, en plus du flag `active`, les
// colonnes de préférences ajoutées par supabase_flightwatch.sql (Lot 0) :
// interrupteurs par signal (sig_*), seuils, voix. Défauts SAINS répliqués
// ici : si une valeur manque (ligne pré-existante, ou colonne pas encore
// vue par sbGet pour une raison quelconque), on retombe dessus — jamais
// de crash, même politique défensive que le reste de pollAndNotify.
const FW_DEFAULTS = {
  sig_wind_surge:        true,
  sig_breeze_reversal:   true,
  sig_pressure_drop:     true,
  sig_convection:        true,
  sig_vigilance:         true,
  sig_lightning:         true,
  sig_freezing_level:    false, // info pure, off par défaut (cf. schéma Lot 0)
  lightning_radius_km:   50,
  wind_surge_factor:     1.8,
  wind_surge_window_min: 15,
  pressure_drop_hpa_h:   2.0,
  voice_enabled:         true,
};
function fwPrefs(row) {
  const p = {};
  for (const k of Object.keys(FW_DEFAULTS)) {
    const v = row?.[k];
    p[k] = (v === undefined || v === null) ? FW_DEFAULTS[k] : v;
  }
  return p;
}

// ── Étape 10 (flightwatch), Lot 1 : signaux "gratuits" (vent/brise) ─
// Aucune nouvelle source : on dérive tout de `releves` (déjà pollé).
// Historique en RAM du process (par balise, pas par compte — plusieurs
// comptes peuvent surveiller la même balise, la dérive physique est
// unique). Volontairement PAS persisté en base : c'est du signal brut
// dérivé, pas un état d'alerte (celui-là vit dans user_flightwatch_alerts,
// cf. plus bas) — un redémarrage Render (free tier, veille) vide juste le
// buffer, qui se reremplit poll après poll ; conséquence assumée : pas de
// détection de montée de vent tant que `wind_surge_window_min` minutes de
// buffer n'ont pas été accumulées après un redémarrage, jamais de fausse
// alerte par contre (cf. §8 garde-fou "informer, pas juger" — on préfère
// rater une détection à en inventer une).
const FW_TREND_WINDOW_H = 3; // "tendance barométrique 3h", convention aviation standard (cf. §4 FLIGHTWATCH_LOT0.md) — pas de colonne dédiée au schéma Lot 0, fenêtre fixée ici, partagée pression ET CAPE (Lot 3) pour rester cohérent. Depuis le Lot 2b : sert aussi de fenêtre à la pression RÉELLE mesurée par la balise (beaconHistory), pas seulement au modèle Open-Meteo.
const FW_HISTORY_MAX_AGE_MS = (FW_TREND_WINDOW_H * 60 + 30) * 60 * 1000; // 3h30 (Lot 2b) : couvre la fenêtre de tendance pression réelle avec marge — large au-dessus des autres fenêtres réglées (vent/brise, défaut 15 min)
const MF_HISTORY_RETENTION_H = 48; // Lot 8 (12/07) : rétention de la table persistante mf_station_history — INDÉPENDANTE de FW_HISTORY_MAX_AGE_MS/beaconHistory ci-dessus, qui reste à 3h30 pour la veille météo (flightwatch) uniquement
const FW_PRESSURE_MIN_SAMPLES_SPAN_MIN = 150; // Lot 2b : n'évalue la pression RÉELLE (beaconHistory) qu'avec au moins 2h30 de recul (proche de la fenêtre 3h visée) — sinon repli Open-Meteo, jamais un taux calculé sur un intervalle trop court ou juste après un redémarrage
const FW_WIND_MIN_BASELINE_KMH = 3; // évite un facteur "x1.8" absurde quand le vent de référence est quasi nul
const FW_WIND_SURGE_ABS_MIN_KMH = 15; // FIA-1 : plancher absolu sur wind_surge — pas d'alerte niveau 3 si le vent courant reste sous ce seuil (évite les faux positifs "danger imminent" à ~6 km/h les matins calmes thermiques)
const MF_OBS_MAX_AGE_MS = 30 * 60 * 1000; // DATA-1 : garde-fraîcheur MF — une observation dont validityTime dépasse ce seuil est ignorée dans la fusion (évite d'alerter sur des données figées si l'API MF tombe plusieurs heures)
const FW_BREEZE_REVERSAL_MIN_DEG = 100; // retournement net de direction, pas une dérive — pas de colonne dédiée au schéma Lot 0, constante serveur documentée ici
const FW_BREEZE_NEIGHBOR_RADIUS_KM = 20; // "balises voisines" — rayon raisonnable pour la maille de balises Alpes/Maurienne, ajustable à l'usage
const FW_BREEZE_REVERSAL_MIN_WIND_KMH = 5; // FIA-2 : plancher de vitesse sur la bascule de brise — par vent quasi nul la direction d'une girouette est aléatoire, ce qui suffirait à déclencher un retournement fictif de 100°+ entre deux balises calmes au lever/coucher
const FW_ALERT_REPEAT_MS = 15 * 60 * 1000; // anti-répétition flightwatch : pas de colonne repeat_interval dédiée (contrairement à user_watched), intervalle fixe raisonnable niveau 2/3
const FW_OM_MAX_BEACONS_PER_POLL = 200; // garde-fou quota Open-Meteo : coupe court si un jour énormément de balises distinctes étaient surveillées d'un coup (très loin de l'usage actuel), plutôt que de risquer les paliers 600/min ou 5000/h

// ── Étape 10 (flightwatch), Lot 3 : risque de développement convectif ──
// Combine CAPE (niveau + hausse sur FW_TREND_WINDOW_H) comme déclencheur
// PRINCIPAL — pas de colonne dédiée au schéma Lot 0 (seul l'interrupteur
// sig_convection existe), constantes serveur documentées ici, ajustables
// à l'usage. Choix délibéré (§7.5 cadrage note "pas cracher de faux
// positifs") : on exige un PLANCHER (de l'instabilité déjà là, valeurs
// alpines — souvent plus modestes qu'en plaine mais suffisantes pour un
// orage de relief) ET une HAUSSE sur la fenêtre (déstabilisation ACTIVE,
// pas un CAPE ambiant stable qui ne raconte rien de neuf) — même logique
// "dérivée, pas juste un seuil absolu" que wind_surge/pressure_drop. La
// nébulosité basse/moyenne et l'iso 0°C ne GATENT PAS le déclenchement
// (deux signaux bruités combinés en ET auraient multiplié les ratés) :
// elles sont ajoutées en CONTEXTE informatif dans le corps du push,
// cohérent avec le double rôle de l'iso 0°C au cadrage (§2 point 7 :
// "exposé comme info ET comme composante du signal convectif").
const FW_CONVECTION_CAPE_MIN_JKG = 400; // plancher d'instabilité significative (valeurs alpines — un seuil plaine type 1000+ raterait les orages de montagne)
const FW_CONVECTION_CAPE_RISE_MIN_JKG = 150; // hausse minimale sur la fenêtre (J/kg), signe de déstabilisation en cours
// sig_freezing_level (interrupteur séparé, défaut OFF, "info pure" au
// schéma Lot 0) reste HORS scope ici : c'est un signal d'AFFICHAGE passif
// (§7.5 niveau 1, "passif, consultable"), pas un déclencheur de push —
// il trouvera sa place naturelle au Lot 6 (UI, affichage épuré) quand il
// y aura un endroit pour le montrer sans spammer une notification dessus.
// En attendant, l'iso 0°C n'apparaît qu'en info dans le corps du push
// convection ci-dessous (cf. commentaire ci-dessus), jamais en push seul.

// ── Étape 10 (flightwatch), Lot 5 : foudre temps réel (Blitzortung) ──
// Source COMMUNAUTAIRE (réseau bénévole de capteurs), à distinguer nettement
// des sources officielles Open-Meteo/Météo-France des lots précédents.
// ⚠️ Conditions d'usage Blitzortung (revérifiées le 11/07/2026,
// blitzortung.org) : données fournies « à des fins privées et de
// divertissement », le projet « n'est pas une autorité officielle », et les
// apps tierces doivent servir les données via LEUR PROPRE serveur (jamais en
// direct depuis chaque client). D'où l'ingestion ci-dessous CÔTÉ SERVEUR
// (balise-watch-server), la PWA ne parle jamais à Blitzortung. Décision
// produit (avec Yann) : on présente ces impacts comme une INFO INDICATIVE et
// NON OFFICIELLE — cohérent avec le garde-fou n°1 du cadrage (« aide à la
// décision, jamais garantie ») et avec le disclaimer d'inscription à ajouter
// côté client. Le corps du push le dit explicitement (cf. PUSH_LABELS).
// Architecture (passe Opus 11/07) : connexion WebSocket persistante,
// ACTIVÉE À LA DEMANDE (ouverte tant qu'au moins un compte actif a
// sig_lightning, fermée après un délai de grâce sinon → pas de firehose
// mondial inutile), payload obfusqué décodé (variante LZW, cf.
// www.gkbrk.com/blitzortung), filtré à la bbox France À LA RÉCEPTION (le
// reste du monde est jeté avant tout stockage), buffer RAM glissant (même
// philosophie que beaconHistory : JAMAIS persisté, un redémarrage le vide →
// re-remplissage progressif, jamais de fausse alerte). Détection au poll
// 5 min (réutilise evaluateFwSignal comme tous les autres signaux). Tout
// défensif : WS coupé / kill switch / ws absent → buffer vide → signal
// simplement non évalué, jamais de crash (même politique que
// METEOFRANCE_APP_ID absent au Lot 4).
const FW_LIGHTNING_ENABLED = process.env.FW_LIGHTNING_ENABLED === '1'; // OPT-IN : OFF par défaut. La chaîne foudre reste DORMANTE en prod (aucune connexion WS, aucun push) tant que FW_LIGHTNING_ENABLED=1 n'est pas mis sur Render — à n'activer qu'une fois le décodage validé sur le vrai flux ET l'accès Blitzortung régularisé (ToU, cf. ROADMAP Lot 5). En local : `export FW_LIGHTNING_ENABLED=1` pour tester.
const FW_LIGHTNING_WS_SERVERS = ['wss://ws1.blitzortung.org', 'wss://ws7.blitzortung.org', 'wss://ws8.blitzortung.org']; // rotation en cas d'échec/silence
const FW_LIGHTNING_BBOX = { latMin: 41.0, latMax: 51.6, lonMin: -5.5, lonMax: 10.0 }; // France métropolitaine + marge (Alpes/Corse) — filtre à la réception
const FW_LIGHTNING_BUFFER_MAX_AGE_MS = 60 * 60 * 1000; // fenêtre glissante du buffer (60 min), large marge sur la fenêtre de comptage
const FW_LIGHTNING_WINDOW_MIN = 15; // fenêtre de comptage des impacts autour d'une balise (min)
const FW_LIGHTNING_REPEAT_MS = 10 * 60 * 1000; // anti-répétition DÉDIÉE, plus courte que FW_ALERT_REPEAT_MS (15 min) vu la criticité niveau 3 — un orage = un push par épisode puis rappel toutes les ~10 min tant que des impacts tombent dans la zone, JAMAIS un push par impact
const FW_LIGHTNING_BUFFER_HARD_MAX = 20000; // garde-fou mémoire dur (borne le buffer même en cas d'orage massif sur la France)

// Buffer RAM des impacts récents, filtrés France. [{t: ms (heure d'arrivée),
// lat, lon}], ordre d'arrivée ~ chronologique. Jamais persisté (cf. ci-dessus).
const lightningStrikes = [];

function fwLightningPrune() {
  const cutoff = Date.now() - FW_LIGHTNING_BUFFER_MAX_AGE_MS;
  while (lightningStrikes.length && lightningStrikes[0].t < cutoff) lightningStrikes.shift();
}

// Décodage du flux Blitzortung (obfusqué, variante LZW) — portage JS fidèle
// de la fonction Python de référence (www.gkbrk.com/blitzortung). Renvoie la
// chaîne JSON décodée (l'appelant fait le JSON.parse dans un try).
function fwLightningDecode(b) {
  const e = {};
  const d = String(b).split('');
  let c = d[0];
  let f = c;
  const g = [c];
  const h = 256;
  let o = h;
  for (let i = 1; i < d.length; i++) {
    const code = d[i].charCodeAt(0);
    let a;
    if (h > code) a = d[i];
    else if (e[code]) a = e[code];
    else a = f + c;
    g.push(a);
    c = a.charAt(0);
    e[o] = f + c;
    o++;
    f = a;
  }
  return g.join('');
}

// Décode + filtre bbox France + bufferise un message brut du WS. Toute
// anomalie (message non décodable, non-JSON, sans lat/lon, message de
// contrôle) est silencieusement ignorée — jamais de crash de l'ingestion.
function fwLightningIngest(raw) {
  try {
    const json = JSON.parse(fwLightningDecode(raw));
    const lat = json?.lat, lon = json?.lon;
    if (typeof lat !== 'number' || typeof lon !== 'number') return;
    const bb = FW_LIGHTNING_BBOX;
    if (lat < bb.latMin || lat > bb.latMax || lon < bb.lonMin || lon > bb.lonMax) return; // hors France → jeté avant stockage
    lightningStrikes.push({ t: Date.now(), lat, lon }); // heure d'arrivée : suffisant pour une fenêtre de minutes, évite le parsing ns / la dérive d'horloge
    if (lightningStrikes.length > FW_LIGHTNING_BUFFER_HARD_MAX) lightningStrikes.splice(0, lightningStrikes.length - FW_LIGHTNING_BUFFER_HARD_MAX);
  } catch { /* message non décodable/non-strike → ignoré */ }
}

// Compte les impacts à <= radiusKm d'un point sur les `windowMin` dernières
// minutes (parcours de la fin du buffer, coupé dès qu'on sort de la fenêtre).
function fwLightningCountNear(lat, lon, radiusKm, windowMin) {
  if (lat == null || lon == null) return 0;
  const since = Date.now() - windowMin * 60 * 1000;
  let n = 0;
  for (let i = lightningStrikes.length - 1; i >= 0; i--) {
    const s = lightningStrikes[i];
    if (s.t < since) break; // buffer trié chronologiquement → on peut s'arrêter
    if (fwHaversineKm(lat, lon, s.lat, s.lon) <= radiusKm) n++;
  }
  return n;
}

// ── Gestion de la connexion WebSocket (activée à la demande, robuste) ──
let fwLightningWs = null;
let fwLightningWantConnected = false;
let fwLightningServerIdx = 0;
let fwLightningBackoffMs = 1000;
let fwLightningReconnectTimer = null;
let fwLightningIdleTimer = null;      // watchdog de silence (reconnecte si le flux se tait)
let fwLightningStopGraceTimer = null; // délai de grâce avant fermeture quand plus personne n'a besoin

function fwLightningResetIdleWatchdog() {
  if (fwLightningIdleTimer) clearTimeout(fwLightningIdleTimer);
  fwLightningIdleTimer = setTimeout(() => {
    console.warn('⚡ Blitzortung : silence prolongé, reconnexion');
    try { fwLightningWs?.terminate(); } catch {}
  }, 60 * 1000);
}

function fwLightningConnect() {
  if (!FW_LIGHTNING_ENABLED || !fwLightningWantConnected || fwLightningWs) return;
  const url = FW_LIGHTNING_WS_SERVERS[fwLightningServerIdx % FW_LIGHTNING_WS_SERVERS.length];
  let ws;
  try { ws = new WebSocket(url); } catch { fwLightningScheduleReconnect(); return; }
  fwLightningWs = ws;
  ws.on('open', () => {
    fwLightningBackoffMs = 1000; // reset backoff sur connexion réussie
    try { ws.send(JSON.stringify({ a: 111 })); } catch {} // handshake d'abonnement au flux
    fwLightningResetIdleWatchdog();
    console.log(`⚡ Blitzortung connecté (${url})`);
  });
  ws.on('message', (data) => { fwLightningResetIdleWatchdog(); fwLightningIngest(data.toString()); });
  ws.on('close', () => { fwLightningWs = null; fwLightningScheduleReconnect(); });
  ws.on('error', (err) => { console.warn(`⚡ Blitzortung erreur WS: ${err?.message || err}`); try { ws.terminate(); } catch {} });
}

function fwLightningScheduleReconnect() {
  if (fwLightningIdleTimer) { clearTimeout(fwLightningIdleTimer); fwLightningIdleTimer = null; }
  if (!FW_LIGHTNING_ENABLED || !fwLightningWantConnected || fwLightningReconnectTimer) return;
  fwLightningServerIdx++; // rotation serveur au prochain essai
  const delay = fwLightningBackoffMs;
  fwLightningBackoffMs = Math.min(fwLightningBackoffMs * 2, 30000); // backoff exponentiel plafonné à 30 s
  fwLightningReconnectTimer = setTimeout(() => { fwLightningReconnectTimer = null; fwLightningConnect(); }, delay);
}

// Appelé à CHAQUE poll : ouvre/maintient la connexion si au moins un compte
// actif a besoin de la foudre, sinon programme sa fermeture (avec un délai de
// grâce de 2 polls pour éviter un cycle open/close si l'activité oscille).
function fwLightningSetNeeded(needed) {
  if (!FW_LIGHTNING_ENABLED) return;
  if (needed) {
    if (fwLightningStopGraceTimer) { clearTimeout(fwLightningStopGraceTimer); fwLightningStopGraceTimer = null; }
    if (!fwLightningWantConnected) { fwLightningWantConnected = true; fwLightningConnect(); }
  } else if (fwLightningWantConnected && !fwLightningStopGraceTimer) {
    fwLightningStopGraceTimer = setTimeout(() => {
      fwLightningStopGraceTimer = null;
      fwLightningWantConnected = false;
      if (fwLightningReconnectTimer) { clearTimeout(fwLightningReconnectTimer); fwLightningReconnectTimer = null; }
      if (fwLightningIdleTimer) { clearTimeout(fwLightningIdleTimer); fwLightningIdleTimer = null; }
      try { fwLightningWs?.close(); } catch {}
      fwLightningWs = null;
      console.log('⚡ Blitzortung : plus de besoin, déconnexion');
    }, 2 * POLL_MS);
  }
}

const beaconHistory = new Map(); // beacon_id (string) -> [{t, moy, dir, pressure}] trié par t croissant

// Débogage 12/07/2026 — cache de la source de pression réellement utilisée
// pour CHAQUE balise évaluée (capteur embarqué OU modèle AROME de repli),
// alimenté à chaque poll (cf. pollAndNotify, bloc "chute de pression
// rapide") et servi tel quel par GET /pressure-signal. Objectif : le
// client (WatchCard) affiche la MÊME valeur/source que celle utilisée
// pour décider les alertes, plutôt que de recalculer un repli séparé
// (et potentiellement divergent) de son côté. beacon_id (string) ->
// { source: 'sensor'|'model'|null, value: number|null, rate: number|null,
//   updatedAt: number }.
const pressureSignalCache = new Map();

function fwRecordHistory(beaconId, sample) {
  const arr = beaconHistory.get(beaconId) || [];
  arr.push(sample);
  const cutoff = Date.now() - FW_HISTORY_MAX_AGE_MS;
  while (arr.length && arr[0].t < cutoff) arr.shift();
  beaconHistory.set(beaconId, arr);
}

// Lot 8 (12/07) — persistance 48h de l'historique des stations MF, en
// complément du buffer RAM ci-dessus (qui reste inchangé, 3h30, pour la
// veille météo). Table : mf_station_history (cf.
// supabase_step13_mf_station_history.sql). Volontairement
// fire-and-forget (pas de await côté appelant, erreurs avalées ici) :
// une panne/lenteur Supabase sur CETTE écriture ne doit jamais retarder
// ni casser l'évaluation des alertes flightwatch qui suit dans
// pollAndNotify — même philosophie défensive que le reste du fichier
// (§8 cadrage "informer, pas juger" : mieux vaut perdre quelques points
// d'historique qu'un poll d'alertes entier). Purge (>48h) regroupée ici
// plutôt que dans un cron séparé : un DELETE indexé sur `t` à chaque
// poll est trivial pour Postgres, pas besoin de pg_cron.
function mfPersistHistory(rows) {
  if (!rows.length) return;
  sbUpsert('mf_station_history', rows, 'station_id,t')
    .catch(e => console.error('mfPersistHistory upsert error:', e.message));
  const cutoff = Date.now() - MF_HISTORY_RETENTION_H * 3600 * 1000;
  sbDelete('mf_station_history', `t=lt.${cutoff}`)
    .catch(e => console.error('mfPersistHistory purge error:', e.message));
}
// Renvoie l'échantillon le plus RÉCENT qui a au moins `windowMin` minutes
// (le plus proche possible de cette borne vu la cadence de poll 5 min).
// null si l'historique n'a pas encore assez de recul (pas de faux positif
// au démarrage du process).
function fwBaselineAt(beaconId, windowMin) {
  const arr = beaconHistory.get(beaconId);
  if (!arr || !arr.length) return null;
  const targetT = Date.now() - windowMin * 60 * 1000;
  let candidate = null;
  for (const s of arr) {
    if (s.t <= targetT) candidate = s; else break;
  }
  return candidate;
}
// Étape 10 (flightwatch), Lot 2b : tendance de pression RÉELLE, mesurée par
// le baromètre embarqué de la balise elle-même (`measurements.pressure` de
// l'API Pioupiou live, déjà présent dans le poll existant — ZÉRO appel
// réseau supplémentaire), à la place de la pression MODÈLE Open-Meteo
// utilisée jusqu'ici seule. Avantage double : mesure au point exact du site
// de vol (jamais le cas d'une station SYNOP/METAR, presque toujours en
// fond de vallée ou sur un aérodrome) ; un biais de calibration du capteur
// s'annule dans le calcul puisque c'est une dérivée avant/après sur LE
// MÊME capteur. Limite : toutes les balises n'ont pas de baromètre
// (`pressure` peut être `null`) → repli Open-Meteo dans ce cas (cf.
// pollAndNotify, section "chute de pression rapide"). Renvoie `null` sans
// calcul si l'historique n'a pas encore FW_PRESSURE_MIN_SAMPLES_SPAN_MIN
// minutes de recul réel (pas juste un vieil échantillon isolé) — même
// politique défensive que fwBaselineAt, jamais de taux calculé sur un
// intervalle trop court ou juste après un redémarrage serveur.
function fwRealPressureTrend(beaconId, nowPressure) {
  if (nowPressure == null) return null;
  const past = fwBaselineAt(beaconId, FW_TREND_WINDOW_H * 60);
  if (!past || past.pressure == null) return null;
  const spanMin = (Date.now() - past.t) / 60000;
  if (spanMin < FW_PRESSURE_MIN_SAMPLES_SPAN_MIN) return null;
  return { now: nowPressure, past: past.pressure, rate: (nowPressure - past.pressure) / (spanMin / 60) };
}
// Différence angulaire absolue (0-180°), gère le passage 359°→0°.
function fwAngularDiff(a, b) {
  if (a == null || b == null) return null;
  let d = Math.abs(a - b) % 360;
  if (d > 180) d = 360 - d;
  return d;
}
// Distance à vol d'oiseau (km) — formule haversine, précision suffisante
// pour juger "balises voisines" (pas de calcul géodésique de précision).
function fwHaversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const toRad = deg => deg * Math.PI / 180;
  const dLat = toRad(lat2 - lat1), dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}
// Regroupe une liste de {beaconId, rel:{lat,lon,...}} en composantes
// connexes par proximité (BFS, chaînage transitif — deux balises à la
// limite du rayon l'une de l'autre suffisent à relier deux clusters).
function fwClusterByProximity(items, radiusKm) {
  const n = items.length;
  const visited = new Array(n).fill(false);
  const clusters = [];
  for (let i = 0; i < n; i++) {
    if (visited[i]) continue;
    const stack = [i]; visited[i] = true;
    const cluster = [items[i]];
    while (stack.length) {
      const cur = stack.pop();
      for (let j = 0; j < n; j++) {
        if (visited[j]) continue;
        const dKm = fwHaversineKm(items[cur].rel.lat, items[cur].rel.lon, items[j].rel.lat, items[j].rel.lon);
        if (dKm <= radiusKm) { visited[j] = true; cluster.push(items[j]); stack.push(j); }
      }
    }
    clusters.push(cluster);
  }
  return clusters;
}

// Signaux Open-Meteo (Lot 2 pression, généralisé Lot 3 convection) : UNE
// requête par balise distincte (mutualisée entre tous les comptes qui la
// surveillent — cf. cadrage §5 "une requête par zone/balise, mutualisée"),
// jamais par compte. `past_days=1` donne l'historique horaire nécessaire
// aux dérivées SANS buffer RAM à reconstituer après un redémarrage
// (contraste avec l'approche vent/brise ci-dessus : Open-Meteo porte déjà
// l'historique). Lot 3 réutilise EXACTEMENT cette requête (mêmes
// latitude/longitude/past_days/modèle) en ajoutant des variables
// `hourly=` supplémentaires — aucun appel réseau de plus par balise (cf.
// cadrage : "Réutilise l'appel Open-Meteo du Lot 2, pas de coût réseau
// supplémentaire"). Défensif : toute erreur (réseau, hors couverture,
// réponse inattendue) renvoie null — l'appelant doit alors s'abstenir
// d'évaluer TOUS les signaux dérivés de cet appel ce poll-ci plutôt que
// de risquer un faux reset (cf. §8 garde-fou "informer, pas juger").
function fwPick(arr, idx) {
  return (Array.isArray(arr) && idx != null && idx >= 0 && arr[idx] != null) ? arr[idx] : null;
}
async function fetchOpenMeteoSignals(lat, lon) {
  try {
    const url = `${OPEN_METEO_URL}?latitude=${lat}&longitude=${lon}` +
      `&hourly=pressure_msl,cape,cloud_cover_low,cloud_cover_mid,cloud_cover_high,freezing_level_height` +
      `&past_days=1&forecast_days=1&models=meteofrance_seamless&timezone=UTC`;
    const r = await fetch(url);
    if (!r.ok) return null;
    const d = await r.json();
    const h = d?.hourly;
    const times = h?.time;
    if (!Array.isArray(times) || !times.length) return null;

    const nowMs = Date.now();
    let idxNow = -1;
    for (let i = 0; i < times.length; i++) {
      if (new Date(`${times[i]}Z`).getTime() <= nowMs) idxNow = i; else break;
    }
    if (idxNow < 0) return null;
    const idxPast = idxNow - FW_TREND_WINDOW_H;

    // Dérivée (now vs il y a FW_TREND_WINDOW_H heures) pour les variables qui
    // en ont besoin (pression, CAPE) ; null si historique insuffisant plutôt
    // qu'une dérivée bancale — même politique que le Lot 1 (fwBaselineAt).
    const trendOf = (arr) => {
      const now = fwPick(arr, idxNow);
      const past = idxPast >= 0 ? fwPick(arr, idxPast) : null;
      const rate = (now != null && past != null) ? (now - past) / FW_TREND_WINDOW_H : null;
      return { now, past, rate };
    };

    return {
      pressure: trendOf(h.pressure_msl),
      cape: trendOf(h.cape),
      // Nuages/iso 0°C : valeur COURANTE seulement (pas de dérivée requise
      // par le cadrage Lot 3, cf. §4 — utilisées comme contexte/info, pas
      // comme déclencheur à elles seules, cf. commentaire d'évaluation
      // plus bas dans pollAndNotify).
      cloudLowNow: fwPick(h.cloud_cover_low, idxNow),
      cloudMidNow: fwPick(h.cloud_cover_mid, idxNow),
      cloudHighNow: fwPick(h.cloud_cover_high, idxNow),
      freezingLevelNow: fwPick(h.freezing_level_height, idxNow),
    };
  } catch { return null; }
}

// ── Vigilance Météo-France (Lot 4) ──────────────────────────────────
// Token en cache module (RAM, jamais persisté — comme beaconHistory) :
// obtenu via OAuth2 client_credentials, marge de sécurité 60 s avant
// expiration pour ne jamais présenter un token tout juste périmé.
let mfTokenCache = { token: null, expiresAt: 0 };
async function getMeteoFranceToken() {
  if (!METEOFRANCE_APP_ID) return null; // fonctionnalité non configurée -> dégradation silencieuse
  const now = Date.now();
  if (mfTokenCache.token && mfTokenCache.expiresAt > now + 60_000) return mfTokenCache.token;
  try {
    const r = await fetch(METEOFRANCE_TOKEN_URL, {
      method: 'POST',
      headers: {
        'Authorization': `Basic ${METEOFRANCE_APP_ID}`,
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: 'grant_type=client_credentials',
    });
    if (!r.ok) return null;
    const d = await r.json();
    if (!d?.access_token) return null;
    const ttlMs = (Number(d.expires_in) || 3600) * 1000;
    mfTokenCache = { token: d.access_token, expiresAt: now + ttlMs };
    return d.access_token;
  } catch { return null; }
}

// Carte de vigilance NATIONALE en un seul appel (pas par département, pas
// par balise) — un poll = au plus un renouvellement de token (~1h de
// validité, donc rarement) + un GET vigilance. Retourne une Map
// codeDépartement (string "01".."2B"..) -> color_id (1 vert, 2 jaune,
// 3 orange, 4 rouge), ou null si indisponible (token/API en échec, ou
// forme de réponse inattendue) — l'appelant doit alors s'abstenir
// d'évaluer le signal ce poll-ci (même politique défensive que le reste).
async function fetchVigilanceColors() {
  const token = await getMeteoFranceToken();
  if (!token) return null;
  try {
    const r = await fetch(METEOFRANCE_VIGILANCE_URL, {
      headers: { 'Authorization': `Bearer ${token}`, 'accept': '*/*' },
    });
    if (!r.ok) return null;
    const d = await r.json();
    const periods = d?.product?.periods;
    if (!Array.isArray(periods) || !periods.length) return null;
    const period = periods.find(p => p?.echeance === 'J') || periods[0];
    const domainIds = period?.timelaps?.domain_ids;
    if (!Array.isArray(domainIds)) return null;

    const colors = new Map();
    for (const entry of domainIds) {
      if (entry?.domain_id != null && entry?.max_color_id != null) {
        colors.set(String(entry.domain_id), Number(entry.max_color_id));
      }
    }
    return colors.size ? colors : null;
  } catch { return null; }
}

// Mapping balise -> département, mis en cache EN PERMANENCE pour la
// durée de vie du process (pas un cache par poll : les coordonnées d'une
// balise ne changent jamais). On ne met en cache QUE les succès — un
// échec réseau ponctuel n'empoisonne pas le cache, on retentera au
// prochain poll (contraste volontaire avec fwRecordHistory/beaconHistory,
// qui eux se rafraîchissent en continu).
const beaconDepartmentCache = new Map(); // beacon_id (string) -> code département (string) — jamais de valeur null stockée
async function getBeaconDepartment(beaconId, lat, lon) {
  if (beaconDepartmentCache.has(beaconId)) return beaconDepartmentCache.get(beaconId);
  try {
    const r = await fetch(`${GEO_COMMUNES_URL}?lat=${lat}&lon=${lon}&fields=departement&format=json`);
    if (!r.ok) return null;
    const d = await r.json();
    const dept = Array.isArray(d) && d[0]?.departement?.code ? String(d[0].departement.code) : null;
    if (dept) beaconDepartmentCache.set(beaconId, dept);
    return dept;
  } catch { return null; }
}

// ── Étape 11 : stations d'observation Météo-France ──────────────────
// Deux caches RAM séparés, jamais persistés (même philosophie que
// beaconHistory/mfTokenCache) :
//  - mfStationsList : métadonnées statiques (id/nom/lat/lon/altitude),
//    ~2150 stations, rafraîchi une fois par jour (MF_STATIONS_LIST_REFRESH_MS)
//  - mfObsCache : dernier paquet d'observations (vent/pression), TOUTES
//    stations en un seul appel national, rafraîchi toutes les 6 min
//    (MF_OBS_POLL_MS) — mutualisé pour tous les comptes, comme Vigilance.
// Si METEOFRANCE_API_KEY n'est pas configurée : les deux caches restent
// vides, /meteofrance-stations renvoie une liste vide, aucun crash
// (même dégradation silencieuse que le reste du module Météo-France).
let mfStationsList = []; // [{id, nom, lat, lon, alt}]
let mfStationsListFetchedAt = 0;
let mfObsCache = new Map(); // id_station -> {dd, ff, ddraf10, raf10, pres, pmer, validityTime}
let mfObsCacheFetchedAt = 0;

// Parse minimal d'un CSV ';' avec en-tête — suffisant pour la forme
// stable de /liste-stations (pas de valeur contenant ';' ou de guillemets
// dans ce jeu de données, vérifié sur un extrait en direct le 11/07).
function parseMfStationsCsv(text) {
  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
  if (lines.length < 2) return [];
  return lines.slice(1).map(line => {
    const [id, , nom, lat, lon, alt] = line.split(';');
    return { id, nom, lat: parseFloat(lat), lon: parseFloat(lon), alt: alt ? parseInt(alt, 10) : null };
  }).filter(s => s.id && Number.isFinite(s.lat) && Number.isFinite(s.lon));
}

async function refreshMfStationsList() {
  if (!METEOFRANCE_API_KEY) return;
  try {
    const r = await fetch(MF_LISTE_STATIONS_URL, { headers: { apikey: METEOFRANCE_API_KEY } });
    if (!r.ok) return; // échec ponctuel : on garde l'ancienne liste plutôt que de la vider
    const text = await r.text();
    const parsed = parseMfStationsCsv(text);
    if (parsed.length) { mfStationsList = parsed; mfStationsListFetchedAt = Date.now(); }
  } catch (e) { console.error('refreshMfStationsList error:', e.message); }
}

// Date alignée sur un multiple de 6 min avec ~12 min de marge (pipeline
// MF pas instantané — vérifié en direct : une marge de 6 min pile peut
// renvoyer un paquet encore incomplet, 12 min est fiable).
function mfPaquetDateParam() {
  const now = new Date(Date.now() - 12 * 60 * 1000);
  const m = Math.floor(now.getUTCMinutes() / 6) * 6;
  now.setUTCMinutes(m, 0, 0);
  return now.toISOString().replace(/\.\d{3}Z$/, 'Z');
}

async function refreshMfObs() {
  if (!METEOFRANCE_API_KEY) return;
  try {
    const url = `${MF_PAQUET_URL}?date=${mfPaquetDateParam()}&format=json`;
    const r = await fetch(url, { headers: { apikey: METEOFRANCE_API_KEY } });
    if (!r.ok) return; // échec ponctuel : on garde l'ancien paquet plutôt que de le vider
    const data = await r.json();
    if (!Array.isArray(data)) return;
    const next = new Map();
    for (const s of data) {
      const id = s?.geo_id_insee;
      if (!id) continue;
      // Conversion en unités natives de l'app (km/h, hPa) dès l'ingestion —
      // le reste du code (comme Pioupiou) travaille déjà dans ces unités.
      next.set(id, {
        dd: s.dd ?? null,
        ff: s.ff != null ? s.ff * 3.6 : null,
        ddraf10: s.ddraf10 ?? null,
        raf10: s.raf10 != null ? s.raf10 * 3.6 : null,
        pres: s.pres != null ? s.pres / 100 : null,
        pmer: s.pmer != null ? s.pmer / 100 : null,
        validityTime: s.validity_time ?? null,
      });
    }
    if (next.size) { mfObsCache = next; mfObsCacheFetchedAt = Date.now(); }
  } catch (e) { console.error('refreshMfObs error:', e.message); }
}

async function refreshMeteoFranceData() {
  if (!METEOFRANCE_API_KEY) return;
  if (!mfStationsList.length || Date.now() - mfStationsListFetchedAt > MF_STATIONS_LIST_REFRESH_MS) {
    await refreshMfStationsList();
  }
  await refreshMfObs();
}

// ── Module de traduction (commentaires), 08/07 ──────────────────────
// Nos codes langue (i18next, sans région) → codes cible Azure.
// Seul cas particulier : Azure fait de 'pt' nu un défaut vers le
// portugais BRÉSILIEN ("Language code pt defaults to pt-br" — doc
// officielle Azure, vérifié 08/07) ; nos traductions client (Lot 4)
// sont en portugais du Portugal, d'où le 'pt-pt' explicite ici. Les
// 7 autres langues correspondent telles quelles aux codes Azure.
const AZURE_LANG_MAP = {
  fr: 'fr', en: 'en', de: 'de', it: 'it',
  es: 'es', pt: 'pt-pt', nl: 'nl', sl: 'sl',
};

webpush.setVapidDetails(VAPID_EMAIL, VAPID_PUB, VAPID_PRIV);
const app = express();
// Render est derrière un proxy inverse (load balancer) : sans ça,
// express-rate-limit verrait l'IP du proxy pour tout le monde (un seul
// compteur partagé) au lieu de l'IP réelle de chaque appelant — ou lève
// une erreur si le header X-Forwarded-For est présent sans ce réglage.
app.set('trust proxy', 1);
app.use(express.json());
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Headers', 'Content-Type');
  res.header('Access-Control-Allow-Methods', 'GET,POST,DELETE,OPTIONS');
  if (req.method === 'OPTIONS') return res.sendStatus(200);
  next();
});

// ── Rate-limit global (F7, audit sécurité 30/06) ──
// 60 req/min/IP, recommandation du rapport. Combiné à F1 (test-push
// authentifié), ça ferme le risque résiduel de flood — chaque endpoint
// authentifié (/sync, /ack, /unsubscribe-device, /test-push) reste de
// toute façon borné au périmètre d'un seul compte.
const limiter = rateLimit({
  windowMs: 60 * 1000,
  max: 60,
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: 'Trop de requêtes, réessaie dans une minute.' },
});
app.use(limiter);

const SB_HEADERS = { 'apikey': SB_KEY, 'Authorization': `Bearer ${SB_KEY}`, 'Content-Type': 'application/json' };
async function sbGet(table, query='') { const r = await fetch(`${SB_URL}/rest/v1/${table}?${query}`, { headers: SB_HEADERS }); return r.json(); }
async function sbUpsert(table, body, onConflict) { const r = await fetch(`${SB_URL}/rest/v1/${table}?on_conflict=${onConflict}`, { method:'POST', headers:{...SB_HEADERS,'Prefer':'resolution=merge-duplicates,return=minimal'}, body:JSON.stringify(body) }); return r.ok; }
async function sbDelete(table, query) { const r = await fetch(`${SB_URL}/rest/v1/${table}?${query}`, { method:'DELETE', headers:SB_HEADERS }); return r.ok; }
async function sbPatch(table, query, body) { const r = await fetch(`${SB_URL}/rest/v1/${table}?${query}`, { method:'PATCH', headers:{...SB_HEADERS,'Prefer':'return=minimal'}, body:JSON.stringify(body) }); return r.ok; }
async function sbRpc(fn, body) { const r = await fetch(`${SB_URL}/rest/v1/rpc/${fn}`, { method:'POST', headers:SB_HEADERS, body:JSON.stringify(body) }); return r.json(); }

// ── AUTH : vérifie un access_token Supabase et renvoie le user (ou null) ──
// Le client envoie son access_token de session ; on ne fait JAMAIS confiance
// à un user_id envoyé tel quel par le client (sinon n'importe qui pourrait
// écrire dans la surveillance de quelqu'un d'autre).
async function verifyUser(accessToken) {
  if (!accessToken) return null;
  try {
    const r = await fetch(`${SB_URL}/auth/v1/user`, {
      headers: { 'apikey': SB_KEY, 'Authorization': `Bearer ${accessToken}` },
    });
    if (!r.ok) return null;
    const data = await r.json();
    return data?.id ? data : null;
  } catch { return null; }
}

app.get('/', (req, res) => res.json({ status:'ok', version:'2.1.0', service:'Balise Watch Push Server' }));
app.get('/vapid-public-key', (req, res) => res.json({ key: VAPID_PUB }));

// ── Débogage 12/07/2026 — source de pression par balise ─────────────
// Sert pressureSignalCache (alimenté à chaque poll, cf. plus haut) pour
// que le client affiche exactement la source/valeur utilisée pour les
// alertes (capteur embarqué en priorité, modèle AROME en repli) au lieu
// d'un repli client séparé qui pouvait diverger et n'affichait de toute
// façon aucune valeur (juste le mot "Arome" sans nombre). ?ids=1,2,3 —
// pas d'auth, même donnée publique en lecture que /meteofrance-stations.
// Une balise pas encore dans le cache (juste ajoutée, pas encore de
// poll passé dessus) renvoie null — le client garde alors son propre
// repli d'affichage ("pas encore de donnée").
app.get('/pressure-signal', (req, res) => {
  const ids = String(req.query.ids || '').split(',').map(s => s.trim()).filter(Boolean);
  const signals = {};
  for (const id of ids) signals[id] = pressureSignalCache.get(id) ?? null;
  res.json({ signals });
});

// ── Étape 11 : stations Météo-France avec vent (lecture seule) ──────
// Sert le cache mfObsCache/mfStationsList (rafraîchi en tâche de fond,
// cf. refreshMeteoFranceData) — jamais d'appel Météo-France déclenché
// par une requête client, jamais la clé API exposée côté client. Ne
// renvoie que les stations qui ont du vent dans le dernier paquet
// (pas de baromètre attendu chez le client si null, cf. réflexion
// pression Pioupiou) — pas d'auth requise, données publiques en lecture.
app.get('/meteofrance-stations', (req, res) => {
  const stationsById = new Map(mfStationsList.map(s => [s.id, s]));
  const out = [];
  for (const [id, obs] of mfObsCache) {
    if (obs.ff == null) continue;
    const meta = stationsById.get(id);
    if (!meta) continue;
    out.push({
      id, nom: meta.nom, lat: meta.lat, lon: meta.lon, alt: meta.alt,
      dd: obs.dd, ff: obs.ff, raf10: obs.raf10, ddraf10: obs.ddraf10,
      pres: obs.pres, pmer: obs.pmer, validityTime: obs.validityTime,
    });
  }
  res.json({ stations: out, fetchedAt: mfObsCacheFetchedAt });
});

// ── Étape 11 (suite, 11/07) — Historique court d'une station MF ─────
// Réutilise TEL QUEL le buffer RAM `beaconHistory` (cf. plus haut) déjà
// alimenté à CHAQUE poll (5 min, pollAndNotify) pour toute entrée de
// `releves` — donc aussi les stations MF avec du vent, fondues dedans
// depuis le Lot 7 suite. Aucun nouveau cache, aucun appel réseau ajouté.
// Limites assumées (vs l'archive Pioupiou, hébergée par Pioupiou) :
// (1) moy/direction/pression SEULEMENT — fwRecordHistory n'enregistre
// pas la rafale (jamais utilisée par les signaux flightwatch en amont),
// (2) 3h30 de profondeur MAX (FW_HISTORY_MAX_AGE_MS) pour CE buffer RAM,
// (3) buffer RAM pur, vidé à chaque redémarrage du process.
// Pas d'auth : même donnée publique en lecture que /meteofrance-stations.
//
// Lot 8 (12/07) — paramètre optionnel ?hours=N : SANS lui, comportement
// rigoureusement inchangé (buffer RAM 3h30 intégral, zéro risque de
// régression pour les appelants existants qui ne le précisent pas).
// Avec, et seulement si N dépasse la profondeur RAM (3h30), complète
// avec mf_station_history — la table persistante 48h créée ce même Lot
// (supabase_step13_mf_station_history.sql) — pour les points plus
// anciens que ce que le buffer RAM couvre encore. Le buffer RAM reste
// systématiquement la source des points les plus récents (jamais en
// retard, jamais remplacé par une lecture Supabase potentiellement
// périmée de quelques secondes).
app.get('/meteofrance-history/:id', async (req, res) => {
  const ramPts = beaconHistory.get(req.params.id) || [];
  const hoursParam = Number(req.query.hours);
  const hours = Number.isFinite(hoursParam) ? Math.min(Math.max(hoursParam, 0), MF_HISTORY_RETENTION_H) : null;
  if (!hours || hours * 3600 * 1000 <= FW_HISTORY_MAX_AGE_MS) {
    return res.json({ points: ramPts });
  }
  try {
    const cutoff = Date.now() - hours * 3600 * 1000;
    const oldPts = await sbGet(
      'mf_station_history',
      `station_id=eq.${encodeURIComponent(req.params.id)}&t=gte.${cutoff}&select=t,moy,dir,pressure&order=t.asc`
    );
    const ramCutoff = ramPts[0]?.t ?? Infinity; // évite les doublons : ne garde du passé persistant que ce qui précède le buffer RAM
    const merged = [...(Array.isArray(oldPts) ? oldPts.filter(p => p.t < ramCutoff) : []), ...ramPts];
    res.json({ points: merged });
  } catch (e) {
    console.error('meteofrance-history (hours) error:', e.message);
    res.json({ points: ramPts }); // dégradation gracieuse : au pire, la profondeur RAM habituelle
  }
});

// ── Lot 5 — Éclairs (public, lecture seule) ──────────────────────────
// Retourne le buffer RAM lightningStrikes, élagué aux 60 dernières
// minutes (fwLightningPrune appelé ici en garde-fou). Retourne [] si
// FW_LIGHTNING_ENABLED=0 (kill-switch env, bêta opt-in côté serveur).
// Pas d'auth : affiché en couche carte optionnelle, donnée publique.
app.get('/lightning-strikes', (req, res) => {
  fwLightningPrune();
  if (!FW_LIGHTNING_ENABLED) return res.json([]);
  res.json(lightningStrikes.map(s => ({ lat: s.lat, lon: s.lon, t: s.t })));
});

// ── /sync : lie l'appareil (endpoint push) au compte + remplace la liste
//    de surveillance du compte par celle envoyée (upsert + suppression
//    des balises qui ne sont plus dans la liste) ──
app.post('/sync', async (req, res) => {
  const { access_token, subscription, watched } = req.body;
  const user = await verifyUser(access_token);
  if (!user) return res.status(401).json({ error:'Session invalide ou expirée' });

  try {
    // subscription optionnelle : la surveillance doit pouvoir se synchroniser
    // au compte même si l'utilisateur n'a pas (encore) activé les push
    if (subscription?.endpoint) {
      await sbUpsert('user_devices', {
        user_id: user.id, endpoint: subscription.endpoint,
        p256dh: subscription.keys.p256dh, auth: subscription.keys.auth,
        updated_at: new Date().toISOString(),
      }, 'endpoint');
    }

    const list = watched || [];
    if (list.length) {
      const rows = list.map(w => ({
        user_id: user.id, beacon_id: String(w.id), beacon_nom: w.nom,
        seuil_moy: w.seuilMoy ?? null, seuil_rafale: w.seuilRafale ?? null,
        repeat_interval_min: w.repeatIntervalMin ?? null,
        // Lot 7 (suite) : 'pioupiou' si absent — colonne pas encore
        // créée tant que Yann n'a pas exécuté
        // supabase_step12_mf_stations_watch.sql (sbUpsert POST-erait
        // alors une colonne inconnue ; Supabase/PostgREST l'ignore
        // silencieusement pour les colonnes non reconnues côté insert
        // simple, donc pas de casse tant que le script n'a pas tourné —
        // MAIS l'onConflict ci-dessous suppose déjà la contrainte à 3
        // colonnes : à activer seulement après exécution du script).
        source: w.source ?? 'pioupiou',
        updated_at: new Date().toISOString(),
      }));
      await sbUpsert('user_watched', rows, 'user_id,beacon_id,source');
    }
    // Supprime les balises qui ne sont plus dans la liste envoyée
    const ids = list.map(w => String(w.id));
    const staleQuery = ids.length
      ? `user_id=eq.${user.id}&beacon_id=not.in.(${ids.map(encodeURIComponent).join(',')})`
      : `user_id=eq.${user.id}`;
    await sbDelete('user_watched', staleQuery);

    const deviceLabel = subscription?.endpoint ? `device ...${subscription.endpoint.slice(-12)}` : 'sans device';
    console.log(`✅ Sync ${user.email||user.id.slice(0,8)} — ${list.length} balise(s), ${deviceLabel}`);
    res.json({ success:true });
  } catch(e) { res.status(500).json({ error:e.message }); }
});

// ── /unsubscribe-device : détache un appareil du compte ──
app.delete('/unsubscribe-device', async (req, res) => {
  const { access_token, endpoint } = req.body;
  const user = await verifyUser(access_token);
  if (!user) return res.status(401).json({ error:'Session invalide ou expirée' });
  if (!endpoint) return res.status(400).json({ error:'Endpoint manquant' });
  await sbDelete('user_devices', `endpoint=eq.${encodeURIComponent(endpoint)}&user_id=eq.${user.id}`);
  res.json({ success:true });
});

// ── /ack : acquittement manuel d'une alerte en cours (étape 5) ──
// Stoppe les rappels pour CETTE surveillance jusqu'à ce que la balise
// repasse sous le seuil (réarmement automatique côté pollAndNotify).
// L'utilisateur ne peut acquitter que ses propres lignes — filtre user_id
// en plus de l'id, même si verifyUser garantit déjà l'identité.
app.post('/ack', async (req, res) => {
  const { access_token, beacon_id } = req.body;
  const user = await verifyUser(access_token);
  if (!user) return res.status(401).json({ error:'Session invalide ou expirée' });
  if (!beacon_id) return res.status(400).json({ error:'beacon_id manquant' });
  const ok = await sbPatch(
    'user_watched',
    `user_id=eq.${user.id}&beacon_id=eq.${encodeURIComponent(String(beacon_id))}`,
    { alert_acked_at: new Date().toISOString() }
  );
  if (!ok) return res.status(500).json({ error:'Échec acquittement' });
  console.log(`🔕 Ack ${user.email||user.id.slice(0,8)} — balise ${beacon_id}`);
  res.json({ success:true });
});

// ── /test-push : notif de test à tous les appareils enregistrés ──
// Réservé admin (F1, audit sécurité 30/06) : exige un access_token valide
// ET vérifie que le compte est admin avant tout envoi. Sans ça, n'importe
// qui sur Internet pouvait spammer une notif à TOUS les abonnés.
app.post('/test-push', async (req, res) => {
  const { access_token } = req.body;
  const user = await verifyUser(access_token);
  if (!user) return res.status(401).json({ error:'Session invalide ou expirée' });
  const admins = await sbGet('admins', `user_id=eq.${user.id}&select=user_id`);
  if (!admins?.length) return res.status(403).json({ error:'Réservé admin' });

  try {
    const devices = await sbGet('user_devices', 'select=*');
    if (!devices?.length) return res.json({ success:true, sent:0, message:'Aucun appareil enregistré' });
    let sent = 0, errors = 0;
    for (const dv of devices) {
      try {
        await webpush.sendNotification(
          { endpoint:dv.endpoint, keys:{ p256dh:dv.p256dh, auth:dv.auth } },
          JSON.stringify({ title:'🧪 Test Balise Watch', body:'Notification de test reçue avec succès !', icon:'/apple-touch-icon.png', badge:'/apple-touch-icon.png', tag:'test-push', data:{ url:'/' } })
        );
        sent++;
      } catch(err) {
        if (err.statusCode===410||err.statusCode===404) { await sbDelete('user_devices', `endpoint=eq.${encodeURIComponent(dv.endpoint)}`); }
        else { console.warn(`⚠️ Test-push error ${err.statusCode}: ${err.message}`); errors++; }
      }
    }
    console.log(`🧪 Test-push: ${sent} envoyés, ${errors} erreurs`);
    res.json({ success:true, sent, errors });
  } catch(e) { res.status(500).json({ error:e.message }); }
});

// ── /translate : traduction à la demande d'un commentaire (08/07) ──
// Auth requise (accès réservé aux comptes connectés, comme le reste
// de l'app) mais PAS admin — n'importe quel pilote peut traduire un
// commentaire qu'il lit. Cache-first : ne rappelle DeepL que si la
// paire (contenu, langue cible) n'a jamais été traduite. Garde-fou
// quota avant tout appel payant : /v2/usage ne consomme pas le quota
// de traduction, on peut donc le vérifier à chaque fois sans coût.
app.post('/translate', async (req, res) => {
  const { access_token, content_type, content_id, text, target_lang } = req.body;
  const user = await verifyUser(access_token);
  if (!user) return res.status(401).json({ error:'Session invalide ou expirée' });
  if (!AZURE_TRANSLATOR_KEY) return res.status(503).json({ error:'Traduction non configurée' });
  if (content_type !== 'beacon_comment') return res.status(400).json({ error:'Type de contenu non pris en charge' });
  if (!content_id || !text || !target_lang) return res.status(400).json({ error:'Paramètres manquants' });
  const azureLang = AZURE_LANG_MAP[target_lang];
  if (!azureLang) return res.status(400).json({ error:'Langue non prise en charge' });

  try {
    const cached = await sbGet(
      'content_translations',
      `content_type=eq.${content_type}&content_id=eq.${content_id}&target_lang=eq.${target_lang}&select=translated_text,source_lang`,
    );
    if (Array.isArray(cached) && cached.length) {
      return res.json({ translatedText: cached[0].translated_text, sourceLang: cached[0].source_lang, cached: true });
    }

    // Jamais de bascule silencieuse vers du payant (app gratuite, sans
    // financement) : Azure n'expose pas d'endpoint "quota restant" (à
    // la différence de DeepL) — on compte nous-mêmes les caractères
    // envoyés ce mois-ci et on refuse avant de dépasser le palier F0.
    const month = new Date().toISOString().slice(0, 7); // 'YYYY-MM'
    const usageRows = await sbGet('translation_usage_monthly', `month=eq.${month}&select=chars_used`);
    const used = Array.isArray(usageRows) && usageRows.length ? usageRows[0].chars_used : 0;
    if (used + text.length + 5000 > AZURE_MONTHLY_CHAR_LIMIT) {
      return res.status(503).json({ error:'Quota de traduction mensuel atteint' });
    }

    const trRes = await fetch(
      `${AZURE_TRANSLATOR_URL}/translate?api-version=3.0&to=${encodeURIComponent(azureLang)}`,
      {
        method: 'POST',
        headers: {
          'Ocp-Apim-Subscription-Key': AZURE_TRANSLATOR_KEY,
          ...(AZURE_TRANSLATOR_REGION ? { 'Ocp-Apim-Subscription-Region': AZURE_TRANSLATOR_REGION } : {}),
          'Content-Type': 'application/json',
        },
        body: JSON.stringify([{ text }]),
      },
    );
    if (!trRes.ok) return res.status(502).json({ error:'Erreur du service de traduction' });
    const trData = await trRes.json();
    const translated = trData?.[0]?.translations?.[0]?.text;
    const sourceLang = trData?.[0]?.detectedLanguage?.language ?? null;
    if (!translated) return res.status(502).json({ error:'Réponse de traduction invalide' });

    await sbUpsert(
      'content_translations',
      { content_type, content_id, target_lang, translated_text: translated, source_lang: sourceLang },
      'content_type,content_id,target_lang',
    );
    // Comptabilise APRÈS succès uniquement — un échec Azure ne doit pas
    // consommer de quota côté compteur maison.
    await sbRpc('increment_translation_usage', { p_month: month, p_chars: text.length });

    res.json({ translatedText: translated, sourceLang, cached: false });
  } catch (e) { res.status(500).json({ error: e.message }); }
});

async function pollAndNotify() {
  console.log(`[${new Date().toLocaleTimeString('fr-FR')}] Polling...`);
  try {
    const r = await fetch(API_ALL);
    const d = await r.json();
    const releves = {};
    // dir/lat/lon : déjà présents dans la même réponse API (aucune nouvelle
    // source, cf. cadrage §2 point 4) — ajoutés pour les signaux flightwatch
    // Lot 1 (montée du vent = dérivée sur `moy` ; bascule de brise = `dir` +
    // proximité géo entre balises surveillées).
    (d.data||[]).forEach(b => { releves[String(b.id)] = {
      moy: b.measurements?.wind_speed_avg ?? null,
      raf: b.measurements?.wind_speed_max ?? null,
      dir: b.measurements?.wind_heading ?? null,
      pressure: b.measurements?.pressure ?? null, // Lot 2b : baromètre embarqué, null si la balise n'en a pas — même champ déjà lu côté client dans l'archive Pioupiou
      lat: b.location?.latitude ?? null,
      lon: b.location?.longitude ?? null,
      nom: b.meta?.name || `Balise ${b.id}`,
    }; });

    // Lot 7 (suite, 11/07/2026) — fusion des stations Météo-France
    // surveillées dans `releves`, EXACT même format que les balises
    // Pioupiou ci-dessus. Choix de Yann : une station MF surveillée doit
    // déclencher les mêmes alertes seuil moy/rafale qu'une balise
    // Pioupiou — en la fondant dans `releves` avec les mêmes clés, TOUTE
    // la logique en aval (seuils classiques § plus bas, ET les signaux
    // flightwatch génériques : montée de vent, chute de pression réelle,
    // etc.) fonctionne SANS AUCUNE branche conditionnelle sur la source.
    // mfObsCache/mfStationsList sont déjà maintenus indépendamment (cf.
    // refreshMeteoFranceData, poll 6 min) — lecture pure ici, aucun appel
    // réseau ajouté à ce poll. Seules les stations avec du vent effectif
    // sont utilisables (même filtre que /meteofrance-stations).
    // fwPollT hoisté ici (au lieu de juste avant fwRecordHistory plus bas)
    // pour aussi horodater les lignes de mf_station_history créées dans
    // CETTE boucle, avec le même instant que le reste du poll (Lot 8, 12/07).
    const fwPollT = Date.now();
    const mfHistoryRows = []; // Lot 8 (12/07) — persistance 48h, cf. mfPersistHistory
    const mfStationsById = new Map(mfStationsList.map(s => [s.id, s]));
    for (const [mfId, obs] of mfObsCache) {
      if (obs.ff == null) continue;
      const meta = mfStationsById.get(mfId);
      if (!meta) continue;
      // DATA-1 : garde-fraîcheur — si validityTime est connue et trop vieille
      // (API MF en panne depuis > 30 min, mfObsCache figé), on ignore cette
      // observation plutôt que d'évaluer du vent qui n'existe peut-être plus.
      // Si validityTime est null (champ absent du paquet), on laisse passer :
      // dégradation gracieuse, mieux qu'un silence total.
      if (obs.validityTime) {
        const ageMs = Date.now() - new Date(obs.validityTime).getTime();
        if (ageMs > MF_OBS_MAX_AGE_MS) continue;
      }
      releves[mfId] = {
        moy: obs.ff, raf: obs.raf10, dir: obs.dd,
        pressure: obs.pmer ?? null, // FIA-3 : n'utiliser QUE pmer (pression ramenée au niveau de la mer) — mélanger pmer et pres (pression station, différente de ~50-100 hPa en montagne) produirait une fausse chute de dizaines de hPa/h si le pipeline alterne les champs entre deux polls
        lat: meta.lat, lon: meta.lon, nom: meta.nom,
      };
      // Lot 8 (12/07) — même échantillon que fwRecordHistory plus bas
      // (moy/dir/pressure, pas de rafale — jamais enregistrée pour les
      // stations MF, même limitation assumée), mais destiné à
      // mf_station_history (persistant 48h) plutôt qu'au buffer RAM.
      mfHistoryRows.push({ station_id: mfId, t: fwPollT, moy: obs.ff, dir: obs.dd, pressure: obs.pmer ?? null });
    }
    mfPersistHistory(mfHistoryRows); // fire-and-forget — cf. définition, ne bloque/casse jamais la suite du poll

    // Historique flightwatch (Lot 1, +pressure Lot 2b) : un échantillon par
    // balise réelle à chaque poll, AVANT d'ajouter la balise de test
    // (fictive, pas de dérive physique à surveiller). Sert aux dérivées
    // vent/direction/pression ci-dessous (fwBaselineAt / fwRealPressureTrend).
    // fwPollT hoisté plus haut (avant la boucle MF, Lot 8) — inchangé ici.
    Object.entries(releves).forEach(([id, rel]) => {
      fwRecordHistory(id, { t: fwPollT, moy: rel.moy, dir: rel.dir, pressure: rel.pressure });
    });
    const testData = await sbGet('test_beacon', 'id=eq.singleton&select=*');
    const test = testData?.[0];
    if (test?.enabled) releves['__test__'] = { moy:test.wind_avg, raf:test.wind_max, nom:'🧪 '+(test.label||'Balise de test') };

    const watchedRows = await sbGet('user_watched', 'select=*');
    if (!watchedRows?.length) { console.log('Aucune balise surveillée'); return; }

    const devices = await sbGet('user_devices', 'select=*');
    const devicesByUser = {};
    (devices||[]).forEach(dv => { (devicesByUser[dv.user_id] ??= []).push(dv); });

    // Session débogage 01/07 : la surveillance (liste de balises,
    // user_watched) ne suffit plus à elle seule pour alerter — il faut
    // aussi que le compte ait explicitement DÉMARRÉ la surveillance
    // (bouton dédié, PWA). Sans ça, un pilote recevait des push dès
    // qu'une balise était dans sa liste, même chez lui/au travail,
    // jamais parti voler. Pas de ligne dans user_surveillance = traité
    // comme inactif par défaut (comportement sûr pour tout compte qui
    // n'a encore jamais démarré la surveillance sous ce système).
    // select élargi (Lot 1 flightwatch) : les colonnes de prefs voyagent
    // avec la même lecture que le flag `active` (décision coût Lot 0,
    // §2 — zéro requête ajoutée par poll). Même repli défensif qu'avant :
    // si sbGet échoue (table/colonnes pas prêtes), on retombe sur une
    // liste vide -> personne actif -> aucun push (météo ou seuil), jamais
    // de crash.
    const surveillanceRows = await sbGet('user_surveillance',
      // beta_lightning : accès bêta foudre Blitzortung, activé par l'admin par compte
      // (colonne ajoutée par beta_lightning.sql — défaut FALSE, invisible pour les non-bêta)
      'select=user_id,active,sig_wind_surge,sig_breeze_reversal,sig_pressure_drop,sig_convection,sig_vigilance,sig_lightning,sig_freezing_level,lightning_radius_km,wind_surge_factor,wind_surge_window_min,pressure_drop_hpa_h,voice_enabled,beta_lightning');
    const activeByUser = new Set(
      (Array.isArray(surveillanceRows) ? surveillanceRows : []).filter(s => s.active).map(s => s.user_id)
    );
    // Préférences flightwatch par compte (Lot 1) : mêmes lignes que
    // ci-dessus, défauts sains appliqués via fwPrefs (cf. plus haut).
    const prefsByUser = new Map(
      (Array.isArray(surveillanceRows) ? surveillanceRows : []).map(s => [s.user_id, fwPrefs(s)])
    );
    const betaByUser = new Map(
      (Array.isArray(surveillanceRows) ? surveillanceRows : []).map(s => [s.user_id, !!s.beta_lightning])
    );

    // ── Lot 5 flightwatch : foudre Blitzortung — connexion WS à la demande ──
    // Recalcule à chaque poll si au moins un compte actif a besoin de la
    // foudre ; fwLightningSetNeeded ouvre/maintient ou programme la fermeture
    // de la connexion WS en conséquence (pas de firehose mondial inutile).
    // Prune du buffer glissant au passage. Défensif : si tout est absent/coupé
    // le buffer reste vide et le signal ne sera simplement pas évalué plus bas.
    // beta_lightning : seuls les comptes explicitement activés par l'admin
    // reçoivent le signal foudre. Double garde : FW_LIGHTNING_ENABLED (env var
    // Render, doit être posé à '1' manuellement) ET beta_lightning par compte.
    const anyLightningWanted = (Array.isArray(surveillanceRows) ? surveillanceRows : [])
      .some(s => s.active && s.beta_lightning && fwPrefs(s).sig_lightning);
    fwLightningSetNeeded(anyLightningWanted);
    fwLightningPrune();

    // Langue par compte (Lot 3) : même lecture batchée par table que
    // surveillanceRows ci-dessus (sbGet sur user_language, jamais
    // l'Admin API Auth — voir supabase_step10_user_language.sql). Repli
    // défensif identique : si la table n'existe pas encore côté
    // Supabase ou toute erreur de fetch, sbGet renvoie un objet
    // d'erreur (pas un tableau) — Map vide -> pushLabels() retombe sur
    // 'en' pour tout le monde, aucun crash de pollAndNotify.
    const languageRows = await sbGet('user_language', 'select=user_id,lang');
    const langByUser = new Map(
      (Array.isArray(languageRows) ? languageRows : []).map(l => [l.user_id, l.lang])
    );

    // État d'alerte flightwatch (Lot 1) : mêmes défensifs que le reste —
    // table pas encore créée (SQL Lot 0 pas exécuté) → sbGet renvoie une
    // erreur, pas un tableau → Map vide → tout signal se comporte comme
    // "jamais encore alerté" (envoi immédiat au 1er dépassement dès que la
    // table existera, aucun crash entre-temps).
    const fwAlertRows = await sbGet('user_flightwatch_alerts', 'select=*');
    const fwAlertMap = new Map(
      (Array.isArray(fwAlertRows) ? fwAlertRows : []).map(r => [`${r.user_id}|${r.scope}|${r.signal}`, r])
    );

    // Cycle d'alerte par signal (mirroir du cycle user_watched étape 5,
    // mais par (user, scope, signal) — cf. §2 FLIGHTWATCH_LOT0.md).
    // `active=false` réarme silencieusement (alert_active=false,
    // acked_at=null) sans envoyer de push, exactement comme le
    // réarmement des seuils vent existants.
    async function evaluateFwSignal({ userId, scope, signal, level, active, buildPush, repeatMs }) {
      const key = `${userId}|${scope}|${signal}`;
      const row = fwAlertMap.get(key);
      const now = Date.now();

      if (!active) {
        if (row?.alert_active) {
          await sbUpsert('user_flightwatch_alerts', {
            user_id: userId, scope, signal, level,
            alert_active: false, alert_acked_at: null,
            updated_at: new Date(now).toISOString(),
          }, 'user_id,scope,signal');
        }
        return;
      }

      const lastSent = row?.alert_last_sent ? new Date(row.alert_last_sent).getTime() : 0;
      const justActivated = !row?.alert_active;
      const acked = row?.alert_acked_at && new Date(row.alert_acked_at).getTime() >= lastSent;
      if (acked && !justActivated) return;
      const repeatWindow = repeatMs || FW_ALERT_REPEAT_MS; // anti-répétition par défaut 15 min, surchargée par signal (ex. foudre 10 min, Lot 5)
      if (!justActivated && (now - lastSent) < repeatWindow) return;

      const userDevices = devicesByUser[userId] || [];
      for (const dv of userDevices) {
        try {
          await webpush.sendNotification(
            { endpoint: dv.endpoint, keys: { p256dh: dv.p256dh, auth: dv.auth } },
            JSON.stringify(buildPush())
          );
          console.log(`📲 Push flightwatch → ${signal} (${scope})`);
        } catch (err) {
          if (err.statusCode === 410 || err.statusCode === 404) { await sbDelete('user_devices', `endpoint=eq.${encodeURIComponent(dv.endpoint)}`); }
          else console.warn(`⚠️ Push flightwatch error ${err.statusCode}`);
        }
      }

      await sbUpsert('user_flightwatch_alerts', {
        user_id: userId, scope, signal, level,
        alert_active: true, alert_last_sent: new Date(now).toISOString(),
      }, 'user_id,scope,signal');
    }

    console.log(`${new Set(watchedRows.map(w=>w.user_id)).size} compte(s), ${watchedRows.length} surveillance(s), ${activeByUser.size} avec surveillance démarrée`);

    // Balises surveillées valides (lat/lon/dir connus) par compte actif
    // avec le signal bascule de brise activé — alimenté dans la boucle
    // ci-dessous, consommé juste après (§ bascule de brise).
    const watchedBeaconsByUser = new Map();

    // ── Lot 2/3 flightwatch : signaux Open-Meteo (mutualisés) ──────────
    // UNE requête par balise distincte surveillée par au moins un compte
    // actif avec sig_pressure_drop OU sig_convection activé — jamais par
    // (compte, balise), même principe que le mutualisme Pioupiou existant.
    // Un seul appel sert les deux signaux (cf. fetchOpenMeteoSignals) :
    // pas de requête séparée pour la convection (cadrage Lot 3). Récupérée
    // AVANT la boucle principale pour être disponible en lecture pure
    // (Map) dans la boucle, sans appel réseau par itération.
    const weatherBeaconIds = new Set();
    for (const w of watchedRows) {
      if (!activeByUser.has(w.user_id)) continue;
      const prefs = prefsByUser.get(w.user_id) || fwPrefs(null);
      if (!prefs.sig_pressure_drop && !prefs.sig_convection) continue;
      const rel = releves[String(w.beacon_id)];
      if (!rel || rel.lat == null || rel.lon == null) continue;
      weatherBeaconIds.add(String(w.beacon_id));
    }
    const weatherByBeacon = new Map();
    const weatherIdsCapped = [...weatherBeaconIds].slice(0, FW_OM_MAX_BEACONS_PER_POLL);
    if (weatherBeaconIds.size > weatherIdsCapped.length) {
      console.warn(`⚠️ flightwatch Open-Meteo : ${weatherBeaconIds.size - weatherIdsCapped.length} balise(s) ignorée(s) (garde-fou FW_OM_MAX_BEACONS_PER_POLL)`);
    }
    for (const id of weatherIdsCapped) {
      const rel = releves[id];
      const signals = await fetchOpenMeteoSignals(rel.lat, rel.lon);
      if (signals) weatherByBeacon.set(id, signals);
    }

    // ── Lot 4 flightwatch : vigilance Météo-France (mutualisée) ────────
    // Mapping balise -> département résolu une fois par balise (cache
    // permanent, cf. getBeaconDepartment) pour tout compte actif avec
    // sig_vigilance activé. La carte de vigilance elle-même est UN SEUL
    // appel national (fetchVigilanceColors), pas par département/balise —
    // demandé seulement s'il y a au moins une balise à évaluer, pour ne
    // pas déclencher inutilement le flux OAuth si personne n'a activé ce
    // signal ou si METEOFRANCE_APP_ID n'est pas configuré.
    const beaconDeptById = new Map();
    for (const w of watchedRows) {
      if (!FW_VIGILANCE_ENABLED) break; // vigilance retirée (cf. FW_VIGILANCE_ENABLED) -> map vide -> aucune évaluation en aval
      if (!activeByUser.has(w.user_id)) continue;
      const prefs = prefsByUser.get(w.user_id) || fwPrefs(null);
      if (!prefs.sig_vigilance) continue;
      const bid = String(w.beacon_id);
      if (beaconDeptById.has(bid)) continue;
      const rel = releves[bid];
      if (!rel || rel.lat == null || rel.lon == null) continue;
      beaconDeptById.set(bid, await getBeaconDepartment(bid, rel.lat, rel.lon));
    }
    const vigilanceColors = beaconDeptById.size > 0 ? await fetchVigilanceColors() : null;
    // Regroupement (compte, département) -> noms de balises concernées,
    // alimenté dans la boucle principale, consommé juste après (comme le
    // patron bascule de brise) : on ne veut PAS un push par balise si un
    // compte a 2 balises dans le même département, un seul par département
    // suffit (la vigilance ne varie pas à l'intérieur d'un département).
    const vigilanceByUserDept = new Map();

    for (const w of watchedRows) {
      const rel = releves[String(w.beacon_id)];
      if (!rel) continue;

      // Surveillance non démarrée pour ce compte : aucune alerte, ni
      // push ni (indirectement) voix — la voix est déjà bloquée côté
      // client par le même bouton. On réarme aussi l'état d'alerte tout
      // de suite plutôt que de le laisser traîner : à la prochaine
      // activation, un dépassement déjà en cours redéclenche un envoi
      // immédiat (justActivated ci-dessous), sans devoir attendre un
      // repeat_interval_min hérité d'une session d'avant l'arrêt.
      if (!activeByUser.has(w.user_id)) {
        if (w.alert_active || w.alert_acked_at) {
          await sbPatch('user_watched', `id=eq.${w.id}`, { alert_active: false, alert_acked_at: null });
        }
        continue;
      }

      // ── Lot 1 flightwatch : montée soudaine du vent ──────────────
      // Dérivée pure sur la balise déjà surveillée : compare le relevé
      // courant à la référence prise ~`wind_surge_window_min` minutes
      // plus tôt (fwBaselineAt, historique en RAM ci-dessus). Indépendant
      // des seuils moy/rafale de user_watched (peut se déclencher même
      // sous le seuil habituel — c'est la VITESSE de montée qui compte,
      // pas la valeur absolue). Niveau 3 (danger imminent, §7.5 cadrage :
      // "vent qui explose sur ta balise").
      const fwPrefsForUser = prefsByUser.get(w.user_id) || fwPrefs(null);
      if (fwPrefsForUser.sig_wind_surge) {
        const baseline = fwBaselineAt(String(w.beacon_id), fwPrefsForUser.wind_surge_window_min);
        let surging = false;
        if (baseline && baseline.moy != null && rel.moy != null) {
          const effBaseline = Math.max(baseline.moy, FW_WIND_MIN_BASELINE_KMH);
          // FIA-1 : double condition — plancher absolu ET facteur multiplicatif.
          // Sans plancher absolu, un vent à 5,4 km/h avec baseline à 3 km/h
          // suffisait à déclencher un niveau 3 (voix) : bruit inacceptable
          // par vent calme. FW_WIND_SURGE_ABS_MIN_KMH = 15 km/h est
          // documenté en constante serveur — ajustable à l'usage.
          surging = rel.moy >= FW_WIND_SURGE_ABS_MIN_KMH &&
                    rel.moy >= effBaseline * fwPrefsForUser.wind_surge_factor;
        }
        const lbl = pushLabels(langByUser.get(w.user_id)).flightwatch.windSurge;
        await evaluateFwSignal({
          userId: w.user_id, scope: String(w.beacon_id), signal: 'wind_surge', level: 3, active: surging,
          buildPush: () => ({
            title: `💨 ${rel.nom}`,
            body: lbl.body(Math.round(rel.moy), Math.round(baseline.moy), fwPrefsForUser.wind_surge_window_min),
            icon: '/apple-touch-icon.png', badge: '/apple-touch-icon.png',
            tag: `fw-wind_surge-${w.beacon_id}`, requireInteraction: true,
            data: {
              url: '/', kind: 'flightwatch', signal: 'wind_surge', level: 3,
              scope: String(w.beacon_id), voice: !!fwPrefsForUser.voice_enabled,
              value: rel.moy, unit: 'km/h',
            },
          }),
        });
      }

      // ── Lot 5 flightwatch : foudre temps réel (Blitzortung) ──────
      // Compte les impacts bufferisés (ingestion WS temps réel, cf. haut du
      // fichier) à <= lightning_radius_km de la balise sur la fenêtre récente.
      // Niveau 3 (danger imminent, §7.5 : "foudre dans le rayon") + voix si
      // activée — MAIS donnée INDICATIVE et NON OFFICIELLE (réseau bénévole
      // Blitzortung) : le corps du push le dit explicitement (garde-fou n°1
      // "aide à la décision, jamais garantie"). Anti-répétition DÉDIÉE
      // (FW_LIGHTNING_REPEAT_MS ~10 min) passée à evaluateFwSignal : un orage
      // = un push par épisode puis rappel tant que des impacts tombent dans la
      // zone, jamais un push par impact. Buffer vide (WS coupé, démarrage,
      // kill switch) -> count 0 -> active=false -> pas d'alerte, jamais de crash.
      if (FW_LIGHTNING_ENABLED && betaByUser.get(w.user_id) && fwPrefsForUser.sig_lightning && rel.lat != null && rel.lon != null) {
        const radiusKm = fwPrefsForUser.lightning_radius_km;
        const strikeCount = fwLightningCountNear(rel.lat, rel.lon, radiusKm, FW_LIGHTNING_WINDOW_MIN);
        const lbl = pushLabels(langByUser.get(w.user_id)).flightwatch.lightning;
        await evaluateFwSignal({
          userId: w.user_id, scope: String(w.beacon_id), signal: 'lightning', level: 3, active: strikeCount > 0,
          repeatMs: FW_LIGHTNING_REPEAT_MS,
          buildPush: () => ({
            title: `⛈️ ${rel.nom}`,
            body: lbl.body(strikeCount, radiusKm, FW_LIGHTNING_WINDOW_MIN),
            icon: '/apple-touch-icon.png', badge: '/apple-touch-icon.png',
            tag: `fw-lightning-${w.beacon_id}`, requireInteraction: true,
            data: {
              url: '/', kind: 'flightwatch', signal: 'lightning', level: 3,
              scope: String(w.beacon_id), voice: !!fwPrefsForUser.voice_enabled,
              value: strikeCount, unit: 'strikes',
            },
          }),
        });
      }

      // ── Lot 2/2b flightwatch : chute de pression rapide ────────────
      // Lot 2b : préfère la pression RÉELLE mesurée par le baromètre de la
      // balise (fwRealPressureTrend, beaconHistory) — repli sur le modèle
      // Open-Meteo (weatherByBeacon, mutualisé par balise, calculé en amont)
      // seulement si la balise n'a pas de baromètre ou pas encore assez de
      // recul dans l'historique (cf. FW_PRESSURE_MIN_SAMPLES_SPAN_MIN). Si
      // aucune des deux source n'est disponible : on N'ÉVALUE PAS ce
      // poll-ci — ni alerte ni reset — plutôt que de risquer un faux reset
      // sur un simple aléa réseau/capteur (§8 garde-fou "informer, pas
      // juger"). Niveau 2 (vigilance, §7.5 cadrage : "pression qui chute").
      const fwWeather = weatherByBeacon.get(String(w.beacon_id));
      const fwPressureReal = fwRealPressureTrend(String(w.beacon_id), rel.pressure);
      const fwPressure = fwPressureReal ?? fwWeather?.pressure ?? null;
      // Débogage 12/07/2026 — mémorise la source effectivement retenue
      // (capteur si dispo, sinon modèle AROME, sinon aucune) pour cette
      // balise, servie par GET /pressure-signal (voir WatchCard côté
      // client). Écriture idempotente : plusieurs comptes surveillant la
      // même balise réécrivent la même valeur, sans coût réel.
      pressureSignalCache.set(String(w.beacon_id), {
        source: fwPressureReal ? 'sensor' : fwWeather?.pressure ? 'model' : null,
        value: fwPressure?.now ?? null,
        rate: fwPressure?.rate ?? null,
        updatedAt: Date.now(),
      });
      if (fwPrefsForUser.sig_pressure_drop && fwPressure?.rate != null) {
        const dropping = fwPressure.rate <= -fwPrefsForUser.pressure_drop_hpa_h;
        const lbl = pushLabels(langByUser.get(w.user_id)).flightwatch.pressureDrop;
        await evaluateFwSignal({
          userId: w.user_id, scope: String(w.beacon_id), signal: 'pressure_drop', level: 2, active: dropping,
          buildPush: () => ({
            title: `📉 ${rel.nom}`,
            body: lbl.body(Math.abs(fwPressure.rate).toFixed(1), FW_TREND_WINDOW_H),
            icon: '/apple-touch-icon.png', badge: '/apple-touch-icon.png',
            tag: `fw-pressure_drop-${w.beacon_id}`, requireInteraction: false,
            data: {
              url: '/', kind: 'flightwatch', signal: 'pressure_drop', level: 2,
              scope: String(w.beacon_id), voice: false, // niveau 2 = push doux
              value: fwPressure.rate, unit: 'hPa/h',
            },
          }),
        });
      }

      // ── Lot 3 flightwatch : risque de développement convectif ───
      // Déclencheur PRINCIPAL = CAPE (plancher + hausse sur la fenêtre,
      // cf. constantes FW_CONVECTION_*) ; nébulosité basse/moyenne et
      // iso 0°C = CONTEXTE informatif dans le corps du push, pas des
      // conditions supplémentaires (cf. commentaire des constantes plus
      // haut — éviter de multiplier les signaux bruités en ET). Même
      // garde-fou "pas de tendance disponible -> pas d'évaluation" que
      // pressure_drop. Niveau 2 (vigilance, §7.5 : "CAPE qui monte").
      if (fwPrefsForUser.sig_convection && fwWeather?.cape?.now != null && fwWeather.cape.rate != null) {
        const capeNow = fwWeather.cape.now;
        const capeRise = fwWeather.cape.rate * FW_TREND_WINDOW_H; // hausse totale sur la fenêtre (J/kg), plus lisible qu'un taux/h pour du CAPE
        const developing = capeNow >= FW_CONVECTION_CAPE_MIN_JKG && capeRise >= FW_CONVECTION_CAPE_RISE_MIN_JKG;
        // FIA-4 : deux couvertures 0-100% indépendantes ne s'additionnent
        // pas (elles se recouvrent partiellement) — Math.max() donne la
        // meilleure approximation de la fraction de ciel réellement couverte.
        // L'addition pouvait afficher "160%" dans le corps du push.
        const cloudLowMid = Math.round(Math.max(fwWeather.cloudLowNow ?? 0, fwWeather.cloudMidNow ?? 0));
        const freezingRounded = fwWeather.freezingLevelNow != null ? Math.round(fwWeather.freezingLevelNow) : null;
        const lbl = pushLabels(langByUser.get(w.user_id)).flightwatch.convection;
        await evaluateFwSignal({
          userId: w.user_id, scope: String(w.beacon_id), signal: 'convection', level: 2, active: developing,
          buildPush: () => ({
            title: `⛈️ ${rel.nom}`,
            body: lbl.body(Math.round(capeNow), cloudLowMid, freezingRounded),
            icon: '/apple-touch-icon.png', badge: '/apple-touch-icon.png',
            tag: `fw-convection-${w.beacon_id}`, requireInteraction: false,
            data: {
              url: '/', kind: 'flightwatch', signal: 'convection', level: 2,
              scope: String(w.beacon_id), voice: false, // niveau 2 = push doux
              value: capeNow, unit: 'J/kg',
            },
          }),
        });
      }

      // ── Lot 4 flightwatch : vigilance Météo-France (préparation) ─
      // Comme la brise, on ne décide rien balise par balise : la
      // vigilance est PAR DÉPARTEMENT (pas par balise), donc si un compte
      // a 2 balises dans le même département on ne veut qu'UN push, pas
      // deux. On collecte ici (compte, département) -> noms de balises,
      // l'évaluation elle-même se fait après la boucle (cf. plus bas).
      if (FW_VIGILANCE_ENABLED && fwPrefsForUser.sig_vigilance) {
        const dept = beaconDeptById.get(String(w.beacon_id));
        if (dept) {
          const key = `${w.user_id}|${dept}`;
          const entry = vigilanceByUserDept.get(key) || { userId: w.user_id, dept, names: new Set() };
          entry.names.add(rel.nom);
          vigilanceByUserDept.set(key, entry);
        }
      }

      // ── Lot 1 flightwatch : bascule de brise (préparation) ───────
      // On ne décide rien balise par balise : la cohérence multi-balises
      // se juge une fois toutes les balises du compte connues (après
      // cette boucle). On collecte ici seulement les balises valides
      // (lat/lon/dir présents) pour un compte qui a le signal activé.
      if (fwPrefsForUser.sig_breeze_reversal && rel.lat != null && rel.lon != null && rel.dir != null) {
        const arr = watchedBeaconsByUser.get(w.user_id) || [];
        arr.push({ beaconId: String(w.beacon_id), rel, windowMin: fwPrefsForUser.wind_surge_window_min, prefs: fwPrefsForUser });
        watchedBeaconsByUser.set(w.user_id, arr);
      }

      const overM = rel.moy!==null && w.seuil_moy    && rel.moy>=w.seuil_moy;
      const overR = rel.raf!==null && w.seuil_rafale && rel.raf>=w.seuil_rafale;
      const now = Date.now();

      if (!overM && !overR) {
        // Repassé sous le seuil : réarme l'alerte pour la prochaine fois
        // (alert_active + alert_acked_at remis à zéro). On ne touche pas
        // alert_last_sent (inutile, et garde une trace pour debug).
        if (w.alert_active) {
          await sbPatch('user_watched', `id=eq.${w.id}`,
            { alert_active: false, alert_acked_at: null });
        }
        continue;
      }

      // Alerte en cours. Intervalle de rappel : réglage utilisateur
      // (plancher 5 min imposé en base) sinon 10 min par défaut (valeur
      // historique du serveur).
      const intervalMs = (w.repeat_interval_min ?? 10) * 60 * 1000;
      const lastSent = w.alert_last_sent ? new Date(w.alert_last_sent).getTime() : 0;
      const justActivated = !w.alert_active;

      // Acquittée et toujours dans le même épisode de dépassement (pas
      // de réarmement) : on ne renvoie plus, mais on marque quand même
      // alert_active=true si ce n'était pas encore le cas (1er passage
      // au-dessus du seuil après un ancien ack qui n'a jamais été reset
      // — cas limite défensif, ne devrait pas arriver vu le reset ci-dessus).
      const acked = w.alert_acked_at && new Date(w.alert_acked_at).getTime() >= lastSent;
      if (acked && !justActivated) {
        continue;
      }

      if (!justActivated && (now-lastSent) < intervalMs) continue;

      const lbl = pushLabels(langByUser.get(w.user_id));
      let body='';
      if (overM) body+=`${lbl.avg} ${Math.round(rel.moy)} km/h`;
      if (overM&&overR) body+=' · ';
      if (overR) body+=`${lbl.gust} ${Math.round(rel.raf)} km/h`;

      const userDevices = devicesByUser[w.user_id] || [];
      let anySent = false;
      for (const dv of userDevices) {
        try {
          await webpush.sendNotification(
            { endpoint:dv.endpoint, keys:{ p256dh:dv.p256dh, auth:dv.auth } },
            JSON.stringify({ title:`⚠️ ${rel.nom}`, body, icon:'/apple-touch-icon.png', badge:'/apple-touch-icon.png', tag:`alert-${w.beacon_id}`, data:{ url:'/' } })
          );
          console.log(`📲 Push → ${rel.nom} (${body})`);
          anySent = true;
        } catch(err) {
          if (err.statusCode===410||err.statusCode===404) { await sbDelete('user_devices', `endpoint=eq.${encodeURIComponent(dv.endpoint)}`); }
          else console.warn(`⚠️ Push error ${err.statusCode}`);
        }
      }

      // Marque l'alerte active + l'horodatage même si l'utilisateur n'a
      // aucun device (sinon justActivated resterait vrai indéfiniment et
      // l'intervalle ne serait jamais respecté pour un compte sans push).
      await sbPatch('user_watched', `id=eq.${w.id}`,
        { alert_active: true, alert_last_sent: new Date(now).toISOString() });
      void anySent;
    }

    // ── Lot 1 flightwatch : bascule de brise (cohérence multi-balises) ──
    // Piège classique de rentrée maritime/thermique qui bascule : un
    // retournement de direction isolé sur une seule balise est du bruit
    // (rafale, turbulence locale) — la cohérence sur au moins 2 balises
    // VOISINES (même compte, à moins de FW_BREEZE_NEIGHBOR_RADIUS_KM
    // l'une de l'autre) est le signal recherché. Niveau 2 (vigilance,
    // §7.5 cadrage : "brise qui bascule").
    const fwBreezeActiveScopes = new Set();
    for (const [userId, beacons] of watchedBeaconsByUser) {
      if (beacons.length < 2) continue; // pas de "cohérence" possible à 1 seule balise

      const reversed = beacons.filter(b => {
        // FIA-2 : plancher de vitesse aux DEUX extrémités — si le vent est
        // quasi nul (baseline OU courant), la direction est aléatoire et un
        // retournement de 100°+ ne signifie rien aérologiquement.
        if (b.rel.moy == null || b.rel.moy < FW_BREEZE_REVERSAL_MIN_WIND_KMH) return false;
        const baseline = fwBaselineAt(b.beaconId, b.windowMin);
        if (!baseline || baseline.dir == null) return false;
        if (baseline.moy == null || baseline.moy < FW_BREEZE_REVERSAL_MIN_WIND_KMH) return false;
        const diff = fwAngularDiff(baseline.dir, b.rel.dir);
        return diff !== null && diff >= FW_BREEZE_REVERSAL_MIN_DEG;
      });
      if (reversed.length < 2) continue;

      const clusters = fwClusterByProximity(reversed, FW_BREEZE_NEIGHBOR_RADIUS_KM);
      for (const cluster of clusters) {
        if (cluster.length < 2) continue;
        const anchor = cluster.map(b => b.beaconId).sort()[0];
        const scope = `zone:${anchor}`;
        fwBreezeActiveScopes.add(`${userId}|${scope}`);
        const names = cluster.map(b => b.rel.nom).join(', ');
        const lbl = pushLabels(langByUser.get(userId)).flightwatch.breezeReversal;
        await evaluateFwSignal({
          userId, scope, signal: 'breeze_reversal', level: 2, active: true,
          buildPush: () => ({
            title: lbl.title,
            body: lbl.body(names),
            icon: '/apple-touch-icon.png', badge: '/apple-touch-icon.png',
            tag: `fw-breeze_reversal-${scope}`, requireInteraction: false,
            data: {
              url: '/', kind: 'flightwatch', signal: 'breeze_reversal', level: 2,
              scope, voice: false, // niveau 2 = push doux, voix réservée niveau 3 (§7.5)
              value: null, unit: null,
            },
          }),
        });
      }
    }
    // Réarmement : toute zone `breeze_reversal` active lors d'un poll
    // précédent mais non retrouvée ce poll-ci (le compte n'a pas de bascule
    // à collecter au-dessus, ou le cluster ne s'est pas reformé) est
    // remise à plat — même logique de réarmement silencieux que le reste.
    for (const row of (Array.isArray(fwAlertRows) ? fwAlertRows : [])) {
      if (row.signal !== 'breeze_reversal' || !row.alert_active) continue;
      if (fwBreezeActiveScopes.has(`${row.user_id}|${row.scope}`)) continue;
      await evaluateFwSignal({ userId: row.user_id, scope: row.scope, signal: 'breeze_reversal', level: 2, active: false, buildPush: () => ({}) });
    }

    // ── Lot 4 flightwatch : vigilance Météo-France (évaluation) ────────
    // Contrairement à la brise (clusters recalculés à chaque poll, d'où
    // la passe de réarmement ci-dessus), la carte de vigilance couvre
    // TOUS les départements en un seul appel réussi : on évalue donc
    // CHAQUE paire (compte, département) collectée, active ou pas — le
    // réarmement (passage orange/rouge -> jaune/vert) est déjà couvert
    // nativement par active:false ci-dessous, pas besoin d'une passe
    // séparée. Si fetchVigilanceColors a échoué (pas de token, API MF en
    // panne) : vigilanceColors est null, on n'évalue RIEN ce poll-ci — ni
    // alerte ni reset (§8 garde-fou "informer, pas juger").
    // Rappel niveaux (§7.5 cadrage + précision Lot 4 "push si orange/
    // rouge") : vert/jaune = pas de push (jaune = niveau 1 info passive,
    // Lot 6 UI, hors scope ici) ; orange = niveau 2 (push doux) ; rouge =
    // niveau 3 (push fort + voix si activée).
    if (vigilanceColors) {
      for (const { userId, dept, names } of vigilanceByUserDept.values()) {
        const color = vigilanceColors.get(dept);
        if (color == null) continue; // département absent de la réponse -> pas d'évaluation (défensif)
        const active = color >= 3;
        const level = color >= 4 ? 3 : 2;
        const scope = `dept:${dept}`;
        const namesList = [...names].join(', ');
        const lbl = pushLabels(langByUser.get(userId)).flightwatch.vigilance;
        const prefs = prefsByUser.get(userId) || fwPrefs(null);
        await evaluateFwSignal({
          userId, scope, signal: 'vigilance', level, active,
          buildPush: () => ({
            title: lbl.title(level, dept),
            body: lbl.body(namesList),
            icon: '/apple-touch-icon.png', badge: '/apple-touch-icon.png',
            tag: `fw-vigilance-${scope}`, requireInteraction: level === 3,
            data: {
              url: '/', kind: 'flightwatch', signal: 'vigilance', level,
              scope, voice: level === 3 ? !!prefs.voice_enabled : false,
              value: color, unit: 'color_id',
            },
          }),
        });
      }
    }
  } catch(e) { console.error('pollAndNotify error:', e.message); }
}

app.listen(PORT, () => {
  console.log(`🚀 Balise Watch Push Server — port ${PORT}`);
  pollAndNotify();
  setInterval(pollAndNotify, POLL_MS);
  refreshMeteoFranceData(); // no-op silencieux si METEOFRANCE_API_KEY absente
  setInterval(refreshMeteoFranceData, MF_OBS_POLL_MS);
});
