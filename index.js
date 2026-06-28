// ═══════════════════════════════════════════════════════════════
// BALISE WATCH — Serveur Push Notifications
// ═══════════════════════════════════════════════════════════════

const express  = require('express');
const webpush  = require('web-push');
const fetch    = require('node-fetch');
const { createClient } = require('@supabase/supabase-js');

// ── CONFIG ────────────────────────────────────────────────────────
const PORT        = process.env.PORT || 3000;
const VAPID_PUB   = process.env.VAPID_PUBLIC_KEY;
const VAPID_PRIV  = process.env.VAPID_PRIVATE_KEY;
const VAPID_EMAIL = process.env.VAPID_EMAIL || 'mailto:admin@balise-watch.fr';
const SB_URL      = process.env.SUPABASE_URL;
const SB_KEY      = process.env.SUPABASE_SERVICE_KEY; // service_role key
const POLL_MS     = 5 * 60 * 1000; // 5 minutes

const API_ALL     = 'https://api.pioupiou.fr/v1/live-with-meta/all';

// ── INIT ──────────────────────────────────────────────────────────
webpush.setVapidDetails(VAPID_EMAIL, VAPID_PUB, VAPID_PRIV);
const supabase = createClient(SB_URL, SB_KEY);
const app = express();
app.use(express.json());

// CORS pour autoriser l'app Vercel
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', 'https://balise-watch.vercel.app');
  res.header('Access-Control-Allow-Headers', 'Content-Type');
  res.header('Access-Control-Allow-Methods', 'GET,POST,DELETE,OPTIONS');
  if (req.method === 'OPTIONS') return res.sendStatus(200);
  next();
});

// ── ROUTES ────────────────────────────────────────────────────────

// Santé du serveur
app.get('/', (req, res) => {
  res.json({ status: 'ok', version: '1.0.0', service: 'Balise Watch Push Server' });
});

// Clé publique VAPID (l'app en a besoin pour s'abonner)
app.get('/vapid-public-key', (req, res) => {
  res.json({ key: VAPID_PUB });
});

// Enregistrer ou mettre à jour un abonnement push
app.post('/subscribe', async (req, res) => {
  const { subscription, watched } = req.body;
  if (!subscription?.endpoint) return res.status(400).json({ error: 'Subscription invalide' });

  const { error } = await supabase
    .from('subscriptions')
    .upsert({
      endpoint:   subscription.endpoint,
      p256dh:     subscription.keys.p256dh,
      auth:       subscription.keys.auth,
      watched:    watched || [],
      updated_at: new Date().toISOString(),
    }, { onConflict: 'endpoint' });

  if (error) return res.status(500).json({ error: error.message });
  console.log(`✅ Abonnement enregistré: ${subscription.endpoint.slice(-20)}`);
  res.json({ success: true });
});

// Mettre à jour les balises surveillées d'un abonné
app.post('/update-watched', async (req, res) => {
  const { endpoint, watched } = req.body;
  if (!endpoint) return res.status(400).json({ error: 'Endpoint manquant' });

  const { error } = await supabase
    .from('subscriptions')
    .update({ watched, updated_at: new Date().toISOString() })
    .eq('endpoint', endpoint);

  if (error) return res.status(500).json({ error: error.message });
  res.json({ success: true });
});

// Se désabonner
app.delete('/unsubscribe', async (req, res) => {
  const { endpoint } = req.body;
  if (!endpoint) return res.status(400).json({ error: 'Endpoint manquant' });
  await supabase.from('subscriptions').delete().eq('endpoint', endpoint);
  res.json({ success: true });
});

// ── POLLING & ALERTES ─────────────────────────────────────────────

let lastAlerts = {}; // { endpoint_baliseId: timestamp } — anti-spam

async function pollAndNotify() {
  console.log(`[${new Date().toLocaleTimeString('fr-FR')}] Polling balises...`);

  try {
    // 1. Charger les relevés Pioupiou
    const r = await fetch(API_ALL);
    const d = await r.json();
    const releves = {};
    (d.data || []).forEach(b => {
      releves[String(b.id)] = {
        moy: b.measurements?.wind_speed_avg ?? null,
        raf: b.measurements?.wind_speed_max ?? null,
        nom: b.meta?.name || `Balise ${b.id}`,
      };
    });

    // 2. Charger la balise de test
    const { data: testData } = await supabase
      .from('test_beacon')
      .select('*')
      .eq('id', 'singleton')
      .single();

    if (testData?.enabled) {
      releves['__test__'] = {
        moy: testData.wind_avg,
        raf: testData.wind_max,
        nom: '🧪 ' + (testData.label || 'Balise de test'),
      };
    }

    // 3. Charger tous les abonnements
    const { data: subs } = await supabase
      .from('subscriptions')
      .select('*');

    if (!subs?.length) return;

    // 4. Pour chaque abonné, vérifier ses seuils
    for (const sub of subs) {
      const watched = sub.watched || [];
      for (const w of watched) {
        const rel = releves[String(w.id)];
        if (!rel) continue;

        const overM = rel.moy !== null && w.seuilMoy    && rel.moy >= w.seuilMoy;
        const overR = rel.raf !== null && w.seuilRafale && rel.raf >= w.seuilRafale;

        if (!overM && !overR) continue;

        // Anti-spam : pas plus d'une notif par balise toutes les 10 min par abonné
        const key = `${sub.endpoint.slice(-20)}_${w.id}`;
        const now = Date.now();
        if (lastAlerts[key] && (now - lastAlerts[key]) < 10 * 60 * 1000) continue;
        lastAlerts[key] = now;

        // Construire la notification
        let body = '';
        if (overM) body += `Moy. ${Math.round(rel.moy)} km/h`;
        if (overM && overR) body += ' · ';
        if (overR) body += `Rafale ${Math.round(rel.raf)} km/h`;

        const payload = JSON.stringify({
          title: `⚠️ ${rel.nom}`,
          body,
          icon:  '/apple-touch-icon.png',
          badge: '/apple-touch-icon.png',
          tag:   `alert-${w.id}`,
          data:  { url: '/', baliseId: w.id },
        });

        // Envoyer la notification push
        try {
          await webpush.sendNotification(
            { endpoint: sub.endpoint, keys: { p256dh: sub.p256dh, auth: sub.auth } },
            payload
          );
          console.log(`📲 Push envoyé → ${rel.nom} (${body})`);
        } catch (err) {
          if (err.statusCode === 410 || err.statusCode === 404) {
            // Abonnement expiré — supprimer
            console.log(`🗑 Abonnement expiré supprimé: ${sub.endpoint.slice(-20)}`);
            await supabase.from('subscriptions').delete().eq('endpoint', sub.endpoint);
          } else {
            console.warn(`⚠️ Push error (${err.statusCode}):`, err.body);
          }
        }
      }
    }
  } catch(e) {
    console.error('pollAndNotify error:', e.message);
  }
}

// ── DÉMARRAGE ─────────────────────────────────────────────────────

app.listen(PORT, () => {
  console.log(`🚀 Balise Watch Push Server — port ${PORT}`);
  // Premier poll immédiat puis toutes les 5 min
  pollAndNotify();
  setInterval(pollAndNotify, POLL_MS);
});
