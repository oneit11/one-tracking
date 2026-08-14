from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app, abort
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from sqlalchemy import func, desc
from io import BytesIO
from models import db
from models.user import User
from models.client import Client, AMCContract
from models.device import Device, QRBatch, QRCode
from models.request import MaintenanceRequest, VisitReport, SupportTicket
from utils.decorators import admin_required
from utils.helpers import save_upload, next_sequence, next_client_code, next_qr_batch_code, next_qr_code
from services import whatsapp as wa
from services.qr_service import generate_qr_pdf, SIZE_MAP

admin_bp = Blueprint("admin", __name__)


# ================= Dashboard =================

@admin_bp.route("/")
@admin_required
def dashboard():
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    stats = {
        "clients_total": Client.query.filter_by(active=True).count(),
        "devices_total": Device.query.filter_by(active=True).count(),
        "requests_open": MaintenanceRequest.query.filter(
            MaintenanceRequest.status.in_(["new", "assigned", "in_progress", "report_ready"])
        ).count(),
        "requests_new": MaintenanceRequest.query.filter_by(status="new").count(),
        "requests_today": MaintenanceRequest.query.filter(
            MaintenanceRequest.created_at >= now.replace(hour=0, minute=0, second=0, microsecond=0)
        ).count(),
        "requests_week": MaintenanceRequest.query.filter(
            MaintenanceRequest.created_at >= week_ago
        ).count(),
        "requests_month": MaintenanceRequest.query.filter(
            MaintenanceRequest.created_at >= month_ago
        ).count(),
        "requests_closed_month": MaintenanceRequest.query.filter(
            MaintenanceRequest.status == "closed",
            MaintenanceRequest.closed_at >= month_ago
        ).count(),
        "tickets_open": SupportTicket.query.filter(
            SupportTicket.status.in_(["open", "in_progress"])
        ).count(),
        "technicians_total": User.query.filter_by(role="technician", active=True).count(),
        "qr_batches": QRBatch.query.count(),
        "qr_codes_total": QRCode.query.count(),
        "qr_codes_used": QRCode.query.filter(QRCode.device_id.isnot(None)).count(),
    }

    recent_requests = MaintenanceRequest.query.order_by(desc(MaintenanceRequest.created_at)).limit(10).all()

    # Status breakdown for chart
    status_counts = dict(
        db.session.query(MaintenanceRequest.status, func.count(MaintenanceRequest.id))
        .group_by(MaintenanceRequest.status).all()
    )

    return render_template(
        "admin/dashboard.html",
        stats=stats,
        recent_requests=recent_requests,
        status_counts=status_counts,
    )


# ================= Clients =================

@admin_bp.route("/clients")
@admin_required
def clients_list():
    q = request.args.get("q", "").strip()
    query = Client.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Client.company_name.ilike(like),
                Client.contact_person.ilike(like),
                Client.phone.ilike(like),
                Client.code.ilike(like),
            )
        )
    clients = query.order_by(Client.company_name).all()
    return render_template("admin/clients_list.html", clients=clients, q=q)


@admin_bp.route("/clients/new", methods=["GET", "POST"])
@admin_required
def client_new():
    if request.method == "POST":
        client = Client(
            code=next_client_code(),
            company_name=request.form.get("company_name", "").strip(),
            contact_person=request.form.get("contact_person", "").strip(),
            phone=request.form.get("phone", "").strip(),
            whatsapp=request.form.get("whatsapp", "").strip(),
            email=request.form.get("email", "").strip(),
            address=request.form.get("address", "").strip(),
            city=request.form.get("city", "").strip(),
            notes=request.form.get("notes", "").strip(),
        )
        if "logo" in request.files:
            logo = save_upload(request.files["logo"], subfolder="clients", prefix="logo_")
            if logo:
                client.logo_url = logo
        db.session.add(client)
        db.session.commit()
        flash(f"تم إضافة العميل {client.company_name}", "success")
        return redirect(url_for("admin.client_view", cid=client.id))
    return render_template("admin/client_form.html", client=None)


@admin_bp.route("/clients/<int:cid>")
@admin_required
def client_view(cid):
    client = Client.query.get_or_404(cid)
    return render_template("admin/client_view.html", client=client)


@admin_bp.route("/clients/<int:cid>/edit", methods=["GET", "POST"])
@admin_required
def client_edit(cid):
    client = Client.query.get_or_404(cid)
    if request.method == "POST":
        client.company_name = request.form.get("company_name", "").strip()
        client.contact_person = request.form.get("contact_person", "").strip()
        client.phone = request.form.get("phone", "").strip()
        client.whatsapp = request.form.get("whatsapp", "").strip()
        client.email = request.form.get("email", "").strip()
        client.address = request.form.get("address", "").strip()
        client.city = request.form.get("city", "").strip()
        client.notes = request.form.get("notes", "").strip()
        client.active = bool(request.form.get("active"))
        if "logo" in request.files and request.files["logo"].filename:
            logo = save_upload(request.files["logo"], subfolder="clients", prefix="logo_")
            if logo:
                client.logo_url = logo
        db.session.commit()
        flash("تم حفظ التعديلات", "success")
        return redirect(url_for("admin.client_view", cid=cid))
    return render_template("admin/client_form.html", client=client)


@admin_bp.route("/clients/<int:cid>/amc/new", methods=["POST"])
@admin_required
def amc_new(cid):
    client = Client.query.get_or_404(cid)
    try:
        amc = AMCContract(
            client_id=client.id,
            contract_number=request.form.get("contract_number", "").strip(),
            start_date=datetime.strptime(request.form.get("start_date"), "%Y-%m-%d").date(),
            end_date=datetime.strptime(request.form.get("end_date"), "%Y-%m-%d").date(),
            contract_value=float(request.form.get("contract_value") or 0),
            visits_per_year=int(request.form.get("visits_per_year") or 4),
            notes=request.form.get("notes", "").strip(),
        )
        if "amc_file" in request.files and request.files["amc_file"].filename:
            f = save_upload(request.files["amc_file"], subfolder="amc", prefix="amc_")
            if f:
                amc.file_url = f
        db.session.add(amc)
        db.session.commit()
        flash("تم إضافة عقد AMC", "success")
    except Exception as e:
        flash(f"خطأ: {e}", "danger")
    return redirect(url_for("admin.client_view", cid=cid))


# ================= Devices =================

@admin_bp.route("/devices")
@admin_required
def devices_list():
    q = request.args.get("q", "").strip()
    client_id = request.args.get("client_id", type=int)
    query = Device.query
    if client_id:
        query = query.filter_by(client_id=client_id)
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Device.name.ilike(like),
                Device.serial_number.ilike(like),
                Device.model.ilike(like),
            )
        )
    devices = query.order_by(desc(Device.created_at)).all()
    return render_template("admin/devices_list.html", devices=devices, q=q)


@admin_bp.route("/devices/new", methods=["GET", "POST"])
@admin_required
def device_new():
    client_id = request.args.get("client_id", type=int)
    clients = Client.query.filter_by(active=True).order_by(Client.company_name).all()
    if request.method == "POST":
        try:
            install = request.form.get("installation_date")
            warranty = request.form.get("warranty_end")
            d = Device(
                client_id=int(request.form.get("client_id")),
                name=request.form.get("name", "").strip(),
                device_type=request.form.get("device_type", ""),
                brand=request.form.get("brand", "").strip(),
                model=request.form.get("model", "").strip(),
                serial_number=request.form.get("serial_number", "").strip(),
                location=request.form.get("location", "").strip(),
                notes=request.form.get("notes", "").strip(),
                installation_date=datetime.strptime(install, "%Y-%m-%d").date() if install else None,
                warranty_end=datetime.strptime(warranty, "%Y-%m-%d").date() if warranty else None,
            )
            if "photo" in request.files and request.files["photo"].filename:
                p = save_upload(request.files["photo"], subfolder="devices", prefix="dev_")
                if p:
                    d.photo_url = p
            db.session.add(d)
            db.session.commit()

            # Optional: bind to QR
            qr_code = request.form.get("qr_code", "").strip()
            if qr_code:
                qr = QRCode.query.filter_by(code=qr_code).first()
                if qr and not qr.device_id:
                    qr.device_id = d.id
                    qr.bound_at = datetime.utcnow()
                    db.session.commit()
                    flash(f"تم ربط الجهاز بـ QR {qr_code}", "info")

            flash(f"تم إضافة الجهاز: {d.name}", "success")
            return redirect(url_for("admin.device_view", did=d.id))
        except Exception as e:
            flash(f"خطأ: {e}", "danger")
    return render_template("admin/device_form.html", device=None, clients=clients,
                           preselected_client_id=client_id, device_types=Device.DEVICE_TYPES)


@admin_bp.route("/devices/<int:did>")
@admin_required
def device_view(did):
    device = Device.query.get_or_404(did)
    return render_template("admin/device_view.html", device=device)


@admin_bp.route("/devices/<int:did>/edit", methods=["GET", "POST"])
@admin_required
def device_edit(did):
    device = Device.query.get_or_404(did)
    clients = Client.query.filter_by(active=True).order_by(Client.company_name).all()
    if request.method == "POST":
        device.client_id = int(request.form.get("client_id"))
        device.name = request.form.get("name", "").strip()
        device.device_type = request.form.get("device_type", "")
        device.brand = request.form.get("brand", "").strip()
        device.model = request.form.get("model", "").strip()
        device.serial_number = request.form.get("serial_number", "").strip()
        device.location = request.form.get("location", "").strip()
        device.notes = request.form.get("notes", "").strip()
        install = request.form.get("installation_date")
        warranty = request.form.get("warranty_end")
        device.installation_date = datetime.strptime(install, "%Y-%m-%d").date() if install else None
        device.warranty_end = datetime.strptime(warranty, "%Y-%m-%d").date() if warranty else None
        device.active = bool(request.form.get("active"))
        if "photo" in request.files and request.files["photo"].filename:
            p = save_upload(request.files["photo"], subfolder="devices", prefix="dev_")
            if p:
                device.photo_url = p
        db.session.commit()
        flash("تم حفظ التعديلات", "success")
        return redirect(url_for("admin.device_view", did=did))
    return render_template("admin/device_form.html", device=device, clients=clients,
                           device_types=Device.DEVICE_TYPES)


# ================= Maintenance Requests =================

@admin_bp.route("/requests")
@admin_required
def requests_list():
    status = request.args.get("status", "")
    query = MaintenanceRequest.query
    if status:
        query = query.filter_by(status=status)
    reqs = query.order_by(desc(MaintenanceRequest.created_at)).limit(200).all()
    return render_template("admin/requests_list.html", requests=reqs, status=status,
                           status_labels=MaintenanceRequest.STATUS_LABELS)


@admin_bp.route("/requests/<int:rid>")
@admin_required
def request_view(rid):
    req = MaintenanceRequest.query.get_or_404(rid)
    technicians = User.query.filter_by(role="technician", active=True).all()
    return render_template("admin/request_view.html", req=req, technicians=technicians)


@admin_bp.route("/requests/new", methods=["GET", "POST"])
@admin_required
def request_new():
    clients = Client.query.filter_by(active=True).order_by(Client.company_name).all()
    if request.method == "POST":
        req = MaintenanceRequest(
            request_number=next_sequence(MaintenanceRequest, "request_number", "MR"),
            client_id=int(request.form.get("client_id")),
            device_id=int(request.form.get("device_id")) if request.form.get("device_id") else None,
            title=request.form.get("title", "").strip(),
            description=request.form.get("description", "").strip(),
            priority=request.form.get("priority", "normal"),
            created_by=current_user.id,
        )
        if "photo" in request.files and request.files["photo"].filename:
            p = save_upload(request.files["photo"], subfolder="reports", prefix="req_")
            if p:
                req.submitted_photo_url = p
        db.session.add(req)
        db.session.commit()
        wa.notify_request_received(req)
        flash(f"تم إنشاء الطلب {req.request_number}", "success")
        return redirect(url_for("admin.request_view", rid=req.id))
    return render_template("admin/request_form.html", clients=clients)


@admin_bp.route("/requests/<int:rid>/assign", methods=["POST"])
@admin_required
def request_assign(rid):
    req = MaintenanceRequest.query.get_or_404(rid)
    tech_id = int(request.form.get("technician_id"))
    tech = User.query.get_or_404(tech_id)
    if tech.role != "technician":
        flash("المستخدم المختار ليس فني", "danger")
        return redirect(url_for("admin.request_view", rid=rid))
    req.technician_id = tech_id
    req.status = "assigned"
    req.assigned_at = datetime.utcnow()
    db.session.commit()
    wa.notify_technician_assigned(req)
    flash(f"تم تعيين {tech.name}", "success")
    return redirect(url_for("admin.request_view", rid=rid))


@admin_bp.route("/requests/<int:rid>/close", methods=["POST"])
@admin_required
def request_close(rid):
    req = MaintenanceRequest.query.get_or_404(rid)
    if req.status == "closed":
        flash("الطلب مغلق بالفعل", "info")
        return redirect(url_for("admin.request_view", rid=rid))
    req.status = "closed"
    req.closed_at = datetime.utcnow()
    db.session.commit()
    wa.notify_request_closed(req)
    flash("تم إغلاق الطلب", "success")
    return redirect(url_for("admin.request_view", rid=rid))


# ================= Support Tickets =================

@admin_bp.route("/tickets")
@admin_required
def tickets_list():
    status = request.args.get("status", "")
    query = SupportTicket.query
    if status:
        query = query.filter_by(status=status)
    tickets = query.order_by(desc(SupportTicket.created_at)).limit(200).all()
    return render_template("admin/tickets_list.html", tickets=tickets, status=status)


@admin_bp.route("/tickets/new", methods=["GET", "POST"])
@admin_required
def ticket_new():
    clients = Client.query.filter_by(active=True).order_by(Client.company_name).all()
    if request.method == "POST":
        t = SupportTicket(
            ticket_number=next_sequence(SupportTicket, "ticket_number", "TK"),
            client_id=int(request.form.get("client_id")),
            subject=request.form.get("subject", "").strip(),
            description=request.form.get("description", "").strip(),
            priority=request.form.get("priority", "normal"),
            created_by=current_user.id,
        )
        db.session.add(t)
        db.session.commit()
        flash(f"تم إنشاء التذكرة {t.ticket_number}", "success")
        return redirect(url_for("admin.tickets_list"))
    return render_template("admin/ticket_form.html", clients=clients)


# ================= Users =================

@admin_bp.route("/users")
@admin_required
def users_list():
    users = User.query.order_by(User.role, User.name).all()
    return render_template("admin/users_list.html", users=users)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@admin_required
def user_new():
    clients = Client.query.filter_by(active=True).order_by(Client.company_name).all()
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if User.query.filter_by(email=email).first():
            flash("البريد الإلكتروني مستخدم بالفعل", "danger")
            return render_template("admin/user_form.html", user=None, clients=clients)
        u = User(
            name=request.form.get("name", "").strip(),
            email=email,
            phone=request.form.get("phone", "").strip(),
            role=request.form.get("role", "client"),
            active=True,
            password_hash=generate_password_hash(request.form.get("password", "changeme123")),
        )
        if u.role == "client":
            cid = request.form.get("client_id")
            u.client_id = int(cid) if cid else None
        db.session.add(u)
        db.session.commit()
        flash(f"تم إضافة {u.name}", "success")
        return redirect(url_for("admin.users_list"))
    return render_template("admin/user_form.html", user=None, clients=clients)


@admin_bp.route("/users/<int:uid>/edit", methods=["GET", "POST"])
@admin_required
def user_edit(uid):
    u = User.query.get_or_404(uid)
    clients = Client.query.filter_by(active=True).order_by(Client.company_name).all()
    if request.method == "POST":
        u.name = request.form.get("name", "").strip()
        u.phone = request.form.get("phone", "").strip()
        u.role = request.form.get("role", u.role)
        u.active = bool(request.form.get("active"))
        if u.role == "client":
            cid = request.form.get("client_id")
            u.client_id = int(cid) if cid else None
        else:
            u.client_id = None
        new_pw = request.form.get("password", "").strip()
        if new_pw:
            u.password_hash = generate_password_hash(new_pw)
        db.session.commit()
        flash("تم الحفظ", "success")
        return redirect(url_for("admin.users_list"))
    return render_template("admin/user_form.html", user=u, clients=clients)


# ================= QR Batches =================

@admin_bp.route("/qr")
@admin_required
def qr_home():
    batches = QRBatch.query.order_by(desc(QRBatch.created_at)).all()
    return render_template("admin/qr_batches.html", batches=batches, sizes=SIZE_MAP)


@admin_bp.route("/qr/new", methods=["POST"])
@admin_required
def qr_batch_new():
    count = int(request.form.get("count", 50))
    size = request.form.get("size", "medium")
    if count < 1 or count > 5000:
        flash("العدد يجب أن يكون بين 1 و 5000", "danger")
        return redirect(url_for("admin.qr_home"))

    batch = QRBatch(
        batch_code=next_qr_batch_code(),
        count=count,
        size=size,
        created_by=current_user.id,
        notes=request.form.get("notes", "").strip(),
    )
    db.session.add(batch)
    db.session.flush()

    # Generate codes with globally unique IDs
    last_code = QRCode.query.order_by(desc(QRCode.id)).first()
    start_index = (last_code.id + 1) if last_code else 1

    for i in range(count):
        code = next_qr_code(start_index + i)
        qr = QRCode(code=code, batch_id=batch.id)
        db.session.add(qr)

    db.session.commit()
    flash(f"تم إنشاء الباتش {batch.batch_code} ({count} كود)", "success")
    return redirect(url_for("admin.qr_batch_view", bid=batch.id))


@admin_bp.route("/qr/<int:bid>")
@admin_required
def qr_batch_view(bid):
    batch = QRBatch.query.get_or_404(bid)
    return render_template("admin/qr_batch_view.html", batch=batch, sizes=SIZE_MAP)


@admin_bp.route("/qr/<int:bid>/pdf")
@admin_required
def qr_batch_pdf(bid):
    batch = QRBatch.query.get_or_404(bid)
    size = request.args.get("size", batch.size)
    if size not in SIZE_MAP:
        size = "medium"
    pdf = generate_qr_pdf(
        batch.codes,
        size=size,
        app_url=current_app.config.get("APP_URL", ""),
        company_name=current_app.config.get("COMPANY_NAME", ""),
        company_phone=current_app.config.get("COMPANY_PHONE", ""),
    )
    return send_file(
        BytesIO(pdf),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"QR-{batch.batch_code}-{size}.pdf",
    )
