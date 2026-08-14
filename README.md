# ONE Tracking

نظام إدارة الصيانة والدعم الفني لـ ONE For Integrated Solutions

## المميزات

- **3 أدوار:** Admin / Technician / Client
- **إدارة طلبات الصيانة** بدورة حياة كاملة (new → assigned → in_progress → report_ready → closed)
- **بوابة العميل** لمتابعة الطلبات خطوة بخطوة
- **QR Codes:** توليد باتشات + طباعة PDF بـ 3 مقاسات (2سم / 3سم / 5سم)
- **إشعارات WhatsApp** عبر Meta Cloud API (6 رسائل)
- **إدارة عقود AMC** + مرفقات + شعارات
- **Dashboard** بأرقام حقيقية
- **RTL عربي** بدون فريمورك JS

## التشغيل محلياً

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# عدّل .env حسب الحاجة
python app.py
```

يفتح على http://localhost:5000

**دخول افتراضي:** admin@one4in.com / ChangeMe@2026

## النشر على Railway

1. اعمل push للـ repo على GitHub
2. من Railway → New Project → Deploy from GitHub
3. أضف قاعدة بيانات PostgreSQL (Railway → New → Database → PostgreSQL)
4. في Variables، ضيف المتغيرات من `.env.example` (الـ DATABASE_URL يتحط تلقائياً)
5. أول deploy، النظام هيعمل create_all وينشئ admin افتراضي

## إعداد WhatsApp Meta Cloud API

1. من Meta for Developers → أنشئ WhatsApp App
2. احصل على **Phone Number ID** و **Permanent Access Token**
3. ضيف في Environment Variables:
   ```
   WA_ENABLED=true
   WA_PHONE_NUMBER_ID=...
   WA_ACCESS_TOKEN=...
   WA_VERIFY_TOKEN=one-tracking-verify-2026
   ```
4. في Meta App → Webhooks → Configure:
   - Callback URL: `https://your-app.up.railway.app/api/wa/webhook`
   - Verify Token: نفس اللي فوق

## Emergency Migrations

لو محتاج تضيف عمود بعد النشر:

```bash
curl -X POST https://your-app.up.railway.app/api/emergency/migrate \
  -H "X-Emergency-Secret: ONE-Tracking-Emergency-2026"
```

## Stack

- Backend: Flask 3 + SQLAlchemy + PostgreSQL
- Frontend: HTML/CSS/JS نظيف (RTL عربي، Cairo font)
- PDF/QR: reportlab + qrcode
- Deploy: Railway (Nixpacks + Gunicorn)

## الهيكل

```
one-tracking/
├── app.py                  # App factory
├── config.py               # Config
├── models/                 # DB models
├── routes/                 # Blueprints
├── services/               # WhatsApp + QR
├── templates/              # Jinja2 templates
├── static/                 # CSS/JS/uploads
├── utils/                  # Helpers + decorators
├── Procfile
├── railway.json
└── requirements.txt
```
