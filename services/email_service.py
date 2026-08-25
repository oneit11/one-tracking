"""
Email service — sends customer notifications via SMTP (e.g. Google Workspace).
Configured from admin Settings (category "email"). Sends in a background thread
so requests are never blocked, mirroring the WhatsApp service.
"""
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from flask import current_app
from services.settings_service import get_setting


def _config():
    return {
        "enabled": get_setting("smtp_enabled", "false").lower() == "true",
        "host": get_setting("smtp_host", "smtp.gmail.com"),
        "port": int(get_setting("smtp_port", "587") or 587),
        "use_tls": get_setting("smtp_use_tls", "true").lower() == "true",
        "user": get_setting("smtp_user", ""),
        "password": get_setting("smtp_password", ""),
        "from_name": get_setting("smtp_from_name", "ONE"),
        "from_email": get_setting("smtp_from_email", "") or get_setting("smtp_user", ""),
    }


def _send_sync(cfg, to_email, subject, body_text, body_html=None):
    """Blocking send. Returns (ok, error_message)."""
    if not cfg["host"] or not cfg["user"] or not cfg["password"] or not cfg["from_email"]:
        return False, "SMTP not fully configured"
    if not to_email:
        return False, "Missing recipient"
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = formataddr((str(cfg["from_name"]), cfg["from_email"]))
        msg["To"] = to_email
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        if body_html:
            msg.attach(MIMEText(body_html, "html", "utf-8"))

        if cfg["port"] == 465:
            server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], timeout=25)
        else:
            server = smtplib.SMTP(cfg["host"], cfg["port"], timeout=25)
            if cfg["use_tls"]:
                server.starttls()
        server.login(cfg["user"], cfg["password"])
        server.sendmail(cfg["from_email"], [to_email], msg.as_string())
        server.quit()
        return True, ""
    except Exception as e:
        return False, str(e)[:300]


def send_email(to_email, subject, body_text, body_html=None, app=None, force=False):
    """Fire-and-forget email in a background thread. Skips silently if SMTP disabled."""
    _app = app or current_app._get_current_object()
    cfg = _config()
    if not force and not cfg["enabled"]:
        return
    if not to_email:
        return

    def worker():
        with _app.app_context():
            ok, err = _send_sync(cfg, to_email, subject, body_text, body_html)
            if not ok:
                _app.logger.warning(f"email send failed to {to_email}: {err}")

    threading.Thread(target=worker, daemon=True).start()


def send_test_email(to_email):
    """Synchronous test send used by the settings page. Returns (ok, message)."""
    cfg = _config()
    company = get_setting("company_name", "ONE")
    ok, err = _send_sync(
        cfg, to_email,
        f"اختبار بريد — {company}",
        f"تم إعداد البريد الإلكتروني بنجاح ✅\nهذه رسالة اختبار من نظام {company}.",
        f"<div dir='rtl' style='font-family:Arial'>تم إعداد البريد الإلكتروني بنجاح ✅<br>"
        f"هذه رسالة اختبار من نظام <b>{company}</b>.</div>",
    )
    return ok, ("تم إرسال رسالة الاختبار بنجاح" if ok else f"فشل الإرسال: {err}")


def _wrap_html(company, body_html):
    """Wrap a message body in a simple branded HTML shell."""
    return (
        "<div dir='rtl' style='font-family:Tahoma,Arial,sans-serif;background:#f4f5f7;"
        "padding:24px'><div style='max-width:600px;margin:auto;background:#fff;"
        "border-radius:12px;overflow:hidden;border:1px solid #e5e7eb'>"
        "<div style='background:#0b1020;color:#e9c86a;padding:18px 24px;font-size:18px;"
        f"font-weight:bold'>{company}</div>"
        f"<div style='padding:24px;color:#222;line-height:1.9;font-size:15px'>{body_html}</div>"
        "<div style='padding:14px 24px;background:#0b1020;color:#cfd8e8;font-size:12px'>"
        f"{company}</div></div></div>"
    )


def notify_customer_email(to_email, subject, body_text, app=None):
    """Send a branded customer email (no-op if SMTP disabled or no email)."""
    if not to_email:
        return
    company = get_setting("company_name", "ONE")
    body_html = _wrap_html(company, body_text.replace("\n", "<br>"))
    send_email(to_email, subject, body_text, body_html=body_html, app=app)
