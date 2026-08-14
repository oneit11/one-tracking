"""
WhatsApp Meta Cloud API integration.
Sends notifications in background threads to avoid blocking requests.
IMPORTANT: closure variables are extracted BEFORE thread start (Flask context safe).
"""
import threading
import requests
from datetime import datetime
from flask import current_app
from models import db
from models.wa_log import WhatsAppLog
from utils.helpers import normalize_phone


def _send_message_sync(app_config, to_number, message, event_type, entity_type, entity_id):
    """Actual HTTP call. Runs in background thread with copied config values."""
    log = WhatsAppLog(
        to_number=to_number,
        event_type=event_type,
        message_body=message,
        related_entity_type=entity_type,
        related_entity_id=entity_id,
        status="pending",
        sent_at=datetime.utcnow(),
    )
    try:
        if not app_config["enabled"]:
            log.status = "skipped"
            log.error_message = "WA_ENABLED=false"
            db.session.add(log)
            db.session.commit()
            return

        if not to_number or not app_config["phone_number_id"] or not app_config["access_token"]:
            log.status = "failed"
            log.error_message = "Missing WA config or recipient"
            db.session.add(log)
            db.session.commit()
            return

        url = f"https://graph.facebook.com/{app_config['api_version']}/{app_config['phone_number_id']}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number.lstrip("+"),
            "type": "text",
            "text": {"body": message},
        }
        headers = {
            "Authorization": f"Bearer {app_config['access_token']}",
            "Content-Type": "application/json",
        }
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        log.provider_response = resp.text[:2000]
        if resp.status_code in (200, 201):
            log.status = "sent"
        else:
            log.status = "failed"
            log.error_message = f"HTTP {resp.status_code}"
    except Exception as e:
        log.status = "failed"
        log.error_message = str(e)[:500]
    finally:
        db.session.add(log)
        db.session.commit()


def send_wa(to_number, message, event_type="", entity_type="", entity_id=None, app=None):
    """
    Enqueue a WhatsApp message in background.
    Extracts Flask config into a plain dict BEFORE spawning the thread.
    """
    _app = app or current_app._get_current_object()
    to_norm = normalize_phone(to_number)
    if not to_norm:
        return

    # Extract closure variables (Flask request context safe)
    app_config = {
        "enabled": _app.config.get("WA_ENABLED", False),
        "phone_number_id": _app.config.get("WA_PHONE_NUMBER_ID", ""),
        "access_token": _app.config.get("WA_ACCESS_TOKEN", ""),
        "api_version": _app.config.get("WA_API_VERSION", "v20.0"),
    }

    def worker():
        with _app.app_context():
            _send_message_sync(app_config, to_norm, message, event_type, entity_type, entity_id)

    threading.Thread(target=worker, daemon=True).start()


# ===== Event templates =====

def notify_request_received(request, app=None):
    """Event 1: Request received - to admin + client."""
    from models.user import User
    _app = app or current_app._get_current_object()
    company = _app.config.get("COMPANY_NAME", "الشركة")

    client_msg = (
        f"مرحباً {request.client.contact_person or request.client.company_name} 👋\n\n"
        f"تم استلام طلب الصيانة رقم: *{request.request_number}*\n"
        f"العنوان: {request.title}\n"
        f"سيتم التواصل معك قريباً لتعيين الفني.\n\n"
        f"{company}"
    )
    admin_msg = (
        f"🔔 طلب صيانة جديد\n"
        f"رقم: *{request.request_number}*\n"
        f"العميل: {request.client.company_name}\n"
        f"العنوان: {request.title}\n"
        f"الأولوية: {request.priority_label}"
    )

    # Client
    if request.client.notify_number:
        send_wa(
            request.client.notify_number, client_msg,
            event_type="request_received", entity_type="request", entity_id=request.id,
            app=_app
        )

    # All admins
    for admin in User.query.filter_by(role="admin", active=True).all():
        if admin.phone:
            send_wa(
                admin.phone, admin_msg,
                event_type="request_received_admin", entity_type="request", entity_id=request.id,
                app=_app
            )


def notify_technician_assigned(request, app=None):
    """Event 2: Technician assigned - to tech + client."""
    _app = app or current_app._get_current_object()
    company = _app.config.get("COMPANY_NAME", "الشركة")

    tech = request.technician
    tech_msg = (
        f"مرحباً {tech.name}\n\n"
        f"تم تعيينك لمهمة صيانة جديدة:\n"
        f"رقم الطلب: *{request.request_number}*\n"
        f"العميل: {request.client.company_name}\n"
        f"التليفون: {request.client.phone}\n"
        f"العنوان: {request.client.address}\n"
        f"المشكلة: {request.title}\n"
        f"الأولوية: {request.priority_label}"
    )
    client_msg = (
        f"تم تعيين المهندس *{tech.name}* لطلب الصيانة رقم *{request.request_number}*.\n"
        f"سيتواصل معك قريباً لتحديد موعد الزيارة.\n\n"
        f"{company}"
    )

    if tech.phone:
        send_wa(
            tech.phone, tech_msg,
            event_type="tech_assigned_tech", entity_type="request", entity_id=request.id,
            app=_app
        )
    if request.client.notify_number:
        send_wa(
            request.client.notify_number, client_msg,
            event_type="tech_assigned_client", entity_type="request", entity_id=request.id,
            app=_app
        )


def notify_report_ready(request, app=None):
    """Event 3: Visit report ready - to client + admin."""
    from models.user import User
    _app = app or current_app._get_current_object()
    company = _app.config.get("COMPANY_NAME", "الشركة")
    app_url = _app.config.get("APP_URL", "")

    report = request.visit_report
    portal_link = f"{app_url}/portal/requests/{request.id}" if app_url else ""

    client_msg = (
        f"تم رفع تقرير زيارة الصيانة لطلب *{request.request_number}*.\n"
        f"يمكنك مراجعة التقرير من بوابتي:\n{portal_link}\n\n"
        f"{company}"
    )
    admin_msg = (
        f"📋 تقرير زيارة جاهز\n"
        f"طلب: *{request.request_number}*\n"
        f"العميل: {request.client.company_name}\n"
        f"الفني: {report.technician.name if report else ''}\n"
        f"الحالة: {'تم الحل' if report and report.resolved else 'يحتاج متابعة'}"
    )

    if request.client.notify_number:
        send_wa(
            request.client.notify_number, client_msg,
            event_type="report_ready_client", entity_type="request", entity_id=request.id,
            app=_app
        )
    for admin in User.query.filter_by(role="admin", active=True).all():
        if admin.phone:
            send_wa(
                admin.phone, admin_msg,
                event_type="report_ready_admin", entity_type="request", entity_id=request.id,
                app=_app
            )


def notify_request_closed(request, app=None):
    """Event 4: Request closed - to client + admin."""
    from models.user import User
    _app = app or current_app._get_current_object()
    company = _app.config.get("COMPANY_NAME", "الشركة")

    client_msg = (
        f"تم إغلاق طلب الصيانة رقم *{request.request_number}* بنجاح.\n"
        f"شكراً لثقتكم بنا.\n\n"
        f"{company}"
    )
    admin_msg = (
        f"✅ تم إغلاق طلب\n"
        f"رقم: *{request.request_number}*\n"
        f"العميل: {request.client.company_name}"
    )

    if request.client.notify_number:
        send_wa(
            request.client.notify_number, client_msg,
            event_type="request_closed_client", entity_type="request", entity_id=request.id,
            app=_app
        )
    for admin in User.query.filter_by(role="admin", active=True).all():
        if admin.phone:
            send_wa(
                admin.phone, admin_msg,
                event_type="request_closed_admin", entity_type="request", entity_id=request.id,
                app=_app
            )
