# ONE Tracking - WhatsApp Sidecar

خدمة Node.js صغيرة تربط بين ONE Tracking (Flask) و WhatsApp Web عبر Baileys.

## API

- `GET /health` — health check (public)
- `GET /qr` — HTML صفحة QR للعرض (public)
- `GET /qr.json` — JSON `{status, qr, phone, error}` (public)
- `GET /status` — connection status (requires `X-API-Key`)
- `POST /send` — `{to, message}` (requires `X-API-Key`)
- `POST /logout` — clear session (requires `X-API-Key`)

## التشغيل المحلي

```bash
npm install
cp .env.example .env
node server.js
```

افتح `http://localhost:3000/qr` وامسح QR بواتس الشركة.

## النشر على Railway

1. Push الريبو على GitHub
2. Railway → New Service → Deploy from GitHub
3. **مهم:** ضيف **Volume** على المسار `/data` (Railway → Settings → Volumes)
4. Environment Variables:
   ```
   API_KEY=ONE-Tracking-WA-Secret-2026
   AUTH_DIR=/data/auth_info
   ```
5. Generate Domain للحصول على URL
6. في ONE Tracking Flask: ضيف
   ```
   WA_SIDECAR_URL=https://<sidecar>.up.railway.app
   WA_SIDECAR_API_KEY=ONE-Tracking-WA-Secret-2026
   WA_ENABLED=true
   ```

## ملاحظات

- Session بيتحفظ في `/data/auth_info` — لو الـ Volume اتمسح، هترجع تربط QR من جديد.
- Baileys غير رسمي — استخدمه على رقم Business مخصص للنظام.
- الرسايل تروح بشكل عادي بس بترتيب زمني عشان تجنب rate-limits.
