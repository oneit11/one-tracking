from datetime import datetime, timedelta
import os
import secrets
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file, current_app, abort, jsonify
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from sqlalchemy import func, desc, or_
from io import BytesIO
from models import db
from models.user import User
from models.client import Client, AMCContract
from models.device import Device, QRBatch, QRCode
from models.request import MaintenanceRequest, VisitReport, SupportTicket
from models.extras import Notification, Comment, Rating, Followup, PMSchedule
from models.permission import Role
from models.wa_log import WhatsAppLog
from utils.decorators import admin_required, permission_required
from utils.helpers import save_upload, next_sequence, next_client_code, next_qr_batch_code, next_qr_code
from services import whatsapp as wa
from services.whatsapp import (get_sidecar_status, get_sidecar_qr, logout_sidecar,
                                send_wa, notify_new_user_credentials)
from services.qr_service import generate_qr_pdf, SIZE_MAP
from services.sla import compute_sla_due, sla_status, format_time_remaining
from services.notifications import notify_admins, notify_user
from services.audit import log_action

admin_bp = Blueprint("admin", __name__)


def _surveys_open_count():
    """Surveys still in progress (not converted/rejected)."""
    try:
        from models.extras import Survey
        return Survey.query.filter(
            Survey.status.in_(["new", "assigned", "inspected", "quoted", "approved"])
        ).count()
    except Exception:
        return 0


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
        "sla_breached": MaintenanceRequest.query.filter(
            MaintenanceRequest.sla_breached == True,  # noqa: E712
            MaintenanceRequest.status != "closed",
        ).count(),
        "tickets_open": SupportTicket.query.filter(
            SupportTicket.status.in_(["open", "in_progress"])
        ).count(),
        "surveys_open": _surveys_open_count(),
        "technicians_total": User.query.filter_by(role="technician", active=True).count(),
        "qr_codes_total": QRCode.query.count(),
        "qr_codes_used": QRCode.query.filter(QRCode.device_id.isnot(None)).count(),
        "avg_rating": db.session.query(func.avg(Rating.stars)).filter(Rating.stars != None).scalar() or 0,  # noqa: E711
    }

    recent_requests = MaintenanceRequest.query.order_by(desc(MaintenanceRequest.created_at)).limit(8).all()
    status_counts = dict(
        db.session.query(MaintenanceRequest.status, func.count(MaintenanceRequest.id))
        .group_by(MaintenanceRequest.status).all()
    )

    # Chart: requests per day (last 14 days)
    days = 14
    chart_labels = []
    chart_data = []
    for i in range(days - 1, -1, -1):
        d = now - timedelta(days=i)
        d_start = d.replace(hour=0, minute=0, second=0, microsecond=0)
        d_end = d_start + timedelta(days=1)
        count = MaintenanceRequest.query.filter(
            MaintenanceRequest.created_at >= d_start,
            MaintenanceRequest.created_at < d_end
        ).count()
        chart_labels.append(d.strftime("%m-%d"))
        chart_data.append(count)

    from utils.i18n import t as _t
    status_labels_js = {
        k: _t("status." + k) for k in
        ["new", "assigned", "in_progress", "report_ready", "closed", "cancelled"]
    }

    # Financial: total outstanding receivables across all clients + overdue count
    from models.client import AccountEntry
    total_charges = db.session.query(func.coalesce(func.sum(AccountEntry.amount), 0))\
        .filter(AccountEntry.entry_type == "charge").scalar() or 0
    total_payments = db.session.query(func.coalesce(func.sum(AccountEntry.amount), 0))\
        .filter(AccountEntry.entry_type == "payment").scalar() or 0
    stats["total_receivable"] = float(total_charges) - float(total_payments)
    # Count clients who currently owe money (positive balance)
    overdue_clients = 0
    for cl in Client.query.filter_by(active=True).all():
        if cl.balance > 0:
            overdue_clients += 1
    stats["clients_with_balance"] = overdue_clients
    from services.settings_service import get_setting
    currency = get_setting("currency", "ج.م")

    return render_template(
        "admin/dashboard.html",
        stats=stats, recent_requests=recent_requests, status_counts=status_counts,
        chart_labels=chart_labels, chart_data=chart_data,
        status_labels_js=status_labels_js, currency=currency,
    )


# ================= Search =================
@admin_bp.route("/search")
@admin_required
def global_search():
    q = (request.args.get("q") or "").strip()
    if not q:
        return render_template("admin/search.html", q="", results={})

    like = f"%{q}%"
    results = {
        "clients": Client.query.filter(or_(
            Client.company_name.ilike(like),
            Client.phone.ilike(like),
            Client.code.ilike(like),
        )).limit(10).all(),
        "devices": Device.query.filter(or_(
            Device.name.ilike(like),
            Device.serial_number.ilike(like),
            Device.model.ilike(like),
        )).limit(10).all(),
        "requests": MaintenanceRequest.query.filter(or_(
            MaintenanceRequest.request_number.ilike(like),
            MaintenanceRequest.title.ilike(like),
        )).limit(10).all(),
    }
    return render_template("admin/search.html", q=q, results=results)


# ================= Clients =================
@admin_bp.route("/clients")
@admin_required
def clients_list():
    q = request.args.get("q", "").strip()
    flt = request.args.get("filter", "").strip()  # "" | debtors
    query = Client.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Client.company_name.ilike(like), Client.contact_person.ilike(like),
            Client.phone.ilike(like), Client.code.ilike(like),
        ))
    clients = query.order_by(Client.company_name).all()
    # balance is a computed property, so filter in Python
    if flt == "debtors":
        clients = [c for c in clients if c.balance > 0]
    debtors_count = sum(1 for c in Client.query.all() if c.balance > 0)
    return render_template("admin/clients_list.html", clients=clients, q=q,
                           filter=flt, debtors_count=debtors_count)


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
        log_action("client.created", entity_type="client", entity_id=client.id, details=client.company_name)
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
        for field in ["company_name", "contact_person", "phone", "whatsapp",
                      "email", "address", "city", "notes"]:
            setattr(client, field, request.form.get(field, "").strip())
        client.active = bool(request.form.get("active"))
        if "logo" in request.files and request.files["logo"].filename:
            logo = save_upload(request.files["logo"], subfolder="clients", prefix="logo_")
            if logo:
                client.logo_url = logo
        db.session.commit()
        log_action("client.updated", entity_type="client", entity_id=cid)
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
        log_action("amc.created", entity_type="client", entity_id=cid)
        flash("تم إضافة عقد AMC", "success")
    except Exception as e:
        flash(f"خطأ: {e}", "danger")
    return redirect(url_for("admin.client_view", cid=cid))


# ================= Client Account (financial ledger) =================
@admin_bp.route("/clients/<int:cid>/account")
@admin_required
def client_account(cid):
    client = Client.query.get_or_404(cid)
    from services.settings_service import get_setting
    entries = sorted(client.account_entries, key=lambda e: e.created_at)
    running = 0.0
    rows = []
    for e in entries:
        running += e.signed_amount
        rows.append({"entry": e, "balance": round(running, 2)})
    rows.reverse()  # newest first
    return render_template("admin/client_account.html", client=client, rows=rows,
                           currency=get_setting("currency", "ج.م"))


@admin_bp.route("/clients/<int:cid>/account/charge", methods=["POST"])
@admin_required
def client_add_charge(cid):
    client = Client.query.get_or_404(cid)
    from services.account import add_charge
    amount = request.form.get("amount", "").strip()
    desc = request.form.get("description", "").strip()
    entry = add_charge(client.id, amount, description=desc or "فاتورة يدوية",
                       source="manual", created_by=current_user.id)
    if entry:
        log_action("account.charge_added", entity_type="client", entity_id=cid,
                   details=f"{amount} — {desc}")
        flash("تمت إضافة الفاتورة للحساب", "success")
    else:
        flash("مبلغ غير صحيح", "danger")
    return redirect(url_for("admin.client_account", cid=cid))


@admin_bp.route("/clients/<int:cid>/account/payment", methods=["POST"])
@admin_required
def client_add_payment(cid):
    client = Client.query.get_or_404(cid)
    from services.account import add_payment
    amount = request.form.get("amount", "").strip()
    desc = request.form.get("description", "").strip()
    method = request.form.get("method", "").strip()
    entry = add_payment(client.id, amount, description=desc or "سداد من العميل",
                        method=method, created_by=current_user.id)
    if entry:
        log_action("account.payment_added", entity_type="client", entity_id=cid,
                   details=f"{amount} — {method}")
        flash("تم تسجيل الدفعة", "success")
    else:
        flash("مبلغ غير صحيح", "danger")
    return redirect(url_for("admin.client_account", cid=cid))


@admin_bp.route("/clients/<int:cid>/account/entry/<int:eid>/delete", methods=["POST"])
@admin_required
def client_delete_entry(cid, eid):
    from models.client import AccountEntry
    from services.account import delete_entry
    entry = AccountEntry.query.get_or_404(eid)
    if entry.client_id != cid:
        abort(403)
    delete_entry(eid)
    log_action("account.entry_deleted", entity_type="client", entity_id=cid, details=str(eid))
    flash("تم حذف القيد", "info")
    return redirect(url_for("admin.client_account", cid=cid))


@admin_bp.route("/clients/<int:cid>/account/settings", methods=["POST"])
@admin_required
def client_account_settings(cid):
    client = Client.query.get_or_404(cid)
    limit_raw = request.form.get("credit_limit", "").strip()
    try:
        client.credit_limit = float(limit_raw) if limit_raw else 0
    except ValueError:
        client.credit_limit = 0
    client.block_on_overdue = bool(request.form.get("block_on_overdue"))
    db.session.commit()
    log_action("account.settings_updated", entity_type="client", entity_id=cid)
    flash("تم حفظ إعدادات الحساب", "success")
    return redirect(url_for("admin.client_account", cid=cid))


@admin_bp.route("/clients/<int:cid>/account/request-payment", methods=["POST"])
@admin_required
def client_request_payment(cid):
    client = Client.query.get_or_404(cid)
    balance = client.balance
    if balance <= 0:
        flash("لا يوجد مبلغ مستحق على هذا العميل", "info")
        return redirect(url_for("admin.client_account", cid=cid))
    if not client.notify_number:
        flash("العميل ليس له رقم واتساب مسجّل", "warning")
        return redirect(url_for("admin.client_account", cid=cid))
    from services.whatsapp import notify_payment_request
    sent = notify_payment_request(client, balance)
    if sent:
        log_action("account.payment_requested", entity_type="client", entity_id=cid,
                   details=f"{balance:g}")
        flash("تم إرسال طلب السداد للعميل عبر واتساب", "success")
    else:
        flash("تعذّر إرسال الرسالة", "danger")
    return redirect(url_for("admin.client_account", cid=cid))


# ================= Devices =================
@admin_bp.route("/devices")
@permission_required("devices.view")
def devices_list():
    q = request.args.get("q", "").strip()
    query = Device.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Device.name.ilike(like), Device.serial_number.ilike(like), Device.model.ilike(like),
        ))
    devices = query.order_by(desc(Device.created_at)).all()
    return render_template("admin/devices_list.html", devices=devices, q=q)


@admin_bp.route("/devices/new", methods=["GET", "POST"])
@permission_required("devices.create")
def device_new():
    client_id = request.args.get("client_id", type=int)
    clients = Client.query.filter_by(active=True).order_by(Client.company_name).all()
    if request.method == "POST":
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

        qr_code = request.form.get("qr_code", "").strip()
        if qr_code:
            qr = QRCode.query.filter_by(code=qr_code).first()
            if qr and not qr.device_id:
                qr.device_id = d.id
                qr.bound_at = datetime.utcnow()
                db.session.commit()
                flash(f"تم ربط الجهاز بـ QR {qr_code}", "info")

        log_action("device.created", entity_type="device", entity_id=d.id, details=d.name)
        flash(f"تم إضافة الجهاز: {d.name}", "success")
        return redirect(url_for("admin.device_view", did=d.id))
    return render_template("admin/device_form.html", device=None, clients=clients,
                           preselected_client_id=client_id, device_types=Device.DEVICE_TYPES)


@admin_bp.route("/devices/<int:did>")
@permission_required("devices.view")
def device_view(did):
    device = Device.query.get_or_404(did)
    return render_template("admin/device_view.html", device=device)


@admin_bp.route("/devices/<int:did>/edit", methods=["GET", "POST"])
@permission_required("devices.edit")
def device_edit(did):
    device = Device.query.get_or_404(did)
    clients = Client.query.filter_by(active=True).order_by(Client.company_name).all()
    if request.method == "POST":
        device.client_id = int(request.form.get("client_id"))
        for field in ["name", "device_type", "brand", "model", "serial_number", "location", "notes"]:
            setattr(device, field, request.form.get(field, "").strip())
        install = request.form.get("installation_date"); warranty = request.form.get("warranty_end")
        device.installation_date = datetime.strptime(install, "%Y-%m-%d").date() if install else None
        device.warranty_end = datetime.strptime(warranty, "%Y-%m-%d").date() if warranty else None
        device.active = bool(request.form.get("active"))
        if "photo" in request.files and request.files["photo"].filename:
            p = save_upload(request.files["photo"], subfolder="devices", prefix="dev_")
            if p:
                device.photo_url = p
        db.session.commit()
        log_action("device.updated", entity_type="device", entity_id=did)
        flash("تم حفظ التعديلات", "success")
        return redirect(url_for("admin.device_view", did=did))
    return render_template("admin/device_form.html", device=device, clients=clients,
                           device_types=Device.DEVICE_TYPES)


# ================= Maintenance Requests =================
@admin_bp.route("/requests")
@permission_required("requests.view_all", "requests.view_own")
def requests_list():
    status = request.args.get("status", "")
    priority = request.args.get("priority", "")
    tech_id = request.args.get("tech", type=int)
    query = MaintenanceRequest.query
    if status:
        query = query.filter_by(status=status)
    if priority:
        query = query.filter_by(priority=priority)
    if tech_id:
        query = query.filter_by(technician_id=tech_id)
    reqs = query.order_by(desc(MaintenanceRequest.created_at)).limit(200).all()

    # Compute SLA statuses
    sla_map = {r.id: sla_status(r) for r in reqs}
    sla_time = {r.id: format_time_remaining(r.sla_due_at) for r in reqs}

    techs = User.query.filter_by(role="technician", active=True).all()
    return render_template("admin/requests_list.html", requests=reqs, status=status,
                           priority=priority, tech_id=tech_id, techs=techs,
                           sla_map=sla_map, sla_time=sla_time,
                           status_labels=MaintenanceRequest.STATUS_LABELS)


@admin_bp.route("/requests/<int:rid>", methods=["GET", "POST"])
@permission_required("requests.view_all", "requests.view_own")
def request_view(rid):
    req = MaintenanceRequest.query.get_or_404(rid)
    if request.method == "POST":
        # Add a comment
        body = request.form.get("comment", "").strip()
        if body:
            c = Comment(request_id=req.id, user_id=current_user.id,
                        user_name=current_user.name, body=body)
            db.session.add(c)
            db.session.commit()
            flash("تم إضافة التعليق", "success")
        return redirect(url_for("admin.request_view", rid=rid))

    technicians = User.query.filter_by(role="technician", active=True).all()
    comments = Comment.query.filter_by(request_id=req.id).order_by(Comment.created_at).all()
    followups = Followup.query.filter_by(request_id=req.id).order_by(Followup.scheduled_at.desc()).all()
    from services.settings_service import get_setting
    return render_template("admin/request_view.html", req=req, technicians=technicians,
                           comments=comments, followups=followups,
                           today=datetime.utcnow().strftime("%Y-%m-%d"),
                           now_time=datetime.utcnow().strftime("%H:%M"),
                           currency=get_setting("currency", "ج.م"),
                           sla_status=sla_status(req), sla_time=format_time_remaining(req.sla_due_at))


@admin_bp.route("/requests/new", methods=["GET", "POST"])
@permission_required("requests.create")
def request_new():
    clients = Client.query.filter_by(active=True).order_by(Client.company_name).all()
    if request.method == "POST":
        priority = request.form.get("priority", "normal")
        req = MaintenanceRequest(
            request_number=next_sequence(MaintenanceRequest, "request_number", "MR"),
            client_id=int(request.form.get("client_id")),
            device_id=int(request.form.get("device_id")) if request.form.get("device_id") else None,
            title=request.form.get("title", "").strip(),
            description=request.form.get("description", "").strip(),
            priority=priority,
            created_by=current_user.id,
        )
        # SLA
        req.sla_due_at = compute_sla_due(datetime.utcnow(), priority)

        if "photo" in request.files and request.files["photo"].filename:
            p = save_upload(request.files["photo"], subfolder="reports", prefix="req_")
            if p:
                req.submitted_photo_url = p
        db.session.add(req)
        db.session.commit()

        wa.notify_request_received(req)
        notify_admins(f"طلب صيانة جديد {req.request_number}",
                      f"{req.client.company_name} — {req.title}",
                      "📥", url_for("admin.request_view", rid=req.id))
        log_action("request.created", entity_type="request", entity_id=req.id,
                   details=req.request_number)
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
    # Optional scheduled visit date/time
    visit_date = request.form.get("visit_date", "").strip()
    visit_time = request.form.get("visit_time", "").strip() or "09:00"
    if visit_date:
        try:
            req.visit_at = datetime.strptime(f"{visit_date} {visit_time}", "%Y-%m-%d %H:%M")
        except ValueError:
            req.visit_at = None
    db.session.commit()
    wa.notify_technician_assigned(req)
    visit_txt = f" — موعد الزيارة {req.visit_at.strftime('%Y-%m-%d %H:%M')}" if req.visit_at else ""
    notify_user(tech.id, f"تم تعيينك لطلب {req.request_number}",
                f"{req.client.company_name} - {req.title}{visit_txt}",
                "🔧", url_for("tech.request_view", rid=req.id))
    log_action("request.assigned", entity_type="request", entity_id=req.id, details=tech.name)
    flash(f"تم تعيين {tech.name}", "success")
    return redirect(url_for("admin.request_view", rid=rid))


@admin_bp.route("/requests/<int:rid>/report/edit", methods=["GET", "POST"])
@admin_required
def report_edit(rid):
    """Admin can review/edit the technician's visit report before exporting the PDF."""
    req = MaintenanceRequest.query.get_or_404(rid)
    r = req.visit_report
    if not r:
        flash("لا يوجد تقرير زيارة لهذا الطلب بعد", "warning")
        return redirect(url_for("admin.request_view", rid=rid))

    if request.method == "POST":
        r.diagnosis = request.form.get("diagnosis", "").strip()
        r.actions_taken = request.form.get("actions_taken", "").strip()
        r.spare_parts = request.form.get("spare_parts", "").strip()
        r.recommendations = request.form.get("recommendations", "").strip()
        r.admin_notes = request.form.get("admin_notes", "").strip()
        r.resolved = bool(request.form.get("resolved"))
        r.edited_by_admin = True

        # Optional: admin adds more photos/videos to the report
        from models.attachment import Attachment
        files = request.files.getlist("photos")
        added = 0
        for f in files:
            if not f or not f.filename:
                continue
            p = save_upload(f, subfolder="reports", prefix="admin_")
            if not p:
                continue
            ext = (f.filename.rsplit(".", 1)[-1] or "").lower()
            ftype = "video" if ext in current_app.config.get("VIDEO_EXTENSIONS", set()) else "image"
            db.session.add(Attachment(entity_type="visit_report", entity_id=r.id,
                                      file_url=p, file_type=ftype))
            added += 1
        db.session.commit()
        log_action("report.edited_by_admin", entity_type="request", entity_id=req.id,
                   details=req.request_number)
        flash("تم حفظ تعديلات التقرير" + (f" وإضافة {added} ملف" if added else ""), "success")
        return redirect(url_for("admin.request_view", rid=rid))

    return render_template("admin/report_edit.html", req=req, r=r)


@admin_bp.route("/requests/<int:rid>/close", methods=["POST"])
@admin_required
def request_close(rid):
    req = MaintenanceRequest.query.get_or_404(rid)
    if req.status == "closed":
        flash("الطلب مغلق بالفعل", "info")
        return redirect(url_for("admin.request_view", rid=rid))
    # Optional visit cost (admin only)
    cost_raw = request.form.get("visit_cost", "").strip()
    if cost_raw:
        try:
            req.visit_cost = float(cost_raw)
        except ValueError:
            req.visit_cost = None
    req.status = "closed"
    req.closed_at = datetime.utcnow()
    db.session.commit()
    # Post the visit cost as a charge on the client's account (auto invoice).
    try:
        from services.account import sync_visit_charge
        sync_visit_charge(req, created_by=current_user.id)
    except Exception as e:
        current_app.logger.warning(f"account charge sync failed: {e}")
    wa.notify_request_closed(req)
    log_action("request.closed", entity_type="request", entity_id=req.id)
    flash("تم إغلاق الطلب", "success")
    return redirect(url_for("admin.request_view", rid=rid))


# ================= Projects (was Support Tickets) =================
@admin_bp.route("/tickets")
@permission_required("tickets.view")
def tickets_list():
    status = request.args.get("status", "")
    query = SupportTicket.query
    if status:
        query = query.filter_by(status=status)
    tickets = query.order_by(desc(SupportTicket.created_at)).limit(200).all()
    return render_template("admin/tickets_list.html", tickets=tickets, status=status)


@admin_bp.route("/tickets/new", methods=["GET", "POST"])
@permission_required("tickets.create")
def ticket_new():
    clients = Client.query.filter_by(active=True).order_by(Client.company_name).all()
    if request.method == "POST":
        start = request.form.get("start_date", "").strip()
        t = SupportTicket(
            ticket_number=next_sequence(SupportTicket, "ticket_number", "TK"),
            client_id=int(request.form.get("client_id")),
            subject=request.form.get("subject", "").strip(),
            description=request.form.get("description", "").strip(),
            priority=request.form.get("priority", "normal"),
            start_date=datetime.strptime(start, "%Y-%m-%d").date() if start else None,
            created_by=current_user.id,
        )
        db.session.add(t)
        db.session.commit()
        log_action("ticket.created", entity_type="ticket", entity_id=t.id)
        flash(f"تم إنشاء المشروع {t.ticket_number}", "success")
        return redirect(url_for("admin.ticket_view", tid=t.id))
    return render_template("admin/ticket_form.html", clients=clients)


@admin_bp.route("/tickets/<int:tid>")
@permission_required("tickets.view")
def ticket_view(tid):
    project = SupportTicket.query.get_or_404(tid)
    technicians = User.query.filter_by(role="technician", active=True).all()
    return render_template("admin/ticket_view.html", project=project,
                           technicians=technicians,
                           today=datetime.utcnow().strftime("%Y-%m-%d"))


@admin_bp.route("/tickets/<int:tid>/assign", methods=["POST"])
@admin_required
def ticket_assign(tid):
    from models.request import ProjectMember
    project = SupportTicket.query.get_or_404(tid)
    tech_ids = request.form.getlist("technician_ids")
    tech_ids = [int(x) for x in tech_ids if x]
    lead_id = request.form.get("lead_id", type=int)
    start = request.form.get("start_date", "").strip()

    if not tech_ids:
        flash("اختر فني واحد على الأقل للفريق", "warning")
        return redirect(url_for("admin.ticket_view", tid=tid))
    if lead_id and lead_id not in tech_ids:
        tech_ids.append(lead_id)
    if not lead_id:
        lead_id = tech_ids[0]

    if start:
        try:
            project.start_date = datetime.strptime(start, "%Y-%m-%d").date()
        except ValueError:
            pass

    # Reset team
    ProjectMember.query.filter_by(ticket_id=tid).delete(synchronize_session=False)
    for uid in tech_ids:
        db.session.add(ProjectMember(ticket_id=tid, user_id=uid, is_lead=(uid == lead_id)))
    project.assigned_to = lead_id  # lead
    project.assigned_at = datetime.utcnow()
    if project.status == "open":
        project.status = "in_progress"
    db.session.commit()

    # WhatsApp to the whole team + in-app notifications
    wa.notify_project_team_assigned(project)
    for u in project.team_users:
        role = "قائد الفريق" if u.id == lead_id else "عضو فريق"
        notify_user(u.id, f"تعيينك على مشروع {project.ticket_number} ({role})",
                    f"{project.client.company_name} — {project.subject}",
                    "🏗️", url_for("tech.project_view", tid=project.id))
    log_action("ticket.team_assigned", entity_type="ticket", entity_id=tid,
               details=f"{len(tech_ids)} فنيين")
    flash("تم تعيين الفريق وإرسال الإشعارات", "success")
    return redirect(url_for("admin.ticket_view", tid=tid))


@admin_bp.route("/tickets/<int:tid>/report.pdf")
@permission_required("tickets.view")
def ticket_report_pdf(tid):
    project = SupportTicket.query.get_or_404(tid)
    from services.pdf_service import generate_project_report
    from services.settings_service import get_setting
    pdf = generate_project_report(
        project,
        company_name=get_setting("company_name", current_app.config.get("COMPANY_NAME", "")),
        company_phone=get_setting("company_phone", current_app.config.get("COMPANY_PHONE", "")),
        company_phone_alt=get_setting("company_phone_alt", ""),
        company_email=get_setting("company_email", current_app.config.get("COMPANY_EMAIL", "")),
        logo_url=get_setting("logo_url", ""),
        upload_folder=current_app.config["UPLOAD_FOLDER"],
    )
    return send_file(BytesIO(pdf), mimetype="application/pdf",
                     as_attachment=True,
                     download_name=f"Project-{project.ticket_number}.pdf")


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
    roles = Role.query.order_by(Role.is_system.desc(), Role.name).all()
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if User.query.filter_by(email=email).first():
            flash("البريد الإلكتروني مستخدم بالفعل", "danger")
            return render_template("admin/user_form.html", user=None, clients=clients, roles=roles)

        password = request.form.get("password", "changeme123")
        role_code = request.form.get("role_code", request.form.get("role", "client"))
        legacy_role = role_code if role_code in ("admin", "technician", "client") else "technician"

        u = User(
            name=request.form.get("name", "").strip(),
            email=email,
            phone=request.form.get("phone", "").strip(),
            role=legacy_role,
            role_code=role_code,
            active=True,
            password_hash=generate_password_hash(password),
        )
        if u.role == "client":
            cid = request.form.get("client_id")
            u.client_id = int(cid) if cid else None
        db.session.add(u)
        db.session.commit()

        # Send credentials via WA if enabled
        if request.form.get("send_credentials"):
            notify_new_user_credentials(u, password)
            flash(f"تم إرسال بيانات الدخول لـ {u.name} على واتس", "info")

        log_action("user.created", entity_type="user", entity_id=u.id, details=email)
        flash(f"تم إضافة {u.name}", "success")
        return redirect(url_for("admin.users_list"))
    return render_template("admin/user_form.html", user=None, clients=clients, roles=roles)


@admin_bp.route("/users/<int:uid>/edit", methods=["GET", "POST"])
@admin_required
def user_edit(uid):
    u = User.query.get_or_404(uid)
    clients = Client.query.filter_by(active=True).order_by(Client.company_name).all()
    roles = Role.query.order_by(Role.is_system.desc(), Role.name).all()
    if request.method == "POST":
        u.name = request.form.get("name", "").strip()
        u.phone = request.form.get("phone", "").strip()
        role_code = request.form.get("role_code", u.role_code or u.role)
        u.role_code = role_code
        u.role = role_code if role_code in ("admin", "technician", "client") else u.role
        u.active = bool(request.form.get("active"))
        if u.role == "client":
            cid = request.form.get("client_id")
            u.client_id = int(cid) if cid else None
        else:
            u.client_id = None
        new_pw = request.form.get("password", "").strip()
        if new_pw:
            u.password_hash = generate_password_hash(new_pw)
            if request.form.get("send_credentials"):
                notify_new_user_credentials(u, new_pw)
        db.session.commit()
        log_action("user.updated", entity_type="user", entity_id=uid)
        flash("تم الحفظ", "success")
        return redirect(url_for("admin.users_list"))
    return render_template("admin/user_form.html", user=u, clients=clients, roles=roles)


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
        batch_code=next_qr_batch_code(), count=count, size=size,
        created_by=current_user.id, notes=request.form.get("notes", "").strip(),
    )
    db.session.add(batch)
    db.session.flush()

    last_code = QRCode.query.order_by(desc(QRCode.id)).first()
    start_index = (last_code.id + 1) if last_code else 1
    for i in range(count):
        db.session.add(QRCode(code=next_qr_code(start_index + i), batch_id=batch.id))
    db.session.commit()
    log_action("qr.batch_created", entity_type="qr_batch", entity_id=batch.id, details=f"{count} codes")
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
        batch.codes, size=size,
        app_url=current_app.config.get("APP_URL", ""),
        company_name=current_app.config.get("COMPANY_NAME", ""),
        company_phone=current_app.config.get("COMPANY_PHONE", ""),
    )
    return send_file(BytesIO(pdf), mimetype="application/pdf",
                     as_attachment=True, download_name=f"QR-{batch.batch_code}-{size}.pdf")


# ================= WhatsApp Management =================
@admin_bp.route("/wa")
@admin_required
def wa_home():
    status = get_sidecar_status()
    qr_info = get_sidecar_qr()
    from services.settings_service import get_setting
    sidecar_configured = bool(get_setting("wa_sidecar_url") or current_app.config.get("WA_SIDECAR_URL"))
    return render_template("admin/wa_home.html",
                           status=status, qr_info=qr_info,
                           sidecar_configured=sidecar_configured,
                           wa_enabled=(get_setting("wa_enabled", "false").lower() == "true"))


@admin_bp.route("/wa/qr.json")
@admin_required
def wa_qr_json():
    qr_info = get_sidecar_qr()
    if qr_info is None:
        return jsonify({"error": "sidecar unreachable"}), 503
    return jsonify(qr_info)


@admin_bp.route("/wa/logout", methods=["POST"])
@admin_required
def wa_logout():
    ok = logout_sidecar()
    if ok:
        flash("تم قطع الاتصال. أعد المسح لربط رقم جديد.", "info")
    else:
        flash("فشل قطع الاتصال - راجع الـ sidecar", "danger")
    return redirect(url_for("admin.wa_home"))


@admin_bp.route("/wa/test", methods=["POST"])
@admin_required
def wa_test():
    number = request.form.get("test_number", "").strip()
    text = request.form.get("test_message", "").strip() or "رسالة اختبار من ONE Tracking ✓"
    if not number:
        flash("ادخل رقم للاختبار", "warning")
        return redirect(url_for("admin.wa_home"))
    send_wa(number, text, event_type="test", entity_type="test", entity_id=0)
    flash(f"تم إرسال رسالة الاختبار إلى {number}", "info")
    return redirect(url_for("admin.wa_home"))


@admin_bp.route("/wa/logs")
@admin_required
def wa_logs():
    logs = WhatsAppLog.query.order_by(desc(WhatsAppLog.sent_at)).limit(200).all()
    return render_template("admin/wa_logs.html", logs=logs)


# ================= Follow-up Appointments =================
@admin_bp.route("/requests/<int:rid>/followups/new", methods=["POST"])
@admin_required
def followup_new(rid):
    req = MaintenanceRequest.query.get_or_404(rid)
    # New split date + time fields (easy to fill), with backward-compat for the
    # old single datetime-local field.
    date_str = request.form.get("followup_date", "").strip()
    time_str = request.form.get("followup_time", "").strip() or "09:00"
    scheduled = request.form.get("scheduled_at", "").strip()

    dt = None
    if date_str:
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(f"{date_str} {time_str}", fmt)
                break
            except ValueError:
                continue
    elif scheduled:
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
            try:
                dt = datetime.strptime(scheduled, fmt)
                break
            except ValueError:
                continue

    if dt is None:
        flash("حدد تاريخ المتابعة", "warning")
        return redirect(url_for("admin.request_view", rid=rid))
    tech_id = request.form.get("technician_id")
    fu = Followup(
        request_id=req.id,
        scheduled_at=dt,
        technician_id=int(tech_id) if tech_id else (req.technician_id or None),
        notes=request.form.get("notes", "").strip(),
        created_by=current_user.id,
    )
    db.session.add(fu)
    db.session.commit()
    log_action("followup.created", entity_type="request", entity_id=rid,
               details=dt.strftime("%Y-%m-%d %H:%M"))
    if fu.technician_id:
        notify_user(fu.technician_id, f"موعد متابعة جديد - {req.request_number}",
                    f"{req.client.company_name} في {dt.strftime('%Y-%m-%d %H:%M')}",
                    "📅", url_for("tech.request_view", rid=req.id))
    flash("تم جدولة موعد المتابعة", "success")
    return redirect(url_for("admin.request_view", rid=rid))


@admin_bp.route("/followups/<int:fid>/done", methods=["POST"])
@admin_required
def followup_done(fid):
    fu = Followup.query.get_or_404(fid)
    fu.status = "done"
    fu.done_at = datetime.utcnow()
    db.session.commit()
    log_action("followup.done", entity_type="request", entity_id=fu.request_id)
    flash("تم تعليم المتابعة كمنجزة", "success")
    return redirect(url_for("admin.request_view", rid=fu.request_id))


@admin_bp.route("/followups/<int:fid>/cancel", methods=["POST"])
@admin_required
def followup_cancel(fid):
    fu = Followup.query.get_or_404(fid)
    fu.status = "cancelled"
    db.session.commit()
    log_action("followup.cancelled", entity_type="request", entity_id=fu.request_id)
    flash("تم إلغاء موعد المتابعة", "info")
    return redirect(url_for("admin.request_view", rid=fu.request_id))


# ================= Delete (Admin only) =================
@admin_bp.route("/users/<int:uid>/delete", methods=["POST"])
@admin_required
def user_delete(uid):
    if uid == current_user.id:
        flash("لا يمكنك حذف حسابك", "danger")
        return redirect(url_for("admin.users_list"))
    u = User.query.get_or_404(uid)
    # Detach from requests instead of orphaning
    for r in MaintenanceRequest.query.filter_by(technician_id=uid).all():
        r.technician_id = None
    for r in MaintenanceRequest.query.filter_by(created_by=uid).all():
        r.created_by = None
    for t in SupportTicket.query.filter_by(assigned_to=uid).all():
        t.assigned_to = None
    for t in SupportTicket.query.filter_by(created_by=uid).all():
        t.created_by = None
    name = u.name
    try:
        db.session.delete(u)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"user_delete failed: {e}")
        flash("تعذّر حذف المستخدم بسبب بيانات مرتبطة به", "danger")
        return redirect(url_for("admin.users_list"))
    log_action("user.deleted", entity_type="user", entity_id=uid, details=name)
    flash(f"تم حذف المستخدم: {name}", "success")
    return redirect(url_for("admin.users_list"))


def _purge_requests(req_ids):
    """Delete maintenance requests and every child row that references them."""
    if not req_ids:
        return
    Comment.query.filter(Comment.request_id.in_(req_ids)).delete(synchronize_session=False)
    Followup.query.filter(Followup.request_id.in_(req_ids)).delete(synchronize_session=False)
    Rating.query.filter(Rating.request_id.in_(req_ids)).delete(synchronize_session=False)
    VisitReport.query.filter(VisitReport.request_id.in_(req_ids)).delete(synchronize_session=False)
    MaintenanceRequest.query.filter(MaintenanceRequest.id.in_(req_ids)).delete(synchronize_session=False)


@admin_bp.route("/requests/<int:rid>/delete", methods=["POST"])
@admin_required
def request_delete(rid):
    req = MaintenanceRequest.query.get_or_404(rid)
    num = req.request_number
    try:
        _purge_requests([rid])
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"request_delete failed: {e}")
        flash("تعذّر حذف الطلب بسبب بيانات مرتبطة به", "danger")
        return redirect(url_for("admin.request_view", rid=rid))
    log_action("request.deleted", entity_type="request", entity_id=rid, details=num)
    flash(f"تم حذف الطلب {num}", "success")
    return redirect(url_for("admin.requests_list"))


@admin_bp.route("/tickets/<int:tid>/delete", methods=["POST"])
@admin_required
def ticket_delete(tid):
    t = SupportTicket.query.get_or_404(tid)
    num = t.ticket_number
    try:
        db.session.delete(t)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"ticket_delete failed: {e}")
        flash("تعذّر حذف التذكرة", "danger")
        return redirect(url_for("admin.tickets_list"))
    log_action("ticket.deleted", entity_type="ticket", entity_id=tid, details=num)
    flash(f"تم حذف التذكرة {num}", "success")
    return redirect(url_for("admin.tickets_list"))


@admin_bp.route("/tickets/<int:tid>/close", methods=["POST"])
@admin_required
def ticket_close(tid):
    t = SupportTicket.query.get_or_404(tid)
    t.status = "closed"
    t.closed_at = datetime.utcnow()
    db.session.commit()
    # Final report link + notify team/client
    report_link = ""
    try:
        app_url = current_app.config.get("APP_URL", "")
        report_link = f"{app_url}/admin/tickets/{tid}/report.pdf" if app_url else ""
        wa.notify_project_closed(t, report_link=report_link)
    except Exception as e:
        current_app.logger.warning(f"project close notify failed: {e}")
    log_action("ticket.closed", entity_type="ticket", entity_id=tid)
    flash("تم إغلاق المشروع وإصدار التقرير النهائي", "success")
    return redirect(url_for("admin.ticket_view", tid=tid))


@admin_bp.route("/clients/<int:cid>/delete", methods=["POST"])
@admin_required
def client_delete(cid):
    client = Client.query.get_or_404(cid)
    name = client.company_name
    try:
        # 1) Requests (and all their children)
        req_ids = [r.id for r in MaintenanceRequest.query.filter_by(client_id=cid).all()]
        _purge_requests(req_ids)
        # 2) Tickets
        SupportTicket.query.filter_by(client_id=cid).delete(synchronize_session=False)
        # 3) PM schedules for this client
        PMSchedule.query.filter_by(client_id=cid).delete(synchronize_session=False)
        # 4) Unbind QR codes from this client's devices
        dev_ids = [d.id for d in Device.query.filter_by(client_id=cid).all()]
        if dev_ids:
            for qr in QRCode.query.filter(QRCode.device_id.in_(dev_ids)).all():
                qr.device_id = None
                qr.bound_at = None
            PMSchedule.query.filter(PMSchedule.device_id.in_(dev_ids)).delete(synchronize_session=False)
        # 5) Detach linked user accounts
        for u in User.query.filter_by(client_id=cid).all():
            u.client_id = None
        # 6) Delete the client — devices + AMC contracts cascade via relationships
        db.session.delete(client)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"client_delete failed: {e}")
        flash("تعذّر حذف العميل بسبب بيانات مرتبطة به", "danger")
        return redirect(url_for("admin.client_view", cid=cid))
    log_action("client.deleted", entity_type="client", entity_id=cid, details=name)
    flash(f"تم حذف العميل: {name}", "success")
    return redirect(url_for("admin.clients_list"))


@admin_bp.route("/devices/<int:did>/delete", methods=["POST"])
@admin_required
def device_delete(did):
    d = Device.query.get_or_404(did)
    name = d.name
    try:
        # Requests that reference this device (and their children)
        req_ids = [r.id for r in MaintenanceRequest.query.filter_by(device_id=did).all()]
        _purge_requests(req_ids)
        # PM schedules on this device
        PMSchedule.query.filter_by(device_id=did).delete(synchronize_session=False)
        # Unbind QR codes
        for qr in QRCode.query.filter_by(device_id=did).all():
            qr.device_id = None
            qr.bound_at = None
        db.session.delete(d)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"device_delete failed: {e}")
        flash("تعذّر حذف الجهاز بسبب بيانات مرتبطة به", "danger")
        return redirect(url_for("admin.device_view", did=did))
    log_action("device.deleted", entity_type="device", entity_id=did, details=name)
    flash(f"تم حذف الجهاز: {name}", "success")
    return redirect(url_for("admin.devices_list"))


# ================= Leads (Marketing / Facebook) =================
@admin_bp.route("/leads")
@permission_required("leads.view")
def leads_list():
    from models.extras import Lead
    status = request.args.get("status", "")
    query = Lead.query
    if status:
        query = query.filter_by(status=status)
    leads = query.order_by(Lead.created_at.desc()).all()
    counts = {
        "all": Lead.query.count(),
        "new": Lead.query.filter_by(status="new").count(),
        "contacted": Lead.query.filter_by(status="contacted").count(),
        "converted": Lead.query.filter_by(status="converted").count(),
        "closed": Lead.query.filter_by(status="closed").count(),
    }
    service_url = url_for("public.service_landing", _external=True)
    return render_template("admin/leads_list.html", leads=leads, counts=counts,
                           status=status, service_url=service_url)


@admin_bp.route("/leads/<int:lid>")
@permission_required("leads.view")
def lead_view(lid):
    from models.extras import Lead
    lead = Lead.query.get_or_404(lid)
    return render_template("admin/lead_view.html", lead=lead)


@admin_bp.route("/leads/<int:lid>/status", methods=["POST"])
@permission_required("leads.manage")
def lead_status(lid):
    from models.extras import Lead
    lead = Lead.query.get_or_404(lid)
    new_status = request.form.get("status", "").strip()
    if new_status in Lead.STATUS_LABELS:
        lead.status = new_status
        db.session.commit()
        flash("تم تحديث حالة الطلب", "success")
    return redirect(url_for("admin.leads_list"))


@admin_bp.route("/leads/<int:lid>/convert", methods=["POST"])
@permission_required("leads.manage")
def lead_convert(lid):
    from models.extras import Lead
    lead = Lead.query.get_or_404(lid)
    if lead.converted_request_id:
        flash("تم تحويل هذا الطلب من قبل", "info")
        return redirect(url_for("admin.request_view", rid=lead.converted_request_id))

    # Find or create a client from the lead's phone
    client = Client.query.filter(
        (Client.phone == lead.phone) | (Client.whatsapp == lead.phone)
    ).first()
    if not client:
        cname = lead.name
        if lead.customer_type and lead.customer_type not in ("فرد", "أخرى"):
            cname = f"{lead.name} - {lead.customer_type}"
        client = Client(
            code=next_client_code(),
            company_name=cname,
            contact_person=lead.name,
            phone=lead.phone,
            whatsapp=lead.phone,
            city=lead.location or "",
            address=lead.location or "",
            notes=f"عميل من التسويق ({lead.source}) — {lead.service_type}",
        )
        db.session.add(client)
        db.session.flush()

    priority = "normal"
    title = lead.service_type or "طلب صيانة"
    desc = lead.description or ""
    if lead.location:
        desc = (desc + f"\nالموقع: {lead.location}").strip()
    req = MaintenanceRequest(
        request_number=next_sequence(MaintenanceRequest, "request_number", "MR"),
        client_id=client.id,
        title=title,
        description=desc,
        priority=priority,
        source=lead.source or "marketing",
        contact_name=lead.name,
        contact_phone=lead.phone,
        submitted_photo_url=lead.photo_url or "",
        created_by=current_user.id,
    )
    try:
        req.sla_due_at = compute_sla_due(datetime.utcnow(), priority)
    except Exception:
        pass
    db.session.add(req)
    db.session.flush()

    lead.status = "converted"
    lead.converted_request_id = req.id
    db.session.commit()

    try:
        wa.notify_request_received(req)
    except Exception:
        pass
    notify_admins(f"تحوّل طلب تسويق لطلب صيانة {req.request_number}",
                  f"{client.company_name} — {title}",
                  "📥", url_for("admin.request_view", rid=req.id))
    log_action("lead.converted", entity_type="lead", entity_id=lead.id,
               details=req.request_number)
    flash(f"تم تحويل الطلب إلى طلب صيانة {req.request_number}", "success")
    return redirect(url_for("admin.request_view", rid=req.id))


@admin_bp.route("/leads/<int:lid>/delete", methods=["POST"])
@permission_required("leads.manage")
def lead_delete(lid):
    from models.extras import Lead
    lead = Lead.query.get_or_404(lid)
    db.session.delete(lead)
    db.session.commit()
    log_action("lead.deleted", entity_type="lead", entity_id=lid, details=lead.name)
    flash("تم حذف الطلب", "success")
    return redirect(url_for("admin.leads_list"))


@admin_bp.route("/leads/qr.png")
@permission_required("leads.view")
def leads_qr_png():
    """QR code image that points to the public marketing landing page."""
    from services.qr_service import build_qr_image
    service_url = url_for("public.service_landing", _external=True)
    img = build_qr_image(service_url, box_size=10)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png",
                     download_name="one-service-qr.png")


# ================= Surveys (المعاينات) =================
def _notify_survey_customer(survey):
    """Send the customer a WhatsApp with their survey (inspection) appointment."""
    if not survey.visit_at:
        return
    phone = survey.customer_phone
    if not phone:
        return
    try:
        from services.settings_service import get_setting
        company = get_setting("company_name", "الشركة")
        phone1 = get_setting("company_phone", "")
        msg = (f"أهلاً {survey.customer_name} 👋\n"
               f"تم تحديد موعد معاينة من {company} 📋\n"
               f"📅 الموعد: {survey.visit_at.strftime('%Y-%m-%d %H:%M')}\n"
               f"📍 الموقع: {survey.location}\n"
               f"فريقنا الفني هيزورك في الميعاد ده."
               + (f"\nلأي استفسار: {phone1}" if phone1 else ""))
        wa.send_wa(phone, msg, event_type="survey_visit",
                   entity_type="survey", entity_id=survey.id, dedupe=True)
    except Exception:
        pass


@admin_bp.route("/surveys")
@admin_required
def surveys_list():
    from models.extras import Survey
    status = request.args.get("status", "")
    query = Survey.query
    if status:
        query = query.filter_by(status=status)
    surveys = query.order_by(desc(Survey.created_at)).limit(200).all()
    counts = {
        "all": Survey.query.count(),
        "new": Survey.query.filter_by(status="new").count(),
        "assigned": Survey.query.filter_by(status="assigned").count(),
        "inspected": Survey.query.filter_by(status="inspected").count(),
        "quoted": Survey.query.filter_by(status="quoted").count(),
        "approved": Survey.query.filter_by(status="approved").count(),
        "converted": Survey.query.filter_by(status="converted").count(),
    }
    return render_template("admin/surveys_list.html", surveys=surveys,
                           counts=counts, status=status)


@admin_bp.route("/surveys/new", methods=["GET", "POST"])
@admin_required
def survey_new():
    from models.extras import Survey
    clients = Client.query.filter_by(active=True).order_by(Client.company_name).all()
    technicians = User.query.filter_by(role="technician", active=True).all()
    if request.method == "POST":
        client_id = request.form.get("client_id") or None
        tech_id = request.form.get("technician_id") or None
        visit_raw = request.form.get("visit_at", "").strip()
        visit_at = None
        if visit_raw:
            for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
                try:
                    visit_at = datetime.strptime(visit_raw, fmt); break
                except ValueError:
                    continue
        s = Survey(
            survey_number=next_sequence(Survey, "survey_number", "SV"),
            client_id=int(client_id) if client_id else None,
            contact_name=request.form.get("contact_name", "").strip(),
            contact_phone=request.form.get("contact_phone", "").strip(),
            contact_email=request.form.get("contact_email", "").strip(),
            location=request.form.get("location", "").strip(),
            description=request.form.get("description", "").strip(),
            technician_id=int(tech_id) if tech_id else None,
            visit_at=visit_at,
            status="assigned" if tech_id else "new",
            created_by=current_user.id,
        )
        db.session.add(s)
        db.session.commit()
        # Notify technician
        if s.technician_id:
            when = f" بتاريخ {s.visit_at.strftime('%Y-%m-%d %H:%M')}" if s.visit_at else ""
            notify_user(s.technician_id, f"معاينة جديدة {s.survey_number}",
                        f"{s.customer_name} — {s.location}{when}",
                        "📋", url_for("tech.survey_view", sid=s.id))
            try:
                tech = User.query.get(s.technician_id)
                if tech and tech.phone:
                    wa.send_wa(tech.phone,
                               f"📋 معاينة جديدة {s.survey_number}\n"
                               f"العميل: {s.customer_name}\nالموقع: {s.location}{when}",
                               event_type="survey_assigned", entity_type="survey", entity_id=s.id)
            except Exception:
                pass
        # Notify customer of the survey appointment
        _notify_survey_customer(s)
        log_action("survey.created", entity_type="survey", entity_id=s.id,
                   details=s.survey_number)
        flash(f"تم إنشاء المعاينة {s.survey_number}", "success")
        return redirect(url_for("admin.survey_view", sid=s.id))
    return render_template("admin/survey_new.html", clients=clients, technicians=technicians)


@admin_bp.route("/surveys/<int:sid>")
@admin_required
def survey_view(sid):
    from models.extras import Survey
    survey = Survey.query.get_or_404(sid)
    technicians = User.query.filter_by(role="technician", active=True).all()
    return render_template("admin/survey_view.html", survey=survey,
                           technicians=technicians,
                           now_local=datetime.utcnow().strftime("%Y-%m-%dT%H:%M"))


@admin_bp.route("/surveys/<int:sid>/assign", methods=["POST"])
@admin_required
def survey_assign(sid):
    from models.extras import Survey
    survey = Survey.query.get_or_404(sid)
    tech_id = request.form.get("technician_id") or None
    visit_raw = request.form.get("visit_at", "").strip()
    if visit_raw:
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                survey.visit_at = datetime.strptime(visit_raw, fmt); break
            except ValueError:
                continue
    if tech_id:
        survey.technician_id = int(tech_id)
        if survey.status == "new":
            survey.status = "assigned"
    db.session.commit()
    if survey.technician_id:
        when = f" بتاريخ {survey.visit_at.strftime('%Y-%m-%d %H:%M')}" if survey.visit_at else ""
        notify_user(survey.technician_id, f"تم إسنادك لمعاينة {survey.survey_number}",
                    f"{survey.customer_name} — {survey.location}{when}",
                    "📋", url_for("tech.survey_view", sid=survey.id))
    # Notify customer of the (updated) appointment
    _notify_survey_customer(survey)
    flash("تم تحديث بيانات الإسناد وإبلاغ العميل بالموعد", "success")
    return redirect(url_for("admin.survey_view", sid=sid))


@admin_bp.route("/surveys/<int:sid>/items/add", methods=["POST"])
@admin_required
def survey_item_add(sid):
    from models.extras import Survey, SurveyItem
    survey = Survey.query.get_or_404(sid)
    name = request.form.get("name", "").strip()
    if name:
        price = request.form.get("unit_price", "").strip()
        db.session.add(SurveyItem(
            survey_id=survey.id, name=name,
            spec=request.form.get("spec", "").strip(),
            quantity=request.form.get("quantity", type=int) or 1,
            unit_price=float(price) if price else None,
            notes=request.form.get("notes", "").strip(),
            added_by_role="admin",
        ))
        db.session.commit()
        flash("تم إضافة البند", "success")
    return redirect(url_for("admin.survey_view", sid=sid))


@admin_bp.route("/surveys/items/<int:item_id>/delete", methods=["POST"])
@admin_required
def survey_item_delete(item_id):
    from models.extras import SurveyItem
    it = SurveyItem.query.get_or_404(item_id)
    sid = it.survey_id
    db.session.delete(it)
    db.session.commit()
    flash("تم حذف البند", "success")
    return redirect(url_for("admin.survey_view", sid=sid))


@admin_bp.route("/surveys/<int:sid>/quote", methods=["POST"])
@admin_required
def survey_quote(sid):
    from models.extras import Survey
    survey = Survey.query.get_or_404(sid)
    if "quote_file" in request.files and request.files["quote_file"].filename:
        p = save_upload(request.files["quote_file"], subfolder="quotes", prefix="quote_")
        if p:
            survey.quote_file_url = p
        else:
            flash("صيغة الملف غير مسموحة (ارفع PDF)", "warning")
            return redirect(url_for("admin.survey_view", sid=sid))
    amount = request.form.get("quote_amount", "").strip()
    if amount:
        try:
            survey.quote_amount = float(amount)
        except ValueError:
            pass
    # Save/update the customer email (for surveys not linked to a full client)
    ce = request.form.get("contact_email", "").strip()
    if ce and not (survey.client and getattr(survey.client, "email", "")):
        survey.contact_email = ce
    survey.quote_sent_at = datetime.utcnow()
    if survey.status in ("assigned", "inspected", "new"):
        survey.status = "quoted"
    db.session.commit()
    # Send quote to customer via WhatsApp (best effort) — include a link to the file
    try:
        phone = survey.customer_phone
        if phone:
            from services.settings_service import get_setting
            company = get_setting("company_name", "الشركة")
            base = (get_setting("app_url", "") or request.url_root or "").rstrip("/")
            msg = (f"أهلاً {survey.customer_name} 👋\n"
                   f"ده عرض السعر الخاص بمعاينة {survey.survey_number} من {company}.")
            if survey.quote_amount:
                cur = get_setting("currency", "ج.م")
                msg += f"\nالإجمالي: {survey.quote_amount:g} {cur}"
            if survey.quote_file_url:
                link = survey.quote_file_url
                if base and link.startswith("/"):
                    link = base + link
                msg += f"\n📄 تحميل عرض السعر:\n{link}"
            msg += "\nفي انتظار موافقتك ✅"
            wa.send_wa(phone, msg, event_type="survey_quote",
                       entity_type="survey", entity_id=survey.id)
    except Exception:
        pass
    # Send the quote by email too (if the customer has an email on file)
    try:
        if survey.customer_email:
            from services.settings_service import get_setting
            from services.email_service import notify_customer_email
            company = get_setting("company_name", "الشركة")
            base = (get_setting("app_url", "") or request.url_root or "").rstrip("/")
            ebody = (f"أهلاً {survey.customer_name} 👋\n"
                     f"ده عرض السعر الخاص بمعاينة {survey.survey_number} من {company}.")
            if survey.quote_amount:
                cur = get_setting("currency", "ج.م")
                ebody += f"\nالإجمالي: {survey.quote_amount:g} {cur}"
            # Attach the quote PDF to the email so the customer gets the file itself
            attachments = []
            if survey.quote_file_url:
                link = survey.quote_file_url
                if base and link.startswith("/"):
                    link = base + link
                ebody += f"\n📄 عرض السعر مرفق بالإيميل (وللتحميل: {link})"
                try:
                    if survey.quote_file_url.startswith("/static/uploads/"):
                        rel = survey.quote_file_url[len("/static/uploads/"):]
                        fpath = os.path.join(current_app.config["UPLOAD_FOLDER"], rel)
                        if os.path.isfile(fpath):
                            with open(fpath, "rb") as fh:
                                fname = f"عرض-سعر-{survey.survey_number}.pdf"
                                attachments.append((fname, fh.read()))
                except Exception:
                    pass
            ebody += "\nفي انتظار موافقتك ✅"
            notify_customer_email(survey.customer_email,
                                  f"عرض سعر معاينة {survey.survey_number} — {company}",
                                  ebody, attachments=attachments or None)
    except Exception:
        pass
    log_action("survey.quoted", entity_type="survey", entity_id=survey.id)
    flash("تم حفظ عرض السعر وإرساله للعميل", "success")
    return redirect(url_for("admin.survey_view", sid=sid))


@admin_bp.route("/surveys/<int:sid>/approve", methods=["POST"])
@admin_required
def survey_approve(sid):
    from models.extras import Survey
    survey = Survey.query.get_or_404(sid)
    survey.status = "approved"
    survey.approved_at = datetime.utcnow()
    survey.decision_note = request.form.get("decision_note", "").strip()
    db.session.commit()
    log_action("survey.approved", entity_type="survey", entity_id=survey.id)
    flash("تم تسجيل موافقة العميل — تقدر تحوّلها لمشروع الآن", "success")
    return redirect(url_for("admin.survey_view", sid=sid))


@admin_bp.route("/surveys/<int:sid>/reject", methods=["POST"])
@admin_required
def survey_reject(sid):
    from models.extras import Survey
    survey = Survey.query.get_or_404(sid)
    survey.status = "rejected"
    survey.decision_note = request.form.get("decision_note", "").strip()
    db.session.commit()
    log_action("survey.rejected", entity_type="survey", entity_id=survey.id)
    flash("تم تسجيل رفض العميل", "info")
    return redirect(url_for("admin.survey_view", sid=sid))


@admin_bp.route("/surveys/<int:sid>/convert", methods=["POST"])
@admin_required
def survey_convert(sid):
    from models.extras import Survey
    survey = Survey.query.get_or_404(sid)
    if survey.converted_ticket_id:
        flash("تم تحويل هذه المعاينة من قبل", "info")
        return redirect(url_for("admin.ticket_view", tid=survey.converted_ticket_id))

    # Installation date (chosen by admin before conversion)
    install_raw = request.form.get("install_at", "").strip()
    install_dt = None
    if install_raw:
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                install_dt = datetime.strptime(install_raw, fmt); break
            except ValueError:
                continue
    if install_dt:
        survey.install_at = install_dt

    # Ensure there's a client to attach the project to
    client = survey.client
    if not client:
        client = Client.query.filter(
            (Client.phone == survey.contact_phone) | (Client.whatsapp == survey.contact_phone)
        ).first() if survey.contact_phone else None
    if not client:
        client = Client(
            code=next_client_code(),
            company_name=survey.contact_name or f"عميل معاينة {survey.survey_number}",
            contact_person=survey.contact_name or "",
            phone=survey.contact_phone or "",
            whatsapp=survey.contact_phone or "",
            city=survey.location or "",
            address=survey.location or "",
            notes=f"عميل من معاينة {survey.survey_number}",
        )
        db.session.add(client)
        db.session.flush()

    # Build the installation scope (device items) into the project description
    lines = [f"مشروع تركيب ناتج عن المعاينة {survey.survey_number}."]
    if survey.location:
        lines.append(f"الموقع: {survey.location}")
    if survey.description:
        lines.append(f"طلب العميل: {survey.description}")
    if survey.inspection_notes:
        lines.append(f"\nملاحظات المعاينة:\n{survey.inspection_notes}")
    if survey.items:
        lines.append("\nبنود الأجهزة المطلوب تركيبها:")
        for i, it in enumerate(survey.items, 1):
            row = f"{i}. {it.name}"
            if it.spec:
                row += f" ({it.spec})"
            row += f" × {it.quantity or 1}"
            lines.append(row)
    if survey.quote_amount:
        lines.append(f"\nقيمة العرض المعتمد: {survey.quote_amount:g}")
    if install_dt:
        lines.append(f"\n📅 موعد التركيب: {install_dt.strftime('%Y-%m-%d %H:%M')}")

    t = SupportTicket(
        ticket_number=next_sequence(SupportTicket, "ticket_number", "TK"),
        client_id=client.id,
        subject=f"تركيب — {survey.location or survey.customer_name}",
        description="\n".join(lines),
        priority="normal",
        start_date=install_dt.date() if install_dt else datetime.utcnow().date(),
        created_by=current_user.id,
    )
    db.session.add(t)
    db.session.flush()
    survey.converted_ticket_id = t.id
    survey.status = "converted"
    db.session.commit()

    # Notify the customer of the installation appointment
    try:
        phone = survey.customer_phone
        if phone and install_dt:
            from services.settings_service import get_setting
            company = get_setting("company_name", "الشركة")
            phone1 = get_setting("company_phone", "")
            msg = (f"أهلاً {survey.customer_name} 🎉\n"
                   f"تم اعتماد التركيب مع {company}.\n"
                   f"📅 موعد التركيب: {install_dt.strftime('%Y-%m-%d %H:%M')}\n"
                   f"📍 الموقع: {survey.location}\n"
                   f"فريقنا هيكون عندك في الميعاد ده."
                   + (f"\nلأي استفسار: {phone1}" if phone1 else ""))
            wa.send_wa(phone, msg, event_type="survey_install",
                       entity_type="survey", entity_id=survey.id, dedupe=True)
    except Exception:
        pass

    notify_admins(f"تحوّلت معاينة لمشروع تركيب {t.ticket_number}",
                  f"{client.company_name} — {len(survey.items)} بند",
                  "🏗️", url_for("admin.ticket_view", tid=t.id))
    log_action("survey.converted", entity_type="survey", entity_id=survey.id,
               details=t.ticket_number)
    flash(f"تم تحويل المعاينة إلى مشروع تركيب {t.ticket_number}", "success")
    return redirect(url_for("admin.ticket_view", tid=t.id))


@admin_bp.route("/surveys/<int:sid>/delete", methods=["POST"])
@admin_required
def survey_delete(sid):
    from models.extras import Survey
    survey = Survey.query.get_or_404(sid)
    from models.attachment import Attachment
    Attachment.query.filter_by(entity_type="survey", entity_id=sid).delete(synchronize_session=False)
    num = survey.survey_number
    db.session.delete(survey)
    db.session.commit()
    log_action("survey.deleted", entity_type="survey", entity_id=sid, details=num)
    flash("تم حذف المعاينة", "success")
    return redirect(url_for("admin.surveys_list"))
