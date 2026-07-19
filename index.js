const express  = require('express');
const webpush  = require('web-push');
const fetch    = require('node-fetch');
const rateLimit = require('express-rate-limit');
const WebSocket = require('ws'); // Étape 10 Lot 5 : flux foudre Blitzortung (WebSocket temps réel)
const { PNG } = require('pngjs'); // Étape 10 Lot C : décodage des tuiles radar RainViewer (détection précip)

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
    dirOut: '🧭 Hors zone :', // Débogage 16/07/2026 (demande Yann) — option orientation par balise
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
  if (!tiles.size || lat == null || lon == null) return { near: false, distanceKm: null };
  const z = FW_PRECIP_TILE_Z, size = FW_PRECIP_TILE_SIZE;
  const world = Math.pow(2, z) * size; // largeur du monde en pixels à ce zoom
  const gx = (lon + 180) / 360 * world;
  const r = lat * Math.PI / 180;
  const gy = (1 - Math.log(Math.tan(r) + 1 / Math.cos(r)) / Math.PI) / 2 * world;
  const mPerPx = 156543.03 * Math.cos(r) / Math.pow(2, z) * (256 / size); // résolution sol (m/px) au point
  const rp = Math.max(1, Math.ceil((radiusKm * 1000) / mPerPx));
  const rp2 = rp * rp;
  let bestPx2 = Infinity;
  for (let dy = -rp; dy <= rp; dy++) {
    for (let dx = -rp; dx <= rp; dx++) {
      const d2 = dx * dx + dy * dy;
      if (d2 > rp2 || d2 >= bestPx2) continue; // disque, pas carré ; élague si déjà moins bon que le meilleur trouvé
      const px = Math.floor(gx + dx), py = Math.floor(gy + dy);
      const tx = Math.floor(px / size), ty = Math.floor(py / size);
      const tile = tiles.get(`${tx}/${ty}`);
      if (!tile) continue;
      const lx = px - tx * size, ly = py - ty * size;
      if (lx < 0 || ly < 0 || lx >= tile.width || ly >= tile.height) continue;
      if (tile.data[(ly * tile.width + lx) * 4 + 3] > FW_PRECIP_ALPHA_MIN) bestPx2 = d2;
    }
  }
  if (bestPx2 === Infinity) return { near: false, distanceKm: null };
  return { near: true, distanceKm: Math.round((Math.sqrt(bestPx2) * mPerPx) / 100) / 10 };
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
    const next = new Map();
    for (const r of results) if (r) next.set(r[0], r[1]);
    if (next.size) { cutPrecipTiles = next; cutPrecipFrameTime = frame.time; }
  } catch { /* dégradation silencieuse : cache inchangé, route renvoie near:false */ }
  finally { cutPrecipRefreshing = false; }
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
// StatIC) ────────────────────────────────────────────────────────────
// Contrairement aux stations MF (réseau officiel RADOME), ce sont des
// stations AMATEUR (Netatmo, Davis, WeeWX...) hébergées bénévolement par
// des particuliers et republiées par l'association Infoclimat sous
// licence CC BY / CC BY-NC (jamais Etalab plein pour les stations de
// contributeurs — cf. www.infoclimat.fr/opendata, sondé en direct le
// 17/07/2026 avec Yann). Deux caches RAM séparés, même philosophie que
// mfStationsList/mfObsCache ci-dessus :
//  - infoclimatStationsList / infoclimatStationsById : métadonnées
//    statiques (id/nom/coords/altitude/licence), ~1200 stations en
//    France, source = fichier GeoJSON PUBLIC data.gouv.fr (aucune clé
//    requise pour celui-ci, contrairement au reste), rafraîchi une fois
//    par jour.
//  - infoclimatObsCache : dernier relevé par station (vent/direction/
//    pression/température), rafraîchi par LOTS de INFOCLIMAT_BATCH_SIZE
//    ids (l'URL deviendrait déraisonnable pour ~1200 stations en un seul
//    appel) toutes les INFOCLIMAT_OBS_POLL_MS.
// Si INFOCLIMAT_API_KEY n'est pas configurée : les deux caches restent
// vides, /infoclimat-stations renvoie une liste vide, aucun crash (même
// dégradation silencieuse que le reste des modules optionnels).
const INFOCLIMAT_API_KEY = process.env.INFOCLIMAT_API_KEY;
// Fichier GeoJSON "Liste des stations en open-data du réseau
// météorologique Infoclimat (Réseau StatIC)" — mis à jour en continu par
// Infoclimat, lecture publique sans authentification (vérifié en direct
// le 17/07/2026 : ~1200 features, dont 1199 source infoclimat.fr).
const INFOCLIMAT_STATIONS_GEOJSON_URL = 'https://www.data.gouv.fr/api/1/datasets/r/8a9e6a12-03f8-4056-861f-70b84136313e';
const INFOCLIMAT_OPENDATA_URL = 'https://www.infoclimat.fr/opendata/';
const INFOCLIMAT_STATIONS_LIST_REFRESH_MS = 24 * 60 * 60 * 1000;
// Cadence native constatée des relevés StatIC (pas de 15 min sur
// l'échantillon sondé le 17/07) — inutile de poller plus vite.
const INFOCLIMAT_OBS_POLL_MS = 15 * 60 * 1000;
// Taille de lot pour `stations[]=A&stations[]=B&...` — fonctionne en
// bulk (vérifié en direct le 17/07 avec 2 ids), mais on borne la
// longueur d'URL/le poids de réponse plutôt que de tenter les ~1200
// d'un coup. Piste d'optimisation notée mais pas implémentée : ne
// redemander qu'une fenêtre courte (dernière heure) au lieu de la
// journée entière à chaque cycle réduirait le volume transféré — laissé
// simple pour ce premier lot, à revisiter si la bande passante Render
// devient un problème réel.
const INFOCLIMAT_BATCH_SIZE = 100;

let infoclimatStationsList = []; // [{id, nom, lat, lon, alt, licenseCode, licenseLabel, licenseUrl}]
let infoclimatStationsById = new Map();
let infoclimatStationsListFetchedAt = 0;
let infoclimatObsCache = new Map(); // id -> {t, moy, raf, dir, pressure, temp}
let infoclimatObsCacheFetchedAt = 0;
// Débogage 17/07/2026 — dernière erreur rencontrée par le pipeline
// Infoclimat (liste stations OU obs), exposée via /infoclimat-stations
// pour diagnostiquer depuis le client sans accès aux logs Render.
let infoclimatLastError = null;

function chunkArray(arr, size) {
  const out = [];
  for (let i = 0; i < arr.length; i += size) out.push(arr.slice(i, i + size));
  return out;
}

async function refreshInfoclimatStationsList() {
  try {
    const r = await fetch(INFOCLIMAT_STATIONS_GEOJSON_URL);
    if (!r.ok) return; // échec ponctuel : on garde l'ancienne liste plutôt que de la vider
    const geo = await r.json();
    const feats = Array.isArray(geo?.features) ? geo.features : [];
    const parsed = [];
    for (const f of feats) {
      const p = f?.properties || {};
      const coords = f?.geometry?.coordinates;
      const lon = coords?.[0], lat = coords?.[1];
      if (!p.id || !Number.isFinite(lat) || !Number.isFinite(lon)) continue;
      // Ne garder que le réseau Infoclimat (StatIC) — exclut la poignée
      // d'entrées source 'METEO-FRANCE' présentes dans ce même fichier,
      // déjà couvertes par /meteofrance-stations : jamais doubler un
      // même point physique sur la carte.
      if (p.license?.source !== 'infoclimat.fr') continue;
      parsed.push({
        id: p.id, nom: p.name || p.id, lat, lon, alt: p.elevation ?? null,
        licenseCode: p.license?.code ?? null,
        licenseLabel: p.license?.license ?? null,
        licenseUrl: p.license?.url ?? null,
      });
    }
    if (parsed.length) {
      infoclimatStationsList = parsed;
      infoclimatStationsById = new Map(parsed.map(s => [s.id, s]));
      infoclimatStationsListFetchedAt = Date.now();
    }
  } catch (e) {
    console.error('refreshInfoclimatStationsList error:', e.message);
    infoclimatLastError = `stationsList: ${e.message}`;
  }
}

// Un seul lot (déjà vérifié en direct le 17/07 : `stations[]` répété
// fonctionne, `hourly` ne contient que les stations avec au moins un
// point sur la période demandée — pas d'erreur pour les autres).
// Débogage 17/07/2026 — le cache d'observations Infoclimat restait vide
// en prod (fetchedAt:0) sans jamais lever d'erreur visible. Cause :
// l'API opendata Infoclimat répond en texte brut (200 OK, PAS du JSON)
// sur certains rejets ("Wrong ip address", "Could not authenticate
// request" — vérifié en direct depuis un autre réseau que celui de
// Yann). L'ancien code faisait `await r.json()` directement, qui lève
// une SyntaxError sur ce texte brut ; l'erreur était bien catchée plus
// haut (refreshInfoclimatObs) mais SANS le contenu de la réponse, donc
// invisible dans les logs. Ici : on lit toujours le texte d'abord, on
// logge le corps brut (tronqué) sur tout échec de parsing/statut, pour
// pouvoir diagnostiquer depuis les logs Render sans avoir à reproduire
// le problème en local.
async function fetchInfoclimatBatch(ids, startDate, endDate) {
  const params = new URLSearchParams({
    method: 'get', format: 'json', start: startDate, end: endDate, token: INFOCLIMAT_API_KEY,
  });
  for (const id of ids) params.append('stations[]', id);
  const r = await fetch(`${INFOCLIMAT_OPENDATA_URL}?${params.toString()}`);
  const text = await r.text();
  if (!r.ok) {
    infoclimatLastError = `HTTP ${r.status} — ${text.slice(0, 300)}`;
    console.error(`fetchInfoclimatBatch: ${infoclimatLastError}`);
    return null;
  }
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    infoclimatLastError = `réponse non-JSON — ${text.slice(0, 300)}`;
    console.error(`fetchInfoclimatBatch: ${infoclimatLastError}`);
    return null;
  }
  if (data?.status !== 'OK') {
    infoclimatLastError = `status="${data?.status}" — ${JSON.stringify(data?.errors ?? data).slice(0, 300)}`;
    console.error(`fetchInfoclimatBatch: ${infoclimatLastError}`);
    return null;
  }
  return data.hourly || {};
}

function parseInfoclimatPoint(raw) {
  const num = v => (v != null && v !== '' ? parseFloat(v) : null);
  return {
    t: Date.parse(`${raw.dh_utc.replace(' ', 'T')}Z`),
    moy: num(raw.vent_moyen),
    raf: num(raw.vent_rafales),
    dir: num(raw.vent_direction),
    pressure: num(raw.pression),
    temp: num(raw.temperature),
  };
}

async function refreshInfoclimatObs() {
  if (!INFOCLIMAT_API_KEY || !infoclimatStationsList.length) return;
  try {
    const today = new Date().toISOString().slice(0, 10);
    const batches = chunkArray(infoclimatStationsList.map(s => s.id), INFOCLIMAT_BATCH_SIZE);
    const next = new Map();
    for (const ids of batches) {
      const hourly = await fetchInfoclimatBatch(ids, today, today);
      if (!hourly) continue; // ce lot échoue : on garde les autres plutôt que tout annuler
      for (const [id, points] of Object.entries(hourly)) {
        if (!Array.isArray(points) || !points.length) continue;
        // dh_utc croissant dans la réponse (vérifié en direct le 17/07) →
        // le dernier élément est le relevé le plus récent.
        const parsed = parseInfoclimatPoint(points[points.length - 1]);
        if (Number.isFinite(parsed.t)) next.set(id, parsed);
      }
    }
    if (next.size) { infoclimatObsCache = next; infoclimatObsCacheFetchedAt = Date.now(); }
  } catch (e) {
    console.error('refreshInfoclimatObs error:', e.message);
    infoclimatLastError = `refreshObs: ${e.message}`;
  }
}

async function refreshInfoclimatData() {
  if (!INFOCLIMAT_API_KEY) return;
  if (!infoclimatStationsList.length || Date.now() - infoclimatStationsListFetchedAt > INFOCLIMAT_STATIONS_LIST_REFRESH_MS) {
    await refreshInfoclimatStationsList();
  }
  await refreshInfoclimatObs();
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
  const { near, distanceKm } = precipNearestInTiles(cutPrecipTiles, lat, lon, radiusKm);
  res.json({
    near, distanceKm, radiusKm,
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
app.get('/meteofrance-stations', (req, res) => {
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
  res.json({ stations: out, fetchedAt: mfObsCacheFetchedAt });
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
      `station_id=eq.${encodeURIComponent(req.params.id)}&t=gte.${cutoff}&select=t,moy,raf,min,dir,pressure&order=t.asc`
    );
    const ramCutoff = ramPts[0]?.t ?? Infinity; // évite les doublons : ne garde du passé persistant que ce qui précède le buffer RAM
    const merged = [...(Array.isArray(oldPts) ? oldPts.filter(p => p.t < ramCutoff) : []), ...ramPts];
    res.json({ points: merged });
  } catch (e) {
    console.error('meteofrance-history (hours) error:', e.message);
    res.json({ points: ramPts }); // dégradation gracieuse : au pire, la profondeur RAM habituelle
  }
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
  // cache vide (INFOCLIMAT_API_KEY absente, IP Render rejetée par
  // l'API Infoclimat, etc.) sans avoir besoin des logs Render.
  res.json({
    stations: out,
    fetchedAt: infoclimatObsCacheFetchedAt,
    stationsListCount: infoclimatStationsList.length,
    lastError: infoclimatLastError,
  });
});

// ── Étape 12 (suite) — Historique d'une station Infoclimat ──────────
// Contrairement aux stations MF, Infoclimat expose SA PROPRE archive
// interrogeable sur n'importe quelle période passée : pas besoin de
// maintenir notre propre buffer RAM ni table Supabase ici, on relaie
// simplement la requête (avec la clé serveur, jamais exposée côté
// client) et on reforme la réponse en HistoryPoint[] (même forme que
// Pioupiou/MF : {t, min, avg, max, dir, pressure}). `min` toujours null
// (pas de notion de minimum glissant côté Infoclimat, contrairement à
// Pioupiou/MF où on le calcule nous-mêmes) ; `max` = rafale native si le
// modèle de station de l'utilisateur en mesure une (beaucoup de stations
// amateur n'ont pas d'anémomètre à rafale, cf. vent_rafales souvent null
// constaté en sondage direct le 17/07 — jamais 0/faux dans ce cas).
// Débogage 17/07/2026 — diagnostic temporaire : l'API Infoclimat exige
// une IPv4 fixe déclarée par clé (`Wrong ip address` sinon), or Render
// n'a par défaut qu'une PLAGE d'IP de sortie partagée (74.220.51.0/24 +
// 74.220.59.0/24, 512 adresses possibles), pas une IP unique garantie.
// Cette route relaie ipify pour voir l'IP RÉELLE utilisée par CE
// processus à cet instant — si elle reste stable sur plusieurs appels
// (l'attribution NAT peut être sticky tant que l'instance ne redémarre
// pas), Yann peut la déclarer directement chez Infoclimat sans payer de
// proxy IP fixe. À retirer une fois la question tranchée.
app.get('/whatismyip', async (req, res) => {
  try {
    const r = await fetch('https://api.ipify.org?format=json');
    const d = await r.json();
    res.json({ ip: d.ip, checkedAt: new Date().toISOString() });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
});

app.get('/infoclimat-history/:id', async (req, res) => {
  if (!INFOCLIMAT_API_KEY) return res.json({ points: [] });
  try {
    const hoursParam = Number(req.query.hours);
    const hours = Number.isFinite(hoursParam) ? Math.min(Math.max(hoursParam, 1), 24 * 14) : 24;
    const end = new Date();
    const start = new Date(end.getTime() - hours * 3600 * 1000);
    const fmt = d => d.toISOString().slice(0, 10);
    const hourly = await fetchInfoclimatBatch([req.params.id], fmt(start), fmt(end));
    const raw = hourly?.[req.params.id];
    if (!Array.isArray(raw)) return res.json({ points: [] });
    const cutoff = start.getTime();
    const points = raw.map(p => {
      const parsed = parseInfoclimatPoint(p);
      return { t: parsed.t, min: null, avg: parsed.moy, max: parsed.raf, dir: parsed.dir, pressure: parsed.pressure };
    }).filter(p => Number.isFinite(p.t) && p.t >= cutoff);
    res.json({ points });
  } catch (e) {
    console.error('infoclimat-history error:', e.message);
    res.json({ points: [] });
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
        // Débogage 16/07/2026 (demande Yann) — option orientation, même
        // politique défensive que `source` ci-dessus : colonnes pas
        // encore créées tant que Yann n'a pas exécuté
        // supabase_watch_orientation.sql, PostgREST les ignore
        // silencieusement côté insert simple, aucune casse avant.
        dir_enabled: w.dirEnabled ?? false,
        dir_sectors: Array.isArray(w.dirSectors) ? w.dirSectors : [],
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
const foehnDiffCache = new Map(); // axisId -> { ts, diff:{ times, diff } }

// Différentiel Δ = pmsl(A) − pmsl(B) prévu (GFS), deux points en une requête.
// Cache court par axe (mutualisé entre comptes surveillant le même axe).
async function fetchFoehnDiffServer(axis) {
  const cached = foehnDiffCache.get(axis.id);
  if (cached && (Date.now() - cached.ts) < FOEHN_CACHE_TTL_MS) return cached.diff;
  const url = `${OPEN_METEO_URL}?latitude=${axis.a_lat},${axis.b_lat}` +
    `&longitude=${axis.a_lon},${axis.b_lon}` +
    `&hourly=pressure_msl&models=gfs_seamless&forecast_days=2&timezone=UTC`;
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
// Renvoie { time, diff, level, direction } ou null. threshold = seuil du compte.
// wantDir : sens surveillé par le pilote — 'both' (défaut), 'toA' (Δ négatif,
// foehn vers A) ou 'toB' (Δ positif, foehn vers B). On ignore le versant
// qui n'intéresse pas le compte, pour ne pas l'alerter à tort de l'autre côté.
function foehnServerPeak(d, threshold, wantDir = 'both') {
  const now = Date.now();
  const hi = now + FOEHN_FORECAST_HORIZON_MS;
  let best = null;
  for (let i = 0; i < d.times.length; i++) {
    const t = d.times[i], v = d.diff[i];
    if (v == null || t < now || t > hi) continue;
    if (wantDir === 'toA' && v >= 0) continue; // toA = Δ négatif seulement
    if (wantDir === 'toB' && v <= 0) continue; // toB = Δ positif seulement
    if (best === null || Math.abs(v) > Math.abs(best.diff)) best = { time: t, diff: v };
  }
  if (!best) return null;
  const mag = Math.abs(best.diff);
  best.level = mag >= FOEHN_HPA_PLAIN ? 3 : mag >= threshold ? 2 : 0;
  best.direction = mag < threshold ? 'none' : (best.diff < 0 ? 'toA' : 'toB');
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
    // ignoré (le foehn s'anticipe la veille, sans balise ni départ de veille).
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
    async function evaluateFwSignal({ userId, scope, signal, level, active, buildPush, repeatMs, notify }) {
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
        const dueForSend = justActivated || (now - lastSent) >= repeatWindow;
        if (!(acked && !justActivated) && dueForSend) {
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
    // ── Lot foehn : alarme différentiel de pression par AXE ───────────
    // Veille par axe (user_foehn_watch, déjà lu en tête pour le garde-fou
    // d'arrêt), mutualisée : un seul fetch OM par axe distinct surveillé.
    // Scope 'axis:<id>', réutilise le cycle user_flightwatch_alerts
    // (signal 'foehn'). L'alarme vise le PIC À VENIR (anticipation), pas
    // l'instant présent. notify:true car le foehn s'anticipe la veille —
    // l'opt-in EST la ligne user_foehn_watch, indépendant du "démarrage"
    // de la veille balises. Push formulé DANGER (non-vol). Défensif :
    // table/axe absent -> réarmement silencieux, jamais de crash.
    if (anyFoehnWatch) {
      const foehnAxesRows = await sbGet('foehn_axes', 'select=*');
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
        const threshold = Number(w.threshold_hpa) || FOEHN_HPA_VALLEY;
        const wantDir = w.direction || 'both'; // sens surveillé (step20), défaut both
        const peak = foehnServerPeak(dd, threshold, wantDir);
        const level = peak ? peak.level : 0;
        const active = level >= 2;
        const lang = langByUser.get(w.user_id);
        const lbl = pushLabels(lang).flightwatch.foehn;
        const prefs = prefsByUser.get(w.user_id) || fwPrefs(null);
        await evaluateFwSignal({
          userId: w.user_id, scope, signal: 'foehn', level: level || 2, active,
          notify: true, repeatMs: FOEHN_ALERT_REPEAT_MS,
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
  // Débogage 12/07/2026 (suite 5) — hydratation AVANT le premier
  // pollAndNotify, pour que le tout premier cycle après un redémarrage
  // bénéficie déjà de l'historique persisté (station MF proche
  // utilisable immédiatement si elle a assez de recul en base) plutôt
  // que d'attendre le cycle suivant. `await` ici retarde le tout premier
  // poll de quelques centaines de ms (une requête Supabase) — négligeable
  // à l'échelle d'une cadence de 5 min, et fait UNE SEULE FOIS au boot.
  await hydrateBeaconHistoryFromSupabase();
  pollAndNotify();
  setInterval(pollAndNotify, POLL_MS);
  refreshMeteoFranceData(); // no-op silencieux si METEOFRANCE_API_KEY absente
  setInterval(refreshMeteoFranceData, MF_OBS_POLL_MS);
  refreshInfoclimatData(); // no-op silencieux si INFOCLIMAT_API_KEY absente
  setInterval(refreshInfoclimatData, INFOCLIMAT_OBS_POLL_MS);
});
