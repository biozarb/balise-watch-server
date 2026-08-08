const express  = require('express');
const compression = require('compression'); // gzip des réponses (audit charge 24/07 : listes de stations servies en clair = ~55% de la bande passante Render)
const webpush  = require('web-push');
const fetch    = require('node-fetch');
const rateLimit = require('express-rate-limit');
const WebSocket = require('ws'); // Étape 10 Lot 5 : flux foudre Blitzortung (WebSocket temps réel)
const { PNG } = require('pngjs'); // Étape 10 Lot C : décodage des tuiles radar RainViewer (détection précip)

// ── Lot 7 (04/08/2026) — la physique de la pression, partagée ───────
// `lib/pressure.cjs` est GÉNÉRÉ depuis PWA/web/src/lib/pressure.ts : la
// fiche et le serveur exécutent littéralement le même code. Avant, le
// serveur soustrayait deux pressions MSL de modèle et la fiche
// convertissait des relevés de stations en QFF — deux nombres
// différents présentés comme le même. Sur un outil de sécurité, deux
// vérités valent moins qu'une seule.
// Ne jamais éditer lib/pressure.cjs à la main (cf. son en-tête) ;
// contrôle de dérive : node tools/verify-pressure-sync.mjs
const PRESSURE = require('./lib/pressure.cjs');
const { computePhenomenonDelta, OBSERVED_HOURS } = require('./lib/phenomenon-delta');

const PORT         = process.env.PORT || 3000;
// ── Marqueur de build ──────────────────────────────────────────────
// Ajouté le 04/08/2026. `version` est une constante du source : elle ne
// distingue PAS un build déployé du précédent, et le 03/08 comme le
// 04/08 on a cru à un bug de veille alors que le correctif n'était tout
// simplement pas en ligne. Render injecte le SHA du commit déployé dans
// l'environnement — le lire ici rend le déploiement CONSTATABLE depuis
// l'extérieur, au lieu d'être supposé.
// Variables fournies par Render : RENDER_GIT_COMMIT, RENDER_GIT_BRANCH,
// RENDER_INSTANCE_ID (cf. render.com/docs/environment-variables).
// Repli 'inconnu' hors Render (poste local), jamais une valeur fausse.
const GIT_COMMIT   = process.env.RENDER_GIT_COMMIT || null;
const GIT_BRANCH   = process.env.RENDER_GIT_BRANCH || null;
const BOOT_AT      = Date.now();
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
    dirOut: '🧭 Hors zone :', // Débogage 16/07/2026 (demande Yann) — option orientation par balise
    // Lot 5 « Surveiller ce site » : le push groupé par site. Le sous-titre
    // n'est pas décoratif — c'est le garde-fou n°1 (fausse confiance). Un
    // pilote qui reçoit UN push au lieu de trois doit lire noir sur blanc
    // qu'il s'agit de trois balises, sinon il conclut que ça se calme. Et
    // aucune formulation ne doit laisser croire que le site est « couvert ».
    siteWind: {
      title: (site, n) => `⚠️ ${site} — ${n} balise${n > 1 ? 's' : ''} au-dessus du seuil`,
      footer: n => n > 1 ? `${n} balises de ce site dans un seul message.` : '',
    },
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
      precip: {
        body: radiusKm =>
          `Précipitations détectées à moins de ${radiusKm} km de ta balise — donnée radar indicative (RainViewer), non officielle`,
      },
      foehn: {
        title: label => `🌀 Foehn — ${label}`,
        body: (town, signedVal, level, whenStr) =>
          `Foehn attendu ${whenStr} : Δ ${signedVal} hPa, orienté vers ${town}. ` +
          (level === 3 ? 'Assez marqué pour déborder en plaine.' : 'Vent fort et turbulent probable dans les vallées.') +
          ' Danger pour le vol — ne décolle pas en foehn.',
      },
    },
  },
  en: {
    avg: 'Avg.', gust: 'Gust',
    dirOut: '🧭 Out of zone:',
    siteWind: {
      title: (site, n) => `⚠️ ${site} — ${n} beacon${n > 1 ? 's' : ''} above threshold`,
      footer: n => n > 1 ? `${n} beacons at this site in a single message.` : '',
    },
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
      precip: {
        body: radiusKm =>
          `Precipitation detected within ${radiusKm} km of your beacon — indicative radar data (RainViewer), unofficial`,
      },
      foehn: {
        title: label => `🌀 Foehn — ${label}`,
        body: (town, signedVal, level, whenStr) =>
          `Foehn expected ${whenStr}: Δ ${signedVal} hPa, toward ${town}. ` +
          (level === 3 ? 'Strong enough to spill into the plains.' : 'Strong, turbulent wind likely in the valleys.') +
          ' Dangerous for flying — do not take off in foehn.',
      },
    },
  },
};
function pushLabels(lang) { return PUSH_LABELS[lang] || PUSH_LABELS.en; }

// ── Lot 5 « Surveiller ce site » : le nom d'un site, côté serveur ──
// `origin_site` (lot 4) ne porte que la clé `lat|lon` du décollage qui a
// créé la ligne. decos.json vit côté PWA — jusqu'ici le serveur n'avait
// aucun moyen de nommer un site. Décision Yann du 08/08 : « tant qu'à y
// être on embarque decos.json, ça résout le pb de nom ».
//
// On NE COPIE PAS le fichier dans ce dépôt. Deux copies qui divergent, ce
// n'est pas un nom qui manque, c'est un nom FAUX dans un push — pire que
// pas de nom du tout. On lit donc l'UNIQUE exemplaire, celui que la PWA
// publie déjà, et on le garde en RAM (3 313 décollages, ~160 ko) avec un
// rafraîchissement quotidien : une correction dans decos.json se propage
// toute seule, là où un instantané recopié resterait faux.
//
// ⚠️ La clé est dérivée EXACTEMENT comme côté client (`siteKey`,
// web/src/lib/decos.ts : `${lat.toFixed(4)}|${lon.toFixed(4)}`). Un
// arrondi qui divergerait d'un seul chiffre ne lèverait aucune erreur :
// il ne trouverait simplement jamais rien.
//
// Défensif de bout en bout : fetch en panne, JSON illisible, déco déplacé
// par pgEarth → pas de nom, et l'appelant retombe sur les coordonnées.
// JAMAIS un nom approché (pas de nearestDeco avec tolérance ici) — c'est
// la règle du lot 4 : « à défaut on montre les coordonnées plutôt qu'un
// nom inventé ».
const DECOS_URL = process.env.DECOS_URL || 'https://balise-watch.vercel.app/data/decos.json';
const DECOS_TTL_MS = 24 * 60 * 60 * 1000;
let decoNameByKey = null;
let decosFetchedAt = 0;
async function loadDecoNames() {
  if (decoNameByKey && (Date.now() - decosFetchedAt) < DECOS_TTL_MS) return decoNameByKey;
  try {
    const r = await fetch(DECOS_URL, { headers: { 'User-Agent': 'BaliseWatch/1.0 (+https://balise-watch.vercel.app)' } });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const arr = await r.json();
    if (!Array.isArray(arr)) throw new Error('format inattendu');
    const m = new Map();
    // Deco = [lat, lon, name, altM, sectors] — un tuple, aucun identifiant
    // stable (vérifié au lot 4). D'où la clé dérivée des coordonnées.
    for (const d of arr) {
      if (!Array.isArray(d) || typeof d[0] !== 'number' || typeof d[1] !== 'number') continue;
      const nom = typeof d[2] === 'string' ? d[2].trim() : '';
      if (nom) m.set(`${d[0].toFixed(4)}|${d[1].toFixed(4)}`, nom);
    }
    if (m.size === 0) throw new Error('aucun décollage lisible');
    decoNameByKey = m;
    decosFetchedAt = Date.now();
    console.log(`🗺️  decos.json chargé : ${m.size} décollages`);
  } catch (err) {
    console.warn(`⚠️ decos.json indisponible (${err.message}) — les push de site nommeront les coordonnées`);
    // Map vide plutôt que null : évite de re-tenter le fetch à chaque
    // groupe du poll. Le TTL fera la prochaine tentative.
    if (!decoNameByKey) decoNameByKey = new Map();
    decosFetchedAt = Date.now();
  }
  return decoNameByKey;
}
/** Ce qu'on écrit dans un push pour désigner un site : son nom si on
 *  l'a, ses coordonnées sinon. Jamais un nom approché. */
function siteLabelFromKey(key) {
  const nom = decoNameByKey?.get(String(key));
  if (nom) return nom;
  const [a, b] = String(key).split('|');
  const lat = Number(a), lon = Number(b);
  return Number.isFinite(lat) && Number.isFinite(lon)
    ? `${lat.toFixed(3)}, ${lon.toFixed(3)}`
    : String(key);
}

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
  sig_precip:            true, // Lot C : précipitations à proximité (radar RainViewer)
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
const MF_HISTORY_RETENTION_H = 48; // Lot 8 (12/07) : rétention de la table persistante mf_station_history pour les stations AVEC vent — INDÉPENDANTE de FW_HISTORY_MAX_AGE_MS/beaconHistory ci-dessus, qui reste à 3h30 pour la veille météo (flightwatch) uniquement
const MF_MINMAX_WINDOW_MIN = 30; // Débogage 17/07 (retour Yann : enregistrer min/max pour les stations MF) — Météo-France ne publie pas de vitesse minimale par relevé (contrairement à Pioupiou, wind_speed_min) : le max est le raf10 natif (déjà récupéré à chaque poll, juste jamais persisté jusqu'ici), le min est calculé nous-mêmes, glissant sur les échantillons `ff` déjà en RAM (beaconHistory) sur cette fenêtre — un min "maison", pas une mesure native. 30 min choisi comme repère "a-t-il molli récemment", volontairement plus court que FW_TREND_WINDOW_H (3h, pensé pour la pression) — à ajuster si besoin.
const MF_PRESSURE_ONLY_RETENTION_H = 12; // Débogage 12/07/2026 (suite) : rétention DÉDIÉE, plus courte, pour les lignes pression-seule (moy IS NULL) de la même table — décidé avec Yann : 12h suffit à voir l'évolution de la pression (pas de graphe vent à afficher pour ces stations, contrairement aux stations MF avec vent qui gardent 48h), coûte nettement moins cher en stockage Supabase
const FW_PRESSURE_MIN_SAMPLES_SPAN_MIN = 150; // Lot 2b : n'évalue la pression RÉELLE (beaconHistory) qu'avec au moins 2h30 de recul (proche de la fenêtre 3h visée) — sinon repli Open-Meteo, jamais un taux calculé sur un intervalle trop court ou juste après un redémarrage
const FW_PRESSURE_NEARBY_STATION_MAX_KM = 40; // Débogage 12/07/2026 : rayon de recherche d'une station MF PROCHE (pression uniquement, vent ou pas) comme repli intermédiaire avant le modèle — la pression est un champ spatialement lisse (contrairement au vent), une vraie mesure à 40 km reste plus fiable qu'une valeur de grille modèle interpolée
const FW_WIND_MIN_BASELINE_KMH = 3; // évite un facteur "x1.8" absurde quand le vent de référence est quasi nul
const FW_WIND_SURGE_ABS_MIN_KMH = 15; // FIA-1 : plancher absolu sur wind_surge — pas d'alerte niveau 3 si le vent courant reste sous ce seuil (évite les faux positifs "danger imminent" à ~6 km/h les matins calmes thermiques)
const MF_OBS_MAX_AGE_MS = 30 * 60 * 1000; // DATA-1 : garde-fraîcheur MF — une observation dont validityTime dépasse ce seuil est ignorée dans la fusion (évite d'alerter sur des données figées si l'API MF tombe plusieurs heures)
const FW_BREEZE_REVERSAL_MIN_DEG = 100; // retournement net de direction, pas une dérive — pas de colonne dédiée au schéma Lot 0, constante serveur documentée ici
const FW_BREEZE_NEIGHBOR_RADIUS_KM = 20; // "balises voisines" — rayon raisonnable pour la maille de balises Alpes/Maurienne, ajustable à l'usage
const FW_BREEZE_REVERSAL_MIN_WIND_KMH = 5; // FIA-2 : plancher de vitesse sur la bascule de brise — par vent quasi nul la direction d'une girouette est aléatoire, ce qui suffirait à déclencher un retournement fictif de 100°+ entre deux balises calmes au lever/coucher
const WATCH_DIR_MIN_WIND_KMH = 5; // Débogage 16/07/2026 (demande Yann, option orientation par balise) : même garde-fou que FW_BREEZE_REVERSAL_MIN_WIND_KMH — par vent quasi nul la direction n'a pas de sens physique, on n'évalue pas "hors secteur" en dessous de ce seuil (évite un faux "hors zone" au lever du jour, vent calme, direction erratique)
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

// ── Étape 10 (flightwatch), Lot C : précipitations observées (radar) ──
// Alerte "pluie à <= X km d'une balise surveillée", à partir du RADAR
// RainViewer — la MÊME source que le calque radar affiché sur la carte
// côté client (cohérence : ce que le pilote voit = ce qui déclenche).
// Choix d'archi (cf. ETUDE_CONVECTION_SATELLITE.md §6/§11) : l'API MF
// Données Radar renvoie des rasters lourds (GeoTIFF/BUFR) incompatibles
// avec un décodage sur Render free tier ; RainViewer sert des tuiles
// légères, pan-européennes, sans clé → on récupère les quelques tuiles
// z7 couvrant la France, on les décode (petit PNG) et on cherche un écho
// de pluie dans le rayon autour de chaque balise. Tout défensif : index
// KO / tuile KO / kill switch → cache vide → signal non évalué, jamais de
// crash (même politique que la foudre/vigilance).
//
// ⚠️ v1 volontairement simple : gaté par la SEULE variable d'env
// FW_PRECIP_ENABLED (OPT-IN, OFF par défaut en prod, comme la foudre) +
// un rayon global FW_PRECIP_RADIUS_KM. PAS de colonne de prefs par compte
// pour l'instant → aucun changement de schéma Supabase, aucun risque pour
// le select de la veille. Le toggle par utilisateur + rayon perso
// (sig_precip / precip_radius_km) sera un lot ultérieur (SQL d'abord).
// ⚠️ Clause RainViewer : usage "perso/communautaire", pas de SLA,
// attribution requise → donnée présentée comme INDICATIVE (le push le dit),
// comme Blitzortung.
const FW_PRECIP_ENABLED   = process.env.FW_PRECIP_ENABLED === '1';
const FW_PRECIP_RADIUS_KM = Number(process.env.FW_PRECIP_RADIUS_KM) || 20;
const FW_PRECIP_INDEX_URL = 'https://api.rainviewer.com/public/weather-maps.json';
const FW_PRECIP_TILE_Z    = 7;   // zoom MAX des tuiles publiques RainViewer (doc) — au-delà : "Zoom Level Not Supported"
const FW_PRECIP_TILE_SIZE = 256; // 256 ou 512 (doc RainViewer)
const FW_PRECIP_COLOR     = 4;   // schéma couleur (sans effet sur la détection, faite sur l'alpha) ; options "0_1" = non lissé + neige comptée comme précip
const FW_PRECIP_ALPHA_MIN = 40;  // seuil alpha : un pixel réellement peint = écho radar ; ignore le fuzz d'anti-aliasing
const FW_PRECIP_BBOX      = FW_LIGHTNING_BBOX; // même emprise France métropolitaine + marge (Alpes/Corse), réutilisée

let fwPrecipTiles = new Map();  // "x/y" -> PNG décodé {width, height, data (RGBA)}
let fwPrecipFrameTime = 0;      // timestamp de la frame radar actuellement en cache
let fwPrecipRefreshing = false; // garde anti-recouvrement d'appels concurrents

function fwPrecipClear() { if (fwPrecipTiles.size) { fwPrecipTiles = new Map(); fwPrecipFrameTime = 0; } }

// Coordonnées de tuile "slippy map" (standard OSM/Leaflet).
function fwLon2tileX(lon, z) { return Math.floor((lon + 180) / 360 * Math.pow(2, z)); }
function fwLat2tileY(lat, z) { const r = lat * Math.PI / 180; return Math.floor((1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * Math.pow(2, z)); }

// Récupère (au plus une fois par frame) les tuiles radar z7 couvrant la
// France et les décode en RAM. Rien n'est persisté (comme le buffer
// foudre) : un redémarrage vide le cache, re-rempli au poll suivant.
async function fwPrecipRefresh() {
  if (!FW_PRECIP_ENABLED || fwPrecipRefreshing) return;
  fwPrecipRefreshing = true;
  try {
    const res = await fetch(FW_PRECIP_INDEX_URL);
    if (!res.ok) return;
    const idx = await res.json();
    const frames = idx?.radar?.past;
    if (!Array.isArray(frames) || !frames.length || !idx.host) return;
    const frame = frames[frames.length - 1]; // dernière image observée
    if (frame.time === fwPrecipFrameTime && fwPrecipTiles.size) return; // déjà à jour
    const z = FW_PRECIP_TILE_Z, bb = FW_PRECIP_BBOX;
    const x0 = fwLon2tileX(bb.lonMin, z), x1 = fwLon2tileX(bb.lonMax, z);
    const y0 = fwLat2tileY(bb.latMax, z), y1 = fwLat2tileY(bb.latMin, z); // latMax → y le plus petit
    const jobs = [];
    for (let x = x0; x <= x1; x++) {
      for (let y = y0; y <= y1; y++) {
        const url = `${idx.host}${frame.path}/${FW_PRECIP_TILE_SIZE}/${z}/${x}/${y}/${FW_PRECIP_COLOR}/0_1.png`;
        jobs.push(
          fetch(url)
            .then(r => (r.ok ? r.buffer() : null))
            .then(buf => (buf ? [`${x}/${y}`, PNG.sync.read(buf)] : null))
            .catch(() => null) // tuile en échec ignorée, jamais de crash
        );
      }
    }
    const results = await Promise.all(jobs);
    const next = new Map();
    for (const r of results) if (r) next.set(r[0], r[1]);
    if (next.size) { fwPrecipTiles = next; fwPrecipFrameTime = frame.time; }
  } catch { /* dégradation silencieuse : cache inchangé, signal non évalué */ }
  finally { fwPrecipRefreshing = false; }
}

// Y a-t-il un écho de pluie à <= radiusKm du point, et si oui à quelle
// distance (km) se trouve le plus proche ? Balayage d'un disque en espace
// pixel (z7) sur les tuiles décodées : alpha > seuil = pixel réellement
// peint par le radar = précipitation. Cache vide → { near: false,
// distanceKm: null } (jamais de fausse alerte, cf. §8 garde-fou "informer,
// pas juger"). Débogage 13/07/2026 (nice-to-have "valeur chiffrée
// dashboard") — cherchait jusqu'ici juste un booléen (return au 1er hit,
// peu importe lequel) ; parcourt maintenant TOUT le disque pour garder le
// pixel peint le plus proche du centre, afin d'exposer une distance réelle
// à l'affichage (cf. precipSignalCache) plutôt que le seul rayon configuré.
// Débogage 17/07/2026 (Lot 3 plan de coupe — retour Yann "distance réelle
// (km)" à la précipitation) — cœur du balayage disque extrait en fonction
// pure paramétrée par la Map de tuiles décodées, pour être réutilisé par
// DEUX caches indépendants : fwPrecipTiles (flightwatch, balises
// surveillées, cf. ci-dessus) ET cutPrecipTiles (plan de coupe, point
// libre quelconque, cf. plus bas) — même algorithme, même source radar,
// juste un cache RAM différent selon l'appelant. Comportement de
// fwPrecipNear strictement inchangé (délègue tel quel).
function precipNearestInTiles(tiles, lat, lon, radiusKm) {
  if (!tiles.size || lat == null || lon == null) return { near: false, distanceKm: null, dxPx: null, dyPx: null, geom: null };
  const z = FW_PRECIP_TILE_Z, size = FW_PRECIP_TILE_SIZE;
  const world = Math.pow(2, z) * size; // largeur du monde en pixels à ce zoom
  const gx = (lon + 180) / 360 * world;
  const r = lat * Math.PI / 180;
  const gy = (1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * world;
  const mPerPx = 156543.03 * Math.cos(r) / Math.pow(2, z) * (256 / size); // résolution sol (m/px) au point
  const rp = Math.max(1, Math.ceil((radiusKm * 1000) / mPerPx));
  const rp2 = rp * rp;
  let bestPx2 = Infinity, bestDx = 0, bestDy = 0;
  for (let dy = -rp; dy <= rp; dy++) {
    for (let dx = -rp; dx <= rp; dx++) {
      const d2 = dx * dx + dy * dy;
      if (d2 > rp2 || d2 >= bestPx2) continue; // disque, pas carré ; élague si déjà moins bon que le meilleur trouvé
      if (!precipEchoAt(tiles, Math.floor(gx + dx), Math.floor(gy + dy))) continue;
      bestPx2 = d2; bestDx = dx; bestDy = dy;
    }
  }
  // Débogage 30/07/2026 (suivi de cellule, cf. precipTrackInTiles) — le
  // décalage pixel du meilleur écho ET le repère pixel du point sont
  // renvoyés EN PLUS des deux champs d'origine. Purement additif :
  // `fwPrecipNear` (alertes flightwatch) déstructure `{ near, distanceKm }`
  // et ignore le reste, comportement strictement inchangé.
  const geom = { gx, gy, mPerPx };
  if (bestPx2 === Infinity) return { near: false, distanceKm: null, dxPx: null, dyPx: null, geom };
  return {
    near: true,
    distanceKm: Math.round((Math.sqrt(bestPx2) * mPerPx) / 100) / 10,
    dxPx: bestDx, dyPx: bestDy, geom,
  };
}

/** Y a-t-il un écho radar au pixel monde (px, py) ? Accès unifié aux DEUX
 *  formes de tuile manipulées ici : le PNG décodé par `pngjs` (RGBA, cache
 *  de la frame courante — on teste l'alpha, cf. FW_PRECIP_ALPHA_MIN) et le
 *  masque binaire compact d'une frame précédente (`Uint8Array`, 1 octet par
 *  pixel, cf. precipMaskTiles) — 4x moins de RAM, ce qui compte sur le plan
 *  gratuit Render puisqu'on garde désormais DEUX frames en mémoire. */
function precipEchoAt(tiles, px, py) {
  const size = FW_PRECIP_TILE_SIZE;
  const tx = Math.floor(px / size), ty = Math.floor(py / size);
  const tile = tiles.get(`${tx}/${ty}`);
  if (!tile) return false;
  const lx = px - tx * size, ly = py - ty * size;
  if (lx < 0 || ly < 0 || lx >= tile.width || ly >= tile.height) return false;
  const i = ly * tile.width + lx;
  return tile.mask ? tile.mask[i] === 1 : tile.data[i * 4 + 3] > FW_PRECIP_ALPHA_MIN;
}

/** PNG décodés -> masques binaires (1 octet/pixel). Appliqué à la frame
 *  qui SORT du cache courant pour devenir la frame précédente : on n'a
 *  plus besoin des couleurs à ce stade, seulement de « écho ou pas ».
 *  9 Mo de RGBA (36 tuiles France à z7) -> 2,25 Mo. */
function precipMaskTiles(tiles) {
  const out = new Map();
  for (const [k, t] of tiles) {
    const mask = new Uint8Array(t.width * t.height);
    for (let i = 0; i < mask.length; i++) mask[i] = t.data[i * 4 + 3] > FW_PRECIP_ALPHA_MIN ? 1 : 0;
    out.set(k, { width: t.width, height: t.height, mask });
  }
  return out;
}
function fwPrecipNear(lat, lon, radiusKm) {
  return precipNearestInTiles(fwPrecipTiles, lat, lon, radiusKm);
}

// ── Lot 3 plan de coupe (17/07/2026) — distance réelle à la pluie ────
// Second cache de tuiles radar, INDÉPENDANT de fwPrecipTiles ci-dessus :
// celui-ci sert un affichage À LA DEMANDE (plan de coupe, point libre
// quelconque cliqué sur la carte), PAS une alerte flightwatch — donc PAS
// gaté par FW_PRECIP_ENABLED (feature à part, opt-in réservé au
// push/bêta) ni par watchedRows.length > 0 (un point libre n'est pas
// forcément une balise surveillée). Rafraîchi paresseusement (1er appel
// après CUT_PRECIP_MAX_AGE_MS écoulé), jamais par le poll 5 min.
// `cutPrecipLastAttempt` (horloge murale, PAS le timestamp de la frame
// RainViewer) borne la fréquence de re-fetch même en cas d'échec répété,
// pour ne jamais marteler RainViewer si plusieurs plans de coupe
// s'ouvrent dans la même minute.
let cutPrecipTiles = new Map();
let cutPrecipFrameTime = 0;      // timestamp (s, epoch RainViewer) de la frame en cache
let cutPrecipLastAttempt = 0;    // horloge murale (ms) de la dernière TENTATIVE de refresh
let cutPrecipRefreshing = false;
const CUT_PRECIP_MAX_AGE_MS = 3 * 60 * 1000; // marge confortable sous la cadence de renouvellement RainViewer (~10 min)

// ── Suivi de cellule (30/07/2026, retour Yann : « on pourrait avoir la
// direction et la probabilité qu'il nous atteigne ? ») ────────────────
// Frame PRÉCÉDENTE, gardée en masque binaire (cf. precipMaskTiles) pour
// comparer deux images successives et en déduire le déplacement réel des
// échos. Point clé d'archi : ce n'est PAS un téléchargement de plus. Les
// frames RainViewer se renouvellent toutes les ~10 min alors qu'on
// rafraîchit au plus toutes les 3 min : quand une nouvelle frame arrive,
// celle qui sort du cache EST la frame précédente. On la convertit en
// masque au lieu de la jeter. Zéro requête réseau supplémentaire en
// régime établi, +2,25 Mo de RAM (contre +9 Mo si on gardait le RGBA).
// ⚠️ TROIS frames, pas deux (débogage 30/07/2026, cf. plus bas) : le
// verdict n'est publié que si le vecteur mesuré sur (N-2 -> N-1) confirme
// celui mesuré sur (N-1 -> N). Sans ce recoupement, la corrélation sur une
// seule paire ne bat "rien ne bouge" que 45 % du temps — mesuré, pas
// supposé.
let cutPrecipPrevTiles = new Map();
let cutPrecipPrevFrameTime = 0;
let cutPrecipPrev2Tiles = new Map();
let cutPrecipPrev2FrameTime = 0;
// Au-delà, les deux frames sont trop éloignées pour qu'un écho soit
// encore « le même » : serveur redémarré, longue inactivité (le plan
// gratuit Render endort l'instance), trou côté RainViewer. On préfère ne
// rien affirmer plutôt qu'extrapoler sur un intervalle inconnu.
const CUT_PRECIP_TRACK_MAX_DT_MS = 30 * 60 * 1000;
// Demi-fenêtre de corrélation (px). 40 px = 81x81, ~70 km de côté.
// ⚠️ Était à 15 px : une fenêtre à peine plus grande que l'amplitude de
// recherche compare, aux grands décalages, deux zones qui n'ont presque
// plus rien en commun -> appariements fantaisistes (vitesses mesurées à
// 120-170 km/h pour un flux directeur à 20 km/h). La fenêtre doit rester
// nettement plus large que le décalage cherché.
const CUT_PRECIP_TRACK_WIN_PX = 40;
// Amplitude de recherche du décalage (px). 20 px sur 10 min ≈ 104 km/h,
// ce qui couvre le domaine physique réel des déplacements de cellules.
const CUT_PRECIP_TRACK_SEARCH_PX = 20;
// Sous ce nombre de pixels d'écho dans la fenêtre, l'échantillon est trop
// maigre pour que la corrélation veuille dire quoi que ce soit.
const CUT_PRECIP_TRACK_MIN_HITS = 30;
// Indice de Jaccard minimal (intersection / union) entre la fenêtre et la
// frame précédente décalée. ⚠️ Le score était auparavant un simple TAUX DE
// RECOUVREMENT (fraction des pixels d'écho de la fenêtre retombant sur de
// l'écho) : il saturait à 100 % dès que la fenêtre glissait vers
// l'INTÉRIEUR du champ de pluie, sans jamais pénaliser une zone d'arrivée
// bien plus vaste que la fenêtre. Jaccard pénalise ce cas (l'union
// gonfle), ce qui est exactement ce qui manquait.
const CUT_PRECIP_TRACK_MIN_SCORE = 0.45;
// Écart maximal toléré entre le vecteur de la paire précédente et celui de
// la paire courante, pour publier un verdict : 3 px, ou la moitié du
// déplacement courant si celui-ci est plus grand (une cellule rapide a le
// droit de varier un peu plus en valeur absolue).
const CUT_PRECIP_TRACK_AGREE_PX = 3;
// Le suivi coûte ~40 ms de CPU par point (deux corrélations 41x41 décalages
// sur une fenêtre 81x81). Node étant mono-thread, plusieurs plans de coupe
// ouverts en même temps se bloqueraient mutuellement. Mémo par frame et par
// point arrondi à ~100 m : le client resonde toutes les 5 min alors qu'une
// frame vit ~10 min, donc au moins un sondage sur deux est servi du cache.
// Vidé à chaque rotation de frame — pas d'éviction à écrire.
let cutPrecipTrackMemo = new Map();
// 1 px sur 10 min ≈ 5,2 km/h : la quantification pixel À ELLE SEULE peut
// produire un déplacement apparent. On ne parle de mouvement qu'au-delà
// de ~1,5 px, sinon c'est « stationnaire » (ce qui n'est PAS rassurant
// pour autant, cf. la note sur la régénération sur place).
const CUT_PRECIP_STATIONARY_KMH = 8;
// Distance de passage au plus près (CPA) au-delà de laquelle on accepte
// d'écrire « passe à côté ». Calée sur l'incertitude propre de la méthode :
// ±15° d'erreur d'angle à 20 km de distance, c'est déjà ±5 km d'écart
// latéral. En dessous de ce seuil on reste sur « se rapproche » — en cas
// de doute on penche vers l'alerte, jamais vers le rassurant.
const CUT_PRECIP_CPA_CLEAR_KM = 10;

/**
 * Déplacement de l'écho le plus proche, par corrélation de la frame
 * courante avec la précédente (méthode classique de suivi radar, dite
 * TREC, réduite à une seule fenêtre — on ne cherche pas un champ de
 * vecteurs sur toute la France, seulement le déplacement de LA cellule
 * qui nous concerne).
 *
 * Choix assumé : on suit une TRANSLATION, pas une croissance. Une cellule
 * qui grossit vers nous sans que son centre bouge sortira « stationary »
 * — mot volontairement neutre, jamais présenté comme un feu vert.
 *
 * Repère : x vers l'est, y vers le SUD (convention pixel Mercator), d'où
 * le `-vy` dans les caps.
 *
 * @returns null si aucun verdict fiable, sinon
 *  { trend, moveDirDeg, moveSpeedKmh, etaMin, cpaKm }
 */
function precipPatch(tiles, cx, cy, R) {
  const w = 2 * R + 1, a = new Uint8Array(w * w);
  for (let dy = -R; dy <= R; dy++) {
    for (let dx = -R; dx <= R; dx++) {
      a[(dy + R) * w + (dx + R)] = precipEchoAt(tiles, cx + dx, cy + dy) ? 1 : 0;
    }
  }
  return a;
}

/** Indice de Jaccard entre la fenêtre `cur` (demi-taille W) et la fenêtre
 *  `prev` (demi-taille P >= W) décalée de (sx, sy). Intersection / union :
 *  contrairement à un simple taux de recouvrement, un décalage qui amène la
 *  fenêtre sur une zone bien plus pluvieuse est pénalisé (l'union gonfle).
 *  C'est LE point qui manquait à la première version. */
function precipJaccard(cur, W, prev, P, sx, sy) {
  const wc = 2 * W + 1, wp = 2 * P + 1;
  let inter = 0, uni = 0;
  for (let dy = -W; dy <= W; dy++) {
    for (let dx = -W; dx <= W; dx++) {
      const a = cur[(dy + W) * wc + (dx + W)];
      const px = dx - sx + P, py = dy - sy + P;
      const b = (px < 0 || py < 0 || px >= wp || py >= wp) ? 0 : prev[py * wp + px];
      if (a & b) inter++;
      if (a | b) uni++;
    }
  }
  return uni ? inter / uni : 0;
}

/** Meilleur décalage (px) de la fenêtre centrée (ex, ey) entre `prev` et
 *  `cur`, au sens de Jaccard. `null` si le score est trop faible ou si le
 *  maximum tombe SUR la borne de recherche (signe qu'on n'a pas trouvé de
 *  vrai maximum, juste le bord du domaine exploré). */
function precipBestShift(cur, prev, ex, ey) {
  const W = CUT_PRECIP_TRACK_WIN_PX, S = CUT_PRECIP_TRACK_SEARCH_PX;
  const pc = precipPatch(cur, ex, ey, W), pp = precipPatch(prev, ex, ey, W + S);
  let best = -1, bx = 0, by = 0;
  for (let sy = -S; sy <= S; sy++) {
    for (let sx = -S; sx <= S; sx++) {
      const j = precipJaccard(pc, W, pp, W + S, sx, sy);
      // À score égal on garde le décalage le PLUS PETIT : sans ce
      // départage, un champ de pluie étendu et uniforme sortirait un
      // vecteur arbitraire pris dans l'ordre de balayage.
      if (j > best || (j === best && sx * sx + sy * sy < bx * bx + by * by)) { best = j; bx = sx; by = sy; }
    }
  }
  if (best < CUT_PRECIP_TRACK_MIN_SCORE) return null;
  if (Math.abs(bx) === S || Math.abs(by) === S) return null;
  return { vx: bx, vy: by, score: best };
}

function precipTrackInTiles(cur, prev, prev2, near, dtSec, dtSec2) {
  if (!cur.size || !prev.size || !near?.near || !near.geom || !(dtSec > 0)) return null;
  // Pluie SUR le point : ni cap ni point de passage au plus près ne sont
  // définissables (le vecteur nous->écho est nul). On ne dit rien plutôt
  // que de renvoyer un « s'éloigne » qui n'est qu'un artefact du produit
  // scalaire nul.
  if (near.dxPx === 0 && near.dyPx === 0) return null;
  const { gx, gy, mPerPx } = near.geom;
  const W = CUT_PRECIP_TRACK_WIN_PX;
  const nx = Math.floor(gx + near.dxPx), ny = Math.floor(gy + near.dyPx);
  // ⚠️ Centre de la fenêtre = CENTROÏDE des échos autour du pixel le plus
  // proche, pas ce pixel lui-même. Le plus proche est par construction sur
  // le BORD du champ de pluie, celui qui nous fait face : une fenêtre
  // centrée là est à moitié vide, et l'appariement dérive alors
  // systématiquement vers l'intérieur du champ — c'est-à-dire toujours
  // dans le même sens par rapport à nous. C'était la cause du verdict
  // inversé signalé le 30/07.
  let sx = 0, sy = 0, n = 0;
  for (let dy = -W; dy <= W; dy++) {
    for (let dx = -W; dx <= W; dx++) {
      if (precipEchoAt(cur, nx + dx, ny + dy)) { sx += dx; sy += dy; n++; }
    }
  }
  if (n < CUT_PRECIP_TRACK_MIN_HITS) return null;
  const ex = nx + Math.round(sx / n), ey = ny + Math.round(sy / n);

  const m = precipBestShift(cur, prev, ex, ey);
  if (!m) return null;
  // Recoupement temporel : le même vecteur doit ressortir de la paire
  // précédente. Une corrélation isolée ne bat "rien ne bouge" que 45 % du
  // temps ; filtrée par ce recoupement, 64 % (mesuré sur 4 frames réelles,
  // cf. le commentaire d'en-tête). Sans deuxième paire disponible
  // (démarrage, trou de frame), pas de verdict — on n'affirme rien.
  if (!prev2.size || !(dtSec2 > 0)) return null;
  const m0 = precipBestShift(prev, prev2, ex, ey);
  if (!m0) return null;
  // Vecteurs ramenés à la même durée avant comparaison (les frames
  // RainViewer sont régulières, mais un trou ne doit pas passer pour une
  // accélération).
  const k = dtSec / dtSec2;
  const dvx = m.vx - m0.vx * k, dvy = m.vy - m0.vy * k;
  const speedPx = Math.hypot(m.vx, m.vy);
  if (Math.hypot(dvx, dvy) > Math.max(CUT_PRECIP_TRACK_AGREE_PX, 0.5 * speedPx)) return null;

  const kmh = (speedPx * mPerPx / dtSec) * 3.6;
  const moveDirDeg = speedPx > 0 ? (Math.atan2(m.vx, -m.vy) * 180 / Math.PI + 360) % 360 : null;
  if (kmh < CUT_PRECIP_STATIONARY_KMH) {
    return { trend: 'stationary', moveDirDeg, moveSpeedKmh: Math.round(kmh), etaMin: null, cpaKm: null };
  }
  // Point de passage au plus près : d = vecteur (nous -> écho),
  // v = vitesse de l'écho. d·v >= 0 => il s'éloigne déjà.
  const dx = near.dxPx, dy = near.dyPx;
  const vx = m.vx / dtSec, vy = m.vy / dtSec; // px/s
  const dot = dx * vx + dy * vy;
  if (dot >= 0) {
    return { trend: 'away', moveDirDeg, moveSpeedKmh: Math.round(kmh), etaMin: null, cpaKm: null };
  }
  const tCpa = -dot / (vx * vx + vy * vy); // secondes
  const cpaKm = Math.hypot(dx + vx * tCpa, dy + vy * tCpa) * mPerPx / 1000;
  // Plancher à 1 min : un arrondi à 0 afficherait « dans ~0 min », ce qui
  // se lit comme une absence de donnée alors que ça veut dire l'inverse.
  const etaMin = Math.max(1, Math.round(tCpa / 60));
  return {
    trend: cpaKm > CUT_PRECIP_CPA_CLEAR_KM ? 'aside' : 'approaching',
    moveDirDeg,
    moveSpeedKmh: Math.round(kmh),
    etaMin,
    cpaKm: Math.round(cpaKm * 10) / 10,
  };
}

async function cutPrecipRefresh() {
  if (cutPrecipRefreshing) return;
  cutPrecipRefreshing = true;
  cutPrecipLastAttempt = Date.now();
  try {
    const res = await fetch(FW_PRECIP_INDEX_URL);
    if (!res.ok) return;
    const idx = await res.json();
    const frames = idx?.radar?.past;
    if (!Array.isArray(frames) || !frames.length || !idx.host) return;
    const frame = frames[frames.length - 1]; // dernière image observée
    if (frame.time === cutPrecipFrameTime && cutPrecipTiles.size) return; // déjà à jour
    const next = await cutPrecipFetchFrame(idx, frame);
    if (!next.size) return;
    // Rotation des frames (30/07/2026, suivi de cellule). En régime
    // établi la frame qui sort devient la précédente — gratuit. Au
    // DÉMARRAGE À FROID en revanche il n'y a rien à faire tourner : on
    // télécharge alors explicitement l'avant-dernière frame, une seule
    // fois, pour ne pas laisser le suivi muet pendant les ~10 min qu'il
    // faudrait sinon attendre qu'une frame se renouvelle. Échec de ce
    // rattrapage = pas de frame précédente = pas de verdict, jamais une
    // erreur (le reste de la route continue de répondre).
    if (cutPrecipTiles.size && cutPrecipFrameTime) {
      cutPrecipPrev2Tiles = cutPrecipPrevTiles;
      cutPrecipPrev2FrameTime = cutPrecipPrevFrameTime;
      cutPrecipPrevTiles = precipMaskTiles(cutPrecipTiles);
      cutPrecipPrevFrameTime = cutPrecipFrameTime;
    } else if (frames.length >= 3) {
      // Deux frames de rattrapage : le verdict exige DEUX paires
      // concordantes (cf. precipTrackInTiles), donc trois images.
      for (const [offset, assign] of [[2, 'prev'], [3, 'prev2']]) {
        const f = frames[frames.length - offset];
        const tiles = await cutPrecipFetchFrame(idx, f);
        if (!tiles.size) continue;
        if (assign === 'prev') { cutPrecipPrevTiles = precipMaskTiles(tiles); cutPrecipPrevFrameTime = f.time; }
        else { cutPrecipPrev2Tiles = precipMaskTiles(tiles); cutPrecipPrev2FrameTime = f.time; }
      }
    }
    cutPrecipTiles = next;
    cutPrecipFrameTime = frame.time;
    cutPrecipTrackMemo = new Map(); // les verdicts mémoïsés portent sur l'ancienne frame
  } catch { /* dégradation silencieuse : cache inchangé, route renvoie near:false */ }
  finally { cutPrecipRefreshing = false; }
}

/** Télécharge et décode les tuiles France d'UNE frame RainViewer.
 *  Extrait de `cutPrecipRefresh` (30/07/2026) pour être appelé deux fois :
 *  frame courante, et frame précédente au démarrage à froid. */
async function cutPrecipFetchFrame(idx, frame) {
  const z = FW_PRECIP_TILE_Z, bb = FW_PRECIP_BBOX;
  const x0 = fwLon2tileX(bb.lonMin, z), x1 = fwLon2tileX(bb.lonMax, z);
  const y0 = fwLat2tileY(bb.latMax, z), y1 = fwLat2tileY(bb.latMin, z);
  const jobs = [];
  for (let x = x0; x <= x1; x++) {
    for (let y = y0; y <= y1; y++) {
      const url = `${idx.host}${frame.path}/${FW_PRECIP_TILE_SIZE}/${z}/${x}/${y}/${FW_PRECIP_COLOR}/0_1.png`;
      jobs.push(
        fetch(url)
          .then(r => (r.ok ? r.buffer() : null))
          .then(buf => (buf ? [`${x}/${y}`, PNG.sync.read(buf)] : null))
          .catch(() => null) // tuile en échec ignorée, jamais de crash
      );
    }
  }
  const results = await Promise.all(jobs);
  const out = new Map();
  for (const r of results) if (r) out.set(r[0], r[1]);
  return out;
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

// Débogage 13/07/2026 (nice-to-have "valeur chiffrée dashboard") — même
// principe que pressureSignalCache ci-dessus, pour les deux signaux qui
// n'affichaient jusqu'ici qu'un OK/détecté sans nombre : précipitations
// (distance en km au plus proche écho radar détecté, cf. fwPrecipNear
// plus haut, désormais renvoyé en plus du booléen) et bascule de brise
// (angle de retournement en degrés, cf. bloc d'évaluation plus bas).
// beacon_id (string) -> { detected: boolean, distanceKm|angleDeg: number|null, updatedAt }.
const precipSignalCache = new Map();
const breezeSignalCache = new Map();
const convectionSignalCache = new Map();

function fwRecordHistory(beaconId, sample) {
  const arr = beaconHistory.get(beaconId) || [];
  arr.push(sample);
  const cutoff = Date.now() - FW_HISTORY_MAX_AGE_MS;
  while (arr.length && arr[0].t < cutoff) arr.shift();
  beaconHistory.set(beaconId, arr);
}

// Débogage 17/07 (retour Yann : min/max pour les stations MF) — minimum
// glissant de `ff` (vitesse moyenne) sur `windowMin` minutes, calculé à
// partir du buffer RAM `beaconHistory` DÉJÀ accumulé pour ce beaconId
// (lu AVANT que le nouvel échantillon n'y soit poussé par fwRecordHistory,
// donc à appeler avant ce dernier). `newFf` (l'échantillon du poll en
// cours) est inclus dans le calcul. Retourne null si newFf est null (pas
// de vent mesuré) — jamais une fausse valeur 0.
function fwWindowMinFf(beaconId, newFf, windowMin = MF_MINMAX_WINDOW_MIN) {
  if (newFf == null) return null;
  const arr = beaconHistory.get(beaconId) || [];
  const cutoff = Date.now() - windowMin * 60 * 1000;
  let min = newFf;
  for (const s of arr) {
    if (s.t < cutoff || s.moy == null) continue;
    if (s.moy < min) min = s.moy;
  }
  return min;
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
// d'historique qu'un poll d'alertes entier). Purge regroupée ici plutôt
// que dans un cron séparé : un DELETE indexé sur `t` à chaque poll est
// trivial pour Postgres, pas besoin de pg_cron.
//
// Débogage 12/07/2026 (suite) — purge DIFFÉRENCIÉE : les lignes vent
// (moy non NULL) gardent 48h (MF_HISTORY_RETENTION_H, pensé pour un
// futur toggle 24h/48h sur les graphes) ; les lignes pression-seule
// (moy NULL — stations sans anémomètre, cf. refreshMfObs) n'en gardent
// que 12h (MF_PRESSURE_ONLY_RETENTION_H, décidé avec Yann : suffisant
// pour voir l'évolution de la pression, nettement moins coûteux en
// stockage). `moy` sert de discriminant, jamais renseigné autrement que
// null|number selon le type d'échantillon. Fonction réutilisée par les
// DEUX call sites (pollAndNotify pour le vent, refreshMfObs pour la
// pression seule) — chaque appel purge la table ENTIÈRE par âge, pas
// seulement les lignes du batch en cours (comme avant ce lot).
function mfPersistHistory(rows) {
  if (!rows.length) return;
  sbUpsert('mf_station_history', rows, 'station_id,t')
    .catch(e => console.error('mfPersistHistory upsert error:', e.message));
  const windCutoff = Date.now() - MF_HISTORY_RETENTION_H * 3600 * 1000;
  sbDelete('mf_station_history', `moy=not.is.null&t=lt.${windCutoff}`)
    .catch(e => console.error('mfPersistHistory purge (vent) error:', e.message));
  const pressureOnlyCutoff = Date.now() - MF_PRESSURE_ONLY_RETENTION_H * 3600 * 1000;
  sbDelete('mf_station_history', `moy=is.null&t=lt.${pressureOnlyCutoff}`)
    .catch(e => console.error('mfPersistHistory purge (pression seule) error:', e.message));
}
// Débogage 12/07/2026 (suite 5, retour Yann) — hydrate le buffer RAM
// beaconHistory depuis la table PERSISTANTE mf_station_history au
// démarrage du process. Sans ça, la persistance 12h/48h construite au
// Lot 8 ne servait QUE le graphe client (GET /meteofrance-history/:id) —
// fwBaselineAt/fwRealPressureTrend (qui décident le repli "station MF
// proche" pour pressure_drop) ne lisaient QUE le RAM, vidé à chaque
// redémarrage Render (veille free tier) : une station MF proche déjà
// connue devait réaccumuler FW_PRESSURE_MIN_SAMPLES_SPAN_MIN (2h30)
// avant de pouvoir resservir, alors que la donnée existait déjà en base.
// Bénéfice secondaire : mf_station_history contient aussi les stations
// MF AVEC vent (moy non NULL, Lot 8) — cette hydratation redonne donc
// aussi tout de suite un historique wind_surge/breeze_reversal aux
// stations MF surveillées après un redémarrage, pas seulement la
// pression. Ne couvre PAS le baromètre propre d'une balise Pioupiou
// (aucune table persistante équivalente pour ça) — ce cas reste
// RAM-only comme avant, réaccumulation nécessaire après un redémarrage.
// Fenêtre bornée à FW_HISTORY_MAX_AGE_MS (3h30) — inutile de charger plus
// que ce que fwBaselineAt ira jamais lire. Défensif : une erreur ici
// (Supabase indisponible, etc.) ne doit jamais empêcher le serveur de
// démarrer — au pire, repli sur la réaccumulation RAM habituelle.
async function hydrateBeaconHistoryFromSupabase() {
  try {
    const cutoff = Date.now() - FW_HISTORY_MAX_AGE_MS;
    const rows = await sbGet(
      'mf_station_history',
      `t=gte.${cutoff}&select=station_id,t,moy,raf,min,dir,pressure&order=t.asc&limit=200000`
    );
    if (!Array.isArray(rows) || !rows.length) return;
    const stationIds = new Set();
    for (const r of rows) {
      fwRecordHistory(String(r.station_id), { t: r.t, moy: r.moy, raf: r.raf ?? null, min: r.min ?? null, dir: r.dir, pressure: r.pressure });
      stationIds.add(r.station_id);
    }
    console.log(`🔄 beaconHistory hydraté depuis mf_station_history : ${rows.length} échantillons, ${stationIds.size} stations`);
  } catch (e) {
    console.error('hydrateBeaconHistoryFromSupabase error:', e.message);
  }
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
// Débogage 16/07/2026 (demande Yann, option orientation par balise) —
// direction (degrés météo) -> secteur le plus proche parmi 8 (0/45/…/315).
// MIROIR EXACT de degToSector8 (client, src/lib/utils.ts) : les deux
// bouts doivent s'accorder sur le même découpage, sinon l'affichage
// (WatchCard, secteur courant surligné) et l'évaluation serveur
// (déclenchement du push) pourraient diverger sur une direction proche
// d'une frontière de secteur (ex. 22°, à la limite N/NE).
function watchDirToSector8(deg) {
  const idx = ((Math.round(deg / 45) % 8) + 8) % 8;
  return idx * 45;
}
// Même notation française que côté client (SECTOR_8_LABELS, src/lib/utils.ts).
const WATCH_SECTOR_8_LABELS = { 0: 'N', 45: 'NE', 90: 'E', 135: 'SE', 180: 'S', 225: 'SO', 270: 'O', 315: 'NO' };
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
// Débogage 19/07/2026 — cache RAM sur les signaux Open-Meteo de la veille.
// AVANT : `fetchOpenMeteoSignals` était rappelé pour CHAQUE balise distincte
// surveillée à CHAQUE poll (5 min), SANS cache -> nb_balises × 288 appels/j
// sur l'IP Render partagée, ce qui saturait le quota gratuit Open-Meteo
// (10 000/j) et faisait échouer en 429 tout le reste (calque vent /wind-grid,
// et silencieusement la veille elle-même). Un TTL de 20 min ramène ça à
// nb_balises × 72 appels/j (÷4) : la pression/convection évoluent à l'heure,
// pas aux 5 min — 20 min de fraîcheur n'a aucun effet sur des dérivées
// calculées sur FW_TREND_WINDOW_H heures. Clé = coordonnées arrondies (une
// balise = une position fixe). Pas d'éviction : borné par le nombre de
// balises distinctes surveillées (même logique que beaconDepartmentCache).
const fwSignalsCache = new Map(); // `lat,lon` -> { ts, data }
const FW_SIGNALS_TTL_MS = 20 * 60 * 1000;
async function fetchOpenMeteoSignals(lat, lon) {
  const key = `${lat.toFixed(3)},${lon.toFixed(3)}`;
  const cached = fwSignalsCache.get(key);
  if (cached && Date.now() - cached.ts < FW_SIGNALS_TTL_MS) return cached.data;
  // Miss/périmé : un seul appel réseau, mis en cache uniquement si succès —
  // un échec (429, réseau…) renvoie null SANS écraser le cache : la
  // sémantique d'abstention de l'appelant reste strictement inchangée.
  const data = await fetchOpenMeteoSignalsNet(lat, lon);
  if (data) fwSignalsCache.set(key, { ts: Date.now(), data });
  return data;
}
async function fetchOpenMeteoSignalsNet(lat, lon) {
  try {
    const url = `${OPEN_METEO_URL}?latitude=${lat}&longitude=${lon}` +
      `&hourly=pressure_msl,cape,cloud_cover_low,cloud_cover_mid,cloud_cover_high,freezing_level_height` +
      `&past_days=1&forecast_days=1&models=meteofrance_seamless&timezone=UTC`;
    const r = await fetch(url);
    if (!r.ok) {
      // Log ajouté 19/07 — cet échec était totalement muet jusqu'ici, si
      // bien qu'un 429 dégradait la veille sans laisser aucune trace (même
      // symptôme que celui rendu visible côté /wind-grid).
      console.error(`fetchOpenMeteoSignals ${lat},${lon}: HTTP ${r.status}`);
      return null;
    }
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
        // Étape 28 (front de rafales) : la température était déjà dans le
        // paquet mais jamais lue. Elle sert de signal BONUS au score de
        // passage (une chute de 3-8 °C accompagne un outflow) — jamais
        // seule, car par air sec elle peut être faible alors que le front
        // est bien réel. Kelvin → °C ici, avec les autres conversions :
        // le §10 de la spec insiste pour que les unités SI de
        // Météo-France soient converties EN UN SEUL ENDROIT.
        temp: s.t != null ? s.t - 273.15 : null,
        validityTime: s.validity_time ?? null,
      });
    }
    if (next.size) {
      mfObsCache = next;
      mfObsCacheFetchedAt = Date.now();
      // Débogage 12/07/2026 — historique de pression pour les stations MF
      // qui n'ont PAS de vent (obs.ff == null) : les stations AVEC vent
      // sont déjà enregistrées, avec moy/dir/pressure complets, par la
      // boucle releves de pollAndNotify (5 min) — les réenregistrer ici
      // aurait mélangé dans le même buffer deux formes d'échantillons
      // (avec et sans moy/dir) à deux cadences différentes (6 min ici vs
      // 5 min là-bas), doublant inutilement la mémoire pour ces stations
      // sans rien apporter. Les stations SANS vent, elles, n'étaient
      // jusqu'ici enregistrées NULLE PART (invisibles pour l'app) —
      // cf. retour Yann : elles servent désormais de repli "station
      // proche" pour les balises Pioupiou sans baromètre (voir
      // findNearbyMfStations plus bas). Coût négligeable, échantillons
      // courts, purgées à 3h30 en RAM (beaconHistory) comme avant.
      //
      // Correction 12/07/2026 (suite 3, retour Yann après déploiement de
      // la couche carte "Stations pression") : le "~1400 stations (2150 -
      // ~780 avec vent)" ci-dessus était une estimation PAPIER jamais
      // vérifiée en direct — FAUSSE. mfStationsList (2150) est la liste
      // de référence de TOUTES les stations MF connues (CSV statique
      // /liste-stations), mais le paquet d'observations 6 min réellement
      // utilisé ici (DPPaquetObs infrahoraire-6m, réseau RADOME temps
      // réel) ne couvre en pratique qu'un sous-ensemble bien plus restreint
      // (~780 entrées mesuré en direct le 12/07) — et sur ce sous-ensemble,
      // la quasi-totalité a DÉJÀ un anémomètre. En pratique, très peu de
      // stations pression-seule apparaissent dans ce flux (ex. observé :
      // une seule, "CAP BEAR" — station maritime avec baromètre mais sans
      // anémomètre). Un réseau barométrique plus dense existerait
      // potentiellement dans un AUTRE produit Météo-France (non
      // investigué) — pas dans DPPaquetObs infrahoraire-6m tel qu'utilisé
      // ici.
      // Débogage 12/07/2026 (suite) — EN PLUS du buffer RAM ci-dessus,
      // persistance dans mf_station_history (12h, MF_PRESSURE_ONLY_
      // RETENTION_H, purge différenciée dans mfPersistHistory) : sans ça,
      // un redémarrage du process (Render free tier, veille après
      // inactivité) reperdait tout jusqu'à ré-accumuler 2h30+ de recul —
      // même table que les stations vent (Lot 8), lignes distinguées par
      // moy=NULL. moy/dir volontairement absents (jamais mesurés pour
      // ces stations) plutôt que 0/faux, pour ne jamais laisser croire à
      // un vent nul mesuré.
      const t = Date.now();
      const pressureOnlyRows = [];
      for (const [id, obs] of next) {
        if (obs.ff == null && obs.pmer != null) {
          fwRecordHistory(id, { t, pressure: obs.pmer });
          pressureOnlyRows.push({ station_id: id, t, moy: null, dir: null, pressure: obs.pmer });
        }
      }
      mfPersistHistory(pressureOnlyRows); // fire-and-forget — cf. définition, ne bloque/casse jamais la suite

      // ── Étape 28 : alimentation du détecteur de front de rafales ────
      // TOUTES les stations du paquet, pas seulement celles surveillées :
      // l'intérêt du réseau MF est justement de voir le front ARRIVER,
      // 200-300 km en amont, là où personne ne surveille de balise.
      // Historique en RAM (cf. gust-front.js), aucune écriture en base.
      gfIngest(next, t);
    }
  } catch (e) { console.error('refreshMfObs error:', e.message); }
}

async function refreshMeteoFranceData() {
  if (!METEOFRANCE_API_KEY) return;
  if (!mfStationsList.length || Date.now() - mfStationsListFetchedAt > MF_STATIONS_LIST_REFRESH_MS) {
    await refreshMfStationsList();
  }
  await refreshMfObs();
}

// ═══════════════════════════════════════════════════════════════════
//  ÉTAPE 28 — FRONT DE RAFALES (outflow / vague de pression)
//
//  Cf. PROMPT_REPRISE_FRONT_RAFALES.md. La détection elle-même vit dans
//  ./gust-front.js (aucune I/O, rejouable sur archive) ; ce bloc-ci ne
//  fait que l'ingestion, la persistance et le push.
//
//  ⚠️ OPT-IN, comme la chaîne foudre (FW_LIGHTNING_ENABLED) : tout reste
//  dormant tant que GUST_FRONT_ENABLED=1 n'est pas posé sur Render. Et
//  même activé, GUST_FRONT_SHADOW=1 (valeur par défaut) fait tourner le
//  détecteur en écrivant en base SANS envoyer le moindre push — c'est le
//  shadow mode réclamé par le §8.1 de la spec. Un faux positif coûte
//  beaucoup plus cher qu'un ratage : après deux fausses alertes, plus
//  personne ne lit la troisième.
// ═══════════════════════════════════════════════════════════════════
const gf = require('./gust-front');

const GUST_FRONT_ENABLED = process.env.GUST_FRONT_ENABLED === '1';
/** Shadow mode ACTIF par défaut : il faut poser explicitement =0 pour ouvrir les push. */
const GUST_FRONT_SHADOW = process.env.GUST_FRONT_SHADOW !== '0';
/** Cadence de détection — calée sur celle du paquet MF, inutile d'aller plus vite. */
const GUST_FRONT_CYCLE_MS = MF_OBS_POLL_MS;
/** Un événement sans nouvelle détection au-delà de ce délai est clos. */
const GF_EVENT_STALE_MS = 30 * 60 * 1000;
/** Au-delà, un `watch` jamais confirmé est déclaré faux positif. */
const GF_WATCH_EXPIRY_MS = 2 * 60 * 60 * 1000;
/** ETA en deçà de laquelle un événement confirmé devient « imminent ». */
const GF_IMMINENT_MS = 60 * 60 * 1000;

/** Positions des balises Pioupiou, alimentées par pollAndNotify (zéro requête ajoutée). */
const gfBeaconPositions = new Map(); // id -> { lat, lon, nom }

let gfActiveEvent = null;      // { id, status, lastDetectionAt, createdAt, intensity: [] }
let gfLastCycleAt = 0;         // dernière tentative
let gfLastCycleOkAt = 0;       // dernier cycle SANS erreur
let gfLastReason = null;       // pourquoi aucun front (diagnostic)
let gfPublicationLatencyMs = 0;
let gfLastError = null;
let gfModelLastReason = null;  // pourquoi aucun front ANNONCÉ (diagnostic)
let gfLastPurgeAt = 0;         // purge des épisodes anciens, au plus 1×/h

/**
 * Cache RAM des événements vivants, servi tel quel par
 * /gust-front/active. Rafraîchi UNE fois par cycle de détection, donc
 * le coût Supabase est indépendant du nombre de pilotes connectés (même
 * philosophie mutualiste que mfObsCache / fwSignalsCache).
 *
 * Rafraîchi depuis Supabase et non depuis ce que le cycle vient de
 * calculer : c'est ce qui fait apparaître les événements créés À LA MAIN
 * par un admin (RPC admin_create_gust_front_event), que le détecteur ne
 * connaît pas.
 */
let gfActiveCache = { events: [], fetchedAt: 0 };

async function gfRefreshActiveCache() {
  try {
    const events = await sbGet('gust_front_events',
      'select=*&status=in.(watch,confirmed,downgraded)&order=updated_at.desc&limit=5');
    if (!Array.isArray(events) || !events.length) {
      gfActiveCache = { events: [], fetchedAt: Date.now() };
      return;
    }
    const ids = events.map(e => `"${e.id}"`).join(',');
    const [detections, targets] = await Promise.all([
      sbGet('gust_front_detections', `select=*&event_id=in.(${ids})`),
      sbGet('gust_front_targets', `select=*&event_id=in.(${ids})`),
    ]);
    gfActiveCache = {
      events: events.map(e => ({
        ...e,
        detections: (Array.isArray(detections) ? detections : []).filter(d => d.event_id === e.id),
        targets: (Array.isArray(targets) ? targets : []).filter(t => t.event_id === e.id),
      })),
      fetchedAt: Date.now(),
    };
  } catch (e) {
    // On GARDE l'ancien cache plutôt que de le vider : un incident
    // Supabase passager ne doit pas faire disparaître de la carte un
    // front réel en cours de traversée.
    console.error('gfRefreshActiveCache error:', e.message);
  }
}

/**
 * Latence de publication Météo-France : écart entre l'heure de MESURE
 * (validity_time) et l'instant où le paquet nous parvient.
 *
 * Elle se soustrait directement du préavis réellement offert au pilote.
 * L'ignorer reviendrait à annoncer une heure d'arrivée systématiquement
 * trop tardive — donc à promettre un préavis qu'on n'a pas. Mesurée à
 * chaque paquet plutôt que devinée (§3.2 : « à mesurer en shadow mode »).
 */
function gfMeasureLatency(obsMap, now) {
  const lats = [];
  for (const obs of obsMap.values()) {
    if (!obs.validityTime) continue;
    const vt = Date.parse(obs.validityTime);
    if (!Number.isFinite(vt)) continue;
    const d = now - vt;
    if (d >= 0 && d < 60 * 60 * 1000) lats.push(d);
  }
  if (!lats.length) return;
  lats.sort((a, b) => a - b);
  gfPublicationLatencyMs = lats[lats.length >> 1]; // médiane, insensible aux stations en retard
}

// ── Lot A : grille modèle AROME ────────────────────────────────────
//  Produite par la GitHub Action arome-gustfront (8×/jour) et déposée
//  dans Supabase Storage. Le serveur la relit par GET CONDITIONNEL
//  (If-None-Match) : un 304 ne coûte quasiment rien, et on ne
//  retélécharge les ~1,6 Mo que quand le run a réellement changé. Sans
//  ça, une relecture toutes les 30 min ferait 77 Mo/jour d'egress
//  Storage pour une donnée qui ne bouge que 8 fois par jour.
const GF_MODEL_URL = `${SB_URL}/storage/v1/object/public/wind-grid/arome/gustfront/grid.json`;
const GF_MODEL_CHECK_MS = 30 * 60 * 1000;

let gfModelGrid = null;
let gfModelEtag = null;
let gfModelCheckedAt = 0;
let gfModelRun = null;

async function gfLoadModelGrid() {
  if (Date.now() - gfModelCheckedAt < GF_MODEL_CHECK_MS && gfModelGrid) return;
  gfModelCheckedAt = Date.now();
  try {
    const headers = {};
    if (gfModelEtag) headers['If-None-Match'] = gfModelEtag;
    const r = await fetch(GF_MODEL_URL, { headers });
    if (r.status === 304) return;          // run inchangé, rien à faire
    if (!r.ok) {
      // Grille absente = veille modèle simplement indisponible. Ce n'est
      // pas une erreur bloquante : la détection MESURÉE, qui est la
      // source principale, continue sans elle.
      if (r.status !== 404) console.warn(`gfLoadModelGrid: HTTP ${r.status}`);
      return;
    }
    const grid = await r.json();
    if (!grid || !Array.isArray(grid.times) || !grid.times.length) return;
    gfModelGrid = grid;
    gfModelEtag = r.headers.get('etag');
    gfModelRun = grid.run || null;
    console.log(`🌬️ Grille modèle chargée — run ${gfModelRun}, ${grid.times.length} échéances`);
  } catch (e) {
    console.error('gfLoadModelGrid error:', e.message);
  }
}

/** Passe le paquet d'observations MF au détecteur. */
function gfIngest(obsMap, t) {
  if (!GUST_FRONT_ENABLED) return;
  try {
    gfMeasureLatency(obsMap, t);
    const rows = [];
    for (const [id, obs] of obsMap) {
      rows.push({ id, pmer: obs.pmer, ff: obs.ff, raf: obs.raf10, dd: obs.dd, temp: obs.temp });
    }
    gf.gfRecordObs(rows, t);
  } catch (e) { console.error('gfIngest error:', e.message); }
}

/**
 * Toutes les positions connues, toutes sources confondues — c'est sur
 * cette table qu'on calcule les ETA et qu'on décide qui est prévenu.
 * Les quatre sources sont incluses délibérément : un pilote qui n'a que
 * des favoris AEMET ou Infoclimat ne doit pas être silencieusement
 * exclu du ciblage parce que sa source n'est pas Pioupiou.
 */
function gfAllPositions() {
  const out = new Map(); // `${source}:${id}` -> { id, source, lat, lon, nom }
  for (const [id, p] of gfBeaconPositions) {
    if (Number.isFinite(p.lat) && Number.isFinite(p.lon)) {
      out.set(`pioupiou:${id}`, { id, source: 'pioupiou', lat: p.lat, lon: p.lon, nom: p.nom });
    }
  }
  for (const s of mfStationsList) {
    out.set(`meteofrance:${s.id}`, { id: s.id, source: 'meteofrance', lat: s.lat, lon: s.lon, nom: s.nom });
  }
  for (const [id, s] of infoclimatStationsById) {
    if (Number.isFinite(s.lat) && Number.isFinite(s.lon)) {
      out.set(`infoclimat:${id}`, { id, source: 'infoclimat', lat: s.lat, lon: s.lon, nom: s.nom });
    }
  }
  for (const [id, s] of aemetObsCache) {
    if (Number.isFinite(s.lat) && Number.isFinite(s.lon)) {
      out.set(`aemet:${id}`, { id, source: 'aemet', lat: s.lat, lon: s.lon, nom: s.nom });
    }
  }
  return out;
}

/** Corps du push, dans l'enveloppe flightwatch déjà gérée par le Service Worker. */
function gfBuildPush(level, event, etaMs, beaconName) {
  const hhmm = etaMs
    ? new Date(etaMs).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Paris' })
    : null;
  const gust = event.max_gust_kmh ? `${Math.round(event.max_gust_kmh)} km/h` : null;

  // Ton volontairement factuel et non alarmiste, avec l'incertitude
  // assumée et une consigne actionnable — gabarit repris du §1 de la
  // spec. Jamais de formulation qui ressemblerait à une AUTORISATION de
  // voler, et aucune notion de niveau de pilote (ligne rouge projet).
  const title = level === 'imminent'
    ? '🔴 Front de rafales — arrivée imminente'
    : '⚠️ Front de rafales possible';
  const parts = [];
  if (beaconName) parts.push(beaconName);
  if (hhmm) parts.push(level === 'imminent' ? `arrivée ~${hhmm}` : `arrivée estimée ~${hhmm}`);
  if (gust) parts.push(`rafales ${gust}`);
  parts.push('soyez au sol et le matériel rangé avant');

  return {
    title, body: parts.join(' — '),
    // Mêmes chemins que tous les autres push du serveur : /icons/icon-192.png
    // n'existe pas (l'icône est à la racine du public/), et un chemin
    // d'icône invalide fait tomber la notification sur un rendu générique
    // sans le moindre message d'erreur.
    icon: '/apple-touch-icon.png', badge: '/apple-touch-icon.png',
    tag: `fw-gust_front-${event.id}`,
    requireInteraction: level === 'imminent',
    data: {
      kind: 'flightwatch',
      signal: 'gust_front',
      level: level === 'imminent' ? 3 : 2,
      scope: `gust_front:${event.id}`,
      eventId: event.id,
      // Pas de voix : la synthèse vocale est réservée aux signaux ancrés
      // sur une balise surveillée, et un front de rafales concerne un
      // couloir entier. Le son distinct du niveau 3 suffit.
      voice: false,
      value: event.max_gust_kmh ?? null,
      unit: 'km/h',
      eta: etaMs ? new Date(etaMs).toISOString() : null,
    },
  };
}

/**
 * Cycle complet : détecter, persister, cibler, notifier.
 * Ne jette jamais — une exception ici ne doit pas emporter la boucle MF.
 */
async function gustFrontCycle() {
  if (!GUST_FRONT_ENABLED) return;
  gfLastCycleAt = Date.now();
  try {
    const now = Date.now();

    // ── Lot A d'abord : la veille modèle ────────────────────────────
    // Elle tourne AVANT la détection mesurée pour deux raisons : elle
    // fournit l'a priori qui rendra la mesure plus sensible dans le
    // couloir annoncé, et elle crée l'événement `watch` que la mesure
    // viendra ensuite confirmer plutôt que d'en créer un second.
    await gfLoadModelGrid();
    const modelFront = await gfModelCycle(now);

    const stationMeta = new Map(
      mfStationsList.map(s => [s.id, { lat: s.lat, lon: s.lon, nom: s.nom }])
    );
    const res = gf.gfDetect(stationMeta, now, gfPublicationLatencyMs, {
      priorCorridor: modelFront ? modelFront.contains : null,
    });
    gfLastReason = res.front ? null : res.reason;

    if (!res.front) {
      await gfCloseStaleEvent(now);
      await gfSweepOrphans(now);
      // Rafraîchi MÊME sans détection : c'est ce qui fait apparaître un
      // événement saisi à la main par un admin, et disparaître un
      // événement qu'on vient de clore.
      await gfRefreshActiveCache();
      gfLastCycleOkAt = now;
      gfLastError = null;
      return;
    }

    const f = res.front;
    const eventPayload = {
      source: 'mf_network',
      kind: 'outflow',
      status: 'confirmed', // détection MESURÉE : confirmé d'emblée (§4.4)
      axis: { type: 'LineString', coordinates: [
        [f.line.a.lon, f.line.a.lat], [f.line.b.lon, f.line.b.lat],
      ] },
      corridor: { type: 'Polygon', coordinates: [f.corridor] },
      propagation_bearing: f.bearing,
      propagation_speed_kmh: f.speedKmh,
      max_gust_kmh: f.maxGustKmh,
      max_pressure_jump_hpa: f.maxPressureJumpHpa,
      confidence: f.confidence,
      updated_at: new Date(now).toISOString(),
      raw: {
        thresholds_version: f.thresholdsVersion,
        station_count: f.stationCount,
        r2: f.r2,
        publication_latency_min: Math.round(f.publicationLatencyMs / 60000),
        stations_evaluated: res.evaluated,
        shadow: GUST_FRONT_SHADOW,
        forecast_lines: f.forecastLines.map(l => ({
          offset_min: l.offsetMin,
          coordinates: [[l.line.a.lon, l.line.a.lat], [l.line.b.lon, l.line.b.lat]],
        })),
      },
    };

    // Un front détecté alors qu'un épisode est déjà suivi le raffine ;
    // il n'en crée pas un second. C'est toute la différence entre une
    // photo par cycle et un objet suivi (§4.2).
    //
    // Cas particulier §4.4 : si l'épisode suivi est une VEILLE MODÈLE
    // (`watch`), la mesure ne crée pas un événement concurrent — elle
    // PROMEUT celui-là en `confirmed`, et ses géométries mesurées
    // remplacent les géométries prévues. C'est le moment où « il va
    // peut-être se passer quelque chose » devient « c'est en train
    // d'arriver, voici où et quand ».
    const reuse = gfActiveEvent && (now - gfActiveEvent.lastDetectionAt) < GF_EVENT_STALE_MS;
    const promoting = reuse && gfActiveEvent.status === 'watch';
    if (promoting) {
      eventPayload.source = 'merged';   // annoncé par le modèle, confirmé par la mesure
      console.log(`🌬️ Veille modèle ${gfActiveEvent.id} CONFIRMÉE par la mesure`);
    }
    let eventId;
    if (reuse) {
      eventId = gfActiveEvent.id;
      await sbPatch('gust_front_events', `id=eq.${eventId}`, eventPayload);
    } else {
      const created = await sbInsertReturning('gust_front_events', eventPayload);
      eventId = created?.id;
      if (!eventId) { gfLastError = 'insert_failed'; return; }
      gfActiveEvent = { id: eventId, status: 'confirmed', createdAt: now, intensity: [] };
      console.log(`🌬️ Front de rafales détecté (${f.stationCount} stations, ${Math.round(f.speedKmh)} km/h au ${Math.round(f.bearing)}°) — événement ${eventId}`);
    }
    gfActiveEvent.lastDetectionAt = now;
    gfActiveEvent.status = eventPayload.status;

    // Essoufflement : trois cycles d'affilée d'intensité décroissante →
    // on RÉTROGRADE plutôt que de maintenir une alerte pour un front qui
    // meurt en route. Bandeau atténué, et surtout aucun nouveau push.
    gfActiveEvent.intensity.push(f.maxGustKmh ?? 0);
    if (gfActiveEvent.intensity.length > 4) gfActiveEvent.intensity.shift();
    const ints = gfActiveEvent.intensity;
    if (ints.length >= 4 && ints[0] > ints[1] && ints[1] > ints[2] && ints[2] > ints[3]) {
      await sbPatch('gust_front_events', `id=eq.${eventId}`,
        { status: 'downgraded', updated_at: new Date(now).toISOString() });
      gfActiveEvent.status = 'downgraded';
    }

    // Détections élémentaires : remplacées à chaque cycle (l'ajustement
    // est recalculé en entier, garder les anciennes ferait doublon).
    await sbDelete('gust_front_detections', `event_id=eq.${eventId}`);
    await sbInsert('gust_front_detections', res.detections.map(d => ({
      event_id: eventId,
      source: 'mf_station',
      station_id: d.id,
      station_name: d.nom,
      lat: d.lat, lon: d.lon,
      detected_at: new Date(d.t).toISOString(),
      delta_pressure_hpa: d.deltaPressureHpa,
      delta_speed_kmh: d.deltaSpeedKmh,
      delta_heading_deg: d.deltaHeadingDeg,
      delta_temp_c: d.deltaTempC,
      gust_kmh: d.gustKmh,
      score: d.score,
    })));

    // ETA par balise du couloir.
    const positions = gfAllPositions();
    const targets = [];
    for (const p of positions.values()) {
      if (!f.contains(p.lat, p.lon)) continue;
      const eta = f.etaFor(p.lat, p.lon);
      if (eta < now - 30 * 60 * 1000) continue; // déjà franchie il y a longtemps
      targets.push({
        event_id: eventId,
        station_id: p.id,
        station_name: p.nom,
        source: p.source,
        lat: p.lat, lon: p.lon,
        eta_at: new Date(eta).toISOString(),
        // ±15 min tant qu'aucune balise locale n'a confirmé le passage
        // (§4.2). Resserré à ±5 min par le Lot C, plus tard.
        eta_window_minutes: 15,
        expected_gust_kmh: f.maxGustKmh,
        passed_at: eta <= now ? new Date(eta).toISOString() : null,
      });
    }
    await sbDelete('gust_front_targets', `event_id=eq.${eventId}`);
    await sbInsert('gust_front_targets', targets);

    // Bornes de la fenêtre annoncée : de la première à la dernière
    // arrivée encore à venir dans le couloir.
    const future = targets.filter(t => new Date(t.eta_at).getTime() > now)
      .map(t => new Date(t.eta_at).getTime()).sort((a, b) => a - b);
    if (future.length) {
      await sbPatch('gust_front_events', `id=eq.${eventId}`, {
        eta_start: new Date(future[0] - 15 * 60000).toISOString(),
        eta_end: new Date(future[future.length - 1] + 15 * 60000).toISOString(),
      });
    }

    // Cache AVANT le push : si l'envoi échoue, les pilotes doivent
    // malgré tout voir le front sur la carte.
    await gfRefreshActiveCache();

    await gfNotify(eventId, targets, now);

    gfLastCycleOkAt = now;
    gfLastError = null;
  } catch (e) {
    gfLastError = e.message;
    console.error('gustFrontCycle error:', e.message);
  }
}

/**
 * Lot A — veille modèle. Crée ou rafraîchit un événement `watch`, et
 * renvoie le front annoncé pour que la détection mesurée s'en serve
 * comme a priori.
 *
 * ⚠️ AUCUN PUSH ici, jamais. Une veille modèle s'affiche (bandeau
 * orange, calque en pointillés), elle ne réveille personne. AROME se
 * trompe couramment d'une à deux heures sur le déclenchement convectif ;
 * pousser à chaque front annoncé garantirait des fausses alertes
 * régulières, et après deux d'entre elles plus personne ne lit la
 * troisième. Le push reste l'apanage du front MESURÉ (§8, décision Yann
 * du 31/07/2026).
 */
async function gfModelCycle(now) {
  if (!gfModelGrid) return null;
  try {
    const res = gf.gfDetectModel(gfModelGrid, now);
    gfModelLastReason = res.front ? null : res.reason;
    if (!res.front) return null;

    const m = res.front;

    // Un épisode déjà CONFIRMÉ par la mesure prime : on ne le rétrograde
    // pas vers une géométrie de prévision, moins précise. On rend quand
    // même le couloir modèle, il reste utile comme a priori.
    if (gfActiveEvent && gfActiveEvent.status !== 'watch') return m;

    const payload = {
      source: 'model',
      kind: m.kind,
      status: 'watch',
      axis: { type: 'LineString', coordinates: [
        [m.line.a.lon, m.line.a.lat], [m.line.b.lon, m.line.b.lat],
      ] },
      corridor: { type: 'Polygon', coordinates: [m.corridor] },
      propagation_bearing: m.bearing,
      propagation_speed_kmh: m.speedKmh,
      max_gust_kmh: m.maxGustKmh,
      confidence: m.confidence,
      updated_at: new Date(now).toISOString(),
      raw: {
        thresholds_version: m.thresholdsVersion,
        model_run: gfModelRun,
        grid_points: m.stationCount,
        r2: m.r2,
        shadow: GUST_FRONT_SHADOW,
        forecast_lines: m.forecastLines.map(l => ({
          offset_min: l.offsetMin,
          coordinates: [[l.line.a.lon, l.line.a.lat], [l.line.b.lon, l.line.b.lat]],
        })),
      },
    };

    if (gfActiveEvent) {
      await sbPatch('gust_front_events', `id=eq.${gfActiveEvent.id}`, payload);
      gfActiveEvent.lastDetectionAt = now;
    } else {
      const created = await sbInsertReturning('gust_front_events', payload);
      if (!created?.id) return m;
      gfActiveEvent = {
        id: created.id, status: 'watch', createdAt: now,
        lastDetectionAt: now, intensity: [],
      };
      console.log(`🌬️ VEILLE MODÈLE — front annoncé (${m.stationCount} points, ${Math.round(m.speedKmh)} km/h au ${Math.round(m.bearing)}°, ${m.kind}) — événement ${created.id}`);
    }

    // ETA par balise, comme pour la mesure — mais fenêtre BEAUCOUP plus
    // large : ±45 min contre ±15. Le modèle ne sait pas faire mieux, et
    // annoncer une précision qu'on n'a pas serait pire que de ne rien
    // annoncer.
    const positions = gfAllPositions();
    const targets = [];
    for (const p of positions.values()) {
      if (!m.contains(p.lat, p.lon)) continue;
      const eta = m.etaFor(p.lat, p.lon);
      if (eta < now) continue;
      targets.push({
        event_id: gfActiveEvent.id,
        station_id: p.id, station_name: p.nom, source: p.source,
        lat: p.lat, lon: p.lon,
        eta_at: new Date(eta).toISOString(),
        eta_window_minutes: 45,
        expected_gust_kmh: m.maxGustKmh,
        passed_at: null,
      });
    }
    await sbDelete('gust_front_targets', `event_id=eq.${gfActiveEvent.id}`);
    await sbInsert('gust_front_targets', targets);

    const future = targets.map(t => new Date(t.eta_at).getTime()).sort((a, b) => a - b);
    if (future.length) {
      await sbPatch('gust_front_events', `id=eq.${gfActiveEvent.id}`, {
        eta_start: new Date(future[0] - 45 * 60000).toISOString(),
        eta_end: new Date(future[future.length - 1] + 45 * 60000).toISOString(),
      });
    }

    return m;
  } catch (e) {
    console.error('gfModelCycle error:', e.message);
    return null;
  }
}

/**
 * Balayage des événements ORPHELINS, indépendant de l'état RAM.
 *
 * ⚠️ Défaut trouvé le 31/07/2026 en relisant le cycle de vie avant
 * l'ouverture à tous. `gfActiveEvent` vit en RAM. Or le free tier Render
 * s'endort et redémarre régulièrement : au réveil, `gfActiveEvent` est
 * null, le cycle crée donc un NOUVEL événement — pendant que l'ancien
 * reste `watch` pour toujours, puisque gfCloseStaleEvent ne sait clore
 * que celui qu'il a en mémoire.
 *
 * Conséquence : des bandeaux « front de rafales » figés indéfiniment
 * chez tous les pilotes, et une accumulation silencieuse en base. C'est
 * la même classe de bug que les objets orphelins du Storage (cf.
 * BUGS.md 30/07) — un état vivant qui n'a personne pour le clore.
 *
 * D'où ce balayage qui travaille sur la BASE et non sur la RAM : tout
 * événement vivant non rafraîchi depuis GF_EVENT_STALE_MS est expiré,
 * que le process qui l'a créé existe encore ou non.
 */
async function gfSweepOrphans(now) {
  try {
    const cutoff = new Date(now - GF_EVENT_STALE_MS).toISOString();
    // `is_manual=is.false` est indispensable : un événement saisi par un
    // admin n'est JAMAIS rafraîchi par le détecteur, ce balayage le
    // tuerait donc dans la minute.
    await sbPatch(
      'gust_front_events',
      `status=in.(watch,confirmed,downgraded)&updated_at=lt.${cutoff}&is_manual=is.false`,
      { status: 'expired', updated_at: new Date(now).toISOString() },
    );
    // Les événements manuels, eux, s'effacent une heure après la fin de
    // leur fenêtre annoncée — sinon ils resteraient à l'écran jusqu'à ce
    // qu'un admin y repense.
    const past = new Date(now - 60 * 60 * 1000).toISOString();
    await sbPatch(
      'gust_front_events',
      `status=in.(watch,confirmed,downgraded)&is_manual=is.true&eta_end=lt.${past}`,
      { status: 'passed', updated_at: new Date(now).toISOString() },
    );
    // ── Purge des épisodes anciens ────────────────────────────────
    // Les détections et ETA d'un épisode clos ne sont JAMAIS réécrites :
    // sans purge, chaque épisode laisse ~575 lignes derrière lui, pour
    // toujours. C'est exactement le mécanisme d'accumulation silencieuse
    // qui a rempli le Storage (cf. BUGS.md 30/07) — aucune des chaînes
    // d'ingestion ne contenait de `delete`.
    //
    // 30 jours : assez pour un post-mortem et une campagne de
    // calibration (§8.2), assez court pour borner la croissance. Les
    // ÉVÉNEMENTS eux-mêmes sont conservés indéfiniment — ils sont peu
    // nombreux et constituent l'historique des faux positifs, qui est la
    // mesure de qualité du détecteur.
    if (now - gfLastPurgeAt > 60 * 60 * 1000) {
      gfLastPurgeAt = now;
      const old = new Date(now - 30 * 24 * 60 * 60 * 1000).toISOString();
      const stale = await sbGet('gust_front_events',
        `select=id&updated_at=lt.${old}&status=in.(passed,expired,cancelled)&limit=200`);
      const ids = (Array.isArray(stale) ? stale : []).map(e => `"${e.id}"`).join(',');
      if (ids) {
        await sbDelete('gust_front_detections', `event_id=in.(${ids})`);
        await sbDelete('gust_front_targets', `event_id=in.(${ids})`);
      }
    }
  } catch (e) {
    console.error('gfSweepOrphans error:', e.message);
  }
}

/**
 * Au démarrage, reprendre l'épisode en cours plutôt que d'en créer un
 * doublon. Complément indispensable du balayage ci-dessus : sans lui, un
 * redémarrage au milieu d'un vrai front couperait le suivi en deux
 * événements, et le pilote verrait l'ETA se réinitialiser.
 */
async function gfAdoptActiveEvent() {
  if (!GUST_FRONT_ENABLED) return;
  try {
    const rows = await sbGet('gust_front_events',
      'select=id,status,updated_at,max_gust_kmh&status=in.(watch,confirmed,downgraded)&is_manual=is.false&order=updated_at.desc&limit=1');
    const row = Array.isArray(rows) ? rows[0] : null;
    if (!row) return;
    const age = Date.now() - new Date(row.updated_at).getTime();
    if (age > GF_EVENT_STALE_MS) return;   // le balayage s'en chargera
    gfActiveEvent = {
      id: row.id,
      status: row.status,
      createdAt: Date.now(),
      lastDetectionAt: new Date(row.updated_at).getTime(),
      intensity: [],
    };
    console.log(`🌬️ Épisode ${row.id} (${row.status}) repris après redémarrage`);
  } catch (e) {
    console.error('gfAdoptActiveEvent error:', e.message);
  }
}

/** Clôt l'épisode suivi quand plus rien ne le confirme. */
async function gfCloseStaleEvent(now) {
  if (!gfActiveEvent) return;
  const silent = now - gfActiveEvent.lastDetectionAt;
  if (silent < GF_EVENT_STALE_MS) return;

  // `passed` = le front a bien traversé et il est sorti du réseau.
  // `expired` = une veille jamais confirmée, donc un FAUX POSITIF, et
  // c'est important de le nommer ainsi : c'est cette comptabilité qui
  // permettra de dire si le détecteur tient l'objectif de ≤ 1 faux
  // positif par mois de saison avant d'ouvrir aux utilisateurs.
  const status = gfActiveEvent.status === 'watch' && silent > GF_WATCH_EXPIRY_MS
    ? 'expired' : 'passed';
  await sbPatch('gust_front_events', `id=eq.${gfActiveEvent.id}`,
    { status, updated_at: new Date(now).toISOString() });
  console.log(`🌬️ Événement ${gfActiveEvent.id} clos (${status})`);
  gfActiveEvent = null;
}

/**
 * Push ciblé. Deux verrous avant qu'un pilote soit notifié :
 *  1. shadow mode désactivé explicitement (GUST_FRONT_SHADOW=0) ;
 *  2. une de ses balises favorites ou surveillées est dans le couloir.
 * Plus la déduplication en base : au plus UN push `watch` et UN push
 * `imminent` par événement et par compte.
 *
 * Le filtre `beta_testers` a été RETIRÉ le 31/07/2026 (sortie de bêta,
 * décision Yann). GUST_FRONT_SHADOW devient donc l'unique interrupteur
 * maître : tant qu'il vaut 1, le détecteur écrit en base et alimente la
 * carte mais n'envoie aucun push, pour personne.
 *
 * Rappel de ce qui ne pousse JAMAIS, indépendamment de tout ça : une
 * veille MODÈLE (`status = 'watch'`, source `model`). Seul un front
 * mesuré déclenche une notification — cf. gfModelCycle.
 */
async function gfNotify(eventId, targets, now) {
  if (GUST_FRONT_SHADOW) return;
  if (!targets.length) return;

  const etaByStation = new Map(targets.map(t => [t.station_id, t]));

  const [watchedRows, favRows, survRows, deviceRows, notifRows] = await Promise.all([
    sbGet('user_watched', 'select=user_id,beacon_id,nom'),
    sbGet('user_favorites', 'select=user_id,beacon_id,beacon_nom'),
    sbGet('user_surveillance', 'select=user_id,sig_gust_front'),
    sbGet('user_devices', 'select=*'),
    sbGet('gust_front_notifications', `select=user_id,level&event_id=eq.${eventId}`),
  ]);

  // Pas de ligne = pref absente : on retombe sur le défaut `true` du
  // schéma, cohérent avec le reste des prefs flightwatch.
  const optedOut = new Set(
    (Array.isArray(survRows) ? survRows : [])
      .filter(r => r.sig_gust_front === false).map(r => r.user_id)
  );

  const devicesByUser = {};
  (Array.isArray(deviceRows) ? deviceRows : []).forEach(dv => {
    (devicesByUser[dv.user_id] ??= []).push(dv);
  });

  const alreadySent = new Set(
    (Array.isArray(notifRows) ? notifRows : []).map(r => `${r.user_id}|${r.level}`)
  );

  // Balise la plus proche dans le temps, par compte.
  const soonestByUser = new Map();
  const consider = (userId, beaconId, nom) => {
    if (optedOut.has(userId)) return;
    const tg = etaByStation.get(String(beaconId));
    if (!tg) return;
    const eta = new Date(tg.eta_at).getTime();
    if (eta <= now) return; // déjà passé chez lui : prévenir n'a plus d'objet
    const cur = soonestByUser.get(userId);
    if (!cur || eta < cur.eta) soonestByUser.set(userId, { eta, nom: nom || tg.station_name });
  };
  (Array.isArray(watchedRows) ? watchedRows : []).forEach(w => consider(w.user_id, w.beacon_id, w.nom));
  (Array.isArray(favRows) ? favRows : []).forEach(fv => consider(fv.user_id, fv.beacon_id, fv.beacon_nom));

  const eventRow = (await sbGet('gust_front_events', `id=eq.${eventId}&select=*`))?.[0];
  if (!eventRow) return;
  // Un front qui s'essouffle ne génère plus de nouveau push (§4.4).
  if (eventRow.status === 'downgraded') return;

  for (const [userId, info] of soonestByUser) {
    const level = (info.eta - now) <= GF_IMMINENT_MS ? 'imminent' : 'watch';
    if (alreadySent.has(`${userId}|${level}`)) continue;
    const devices = devicesByUser[userId] || [];
    if (!devices.length) continue;

    const payload = gfBuildPush(level, eventRow, info.eta, info.nom);
    let ok = false;
    for (const dv of devices) {
      try {
        await webpush.sendNotification(
          { endpoint: dv.endpoint, keys: { p256dh: dv.p256dh, auth: dv.auth } },
          JSON.stringify(payload)
        );
        ok = true;
        console.log(`📲 Push front de rafales (${level}) → ${userId}`);
      } catch (err) {
        if (err.statusCode === 410 || err.statusCode === 404) {
          await sbDelete('user_devices', `endpoint=eq.${encodeURIComponent(dv.endpoint)}`);
        } else console.warn(`⚠️ Push front de rafales error ${err.statusCode}`);
      }
    }
    // Écrit MÊME en cas d'échec d'envoi : la clé primaire est le garde-fou
    // anti-doublon, et une tentative ratée ne doit pas rouvrir la porte à
    // un renvoi en boucle au cycle suivant.
    await sbUpsert('gust_front_notifications', {
      event_id: eventId, user_id: userId, level,
      sent_at: new Date(now).toISOString(), channel: 'webpush', success: ok,
    }, 'event_id,user_id,level');
  }
}

// Débogage 12/07/2026 — stations MF PROCHES d'une balise (pression
// uniquement, avec ou sans vent), triées par distance croissante, dans
// FW_PRESSURE_NEARBY_STATION_MAX_KM. Cache PERMANENT par balise (mêmes
// coordonnées fixes, même philosophie que beaconDepartmentCache
// ci-dessus) : la géographie ne change jamais, seule la donnée mfObsCache
// (fraîcheur/validité de pmer à l'instant T) est revérifiée à chaque
// appel côté appelant. Sert de repli intermédiaire pour pressure_drop
// (fwRealPressureTrend propre à la balise > station MF proche > modèle
// AROME, cf. pollAndNotify) — beaucoup de balises Pioupiou n'ont pas de
// baromètre, mais une station MF (même sans anémomètre) est presque
// toujours à moins de 40 km, et une vraie mesure reste plus fiable
// qu'une valeur de grille modèle sur un champ aussi lisse que la
// pression.
const nearbyMfStationsCache = new Map(); // beacon_id (string) -> [{id, nom, distanceKm}] trié croissant
function findNearbyMfStations(beaconId, lat, lon) {
  if (nearbyMfStationsCache.has(beaconId)) return nearbyMfStationsCache.get(beaconId);
  const candidates = [];
  if (lat != null && lon != null) {
    for (const s of mfStationsList) {
      const d = fwHaversineKm(lat, lon, s.lat, s.lon);
      if (d <= FW_PRESSURE_NEARBY_STATION_MAX_KM) candidates.push({ id: s.id, nom: s.nom, distanceKm: d });
    }
    candidates.sort((a, b) => a.distanceKm - b.distanceKm);
  }
  // Cache seulement une fois mfStationsList non vide (sinon une balise
  // évaluée avant le tout premier refreshMeteoFranceData resterait
  // bloquée à [] pour toujours) — ré-essayé au prochain appel tant que
  // la liste n'est pas encore chargée.
  if (mfStationsList.length) nearbyMfStationsCache.set(beaconId, candidates);
  return candidates;
}

// ── Étape 12 (17/07/2026) : stations personnelles Infoclimat (réseau
// StatIC) — RÉÉCRIT LE 03/08/2026 : ce serveur ne parle plus à
// Infoclimat ─────────────────────────────────────────────────────────
//
// Contrairement aux stations MF (réseau officiel RADOME), ce sont des
// stations AMATEUR (Netatmo, Davis, WeeWX...) hébergées bénévolement par
// des particuliers et republiées par l'association Infoclimat.
//
// ┌─ POURQUOI CE BLOC N'APPELLE PLUS INFOCLIMAT ────────────────────┐
// │ La clé Infoclimat est liée à UNE adresse IP déclarée. Les IP    │
// │ sortantes de Render sont MULTIPLES (74.220.51.0/24 +            │
// │ 74.220.59.0/24, 512 adresses possibles) : une clé ne peut pas   │
// │ les couvrir. Le refus arrive en `Wrong ip address` — EN HTTP    │
// │ 200 — donc les calques s'affichaient vides, sans une ligne      │
// │ d'erreur, et on a mis trois semaines à le voir.                 │
// │                                                                 │
// │ Depuis le 03/08, un VPS à IPv4 fixe (51.91.102.146) poll et     │
// │ écrit deux objets dans R2 ; ce serveur les LIT. Le poller vit   │
// │ dans `traces/infoclimat/` — c'est là, et SEULEMENT là, que se   │
// │ trouve la connaissance de l'API Infoclimat.                     │
// │                                                                 │
// │ ⚠️ NE PAS REMETTRE D'APPEL DIRECT ICI. Il ne peut pas marcher,  │
// │    et son échec est invisible.                                  │
// └─────────────────────────────────────────────────────────────────┘
//
// Ce qui a disparu avec la réécriture, et pourquoi ce n'est pas une
// perte : `fetchInfoclimatBatch` (et sa gestion des trois échecs qui
// arrivent en HTTP 200), `refreshInfoclimatStationsList` (le GeoJSON
// data.gouv.fr) et le découpage en lots vivent désormais dans
// `traces/infoclimat/poller_infoclimat.py`, sur la seule machine dont
// l'IP est acceptée. Rien n'est oublié, tout a déménagé.
//
// Trois caches RAM, même philosophie que mfStationsList/mfObsCache :
//  - infoclimatStationsList / infoclimatStationsById : métadonnées
//    (id/nom/coords/altitude/LICENCE), servies par `latest.json` ;
//  - infoclimatObsCache : dernier relevé par station ;
//  - infoclimatHistory : jusqu'à 30 h glissantes, relues bien moins
//    souvent parce que l'objet est 14× plus gros.
//
// ⚠️ LA LICENCE VARIE D'UNE STATION À L'AUTRE, y compris dans un rayon
//    de 20 km : sur les 854 stations servies le 03/08, 442 en
//    `NON-COMMERCIAL ONLY: CC BY NC` et 412 en `CC BY`. Elle voyage PAR
//    STATION jusqu'au client, qui doit afficher celle de la station
//    MONTRÉE — une mention globale serait fausse une fois sur deux.
//
// Si les objets R2 sont absents (poller jamais lancé) : les caches
// restent vides, /infoclimat-stations renvoie une liste vide, aucun
// crash — même dégradation silencieuse que le reste des modules
// optionnels.
const INFOCLIMAT_R2_BASE = process.env.INFOCLIMAT_R2_BASE
  || 'https://pub-14b7b6ffdba34729b51280359c8f2c01.r2.dev';
const INFOCLIMAT_LATEST_URL = `${INFOCLIMAT_R2_BASE}/infoclimat/latest.json`;
const INFOCLIMAT_HISTORY_URL = `${INFOCLIMAT_R2_BASE}/infoclimat/history.json`;
// Lecture d'un objet R2 de ~32 Ko, PAS un appel chez Infoclimat : la
// cadence ici ne coûte rien à l'association. 5 min pour que l'affichage
// suive de près le palier le plus rapide du poller (10 min).
const INFOCLIMAT_OBS_POLL_MS = 5 * 60 * 1000;
// L'historique pèse ~444 Ko compressés — 14× `latest.json`. Le poller ne
// le réécrit que toutes les 30 min : le relire plus souvent ne
// rapporterait rien.
const INFOCLIMAT_HISTORY_POLL_MS = 30 * 60 * 1000;
// ⚠️ PÉREMPTION CÔTÉ LECTURE, en plus de celle du poller. Le poller
//    n'écrit que des relevés de moins de 90 min ; mais si le VPS meurt,
//    `latest.json` se FIGE et ce serveur servirait indéfiniment un vent
//    d'il y a six heures comme s'il était courant. Pour une app de
//    sécurité en vol, une donnée périmée présentée comme fraîche est
//    pire que pas de donnée du tout. On refiltre donc à la lecture : le
//    cache se vide tout seul dans les 90 min qui suivent une panne du
//    poller, et le calque disparaît au lieu de mentir.
const INFOCLIMAT_OBS_MAX_AGE_MS = 90 * 60 * 1000;

let infoclimatStationsList = []; // [{id, nom, lat, lon, alt, licenseCode, licenseLabel, licenseUrl}]
let infoclimatStationsById = new Map();
let infoclimatObsCache = new Map(); // id -> {t, moy, raf, dir, pressure, temp}
let infoclimatObsCacheFetchedAt = 0;
let infoclimatHistory = new Map(); // id -> [{t, avg, max, dir, pressure}]
let infoclimatHistoryFetchedAt = 0;
// Débogage 17/07/2026 — dernière erreur rencontrée par le pipeline
// Infoclimat, exposée via /infoclimat-stations pour diagnostiquer depuis
// le client sans accès aux logs Render. Depuis le 03/08 elle porte aussi
// « objet périmé », qui est le symptôme d'un poller arrêté sur le VPS.
let infoclimatLastError = null;

// Lecture d'un objet JSON écrit par le poller.
// ⚠️ `fetch` de Node envoie `Accept-Encoding: br, gzip, deflate` de
//    lui-même et Cloudflare sert du gzip : on lit ~32 Ko au lieu de
//    218 Ko sans rien avoir à écrire (vérifié en direct le 03/08).
//    Ne PAS ajouter d'en-tête à la main, et surtout ne pas en retirer.
async function fetchInfoclimatObjet(url) {
  const r = await fetch(url, { headers: { 'Cache-Control': 'no-cache' } });
  if (!r.ok) {
    // 404 = le poller n'a jamais tourné. Ce n'est pas une panne, c'est
    // un module optionnel non configuré : on le dit sans crier.
    throw new Error(r.status === 404
      ? `objet absent (${url}) — le poller du VPS n'a pas encore écrit`
      : `HTTP ${r.status} sur ${url}`);
  }
  return r.json();
}

// Âge de l'objet, en minutes, d'après le `genere_le` que le poller y
// écrit. C'est le seul moyen de distinguer « le poller tourne et rien
// n'a bougé » de « le poller est mort depuis trois heures » : les deux
// donnent le même contenu.
function infoclimatAgeMin(doc) {
  const t = Date.parse(doc?.genere_le ?? '');
  return Number.isFinite(t) ? (Date.now() - t) / 60000 : null;
}

async function refreshInfoclimatObs() {
  try {
    const doc = await fetchInfoclimatObjet(INFOCLIMAT_LATEST_URL);
    const meta = doc?.stations || {};
    const obs = doc?.obs || {};
    const limite = Date.now() - INFOCLIMAT_OBS_MAX_AGE_MS;

    const liste = [];
    const parId = new Map();
    const cache = new Map();
    for (const [id, o] of Object.entries(obs)) {
      const m = meta[id];
      if (!m) continue;
      // ⚠️ Le poller écrit `t` en SECONDES Unix (convention Python) ;
      //    tout le reste de ce fichier raisonne en MILLISECONDES. La
      //    conversion se fait ICI, une fois, et pas dans les routes.
      const t = Number.isFinite(o?.t) ? o.t * 1000 : NaN;
      if (!Number.isFinite(t) || t < limite) continue; // cf. péremption
      const s = {
        id, nom: m.nom, lat: m.lat, lon: m.lon, alt: m.alt ?? null,
        licenseCode: m.licence_code ?? null,
        licenseLabel: m.licence ?? null,
        licenseUrl: m.licence_url ?? null,
      };
      liste.push(s);
      parId.set(id, s);
      cache.set(id, {
        t, moy: o.moy ?? null, raf: o.raf ?? null, dir: o.dir ?? null,
        pressure: o.pres ?? null, temp: o.temp ?? null,
      });
    }

    const age = infoclimatAgeMin(doc);
    if (age != null && age > INFOCLIMAT_OBS_MAX_AGE_MS / 60000) {
      infoclimatLastError = `latest.json périmé (${age.toFixed(0)} min) — `
        + `le poller du VPS ne tourne probablement plus`;
      console.error(`refreshInfoclimatObs: ${infoclimatLastError}`);
    } else if (!cache.size) {
      // Objet frais mais vide : le poller tourne et ne trouve rien. À
      // dire, parce que c'est indistinguable d'une panne côté client.
      infoclimatLastError = 'latest.json lu mais aucune station fraîche';
    } else {
      infoclimatLastError = null;
    }

    infoclimatStationsList = liste;
    infoclimatStationsById = parId;
    infoclimatObsCache = cache;
    infoclimatObsCacheFetchedAt = Date.now();
    console.log(`refreshInfoclimatObs: ${cache.size} stations `
      + `(objet de ${age == null ? '?' : age.toFixed(0)} min)`);
  } catch (e) {
    // On garde l'état précédent plutôt que de vider sur un incident
    // réseau — la péremption ci-dessus s'en chargera si ça dure.
    console.error('refreshInfoclimatObs error:', e.message);
    infoclimatLastError = `refreshObs: ${e.message}`;
  }
}

// Historique — relu sur NOTRE cadence et gardé en RAM, comme mfObsCache.
// ⚠️ NE PAS le relire à chaque requête client : 444 Ko transiteraient
//    pour afficher un seul graphe, ce qui déplacerait d'un cran le
//    gaspillage qu'on vient de retirer chez Infoclimat.
//
// Format COLONNAIRE côté objet (tableaux alignés sur `t`, une série
// absente = entièrement nulle), déplié ici une fois pour toutes en
// HistoryPoint[] — la même forme que Pioupiou/MF/AEMET, pour ne pas
// introduire une quatrième convention côté client.
async function refreshInfoclimatHistory() {
  try {
    const doc = await fetchInfoclimatObjet(INFOCLIMAT_HISTORY_URL);
    const src = doc?.historique || {};
    const next = new Map();
    for (const [id, serie] of Object.entries(src)) {
      const ts = serie?.t;
      if (!Array.isArray(ts) || !ts.length) continue;
      const col = nom => (Array.isArray(serie[nom]) ? serie[nom] : null);
      const moy = col('moy'), raf = col('raf');
      const dir = col('dir'), pres = col('pres');
      const pts = [];
      for (let i = 0; i < ts.length; i++) {
        // `min` toujours null : Infoclimat n'a pas de notion de minimum
        // glissant, contrairement à Pioupiou/MF où on le calcule.
        //
        // `max` = rafale NATIVE quand la station en mesure une, null
        // sinon — jamais 0, jamais une valeur reconstituée.
        //
        // ⚠️ CORRIGÉ LE 03/08/2026 : il était écrit ici que
        // `vent_rafales` était « null sur tout le réseau ». C'EST FAUX.
        // Relevé sur `history.json` en prod : **25 stations sur 865**
        // publient de vraies rafales, souvent 140 à 178 points sur 30 h,
        // avec des facteurs rafale/moyenne de 1,1 à 4,1. L'erreur venait
        // de l'échantillon de 8 stations sondé le matin même, et le
        // format colonnaire la rendait invisible : il OMET les séries
        // entièrement nulles, donc la clé `raf` disparaît chez les 840
        // autres au lieu d'apparaître pleine de null.
        // Le code ci-dessous était juste — c'est la seule raison pour
        // laquelle ces 25 stations n'ont jamais rien perdu.
        pts.push({
          t: ts[i] * 1000, min: null,
          avg: moy ? moy[i] ?? null : null,
          max: raf ? raf[i] ?? null : null,
          dir: dir ? dir[i] ?? null : null,
          pressure: pres ? pres[i] ?? null : null,
        });
      }
      next.set(id, pts);
    }
    if (next.size) {
      infoclimatHistory = next;
      infoclimatHistoryFetchedAt = Date.now();
    }
    const age = infoclimatAgeMin(doc);
    console.log(`refreshInfoclimatHistory: ${next.size} stations `
      + `(objet de ${age == null ? '?' : age.toFixed(0)} min)`);
  } catch (e) {
    console.error('refreshInfoclimatHistory error:', e.message);
    infoclimatLastError = `refreshHistory: ${e.message}`;
  }
}

async function refreshInfoclimatData() {
  await refreshInfoclimatObs();
}

// ── AEMET (Espagne) : stations vent+pression, ajout 22/07/2026 ─────
// Agence météorologique espagnole (AEMET OpenData), réseau OFFICIEL
// (~850 stations synoptiques/automatiques actives, vérifié en direct le
// 22/07 avec la vraie clé de Yann), même philosophie que Météo-France
// ci-dessus — contrairement aux stations amateur Infoclimat. Traitée
// EXACTEMENT comme MF (demande Yann : « on les traite exactement comme
// les autres ») : fondue dans `releves` (cf. pollAndNotify), donc
// surveillable/alertable au même titre qu'une balise Pioupiou ou une
// station MF — PAS le traitement affichage-seul retenu pour Infoclimat.
//
// Architecture de l'API, vérifiée EN DIRECT le 22/07/2026 (contrairement
// aux notes MF ci-dessus, jamais vérifiées faute de compte à l'époque) :
//  1. GET .../api/observacion/convencional/todas (header `api_key`)
//     renvoie une ENVELOPPE {estado, datos:<url>, metadatos:<url>}, PAS
//     les données elles-mêmes (contrairement à Pioupiou/MF/Infoclimat,
//     un seul call direct) — il faut un DEUXIÈME fetch sur l'URL `datos`
//     pour obtenir le tableau réel.
//  2. `datos` est un tableau PLAT (9716 lignes / 854 stations distinctes
//     le 22/07, PAS une ligne par station) : chaque station apparaît
//     PLUSIEURS fois, une ligne par heure, sur une fenêtre glissante
//     d'environ 12h (12 horodatages distincts observés, cadence horaire
//     pile). AEMET n'a donc PAS de vrai historique long terme accessible
//     par l'API — situation intermédiaire entre Pioupiou (archive
//     complète, propre à Pioupiou) et MF (aucun historique natif,
//     snapshot instantané) : d'où la même persistance Supabase que MF
//     (aemet_station_history), qui se remplit ICI d'un coup avec ~12h
//     dès le premier poll, au lieu de s'accumuler point par point comme
//     pour MF.
//  3. PIÈGE (vérifié en direct, réponse HTTP `Content-Type: text/plain;
//     charset=ISO-8859-15`) : la réponse `datos` n'est PAS en UTF-8 — les
//     noms de station accentués (ex. "VANDELLÓS", champ `ubi`) seraient
//     corrompus par un simple `r.json()`/`r.text()` de node-fetch (qui
//     suppose UTF-8 par défaut). Décodage explicite obligatoire via
//     TextDecoder('iso-8859-15') sur le buffer brut avant JSON.parse.
//  4. Champs utiles par ligne (vérifiés en direct) : idema (id station),
//     ubi (nom), lat/lon/alt, fint (horodatage ISO, UTC), vv (vitesse
//     moyenne, m/s), vmax (rafale, m/s), dv/dmax (direction moy/rafale,
//     degrés), pres (pression station, hPa), pres_nmar (pression ramenée
//     au niveau de la mer, hPa — même champ que pmer côté MF, utilisé
//     pour la même raison : cohérence avec un baromètre de balise en
//     fond de vallée/plaine). vv/vmax en m/s → ×3.6 pour rester dans les
//     unités natives de l'app (km/h), même conversion que MF (s.ff*3.6).
const AEMET_API_KEY = process.env.AEMET_API_KEY;
const AEMET_OBS_URL = 'https://opendata.aemet.es/opendata/api/observacion/convencional/todas';
// Donnée native horaire (12 points/heure vus en direct) : inutile de
// poller plus vite. Marge de 20 min (comme les 12 min MF) par prudence
// sur la fraîcheur de publication.
const AEMET_OBS_POLL_MS = 20 * 60 * 1000;
// Même politique de rétention différenciée que MF (mfPersistHistory) :
// vent 48h / pression-seule 12h — voir aemetPersistHistory.
const AEMET_HISTORY_RETENTION_H = 48;
const AEMET_PRESSURE_ONLY_RETENTION_H = 12;
// Garde-fraîcheur, même logique que MF_OBS_MAX_AGE_MS — mais la cadence
// AEMET étant horaire (pas 6 min), le seuil est proportionnellement plus
// large (90 min : une heure de cadence + marge), sinon une station serait
// systématiquement rejetée entre deux rafraîchissements normaux.
const AEMET_OBS_MAX_AGE_MS = 90 * 60 * 1000;

// ── Gardes-fraîcheur des trois réseaux ouverts à la surveillance le
//    07/08/2026 (lot « Surveiller ce site », cf. pollAndNotify) ────────
//
// Règle appliquée, la même que pour MF et AEMET : le seuil de péremption
// est une propriété de la SOURCE, dérivée de sa cadence de publication —
// jamais une constante unique du serveur. Un seuil trop serré ne protège
// de rien, il jette des relevés parfaitement valides et rend la balise
// muette au moment où on la surveille.
//
// METAR : cadence 30 min (cf. `cadenceMin` dans pressureStationsPayload),
// publication APRÈS l'heure d'observation. 90 min = 3 × cadence. C'est le
// prix à payer pour ce réseau, et il doit être DIT au pilote : un
// dépassement peut lui parvenir avec une demi-heure de retard.
const METAR_OBS_MAX_AGE_MS = 90 * 60 * 1000;
// SMN : cadence 10 min, réseau automatique moderne — même ordre de
// grandeur qu'une balise ordinaire.
const SMN_OBS_MAX_AGE_MS = 40 * 60 * 1000;
// Infoclimat : PAS de constante ici, `INFOCLIMAT_OBS_MAX_AGE_MS` existe
// déjà plus haut (90 min) et le cache est DÉJÀ refiltré à la lecture par
// refreshInfoclimatData — le garde-fraîcheur de pollAndNotify ne fait
// donc que rejouer une règle existante, il n'en invente pas une seconde.
// (Une deuxième déclaration du même nom a été écrite ici par erreur le
// 08/08 : `node --check` l'a attrapée. Deux seuils de péremption pour la
// même source, c'est exactement le genre de divergence silencieuse que
// la révision du lot 7 a supprimée côté seuils foehn.)

let aemetObsCache = new Map(); // idema -> {t, moy, raf, dir, dirRaf, pressure, lat, lon, alt, nom}
let aemetObsCacheFetchedAt = 0;
let aemetLastError = null; // même principe diagnostic que infoclimatLastError

async function fetchAemetJson(url) {
  const r = await fetch(url, AEMET_API_KEY ? { headers: { api_key: AEMET_API_KEY } } : undefined);
  const buf = await r.arrayBuffer();
  // ISO-8859-15 explicite (cf. note d'archi ci-dessus) — jamais r.text()/
  // r.json() qui décoderaient en UTF-8 et corrompraient les noms accentués.
  const text = new TextDecoder('iso-8859-15').decode(buf);
  if (!r.ok) {
    aemetLastError = `HTTP ${r.status} — ${text.slice(0, 300)}`;
    console.error(`fetchAemetJson: ${aemetLastError}`);
    return null;
  }
  try {
    return JSON.parse(text);
  } catch {
    aemetLastError = `réponse non-JSON — ${text.slice(0, 300)}`;
    console.error(`fetchAemetJson: ${aemetLastError}`);
    return null;
  }
}

async function refreshAemetObs() {
  if (!AEMET_API_KEY) return;
  try {
    const outer = await fetchAemetJson(AEMET_OBS_URL);
    if (!outer || outer.estado !== 200 || !outer.datos) {
      aemetLastError = `estado=${outer?.estado} — ${JSON.stringify(outer ?? {}).slice(0, 300)}`;
      console.error(`refreshAemetObs: ${aemetLastError}`);
      return;
    }
    const rows = await fetchAemetJson(outer.datos);
    if (!Array.isArray(rows)) return; // échec du 2e fetch : on garde l'ancien cache plutôt que de le vider

    // Regroupe par station, ne garde QUE la ligne la plus récente (fint
    // max) pour le cache "état courant" (aemetObsCache, consommé par
    // pollAndNotify et /aemet-stations) — mais TOUTES les lignes servent
    // à la persistance d'historique juste après (elles couvrent ~12h en
    // un seul poll, contrairement à MF qui n'a qu'un point par poll).
    const latestByStation = new Map();
    for (const row of rows) {
      const id = row?.idema;
      const t = row?.fint ? Date.parse(row.fint) : NaN;
      if (!id || !Number.isFinite(t)) continue;
      const prev = latestByStation.get(id);
      if (!prev || t > prev.t) latestByStation.set(id, { ...row, t });
    }
    const next = new Map();
    for (const [id, row] of latestByStation) {
      next.set(id, {
        t: row.t,
        moy: row.vv != null ? row.vv * 3.6 : null,
        raf: row.vmax != null ? row.vmax * 3.6 : null,
        dir: row.dv ?? null,
        dirRaf: row.dmax ?? null,
        pressure: row.pres_nmar ?? null,
        lat: row.lat ?? null, lon: row.lon ?? null, alt: row.alt ?? null,
        nom: row.ubi || id,
      });
    }
    if (next.size) { aemetObsCache = next; aemetObsCacheFetchedAt = Date.now(); aemetLastError = null; }

    // Persistance Supabase de LA FENÊTRE ENTIÈRE (jusqu'à 12h/station en
    // un seul poll, cf. note d'archi) — pas juste le point le plus récent
    // comme mfHistoryRows dans pollAndNotify. Fire-and-forget, même
    // politique que mfPersistHistory.
    const historyRows = [];
    for (const row of rows) {
      const id = row?.idema;
      const t = row?.fint ? Date.parse(row.fint) : NaN;
      if (!id || !Number.isFinite(t)) continue;
      const moy = row.vv != null ? row.vv * 3.6 : null;
      const pressure = row.pres_nmar ?? null;
      if (moy == null && pressure == null) continue; // rien d'exploitable sur cette ligne
      historyRows.push({
        station_id: id, t, moy,
        raf: row.vmax != null ? row.vmax * 3.6 : null,
        dir: row.dv ?? null, pressure,
      });
    }
    aemetPersistHistory(historyRows);
  } catch (e) {
    console.error('refreshAemetObs error:', e.message);
    aemetLastError = `refreshObs: ${e.message}`;
  }
}

// Miroir de mfPersistHistory (même table shape, même politique de purge
// différenciée vent 48h / pression-seule 12h) — voir
// supabase_step24_aemet_station_history.sql.
function aemetPersistHistory(rows) {
  if (!rows.length) return;
  sbUpsert('aemet_station_history', rows, 'station_id,t')
    .catch(e => console.error('aemetPersistHistory upsert error:', e.message));
  const windCutoff = Date.now() - AEMET_HISTORY_RETENTION_H * 3600 * 1000;
  sbDelete('aemet_station_history', `moy=not.is.null&t=lt.${windCutoff}`)
    .catch(e => console.error('aemetPersistHistory purge (vent) error:', e.message));
  const pressureOnlyCutoff = Date.now() - AEMET_PRESSURE_ONLY_RETENTION_H * 3600 * 1000;
  sbDelete('aemet_station_history', `moy=is.null&t=lt.${pressureOnlyCutoff}`)
    .catch(e => console.error('aemetPersistHistory purge (pression seule) error:', e.message));
}

// Miroir de hydrateBeaconHistoryFromSupabase (MF) — hydrate le buffer RAM
// beaconHistory depuis aemet_station_history au démarrage, même raison :
// sans ça, fwWindowMinFf/fwRecordHistory repartiraient de zéro à chaque
// redémarrage Render alors que l'historique existe déjà en base.
async function hydrateAemetHistoryFromSupabase() {
  try {
    const cutoff = Date.now() - FW_HISTORY_MAX_AGE_MS;
    const rows = await sbGet(
      'aemet_station_history',
      `t=gte.${cutoff}&select=station_id,t,moy,raf,dir,pressure&order=t.asc&limit=200000`
    );
    if (!Array.isArray(rows) || !rows.length) return;
    const stationIds = new Set();
    for (const r of rows) {
      fwRecordHistory(String(r.station_id), { t: r.t, moy: r.moy, raf: r.raf ?? null, min: null, dir: r.dir, pressure: r.pressure });
      stationIds.add(r.station_id);
    }
    console.log(`🔄 beaconHistory hydraté depuis aemet_station_history : ${rows.length} échantillons, ${stationIds.size} stations`);
  } catch (e) {
    console.error('hydrateAemetHistoryFromSupabase error:', e.message);
  }
}

async function refreshAemetData() {
  if (!AEMET_API_KEY) return;
  await refreshAemetObs();
}

// ════════════════════════════════════════════════════════════════════
// WINDS.MOBI — agrégateur multi-réseaux (07/08/2026)
// ════════════════════════════════════════════════════════════════════
// Pourquoi un agrégateur alors que le projet a toujours branché ses
// sources en direct : parce que les trois réseaux visés (Holfuy, Adison,
// Sencrop) sont fermés. Mesuré le 07/08 — Holfuy répond ` No access`
// sans mot de passe, Adison n'est pas un réseau mais un bureau d'études
// qui fabrique les balises FFVL, Sencrop est un partenariat commercial
// agricole. Et data.ffvl.fr réclame toujours une clé, y compris sur les
// deux ressources encore publiées comme open data sur data.gouv.fr.
// Voir PWA/web/RESEAU_WINDSMOBI.md pour le détail des appels, et
// tools/sonde_windsmobi.mjs pour rejouer la mesure.
//
// winds.mobi est un projet open source (AGPL, github.com/winds-mobi)
// qui collecte 23 réseaux et les republie sous un modèle unique, sans
// clé. Il a SA propre clé FFVL : la donnée fédérale passe par lui.
//
// ⚠️ SES CONDITIONS D'USAGE SONT CONTRAIGNANTES, pas décoratives —
// « Any IP or service that doesn't respect these rules will be
// blacklisted without any notice » :
//   1. user-agent identifiant obligatoire  → WINDSMOBI_UA
//   2. aucune monétisation                 → conforme (ni pub ni abo)
//   3. ne pas surcharger, grouper les appels → cf. les deux cadences
// C'est aussi pourquoi TOUT passe par le serveur : si chaque PWA
// appelait winds.mobi, le nombre d'appels suivrait le nombre de pilotes
// connectés au lieu de rester constant.
//
// ── Ce qu'on NE prend PAS, et pourquoi ─────────────────────────────
//  · `pioupiou` : on l'a déjà en direct, et EN PLUS FRAIS — âge médian
//    mesuré 12,1 min chez winds.mobi contre le poll 5 min d'API_ALL.
//    Sur une alerte en vol la latence est le sujet ; l'agrégateur vient
//    en plus, jamais à la place.
//  · `metar` : l'app a déjà son espace `metar:` (43 stations) dans le
//    référentiel de pression, et le grand commentaire de
//    pressureStationsPayload tranche que ce ne sont PAS des balises.
//    Un second espace d'ids METAR fabriquerait des doublons invisibles.
//
// ── Deux cadences, calées sur la fraîcheur MESURÉE (07/08) ─────────
// Âge médian du dernier relevé, par réseau : holfuy 2,6 min · ffvl
// 6,2 min · slf et meteoswiss 13,3 min. Poller SLF toutes les 5 min
// serait donc 2,5 appels sur 3 pour rien — exactement ce que le point 3
// des CGU demande d'éviter. D'où deux groupes : les réseaux de balises
// de déco au rythme des alertes, le reste au rythme de la donnée.
const WINDSMOBI_API = 'https://winds.mobi/api/2';
const WINDSMOBI_UA = 'balise-watch.app (biozarb@gmail.com)';
// Réseaux au rythme des alertes : ce sont les balises de décollage.
const WINDSMOBI_PROVIDERS_FAST = ['holfuy', 'ffvl'];
// Réseaux d'appoint — stations fixes, cadence source ≥ 10 min.
const WINDSMOBI_PROVIDERS_SLOW = [
  'slf', 'meteoswiss', 'windspots', 'aletsch', 'windball', 'windline',
  'iweathar', 'pgsonda', 'gxaircom', 'pdcs', 'yvbeach', 'thunerwetter',
  'kachelmannwetter', 'wunderground',
];
const WINDSMOBI_POLL_FAST_MS = 5 * 60 * 1000;
const WINDSMOBI_POLL_SLOW_MS = 15 * 60 * 1000;
// France + pays limitrophes — le principe de couverture géographique du
// ROADMAP, pas un cadrage Maurienne. Filtré ICI et pas côté client :
// une balise hors boîte ne doit jamais entrer dans `releves`.
const WINDSMOBI_BOX = { latMin: 41.2, latMax: 51.6, lonMin: -5.5, lonMax: 10.2 };
// Garde-fraîcheur : le plus lent des réseaux retenus publie toutes les
// ~13 min, 60 min laisse donc passer quatre cycles manqués avant de
// déclarer une balise muette. Même politique que MF/AEMET — le seuil
// est une propriété de la source, jamais une constante du serveur.
const WINDSMOBI_OBS_MAX_AGE_MS = 60 * 60 * 1000;
// Rayon de dédoublonnage : la valeur déjà tranchée pour la FFVL
// (PROMPT_REPRISE.md, « Arbitrages tranchés par défaut »).
const WINDSMOBI_DEDUP_M = 180;
// Profondeur d'historique servie par winds.mobi, mesurée le 07/08 :
// 1 336 points sur 168 h pour une station Holfuy. C'est ce qui permet de
// NE PAS créer de table Supabase pour cette source, contrairement à MF
// et AEMET dont l'API ne rend que l'instant présent.
const WINDSMOBI_HISTORY_MAX_H = 168;

let windsmobiObsCache = new Map(); // id -> {t, moy, raf, dir, lat, lon, alt, nom, reseau, reseauNom, url}
let windsmobiFetchedAt = 0;
let windsmobiLastError = null;
let windsmobiDedupCount = 0; // diagnostic : combien de balises écartées comme doublons
// Coordonnées Pioupiou du dernier poll, alimentées par pollAndNotify.
// Volontairement PAS un appel réseau à nous : pollAndNotify a déjà la
// liste complète en main à chaque cycle, la redemander serait payer deux
// fois la même donnée.
let pioupiouCoords = [];

// Index géographique de TOUT ce que l'app connaît déjà, toutes sources
// confondues. Reconstruit à chaque rafraîchissement : les caches sources
// bougent (une station MF muette sort de mfObsCache), et un index figé
// ferait réapparaître un doublon au premier trou de donnée.
function windsmobiKnownGrid() {
  const grid = new Map(); // "lat0.1,lon0.1" -> [[lat, lon]...]
  const add = (lat, lon) => {
    if (lat == null || lon == null || !Number.isFinite(lat) || !Number.isFinite(lon)) return;
    const key = `${Math.round(lat * 10)},${Math.round(lon * 10)}`;
    let cell = grid.get(key);
    if (!cell) { cell = []; grid.set(key, cell); }
    cell.push([lat, lon]);
  };
  for (const [lat, lon] of pioupiouCoords) add(lat, lon);
  for (const s of mfStationsList) add(s.lat, s.lon);
  for (const o of aemetObsCache.values()) add(o.lat, o.lon);
  for (const m of infoclimatStationsById.values()) add(m.lat, m.lon);
  for (const o of metarObsCache.values()) add(o.lat, o.lon);
  for (const o of smnObsCache.values()) add(o.lat, o.lon);
  return grid;
}

// Une cellule de 0,1° fait ~11 km de côté : le rayon cherché (180 m) est
// très inférieur, donc regarder la cellule et ses 8 voisines suffit et
// aucun candidat ne peut échapper au test.
function windsmobiIsDuplicate(grid, lat, lon) {
  const clat = Math.round(lat * 10), clon = Math.round(lon * 10);
  for (let dlat = -1; dlat <= 1; dlat++) {
    for (let dlon = -1; dlon <= 1; dlon++) {
      const cell = grid.get(`${clat + dlat},${clon + dlon}`);
      if (!cell) continue;
      for (const [klat, klon] of cell) {
        if (fwHaversineKm(lat, lon, klat, klon) * 1000 < WINDSMOBI_DEDUP_M) return true;
      }
    }
  }
  return false;
}

async function fetchWindsmobi(path) {
  const r = await fetch(`${WINDSMOBI_API}${path}`, { headers: { 'user-agent': WINDSMOBI_UA } });
  if (!r.ok) {
    // 403/429 = on est peut-être en train de se faire blacklister : le
    // dire fort dans /diag plutôt que de le noyer dans un log.
    windsmobiLastError = `HTTP ${r.status} sur ${path}`;
    console.error(`fetchWindsmobi: ${windsmobiLastError}`);
    return null;
  }
  return r.json();
}

// ⚠️ `pressure` n'est JAMAIS repris de winds.mobi, décision explicite.
// La convention de réduction (QFE/QNH/QFF) diffère d'un réseau source à
// l'autre et l'API ne la dit pas — le champ `pres` n'est même présent
// que sur une minorité de relevés (vérifié le 07/08 : les stations
// sondées n'exposaient que w-avg/w-max/w-dir). Mélanger deux conventions
// sur une même série est exactement le piège FIA-3 corrigé côté foehn.
// Aucune pression vaut mieux qu'une pression qui fabrique une fausse
// tendance : les signaux de chute de pression ignorent proprement null.
async function refreshWindsmobiProviders(providers) {
  const grid = windsmobiKnownGrid();
  if (!grid.size) {
    // Aucun référentiel connu = on ne saurait pas dédoublonner, et
    // publier sans dédup mettrait ~285 doublons FFVL sur la carte. On
    // garde le cache précédent (vide au premier boot) et on repassera.
    console.log('refreshWindsmobi: référentiel de dédup vide, publication reportée');
    return;
  }
  let dropped = 0, kept = 0;
  for (const provider of providers) {
    try {
      const rows = await fetchWindsmobi(`/stations/?provider=${encodeURIComponent(provider)}&limit=0`);
      if (!Array.isArray(rows)) continue; // échec : on garde l'ancien cache de CE réseau

      // ⚠️ ÉCRITURE EN PLACE, RÉSEAU PAR RÉSEAU — et surtout PAS un
      // `const next = new Map(cache)` en tête de fonction suivi d'un
      // `cache = next` à la fin. C'est la première version, et elle
      // perdait des balises en production dès le premier déploiement
      // (07/08, vu sur /windsmobi-stations : 384 balises, sans Holfuy ni
      // FFVL).
      //
      // La raison : les deux cadences appellent CETTE MÊME fonction, et
      // le groupe lent (14 appels) finit après le rapide (2 appels).
      // Chacun ayant pris sa photo du cache au départ, le dernier à
      // écrire écrasait le travail de l'autre — donc le lent effaçait
      // Holfuy et la FFVL, c'est-à-dire exactement les balises de déco.
      //
      // Le piège est qu'il se répare seul au cycle suivant : cinq
      // minutes plus tard le rapide les remettait, et une vérification
      // faite au mauvais moment aurait conclu que tout allait bien. La
      // perte revenait toutes les 15 min, quand les deux boucles
      // retombent en phase.
      //
      // Ici la purge et la réécriture d'un réseau sont dans le MÊME bloc
      // synchrone (aucun `await` entre les deux) : Node ne peut pas
      // intercaler l'autre boucle au milieu, et chaque réseau ne touche
      // que ses propres entrées. Ajouter un `await` entre ces deux
      // boucles rouvrirait la fenêtre.
      for (const [id, o] of windsmobiObsCache) if (o.reseau === provider) windsmobiObsCache.delete(id);
      for (const s of rows) {
        const coords = s?.loc?.coordinates;
        if (!Array.isArray(coords) || coords.length < 2) continue;
        const lon = coords[0], lat = coords[1];
        if (lat < WINDSMOBI_BOX.latMin || lat > WINDSMOBI_BOX.latMax) continue;
        if (lon < WINDSMOBI_BOX.lonMin || lon > WINDSMOBI_BOX.lonMax) continue;
        if (s.status === 'red' || s.status === 'hidden') continue;
        const last = s.last;
        if (!last || !Number.isFinite(last._id)) continue;
        if (last['w-avg'] == null) continue; // station sans vent : rien à surveiller
        if (windsmobiIsDuplicate(grid, lat, lon)) { dropped++; continue; }
        windsmobiObsCache.set(s._id, {
          t: last._id * 1000, // winds.mobi horodate en SECONDES
          moy: last['w-avg'], raf: last['w-max'] ?? null, dir: last['w-dir'] ?? null,
          lat, lon, alt: s.alt ?? null,
          nom: (s.name || s.short || s._id).trim(),
          reseau: provider,
          reseauNom: s['pv-name'] || provider,
          url: s.url?.default ?? null,
        });
        kept++;
      }
    } catch (e) {
      console.error(`refreshWindsmobi(${provider}) error:`, e.message);
      windsmobiLastError = `${provider}: ${e.message}`;
    }
  }
  windsmobiFetchedAt = Date.now();
  windsmobiDedupCount = dropped;
  if (kept) windsmobiLastError = null;
  // Le total du cache est journalisé EN PLUS du compte de ce groupe :
  // c'est lui qui aurait rendu la perte visible dans les logs Render dès
  // le premier boot (« 384 » là où on attend ~884).
  console.log(`refreshWindsmobi: ${kept} balises retenues, ${dropped} doublons écartés (${providers.join(', ')}) — cache total ${windsmobiObsCache.size}`);
}

const refreshWindsmobiFast = () => refreshWindsmobiProviders(WINDSMOBI_PROVIDERS_FAST);
const refreshWindsmobiSlow = () => refreshWindsmobiProviders(WINDSMOBI_PROVIDERS_SLOW);

// ════════════════════════════════════════════════════════════════════
// BALISES DE PRESSION — METAR + MeteoSuisse (foehn v2, lot 0, 03/08/2026)
// ════════════════════════════════════════════════════════════════════
// Cf. PWA/web/PROMPT_REPRISE_FOEHN_V2.md §2. Contexte en une phrase :
// le module foehn n'avait AUCUNE balise de pression hors de France, donc
// aucun de ses 8 axes présets ne pouvait afficher de courbe réelle —
// l'extrémité italienne ou espagnole n'était jamais appariée.
//
// Enquête du 03/08/2026, vérifiée par API et non supposée : les réseaux
// régionaux italiens NE PUBLIENT PAS de pression. ARPA Lombardia expose
// exactement 8 types de capteurs (neige, vent, hydrométrie, pluie,
// radiation, température, humidité, direction) et aucun baromètre ;
// l'API météo de la province de Bolzano expose LT/N/Q/SD/W/WR, idem ;
// ARPA Piemonte demande une inscription par e-mail pour le temps réel.
// Le METAR est donc la SEULE source libre de pression réduite au niveau
// de la mer côté italien. Écrire ce constat ici évite de refaire
// l'enquête dans six mois.
//
// ⚠️ CES STATIONS NE SONT PAS DES BALISES. Décision explicite de Yann :
// elles alimentent les phénomènes de gradient, point. Pas de marqueur
// carte, pas de favori, pas de surveillance, pas de fusion dans
// `releves`. Un METAR est une donnée d'aérodrome (10 m, piste dégagée),
// peu représentative d'un site de vol — et 45 marqueurs d'aéroports en
// plus sur la carte sans demande pilote seraient une régression.
// C'est pourquoi la route dédiée /pressure-stations n'a PAS la forme de
// /meteofrance-stations : lui donner la même forme inviterait
// précisément à les traiter comme des balises.
//
// ⚠️ AUCUNE CONVERSION N'EST FAITE ICI. Le serveur publie la valeur
// BRUTE, sa convention de réduction, la température et l'altitude ; la
// conversion QNH → QFF vit dans PWA/web/src/lib/pressure.ts, vérifiée
// par scripts/verify-pressure.mjs. Une formule barométrique dupliquée
// dans deux dépôts, c'est deux sources de vérité dont une seule sera
// corrigée le jour où il y aura un bug. Quand la veille serveur en aura
// besoin (lot 7), on extraira le module — on ne le recopiera pas.

// ── METAR (aviationweather.gov / NOAA) ────────────────────────────
// API publique, SANS CLÉ, mondiale, 100 requêtes/minute. Un seul appel
// ramène toutes les ancres. Champs utiles (vérifiés en direct le
// 03/08) : icaoId, obsTime (epoch s), lat, lon, elev (m), temp (°C),
// dewp, wdir, wspd (nœuds), altim (QNH en hPa, ARRONDI À L'ENTIER),
// name.
//
// ⚠️ `altim` est du QNH — réduction en atmosphère STANDARD — alors que
// Météo-France (`pmer`), AEMET (`pres_nmar`) et MeteoSuisse
// (`pp0qffs0`) publient du QFF, réduit avec la température réelle. Les
// mélanger dans un même Δ fabrique un biais corrélé au foehn mesuré :
// 2,4 hPa entre deux stations de même altitude séparées par 15 K. D'où
// le champ `reduction` transmis au client, et `tempC` sans lequel la
// conversion est impossible (le client refuse alors le point plutôt que
// de mentir).
const METAR_URL = 'https://aviationweather.gov/api/data/metar';
// Cadence : les METAR sortent à :20 et :50 sur les grands terrains, à
// l'heure ronde ailleurs. 20 min garantit de ne jamais rater plus d'un
// cycle — 72 appels/jour sur une limite de 100/MINUTE, très large.
const METAR_POLL_MS = 20 * 60 * 1000;
// Profondeur d'historique demandée en régime établi (recouvrement large
// pour absorber un poll manqué) et au démarrage.
const METAR_POLL_HOURS = 3;
const METAR_BOOT_HOURS = 30;
// Rétention du buffer RAM. Pas de table Supabase, CONTRAIREMENT à MF et
// AEMET : l'API METAR sert elle-même son propre historique via `hours`,
// donc un redémarrage Render se rattrape tout seul au premier poll.
// C'est une vraie différence de nature — MF n'expose qu'un instantané,
// d'où sa table de persistance ; ici la persistance serait un doublon.
// (Reste vrai après le 04/08/2026, MAIS à la condition expresse du
// découpage en lots ci-dessous — sans lui le rattrapage ne rattrapait
// rien. Voir METAR_ROW_BUDGET.)
const METAR_RETENTION_MS = 36 * 3600 * 1000;

// ── Plafond de la réponse aviationweather, mesuré le 04/08/2026 ──────
// ⚠️ L'API PLAFONNE le nombre total d'enregistrements d'une réponse
// (~400) et, quand le plafond est atteint, elle rabote par le TEMPS.
// Elle ne renvoie NI erreur NI avertissement : elle renvoie simplement
// moins d'heures que demandé. C'est le pire mode de défaillance
// possible pour cet outil — la courbe reste plausible, juste courte.
//
// Mesures en direct, toutes à `hours=30`, le 04/08/2026 à 05:41 UTC :
//    2 ancres → 29,7 h  (60 points/station)  ✅
//    6 ancres → 29,7 h  (~60 points/station) ✅
//   20 ancres → 11,4 h  (~23 points/station) ❌
//   43 ancres →  5,5 h  (~10 points/station) ❌
//
// C'est LA cause du buffer de ~5 h constaté en prod le 04/08 sur les
// huit stations testées, et l'explication est structurelle : demander
// les 43 ancres en une requête ne POUVAIT PAS rendre 30 h. Le poll de
// démarrage n'a jamais échoué — il n'avait aucune chance d'aboutir.
// (L'hypothèse d'un redémarrage Render dont le poll de boot aurait
// échoué est donc écartée : elle n'est pas nécessaire.)
//
// La parade : borner `ids × heures × 2` (≈ 2 relevés par heure sur un
// terrain dense) à ce budget, et découper en autant de requêtes
// séquentielles qu'il faut. Conséquences voulues :
//   - à hours=3 (régime établi), 3×2=6 → 50 ancres par requête : les 43
//     passent en UNE requête, la cadence de croisière ne change pas ;
//   - à hours=30 (démarrage), 30×2=60 → 5 ancres par requête, soit 9
//     requêtes espacées de 300 ms. Sur une limite de 100 requêtes PAR
//     MINUTE, c'est négligeable.
// Budget volontairement sous le plafond mesuré (300 < ~400) : on ne
// veut pas se retrouver pile à la limite le jour où un terrain publie
// des SPECI en rafale.
const METAR_ROW_BUDGET = 300;
const METAR_BATCH_DELAY_MS = 300;
// Passe profonde périodique. Le découpage ci-dessus corrige la cause ;
// ceci est la ceinture : si un lot échoue au démarrage, si Render
// redémarre, ou si l'API rebaisse son plafond sans prévenir, le buffer
// se re-remplit tout seul en moins de 6 h au lieu de rester court
// jusqu'au prochain déploiement. 9 requêtes toutes les 6 h.
const METAR_DEEP_MS = 6 * 3600 * 1000;

// Ancres METAR curées. Volontairement une LISTE EXPLICITE plutôt qu'un
// bbox : sur un outil de sécurité on veut savoir exactement ce qu'on
// ingère, et un bbox ramènerait des dizaines de terrains sans rapport.
// Un identifiant inconnu ou muet ne casse rien — il n'apparaît
// simplement pas dans la réponse.
// Priorité aux zones SANS meilleure source : l'Italie n'a que ça, la
// France a déjà Météo-France (QFF, 6 min) et l'Espagne AEMET — les
// quelques terrains français/espagnols ci-dessous servent de recoupement
// et de repli.
const METAR_ANCHORS = [
  // Italie — plaine du Pô, Val d'Aoste, Piémont, Dolomites.
  'LIMW', 'LIMF', 'LIMZ', 'LIMC', 'LIML', 'LIME', 'LIMN', 'LIPO',
  'LIPX', 'LIPB', 'LIMJ', 'LIMP', 'LIPE', 'LIQW',
  // Suisse — doublées par MeteoSuisse (meilleur), gardées en repli.
  'LSGG', 'LSGS', 'LSZA', 'LSZL', 'LSZH', 'LSZB', 'LSMP', 'LSZR',
  // Autriche — Brenner (Innsbruck) et arc oriental.
  'LOWI', 'LOWS', 'LOWK',
  // France — recoupement, et couloirs de plaine (Rhône, Lauragais).
  'LFLB', 'LFLP', 'LFLS', 'LFLL', 'LFLU', 'LFML', 'LFMN', 'LFBO',
  'LFMP', 'LFMT', 'LFBP', 'LFSB',
  // Espagne — versant sud pyrénéen (doublé par AEMET).
  'LEZG', 'LEDA', 'LEHC', 'LEPP', 'LEGE',
  // Allemagne — lac de Constance, pour la bise.
  'EDNY',
];

let metarObsCache = new Map();   // icaoId -> dernier relevé
let metarHistory = new Map();    // icaoId -> [{t, qnh, tempC}] croissant
let metarFetchedAt = 0;
let metarLastError = null;
let metarDeepDoneAt = 0;      // dernière passe profonde terminée

// Insère un point dans un buffer d'historique trié par t, sans doublon
// (l'API renvoie des fenêtres qui se recouvrent d'un poll à l'autre) et
// en élaguant au-delà de la rétention. Partagé METAR ↔ MeteoSuisse.
function pressureHistoryPush(map, id, point, retentionMs) {
  let arr = map.get(id);
  if (!arr) { arr = []; map.set(id, arr); }
  // Cas courant : le point est le plus récent → push direct.
  const last = arr[arr.length - 1];
  if (!last || point.t > last.t) arr.push(point);
  else {
    const i = arr.findIndex(p => p.t >= point.t);
    if (i >= 0 && arr[i].t === point.t) { arr[i] = point; }
    else if (i < 0) arr.push(point);
    else arr.splice(i, 0, point);
  }
  const cutoff = Date.now() - retentionMs;
  while (arr.length && arr[0].t < cutoff) arr.shift();
}

/**
 * Étendue d'un buffer d'historique, en heures. null si l'ancre est
 * absente ou n'a qu'un point — un point unique n'a pas d'étendue, et
 * renvoyer 0 le ferait passer pour un buffer vide dans les moyennes.
 * Sert au log de démarrage et à /pressure-diag ; c'est cette grandeur,
 * et elle seule, qui aurait montré le problème du 04/08 en un coup
 * d'œil au lieu de huit requêtes à la main.
 */
function pressureHistorySpanH(map, id) {
  const arr = map.get(id);
  if (!arr || arr.length < 2) return null;
  return (arr[arr.length - 1].t - arr[0].t) / 3600000;
}

/** Découpe les ancres en lots tenant dans METAR_ROW_BUDGET. */
function metarBatches(anchors, hours) {
  const perRequest = Math.max(1, Math.floor(METAR_ROW_BUDGET / Math.max(1, hours * 2)));
  if (perRequest >= anchors.length) return [anchors];
  const out = [];
  for (let i = 0; i < anchors.length; i += perRequest) out.push(anchors.slice(i, i + perRequest));
  return out;
}

const metarSleep = ms => new Promise(res => setTimeout(res, ms));

/**
 * UN lot. Renvoie true si le lot a rendu au moins un relevé exploitable.
 * N'écrit ni metarFetchedAt ni metarLastError : c'est l'appelant qui
 * décide, une fois tous les lots passés — sinon un dernier lot vide
 * effacerait la réussite des précédents.
 */
async function refreshMetarBatch(ids, hours) {
  try {
    const url = `${METAR_URL}?ids=${ids.join(',')}&format=json&hours=${hours}`;
    const r = await fetch(url);
    if (!r.ok) {
      metarLastError = `HTTP ${r.status}`;
      console.error(`refreshMetarObs: ${metarLastError}`);
      return false;
    }
    const rows = await r.json();
    // Échec de parsing ou réponse vide : on GARDE l'ancien cache plutôt
    // que de le vider (même politique que refreshAemetObs).
    if (!Array.isArray(rows) || !rows.length) return false;

    const latest = new Map();
    for (const row of rows) {
      const id = row?.icaoId;
      const t = Number(row?.obsTime) * 1000;
      if (!id || !Number.isFinite(t)) continue;
      // altim = QNH. Sans lui la ligne n'a aucun intérêt ici.
      if (row.altim == null) continue;
      const tempC = row.temp != null ? Number(row.temp) : null;
      // `p` + `reduction`, même forme que l'historique SwissMetNet depuis
      // que celui-ci peut être en repli QNH : deux clés différentes pour
      // la même grandeur obligeraient chaque lecteur à savoir de quelle
      // source il vient avant de savoir où regarder.
      pressureHistoryPush(metarHistory, id, { t, p: Number(row.altim), reduction: 'qnh', tempC }, METAR_RETENTION_MS);
      const prev = latest.get(id);
      if (!prev || t > prev.t) {
        latest.set(id, {
          t,
          qnh: Number(row.altim),
          tempC,
          lat: row.lat ?? null, lon: row.lon ?? null, alt: row.elev ?? null,
          nom: row.name || id,
          // Vent — nœuds → km/h, comme MF fait m/s → km/h.
          dir: typeof row.wdir === 'number' ? row.wdir : null,
          moy: row.wspd != null ? Number(row.wspd) * 1.852 : null,
          // Rafale (lot balises, 04/08/2026). `wgst` est DÉJÀ dans la
          // réponse qu'on télécharge : aucun appel réseau ajouté, aucune
          // clé. Absent la plupart du temps — un METAR ne publie la
          // rafale que si elle dépasse le vent moyen de 10 kt, c'est la
          // règle de codage OACI. `null` veut donc dire « pas de rafale
          // significative », PAS « pas mesurée » : à ne pas afficher
          // comme une donnée manquante côté client.
          raf: row.wgst != null ? Number(row.wgst) * 1.852 : null,
        });
      }
    }
    if (!latest.size) return false;
    // Fusion et non remplacement : un terrain fermé la nuit disparaît
    // de la réponse, son dernier relevé connu doit survivre (le client
    // décide de sa fraîcheur, cf. `t` transmis).
    for (const [id, obs] of latest) metarObsCache.set(id, obs);
    return true;
  } catch (e) {
    metarLastError = `refreshMetarObs: ${e.message}`;
    console.error(metarLastError);
    return false;
  }
}

/**
 * Poll METAR complet. `hours` pilote tout : la profondeur demandée ET,
 * mécaniquement, le nombre d'ancres par requête (cf. METAR_ROW_BUDGET).
 * Les lots sont SÉQUENTIELS et espacés — pas de Promise.all : neuf
 * requêtes simultanées sur une API publique gratuite est exactement le
 * genre de chose qui fait blacklister une IP Render partagée.
 */
async function refreshMetarObs(hours = METAR_POLL_HOURS) {
  const batches = metarBatches(METAR_ANCHORS, hours);
  let any = false;
  for (let i = 0; i < batches.length; i++) {
    if (i) await metarSleep(METAR_BATCH_DELAY_MS);
    if (await refreshMetarBatch(batches[i], hours)) any = true;
  }
  if (any) {
    metarFetchedAt = Date.now();
    metarLastError = null;
  }
  return any;
}

/**
 * Passe profonde : recharge METAR_BOOT_HOURS pour toutes les ancres.
 * Appelée au démarrage puis toutes les METAR_DEEP_MS. Journalise la
 * profondeur RÉELLEMENT obtenue — c'est le seul moyen de voir depuis
 * les logs Render que le plafond de l'API n'a pas rebougé.
 */
async function refreshMetarDeep() {
  const t0 = Date.now();
  await refreshMetarObs(METAR_BOOT_HOURS);
  metarDeepDoneAt = Date.now();
  const spans = METAR_ANCHORS
    .map(id => pressureHistorySpanH(metarHistory, id))
    .filter(h => h != null);
  const profondes = spans.filter(h => h >= METAR_BOOT_HOURS / 2).length;
  const mediane = spans.length ? spans.slice().sort((a, b) => a - b)[Math.floor(spans.length / 2)] : 0;
  console.log(
    `🌡️  METAR passe profonde (${metarBatches(METAR_ANCHORS, METAR_BOOT_HOURS).length} lots, ` +
    `${((Date.now() - t0) / 1000).toFixed(1)} s) : ${spans.length}/${METAR_ANCHORS.length} ancres alimentées, ` +
    `étendue médiane ${mediane.toFixed(1)} h, ${profondes} au-delà de ${(METAR_BOOT_HOURS / 2).toFixed(0)} h`
  );
  // Une médiane courte alors qu'on a demandé 30 h = le plafond de
  // l'API a rebougé. On le DIT, plutôt que de laisser une courbe
  // tronquée passer pour une courbe complète (cf. METAR_ROW_BUDGET).
  if (spans.length && mediane < METAR_BOOT_HOURS / 3) {
    console.warn(
      `⚠️  METAR : étendue médiane ${mediane.toFixed(1)} h pour ${METAR_BOOT_HOURS} h demandées. ` +
      `Le plafond d'enregistrements de l'API a probablement baissé — réduire METAR_ROW_BUDGET.`
    );
  }
}

// ── MeteoSuisse — SwissMetNet (OGD, data.geo.admin.ch) ─────────────
// ~160 stations automatiques, SANS CLÉ, cadence 10 MINUTES, pression
// incluse. Nettement meilleur que le METAR côté suisse : QFF natif au
// dixième de hPa, contre du QNH arrondi à l'entier.
//
// ⚠️ IL N'Y A PAS DE FICHIER « TOUTES STATIONS ». Vérifié le 03/08 :
// l'API STAC de la collection ch.meteoschweiz.ogd-smn ne liste que des
// assets PAR STATION (ogd-smn_<abbr>_t_now.csv), et l'URL agrégée que
// laissait espérer la documentation renvoie du vide. D'où une liste
// d'ancres curée et un fetch par station — surtout pas les 160.
//
// Format du CSV (vérifié en direct sur LUG) : séparateur `;`, décimale
// `.`, encodage Windows-1252, horodatage `dd.mm.yyyy HH:MM` en UTC, une
// ligne toutes les 10 min.
//
// ⚠️ CORRECTION DU 04/08/2026 — ce commentaire disait « depuis hier
// 12 UTC ». C'est FAUX, et ça a fondé une décision d'architecture
// entière (voir /pressure-history). Le fichier `_t_now.csv` couvre
// LE JOUR UTC COURANT, un point c'est tout. Vérifié en direct sur GVE
// le 04/08 à 05:41 UTC : première ligne `04.08.2026 00:00`, dernière
// `05:20`, 33 lignes, 5,3 h. Sa profondeur n'est donc pas une propriété
// du fichier mais l'heure qu'il est : 24 h juste avant minuit UTC,
// ZÉRO juste après. Le jour de la veille part dans `_t_recent.csv`
// (rotation quotidienne vers 02:28 UTC), qui couvre l'année entière au
// pas de 10 min — beaucoup trop gros pour un rattrapage au démarrage.
// D'où la persistance Supabase ajoutée plus bas : contrairement au
// METAR, MeteoSuisse ne peut PAS resservir notre fenêtre de 36 h.
// Colonnes lues par NOM
// (jamais par position — l'ordre peut changer sans préavis) :
//   station_abbr, reference_timestamp,
//   tre200s0  température 2 m (°C)
//   prestas0  pression station (hPa)
//   pp0qnhs0  QNH (hPa)
//   pp0qffs0  QFF (hPa)          ← c'est celle qu'on utilise
//   fkl010z0  vent moyen 10 min (m/s)
//   dkl010z0  direction (°)
//
// Bonus inattendu et précieux : ce fichier publie QNH ET QFF côte à
// côte. Il sert donc de VALIDATION INDÉPENDANTE de la conversion du
// client — confrontée aux valeurs officielles de Lugano le 03/08, la
// chaîne QNH → QFF de lib/pressure.ts tombe à 0,20 hPa près (cf.
// scripts/verify-pressure.mjs, section 7).
//
// Licence : usage libre, MENTION OBLIGATOIRE « Source : MeteoSuisse »
// partout où la donnée est affichée (même traitement que l'attribution
// Infoclimat).
const SMN_BASE = 'https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn';
const SMN_META_URL = `${SMN_BASE}/ogd-smn_meta_stations.csv`;
// Donnée 10 min, cache serveur de 10 s côté Confédération : 15 min est
// large, et l'ETag évite de retélécharger un fichier inchangé.
const SMN_POLL_MS = 15 * 60 * 1000;
const SMN_META_POLL_MS = 24 * 3600 * 1000;
const SMN_RETENTION_MS = 36 * 3600 * 1000;

// Ancres SwissMetNet. Sigles à trois lettres. Toute entrée absente des
// métadonnées officielles est ignorée avec un log unique au démarrage —
// une faute de frappe dégrade, elle ne boucle pas sur des 404.
// Les stations de haute montagne (Samedan 1708 m, Grand-Saint-Bernard
// 2472 m, Davos, Jungfraujoch) sont VOLONTAIREMENT absentes : au-delà
// de ~1000 m aucune réduction au niveau de la mer n'est exploitable —
// Samedan annonçait Q1025 le 03/08 quand toute la Suisse était entre
// Q1013 et Q1018.
const SMN_ANCHORS = [
  'GVE', 'SIO', 'PAY', 'NEU', 'BER', 'BAS', 'LUZ', 'ALT',
  'SMA', 'KLO', 'STG', 'GUT', 'CHU', 'GLA', 'VIS', 'MAG',
  'LUG', 'OTL', 'INT', 'MER',
];

let smnMeta = new Map();       // abbr -> {nom, lat, lon, alt}
let smnMetaFetchedAt = 0;
let smnObsCache = new Map();   // abbr -> dernier relevé
let smnHistory = new Map();    // abbr -> [{t, qff, tempC}] croissant
let smnFetchedAt = 0;
let smnLastError = null;
const smnEtags = new Map();    // url -> ETag du dernier téléchargement

// Télécharge un CSV MeteoSuisse en respectant l'ETag. Renvoie null si
// rien n'a changé (304) ou en cas d'échec — l'appelant garde alors ses
// données précédentes.
async function smnFetchCsv(url) {
  const prev = smnEtags.get(url);
  const r = await fetch(url, prev ? { headers: { 'If-None-Match': prev } } : undefined);
  if (r.status === 304) return null;
  if (!r.ok) { smnLastError = `HTTP ${r.status} sur ${url}`; return null; }
  const etag = r.headers.get('etag');
  if (etag) smnEtags.set(url, etag);
  const buf = await r.arrayBuffer();
  // Windows-1252 explicite : les noms de station accentués (Genève,
  // Zürich) seraient corrompus par un r.text() qui suppose UTF-8. Même
  // piège qu'AEMET en ISO-8859-15, même parade.
  return new TextDecoder('windows-1252').decode(buf);
}

// Découpe une ligne CSV `;` et renvoie un objet indexé par en-tête.
// Lire par NOM de colonne est le point important : les fichiers OGD ont
// 33 colonnes dont l'ordre n'est garanti par rien.
function smnParseCsv(text) {
  const lines = text.split(/\r?\n/).filter(l => l.trim().length);
  if (lines.length < 2) return [];
  const head = lines[0].split(';').map(h => h.trim());
  return lines.slice(1).map(line => {
    const cells = line.split(';');
    const o = {};
    head.forEach((h, i) => { o[h] = (cells[i] ?? '').trim(); });
    return o;
  });
}

/** `dd.mm.yyyy HH:MM` UTC → ms epoch. NaN si illisible. */
function smnParseTimestamp(s) {
  const m = /^(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})$/.exec(s || '');
  if (!m) return NaN;
  return Date.UTC(+m[3], +m[2] - 1, +m[1], +m[4], +m[5]);
}

/** Nombre ou null (cellule vide = mesure manquante, pas zéro). */
function smnNum(v) {
  if (v == null || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

// Métadonnées : nom, coordonnées et surtout ALTITUDE.
// ⚠️ L'altitude doit venir d'ici et JAMAIS d'une valeur devinée ou
// reprise d'un aérodrome voisin : la réduction au niveau de la mer en
// dépend directement. Vérifié le 03/08 sur Lugano — la station SMN est
// à ~300 m, pas aux 276 m de l'aérodrome LSZA, et se tromper de 28 m
// décalait la pression station de 3,3 hPa.
//
// Et ce n'est pas `station_height_masl` qu'il faut lire mais
// `station_height_barometer_masl` : l'altitude du BAROMÈTRE, qui diffère
// de celle du sol de un à deux mètres, et c'est elle qui entre dans la
// réduction. Bénéfice secondaire, plus important que la précision : une
// colonne `station_height_barometer_masl` VIDE signale une station SANS
// baromètre — filtre exact, plutôt que de découvrir des `pp0qffs0`
// systématiquement vides à l'usage.
// Colonnes vérifiées en direct le 03/08 sur l'en-tête réel du fichier.
async function refreshSmnMeta() {
  try {
    const text = await smnFetchCsv(SMN_META_URL);
    if (!text) return;
    const rows = smnParseCsv(text);
    const next = new Map();
    for (const row of rows) {
      const abbr = (row.station_abbr || '').toUpperCase();
      if (!abbr) continue;
      const lat = smnNum(row.station_coordinates_wgs84_lat);
      const lon = smnNum(row.station_coordinates_wgs84_lon);
      const alt = smnNum(row.station_height_barometer_masl);
      // alt null = pas de baromètre sur cette station : inutile ici.
      if (lat == null || lon == null || alt == null) continue;
      next.set(abbr, { nom: row.station_name || abbr, lat, lon, alt });
    }
    if (next.size) {
      smnMeta = next;
      smnMetaFetchedAt = Date.now();
      const manquantes = SMN_ANCHORS.filter(a => !smnMeta.has(a));
      if (manquantes.length) {
        console.warn(`⚠️  Ancres SwissMetNet inconnues du référentiel, ignorées : ${manquantes.join(', ')}`);
      }
      console.log(`📇 Métadonnées SwissMetNet : ${smnMeta.size} stations, ${SMN_ANCHORS.length - manquantes.length} ancres résolues`);
    }
  } catch (e) {
    smnLastError = `refreshSmnMeta: ${e.message}`;
    console.error(smnLastError);
  }
}

async function refreshSmnObs() {
  if (!smnMeta.size) await refreshSmnMeta();
  if (!smnMeta.size) return;
  let ok = 0;
  for (const abbr of SMN_ANCHORS) {
    const meta = smnMeta.get(abbr);
    if (!meta) continue;
    try {
      const slug = abbr.toLowerCase();
      const text = await smnFetchCsv(`${SMN_BASE}/${slug}/ogd-smn_${slug}_t_now.csv`);
      if (!text) continue; // 304 ou échec : on garde l'existant
      const rows = smnParseCsv(text);
      // QFF d'abord, QNH en REPLI — et la décision se prend PAR STATION,
      // sur l'ensemble du fichier, jamais ligne à ligne.
      //
      // Pourquoi ce repli existe : MeteoSuisse ne publie pas `pp0qffs0`
      // partout. Sur les 131 relevés du 03/08, Visp et St-Gall en avaient
      // ZÉRO, tout en publiant `pp0qnhs0` ET la température sur les 131.
      // Ces deux ancres étaient donc écartées en silence — pas au filtre
      // des métadonnées (leurs baromètres sont bien déclarés, 641 m et
      // 777 m) mais faute de valeur exploitable ici.
      //
      // Visp justifie le repli à elle seule : c'est LA station de la
      // vallée du Rhône, là où se joue le foehn du Valais, et son QNH est
      // au dixième d'hPa — dix fois mieux résolu qu'un METAR. La
      // conversion QNH→QFF côté client (lib/pressure.ts) réclame la
      // température réelle : elle est là, sur tous les relevés.
      //
      // Pourquoi PAR STATION et pas par ligne : Sion a 130 relevés sur
      // 131 avec QFF, et le DERNIER sans. Un repli ligne à ligne ferait
      // basculer Sion en QNH sur son relevé le plus récent — donc sur
      // celui que le panneau affiche — et ferait sauter la convention
      // d'un point à l'autre de la même courbe. Une station qui publie du
      // QFF reste en QFF : mieux vaut son QFF vieux de 10 minutes que son
      // QNH de maintenant.
      //
      // ⚠️ Le repli n'est pas gratuit et ne doit jamais être présenté
      // comme équivalent : une valeur convertie porte une incertitude que
      // `normalizePressure` calcule et que le panneau doit afficher. D'où
      // `reduction` transmis par station, et non plus codé en dur à 'qff'
      // pour toute la source.
      const aDuQff = rows.some(r => smnNum(r.pp0qffs0) != null);
      const champ = aDuQff ? 'pp0qffs0' : 'pp0qnhs0';
      const reduction = aDuQff ? 'qff' : 'qnh';

      // Borne haute du buffer AVANT d'y verser ce fichier : tout ce qui
      // est au-delà est nouveau et part en base. Sans ce repère on
      // ré-upserterait les ~144 lignes du jour à chaque poll de 15 min,
      // soit 14 000 lignes/jour pour 2 900 utiles.
      const dejaVuJusqua = smnHistory.get(abbr)?.at(-1)?.t ?? -Infinity;
      const nouveaux = [];

      let latest = null;
      for (const row of rows) {
        const t = smnParseTimestamp(row.reference_timestamp);
        const p = smnNum(row[champ]);
        if (!Number.isFinite(t) || p == null) continue;
        const tempC = smnNum(row.tre200s0);
        pressureHistoryPush(smnHistory, abbr, { t, p, reduction, tempC }, SMN_RETENTION_MS);
        if (t > dejaVuJusqua) nouveaux.push({ station_abbr: abbr, t, p, reduction, temp_c: tempC });
        if (!latest || t > latest.t) {
          latest = {
            t, p, reduction, tempC,
            // Le vent SMN est en m/s → km/h, comme MF.
            moy: smnNum(row.fkl010z0) != null ? smnNum(row.fkl010z0) * 3.6 : null,
            dir: smnNum(row.dkl010z0),
            // Rafale (lot balises, 04/08/2026). Elle est dans le MÊME
            // CSV, déjà téléchargé : rien à demander en plus.
            //
            // `fkl010z1` = pointe de vent (1 s), maximum sur 10 min, en
            // m/s. Vérifié colonne par colonne sur Lugano le 03/08 à
            // 15:40 : fkl010z1 = 6,2 m/s et fu3010z1 = 22,3 km/h, soit
            // exactement 6,2 × 3,6 = 22,32. Le repli sur `fu3010z1`
            // n'est donc pas une autre grandeur, c'est la MÊME déjà
            // convertie — d'où l'ordre : on garde la convention m/s des
            // autres champs, et on ne descend sur le km/h natif que si
            // la colonne m/s manque.
            //
            // ⚠️ NE PAS confondre avec `fkl010z3` / `fu3010z3` (5,8 m/s
            // et 20,9 km/h sur le même relevé) : autre fenêtre de
            // pointe, valeur systématiquement plus basse. Prendre celle
            // -là ferait sous-annoncer les rafales sur un outil de
            // sécurité.
            raf: smnNum(row.fkl010z1) != null ? smnNum(row.fkl010z1) * 3.6
               : smnNum(row.fu3010z1),
          };
        }
      }
      if (latest) { smnObsCache.set(abbr, { ...latest, ...meta }); ok++; }
      smnPersistHistory(nouveaux);
    } catch (e) {
      console.error(`refreshSmnObs ${abbr}: ${e.message}`);
    }
  }
  if (ok) { smnFetchedAt = Date.now(); smnLastError = null; smnPurgeHistory(); }
}

// ── Persistance SwissMetNet — 04/08/2026 ────────────────────────────
// Miroir d'aemetPersistHistory, à une différence près : purge à un seul
// seuil (SMN_RETENTION_MS), là où MF et AEMET séparent vent 48 h /
// pression seule 12 h. Ici tout est de la pression, il n'y a rien à
// différencier.
//
// POURQUOI cette table existe alors que le commentaire de
// /pressure-history disait qu'elle serait un doublon : parce que ce
// commentaire reposait sur une prémisse fausse (cf. le bloc SMN_BASE).
// `_t_now.csv` ne resert PAS 36 h, il resert le jour courant. Un
// redémarrage Render à 02:00 UTC laisse donc SwissMetNet à deux heures
// d'historique, sur les MEILLEURES stations du dispositif — celles au
// dixième d'hPa qui portent Zurich, Lugano, Sion, Viège. Le METAR, lui,
// garde sa dispense : son API resert bien 30 h, à la condition du
// découpage en lots (cf. METAR_ROW_BUDGET), donc rien à persister.
//
// Fire-and-forget, comme mfPersistHistory et aemetPersistHistory : une
// écriture Supabase qui échoue ne doit jamais empêcher le poll suivant.
function smnPersistHistory(rows) {
  if (!rows.length) return;
  sbUpsert('smn_pressure_history', rows, 'station_abbr,t')
    .catch(e => console.error('smnPersistHistory upsert error:', e.message));
}

// Purge, appelée UNE FOIS par cycle et non par station — contrairement
// à aemetPersistHistory, où purge et écriture partagent le même appel.
// Le seuil est global : vingt DELETE identiques pour un seul `t < X`,
// c'est dix-neuf requêtes Supabase pour rien, toutes les 15 minutes.
function smnPurgeHistory() {
  const cutoff = Date.now() - SMN_RETENTION_MS;
  sbDelete('smn_pressure_history', `t=lt.${cutoff}`)
    .catch(e => console.error('smnPurgeHistory error:', e.message));
}

// Hydrate smnHistory au démarrage. À appeler AVANT le premier
// refreshSmnObs : celui-ci se sert de la borne haute du buffer pour
// savoir quoi persister, et repartir d'un buffer vide lui ferait
// ré-upserter le jour entier pour rien.
async function hydrateSmnHistoryFromSupabase() {
  try {
    const cutoff = Date.now() - SMN_RETENTION_MS;
    const rows = await sbGet(
      'smn_pressure_history',
      `t=gte.${cutoff}&select=station_abbr,t,p,reduction,temp_c&order=t.asc&limit=200000`
    );
    if (!Array.isArray(rows) || !rows.length) return;
    const stations = new Set();
    for (const r of rows) {
      const abbr = String(r.station_abbr);
      // `Number()` explicite : PostgREST rend les `numeric` en CHAÎNES.
      // Les laisser telles quelles ferait des soustractions de Δ en
      // concaténations silencieuses côté client.
      pressureHistoryPush(smnHistory, abbr, {
        t: Number(r.t), p: Number(r.p),
        reduction: r.reduction,
        tempC: r.temp_c == null ? null : Number(r.temp_c),
      }, SMN_RETENTION_MS);
      stations.add(abbr);
    }
    console.log(`🔄 smnHistory hydraté depuis smn_pressure_history : ${rows.length} points, ${stations.size} stations`);
  } catch (e) {
    console.error('hydrateSmnHistoryFromSupabase error:', e.message);
  }
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
// ── Compression gzip (audit charge 24/07/2026) ──
// Premier middleware : compresse TOUTES les réponses JSON. Les listes de
// stations (/meteofrance-stations ~65 Ko, /aemet-stations, /infoclimat-stations)
// étaient servies en clair à chaque poll client (6/15/20 min) = poste n°1 de la
// bande passante Render (HTTP Responses). Le JSON compresse ~8× → ÷8 sur ce
// poste, sans aucun changement de comportement côté client (décompression
// transparente par le navigateur). Placé avant express.json/CORS/routes pour
// envelopper toutes les réponses.
app.use(compression());
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
// Étape 28 — insertion pure (sans clé de conflit, contrairement à sbUpsert).
// Tolère un tableau vide : ne fait alors AUCUNE requête, ce qui évite un
// 400 PostgREST sur un body `[]` à chaque cycle sans détection.
async function sbInsert(table, rows) {
  if (!Array.isArray(rows) || !rows.length) return true;
  const r = await fetch(`${SB_URL}/rest/v1/${table}`, { method:'POST', headers:{...SB_HEADERS,'Prefer':'return=minimal'}, body:JSON.stringify(rows) });
  return r.ok;
}
// Insertion d'UNE ligne dont on a besoin de l'id généré (événement front
// de rafales). `return=representation` est indispensable ici : sans lui
// PostgREST renvoie un corps vide et on perdrait le lien avec les
// détections/ETA à écrire juste après.
async function sbInsertReturning(table, row) {
  const r = await fetch(`${SB_URL}/rest/v1/${table}`, { method:'POST', headers:{...SB_HEADERS,'Prefer':'return=representation'}, body:JSON.stringify(row) });
  if (!r.ok) return null;
  const d = await r.json();
  return Array.isArray(d) ? d[0] : d;
}

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

// Health check. Étape 28 — le champ `loops` expose, pour chaque boucle,
// l'ancienneté du dernier cycle RÉUSSI. Motif : un détecteur silencieux
// qui est EN PANNE est indiscernable d'un détecteur silencieux qui n'a
// rien à signaler ; sans cette information, une panne de la chaîne front
// de rafales ne se verrait jamais. UptimeRobot garde Render éveillé, il
// ne dit rien de la fraîcheur des données.
app.get('/', (req, res) => {
  const now = Date.now();
  const ageMin = (t) => (t ? Math.round((now - t) / 60000) : null);
  res.json({
    status: 'ok', version: '2.2.0', service: 'Balise Watch Push Server',
    // `version` dit ce que le SOURCE prétend être ; `build` dit ce qui
    // TOURNE. Les deux ne se recoupent pas : seul `build.commit` permet
    // d'affirmer qu'un correctif est en ligne.
    //   curl -s https://balise-watch-server.onrender.com/ | grep -o '"commit":"[^"]*"'
    build: {
      commit: GIT_COMMIT,                 // null hors Render
      short: GIT_COMMIT ? GIT_COMMIT.slice(0, 7) : null,
      branch: GIT_BRANCH,
      bootAt: new Date(BOOT_AT).toISOString(),
      uptimeMin: Math.round((now - BOOT_AT) / 60000),
    },
    loops: {
      meteofrance: { lastObsAgeMin: ageMin(mfObsCacheFetchedAt), stations: mfObsCache.size },
      gustFront: {
        enabled: GUST_FRONT_ENABLED,
        shadow: GUST_FRONT_SHADOW,
        lastCycleAgeMin: ageMin(gfLastCycleAt),
        lastOkAgeMin: ageMin(gfLastCycleOkAt),
        lastError: gfLastError,
      },
    },
  });
});

// ── Étape 28 : front de rafales ────────────────────────────────────
// Événements vivants + leurs détections et ETA. Lecture publique comme
// /meteofrance-stations : c'est de la donnée d'observation agrégée, et
// le gate bêta-testeur se fait côté client sur l'AFFICHAGE du calque —
// le serveur n'a pas de session ici. Rien de personnel n'est exposé.
//
// ⚠️ SERVI DEPUIS LA RAM, jamais depuis Supabase à la demande.
// Première version : 3 requêtes Supabase PAR APPEL. Avec un poll client
// toutes les 6 min, 50 pilotes = 36 000 requêtes/jour pour une donnée
// STRICTEMENT IDENTIQUE pour tout le monde et qui ne change qu'une fois
// par cycle. C'est exactement le piège qui a déjà coûté cher à ce projet
// sur Open-Meteo (cf. BUGS.md 19/07 : quota saturé, 429 silencieux,
// « ne pas retirer ce cache »). Le cache est rafraîchi UNE fois par
// cycle de détection : le coût Supabase devient indépendant du nombre
// de pilotes.
app.get('/gust-front/active', (req, res) => {
  res.json({ events: gfActiveCache.events, fetchedAt: gfActiveCache.fetchedAt });
});

// Supervision détaillée du détecteur (état du buffer, warmup, latence de
// publication mesurée, raison de non-détection). Sert au panneau du
// calque en bêta : le pilote doit pouvoir distinguer « rien à signaler »
// de « le détecteur n'est pas prêt ».
app.get('/gust-front/health', (req, res) => {
  const now = Date.now();
  res.json({
    enabled: GUST_FRONT_ENABLED,
    shadow: GUST_FRONT_SHADOW,
    lastCycleAt: gfLastCycleAt || null,
    lastOkAt: gfLastCycleOkAt || null,
    lastReason: gfLastReason,
    lastError: gfLastError,
    publicationLatencyMin: Math.round(gfPublicationLatencyMs / 60000),
    activeEventId: gfActiveEvent?.id ?? null,
    activeEventStatus: gfActiveEvent?.status ?? null,
    detector: gf.gfHealth(now),
    // Lot A — état de la veille modèle. Distinct du détecteur mesuré :
    // les deux peuvent tomber en panne indépendamment, et une grille
    // modèle périmée ne se voit pas autrement.
    model: {
      run: gfModelRun,
      loaded: !!gfModelGrid,
      steps: gfModelGrid?.times?.length ?? 0,
      ageMin: gfModelCheckedAt ? Math.round((now - gfModelCheckedAt) / 60000) : null,
      lastReason: gfModelLastReason,
    },
  });
});
app.get('/vapid-public-key', (req, res) => res.json({ key: VAPID_PUB }));

// ── Étape 13 (19/07/2026) — Grille de vent (calque carte "champ de vent") ──
// Retour Yann (capture meteo-parapente.com) : un calque carte avec des
// flèches de vent partout (pas juste aux balises), un choix d'altitude,
// et un module bas heures/jours/modèle. meteo-parapente.com fait tourner
// son PROPRE modèle WRF très haute résolution — hors de portée d'un
// projet solo/gratuit. On reste ici sur Open-Meteo/AROME-ICON-ARPEGE-GFS
// déjà utilisés ailleurs dans l'app, à une résolution de grille bien plus
// grossière (un point tous les ~16 km, pas ~1-2 km).
//
// Débogage 19/07/2026 (2e retour Yann — 0 flèche + module bas absent en
// prod) : la route ci-dessous était déclarée à la ligne ~905, AVANT
// `const app = express()` (ligne ~1475 à l'époque). `const` n'est pas
// hissé comme `var` — Node levait `ReferenceError: Cannot access 'app'
// before initialization` AU DÉMARRAGE (visible dans les logs Render),
// donc le serveur entier crashait en boucle et ne servait plus RIEN, pas
// seulement /wind-grid. Bloc entier déplacé ici, après `app` ET après le
// middleware CORS/rate-limit, comme toutes les autres routes du fichier.
//
// Débogage 19/07/2026 (4e retour Yann — capture Ambert/Puy-de-Dôme, hors
// de l'ancienne emprise fixe Vercors/Écrins/Queyras/Maurienne) : « je
// l'utilise pour toute la France ! Et idéalement Espagne / Italie /
// Suisse / Allemagne ». Une grille FIXE à ~16km/point sur toute cette
// zone dépasserait largement la limite de 1000 coordonnées/requête
// Open-Meteo (~20 000 points nécessaires). Décision avec Yann : la
// grille SUIT LA CARTE — découpée en TUILES de WIND_GRID_TILE_DEG° de
// côté, chacune un point de cache RAM indépendant ; le client ne
// demande que les tuiles qui recouvrent la vue actuelle (cf. MapView.tsx,
// windGridTilesForBounds). Remplace l'ancienne grille fixe (WIND_GRID_BBOX/
// WIND_GRID_POINTS) entièrement.
const WIND_GRID_TILE_DEG = 2; // DOIT rester identique à lib/config.ts côté client
const WIND_GRID_STEP_DEG = 0.15; // ~16 km/point à cette latitude, inchangé
// Une tuile de 2° à ce pas donne ⌈2/0.15⌉² ≈ 14×14 = 196 points, large
// marge sous la limite de 1000 coordonnées/requête.
function buildTilePoints(tileLat, tileLon) {
  const pts = [];
  for (let lat = tileLat; lat < tileLat + WIND_GRID_TILE_DEG - 1e-9; lat += WIND_GRID_STEP_DEG) {
    for (let lon = tileLon; lon < tileLon + WIND_GRID_TILE_DEG - 1e-9; lon += WIND_GRID_STEP_DEG) {
      pts.push({ lat: Math.round(lat * 1000) / 1000, lon: Math.round(lon * 1000) / 1000 });
    }
  }
  return pts;
}
// Emprise globale acceptée (France + Espagne/Italie/Suisse/Allemagne +
// marge, demande Yann) — endpoint public sans auth : sert à rejeter
// toute tuile hors de cette zone plutôt que de laisser n'importe quelle
// coordonnée du globe être mise en cache ici.
const WIND_GRID_EXTENT = { latMin: 34, latMax: 56, lonMin: -11, lonMax: 19 };

// Débogage 19/07/2026 (retour Yann, suite) — les hauteurs AGL 10/80/
// 120/180m (1er essai) sont quasi au ras du sol partout dans les Alpes
// (le terrain lui-même dépasse souvent 1000-2000m) : inutilisables pour
// un pilote qui vole à 2000-4000m. Remplacées par les MÊMES NIVEAUX DE
// PRESSION que la coupe verticale (PROFILE_LEVELS côté client, lib/
// config.ts), qui couvrent les vraies altitudes de vol — filtrés pour
// rester ≤ 6000m (demande Yann), donc sans le niveau 400hPa (≈7180m,
// cf. WIND_GRID_LEVEL_ALT_M plus bas). PAS vérifié en direct pour CHACUN
// des 4 modèles dans cette session (réseau sandboxé, cf. plus haut) : si
// un modèle renvoie null sur un niveau une fois en prod, le traiter
// comme un signal pour restreindre WIND_GRID_LEVELS À CE MODÈLE plutôt
// qu'une supposition à corriger ici sans vérification.
const WIND_GRID_LEVELS = [1000, 950, 925, 900, 850, 800, 700, 600, 500];
const WIND_GRID_MODELS = ['meteofrance_seamless', 'icon_seamless', 'arpege_seamless', 'gfs_seamless'];
// Débogage 19/07/2026 (3e retour Yann) — demande de séparer le calque en
// deux options de menu distinctes : "Vent sol" (vent au niveau du sol,
// PAS un niveau de pression — variable AGL 10m native Open-Meteo, celle
// affichée par toutes les stations météo/webcams) et "Vent altitude"
// (grille existante, niveaux de pression WIND_GRID_LEVELS ci-dessus).
// `kind` distingue les deux ; `level` n'a de sens que pour kind='alt'.
const WIND_GRID_KINDS = ['sol', 'alt'];
// Mêmes valeurs que MODEL_FORECAST_DAYS côté client (lib/config.ts, même
// rationnel détaillé là-bas) — pas de code partagé entre les deux repos,
// à garder synchronisé si ces valeurs changent d'un côté.
const WIND_GRID_FORECAST_DAYS = {
  meteofrance_seamless: 3, icon_seamless: 3, arpege_seamless: 5, gfs_seamless: 8,
};
// Cache jugé périmé au-delà de cette durée -> re-fetch synchrone au
// prochain GET pour cette tuile, même politique que /precip-distance
// (cutPrecipLastAttempt/CUT_PRECIP_MAX_AGE_MS) : pas de refresh en tâche
// de fond aveugle sur toutes les tuiles possibles, seules celles
// réellement consultées par au moins un pilote déclenchent un appel.
const WIND_GRID_MAX_AGE_MS = 25 * 60 * 1000;
// Débogage 19/07/2026 — une grille qui suit la carte peut en théorie
// accumuler une tuile par recoin de la zone couverte (France + voisins)
// au fil des sessions de tous les pilotes : éviction simple (pas un vrai
// LRU, juste la plus ancienne mise à jour) au-delà de ce nombre de tuiles
// en cache, largement suffisant pour un projet solo/gratuit sur le RAM
// limité du plan gratuit Render.
const WIND_GRID_CACHE_MAX_TILES = 400;

// Clé "model|kind|level|tileLat|tileLon" (level vide pour kind='sol') ->
// { fetchedAt, times: string[] (ISO UTC),
// points: [{lat,lon,speed:number[],dir:number[]}] } — speed[i]/dir[i]
// alignés sur `times` (même longueur pour tous les points de LA TUILE).
const windGridCache = new Map();
// Débogage 19/07/2026 (5e retour Yann, logs Render collés) — le calque
// ne renvoyait JAMAIS de flèches : chaque appel loggait `refreshWindGrid
// ...: HTTP 429` (Open-Meteo, "Too Many Requests"), et ce AVANT ET APRÈS
// le passage aux tuiles (donc pas introduit par le refactor tuiles :
// l'ancienne grille fixe tapait déjà le même mur). Cause racine : sans
// ceci, un échec (429 ou autre) ne mettait JAMAIS `windGridCache` à jour
// (cf. `refreshWindGrid`, early return sur `!r.ok`) — donc la condition
// `!cached` restait vraie indéfiniment, et CHAQUE requête suivante (poll
// 5 min de chaque pilote affichant le calque, x jusqu'à 12 tuiles x 2
// kinds) retentait aussitôt un appel Open-Meteo, qui se refaisait 429 à
// son tour : tempête de retries qui ne laissait jamais la fenêtre de
// rate-limit d'Open-Meteo se libérer. Même classe de bug déjà résolue
// ailleurs dans ce fichier pour /precip-distance (cf.
// cutPrecipLastAttempt/CUT_PRECIP_MAX_AGE_MS) : horloge murale de la
// dernière TENTATIVE (succès ou échec), séparée du cache de données,
// pour borner la fréquence de retry même en cas d'échec répété.
const windGridLastAttempt = new Map(); // clé identique à windGridCache -> ms epoch de la dernière tentative
const WIND_GRID_RETRY_COOLDOWN_MS = 2 * 60 * 1000; // pas de nouvelle tentative avant 2 min après un échec, sur cette tuile

function evictWindGridCacheIfNeeded() {
  if (windGridCache.size <= WIND_GRID_CACHE_MAX_TILES) return;
  let oldestKey = null, oldestTs = Infinity;
  for (const [k, v] of windGridCache) {
    if (v.fetchedAt < oldestTs) { oldestTs = v.fetchedAt; oldestKey = k; }
  }
  if (oldestKey) windGridCache.delete(oldestKey);
}

async function refreshWindGrid(model, kind, level, tileLat, tileLon) {
  const key = `${model}|${kind}|${level ?? ''}|${tileLat}|${tileLon}`;
  // Horloge murale de la TENTATIVE, avant même l'appel réseau — posée en
  // premier (synchrone, avant le premier `await`) pour qu'une requête
  // concurrente sur la même tuile (autre pilote, même seconde) voie déjà
  // ce cooldown et ne relance pas un second appel Open-Meteo en double.
  windGridLastAttempt.set(key, Date.now());
  const tilePoints = buildTilePoints(tileLat, tileLon);
  const lats = tilePoints.map(p => p.lat).join(',');
  const lons = tilePoints.map(p => p.lon).join(',');
  const days = WIND_GRID_FORECAST_DAYS[model] ?? 3;
  // kind='sol' -> variable AGL 10m native (vent au sol, pas un niveau de
  // pression) ; kind='alt' -> niveau de pression hPa (WIND_GRID_LEVELS).
  const speedVar = kind === 'sol' ? 'wind_speed_10m' : `wind_speed_${level}hPa`;
  const dirVar = kind === 'sol' ? 'wind_direction_10m' : `wind_direction_${level}hPa`;
  const url = `${OPEN_METEO_URL}?latitude=${lats}&longitude=${lons}` +
    `&hourly=${speedVar},${dirVar}` +
    `&models=${model}&wind_speed_unit=kmh&timezone=UTC&forecast_days=${days}`;
  try {
    const r = await fetch(url);
    if (!r.ok) {
      // Log ajouté au déplacement du bloc (19/07) — avant ça, un échec
      // Open-Meteo (4xx/5xx) était totalement silencieux côté Render,
      // rendant ce genre de panne indiagnosticable depuis les logs seuls.
      console.error(`refreshWindGrid ${key}: HTTP ${r.status}`);
      return windGridCache.get(key) ?? null;
    }
    const d = await r.json();
    // Open-Meteo renvoie un TABLEAU d'objets (un par coordonnée) dès que
    // plusieurs lat/lon sont demandés — pas un objet unique comme en
    // mono-point (cf. profileUrl côté client, un seul point). Un point
    // isolé en échec (hors domaine fin du modèle, etc.) devient `null`
    // dans ce tableau : ignoré ci-dessous plutôt que de faire échouer
    // toute la tuile pour un seul point.
    const arr = Array.isArray(d) ? d : [d];
    const times = arr.find(e => e?.hourly?.time)?.hourly?.time ?? [];
    const points = [];
    arr.forEach((entry, i) => {
      const h = entry?.hourly;
      const src = tilePoints[i];
      if (!h || !src) return;
      const speed = h[speedVar];
      const dir = h[dirVar];
      if (!Array.isArray(speed) || !Array.isArray(dir)) return;
      points.push({ lat: src.lat, lon: src.lon, speed, dir });
    });
    const entryOut = { fetchedAt: Date.now(), times, points };
    windGridCache.set(key, entryOut);
    evictWindGridCacheIfNeeded();
    if (!points.length) {
      console.error(`refreshWindGrid ${key}: 0 point exploitable sur ${tilePoints.length} (times=${times.length})`);
    }
    return entryOut;
  } catch (e) {
    // Échec réseau/API -> on garde l'ancien cache tel quel (même
    // politique que refreshMeteoFranceData/cutPrecipRefresh) plutôt que
    // de vider une donnée encore exploitable.
    console.error(`refreshWindGrid ${key} error:`, e.message);
    return windGridCache.get(key) ?? null;
  }
}

// GET /wind-grid?model=meteofrance_seamless&kind=alt&level=850&tileLat=44&
// tileLon=6 (ou kind=sol, sans level) — UNE TUILE de la grille de points
// vent pour le calque carte (pas une balise précise, pas la grille
// entière). Pas d'auth : donnée publique dérivée d'Open-Meteo, même
// politique que les autres routes météo en lecture seule de ce fichier.
app.get('/wind-grid', async (req, res) => {
  const model = String(req.query.model || '');
  const kind = String(req.query.kind || 'alt');
  const level = kind === 'alt' ? Number(req.query.level) : null;
  const tileLatRaw = Number(req.query.tileLat);
  const tileLonRaw = Number(req.query.tileLon);
  if (!WIND_GRID_MODELS.includes(model) || !WIND_GRID_KINDS.includes(kind)) {
    return res.status(400).json({ error: 'model/kind invalide' });
  }
  if (kind === 'alt' && !WIND_GRID_LEVELS.includes(level)) {
    return res.status(400).json({ error: 'level invalide' });
  }
  if (
    !Number.isFinite(tileLatRaw) || !Number.isFinite(tileLonRaw) ||
    tileLatRaw < WIND_GRID_EXTENT.latMin || tileLatRaw >= WIND_GRID_EXTENT.latMax ||
    tileLonRaw < WIND_GRID_EXTENT.lonMin || tileLonRaw >= WIND_GRID_EXTENT.lonMax
  ) {
    return res.status(400).json({ error: 'tuile hors zone couverte' });
  }
  // Tuile normalisée CÔTÉ SERVEUR (pas de confiance dans l'arrondi
  // client) — évite qu'un bug/arrondi client crée une infinité de clés
  // de cache décalées d'une fraction de degré pour la même zone réelle.
  const tileLat = Math.floor(tileLatRaw / WIND_GRID_TILE_DEG) * WIND_GRID_TILE_DEG;
  const tileLon = Math.floor(tileLonRaw / WIND_GRID_TILE_DEG) * WIND_GRID_TILE_DEG;
  const key = `${model}|${kind}|${level ?? ''}|${tileLat}|${tileLon}`;
  const cached = windGridCache.get(key);
  const isStale = !cached || Date.now() - cached.fetchedAt > WIND_GRID_MAX_AGE_MS;
  // Cooldown de retry (cf. windGridLastAttempt plus haut, débogage
  // 19/07/2026 5e retour Yann) : même si `isStale`, on ne retente PAS un
  // appel Open-Meteo tant que la dernière tentative (succès ou échec) a
  // moins de WIND_GRID_RETRY_COOLDOWN_MS — évite la tempête de retries
  // qui empêchait un 429 de jamais se résorber (chaque requête pilote
  // relançait aussitôt un nouvel appel qui se refaisait 429 à son tour).
  const canRetry = Date.now() - (windGridLastAttempt.get(key) ?? 0) > WIND_GRID_RETRY_COOLDOWN_MS;
  if (isStale && canRetry) {
    await refreshWindGrid(model, kind, level, tileLat, tileLon);
  }
  const entry = windGridCache.get(key);
  if (!entry) return res.json({ model, kind, level, tileLat, tileLon, times: [], points: [] });
  res.json({ model, kind, level, tileLat, tileLon, fetchedAt: entry.fetchedAt, times: entry.times, points: entry.points });
});

// ── Sommets NOMMÉS autour d'un site (lot B, 05/08/2026) ──────────────
// Carte d'identité d'un site, CONCEPTION_CARTE_IDENTITE_SITE_05-08.md §3.
// La fiche d'un déco affiche le point le plus haut avoisinant et le vent
// à son altitude. L'altitude, le cap et la distance sont déjà calculés
// côté client par balayage du relief (lib/summit.ts) ; ce qui manque et
// que seul OpenStreetMap peut donner, c'est le NOM.
//
// ── POURQUOI CET ENDPOINT EXISTE, PLUTÔT QU'UN APPEL DEPUIS LE NAVIGATEUR
// Overpass est lent, sujet aux 429, et sans garantie de disponibilité.
// Le mettre dans le chemin d'ouverture d'une fiche le rendrait visible à
// chaque pilote. Surtout, sa politique d'usage (vérifiée le 05/08/2026,
// dev.overpass-api.de/overpass-doc/en/preface/commons.html) désigne
// nommément comme problématique le fait de « monter une app destinée à
// plus que des contributeurs OSM en s'appuyant sur les instances
// publiques comme backend ». Depuis un navigateur, chaque pilote serait
// un utilisateur Overpass distinct et personne ne verrait le volume
// total ; ici tout passe par UNE adresse, la nôtre, avec un cache qu'on
// contrôle et un volume qu'on peut chiffrer.
//
// ── CE QUE DIT LA POLITIQUE, ET OÙ ON SE SITUE ──────────────────────
// Marges annoncées : ~10 000 requêtes/jour et < 1 Go/jour par
// utilisateur (l'adresse IP fait l'utilisateur). Comportement cité comme
// problématique n°1 : « envoyer des dizaines de milliers de fois par
// jour la même requête depuis la même adresse ».
//
// Notre volume MAXIMUM théorique : la base pgEarth compte 3 313 décos ;
// avec un TTL de 30 jours, même si CHAQUE site était consulté, cela fait
// ~110 requêtes/jour. Soit ~1 % de la marge. En pratique, ~40 pilotes
// n'ouvrent qu'une poignée de fiches — l'ordre de grandeur réel est la
// dizaine par jour.
//
// ⚠️ Ce qui fait tenir ce chiffre, ce n'est PAS le TTL de 30 jours, c'est
// le cache NÉGATIF. Un site sans sommet nommé dans son rayon est le cas
// où la tentation d'oublier le cache est la plus forte (il n'y a « rien »
// à garder) et c'est exactement là que le comportement problématique n°1
// se produirait : chaque ouverture de fiche relancerait la même requête
// vide. Un « on a cherché, il n'y a rien » se cache aussi longtemps
// qu'un résultat.
//
// ⚠️ Render est en offre GRATUITE et son IP sortante peut être partagée
// avec d'autres locataires : un 429 peut nous arriver sans être de notre
// fait. C'est sans conséquence — le client retombe sur son balayage du
// relief et affiche un point haut sans nom, cf. lib/summit.ts.
//
// ── PAS DE PERSISTANCE, ET POURQUOI ─────────────────────────────────
// Le cache est en RAM et meurt à chaque redéploiement. La conception
// évoquait un cache disque « si le cache mémoire ne suffit pas au réveil
// de Render » : le disque d'une instance gratuite est lui aussi éphémère,
// il n'apporterait donc rien. La vraie option durable serait une table
// Supabase — écartée pour l'instant parce qu'elle coûterait une migration
// et du quota pour économiser quelques dizaines de requêtes par jour sur
// une marge de 10 000. À reconsidérer si le volume réel dépassait le
// millier de requêtes/jour, ou si un intégrateur externe (lot G) venait
// s'ajouter aux pilotes.
const OVERPASS_URL = 'https://overpass-api.de/api/interpreter';
// ⚠️ DÉBOGAGE 05/08/2026, sur le PREMIER appel réel : 504 systématique.
//
// Ce n'est pas une panne, c'est un refus documenté, et il vient de ce
// qu'on DÉCLARE, pas de ce qu'on consomme. Overpass n'admet une requête
// que si elle promet d'utiliser au plus la moitié des ressources encore
// disponibles — sur les DEUX critères, temps d'exécution et mémoire. Or
// une requête sans `[maxsize:]` explicite déclare 512 Mio par défaut.
// La nôtre lit quelques dizaines de nœuds dans un rayon de 8 km : elle
// demandait mille fois ce qu'elle utilise, et se faisait refuser dès que
// le serveur avait un peu de charge.
//
// D'où deux déclarations désormais explicites et SERRÉES. Elles ne
// rendent pas la requête plus rapide ; elles la rendent ADMISSIBLE, ce
// qui n'est pas la même chose et c'est tout le sujet. Une requête qui
// promet peu passe devant une requête qui promet beaucoup, même si la
// seconde était en réalité aussi légère.
//
// Le refus par ressources est un 504 ; le refus par quota est un 429.
// Les deux se lisent dans /summit-diag, et ils n'appellent pas la même
// correction — celui-ci se corrige en déclarant moins, l'autre en
// appelant moins souvent.
const OVERPASS_TIMEOUT_S = 10;
/** 16 Mio, contre 512 par défaut. Un nœud OSM pèse quelques centaines
 *  d'octets ; 60 nœuds tiennent dans un millième de cette enveloppe. */
const OVERPASS_MAXSIZE_BYTES = 16 * 1024 * 1024;
// Coupe-circuit CÔTÉ NOUS, distinct du précédent : le `[timeout:]` est
// une promesse faite à Overpass, celui-ci garantit qu'une requête pendue
// ne retient pas une réponse HTTP à un pilote.
const OVERPASS_ABORT_MS = 20 * 1000;
// User-Agent descriptif avec un contact : c'est la coutume de la
// communauté OSM, et la seule façon pour l'exploitant de nous joindre
// avant de bloquer une IP qui le dérangerait.
const OVERPASS_UA = 'BaliseWatch/1.0 (PWA meteo parapente; +https://balise-watch.vercel.app; biozarb@gmail.com)';
// Les sommets ne bougent pas. Le seul événement qui périme une réponse
// est une contribution OSM, et 30 jours de retard sur un nom de sommet
// n'a jamais fait de mal à personne.
const SUMMIT_MAX_AGE_MS = 30 * 24 * 3600 * 1000;
// Après un échec (429, 504, réseau), pas de nouvelle tentative sur CETTE
// clé avant ce délai — même patron que WIND_GRID_RETRY_COOLDOWN_MS, et
// même raison : sans lui, chaque ouverture de fiche relance un appel qui
// se refait jeter, et le 429 ne se résorbe jamais.
const SUMMIT_RETRY_COOLDOWN_MS = 15 * 60 * 1000;
// Intervalle minimal entre DEUX appels Overpass, tous sites confondus.
// La politique parle de créneaux et de temps de refroidissement ; se
// sérialiser à un appel par seconde nous met hors de portée du mécanisme
// de délestage quoi qu'il arrive.
const OVERPASS_MIN_INTERVAL_MS = 1000;
const SUMMIT_MAX_PEAKS = 60;
const SUMMIT_RADIUS_MAX_KM = 20;

const summitCache = new Map();        // clé -> { fetchedAt, peaks: [...] }
const summitLastAttempt = new Map();  // clé -> ms epoch de la dernière tentative
const summitInFlight = new Map();     // clé -> Promise, dédoublonne les appels concurrents
let overpassLastCall = 0;
/** Dernier échec Overpass, exposé par /summit-diag.
 *
 *  ⚠️ Ajouté le 05/08/2026 après le PREMIER appel réel, qui a rendu
 *  `unavailable` sans rien dire de plus. Le repli silencieux est le bon
 *  comportement pour un pilote — il voit un point haut sans nom, jamais
 *  une erreur — mais il rend la panne indiagnosticable de l'extérieur.
 *  Même leçon que `loops.lastError` dans le health check (étape 28) : un
 *  composant silencieux EN PANNE est indiscernable d'un composant
 *  silencieux qui n'a rien à signaler. */
let summitLastFailure = null;
/** Dernier succès, pour distinguer « jamais marché » de « marchait, ne
 *  marche plus » sans avoir à lire les logs Render. */
let summitLastSuccess = null;

/** `ele` d'OSM est CONTRIBUTIF et sale : « 3506 », « 3506 m », « 3 506 »,
 *  « 3506.5 », parfois une chaîne libre. On rend un nombre ou `null`, et
 *  jamais une valeur devinée — un sommet sans altitude exploitable sera
 *  mesuré au relief côté client, qui a le DEM sous la main. */
function parseOsmEle(raw) {
  if (raw == null) return null;
  const m = String(raw).replace(/\s| /g, '').match(/-?\d+(?:[.,]\d+)?/);
  if (!m) return null;
  const v = Number(m[0].replace(',', '.'));
  // Bornes de plausibilité terrestre. Une valeur hors de ces bornes est
  // une faute de saisie (unité en pieds, virgule de milliers mal placée),
  // et la propager serait pire que de ne rien dire.
  return Number.isFinite(v) && v > -500 && v < 9000 ? v : null;
}

async function fetchNamedPeaks(lat, lon, radiusKm) {
  const now = Date.now();
  const wait = Math.max(0, OVERPASS_MIN_INTERVAL_MS - (now - overpassLastCall));
  if (wait > 0) await new Promise(r => setTimeout(r, wait));
  overpassLastCall = Date.now();

  // `node` seul et pas `nwr` : un sommet est un point dans OSM. Le filtre
  // `["name"]` fait partie de la requête et pas d'un tri après coup —
  // c'est ce qui garde la réponse à quelques kilo-octets.
  const q = `[out:json][timeout:${OVERPASS_TIMEOUT_S}][maxsize:${OVERPASS_MAXSIZE_BYTES}];`
    + `node["natural"="peak"]["name"](around:${Math.round(radiusKm * 1000)},${lat},${lon});`
    + `out body ${SUMMIT_MAX_PEAKS};`;

  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), OVERPASS_ABORT_MS);
  try {
    const r = await fetch(OVERPASS_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded', 'User-Agent': OVERPASS_UA },
      body: 'data=' + encodeURIComponent(q),
      signal: ctrl.signal,
    });
    // 429 = quota, 504 = ressources insuffisantes : les deux sont des
    // refus NORMAUX et documentés, pas des pannes. On les traite comme
    // un échec silencieux côté pilote (cooldown), mais on GARDE de quoi
    // les distinguer — un 429 et une requête malformée demandent deux
    // corrections opposées, et sans le code on ne peut que deviner.
    if (!r.ok) {
      let corps = '';
      try { corps = (await r.text()).slice(0, 400); } catch { /* corps illisible */ }
      summitLastFailure = { at: new Date().toISOString(), phase: 'http', status: r.status, body: corps, query: q };
      return null;
    }
    const j = await r.json();
    if (!Array.isArray(j?.elements)) {
      summitLastFailure = {
        at: new Date().toISOString(), phase: 'shape', status: r.status,
        body: JSON.stringify(j).slice(0, 400), query: q,
      };
      return null;
    }
    summitLastSuccess = { at: new Date().toISOString(), elements: j.elements.length };
    return j.elements
      .filter(e => e && typeof e.lat === 'number' && typeof e.lon === 'number' && e.tags?.name)
      .map(e => ({
        name: String(e.tags.name).slice(0, 120),
        lat: e.lat,
        lon: e.lon,
        // `null` assumé : le client mesurera au relief. Cf. parseOsmEle.
        eleM: parseOsmEle(e.tags.ele),
      }));
  } catch (e) {
    summitLastFailure = {
      at: new Date().toISOString(), phase: 'network',
      error: String(e && e.name || e), message: String(e && e.message || '').slice(0, 200), query: q,
    };
    return null;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * GET /summit?lat=&lon=&radiusKm=
 *
 * Rend la LISTE des sommets nommés du rayon, pas « le plus haut ».
 * Le choix appartient au client, et ce n'est pas une paresse : départager
 * des sommets demande une altitude pour chacun, or `ele` manque sur une
 * partie d'entre eux et c'est le NAVIGATEUR qui a le relief sous la main
 * (tuiles Terrarium déjà chargées pour ce rayon, cf. lib/summit.ts). Le
 * serveur fait ici la seule chose que le navigateur ne doit pas faire :
 * parler à Overpass.
 *
 * `peaks: []` avec `status: 'ok'` = on a cherché, il n'y a aucun sommet
 * nommé — l'information est vraie et se cache 30 jours.
 * `status: 'unavailable'` = Overpass n'a pas répondu ; rien n'est mis en
 * cache long, seulement un cooldown. Les deux mènent le client au même
 * repli (balayage du relief, point haut sans nom), mais pas pour la même
 * raison, et la fiche ne doit pas les confondre.
 */
app.get('/summit', async (req, res) => {
  const latRaw = Number(req.query.lat);
  const lonRaw = Number(req.query.lon);
  const radiusRaw = Number(req.query.radiusKm);
  if (!Number.isFinite(latRaw) || latRaw < -90 || latRaw > 90
      || !Number.isFinite(lonRaw) || lonRaw < -180 || lonRaw > 180) {
    return res.status(400).json({ error: 'lat/lon invalide' });
  }
  // Normalisation CÔTÉ SERVEUR, comme pour /wind-grid : aucune confiance
  // dans l'arrondi du client. Sans elle, deux appels pour le même site
  // dont les coordonnées diffèrent au dix-millième créeraient deux clés
  // de cache, donc deux requêtes Overpass pour la même réponse — le
  // comportement problématique n°1 de la politique, obtenu par
  // inadvertance. 3 décimales ≈ 110 m, très en dessous du rayon.
  const lat = Math.round(latRaw * 1000) / 1000;
  const lon = Math.round(lonRaw * 1000) / 1000;
  // Rayon en kilomètres ENTIERS et borné : un rayon libre serait une
  // clé de cache libre, donc un cache qu'on ne remplit jamais.
  const radiusKm = Math.min(SUMMIT_RADIUS_MAX_KM, Math.max(1, Math.round(radiusRaw || 8)));

  const key = `${lat}|${lon}|${radiusKm}`;
  const cached = summitCache.get(key);
  if (cached && Date.now() - cached.fetchedAt < SUMMIT_MAX_AGE_MS) {
    return res.json({ lat, lon, radiusKm, status: 'ok', fetchedAt: cached.fetchedAt, peaks: cached.peaks });
  }

  const canRetry = Date.now() - (summitLastAttempt.get(key) ?? 0) > SUMMIT_RETRY_COOLDOWN_MS;
  if (!canRetry) {
    // Périmé mais en cooldown : on ressert le vieux plutôt que rien. Un
    // nom de sommet vieux de 31 jours vaut infiniment mieux qu'un trou.
    if (cached) {
      return res.json({ lat, lon, radiusKm, status: 'ok', fetchedAt: cached.fetchedAt, peaks: cached.peaks });
    }
    return res.json({ lat, lon, radiusKm, status: 'unavailable', peaks: [] });
  }

  // Dédoublonnage des appels concurrents : deux pilotes ouvrant la même
  // fiche en même temps ne doivent pas produire deux requêtes Overpass.
  let job = summitInFlight.get(key);
  if (!job) {
    summitLastAttempt.set(key, Date.now());
    job = fetchNamedPeaks(lat, lon, radiusKm).finally(() => summitInFlight.delete(key));
    summitInFlight.set(key, job);
  }
  const peaks = await job;

  if (peaks == null) {
    if (cached) {
      return res.json({ lat, lon, radiusKm, status: 'ok', fetchedAt: cached.fetchedAt, peaks: cached.peaks });
    }
    return res.json({ lat, lon, radiusKm, status: 'unavailable', peaks: [] });
  }
  // ⚠️ Le tableau VIDE est mis en cache comme le reste. Cf. le
  // commentaire en tête de section : c'est le cache négatif qui tient le
  // volume, pas le TTL.
  const fetchedAt = Date.now();
  summitCache.set(key, { fetchedAt, peaks });
  res.json({ lat, lon, radiusKm, status: 'ok', fetchedAt, peaks });
});

// Diagnostic de /summit — même esprit que /pressure-diag et que le champ
// `loops` du health check : rendre visible ce qu'un repli silencieux
// cache par construction. Sans lui, « aucun point haut ne se nomme
// jamais » a trois causes possibles (quota Overpass, requête malformée,
// réseau) qui demandent trois corrections opposées, et rien à l'écran ne
// permet de choisir. Aucune donnée sensible : la requête et la réponse
// d'Overpass sont publiques.
app.get('/summit-diag', (req, res) => {
  res.json({
    cacheEntries: summitCache.size,
    inFlight: summitInFlight.size,
    lastSuccess: summitLastSuccess,
    lastFailure: summitLastFailure,
    overpassUrl: OVERPASS_URL,
    userAgent: OVERPASS_UA,
  });
});

// ── Sondages réels (radiosondages), 25/07/2026 ───────────────────────
// Retour pilotes (via Yann) : émagramme modèle ok, mais veulent aussi le
// VRAI sondage (ballon-sonde) le plus proche, façon Meteociel/Wyoming.
// Lâchers Météo-France : 2/jour (00Z, 12Z), tous les jours, 5 stations en
// France (Trappes/Brest/Bordeaux/Nîmes/Ajaccio) — pas hebdomadaire.
// Complété par les stations frontalières les plus utiles pour les Alpes/
// zones de vol françaises (Suisse, Allemagne, Italie).
// ⚠️ id = numéro OMM 5 chiffres (celui qu'attend Wyoming). Toutes les
// stations ci-dessous VÉRIFIÉES actives (recherche web 25/07/2026) :
// - Suisse : Payerne est la SEULE station de radiosondage du pays
//   (réseau MeteoSwiss à une seule station, historique depuis 1954).
// - Allemagne : réseau DWD, 11 stations, lâchers ≥2/jour (00Z/12Z) —
//   Stuttgart-Schnarrenberg et Idar-Oberstein confirmées actives.
// - Italie : Milano/Linate a fermé en 2021, remplacée par Cameri
//   (Novara) — corrigé ici. Ajout de Cuneo-Levaldigi (WMO 16117), la
//   plus proche des Alpes françaises/Maurienne (juste à la frontière
//   côté Piémont), donc la plus utile pour ce public de pilotes.
// - Espagne (ajout 25/07/2026, demande Yann) : réseau AEMET, lâchers
//   2/jour (00Z/12Z) confirmés actifs (recherche web 25/07/2026) à
//   A Coruña, Santander, Zaragoza, Madrid-Barajas, Barcelone, Palma de
//   Mallorca et Murcia — les 7 retenues telles quelles (pas de tri
//   supplémentaire par proximité des sites de vol, même logique
//   "réseau national complet" que pour la France ci-dessus).
// - Portugal (ajout 25/07/2026) : une seule station confirmée sur le
//   continent, Lisboa/Gago Coutinho — le réseau des Açores (Lajes/Ponta
//   Delgada) n'a pas pu être confirmé actif à cette date, exclu par
//   prudence plutôt que de risquer une station morte dans la liste.
const SOUNDING_STATIONS = [
  { id: '07145', name: 'Trappes', country: 'FR', lat: 48.774, lon: 2.011 },
  { id: '07110', name: 'Brest-Guipavas', country: 'FR', lat: 48.444, lon: -4.412 },
  { id: '07510', name: 'Bordeaux-Mérignac', country: 'FR', lat: 44.831, lon: -0.691 },
  { id: '07645', name: 'Nîmes-Courbessac', country: 'FR', lat: 43.858, lon: 4.407 },
  { id: '07761', name: 'Ajaccio', country: 'FR', lat: 41.918, lon: 8.793 },
  { id: '06610', name: 'Payerne', country: 'CH', lat: 46.813, lon: 6.943 },
  { id: '10739', name: 'Stuttgart-Schnarrenberg', country: 'DE', lat: 48.828, lon: 9.2 },
  { id: '10618', name: 'Idar-Oberstein', country: 'DE', lat: 49.7, lon: 7.333 },
  { id: '16064', name: 'Cameri (Novara)', country: 'IT', lat: 45.52, lon: 8.65 },
  { id: '16117', name: 'Cuneo-Levaldigi', country: 'IT', lat: 44.547, lon: 7.623 },
  { id: '08001', name: 'A Coruña', country: 'ES', lat: 43.36, lon: -8.42 },
  { id: '08023', name: 'Santander', country: 'ES', lat: 43.47, lon: -3.82 },
  { id: '08160', name: 'Zaragoza', country: 'ES', lat: 41.67, lon: -1.02 },
  { id: '08181', name: 'Barcelone', country: 'ES', lat: 41.29, lon: 2.07 },
  { id: '08221', name: 'Madrid-Barajas', country: 'ES', lat: 40.5, lon: -3.58 },
  { id: '08301', name: 'Palma de Mallorca', country: 'ES', lat: 39.55, lon: 2.61 },
  { id: '08430', name: 'Murcia', country: 'ES', lat: 38.0, lon: -1.17 },
  { id: '08579', name: 'Lisbonne (Gago Coutinho)', country: 'PT', lat: 38.77, lon: -9.13 },
];
// 2 runs/jour (00Z, 12Z) publiés avec un délai (~2-3h après le lâcher) —
// on ne propose que les runs vraisemblablement déjà publiés au client,
// pour éviter une liste pleine de créneaux qui renverront tous "pas de
// donnée". Profondeur d'historique Wyoming largement > 3j en pratique,
// mais on borne à 3j (72h) : au-delà, peu d'intérêt pour un pilote qui
// prépare un vol.
const SOUNDING_HISTORY_DAYS = 3;
const SOUNDING_PUBLISH_DELAY_MS = 3 * 60 * 60 * 1000;

// Cache RAM : une fois publié, un run passé ne change plus jamais —
// TTL long (pas de re-fetch) pour un succès, TTL COURT pour un échec/
// "pas de donnée" (négatif) afin de ne pas marteler Wyoming si un
// pilote revient plusieurs fois sur un créneau vide. Même politique que
// windGridLastAttempt/WIND_GRID_RETRY_COOLDOWN_MS plus haut.
const soundingCache = new Map(); // clé "stationId|YYYY-MM-DD|HH" -> { fetchedAt, available, levels, stationInfo }
const SOUNDING_NEG_TTL_MS = 30 * 60 * 1000;
const SOUNDING_CACHE_MAX = 500;

function evictSoundingCacheIfNeeded() {
  if (soundingCache.size <= SOUNDING_CACHE_MAX) return;
  let oldestKey = null, oldestTs = Infinity;
  for (const [k, v] of soundingCache) {
    if (v.fetchedAt < oldestTs) { oldestTs = v.fetchedAt; oldestKey = k; }
  }
  if (oldestKey) soundingCache.delete(oldestKey);
}

// Parse le <PRE> de données du HTML Wyoming (type=TEXT:LIST) : colonnes
// fixes PRES HGHT TEMP DWPT RELH MIXR DRCT SKNT ... — on ignore l'en-tête/
// séparateur et on split sur les espaces (les valeurs sont toujours
// numériques, pas de risque de collision avec le format à espaces
// multiples de ce texte).
function parseWyomingSounding(html) {
  const preBlocks = [...html.matchAll(/<PRE>([\s\S]*?)<\/PRE>/gi)].map(m => m[1]);
  if (!preBlocks.length) return null;
  const dataBlock = preBlocks[0];
  const lines = dataBlock.split('\n').map(l => l.trimEnd());
  const levels = [];
  for (const line of lines) {
    const cols = line.trim().split(/\s+/);
    if (cols.length < 8) continue;
    const nums = cols.map(Number);
    if (nums.some(n => Number.isNaN(n))) continue; // saute en-tête/séparateurs (texte)
    const [pres, hght, temp, dwpt, relh, , drct, sknt] = nums;
    levels.push({ pressureHpa: pres, heightM: hght, tempC: temp, dewpointC: dwpt, rh: relh, dirDeg: drct, speedKt: sknt });
  }
  return levels.length ? levels : null;
}

async function refreshSounding(stationId, dateStr, hour) {
  const key = `${stationId}|${dateStr}|${hour}`;
  const url = `https://weather.uwyo.edu/wsgi/sounding?datetime=${dateStr}%20${hour}:00:00&id=${stationId}&type=TEXT:LIST`;
  try {
    const r = await fetch(url);
    const html = r.ok ? await r.text() : '';
    const levels = html ? parseWyomingSounding(html) : null;
    const entry = { fetchedAt: Date.now(), available: !!levels, levels: levels ?? [] };
    soundingCache.set(key, entry);
    evictSoundingCacheIfNeeded();
    return entry;
  } catch (e) {
    console.error(`refreshSounding ${key} error:`, e.message);
    const entry = { fetchedAt: Date.now(), available: false, levels: [] };
    soundingCache.set(key, entry);
    return entry;
  }
}

// GET /sounding-stations — liste statique, pas de cache nécessaire.
app.get('/sounding-stations', (req, res) => res.json({ stations: SOUNDING_STATIONS }));

// GET /sounding/runs?station=07510 — créneaux (date+heure) vraisemblablement
// publiés sur les 72 dernières heures, à proposer côté client dans le
// picker (pas d'appel Wyoming ici, calcul pur — la disponibilité réelle
// n'est confirmée qu'au clic, via /sounding).
app.get('/sounding/runs', (req, res) => {
  const stationId = String(req.query.station || '');
  if (!SOUNDING_STATIONS.some(s => s.id === stationId)) {
    return res.status(400).json({ error: 'station inconnue' });
  }
  const runs = [];
  const now = Date.now();
  for (let h = 0; h < SOUNDING_HISTORY_DAYS * 24; h += 12) {
    const t = new Date(now - h * 60 * 60 * 1000);
    t.setUTCMinutes(0, 0, 0);
    const runHour = t.getUTCHours() >= 12 ? 12 : 0;
    t.setUTCHours(runHour, 0, 0, 0);
    if (now - t.getTime() < SOUNDING_PUBLISH_DELAY_MS) continue; // pas encore publié
    const dateStr = t.toISOString().slice(0, 10);
    const hourStr = String(runHour).padStart(2, '0');
    const runKey = `${dateStr}T${hourStr}`;
    if (!runs.some(r => r.key === runKey)) runs.push({ key: runKey, date: dateStr, hour: hourStr });
  }
  res.json({ station: stationId, runs });
});

// GET /sounding?station=07510&date=2026-07-25&hour=12
app.get('/sounding', async (req, res) => {
  const stationId = String(req.query.station || '');
  const dateStr = String(req.query.date || '');
  const hour = String(req.query.hour || '').padStart(2, '0');
  if (!SOUNDING_STATIONS.some(s => s.id === stationId)) {
    return res.status(400).json({ error: 'station inconnue' });
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(dateStr) || !['00', '12'].includes(hour)) {
    return res.status(400).json({ error: 'date/hour invalide' });
  }
  const key = `${stationId}|${dateStr}|${hour}`;
  const cached = soundingCache.get(key);
  const isNegativeStale = cached && !cached.available && Date.now() - cached.fetchedAt > SOUNDING_NEG_TTL_MS;
  if (!cached || isNegativeStale) {
    await refreshSounding(stationId, dateStr, hour);
  }
  const entry = soundingCache.get(key);
  res.json({ station: stationId, date: dateStr, hour, available: entry?.available ?? false, levels: entry?.levels ?? [] });
});

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

// Débogage 13/07/2026 (nice-to-have "valeur chiffrée dashboard") — mêmes
// principe et contrat que /pressure-signal ci-dessus, pour les deux
// signaux qui n'affichaient jusqu'ici qu'un OK/détecté sans nombre.
// Routes séparées (plutôt qu'étendre /pressure-signal) pour ne pas
// toucher un contrat déjà consommé par le client, et parce que les trois
// caches ont des cycles de vie/formes différents.
app.get('/precip-signal', (req, res) => {
  const ids = String(req.query.ids || '').split(',').map(s => s.trim()).filter(Boolean);
  const signals = {};
  for (const id of ids) signals[id] = precipSignalCache.get(id) ?? null;
  res.json({ signals });
});

app.get('/breeze-signal', (req, res) => {
  const ids = String(req.query.ids || '').split(',').map(s => s.trim()).filter(Boolean);
  const signals = {};
  for (const id of ids) signals[id] = breezeSignalCache.get(id) ?? null;
  res.json({ signals });
});

// Débogage 13/07/2026 — re-câblage développement convectif (cf. bloc
// d'évaluation Lot 3 plus bas). Même contrat que les trois routes ci-dessus.
app.get('/convection-signal', (req, res) => {
  const ids = String(req.query.ids || '').split(',').map(s => s.trim()).filter(Boolean);
  const signals = {};
  for (const id of ids) signals[id] = convectionSignalCache.get(id) ?? null;
  res.json({ signals });
});

// ── Lot 3 plan de coupe (17/07/2026) — distance réelle (km) à la pluie ──
// Endpoint À LA DEMANDE (pas de ?ids= en lot comme les 3 routes signal
// ci-dessus) : le plan de coupe interroge un point libre quelconque, pas
// une liste de balises surveillées. lat/lon requis ; radiusKm optionnel
// (borné 5-100 km, défaut 60 — plus large que le rayon d'alerte
// flightwatch/20 km car ici l'usage est un affichage informatif, pas un
// seuil de notification). Défensif : tout échec (index RainViewer KO,
// aucune tuile décodée, kill switch flightwatch OFF — sans rapport, ce
// cache est indépendant) renvoie simplement { near:false,
// distanceKm:null }, jamais d'erreur 500. Pas d'auth : donnée radar déjà
// publique (comme le calque radar affiché sur la carte), même politique
// que /meteofrance-stations.
app.get('/precip-distance', async (req, res) => {
  const lat = Number(req.query.lat), lon = Number(req.query.lon);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    return res.status(400).json({ error: 'lat/lon requis' });
  }
  const radiusKm = Math.min(Math.max(Number(req.query.radiusKm) || 60, 5), 100);
  if (!cutPrecipTiles.size || Date.now() - cutPrecipLastAttempt > CUT_PRECIP_MAX_AGE_MS) {
    await cutPrecipRefresh();
  }
  const nearest = precipNearestInTiles(cutPrecipTiles, lat, lon, radiusKm);
  const { near, distanceKm } = nearest;
  // Cap de l'écho VU DEPUIS le point (0 = nord, 90 = est) — repère pixel
  // Mercator : x vers l'est, y vers le SUD, d'où le `-dyPx`.
  // Pluie au pixel même du point : pas de cap définissable (vecteur nul),
  // on n'en invente pas un.
  const bearingDeg = (near && (nearest.dxPx !== 0 || nearest.dyPx !== 0))
    ? Math.round((Math.atan2(nearest.dxPx, -nearest.dyPx) * 180 / Math.PI + 360) % 360)
    : null;
  // Suivi de cellule (30/07/2026) : seulement si les TROIS frames sont là
  // et raisonnablement rapprochées, sinon `track` reste null et le client
  // se rabat sur distance + cap, sans verdict de déplacement.
  const dtSec = (cutPrecipFrameTime && cutPrecipPrevFrameTime)
    ? cutPrecipFrameTime - cutPrecipPrevFrameTime : 0;
  const dtSec2 = (cutPrecipPrevFrameTime && cutPrecipPrev2FrameTime)
    ? cutPrecipPrevFrameTime - cutPrecipPrev2FrameTime : 0;
  let track = null;
  if (near && dtSec > 0 && dtSec * 1000 <= CUT_PRECIP_TRACK_MAX_DT_MS
      && dtSec2 > 0 && dtSec2 * 1000 <= CUT_PRECIP_TRACK_MAX_DT_MS) {
    const memoKey = `${lat.toFixed(3)}_${lon.toFixed(3)}_${radiusKm}`;
    if (cutPrecipTrackMemo.has(memoKey)) {
      track = cutPrecipTrackMemo.get(memoKey);
    } else {
      track = precipTrackInTiles(cutPrecipTiles, cutPrecipPrevTiles, cutPrecipPrev2Tiles, nearest, dtSec, dtSec2);
      cutPrecipTrackMemo.set(memoKey, track); // `null` mémoïsé aussi : un refus est aussi cher à recalculer
    }
  }
  res.json({
    near, distanceKm, radiusKm, bearingDeg,
    trend: track?.trend ?? null,
    moveDirDeg: track?.moveDirDeg ?? null,
    moveSpeedKmh: track?.moveSpeedKmh ?? null,
    etaMin: track?.etaMin ?? null,
    cpaKm: track?.cpaKm ?? null,
    // Ancienneté (min) de la frame radar utilisée — RainViewer horodate
    // ses frames en secondes (epoch), d'où le *1000. null si aucune frame
    // n'a jamais pu être chargée.
    frameAgeMin: cutPrecipFrameTime ? Math.round((Date.now() - cutPrecipFrameTime * 1000) / 60000) : null,
  });
});

// ── Étape 11 : stations Météo-France (lecture seule) ─────────────────
// Sert le cache mfObsCache/mfStationsList (rafraîchi en tâche de fond,
// cf. refreshMeteoFranceData) — jamais d'appel Météo-France déclenché
// par une requête client, jamais la clé API exposée côté client. Pas
// d'auth requise, données publiques en lecture.
//
// Débogage 12/07/2026 — retour Yann : ne renvoyait QUE les stations avec
// du vent (~780/2151), filtrant silencieusement les ~1400 stations
// pression-seule alors même que le serveur les enregistre déjà (voir
// refreshMfObs / mfPersistHistory ci-dessus, utilisées en interne comme
// repli "station proche" pour la pression des balises Pioupiou sans
// baromètre). Le filtre `obs.ff == null` est retiré : la route renvoie
// désormais TOUTES les stations qui ont un relevé (vent OU pression
// seule) — dd/ff/raf10/ddraf10 restent `null` pour les pression-seule
// (jamais 0/faux, cf. commentaire refreshMfObs), c'est au client de
// décider s'il les affiche (nouvelle couche carte "Stations pression",
// désactivée par défaut — cf. MapView.tsx). Un seul appel national déjà
// en cache RAM, zéro coût réseau supplémentaire côté serveur ; le
// payload JSON grossit (~780 → ~2150 stations) mais reste un unique
// fetch, pas une requête par station.
// Extrait de la route le 04/08/2026 (lot 7) : le serveur construit
// désormais LUI-MÊME le référentiel de pression, et il lui faut la même
// liste que celle qu'il sert au client. La bâtir deux fois, c'est
// s'exposer à ce que la fiche et la route /phenomenon-delta n'aient pas
// les mêmes stations — donc pas les mêmes ancres, donc pas le même Δ.
function mfStationsPayload() {
  const stationsById = new Map(mfStationsList.map(s => [s.id, s]));
  const out = [];
  for (const [id, obs] of mfObsCache) {
    if (obs.ff == null && obs.pmer == null && obs.pres == null) continue; // aucun relevé exploitable
    const meta = stationsById.get(id);
    if (!meta) continue;
    out.push({
      id, nom: meta.nom, lat: meta.lat, lon: meta.lon, alt: meta.alt,
      dd: obs.dd, ff: obs.ff, raf10: obs.raf10, ddraf10: obs.ddraf10,
      pres: obs.pres, pmer: obs.pmer, validityTime: obs.validityTime,
    });
  }
  return out;
}

app.get('/meteofrance-stations', (req, res) => {
  res.json({ stations: mfStationsPayload(), fetchedAt: mfObsCacheFetchedAt });
});

// ── Étape 11 (suite, 11/07) — Historique court d'une station MF ─────
// Réutilise TEL QUEL le buffer RAM `beaconHistory` (cf. plus haut) déjà
// alimenté à CHAQUE poll (5 min, pollAndNotify) pour toute entrée de
// `releves` — donc aussi les stations MF avec du vent, fondues dedans
// depuis le Lot 7 suite. Aucun nouveau cache, aucun appel réseau ajouté.
// Limites assumées (vs l'archive Pioupiou, hébergée par Pioupiou) :
// (1) 3h30 de profondeur MAX (FW_HISTORY_MAX_AGE_MS) pour CE buffer RAM,
// (2) buffer RAM pur, vidé à chaque redémarrage du process.
// Débogage 17/07 (retour Yann) — raf (rafale, raf10 natif) et min (min
// glissant calculé, cf. fwWindowMinFf) sont désormais persistés en plus
// de moy/direction/pression — l'ancienne limitation "pas de rafale" est
// levée.
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
// Extrait de la route le 04/08/2026 (lot 7) : /phenomenon-delta a besoin
// du MÊME historique que la fiche pour tracer la MÊME courbe. Passer par
// une deuxième lecture écrite à part, c'est accepter que les deux courbes
// diffèrent un jour sans que personne ne s'en aperçoive.
async function mfHistoryPoints(stationId, hoursParam) {
  const ramPts = beaconHistory.get(stationId) || [];
  const hours = Number.isFinite(hoursParam) ? Math.min(Math.max(hoursParam, 0), MF_HISTORY_RETENTION_H) : null;
  if (!hours || hours * 3600 * 1000 <= FW_HISTORY_MAX_AGE_MS) return ramPts;
  try {
    const cutoff = Date.now() - hours * 3600 * 1000;
    const oldPts = await sbGet(
      'mf_station_history',
      `station_id=eq.${encodeURIComponent(stationId)}&t=gte.${cutoff}&select=t,moy,raf,min,dir,pressure&order=t.asc`
    );
    const ramCutoff = ramPts[0]?.t ?? Infinity; // évite les doublons : ne garde du passé persistant que ce qui précède le buffer RAM
    return [...(Array.isArray(oldPts) ? oldPts.filter(p => p.t < ramCutoff) : []), ...ramPts];
  } catch (e) {
    console.error('meteofrance-history (hours) error:', e.message);
    return ramPts; // dégradation gracieuse : au pire, la profondeur RAM habituelle
  }
}

app.get('/meteofrance-history/:id', async (req, res) => {
  res.json({ points: await mfHistoryPoints(req.params.id, Number(req.query.hours)) });
});

// ── Étape 12 (suite, 17/07) — Stations Infoclimat (lecture seule) ───
// Sert infoclimatObsCache/infoclimatStationsList (rafraîchi en tâche de
// fond, cf. refreshInfoclimatData) — jamais d'appel Infoclimat déclenché
// par une requête client, jamais la clé API exposée côté client. Pas
// d'auth requise, données déjà publiques (CC BY / CC BY-NC) en lecture.
// `licenseCode`/`licenseLabel`/`licenseUrl` transmis pour que le client
// puisse afficher l'attribution requise par la licence (obligatoire pour
// CC BY, bonne pratique pour CC BY-NC) directement dans la popup carte.
app.get('/infoclimat-stations', (req, res) => {
  const out = [];
  for (const [id, obs] of infoclimatObsCache) {
    const meta = infoclimatStationsById.get(id);
    if (!meta) continue;
    out.push({
      id, nom: meta.nom, lat: meta.lat, lon: meta.lon, alt: meta.alt,
      licenseCode: meta.licenseCode, licenseLabel: meta.licenseLabel, licenseUrl: meta.licenseUrl,
      dd: obs.dir, ff: obs.moy, raf10: obs.raf, pressure: obs.pressure, temp: obs.temp,
      validityTime: Number.isFinite(obs.t) ? new Date(obs.t).toISOString() : null,
    });
  }
  // Débogage 17/07/2026 — `lastError`/`stationsListCount` en clair dans
  // la réponse (jamais la clé API) pour diagnostiquer à distance un
  // cache vide sans avoir besoin des logs Render. Depuis le 03/08, le
  // diagnostic le plus probable a changé : ce n'est plus « clé absente »
  // ni « IP de Render rejetée » (ce serveur n'appelle plus Infoclimat)
  // mais « objet R2 périmé », c'est-à-dire le poller du VPS arrêté.
  res.json({
    stations: out,
    fetchedAt: infoclimatObsCacheFetchedAt,
    stationsListCount: infoclimatStationsList.length,
    lastError: infoclimatLastError,
  });
});

// ── Étape 12 (suite) — Historique d'une station Infoclimat ──────────
// RÉÉCRIT LE 03/08/2026, en même temps que le bloc de rafraîchissement.
//
// Avant : cette route relayait un appel à Infoclimat, DÉCLENCHÉ PAR UNE
// REQUÊTE CLIENT, sur une profondeur allant jusqu'à 14 jours. Deux
// problèmes, dont un de principe :
//  · elle ne pouvait pas marcher — IP de Render refusée, `Wrong ip
//    address` en HTTP 200, et le client recevait `{points: []}` sans
//    savoir pourquoi ;
//  · un clic de pilote déclenchait un appel chez une association
//    bénévole. C'est exactement ce que leur page open data demande
//    d'éviter, et ça ne se plafonne pas.
//
// Depuis : servi depuis `infoclimatHistory`, relu de R2 sur NOTRE
// cadence (cf. refreshInfoclimatHistory). Aucun appel externe déclenché
// par un client, jamais.
//
// ⚠️ PROFONDEUR RAMENÉE À ~30 h. L'archive d'Infoclimat remonte bien
//    plus loin, mais on ne va plus la chercher à la demande. Le client
//    ne demande au maximum que `max(7, heure_locale + 2)` heures pour le
//    graphe de comparaison (ChartModal), soit ~25 h : la profondeur
//    retenue côté poller (HISTORY_HEURES) couvre ce besoin avec marge.
//    Si un écran devait un jour demander plusieurs jours, c'est la
//    rétention du POLLER qu'il faudrait remonter — et son coût est en
//    octets R2, pas en appels chez eux.
//
// Forme de sortie inchangée : HistoryPoint[] {t, min, avg, max, dir,
// pressure}, identique à Pioupiou/MF/AEMET. `min` toujours null (pas de
// minimum glissant chez Infoclimat) ; `max` = rafale native quand la
// station en mesure une, null sinon — jamais 0 ni reconstitué.
// ⚠️ 03/08/2026 — il était écrit ici que `vent_rafales` était null sur
// tout le réseau : FAUX, 25 stations sur 865 en publient. Détail et
// mesure dans le commentaire du dépliage colonnaire (~ligne 2394).
app.get('/infoclimat-history/:id', (req, res) => {
  const pts = infoclimatHistory.get(req.params.id);
  if (!pts) return res.json({ points: [], fetchedAt: infoclimatHistoryFetchedAt });
  const hoursParam = Number(req.query.hours);
  const hours = Number.isFinite(hoursParam) ? Math.min(Math.max(hoursParam, 1), 48) : 24;
  const cutoff = Date.now() - hours * 3600 * 1000;
  res.json({
    points: pts.filter(p => p.t >= cutoff),
    fetchedAt: infoclimatHistoryFetchedAt,
  });
});

// ── AEMET (Espagne), ajout 22/07/2026 — stations (lecture seule) ────
// Sert aemetObsCache (rafraîchi en tâche de fond, cf. refreshAemetData)
// — jamais d'appel AEMET déclenché par une requête client, jamais la clé
// API exposée côté client. Pas d'auth requise, données publiques en
// lecture (licence AEMET OpenData). Mêmes noms de champs que
// /meteofrance-stations (dd/ff/raf10/ddraf10/pres/pmer/validityTime) —
// délibéré, pour réutiliser telle quelle la même forme côté client
// plutôt que d'introduire une troisième convention de champs.
// Extrait de la route pour la même raison que mfStationsPayload : une
// seule construction, servie au client ET consommée par le référentiel
// interne (lot 7).
function aemetStationsPayload() {
  const out = [];
  for (const [id, obs] of aemetObsCache) {
    if (obs.moy == null && obs.pressure == null) continue; // aucun relevé exploitable
    out.push({
      id, nom: obs.nom, lat: obs.lat, lon: obs.lon, alt: obs.alt,
      dd: obs.dir, ff: obs.moy, raf10: obs.raf, ddraf10: obs.dirRaf,
      pres: null, pmer: obs.pressure,
      validityTime: Number.isFinite(obs.t) ? new Date(obs.t).toISOString() : null,
    });
  }
  return out;
}

app.get('/aemet-stations', (req, res) => {
  res.json({ stations: aemetStationsPayload(), fetchedAt: aemetObsCacheFetchedAt, lastError: aemetLastError });
});

// ── AEMET (Espagne), ajout 22/07/2026 — historique d'une station ────
// Même contrat que /meteofrance-history/:id : buffer RAM beaconHistory
// (3h30 max, alimenté à chaque poll pollAndNotify pour toute entrée
// fondue dans `releves`, donc aussi AEMET depuis la fusion ci-dessus)
// complété par aemet_station_history (persistance 48h/12h, cf.
// aemetPersistHistory) au-delà de cette profondeur RAM via ?hours=N. Pas
// d'auth : donnée publique en lecture, comme les autres endpoints stations.
// Extrait de la route pour la même raison que mfHistoryPoints (lot 7).
async function aemetHistoryPoints(stationId, hoursParam) {
  const ramPts = beaconHistory.get(stationId) || [];
  const hours = Number.isFinite(hoursParam) ? Math.min(Math.max(hoursParam, 0), AEMET_HISTORY_RETENTION_H) : null;
  if (!hours || hours * 3600 * 1000 <= FW_HISTORY_MAX_AGE_MS) return ramPts;
  try {
    const cutoff = Date.now() - hours * 3600 * 1000;
    const oldPts = await sbGet(
      'aemet_station_history',
      `station_id=eq.${encodeURIComponent(stationId)}&t=gte.${cutoff}&select=t,moy,raf,dir,pressure&order=t.asc`
    );
    const ramCutoff = ramPts[0]?.t ?? Infinity;
    return [...(Array.isArray(oldPts) ? oldPts.filter(p => p.t < ramCutoff) : []), ...ramPts];
  } catch (e) {
    console.error('aemet-history (hours) error:', e.message);
    return ramPts;
  }
}

app.get('/aemet-history/:id', async (req, res) => {
  res.json({ points: await aemetHistoryPoints(req.params.id, Number(req.query.hours)) });
});

// ── winds.mobi (07/08/2026) — stations agrégées ─────────────────────
// Même forme de payload que /meteofrance-stations et /aemet-stations
// (délibéré : le client réutilise la même normalisation), avec DEUX
// champs en plus, `reseau` et `reseauNom`, parce que la source technique
// unique `windsmobi` recouvre une quinzaine de réseaux réels et qu'un
// pilote doit pouvoir distinguer une balise de déco FFVL d'une station
// de plaine. `pres`/`pmer` sont à null par construction, cf. la note de
// refreshWindsmobiProviders.
function windsmobiStationsPayload() {
  const out = [];
  for (const [id, obs] of windsmobiObsCache) {
    if (obs.moy == null) continue;
    out.push({
      id, nom: obs.nom, lat: obs.lat, lon: obs.lon, alt: obs.alt,
      dd: obs.dir, ff: obs.moy, raf10: obs.raf, ddraf10: null,
      pres: null, pmer: null,
      reseau: obs.reseau, reseauNom: obs.reseauNom, url: obs.url,
      validityTime: Number.isFinite(obs.t) ? new Date(obs.t).toISOString() : null,
    });
  }
  return out;
}

app.get('/windsmobi-stations', (req, res) => {
  res.json({ stations: windsmobiStationsPayload(), fetchedAt: windsmobiFetchedAt, lastError: windsmobiLastError });
});

// ── winds.mobi — historique d'une station ───────────────────────────
// Seule source du projet dont l'historique n'a PAS de table Supabase :
// winds.mobi sert lui-même 7 jours (mesuré). Le buffer RAM
// beaconHistory reste prioritaire sur sa profondeur (il est alimenté par
// pollAndNotify avec NOS horodatages), l'amont vient compléter au-delà —
// même contrat de recouvrement que aemetHistoryPoints.
//
// ⚠️ C'est le SEUL endroit où une requête client peut déclencher un
// appel winds.mobi. Le point 3 des CGU l'exige : un cache de 3 min évite
// qu'un pilote qui ouvre et ferme un graphe cinq fois de suite compte
// pour cinq appels, et la profondeur est plafonnée pour qu'un ?hours
// fantaisiste ne demande pas six mois d'archive.
const windsmobiHistoryCache = new Map(); // id -> {at, points}
const WINDSMOBI_HISTORY_CACHE_MS = 3 * 60 * 1000;

async function windsmobiHistoryPoints(stationId, hoursParam) {
  const ramPts = beaconHistory.get(stationId) || [];
  const hours = Number.isFinite(hoursParam) ? Math.min(Math.max(hoursParam, 1), WINDSMOBI_HISTORY_MAX_H) : 24;
  const cached = windsmobiHistoryCache.get(stationId);
  if (cached && Date.now() - cached.at < WINDSMOBI_HISTORY_CACHE_MS && cached.hours >= hours) {
    return mergeWindsmobiHistory(cached.points, ramPts, hours);
  }
  try {
    const rows = await fetchWindsmobi(
      `/stations/${encodeURIComponent(stationId)}/historic/?duration=${Math.round(hours * 3600)}`
    );
    if (!Array.isArray(rows)) return ramPts;
    // winds.mobi rend le plus récent EN PREMIER et horodate en secondes.
    const points = rows
      .filter(p => Number.isFinite(p?._id))
      .map(p => ({ t: p._id * 1000, moy: p['w-avg'] ?? null, raf: p['w-max'] ?? null, min: null, dir: p['w-dir'] ?? null, pressure: null }))
      .sort((a, b) => a.t - b.t);
    windsmobiHistoryCache.set(stationId, { at: Date.now(), hours, points });
    return mergeWindsmobiHistory(points, ramPts, hours);
  } catch (e) {
    console.error('windsmobi-history error:', e.message);
    return ramPts;
  }
}

// Le buffer RAM gagne sur son propre intervalle : ses points viennent du
// même poll que les alertes, donc une courbe et une alerte ne peuvent
// pas se contredire sur les dernières heures.
function mergeWindsmobiHistory(upstream, ramPts, hours) {
  const cutoff = Date.now() - hours * 3600 * 1000;
  const ramCutoff = ramPts[0]?.t ?? Infinity;
  return [...upstream.filter(p => p.t >= cutoff && p.t < ramCutoff), ...ramPts];
}

app.get('/windsmobi-history/:id', async (req, res) => {
  res.json({ points: await windsmobiHistoryPoints(req.params.id, Number(req.query.hours)) });
});

// ── Balises de pression (foehn v2, lot 0, 03/08/2026) ──────────────
// Sert metarObsCache + smnObsCache, tous deux rafraîchis en tâche de
// fond. Jamais d'appel externe déclenché par une requête client.
//
// Forme DÉLIBÉRÉMENT DIFFÉRENTE de /meteofrance-stations et
// /aemet-stations : ces stations ne sont pas des balises (cf. le grand
// commentaire à la définition des polls), et leur donner la même forme
// inviterait à les traiter comme telles.
//
// Le contrat tient en trois champs :
//   reduction  'qff' | 'qnh'  — la convention de la valeur brute
//   pressure   la valeur BRUTE, jamais convertie ici
//   tempC      indispensable pour convertir un 'qnh' en QFF
// Le client (lib/pressure.ts) normalise et refuse le point s'il ne peut
// pas. Voir PROMPT_REPRISE_FOEHN_V2.md §3 pour pourquoi mélanger les
// deux conventions fabrique un biais corrélé au foehn mesuré.
//
// `id` est préfixé par la source ('metar:LIMW', 'smn:LUG') : trois
// espaces d'identifiants cohabitent déjà côté balises (Pioupiou, MF,
// AEMET) et la collision y est seulement improbable — ici elle est
// impossible par construction.
function pressureStationsPayload() {
  const out = [];
  for (const [code, o] of metarObsCache) {
    if (o.lat == null || o.lon == null || o.alt == null) continue;
    out.push({
      id: `metar:${code}`, source: 'metar', code, nom: o.nom,
      lat: o.lat, lon: o.lon, alt: o.alt,
      reduction: 'qnh', resolutionHpa: 1,
      pressure: o.qnh, tempC: o.tempC,
      dd: o.dir, ff: o.moy,
      // Rafale (lot balises). `null` sur un METAR ne veut PAS dire
      // « non mesurée » mais « pas de rafale significative » : la règle
      // de codage OACI ne fait publier `wgst` que si la pointe dépasse
      // le vent moyen de 10 kt. Le client doit donc afficher un tiret
      // neutre, pas un « — » de donnée manquante.
      raf: o.raf ?? null,
      // ── Cadence de publication (lot balises) ──────────────────────
      // Sans ça, le calque Balises grise les METAR la moitié du temps.
      // Un METAR sort à :20 et :50 sur les grands terrains, à l'heure
      // ronde ailleurs, et il est publié APRÈS l'heure d'observation :
      // un relevé de 25 minutes d'âge est parfaitement NORMAL, là où un
      // Pioupiou de 25 minutes est mort. Le seuil de péremption ne peut
      // donc pas être une constante du client, il est une propriété de
      // la SOURCE — c'est elle qui la connaît.
      cadenceMin: 30,
      t: o.t,
    });
  }
  for (const [code, o] of smnObsCache) {
    out.push({
      id: `smn:${code}`, source: 'smn', code, nom: o.nom,
      lat: o.lat, lon: o.lon, alt: o.alt,
      // `reduction` vient de la station et non de la source : MeteoSuisse
      // ne publie pas de QFF partout (Visp, St-Gall), et une valeur en
      // repli QNH annoncée comme du QFF serait comparée à un vrai QFF
      // sans conversion — un biais silencieux, corrélé à la température,
      // donc corrélé au foehn qu'on mesure. Exactement ce que le §3 du
      // document de conception interdit. La résolution, elle, reste au
      // dixième dans les deux cas : c'est le pas de publication de
      // MeteoSuisse, pas une propriété de la convention.
      reduction: o.reduction, resolutionHpa: 0.1,
      pressure: o.p, tempC: o.tempC,
      dd: o.dir, ff: o.moy,
      // Rafale (lot balises) — ici `null` veut bien dire « non
      // mesurée », contrairement au METAR : SwissMetNet publie
      // `fkl010z1` sur tous ses relevés, une absence est une lacune.
      raf: o.raf ?? null,
      // Cf. la note sur `cadenceMin` au-dessus. SwissMetNet publie
      // toutes les 10 minutes, comme un réseau automatique moderne :
      // même règle de péremption qu'une balise ordinaire.
      cadenceMin: 10,
      t: o.t,
    });
  }
  return out;
}

app.get('/pressure-stations', (req, res) => {
  res.json({
    stations: pressureStationsPayload(),
    fetchedAt: Math.max(metarFetchedAt, smnFetchedAt),
    metarFetchedAt, smnFetchedAt,
    lastError: metarLastError || smnLastError || null,
    // Obligation de licence MeteoSuisse — le client doit pouvoir
    // afficher l'attribution sans la coder en dur de son côté.
    attribution: 'Source : MeteoSuisse ; METAR : NOAA/aviationweather.gov',
  });
});

// Historique d'une balise de pression, `id` préfixé comme ci-dessus.
//
// ⚠️ CORRIGÉ LE 04/08/2026. Ce commentaire affirmait qu'aucune table
// Supabase n'était nécessaire « puisque les deux sources servent
// elles-mêmes leur propre historique ». Vrai pour le METAR, FAUX pour
// MeteoSuisse : `_t_now.csv` couvre le jour UTC courant, pas 36 h (cf.
// le bloc SMN_BASE). Depuis, `smn_pressure_history` persiste le côté
// suisse et `hydrateSmnHistoryFromSupabase` le recharge au démarrage,
// exactement comme /meteofrance-history et /aemet-history. Le METAR
// garde sa dispense — mais elle tient au découpage en lots du poll,
// pas à la générosité de l'API (cf. METAR_ROW_BUDGET).
// Extrait de la route (lot 7) : /phenomenon-delta trace sa courbe avec
// EXACTEMENT les mêmes points que la fiche. Renvoie null si l'id n'est
// pas d'une source de pression, ce que l'appelant traduit à sa façon —
// un 400 pour la route, une courbe vide pour le calcul interne.
function pressureHistoryPayload(raw, hoursParam) {
  const sep = String(raw || '').indexOf(':');
  const source = sep > 0 ? String(raw).slice(0, sep) : '';
  const code = sep > 0 ? String(raw).slice(sep + 1) : '';
  const hours = Number.isFinite(hoursParam) ? Math.min(Math.max(hoursParam, 0), 36) : 36;
  const cutoff = Date.now() - hours * 3600 * 1000;

  if (source === 'metar') {
    const pts = (metarHistory.get(code) || []).filter(p => p.t >= cutoff);
    return { id: raw, reduction: 'qnh', resolutionHpa: 1, points: pts };
  }
  if (source === 'smn') {
    const pts = (smnHistory.get(code) || []).filter(p => p.t >= cutoff);
    // Comme dans pressureStationsPayload : la convention est celle de la
    // STATION, pas de la source. Visp et St-Gall sont en repli QNH. Le
    // `reduction` de chaque point fait foi ; celui-ci n'est que le
    // résumé de la station, tiré du cache d'observations.
    const red = smnObsCache.get(code)?.reduction ?? pts[pts.length - 1]?.reduction ?? 'qff';
    return { id: raw, reduction: red, resolutionHpa: 0.1, points: pts };
  }
  return null;
}

app.get('/pressure-history/:id', (req, res) => {
  const out = pressureHistoryPayload(req.params.id, Number(req.query.hours));
  if (!out) return res.status(400).json({ error: "id attendu sous la forme 'metar:LIMW' ou 'smn:LUG'" });
  res.json(out);
});

// ══════════════════════════════════════════════════════════════════
//  Lot 7 — LE Δ MESURÉ D'UN PHÉNOMÈNE (route B)
//
//  Le problème que cette route supprime : la fiche et le serveur ne
//  calculaient pas le même Δ. Le serveur soustrayait deux pressions MSL
//  du modèle GFS AUX COORDONNÉES DES VILLES ; la fiche lisait les
//  STATIONS déclarées, ramenait tout en QFF, corrigeait l'altitude et
//  pondérait l'incertitude. Ce ne sont pas deux approximations du même
//  nombre, ce sont deux nombres — la fiche pouvait afficher « au-dessus
//  du seuil » pendant que le serveur se taisait, et l'inverse.
//
//  Désormais c'est le serveur qui calcule, avec la physique de la
//  fiche (lib/pressure.cjs), et la fiche consomme. Il possédait déjà
//  toute la matière : METAR et SwissMetNet en RAM, Météo-France et
//  AEMET dans leurs caches. Il ne lui manquait que la physique.
//
//  ⚠️ CETTE ROUTE NE REND QUE DU MESURÉ. L'alerte, elle, se déclenche
//  sur le pic PRÉVU à 36 h (foehnServerPeak) — le foehn s'anticipe la
//  veille, c'est un choix assumé. Les deux séries ne doivent jamais
//  être confondues, et aucun champ de cette réponse ne mélange les deux.
//
//  Lecture publique, comme /pressure-stations : de la donnée
//  d'observation agrégée, rien de personnel.
// ══════════════════════════════════════════════════════════════════

// Cache des phénomènes. Motif identique à celui du front de rafales :
// une lecture Supabase PAR REQUÊTE, pour une donnée strictement
// identique pour tout le monde et qui change une fois par mois, c'est
// le piège qui a déjà coûté cher à ce projet (cf. BUGS.md 19/07).
let foehnAxesCache = [];
let foehnAxesFetchedAt = 0;
const FOEHN_AXES_TTL_MS = 10 * 60 * 1000;

async function getFoehnAxes() {
  if (foehnAxesCache.length && (Date.now() - foehnAxesFetchedAt) < FOEHN_AXES_TTL_MS) return foehnAxesCache;
  const rows = await sbGet('foehn_axes', 'select=*');
  if (Array.isArray(rows)) { foehnAxesCache = rows; foehnAxesFetchedAt = Date.now(); }
  // En cas d'échec on garde le cache précédent : une veille qui tourne
  // sur des seuils d'il y a dix minutes vaut mieux qu'une veille muette.
  return foehnAxesCache;
}

/** LE référentiel, fondu exactement comme AppContext le fond. */
function pressureReferential() {
  return PRESSURE.buildPressureReferential(
    pressureStationsPayload(), mfStationsPayload(), aemetStationsPayload(),
  );
}

/** Historique d'une ancre, quelle que soit sa source. */
async function historyForStation(st) {
  const src = String(st.id).split(':')[0];
  if (src === 'metar' || src === 'smn') {
    return (pressureHistoryPayload(st.id, OBSERVED_HOURS) || {}).points || [];
  }
  if (src === 'mf') return mfHistoryPoints(st.code, OBSERVED_HOURS);
  if (src === 'aemet') return aemetHistoryPoints(st.code, OBSERVED_HOURS);
  return [];
}

// Cache court : les relevés bougent toutes les 10 à 30 min selon la
// source, recalculer à chaque ouverture de fiche n'apporterait rien.
const phenomenonDeltaCache = new Map(); // id -> { ts, payload }
const PHENOMENON_DELTA_TTL_MS = 2 * 60 * 1000;

app.get('/phenomenon-delta/:id', async (req, res) => {
  try {
    const id = String(req.params.id || '');
    const cached = phenomenonDeltaCache.get(id);
    if (cached && (Date.now() - cached.ts) < PHENOMENON_DELTA_TTL_MS) {
      return res.json({ ...cached.payload, cached: true });
    }
    const rows = await getFoehnAxes();
    const row = rows.find(r => r.id === id);
    if (!row) return res.status(404).json({ error: 'phénomène inconnu' });

    const payload = await computePhenomenonDelta({
      row,
      referential: pressureReferential(),
      historyFor: historyForStation,
      // Le seuil du COMPTE n'est pas lu ici : cette route est publique
      // et n'a pas de session. Elle rend le seuil du phénomène ; c'est
      // au client d'appliquer l'éventuel seuil personnel par-dessus,
      // avec la même fonction (phenomenonLevel), donc sans divergence.
      userOverride: null,
    });
    phenomenonDeltaCache.set(id, { ts: Date.now(), payload });
    res.json({ ...payload, cached: false });
  } catch (e) {
    console.error('phenomenon-delta error:', e.message);
    res.status(500).json({ error: 'calcul impossible' });
  }
});

// ── Diagnostic des buffers de pression (public, lecture seule) ───────
// Ajouté le 04/08/2026. Raison d'être : le buffer d'historique était
// tombé à ~5 h au lieu de 30 h et il a fallu huit requêtes manuelles
// sur /pressure-history pour s'en apercevoir, puis une demi-heure pour
// comprendre que la cause n'était pas celle qu'on croyait. Cette route
// rend la même mesure en un coup d'œil, depuis le navigateur, sans
// redéployer.
//
// Ce qu'il faut y lire : `spanH` par ancre. Une étendue courte sur
// TOUTES les ancres d'une source = un problème de processus (plafond
// de l'API, redémarrage, poll cassé). Une étendue courte sur une seule
// = la station se tait, ce qui est normal la nuit sur un aérodrome
// fermé (LIPB entre 21 h et 04 h UTC, cas documenté).
//
// Aucune auth : ne rend que des compteurs et des horodatages sur de la
// donnée publique — même politique que /lightning-strikes.
app.get('/pressure-diag', (req, res) => {
  const now = Date.now();
  const decrire = (map, ids) => ids.map(id => {
    const arr = map.get(id) || [];
    return {
      id,
      points: arr.length,
      spanH: pressureHistorySpanH(map, id),
      oldest: arr.length ? arr[0].t : null,
      newest: arr.length ? arr[arr.length - 1].t : null,
      ageMin: arr.length ? Math.round((now - arr[arr.length - 1].t) / 60000) : null,
    };
  });
  const metar = decrire(metarHistory, METAR_ANCHORS);
  const smn = decrire(smnHistory, SMN_ANCHORS);
  const mediane = liste => {
    const v = liste.map(e => e.spanH).filter(h => h != null).sort((a, b) => a - b);
    return v.length ? v[Math.floor(v.length / 2)] : null;
  };
  res.json({
    now,
    metar: {
      anchors: METAR_ANCHORS.length,
      medianSpanH: mediane(metar),
      fetchedAt: metarFetchedAt,
      deepDoneAt: metarDeepDoneAt,
      deepBatches: metarBatches(METAR_ANCHORS, METAR_BOOT_HOURS).length,
      rowBudget: METAR_ROW_BUDGET,
      lastError: metarLastError,
      stations: metar,
    },
    smn: {
      anchors: SMN_ANCHORS.length,
      medianSpanH: mediane(smn),
      fetchedAt: smnFetchedAt,
      lastError: smnLastError,
      stations: smn,
    },
    retentionH: METAR_RETENTION_MS / 3600000,
    expectedSpanH: METAR_BOOT_HOURS,
  });
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
        // Débogage 16/07/2026 (demande Yann) — option orientation, même
        // politique défensive que `source` ci-dessus : colonnes pas
        // encore créées tant que Yann n'a pas exécuté
        // supabase_watch_orientation.sql, PostgREST les ignore
        // silencieusement côté insert simple, aucune casse avant.
        dir_enabled: w.dirEnabled ?? false,
        dir_sectors: Array.isArray(w.dirSectors) ? w.dirSectors : [],
        // Lot 4 « Surveiller ce site » (07/08/2026) — la clé du
        // décollage dont le geste a créé cette ligne, ou null si le
        // pilote l'a posée à la main.
        //
        // ⚠️ AJOUTÉE SEULEMENT SI LE CLIENT LA FOURNIT, et ce `if` est
        // la garde de migration : tant que le client n'a pas basculé
        // ORIGIN_SITE_SQL_DONE, il ne l'envoie pas, la clé n'apparaît
        // pas dans la ligne, et PostgREST ne voit rien d'inconnu. Un
        // `origin_site: w.originSite ?? null` inconditionnel ferait
        // refuser le lot ENTIER avant l'exécution de
        // supabase_step37_origin_site.sql — c'est-à-dire toute la veille
        // du compte, pas seulement le groupe du site.
        ...(w.originSite !== undefined ? { origin_site: w.originSite ?? null } : {}),
        updated_at: new Date().toISOString(),
      }));
      // ⚠️ Débogage 07/08/2026 — le retour de sbUpsert était JETÉ, et
      // /sync répondait `success: true` quoi qu'il arrive.
      //
      // sbUpsert rend `r.ok`, il ne lève pas : un lot refusé par
      // PostgREST (typiquement le CHECK sur `source`, qui n'accepte que
      // pioupiou/meteofrance/aemet tant que le script d'élargissement
      // n'a pas tourné) ressortait donc comme un succès. Conséquence :
      // le pilote voit sa balise « surveillée » dans l'app alors
      // qu'AUCUNE ligne n'existe en base et qu'aucune alerte ne partira
      // jamais. Sur un outil de sécurité, une surveillance qui se croit
      // active est pire qu'une surveillance absente — c'est le même
      // raisonnement que le témoin `.r2ok` de model-verif : un envoi qui
      // échoue ne doit pas pouvoir sortir en vert.
      //
      // Le nouveau réseau winds.mobi passe exactement par ce chemin :
      // sans ce garde, une balise Holfuy cochée avant l'exécution de
      // supabase_step36 serait silencieusement perdue.
      const ok = await sbUpsert('user_watched', rows, 'user_id,beacon_id,source');
      if (!ok) {
        // On ne supprime RIEN : la liste envoyée n'a pas pu être écrite,
        // la remplacer par elle-même effacerait la seule copie valide
        // (celle déjà en base) au profit d'un état qu'on n'a pas su
        // enregistrer.
        console.error(`⛔ Sync ${user.email || user.id.slice(0, 8)} — upsert user_watched REFUSÉ (${rows.length} ligne(s)), suppression annulée`);
        return res.status(502).json({
          error: "La liste de surveillance n'a pas pu être enregistrée sur le compte. Elle reste active sur cet appareil.",
          sources: [...new Set(rows.map(r => r.source))],
        });
      }
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
  const { access_token, beacon_id, origin_site } = req.body;
  const user = await verifyUser(access_token);
  if (!user) return res.status(401).json({ error:'Session invalide ou expirée' });

  // ── Lot 5 : acquitter un push GROUPÉ ─────────────────────────────
  // Décision Yann (08/08) : « le groupe, rappel maintenu si ça monte, et
  // surtout pour l'évènement ». Un push groupé décrivait N balises d'un
  // même site pour UN signal : l'acquitter acquitte ces N balises, pour
  // CE signal-là seulement — pas les autres signaux du même site, pas
  // les autres sites. Toute autre lecture ferait re-sonner le pilote pour
  // quelque chose qu'il vient de lire.
  // ⚠️ Acquitter ne fige rien : une balise de PLUS qui franchit son seuil
  // repousse malgré l'acquittement (cf. `force` dans evaluateFwSignal).
  if (origin_site) {
    const at = new Date().toISOString();
    // 1. Le cycle du GROUPE — c'est lui qui décide des rappels.
    const okGroup = await sbUpsert('user_flightwatch_alerts', {
      user_id: user.id, scope: `site:${origin_site}`, signal: 'wind_threshold',
      level: 2, alert_acked_at: at, updated_at: at,
    }, 'user_id,scope,signal');
    // 2. L'état INDIVIDUEL, pour que l'affichage suive : l'observation
    //    reste par balise, la dédup ne coupe que le réveil.
    await sbPatch(
      'user_watched',
      `user_id=eq.${user.id}&origin_site=eq.${encodeURIComponent(String(origin_site))}`,
      { alert_acked_at: at }
    );
    if (!okGroup) return res.status(500).json({ error:'Échec acquittement' });
    console.log(`🔕 Ack ${user.email||user.id.slice(0,8)} — site ${origin_site}`);
    return res.json({ success:true });
  }

  if (!beacon_id) return res.status(400).json({ error:'beacon_id ou origin_site manquant' });
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

// ══════════════════════════════════════════════════════════════════
//  Alarme foehn (Lot foehn) — différentiel de pression mer par axe
//
//  Anticipe le foehn via Δ = pressure_msl(A) − pressure_msl(B) entre deux
//  villes (table foehn_axes), sur la PRÉVISION : l'alarme regarde le PIC à
//  venir (~36 h), pas seulement l'instant présent. Modèle gfs_seamless :
//  couverture totale, cohérent sur des points distants (choix atmosoar) et
//  le bon niveau pour un gradient MSLP synoptique de ~100+ km. Le client
//  affiche, lui, le modèle le plus fin de sa cascade — un léger écart
//  d'affichage vs alarme est donc possible (documenté ROADMAP). Convention
//  Δ = A − B ; le signe = la direction (l'air redescend chaud/rafaleux côté
//  basse pression). ⚠️ Le foehn est un DANGER pour le vol — push = non-vol.
// ══════════════════════════════════════════════════════════════════
const FOEHN_HPA_VALLEY = 4;   // |Δ| ≥ → foehn dans les vallées (niveau 2, vigilance)
const FOEHN_HPA_PLAIN  = 8;   // |Δ| ≥ → foehn en plaine (niveau 3, danger)
const FOEHN_FORECAST_HORIZON_MS = 36 * 3600 * 1000; // fenêtre d'anticipation du pic
const FOEHN_CACHE_TTL_MS = 30 * 60 * 1000;          // MSLP prévu bouge lentement
const FOEHN_ALERT_REPEAT_MS = 3 * 3600 * 1000;      // c'est une prévision : rappel espacé, pas minute par minute

// ⚠️ INTERRUPTEUR DE BASCULE — « un phénomène coché suit l'armement de
// la veille » (lot 3 « Surveiller ce site », 07/08/2026).
//
// CE QUI CHANGE. Jusqu'ici, une ligne `user_foehn_watch.active` suffisait
// à recevoir un push : le foehn s'anticipe la veille, l'opt-in ÉTAIT la
// ligne, et le « Démarrer la surveillance » ne la concernait pas. Le
// geste « Surveiller ce site » arme des phénomènes EN LOT, sans que le
// pilote les ait ouverts un par un — le même raisonnement ne tient plus :
// il faut un seul interrupteur maître, celui que le pilote connaît déjà.
//
// POURQUOI UN INTERRUPTEUR ET PAS UN COMMIT. Personne ne doit perdre une
// alerte sans l'avoir su. L'app affiche d'abord un bandeau aux comptes
// concernés (phénomène coché + veille non démarrée) ; Yann met
// FOEHN_REQUIRE_ARMED=1 sur Render quand l'annonce a assez tourné, et
// peut revenir en arrière en une variable d'environnement, sans
// redéploiement de code.
//
// ⚠️ Ceci ne coupe QUE le push. L'état d'alerte reste écrit dans tous les
// cas (cf. `notify` dans evaluateFwSignal) : la fiche du phénomène
// continue de montrer ce qui se passe vraiment, veille armée ou non.
// Un pilote qui regarde voit ; c'est le réveil qui demande d'être armé.
const FOEHN_REQUIRE_ARMED = process.env.FOEHN_REQUIRE_ARMED === '1';

const foehnDiffCache = new Map(); // axisId -> { ts, diff:{ times, diff } }

// Différentiel Δ = pmsl(A) − pmsl(B) prévu (GFS), deux points en une requête.
// Cache court par axe (mutualisé entre comptes surveillant le même axe).
async function fetchFoehnDiffServer(axis) {
  const cached = foehnDiffCache.get(axis.id);
  if (cached && (Date.now() - cached.ts) < FOEHN_CACHE_TTL_MS) return cached.diff;
  const url = `${OPEN_METEO_URL}?latitude=${axis.a_lat},${axis.b_lat}` +
    `&longitude=${axis.a_lon},${axis.b_lon}` +
    // forecast_days : 2 → 3 le 04/08/2026. La fenêtre d'anticipation est
    // de 36 h (FOEHN_FORECAST_HORIZON_MS) mais Open-Meteo compte ses
    // journées depuis 00:00 UTC : à 2 jours, l'horizon réellement
    // couvert tombait de 48 h le matin à 24 h le soir. Un pic prévu
    // pour le lendemain après-midi sortait donc de la fenêtre en fin de
    // journée — exactement le moment où un pilote prépare sa sortie.
    `&hourly=pressure_msl&models=gfs_seamless&forecast_days=3&timezone=UTC`;
  try {
    const r = await fetch(url);
    const j = await r.json();
    if (!Array.isArray(j) || j.length < 2) return null;
    const a = j[0], b = j[1];
    const times = (a?.hourly?.time || []).map(t => new Date(`${t}Z`).getTime());
    const pa = a?.hourly?.pressure_msl || [];
    const pb = b?.hourly?.pressure_msl || [];
    const diff = times.map((_, i) => (pa[i] == null || pb[i] == null) ? null : pa[i] - pb[i]);
    const out = { times, diff };
    foehnDiffCache.set(axis.id, { ts: Date.now(), diff: out });
    return out;
  } catch { return null; }
}

// Pic le plus défavorable (|Δ| max) entre maintenant et l'horizon d'anticipation.
// Renvoie { time, diff, level, direction } ou null.
//
// ⚠️ RÉVISION DU 04/08/2026 — deux paramètres AJOUTÉS, et ils changent
// qui reçoit une alerte :
//
//  • `thresholdStrong` : le niveau 3 était calé sur FOEHN_HPA_PLAIN = 8,
//    la constante globale de la v1. Or un vent de gap est en danger à
//    4 hPa, pas à 8. Le niveau 3 (push `requireInteraction`, voix) ne
//    partait donc JAMAIS sur les 13 vents de gap.
//
//  • `activeSign` : le sens que le PHÉNOMÈNE autorise (colonne ajoutée
//    à l'étape 29) n'était pas lu ici. Le serveur alertait sur |Δ| dans
//    les deux sens dès que le pilote n'avait pas choisi de sens — donc
//    il ne distinguait pas le Südföhn du Nordföhn, qui partagent la
//    même mesure avec des signes opposés, et prévenait les pilotes du
//    Tessin les jours de foehn du sud (et réciproquement).
//
// Les deux filtres se COMPOSENT : `activeSign` dit ce que le phénomène
// permet, `wantDir` ce que le pilote surveille, et on ne retient qu'un
// pas qui satisfait les deux.
//
// ⚠️ RÉVISION DU LOT 7 — la RÈGLE DE NIVEAU n'est plus écrite ici.
// Elle était recopiée de `phenomenonLevel` (lib/phenomena.ts) : deux
// écritures du même seuil de sécurité, c'est-à-dire exactement ce que
// le commentaire du bloc foehn interdit. Le serveur APPELLE désormais
// celle de la fiche, via lib/pressure.cjs.
//
// Ce qui reste ici, et qui n'appartient qu'au serveur : le CHOIX DU
// PIC dans la fenêtre d'anticipation. `phenomenonLevel` juge un Δ ; il
// faut d'abord décider DE QUEL Δ on parle. Le pré-filtrage par signe
// sert à ça — sans lui, on choisirait le plus fort des deux versants
// puis on le jugerait nul, en manquant le pic du bon côté.
//
// `ph` est un phénomène mappé par `phenomenonFromRow`, pas une ligne
// brute : les replis de seuil ont déjà été appliqués, une seule fois,
// au même endroit que pour la fiche.
function foehnServerPeak(d, ph, wantDir = 'both', userOverride = null) {
  const now = Date.now();
  const hi = now + FOEHN_FORECAST_HORIZON_MS;
  const allowNeg = ph.activeSign !== 'pos' && wantDir !== 'toB'; // toA = Δ négatif
  const allowPos = ph.activeSign !== 'neg' && wantDir !== 'toA'; // toB = Δ positif
  let best = null;
  for (let i = 0; i < d.times.length; i++) {
    const t = d.times[i], v = d.diff[i];
    if (v == null || t < now || t > hi) continue;
    if (v < 0 && !allowNeg) continue;
    if (v > 0 && !allowPos) continue;
    if (best === null || Math.abs(v) > Math.abs(best.diff)) best = { time: t, diff: v };
  }
  if (!best) return null;
  best.level = PRESSURE.phenomenonLevel(best.diff, ph, userOverride);
  best.direction = PRESSURE.phenomenonDirection(best.diff, ph, userOverride);
  return best;
}

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

    // Étape 28 — positions des balises Pioupiou pour le ciblage du front
    // de rafales (couloir d'impact / ETA par balise). Alimentées ici,
    // depuis une réponse DÉJÀ récupérée : zéro requête réseau ajoutée.
    // Positions seulement, aucune mesure — ce cache ne sert qu'à de la
    // géométrie, il n'a pas à vieillir avec la donnée vent.
    Object.entries(releves).forEach(([id, rel]) => {
      if (Number.isFinite(rel.lat) && Number.isFinite(rel.lon)) {
        gfBeaconPositions.set(id, { lat: rel.lat, lon: rel.lon, nom: rel.nom });
      }
    });

    // winds.mobi (07/08/2026) — référentiel de dédoublonnage. Même
    // principe que gfBeaconPositions juste au-dessus : on se sert d'une
    // réponse DÉJÀ en main, aucune requête ajoutée. C'est la seule des
    // six sources du référentiel de dédup qui n'a pas de cache global,
    // d'où ce recopiage. Lu par windsmobiKnownGrid().
    pioupiouCoords = (d.data || [])
      .map(b => [b.location?.latitude, b.location?.longitude])
      .filter(([lat, lon]) => Number.isFinite(lat) && Number.isFinite(lon));

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
      // Débogage 17/07 (retour Yann : min/max pour les stations MF) — la
      // limitation "pas de rafale" est levée : obs.raf10 est déjà lu plus
      // haut (releves[mfId].raf), on le persiste ici aussi. `min` est
      // calculé (fwWindowMinFf, cf. définition) — pas une donnée native
      // MF, cf. commentaire de MF_MINMAX_WINDOW_MIN. Appelé AVANT le
      // fwRecordHistory de la boucle releves ci-dessous : lit encore le
      // buffer RAM tel qu'à l'issue du poll précédent.
      mfHistoryRows.push({ station_id: mfId, t: fwPollT, moy: obs.ff, raf: obs.raf10 ?? null, min: fwWindowMinFf(mfId, obs.ff), dir: obs.dd, pressure: obs.pmer ?? null });
    }
    mfPersistHistory(mfHistoryRows); // fire-and-forget — cf. définition, ne bloque/casse jamais la suite du poll

    // ── AEMET (Espagne), ajout 22/07/2026 : fusion des stations dans
    // `releves`, même format que Pioupiou/MF ci-dessus (demande Yann :
    // traiter EXACTEMENT comme les autres — surveillable/alertable, pas
    // le traitement affichage-seul retenu pour Infoclimat). aemetObsCache
    // est maintenu indépendamment (cf. refreshAemetData, poll 20 min) —
    // lecture pure ici, aucun appel réseau ajouté à ce poll. Pas de
    // persistance Supabase ici (contrairement au bloc MF ci-dessus) :
    // aemetPersistHistory est déjà appelée dans refreshAemetObs, avec les
    // VRAIS horodatages AEMET (fint) — écrire une deuxième famille de
    // lignes ici, à la cadence 5 min de CE poll, dupliquerait des valeurs
    // qui ne changent en réalité qu'une fois par heure côté source.
    for (const [aemetId, obs] of aemetObsCache) {
      if (obs.moy == null) continue; // pas de vent exploitable sur cette station
      // Garde-fraîcheur, même logique que MF_OBS_MAX_AGE_MS (seuil
      // proportionnellement plus large ici, cf. AEMET_OBS_MAX_AGE_MS).
      if (Date.now() - obs.t > AEMET_OBS_MAX_AGE_MS) continue;
      releves[aemetId] = {
        moy: obs.moy, raf: obs.raf, dir: obs.dir,
        pressure: obs.pressure,
        lat: obs.lat, lon: obs.lon, nom: obs.nom,
      };
    }

    // ══════════════════════════════════════════════════════════════
    // LOT « SURVEILLER CE SITE » — METAR, SMN, Infoclimat (07/08/2026)
    // ══════════════════════════════════════════════════════════════
    // Ces trois réseaux étaient AFFICHABLES mais pas SURVEILLABLES : ils
    // ont un cache à jour (metarObsCache / smnObsCache / infoclimatObsCache,
    // tous rafraîchis en tâche de fond) et ils sortent déjà par
    // /pressure-stations et /infoclimat-stations — mais personne ne les
    // versait dans `releves`, donc aucun seuil ne pouvait les évaluer.
    // Trois boucles, sur le modèle EXACT de MF et AEMET ci-dessus : la
    // logique en aval (seuils, signaux flightwatch) ne connaît pas la
    // source, et n'a pas à la connaître.
    //
    // Aucun appel réseau ajouté à ce poll — lecture pure des caches.
    //
    // ⚠️ VOLUMÉTRIE : ~609 stations de plus dans `releves` (546 Infoclimat,
    // 43 METAR, 20 SMN, mesuré le 08/08), soit ~+26 % sur le buffer RAM
    // `fwRecordHistory` juste en dessous, qui échantillonne TOUT `releves`
    // et pas seulement le surveillé. Même politique que MF/AEMET, qui
    // versent déjà tout leur réseau ; à surveiller si la RAM Render serre.

    // ── METAR ─────────────────────────────────────────────────────
    // DEUX PIÈGES, tous deux déjà documentés dans pressureStationsPayload :
    //
    //  1. `raf: null` ne veut PAS dire « rafale manquante » mais « pas de
    //     rafale significative » — la règle de codage OACI ne fait publier
    //     `wgst` que si la pointe dépasse le moyen de 10 kt. On le laisse
    //     donc à null SANS le remplacer par 0 : le test de dépassement
    //     (`rel.raf !== null && ...`, cf. plus bas) l'ignore proprement, là
    //     où un 0 serait une valeur mesurée et un `moy` recopié serait un
    //     mensonge. C'est aussi pour ça que le client grise le seuil de
    //     rafale d'une balise METAR : un seuil qu'on ne peut pas franchir
    //     ne doit pas se laisser régler.
    //
    //  2. `cadenceMin: 30`. Un METAR de 25 minutes d'âge est NORMAL, là où
    //     un Pioupiou de 25 minutes est mort. Le garde-fraîcheur est donc
    //     à 90 min (3 × cadence) et non aux 30 min de MF — sinon on
    //     jetterait la moitié des relevés valides. Conséquence à ASSUMER,
    //     et que le client DOIT dire au pilote : un dépassement de seuil
    //     peut être détecté avec une demi-heure de retard.
    //
    // `pressure` VOLONTAIREMENT à null (et pas o.qnh) : le QNH d'un METAR
    // est publié arrondi au hPa entier (`resolutionHpa: 1`). Le signal
    // « chute de pression » se déclenche à 2 hPa/h — sur une donnée
    // quantifiée au hPa, ça fait deux crans, et le bruit d'arrondi seul
    // peut les produire. On préfère aucune pression à une pression qui
    // fabrique des fausses alertes (budget ≤ 1 faux positif/mois).
    for (const [code, o] of metarObsCache) {
      if (o.moy == null) continue;                 // pas de vent exploitable
      if (o.lat == null || o.lon == null) continue; // même garde que le payload
      if (!Number.isFinite(o.t) || Date.now() - o.t > METAR_OBS_MAX_AGE_MS) continue;
      releves[`metar:${code}`] = {
        moy: o.moy, raf: o.raf ?? null, dir: o.dir ?? null,
        pressure: null,
        lat: o.lat, lon: o.lon, nom: o.nom,
      };
    }

    // ── SMN (SwissMetNet) ─────────────────────────────────────────
    // Le réseau le plus propre des trois : cadence 10 min, rafale publiée
    // sur TOUS les relevés (`fkl010z1`) — un `raf` null y est une vraie
    // lacune, pas une convention, contrairement au METAR juste au-dessus.
    // Pression au dixième de hPa : assez fine pour une dérivée, on la
    // verse. `reduction` (qff|qnh) est une propriété de la STATION et ne
    // change pas d'un poll à l'autre : une dérivée temporelle reste donc
    // homogène, ce qui est tout ce dont `fwRealPressureTrend` a besoin
    // (le piège FIA-3 était de MÉLANGER deux conventions sur une même
    // station, pas d'en utiliser une de bout en bout).
    for (const [code, o] of smnObsCache) {
      if (o.moy == null) continue;
      if (o.lat == null || o.lon == null) continue;
      if (!Number.isFinite(o.t) || Date.now() - o.t > SMN_OBS_MAX_AGE_MS) continue;
      releves[`smn:${code}`] = {
        moy: o.moy, raf: o.raf ?? null, dir: o.dir ?? null,
        pressure: o.p ?? null,
        lat: o.lat, lon: o.lon, nom: o.nom,
      };
    }

    // ── Infoclimat ────────────────────────────────────────────────
    // Ouvertes à la surveillance le 07/08/2026 (décision Yann), ce qui
    // REVIENT SUR l'en-tête de supabase_step24 (« stations amateur, jamais
    // rendues watchable »). L'argument de Yann : ces données sont fiables,
    // on les prend simplement EN DERNIER — l'ordre de priorité réseau
    // (Pioupiou > MF > AEMET/SMN/METAR > Infoclimat) vit côté client, dans
    // la sélection du geste « Surveiller ce site ». Mesuré le 08/08 : avec
    // cet ordre, Infoclimat n'est retenu que sur 16 % des sites, et il est
    // la SEULE balise dans 15 km sur 65 décollages — c'est exactement le
    // « au cas où » visé.
    //
    // ⚠️ 537 stations sur 546 ne publient AUCUNE rafale (98 %, mesuré le
    // 08/08 ; le serveur le documentait déjà à ~ligne 4424). Même
    // traitement que le METAR : `raf` reste null, jamais 0, jamais `moy`
    // recopié — et le client grise le seuil de rafale, parce qu'un seuil
    // qui ne peut pas se déclencher ne doit pas se laisser régler.
    for (const [icId, obs] of infoclimatObsCache) {
      if (obs.moy == null) continue;
      const meta = infoclimatStationsById.get(icId);
      if (!meta || meta.lat == null || meta.lon == null) continue;
      if (!Number.isFinite(obs.t) || Date.now() - obs.t > INFOCLIMAT_OBS_MAX_AGE_MS) continue;
      releves[icId] = {
        moy: obs.moy, raf: obs.raf ?? null, dir: obs.dir ?? null,
        pressure: obs.pressure ?? null,
        lat: meta.lat, lon: meta.lon, nom: meta.nom,
      };
    }

    // ── winds.mobi (07/08/2026) ───────────────────────────────────
    // Même moule que les cinq boucles ci-dessus : lecture pure d'un
    // cache maintenu en tâche de fond, aucun appel réseau ajouté à ce
    // poll. Les ids portent leur réseau d'origine
    // (`holfuy-1235`, `ffvl-2820`) — collision impossible avec les
    // espaces Pioupiou/MF/AEMET/Infoclimat par construction, comme pour
    // `metar:`/`smn:`.
    //
    // `pressure` toujours null, cf. la note de refreshWindsmobiProviders.
    //
    // ⚠️ VOLUMÉTRIE : ~910 balises de plus dans `releves` (mesuré le
    // 07/08 après dédup), qui s'ajoutent aux ~609 du lot du 08/08. Le
    // buffer RAM fwRecordHistory juste en dessous échantillonne TOUT
    // `releves`, pas seulement le surveillé : c'est le poste à surveiller
    // si la RAM Render serre, et la première chose à réduire (filtrer sur
    // les balises effectivement surveillées) si ça arrive.
    for (const [wmId, obs] of windsmobiObsCache) {
      if (obs.moy == null) continue;
      if (obs.lat == null || obs.lon == null) continue;
      if (!Number.isFinite(obs.t) || Date.now() - obs.t > WINDSMOBI_OBS_MAX_AGE_MS) continue;
      releves[wmId] = {
        moy: obs.moy, raf: obs.raf ?? null, dir: obs.dir ?? null,
        pressure: null,
        lat: obs.lat, lon: obs.lon, nom: obs.nom,
      };
    }

    // Historique flightwatch (Lot 1, +pressure Lot 2b) : un échantillon par
    // balise réelle à chaque poll, AVANT d'ajouter la balise de test
    // (fictive, pas de dérive physique à surveiller). Sert aux dérivées
    // vent/direction/pression ci-dessous (fwBaselineAt / fwRealPressureTrend).
    // fwPollT hoisté plus haut (avant la boucle MF, Lot 8) — inchangé ici.
    Object.entries(releves).forEach(([id, rel]) => {
      // raf/min (débogage 17/07) : ajoutés pour que le buffer RAM (points
      // les plus récents servis par /meteofrance-history) porte les mêmes
      // champs que mf_station_history — sinon les points tout juste polled
      // resteraient sans raf/min tant que la table persistante n'a pas
      // pris le relais. Sans effet sur les balises Pioupiou (cette route
      // ne les sert jamais, cf. fetchHistory côté client).
      fwRecordHistory(id, { t: fwPollT, moy: rel.moy, raf: rel.raf ?? null, min: fwWindowMinFf(id, rel.moy), dir: rel.dir, pressure: rel.pressure });
    });
    const testData = await sbGet('test_beacon', 'id=eq.singleton&select=*');
    const test = testData?.[0];
    if (test?.enabled) releves['__test__'] = { moy:test.wind_avg, raf:test.wind_max, nom:'🧪 '+(test.label||'Balise de test') };

    let watchedRows = await sbGet('user_watched', 'select=*');
    if (!Array.isArray(watchedRows)) watchedRows = [];
    // Lot foehn : la veille foehn est par AXE (user_foehn_watch), indépendante
    // des balises surveillées — on ne coupe court que si NI balise NI axe
    // n'est surveillé, sinon un compte qui ne veille QUE le foehn serait
    // ignoré.
    //
    // ⚠️ 07/08/2026 — cette clause DOIT rester, même après la bascule
    // FOEHN_REQUIRE_ARMED. La tentation était de la resserrer sur les
    // seuls comptes armés ; ce serait faux dans les deux sens. Un compte
    // ARMÉ qui ne veille que des phénomènes (aucune balise dans 15 km :
    // 37 % des décos) n'aurait plus jamais d'alerte, et un compte non
    // armé cesserait de voir l'ÉTAT de ses phénomènes dans la fiche,
    // alors que l'état a toujours été écrit indépendamment du push
    // (cf. `notify` dans evaluateFwSignal). Ce que la bascule coupe,
    // c'est le réveil — pas l'observation.
    const foehnWatchRows = await sbGet('user_foehn_watch', 'select=*');
    const anyFoehnWatch = Array.isArray(foehnWatchRows) && foehnWatchRows.some(w => w.active);
    if (!watchedRows.length && !anyFoehnWatch) { console.log('Aucune balise ni axe foehn surveillé'); return; }

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
      'select=user_id,active,sig_wind_surge,sig_breeze_reversal,sig_pressure_drop,sig_convection,sig_vigilance,sig_lightning,sig_precip,sig_freezing_level,lightning_radius_km,wind_surge_factor,wind_surge_window_min,pressure_drop_hpa_h,voice_enabled,beta_lightning');
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

    // ── Lot C flightwatch : précipitations observées (radar RainViewer) ──
    // Rafraîchit le cache des tuiles radar France si au moins un compte a
    // démarré la surveillance (et kill switch ON) ; sinon vide le cache
    // pour libérer la RAM. Défensif : refresh KO → cache inchangé/vide →
    // signal simplement non évalué plus bas, jamais de crash.
    // Rafraîchit dès qu'AU MOINS UNE balise est surveillée (pas seulement
    // si un compte a démarré) : l'état précip doit être RÉEL sur toute
    // balise surveillée/favorite, même veille non démarrée (règle 13/07,
    // cf. VEILLE_METEO_EXPLICATION §« affichage vs notifications »).
    if (FW_PRECIP_ENABLED && watchedRows.length > 0) await fwPrecipRefresh();
    else fwPrecipClear();

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
    // `notify` (règle produit 13/07) : sépare l'AFFICHAGE de la NOTIFICATION.
    // L'état d'alerte (alert_active) est TOUJOURS écrit → toute balise
    // surveillée/favorite montre l'état réel de ses signaux, même veille
    // non démarrée. Le PUSH n'est envoyé que si notify=true (= surveillance
    // démarrée). La voix, elle, est déjà bloquée côté client par le même
    // bouton. `notify` absent → traité comme false (défensif).
    // `force` (lot 5) : information NEUVE à l'intérieur d'un épisode déjà
    // en cours — typiquement une balise de PLUS qui franchit son seuil sur
    // le même site. Elle traverse l'intervalle de rappel ET l'acquittement,
    // parce que le pilote a acquitté ce qu'il avait LU, pas ce qui vient de
    // s'ajouter. Absent chez tous les autres appelants → undefined →
    // comportement d'avant, à l'identique.
    async function evaluateFwSignal({ userId, scope, signal, level, active, buildPush, repeatMs, notify, force }) {
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

      // Signal DÉTECTÉ. Décision d'envoi de push — uniquement si notify.
      let sent = false;
      if (notify) {
        const lastSent = row?.alert_last_sent ? new Date(row.alert_last_sent).getTime() : 0;
        const justActivated = !row?.alert_active;
        const acked = row?.alert_acked_at && new Date(row.alert_acked_at).getTime() >= lastSent;
        const repeatWindow = repeatMs || FW_ALERT_REPEAT_MS; // anti-répétition par défaut 15 min, surchargée par signal (ex. foudre 10 min, Lot 5)
        const dueForSend = force || justActivated || (now - lastSent) >= repeatWindow;
        if (!(acked && !justActivated && !force) && dueForSend) {
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
          sent = true;
        }
      }

      // État TOUJOURS persisté (affichage temps réel). alert_last_sent n'est
      // mis à jour QUE si un push vient d'être envoyé — merge-duplicates
      // conserve les colonnes omises, donc l'horodatage d'un épisode
      // précédent n'est pas écrasé quand on ne fait que rafraîchir l'état.
      const patch = { user_id: userId, scope, signal, level, alert_active: true, updated_at: new Date(now).toISOString() };
      if (sent) patch.alert_last_sent = new Date(now).toISOString();
      await sbUpsert('user_flightwatch_alerts', patch, 'user_id,scope,signal');
    }

    console.log(`${new Set(watchedRows.map(w=>w.user_id)).size} compte(s), ${watchedRows.length} surveillance(s), ${activeByUser.size} avec surveillance démarrée`);

    // Balises surveillées valides (lat/lon/dir connus) par compte actif
    // avec le signal bascule de brise activé — alimenté dans la boucle
    // ci-dessous, consommé juste après (§ bascule de brise).
    const watchedBeaconsByUser = new Map();

    // ── Lot 2/3 flightwatch : signaux Open-Meteo (mutualisés) ──────────
    // UNE requête par balise distincte surveillée par au moins un compte
    // avec sig_pressure_drop OU sig_convection activé — jamais par
    // (compte, balise), même principe que le mutualisme Pioupiou existant.
    // Un seul appel sert les deux signaux (cf. fetchOpenMeteoSignals) :
    // pas de requête séparée pour la convection (cadrage Lot 3). Récupérée
    // AVANT la boucle principale pour être disponible en lecture pure
    // (Map) dans la boucle, sans appel réseau par itération.
    //
    // Débogage 12/07/2026 — condition `activeByUser` RETIRÉE ici (elle
    // restait plus bas, pour les alertes elles-mêmes) : pressureSignalCache
    // (source+valeur affichée sur WatchCard) doit être alimenté même
    // surveillance ARRÊTÉE, sinon "en attente" s'affichait en permanence
    // tant que le pilote n'avait pas démarré la surveillance (retour
    // Yann) — c'est un affichage informatif, pas un effet de bord des
    // alertes.
    const weatherBeaconIds = new Set();
    for (const w of watchedRows) {
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

    // ── Lot 5 « Surveiller ce site » : le bocal ───────────────────────
    // Regroupement (compte, site) -> balises de ce site actuellement
    // au-dessus de leur seuil. Alimenté dans la boucle principale,
    // consommé juste après — exactement le patron (compte, département)
    // ci-dessus, et pour la même raison : la vigilance ne varie pas à
    // l'intérieur d'un département, un front ne varie pas à l'intérieur
    // d'un bocal de 15 km.
    //
    // Règle de Yann : « si les 5 balises repèrent le MÊME événement, on ne
    // le fait remonter QU'UNE FOIS ; si c'est une brise qui remonte et qui
    // tape les balises une par une, on informe à chaque fois — la séquence
    // EST l'information. » Les deux tiennent ensemble ici : un seul push
    // par site et par signal, MAIS relancé sans attendre dès qu'une balise
    // de plus tombe (`hasNewCrossing`). Une brise qui progresse fait donc
    // toujours autant de push qu'elle touche de balises ; un front qui
    // fait tout tomber d'un coup n'en fait qu'un.
    //
    // Ne concerne QUE les lignes venues du geste « Surveiller ce site »
    // (`origin_site` non nul). Une balise posée à la main garde son push
    // individuel : c'est la règle d'appartenance du lot 4.
    const windByUserSite = new Map();
    // decos.json (nom des sites) : chargé une fois par poll, hors de la
    // boucle. Échec = pas de nom, jamais d'erreur — cf. loadDecoNames.
    await loadDecoNames();

    for (const w of watchedRows) {
      const rel = releves[String(w.beacon_id)];
      if (!rel) continue;

      // ── Débogage 12/07/2026 — source/valeur de pression affichée ────
      // Déplacé ICI (AVANT le garde-fou "surveillance non démarrée"
      // ci-dessous) : pressureSignalCache alimente un affichage
      // INFORMATIF sur WatchCard (source + valeur de pression), pas une
      // alerte — il doit rester à jour même si le pilote n'a pas encore
      // démarré sa surveillance. Avant ce déplacement, la ligne pression
      // affichait "en attente" en permanence tant que la surveillance
      // n'était pas active (retour Yann). Priorité : baromètre embarqué
      // > station MF proche (cf. findNearbyMfStations) > modèle AROME
      // (weatherByBeacon, mutualisé plus haut) > aucune donnée.
      const fwWeather = weatherByBeacon.get(String(w.beacon_id));
      const fwPressureReal = fwRealPressureTrend(String(w.beacon_id), rel.pressure);
      let fwPressureNearby = null;
      let nearbyStationUsed = null;
      if (!fwPressureReal) {
        for (const cand of findNearbyMfStations(String(w.beacon_id), rel.lat, rel.lon)) {
          const obs = mfObsCache.get(cand.id);
          const trend = fwRealPressureTrend(cand.id, obs?.pmer ?? null);
          if (trend) { fwPressureNearby = trend; nearbyStationUsed = cand; break; }
        }
      }
      const fwPressure = fwPressureReal ?? fwPressureNearby ?? fwWeather?.pressure ?? null;
      // Écriture idempotente : plusieurs comptes surveillant la même
      // balise réécrivent la même valeur, sans coût réel.
      pressureSignalCache.set(String(w.beacon_id), {
        source: fwPressureReal ? 'sensor' : fwPressureNearby ? 'sensor_nearby' : fwWeather?.pressure ? 'model' : null,
        value: fwPressure?.now ?? null,
        rate: fwPressure?.rate ?? null,
        stationName: nearbyStationUsed?.nom ?? null,
        distanceKm: nearbyStationUsed ? Math.round(nearbyStationUsed.distanceKm) : null,
        updatedAt: Date.now(),
      });

      // Règle produit (13/07) : une balise surveillée/favorite affiche
      // l'ÉTAT RÉEL de ses signaux MÊME si la surveillance n'est pas
      // démarrée. « Démarrer la surveillance » ne débloque que les
      // NOTIFICATIONS (push) et la voix — pas l'évaluation. `notify` porte
      // ce gating : tous les signaux ci-dessous sont évalués quoi qu'il
      // arrive (l'état est écrit pour l'affichage), mais evaluateFwSignal
      // n'envoie de push que si notify=true. Le push de SEUIL vent, lui,
      // reste géré plus bas et gaté par ce même `notify`.
      const notify = activeByUser.has(w.user_id);

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
          userId: w.user_id, scope: String(w.beacon_id), signal: 'wind_surge', level: 3, active: surging, notify,
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
          userId: w.user_id, scope: String(w.beacon_id), signal: 'lightning', level: 3, active: strikeCount > 0, notify,
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

      // ── Lot C flightwatch : précipitations à proximité (radar) ──────
      // Écho de pluie détecté à <= FW_PRECIP_RADIUS_KM de la balise sur la
      // dernière image radar RainViewer. Niveau 2 (vigilance, §7.5 cadrage
      // "pression qui chute / convection") — push DOUX, pas de voix.
      // Donnée INDICATIVE (radar communautaire RainViewer, pas de SLA) : le
      // corps du push le dit. Cache vide (kill switch OFF, index KO,
      // démarrage) → false → pas d'alerte, jamais de crash. v1 sans pref
      // par compte : gaté par FW_PRECIP_ENABLED seul (cf. module plus haut).
      if (FW_PRECIP_ENABLED && fwPrefsForUser.sig_precip && rel.lat != null && rel.lon != null) {
        const { near: precipNear, distanceKm: precipDistanceKm } = fwPrecipNear(rel.lat, rel.lon, FW_PRECIP_RADIUS_KM);
        // Débogage 13/07/2026 (nice-to-have "valeur chiffrée dashboard") —
        // alimente precipSignalCache à CHAQUE poll (comme pressureSignalCache),
        // y compris quand rien n'est détecté (distanceKm repasse à null),
        // pour que WatchCard affiche la vraie distance à l'écho le plus
        // proche plutôt que le seul rayon configuré (qui ne bougeait jamais).
        precipSignalCache.set(String(w.beacon_id), { detected: precipNear, distanceKm: precipDistanceKm, updatedAt: Date.now() });
        const lbl = pushLabels(langByUser.get(w.user_id)).flightwatch.precip;
        await evaluateFwSignal({
          userId: w.user_id, scope: String(w.beacon_id), signal: 'precip', level: 2, active: precipNear, notify,
          buildPush: () => ({
            title: `🌧️ ${rel.nom}`,
            body: lbl.body(FW_PRECIP_RADIUS_KM),
            icon: '/apple-touch-icon.png', badge: '/apple-touch-icon.png',
            tag: `fw-precip-${w.beacon_id}`, requireInteraction: false,
            data: {
              url: '/', kind: 'flightwatch', signal: 'precip', level: 2,
              scope: String(w.beacon_id), voice: false,
              value: precipDistanceKm ?? FW_PRECIP_RADIUS_KM, unit: 'km',
            },
          }),
        });
      }

      // ── Lot 2/2b flightwatch : chute de pression rapide ────────────
      // Lot 2b : préfère la pression RÉELLE mesurée par le baromètre de la
      // balise (fwRealPressureTrend, beaconHistory) — repli sur une station
      // MF proche puis sur le modèle Open-Meteo (weatherByBeacon) seulement
      // si rien de mieux n'est disponible (cf. FW_PRESSURE_MIN_SAMPLES_SPAN_MIN).
      // fwPressure/fwWeather calculés plus haut (AVANT le garde-fou
      // "surveillance non démarrée", cf. débogage 12/07/2026 — sert aussi
      // à l'affichage informatif WatchCard, pas seulement à cette alerte).
      // Si aucune source n'est disponible : on N'ÉVALUE PAS ce poll-ci — ni
      // alerte ni reset — plutôt que de risquer un faux reset sur un simple
      // aléa réseau/capteur (§8 garde-fou "informer, pas juger"). Niveau 2
      // (vigilance, §7.5 cadrage : "pression qui chute").
      if (fwPrefsForUser.sig_pressure_drop && fwPressure?.rate != null) {
        const dropping = fwPressure.rate <= -fwPrefsForUser.pressure_drop_hpa_h;
        const lbl = pushLabels(langByUser.get(w.user_id)).flightwatch.pressureDrop;
        await evaluateFwSignal({
          userId: w.user_id, scope: String(w.beacon_id), signal: 'pressure_drop', level: 2, active: dropping, notify,
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
        // Débogage 13/07/2026 (nice-to-have "valeur chiffrée dashboard",
        // re-câblage suite retour Yann : le signal restait détecté/poussé
        // en push mais n'était plus affiché du tout dans le dashboard
        // depuis son retrait le 13/07 matin) — alimente convectionSignalCache
        // à chaque poll où une tendance CAPE est disponible, détecté ou non.
        convectionSignalCache.set(String(w.beacon_id), {
          detected: developing, capeJkg: Math.round(capeNow), capeRiseJkg: Math.round(capeRise), updatedAt: Date.now(),
        });
        // FIA-4 : deux couvertures 0-100% indépendantes ne s'additionnent
        // pas (elles se recouvrent partiellement) — Math.max() donne la
        // meilleure approximation de la fraction de ciel réellement couverte.
        // L'addition pouvait afficher "160%" dans le corps du push.
        const cloudLowMid = Math.round(Math.max(fwWeather.cloudLowNow ?? 0, fwWeather.cloudMidNow ?? 0));
        const freezingRounded = fwWeather.freezingLevelNow != null ? Math.round(fwWeather.freezingLevelNow) : null;
        const lbl = pushLabels(langByUser.get(w.user_id)).flightwatch.convection;
        await evaluateFwSignal({
          userId: w.user_id, scope: String(w.beacon_id), signal: 'convection', level: 2, active: developing, notify,
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
      // Débogage 16/07/2026 (demande Yann) — option orientation : "hors
      // zone" seulement si l'option est active, qu'au moins un secteur
      // favorable est enregistré (défensif — cf. commentaire WatchModal,
      // "aucun secteur coché" ne doit jamais spammer), que la direction
      // est connue, ET que le vent dépasse le plancher WATCH_DIR_MIN_WIND_KMH
      // (direction non significative par vent quasi nul, même garde-fou
      // que la bascule de brise). `dir_sectors` absent tant que Yann n'a
      // pas exécuté supabase_watch_orientation.sql -> Array.isArray
      // défensif, se comporte comme "option indisponible" (jamais de crash).
      const sectorNow = rel.dir != null ? watchDirToSector8(rel.dir) : null;
      const overDir = !!w.dir_enabled && Array.isArray(w.dir_sectors) && w.dir_sectors.length > 0
        && sectorNow !== null && rel.moy !== null && rel.moy >= WATCH_DIR_MIN_WIND_KMH
        && !w.dir_sectors.includes(sectorNow);
      const now = Date.now();

      // Push de SEUIL vent : reste lié au DÉMARRAGE de la surveillance
      // (comme avant ce changement). Surveillance arrêtée (!notify) → pas
      // de push seuil, on réarme l'état et on passe. L'affichage « seuil
      // dépassé » est calculé côté client, indépendamment.
      if (!notify) {
        if (w.alert_active || w.alert_acked_at) {
          await sbPatch('user_watched', `id=eq.${w.id}`, { alert_active: false, alert_acked_at: null });
        }
        continue;
      }

      if (!overM && !overR && !overDir) {
        // Repassé sous le seuil (et/ou revenu dans un secteur favorable) :
        // réarme l'alerte pour la prochaine fois (alert_active +
        // alert_acked_at remis à zéro). On ne touche pas alert_last_sent
        // (inutile, et garde une trace pour debug).
        if (w.alert_active) {
          await sbPatch('user_watched', `id=eq.${w.id}`,
            { alert_active: false, alert_acked_at: null });
        }
        continue;
      }

      // ── Lot 5 : une ligne venue d'un geste « Surveiller ce site » ne
      // pousse plus toute seule ────────────────────────────────────────
      // Elle est collectée ici et évaluée EN GROUPE après la boucle
      // (scope `site:<origin_site>`, signal `wind_threshold`). Son état
      // individuel continue d'être écrit exactement comme avant : la
      // dédup coupe le RÉVEIL, jamais l'OBSERVATION — WatchCard doit
      // continuer de montrer laquelle des cinq balises est au-dessus.
      if (w.origin_site) {
        const gkey = `${w.user_id}|${w.origin_site}`;
        const g = windByUserSite.get(gkey) || {
          userId: w.user_id, originSite: w.origin_site,
          beacons: [], repeatMin: null, hasNewCrossing: false,
        };
        g.beacons.push({
          id: String(w.beacon_id), nom: rel.nom,
          moy: overM ? rel.moy : null,
          raf: overR ? rel.raf : null,
          dirOut: overDir ? sectorNow : null,
        });
        // Le rappel du groupe est le PLUS COURT des réglages de ses
        // balises (décision Yann, 08/08) : sur un groupe, le doute se
        // tranche toujours du côté qui pousse.
        const rep = w.repeat_interval_min ?? 10;
        g.repeatMin = g.repeatMin === null ? rep : Math.min(g.repeatMin, rep);
        // « Ça monte » (décision Yann, 08/08 : « on surveille les
        // dépassements de seuil ») = une balise de PLUS qui franchit le
        // sien. `!w.alert_active` la désigne sans rien inventer : la
        // colonne retombe à false dès qu'une balise repasse sous son
        // seuil, donc « pas encore active ET au-dessus maintenant » = elle
        // vient de tomber. Aucun palier à calibrer, aucune valeur inventée
        // — et c'est précisément ce qui manquait côté vent.
        if (!w.alert_active) g.hasNewCrossing = true;
        windByUserSite.set(gkey, g);
        // Observation : l'état individuel est écrit même si le réveil est
        // délégué au groupe. `alert_last_sent` n'est PAS touché ici — le
        // cycle d'envoi du groupe vit dans user_flightwatch_alerts.
        if (!w.alert_active) {
          await sbPatch('user_watched', `id=eq.${w.id}`, { alert_active: true });
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
      // Débogage 16/07/2026 (demande Yann) — option orientation : ajoute
      // le secteur courant au corps du push, sur sa propre ligne pour ne
      // pas se mélanger visuellement avec moy/rafale (des points " · "
      // en trop rendraient la notif illisible sur un petit écran).
      if (overDir) body += `${body ? '\n' : ''}${lbl.dirOut} ${WATCH_SECTOR_8_LABELS[sectorNow]}`;

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

      // Débogage 13/07/2026 (nice-to-have "valeur chiffrée dashboard") —
      // l'angle de retournement (diff) était calculé puis jeté ici même
      // avant ce changement (juste utilisé pour filtrer) ; il est maintenant
      // conservé sur chaque balise qualifiée (reversalDeg) pour être exposé
      // à l'affichage (cf. breezeSignalCache plus bas), au lieu du
      // `value: null` codé en dur dans le push jusqu'ici.
      const reversed = beacons
        .map(b => {
          // FIA-2 : plancher de vitesse aux DEUX extrémités — si le vent est
          // quasi nul (baseline OU courant), la direction est aléatoire et un
          // retournement de 100°+ ne signifie rien aérologiquement.
          if (b.rel.moy == null || b.rel.moy < FW_BREEZE_REVERSAL_MIN_WIND_KMH) return null;
          const baseline = fwBaselineAt(b.beaconId, b.windowMin);
          if (!baseline || baseline.dir == null) return null;
          if (baseline.moy == null || baseline.moy < FW_BREEZE_REVERSAL_MIN_WIND_KMH) return null;
          const diff = fwAngularDiff(baseline.dir, b.rel.dir);
          if (diff === null || diff < FW_BREEZE_REVERSAL_MIN_DEG) return null;
          return { ...b, reversalDeg: diff };
        })
        .filter(Boolean);
      if (reversed.length < 2) continue;

      const clusters = fwClusterByProximity(reversed, FW_BREEZE_NEIGHBOR_RADIUS_KM);
      for (const cluster of clusters) {
        if (cluster.length < 2) continue;
        const anchor = cluster.map(b => b.beaconId).sort()[0];
        const scope = `zone:${anchor}`;
        fwBreezeActiveScopes.add(`${userId}|${scope}`);
        const names = cluster.map(b => b.rel.nom).join(', ');
        const lbl = pushLabels(langByUser.get(userId)).flightwatch.breezeReversal;
        // Angle représentatif du cluster pour le push : le plus marqué des
        // balises concernées (pire cas, cohérent avec "niveau 2 partout").
        const clusterAngleDeg = Math.round(Math.max(...cluster.map(b => b.reversalDeg)));
        await evaluateFwSignal({
          userId, scope, signal: 'breeze_reversal', level: 2, active: true, notify: activeByUser.has(userId),
          buildPush: () => ({
            title: lbl.title,
            body: lbl.body(names),
            icon: '/apple-touch-icon.png', badge: '/apple-touch-icon.png',
            tag: `fw-breeze_reversal-${scope}`, requireInteraction: false,
            data: {
              url: '/', kind: 'flightwatch', signal: 'breeze_reversal', level: 2,
              scope, voice: false, // niveau 2 = push doux, voix réservée niveau 3 (§7.5)
              value: clusterAngleDeg, unit: '°',
            },
          }),
        });
        // Débogage 13/07/2026 — en plus de la ligne ci-dessus (scope
        // `zone:<ancre>`, seule utilisée pour la notification et
        // l'anti-répétition), une ligne PAR BALISE du cluster (scope =
        // beacon_id) est écrite ici, SANS notification (le push est déjà
        // parti une seule fois au niveau du cluster ci-dessus — en écrire
        // une par balise spammerait autant de push que de balises
        // concernées). Cette ligne beacon_id est ce que WatchCard lit
        // (fwAlerts.filter(a => a.scope === w.id)) : avant cet ajout, le
        // scope `zone:...` ne matchait JAMAIS un id de balise brut, donc le
        // chip/point "détecté" de la bascule de brise ne s'allumait sur
        // AUCUNE carte, quelle que soit la balise — bug préexistant, corrigé
        // au passage (cf. BUGS.md).
        for (const b of cluster) {
          fwBreezeActiveScopes.add(`${userId}|${b.beaconId}`);
          breezeSignalCache.set(b.beaconId, { detected: true, angleDeg: Math.round(b.reversalDeg), updatedAt: Date.now() });
          await sbUpsert('user_flightwatch_alerts', {
            user_id: userId, scope: b.beaconId, signal: 'breeze_reversal', level: 2,
            alert_active: true, updated_at: new Date().toISOString(),
          }, 'user_id,scope,signal');
        }
      }
    }
    // Réarmement : toute portée (zone `zone:<ancre>` OU balise individuelle,
    // cf. ajout 13/07 ci-dessus) `breeze_reversal` active lors d'un poll
    // précédent mais non retrouvée ce poll-ci (le compte n'a pas de bascule
    // à collecter au-dessus, ou le cluster ne s'est pas reformé) est
    // remise à plat — même logique de réarmement silencieux que le reste.
    for (const row of (Array.isArray(fwAlertRows) ? fwAlertRows : [])) {
      if (row.signal !== 'breeze_reversal' || !row.alert_active) continue;
      if (fwBreezeActiveScopes.has(`${row.user_id}|${row.scope}`)) continue;
      breezeSignalCache.delete(row.scope); // no-op si row.scope est un "zone:..." (jamais une clé de ce cache)
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
          userId, scope, signal: 'vigilance', level, active, notify: activeByUser.has(userId),
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
    // ── Lot 5 « Surveiller ce site » : UN push par site et par SIGNAL ──
    // Décision structurante de Yann (08/08) : « surtout pour l'évènement !
    // Un orage qui s'approche peut déclencher plusieurs facteurs :
    // renversement de brise, convection, montée du vent… Il faut que
    // chaque paramètre soit indépendant dans l'annonce. »
    // D'où la clé (compte, SITE, SIGNAL) et pas (compte, site) : ce qu'on
    // interdit, c'est cinq push POUR LA MONTÉE DU VENT. Trois push pour
    // trois phénomènes différents sur le même site, eux, sont trois
    // informations et doivent passer. Le signal porté ici est
    // `wind_threshold` ; les autres gardent leurs propres scopes.
    //
    // Aucune fenêtre en minutes n'est introduite. Question posée à Yann :
    // en combien de temps une lombarde tape deux balises voisines ?
    // Réponse : « je n'en ai aucune idée » — donc on n'écrit pas un
    // chiffre qui aurait l'air de venir du terrain. Le regroupement
    // s'adosse au cycle de rappel qui existe déjà et que le pilote règle
    // lui-même (`repeat_interval_min`, le plus court du groupe).

    // Réarmement : un site dont plus AUCUNE balise n'est au-dessus n'est
    // pas dans windByUserSite, donc la boucle ci-dessous ne le verrait
    // jamais et sa ligne resterait alert_active=true pour toujours — le
    // prochain épisode ne serait plus « justActivated » et attendrait
    // l'intervalle de rappel au lieu de partir tout de suite. Or le
    // premier franchissement doit TOUJOURS pousser immédiatement
    // (décision Yann : « le 1er, il faut avertir tout de suite, le plus
    // tôt possible ! »). D'où cette passe, sur le modèle de celle de la
    // bascule de brise.
    for (const r of fwAlertMap.values()) {
      if (r.signal !== 'wind_threshold' || !r.alert_active) continue;
      if (typeof r.scope !== 'string' || !r.scope.startsWith('site:')) continue;
      if (windByUserSite.has(`${r.user_id}|${r.scope.slice(5)}`)) continue;
      await evaluateFwSignal({
        userId: r.user_id, scope: r.scope, signal: 'wind_threshold',
        level: r.level ?? 2, active: false, notify: false, buildPush: () => ({}),
      });
    }

    for (const g of windByUserSite.values()) {
      const scope = `site:${g.originSite}`;
      const lbl = pushLabels(langByUser.get(g.userId));
      const site = siteLabelFromKey(g.originSite);
      const n = g.beacons.length;
      // Le corps nomme CHAQUE balise et sa mesure. Un push groupé qui se
      // contenterait de « 3 balises au-dessus du seuil » retirerait au
      // pilote ce qu'il avait avant le lot 5 : savoir laquelle, et
      // combien. On groupe le réveil, on ne résume pas l'information.
      const detail = g.beacons.map(b => {
        const parts = [];
        if (b.moy != null) parts.push(`${lbl.avg} ${Math.round(b.moy)} km/h`);
        if (b.raf != null) parts.push(`${lbl.gust} ${Math.round(b.raf)} km/h`);
        if (b.dirOut != null) parts.push(`${lbl.dirOut} ${WATCH_SECTOR_8_LABELS[b.dirOut]}`);
        return `${b.nom} — ${parts.join(' · ')}`;
      }).join('\n');
      const footer = lbl.siteWind.footer(n);
      await evaluateFwSignal({
        userId: g.userId, scope, signal: 'wind_threshold', level: 2,
        active: true, notify: activeByUser.has(g.userId),
        repeatMs: g.repeatMin * 60 * 1000,
        force: g.hasNewCrossing,
        buildPush: () => ({
          title: lbl.siteWind.title(site, n),
          body: footer ? `${detail}\n${footer}` : detail,
          icon: '/apple-touch-icon.png', badge: '/apple-touch-icon.png',
          // Un tag PAR SITE : les push d'un même bocal se remplacent dans
          // le tiroir au lieu de s'y empiler, ce qui était toute la
          // nuisance que le plafond de 5 balises servait à contenir.
          tag: `alert-site-${g.originSite}`,
          data: {
            url: '/', kind: 'siteWatch', signal: 'wind_threshold',
            scope, originSite: g.originSite,
            beacons: g.beacons.map(b => b.id),
          },
        }),
      });
    }

    // ── Lot foehn : alarme différentiel de pression par AXE ───────────
    // Veille par axe (user_foehn_watch, déjà lu en tête pour le garde-fou
    // d'arrêt), mutualisée : un seul fetch OM par axe distinct surveillé.
    // Scope 'axis:<id>', réutilise le cycle user_flightwatch_alerts
    // (signal 'foehn'). L'alarme vise le PIC À VENIR (anticipation), pas
    // l'instant présent. Le push suivait autrefois la seule existence de
    // la ligne user_foehn_watch, indépendamment du "démarrage" de la
    // veille balises ; depuis le lot 3 « Surveiller ce site » il suit
    // l'interrupteur maître comme tous les autres signaux, sous
    // FOEHN_REQUIRE_ARMED. Push formulé DANGER (non-vol). Défensif :
    // table/axe absent -> réarmement silencieux, jamais de crash.
    if (anyFoehnWatch) {
      const foehnAxesRows = await getFoehnAxes();
      const foehnAxisById = new Map((Array.isArray(foehnAxesRows) ? foehnAxesRows : []).map(a => [a.id, a]));
      const wantedAxisIds = [...new Set(foehnWatchRows.filter(w => w.active).map(w => w.axis_id))];
      const foehnDiffByAxis = new Map();
      for (const axisId of wantedAxisIds) {
        const ax = foehnAxisById.get(axisId);
        if (!ax) continue;
        const dd = await fetchFoehnDiffServer(ax);
        if (dd) foehnDiffByAxis.set(axisId, dd);
      }
      for (const w of foehnWatchRows) {
        const scope = `axis:${w.axis_id}`;
        const ax = foehnAxisById.get(w.axis_id);
        const dd = foehnDiffByAxis.get(w.axis_id);
        if (!w.active || !ax || !dd) {
          // Axe retiré de la veille, ou données indisponibles ce poll-ci :
          // réarmement silencieux (aucun push), comme les autres signaux.
          await evaluateFwSignal({ userId: w.user_id, scope, signal: 'foehn', level: 2, active: false, buildPush: () => ({}) });
          continue;
        }
        // ⚠️ CORRECTIF 04/08/2026 — le repli n'est plus la constante
        // globale mais le SEUIL DU PHÉNOMÈNE. Avant, tout compte dont
        // la ligne ne portait pas de seuil explicite était veillé à
        // 4 hPa : le double du seuil réel d'un vent de gap (2 hPa), un
        // tiers de trop sur un axe pyrénéen (3). Côté client, cocher la
        // case écrivait justement 4 sans le dire — les deux défauts se
        // renforçaient, et les pilotes n'étaient jamais avertis sur
        // exactement les vents qu'ils surveillent.
        // Ordre voulu : seuil du compte > seuil du phénomène > global.
        //
        // ⚠️ RÉVISION DU LOT 7 — le repli n'est plus écrit ici. C'est
        // `phenomenonFromRow` (celui de la fiche, via lib/pressure.cjs)
        // qui décide qu'un seuil absent vaut 4 et un seuil fort absent
        // 8. Le serveur le décidait de son côté avec un `||` là où la
        // fiche utilise `??` : sur un seuil à 0 les deux ne disaient
        // déjà pas la même chose. Une seule écriture, un seul repli.
        const ph = PRESSURE.phenomenonFromRow(ax);
        // Le seuil du COMPTE reste un « par-dessus » : il ne remplace
        // pas la curation du phénomène, il la resserre pour un pilote.
        // `|| null` parce qu'un 0 en base veut dire « rien de choisi ».
        const userOverride = Number(w.threshold_hpa) || null;
        const wantDir = w.direction || 'both'; // sens surveillé (step20), défaut both
        // ── Le référentiel, réglé par le lot 7 ────────────────────────
        // Ce commentaire disait « RESTE À FAIRE ». C'est fait, et
        // autrement que prévu : plutôt que d'extraire la physique vers
        // le client, c'est le SERVEUR qui est devenu la source unique
        // (route B). `GET /phenomenon-delta/:id` rend le Δ MESURÉ avec
        // la physique de la fiche.
        //
        // ⚠️ CORRECTION (audit phénomènes du 08/08/2026, constat n°3) —
        // la phrase précédente disait « et la fiche le consomme ». FAUX :
        // aucun appel à `/phenomenon-delta` dans `PWA/web/src` (vérifié
        // par grep). La fiche ne consomme PAS cette route, elle recalcule
        // en LOCAL avec les mêmes fonctions partagées (`lib/pressure.ts`,
        // dont ce fichier `lib/pressure.cjs` est généré) sur le même
        // référentiel. Les deux chemins rendent aujourd'hui le même
        // chiffre (écart max 0,005 hPa, audit du 08/08) parce qu'ils
        // partagent la physique — ce sont deux calculs qui coïncident,
        // pas un calcul partagé. Si l'un dérive un jour de l'autre (ex. :
        // cette route calcule déjà `pairSpanMin`/`beyondTolerance`, que la
        // fiche ignore et recalcule autrement), rien ne le signalera tant
        // que la fiche n'appelle pas réellement cette route.
        //
        // ⚠️ Ce qui suit reste le Δ PRÉVU, et c'est voulu : l'alerte
        // vise le pic à 36 h, parce que le foehn s'anticipe la veille.
        // Mesuré et prévu ne sont pas deux versions du même nombre et
        // ne doivent jamais être fondus dans un seul champ.
        const peak = foehnServerPeak(dd, ph, wantDir, userOverride);
        const level = peak ? peak.level : 0;
        const active = level >= 2;
        const lang = langByUser.get(w.user_id);
        const lbl = pushLabels(lang).flightwatch.foehn;
        const prefs = prefsByUser.get(w.user_id) || fwPrefs(null);
        await evaluateFwSignal({
          userId: w.user_id, scope, signal: 'foehn', level: level || 2, active,
          // ⚠️ CHANGEMENT 07/08/2026 (lot 3 « Surveiller ce site »).
          // C'était `notify: true` en dur. Le foehn était le SEUL signal
          // à réveiller un compte qui n'avait pas démarré sa veille — un
          // écart assumé tant qu'on cochait un axe à la fois, intenable
          // dès qu'un bouton en arme cinq d'un coup. Sous interrupteur
          // (FOEHN_REQUIRE_ARMED, cf. sa déclaration) : tant qu'il est à
          // 0, comportement d'avant, à l'octet près.
          notify: FOEHN_REQUIRE_ARMED ? activeByUser.has(w.user_id) : true,
          repeatMs: FOEHN_ALERT_REPEAT_MS,
          buildPush: () => {
            const town = peak.direction === 'toA' ? ax.a_name : ax.b_name;
            const signed = (peak.diff >= 0 ? '+' : '') + peak.diff.toFixed(1);
            const whenStr = new Date(peak.time).toLocaleString(lang === 'fr' ? 'fr-FR' : 'en-GB',
              { weekday: 'short', hour: '2-digit', minute: '2-digit' });
            return {
              title: lbl.title(ax.label),
              body: lbl.body(town, signed, peak.level, whenStr),
              icon: '/apple-touch-icon.png', badge: '/apple-touch-icon.png',
              tag: `fw-foehn-${w.axis_id}`, requireInteraction: peak.level === 3,
              data: {
                url: '/', kind: 'flightwatch', signal: 'foehn', level: peak.level,
                scope, voice: peak.level === 3 ? !!prefs.voice_enabled : false,
                value: peak.diff, unit: 'hPa',
              },
            };
          },
        });
      }
    }
  } catch(e) { console.error('pollAndNotify error:', e.message); }
}

app.listen(PORT, async () => {
  console.log(`🚀 Balise Watch Push Server — port ${PORT}`);
  // Première ligne des logs Render après un déploiement : le commit qui
  // vient de démarrer. Évite d'avoir à croire le dashboard sur parole.
  console.log(`   build ${GIT_COMMIT ? GIT_COMMIT.slice(0, 7) : 'local (hors Render)'}${GIT_BRANCH ? ` @ ${GIT_BRANCH}` : ''}`);
  // Débogage 12/07/2026 (suite 5) — hydratation AVANT le premier
  // pollAndNotify, pour que le tout premier cycle après un redémarrage
  // bénéficie déjà de l'historique persisté (station MF proche
  // utilisable immédiatement si elle a assez de recul en base) plutôt
  // que d'attendre le cycle suivant. `await` ici retarde le tout premier
  // poll de quelques centaines de ms (une requête Supabase) — négligeable
  // à l'échelle d'une cadence de 5 min, et fait UNE SEULE FOIS au boot.
  await hydrateBeaconHistoryFromSupabase();
  await hydrateAemetHistoryFromSupabase(); // AEMET, 22/07/2026 — même raison, cf. définition
  pollAndNotify();
  setInterval(pollAndNotify, POLL_MS);
  refreshMeteoFranceData(); // no-op silencieux si METEOFRANCE_API_KEY absente
  setInterval(refreshMeteoFranceData, MF_OBS_POLL_MS);
  // Infoclimat — LECTURE d'objets R2 écrits par le VPS, jamais un appel
  // chez Infoclimat (cf. le bloc de rafraîchissement). Dégradation
  // silencieuse si le poller n'a jamais tourné : objets absents, caches
  // vides, aucun crash.
  refreshInfoclimatData();
  setInterval(refreshInfoclimatData, INFOCLIMAT_OBS_POLL_MS);
  // L'historique a sa PROPRE cadence, 6× plus lente : l'objet est 14×
  // plus gros et le poller ne le réécrit que toutes les 30 min.
  refreshInfoclimatHistory();
  setInterval(refreshInfoclimatHistory, INFOCLIMAT_HISTORY_POLL_MS);
  refreshAemetData(); // no-op silencieux si AEMET_API_KEY absente
  setInterval(refreshAemetData, AEMET_OBS_POLL_MS);
  // Balises de pression (foehn v2, lot 0) — aucune clé requise, donc
  // aucun garde d'environnement : les deux sources sont publiques.
  // Le PREMIER poll METAR demande METAR_BOOT_HOURS d'un coup, les
  // suivants METAR_POLL_HOURS : c'est ce qui remplace la table de
  // persistance que MF et AEMET ont dû se payer. Un redémarrage Render
  // ne perd rien, il redemande — mais SEULEMENT depuis le 04/08/2026 et
  // le découpage en lots : la même ligne, avant, ne ramenait que ~5 h
  // sur 30 demandées, sans le dire (cf. METAR_ROW_BUDGET).
  refreshMetarDeep();
  setInterval(() => refreshMetarObs(), METAR_POLL_MS);
  // Ceinture : si un lot du démarrage a échoué, ou si l'API rabaisse
  // son plafond, le buffer se recreuse tout seul sous 6 h.
  setInterval(refreshMetarDeep, METAR_DEEP_MS);
  // MeteoSuisse : les métadonnées d'abord (altitude du baromètre —
  // indispensable à la réduction, cf. refreshSmnMeta), les relevés
  // ensuite. refreshSmnObs les recharge de lui-même si elles manquent,
  // l'ordre ici n'est qu'une optimisation du démarrage.
  //
  // L'hydratation Supabase passe AVANT le premier refreshSmnObs, et pas
  // seulement pour la forme : ce dernier se sert de la borne haute du
  // buffer pour décider quoi persister (cf. smnPersistHistory).
  hydrateSmnHistoryFromSupabase()
    .then(() => refreshSmnMeta())
    .then(() => refreshSmnObs());
  setInterval(refreshSmnObs, SMN_POLL_MS);
  setInterval(refreshSmnMeta, SMN_META_POLL_MS);
  // winds.mobi (07/08/2026) — aucune clé requise, API publique.
  //
  // Démarrage DÉCALÉ de 90 s, et ce n'est pas une précaution de style :
  // windsmobiKnownGrid() a besoin des six caches sources pour
  // dédoublonner, dont pioupiouCoords que seul le premier pollAndNotify
  // remplit. Lancé au boot, le premier rafraîchissement trouverait une
  // grille vide, se reporterait (cf. le garde dans
  // refreshWindsmobiProviders) et on attendrait 5 min pour rien. 90 s
  // laissent passer le premier poll complet.
  //
  // Les deux cadences sont calées sur la fraîcheur mesurée de chaque
  // réseau (cf. WINDSMOBI_PROVIDERS_FAST/SLOW) : ~1,3 appel/min en
  // moyenne, ce que le point 3 des CGU demande.
  setTimeout(() => {
    // Les balises de déco d'abord : ce sont elles qu'on veut à l'écran
    // le plus tôt possible après un redémarrage Render.
    refreshWindsmobiFast();
    setInterval(refreshWindsmobiFast, WINDSMOBI_POLL_FAST_MS);
    // Le groupe lent démarre 20 s APRÈS, et ce décalage n'est pas
    // cosmétique : il évite que les deux groupes soient en phase, donc
    // qu'ils se chevauchent toutes les 15 min. Le chevauchement n'est
    // plus DESTRUCTEUR depuis que l'écriture du cache est en place et
    // réseau par réseau (cf. refreshWindsmobiProviders) — mais deux
    // rafales de 16 appels simultanées chez un hébergeur qui promet la
    // blacklist à qui le surcharge, autant les étaler.
    setTimeout(() => {
      refreshWindsmobiSlow();
      setInterval(refreshWindsmobiSlow, WINDSMOBI_POLL_SLOW_MS);
    }, 20 * 1000);
  }, 90 * 1000);
  // Étape 28 — détecteur de front de rafales. No-op silencieux si
  // GUST_FRONT_ENABLED n'est pas posé. Décalé d'une minute après le
  // démarrage des boucles d'observation : détecter avant que le premier
  // paquet MF soit arrivé ne produirait qu'un cycle vide.
  setTimeout(async () => {
    // Reprendre l'épisode en cours AVANT le premier cycle : sinon un
    // redémarrage au milieu d'un vrai front en créerait un doublon.
    await gfAdoptActiveEvent();
    gustFrontCycle();
    setInterval(gustFrontCycle, GUST_FRONT_CYCLE_MS);
  }, 60 * 1000);
});
