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
async function sbUpsert(table, body, onConflict) { const r = await fetch(`${SB_URL}/rest/v1/${table}?on_conflict=${onConflict}`, { method:'POST', headers:{...SB_HEADERS,'Prefer':'resolution=merge-duplicates,return=minimal'}, body:JSON.stringify(body) }); return r.ok; }
async function sbDelete(table, query) { const r = await fetch(`${SB_URL}/rest/v1/${table}?${query}`, { method:'DELETE', headers:SB_HEADERS }); return r.ok; }

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

app.get('/', (req, res) => res.json({ status:'ok', version:'2.0.0', service:'Balise Watch Push Server' }));
app.get('/vapid-public-key', (req, res) => res.json({ key: VAPID_PUB }));

// ── /sync : lie l'appareil (endpoint push) au compte + remplace la liste
//    de surveillance du compte par celle envoyée (upsert + suppression
//    des balises qui ne sont plus dans la liste) ──
app.post('/sync', async (req, res) => {
  const { access_token, subscription, watched } = req.body;
  const user = await verifyUser(access_token);
  if (!user) return res.status(401).json({ error:'Session invalide ou expirée' });
  if (!subscription?.endpoint) return res.status(400).json({ error:'Subscription invalide' });

  try {
    await sbUpsert('user_devices', {
      user_id: user.id, endpoint: subscription.endpoint,
      p256dh: subscription.keys.p256dh, auth: subscription.keys.auth,
      updated_at: new Date().toISOString(),
    }, 'endpoint');

    const list = watched || [];
    if (list.length) {
      const rows = list.map(w => ({
        user_id: user.id, beacon_id: String(w.id), beacon_nom: w.nom,
        seuil_moy: w.seuilMoy ?? null, seuil_rafale: w.seuilRafale ?? null,
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

    console.log(`✅ Sync ${user.email||user.id.slice(0,8)} — ${list.length} balise(s), device ...${subscription.endpoint.slice(-12)}`);
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

app.post('/test-push', async (req, res) => {
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

    const watchedRows = await sbGet('user_watched', 'select=*');
    if (!watchedRows?.length) { console.log('Aucune balise surveillée'); return; }

    const devices = await sbGet('user_devices', 'select=*');
    const devicesByUser = {};
    (devices||[]).forEach(dv => { (devicesByUser[dv.user_id] ??= []).push(dv); });

    console.log(`${new Set(watchedRows.map(w=>w.user_id)).size} compte(s), ${watchedRows.length} surveillance(s)`);

    for (const w of watchedRows) {
      const rel = releves[String(w.beacon_id)];
      if (!rel) continue;
      const overM = rel.moy!==null && w.seuil_moy    && rel.moy>=w.seuil_moy;
      const overR = rel.raf!==null && w.seuil_rafale && rel.raf>=w.seuil_rafale;
      if (!overM && !overR) continue;

      // Anti-spam : par compte + balise (pas par appareil, sinon
      // incohérent entre les devices d'un même utilisateur)
      const key = `${w.user_id}_${w.beacon_id}`;
      const now = Date.now();
      if (lastAlerts[key] && (now-lastAlerts[key])<10*60*1000) continue;
      lastAlerts[key] = now;

      let body='';
      if (overM) body+=`Moy. ${Math.round(rel.moy)} km/h`;
      if (overM&&overR) body+=' · ';
      if (overR) body+=`Rafale ${Math.round(rel.raf)} km/h`;

      const userDevices = devicesByUser[w.user_id] || [];
      for (const dv of userDevices) {
        try {
          await webpush.sendNotification(
            { endpoint:dv.endpoint, keys:{ p256dh:dv.p256dh, auth:dv.auth } },
            JSON.stringify({ title:`⚠️ ${rel.nom}`, body, icon:'/apple-touch-icon.png', badge:'/apple-touch-icon.png', tag:`alert-${w.beacon_id}`, data:{ url:'/' } })
          );
          console.log(`📲 Push → ${rel.nom} (${body})`);
        } catch(err) {
          if (err.statusCode===410||err.statusCode===404) { await sbDelete('user_devices', `endpoint=eq.${encodeURIComponent(dv.endpoint)}`); }
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
