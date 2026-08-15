"""
WhatsApp service v2 - Baileys sidecar + DB-driven message templates.
"""
import threading
import requests
from datetime import datetime
from flask import current_app
from models import db
from models.wa_log import WhatsAppLog
from models.setting import MessageTemplate
from utils.helpers import normalize_phone
from services.settings_service import get_setting


def _send_sync(config, to_number, message, event_type, entity_type, entity_id):
    log = WhatsAppLog(
        to_number=to_number, event_type=event_type, message_body=message,
        related_entity_type=entity_type, related_entity_id=entity_id,
        status="pending", sent_at=datetime.utcnow(),
    )
    try:
        if not config["enabled"]:
            log.status = "skipped"; log.error_message = "WA disabled"
            db.session.add(log); db.session.commit(); return

        if not config["sidecar_url"] or not config["api_key"]:
            log.status = "failed"; log.error_message = "Missing sidecar config"
            db.session.add(log); db.session.commit(); return

        if not to_number:
            log.status = "failed"; log.error_message = "Missing recipient"
            db.session.add(log); db.session.commit(); return

        url = config["sidecar_url"].rstrip("/") + "/send"
        headers = {"X-API-Key": config["api_key"], "Content-Type": "application/json"}
        payload = {"to": to_number.lstrip("+"), "message": message}

        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        log.provider_response = resp.text[:2000]
        if resp.status_code in (200, 201):
            log.status = "sent"
        else:
            log.status = "failed"
            log.error_message = f"HTTP {resp.status_code}: {resp.text[:200]}"
    except Exception as e:
        log.status = "failed"; log.error_message = str(e)[:500]
    finally:
        db.session.add(log); db.session.commit()


def send_wa(to_number, message, event_type="", entity_type="", entity_id=None, app=None):
    _app = app or current_app._get_current_object()
    to_norm = normalize_phone(to_number)
    if not to_norm:
        return

    # Load from settings (DB) first, fall back to config
    enabled = get_setting("wa_enabled", str(_app.config.get("WA_ENABLED", False))).lower() == "true"
    sidecar = get_setting("wa_sidecar_url", "") or _app.config.get("WA_SIDECAR_URL", "")
    api_key = _app.config.get("WA_SIDECAR_API_KEY", "")

    config = {"enabled": enabled, "sidecar_url": sidecar, "api_key": api_key}

    def worker():
        with _app.app_context():
            _send_sync(config, to_norm, message, event_type, entity_type, entity_id)

    threading.Thread(target=worker, daemon=True).start()


def render_template_msg(code, **kwargs):
    """Render a template by code with variables. Returns None if template not found."""
    tpl = MessageTemplate.query.filter_by(code=code, active=True).first()
    if not tpl:
        return None
    return tpl.render(**kwargs)


# ============ Sidecar management ============

def get_sidecar_status(app=None):
    _app = app or current_app._get_current_object()
    url = (get_setting("wa_sidecar_url") or _app.config.get("WA_SIDECAR_URL", "")).rstrip("/")
    api_key = _app.config.get("WA_SIDECAR_API_KEY", "")
    if not url:
        return None
    try:
        r = requests.get(f"{url}/status", headers={"X-API-Key": api_key}, timeout=5)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def get_sidecar_qr(app=None):
    _app = app or current_app._get_current_object()
    url = (get_setting("wa_sidecar_url") or _app.config.get("WA_SIDECAR_URL", "")).rstrip("/")
    if not url:
        return None
    try:
        r = requests.get(f"{url}/qr.json", timeout=5)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None


def logout_sidecar(app=None):
    _app = app or current_app._get_current_object()
    url = (get_setting("wa_sidecar_url") or _app.config.get("WA_SIDECAR_URL", "")).rstrip("/")
    api_key = _app.config.get("WA_SIDECAR_API_KEY", "")
    if not url:
        return False
    try:
        r = requests.post(f"{url}/logout", headers={"X-API-Key": api_key}, timeout=10)
        return r.status_code == 200
    except Exception:
        return False


# ============ Event notifications ============

def notify_request_received(request, app=None):
    from models.user import User
    _app = app or current_app._get_current_object()
    company_name = get_setting("company_name", "الشركة")

    client_msg = render_template_msg(
        "request_received_client",
        client_name=request.client.contact_person or request.client.company_name,
        request_number=request.request_number,
        title=request.title,
        company_name=company_name,
    )
    admin_msg = render_template_msg(
        "request_received_admin",
        request_number=request.request_number,
        client_name=request.client.company_name,
        title=request.title,
        priority=request.priority_label,
    )

    if client_msg and request.client.notify_number:
        send_wa(request.client.notify_number, client_msg,
                event_type="request_received", entity_type="request", entity_id=request.id, app=_app)

    if admin_msg:
        for admin in User.query.filter_by(role="admin", active=True).all():
            if admin.phone:
                send_wa(admin.phone, admin_msg,
                        event_type="request_received_admin", entity_type="request", entity_id=request.id, app=_app)


def notify_technician_assigned(request, app=None):
    _app = app or current_app._get_current_object()
    company_name = get_setting("company_name", "الشركة")
    tech = request.technician

    tech_msg = render_template_msg(
        "tech_assigned_tech",
        tech_name=tech.name, request_number=request.request_number,
        client_name=request.client.company_name, client_phone=request.client.phone,
        client_address=request.client.address, title=request.title,
        priority=request.priority_label,
    )
    client_msg = render_template_msg(
        "tech_assigned_client",
        tech_name=tech.name, request_number=request.request_number,
        company_name=company_name,
    )

    if tech_msg and tech.phone:
        send_wa(tech.phone, tech_msg,
                event_type="tech_assigned_tech", entity_type="request", entity_id=request.id, app=_app)
    if client_msg and request.client.notify_number:
        send_wa(request.client.notify_number, client_msg,
                event_type="tech_assigned_client", entity_type="request", entity_id=request.id, app=_app)


def notify_report_ready(request, app=None):
    from models.user import User
    _app = app or current_app._get_current_object()
    company_name = get_setting("company_name", "الشركة")
    app_url = _app.config.get("APP_URL", "")
    report = request.visit_report
    portal_link = f"{app_url}/portal/requests/{request.id}" if app_url else ""

    client_msg = render_template_msg(
        "report_ready_client",
        request_number=request.request_number,
        portal_link=portal_link, company_name=company_name,
    )
    admin_msg = render_template_msg(
        "report_ready_admin",
        request_number=request.request_number,
        client_name=request.client.company_name,
        tech_name=report.technician.name if report else "",
        resolved="تم الحل" if report and report.resolved else "يحتاج متابعة",
    )

    if client_msg and request.client.notify_number:
        send_wa(request.client.notify_number, client_msg,
                event_type="report_ready_client", entity_type="request", entity_id=request.id, app=_app)
    if admin_msg:
        for admin in User.query.filter_by(role="admin", active=True).all():
            if admin.phone:
                send_wa(admin.phone, admin_msg,
                        event_type="report_ready_admin", entity_type="request", entity_id=request.id, app=_app)


def notify_request_closed(request, app=None):
    from models.user import User
    _app = app or current_app._get_current_object()
    company_name = get_setting("company_name", "الشركة")
    app_url = _app.config.get("APP_URL", "")

    # Generate rating link if enabled
    rating_link = ""
    if get_setting("rating_enabled", "true").lower() == "true":
        from models.extras import Rating
        import secrets
        rating = Rating.query.filter_by(request_id=request.id).first()
        if not rating:
            rating = Rating(request_id=request.id, token=secrets.token_urlsafe(16))
            db.session.add(rating)
            db.session.commit()
        rating_link = f"{app_url}/rate/{rating.token}" if app_url else ""

    client_msg = render_template_msg(
        "request_closed_client",
        request_number=request.request_number,
        rating_link=rating_link, company_name=company_name,
    )
    admin_msg = render_template_msg(
        "request_closed_admin",
        request_number=request.request_number,
        client_name=request.client.company_name,
    )

    if client_msg and request.client.notify_number:
        send_wa(request.client.notify_number, client_msg,
                event_type="request_closed_client", entity_type="request", entity_id=request.id, app=_app)
    if admin_msg:
        for admin in User.query.filter_by(role="admin", active=True).all():
            if admin.phone:
                send_wa(admin.phone, admin_msg,
                        event_type="request_closed_admin", entity_type="request", entity_id=request.id, app=_app)


def notify_new_user_credentials(user, password, app=None):
    """Send login credentials to newly created user via WA."""
    _app = app or current_app._get_current_object()
    if get_setting("wa_send_credentials_to_new_users", "true").lower() != "true":
        return
    if not user.phone:
        return

    msg = render_template_msg(
        "user_credentials",
        user_name=user.name, email=user.email, password=password,
        app_url=_app.config.get("APP_URL", ""),
        company_name=get_setting("company_name", "الشركة"),
    )
    if msg:
        send_wa(user.phone, msg,
                event_type="user_credentials", entity_type="user", entity_id=user.id, app=_app)
