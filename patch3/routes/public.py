from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, jsonify, current_app, abort, flash
from flask_login import current_user, login_required
from sqlalchemy import text
from models import db
from models.device import QRCode, Device
from models.client import Client
from utils.i18n import set_lang

public_bp = Blueprint("public", __name__)


@public_bp.route("/set-lang/<lang>")
def switch_lang(lang):
    """Toggle UI language."""
    set_lang(lang)
    return redirect(request.referrer or url_for("index"))


@public_bp.route("/health")
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})


@public_bp.route("/d/<code>")
def scan(code):
    """QR scan endpoint. Public entry — routes to appropriate view."""
    qr = QRCode.query.filter_by(code=code).first()
    if not qr:
        return render_template("public/qr_invalid.html", code=code), 404

    if qr.is_bound:
        device = qr.device
        # Public view: minimal info + call button
        return render_template("public/device_public.html", device=device, qr=qr)

    # Not bound: require auth to bind
    if not current_user.is_authenticated:
        flash("امسح QR وقم بتسجيل الدخول لربطه بجهاز", "info")
        return redirect(url_for("auth.login", next=request.path))

    if current_user.role not in ("admin", "technician"):
        abort(403)

    return redirect(url_for("public.bind_qr", code=code))


@public_bp.route("/d/<code>/bind", methods=["GET", "POST"])
@login_required
def bind_qr(code):
    if current_user.role not in ("admin", "technician"):
        abort(403)
    qr = QRCode.query.filter_by(code=code).first_or_404()
    if qr.is_bound:
        flash("هذا الـ QR مربوط بالفعل", "info")
        return redirect(url_for("public.scan", code=code))

    clients = Client.query.filter_by(active=True).order_by(Client.company_name).all()

    if request.method == "POST":
        client_id = request.form.get("client_id")
        existing_device_id = request.form.get("existing_device_id")

        if existing_device_id:
            d = Device.query.get(int(existing_device_id))
            if not d:
                flash("جهاز غير موجود", "danger")
                return redirect(url_for("public.bind_qr", code=code))
            if d.qr_code:
                flash("هذا الجهاز مربوط بـ QR آخر بالفعل", "warning")
                return redirect(url_for("public.bind_qr", code=code))
            qr.device_id = d.id
        else:
            # Create new device
            d = Device(
                client_id=int(client_id),
                name=request.form.get("name", "").strip(),
                device_type=request.form.get("device_type", ""),
                brand=request.form.get("brand", "").strip(),
                model=request.form.get("model", "").strip(),
                serial_number=request.form.get("serial_number", "").strip(),
                location=request.form.get("location", "").strip(),
            )
            db.session.add(d)
            db.session.flush()
            qr.device_id = d.id

        qr.bound_at = datetime.utcnow()
        db.session.commit()
        flash(f"تم ربط الجهاز بـ {qr.code}", "success")
        return redirect(url_for("public.scan", code=code))

    return render_template("public/qr_bind.html", qr=qr, clients=clients,
                           device_types=Device.DEVICE_TYPES)


@public_bp.route("/api/emergency/migrate", methods=["POST"])
def emergency_migrate():
    """Manual migration endpoint - for adding columns after deploy."""
    secret = request.headers.get("X-Emergency-Secret") or request.json.get("secret") if request.is_json else None
    if not secret:
        secret = request.form.get("secret")
    if secret != current_app.config.get("EMERGENCY_MIGRATE_SECRET"):
        return jsonify({"error": "invalid secret"}), 403

    try:
        db.create_all()
        # Add columns idempotently
        migrations = [
            "ALTER TABLE clients ADD COLUMN IF NOT EXISTS whatsapp VARCHAR(30) DEFAULT ''",
            "ALTER TABLE clients ADD COLUMN IF NOT EXISTS logo_url VARCHAR(255) DEFAULT ''",
            "ALTER TABLE clients ADD COLUMN IF NOT EXISTS city VARCHAR(80) DEFAULT ''",
            "ALTER TABLE devices ADD COLUMN IF NOT EXISTS photo_url VARCHAR(255) DEFAULT ''",
            "ALTER TABLE devices ADD COLUMN IF NOT EXISTS warranty_end DATE",
            "ALTER TABLE maintenance_requests ADD COLUMN IF NOT EXISTS submitted_photo_url VARCHAR(255) DEFAULT ''",
            "ALTER TABLE maintenance_requests ADD COLUMN IF NOT EXISTS sla_due_at TIMESTAMP",
            "ALTER TABLE maintenance_requests ADD COLUMN IF NOT EXISTS sla_breached BOOLEAN DEFAULT FALSE",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS role_code VARCHAR(30) DEFAULT ''",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(255) DEFAULT ''",
            "ALTER TABLE ratings ADD COLUMN IF NOT EXISTS tech_stars INTEGER",
            "ALTER TABLE ratings ADD COLUMN IF NOT EXISTS tech_comment TEXT DEFAULT ''",
        ]
        results = []
        for sql in migrations:
            try:
                db.session.execute(text(sql))
                db.session.commit()
                results.append({"sql": sql, "ok": True})
            except Exception as e:
                db.session.rollback()
                results.append({"sql": sql, "ok": False, "error": str(e)[:200]})
        return jsonify({"status": "done", "results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
