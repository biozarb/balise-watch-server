const express  = require('express');
const webpush  = require('web-push');
const fetch    = require('node-fetch');
const rateLimit = require('express-rate-limit');

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
    },
  },
  en: {
    avg: 'Avg.', gust: 'Gust',
    flightwatch: {
      windSurge: {
        body: (nowKmh, baseKmh, windowMin) =>
          `Wind rising sharply: ${nowKmh} km/h (${baseKmh} km/h ${windowMin} min ago)`,
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
const FW_HISTORY_MAX_AGE_MS = 60 * 60 * 1000; // 1h, large marge sur toute fenêtre réglée (défaut 15 min)
const FW_WIND_MIN_BASELINE_KMH = 3; // évite un facteur "x1.8" absurde quand le vent de référence est quasi nul
const FW_ALERT_REPEAT_MS = 15 * 60 * 1000; // anti-répétition flightwatch : pas de colonne repeat_interval dédiée (contrairement à user_watched), intervalle fixe raisonnable niveau 2/3

const beaconHistory = new Map(); // beacon_id (string) -> [{t, moy, dir}] trié par t croissant

function fwRecordHistory(beaconId, sample) {
  const arr = beaconHistory.get(beaconId) || [];
  arr.push(sample);
  const cutoff = Date.now() - FW_HISTORY_MAX_AGE_MS;
  while (arr.length && arr[0].t < cutoff) arr.shift();
  beaconHistory.set(beaconId, arr);
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
        updated_at: new Date().toISOString(),
      }));
      await sbUpsert('user_watched', rows, 'user_id,beacon_id');
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
      lat: b.location?.latitude ?? null,
      lon: b.location?.longitude ?? null,
      nom: b.meta?.name || `Balise ${b.id}`,
    }; });
    // Historique flightwatch (Lot 1) : un échantillon par balise réelle à
    // chaque poll, AVANT d'ajouter la balise de test (fictive, pas de
    // dérive physique à surveiller). Sert aux dérivées vent/direction
    // ci-dessous (fwBaselineAt).
    const fwPollT = Date.now();
    Object.entries(releves).forEach(([id, rel]) => {
      fwRecordHistory(id, { t: fwPollT, moy: rel.moy, dir: rel.dir });
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
      'select=user_id,active,sig_wind_surge,sig_breeze_reversal,sig_pressure_drop,sig_convection,sig_vigilance,sig_lightning,sig_freezing_level,lightning_radius_km,wind_surge_factor,wind_surge_window_min,pressure_drop_hpa_h,voice_enabled');
    const activeByUser = new Set(
      (Array.isArray(surveillanceRows) ? surveillanceRows : []).filter(s => s.active).map(s => s.user_id)
    );
    // Préférences flightwatch par compte (Lot 1) : mêmes lignes que
    // ci-dessus, défauts sains appliqués via fwPrefs (cf. plus haut).
    const prefsByUser = new Map(
      (Array.isArray(surveillanceRows) ? surveillanceRows : []).map(s => [s.user_id, fwPrefs(s)])
    );

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
    async function evaluateFwSignal({ userId, scope, signal, level, active, buildPush }) {
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
      if (!justActivated && (now - lastSent) < FW_ALERT_REPEAT_MS) return;

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
          surging = rel.moy >= effBaseline * fwPrefsForUser.wind_surge_factor;
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
  } catch(e) { console.error('pollAndNotify error:', e.message); }
}

app.listen(PORT, () => {
  console.log(`🚀 Balise Watch Push Server — port ${PORT}`);
  pollAndNotify();
  setInterval(pollAndNotify, POLL_MS);
});
