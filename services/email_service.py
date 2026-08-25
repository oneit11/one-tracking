"""
Email service — sends customer notifications via SMTP (e.g. Google Workspace).
Configured from admin Settings (category "email"). Sends in a background thread
so requests are never blocked, mirroring the WhatsApp service.
"""
import smtplib
import socket
import ssl
import threading
from contextlib import contextmanager
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from flask import current_app
from services.settings_service import get_setting


@contextmanager
def _force_ipv4():
    """Temporarily make socket.getaddrinfo return IPv4 addresses only.

    On some hosts (e.g. Railway) the container has no IPv6 route, so Python
    tries an IPv6 address for smtp.gmail.com first and fails with
    '[Errno 101] Network is unreachable'. Filtering to IPv4 avoids that while
    keeping the hostname intact so TLS certificate verification still passes.
    """
    orig = socket.getaddrinfo

    def ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
        res = orig(host, port, socket.AF_INET, type, proto, flags)
        return res or orig(host, port, family, type, proto, flags)

    socket.getaddrinfo = ipv4_only
    try:
        yield
    finally:
        socket.getaddrinfo = orig


def _config():
    return {
        "enabled": get_setting("smtp_enabled", "false").lower() == "true",
        "provider": (get_setting("email_provider", "brevo") or "brevo").lower(),
        "brevo_api_key": get_setting("brevo_api_key", ""),
        "host": get_setting("smtp_host", "smtp.gmail.com"),
        "port": int(get_setting("smtp_port", "587") or 587),
        "use_tls": get_setting("smtp_use_tls", "true").lower() == "true",
        "user": get_setting("smtp_user", ""),
        "password": get_setting("smtp_password", ""),
        "from_name": get_setting("smtp_from_name", "ONE"),
        "from_email": get_setting("smtp_from_email", "") or get_setting("smtp_user", ""),
    }


def _send_brevo(cfg, to_email, subject, body_text, body_html=None):
    """Send via Brevo's HTTP API (works on hosts that block SMTP ports).

    Uses only the standard library over HTTPS (port 443), so no SMTP ports
    and no extra dependencies are needed. Returns (ok, error_message).
    """
    import json
    import urllib.request
    import urllib.error

    if not cfg["brevo_api_key"]:
        return False, "مفتاح Brevo API غير مضبوط"
    if not cfg["from_email"]:
        return False, "إيميل المُرسِل غير مضبوط"
    if not to_email:
        return False, "Missing recipient"

    payload = {
        "sender": {"name": str(cfg["from_name"] or "ONE"), "email": cfg["from_email"]},
        "to": [{"email": to_email}],
        "subject": subject,
        "textContent": body_text,
    }
    if body_html:
        payload["htmlContent"] = body_html

    req = urllib.request.Request(
        "https://api.brevo.com/v3/smtp/email",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "api-key": cfg["brevo_api_key"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            if 200 <= resp.status < 300:
                return True, ""
            return False, f"Brevo HTTP {resp.status}"
    except urllib.error.HTTPError as e:
        detail = ""
        try:
            detail = e.read().decode("utf-8")[:200]
        except Exception:
            pass
        if e.code in (401, 403):
            return False, f"مفتاح Brevo غير صحيح أو المُرسِل غير مُفعّل ({detail})"
        return False, f"Brevo HTTP {e.code}: {detail}"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:200]}"


def _send_sync(cfg, to_email, subject, body_text, body_html=None):
    """Blocking send. Returns (ok, error_message)."""
    if not cfg["host"] or not cfg["user"] or not cfg["password"] or not cfg["from_email"]:
        return False, "SMTP not fully configured"
    if not to_email:
        return False, "Missing recipient"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((str(cfg["from_name"]), cfg["from_email"]))
    msg["To"] = to_email
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))
    raw = msg.as_string()

    # Try the configured port first; if it fails, fall back to the other
    # common Gmail/Workspace port (587 <-> 465). IPv4 is forced throughout.
    primary = cfg["port"]
    attempts = [primary] + [p for p in (587, 465) if p != primary]
    last_err = "SMTP not reachable"
    for port in attempts:
        try:
            with _force_ipv4():
                if port == 465:
                    ctx = ssl.create_default_context()
                    server = smtplib.SMTP_SSL(cfg["host"], port, timeout=25, context=ctx)
                else:
                    server = smtplib.SMTP(cfg["host"], port, timeout=25)
                    server.ehlo()
                    if cfg["use_tls"] or port == 587:
                        server.starttls(context=ssl.create_default_context())
                        server.ehlo()
                server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["from_email"], [to_email], raw)
                server.quit()
            return True, ""
        except smtplib.SMTPAuthenticationError as e:
            # Auth errors won't be fixed by trying another port — stop early.
            return False, f"فشل تسجيل الدخول — تأكد من الإيميل و App Password ({str(e)[:150]})"
        except Exception as e:
            last_err = f"{type(e).__name__}: {str(e)[:200]} (port {port})"
            continue
    return False, last_err


def _deliver(cfg, to_email, subject, body_text, body_html=None):
    """Route to the configured provider. Returns (ok, error_message)."""
    if cfg.get("provider") == "smtp":
        return _send_sync(cfg, to_email, subject, body_text, body_html)
    # Default: Brevo HTTP API (recommended on Railway and other cloud hosts).
    return _send_brevo(cfg, to_email, subject, body_text, body_html)


def send_email(to_email, subject, body_text, body_html=None, app=None, force=False):
    """Fire-and-forget email in a background thread. Skips silently if disabled."""
    _app = app or current_app._get_current_object()
    cfg = _config()
    if not force and not cfg["enabled"]:
        return
    if not to_email:
        return

    def worker():
        with _app.app_context():
            ok, err = _deliver(cfg, to_email, subject, body_text, body_html)
            if not ok:
                _app.logger.warning(f"email send failed to {to_email}: {err}")

    threading.Thread(target=worker, daemon=True).start()


def send_test_email(to_email):
    """Synchronous test send used by the settings page. Returns (ok, message)."""
    cfg = _config()
    company = get_setting("company_name", "ONE")
    ok, err = _deliver(
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
