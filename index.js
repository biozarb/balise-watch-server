const express  = require('express');
const webpush  = require('web-push');
const fetch    = require('node-fetch');

const PORT         = process.env.PORT || 3000;
const VAPID_PUB    = process.env.VAPID_PUBLIC_KEY;
const VAPID_PRIV   = process.env.VAPID_PRIVATE_KEY;
const VAPID_EMAIL  = process.env.VAPID_EMAIL || 'mailto:admin@balise-watch.fr';
const SB_URL       = process.env.SUPABASE_URL;
const SB_KEY       = process.env.SUPABASE_SERVICE_KEY;
const POLL_MS      = 5 * 60 * 1000;
const API_ALL      = 'https://api.pioupiou.fr/v1/live-with-meta/all';

webpush.setVapidDetails(VAPID_EMAIL, VAPID_PUB, VAPID_PRIV);
const app = express();
app.use(express.json());
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Headers', 'Content-Type');
  res.header('Access-Control-Allow-Methods', 'GET,POST,DELETE,OPTIONS');
  if (req.method === 'OPTIONS') return res.sendStatus(200);
  next();
});

const SB_HEADERS = { 'apikey': SB_KEY, 'Authorization': `Bearer ${SB_KEY}`, 'Content-Type': 'application/json' };
async function sbGet(table, query='') { const r = await fetch(`${SB_URL}/rest/v1/${table}?${query}`, { headers: SB_HEADERS }); return r.json(); }
async function sbPost(table, body) { const r = await fetch(`${SB_URL}/rest/v1/${table}`, { method:'POST', headers:{...SB_HEADERS,'Prefer':'resolution=merge-duplicates'}, body:JSON.stringify(body) }); return r.ok; }
async function sbPatch(table, query, body) { const r = await fetch(`${SB_URL}/rest/v1/${table}?${query}`, { method:'PATCH', headers:{...SB_HEADERS,'Prefer':'return=minimal'}, body:JSON.stringify(body) }); return r.ok; }
async function sbDelete(table, query) { const r = await fetch(`${SB_URL}/rest/v1/${table}?${query}`, { method:'DELETE', headers:SB_HEADERS }); return r.ok; }

app.get('/', (req, res) => res.json({ status:'ok', version:'1.1.0', service:'Balise Watch Push Server' }));
app.get('/vapid-public-key', (req, res) => res.json({ key: VAPID_PUB }));

app.post('/subscribe', async (req, res) => {
  const { subscription, watched } = req.body;
  if (!subscription?.endpoint) return res.status(400).json({ error:'Subscription invalide' });
  try {
    await sbPost('subscriptions', { endpoint:subscription.endpoint, p256dh:subscription.keys.p256dh, auth:subscription.keys.auth, watched:watched||[], updated_at:new Date().toISOString() });
    console.log(`✅ Abonné: ...${subscription.endpoint.slice(-20)}`);
    res.json({ success:true });
  } catch(e) { res.status(500).json({ error:e.message }); }
});

app.post('/update-watched', async (req, res) => {
  const { endpoint, watched } = req.body;
  if (!endpoint) return res.status(400).json({ error:'Endpoint manquant' });
  await sbPatch('subscriptions', `endpoint=eq.${encodeURIComponent(endpoint)}`, { watched, updated_at:new Date().toISOString() });
  res.json({ success:true });
});

app.post('/test-push', async (req, res) => {
  try {
    const subs = await sbGet('subscriptions', 'select=*');
    if (!subs?.length) return res.json({ success:true, sent:0, message:'Aucun abonné' });
    let sent = 0, errors = 0;
    for (const sub of subs) {
      try {
        await webpush.sendNotification(
          { endpoint:sub.endpoint, keys:{ p256dh:sub.p256dh, auth:sub.auth } },
          JSON.stringify({ title:'🧪 Test Balise Watch', body:'Notification de test reçue avec succès !', icon:'/apple-touch-icon.png', badge:'/apple-touch-icon.png', tag:'test-push', data:{ url:'/' } })
        );
        sent++;
      } catch(err) {
        if (err.statusCode===410||err.statusCode===404) { await sbDelete('subscriptions', `endpoint=eq.${encodeURIComponent(sub.endpoint)}`); }
        else { console.warn(`⚠️ Test-push error ${err.statusCode}: ${err.message}`); errors++; }
      }
    }
    console.log(`🧪 Test-push: ${sent} envoyés, ${errors} erreurs`);
    res.json({ success:true, sent, errors });
  } catch(e) { res.status(500).json({ error:e.message }); }
});

app.delete('/unsubscribe', async (req, res) => {
  const { endpoint } = req.body;
  if (!endpoint) return res.status(400).json({ error:'Endpoint manquant' });
  await sbDelete('subscriptions', `endpoint=eq.${encodeURIComponent(endpoint)}`);
  res.json({ success:true });
});

let lastAlerts = {};
async function pollAndNotify() {
  console.log(`[${new Date().toLocaleTimeString('fr-FR')}] Polling...`);
  try {
    const r = await fetch(API_ALL);
    const d = await r.json();
    const releves = {};
    (d.data||[]).forEach(b => { releves[String(b.id)] = { moy:b.measurements?.wind_speed_avg??null, raf:b.measurements?.wind_speed_max??null, nom:b.meta?.name||`Balise ${b.id}` }; });
    const testData = await sbGet('test_beacon', 'id=eq.singleton&select=*');
    const test = testData?.[0];
    if (test?.enabled) releves['__test__'] = { moy:test.wind_avg, raf:test.wind_max, nom:'🧪 '+(test.label||'Balise de test') };
    const subs = await sbGet('subscriptions', 'select=*');
    if (!subs?.length) { console.log('Aucun abonné'); return; }
    console.log(`${subs.length} abonné(s)`);
    for (const sub of subs) {
      for (const w of (sub.watched||[])) {
        const rel = releves[String(w.id)];
        if (!rel) continue;
        const overM = rel.moy!==null && w.seuilMoy    && rel.moy>=w.seuilMoy;
        const overR = rel.raf!==null && w.seuilRafale && rel.raf>=w.seuilRafale;
        if (!overM && !overR) continue;
        const key = `${sub.endpoint.slice(-20)}_${w.id}`;
        const now = Date.now();
        if (lastAlerts[key] && (now-lastAlerts[key])<10*60*1000) continue;
        lastAlerts[key] = now;
        let body='';
        if (overM) body+=`Moy. ${Math.round(rel.moy)} km/h`;
        if (overM&&overR) body+=' · ';
        if (overR) body+=`Rafale ${Math.round(rel.raf)} km/h`;
        try {
          await webpush.sendNotification(
            { endpoint:sub.endpoint, keys:{ p256dh:sub.p256dh, auth:sub.auth } },
            JSON.stringify({ title:`⚠️ ${rel.nom}`, body, icon:'/apple-touch-icon.png', badge:'/apple-touch-icon.png', tag:`alert-${w.id}`, data:{ url:'/' } })
          );
          console.log(`📲 Push → ${rel.nom} (${body})`);
        } catch(err) {
          if (err.statusCode===410||err.statusCode===404) { await sbDelete('subscriptions', `endpoint=eq.${encodeURIComponent(sub.endpoint)}`); }
          else console.warn(`⚠️ Push error ${err.statusCode}`);
        }
      }
    }
  } catch(e) { console.error('pollAndNotify error:', e.message); }
}

app.listen(PORT, () => {
  console.log(`🚀 Balise Watch Push Server — port ${PORT}`);
  pollAndNotify();
  setInterval(pollAndNotify, POLL_MS);
});
