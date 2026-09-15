"""
Device-facing IoT API — endpoints the ESP32 units call directly over HTTPS.

Auth model:
    - /api/iot/provision   uses claim_code (short, one-time, in body)
    - /api/iot/telemetry   uses X-Device-Id + X-Api-Key headers
    - /api/iot/alarm       uses X-Device-Id + X-Api-Key headers

Alarm triggers (in decreasing severity):
    - smoke (digital DO high on MQ)              → 🚨 WhatsApp instantly, cooldown 5 min
    - temp / humidity out of range               → ⚠️ WhatsApp, dedupe 30 min
    - device offline for > 10 minutes            → 🔌 handled by background reaper (future)
"""
import secrets
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, abort, current_app
from models import db
from models.iot_device import IoTDevice, IoTReading, IoTAlarm
from services import whatsapp as wa

iot_bp = Blueprint("iot", __name__)

# ================== helpers ==================
def _auth_device():
    device_id = request.headers.get("X-Device-Id", "").strip()
    api_key = request.headers.get("X-Api-Key", "").strip()
    if not device_id or not api_key:
        abort(401)
    dev = IoTDevice.query.filter_by(device_id=device_id, api_key=api_key).first()
    if not dev or not dev.is_active:
        abort(401)
    return dev


def _fmt_time(dt):
    return (dt or datetime.utcnow()).strftime("%Y-%m-%d %H:%M:%S")


def _send_alarm_wa(dev, alarm, subject_line, body_lines):
    """Fan out one WhatsApp message to the client + every admin/alert phone."""
    message = f"{subject_line}\n\n"
    message += f"🖥️ الجهاز: {dev.name or dev.device_id}\n"
    if dev.location:
        message += f"📍 الموقع: {dev.location}\n"
    if dev.client and dev.client.company_name:
        message += f"🏢 العميل: {dev.client.company_name}\n"
    for line in body_lines:
        message += line + "\n"
    message += f"🕐 الوقت: {_fmt_time(alarm.ts)}"

    # Client
    if dev.client and dev.client.notify_number:
        wa.send_wa(dev.client.notify_number, message,
                   event_type=f"iot_{alarm.alarm_type}",
                   entity_type="iot_device", entity_id=dev.id, dedupe=False)

    # Admins — pull the alert_phones setting (comma-separated numbers)
    from services.settings_service import get_setting
    admin_phones = get_setting("iot_alert_phones", "") or ""
    for phone in [p.strip() for p in admin_phones.split(",") if p.strip()]:
        wa.send_wa(phone, message,
                   event_type=f"iot_{alarm.alarm_type}",
                   entity_type="iot_device", entity_id=dev.id, dedupe=False)


def _recent_alarm(dev, alarm_type, within_min):
    cutoff = datetime.utcnow() - timedelta(minutes=within_min)
    return IoTAlarm.query.filter(
        IoTAlarm.device_id == dev.id,
        IoTAlarm.alarm_type == alarm_type,
        IoTAlarm.ts >= cutoff,
    ).first()


def _check_thresholds(dev, temp, humid):
    """Fire warning alarms when readings escape the configured band.
    Deduped to 30 minutes per (device, kind) to avoid WhatsApp spam."""
    events = []
    if temp is not None:
        if temp > dev.temp_max:
            events.append(("temp_high", temp, f"⚠️ درجة الحرارة مرتفعة: {temp:.1f}°C (الحد: {dev.temp_max:.1f}°C)"))
        elif temp < dev.temp_min:
            events.append(("temp_low", temp, f"⚠️ درجة الحرارة منخفضة: {temp:.1f}°C (الحد: {dev.temp_min:.1f}°C)"))
    if humid is not None:
        if humid > dev.humid_max:
            events.append(("humid_high", humid, f"⚠️ الرطوبة مرتفعة: {humid:.0f}% (الحد: {dev.humid_max:.0f}%)"))
        elif humid < dev.humid_min:
            events.append(("humid_low", humid, f"⚠️ الرطوبة منخفضة: {humid:.0f}% (الحد: {dev.humid_min:.0f}%)"))

    for kind, value, body in events:
        if _recent_alarm(dev, kind, within_min=30):
            continue
        a = IoTAlarm(device_id=dev.id, alarm_type=kind, value=value, message=body)
        db.session.add(a)
        db.session.flush()
        _send_alarm_wa(dev, a, "⚠️ *تنبيه من غرفة السيرفر*", [body])
        a.notified = True


# ================== provisioning ==================
@iot_bp.route("/api/iot/provision", methods=["POST"])
def provision():
    """
    Body: { "device_id": "SR-1A2B3C", "claim": "742391" }
    Response: { "api_key": "..." }

    The admin created a device row with claim_code before shipping.
    On first successful match we bind device_id and issue an api_key.
    Idempotent: hitting it again with the same device_id + api_key returns
    the same api_key (so a factory-reset unit can re-provision).
    """
    data = request.get_json(silent=True) or {}
    device_id = (data.get("device_id") or "").strip()
    claim = (data.get("claim") or "").strip()
    if not device_id or not claim:
        return jsonify(error="device_id and claim are required"), 400

    dev = IoTDevice.query.filter_by(claim_code=claim).first()
    if not dev:
        # Maybe already claimed by this device — allow re-auth for factory resets.
        dev = IoTDevice.query.filter_by(device_id=device_id).first()
        if not dev or not dev.api_key:
            return jsonify(error="invalid claim code"), 401

    # Bind if first time
    if not dev.device_id:
        dev.device_id = device_id
    elif dev.device_id != device_id:
        # Someone else's claim used with a different device_id — reject
        return jsonify(error="claim already used"), 409

    if not dev.api_key:
        dev.api_key = secrets.token_hex(24)

    db.session.commit()
    return jsonify(api_key=dev.api_key, device_id=dev.device_id, name=dev.name or "")


# ================== telemetry ==================
@iot_bp.route("/api/iot/telemetry", methods=["POST"])
def telemetry():
    dev = _auth_device()
    data = request.get_json(silent=True) or {}
    temp = data.get("temp")
    humid = data.get("humidity")
    smoke_a = data.get("smoke_analog")
    smoke_d = bool(data.get("smoke_digital"))
    rssi = data.get("wifi_rssi")

    r = IoTReading(
        device_id=dev.id, temp=temp, humidity=humid,
        smoke_analog=smoke_a, smoke_digital=smoke_d,
    )
    db.session.add(r)

    dev.last_seen = datetime.utcnow()
    dev.last_temp = temp
    dev.last_humid = humid
    dev.last_smoke_a = smoke_a
    dev.last_smoke_d = smoke_d
    if rssi is not None:
        dev.last_rssi = rssi

    _check_thresholds(dev, temp, humid)
    db.session.commit()
    return jsonify(ok=True)


# ================== fire alarm ==================
@iot_bp.route("/api/iot/alarm", methods=["POST"])
def alarm():
    dev = _auth_device()
    data = request.get_json(silent=True) or {}
    a_type = (data.get("type") or "smoke").strip()
    value = data.get("smoke_analog") or 0

    # 5-minute cooldown to avoid WhatsApp storm during actual fire
    if _recent_alarm(dev, a_type, within_min=5):
        return jsonify(ok=True, deduped=True)

    body = f"🔥 قراءة الدخان: {value}"
    a = IoTAlarm(device_id=dev.id, alarm_type=a_type, value=float(value), message=body)
    db.session.add(a)
    db.session.flush()

    _send_alarm_wa(dev, a, "🚨 *إنذار حريق - دخان مكتشف* 🚨",
                   [body, "⚠️ يرجى المتابعة الفورية والتحقق من غرفة السيرفر"])
    a.notified = True
    db.session.commit()
    return jsonify(ok=True)


# ================== public status (for admin/portal UIs) ==================
@iot_bp.route("/api/iot/status/<int:dev_id>")
def public_status(dev_id):
    """
    Read-only public snapshot for the dashboards to poll. Returns just the
    latest state — no history — so it stays cheap.
    The UI page itself is @login_required; this endpoint is unauthenticated
    on purpose so the poll doesn't die if a session lapses.
    """
    dev = IoTDevice.query.get_or_404(dev_id)
    return jsonify(
        online=dev.online,
        last_seen=dev.last_seen.isoformat() if dev.last_seen else None,
        temp=dev.last_temp, humid=dev.last_humid,
        smoke_a=dev.last_smoke_a, smoke_d=dev.last_smoke_d,
        temp_status=dev.temp_status, humid_status=dev.humid_status,
        smoke_status=dev.smoke_status, overall=dev.overall_status,
    )


@iot_bp.route("/api/iot/history/<int:dev_id>")
def history(dev_id):
    """Last 288 readings (~24h @ 30s interval) for the chart."""
    dev = IoTDevice.query.get_or_404(dev_id)
    rows = IoTReading.query.filter_by(device_id=dev.id) \
        .order_by(IoTReading.ts.desc()).limit(288).all()
    rows.reverse()
    return jsonify([
        {
            "t": r.ts.isoformat(),
            "temp": r.temp, "humid": r.humidity,
            "smoke_a": r.smoke_analog, "smoke_d": r.smoke_digital,
        } for r in rows
    ])
