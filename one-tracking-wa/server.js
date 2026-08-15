/**
 * ONE Tracking - WhatsApp Sidecar
 * Provides HTTP API for the Flask app to interact with WhatsApp Web via Baileys.
 *
 * Endpoints:
 *   GET  /health                — health check
 *   GET  /status                — connection status
 *   GET  /qr                    — current QR code (PNG)
 *   GET  /qr.json               — current QR as JSON {qr: "data:image/png;base64,..."}
 *   POST /send                  — send message {to, message}
 *   POST /logout                — clear session (forces re-pair)
 *
 * Auth: all endpoints except /health and /qr require header "X-API-Key".
 */
require('dotenv').config();
const express = require('express');
const QRCode = require('qrcode');
const path = require('path');
const fs = require('fs');
const pino = require('pino');
const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
} = require('@whiskeysockets/baileys');

const PORT = process.env.PORT || 3000;
const API_KEY = process.env.API_KEY || 'change-me-in-production';
const AUTH_DIR = process.env.AUTH_DIR || path.join(__dirname, 'auth_info');
const APP_NAME = process.env.APP_NAME || 'ONE Tracking';

// State
let sock = null;
let currentQR = null;
let connectionStatus = 'disconnected'; // disconnected | connecting | qr | connected
let lastError = null;
let phoneNumber = null;

const logger = pino({ level: 'warn' });

// Ensure auth dir exists
if (!fs.existsSync(AUTH_DIR)) fs.mkdirSync(AUTH_DIR, { recursive: true });

// ============ Baileys connection ============
async function startSocket() {
  try {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version } = await fetchLatestBaileysVersion();

    sock = makeWASocket({
      version,
      auth: state,
      printQRInTerminal: false,
      logger,
      browser: [APP_NAME, 'Chrome', '1.0.0'],
      syncFullHistory: false,
      markOnlineOnConnect: false,
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
      const { connection, lastDisconnect, qr } = update;

      if (qr) {
        connectionStatus = 'qr';
        currentQR = await QRCode.toDataURL(qr, { width: 320, margin: 2 });
        console.log('[WA] QR generated, waiting for scan');
      }

      if (connection === 'open') {
        connectionStatus = 'connected';
        currentQR = null;
        phoneNumber = sock.user?.id?.split(':')[0] || null;
        lastError = null;
        console.log(`[WA] Connected as ${phoneNumber}`);
      }

      if (connection === 'close') {
        const code = lastDisconnect?.error?.output?.statusCode;
        const shouldReconnect = code !== DisconnectReason.loggedOut;
        connectionStatus = 'disconnected';
        currentQR = null;
        lastError = lastDisconnect?.error?.message || 'connection closed';
        console.log(`[WA] Disconnected (${code}): ${lastError}. Reconnect=${shouldReconnect}`);
        if (shouldReconnect) {
          setTimeout(startSocket, 3000);
        } else {
          // Logged out - clear session
          fs.rmSync(AUTH_DIR, { recursive: true, force: true });
          fs.mkdirSync(AUTH_DIR, { recursive: true });
          setTimeout(startSocket, 3000);
        }
      }
    });

    connectionStatus = 'connecting';
  } catch (err) {
    console.error('[WA] startSocket error:', err);
    lastError = err.message;
    setTimeout(startSocket, 5000);
  }
}

// ============ Middleware ============
const app = express();
app.use(express.json({ limit: '1mb' }));

function requireApiKey(req, res, next) {
  const key = req.header('X-API-Key');
  if (key !== API_KEY) {
    return res.status(401).json({ error: 'invalid api key' });
  }
  next();
}

// ============ Public endpoints ============
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    time: new Date().toISOString(),
    wa: connectionStatus,
  });
});

// QR — public but rate-limited by obscurity (should be behind admin auth in Flask)
app.get('/qr', async (req, res) => {
  if (connectionStatus === 'connected') {
    return res.status(200).send(`
      <html><body style="font-family:sans-serif;text-align:center;padding:40px;background:#0f172a;color:#f1f5f9">
        <h2>✅ متصل</h2>
        <p>الرقم: <code>${phoneNumber || ''}</code></p>
      </body></html>
    `);
  }
  if (!currentQR) {
    return res.status(200).send(`
      <html><body style="font-family:sans-serif;text-align:center;padding:40px;background:#0f172a;color:#f1f5f9">
        <h2>⏳ ${connectionStatus === 'connecting' ? 'جاري الاتصال...' : 'في انتظار توليد QR'}</h2>
        <script>setTimeout(()=>location.reload(), 3000)</script>
      </body></html>
    `);
  }
  res.status(200).send(`
    <html><body style="font-family:sans-serif;text-align:center;padding:40px;background:#0f172a;color:#f1f5f9">
      <h2>امسح QR بواتس الشركة</h2>
      <p>WhatsApp → الإعدادات → الأجهزة المرتبطة → ربط جهاز</p>
      <img src="${currentQR}" style="border-radius:12px;background:white;padding:12px" />
      <script>setTimeout(()=>location.reload(), 20000)</script>
    </body></html>
  `);
});

app.get('/qr.json', (req, res) => {
  res.json({
    status: connectionStatus,
    qr: currentQR,
    phone: phoneNumber,
    error: lastError,
  });
});

// ============ Protected endpoints ============
app.get('/status', requireApiKey, (req, res) => {
  res.json({
    status: connectionStatus,
    phone: phoneNumber,
    error: lastError,
  });
});

app.post('/send', requireApiKey, async (req, res) => {
  try {
    if (connectionStatus !== 'connected' || !sock) {
      return res.status(503).json({ error: 'not connected', status: connectionStatus });
    }
    const { to, message } = req.body || {};
    if (!to || !message) {
      return res.status(400).json({ error: 'missing to or message' });
    }

    // Normalize number to JID
    let jid = String(to).replace(/[^\d]/g, '');
    if (!jid.includes('@')) jid = `${jid}@s.whatsapp.net`;

    const result = await sock.sendMessage(jid, { text: String(message) });
    res.json({ ok: true, id: result?.key?.id || null });
  } catch (err) {
    console.error('[WA] send error:', err);
    res.status(500).json({ error: err.message });
  }
});

app.post('/logout', requireApiKey, async (req, res) => {
  try {
    if (sock) {
      try { await sock.logout(); } catch (_) {}
    }
    fs.rmSync(AUTH_DIR, { recursive: true, force: true });
    fs.mkdirSync(AUTH_DIR, { recursive: true });
    connectionStatus = 'disconnected';
    currentQR = null;
    phoneNumber = null;
    setTimeout(startSocket, 1500);
    res.json({ ok: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ============ Start ============
app.listen(PORT, '0.0.0.0', () => {
  console.log(`[HTTP] ONE Tracking WA sidecar listening on :${PORT}`);
  startSocket();
});
