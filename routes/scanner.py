from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import desc
from models import db
from models.device import QRCode
from models.extras import Notification, AuditLog, Rating
from services.notifications import recent_for_user, unread_count, mark_all_read
from utils.decorators import admin_required

scanner_bp = Blueprint("scanner", __name__)
notifs_bp = Blueprint("notifications", __name__)
audit_bp = Blueprint("audit", __name__)
rating_bp = Blueprint("rating", __name__)
pwa_bp = Blueprint("pwa", __name__)


# ============ QR Scanner ============
@scanner_bp.route("/scan")
@login_required
def scan_page():
    """Camera scanner page for staff. Uses html5-qrcode."""
    if current_user.role not in ("admin", "technician"):
        flash("غير مصرح", "danger")
        return redirect(url_for("index"))
    return render_template("scanner/scan.html")


@scanner_bp.route("/api/scan-lookup")
@login_required
def scan_lookup():
    """Lookup a scanned QR code. Returns URL to redirect to."""
    code = (request.args.get("code") or "").strip()
    if not code:
        return jsonify({"error": "no code"}), 400

    # If code is a full URL, extract the code
    if "/d/" in code:
        code = code.split("/d/")[-1].split("?")[0].split("#")[0].strip("/")

    qr = QRCode.query.filter_by(code=code).first()
    if not qr:
        return jsonify({"error": "unknown", "code": code}), 404

    if qr.device_id:
        return jsonify({
            "found": True,
            "bound": True,
            "device_id": qr.device_id,
            "device_name": qr.device.name,
            "client_name": qr.device.client.company_name,
            "redirect": url_for("admin.device_view", did=qr.device_id) if current_user.is_admin
                        else url_for("tech.request_view", rid=0) if current_user.is_technician else "/",
        })
    return jsonify({
        "found": True, "bound": False, "code": qr.code,
        "redirect": url_for("public.bind_qr", code=qr.code),
    })


# ============ Notifications ============
@notifs_bp.route("/notifications")
@login_required
def list_all():
    items = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(desc(Notification.created_at)).limit(200).all()
    return render_template("notifications/list.html", items=items)


@notifs_bp.route("/notifications/api/recent")
@login_required
def api_recent():
    items = recent_for_user(current_user.id, 15)
    return jsonify({
        "unread": unread_count(current_user.id),
        "items": [{
            "id": n.id, "title": n.title, "body": n.body[:120],
            "icon": n.icon, "link": n.link,
            "is_read": n.is_read,
            "when": n.created_at.strftime("%m-%d %H:%M"),
        } for n in items]
    })


@notifs_bp.route("/notifications/read-all", methods=["POST"])
@login_required
def read_all():
    mark_all_read(current_user.id)
    return jsonify({"ok": True})


@notifs_bp.route("/notifications/<int:nid>/read", methods=["POST"])
@login_required
def mark_read(nid):
    n = Notification.query.get_or_404(nid)
    if n.user_id != current_user.id:
        return jsonify({"error": "forbidden"}), 403
    n.is_read = True
    db.session.commit()
    return jsonify({"ok": True})


# ============ Audit ============
@audit_bp.route("/")
@admin_required
def logs():
    logs = AuditLog.query.order_by(desc(AuditLog.created_at)).limit(500).all()
    return render_template("admin/audit/list.html", logs=logs)


# ============ Rating ============
@rating_bp.route("/rate/<token>", methods=["GET", "POST"])
def rate(token):
    r = Rating.query.filter_by(token=token).first_or_404()
    if request.method == "POST":
        try:
            stars = int(request.form.get("stars", 0))
            if 1 <= stars <= 5:
                r.stars = stars
                r.comment = request.form.get("comment", "").strip()
            # Optional technician rating
            tech_val = request.form.get("tech_stars")
            if tech_val:
                try:
                    ts = int(tech_val)
                    if 1 <= ts <= 5:
                        r.tech_stars = ts
                        r.tech_comment = request.form.get("tech_comment", "").strip()
                except (ValueError, TypeError):
                    pass
            r.rated_at = datetime.utcnow()
            db.session.commit()
            return render_template("portal/rating/thanks.html", rating=r)
        except (ValueError, TypeError):
            flash("رجاءً اختر تقييم من 1 إلى 5", "warning")
    return render_template("portal/rating/form.html", rating=r)


# ============ PWA ============
@pwa_bp.route("/manifest.json")
def manifest():
    from services.settings_service import get_setting
    app_name = get_setting("app_name", "ONE Tracking")
    short_name = get_setting("app_short_name", "ONE Track")
    primary = get_setting("primary_color", "#0b3d91")

    return jsonify({
        "name": app_name,
        "short_name": short_name,
        "description": "نظام إدارة الصيانة والدعم الفني",
        "start_url": "/",
        "display": "standalone",
        "orientation": "portrait-primary",
        "background_color": "#f4f6fb",
        "theme_color": primary,
        "lang": "ar",
        "dir": "rtl",
        "icons": [
            {"src": "/static/img/pwa/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/static/img/pwa/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/static/img/pwa/icon-512-maskable.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        "shortcuts": [
            {"name": "لوحة التحكم", "url": "/admin/"},
            {"name": "ماسح QR", "url": "/scan"},
        ],
    })


@pwa_bp.route("/sw.js")
def service_worker():
    from flask import Response
    sw = """
const CACHE_NAME = 'one-tracking-v1';
const STATIC = ['/', '/static/css/main.css', '/static/js/main.js', '/manifest.json'];

self.addEventListener('install', e => {
    e.waitUntil(caches.open(CACHE_NAME).then(c => c.addAll(STATIC)));
    self.skipWaiting();
});

self.addEventListener('activate', e => {
    e.waitUntil(caches.keys().then(keys =>
        Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ));
    self.clients.claim();
});

self.addEventListener('fetch', e => {
    if (e.request.method !== 'GET') return;
    const url = new URL(e.request.url);
    // Network-first for API/dynamic, cache-first for static
    if (url.pathname.startsWith('/static/') || url.pathname === '/manifest.json') {
        e.respondWith(caches.match(e.request).then(r => r || fetch(e.request).then(res => {
            const clone = res.clone();
            caches.open(CACHE_NAME).then(c => c.put(e.request, clone));
            return res;
        }).catch(() => caches.match('/'))));
    }
});
"""
    return Response(sw, mimetype="application/javascript")
